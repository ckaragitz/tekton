#!/usr/bin/env python
"""subtractive.py -- THE SUBTRACTIVE LADDER (subtractive stream, 2026-08-05).

WHERE THE HUNT STANDS (genesis-audit VERDICTS #39, batch 45).  With mandatory
64-byte unit blobs: donor famdoc body + ANY/ALL of our six content axes =
PASS (U16, U12345, all pairs); our lean 41-element famdoc in ANY variant
(donor frame, any base, any loader: F1..F4, H8B, B0) = FAIL.  INVERSION: the
donor body accepts everything of ours; nothing swapped into OUR document
saves it.  So the audit requires something the donor's remaining body
elements PROVIDE and our lean document LACKS (missing element
infrastructure), or a whole-document property (element order / unit shape).

THIS TOOL runs the SUBTRACTIVE delta-debugging round on U16 (the certified
PASS substrate): delete the donor's extra elements from U16 by CLASS-GROUP
until the PASS flips to FAIL -- the flip names the required infrastructure.

THE CLASSIFICATION (donor = M_Concrete-Square-Column, rst unit 36, 417
elements; measured, structural, test-pinned).  The FRAME (self-Family +
UnitsElem + project-view chain, 6 elements) is hard-self-contained (its only
non-registry references are to each other) and is the only KEPT donor floor.
Every other donor element (411) partitions into SEVEN class-groups:

  S1  sketch/geometry infra     13  donor extrusion + its sketch (VarSketch,
                                    4 CurveElem, SketchPlane) + 3 standalone
                                    sketch-stub pairs (VarSketch+SketchPlane)
  S2  dims/constraints          11  LinearDimString / RadialDim / Alignment
                                    outside the nested family
  S3  datum/reference infra     19  2 Levels + LevelAttributes (+its cat/
                                    gstyle/font furniture) + 7 RefPlanes +
                                    2 datum-hosted SketchPlanes +
                                    BaseLevelTracker + TrueNorth
  S4  view/annotation locals    85  20 extra DBViewTypes + section/3d/
                                    drafting/2nd-plan view chains (Viewer /
                                    DBDrawing / Viewport / ExtentElem /
                                    SketchGrid / view SketchPlanes) + the
                                    view-type attrs (CalloutTag, Section- /
                                    InteriorElevAttributes + subtrees) + Sun
                                    + 2 BrowserOrganization + ModelClipBox
  S5  styles/categories/fonts  125  DimensionStyle / LeaderStyle / SpotElev /
                                    TextNote / TagNote / FilledRegion attrs +
                                    Text3dAttrSymbol + RevisionCloudAttr +
                                    ReferenceViewerAttributes + their OWNED
                                    CategoryElem/GStyleElem/FontElem subtrees
  S6  nested level-head family 116  Family 'Level Head - Upgrade' + its 112
                                    registered members (its own view types,
                                    styles, filled regions, tag notes, 2D
                                    curves, dims) + FamilySymbol +
                                    FamilySurrogate + FamSymSurrogate
  S7  struct/settings residue   42  LoadCase/LoadNature pairs, StructConn
                                    types, the settings singletons (area /
                                    autocam / autojoin / coordsys / divide /
                                    draworder / dwg / step / pen / daylight /
                                    appearance parents ...), the SF's one
                                    ParamElemFamily, misc attrs

THE DELETION LAW (famdoc adaptation of the certified reduction discipline):
a set S deletes lawfully iff after (a) removing S's elements, (b) scrubbing
S-ids from REGISTRY surfaces only -- any Family element's membership
registries (m_familyIds, m_familyParams, m_pFamilyTypes rows, locked list,
order cell, m_deletableElements, m_oFamDimConstrMgr, m_refs, m_fsdos), any
survivor's header m_parents lists (m_deletion / m_regenOnly /
m_appearanceParents), a VarSketch's dim registries (m_dimIds / m_dimData),
and the inline ADocument's ElemTable rows -- NO survivor node carries an
S-id anywhere (machine-scanned; build-refusing).  Elements that reference S
on NON-registry surfaces are CASCADED into S (delete-with-referrer; children
cascade with owners).  The frame + our carried elements may never cascade --
that would mark the group undeletable-alone (measured: never happens; the
ONE binding is LevelAttributes.m_familyTagId -> the nested level-head
FamilySymbol, DETACHED to -1 for SUB_S6, our famgen's own certified form).
The donor inline ADocument's deep registries (AppInfoManager) keep their
entries (the genesis deletion precedent: dangling tolerated, censused).

THE LADDER (11 probes; reading order = maximum information first):

  SUB_ALL   U16 minus ALL seven groups = the donor reduced to OUR lean shape
            (donor frame 6 + our carried 35 = 41 elements) -- the anchor;
            expected FAIL (B0/H8B/F1 all fail with lean rosters).
  SUB_S5    minus styles/categories/fonts (top prior: the largest
            infrastructure family our famdoc lacks ENTIRELY)
  SUB_S6    minus the nested level-head family cluster
  SUB_S4    minus the view/annotation locals
  SUB_S7    minus struct/settings residue
  SUB_S2    minus dims/constraints
  SUB_S1    minus sketch/geometry infra (ours remains)
  SUB_S3    minus datum/reference infra (heaviest cascade: the donor's
            plan/section furniture crops to these planes and follows)
  SUB_S5A   minus the dim-flavored HALF of S5 (DimensionStyle + LeaderStyle
            + SpotElevationStyle constellations) -- the pre-built bisection
            of the top-prior group
  SUB_S5B   minus the text/region-flavored HALF of S5
  SUB_O1    the ORDER probe: our famdoc, ids re-assigned so ascending-id
            order follows the DONOR's class-ordering convention, through the
            EXACT B0 recipe (famgen loader on G_ABPD, corpus symbol form,
            demo placement).  PASS => element order was the missing
            whole-document property; FAIL => order alone does not heal B0.

READING: U16 (certified PASS) brackets the top; SUB_ALL the bottom.  A
single SUB_Sx FAIL convicts that group's infrastructure as REQUIRED (the
document retains OUR copy of every roster class, so the conviction names
donor-only furniture); SUB_Sx PASS exonerates it alone.  ALL singles PASS +
SUB_ALL FAIL => the requirement is a UNION (next round: cumulative
deletions).  ALL singles FAIL => suspect the shared deletion mechanics
(ADocument registry dangling) FIRST -- rebuild one single with a scrubbed
ADocument before reading convictions.

PROOF-ONLY: every probe embeds Autodesk sample content and stays
quarantined in experiments/ (zero donors in shipped output).  STAGE ONLY --
the orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/subtractive.py classify        # class->group map
    .venv/bin/python tools/subtractive.py build           # all 11 probes
    .venv/bin/python tools/subtractive.py build --only SUB_ALL,SUB_S5
    .venv/bin/python tools/subtractive.py verify          # re-run gates
    .venv/bin/python tools/subtractive.py spec            # author_spec.json
    .venv/bin/python tools/subtractive.py stage           # probe_batch + controls

TERRITORY: this file, ``experiments/subtractive/**``,
``tests/test_subtractive.py``, ``docs/inbox/subtractive.md``, plus staging
copies probe_batch writes under ``experiments/acceptance/``.  IMPORTS (never
edits): tools/famdoc_bisect.py, tools/famdoc_final.py, tools/famdoc_blobs.py,
tools/bisect_instance_bug.py, tools/probe_batch.py, tools/ifc_intent.py,
rvt.famgen.loader, rvt.famload_hostfix.  No Autodesk install dirs, no
browser, no full-suite runs.
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
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "subtractive")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")

#: staging/reading order = maximum information first
LADDER = ("SUB_ALL", "SUB_S5", "SUB_S6", "SUB_S4", "SUB_S7", "SUB_S2",
          "SUB_S1", "SUB_S3", "SUB_S5A", "SUB_S5B", "SUB_O1")

GROUPS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")

#: measured partition sizes (classify() asserts these -- drift refuses)
EXPECT_SIZES = {"S1": 13, "S2": 11, "S3": 19, "S4": 85, "S5": 125,
                "S6": 116, "S7": 42}

#: measured cascade-pull sizes (closure - seed; classify() asserts)
EXPECT_PULLS = {"S1": 6, "S2": 0, "S3": 57, "S4": 21, "S5": 12, "S6": 0,
                "S7": 2}

#: the one detach normalization: survivor LevelAttributes' family-tag symbol
#: ref set to OUR famgen form (measured: our certified famdoc carries -1)
DETACH_LAW = ("LevelAttributes.obj.m_familyTagId -> -1 (our famgen authors "
              "-1; the donor binds the nested level-head FamilySymbol)")

#: class -> primary group (cat/gstyle/font + SketchPlane resolved per-element)
CLASS_GROUP = {
    "S1": ("ExtrusionElem", "VarSketch", "CurveElem"),
    "S2": ("LinearDimString", "RadialDim", "Alignment"),
    "S3": ("RefPlane", "Level", "LevelAttributes", "BaseLevelTracker",
           "TrueNorth"),
    "S4": ("DBViewPlan", "DBViewSection", "DBView3d", "DBViewDrafting",
           "Viewer", "Viewer3d", "DBDrawing", "Viewport", "DBViewType",
           "ExtentElem", "SketchGrid", "ModelClipBox", "CalloutTag",
           "SectionAttributes", "InteriorElevAttributes",
           "SunAndShadowSettings", "BrowserOrganization"),
    "S5": ("DimensionStyle", "LeaderStyle", "SpotElevationStyle",
           "TextNoteAttributes", "TagNoteAttributes",
           "FilledRegionAttributes", "Text3dAttrSymbol", "RevisionCloudAttr",
           "ReferenceViewerAttributes", "FilledRegion", "TagNote"),
    "S7": ("LoadNatureElem", "LoadCaseElem", "StructConnectionType",
           "AnalyticalLinkType", "StructSettingsElem", "AreaSettingsElem",
           "AutoJoinTracker", "CoordinateSystemDisplayElem",
           "DefaultDivideSettings", "DrawOrder3dElem",
           "Dwg2dExportUserSettingsData", "STEPExportSettings",
           "DaylightSourceIdSet", "PenWidthTableElem", "CoverType",
           "PropertyAttr", "RevealAttr", "CorniceAttr",
           "ComponentRepeaterSlotSpecialType",
           "RvtLinkInstanceAppearanceParentElem",
           "SketchGridAppearanceParentElem", "ParamElemFamily",
           "AutoCamSettingsElem"),
}

#: dim-flavored constellation roots = the S5A half
S5A_ROOTS = ("DimensionStyle", "LeaderStyle", "SpotElevationStyle")

#: registry top-level keys on ANY Family element (scrub-lawful surfaces)
FAMILY_REG_KEYS = ("m_familyIds", "m_familyParams", "m_pFamilyTypes",
                   "m_lockedParameterIdsForDirectManipulation", "m_cellList",
                   "m_oFamDimConstrMgr", "m_deletableElements", "m_refs",
                   "m_fsdos")
#: registry top-level keys on a VarSketch (its dim membership)
SKETCH_REG_KEYS = ("m_dimIds", "m_dimData")
#: header parent lists (scrub-lawful on every survivor)
PARENT_LISTS = ("m_deletion", "m_regenOnly", "m_appearanceParents")

AXES = {
    "SUB_ALL": "U16 minus ALL seven class-groups: the donor reduced to OUR "
               "lean shape (frame 6 + our carried 35 = 41 elements)",
    "SUB_S5": "U16 minus S5 styles/categories/fonts (the annotation-style "
              "constellations + their category/gstyle/font subtrees)",
    "SUB_S6": "U16 minus S6 the nested 'Level Head - Upgrade' family cluster "
              "(family + 112 registered members + symbol + surrogates)",
    "SUB_S4": "U16 minus S4 view/annotation locals (extra view types + "
              "section/3d/drafting/2nd-plan chains + view-type attrs)",
    "SUB_S7": "U16 minus S7 struct/settings residue (load cases/natures, "
              "struct connection types, settings singletons, the SF param)",
    "SUB_S2": "U16 minus S2 dims/constraints (LinearDimString / RadialDim / "
              "Alignment outside the nested family)",
    "SUB_S1": "U16 minus S1 sketch/geometry infra (donor extrusion + sketch "
              "machinery; OUR carried geometry remains)",
    "SUB_S3": "U16 minus S3 datum/reference infra (levels, level attrs, ref "
              "planes, trackers; the view furniture cropping to them "
              "cascades)",
    "SUB_S5A": "U16 minus the dim-flavored HALF of S5 (DimensionStyle + "
               "LeaderStyle + SpotElevationStyle constellations)",
    "SUB_S5B": "U16 minus the text/region-flavored HALF of S5 (TextNote / "
               "TagNote / FilledRegion attrs, Text3d, RevisionCloud, "
               "ReferenceViewer)",
    "SUB_O1": "the ORDER probe: our famdoc renumbered to the donor's "
              "class-ordering convention through the EXACT B0 recipe",
}


def log(msg: str) -> None:
    print(f"[subtr] {msg}", flush=True)


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


def _ff():
    import famdoc_final as FF
    return FF


def _fbl():
    import famdoc_blobs as FBL
    return FBL


def _bisect():
    import bisect_instance_bug as B
    return B


def _room():
    import ifc_intent as T
    return T


def _pb():
    spec = importlib.util.spec_from_file_location(
        "_subtractive_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    return pb


# ===========================================================================
# the donor graph (edges with paths, ownership, registry law)
# ===========================================================================

_IDX_RE = re.compile(r"\[\d+\]")


def _norm(p: str) -> str:
    return _IDX_RE.sub("[]", p)


def donor_graph() -> Dict[str, Any]:
    """The donor famdoc's reference graph in ORIGINAL id space: elements,
    int-walk edges (src, path, dst), ownership, the registry-path law, and
    the hard (non-registry) adjacency."""
    FB = _fb()
    els, adoc_value, _idx = FB.load_unit_elements(RST, FB.DONOR_UNIT)
    by_id = {e.elem_id: e for e in els}
    ids = set(by_id)
    edges: List[Tuple[int, str, int]] = []

    def walk(node, src, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in ids and v != src:
                    edges.append((src, path + "." + k, v))
                else:
                    walk(v, src, path + "." + k)
        elif isinstance(node, list):
            for j, v in enumerate(node):
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in ids and v != src:
                    edges.append((src, f"{path}[{j}]", v))
                else:
                    walk(v, src, f"{path}[{j}]")

    for e in els:
        walk(e.header, e.elem_id, "hdr")
        walk(e.obj, e.elem_id, "obj")
        if e.rep is not None:
            walk(e.rep, e.elem_id, "rep")

    family_ids = {i for i, e in by_id.items() if e.class_name == "Family"}

    def is_registry(src: int, path: str) -> bool:
        np = _norm(path)
        if np.startswith("hdr.m_parents."):
            return True
        if src in family_ids and np.startswith("obj."):
            if np.split(".")[1].split("[")[0] in FAMILY_REG_KEYS:
                return True
        if by_id[src].class_name == "VarSketch" and np.startswith("obj."):
            if np.split(".")[1].split("[")[0] in SKETCH_REG_KEYS:
                return True
        return False

    hard_out: Dict[int, Set[int]] = collections.defaultdict(set)
    for s, p, t in edges:
        if not is_registry(s, p):
            hard_out[s].add(t)
    own = {e.elem_id: e.owner_id for e in els if (e.owner_id or 0) > 0}
    return {"elements": els, "by_id": by_id, "edges": edges,
            "hard_out": hard_out, "own": own, "adoc_value": adoc_value,
            "family_ids": family_ids}


# ===========================================================================
# the classification (donor extras -> seven class-groups)
# ===========================================================================

def classify(graph: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The full partition of the donor's 411 non-frame elements into the
    seven class-groups + the roster-equivalence map.  Structural + pinned;
    raises on any drift from the measured shape."""
    FB = _fb()
    FF = _ff()
    g = graph or donor_graph()
    by_id, own = g["by_id"], g["own"]
    els = g["elements"]
    dfr = FF.donor_frame(els)
    frame = set(dfr["roles"].values())

    nested_fams = [e for e in els if e.class_name == "Family"
                   and e.elem_id not in frame]
    if len(nested_fams) != 1:
        raise RuntimeError(f"expected exactly 1 nested Family, got "
                           f"{[e.elem_id for e in nested_fams]}")
    nf = nested_fams[0]
    fi = ((nf.obj.get("m_familyIds") or {}).get("value") or {}).get("m_data") or []
    nested_members = sorted(int(d["m_elementId"]) for d in fi)
    surrogates = sorted(e.elem_id for e in els if e.class_name in
                        ("FamilySurrogate", "FamSymSurrogate", "FamilySymbol"))
    s6 = set(nested_members) | {nf.elem_id} | set(surrogates)

    def root_attr(i: int) -> Optional[int]:
        j = i
        while j in own and by_id[own[j]].class_name in ("CategoryElem",
                                                        "GStyleElem"):
            j = own[j]
        return own.get(j)

    grp: Dict[int, str] = {}
    for e in sorted(els, key=lambda e: e.elem_id):
        i, c = e.elem_id, e.class_name
        if i in frame:
            grp[i] = "FRAME"
            continue
        if i in s6:
            grp[i] = "S6"
            continue
        if c == "SketchPlane":
            if (e.obj.get("m_ownerDBViewId") or -1) > 0 or \
                    (e.header.get("m_ownerViewId") or -1) > 0:
                grp[i] = "S4"                       # a view's sketch plane
            elif (e.obj.get("m_userId") or -1) > 0:
                grp[i] = "S1"                       # a sketch's plane
            else:
                grp[i] = "S3"                       # datum-hosted plane
            continue
        if c in ("CategoryElem", "GStyleElem", "FontElem"):
            ra = root_attr(i)
            if ra is not None and ra not in frame and ra not in s6:
                rc = by_id[ra].class_name
                tgt = next((k for k, v in CLASS_GROUP.items() if rc in v), "S5")
                grp[i] = tgt
            else:
                grp[i] = "S5"
            continue
        tgt = next((k for k, v in CLASS_GROUP.items() if c in v), None)
        if tgt is None:
            raise RuntimeError(f"unclassified donor element {i} {c}")
        grp[i] = tgt

    sizes = collections.Counter(v for v in grp.values() if v != "FRAME")
    if dict(sizes) != EXPECT_SIZES:
        raise RuntimeError(f"partition drifted: {dict(sorted(sizes.items()))} "
                           f"!= {EXPECT_SIZES}")
    if sum(sizes.values()) + len(frame) != len(els):
        raise RuntimeError("partition does not cover the donor")

    # S5 halves by constellation root
    def s5_root(i: int) -> int:
        j = i
        while j in own and by_id[j].class_name in ("CategoryElem",
                                                   "GStyleElem", "FontElem"):
            j = own[j]
        return j

    s5 = {i for i, k in grp.items() if k == "S5"}
    s5a = {i for i in s5 if by_id[s5_root(i)].class_name in S5A_ROOTS}
    s5b = s5 - s5a

    # roster equivalence: the donor elements playing OUR 41 roles (recorded
    # classification metadata; the groups still partition ALL non-frame
    # elements -- U16 carries OUR copy of every roster class, so deleting
    # the donor's copy never removes the machinery from the document)
    ext_sketch = next(e.elem_id for e in els if e.class_name == "VarSketch"
                      and e.owner_id == FB.DONOR_EXTRUSION)
    curves = sorted(e.elem_id for e in els if e.class_name == "CurveElem"
                    and e.owner_id == ext_sketch)
    sketch_plane = next(e.elem_id for e in els if e.class_name == "SketchPlane"
                        and (e.obj.get("m_userId") or -1) == ext_sketch)
    plan = by_id[FB.DONOR_PLAN_VIEW]
    plan_viewer = next(e.elem_id for e in els if e.class_name == "Viewer"
                       and e.owner_id == plan.elem_id)
    plan_drawing = next(e.elem_id for e in els if e.class_name == "DBDrawing"
                        and e.owner_id == plan.elem_id)
    plan_viewport = next(e.elem_id for e in els if e.class_name == "Viewport"
                         and e.owner_id == plan_drawing)
    plan_type = plan.obj.get("m_dbViewTypeId")
    plan_extent = next(t for t in g["hard_out"][plan.elem_id]
                       if by_id[t].class_name == "ExtentElem")
    plan_sketchplane = next(e.elem_id for e in els
                            if e.class_name == "SketchPlane"
                            and (e.obj.get("m_ownerDBViewId") or -1) == plan.elem_id)
    sun = next(e.elem_id for e in els
               if e.class_name == "SunAndShadowSettings")
    sf_params = sorted(e.elem_id for e in els
                       if e.class_name == "ParamElemFamily"
                       and e.elem_id not in s6)
    # our 2 origin ref planes' equivalents: the planes the extrusion sketch's
    # alignments witness (the column's center planes)
    align_targets: Set[int] = set()
    for e in els:
        if e.class_name == "Alignment" and e.owner_id == ext_sketch:
            for t in g["hard_out"].get(e.elem_id, ()):
                if by_id[t].class_name == "RefPlane":
                    align_targets.add(t)
    equivalence = {
        "frame (6)": sorted(frame),
        "level": FB.DONOR_LEVEL, "level_attributes": 1410873,
        "plan_view": FB.DONOR_PLAN_VIEW, "plan_viewer": plan_viewer,
        "plan_drawing": plan_drawing, "plan_viewport": plan_viewport,
        "plan_view_type": plan_type, "plan_extent": plan_extent,
        "plan_sketch_plane": plan_sketchplane, "sun": sun,
        "extrusion": FB.DONOR_EXTRUSION, "sketch": ext_sketch,
        "curves": curves, "sketch_plane": sketch_plane,
        "sketch_alignment_ref_planes": sorted(align_targets),
        "sketch_alignment_note": "the donor sketch's alignments witness "
                                 "FOUR ref planes (one per column face); "
                                 "our famgen authors TWO origin planes -- "
                                 "the equivalence is partial by design",
        "sf_params": sf_params,
        "connector_layer": "NO donor equivalent (structural column)",
    }

    class_map: Dict[str, Dict[str, int]] = collections.defaultdict(dict)
    for i, k in grp.items():
        c = by_id[i].class_name
        class_map[c][k] = class_map[c].get(k, 0) + 1

    return {"graph": g, "frame": frame, "groups": grp,
            "group_ids": {k: sorted(i for i, v in grp.items() if v == k)
                          for k in GROUPS},
            "s5a": sorted(s5a), "s5b": sorted(s5b),
            "nested_family": nf.elem_id, "nested_members": nested_members,
            "sizes": dict(sorted(sizes.items())),
            "class_to_group": {c: dict(sorted(m.items()))
                               for c, m in sorted(class_map.items())},
            "equivalence": equivalence}


# ===========================================================================
# the cascade closure (the deletion law's referrer handling)
# ===========================================================================

def cascade_closure(seed: Set[int], cls_out: Dict[str, Any]
                    ) -> Tuple[Set[int], List[int], List[int]]:
    """Close ``seed`` under the deletion law: children cascade with owners,
    hard (non-registry) referrers cascade with their targets.  A frame
    element that would cascade REFUSES the group -- except the measured
    LevelAttributes -> nested-FamilySymbol binding, which is DETACHED
    (m_familyTagId -> -1, our famgen's own form) instead.  Returns
    (closure, detached_ids, refusals)."""
    g = cls_out["graph"]
    by_id, own, hard_out = g["by_id"], g["own"], g["hard_out"]
    frame = cls_out["frame"]
    all_ids = set(by_id)
    S = set(seed)
    detached: List[int] = []
    refused: List[int] = []
    changed = True
    while changed:
        changed = False
        for i in sorted(all_ids - S):
            pulls_own = own.get(i) in S
            pulled_refs = {t for t in hard_out.get(i, ()) if t in S}
            if not pulls_own and not pulled_refs:
                continue
            if (by_id[i].class_name == "LevelAttributes" and not pulls_own
                    and all(by_id[t].class_name == "FamilySymbol"
                            for t in pulled_refs)):
                if i not in detached:
                    detached.append(i)
                continue
            if i in frame:
                refused.append(i)
                continue
            S.add(i)
            changed = True
    return S, detached, refused


def deletion_sets(cls_out: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Per-probe deletion closures in ORIGINAL donor id space, with the
    cascade/detach/refusal record and the measured pull census."""
    out: Dict[str, Dict[str, Any]] = {}
    seeds = {f"SUB_{k}": set(cls_out["group_ids"][k]) for k in GROUPS}
    seeds["SUB_ALL"] = set().union(*(set(cls_out["group_ids"][k])
                                     for k in GROUPS))
    seeds["SUB_S5A"] = set(cls_out["s5a"])
    seeds["SUB_S5B"] = set(cls_out["s5b"])
    by_id = cls_out["graph"]["by_id"]
    grp = cls_out["groups"]
    for name, seed in seeds.items():
        S, detached, refused = cascade_closure(seed, cls_out)
        if refused:
            raise RuntimeError(f"{name}: frame elements would cascade -- "
                               f"undeletable-alone: {refused}")
        pulled = sorted(S - seed)
        census = collections.Counter(
            f"{grp[i]}:{by_id[i].class_name}" for i in pulled)
        out[name] = {"seed": sorted(seed), "closure": sorted(S),
                     "detached": detached,
                     "pulled": pulled,
                     "pull_census": dict(sorted(census.items())),
                     "n_seed": len(seed), "n_closure": len(S)}
    expect_single = {f"SUB_{k}": EXPECT_SIZES[k] + EXPECT_PULLS[k]
                     for k in GROUPS}
    for name, want in expect_single.items():
        got = out[name]["n_closure"]
        if got != want:
            raise RuntimeError(f"{name}: closure {got} != measured {want}")
    if out["SUB_ALL"]["n_closure"] != sum(EXPECT_SIZES.values()):
        raise RuntimeError("SUB_ALL closure != the full non-frame partition")
    return out


# ===========================================================================
# the deletion itself (scrub registry surfaces, refuse residuals)
# ===========================================================================

def _prune_int_list(lst: List[Any], del_set: Set[int]) -> int:
    """Remove ints in del_set from a flat list IN PLACE; count removed."""
    keep = [x for x in lst if not (isinstance(x, int)
                                   and not isinstance(x, bool)
                                   and x in del_set)]
    n = len(lst) - len(keep)
    lst[:] = keep
    return n


def _contains_id(node: Any, del_set: Set[int]) -> bool:
    if isinstance(node, bool):
        return False
    if isinstance(node, int):
        return node in del_set
    if isinstance(node, dict):
        return any(_contains_id(v, del_set) for v in node.values())
    if isinstance(node, list):
        return any(_contains_id(v, del_set) for v in node)
    return False


def _prune_entry_lists(node: Any, del_set: Set[int], census: Dict[str, int],
                       path: str) -> None:
    """Generic registry prune: inside ``node``, drop LIST ENTRIES that
    reference a deleted id anywhere (deregistration row drop).  Applied ONLY
    to designated registry surfaces."""
    if isinstance(node, dict):
        for k, v in node.items():
            _prune_entry_lists(v, del_set, census, f"{path}.{k}")
    elif isinstance(node, list):
        keep = []
        for v in node:
            if _contains_id(v, del_set):
                census[_norm(path) + "[]"] = census.get(_norm(path) + "[]", 0) + 1
            else:
                keep.append(v)
        node[:] = keep
        for j, v in enumerate(node):
            _prune_entry_lists(v, del_set, census, f"{path}[{j}]")


def delete_from_union(doc, del_hybrid: Set[int],
                      detach_hybrid: Set[int]) -> Dict[str, Any]:
    """Delete ``del_hybrid`` from the union document under the FAMDOC
    DELETION LAW: elements removed; every survivor's registry surfaces
    scrubbed (any Family's membership registries, header parent lists, a
    VarSketch's dim registries); the measured detach normalization applied;
    then a build-refusing residual scan proves NO survivor node carries a
    deleted id.  Returns the per-surface scrub census."""
    census: Dict[str, int] = {}
    report: Dict[str, Any] = {"n_deleted": len(del_hybrid),
                              "detached": sorted(detach_hybrid),
                              "detach_law": DETACH_LAW}
    survivors = [e for e in doc.elements if e.elem_id not in del_hybrid]
    if len(survivors) + len(del_hybrid) != len(doc.elements):
        raise RuntimeError("deletion set contains non-members")
    deleted_classes = collections.Counter(
        e.class_name for e in doc.elements if e.elem_id in del_hybrid)
    report["deleted_class_census"] = dict(sorted(deleted_classes.items()))

    for e in survivors:
        # ownership law: a survivor's owner must survive
        if (e.owner_id or 0) > 0 and e.owner_id in del_hybrid:
            raise RuntimeError(f"survivor {e.elem_id} owned by deleted "
                               f"{e.owner_id} -- ownership cascade broken")
        # header parent lists
        par = ((e.header.get("m_parents") or {}).get("value") or {})
        for k in PARENT_LISTS:
            if isinstance(par.get(k), list):
                n = _prune_int_list(par[k], del_hybrid)
                if n:
                    census[f"hdr.m_parents.{k}"] = \
                        census.get(f"hdr.m_parents.{k}", 0) + n
        if e.class_name == "Family":
            o = e.obj
            fi = ((o.get("m_familyIds") or {}).get("value") or {})
            rows = fi.get("m_data")
            if isinstance(rows, list):
                keep = [r for r in rows
                        if int(r.get("m_elementId", -1)) not in del_hybrid]
                census["Family.m_familyIds"] = census.get(
                    "Family.m_familyIds", 0) + len(rows) - len(keep)
                fi["m_data"] = keep
            fp = ((o.get("m_familyParams") or {}).get("value") or {})
            rows = fp.get("m_params")
            if isinstance(rows, list):
                keep = [r for r in rows
                        if not (isinstance(r.get("m_paramId"), int)
                                and r["m_paramId"] in del_hybrid)]
                census["Family.m_familyParams"] = census.get(
                    "Family.m_familyParams", 0) + len(rows) - len(keep)
                fp["m_params"] = keep
            ftt = ((o.get("m_pFamilyTypes") or {}).get("value") or {})
            for pr in ftt.get("m_pairs") or []:
                pv = (pr.get("params") or {})
                rows = pv.get("m_params")
                if isinstance(rows, list):
                    keep = [r for r in rows
                            if not (isinstance(r.get("m_paramId"), int)
                                    and r["m_paramId"] in del_hybrid)]
                    census["Family.m_pFamilyTypes.rows"] = census.get(
                        "Family.m_pFamilyTypes.rows", 0) + len(rows) - len(keep)
                    pv["m_params"] = keep
            lk = o.get("m_lockedParameterIdsForDirectManipulation")
            if isinstance(lk, list):
                n = _prune_int_list(lk, del_hybrid)
                if n:
                    census["Family.m_locked"] = census.get("Family.m_locked", 0) + n
            cells = ((o.get("m_cellList") or {}).get("value") or {}).get(
                "m_cells") or []
            for c in cells:
                cv = (c.get("value") or {}) if isinstance(c, dict) else {}
                for gph in cv.get("m_sortedParams") or []:
                    if isinstance(gph, dict) and isinstance(
                            gph.get("m_paramIds"), list):
                        n = _prune_int_list(gph["m_paramIds"], del_hybrid)
                        if n:
                            census["Family.m_cellList.paramIds"] = census.get(
                                "Family.m_cellList.paramIds", 0) + n
            de = o.get("m_deletableElements")
            if isinstance(de, list):
                n = _prune_int_list(de, del_hybrid)
                if n:
                    census["Family.m_deletableElements"] = census.get(
                        "Family.m_deletableElements", 0) + n
                _prune_entry_lists(de, del_hybrid, census,
                                   "Family.m_deletableElements")
            for k in ("m_oFamDimConstrMgr", "m_refs", "m_fsdos"):
                if k in o and o[k] is not None:
                    _prune_entry_lists(o[k], del_hybrid, census, f"Family.{k}")
        if e.class_name == "VarSketch":
            for k in SKETCH_REG_KEYS:
                v = e.obj.get(k)
                if isinstance(v, list):
                    n = _prune_int_list(v, del_hybrid)
                    if n:
                        census[f"VarSketch.{k}"] = census.get(
                            f"VarSketch.{k}", 0) + n
                    _prune_entry_lists(v, del_hybrid, census, f"VarSketch.{k}")
        # the detach normalization (our famgen's own certified form)
        if e.elem_id in detach_hybrid:
            if e.class_name != "LevelAttributes":
                raise RuntimeError(f"detach target {e.elem_id} is "
                                   f"{e.class_name}, not LevelAttributes")
            was = e.obj.get("m_familyTagId")
            e.obj["m_familyTagId"] = -1
            report["detach_applied"] = {"elem": e.elem_id,
                                        "m_familyTagId_was": was,
                                        "now": -1}

    # THE RESIDUAL SCAN (build-refusing): no survivor node carries a deleted id
    residual: List[Tuple[str, int]] = []

    def scan(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in del_hybrid:
                    residual.append((path + "." + k, v))
                else:
                    scan(v, path + "." + k)
        elif isinstance(node, list):
            for j, v in enumerate(node):
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in del_hybrid:
                    residual.append((f"{path}[{j}]", v))
                else:
                    scan(v, f"{path}[{j}]")

    for e in survivors:
        scan(e.header, f"{e.elem_id}.hdr")
        scan(e.obj, f"{e.elem_id}.obj")
        if e.rep is not None:
            scan(e.rep, f"{e.elem_id}.rep")
    if residual:
        raise RuntimeError(f"deletion leaves {len(residual)} residual "
                           f"reference(s) on survivors: {residual[:8]}")
    report["survivor_residual_refs"] = 0
    report["scrub_census"] = dict(sorted(census.items()))
    doc.elements = sorted(survivors, key=lambda e: e.elem_id)
    report["n_survivors"] = len(survivors)
    return report


# ===========================================================================
# the inline-ADocument treatment (rows dropped + carried appended + census)
# ===========================================================================

def swap_inline_adoc_subtractive(path_in: str, path_out: str, *, guid: str,
                                 adoc_value: dict, idmap: Dict[int, int],
                                 self_family_new: int,
                                 carried_elements: Sequence[Any],
                                 deleted_hybrid: Set[int]) -> Dict[str, Any]:
    """famdoc_final.swap_inline_adoc_union's proven U16 recipe EXTENDED for
    deletion: the donor inline ADocument is remapped, history GUIDs re-keyed
    fresh, the carried roster's ElemTable rows appended, IdentifierSource
    raised -- and the DELETED elements' ElemTable rows DROPPED.  Deep
    registries (AppInfoManager) keep their entries; every remaining
    reference to a deleted id is CENSUSED per top-level key (the genesis
    deletion precedent: dangling tolerated, never nulled)."""
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
        gv = (hist.get(k) or {}).get("m_guid")
        if gv is not None:
            guid_fields[k] = str(gv)
            hist[k] = {"m_guid": fresh_identity}

    inner = ((value.get("m_elemTable") or {}).get("value") or {})
    arr = inner.get("m_elemArr")
    if not isinstance(arr, list) or not arr:
        raise RuntimeError("donor inline ADocument has no ElemTable rows")
    n_rows_before = len(arr)
    kept_rows = [r for r in arr if int(r.get("m_id", -1)) not in deleted_hybrid]
    n_dropped = n_rows_before - len(kept_rows)
    for r in kept_rows:                      # kept rows' owners must survive
        ow = int(r.get("m_OwningElementId", -1))
        if ow in deleted_hybrid:
            raise RuntimeError(f"ElemTable row {r.get('m_id')} owned by "
                               f"deleted {ow}")
    arr[:] = kept_rows
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

    # dangling census over the rest of the ADocument (registries untouched)
    dangling: Dict[str, int] = {}

    def cens(node, topkey):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in deleted_hybrid:
                    dangling[topkey] = dangling.get(topkey, 0) + 1
                else:
                    cens(v, topkey)
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in deleted_hybrid:
                    dangling[topkey] = dangling.get(topkey, 0) + 1
                else:
                    cens(v, topkey)

    for k, v in value.items():
        if k == "m_elemTable":
            continue
        cens(v, k)

    payload = A.encode_latest(value, trailer=b"")
    back = A.decode_latest(payload)
    if not back.clean:
        raise RuntimeError("remapped+reduced donor inline ADocument does not "
                           "re-decode clean")
    with open_rvt(path_in) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    entries, tail = F.parse_content_documents(cd)
    if not any(gk == guid for gk, _a in entries):
        raise RuntimeError(f"no ContentDocuments entry for {guid}")
    swapped = [(gk, (payload if gk == guid else a)) for gk, a in entries]
    new_cd = F.assemble_content_documents(swapped, tail=tail or F.CD_END_RECORD)
    stream = ecc.frame_stream(wrap_global_stream("Global/ContentDocuments",
                                                 new_cd, level=3))
    ents = read_entries(path_in)
    out_entries = [dataclasses.replace(e, data=stream)
                   if (e.entry_type == "stream"
                       and e.path == "Global/ContentDocuments")
                   else e for e in ents]
    write_cfb(path_out, out_entries)
    return {"swapped_guid": guid, "adoc_bytes": len(payload),
            "elem_rows_before": n_rows_before,
            "elem_rows_dropped": n_dropped,
            "elem_rows_appended": appended,
            "elem_rows_total": len(arr),
            "identifier_source_last": {"before": m_last_before,
                                       "after": src.get("m_last")},
            "history_identity_fresh": fresh_identity,
            "history_guids_rekeyed_from": guid_fields,
            "registry_dangling_census": dict(sorted(dangling.items())),
            "registry_dangling_total": sum(dangling.values()),
            "registry_law": "deep ADocument registries keep their entries "
                            "(genesis deletion precedent: dangling "
                            "tolerated, censused; ONLY ElemTable rows are "
                            "roster-reconciled)"}


# ===========================================================================
# deletion probes (the U16 recipe + the lawful deletion)
# ===========================================================================

def build_deletion_probe(name: str, cls_out: Dict[str, Any],
                         dels: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    FB = _fb()
    FF = _ff()
    T = _room()
    wm = T.host_watermark(RST)
    info: Dict[str, Any] = {"probe": name, "axis": AXES[name],
                            "base": relp(RST)}
    pdir = os.path.join(BUILD_DIR, name)
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, f"{name}.rvt")

    doc, hrep, carried, dctx = FF.make_union_doc("U16", wm)
    idmap = dctx["idmap"]
    n_before = len(doc.elements)
    d = dels[name]
    del_h = {idmap[i] for i in d["closure"]}
    detach_h = {idmap[i] for i in d["detached"]}
    drep = delete_from_union(doc, del_h, detach_h)
    drep["closure_original_ids"] = d["closure"]
    drep["seed_original_ids"] = d["seed"]
    drep["pull_census"] = d["pull_census"]
    jdump(os.path.join(pdir, "deletion_report.json"), drep)
    info["deletion"] = {"n_elements_before": n_before,
                        "n_deleted": len(del_h),
                        "n_elements_after": len(doc.elements),
                        "n_seed": d["n_seed"],
                        "n_cascade_pulled": len(d["pulled"]),
                        "pull_census": d["pull_census"],
                        "detached": d["detached"],
                        "scrub_census": drep["scrub_census"],
                        "survivor_residual_refs": 0}
    if len(doc.elements) != n_before - len(del_h):
        raise RuntimeError(f"{name}: element count drifted")
    # classes ZEROED document-wide (present in U16, absent after deletion --
    # the candidate requirement space this probe reads on)
    kept_classes = {e.class_name for e in doc.elements}
    del_classes = set(drep["deleted_class_census"])
    info["classes_zeroed_documentwide"] = sorted(del_classes - kept_classes)
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)

    rfa = os.path.join(pdir, f"{name}_famdoc.rfa")
    info["dev_rfa"] = FB.emit_dev_rfa(doc, rfa)

    src = os.path.join(pdir, f"{name}_load.rvt")
    info["load"] = FB.famload_doc(doc, src, name)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam

    swapped = os.path.join(pdir, f"{name}_load_adoc.rvt")
    info["adoc_swap"] = swap_inline_adoc_subtractive(
        src, swapped, guid=doc.document_guid,
        adoc_value=dctx["adoc_value"], idmap=idmap,
        self_family_new=dctx["anchors"]["self_family"],
        carried_elements=carried, deleted_hybrid=del_h)
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
# SUB_O1: the order probe (donor class-ordering convention, B0 recipe)
# ===========================================================================

#: the donor's ordering convention, projected onto OUR roster (measured
#: donor ids of the role-equivalents; our unmatched electrical layer last)
O1_ROLE_RANK = {
    "self_family": 1410872, "level_type": 1410873, "ref_level": 1410875,
    "plan_viewer": 1410876, "plan_view": 1410877, "plan_drawing": 1410878,
    "plan_viewport": 1410879, "ref_plane": 1410901,      # both origin planes
    "proj_viewer": 1410912, "proj_view": 1410913, "proj_drawing": 1410914,
    "proj_viewport": 1410915, "sketch": 1410971, "extrusion": 1410972,
    "curve": 1410973, "sketch_plane": 1410981, "extent": 1411001,
    "units": 1411008, "family_param": 1411115, "view_type": 1411162,
    "sun": 1411204, "view_sketch_plane": 1411228,
    "load_class": 9_000_000, "connector": 9_000_001,
}


def _o1_role_of(e, doc) -> str:
    """Map one of OUR famdoc elements to its donor-convention role."""
    c, k = e.class_name, e.kind
    proj = next(x for x in doc.elements if x.class_name == "DBViewProject")
    proj_owned = {x.elem_id: x for x in doc.elements
                  if x.owner_id == proj.elem_id}
    proj_drawing = next(x for x in proj_owned.values()
                        if x.class_name == "DBDrawing")
    if c == "Family":
        return "self_family"
    if c == "UnitsElem":
        return "units"
    if c == "LevelAttributes":
        return "level_type"
    if c == "Level":
        return "ref_level"
    if c == "DBViewProject":
        return "proj_view"
    if c == "DBViewPlan":
        return "plan_view"
    if c == "DBViewType":
        return "view_type"
    if c == "SunAndShadowSettings":
        return "sun"
    if c == "ExtentElem":
        return "extent"
    if c == "RefPlane":
        return "ref_plane"
    if c == "ParamElemFamily":
        return "family_param"
    if c == "VarSketch":
        return "sketch"
    if c == "ExtrusionElem":
        return "extrusion"
    if c == "CurveElem":
        return "curve"
    if c == "ElectricalLoadClassification":
        return "load_class"
    if c == "ConnectorElem":
        return "connector"
    if c == "SketchPlane":
        return "sketch_plane" if k == "sketch_plane" else "view_sketch_plane"
    if c in ("Viewer", "DBDrawing", "Viewport"):
        side = "proj" if (e.owner_id == proj.elem_id
                          or e.owner_id == proj_drawing.elem_id) else "plan"
        kindmap = {"Viewer": "viewer", "DBDrawing": "drawing",
                   "Viewport": "viewport"}
        return f"{side}_{kindmap[c]}"
    raise RuntimeError(f"O1: unmapped element {e.elem_id} {c} kind={k}")


def permute_doc_to_donor_order(doc) -> Dict[str, Any]:
    """Renumber OUR famdoc's element ids (a pure bijection over the SAME id
    block) so ascending-id order follows the donor's class-ordering
    convention.  Semantics-preserving: every id occurrence is remapped
    through the famgen loader's own conservative int-walk."""
    from rvt.famgen.loader import _walk_replace_ids
    els = list(doc.elements)
    ranked = sorted(els, key=lambda e: (O1_ROLE_RANK[_o1_role_of(e, doc)],
                                        e.elem_id))
    ordered_ids = sorted(e.elem_id for e in els)
    perm = {e.elem_id: ordered_ids[i] for i, e in enumerate(ranked)}
    if sorted(perm) != sorted(perm.values()):
        raise RuntimeError("O1 permutation is not a bijection on the id block")
    moved = sum(1 for a, b in perm.items() if a != b)
    order_before = [(e.elem_id, e.class_name)
                    for e in sorted(els, key=lambda e: e.elem_id)]
    for e in els:
        _walk_replace_ids(e.header, perm)
        _walk_replace_ids(e.obj, perm)
        if e.rep is not None:
            _walk_replace_ids(e.rep, perm)
        if (e.owner_id or 0) > 0:
            e.owner_id = perm.get(e.owner_id, e.owner_id)
        e.elem_id = perm[e.elem_id]
    doc.elements.sort(key=lambda e: e.elem_id)
    if hasattr(doc, "plan_view_id") and doc.plan_view_id in perm:
        doc.plan_view_id = perm[doc.plan_view_id]
    order_after = [(e.elem_id, e.class_name) for e in doc.elements]
    return {"n_elements": len(els), "n_moved": moved,
            "permutation": {str(k): v for k, v in sorted(perm.items())},
            "class_order_before": [c for _i, c in order_before],
            "class_order_after": [c for _i, c in order_after],
            "role_rank": {k: v for k, v in sorted(O1_ROLE_RANK.items(),
                                                  key=lambda kv: kv[1])}}


def build_o1() -> Dict[str, Any]:
    """SUB_O1: the exact B0 recipe (famgen loader chain on G_ABPD under
    corpus_symbol_form + the demo's own stage_equipment placement) with the
    ORDER permutation injected between build_product and the load -- the
    same injection point as famdoc_final's F-probes."""
    B = _bisect()
    T = _room()
    FF = _ff()
    from rvt import famload_hostfix as HF
    from rvt.famgen import loader as L
    info: Dict[str, Any] = {"probe": "SUB_O1", "axis": AXES["SUB_O1"],
                            "base": relp(G_ABPD),
                            "recipe": "BXhf_f1i1/B0 (famgen loader on G_ABPD "
                                      "under corpus_symbol_form, demo "
                                      "stage_equipment placement) with the "
                                      "donor-convention ID PERMUTATION "
                                      "injected between build_product and "
                                      "the load"}
    chain_dir = os.path.join(BUILD_DIR, "SUB_O1_chain")
    if os.path.isdir(chain_dir):
        shutil.rmtree(chain_dir)
    os.makedirs(chain_dir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "SUB_O1.rvt")
    with HF.corpus_symbol_form():
        model6 = B.demo_model()
        m1 = B.truncate_model(model6, 1)
        current = os.path.join(chain_dir, "stage_L0_base.rvt")
        shutil.copyfile(G_ABPD, current)
        wm = T.host_watermark(current)
        prod = T.build_product(m1.plan_for("PP-1"), start_id=wm + 1, solid=True)
        if not prod.doc.finalized:
            prod.doc.finalize()
        prep = permute_doc_to_donor_order(prod.doc)
        jdump(os.path.join(BUILD_DIR, "SUB_O1_permutation.json"), prep)
        info["permutation"] = {k: prep[k] for k in
                               ("n_elements", "n_moved", "class_order_before",
                                "class_order_after")}
        info["reference_resolution"] = FF.famdoc_reference_resolution(
            prod.doc, G_ABPD)
        nxt = os.path.join(chain_dir, "stage_L1_pp1.rvt")
        res = L.load_family_into_project(current, nxt, product=prod,
                                         place=False, symbol_solid=True,
                                         report_path=nxt + ".load.json",
                                         validate=False)
        if not res.ok:
            raise RuntimeError(f"SUB_O1: famgen load failed: {res.stop_reason}")
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
    FF._b0_style_gates(outp, info)                             # noqa: SLF001
    return info


# ===========================================================================
# accounting + gates (famdoc_final's law, subtractive naming)
# ===========================================================================

def base_of(name: str) -> str:
    return G_ABPD if name == "SUB_O1" else RST


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
    if name == "SUB_O1":
        unresolved = (info.get("reference_resolution")
                      or {}).get("unresolved_anywhere")
    else:
        unresolved = (((info.get("dev_rfa") or {}).get("reference_resolution")
                       or {}).get("unresolved_anywhere"))
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
    if name != "SUB_O1":
        g["deletion_survivor_residual_refs"] = (
            (info.get("deletion") or {}).get("survivor_residual_refs"))
    else:
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
    if name != "SUB_O1":
        ok = ok and g.get("deletion_survivor_residual_refs") == 0
    else:
        ok = ok and g.get("symbol_form_ok") is True
    g["gates_ok"] = bool(ok)
    return g


# ===========================================================================
# build driver
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    FB = _fb()
    FB._install_schema()                                       # noqa: SLF001
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    cls_out = classify()
    dels = deletion_sets(cls_out)
    write_classification(cls_out, dels)
    out: Dict[str, Any] = {"tool": "tools/subtractive.py",
                           "bases": {"deletion_probes": relp(RST),
                                     "SUB_O1": relp(G_ABPD)},
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
            if name == "SUB_O1":
                info = build_o1()
            else:
                info = build_deletion_probe(name, cls_out, dels)
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
    write_probes_json(out, cls_out, dels)
    return out


# ===========================================================================
# classification.json (the class->group map, the record's centerpiece)
# ===========================================================================

def write_classification(cls_out: Dict[str, Any],
                         dels: Dict[str, Dict[str, Any]]) -> str:
    by_id = cls_out["graph"]["by_id"]
    groups_detail = {}
    for k in GROUPS:
        ids = cls_out["group_ids"][k]
        cen = collections.Counter(by_id[i].class_name for i in ids)
        groups_detail[k] = {"n": len(ids),
                            "classes": dict(sorted(cen.items())),
                            "ids": ids}
    payload = {
        "donor": "M_Concrete-Square-Column (rst unit 36, 417 elements)",
        "law": "FRAME (6: self-Family + UnitsElem + project-view chain) is "
               "the only kept donor floor -- measured hard-self-contained.  "
               "Every other donor element (411) partitions into the seven "
               "groups.  Roster equivalence (the donor elements playing OUR "
               "41 famdoc roles) is recorded below as metadata: those "
               "elements ride in their natural groups, and U16 carries OUR "
               "copy of every roster class, so no deletion ever removes a "
               "roster class from the document -- a FAIL convicts "
               "donor-only infrastructure.",
        "sizes": cls_out["sizes"],
        "class_to_group": cls_out["class_to_group"],
        "groups": groups_detail,
        "s5_halves": {"S5A_dim_flavored": cls_out["s5a"],
                      "S5B_text_region_flavored": cls_out["s5b"]},
        "nested_family": {"family": cls_out["nested_family"],
                          "n_registered_members": len(cls_out["nested_members"])},
        "roster_equivalence": cls_out["equivalence"],
        "deletion_closures": {n: {k: v for k, v in d.items()
                                  if k != "closure" and k != "seed"}
                              for n, d in dels.items()},
        "detach_law": DETACH_LAW,
    }
    path = os.path.join(OUT_DIR, "classification.json")
    jdump(path, payload)
    log(f"classification.json -> {relp(path)}")
    return path


# ===========================================================================
# probes.json (the decision table)
# ===========================================================================

READING = {
    "CTRL FAIL (either)": "round VOID for that base's probes (the rst "
                          "control voids the SUB_ deletion probes; the "
                          "G_ABPD control voids SUB_O1).",
    "the bracket": "U16 (batch 45, certified PASS) is the top of this "
                   "ladder -- every SUB_ probe is U16 minus one lawful "
                   "deletion; SUB_ALL (the donor reduced to our lean 41 "
                   "shape) is the bottom, expected FAIL (B0/H8B/F1 all "
                   "fail with lean rosters).",
    "SUB_Sx FAIL (single)": "THE FLIP: that group's infrastructure is "
                            "REQUIRED by the audit.  The document retains "
                            "OUR copy of every roster class (35 carried "
                            "elements) plus the donor frame, so the "
                            "conviction names donor-only furniture -- read "
                            "'classes_zeroed_documentwide' in the probe's "
                            "accounting entry for the exact candidate "
                            "classes.  NEXT round bisects INSIDE the "
                            "convicted group (for S5 the halves SUB_S5A / "
                            "SUB_S5B are already in this batch).",
    "SUB_Sx PASS (single)": "that group alone is NOT required: U16 stays "
                            "lawful without it.",
    "ALL singles PASS + SUB_ALL FAIL": "no single group is required alone "
                            "=> the requirement is a UNION of groups (or "
                            "a whole-document property the deletions "
                            "share).  Next round: cumulative deletions in "
                            "reading order (S5+S6, +S4, ...) -- mechanical.",
    "ALL singles FAIL": "suspect the SHARED DELETION MECHANICS first (every "
                        "probe leaves the donor inline-ADocument's deep "
                        "registries dangling over the deleted ids -- the "
                        "genesis-deletion precedent tolerated this at "
                        "PROJECT level, unproven at famdoc level).  Rebuild "
                        "ONE single with a fully scrubbed ADocument before "
                        "reading convictions.",
    "SUB_ALL PASS": "INVERSION AGAIN: the lean shape is lawful when reached "
                    "by deletion from the donor -- the defect would then be "
                    "in HOW our famdoc AUTHORS the same shape (field-level "
                    "grammar, not element roster).  Diff SUB_ALL's famdoc "
                    "against B0's element-by-element; the delta is the fix "
                    "spec.",
    "SUB_S5A/S5B (read on SUB_S5 FAIL)": "the pre-built bisection of the "
                    "top-prior group: A = dim-flavored style constellations "
                    "(DimensionStyle/LeaderStyle/SpotElevation + subtrees), "
                    "B = text/region-flavored (TextNote/TagNote/FilledRegion "
                    "attrs, Text3d, RevisionCloud, ReferenceViewer).  The "
                    "failing half carries the requirement; both-FAIL => "
                    "both constellations required (or the shared "
                    "cat/gstyle/font substrate).",
    "SUB_O1 PASS": "ELEMENT ORDER was a missing whole-document property: "
                   "our famdoc renumbered to the donor's class-ordering "
                   "convention heals B0's exact recipe.  Fix = famgen "
                   "allocation order (mechanical, no new elements).",
    "SUB_O1 FAIL": "order alone does not heal B0 -- consistent with the "
                   "missing-infrastructure reading; the deletion probes "
                   "carry the round.",
    "honest residue": "the deletion probes share one non-deletion delta vs "
                      "U16: the inline ADocument's deep registries dangle "
                      "over deleted ids (censused per probe) and SUB_S6 "
                      "carries the one detach normalization "
                      "(LevelAttributes.m_familyTagId -> -1, our famgen's "
                      "own certified form).  SUB_O1 varies ONLY the id "
                      "assignment; unit shape (record framing, blob layout) "
                      "is not varied by any probe here.",
}

EXPECTED = {
    "SUB_ALL": "FAIL (anchors the ladder at our lean shape)",
    "SUB_S5": "the top-prior flip candidate: FAIL convicts the style/"
              "category/font infrastructure",
    "SUB_S6": "FAIL convicts the nested level-head family cluster",
    "SUB_S4": "FAIL convicts the view/annotation locals",
    "SUB_S7": "FAIL convicts struct/settings residue",
    "SUB_S2": "FAIL convicts dims/constraints",
    "SUB_S1": "FAIL convicts donor sketch/geometry infra (ours remains)",
    "SUB_S3": "FAIL convicts datum/reference infra (+its view cascade)",
    "SUB_S5A": "read on SUB_S5 FAIL: is the dim-flavored half required?",
    "SUB_S5B": "read on SUB_S5 FAIL: is the text/region half required?",
    "SUB_O1": "PASS => element order was the whole-document property",
}


def write_probes_json(build_out: Dict[str, Any], cls_out: Dict[str, Any],
                      dels: Dict[str, Dict[str, Any]]) -> str:
    probes = []
    for i, name in enumerate(LADDER, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        gates = (build_out.get("gates") or {}).get(name) or {}
        bp = ((build_out.get("accounting") or {}).get(name) or {}).get(
            "blob_proof") or {}
        entry = {
            "order": i,
            "rung": name,
            "file": f"experiments/subtractive/{name}.rvt",
            "base": relp(base_of(name)),
            "kind": "probe",
            "axis": AXES[name],
            "n_families": 1, "n_instances": 1, "n_walls": 0,
            "the_ONE_thing_it_tests": AXES[name],
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
        if name != "SUB_O1":
            d = dels.get(name) or {}
            entry["deletion"] = {"n_seed": d.get("n_seed"),
                                 "n_closure": d.get("n_closure"),
                                 "pull_census": d.get("pull_census"),
                                 "detached": d.get("detached")}
            entry["classes_zeroed_documentwide"] = info.get(
                "classes_zeroed_documentwide")
        else:
            entry["permutation"] = (info.get("permutation") or {})
        probes.append(entry)
    manifest = {
        "stream": "subtractive: THE SUBTRACTIVE LADDER on U16.  Verdicts "
                  "#39: donor body + our axes = PASS (U16); our lean "
                  "famdoc in any variant = FAIL.  These probes delete the "
                  "donor's extra elements from U16 by class-group under "
                  "the famdoc deletion law; the PASS->FAIL flip names the "
                  "infrastructure the audit requires.  SUB_O1 tests the "
                  "element-order hypothesis from the other direction.",
        "bases": {"deletion_probes": relp(RST), "SUB_O1": relp(G_ABPD)},
        "classification": "experiments/subtractive/classification.json "
                          "(the full class->group map + roster equivalence "
                          "+ per-probe closures)",
        "note": "deletion probes = untouched rst sample + ONE loaded "
                "reduced-hybrid famdoc + ONE placed instance (the exact "
                "certified U16 recipe with the lawful deletion between "
                "union assembly and the load).  SUB_O1 = G_ABPD + ONE "
                "famgen family + ONE instance (the B0 recipe verbatim) "
                "with only the id assignment permuted.  EVERY probe's "
                "added unit carries the 64-byte 0x0f3f blob "
                "(machine-verified nonce).  PROOF-ONLY sample-derived "
                "content, quarantined, never shipped.  Fresh GUIDs per "
                "rebuild -- re-hash after any rerun.",
        "upload_order_max_information_first": list(LADDER),
        "controls": {
            "rst": {"source": relp(RST),
                    "voids": "every SUB_ deletion probe on CTRL FAIL"},
            "g_abpd": {"source": relp(G_ABPD),
                       "voids": "SUB_O1 on CTRL FAIL"},
        },
        "reading_the_matrix": READING,
        "companion_evidence": {
            "accounting": "experiments/subtractive/accounting.json",
            "classification": "experiments/subtractive/classification.json",
            "author_spec": "experiments/subtractive/author_spec.json",
            "per_probe_reports": "experiments/subtractive/_build/<rung>/",
            "prior_round": "experiments/famdoc_final/probes.json (batch 45)",
            "substrate": "experiments/famdoc_final/U16.rvt (certified PASS, "
                         "batch 45)",
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
    cls_out = classify()
    dels = deletion_sets(cls_out)
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
    write_probes_json(out, cls_out, dels)
    return fresh


def stage() -> Dict[str, Any]:
    """probe_batch gate + stage with TWO controls (byte-identical untouched
    rst copy for the deletion probes + a G_ABPD copy for SUB_O1)."""
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
    for req in ("classification.json", "author_spec.json"):
        if not os.path.isfile(os.path.join(OUT_DIR, req)):
            raise SystemExit(f"{req} missing -- run classify/spec first")
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
        "tool": "tools/subtractive.py (via tools/probe_batch.py primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified' (or is an Autodesk sample "
                "source); the batch carries >= 1 CONTROL = a byte-identical "
                "copy of a certified file; read the round with "
                "read_batch_verdicts(): control FAIL => every verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 2,
        "controls": {"rst": ctrl_rst.staged_as, "g_abpd": ctrl_g.staged_as,
                     "note": "the rst control gates the SUB_ deletion "
                             "probes; the G_ABPD control gates SUB_O1 -- "
                             "either control FAIL voids its probes"},
        "note": "subtractive: the SUBTRACTIVE LADDER on U16 (verdicts #39). "
                "U16 (donor body + all our axes, certified PASS) is reduced "
                "by class-group under the famdoc deletion law; the "
                "PASS->FAIL flip names the donor infrastructure the audit "
                "requires.  SUB_ALL anchors at our lean shape (expected "
                "FAIL); SUB_S5A/B pre-build the top-prior group's "
                "bisection; SUB_O1 tests element order on the B0 recipe. "
                "Read experiments/subtractive/probes.json "
                "reading_the_matrix; the classification and author spec "
                "are experiments/subtractive/classification.json + "
                "author_spec.json.",
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
# author_spec.json (what famgen would need to AUTHOR, top-2 prior groups)
# ===========================================================================

def author_spec() -> str:
    """The frame_diff-style AUTHORING spec for the top-2 prior groups (S5
    styles/categories/fonts + S6 nested annotation family): the corpus
    shape of those elements for a PANELBOARD-class family, measured from
    the structural donor (element structure) and the RME panelboard donor
    (unit 30, the same-category count reference).  Honest about unknowns."""
    FB = _fb()
    cls_out = classify()
    g = cls_out["graph"]
    by_id = g["by_id"]

    def constellation_shape(root_ids: Sequence[int]) -> List[Dict[str, Any]]:
        out = []
        for r in sorted(root_ids):
            e = by_id[r]
            kids = sorted(i for i, o in g["own"].items() if o == r)
            out.append({
                "class": e.class_name, "id": r,
                "owned_children": [{"class": by_id[k].class_name, "id": k}
                                   for k in kids],
                "hard_refs_out": sorted({by_id[t].class_name
                                         for t in g["hard_out"].get(r, ())}),
                "obj_top_keys": sorted(e.obj)[:40],
            })
        return out

    grp = cls_out["groups"]
    s5_roots = [i for i, k in grp.items()
                if k == "S5" and by_id[i].class_name not in
                ("CategoryElem", "GStyleElem", "FontElem")]
    nf = cls_out["nested_family"]

    # RME panelboard census (the same-category count reference)
    rme_note: Dict[str, Any]
    try:
        rme_els, _a, _i = FB.load_unit_elements(RME, FB.RME_PANELBOARD_UNIT)
        rme_census = collections.Counter(e.class_name for e in rme_els)
        rme_note = {"unit": FB.RME_PANELBOARD_UNIT,
                    "n_elements": len(rme_els),
                    "census": dict(sorted(rme_census.items()))}
    except Exception as e:                                     # noqa: BLE001
        rme_note = {"error": f"{type(e).__name__}: {e}"}

    def rme_counts(classes: Sequence[str]) -> Dict[str, int]:
        c = (rme_note.get("census") or {})
        return {k: c.get(k, 0) for k in classes}

    payload = {
        "purpose": "IF the ladder convicts S5 and/or S6, this is what "
                   "famgen must learn to AUTHOR for a panelboard-class "
                   "family document.  Element STRUCTURE measured on the "
                   "structural-column donor (rst unit 36); COUNTS for the "
                   "electrical/panelboard class measured on the RME "
                   "panelboard donor (rme unit 30, M_Lighting and "
                   "Appliance Panelboard - 208V MCB - Surface, 549 "
                   "elements, nested => diff-only reference).",
        "S5_styles_categories_fonts": {
            "what": "the family editor's annotation-style constellations: "
                    "each style/attr element OWNS its CategoryElem locals "
                    "(which own their GStyleElem) and FontElems.  There is "
                    "NO free-floating category table -- every CategoryElem "
                    "in both donors is owned by an annotation attr.",
            "ownership_law": "attr -> CategoryElem -> GStyleElem; attr -> "
                             "FontElem.  Backrefs: child obj.m_ownerId / "
                             "hdr m_parents lists mirror the owner; "
                             "Category<->GStyle reference each other "
                             "(m_gstyleIds[] / m_categoryId).",
            "registration": "every element registered in the self-Family "
                            "(m_familyIds absorbed index + header "
                            "m_deletion) exactly like geometry members.",
            "panelboard_counts": rme_counts(
                ["DimensionStyle", "LeaderStyle", "SpotElevationStyle",
                 "TextNoteAttributes", "TagNoteAttributes",
                 "FilledRegionAttributes", "Text3dAttrSymbol",
                 "RevisionCloudAttr", "ReferenceViewerAttributes",
                 "CategoryElem", "GStyleElem", "FontElem"]),
            "column_donor_constellations": constellation_shape(s5_roots),
            "unknowns": [
                "field VALUES per style (tick marks, font names, sizes): "
                "measured dumps exist per element in the donor units; "
                "which values are category-generic vs family-specific is "
                "NOT yet established",
                "whether the audit requires ALL constellations or a "
                "minimal subset (SUB_S5A/S5B begin that bisection)",
                "the m_cellList group ids on CategoryElem rows (observed "
                "m_groupId -> owner style) -- semantics inferred, not "
                "proven",
            ],
        },
        "S6_nested_annotation_family": {
            "what": "a COMPLETE nested annotation symbol family (the "
                    "column donor nests 'Level Head - Upgrade'): a second "
                    "Family element owned by the self-Family, carrying its "
                    "own m_familyIds registry over 112 members resident in "
                    "the SAME unit (its 2D curves, filled regions, tag "
                    "notes, dims, view types, drafting-view chain), plus "
                    "FamilySymbol (the type, owned by the nested family), "
                    "FamilySurrogate + FamSymSurrogate (owned by the "
                    "self-Family).  The nested Family carries NO content "
                    "document (famdoc_bisect: measured).",
            "binding": "LevelAttributes.obj.m_familyTagId -> the nested "
                       "FamilySymbol (the level datum draws its head with "
                       "it).  OUR famgen authors m_familyTagId = -1.",
            "panelboard_counts": {
                "Family_total_incl_self": rme_counts(["Family"])["Family"],
                "FamilySymbol": rme_counts(["FamilySymbol"])["FamilySymbol"],
                "FamilySurrogate": rme_counts(["FamilySurrogate"])["FamilySurrogate"],
                "FamSymSurrogate": rme_counts(["FamSymSurrogate"])["FamSymSurrogate"],
                "note": "the panelboard donor nests THREE annotation "
                        "families (4 Family elements incl. self) -- "
                        "electrical famdocs carry MORE nested furniture "
                        "than the structural column, not less",
            },
            "column_donor_cluster": {
                "family": nf,
                "n_registered_members": len(cls_out["nested_members"]),
                "member_census": dict(sorted(collections.Counter(
                    by_id[i].class_name
                    for i in cls_out["nested_members"]).items())),
                "surrogate_shape": constellation_shape(
                    [i for i in by_id
                     if by_id[i].class_name in ("FamilySymbol",
                                                "FamilySurrogate",
                                                "FamSymSurrogate")]),
            },
            "unknowns": [
                "which nested families a panelboard NEEDS (the RME donor "
                "nests 3; their identities/roles need the RME unit's own "
                "classification pass)",
                "whether the audit requires the nested family or only "
                "tolerates it (SUB_S6's verdict answers this)",
                "the FamSymSurrogate <-> host-side type wiring for a "
                "nested (non-loadable) family -- unmeasured",
            ],
        },
        "rme_panelboard_reference": rme_note,
    }
    path = os.path.join(OUT_DIR, "author_spec.json")
    jdump(path, payload)
    log(f"author_spec.json -> {relp(path)}")
    return path


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the 11 probes")
    b.add_argument("--only", default=None, help="comma-separated probe subset")
    sub.add_parser("classify", help="print + write the class->group map")
    sub.add_parser("spec", help="author_spec.json (top-2 prior groups)")
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
    if a.cmd == "classify":
        _fb()._install_schema()                                # noqa: SLF001
        cls_out = classify()
        dels = deletion_sets(cls_out)
        write_classification(cls_out, dels)
        log(f"partition: {cls_out['sizes']} (+ frame 6)")
        for c, m in cls_out["class_to_group"].items():
            log(f"  {c:38s} {m}")
        return 0
    if a.cmd == "spec":
        _fb()._install_schema()                                # noqa: SLF001
        author_spec()
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
