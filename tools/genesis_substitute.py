#!/usr/bin/env python
"""genesis_substitute.py -- THE SUBSTITUTION LADDER (X-rungs): the
constructive twin of the reduction ladder, and the path that cannot dead-end.

THE SITUATION (2026-08-03, docs/inbox/genesis-audit.md "ORCHESTRATOR VERDICTS"
#1..#7): every REDUCTION of Autodesk's sample skeleton LOADS in Autodesk's
own reader (R5, R9, K1, K3, K4, KD1 PASS) and every CONSTRUCTED base FAILS
(G0, G1_candidate, G1a, G1b, and even S1..S5 = G1_candidate + our settings
singletons + our full catalog) with 'Revit-DocumentCorruption: The file is
corrupt' + 'Design is empty' + an extractor crash.  The S-set tested OUR
content ON THE SUSPECT BASE and could not separate 'our singletons/catalog
are mis-shaped or mis-registered' from 'the G1 base carries an independent
defect'.  THIS TOOL ISOLATES BY BUILDING ON THE PASSING SIDE.

THE OPERATION.  Start from K1 = Autodesk's empty-project skeleton (viewer
PASSED, 6,540 elements) and REPLACE its Autodesk-authored content with OUR
constructors' output CLASS BY CLASS, cumulatively, one class(-group) per
rung.  Every rung derives from a PASSING file (K1 or the previous rung), so
the first rung the viewer REJECTS names exactly the one of OUR constructors
the reader disagrees with -- and a clean run to Xn IS the genesis base.

WHAT ONE SUBSTITUTION DOES (the operator `substitute()`), for a class C on
a passing parent P:
  1. OLD = P's element ids of class C (+ their ownership constellation).
  2. NEW = OUR constructor's records for C, allocated above P's watermark,
     WIRED to whatever the OLD elements referenced in P (their outbound
     phase / units / sun / catalog ids): our OBJECT, the document's WIRING.
  3. CORRESPONDENCE old -> new where a 1:1 role match exists (pen table ->
     our pen table; the per-tree default browser organization -> ours of the
     same tree; navigator view/viewer/viewport/drawing -> ours by role...).
     OLD ids with no correspondent are simply deleted.
  4. Every SURVIVOR referrer of an OLD id is RE-POINTED to the corresponding
     NEW id (or neutralised when there is none) through the certified
     byte-exact modify path -- discovered with the arbiter's own SCHEMA-TYPED
     ElementId decoder (NOT a byte scan: id 2, the pen table, is byte-
     mentioned by hundreds of geometry-step counters that are not ids).
  5. OUR records are appended, the OLD deleted, save-unit 0 re-blocked --
     all through the proven writer path (commit_new_elements / commit_plans).
  6. The ADocument (Global/Latest): every ElementId leaf holding an OLD id
     is REMAPPED to its NEW id IN PLACE (registry parity BY CONSTRUCTION --
     same registry, same slot/key, our id substituted); unmapped OLD ids are
     purged with Revit's own deletion semantics (positional slot -> -1,
     registry row dropped); OUR new-only records (no old correspondent) are
     REGISTERED additively.  Then the tree is re-encoded byte-exactly.
  7. PARITY IS ASSERTED, not assumed: the registry surface of every OLD id
     (the set of typed leaf paths holding it) is captured BEFORE; AFTER the
     rung the SAME normalized path set must hold the NEW id, positional
     (UniqueElementsTracking) slots must be index-identical, and NO leaf
     anywhere may hold any OLD id.  P4/P6/K6 proved these registries are
     walked at load, so parity is the whole point of the rung.
  8. CERTIFIED: tools/rvt_validate.py 0 errors (necessary, NOT sufficient),
     structural proof, four-registry document coherence, ADocument re-decode
     with zero NEW dangling ids, and the parity table -- all in <rung>.json.

RUNG PLAN (labels follow the brief; DERIVATION ORDER is the manifest's
`derived_from` chain -- the family-layer rung (the brief's X10) MUST precede
the catalog rung (the brief's X6) because embedded family documents PIN
host catalog rows (genesis-triage-a finding 4), so it is DERIVED right
after X5 and the catalog rungs derive from it):
  X1   PenWidthTableElem (the real project pen table, id 2)      -> ours
  X2   the BrowserOrganization set + the system-navigator
       constellation (+ ReconcileBrowserSettings, ConstructionSet) -> ours
  X3   StructSettingsElem + WallJoinDefaultSetting + AutoJoinTracker +
       KeynoteTable/KeynotingSystem + InitialViewSettings         -> ours
  X4   the Rbs*Settings + Rbs*Sizes tables (wire/duct/pipe/conduit/
       cable-tray), keyed onto the still-present MEP catalogs      -> ours
  X5   every remaining settings singleton / tracker with a
       constructor (the standard constellation's residue)         -> ours;
       classes WITHOUT a constructor are LISTED (residue), never
       silently kept as if they were ours
  X10  the loadable-family layer + ALL embedded documents removed
       coherently (K4's viewer-PASSED operation, families are NOT
       required); optionally re-added as OUR heads via rvt.famload
  X6   the built-in-category GStyle catalog rows                    -> OUR
       complete catalog (1:1 by (category, style-type)); X6a/X6b/X6c
       split if the wholesale substitution is too big
  X7   line/fill patterns + materials + assets                     -> ours
  X8   levels / phases / phase filters / project info / base points /
       site / units                                                -> ours
  X9   the project DBViewTypes + view constellations + annotation
       types                                                       -> ours
  Xn   the residue check: what Autodesk-authored elements remain (a
       provenance / census diff vs K1) -- if none, Xn IS genesis.
If a rung cannot be built because OUR constructor does not exist or its
registry surface is unknown, the ladder STOPS THERE honestly and names the
missing constructor -- that IS the finding.

Territory: tools/genesis_substitute.py, experiments/genesis/subst/*,
tests/test_genesis_substitute.py, docs/writer/substitution-ladder.md,
docs/inbox/genesis-substitute.md.  Every dependency (rvt.reduce /
rvt.manipulate / rvt.commit / rvt.adocument / rvt.genesis.settings /
catalog / skeleton / types, tools/rvt_reduce.py, tools/genesis_assemble.py,
tools/genesis_triage.py) is IMPORTED, never edited.  You cannot run the
Autodesk viewer from here; every rung is a probe for the orchestrator's
queue.  Python: .venv/bin/python from the repo root.

Usage:
  .venv/bin/python tools/genesis_substitute.py                 # every rung
  .venv/bin/python tools/genesis_substitute.py --only X1,X2    # some rungs
  .venv/bin/python tools/genesis_substitute.py --manifest-only
"""
from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import json
import os
import re
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import rvt_reduce as RR                                            # noqa: E402
import genesis_assemble as GA                                       # noqa: E402
from rvt import adocument as adoc                                   # noqa: E402
from rvt import manipulate as MP                                    # noqa: E402
from rvt.commit import commit_new_elements, verify_written          # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.mutate import Document                                     # noqa: E402
from rvt.reduce import delete_elements, verify_reduced              # noqa: E402
from rvt import stream_encoders as se                               # noqa: E402
from rvt.genesis import settings as ST                              # noqa: E402
from rvt.genesis import catalog as CAT                              # noqa: E402
from rvt.genesis.types import IdSource, INVALID, TypeRecord         # noqa: E402

SUBST = os.path.join(ROOT, "experiments", "genesis", "subst")
TRIAGE = os.path.join(ROOT, "experiments", "genesis", "triage")
K1 = os.path.join(TRIAGE, "K1.rvt")            # viewer PASS -- the starting base
LEDGER_MD = os.path.join(ROOT, "docs", "writer", "substitution-ladder.md")
IDENTITY = {"author": "rvt-writer", "client_app_name": "rvt-writer",
            "username": "rvt-writer"}
os.makedirs(SUBST, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


# ===========================================================================
# 1. registry-surface machinery: schema-typed ElementId leaves + parity
# ===========================================================================
#: strip the AppInfoManager array index and every list index EXCEPT the
#: positional-slot indices under UniqueElementsTracking (where the index IS
#: the compiled-in slot).  What remains identifies a REGISTRY SURFACE:
#: e.g.  '...->PenWidthTableInfo.m_penWidthTableElemId'
#:       '...->UniqueElementsTracking.m_elemIds[32]'
#:       '...->BrowserOrganizationTracking.m_currentBrOrgTypeToBrOrgMap[*].second'
_APPINFO_IDX = re.compile(r"m_appInfoArr\[\d+\]")
_ANY_IDX = re.compile(r"\[\d+\]")
_UET_IDX = re.compile(r"(UniqueElementsTracking\.m_elemIds)\[(\d+)\]")


def normalize_surface_path(path: str) -> str:
    """Normalize a typed-leaf path to a REGISTRY-SURFACE key: the AppInfo
    array index and ordinary container indices are wildcarded (row order is
    not semantic); the positional UniqueElementsTracking slot index is KEPT
    (the slot IS the identity there)."""
    keep = {}
    def _hold(m):                                   # protect UET indices
        tok = f"@UET{len(keep)}@"
        keep[tok] = f"{m.group(1)}[{m.group(2)}]"
        return tok
    p = _UET_IDX.sub(_hold, path)
    p = _APPINFO_IDX.sub("m_appInfoArr[*]", p)
    p = _ANY_IDX.sub("[*]", p)
    for tok, val in keep.items():
        p = p.replace(tok, val)
    # drop the leading root class token noise ('ADocument.') for readability
    return p


class TypedEditor:
    """Schema-typed ElementId walker/editor over ANY decoded class body --
    the ADocument tree or an element record's value dict.  Thin wrapper over
    ``genesis_assemble.AdocGraphEditor`` (the same walker that certified
    the K-ladder's ADocument purges), which types leaves by their archive
    field type (kind 0x0E + ElementId/Identifier), NOT by field name or by
    byte pattern -- so integers that are not ids (geometry-step counters,
    enum indexes, the '2' that byte-scans hit hundreds of times for the pen
    table) are never touched."""

    def __init__(self, decoder=None, maps: Optional[dict] = None):
        self.maps = maps if maps is not None else GA.load_registry_maps()
        self.ed = GA.AdocGraphEditor(decoder=decoder, maps=self.maps)

    def leaves(self, value: dict, class_name: str):
        return list(self.ed.iter_leaves(value, class_name) or [])

    def surface(self, value: dict, class_name: str,
                ids: Iterable[int]) -> Dict[int, List[Tuple[str, str]]]:
        """{id: [(raw_path, normalized_path), ...]} for every leaf whose
        value is one of ``ids`` -- the id's REGISTRY SURFACE in this body."""
        want = {int(i) for i in ids}
        out: Dict[int, List[Tuple[str, str]]] = collections.defaultdict(list)
        for lf in self.leaves(value, class_name):
            if isinstance(lf.value, int) and lf.value in want:
                out[lf.value].append((lf.path, normalize_surface_path(lf.path)))
        return {k: v for k, v in out.items()}

    def remap(self, value: dict, class_name: str,
              mapping: Dict[int, int]) -> List[dict]:
        """Rewrite every ElementId leaf whose value is a KEY of ``mapping``
        to the mapped id, IN PLACE.  Returns the edit log."""
        edits = []
        for lf in self.leaves(value, class_name):
            v = lf.value
            if isinstance(v, int) and v in mapping and mapping[v] not in (None,):
                new = int(mapping[v])
                lf.holder[lf.key] = new
                edits.append({"path": lf.path, "old": v, "new": new})
        return edits

    def purge(self, value: dict, class_name: str, live_ids: Set[int],
              label: str = "") -> dict:
        """Null/drop every ElementId leaf whose (positive) id is not live --
        Revit's own deletion semantics (positional slot -> -1, container
        row dropped).  See ``AdocGraphEditor.purge_dangling``."""
        return self.ed.purge_dangling(value, class_name, live_ids, label=label)

    def all_referenced_ids(self, value: dict, class_name: str) -> Set[int]:
        return {lf.value for lf in self.leaves(value, class_name)
                if isinstance(lf.value, int) and lf.value > 0}


#: ownership-child classes for a SUBSTITUTION's constellation growth: the
#: reduction ladder's V2_CHILD_CLASSES minus the trackers / settings
#: singletons that merely REFERENCE seeded content.  In a REDUCTION those
#: die with the content they track; in a SUBSTITUTION they must SURVIVE
#: and have their references re-pointed (X9's parity assertion caught our
#: X3 InitialViewSettings being swept away by its start-view reference).
_SUBST_EXCLUDE_CHILDREN = {
    "InitialViewSettings", "AutoJoinTracker", "GCSTracker", "HubsTracker",
    "PlanTopology", "AllPlanTopologies", "PostedWarningElem", "RegenSplitterElem",
    "SelectionFilterElement", "ScheduleInstanceBaseOnSheetsTracker",
}
SUBST_CHILD_CLASSES = set(RR.V2_CHILD_CLASSES) - _SUBST_EXCLUDE_CHILDREN


# ===========================================================================
# 2. the substitution context: everything a rung's build() may read
# ===========================================================================

class SubstContext:
    """Read-only view of the PASSING parent file a rung is derived from:
    the mutate.Document, the arbiter-typed reference graph (rvt_reduce
    ladder-v2 state), the decoded ADocument tree, the id allocator (fresh
    ids above the parent's watermark) and small lookup helpers."""

    def __init__(self, parent: str, rung: str):
        self.parent = parent
        self.rung = rung
        t0 = time.time()
        self.st = RR.build_state_v2(parent)             # typed graph + referrers
        self.doc = self.st["doc"]
        self.cls_of = self.st["cls_of"]
        self.host = self.st["host"]
        self.universe = self.st["universe"]
        self.watermark = max(int(r) for r in self.doc.et_by_id) if self.doc.et_by_id else 0
        # our ids: a readable per-rung band above the parent's watermark
        self.id_start = ((self.watermark // 100_000) + 1) * 100_000
        self.ids = IdSource(self.id_start)
        with open_rvt(parent) as f:
            self.latest_payload = f.inflate(adoc.STREAM, 0)
            self.bfi = se.decode_basic_file_info(f.logical("BasicFileInfo"))
        a = adoc.decode_latest(self.latest_payload)
        if not a.clean:
            raise RuntimeError(f"{parent}: ADocument decode not clean: {a.errors[:1]}")
        self.tree = a.value                               # the LIVE parent tree (do not edit)
        self.maps = GA.load_registry_maps()
        self.ted = TypedEditor(decoder=self.doc.dec, maps=self.maps)   # element records
        self.ted_adoc = TypedEditor(decoder=None, maps=self.maps)      # the ADocument codec
        self.build_seconds = round(time.time() - t0, 1)
        self._by_cls: Optional[Dict[str, List[int]]] = None

    # -- census helpers ---------------------------------------------------------
    def ids_of(self, *classes: str, host_only: bool = True) -> List[int]:
        if self._by_cls is None:
            m: Dict[str, List[int]] = collections.defaultdict(list)
            for e in (self.host if host_only else self.universe):
                m[self.cls_of.get(e, "?")].append(int(e))
            for v in m.values():
                v.sort()
            self._by_cls = dict(m)
        out: List[int] = []
        for c in classes:
            out += self._by_cls.get(c, [])
        return sorted(out)

    def one(self, cls_name: str) -> Optional[int]:
        ids = self.ids_of(cls_name)
        return ids[0] if ids else None

    def value(self, eid: int, seq: int = 102) -> dict:
        return self.doc.value(int(eid), seq) or {}

    def name_of(self, eid: int) -> str:
        v = self.value(eid) or {}
        si = v.get("m_symbolInfo")
        if isinstance(si, dict):
            n = (si.get("value") or {}).get("m_name") or si.get("m_name")
            if n:
                return str(n)
        for k in ("m_name", "m_viewName", "m_strName"):
            if v.get(k):
                return str(v.get(k))
        return ""

    def outbound(self, eid: int) -> Set[int]:
        return set(self.st["graph"].get(int(eid), set()))

    def inbound(self, eid: int) -> Set[int]:
        return set(self.st["referrers"].get(int(eid), set()))

    def _child_candidates(self) -> Set[int]:
        cands = getattr(self, "_cand_cache", None)
        if cands is None:
            cands = {e for e in self.host if self.cls_of.get(e) in SUBST_CHILD_CLASSES}
            self._cand_cache = cands
        return cands

    def own_fixpoint(self, seed: Set[int]) -> Set[int]:
        """Grow a seed by its ownership constellation: companion-class
        elements REFERENCING a seeded element (a view's viewer / viewport /
        drawing / sun / extents / sketch planes, a symbol's sub-category
        rows), view-OWNED content (m_ownerDBViewId), and ElemTable-owned
        rows, to a fixpoint.  Uses :data:`SUBST_CHILD_CLASSES` (the
        substitution variant: trackers / settings singletons that only
        REFERENCE the seed are NOT pulled in -- they survive and get their
        references re-pointed instead)."""
        seed = {int(x) for x in seed}
        graph = self.st["graph"]
        cands = self._child_candidates()
        while True:
            add: Set[int] = set()
            for e in cands - seed:
                if graph.get(e, set()) & seed:
                    add.add(e)
            add |= {e for e, ov in self.st["owner_view"].items()
                    if ov in seed and e not in seed and e in self.host}
            try:
                add |= {c for c in MP.owned_children(self.doc, seed) if c in self.host}
            except Exception:
                pass
            add -= seed
            if not add:
                break
            seed |= add
        return seed

    def field(self, eid: int, path: str, default=None):
        """Read a decoded field of element ``eid`` by dotted path."""
        try:
            return MP.get_path(self.value(eid), path)
        except Exception:
            return default


# ===========================================================================
# 3. what a rung's build() returns
# ===========================================================================

@dataclasses.dataclass
class SubstBuild:
    """The result of a rung's build(): the OLD elements to remove, OUR NEW
    records, the correspondence, and the ours-only records that need a NEW
    registry registration."""
    old_ids: List[int]
    records: List[Any]                        # TypeRecord-like (encode / as_new_element / roundtrip)
    corr: Dict[int, int] = dataclasses.field(default_factory=dict)   # old -> new
    new_only: List[Any] = dataclasses.field(default_factory=list)   # records needing NEW registry entries
    notes: List[str] = dataclasses.field(default_factory=list)
    #: classes whose Autodesk elements are DELIBERATELY LEFT in place at
    #: this rung because no our-constructor exists (the honest residue)
    residue: Dict[str, str] = dataclasses.field(default_factory=dict)
    #: extra info the rung wants in its report
    info: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Rung:
    name: str
    label: str                                # the class(es) substituted
    parent: str                               # rung name of the parent ('K1' or 'X3'...)
    description: str
    tests: str
    if_pass: str
    if_fail: str
    build: Callable[["SubstContext"], SubstBuild]
    #: rungs that only DELETE (X10's family layer) still assert coherence
    kind: str = "substitute"


# ===========================================================================
# 4. ADocument registry work
# ===========================================================================

def _bodies(tree: dict) -> List[Tuple[str, dict]]:
    """Every registry body of the ADocument tree: all AppInfo slots + the
    five named top-level holders (the purge machinery's proven enumeration).
    Kept for the per-body purge; the WHOLE-tree walk is used for surfaces."""
    bodies: List[Tuple[str, dict]] = list(GA._appinfo_bodies(tree))
    for fld, cls_name in (("m_oContentTable", "ContentTable"),
                          ("m_oNobleSecondaryData", "NOBLE_SecondaryDataStorage"),
                          ("m_pStyleSettings", "StyleSettings"),
                          ("m_pSteelModelInfo", "SteelModelInfo"),
                          ("m_oExServicesUsed", "ExServicesUsed")):
        holder = tree.get(fld)
        body = holder.get("value") if isinstance(holder, dict) else None
        if isinstance(body, dict):
            bodies.append((cls_name, body))
    return bodies


def adoc_surface(ted: TypedEditor, tree: dict, ids: Iterable[int]) -> Dict[int, List[str]]:
    """{id: sorted [normalized surface paths]} over the WHOLE ADocument tree
    (14.8k typed leaves on K1) -- the registry surface of each id."""
    want = {int(i) for i in ids}
    out: Dict[int, List[str]] = collections.defaultdict(list)
    for lf in ted.leaves(tree, "ADocument"):
        if isinstance(lf.value, int) and lf.value in want:
            out[lf.value].append(normalize_surface_path(lf.path))
    return {k: sorted(v) for k, v in out.items()}


def _uet_slots(surface: Dict[int, List[str]]) -> Dict[int, List[str]]:
    """The positional UniqueElementsTracking slots inside a surface map."""
    return {i: sorted(p for p in ps if "UniqueElementsTracking.m_elemIds[" in p)
            for i, ps in surface.items()
            if any("UniqueElementsTracking.m_elemIds[" in p for p in ps)}


def register_new_only(tree: dict, records: List[Any], maps: dict) -> dict:
    """ADDITIVELY register OUR ours-only records (those with no old
    correspondent) into the document's registries.  BrowserOrganization is
    handled here directly (append to the tracking set + a system-family-
    names key) because ``settings.apply_adoc_registry``'s browser handler
    REBUILDS the per-tree default map from the passed records -- which,
    given only OUR non-default house schemes, would erase the defaults this
    rung just re-pointed.  Every other class goes through
    ``apply_adoc_registry``, whose remaining handlers only fill EMPTY slots
    or APPEND rows (never clobbering an existing entry)."""
    rep: Dict[str, Any] = {"applied": collections.Counter(), "skipped": []}
    browser = [r for r in records if r.class_name == "BrowserOrganization"]
    rest = [r for r in records if r.class_name != "BrowserOrganization"]
    if browser:
        body = ST._appinfo_body(tree, "BrowserOrganizationTracking")
        if body is None:
            rep["skipped"].append("browser: BrowserOrganizationTracking absent")
        else:
            ids = body.setdefault("m_elemIdSet", [])
            for r in browser:
                if int(r.elem_id) not in ids:
                    ids.append(int(r.elem_id))
                    rep["applied"]["browser-set"] += 1
                if r.refs.get("default"):
                    # a NEW default with no old correspondent: extend the map
                    t = int(r.refs.get("org_type", 0))
                    m = body.setdefault("m_currentBrOrgTypeToBrOrgMap", [])
                    if not any(int(p.get("first", -9)) == t for p in m if isinstance(p, dict)):
                        m.append({"first": t, "second": int(r.elem_id)})
                        rep["applied"]["browser-default"] += 1
        # AppInfoSystemFamiliesNames rows for the new organizations
        sfn = ST._appinfo_body(tree, "AppInfoSystemFamiliesNames")
        if sfn is not None:
            rows = sfn.setdefault("m_idMap", [])
            key = int(sfn.get("m_newKey") or len(rows))
            for r in browser:
                rows.append({"first": key, "second": {"m_elementIds": [int(r.elem_id)]}})
                key += 1
                rep["applied"]["sysfam"] += 1
            sfn["m_newKey"] = key
            sfn["m_bValid"] = True
    if rest:
        sub = ST.apply_adoc_registry(tree, rest, maps=maps)
        for k, v in (sub.get("applied") or {}).items():
            rep["applied"][k] += v
        rep["skipped"] += sub.get("skipped") or []
    rep["applied"] = dict(rep["applied"])
    return rep


# ===========================================================================
# 5. the substitution operator
# ===========================================================================

def _record_ok(r) -> Tuple[bool, dict]:
    rep = r.roundtrip()
    ok = rep.get("ok")
    if ok is None:                                   # SkelElement report shape
        ok = all(v.get("clean") and v.get("byte_exact")
                 for k, v in rep.items() if k != "ok" and isinstance(v, dict))
    return bool(ok), rep


def _encode_record(r) -> Dict[int, bytes]:
    """{seq: framed record bytes} for a TypeRecord OR a SkelElement (the
    skeleton stream's record shape) -- the same three (seq, class, object)
    records, framed by rvt.encode (stamps auto-computed)."""
    if hasattr(r, "encode"):
        return r.encode()
    from rvt.encode import encode_record
    return {seq: encode_record(seq, r.elem_id, None, cid, o)
            for seq, cid, o in r.records()}


def _validate(path: str) -> dict:
    return RR._run_validator(path)


def _census(path: str) -> dict:
    """Class census + the four-registry document-coherence tuple (the
    genesis-triage census -- imported logic, kept identical)."""
    import genesis_triage as GT
    return GT.census(path)


def _decode_latest(path: str):
    with open_rvt(path) as f:
        payload = f.inflate(adoc.STREAM, 0)
    a = adoc.decode_latest(payload)
    if not a.clean:
        raise RuntimeError(f"{path}: ADocument decode not clean")
    return a, payload


def substitute(rung: Rung, parent_path: str, out_dir: str = SUBST, *,
               keep_intermediates: bool = False) -> dict:
    """Emit ``<out_dir>/<rung.name>.rvt`` = ``parent_path`` with the class
    substituted per ``rung.build``; write the certification report
    ``<rung.name>.json``.  Returns the report dict (also written)."""
    t_all = time.time()
    out = os.path.join(out_dir, f"{rung.name}.rvt")
    t_add = os.path.join(out_dir, f".{rung.name}.a_appended.rvt")
    t_del = os.path.join(out_dir, f".{rung.name}.b_repointed.rvt")
    log(f"\n== {rung.name} :: {rung.label}")
    log(f"   parent {_relp(parent_path)}")

    # ---- 1. context + build ------------------------------------------------
    ctx = SubstContext(parent_path, rung.name)
    log(f"   context: {len(ctx.host):,} host elements, watermark {ctx.watermark:,}, "
        f"our ids from {ctx.id_start:,} ({ctx.build_seconds}s)")
    sb = rung.build(ctx)
    old_ids = sorted({int(i) for i in sb.old_ids})
    old_set = set(old_ids)
    records = sorted(sb.records, key=lambda r: r.elem_id)
    new_ids = [int(r.elem_id) for r in records]
    corr = {int(k): int(v) for k, v in sb.corr.items()
            if v not in (None, INVALID) and int(k) in old_set}
    unmapped = sorted(old_set - set(corr))
    by_class_old = collections.Counter(ctx.cls_of.get(i, "?") for i in old_ids)
    by_class_new = collections.Counter(r.class_name for r in records)
    log(f"   OLD {len(old_ids)} elements {dict(by_class_old.most_common(6))}")
    log(f"   NEW {len(records)} records {dict(by_class_new.most_common(6))}; "
        f"correspondence {len(corr)} pairs; unmapped-deleted {len(unmapped)}; "
        f"new-only-registered {len(sb.new_only)}")

    report: Dict[str, Any] = {
        "rung": rung.name, "label": rung.label, "kind": rung.kind,
        "parent": _relp(parent_path), "parent_rung": rung.parent,
        "out": _relp(out),
        "description": rung.description, "tests": rung.tests,
        "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
        "old": {"count": len(old_ids), "ids": old_ids,
                "by_class": dict(by_class_old.most_common())},
        "new": {"count": len(records), "id_range": [new_ids[0], new_ids[-1]] if new_ids else [],
                "by_class": dict(by_class_new.most_common())},
        "correspondence": [{"old": o, "new": n, "old_class": ctx.cls_of.get(o, "?"),
                            "new_class": next((r.class_name for r in records
                                               if r.elem_id == n), "?")}
                           for o, n in sorted(corr.items())],
        "unmapped_old_deleted": [{"id": i, "class": ctx.cls_of.get(i, "?")} for i in unmapped],
        "new_only_registered": [{"id": r.elem_id, "class": r.class_name} for r in sb.new_only],
        "residue_left_in_place": sb.residue,
        "build_notes": sb.notes,
        "build_info": sb.info,
        "stages": [],
    }

    # ---- 2. new-record self-verification (BEFORE anything is written) -------
    bad_rt = []
    for r in records:
        ok, rep = _record_ok(r)
        if not ok:
            bad_rt.append({"id": r.elem_id, "class": r.class_name, "roundtrip": rep})
    if bad_rt:
        report["FAILED_SELF_CHECK"] = f"{len(bad_rt)} new record(s) not clean/byte-exact"
        report["record_failures"] = bad_rt[:12]
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: {len(bad_rt)} records fail round-trip -- NO FILE EMITTED")
        return report
    # new records must not reference OLD ids (they are being deleted) --
    # except through their own new ids; and every id they reference must
    # exist afterwards (parent universe minus olds, plus new ids)
    survivors_universe = (set(ctx.universe) - old_set) | set(new_ids)
    ref_bad = []
    for r in records:
        for lf in ctx.ted.leaves(r.obj, r.class_name) + ctx.ted.leaves(r.header, "ElementHeader"):
            v = lf.value
            if isinstance(v, int) and v > 0 and v != r.elem_id and v not in survivors_universe:
                ref_bad.append({"id": r.elem_id, "class": r.class_name,
                                "path": lf.path, "target": v,
                                "target_is_old": v in old_set})
    report["new_records_reference_check"] = {"dangling": len(ref_bad),
                                              "examples": ref_bad[:12]}
    if ref_bad:
        report["FAILED_SELF_CHECK"] = (f"{len(ref_bad)} reference(s) in our new records "
                                       f"do not resolve after the substitution")
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: {len(ref_bad)} unresolved refs in new records "
            f"(e.g. {ref_bad[0]}) -- NO FILE EMITTED")
        return report

    # ---- 3. registry surface BEFORE (parent's ADocument) ------------------
    surf_before = adoc_surface(ctx.ted_adoc, ctx.tree, old_set)
    uet_before = _uet_slots(surf_before)
    referenced_before = ctx.ted_adoc.all_referenced_ids(ctx.tree, "ADocument")
    dangling_before = referenced_before - set(ctx.universe)

    # ---- 4. STAGE A: append OUR records (proven commit path) -----------------
    t0 = time.time()
    recs = [{seq: b for seq, b in _encode_record(r).items()} for r in records]
    plans = [r.as_new_element().elemrec for r in records]
    guid = ctx.bfi.get("unique_document_guid") or ctx.bfi.get("central_model_identity") or ""
    crep = commit_new_elements(parent_path, t_add, recs, plans,
                               identity=dict(IDENTITY, document_guid=guid))
    ver_a = verify_written(t_add, new_ids)
    clean_new = sum(1 for s in ver_a["new_ids_found"].values()
                    for v in s.values() if v.get("clean") is not False)
    report["stages"].append({
        "stage": "A: append our records (rvt.commit.commit_new_elements)",
        "new_elements": len(records), "elemtable_after": crep.elemtable_count_after,
        "watermark_after": crep.watermark_after,
        "verify_written": {k: ver_a[k] for k in ("crc_failures", "ecc_mismatches",
                                              "walker_errors", "stamps_ok")},
        "new_records_clean": clean_new, "seconds": round(time.time() - t0, 1)})
    log(f"   A: appended {len(records)} records -> elemtable {crep.elemtable_count_after:,}; "
        f"new records clean {clean_new}")

    # ---- 5. STAGE B: re-point survivor referrers + delete OLD (manipulate) ---
    t0 = time.time()
    doc1 = Document.from_file(t_add)
    sess = MP.session(doc1)
    # typed referrer discovery: the PARENT's arbiter-typed graph (new records
    # never reference old ids -- verified above -- so the parent's referrer
    # set is exact); referrers outside the host document (embedded documents)
    # cannot be edited by the modify path and are reported.
    referrers: Set[int] = set()
    embedded_referrers = 0
    for o in old_set:
        for r in ctx.inbound(o):
            if r in old_set:
                continue
            if r in ctx.host:
                referrers.add(int(r))
            else:
                embedded_referrers += 1
    live_ids = (set(ctx.universe) | set(new_ids)) - set(unmapped)
    plans_b: list = []
    repoint_log: List[dict] = []
    repoint_errors: List[dict] = []
    for rid in sorted(referrers):
        pl = MP.ModifyPlan(kind="substitution-repoint", elem_id=rid,
                           class_name=doc1.class_of(rid))
        touched = False
        for seq in (101, 102, 103):
            rec = doc1.idx[seq].get(rid)
            if rec is None:
                continue
            try:
                val = sess.value(rid, seq)
            except Exception as e:                              # not byte-exact editable
                repoint_errors.append({"referrer": rid, "class": doc1.class_of(rid),
                                       "seq": seq, "error": repr(e)[:300]})
                continue
            cname = "ElementHeader" if seq == 101 else doc1.dec.class_name(rec.class_id)
            edits = ctx.ted.remap(val, cname, corr) if corr else []
            purged = None
            if unmapped:
                purged = ctx.ted.purge(val, cname, live_ids, label=f"{rid}/{seq}")
                if purged and not (purged["dangling"] or purged["nulled"]
                                   or purged["elements_dropped"] or purged["scalars_nulled"]):
                    purged = None
            if edits or purged:
                touched = True
                pl.record_edits.append(sess.replacement(
                    rid, seq, f"{rung.name}: re-point references to substituted "
                              f"{rung.label} ({len(edits)} remapped)"))
                repoint_log.append({"referrer": rid, "class": doc1.class_of(rid), "seq": seq,
                                    "remapped": len(edits),
                                    "example_paths": [e["path"] for e in edits[:3]],
                                    "purged": ({k: purged[k] for k in ("dangling", "nulled",
                                                                        "elements_dropped",
                                                                        "scalars_nulled")}
                                               if purged else None)})
        if touched:
            plans_b.append(pl)
    # the DELETE plan for the OLD elements (records + ElemTable rows)
    dplan = MP.DeletePlan(root_id=(old_ids[0] if old_ids else -1), cascade=True,
                          ids_to_remove=list(old_ids), dependents=[], referrer_edits=[],
                          elemtable_remove=list(old_ids))
    for did in old_ids:
        for seq in (101, 102, 103):
            if doc1.idx[seq].get(did) is not None:
                dplan.record_edits.append(MP.RecordEdit(seq, did, "remove", None,
                                                        f"{rung.name}: substituted OLD element"))
        sess.removed.add(did)
    if old_ids:
        plans_b.append(dplan)
    if repoint_errors:
        report["repoint_errors"] = repoint_errors
    rem_by_class = collections.Counter(x["class"] for x in repoint_log)
    if plans_b:
        mrep = MP.commit_plans(t_add, t_del, plans_b)
        ver_b = MP.verify_manipulated(t_del, deleted_ids=old_ids,
                                     edited_ids=sorted({x["referrer"] for x in repoint_log}))
        report["stages"].append({
            "stage": "B: re-point survivor referrers + delete OLD (rvt.manipulate.commit_plans)",
            "referrers_repointed": len({x["referrer"] for x in repoint_log}),
            "referrer_records_edited": len(repoint_log),
            "repointed_by_class": rem_by_class.most_common(20),
            "embedded_document_referrers_uneditable": embedded_referrers,
            "old_records_removed": mrep.removed_ids and len(mrep.removed_ids),
            "elemtable_before": mrep.elemtable_count_before,
            "elemtable_after": mrep.elemtable_count_after,
            "verify_manipulated": {k: ver_b.get(k) for k in ("crc_failures", "ecc_mismatches",
                                                             "walker_errors", "stamps_ok",
                                                             "deleted_ids_gone",
                                                             "isize_identity_mismatches")
                                   if k in ver_b},
            "seconds": round(time.time() - t0, 1)})
        log(f"   B: re-pointed {len({x['referrer'] for x in repoint_log})} referrer element(s) "
            f"{dict(rem_by_class.most_common(6))}; deleted {len(old_ids)} old; "
            f"embedded-doc referrers (uneditable) {embedded_referrers}")
    else:
        # nothing to change in the element layer (pure registry rung)
        import shutil
        shutil.copyfile(t_add, t_del)
        report["stages"].append({"stage": "B: (no element-layer edits needed)"})
    report["referrer_repoint"] = {
        "referrer_elements": len({x["referrer"] for x in repoint_log}),
        "record_edits": repoint_log[:60],
        "embedded_document_referrers_uneditable": embedded_referrers,
        "errors": repoint_errors,
    }
    if embedded_referrers:
        report.setdefault("warnings", []).append(
            f"{embedded_referrers} referrer(s) live INSIDE embedded documents and cannot be "
            f"edited by the host modify path -- they now dangle (a validator error will show)")

    # ---- 6. STAGE C: the ADocument -- remap / purge / register + re-encode --
    t0 = time.time()
    a_del, payload_del = _decode_latest(t_del)          # == parent's Latest (untouched so far)
    tree = json.loads(json.dumps(a_del.value))
    remap_edits = ctx.ted_adoc.remap(tree, "ADocument", corr) if corr else []
    # purge the UNMAPPED old ids only (inherited dangling refs are left alone)
    purge_totals: Counter = collections.Counter()
    purge_bodies = []
    if unmapped:
        referenced_now = ctx.ted_adoc.all_referenced_ids(tree, "ADocument")
        live = referenced_now - set(unmapped)
        for cls_name, body in _bodies(tree):
            st_p = ctx.ted_adoc.purge(body, cls_name, live, label=cls_name)
            if st_p["dangling"]:
                purge_bodies.append({k: st_p[k] for k in ("body", "dangling", "nulled",
                                                          "elements_dropped", "scalars_nulled")})
            purge_totals.update({k: st_p[k] for k in ("dangling", "nulled",
                                                       "elements_dropped", "scalars_nulled")})
        for k in ("m_ownerFamilyId", "m_ownerFamilyContainingGroupId"):
            v = tree.get(k)
            if isinstance(v, int) and v in set(unmapped):
                tree[k] = INVALID
                purge_totals["scalars_nulled"] += 1
    # register the ours-only records (no old correspondent)
    reg_rep = register_new_only(tree, list(sb.new_only), ctx.maps) if sb.new_only else \
        {"applied": {}, "skipped": []}
    new_payload = adoc.encode_latest(tree)
    back = adoc.decode_latest(new_payload)
    if not (back.clean and back.value == tree):
        report["FAILED_SELF_CHECK"] = "authored ADocument does not round-trip byte-exactly"
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: ADocument round-trip failed -- NO FILE EMITTED")
        return report
    adoc.write_with_latest(t_del, out, new_payload)
    # canonical re-block of save-unit 0 (the S-ladder / triage convention)
    tmp_rb = out + ".reblock.tmp"
    os.replace(out, tmp_rb)
    delete_elements(tmp_rb, out, [])
    os.remove(tmp_rb)
    report["stages"].append({
        "stage": "C: ADocument remap old->new / purge unmapped / register ours-only / re-encode",
        "leaves_remapped": len(remap_edits),
        "remap_examples": [{"path": normalize_surface_path(e["path"]), "old": e["old"],
                            "new": e["new"]} for e in remap_edits[:16]],
        "purge_totals": dict(purge_totals),
        "purge_bodies": purge_bodies[:20],
        "new_only_registration": reg_rep,
        "latest_payload_before": len(payload_del),
        "latest_payload_after": len(new_payload),
        "seconds": round(time.time() - t0, 1)})
    log(f"   C: ADocument leaves remapped {len(remap_edits)}; purged {dict(purge_totals)}; "
        f"registered {reg_rep.get('applied')}")

    # ---- 7. PARITY + coherence + certification -----------------------------
    t0 = time.time()
    a_out, _payload_out = _decode_latest(out)
    tree_out = a_out.value
    surf_after = adoc_surface(ctx.ted_adoc, tree_out, set(new_ids) | old_set)
    parity_rows = []
    parity_fail = 0
    for o, n in sorted(corr.items()):
        before = collections.Counter(surf_before.get(o, []))
        after = collections.Counter(surf_after.get(n, []))
        missing = list((before - after).elements())      # surfaces that lost the id
        extra = list((after - before).elements())        # (informational: n may sit elsewhere too)
        ok = not missing
        parity_rows.append({"old": o, "new": n, "class": ctx.cls_of.get(o, "?"),
                            "surface_before": sorted(before.elements()),
                            "surface_after": sorted(after.elements()),
                            "missing": missing, "extra": extra, "parity": ok})
        if not ok:
            parity_fail += 1
    # positional UniqueElementsTracking slots: exact index equality
    uet_after = _uet_slots(surf_after)
    uet_rows = []
    for o, slots in sorted(uet_before.items()):
        n = corr.get(o)
        got = uet_after.get(n, []) if n is not None else []
        uet_rows.append({"old": o, "new": n, "slot_before": slots, "slot_after": got,
                         "ok": (n is not None and slots == got)})
    uet_fail = sum(1 for r in uet_rows if not r["ok"])
    # no OLD id may survive anywhere in the document object
    old_still = {i: p for i, p in surf_after.items() if i in old_set}
    # new dangling ids created by this rung (against the OUTPUT's id universe)
    out_ids = set(Document.from_file(out).et_by_id)
    referenced_after = ctx.ted_adoc.all_referenced_ids(tree_out, "ADocument")
    with open_rvt(out) as f:
        # embedded-document ids also count as existing (they were file-wide ids)
        pass
    universe_out = set(RR.build_state_v2(out)["universe"])
    dangling_after = referenced_after - universe_out
    new_dangling = sorted(dangling_after - dangling_before)
    # keep the stored parity table bounded for large rungs: every FAILED
    # row + a sample of ok rows (the counts stay exact)
    if len(parity_rows) > 80:
        failed_rows = [r for r in parity_rows if not r["parity"]]
        ok_rows = [r for r in parity_rows if r["parity"]]
        stored_rows = failed_rows[:200] + ok_rows[:30]
        table_note = (f"{len(parity_rows)} pairs total; storing all {len(failed_rows)} "
                      f"failures + a 30-row sample of the ok pairs")
    else:
        stored_rows, table_note = parity_rows, "all pairs stored"
    report["parity"] = {
        "pairs": len(corr), "pairs_ok": len(corr) - parity_fail, "pairs_failed": parity_fail,
        "table_note": table_note,
        "table": stored_rows,
        "positional_uet_slots": uet_rows, "uet_failed": uet_fail,
        "old_ids_still_in_adocument": {str(k): v for k, v in old_still.items()},
        "adocument_dangling_before": len(dangling_before),
        "adocument_dangling_after": len(dangling_after),
        "adocument_dangling_created": new_dangling[:40],
        "seconds": round(time.time() - t0, 1)}
    log(f"   parity: {len(corr) - parity_fail}/{len(corr)} pairs ok; UET slots ok "
        f"{len(uet_rows) - uet_fail}/{len(uet_rows)}; old ids left in ADocument "
        f"{len(old_still)}; NEW dangling created {len(new_dangling)}")

    # structural + validator + census
    struct_ok = verify_reduced(out, old_ids)
    val = _validate(out)
    cen = _census(out)
    report["structural"] = {k: struct_ok.get(k) for k in ("ok", "crc_failures", "ecc_mismatches",
                                                        "counts_match", "seq_id_sets_equal",
                                                        "stamps_bad", "deleted_still_present",
                                                        "isize_identity_ok", "unit0_element_records")}
    report["structural"]["walker_errors"] = len(struct_ok.get("walker_errors") or [])
    report["validator"] = val
    report["census"] = cen
    report["coherence"] = {
        "save_units": cen.get("save_units"),
        "contentdocs_entries": cen.get("contentdocs_entries"),
        "contenttable_records": cen.get("contenttable_records"),
        "familymgr_doc_guids": cen.get("familymgr_doc_guids"),
        "coherent": (cen.get("save_units", 0) - 1 == cen.get("contentdocs_entries")
                     == cen.get("contenttable_records")),
    }
    report["bytes"] = os.path.getsize(out)
    report["seconds"] = round(time.time() - t_all, 1)
    # ---- verdict -------------------------------------------------------------
    problems = []
    if not (val.get("ok") and val.get("errors") == 0):
        problems.append(f"validator errors={val.get('errors')}")
    if not struct_ok.get("ok"):
        problems.append("structural proof failed")
    if parity_fail:
        problems.append(f"{parity_fail} registry parity failure(s)")
    if uet_fail:
        problems.append(f"{uet_fail} positional UET slot mismatch(es)")
    if old_still:
        problems.append(f"{len(old_still)} OLD id(s) still referenced by the ADocument")
    if new_dangling:
        problems.append(f"{len(new_dangling)} NEW dangling ADocument id(s)")
    if not report["coherence"]["coherent"]:
        problems.append("four-registry document coherence broken")
    if repoint_errors:
        problems.append(f"{len(repoint_errors)} referrer(s) could not be re-pointed")
    if embedded_referrers:
        problems.append(f"{embedded_referrers} embedded-document referrer(s) left dangling")
    report["problems"] = problems
    report["verdict"] = "VALID" if not problems else "NOT-CLEAN"
    if problems:
        report["FAILED_SELF_CHECK"] = "; ".join(problems)
    _write_report(out_dir, rung.name, report)
    for tmp in (t_add, t_del):
        if not keep_intermediates and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    log(f"   validator: {'VALID' if val.get('ok') else 'INVALID'} errors={val.get('errors')} "
        f"warnings={val.get('warnings')} elements={(val.get('stats') or {}).get('elements_decoded')}; "
        f"structural ok={struct_ok.get('ok')}; coherence {report['coherence']['save_units']}/"
        f"{report['coherence']['contentdocs_entries']}/{report['coherence']['contenttable_records']}")
    log(f"   -> {_relp(out)} {report['bytes']:,} B  VERDICT {report['verdict']}"
        f"{('  *** ' + report['FAILED_SELF_CHECK']) if problems else ''} ({report['seconds']}s)")
    for m in (val.get("error_messages") or [])[:4]:
        log(f"      ERROR {m}")
    return report


def _write_report(out_dir: str, name: str, rep: dict) -> None:
    with open(os.path.join(out_dir, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))


# ===========================================================================
# 6. RUNG BUILDERS
# ===========================================================================
#: BuiltInParameter of a view's associated phase (the browser 'Phase'
#: organization keys on it) -- our house browser scheme uses discipline /
#: phase / sheet-series folders (see settings.default_browser_organizations)

def _tr_id(rec) -> int:
    return int(rec.elem_id)


# ---------------------------------------------------------------------------
# X1  PenWidthTableElem (the REAL project pen table, m_famId == -1)
# ---------------------------------------------------------------------------
def build_X1(ctx: SubstContext) -> SubstBuild:
    """OLD = the project pen table (the one PenWidthTableElem with m_famId ==
    -1: element id 2 in every 2026 file; the 8 family-scoped copies belong to
    the curtain SYSTEM families and are theirs).  NEW = OUR pen table
    (settings.pen_width_table: our ISO-128-based line-weight series over our
    scale breakpoints -- 0.42 max byte-similarity to any Autodesk table).
    Registry: PenWidthTableInfo.m_penWidthTableElemId (1 leaf).  Referrers:
    NONE (K5a proved it; a byte scan is fooled by ~40 geometry-step '2's --
    the typed walk finds zero)."""
    olds = []
    for e in ctx.ids_of("PenWidthTableElem"):
        if int(ctx.value(e).get("m_famId", -1)) == -1:
            olds.append(e)
    if not olds:
        raise RuntimeError("X1: no project pen table (m_famId -1) found in the parent")
    ours = ST.pen_width_table(ids=ctx.ids)
    corr = {olds[0]: ours.elem_id}          # any further -1 tables are just deleted
    notes = [f"old project pen table id(s) {olds}; ours id {ours.elem_id}; "
             f"family-scoped copies kept ({len(ctx.ids_of('PenWidthTableElem')) - len(olds)}, "
             f"owned by the curtain SYSTEM families -> the family rung)"]
    return SubstBuild(old_ids=olds, records=[ours], corr=corr, notes=notes,
                      info={"our_scales": ours.refs.get("scales")})


# ---------------------------------------------------------------------------
# X2  the BrowserOrganization set + the system-navigator constellation
#     + ReconcileBrowserSettingsElem + ConstructionSetProject
# ---------------------------------------------------------------------------
def _navigator_wiring(ctx: SubstContext, nav_id: int) -> dict:
    """Read the OLD navigator view's outbound wiring (its phase, phase
    filter, sun settings, style overrides, and the regen edges into
    AllProjectPhases / UnitsElem / WorksetVisibilitySettings /
    MEPSystemTracker) so OUR navigator is wired to the SAME infrastructure."""
    v = ctx.value(nav_id)
    hdr = ctx.value(nav_id, 101)
    parents = (hdr.get("m_parents") or {}).get("value") or {}
    regen = [int(x) for x in (parents.get("m_regenOnly") or [])
             if isinstance(x, int) and x > 0]
    deferred = [int(x) for x in (parents.get("m_deferredParents") or [])
                if isinstance(x, int) and x > 0]

    def _pick(cls_name: str, pool: Sequence[int]) -> int:
        for x in pool:
            if ctx.cls_of.get(x) == cls_name:
                return int(x)
        return INVALID

    def _f(name: str, default=INVALID):
        val = v.get(name)
        return int(val) if isinstance(val, int) else default
    # invisible / not-silhouette GStyle overrides live on the DBView base
    inv = _f("m_invisibleStyleId")
    nsil = _f("m_notSilhouetteStyleId")
    excl = v.get("m_excludedCategories")
    if not isinstance(excl, list):
        # draw filters: the schema stores them under the display manager
        excl = []
    return {
        "phase_id": _f("m_phaseId"),
        "phase_filter_id": _f("m_phaseFilterId"),
        "sun_settings_id": _f("m_pSunAndShadowSettingsId", _f("m_sunAndShadowSettingsId")),
        "invisible_style_id": inv, "not_silhouette_style_id": nsil,
        "all_phases_id": _pick("AllProjectPhases", regen),
        "units_id": _pick("UnitsElem", regen),
        "workset_visibility_id": _pick("WorksetVisibilitySettingsElem", regen),
        "mep_system_tracker_id": _pick("MEPSystemTracker", deferred + regen),
        "excluded_categories": [int(x) for x in excl if isinstance(x, int)],
    }


def build_X2(ctx: SubstContext) -> SubstBuild:
    """OLD = every BrowserOrganization (11) + the MEP system-navigator view
    and its Viewer/Viewport/DBDrawing companions + ReconcileBrowserSettings
    Elem + ConstructionSetProject.  NEW = OUR browser scheme (the 4 REQUIRED
    per-tree 'all' defaults + our 2 house schemes) + OUR navigator
    constellation (settings.system_navigator, wired to the parent's own
    phases / units / workset-visibility / MEP tracker) + our reconcile-
    browser + construction-set singletons.
    Correspondence: default-org-of-tree-T -> our default of tree T (the four
    DBViewProject regen edges + BrowserOrganizationTracking's per-tree map
    ride on it); navigator view/viewer/viewport/drawing -> ours by role
    (DBViewInfo / DBDrawingInfo registries ride on it); the reconcile /
    construction-set singletons 1:1.  The seven non-default sample
    organizations ('not on sheets', 'Phase', 'Discipline', ...) have no
    correspondent (Autodesk's shipped browser schemes are theirs) and are
    simply deleted; OUR 2 house schemes are ours-only (appended to the
    tracking set + a system-family-names key)."""
    olds: Set[int] = set()
    corr: Dict[int, int] = {}
    notes: List[str] = []
    # ---- browser organizations ---------------------------------------------
    org_ids = ctx.ids_of("BrowserOrganization")
    old_default_by_type: Dict[int, int] = {}
    for o in org_ids:
        v = ctx.value(o)
        olds.add(o)
        if bool(v.get("m_bDefault")):
            old_default_by_type[int(v.get("m_type", 0))] = int(o)
    ours = ST.default_browser_organizations(ctx.ids, with_house_set=True)
    our_default_by_type: Dict[int, Any] = {}
    house = []
    for r in ours:
        if r.refs.get("default"):
            our_default_by_type[int(r.refs.get("org_type", 0))] = r
        else:
            house.append(r)
    for t, oid in old_default_by_type.items():
        r = our_default_by_type.get(t)
        if r is not None:
            corr[oid] = r.elem_id
    unmatched_types = sorted(set(old_default_by_type) - set(our_default_by_type))
    if unmatched_types:
        notes.append(f"old default organizations of tree types {unmatched_types} have no "
                     f"our-default of that type -> deleted (their tree falls back to no scheme)")
    notes.append(f"{len(org_ids)} old organizations; defaults per tree "
                 f"{old_default_by_type}; ours {[(int(r.refs.get('org_type', 0)), r.elem_id) for r in ours]}")
    # ---- reconcile-browser + construction-set singletons --------------------
    records: List[Any] = list(ours)
    for cls_name, fn in (("ReconcileBrowserSettingsElem", ST.reconcile_browser_settings),
                         ("ConstructionSetProject", ST.construction_set_project)):
        old = ctx.one(cls_name)
        rec = fn(ids=ctx.ids)
        records.append(rec)
        if old is not None:
            olds.add(old)
            corr[old] = rec.elem_id
    # ---- the system navigator constellation ---------------------------------
    nav = ctx.one("RbsDbViewSystemNavigator")
    if nav is not None:
        wiring = _navigator_wiring(ctx, nav)
        constellation = ctx.own_fixpoint({nav})
        olds |= constellation
        our_nav = ST.system_navigator(ctx.ids, **wiring)
        records.extend(our_nav)
        role_new = {r.class_name: r.elem_id for r in our_nav}
        matched_roles = []
        for e in sorted(constellation):
            c = ctx.cls_of.get(e)
            if c in role_new and c not in matched_roles:
                corr[e] = role_new[c]
                matched_roles.append(c)
        notes.append(f"navigator constellation {sorted(constellation)} "
                     f"({[ctx.cls_of.get(e) for e in sorted(constellation)]}) -> "
                     f"ours {role_new}; wiring {wiring}")
    else:
        notes.append("no RbsDbViewSystemNavigator in the parent (nothing to substitute)")
    return SubstBuild(old_ids=sorted(olds), records=records, corr=corr,
                      new_only=house, notes=notes,
                      info={"old_defaults_by_type": old_default_by_type,
                            "our_defaults_by_type": {t: r.elem_id for t, r in our_default_by_type.items()},
                            "house_schemes": [r.elem_id for r in house]})


# ---------------------------------------------------------------------------
# X3  StructSettingsElem + WallJoinDefaultSetting + AutoJoinTracker +
#     KeynoteTable / KeynotingSystem + InitialViewSettings
# ---------------------------------------------------------------------------
def build_X3(ctx: SubstContext) -> SubstBuild:
    """OLD = the structural-settings, wall-join-default, auto-join, keynote
    table + keynoting-system, and starting-view singletons.  NEW = OURS
    (settings.struct_settings / wall_join_default_setting /
    auto_join_tracker / keynote_table(EMPTY -- Autodesk's 3,840-row
    keynote database is NOT reproduced) / keynoting_system /
    initial_view_settings), each wired to whatever the OLD one referenced
    (the structural boundary-condition symbol, the starting drafting view).
    Registry: UniqueElementsTracking slots + KeynoteTableTracking /
    KeynotingSystemTracking sets, all remapped in place.  Inbound: the
    KeynotingSystem->KeynoteTable edge is internal (both replaced); the
    RvtLinkInstance that names the keynote table is re-pointed."""
    olds: Set[int] = set()
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    # StructSettingsElem: keep its wiring to the (still present) brace symbol /
    # boundary-condition families and hidden levels
    ss = ctx.one("StructSettingsElem")
    if ss is not None:
        v = ctx.value(ss)
        kw = dict(hidden_level_ids=[int(x) for x in (v.get("m_hiddenLevelIds") or [])
                                    if isinstance(x, int) and x > 0],
                  brace_above_id=int(v.get("m_braceAbove", INVALID) or INVALID),
                  brace_below_id=int(v.get("m_braceBelow", INVALID) or INVALID),
                  kicker_brace_id=int(v.get("m_kickerBrace", INVALID) or INVALID),
                  bc_fixed_family_id=int(v.get("m_bcFixedFamilyId", INVALID) or INVALID),
                  bc_pinned_family_id=int(v.get("m_bcPinnedFamilyId", INVALID) or INVALID),
                  bc_roller_family_id=int(v.get("m_bcRollerFamilyId", INVALID) or INVALID),
                  bc_user_family_id=int(v.get("m_bcUserFamilyId", INVALID) or INVALID))
        for k in list(kw):
            if k != "hidden_level_ids" and kw[k] in (None, 0):
                kw[k] = INVALID
        rec = ST.struct_settings(ids=ctx.ids, **kw)
        records.append(rec)
        olds.add(ss)
        corr[ss] = rec.elem_id
        notes.append(f"StructSettings wiring kept: {kw}")
    # WallJoinDefaultSetting / AutoJoinTracker (empty machinery)
    for cls_name, fn in (("WallJoinDefaultSetting", ST.wall_join_default_setting),
                         ("AutoJoinTracker", ST.auto_join_tracker)):
        old = ctx.one(cls_name)
        rec = fn(ids=ctx.ids)
        records.append(rec)
        if old is not None:
            olds.add(old)
            corr[old] = rec.elem_id
    # keynote table (EMPTY, ours) + keynoting system pointing at it
    old_kt = ctx.one("KeynoteTable")
    old_ks = ctx.one("KeynotingSystem")
    kt = ST.keynote_table(ids=ctx.ids)
    records.append(kt)
    number_by_sheet = False
    if old_ks is not None:
        number_by_sheet = bool(ctx.value(old_ks).get("m_isNumberBySheet", False))
    ks = ST.keynoting_system(kt.elem_id, ids=ctx.ids, number_by_sheet=number_by_sheet)
    records.append(ks)
    if old_kt is not None:
        olds.add(old_kt)
        corr[old_kt] = kt.elem_id
        n_entries = 0
        try:
            tree = ((ctx.value(old_kt).get("m_oKeyBasedTreeEntries") or {}).get("value") or {})
            n_entries = len(tree.get("m_keyBasedTreeEntrySet") or [])
        except Exception:
            pass
        notes.append(f"old keynote table carried {n_entries} entries (Autodesk's shipped "
                     f"keynote database) -> ours is EMPTY (not reproduced; a job passes its own rows)")
    if old_ks is not None:
        olds.add(old_ks)
        corr[old_ks] = ks.elem_id
    # InitialViewSettings -> keep the starting view (a still-present view)
    old_iv = ctx.one("InitialViewSettings")
    start_view = INVALID
    if old_iv is not None:
        sv = ctx.value(old_iv).get("m_initialViewId")
        start_view = int(sv) if isinstance(sv, int) and sv > 0 else INVALID
    iv = ST.initial_view_settings(ids=ctx.ids, initial_view_id=start_view)
    records.append(iv)
    if old_iv is not None:
        olds.add(old_iv)
        corr[old_iv] = iv.elem_id
        notes.append(f"starting view kept: {start_view}")
    return SubstBuild(old_ids=sorted(olds), records=records, corr=corr, notes=notes)


# ---------------------------------------------------------------------------
# X4  the Rbs*Settings + Rbs*Sizes tables (wire / duct / pipe / conduit /
#     cable tray), keyed onto the parent's still-present MEP catalogs
# ---------------------------------------------------------------------------
#: OUR pipe SIZE data = published dimensional facts (like the NEC wire
#: tables): ASME B36.10M carbon-steel schedule 40 / 80 (NPS, OD, wall) and
#: ASTM B88 copper tube types K / L / M (nominal, OD, wall), inches.  The
#: choice of range (1/2" .. 12") is ours.  ID = OD - 2*wall.
_ASME_B36_10_SCH40: List[Tuple[float, float, float]] = [
    # (NPS_in, OD_in, wall_in)  -- ASME B36.10M schedule 40
    (0.5, 0.840, 0.109), (0.75, 1.050, 0.113), (1.0, 1.315, 0.133),
    (1.25, 1.660, 0.140), (1.5, 1.900, 0.145), (2.0, 2.375, 0.154),
    (2.5, 2.875, 0.203), (3.0, 3.500, 0.216), (4.0, 4.500, 0.237),
    (5.0, 5.563, 0.258), (6.0, 6.625, 0.280), (8.0, 8.625, 0.322),
    (10.0, 10.750, 0.365), (12.0, 12.750, 0.406),
]
_ASME_B36_10_SCH80: List[Tuple[float, float, float]] = [
    (0.5, 0.840, 0.147), (0.75, 1.050, 0.154), (1.0, 1.315, 0.179),
    (1.25, 1.660, 0.191), (1.5, 1.900, 0.200), (2.0, 2.375, 0.218),
    (2.5, 2.875, 0.276), (3.0, 3.500, 0.300), (4.0, 4.500, 0.337),
    (5.0, 5.563, 0.375), (6.0, 6.625, 0.432), (8.0, 8.625, 0.500),
    (10.0, 10.750, 0.594), (12.0, 12.750, 0.688),
]
_ASME_B36_19_10S: List[Tuple[float, float, float]] = [
    (0.5, 0.840, 0.083), (0.75, 1.050, 0.083), (1.0, 1.315, 0.109),
    (1.25, 1.660, 0.109), (1.5, 1.900, 0.109), (2.0, 2.375, 0.109),
    (2.5, 2.875, 0.120), (3.0, 3.500, 0.120), (4.0, 4.500, 0.120),
    (5.0, 5.563, 0.134), (6.0, 6.625, 0.134), (8.0, 8.625, 0.148),
    (10.0, 10.750, 0.165), (12.0, 12.750, 0.180),
]
_ASTM_B88_TYPE_L: List[Tuple[float, float, float]] = [
    # (nominal_in, OD_in, wall_in)  -- ASTM B88 copper tube, type L
    (0.5, 0.625, 0.040), (0.75, 0.875, 0.045), (1.0, 1.125, 0.050),
    (1.25, 1.375, 0.055), (1.5, 1.625, 0.060), (2.0, 2.125, 0.070),
    (2.5, 2.625, 0.080), (3.0, 3.125, 0.090), (4.0, 4.125, 0.110),
    (5.0, 5.125, 0.125), (6.0, 6.125, 0.140), (8.0, 8.125, 0.200),
]
_ASTM_B88_TYPE_K: List[Tuple[float, float, float]] = [
    (0.5, 0.625, 0.049), (0.75, 0.875, 0.065), (1.0, 1.125, 0.065),
    (1.25, 1.375, 0.065), (1.5, 1.625, 0.072), (2.0, 2.125, 0.083),
    (2.5, 2.625, 0.095), (3.0, 3.125, 0.109), (4.0, 4.125, 0.134),
    (5.0, 5.125, 0.160), (6.0, 6.125, 0.192), (8.0, 8.125, 0.271),
]
_ASTM_B88_TYPE_M: List[Tuple[float, float, float]] = [
    (0.5, 0.625, 0.028), (0.75, 0.875, 0.032), (1.0, 1.125, 0.035),
    (1.25, 1.375, 0.042), (1.5, 1.625, 0.049), (2.0, 2.125, 0.058),
    (2.5, 2.625, 0.065), (3.0, 3.125, 0.072), (4.0, 4.125, 0.095),
    (5.0, 5.125, 0.109), (6.0, 6.125, 0.122), (8.0, 8.125, 0.170),
]


def _rows_from_od_wall(table: Sequence[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
    """(nominal, OD, wall) -> (nominal, inner, outer) in inches."""
    return [(nom, round(od - 2.0 * wall, 4), od) for nom, od, wall in table]


def _norm_name(s: str) -> str:
    s = str(s or "").strip().lower()
    return {"aluminium": "aluminum"}.get(s, s)


def _our_pipe_size_map(ctx: SubstContext, old_sizes_id: int, notes: List[str]) -> Dict[int, dict]:
    """OUR pipe-size table keyed onto the parent's EXISTING piping catalog
    (RbsPipeMaterialType / -ConnectionType / -ScheduleType ids -- the
    catalog is Autodesk's until the catalog rung).  The KEY structure
    (which material/connection/schedule combinations exist) is read from
    the OLD RbsPipeSizesElem; the size ROWS are OUR dimensional facts,
    selected by the schedule / material NAME:
      'schedule 40' -> ASME B36.10M sch 40;  'schedule 80' -> sch 80;
      stainless '10s'/'5s'/'40s' -> ASME B36.19M 10S table;
      copper 'a'->type K, 'b'/'l'->type L, 'c'/'m'->type M, 'd'->type M;
      anything else -> the schedule-40 series (documented default).
    """
    old = ctx.value(old_sizes_id)
    mats = old.get("m_materialMapConnections") or []
    out: Dict[int, dict] = {}
    n_rows = 0
    for m in mats:
        mid = int(m.get("first"))
        mname = _norm_name(ctx.name_of(mid))
        conns_out: Dict[int, dict] = {}
        for c in ((m.get("second") or {}).get("m_connectionMapSchedules") or []):
            cid = int(c.get("first"))
            scheds_out: Dict[int, list] = {}
            for s in ((c.get("second") or {}).get("m_scheduleMapSizes") or []):
                sid = int(s.get("first"))
                sname = _norm_name(ctx.name_of(sid))
                if "80" in sname:
                    table = _ASME_B36_10_SCH80
                elif "copper" in mname:
                    table = {"a": _ASTM_B88_TYPE_K, "k": _ASTM_B88_TYPE_K,
                             "b": _ASTM_B88_TYPE_L, "l": _ASTM_B88_TYPE_L,
                             "c": _ASTM_B88_TYPE_M, "m": _ASTM_B88_TYPE_M,
                             "d": _ASTM_B88_TYPE_M}.get(sname.strip(), _ASTM_B88_TYPE_L)
                elif any(t in sname for t in ("10s", "5s", "40s")) or "stainless" in mname:
                    table = _ASME_B36_19_10S
                else:
                    table = _ASME_B36_10_SCH40
                rows = _rows_from_od_wall(table)
                scheds_out[sid] = rows
                n_rows += len(rows)
            conns_out[cid] = scheds_out
        out[mid] = conns_out
    notes.append(f"pipe sizes keyed onto the parent's catalog ({len(out)} materials); "
                 f"{n_rows} size rows of OUR dimensional data (ASME B36.10/B36.19, ASTM B88)")
    return out


def _our_wire_size_tables(ctx: SubstContext, notes: List[str]) -> Tuple[dict, dict]:
    """OUR wire-sizes table (NEC 310.16 ampacity / 250.122 grounds /
    310.15 correction -- facts) keyed onto the parent's EXISTING wire
    catalog symbols by normalized NAME ('Copper'/'Aluminum' materials,
    '75'/'90' temperature ratings, every insulation type listed against
    each rating).  Catalog symbols our NEC data does not cover (steel /
    non-magnetic conductors, the 60 C column) get NO rows -- our ampacity
    standard does not define them (documented, not an omission)."""
    from rvt.genesis.house_standard import WIRE_AMPACITY_TABLE
    mats = {_norm_name(ctx.name_of(e)): e for e in ctx.ids_of("RbsWireMaterialType")}
    temps = {_norm_name(ctx.name_of(e)): e for e in ctx.ids_of("RbsWireTemperatureRatingType")}
    ins = {ctx.name_of(e): e for e in ctx.ids_of("RbsWireInsulationType")}
    material_ids, temp_ids = {}, {}
    for our_name in WIRE_AMPACITY_TABLE:
        e = mats.get(_norm_name(our_name))
        if e is not None:
            material_ids[our_name] = e
    for tname in set(sum((list(t) for t in WIRE_AMPACITY_TABLE.values()), [])):
        e = temps.get(_norm_name(tname))
        if e is not None:
            temp_ids[tname] = e
    notes.append(f"wire sizes keyed onto the parent's catalog: materials {material_ids} "
                 f"(of {list(mats)}), ratings {temp_ids} (of {list(temps)}), "
                 f"{len(ins)} insulation symbols; uncovered by our NEC data: "
                 f"{sorted(set(mats) - {_norm_name(k) for k in material_ids})} materials, "
                 f"{sorted(set(temps) - {_norm_name(k) for k in temp_ids})} ratings")
    return material_ids, temp_ids, ins


def build_X4(ctx: SubstContext) -> SubstBuild:
    """OLD = the MEP settings + size-table singletons: RbsWire/Pipe/Duct
    SettingsElem, RbsWire/Pipe/DuctSizesElem, Conduit/CableTraySettingsElem.
    NEW = OURS, WIRED to the parent's still-present catalogs: our wire
    settings keep the old home-run leader style / tick-mark symbols; our
    pipe / duct settings keep the per-classification pipe / duct TYPE ids;
    the size TABLES are OUR data (SMACNA duct series, ASME/ASTM pipe
    dimensions, NEC ampacity) keyed onto the existing catalog symbol ids.
    Inbound: the MEP tracker constellation's regen edges into the duct /
    pipe settings are re-pointed to ours.  The MEP catalogs themselves
    (wire material / pipe schedule / conduit-standard symbols) are a later
    rung (the settings CATALOG layer) and are left as residue here."""
    olds: Set[int] = set()
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    residue: Dict[str, str] = {}
    # ---- wire settings ---------------------------------------------------------
    ws = ctx.one("RbsWireSettingsElem")
    if ws is not None:
        v = ctx.value(ws)
        tick = v.get("m_wireTickMarkStyle") or {}
        rec = ST.wire_settings(
            ids=ctx.ids,
            tick_mark_families={"hot": int(tick.get("m_hotConductorFamSymId", INVALID)),
                                "neutral": int(tick.get("m_neutralConductorFamSymId", INVALID)),
                                "ground": int(tick.get("m_groundConductorFamSymId", INVALID)),
                                "slanted": bool(tick.get("m_bDrawSlantedLine", False))},
            connector_separator=str(v.get("m_strElectricalConnectorSeparator") or "-"),
            home_run_arrow_style_id=int(v.get("m_idWireHomeRunArrowLeaderStyle", INVALID) or INVALID),
            show_tick_marks=int(v.get("m_eShowTickMarks", 0) or 0),
            tick_mark_style=int(v.get("m_nWireTickMarkStyle", 0) or 0),
            electrical_data_style=int(v.get("m_nElectricalDataStyle", 0) or 0),
            circuit_description_style=int(v.get("m_nCircuitDescriptionStyle", 0) or 0),
            home_run_arrow_count_style=int(v.get("m_eWireHomeRunArrowCountStyle", 0) or 0))
        records.append(rec)
        olds.add(ws)
        corr[ws] = rec.elem_id
    # ---- wire sizes (our NEC data over the existing wire catalog) --------------
    wz = ctx.one("RbsWireSizesElem")
    if wz is not None:
        material_ids, temp_ids, ins_ids = _our_wire_size_tables(ctx, notes)
        if material_ids and temp_ids:
            rec = ST.wire_sizes_from_house_table(material_ids, temp_ids, ins_ids, ids=ctx.ids)
        else:
            rec = ST.wire_sizes({}, ids=ctx.ids)          # empty (no catalog symbols)
            notes.append("wire sizes: no matching catalog symbols -> empty table")
        records.append(rec)
        olds.add(wz)
        corr[wz] = rec.elem_id
    # ---- pipe settings (keep per-classification pipe TYPE wiring) -----------
    ps = ctx.one("RbsPipeSettingsElem")
    if ps is not None:
        v = ctx.value(ps)
        routing = {}
        for row in v.get("m_mapSystemTypeToPipeSettings") or []:
            code = int(row.get("first"))
            s = row.get("second") or {}
            routing[code] = {"type_id": int(s.get("m_typeId", INVALID) or INVALID),
                             "branch_type_id": int(s.get("m_branchTypeId", INVALID) or INVALID)}
        rec = ST.pipe_settings(ids=ctx.ids, system_routing=(routing or None))
        records.append(rec)
        olds.add(ps)
        corr[ps] = rec.elem_id
    # ---- pipe sizes (our ASME/ASTM data over the existing pipe catalog) ------
    pz = ctx.one("RbsPipeSizesElem")
    if pz is not None:
        material_map = _our_pipe_size_map(ctx, pz, notes)
        rec = ST.pipe_sizes(material_map, ids=ctx.ids)
        records.append(rec)
        olds.add(pz)
        corr[pz] = rec.elem_id
    # ---- duct settings (keep per-classification duct TYPE wiring) -----------
    ds = ctx.one("RbsDuctSettingsElem")
    if ds is not None:
        v = ctx.value(ds)
        routing = {}
        for row in v.get("m_mapSystemTypeToDuctSettings") or []:
            code = int(row.get("first"))
            s = row.get("second") or {}
            routing[code] = {"type_id": int(s.get("m_typeId", INVALID) or INVALID),
                             "branch_type_id": int(s.get("m_branchTypeId", INVALID) or INVALID),
                             "flex_type_id": int(s.get("m_flexTypeId", INVALID) or INVALID)}
        rec = ST.duct_settings(ids=ctx.ids, system_routing=(routing or None))
        records.append(rec)
        olds.add(ds)
        corr[ds] = rec.elem_id
    dz = ctx.one("RbsDuctSizesElem")
    if dz is not None:
        rec = ST.duct_sizes(ids=ctx.ids)
        records.append(rec)
        olds.add(dz)
        corr[dz] = rec.elem_id
    # ---- conduit / cable tray settings ---------------------------------------
    for cls_name, fn in (("ConduitSettingsElem", ST.conduit_settings),
                         ("CableTraySettingsElem", ST.cable_tray_settings)):
        old = ctx.one(cls_name)
        rec = fn(ids=ctx.ids)
        records.append(rec)
        if old is not None:
            olds.add(old)
            corr[old] = rec.elem_id
    # the MEP catalogs stay (a later rung)
    for cls_name in ("RbsWireMaterialType", "RbsWireTemperatureRatingType",
                     "RbsWireInsulationType", "RbsPipeMaterialType",
                     "RbsPipeConnectionType", "RbsPipeScheduleType", "PipeSegment",
                     "ConduitSizesElem", "CableTraySizesElem"):
        n = len(ctx.ids_of(cls_name))
        if n:
            residue[cls_name] = f"{n} kept -- MEP catalog / catalog-keyed size table (later rung)"
    return SubstBuild(old_ids=sorted(olds), records=records, corr=corr,
                      notes=notes, residue=residue)


# ---------------------------------------------------------------------------
# X5  every remaining settings singleton / tracker WITH a constructor
# ---------------------------------------------------------------------------
#: classes substituted by the earlier rungs (their old elements are gone)
_DONE_BY_X1_X4 = {
    "PenWidthTableElem",                                    # X1
    "BrowserOrganization", "RbsDbViewSystemNavigator", "ReconcileBrowserSettingsElem",
    "ConstructionSetProject",                               # X2 (+ its Viewer/Viewport/DBDrawing)
    "StructSettingsElem", "WallJoinDefaultSetting", "AutoJoinTracker",
    "KeynoteTable", "KeynotingSystem", "InitialViewSettings",              # X3
    "RbsWireSettingsElem", "RbsWireSizesElem", "RbsPipeSettingsElem",
    "RbsPipeSizesElem", "RbsDuctSettingsElem", "RbsDuctSizesElem",
    "ConduitSettingsElem", "CableTraySettingsElem",                        # X4
}
#: settings-ish classes that BELONG to a LATER rung (not X5's business)
_DEFERRED_TO_LATER_RUNG = {
    "DBViewType": "X9 (view-type layer; 72 of the 91 are curtain-SYSTEM-family editor types)",
    "RbsWireMaterialType": "catalog rung (MEP catalog symbol, keyed by our X4 sizes table)",
    "RbsWireTemperatureRatingType": "catalog rung", "RbsWireInsulationType": "catalog rung",
    "RbsPipeMaterialType": "catalog rung", "RbsPipeConnectionType": "catalog rung",
    "RbsPipeScheduleType": "catalog rung", "PipeSegment": "catalog rung",
    "ConduitSizesElem": "catalog rung (keyed on the conduit standards)",
    "CableTraySizesElem": "catalog rung",
    "ElectricalLoadClassification": "catalog rung (types stream constructor exists)",
    "ElectricalDemandFactorDefinition": "catalog rung (types stream constructor exists)",
    "UnitsElem": "X8 (document units)", "ProjectInfo": "X8", "BasePoint": "X8",
    "GeoLocation": "X8", "GeoSite": "X8", "TrueNorth": "X8", "ProjectPhase": "X8",
    "AllProjectPhases": "X8", "PhaseFilterElem": "X8", "Level": "X8",
    "SunAndShadowSettings": "X9 (view companions)", "LightSchemeElement": "X9",
}
#: settings-ish classes with NO our-constructor (the honest residue list)
_NO_CONSTRUCTOR = {
    "NumberingSchema": "element-numbering schema (no constructor)",
    "AssemblyCodeTable": "Autodesk's UniFormat assembly-code table (product data; no constructor)",
    "AllPlanTopologies": "plan-topology regeneration cache (no constructor; regenerable)",
    "PlanTopology": "plan-topology regeneration cache (no constructor; regenerable)",
    "AreaSchemePlanTopologies": "area-scheme plan-topology cache (no constructor)",
    "PostedWarningElem": "posted-warnings state (no constructor)",
    "RegenSplitterElem": "regeneration splitter state (no constructor)",
    "HubsTracker": "structural-hub tracker (no constructor)",
    "MEPAnalyticalModelSettings": "MEP analytical-model settings (no constructor)",
    "LinkLoadTable": "linked-file load table (link machinery; no constructor)",
    "PrintSetup": "print setup (no constructor)",
    "SunStudyElem": "sun-study state (no constructor)",
}
_SETTINGS_LIKE = re.compile(r"(Setting|Settings|SettingsElem|SizesElem|Tracker|Manager|"
                            r"Mgr|Table|System|Sequence|Schema|Scheme|Set)$")


def _elem_name(ctx: SubstContext, eid: int) -> str:
    v = ctx.value(eid) or {}
    for k in ("m_sName", "m_sequenceName", "m_areaElemName"):
        if v.get(k):
            return str(v.get(k))
    return ctx.name_of(eid)


def _rec_name(rec) -> str:
    o = rec.obj or {}
    si = o.get("m_symbolInfo")
    if isinstance(si, dict):
        n = (si.get("value") or {}).get("m_name") or si.get("m_name")
        if n:
            return str(n)
    for k in ("m_name", "m_sName", "m_sequenceName", "m_areaElemName", "m_viewName"):
        if o.get(k):
            return str(o.get(k))
    return ""


def build_X5(ctx: SubstContext) -> SubstBuild:
    """OLD = every settings singleton / tracker / small settings set the
    PARENT carries for which we have a constructor, minus the X1..X4
    classes.  NEW = ours for exactly those classes, each wired to the
    CURRENT file (units, sun, phases, geo-location, the X4 duct/pipe
    settings, the still-present catalogs).  RULE: X5 never introduces a
    class the parent lacks and never touches a class that belongs to a
    later rung (view types, catalogs, datums); the parent's settings
    classes WITHOUT a constructor are LISTED as residue -- the honest
    finding, never a silent keep.  Multi-instance sets pair by name
    (sequences 'Numeric'/'Alphanumeric', styles '<Shading>'/'<Raytracing>',
    area schemes by area-type code); a class where ours has FEWER instances
    (print setups 3->1, worksharing display 2->1) deletes the extra sample
    ones (their registry rows drop with them)."""
    olds: Set[int] = set()
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    residue: Dict[str, str] = {}
    substituted: List[str] = []

    def one_for_one(cls_name: str, factory: Callable[[int], Any]) -> None:
        """Substitute a true singleton: ours built by factory(old_id)."""
        old = ctx.ids_of(cls_name)
        if not old:
            return
        for o in old:
            olds.add(o)
        rec = factory(old[0])
        records.append(rec)
        corr[old[0]] = rec.elem_id
        substituted.append(cls_name)
        if len(old) > 1:
            notes.append(f"{cls_name}: {len(old)} in parent, ours 1 -> "
                         f"{len(old) - 1} extra sample instance(s) deleted")

    # ---- CURRENT-file wiring targets ------------------------------------------
    units = ctx.one("UnitsElem") or INVALID
    geo = ctx.one("GeoLocation") or INVALID
    sun = INVALID
    for e in ctx.ids_of("SunAndShadowSettings"):
        if not ctx.st["owner_view"].get(e):               # the DOCUMENT sun (no owner view)
            sun = e
            break
    duct_settings = ctx.one("RbsDuctSettingsElem") or INVALID    # ours from X4
    pipe_settings = ctx.one("RbsPipeSettingsElem") or INVALID    # ours from X4
    notes.append(f"wiring: units {units}, document sun {sun}, geo {geo}, "
                 f"duct settings {duct_settings}, pipe settings {pipe_settings}")

    # ---- the MEP tracker constellation (wired to OUR X4 duct/pipe settings) ---
    if ctx.ids_of("MEPSystemTracker") or ctx.ids_of("MEPComponentTracker"):
        trk = ST.mep_tracker_constellation(ctx.ids, duct_settings, pipe_settings)
        by_cls = {r.class_name: r for r in trk}
        for cls_name, rec in by_cls.items():
            old = ctx.ids_of(cls_name)
            if old:
                records.append(rec)
                for o in old:
                    olds.add(o)
                corr[old[0]] = rec.elem_id
                substituted.append(cls_name)
            else:
                notes.append(f"{cls_name}: parent has none -> our record NOT added "
                             f"(X5 introduces no new class)")
        # the constellation's internal edges (system -> component/layout ...) all
        # point at our own records; any tracker class the parent lacks is dropped
        # above, so purge dangling internal edges to dropped members
        present_new = {r.elem_id for r in records}
        for r in records:
            if r.class_name in by_cls:
                par = ((r.header.get("m_parents") or {}).get("value") or {})
                ro = par.get("m_regenOnly")
                if isinstance(ro, list):
                    par["m_regenOnly"] = [x for x in ro if not (isinstance(x, int) and x > 0
                                                             and x not in present_new
                                                             and x not in ctx.universe)]
    # ---- simple 1:1 singletons -------------------------------------------------
    one_for_one("MEPHiddenLineSettingsElem", lambda o: ST.mep_hidden_line_settings(ids=ctx.ids))
    for cls_name in ("CircuitNamingTypeSetting", "AssemblyTracker",
                     "KeynoteTagsOnSheetsTracker", "RevisionCloudsOnSheetsTracker",
                     "SheetsInSheetCollectionTracker", "AnalyticalToPhysicalRelationManager",
                     "ReactionsUpToDateElem", "GraphicsCache", "ExternalParamLock",
                     "DaylightSourceIdSet", "WorksetVisibilitySettingsElem",
                     "Dwg2dExportUserSettingsData", "STEPExportSettings", "ZoneScheme",
                     "RvtLinkInstanceAppearanceParentElem", "SketchGridAppearanceParentElem",
                     "FabricationServiceSettings", "CurtaSystemFaceManager",
                     "StructuralConnectionSettings"):
        one_for_one(cls_name, lambda o, c=cls_name: ST.tracker(c, ids=ctx.ids))
    one_for_one("GCSTracker", lambda o: ST.gcs_tracker(ctx.ids, units_id=units))
    one_for_one("AutoCamSettingsElem", lambda o: ST.auto_cam_settings(ids=ctx.ids))
    one_for_one("HalftoneUnderlaySettings", lambda o: ST.halftone_underlay_settings(ids=ctx.ids))
    one_for_one("MultipleValuesIndicationSettings",
                lambda o: ST.multiple_values_indication_settings(ids=ctx.ids))
    one_for_one("DefaultDivideSettings", lambda o: ST.default_divide_settings(ids=ctx.ids))
    one_for_one("ProjectCopySettingsElem", lambda o: ST.project_copy_settings(ids=ctx.ids))
    one_for_one("AreaSettingsElem", lambda o: ST.area_settings(ids=ctx.ids))
    one_for_one("RouteAnalysisSettings", lambda o: ST.route_analysis_settings(ids=ctx.ids))
    one_for_one("FabricationSettings", lambda o: ST.fabrication_settings(ids=ctx.ids))
    one_for_one("FabricationSettingsElement", lambda o: ST.fabrication_settings_element(ids=ctx.ids))
    one_for_one("SSEPointVisibilitySettings", lambda o: ST.sse_point_visibility_settings(ids=ctx.ids))
    one_for_one("ReinforcementSettings", lambda o: ST.reinforcement_settings(ids=ctx.ids))
    one_for_one("CoordinateSystemDisplayElem", lambda o: ST.coordinate_system_display(ids=ctx.ids))
    # electrical setting (the types stream's constructor)
    if ctx.ids_of("ElectricalSetting"):
        from rvt.genesis.types import electrical_setting
        one_for_one("ElectricalSetting", lambda o: electrical_setting(ids=ctx.ids))
    # copy-watch: keep the linked model reference the sample points at
    if ctx.ids_of("CopyWatchProperties"):
        def _cw(o):
            link = int(ctx.value(o).get("m_linkId", INVALID) or INVALID)
            return ST.copy_watch_properties(ids=ctx.ids, link_id=link)
        one_for_one("CopyWatchProperties", _cw)
    # active geo-location tracking: keep the project / active positions
    if ctx.ids_of("ActiveGeoLocationTrackingElement"):
        def _geo(o):
            v = ctx.value(o)
            proj = int(v.get("m_projectGeoLocationId", INVALID) or INVALID)
            act = int(v.get("m_activeGeoLocationId", INVALID) or INVALID)
            if proj in (None, INVALID):
                proj = geo
            return ST.active_geo_location_tracking(proj, active_geo_location_id=act, ids=ctx.ids)
        one_for_one("ActiveGeoLocationTrackingElement", _geo)
    # energy data: keep every id the sample's element wires to
    if ctx.ids_of("EnergyDataSettings"):
        def _energy(o):
            v = ctx.value(o)
            def g(k):
                x = v.get(k)
                return int(x) if isinstance(x, int) and x > 0 else INVALID
            return ST.energy_data_settings(
                ids=ctx.ids, ground_level_id=g("m_groundPlane"),
                project_phase_id=g("m_projectPhase"),
                building_type_id=g("m_buildingTypeId"),
                construction_set_id=g("m_constructionSetElementId"))
        one_for_one("EnergyDataSettings", _energy)
    # worksharing display: ours = the PROJECT element; per-user copies deleted
    wvm = ctx.ids_of("WorksharingViewModeSettings")
    if wvm:
        proj_old = next((o for o in wvm if ctx.value(o).get("m_projectSettings")), wvm[0])
        rec = ST.worksharing_view_mode_settings(ids=ctx.ids)
        records.append(rec)
        olds |= set(wvm)
        corr[proj_old] = rec.elem_id
        substituted.append("WorksharingViewModeSettings")
        if len(wvm) > 1:
            notes.append(f"WorksharingViewModeSettings: {len(wvm)} in parent (project + "
                         f"per-user); ours = the project element only")
    # ---- multi-instance settings sets ---------------------------------------
    # model graphics styles: '<Shading>' / '<Raytracing>' by name
    mgs = ctx.ids_of("ModelGraphicsStyle")
    if mgs:
        ours_mgs = ST.model_graphics_styles(ctx.ids, sun)
        by_name = {_norm_name(_elem_name(ctx, o)): o for o in mgs}
        records.extend(ours_mgs)
        olds |= set(mgs)
        for r in ours_mgs:
            o = by_name.get(_norm_name(_rec_name(r)))
            if o is not None:
                corr[o] = r.elem_id
        substituted.append("ModelGraphicsStyle")
    # the revision constellation: sequences by name, revision + table 1:1
    seqs = ctx.ids_of("RevisionNumberingSequence")
    revs = ctx.ids_of("ProjectRevision")
    table = ctx.ids_of("AllProjectRevisions")
    if seqs or revs or table:
        cons = ST.revision_constellation(ctx.ids)      # [num, alpha, rev, table]
        records.extend(cons)
        olds |= set(seqs) | set(revs) | set(table)
        seq_by_name = {_norm_name(_elem_name(ctx, o)): o for o in seqs}
        for r in cons:
            if r.class_name == "RevisionNumberingSequence":
                o = seq_by_name.get(_norm_name(_rec_name(r)))
                if o is not None:
                    corr[o] = r.elem_id
            elif r.class_name == "ProjectRevision" and revs:
                corr[revs[0]] = r.elem_id
                if len(revs) > 1:
                    notes.append(f"ProjectRevision: {len(revs)} in parent, ours 1 initial "
                                 f"revision -> {len(revs) - 1} sample revision(s) deleted")
            elif r.class_name == "AllProjectRevisions" and table:
                corr[table[0]] = r.elem_id
        substituted += ["RevisionNumberingSequence", "ProjectRevision", "AllProjectRevisions"]
    # print settings: ours = the 'Default' setup
    ps = ctx.ids_of("PrintSettings")
    if ps:
        rec = ST.print_settings(ids=ctx.ids)
        records.append(rec)
        olds |= set(ps)
        by_name = {_norm_name(_elem_name(ctx, o)): o for o in ps}
        target = by_name.get("default", ps[0])
        corr[target] = rec.elem_id
        substituted.append("PrintSettings")
        if len(ps) > 1:
            notes.append(f"PrintSettings: {len(ps)} in parent (named setups), ours 1 "
                         f"'Default' -> {len(ps) - 1} sample setup(s) deleted")
    # view sheet sets: ours (our names) over the SAME drawings the sample sets held
    vss = ctx.ids_of("ViewSheetSet")
    if vss:
        from rvt.genesis.house_standard import gen
        our_names = ["Working Set", "Issue Set", "Progress Set", "Record Set"]
        for i, o in enumerate(vss):
            v = ctx.value(o)
            ordered = (v.get("m_orderedViewSheetList") or {})
            dids = [int(x) for x in (ordered.get("m_dbDrawingIds") or [])
                    if isinstance(x, int) and x > 0]
            nm = gen(our_names[i]) if i < len(our_names) else gen(f"Set {i + 1}")
            rec = ST.view_sheet_set(nm, ids=ctx.ids, drawing_ids=dids,
                                    sheet_organization_id=int(ordered.get("m_sheetOrganizationId", INVALID) or INVALID),
                                    view_organization_id=int(ordered.get("m_viewOrganizationId", INVALID) or INVALID),
                                    automatic=bool(ordered.get("m_isAutomatic", False)))
            records.append(rec)
            olds.add(o)
            corr[o] = rec.elem_id
        substituted.append("ViewSheetSet")
        notes.append(f"ViewSheetSet: {len(vss)} sets renamed to our set names, each over "
                     f"the drawings the sample set held (wiring kept, names ours)")
    # area schemes: ours (our names / BOMA-IPMS descriptions) by area-type code
    ams = ctx.ids_of("AreaMeasureElem")
    if ams:
        from rvt.genesis.house_standard import gen
        old_by_type: Dict[int, int] = {}
        for o in ams:
            old_by_type.setdefault(int(ctx.value(o).get("m_eAreaType", 0) or 0), o)
        used = set()
        for nm, desc, code in ST.AREA_SCHEMES:
            o = old_by_type.get(int(code))
            if o is None:
                continue                       # parent has no scheme of this type: add none
            v = ctx.value(o)
            rec = ST.area_measure(
                gen(nm), desc, int(code), ids=ctx.ids,
                area_type_ids=[int(x) for x in (v.get("m_areaTypeElemSet") or [])
                               if isinstance(x, int) and x > 0],
                plan_topology_id=int(v.get("m_areaSchemePlanTopologyElemId", INVALID) or INVALID),
                default_space_id=int(v.get("m_defaultSpaceElemId", INVALID) or INVALID))
            records.append(rec)
            corr[o] = rec.elem_id
            used.add(o)
        olds |= set(ams)
        substituted.append("AreaMeasureElem")
        extra = [o for o in ams if o not in used]
        if extra:
            notes.append(f"AreaMeasureElem: {len(extra)} sample scheme(s) with an area type our "
                         f"pair does not cover -> deleted")
    notes.append(f"X5 substituted {len(substituted)} classes: {sorted(set(substituted))}")

    # ---- residue: everything settings-ish X5 did NOT substitute ---------------
    done = _DONE_BY_X1_X4 | set(substituted) | {"MEPComponentTracker", "LayoutNodesTracker",
                                                 "MEPSystemTracker", "MEPNetworkTracker",
                                                 "MEPNetworkDataElem"}
    parent_classes = collections.Counter(ctx.cls_of.get(e, "?") for e in ctx.host)
    deferred: Dict[str, str] = {}
    for cls_name, n in sorted(parent_classes.items()):
        if cls_name in done:
            continue
        if cls_name in _DEFERRED_TO_LATER_RUNG:
            deferred[cls_name] = f"{n} kept -> {_DEFERRED_TO_LATER_RUNG[cls_name]}"
        elif cls_name in _NO_CONSTRUCTOR:
            residue[cls_name] = f"{n} kept -- {_NO_CONSTRUCTOR[cls_name]}"
        elif _SETTINGS_LIKE.search(cls_name):
            residue[cls_name] = f"{n} kept -- settings-like class with NO our-constructor"
    return SubstBuild(old_ids=sorted(olds), records=records, corr=corr,
                      notes=notes, residue=residue,
                      info={"substituted_classes": sorted(set(substituted)),
                            "deferred_to_later_rungs": deferred,
                            "wiring": {"units": units, "document_sun": sun, "geo": geo,
                                       "duct_settings": duct_settings,
                                       "pipe_settings": pipe_settings}})


# ---------------------------------------------------------------------------
# X6a  the built-in-category GStyle catalog (the K6 / S4 question)
# ---------------------------------------------------------------------------
def build_X6a(ctx: SubstContext) -> SubstBuild:
    """OLD = every PROJECT-level built-in-category graphic-style row: the
    GStyleElem rows with a negative (built-in) m_categoryId and m_famId -1
    -- Autodesk's object-styles table (their per-category default pen /
    colour / pattern values = the quarantined product table; K6 FAIL proved
    the reader REQUIRES this catalog complete).  NEW = OUR complete catalog
    (catalog.builtin_style_catalog: the same registered per-release
    graphic-category ENUM -- 1,074 categories, 333 cuttable, an interface
    constant -- valued by OUR discipline scheme; 0 rows value-identical to
    Autodesk's table, asserted by the singletons stream's test).  The enum
    match makes the correspondence a perfect 1:1 by (category id, style
    type): every reference to an old row (views' per-category machinery,
    the area-boundary curves' line styles, the curtain-system symbols, the
    ADocument's CategoryTracking category->style maps that P4/P6/K6 proved
    are walked at load) is re-pointed to OUR row of the SAME (category,
    type).  Family-scoped rows (the curtain systems') and the project
    SUBCATEGORY layer (project CategoryElem rows + their styles: Revit's
    auto-created line styles / annotation subcategories) are NOT touched --
    the subcategory layer has NO our-constructor and is the X6b GAP."""
    old_by_key: Dict[Tuple[int, int], int] = {}
    dup = 0
    for e in ctx.ids_of("GStyleElem"):
        v = ctx.value(e)
        if int(v.get("m_famId", -1) or -1) != -1:
            continue                                   # family-scoped (curtain systems)
        cid = v.get("m_categoryId")
        t = v.get("m_gstyleType")
        if not (isinstance(cid, int) and cid < 0 and isinstance(t, int)):
            continue                                   # project subcategory row (X6b gap)
        key = (int(cid), int(t))
        if key in old_by_key:
            dup += 1
            continue
        old_by_key[key] = int(e)
    ours = CAT.builtin_style_catalog(ctx.ids)
    corr: Dict[int, int] = {}
    new_only: List[Any] = []
    covered = set()
    for r in ours:
        key = (int(r.obj.get("m_categoryId")), int(r.obj.get("m_gstyleType")))
        o = old_by_key.get(key)
        if o is None:
            new_only.append(r)                         # a (category,type) the sample lacked
        else:
            corr[o] = r.elem_id
            covered.add(key)
    old_uncovered = sorted(set(old_by_key) - covered)
    subcat_rows = sum(1 for e in ctx.ids_of("GStyleElem")
                      if int(ctx.value(e).get("m_famId", -1) or -1) == -1
                      and not (isinstance(ctx.value(e).get("m_categoryId"), int)
                               and ctx.value(e).get("m_categoryId") < 0))
    notes = [f"sample built-in rows {len(old_by_key)} (duplicates skipped {dup}); our catalog "
             f"{len(ours)} rows (enum {len({(int(r.obj.get('m_categoryId')), 1) for r in ours})} "
             f"categories); 1:1 by (category, style-type): mapped {len(corr)}, "
             f"sample-only (deleted) {len(old_uncovered)}, ours-only (registered) {len(new_only)}",
             f"project SUBCATEGORY GStyle rows left in place: {subcat_rows} (X6b gap: no "
             f"our-constructor for Revit's auto-created subcategory / line-style layer)"]
    return SubstBuild(old_ids=sorted(old_by_key.values()), records=list(ours), corr=corr,
                      new_only=new_only, notes=notes,
                      residue={"GStyleElem(project-subcategory)": f"{subcat_rows} rows kept -- "
                               "the subcategory / line-style layer (X6b gap)",
                               "CategoryElem": f"{len(ctx.ids_of('CategoryElem'))} kept -- "
                               "project + curtain-system subcategory records (X6b gap)"},
                      info={"sample_only_keys": [list(k) for k in old_uncovered[:40]],
                            "ours_only_keys": [[int(r.obj.get("m_categoryId")),
                                                int(r.obj.get("m_gstyleType"))]
                                               for r in new_only[:40]]})


# ---------------------------------------------------------------------------
# X7  line patterns + fill patterns + materials (+ their asset companions)
# ---------------------------------------------------------------------------
def _house_records(ctx: SubstContext, kinds: Set[str],
                   cache: dict = {}) -> Tuple[List[Any], Any]:
    """Instantiate OUR complete self-contained content once per rung
    (rvt.genesis.house_standard.build_catalog, ids from the rung's band)
    and return the records whose manifest KIND is in ``kinds`` + the
    catalog (for its named ids).  The catalog is exactly what the genesis
    assembler builds G0/G1 from -- the same constructors, our values."""
    from rvt.genesis import house_standard as hs
    key = (ctx.rung, ctx.id_start)
    if key not in cache:
        cache.clear()
        cache[key] = hs.build_catalog(start_id=ctx.id_start)
        # keep the rung's allocator past everything the catalog took
        ctx.ids = IdSource(int(cache[key].last_id) + 1)
    hc = cache[key]
    by_id = {int(r.elem_id): r for r in hc.records}
    picked = [by_id[int(m["id"])] for m in hc.manifest
              if m.get("kind") in kinds and int(m["id"]) in by_id]
    return picked, hc


def _sample_gfx_name(ctx: SubstContext, eid: int) -> str:
    """Name of a sample pattern / material / asset element."""
    v = ctx.value(eid)
    for holder in ("m_pMaterial", "m_pFillPattern", "m_pLinePattern"):
        h = v.get(holder)
        if isinstance(h, dict):
            n = (h.get("value") or {}).get("m_name")
            if n:
                return str(n)
    return ctx.name_of(eid)


def _sample_material_class(ctx: SubstContext, eid: int) -> str:
    v = ctx.value(eid)
    m = ((v.get("m_pMaterial") or {}).get("value") or {})
    return str(m.get("m_sMaterialClass") or "")


#: OUR pattern / material ROLE matcher: a sample element is paired with our
#: record of the same ROLE by these documented keyword rules (many sample
#: elements may share one of our roles -- their references then all
#: re-point to our one element of that role).  Elements matching no role
#: are simply deleted (their referencing fields neutralise to -1 = solid /
#: none / by-category, which is Revit-legal everywhere those fields sit).
_LINE_ROLE_RULES = [("demol", "demolition"), ("hidden", "hidden"),
                    ("centre", "centre"), ("center", "centre"),
                    ("dash", "dash"), ("dot", "dash"), ("overhead", "dash")]
_FILL_ROLE_RULES = [("solid", "solid"), ("insul", "insulation"), ("sand", "sand"),
                    ("cross", "crosshatch"), ("diagonal", "diagonal_up"),
                    ("hatch", "crosshatch")]
_MAT_ROLE_RULES = [("phase - exist", "phase_existing"), ("existing", "phase_existing"),
                   ("phase - demo", "phase_demo"), ("demolition", "phase_demo"),
                   ("phase - new", "phase_new"), ("phase - temp", "phase_temp"),
                   ("temporary", "phase_temp"),
                   ("block", "cmu"), ("masonry", "cmu"), ("brick", "cmu"), ("cmu", "cmu"),
                   ("gypsum", "gypsum"), ("plaster", "gypsum"), ("stud", "metal_stud"),
                   ("insul", "insulation"), ("glass", "glass"), ("glaz", "glass"),
                   ("wood", "wood"), ("timber", "wood"), ("lumber", "wood"), ("ply", "wood"),
                   ("earth", "earth"), ("soil", "earth"), ("site", "earth"),
                   ("concrete", "concrete"), ("cast", "concrete"), ("mpa", "concrete"),
                   ("steel", "steel"), ("metal", "steel"), ("alumin", "steel"),
                   ("copper", "steel"), ("iron", "steel"),
                   ("default", "concrete")]        # Revit's 'Default' material -> a neutral one


def _role_of(name: str, rules) -> Optional[str]:
    n = str(name or "").strip().lower()
    for kw, role in rules:
        if kw in n:
            return role
    return None


def _our_role_of_record(rec, kind: str) -> str:
    """Our record's role key (from its own name)."""
    n = _rec_name(rec).lower()
    if kind == "line":
        if "demol" in n: return "demolition"
        if "hidden" in n: return "hidden"
        if "centre" in n or "center" in n: return "centre"
        return "dash"
    if kind == "fill":
        if "solid" in n: return "solid"
        if "insul" in n: return "insulation"
        if "sand" in n: return "sand"
        if "cross" in n: return "crosshatch"
        return "diagonal_up"
    # material
    if "phase" in n:
        if "exist" in n: return "phase_existing"
        if "demol" in n: return "phase_demo"
        if "new" in n: return "phase_new"
        if "temp" in n: return "phase_temp"
    if "masonry" in n or "cmu" in n: return "cmu"
    if "gypsum" in n: return "gypsum"
    if "stud" in n: return "metal_stud"
    if "insul" in n: return "insulation"
    if "glass" in n: return "glass"
    if "wood" in n: return "wood"
    if "earth" in n: return "earth"
    if "steel" in n: return "steel"
    return "concrete"


def build_X7(ctx: SubstContext) -> SubstBuild:
    """OLD = the whole graphic-material palette layer: every LinePatternElem,
    FillPatternElem, MaterialElem, plus the materials' companions
    (AppearanceAssetElem render assets, PropertySetElement thermal/physical
    property sets, PropertySetLibrary) -- Autodesk's drafting-pattern set,
    their material library ('Concrete 10 MPa', 'Default', the phase
    materials) and its render/physical asset data.  NEW = OUR palette
    (house_standard: 4 line patterns, 5 fill patterns, 13 materials incl.
    our four phase-override materials; our materials carry NO Autodesk
    asset binding and NO property sets).  Correspondence is MANY-to-ONE by
    ROLE (their many 'Dash' variants -> our one dash pattern; 'Concrete
    10 MPa' -> our concrete; 'Phase - Demo' -> our demolition-phase
    material...); the wall / floor / roof types, pipe segments, phase
    filters, colour-fill schemas and residue subcategory styles that
    referenced their palette are re-pointed by role, or neutralised (-1 =
    solid / by-category / none) where no role matches.  Two open token
    questions ride on this rung: does the reader key on the sample's
    '<Solid fill>' NAME (ours is a structural solid, named ours) and on the
    'Default' material name (ours has no 'Default')."""
    ours, _hc = _house_records(ctx, {"line-pattern", "fill-pattern", "material"})
    our_line = [r for r in ours if r.class_name == "LinePatternElem"]
    our_fill = [r for r in ours if r.class_name == "FillPatternElem"]
    our_mat = [r for r in ours if r.class_name == "MaterialElem"]
    our_line_by_role = {}
    for r in our_line:
        our_line_by_role.setdefault(_our_role_of_record(r, "line"), r)
    our_fill_by_role = {}
    for r in our_fill:
        our_fill_by_role.setdefault(_our_role_of_record(r, "fill"), r)
    our_mat_by_role = {}
    for r in our_mat:
        our_mat_by_role.setdefault(_our_role_of_record(r, "mat"), r)
    olds: Set[int] = set()
    corr: Dict[int, int] = {}
    role_hist: Counter = collections.Counter()
    unmatched: Counter = collections.Counter()
    for e in ctx.ids_of("LinePatternElem"):
        olds.add(e)
        role = _role_of(_sample_gfx_name(ctx, e), _LINE_ROLE_RULES)
        r = our_line_by_role.get(role) if role else None
        if r is not None:
            corr[e] = r.elem_id
            role_hist[("line", role)] += 1
        else:
            unmatched["LinePatternElem"] += 1
    for e in ctx.ids_of("FillPatternElem"):
        olds.add(e)
        # a zero-grid pattern IS a solid fill (structure), whatever its name
        v = ctx.value(e)
        grids = (((v.get("m_pFillPattern") or {}).get("value") or {}).get("m_gridsArr"))
        role = "solid" if (isinstance(grids, list) and not grids) else \
            _role_of(_sample_gfx_name(ctx, e), _FILL_ROLE_RULES)
        r = our_fill_by_role.get(role) if role else None
        if r is not None:
            corr[e] = r.elem_id
            role_hist[("fill", role)] += 1
        else:
            unmatched["FillPatternElem"] += 1
    for e in ctx.ids_of("MaterialElem"):
        olds.add(e)
        nm = _sample_gfx_name(ctx, e)
        role = _role_of(nm, _MAT_ROLE_RULES) or \
            _role_of(_sample_material_class(ctx, e), _MAT_ROLE_RULES)
        r = our_mat_by_role.get(role) if role else None
        if r is not None:
            corr[e] = r.elem_id
            role_hist[("material", role)] += 1
        else:
            unmatched["MaterialElem"] += 1
    for cls_name in ("AppearanceAssetElem", "PropertySetElement", "PropertySetLibrary"):
        olds |= set(ctx.ids_of(cls_name))
    notes = [
        f"our palette: {len(our_line)} line patterns {sorted(our_line_by_role)}, "
        f"{len(our_fill)} fill patterns {sorted(our_fill_by_role)}, "
        f"{len(our_mat)} materials {sorted(our_mat_by_role)}",
        f"role matches (sample->ours, many-to-one): "
        f"{ {f'{k[0]}:{k[1]}': v for k, v in sorted(role_hist.items())} }",
        f"sample elements with NO role match (deleted; their referencing fields neutralise): "
        f"{dict(unmatched)}",
        "companions deleted with the materials: AppearanceAssetElem (render assets, "
        "Autodesk's asset library), PropertySetElement (thermal/physical property data), "
        "PropertySetLibrary -- our materials carry none",
        "OPEN TOKEN QUESTIONS (probe rows): (1) the sample's '<Solid fill>' pattern is "
        "replaced by our structural solid fill under our name; (2) the sample's 'Default' "
        "material is replaced by our concrete -- ours has no 'Default'-named material",
    ]
    return SubstBuild(old_ids=sorted(olds), records=ours, corr=corr, notes=notes,
                      residue={"GStyleElem(project-subcategory)": "the subcategory line "
                               "styles now point at our patterns or -1 (X6b gap layer)",
                               "BasicWallType/FloorAttributes/RoofAttributes/"
                               "CompoundCeilingType": "the sample's SYSTEM types stay "
                               "(their layer materials re-pointed to ours by role) -- a "
                               "system-types rung",
                               "ConceptualConstructionType": "massing energy constructions "
                               "(their materials neutralised) -- residue"},
                      info={"role_histogram": {f"{k[0]}:{k[1]}": v
                                               for k, v in role_hist.items()},
                            "unmatched": dict(unmatched)})


# ---------------------------------------------------------------------------
# catalog SUBSET re-wiring: our records reference catalog SIBLINGS
# (levels -> our units / geolocation; phasing overrides -> our phase
# materials + patterns).  When a rung takes only a SUBSET of the house
# catalog, references to non-picked catalog records are re-pointed to the
# CURRENT file's element of the same (class, name) -- or, for
# document-unique classes, its one element -- so the subset stays coherent
# with the layers earlier rungs already made ours.
# ---------------------------------------------------------------------------

_SINGLETON_CLASSES = {"UnitsElem", "TrueNorth", "ProjectInfo", "AllProjectPhases",
                      "AllProjectRevisions", "ElectricalSetting"}


def _file_element_names(ctx: SubstContext) -> Dict[Tuple[str, str], int]:
    """(class, normalized name) -> element id over the current file, for
    every class our catalog subsets may need to re-wire to."""
    out: Dict[Tuple[str, str], int] = {}
    want = {"MaterialElem", "FillPatternElem", "LinePatternElem", "GeoLocation",
            "GeoSite", "UnitsElem", "TrueNorth", "ProjectInfo", "SunAndShadowSettings",
            "AllProjectPhases", "ProjectPhase", "PhaseFilterElem", "Level",
            "LevelAttributes", "DBViewType"}
    for e in ctx.host:
        c = ctx.cls_of.get(e)
        if c not in want:
            continue
        nm = _norm_name(_sample_gfx_name(ctx, e) or ctx.name_of(e))
        out.setdefault((c, nm), int(e))
    return out


def _catalog_name(rec) -> str:
    nm = _rec_name(rec)
    if nm:
        return nm
    o = rec.obj or {}
    for h in ("m_pMaterial", "m_pFillPattern", "m_pLinePattern"):
        x = o.get(h)
        if isinstance(x, dict):
            n = (x.get("value") or {}).get("m_name")
            if n:
                return str(n)
    return ""


def _rewire_subset(ctx: SubstContext, picked: List[Any], hc,
                   notes: List[str]) -> Tuple[int, int]:
    """Re-point references from ``picked`` records to NON-picked catalog
    records onto the current file's same-(class,name)/singleton element.
    Unresolvable references are removed (scalar -> INVALID, list entry
    dropped) and counted.  Returns (rewired, dropped)."""
    picked_ids = {int(r.elem_id) for r in picked}
    cat_by_id = {int(r.elem_id): r for r in hc.records}
    file_names = _file_element_names(ctx)
    file_singleton: Dict[str, int] = {}
    for cls_name in _SINGLETON_CLASSES:
        ids = ctx.ids_of(cls_name)
        if len(ids) == 1:
            file_singleton[cls_name] = ids[0]
    # the document sun = the SunAndShadowSettings no view owns
    for e in ctx.ids_of("SunAndShadowSettings"):
        if not ctx.st["owner_view"].get(e):
            file_singleton["SunAndShadowSettings(document)"] = e
            break
    mapping: Dict[int, int] = {}
    unresolved: Set[int] = set()

    def resolve(cid: int) -> Optional[int]:
        rec = cat_by_id.get(cid)
        if rec is None:
            return None
        cls_name = rec.class_name
        key = (cls_name, _norm_name(_catalog_name(rec)))
        if key in file_names:
            return file_names[key]
        if cls_name in file_singleton:
            return file_singleton[cls_name]
        if cls_name == "SunAndShadowSettings" and "SunAndShadowSettings(document)" in file_singleton:
            return file_singleton["SunAndShadowSettings(document)"]
        return None
    # collect every catalog-sibling reference the picked records hold
    for r in picked:
        for body, cname in ((r.obj, r.class_name), (r.header, "ElementHeader")):
            for lf in ctx.ted.leaves(body, cname):
                v = lf.value
                if not (isinstance(v, int) and v > 0) or v in picked_ids or v == r.elem_id:
                    continue
                if v in cat_by_id:                      # a non-picked catalog sibling
                    if v not in mapping:
                        tgt = resolve(v)
                        if tgt is not None:
                            mapping[v] = tgt
                        else:
                            unresolved.add(v)
    # apply: remap resolvable, strip unresolvable
    n_re = n_drop = 0
    for r in picked:
        for body, cname in ((r.obj, r.class_name), (r.header, "ElementHeader")):
            if mapping:
                n_re += len(ctx.ted.remap(body, cname, mapping))
            if unresolved:
                live = ({int(x.elem_id) for x in picked} | set(mapping.values())
                        | set(ctx.universe)) - unresolved
                st_p = ctx.ted.purge(body, cname, live)
                n_drop += (st_p.get("nulled", 0) + st_p.get("elements_dropped", 0)
                           + st_p.get("scalars_nulled", 0))
    if mapping:
        notes.append(f"catalog re-wiring: {n_re} reference(s) re-pointed to the current "
                     f"file's elements: "
                     f"{[(cat_by_id[k].class_name, _catalog_name(cat_by_id[k])) for k in sorted(mapping)][:12]}")
    if unresolved:
        notes.append(f"catalog re-wiring: {len(unresolved)} sibling(s) had NO current-file "
                     f"counterpart -> {n_drop} reference(s) dropped: "
                     f"{[(cat_by_id[k].class_name, _catalog_name(cat_by_id[k])) for k in sorted(unresolved)][:12]}")
    return n_re, n_drop


# ---------------------------------------------------------------------------
# X8  units + true north + geo sites/locations + base points + project info
# ---------------------------------------------------------------------------
def build_X8(ctx: SubstContext) -> SubstBuild:
    """OLD = the document-identity + site layer: UnitsElem, TrueNorth, the
    GeoSite/GeoLocation pairs, the two BasePoints (project base point +
    survey point) and ProjectInfo.  NEW = ours (house catalog: our unit
    formats, our poche/true-north, OUR site (latitude/longitude/climate),
    our project + survey points, OUR project information).  Correspondence:
    units / true-north / project-info 1:1; the sample's PROJECT geo-location
    (the one our X5 ActiveGeoLocationTracking names as project position) ->
    our project location and its site -> ours; the other location/site ->
    our internal ones; base points by role (shared = survey point).  Every
    view / level / navigator regen-edge into the sample's units and every
    element referencing the sample's geo-locations is re-pointed."""
    picked, hc = _house_records(ctx, {"units-registry", "true-north", "geo-site",
                                      "geo-location", "project-base-point",
                                      "survey-point", "project-info"})
    notes: List[str] = []
    _rewire_subset(ctx, picked, hc, notes)              # self-contained, but be safe
    by_kind: Dict[str, List[Any]] = collections.defaultdict(list)
    manifest_kind = {int(m["id"]): m["kind"] for m in hc.manifest}
    for r in picked:
        by_kind[manifest_kind.get(int(r.elem_id), r.class_name)].append(r)
    olds: Set[int] = set()
    corr: Dict[int, int] = {}
    # units / true north / project info: singletons
    for cls_name, kind in (("UnitsElem", "units-registry"), ("TrueNorth", "true-north"),
                           ("ProjectInfo", "project-info")):
        ours = by_kind.get(kind) or []
        old = ctx.ids_of(cls_name)
        if ours and old:
            olds |= set(old)
            corr[old[0]] = ours[0].elem_id
    # geo locations + their sites: sample project location = the one our
    # ActiveGeoLocationTracking (from X5) names as m_projectGeoLocationId
    our_locs = by_kind.get("geo-location") or []
    our_sites = by_kind.get("geo-site") or []
    old_locs = ctx.ids_of("GeoLocation")
    old_sites = ctx.ids_of("GeoSite")
    proj_old = None
    trk = ctx.one("ActiveGeoLocationTrackingElement")
    if trk is not None:
        p = ctx.value(trk).get("m_projectGeoLocationId")
        if isinstance(p, int) and p in old_locs:
            proj_old = p
    if proj_old is None and old_locs:
        proj_old = old_locs[-1]
    if our_locs and old_locs:
        # our loc_prj = the catalog's 'geo_location' named id; the other is internal
        prj_id = hc.ids.get("geo_location")
        our_prj = next((r for r in our_locs if r.elem_id == prj_id), our_locs[-1])
        our_int = next((r for r in our_locs if r.elem_id != our_prj.elem_id), our_locs[0])
        olds |= set(old_locs)
        corr[proj_old] = our_prj.elem_id
        others = [l for l in old_locs if l != proj_old]
        if others:
            corr[others[0]] = our_int.elem_id
        # sites: the site each mapped location references -> ours
        def site_of(loc_id: int) -> Optional[int]:
            for t in ctx.outbound(loc_id):
                if ctx.cls_of.get(t) == "GeoSite":
                    return int(t)
            return None
        our_site_prj = next((r for r in our_sites
                             if int(our_prj.obj.get("m_siteId", -1) or -1) == r.elem_id), None) \
            or (our_sites[-1] if our_sites else None)
        our_site_int = next((r for r in our_sites
                             if our_site_prj is None or r.elem_id != our_site_prj.elem_id),
                            our_sites[0] if our_sites else None)
        s_prj = site_of(proj_old)
        s_int = site_of(others[0]) if others else None
        for s_old, s_new in ((s_prj, our_site_prj), (s_int, our_site_int)):
            if s_old is not None and s_new is not None:
                olds.add(s_old)
                corr[s_old] = s_new.elem_id
        for s in old_sites:                                # any un-referenced sample site
            if s not in corr:
                olds.add(s)
        notes.append(f"project geo-location {proj_old} -> ours {our_prj.elem_id}; "
                     f"internal {others[:1]} -> {our_int.elem_id}; sites {s_prj}/{s_int} -> "
                     f"{our_site_prj.elem_id if our_site_prj else None}/"
                     f"{our_site_int.elem_id if our_site_int else None}")
    # base points: role by 'shared' (True = survey point)
    old_bp = ctx.ids_of("BasePoint")
    our_bp = (by_kind.get("project-base-point") or []) + (by_kind.get("survey-point") or [])
    if old_bp and our_bp:
        our_by_role = {bool(r.obj.get("m_bShared", False)): r for r in our_bp}
        for b in old_bp:
            olds.add(b)
            role = bool(ctx.value(b).get("m_bShared", False))
            r = our_by_role.get(role)
            if r is not None:
                corr[b] = r.elem_id
    notes.append(f"our identity/site layer: {[(k, len(v)) for k, v in by_kind.items()]}")
    return SubstBuild(old_ids=sorted(olds), records=picked, corr=corr, notes=notes)


# ---------------------------------------------------------------------------
# X9  the DOCUMENT SKELETON: levels + level type + phases + phase set +
#     phase filters + document sun + the 19 project view types + every
#     view constellation + our text types -- ONE coherent replacement
# ---------------------------------------------------------------------------
#: view classes whose elements ARE the sample's view constellations (each
#: view's companions -- viewer, viewport, drawing, extents, sketch planes,
#: sun settings, light schemes, clip boxes -- join through the ownership
#: fixpoint)
_VIEW_ROOT_CLASSES = {
    "DBView3d", "DBViewSection", "DBViewPlan", "DBViewDrafting", "DBViewAnonDrafting",
    "DBViewRendering", "DBViewGraphSchedColumn", "DBViewTypeAreaPlan", "DBViewProject",
    "DBViewSchedule", "LevelRoomPlan", "PanelScheduleView",
}
_VIEW_COMPANION_CLASSES = {
    "DBDrawing", "Viewer", "Viewer3d", "Section", "InteriorElev", "InteriorElevArrow",
    "GraphSchedColumnTable", "Viewport", "GCSViewport", "ExtentElem", "ModelClipBox",
    "SunAndShadowSettings", "LightSchemeElement", "SunAnnotationElem",
}
_PHASE_FILTER_ROLE_RULES = [("show all", "all"), ("complete", "all"),
                            ("demo", "demolition"), ("new", "new"),
                            ("previous phase", "existing"), ("existing", "existing"),
                            ("previous", "existing")]


def _our_filter_role(rec) -> str:
    n = _rec_name(rec).lower()
    if "all phases" in n or "construction set" in n:
        return "all"
    if "demolition" in n:
        return "demolition"
    if "new work" in n:
        return "new"
    if "existing" in n:
        return "existing"
    return "all"


def build_X9(ctx: SubstContext) -> SubstBuild:
    """OLD = the whole document SKELETON layer: every level + the level
    type (LevelAttributes), the phases + AllProjectPhases + phase filters,
    the document sun, all 19 PROJECT DBViewTypes (m_famId -1), and EVERY
    view constellation (project view, 3D views, plans, sections,
    elevations, drafting / legend / rendering views, with their viewers,
    viewports, drawings, extents, clip boxes, sketch planes, per-view sun
    settings and light schemes) plus the sample's SYSTEM text types.
    NEW = OUR skeleton from the house catalog (2 building-storey levels +
    our level type, our 2 phases + set (phasing overrides re-wired to OUR
    X7 phase materials) + 5 filters, our document sun, our 19 view types
    (3 house + 16 system), our project-view + 3D + 2 plan constellations,
    our 3 text types) -- ONE coherent replacement, so no view is left
    bound to a deleted level.  Correspondence: the sample project view ->
    ours; its '{3D}' default 3D view -> our 3D view; the floor plans of
    the two lowest building storeys -> our two plans (and THOSE plans'
    levels -> our L1 / L2); phases by order; filters by role name; view
    types by m_systemFamilyIdx; the DEFAULT text type (SymbolIdMgr row)
    -> our body text.  Everything else in the layer is deleted; the DBView
    registries (DBViewInfo project-view / views-index / navigator,
    DBViewTypesForNewLevel, SymbolIdMgr defaults) are re-pointed or
    purged.  Residue by construction: the 72 curtain-SYSTEM-family view
    types, dimension / leader / section / callout attribute types, fonts
    (no constructors), grids and reference planes (sample datum content)."""
    kinds = {"level-type", "level", "phase", "phase-set", "phase-filter",
             "document-sun-settings", "view-type", "project-view-constellation",
             "3d-view-constellation", "plan-view-constellation", "text-type"}
    picked, hc = _house_records(ctx, kinds)
    notes: List[str] = []
    # ---- the 16 remaining SYSTEM view types (the house builds 3d/plan/rcp) ---
    extra_vt = ST.system_view_type_table(ctx.ids, skip_families=("3d", "floor_plan",
                                                                  "ceiling_plan"))
    picked = list(picked) + list(extra_vt)
    _rewire_subset(ctx, picked, hc, notes)
    manifest_kind = {int(m["id"]): m["kind"] for m in hc.manifest}
    by_kind: Dict[str, List[Any]] = collections.defaultdict(list)
    for r in picked:
        by_kind[manifest_kind.get(int(r.elem_id), "system-view-type"
                                   if r.class_name == "DBViewType" else r.class_name)].append(r)
    olds: Set[int] = set()
    corr: Dict[int, int] = {}
    new_only: List[Any] = []
    doc, cls_of = ctx.doc, ctx.cls_of

    # ================= the VIEW LAYER =================
    view_roots = set(ctx.ids_of(*_VIEW_ROOT_CLASSES))
    companions = set(ctx.ids_of(*_VIEW_COMPANION_CLASSES))
    view_layer = ctx.own_fixpoint(view_roots) | companions
    view_layer = ctx.own_fixpoint(view_layer)
    olds |= view_layer
    # -- pick the sample views to map ---------------------------------------
    proj_view = next(iter(ctx.ids_of("DBViewProject")), None)
    threed = None
    for e in ctx.ids_of("DBView3d"):
        if str(ctx.value(e).get("m_viewName") or "").strip() == "{3D}":
            threed = e
            break
    if threed is None:
        c3 = ctx.ids_of("DBView3d")
        threed = c3[0] if c3 else None
    # floor plans of the two lowest building storeys (by their level elevation)
    plans = []
    for e in ctx.ids_of("DBViewPlan"):
        v = ctx.value(e)
        # a plan's LEVEL = its generating element (m_genElemId) [VERIFIED on
        # rstbasic plans: the associated level; also the view-depth plane]
        lv = None
        for k in ("m_genElemId", "m_levelId", "m_pLevelId", "m_associatedLevelId"):
            x = v.get(k)
            if isinstance(x, int) and x > 0 and ctx.cls_of.get(x) == "Level":
                lv = x
                break
        lvl = int(lv) if lv else None
        elev = None
        if lvl is not None:
            el = ctx.value(lvl).get("m_elevation")
            if isinstance(el, (int, float)):
                elev = float(el)
        name = str(v.get("m_viewName") or "")
        plans.append((elev if elev is not None else 1e18, e, lvl, name))
    # prefer views literally named 'Level 1'/'Level 2', else lowest storeys
    named12 = {}
    for elev, e, lvl, nm in plans:
        n = nm.strip().lower()
        if n in ("level 1", "level1", "01", "ground floor", "l1"):
            named12.setdefault(1, (e, lvl))
        elif n in ("level 2", "level2", "02", "l2"):
            named12.setdefault(2, (e, lvl))
    plan_pairs: List[Tuple[int, Optional[int]]] = []
    if len(named12) == 2:
        plan_pairs = [named12[1], named12[2]]
    else:
        seen_lvls = set()
        for elev, e, lvl, nm in sorted(p for p in plans if p[0] is not None):
            if lvl in seen_lvls:
                continue
            seen_lvls.add(lvl)
            plan_pairs.append((e, lvl))
            if len(plan_pairs) == 2:
                break
    # -- our constellations, keyed by role ------------------------------------
    our_proj = by_kind.get("project-view-constellation") or []
    our_3d = by_kind.get("3d-view-constellation") or []
    our_plans_all = by_kind.get("plan-view-constellation") or []
    # split our two plan constellations: each starts at a DBViewPlan record
    our_plan_groups: List[List[Any]] = []
    cur: List[Any] = []
    for r in sorted(our_plans_all, key=lambda x: x.elem_id):
        if r.class_name == "DBViewPlan" and cur:
            our_plan_groups.append(cur)
            cur = []
        cur.append(r)
    if cur:
        our_plan_groups.append(cur)

    def map_constellation(sample_root: Optional[int], ours: List[Any], tag: str) -> None:
        """Map the sample view's constellation onto ours by class, in id
        order (a role match: the k-th Viewer of the sample view -> the k-th
        Viewer of our view)."""
        if sample_root is None or not ours:
            return
        cons = sorted(ctx.own_fixpoint({sample_root}))
        by_cls_new: Dict[str, List[Any]] = collections.defaultdict(list)
        for r in ours:
            by_cls_new[r.class_name].append(r)
        used: Dict[str, int] = collections.Counter()
        n_map = 0
        for e in cons:
            c = cls_of.get(e)
            lst = by_cls_new.get(c) or []
            k = used[c]
            if k < len(lst):
                corr[e] = lst[k].elem_id
                used[c] += 1
                n_map += 1
        notes.append(f"{tag}: sample view {sample_root} constellation {len(cons)} -> "
                     f"ours {len(ours)} records; {n_map} role-matched")

    map_constellation(proj_view, our_proj, "project view")
    map_constellation(threed, our_3d, "3D view '{3D}'")
    level_corr_source: List[Tuple[int, int]] = []          # (sample level, our plan index)
    for i, (e, lvl) in enumerate(plan_pairs[:2]):
        if i < len(our_plan_groups):
            map_constellation(e, our_plan_groups[i], f"plan {i + 1}")
            if lvl is not None:
                level_corr_source.append((lvl, i))
    n_del_views = len(view_layer - set(corr))
    notes.append(f"view layer: {len(view_layer)} sample elements ({len(view_roots)} view "
                 f"roots); mapped constellations {sum(1 for e in view_layer if e in corr)}; "
                 f"deleted {n_del_views}")

    # ================= view types =================
    old_vt = [e for e in ctx.ids_of("DBViewType")
              if int(ctx.value(e).get("m_famId", -1) or -1) == -1]
    our_vt = (by_kind.get("view-type") or []) + (by_kind.get("system-view-type") or [])
    ours_by_idx: Dict[int, List[Any]] = collections.defaultdict(list)
    for r in our_vt:
        idx = r.obj.get("m_systemFamilyIdx")
        if isinstance(idx, int):
            ours_by_idx[idx].append(r)
    olds |= set(old_vt)
    used_idx: Dict[int, int] = collections.Counter()
    for e in sorted(old_vt):
        idx = ctx.value(e).get("m_systemFamilyIdx")
        lst = ours_by_idx.get(int(idx)) if isinstance(idx, int) else None
        if lst:
            k = used_idx[int(idx)]
            corr[e] = lst[min(k, len(lst) - 1)].elem_id
            used_idx[int(idx)] += 1
    for idx, lst in ours_by_idx.items():
        if idx not in used_idx:
            new_only.extend(lst)                    # a view family the sample lacked
    notes.append(f"view types: sample project types {len(old_vt)} -> ours {len(our_vt)} "
                 f"(by m_systemFamilyIdx); family-scoped (curtain) types untouched: "
                 f"{len(ctx.ids_of('DBViewType')) - len(old_vt)}")

    # ================= levels + level type =================
    old_levels = ctx.ids_of("Level")
    our_levels = sorted(by_kind.get("level") or [], key=lambda r: r.obj.get("m_elevation", 0) or 0)
    olds |= set(old_levels)
    lvl_mapped = 0
    for lvl, i in level_corr_source:
        if i < len(our_levels) and lvl in old_levels and lvl not in corr:
            corr[lvl] = our_levels[i].elem_id
            lvl_mapped += 1
    if lvl_mapped == 0 and old_levels and our_levels:
        # fallback: the two lowest sample levels by elevation
        by_elev = sorted(old_levels, key=lambda l: (ctx.value(l).get("m_elevation") or 0))
        for i, l in enumerate(by_elev[:len(our_levels)]):
            corr[l] = our_levels[i].elem_id
            lvl_mapped += 1
    notes.append(f"levels: sample {len(old_levels)} -> ours {len(our_levels)}; mapped "
                 f"{lvl_mapped} (the levels the mapped plans sit on -> our L1/L2); "
                 f"the rest deleted with their views")
    old_ltype = ctx.ids_of("LevelAttributes")
    our_ltype = by_kind.get("level-type") or []
    if old_ltype and our_ltype:
        olds |= set(old_ltype)
        corr[old_ltype[0]] = our_ltype[0].elem_id

    # ================= phases + phase set + filters =================
    old_ph = list(ctx.ids_of("ProjectPhase"))
    aps = ctx.one("AllProjectPhases")
    if aps is not None:
        seq = [int(x) for x in (ctx.value(aps).get("m_phaseIds") or [])
               if isinstance(x, int) and x in old_ph]
        if seq:
            old_ph = seq + [p for p in old_ph if p not in seq]      # sequence order
        olds.add(aps)
    olds |= set(old_ph)
    our_ph = by_kind.get("phase") or []
    our_ph_set = by_kind.get("phase-set") or []
    for i, p in enumerate(old_ph):
        if i < len(our_ph):
            corr[p] = our_ph[i].elem_id
    if aps is not None and our_ph_set:
        corr[aps] = our_ph_set[0].elem_id
    old_pf = ctx.ids_of("PhaseFilterElem")
    our_pf = by_kind.get("phase-filter") or []
    our_pf_by_role: Dict[str, Any] = {}
    for r in our_pf:
        our_pf_by_role.setdefault(_our_filter_role(r), r)
    olds |= set(old_pf)
    for f in old_pf:
        role = _role_of(_sample_gfx_name(ctx, f), _PHASE_FILTER_ROLE_RULES)
        r = our_pf_by_role.get(role) if role else None
        if r is not None:
            corr[f] = r.elem_id
    notes.append(f"phases: sample {len(old_ph)} -> ours {len(our_ph)} (by sequence order); "
                 f"phase set 1:1; filters sample {len(old_pf)} -> ours {len(our_pf)} "
                 f"(by role; unmatched sample filters deleted)")

    # ================= document sun =================
    doc_sun_old = None
    for e in ctx.ids_of("SunAndShadowSettings"):
        if not ctx.st["owner_view"].get(e) and e not in view_layer:
            doc_sun_old = e
            break
    our_sun = by_kind.get("document-sun-settings") or []
    if doc_sun_old is not None and our_sun:
        olds.add(doc_sun_old)
        corr[doc_sun_old] = our_sun[0].elem_id
    # every other sample SunAndShadowSettings / LightSchemeElement is a view
    # companion (deleted with the views)
    olds |= set(ctx.ids_of("LightSchemeElement"))
    olds |= {e for e in ctx.ids_of("SunAndShadowSettings") if e != doc_sun_old}

    # ================= system TEXT types =================
    old_text = [e for e in ctx.ids_of("TextNoteAttributes")
                if int(ctx.value(e).get("m_famId", -1) or -1) == -1]
    our_text = [r for r in (by_kind.get("text-type") or []) if r.class_name == "TextNoteAttributes"]
    if old_text and our_text:
        # our body text (smallest) <- the sample's DEFAULT / most sizes; the
        # largest sample size -> our title text (many-to-one by size rank)
        def _size(rec_or_id):
            if isinstance(rec_or_id, int):
                v = ctx.value(rec_or_id)
            else:
                v = rec_or_id.obj
            for k in ("m_textSize", "m_size", "m_dTextSize"):
                x = v.get(k)
                if isinstance(x, (int, float)):
                    return float(x)
            return 0.0
        ours_sorted = sorted(our_text, key=_size)
        olds |= set(old_text)
        by_size = sorted(old_text, key=_size)
        for i, e in enumerate(by_size):
            # rank-proportional match onto our sizes
            j = min(int(i * len(ours_sorted) / max(1, len(by_size))), len(ours_sorted) - 1)
            corr[e] = ours_sorted[j].elem_id
        notes.append(f"text types: sample system text types {len(old_text)} -> ours "
                     f"{len(our_text)} (many-to-one by size rank); their fonts/companions "
                     f"stay as residue with the un-substituted annotation types")
    return SubstBuild(
        old_ids=sorted(olds), records=picked, corr=corr, new_only=new_only, notes=notes,
        residue={
            "DBViewType(curtain-family-scoped)": f"{len(ctx.ids_of('DBViewType')) - len(old_vt)} "
                                                  "kept -- the 8 curtain SYSTEM families' editor types",
            "DimensionStyle/LeaderStyle/SectionAttributes/CalloutTag/"
            "InteriorElevAttributes/ViewportAttributes/GridAttributes/"
            "SpotElevationStyle/FilledRegionAttributes":
                "annotation attribute types kept -- NO our-constructor (dimension / arrowhead / "
                "view-tag types)",
            "FontElem": f"{len(ctx.ids_of('FontElem'))} kept -- the residue annotation types' fonts",
            "Grid/RefPlane/MultiSegGrid": "sample datum content kept -- a datum-content rung "
                                          "(our grid/refplane constructors exist in the skeleton) "
                                          "or a removal rung",
        },
        info={"mapped_views": {"project_view": proj_view, "view_3d": threed,
                                "plans": [p[0] for p in plan_pairs[:2]]},
              "level_correspondence_from_plans": [list(x) for x in level_corr_source],
              "our_constellation_sizes": {"project": len(our_proj), "3d": len(our_3d),
                                          "plans": [len(g) for g in our_plan_groups]}})


# ===========================================================================
# 6b. X10 -- the FAMILY-LAYER removal rung (K3 + K4's proven operation)
# ===========================================================================
#: WHY X10 IS DERIVED RIGHT AFTER X5 (before the catalog rung): a
#: measurement on the X5 base found 1,421 of the built-in catalog rows'
#: referrers live INSIDE the embedded family documents (their internal
#: views reference the host's built-in styles) plus 238 Family / 228
#: FamilySymbol referrers.  Embedded-document records are NOT editable by
#: the host modify path, so substituting the catalog while the documents
#: exist would strand ~1,400 references.  Removing the loadable-family
#: layer + ALL embedded documents FIRST (K3's usage-null then K4's
#: coherent four-registry removal -- BOTH viewer-PASSED; families are NOT
#: required, K4 PASS) leaves the catalog free to substitute.  This is the
#: brief's X10, PROMOTED before X6 for that reason -- a recorded finding.

def run_family_removal(rung: Rung, parent_path: str, out_dir: str = SUBST) -> dict:
    """X10: parent minus the ENTIRE loadable-family layer AND all embedded
    family documents, removed together and coherently -- exactly the
    genesis-triage K3 (usage fields nulled) + K4 (documents + layer
    removed, four-registry coherent) operations, both viewer-PASSED.  What
    remains: the curtain-wall SYSTEM families (no documents) and every
    settings / catalog / view / datum element.  Emits <name>.rvt + json."""
    import genesis_triage as GT
    t_all = time.time()
    out = os.path.join(out_dir, f"{rung.name}.rvt")
    t_use = os.path.join(out_dir, f".{rung.name}.usage_nulled.rvt")
    t_docs = os.path.join(out_dir, f".{rung.name}.docs_removed.rvt")
    log(f"\n== {rung.name} :: {rung.label}")
    log(f"   parent {_relp(parent_path)}")
    report: Dict[str, Any] = {
        "rung": rung.name, "label": rung.label, "kind": rung.kind,
        "parent": _relp(parent_path), "parent_rung": rung.parent, "out": _relp(out),
        "description": rung.description, "tests": rung.tests,
        "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail, "stages": [],
    }
    # ---- step 1 (K3): the loadable-family layer + its USAGE fields ----------
    t0 = time.time()
    st = RR.build_state_v2(parent_path)
    lay = GT.family_layer(st)
    F = set(lay["ids"])
    nrep = GT.neutralise_referrers(st, F, t_use, name=rung.name)
    report["stages"].append({
        "stage": "1 (K3): null every USAGE field naming the loadable-family layer",
        "family_layer_size": len(F), "families": lay["families"],
        "children_by_class": lay["children_by_class"],
        "referrer_elements_edited": nrep["referrer_elements_edited"],
        "edits_by_referrer_class": nrep["edits_by_referrer_class"],
        "embedded_document_referrers_not_edited": nrep["embedded_document_referrers_not_edited"],
        "verify": nrep["verify"], "seconds": round(time.time() - t0, 1)})
    log(f"   1: family layer {len(F):,} elements ({len(lay['families'])} loadable families); "
        f"usage referrers edited {nrep['referrer_elements_edited']} "
        f"({dict(nrep['edits_by_referrer_class'][:5])})")
    # ---- step 2 (K4): remove ALL embedded documents coherently -----------------
    t0 = time.time()
    _ranges, guid_of_unit = GT._unit_guid_map(t_use)
    all_guids = set(guid_of_unit)
    rrep = GT.remove_documents(t_use, t_docs, all_guids, reconcile_contenttable=True,
                               reconcile_familymgr=True)
    resid = GT._residual_guid_hits(t_docs, all_guids)
    report["stages"].append({
        "stage": "2 (K4): remove ALL embedded family documents coherently (units + "
                 "ContentDocuments + ContentTable + FamilyMgr = the four registries)",
        "documents_removed": len(all_guids),
        "units": [rrep.get("units_before"), rrep.get("units_after")],
        "contentdocs_entries": [rrep.get("cd_entries_before"), rrep.get("cd_entries_after")],
        "contenttable_records": [rrep.get("contenttable_records_before"),
                                 rrep.get("contenttable_records_after")],
        "familymgr_entries": [rrep.get("familymgr_entries_before"),
                              rrep.get("familymgr_entries_after")],
        "residual_guid_bytes": sum(resid.values()), "seconds": round(time.time() - t0, 1)})
    log(f"   2: documents removed {len(all_guids)} (units {rrep.get('units_before')}->"
        f"{rrep.get('units_after')}, CD {rrep.get('cd_entries_before')}->"
        f"{rrep.get('cd_entries_after')}, ContentTable "
        f"{rrep.get('contenttable_records_before')}->{rrep.get('contenttable_records_after')}, "
        f"FamilyMgr {rrep.get('familymgr_entries_before')}->"
        f"{rrep.get('familymgr_entries_after')}); residual GUID bytes {sum(resid.values())}")
    # ---- step 3: maxgc-delete the (now reference-free) family layer ------------
    t0 = time.time()
    st2 = RR.build_state_v2(t_docs)
    L = {e for e in F if e in st2["host"]}
    L |= {e for e in st2["host"] if st2["cls_of"].get(e) == "LegendComponent"}
    L = RR._protect_history(st2, L)
    delete, kept, ev = RR.maxgc(st2, L)
    delete_elements(t_docs, out, delete)
    struct_ok = verify_reduced(out, delete)
    report["stages"].append({
        "stage": "3: delete the reference-free family layer (+ depicting legend components) "
                 "by maximal garbage collection",
        "seed": len(L), "deleted": len(delete), "kept_pinned": len(kept),
        "deleted_by_class": GT._class_hist(st2, delete),
        "kept_by_class": GT._class_hist(st2, kept),
        "pin_evidence": ev, "seconds": round(time.time() - t0, 1)})
    log(f"   3: layer seed {len(L):,} -> deleted {len(delete):,} (kept/pinned {len(kept)}); "
        f"structural ok {struct_ok.get('ok')}")
    for tmp in (t_use, t_docs):
        try:
            os.remove(tmp)
        except OSError:
            pass
    # ---- certification -----------------------------------------------------------
    val = _validate(out)
    cen = _census(out)
    report["structural"] = {k: struct_ok.get(k) for k in ("ok", "crc_failures", "ecc_mismatches",
                                                        "counts_match", "seq_id_sets_equal",
                                                        "stamps_bad", "isize_identity_ok")}
    report["structural"]["walker_errors"] = len(struct_ok.get("walker_errors") or [])
    report["validator"] = val
    report["census"] = cen
    report["coherence"] = {
        "save_units": cen.get("save_units"), "contentdocs_entries": cen.get("contentdocs_entries"),
        "contenttable_records": cen.get("contenttable_records"),
        "familymgr_entries": cen.get("familymgr_entries"),
        "familymgr_doc_guids": cen.get("familymgr_doc_guids"),
        "coherent": (cen.get("save_units", 0) - 1 == cen.get("contentdocs_entries")
                     == cen.get("contenttable_records")),
    }
    report["bytes"] = os.path.getsize(out)
    report["seconds"] = round(time.time() - t_all, 1)
    problems = []
    if not (val.get("ok") and val.get("errors") == 0):
        problems.append(f"validator errors={val.get('errors')}")
    if not struct_ok.get("ok"):
        problems.append("structural proof failed")
    if not report["coherence"]["coherent"]:
        problems.append("four-registry document coherence broken")
    if sum(resid.values()):
        problems.append(f"{sum(resid.values())} residual document-GUID byte(s)")
    report["problems"] = problems
    report["verdict"] = "VALID" if not problems else "NOT-CLEAN"
    if problems:
        report["FAILED_SELF_CHECK"] = "; ".join(problems)
    _write_report(out_dir, rung.name, report)
    log(f"   validator: {'VALID' if val.get('ok') else 'INVALID'} errors={val.get('errors')} "
        f"warnings={val.get('warnings')}; coherence {report['coherence']['save_units']}/"
        f"{report['coherence']['contentdocs_entries']}/{report['coherence']['contenttable_records']}/"
        f"{report['coherence']['familymgr_doc_guids']}")
    log(f"   -> {_relp(out)} {report['bytes']:,} B  VERDICT {report['verdict']}"
        f"{('  *** ' + report['FAILED_SELF_CHECK']) if problems else ''} ({report['seconds']}s)")
    return report


# ===========================================================================
# 6c. Xn -- the RESIDUE CHECK (report rung)
# ===========================================================================
#: our substitution ids all live in bands >= X1's band start; K1's own
#: elements sit at or below its watermark (1,472,524) -- a clean split
_OUR_ID_FLOOR = 1_500_000

#: residue reasoning: class (or class group) -> (bucket, reason)
_RESIDUE_REASONS: List[Tuple[Set[str], str, str]] = [
    ({"Family", "SysPanelFamSym", "SysMullionFamSym", "FamilySurrogate", "FamSymSurrogate",
      "StairsTriserSymbol", "FamilySymbol", "SlaveSymbolTrackerElem", "DBViewType",
      "PenWidthTableElem"},
     "curtain-systems(no-constructor)",
     "the 8 curtain-wall SYSTEM families + everything m_famId-scoped to them (their "
     "family-editor DBViewTypes, family pen tables, symbols/surrogates) -- NO our-constructor "
     "for curtain-system families (residue DBViewTypes / PenWidthTables here are the "
     "family-scoped ones; the project ones are OURS)"),
    ({"CategoryElem"},
     "gap-X6b",
     "project + curtain-scoped SUBCATEGORY records (Revit's auto-created angle-bracket "
     "line styles + template subcategories) -- the X6b GAP: no our-constructor for the "
     "built-in subcategory layer"),
    ({"GStyleElem"},
     "gap-X6b+family-scoped",
     "the project SUBCATEGORY style rows (X6b gap) + the curtain systems' family-scoped "
     "rows -- the 1,407 built-in rows themselves ARE ours (X6a)"),
    ({"DimensionStyle", "LeaderStyle", "SectionAttributes", "CalloutTag",
      "InteriorElevAttributes", "ViewportAttributes", "GridAttributes",
      "SpotElevationStyle", "FilledRegionAttributes", "TextNoteAttributes",
      "TagNoteAttributes", "MultiSegmentGridType", "LinearDimString"},
     "no-constructor",
     "annotation ATTRIBUTE types (dimension / arrowhead / view-tag types; the "
     "family-scoped ones belong to the curtain systems) -- no our-constructor"),
    ({"FontElem"},
     "no-constructor",
     "fonts of the residue annotation types (our text types brought their own)"),
    ({"Grid", "MultiSegGrid", "RefPlane", "CurveElem", "SketchPlane", "LegendComponent"},
     "content-removal-candidate",
     "sample datum / model-line / legend content (grids, reference planes, area "
     "boundary lines, model sketch planes, legend graphics) -- placeable CONTENT: a "
     "removal rung, or our datum constructors (skeleton has grids/refplanes) as a "
     "content rung"),
    ({"ParamElemExternal", "ParamBinding", "ParamElemProject",
      "ParamElemElectricalLoadClassification", "PropertySetLibrary"},
     "definitions-removal-candidate",
     "the sample's PARAMETER DEFINITIONS + category bindings (shared / project "
     "parameters; the R10 param-defs class group) -- a GC-removal rung or a "
     "parameter-definition constructor"),
    ({"HVACLoadSpaceTypeElem", "HVACLoadBuildingTypeElem", "HVACLoadScheduleElem",
      "BuildingOperatingYearSchedule"},
     "product-data",
     "Autodesk's HVAC / energy space-type + schedule DATABASE (product data; the "
     "singletons stream's rank-1 next constructor queue) -- counsel or removal"),
    ({"ElectricalLoadClassification", "ElectricalDemandFactorDefinition",
      "RbsWireMaterialType", "RbsWireTemperatureRatingType", "RbsWireInsulationType",
      "RbsVoltageType", "RbsDistributionSysType", "RbsWireType", "CustomElement"},
     "constructor-exists",
     "the electrical wire / load catalog -- our types-stream constructors EXIST "
     "(voltage / distribution / load-class / wire / conductor cells): a catalog rung"),
    ({"PipeSegment", "RbsPipeScheduleType", "RbsPipeMaterialType", "RbsPipeConnectionType",
      "RbsPipingSystemType", "RbsFluidType", "RbsPipeType", "RbsFlexPipeType",
      "ConduitStandardType", "RbsConduitType", "RbsCableTrayType", "RbsCableType",
      "ConduitSizesElem", "CableTraySizesElem", "AbsDuctType", "AbsFlexDuctType",
      "RbsHvacSystemType", "MechanicalEquipmentSetType", "MEPSystemZoneElementType",
      "MEPSystemZoneType", "MEPAnalyticalConnectionElementType"},
     "constructor-partial",
     "the piping / duct / conduit / cable-tray / fluid catalogs -- partly constructible "
     "(conduit + tray constructors exist; pipe schedules / fluids do not): a catalog rung"),
    ({"BasicWallType", "FloorAttributes", "RoofAttributes", "CompoundCeilingType",
      "RoofSoffitType", "StackedWallType", "NewCurtainWallType", "StairsType",
      "StairsRunType", "StairsLandingType", "StairsSupportType", "StairsPathType",
      "TopRailType", "HandRailType", "ContFootingType", "CoverType", "ToposolidType",
      "BuildingPadType", "AreaReinforcementType", "RebarBarType", "RebarShape",
      "RebarHookType", "RebarBendingDetailType", "FabricSheetType", "FabricAreaType",
      "FabricWireType", "AnalyticalLinkType", "StructConnectionType", "LineLoadType",
      "AreaLoadType", "CutMarkType", "ComponentRepeaterSlotSpecialType", "CustomElementType"},
     "constructor-partial",
     "the sample's SYSTEM FAMILY TYPES (wall/floor/roof/ceiling/stair/rebar...) -- our "
     "house catalog HAS wall/floor/roof/ceiling type constructors: a system-types rung; "
     "the structural / stair types have none"),
    ({"ColorFillSchema", "ColorFillSymbol", "TilePatternType", "DivisionRule",
      "ConceptualConstructionType", "ConceptualSurfaceType", "ListConceptualSurfaceTypes",
      "LoadCaseElem", "LoadNatureElem", "AreaTypeElem", "AreaSchemePlanTopologies",
      "AllPlanTopologies", "PlanTopology", "NumberingSchema", "AssemblyCodeTable",
      "DesignOption", "DesignOptionSet", "AreaReportSettingsElem", "GraphSchedColumnTable",
      "PropertyAttr", "CorniceAttr", "CurtaSystemAttr", "CurtainRoofAttributes",
      "EdgeSlabAttr", "FasciaAttr", "GutterAttr", "JoistSystemAttr", "RampAttributes",
      "RevealAttr", "RevisionCloudAttr", "StairsAttributes", "StairsRailingAttr",
      "ContourLabelingAttributes", "ReferenceViewerAttributes",
      "RepeatingDetailAttributes", "Text3dAttrSymbol", "MasterImportSymbol",
      "ImportInstance", "ImageSymbol", "ImageHolder", "DataStorage", "MEPNetworkDataElem",
      "ParameterFilterElement", "PropertySetElement", "AreaScheme"},
     "no-constructor",
     "misc analysis / massing / area-scheme / rebar-attribute / design-option / import "
     "machinery -- no our-constructor (colour-fill schemas, load cases, conceptual "
     "constructions, area types, numbering schemas, the UniFormat table...)"),
    ({"RvtLinkInstance", "RvtLinkSymbol", "LinkLoadTable"},
     "external-link-removal-candidate",
     "a LINKED REVIT MODEL reference (the sample's site link -- names an external "
     "Autodesk file) -- REMOVE (a link removal rung; the keynote table / copy-watch "
     "wiring we own no longer depends on it)"),
]


def _residue_reason(cls_name: str) -> Tuple[str, str]:
    for classes, bucket, reason in _RESIDUE_REASONS:
        if cls_name in classes:
            return bucket, reason
    return ("unclassified", "not yet classified -- inspect")


def run_residue_census(rung: Rung, subject_path: str, out_dir: str = SUBST, *,
                       ledger: bool = True) -> dict:
    """Xn: the RESIDUE CHECK of the deepest built rung -- which Autodesk-
    authored elements remain in the file after every substitution?  Every
    host element is OURS (id in a substitution band, >= 1,500,000) or a
    K1-inherited RESIDUE (an original sample id); the residue is grouped by
    class with the reason it is still there (a named constructor gap, a
    removal candidate, product data, or a class an earlier rung deferred).
    Also runs the provenance ledger (streams + bytes) for the container-
    layer picture.  Report only (Xn.json); the file to viewer-test is the
    subject rung's .rvt."""
    t_all = time.time()
    log(f"\n== {rung.name} :: {rung.label}")
    log(f"   subject {_relp(subject_path)}")
    doc = Document.from_file(subject_path)
    k1_ids: Set[int] = set()
    try:
        k1_ids = {int(r) for r in Document.from_file(K1).et_by_id}
    except Exception:
        pass
    ours: Counter = collections.Counter()
    residue: Counter = collections.Counter()
    unknown: Counter = collections.Counter()
    for e in doc.et_by_id:
        cls_name = doc.class_of(e) or "?"
        if e >= _OUR_ID_FLOOR:
            ours[cls_name] += 1
        elif e in k1_ids or not k1_ids:
            residue[cls_name] += 1
        else:
            unknown[cls_name] += 1
    buckets: Dict[str, dict] = {}
    for cls_name, n in residue.most_common():
        bucket, reason = _residue_reason(cls_name)
        b = buckets.setdefault(bucket, {"elements": 0, "classes": {}, "reason_examples": []})
        b["elements"] += n
        b["classes"][cls_name] = n
        if len(b["reason_examples"]) < 3 and reason not in b["reason_examples"]:
            b["reason_examples"].append(reason)
    residue_rows = [{"class": c, "count": n, "bucket": _residue_reason(c)[0],
                     "reason": _residue_reason(c)[1]} for c, n in residue.most_common()]
    report: Dict[str, Any] = {
        "rung": rung.name, "label": rung.label, "kind": rung.kind,
        "subject": _relp(subject_path), "parent_rung": rung.parent,
        "description": rung.description, "tests": rung.tests,
        "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
        "elements_total": len(doc.et_by_id),
        "ours": {"elements": sum(ours.values()), "classes": len(ours),
                 "by_class": dict(ours.most_common())},
        "residue": {"elements": sum(residue.values()), "classes": len(residue),
                    "by_bucket": buckets, "table": residue_rows},
        "unknown_origin": dict(unknown),
        "genesis_candidate": (_relp(subject_path) if sum(residue.values()) == 0 else None),
        "stages": [],
    }
    log(f"   elements {len(doc.et_by_id):,}: OURS {sum(ours.values()):,} "
        f"({len(ours)} classes), K1-inherited RESIDUE {sum(residue.values()):,} "
        f"({len(residue)} classes){', unknown ' + str(sum(unknown.values())) if unknown else ''}")
    for bkt, b in sorted(buckets.items(), key=lambda kv: -kv[1]["elements"]):
        top = dict(sorted(b["classes"].items(), key=lambda kv: -kv[1])[:6])
        log(f"      {bkt:34s} {b['elements']:5d}  {top}")
    # ---- the container-layer picture: provenance ledger v2 --------------------
    if ledger:
        t0 = time.time()
        try:
            rep = GA.run_ledger_v2(subject_path,
                                   json_out=os.path.join(out_dir, f"{rung.name}_provenance.json"))
            summ = GA.summarize_ledger(rep)
            report["provenance_ledger"] = summ
            gl = summ.get("global_latest") or {}
            report["stages"].append({"stage": "provenance ledger v2 (--baseline all --streams)",
                                     "seconds": round(time.time() - t0, 1)})
            log(f"   ledger: gate {str(summ.get('gate_verdict'))[:80]}")
            log(f"           bytes identical-to-baseline {summ['bytes']['identical_pct']}% "
                f"(excl. schema {summ['bytes']['excluding_schema_identical_pct']}%); ours "
                f"{summ['bytes']['ours_pct']}%; Global/Latest {gl.get('inflated'):,} B "
                f"{gl.get('identical_pct')}% identical ({gl.get('class')}); elements "
                f"{summ['elements']['totals']}; identity ok={summ['identity_ok']}")
        except Exception as ex:                                   # ledger is advisory
            report["provenance_ledger_error"] = repr(ex)[:400]
            log(f"   ledger: skipped ({ex!r})")
    report["seconds"] = round(time.time() - t_all, 1)
    report["verdict"] = "GENESIS-CANDIDATE" if sum(residue.values()) == 0 else "RESIDUE-LISTED"
    _write_report(out_dir, rung.name, report)
    log(f"   -> {rung.name}.json  VERDICT {report['verdict']} ({report['seconds']}s)")
    return report


# ===========================================================================
# 7. the rung table + driver
# ===========================================================================

RUNGS: List[Rung] = [
    Rung(name="X1", label="PenWidthTableElem (the project pen table, id 2) -> ours",
         parent="K1", kind="substitute", build=build_X1,
         description=("K1 (Autodesk's empty-project skeleton, viewer PASS) with its REAL "
                      "project pen table (PenWidthTableElem id 2, m_famId -1 -- the "
                      "skeleton census's #1 singleton suspect, K5a's class) REPLACED by "
                      "OUR pen table (settings.pen_width_table: our ISO-128-based line-"
                      "weight series over our imperial scale breakpoints).  The one registry "
                      "leaf that named it (PenWidthTableInfo.m_penWidthTableElemId) now "
                      "names ours -- same registry, same slot, our id.  The 8 family-scoped "
                      "pen tables are the curtain SYSTEM families' and stay until the family "
                      "rung."),
         tests=("Whether the reader accepts OUR pen table in the exact registry slot the "
                "sample's occupied, on the otherwise-Autodesk skeleton (S1 tested our pen "
                "table on the FAILING G1 base and could not attribute the FAIL)."),
         if_pass=("Our PenWidthTableElem constructor + its registry wiring are reader-"
                  "accepted; the pen table is retired from the constructed-base suspect "
                  "list; X2 reads cleanly."),
         if_fail=("Our pen table (or its registration) is what the reader rejects -- the "
                  "first named defect in OUR constructors: diff our record vs Autodesk's "
                  "id 2 field by field.")),
    Rung(name="X2", label="BrowserOrganization set + system-navigator constellation -> ours",
         parent="X1", kind="substitute", build=build_X2,
         description=("X1 with the whole project-browser layer REPLACED: the 11 sample "
                      "BrowserOrganizations -> OUR scheme (the 4 REQUIRED per-tree 'all' "
                      "defaults + our 2 house schemes), the MEP system-navigator view + its "
                      "Viewer/Viewport/DBDrawing -> OUR navigator constellation (wired to "
                      "the same phases / units / workset-visibility / MEP tracker the "
                      "sample's was), ReconcileBrowserSettingsElem + ConstructionSetProject "
                      "-> ours.  DBViewProject's four regen edges and the "
                      "BrowserOrganizationTracking per-tree default map are re-pointed to "
                      "OUR defaults; DBViewInfo.m_DBViewSystemNavigatorId + the views / "
                      "drawings indexes are re-pointed to our navigator constellation; the "
                      "seven Autodesk browser schemes ('not on sheets', 'Phase', ...) are "
                      "deleted; our two house schemes are appended to the tracking set."),
         tests=("Whether the reader accepts OUR browser-organization scheme + OUR MEP "
                "system-navigator view constellation (K5b's classes) in place of the "
                "sample's, with every registry that indexed the originals re-pointed."),
         if_pass=("Our browser / navigator constructors and their four registries "
                  "(BrowserOrganizationTracking, DBViewInfo, DBDrawingInfo, "
                  "AppInfoSystemFamiliesNames) are reader-accepted."),
         if_fail=("One of our browser / navigator constructions is rejected -- bisect: "
                  "an X2a with only the browser organizations replaced (navigator kept) "
                  "vs an X2b with only the navigator replaced.")),
    Rung(name="X3", label="StructSettings / wall-join / auto-join / keynote / initial-view -> ours",
         parent="X2", kind="substitute", build=build_X3,
         description=("X2 with the charter's named singletons REPLACED by ours: "
                      "StructSettingsElem (our imperial structural conventions, keeping the "
                      "sample's wiring to its still-present brace / boundary-condition "
                      "symbols), WallJoinDefaultSetting, AutoJoinTracker, KeynoteTable "
                      "(OURS = EMPTY: Autodesk's shipped 3,840-row keynote database is NOT "
                      "reproduced) + KeynotingSystem, InitialViewSettings (starting view "
                      "kept).  Their UniqueElementsTracking slots + KeynoteTable/"
                      "KeynotingSystem tracking sets are remapped in place; the "
                      "RvtLinkInstance that names the keynote table is re-pointed."),
         tests=("Whether the reader accepts our structural / join / keynote / start-view "
                "singletons (incl. an EMPTY keynote table) in their exact registry slots."),
         if_pass=("The named singleton constructors are reader-accepted (and an empty "
                  "keynote table is legal)."),
         if_fail=("One of these five constructors is rejected -- bisect X3a (keynote pair "
                  "only) / X3b (StructSettings only) / X3c (the rest).")),
    Rung(name="X4", label="Rbs* settings + sizes tables (wire/duct/pipe/conduit/cable-tray) -> ours",
         parent="X3", kind="substitute", build=build_X4,
         description=("X3 with the MEP settings + size-table singletons REPLACED by ours: "
                      "RbsWire/Pipe/DuctSettingsElem (our routing / annotation conventions, "
                      "keeping the sample's per-classification type wiring), "
                      "RbsWire/Pipe/DuctSizesElem (OUR data: NEC ampacity tables, ASME "
                      "B36.10/B36.19 + ASTM B88 pipe dimensions, our SMACNA duct series -- "
                      "keyed onto the parent's still-present wire / pipe catalog symbols by "
                      "name), Conduit/CableTraySettingsElem.  Their UET slots are remapped; "
                      "the MEP tracker constellation's regen edges into the duct / pipe "
                      "settings are re-pointed to ours.  The MEP catalogs (wire material, "
                      "pipe schedule, conduit-standard symbols) STAY (a later rung)."),
         tests=("Whether the reader accepts our MEP settings singletons and OUR size-table "
                "DATA in the settings singletons' registry slots."),
         if_pass=("Our MEP settings / sizes constructors are reader-accepted."),
         if_fail=("One of the eight is rejected -- bisect settings vs sizes vs the "
                  "conduit/cable-tray pair.")),
    Rung(name="X5", label="every remaining settings singleton / tracker with a constructor -> ours",
         parent="X4", kind="substitute", build=build_X5,
         description=("X4 with EVERY other settings singleton / tracker OUR standard "
                      "constellation constructs REPLACED by ours (the MEP tracker "
                      "constellation, GCS / assembly / keynote-tags / revision-clouds / "
                      "sheet-collection trackers, revisions + numbering sequences, print "
                      "settings, worksharing / export / area / energy / reinforcement / "
                      "route-analysis / fabrication settings, model graphics styles, area "
                      "schemes, the remaining SYSTEM view types...), each in its exact "
                      "registry slot; the parent's settings classes WITHOUT a constructor are "
                      "LISTED in the report's residue (Autodesk-authored, left in place -- the "
                      "honest finding, never a silent keep)."),
         tests=("Whether the reader accepts the WHOLE our-settings constellation on the "
                "otherwise-Autodesk skeleton -- the S5-set question, now attributable "
                "because everything else in the file already loads."),
         if_pass=("Every settings constructor we own is reader-accepted; what remains is the "
                  "residue list (constructors we do not have yet)."),
         if_fail=("A constructor added at X5 is rejected -- bisect X5 by the constellation's "
                  "tiers (mep / trackers / revisions / view types).")),
    Rung(name="X10", label="loadable-family layer + ALL embedded documents removed coherently",
         parent="X5", kind="removal", build=lambda ctx: (_ for _ in ()).throw(
             RuntimeError("X10 is a removal rung (run_family_removal)")),
         description=("X5 with the ENTIRE loadable-family layer (the annotation heads, tags, "
                      "title block, boundary-condition and column families + their symbols, "
                      "surrogates and every m_famId-scoped child) AND ALL embedded family "
                      "documents removed together and coherently -- the genesis-triage K3 "
                      "(usage fields nulled) + K4 (documents + layer removed, all FOUR "
                      "document registries reconciled) operations, BOTH viewer-PASSED (K4 "
                      "PASS: families are NOT required).  DERIVED before the catalog rung "
                      "because 1,421 built-in-catalog referrers live INSIDE the embedded "
                      "documents (uneditable) -- the catalog cannot be substituted while the "
                      "documents pin it.  The curtain-wall SYSTEM families (no documents) stay; "
                      "our own annotation-head families can be re-added later via rvt.famload "
                      "(the loader proven by L1a PASS) once the base itself is proven."),
         tests=("K4's zero-family / zero-document operation, re-applied to OUR partially-"
                "substituted base: does the coherent removal still open when the settings layer "
                "is already ours?"),
         if_pass=("The family/document removal composes with our settings layer; the catalog "
                  "rungs (X6..) are now buildable (nothing embedded pins the catalog)."),
         if_fail=("(K4 itself PASSED on the pure sample) => an interaction between the removal "
                  "and one of our X1..X5 substitutions -- re-check the usage referrers we own "
                  "(our StructSettings' bc symbols, our navigator's style refs).")),
    Rung(name="X6a", label="built-in-category GStyle catalog (1,407 rows) -> OUR complete catalog",
         parent="X10", kind="substitute", build=build_X6a,
         description=("X10 with the ENTIRE built-in-category object-styles table REPLACED: every "
                      "project-level GStyleElem row of a built-in category (1,074 projection + "
                      "333 cut = Autodesk's default pen / colour / pattern table -- the class "
                      "K6's FAIL proved the reader requires COMPLETE) -> OUR row of the SAME "
                      "(category, style-type) from catalog.builtin_style_catalog (the "
                      "registered per-release graphic-category ENUM, valued by OUR discipline "
                      "scheme; 0 rows value-identical to Autodesk's table).  A perfect 1:1: "
                      "every view / curve / curtain-symbol reference and every "
                      "CategoryTracking category->style registry row (the map P4/P6/K6 proved "
                      "is walked at load) is re-pointed to our row of the same (category, "
                      "type).  The project SUBCATEGORY / line-style layer (349 CategoryElem "
                      "records + 509 style rows, incl. Revit's angle-bracket auto line styles) "
                      "STAYS -- no our-constructor exists for it: that is the X6b GAP, named in "
                      "the report, and it rides along as residue in every later rung."),
         tests=("Whether the reader accepts OUR object-styles table -- the S4/K6 question -- when "
                "everything else that must reference it is re-pointed correctly (S4 tested our "
                "catalog on the FAILING base and could not attribute the FAIL)."),
         if_pass=("Our complete built-in style catalog + its CategoryTracking registration are "
                  "reader-accepted: the catalog counsel item (a full table over their enum, our "
                  "values) is the only remaining decision, no longer an engineering unknown."),
         if_fail=("Our catalog is what the reader rejects -- the FIRST viewer verdict that "
                  "attributes a FAIL to our catalog specifically. Candidates in order: a "
                  "(category, type) row we emit that a real project never carries (see "
                  "'ours_only_keys'), a value the reader validates (pen index range, colour), "
                  "or the CategoryTracking row shape.")),
    Rung(name="X7", label="line/fill patterns + materials (+ asset companions) -> our palette",
         parent="X6a", kind="substitute", build=build_X7,
         description=("X6a with the whole graphic-material palette REPLACED: every "
                      "LinePatternElem / FillPatternElem / MaterialElem (Autodesk's drafting "
                      "patterns, their material library incl. 'Default' and the phase "
                      "materials) plus the materials' companions (AppearanceAssetElem render "
                      "assets naming Autodesk's asset library, PropertySetElement thermal/"
                      "physical data, PropertySetLibrary) -> OUR palette (house_standard: 4 "
                      "line patterns, 5 fill patterns, 13 materials incl. our phase-override "
                      "materials; NO asset binding, NO property sets).  Correspondence is many-"
                      "to-one by ROLE (their 'Dash' variants -> our dash; 'Concrete 10 MPa' -> "
                      "our concrete; 'Phase - Demo' -> our demolition material); every wall/"
                      "floor/roof type, pipe segment, phase filter, colour-fill schema and "
                      "subcategory line style is re-pointed by role or neutralised (-1 = "
                      "solid / by-category)."),
         tests=("Whether the reader accepts OUR pattern + material palette in place of "
                "Autodesk's, incl. two token questions: our solid fill under our own name (not "
                "'<Solid fill>') and no 'Default'-named material."),
         if_pass=("Our patterns / materials and the by-role re-pointing are reader-accepted; "
                  "no name token is required for the solid fill or the default material."),
         if_fail=("Bisect: X7a (patterns only) vs X7b (materials only); if a token is the "
                  "cause, rename our solid fill to '<Solid fill>' / add a 'Default' material "
                  "and re-test -- that names a REQUIRED TOKEN for the counsel list.")),
    Rung(name="X8", label="units + true north + sites / geo-locations + base points + project info -> ours",
         parent="X7", kind="substitute", build=build_X8,
         description=("X7 with the document identity + site layer REPLACED: UnitsElem (our unit "
                      "formats), TrueNorth (our angle / poche), the GeoSite + GeoLocation "
                      "pairs (OUR site: latitude / longitude / climate; project + internal "
                      "positions), the project base point + survey point, and ProjectInfo "
                      "(OUR project information) -> ours from the house catalog.  Every "
                      "regen-edge into the sample's units (levels, GCS tracker, navigator, "
                      "views) and every geo-location reference (the base points, our X5 "
                      "ActiveGeoLocationTracking) is re-pointed."),
         tests=("Whether the reader accepts our units registry, site/geo-location pair, base "
                "points and project-info in place of the sample's, with every regen edge into "
                "the units re-pointed."),
         if_pass=("Our identity + site constructors are reader-accepted."),
         if_fail=("Bisect X8a (units only -- the highest fan-in element in the document) vs "
                  "X8b (site / geo-locations / base points) vs X8c (project info).")),
    Rung(name="X9", label="the document skeleton: levels + phases + filters + view types + all views -> ours",
         parent="X8", kind="substitute", build=build_X9,
         description=("X8 with the whole document SKELETON layer REPLACED in ONE coherent step "
                      "(views are bound to levels, so they are substituted together): every "
                      "level + the level type, the phases + AllProjectPhases (phasing "
                      "overrides re-wired to OUR X7 phase materials) + phase filters, the "
                      "document sun, all 19 PROJECT DBViewTypes (by m_systemFamilyIdx), and "
                      "EVERY view constellation (project view, 3D views, plans, sections, "
                      "elevations, drafting/legend/rendering views + their viewers, viewports, "
                      "drawings, extents, clip boxes, sketch planes, per-view suns, light "
                      "schemes) + the SYSTEM text types -> OUR skeleton from the house catalog "
                      "(2 storey levels, 2 phases + set + 5 filters, our sun, our 19 view "
                      "types, our project-view + 3D + 2 plan constellations, our 3 text "
                      "types).  Correspondence: project view / '{3D}' / the two lowest-storey "
                      "plans -> ours (their levels -> our L1/L2), phases by order, filters "
                      "by role, view types by family, the default text type -> our body "
                      "text; the DBView registries (project view, views index, navigator, "
                      "view types for new levels, default types) re-pointed / purged.  "
                      "Residue: curtain-family view types, dimension/leader/view-tag types, "
                      "fonts, grids/reference planes."),
         tests=("Whether the reader accepts OUR complete document skeleton -- the layer G0/G1 "
                "were BUILT from (K2 proved the sample's own view minimality legal; this "
                "tests OUR views + levels + phases on the passing base)."),
         if_pass=("Our skeleton is reader-accepted: the constructed-base defect is NOT in our "
                  "level / phase / view constructors -- what remains is the Xn residue "
                  "(curtain systems, annotation types, datum content, the subcategory layer)."),
         if_fail=("Our skeleton layer is where the reader objects -- the G0/G1 FAIL's most "
                  "likely home. Bisect: X9a (view types only), X9b (views only, levels "
                  "kept), X9c (levels + phases only), reading the card message each time.")),
    Rung(name="Xn", label="the RESIDUE CHECK -- what Autodesk-authored elements remain after X9",
         parent="X9", kind="report",
         build=lambda ctx: (_ for _ in ()).throw(
             RuntimeError("Xn is a report rung (run_residue_census)")),
         description=("A census of the deepest built rung (X9): every host element is OURS "
                      "(a substitution band id, >= 1,500,000) or a K1-inherited RESIDUE (an "
                      "original sample id), the residue grouped by class with the REASON it "
                      "is still there -- a named constructor gap (curtain systems, the "
                      "subcategory layer, annotation types), a removal candidate (datum "
                      "content, parameter definitions, the linked model), product data "
                      "(HVAC database), or a catalog / system-types rung not yet run -- plus "
                      "the provenance ledger for the CONTAINER layer (Formats/Latest schema, "
                      "History lineage, the Forge corpus inside Global/Latest -- Autodesk "
                      "bytes NO element-layer rung addresses; the own-save / counsel "
                      "territory).  Report only: the file to viewer-test is X9.rvt.  If the "
                      "residue were EMPTY, Xn WOULD BE the genesis candidate; it is not, and "
                      "the list is the work queue."),
         tests="(report -- nothing to viewer-test beyond X9)",
         if_pass="n/a", if_fail="n/a"),
]


def rung_by_name(name: str) -> Rung:
    for r in RUNGS:
        if r.name == name:
            return r
    raise KeyError(name)


def parent_path_of(rung: Rung) -> str:
    if rung.parent == "K1":
        return K1
    return os.path.join(SUBST, f"{rung.parent}.rvt")


# ===========================================================================
# 8. probes.json (the upload manifest, in DERIVATION order)
# ===========================================================================

def write_probes_manifest(out_dir: str = SUBST) -> str:
    entries = []
    residue_summary = None
    for rung in RUNGS:
        p = os.path.join(out_dir, f"{rung.name}.json")
        rep = {}
        if os.path.exists(p):
            with open(p) as fh:
                rep = json.load(fh)
        v = rep.get("validator") or {}
        par = rep.get("parity") or {}
        if rung.kind == "report":
            # the residue check: no file of its own; summarize its findings
            res = rep.get("residue") or {}
            residue_summary = {
                "subject": rep.get("subject"), "verdict": rep.get("verdict", "not built"),
                "elements_total": rep.get("elements_total"),
                "ours": (rep.get("ours") or {}).get("elements"),
                "residue_elements": res.get("elements"),
                "residue_by_bucket": {k: {"elements": vv.get("elements"),
                                          "classes": vv.get("classes")}
                                      for k, vv in (res.get("by_bucket") or {}).items()},
                "container_layer_ledger": rep.get("provenance_ledger"),
                "report": f"experiments/genesis/subst/{rung.name}.json",
            }
            entries.append({
                "file": None, "rung": rung.name, "order": len(entries) + 1,
                "class_substituted": rung.label, "kind": "report",
                "derived_from": rep.get("subject") or _relp(parent_path_of(rung)),
                "parent_rung": rung.parent,
                "verdict": rep.get("verdict", "not built"),
                "report": f"experiments/genesis/subst/{rung.name}.json",
                "note": "report rung -- viewer-test its subject file (X9.rvt), not this",
            })
            continue
        entries.append({
            "file": f"experiments/genesis/subst/{rung.name}.rvt",
            "rung": rung.name,
            "order": len(entries) + 1,
            "kind": rung.kind,
            "class_substituted": rung.label,
            "derived_from": (rep.get("parent") or _relp(parent_path_of(rung))),
            "parent_rung": rung.parent,
            "the_ONE_thing_it_tests": rung.tests,
            "if_PASS": rung.if_pass,
            "if_FAIL": rung.if_fail,
            "elements_removed": (rep.get("old") or {}).get("by_class"),
            "elements_added": (rep.get("new") or {}).get("by_class"),
            "registry_parity": ({"pairs": par.get("pairs"), "pairs_ok": par.get("pairs_ok"),
                                 "uet_slots_ok": (len(par.get("positional_uet_slots") or [])
                                                  - int(par.get("uet_failed") or 0)),
                                 "old_ids_left_in_adocument": len(par.get("old_ids_still_in_adocument") or {}),
                                 "new_dangling_created": len(par.get("adocument_dangling_created") or [])}
                                if par else None),
            "referrers_repointed": (rep.get("referrer_repoint") or {}).get("referrer_elements"),
            "residue_left_in_place": rep.get("residue_left_in_place"),
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"),
                          "warnings": v.get("warnings")},
            "structural_ok": (rep.get("structural") or {}).get("ok"),
            "document_coherence": rep.get("coherence"),
            "verdict": rep.get("verdict", "not built"),
            "self_check": rep.get("FAILED_SELF_CHECK"),
            "bytes": rep.get("bytes"),
            "report": f"experiments/genesis/subst/{rung.name}.json",
        })
    manifest = {
        "stream": "genesis-substitute (THE SUBSTITUTION LADDER -- constructive twin of the "
                  "reduction ladder; the path that cannot dead-end)",
        "situation": (
            "Every reduction of Autodesk's sample skeleton LOADS (R5, R9, K1, K3, K4, KD1 "
            "PASS) and every constructed base FAILS (G0/G1 set, and S1..S5 = G1_candidate + "
            "our singletons + our full catalog) with 'Revit-DocumentCorruption: The file "
            "is corrupt'.  The S-set tested our content ON THE SUSPECT BASE and could not "
            "separate 'our constructors are mis-shaped / mis-registered' from 'the G1 base "
            "carries an independent defect'.  This ladder ISOLATES by building on the "
            "PASSING side: starting from K1 (Autodesk's empty-project skeleton, viewer "
            "PASS) it REPLACES the sample's content with OUR constructors' output class by "
            "class, cumulatively.  Every rung derives from a PASSING file, re-points every "
            "referrer, re-points every ADocument registry to our ids EXACTLY as the "
            "sample's indexed the originals (parity ASSERTED, not assumed), and is validator-"
            "clean (0 errors).  The first rung the viewer REJECTS names the exact one of OUR "
            "constructors the reader disagrees with; a clean run to Xn IS the genesis base."),
        "the_operation": (
            "substitute(class): OLD = the parent's elements of the class (+ ownership "
            "constellation); NEW = our constructor's records wired to what the OLD "
            "referenced; every survivor referrer of an OLD id is re-pointed to the "
            "corresponding NEW id (schema-typed reference decoder, byte-exact record "
            "re-encode); OLD deleted + NEW appended through the proven writer path; every "
            "ElementId leaf of the ADocument holding an OLD id is remapped IN PLACE (same "
            "registry, same slot); parity + coherence + validator asserted per rung."),
        "start_base": {"K1": "experiments/genesis/triage/K1.rvt (Autodesk's empty-project "
                             "skeleton, viewer PASS -- the reference the ladder replaces)"},
        "known_failing_reference": {
            "G1_candidate": "experiments/genesis/G1_candidate.rvt (constructed base, viewer FAIL)",
            "S1..S5": "experiments/genesis/singletons/S*.rvt (our content on the FAILING base -- "
                      "all FAIL; this ladder tests the same content on the PASSING base)"},
        "reading_the_results": {
            "how": ("Upload the rungs IN ORDER (each is cumulative). The first rung that FAILS "
                    "while its parent PASSED convicts exactly the class group that rung "
                    "substituted -- ONE of our constructors, named in the rung's "
                    "'class_substituted'. Every rung's report carries the field-level "
                    "correspondence + registry-parity table for the diff."),
            "X1 FAIL": "our PenWidthTableElem (S1's own class) is the reader's objection: diff "
                       "our pen table vs Autodesk's id 2 field by field.",
            "X1 PASS, X2 FAIL": "our browser scheme / system-navigator constellation: bisect "
                                "the organizations from the navigator (X2a / X2b).",
            "X2 PASS, X3 FAIL": "one of the five named singletons (struct / wall-join / auto-"
                                "join / keynote pair / initial view): bisect X3a..c.",
            "X3 PASS, X4 FAIL": "our MEP settings or size-table DATA: bisect settings vs "
                                "sizes.",
            "X4 PASS, X5 FAIL": "a constructor of the wider settings constellation: bisect "
                                "X5 by tier (mep / trackers / revisions / view types).",
            "ALL of X1..X5 PASS": ("EVERY settings-singleton constructor we own is reader-"
                                   "accepted on the passing skeleton => the S5-set's FAIL "
                                   "on G1 was the G1 BASE, not our singletons (the singleton "
                                   "layer is retired). The genesis defect is in a layer this "
                                   "ladder reaches later: the catalog (X6), patterns/"
                                   "materials (X7), datums/phases (X8), views (X9), or the "
                                   "residue Xn lists."),
        },
        "derivation_order": [f"{r.name} <- {r.parent}" for r in RUNGS],
        "why_X10_before_X6": ("the family-layer removal (the brief's X10) is DERIVED right "
                              "after X5 because a measurement on the X5 base found 1,421 of "
                              "the built-in catalog rows' referrers INSIDE the embedded family "
                              "documents (uneditable by the host path) + 238 Family / 228 "
                              "FamilySymbol referrers: the catalog cannot be substituted while "
                              "the documents pin it. K3+K4 (the removal) are both viewer-"
                              "PASSED, so the reorder costs nothing and unblocks X6."),
        "upload_order": [r.name for r in RUNGS
                         if r.kind != "report"
                         and os.path.exists(os.path.join(out_dir, f"{r.name}.rvt"))],
        "residue_check": residue_summary,
        "probes": entries,
        "not_uploaded_intermediates": [
            ".<rung>.a_appended.rvt / .<rung>.b_repointed.rvt (pipeline stages, deleted "
            "unless --keep-intermediates)"],
    }
    p = os.path.join(out_dir, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"[probes] wrote {_relp(p)} ({len(entries)} probes)")
    return p


# ===========================================================================
# 9. driver
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", default="", help="comma list of rungs to build (X1,X2,...)")
    ap.add_argument("--manifest-only", action="store_true",
                    help="only (re)write probes.json from existing reports")
    ap.add_argument("--keep-intermediates", action="store_true",
                    help="keep the .a_appended / .b_repointed pipeline files")
    ap.add_argument("--no-ledger", action="store_true",
                    help="Xn: skip the (slow) provenance ledger")
    args = ap.parse_args(argv)
    want = [s.strip() for s in args.only.split(",") if s.strip()]
    t0 = time.time()
    results: Dict[str, dict] = {}
    if not args.manifest_only:
        chain = [r for r in RUNGS if (not want or r.name in want)]
        for rung in chain:
            parent = parent_path_of(rung)
            if not os.path.exists(parent):
                log(f"\n== {rung.name}: parent {_relp(parent)} missing -- SKIPPED "
                    f"(build {rung.parent} first)")
                continue
            try:
                if rung.kind == "removal":
                    results[rung.name] = run_family_removal(rung, parent)
                elif rung.kind == "report":
                    results[rung.name] = run_residue_census(rung, parent,
                                                             ledger=not args.no_ledger)
                else:
                    results[rung.name] = substitute(rung, parent,
                                                     keep_intermediates=args.keep_intermediates)
            except Exception as ex:                      # a rung that cannot build is a FINDING
                import traceback
                tb = traceback.format_exc()
                log(f"\n== {rung.name}: BUILD ABORTED -- {ex!r}\n{tb}")
                results[rung.name] = {"rung": rung.name, "label": rung.label,
                                      "verdict": "NOT-BUILT", "abort": repr(ex),
                                      "traceback": tb}
                _write_report(SUBST, rung.name, results[rung.name])
                out_bad = os.path.join(SUBST, f"{rung.name}.rvt")
                if os.path.exists(out_bad):
                    os.remove(out_bad)                    # never leave a half-built rung
                break                                     # the ladder stops here honestly
    write_probes_manifest()
    log("\n=== SUBSTITUTION LADDER SUMMARY ===")
    for rung in RUNGS:
        p = os.path.join(SUBST, f"{rung.name}.json")
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            rep = json.load(fh)
        v = rep.get("validator") or {}
        par = rep.get("parity") or {}
        log(f"  {rung.name:<4} {rep.get('verdict', '?'):<10} validator ok={v.get('ok')} "
            f"errors={v.get('errors')} warnings={v.get('warnings')}  parity "
            f"{par.get('pairs_ok', '?')}/{par.get('pairs', '?')}  "
            f"{rep.get('bytes', 0):>9,} B  {rung.label[:60]}")
    log(f"total {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
