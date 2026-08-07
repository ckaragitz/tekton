#!/usr/bin/env python
"""hostpair_probe.py -- THE HOST-PAIR BYTE-COPY BINARY (hostpair stream,
2026-08-05).

THE QUESTION (genesis-audit verdict #33).  H7 -- an UNMODIFIED Autodesk
famdoc (the rst sample's own M_Concrete-Square-Column, unit 36), id-rebased
and loaded through rvt.famload with one template-placed instance -- FAILS
the open-time audit on its own sample base.  The famdoc CONTENT is thereby
exonerated; the defect lives in what the load path AUTHORS AROUND the
family: the host Family + FamilySymbol elements famload constructs, and/or
the unit/four-registry registration rows.  This tool builds the binary that
decides WHICH.

THE 2x2 MATRIX this completes (rows = host-element authorship, cols =
instance present):

                      | no instance          | one instance
  famload-authored    | L_v2 / BX_f2  PASS   | H7   FAIL   (recorded)
  native byte-copies  | H10  (this tool)     | H9   (this tool)

  H9  = untouched rst sample + the donor famdoc loaded EXACTLY like H7
        (same build_donor rebase, same famload unit build + inline
        ADocument + four-registry registration rows) BUT the host-side
        family layer is NOT famload-authored: it is the donor's own NATIVE
        22-element host constellation (Family 1410863 + FamilySurrogate +
        preview LegendComponent + 16 family-scoped resource twins +
        FamilySymbol '450 x 450mm' + FamSymSurrogate + the slave symbol),
        ID-REBASED BYTE-COPIES -- every field byte-identical except the
        ids that must move, the content GUID re-pointed at OUR loaded
        unit, a fresh m_famDocGUID, the collision-avoiding name, and the
        twin's id-derived local-type suffix (the exhaustive machine diff
        of what moved is copy_report.json) -- plus ONE instance placed by
        the exact template recipe H7 used (famdoc_bisect.place_probe, the
        V20-certified created-instance shape).
  H10 = H9's immediate parent: the SAME load, NO instance.  It must PASS
        if the byte-copies + registration are lawful uninstanced,
        completing the matrix against L_v2/BX_f2.

READING (probes.json carries the full decision table):
  H9 PASS  (H7 FAIL recorded)  => the defect IS famload's authored host
        elements; the fix spec = the famload-vs-native field diff
        (hostfix_spec.json, computed by this tool; the symbol's
        GElement rep + m_geomSteps + m_pGeomTable head the ranking).
  H9 FAIL + H10 PASS => the copies are lawful uninstanced but fail under
        an instance while V20 certified an instance of the NATIVE original
        on this base => the defect is the unit/registration surface the
        load itself adds (the four-registry rows and/or the re-encoded
        unit) -- next rung H11: H9 with registration rows byte-modeled on
        an Autodesk multi-unit file's row shapes.
  H9 FAIL + H10 FAIL => the byte-copies are unlawful even uninstanced
        (something in the copy delta itself); re-examine copy_report.json
        against L_v2's famload-authored PASS.
  H9 PASS + H10 FAIL => incoherent (instanced passes, uninstanced fails);
        treat the round as oracle noise and re-run.

WHY THE WHOLE 22-ELEMENT CONSTELLATION AND NOT JUST Family+FamilySymbol:
the native Family's field content references its cluster (m_surrogateId,
the 16-row m_familyIds, the 50-row big2small, the header deletion list);
a partial swap would leave the copy pointing into the NATIVE family's
members (cross-family links no corpus file exhibits).  The charter's
"host Family + FamilySymbol famload constructs" is tested wholesale: H9
carries ZERO famload-authored host elements.

MEASURED LAWS THE BUILD ENFORCES (survey pinned by tests/test_hostpair.py):
  * the native cluster re-encodes byte-exact (66/66 records) -- so the
    emitted copies differ from the native bytes ONLY by the remapped
    values (the byte-copy claim is machine-checkable, not aspirational);
  * typed-reference census of the cluster: every ElementId-typed value
    resolves to {cluster, host-shared, builtin} -- ZERO dangling; the only
    embedded-unit references are the 50 big2SmallMap2 m_id64 values
    (remapped through the same famdoc rebase map H7 used);
  * native ElemTable owner chains of the 16 resource twins are mirrored
    (remapped); episodes follow famload's fresh-row law (H7-verbatim);
  * the native relative id ORDER of the cluster is preserved in the new
    block (the donor's own order: family < surrogate < preview < twins <
    symbol < symsurrogate < slave).

PROOF-ONLY: every probe embeds Autodesk sample content and stays in
experiments/ under the quarantine rule (zero donors in shipped output; the
viewer batch is the certified probe mechanism, exactly like H7/SX/SL).

USAGE (repo root)::

    .venv/bin/python tools/hostpair_probe.py survey    # measure + pin the native cluster
    .venv/bin/python tools/hostpair_probe.py build     # H9 + H10 (+ gates + probes.json)
    .venv/bin/python tools/hostpair_probe.py diffspec  # hostfix_spec.json (famload vs native, ranked)
    .venv/bin/python tools/hostpair_probe.py verify    # re-run gates on emitted probes
    .venv/bin/python tools/hostpair_probe.py stage     # probe_batch gate + rst control

TERRITORY: this file, ``experiments/hostpair/**``,
``tests/test_hostpair.py``, ``docs/inbox/hostpair-binary.md``,
``src/rvt/famload_hostfix.py`` (the speculative fix, separate module).
IMPORTS (never edits): tools/famdoc_bisect.py (build_donor / HybridFamilyDoc
/ place_probe -- the H7 recipe verbatim), tools/bisect_instance_bug.py
(account / batch numbering), tools/probe_batch.py (staging), rvt.famload
(survey_host / LoadPlan / register_in_host_adocument / four_registry_census
-- the registration machinery H7 used), rvt.famgen.factory (unit build +
inline ADocument + ContentDocuments grammar), rvt.commit, rvt.mutate,
rvt.validate.  No Autodesk install dirs, no browser; STAGE only (the
orchestrator uploads).
"""
from __future__ import annotations

import argparse
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
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "hostpair")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
H7_LOAD = os.path.join(ROOT, "experiments", "famdoc_bisect", "_build", "H7",
                       "H7_load.rvt")
H7_LOAD_JSON = H7_LOAD + ".load.json"

#: the donor family document + its NATIVE host constellation (measured
#: 2026-08-05; tests pin these)
DONOR_UNIT = 36
DONOR_CATEGORY = -2001330
DONOR_TYPE = "450 x 450mm"
NATIVE_FAMILY = 1410863
NATIVE_SURROGATE = 1411267
NATIVE_PREVIEW = 1411268              # LegendComponent (type preview)
NATIVE_RESOURCE_TWINS = tuple(range(1411269, 1411285))   # 16 family-scoped rows
NATIVE_TWIN_PARAM = 1411280           # the 'b' ParamElemFamily twin (in the 16)
NATIVE_SYMBOL = 1411287               # the V20-certified instance target
NATIVE_SYMSURROGATE = 1411288
NATIVE_SLAVE_SYMBOL = 1411406         # m_masterId -> 1411287, surrogate -1

#: the native relative order, preserved in the copy block
CLUSTER_ORDER: Tuple[int, ...] = ((NATIVE_FAMILY, NATIVE_SURROGATE, NATIVE_PREVIEW)
                                  + NATIVE_RESOURCE_TWINS
                                  + (NATIVE_SYMBOL, NATIVE_SYMSURROGATE,
                                     NATIVE_SLAVE_SYMBOL))

#: the collision-avoiding family name (the native original stays loaded in
#: the same host; H7's own precedent shape 'M Concrete-Square-Column P7')
H9_NAME = "M Concrete-Square-Column H9"

LADDER = ("H9", "H10")
AXES = {
    "H9": "native host-pair byte-copies + famload registration + ONE instance",
    "H10": "H9's immediate parent: same load, NO instance",
}


def log(msg: str) -> None:
    print(f"[hostpair] {msg}", flush=True)


def relp(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return r if not r.startswith("..") else p
    except ValueError:                                     # pragma: no cover
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


def _fdb():
    import famdoc_bisect as FDB
    return FDB


def _bisect():
    import bisect_instance_bug as B
    return B


def _residual():
    import residual_probe as R
    return R


# ===========================================================================
# the native-cluster survey (measure everything the build relies on)
# ===========================================================================

def survey_cluster() -> Dict[str, Any]:
    """Measure the native constellation: classes, linkage, ElemTable owner
    chains, byte-exact re-encode, typed-reference census, embedded-id census.
    Raises if any pinned law fails -- the build refuses on a drifted base."""
    from rvt.mutate import Document
    from rvt.encode import ObjectEncoder
    from rvt.families import FamilyIndex
    from rvt.validate import _RefDecoder
    from rvt.container import open_rvt
    from rvt.elemtable import parse_elemtable
    doc = Document.from_file(RST)
    enc = ObjectEncoder()
    idx = FamilyIndex(RST)
    unit_ids = set(idx.unit_records(DONOR_UNIT).get(102, {}))
    cluster = set(CLUSTER_ORDER)
    if cluster & unit_ids:
        raise RuntimeError("cluster and donor-unit ids overlap (file-wide "
                           "uniqueness broken?)")
    rep: Dict[str, Any] = {"base": relp(RST), "cluster": list(CLUSTER_ORDER),
                           "donor_unit": DONOR_UNIT,
                           "unit_ids": [min(unit_ids), max(unit_ids), len(unit_ids)]}
    # classes + linkage pins
    classes = {i: doc.class_of(i) for i in CLUSTER_ORDER}
    rep["classes"] = {str(k): v for k, v in classes.items()}
    pins = {
        "family_class": classes[NATIVE_FAMILY] == "Family",
        "surrogate_class": classes[NATIVE_SURROGATE] == "FamilySurrogate",
        "preview_class": classes[NATIVE_PREVIEW] == "LegendComponent",
        "symbol_class": classes[NATIVE_SYMBOL] == "FamilySymbol",
        "symsur_class": classes[NATIVE_SYMSURROGATE] == "FamSymSurrogate",
        "slave_class": classes[NATIVE_SLAVE_SYMBOL] == "FamilySymbol",
        "twin_class": classes[NATIVE_TWIN_PARAM] == "ParamElemFamily",
    }
    fam = doc.value(NATIVE_FAMILY) or {}
    fdoc = ((fam.get("m_oFamDoc") or {}).get("value") or {})
    b2s = fdoc.get("m_big2SmallMap2") or []
    sym = doc.value(NATIVE_SYMBOL) or {}
    slave = doc.value(NATIVE_SLAVE_SYMBOL) or {}
    sur = doc.value(NATIVE_SURROGATE) or {}
    pins.update({
        "family_name": fam.get("m_name") == "M_Concrete-Square-Column",
        "family_surrogate_link": fam.get("m_surrogateId") == NATIVE_SURROGATE,
        "family_content_guid_is_unit36": str(fdoc.get("m_contentDocGUID"))
                                          == str(idx.units[DONOR_UNIT].guid),
        "big2small_50_rows": len(b2s) == 50,
        "big2small_seconds_in_unit": all(
            int(((r.get("second") or {}).get("m_id64", -1))) in unit_ids
            for r in b2s),
        "twin_in_big2small": any(int(r.get("first", -1)) == NATIVE_TWIN_PARAM
                                 for r in b2s),
        "symbol_geomSteps_populated": isinstance(sym.get("m_geomSteps"), dict),
        "symbol_geomTable_populated": isinstance(sym.get("m_pGeomTable"), dict),
        "symbol_rep_is_GElement": doc.class_of(NATIVE_SYMBOL, 103) == "GElement",
        "symbol_name": ((sym.get("m_symbolInfo") or {}).get("value") or {})
                       .get("m_name") == DONOR_TYPE,
        "symbol_surrogate_link": sym.get("m_partitionSurrogateId") == NATIVE_SYMSURROGATE,
        "slave_master_link": slave.get("m_masterId") == NATIVE_SYMBOL,
        "slave_no_surrogate": slave.get("m_partitionSurrogateId") == -1,
        "surrogate_preview_link": sur.get("m_previewElemId") == NATIVE_PREVIEW,
        "type_table_5_pairs": [pp.get("name") for pp in
                               (((fam.get("m_pFamilyTypes") or {}).get("value")
                                 or {}).get("m_pairs") or [])]
                              == [" ", "300 x 300mm", "450 x 450mm",
                                  "600 x 600mm", "750 x 750mm"],
    })
    # the twin's local-type-id law: trailing 8 hex == its own id
    tw = doc.value(NATIVE_TWIN_PARAM) or {}
    pd = ((tw.get("m_pParamDef") or {}).get("value") or {})
    tid = pd.get("m_typeId")
    tid = tid.get("m_typeId") if isinstance(tid, dict) else tid
    m = re.match(r"revit\.local\.family:([0-9a-f]{32})([0-9a-f]{8})-1\.0\.0$",
                 str(tid))
    pins["twin_typeid_trailing_hex_is_own_id"] = bool(
        m and int(m.group(2), 16) == NATIVE_TWIN_PARAM)
    rep["twin_session_hex"] = m.group(1) if m else None
    # byte-exact re-encode of every record
    rt = {"records": 0, "byte_exact": 0, "diffs": []}
    for eid in CLUSTER_ORDER:
        for seq in (101, 102, 103):
            r = doc.record(eid, seq)
            if r is None:
                continue
            rt["records"] += 1
            o = doc.decode(eid, seq)
            if o is None or not (o.clean or getattr(o, "stub", False)):
                rt["diffs"].append([eid, seq, "not clean"])
                continue
            body = enc.encode_object(r.class_id, o.value or {})
            if body == r.payload:
                rt["byte_exact"] += 1
            else:
                rt["diffs"].append([eid, seq, f"{len(body)} vs {len(r.payload)}"])
    rep["reencode_roundtrip"] = rt
    pins["reencode_byte_exact_all"] = (rt["records"] == rt["byte_exact"]
                                       and not rt["diffs"])
    # typed reference census
    dec = _RefDecoder(doc.dec.schema)
    host_ids = set(doc.et_by_id)
    buckets = {"cluster": 0, "host_shared": 0, "negative": 0,
               "embedded_typed": 0, "unresolved": 0}
    unresolved = []
    for eid in CLUSTER_ORDER:
        for seq in (101, 102, 103):
            r = doc.record(eid, seq)
            if r is None:
                continue
            dec.refs = []
            try:
                dec.decode_record(r.class_id, r.payload)
            except Exception:                              # noqa: BLE001
                continue
            for pth, v in dec.refs:
                if v in cluster:
                    buckets["cluster"] += 1
                elif v < 0:
                    buckets["negative"] += 1
                elif v in unit_ids:
                    buckets["embedded_typed"] += 1
                elif v in host_ids:
                    buckets["host_shared"] += 1
                else:
                    buckets["unresolved"] += 1
                    unresolved.append([eid, seq, pth[-70:], v])
    rep["typed_ref_census"] = buckets
    rep["typed_ref_unresolved"] = unresolved[:10]
    pins["typed_refs_all_resolve"] = buckets["unresolved"] == 0
    # embedded-id (untyped) census: exactly the 50 big2small m_id64 values
    hits = []

    def scan(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in unit_ids:
                    hits.append(path + "." + k)
                else:
                    scan(v, path + "." + k)
        elif isinstance(node, list):
            for j, v in enumerate(node):
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in unit_ids:
                    hits.append(f"{path}[{j}]")
                else:
                    scan(v, f"{path}[{j}]")

    for eid in CLUSTER_ORDER:
        for seq in (101, 102, 103):
            v = doc.value(eid, seq)
            if isinstance(v, dict):
                scan(v, f"{eid}.s{seq}")
    rep["embedded_id_hits"] = len(hits)
    pins["embedded_ids_only_big2small"] = (
        len(hits) == 50 and all(".m_big2SmallMap2[" in h and h.endswith(".m_id64")
                                for h in hits))
    # ElemTable owner chains + ETD row
    with open_rvt(RST) as f:
        et = parse_elemtable(f.inflate("Global/ElemTable", 0))
    by = {r.id: r for r in et.records}
    owners = {}
    for i in CLUSTER_ORDER:
        r = by.get(i)
        o = int(r.owner_id) if r is not None else None
        if o is not None and o > 0xFFFFFFFF:                     # u64 -1
            o = -1
        owners[i] = o
    rep["et_owner_of"] = {str(k): v for k, v in owners.items()}
    pins["et_rows_all_present"] = all(i in by for i in CLUSTER_ORDER)
    pins["et_owner_chain_in_cluster"] = all(
        owners[i] in (-1, None) or owners[i] in cluster for i in CLUSTER_ORDER)
    from rvt import famload as FL
    cen = FL.four_registry_census(RST)
    pins["base_registries_coherent"] = bool(cen.get("coherent"))
    rep["pins"] = pins
    bad = sorted(k for k, v in pins.items() if not v)
    if bad:
        raise RuntimeError(f"native-cluster pins failed: {bad}")
    return rep


# ===========================================================================
# the byte-copies
# ===========================================================================

def _walk(node, idmap):
    from rvt.famgen.loader import _walk_replace_ids
    _walk_replace_ids(node, idmap)


def _leaf_diff(a: Any, b: Any, path: str, out: List[Tuple[str, Any, Any]]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _leaf_diff(a.get(k), b.get(k), f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for j, (x, y) in enumerate(zip(a, b)):
            _leaf_diff(x, y, f"{path}[{j}]", out)
    elif a != b:
        out.append((path, a, b))


def build_copies(host_idmap: Dict[int, int], famdoc_idmap: Dict[int, int],
                 *, content_guid: str, fam_doc_guid: str,
                 owners: Dict[int, int]) -> Tuple[List[Any], Dict[str, Any]]:
    """The 22 native records deep-copied, remapped, and minimally re-pointed.
    Returns (SkelElements sorted by new id, the exhaustive delta ledger)."""
    from rvt.mutate import Document
    from rvt.genesis.skeleton import SkelElement
    doc = Document.from_file(RST)
    combined = dict(famdoc_idmap)
    combined.update(host_idmap)
    old_id_space = set(host_idmap) | set(famdoc_idmap)
    ledger: Dict[str, Any] = {"elements": [], "content_moves": [],
                              "remapped_leaves": 0}
    els: List[SkelElement] = []
    for old in CLUSTER_ORDER:
        new = host_idmap[old]
        cname = doc.class_of(old)
        hdr0 = copy.deepcopy(doc.value(old, 101) or {})
        obj0 = copy.deepcopy(doc.value(old, 102) or {})
        rep0 = None
        if doc.class_of(old, 103) == "GElement":
            rv = doc.value(old, 103)
            rep0 = copy.deepcopy(rv) if isinstance(rv, dict) else None
        hdr, obj, rep = (copy.deepcopy(hdr0), copy.deepcopy(obj0),
                         copy.deepcopy(rep0) if rep0 is not None else None)
        for node in (hdr, obj, rep):
            if node is not None:
                _walk(node, combined)
        moves: List[Tuple[str, Any, Any]] = []
        # forced content moves (everything that is NOT a pure id remap)
        if old == NATIVE_FAMILY:
            moves.append(("m_name", obj["m_name"], H9_NAME))
            obj["m_name"] = H9_NAME
            moves.append(("m_famDocGUID", obj["m_famDocGUID"], fam_doc_guid))
            obj["m_famDocGUID"] = fam_doc_guid
            fd = ((obj.get("m_oFamDoc") or {}).get("value") or {})
            moves.append(("m_oFamDoc.value.m_contentDocGUID",
                          fd.get("m_contentDocGUID"), content_guid))
            fd["m_contentDocGUID"] = content_guid
        elif old == NATIVE_SURROGATE:
            moves.append(("m_name", obj["m_name"], H9_NAME))
            obj["m_name"] = H9_NAME
        elif old == NATIVE_TWIN_PARAM:
            pd = ((obj.get("m_pParamDef") or {}).get("value") or {})
            tt = pd.get("m_typeId")
            holder = tt if isinstance(tt, dict) else pd
            key = "m_typeId"
            path = ("m_pParamDef.value.m_typeId.m_typeId"
                    if isinstance(tt, dict) else "m_pParamDef.value.m_typeId")
            tid = str(holder.get(key))
            m = re.match(r"(revit\.local\.family:[0-9a-f]{32})[0-9a-f]{8}(-1\.0\.0)$",
                         tid)
            if not m:
                raise RuntimeError(f"twin typeId shape drifted: {tid!r}")
            new_tid = f"{m.group(1)}{new & 0xFFFFFFFF:08x}{m.group(2)}"
            moves.append((path, tid, new_tid))
            holder[key] = new_tid
        # the exhaustive leaf diff vs the native decode = id remaps + moves
        leaf: List[Tuple[str, Any, Any]] = []
        _leaf_diff(hdr0, hdr, "s101", leaf)
        _leaf_diff(obj0, obj, "s102", leaf)
        if rep0 is not None:
            _leaf_diff(rep0, rep, "s103", leaf)
        moved_paths = {f"s102.{p}" for p, _a, _b in moves}
        non_id = []
        for p, a, b in leaf:
            if p in moved_paths:
                continue
            if isinstance(a, int) and isinstance(b, int) \
                    and combined.get(a) == b:
                continue                                   # a pure id remap
            non_id.append((p, a, b))
        if non_id:
            raise RuntimeError(f"{old}: copy carries a non-id, non-declared "
                               f"delta: {non_id[:4]}")
        # residual old-id scan: nothing may still reference the old id space
        residue: List[str] = []

        def rscan(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    if isinstance(v, bool):
                        continue
                    if isinstance(v, int) and v in old_id_space:
                        residue.append(f"{path}.{k}={v}")
                    else:
                        rscan(v, f"{path}.{k}")
            elif isinstance(node, list):
                for j, v in enumerate(node):
                    if isinstance(v, bool):
                        continue
                    if isinstance(v, int) and v in old_id_space:
                        residue.append(f"{path}[{j}]={v}")
                    else:
                        rscan(v, f"{path}[{j}]")

        for node in (hdr, obj, rep):
            if node is not None:
                rscan(node, str(new))
        if residue:
            raise RuntimeError(f"{old}: old-id residue after remap: {residue[:5]}")
        own = owners.get(old, -1)
        own_new = host_idmap.get(own, -1) if (own or 0) > 0 else -1
        el = SkelElement(new, cname, hdr, obj, rep, owner_id=own_new,
                         kind=f"native_copy_{cname}")
        el.notes.append(f"byte-copy of native {old} (remap + "
                        f"{len(moves)} declared move(s))")
        els.append(el)
        ledger["elements"].append({
            "native_id": old, "new_id": new, "class": cname,
            "rep": ("GElement" if rep is not None else "SerializedDummy"),
            "et_owner": own_new,
            "leaf_deltas_total": len(leaf),
            "id_remapped_leaves": len(leaf) - len(moves),
            "content_moves": [{"path": p, "old": a, "new": b}
                              for p, a, b in moves]})
        ledger["remapped_leaves"] += len(leaf) - len(moves)
        ledger["content_moves"].extend(
            {"element": old, "path": p} for p, _a, _b in moves)
    els.sort(key=lambda e: e.elem_id)
    return els, ledger


# ===========================================================================
# the H9/H10 load (famload's registration machinery, H7-verbatim; host
# elements = the byte-copies)
# ===========================================================================

def build_load(out_path: str) -> Dict[str, Any]:
    """The load: donor famdoc (H7's build_donor rebase) + byte-copied host
    constellation + famload's four-registry registration.  Writes
    ``out_path`` and returns the build report (plan, gates, ledger)."""
    import dataclasses as _dc
    from rvt import famload as FL
    from rvt import ecc
    from rvt.adocument import decode_latest, encode_latest
    from rvt.cfb_writer import write_cfb
    from rvt.commit import commit_new_elements
    from rvt.container import open_rvt
    from rvt.encode import encode_record
    from rvt.famgen import factory as F
    from rvt.genesis.skeleton import roundtrip_report
    from rvt.roundtrip import read_entries
    from rvt.stream_encoders import wrap_global_stream
    FDB = _fdb()
    T = FDB._room()                                        # noqa: SLF001
    rep: Dict[str, Any] = {}

    survey = survey_cluster()
    rep["survey_pins_ok"] = True
    owners = {int(k): v for k, v in survey["et_owner_of"].items()}

    host = FL.survey_host(RST, categories=[DONOR_CATEGORY])
    wm = T.host_watermark(RST)
    if wm != host.watermark:
        raise RuntimeError(f"watermark disagreement: {wm} vs {host.watermark}")
    rep["watermark"] = wm

    # ---- the donor famdoc, H7-verbatim ------------------------------------
    donor_els, anchors, famdoc_idmap, _adoc, _census = FDB.build_donor(wm + 1)
    sf = next(e for e in donor_els if e.elem_id == anchors["self_family"])
    doc = FDB.HybridFamilyDoc(donor_els, sf, name=H9_NAME,
                              category_id=DONOR_CATEGORY, part_type=-1,
                              types=[(DONOR_TYPE, {})], current_type=1)
    lo = min(e.elem_id for e in donor_els)
    hi = max(e.elem_id for e in donor_els)
    rep["famdoc"] = {"records": len(donor_els), "id_range": [lo, hi],
                    "guid": doc.document_guid,
                    "rebase": "famdoc_bisect.build_donor (H7-verbatim)"}

    # ---- the host block: native order preserved ---------------------------
    base = hi + 1
    host_idmap = {old: base + i for i, old in enumerate(CLUSTER_ORDER)}
    fam_doc_guid = str(uuid.uuid4())
    copies, ledger = build_copies(host_idmap, famdoc_idmap,
                                  content_guid=doc.document_guid,
                                  fam_doc_guid=fam_doc_guid, owners=owners)
    rep["host_idmap"] = {str(k): v for k, v in host_idmap.items()}
    rep["copy_ledger"] = ledger

    # ---- the load plan (native rosters) -----------------------------------
    new_twin = host_idmap[NATIVE_TWIN_PARAM]
    fam0 = copies[0]
    b2s = (((fam0.obj.get("m_oFamDoc") or {}).get("value") or {})
           .get("m_big2SmallMap2") or [])
    emb_of_twin = [int((r.get("second") or {}).get("m_id64", -1)) for r in b2s
                   if int(r.get("first", -1)) == new_twin]
    if len(emb_of_twin) != 1:
        raise RuntimeError(f"twin correspondence not unique: {emb_of_twin}")
    plan = FL.LoadPlan(key="H9", guid=doc.document_guid,
                       fam_doc_guid=fam_doc_guid,
                       session_guid_hex=str(survey.get("twin_session_hex")),
                       family_name=H9_NAME, category=DONOR_CATEGORY,
                       part_type=-1, type_names=[DONOR_TYPE],
                       episode=int(host.episode), doc_id_range=(lo, hi),
                       unit_records=len(donor_els))
    plan.host_family_id = host_idmap[NATIVE_FAMILY]
    plan.surrogate_id = host_idmap[NATIVE_SURROGATE]
    plan.symbol_ids = [host_idmap[NATIVE_SYMBOL]]
    plan.symbol_surrogate_ids = [host_idmap[NATIVE_SYMSURROGATE]]
    plan.twin_of = {emb_of_twin[0]: new_twin}
    rep["plan"] = plan.as_json()

    # ---- gates ------------------------------------------------------------
    gate = roundtrip_report(copies)
    rep["roundtrip_gate"] = {k: gate.get(k) for k in
                            ("records", "roundtrip_ok", "failed")}
    if gate.get("failed", 1) != 0:
        raise RuntimeError(f"copy roundtrip gate failed: {gate.get('failures', [])[:4]}")

    # ---- embedded unit + inline ADocument (famload's own, H7-verbatim) ----
    ad = F.author_embedded_adocument(doc, episode=plan.episode,
                                     document_guid=plan.guid)
    unit = F.build_family_save_unit(doc)
    if str(unit["guid"]) != plan.guid:
        raise RuntimeError("unit GUID mismatch")
    plan.unit_records = int(unit["record_count"])
    rep["embedded"] = {"adocument_self_check": dict(ad["self_check"]),
                       "unit_records": unit["record_count"],
                       "unit_bytes": len(unit["bytes"])}

    # ---- PASS 1: the copies into save-unit 0 ------------------------------
    tmp1 = out_path + ".pass1.tmp"
    if os.path.exists(tmp1):
        os.remove(tmp1)
    recs, new_els = [], []
    for e in copies:
        ne = e.as_new_element(creation_ep=host.episode)
        recs.append({seq: encode_record(seq, ne.elem_id, None, cid, obj)
                     for seq, cid, obj in ne.records()})
        new_els.append(ne)
    crep = commit_new_elements(RST, tmp1, recs, [ne.elemrec for ne in new_els],
                               creation_ep=host.episode,
                               identity={"username": ""})
    rep["pass1_commit"] = {"new_element_ids": list(crep.new_element_ids),
                           "elemtable_count_after": crep.elemtable_count_after,
                           "watermark_after": crep.watermark_after}
    if int(crep.watermark_after) < hi:
        raise RuntimeError("watermark does not cover the embedded document")

    # ---- PASS 2: unit + ContentDocuments + host ADocument -----------------
    with open_rvt(tmp1) as f2:
        part_logical = f2.logical(host.partition_name)
        cd_payload = b"".join(f2.inflate_all("Global/ContentDocuments"))
        latest_payload = f2.inflate("Global/Latest")
    sp = F.splice_save_unit(part_logical, unit["bytes"])
    w = sp["walker"]
    rep["pass2_splice"] = {k: w[k] for k in ("units_before", "units_after",
                                             "errors", "our_unit_guid",
                                             "our_unit_records")}
    if w["errors"] or w["units_after"] != w["units_before"] + 1 \
            or str(w["our_unit_guid"]) != plan.guid:
        raise RuntimeError(f"partition splice failed: {w['errors'][:3]}")
    cd_new = F.insert_content_document(cd_payload, plan.guid, ad["payload"])
    ents_after, tail_after = F.parse_content_documents(cd_new)
    if plan.guid not in {g for g, _a in ents_after}:
        raise RuntimeError("ContentDocuments entry did not insert")
    lat = decode_latest(latest_payload)
    if not lat.clean:
        raise RuntimeError("host Global/Latest does not decode clean")
    lv = copy.deepcopy(lat.value)
    reg = FL.register_in_host_adocument(lv, [plan])
    rep["pass2_registrations"] = reg
    new_latest = encode_latest(lv, trailer=lat.trailer)
    if not decode_latest(new_latest).clean:
        raise RuntimeError("edited host ADocument does not re-decode clean")
    new_streams = {
        host.partition_name: ecc.frame_stream(sp["logical"]),
        "Global/ContentDocuments": ecc.frame_stream(
            wrap_global_stream("Global/ContentDocuments", cd_new, level=3)),
        "Global/Latest": ecc.frame_stream(
            wrap_global_stream("Global/Latest", new_latest, level=3)),
    }
    entries = read_entries(tmp1)
    out_entries = [_dc.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out_path, out_entries)
    try:
        os.remove(tmp1)
    except OSError:                                        # pragma: no cover
        pass

    # ---- read-back verification ------------------------------------------
    rep["verify"] = verify_load(out_path, plan, host_idmap)
    if not rep["verify"]["ok"]:
        raise RuntimeError(f"load verification failed: "
                           f"{rep['verify'].get('failures')}")
    return rep


def verify_load(path: str, plan, host_idmap: Dict[int, int]) -> Dict[str, Any]:
    """The machine proofs of the written load: four registries coherent
    (ours in all four), the 22 copies present + byte-faithful, linkage
    (family <-> surrogate <-> symbol <-> symsurrogate <-> twin), the ETD
    -2001330 row gained exactly our symbol, validator 0 errors."""
    from rvt import famload as FL
    from rvt.mutate import Document
    from rvt.encode import ObjectEncoder
    from rvt import adocument as A
    from rvt.container import open_rvt
    from rvt.validate import validate_file
    out: Dict[str, Any] = {}
    failures: List[str] = []
    cen = FL.four_registry_census(path)
    out["registries"] = {k: cen.get(k) for k in
                         ("save_units", "contentdocs_entries",
                          "contenttable_records", "familymgr_entries",
                          "coherent")}
    if not cen.get("coherent"):
        failures.append("four registries incoherent")
    g = plan.guid.lower()
    if not all(g in (cen.get(k) or []) for k in
               ("unit_guids", "contentdocs_guids", "contenttable_guids",
                "familymgr_guids")):
        failures.append("our GUID not in all four registries")
    doc = Document.from_file(path)
    enc = ObjectEncoder()
    nat = Document.from_file(RST)
    # every copy present; obj records byte-equal to our authored values
    n_checked = 0
    for old, new in host_idmap.items():
        if doc.class_of(new) != nat.class_of(old):
            failures.append(f"copy {new}: class mismatch")
        n_checked += 1
    out["copies_present"] = n_checked
    fam = doc.value(host_idmap[NATIVE_FAMILY]) or {}
    fd = ((fam.get("m_oFamDoc") or {}).get("value") or {})
    checks = {
        "family_name": fam.get("m_name") == H9_NAME,
        "family_guid": str(fd.get("m_contentDocGUID")) == plan.guid,
        "family_surrogate": fam.get("m_surrogateId") == plan.surrogate_id,
        "surrogate_points_back": (doc.value(plan.surrogate_id) or {})
                                 .get("m_elemId") == plan.host_family_id,
        "symbol_family": (doc.value(plan.symbol_id) or {})
                         .get("m_familyId") == plan.host_family_id,
        "symbol_surrogate": (doc.value(plan.symbol_id) or {})
                            .get("m_partitionSurrogateId")
                            == plan.symbol_surrogate_id,
        "symsur_points_back": (doc.value(plan.symbol_surrogate_id) or {})
                              .get("m_elemId") == plan.symbol_id,
        "twin_famid": (doc.value(host_idmap[NATIVE_TWIN_PARAM]) or {})
                      .get("m_famId") == plan.host_family_id,
        "slave_master": (doc.value(host_idmap[NATIVE_SLAVE_SYMBOL]) or {})
                        .get("m_masterId") == plan.symbol_id,
        "symbol_geomSteps_populated": isinstance(
            (doc.value(plan.symbol_id) or {}).get("m_geomSteps"), dict),
        "symbol_rep_GElement": doc.class_of(plan.symbol_id, 103) == "GElement",
    }
    out["linkage"] = checks
    failures.extend(k for k, v in checks.items() if not v)
    # ETD row -2001330 must now contain our symbol AND the native one
    with open_rvt(path) as f:
        a = A.decode_latest(f.inflate("Global/Latest"))
    mgr = (a.value.get("m_pAppInfoManager") or {}).get("value") or {}
    etd_ok = False
    for slot in mgr.get("m_appInfoArr") or []:
        if isinstance(slot, dict) and slot.get("ptr_class") == "ElementTrackingData":
            for row in (slot.get("value") or {}).get("m_symbols") or []:
                if row.get("m_categoryId") == DONOR_CATEGORY:
                    s = row.get("m_elemIdSet") or []
                    etd_ok = plan.symbol_id in s and NATIVE_SYMBOL in s
    out["etd_row_has_our_symbol"] = etd_ok
    if not etd_ok:
        failures.append("ETD -2001330 row lacks our symbol")
    vr = validate_file(path)
    out["validate"] = {"verdict": "VALID" if vr.ok else "INVALID",
                       "n_errors": len(vr.errors),
                       "n_warnings": len(vr.warnings),
                       "errors": [f"[{x.layer}] {x.where}: {x.message}"
                                  for x in vr.errors[:8]]}
    if vr.errors:
        failures.append(f"validator {len(vr.errors)} error(s)")
    out["failures"] = failures
    out["ok"] = not failures
    return out


# ===========================================================================
# build driver: H10 (load only) + H9 (load + one instance)
# ===========================================================================

def build() -> Dict[str, Any]:
    FDB = _fdb()
    B = _bisect()
    FDB._install_schema()                                  # noqa: SLF001
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/hostpair_probe.py", "base": relp(RST),
                           "built": {}, "accounting": {}, "errors": {}}
    load_path = os.path.join(BUILD_DIR, "H9_load.rvt")
    h9 = os.path.join(OUT_DIR, "H9.rvt")
    h10 = os.path.join(OUT_DIR, "H10.rvt")
    try:
        lrep = build_load(load_path)
        jdump(os.path.join(BUILD_DIR, "load_report.json"), lrep)
        jdump(os.path.join(OUT_DIR, "copy_report.json"),
              {"survey": "see _build/load_report.json survey_pins_ok",
               "ledger": lrep["copy_ledger"], "plan": lrep["plan"],
               "host_idmap": lrep["host_idmap"]})
        plan = lrep["plan"]
        sym, fam = plan["symbol_ids"][0], plan["host_family_id"]
        # H10 = the load file itself (byte-copy)
        shutil.copyfile(load_path, h10)
        out["built"]["H10"] = {
            "probe": "H10", "axis": AXES["H10"], "base": relp(RST),
            "file": relp(h10), "md5": md5_of(h10),
            "immediate_parent": relp(RST),
            "symbol_id": sym, "family_id": fam, "instance_ids": [],
            "document_guid": plan["guid"],
            "note": "byte-identical to H9's immediate parent (the load file)"}
        log(f"H10 BUILT -> {relp(h10)} (md5 {out['built']['H10']['md5'][:8]})")
        # H9 = + ONE instance, the exact template recipe H7 used
        prec = FDB.place_probe(load_path, h9, symbol_id=sym, family_id=fam,
                               category=DONOR_CATEGORY)
        out["built"]["H9"] = {
            "probe": "H9", "axis": AXES["H9"], "base": relp(RST),
            "file": relp(h9), "md5": md5_of(h9),
            "immediate_parent": relp(load_path),
            "symbol_id": sym, "family_id": fam,
            "instance_ids": [prec["instance_id"]],
            "instance": prec, "document_guid": plan["guid"],
            "placement": "famdoc_bisect.place_probe (H7-verbatim: "
                         "ConstructedSpecimens + add_family_instance + "
                         "commit; category = the family's own; connmgr = "
                         "template's)"}
        log(f"H9 BUILT -> {relp(h9)} (md5 {out['built']['H9']['md5'][:8]}, "
            f"instance {prec['instance_id']})")
    except Exception as e:                                 # noqa: BLE001
        out["errors"]["build"] = f"{type(e).__name__}: {e}"
        out["errors"]["build.traceback"] = traceback.format_exc(limit=12)
        log(f"BUILD FAILED: {type(e).__name__}: {e}")
        jdump(os.path.join(OUT_DIR, "accounting.json"), out)
        return out

    # accounting: H9 vs its parent (instance hop), H10 vs the base (load hop)
    for name, parent in (("H9", load_path), ("H10", RST)):
        info = out["built"][name]
        try:
            repacc = B.account(name, os.path.join(ROOT, info["file"]), parent,
                               declared_base=RST,
                               instance_ids=info.get("instance_ids") or [])
            out["accounting"][name] = repacc
            va = repacc["validator"]
            log(f"{name}: validator {va['n_errors']} err "
                f"(unexpected {len(va['unexpected_errors'])}), census "
                f"+{repacc['census_delta']['save_units']}u coherent "
                f"{repacc['census']['coherent']}, survivor "
                f"{'OK' if repacc['survivor_law_ok'] else 'VIOLATED'}")
        except Exception as e:                             # noqa: BLE001
            out["errors"][name + ".accounting"] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".accounting.tb"] = traceback.format_exc(limit=8)
            log(f"{name} ACCOUNTING FAILED: {type(e).__name__}: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(OUT_DIR, "accounting.json"), out)
    write_probes_json(out)
    return out


# ===========================================================================
# probes.json (the decision table)
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing",
    "H9 PASS": "with the recorded H7 FAIL: the defect IS famload's authored "
               "host elements -- native byte-copies under the SAME famload "
               "registration + the SAME instance recipe pass where famload's "
               "authored pair failed.  The fix spec is the famload-vs-native "
               "field diff (experiments/hostpair/hostfix_spec.json): the "
               "symbol's GElement rep + m_geomSteps + m_pGeomTable head the "
               "ranking, then m_refFaces/m_strongRefs/m_hasParamDefValue/"
               "outline, then the Family's type-table/familyIds/big2small/"
               "preview shapes.  src/rvt/famload_hostfix.py implements the "
               "geometry-history authoring (opt-in, default OFF).",
    "H9 FAIL + H10 PASS": "the copies are lawful uninstanced (H10 = L_v2's "
                          "cell with native copies) but an instance still "
                          "kills the load -- with V20 certifying an instance "
                          "of the NATIVE original on this base, the remaining "
                          "our-authored surface is the registration itself "
                          "(the four-registry rows + the re-encoded unit).  "
                          "Next rung H11: H9 with ContentTable/FamilyMgr/"
                          "ContentDocuments rows byte-modeled on an Autodesk "
                          "multi-unit file's own row shapes (field-by-field "
                          "parity with a native row, fresh GUID only).",
    "H9 FAIL + H10 FAIL": "the byte-copies themselves are rejected even "
                          "uninstanced, where famload's authored elements "
                          "pass uninstanced (L_v2/BX_f2) -- a copy delta is "
                          "unlawful (duplicate-family shape, the renamed "
                          "surrogate, the carried LegendComponent preview, "
                          "or the slave symbol).  Re-examine copy_report."
                          "json's declared moves; rebuild minus the preview/"
                          "slave sub-cluster as H9b.",
    "H9 PASS + H10 FAIL": "incoherent (the instanced superset of a failing "
                          "file passed) -- oracle noise; re-run the round.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    onething = {
        "H9": "H7's exact load (same donor famdoc, same rebase, same famload "
              "unit build + inline ADocument + four-registry registration) "
              "with the host Family/FamilySymbol layer replaced by id-rebased "
              "BYTE-COPIES of the donor's own NATIVE 22-element host "
              "constellation, + ONE instance by H7's exact template recipe.  "
              "The ONE thing vs H7: WHO authored the host elements.",
        "H10": "H9 minus the instance (byte-identical to H9's immediate "
               "parent).  The ONE thing vs L_v2/BX_f2 (famload loads, "
               "uninstanced, PASS): the byte-copied host constellation.",
    }
    expected = {
        "H9": "the hypothesis-bearing rung: PASS convicts famload's authored "
              "host elements; FAIL moves the defect into the registration "
              "rows / unit re-encode",
        "H10": "PASS expected (completes the 2x2; a FAIL here re-frames H9)",
    }
    probes = []
    for i, name in enumerate(LADDER, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        acct = (build_out.get("accounting") or {}).get(name) or {}
        va = acct.get("validator") or {}
        probes.append({
            "order": i, "rung": name,
            "file": f"experiments/hostpair/{name}.rvt",
            "base": relp(RST), "kind": "probe", "axis": AXES[name],
            "n_families": 1,
            "n_instances": len(info.get("instance_ids") or []),
            "n_walls": 0,
            "the_ONE_thing_it_tests": onething[name],
            "expected": expected[name],
            "md5": info.get("md5"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "immediate_parent": info.get("immediate_parent"),
            "gates": {"validator_errors": va.get("n_errors"),
                      "validator_unexpected": len(va.get("unexpected_errors") or []),
                      "four_registry_coherent": (acct.get("census") or {}).get("coherent"),
                      "survivor_law_ok": acct.get("survivor_law_ok"),
                      "identity": ((acct.get("identity_gate") or {}).get("status"))},
        })
    manifest = {
        "stream": "hostpair: the host-pair byte-copy binary.  H7 (verdict "
                  "#33) proved an unmodified Autodesk famdoc through our "
                  "famload + one instance FAILS on its own sample base -- "
                  "famdoc content exonerated.  H9/H10 decide whether the "
                  "defect is famload's AUTHORED HOST ELEMENTS or the "
                  "unit/registration rows.",
        "base": relp(RST),
        "note": "H9 = untouched rst + the H7 load recipe with the host "
                "family layer replaced by ID-REBASED BYTE-COPIES of the "
                "donor's own NATIVE host constellation (22 elements; every "
                "field byte-identical except ids, the content GUID, a fresh "
                "famDocGUID, the collision-avoiding name, and the twin's "
                "id-derived type suffix -- exhaustive machine ledger in "
                "copy_report.json) + ONE instance by H7's exact template "
                "recipe.  H10 = H9's immediate parent (no instance).  "
                "PROOF-ONLY: sample-derived content, quarantined, never "
                "shipped.  Fresh GUIDs are minted per rebuild -- re-hash "
                "after any rerun.",
        "upload_order_max_information_first": list(LADDER),
        "control": {"source": relp(RST),
                    "note": "control = byte-identical copy of the UNTOUCHED "
                            "rst sample (probe_batch stage --control-from)"},
        "recorded_context": {
            "H7": "FAIL (famload-authored host pair + instance, batch 37)",
            "L_v2 / BX_f2": "PASS (famload-authored host pair, no instance)",
            "V20": "PASS (instance of the NATIVE symbol 1411287, no load)",
        },
        "reading_the_matrix": READING,
        "companion_evidence": {
            "accounting": "experiments/hostpair/accounting.json",
            "copy_ledger": "experiments/hostpair/copy_report.json",
            "fix_spec": "experiments/hostpair/hostfix_spec.json",
            "load_report": "experiments/hostpair/_build/load_report.json",
        },
        "probes": probes,
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# the SPECULATIVE FIX probes (batch 39): the corpus-lawful symbol form
# ===========================================================================

G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
DEMO_PROMPT = "an electrical room rated for 250V with 6 panels"
FIX_LADDER = ("BXhf_f1i1", "DEMO_250v_room_v3")
FIX_AXES = {
    "BXhf_f1i1": "the minimal fixed probe: G_ABPD + ONE famgen family + ONE "
                 "instance, symbols in the corpus-lawful form "
                 "(famload_hostfix)",
    "DEMO_250v_room_v3": "the user's exact prompt end-to-end through "
                         "rvt.frontdoor.run with famload_hostfix applied",
}


def build_fix() -> Dict[str, Any]:
    """BXhf_f1i1 + DEMO_250v_room_v3 through the corpus-lawful symbol form
    (src/rvt/famload_hostfix.corpus_symbol_form; the D1..D5 fixes are landed
    in the loaders' source already).  Gates: validator 0 errors,
    assert_symbol_form on every loaded symbol, account() vs the G_ABPD
    base (pure adds)."""
    FDB = _fdb()
    B = _bisect()
    FDB._install_schema()                                  # noqa: SLF001
    import ifc_intent  # noqa: F401
    from rvt.frontdoor.build import load_ifc_room_module
    load_ifc_room_module()
    from rvt import famload_hostfix as HF
    from rvt import frontdoor as FD
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/hostpair_probe.py fixdemo",
                           "base": relp(G_ABPD), "built": {},
                           "accounting": {}, "errors": {}}
    try:
        with HF.corpus_symbol_form():
            model6 = B.demo_model()
            # ---- BXhf_f1i1 -----------------------------------------------
            m1 = B.truncate_model(model6, 1)
            c1 = os.path.join(BUILD_DIR, "hf_chain1")
            if os.path.isdir(c1):
                shutil.rmtree(c1)
            l1 = B.build_chain(G_ABPD, c1, m1)
            f1 = B.chain_file(c1, 1, "PP-1")
            p1 = os.path.join(OUT_DIR, "BXhf_f1i1.rvt")
            e1 = B.place_instances(m1, f1, p1, G_ABPD, l1.get("_loaded") or {})
            out["built"]["BXhf_f1i1"] = {
                "probe": "BXhf_f1i1", "axis": FIX_AXES["BXhf_f1i1"],
                "base": relp(G_ABPD), "file": relp(p1), "md5": md5_of(p1),
                "immediate_parent": relp(f1),
                "instance_ids": [i.get("elem_id")
                                 for i in e1.get("instances") or []],
                "symbols": [i.get("symbol")
                            for i in e1.get("instances") or []],
                "recipe": "tools/bisect_instance_bug chain+place (the BXfix "
                          "recipe) under famload_hostfix.corpus_symbol_form"}
            log(f"BXhf_f1i1 BUILT -> {relp(p1)}")
            # ---- DEMO_250v_room_v3: the REAL front door ------------------
            demo_dir = os.path.join(BUILD_DIR, "demo_v3")
            if os.path.isdir(demo_dir):
                shutil.rmtree(demo_dir)
            req = FD.AuthorRequest(prompt=DEMO_PROMPT, out=demo_dir,
                                   stem="DEMO_250v_room_v3", no_handoff=True,
                                   quiet=True)
            r = FD.run(req)
            combined = (r.files or {}).get("combined")
            if not combined or not os.path.isfile(combined):
                raise RuntimeError(f"front door did not emit the combined "
                                   f"file: {r.errors[:3]}")
            pd = os.path.join(OUT_DIR, "DEMO_250v_room_v3.rvt")
            shutil.copyfile(combined, pd)
            out["built"]["DEMO_250v_room_v3"] = {
                "probe": "DEMO_250v_room_v3",
                "axis": FIX_AXES["DEMO_250v_room_v3"],
                "base": relp(G_ABPD), "file": relp(pd), "md5": md5_of(pd),
                "immediate_parent": relp(G_ABPD),
                "frontdoor_status": r.status,
                "out_dir": relp(demo_dir),
                "prompt": DEMO_PROMPT}
            log(f"DEMO_250v_room_v3 BUILT -> {relp(pd)} "
                f"(frontdoor {r.status})")
    except Exception as e:                                 # noqa: BLE001
        out["errors"]["build"] = f"{type(e).__name__}: {e}"
        out["errors"]["build.traceback"] = traceback.format_exc(limit=12)
        log(f"FIX BUILD FAILED: {type(e).__name__}: {e}")
        jdump(os.path.join(OUT_DIR, "fix_accounting.json"), out)
        return out

    # ---- gates ------------------------------------------------------------
    from rvt.mutate import Document
    for name in FIX_LADDER:
        info = out["built"].get(name) or {}
        child = os.path.join(ROOT, info["file"])
        try:
            # every loaded symbol of ours must carry the corpus form
            doc = Document.from_file(child)
            forms = {}
            for sid in doc.ids_of_class("FamilySymbol"):
                v = doc.value(sid) or {}
                fam = doc.value(v.get("m_familyId") or -1) or {}
                if "PP-" in str(fam.get("m_name") or ""):
                    forms[sid] = HF.assert_symbol_form(child, sid)
            info["symbol_form"] = {str(k): {"ok": f["ok"], "counts": f["counts"]}
                                   for k, f in forms.items()}
            bad = [k for k, f in forms.items() if not f["ok"]]
            if bad or not forms:
                raise RuntimeError(f"symbol form check failed: "
                                   f"{bad or 'no PP- symbols found'}")
            instance_ids = info.get("instance_ids") or []
            repacc = B.account(name, child, G_ABPD, declared_base=G_ABPD,
                               instance_ids=instance_ids, with_regdiff=False)
            out["accounting"][name] = repacc
            va = repacc["validator"]
            log(f"{name}: validator {va['n_errors']} err "
                f"(unexpected {len(va['unexpected_errors'])}), census "
                f"+{repacc['census_delta']['save_units']}u coherent "
                f"{repacc['census']['coherent']}, survivor "
                f"{'OK' if repacc['survivor_law_ok'] else 'VIOLATED'}, "
                f"symbol form OK x{len(forms)}")
        except Exception as e:                             # noqa: BLE001
            out["errors"][name + ".gates"] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".gates.tb"] = traceback.format_exc(limit=8)
            log(f"{name} GATES FAILED: {type(e).__name__}: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(OUT_DIR, "fix_accounting.json"), out)
    write_probes_json_all()
    return out


def write_probes_json_all() -> None:
    """Regenerate probes.json with BOTH ladders (H9/H10 on the rst base +
    the fix probes on G_ABPD), so probe_batch resolves every base."""
    acct_path = os.path.join(OUT_DIR, "accounting.json")
    build_out: Dict[str, Any] = {}
    if os.path.isfile(acct_path):
        with open(acct_path) as fh:
            build_out = json.load(fh)
    write_probes_json(build_out)
    fix_path = os.path.join(OUT_DIR, "fix_accounting.json")
    if not os.path.isfile(fix_path):
        return
    with open(fix_path) as fh:
        fix_out = json.load(fh)
    with open(os.path.join(OUT_DIR, "probes.json")) as fh:
        manifest = json.load(fh)
    onething = {
        "BXhf_f1i1": "ONE change vs the FAILED BXfix_f1i1 (batch 33): the "
                     "loaded symbol carries the corpus-lawful geometry form "
                     "(ref-face node rows + m_refFaces + the trailing "
                     "Geometry roster + hasParamDefValue 0) instead of the "
                     "one-specimen bake.  PASS = the fix; FAIL = the "
                     "instanced-symbol defect is not (only) the symbol's "
                     "geometry form.",
        "DEMO_250v_room_v3": "the user's exact prompt end-to-end under the "
                             "fix -- the product-scale confirmation of "
                             "whatever BXhf_f1i1 shows.",
    }
    n0 = len(manifest.get("probes") or [])
    for j, name in enumerate(FIX_LADDER):
        info = (fix_out.get("built") or {}).get(name) or {}
        acct = (fix_out.get("accounting") or {}).get(name) or {}
        va = acct.get("validator") or {}
        manifest["probes"].append({
            "order": n0 + j + 1, "rung": name,
            "file": f"experiments/hostpair/{name}.rvt",
            "base": relp(G_ABPD), "kind": "probe",
            "axis": FIX_AXES[name],
            "n_families": (1 if name == "BXhf_f1i1" else 6),
            "n_instances": (1 if name == "BXhf_f1i1" else 6),
            "n_walls": (0 if name == "BXhf_f1i1" else 4),
            "the_ONE_thing_it_tests": onething[name],
            "expected": "the fix verdict rung" if name == "BXhf_f1i1"
                        else "product-scale confirmation",
            "md5": info.get("md5"),
            "instance_ids": info.get("instance_ids"),
            "immediate_parent": info.get("immediate_parent"),
            "gates": {"validator_errors": va.get("n_errors"),
                      "validator_unexpected": len(va.get("unexpected_errors") or []),
                      "four_registry_coherent": (acct.get("census") or {}).get("coherent"),
                      "survivor_law_ok": acct.get("survivor_law_ok"),
                      "symbol_form_ok": all(
                          f.get("ok") for f in
                          (info.get("symbol_form") or {}).values())},
        })
    manifest["fix_reading"] = {
        "BXhf_f1i1 PASS": "the corpus-lawful symbol form IS the fix (the "
                          "one change vs batch-33's failed BXfix_f1i1); "
                          "flip famload_hostfix to default ON and re-emit "
                          "the product path.",
        "BXhf_f1i1 FAIL": "the symbol geometry form alone does not clear "
                          "the audit -- read against the SAME round's "
                          "H9/H10 verdict: the surviving suspect set is "
                          "the remaining famload/famgen host-element "
                          "deltas in hostfix_spec.json (family type-table/"
                          "familyIds/big2small/preview shapes) or the "
                          "registration rows (H11).",
        "DEMO PASS + BXhf FAIL (or converse)": "scale-dependent second "
                                               "defect; diff the two "
                                               "accountings.",
    }
    jdump(os.path.join(OUT_DIR, "probes.json"), manifest)
    log("probes.json extended with the fix ladder")


def stage_fix() -> Dict[str, Any]:
    B = _bisect()
    spec = importlib.util.spec_from_file_location(
        "_hostpair_probe_batch2", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in FIX_LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing fix probes (run fixdemo): "
                         f"{[relp(m) for m in missing]}")
    manifest = pb.stage_batch(
        files, control_from=G_ABPD,
        batch_n=B._campaign_global_next_batch(),           # noqa: SLF001
        note="hostpair fix ladder: the corpus-lawful instanced-symbol form "
             "(src/rvt/famload_hostfix, opt-in, default OFF), built "
             "speculatively while the batch-38 H9/H10 verdicts wait.  "
             "BXhf_f1i1 = ONE change vs batch-33's failed BXfix_f1i1 "
             "(the symbol geometry form); DEMO_250v_room_v3 = the user's "
             "exact prompt end-to-end under the fix.  Read "
             "experiments/hostpair/probes.json fix_reading.")
    log(f"STAGED fix batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} (base {e.get('base')}, "
            f"{e.get('kind')})")
    return manifest


# ===========================================================================
# the fix spec: famload-authored vs native, ranked  (deliverable 2)
# ===========================================================================

def diffspec() -> Dict[str, Any]:
    """The famload-vs-native host-pair field diff, ranked by the audit's
    deep walk from a placed instance.  A = the NATIVE element (rst),
    B = famload's authored element (H7's load file, batch-37 evidence)."""
    from rvt.mutate import Document
    R = _residual()
    if not os.path.isfile(H7_LOAD):
        raise SystemExit(f"missing {relp(H7_LOAD)} (famdoc_bisect build H7 first)")
    with open(H7_LOAD_JSON) as fh:
        h7plan = json.load(fh)["plans"][0]
    nat = Document.from_file(RST)
    h7 = Document.from_file(H7_LOAD)
    pairs = [
        (1, "FamilySymbol", NATIVE_SYMBOL, h7plan["symbol_ids"][0],
         "the element the instance names: the audit's walk regenerates/reads "
         "symbol geometry here -- rep + m_geomSteps + m_pGeomTable are the "
         "corpus-law gap (201/201 instanced sample symbols carry GElement + "
         "populated steps; famload writes dummy + None + None)"),
        (2, "Family", NATIVE_FAMILY, h7plan["host_family_id"],
         "the symbol's family: type table (5 named pairs vs 1 blank row), "
         "m_familyIds (16 resource twins vs param twins only), big2small "
         "(50 rows vs param twins only), preview infos, reference mgr"),
        (3, "FamilySurrogate", NATIVE_SURROGATE, h7plan["surrogate_id"],
         "the FamilyMgr registration anchor: native carries a preview "
         "LegendComponent (m_previewElemId); famload writes -1"),
        (4, "FamSymSurrogate", NATIVE_SYMSURROGATE, h7plan["symbol_surrogate_ids"][0],
         "the symbol's partition surrogate (near-parity expected)"),
        (5, "ParamElemFamily.twin", NATIVE_TWIN_PARAM,
         h7plan["twin_of"][str(min(int(k) for k in h7plan["twin_of"]))]
         if isinstance(h7plan["twin_of"], dict) else None,
         "the host param twin (near-parity expected; famload twins EVERY "
         "embedded param -- native twins ONE of two)"),
    ]
    id_fields = {"m_id", "m_familyId", "m_elemId", "m_surrogateId",
                 "m_famSurrogateId", "m_famId", "m_partitionSurrogateId",
                 "m_previewElemId", "m_famDocGUID", "m_masterId"}
    out: Dict[str, Any] = {
        "law": "A = the NATIVE host element (the V20-certified family "
               "layer); B = famload's authored element (H7's load file, "
               "recorded FAIL under an instance).  'differing' excludes "
               "nothing -- id/GUID fields are annotated so the CONTENT "
               "deltas stand out.  Rank = the audit's deep walk from a "
               "placed instance.",
        "A": {"file": relp(RST), "family": NATIVE_FAMILY},
        "B": {"file": relp(H7_LOAD), "family": h7plan["host_family_id"]},
        "native_only_constellation": {
            "LegendComponent_preview": NATIVE_PREVIEW,
            "resource_twins_16": list(NATIVE_RESOURCE_TWINS),
            "slave_FamilySymbol": NATIVE_SLAVE_SYMBOL,
            "note": "famload authors NO counterpart for any of these; H9 "
                    "carries copies of all of them"},
        "checklist": [],
    }
    for rank, label, a_id, b_id, why in pairs:
        entry: Dict[str, Any] = {"rank": rank, "element": label,
                                 "A_id": a_id, "B_id": b_id, "why_walked": why}
        if b_id is None:
            entry["note"] = "no famload counterpart"
            out["checklist"].append(entry)
            continue
        av, bv = nat.value(a_id) or {}, h7.value(b_id) or {}
        d = R.diff_objects(av, bv)
        entry["obj_diff"] = d
        entry["hdr_diff"] = R.diff_objects(nat.value(a_id, 101) or {},
                                           h7.value(b_id, 101) or {})
        entry["rep"] = {"A": nat.class_of(a_id, 103), "B": h7.class_of(b_id, 103)}
        diffs = d.get("differing") or []
        names = [x[0] if isinstance(x, (list, tuple)) else x for x in diffs]
        entry["content_deltas"] = [n for n in names if n not in id_fields]
        entry["id_deltas"] = [n for n in names if n in id_fields]
        if label == "FamilySymbol":
            gs = av.get("m_geomSteps") or {}
            gt = av.get("m_pGeomTable") or {}
            gsv = gs.get("value") or {}
            steps = gsv.get("m_bRepFormGList") or []
            entry["native_geometry_history"] = {
                "geomSteps_class": gs.get("ptr_class"),
                "bRepForm_steps": len(steps),
                "step_classes": sorted({str(s.get("ptr_class")) for s in steps
                                        if isinstance(s, dict)}),
                "idCounter": gsv.get("m_idCounter"),
                "flags": gsv.get("m_flags"),
                "latestGStepType": gsv.get("m_latestGStepTypeInPrevRegenCycle"),
                "geomTable_class": gt.get("ptr_class"),
                "geomTable_rows": len((gt.get("value") or {}).get("m_table") or []),
                "refFaces": len(av.get("m_refFaces") or []),
                "strongRefs": len(av.get("m_strongRefs") or []),
                "hasParamDefValue": av.get("m_hasParamDefValue"),
            }
        out["checklist"].append(entry)
    path = os.path.join(OUT_DIR, "hostfix_spec.json")
    jdump(path, out)
    log(f"hostfix_spec.json -> {relp(path)}")
    return out


# ===========================================================================
# verify + stage
# ===========================================================================

def verify() -> Dict[str, Any]:
    B = _bisect()
    _fdb()._install_schema()                               # noqa: SLF001
    acct_path = os.path.join(OUT_DIR, "accounting.json")
    if not os.path.isfile(acct_path):
        raise SystemExit("no accounting.json -- run build first")
    with open(acct_path) as fh:
        out = json.load(fh)
    fresh = {}
    parents = {"H9": os.path.join(BUILD_DIR, "H9_load.rvt"), "H10": RST}
    for name, info in (out.get("built") or {}).items():
        child = os.path.join(ROOT, info["file"])
        parent = parents[name]
        if not (os.path.isfile(child) and os.path.isfile(parent)):
            fresh[name] = {"error": "file(s) missing"}
            continue
        r = B.account(name, child, parent, declared_base=RST,
                      instance_ids=info.get("instance_ids") or [],
                      with_regdiff=False)
        fresh[name] = r
        va = r["validator"]
        log(f"{name}: validator {va['n_errors']} err (unexpected "
            f"{len(va['unexpected_errors'])}), coherent {r['census']['coherent']}, "
            f"survivor {'OK' if r['survivor_law_ok'] else 'VIOLATED'}")
    return fresh


def stage() -> Dict[str, Any]:
    B = _bisect()
    spec = importlib.util.spec_from_file_location(
        "_hostpair_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run build): {[relp(m) for m in missing]}")
    manifest = pb.stage_batch(
        files, control_from=RST,
        batch_n=B._campaign_global_next_batch(),           # noqa: SLF001
        note="hostpair: the host-pair byte-copy binary (post-verdict-#33). "
             "H9 = H7's exact load with the host family layer replaced by "
             "id-rebased BYTE-COPIES of the donor's own NATIVE 22-element "
             "host constellation + one instance by H7's exact template "
             "recipe; H10 = H9's immediate parent (no instance).  Read "
             "experiments/hostpair/probes.json reading_the_matrix; the "
             "famload-vs-native fix spec is hostfix_spec.json.")
    log(f"STAGED batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} (base {e.get('base')}, "
            f"{e.get('kind')})")
    return manifest


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("survey", help="measure + pin the native cluster")
    sub.add_parser("build", help="build H9 + H10 (+ gates + probes.json)")
    sub.add_parser("diffspec", help="hostfix_spec.json (famload vs native, ranked)")
    sub.add_parser("verify", help="re-run gates on the emitted probes")
    sub.add_parser("stage", help="probe_batch gate + stage (control = rst copy)")
    sub.add_parser("fixdemo", help="build BXhf_f1i1 + DEMO_250v_room_v3 "
                                   "through famload_hostfix")
    sub.add_parser("stagefix", help="probe_batch gate + stage the fix ladder "
                                    "(control = G_ABPD copy)")
    a = ap.parse_args(argv)
    if a.cmd == "survey":
        _fdb()._install_schema()                           # noqa: SLF001
        rep = survey_cluster()
        jdump(os.path.join(OUT_DIR, "native_cluster_survey.json"), rep)
        log(f"survey OK: {len(rep['cluster'])} elements, "
            f"{rep['reencode_roundtrip']['byte_exact']}/"
            f"{rep['reencode_roundtrip']['records']} byte-exact, pins all true "
            f"-> {relp(os.path.join(OUT_DIR, 'native_cluster_survey.json'))}")
        return 0
    if a.cmd == "build":
        out = build()
        n_err = len([k for k in out["errors"]
                     if not k.endswith((".traceback", ".tb"))])
        log(f"build done: {len(out['built'])} probe(s), {n_err} error(s), "
            f"{out.get('seconds')}s")
        return 1 if n_err else 0
    if a.cmd == "diffspec":
        diffspec()
        return 0
    if a.cmd == "verify":
        fresh = verify()
        bad = [n for n, r in fresh.items() if r.get("error") or not r.get("gates_ok")]
        log(f"verify done: {len(fresh)} probe(s), gate failures: {bad or 'none'}")
        return 1 if bad else 0
    if a.cmd == "stage":
        stage()
        return 0
    if a.cmd == "fixdemo":
        out = build_fix()
        n_err = len([k for k in out["errors"]
                     if not k.endswith((".traceback", ".tb"))])
        log(f"fixdemo done: {len(out['built'])} probe(s), {n_err} error(s), "
            f"{out.get('seconds')}s")
        return 1 if n_err else 0
    if a.cmd == "stagefix":
        stage_fix()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
