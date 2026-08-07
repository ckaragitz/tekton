#!/usr/bin/env python
"""famdoc_bisect.py -- THE HYBRID FAMILY-DOCUMENT BISECTION (famdoc-bisect
stream, 2026-08-05).

THE QUESTION.  Instances of Autodesk-authored families pass the viewer's
open-time audit (V20..V29: our mutate path placing SAMPLE symbols on sample
bases); instances of OUR generated families fail -- any base, any load path
(famgen AND famload), any symbol form (solid AND no-solid), with the D1..D5
corpus-law fixes landed (instbug-fix / instbug-residual records).  The defect
is therefore INSIDE our generated family DOCUMENT content, deep-walked by the
audit only when an instance references it.  This tool bisects WHAT.

THE CONTROLLED PAIR.
  A = an Autodesk-authored family document living in the QUARANTINED rst
      sample itself: ``M_Concrete-Square-Column`` (unit 36 of
      samples/rstbasicsampleproject.rvt, 417 records, SELF-CONTAINED -- its
      one nested Family element carries NO content document).  Its symbol
      '450 x 450mm' is the exact symbol the certified V20 instance points
      at: the placement of an instance of THIS family on THIS base is
      already viewer-PASSED.
  B = our famgen panel family document (the demo's PP-1 product,
      ``tools/ifc_intent.build_product`` -- instances always FAIL).

THE HYBRID LADDER (each probe = untouched rst sample + ONE loaded family
document + ONE placed instance; the family document varies ONE axis):

  H7   the Autodesk famdoc, id-rebased above the rst watermark (the ONLY
       unavoidable transform), loaded by CERTIFIED rvt.famload + one
       instance by our template path.  Machinery exoneration: PASS =>
       loader + rebase + placement are lawful on a lawful document, and the
       famload flavour (minimal inline ADocument, dummy host symbol,
       1-blank-row host type table) is exonerated UNDER AN INSTANCE.
  H1   H7's famdoc + OUR GEOMETRY subtree (extrusion + sketch + curves +
       sketch plane) added, references repointed to the donor's self-Family
       / level.  The downlight precedent makes geometry the prime suspect.
  H2   + OUR PARAMETER/TYPE layer (14 ParamElemFamily + our rows appended
       to the donor's FamilyTypeTable / m_familyParams / order cell).
  H3   + OUR REFERENCE/DATUM layer (2 origin ref planes + Level +
       LevelAttributes), gen-view refs repointed to the donor's plan view.
  H4   + OUR VIEW constellation (the plan-view chain: DBViewPlan +
       DBViewType + Viewer + SketchPlane + Sun + Viewport + DBDrawing +
       ExtentElem), level refs repointed to the donor's level.
  H5   + OUR CONNECTOR layer (ConnectorElem + ElectricalLoadClassification
       + the one apparent-load param its cell drives), the connector's
       face reference repointed to the donor extrusion (face tag 2 exists
       on both solids -- measured).
  H6   H7's shape with the DONOR's OWN inline ADocument carried (remapped)
       into the ContentDocuments entry instead of our authored minimal one
       (131 populated AppInfoManager registries vs our all-null 239) --
       splits the inline-ADocument axis from the unit-content axes if H7
       fails; corroborates it if H7 passes.
  H8   OUR famdoc verbatim through the SAME famload path + the demo's own
       stage_equipment placement (the instbug-residual SL_f1i1 recipe) --
       the known-FAIL anchor of the round.

READING (probes.json carries the full matrix): H7 PASS + H8 FAIL brackets
the round; each H1..H5 FAIL convicts that axis of our grammar; all-H PASS
with H8 FAIL pushes the defect into what H8 alone carries (our whole-doc
composition: the skeleton itself / element ordering / the parts no single
axis isolates).

ADD-FORM LAW: hybrids are UNIONS (our subtree added to the intact donor
body), never deletions -- a FAIL convicts OUR added grammar, never a botched
excision; the reduction law stays untouched.  Every added element is
registered in the donor self-Family exactly like the donor's own members
(header deletion list + m_familyIds absorbed indices + for parameters the
four table surfaces) -- the same fix-up famload's big2SmallMap machinery
performs host-side.

PROOF-ONLY: every probe embeds Autodesk sample content and stays in
experiments/ under the quarantine rule (zero donors in shipped output; the
viewer batch is the certified probe mechanism, exactly like SX/SL).

USAGE (repo root)::

    .venv/bin/python tools/famdoc_bisect.py build             # all 8 probes
    .venv/bin/python tools/famdoc_bisect.py build --only H7,H1
    .venv/bin/python tools/famdoc_bisect.py diff              # famdoc_diff.json (ranked checklist)
    .venv/bin/python tools/famdoc_bisect.py verify            # re-run gates on emitted probes
    .venv/bin/python tools/famdoc_bisect.py stage             # probe_batch gate + rst control

TERRITORY: this file, ``experiments/famdoc_bisect/**``,
``tests/test_famdoc_bisect.py``, ``docs/inbox/famdoc-bisect.md``.  IMPORTS
(never edits): rvt.famload, rvt.famgen.{skeleton,factory,loader},
rvt.families, rvt.mutate, rvt.commit, rvt.validate, rvt.adocument,
rvt.convert.rfa_assemble, tools/ifc_intent.py, tools/bisect_instance_bug.py,
tools/residual_probe.py, tools/probe_batch.py.  No Autodesk install dirs,
no browser; STAGE only (the orchestrator uploads).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
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
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "famdoc_bisect")
BUILD_DIR = os.path.join(OUT_DIR, "_build")

#: the donor family document (measured 2026-08-05; tests pin these)
DONOR_UNIT = 36                       # M_Concrete-Square-Column
DONOR_SELF_FAMILY = 1410872
DONOR_LEVEL = 1410875                 # 'Lower Ref. Level' (both plan views generate from it)
DONOR_PLAN_VIEW = 1410877
DONOR_EXTRUSION = 1410972
DONOR_NATIVE_HOST_FAMILY = 1410863    # rst unit-0 Family (the V20 lineage)
DONOR_TYPE = "450 x 450mm"            # the V20-certified type name
DONOR_CATEGORY = -2001330             # OST structural columns

#: the same-category diff reference (nested => not loadable, diff-only)
RME_PANELBOARD_UNIT = 30              # M_Lighting and Appliance Panelboard - 208V MCB - Surface

#: instance placement (uniform across H1..H7; H8 uses the demo's own recipe)
PROBE_POSITION_FT = (16.0, -8.0, 0.0)

#: ladder / staging order = maximum information first
LADDER = ("H7", "H1", "H2", "H3", "H4", "H5", "H6", "H8")

AXES = {
    "H7": "control-A: the Autodesk famdoc (id-rebased only)",
    "H1": "our GEOMETRY subtree added",
    "H2": "our PARAMETER/TYPE layer added",
    "H3": "our REFERENCE/DATUM layer added",
    "H4": "our VIEW constellation added",
    "H5": "our CONNECTOR layer added",
    "H6": "control-A with the donor's OWN inline ADocument carried",
    "H8": "control-B: our famdoc verbatim (known-FAIL anchor)",
}


def log(msg: str) -> None:
    print(f"[famdoc] {msg}", flush=True)


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


def _bisect():
    import bisect_instance_bug as B
    return B


def _residual():
    import residual_probe as R
    return R


def _room():
    import ifc_intent as T
    return T


def _install_schema() -> None:
    from rvt.frontdoor import standalone as SA
    SA.install_schema(G_ABPD)


# ===========================================================================
# the FamilyDoc protocol over an arbitrary SkelElement list
# ===========================================================================

class HybridFamilyDoc:
    """The famload FamilyDoc protocol over decoded/mutated SkelElements.
    Segments are RE-ENCODED from the elements (the donor unit's 418/418
    encoder roundtrip is byte-exact -- measured; the loader's own roundtrip
    gate re-proves every record at load time)."""

    finalized = True

    def __init__(self, elements, self_family, *, name: str, category_id: int,
                 part_type: int, types: Sequence[Tuple[str, dict]],
                 current_type: int = 0, document_guid: Optional[str] = None):
        self.elements = list(elements)
        self.self_family = self_family
        self.name = str(name)
        self.category_id = int(category_id)
        self.part_type = int(part_type)
        self.types = list(types)
        self.current_type = int(current_type)
        self.document_guid = document_guid or str(uuid.uuid4())
        self.params = {}

    def finalize(self) -> "HybridFamilyDoc":
        return self

    def to_embedded_unit(self) -> Dict[str, Any]:
        from rvt.famgen import skeleton as SK
        segs = SK.build_unit_segments(self.elements)
        return {"content_doc_guid": self.document_guid,
                "record_count": len(self.elements),
                "segments": segs,
                "self_family_id": self.self_family.elem_id,
                "type_names": [n for n, _v in self.types]}


# ===========================================================================
# donor loading + id rebase
# ===========================================================================

def _inline_adoc_value(idx, unit: int) -> Tuple[dict, Dict[int, int]]:
    """(decoded inline-ADocument value, {elem id: owner id}) of one embedded
    unit's ContentDocuments entry."""
    from rvt import adocument as A
    from rvt.families import content_document_adoc
    guid = idx.units[unit].guid
    blob = content_document_adoc(idx, guid)
    if not blob:
        raise RuntimeError(f"unit {unit}: no ContentDocuments entry for {guid}")
    ad = A.decode_latest(blob)
    if not ad.clean:
        raise RuntimeError(f"unit {unit}: inline ADocument does not decode clean")
    owner_of: Dict[int, int] = {}
    inner = ((ad.value.get("m_elemTable") or {}).get("value") or {})
    for r in inner.get("m_elemArr") or []:
        owner_of[int(r.get("m_id", -1))] = int(r.get("m_OwningElementId", -1))
    return ad.value, owner_of


def load_unit_elements(rvt_path: str, unit: int):
    """Decode one embedded family unit into SkelElements (owner ids from the
    inline ADocument; seq-103 GElement reps kept, dummies -> None)."""
    from rvt.families import FamilyIndex
    from rvt.genesis.skeleton import SkelElement
    idx = FamilyIndex(rvt_path)
    recs = idx.unit_records(unit)
    adoc_value, owner_of = _inline_adoc_value(idx, unit)
    els: List[SkelElement] = []
    other_rep_classes = set()
    for eid in sorted(recs.get(102, {})):
        cname = idx.class_name(recs[102][eid].class_id)
        obj = idx.value(unit, eid, 102)
        hdr = idx.value(unit, eid, 101)
        rep = None
        r3 = recs.get(103, {}).get(eid)
        if r3 is not None:
            c3 = idx.class_name(r3.class_id)
            if c3 == "GElement":
                rv = idx.value(unit, eid, 103)
                rep = rv if isinstance(rv, dict) else None
            elif c3 != "SerializedDummy":
                other_rep_classes.add(c3)
        els.append(SkelElement(eid, cname, hdr if isinstance(hdr, dict) else {},
                               obj if isinstance(obj, dict) else {}, rep,
                               owner_id=owner_of.get(eid, -1)))
    if other_rep_classes:
        raise RuntimeError(f"unit {unit} carries seq-103 classes beyond "
                           f"GElement/SerializedDummy: {sorted(other_rep_classes)} "
                           f"-- the SkelElement re-encode would be lossy; refused")
    return els, adoc_value, idx


def rebase_elements(els, idmap: Dict[int, int]):
    """Deep-copied elements with EVERY unit-internal id remapped through
    ``idmap`` (the famgen loader's own conservative int-walk: only ints that
    are in the map are touched -- host-catalog ids / negatives ride
    unchanged).  Also returns the remap census {key name: hits} for the
    safety report."""
    from rvt.famgen.loader import _walk_replace_ids
    from rvt.genesis.skeleton import SkelElement
    census: Dict[str, int] = {}

    def count_keys(node, out):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in idmap:
                    out[k] = out.get(k, 0) + 1
                else:
                    count_keys(v, out)
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in idmap:
                    out["<list>"] = out.get("<list>", 0) + 1
                else:
                    count_keys(v, out)

    out = []
    for e in els:
        h = copy.deepcopy(e.header)
        o = copy.deepcopy(e.obj)
        r = copy.deepcopy(e.rep) if e.rep is not None else None
        for node in (h, o, r):
            if node is not None:
                count_keys(node, census)
                _walk_replace_ids(node, idmap)
        owner = idmap.get(e.owner_id, -1) if (e.owner_id or 0) > 0 else -1
        out.append(SkelElement(idmap[e.elem_id], e.class_name, h, o, r,
                               owner_id=owner, kind=e.kind))
    return out, census


# ===========================================================================
# our famdoc + the axis subtrees
# ===========================================================================

def our_product(start_id: int):
    """The demo's own PP-1 famgen product at ``start_id`` (finalized)."""
    B = _bisect()
    T = _room()
    model = B.demo_model()
    prod = T.build_product(model.plan_for("PP-1"), start_id=start_id, solid=True)
    if not prod.doc.finalized:
        prod.doc.finalize()
    return prod


def axis_sets(doc) -> Dict[str, List[int]]:
    """The one-axis element-id sets of OUR famdoc, selected by kind/class and
    pinned by exact class multisets (raises if the famgen shape drifts)."""
    by_id = {e.elem_id: e for e in doc.elements}
    sf = doc.self_family.elem_id

    def ids_of(pred):
        return sorted(e.elem_id for e in doc.elements if pred(e))

    geometry = ids_of(lambda e: e.kind in ("extrusion", "sketch", "curve", "sketch_plane"))
    params = ids_of(lambda e: e.kind == "family_param")
    datum = ids_of(lambda e: e.kind in ("ref_plane", "ref_level", "level_type"))
    connector = ids_of(lambda e: e.kind in ("connector", "load_class"))
    # the plan-view chain = every view-layer element NOT in the project-view
    # chain (DBViewProject + its owned satellites + the viewport they own)
    dbvp = [e for e in doc.elements if e.class_name == "DBViewProject"]
    proj_chain = set()
    if dbvp:
        proj_chain.add(dbvp[0].elem_id)
        owned = [e for e in doc.elements if e.owner_id == dbvp[0].elem_id]
        proj_chain.update(e.elem_id for e in owned)
        for e in doc.elements:                       # viewport owned by the drawing
            if e.owner_id in proj_chain:
                proj_chain.add(e.elem_id)
    views = ids_of(lambda e: e.kind in ("view", "view_type", "view_satellite")
                   and e.elem_id not in proj_chain)
    sets = {"H1": geometry, "H2": params, "H3": datum, "H4": views, "H5": connector}

    expect = {
        "H1": {"ExtrusionElem": 1, "VarSketch": 1, "CurveElem": 4, "SketchPlane": 1},
        "H2": {"ParamElemFamily": 14},
        "H3": {"RefPlane": 2, "Level": 1, "LevelAttributes": 1},
        "H4": {"DBViewPlan": 1, "DBViewType": 1, "Viewer": 1, "SketchPlane": 1,
               "SunAndShadowSettings": 1, "Viewport": 1, "DBDrawing": 1,
               "ExtentElem": 1},
        "H5": {"ConnectorElem": 1, "ElectricalLoadClassification": 1},
    }
    for axis, ids in sets.items():
        got: Dict[str, int] = {}
        for i in ids:
            got[by_id[i].class_name] = got.get(by_id[i].class_name, 0) + 1
        if got != expect[axis]:
            raise RuntimeError(f"{axis}: our famdoc shape drifted: {got} != {expect[axis]}")
    # nothing overlaps; nothing references the self-family index twice
    all_ids = [i for s in sets.values() for i in s]
    if len(all_ids) != len(set(all_ids)):
        raise RuntimeError("axis sets overlap")
    if sf in all_ids:
        raise RuntimeError("self-family leaked into an axis set")
    return sets


#: our apparent-load family parameter (the one H5 carries): measured kind
#: family_param whose ConnectorElem cell names it (m_famParamId)
def connector_param_id(doc) -> int:
    con = next(e for e in doc.elements if e.class_name == "ConnectorElem")
    cells = ((con.obj.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        for d in cv.get("m_paramDrivenData") or []:
            pid = d.get("m_famParamId")
            if isinstance(pid, int) and pid > 0:
                return pid
    raise RuntimeError("our connector cell names no positive m_famParamId")


# ===========================================================================
# self-Family surgery (registration exactly like the donor's own members)
# ===========================================================================

def _sf_deletion(sf) -> List[int]:
    par = ((sf.header.get("m_parents") or {}).get("value") or {})
    return par.setdefault("m_deletion", [])


def _sf_family_ids(sf) -> List[dict]:
    fi = ((sf.obj.get("m_familyIds") or {}).get("value") or {})
    return fi.setdefault("m_data", [])


def register_added(sf, added_ids: Sequence[int]) -> Dict[str, Any]:
    """Register added elements in the donor self-Family the way its own
    members are registered: header deletion list (sorted ascending) +
    ``m_familyIds`` absorbed-index entries (fresh indices past the max)."""
    dele = _sf_deletion(sf)
    for i in added_ids:
        if i not in dele:
            dele.append(int(i))
    dele.sort()
    data = _sf_family_ids(sf)
    nxt = max((int(d.get("m_index", -1)) for d in data), default=-1) + 1
    added_idx = {}
    have = {int(d.get("m_elementId", -1)) for d in data}
    for i in sorted(added_ids):
        if i in have:
            continue
        data.append({"m_elementId": int(i), "m_index": int(nxt)})
        added_idx[int(i)] = int(nxt)
        nxt += 1
    return {"deletion_len": len(dele), "family_ids_len": len(data),
            "absorbed_indices": added_idx}


def register_param_rows(sf, rows: List[dict], locked: List[int],
                        order_groups: List[dict]) -> Dict[str, Any]:
    """Append OUR parameter rows to the donor self-Family's FOUR parameter
    surfaces (current values, every type-table pair, the locked list, the
    FamilyParamsOrderCell -- merged by group type id).  ``rows`` are already
    remapped to the hybrid id space."""
    o = sf.obj
    have = set()
    fp = ((o.get("m_familyParams") or {}).get("value") or {})
    fp_rows = fp.setdefault("m_params", [])
    have = {r.get("m_paramId") for r in fp_rows}
    new_rows = [copy.deepcopy(r) for r in rows if r.get("m_paramId") not in have]
    fp_rows.extend(copy.deepcopy(new_rows))
    ftt = ((o.get("m_pFamilyTypes") or {}).get("value") or {})
    n_pairs = 0
    for pr in ftt.get("m_pairs") or []:
        pv = (pr.get("params") or {})
        pl = pv.setdefault("m_params", [])
        ph = {r.get("m_paramId") for r in pl}
        pl.extend(copy.deepcopy(r) for r in new_rows if r.get("m_paramId") not in ph)
        n_pairs += 1
    lk = o.setdefault("m_lockedParameterIdsForDirectManipulation", [])
    for i in locked:
        if i not in lk:
            lk.append(int(i))
    lk.sort()
    n_merged = 0
    cells = ((o.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        sp = cv.get("m_sortedParams")
        if not isinstance(sp, list):
            continue
        by_group = {}
        for g in sp:
            if isinstance(g, dict):
                by_group[str((g.get("m_groupTypeId") or {}).get("m_typeId"))] = g
        for g in order_groups:
            key = str((g.get("m_groupTypeId") or {}).get("m_typeId"))
            tgt = by_group.get(key)
            if tgt is None:
                sp.append(copy.deepcopy(g))
                n_merged += 1
            else:
                ids = tgt.setdefault("m_paramIds", [])
                for pid in g.get("m_paramIds") or []:
                    if pid not in ids:
                        ids.append(pid)
                        n_merged += 1
        break                                        # first order cell only
    return {"rows_appended": len(new_rows), "type_pairs_extended": n_pairs,
            "locked_len": len(lk), "order_ids_merged": n_merged}


# ===========================================================================
# hybrid assembly
# ===========================================================================

def build_donor(start_id: int):
    """The donor famdoc rebased to a contiguous block at ``start_id``.
    Returns (elements, anchors, idmap, inline_adoc_value, remap_census)."""
    els, adoc_value, _idx = load_unit_elements(RST, DONOR_UNIT)
    member = sorted(e.elem_id for e in els)
    idmap = {old: start_id + i for i, old in enumerate(member)}
    new_els, census = rebase_elements(els, idmap)
    anchors = {"self_family": idmap[DONOR_SELF_FAMILY],
               "level": idmap[DONOR_LEVEL],
               "plan_view": idmap[DONOR_PLAN_VIEW],
               "extrusion": idmap[DONOR_EXTRUSION]}
    return new_els, anchors, idmap, adoc_value, census


def make_hybrid(axis: str, wm: int) -> Tuple[HybridFamilyDoc, Dict[str, Any]]:
    """One hybrid family document.  ``axis`` in H7/H1..H5 (H6 shares H7's
    document; H8 does not use this path)."""
    donor_els, anchors, idmap, _adoc, census = build_donor(wm + 1)
    donor_top = wm + len(donor_els)
    sf = next(e for e in donor_els if e.elem_id == anchors["self_family"])
    report: Dict[str, Any] = {"axis": axis, "donor_block": [wm + 1, donor_top],
                              "anchors": anchors, "remap_census": census,
                              "carried": [], "repointed": {}, "registration": {}}

    part_type = 0                       # native host M_Concrete-Square-Column m_partType == -1 -> keep
    from rvt.mutate import Document
    host_fam = Document.from_file(RST).value(DONOR_NATIVE_HOST_FAMILY) or {}
    part_type = int(host_fam.get("m_partType") or 0)

    if axis in ("H7", "H6"):
        doc = HybridFamilyDoc(donor_els, sf, name="M Concrete-Square-Column P7",
                              category_id=DONOR_CATEGORY, part_type=part_type,
                              types=[(DONOR_TYPE, {})], current_type=1)
        return doc, report

    prod = our_product(wm + 2000)
    ours = prod.doc
    sets = axis_sets(ours)
    carried_ids = sets[axis]
    by_id = {e.elem_id: e for e in ours.elements}

    # repoint map: our out-of-axis anchors -> donor anchors
    repoint = {ours.self_family.elem_id: anchors["self_family"]}
    our_level = next(e.elem_id for e in ours.elements if e.kind == "ref_level")
    our_plan = next(e.elem_id for e in ours.elements if e.class_name == "DBViewPlan")
    our_ext = next(e.elem_id for e in ours.elements if e.class_name == "ExtrusionElem")
    if axis in ("H1", "H4"):
        repoint[our_level] = anchors["level"]
    if axis == "H3":
        repoint[our_plan] = anchors["plan_view"]
    if axis == "H5":
        repoint[our_ext] = anchors["extrusion"]
        pid = connector_param_id(ours)
        carried_ids = sorted(set(carried_ids) | {pid})
    report["repointed"] = {str(k): v for k, v in repoint.items()}

    from rvt.famgen.loader import _walk_replace_ids
    from rvt.genesis.skeleton import SkelElement
    carried = []
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
            owner = anchors["self_family"]
        carried.append(SkelElement(e.elem_id, e.class_name, h, o, r,
                                   owner_id=owner if (owner or 0) > 0 else -1,
                                   kind=e.kind))
    report["carried"] = [{"id": e.elem_id, "class": e.class_name, "kind": e.kind}
                         for e in carried]

    # dangling gate: a carried element may reference ONLY hybrid members
    # inside the allocated id blocks (donor block + our block).  An int in
    # those blocks that is not a hybrid member is a reference to an
    # UN-CARRIED element of our famdoc = a repoint the axis missed.  Ints
    # above the blocks are flag words / bitfields, below are host ids and
    # built-ins -- both out of scope by construction.
    hybrid_ids = {e.elem_id for e in donor_els} | carried_set
    our_ids = {e.elem_id for e in ours.elements}
    blocks_top = max(our_ids)
    host_ids = set(Document.from_file(RST).et_by_id)
    dangling = []

    def scan(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and wm < v <= blocks_top and v not in hybrid_ids:
                    dangling.append((path + "." + k, v))
                else:
                    scan(v, path + "." + k)
        elif isinstance(node, list):
            for j, v in enumerate(node):
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and wm < v <= blocks_top and v not in hybrid_ids:
                    dangling.append((f"{path}[{j}]", v))
                else:
                    scan(v, f"{path}[{j}]")

    for e in carried:
        scan(e.header, f"{e.elem_id}.hdr")
        scan(e.obj, f"{e.elem_id}.obj")
        if e.rep is not None:
            scan(e.rep, f"{e.elem_id}.rep")
    if dangling:
        raise RuntimeError(f"{axis}: carried subtree leaves dangling above-watermark "
                           f"refs: {dangling[:6]}")
    report["dangling_above_watermark"] = 0
    report["host_ids_visible"] = len(host_ids)

    # register in the donor self-Family
    report["registration"]["membership"] = register_added(sf, sorted(carried_set))
    if axis == "H2" or (axis == "H5" and any(e.class_name == "ParamElemFamily"
                                             for e in carried)):
        param_ids = {e.elem_id for e in carried if e.class_name == "ParamElemFamily"}
        our_sf = ours.self_family.obj
        fp_rows = (((our_sf.get("m_familyParams") or {}).get("value") or {})
                   .get("m_params") or [])
        rows = [r for r in fp_rows
                if r.get("m_paramId") in param_ids or
                (axis == "H2" and isinstance(r.get("m_paramId"), int)
                 and r.get("m_paramId") < 0)]
        locked = [i for i in (our_sf.get("m_lockedParameterIdsForDirectManipulation") or [])
                  if i in param_ids]
        groups = []
        cells = ((our_sf.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
        for c in cells:
            cv = (c.get("value") or {}) if isinstance(c, dict) else {}
            for g in cv.get("m_sortedParams") or []:
                if not isinstance(g, dict):
                    continue
                keep = [pid for pid in (g.get("m_paramIds") or [])
                        if pid in param_ids or (axis == "H2" and isinstance(pid, int)
                                                and pid < 0)]
                if keep:
                    groups.append({"m_groupTypeId": copy.deepcopy(g.get("m_groupTypeId")),
                                   "m_paramIds": keep})
            break
        report["registration"]["params"] = register_param_rows(sf, rows, locked, groups)

    elements = sorted(donor_els + carried, key=lambda e: e.elem_id)
    doc = HybridFamilyDoc(elements, sf, name=f"M Concrete-Square-Column {axis}",
                          category_id=DONOR_CATEGORY, part_type=part_type,
                          types=[(DONOR_TYPE, {})], current_type=1)
    return doc, report


# ===========================================================================
# the load + instance + gates of one probe
# ===========================================================================

def famload_doc(doc, out_path: str, key: str) -> Dict[str, Any]:
    from rvt import famload as FL
    res = FL.load_family_documents(RST, [FL.FamilyLoad(key=key, doc=doc)],
                                   out_path, validate=True,
                                   report_path=out_path + ".load.json")
    if not res.ok:
        raise RuntimeError(f"{key}: famload failed: {res.stop_reason}")
    p = res.plans[0]
    ver = (res.proofs.get("verify_written") or {})
    return {"family_id": p.host_family_id, "symbol_id": p.symbol_id,
            "surrogate": p.surrogate_id, "guid": p.guid,
            "twins": dict(p.twin_of), "doc_id_range": list(p.doc_id_range),
            "verify_ok": bool(ver.get("ok")),
            "validate_errors": ((ver.get("validate") or {}).get("n_errors"))}


def place_probe(src: str, out_path: str, *, symbol_id: int, family_id: int,
                category: int) -> Dict[str, Any]:
    """ONE instance by the demo's own template machinery
    (ConstructedSpecimens + Document.add_family_instance + commit), with the
    instance's category following the FAMILY's own (the only parameter that
    varies vs tools/ifc_intent.stage_equipment, which pins electrical
    equipment); product connector manager not injected (template's rides --
    corpus-lawful {null, FamilyInstanceConnectorManager})."""
    from rvt.frontdoor import standalone as SA
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements, verify_written
    T = _room()
    doc = Document.from_file(src)
    sp = SA.ConstructedSpecimens(SA.CONSTRUCTED, base_path=RST)
    sp.inject_into(doc)
    lvl = T._pick_level(doc, 0.0)
    el = doc.add_family_instance(symbol_id, lvl, position=PROBE_POSITION_FT,
                                 rotation=0.0, template_instance_id=sp.instance_id)
    T._apply_frame(el, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                   PROBE_POSITION_FT)
    scrub = T._scrub_instance(el, doc, our_symbol=symbol_id, our_family=family_id,
                              spec_symbol=sp.instance_symbol,
                              spec_category=sp.instance_category,
                              category=category)
    dangling = doc.check_references(el)
    recs = doc.serialize(el)
    if recs is None:
        raise RuntimeError("rvt.encode unavailable")
    crep = commit_new_elements(src, out_path, [dict(recs)], [el.elemrec])
    ver = verify_written(out_path, [el.elem_id])
    cm = el.obj.get("m_pConnectorManager")
    return {"instance_id": el.elem_id, "level": lvl,
            "position_ft": list(PROBE_POSITION_FT),
            "connmgr": (cm.get("ptr_class") if isinstance(cm, dict) else cm),
            "scrub": scrub, "n_dangling": len(dangling),
            "watermark_after": crep.watermark_after,
            "verify": {k: ver.get(k) for k in ("crc_failures", "ecc_mismatches",
                                               "walker_errors", "stamps_ok")}}


def swap_inline_adoc(path_in: str, path_out: str, *, guid: str,
                     adoc_value: dict, idmap: Dict[int, int],
                     self_family_new: int) -> Dict[str, Any]:
    """H6: replace OUR authored inline ADocument in the ContentDocuments
    entry for ``guid`` with the DONOR's ORIGINAL one, ids remapped and the
    four DocumentHistory identity GUIDs re-keyed to ONE FRESH guid.

    MEASURED NATIVE LAW (donor's own rst entry): the history
    creation/detach/upgrade/saveAs GUIDs are all EQUAL to each other but
    INDEPENDENT of the unit/content GUID (e2fe4920... vs 09982dbb...) --
    the famdoc keeps its own document identity inside the entry.  A fresh
    guid preserves both that shape and uniqueness (keeping the donor's
    would duplicate the still-present original entry's identity; famload's
    own flavour -- history == unit guid -- is what H7 carries)."""
    from rvt import adocument as A
    from rvt import ecc
    from rvt.container import open_rvt
    from rvt.famgen import factory as F
    from rvt.famgen.loader import _walk_replace_ids
    from rvt.roundtrip import read_entries
    from rvt.stream_encoders import wrap_global_stream
    from rvt.cfb_writer import write_cfb
    import dataclasses

    value = copy.deepcopy(adoc_value)
    _walk_replace_ids(value, idmap)
    hist = ((value.get("m_pHistory") or {}).get("value") or {})
    fresh_identity = str(uuid.uuid4())
    guid_fields = {}
    for k in ("m_creationGUID", "m_detachGUID", "m_upgradeGUID", "m_saveAsGUID"):
        g = (hist.get(k) or {}).get("m_guid")
        if g is not None:
            guid_fields[k] = str(g)
            hist[k] = {"m_guid": fresh_identity}
    payload = A.encode_latest(value, trailer=b"")
    back = A.decode_latest(payload)
    if not back.clean:
        raise RuntimeError("H6: remapped donor inline ADocument does not re-decode clean")
    with open_rvt(path_in) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    entries, tail = F.parse_content_documents(cd)
    n_before = len(entries)
    swapped = [(g, (payload if g == guid else a)) for g, a in entries]
    if not any(g == guid for g, _a in entries):
        raise RuntimeError(f"H6: no ContentDocuments entry for {guid}")
    new_cd = F.assemble_content_documents(swapped, tail=tail or F.CD_END_RECORD)
    stream = ecc.frame_stream(wrap_global_stream("Global/ContentDocuments", new_cd, level=3))
    ents = read_entries(path_in)
    out_entries = [dataclasses.replace(e, data=stream)
                   if (e.entry_type == "stream" and e.path == "Global/ContentDocuments")
                   else e for e in ents]
    write_cfb(path_out, out_entries)
    aim = ((value.get("m_pAppInfoManager") or {}).get("value") or {})
    arr = aim.get("m_appInfoArr") or []
    return {"entries": n_before, "swapped_guid": guid,
            "adoc_bytes": len(payload),
            "appinfo_slots": len(arr),
            "appinfo_populated": sum(1 for x in arr if x),
            "owner_family_id": value.get("m_ownerFamilyId"),
            "owner_family_expected": self_family_new,
            "history_identity_fresh": fresh_identity,
            "history_guids_rekeyed_from": guid_fields,
            "native_law": "history identity GUIDs equal each other, "
                          "independent of the unit GUID (measured on the "
                          "donor's own entry); a fresh identity preserves "
                          "the shape without duplicating the original "
                          "entry's identity"}


def emit_dev_rfa(doc, out_rfa: str) -> Dict[str, Any]:
    """The hybrid famdoc as a standalone dev .rfa (family-mode validator
    evidence; NEVER staged).  Dangling-ElementId findings that point at ids
    RESIDENT IN THE RST HOST are classified expected (a project-hosted family
    is not fully self-contained -- the probe re-embeds it into the very host
    that owns those ids); any other error class is a build bug."""
    from rvt.container import open_rvt
    from rvt.convert.rfa_assemble import UnitDoc, UnitElement, assemble_rfa
    from rvt.famgen import famdoc_adoc as FA
    from rvt.mutate import Document
    unit = doc.to_embedded_unit()
    els = [UnitElement(elem_id=e.elem_id, class_name=e.class_name,
                       obj=e.obj if isinstance(e.obj, dict) else {},
                       owner_id=e.owner_id, original_id=e.elem_id)
           for e in doc.elements]
    sf_el = next(u for u in els if u.elem_id == doc.self_family.elem_id)
    ud = UnitDoc(elements=els, self_family=sf_el, document_guid=doc.document_guid,
                 name=doc.name, category_id=doc.category_id,
                 part_type=doc.part_type, types=list(doc.types))
    with open_rvt(RST) as f:
        formats_raw = f.raw("Formats/Latest")
    rep = assemble_rfa(unit["segments"], ud, out_rfa, formats_raw=formats_raw)
    out: Dict[str, Any] = {"rfa": relp(out_rfa), "size": rep.get("size"),
                           "verify": {k: (rep.get("verify") or {}).get(k)
                                      for k in ("gzip_crc_failures", "ecc_mismatch",
                                                "walker_errors", "n_units")}}
    try:
        val = FA.validate_family_file(out_rfa, with_donor_parity=False)
        fm = val.get("family_mode") or {}
        out["family_mode"] = {"verdict": fm.get("verdict"),
                              "n_errors": fm.get("n_errors"),
                              "n_warnings": fm.get("n_warnings"),
                              "errors": [str(e)[:200] for e in fm.get("errors") or []]}
    except Exception as e:                                    # noqa: BLE001
        out["family_mode"] = {"verdict": "ERROR", "error": f"{type(e).__name__}: {e}"}
    # SCHEMA-TYPED reference resolution (the validator's own RefDecoder --
    # not field-name guessing): every ElementId-typed value of every unit
    # record, resolved against (unit members) then (rst host ElemTable).
    # STANDALONE-DANGLING refs that are HOST-RESIDENT are the expected
    # project-hosted-family shape (the probe re-embeds the document into the
    # very host that owns those ids -- the probe-file validator's clean
    # reference pass is the binding proof); anything else is a build bug.
    try:
        from rvt.families import FamilyIndex
        from rvt.objects import iter_records
        from rvt.validate import _RefDecoder, find_dangling_refs
        schema = FamilyIndex(RST).schema
        dec = _RefDecoder(schema)
        refs = []
        seg = unit["segments"][102]
        for rec in iter_records(seg, 102):
            if rec.elem_id < 0:
                continue
            dec.refs = []
            try:
                dec.decode_record(rec.class_id, rec.payload)
            except Exception:                                  # noqa: BLE001
                continue
            refs.extend((rec.elem_id, p, v) for p, v in dec.refs)
        member = {e.elem_id for e in doc.elements}
        host_ids = set(Document.from_file(RST).et_by_id)
        dangling = find_dangling_refs(refs, member)
        host_resident = [d for d in dangling if d[2] in host_ids]
        unresolved = [d for d in dangling if d[2] not in host_ids]
        out["reference_resolution"] = {
            "refs_typed": len(refs),
            "resolve_in_unit": len(refs) - len(dangling),
            "standalone_dangling_host_resident": len(host_resident),
            "unresolved_anywhere": len(unresolved),
            "unresolved_examples": [{"owner": o, "path": p[-80:], "target": t}
                                    for o, p, t in unresolved[:8]],
        }
        if unresolved:
            raise RuntimeError(
                f"hybrid famdoc leaves {len(unresolved)} schema-typed reference(s) "
                f"unresolved in BOTH the unit and the rst host: {unresolved[:4]}")
    except RuntimeError:
        raise
    except Exception as e:                                     # noqa: BLE001
        out["reference_resolution"] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ===========================================================================
# build driver
# ===========================================================================

def build_probe(name: str, wm: int) -> Dict[str, Any]:
    B = _bisect()
    info: Dict[str, Any] = {"probe": name, "axis": AXES[name], "base": relp(RST)}
    pdir = os.path.join(BUILD_DIR, name)
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, f"{name}.rvt")

    if name == "H8":
        R = _residual()
        model1 = B.truncate_model(B.demo_model(), 1)
        src = os.path.join(pdir, "H8_load.rvt")
        lrec = R.famload_load(RST, src, model1)
        info["load"] = {k: v for k, v in lrec.items() if not k.startswith("_")}
        loaded = lrec["_loaded"]
        erec = B.place_instances(model1, src, outp, RST, loaded)
        info["equipment"] = {
            "instances": [{k: i.get(k) for k in ("tag", "elem_id", "symbol",
                                                 "family", "n_dangling")}
                          for i in erec.get("instances") or []]}
        info["instance_ids"] = [i["elem_id"] for i in erec.get("instances") or []]
        first = (erec.get("instances") or [{}])[0]
        info["symbol_id"] = first.get("symbol")
        info["family_id"] = first.get("family")
        info["placement"] = "demo stage_equipment (SL_f1i1 recipe: product " \
                            "connector manager, intent position)"
        info["immediate_parent"] = relp(src)
        info["file"] = relp(outp)
        info["md5"] = md5_of(outp)
        return info

    doc, hrep = make_hybrid(name, wm)
    jdump(os.path.join(pdir, "hybrid_report.json"), hrep)
    info["hybrid"] = {k: hrep[k] for k in ("axis", "donor_block", "anchors",
                                           "carried", "repointed", "registration")}
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)

    rfa = os.path.join(pdir, f"{name}_famdoc.rfa")
    try:
        info["dev_rfa"] = emit_dev_rfa(doc, rfa)
    except Exception as e:                                     # noqa: BLE001
        info["dev_rfa"] = {"error": f"{type(e).__name__}: {e}",
                           "note": "evidence-only gate; the probe validator binds"}

    src = os.path.join(pdir, f"{name}_load.rvt")
    info["load"] = famload_doc(doc, src, name)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam

    if name == "H6":
        donor_els, anchors, idmap, adoc_value, _c = build_donor(wm + 1)
        swapped = os.path.join(pdir, "H6_load_adoc.rvt")
        info["adoc_swap"] = swap_inline_adoc(
            src, swapped, guid=doc.document_guid, adoc_value=adoc_value,
            idmap=idmap, self_family_new=anchors["self_family"])
        src = swapped
        info["immediate_parent"] = relp(swapped)
    else:
        info["immediate_parent"] = relp(src)

    info["placement"] = ("uniform template path (ConstructedSpecimens + "
                         "add_family_instance + commit; category = the "
                         "family's own; connmgr = template's)")
    prec = place_probe(src, outp, symbol_id=sym, family_id=fam,
                       category=DONOR_CATEGORY)
    info["instance"] = prec
    info["instance_ids"] = [prec["instance_id"]]
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    _install_schema()
    B = _bisect()
    T = _room()
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    wm = T.host_watermark(RST)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/famdoc_bisect.py", "base": relp(RST),
                           "watermark": wm, "built": {}, "accounting": {},
                           "errors": {}}
    acct_path = os.path.join(OUT_DIR, "accounting.json")
    if os.path.isfile(acct_path):                  # merge partial (--only) runs
        try:
            with open(acct_path) as fh:
                prev = json.load(fh)
            out["built"] = {k: v for k, v in (prev.get("built") or {}).items()
                            if k not in only}
            out["accounting"] = {k: v for k, v in (prev.get("accounting") or {}).items()
                                 if k.split(".")[0] not in only}
        except Exception:                          # noqa: BLE001
            pass
    for name in [n for n in LADDER if n in only]:
        try:
            t1 = time.time()
            info = build_probe(name, wm)
            info["seconds"] = round(time.time() - t1, 1)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]}, "
                f"{info['seconds']}s)")
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = traceback.format_exc(limit=10)
            log(f"{name} FAILED: {type(e).__name__}: {e}")

    for name, info in out["built"].items():
        if name not in only and name in out["accounting"]:
            continue                               # carried over from a prior run
        try:
            parent = os.path.join(ROOT, info["immediate_parent"])
            rep = B.account(name, os.path.join(ROOT, info["file"]), parent,
                            declared_base=RST,
                            instance_ids=info.get("instance_ids") or [])
            out["accounting"][name] = rep
            # the load hop (parent vs the untouched base)
            out["accounting"][name + ".hop_load"] = B.account(
                name + ".hop_load", parent, RST, declared_base=RST,
                instance_ids=[], with_regdiff=False)
            va = rep["validator"]
            log(f"{name}: validator {va['n_errors']} err "
                f"(unexpected {len(va['unexpected_errors'])}), "
                f"census +{rep['census_delta']['save_units']}u coherent "
                f"{rep['census']['coherent']}, survivor "
                f"{'OK' if rep['survivor_law_ok'] else 'VIOLATED'}")
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name + ".accounting"] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".accounting.tb"] = traceback.format_exc(limit=8)
            log(f"{name} ACCOUNTING FAILED: {type(e).__name__}: {e}")

    out["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(OUT_DIR, "accounting.json"), out)
    write_probes_json(out)
    return out


# ===========================================================================
# probes.json
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing",
    "H7 PASS + H8 FAIL": "the round is bracketed: loader + rebase + placement "
                         "are lawful on the Autodesk famdoc while our famdoc "
                         "fails under the SAME path -- the poison is inside "
                         "our document content; read H1..H5 as convictions.",
    "H7 FAIL": "the machinery corrupts a LAWFUL document: the axis shifts to "
               "the famload treatment itself.  Read H6 -- H6 PASS + H7 FAIL "
               "convicts OUR authored minimal inline ADocument (all-null "
               "AppInfoManager); both FAIL convicts the unit re-encode/rebase "
               "or the famload host flavour: diff the loaded bytes vs the "
               "donor's original unit (the segments are re-encoded from the "
               "decoded records; the 418/418 roundtrip bounds the delta to "
               "the id rebase).  Note V20 already certifies PLACEMENT of "
               "this exact symbol shape on this base.",
    "H1 FAIL (H7 PASS)": "OUR GEOMETRY GRAMMAR CONVICTED: the extrusion/"
                         "sketch/curve subtree poisons a lawful famdoc when "
                         "an instance walks it -- the [H]-grammar bake is the "
                         "fix target (corpus mining spec in instbug-residual "
                         "corpus_symbols.json).",
    "H2 FAIL (H7 PASS)": "our parameter/type-table layer convicted (14 "
                         "ParamElemFamily + row grammar).",
    "H3 FAIL (H7 PASS)": "our reference/datum layer convicted (ref planes / "
                         "level / level type grammar).",
    "H4 FAIL (H7 PASS)": "our view-constellation grammar convicted.",
    "H5 FAIL (H7 PASS)": "our connector layer convicted (ConnectorElem + "
                         "load classification + param-driven cell).",
    "H6 verdict": "with H7 PASS it is corroboration (both inline-ADocument "
                  "forms lawful); with H7 FAIL it splits the inline-ADocument "
                  "axis from the unit-content axes.",
    "all H1..H6 PASS + H8 FAIL": "no single added axis reproduces the "
                                 "failure: the defect is in what ONLY H8 "
                                 "carries -- our whole-document composition "
                                 "(the S0 skeleton itself, element ordering, "
                                 "the units/registry singletons, or an "
                                 "interaction of axes).  Next ladder: "
                                 "pairwise axis unions, or the inverse "
                                 "bisection (our doc with donor subtrees).",
    "multiple axis FAILs": "each failing axis is independently convicted "
                           "(the add-form makes probes independent); fix in "
                           "deep-walk rank order H1 > H2 > H3 > H5 > H4.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    onething = {
        "H7": "control-A: the Autodesk M_Concrete-Square-Column famdoc "
              "(id-rebased, otherwise verbatim) famload-loaded into its own "
              "rst sample + ONE instance by our template path.  V20 already "
              "certified an instance of this family's native symbol on this "
              "base -- the ONE new thing is the famload load of the copy.",
        "H1": "H7 + OUR geometry subtree (ExtrusionElem + VarSketch + 4 "
              "CurveElems + SketchPlane) added to the donor famdoc, "
              "registered like its own members.  The downlight precedent "
              "makes this the prime suspect.",
        "H2": "H7 + OUR parameter/type layer (14 ParamElemFamily + our rows "
              "in all four self-Family parameter surfaces).",
        "H3": "H7 + OUR reference/datum layer (2 origin RefPlanes + Level + "
              "LevelAttributes).",
        "H4": "H7 + OUR plan-view constellation (8 elements).",
        "H5": "H7 + OUR connector layer (ConnectorElem + "
              "ElectricalLoadClassification + the apparent-load param), "
              "face ref repointed to the donor solid (tag 2 exists on both).",
        "H6": "H7's document with the DONOR's OWN inline ADocument (131 "
              "populated family-editor registries, remapped) in the "
              "ContentDocuments entry instead of our authored all-null one.",
        "H8": "control-B: OUR famdoc verbatim through the same famload path "
              "+ the demo's own placement (the SL_f1i1 recipe) -- the "
              "known-FAIL anchor.",
    }
    expected = {
        "H7": "PASS (every ingredient individually certified: famdoc native "
              "to the base, famload = L1a/L_v2 lineage, placement = V20)",
        "H1": "the hypothesis-bearing rung: FAIL convicts our geometry",
        "H2": "unknown", "H3": "unknown", "H4": "unknown", "H5": "unknown",
        "H6": "PASS if H7 passes (corroboration); the split matters only "
              "under H7 FAIL",
        "H8": "FAIL (the recorded SL_f1i1 verdict reproduces)",
    }
    probes = []
    for i, name in enumerate(LADDER, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        acct = (build_out.get("accounting") or {}).get(name) or {}
        va = acct.get("validator") or {}
        probes.append({
            "order": i,
            "rung": name,
            "file": f"experiments/famdoc_bisect/{name}.rvt",
            "base": relp(RST),
            "kind": "probe",
            "axis": AXES[name],
            "n_families": 1, "n_instances": 1, "n_walls": 0,
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
                      "identity": ((acct.get("identity_gate") or {}).get("status")),
                      "famdoc_refs_unresolved_anywhere": ((info.get("dev_rfa") or {})
                                                          .get("reference_resolution") or {})
                                                         .get("unresolved_anywhere")},
        })
    manifest = {
        "stream": "famdoc-bisect: WHAT inside our generated family document "
                  "does the audit reject when an instance references it -- "
                  "hybrid ladder on the rst sample (Autodesk famdoc body + "
                  "our subtrees, one axis per rung)",
        "base": relp(RST),
        "note": "every probe = untouched rst sample + ONE loaded family "
                "document + ONE placed instance.  Hybrids are ADD-form "
                "(our subtree added to the intact donor body, registered in "
                "the donor self-Family like its own members); the donor is "
                "the sample's own M_Concrete-Square-Column (unit 36; its "
                "native symbol is the V20-certified instance target).  "
                "PROOF-ONLY: sample-derived content, quarantined, never "
                "shipped.  Fresh GUIDs are minted per rebuild -- re-hash "
                "after any rerun.  H1..H7 placement is uniform (template "
                "path, null/template connmgr, fixed position); H8 is the "
                "demo's own recipe (product connmgr, intent position) so it "
                "reproduces the recorded SL_f1i1 FAIL byte-faithfully.",
        "upload_order_max_information_first": list(LADDER),
        "control": {"source": relp(RST),
                    "note": "control = byte-identical copy of the UNTOUCHED "
                            "rst sample (probe_batch stage --control-from)"},
        "reading_the_matrix": READING,
        "companion_evidence": {
            "accounting": "experiments/famdoc_bisect/accounting.json",
            "ranked_diff_checklist": "experiments/famdoc_bisect/famdoc_diff.json",
            "per_probe_hybrid_reports": "experiments/famdoc_bisect/_build/<rung>/hybrid_report.json",
            "dev_rfas": "experiments/famdoc_bisect/_build/<rung>/<rung>_famdoc.rfa (evidence only, never staged)",
        },
        "probes": probes,
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# the ranked per-element diff checklist (deliverable 2)
# ===========================================================================

def _class_histogram(els) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for e in els:
        out[e.class_name] = out.get(e.class_name, 0) + 1
    return out


def _diff_objects(a: Optional[dict], b: Optional[dict]) -> Dict[str, Any]:
    R = _residual()
    return R.diff_objects(a, b)


def _gelement_stats(rep):
    R = _residual()
    return R._gelement_stats(rep)                              # noqa: SLF001


def famdoc_diff() -> Dict[str, Any]:
    """The per-element field diff between Autodesk famdocs and OURS, ranked
    by what the audit's deep walk visits from a placed instance.  Two
    references: (1) the SAME-CATEGORY rme 208V MCB panelboard (nested =>
    diff-only, the apples-to-apples checklist); (2) the rst column donor
    (the hybrid body).  A = Autodesk, B = ours."""
    _install_schema()
    t0 = time.time()
    prod = our_product(2_000_000)
    ours = prod.doc
    by_kind: Dict[str, Any] = {e.kind: e for e in ours.elements}
    by_class: Dict[str, List[Any]] = {}
    for e in ours.elements:
        by_class.setdefault(e.class_name, []).append(e)

    out: Dict[str, Any] = {
        "law": "A = the Autodesk famdoc element; B = ours.  only_in_A = what "
               "our grammar NEVER AUTHORS (missing surface); only_in_B = what "
               "we author that Autodesk does not; differing = shared fields "
               "with different shapes.  Rank = deep-walk order from a placed "
               "instance: instance -> symbol (geomSteps/GeomTable/type row) "
               "-> famdoc geometry -> params/types -> refs/datum -> "
               "connector -> views -> registry/inline-ADocument.",
        "references": {
            "same_category": {"file": relp(RME), "unit": RME_PANELBOARD_UNIT,
                              "family": "M_Lighting and Appliance Panelboard - "
                                        "208V MCB - Surface (nested: diff-only, "
                                        "not loadable standalone)"},
            "hybrid_donor": {"file": relp(RST), "unit": DONOR_UNIT,
                             "family": "M_Concrete-Square-Column"},
        },
        "ours": {"name": ours.name, "n_elements": len(ours.elements),
                 "class_histogram": _class_histogram(ours.elements)},
        "checklist": [],
    }

    def snap(el):
        return {"obj": el.obj, "header": el.header, "rep": el.rep}

    def one_ref(tag: str, rvt_path: str, unit: int) -> Dict[str, Any]:
        els, adoc_value, idx = (None, None, None)
        try:
            els, adoc_value, idx = load_unit_elements(rvt_path, unit)
        except RuntimeError as e:
            # nested/lossy units: fall back to a FamilyIndex-only view
            from rvt.families import FamilyIndex
            from rvt.genesis.skeleton import SkelElement
            idx = FamilyIndex(rvt_path)
            recs = idx.unit_records(unit)
            els = []
            for eid in sorted(recs.get(102, {})):
                cname = idx.class_name(recs[102][eid].class_id)
                obj = idx.value(unit, eid, 102)
                hdr = idx.value(unit, eid, 101)
                rep = None
                r3 = recs.get(103, {}).get(eid)
                if r3 is not None and idx.class_name(r3.class_id) == "GElement":
                    rv = idx.value(unit, eid, 103)
                    rep = rv if isinstance(rv, dict) else None
                els.append(SkelElement(eid, cname, hdr or {}, obj or {}, rep))
            adoc_value = None
        A_by_class: Dict[str, List[Any]] = {}
        for e in els:
            A_by_class.setdefault(e.class_name, []).append(e)
        rep_hist: Dict[str, int] = {}
        for e in els:
            key = "GElement" if e.rep is not None else "SerializedDummy"
            rep_hist[key] = rep_hist.get(key, 0) + 1
        rec: Dict[str, Any] = {
            "reference": tag,
            "n_elements": len(els),
            "class_histogram": _class_histogram(els),
            "classes_only_in_A": sorted(set(A_by_class) - set(by_class)),
            "classes_only_in_B": sorted(set(by_class) - set(A_by_class)),
            "rep_histogram": rep_hist,
        }
        if adoc_value is not None:
            aim = ((adoc_value.get("m_pAppInfoManager") or {}).get("value") or {})
            arr = aim.get("m_appInfoArr") or []
            hist = ((adoc_value.get("m_pHistory") or {}).get("value") or {})
            eps = (hist.get("m_episodeList") or {}).get("m_oEpisodes")
            rec["inline_adocument"] = {
                "appinfo_slots": len(arr),
                "appinfo_populated": sum(1 for x in arr if x),
                "appinfo_populated_classes": sorted({
                    str((x or {}).get("ptr_class")) for x in arr if x})[:40],
                "n_episodes": len(eps) if isinstance(eps, list) else None,
                "note": "OUR loads author all-null slots + single episode "
                        "(rvt.famgen.factory.author_embedded_adocument)",
            }
        pair_specs = [
            # (rank, name, A selector, B element, deep-walk note)
            (1, "ExtrusionElem", "ExtrusionElem", by_kind.get("extrusion"),
             "the solid the symbol's geomSteps/GeomTable regenerate from -- "
             "the instance walk's deepest content"),
            (1, "VarSketch", "VarSketch", by_kind.get("sketch"),
             "the extrusion's profile sketch"),
            (1, "CurveElem", "CurveElem",
             (by_class.get("CurveElem") or [None])[0],
             "profile curves (first of ours vs first of theirs)"),
            (1, "SketchPlane(sketch)", "SketchPlane", by_kind.get("sketch_plane"),
             "the sketch's plane"),
            (2, "self-Family", "Family", ours.self_family,
             "type table + params + familyIds registry the symbol's type row "
             "comes from"),
            (2, "ParamElemFamily", "ParamElemFamily",
             (by_class.get("ParamElemFamily") or [None])[0],
             "parameter definition grammar (first of each)"),
            (3, "RefPlane", "RefPlane", by_kind.get("ref_plane"),
             "reference planes (origin/datum)"),
            (3, "Level", "Level", by_kind.get("ref_level"), "the ref level"),
            (3, "LevelAttributes", "LevelAttributes", by_kind.get("level_type"),
             "the level type"),
            (4, "ConnectorElem", "ConnectorElem", by_kind.get("connector"),
             "the electrical connector (rme reference only -- the column has "
             "none)"),
            (5, "DBViewPlan", "DBViewPlan", by_kind.get("view"),
             "the plan view the datum elements generate in"),
            (5, "Viewer(plan)", "Viewer",
             (by_class.get("Viewer") or [None, None])[1] if len(by_class.get("Viewer") or []) > 1 else None,
             "the plan view's viewer satellite"),
            (6, "UnitsElem", "UnitsElem", by_kind.get("registry"),
             "the units registry singleton"),
        ]
        checklist = []
        for rank, label, a_cls, b_el, why in pair_specs:
            a_list = A_by_class.get(a_cls) or []
            if b_el is None and not a_list:
                continue
            entry: Dict[str, Any] = {"rank": rank, "element": label,
                                     "reference": tag, "why_walked": why,
                                     "A_count": len(a_list),
                                     "B_present": b_el is not None}
            if a_list and b_el is not None:
                a_el = a_list[0]
                if a_cls == "Family":
                    a_el = next((e for e in a_list
                                 if (e.obj.get("m_famId") in (-1, None))), a_list[0])
                entry["A_id"] = a_el.elem_id
                entry["B_id"] = b_el.elem_id
                entry["obj_diff"] = _diff_objects(a_el.obj, b_el.obj)
                entry["header_diff"] = _diff_objects(a_el.header, b_el.header)
                if a_el.rep is not None or b_el.rep is not None:
                    entry["rep_stats"] = {"A": _gelement_stats(a_el.rep),
                                          "B": _gelement_stats(b_el.rep)}
            checklist.append(entry)
        rec["checklist"] = checklist
        return rec

    out["same_category_panelboard"] = one_ref("rme_208V_MCB_panelboard", RME,
                                              RME_PANELBOARD_UNIT)
    out["hybrid_donor_column"] = one_ref("rst_concrete_square_column", RST,
                                         DONOR_UNIT)
    out["seconds"] = round(time.time() - t0, 1)
    path = os.path.join(OUT_DIR, "famdoc_diff.json")
    jdump(path, out)
    log(f"famdoc_diff.json -> {relp(path)} ({out['seconds']}s)")
    return out


# ===========================================================================
# verify + stage
# ===========================================================================

def verify() -> Dict[str, Any]:
    """Re-run the accounting gates on the emitted probes (current validator)."""
    _install_schema()
    B = _bisect()
    acct_path = os.path.join(OUT_DIR, "accounting.json")
    if not os.path.isfile(acct_path):
        raise SystemExit("no accounting.json -- run build first")
    with open(acct_path) as fh:
        out = json.load(fh)
    fresh = {}
    for name, info in (out.get("built") or {}).items():
        child = os.path.join(ROOT, info["file"])
        parent = os.path.join(ROOT, info["immediate_parent"])
        if not (os.path.isfile(child) and os.path.isfile(parent)):
            fresh[name] = {"error": "file(s) missing"}
            continue
        r = B.account(name, child, parent, declared_base=RST,
                      instance_ids=info.get("instance_ids") or [],
                      with_regdiff=False)
        fresh[name] = r
        if name in (out.get("accounting") or {}):
            out["accounting"][name]["validator_now"] = r["validator"]
        va = r["validator"]
        log(f"{name}: validator {va['n_errors']} err (unexpected "
            f"{len(va['unexpected_errors'])}), coherent {r['census']['coherent']}, "
            f"survivor {'OK' if r['survivor_law_ok'] else 'VIOLATED'}")
    jdump(acct_path, out)
    write_probes_json(out)
    return fresh


def stage() -> Dict[str, Any]:
    B = _bisect()
    spec = importlib.util.spec_from_file_location(
        "_famdoc_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run build): {[relp(m) for m in missing]}")
    manifest = pb.stage_batch(
        files, control_from=RST,
        batch_n=B._campaign_global_next_batch(),                # noqa: SLF001
        note="famdoc-bisect: the hybrid family-document ladder. Donor body = "
             "the rst sample's own M_Concrete-Square-Column famdoc (V20's "
             "certified instance target); each rung = untouched rst + ONE "
             "loaded famdoc + ONE instance, varying ONE axis of OUR grammar "
             "(H7 control-A, H1 geometry, H2 params, H3 datum, H4 views, "
             "H5 connector, H6 inline-ADocument, H8 our-famdoc FAIL anchor). "
             "Read experiments/famdoc_bisect/probes.json reading_the_matrix; "
             "the ranked per-element diff is famdoc_diff.json.")
    log(f"STAGED batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} (base {e.get('base')}, "
            f"{e.get('kind')})")
    return manifest


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the 8 probes (+ accounting + probes.json)")
    b.add_argument("--only", default=None, help="comma-separated probe subset")
    sub.add_parser("diff", help="the ranked per-element diff checklist")
    sub.add_parser("verify", help="re-run the gates on the emitted probes")
    sub.add_parser("stage", help="probe_batch gate + stage (control = rst copy)")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        only = [s.strip() for s in a.only.split(",")] if a.only else None
        bad = [r for r in (only or []) if r not in LADDER]
        if bad:
            ap.error(f"unknown probe(s): {bad}; choose from {list(LADDER)}")
        out = build(only)
        n_err = len([k for k in out["errors"] if not k.endswith((".traceback", ".tb"))])
        log(f"build done: {len(out['built'])} probe(s), {n_err} error(s), "
            f"{out['seconds']}s")
        return 1 if n_err else 0
    if a.cmd == "diff":
        famdoc_diff()
        return 0
    if a.cmd == "verify":
        fresh = verify()
        bad = [n for n, r in fresh.items() if r.get("error") or not r.get("gates_ok")]
        log(f"verify done: {len(fresh)} probe(s), gate failures: {bad or 'none'}")
        return 1 if bad else 0
    if a.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
