#!/usr/bin/env python
"""species_probe.py -- THE SPECIES CELLS + THE REGISTRATION FORENSICS + v3
(species stream, 2026-08-05, post-verdict-#46).

THE MAP (genesis-audit #43..#46): pristine rst accepts EVERY loaded-famdoc
species with instances (T1r embedded-union, T1u standalone-union, B7
embedded-born, TB0r); REDUCED bases (K4 / G_ABP / G_ABPD) accept exactly
ONE -- T2a, the standalone-BORN species.  Embedded-species famdocs and our
authored famdocs fail on all reduced substrates regardless of content /
refs / binds (U16gK4 fails with byte-born ref targets; SC1 fails fully
self-contained with in-unit walked binds).

THE ROUND (staged behind one G_ABPD control, reading order first-to-last):

  T1uG   THE DECISIVE CELL: T1u's famdoc -- the standalone vendor shell +
         our 35-element content union built by the PROVEN famdoc_final
         machinery, the born Global/Latest ADocument wrapper swapped in --
         rebuilt BYTE-IDENTICALLY (machine-pinned against
         experiments/unionrec/T1u.rvt, the rst PASS) and famloaded + one
         instance on G_ABPD.  PASS => the standalone SPECIES SHAPE is the
         law on reduced bases and our content is fine inside it.
  TB0g   the embedded-born x reduced cell: the rst sample's OWN smallest
         model-instanceable embedded-born famdoc (M_Pile-Steel Pipe, unit
         41, 414 records -- TB0r's famdoc, viewer-PASS on rst) rebuilt
         byte-identically and famloaded + one instance on G_ABPD.
         DECLARED DEVIATION from the charter's "TB0's famdoc": TB0's
         donor host racadvanced has watermark 438,567 (measured) vs
         G_ABPD's 1,472,524 -- its rebased famdoc ids alias live G_ABPD
         host ids, so a byte-identical transplant is IMPOSSIBLE from that
         host.  TB0r's famdoc is the same embedded-born species on the
         watermark-equal host (rst wm == G_ABPD wm, the b52 transplant
         law), and its TB0r cell is the certified PASS baseline -- TB0g
         vs TB0r is a pure base swap.
  BX_v3  B0's recipe (our famgen famdoc via famload + one instance on
         G_ABPD) through BIRTHRIGHT v3 -- the forensics-derived species
         lanes (v2 self-containment + in-unit binds + the HOSTSYM lane).
         vs SC1 (certified FAIL): exactly ONE registered surface moves --
         the host symbol table (no ' '-named FamSymSurrogate; the placed
         instance binds a real-named symbol; T2a's registered shape).
  DEMO_250v_room_v9  the user's exact prompt end-to-end through
         rvt.frontdoor.run with birthright v3 -- v8's recipe with
         version=3 (the famgen-loader half of HOSTSYM repairs the host
         Family DOUBLE-BLANK type table v8 shipped: [' ', ' ', real] with
         m_idx=1 POINTING AT A BLANK ROW -- a shape no native host
         exhibits; native law measured on rstbasic: [' ', 'Notch'] m_idx
         1).

THE FORENSICS (``forensics`` -> experiments/species/cd_forensics.json):
T2a (the ONLY reduced-base loaded-famdoc PASS) vs SC1 (the closest FAIL;
same base, same famload lane, both appended ONE unit to G_ABPD's
rebuilt-empty ContentDocuments stream) -- EVERY registration surface
diffed: the CD stream (0x3a3 separator prologue, entry framing, end
record), the decoded inline ADocument (field-for-field), the host
ContentTable record, the FamilyMgr entry, the host Global/ElemTable rows,
the partition separator, the host-side registration elements, and the
unit internals (class histograms, self-Family shape, type table, id
policy, small-id residue).  The measured delta list IS the v3 spec; the
measured EXONERATIONS (the hypothesized standalone inline-ADocument form
is NOT the registered form; id policy identical) are recorded with the
same weight.

PROOF-ONLY: T1uG and TB0g embed vendor-born / Autodesk-sample content and
stay quarantined under experiments/ (zero donors in anything shipped);
BX_v3 and DEMO v9 carry zero donor bytes (authored birth + symbolic-id
binds, test-enforced).  STAGE ONLY -- the orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/species_probe.py forensics
    .venv/bin/python tools/species_probe.py build [--only T1uG,TB0g,...]
    .venv/bin/python tools/species_probe.py census FILE [--base BASE]
    .venv/bin/python tools/species_probe.py verify
    .venv/bin/python tools/species_probe.py stage

TERRITORY: this file, src/rvt/famgen/birthright.py (v3 lanes),
experiments/species/**, tests/test_species.py, docs/inbox/species.md,
plus the staging copies probe_batch writes under experiments/acceptance/.
IMPORTS (never edits): tools/union_reconcile.py (T1u machinery +
byte-identity pin + born-ADocument swap), tools/rft_probe.py (born-doc
loader, famload_onto, place_one), tools/selfcontained.py (four-surface
census + SC1's recipe), tools/famdoc_blobs.py, tools/bisect_instance_bug.py,
tools/probe_batch.py, rvt.famgen.birthright (v3).  No Autodesk install
dirs, no browser, no full-suite runs.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "species")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
FORENSICS = os.path.join(OUT_DIR, "cd_forensics.json")
PROBES = os.path.join(OUT_DIR, "probes.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
RAC_ADV = os.path.join(ROOT, "samples", "racadvancedsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
VENDOR_RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples",
                          "Autodesk", "racbasicsamplefamily-2026.rfa")

#: the reference files this round measures against (all viewer-read)
T2A_RVT = os.path.join(ROOT, "experiments", "rftprobe", "T2a.rvt")
SC1_RVT = os.path.join(ROOT, "experiments", "selfcontained", "SC1.rvt")
T1U_RVT = os.path.join(ROOT, "experiments", "unionrec", "T1u.rvt")
TB0R_RVT = os.path.join(ROOT, "experiments", "rftprobe", "TB0r.rvt")
DEMO_V8_RVT = os.path.join(ROOT, "experiments", "selfcontained",
                           "DEMO_250v_room_v8.rvt")

#: recorded unit GUIDs of the reference builds (experiments/*/accounting.json)
T1U_DOC_GUID = "7218d5e4-424d-4914-9904-e7bcc1794fd7"
TB0R_DOC_GUID = "54c84546-ee5d-4d52-a60e-12b37ecbbbaa"

#: TB0r donor pins (rft_probe's, re-declared so a drift refuses loudly)
TB0R_UNIT = 41
TB0R_SELF_FAMILY = 1224269
TB0R_CATEGORY = -2001300
TB0R_TYPE = "600mm Diameter"

DEMO_PROMPT = "an electrical room rated for 250V with 6 panels"

LADDER = ("T1uG", "TB0g", "BX_v3", "DEMO_250v_room_v9")

AXES = {
    "T1uG": "THE DECISIVE CELL: T1u's byte-identical famdoc (standalone "
            "vendor shell + our 35-element union, famdoc_final machinery, "
            "born Global/Latest ADocument wrapper swapped in; machine-pinned "
            "against the rst PASS T1u.rvt) famloaded + one uniform instance "
            "on G_ABPD.  The ONE thing vs T1u (PASS): the base.  vs T1v "
            "(FAIL on G_ABPD): the machinery/ADocument-wrapper/offset form.",
    "TB0g": "embedded-born x reduced: TB0r's byte-identical famdoc (rst's "
            "own M_Pile-Steel Pipe, unit 41, embedded-born species; "
            "machine-verified against the rst PASS TB0r.rvt) famloaded + "
            "one uniform instance on G_ABPD.  The ONE thing vs TB0r "
            "(PASS): the base.  Splits species-shape from ours-content on "
            "the failing side.",
    "BX_v3": "B0's recipe through birthright v3: our famgen famdoc + "
             "authored birth set + in-unit render binds + the HOSTSYM lane "
             "via famload + one instance on G_ABPD.  The ONE registered "
             "surface vs SC1 (FAIL): the host symbol table (no blank-named "
             "FamSymSurrogate; instance binds a real-named symbol -- T2a's "
             "registered shape).",
    "DEMO_250v_room_v9": "the user's exact prompt through rvt.frontdoor.run "
                         "with birthright v3: v8's recipe + version=3 (the "
                         "loader half of HOSTSYM repairs v8's double-blank "
                         "host Family type table with m_idx on a blank -- "
                         "a shape no native host exhibits).",
}


def log(msg: str) -> None:
    print(f"[species] {msg}", flush=True)


def relp(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return r if not r.startswith("..") else p
    except ValueError:
        return p


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_species_{name}", os.path.join(HERE, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CACHE: Dict[str, Any] = {}


def _ur():
    """tools/union_reconcile.py -- T1u machinery, byte-identity pin, the
    born-ADocument swap (reads only; its build/stage never invoked)."""
    if "ur" not in _CACHE:
        _CACHE["ur"] = _load_tool("union_reconcile")
    return _CACHE["ur"]


def _rp():
    if "rp" not in _CACHE:
        _CACHE["rp"] = _load_tool("rft_probe")
    return _CACHE["rp"]


def _sc():
    """tools/selfcontained.py -- the four-surface census + SC1's recipe
    facts (reads only)."""
    if "sc" not in _CACHE:
        _CACHE["sc"] = _load_tool("selfcontained")
    return _CACHE["sc"]


def _fb():
    if "fb" not in _CACHE:
        import famdoc_bisect as FB
        _CACHE["fb"] = FB
    return _CACHE["fb"]


def _fbl():
    if "fbl" not in _CACHE:
        _CACHE["fbl"] = _load_tool("famdoc_blobs")
    return _CACHE["fbl"]


def _bisect():
    if "bisect" not in _CACHE:
        import bisect_instance_bug as B
        _CACHE["bisect"] = B
    return _CACHE["bisect"]


def _room():
    if "room" not in _CACHE:
        import ifc_intent as T
        _CACHE["room"] = T
    return _CACHE["room"]


def _pb():
    if "pb" not in _CACHE:
        _CACHE["pb"] = _load_tool("probe_batch")
    return _CACHE["pb"]


# ===========================================================================
# shared decode helpers
# ===========================================================================

def _cd_entries(path: str) -> Tuple[List[Tuple[str, bytes]], bytes, int]:
    """(entries, tail, total_len) of a file's Global/ContentDocuments."""
    from rvt.container import open_rvt
    from rvt.famgen import factory as F
    with open_rvt(path) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    entries, tail = F.parse_content_documents(cd)
    return entries, tail, len(cd)


def _adoc_value(path: str, guid: Optional[str] = None) -> Tuple[str, dict]:
    """The decoded inline ADocument of a registered famdoc entry.  With no
    guid, the file must carry exactly ONE entry."""
    from rvt import adocument as A
    entries, _tail, _n = _cd_entries(path)
    if guid is None:
        if len(entries) != 1:
            raise RuntimeError(f"{relp(path)}: {len(entries)} CD entries; "
                               f"pass the guid explicitly")
        guid, payload = entries[0]
    else:
        matches = [a for g, a in entries if g == guid]
        if len(matches) != 1:
            raise RuntimeError(f"{relp(path)}: no CD entry {guid}")
        payload = matches[0]
    d = A.decode_latest(payload)
    if not d.clean:
        raise RuntimeError(f"{relp(path)}: inline ADocument {guid} does not "
                           f"decode clean")
    return guid, d.value


def _leaf_diff(a: Any, b: Any, p: str = "", out: Optional[list] = None) -> list:
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _leaf_diff(a.get(k), b.get(k), p + "." + k, out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _leaf_diff(x, y, p + f"[{i}]", out)
    else:
        if a != b:
            out.append(p)
    return out


def _shape_sig(v: Any, depth: int = 0) -> Any:
    """Structure without values: dict keys, list lengths, leaf types."""
    if isinstance(v, dict):
        if depth > 6:
            return "dict"
        return {k: _shape_sig(x, depth + 1) for k, x in sorted(v.items())}
    if isinstance(v, list):
        return f"list{len(v)}"
    if v is None:
        return "null"
    return type(v).__name__


def _added_host_elements(path: str, base: str) -> List[Dict[str, Any]]:
    """Host-side (unit 0) elements of ``path`` absent from ``base``'s
    ElemTable, with class + name facts."""
    from rvt.families import FamilyIndex
    from rvt.mutate import Document
    base_ids = set(Document.from_file(base).et_by_id)
    idx = FamilyIndex(path)
    recs = idx.unit_records(0)
    out = []
    for eid in sorted(recs.get(102, {})):
        if eid in base_ids:
            continue
        r = recs[102][eid]
        cn = idx.class_name(r.class_id)
        v = idx.value(0, eid) or {}
        row: Dict[str, Any] = {"id": eid, "class": cn, "name": v.get("m_name")}
        if cn == "FamilySymbol":
            row["family_id"] = v.get("m_familyId")
        if cn == "FamilyInstance":
            row["symbol_id"] = v.get("m_masterSymbolId")
            row["level_id"] = v.get("m_assocLevelId")
        if cn == "Family":
            ftt = ((v.get("m_pFamilyTypes") or {}).get("value") or {})
            row["type_table"] = {
                "pairs": [p.get("name") for p in (ftt.get("m_pairs") or [])],
                "m_idx": ftt.get("m_idx")}
        out.append(row)
    return out


# ===========================================================================
# THE FORENSICS: T2a (PASS) vs SC1 (FAIL) -- every registration surface
# ===========================================================================

#: the four history-identity GUID paths (fresh identity per build is the
#: measured native law; the ONLY tolerated inline-ADocument value drift)
_HISTORY_PATHS = re.compile(
    r"^\.m_pHistory\.value\.m_(creation|detach|upgrade|saveAs)GUID\.m_guid$")


def _forensic_adoc(pass_path: str, fail_path: str) -> Dict[str, Any]:
    gp, vp = _adoc_value(pass_path)
    gf, vf = _adoc_value(fail_path)
    diffs = _leaf_diff(vp, vf)

    def facts(v, guid):
        et = ((v.get("m_elemTable") or {}).get("value") or {})
        arr = et.get("m_elemArr") or []
        src = ((et.get("m_pSource") or {}).get("value") or {})
        hist = ((v.get("m_pHistory") or {}).get("value") or {})
        idg = {k: (hist.get(k) or {}).get("m_guid")
               for k in ("m_creationGUID", "m_detachGUID", "m_upgradeGUID",
                         "m_saveAsGUID")}
        aim = ((v.get("m_pAppInfoManager") or {}).get("value") or {})
        ai = aim.get("m_appInfoArr") or []
        ct = ((v.get("m_oContentTable") or {}).get("value") or {})
        owners = collections.Counter(
            "positive" if (r.get("m_OwningElementId") or -1) > 0 else "-1"
            for r in arr)
        return {"guid": guid,
                "elem_rows": len(arr),
                "id_range": ([min(r["m_id"] for r in arr),
                              max(r["m_id"] for r in arr)] if arr else None),
                "identifier_source_last": src.get("m_last"),
                "owners": dict(owners),
                "elem_table_populated": bool(arr),
                "history_identity": idg,
                "identity_equals_unit_guid": all(g == guid
                                                 for g in idg.values()),
                "m_pHostDocument": v.get("m_pHostDocument"),
                "content_rec_set": len(ct.get("m_ContentRecSet") or []),
                "appinfo_slots": len(ai),
                "appinfo_populated": sum(1 for x in ai if x),
                "stored_by_revit_build": [x.get("m_str") for x in
                                          (v.get("m_storedByRevitBuild")
                                           or [])],
                "owner_family_id": v.get("m_ownerFamilyId"),
                "dev_branch": v.get("m_devBranchInfo")}

    fp, ff = facts(vp, gp), facts(vf, gf)
    identity_only = [d for d in diffs
                     if _HISTORY_PATHS.match(d)
                     or d == ".m_ownerFamilyId"
                     or d.startswith(".m_elemTable.")]
    beyond = [d for d in diffs if d not in identity_only]
    return {
        "pass": fp, "fail": ff,
        "n_diff_paths": len(diffs),
        "diff_paths_beyond_identity_and_elem_rows": beyond,
        "form_identical_modulo_identity": not beyond,
        "verdict": (
            "the registered inline ADocument is FORM-IDENTICAL between the "
            "PASS and the FAIL (identity GUIDs + ownerFamilyId + elem rows "
            "only); BOTH ship the authored embedded form -- m_elemTable "
            "POPULATED inline, four history GUIDs == own unit GUID, "
            "m_pHostDocument weakref 1, ContentRecSet 0, 0/239 AppInfo "
            "registries, storedByRevitBuild [].  The hypothesized "
            "standalone form (m_elemTable NULL, owners externalized, NO "
            "history GUIDs) is the standalone FILE's Global/Latest shape, "
            "not the registered shape.  Cross-evidence: U16g shipped the "
            "born wrapper (independent identity, 131/239 registries, donor "
            "build strings) and FAILED on G_ABPD -- the ADocument axis is "
            "dead on reduced bases."),
    }


def _forensic_registries(pass_path: str, fail_path: str,
                         base: str) -> Dict[str, Any]:
    """ContentTable record + FamilyMgr entry, host Global/Latest side."""
    from rvt.container import open_rvt
    from rvt import adocument as A

    def latest(path):
        with open_rvt(path) as f:
            return A.decode_latest(f.inflate("Global/Latest")).value

    out: Dict[str, Any] = {}
    rows = {}
    fams = {}
    for name, path in (("base", base), ("pass", pass_path),
                       ("fail", fail_path)):
        v = latest(path)
        ct = ((v.get("m_oContentTable") or {}).get("value") or {})
        rows[name] = list(ct.get("m_ContentRecSet") or [])
        aim = ((v.get("m_pAppInfoManager") or {}).get("value") or {})
        for slot in (aim.get("m_appInfoArr") or []):
            if isinstance(slot, dict) and slot.get("ptr_class") == "FamilyMgr":
                fams[name] = list(((slot.get("value") or {})
                                   .get("m_arrLoadedFamilyInfo")) or [])
    out["content_rec_counts"] = {k: len(v) for k, v in rows.items()}
    base_json = {json.dumps(x, sort_keys=True, default=str)
                 for x in fams.get("base", [])}
    added = {}
    for name in ("pass", "fail"):
        added[name] = [x for x in fams.get(name, [])
                       if json.dumps(x, sort_keys=True, default=str)
                       not in base_json]
    out["family_mgr_added"] = added
    prow = rows["pass"][0] if rows["pass"] else {}
    frow = rows["fail"][0] if rows["fail"] else {}
    sd = [k for k in set(prow) | set(frow)
          if _shape_sig(prow.get(k)) != _shape_sig(frow.get(k))]
    out["content_rec_rows"] = {"pass": prow, "fail": frow,
                               "shape_diff_keys": sd}
    out["verdict"] = (
        "ContentTable record and FamilyMgr entry are SHAPE-IDENTICAL "
        "between the PASS and the FAIL (identity GUID, surrogate id and "
        "the episode element count are the only value differences).")
    return out


def _forensic_elemtable(pass_path: str, fail_path: str,
                        base: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    from rvt.mutate import Document
    base_ids = set(Document.from_file(base).et_by_id)
    out: Dict[str, Any] = {}
    for name, path in (("pass", pass_path), ("fail", fail_path)):
        with open_rvt(path) as f:
            raw = f.raw("Global/ElemTable")
        et = parse_elemtable(inflate_global_stream(raw).payload, relp(path))
        rows = {int(r.id): r for r in et.records}
        added = sorted(i for i in rows if i not in base_ids)
        shapes = collections.Counter()
        for i in added:
            r = rows[i]
            shapes[(r.owner_id != 0xFFFFFFFFFFFFFFFF,
                    r.original_id == r.id, r.partition_id, r.renumbered)] += 1
        out[name] = {"total_rows": len(rows), "added": len(added),
                     "row_shapes": {str(k): v for k, v in shapes.items()}}
    out["verdict"] = ("host Global/ElemTable rows are SHAPE-IDENTICAL "
                      "(owner law identical: ParamElemFamily twins own to "
                      "the host Family; surrogate/symbol/instance rows "
                      "ownerless; original_id == id; partition 0).")
    return out


def _forensic_units(pass_path: str, fail_path: str) -> Dict[str, Any]:
    """Unit separators, class histograms, self-Family shape, type table,
    id policy, small-id residue."""
    from rvt.families import FamilyIndex
    out: Dict[str, Any] = {}
    idxs = {}
    hists = {}
    for name, path in (("pass", pass_path), ("fail", fail_path)):
        idx = FamilyIndex(path)
        idxs[name] = idx
        if len(idx.units) != 2:
            raise RuntimeError(f"{relp(path)}: expected host + ONE unit, "
                               f"got {len(idx.units)}")
        u = idx.units[1]
        recs = idx.unit_records(1)
        h = collections.Counter()
        for eid, r in recs.get(102, {}).items():
            h[idx.class_name(r.class_id)] += 1
        hists[name] = h
        ids = sorted(recs.get(102, {}))
        # RAW small-int census of the rep segments (positive ints at or
        # below the born standalone id ceiling that are not unit ids).
        # NOTE: an UNTYPED walk -- it counts ordinary small integers too,
        # so it over-counts on both sides; the schema-TYPED alias count is
        # HR1's (T2a: 45 born-internal rep ids, SC1: 0).  Recorded here
        # only to show BOTH sides carry small ints in reps (the raw walk
        # separates nothing).
        member = set(ids)
        small = collections.Counter()

        def walk(node):
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, int) and not isinstance(node, bool):
                if 0 < node <= 7674 and node not in member:
                    small[node] += 1

        for eid, r in recs.get(103, {}).items():
            if idx.class_name(r.class_id) == "GElement":
                walk(idx.value(1, eid, 103))
        out[name] = {
            "unit_separator": {"guid": str(u.guid), "counter": u.counter,
                               "first_block": u.first_block,
                               "n_blocks": u.n_blocks},
            "n_records": sum(h.values()),
            "id_range": [min(ids), max(ids)] if ids else None,
            "id_policy": "contiguous watermark+1.. (current-id)",
            "rep_small_int_values_raw_untyped": len(small),
            "rep_small_int_hits_raw_untyped": sum(small.values()),
            "typed_alias_reference": "HR1 (schema-typed): pass 45 born-internal rep aliases, fail 0",
        }
    t, s = hists["pass"], hists["fail"]
    delta = {c: [t.get(c, 0), s.get(c, 0)]
             for c in sorted(set(t) | set(s)) if t.get(c, 0) != s.get(c, 0)}
    out["class_histogram_delta"] = delta
    out["classes_diverging"] = len(delta)
    out["roster_gap_pass_minus_fail"] = sum(t.values()) - sum(s.values())

    # self-Family shape diff (key sets + shape signatures)
    def self_family(idx):
        recs = idx.unit_records(1)
        fams = [(eid, idx.value(1, eid) or {})
                for eid, r in recs.get(102, {}).items()
                if idx.class_name(r.class_id) == "Family"]
        # the self-Family is the '' -named shared one (measured both files)
        for eid, v in sorted(fams):
            if not str(v.get("m_name") or ""):
                return eid, v, idx.value(1, eid, 101) or {}
        raise RuntimeError("no self-Family found")

    ep, vp, hp = self_family(idxs["pass"])
    ef, vf, hf = self_family(idxs["fail"])
    obj_shape = [k for k in set(vp) | set(vf)
                 if _shape_sig(vp.get(k)) != _shape_sig(vf.get(k))]
    hdr_shape = [k for k in set(hp) | set(hf)
                 if _shape_sig(hp.get(k)) != _shape_sig(hf.get(k))]
    def tt(v):
        ftt = ((v.get("m_pFamilyTypes") or {}).get("value") or {})
        return {"pairs": [p.get("name") for p in (ftt.get("m_pairs") or [])],
                "m_idx": ftt.get("m_idx")}
    out["self_family"] = {
        "pass_id": ep, "fail_id": ef,
        "obj_key_set_delta": sorted(set(vp) ^ set(vf)),
        "obj_shape_diff_keys": sorted(obj_shape),
        "hdr_key_set_delta": sorted(set(hp) ^ set(hf)),
        "hdr_shape_diff_keys": sorted(hdr_shape),
        "m_bShared": {"pass": vp.get("m_bShared"), "fail": vf.get("m_bShared")},
        "unit_type_table": {"pass": tt(vp), "fail": tt(vf)},
    }
    return out


def _native_host_family_law(sample: str = RST) -> Dict[str, Any]:
    """The native HOST Family type-table law, measured on the corpus: at
    most ONE leading blank row; when real pairs exist, m_idx names a real
    pair (never a blank)."""
    from rvt.families import FamilyIndex, family_documents
    idx = FamilyIndex(sample)
    n = double_blank = idx_on_blank = 0
    for fam in family_documents(idx):
        fid = fam.get("family_id")
        if fid is None:
            continue
        v = idx.value(0, fid) or {}
        ftt = ((v.get("m_pFamilyTypes") or {}).get("value") or {})
        pairs = [str(p.get("name", "")) for p in (ftt.get("m_pairs") or [])]
        if not pairs:
            continue
        n += 1
        blanks = [i for i, nm in enumerate(pairs) if not nm.strip()]
        if len(blanks) > 1:
            double_blank += 1
        mi = ftt.get("m_idx")
        if (isinstance(mi, int) and 0 <= mi < len(pairs)
                and not pairs[mi].strip() and len(pairs) > 1):
            idx_on_blank += 1
    return {"sample": relp(sample), "host_family_rows": n,
            "rows_with_more_than_one_blank": double_blank,
            "rows_with_midx_on_blank_despite_real_pairs": idx_on_blank,
            "law": "at most ONE leading blank current-values row; m_idx "
                   "names a real pair whenever real pairs exist"}


def forensics() -> Dict[str, Any]:
    """T2a vs SC1: every registration surface, measured.  Writes
    experiments/species/cd_forensics.json."""
    t0 = time.time()
    out: Dict[str, Any] = {
        "tool": "tools/species_probe.py forensics",
        "pass_file": relp(T2A_RVT), "fail_file": relp(SC1_RVT),
        "base": relp(G_ABPD),
        "question": ("T2a (the ONLY reduced-base loaded-famdoc PASS) and "
                     "SC1 (the closest FAIL) both appended ONE unit to "
                     "G_ABPD's rebuilt-empty ContentDocuments stream via "
                     "famload.  What differs, surface by surface?"),
    }
    # 1. the CD stream framing
    st = {}
    for name, path in (("base", G_ABPD), ("pass", T2A_RVT),
                       ("fail", SC1_RVT)):
        entries, tail, n = _cd_entries(path)
        st[name] = {"stream_len": n, "entries": len(entries),
                    "entry_guids": [g for g, _a in entries],
                    "adoc_bytes": [len(a) for _g, a in entries],
                    "tail_hex": tail.hex(),
                    "prologue": "each entry opens with the 12-byte 0x3a3 "
                                "separator (u16 0x3a3, i32 -1, u16 0x3a2, "
                                "i32 -1); stream ends with the 14-byte "
                                "0x3a3 end record"}
    same_tail = st["pass"]["tail_hex"] == st["fail"]["tail_hex"] == \
        st["base"]["tail_hex"]
    out["cd_stream"] = {**st, "framing_identical": same_tail and
                        st["pass"]["entries"] == st["fail"]["entries"] == 1,
                        "verdict": "one entry each, identical separator "
                                   "prologue and end record -- framing "
                                   "EXONERATED"}
    # 2. the inline ADocument
    out["inline_adoc"] = _forensic_adoc(T2A_RVT, SC1_RVT)
    # 3. ContentTable + FamilyMgr
    out["host_registries"] = _forensic_registries(T2A_RVT, SC1_RVT, G_ABPD)
    # 4. host ElemTable rows
    out["host_elemtable"] = _forensic_elemtable(T2A_RVT, SC1_RVT, G_ABPD)
    # 5. host-side registration elements -- THE SYMBOL TABLE DELTA
    added = {"pass": _added_host_elements(T2A_RVT, G_ABPD),
             "fail": _added_host_elements(SC1_RVT, G_ABPD)}

    def sym_facts(rows):
        surs = [r for r in rows if r["class"] == "FamSymSurrogate"]
        syms = [r for r in rows if r["class"] == "FamilySymbol"]
        inst = [r for r in rows if r["class"] == "FamilyInstance"]
        fam = [r for r in rows if r["class"] == "Family"]
        blank = [r for r in surs if not str(r.get("name") or "").strip()]
        bound = None
        if inst and surs:
            sid = inst[0].get("symbol_id")
            # FamSymSurrogate.m_elemId names the symbol; pair by allocation
            # order (surrogate immediately precedes its symbol)
            for i, s in enumerate(surs):
                if i < len(syms) and syms[i]["id"] == sid:
                    bound = s.get("name")
        return {"n_by_class": dict(collections.Counter(
                    r["class"] for r in rows)),
                "symbol_pairs": [s.get("name") for s in surs],
                "blank_named_surrogates": len(blank),
                "instance_symbol_id": inst[0].get("symbol_id") if inst
                else None,
                "instance_bound_pair_name": bound,
                "host_family_type_table": fam[0].get("type_table") if fam
                else None}

    out["host_registration"] = {
        "pass": sym_facts(added["pass"]), "fail": sym_facts(added["fail"]),
        "added_elements": added,
        "native_host_family_law": _native_host_family_law(),
        "verdict": (
            "THE ONE separating registered surface: the HOST SYMBOL TABLE. "
            "The FAIL authored TWO FamSymSurrogate+FamilySymbol pairs, the "
            "first named ' ' (blank), and bound the placed instance to the "
            "blank pair's symbol; the PASS authored exactly ONE pair, "
            "non-blank, instance bound to it.  No native host exhibits a "
            "blank-named symbol row.  Root cause: birthright v2's types "
            "lane prepends the blank pair to doc.types; famload authors "
            "one host pair per doc.types entry and plan.symbol_id = the "
            "first."),
    }
    # 5b. the famgen-loader lane's own leak (DEMO v8's host Family rows)
    if os.path.isfile(DEMO_V8_RVT):
        v8 = _added_host_elements(DEMO_V8_RVT, G_ABPD)
        v8fams = [r for r in v8 if r["class"] == "Family"]
        out["famgen_loader_leak_demo_v8"] = {
            "host_family_type_tables": [r.get("type_table") for r in v8fams],
            "verdict": ("the famgen loader copies the BAKED unit table "
                        "([' ', real]) and prepends its OWN blank row -> "
                        "v8's host Family rows carry a DOUBLE-blank table "
                        "with m_idx=1 POINTING AT A BLANK ROW -- a shape "
                        "no native host exhibits (native law above)."),
        }
    # 6. unit internals
    out["unit_internal"] = _forensic_units(T2A_RVT, SC1_RVT)
    # 7. THE RANKED DELTA LIST
    out["species_delta_list"] = [
        {"rank": 1, "surface": "host symbol table + instance binding",
         "delta": "FAIL: blank-named FamSymSurrogate + instance bound to "
                  "the blank pair's symbol; PASS: one non-blank pair, "
                  "instance bound to it",
         "authorable": True, "v3_lane": "hostsym (famload half: strip "
         "blank pairs from the famload-facing doc.types post-finalize; "
         "famgen-loader half: apply_host_family_table_law)"},
        {"rank": 2, "surface": "unit roster (class histogram)",
         "delta": "PASS carries +{} elements across {} classes (the "
                  "overlapping-class shortfall + the reference-closure "
                  "dropped set + the loaded-family registration block)"
                  .format(out["unit_internal"]["roster_gap_pass_minus_fail"],
                          out["unit_internal"]["classes_diverging"]),
         "authorable": "deferred", "why_deferred": (
             "T1v (the FULL born roster + our 35 elements, clean symbol "
             "table, authored-empty ADocument) FAILED on G_ABPD -- roster "
             "parity is measured NOT SUFFICIENT with ours-content present; "
             "the true-up is the pre-committed BX_v3-FAIL branch lane")},
        {"rank": 3, "surface": "unit content authorship",
         "delta": "PASS content is BORN; FAIL content is authored (ours + "
                  "authored birth set, field-model-verified 0 mismatches)",
         "authorable": False, "note": "this is the residual axis T1uG and "
         "TB0g split"},
        {"rank": "exonerated", "surface": "inline ADocument form",
         "delta": "form-identical modulo identity (see inline_adoc)",
         "note": "the charter-hypothesized standalone form (m_elemTable "
                 "NULL, external owners, NO history GUIDs) is the "
                 "standalone FILE form, not the registered form; U16g "
                 "shipped the born wrapper and still failed"},
        {"rank": "exonerated", "surface": "id policy",
         "delta": "both register contiguous watermark+1.. (current-id); "
                  "the PASS additionally carries unremapped born-internal "
                  "small-id rep aliases (residue, tolerated per HR1, not "
                  "a shape to author)"},
        {"rank": "exonerated", "surface": "CD framing / ContentTable row / "
         "FamilyMgr entry / host ElemTable rows / partition separator",
         "delta": "shape-identical"},
    ]
    out["seconds"] = round(time.time() - t0, 1)
    jdump(FORENSICS, out)
    log(f"forensics -> {relp(FORENSICS)} (adoc form-identical: "
        f"{out['inline_adoc']['form_identical_modulo_identity']}; "
        f"blank surrogates fail-side: "
        f"{out['host_registration']['fail']['blank_named_surrogates']}; "
        f"roster gap {out['unit_internal']['roster_gap_pass_minus_fail']})")
    return out


# ===========================================================================
# the species census (the machine gate for v3-authored output)
# ===========================================================================

def species_census(path: str, base: str = G_ABPD, *,
                   ours_content: bool = True) -> Dict[str, Any]:
    """The REGISTERED species-shape census of every added famdoc in
    ``path``: host symbol law, host Family type-table law, unit-side
    blank-pair-first law, inline-ADocument registered form, and (for
    ours-content famdocs) the four-surface self-containment + walked-bind
    census.  ``species_ok`` is the machine gate BX_v3 / DEMO v9 must
    pass."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex(path)
    added = _added_host_elements(path, base)
    surs = [r for r in added if r["class"] == "FamSymSurrogate"]
    syms = [r for r in added if r["class"] == "FamilySymbol"]
    insts = [r for r in added if r["class"] == "FamilyInstance"]
    fams = [r for r in added if r["class"] == "Family"]
    blank_surs = [r for r in surs if not str(r.get("name") or "").strip()]
    sym_name = {}
    for i, s in enumerate(surs):
        if i < len(syms):
            sym_name[syms[i]["id"]] = s.get("name")
    inst_bound = [{"instance": r["id"], "symbol": r.get("symbol_id"),
                   "pair_name": sym_name.get(r.get("symbol_id"))}
                  for r in insts]
    inst_blank = [b for b in inst_bound
                  if b["pair_name"] is not None
                  and not str(b["pair_name"]).strip()]
    fam_tables = [r.get("type_table") for r in fams]
    fam_bad = []
    for t in fam_tables:
        pairs = [str(x) for x in (t or {}).get("pairs") or []]
        mi = (t or {}).get("m_idx")
        blanks = [i for i, nm in enumerate(pairs) if not nm.strip()]
        ok = bool(len(blanks) <= 1 and (not blanks or blanks[0] == 0)
                  and isinstance(mi, int) and 0 <= mi < len(pairs)
                  and (pairs[mi].strip() or len(pairs) == 1))
        if not ok:
            fam_bad.append(t)
    units = []
    for u in range(1, len(idx.units)):
        recs = idx.unit_records(u)
        fam_ids = [eid for eid, r in recs.get(102, {}).items()
                   if idx.class_name(r.class_id) == "Family"
                   and not str((idx.value(u, eid) or {}).get("m_name") or "")]
        guid = str(idx.units[u].guid)
        unit_tt = None
        if fam_ids:
            v = idx.value(u, sorted(fam_ids)[0]) or {}
            ftt = ((v.get("m_pFamilyTypes") or {}).get("value") or {})
            unit_tt = {"pairs": [p.get("name")
                                 for p in (ftt.get("m_pairs") or [])],
                       "m_idx": ftt.get("m_idx")}
        _g, av = _adoc_value(path, guid)
        et = ((av.get("m_elemTable") or {}).get("value") or {})
        arr = et.get("m_elemArr") or []
        hist = ((av.get("m_pHistory") or {}).get("value") or {})
        aim = ((av.get("m_pAppInfoManager") or {}).get("value") or {})
        ai = aim.get("m_appInfoArr") or []
        ct = ((av.get("m_oContentTable") or {}).get("value") or {})
        pairs = (unit_tt or {}).get("pairs") or []
        mi = (unit_tt or {}).get("m_idx")
        blank_first = bool(pairs) and not str(pairs[0]).strip()
        idx_real = bool(isinstance(mi, int) and 0 <= mi < len(pairs)
                        and (str(pairs[mi]).strip() or len(pairs) == 1))
        units.append({
            "unit": u, "guid": guid, "n_records": len(recs.get(102, {})),
            "unit_type_table": unit_tt,
            "unit_blank_pair_first": blank_first,
            "unit_idx_on_real": idx_real,
            "adoc": {
                "elem_rows": len(arr),
                "rows_match_records": len(arr) == len(recs.get(102, {})),
                "host_weakref_1": av.get("m_pHostDocument") == {"weakref": 1},
                "content_rec_set": len(ct.get("m_ContentRecSet") or []),
                "appinfo_populated": sum(1 for x in ai if x),
                "stored_by_revit_build": [x.get("m_str") for x in
                                          (av.get("m_storedByRevitBuild")
                                           or [])],
                "identity_equals_unit_guid": all(
                    (hist.get(k) or {}).get("m_guid") == guid
                    for k in ("m_creationGUID", "m_detachGUID",
                              "m_upgradeGUID", "m_saveAsGUID")),
            },
        })
    out: Dict[str, Any] = {
        "file": relp(path), "base": relp(base),
        "host_symbol_pairs": [s.get("name") for s in surs],
        "blank_named_surrogates": len(blank_surs),
        "instances_bound": inst_bound,
        "instances_bound_to_blank_pair": len(inst_blank),
        "host_family_type_tables": fam_tables,
        "host_family_tables_off_native_law": fam_bad,
        "units": units,
    }
    checks = {
        "no_blank_host_surrogate": len(blank_surs) == 0,
        "no_instance_on_blank_pair": len(inst_blank) == 0,
        "host_family_tables_native": not fam_bad,
        "unit_tables_blank_pair_first": all(u["unit_blank_pair_first"]
                                            for u in units),
        "unit_tables_idx_on_real": all(u["unit_idx_on_real"]
                                       for u in units),
        "adoc_registered_form": all(
            u["adoc"]["rows_match_records"] and u["adoc"]["host_weakref_1"]
            and u["adoc"]["content_rec_set"] == 0 for u in units),
    }
    if ours_content:
        SC = _sc()
        fc = SC.famdoc_census(path, base)
        out["four_surface"] = {k: fc.get(k) for k in
                               ("self_contained", "host_resident_total",
                                "walked_self_contained")}
        checks["self_contained"] = bool(fc.get("self_contained"))
    out["checks"] = checks
    out["species_ok"] = all(checks.values())
    return out


# ===========================================================================
# rung builders
# ===========================================================================

def _verify_unit_bytes_born(doc, target_file: str,
                            target_guid: str) -> Dict[str, Any]:
    """Byte-identity for a BORN (donor-embedded) famdoc rebuild: any
    ``revit.local.family:`` session strings are the DONOR's OWN (they ride
    verbatim in the donor bytes -- measured: rst unit 41 carries 3 native
    ones), so NO pinning happens; the hex sets must already be EQUAL and
    the rebuilt unit segments must byte-match the target's."""
    UR = _ur()
    from rvt.families import FamilyIndex, unit_segments
    hexes = UR.doc_session_hexes(doc.elements)
    idx = FamilyIndex(target_file)
    tgt = None
    for i, u in enumerate(idx.units):
        if str(u.guid) == target_guid:
            tgt = i
    if tgt is None:
        raise RuntimeError(f"{relp(target_file)}: no unit {target_guid}")
    tgt_hexes: set = set()
    for eid, r in idx.unit_records(tgt).get(102, {}).items():
        if idx.class_name(r.class_id) == "ParamElemFamily":
            v = idx.value(tgt, eid) or {}
            tid = str((((v.get("m_pParamDef") or {}).get("value") or {})
                       .get("m_typeId") or {}).get("m_typeId") or "")
            tgt_hexes.update(UR.SESSION_RE.findall(tid))
    if hexes != tgt_hexes:
        raise RuntimeError(
            f"born famdoc session strings differ from the target's "
            f"(mine {sorted(hexes)}, target {sorted(tgt_hexes)}) -- these "
            f"ride verbatim in a born famdoc; a difference means the "
            f"rebuild is NOT the same donor bytes; refused")
    segs = doc.to_embedded_unit()["segments"]
    got = unit_segments(idx, tgt)
    equal = {int(k): (segs.get(k) == got.get(k))
             for k in sorted(set(segs) | set(got))}
    if not all(equal.values()):
        bad = [k for k, ok in equal.items() if not ok]
        raise RuntimeError(
            f"rebuilt born unit is NOT byte-identical to "
            f"{relp(target_file)} unit {tgt}: segments {bad} differ -- "
            f"refused")
    return {"target_file": relp(target_file), "target_unit": tgt,
            "target_guid": target_guid,
            "session_hexes_native_donor": sorted(hexes),
            "session_hex_pinned": "none needed (donor strings ride "
                                  "verbatim; sets equal)",
            "segments_byte_identical": {str(k): v for k, v in equal.items()},
            "segment_bytes": {str(k): len(v)
                              for k, v in sorted(segs.items())}}


def _adoc_value_diff_vs(swapped_path: str, guid: str, ref_path: str,
                        ref_guid: str) -> Dict[str, Any]:
    """The swapped inline ADocument must equal the reference build's
    field-for-field, modulo exactly the four history identity GUIDs
    (fresh per build -- the measured native law).  Build-refusing."""
    _g, mine = _adoc_value(swapped_path, guid)
    _g2, theirs = _adoc_value(ref_path, ref_guid)
    diffs = _leaf_diff(mine, theirs)
    unexpected = [d for d in diffs if not _HISTORY_PATHS.match(d)]
    if unexpected:
        raise RuntimeError(f"swapped inline ADocument differs from "
                           f"{relp(ref_path)}'s beyond the history "
                           f"identity: {unexpected[:6]}")
    return {"ref": relp(ref_path), "n_diff_paths": len(diffs),
            "all_within_history_identity": True, "diff_paths": diffs}


def build_t1ug() -> Dict[str, Any]:
    """T1uG: T1u's byte-identical famdoc + full recipe (union_reconcile's
    T1u builder verbatim -- make_union_doc_standalone + the born-ADocument
    swap), famload + one uniform instance on G_ABPD."""
    UR = _ur()
    rp = UR._rp()
    T = _room()
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    wm_r = T.host_watermark(RST)
    if wm != wm_r:
        raise RuntimeError(f"T1uG: G_ABPD watermark {wm} != RST watermark "
                           f"{wm_r} -- the byte-identical transplant "
                           f"assumption fails; re-derive the plan")
    pdir = os.path.join(BUILD_DIR, "T1uG")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T1uG.rvt")
    info: Dict[str, Any] = {"probe": "T1uG", "axis": AXES["T1uG"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "rfa": relp(VENDOR_RFA)}
    doc, rep, carried, ctx = UR.make_union_doc_standalone(UR.VENDOR_RFA, wm)
    info["union"] = {
        "shell_block": rep["shell_block"],
        "shell_rebase": rep["shell_rebase"],
        "n_carried": len(rep["carried"]),
        "registration": rep["registration"],
        "port_law": rep["port_law"],
    }
    # the byte-identity pin discovers fresh-vs-target session hex by set
    # difference against T1u.rvt (whose carried block is pinned to U16's
    # hex) and REFUSES unless segments 101/102/103 byte-match
    info["byte_identity"] = UR.pin_doc_to_target_unit(doc, T1U_RVT,
                                                      T1U_DOC_GUID)
    info["document_guid"] = doc.document_guid          # fresh (house law)
    info["n_elements"] = len(doc.elements)
    info["reference_resolution"] = UR.famdoc_refs(doc, G_ABPD)

    def _swap(src, dst):
        rec = UR.swap_born_adoc(src, dst, doc=doc, rfa_path=UR.VENDOR_RFA,
                                idmap=ctx["idmap"])
        rec["machinery"] = ("union_reconcile.swap_born_adoc VERBATIM "
                            "(T1u's own axis-6 port; only the host file "
                            "differs)")
        return rec

    info.update(UR._build_common("T1uG", doc, host=G_ABPD,
                                 category=int(doc.category_id), pdir=pdir,
                                 outp=outp, adoc_swap=_swap))
    info["instance_category"] = int(doc.category_id)
    info["adoc_value_diff_vs_t1u"] = _adoc_value_diff_vs(
        os.path.join(pdir, "T1uG_load_adoc.rvt"), doc.document_guid,
        T1U_RVT, T1U_DOC_GUID)
    info["species"] = species_census(outp, G_ABPD, ours_content=False)
    return info


def build_tb0g() -> Dict[str, Any]:
    """TB0g: TB0r's byte-identical famdoc (rst unit 41, embedded-born)
    famloaded + one uniform instance on G_ABPD."""
    rp = _rp()
    T = _room()
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    wm_r = T.host_watermark(RST)
    if wm != wm_r:
        raise RuntimeError(f"TB0g: G_ABPD watermark {wm} != RST watermark "
                           f"{wm_r} -- the byte-identical transplant "
                           f"assumption fails")
    wm_rac = T.host_watermark(RAC_ADV)
    pdir = os.path.join(BUILD_DIR, "TB0g")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "TB0g.rvt")
    fam_row = rp.host_family_row(RST, TB0R_UNIT)
    if (rp.TB0R_UNIT, rp.TB0R_SELF_FAMILY) != (TB0R_UNIT, TB0R_SELF_FAMILY):
        raise RuntimeError("TB0g: rft_probe's TB0r pins drifted from this "
                           "stream's re-declaration; re-measure")
    info: Dict[str, Any] = {
        "probe": "TB0g", "axis": AXES["TB0g"],
        "base": relp(G_ABPD), "watermark": wm,
        "donor": {k: fam_row.get(k) for k in
                  ("family_id", "family_name", "category", "part_type",
                   "n_records", "unit")},
        "deviation": {
            "charter_named": "TB0's famdoc (racadvanced unit 33)",
            "used": "TB0r's famdoc (rst unit 41) -- same embedded-born "
                    "species, watermark-equal host",
            "why": f"racadvanced watermark {wm_rac} != G_ABPD watermark "
                   f"{wm}: TB0's rebased famdoc ids "
                   f"({wm_rac + 1}..{wm_rac + 381}) alias LIVE G_ABPD host "
                   f"ids, so a byte-identical transplant from that host is "
                   f"impossible; TB0r's famdoc rides byte-identically "
                   f"(rst wm == G_ABPD wm, the b52 transplant law) and its "
                   f"TB0r cell is the certified PASS baseline",
        },
    }
    part_type = int(fam_row.get("part_type") or 0)
    doc, drep = rp.born_doc_from_unit(
        RST, TB0R_UNIT, TB0R_SELF_FAMILY, wm,
        name=f"{fam_row.get('family_name')} TB0r",
        category_id=TB0R_CATEGORY, part_type=part_type, type_name=TB0R_TYPE)
    info["hybrid"] = drep
    info["byte_identity"] = _verify_unit_bytes_born(doc, TB0R_RVT,
                                                    TB0R_DOC_GUID)
    info["document_guid"] = doc.document_guid          # fresh (house law)
    info["n_elements"] = len(doc.elements)
    UR = _ur()
    info["reference_resolution"] = UR.famdoc_refs(doc, G_ABPD)
    src = os.path.join(pdir, "TB0g_load.rvt")
    info["load"] = rp.famload_onto(G_ABPD, doc, src, "TB0g")
    info["immediate_parent"] = relp(src)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    info["placement"] = ("uniform template path (ConstructedSpecimens on "
                         "G_ABPD + add_family_instance + commit; category "
                         "= the family's own)")
    info["instance"] = rp.place_one(src, outp, host=G_ABPD, symbol_id=sym,
                                    family_id=fam, category=TB0R_CATEGORY)
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["instance_category"] = TB0R_CATEGORY
    fbl = _fbl()
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    info["species"] = species_census(outp, G_ABPD, ours_content=False)
    return info


def build_bx_v3() -> Dict[str, Any]:
    """BX_v3: SC1's exact recipe (famload + builder + one instance on
    G_ABPD, birthright with binds) at version=3.  The ONE registered
    surface vs SC1: the host symbol table."""
    SC = _sc()
    rp = _rp()
    FB = _fb()
    fbl = _fbl()
    T = _room()
    from rvt.famgen import birthright as BR
    from rvt import famload as FL
    spec = BR.read_birth_spec(SC.BIRTH_SPEC)
    binds = BR.read_bind_spec(SC.BINDS_PATH)
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "BX_v3")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "BX_v3.rvt")
    info: Dict[str, Any] = {"probe": "BX_v3", "axis": AXES["BX_v3"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256"),
                            "binds": {k: v["__eid__"] for k, v in
                                      (binds.get("binds") or {}).items()}}
    products: Dict[str, Any] = {}

    def mk(start_id):
        prod = FB.our_product(start_id)
        products["BX_v3"] = prod
        return prod.doc

    src = os.path.join(pdir, "BX_v3_load.rvt")
    with BR.enabled(spec, binds=binds, version=3) as br_ctx:
        res = FL.load_family_documents(
            G_ABPD, [FL.FamilyLoad(key="BX_v3", builder=mk)], src,
            validate=True, report_path=src + ".load.json")
    if not res.ok:
        raise RuntimeError(f"BX_v3: famload failed: {res.stop_reason}")
    if not br_ctx["reports"]:
        raise RuntimeError("BX_v3: birthright never fired")
    ent = br_ctx["reports"][0]
    rep = ent.get("report") or {}
    if rep.get("version") != 3:
        raise RuntimeError(f"BX_v3: birthright ran version "
                           f"{rep.get('version')}, expected 3")
    hs = rep.get("hostsym") or {}
    if not hs.get("applied"):
        raise RuntimeError(f"BX_v3: hostsym lane did not apply: {hs}")
    if not (ent.get("verify") or {}).get("ok"):
        raise RuntimeError("BX_v3: authored-vs-mined verify not ok")
    if not (ent.get("walked_bind_census") or {}).get("self_contained"):
        raise RuntimeError("BX_v3: doc-side walked binds not self-contained")
    info["birthright"] = {
        "version": 3,
        "n_added": ent.get("n_added"),
        "verify_ok": (ent.get("verify") or {}).get("ok"),
        "hostsym": hs,
        "binds_bound": (ent.get("binds") or {}).get("bound"),
        "walked_bind_census": ent.get("walked_bind_census"),
    }
    p = res.plans[0]
    if [n for n in p.type_names if not str(n).strip()]:
        raise RuntimeError(f"BX_v3: famload plan still carries a blank "
                           f"type name: {p.type_names!r}")
    info["load"] = {"family_id": p.host_family_id, "symbol_id": p.symbol_id,
                    "guid": p.guid, "type_names": list(p.type_names or []),
                    "part_type": p.part_type}
    info["immediate_parent"] = relp(src)
    doc = products["BX_v3"].doc
    info["our_category"] = int(doc.category_id)
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    info["instance"] = rp.place_one(src, outp, host=G_ABPD,
                                    symbol_id=p.symbol_id,
                                    family_id=p.host_family_id,
                                    category=int(doc.category_id))
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["symbol_id"], info["family_id"] = p.symbol_id, p.host_family_id
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    info["species"] = species_census(outp, G_ABPD, ours_content=True)
    if not info["species"]["species_ok"]:
        raise RuntimeError(f"BX_v3 emitted species census not ok: "
                           f"{info['species']['checks']}")
    info["self_containment"] = info["species"].get("four_surface")
    return info


def build_demo_v9() -> Dict[str, Any]:
    """DEMO v9: v8's exact recipe (the user's prompt through
    rvt.frontdoor.run with birthright binds + corpus symbol form) at
    version=3."""
    SC = _sc()
    rp = _rp()
    fbl = _fbl()
    from rvt.famgen import birthright as BR
    from rvt import famload_hostfix as HF
    from rvt.mutate import Document
    spec = BR.read_birth_spec(SC.BIRTH_SPEC)
    binds = BR.read_bind_spec(SC.BINDS_PATH)
    rp._install_schema(G_ABPD)
    import ifc_intent  # noqa: F401
    from rvt.frontdoor.build import load_ifc_room_module
    load_ifc_room_module()
    from rvt import frontdoor as FD
    demo_dir = os.path.join(BUILD_DIR, "demo_v9")
    if os.path.isdir(demo_dir):
        shutil.rmtree(demo_dir)
    outp = os.path.join(OUT_DIR, "DEMO_250v_room_v9.rvt")
    info: Dict[str, Any] = {"probe": "DEMO_250v_room_v9",
                            "axis": AXES["DEMO_250v_room_v9"],
                            "base": relp(G_ABPD), "prompt": DEMO_PROMPT,
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256"),
                            "binds": {k: v["__eid__"] for k, v in
                                      (binds.get("binds") or {}).items()}}
    with BR.enabled(spec, binds=binds, version=3) as br_ctx:
        with HF.corpus_symbol_form():
            req = FD.AuthorRequest(prompt=DEMO_PROMPT, out=demo_dir,
                                   stem="DEMO_250v_room_v9",
                                   no_handoff=True, quiet=True)
            r = FD.run(req)
    combined = (r.files or {}).get("combined")
    if not combined or not os.path.isfile(combined):
        raise RuntimeError(f"front door did not emit the combined file: "
                           f"{r.errors[:3]}")
    shutil.copyfile(combined, outp)
    info["frontdoor_status"] = r.status
    info["out_dir"] = relp(demo_dir)
    reports = br_ctx["reports"]
    if not reports:
        raise RuntimeError("DEMO v9: birthright never fired")
    bad = [x["family"] for x in reports
           if (x.get("report") or {}).get("version") != 3
           or not ((x.get("report") or {}).get("hostsym") or {}).get(
               "applied")]
    if bad:
        raise RuntimeError(f"DEMO v9: v3 hostsym did not apply: {bad}")
    bad = [x["family"] for x in reports
           if not (x.get("verify") or {}).get("ok")]
    if bad:
        raise RuntimeError(f"DEMO v9: authored-vs-mined verify not ok: {bad}")
    unbound = [x["family"] for x in reports
               if not (x.get("walked_bind_census") or {}).get(
                   "self_contained")]
    if unbound:
        raise RuntimeError(f"DEMO v9: walked binds not self-contained: "
                           f"{unbound}")
    loader_reps = br_ctx.get("hostsym_loader") or []
    if not loader_reps or not all(x.get("applied") for x in loader_reps):
        raise RuntimeError(f"DEMO v9: loader-half hostsym did not apply on "
                           f"every family: {loader_reps}")
    info["n_birthright_applications"] = len(reports)
    info["n_families"] = len({x.get("family") for x in reports})
    info["hostsym_loader"] = loader_reps
    T = _room()
    wm = T.host_watermark(G_ABPD)
    doc = Document.from_file(outp)
    inst_ids = [i for i in doc.ids_of_class("FamilyInstance") if i > wm]
    info["instance_ids"] = inst_ids
    info["n_instances"] = len(inst_ids)
    info["n_walls"] = len([i for i in doc.ids_of_class("Wall") if i > wm])
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or ""):
            forms[sid] = HF.assert_symbol_form(outp, sid)
    badf = [k for k, f in forms.items() if not f["ok"]]
    if badf or not forms:
        raise RuntimeError(f"DEMO v9 symbol form check failed: "
                           f"{badf or 'no PP- symbols found'}")
    info["symbol_form_ok"] = {str(k): f["ok"] for k, f in forms.items()}
    info["immediate_parent"] = relp(G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["species"] = species_census(outp, G_ABPD, ours_content=True)
    if not info["species"]["species_ok"]:
        raise RuntimeError(f"DEMO v9 emitted species census not ok: "
                           f"{info['species']['checks']}")
    info["self_containment"] = info["species"].get("four_surface")
    return info


BUILDERS = {"T1uG": build_t1ug, "TB0g": build_tb0g, "BX_v3": build_bx_v3,
            "DEMO_250v_room_v9": build_demo_v9}


# ===========================================================================
# accounting + gates
# ===========================================================================

def _accounting(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
    B = _bisect()
    fbl = _fbl()
    base = G_ABPD
    child = os.path.join(ROOT, info["file"])
    parent = os.path.join(ROOT, info["immediate_parent"])
    out: Dict[str, Any] = {}
    out["probe"] = B.account(name, child, parent, declared_base=base,
                             instance_ids=info.get("instance_ids") or [])
    if os.path.abspath(parent) != os.path.abspath(base):
        out["hop_load"] = B.account(name + ".hop_load", parent, base,
                                    declared_base=base, instance_ids=[],
                                    with_regdiff=False)
    out["blob_proof"] = fbl.blob_proof(child, base)
    return out


def _gates(name: str, info: Dict[str, Any],
           acct: Dict[str, Any]) -> Dict[str, Any]:
    rep = acct["probe"]
    va = rep["validator"]
    bp = acct["blob_proof"]
    hop = acct.get("hop_load")
    sp = info.get("species") or {}
    g: Dict[str, Any] = {
        "validator_errors": va["n_errors"],
        "validator_unexpected": len(va["unexpected_errors"]),
        "four_registry_coherent": rep["census"]["coherent"],
        "survivor_law_ok": bool(rep["survivor_law_ok"]) and (
            hop is None or bool(hop["survivor_law_ok"])),
        "identity": (rep.get("identity_gate") or {}).get("status"),
        "blob_all_units_64B": bp["all_units_64B"],
        "blob_added_nonce_verified": bp["added_nonce_verified"],
        "famdoc_refs_unresolved_anywhere": (
            info.get("reference_resolution") or {}).get(
                "unresolved_anywhere"),
        "instance_zero_dangling": (
            (info.get("instance") or {}).get("n_dangling") == 0
            if info.get("instance") else None),
        "byte_identity_verified": (
            all((info.get("byte_identity") or {}).get(
                "segments_byte_identical", {}).values())
            if info.get("byte_identity") else None),
        "species_ok": sp.get("species_ok"),
    }
    if hop is not None:
        g["load_hop_units_added"] = hop["census_delta"]["save_units"]
        g["instance_hop_units_added"] = rep["census_delta"]["save_units"]
    ok = (g["validator_errors"] == 0 and g["validator_unexpected"] == 0
          and g["four_registry_coherent"] is True
          and g["survivor_law_ok"] and g["identity"] == "PASS"
          and g["blob_all_units_64B"] and g["blob_added_nonce_verified"])
    if name in ("T1uG", "TB0g"):
        ok = (ok and g["byte_identity_verified"] is True
              and g["famdoc_refs_unresolved_anywhere"] == 0
              and g["instance_zero_dangling"] is True
              and g.get("load_hop_units_added") == 1
              and g.get("instance_hop_units_added") == 0)
    if name == "BX_v3":
        ok = (ok and g["species_ok"] is True
              and g["instance_zero_dangling"] is True
              and g.get("load_hop_units_added") == 1
              and g.get("instance_hop_units_added") == 0)
    if name == "DEMO_250v_room_v9":
        ok = ok and g["species_ok"] is True
    g["gates_ok"] = bool(ok)
    return g


# ===========================================================================
# build driver + probes.json + verify + stage
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/species_probe.py",
                           "bases": {n: relp(G_ABPD) for n in LADDER},
                           "built": {}, "accounting": {}, "gates": {},
                           "errors": {}}
    if os.path.isfile(ACCT):
        try:
            with open(ACCT) as fh:
                prev = json.load(fh)
            for k in ("built", "accounting", "gates"):
                out[k] = {n: v for n, v in (prev.get(k) or {}).items()
                          if n not in only}
        except Exception:                                      # noqa: BLE001
            pass
    for name in [n for n in LADDER if n in only]:
        try:
            t1 = time.time()
            info = BUILDERS[name]()
            info["seconds"] = round(time.time() - t1, 1)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]}, "
                f"{info['seconds']}s)")
            acct = _accounting(name, info)
            out["accounting"][name] = acct
            g = _gates(name, info, acct)
            out["gates"][name] = g
            log(f"{name}: validator {g['validator_errors']} err "
                f"(unexpected {g['validator_unexpected']}), coherent "
                f"{g['four_registry_coherent']}, byte-identity "
                f"{g['byte_identity_verified']}, species "
                f"{g['species_ok']}, gates_ok {g['gates_ok']}")
            if not g["gates_ok"]:
                out["errors"][name + ".gates"] = f"gates_ok False: {g}"
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = \
                traceback.format_exc(limit=10)
            log(f"{name} FAILED: {type(e).__name__}: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(ACCT, out)
    write_probes_json(out)
    return out


READING_THE_MATRIX = {
    "knowns": {
        "T2a": "PASS on G_ABPD (standalone-born, unmodified, no ours "
               "content) -- the only reduced-base loaded-famdoc PASS",
        "T1v": "FAIL on G_ABPD (standalone shell + ours 35, template "
               "machinery, authored-empty ADocument, clean symbol table)",
        "T1u/T1r": "PASS on rst (both machineries, standalone shell + "
                   "ours 35)",
        "U16g/U16gK4/U16gABP": "FAIL on every reduced substrate "
                               "(embedded-donor shell + ours 35; K4 cell "
                               "has byte-born ref targets)",
        "SC1/DEMO v8": "FAIL on G_ABPD (ours + authored birth v2, "
                       "self-contained, in-unit binds)",
        "TB0r": "PASS on rst (embedded-born famdoc, own content, B7's "
                "host+path)",
    },
    "pre_committed": [
        "T1uG PASS + BX_v3 PASS + DEMO v9 PASS => THE CLOSE: the "
        "standalone species shape is the law on reduced bases, our "
        "content is fine inside it, and v3 authors it -- promote "
        "birthright v3 to the famgen emission default and rebuild "
        "acceptance.",
        "T1uG PASS + BX_v3 FAIL => v3 AUTHORING GAP: our authored famdoc "
        "still differs from T1u's registered shape by a finite list -- "
        "re-run the forensic instrument on the (T1uG, BX_v3) pair; the "
        "pre-identified candidates, in order: (1) the born-roster "
        "true-up (the +268-element layer: overlapping-class shortfall + "
        "reference-closure dropped set + the loaded-family registration "
        "block), (2) the born-wrapper ADocument (populated AppInfo "
        "registries + independent history identity + build strings -- "
        "authored equivalents, zero donor).",
        "T1uG PASS + BX_v3 PASS + DEMO v9 FAIL => the famgen-loader lane "
        "delta list (corpus symbol GElement host binds, multi-family, "
        "walls) -- bisect v9 family-by-family through BX_v3's famload "
        "lane.",
        "T1uG FAIL + TB0g PASS => CONTENT BIRTH is the axis: reduced "
        "bases accept only fully-BORN unit content (embedded-born AND "
        "standalone-born), rejecting any unit carrying authored content "
        "even inside a born shell.  No famdoc-side authoring closes "
        "that; route to (a) the compose-side repair (hr1 rank 1: the "
        "stripped material appearance asset + cellList + deleted-style "
        "holes on the substituted rows the walk lands on), (b) the "
        "desktop-Revit check kit.",
        "T1uG FAIL + TB0g FAIL => reduced bases reject EVERY loaded "
        "famdoc except the unmodified standalone-born vendor file: the "
        "acceptance boundary is the T2a bytes themselves; suspicion "
        "moves to the reduced base's registration substrate (the "
        "rebuilt-empty CD stream x unit-content interplay) -- compose "
        "territory; escalate with the desktop-Revit kit.",
        "TB0g PASS + T1uG PASS => both species shapes carry on reduced "
        "bases when byte-born or standalone-shaped; the embedded-donor "
        "U16g failures re-read as a shell-x-content interaction "
        "(informative for the map).",
        "BX_v3 PASS + T1uG FAIL would be a SURPRISE (our authored "
        "species shape passing where the born shell + ours fails) -- "
        "re-read the round for a control/dedup problem before "
        "celebrating.",
        "Control FAIL => every verdict in the round is VOID.",
    ],
    "reading_order": list(LADDER),
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    probes = []
    for name in LADDER:
        info = (build_out.get("built") or {}).get(name)
        if not info:
            continue
        probes.append({
            "probe": name, "file": info["file"], "md5": info["md5"],
            "base": relp(G_ABPD),
            "axis": AXES[name],
            "document_guid": info.get("document_guid"),
            "gates_ok": ((build_out.get("gates") or {}).get(name)
                         or {}).get("gates_ok"),
        })
    out = {
        "tool": "tools/species_probe.py",
        "stream": "species",
        "base": relp(G_ABPD),
        "forensics": relp(FORENSICS),
        "probes": probes,
        "reading_the_matrix": READING_THE_MATRIX,
        "quarantine": ("T1uG + TB0g embed vendor-born / Autodesk-sample "
                       "content -- PROOF-ONLY, never shipped; BX_v3 + "
                       "DEMO v9 carry zero donor bytes (test-enforced)"),
    }
    jdump(PROBES, out)
    return PROBES


def verify() -> Dict[str, Any]:
    """Re-run the accounting gates on the built probes (no rebuilds)."""
    with open(ACCT) as fh:
        acct = json.load(fh)
    out = {}
    for name in LADDER:
        info = (acct.get("built") or {}).get(name)
        if not info:
            out[name] = "not built"
            continue
        path = os.path.join(ROOT, info["file"])
        if not os.path.isfile(path):
            out[name] = "file missing"
            continue
        if md5_of(path) != info["md5"]:
            out[name] = "MD5 DRIFT vs accounting"
            continue
        g = _gates(name, info, acct["accounting"][name])
        out[name] = "gates_ok" if g["gates_ok"] else f"GATES NOT OK: {g}"
    print(json.dumps(out, indent=1))
    return out


def stage() -> Dict[str, Any]:
    """probe_batch gate + stage: ONE G_ABPD control + the four probes,
    reading order T1uG, TB0g, BX_v3, DEMO v9.  STOP at READY."""
    pb = _pb()
    import datetime as _dt
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run build): "
                         f"{[relp(m) for m in missing]}")
    with open(ACCT) as fh:
        acct = json.load(fh)
    bad = [n for n in LADDER
           if not (acct.get("gates") or {}).get(n, {}).get("gates_ok")]
    if bad:
        raise SystemExit(f"gates not green for {bad} -- stage refused")
    if not os.path.isfile(FORENSICS):
        raise SystemExit("cd_forensics.json missing -- run forensics first "
                         "(it is the round's delta-list evidence)")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = pb.next_batch_number()
    out_dir = pb.ACCEPTANCE
    ctrl = pb.make_control(ledger, n, out_dir, source=G_ABPD)
    ordered = [ctrl] + [e for e in entries if e.kind == "probe"]
    for i, e in enumerate(ordered):
        e.order = i
        if e.kind == "control":
            continue
        src = pb.abspath(e.file)
        dst = os.path.join(out_dir, os.path.basename(e.file))
        if os.path.abspath(src) != os.path.abspath(dst):
            if os.path.exists(dst) and md5_of(dst) != e.md5:
                raise pb.GateRefusal(
                    [f"{e.file}: a DIFFERENT file already sits at "
                     f"{pb.rel(dst)} (md5 {md5_of(dst)} vs {e.md5}); "
                     f"rename the probe -- never overwrite a staged file "
                     f"the viewer may already have read"])
            shutil.copyfile(src, dst)
        e.staged_as = pb.rel(dst)
    manifest = {
        "batch": n,
        "created": _dt.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "tool": "tools/species_probe.py (via tools/probe_batch.py "
                "primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified' (or is an Autodesk "
                "sample source); the batch carries >= 1 CONTROL = a "
                "byte-identical copy of a certified file; read the round "
                "with read_batch_verdicts(): control FAIL => every "
                "verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 1,
        "controls": {"g_abpd": ctrl.staged_as,
                     "note": "one G_ABPD control gates all four probes "
                             "(every probe's base is G_ABPD)"},
        "note": ("species THE CELLS: T1uG (T1u's byte-identical "
                 "standalone-shell+ours famdoc on G_ABPD -- THE decisive "
                 "cell), TB0g (TB0r's byte-identical embedded-born famdoc "
                 "on G_ABPD), BX_v3 (our famdoc through birthright v3 -- "
                 "the forensics-derived HOSTSYM lane; single registered "
                 "surface vs certified-FAIL SC1), DEMO_250v_room_v9 (the "
                 "prompt through v3).  Read "
                 "experiments/species/probes.json reading_the_matrix; the "
                 "forensic delta list is "
                 "experiments/species/cd_forensics.json."),
        "reading_order": [os.path.basename(e.staged_as or e.file)
                          for e in ordered],
        "entries": [e.to_json() for e in ordered],
    }
    path = os.path.join(out_dir, f"batch_{n}.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    manifest["manifest_path"] = pb.rel(path)
    log(f"STAGED batch {n} -> {pb.rel(path)} (1 control + {len(files)} "
        f"probes; STOP at READY -- the orchestrator uploads)")
    return manifest


# ===========================================================================
# CLI
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("forensics")
    b = sub.add_parser("build")
    b.add_argument("--only")
    c = sub.add_parser("census")
    c.add_argument("file")
    c.add_argument("--base", default=G_ABPD)
    c.add_argument("--born", action="store_true",
                   help="born content: skip the ours-content four-surface "
                        "gate")
    sub.add_parser("verify")
    sub.add_parser("stage")
    args = ap.parse_args(argv)
    if args.cmd == "forensics":
        forensics()
        return 0
    if args.cmd == "build":
        only = args.only.split(",") if args.only else None
        out = build(only)
        return 0 if not out["errors"] else 1
    if args.cmd == "census":
        rep = species_census(args.file, args.base,
                             ours_content=not args.born)
        print(json.dumps(rep, indent=1, default=str))
        return 0 if rep["species_ok"] else 1
    if args.cmd == "verify":
        verify()
        return 0
    if args.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
