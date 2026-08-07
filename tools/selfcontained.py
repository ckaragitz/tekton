#!/usr/bin/env python
"""selfcontained.py -- THE CLOSE round (selfcontained stream, 2026-08-05).

THE CONVICTION IT SERVES (genesis-audit ORCHESTRATOR VERDICTS #45): b52
read CTRLs PASS, T1u PASS, T1r PASS (T1v's exact bytes on rst!), U16g FAIL
(U16's proven famdoc on G_ABPD!) -- machinery and species exonerated, the
axis is G_ABPD x loaded-famdoc.  This stream (a) enumerates the exact
famdoc->host reference surface of every failing famdoc and diffs the
targets rst-vs-G_ABPD field by field (HR1), (b) builds OUR panelboard
content in a famdoc whose walked style resolution never leaves the unit
(SC1: authored birth set + the born render-bind law), (c) splits the base
conviction WITHIN the compose stack (U16gK4 / U16gABP: U16's byte-
identical famdoc on the certified substrate K4 and on the pre-deletion
G_ABP), and (d) pre-builds DEMO v8 (the user's exact prompt through
birthright v2 self-contained authoring) so an SC1 PASS reading has the
demo verdict in the same round.

HR1'S MEASURED ANATOMY (2026-08-05, this session; full data in
experiments/selfcontained/hr1_report.json):

  * U16g (FAIL on G_ABPD): 29 seq-102 typed host refs + 23 seq-101 header
    (m_parents.m_deletion) refs + 51 seq-103 rep binds into the HOST --
    the embedded-donor species binds PROJECT style rows.  On the walk
    surface: the instanced form's Geometry style -> host GStyle 7845,
    6 face fillings -> GStyle 12632 + FillPattern 429, 6 face
    m_renderStyleId + ExtrusionElem.m_materialId + 7 Family refs ->
    MaterialElem 1177727.  EVERY target on G_ABPD is OUR SUBSTITUTED
    element (same class, same header bytes, value-level diffs: house
    colors/pens/names; m_cellList dropped to None; the material's
    appearance asset STRIPPED to m_appearanceAssetId=-1 with 0
    properties).  On rst the same ids are the born originals.
  * T2a (PASS on G_ABPD) really is fully self-contained on the walk
    surface: its instanced form binds IN-UNIT GStyle rows (solid style,
    face-fill style) and IN-UNIT materials.  Its 45 rep-level non-in-unit
    ids are UNREMAPPED BORN-INTERNAL ids (a T-lane rebase gap; 6
    coincidentally alias host rows incl. one deleted) -- TOLERATED, which
    calibrates the objection ranking: off-walk residue is not fatal.
  * T1v/B0/T0/BX_birth (FAIL on G_ABPD): ZERO host-resident refs on all
    four unit surfaces (seq-101/102 typed, seq-103 id walk, inline
    ADocument typed) -- our famdocs' form geometry binds NOTHING
    (m_categoryId -1, m_renderStyleId -1, m_materialId -1), so the walked
    style resolution falls through to the HOST's catalog.  T2a also
    carries the SAME authored-empty inline ADocument (0/239 registries)
    and the SAME dummy host reps and PASSES: flavour and lane are
    exonerated; the unbound-vs-in-unit-bound walk surface is the one
    measured separator left standing.

THE RANKED OBJECTION LIST (HR1; per-ref detail in the report JSON):
  1. face m_renderStyleId / m_materialId -> substituted MaterialElem
     1177727 whose appearance asset is stripped (asset -1, 0 properties)
     -- the most violent target diff on the walk surface (U16g).
  2. form Geometry/face-fill style binds -> substituted GStyle 7845/12632
     + FillPattern 429 (house values, cellList None) (U16g).
  3. OUR unbound (-1) form binds -- the same walk with no in-unit answer
     at all (every failing ours-content famdoc; the SC1 axis).
  4. host-side loader rows binding host styles (Family->category GStyle
     78/124, corpus symbol GElement 124, instance->Level 311/Phase 86961):
     T2a passes with the Family/instance shape => ranked low; the corpus
     GElement bind is dropped by SC1's T-lane anyway.
  5. off-walk view refs (RetouchTable 201/55150, sketch styles 69/111/
     193/23795, patterns 3/16/6473, header deletion lists): T2a's
     tolerated aliases + missing 3644 calibrate these as non-fatal.
ALTERNATIVE COMPOSE-SIDE FIX (per charter, ranked by the diff): repair
G_ABPD's substituted rows where they are IMPOVERISHED rather than merely
restyled -- (a) give the substituted MaterialElem a real in-file
appearance asset, (b) restore m_cellList on substituted style/pattern/
material rows (born rows carry it, ours write None), (c) close the
deleted-style holes (e.g. -2001265's rows, GStyle 3644).  That route
would admit host-bound famdocs (the U16g species) without
self-containment; SC1 tests the self-containment route this round.

THE 2025 CELL (charter U16g25) -- MEASURED BLOCKER, not built this round:
famload cannot walk 2025 framing (docs/inbox/compose-2025.md gap B:
``unexpected Partitions header: v=9 cls=0x391``), 4 of the famdoc's 77
classes have different 2025 layouts (BrowserOrganization, DBViewDrafting,
StructSettingsElem, Viewport) and the inline ADocument needs the port2025
adapt -- "U16's famdoc bytes" cannot ride verbatim and no 2025
famload/instance lane exists.  The base split ships instead on the SAME
format WITHIN the compose stack: U16gK4 (targets = born Autodesk rows on
the certified substrate) and U16gABP (targets = OUR substituted rows,
pre-deletion), against the b52 U16g cell (substituted + deletions).
2025 replication is the recorded follow-up once a 2025 famload exists.

USAGE (repo root, .venv/bin/python):
  tools/selfcontained.py census FILE --base BASE [--host HOST]
  tools/selfcontained.py hr1                  # the enumeration + diffs
  tools/selfcontained.py mine-binds           # render_binds.json sidecar
  tools/selfcontained.py build [--only SC1,U16gK4,U16gABP,DEMO_250v_room_v8]
  tools/selfcontained.py stage                # probe_batch + 3 controls
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_DIR = os.path.join(ROOT, "experiments", "selfcontained")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
PROBES = os.path.join(OUT_DIR, "probes.json")
HR1_REPORT = os.path.join(OUT_DIR, "hr1_report.json")
BINDS_PATH = os.path.join(OUT_DIR, "render_binds.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
K4 = os.path.join(ROOT, "experiments", "genesis", "triage", "K4.rvt")
G_ABP = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                     "G_ABP.rvt")
VENDOR_RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples",
                          "Autodesk", "racbasicsamplefamily-2026.rfa")
BIRTH_SPEC = os.path.join(ROOT, "experiments", "birthright",
                          "template_birth.json")
DEMO_PROMPT = "an electrical room rated for 250V with 6 panels"

LADDER = ("SC1", "U16gK4", "U16gABP", "DEMO_250v_room_v8")

_CACHE: Dict[str, Any] = {}


def log(msg: str) -> None:
    print(f"[selfcontained] {msg}", flush=True)


def relp(p: str) -> str:
    a = os.path.abspath(p)
    return os.path.relpath(a, ROOT) if a.startswith(ROOT) else a


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def _rp():
    if "rp" not in _CACHE:
        import rft_probe as RP
        _CACHE["rp"] = RP
    return _CACHE["rp"]


def _ur():
    """tools/union_reconcile.py with its output dirs repointed into THIS
    stream's territory (module attrs only; the union stream's own evidence
    is never touched)."""
    if "ur" not in _CACHE:
        import union_reconcile as UR
        UR.OUT_DIR = os.path.join(BUILD_DIR, "_ur")
        UR.BUILD_DIR = os.path.join(BUILD_DIR, "_ur", "_build")
        _CACHE["ur"] = UR
    return _CACHE["ur"]


def _fb():
    if "fb" not in _CACHE:
        import famdoc_bisect as FB
        FB.OUT_DIR = os.path.join(BUILD_DIR, "_fb")
        FB.BUILD_DIR = os.path.join(BUILD_DIR, "_fb", "_build")
        _CACHE["fb"] = FB
    return _CACHE["fb"]


def _fbl():
    if "fbl" not in _CACHE:
        import famdoc_blobs as FBL
        _CACHE["fbl"] = FBL
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
        import probe_batch as PB
        _CACHE["pb"] = PB
    return _CACHE["pb"]


class _Swapped:
    """Scoped module-attribute override (the catprobe/live-patch precedent)."""

    def __init__(self, obj: Any, **attrs: Any):
        self.obj, self.attrs, self.saved = obj, attrs, []

    def __enter__(self):
        for k, v in self.attrs.items():
            self.saved.append((k, getattr(self.obj, k)))
            setattr(self.obj, k, v)
        return self

    def __exit__(self, *exc):
        for k, v in reversed(self.saved):
            setattr(self.obj, k, v)
        return False


# ===========================================================================
# THE CENSUS -- every surface a famdoc unit can reference the host through
# ===========================================================================

def _typed_refs(idx, unit: int, seq: int) -> List[Tuple[int, str, int]]:
    """(owner, path, value) for every schema-typed ElementId in one seq of
    one unit (the famdoc_final/union_reconcile instrument, generalized to
    headers)."""
    from rvt.validate import _RefDecoder
    dec = _RefDecoder(idx.schema)
    refs: List[Tuple[int, str, int]] = []
    for eid, r in idx.unit_records(unit).get(seq, {}).items():
        dec.refs = []
        try:
            dec.decode_record(r.class_id, r.payload)
        except Exception:                                  # noqa: BLE001
            continue
        refs.extend((eid, p, v) for p, v in dec.refs
                    if isinstance(v, int))
    return refs


def _rep_id_walk(value: Any) -> List[Tuple[str, str, int]]:
    """(path, key, positive int) for every id-keyed scalar inside a decoded
    seq-103 rep ('Id' in key or key == 'm_id')."""
    out: List[Tuple[str, str, int]] = []

    def walk(o: Any, key: str, path: str) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, k, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, key, path + f"[{i}]")
        elif isinstance(o, int) and not isinstance(o, bool) and o > 0 \
                and ("Id" in key or key == "m_id"):
            out.append((path, key, o))

    walk(value, "", "")
    return out


def _adoc_typed_refs(idx, payload: bytes) -> List[Tuple[str, int]]:
    """Schema-typed ElementId census of an inline ADocument (the unit's
    ContentDocuments entry) via an ADocumentDecoder ref hook."""
    from rvt import adocument as A

    class _ARef(A.ADocumentDecoder):
        def __init__(self, schema):
            super().__init__(schema)
            ed = schema.by_name.get("ElementId")
            self.id_ElementId = ed.type_id if ed else None
            self.refs: List[Tuple[str, int]] = []

        def _decode_value_class(self, rd, type_id, queue, state, path):
            v = super()._decode_value_class(rd, type_id, queue, state, path)
            if type_id == self.id_ElementId:
                self.refs.append((path, v))
            return v

    dec = _ARef(idx.schema)
    A.decode_latest(payload, dec)
    return [(p, v) for p, v in dec.refs if isinstance(v, int)]


def _walked_binds_of_unit(idx, unit: int, member: set) -> Dict[str, Any]:
    """The instanced-walk bind surface of an EMITTED famdoc unit: every
    ExtrusionElem/CurveElem rep style bind + face render style, classified
    in_unit / unbound(-1) / foreign."""
    out = {"solid": [], "faces_render": [], "curves": [],
           "foreign": 0, "unbound_form": 0}
    cls_of = {e: idx.class_name(r.class_id)
              for e, r in idx.unit_records(unit).get(102, {}).items()}
    for eid, r in idx.unit_records(unit).get(103, {}).items():
        cname = cls_of.get(eid)
        if cname not in ("ExtrusionElem", "CurveElem"):
            continue
        o = idx.dec.decode_record(r.class_id, r.payload)
        v = getattr(o, "value", None) or {}
        if cname == "CurveElem":
            b = (v.get("m_GInfo") or {}).get("m_categoryId", -1)
            out["curves"].append(b)
            if isinstance(b, int) and b > 0 and b not in member:
                out["foreign"] += 1
            continue
        for sn in v.get("m_subNodes") or []:
            if not (isinstance(sn, dict) and sn.get("ptr_class") == "Geometry"):
                continue
            gv = sn.get("value") or {}
            b = (gv.get("m_GInfo") or {}).get("m_categoryId", -1)
            out["solid"].append(b)
            if b == -1:
                out["unbound_form"] += 1
            elif isinstance(b, int) and b > 0 and b not in member:
                out["foreign"] += 1
            for f in gv.get("m_pFaces") or []:
                fv = f.get("value") if isinstance(f, dict) else None
                if isinstance(fv, dict):
                    rr = fv.get("m_renderStyleId", -1)
                    out["faces_render"].append(rr)
                    if rr == -1:
                        out["unbound_form"] += 1
                    elif isinstance(rr, int) and rr > 0 and rr not in member:
                        out["foreign"] += 1
    out["self_contained"] = out["foreign"] == 0 and out["unbound_form"] == 0
    return out


def famdoc_census(probe: str, base: str, host: Optional[str] = None,
                  *, keep_rows: int = 200) -> Dict[str, Any]:
    """The FOUR-surface host-resident census of every save unit ``probe``
    adds over ``base`` (identified by unit GUID), plus the walked-bind
    census.  ``host`` defaults to ``base`` (the document the famdoc was
    loaded onto).  This is the machine-verify gate the charter demands:
    ``host_resident_total == 0`` and ``walked self_contained`` = the famdoc
    is self-contained."""
    from rvt.families import FamilyIndex, content_document_adoc
    from rvt.mutate import Document
    host = host or base
    pi, bi = FamilyIndex.open(probe), FamilyIndex.open(base)
    bguids = {u.guid for u in bi.units}
    host_ids = set(Document.from_file(host).et_by_id)
    out: Dict[str, Any] = {"probe": relp(probe), "base": relp(base),
                           "host": relp(host), "units": []}
    for u in pi.units:
        if u.guid in bguids or u.index == 0:
            continue
        member: set = set()
        for seq in (101, 102, 103):
            member |= set(pi.unit_records(u.index).get(seq, {}))
        unit: Dict[str, Any] = {"unit": u.index, "guid": u.guid,
                                "n_records_102":
                                    len(pi.unit_records(u.index).get(102, {}))}
        rows: List[Dict[str, Any]] = []
        totals = collections.Counter()
        for seq in (101, 102):
            for eid, p, v in _typed_refs(pi, u.index, seq):
                if v <= 0 or v in member:
                    continue
                kind = "host" if v in host_ids else "other"
                totals[f"seq{seq}_{kind}"] += 1
                if kind == "host" and len(rows) < keep_rows:
                    rows.append({"surface": f"seq{seq}", "owner": eid,
                                 "path": p[-70:], "target": v})
        for eid, r in pi.unit_records(u.index).get(103, {}).items():
            o = pi.dec.decode_record(r.class_id, r.payload)
            for p, k, v in _rep_id_walk(getattr(o, "value", None)):
                if v in member:
                    continue
                kind = "host" if v in host_ids else "other"
                totals[f"seq103_{kind}"] += 1
                if kind == "host" and len(rows) < keep_rows:
                    rows.append({"surface": "seq103", "owner": eid,
                                 "path": p[-70:], "key": k, "target": v})
        blob = content_document_adoc(pi, u.guid)
        if blob:
            for p, v in _adoc_typed_refs(pi, blob):
                if v <= 0 or v in member:
                    continue
                kind = "host" if v in host_ids else "other"
                totals[f"adoc_{kind}"] += 1
                if kind == "host" and len(rows) < keep_rows:
                    rows.append({"surface": "inline_adoc", "path": p[-80:],
                                 "target": v})
        else:
            unit["inline_adoc"] = "missing"
        unit["totals"] = dict(totals)
        unit["host_resident_total"] = sum(
            n for k, n in totals.items() if k.endswith("_host"))
        unit["host_resident_rows"] = rows
        unit["walked_binds"] = _walked_binds_of_unit(pi, u.index, member)
        out["units"].append(unit)
    out["host_resident_total"] = sum(u["host_resident_total"]
                                     for u in out["units"])
    out["walked_self_contained"] = all(
        u["walked_binds"]["self_contained"] for u in out["units"])
    out["self_contained"] = (out["host_resident_total"] == 0
                             and out["walked_self_contained"])
    return out


# ===========================================================================
# HR1 -- the enumeration + the field-by-field target diff
# ===========================================================================

HR1_PROBES = [
    ("U16g", "experiments/unionrec/U16g.rvt", G_ABPD),
    ("T1v", "experiments/birthright/T1v.rvt", G_ABPD),
    ("T2a", "experiments/rftprobe/T2a.rvt", G_ABPD),
    ("T1r", "experiments/unionrec/T1r.rvt", RST),
    ("B0", "experiments/famdoc_blobs/B0.rvt", G_ABPD),
    ("BX_birth", "experiments/birthright/BX_birth.rvt", G_ABPD),
    ("U16", "experiments/famdoc_final/U16.rvt", RST),
]

#: the referenced-target roster (union of every probe's host refs + the
#: host-row anchors measured in the HR1 session; see the module docstring)
HR1_TARGETS = [3, 16, 51, 69, 78, 81, 82, 87, 88, 111, 124, 193, 201, 311,
               429, 3644, 6473, 7845, 12632, 23795, 55150, 86961, 1177727]


def _leafdiff(a: Any, b: Any, path: str = "", out: Optional[list] = None,
              depth: int = 0) -> list:
    if out is None:
        out = []
    if depth > 14 or len(out) > 400:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _leafdiff(a.get(k), b.get(k), path + "/" + k, out, depth + 1)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path + "#len", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            _leafdiff(x, y, path + f"[{i}]", out, depth + 1)
    elif a != b:
        out.append((path, a, b))
    return out


def hr1_target_diffs(targets: Sequence[int] = HR1_TARGETS,
                     left: str = RST, right: str = G_ABPD) -> List[dict]:
    """Field-by-field diff of each referenced host target between two
    hosts (default: rst-vs-G_ABPD -- born original vs our substituted)."""
    from rvt.families import FamilyIndex
    li, ri = FamilyIndex.open(left), FamilyIndex.open(right)
    report = []
    for t in targets:
        lr = li.unit_records(0).get(102, {}).get(t)
        rr = ri.unit_records(0).get(102, {}).get(t)
        if rr is None:
            report.append({"target": t,
                           "class": li.class_name(lr.class_id) if lr else None,
                           "verdict": f"MISSING on {relp(right)}"})
            continue
        row: Dict[str, Any] = {"target": t,
                               "class": ri.class_name(rr.class_id)}
        same102 = lr is not None and lr.payload == rr.payload
        lh = li.unit_records(0).get(101, {}).get(t)
        rh = ri.unit_records(0).get(101, {}).get(t)
        row["bytes_same_102"] = same102
        row["bytes_same_101"] = (lh is not None and rh is not None
                                 and lh.payload == rh.payload)
        row["verdict"] = ("KEPT byte-identical" if same102
                          else "SUBSTITUTED (ours)")
        if not same102 and lr is not None:
            lv = li.dec.decode_record(lr.class_id, lr.payload).value
            rv = ri.dec.decode_record(rr.class_id, rr.payload).value
            diffs = _leafdiff(lv, rv)
            row["n_leaf_diffs"] = len(diffs)
            row["diffs"] = [{"path": p[-70:], "left": str(a)[:60],
                             "right": str(b)[:60]} for p, a, b in diffs[:16]]
        report.append(row)
    return report


def hr1() -> Dict[str, Any]:
    """The HR1 deliverable: per-probe four-surface censuses + the target
    diff table, written to experiments/selfcontained/hr1_report.json."""
    out: Dict[str, Any] = {"tool": "tools/selfcontained.py hr1",
                           "censuses": {}, "ranked_objections": []}
    for name, probe, base in HR1_PROBES:
        p = probe if os.path.isabs(probe) else os.path.join(ROOT, probe)
        if not os.path.isfile(p):
            out["censuses"][name] = {"missing": relp(p)}
            continue
        log(f"HR1 census {name}")
        out["censuses"][name] = famdoc_census(p, base)
    out["target_diffs_rst_vs_G_ABPD"] = hr1_target_diffs()
    out["ranked_objections"] = [
        {"rank": 1, "surface": "instanced-form face m_renderStyleId + "
                               "ExtrusionElem.m_materialId",
         "targets": [1177727],
         "objection": "substituted MaterialElem: appearance asset stripped "
                      "(m_appearanceAssetId -1, 0 properties, empty "
                      "materialPathMap) -- the walk renders faces through "
                      "an assetless material",
         "carried_by": ["U16g (host-bound)"],
         "ours_analog": "our famdocs bind -1 (no material at all)"},
        {"rank": 2, "surface": "instanced-form Geometry style + face "
                               "fillings",
         "targets": [7845, 12632, 429],
         "objection": "substituted GStyle/FillPattern rows (house colors/"
                      "pens/pattern geometry; m_cellList None where born "
                      "rows carry a CellList)",
         "carried_by": ["U16g"],
         "ours_analog": "our famdocs bind -1 -- resolution leaves the unit "
                        "with no answer"},
        {"rank": 3, "surface": "OUR unbound (-1) walk binds",
         "targets": [],
         "objection": "B0/T0/T1v/BX_birth emit m_categoryId -1 and "
                      "m_renderStyleId -1 on the walked form; the born law "
                      "binds in-unit rows (T2a).  SC1 flips exactly this.",
         "carried_by": ["B0", "T0", "T1v", "BX_birth", "DEMO v5/v7"]},
        {"rank": 4, "surface": "host-side loader rows",
         "targets": [78, 124, 311, 86961],
         "objection": "Family -> category GStyle, corpus symbol GElement "
                      "-> GStyle 124, instance -> Level/Phase -- all "
                      "substituted on G_ABPD; T2a PASSES with the Family/"
                      "instance shape (dummy symbol) => ranked low",
         "carried_by": ["every load; corpus GElement only on B0/BX_birth"]},
        {"rank": 5, "surface": "off-walk view/annotation refs + header "
                               "deletion lists + unremapped born-internal "
                               "rep ids",
         "targets": [201, 55150, 69, 111, 193, 23795, 3, 16, 6473, 3644],
         "objection": "T2a tolerates aliases onto substituted rows AND one "
                      "deleted target (3644) => calibrated non-fatal",
         "carried_by": ["U16g (real refs)", "T2a/T1v/T1r (aliases)"]},
    ]
    out["compose_side_alternative"] = (
        "repair the substituted rows the walk lands on instead of (or in "
        "addition to) self-containment: (a) author a real in-file "
        "appearance asset for substituted MaterialElem rows (today "
        "m_appearanceAssetId=-1 with the asset property list emptied); "
        "(b) author m_cellList on substituted style/pattern/material rows "
        "(born rows carry it; our writer drops it to None); (c) close "
        "deleted-style holes the deletion set left referenced (GStyle "
        "3644; category -2001265's rows).  Compose territory; ranked by "
        "the same diff table.")
    jdump(HR1_REPORT, out)
    log(f"HR1 report -> {relp(HR1_REPORT)}")
    return out


# ===========================================================================
# mine-binds -- the render-bind sidecar (born ids only, zero identity)
# ===========================================================================

def mine_binds(rfa: str = VENDOR_RFA, out_path: str = BINDS_PATH
               ) -> Dict[str, Any]:
    """Mine the born render-bind law from the vendor standalone specimen:
    which in-unit rows the instanced form's geometry binds.  Emits ONLY
    symbolic born ids (zero donor identity -- ids are coordinates, not
    content)."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex.open(rfa)
    solid_styles: set = set()
    fill_styles: set = set()
    sketch_styles: set = set()
    materials: List[int] = []
    ext_ids = idx.ids_of_class(0, "ExtrusionElem")
    if not ext_ids:
        raise SystemExit("mine-binds: specimen has no ExtrusionElem")
    for eid in ext_ids:
        r = idx.unit_records(0).get(103, {}).get(eid)
        if r is None:
            continue
        v = idx.dec.decode_record(r.class_id, r.payload).value or {}
        for sn in v.get("m_subNodes") or []:
            if not (isinstance(sn, dict) and sn.get("ptr_class") == "Geometry"):
                continue
            gv = sn.get("value") or {}
            b = (gv.get("m_GInfo") or {}).get("m_categoryId", -1)
            if b > 0:
                solid_styles.add(b)
            for f in gv.get("m_pFaces") or []:
                fv = f.get("value") if isinstance(f, dict) else None
                if not isinstance(fv, dict):
                    continue
                fill = (fv.get("m_pGFilling") or {}).get("value") or {}
                fb = (fill.get("m_GInfo") or {}).get("m_categoryId", -1)
                if fb > 0:
                    fill_styles.add(fb)
                rsid = fv.get("m_renderStyleId", -1)
                if rsid > 0:
                    materials.append(rsid)
    # sketch curves: every bound CurveElem style; the sketch style is the
    # one carrying the '<Sketch>' magenta (m_color 16711905 -- the
    # corpus-stable sketch-mode constant)
    for cid in idx.ids_of_class(0, "CurveElem"):
        rr = idx.unit_records(0).get(103, {}).get(cid)
        if rr is None:
            continue
        cv = idx.dec.decode_record(rr.class_id, rr.payload).value or {}
        cb = (cv.get("m_GInfo") or {}).get("m_categoryId", -1)
        if isinstance(cb, int) and cb > 0:
            sketch_styles.add(cb)
    # the sketch style: the modal CurveElem bind (the '<Sketch>' magenta
    # style, color 16711905 on the specimen) -- verify by GStyle color
    sketch_pick = None
    for sid in sorted(sketch_styles):
        v = idx.value(0, sid) or {}
        gs = (v.get("m_pGStyle") or {}).get("value") or {}
        if gs.get("m_color") == 16711905:
            sketch_pick = sid
            break
    if sketch_pick is None and sketch_styles:
        sketch_pick = sorted(sketch_styles)[0]
    if len(solid_styles) != 1 or len(fill_styles) != 1 or not materials \
            or sketch_pick is None:
        raise SystemExit(
            f"mine-binds: specimen law not singleton -- solid {solid_styles} "
            f"fill {fill_styles} sketch {sketch_styles} mats {materials}")
    out = {
        "version": 1,
        "tool": "tools/selfcontained.py mine-binds",
        "source": {"rfa": relp(rfa), "sha256": sha256_of(rfa),
                   "note": "DEV/PROOF-ONLY mining material; only born IDS "
                           "ride below (coordinates, not content)"},
        "law": ("the born instanced form binds IN-UNIT rows: solid Geometry "
                "GInfo -> the solid style; every face m_pGFilling GInfo -> "
                "the face-fill style; the form's sketch CurveElems -> the "
                "sketch style; every face m_renderStyleId (+ the "
                "ExtrusionElem's m_materialId) -> an in-unit MaterialElem "
                "[V this specimen + its T2a embedding, viewer-PASS]"),
        "binds": {
            "solid_style": {"__eid__": sorted(solid_styles)[0]},
            "face_fill_style": {"__eid__": sorted(fill_styles)[0]},
            "sketch_style": {"__eid__": int(sketch_pick)},
            "render_material": {"__eid__": int(materials[0])},
        },
        "specimen_materials_seen": sorted(set(materials)),
    }
    # every bind target must be in the authored birth set
    with open(BIRTH_SPEC) as fh:
        have = {e["born_id"] for e in json.load(fh)["birth_elements"]}
    missing = [r for r, n in out["binds"].items()
               if n["__eid__"] not in have]
    if missing:
        raise SystemExit(f"mine-binds: bind targets not in the authored "
                         f"birth set: {missing}")
    jdump(out_path, out)
    log(f"render binds -> {relp(out_path)}: "
        f"{ {k: v['__eid__'] for k, v in out['binds'].items()} }")
    return out


# ===========================================================================
# SC1 -- our content, self-contained, through the T2a-exact lane
# ===========================================================================

AXES = {
    "SC1": ("OUR 35-element panelboard content in a famdoc whose walked "
            "style resolution never leaves the unit: the authored birth "
            "set (1,683 elements incl. the full style catalog) + the born "
            "render-bind law (solid/face/sketch styles + render material "
            "bound to authored IN-UNIT rows), loaded by the T2a-EXACT "
            "lane (famload, dummy host symbol, authored inline ADocument) "
            "+ ONE uniform instance on G_ABPD.  The ONE thing vs T2a "
            "(PASS): the unit's content is OURS.  vs T0 (FAIL): the birth "
            "set + the binds.  vs BX_birth (FAIL): the binds + the lane."),
    "U16gK4": ("U16's byte-identical famdoc + full recipe on K4 -- the "
               "compose stack's SUBSTRATE (pure Autodesk empty skeleton, "
               "certified PASS).  Every famdoc->host ref lands on a BORN "
               "row.  PASS = the U16 recipe survives this lineage's "
               "skeleton; FAIL = composed-lineage conviction independent "
               "of our substitutions."),
    "U16gABP": ("U16's byte-identical famdoc + full recipe on G_ABP -- "
                "substitutions IN, deletions OUT (certified PASS).  Every "
                "famdoc->host ref lands on OUR SUBSTITUTED row; nothing "
                "referenced is deleted.  vs U16gK4: the substitution "
                "layer.  vs U16g (b52 FAIL): the deletion layer."),
    "DEMO_250v_room_v8": ("the user's exact prompt through birthright v2 "
                          "self-contained authoring: every generated "
                          "family carries the authored birth set + "
                          "in-unit render binds (machine-verified "
                          "self-contained famdocs), through the product "
                          "front door on G_ABPD.  vs DEMO v7 (FAIL): the "
                          "binds.  vs SC1: the product loader lane "
                          "(famgen chain + corpus symbol form) and "
                          "multi-family."),
}


def _spec():
    from rvt.famgen import birthright as BR
    if "spec" not in _CACHE:
        _CACHE["spec"] = BR.read_birth_spec(BIRTH_SPEC)
    return _CACHE["spec"]


def _binds():
    from rvt.famgen import birthright as BR
    if not os.path.isfile(BINDS_PATH):
        mine_binds()
    return BR.read_bind_spec(BINDS_PATH)


def build_sc1() -> Dict[str, Any]:
    """SC1 through the T-lane (T0's exact recipe + birthright with binds)."""
    rp = _rp()
    FB = _fb()
    fbl = _fbl()
    T = _room()
    from rvt.famgen import birthright as BR
    from rvt import famload as FL
    spec, binds = _spec(), _binds()
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "SC1")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "SC1.rvt")
    info: Dict[str, Any] = {"probe": "SC1", "axis": AXES["SC1"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256"),
                            "binds": {k: v["__eid__"] for k, v in
                                      (_binds().get("binds") or {}).items()}}
    products: Dict[str, Any] = {}

    def mk(start_id):
        prod = FB.our_product(start_id)
        products["SC1"] = prod
        return prod.doc

    src = os.path.join(pdir, "SC1_load.rvt")
    with BR.enabled(spec, binds=binds) as br_ctx:
        res = FL.load_family_documents(
            G_ABPD, [FL.FamilyLoad(key="SC1", builder=mk)], src,
            validate=True, report_path=src + ".load.json")
    if not res.ok:
        raise RuntimeError(f"SC1: famload failed: {res.stop_reason}")
    if not br_ctx["reports"]:
        raise RuntimeError("SC1: birthright never fired")
    ent = br_ctx["reports"][0]
    if not (ent.get("verify") or {}).get("ok"):
        raise RuntimeError("SC1: authored-vs-mined verify not ok")
    if not (ent.get("walked_bind_census") or {}).get("self_contained"):
        raise RuntimeError("SC1: doc-side walked binds not self-contained")
    info["birthright"] = {
        "n_added": ent.get("n_added"),
        "verify_ok": (ent.get("verify") or {}).get("ok"),
        "binds_bound": (ent.get("binds") or {}).get("bound"),
        "bind_targets": (ent.get("binds") or {}).get("targets"),
        "walked_bind_census": ent.get("walked_bind_census"),
    }
    p = res.plans[0]
    info["load"] = {"family_id": p.host_family_id, "symbol_id": p.symbol_id,
                    "guid": p.guid, "type_names": list(p.type_names or []),
                    "part_type": p.part_type}
    info["immediate_parent"] = relp(src)
    doc = products["SC1"].doc
    info["our_category"] = int(doc.category_id)
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    # the authored material's asset must resolve in-unit (rank-1 objection)
    idmap = None
    info["instance"] = rp.place_one(src, outp, host=G_ABPD,
                                    symbol_id=p.symbol_id,
                                    family_id=p.host_family_id,
                                    category=int(doc.category_id))
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["symbol_id"], info["family_id"] = p.symbol_id, p.host_family_id
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    # THE MACHINE GATE: the emitted unit's four-surface census
    info["self_containment"] = famdoc_census(outp, G_ABPD)
    if not info["self_containment"]["self_contained"]:
        raise RuntimeError(
            f"SC1 emitted unit is NOT self-contained: "
            f"host_resident_total="
            f"{info['self_containment']['host_resident_total']}, walked="
            f"{info['self_containment']['walked_self_contained']}")
    return info


# ===========================================================================
# U16gK4 / U16gABP -- the base ladder within the compose stack
# ===========================================================================

def build_u16g_on(name: str, base: str) -> Dict[str, Any]:
    """U16's byte-identical famdoc + full recipe (union_reconcile's U16g
    builder VERBATIM) with the base swapped to a certified sibling of the
    compose stack.  The builder's own gates all run: byte-identity pin to
    U16's unit, famdoc_refs (host-resident counted, unresolved refused),
    inline-ADocument diff vs U16's."""
    UR = _ur()
    os.makedirs(UR.OUT_DIR, exist_ok=True)
    os.makedirs(UR.BUILD_DIR, exist_ok=True)
    with _Swapped(UR, G_ABPD=base):
        info = UR.build_u16g()
        acct = UR._accounting("U16g", info)
        gates = UR._gates("U16g", info, acct)
    # move the artifacts into THIS stream's names
    built = os.path.join(UR.OUT_DIR, "U16g.rvt")
    outp = os.path.join(OUT_DIR, f"{name}.rvt")
    shutil.move(built, outp)
    for stage in ("U16g_load.rvt", "U16g_load.rvt.load.json",
                  "U16g_load_adoc.rvt"):
        s = os.path.join(UR.BUILD_DIR, "U16g", stage)
        if os.path.exists(s):
            d = os.path.join(BUILD_DIR, name)
            os.makedirs(d, exist_ok=True)
            shutil.move(s, os.path.join(d, stage.replace("U16g", name)))
    info["probe"] = name
    info["axis"] = AXES[name]
    info["base"] = relp(base)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    # re-point accounting paths that named the temporary location
    info["immediate_parent"] = relp(os.path.join(
        BUILD_DIR, name, f"{name}_load_adoc.rvt"))
    return {"info": info, "acct": acct, "gates": gates}


# ===========================================================================
# DEMO v8 -- the product path, self-contained authoring
# ===========================================================================

def build_demo_v8() -> Dict[str, Any]:
    """DEMO v7's exact recipe + the render-bind lane: the user's prompt
    end-to-end through rvt.frontdoor.run with birthright(binds) enabled."""
    rp = _rp()
    fbl = _fbl()
    from rvt.famgen import birthright as BR
    from rvt import famload_hostfix as HF
    from rvt.mutate import Document
    spec, binds = _spec(), _binds()
    rp._install_schema(G_ABPD)
    import ifc_intent  # noqa: F401
    from rvt.frontdoor.build import load_ifc_room_module
    load_ifc_room_module()
    from rvt import frontdoor as FD
    demo_dir = os.path.join(BUILD_DIR, "demo_v8")
    if os.path.isdir(demo_dir):
        shutil.rmtree(demo_dir)
    outp = os.path.join(OUT_DIR, "DEMO_250v_room_v8.rvt")
    info: Dict[str, Any] = {"probe": "DEMO_250v_room_v8",
                            "axis": AXES["DEMO_250v_room_v8"],
                            "base": relp(G_ABPD), "prompt": DEMO_PROMPT,
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256"),
                            "binds": {k: v["__eid__"] for k, v in
                                      (binds.get("binds") or {}).items()}}
    with BR.enabled(spec, binds=binds) as br_ctx:
        with HF.corpus_symbol_form():
            req = FD.AuthorRequest(prompt=DEMO_PROMPT, out=demo_dir,
                                   stem="DEMO_250v_room_v8",
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
        raise RuntimeError("DEMO v8: birthright never fired")
    bad = [x["family"] for x in reports
           if not (x.get("verify") or {}).get("ok")]
    if bad:
        raise RuntimeError(f"DEMO v8: authored-vs-mined verify not ok: {bad}")
    unbound = [x["family"] for x in reports
               if not (x.get("walked_bind_census") or {}).get(
                   "self_contained")]
    if unbound:
        raise RuntimeError(f"DEMO v8: walked binds not self-contained: "
                           f"{unbound}")
    info["n_birthright_applications"] = len(reports)
    info["n_families"] = len({x.get("family") for x in reports})
    info["binds_per_family"] = {x["family"]: (x.get("binds") or {}).get(
        "bound") for x in reports}
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
        raise RuntimeError(f"DEMO v8 symbol form check failed: "
                           f"{badf or 'no PP- symbols found'}")
    info["symbol_form_ok"] = {str(k): f["ok"] for k, f in forms.items()}
    info["immediate_parent"] = relp(G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    # THE MACHINE GATE on the emitted bytes: every added famdoc unit
    info["self_containment"] = famdoc_census(outp, G_ABPD)
    if not info["self_containment"]["self_contained"]:
        raise RuntimeError(
            f"DEMO v8 emitted units NOT self-contained: "
            f"host_resident_total="
            f"{info['self_containment']['host_resident_total']}, walked="
            f"{info['self_containment']['walked_self_contained']}")
    return info


# ===========================================================================
# accounting + gates (union_reconcile's instrument, reused)
# ===========================================================================

def _accounting(name: str, info: Dict[str, Any], base: str) -> Dict[str, Any]:
    B = _bisect()
    fbl = _fbl()
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


def _gates(name: str, info: Dict[str, Any], acct: Dict[str, Any]
           ) -> Dict[str, Any]:
    rep = acct["probe"]
    va = rep["validator"]
    bp = acct["blob_proof"]
    hop = acct.get("hop_load")
    sc = info.get("self_containment") or {}
    g: Dict[str, Any] = {
        "validator_errors": va["n_errors"],
        "validator_unexpected": len(va["unexpected_errors"]),
        "four_registry_coherent": rep["census"]["coherent"],
        "survivor_law_ok": bool(rep["survivor_law_ok"]) and (
            hop is None or bool(hop["survivor_law_ok"])),
        "identity": (rep.get("identity_gate") or {}).get("status"),
        "blob_all_units_64B": bp["all_units_64B"],
        "blob_added_nonce_verified": bp["added_nonce_verified"],
        "instance_zero_dangling": all(
            (x or {}).get("n_dangling", 1) == 0
            for x in [info.get("instance")]) if info.get("instance")
        else None,
        "self_contained": sc.get("self_contained"),
        "host_resident_total": sc.get("host_resident_total"),
    }
    if hop is not None:
        g["load_hop_units_added"] = hop["census_delta"]["save_units"]
        g["instance_hop_units_added"] = rep["census_delta"]["save_units"]
    ok = (g["validator_errors"] == 0 and g["validator_unexpected"] == 0
          and g["four_registry_coherent"] is True
          and g["survivor_law_ok"] and g["identity"] == "PASS"
          and g["blob_all_units_64B"] and g["blob_added_nonce_verified"])
    if name in ("SC1", "DEMO_250v_room_v8"):
        ok = ok and g["self_contained"] is True \
            and g["host_resident_total"] == 0
    if name == "SC1":
        ok = ok and g.get("load_hop_units_added") == 1 \
            and g.get("instance_hop_units_added") == 0 \
            and g["instance_zero_dangling"] is True
    g["gates_ok"] = bool(ok)
    return g


# ===========================================================================
# build driver + probes.json + stage
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/selfcontained.py",
                           "bases": {"SC1": relp(G_ABPD),
                                     "U16gK4": relp(K4),
                                     "U16gABP": relp(G_ABP),
                                     "DEMO_250v_room_v8": relp(G_ABPD)},
                           "built": {}, "accounting": {}, "gates": {},
                           "errors": {}}
    if os.path.isfile(ACCT):
        try:
            with open(ACCT) as fh:
                prev = json.load(fh)
            for k in ("built", "accounting", "gates"):
                out[k] = {n: v for n, v in (prev.get(k) or {}).items()
                          if n not in only}
        except Exception:                                  # noqa: BLE001
            pass
    for name in only:
        log(f"build {name}")
        try:
            if name == "SC1":
                info = build_sc1()
                acct = _accounting(name, info, G_ABPD)
                gates = _gates(name, info, acct)
            elif name == "U16gK4":
                r = build_u16g_on(name, K4)
                info, acct, gates = r["info"], r["acct"], r["gates"]
            elif name == "U16gABP":
                r = build_u16g_on(name, G_ABP)
                info, acct, gates = r["info"], r["acct"], r["gates"]
            elif name == "DEMO_250v_room_v8":
                info = build_demo_v8()
                acct = _accounting(name, info, G_ABPD)
                gates = _gates(name, info, acct)
            else:
                raise SystemExit(f"unknown probe {name}")
            out["built"][name] = info
            out["accounting"][name] = acct
            out["gates"][name] = gates
            log(f"  {name}: gates_ok={gates['gates_ok']} md5={info['md5']}")
        except Exception as e:                             # noqa: BLE001
            import traceback
            out["errors"][name] = {"error": str(e),
                                   "trace": traceback.format_exc()[-2000:]}
            log(f"  {name} FAILED: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(ACCT, out)
    write_probes_json(out)
    return out


READING = {
    "CTRL FAIL (any)": "that base's probes are VOID -- interpret nothing "
                       "built on it.",
    "SC1 PASS": "THE LAW CONFIRMED: the composed base accepts OUR famdoc "
                "once its walked style resolution stays in-unit.  The fix "
                "is specified = birthright v2 self-contained authoring "
                "(birth set + render binds).  Read DEMO v8 immediately.",
    "SC1 FAIL": "self-containment is NOT sufficient: with T2a as the "
                "PASSing control shape, the remaining delta vs T2a is the "
                "unit content AUTHORSHIP itself (our records) x this "
                "base.  Next instruments: the U16gK4/U16gABP split below "
                "+ the desktop-Revit kit (experiments/terminal/"
                "REVIT-CHECK-KIT.md); a 2025-lane famload port would "
                "extend the split cross-lineage.",
    "U16gK4 PASS + U16gABP FAIL": "SUBSTITUTION-LAYER conviction at the "
                                  "famdoc->host surface: born targets "
                                  "accepted, our substituted targets "
                                  "rejected.  The compose-side fix "
                                  "(hr1_report.json "
                                  "compose_side_alternative) is the "
                                  "specified repair; rank 1 = the "
                                  "stripped material appearance asset.",
    "U16gK4 PASS + U16gABP PASS": "DELETION-LAYER conviction: the U16 "
                                  "recipe survives substituted targets; "
                                  "only the deletion set's holes kill it "
                                  "(b52 U16g FAIL had deletions).  Fix = "
                                  "close the referenced holes (3644, "
                                  "-2001265 rows) or re-compose without "
                                  "deleting referenced style rows.",
    "U16gK4 FAIL": "LINEAGE conviction independent of substitution: the "
                   "composed skeleton itself rejects the loaded-famdoc "
                   "recipe that rst accepts byte-identically.  The "
                   "compose stack (not our content) is the axis; "
                   "replicate on 2025/2024 once a famload lane exists "
                   "there.",
    "SC1 PASS + DEMO v8 PASS": "THE CAMPAIGN CLOSES: promote "
                               "birthright.enabled(spec, binds) to the "
                               "famgen emission default; rebuild "
                               "acceptance.",
    "SC1 PASS + DEMO v8 FAIL": "the law holds but the product lane "
                               "differs: enumerated deltas = famgen "
                               "loader chain (vs famload), corpus symbol "
                               "GElement binding host GStyle 124 on the "
                               "host side, multi-family (6 units), "
                               "walls.  Bisect: v8 through the T-lane, "
                               "then corpus_symbol_form off.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    probes = []
    order = {"SC1": 1, "U16gK4": 2, "U16gABP": 3, "DEMO_250v_room_v8": 4}
    for name in LADDER:
        info = (build_out.get("built") or {}).get(name)
        if not info:
            continue
        gates = (build_out.get("gates") or {}).get(name) or {}
        probes.append({
            "order": order[name],
            "rung": name,
            "file": info["file"],
            "base": info["base"],
            "kind": "probe",
            "axis": info["axis"],
            "the_ONE_thing_it_tests": info["axis"],
            "md5": info["md5"],
            "document_guid": info.get("document_guid"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "n_instances": len(info.get("instance_ids") or []),
            "n_walls": info.get("n_walls", 0),
            "immediate_parent": info.get("immediate_parent"),
            "blob_proof": info.get("blob_proof"),
            "gates": gates,
            "self_containment": {
                k: (info.get("self_containment") or {}).get(k)
                for k in ("host_resident_total", "walked_self_contained",
                          "self_contained")},
        })
    man = {
        "stream": ("selfcontained: THE CLOSE.  Verdict #45 convicted "
                   "G_ABPD x loaded-famdoc; HR1 (hr1_report.json) "
                   "enumerated the famdoc->host surface and measured that "
                   "T2a's walked binds stay in-unit while every failing "
                   "ours-content famdoc either binds host rows (U16g) or "
                   "binds NOTHING (-1 fallback).  SC1 = our content with "
                   "in-unit walked binds (T2a-exact lane).  U16gK4/"
                   "U16gABP split the base conviction within the compose "
                   "stack (substrate / +substitutions / +deletions=b52 "
                   "U16g).  DEMO v8 = the product prompt through the "
                   "same self-contained authoring."),
        "known_cells": {
            "T2a": "born standalone unmodified + G_ABPD = PASS (b50); "
                   "walked binds in-unit; authored-empty inline ADocument; "
                   "dummy host reps",
            "T0": "our famgen famdoc (unbound walk binds) + same lane + "
                  "G_ABPD = FAIL (b49)",
            "T1v/T1r": "born shell + our content: FAIL on G_ABPD, PASS on "
                       "rst -- byte-identical famdoc (b51/b52)",
            "U16g": "U16's famdoc (host-bound refs onto substituted rows) "
                    "+ G_ABPD = FAIL (b52); same bytes PASS on rst (U16, "
                    "b45)",
            "BX_birth/DEMO v7": "birth set WITHOUT binds = FAIL (b51)",
        },
        "bases": {"SC1": relp(G_ABPD), "U16gK4": relp(K4),
                  "U16gABP": relp(G_ABP),
                  "DEMO_250v_room_v8": relp(G_ABPD)},
        "upload_order_max_information_first": list(LADDER),
        "controls": {
            "g_abpd": {"source": relp(G_ABPD),
                       "voids": "SC1, DEMO_250v_room_v8 on CTRL FAIL"},
            "k4": {"source": relp(K4), "voids": "U16gK4 on CTRL FAIL"},
            "g_abp": {"source": relp(G_ABP), "voids": "U16gABP on CTRL FAIL"},
        },
        "reading_the_matrix": READING,
        "u16g25_blocker": (
            "charter's U16g25 (U16 recipe on G_ABPD_2025) is BLOCKED by "
            "measured gaps, not skipped by choice: famload cannot walk "
            "2025 framing (compose-2025.md gap B: 'unexpected Partitions "
            "header: v=9 cls=0x391'); 4/77 unit classes have different "
            "2025 layouts (BrowserOrganization, DBViewDrafting, "
            "StructSettingsElem, Viewport); the inline ADocument needs "
            "port2025 adaptation.  The within-stack ladder above delivers "
            "the lineage-vs-instance split on the same format; the 2025 "
            "famload port is the recorded follow-up."),
        "hr1": relp(HR1_REPORT),
        "companion_evidence": {
            "accounting": relp(ACCT),
            "render_binds": relp(BINDS_PATH),
            "per_probe_builds": relp(BUILD_DIR) + "/<rung>/",
        },
        "note": ("every famdoc unit GUID is FRESH per house law; SC1/DEMO "
                 "v8 carry ZERO donor bytes (authored birth + binds; "
                 "test-enforced); U16gK4/U16gABP embed the rst donor "
                 "famdoc -- PROOF-ONLY, quarantined under experiments/, "
                 "never shipped."),
        "probes": probes,
    }
    jdump(PROBES, man)
    log(f"probes.json -> {relp(PROBES)}")
    return PROBES


def stage() -> Dict[str, Any]:
    """probe_batch gate + stage with THREE controls (G_ABPD for SC1/DEMO,
    K4 for U16gK4, G_ABP for U16gABP)."""
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
    if not os.path.isfile(HR1_REPORT):
        raise SystemExit("hr1_report.json missing -- run hr1 first (it is "
                         "the round's objection-list evidence)")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = pb.next_batch_number()
    out_dir = pb.ACCEPTANCE
    ctrl_g = pb.make_control(ledger, n, out_dir, source=G_ABPD)
    ctrl_k4 = pb.make_control(ledger, n, out_dir, source=K4)
    ctrl_abp = pb.make_control(ledger, n, out_dir, source=G_ABP)
    ordered = [ctrl_g, ctrl_k4, ctrl_abp] + \
              [e for e in entries if e.kind == "probe"]
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
        "tool": "tools/selfcontained.py (via tools/probe_batch.py "
                "primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified' (or is an Autodesk "
                "sample source); the batch carries >= 1 CONTROL = a "
                "byte-identical copy of a certified file; read the round "
                "with read_batch_verdicts(): control FAIL => every "
                "verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 3,
        "controls": {"g_abpd": ctrl_g.staged_as, "k4": ctrl_k4.staged_as,
                     "g_abp": ctrl_abp.staged_as,
                     "note": "the G_ABPD control gates SC1 + DEMO v8; the "
                             "K4 control gates U16gK4; the G_ABP control "
                             "gates U16gABP -- a control FAIL voids its "
                             "own base's probes only"},
        "note": ("selfcontained THE CLOSE: SC1 (our content, walked binds "
                 "in-unit, T2a-exact lane, on G_ABPD), U16gK4 + U16gABP "
                 "(U16's byte-identical famdoc on the compose stack's "
                 "substrate and pre-deletion layers), DEMO v8 (the "
                 "user's prompt through self-contained authoring).  Read "
                 "experiments/selfcontained/probes.json "
                 "reading_the_matrix; the objection-list evidence is "
                 "experiments/selfcontained/hr1_report.json."),
        "reading_order": [os.path.basename(e.staged_as or e.file)
                          for e in ordered],
        "entries": [e.to_json() for e in ordered],
    }
    path = os.path.join(out_dir, f"batch_{n}.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    manifest["manifest_path"] = pb.rel(path)
    log(f"STAGED batch {n} -> {pb.rel(path)} (3 controls + {len(files)} "
        f"probes; STOP at READY -- the orchestrator uploads)")
    return manifest


# ===========================================================================
# CLI
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("census")
    c.add_argument("file")
    c.add_argument("--base", required=True)
    c.add_argument("--host")
    sub.add_parser("hr1")
    sub.add_parser("mine-binds")
    b = sub.add_parser("build")
    b.add_argument("--only")
    sub.add_parser("stage")
    args = ap.parse_args(argv)
    if args.cmd == "census":
        rep = famdoc_census(args.file, args.base, args.host)
        print(json.dumps(rep, indent=1, default=str))
        return 0 if rep["self_contained"] else 1
    if args.cmd == "hr1":
        hr1()
        return 0
    if args.cmd == "mine-binds":
        mine_binds()
        return 0
    if args.cmd == "build":
        only = args.only.split(",") if args.only else None
        out = build(only)
        return 0 if not out["errors"] else 1
    if args.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
