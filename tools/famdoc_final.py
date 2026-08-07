#!/usr/bin/env python
"""famdoc_final.py -- COMBINATION vs FRAME: the round that decides
(famdoc-final stream, 2026-08-05).

WHERE THE HUNT STANDS (genesis-audit VERDICTS #38, batch 44).  With the
64-byte 0x0f3f unit blobs emitted by the fixed writer: B7 (donor famdoc
through famload + instance) PASS -- the machinery is exonerated; B1..B6
(each of our content axes added SINGLY to the donor body) ALL PASS; B0 (our
COMPLETE famgen famdoc, one family + one instance on G_ABPD) FAIL.  The
defect is therefore EITHER a COMBINATION of our axes OR the RESIDUAL FRAME
-- the famdoc elements outside all six axis categories (the document
skeleton famgen composes).

THE FRAME, measured (`frame_roster` below prints it): exactly SIX of our 41
famdoc elements sit outside the six axis sets, in THREE natural groups:

  G1  the self-Family element        (Family)
  G2  the units registry singleton   (UnitsElem)
  G3  the project-view chain         (DBViewProject + Viewer + DBDrawing +
                                      Viewport; the donor's chain also
                                      references 2 BrowserOrganization
                                      elements ours lacks -- imported with
                                      the group)

THE LADDER (staged reading order = maximum information first):

  U16     donor body + ALL SIX of our axis additions at once: the union of
          B1..B5's subtrees (35 elements) registered in the donor
          self-Family + B6's donor-inline-ADocument swap (elem-table rows
          appended for the carried roster).  famload + template instance on
          the rst sample.  FAIL => a combination is guilty; PASS => no
          union of the added axes reproduces B0's failure.
  F1      the CONVERSE: OUR famgen famdoc with the donor's FRAME swapped in
          (G1+G2+G3; membership/identity/registry-counter surfaces kept
          ours -- the deterministic field law below), loaded by the EXACT
          B0 recipe (famgen loader chain on G_ABPD, corpus symbol form, the
          demo's own placement).  The ONLY delta vs B0 is the frame.
  U12345  U16 minus the ADocument swap: the five content axes with OUR
          authored inline ADocument -- the closest "B0 minus frame" shape
          (B0 rides our authored ADocument, not the donor's).  The probe
          that makes the frame inference tight.
  H8B     our famdoc VERBATIM (corpus symbol form) through famload on rst +
          the demo's own placement -- batch 37's H8 rebuilt with blobs: the
          loader/base split anchor (famgen-on-G_ABPD vs famload-on-rst).
  U12/U15/U25  the three highest-prior PAIRS (geometry+params,
          geometry+connector, params+connector -- famdoc_diff.json ranks
          geometry, params, connector as the deep-walk-first axes), built
          NOW so a U16 FAIL bisects immediately.
  F2/F3/F4  F1's inverse singles: ONE frame group donor-swapped each
          (F2=G1 self-Family, F3=G2 units, F4=G3 chain+imports), so a frame
          conviction names the exact element group without another cycle.

THE FRAME-SWAP FIELD LAW (deterministic, measured, recorded per probe):
donor and our frame elements carry IDENTICAL top-level key sets (measured;
build-refused otherwise).  For the self-Family, a top-level obj/header key
is kept OURS iff (a) its donor subtree references donor unit members or its
our-subtree references our members (membership surfaces: familyIds, params,
type table, cell list, locked list, deletion header, deletable elements,
dim-constraint mgr, refs), (b) it is IDENTITY (m_id, m_categoryId,
m_partType, m_name, m_famId, m_famDocGUID, m_surrogateId), or (c) it is a
REGISTRY-COUPLED counter (m_nextAbsorbedIndex, m_predefinedLimitIdx,
m_refTypeIds, m_trivialParamIds, m_keyExtParamId).  EVERY other key takes
the donor's value, ids repointed through the frame equivalence map.  G2/G3
elements swap whole (donor value, ids repointed; owner topology asserted
equal).  The kept-ours keys are the recorded, honest residue the swap
cannot test -- listed field-by-field in frame_diff.json.

frame_diff.json (the fix spec on a frame conviction): the per-element field
diff of OUR frame vs the DONOR's, ranked deep-walk-visited first
(self-Family > units registry > project-view chain), each self-Family key
tagged with its swap disposition.

PROOF-ONLY: U-probes and the F-probes' swapped elements embed Autodesk
sample content and stay quarantined in experiments/ (zero donors in shipped
output).  STAGE ONLY -- the orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/famdoc_final.py roster            # print the frame roster
    .venv/bin/python tools/famdoc_final.py diff              # frame_diff.json
    .venv/bin/python tools/famdoc_final.py build             # all 10 probes
    .venv/bin/python tools/famdoc_final.py build --only U16,F1
    .venv/bin/python tools/famdoc_final.py verify            # re-run gates
    .venv/bin/python tools/famdoc_final.py stage             # probe_batch + 2 controls

TERRITORY: this file, ``experiments/famdoc_final/**``,
``tests/test_famdoc_final.py``, ``docs/inbox/famdoc-final.md``, plus the
staging copies probe_batch itself writes under ``experiments/acceptance/``.
IMPORTS (never edits): tools/famdoc_bisect.py (the hybrid machinery),
tools/famdoc_blobs.py (the blob gate), tools/bisect_instance_bug.py,
tools/residual_probe.py, tools/probe_batch.py, tools/ifc_intent.py,
rvt.famgen.loader, rvt.famload_hostfix.  No Autodesk install dirs, no
browser, no full-suite runs.
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
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "famdoc_final")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")

#: staging/reading order = maximum information first
LADDER = ("U16", "F1", "U12345", "H8B", "U12", "U15", "U25", "F2", "F3", "F4")

#: which axes (1..6) each U-probe unions (6 = the donor-inline-ADocument swap)
U_AXES = {"U16": (1, 2, 3, 4, 5, 6), "U12345": (1, 2, 3, 4, 5),
          "U12": (1, 2), "U15": (1, 5), "U25": (2, 5)}

#: which frame groups each F-probe swaps
F_GROUPS = {"F1": ("G1", "G2", "G3"), "F2": ("G1",), "F3": ("G2",),
            "F4": ("G3",)}

#: frame roles, group membership, and the class each role must have
FRAME_ROLE_CLASS = {"self_family": "Family", "units": "UnitsElem",
                    "proj_view": "DBViewProject", "proj_viewer": "Viewer",
                    "proj_drawing": "DBDrawing", "proj_viewport": "Viewport"}
GROUP_ROLES = {"G1": ("self_family",), "G2": ("units",),
               "G3": ("proj_view", "proj_viewer", "proj_drawing",
                      "proj_viewport")}

#: self-Family swap law: keys kept OURS beyond the automatic member-ref rule
SF_KEEP_IDENTITY = ("m_id", "m_categoryId", "m_partType", "m_name",
                    "m_famId", "m_famDocGUID", "m_surrogateId")
SF_KEEP_REGISTRY = ("m_nextAbsorbedIndex", "m_predefinedLimitIdx",
                    "m_refTypeIds", "m_trivialParamIds", "m_keyExtParamId")

AXES = {
    "U16": "donor body + ALL SIX of our axis additions at once (five content "
           "subtrees + the donor-inline-ADocument swap)",
    "F1": "OUR famdoc with the donor's FRAME swapped in (self-Family + units "
          "+ project-view chain), the exact B0 recipe otherwise",
    "U12345": "donor body + our five content axes with OUR authored inline "
              "ADocument (the B0-minus-frame shape)",
    "H8B": "our famdoc VERBATIM through famload on rst (the loader/base "
           "split anchor; batch 37's H8 with blobs)",
    "U12": "donor body + our geometry + our params/types",
    "U15": "donor body + our geometry + our connector layer",
    "U25": "donor body + our params/types + our connector layer",
    "F2": "our famdoc with ONLY the donor self-Family frame fields swapped in",
    "F3": "our famdoc with ONLY the donor units registry swapped in",
    "F4": "our famdoc with ONLY the donor project-view chain swapped in "
          "(+ its 2 BrowserOrganization imports)",
}


def log(msg: str) -> None:
    print(f"[final] {msg}", flush=True)


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


def _fb():
    import famdoc_bisect as FB
    return FB


def _fbl():
    import famdoc_blobs as FBL
    return FBL


def _bisect():
    import bisect_instance_bug as B
    return B


def _residual():
    import residual_probe as R
    return R


def _room():
    import ifc_intent as T
    return T


def _pb():
    spec = importlib.util.spec_from_file_location(
        "_final_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    return pb


def _deep_equal(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == \
        json.dumps(b, sort_keys=True, default=str)


def _has_member_ref(node: Any, member_ids) -> bool:
    if isinstance(node, dict):
        return any((isinstance(v, int) and not isinstance(v, bool)
                    and v in member_ids) or _has_member_ref(v, member_ids)
                   for v in node.values())
    if isinstance(node, list):
        return any((isinstance(v, int) and not isinstance(v, bool)
                    and v in member_ids) or _has_member_ref(v, member_ids)
                   for v in node)
    return False


# ===========================================================================
# the frame model (roster discovery -- structural, class-pinned)
# ===========================================================================

def frame_roles_of(elements, self_family_id: int, tag: str) -> Dict[str, int]:
    """The frame roles of a famdoc, discovered structurally: the UnitsElem
    singleton + the DBViewProject-owned chain (Viewer + DBDrawing + the
    Viewport the drawing owns) + the self-Family.  Class-pinned; raises on
    any drift."""
    by_id = {e.elem_id: e for e in elements}
    roles: Dict[str, int] = {"self_family": self_family_id}
    units = [e for e in elements if e.class_name == "UnitsElem"]
    if len(units) != 1:
        raise RuntimeError(f"{tag}: expected exactly 1 UnitsElem, got {len(units)}")
    roles["units"] = units[0].elem_id
    dbvp = [e for e in elements if e.class_name == "DBViewProject"]
    if len(dbvp) != 1:
        raise RuntimeError(f"{tag}: expected exactly 1 DBViewProject, got {len(dbvp)}")
    roles["proj_view"] = dbvp[0].elem_id
    owned = [e for e in elements if e.owner_id == dbvp[0].elem_id]
    viewers = [e for e in owned if e.class_name == "Viewer"]
    drawings = [e for e in owned if e.class_name == "DBDrawing"]
    if len(viewers) != 1 or len(drawings) != 1:
        raise RuntimeError(f"{tag}: project chain drifted: "
                           f"{[(e.elem_id, e.class_name) for e in owned]}")
    roles["proj_viewer"] = viewers[0].elem_id
    roles["proj_drawing"] = drawings[0].elem_id
    vports = [e for e in elements if e.owner_id == drawings[0].elem_id
              and e.class_name == "Viewport"]
    if len(vports) != 1:
        raise RuntimeError(f"{tag}: expected 1 Viewport under the drawing, "
                           f"got {len(vports)}")
    roles["proj_viewport"] = vports[0].elem_id
    for role, eid in roles.items():
        got = by_id[eid].class_name
        if got != FRAME_ROLE_CLASS[role]:
            raise RuntimeError(f"{tag}: role {role} is {got}, expected "
                               f"{FRAME_ROLE_CLASS[role]}")
    return roles


def our_frame(ours) -> Dict[str, Any]:
    """OUR famdoc's frame: the roles + the assertion that role ids ==
    exactly the elements outside the six axis sets."""
    FB = _fb()
    sets = FB.axis_sets(ours)
    union = set()
    for v in sets.values():
        union |= set(v)
    outside = sorted(e.elem_id for e in ours.elements if e.elem_id not in union)
    roles = frame_roles_of(ours.elements, ours.self_family.elem_id, "ours")
    if sorted(roles.values()) != outside:
        raise RuntimeError(f"frame roster drifted: roles {sorted(roles.values())} "
                           f"!= outside-axes {outside}")
    by_id = {e.elem_id: e for e in ours.elements}
    return {"roles": roles, "outside_axis_ids": outside,
            "roster": [{"role": r, "id": i, "class": by_id[i].class_name,
                        "kind": by_id[i].kind, "owner": by_id[i].owner_id}
                       for r, i in roles.items()],
            "axis_sets": {k: list(v) for k, v in sets.items()}}


def donor_frame(donor_els) -> Dict[str, Any]:
    """The donor famdoc's frame roles + the BrowserOrganization elements its
    project view references (m_regenOnly) -- part of the donor's project-view
    furniture, imported with group G3."""
    FB = _fb()
    self_fams = [e for e in donor_els if e.class_name == "Family"
                 and (e.obj.get("m_famId") in (-1, None))]
    if len(self_fams) != 1 or self_fams[0].elem_id != FB.DONOR_SELF_FAMILY:
        raise RuntimeError(f"donor self-Family drifted: "
                           f"{[e.elem_id for e in self_fams]}")
    roles = frame_roles_of(donor_els, FB.DONOR_SELF_FAMILY, "donor")
    by_id = {e.elem_id: e for e in donor_els}
    pv = by_id[roles["proj_view"]]
    regen = list((((pv.header.get("m_parents") or {}).get("value") or {})
                  .get("m_regenOnly")) or [])
    bad = [i for i in regen
           if by_id.get(i) is None or by_id[i].class_name != "BrowserOrganization"]
    if bad or len(regen) != 2:
        raise RuntimeError(f"donor proj-view m_regenOnly drifted: {regen}")
    return {"roles": roles, "browser_orgs": regen}


# ===========================================================================
# U-probes: the union hybrids (famdoc_bisect's machinery, generalized)
# ===========================================================================

def make_union_doc(name: str, wm: int) -> Tuple[Any, Dict[str, Any], List[Any], Dict[str, Any]]:
    """The donor famdoc + the UNION of our axis subtrees for ``name``
    (make_hybrid generalized to axis SETS: an anchor is repointed to the
    donor's only when the axis that carries it is NOT in the union).
    Returns (HybridFamilyDoc, report, carried_elements, donor_ctx)."""
    FB = _fb()
    from rvt.famgen.loader import _walk_replace_ids
    from rvt.genesis.skeleton import SkelElement
    from rvt.mutate import Document

    axes = set(U_AXES[name])
    content_axes = sorted(axes - {6})
    donor_els, anchors, idmap, adoc_value, census = FB.build_donor(wm + 1)
    sf = next(e for e in donor_els if e.elem_id == anchors["self_family"])
    report: Dict[str, Any] = {"axes": sorted(axes),
                              "donor_block": [wm + 1, wm + len(donor_els)],
                              "anchors": anchors, "remap_census": census,
                              "carried": [], "repointed": {},
                              "registration": {}}

    host_fam = Document.from_file(RST).value(FB.DONOR_NATIVE_HOST_FAMILY) or {}
    part_type = int(host_fam.get("m_partType") or 0)

    prod = FB.our_product(wm + 2000)
    ours = prod.doc
    sets = FB.axis_sets(ours)
    carried_ids: set = set()
    for a in content_axes:
        carried_ids |= set(sets[f"H{a}"])
    if 5 in axes and 2 not in axes:
        carried_ids.add(FB.connector_param_id(ours))
    carried_ids = sorted(carried_ids)
    by_id = {e.elem_id: e for e in ours.elements}

    # repoint: only anchors whose carrying axis is NOT in the union
    repoint = {ours.self_family.elem_id: anchors["self_family"]}
    our_level = next(e.elem_id for e in ours.elements if e.kind == "ref_level")
    our_plan = next(e.elem_id for e in ours.elements
                    if e.class_name == "DBViewPlan")
    our_ext = next(e.elem_id for e in ours.elements
                   if e.class_name == "ExtrusionElem")
    if (1 in axes or 4 in axes) and 3 not in axes:
        repoint[our_level] = anchors["level"]
    if 3 in axes and 4 not in axes:
        repoint[our_plan] = anchors["plan_view"]
    if 5 in axes and 1 not in axes:
        repoint[our_ext] = anchors["extrusion"]
    report["repointed"] = {str(k): v for k, v in repoint.items()}

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
    report["carried"] = [{"id": e.elem_id, "class": e.class_name,
                          "kind": e.kind} for e in carried]

    # the dangling gate (famdoc_bisect's law): a carried element may
    # reference ONLY hybrid members inside the allocated id blocks
    hybrid_ids = {e.elem_id for e in donor_els} | carried_set
    our_ids = {e.elem_id for e in ours.elements}
    blocks_top = max(our_ids)
    dangling: List[Tuple[str, int]] = []

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
        raise RuntimeError(f"{name}: carried union leaves dangling "
                           f"above-watermark refs: {dangling[:6]}")
    report["dangling_above_watermark"] = 0

    # register in the donor self-Family exactly like famdoc_bisect does
    report["registration"]["membership"] = FB.register_added(
        sf, sorted(carried_set))
    param_ids = {e.elem_id for e in carried
                 if e.class_name == "ParamElemFamily"}
    if param_ids:
        with_negatives = 2 in axes            # H2's own convention
        our_sf = ours.self_family.obj
        fp_rows = (((our_sf.get("m_familyParams") or {}).get("value") or {})
                   .get("m_params") or [])
        rows = [r for r in fp_rows
                if r.get("m_paramId") in param_ids or
                (with_negatives and isinstance(r.get("m_paramId"), int)
                 and r.get("m_paramId") < 0)]
        locked = [i for i in (our_sf.get(
            "m_lockedParameterIdsForDirectManipulation") or [])
            if i in param_ids]
        groups = []
        cells = ((our_sf.get("m_cellList") or {}).get("value") or {}).get(
            "m_cells") or []
        for c in cells:
            cv = (c.get("value") or {}) if isinstance(c, dict) else {}
            for g in cv.get("m_sortedParams") or []:
                if not isinstance(g, dict):
                    continue
                keep = [pid for pid in (g.get("m_paramIds") or [])
                        if pid in param_ids or
                        (with_negatives and isinstance(pid, int) and pid < 0)]
                if keep:
                    groups.append({"m_groupTypeId":
                                   copy.deepcopy(g.get("m_groupTypeId")),
                                   "m_paramIds": keep})
            break
        report["registration"]["params"] = FB.register_param_rows(
            sf, rows, locked, groups)
        report["registration"]["params_with_negatives"] = with_negatives

    elements = sorted(donor_els + carried, key=lambda e: e.elem_id)
    doc = FB.HybridFamilyDoc(
        elements, sf, name=f"M Concrete-Square-Column {name}",
        category_id=FB.DONOR_CATEGORY, part_type=part_type,
        types=[(FB.DONOR_TYPE, {})], current_type=1)
    donor_ctx = {"idmap": idmap, "adoc_value": adoc_value, "anchors": anchors}
    return doc, report, carried, donor_ctx


def swap_inline_adoc_union(path_in: str, path_out: str, *, guid: str,
                           adoc_value: dict, idmap: Dict[int, int],
                           self_family_new: int,
                           carried_elements: Sequence[Any]) -> Dict[str, Any]:
    """U16's axis-6 swap: famdoc_bisect.swap_inline_adoc's proven recipe
    (donor inline ADocument remapped, history identity GUIDs re-keyed
    fresh) EXTENDED for a union document: the carried elements are APPENDED
    to the inline ElemTable (rows shaped like the donor's own, ids/owners in
    the hybrid space) and the IdentifierSource high-water mark is raised to
    cover them -- the same roster registration our authored ADocument
    performs (factory.author_embedded_adocument writes one ElemRec per
    element)."""
    import dataclasses
    import uuid as _uuid
    from rvt import adocument as A
    from rvt import ecc
    from rvt.container import open_rvt
    from rvt.famgen import factory as F
    from rvt.famgen.loader import _walk_replace_ids
    from rvt.roundtrip import read_entries
    from rvt.stream_encoders import wrap_global_stream
    from rvt.cfb_writer import write_cfb

    value = copy.deepcopy(adoc_value)
    _walk_replace_ids(value, idmap)
    hist = ((value.get("m_pHistory") or {}).get("value") or {})
    fresh_identity = str(_uuid.uuid4())
    guid_fields = {}
    for k in ("m_creationGUID", "m_detachGUID", "m_upgradeGUID", "m_saveAsGUID"):
        g = (hist.get(k) or {}).get("m_guid")
        if g is not None:
            guid_fields[k] = str(g)
            hist[k] = {"m_guid": fresh_identity}

    # -- the union extension: append the carried roster to the ElemTable --
    inner = ((value.get("m_elemTable") or {}).get("value") or {})
    arr = inner.get("m_elemArr")
    if not isinstance(arr, list) or not arr:
        raise RuntimeError("U16: donor inline ADocument has no ElemTable rows")
    template = copy.deepcopy(arr[-1])
    have = {int(r.get("m_id", -1)) for r in arr}
    appended = []
    for e in sorted(carried_elements, key=lambda e: e.elem_id):
        if e.elem_id in have:
            continue
        row = copy.deepcopy(template)
        row["m_id"] = int(e.elem_id)
        row["m_OwningElementId"] = (int(e.owner_id)
                                    if (e.owner_id or -1) >= 0 else -1)
        hrow = row.get("m_history")
        if isinstance(hrow, dict) and "m_originalElementId" in hrow:
            hrow["m_originalElementId"] = {"m_id64": int(e.elem_id)}
        arr.append(row)
        appended.append(int(e.elem_id))
    src = ((inner.get("m_pSource") or {}).get("value") or {})
    top = max(int(r.get("m_id", 0)) for r in arr)
    m_last_before = src.get("m_last")
    if isinstance(src.get("m_last"), int):
        src["m_last"] = max(int(src["m_last"]), top)

    payload = A.encode_latest(value, trailer=b"")
    back = A.decode_latest(payload)
    if not back.clean:
        raise RuntimeError("U16: remapped+extended donor inline ADocument "
                           "does not re-decode clean")
    with open_rvt(path_in) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    entries, tail = F.parse_content_documents(cd)
    n_before = len(entries)
    if not any(g == guid for g, _a in entries):
        raise RuntimeError(f"U16: no ContentDocuments entry for {guid}")
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
    return {"entries": n_before, "swapped_guid": guid,
            "adoc_bytes": len(payload),
            "appinfo_slots": len(a_arr),
            "appinfo_populated": sum(1 for x in a_arr if x),
            "owner_family_id": value.get("m_ownerFamilyId"),
            "owner_family_expected": self_family_new,
            "history_identity_fresh": fresh_identity,
            "history_guids_rekeyed_from": guid_fields,
            "elem_rows_appended": appended,
            "elem_rows_total": len(arr),
            "identifier_source_last": {"before": m_last_before,
                                       "after": src.get("m_last")}}


def build_union_probe(name: str) -> Dict[str, Any]:
    FB = _fb()
    T = _room()
    wm = T.host_watermark(RST)
    info: Dict[str, Any] = {"probe": name, "axis": AXES[name],
                            "base": relp(RST)}
    pdir = os.path.join(BUILD_DIR, name)
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, f"{name}.rvt")

    doc, hrep, carried, dctx = make_union_doc(name, wm)
    jdump(os.path.join(pdir, "union_report.json"), hrep)
    info["union"] = {k: hrep[k] for k in ("axes", "donor_block", "anchors",
                                          "repointed", "registration")}
    info["union"]["n_carried"] = len(hrep["carried"])
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)

    rfa = os.path.join(pdir, f"{name}_famdoc.rfa")
    info["dev_rfa"] = FB.emit_dev_rfa(doc, rfa)

    src = os.path.join(pdir, f"{name}_load.rvt")
    info["load"] = FB.famload_doc(doc, src, name)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam

    if 6 in U_AXES[name]:
        swapped = os.path.join(pdir, f"{name}_load_adoc.rvt")
        info["adoc_swap"] = swap_inline_adoc_union(
            src, swapped, guid=doc.document_guid,
            adoc_value=dctx["adoc_value"], idmap=dctx["idmap"],
            self_family_new=dctx["anchors"]["self_family"],
            carried_elements=carried)
        src = swapped
    info["immediate_parent"] = relp(src)

    info["placement"] = ("uniform template path (ConstructedSpecimens + "
                         "add_family_instance + commit; category = the "
                         "family's own; connmgr = template's)")
    prec = FB.place_probe(src, outp, symbol_id=sym, family_id=fam,
                          category=FB.DONOR_CATEGORY)
    info["instance"] = prec
    info["instance_ids"] = [prec["instance_id"]]
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


# ===========================================================================
# F-probes: our famdoc with the donor frame swapped in
# ===========================================================================

def swap_frame(ours, groups: Sequence[str]) -> Dict[str, Any]:
    """Mutate OUR finalized famdoc IN PLACE: the frame elements of
    ``groups`` replaced by the donor's equivalents (id-rebased to OUR ids,
    internal references repointed through the frame equivalence map -- the
    famgen loader's own conservative int-walk).  G1 (self-Family) follows
    the FIELD LAW (module docstring); G3 also imports the donor's two
    BrowserOrganization elements (registered in whatever self-Family the
    document then carries).  Refuses on any residual donor-block id."""
    FB = _fb()
    from rvt.famgen.loader import _walk_replace_ids
    from rvt.genesis.skeleton import SkelElement

    donor_els, adoc_value, _idx = FB.load_unit_elements(RST, FB.DONOR_UNIT)
    don_by_id = {e.elem_id: e for e in donor_els}
    don_ids = set(don_by_id)
    dfr = donor_frame(donor_els)
    ofr = our_frame(ours)
    o_roles, d_roles = ofr["roles"], dfr["roles"]
    our_by_id = {e.elem_id: e for e in ours.elements}
    our_ids = set(our_by_id)

    our_level = next(e.elem_id for e in ours.elements if e.kind == "ref_level")
    our_plan = next(e.elem_id for e in ours.elements
                    if e.class_name == "DBViewPlan")
    max_id = max(our_ids)
    bo_ids = {dfr["browser_orgs"][0]: max_id + 1,
              dfr["browser_orgs"][1]: max_id + 2}

    equiv: Dict[int, int] = {d_roles[r]: o_roles[r] for r in d_roles}
    equiv[FB.DONOR_LEVEL] = our_level
    equiv[FB.DONOR_PLAN_VIEW] = our_plan
    equiv.update(bo_ids)

    report: Dict[str, Any] = {"groups": list(groups),
                              "equivalence_map": {str(k): v
                                                  for k, v in equiv.items()},
                              "swapped": [], "imports": [],
                              "self_family_disposition": None}

    roles_to_swap: List[str] = []
    for g in groups:
        roles_to_swap.extend(GROUP_ROLES[g])

    # G2/G3 whole-element swaps
    for role in roles_to_swap:
        if role == "self_family":
            continue
        oe, de = our_by_id[o_roles[role]], don_by_id[d_roles[role]]
        if oe.rep is not None or de.rep is not None:
            raise RuntimeError(f"{role}: unexpected seq-103 rep on a frame "
                               f"element")
        d_owner = de.owner_id if (de.owner_id or 0) > 0 else -1
        if d_owner > 0 and d_owner not in equiv:
            raise RuntimeError(f"{role}: donor owner {d_owner} has no "
                               f"equivalent in our famdoc")
        # ADOPT the donor's ownership topology (part of the frame shape --
        # measured: the donor's UnitsElem is OWNED by the self-Family while
        # ours is top-level; the ownership rides in the inline ADocument's
        # ElemTable row the loader authors from owner_id)
        mapped_owner = equiv[d_owner] if d_owner > 0 else -1
        owner_was = oe.owner_id
        oe.owner_id = mapped_owner
        h, o = copy.deepcopy(de.header), copy.deepcopy(de.obj)
        _walk_replace_ids(h, equiv)
        _walk_replace_ids(o, equiv)
        oe.header, oe.obj = h, o
        report["swapped"].append({"role": role, "our_id": oe.elem_id,
                                  "donor_id": de.elem_id,
                                  "class": oe.class_name,
                                  "owner_adopted": mapped_owner,
                                  "owner_was": owner_was,
                                  "owner_changed": mapped_owner != owner_was})

    # G1: the self-Family field law
    if "self_family" in roles_to_swap:
        osf, dsf = our_by_id[o_roles["self_family"]], don_by_id[d_roles["self_family"]]
        disposition: Dict[str, Dict[str, str]] = {"obj": {}, "header": {}}
        for surface, o_node, d_node in (("obj", osf.obj, dsf.obj),
                                        ("header", osf.header, dsf.header)):
            if set(o_node) != set(d_node):
                raise RuntimeError(
                    f"self-Family {surface} key sets differ (ours-only "
                    f"{sorted(set(o_node) - set(d_node))}, donor-only "
                    f"{sorted(set(d_node) - set(o_node))}) -- the field law "
                    f"assumes identical key sets; re-measure")
            new_node: Dict[str, Any] = {}
            for k in o_node:                     # preserve OUR key order
                ov, dv = o_node[k], d_node[k]
                if k in SF_KEEP_IDENTITY:
                    new_node[k] = copy.deepcopy(ov)
                    disposition[surface][k] = "kept_ours_identity"
                elif k in SF_KEEP_REGISTRY:
                    new_node[k] = copy.deepcopy(ov)
                    disposition[surface][k] = "kept_ours_registry_coupled"
                elif (_has_member_ref(dv, don_ids)
                      or (isinstance(dv, int) and not isinstance(dv, bool)
                          and dv in don_ids)
                      or _has_member_ref(ov, our_ids)
                      or (isinstance(ov, int) and not isinstance(ov, bool)
                          and ov in our_ids)):
                    new_node[k] = copy.deepcopy(ov)
                    disposition[surface][k] = "kept_ours_membership"
                else:
                    nv = copy.deepcopy(dv)
                    _walk_replace_ids(nv, equiv)
                    new_node[k] = nv
                    disposition[surface][k] = ("donor" if not _deep_equal(dv, ov)
                                               else "donor_equal")
            if surface == "obj":
                osf.obj = new_node
            else:
                osf.header = new_node
        report["self_family_disposition"] = disposition
        report["swapped"].append({"role": "self_family",
                                  "our_id": osf.elem_id,
                                  "donor_id": dsf.elem_id, "class": "Family"})

    # G3 imports: the donor's BrowserOrganization pair
    if "G3" in groups:
        sf_now = ours.self_family
        for did, nid in sorted(bo_ids.items(), key=lambda kv: kv[1]):
            de = don_by_id[did]
            h, o = copy.deepcopy(de.header), copy.deepcopy(de.obj)
            _walk_replace_ids(h, equiv)
            _walk_replace_ids(o, equiv)
            d_owner = de.owner_id if (de.owner_id or 0) > 0 else -1
            owner = equiv.get(d_owner, -1) if d_owner > 0 else -1
            el = SkelElement(nid, "BrowserOrganization", h, o, None,
                             owner_id=owner, kind="frame_import")
            ours.elements.append(el)
            report["imports"].append({"new_id": nid, "donor_id": did,
                                      "class": "BrowserOrganization",
                                      "owner": owner})
        reg = FB.register_added(sf_now, sorted(bo_ids.values()))
        data = (((sf_now.obj.get("m_familyIds") or {}).get("value") or {})
                .get("m_data") or [])
        top_index = max((int(d.get("m_index", -1)) for d in data), default=-1)
        sf_now.obj["m_nextAbsorbedIndex"] = top_index + 1
        report["import_registration"] = dict(reg,
                                             next_absorbed_index=top_index + 1)

    # residual donor-block scan over the WHOLE document
    lo, hi = min(don_ids), max(don_ids)
    residual: List[Tuple[str, int]] = []

    def scan(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and lo <= v <= hi:
                    residual.append((path + "." + k, v))
                else:
                    scan(v, path + "." + k)
        elif isinstance(node, list):
            for j, v in enumerate(node):
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and lo <= v <= hi:
                    residual.append((f"{path}[{j}]", v))
                else:
                    scan(v, f"{path}[{j}]")

    for e in ours.elements:
        scan(e.header, f"{e.elem_id}.hdr")
        scan(e.obj, f"{e.elem_id}.obj")
        if e.rep is not None:
            scan(e.rep, f"{e.elem_id}.rep")
    if residual:
        raise RuntimeError(f"frame swap left donor-block ids in the "
                           f"document: {residual[:6]}")
    report["donor_block_residual"] = 0
    report["donor_block"] = [lo, hi]
    return report


def famdoc_reference_resolution(doc, host_path: str) -> Dict[str, Any]:
    """The schema-typed reference-resolution gate (emit_dev_rfa's RefDecoder
    pass) run directly on a famdoc against an arbitrary HOST: every
    ElementId-typed value of every seq-102 record must resolve in the unit
    or in the host ElemTable.  Build-refusing."""
    from rvt.families import FamilyIndex
    from rvt.mutate import Document
    from rvt.objects import iter_records
    from rvt.validate import _RefDecoder, find_dangling_refs
    unit = doc.to_embedded_unit()
    seg = unit["segments"][102]
    schema = FamilyIndex(RST).schema
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
    host_ids = set(Document.from_file(host_path).et_by_id)
    dangling = find_dangling_refs(refs, member)
    host_resident = [d for d in dangling if d[2] in host_ids]
    unresolved = [d for d in dangling if d[2] not in host_ids]
    out = {"host": relp(host_path),
           "refs_typed": len(refs),
           "resolve_in_unit": len(refs) - len(dangling),
           "standalone_dangling_host_resident": len(host_resident),
           "unresolved_anywhere": len(unresolved),
           "unresolved_examples": [{"owner": o, "path": p[-80:], "target": t}
                                   for o, p, t in unresolved[:8]]}
    if unresolved:
        raise RuntimeError(f"famdoc leaves {len(unresolved)} schema-typed "
                           f"reference(s) unresolved in BOTH the unit and "
                           f"the host: {unresolved[:4]}")
    return out


def _b0_style_gates(outp: str, info: Dict[str, Any]) -> None:
    """The B0 recipe's own build-time invariants: exactly ONE dangling-free
    instance, product connector manager read back from the emitted bytes,
    corpus-lawful symbol form on every PP- symbol."""
    from rvt import famload_hostfix as HF
    from rvt.mutate import Document
    insts = info.get("_instances") or []
    dangling = [i for i in insts if (i.get("n_dangling") or 0) != 0]
    if len(insts) != 1 or dangling:
        raise RuntimeError(f"{info['probe']}: expected exactly 1 "
                           f"dangling-free instance, got {len(insts)} "
                           f"(dangling: {dangling})")
    doc = Document.from_file(outp)
    cm = (doc.value(info["instance_ids"][0]) or {}).get("m_pConnectorManager")
    info["instance_connmgr"] = (cm.get("ptr_class") if isinstance(cm, dict)
                                else cm)
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or ""):
            forms[sid] = HF.assert_symbol_form(outp, sid)
    bad = [k for k, f in forms.items() if not f["ok"]]
    if bad or not forms:
        raise RuntimeError(f"{info['probe']} symbol form check failed: "
                           f"{bad or 'no PP- symbols found'}")
    info["symbol_form"] = {str(k): {"ok": f["ok"], "counts": f["counts"]}
                           for k, f in forms.items()}
    info.pop("_instances", None)


def build_f_probe(name: str) -> Dict[str, Any]:
    """One F-probe: the EXACT B0 recipe (famgen loader chain on G_ABPD under
    corpus_symbol_form + the demo's own stage_equipment placement) with the
    frame swap injected between build_product and the load."""
    B = _bisect()
    T = _room()
    from rvt import famload_hostfix as HF
    from rvt.famgen import loader as L
    groups = F_GROUPS[name]
    info: Dict[str, Any] = {"probe": name, "axis": AXES[name],
                            "base": relp(G_ABPD),
                            "recipe": "BXhf_f1i1/B0 (famgen loader on G_ABPD "
                                      "under corpus_symbol_form, demo "
                                      "stage_equipment placement) with the "
                                      f"frame swap {list(groups)} injected "
                                      "between build_product and the load"}
    chain_dir = os.path.join(BUILD_DIR, f"{name}_chain")
    if os.path.isdir(chain_dir):
        shutil.rmtree(chain_dir)
    os.makedirs(chain_dir, exist_ok=True)
    outp = os.path.join(OUT_DIR, f"{name}.rvt")
    with HF.corpus_symbol_form():
        model6 = B.demo_model()
        m1 = B.truncate_model(model6, 1)
        current = os.path.join(chain_dir, "stage_L0_base.rvt")
        shutil.copyfile(G_ABPD, current)
        wm = T.host_watermark(current)
        prod = T.build_product(m1.plan_for("PP-1"), start_id=wm + 1, solid=True)
        info["frame_swap"] = swap_frame(prod.doc, groups)
        info["reference_resolution"] = famdoc_reference_resolution(
            prod.doc, G_ABPD)
        nxt = os.path.join(chain_dir, "stage_L1_pp1.rvt")
        res = L.load_family_into_project(current, nxt, product=prod,
                                         place=False, symbol_solid=True,
                                         report_path=nxt + ".load.json",
                                         validate=False)
        if not res.ok:
            raise RuntimeError(f"{name}: famgen load failed: {res.stop_reason}")
        loaded = {"PP-1": {"symbol_id": res.plan.symbol_id,
                           "family_id": res.plan.host_family_id,
                           "content_guid": res.plan.guid,
                           "product": prod}}
        info["load"] = {"symbol_id": res.plan.symbol_id,
                        "family_id": res.plan.host_family_id,
                        "content_guid": res.plan.guid,
                        "host_watermark": wm,
                        "elements_added": len(res.elements)}
        erec = B.place_instances(m1, nxt, outp, G_ABPD, loaded)
    insts = erec.get("instances") or []
    info["_instances"] = insts
    info["equipment"] = {"instances": [{k: i.get(k) for k in
                                        ("tag", "elem_id", "symbol", "family",
                                         "n_dangling")} for i in insts]}
    info["instance_ids"] = [i["elem_id"] for i in insts]
    first = (insts or [{}])[0]
    info["symbol_id"] = first.get("symbol")
    info["family_id"] = first.get("family")
    info["placement"] = ("demo stage_equipment (the B0/BXhf_f1i1 recipe: "
                         "product connector manager, intent position)")
    info["immediate_parent"] = relp(nxt)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    _b0_style_gates(outp, info)
    jdump(os.path.join(BUILD_DIR, f"{name}_frame_swap.json"),
          info["frame_swap"])
    return info


def build_h8b() -> Dict[str, Any]:
    """H8B: our famdoc VERBATIM (corpus symbol form -- B0's own famdoc
    flavour) through CERTIFIED rvt.famload on the rst sample + the demo's
    own placement.  The loader/base split anchor: vs B0 the famdoc content
    is the same; the loader (famload vs famgen) and the base (rst vs
    G_ABPD) differ."""
    B = _bisect()
    R = _residual()
    from rvt import famload_hostfix as HF
    info: Dict[str, Any] = {"probe": "H8B", "axis": AXES["H8B"],
                            "base": relp(RST),
                            "recipe": "batch 37's H8 (residual_probe"
                                      ".famload_load + demo placement) "
                                      "rebuilt through the fixed writer "
                                      "UNDER corpus_symbol_form (so the "
                                      "famdoc matches B0's flavour exactly)"}
    pdir = os.path.join(BUILD_DIR, "H8B")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "H8B.rvt")
    src = os.path.join(pdir, "H8B_load.rvt")
    with HF.corpus_symbol_form():
        model1 = B.truncate_model(B.demo_model(), 1)
        lrec = R.famload_load(RST, src, model1)
        loaded = lrec["_loaded"]
        prod = loaded["PP-1"]["product"]
        info["reference_resolution"] = famdoc_reference_resolution(
            prod.doc, RST)
        erec = B.place_instances(model1, src, outp, RST, loaded)
    info["load"] = {k: v for k, v in lrec.items() if not k.startswith("_")}
    insts = erec.get("instances") or []
    info["_instances"] = insts
    info["equipment"] = {"instances": [{k: i.get(k) for k in
                                        ("tag", "elem_id", "symbol", "family",
                                         "n_dangling")} for i in insts]}
    info["instance_ids"] = [i["elem_id"] for i in insts]
    first = (insts or [{}])[0]
    info["symbol_id"] = first.get("symbol")
    info["family_id"] = first.get("family")
    info["placement"] = ("demo stage_equipment (the SL_f1i1/B0 recipe: "
                         "product connector manager, intent position)")
    info["immediate_parent"] = relp(src)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    _b0_style_gates(outp, info)
    return info


# ===========================================================================
# frame_diff.json (the fix spec on a frame conviction)
# ===========================================================================

#: deep-walk rank of the frame roles (the audit reaches the self-Family
#: through the symbol's type row / params / geom tables first; the units
#: registry is a document singleton; the project-view chain is barely
#: walked from an instance)
FRAME_RANK = {"self_family": 1, "units": 2, "proj_view": 3,
              "proj_viewer": 3, "proj_drawing": 3, "proj_viewport": 3}


def frame_diff() -> Dict[str, Any]:
    """The per-element field diff of OUR frame vs the DONOR's, ranked
    deep-walk-visited first, each self-Family key tagged with its swap
    disposition -- THE FIX SPEC once the frame is convicted."""
    FB = _fb()
    FB._install_schema()                                       # noqa: SLF001
    t0 = time.time()
    prod = FB.our_product(2_000_000)
    ours = prod.doc
    donor_els, _adoc, _idx = FB.load_unit_elements(RST, FB.DONOR_UNIT)
    don_by_id = {e.elem_id: e for e in donor_els}
    don_ids = set(don_by_id)
    our_by_id = {e.elem_id: e for e in ours.elements}
    our_ids = set(our_by_id)
    ofr = our_frame(ours)
    dfr = donor_frame(donor_els)

    out: Dict[str, Any] = {
        "law": "A = the donor (Autodesk) frame element; B = OURS.  The "
               "frame = the six famdoc elements outside all six content "
               "axis sets (batch 44's B1..B6 categories).  Rank = deep-walk "
               "order from a placed instance.  disposition = what the "
               "F-probe swap did with each self-Family key: 'donor' keys "
               "ARE tested by F1/F2 (donor value swapped in); "
               "'kept_ours_*' keys are the recorded residue the swap "
               "cannot test (membership registries, identity, "
               "registry-coupled counters).",
        "frame_roster": ofr["roster"],
        "donor_roles": dfr["roles"],
        "donor_browser_org_imports": dfr["browser_orgs"],
        "checklist": [],
        "seconds": None,
    }

    inv_roles = {v: k for k, v in dfr["roles"].items()}
    inv_roles_o = {v: k for k, v in ofr["roles"].items()}
    for role in ("self_family", "units", "proj_view", "proj_viewer",
                 "proj_drawing", "proj_viewport"):
        oe = our_by_id[ofr["roles"][role]]
        de = don_by_id[dfr["roles"][role]]
        a_owner = inv_roles.get(de.owner_id, de.owner_id if (de.owner_id or 0) > 0 else None)
        b_owner = inv_roles_o.get(oe.owner_id, oe.owner_id if (oe.owner_id or 0) > 0 else None)
        entry: Dict[str, Any] = {
            "rank": FRAME_RANK[role], "role": role,
            "class": oe.class_name,
            "B_id": oe.elem_id, "A_id": de.elem_id,
            "ownership": {"A_owner": a_owner, "B_owner": b_owner,
                          "differs": a_owner != b_owner,
                          "note": "owner rides in the inline ADocument "
                                  "ElemTable row (m_OwningElementId), not "
                                  "the element bytes; the F-swap ADOPTS the "
                                  "donor topology"},
            "obj_diff": FB._diff_objects(de.obj, oe.obj),
            "header_diff": FB._diff_objects(de.header, oe.header),
        }
        if role == "self_family":
            disposition = {}
            for k in de.obj:
                dv, ov = de.obj[k], oe.obj.get(k)
                if k in SF_KEEP_IDENTITY:
                    disposition[k] = "kept_ours_identity"
                elif k in SF_KEEP_REGISTRY:
                    disposition[k] = "kept_ours_registry_coupled"
                elif (_has_member_ref(dv, don_ids)
                      or _has_member_ref(ov, our_ids)):
                    disposition[k] = "kept_ours_membership"
                else:
                    disposition[k] = ("donor" if not _deep_equal(dv, ov)
                                      else "donor_equal")
            entry["swap_disposition_obj"] = disposition
            entry["swap_disposition_header"] = {
                k: ("kept_ours_membership"
                    if (_has_member_ref(de.header[k], don_ids)
                        or _has_member_ref(oe.header.get(k), our_ids))
                    else ("donor" if not _deep_equal(de.header[k],
                                                     oe.header.get(k))
                          else "donor_equal"))
                for k in de.header}
            entry["untested_by_swap"] = sorted(
                k for k, v in disposition.items()
                if v.startswith("kept_ours") and not _deep_equal(
                    de.obj[k], oe.obj.get(k)))
        out["checklist"].append(entry)
    out["checklist"].sort(key=lambda e: (e["rank"], e["role"]))
    out["seconds"] = round(time.time() - t0, 1)
    path = os.path.join(OUT_DIR, "frame_diff.json")
    jdump(path, out)
    log(f"frame_diff.json -> {relp(path)} ({out['seconds']}s)")
    return out


# ===========================================================================
# build driver (per-probe: build + accounting + blob proof + gates)
# ===========================================================================

def base_of(name: str) -> str:
    return G_ABPD if name.startswith("F") else RST


def _accounting(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
    B = _bisect()
    FBL = _fbl()
    base = base_of(name)
    child = os.path.join(ROOT, info["file"])
    parent = os.path.join(ROOT, info["immediate_parent"])
    out: Dict[str, Any] = {}
    out["probe"] = B.account(name, child, parent, declared_base=base,
                             instance_ids=info.get("instance_ids") or [])
    out["hop_load"] = B.account(name + ".hop_load", parent, base,
                                declared_base=base, instance_ids=[],
                                with_regdiff=False)
    out["blob_proof"] = FBL.blob_proof(child, base)
    out["blob_proof_parent"] = FBL.blob_proof(parent, base)
    return out


def _gates(name: str, info: Dict[str, Any], acct: Dict[str, Any]) -> Dict[str, Any]:
    rep = acct["probe"]
    hop = acct["hop_load"]
    va = rep["validator"]
    bp = acct["blob_proof"]
    if name.startswith("U"):
        unresolved = (((info.get("dev_rfa") or {}).get("reference_resolution")
                       or {}).get("unresolved_anywhere"))
    else:
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
    }
    if not name.startswith("U"):
        g["frame_donor_block_residual"] = (info.get("frame_swap") or {}).get(
            "donor_block_residual") if name.startswith("F") else None
        g["symbol_form_ok"] = all(
            f.get("ok") for f in (info.get("symbol_form") or {}).values()) \
            if info.get("symbol_form") else None
    ok = (g["validator_errors"] == 0 and g["validator_unexpected"] == 0
          and g["four_registry_coherent"] is True
          and g["load_hop_units_added"] == 1
          and g["instance_hop_units_added"] == 0
          and g["survivor_law_ok"] and g["identity"] == "PASS"
          and g["blob_all_units_64B"] and g["blob_added_nonce_verified"]
          and g["blob_units_added"] == 1
          and unresolved == 0)
    if name.startswith("F"):
        ok = ok and g.get("frame_donor_block_residual") == 0 \
            and g.get("symbol_form_ok") is True
    if name == "H8B":
        ok = ok and g.get("symbol_form_ok") is True
    g["gates_ok"] = bool(ok)
    return g


def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    FB = _fb()
    FB._install_schema()                                       # noqa: SLF001
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/famdoc_final.py",
                           "bases": {"U_probes": relp(RST),
                                     "H8B": relp(RST),
                                     "F_probes": relp(G_ABPD)},
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
            if name.startswith("U"):
                info = build_union_probe(name)
            elif name == "H8B":
                info = build_h8b()
            else:
                info = build_f_probe(name)
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
                f"load hop, blob 64B x{acct['blob_proof']['units_total']} "
                f"(added nonce {'OK' if g['blob_added_nonce_verified'] else 'BAD'}), "
                f"refs unresolved {g['famdoc_refs_unresolved_anywhere']}, "
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
# probes.json (the decision table the orchestrator reads)
# ===========================================================================

READING = {
    "CTRL FAIL (either)": "round VOID for that base's probes (the rst "
                          "control voids U16/U12345/H8B/U12/U15/U25; the "
                          "G_ABPD control voids F1/F2/F3/F4).",
    "U16 FAIL": "A COMBINATION IS GUILTY: the union of our added axes "
                "fails on the donor frame where every single axis passed "
                "(B1..B6).  Read U12345 to place the inline-ADocument: "
                "U12345 FAIL too => the guilty combination is inside the "
                "five content axes -- read the pairs (U12/U15/U25, "
                "already in this batch); U12345 PASS (U16 FAIL alone) => "
                "the donor-ADocument SWAP is implicated in combination -- "
                "an inversion of B6's single-axis PASS; re-run the union "
                "ladder holding the ADocument axis fixed.",
    "U16 PASS + U12345 FAIL": "the guilty combination INVOLVES our authored "
                "inline-ADocument flavour interacting with our content "
                "(the donor ADocument rescues the same union).  Fix target: "
                "factory.author_embedded_adocument vs the donor's populated "
                "registries; next ladder swaps the donor ADocument into "
                "the B0 shape.",
    "U16 PASS + U12345 PASS": "NO union of our added axes reproduces B0's "
                "failure on the donor frame => the defect is in what B0 "
                "carries and the unions do not: OUR FRAME (self-Family / "
                "units registry / project-view chain fields), the famgen "
                "loader flavour, or the G_ABPD base.  Read F1 and H8B.",
    "F1 PASS (with U16+U12345 PASS)": "FRAME CONVICTION CONFIRMED FROM "
                "BOTH DIRECTIONS: our content on the donor frame passes "
                "(U-probes) AND the donor frame under our content passes "
                "with loader+base+recipe held EXACTLY at B0's (F1) while "
                "B0 fails.  The guilty fields are in frame_diff.json's "
                "'donor'-disposition entries; F2/F3/F4 name the element "
                "group (each is ONE group swapped).",
    "F1 FAIL": "the frame's guilt (if any) is NOT in the swappable element "
               "fields.  Read H8B: H8B PASS => our COMPLETE famdoc (frame "
               "included) is lawful under famload-on-rst => the defect "
               "lives in the famgen-loader flavour or the G_ABPD base, "
               "not the famdoc -- pivot the hunt to the loader delta.  "
               "H8B FAIL => our famdoc content is rejected under BOTH "
               "loaders => the residue is in what no probe here varies: "
               "element ORDER / unit shape, the kept-ours self-Family "
               "fields (frame_diff.json 'untested_by_swap'), or the "
               "document identity surfaces.",
    "H8B verdict": "the loader/base split anchor: B0 (famgen+G_ABPD) FAIL "
                   "is batch 44's anchor; H8B (famload+rst, SAME famdoc "
                   "flavour incl. corpus symbol form) PASS convicts the "
                   "loader/base delta; H8B FAIL re-convicts our famdoc "
                   "content under the exonerated machinery (B7) and makes "
                   "the F-probes' frame reads decisive.",
    "pairs U12/U15/U25 (read on U16 FAIL + U12345 FAIL)": "each pair FAIL "
                "convicts that axis pair's interaction (add-form unions: "
                "independent); all three PASS => the guilty combination "
                "needs a triple or axes 3/4 -- next round builds the "
                "remaining pairs/triples (mechanical).",
    "singles F2/F3/F4 (read on F1 PASS)": "the group whose single-swap "
                "PASSES carries the guilty fields (its donor form heals "
                "B0's recipe); a group whose single-swap FAILS is "
                "exonerated for the fields it swaps.  F2=self-Family, "
                "F3=units registry, F4=project-view chain (+2 "
                "BrowserOrganization imports).",
    "honest residue": "the F-swap keeps membership registries, identity "
                "fields and registry-coupled counters OURS (they cannot "
                "carry donor values over our roster); frame_diff.json "
                "lists every kept-ours key that DIFFERS from the donor "
                "under 'untested_by_swap' -- on F1 FAIL + H8B FAIL those "
                "fields plus element order/unit shape are the remaining "
                "suspect space.",
}

EXPECTED = {
    "U16": "the combination-vs-frame decider, direction 1: FAIL => "
           "combination; PASS => frame (with U12345)",
    "F1": "the combination-vs-frame decider, direction 2: PASS (with U16 "
          "PASS) => frame convicted, fix spec = frame_diff.json",
    "U12345": "tightens U16's read: the B0-minus-frame shape (our authored "
              "ADocument)",
    "H8B": "the loader/base split anchor (batch 37 H8 FAILED empty-blob; "
           "with blobs the verdict is NEW information)",
    "U12": "read on U16+U12345 FAIL: geometry x params interaction",
    "U15": "read on U16+U12345 FAIL: geometry x connector interaction",
    "U25": "read on U16+U12345 FAIL: params x connector interaction",
    "F2": "read on F1 PASS: does the self-Family frame-field swap alone heal?",
    "F3": "read on F1 PASS: does the units-registry swap alone heal?",
    "F4": "read on F1 PASS: does the project-view-chain swap alone heal?",
}

ONETHING = {
    "U16": "donor famdoc + the UNION of our five content subtrees (35 "
           "elements, registered like donor members) + the donor's OWN "
           "inline ADocument (elem-table extended for the carried roster) "
           "-- every single one of these additions PASSED alone in batch "
           "44; this asks them TOGETHER.",
    "F1": "OUR famdoc built by the exact B0 recipe with the donor's frame "
          "swapped in: self-Family frame fields (member/identity/counter "
          "surfaces kept ours), units registry, project-view chain (+ the "
          "donor's 2 BrowserOrganization imports).  The ONLY delta vs "
          "batch 44's failing B0 is the frame.",
    "U12345": "donor famdoc + the same 35-element union with OUR authored "
              "inline ADocument (what B0 actually carries) -- the "
              "B0-minus-frame probe.",
    "H8B": "our famdoc VERBATIM (corpus symbol form, B0's famdoc flavour) "
           "through famload on rst + the demo's own placement -- only the "
           "loader and base differ from B0.",
    "U12": "donor famdoc + our geometry subtree + our param/type layer "
           "(registered with the built-in rows, H2's convention).",
    "U15": "donor famdoc + our geometry subtree + our connector layer "
           "(the connector's face ref resolves to OUR carried extrusion).",
    "U25": "donor famdoc + our param/type layer + our connector layer "
           "(the connector's face ref repointed to the donor extrusion).",
    "F2": "B0's recipe with ONLY the self-Family frame-field swap "
          "(disposition table in frame_diff.json).",
    "F3": "B0's recipe with ONLY the units registry element swapped for "
          "the donor's (ids repointed).",
    "F4": "B0's recipe with ONLY the project-view chain swapped for the "
          "donor's (+2 BrowserOrganization imports, registered).",
}


def _roster_for_manifest() -> Any:
    """The frame roster for probes.json, read from frame_diff.json (the fix
    spec computes it authoritatively)."""
    p = os.path.join(OUT_DIR, "frame_diff.json")
    try:
        with open(p) as fh:
            d = json.load(fh)
        return {"roster": d["frame_roster"],
                "donor_roles": d["donor_roles"],
                "donor_browser_org_imports": d["donor_browser_org_imports"],
                "note": "the SIX elements of our famdoc outside every "
                        "batch-44 content axis, in three swap groups "
                        "(G1 self-Family, G2 units, G3 project-view chain "
                        "+ the donor's BrowserOrganization pair)"}
    except (OSError, ValueError, KeyError):
        return "run `tools/famdoc_final.py diff`; also in frame_diff.json"


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
            "file": f"experiments/famdoc_final/{name}.rvt",
            "base": relp(base_of(name)),
            "kind": "probe",
            "axis": AXES[name],
            "n_families": 1, "n_instances": 1, "n_walls": 0,
            "the_ONE_thing_it_tests": ONETHING[name],
            "expected": EXPECTED[name],
            "md5": info.get("md5"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "immediate_parent": info.get("immediate_parent"),
            "blob_proof": {k: bp.get(k) for k in
                           ("units_total", "blob_len_histogram",
                            "units_added_vs_base", "added_nonce_verified")},
            "gates": gates,
        }
        if name.startswith("F"):
            entry["frame_groups_swapped"] = list(F_GROUPS[name])
        if name.startswith("U"):
            entry["axes_unioned"] = list(U_AXES[name])
        probes.append(entry)
    manifest = {
        "stream": "famdoc-final: COMBINATION vs FRAME -- the round that "
                  "decides.  Batch 44 (verdicts #38): B7 PASS (machinery "
                  "exonerated with blobs), B1..B6 ALL PASS (every content "
                  "axis lawful alone), B0 FAIL (our complete famdoc).  "
                  "This round asks the two remaining questions from both "
                  "directions: U-probes put our axis UNIONS on the donor "
                  "frame; F-probes put the donor FRAME under our complete "
                  "content via the exact B0 recipe.",
        "bases": {"U_probes+H8B": relp(RST), "F_probes": relp(G_ABPD)},
        "frame_roster": _roster_for_manifest(),
        "note": "U-probes = untouched rst sample + ONE loaded hybrid famdoc "
                "+ ONE placed instance (famdoc_bisect's machinery "
                "generalized to axis unions; donor = the sample's own "
                "M_Concrete-Square-Column).  F-probes = G_ABPD + ONE famgen "
                "family + ONE instance (the B0/BXhf_f1i1 recipe verbatim) "
                "with the donor frame swapped into OUR famdoc before the "
                "load.  H8B = our famdoc verbatim through famload on rst.  "
                "EVERY probe's added unit carries the 64-byte 0x0f3f blob "
                "(machine-verified nonce).  PROOF-ONLY sample-derived "
                "content, quarantined, never shipped.  Fresh GUIDs per "
                "rebuild -- re-hash after any rerun.",
        "upload_order_max_information_first": list(LADDER),
        "controls": {
            "rst": {"source": relp(RST),
                    "voids": "U16,U12345,H8B,U12,U15,U25 on CTRL FAIL"},
            "g_abpd": {"source": relp(G_ABPD),
                       "voids": "F1,F2,F3,F4 on CTRL FAIL"},
        },
        "reading_the_matrix": READING,
        "companion_evidence": {
            "accounting": "experiments/famdoc_final/accounting.json",
            "frame_diff_fix_spec": "experiments/famdoc_final/frame_diff.json",
            "per_probe_reports": "experiments/famdoc_final/_build/<rung>/",
            "axis_fix_spec": "experiments/famdoc_bisect/famdoc_diff.json",
            "prior_round": "experiments/famdoc_blobs/probes.json (batch 44)",
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
    FB = _fb()
    FB._install_schema()                                       # noqa: SLF001
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
    rst copy for the U-probes/H8B + a G_ABPD copy for the F-probes)."""
    pb = _pb()
    FBL = _fbl()
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
    if not os.path.isfile(os.path.join(OUT_DIR, "frame_diff.json")):
        raise SystemExit("frame_diff.json missing -- run diff first (it is "
                         "the round's fix spec)")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = FBL.next_batch_number()
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
        "tool": "tools/famdoc_final.py (via tools/probe_batch.py primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified' (or is an Autodesk sample "
                "source); the batch carries >= 1 CONTROL = a byte-identical "
                "copy of a certified file; read the round with "
                "read_batch_verdicts(): control FAIL => every verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 2,
        "controls": {"rst": ctrl_rst.staged_as, "g_abpd": ctrl_g.staged_as,
                     "note": "the rst control gates U16/U12345/H8B/U12/U15/"
                             "U25; the G_ABPD control gates F1/F2/F3/F4 -- "
                             "either control FAIL voids its probes"},
        "note": "famdoc-final: COMBINATION vs FRAME, both directions.  "
                "Batch 44 left exactly two suspects for B0's FAIL "
                "(B7+B1..B6 all PASS): an axis combination, or the residual "
                "frame (self-Family / units registry / project-view chain "
                "-- the six famdoc elements outside every content axis).  "
                "U16 = all our additions at once on the donor body; F1 = "
                "the donor frame swapped into OUR famdoc under the exact "
                "B0 recipe; U12345/H8B tighten the loader+ADocument reads; "
                "U12/U15/U25 pre-build the pair bisection; F2/F3/F4 "
                "pre-build the frame singles.  Read "
                "experiments/famdoc_final/probes.json reading_the_matrix; "
                "the frame fix spec is "
                "experiments/famdoc_final/frame_diff.json.",
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

def roster() -> Dict[str, Any]:
    """Print (and return) the frame roster -- the record's centerpiece."""
    FB = _fb()
    FB._install_schema()                                       # noqa: SLF001
    prod = FB.our_product(2_000_000)
    ofr = our_frame(prod.doc)
    donor_els, _a, _i = FB.load_unit_elements(RST, FB.DONOR_UNIT)
    dfr = donor_frame(donor_els)
    log(f"OUR famdoc: {len(prod.doc.elements)} elements; six-axis union "
        f"{sum(len(v) for v in ofr['axis_sets'].values())}; FRAME = "
        f"{len(ofr['roster'])} elements:")
    for r in ofr["roster"]:
        log(f"  {r['role']:<14} id {r['id']}  {r['class']:<16} "
            f"(donor equivalent {dfr['roles'][r['role']]})")
    log(f"  + donor project-view furniture imported with G3: "
        f"BrowserOrganization x2 ({dfr['browser_orgs']})")
    return {"ours": ofr, "donor": dfr}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the 10 probes")
    b.add_argument("--only", default=None, help="comma-separated probe subset")
    sub.add_parser("roster", help="print the frame roster")
    sub.add_parser("diff", help="frame_diff.json (the frame fix spec)")
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
    if a.cmd == "roster":
        _fb()._install_schema()                                # noqa: SLF001
        roster()
        return 0
    if a.cmd == "diff":
        _fb()._install_schema()                                # noqa: SLF001
        frame_diff()
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
