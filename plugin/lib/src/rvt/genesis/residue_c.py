"""rvt.genesis.residue_c -- GENESIS-12: THE RESIDUE ENDGAME on the composed
genesis base G_ABPD (residue round 3).

Context (docs/inbox/genesis-audit.md VERDICTS #24/#26, KNOWLEDGE.md): the
composed genesis project base ``experiments/genesis/subst_k4/compose/
G_ABPD.rvt`` is viewer-CERTIFIED.  This module (a) takes the byte-ground-truth
CENSUS of what is still Autodesk's in it, (b) authors constructors for the
REACHABLE remaining classes and emits in-place rungs from G_ABPD (validator 0
errors, byte-delta-vs-G_ABPD = only the landed records, asserted), plus the
cumulative ``RC_deep``, and (c) retires the remaining STRAGGLERS by the
reduction law (``RC_zero`` = RC_deep + three lawful maxgc deletion sets via
``tools/genesis_compose.compose``), after the two enabling in-place fixes:

* the CLEAN-HEADER rung -- our six view slots' inherited seq-101
  ``ElementHeader.m_parents.m_deletion`` webs still name the ``RvtLinkSymbol``
  1250029 (in-place substitution replaced only seq-102 objects; deletion
  stream finding 1); re-emit OUR headers without that entry so the symbol
  becomes delete-reachable;
* the AREA-WIRING rung -- OUR Y5-landed ``AreaMeasureElem`` 9490 kept the
  slot's wiring to the sample's plan topology 9744
  (``m_areaSchemePlanTopologyElemId`` + header ``m_deletion``); re-emit it
  unwired so the room constellation becomes delete-reachable (deletion
  stream finding 2's exact prescription).

CENSUS FACTS this round establishes (evidence [V], measured here):

* G_ABPD carries 3,102 host elements; 422 have seq-102 object bytes
  BYTE-IDENTICAL to K4's (the pre-substitution ancestor = Autodesk's
  serialization).  411 of those were LANDED by certified rungs (almost all
  as REPRODUCED machinery with no free value); 11 were never landed.
* ``BuildingOperatingYearSchedule.m_scheduleName`` IS a free value --
  localized in the German corpus file ('Aus - 24 Stunden') -- so the 27
  year schedules REPRODUCED by residue_a2 ("no free value" -- WRONG for
  this one field) still carry Autodesk's schedule names.  RC_year lands OUR
  names (the wrapped day schedule's own GEN name).
* The 2 residue ``LegendComponent`` type previews (907404 / 1201130) carry
  ``m_oPreviewImage`` = a Revit-RENDERED 128x128 PNG cache of the
  (formerly Autodesk) type; the NULL-image form is corpus-normal (dach 2,
  rme 4 nulls).  RC_preview re-emits them with the stale Autodesk-rendered
  cache NULLED (previews regenerate; the wiring is untouched).
* Stragglers still present: RvtLinkSymbol 1250029 (+ its Dropbox-path
  identity leak), DataStorage 1382860 (vendor ES blob, zero referrers),
  AreaSchemePlanTopologies 9744 + the room constellation it contains
  (RoomElem 1004910, LevelRoomPlan 1004909, CurveElems 1004904-08,
  SketchPlane 245433).  RvtLinkInstance 1250030 + CopyWatchProperties
  1250031 are ALREADY retired (D_links c D_all, absent from G_ABPD).

THE WALLS+FAMILIES FIX (GENESIS-12 task 2; consumed by
``experiments/render/g12/build_g12_probes.py``): the corpus-lawful EMPTY
forms of the two owned-pointer slots ``rvt.famgen.loader`` NULLS on the host
family layer -- ``Family.m_oFamDimConstrMgr`` (corpus: present 831/831) and
``FamilySymbol.m_pMoveRestrictions`` (corpus: present 2710/2710) -- the ONLY
CRITICAL invariant violations (rvt.objlint, six-sample mine) separating every
audit-FAILED loaded-family file from every audit-PASSED one.  See
:func:`famdim_constr_empty`, :func:`move_restrictions_empty`,
:func:`fix_family_layer_records`.

Reproduce (repo root)::

    .venv/bin/python -m rvt.genesis.residue_c                # build everything (~2 min)
    .venv/bin/python -m rvt.genesis.residue_c --census-only  # the census json
    .venv/bin/python -m rvt.genesis.residue_c --demo         # constructor round trips

TERRITORY: this module + tests/test_residue_c.py + experiments/genesis/
subst_k4/residue_c/** + experiments/render/g12/**; everything else imported.
"""
from __future__ import annotations

import collections
import copy
import dataclasses
import glob
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if os.path.join(ROOT, "src") not in sys.path:                  # pragma: no cover
    sys.path.insert(0, os.path.join(ROOT, "src"))

LADDER = os.path.join(ROOT, "experiments", "genesis", "subst_k4")
RESIDUE_DIR = os.path.join(LADDER, "residue_c")
G_ABPD = os.path.join(LADDER, "compose", "G_ABPD.rvt")
K4 = os.path.join(ROOT, "experiments", "genesis", "triage", "K4.rvt")
LEDGER = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")

#: the six view slots whose inherited seq-101 headers still name the link
#: symbol as a deletion parent (deletion stream finding 1 + this session's
#: referrer scan on G_ABPD -- the drafting/sheet view 1457028 included; its
#: seq-102 pin was already emptied by residue_a2's ZC_browse).
VIEW_HEADER_SLOTS = (230, 69851, 245443, 1064656, 1454508, 1457028)

LINK_SYMBOL = 1250029          # RvtLinkSymbol (external sample file reference)
DATASTORAGE = 1382860          # vendor Extensible-Storage blob, zero referrers
TOPOLOGY = 9744                # AreaSchemePlanTopologies containing the room
AREA_MEASURE = 9490            # OUR AreaMeasureElem still wired to 9744

#: the room constellation the topology contains (deletion stream finding 2:
#: held together entirely by 9744; leaves atomically WITH it).
ROOM_CONSTELLATION = (TOPOLOGY, 245433, 1004904, 1004905, 1004906, 1004907,
                      1004908, 1004909, 1004910)

#: the residue type previews (deletion finding 3: a preview leaves only with
#: its type; the types are OURS now, so the previews are re-emitted in place).
PREVIEW_SLOTS = (907404, 1201130)

#: already retired before this round (D_links c D_all): stated, verified.
ALREADY_RETIRED = (1250030, 1250031)

SEQS = (101, 102, 103)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _dc(v: Any) -> Any:
    return copy.deepcopy(v)


def _relp(p: str) -> str:
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:                                          # pragma: no cover
        return p


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log(msg: str) -> None:
    print(msg, flush=True)


def ledger_certification(path: str) -> Optional[dict]:
    """The viewer-certified.json entry for ``path`` (repo-relative match)."""
    try:
        with open(LEDGER) as fh:
            led = json.load(fh)
    except OSError:                                             # pragma: no cover
        return None
    rel = _relp(os.path.abspath(path)).replace(os.sep, "/")
    for e in led.get("certified") or []:
        if e.get("file") == rel:
            return e
    return None


# ---------------------------------------------------------------------------
# THE WALLS+FAMILIES FIX -- the corpus-lawful empty forms
# ---------------------------------------------------------------------------

def famdim_constr_empty() -> dict:
    """The corpus-lawful EMPTY ``Family.m_oFamDimConstrMgr`` owned sub-object.

    Byte-for-byte the form every Autodesk host Family carries (831/831
    specimens across the six 2026 samples; identical shape) and every
    audit-PASSED loaded family carries (L1a / L_downlight / L_v2, certified):
    an empty ``FamDimConstrMgrImpl`` whose only reference is the weak
    back-pointer to the Family object itself (archive pid 2 = the record's
    root element object; 60/60 corpus specimens).  ``rvt.famgen.loader``
    writes NULL here -- null in 0/831 specimens (rvt.objlint CRITICAL)."""
    return {
        "ptr_class": "FamDimConstrMgrImpl", "pid": -1,
        "value": {
            "m_pFam": {"weakref": 2},
            "m_paramExprs": [], "m_drivenDimSegs": [],
            "m_ignoredDimValueExprs": [], "m_overconstrDimSegs": [],
            "m_fixedRefs": [], "m_redundantConstrs": [],
            "m_propagatedDrivers": [], "m_dimSegDataMap": [],
            "m_additionalParamExprs": [], "m_additionalFixedRefs": [],
        },
    }


def move_restrictions_empty() -> dict:
    """The corpus-lawful EMPTY ``FamilySymbol.m_pMoveRestrictions`` Matrix
    (0 rows x 3 cols, single-array form) -- present in 2710/2710 corpus
    FamilySymbols and in every audit-PASSED loaded symbol;
    ``rvt.famgen.loader`` writes NULL (0/2710; rvt.objlint CRITICAL)."""
    return {
        "ptr_class": "Matrix", "pid": -1,
        "value": {"m_nRows": 0, "m_ncols": 3, "m_bUseSingleArray": True,
                  "m_arr": [], "m_rows": []},
    }


def fix_family_layer_records(doc, *, family_ids: Sequence[int] = (),
                             symbol_ids: Sequence[int] = ()) -> Dict[int, dict]:
    """Return the in-place substitution records that repair the famgen.loader
    null-field defects on ``doc`` (a :class:`rvt.mutate.Document`):

    * every ``Family`` in ``family_ids`` whose ``m_oFamDimConstrMgr`` is null
      gets :func:`famdim_constr_empty`;
    * every ``FamilySymbol`` in ``symbol_ids`` whose ``m_pMoveRestrictions``
      is null gets :func:`move_restrictions_empty`.

    Shape: ``{elem_id: {102: (class_id, value)}}`` for
    ``rvt.regadd.substitute_elements(seqs=(102,))``.  Elements already
    carrying the lawful form are skipped (idempotent)."""
    out: Dict[int, dict] = {}
    for eid in family_ids:
        eid = int(eid)
        v = _dc(doc.value(eid))
        if v.get("m_oFamDimConstrMgr") is None:
            v["m_oFamDimConstrMgr"] = famdim_constr_empty()
            out[eid] = {102: (doc.record(eid).class_id, v)}
    for eid in symbol_ids:
        eid = int(eid)
        v = _dc(doc.value(eid))
        if v.get("m_pMoveRestrictions") is None:
            v["m_pMoveRestrictions"] = move_restrictions_empty()
            out[eid] = {102: (doc.record(eid).class_id, v)}
    return out


# ---------------------------------------------------------------------------
# THE CENSUS (byte ground truth: G_ABPD vs its pre-substitution ancestor K4)
# ---------------------------------------------------------------------------

#: dispositions of the 422 Autodesk-serialization-identical elements.
DISPOSITION = {
    "RC-YEAR": "value-carrying: m_scheduleName is Autodesk's (localized in dach "
               "=> free value); RC_year lands OUR name",
    "RC-PREVIEW": "stale cache: m_oPreviewImage is a Revit-rendered PNG of the "
                  "formerly-Autodesk type; RC_preview nulls it (corpus-normal form)",
    "STRAGGLER": "not in-place-able: retired by the RC_zero reduction-law deletion",
    "MACHINERY": "no free value (wiring / enum / tracker / cache apparatus): "
                 "retired by REPRODUCTION in a certified rung (nothing of ours to reject)",
    "COINCIDENT": "landed with OUR library value that equals the published fact "
                  "(NEC / ASME designations, 'Arial', built-in tokens): ours by "
                  "authorship, identical by coincidence of facts",
}

#: classes whose byte-identity is our library value coinciding with a
#: published-standard designation (Z_mepcat / ZA_deep landed them).
COINCIDENT_CLASSES = {
    "RbsWireInsulationType", "RbsWireTemperatureRatingType", "RbsWireMaterialType",
    "RbsPipeConnectionType", "RbsPipeScheduleType", "FontElem",
}


def _rung_reports() -> List[str]:
    return ([os.path.join(LADDER, f"Y{i}.json") for i in range(1, 10)]
            + [os.path.join(LADDER, "residue_a", "ZA_deep.json"),
               os.path.join(LADDER, "residue_a2", "ZC_deep.json")]
            + sorted(glob.glob(os.path.join(LADDER, "residue_b", "Z_*.json")))
            + [os.path.join(LADDER, "palette_fix", "Z_palette_v2.json")])


def landed_map(reports: Optional[Sequence[str]] = None) -> Dict[int, List[str]]:
    """{slot: [rung names that landed it]} from the certified rung reports."""
    out: Dict[int, List[str]] = {}
    for p in (reports or _rung_reports()):
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                j = json.load(fh)
        except Exception:                                       # pragma: no cover
            continue
        name = os.path.basename(p)[:-5]
        for row in j.get("landed_slots") or []:
            out.setdefault(int(row["slot"]), []).append(name)
    return out


def census(parent_path: str = G_ABPD, ancestor_path: str = K4, *,
           save: bool = True) -> dict:
    """The byte-ground-truth residue census of the composed base.

    An element is *Autodesk-serialization-identical* when its seq-102 object
    record's payload equals K4's at the same id (in-place substitution never
    moved anything, so K4 is the byte baseline of the whole ladder).  Each
    such element gets a DISPOSITION; the honest headline is the count of
    elements that still carry an Autodesk free value (RC-YEAR + RC-PREVIEW +
    STRAGGLER) -- this round's queue."""
    from ..mutate import Document
    ga = Document.from_file(parent_path)
    k4 = Document.from_file(ancestor_path)
    landed = landed_map()
    ga_ids = sorted(int(i) for i in ga.et_by_id)
    k4_ids = set(int(i) for i in k4.et_by_id)
    identical: List[dict] = []
    for e in ga_ids:
        r1, r0 = ga.idx[102].get(e), k4.idx[102].get(e)
        if r0 is None or r1 is None or r1.payload != r0.payload:
            continue
        cls = ga.class_of(e) or "?"
        if e in (LINK_SYMBOL, DATASTORAGE) or e in ROOM_CONSTELLATION:
            disp = "STRAGGLER"
        elif cls == "BuildingOperatingYearSchedule":
            disp = "RC-YEAR"
        elif e in PREVIEW_SLOTS:
            disp = "RC-PREVIEW"
        elif cls in COINCIDENT_CLASSES:
            disp = "COINCIDENT"
        else:
            disp = "MACHINERY"
        identical.append({"id": e, "class": cls, "disposition": disp,
                          "landed_by": landed.get(e, [])})
    by_disp = collections.Counter(r["disposition"] for r in identical)
    by_class = collections.Counter(r["class"] for r in identical)
    never_landed = [r for r in identical if not r["landed_by"]]
    rep = {
        "subject": _relp(parent_path),
        "ancestor_baseline": _relp(ancestor_path),
        "method": ("seq-102 payload byte-compare per host element id vs the "
                   "pre-substitution ancestor K4 (in-place ladder => same id "
                   "space; identical bytes = Autodesk's serialization)"),
        "host_elements": len(ga_ids),
        "deleted_vs_ancestor": len(k4_ids - set(ga_ids)),
        "autodesk_serialization_identical": len(identical),
        "by_disposition": dict(by_disp),
        "by_class": dict(by_class.most_common()),
        "never_landed": [{k: r[k] for k in ("id", "class", "disposition")}
                         for r in never_landed],
        "already_retired_stragglers": {
            str(e): ("ABSENT (deleted by D_links within D_all)" if e not in set(ga_ids)
                     else "STILL PRESENT (unexpected)") for e in ALREADY_RETIRED},
        "this_round_queue": {
            "RC_year_slots": by_disp.get("RC-YEAR", 0),
            "RC_preview_slots": by_disp.get("RC-PREVIEW", 0),
            "straggler_elements": by_disp.get("STRAGGLER", 0),
            "clean_header_slots": list(VIEW_HEADER_SLOTS),
            "area_wiring_slot": AREA_MEASURE,
        },
        "dispositions": DISPOSITION,
        "elements": identical,
    }
    if save:
        os.makedirs(RESIDUE_DIR, exist_ok=True)
        out = os.path.join(RESIDUE_DIR, "census.json")
        with open(out, "w") as fh:
            json.dump(rep, fh, indent=1)
        log(f"[census] {rep['autodesk_serialization_identical']} identical "
            f"({dict(by_disp)}) -> {_relp(out)}")
    return rep


# ---------------------------------------------------------------------------
# constructors (each returns (class_id, value) ready for encode_record)
# ---------------------------------------------------------------------------

def our_year_schedule(slot_value: dict, our_name: str) -> dict:
    """OUR ``BuildingOperatingYearSchedule``: the 365-day wrapper apparatus is
    the slot's own (pure machinery), the NAME is ours -- the wrapped day
    schedule's OUR name (the corpus convention: year name ~= day name;
    localized in dach => free value)."""
    v = _dc(slot_value)
    v["m_scheduleName"] = str(our_name)
    return v


def our_type_preview(slot_value: dict) -> dict:
    """OUR type-preview ``LegendComponent`` state: wiring untouched (it
    previews OUR type via ``m_componentType``), the Autodesk-rendered PNG
    cache NULLED -- the null ``m_oPreviewImage`` form is corpus-normal
    (dach 2 / rme 4 nulls measured this session); Revit regenerates type
    previews on demand."""
    v = _dc(slot_value)
    v["m_oPreviewImage"] = None
    return v


def clean_view_header(header_value: dict, drop_id: int = LINK_SYMBOL) -> dict:
    """OUR view-slot seq-101 header: the inherited ``m_parents`` web minus the
    ``drop_id`` deletion-parent entry (the clean-header rung of deletion
    finding 1 / residue-A2's not-in-place-able table)."""
    h = _dc(header_value)
    par = ((h.get("m_parents") or {}).get("value") or {})
    for key in ("m_deletion", "m_appearanceParents", "m_regeneration"):
        lst = par.get(key)
        if isinstance(lst, list) and drop_id in lst:
            par[key] = [x for x in lst if x != drop_id]
    return h


def rewired_area_measure(obj_value: dict, header_value: dict,
                         topology_id: int = TOPOLOGY) -> Tuple[dict, dict]:
    """OUR ``AreaMeasureElem`` 9490 with the sample-topology wiring removed:
    seq-102 ``m_areaSchemePlanTopologyElemId`` -> -1 and the seq-101 header
    deletion-parent entry dropped (deletion finding 2's prescribed fix), so
    the room constellation becomes delete-reachable."""
    v = _dc(obj_value)
    if int(v.get("m_areaSchemePlanTopologyElemId") or -1) == int(topology_id):
        v["m_areaSchemePlanTopologyElemId"] = -1
    h = clean_view_header(header_value, drop_id=topology_id)
    return v, h


# ---------------------------------------------------------------------------
# rung plans
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class RcPlan:
    """One in-place rung: {slot: {seq: (class_id, value)}} + bookkeeping."""
    name: str
    label: str
    records: Dict[int, Dict[int, Tuple[int, dict]]]
    ours: Dict[int, List[str]] = dataclasses.field(default_factory=dict)
    notes: List[str] = dataclasses.field(default_factory=list)

    @property
    def seqs(self) -> Tuple[int, ...]:
        return tuple(sorted({s for by in self.records.values() for s in by}))

    def merge(self, other: "RcPlan") -> None:
        for slot, by in other.records.items():
            if slot in self.records:
                self.records[slot].update(by)
            else:
                self.records[slot] = dict(by)
        self.ours.update(other.ours)
        self.notes.extend(other.notes)


def plan_year(doc) -> RcPlan:
    """RC_year: the 27 year schedules' Autodesk names -> OUR names."""
    recs: Dict[int, Dict[int, Tuple[int, dict]]] = {}
    ours: Dict[int, List[str]] = {}
    notes: List[str] = []
    for e in sorted(doc.ids_of_class("BuildingOperatingYearSchedule")):
        v = doc.value(e)
        days = sorted({d for d in (v.get("m_daySchedules") or []) if isinstance(d, int) and d > 0})
        if len(days) != 1:
            notes.append(f"WARNING year {e}: wraps {len(days)} day slots (expected 1) -- skipped")
            continue
        day_name = str((doc.value(days[0]) or {}).get("m_strName") or "")
        if not day_name:
            notes.append(f"WARNING year {e}: wrapped day {days[0]} has no name -- skipped")
            continue
        nv = our_year_schedule(v, day_name)
        if nv["m_scheduleName"] == v.get("m_scheduleName"):
            notes.append(f"year {e}: name already ours ({day_name!r}) -- landed byte-identical")
        recs[e] = {102: (doc.record(e).class_id, nv)}
        ours[e] = ["m_scheduleName"]
    return RcPlan("RC_year", "the 27 operating-year schedules named OURS "
                             "(the wrapped GEN day schedule's name)", recs, ours,
                  notes + [f"{len(recs)} year schedules; name source = OUR day-schedule "
                           f"library landed by ZC_hvac (names read from the parent)"])


def plan_preview(doc) -> RcPlan:
    """RC_preview: the 2 type-preview LegendComponents' stale caches nulled."""
    recs: Dict[int, Dict[int, Tuple[int, dict]]] = {}
    ours: Dict[int, List[str]] = {}
    for e in PREVIEW_SLOTS:
        v = doc.value(e)
        recs[e] = {102: (doc.record(e).class_id, our_type_preview(v))}
        ours[e] = ["m_oPreviewImage"]
    return RcPlan("RC_preview", "the 2 residue type previews with the "
                                "Autodesk-rendered PNG cache nulled (corpus-normal form)",
                  recs, ours,
                  ["null m_oPreviewImage is corpus-normal (dach 2 / rme 4 measured); "
                   "the wiring (m_componentType -> OUR types 600634 / 1201129) is untouched"])


def plan_hdr(doc) -> RcPlan:
    """RC_hdr: the clean-header rung (seq-101 only, six view slots)."""
    recs: Dict[int, Dict[int, Tuple[int, dict]]] = {}
    ours: Dict[int, List[str]] = {}
    for e in VIEW_HEADER_SLOTS:
        h = doc.value(e, seq=101)
        nh = clean_view_header(h)
        if json.dumps(nh, default=str) == json.dumps(h, default=str):
            raise RuntimeError(f"clean-header: slot {e} header does not name {LINK_SYMBOL}")
        recs[e] = {101: (doc.record(e, seq=101).class_id, nh)}
        ours[e] = ["m_parents.m_deletion (minus the RvtLinkSymbol entry)"]
    return RcPlan("RC_hdr", "the clean-header rung: our six view slots' seq-101 "
                            "headers re-emitted without the RvtLinkSymbol deletion parent",
                  recs, ours,
                  ["seq-101 substitution at OUR OWN slots (the certified in-place "
                   "mechanism; the objects were already ours / adopted) -- the "
                   "RvtLinkSymbol's last pins leave, enabling its lawful deletion"])


def plan_area(doc) -> RcPlan:
    """RC_area: the area-wiring rung on OUR AreaMeasureElem 9490."""
    v, h = doc.value(AREA_MEASURE), doc.value(AREA_MEASURE, seq=101)
    nv, nh = rewired_area_measure(v, h)
    recs = {AREA_MEASURE: {101: (doc.record(AREA_MEASURE, seq=101).class_id, nh),
                           102: (doc.record(AREA_MEASURE).class_id, nv)}}
    return RcPlan("RC_area", "OUR AreaMeasureElem 9490 unwired from the sample's "
                             "plan topology 9744 (obj id -> -1 + header parent dropped)",
                  recs, {AREA_MEASURE: ["m_areaSchemePlanTopologyElemId",
                                        "m_parents.m_deletion (minus 9744)"]},
                  ["the deletion stream's finding-2 fix: after this the room "
                   "constellation {9744 + room content} is one clean maxgc rung"])


def plan_deep(doc) -> RcPlan:
    """RC_deep: every group at once (the cumulative rung from G_ABPD)."""
    deep = RcPlan("RC_deep", "ALL residue-C groups in one in-place rung from "
                             "the certified G_ABPD", {}, {}, [])
    for p in (plan_year(doc), plan_preview(doc), plan_hdr(doc), plan_area(doc)):
        deep.merge(p)
    return deep


# ---------------------------------------------------------------------------
# emission + certification
# ---------------------------------------------------------------------------

def _dangling_check(doc, plans: Dict[int, Dict[int, Tuple[int, dict]]]) -> dict:
    """Every positive id our objects reference must exist in the parent."""
    live = set(int(e) for e in doc.et_by_id)
    dangle: List[dict] = []

    def walk(v, path, slot):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}", slot)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]", slot)
        elif isinstance(v, int) and v > 1_000 and v not in live and not path.endswith("m_id"):
            # heuristic pre-filter; typed check below refines
            dangle.append({"slot": slot, "path": path, "target": v})

    # typed walk where available (mirrors residue_a's gate)
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import genesis_substitute as GS                          # noqa: E402
        ted = GS.TypedEditor(decoder=doc.dec, maps=None)
        for slot, by in plans.items():
            for seq, (cid, value) in by.items():
                cls = doc.dec.class_name(cid) if seq != 101 else "ElementHeader"
                for lf in ted.leaves(value, cls):
                    t = lf.value
                    if isinstance(t, int) and t > 0 and t not in live and lf.path != "m_id":
                        dangle.append({"slot": slot, "seq": seq, "path": lf.path, "target": t})
        return {"mode": "typed", "dangling": len(dangle), "examples": dangle[:10]}
    except Exception as ex:                                      # pragma: no cover
        for slot, by in plans.items():
            for seq, (cid, value) in by.items():
                walk(value, "", slot)
        return {"mode": "heuristic", "error": repr(ex)[:120],
                "dangling": len(dangle), "examples": dangle[:10]}


def emit_rung(plan: RcPlan, parent_path: str = G_ABPD,
              out_dir: str = RESIDUE_DIR, *, doc=None) -> dict:
    """Emit ``<out_dir>/<plan.name>.rvt`` = the certified parent with the
    plan's records substituted IN PLACE, plus the certification report
    (validator, structural proof, byte-delta assertion, registry parity,
    dangling check, self-check)."""
    from .. import regadd
    from ..mutate import Document
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{plan.name}.rvt")
    t0 = time.time()
    if doc is None:
        doc = Document.from_file(parent_path)
    log(f"== {plan.name} :: {plan.label} ({len(plan.records)} slots, seqs {plan.seqs})")
    report: Dict[str, Any] = {
        "rung": plan.name, "label": plan.label, "kind": "inplace",
        "mechanism": (f"rvt.regadd.substitute_elements -- IN-PLACE, seqs {list(plan.seqs)}, "
                      "keep_row=True (ElemTable row byte-identical), Global/Latest "
                      "byte-identical; nothing added, nothing deleted"),
        "base": {"file": _relp(parent_path),
                 "certification": ledger_certification(parent_path)},
        "parent": _relp(parent_path), "out": _relp(out),
        "slots": sorted(plan.records), "seqs": list(plan.seqs),
        "ours_by_slot": {str(k): v for k, v in plan.ours.items()},
        "notes": plan.notes,
    }
    report["new_object_reference_check"] = _dangling_check(doc, plan.records)
    srep = regadd.substitute_elements(
        parent_path, out,
        {int(s): {seq: rec for seq, rec in by.items()} for s, by in plan.records.items()},
        seqs=plan.seqs, keep_row=True, verify=True, diff=True)
    diff = srep.diff or {}
    report["substitute"] = {"op": srep.op, "verdict": srep.verdict,
                            "problems": srep.problems,
                            "seqs_replaced": srep.seqs_replaced}
    report["validator"] = srep.validator
    report["structural"] = srep.structural
    # ---- byte-delta assertion: ONLY our records changed ------------------
    recs = diff.get("records") or {}
    changed_ids = {int(i) for i in recs.get("changed_ids") or []}
    added_ids = {int(i) for i in recs.get("added_ids") or []}
    removed_ids = {int(i) for i in recs.get("removed_ids") or []}
    expected_ids = {int(s) for s in plan.records}
    expected_records = sum(len(by) for by in plan.records.values())
    unexpected = sorted(changed_ids - expected_ids)
    latest_ident = bool((diff.get("latest") or {}).get("identical"))
    et_ident = bool((diff.get("elemtable") or {}).get("identical"))
    report["byte_delta"] = {
        "changed_records": recs.get("changed_count"),
        "changed_ids": sorted(changed_ids),
        "expected_slot_ids": sorted(expected_ids),
        "expected_records_max": expected_records,
        "unexpected_changed_ids": unexpected[:10],
        "added_or_removed": bool(added_ids or removed_ids),
        "landed_but_byte_identical": sorted(expected_ids - changed_ids),
        "global_latest_identical": latest_ident,
        "global_elemtable_identical": et_ident,
        "assertion_holds": (not unexpected and not added_ids and not removed_ids
                            and (recs.get("changed_count") or 0) <= expected_records
                            and latest_ident and et_ident),
        "diff_streams": (diff.get("streams") or {}).get("differing"),
    }
    ok = (srep.verdict == "VALID"
          and (srep.validator or {}).get("errors") == 0
          and (srep.structural or {}).get("ok", True)
          and report["byte_delta"]["assertion_holds"]
          and report["new_object_reference_check"]["dangling"] == 0)
    report["verdict"] = "VALID" if ok else "NOT-CLEAN"
    report["md5"] = md5_of(out)
    report["seconds"] = round(time.time() - t0, 1)
    # landed_slots in the ladder-report convention (census consumers)
    report["landed_slots"] = [{"slot": int(s), "class": doc.class_of(int(s)) or "?"}
                              for s in sorted(plan.records)]
    with open(os.path.join(out_dir, f"{plan.name}.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    log(f"   {plan.name}: {report['verdict']} validator_errors="
        f"{(srep.validator or {}).get('errors')} byte_delta_ok="
        f"{report['byte_delta']['assertion_holds']} ({report['seconds']}s)")
    return report


# ---------------------------------------------------------------------------
# RC_zero -- the straggler retirement (composed: RC_deep + lawful deletions)
# ---------------------------------------------------------------------------

def _deletion_specs(out_dir: str = RESIDUE_DIR) -> List[str]:
    """Write the three deletion-spec JSONs; return their paths."""
    os.makedirs(out_dir, exist_ok=True)
    specs = [
        {"name": "RC_del_link",
         "ids": [LINK_SYMBOL], "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["retire the RvtLinkSymbol: a genesis file links NO model; the "
                   "symbol names an external Autodesk sample file + an Autodesk "
                   "employee's Dropbox path (identity leak) -- both leave with it. "
                   "Delete-reachable only after the RC_hdr clean-header rung."]},
        {"name": "RC_del_datastorage",
         "ids": [DATASTORAGE], "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["retire the vendor DataStorage blob: an Extensible-Storage entity "
                   "this project's decoder does not read; zero referrers (leaf)."]},
        {"name": "RC_del_room",
         "ids": sorted(ROOM_CONSTELLATION), "policy": "maxgc", "purpose": "genesis-base",
         "notes": ["retire the sample-placed room constellation atomically with its "
                   "containing plan topology 9744 (deletion finding 2); "
                   "delete-reachable only after the RC_area wiring rung."]},
    ]
    paths = []
    for s in specs:
        p = os.path.join(out_dir, f"{s['name']}.spec.json")
        with open(p, "w") as fh:
            json.dump(s, fh, indent=1)
        paths.append(p)
    return paths


def emit_zero(rc_deep_path: str, out_dir: str = RESIDUE_DIR, *,
              base_path: str = G_ABPD) -> dict:
    """``RC_zero.rvt`` = compose(base=G_ABPD, rung=RC_deep-delta, the three
    straggler deletion sets) in ONE deterministic build whose declared base
    is the certified G_ABPD -- the composer precedent (G_ABPD itself was
    built this way from ZC_deep)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import genesis_compose as GC                                 # noqa: E402
    out = os.path.join(out_dir, "RC_zero.rvt")
    spec_paths = _deletion_specs(out_dir)
    rung = GC.RungSpec.from_rung_file(rc_deep_path, base_path, name="RC_deep",
                                      group="C",
                                      report_file=os.path.join(out_dir, "RC_deep.json"))
    deletions = [GC.DeletionSpec.from_json(p) for p in spec_paths]
    crep = GC.compose(base_path, [rung], out, deletions=deletions,
                      manifest_path=os.path.join(out_dir, "RC_zero.manifest.json"),
                      on_overlap="refuse", verify=True,
                      label="RC_zero (residue-C deep + straggler retirement)")
    # ---- post assertions --------------------------------------------------
    from ..mutate import Document
    z = Document.from_file(out)
    ids = set(int(e) for e in z.et_by_id)
    gone = sorted(set([LINK_SYMBOL, DATASTORAGE]) | set(ROOM_CONSTELLATION))
    still = [e for e in gone if e in ids]
    rep = {
        "out": _relp(out), "md5": md5_of(out),
        "composer_verdict": crep.verdict, "composer_problems": crep.problems,
        "deletion_specs": [_relp(p) for p in spec_paths],
        "stragglers_expected_gone": gone,
        "stragglers_still_present": still,
        "host_elements_after": len(ids),
        "ok": (not still) and crep.verdict == "COMPOSED-VALID",
    }
    with open(os.path.join(out_dir, "RC_zero.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    log(f"   RC_zero: composer={crep.verdict} stragglers_still_present={still} "
        f"elements={len(ids)}")
    return rep


# ---------------------------------------------------------------------------
# the batch (control + probes.json)
# ---------------------------------------------------------------------------

def write_batch(reports: Dict[str, dict], zero_rep: Optional[dict],
                out_dir: str = RESIDUE_DIR) -> str:
    cert = ledger_certification(G_ABPD)
    ctrl = os.path.join(out_dir, "CTRL_G_ABPD_base.rvt")
    if not os.path.exists(ctrl):
        shutil.copyfile(G_ABPD, ctrl)
    base_block = {"file": _relp(G_ABPD), "certification": cert}
    probes = []
    order = ["RC_zero", "RC_deep", "RC_year", "RC_preview", "RC_hdr", "RC_area"]
    tests = {
        "RC_zero": ("THE ENDGAME CANDIDATE: RC_deep's in-place layer + the three "
                    "lawful maxgc deletion sets (link symbol, vendor DataStorage, "
                    "room constellation) composed directly from certified G_ABPD -- "
                    "the deepest genesis base yet: zero never-landed Autodesk "
                    "elements remain."),
        "RC_deep": ("ALL residue-C groups in one in-place rung: our year-schedule "
                    "names, nulled preview caches, clean view headers, unwired "
                    "area measure."),
        "RC_year": "OUR names on the 27 operating-year schedules (free value, dach-proven).",
        "RC_preview": "the 2 type previews with the Autodesk-rendered PNG cache nulled.",
        "RC_hdr": "the clean-header rung alone (seq-101 on our six view slots).",
        "RC_area": "the area-wiring rung alone (9490 unwired from topology 9744).",
    }
    for name in order:
        if name == "RC_zero":
            if not zero_rep:
                continue
            entry = {
                "order": len(probes) + 1, "rung": name,
                "file": _relp(os.path.join(out_dir, "RC_zero.rvt")),
                "base": base_block, "derived_from": _relp(G_ABPD),
                "kind": "probe",
                "mechanism": ("tools/genesis_compose.py compose: in-place layer first "
                              "(zero registration motion), then the reduce-law-governed "
                              "maxgc deletions, one deterministic build from the "
                              "certified base"),
                "the_ONE_thing_it_tests": tests[name],
                "deleted": zero_rep.get("stragglers_expected_gone"),
                "if_PASS": ("the stragglers are retired lawfully and the residue-C "
                            "layer loads: the element-layer genesis endgame is "
                            "COMPLETE (only the two counsel corpora + own-save "
                            "container work remain)"),
                "if_FAIL": ("read RC_deep: RC_deep PASS + RC_zero FAIL convicts the "
                            "deletion layer (read the three specs' evidence blocks); "
                            "RC_deep FAIL names the in-place layer -- read the four "
                            "singles"),
                "md5": zero_rep.get("md5"),
            }
        else:
            r = reports.get(name)
            if not r:
                continue
            entry = {
                "order": len(probes) + 1, "rung": name,
                "file": _relp(os.path.join(out_dir, f"{name}.rvt")),
                "base": base_block, "derived_from": _relp(G_ABPD),
                "kind": "probe",
                "mechanism": r.get("mechanism"),
                "the_ONE_thing_it_tests": tests[name],
                "if_PASS": "this layer is clean; a deeper failure lies elsewhere",
                "if_FAIL": "this single names the rejected group exactly (parent certified)",
                "md5": r.get("md5"),
            }
        probes.append(entry)
    man = {
        "stream": "genesis-12 residue-C (THE RESIDUE ENDGAME on the composed base G_ABPD)",
        "situation": ("G_ABPD is viewer-certified (VERDICTS #24). The byte census "
                      "against ancestor K4 leaves 422 Autodesk-serialization-identical "
                      "elements: 27 value-carrying year schedules + 2 stale type-preview "
                      "caches (both reached IN PLACE here), 11 straggler elements "
                      "(deleted lawfully here), and machinery/coincident classes already "
                      "retired by certified rungs. RC_zero is the endgame candidate."),
        "base": base_block,
        "standing_control": {
            "file": _relp(ctrl), "copied_from": _relp(G_ABPD), "md5": md5_of(ctrl),
            "note": ("byte-identical to the certified G_ABPD; read FIRST -- a failing "
                     "control voids the round"),
            "certification": cert,
        },
        "upload_order_bisection_first": order,
        "probes": probes,
        "not_needed_any_more": {
            "RvtLinkInstance 1250030 + CopyWatchProperties 1250031":
                "already retired (D_links c D_all; verified ABSENT from G_ABPD)",
        },
    }
    p = os.path.join(out_dir, "probes.json")
    with open(p, "w") as fh:
        json.dump(man, fh, indent=1)
    log(f"[batch] control {_relp(ctrl)} + probes.json ({len(probes)} probes)")
    return p


# ---------------------------------------------------------------------------
# drivers
# ---------------------------------------------------------------------------

def build_all(parent_path: str = G_ABPD, out_dir: str = RESIDUE_DIR) -> dict:
    from ..mutate import Document
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    cen = census(parent_path, save=True)
    doc = Document.from_file(parent_path)
    reports: Dict[str, dict] = {}
    for plan in (plan_year(doc), plan_preview(doc), plan_hdr(doc), plan_area(doc),
                 plan_deep(doc)):
        reports[plan.name] = emit_rung(plan, parent_path, out_dir, doc=doc)
    zero = None
    if reports.get("RC_deep", {}).get("verdict") == "VALID":
        zero = emit_zero(os.path.join(out_dir, "RC_deep.rvt"), out_dir,
                         base_path=parent_path)
    write_batch(reports, zero, out_dir)
    ok = (all(r.get("verdict") == "VALID" for r in reports.values())
          and (zero or {}).get("ok"))
    log(f"[build_all] {'OK' if ok else 'PROBLEMS'} in {time.time()-t0:.0f}s")
    return {"census": {k: cen[k] for k in ("autodesk_serialization_identical",
                                           "by_disposition")},
            "reports": {k: r.get("verdict") for k, r in reports.items()},
            "zero": (zero or {}).get("ok"), "ok": ok}


def demo() -> int:
    """Constructor round-trips against the live parent (no file written)."""
    from ..mutate import Document
    from ..encode import encode_record
    import struct
    doc = Document.from_file(G_ABPD)
    n = ok = 0
    for plan in (plan_year(doc), plan_preview(doc), plan_hdr(doc), plan_area(doc)):
        for slot, by in plan.records.items():
            for seq, (cid, value) in by.items():
                n += 1
                b = encode_record(seq, int(slot), None, int(cid), value)
                off = 8 if seq == 101 else 12               # id [+stamp] then psize
                psize = struct.unpack_from("<I", b, off)[0]
                body = b[off + 4 + 2: off + 4 + psize]      # u16 class + body[psize-2]
                dec = doc.dec.decode_record(int(cid), body)
                b2 = encode_record(seq, int(slot), None, int(cid), dec.value)
                good = bool(dec.clean and b2 == b)
                ok += good
                if not good:
                    print(f"  ROUND-TRIP FAIL slot {slot} seq {seq} clean={dec.clean}")
    print(f"demo: {ok}/{n} constructed records encode->decode->encode byte-exact")
    return 0 if ok == n else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--census-only", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args(argv)
    if args.demo:
        return demo()
    if args.census_only:
        census(save=True)
        return 0
    rep = build_all()
    return 0 if rep["ok"] else 2


if __name__ == "__main__":                                       # pragma: no cover
    sys.exit(main())
