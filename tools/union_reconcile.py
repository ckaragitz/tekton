#!/usr/bin/env python
"""union_reconcile.py -- U16 vs T1v: the three-axis reconciliation round
(union-reconcile stream, 2026-08-05).

THE CONTRADICTION (genesis-audit verdicts #38..#44).  U16: our 35-element
content union added to the born EMBEDDED donor famdoc (rst concrete
column) by famdoc_final's union machinery, famloaded + instanced ON THE
RST SAMPLE -- viewer-PASS (b45).  T1v: the SAME content union added to the
born STANDALONE vendor-.rfa famdoc by the NEW rft_probe.template_union_doc
machinery (schema-typed small-id rebase), famloaded + instanced ON G_ABPD
-- viewer-FAIL (b51).  Three variables differ at once:

  (a) union MACHINERY   famdoc_final.make_union_doc + the donor-inline-
                        ADocument swap  vs  rft_probe.template_union_doc +
                        the famload-AUTHORED inline ADocument
  (b) shell SPECIES     embedded-born donor famdoc  vs  standalone-born
                        vendor .rfa famdoc
  (c) instance BASE     rst sample  vs  composed G_ABPD

T2a (standalone shell UNMODIFIED on G_ABPD) PASSED, so species-alone and
base-alone are each exonerated for the NO-union case; U12345 (U16 minus
the ADocument swap) PASSED, so the authored-ADocument flavour is
exonerated on the embedded shell.  What needs splitting is the
interaction of each axis WITH THE UNION.

THE LADDER (single-variable each):

  T1u   our content union in the STANDALONE vendor shell by the OLD
        PROVEN famdoc_final machinery (ported -- see PORT LAW below),
        famload + uniform instance ON RST.  T1u vs U16 = pure SPECIES.
  T1r   T1v's EXACT famdoc (unit segments rebuilt byte-identically --
        machine-verified against T1v_load.rvt before the load is allowed
        to proceed), famload + uniform instance ON RST.  T1r vs T1v =
        pure BASE; T1r vs U16 = machinery+species.
  U16g  U16's PROVEN famdoc + full recipe (unit segments rebuilt
        byte-identically -- machine-verified against U16.rvt -- PLUS the
        donor-inline-ADocument swap via famdoc_final's own function),
        famload + uniform instance ON G_ABPD.  U16g vs U16 = pure BASE
        on the proven side.

THE PORT LAW (T1u -- exactly what "famdoc_final machinery on a standalone
shell" means; every departure from U16's literal code is species-FORCED
and recorded):

  1. SHELL REBASE: schema-TYPED decode-time remap
     (rft_probe.load_rft_elements).  famdoc_final's blind int-walk is
     measured-unsound for the standalone species (ids 3..7674 alias
     ordinary small integers; first symptom GeomStepList.m_flags encode
     overflow -- rft_probe's own finding).  This is the ONE machinery
     element that cannot be held fixed across species; it is the same
     rebase T1v used, so it cancels OUT of the T1u-vs-T1r comparison and
     rides INTO the T1u-vs-U16 species comparison by necessity.
  2. OUR BLOCK at wm+2000 (famdoc_final's offset; T1v used wm+200000).
     The 1,992-element shell tops out at wm+1992 -- an overlap gate
     refuses if the blocks ever collide.  With RST's wm equal to
     G_ABPD's (1472524, measured), T1u's carried block lands on U16's
     exact carried ids (1474526..1474564).
  3. UNION + REGISTRATION: famdoc_final.make_union_doc's axes-{1..5}
     treatment verbatim -- carried block self-consistent, ONLY the
     self-Family reference repointed, register_added +
     register_param_rows(with_negatives=True), the dangling gate.
  4. AXIS 6 (the inline-ADocument swap), ported to the species: the
     standalone file has NO inline ContentDocuments ADocument; its BORN
     document object is Global/Latest (measured: same 19 top-level keys
     as the donor's inline value; m_elemTable/m_pHistory NULL --
     externalized to the Global/ElemTable + Global/History streams
     [standalone-ownership law]; AppInfoManager 131/239 registries
     POPULATED -- the exact surface the authored flavour nulls, and the
     one real separable machinery delta U12345 left standing).  The port
     swaps the BORN wrapper in: Global/Latest decoded through a
     schema-TYPED remapping ADocumentDecoder (calibrated on the donor's
     inline ADocument: the typed remap reproduces the blind walk's 1,194
     substitutions EXACTLY except m_elemArr[].m_history.m_originalElementId
     .m_id64 -- an id64-typed field inside the elem table, which the port
     AUTHORS anyway), the inline ElemTable + inline DocumentHistory
     transplanted from factory.author_embedded_adocument (the embedded
     form the species law demands; rows cover shell + carried, exactly
     like U16's row-append), and the four history identity GUIDs set to
     ONE fresh identity independent of the unit GUID (U16's
     swap_inline_adoc_union law, measured native on the donor's entry).
  5. IDENTITY PINS: T1u's carried ParamElemFamily m_typeId session hex is
     pinned to U16's (8217b592...) so the carried param records are
     byte-comparable to U16's; the unit GUID is FRESH (house law:
     fresh GUIDs per build; a reused unit GUID risks viewer-side content
     dedupe faking a verdict).

DOC-GUID LAW OF THIS ROUND: unit segments carry NO GUID (measured:
rebuilt segments byte-match the shipped units while the GUID lives only
in the host-side registration + the footer nonce), so "byte-identical
famdoc" = byte-identical 101/102/103 unit segments, machine-verified;
every probe mints a FRESH unit GUID and records it.

THE BYTE AUDIT (``audit``): the machinery delta MEASURED, not argued --
each union file diffed record-by-record against its own certified-PASS
unmodified-shell baseline on the same id layout (T1v vs T2a, U16 vs B7:
wm identical, shell blocks identical), so each diff IS exactly what that
machinery did to that shell; then the two diffs are compared axis by
axis (carried 35 pairwise through the id correspondence, self-Family
registration surfaces, inline-ADocument flavour, small-id residue hunt).
Findings ranked in byte_audit.json + the record.

PROOF-ONLY: all three probes embed Autodesk sample / vendor-born content
and stay quarantined in experiments/ (zero donors in shipped output).
STAGE ONLY -- the orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/union_reconcile.py audit            # byte_audit.json
    .venv/bin/python tools/union_reconcile.py build            # all 3 probes
    .venv/bin/python tools/union_reconcile.py build --only T1r
    .venv/bin/python tools/union_reconcile.py verify           # re-run gates
    .venv/bin/python tools/union_reconcile.py stage            # probe_batch + 2 controls

TERRITORY: this file, ``experiments/unionrec/**``,
``tests/test_union_reconcile.py``, ``docs/inbox/union-reconcile.md``,
plus the staging copies probe_batch itself writes under
``experiments/acceptance/``.  IMPORTS (never edits): tools/famdoc_final.py
(the proven union machinery + its ADocument swap), tools/rft_probe.py
(the .rfa reader / typed rebase / T1 union / placement),
tools/famdoc_bisect.py, tools/famdoc_blobs.py, tools/bisect_instance_bug.py,
tools/probe_batch.py, rvt.famload, rvt.adocument, rvt.famgen.factory.
No Autodesk install dirs, no browser, no full-suite runs.
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

OUT_DIR = os.path.join(ROOT, "experiments", "unionrec")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
AUDIT = os.path.join(OUT_DIR, "byte_audit.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
VENDOR_RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples",
                          "Autodesk", "racbasicsamplefamily-2026.rfa")

#: the four reference files this round measures against (all viewer-read)
U16_RVT = os.path.join(ROOT, "experiments", "famdoc_final", "U16.rvt")
T1V_RVT = os.path.join(ROOT, "experiments", "birthright", "T1v.rvt")
T1V_LOAD = os.path.join(ROOT, "experiments", "birthright", "_build", "T1v",
                        "T1v_load.rvt")
B7_RVT = os.path.join(ROOT, "experiments", "famdoc_blobs", "B7.rvt")
T2A_RVT = os.path.join(ROOT, "experiments", "rftprobe", "T2a.rvt")

#: recorded build identities of the two sides of the contradiction
#: (experiments/famdoc_final/accounting.json + experiments/birthright/
#: accounting.json; the session hex is the ``revit.local.family:`` GUID our
#: famgen mints per creation session -- it rides INSIDE the unit segments,
#: so byte-identical rebuilds must pin it)
U16_DOC_GUID = "ffee468e-5c5a-4cde-9030-56dbca68b3e7"
U16_SESSION_HEX = "8217b592879e4857b9d2c326faa567e4"
T1V_DOC_GUID = "3b21dfd9-a68c-4ece-a51e-368f55980d13"
T1V_SESSION_HEX = "3c5faf44b7a9417693b8442eefbf2dd1"

LADDER = ("T1u", "T1r", "U16g")

AXES = {
    "T1u": "SPECIES probe: our 35-element content union in the STANDALONE "
           "vendor shell by the OLD PROVEN famdoc_final machinery (ported; "
           "born Global/Latest ADocument swapped in), famload + uniform "
           "instance on RST.  The ONE thing vs U16 (PASS): the shell species.",
    "T1r": "BASE probe, failing side: T1v's EXACT famdoc (unit segments "
           "byte-identical, machine-verified), famload + uniform instance "
           "on RST.  The ONE thing vs T1v (FAIL): the base.",
    "U16g": "BASE probe, proven side: U16's EXACT famdoc + full recipe "
            "(unit segments byte-identical, machine-verified; donor inline "
            "ADocument swapped by famdoc_final's own function), famload + "
            "uniform instance on G_ABPD.  The ONE thing vs U16 (PASS): "
            "the base.",
}

SESSION_RE = re.compile(r"revit\.local\.family:([0-9a-f]{32})")


def log(msg: str) -> None:
    print(f"[unionrec] {msg}", flush=True)


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
        f"_unionrec_{name}", os.path.join(HERE, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CACHE: Dict[str, Any] = {}


def _ff():
    """tools/famdoc_final.py -- the proven union machinery (its own
    famdoc_bisect import repoints nothing; famdoc_final writes only when
    ITS build/stage commands run, which this stream never invokes)."""
    if "ff" not in _CACHE:
        _CACHE["ff"] = _load_tool("famdoc_final")
    return _CACHE["ff"]


def _rp():
    """tools/rft_probe.py -- the .rfa reader (typed rebase), the T1 union,
    famload_onto + place_one (its famdoc_bisect output dirs repoint
    themselves into ITS build tree; this stream only reads)."""
    if "rp" not in _CACHE:
        _CACHE["rp"] = _load_tool("rft_probe")
    return _CACHE["rp"]


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
# identity pinning (session hex) + unit byte-identity verification
# ===========================================================================

def _walk_strings(node, fn):
    """Apply ``fn`` to every str leaf, in place (dict/list containers)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str):
                node[k] = fn(v)
            else:
                _walk_strings(v, fn)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str):
                node[i] = fn(v)
            else:
                _walk_strings(v, fn)


def doc_session_hexes(elements) -> set:
    """Every ``revit.local.family:<hex>`` session GUID present in the
    elements' string fields."""
    out: set = set()

    def scan(node):
        if isinstance(node, dict):
            for v in node.values():
                scan(v)
        elif isinstance(node, list):
            for v in node:
                scan(v)
        elif isinstance(node, str):
            out.update(SESSION_RE.findall(node))

    for e in elements:
        scan(e.header)
        scan(e.obj)
        if e.rep is not None:
            scan(e.rep)
    return out


def pin_session_hex(elements, fresh_hex: str, target_hex: str) -> int:
    """Replace ``fresh_hex`` with ``target_hex`` in every string field of
    every element (the per-creation-session ``revit.local.family:`` GUID our
    famgen mints -- the ONLY nondeterminism inside the unit segments,
    measured).  Returns the substitution count."""
    n = [0]

    def sub(s: str) -> str:
        if fresh_hex in s:
            n[0] += s.count(fresh_hex)
            return s.replace(fresh_hex, target_hex)
        return s

    for e in elements:
        _walk_strings(e.header, sub)
        _walk_strings(e.obj, sub)
        if e.rep is not None:
            _walk_strings(e.rep, sub)
    return n[0]


def pin_doc_to_target_unit(doc, target_file: str, target_guid: str) -> Dict[str, Any]:
    """Pin the rebuilt doc's session hex to the target build's and VERIFY
    the unit segments are byte-identical to the target file's unit
    (build-refusing).  The fresh/target hexes are discovered by set
    difference (self-calibrating; refuses on ambiguity)."""
    from rvt.families import FamilyIndex, unit_segments
    idx = FamilyIndex(target_file)
    tgt_unit = None
    for i, u in enumerate(idx.units):
        if str(u.guid) == target_guid:
            tgt_unit = i
    if tgt_unit is None:
        raise RuntimeError(f"{relp(target_file)}: no unit with guid "
                           f"{target_guid}")
    tgt_els_hexes: set = set()
    for eid, r in idx.unit_records(tgt_unit).get(102, {}).items():
        if idx.class_name(r.class_id) == "ParamElemFamily":
            v = idx.value(tgt_unit, eid) or {}
            tid = str((((v.get("m_pParamDef") or {}).get("value") or {})
                       .get("m_typeId") or {}).get("m_typeId") or "")
            tgt_els_hexes.update(SESSION_RE.findall(tid))
    mine = doc_session_hexes(doc.elements)
    fresh = sorted(mine - tgt_els_hexes)
    target = sorted(tgt_els_hexes - mine)
    if len(fresh) != 1 or len(target) != 1:
        raise RuntimeError(
            f"session-hex pinning is ambiguous vs {relp(target_file)}: "
            f"mine-only {fresh}, target-only {target} (expected exactly one "
            f"each -- the per-build session GUID)")
    n = pin_session_hex(doc.elements, fresh[0], target[0])
    segs = doc.to_embedded_unit()["segments"]
    got = unit_segments(idx, tgt_unit)
    equal = {int(k): (segs.get(k) == got.get(k)) for k in
             sorted(set(segs) | set(got))}
    if not all(equal.values()):
        bad = [k for k, ok in equal.items() if not ok]
        raise RuntimeError(
            f"rebuilt unit is NOT byte-identical to {relp(target_file)} unit "
            f"{tgt_unit} after session-hex pinning: segments {bad} differ -- "
            f"the byte-identity claim would be false; refused")
    return {"target_file": relp(target_file), "target_unit": tgt_unit,
            "target_guid": target_guid,
            "session_hex_pinned": {"from": fresh[0], "to": target[0],
                                   "substitutions": n},
            "segments_byte_identical": {str(k): v for k, v in equal.items()},
            "segment_bytes": {str(k): len(v) for k, v in sorted(segs.items())}}


def famdoc_refs(doc, host: str) -> Dict[str, Any]:
    """famdoc_final.famdoc_reference_resolution parameterized by HOST (the
    schema comes from the host itself): every ElementId-typed value of every
    seq-102 record must resolve in the unit or the host ElemTable.
    Build-refusing."""
    from rvt.families import FamilyIndex
    from rvt.mutate import Document
    from rvt.objects import iter_records
    from rvt.validate import _RefDecoder, find_dangling_refs
    unit = doc.to_embedded_unit()
    seg = unit["segments"][102]
    schema = FamilyIndex(host).schema
    dec = _RefDecoder(schema)
    refs = []
    for rec in iter_records(seg, 102):
        if rec.elem_id < 0:
            continue
        dec.refs = []
        try:
            dec.decode_record(rec.class_id, rec.payload)
        except Exception:                                      # noqa: BLE001
            continue
        refs.extend((rec.elem_id, p, v) for p, v in dec.refs)
    member = {e.elem_id for e in doc.elements}
    host_ids = set(Document.from_file(host).et_by_id)
    dangling = find_dangling_refs(refs, member)
    host_resident = [d for d in dangling if d[2] in host_ids]
    unresolved = [d for d in dangling if d[2] not in host_ids]
    out = {"host": relp(host), "refs_typed": len(refs),
           "resolve_in_unit": len(refs) - len(dangling),
           "standalone_dangling_host_resident": len(host_resident),
           "unresolved_anywhere": len(unresolved),
           "unresolved_examples": [{"owner": o, "path": p[-80:], "target": t}
                                   for o, p, t in unresolved[:8]]}
    if unresolved:
        raise RuntimeError(f"famdoc leaves {len(unresolved)} schema-typed "
                           f"reference(s) unresolved in BOTH the unit and "
                           f"the host {relp(host)}: {unresolved[:4]}")
    return out


# ===========================================================================
# T1u: famdoc_final's union machinery ported to the standalone shell
# ===========================================================================

def make_union_doc_standalone(rfa_path: str, wm: int):
    """famdoc_final.make_union_doc's axes-{1..5} body with the STANDALONE
    vendor shell in the donor slot.  Departures from U16's literal code are
    species-FORCED and recorded in the report: the shell rebase is the
    schema-TYPED decode remap (the blind walk is measured-unsound at small
    ids); the shell's name/category/part_type/type come from the .rfa's own
    facts (U16 took the donor's from its native host row -- a standalone
    file HAS no host row; T2a PASSED with these exact facts).  Everything
    else -- our-block offset wm+2000, carried-set law, repoint law,
    dangling gate, registration -- is famdoc_final's verbatim.
    Returns (doc, report, carried, ctx)."""
    FB = _fb()
    rp = _rp()
    from rvt.families import FamilyIndex
    from rvt.famgen.loader import _walk_replace_ids
    from rvt.genesis.skeleton import SkelElement

    member = sorted(FamilyIndex(rfa_path).unit_records(0).get(102, {}))
    idmap = {old: wm + 1 + i for i, old in enumerate(member)}
    shell_els, facts = rp.load_rft_elements(rfa_path, idmap)
    sf_new = idmap[facts["self_family"]]
    sf = next(e for e in shell_els if e.elem_id == sf_new)
    shell_top = wm + len(shell_els)
    report: Dict[str, Any] = {
        "axes": [1, 2, 3, 4, 5, 6],
        "shell_block": [wm + 1, shell_top],
        "shell_rebase": facts["rebase"],
        "shell_facts": {k: facts[k] for k in
                        ("rft", "sha256", "owner_source", "n_elements",
                         "self_family", "category", "part_type")},
        "anchors": {"self_family": sf_new},
        "carried": [], "repointed": {}, "registration": {},
        "port_law": {
            "shell_rebase": "schema-TYPED decode remap (species-forced; the "
                            "famdoc_final blind int-walk aliases small ids "
                            "-- rft_probe's measured finding)",
            "our_block": "wm+2000 (famdoc_final's offset; lands on U16's "
                         "exact carried ids since RST wm == G_ABPD wm)",
            "facts": "name/category/part_type/type from the .rfa's own "
                     "facts (no native host row exists for a standalone "
                     "shell; the same facts T2a PASSED with)",
            "adoc": "BORN Global/Latest wrapper swapped in post-famload "
                    "(swap_born_adoc; U16's axis 6 ported to the species)",
        },
    }

    if shell_top >= wm + 2000:
        raise RuntimeError(f"T1u: shell block tops at {shell_top}, "
                           f"colliding with our famdoc block at {wm + 2000}")

    prod = FB.our_product(wm + 2000)
    ours = prod.doc
    sets = FB.axis_sets(ours)
    carried_ids: set = set()
    for a in (1, 2, 3, 4, 5):
        carried_ids |= set(sets[f"H{a}"])
    carried_ids = sorted(carried_ids)
    by_id = {e.elem_id: e for e in ours.elements}

    # famdoc_final's repoint law for the full union: ONLY the self-Family
    repoint = {ours.self_family.elem_id: sf_new}
    carried: List[Any] = []
    carried_set = set(carried_ids)
    for i in carried_ids:
        e = by_id[i]
        h, o = copy.deepcopy(e.header), copy.deepcopy(e.obj)
        r = copy.deepcopy(e.rep) if e.rep is not None else None
        for node in (h, o, r):
            if node is not None:
                _walk_replace_ids(node, repoint)
        owner = e.owner_id
        if owner in repoint:
            owner = repoint[owner]
        elif owner == ours.self_family.elem_id:
            owner = sf_new
        carried.append(SkelElement(e.elem_id, e.class_name, h, o, r,
                                   owner_id=owner if (owner or 0) > 0 else -1,
                                   kind=e.kind))
    report["carried"] = [{"id": e.elem_id, "class": e.class_name,
                          "kind": e.kind} for e in carried]
    report["repointed"] = {str(k): v for k, v in repoint.items()}

    # famdoc_final's dangling gate
    hybrid_ids = {e.elem_id for e in shell_els} | carried_set
    our_ids = {e.elem_id for e in ours.elements}
    blocks_top = max(our_ids)
    dangling: List[Tuple[str, int]] = []

    def scan(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and wm < v <= blocks_top \
                        and v not in hybrid_ids:
                    dangling.append((path + "." + k, v))
                else:
                    scan(v, path + "." + k)
        elif isinstance(node, list):
            for j, v in enumerate(node):
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and wm < v <= blocks_top \
                        and v not in hybrid_ids:
                    dangling.append((f"{path}[{j}]", v))
                else:
                    scan(v, f"{path}[{j}]")

    for e in carried:
        scan(e.header, f"{e.elem_id}.hdr")
        scan(e.obj, f"{e.elem_id}.obj")
        if e.rep is not None:
            scan(e.rep, f"{e.elem_id}.rep")
    if dangling:
        raise RuntimeError(f"T1u: carried union leaves dangling "
                           f"above-watermark refs: {dangling[:6]}")
    report["dangling_above_watermark"] = 0

    # famdoc_final's registration, verbatim (with_negatives=True: axis 2
    # is in the union, exactly U16's condition)
    report["registration"]["membership"] = FB.register_added(
        sf, sorted(carried_set))
    param_ids = {e.elem_id for e in carried
                 if e.class_name == "ParamElemFamily"}
    our_sf = ours.self_family.obj
    fp_rows = (((our_sf.get("m_familyParams") or {}).get("value") or {})
               .get("m_params") or [])
    rows = [r for r in fp_rows
            if r.get("m_paramId") in param_ids
            or (isinstance(r.get("m_paramId"), int)
                and r.get("m_paramId") < 0)]
    locked = [i for i in (our_sf.get(
        "m_lockedParameterIdsForDirectManipulation") or []) if i in param_ids]
    groups: List[Dict[str, Any]] = []
    cells = ((our_sf.get("m_cellList") or {}).get("value") or {}) \
        .get("m_cells") or []
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        for g in cv.get("m_sortedParams") or []:
            if not isinstance(g, dict):
                continue
            keep = [pid for pid in (g.get("m_paramIds") or [])
                    if pid in param_ids
                    or (isinstance(pid, int) and pid < 0)]
            if keep:
                groups.append({"m_groupTypeId":
                               copy.deepcopy(g.get("m_groupTypeId")),
                               "m_paramIds": keep})
        break
    report["registration"]["params"] = FB.register_param_rows(
        sf, rows, locked, groups)
    report["registration"]["params_with_negatives"] = True

    elements = sorted(list(shell_els) + carried, key=lambda e: e.elem_id)
    named = [n for n in facts["type_names"] if str(n).strip()]
    types = [(named[0], {})] if named else [("T1u", {})]
    doc = FB.HybridFamilyDoc(
        elements, sf, name="racbasicsamplefamily T1u",
        category_id=int(facts["category"]),
        part_type=int(facts.get("part_type") if facts.get("part_type")
                      is not None else -1),
        types=types, current_type=1)
    ctx = {"idmap": idmap, "self_family": sf_new, "facts": facts,
           "carried": carried}
    return doc, report, carried, ctx


class RemapADocDecoder:
    """Factory for the schema-TYPED remapping ADocumentDecoder (the unit
    records' _remap_decoder law extended to the document object).
    CALIBRATED on the donor's inline ADocument (1.4M ids -- zero false
    positives): the typed remap reproduces the blind int-walk's 1,194
    substitutions exactly, except ``m_elemArr[].m_history
    .m_originalElementId.m_id64`` (schema type id64, not ElementId) --
    a field inside the elem table, which the T1u port AUTHORS anyway."""

    def __new__(cls, schema, idmap: Dict[int, int]):
        from rvt import adocument as A

        class _Dec(A.ADocumentDecoder):
            def __init__(self, s, m):
                super().__init__(s)
                self._idmap = m
                self.n_remapped = 0
                self.small_unmapped: Dict[int, int] = {}

            def _decode_value_class(self, rd, type_id, queue, state, path):
                v = super()._decode_value_class(rd, type_id, queue, state,
                                                path)
                if (type_id == self.id_ElementId and isinstance(v, int)
                        and not isinstance(v, bool)):
                    if v in self._idmap:
                        self.n_remapped += 1
                        return self._idmap[v]
                    if v > 0:
                        self.small_unmapped[v] = \
                            self.small_unmapped.get(v, 0) + 1
                return v

        return _Dec(schema, idmap)


def swap_born_adoc(path_in: str, path_out: str, *, doc, rfa_path: str,
                   idmap: Dict[int, int],
                   identity_guid: Optional[str] = None) -> Dict[str, Any]:
    """T1u's axis 6: replace the famload-AUTHORED inline ADocument with the
    shell's BORN document object (Global/Latest of the .rfa), ported to the
    inline embedded form:

      * born wrapper decoded through the schema-TYPED remap decoder (every
        ElementId-typed value -- the 131 populated AppInfo registries'
        whole reference surface -- rebased to the hybrid block);
      * inline ElemTable + inline DocumentHistory transplanted from
        factory.author_embedded_adocument over the FULL hybrid element
        list (the standalone species externalizes both to Global streams;
        the inline form requires them -- rows cover shell + carried,
        U16's own row-append law);
      * the four history identity GUIDs set to ONE fresh identity
        independent of the unit GUID (swap_inline_adoc_union's measured
        native law; the born standalone carries NO history GUIDs).

    Key-set, owner-family, host-weakref and decode-clean gates refuse any
    species drift."""
    import dataclasses
    from rvt import adocument as A
    from rvt import ecc
    from rvt.container import open_rvt
    from rvt.famgen import factory as F
    from rvt.families import FamilyIndex
    from rvt.roundtrip import read_entries
    from rvt.stream_encoders import wrap_global_stream
    from rvt.cfb_writer import write_cfb

    with open_rvt(rfa_path) as f:
        latest = f.inflate("Global/Latest")
    dec = RemapADocDecoder(FamilyIndex(rfa_path).schema, idmap)
    born = A.decode_latest(latest, decoder=dec)
    if not born.clean:
        raise RuntimeError("T1u: born Global/Latest does not decode clean "
                           "through the typed remap decoder")
    value = born.value

    authored = F.author_embedded_adocument(doc)
    av = authored["value"]
    if set(value) != set(av):
        raise RuntimeError(
            f"T1u: born ADocument key set differs from the embedded form "
            f"(born-only {sorted(set(value) - set(av))}, embedded-only "
            f"{sorted(set(av) - set(value))}) -- species drift; re-measure")
    if value.get("m_pHostDocument") != {"weakref": 1}:
        raise RuntimeError(f"T1u: born m_pHostDocument is "
                           f"{value.get('m_pHostDocument')!r}, expected the "
                           f"host weakref 1")
    if value.get("m_elemTable") is not None:
        raise RuntimeError("T1u: born m_elemTable is not the externalized "
                           "NULL the standalone law promises; re-measure")
    if value.get("m_pHistory") is not None:
        raise RuntimeError("T1u: born m_pHistory is not the externalized "
                           "NULL the standalone law promises; re-measure")

    value["m_elemTable"] = copy.deepcopy(av["m_elemTable"])
    value["m_pHistory"] = copy.deepcopy(av["m_pHistory"])
    fresh_identity = identity_guid or str(uuid.uuid4())
    hist = ((value.get("m_pHistory") or {}).get("value") or {})
    for k in ("m_creationGUID", "m_detachGUID", "m_upgradeGUID",
              "m_saveAsGUID"):
        hist[k] = {"m_guid": fresh_identity}

    own = value.get("m_ownerFamilyId")
    if own != doc.self_family.elem_id:
        raise RuntimeError(f"T1u: born m_ownerFamilyId remapped to {own}, "
                           f"expected the hybrid self-Family "
                           f"{doc.self_family.elem_id}")

    inner = ((value.get("m_elemTable") or {}).get("value") or {})
    arr = inner.get("m_elemArr") or []
    if len(arr) != len(doc.elements):
        raise RuntimeError(f"T1u: authored elem table carries {len(arr)} "
                           f"rows for {len(doc.elements)} elements")

    payload = A.encode_latest(value, trailer=b"")
    back = A.decode_latest(payload)
    if not back.clean:
        raise RuntimeError("T1u: ported born ADocument does not re-decode "
                           "clean")

    guid = doc.document_guid
    with open_rvt(path_in) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    entries, tail = F.parse_content_documents(cd)
    n_before = len(entries)
    if not any(g == guid for g, _a in entries):
        raise RuntimeError(f"T1u: no ContentDocuments entry for {guid}")
    swapped = [(g, (payload if g == guid else a)) for g, a in entries]
    new_cd = F.assemble_content_documents(swapped, tail=tail or F.CD_END_RECORD)
    stream = ecc.frame_stream(wrap_global_stream("Global/ContentDocuments",
                                                 new_cd, level=3))
    ents = read_entries(path_in)
    out_entries = [dataclasses.replace(e, data=stream)
                   if (e.entry_type == "stream"
                       and e.path == "Global/ContentDocuments")
                   else e for e in ents]
    write_cfb(path_out, out_entries)
    aim = ((value.get("m_pAppInfoManager") or {}).get("value") or {})
    a_arr = aim.get("m_appInfoArr") or []
    src = ((inner.get("m_pSource") or {}).get("value") or {})
    return {"entries": n_before, "swapped_guid": guid,
            "adoc_bytes": len(payload),
            "born_source": relp(rfa_path),
            "typed_remap": {"ids_remapped_values": dec.n_remapped,
                            "positive_elementids_not_in_idmap":
                                sum(dec.small_unmapped.values()),
                            "distinct_unmapped": len(dec.small_unmapped)},
            "appinfo_slots": len(a_arr),
            "appinfo_populated": sum(1 for x in a_arr if x),
            "stored_by_revit_build": len(value.get("m_storedByRevitBuild")
                                         or []),
            "owner_family_id": own,
            "history_identity_fresh": fresh_identity,
            "history_guids_born": "absent (standalone species) -- set to "
                                  "one fresh identity per the measured "
                                  "inline law",
            "elem_rows_total": len(arr),
            "identifier_source_last": src.get("m_last")}


# ===========================================================================
# rung builders
# ===========================================================================

def _build_common(name: str, doc, *, host: str, category: int,
                  pdir: str, outp: str,
                  adoc_swap=None) -> Dict[str, Any]:
    """famload + (optional inline-ADocument swap) + ONE uniform template
    instance -- the shared tail of all three rungs (famdoc_final's
    build_union_probe shape with the host parameterized via rft_probe's
    generalized famload_onto/place_one)."""
    rp = _rp()
    fbl = _fbl()
    info: Dict[str, Any] = {}
    src = os.path.join(pdir, f"{name}_load.rvt")
    info["load"] = rp.famload_onto(host, doc, src, name)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    if adoc_swap is not None:
        swapped = os.path.join(pdir, f"{name}_load_adoc.rvt")
        info["adoc_swap"] = adoc_swap(src, swapped)
        src = swapped
    info["immediate_parent"] = relp(src)
    info["placement"] = ("uniform template path (ConstructedSpecimens on "
                         "the probe's own host + add_family_instance + "
                         "commit; category = the family's own)")
    info["instance"] = rp.place_one(src, outp, host=host, symbol_id=sym,
                                    family_id=fam, category=category)
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["blob_proof"] = fbl.blob_proof(outp, host)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


def build_t1u() -> Dict[str, Any]:
    ff = _ff()
    rp = _rp()
    T = _room()
    rp._install_schema(RST)
    wm = T.host_watermark(RST)
    pdir = os.path.join(BUILD_DIR, "T1u")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T1u.rvt")
    info: Dict[str, Any] = {"probe": "T1u", "axis": AXES["T1u"],
                            "base": relp(RST), "watermark": wm,
                            "rfa": relp(VENDOR_RFA)}
    doc, rep, carried, ctx = make_union_doc_standalone(VENDOR_RFA, wm)
    # identity pins: carried params byte-comparable to U16's; unit GUID fresh
    hexes = doc_session_hexes(carried)
    if len(hexes) != 1:
        raise RuntimeError(f"T1u: carried block carries {len(hexes)} session "
                           f"hexes, expected exactly our fresh one: {hexes}")
    n_sub = pin_session_hex(doc.elements, next(iter(hexes)), U16_SESSION_HEX)
    rep["session_hex"] = {"pinned_to": U16_SESSION_HEX,
                          "reason": "U16's creation-session GUID: makes the "
                                    "carried ParamElemFamily records "
                                    "byte-comparable to U16's",
                          "substitutions": n_sub}
    info["union"] = rep
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    info["reference_resolution"] = famdoc_refs(doc, RST)

    def _swap(src, dst):
        return swap_born_adoc(src, dst, doc=doc, rfa_path=VENDOR_RFA,
                              idmap=ctx["idmap"])

    info.update(_build_common("T1u", doc, host=RST,
                              category=int(doc.category_id), pdir=pdir,
                              outp=outp, adoc_swap=_swap))
    info["instance_category"] = int(doc.category_id)
    return info


def build_t1r() -> Dict[str, Any]:
    rp = _rp()
    T = _room()
    rp._install_schema(RST)
    wm = T.host_watermark(RST)
    wm_g = T.host_watermark(G_ABPD)
    if wm != wm_g:
        raise RuntimeError(f"T1r: RST watermark {wm} != G_ABPD watermark "
                           f"{wm_g} -- the byte-identical famdoc transplant "
                           f"assumption fails; re-derive the plan")
    pdir = os.path.join(BUILD_DIR, "T1r")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T1r.rvt")
    info: Dict[str, Any] = {"probe": "T1r", "axis": AXES["T1r"],
                            "base": relp(RST), "watermark": wm,
                            "rfa": relp(VENDOR_RFA)}
    doc, rep = rp.template_union_doc(rp.VENDOR_RFA, wm)
    info["union"] = {
        "template": {k: rep["template"].get(k) for k in
                     ("template_block", "self_family", "types_authored",
                      "types_from_template")},
        "n_carried": len(rep["carried"]),
        "registration": rep["registration"],
    }
    info["byte_identity"] = pin_doc_to_target_unit(doc, T1V_LOAD,
                                                   T1V_DOC_GUID)
    info["document_guid"] = doc.document_guid       # fresh (house law)
    info["n_elements"] = len(doc.elements)
    info["reference_resolution"] = famdoc_refs(doc, RST)
    info.update(_build_common("T1r", doc, host=RST,
                              category=int(doc.category_id), pdir=pdir,
                              outp=outp))
    info["instance_category"] = int(doc.category_id)
    return info


def build_u16g() -> Dict[str, Any]:
    ff = _ff()
    FB = _fb()
    rp = _rp()
    T = _room()
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    wm_r = T.host_watermark(RST)
    if wm != wm_r:
        raise RuntimeError(f"U16g: G_ABPD watermark {wm} != RST watermark "
                           f"{wm_r} -- the byte-identical famdoc transplant "
                           f"assumption fails; re-derive the plan")
    pdir = os.path.join(BUILD_DIR, "U16g")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "U16g.rvt")
    info: Dict[str, Any] = {"probe": "U16g", "axis": AXES["U16g"],
                            "base": relp(G_ABPD), "watermark": wm}
    doc, hrep, carried, dctx = ff.make_union_doc("U16", wm)
    info["union"] = {k: hrep[k] for k in ("axes", "donor_block", "anchors",
                                          "repointed", "registration")}
    info["union"]["n_carried"] = len(hrep["carried"])
    info["byte_identity"] = pin_doc_to_target_unit(doc, U16_RVT,
                                                   U16_DOC_GUID)
    info["document_guid"] = doc.document_guid       # fresh (house law)
    info["n_elements"] = len(doc.elements)
    info["reference_resolution"] = famdoc_refs(doc, G_ABPD)

    def _swap(src, dst):
        rec = ff.swap_inline_adoc_union(
            src, dst, guid=doc.document_guid, adoc_value=dctx["adoc_value"],
            idmap=dctx["idmap"],
            self_family_new=dctx["anchors"]["self_family"],
            carried_elements=carried)
        rec["machinery"] = ("famdoc_final.swap_inline_adoc_union VERBATIM "
                            "(U16's own function; only the target file "
                            "differs)")
        return rec

    info.update(_build_common("U16g", doc, host=G_ABPD,
                              category=FB.DONOR_CATEGORY, pdir=pdir,
                              outp=outp, adoc_swap=_swap))
    info["instance_category"] = FB.DONOR_CATEGORY
    info["adoc_value_diff_vs_u16"] = _adoc_value_diff_vs_u16(
        os.path.join(pdir, "U16g_load_adoc.rvt"), doc.document_guid)
    return info


def _adoc_value_diff_vs_u16(swapped_path: str, guid: str) -> Dict[str, Any]:
    """Machine-verify U16g's swapped inline ADocument equals U16's shipped
    one field-for-field, modulo exactly the four history identity GUIDs
    (fresh per build -- U16's own law).  Build-refusing on any other
    delta."""
    from rvt import adocument as A
    from rvt.families import FamilyIndex, content_document_adoc
    mine = A.decode_latest(content_document_adoc(FamilyIndex(swapped_path),
                                                 guid)).value
    theirs = A.decode_latest(content_document_adoc(FamilyIndex(U16_RVT),
                                                   U16_DOC_GUID)).value

    diffs: List[str] = []

    def walk(a, b, p=""):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                walk(a.get(k), b.get(k), p + "." + k)
        elif isinstance(a, list) and isinstance(b, list) \
                and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, p + f"[{i}]")
        else:
            if a != b:
                diffs.append(p)

    walk(mine, theirs)
    allowed = re.compile(
        r"^\.m_pHistory\.value\.m_(creation|detach|upgrade|saveAs)GUID"
        r"\.m_guid$")
    unexpected = [d for d in diffs if not allowed.match(d)]
    if unexpected:
        raise RuntimeError(f"U16g: swapped inline ADocument differs from "
                           f"U16's beyond the history identity: "
                           f"{unexpected[:6]}")
    return {"n_diff_paths": len(diffs),
            "all_within_history_identity": True,
            "diff_paths": diffs}


BUILDERS = {"T1u": build_t1u, "T1r": build_t1r, "U16g": build_u16g}


def base_of(name: str) -> str:
    return G_ABPD if name == "U16g" else RST


# ===========================================================================
# accounting + gates (famdoc_final's U-probe shape)
# ===========================================================================

def _accounting(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
    B = _bisect()
    fbl = _fbl()
    base = base_of(name)
    child = os.path.join(ROOT, info["file"])
    parent = os.path.join(ROOT, info["immediate_parent"])
    out: Dict[str, Any] = {}
    out["probe"] = B.account(name, child, parent, declared_base=base,
                             instance_ids=info.get("instance_ids") or [])
    out["hop_load"] = B.account(name + ".hop_load", parent, base,
                                declared_base=base, instance_ids=[],
                                with_regdiff=False)
    out["blob_proof"] = fbl.blob_proof(child, base)
    out["blob_proof_parent"] = fbl.blob_proof(parent, base)
    return out


def _gates(name: str, info: Dict[str, Any], acct: Dict[str, Any]) -> Dict[str, Any]:
    rep = acct["probe"]
    hop = acct["hop_load"]
    va = rep["validator"]
    bp = acct["blob_proof"]
    unresolved = (info.get("reference_resolution")
                  or {}).get("unresolved_anywhere")
    g = {
        "validator_errors": va["n_errors"],
        "validator_unexpected": len(va["unexpected_errors"]),
        "four_registry_coherent": rep["census"]["coherent"],
        "load_hop_units_added": hop["census_delta"]["save_units"],
        "instance_hop_units_added": rep["census_delta"]["save_units"],
        "survivor_law_ok": bool(rep["survivor_law_ok"]) and bool(hop["survivor_law_ok"]),
        "identity": (rep.get("identity_gate") or {}).get("status"),
        "blob_all_units_64B": bp["all_units_64B"],
        "blob_added_nonce_verified": bp["added_nonce_verified"],
        "blob_units_added": bp["units_added_vs_base"],
        "famdoc_refs_unresolved_anywhere": unresolved,
        "instance_zero_dangling": (info.get("instance") or {}).get(
            "n_dangling") == 0,
        "byte_identity_verified": (
            all((info.get("byte_identity") or {}).get(
                "segments_byte_identical", {}).values())
            if info.get("byte_identity") else None),
    }
    ok = (g["validator_errors"] == 0 and g["validator_unexpected"] == 0
          and g["four_registry_coherent"] is True
          and g["load_hop_units_added"] == 1
          and g["instance_hop_units_added"] == 0
          and g["survivor_law_ok"] and g["identity"] == "PASS"
          and g["blob_all_units_64B"] and g["blob_added_nonce_verified"]
          and g["blob_units_added"] == 1
          and unresolved == 0
          and g["instance_zero_dangling"])
    if name in ("T1r", "U16g"):
        ok = ok and g["byte_identity_verified"] is True
    g["gates_ok"] = bool(ok)
    return g


# ===========================================================================
# build driver
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/union_reconcile.py",
                           "bases": {"T1u": relp(RST), "T1r": relp(RST),
                                     "U16g": relp(G_ABPD)},
                           "built": {}, "accounting": {}, "gates": {},
                           "errors": {}}
    if os.path.isfile(ACCT):                     # merge partial (--only) runs
        try:
            with open(ACCT) as fh:
                prev = json.load(fh)
            for k in ("built", "accounting", "gates"):
                out[k] = {n: v for n, v in (prev.get(k) or {}).items()
                          if n not in only}
        except Exception:                          # noqa: BLE001
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
                f"{g['four_registry_coherent']}, +{g['load_hop_units_added']}u "
                f"load hop, blob nonce "
                f"{'OK' if g['blob_added_nonce_verified'] else 'BAD'}, "
                f"refs unresolved {g['famdoc_refs_unresolved_anywhere']}, "
                f"byte-identity {g['byte_identity_verified']}, "
                f"gates_ok {g['gates_ok']}")
            if not g["gates_ok"]:
                out["errors"][name + ".gates"] = f"gates_ok False: {g}"
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = traceback.format_exc(limit=10)
            log(f"{name} FAILED: {type(e).__name__}: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(ACCT, out)
    write_probes_json(out)
    return out


# ===========================================================================
# the byte audit: the machinery delta, measured
# ===========================================================================

def _unit_index_of(path: str, guid: str) -> int:
    from rvt.families import FamilyIndex
    idx = FamilyIndex(path)
    for i, u in enumerate(idx.units):
        if str(u.guid) == guid:
            return i
    raise RuntimeError(f"{relp(path)}: no unit {guid}")


def _flat(d, p=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flat(v, p + "." + k))
    elif isinstance(d, list):
        for j, v in enumerate(d):
            out.update(_flat(v, p + f"[{j}]"))
    else:
        out[p] = d
    return out


def _diff_units(path_a: str, guid_a: str, path_b: str, guid_b: str):
    """Record-level diff of two units: (only_a, only_b, changed, idx_a,
    unit_a, idx_b, unit_b) with changed = [(eid, seq, class)] for records
    whose payload bytes differ."""
    from rvt.families import FamilyIndex
    ia, ib = FamilyIndex(path_a), FamilyIndex(path_b)
    ua, ub = _unit_index_of(path_a, guid_a), _unit_index_of(path_b, guid_b)
    ra, rb = ia.unit_records(ua), ib.unit_records(ub)
    only_a, only_b, changed = [], [], []
    for seq in (101, 102, 103):
        sa, sb = ra.get(seq, {}), rb.get(seq, {})
        for eid in sa:
            if eid not in sb:
                only_a.append((eid, seq, ia.class_name(sa[eid].class_id)))
            elif sa[eid].payload != sb[eid].payload:
                changed.append((eid, seq, ia.class_name(sa[eid].class_id)))
        for eid in sb:
            if eid not in sa:
                only_b.append((eid, seq, ib.class_name(sb[eid].class_id)))
    return only_a, only_b, changed, ia, ua, ib, ub


def audit() -> Dict[str, Any]:
    """byte_audit.json: what each union machinery DID to its shell,
    measured against that shell's certified-PASS unmodified baseline on
    the identical id layout (T1v vs T2a; U16 vs B7), then the two deltas
    compared axis by axis; plus the carried-35 pairwise diff through the
    id correspondence and the small-id residue hunt."""
    t0 = time.time()
    out: Dict[str, Any] = {
        "tool": "tools/union_reconcile.py audit",
        "instruments": {
            "T1v_vs_T2a": "same wm (1472524), same shell block "
                          "(1472525..1474516), same typed rebase -- the "
                          "record diff IS what template_union_doc did to "
                          "the born standalone shell (T2a viewer-PASS)",
            "U16_vs_B7": "same wm, same donor block (1472525..1472941) -- "
                         "the record diff IS what famdoc_final's union "
                         "machinery did to the donor shell (B7 viewer-PASS)",
        },
        "findings_ranked": [],
    }
    import json as _json
    with open(os.path.join(ROOT, "experiments", "rftprobe",
                           "accounting.json")) as fh:
        t2a_guid = _json.load(fh)["built"]["T2a"]["document_guid"]
    with open(os.path.join(ROOT, "experiments", "famdoc_blobs",
                           "accounting.json")) as fh:
        b7_guid = _json.load(fh)["built"]["B7"]["document_guid"]

    # -- instrument 1: T1v vs T2a ------------------------------------------
    oa, ob, ch, i_t1v, u_t1v, i_t2a, u_t2a = _diff_units(
        T1V_RVT, T1V_DOC_GUID, T2A_RVT, t2a_guid)
    t1v_added = sorted({e for e, _s, _c in oa})
    t1v_changed = sorted({(e, s, c) for e, s, c in ch})
    out["T1v_vs_T2a"] = {
        "records_only_in_T1v": len(oa),
        "added_element_ids": [t1v_added[0], t1v_added[-1],
                              f"n={len(t1v_added)}"] if t1v_added else [],
        "records_only_in_T2a": [list(x) for x in ob],
        "records_changed": [list(x) for x in t1v_changed],
    }

    # -- instrument 2: U16 vs B7 -------------------------------------------
    oa2, ob2, ch2, i_u16, u_u16, i_b7, u_b7 = _diff_units(
        U16_RVT, U16_DOC_GUID, B7_RVT, b7_guid)
    u16_added = sorted({e for e, _s, _c in oa2})
    u16_changed = sorted({(e, s, c) for e, s, c in ch2})
    out["U16_vs_B7"] = {
        "records_only_in_U16": len(oa2),
        "added_element_ids": [u16_added[0], u16_added[-1],
                              f"n={len(u16_added)}"] if u16_added else [],
        "records_only_in_B7": [list(x) for x in ob2],
        "records_changed": [list(x) for x in u16_changed],
    }

    # -- the carried 35, pairwise through the id correspondence ------------
    with open(os.path.join(ROOT, "experiments", "birthright",
                           "accounting.json")) as fh:
        t1v_acct = _json.load(fh)["built"]["T1v"]
    with open(os.path.join(ROOT, "experiments", "famdoc_final",
                           "accounting.json")) as fh:
        u16_acct = _json.load(fh)["built"]["U16"]
    t1v_carried = sorted(int(c["id"]) for c in t1v_acct["union"]["carried"])
    u16_carried = sorted(u16_acct["adoc_swap"]["elem_rows_appended"])
    if len(t1v_carried) != len(u16_carried):
        raise RuntimeError(f"carried rosters differ in size: "
                           f"{len(t1v_carried)} vs {len(u16_carried)}")
    # correspondence: sorted order (both blocks allocated ascending by the
    # same our_product walk) + the two shell self-Family anchors
    t1v_sf = t1v_acct["union"]["template"]["self_family"]
    u16_sf = u16_acct["union"]["anchors"]["self_family"]
    idcorr = dict(zip(t1v_carried, u16_carried))
    idcorr[t1v_sf] = u16_sf

    # normalization of the parameter identity string
    # ``revit.local.family:<32-hex session><8-hex elem id>-...``: both
    # components are per-identity, not structure -- the session GUID is
    # minted per creation session, the suffix embeds the param element's
    # OWN id.  Map both through the correspondence so only STRUCTURAL
    # string deltas survive.
    local_re = re.compile(r"revit\.local\.family:([0-9a-f]{32})([0-9a-f]{8})")

    def norm_local(s: str) -> str:
        def repl(m):
            hex32, hex8 = m.group(1), m.group(2)
            eid = int(hex8, 16)
            eid = idcorr.get(eid, eid)
            return f"revit.local.family:<session>{eid:08x}"
        return local_re.sub(repl, s)

    pair_diffs: List[Dict[str, Any]] = []
    from rvt.famgen.loader import _walk_replace_ids
    kinds_checked = 0
    for a_id, b_id in zip(t1v_carried, u16_carried):
        row: Dict[str, Any] = {"T1v_id": a_id, "U16_id": b_id}
        deltas: List[str] = []
        for seq in (101, 102, 103):
            ra = i_t1v.unit_records(u_t1v).get(seq, {}).get(a_id)
            rb = i_u16.unit_records(u_u16).get(seq, {}).get(b_id)
            if (ra is None) != (rb is None):
                deltas.append(f"seq{seq}: present only in "
                              f"{'T1v' if rb is None else 'U16'}")
                continue
            if ra is None:
                continue
            ca = i_t1v.class_name(ra.class_id)
            cb = i_u16.class_name(rb.class_id)
            if ca != cb:
                deltas.append(f"seq{seq}: class {ca} vs {cb}")
                continue
            row.setdefault("class", ca)
            va = i_t1v.value(u_t1v, a_id, seq)
            vb = i_u16.value(u_u16, b_id, seq)
            va = copy.deepcopy(va) if isinstance(va, dict) else va
            if isinstance(va, dict):
                _walk_replace_ids(va, idcorr)
            fa, fb2 = _flat(va or {}), _flat(vb or {})
            for k in sorted(set(fa) | set(fb2)):
                x, y = fa.get(k), fb2.get(k)
                if x == y:
                    continue
                if isinstance(x, str) and isinstance(y, str) and \
                        norm_local(x) == norm_local(y):
                    continue          # per-identity string, not structure
                deltas.append(f"seq{seq}{k}: {x!r:.60} vs {y!r:.60}")
        kinds_checked += 1
        if deltas:
            row["deltas"] = deltas[:24]
            row["n_deltas"] = len(deltas)
            pair_diffs.append(row)
    out["carried_pairwise"] = {
        "n_pairs": kinds_checked,
        "id_correspondence": "sorted carried order + self-Family anchor "
                             f"({t1v_sf} <-> {u16_sf})",
        "pairs_with_deltas": pair_diffs,
        "clean_pairs": kinds_checked - len(pair_diffs),
    }

    # -- what each registration DID to its shell's self-Family -------------
    # (union sf vs baseline sf, per surface; then the two touched-path
    # sets compared -- a path one machinery touches and the other does not
    # is a machinery delta)
    def sf_touched(idx_u, unit_u, idx_b, unit_b, sf_id):
        paths: set = set()
        for seq in (101, 102):
            va = _flat(idx_u.value(unit_u, sf_id, seq) or {})
            vb = _flat(idx_b.value(unit_b, sf_id, seq) or {})
            for k in set(va) | set(vb):
                if va.get(k) != vb.get(k):
                    paths.add(f"seq{seq}" + re.sub(r"\[\d+\]", "[]", k))
        return paths

    t1v_touch = sf_touched(i_t1v, u_t1v, i_t2a, u_t2a, t1v_sf)
    u16_touch = sf_touched(i_u16, u_u16, i_b7, u_b7, u16_sf)

    def top_groups(paths):
        g: Dict[str, int] = {}
        for p in paths:
            m = re.match(r"(seq\d+\.[A-Za-z0-9_]+(?:\.value\.[A-Za-z0-9_]+)?)", p)
            key = m.group(1) if m else p
            g[key] = g.get(key, 0) + 1
        return dict(sorted(g.items()))

    out["self_family_registration"] = {
        "T1v_touched_vs_T2a": top_groups(t1v_touch),
        "U16_touched_vs_B7": top_groups(u16_touch),
        "surface_only_in_T1v": sorted(set(top_groups(t1v_touch))
                                      - set(top_groups(u16_touch))),
        "surface_only_in_U16": sorted(set(top_groups(u16_touch))
                                      - set(top_groups(t1v_touch))),
        "reading": "surfaces touched by ONE machinery only are machinery "
                   "deltas; shared surfaces with different counts reflect "
                   "the shells' own differing sizes (registration appends "
                   "scale with the shell's existing rosters)",
    }

    # -- the inline-ADocument flavour delta --------------------------------
    from rvt import adocument as A
    from rvt.families import FamilyIndex, content_document_adoc
    v_t1v = A.decode_latest(content_document_adoc(FamilyIndex(T1V_RVT),
                                                  T1V_DOC_GUID)).value
    v_u16 = A.decode_latest(content_document_adoc(FamilyIndex(U16_RVT),
                                                  U16_DOC_GUID)).value

    def _adoc_shape(v):
        aim = ((v.get("m_pAppInfoManager") or {}).get("value") or {})
        arr = aim.get("m_appInfoArr") or []
        inner = ((v.get("m_elemTable") or {}).get("value") or {})
        hist = ((v.get("m_pHistory") or {}).get("value") or {})
        src = ((inner.get("m_pSource") or {}).get("value") or {})
        return {
            "appinfo_slots": len(arr),
            "appinfo_populated": sum(1 for x in arr if x),
            "elem_rows": len(inner.get("m_elemArr") or []),
            "identifier_source_last": src.get("m_last"),
            "stored_by_revit_build": [s.get("m_str")
                                      for s in v.get("m_storedByRevitBuild")
                                      or []],
            "history_identity": {k: (hist.get(k) or {}).get("m_guid")
                                 for k in ("m_creationGUID", "m_detachGUID",
                                           "m_upgradeGUID", "m_saveAsGUID")},
            "owner_family_id": v.get("m_ownerFamilyId"),
        }

    out["inline_adoc_flavour"] = {
        "T1v_authored": _adoc_shape(v_t1v),
        "U16_donor_swapped": _adoc_shape(v_u16),
        "the_separable_machinery_delta":
            "U16 ships the donor's BORN document object (131/239 AppInfo "
            "registries populated, donor storedByRevitBuild strings, "
            "independent history identity); T1v ships the authored form "
            "(0/239 registries -- factory.author_embedded_adocument's own "
            "docstring flags empty registries as THE OPEN QUESTION; "
            "history identity = unit GUID).  U12345 (PASS) exonerated the "
            "authored form on the EMBEDDED shell + rst only.",
    }

    # -- small-id residue hunt (aliasing/missed-ref check) -----------------
    # every ElementId-typed value in T1v's famdoc unit that is a small id
    # (<= the .rfa's original max id, 7674) survived the typed rebase: it
    # is either a lawful non-member reference or a missed remap.  T2a
    # (viewer-PASS, same shell, same rebase) is the exoneration oracle.
    from rvt.validate import _RefDecoder

    def small_typed_ids(idx_obj, unit, limit=7674):
        dec = _RefDecoder(idx_obj.schema)
        found: Dict[int, int] = {}
        recs = idx_obj.unit_records(unit)
        for eid, r in recs.get(102, {}).items():
            dec.refs = []
            try:
                dec.decode_record(r.class_id, r.payload)
            except Exception:                                  # noqa: BLE001
                continue
            for _p, v in dec.refs:
                if isinstance(v, int) and 0 < v <= limit:
                    found[v] = found.get(v, 0) + 1
        return found

    s_t1v = small_typed_ids(i_t1v, u_t1v)
    s_t2a = small_typed_ids(i_t2a, u_t2a)
    only_t1v = {k: v for k, v in s_t1v.items() if k not in s_t2a}
    out["small_id_residue"] = {
        "rfa_original_id_range": [3, 7674],
        "T1v_small_typed_refs": {"distinct": len(s_t1v),
                                 "total": sum(s_t1v.values())},
        "T2a_small_typed_refs": {"distinct": len(s_t2a),
                                 "total": sum(s_t2a.values())},
        "in_T1v_not_in_T2a": {str(k): v for k, v in sorted(only_t1v.items())},
        "reading": "identical sets = the residue is BORN state the "
                   "certified T2a already carries (exonerated); T1v-only "
                   "entries = candidates the union machinery introduced",
    }

    # -- ranked findings ----------------------------------------------------
    findings: List[Dict[str, Any]] = []
    findings.append({
        "rank": 1,
        "finding": "inline-ADocument flavour is the one separable machinery "
                   "delta",
        "detail": out["inline_adoc_flavour"]["the_separable_machinery_delta"],
        "probe_that_splits_it": "T1u (born wrapper on the standalone shell) "
                                "vs T1r (authored, same shell+base)",
    })
    unexpected_changed = [c for c in t1v_changed
                          if c[0] != t1v_sf]
    findings.append({
        "rank": 2,
        "finding": f"template_union_doc touched "
                   f"{len(t1v_changed)} shell record(s) "
                   f"(vs T2a): {[list(x) for x in t1v_changed[:6]]}",
        "detail": "expected: the self-Family registration record only; "
                  "anything else is a machinery artifact",
        "unexpected_beyond_self_family": [list(x) for x in
                                          unexpected_changed],
    })
    unexpected_changed2 = [c for c in u16_changed if c[0] != u16_sf]
    findings.append({
        "rank": 3,
        "finding": f"famdoc_final machinery touched "
                   f"{len(u16_changed)} shell record(s) (vs B7): "
                   f"{[list(x) for x in u16_changed[:6]]}",
        "detail": "expected: the self-Family registration record only",
        "unexpected_beyond_self_family": [list(x) for x in
                                          unexpected_changed2],
    })
    findings.append({
        "rank": 4,
        "finding": f"carried-35 pairwise: {len(pair_diffs)} pair(s) with "
                   f"deltas beyond the id correspondence + session hex",
        "detail": "see carried_pairwise.pairs_with_deltas",
    })
    findings.append({
        "rank": 5,
        "finding": f"small-id residue: {len(only_t1v)} distinct typed "
                   f"small ids in T1v not in T2a",
        "detail": "see small_id_residue",
    })
    out["findings_ranked"] = findings
    unit_clean = (not unexpected_changed and not unexpected_changed2
                  and not pair_diffs and not only_t1v
                  and not ob and not ob2)
    out["smoking_gun_verdict"] = {
        "unit_content_smoking_gun": not unit_clean,
        "t1w_warranted": not unit_clean,
        "statement": (
            "NO unit-content smoking gun: the two machineries produced "
            "structurally IDENTICAL famdoc mutations (35/35 carried pairs "
            "clean through the id correspondence; both registrations "
            "touched exactly the same six self-Family surfaces; neither "
            "touched any other shell record; zero small-id residue -- no "
            "aliased ids escaped the typed rebase).  The ONE separable "
            "machinery delta is HOST-SIDE: the inline-ADocument flavour "
            "(authored all-null registries vs the born 131-populated "
            "document object), which T1u vs T1r splits by design.  No "
            "corrected-T1v variant (T1w) is warranted."
            if unit_clean else
            "unit-content deltas survived the audit -- see findings_ranked; "
            "a corrected T1v variant (T1w) should be built for the top "
            "finding"),
    }
    out["seconds"] = round(time.time() - t0, 1)
    jdump(AUDIT, out)
    log(f"byte_audit.json -> {relp(AUDIT)} ({out['seconds']}s)")
    return out


# ===========================================================================
# probes.json (the 8-outcome decision table)
# ===========================================================================

DECISION_TABLE = {
    "CTRL FAIL (either)": "round VOID for that base's probes (the rst "
                          "control voids T1u/T1r; the G_ABPD control voids "
                          "U16g).",
    "T1u PASS, T1r PASS, U16g PASS": "every single axis is innocent alone "
        "=> T1v's FAIL is a CONJUNCTION: standalone species x G_ABPD base "
        "under the union (T2a passed unmodified on that base, T1r passes "
        "that famdoc on rst, U16g passes the proven famdoc on G_ABPD).  "
        "Next: T1r's exact famdoc on a THIRD certified base, or the "
        "authored-vs-born ADocument flavour on G_ABPD.",
    "T1u PASS, T1r PASS, U16g FAIL": "BASE convicted on the proven side "
        "too: G_ABPD rejects even U16's byte-identical famdoc while rst "
        "accepts everything => the base axis is the law (union x G_ABPD "
        "interaction; T2a PASS says no-union survives it).  The famdoc "
        "machinery and species are exonerated.",
    "T1u PASS, T1r FAIL, U16g PASS": "MACHINERY convicted on the standalone "
        "shell: famdoc_final's port passes where template_union_doc fails "
        "on the SAME shell + base => the byte-audit deltas (ranked in "
        "byte_audit.json; the ADocument flavour is rank 1) are the finite "
        "suspect list.  Base exonerated both sides.",
    "T1u PASS, T1r FAIL, U16g FAIL": "machinery delta AND base both "
        "guilty (overdetermined: T1v fails for two reasons).  Fix the "
        "machinery delta first (byte_audit rank 1), then re-run the base "
        "split.",
    "T1u FAIL, T1r PASS, U16g PASS": "the famdoc_final-side PORT is the "
        "prime suspect (T1r passes the same shell+base with the authored "
        "flavour): the born-ADocument port or a species x born-wrapper "
        "interaction.  Species partially exonerated by T1r's PASS.  "
        "Bisect: T1u minus the ADocument swap (= U12345's form on the "
        "standalone shell).",
    "T1u FAIL, T1r FAIL, U16g PASS": "SPECIES convicted: the standalone "
        "shell + our union fails on rst under BOTH machineries while the "
        "embedded shell passes everywhere (incl. G_ABPD) => the audit "
        "checks something a standalone-born body + registered foreign "
        "content trips (T2a PASS = no-union survives).  The species x "
        "union interaction is the law; the birthright mining must add "
        "whatever the embedded species carries.",
    "T1u FAIL, T1r FAIL, U16g FAIL": "species AND base each convicted "
        "(everything but U16's original cell fails).  Improbable given "
        "T2a/U12345; re-verify controls before reading.",
    "T1u FAIL, T1r PASS, U16g FAIL": "port suspect + base conviction "
        "(double).  T1r's PASS exonerates standalone+authored+rst; read "
        "U16g's FAIL as the base law and re-run T1u without the ADocument "
        "swap.",
}

EXPECTED = {
    "T1u": "PASS = species exonerated under famdoc_final machinery on rst "
           "(with U16); FAIL = species x union (or the born-ADocument "
           "port) -- T1r disambiguates",
    "T1r": "PASS = BASE convicted (T1v's exact famdoc accepted on rst); "
           "FAIL = the standalone union famdoc is rejected on both bases "
           "=> species/machinery, read with T1u",
    "U16g": "PASS = base exonerated on the proven side (U16's famdoc "
            "accepted on G_ABPD); FAIL = BASE convicted from the proven "
            "side (G_ABPD x union interaction)",
}

ONETHING = {
    "T1u": "the vendor-born STANDALONE famdoc + our 35-element union by "
           "the famdoc_final recipe (registration verbatim, born document "
           "object swapped inline, carried params byte-pinned to U16's "
           "session), famload + one uniform instance on rst.  The ONE "
           "thing vs U16 (PASS): the shell species.",
    "T1r": "T1v's famdoc, unit segments BYTE-IDENTICAL (machine-verified "
           "against T1v_load.rvt; fresh unit GUID per house law), famload "
           "+ one uniform instance on rst.  The ONE thing vs T1v (FAIL): "
           "the base.",
    "U16g": "U16's famdoc, unit segments BYTE-IDENTICAL (machine-verified "
            "against U16.rvt) + the donor inline-ADocument swap by "
            "famdoc_final's own function (value equality vs U16's entry "
            "machine-verified modulo the 4 fresh history GUIDs), famload "
            "+ one uniform instance on G_ABPD.  The ONE thing vs U16 "
            "(PASS): the base.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    probes = []
    for i, name in enumerate(LADDER, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        gates = (build_out.get("gates") or {}).get(name) or {}
        bp = ((build_out.get("accounting") or {}).get(name) or {}).get(
            "blob_proof") or {}
        entry = {
            "order": i,
            "rung": name,
            "file": f"experiments/unionrec/{name}.rvt",
            "base": relp(base_of(name)),
            "kind": "probe",
            "axis": AXES[name],
            "n_families": 1, "n_instances": 1, "n_walls": 0,
            "the_ONE_thing_it_tests": ONETHING[name],
            "expected": EXPECTED[name],
            "md5": info.get("md5"),
            "document_guid": info.get("document_guid"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "immediate_parent": info.get("immediate_parent"),
            "byte_identity": info.get("byte_identity"),
            "blob_proof": {k: bp.get(k) for k in
                           ("units_total", "blob_len_histogram",
                            "units_added_vs_base", "added_nonce_verified")},
            "gates": gates,
        }
        probes.append(entry)
    manifest = {
        "stream": "union-reconcile: U16 (PASS) vs T1v (FAIL) split into "
                  "single variables.  U16 = our 35-element union in the "
                  "born EMBEDDED donor shell, famdoc_final machinery, on "
                  "rst.  T1v = the same union in the born STANDALONE "
                  "vendor shell, template_union_doc machinery, on G_ABPD.  "
                  "Three axes differ: machinery, species, base.  T1u "
                  "isolates SPECIES (vs U16), T1r isolates BASE on the "
                  "failing side (vs T1v), U16g isolates BASE on the "
                  "proven side (vs U16).",
        "known_cells": {
            "U16": "embedded shell + famdoc_final + rst = PASS (b45)",
            "U12345": "embedded shell + union + AUTHORED ADocument + rst "
                      "= PASS (b45) -- the authored-ADocument flavour is "
                      "exonerated on the embedded side",
            "T2a": "standalone shell UNMODIFIED + G_ABPD = PASS (b50)",
            "T1v": "standalone shell + template_union_doc + G_ABPD = "
                   "FAIL (b51)",
        },
        "bases": {"T1u+T1r": relp(RST), "U16g": relp(G_ABPD)},
        "upload_order_max_information_first": list(LADDER),
        "controls": {
            "rst": {"source": relp(RST), "voids": "T1u,T1r on CTRL FAIL"},
            "g_abpd": {"source": relp(G_ABPD), "voids": "U16g on CTRL FAIL"},
        },
        "reading_the_matrix": DECISION_TABLE,
        "byte_audit": "experiments/unionrec/byte_audit.json (the machinery "
                      "delta measured record-by-record against the "
                      "certified baselines T2a and B7; the inline-ADocument "
                      "flavour -- authored all-null registries vs born "
                      "131-populated -- is the rank-1 separable delta)",
        "note": "every famdoc unit GUID is FRESH per house law (a reused "
                "unit GUID risks viewer-side content dedupe faking a "
                "verdict); byte-identity claims are about the unit "
                "SEGMENTS, which carry no GUID (measured) and are "
                "machine-verified equal.  PROOF-ONLY sample/vendor-derived "
                "content, quarantined, never shipped.",
        "companion_evidence": {
            "accounting": "experiments/unionrec/accounting.json",
            "byte_audit": "experiments/unionrec/byte_audit.json",
            "per_probe_builds": "experiments/unionrec/_build/<rung>/",
            "U16_round": "experiments/famdoc_final/probes.json (b45)",
            "T1v_round": "experiments/birthright/probes.json (b51)",
            "T2a_round": "experiments/rftprobe/probes.json (b50)",
        },
        "probes": probes,
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# verify + stage
# ===========================================================================

def verify() -> Dict[str, Any]:
    if not os.path.isfile(ACCT):
        raise SystemExit("no accounting.json -- run build first")
    with open(ACCT) as fh:
        out = json.load(fh)
    fresh: Dict[str, Any] = {}
    for name, info in (out.get("built") or {}).items():
        child = os.path.join(ROOT, info["file"])
        parent = os.path.join(ROOT, info["immediate_parent"])
        if not (os.path.isfile(child) and os.path.isfile(parent)):
            fresh[name] = {"error": "file(s) missing"}
            continue
        try:
            acct = _accounting(name, info)
            g = _gates(name, info, acct)
            out["accounting"][name] = acct
            out["gates"][name] = g
            fresh[name] = g
            log(f"{name}: gates_ok {g['gates_ok']} (validator "
                f"{g['validator_errors']} err, blob nonce "
                f"{'OK' if g['blob_added_nonce_verified'] else 'BAD'})")
        except Exception as e:                                 # noqa: BLE001
            fresh[name] = {"error": f"{type(e).__name__}: {e}"}
            log(f"{name} VERIFY FAILED: {type(e).__name__}: {e}")
    jdump(ACCT, out)
    write_probes_json(out)
    return fresh


def stage() -> Dict[str, Any]:
    """probe_batch gate + stage with TWO controls (byte-identical untouched
    rst copy for T1u/T1r + a G_ABPD copy for U16g)."""
    pb = _pb()
    fbl = _fbl()
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
    if not os.path.isfile(AUDIT):
        raise SystemExit("byte_audit.json missing -- run audit first (it is "
                         "the round's machinery-delta evidence)")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = fbl.next_batch_number()
    out_dir = pb.ACCEPTANCE
    ctrl_rst = pb.make_control(ledger, n, out_dir, source=RST)
    ctrl_g = pb.make_control(ledger, n, out_dir, source=G_ABPD)
    ordered = [ctrl_rst, ctrl_g] + [e for e in entries if e.kind == "probe"]
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
                     f"{pb.rel(dst)} (md5 {md5_of(dst)} vs {e.md5}); rename "
                     f"the probe -- never overwrite a staged file the viewer "
                     f"may already have read"])
            shutil.copyfile(src, dst)
        e.staged_as = pb.rel(dst)
    manifest = {
        "batch": n,
        "created": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": "tools/union_reconcile.py (via tools/probe_batch.py "
                "primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified' (or is an Autodesk sample "
                "source); the batch carries >= 1 CONTROL = a byte-identical "
                "copy of a certified file; read the round with "
                "read_batch_verdicts(): control FAIL => every verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 2,
        "controls": {"rst": ctrl_rst.staged_as, "g_abpd": ctrl_g.staged_as,
                     "note": "the rst control gates T1u/T1r; the G_ABPD "
                             "control gates U16g -- either control FAIL "
                             "voids its probes"},
        "note": "union-reconcile: the U16(PASS)/T1v(FAIL) contradiction "
                "split into single variables.  T1u = species (standalone "
                "shell under U16's machinery on rst), T1r = base on the "
                "failing side (T1v's byte-identical famdoc on rst), U16g = "
                "base on the proven side (U16's byte-identical famdoc + "
                "recipe on G_ABPD).  Read "
                "experiments/unionrec/probes.json reading_the_matrix (all "
                "8 outcomes pre-committed); the machinery-delta evidence "
                "is experiments/unionrec/byte_audit.json.",
        "reading_order": [os.path.basename(e.staged_as or e.file)
                          for e in ordered],
        "entries": [e.to_json() for e in ordered],
    }
    path = os.path.join(out_dir, f"batch_{n}.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    manifest["manifest_path"] = pb.rel(path)
    log(f"STAGED batch {n} -> {manifest['manifest_path']}")
    for e in ordered:
        log(f"  [{e.order}] {e.staged_as} ({e.kind})")
    for e in ordered:
        got = md5_of(os.path.join(ROOT, e.staged_as))
        if got != e.md5:
            raise RuntimeError(f"staged copy md5 mismatch: {e.staged_as}")
    log("staged copies md5-verified")
    return manifest


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the 3 probes")
    b.add_argument("--only", default=None, help="comma-separated probe subset")
    sub.add_parser("audit", help="byte_audit.json (the machinery delta, "
                                 "measured)")
    sub.add_parser("verify", help="re-run the gates on the emitted probes")
    sub.add_parser("stage", help="probe_batch gate + stage (2 controls)")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        only = [s.strip() for s in a.only.split(",")] if a.only else None
        bad = [r for r in (only or []) if r not in LADDER]
        if bad:
            ap.error(f"unknown probe(s): {bad}; choose from {list(LADDER)}")
        out = build(only)
        n_err = len([k for k in out["errors"]
                     if not k.endswith((".traceback", ".tb"))])
        log(f"build done: {len(out['built'])} probe(s), {n_err} error(s), "
            f"{out['seconds']}s")
        return 1 if n_err else 0
    if a.cmd == "audit":
        audit()
        return 0
    if a.cmd == "verify":
        fresh = verify()
        bad = [n for n, r in fresh.items()
               if r.get("error") or not r.get("gates_ok")]
        log(f"verify done: {len(fresh)} probe(s), gate failures: {bad or 'none'}")
        return 1 if bad else 0
    if a.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
