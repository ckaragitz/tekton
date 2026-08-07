#!/usr/bin/env python
"""instbug_forensics.py -- THE FORENSIC DIFF of the product-path bug.

WHAT the Autodesk consistency audit sees: files that LOAD MULTIPLE family
documents or PLACE INSTANCES onto the genesis lineage trip
Revit-DocumentCorruption (extractor -1073742517) while the SAME operations on
sample bases pass.  This tool measures EVERYTHING about the family-load +
instance registration of a file -- the four registries entry-by-entry, the
partition save units (separators, block headers, gzip framing), the
ContentDocuments entries, the ADocument ContentTable / FamilyMgr / tracking
registries (+ a typed-id scan of EVERY ADocument registry naming ids in a
range), the host elements' ElemTable rows and unit-0 record order/runs, the
Contents (DocumentStorageIndex) counters, History/DIT/PartitionTable digests
-- and diffs the LOAD DELTA of a failing-lineage file against the LOAD DELTA
of viewer-PASSED files.

Matched pairs measured (docs/inbox/instbug-forensics.md):
  PASS  L_v2_panel_loaded.rvt        vs samples/rstbasicsampleproject.rvt
  FAIL* experiments/frontdoor/demo-250v/_stages/stage_L1_pp1.rvt vs stage_L0_base.rvt
  PASS  experiments/render/g12/WF_nofix.rvt vs experiments/ifc_room/electrical_room_2500a_walls_only.rvt
  ...plus the demo ladder stage_L1..L6 -> prompt_room and the acceptance
  controls (V20 commit-onto-sample).

CLI (repo root)::

    .venv/bin/python tools/instbug_forensics.py survey FILE [--ids-from N]
    .venv/bin/python tools/instbug_forensics.py delta BASE DERIVED
    .venv/bin/python tools/instbug_forensics.py all          # the whole evidence run
    .venv/bin/python tools/instbug_forensics.py unitdiff A B # unit-by-unit byte diff

Read-only over every stream; writes JSON only under
experiments/instbug/forensics/.  Territory: instbug-forensics stream.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import uuid
import zlib
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT_DIR = os.path.join(ROOT, "experiments", "instbug", "forensics")


def _relp(p: str) -> str:
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:
        return p


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


# ---------------------------------------------------------------------------
# partition survey
# ---------------------------------------------------------------------------

def _gzip_flavor(raw: bytes, start: int, end: int) -> Dict[str, Any]:
    """Facts about one gzip member's container bytes (not its payload)."""
    hdr = raw[start:start + 10]
    out: Dict[str, Any] = {}
    if len(hdr) < 10 or hdr[:3] != b"\x1f\x8b\x08":
        out["bad_magic"] = hdr[:4].hex()
        return out
    out["flg"] = hdr[3]
    out["mtime"] = struct.unpack_from("<I", hdr, 4)[0]
    out["xfl"] = hdr[8]
    out["os"] = hdr[9]
    # sync-flush signature: an empty stored block 00 00 00 FF FF before the
    # final block is not directly visible; instead fingerprint the deflate
    # first byte + whether the member ends exactly at `end`
    out["deflate_first"] = raw[start + 10] if start + 10 < len(raw) else None
    out["member_len"] = end - start
    return out


def survey_partition(raw_logical: bytes) -> Dict[str, Any]:
    from rvt.partitions import StreamWalker
    w = StreamWalker(raw_logical, inflate=True, keep_data=True)
    rep: Dict[str, Any] = {"errors": list(w.errors)[:8]}
    rep["stream_header"] = raw_logical[:18].hex()
    rep["elem_table_count_hdr"] = struct.unpack_from("<I", raw_logical, 14)[0]
    units = []
    for u in w.units:
        ub: Dict[str, Any] = {"index": u.index}
        g = getattr(u, "guid", None)
        ub["guid"] = str(uuid.UUID(bytes_le=g)) if g else None
        ub["record_count_hdr"] = getattr(u, "record_count", None)
        blocks = [b for b in w.blocks if b.unit == u.index]
        ub["n_blocks"] = len(blocks)
        per_seq: Dict[int, int] = {}
        bl = []
        for b in sorted(blocks, key=lambda x: x.hdr_offset):
            per_seq[b.seq] = per_seq.get(b.seq, 0) + b.n_records
            gz = _gzip_flavor(raw_logical, b.member_offset,
                              b.member_offset + b.member_len)
            bl.append({
                "seq": b.seq, "flags": b.flags, "A": b.n_records,
                "B": b.size_hint, "C": getattr(b, "body_bytes", None),
                "hdr_off": b.hdr_offset, "payload_len": (len(b.data) if b.data else None),
                "payload_md5": (md5(b.data) if b.data else None),
                "gzip": gz,
                "trailer": raw_logical[b.member_offset + b.member_len:
                                       b.member_offset + b.member_len + 6].hex(),
            })
        ub["records_per_seq"] = per_seq
        ub["blocks"] = bl
        # the 28-byte unit separator raw bytes (units > 0)
        if u.index > 0 and blocks:
            first_hdr = min(b.hdr_offset for b in blocks)
            ub["separator_hex"] = raw_logical[first_hdr - 28:first_hdr].hex()
        units.append(ub)
    rep["units"] = units
    rep["n_units"] = len(w.units)
    rep["end_offset"] = w.end_offset
    rep["end_record_hex"] = w.end_record.hex() if w.end_record else None
    rep["bytes_after_end"] = len(raw_logical) - (w.end_offset + len(w.end_record or b""))
    rep["magic_count"] = raw_logical.count(b"Data generated")
    return rep


# ---------------------------------------------------------------------------
# ADocument registry survey
# ---------------------------------------------------------------------------

def _appinfo_slot(value: dict, class_name: str) -> Optional[dict]:
    mgr = (value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def survey_latest(latest_payload: bytes, id_lo: int, id_hi: int) -> Dict[str, Any]:
    from rvt import adocument as A
    from rvt.regdiff import TypedIdWalker
    lat = A.decode_latest(latest_payload)
    v = lat.value
    rep: Dict[str, Any] = {"clean": bool(lat.clean), "bytes": len(latest_payload)}

    # ContentTable, in stream order
    ct = ((v.get("m_oContentTable") or {}).get("value") or {})
    recs = ct.get("m_ContentRecSet") or []
    ents = []
    for r in recs:
        g = str((r.get("m_ContentKey") or {}).get("m_guidKey") or "")
        h = r.get("m_history") or {}
        ents.append({
            "guid": g.lower(),
            "author": r.get("m_author"),
            "creation": ((h.get("m_creationDate") or {}).get("m_id")),
            "modification": ((h.get("m_lastModificationDate") or {}).get("m_id")),
            "user_modification": ((h.get("m_lastUserModificationDate") or {}).get("m_id")),
            "original_elem": ((h.get("m_originalElementId") or {}).get("m_id64")),
            "episode_counts": [((p.get("first") or {}).get("m_id"), p.get("second"))
                               for p in (r.get("m_EpisodeCounts") or [])],
        })
    rep["content_table"] = ents
    order = [e["guid"] for e in ents]
    rep["content_table_sorted_by_guid_bytes_le"] = (
        order == sorted(order, key=lambda g: uuid.UUID(g).bytes_le if g else b""))
    rep["content_table_sorted_by_guid_str"] = (order == sorted(order))

    # FamilyMgr slot: dump EVERYTHING in the slot, not only the array
    fm = _appinfo_slot(v, "FamilyMgr")
    if fm is not None:
        rep["family_mgr_fields"] = sorted(fm.keys())
        rep["family_mgr_entries"] = [
            {"surrogate": e.get("m_surrogateId"),
             "guids": [str(g).lower() for g in (e.get("m_familyDocGUIDs") or [])]}
            for e in (fm.get("m_arrLoadedFamilyInfo") or [])]
        surr = [e["surrogate"] for e in rep["family_mgr_entries"]]
        rep["family_mgr_sorted_by_surrogate"] = (surr == sorted(surr))
        rep["family_mgr_other"] = {k: fm[k] for k in fm
                                   if k != "m_arrLoadedFamilyInfo"
                                   and not isinstance(fm[k], (list, dict))}
    else:
        rep["family_mgr_entries"] = None

    # ElementTrackingData
    etd = _appinfo_slot(v, "ElementTrackingData")
    if etd is not None:
        t: Dict[str, Any] = {}
        for fld in ("m_symbols", "m_elems"):
            rows = etd.get(fld) or []
            t[fld] = {str(r.get("m_categoryId")): list(r.get("m_elemIdSet") or [])
                      for r in rows}
        rep["element_tracking"] = t
    else:
        rep["element_tracking"] = None

    # the FULL registry surface: every ElementId-typed leaf naming an id in
    # [id_lo, id_hi] anywhere in the ADocument
    tw = TypedIdWalker()
    leaves = tw.leaves(v, "ADocument")
    hits: Dict[str, List[int]] = {}
    for lf in leaves:
        if id_lo <= lf.value <= id_hi:
            # collapse indices for grouping
            key = "".join(ch for ch in lf.path)
            import re
            key = re.sub(r"\[\d+\]", "[]", key)
            hits.setdefault(key, []).append(lf.value)
    rep["registry_paths_naming_range"] = {k: sorted(set(vv)) for k, vv in sorted(hits.items())}
    rep["n_id_leaves_total"] = len(leaves)
    return rep


# ---------------------------------------------------------------------------
# whole-file survey
# ---------------------------------------------------------------------------

def survey(path: str, ids_from: Optional[int] = None) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.famgen.factory import parse_content_documents
    from rvt.stream_encoders import decode_elemtable, decode_contents
    rep: Dict[str, Any] = {"path": _relp(path), "size": os.path.getsize(path)}
    with open_rvt(path) as f:
        parts = f.partition_streams()
        rep["partition_streams"] = parts
        pname = parts[0]
        logical = f.logical(pname)
        rep["partition"] = survey_partition(logical)
        # ContentDocuments
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
        try:
            ents, tail = parse_content_documents(cd)
            rep["content_documents"] = {
                "entries": [{"guid": str(g).lower(), "adoc_len": len(a)} for g, a in ents],
                "order_sorted_bytes_le": (
                    [str(g).lower() for g, _ in ents]
                    == sorted([str(g).lower() for g, _ in ents],
                              key=lambda s: uuid.UUID(s).bytes_le)),
                "tail_len": len(tail),
            }
        except Exception as ex:
            rep["content_documents"] = {"error": repr(ex)}
        # ElemTable
        et = decode_elemtable(f.inflate("Global/ElemTable"))
        recs = et["records"]
        rep["elemtable"] = {
            "count": len(recs),
            "footer": et.get("footer"),
            "max_modified_ep": max(r[2] for r in recs),
        }
        wm = et.get("footer", {}).get("last_id") if isinstance(et.get("footer"), dict) else None
        lo = ids_from if ids_from is not None else 1472525
        rows = []
        for r in recs:
            if r[0] >= lo:
                rows.append({"id": r[0], "tuple": list(r)})
        rep["elemtable"]["rows_from"] = lo
        rep["elemtable"]["rows"] = rows
        # Latest
        lat_payload = f.inflate("Global/Latest")
        hi = (wm or (1 << 62))
        rep["latest"] = survey_latest(lat_payload, lo, hi)
        # Contents / History / DIT / PartitionTable digests
        try:
            con_raw = f.raw("Contents")
            # 24-byte prologue + gzip
            infl = zlib.decompress(con_raw[24:24 + (len(con_raw) - 24)], 31)
            rep["contents"] = {k: v for k, v in decode_contents(infl).items()
                               if k in ("counters", "counter_g", "creation_guid",
                                        "trailing_pairs", "hdr5", "build")}
        except Exception as ex:
            rep["contents"] = {"error": repr(ex)}
        for nm in ("Global/History", "Global/DocumentIncrementTable",
                   "Global/PartitionTable"):
            try:
                b = f.inflate(nm)
                rep[nm.split("/")[-1]] = {"bytes": len(b), "md5": md5(b)}
            except Exception as ex:
                rep[nm.split("/")[-1]] = {"error": repr(ex)}
        try:
            bfi = f.raw("BasicFileInfo")
            rep["BasicFileInfo"] = {"bytes": len(bfi), "md5": md5(bfi)}
        except Exception:
            pass
    return rep


# ---------------------------------------------------------------------------
# unit-0 record order (the run law) for the added ids
# ---------------------------------------------------------------------------

def unit0_tail(path: str) -> Dict[str, Any]:
    """The regdiff run-law verdict of unit-0's seq-102 record stream."""
    from rvt.regdiff import RegDoc, run_law_report
    try:
        return run_law_report(RegDoc(path), 102)
    except Exception as ex:
        return {"error": repr(ex)}


# ---------------------------------------------------------------------------
# delta between base and derived
# ---------------------------------------------------------------------------

def _unit_key(u: Dict[str, Any]) -> str:
    return u["guid"] or f"unit0"


def delta(base: Dict[str, Any], der: Dict[str, Any]) -> Dict[str, Any]:
    d: Dict[str, Any] = {"base": base["path"], "derived": der["path"]}
    # units
    bu = {(_unit_key(u)): u for u in base["partition"]["units"]}
    du = {(_unit_key(u)): u for u in der["partition"]["units"]}
    d["units_added"] = [k for k in du if k not in bu]
    d["units_removed"] = [k for k in bu if k not in du]
    changed = []
    for k in du:
        if k in bu:
            a, b = bu[k], du[k]
            delta_fields = {}
            if a["records_per_seq"] != b["records_per_seq"]:
                delta_fields["records_per_seq"] = [a["records_per_seq"], b["records_per_seq"]]
            pa = [x["payload_md5"] for x in a["blocks"]]
            pb = [x["payload_md5"] for x in b["blocks"]]
            if pa != pb:
                delta_fields["payload_md5"] = "CHANGED"
            ga = [(x["gzip"].get("flg"), x["gzip"].get("mtime"), x["gzip"].get("xfl"),
                   x["gzip"].get("os")) for x in a["blocks"]]
            gb = [(x["gzip"].get("flg"), x["gzip"].get("mtime"), x["gzip"].get("xfl"),
                   x["gzip"].get("os")) for x in b["blocks"]]
            if ga != gb:
                delta_fields["gzip_container"] = [ga, gb]
            fa = [(x["seq"], x["flags"], x["A"]) for x in a["blocks"]]
            fb = [(x["seq"], x["flags"], x["A"]) for x in b["blocks"]]
            if fa != fb:
                delta_fields["block_shape"] = [fa, fb]
            if a.get("separator_hex") != b.get("separator_hex"):
                delta_fields["separator"] = [a.get("separator_hex"), b.get("separator_hex")]
            if delta_fields:
                changed.append({("unit " + k): delta_fields})
    d["units_changed"] = changed
    d["hdr_count"] = [base["partition"]["elem_table_count_hdr"],
                      der["partition"]["elem_table_count_hdr"]]
    d["end_record_same"] = (base["partition"]["end_record_hex"]
                            == der["partition"]["end_record_hex"])
    # content documents
    bg = [e["guid"] for e in base["content_documents"].get("entries", [])]
    dg = [e["guid"] for e in der["content_documents"].get("entries", [])]
    d["contentdocs_added"] = [g for g in dg if g not in bg]
    d["contentdocs_order_sorted"] = der["content_documents"].get("order_sorted_bytes_le")
    # content table
    bct = {e["guid"]: e for e in base["latest"]["content_table"]}
    dct = der["latest"]["content_table"]
    d["contenttable_added"] = [e for e in dct if e["guid"] not in bct]
    d["contenttable_order"] = [e["guid"][:8] for e in dct]
    d["contenttable_sorted"] = der["latest"]["content_table_sorted_by_guid_bytes_le"]
    # family mgr
    bfm = base["latest"].get("family_mgr_entries") or []
    dfm = der["latest"].get("family_mgr_entries") or []
    d["familymgr_added"] = [e for e in dfm if e not in bfm]
    d["familymgr_sorted"] = der["latest"].get("family_mgr_sorted_by_surrogate")
    # tracking
    d["element_tracking_base"] = base["latest"].get("element_tracking")
    d["element_tracking_derived"] = der["latest"].get("element_tracking")
    # registry surface
    d["registry_paths_naming_new_ids"] = der["latest"].get("registry_paths_naming_range")
    # elemtable
    d["elemtable_counts"] = [base["elemtable"]["count"], der["elemtable"]["count"]]
    d["new_rows"] = der["elemtable"]["rows"]
    # small streams
    for nm in ("History", "DocumentIncrementTable", "PartitionTable", "BasicFileInfo"):
        a, b = base.get(nm, {}), der.get(nm, {})
        d[nm] = ("SAME" if a.get("md5") == b.get("md5") else
                 {"base": a, "derived": b})
    d["contents_counters"] = [base.get("contents", {}).get("counters"),
                              der.get("contents", {}).get("counters")]
    d["contents_counter_g"] = [base.get("contents", {}).get("counter_g"),
                               der.get("contents", {}).get("counter_g")]
    return d


# ---------------------------------------------------------------------------
# raw unit byte diff between two files (same GUID units)
# ---------------------------------------------------------------------------

def unitdiff(path_a: str, path_b: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    out: Dict[str, Any] = {"a": _relp(path_a), "b": _relp(path_b), "units": []}

    def unit_bytes(path: str) -> Dict[str, Tuple[bytes, Dict]]:
        with open_rvt(path) as f:
            logical = f.logical(f.partition_streams()[0])
        w = StreamWalker(logical, inflate=True, keep_data=True)
        res: Dict[str, Tuple[bytes, Dict]] = {}
        for u in w.units:
            blocks = sorted((b for b in w.blocks if b.unit == u.index),
                            key=lambda x: x.hdr_offset)
            if not blocks:
                continue
            g = getattr(u, "guid", None)
            key = str(uuid.UUID(bytes_le=g)) if g else "unit0"
            start = min(b.hdr_offset for b in blocks)
            if u.index > 0:
                start -= 28
            end = max(b.member_offset + b.member_len + 6 for b in blocks)
            payloads = {}
            for b in blocks:
                payloads.setdefault(b.seq, []).append(b.data)
            res[key] = (logical[start:end],
                        {seq: md5(b"".join(x)) for seq, x in payloads.items()})
        return res

    ua, ub = unit_bytes(path_a), unit_bytes(path_b)
    for k in ub:
        if k in ua:
            ra, mb_a = ua[k]
            rb, mb_b = ub[k]
            out["units"].append({
                "unit": k,
                "raw_identical": ra == rb,
                "raw_lens": [len(ra), len(rb)],
                "payload_md5_per_seq_same": mb_a == mb_b,
                "payload_md5_a": mb_a, "payload_md5_b": mb_b,
            })
        else:
            out["units"].append({"unit": k, "only_in": "b"})
    for k in ua:
        if k not in ub:
            out["units"].append({"unit": k, "only_in": "a"})
    return out


# ---------------------------------------------------------------------------
# the evidence run
# ---------------------------------------------------------------------------

FILES = {
    "rstbasic": "samples/rstbasicsampleproject.rvt",
    "L_v2": "experiments/families/genesis2/L_v2_panel_loaded.rvt",
    "stage_L0": "experiments/frontdoor/demo-250v/_stages/stage_L0_base.rvt",
    "stage_L1": "experiments/frontdoor/demo-250v/_stages/stage_L1_pp1.rvt",
    "stage_L2": "experiments/frontdoor/demo-250v/_stages/stage_L2_pp2.rvt",
    "stage_L3": "experiments/frontdoor/demo-250v/_stages/stage_L3_pp3.rvt",
    "stage_L6": "experiments/frontdoor/demo-250v/_stages/stage_L6_pp6.rvt",
    "prompt_room": "experiments/frontdoor/demo-250v/prompt_room.rvt",
    "walls_only": "experiments/ifc_room/electrical_room_2500a_walls_only.rvt",
    "WF_nofix": "experiments/render/g12/WF_nofix.rvt",
    "WF_fix": "experiments/render/g12/WF_fix.rvt",
    "ZA_deep": "experiments/genesis/subst_k4/residue_a/ZA_deep.rvt",
    "R_inst_box": "experiments/ifc_room/render_probes/R_inst_box.rvt",
    "stage_L8_lp4": "experiments/ifc_room/stage_L8_lp4.rvt",
    "stage_W": "experiments/ifc_room/stage_W_loaded_walls.rvt",
    "V20": "experiments/acceptance/V20_first_created_element.rvt",
    "G_ABPD": "experiments/genesis/subst_k4/compose/G_ABPD.rvt",
}


def run_all() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    surveys: Dict[str, Dict] = {}
    for k, rel in FILES.items():
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            print(f"[skip] {k}: {rel} not on disk")
            continue
        print(f"[survey] {k}")
        try:
            surveys[k] = survey(p)
        except Exception as ex:
            import traceback
            surveys[k] = {"path": rel, "error": repr(ex),
                          "traceback": traceback.format_exc(limit=6)}
            print(f"  ERROR {ex!r}")
    with open(os.path.join(OUT_DIR, "surveys.json"), "w") as fh:
        json.dump(surveys, fh, indent=1, default=str)

    pairs = [
        ("PASS_load_on_sample", "rstbasic", "L_v2"),
        ("FAIL_lineage_load_on_genesis", "stage_L0", "stage_L1"),
        ("PASS_load_on_walls_base", "walls_only", "WF_nofix"),
        ("second_load", "stage_L1", "stage_L2"),
        ("third_load", "stage_L2", "stage_L3"),
        ("instance_commit", "stage_L6", "prompt_room"),
        ("FAIL_load_place_on_ZA", "ZA_deep", "R_inst_box"),
        ("PASS_commit_on_sample", "rstbasic", "V20"),
    ]
    deltas: Dict[str, Dict] = {}
    for name, a, b in pairs:
        if a in surveys and b in surveys and "error" not in surveys[a] and "error" not in surveys[b]:
            print(f"[delta] {name}: {a} -> {b}")
            try:
                deltas[name] = delta(surveys[a], surveys[b])
            except Exception as ex:
                import traceback
                deltas[name] = {"error": repr(ex),
                                "traceback": traceback.format_exc(limit=6)}
    with open(os.path.join(OUT_DIR, "deltas.json"), "w") as fh:
        json.dump(deltas, fh, indent=1, default=str)
    print(f"-> {os.path.join(_relp(OUT_DIR), 'surveys.json')} / deltas.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("survey")
    s1.add_argument("file")
    s1.add_argument("--ids-from", type=int, default=None)
    s2 = sub.add_parser("delta")
    s2.add_argument("base")
    s2.add_argument("derived")
    sub.add_parser("all")
    s4 = sub.add_parser("unitdiff")
    s4.add_argument("a")
    s4.add_argument("b")
    a = ap.parse_args(argv)
    if a.cmd == "survey":
        print(json.dumps(survey(a.file, a.ids_from), indent=1, default=str))
    elif a.cmd == "delta":
        print(json.dumps(delta(survey(a.base), survey(a.derived)), indent=1, default=str))
    elif a.cmd == "unitdiff":
        print(json.dumps(unitdiff(a.a, a.b), indent=1, default=str))
    else:
        run_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
