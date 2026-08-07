"""reduce_law.py -- THE REDUCTION LAW, folded into checkable code.

THE LAW (K1 autopsy, docs/writer/k1-autopsy.md sec.4; KNOWLEDGE.md "THE REDUCTION
LAW"; viewer-CONFIRMED by the K1a_editfree PASS of ORCHESTRATOR VERDICTS #17):

    A referrer of removed content is either DELETED WITH the content or LEFT
    BYTE-IDENTICAL.  It is never "neutralised" (null id / dropped struct /
    pruned map) into a byte-state no viewer-PASSED file exhibits.

K1 (= R5 minus the placed model) broke the law: ``rvt.manipulate``'s
neutralise pre-pass EDITED 22 surviving referrers (a registry-indexed default
FamilySymbol orphaned m_familyId -> -1 with its Family deleted, surrogates
nulled, a stair symbol un-hosted, schedule grid-intersection structs
dropped, view state maps pruned) and the file CRASHED the reader -- silently,
because the validator and the ElemTable read K1 as 6,540 clean rows.  Only a
record-BYTE diff sees an edited survivor.  This module IS that diff, as a
guard, plus the LAW as a policy that every reduction generator and the
substitution engine call before they emit.

The five clauses (:data:`CLAUSES`):

  1. FAMILY/TYPE LAYER IS ATOMIC -- Family + FamilySymbol + FamilySurrogate +
     FamSymSurrogate + StairsTriserSymbol + m_famId children + instances are
     removed TOGETHER (the R9 / K3-K4 pattern) or not at all.  Never null a
     symbol's m_familyId / m_hostId or a surrogate's m_elemId while the
     symbol survives -- least of all a symbol the ADocument indexes as a
     category default.
  2. NEVER DROP STRUCTURED ENTRIES FROM A SURVIVOR'S ARRAYS -- a schedule's
     m_visGridIntPntArr, a plan-topology's m_rooms / segments, connector /
     ref entries: the containing view/topology is deleted with its content,
     or the content is kept.  manipulate's "drop the struct that mentions a
     target" rule is BANNED for genesis output.
  3. VIEW STATE MAPS GO WITH THE VIEW -- a model view (3D / section /
     rendering / graphical schedule) whose content is being removed is
     DELETED with its Viewer / DBDrawing / Viewport companions and the sheets
     that place it (as R6 does), never un-hidden / un-overridden.
  4. WHATEVER REMAINS IS BYTE-IDENTICAL TO A VIEWER-PASSED SOURCE -- the only
     sanctioned generator of a reduced base is maximal garbage collection
     (maxgc) over the validator's own reference graph -- dangling-free by
     construction, ZERO survivor edits -- plus the four-registry document
     reconciliation (KD1) when embedded documents are removed.  A rung that
     "needs to edit a survivor" is a rung that must instead put that survivor
     in the SEED (delete it WITH its content).
  5. A BASE IS CERTIFIED BEFORE ANYTHING IS BUILT ON IT (tools/probe_batch.py
     enforces base + control per batch); and "the empty project that KEEPS
     the sample's model-referencing view constellation" is not
     delete-reachable -- those views leave with the model (R9 / K4's shape).

Public surface
--------------
* :func:`element_diff` -- the k1_autopsy record-byte instrument (seq
  101/102/103 framed-record identity), removed / added / modified survivors.
* :func:`assert_edit_free` -- THE GUARD.  Raises :class:`SurvivorEditedError`
  on any edited survivor (or added id) of a reduction; returns the
  :class:`EditFreeReport` otherwise.  :func:`check_reduction` is the
  non-raising form.  ``assert_edit_free_files`` / ``check_files`` load the
  two documents from ``.rvt`` paths.
* :func:`classify_survivor_edit` -- names the LAW CLAUSE an edited survivor
  breaks (its class group + edit signature: nulled id leaves, dropped
  structured entries, pruned view maps) so a rejection is diagnostic.
* :func:`check_substitution` / :func:`assert_substitution` -- the IN-PLACE
  law the substitution engine (rvt.regadd.substitute_element[s]) asserts: only
  the landed slots' records may differ (object-only mode = seq 102 alone),
  nothing added or removed.  :class:`InPlaceLawError` on violation.
* :class:`ReductionLaw` / :func:`law_policy` / :func:`guard_generator` -- the
  policy: which generator MECHANISMS are sanctioned for which PURPOSE.  The
  neutralise mechanism is REFUSED for any genesis-base / reduction-rung
  purpose (allowed only for research probes and genuine user modification).
* :func:`deletion_with_content_seed` -- the sanctioned replacement for the
  neutralise pre-pass: the referrers of the content to remove, returned as ids
  to ADD to the maxgc seed (delete them WITH the content -- the K1v pattern).
* :func:`vindicated_by` -- the K3/K4 BYTE-VINDICATION technique: an edited
  survivor whose exact after-state exists in a viewer-PASSED document is
  reader-legal without a viewer round.  Opt-in (``vindication_sources``).

This module READS documents (``rvt.mutate.Document``) and mutates nothing.
Territory: this file + tests/test_reduce_law.py.  Diffs that wire the guard
into tools/genesis_triage.py and rvt/reduce.py live in
docs/inbox/genesis-integrate.md (not applied here).
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

SEQS = (101, 102, 103)
INVALID_ID = -1

# ===========================================================================
# THE LAW AS DATA
# ===========================================================================

THE_LAW = (
    "A referrer of removed content is either DELETED WITH the content or LEFT "
    "BYTE-IDENTICAL; it is never 'neutralised' (null id / dropped struct / "
    "pruned map) into a byte-state no viewer-PASSED file exhibits.  The only "
    "sanctioned generator of a reduced base is maximal garbage collection over "
    "the validator's own reference graph (+ the four-registry reconciliation "
    "when embedded documents leave); a rung that 'needs to edit a survivor' "
    "must instead put that survivor in the seed."
)


@dataclass(frozen=True)
class LawClause:
    number: int
    slug: str
    title: str
    rule: str
    #: element classes whose EDIT belongs to this clause (empirical: K1 groups)
    classes: frozenset = frozenset()
    #: which K1 autopsy edit-group established it
    k1_group: str = ""
    #: the certified alternative to the banned edit
    instead: str = ""


CLAUSES: Dict[int, LawClause] = {
    1: LawClause(
        1, "family-type-layer-atomic", "The family/type layer is atomic",
        "Family + FamilySymbol + FamilySurrogate + FamSymSurrogate + "
        "StairsTriserSymbol + m_famId children + instances are removed "
        "TOGETHER (R9 / K3-K4 pattern) or not at all; never null a symbol's "
        "m_familyId / m_hostId or a surrogate's m_elemId while the symbol "
        "survives -- least of all a symbol the ADocument indexes as a "
        "category default (SymbolIdMgr.m_defCatSymIds).",
        frozenset({"Family", "FamilySymbol", "FamilySurrogate",
                   "FamSymSurrogate", "StairsTriserSymbol"}),
        "G4_orphaning",
        "seed the whole family/type unit (family_layer / _own_fixpoint) into "
        "maxgc, or keep every member; the surrogates and symbol leave WITH "
        "the family"),
    2: LawClause(
        2, "no-dropped-struct-entries",
        "Never drop structured entries from a survivor's arrays",
        "A schedule's m_visGridIntPntArr, a plan-topology's m_rooms / "
        "segments, connector / ref entries: the containing view/topology "
        "is DELETED with its content, or the content is kept.  The neutralise "
        "rule 'a structured list entry that mentions a target is DROPPED' is "
        "banned for genesis output (it also dropped references to STILL-"
        "PRESENT grids and their m_pDoc weakrefs on K1).",
        frozenset({"DBViewGraphSchedColumn", "LevelRoomPlan",
                   "AreaSchemePlanTopologies", "PlanTopology",
                   "AllPlanTopologies", "InteriorElevArrow"}),
        "G3_schedule + G5_topology",
        "delete the schedule / topology / arrow together with the content "
        "it depicts (Revit REGENERATES the schedule's intersection table; "
        "it never carries a pruned one)",
    ),
    3: LawClause(
        3, "view-state-maps-go-with-view", "View state maps go with the view",
        "A model view (3D / section / rendering / graphical schedule) whose "
        "content is being removed is DELETED with its Viewer / DBDrawing / "
        "Viewport companions and the sheets that place it, exactly as R6 does "
        "-- not un-hidden / un-overridden (m_oHiddenElementsViewSettings, "
        "m_oAdHocOverrides, m_parents webs stay byte-identical or leave).",
        frozenset({"DBView3d", "DBViewSection", "DBViewRendering",
                   "DBViewPlan", "DBViewCeilingPlan", "DBViewElevation",
                   "DBViewDetail", "DBViewLegend", "DBViewSheet",
                   "DBViewGraphSched", "DBViewSchedule"}),
        "G2_viewmaps",
        "seed the view (and its companions + placing sheets) into maxgc "
        "with the content it depicts",
    ),
    4: LawClause(
        4, "survivors-byte-identical",
        "Whatever remains is byte-identical to a viewer-PASSED source",
        "The only sanctioned reduction generator is maxgc over the "
        "validator's reference graph (dangling-free, ZERO survivor edits) plus "
        "the four-registry document reconciliation (KD1) when embedded "
        "documents leave.  Any other surviving record must equal, byte for "
        "byte, its state in the certified parent -- or be BYTE-VINDICATED "
        "by a viewer-PASSED file carrying that exact state (K3/K4 technique).",
        frozenset(),           # the catch-all: every survivor class
        "G1_sheets + everything ungrouped",
        "seed the referrer for deletion with its content, or leave it "
        "byte-identical",
    ),
    5: LawClause(
        5, "base-certified-first", "A base is certified before it is built on",
        "Every emitted rung derives from a viewer-CERTIFIED file "
        "(docs/coverage/viewer-certified.json 'certified'; enforced per batch "
        "by tools/probe_batch.py with >= 1 certified control), and the "
        "sample's model-referencing view constellation is NOT delete-"
        "reachable (its model views are pinned by viewports on the surviving "
        "sheets): the certified shape of 'empty' is R9's / K4's -- those "
        "views leave with the model.",
        frozenset(), "K1v_delete_referrers (analytic)",
        "certify the base first (probe_batch gate); build the empty project "
        "the R9/K4 way",
    ),
}

#: element-class -> clause lookup (clause 4 is the default for any other class)
CLASS_CLAUSE: Dict[str, int] = {c: n for n, cl in CLAUSES.items() for c in cl.classes}

#: THE SANCTIONED GENERATORS of reduced / genesis output (mechanism -> why)
SANCTIONED_GENERATORS: Dict[str, str] = {
    "maxgc": ("maximal garbage collection over the validator's reference "
              "graph (rvt.reduce.delete_elements over an rvt_reduce.maxgc seed): "
              "only elements no survivor references are deleted; survivors are "
              "byte-identical BY CONSTRUCTION (the certified ladder R5..R10)"),
    "registry-reconciliation": (
        "the schema-typed ADocument purge of EXACTLY the deleted ids "
        "(genesis_triage.purge_ids_from_latest / AdocGraphEditor): registry "
        "rows keyed by deleted ids dropped, positional slots nulled -- "
        "Revit's own deletion semantics; touches Global/Latest ONLY (K3, KD1)"),
    "unit-removal-reconciled": (
        "removing embedded content documents with the FOUR-registry "
        "document reconciliation (ContentTable / ContentDocuments / "
        "FamilyMgr / units -- rvt.reduce_v2.remove_units_v2): K4, KD1 PASS"),
    "in-place-substitution": (
        "rvt.regadd.substitute_element[s] object-only (seq 102) mode: zero "
        "registration motion -- same id / ElemTable row / record position / "
        "registry slots; Global/Latest + Global/ElemTable byte-identical to "
        "the parent (Y1..Y9, Y_cat PASS)"),
    "control-copy": (
        "a byte-identical copy of a certified file (the batch CTRL_* "
        "control): nothing changes"),
}

#: THE BANNED MECHANISMS for genesis-base / reduction-rung output.  Each is a
#: rvt.manipulate._neutralise rule (M2/M3-certified for genuine USER edits,
#: never validated for reduction referrers -- K1 met the reader with all
#: three at once).
BANNED_MECHANISMS: Dict[str, str] = {
    "neutralise-referrers": (
        "the K1 pre-pass (genesis_triage.neutralise_referrers / "
        "manipulate.delete_element cascade with neutralise_referrers=True): "
        "edits every survivor field naming a to-be-removed id -- produced "
        "K1's 22 unvindicated edited survivors and the CRASH"),
    "neutralise-scalar-null": (
        "manipulate._neutralise rule 1: scalar id field -> -1 (orphans a "
        "surviving FamilySymbol / surrogate / riser symbol / arrow: clause 1)"),
    "neutralise-list-remove": (
        "manipulate._neutralise rule 2: bare id removed from a list "
        "(hidden-element lists, m_parents webs of a KEPT model view: clause 3)"),
    "neutralise-struct-drop": (
        "manipulate._neutralise rule 3: 'a structured entry inside a list that "
        "mentions a target anywhere -> the WHOLE entry is dropped' (schedule "
        "grid-intersection structs, plan-topology segments: clause 2)"),
}

#: PURPOSES a generator may run under, and whether a banned mechanism may
#: emit for it.  A reduction rung / genesis base / substitution base is a
#: file MEANT TO BE CERTIFIED and built upon -- the law is absolute there.  A
#: research probe (the autopsy bisection ladder) manufactures the banned state
#: ON PURPOSE to isolate its effect -- allowed, but the file may never be a
#: base.  Genuine user modification (M2/M3 acceptance) is not a reduction.
PURPOSE_POLICY: Dict[str, str] = {
    "genesis-base": "REFUSE",
    "reduction-rung": "REFUSE",
    "substitution-base": "REFUSE",
    "candidate-base": "REFUSE",
    "research-probe": "ALLOW-NOTED",
    "user-modify": "ALLOW",
    "diagnostic": "ALLOW-NOTED",
}


# ===========================================================================
# EXCEPTIONS
# ===========================================================================

class LawViolation(Exception):
    """Base class: the reduction law was broken (carries a report)."""

    def __init__(self, message: str, report: Any = None):
        super().__init__(message)
        self.report = report


class SurvivorEditedError(LawViolation):
    """A 'reduction' edited (or added) elements: it is not edit-free."""


class InPlaceLawError(LawViolation):
    """An in-place substitution touched more than its landed slots."""


class BannedGeneratorError(LawViolation):
    """A banned mechanism was requested for a purpose the law refuses."""


# ===========================================================================
# THE RECORD-BYTE INSTRUMENT (k1_autopsy.element_diff, byte-strict)
# ===========================================================================

def _payload_sha(payload: bytes) -> str:
    return hashlib.sha1(payload).hexdigest()


def record_signature(rec: Any, seq: int = 0) -> Optional[tuple]:
    """The BYTE IDENTITY of one framed partition record.

    ``rec`` is an ``rvt.objects.Record`` (elem_id, stamp, class_id,
    body_size, payload, trailer_ok).  Two records with equal signatures are
    byte-identical on disk (the framing = id + [stamp] + psize + u16 class +
    payload + psize repeat is fully determined by these fields).  ``None``
    (record absent) signs as ``None`` so present/absent compares unequal.
    The stamp is included: a re-encoded record with a stale stamp is NOT the
    same record.
    """
    if rec is None:
        return None
    return (seq, int(rec.class_id), int(rec.stamp), int(rec.body_size),
            _payload_sha(rec.payload), bool(getattr(rec, "trailer_ok", True)))


def _all_ids(doc, host_only: bool = False) -> Set[int]:
    if host_only:
        return set(getattr(doc, "et_by_id", {}) or set())
    return set(doc.idx[101]) | set(doc.idx[102]) | set(doc.idx[103])


@dataclass
class ElementDiff:
    """Record-level difference between two documents (before -> after)."""
    removed: Set[int]
    added: Set[int]
    modified: Dict[int, List[int]]     # surviving id -> seqs whose record bytes differ
    common: int                        # ids present in both

    @property
    def survivors_edited(self) -> int:
        return len(self.modified)

    def to_json(self) -> dict:
        return {"removed": len(self.removed), "added": len(self.added),
                "common": self.common,
                "survivors_modified": len(self.modified),
                "modified_seq_hist": dict(Counter(s for ss in self.modified.values() for s in ss))}


def element_diff(before, after, *, host_only: bool = False) -> ElementDiff:
    """Compare two loaded documents (``rvt.mutate.Document``) record-by-record
    over all three seqs -- THE k1_autopsy instrument, byte-strict.

    ``removed`` = ids only in ``before``; ``added`` = ids only in ``after``;
    ``modified`` = ids present in BOTH whose framed record bytes differ in
    at least one seq (a REDUCTION must leave every one of these EMPTY: the
    survivor-byte-identity law).  ``host_only`` restricts the universe to
    the host document (Global/ElemTable ids); the default walks every save
    unit, so untouched embedded documents are proven byte-identical too.
    """
    ida = _all_ids(before, host_only)
    idb = _all_ids(after, host_only)
    modified: Dict[int, List[int]] = {}
    for eid in ida & idb:
        seqs = [s for s in SEQS
                if record_signature(before.idx[s].get(eid), s)
                != record_signature(after.idx[s].get(eid), s)]
        if seqs:
            modified[eid] = seqs
    return ElementDiff(removed=ida - idb, added=idb - ida,
                       modified=modified, common=len(ida & idb))


# ===========================================================================
# EDIT CLASSIFICATION (which clause did the edit break?)
# ===========================================================================

def _flat(x, pre: str = "") -> Dict[str, object]:
    out: Dict[str, object] = {}
    if isinstance(x, dict):
        for k, v in x.items():
            out.update(_flat(v, f"{pre}.{k}" if pre else k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out.update(_flat(v, f"{pre}[{i}]"))
    else:
        out[pre] = x
    return out


def _lens(x, pre: str = "", out: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """Length of every list in a decoded value, keyed by (index-free) path."""
    if out is None:
        out = {}
    if isinstance(x, dict):
        for k, v in x.items():
            _lens(v, f"{pre}.{k}" if pre else k, out)
    elif isinstance(x, list):
        key = re.sub(r"\[\d+\]", "[]", pre).replace(".value.", ".")
        # keep the SHORTEST length seen for a repeating path (worst shrink)
        out[key] = min(out.get(key, len(x)), len(x)) if key in out else len(x)
        for i, v in enumerate(x):
            _lens(v, f"{pre}[{i}]", out)
    return out


def _name_of(doc, eid: int) -> Optional[str]:
    try:
        v = doc.value(eid) or {}
    except Exception:                                             # pragma: no cover
        return None
    if not isinstance(v, dict):
        return None
    for f in ("m_viewName", "m_name", "m_text", "m_familyName"):
        n = v.get(f)
        if n:
            return str(n)
    return None


def _class_of(doc, eid: int) -> str:
    try:
        return doc.class_of(eid) or "?"
    except Exception:                                             # pragma: no cover
        return "?"


@dataclass
class SurvivorEdit:
    """One EDITED survivor and the law clause its edit breaks."""
    id: int
    class_name: str
    name: Optional[str]
    seqs: List[int]
    clause: int
    clause_slug: str
    k1_group: str
    bytes_before: Dict[int, int]
    bytes_after: Dict[int, int]
    nulled_id_leafs: List[str]         # decoded id-valued leaves that became -1
    dropped_entries: Dict[str, List[int]]   # list path -> [len_before, len_after]
    leaf_changes: Dict[int, int]       # seq -> count of changed decoded leaves
    vindicated_by: List[str] = dc_field(default_factory=list)
    instead: str = ""

    @property
    def vindicated(self) -> bool:
        return bool(self.vindicated_by)

    def to_json(self) -> dict:
        return dataclasses.asdict(self)

    def one_line(self) -> str:
        v = f" [VINDICATED by {','.join(self.vindicated_by)}]" if self.vindicated else ""
        sig = []
        if self.nulled_id_leafs:
            sig.append(f"nulled {len(self.nulled_id_leafs)}: {self.nulled_id_leafs[:3]}")
        if self.dropped_entries:
            drop = list(self.dropped_entries.items())[:3]
            sig.append("dropped " + ", ".join(f"{p} {a}->{b}" for p, (a, b) in drop))
        return (f"{self.id} {self.class_name}{f' {self.name!r}' if self.name else ''} "
                f"seq{self.seqs} -> CLAUSE {self.clause} ({self.clause_slug})"
                f"{v}" + (f" | {'; '.join(sig)}" if sig else ""))


def classify_survivor_edit(before, after, eid: int, seqs: Sequence[int]) -> SurvivorEdit:
    """Name the LAW CLAUSE a surviving element's edit breaks, with evidence.

    Class group first (the K1 autopsy's certified edit groups: family/type
    orphaning -> clause 1; schedule / plan-topology / attachment structs ->
    clause 2; model-view state maps -> clause 3), then the decoded edit
    SIGNATURE as corroboration: id-valued leaves that became ``-1`` (the
    neutralise scalar rule) and list paths that SHRANK (the neutralise
    remove / struct-drop rules).  Any other class is clause 4 -- the
    generic survivor-byte-identity clause.
    """
    cls = _class_of(after, eid) if eid in after.idx[102] else _class_of(before, eid)
    nulled: List[str] = []
    dropped: Dict[str, List[int]] = {}
    leaf_changes: Dict[int, int] = {}
    bb: Dict[int, int] = {}
    ba: Dict[int, int] = {}
    for s in seqs:
        rb, ra = before.idx[s].get(eid), after.idx[s].get(eid)
        bb[s] = (len(rb.payload) + 2) if rb else 0
        ba[s] = (len(ra.payload) + 2) if ra else 0
        try:
            vb = before.value(eid, s) or {}
        except Exception:
            vb = {}
        try:
            va = after.value(eid, s) or {}
        except Exception:
            va = {}
        fb, fa = _flat(vb), _flat(va)
        nch = 0
        for k in set(fb) | set(fa):
            x, y = fb.get(k, "<absent>"), fa.get(k, "<absent>")
            if x == y:
                continue
            nch += 1
            if (isinstance(x, int) and not isinstance(x, bool) and x > 0
                    and y == INVALID_ID):
                nulled.append(f"seq{s}:{k}")
        leaf_changes[s] = nch
        lb, la = _lens(vb), _lens(va)
        for p, n in lb.items():
            m = la.get(p, 0)
            if m < n:
                dropped[f"seq{s}:{p}"] = [n, m]
    n_clause = CLASS_CLAUSE.get(cls)
    if n_clause is None:
        # signature-driven fallback for classes outside the K1 groups
        obj_struct_drop = any(not p.split(":", 1)[1].startswith("m_parents")
                              for p in dropped if p.startswith("seq102"))
        if obj_struct_drop:
            n_clause = 2
        elif cls.startswith("DBView") and ("m_oHiddenElementsViewSettings" in " ".join(dropped)
                                           or "m_oAdHocOverrides" in " ".join(dropped)):
            n_clause = 3
        else:
            n_clause = 4
    cl = CLAUSES[n_clause]
    return SurvivorEdit(
        id=int(eid), class_name=cls, name=_name_of(after, eid) or _name_of(before, eid),
        seqs=list(seqs), clause=n_clause, clause_slug=cl.slug, k1_group=cl.k1_group,
        bytes_before=bb, bytes_after=ba, nulled_id_leafs=sorted(nulled),
        dropped_entries=dropped, leaf_changes=leaf_changes, instead=cl.instead)


# ===========================================================================
# BYTE-VINDICATION (the K3/K4 technique)
# ===========================================================================

def vindicated_by(after, eid: int, sources: Sequence[Any]) -> List[str]:
    """Names of the certified ``sources`` (loaded Documents; may carry a
    ``.name`` / ``.project`` attribute) in which element ``eid`` exists with
    EVERY seq record byte-identical to its state in ``after`` -- proof the
    edited state is reader-legal without a viewer round (how K1's sheet edit
    was retired: sheet 1457028 is byte-identical in the PASSING K3/K4)."""
    out = []
    sig_after = tuple(record_signature(after.idx[s].get(eid), s) for s in SEQS)
    for src in sources or ():
        if src is None:
            continue
        if all(record_signature(src.idx[s].get(eid), s) == sig_after[i]
               for i, s in enumerate(SEQS)):
            nm = getattr(src, "name", None) or getattr(src, "project", None) or "certified-source"
            out.append(str(nm))
    return out


# ===========================================================================
# THE GUARD
# ===========================================================================

@dataclass
class EditFreeReport:
    """Verdict of :func:`check_reduction` / :func:`assert_edit_free`."""
    ok: bool
    verdict: str                        # EDIT-FREE | SURVIVORS-EDITED | IDS-ADDED
    removed: int
    added: List[int]
    common: int
    survivors_edited: List[SurvivorEdit] = dc_field(default_factory=list)
    clause_counts: Dict[int, int] = dc_field(default_factory=dict)
    vindicated: int = 0
    before_label: str = "before"
    after_label: str = "after"

    def to_json(self) -> dict:
        return {"ok": self.ok, "verdict": self.verdict, "removed": self.removed,
                "added": len(self.added), "common": self.common,
                "survivors_edited": len(self.survivors_edited),
                "vindicated": self.vindicated,
                "clause_counts": self.clause_counts,
                "edits": [e.to_json() for e in self.survivors_edited]}

    def summary(self, limit: int = 12) -> str:
        head = (f"[{self.verdict}] {self.after_label} vs {self.before_label}: "
                f"removed {self.removed:,}, added {len(self.added):,}, common "
                f"{self.common:,}, SURVIVORS EDITED {len(self.survivors_edited)} "
                f"(vindicated {self.vindicated})")
        if not self.survivors_edited:
            return head
        cc = ", ".join(f"clause{k}={v}" for k, v in sorted(self.clause_counts.items()))
        lines = [head, f"  clauses: {cc}"]
        for e in self.survivors_edited[:limit]:
            lines.append("   - " + e.one_line())
        if len(self.survivors_edited) > limit:
            lines.append(f"   ... {len(self.survivors_edited) - limit} more")
        return "\n".join(lines)


def check_reduction(before, after, *, allow_added: bool = False,
                    vindication_sources: Sequence[Any] = (),
                    host_only: bool = False,
                    before_label: str = "before", after_label: str = "after") -> EditFreeReport:
    """NON-RAISING law check of a reduction ``before -> after``.

    A reduction is EDIT-FREE iff no id was added (a reduction never adds)
    and every surviving id's records are byte-identical.  Each edited
    survivor is classified into the clause it breaks; edits whose exact
    after-state exists in one of ``vindication_sources`` (loaded, viewer-
    PASSED documents) are marked VINDICATED and do not fail the check (the
    K3/K4 technique; empty by default = strict).
    """
    d = element_diff(before, after, host_only=host_only)
    edits: List[SurvivorEdit] = []
    for eid in sorted(d.modified):
        e = classify_survivor_edit(before, after, eid, d.modified[eid])
        if vindication_sources:
            e.vindicated_by = vindicated_by(after, eid, vindication_sources)
        edits.append(e)
    unvindicated = [e for e in edits if not e.vindicated]
    added = sorted(d.added)
    counts = dict(Counter(e.clause for e in unvindicated))
    if unvindicated:
        verdict = "SURVIVORS-EDITED"
        ok = False
    elif added and not allow_added:
        verdict = "IDS-ADDED"
        ok = False
    else:
        verdict = "EDIT-FREE"
        ok = True
    return EditFreeReport(ok=ok, verdict=verdict, removed=len(d.removed), added=added,
                          common=d.common, survivors_edited=edits, clause_counts=counts,
                          vindicated=sum(1 for e in edits if e.vindicated),
                          before_label=before_label, after_label=after_label)


def assert_edit_free(before, after, **kw) -> EditFreeReport:
    """THE GUARD: verify a reduction left every survivor BYTE-IDENTICAL.

    Raises :class:`SurvivorEditedError` (carrying the :class:`EditFreeReport`,
    every edited survivor classified by law clause) if ANY survivor's
    record bytes differ between ``before`` and ``after`` (seq 101/102/103,
    the k1_autopsy element_diff method), or if ids were added.  Returns the
    report when the reduction is edit-free.  Keyword args: see
    :func:`check_reduction` (``allow_added``, ``vindication_sources``,
    ``host_only``, labels).

    This is the mechanical form of the whole law's fourth clause: a rung
    that 'needs to edit a survivor' must instead put that survivor in the
    seed (:func:`deletion_with_content_seed`).
    """
    rep = check_reduction(before, after, **kw)
    if not rep.ok:
        raise SurvivorEditedError(
            f"REDUCTION LAW VIOLATED ({rep.verdict}): "
            f"{len([e for e in rep.survivors_edited if not e.vindicated])} unvindicated "
            f"edited survivor(s), {len(rep.added)} added id(s).\n" + rep.summary(), rep)
    return rep


def _load(path_or_doc):
    if isinstance(path_or_doc, str):
        from .mutate import Document
        d = Document.from_file(path_or_doc)
        return d
    return path_or_doc


def check_files(before_path: str, after_path: str, **kw) -> EditFreeReport:
    """:func:`check_reduction` over two ``.rvt`` paths."""
    b, a = _load(before_path), _load(after_path)
    kw.setdefault("before_label", str(getattr(b, "project", "before")))
    kw.setdefault("after_label", str(getattr(a, "project", "after")))
    return check_reduction(b, a, **kw)


def assert_edit_free_files(before_path: str, after_path: str, **kw) -> EditFreeReport:
    """:func:`assert_edit_free` over two ``.rvt`` paths (loads Documents)."""
    b, a = _load(before_path), _load(after_path)
    kw.setdefault("before_label", str(getattr(b, "project", "before")))
    kw.setdefault("after_label", str(getattr(a, "project", "after")))
    return assert_edit_free(b, a, **kw)


# ===========================================================================
# THE IN-PLACE SUBSTITUTION LAW (the engine's checkable policy)
# ===========================================================================

@dataclass
class SubstitutionReport:
    """Verdict of :func:`check_substitution`: ONLY the landed slots' records
    may differ (default object-only: seq 102), nothing added or removed."""
    ok: bool
    landed: int
    changed: List[int]
    unchanged_landed: List[int]          # landed but byte-identical (allowed)
    stray_changed: List[int]             # changed but NOT a landed slot
    seq_violations: Dict[int, List[int]] # id -> changed seqs outside allow_seqs
    added: List[int]
    removed: List[int]
    problems: List[str] = dc_field(default_factory=list)

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def check_substitution(before, after, landed_ids: Iterable[int], *,
                       allow_seqs: Sequence[int] = (102,),
                       allow_add_remove: bool = False,
                       host_only: bool = False) -> SubstitutionReport:
    """The IN-PLACE law: an in-place substitution (rvt.regadd.substitute_
    element[s]) changes ONLY the records of its landed slots, ONLY in the
    ``allow_seqs`` (object-only mode = seq 102 alone; pass ``(101,102,103)``
    for full-record rungs), adds and removes NOTHING (zero registration
    motion => Global/ElemTable + Global/Latest byte-identical, which the
    engine asserts stream-side).  A landed slot MAY be byte-identical (our
    constructor reproduced the sample's own object -- Y5's empty trackers).
    """
    d = element_diff(before, after, host_only=host_only)
    landed = {int(i) for i in landed_ids}
    changed = sorted(d.modified)
    stray = sorted(set(changed) - landed)
    seq_bad: Dict[int, List[int]] = {}
    allow = set(allow_seqs)
    for eid, seqs in d.modified.items():
        bad = [s for s in seqs if s not in allow]
        if bad:
            seq_bad[eid] = bad
    problems: List[str] = []
    if stray:
        problems.append(f"{len(stray)} record(s) changed beyond the landed slots: {stray[:8]}")
    if seq_bad:
        problems.append(f"{len(seq_bad)} slot(s) changed outside seqs {sorted(allow)}: "
                        f"{list(seq_bad.items())[:5]}")
    if (d.added or d.removed) and not allow_add_remove:
        problems.append(f"registration motion: added {len(d.added)} / removed "
                        f"{len(d.removed)} ids (in-place = zero motion)")
    return SubstitutionReport(
        ok=not problems, landed=len(landed), changed=changed,
        unchanged_landed=sorted(landed - set(changed) - d.removed),
        stray_changed=stray, seq_violations=seq_bad,
        added=sorted(d.added), removed=sorted(d.removed), problems=problems)


def assert_substitution(before, after, landed_ids: Iterable[int], **kw) -> SubstitutionReport:
    """Raising form of :func:`check_substitution` (:class:`InPlaceLawError`)."""
    rep = check_substitution(before, after, landed_ids, **kw)
    if not rep.ok:
        raise InPlaceLawError("IN-PLACE SUBSTITUTION LAW VIOLATED: " + "; ".join(rep.problems), rep)
    return rep


# ===========================================================================
# THE POLICY (generators call this BEFORE emitting)
# ===========================================================================

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    mechanism: str
    purpose: str
    reason: str

    def __bool__(self) -> bool:                                # noqa: D105
        return self.allowed


class ReductionLaw:
    """The reduction law as a queryable policy object.

    ``permits(mechanism, purpose)`` -> :class:`PolicyDecision`;
    ``check_generator(mechanism, purpose)`` raises
    :class:`BannedGeneratorError` when a banned mechanism (the neutralise
    pre-pass and its three rewrite rules) is requested for a purpose whose
    output is meant to be certified / built upon (genesis-base,
    reduction-rung, substitution-base, candidate-base).  Sanctioned
    mechanisms (maxgc, registry reconciliation, unit removal, in-place
    substitution, control copy) are allowed for every purpose.  Unknown
    mechanisms are refused for base purposes (undeclared machinery is not
    lineage) and noted otherwise.
    """

    statement = THE_LAW
    clauses = CLAUSES
    sanctioned = SANCTIONED_GENERATORS
    banned = BANNED_MECHANISMS
    purposes = PURPOSE_POLICY

    def clause(self, n: int) -> LawClause:
        return CLAUSES[n]

    def permits(self, mechanism: str, purpose: str = "genesis-base") -> PolicyDecision:
        mech = str(mechanism).strip().lower()
        purp = str(purpose).strip().lower()
        pol = PURPOSE_POLICY.get(purp)
        if pol is None:
            return PolicyDecision(False, mech, purp,
                                  f"unknown purpose {purp!r}; known: {sorted(PURPOSE_POLICY)}")
        if mech in SANCTIONED_GENERATORS:
            return PolicyDecision(True, mech, purp, "sanctioned generator: " + SANCTIONED_GENERATORS[mech])
        if mech in BANNED_MECHANISMS:
            if pol == "REFUSE":
                return PolicyDecision(
                    False, mech, purp,
                    f"BANNED for {purp!r}: {BANNED_MECHANISMS[mech]}.  THE LAW: {THE_LAW}  "
                    f"Instead: delete the referrers WITH their content "
                    f"(deletion_with_content_seed) so every survivor stays byte-identical.")
            note = ("research probe: the file manufactures the banned state on purpose "
                    "and may NEVER be certified as / declared to be a base"
                    if pol == "ALLOW-NOTED" else "genuine user modification (M2/M3 path)")
            return PolicyDecision(True, mech, purp,
                                  f"allowed for {purp!r} ({note}): {BANNED_MECHANISMS[mech]}")
        if pol == "REFUSE":
            return PolicyDecision(False, mech, purp,
                                  f"unknown mechanism {mech!r} for a {purp!r} emission -- "
                                  f"only {sorted(SANCTIONED_GENERATORS)} are sanctioned")
        return PolicyDecision(True, mech, purp, f"unknown mechanism {mech!r}, {purp!r}: allowed-noted")

    def check_generator(self, mechanism: str, purpose: str = "genesis-base") -> PolicyDecision:
        dec = self.permits(mechanism, purpose)
        if not dec.allowed:
            raise BannedGeneratorError(dec.reason, dec)
        return dec

    def to_json(self) -> dict:
        return {"law": THE_LAW,
                "clauses": {n: dataclasses.asdict(c) | {"classes": sorted(c.classes)}
                            for n, c in CLAUSES.items()},
                "sanctioned_generators": SANCTIONED_GENERATORS,
                "banned_mechanisms": BANNED_MECHANISMS,
                "purpose_policy": PURPOSE_POLICY}


_LAW = ReductionLaw()


def law_policy() -> ReductionLaw:
    """The singleton policy object every generator / engine consults."""
    return _LAW


def guard_generator(mechanism: str, purpose: str = "genesis-base") -> PolicyDecision:
    """Refuse a banned generator MECHANISM for ``purpose`` (raises
    :class:`BannedGeneratorError`); return the decision otherwise.

    Wire this into every emitting entry point BEFORE it writes bytes:
    ``genesis_triage.neutralise_referrers`` (mechanism
    ``"neutralise-referrers"``), ``manipulate.delete_element(...,
    neutralise_referrers=True)`` cascades, the maxgc rungs (``"maxgc"``),
    the substitution engine (``"in-place-substitution"``).  See the diffs
    in docs/inbox/genesis-integrate.md.
    """
    return _LAW.check_generator(mechanism, purpose)


# ===========================================================================
# THE SANCTIONED ALTERNATIVE: delete referrers WITH their content
# ===========================================================================

def deletion_with_content_seed(doc, targets: Iterable[int], *,
                               exclude: Iterable[int] = ()) -> Set[int]:
    """The referrer set to ADD TO A MAXGC SEED so that the referrers of
    ``targets`` are DELETED WITH the content instead of neutralised (the
    K1v_delete_referrers pattern -- Revit's own delete cascade / the R6-R9
    shape).  Whatever an outside element still pins survives UNEDITED, so
    every survivor is byte-identical to the parent.

    ``doc`` is an ``rvt.mutate.Document``; the referrer discovery is
    ``rvt.manipulate.referrers`` (the SAME instrument the banned neutralise
    pre-pass used to choose whom to edit) restricted to host-document
    elements outside ``targets`` / ``exclude``.  The caller feeds
    ``targets | this set`` (+ ownership children) into ``rvt_reduce.maxgc``.
    """
    from .manipulate import referrers
    t = {int(x) for x in targets}
    skip = t | {int(x) for x in exclude}
    host = set(getattr(doc, "et_by_id", {}) or ())
    refmap = referrers(doc, t)
    return {int(rid) for rid in refmap
            if rid not in skip and (not host or rid in host)}


# ===========================================================================
# DEMO / CLI
# ===========================================================================

def _demo() -> int:                                          # pragma: no cover
    import os
    import sys
    import time
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    gen = os.path.join(root, "experiments", "genesis")
    R5 = os.path.join(gen, "R5.rvt")
    K1 = os.path.join(gen, "triage", "K1.rvt")
    K1A = os.path.join(gen, "autopsy", "K1a_editfree.rvt")
    K3 = os.path.join(gen, "triage", "K3.rvt")
    K4 = os.path.join(gen, "triage", "K4.rvt")
    Y1 = os.path.join(gen, "subst_k4", "Y1.rvt")
    missing = [p for p in (R5, K1, K1A) if not os.path.exists(p)]
    print("THE REDUCTION LAW\n  " + THE_LAW)
    for n, c in CLAUSES.items():
        print(f"  clause {n}: {c.title}")
    if missing:
        print(f"[demo] corpus files missing, skipping the file demo: {missing}")
        return 0
    from .mutate import Document
    t0 = time.time()
    r5, k1a, k1 = Document.from_file(R5), Document.from_file(K1A), Document.from_file(K1)
    print(f"\n[loaded R5 / K1a_editfree / K1 in {time.time() - t0:.1f}s]")
    # -- the ACCEPTED recipe: edit-free
    rep = check_reduction(r5, k1a, before_label="R5", after_label="K1a_editfree")
    print("\n== K1a_editfree (R5 minus maxgc(placed model), ZERO edits) ==")
    print(rep.summary())
    # -- the REJECTED recipe: neutralise + delete
    src = []
    if os.path.exists(K3):
        d3 = Document.from_file(K3)
        d3.name = "K3"
        src.append(d3)
    if os.path.exists(K4):
        d4 = Document.from_file(K4)
        d4.name = "K4"
        src.append(d4)
    print("\n== K1 (R5 minus placed model VIA THE NEUTRALISE PRE-PASS) ==")
    try:
        assert_edit_free(r5, k1, vindication_sources=src, before_label="R5", after_label="K1")
        print("!! guard did NOT raise (unexpected)")
        rc = 1
    except SurvivorEditedError as e:
        print(str(e))
        rc = 0
    # -- the policy
    print("\n== policy ==")
    for mech, purp in (("maxgc", "genesis-base"), ("in-place-substitution", "genesis-base"),
                       ("neutralise-referrers", "genesis-base"),
                       ("neutralise-referrers", "research-probe"),
                       ("neutralise-struct-drop", "reduction-rung"),
                       ("neutralise-scalar-null", "user-modify")):
        dec = _LAW.permits(mech, purp)
        print(f"  {mech:26s} for {purp:18s} -> {'ALLOW' if dec.allowed else 'REFUSE'}: "
              f"{dec.reason[:110]}")
    # -- the in-place law
    if os.path.exists(K4) and os.path.exists(Y1):
        y1 = Document.from_file(Y1)
        srep = check_substitution(d4 if src and getattr(src[-1], "name", "") == "K4" else Document.from_file(K4),
                                  y1, {2})
        print(f"\n== in-place law K4 -> Y1 (landed slot: id 2, the pen table) ==\n"
              f"   ok={srep.ok} changed={srep.changed} unchanged_landed={srep.unchanged_landed} "
              f"stray={srep.stray_changed} added={srep.added} removed={srep.removed}")
    return rc


def main(argv=None) -> int:                                    # pragma: no cover
    import argparse
    import json as _json
    import sys
    ap = argparse.ArgumentParser(description="reduction-law guard: verify a reduction "
                                             "left every survivor byte-identical")
    ap.add_argument("before", nargs="?", help="parent .rvt")
    ap.add_argument("after", nargs="?", help="reduced .rvt")
    ap.add_argument("--vindication", action="append", default=[],
                    help="viewer-PASSED .rvt whose byte-states vindicate edits (repeatable)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--policy", action="store_true", help="print the law + policy tables")
    args = ap.parse_args(argv)
    if args.policy:
        print(_json.dumps(_LAW.to_json(), indent=1, default=str))
        return 0
    if not (args.before and args.after):
        return _demo()
    from .mutate import Document
    srcs = []
    for p in args.vindication:
        d = Document.from_file(p)
        d.name = p.rsplit("/", 1)[-1]
        srcs.append(d)
    rep = check_files(args.before, args.after, vindication_sources=srcs)
    if args.json:
        print(_json.dumps(rep.to_json(), indent=1, default=str))
    else:
        print(rep.summary(limit=60))
    return 0 if rep.ok else 2


__all__ = [
    "THE_LAW", "CLAUSES", "CLASS_CLAUSE", "LawClause",
    "SANCTIONED_GENERATORS", "BANNED_MECHANISMS", "PURPOSE_POLICY",
    "LawViolation", "SurvivorEditedError", "InPlaceLawError", "BannedGeneratorError",
    "record_signature", "element_diff", "ElementDiff",
    "SurvivorEdit", "classify_survivor_edit", "vindicated_by",
    "EditFreeReport", "check_reduction", "assert_edit_free",
    "check_files", "assert_edit_free_files",
    "SubstitutionReport", "check_substitution", "assert_substitution",
    "ReductionLaw", "PolicyDecision", "law_policy", "guard_generator",
    "deletion_with_content_seed",
]


if __name__ == "__main__":                                     # pragma: no cover
    import sys
    sys.exit(main())
