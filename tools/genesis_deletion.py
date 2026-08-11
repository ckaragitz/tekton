#!/usr/bin/env python
"""genesis_deletion.py -- THE DELETION ENDGAME (genesis-deletion stream, 2026-08-04).

Retire, BY THE REDUCTION LAW, everything on the certified in-place-substituted
base that must LEAVE rather than be substituted:

  * the 8 curtain-SYSTEM families' coherent-removal set (Group A's
    ``curtain_constellation.json`` -- Family x8 + FamilySurrogate x8 + 72
    family-editor DBViewTypes + 40 family-scoped CategoryElem + 40 GStyleElem
    + 24 FontElem + 8 SectionAttributes / InteriorElevAttributes /
    CalloutTag / DimensionStyle / PenWidthTableElem each) TOGETHER WITH the
    two type-preview LegendComponents whose ``m_previewElemId`` owners are
    curtain surrogates (delete-with-content: a preview cannot outlive the
    type it renders) -- ``D_curtain``;
  * the linked-model pair's delete-REACHABLE side: the ``RvtLinkInstance``
    + its ``CopyWatchProperties`` companion (Group B's designed deletion,
    endgame step 15) -- ``D_links``.  The ``RvtLinkSymbol`` is PROVEN NOT
    delete-reachable on this base (it is PINNED by OUR view constellation's
    inherited seq-101 header parents + the residue drafting view's seq-102
    link-overrides map -- the campaign finding this stream records);
  * the constraint-dimension content constellation (LinearDimString 763420
    + the three reference planes locked to it -- their EQ-constraint
    ``m_constrId`` names the dimension, so the planes LEAVE WITH it) --
    ``D_content``.  The room-boundary loop and the two remaining
    type-preview legend components are PROVEN blocked (below) and left
    byte-identical, as the law demands;
  * the 99-element removal queue's LAWFUL CLOSURE -- 88 of its members are
    the atomic curtain family layer (law clause 1) and 11 are members of the
    content constellations, so the queue's coherent closure = the curtain
    set + the dimension group (its room / preview members being blocked)
    -- ``D_queue``;
  * and the cumulative ``D_all`` = the union of the four.

MECHANISM (the ONLY sanctioned reduction generator: ``reduce_law``): maximal
garbage collection over the arbiter's typed reference graph
(``rvt_reduce.maxgc``) + the certified re-blocking deleter
(``rvt.reduce.delete_elements``) -- DELETION-WITH-CONTENT, NEVER
neutralisation.  Every seed is grown to its delete-with-content closure
BEFORE maxgc, and maxgc must then find NOTHING pinned (a pinned seed member
means the seed was not a coherent constellation -- the rung REFUSES to emit
and reports the pinning survivors instead of silently keeping content).
Every emitted file:

  * passes ``src/rvt/reduce_law.py`` ``assert_edit_free(parent, child)``
    (0 edited survivors, 0 added ids -- the K1 crime made mechanical);
  * validates with ZERO errors (``tools/rvt_validate.py``), proves
    structurally (``rvt.reduce.verify_reduced``), keeps the FOUR content
    registries coherent (``rvt.famload.four_registry_census`` -- trivially:
    the base is family-free, and this stream removes no documents);
  * leaves Global/Latest + Global/ContentDocuments + Global/PartitionTable +
    every identity stream BYTE-IDENTICAL to the base (only the element
    partition + Global/ElemTable are re-emitted): registry parity for the
    survivors is 100% BY CONSTRUCTION and NO live registry id is nulled
    (P4/P6); the deleted ids' ADocument registry entries are LEFT DANGLING
    and CENSUSED (dangling ADocument ids are viewer-tolerated: R5 / R9 /
    the curtain lineage's own already-dangling FamilyMgr surrogate 876494).

BASE: ``experiments/genesis/subst_k4/residue_a/ZA_deep.rvt`` -- CERTIFIED
(docs/coverage/viewer-certified.json: "*** GROUP-A RESIDUE LOADS ***";
ORCHESTRATOR VERDICTS #18: 1,806 / 3,342 elements ours, viewer-PASSED).
The batch control = ``CTRL_ZA_deep_base.rvt`` (md5-identical copy).

Usage (repo root)::

  .venv/bin/python tools/genesis_deletion.py            # all five files + probes.json
  .venv/bin/python tools/genesis_deletion.py --rung D_curtain
  .venv/bin/python tools/genesis_deletion.py --analysis  # the blocked-constellation report only
  .venv/bin/python tools/genesis_deletion.py --law D_all  # re-run the law guard on an emitted file

TERRITORY (genesis-deletion): this tool, ``tests/test_genesis_deletion.py``,
``experiments/genesis/subst_k4/deletion/`` (files + reports + probes.json),
``docs/inbox/genesis-deletion.md``.  Everything else is IMPORTED, never
edited.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import rvt_reduce as RR                                            # noqa: E402  (build_state_v2 / maxgc -- the arbiter's graph)
from rvt import reduce_law as RL                                    # noqa: E402  (THE LAW + the guard)
from rvt.reduce import delete_elements, verify_reduced             # noqa: E402  (the certified re-blocking deleter)
from rvt.mutate import Document                                    # noqa: E402
from rvt.validate import validate_file                             # noqa: E402
from rvt import famload                                            # noqa: E402  (four_registry_census)
from rvt.roundtrip import read_streams                             # noqa: E402
from rvt.genesis import residue_a as RA                            # noqa: E402  (curtain_constellation + residue census)

# ---------------------------------------------------------------------------
# paths + constants
# ---------------------------------------------------------------------------
LADDER_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4")
RESIDUE_A_DIR = os.path.join(LADDER_DIR, "residue_a")
BASE = os.path.join(RESIDUE_A_DIR, "ZA_deep.rvt")                 # CERTIFIED (VERDICTS #18)
OUT_DIR = os.path.join(LADDER_DIR, "deletion")
CONTROL_NAME = "CTRL_ZA_deep_base.rvt"
CERTIFIED_JSON = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")
CURTAIN_JSON = os.path.join(RESIDUE_A_DIR, "curtain_constellation.json")
RESIDUE_AFTER_JSON = os.path.join(RESIDUE_A_DIR, "residue_after_ZA_deep.json")
LEDGER_MD = os.path.join(ROOT, "docs", "inbox", "genesis-deletion.md")

#: the FIXED element ids of the named constellations on the ZA_deep base
#: (ids are stable through the whole in-place lineage K4 -> Y9 -> ZA_deep;
#: every id below is verified against the live graph before use).
LINK_SYMBOL = 1250029          # RvtLinkSymbol   -- PINNED (finding), NOT deleted
LINK_INSTANCE = 1250030        # RvtLinkInstance -- deleted
LINK_COPYWATCH = 1250031       # CopyWatchProperties (OUR Y5 object bound to the link) -- deleted WITH
LINK_APPEARANCE_PARENT = 132481  # RvtLinkInstanceAppearanceParentElem (ours) -- KEPT (see below)
ROOM = 1004910                 # RoomElem -- BLOCKED (finding)
ROOM_LEVEL_PLAN = 1004909      # LevelRoomPlan
ROOM_BOUNDARY_CURVES = (1004904, 1004905, 1004906, 1004907, 1004908)
ROOM_SKETCH_PLANE = 245433
ROOM_TOPOLOGY = 9744           # AreaSchemePlanTopologies containing the room content
AREA_SCHEME_OURS = 9490        # OUR AreaMeasureElem (Y5) -- the room anchor's root
CONSTRAINT_DIM = 763420        # LinearDimString (locked EQ constraint)
CONSTRAINED_REFPLANES = (699327, 699381, 763366)
PREVIEW_LEGEND_WALLTYPE = 907404     # LegendComponent previewing BasicWallType 600634 -- BLOCKED
PREVIEW_LEGEND_FLOORTYPE = 1201130   # LegendComponent previewing FloorAttributes 1201129 -- BLOCKED
PREVIEW_LEGEND_CURTAIN = (907423, 907424)   # LegendComponents previewing curtain surrogates 12610/12614 -- deleted WITH curtain
BASIC_WALL_TYPE = 600634
FLOOR_TYPE = 1201129
DRAFTING_VIEW = 1457028

#: the residue-A "Group A NON-INPLACE removal queue" (Yn's 99): 72 family-editor
#: DBViewTypes + 8 curtain Families + 8 FamilySurrogates + the 11 placed-content
#: elements (5 CurveElem + 4 LegendComponent + 1 LinearDimString + 1 LevelRoomPlan)
QUEUE99_CONTENT_CLASSES = ("CurveElem", "LegendComponent", "LinearDimString", "LevelRoomPlan")
QUEUE99_CURTAIN_CLASSES = ("DBViewType", "Family", "FamilySurrogate")


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:                                                # pragma: no cover
        return p


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ===========================================================================
# 1. THE BASE: certification + the standing control
# ===========================================================================

def load_certifications(path: str = CERTIFIED_JSON) -> Dict[str, dict]:
    """{repo-relative file: entry} of the viewer-CERTIFIED ledger."""
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:                                                # pragma: no cover
        return {}
    return {str(e.get("file")): dict(e) for e in (data.get("certified") or []) if e.get("file")}


def certification_of(rvt_path: str) -> Optional[dict]:
    return load_certifications().get(_relp(os.path.abspath(rvt_path)))


def assert_certified(rvt_path: str) -> dict:
    """A deletion rung may only derive from a viewer-CERTIFIED base (verdict
    #15: the whole K1 program was built on an untested base).  Raises when
    ``rvt_path`` is not in the ledger's 'certified' list."""
    cert = certification_of(rvt_path)
    if cert is None:
        raise RuntimeError(
            f"{_relp(rvt_path)} is NOT viewer-certified (docs/coverage/viewer-certified.json"
            f" 'certified'); the deletion endgame builds ONLY on a certified base")
    return cert


BASE_LINEAGE = (
    "ZA_deep = certified Y9 (K4 + the Y-ladder's settings / catalog / palette / datum / view "
    "constructors in place) + Group A's residue layers (sub-categories, annotation types + "
    "fonts, grids / surplus levels, extra patterns, appearance assets), all IN PLACE -- 1,806 of "
    "3,342 host elements are OUR constructors' output, viewer-PASSED (ORCHESTRATOR VERDICTS "
    "#18).  Family-free (K4 lineage): 1 save unit, 0 embedded documents, ContentTable / "
    "ContentDocuments empty, four-registry COHERENT.  The certified control CTRL_ZA_deep_base.rvt "
    "is md5-identical to it.")


def stage_control(base_path: str = BASE, out_dir: str = OUT_DIR) -> dict:
    """Stage the batch's CERTIFIED POSITIVE CONTROL: a byte-identical copy
    of the certified base (md5-asserted), uploaded with EVERY probe of this
    stream.  A failing control voids the batch, never the deletions."""
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, CONTROL_NAME)
    shutil.copyfile(base_path, dst)
    m1, m2 = _md5(base_path), _md5(dst)
    if m1 != m2:                                                    # pragma: no cover
        raise RuntimeError("staged control is not byte-identical to the base")
    return {"file": _relp(dst), "identical_to": _relp(base_path), "md5": m2,
            "certification": certification_of(base_path),
            "note": ("the deletion batch's standing certified control (md5-identical to "
                     "ZA_deep); upload with EVERY batch -- a failing control VOIDS the round")}


# ===========================================================================
# 2. THE GRAPH STATE (arbiter-typed reference graph of the base)
# ===========================================================================

_STATE: Dict[str, dict] = {}


def state_of(base: str = BASE) -> dict:
    """The rvt_reduce ladder-v2 state of ``base`` (typed graph over EVERY
    seq of EVERY record -- the same reference model maxgc and the arbiter
    share), cached per path."""
    ap = os.path.abspath(base)
    if ap not in _STATE:
        _STATE[ap] = RR.build_state_v2(ap)
    return _STATE[ap]


_LANDED: Optional[Dict[int, str]] = None


def landed_slots() -> Dict[int, str]:
    """{slot: rung} of every element the Y-ladder + ZA_deep LANDED an
    our-object in (Yn's own definition of 'ours').  Cached (the rung reports
    are read once per process)."""
    global _LANDED
    if _LANDED is None:
        _LANDED = RA.ladder_landed(extra_reports=[os.path.join(RESIDUE_A_DIR, "ZA_deep.json")])
    return _LANDED


def residue_by_class(st: Optional[dict] = None) -> Dict[str, List[int]]:
    """The K4-inherited RESIDUE of the base (host elements no Y / ZA rung
    landed), grouped by class -- Yn's census re-computed live."""
    st = st or state_of()
    return RA.residue_by_class(st["doc"], landed_slots())


# ===========================================================================
# 3. THE CONSTELLATIONS (delete-with-content seeds, with their graph proof)
# ===========================================================================

@dataclasses.dataclass
class Constellation:
    """One coherent delete-with-content unit and the evidence for it."""
    name: str
    ids: List[int]                          # the delete-with-content seed (closed)
    by_class: Dict[str, int]
    rationale: str                          # why these ids leave TOGETHER (the law clause)
    outside_referrers: List[dict] = dataclasses.field(default_factory=list)   # must be EMPTY (proof)
    grew_from: Dict[str, Any] = dataclasses.field(default_factory=dict)      # the seed's provenance
    notes: List[str] = dataclasses.field(default_factory=list)

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def _by_class(st: dict, ids: Iterable[int]) -> Dict[str, int]:
    c = collections.Counter(st["cls_of"].get(int(e), "?") for e in ids)
    return dict(c.most_common())


def _outside_referrers(st: dict, ids: Iterable[int]) -> List[dict]:
    """Every survivor (host element NOT in ``ids``) whose records reference a
    member of ``ids`` -- the pins that would keep the seed alive under maxgc.
    A coherent delete-with-content constellation has NONE."""
    S = {int(e) for e in ids}
    ref = st["referrers"]
    cls_of = st["cls_of"]
    out = []
    for t in sorted(S):
        for r in sorted(ref.get(t, set())):
            if r not in S:
                out.append({"referrer": int(r), "referrer_class": cls_of.get(r, "?"),
                            "target": int(t), "target_class": cls_of.get(t, "?")})
    return out


def curtain_constellation(st: Optional[dict] = None) -> Constellation:
    """The 8 curtain-SYSTEM families' coherent-removal set (Group A's
    ``curtain_constellation.json``, re-computed live on the base) PLUS the
    type-preview LegendComponents whose deletion parent / ``m_previewElemId``
    owner is a curtain surrogate (they are the constellation's ONLY outside
    referrers; a type's preview leaves WITH the type -- delete-with-content).

    Law clause 1 (the family/type layer is atomic): Family + surrogate +
    every ``m_famId``-scoped child leave TOGETHER; the FamilyMgr entries and
    the CategoryTracking rows that index them are LEFT DANGLING (never
    edited -- exactly R9's certified shape, and the curtain lineage's own
    already-dangling FamilyMgr surrogate 876494 proves the reader tolerates a
    dangling loaded-family surrogate)."""
    st = st or state_of()
    cc = RA.curtain_constellation(st)                                # the residue-A instrument
    core = {int(e) for e in cc["removal_set"]}
    # the ONLY outside referrers of the 232 are type-PREVIEW legend components:
    # a surrogate's m_previewElemId (+ its header deletion parent) names its
    # preview LegendComponent, whose m_deletion parent is the surrogate.  A
    # preview cannot outlive the type it renders => it LEAVES WITH the type.
    previews: Set[int] = set()
    grew: Dict[str, Any] = {"core_removal_set": len(core), "previews_added": []}
    for pin in _outside_referrers(st, core):
        r, rc = pin["referrer"], pin["referrer_class"]
        if rc == "LegendComponent" and pin["target_class"] == "FamilySurrogate":
            previews.add(r)
            grew["previews_added"].append(
                {"legend_component": r, "previews_surrogate": pin["target"],
                 "why": ("type-PREVIEW element: the surrogate's m_previewElemId / header names "
                         "it and its own header deletion parent is the surrogate -- delete-with-"
                         "content (clause 4: the referrer leaves WITH the content)")})
    ids = sorted(core | previews)
    con = Constellation(
        name="curtain-systems",
        ids=ids, by_class=_by_class(st, ids),
        rationale=("THE ATOMIC FAMILY LAYER (law clause 1): the 8 curtain-SYSTEM Family elements "
                   "+ their FamilySurrogates + EVERY m_famId-scoped child (72 family-editor "
                   "DBViewTypes, 40 CategoryElem + 40 GStyleElem sub-category rows, 24 FontElem, 8 "
                   "SectionAttributes / InteriorElevAttributes / CalloutTag / DimensionStyle / "
                   "PenWidthTableElem each) leave TOGETHER, plus the two LegendComponents that "
                   "PREVIEW curtain surrogates 12610 / 12614 (their only outside referrers).  "
                   "Registry effect: 8 of the 9 FamilyMgr.m_arrLoadedFamilyInfo entries + 40 "
                   "CategoryTracking category rows + 40 style rows in Global/Latest are LEFT "
                   "DANGLING (never edited) -- the R9 shape; the same lineage ALREADY carries the "
                   "dangling FamilyMgr surrogate 876494, which the reader accepts (K4 / Y9 / ZA_deep "
                   "all viewer-PASSED)."),
        outside_referrers=_outside_referrers(st, ids),
        grew_from=grew,
        notes=[
            f"curtain families: {[f['name'] for f in cc['families']]}",
            "system-family removal has NO prior viewer verdict (the endgame's flagged unproven "
            "mechanic, step 22) -- this constellation is EXACTLY that probe, isolated, with the "
            "certified control",
            "SlaveSymbolTrackerElem 1454535 is NOT curtain machinery on this base: its master is "
            "FabricSheetType 1352719 (verified live) -- it leaves with the fabric-sheet type, not here",
        ])
    return con


def links_constellation(st: Optional[dict] = None) -> Tuple[Constellation, dict]:
    """The linked-model pair's DELETE-REACHABLE side + the blocked analysis.

    Reachable: RvtLinkInstance 1250030 and CopyWatchProperties 1250031 (OUR
    Y5 object BOUND to the link: its seq-102 ``m_linkId`` names the instance
    and its header lists both link ids as deletion parents -- a copy/monitor
    settings record cannot outlive its link => delete-with-content).

    BLOCKED (the finding): the RvtLinkSymbol 1250029 is PINNED by OUR OWN
    view constellation -- the seq-101 headers of DBViewProject 230, DBViewPlan
    245443 / 1064656, DBView3d 1454508 and the Y2 navigator 69851 (all Y-ladder
    LANDED slots) list it as a deletion parent (in-place substitution replaced
    ONLY seq-102 objects, so those headers are Autodesk's originals), and the
    residue drafting view 1457028 names it in its seq-102 link-overrides map
    (a validator-gated ElementId) and its header.  Deleting the symbol would
    (a) leave a dangling seq-102 ElementId (validator ERROR) and (b) require
    editing our views' headers (BANNED) or deleting our whole view
    constellation.  The certified fix is NOT a deletion: the view / navigator
    constructors must re-emit their slots WITH CLEAN HEADERS (a seqs=(101,102)
    in-place rung of the substitution stream), after which the symbol + the
    drafting-view constellation become one delete-reachable rung.

    KEPT ON PURPOSE: RvtLinkInstanceAppearanceParentElem 132481 (OUR Y5
    object): referenced ONLY by the instance and referencing nothing, so it
    dangles NOWHERE once the instance goes; deleting it would empty the
    UniqueElementsTracking positional slot 41 that indexes it for no gain."""
    st = st or state_of()
    cls_of = st["cls_of"]
    ref = st["referrers"]
    graph = st["graph"]
    ids = sorted({LINK_INSTANCE, LINK_COPYWATCH})
    con = Constellation(
        name="linked-model-instance",
        ids=ids, by_class=_by_class(st, ids),
        rationale=("The placed link + its copy/monitor companion: CopyWatchProperties 1250031 (our "
                   "Y5-landed object, born bound to the sample link -- seq-102 m_linkId = the "
                   "instance) references the instance, and NOTHING references CopyWatchProperties, "
                   "so the pair {instance, copy-monitor properties} is a closed delete-with-content "
                   "unit.  The link SYMBOL is pinned (blocked analysis) and stays."),
        outside_referrers=_outside_referrers(st, ids),
        notes=[
            "CopyWatchProperties 1250031 is one of OUR Y5 objects: it existed only because the "
            "sample carried a link; on a link-free genesis base the Y5 constructor should not "
            "build it (proposed hook for the settings stream)",
            f"RvtLinkInstanceAppearanceParentElem {LINK_APPEARANCE_PARENT} (ours) is KEPT: it "
            "references nothing and only the instance referenced it, so keeping it dangles nowhere "
            "and keeps UniqueElementsTracking slot 41 valid",
        ])
    # -- the blocked analysis of the SYMBOL ------------------------------------
    symbol_pins = []
    for r in sorted(ref.get(LINK_SYMBOL, set())):
        symbol_pins.append({"referrer": int(r), "class": cls_of.get(r, "?"),
                            "ours": r in landed_slots(),
                            "fields": _ref_fields(st, r, {LINK_SYMBOL})})
    blocked = {
        "element": LINK_SYMBOL, "class": cls_of.get(LINK_SYMBOL),
        "verdict": "NOT delete-reachable on ZA_deep by any sanctioned generator",
        "pinned_by": symbol_pins,
        "symbol_references_outward": [(int(x), cls_of.get(x)) for x in sorted(graph.get(LINK_SYMBOL, set()))],
        "why": ("Six of the seven pinning records are OUR OWN landed view / navigator slots "
                "(Y9 / Y2): in-place substitution replaced only their seq-102 objects, so their "
                "seq-101 ElementHeader.m_parents webs are the sample's originals and list the link "
                "symbol as a deletion parent.  The seventh, DBViewDrafting 1457028 (residue), also "
                "names it in a validator-gated seq-102 field (m_pRvtLinkOverrides ... "
                "m_displaySettingsMap[0].first).  maxgc pins the symbol; the validator would ERROR; "
                "the law forbids editing the referrers."),
        "fix": ("(1) the substitution stream re-emits our view / navigator slots WITH OUR "
                "HEADERS (regadd full-record in-place rung, seqs=(101,102)) whose parent lists name "
                "only surviving elements; (2) the drafting-view constellation (1457028 + Viewer "
                "1457029 + Viewports 1457030/43/44 + DBDrawing 1457031 + SketchPlane 1457032) is "
                "adopted-as-ours or seeded WITH the symbol -- it is itself pinned by our plans "
                "245443 / 1064656 and their Viewers; then {symbol, drafting constellation} is one "
                "maxgc rung.  The symbol's external-file name / path (the sample-lineage string "
                "the endgame wants gone) leaves in that rung, or in the own-save identity step."),
    }
    return con, blocked


def content_constellation(st: Optional[dict] = None) -> Tuple[Constellation, dict]:
    """The delete-reachable CONTENT of residue-A's dispositions: the locked
    constraint dimension 763420 + the three reference planes it locks
    (their seq-102 ``m_constrInfo[0]->EqConstrInfo.m_constrId`` names the
    dimension, so the planes cannot outlive it -- delete-with-content; the
    three planes reference only each other and the dimension, and nothing
    else references them: a CLOSED constellation).

    BLOCKED (findings, left byte-identical):
      * the ROOM constellation (RoomElem 1004910 + LevelRoomPlan 1004909 + 5
        area-boundary CurveElems + boundary SketchPlane 245433): its containing
        topology AreaSchemePlanTopologies 9744 lists the room content as regen
        children / its LevelRoomPlan in a seq-102 plan-topology set (law
        clause 2: the containing topology leaves WITH its content) -- and 9744
        is pinned by OUR AreaMeasureElem 9490 (a Y5-landed slot), whose seq-102
        ``m_areaSchemePlanTopologyElemId`` (+ header) names it.  The chain
        room <- 9744 <- OUR 9490 makes the room NOT delete-reachable until the
        area-scheme constructor stops wiring the sample's plan topology.
      * the two type-PREVIEW legend components 907404 (BasicWallType 600634's
        m_previewElemId) and 1201130 (FloorAttributes 1201129's): owned
        preview children of the residue system-family types the types stream
        substitutes / retires -- they leave with THOSE types, not here."""
    st = st or state_of()
    cls_of = st["cls_of"]
    ids = sorted({CONSTRAINT_DIM, *CONSTRAINED_REFPLANES})
    con = Constellation(
        name="constraint-dimension",
        ids=ids, by_class=_by_class(st, ids),
        rationale=("The locked EQ-constraint dimension (LinearDimString 763420, category "
                   "OST_Constraints) + the three reference planes it locks: each plane's seq-102 "
                   "m_constrInfo[0]->EqConstrInfo.m_constrId = the dimension and the dimension's "
                   "witness refs name the planes (a mutual constellation); nothing else references "
                   "any of the four (verified) => a CLOSED delete-with-content unit.  A constraint's "
                   "'value' is the geometry it constrains -- content, not a substitution slot."),
        outside_referrers=_outside_referrers(st, ids),
        notes=[
            "the 3 reference planes are Group B classes (M..Z) on their branch; on THIS base they "
            "are Autodesk residue and members of the dimension's constellation (endgame section 2, "
            "'the dimensioned refplane group') -- the constellation leaves whole",
        ])
    # -- the blocked analysis: room + type previews ---------------------------
    room_ids = [ROOM, ROOM_LEVEL_PLAN, ROOM_SKETCH_PLANE, *ROOM_BOUNDARY_CURVES]
    blocked = {
        "room_constellation": {
            "ids": room_ids, "by_class": _by_class(st, room_ids),
            "verdict": "NOT delete-reachable on ZA_deep (law clause 2 + maxgc)",
            "anchor_chain": [
                {"element": ROOM_TOPOLOGY, "class": cls_of.get(ROOM_TOPOLOGY),
                 "role": "the containing AreaSchemePlanTopologies of the room content",
                 "names_content_in": _ref_fields(st, ROOM_TOPOLOGY, set(room_ids)),
                 "law": ("clause 2 -- a plan-topology's structured entries: the containing "
                         "topology is DELETED WITH its content, or the content is kept")},
                {"element": AREA_SCHEME_OURS, "class": cls_of.get(AREA_SCHEME_OURS),
                 "ours": AREA_SCHEME_OURS in landed_slots(),
                 "role": "OUR area-scheme object (Y5-landed) that pins the topology",
                 "names_topology_in": _ref_fields(st, AREA_SCHEME_OURS, {ROOM_TOPOLOGY}),
                 "law": "editing our surviving object is not a deletion; deleting it is out of scope"},
            ],
            "fix": ("the Y5 AreaMeasureElem constructor emits m_areaSchemePlanTopologyElemId = -1 "
                    "(and no header parent to the sample topology) on a base whose plan topology is "
                    "content-to-remove; then {9744 + room content} is one clean maxgc rung.  Until "
                    "then the room loop stays BYTE-IDENTICAL (the law's own alternative)."),
        },
        "type_preview_legend_components": {
            "ids": [PREVIEW_LEGEND_WALLTYPE, PREVIEW_LEGEND_FLOORTYPE],
            "verdict": "owned preview children of residue system-family types (types-stream territory)",
            "owners": {str(PREVIEW_LEGEND_WALLTYPE): _ref_fields(st, BASIC_WALL_TYPE, {PREVIEW_LEGEND_WALLTYPE}),
                       str(PREVIEW_LEGEND_FLOORTYPE): _ref_fields(st, FLOOR_TYPE, {PREVIEW_LEGEND_FLOORTYPE})},
            "why": ("BasicWallType 600634 / FloorAttributes 1201129 name their preview LegendComponent "
                    "in m_previewElemId (a validator-gated seq-102 field) + their header deletion "
                    "parents; the preview leaves ONLY with its type.  The types are the residue "
                    "system-family types the types stream substitutes in place (our wall / floor "
                    "type constructors) -- the preview companion is that rung's decision, exactly as "
                    "the curtain surrogates' previews left with the curtain constellation here."),
        },
    }
    return con, blocked


def queue99(st: Optional[dict] = None) -> dict:
    """The residue-A 99-element removal queue re-derived LIVE (Yn's
    'Group A NON-INPLACE (curtain constellation / placed content)'
    disposition): 72 family-editor DBViewTypes + 8 curtain Families + 8
    FamilySurrogates + 5 CurveElem + 4 LegendComponent + 1 LinearDimString +
    1 LevelRoomPlan, all K4-inherited residue on the base."""
    st = st or state_of()
    res = residue_by_class(st)
    doc = st["doc"]
    q: Dict[str, List[int]] = {}
    for cls_name in QUEUE99_CURTAIN_CLASSES:
        ids = res.get(cls_name, [])
        if cls_name == "DBViewType":                                # family-scoped view types only
            _proj, fam = RA.split_family_scoped(doc, ids)
            ids = fam
        q[cls_name] = sorted(ids)
    for cls_name in QUEUE99_CONTENT_CLASSES:
        q[cls_name] = sorted(res.get(cls_name, []))
    flat = sorted({e for v in q.values() for e in v})
    return {"by_class": q, "ids": flat, "count": len(flat),
            "note": ("Yn's 'Group A NON-INPLACE removal queue' re-derived on ZA_deep: the residue "
                     "classes residue-A named as removal (not substitution) candidates")}


def queue99_closure(st: Optional[dict] = None, curtain: Optional[Constellation] = None,
                    content: Optional[Constellation] = None,
                    content_blocked: Optional[dict] = None) -> Tuple[List[int], dict]:
    """The 99-queue's LAWFUL CLOSURE: the queue as listed is NOT independently
    delete-reachable -- 88 of its members are the atomic curtain family layer
    (clause 1: they cannot leave without their 144 scoped children), and its
    11 content members belong to content constellations.  Its coherent closure
    therefore = the curtain constellation UNION the delete-reachable content
    constellation (the dimension group); its room / type-preview members are
    the BLOCKED ones.  Returns (closure ids, the accounting)."""
    st = st or state_of()
    curtain = curtain or curtain_constellation(st)
    if content is None or content_blocked is None:
        content, content_blocked = content_constellation(st)
    q = queue99(st)
    qset = set(q["ids"])
    cur = set(curtain.ids)
    dim = set(content.ids)
    room = set(content_blocked["room_constellation"]["ids"])
    previews_blocked = set(content_blocked["type_preview_legend_components"]["ids"])
    closure = sorted(cur | dim)
    acct = {
        "queue_count": len(qset),
        "queue_by_class": {k: len(v) for k, v in q["by_class"].items()},
        "queue_members_in_curtain_constellation": len(qset & cur),
        "queue_members_in_dimension_group": len(qset & dim),
        "queue_members_blocked_room": sorted(qset & room),
        "queue_members_blocked_type_previews": sorted(qset & previews_blocked),
        "queue_members_unaccounted": sorted(qset - cur - dim - room - previews_blocked),
        "closure_beyond_queue": {"curtain_scoped_children": len(cur - qset),
                                 "dimension_refplanes": len(dim - qset)},
        "closure_count": len(closure),
        "equals_curtain_union_content": True,
        "reading": ("the 99-queue is not an independent deletion set: its lawful closure is exactly "
                    "D_curtain's set UNION D_content's set (its room / type-preview members are the "
                    "BLOCKED constellations); D_queue emits that closure as the coarser bisection cut"),
    }
    return closure, acct


def _ref_fields(st: dict, owner: int, targets: Set[int]) -> List[dict]:
    """Which decoded fields of ``owner`` (seq 101 header / seq 102 object /
    seq 103 rep) hold an ElementId in ``targets`` -- the evidence behind a pin."""
    from rvt.validate import _RefDecoder                                # the arbiter's decoder
    doc = st["doc"]
    dec = _RefDecoder(doc.dec.schema)
    out = []
    for seq in (101, 102, 103):
        rec = doc.idx[seq].get(int(owner))
        if rec is None:
            continue
        dec.refs = []
        try:
            dec.decode_record(rec.class_id, rec.payload)
        except Exception as ex:                                    # pragma: no cover
            out.append({"seq": seq, "error": repr(ex)[:120]})
            continue
        for path, val in dec.refs:
            if isinstance(val, int) and val in targets:
                out.append({"seq": seq, "field": path, "target": int(val)})
    return out


# ===========================================================================
# 4. THE RUNG TABLE
# ===========================================================================

@dataclasses.dataclass
class DeletionRung:
    name: str
    label: str
    description: str
    tests: str
    if_pass: str
    if_fail: str
    order: int                                   # upload order (bisection-first: D_all first)


RUNGS: List[DeletionRung] = [
    DeletionRung(
        name="D_all", order=1,
        label="ZA_deep with EVERY delete-reachable endgame deletion (curtain systems + link instance + constraint dims)",
        description=("The cumulative deletion file: certified ZA_deep MINUS the union of the three "
                     "delete-reachable constellations -- the 8 curtain-SYSTEM families' whole atomic "
                     "layer (232 elements + the 2 surrogate type-previews), the linked model's "
                     "instance side (RvtLinkInstance + its CopyWatchProperties companion), and the "
                     "locked constraint dimension with its three reference planes -- by maximal "
                     "garbage collection (delete-with-content, ZERO survivor edits: reduce_law "
                     "EDIT-FREE proven).  Global/Latest, Global/ContentDocuments, the identity and "
                     "history streams are BYTE-IDENTICAL to ZA_deep; only Partitions/21 + "
                     "Global/ElemTable change.  D_queue's set is a subset (D_all = D_queue + the "
                     "two link elements)."),
        tests=("Whether the reader accepts the whole delete-reachable deletion endgame at once on "
               "the certified in-place base: the FIRST removal of a SYSTEM-family layer (curtain "
               "systems -- no prior viewer verdict), the retirement of the placed link instance + "
               "its copy-monitor companion, and the removal of the locked constraint-dimension group "
               "-- all with the ADocument registries left dangling (never edited)."),
        if_pass=("Every delete-reachable removal candidate of the endgame is retired lawfully: the "
                 "system-family removal mechanic is PROVEN, the link instance is gone, the "
                 "constraint content is gone; the remaining Autodesk residue = the BLOCKED "
                 "constellations (link symbol, room loop, two type previews -- each with its named "
                 "fix) + Group B's classes + the product-data / analysis buckets (this record's "
                 "'residue after D_all' census).  D_all becomes the certified base of the next "
                 "phase (blocked-constellation fixes + Phase-III singles)."),
        if_fail=("Read the singles (each derives DIRECTLY from ZA_deep, control uploaded with the "
                 "batch): D_curtain FAIL => the SYSTEM-family removal is what the reader rejects "
                 "(the prime suspect: an unproven mechanic); D_links FAIL => the link instance / "
                 "copy-monitor removal (the CopyWatchModeMgr / RvtLinkInstTracking registries "
                 "dangling); D_content FAIL => the constraint-dimension group (ConstraintDimTracking "
                 "/ DatumTracking dangling); D_queue (curtain + dims) splits the interaction.  A "
                 "single FAILing with its parent ZA_deep certified and the control PASSING convicts "
                 "exactly its constellation.")),
    DeletionRung(
        name="D_curtain", order=2,
        label="ZA_deep minus the 8 curtain-SYSTEM families' whole atomic layer (232 + 2 previews)",
        description=("Certified ZA_deep MINUS the curtain constellation: the 8 curtain-SYSTEM Family "
                     "elements ('Rectangular / Circular / L / V / Trapezoid / Quad Corner Mullion', "
                     "'System Panel', 'Empty System Panel') + their 8 FamilySurrogates + every "
                     "m_famId-scoped child (72 family-editor DBViewTypes, 40 CategoryElem + 40 "
                     "GStyleElem sub-category rows, 24 FontElem, 8 SectionAttributes, 8 "
                     "InteriorElevAttributes, 8 CalloutTags, 8 'Diameter' DimensionStyles, 8 family "
                     "pen tables) + the 2 LegendComponents that PREVIEW the surrogates 12610 / 12614 "
                     "(their only outside referrers) -- deleted TOGETHER by maxgc (law clause 1: the "
                     "family/type layer is atomic).  8 of the 9 FamilyMgr loaded-family entries + 40 "
                     "CategoryTracking category rows + 40 style rows in Global/Latest are LEFT "
                     "DANGLING (Latest byte-identical, never edited); the four content registries are "
                     "untouched (system families own no embedded document)."),
        tests=("The endgame's ONE unproven removal mechanic, isolated: does the reader accept the "
               "removal of a SYSTEM-family layer (the curtain families) with its FamilyMgr / "
               "CategoryTracking registry entries left dangling -- the R9 pattern, applied to "
               "system families for the first time?  (The certified precedents: R9 deleted every "
               "LOADABLE family with Latest untouched and PASSED; the base's own FamilyMgr already "
               "carries the dangling surrogate 876494 and PASSES.)"),
        if_pass=("System-family removal by maxgc with dangling registries is reader-legal: the "
                 "curtain constellation is retired for real and every future genesis file may omit "
                 "curtain systems the same way (endgame step 22 CLOSED)."),
        if_fail=("(with the control + D_content / D_links PASSING) the SYSTEM-family layer or one "
                 "of its dangling registry surfaces is what the reader requires: read the card "
                 "message, then bisect (a) the family layer alone WITHOUT the sub-category / view-type "
                 "children [not clause-1-legal: only as a research probe], (b) the same removal WITH "
                 "the sanctioned registry-reconciliation purge of the 8 FamilyMgr entries + the 80 "
                 "CategoryTracking rows (Revit's own deletion semantics, the KD1 method) -- the "
                 "'reconciled' variant this record already specifies (D_curtain_reconciled)."))
    ,
    DeletionRung(
        name="D_links", order=3,
        label="ZA_deep minus the linked model's instance side (RvtLinkInstance + our CopyWatchProperties)",
        description=("Certified ZA_deep MINUS the placed linked model's delete-reachable side: the "
                     "RvtLinkInstance 1250030 + CopyWatchProperties 1250031 (OUR Y5-landed "
                     "copy/monitor object, born bound to the sample link -- its seq-102 m_linkId names "
                     "the instance, so it LEAVES WITH it: delete-with-content).  The RvtLinkSymbol "
                     "1250029 STAYS: it is PROVEN pinned by OUR view constellation's inherited seq-101 "
                     "header parents + the residue drafting view's seq-102 link-overrides map (this "
                     "stream's central finding -- the fix is a clean-header substitution rung, not a "
                     "deletion).  RvtLinkInstanceAppearanceParentElem 132481 (ours) is kept: nothing it "
                     "names, nothing dangles.  The CopyWatchModeMgr (m_linkCopyWatchProps / "
                     "m_linkDocIds) + RvtLinkInstTracking registry entries are LEFT DANGLING."),
        tests=("Whether the reader accepts a project whose linked model is LOADED (symbol present) "
               "but UNPLACED (instance + copy-monitor companion deleted), with the link-instance "
               "registries dangling -- the delete-reachable half of the link retirement."),
        if_pass=("The link instance side is retired lawfully; the remaining sample-lineage exposure "
                 "of the link is the SYMBOL (external file name / path), whose retirement waits on "
                 "the clean-header view rung named in this record (a substitution-stream task)."),
        if_fail=("(with the control PASSING) an unplaced-link project or a dangling link-instance "
                 "registry (CopyWatchModeMgr / RvtLinkInstTracking) is rejected: the link must "
                 "leave WHOLE (symbol + instance + registries) in a single future rung after the "
                 "clean-header fix, or the CopyWatch registries need the sanctioned reconciliation "
                 "purge -- read the card message."))
    ,
    DeletionRung(
        name="D_content", order=4,
        label="ZA_deep minus the delete-reachable placed CONTENT (the locked constraint dimension + its 3 reference planes)",
        description=("Certified ZA_deep MINUS the constraint-dimension constellation: LinearDimString "
                     "763420 (a locked EQ constraint, category OST_Constraints, typed by the secret "
                     "internal LinAng dimension style) + the three reference planes it locks (699327 "
                     "/ 699381 / 763366 -- their EqConstrInfo.m_constrId names the dimension, so they "
                     "leave WITH it; nothing else references the four).  The ROOM boundary loop "
                     "(RoomElem + LevelRoomPlan + 5 CurveElems + sketch plane) and the two remaining "
                     "type-preview legend components are PROVEN blocked (anchored to our own "
                     "AreaMeasureElem's plan-topology wiring / to residue system types) and are left "
                     "BYTE-IDENTICAL exactly as the law requires -- the blocked table names each anchor "
                     "field and its fix.  ConstraintDimTracking + DatumTracking registry entries are LEFT "
                     "DANGLING."),
        tests=("Whether the reader accepts the removal of the locked-constraint content constellation "
               "(a constraint dimension + the planes it locks) by maxgc, with its constraint / datum "
               "tracking registry entries left dangling."),
        if_pass=("The constraint content is retired; the placed-content residue that remains "
                 "(room loop, type previews) is exactly the blocked table -- retired by the two "
                 "constructor fixes it names, not by more deletion attempts."),
        if_fail=("(with the control PASSING) removing a locked constraint's dimension + planes is "
                 "rejected -- most likely the ConstraintDimTracking / DatumTracking registry entries "
                 "must be reconciled (the KD1-style purge, sanctioned): the reconciled variant is the "
                 "one-change follow-up (D_content_reconciled); read the card message first."))
    ,
    DeletionRung(
        name="D_queue", order=5,
        label="ZA_deep minus the 99-element removal queue's LAWFUL CLOSURE (= curtain constellation + constraint-dimension group)",
        description=("Certified ZA_deep MINUS the coherent closure of Yn's 99-element 'Group A "
                     "NON-INPLACE removal queue' (72 family-editor DBViewTypes + 8 curtain Families "
                     "+ 8 surrogates + 5 boundary CurveElems + 4 LegendComponents + 1 LinearDimString "
                     "+ 1 LevelRoomPlan).  The queue as listed is NOT independently delete-reachable: "
                     "88 of its members are the atomic curtain family layer (clause 1 forces their 144 "
                     "scoped children out with them) and its 11 content members belong to content "
                     "constellations (the dimension group / the BLOCKED room loop / the type-preview "
                     "pairs) -- so its lawful closure is exactly D_curtain's set UNION D_content's set "
                     "(238 elements), a superset of the queue by the curtain-scoped children and the "
                     "three constrained planes, minus the blocked room / preview members which stay."),
        tests=("The coarser bisection cut: curtain systems + constraint content together (everything "
               "of D_all except the link instance side)."),
        if_pass=("The Group-A removal queue is retired in its lawful sense; only the blocked members "
                 "(room loop 8, type previews 2 -- each named with its fix) remain of the queue."),
        if_fail=("(reading with the singles) D_queue FAIL with D_curtain and D_content BOTH PASSING "
                 "=> the INTERACTION of the two removals (unexpected: their sets are disjoint); D_queue "
                 "FAIL with a single FAILING => that single's constellation is the cause."))
    ,
]


def rung_by_name(name: str) -> DeletionRung:
    for r in RUNGS:
        if r.name == name:
            return r
    raise KeyError(f"unknown rung {name!r}; known: {[r.name for r in RUNGS]}")


# ===========================================================================
# 5. DELETION SETS (per rung) + the endgame accounting
# ===========================================================================

@dataclasses.dataclass
class Endgame:
    """The whole deletion-endgame decision on the base: the constellations,
    the per-rung deletion sets, the blocked analysis and the queued next."""
    curtain: Constellation
    links: Constellation
    content: Constellation
    links_blocked: dict
    content_blocked: dict
    queue99: dict
    queue_accounting: dict
    sets: Dict[str, List[int]]
    next_queue: Dict[str, dict]

    def to_json(self) -> dict:
        return {
            "constellations": {c.name: c.to_json() for c in (self.curtain, self.links, self.content)},
            "blocked": {"link_symbol": self.links_blocked, **self.content_blocked},
            "queue99": {k: v for k, v in self.queue99.items() if k != "ids"} | {"ids_count": len(self.queue99["ids"])},
            "queue99_closure_accounting": self.queue_accounting,
            "deletion_sets": {k: {"count": len(v)} for k, v in self.sets.items()},
            "set_relations": self.set_relations(),
            "next_queue": self.next_queue,
        }

    def set_relations(self) -> dict:
        S = {k: set(v) for k, v in self.sets.items()}
        return {
            "D_all_equals_union_of_singles": S["D_all"] == (S["D_curtain"] | S["D_links"]
                                                          | S["D_content"] | S["D_queue"]),
            "D_queue_equals_curtain_union_content": S["D_queue"] == (S["D_curtain"] | S["D_content"]),
            "D_all_minus_D_queue": sorted(S["D_all"] - S["D_queue"]),
            "singles_pairwise_disjoint_except_queue": (
                not (S["D_curtain"] & S["D_links"]) and not (S["D_curtain"] & S["D_content"])
                and not (S["D_links"] & S["D_content"])),
        }


def _residue_ids(st: dict, *classes: str) -> List[int]:
    res = residue_by_class(st)
    out: List[int] = []
    for c in classes:
        out += res.get(c, [])
    return sorted(out)


def next_queue(st: dict) -> Dict[str, dict]:
    """The endgame's REMAINING deletion candidates beyond this batch, with
    their measured maxgc reach-ability on the base (recorded, NOT emitted:
    each is another stream's disposition or an ambiguous counsel item)."""
    out: Dict[str, dict] = {}

    def reach(name: str, ids: List[int], disposition: str, decision: str) -> None:
        if not ids:
            out[name] = {"seed": 0, "note": "class absent on this base"}
            return
        d, k, _ev = RR.maxgc(st, set(RR._protect_history(st, set(ids))))
        out[name] = {"seed": len(ids), "maxgc_deletable": len(d), "pinned": len(k),
                     "pinned_by_class": _by_class(st, k),
                     "disposition": disposition, "decision": decision}

    reach("surplus_browser_schemes", _residue_ids(st, "BrowserOrganization"),
          "residue-A 'surplus-removal' (endgame step 19)",
          "clean leaves (deletable); their own single (D_surplus) in the next batch, or with the "
          "own-save step -- not in this batch to keep D_all exactly the union of the four singles")
    drafting = [1457028, 1457029, 1457030, 1457031, 1457032, 1457043, 1457044]
    reach("drafting_view_constellation",
          [e for e in drafting if e in st["host"]],
          "endgame section 2 'adopt or delete'",
          "ANSWERED by the graph: pinned by OUR plans 245443/1064656 + their Viewers => ADOPT (the "
          "delete branch is not reachable); this is also the second pin on the link symbol")
    reach("hvac_energy_database",
          _residue_ids(st, "HVACLoadSpaceTypeElem", "HVACLoadBuildingTypeElem",
                       "HVACLoadScheduleElem", "BuildingOperatingYearSchedule"),
          "product data -- counsel-or-removal (endgame step 23)",
          "207 of 212 delete-reachable; 5 pinned via OUR EnergyDataSettings + the (blocked) room; a "
          "later Phase-III single once counsel rules (not this batch)")
    reach("misc_analysis_area_machinery",
          _residue_ids(st, "AreaTypeElem", "AreaSchemePlanTopologies", "AreaReportSettingsElem",
                       "AssemblyCodeTable", "DataStorage", "LoadCaseElem", "LoadNatureElem",
                       "ColorFillSchema"),
          "misc analysis machinery -- 'analysis-settings rung OR removal' (endgame step 24)",
          "32 of 43 delete-reachable; the AreaType / AreaScheme rows are pinned by OUR area schemes "
          "and the AreaReportSettings by our category / font rows -- ambiguous disposition, a "
          "later single (not this batch)")
    reach("fabric_sheet_type_and_slave_tracker",
          _residue_ids(st, "FabricSheetType", "FabricWireType", "SlaveSymbolTrackerElem"),
          "rebar fabric system types (no constructor) + the slave tracker whose master is FabricSheetType",
          "residue-A misfiled the tracker as curtain machinery; it leaves with the fabric-sheet type "
          "(system-types disposition -- types stream / a later single)")
    return out


def build_endgame(st: Optional[dict] = None) -> Endgame:
    st = st or state_of()
    curtain = curtain_constellation(st)
    links, links_blocked = links_constellation(st)
    content, content_blocked = content_constellation(st)
    closure, acct = queue99_closure(st, curtain, content, content_blocked)
    sets = {
        "D_curtain": sorted(set(curtain.ids)),
        "D_links": sorted(set(links.ids)),
        "D_content": sorted(set(content.ids)),
        "D_queue": sorted(set(closure)),
    }
    sets["D_all"] = sorted(set(sets["D_curtain"]) | set(sets["D_links"])
                            | set(sets["D_content"]) | set(sets["D_queue"]))
    return Endgame(curtain=curtain, links=links, content=content,
                   links_blocked=links_blocked, content_blocked=content_blocked,
                   queue99=queue99(st), queue_accounting=acct, sets=sets,
                   next_queue=next_queue(st))


# ===========================================================================
# 6. THE DANGLING / REGISTRY CENSUS (what a deletion leaves in Global/Latest)
# ===========================================================================

def adocument_dangling_census(path: str, deleted_ids: Iterable[int]) -> dict:
    """The ADocument (Global/Latest) registry surface of the DELETED ids in
    ``path``: which typed ElementId leaves of the document object now name an
    element that no longer exists (LEFT DANGLING -- viewer-tolerated per
    R5 / R9), grouped by class and by registry path.  Latest is byte-identical
    to the base in every file this stream emits, so NO live registry id is
    nulled (P4/P6) and NO registry row is edited -- asserted separately by the
    stream-identity check."""
    import genesis_assemble as GA                                    # the ADocument codec's typed walker
    import genesis_substitute as GS
    from rvt import adocument as adoc
    from rvt.container import open_rvt
    want = {int(i) for i in deleted_ids}
    with open_rvt(path) as f:
        payload = f.inflate(adoc.STREAM, 0)
    a = adoc.decode_latest(payload)
    ted = GS.TypedEditor(decoder=None, maps=GA.load_registry_maps())
    surf = GS.adoc_surface(ted, a.value, want)                        # {id: [normalized paths]}
    doc = Document.from_file(path)
    # class of a DELETED id: not in the file any more -> classify from the base
    base_doc = Document.from_file(BASE)
    by_class = collections.Counter(base_doc.class_of(i) or "?" for i in surf)
    by_path: collections.Counter = collections.Counter()
    for _i, ps in surf.items():
        for p in ps:
            by_path[p] += 1
    still_present = sorted(i for i in surf if i in doc.et_by_id)
    return {
        "adocument_clean": bool(a.clean),
        "deleted_ids_with_registry_surface": len(surf),
        "by_class": dict(by_class.most_common()),
        "by_registry_path": dict(by_path.most_common()),
        "examples": {str(i): ps[:3] for i, ps in list(surf.items())[:8]},
        "deleted_ids_still_present_in_file": still_present,        # must be []
        "verdict": ("DANGLING ONLY (deleted ids' registry entries left as they were; Latest "
                    "byte-identical => zero nulled live ids, zero registry edits) -- viewer-"
                    "tolerated per R5 / R9 and the curtain lineage's own dangling FamilyMgr "
                    "surrogate 876494"),
    }


def stream_identity(base: str, out: str) -> dict:
    """Which streams of ``out`` are BYTE-IDENTICAL to ``base``.  A deletion
    re-emits ONLY the element partition + Global/ElemTable; everything else
    (Global/Latest, ContentDocuments, PartitionTable, History, DIT, identity)
    must be byte-identical."""
    a, b = read_streams(base), read_streams(out)
    same, diff = [], []
    for p in sorted(set(a) | set(b)):
        (same if a.get(p) == b.get(p) else diff).append(p)
    expected_diff = {"Global/ElemTable"} | {p for p in diff if p.startswith("Partitions/")}
    return {"byte_identical_streams": same, "differing_streams": diff,
            "only_partition_and_elemtable_differ": set(diff) <= expected_diff,
            "latest_byte_identical": "Global/Latest" in same,
            "contentdocs_byte_identical": "Global/ContentDocuments" in same,
            "partitiontable_byte_identical": "Global/PartitionTable" in same}


# ===========================================================================
# 7. THE RUNG OPERATOR (emit + certify one deletion file)
# ===========================================================================

def emit_rung(name: str, delete_ids: Sequence[int], st: Optional[dict] = None, *,
              endgame: Optional[Endgame] = None, out_dir: str = OUT_DIR,
              control: Optional[dict] = None, base: str = BASE) -> dict:
    """Emit ``<out_dir>/<name>.rvt`` = certified ``base`` MINUS ``delete_ids``
    (maxgc-verified: nothing pinned) by the certified deleter, and write the
    certification report ``<name>.json`` + the law report ``<name>_law.json``.

    Gates (a rung that fails any is NOT-CLEAN and says why): the reduction-law
    guard EDIT-FREE (0 edited survivors, 0 added ids); validator 0 errors; the
    structural proof; four-registry coherence; every non-partition stream
    byte-identical to the base (Latest / ContentDocuments untouched => registry
    parity 100% for survivors, zero nulled live ids); the dangling census."""
    t_all = time.time()
    st = st or state_of(base)
    rung = rung_by_name(name)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{name}.rvt")
    log(f"\n== {name} :: {rung.label}")
    # ---- the policy gate: only sanctioned generators for a reduction rung ----
    policy = RL.law_policy().permits("maxgc", "reduction-rung")
    if not policy.allowed:                                          # pragma: no cover (sanctioned)
        raise RL.BannedGeneratorError(policy.reason, policy)
    base_cert = assert_certified(base)
    report: Dict[str, Any] = {
        "rung": name, "label": rung.label, "kind": "deletion (delete-with-content by maxgc)",
        "mechanism": ("rvt_reduce.maxgc over the arbiter's typed reference graph (every seq of "
                      "every record) + rvt.reduce.delete_elements (the certified re-blocking "
                      "deleter: records cut out of unit 0, ElemTable rows dropped, header count "
                      "patched, both streams CRCIO re-framed).  DELETION-WITH-CONTENT ONLY: every "
                      "seed is a closed constellation (referrers of removed content are IN the "
                      "seed); maxgc must pin NOTHING.  Global/Latest / ContentDocuments / "
                      "PartitionTable / History / DIT / identity streams are NEVER touched: the "
                      "deleted ids' ADocument registry entries are LEFT DANGLING (never nulled, "
                      "never dropped) and censused."),
        "law": {"statement": RL.THE_LAW, "policy": {"mechanism": "maxgc",
                                                     "purpose": "reduction-rung",
                                                     "decision": "ALLOW" if policy.allowed else "REFUSE",
                                                     "reason": policy.reason}},
        "base": {"file": _relp(base), "certification": base_cert, "lineage": BASE_LINEAGE},
        "control_to_upload_with_batch": control,
        "parent": _relp(base), "out": _relp(out),
        "description": rung.description, "tests": rung.tests,
        "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
    }
    # ---- 1. the deletion set: history-protect + maxgc pin check --------------
    seed = {int(i) for i in delete_ids}
    protected = RR._protect_history(st, seed)                        # never delete the max-episode carrier
    dropped_for_history = sorted(seed - protected)
    delete, kept, ev = RR.maxgc(st, protected)
    report["deletion_set"] = {
        "seed": len(seed), "seed_by_class": _by_class(st, seed),
        "history_protected_removed": dropped_for_history,
        "deleted": len(delete), "deleted_by_class": _by_class(st, delete),
        "kept_pinned": len(kept),
        "kept_pinned_ids": [{"id": int(k), "class": st["cls_of"].get(k, "?")} for k in sorted(kept)][:40],
        "pin_evidence": ev if kept else None,
        "deleted_ids": sorted(delete),
    }
    log(f"   seed {len(seed):,} (history-protected {len(dropped_for_history)}) -> "
        f"maxgc delete {len(delete):,}, PINNED {len(kept)}")
    if kept or dropped_for_history:
        report["FAILED_SELF_CHECK"] = (f"{len(kept)} seed member(s) PINNED by survivors / "
                                       f"{len(dropped_for_history)} history-protected -- the seed "
                                       f"is not a closed delete-with-content constellation")
        report["verdict"] = "NOT-BUILT"
        _write_report(out_dir, name, report)
        log(f"   *** {name}: {report['FAILED_SELF_CHECK']} -- NO FILE EMITTED")
        return report
    # ---- 2. emit ------------------------------------------------------------------
    t0 = time.time()
    rrep = delete_elements(base, out, delete)
    report["emit"] = {**rrep.to_json(), "out": _relp(out), "seconds": round(time.time() - t0, 1)}
    log(f"   emit: {rrep.deleted} deleted; ElemTable {rrep.elemtable_count_before:,} -> "
        f"{rrep.elemtable_count_after:,}; blocks {rrep.blocks_before} -> {rrep.blocks_after}; "
        f"{os.path.getsize(out):,} B")
    # ---- 3. THE LAW GUARD (assert_edit_free) ---------------------------------------
    t0 = time.time()
    try:
        law_rep = RL.assert_edit_free_files(base, out, before_label="ZA_deep", after_label=name)
        law_ok = bool(law_rep.ok)
        law_json = law_rep.to_json()
        law_summary = law_rep.summary()
    except RL.SurvivorEditedError as e:                              # pragma: no cover (must never fire)
        law_ok = False
        law_json = e.report.to_json() if e.report is not None else {"verdict": "SURVIVORS-EDITED"}
        law_summary = str(e)
    report["reduce_law"] = {"assert_edit_free": "PASS" if law_ok else "FAIL",
                            "summary": law_summary, "report": law_json,
                            "seconds": round(time.time() - t0, 1)}
    log(f"   LAW: {law_summary}")
    with open(os.path.join(out_dir, f"{name}_law.json"), "w") as fh:
        json.dump({"rung": name, "before": _relp(base), "after": _relp(out),
                   "assert_edit_free": "PASS" if law_ok else "FAIL",
                   "summary": law_summary, "report": law_json}, fh, indent=1, default=str)
    # ---- 4. structural + validator + coherence + identity + dangling ----------
    struct = verify_reduced(out, delete)
    vrep = validate_file(out)
    val = {"ok": bool(vrep.ok), "errors": len(vrep.errors), "warnings": len(vrep.warnings),
           "error_messages": [f"[{f.layer}] {f.where}: {f.message}"[:400] for f in vrep.errors[:6]],
           "warning_messages": [f"[{f.layer}] {f.where}: {f.message}"[:240] for f in vrep.warnings[:4]],
           "stats": {k: v for k, v in vrep.stats.items()
                     if k in ("streams", "records", "elements_decoded", "refs_checked",
                              "partition_blocks", "decode_failures")}}
    coh = famload.four_registry_census(out)
    coherence = {k: coh.get(k) for k in ("save_units", "contentdocs_entries", "contenttable_records",
                                         "familymgr_entries", "coherent_counts", "coherent_guids",
                                         "coherent")}
    coherence["familymgr_guids"] = len(coh.get("familymgr_guids") or [])
    ident = stream_identity(base, out)
    dang = adocument_dangling_census(out, delete)
    doc_after = Document.from_file(out)
    census_after = {"elements": len(doc_after.et_by_id), "file_size": os.path.getsize(out),
                    "classes_top": dict(collections.Counter(
                        doc_after.class_of(int(e)) or "?" for e in doc_after.et_by_id).most_common(24))}
    report["structural"] = {k: struct.get(k) for k in
                            ("ok", "crc_failures", "ecc_mismatches", "walker_errors", "counts_match",
                             "seq_id_sets_equal", "stamps_bad", "isize_identity_ok",
                             "deleted_still_present", "elemtable_ids_without_record", "units",
                             "blocks_unit0")}
    report["validator"] = val
    report["coherence"] = coherence
    report["stream_identity"] = ident
    report["dangling_census"] = dang
    report["registry_parity"] = {
        "survivors": ("100% by construction: Global/Latest is BYTE-IDENTICAL to ZA_deep, so every "
                      "registry leaf that indexed a surviving element still indexes it, unchanged")
        if ident["latest_byte_identical"] else "NOT PROVEN (Global/Latest differs)",
        "nulled_live_registry_ids": 0 if ident["latest_byte_identical"] else "unknown",
        "deleted_ids_registry_entries": (f"{dang['deleted_ids_with_registry_surface']} deleted id(s) still "
                                         "named by the ADocument => DANGLING (tolerated per R5/R9); "
                                         "listed in dangling_census"),
    }
    report["census_after"] = census_after
    # ---- 5. verdict ------------------------------------------------------------------
    problems: List[str] = []
    if not law_ok:
        problems.append("reduce_law assert_edit_free FAILED (survivor edited / id added)")
    if not (val["ok"] and val["errors"] == 0):
        problems.append(f"validator errors={val['errors']}")
    if not struct.get("ok"):
        problems.append("structural proof failed (verify_reduced)")
    if not coherence.get("coherent"):
        problems.append("four-registry content coherence broken")
    if not ident["only_partition_and_elemtable_differ"]:
        problems.append(f"unexpected streams differ from the base: {ident['differing_streams']}")
    if not ident["latest_byte_identical"]:
        problems.append("Global/Latest not byte-identical (a deletion must not touch it)")
    if dang["deleted_ids_still_present_in_file"]:
        problems.append("deleted ids still present in the file")
    report["problems"] = problems
    report["verdict"] = "VALID" if not problems else "NOT-CLEAN"
    if problems:
        report["FAILED_SELF_CHECK"] = "; ".join(problems)
    report["bytes"] = os.path.getsize(out)
    report["sha256"] = _sha(out)
    report["seconds"] = round(time.time() - t_all, 1)
    if endgame is not None:
        report["endgame_context"] = {
            "deletion_sets": {k: len(v) for k, v in endgame.sets.items()},
            "set_relations": endgame.set_relations(),
        }
    _write_report(out_dir, name, report)
    log(f"   validator {'VALID' if val['ok'] else 'INVALID'} (errors {val['errors']}, warnings "
        f"{val['warnings']}); structural ok={struct.get('ok')}; coherent={coherence.get('coherent')}; "
        f"only-partition+ElemTable-differ={ident['only_partition_and_elemtable_differ']}; "
        f"dangling-ADocument-surface {dang['deleted_ids_with_registry_surface']}")
    log(f"   -> {_relp(out)} {report['bytes']:,} B  VERDICT {report['verdict']}"
        f"{('  *** ' + report['FAILED_SELF_CHECK']) if problems else ''} ({report['seconds']}s)")
    for m in val.get("error_messages") or []:
        log(f"      ERROR {m}")
    return report


def _write_report(out_dir: str, name: str, rep: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))


# ===========================================================================
# 8. THE PROBES MANIFEST (bisection-first, base + control per probe)
# ===========================================================================

def write_probes_manifest(reports: Dict[str, dict], endgame: Endgame, control: dict,
                          out_dir: str = OUT_DIR, base: str = BASE) -> str:
    """probes.json for the batch gate (tools/probe_batch.py): every probe
    declares its base (ZA_deep, ITSELF in the certified ledger) and the batch
    control; upload order = bisection-first (D_all, then the singles)."""
    base_cert = certification_of(base)
    order = sorted(RUNGS, key=lambda r: r.order)
    probes = []
    for r in order:
        rep = reports.get(r.name) or {}
        law = (rep.get("reduce_law") or {})
        probes.append({
            "order": r.order, "rung": r.name,
            "file": _relp(os.path.join(out_dir, f"{r.name}.rvt")),
            "constellation_deleted": r.label,
            "base": {"file": _relp(base), "certification": base_cert},
            "derived_from": _relp(base),
            "parent_rung": "BASE",
            "passing_sibling": ("ZA_deep (the certified parent) -- with the control PASSING, a FAIL "
                                "here convicts exactly this rung's deleted constellation"),
            "the_ONE_thing_it_tests": r.tests,
            "if_PASS": r.if_pass, "if_FAIL": r.if_fail,
            "mechanism": ("maxgc delete-with-content (rvt.reduce.delete_elements); Global/Latest + "
                          "ContentDocuments + PartitionTable + identity streams BYTE-IDENTICAL to the "
                          "base; ADocument registry entries of deleted ids LEFT DANGLING (censused)"),
            "elements_deleted": {
                "count": (rep.get("deletion_set") or {}).get("deleted"),
                "by_class": (rep.get("deletion_set") or {}).get("deleted_by_class"),
            },
            "reduce_law": {"assert_edit_free": law.get("assert_edit_free"),
                           "summary": law.get("summary")},
            "byte_identity": (rep.get("stream_identity") or {}).get("only_partition_and_elemtable_differ"),
            "latest_byte_identical": (rep.get("stream_identity") or {}).get("latest_byte_identical"),
            "validator": {"ok": (rep.get("validator") or {}).get("ok"),
                          "errors": (rep.get("validator") or {}).get("errors"),
                          "warnings": (rep.get("validator") or {}).get("warnings")},
            "structural_ok": (rep.get("structural") or {}).get("ok"),
            "document_coherence": rep.get("coherence"),
            "dangling_census": {k: (rep.get("dangling_census") or {}).get(k)
                                for k in ("deleted_ids_with_registry_surface", "by_class", "by_registry_path")},
            "verdict": rep.get("verdict"),
            "bytes": rep.get("bytes"), "sha256": rep.get("sha256"),
            "control_to_upload_with_batch": control,
        })
    manifest = {
        "stream": "genesis-deletion (THE DELETION ENDGAME -- delete-with-content by the reduction law)",
        "situation": ("ORCHESTRATOR VERDICTS #18 (2026-08-04): ZA_deep (Group A's residue in place on "
                      "the certified Y9) PASSES -- 1,806 / 3,342 of the family-free base are OUR "
                      "constructors' output.  The genesis end-game names what must LEAVE the base "
                      "rather than be substituted: the 8 curtain-SYSTEM families' 232-element "
                      "coherent-removal set, the linked-model pair, the 99-element Group-A removal "
                      "queue, and the room-loop / legend / constraint-dimension content "
                      "constellations.  THIS batch retires every DELETE-REACHABLE one of them by "
                      "the reduction law, and PROVES (graph + field evidence) which ones are BLOCKED "
                      "-- and by exactly which of our own slots' inherited references."),
        "the_operation": ("Maximal garbage collection (rvt_reduce.maxgc over the arbiter's typed "
                          "reference graph, every seq of every record) + the certified deleter "
                          "(rvt.reduce.delete_elements).  DELETION-WITH-CONTENT, NEVER "
                          "neutralisation: every seed is grown to a closed constellation (the "
                          "referrers of removed content are IN the seed) and maxgc must pin NOTHING.  "
                          "Every file passes src/rvt/reduce_law.py assert_edit_free(ZA_deep, file): "
                          "0 edited survivors, 0 added ids.  Global/Latest, Global/ContentDocuments, "
                          "Global/PartitionTable and every identity stream are BYTE-IDENTICAL to "
                          "ZA_deep (only Partitions/21 + Global/ElemTable are re-emitted): survivor "
                          "registry parity is 100% by construction, NO live registry id is nulled "
                          "(P4/P6), and the deleted ids' ADocument entries are LEFT DANGLING and "
                          "censused per file (dangling ADocument ids are viewer-tolerated: R5 / R9 / "
                          "the base's own already-dangling FamilyMgr surrogate 876494)."),
        "base": {"file": _relp(base), "certification": base_cert, "lineage": BASE_LINEAGE},
        "standing_control": control,
        "controls_discipline": ("Upload EVERY batch with the certified CONTROL "
                                f"({control.get('file') if control else CONTROL_NAME} -- md5-identical "
                                "to ZA_deep).  If the CONTROL fails the round is VOID and nothing is "
                                "read from the probes.  Only with the control PASSING are the "
                                "deletion verdicts read, bisection-first."),
        "upload_order_bisection_first": [r.name for r in order],
        "reading_the_results": {
            "how": ("D_all FIRST (with the control).  D_all PASS => every delete-reachable removal "
                    "of the endgame is retired: system-family removal PROVEN, link instance gone, "
                    "constraint content gone; D_all becomes the next certified base and the blocked "
                    "constellations wait on their named constructor fixes.  D_all FAIL => read the "
                    "singles (each derives DIRECTLY from ZA_deep, none from another single): the "
                    "single that FAILS with the control + its siblings PASSING convicts exactly its "
                    "constellation."),
            "D_all FAIL & D_curtain FAIL": ("the SYSTEM-family layer removal (the endgame's ONE "
                                           "unproven mechanic) is rejected -- read the card message; "
                                           "the follow-up variants are pre-specified in this record: "
                                           "D_curtain_reconciled (same removal + the sanctioned "
                                           "registry-reconciliation purge of the 8 dangling FamilyMgr "
                                           "entries + 80 CategoryTracking rows) and the family-layer "
                                           "bisection."),
            "D_all FAIL & D_links FAIL": ("an unplaced link (symbol present, instance + copy-monitor "
                                         "companion gone) or its dangling CopyWatchModeMgr / "
                                         "RvtLinkInstTracking registries are rejected -- the link must "
                                         "leave WHOLE in one rung after the clean-header view fix, or the "
                                         "registries need reconciliation."),
            "D_all FAIL & D_content FAIL": ("removing the locked-constraint dimension + planes is "
                                           "rejected -- ConstraintDimTracking / DatumTracking "
                                           "reconciliation (the sanctioned purge) is the one-change "
                                           "follow-up (D_content_reconciled)."),
            "D_queue": ("= curtain systems + constraint content (D_all minus the link elements): "
                        "confirms / splits the reading of D_curtain vs D_content when their interaction "
                        "is in question."),
            "any FAIL with the control FAILING": "the round is VOID -- oracle / environment, not the probes",
        },
        "endgame": endgame.to_json(),
        "probes": probes,
        "verdicts_local_self_checks": {r["rung"]: r.get("verdict") for r in probes},
        "record": _relp(LEDGER_MD),
    }
    path = os.path.join(out_dir, "probes.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    return path


# ===========================================================================
# 9. THE RESIDUE-AFTER CENSUS (what D_all leaves Autodesk-authored)
# ===========================================================================

def residue_after(rvt_path: str, deleted_ids: Iterable[int]) -> dict:
    """The K4-inherited residue REMAINING in ``rvt_path`` after a deletion:
    host elements no Y / ZA rung landed and this stream did not delete,
    grouped by class -- the honest 'what is still Autodesk's' after D_all."""
    doc = Document.from_file(rvt_path)
    landed = landed_slots()
    deleted = {int(i) for i in deleted_ids}
    by_cls: Dict[str, List[int]] = collections.defaultdict(list)
    ours = 0
    for e in doc.et_by_id:
        eid = int(e)
        if eid in landed:
            ours += 1
            continue
        by_cls[doc.class_of(eid) or "?"].append(eid)
    total = len(doc.et_by_id)
    return {
        "path": _relp(rvt_path), "elements": total, "ours_landed_surviving": ours,
        "residue_elements": sum(len(v) for v in by_cls.values()),
        "residue_by_class": {k: len(v) for k, v in sorted(by_cls.items(), key=lambda kv: -len(kv[1]))},
        "deleted_by_this_stream": len(deleted),
        "note": ("residue = K4-inherited elements no Y / ZA rung landed and D_all did not delete: the "
                 "blocked constellations (link symbol, room loop, 2 type previews), Group B's M..Z "
                 "classes (theirs to substitute), the product-data / analysis buckets, and the "
                 "system-types the types stream owns"),
    }


# ===========================================================================
# 10. THE DRIVER
# ===========================================================================

def run(rungs: Sequence[str] = ("D_all", "D_curtain", "D_links", "D_content", "D_queue"),
        out_dir: str = OUT_DIR, base: str = BASE) -> Dict[str, dict]:
    """Build the endgame decision, emit the requested rungs, stage the
    control, write probes.json + the residue-after census.  Returns the
    reports."""
    t0 = time.time()
    log(f"[genesis-deletion] base {_relp(base)} (certified: {bool(certification_of(base))})")
    st = state_of(base)
    eg = build_endgame(st)
    rel = eg.set_relations()
    log(f"[endgame] sets: " + ", ".join(f"{k}={len(v)}" for k, v in eg.sets.items()))
    log(f"[endgame] D_all == union of singles: {rel['D_all_equals_union_of_singles']}; "
        f"D_queue == curtain U content: {rel['D_queue_equals_curtain_union_content']}; "
        f"blocked: link-symbol, room {len(eg.content_blocked['room_constellation']['ids'])}, "
        f"type-previews {len(eg.content_blocked['type_preview_legend_components']['ids'])}")
    control = stage_control(base, out_dir)
    log(f"[control] {control['file']} md5 {control['md5']}")
    reports: Dict[str, dict] = {}
    for name in rungs:
        reports[name] = emit_rung(name, eg.sets[name], st, endgame=eg, out_dir=out_dir,
                                  control=control, base=base)
    path = write_probes_manifest(reports, eg, control, out_dir=out_dir, base=base)
    log(f"\n[probes] {_relp(path)}")
    # residue-after census of the cumulative file
    if "D_all" in reports and reports["D_all"].get("verdict") == "VALID":
        ra = residue_after(os.path.join(out_dir, "D_all.rvt"), eg.sets["D_all"])
        with open(os.path.join(out_dir, "residue_after_D_all.json"), "w") as fh:
            json.dump(ra, fh, indent=1)
        log(f"[residue-after] {ra['residue_elements']} residue elements in D_all "
            f"({ra['ours_landed_surviving']} ours) -> {_relp(os.path.join(out_dir, 'residue_after_D_all.json'))}")
    # the endgame decision record (standalone)
    with open(os.path.join(out_dir, "endgame.json"), "w") as fh:
        json.dump(eg.to_json(), fh, indent=1, default=str)
    verdicts = {n: r.get("verdict") for n, r in reports.items()}
    log(f"\n[genesis-deletion] {len(reports)} files: {verdicts} ({round(time.time() - t0, 1)}s)")
    return reports


def demo() -> int:                                                   # pragma: no cover
    """Print the endgame decision (constellations, sets, blocked table) on
    the certified base -- no files written."""
    st = state_of()
    eg = build_endgame(st)
    print(json.dumps({
        "base": _relp(BASE),
        "sets": {k: len(v) for k, v in eg.sets.items()},
        "relations": eg.set_relations(),
        "curtain": {"count": len(eg.curtain.ids), "by_class": eg.curtain.by_class,
                    "outside_referrers": eg.curtain.outside_referrers,
                    "previews": eg.curtain.grew_from},
        "links": {"deleted": eg.links.ids, "outside_referrers": eg.links.outside_referrers,
                  "blocked_symbol": {k: eg.links_blocked[k] for k in ("element", "verdict")}
                                    | {"pinned_by_n": len(eg.links_blocked["pinned_by"])}},
        "content": {"deleted": eg.content.ids, "outside_referrers": eg.content.outside_referrers,
                    "blocked_room": eg.content_blocked["room_constellation"]["ids"],
                    "blocked_previews": eg.content_blocked["type_preview_legend_components"]["ids"]},
        "queue99": eg.queue_accounting,
        "next_queue": eg.next_queue,
    }, indent=1, default=str))
    return 0


def law_recheck(name: str, out_dir: str = OUT_DIR, base: str = BASE) -> int:  # pragma: no cover
    """Re-run the reduction-law guard on an emitted file (paste-able)."""
    path = os.path.join(out_dir, f"{name}.rvt")
    rep = RL.check_files(base, path, before_label="ZA_deep", after_label=name)
    print(rep.summary(limit=20))
    return 0 if rep.ok else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rung", action="append", default=None,
                    help="emit only these rungs (repeatable); default: all five")
    ap.add_argument("--analysis", action="store_true", help="print the endgame decision only (no files)")
    ap.add_argument("--law", default=None, metavar="RUNG", help="re-run the law guard on an emitted rung")
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    a = ap.parse_args(argv)
    if a.analysis:
        return demo()
    if a.law:
        return law_recheck(a.law, a.out)
    rungs = a.rung or [r.name for r in sorted(RUNGS, key=lambda x: x.order)]
    reps = run(rungs, out_dir=a.out)
    bad = [n for n, r in reps.items() if r.get("verdict") != "VALID"]
    return 0 if not bad else 1


__all__ = [
    "BASE", "OUT_DIR", "CONTROL_NAME", "Constellation", "Endgame", "DeletionRung", "RUNGS",
    "state_of", "landed_slots", "residue_by_class", "curtain_constellation", "links_constellation",
    "content_constellation", "queue99", "queue99_closure", "build_endgame", "next_queue",
    "adocument_dangling_census", "stream_identity", "emit_rung", "stage_control",
    "write_probes_manifest", "residue_after", "run", "assert_certified", "rung_by_name",
]

if __name__ == "__main__":
    sys.exit(main())
