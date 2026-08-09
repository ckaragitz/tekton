#!/usr/bin/env python
"""terminal_diff -- THE EXHAUSTIVE H12-vs-NATIVE WHOLE-FILE DIFF + THE
RE-ENVELOPE PROBES (terminal-diff stream, post-verdict-#35).

Verdict #35 killed every record-level hypothesis: symbol form, famdoc
content, host elements, registration row content, inline ADocument,
CategoryTracking totality, pairwise combos -- all byte-modeled on native,
all rejected when instanced.  H12 (the all-native-copy probe) is mostly
native bytes, so the complete H12-vs-native difference list is SMALL and
FINITE, and the audit's objection MUST live inside it.  The prime untested
suspect is the layer BELOW decoded records: the container envelope.

This tool:

  enumerate  -> experiments/terminal/terminal_diff.json
        every difference between H12.rvt and the pure native rst sample at
        every layer (CFB header / directory / allocation+slack; per-stream
        bytes; gzip-member envelope; ECC page layer; Partitions framing:
        units, block frames, footer blobs, end record; decoded-record
        delta), each item classified TESTED-DEAD (verdict citation) /
        UNTESTED (ranked) / PARITY (measured equal).  The same diff is run
        H10-vs-native (the PASSING file) as the exoneration cross-check.

  probes     -> experiments/terminal/probes/E*.rvt (+ gates + probes.json)
        one probe per untested envelope axis, each = H12 +/- exactly ONE
        change, plus E_ALL (every envelope axis at once -- the terminal
        split).

  verify     -> re-run the per-probe gates on the emitted bytes.
  stage      -> tools/probe_batch.py staging (control = untouched rst copy).
  kit        -> delegates to tools/revit_kit.py build (kit v2, issue #118):
                the regenerable K0-K3 desktop-Revit check kit under
                experiments/terminal/kit2/ + REVIT-CHECK-KIT.md.  The v1
                pair (H12 + BXhf_f1i1 copies) is retired: both fail only
                for the empty-blob law solved in VERDICTS #36.

MEASURED FACTS THIS TOOL IS BUILT ON (all re-derived at runtime, gated):

* Autodesk's gzip member recipe is EXACTLY reproducible with stock zlib
  (level 3, memLevel 8, raw deflate):
    - Partitions block members:  compress + Z_PARTIAL_FLUSH + Z_FINISH
      (13,534/13,535 corpus members byte-exact; the 1 miss is one
      historical block in dach Partitions/84 with a different flush combo).
    - every other framed stream:  compress + Z_SYNC_FLUSH + the 3-byte
      aligned tail 02 0c 00 (= empty static non-final block + empty static
      final block), 48/48 corpus members byte-exact.
  Our writer's sync+finish ending (...00 00 ff ff 03 00) differs in the
  final 3-7 bytes of EVERY member it emits.
* Every native save unit ends terminator + 0x0f3f footer blob of 64
  HIGH-ENTROPY bytes (distinct per unit, not a plain hash of the unit
  bytes, no GUID embedded) + the magic string.  famgen's
  build_family_save_unit writes blob length 0 -- the new unit is the ONLY
  unit in the corpus with an empty footer blob.
* Our emit pipeline bakes the source file's depage tail junk (final ECC
  block pad+parity read back as data) INTO the logical stream after the
  10-byte end record; the junk grows per re-emit hop (H12: 571 B, H10:
  150 B, native: 0).
* The ECC page layer is measured PARITY: ecc.unframe/frame round-trips
  BOTH files byte-exactly (native pads are zero-filled here too).
* CFB: same 16 directory entries in the same SID order with the same
  storage timestamps; the RB-tree differs (root child, sibling links of
  Root's children, node colors: native mixed red/black vs our all-black),
  and sector allocation / header layout fields differ.

Territory: tools/terminal_diff.py, experiments/terminal/**,
tests/test_terminal_diff.py, docs/inbox/terminal-diff.md.  Probes are
PROOF-ONLY sample-derived dev content, quarantined under experiments/
(never bundled -- the deliverable rule's dev-only lane).  STAGE ONLY: the
orchestrator uploads.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import struct
import sys
import time
import zlib
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import ecc                                    # noqa: E402
from rvt.container import open_rvt                     # noqa: E402
from rvt.partitions import (FOOTER_TAG, StreamWalker,  # noqa: E402
                            parse_stream_header)
from rvt.roundtrip import read_entries                 # noqa: E402
from rvt.cfb_writer import write_cfb                   # noqa: E402
from rvt.stream_encoders import (decode_basic_file_info,      # noqa: E402
                                 decode_elemtable,
                                 decode_increment_table,
                                 encode_basic_file_info,
                                 encode_increment_table,
                                 global_prefix)

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
H12 = os.path.join(ROOT, "experiments", "regcorner", "probes", "H12.rvt")
H10 = os.path.join(ROOT, "experiments", "hostpair", "H10.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "terminal")
PROBE_DIR = os.path.join(OUT_DIR, "probes")
PART = "Partitions/21"
DONOR_UNIT = 36          # the V20 lineage unit (M_Concrete-Square-Column)
END_RECORD_LEN = 10      # u16 0x3a3 + i32 0 + i32 -1

#: framed (CRCIO-paged) streams of the rst lineage
FRAMED = ["Contents", "Formats/Latest", "Global/ContentDocuments",
          "Global/DocumentIncrementTable", "Global/ElemTable",
          "Global/History", "Global/Latest", "Global/PartitionTable", PART]
UNFRAMED = ["BasicFileInfo", "ProjectInformation", "TransmissionData"]

GZIP_HEADER = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x0b"
GLOBAL_TAIL = b"\x02\x0c\x00"     # empty static non-final + empty static final


def log(msg: str) -> None:
    print(f"[terminal_diff] {msg}", flush=True)


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=str)
        f.write("\n")


# ===========================================================================
# Autodesk gzip member recipes (measured; see module docstring)
# ===========================================================================

def adsk_member_partition(payload: bytes, level: int = 3) -> bytes:
    """A Partitions-block gzip member exactly as Autodesk's writer emits it:
    raw deflate level 3 + Z_PARTIAL_FLUSH + Z_FINISH (13,534/13,535 corpus
    members byte-exact)."""
    co = zlib.compressobj(level, zlib.DEFLATED, -15, 8, 0)
    body = co.compress(payload) + co.flush(zlib.Z_PARTIAL_FLUSH) + co.flush(zlib.Z_FINISH)
    return GZIP_HEADER + body + struct.pack(
        "<II", zlib.crc32(payload) & 0xFFFFFFFF, len(payload) & 0xFFFFFFFF)


def adsk_member_global(payload: bytes, level: int = 3) -> bytes:
    """A non-partition gzip member exactly as Autodesk's writer emits it:
    raw deflate level 3 + Z_SYNC_FLUSH + the aligned 3-byte tail 02 0c 00
    (python zlib swallows a flush with nothing pending, so the empty
    static-non-final + static-final pair is appended literally -- bit-decoded
    from the corpus, 48/48 members byte-exact)."""
    co = zlib.compressobj(level, zlib.DEFLATED, -15, 8, 0)
    body = co.compress(payload) + co.flush(zlib.Z_SYNC_FLUSH) + GLOBAL_TAIL
    return GZIP_HEADER + body + struct.pack(
        "<II", zlib.crc32(payload) & 0xFFFFFFFF, len(payload) & 0xFFFFFFFF)


def ours_member(payload: bytes, level: int = 3) -> bytes:
    """Our writer's member (writer.gzip_member level 3 sync_flush=True)."""
    from rvt.writer import gzip_member
    return gzip_member(payload, level=level, sync_flush=True)


def classify_member(stored: bytes, payload: bytes) -> str:
    """Which recipe produced `stored` for `payload`."""
    if stored == adsk_member_partition(payload):
        return "adsk-partition (partial+finish)"
    if stored == adsk_member_global(payload):
        return "adsk-global (sync+02 0c 00)"
    if stored == ours_member(payload):
        return "ours (sync+finish)"
    return "other"


# ===========================================================================
# raw CFB parsing (header / directory / FAT / slack)
# ===========================================================================

FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE


def parse_cfb(path: str) -> Dict[str, Any]:
    data = open(path, "rb").read()
    hdr: Dict[str, Any] = {}
    (hdr["minor"], hdr["major"], hdr["byte_order"], hdr["sector_shift"],
     hdr["mini_shift"]) = struct.unpack_from("<HHHHH", data, 24)
    sect = 1 << hdr["sector_shift"]
    hdr["sector_size"] = sect
    (hdr["num_dir_sectors"], hdr["num_fat_sectors"], hdr["first_dir_sector"],
     hdr["transaction_sig"], hdr["mini_cutoff"], hdr["first_minifat_sector"],
     hdr["num_minifat_sectors"], hdr["first_difat_sector"],
     hdr["num_difat_sectors"]) = struct.unpack_from("<9I", data, 40)
    difat = list(struct.unpack_from("<109I", data, 76))
    hdr["header_difat"] = [s for s in difat if s != FREESECT]
    fat: List[int] = []
    for s in hdr["header_difat"]:
        fat += struct.unpack_from(f"<{sect // 4}I", data, (s + 1) * sect)
    n_sectors = (len(data) - sect) // sect
    hdr["n_sectors"] = n_sectors

    entries: List[Optional[Dict[str, Any]]] = []
    s = hdr["first_dir_sector"]
    dir_sectors = []
    while s not in (ENDOFCHAIN, FREESECT):
        dir_sectors.append(s)
        off = (s + 1) * sect
        for i in range(sect // 128):
            e = data[off + i * 128: off + (i + 1) * 128]
            nlen = struct.unpack_from("<H", e, 64)[0]
            if nlen == 0:
                entries.append(None)
                continue
            entries.append({
                "name": e[:nlen - 2].decode("utf-16-le"),
                "type": e[66], "color": e[67],
                "left": struct.unpack_from("<i", e, 68)[0],
                "right": struct.unpack_from("<i", e, 72)[0],
                "child": struct.unpack_from("<i", e, 76)[0],
                "clsid": e[80:96].hex(),
                "state": struct.unpack_from("<I", e, 96)[0],
                "ctime": struct.unpack_from("<Q", e, 100)[0],
                "mtime": struct.unpack_from("<Q", e, 108)[0],
                "start": struct.unpack_from("<I", e, 116)[0],
                "size": struct.unpack_from("<Q", e, 120)[0],
            })
        s = fat[s]
    hdr["dir_sectors"] = dir_sectors

    # chain + slack per stream entry (regular sectors only)
    root = entries[0]
    mini_cut = hdr["mini_cutoff"]
    slack: List[Dict[str, Any]] = []
    for sid, e in enumerate(entries):
        if e is None or e["type"] not in (2, 5):
            continue
        if e["type"] == 2 and e["size"] < mini_cut and sid != 0:
            continue          # ministream-resident; handled via root chain
        chain = []
        s2 = e["start"]
        while s2 not in (ENDOFCHAIN, FREESECT) and len(chain) <= n_sectors:
            chain.append(s2)
            s2 = fat[s2]
        used = int(e["size"])
        alloc = len(chain) * sect
        tail = b""
        if chain and alloc > used:
            last_off = (chain[-1] + 1) * sect
            inset = used - (len(chain) - 1) * sect
            tail = data[last_off + inset: last_off + sect]
        slack.append({"sid": sid, "name": e["name"], "size": used,
                      "sectors": len(chain), "slack_bytes": len(tail),
                      "slack_nonzero": sum(1 for b in tail if b),
                      "chain_first": chain[0] if chain else None,
                      "chain_is_contiguous": chain == list(
                          range(chain[0], chain[0] + len(chain))) if chain else True})
    free = [i for i, v in enumerate(fat[:n_sectors]) if v == FREESECT]
    fat_tail_nonzero = 0
    for s3 in free:
        off = (s3 + 1) * sect
        fat_tail_nonzero += sum(1 for b in data[off:off + sect] if b)
    return {"header": hdr, "entries": entries, "fat_len": len(fat),
            "free_sectors": free, "free_sector_nonzero_bytes": fat_tail_nonzero,
            "root_ministream": {"start": root["start"], "size": root["size"]},
            "stream_slack": slack, "file_size": len(data)}


def diff_cfb(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    hdr_diff = {k: {"native": a["header"][k], "target": b["header"][k]}
                for k in a["header"]
                if a["header"][k] != b["header"][k] and k != "header_difat"}
    ent_diff = []
    same_order = True
    for sid, (ea, eb) in enumerate(zip(a["entries"], b["entries"])):
        if (ea is None) != (eb is None):
            ent_diff.append({"sid": sid, "field": "presence"})
            same_order = False
            continue
        if ea is None:
            continue
        if ea["name"] != eb["name"]:
            same_order = False
        for f in ("name", "type", "color", "left", "right", "child",
                  "start", "size", "ctime", "mtime", "state", "clsid"):
            if ea[f] != eb[f]:
                ent_diff.append({"sid": sid, "name": ea["name"], "field": f,
                                 "native": ea[f], "target": eb[f]})
    return {"header_field_diffs": hdr_diff,
            "sid_order_identical": same_order,
            "entry_field_diffs": ent_diff,
            "tree_shape_differs": any(d["field"] in ("left", "right", "child")
                                      for d in ent_diff),
            "colors_differ": any(d["field"] == "color" for d in ent_diff)}


# ===========================================================================
# per-stream + partition envelope measurement
# ===========================================================================

def stream_report(native: str, target: str) -> Dict[str, Any]:
    A, B = open_rvt(native), open_rvt(target)
    try:
        names_a = {s.name for s in A.streams()}
        names_b = {s.name for s in B.streams()}
        out: Dict[str, Any] = {
            "only_in_native": sorted(names_a - names_b),
            "only_in_target": sorted(names_b - names_a),
            "streams": {},
        }
        for name in sorted(names_a & names_b):
            ra, rb = A.raw(name), B.raw(name)
            rec: Dict[str, Any] = {
                "raw_size": {"native": len(ra), "target": len(rb)},
                "byte_equal": ra == rb,
            }
            if name in FRAMED:
                la, lb = ecc.unframe_stream(ra), ecc.unframe_stream(rb)
                rec["ecc"] = {
                    "native_roundtrip_exact": ecc.frame_stream(la) == ra,
                    "target_roundtrip_exact": ecc.frame_stream(lb) == rb,
                    "data_len": {"native": len(la), "target": len(lb)},
                }
                if name != PART:
                    ma, mb = A.members(name), B.members(name)
                    rec["members"] = {
                        "count": {"native": len(ma), "target": len(mb)},
                        "header_10B": {
                            "native": sorted({A.logical(name)[m.offset:m.offset + 10].hex() for m in ma}),
                            "target": sorted({B.logical(name)[m.offset:m.offset + 10].hex() for m in mb}),
                        },
                        "recipe": {
                            "native": [classify_member(
                                la[m.offset:m.offset + m.consumed],
                                A.inflate(name, m.index)) for m in ma],
                            "target": [classify_member(
                                lb[m.offset:m.offset + m.consumed],
                                B.inflate(name, m.index)) for m in mb],
                        },
                    }
                    # junk after the last member inside the framed DATA
                    if ma and mb:
                        rec["data_junk_after_members"] = {
                            "native": len(la) - (ma[-1].offset + ma[-1].consumed),
                            "target": len(lb) - (mb[-1].offset + mb[-1].consumed),
                        }
            if not rec["byte_equal"]:
                n = min(len(ra), len(rb))
                rec["first_raw_divergence"] = next(
                    (i for i in range(n) if ra[i] != rb[i]), n)
            out["streams"][name] = rec
        return out
    finally:
        A.close()
        B.close()


def partition_envelope(native: str, target: str) -> Dict[str, Any]:
    A, B = open_rvt(native), open_rvt(target)
    try:
        la = ecc.unframe_stream(A.raw(PART))
        lb = ecc.unframe_stream(B.raw(PART))
    finally:
        A.close()
        B.close()
    wa = StreamWalker(la, inflate=True, keep_data=True)
    wb = StreamWalker(lb, inflate=True, keep_data=True)
    ha, hb = parse_stream_header(la), parse_stream_header(lb)
    content_diff_blocks = []
    ending_only_blocks = 0
    byte_equal_blocks = 0
    for i in range(len(wa.blocks)):
        ba, bb = wa.blocks[i], wb.blocks[i]
        xa = la[ba.hdr_offset:ba.member_offset + ba.member_len + 6]
        xb = lb[bb.hdr_offset:bb.member_offset + bb.member_len + 6]
        if xa == xb:
            byte_equal_blocks += 1
        elif ba.data == bb.data:
            ending_only_blocks += 1
        else:
            content_diff_blocks.append({
                "aligned_index": i, "unit": ba.unit, "seq": ba.seq,
                "records": {"native": ba.n_records, "target": bb.n_records}})
    new_blocks = [{"index": b.index, "unit": b.unit, "seq": b.seq,
                   "flags": b.flags, "records": b.n_records,
                   "recipe": classify_member(
                       lb[b.member_offset:b.member_offset + b.member_len], b.data)}
                  for b in wb.blocks[len(wa.blocks):]]
    units_aligned = min(len(wa.units), len(wb.units))
    return {
        "prefix_u64": {"native": la[:8].hex(), "target": lb[:8].hex()},
        "header": {"native": vars(ha), "target": vars(hb)},
        "units": {"native": len(wa.units), "target": len(wb.units)},
        "blocks": {"native": len(wa.blocks), "target": len(wb.blocks)},
        "aligned_blocks": {"byte_equal": byte_equal_blocks,
                           "compression_ending_only": ending_only_blocks,
                           "content_diff": content_diff_blocks},
        "new_unit": None if len(wb.units) == len(wa.units) else {
            "index": wb.units[-1].index,
            "counter": wb.units[-1].counter,
            "guid": wb.units[-1].guid.hex() if wb.units[-1].guid else None,
            "blocks": new_blocks,
            "footer_blob_len": len(wb.units[-1].footer_blob),
            "footer_text_equal_native_form":
                wb.units[-1].footer_text == wa.units[0].footer_text,
        },
        "aligned_separators_equal": sum(
            1 for ua, ub in zip(wa.units, wb.units)
            if (ua.guid, ua.counter) == (ub.guid, ub.counter)) == units_aligned,
        "aligned_footer_blobs_equal": sum(
            1 for ua, ub in zip(wa.units, wb.units)
            if ua.footer_blob == ub.footer_blob) == units_aligned,
        "native_footer_blob_lens": sorted({len(u.footer_blob) for u in wa.units}),
        "end_record": {
            "native_total": len(wa.end_record),
            "target_total": len(wb.end_record),
            "true_len": END_RECORD_LEN,
            "target_junk_after_end": len(wb.end_record) - END_RECORD_LEN,
            "native_junk_after_end": len(wa.end_record) - END_RECORD_LEN,
            "target_starts_with_native": wb.end_record[:len(wa.end_record)] == wa.end_record,
        },
    }


# ===========================================================================
# decoded-record delta (layer d re-verification)
# ===========================================================================

def _leaf_diff(a: Any, b: Any, path: str, out: List[Tuple[str, Any, Any]],
               limit: int = 400) -> None:
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _leaf_diff(a.get(k), b.get(k), f"{path}.{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((f"{path}#len", len(a), len(b)))
            return
        for j, (x, y) in enumerate(zip(a, b)):
            _leaf_diff(x, y, f"{path}[{j}]", out, limit)
    elif a != b:
        out.append((path, a, b))


def record_delta(native: str, target: str) -> Dict[str, Any]:
    from rvt.adocument import open_document_object
    from rvt.famgen.factory import parse_content_documents

    out: Dict[str, Any] = {}
    A, B = open_rvt(native), open_rvt(target)
    try:
        # BasicFileInfo fields
        bfa = decode_basic_file_info(A.raw("BasicFileInfo"))
        bfb = decode_basic_file_info(B.raw("BasicFileInfo"))
        leaves: List[Tuple[str, Any, Any]] = []
        _leaf_diff({k: v for k, v in bfa.items() if k != "mirror_text"},
                   {k: v for k, v in bfb.items() if k != "mirror_text"},
                   "bfi", leaves)
        out["basic_file_info"] = [
            {"path": p, "native": x, "target": y} for p, x, y in leaves]

        # DocumentIncrementTable rows
        da = decode_increment_table(A.inflate("Global/DocumentIncrementTable", 0))
        db = decode_increment_table(B.inflate("Global/DocumentIncrementTable", 0))
        leaves = []
        _leaf_diff(da, db, "dit", leaves)
        out["increment_table"] = {
            "row_count": {"native": len(da.get("records", [])),
                          "target": len(db.get("records", []))},
            "leaf_diffs": len(leaves),
            "all_diffs_are_username_blanking": bool(leaves) and all(
                p.endswith(".username") and y == "" for p, x, y in leaves),
            "sample": [{"path": p, "native": x, "target": y}
                       for p, x, y in leaves[:4]],
        }

        # ElemTable adds
        ea = decode_elemtable(A.inflate("Global/ElemTable", 0))
        eb = decode_elemtable(B.inflate("Global/ElemTable", 0))
        ids_a = {r[4] for r in ea["records"]}      # 7-tuple, [4] = id
        ids_b = {r[4] for r in eb["records"]}
        out["elem_table"] = {
            "rows": {"native": len(ids_a), "target": len(ids_b)},
            "added_ids": sorted(ids_b - ids_a),
            "removed_ids": sorted(ids_a - ids_b),
        }

        # ContentDocuments entries by separator GUID
        pa = A.inflate("Global/ContentDocuments", 0)
        pb = B.inflate("Global/ContentDocuments", 0)
        ents_a, end_a = parse_content_documents(pa)
        ents_b, end_b = parse_content_documents(pb)
        ga = {g: blob for g, blob in ents_a}
        gb = {g: blob for g, blob in ents_b}
        changed = [g for g in ga if g in gb and ga[g] != gb[g]]
        out["content_documents"] = {
            "entries": {"native": len(ents_a), "target": len(ents_b)},
            "added_guids": sorted(set(gb) - set(ga)),
            "removed_guids": sorted(set(ga) - set(gb)),
            "changed_common_entries": changed,
            "end_record_equal": end_a == end_b,
        }

        # Global/Latest ADocument leaf diff
        adoc_a = open_document_object(native)
        adoc_b = open_document_object(target)
        leaves = []
        _leaf_diff(adoc_a.value, adoc_b.value, "adoc", leaves)
        buckets: Dict[str, int] = {}
        for p, _x, _y in leaves:
            key = ".".join(p.split(".")[1:3])
            buckets[key] = buckets.get(key, 0) + 1
        out["global_latest"] = {
            "leaf_diffs": len(leaves),
            "buckets": buckets,
            "sample": [{"path": p, "native": str(x)[:120], "target": str(y)[:120]}
                       for p, x, y in leaves[:12]],
        }

        # keyed sub-diffs of the three container-length changes, so the
        # "known adds and NOTHING else" claim is row-exact, not just
        # container-count-exact
        def _ct_key(row: Dict[str, Any]) -> str:
            return json.dumps(row.get("m_ContentKey"), default=str, sort_keys=True)

        ct_a = adoc_a.value["m_oContentTable"]["value"]["m_ContentRecSet"]
        ct_b = adoc_b.value["m_oContentTable"]["value"]["m_ContentRecSet"]
        ka = {_ct_key(r): r for r in ct_a}
        kb = {_ct_key(r): r for r in ct_b}
        ct_changed = []
        for k in ka:
            if k in kb and ka[k] != kb[k]:
                ct_changed.append(k[:60])
        fm_a = adoc_a.value["m_pAppInfoManager"]["value"]["m_appInfoArr"][0]["value"]["m_arrLoadedFamilyInfo"]
        fm_b = adoc_b.value["m_pAppInfoManager"]["value"]["m_appInfoArr"][0]["value"]["m_arrLoadedFamilyInfo"]
        fa = {e["m_surrogateId"]: e for e in fm_a}
        fb = {e["m_surrogateId"]: e for e in fm_b}
        etd_a = adoc_a.value["m_pAppInfoManager"]["value"]["m_appInfoArr"][32]["value"]["m_symbols"][44]
        etd_b = adoc_b.value["m_pAppInfoManager"]["value"]["m_appInfoArr"][32]["value"]["m_symbols"][44]
        out["global_latest"]["keyed"] = {
            "contenttable": {
                "rows": {"native": len(ct_a), "target": len(ct_b)},
                "added_keys": len([k for k in kb if k not in ka]),
                "removed_keys": len([k for k in ka if k not in kb]),
                "changed_common_rows": ct_changed,
            },
            "familymgr": {
                "entries": {"native": len(fm_a), "target": len(fm_b)},
                "added_surrogates": sorted(set(fb) - set(fa)),
                "removed_surrogates": sorted(set(fa) - set(fb)),
                "changed_common_entries": sorted(
                    k for k in fa if k in fb and fa[k] != fb[k]),
            },
            "etd_symbols_row44": {
                "category": etd_a.get("m_categoryId"),
                "added_ids": sorted(set(etd_b["m_elemIdSet"]) - set(etd_a["m_elemIdSet"])),
                "removed_ids": sorted(set(etd_a["m_elemIdSet"]) - set(etd_b["m_elemIdSet"])),
            },
        }
        return out
    finally:
        A.close()
        B.close()


# ===========================================================================
# the classified axis table
# ===========================================================================

def build_axes(sr: Dict[str, Any], pe: Dict[str, Any], pe10: Dict[str, Any],
               cd: Dict[str, Any], rd: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The COMPLETE finite difference list, classified.  Every measured
    difference between H12 and native lands in exactly one axis below."""
    part = sr["streams"][PART]
    new_unit = pe["new_unit"] or {}
    axes: List[Dict[str, Any]] = []

    def axis(id_: str, layer: str, desc: str, cls: str, **kw: Any) -> None:
        axes.append({"id": id_, "layer": layer, "difference": desc,
                     "classification": cls, **kw})

    # ---- PARITY (measured equal -- no probe possible or needed) ----------
    axis("P1", "gzip-envelope",
         "10-byte gzip member headers (mtime 0, XFL 0, OS 0x0b): identical "
         "constant on every member of both files", "PARITY",
         evidence="stream_report members.header_10B")
    axis("P2", "ecc",
         "ECC page layer: ecc.unframe/frame round-trips BOTH files "
         "byte-exactly (same algorithm, zero-filled pads in both)", "PARITY",
         evidence="stream_report ecc.*_roundtrip_exact all true")
    axis("P3", "stream-inventory",
         "same 12 streams, no stream only in one file", "PARITY",
         evidence=f"only_in_native={sr['only_in_native']} "
                  f"only_in_target={sr['only_in_target']}")
    axis("P4", "partition-frame",
         "Partitions header form (v9/0x3a3), u64 prefix, block flags 4, the "
         "new unit's block segmentation == the donor's (418/146+272/418), "
         "separators + footer text + terminator forms, 53 aligned unit "
         "separators and footer blobs byte-equal", "PARITY",
         evidence="partition_envelope aligned_* fields")
    axis("P5", "cfb",
         "CFB v4 header constants (4096 sectors, cutoff, 0 DIFAT), 16 "
         "directory entries in the same SID order, storage/root timestamps "
         "copied, clsids/state zero", "PARITY",
         evidence="cfb_diff sid_order_identical")
    axis("P6", "stream-bytes",
         "byte-equal streams: Contents, Formats/Latest, Global/History, "
         "Global/PartitionTable, ProjectInformation, TransmissionData",
         "PARITY", evidence="stream_report byte_equal")

    # ---- TESTED-DEAD (record layer -- the verdicts) ----------------------
    axis("D1", "records",
         "registration row content (ContentTable/FamilyMgr rows famload "
         "authors; the Global/Latest decoded delta)", "TESTED-DEAD",
         verdict="H11 + H11x12 FAIL (genesis-audit VERDICTS #35, b40); "
                 "row forensics exonerated row content (#34 note)")
    axis("D2", "records",
         "inline ContentDocuments ADocument population (0/239 vs 131/239)",
         "TESTED-DEAD", verdict="H12 FAIL (#35); H6 FAIL (b37, #33)")
    axis("D3", "records",
         "famdoc content of the new unit (verbatim Autodesk famdoc)",
         "TESTED-DEAD", verdict="H7 FAIL (#33); byte-copies in H9 (#34)")
    axis("D4", "records",
         "host Family/FamilySymbol constellation (22-element native "
         "byte-copies)", "TESTED-DEAD", verdict="H9 FAIL + H10 PASS (#34)")
    axis("D5", "records",
         "CategoryTracking index totality (appinfo slot 28)", "TESTED-DEAD",
         verdict="H13 FAIL (#35, b41-as-uploaded-with-b40)")
    axis("D6", "records",
         "symbol geometry form (no-solid / corpus-lawful hostfix forms)",
         "TESTED-DEAD", verdict="BXns FAIL (#32, b34); BXhf FAIL (#34, b39)")
    axis("D7", "records",
         "the instance record itself (V20-certified template shape)",
         "TESTED-DEAD",
         verdict="V20 PASS on a native unit (#31-era); the instance is the "
                 "TRIGGER of the audit walk, not the defect (invariant table)")
    axis("D8", "records",
         "ElemTable adds + watermark mechanics "
         f"(added ids {rd['elem_table']['rows']['target'] - rd['elem_table']['rows']['native']})",
         "TESTED-DEAD",
         verdict="H10 +22 rows PASS uninstanced (#34); V20 +1 row PASS "
                 "instanced-on-native; mechanics exonerated both ways")

    # ---- UNTESTED (the envelope -- ranked, each with a probe) ------------
    h10_env = {"member_recipe_ours_everywhere": True,
               "junk_after_end": pe10["end_record"]["target_junk_after_end"],
               "new_unit_footer_blob_len": (pe10["new_unit"] or {}).get("footer_blob_len")}
    axis("U1", "partition-unit-envelope",
         "the new unit's 0x0f3f footer blob is EMPTY (0 B); all 53 native "
         "units carry 64 high-entropy bytes, distinct per unit (not a plain "
         "hash of unit bytes/GUID -- opaque). famgen build_family_save_unit "
         "writes blen=0", "UNTESTED", rank=1,
         probe="E1 (donor unit 36's blob copied verbatim) + E1b (random 64 B) "
               "-- the pair splits content-verified vs presence-checked",
         h10_shares=h10_env["new_unit_footer_blob_len"] == 0,
         exoneration="H10 PASSES with the same empty blob UNINSTANCED only; "
                     "V20's units are all native (blob present)",
         why_ranked_first="the ONLY remaining opaque unmodeled bytes in the "
                          "file; unit-scoped (exactly the new unit lacks it); "
                          "distinct per unit = plausibly content/identity-"
                          "derived, exactly what an instance-walk cross-check "
                          "could consult")
    axis("U2", "partition-stream-tail",
         f"{pe['end_record']['target_junk_after_end']} bytes of high-entropy "
         "junk baked as DATA after the 10-byte end record (accumulated "
         "depage tail junk re-framed as data by every emit hop; native: 0, "
         f"H10: {h10_env['junk_after_end']})", "UNTESTED", rank=2,
         probe="E6 (truncate the logical at the true end record)",
         h10_shares=True,
         exoneration="H10 (150 B) + V15/V20 lineage pass with nonzero junk "
                     "uninstanced / instanced-on-native",
         why_ranked_second="physically adjacent to the new unit (the junk "
                           "sits right after the end record that FOLLOWS our "
                           "unit); grows per hop so H12 carries 3.8x H10's")
    axis("U3", "gzip-envelope",
         "EVERY gzip member our pipeline wrote ends sync+finish "
         "(...00 00 ff ff 03 00) where Autodesk ends partial+finish "
         "(partitions) / sync+02 0c 00 (other streams): all 418 partition "
         "blocks + 4 rewritten global members deviate; 411 of 414 aligned "
         "blocks differ ONLY by this", "UNTESTED", rank=3,
         probe="E3 (re-emit every member with the exact Autodesk recipe; "
               "untouched blocks become byte-identical to native)",
         h10_shares=True,
         exoneration="V15 (whole file our gzip) PASS; H10 PASS; V20's "
                     "rewritten unit-0 blocks PASS instanced-on-native")
    axis("U4", "records-out-of-registry",
         "BasicFileInfo identity strings: author 'Autodesk Revit'->"
         "'rvt-writer', client_app_name 'RevitApplication'->'rvt-writer', "
         "last_save_path native path->'H12.rvt'", "UNTESTED", rank=4,
         probe="E4 (restore the native strings; BFI becomes byte-equal to "
               "native)", h10_shares=True,
         exoneration="H10 passes with the same rebrand uninstanced; V20's "
                     "BFI is untouched native",
         note="OUTSIDE the four-registry model -- never covered by #34/#35; "
              "'unaudited record surface' is the honest classification")
    axis("U5", "records-out-of-registry",
         "DocumentIncrementTable: every one of the 44 rows' username "
         "scrubbed to '' (zhangg/xuew/loboarch/hansonje/... -> '')",
         "UNTESTED", rank=5,
         probe="E5 (restore the native usernames)", h10_shares=True,
         exoneration="H10 passes scrubbed uninstanced; V20's DIT untouched",
         note="also outside the four-registry model")
    axis("U6", "cfb",
         "CFB directory red-black tree: Root's child tree differs (root "
         "child Formats vs Partitions, sibling links), node colors (native "
         "mixed red/black incl. red Root Entry vs our all-black); Global's "
         "subtree links happen to match", "UNTESTED", rank=6,
         probe="E2 (patch the directory sector to native tree links+colors)",
         h10_shares=True,
         exoneration="V15/V20/H10 all carry our tree shape and pass")
    axis("U7", "cfb",
         "sector allocation layout: start sectors, chain order, "
         "first_dir/minifat header fields, ministream packing differ "
         "(content-equal, layout-different)", "UNTESTED", rank=7,
         probe="DEFERRED (no probe this round): Revit reads via the "
               "layout-agnostic Structured Storage API; V15/V20/H10 pass "
               "with our layout; revisit only if E2 moves the needle",
         h10_shares=True)
    axis("U8", "cfb",
         "slack content: our zero-fill vs native heap-garbage slack "
         "(measured HERE: native final-sector slack is nonzero for "
         "Partitions/21 (1,007 B), ElemTable (1,288), Global/Latest (1,086), "
         "Formats/Latest (1,367); every target slack byte is zero)",
         "UNTESTED", rank=8,
         probe="DEFERRED (no probe this round): slack is invisible to the "
               "Structured Storage API; V15/V20/H10 pass zero-filled",
         h10_shares=True)
    axis("N1", "save-story",
         "NOT A DIFF (recorded for completeness): H12 records NO new save "
         "(BFI increments 22 == native, History/Contents byte-equal, no new "
         "DIT row) -- a unit appears with no save episode recording it. "
         "Identical to native on every compared byte, so not in the diff "
         "list; the semantic oddity is noted for the desktop-Revit kit",
         "NOT-A-DIFF")
    return axes


# ===========================================================================
# enumerate
# ===========================================================================

def enumerate_diff() -> Dict[str, Any]:
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    log("CFB layer ...")
    ca, cb, ch10 = parse_cfb(RST), parse_cfb(H12), parse_cfb(H10)
    cd = diff_cfb(ca, cb)
    cd10 = diff_cfb(ca, ch10)
    log("stream layer ...")
    sr = stream_report(RST, H12)
    sr10 = stream_report(RST, H10)
    log("partition envelope ...")
    pe = partition_envelope(RST, H12)
    pe10 = partition_envelope(RST, H10)
    log("decoded-record delta (Global/Latest leaf diff takes ~a minute) ...")
    rd = record_delta(RST, H12)
    axes = build_axes(sr, pe, pe10, cd, rd)
    out = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": "tools/terminal_diff.py enumerate",
        "charter": "terminal-diff: the exhaustive H12-vs-native whole-file "
                   "diff, every layer, every item classified",
        "pair": {"native": relp(RST), "native_md5": md5_of(RST),
                 "target": relp(H12), "target_md5": md5_of(H12)},
        "crosscheck_pair": {"target": relp(H10), "target_md5": md5_of(H10),
                            "meaning": "H10 PASSES with our envelope "
                            "uninstanced; shared envelope axes are "
                            "exonerated-uninstanced-ONLY (ranked, not "
                            "excluded -- an envelope feature may be walked "
                            "only when instanced)"},
        "cfb": {"native": ca["header"], "target": cb["header"],
                "diff": cd, "crosscheck_h10_diff": cd10,
                "native_stream_slack": ca["stream_slack"],
                "target_stream_slack": cb["stream_slack"],
                "free_sectors": {"native": ca["free_sectors"],
                                 "target": cb["free_sectors"]}},
        "streams": sr,
        "partitions": pe,
        "partitions_crosscheck_h10": pe10,
        "record_delta": rd,
        "axes": axes,
        "summary": {
            "untested_axes": [a["id"] for a in axes
                              if a["classification"] == "UNTESTED"],
            "tested_dead_axes": [a["id"] for a in axes
                                 if a["classification"] == "TESTED-DEAD"],
            "parity_axes": [a["id"] for a in axes
                            if a["classification"] == "PARITY"],
            "elapsed_s": round(time.time() - t0, 1),
        },
    }
    jdump(os.path.join(OUT_DIR, "terminal_diff.json"), out)
    log(f"terminal_diff.json written ({out['summary']})")
    return out


# ===========================================================================
# probe construction (byte surgery on H12)
# ===========================================================================

def _partition_pieces(logical: bytes) -> Dict[str, Any]:
    """Decompose an unframed Partitions logical stream into rebuildable
    pieces, asserting the walk is clean."""
    w = StreamWalker(logical, inflate=True, keep_data=True)
    if w.errors:
        raise RuntimeError(f"walker errors: {w.errors[:3]}")
    return {"walker": w, "logical": logical}


def _rebuild_partition_logical(pieces: Dict[str, Any], *,
                               member_fn=None,
                               footer_blob_override: Optional[Dict[int, bytes]] = None,
                               truncate_junk: bool = False) -> bytes:
    """Reassemble the logical stream copying every framing byte region from
    the source, optionally (a) re-emitting every block member with
    `member_fn(payload)` (block header B + trailer mirror updated), (b)
    replacing unit footer blobs, (c) truncating after the 10-byte end
    record."""
    w: StreamWalker = pieces["walker"]
    raw: bytes = pieces["logical"]
    out = bytearray()
    out += raw[:w.header.size]                       # 18-byte stream header
    blob_over = footer_blob_override or {}
    for u in w.units:
        if u.index > 0:
            # 28-byte separator sits immediately before the unit's first block
            first = w.blocks[u.first_block]
            out += raw[first.hdr_offset - 28:first.hdr_offset]
        for b in w.blocks[u.first_block:u.first_block + u.n_blocks]:
            hdr = bytearray(raw[b.hdr_offset:b.hdr_offset + 26])
            member = raw[b.member_offset:b.member_offset + b.member_len]
            if member_fn is not None:
                member = member_fn(b.data)
                assert zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(member) == b.data
                struct.pack_into("<I", hdr, 10, 8 + len(member))   # B field
            out += hdr + member
            out += struct.pack("<HI", 0x0F21, struct.unpack_from("<I", hdr, 10)[0])
        # terminator + footer
        out += raw[u.footer_offset:u.footer_offset + 18]
        blob = blob_over.get(u.index, u.footer_blob)
        out += struct.pack("<HI", FOOTER_TAG, len(blob)) + blob
        txt = u.footer_text.encode("utf-16-le")
        out += struct.pack("<I", len(u.footer_text)) + txt
    end = w.end_record
    out += end[:END_RECORD_LEN] if truncate_junk else end
    return bytes(out)


def _replace_streams(src_path: str, out_path: str,
                     new_raw: Dict[str, bytes]) -> None:
    """Rebuild the container from src replacing chosen streams' raw bytes."""
    import dataclasses
    entries = read_entries(src_path)
    out_entries = []
    for e in entries:
        if e.entry_type == "stream" and e.path in new_raw:
            out_entries.append(dataclasses.replace(e, data=new_raw[e.path]))
        else:
            out_entries.append(e)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_cfb(out_path, out_entries)


def _patch_directory_tree(path: str, native_cfb: Dict[str, Any]) -> None:
    """Overwrite color + left/right/child of every directory entry with the
    native file's values (same names at the same SIDs -- asserted)."""
    with open(path, "r+b") as f:
        data = bytearray(f.read())
        hdr = parse_cfb(path)["header"]
        sect = hdr["sector_size"]
        ours = parse_cfb(path)["entries"]
        for sid, ne in enumerate(native_cfb["entries"]):
            oe = ours[sid] if sid < len(ours) else None
            if ne is None or oe is None:
                if (ne is None) != (oe is None):
                    raise RuntimeError(f"SID {sid} presence mismatch")
                continue
            if ne["name"] != oe["name"]:
                raise RuntimeError(f"SID {sid} name mismatch {ne['name']!r} vs {oe['name']!r}")
            off = (hdr["dir_sectors"][sid // (sect // 128)] + 1) * sect \
                + (sid % (sect // 128)) * 128
            data[off + 67] = ne["color"]
            struct.pack_into("<iii", data, off + 68,
                             ne["left"], ne["right"], ne["child"])
        f.seek(0)
        f.write(data)


def _bfi_native_strings(h12_raw: bytes, native_raw: bytes) -> bytes:
    model = decode_basic_file_info(h12_raw)
    nat = decode_basic_file_info(native_raw)
    for k in ("author", "client_app_name", "last_save_path"):
        model[k] = nat[k]
    return encode_basic_file_info(model, regenerate_mirror=True)


def _dit_native_usernames(h12_payload: bytes, native_payload: bytes) -> bytes:
    model = decode_increment_table(h12_payload)
    nat = decode_increment_table(native_payload)
    for key in ("records", "records2"):     # the stream serializes TWO copies
        if len(model.get(key, [])) != len(nat.get(key, [])):
            raise RuntimeError(f"DIT {key} row counts differ; refusing")
        for r, rn in zip(model.get(key, []), nat.get(key, [])):
            r["username"] = rn["username"]
    return encode_increment_table(model)


def build_probes() -> Dict[str, Any]:
    os.makedirs(PROBE_DIR, exist_ok=True)
    A = open_rvt(RST)
    B = open_rvt(H12)
    nat_cfb = parse_cfb(RST)
    try:
        nat_part_logical = ecc.unframe_stream(A.raw(PART))
        h12_part_logical = ecc.unframe_stream(B.raw(PART))
        nat_w = StreamWalker(nat_part_logical, inflate=True, keep_data=True)
        donor_blob = nat_w.units[DONOR_UNIT].footer_blob
        assert len(donor_blob) == 64
        pieces = _partition_pieces(h12_part_logical)
        our_unit_idx = pieces["walker"].units[-1].index
        # rebuild-identity gate: reassembly with no edits must be byte-exact
        if _rebuild_partition_logical(pieces) != h12_part_logical:
            raise RuntimeError("rebuild-identity gate REFUSED: no-edit "
                               "reassembly is not byte-exact")
        log("rebuild-identity gate OK (no-edit reassembly byte-exact)")
        rng = random.Random(0x7E12)
        random_blob = bytes(rng.randrange(256) for _ in range(64))

        nat_bfi = A.raw("BasicFileInfo")
        h12_bfi = B.raw("BasicFileInfo")
        nat_dit = A.inflate("Global/DocumentIncrementTable", 0)
        h12_dit = B.inflate("Global/DocumentIncrementTable", 0)

        # Global streams H12 rewrote (candidates for E3's member re-ending)
        rewritten_globals = [n for n in ("Global/ContentDocuments",
                                         "Global/DocumentIncrementTable",
                                         "Global/ElemTable", "Global/Latest")
                             if A.raw(n) != B.raw(n)]

        def part_raw(**kw: Any) -> bytes:
            return ecc.frame_stream(_rebuild_partition_logical(pieces, **kw))

        def global_raw(name: str, member: bytes) -> bytes:
            return ecc.frame_stream(global_prefix(name) + member)

        built: Dict[str, Dict[str, Any]] = {}

        def emit(name: str, new_raw: Dict[str, bytes], axis: str,
                 expected: str, dir_patch: bool = False) -> None:
            outp = os.path.join(PROBE_DIR, f"{name}.rvt")
            _replace_streams(H12, outp, new_raw)
            if dir_patch:
                _patch_directory_tree(outp, nat_cfb)
            built[name] = {"file": relp(outp), "axis": axis,
                           "expected": expected,
                           "streams_replaced": sorted(new_raw),
                           "dir_patched": dir_patch, "md5": md5_of(outp)}
            log(f"built {name}.rvt  ({axis})")

        # E1: donor footer blob
        emit("E1", {PART: part_raw(footer_blob_override={our_unit_idx: donor_blob})},
             "U1: new unit's 0x0f3f footer blob 0 B -> the donor unit's own "
             "64 B blob, verbatim",
             "PASS convicts the footer-blob axis (presence or "
             "donor-content-tolerant check)")
        # E1b: random footer blob
        emit("E1b", {PART: part_raw(footer_blob_override={our_unit_idx: random_blob})},
             "U1-split: same edit with 64 RANDOM bytes (seeded 0x7E12)",
             "E1 PASS + E1b FAIL => blob content is verified against "
             "something; E1 PASS + E1b PASS => presence/shape only")
        # E6: truncate baked junk after the end record
        emit("E6", {PART: part_raw(truncate_junk=True)},
             "U2: the 571 junk bytes after the 10-byte end record removed "
             "(logical ends exactly like native)",
             "PASS convicts the baked stream-tail junk")
        # E3: Autodesk member recipe everywhere our pipeline wrote members
        e3 = {PART: part_raw(member_fn=adsk_member_partition, truncate_junk=False)}
        for n in rewritten_globals:
            e3[n] = global_raw(n, adsk_member_global(B.inflate(n, 0)))
        emit("E3", e3,
             "U3: every member re-emitted with the exact Autodesk recipe "
             "(partitions partial+finish; globals sync+02 0c 00); the 411 "
             "content-identical blocks become byte-identical to native",
             "PASS convicts the member-ending shape")
        # E4: native BFI identity strings
        emit("E4", {"BasicFileInfo": _bfi_native_strings(h12_bfi, nat_bfi)},
             "U4: BasicFileInfo author/client_app_name/last_save_path "
             "restored to the native strings (stream becomes byte-equal "
             "to native)",
             "PASS convicts the BFI identity rebrand")
        # E5: native DIT usernames
        emit("E5", {"Global/DocumentIncrementTable":
                    global_raw("Global/DocumentIncrementTable",
                               ours_member(_dit_native_usernames(h12_dit, nat_dit)))},
             "U5: the 44 DocumentIncrementTable usernames restored from "
             "native (decoded table becomes field-equal to native)",
             "PASS convicts the username scrub")
        # E2: native CFB directory tree (no stream bytes change)
        emit("E2", {}, "U6: directory sector patched to the native "
             "red-black tree (colors + left/right/child per SID)",
             "PASS convicts the CFB directory tree shape", dir_patch=True)
        # E_ALL: everything at once (donor blob + truncate + adsk members +
        # native BFI + native DIT + native dir tree)
        eall = {PART: ecc.frame_stream(_rebuild_partition_logical(
                    pieces, member_fn=adsk_member_partition,
                    footer_blob_override={our_unit_idx: donor_blob},
                    truncate_junk=True)),
                "BasicFileInfo": _bfi_native_strings(h12_bfi, nat_bfi),
                "Global/DocumentIncrementTable":
                    global_raw("Global/DocumentIncrementTable",
                               adsk_member_global(_dit_native_usernames(h12_dit, nat_dit)))}
        for n in ("Global/ContentDocuments", "Global/ElemTable", "Global/Latest"):
            if n in rewritten_globals:
                eall[n] = global_raw(n, adsk_member_global(B.inflate(n, 0)))
        emit("E_ALL", eall,
             "ALL envelope axes at once: donor blob + junk truncated + "
             "Autodesk member recipe + native BFI strings + native DIT "
             "usernames + native directory tree -- the maximally-native H12",
             "the terminal split: PASS => the objection lives in the "
             "envelope/out-of-registry layer (singles name it; if all "
             "singles FAIL, a conjunction -- bisect next); FAIL => the "
             "in-file envelope is exonerated wholesale EXCEPT the footer-"
             "blob CONTENT function (E_ALL carries the donor's blob, which "
             "would be wrong if the blob is a content digest)",
             dir_patch=True)
        return built
    finally:
        A.close()
        B.close()


# ===========================================================================
# gates
# ===========================================================================

STANDING_WARNING = "records failed schema decode"


def gate_probe_file(name: str, path: str) -> Dict[str, Any]:
    """The per-probe machine gates: validator, walkability, single-axis
    byte attribution, decoded-record identity where the axis promises it."""
    from rvt.validate import validate_file
    rep: Dict[str, Any] = {"name": name, "file": relp(path), "md5": md5_of(path)}

    v = validate_file(path)
    rep["validator"] = {
        "verdict": "VALID" if not v.errors else "INVALID",
        "n_errors": len(v.errors),
        "n_warnings": len(v.warnings),
        "first_errors": [str(e)[:160] for e in v.errors[:3]],
    }

    A, B, P = open_rvt(RST), open_rvt(H12), open_rvt(path)
    try:
        names12 = {s.name for s in B.streams()}
        namesP = {s.name for s in P.streams()}
        rep["stream_set_equal_h12"] = names12 == namesP
        changed = sorted(n for n in names12 & namesP if B.raw(n) != P.raw(n))
        rep["streams_changed_vs_h12"] = changed

        # decoded-record identity vs H12 (envelope probes promise ZERO)
        ident: Dict[str, Any] = {}
        ident["elemtable_equal"] = (
            decode_elemtable(B.inflate("Global/ElemTable", 0)) ==
            decode_elemtable(P.inflate("Global/ElemTable", 0)))
        ident["latest_payload_equal"] = (
            B.inflate("Global/Latest", 0) == P.inflate("Global/Latest", 0))
        ident["contentdocs_payload_equal"] = (
            B.inflate("Global/ContentDocuments", 0) ==
            P.inflate("Global/ContentDocuments", 0))
        bf_b = decode_basic_file_info(B.raw("BasicFileInfo"))
        bf_p = decode_basic_file_info(P.raw("BasicFileInfo"))
        bf_a = decode_basic_file_info(A.raw("BasicFileInfo"))
        ident["bfi_equal_h12"] = bf_b == bf_p
        ident["bfi_equal_native"] = bf_a == bf_p
        ident["bfi_raw_equal_native"] = A.raw("BasicFileInfo") == P.raw("BasicFileInfo")
        dit_b = decode_increment_table(B.inflate("Global/DocumentIncrementTable", 0))
        dit_p = decode_increment_table(P.inflate("Global/DocumentIncrementTable", 0))
        dit_a = decode_increment_table(A.inflate("Global/DocumentIncrementTable", 0))
        ident["dit_equal_h12"] = dit_b == dit_p
        ident["dit_equal_native"] = dit_a == dit_p
        rep["decoded_identity"] = ident

        # partitions: records byte-identical per aligned block; envelope facts
        lb = ecc.unframe_stream(B.raw(PART))
        lp = ecc.unframe_stream(P.raw(PART))
        wb = StreamWalker(lb, inflate=True, keep_data=True)
        wp = StreamWalker(lp, inflate=True, keep_data=True)
        rep["partitions"] = {
            "walker_errors": wp.errors[:3],
            "units": len(wp.units), "blocks": len(wp.blocks),
            "all_block_contents_equal_h12":
                len(wb.blocks) == len(wp.blocks) and all(
                    x.data == y.data for x, y in zip(wb.blocks, wp.blocks)),
            "new_unit_footer_blob_len": len(wp.units[-1].footer_blob),
            "junk_after_end": len(wp.end_record) - END_RECORD_LEN,
            "ecc_roundtrip_exact": ecc.frame_stream(lp) == P.raw(PART),
        }
        # instance still present (the probe must keep H12's instance)
        et = decode_elemtable(P.inflate("Global/ElemTable", 0))
        ids = {r[4] for r in et["records"]}        # 7-tuple, [4] = id
        rep["instance_present_1472964"] = 1472964 in ids

        # E3-family gate: aligned content-identical blocks byte-equal native
        la = ecc.unframe_stream(A.raw(PART))
        wa = StreamWalker(la, inflate=True, keep_data=True)
        nat_eq = 0
        comparable = 0
        for i in range(min(len(wa.blocks), len(wp.blocks))):
            ba, bp = wa.blocks[i], wp.blocks[i]
            if ba.data == bp.data:
                comparable += 1
                xa = la[ba.hdr_offset:ba.member_offset + ba.member_len + 6]
                xp = lp[bp.hdr_offset:bp.member_offset + bp.member_len + 6]
                if xa == xp:
                    nat_eq += 1
        rep["partitions"]["aligned_content_identical_blocks"] = comparable
        rep["partitions"]["of_those_byte_identical_to_native"] = nat_eq
        # CFB tree signature
        cp = parse_cfb(path)
        ca = parse_cfb(RST)
        tree_p = [(e["color"], e["left"], e["right"], e["child"])
                  for e in cp["entries"] if e]
        tree_a = [(e["color"], e["left"], e["right"], e["child"])
                  for e in ca["entries"] if e]
        rep["cfb_tree_equal_native"] = tree_p == tree_a
        return rep
    finally:
        A.close()
        B.close()
        P.close()


EXPECT = {
    # name -> (streams_changed_vs_h12 predicate description, checks)
    "E1":   {"changed": {PART}, "records_h12": True, "blob": 64, "junk": 571},
    "E1b":  {"changed": {PART}, "records_h12": True, "blob": 64, "junk": 571},
    "E6":   {"changed": {PART}, "records_h12": True, "blob": 0, "junk": 0},
    "E3":   {"changed": {PART, "Global/ContentDocuments",
                         "Global/DocumentIncrementTable", "Global/ElemTable",
                         "Global/Latest"},
             "records_h12": True, "blob": 0, "junk": 571, "e3_native_blocks": True},
    "E4":   {"changed": {"BasicFileInfo"}, "records_h12": False,
             "bfi_native": True, "blob": 0, "junk": 571},
    "E5":   {"changed": {"Global/DocumentIncrementTable"},
             "records_h12": False, "dit_native": True, "blob": 0, "junk": 571},
    "E2":   {"changed": set(), "records_h12": True, "blob": 0, "junk": 571,
             "tree_native": True},
    "E_ALL": {"changed": {PART, "BasicFileInfo", "Global/ContentDocuments",
                          "Global/DocumentIncrementTable", "Global/ElemTable",
                          "Global/Latest"},
              "records_h12": False, "bfi_native": True, "dit_native": True,
              "blob": 64, "junk": 0, "e3_native_blocks": True,
              "tree_native": True},
}


def check_expectations(name: str, rep: Dict[str, Any]) -> List[str]:
    exp = EXPECT[name]
    bad: List[str] = []
    if rep["validator"]["n_errors"]:
        bad.append(f"validator errors: {rep['validator']['first_errors']}")
    if set(rep["streams_changed_vs_h12"]) != exp["changed"]:
        bad.append(f"streams changed {rep['streams_changed_vs_h12']} != "
                   f"expected {sorted(exp['changed'])}")
    ident = rep["decoded_identity"]
    if exp["records_h12"]:
        for k in ("elemtable_equal", "latest_payload_equal",
                  "contentdocs_payload_equal", "bfi_equal_h12", "dit_equal_h12"):
            if not ident[k]:
                bad.append(f"decoded identity broken: {k}")
    if exp.get("bfi_native") and not ident["bfi_equal_native"]:
        bad.append("BFI not field-equal to native")
    if exp.get("bfi_native") and not ident["bfi_raw_equal_native"]:
        bad.append("BFI not BYTE-equal to native")
    if exp.get("dit_native") and not ident["dit_equal_native"]:
        bad.append("DIT not field-equal to native")
    P = rep["partitions"]
    if P["walker_errors"]:
        bad.append(f"walker errors {P['walker_errors']}")
    if not P["all_block_contents_equal_h12"]:
        bad.append("block CONTENTS changed vs H12 (envelope probe must not)")
    if P["new_unit_footer_blob_len"] != exp["blob"]:
        bad.append(f"footer blob len {P['new_unit_footer_blob_len']} != {exp['blob']}")
    if P["junk_after_end"] != exp["junk"]:
        bad.append(f"junk after end {P['junk_after_end']} != {exp['junk']}")
    if not P["ecc_roundtrip_exact"]:
        bad.append("ecc roundtrip broken")
    if exp.get("e3_native_blocks") and \
            P["of_those_byte_identical_to_native"] != P["aligned_content_identical_blocks"]:
        bad.append(f"E3 gate: only {P['of_those_byte_identical_to_native']}/"
                   f"{P['aligned_content_identical_blocks']} untouched blocks "
                   "byte-identical to native")
    if exp.get("tree_native") and not rep["cfb_tree_equal_native"]:
        bad.append("CFB tree not native-shaped")
    if not rep["instance_present_1472964"]:
        bad.append("instance 1472964 missing")
    if not rep["stream_set_equal_h12"]:
        bad.append("stream set changed")
    return bad


ORDER = ["E_ALL", "E1", "E1b", "E3", "E6", "E4", "E5", "E2"]


def verify(built: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    reports: Dict[str, Any] = {}
    ok = True
    for name in ORDER:
        path = os.path.join(PROBE_DIR, f"{name}.rvt")
        if not os.path.isfile(path):
            raise SystemExit(f"missing probe {relp(path)} (run probes)")
        rep = gate_probe_file(name, path)
        bad = check_expectations(name, rep)
        rep["gate"] = "OK" if not bad else "REFUSED"
        rep["gate_failures"] = bad
        reports[name] = rep
        ok = ok and not bad
        log(f"{name}: validator {rep['validator']['n_errors']} err / "
            f"{rep['validator']['n_warnings']} warn; changed "
            f"{rep['streams_changed_vs_h12']}; gate {rep['gate']}"
            + (f"  FAILURES {bad}" if bad else ""))
    if not ok:
        raise SystemExit("GATES REFUSED -- see failures above")
    return reports


def write_probes_json(built: Dict[str, Any], gates: Dict[str, Any]) -> None:
    probes = []
    for i, name in enumerate(ORDER):
        b = built.get(name, {})
        g = gates.get(name, {})
        probes.append({
            "name": name, "order": i,
            "file": b.get("file", relp(os.path.join(PROBE_DIR, f"{name}.rvt"))),
            "md5": g.get("md5") or b.get("md5"),
            "kind": "probe",
            "base": relp(RST),
            "derived_from": relp(H12),
            "axis": b.get("axis"),
            "expected": b.get("expected"),
            "gates": {
                "validator_errors": g.get("validator", {}).get("n_errors"),
                "gate": g.get("gate"),
                "streams_changed_vs_h12": g.get("streams_changed_vs_h12"),
                "decoded_identity": g.get("decoded_identity"),
                "partitions": {k: v for k, v in g.get("partitions", {}).items()
                               if k != "walker_errors"},
            },
        })
    doc = {
        "stream": "terminal-diff",
        "base": relp(RST),
        "note": "the RE-ENVELOPE probes: post-#35 every record-level "
                "hypothesis is dead; these probe the layers BELOW decoded "
                "records.  Every probe = H12 +/- exactly ONE envelope "
                "change (E_ALL = all of them).  H12's recorded verdict is "
                "FAIL (#35): any PASS here convicts its axis.",
        "charter_note_on_batch_number": "the charter says 'stage batch 41'; "
                "batch_41.json was already consumed by regcorner H13 "
                "(uploaded inside the b40 round, genesis-audit '~04:20'), "
                "so this round takes the next campaign-global number -- the "
                "no-collision law (test_batch_manifest_number) outranks the "
                "charter's literal numeral.",
        "upload_order_max_information_first": ORDER,
        "reading_the_matrix": {
            "CTRL FAIL": "round VOID",
            "E_ALL PASS": "the objection lives in the envelope / "
                          "out-of-registry layer; the singles name the axis; "
                          "if every single FAILs while E_ALL passes, a "
                          "conjunction is required -- bisect pairs next round",
            "E1 PASS": "the 0x0f3f footer blob convicted; E1b splits: E1b "
                       "PASS too => presence/shape check only (port: author "
                       "any 64-B blob in build_family_save_unit); E1b FAIL "
                       "=> the blob content is VERIFIED -- crack the "
                       "function (more corpus pairs) before any port",
            "E3 PASS": "member-ending shape convicted (port: writer.gzip_"
                       "member grows partial+finish / sync+02 0c 00 modes)",
            "E6 PASS": "baked stream-tail junk convicted (port: every emit "
                       "path truncates the logical at the true end record)",
            "E4 PASS": "BFI identity strings convicted (port decision is a "
                       "provenance question: 'rvt-writer' authorship is "
                       "TRUTHFUL; forging 'Autodesk Revit'/'RevitApplication' "
                       "in deliverables needs counsel sign-off -- same "
                       "caveat as H11's author string)",
            "E5 PASS": "DIT username scrub convicted (port: stop scrubbing, "
                       "or scrub only rows our own saves author)",
            "E2 PASS": "CFB directory tree convicted (port: cfb_writer "
                       "mimics the native insertion-order red-black shape)",
            "ALL FAIL (incl. E_ALL)": "the in-file container envelope is "
                       "exonerated wholesale EXCEPT the footer-blob CONTENT "
                       "function (E_ALL carries the donor's blob -- wrong if "
                       "the blob digests unit content).  Remaining in-file "
                       "suspects: exactly that 64-byte function.  The "
                       "desktop-Revit kit (experiments/terminal/"
                       "REVIT-CHECK-KIT.md) becomes the decisive instrument.",
        },
        "probes": probes,
        "recorded_context": {
            "H12_verdict": "FAIL (genesis-audit VERDICTS #35, b40)",
            "H10_verdict": "PASS (VERDICTS #34, b38)",
            "V20_verdict": "PASS (instance of a NATIVE unit)",
            "invariant": "newly-added unit + instance referencing it = FAIL; "
                         "same file minus instance = PASS; instance of "
                         "native unit = PASS",
        },
    }
    jdump(os.path.join(OUT_DIR, "probes.json"), doc)
    log(f"probes.json written ({len(probes)} probes)")


# ===========================================================================
# staging + kit
# ===========================================================================

def _campaign_global_next_batch() -> int:
    """Batch numbers are CAMPAIGN-GLOBAL (fleet lesson): scan every
    batch_<n>.json under experiments/."""
    import glob
    import re
    n = 14
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "batch_*.json"),
                       recursive=True):
        m = re.match(r"batch_(\d+)\.json$", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def stage() -> Dict[str, Any]:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_terminal_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(PROBE_DIR, f"{n}.rvt") for n in ORDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run probes+verify): {missing}")
    n = _campaign_global_next_batch()
    manifest = pb.stage_batch(
        files, control_from=RST, batch_n=n,
        note="terminal-diff: the RE-ENVELOPE probes (post-verdict-#35; the "
             "charter's 'batch 41' -- 41 was consumed by regcorner H13, so "
             "this is the next campaign-global number).  Every record-level "
             "hypothesis is dead; these probe the container envelope.  Each "
             "probe = H12 (recorded FAIL, #35) +/- exactly ONE envelope "
             "change; E_ALL = all of them (upload FIRST -- the biggest "
             "split).  E1/E1b footer blob, E3 member recipe, E6 tail junk, "
             "E4 BFI strings, E5 DIT usernames, E2 CFB tree.  Read with "
             "experiments/terminal/probes.json reading_the_matrix.")
    log(f"STAGED batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} ({e.get('kind')})")
    return manifest


KIT_DIR = os.path.join(OUT_DIR, "kit2")


def kit(argv: Optional[Sequence[str]] = None) -> int:
    """The desktop-Revit check kit is v2 (issue #118): built from a fresh
    clone by ``tools/revit_kit.py build`` -- K0 (byte-identical pinned base),
    K1 (shell walls), K2 (one generated family + one instance), K3 (room
    combined) + the standalone .rfa, a manifest with an id -> class/unit/
    family index, and the regenerated REVIT-CHECK-KIT.md.  The v1 pair this
    verb used to copy (H12 + BXhf_f1i1) is retired: E1/E1b PASSED in
    VERDICTS #36, so H12 failed only on its empty 0x0f3f blob, and BXhf_f1i1
    predates that fix.  This verb only delegates (``argv`` defaults to the
    build into experiments/terminal/kit2)."""
    import importlib.util
    argv = list(argv) if argv is not None else ["build", "--out", KIT_DIR]
    log("kit -> tools/revit_kit.py " + " ".join(argv)
        + "  (kit v2, issue #118; the H12/BXhf_f1i1 pair is retired)")
    spec = importlib.util.spec_from_file_location(
        "_terminal_revit_kit", os.path.join(HERE, "revit_kit.py"))
    rk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rk)
    return rk.main(argv)


# ===========================================================================
# main
# ===========================================================================

def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="terminal_diff")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("enumerate", help="the exhaustive layered diff -> terminal_diff.json")
    sub.add_parser("probes", help="build the E-probes")
    sub.add_parser("verify", help="re-run gates on emitted probes")
    sub.add_parser("stage", help="probe_batch staging (control = rst copy)")
    sub.add_parser("kit", help="the desktop-Revit check kit (delegates to tools/revit_kit.py build)")
    sub.add_parser("all", help="enumerate + probes + verify + stage + kit")
    a = ap.parse_args(argv)
    if a.cmd in ("enumerate", "all"):
        enumerate_diff()
    if a.cmd in ("probes", "all"):
        built = build_probes()
        gates = verify(built)
        write_probes_json(built, gates)
    if a.cmd == "verify":
        gates = verify()
        # preserve the axis/expected text from the existing probes.json
        built: Dict[str, Any] = {}
        pj = os.path.join(OUT_DIR, "probes.json")
        if os.path.isfile(pj):
            for p in json.load(open(pj)).get("probes", []):
                built[p["name"]] = {k: p.get(k) for k in
                                    ("file", "axis", "expected", "md5")}
        write_probes_json(built, gates)
    if a.cmd in ("stage", "all"):
        stage()
    if a.cmd in ("kit", "all"):
        return kit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
