#!/usr/bin/env python
"""genesis_substitute_v3.py -- THE SUBSTITUTION LADDER v3 (Y-rungs): the
X-rung machinery of ``tools/genesis_substitute.py`` REBASED onto a
viewer-CERTIFIED base and driven by IN-PLACE substitution.

WHY v3 EXISTS (docs/inbox/genesis-audit.md, ORCHESTRATOR VERDICTS #15,
2026-08-04 ~02:45 -- the RETRACTION).  Every X-rung (X1..X9 + X10) and every
S/R/C/P probe of the previous night derived from ``triage/K1.rvt`` -- the
'R5 minus the placed model' maximal-GC reduction that had NEVER itself been
uploaded and, once uploaded, FAILS the Autodesk reader on its own (crash exit
-1073741831, no 'Revit-DocumentCorruption' line, 'Design is empty'; XR_null,
byte-identical to K1, fails too).  Nothing K1-derived ever passed, so the
grand conclusions of verdicts #9..#14 ('constructed objects fail', 'the ADD
path is the bug', 'our values violate a value grammar', 'two independent
constraints') are RETRACTED artefacts of a broken base: our constructors,
the regadd add/substitute paths and our values are UNJUDGED, not condemned.
The substitution engine itself is sound machinery pointed at a broken base.
THIS TOOL RE-POINTS IT at a CERTIFIED base and makes every rung as clean a
probe as physics allows.

THE BASE.  Default ``experiments/genesis/triage/K4.rvt`` -- viewer-CERTIFIED
(docs/coverage/viewer-certified.json 'certified': "ZERO family documents
(all 52 removed, FOUR-registry coherent) LOADS => family documents NOT
required by the reader").  Lineage: rstbasicsampleproject -> R5 -> ... -> R9
(the deepest viewer-PASSED reduction, thousands of dangling refs tolerated)
-> K3 (loadable-family USAGE fields nulled, certified) -> K4 (the whole
family-document layer removed, four-registry coherent, certified).  K4 is
the IDEAL genesis base: the family/document layer is already gone -- exactly
what genesis wants -- 3,342 host elements, one save unit, and it LOADS.
The tool REFUSES to build on a base that is not listed as certified (this
is the STANDING CONTROLS DISCIPLINE of verdict #15c).

THE OPERATION -- PURE IN-PLACE SUBSTITUTION (``rvt.regadd.substitute_elements``,
the operation the substitution ladder actually needs).  For a class layer C on
a PASSING parent P:
  1. OUR constructor's records for C are built exactly as the X-ladder built
     them (tools/genesis_substitute build_X1..build_X9 are IMPORTED, never
     edited): our OBJECTS wired to P's own document ids.
  2. A CORRESPONDENCE old -> new (the X builders' role rules) becomes an
     IN-PLACE PLAN: each of our records is RE-TARGETED onto ONE existing
     element id of the same class -- its role correspondent (the most-
     referenced one when several share a role) or, for our records without
     a role slot, a free DONOR element of the same class ('slot-fill': the
     sample carries 23 materials, our palette 13 -> all 13 land in 13 of
     those slots).  Every cross-reference among our records is REMAPPED to
     the slots (schema-typed leaf walker, never a byte scan); references to
     our records that found NO slot are resolved by (class, name) against
     the CURRENT file or neutralised (reported, never silent).
  3. ONLY the seq-102 OBJECT record at each slot is replaced (default; a
     rung may opt into 101/103): same ElementId, same ElemTable row
     (episodes / owner / vintage byte-identical), same record POSITION in
     each seq stream, same registry slots -- Global/Latest (the ADocument)
     and Global/ElemTable are BYTE-IDENTICAL to the parent.  NOTHING is
     added, NOTHING is deleted: the sample's surplus instances and our
     slot-less records are LISTED (the residue / not-landed queues), never
     silently kept or dropped.  This is 'the cleanest possible probe': the
     ONE variable is the OBJECT CONTENT of a class layer.
  4. Every rung is CERTIFIED: tools/rvt_validate 0 errors, the structural
     proof (CRC / ECC / walker / stamps / counts), four-registry coherence,
     registry PARITY (the ADocument surface of every landed slot before ==
     after -- by construction, since Global/Latest is byte-identical, and
     ASSERTED), a rvt.regdiff registration diff on a sample of slots (row /
     positions / run / surface all equal), and the rvt.regadd BYTE-DELTA
     REPORT versus the parent with the assertion table: for an in-place rung
     ONLY the substituted slots' seq-102 record bytes may change, the two
     global registry streams must be byte-identical, no id may be added or
     removed, and the per-seq id order must be identical -- every exception
     is listed with its reason.

THE Y-LADDER (cumulative, each rung derives from the previous rung's PASSING
file; probes.json orders the uploads BISECTION-FIRST):
  Y1 = base + OUR project pen table in place (== the Y_pen single-change probe)
  Y2 = + the browser-organization / system-navigator layer in place
  Y3 = + the named settings singletons (struct / joins / keynote pair)
  Y4 = + the MEP settings + size tables (our NEC/ASME/ASTM/SMACNA data)
  Y5 = + every remaining settings singleton / tracker with a constructor
  Y6 = the built-in-category GStyle CATALOG swapped in place row-for-row
       (X6a's 1:1 (category, style-type) map; == the Y_cat probe cumulative)
  Y7 = + line/fill patterns + materials (our palette by role + slot-fill)
  Y8 = + levels / phases / phase set + units / site / geo-location / base
       points / project info (the datum + identity layer)
  Y9 = + the 19 project view types + every view constellation (project view,
       {3D}, plans) + the document sun
  Yn = the RESIDUE CENSUS of the Y9 file: which Autodesk-authored elements
       remain, in which bucket, and which of OUR records found NO in-place
       slot (the honest 'still theirs' + 'add-path needed' work queues).
  Y_pen = base + ONLY the pen table (identical to Y1: the ladder's rung 1)
  Y_cat = base + ONLY the catalog (single-change, not cumulative)
If a rung's class layer does NOT EXIST in the base (K4's R9 lineage already
reduced e.g. every system text type away), the rung says so per class and
substitutes only what EXISTS -- a shorter honest ladder beats a longer
fictional one.

Territory: tools/genesis_substitute_v3.py, experiments/genesis/subst_k4/*
(+ probes.json + CTRL_K4_base.rvt), tests/test_genesis_substitute_v3.py,
docs/writer/substitution-ladder-v3.md, docs/inbox/genesis-rebase.md.  Every
dependency (tools/genesis_substitute, rvt.regadd, rvt.regdiff, rvt.reduce,
rvt.adocument, rvt.genesis.*, tools/genesis_triage, tools/genesis_assemble)
is IMPORTED, never edited.  Python: ``.venv/bin/python`` from the repo root.

Usage:
  .venv/bin/python tools/genesis_substitute_v3.py                     # whole ladder + probes
  .venv/bin/python tools/genesis_substitute_v3.py --only Y1,Y_cat     # some rungs
  .venv/bin/python tools/genesis_substitute_v3.py --base <rvt> --out-dir <dir>
  .venv/bin/python tools/genesis_substitute_v3.py --manifest-only     # re-write probes.json
"""
from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import genesis_substitute as GS                                        # noqa: E402  (the X-rung machinery -- reused, never edited)
from rvt import regadd                                              # noqa: E402  (in-place substitute + byte-diff report)
from rvt import regdiff as RD                                       # noqa: E402  (registration record + diff)
from rvt.genesis.types import INVALID                               # noqa: E402
from rvt.mutate import Document                                     # noqa: E402

DEFAULT_BASE = os.path.join(ROOT, "experiments", "genesis", "triage", "K4.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4")
CERTIFIED_JSON = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")
LEDGER_MD = os.path.join(ROOT, "docs", "writer", "substitution-ladder-v3.md")

#: the level / phase layer of the X9 skeleton builder -- Y8's share of X9
#: (Y9 takes the rest: view types, view constellations, document sun, text
#: types).  In-place substitution keeps every id, so the layers X9 had to
#: replace TOGETHER (plan views are bound to level ids) can be split: our
#: levels land at the sample's level ids, so the plans still point at them.
LEVEL_PHASE_CLASSES = {"Level", "LevelAttributes", "ProjectPhase",
                       "AllProjectPhases", "PhaseFilterElem"}


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ===========================================================================
# 1. THE BASE: certification (standing-controls discipline, verdict #15c)
# ===========================================================================

def load_certifications(path: str = CERTIFIED_JSON) -> Dict[str, dict]:
    """{repo-relative file: entry} for every viewer-CERTIFIED file (the
    orchestrator's ``docs/coverage/viewer-certified.json`` 'certified'
    list) -- the ONLY files a ladder may derive from."""
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:                                              # pragma: no cover
        return {}
    out: Dict[str, dict] = {}
    for e in data.get("certified") or []:
        f = e.get("file")
        if f:
            out[str(f)] = dict(e)
    return out


def load_failures(path: str = CERTIFIED_JSON) -> Dict[str, dict]:
    """{repo-relative file: entry} for every viewer-FAILED file."""
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:                                              # pragma: no cover
        return {}
    return {str(e.get("file")): dict(e) for e in (data.get("failed") or []) if e.get("file")}


def certification_of(rvt_path: str) -> Optional[dict]:
    """The viewer-certification entry of ``rvt_path`` (None = not certified)."""
    rel = _relp(os.path.abspath(rvt_path))
    return load_certifications().get(rel)


def assert_certified(rvt_path: str, *, allow_uncertified: bool = False) -> dict:
    """The base MUST be a viewer-CERTIFIED file before ANYTHING is built on
    it (the K1 disaster: an unproven base wrapped forty probes in its own
    defect).  Returns the certification entry; raises otherwise unless
    ``allow_uncertified`` (never used by this stream)."""
    cert = certification_of(rvt_path)
    if cert is not None:
        return cert
    fail = load_failures().get(_relp(os.path.abspath(rvt_path)))
    msg = (f"{_relp(rvt_path)} is NOT viewer-certified (docs/coverage/viewer-certified.json"
           f"{'; it is listed as FAILED: ' + str(fail.get('verdict')) if fail else ''})"
           " -- a substitution ladder may only derive from a CERTIFIED base "
           "(verdict #15: the entire K1 program was built on an untested base "
           "that fails on its own)")
    if allow_uncertified:
        log(f"   WARNING: {msg}")
        return {"file": _relp(rvt_path), "proves": "NOT CERTIFIED (override)"}
    raise RuntimeError(msg)


BASE_LINEAGE = {
    "experiments/genesis/triage/K4.rvt": (
        "K4 = K3 minus the ENTIRE loadable-family layer AND all 52 embedded family "
        "documents (four-registry coherent removal); K3 = R9 with every family-USAGE "
        "field nulled; R9 = the deepest viewer-PASSED reduction of "
        "samples/rstbasicsampleproject (R5 -> R9 lineage; thousands of dangling ADocument "
        "refs, tolerated).  Every ancestor that matters is itself certified: R5, R9, K3, "
        "K4, KD1.  K4 is family-free (52/52 documents removed, ContentDocuments 14-byte "
        "empty form, ContentTable + FamilyMgr reconciled), 3,342 host elements, one save "
        "unit -- the ideal genesis base: the family/document layer is already gone."),
}


def stage_control(base_path: str, out_dir: str = OUT_DIR) -> dict:
    """Stage the batch's CERTIFIED POSITIVE CONTROL: a byte-identical copy
    of the certified base itself (md5-asserted), to be uploaded with EVERY
    batch of this ladder's probes.  A failing control voids the batch
    (oracle health / base health), never the constructors."""
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"CTRL_{os.path.splitext(os.path.basename(base_path))[0]}_base.rvt")
    shutil.copyfile(base_path, dst)
    m1, m2 = _md5(base_path), _md5(dst)
    if m1 != m2:                                                    # pragma: no cover
        raise RuntimeError("staged control is not byte-identical to the base")
    return {"file": _relp(dst), "identical_to": _relp(base_path), "md5": m2,
            "certification": certification_of(base_path)}


# ===========================================================================
# 2. THE RUNG TABLE
# ===========================================================================

@dataclasses.dataclass
class Rung3:
    name: str
    label: str                                # the class layer substituted
    parent: str                               # 'BASE' or the parent rung's name
    build: str                                # 'X1'..'X9' | 'Y8' | 'Y9' | 'report'
    description: str
    tests: str
    if_pass: str
    if_fail: str
    seqs: Tuple[int, ...] = (102,)            # records replaced per slot (object only)
    slot_fill: bool = True                    # land slot-less our-records into free same-class slots
    kind: str = "inplace"                     # 'inplace' | 'report' | 'alias'
    alias_of: Optional[str] = None            # Y_pen == Y1


RUNGS: List[Rung3] = [
    Rung3(name="Y1", label="the project pen table (PenWidthTableElem id 2) -> OUR pen table, IN PLACE",
          parent="BASE", build="X1",
          description=("The certified base with its REAL project pen table (PenWidthTableElem, "
                       "m_famId -1, element id 2) carrying OUR pen-width object (settings."
                       "pen_width_table) instead of Autodesk's -- SAME id, SAME ElemTable row, "
                       "SAME record position, SAME PenWidthTableInfo.m_penWidthTableElemId leaf; "
                       "Global/Latest and Global/ElemTable byte-identical to the base.  The 8 "
                       "family-scoped pen tables are the curtain SYSTEM families' and stay.  "
                       "This IS the Y_pen single-change probe."),
          tests=("Whether the reader accepts OUR pen table CONTENT when nothing but the object "
                 "bytes at Autodesk's own registration change (X1v/X_pen/XR0 asked this on the "
                 "BROKEN K1 base; this is the first time it is asked on a CERTIFIED base)."),
          if_pass=("Our pen table constructor's values load at Autodesk's registration; the "
                   "K5a/S1/X_pen line is retired for real."),
          if_fail=("Our pen-table VALUES are what the reader rejects (the ONLY variable): diff our "
                   "record vs the base's id 2 field by field (docs/writer/substitution-ladder-v3.md).")),
    Rung3(name="Y2", label="BrowserOrganization set + system-navigator constellation -> ours, IN PLACE",
          parent="Y1", build="X2",
          description=("Y1 with the browser layer's OBJECTS replaced in place: the 4 per-tree DEFAULT "
                       "BrowserOrganizations -> our defaults (same ids), the MEP system-navigator "
                       "view + its Viewer / Viewport / DBDrawing -> our navigator constellation by "
                       "role (same ids, so DBViewInfo / DBDrawingInfo / the navigator's owned rows "
                       "index them unchanged), ReconcileBrowserSettingsElem + ConstructionSetProject "
                       "-> ours; our two house schemes land in two of the seven non-default sample "
                       "scheme slots (slot-fill); the remaining sample schemes STAY (residue)."),
          tests=("Whether the reader accepts our browser-organization / navigator OBJECTS at "
                 "Autodesk's own registrations."),
          if_pass="Our browser / navigator constructors are reader-accepted.",
          if_fail=("One of our browser / navigator objects is rejected -- bisect the organizations "
                   "from the navigator (two single-class in-place probes).")),
    Rung3(name="Y3", label="StructSettings / wall-join / auto-join / keynote pair -> ours, IN PLACE",
          parent="Y2", build="X3",
          description=("Y2 with the named settings singletons' OBJECTS replaced in place: "
                       "StructSettingsElem (our imperial structural conventions), WallJoinDefault"
                       "Setting, AutoJoinTracker, KeynoteTable (OURS = EMPTY: Autodesk's 3,840-row "
                       "keynote database is NOT reproduced) + KeynotingSystem.  InitialViewSettings "
                       "is NOT in K4's lineage (nothing to land it in -> listed as ours-not-landed)."),
          tests="Whether the reader accepts our structural / join / keynote singleton OBJECTS (incl. an EMPTY keynote table) at Autodesk's slots.",
          if_pass="The named singleton constructors are reader-accepted (an empty keynote table is legal).",
          if_fail="One of these five objects is rejected -- bisect the keynote pair from the joins pair from StructSettings."),
    Rung3(name="Y4", label="Rbs* settings + sizes tables (wire/duct/pipe/conduit/cable-tray) -> ours, IN PLACE",
          parent="Y3", build="X4",
          description=("Y3 with the eight MEP settings / size-table singletons' OBJECTS replaced in "
                       "place: RbsWire/Pipe/DuctSettingsElem (our conventions, keeping the base's "
                       "per-classification type wiring) and RbsWire/Pipe/DuctSizesElem (OUR data: "
                       "NEC ampacity, ASME B36.10/B36.19 + ASTM B88 pipe dimensions, our SMACNA "
                       "duct series -- keyed onto the base's still-present catalog symbols), "
                       "Conduit/CableTraySettingsElem."),
          tests="Whether the reader accepts our MEP settings singletons and OUR size-table DATA at Autodesk's slots.",
          if_pass="Our MEP settings / sizes constructors + our dimensional data are reader-accepted.",
          if_fail="One of the eight is rejected -- bisect settings vs sizes vs the conduit/cable-tray pair."),
    Rung3(name="Y5", label="every remaining settings singleton / tracker with a constructor -> ours, IN PLACE",
          parent="Y4", build="X5",
          description=("Y4 with EVERY other settings singleton / tracker our standard constellation "
                       "constructs REPLACED in place (the MEP tracker constellation, GCS / assembly / "
                       "keynote-tags / revision-clouds / sheet-collection trackers, revisions + "
                       "numbering sequences, print settings, worksharing / export / area / energy / "
                       "reinforcement / route-analysis / fabrication settings, model graphics "
                       "styles, area schemes, ...).  The base's extra multi-instances (2 extra print "
                       "setups, the per-user worksharing display) STAY as residue.  Classes WITHOUT "
                       "a constructor are LISTED, never touched."),
          tests="Whether the reader accepts the WHOLE our-settings constellation OBJECTS at Autodesk's slots.",
          if_pass="Every settings constructor we own is reader-accepted; the settings layer is retired.",
          if_fail="A constructor of the wider settings constellation is rejected -- bisect Y5 by tier (mep / trackers / revisions).")
    ,
    Rung3(name="Y6", label="the built-in-category GStyle CATALOG swapped in place, row for row (X6a's 1:1 map)",
          parent="Y5", build="X6a",
          description=("Y5 with the ENTIRE present built-in-category object-styles table swapped IN "
                       "PLACE, ROW FOR ROW: each project-level GStyleElem row of a built-in category "
                       "(the K4 lineage carries 1,172 of the 1,407-row enum -- R9's GC removed the "
                       "unreferenced rows AND STILL LOADS) -> OUR row of the SAME (category, "
                       "style-type) from catalog.builtin_style_catalog, at the SAME id.  Every "
                       "CategoryTracking category->style registry leaf keeps indexing the same id "
                       "(now our row) -- Global/Latest byte-identical.  Our 235 (category, type) rows "
                       "the base does not carry are NOT ADDED (no in-place slot; the add path is not "
                       "this ladder's variable) -- listed as ours-not-landed.  The project "
                       "SUBCATEGORY layer stays (the X6b gap)."),
          tests=("Whether the reader accepts OUR object-styles VALUES row for row at Autodesk's "
                 "own catalog registrations -- the C0/X_cat/X6a question, first time on a certified base."),
          if_pass="Our catalog values are reader-accepted: the catalog counsel item is a pure legal decision.",
          if_fail=("Our catalog is what the reader rejects -- the FIRST attributable answer to the "
                   "catalog question: candidates are a validated value (pen index / colour / pattern "
                   "id) since the (category,type) keys and every registration are Autodesk's own.")),
    Rung3(name="Y7", label="line/fill patterns + materials -> our palette, IN PLACE (role + slot-fill)",
          parent="Y6", build="X7",
          description=("Y6 with the graphic-material palette's OBJECTS replaced in place: the base's "
                       "7 line patterns / 9 fill patterns / 23 materials receive OUR palette "
                       "(house_standard: 4 line patterns, 5 fill patterns, 13 materials -- no asset "
                       "binding, no property sets): role-matched slots first (their 'Dash' variants -> "
                       "our dash; 'Concrete 10 MPa' -> our concrete; a zero-grid fill -> our solid), "
                       "the rest of our palette into free same-class slots ranked by inbound "
                       "reference count (SLOT-FILL); our materials' pattern references are remapped "
                       "onto the fill-pattern slots our patterns landed in.  The base's surplus "
                       "patterns / materials and ALL its AppearanceAssetElem / PropertySetElement "
                       "companions STAY as residue (a removal rung's business)."),
          tests=("Whether the reader accepts OUR pattern + material OBJECTS at Autodesk's palette "
                 "registrations (incl. the two token questions: our solid fill under our own name, "
                 "no 'Default'-named material)."),
          if_pass="Our patterns / materials are reader-accepted at the sample's slots; no name token is required.",
          if_fail=("Our palette objects are rejected -- bisect patterns vs materials (two single-layer "
                   "in-place probes); if a NAME token is the cause it is a REQUIRED TOKEN for the "
                   "counsel list.")),
    Rung3(name="Y8", label="levels + phases (+ set/filter) + units / site / base points / project info -> ours, IN PLACE",
          parent="Y7", build="Y8",
          description=("Y7 with the DATUM + IDENTITY layer's OBJECTS replaced in place: the two "
                       "plan-bearing levels -> our L1 / L2 (their DBViewPlans keep pointing at the "
                       "same level ids -- in place, the level/view binding is by construction), "
                       "the level type -> ours; the two ProjectPhases -> our phases (sequence order), "
                       "AllProjectPhases -> our phase set (phasing overrides re-wired to OUR Y7 phase "
                       "materials by name), the phase filter -> our 'all' filter; UnitsElem -> our units "
                       "registry, TrueNorth, the GeoSite / GeoLocation pairs -> our site + project / "
                       "internal locations, the two BasePoints -> our project base point + survey point, "
                       "ProjectInfo -> ours.  The base's 7 plan-less levels STAY as residue; 4 of our "
                       "5 phase filters find no slot (the base carries 1) -> ours-not-landed."),
          tests=("Whether the reader accepts our datum + identity OBJECTS (levels, phases, units, site, "
                 "project info) at Autodesk's own registrations."),
          if_pass="Our level / phase / units / site / project-info constructors are reader-accepted.",
          if_fail=("Our datum/identity objects are rejected -- bisect levels+phases vs units vs "
                   "site/base-points vs project info (single-layer in-place probes).")),
    Rung3(name="Y9", label="the 19 project view types + every view constellation (+ document sun) -> ours, IN PLACE",
          parent="Y8", build="Y9",
          description=("Y8 with the VIEW layer's OBJECTS replaced in place: all 19 PROJECT DBViewTypes "
                       "(by m_systemFamilyIdx) -> our view types; the project view (DBViewProject) + its "
                       "companions, the '{3D}' 3D view + its Viewer3d / Viewport / DBDrawing / clip box "
                       "companions, and the two floor plans + their viewer / viewport / drawing "
                       "companions -> OUR constellations by role, each record at the corresponding "
                       "sample id; the document SunAndShadowSettings -> ours.  The base's surplus "
                       "companions (its plans carry ~16 satellites each vs our 7), the drafting view, "
                       "and the curtain-system-family-scoped view types STAY as residue; our 3 system "
                       "text types + their font/category/style children find NO slot in the R9 lineage "
                       "(it carries no project text types) -> ours-not-landed."),
          tests=("Whether the reader accepts OUR view / view-type / sun OBJECTS -- the document skeleton "
                 "G0/G1 were built from -- at Autodesk's own registrations (the deepest cumulative rung: "
                 "a PASS proves the WHOLE settings + catalog + palette + datum + view chain of our "
                 "constructors)."),
          if_pass=("EVERY constructor this ladder owns loads at Autodesk's registrations: the residue "
                   "census (Yn) is the honest remaining work, and the next variable is registration "
                   "(the add path) on a certified base."),
          if_fail=("Our view-layer objects are rejected while Y8 passed -- the constructed-base "
                   "defect's most likely home; bisect view types vs the 3D constellation vs the plans "
                   "(each a single-layer in-place probe), reading the card message.")),
    Rung3(name="Yn", label="the RESIDUE CENSUS of the deepest rung (Y9): what is still Autodesk's, and what of ours found no slot",
          parent="Y9", build="report", kind="report",
          description=("A census of Y9: every host element is LANDED (its object bytes are OUR "
                       "constructor's, at Autodesk's registration -- listed per rung / class) or "
                       "K4-INHERITED RESIDUE (never substituted), the residue bucketed by class with "
                       "the reason (no our-constructor, product data, definitions, datum content, the "
                       "sample's SURPLUS instances of substituted classes, material companions, the "
                       "curtain systems) + the aggregated OURS-NOT-LANDED queue (our records that "
                       "found no in-place slot: 235 catalog rows, 4 phase filters, the text-type "
                       "constellation, InitialViewSettings -- each needs the ADD path or a base that "
                       "carries the class) + the provenance ledger for the container layer.  Report "
                       "only: the file to viewer-test is Y9.rvt."),
          tests="(report -- nothing to viewer-test beyond Y9)",
          if_pass="n/a", if_fail="n/a"),
    # ---- the two standalone single-change probes ----------------------------
    Rung3(name="Y_pen", label="the base + ONLY our pen table in place (single-change probe; identical to Y1)",
          parent="BASE", build="X1", kind="alias", alias_of="Y1",
          description=("The single-change control of the ladder: the certified base with exactly ONE "
                       "object swapped -- OUR pen-width table at PenWidthTableElem id 2.  This is "
                       "Y1 (same operation, same parent); the probes manifest lists it as an alias so "
                       "it is uploaded once."),
          tests="Y1's question, isolated: our pen-table object at Autodesk's registration.",
          if_pass="Our pen table object loads (the smallest possible OUR-content probe passes).",
          if_fail=("Even ONE our-object at Autodesk's registration fails: the object CONTENT layer is "
                   "the defect (diff our pen record vs the base's id 2), and the whole ladder is "
                   "expected to fail until it is fixed.")),
    Rung3(name="Y_cat", label="the base + ONLY the built-in GStyle catalog in place (single-change probe)",
          parent="BASE", build="X6a",
          description=("The certified base with exactly ONE class layer swapped: every present "
                       "built-in-category GStyleElem row (1,172) -> OUR row of the same (category, "
                       "style-type), in place, nothing else touched (no settings, no palette).  The "
                       "cleanest possible statement of the catalog question (X6a / X_cat / C0 asked it "
                       "on the broken K1 base)."),
          tests="Whether OUR object-styles values load at Autodesk's own catalog registrations, isolated from every other constructor.",
          if_pass="Our catalog values are reader-accepted in isolation (the catalog is retired as an engineering question).",
          if_fail=("Our catalog VALUES are rejected in isolation -- diff a rejected (category, type) row's "
                   "pen / colour / pattern values against the base's row (report's field diff sample).")),
]


def rung_by_name(name: str) -> Rung3:
    for r in RUNGS:
        if r.name == name:
            return r
    raise KeyError(name)


def parent_path_of(rung: Rung3, base_path: str, out_dir: str) -> str:
    if rung.parent == "BASE":
        return base_path
    return os.path.join(out_dir, f"{rung.parent}.rvt")


# ===========================================================================
# 3. BUILD ADAPTERS: the X builders' output, partitioned for the Y layers
# ===========================================================================

def _restrict(ctx: "GS.SubstContext", sb: "GS.SubstBuild", keep_classes: Set[str],
              *, invert: bool = False) -> "GS.SubstBuild":
    """Keep (or drop, when ``invert``) the records / old ids / correspondence
    of ``sb`` whose class is in ``keep_classes``.  Used to split X9's
    coherent skeleton substitution into the Y8 (level/phase) and Y9 (view)
    layers -- possible IN PLACE because no id changes, so the plan-view /
    level binding X9 had to keep together holds by construction."""
    def wanted_rec(r) -> bool:
        inside = r.class_name in keep_classes
        return inside != invert
    def wanted_old(o) -> bool:
        inside = ctx.cls_of.get(int(o)) in keep_classes
        return inside != invert
    recs = [r for r in sb.records if wanted_rec(r)]
    removed = [r for r in sb.records if not wanted_rec(r)]
    rec_ids = {int(r.elem_id) for r in recs}
    olds = [int(o) for o in sb.old_ids if wanted_old(o)]
    corr = {int(k): int(v) for k, v in sb.corr.items()
            if wanted_old(int(k)) and int(v) in rec_ids}
    new_only = [r for r in (sb.new_only or []) if wanted_rec(r)]
    out = GS.SubstBuild(old_ids=olds, records=recs, corr=corr, new_only=new_only,
                        notes=list(sb.notes), residue=dict(sb.residue), info=dict(sb.info))
    # the OTHER layer's records: kept only so this rung's records that
    # reference them (a view -> our level) can resolve to the slots the other
    # layer's rung landed them in (by (class, name) against the current file)
    out.extra_records_for_resolution = removed
    return out


def build_for(rung: Rung3, ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """The X-rung builder (or a layer split of one) for a Y rung."""
    b = rung.build
    if b in ("X1", "X2", "X3", "X4", "X5", "X6a", "X7", "X8", "X9"):
        return getattr(GS, f"build_{b}")(ctx)
    if b == "Y8":
        # units / true north / site + geo-locations / base points / project info (X8)
        # PLUS the level + phase layer of the skeleton (X9's Level, level type,
        # phases, phase set, filters).  Built from ONE house catalog instance
        # (the _house_records cache is keyed by (rung, id_start)), so the two
        # halves reference each other by consistent temporary ids.
        sb8 = GS.build_X8(ctx)
        sb9 = GS.build_X9(ctx)
        lp = _restrict(ctx, sb9, LEVEL_PHASE_CLASSES)
        notes = ([f"[X8] {n}" for n in sb8.notes] + [f"[X9-level/phase layer] {n}" for n in lp.notes]
                 + ["Y8 = X8 (units / true north / sites / base points / project info) + the "
                    "level / phase layer of X9 (levels + level type + phases + phase set + "
                    "filters); the view layer is Y9.  Split possible IN PLACE: no id changes, so "
                    "the sample plan views keep pointing at the same level ids (now our levels)."])
        return GS.SubstBuild(old_ids=sorted(set(sb8.old_ids) | set(lp.old_ids)),
                             records=list(sb8.records) + list(lp.records),
                             corr={**{int(k): int(v) for k, v in sb8.corr.items()}, **lp.corr},
                             new_only=list(sb8.new_only or []) + list(lp.new_only or []),
                             notes=notes,
                             residue={**dict(sb8.residue or {}), **dict(lp.residue or {})},
                             info={"x8": sb8.info, "x9_level_phase": lp.info})
    if b == "Y9":
        sb9 = GS.build_X9(ctx)
        vw = _restrict(ctx, sb9, LEVEL_PHASE_CLASSES, invert=True)
        vw.notes = ([f"[X9-view layer] {n}" for n in sb9.notes]
                    + ["Y9 = the VIEW layer of X9 (view types + view constellations + document "
                       "sun + text types); the level / phase layer landed at Y8, so this rung's "
                       "references to our levels / phases resolve to those slots by (class, name)."])
        return vw
    raise ValueError(f"{rung.name}: unknown build key {b!r}")


# ===========================================================================
# 4. THE IN-PLACE PLAN: correspondence -> slots (role primary + slot-fill)
# ===========================================================================

@dataclasses.dataclass
class Pair:
    ours: int                 # our record's (temporary) id
    slot: int                 # the existing element id it lands in (in place)
    cls: str
    match: str                # 'role' | 'role-primary' | 'sibling-donor' | 'donor'
    slot_referrers: int       # inbound typed referrers of the slot in the parent
    role_group: int = 1       # how many old elements shared this role


@dataclasses.dataclass
class InPlacePlan:
    pairs: List[Pair]                              # our record -> slot
    landed: Dict[int, int]                         # ours -> slot
    dropped: List[dict]                            # our records with NO slot
    residue: List[dict]                            # old elements left in place (not landed on)
    class_mismatch: List[dict]                     # correspondence pairs of differing class
    protected_skipped: List[dict]                  # slots already landed by an earlier rung
    notes: List[str] = dataclasses.field(default_factory=list)


def _referrer_count(ctx: "GS.SubstContext", eid: int, exclude: Set[int]) -> int:
    return len({r for r in ctx.inbound(eid) if r not in exclude})


def plan_inplace(ctx: "GS.SubstContext", sb: "GS.SubstBuild", *,
                 slot_fill: bool = True, protected: Set[int] = frozenset()) -> InPlacePlan:
    """Turn the X-builder's (old_ids, records, corr) into an IN-PLACE plan.

    Each of OUR records lands in exactly ONE existing element ('slot') of the
    SAME class: its role correspondent (when several olds share a role, the
    PRIMARY = the most-referenced one, so the most referrers now see our
    object; the others become donor candidates), else -- ``slot_fill`` -- a
    free element of the same class ranked by inbound referrer count.  Slots
    landed by an EARLIER rung (``protected``) are never reused.  What finds no
    slot is DROPPED (listed); old elements nobody landed on stay (residue)."""
    recs = {int(r.elem_id): r for r in sb.records}
    old_all = {int(o) for o in sb.old_ids}
    protected = {int(p) for p in protected}
    prot_skip = [{"id": o, "class": ctx.cls_of.get(o, "?")} for o in sorted(old_all & protected)]
    old_set = old_all - protected
    corr = {int(k): int(v) for k, v in sb.corr.items()
            if v not in (None, INVALID) and int(k) in old_set and int(v) in recs}
    inv: Dict[int, List[int]] = collections.defaultdict(list)
    for o, n in corr.items():
        inv[n].append(o)
    pairs: List[Pair] = []
    landed: Dict[int, int] = {}
    mismatch: List[dict] = []
    siblings: Dict[str, List[int]] = collections.defaultdict(list)
    notes: List[str] = []

    def refc(o: int) -> int:
        return _referrer_count(ctx, o, old_set)

    # ---- role correspondents (primary = most-referenced old of the role) ----
    for n in sorted(inv):
        rec = recs[n]
        same = [o for o in inv[n] if ctx.cls_of.get(o) == rec.class_name]
        for o in inv[n]:
            if o not in same:
                mismatch.append({"ours": n, "our_class": rec.class_name,
                                 "old": o, "old_class": ctx.cls_of.get(o, "?")})
        if not same:
            continue
        primary = max(same, key=lambda o: (refc(o), -o))
        landed[n] = primary
        pairs.append(Pair(ours=n, slot=primary, cls=rec.class_name,
                          match=("role" if len(same) == 1 else "role-primary"),
                          slot_referrers=refc(primary), role_group=len(same)))
        for o in same:
            if o != primary:
                siblings[rec.class_name].append(o)
    # ---- slot-fill: our slot-less records into free same-class slots ------
    taken = set(landed.values())
    free: Dict[str, List[Tuple[int, str]]] = collections.defaultdict(list)
    for cls_name, olds in siblings.items():
        for o in olds:
            if o not in taken:
                free[cls_name].append((o, "sibling-donor"))
    for o in old_set - taken:
        if any(o == x for lst in free.values() for x, _ in lst):
            continue
        free[ctx.cls_of.get(o, "?")].append((o, "donor"))
    for cls_name in free:
        free[cls_name].sort(key=lambda t: (-refc(t[0]), t[0]))
    dropped: List[dict] = []
    for n in sorted(recs):
        if n in landed:
            continue
        rec = recs[n]
        pool = free.get(rec.class_name) if slot_fill else None
        if pool:
            o, kind = pool.pop(0)
            landed[n] = o
            pairs.append(Pair(ours=n, slot=o, cls=rec.class_name, match=kind,
                              slot_referrers=refc(o), role_group=0))
        else:
            dropped.append({"ours": n, "class": rec.class_name,
                            "name": GS._rec_name(rec) or GS._catalog_name(rec) or "",
                            "reason": (f"no free {rec.class_name} slot in the base "
                                       f"({len(ctx.ids_of(rec.class_name))} exist"
                                       f"{'' if slot_fill else ', slot-fill disabled'})"
                                       " -- landing it needs the ADD path (not this "
                                       "ladder's variable) or a base carrying the class")})
    # ---- residue: old elements nobody landed on (left exactly as they are) ---
    used = set(landed.values())
    residue = [{"id": o, "class": ctx.cls_of.get(o, "?")} for o in sorted(old_set - used)]
    if siblings:
        notes.append("role groups where several sample elements shared one of our roles: "
                     + json.dumps({k: len(v) + 1 for k, v in siblings.items()}))
    return InPlacePlan(pairs=pairs, landed=landed, dropped=dropped, residue=residue,
                       class_mismatch=mismatch, protected_skipped=prot_skip, notes=notes)


# ===========================================================================
# 5. RETARGET: our records onto their slots (typed remap; no dangling)
# ===========================================================================

def _our_record_name(rec) -> str:
    """OUR record's name: the accessors genesis_substitute uses (m_symbolInfo /
    m_name / m_viewName / pattern-material holders) PLUS ``m_text`` -- where
    a Level (datum) stores its name, which the X-ladder helpers miss."""
    nm = GS._rec_name(rec) or GS._catalog_name(rec)
    if nm:
        return str(nm)
    o = rec.obj or {}
    for k in ("m_text", "m_datumName"):
        v = o.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _file_name_index(ctx: "GS.SubstContext") -> Dict[Tuple[str, str], int]:
    """(class, normalized name) -> element id over the CURRENT file, over the
    classes our layers reference by name: genesis_substitute's index plus the
    ``m_text`` accessor (Level datum names) and the view classes.  Elements
    with NO name are NOT indexed (an empty-name key would collapse every
    unnamed element of a class onto one id -- the plan-level bug the first
    Y9 build had: both plans pointed at one level)."""
    out = dict(GS._file_element_names(ctx))
    for k in [k for k in out if not k[1]]:
        out.pop(k)                                              # drop empty-name keys
    want = {"Level", "DBViewPlan", "DBView3d", "DBViewDrafting", "DBViewProject",
            "DBViewType", "TextNoteAttributes", "FontElem", "GeoSite", "GeoLocation",
            "BasePoint", "ProjectPhase", "PhaseFilterElem", "MaterialElem",
            "FillPatternElem", "LinePatternElem", "LevelAttributes"}
    for e in ctx.host:
        c = ctx.cls_of.get(e)
        if c not in want:
            continue
        nm = GS._norm_name(GS._sample_gfx_name(ctx, e) or ctx.name_of(e))
        if not nm:
            v = ctx.value(e) or {}
            for k in ("m_text", "m_datumName"):
                x = v.get(k)
                if isinstance(x, str) and x.strip():
                    nm = GS._norm_name(x)
                    break
        if nm:
            out.setdefault((c, nm), int(e))
    return out


def _resolve_by_name(ctx: "GS.SubstContext", rec, file_names: Dict[Tuple[str, str], int],
                     singletons: Dict[str, int]) -> Optional[int]:
    """The current file's element of the same (class, normalized name), or its
    singleton of the class -- the resolution rule _rewire_subset uses.  This
    is how a Y9 view's reference to our (dropped-here) level lands on the level
    slot Y8 already made ours: same class, our name, in the CURRENT file."""
    nm = GS._norm_name(_our_record_name(rec))
    if nm and (rec.class_name, nm) in file_names:
        return int(file_names[(rec.class_name, nm)])
    if rec.class_name in singletons:
        return int(singletons[rec.class_name])
    return None


def retarget(ctx: "GS.SubstContext", sb: "GS.SubstBuild", plan: InPlacePlan,
             seqs: Sequence[int] = (102,),
             prior_tmp_to_slot: Optional[Dict[int, int]] = None
             ) -> Tuple[Dict[int, Dict[int, Tuple[int, dict]]], dict]:
    """Re-target every landed record onto its slot: remap our ids -> slots in
    every schema-typed ElementId leaf; resolve references to our records
    that did NOT land HERE (dropped ones + the other layer of a split
    builder) first through the PRIOR RUNGS' correspondence (their landed
    slots -- our house catalog allocates deterministic temporary ids, so the
    earlier rung's temporary id of 'our L1' equals this rung's), then by
    (class, name) against the CURRENT file, else neutralise them (reported);
    set m_id = slot; prove every re-targeted record body schema-decodes and
    re-encodes byte-exactly.  Returns ({slot: {seq: (class_id, value)}},
    report)."""
    recs = {int(r.elem_id): r for r in sb.records}
    # the OTHER layer's records of a split builder (e.g. Y9's view records
    # referencing our levels / phases, which Y8 already landed): treat them
    # as our-records-with-no-slot HERE so their ids resolve to the slots the
    # earlier rung landed them in
    for r in getattr(sb, "extra_records_for_resolution", []) or []:
        recs.setdefault(int(r.elem_id), r)
    mapping = dict(plan.landed)                                  # ours -> slot
    dropped_ids = set(recs) - set(plan.landed)
    prior = {int(k): int(v) for k, v in (prior_tmp_to_slot or {}).items()
             if int(v) in ctx.universe}                         # only slots that still exist
    file_names = _file_name_index(ctx)
    singletons: Dict[str, int] = {}
    for cls_name in ("UnitsElem", "TrueNorth", "ProjectInfo", "AllProjectPhases",
                     "AllProjectRevisions", "ElectricalSetting", "DBViewProject",
                     "KeynoteTable", "KeynotingSystem", "PhaseFilterElem"):
        ids = ctx.ids_of(cls_name)
        if len(ids) == 1:
            singletons[cls_name] = int(ids[0])
    # the document sun (the SunAndShadowSettings no view owns)
    for e in ctx.ids_of("SunAndShadowSettings"):
        if not ctx.st["owner_view"].get(e):
            singletons["SunAndShadowSettings"] = int(e)
            break
    live_ids: Set[int] = (set(ctx.universe) | set(plan.landed.values()))
    out: Dict[int, Dict[int, Tuple[int, dict]]] = {}
    rep: Dict[str, Any] = {"leaves_remapped": 0, "dropped_refs_resolved_by_prior_rung": [],
                           "dropped_refs_resolved_by_name": [],
                           "dropped_refs_neutralised": [], "record_selfcheck_failures": [],
                           "records": 0, "seqs": list(seqs), "would_differ_101": 0, "would_differ_103": 0}
    dec, enc = ctx.doc.dec, GS.MP.session(ctx.doc).enc          # decoder + encoder for the proof
    for ours, slot in sorted(plan.landed.items(), key=lambda kv: kv[1]):
        rec = recs[ours]
        by_seq: Dict[int, Tuple[int, dict]] = {}
        bodies = {102: (rec.class_id, rec.class_name, rec.obj)}
        if 101 in seqs:
            bodies[101] = (_class_id("ElementHeader"), "ElementHeader", rec.header)
        if 103 in seqs:
            bodies[103] = (rec.rep_class_id, rec.rep_class_name,
                           rec.rep if rec.rep is not None else {})
        for seq, (cid, cname, body) in bodies.items():
            val = copy.deepcopy(body or {})
            if seq == 102 and "m_id" in val:
                val["m_id"] = int(slot)
            # 1. our ids -> slots (typed)
            edits = ctx.ted.remap(val, cname, mapping)
            rep["leaves_remapped"] += len(edits)
            # 2. references to our NOT-LANDED-HERE records: resolve to the slot an
            #    earlier rung landed the same record in (prior correspondence), else
            #    by (class, name) against the current file
            resolved: Dict[int, int] = {}
            unresolved: Set[int] = set()
            for lf in ctx.ted.leaves(val, cname):
                v = lf.value
                if isinstance(v, int) and v in dropped_ids:
                    if v in resolved or v in unresolved:
                        continue
                    # (a) semantic: same class + same NAME (or the class singleton) in
                    #     the current file -- where an earlier rung landed the record
                    tgt = _resolve_by_name(ctx, recs[v], file_names, singletons)
                    how = "class+name-in-current-file" if tgt is not None else ""
                    # (b) fallback: an earlier rung's report says which slot this exact
                    #     record (same temporary id) landed in -- CLASS-CHECKED, because
                    #     every rung allocates temporary ids from the same band and the
                    #     ids of different rungs' records can collide
                    if tgt is None and v in prior and \
                            ctx.cls_of.get(prior[v]) == recs[v].class_name:
                        tgt, how = prior[v], "prior-rung-correspondence"
                    if tgt is not None:
                        resolved[v] = tgt
                        rep[("dropped_refs_resolved_by_prior_rung" if how.startswith("prior")
                             else "dropped_refs_resolved_by_name")].append(
                            {"in_slot": slot, "seq": seq, "our_record": v,
                             "class": recs[v].class_name, "name": _our_record_name(recs[v]),
                             "resolved_to": tgt, "how": how})
                    else:
                        unresolved.add(v)
            if resolved:
                ctx.ted.remap(val, cname, resolved)
            if unresolved:
                st_p = ctx.ted.purge(val, cname, live_ids - unresolved, label=f"{slot}/{seq}")
                rep["dropped_refs_neutralised"].append(
                    {"in_slot": slot, "seq": seq,
                     "targets": [{"our_dropped": v, "class": recs[v].class_name,
                                  "name": _our_record_name(recs[v])} for v in sorted(unresolved)],
                     "purge": {k: st_p.get(k) for k in ("nulled", "elements_dropped", "scalars_nulled")}})
            # 3. self-check: encode -> decode -> re-encode byte-exact (never emit a
            #    lossy object; a purge that broke a fixed-arity structure is caught HERE)
            body_bytes = enc.encode_object(cid, val)
            got = dec.decode_record(cid, body_bytes)
            re = enc.encode_object(cid, got.value) if got.clean else b""
            if not (got.clean and re == body_bytes):
                rep["record_selfcheck_failures"].append(
                    {"ours": ours, "slot": slot, "seq": seq, "class": cname,
                     "decode_clean": bool(got.clean), "byte_exact": (re == body_bytes),
                     "errors": (got.errors or [])[:3]})
            by_seq[seq] = (int(cid), val)
        # informational: WOULD our header / rep have differed from the sample's?
        if 101 not in seqs:
            rep["would_differ_101"] += _would_differ(ctx, slot, 101, rec)
        if 103 not in seqs:
            rep["would_differ_103"] += _would_differ(ctx, slot, 103, rec)
        out[int(slot)] = by_seq
        rep["records"] += 1
    return out, rep


def _class_id(name: str) -> int:
    from rvt.genesis.skeleton import class_id
    return int(class_id(name))


def _would_differ(ctx: "GS.SubstContext", slot: int, seq: int, rec) -> int:
    """1 if OUR seq-101 header / seq-103 rep would differ from the record the
    slot keeps (we do NOT replace it in an object-only rung; this counts the
    'kept the sample's envelope' cases for the report), else 0."""
    try:
        old = ctx.doc.value(int(slot), seq) or {}
    except Exception:
        return 0
    ours = rec.header if seq == 101 else (rec.rep if rec.rep is not None else {})
    return 0 if (ours or {}) == (old or {}) else 1


# ===========================================================================
# 6. CERTIFICATION EXTRAS: parity, registration diff, byte-delta assertions
# ===========================================================================

def _byte_delta_assertions(diff: dict, *, slots: Set[int], seqs: Sequence[int],
                           partition_name: str) -> dict:
    """The BYTE-DELTA ASSERTION TABLE for an in-place rung: exactly which
    bytes changed vs the parent, whether that is the expected set, and every
    exception with its reason."""
    recs = diff["records"]
    changed = {(c["seq"], c["id"]) for c in recs["changed"]}          # may be truncated examples
    changed_ids = set(recs["changed_ids"])
    added_ids = set(recs["added_ids"])
    removed_ids = set(recs["removed_ids"])
    expected_slots = set(int(s) for s in slots)
    unexpected_changed = sorted(changed_ids - expected_slots)
    unchanged_slots = sorted(expected_slots - changed_ids)             # our object == sample's object
    streams_diff = list(diff["streams"]["differing"])
    exceptions: List[dict] = []
    problems: List[str] = []
    # the two document registry streams MUST be byte-identical
    for s in ("Global/Latest", "Global/ElemTable"):
        if s in streams_diff:
            problems.append(f"{s} differs from the parent (in-place must not touch it)")
    other = [s for s in streams_diff if s != partition_name]
    if other:
        problems.append(f"streams other than the element partition differ: {other}")
    if added_ids:
        problems.append(f"record ids ADDED (in-place adds nothing): {sorted(added_ids)[:8]}")
    if removed_ids:
        problems.append(f"record ids REMOVED (in-place deletes nothing): {sorted(removed_ids)[:8]}")
    if unexpected_changed:
        problems.append(f"record ids CHANGED beyond the landed slots: {unexpected_changed[:8]}")
    if not recs.get("id_order_identical", True):
        problems.append("per-seq id order changed (in-place keeps every record position)")
    if not diff["elemtable"].get("identical", False):
        problems.append("ElemTable rows differ (rows / episodes / owners must be untouched)")
    if not diff["latest"].get("identical", False):
        problems.append("ADocument (Global/Latest) differs (registries must be untouched)")
    if not diff.get("embedded_units_identical", True):
        problems.append("embedded save units differ (in-place edits unit 0 only)")
    # seq scope of the changed records
    changed_seqs = collections.Counter(s for (s, _i) in changed)
    for s in changed_seqs:
        if s not in seqs:
            problems.append(f"seq-{s} records changed although only seqs {list(seqs)} were replaced")
    # expected, benign deviations: block re-flow when record lengths change
    for s, b in (diff.get("blocks") or {}).items():
        if not b.get("identical", True):
            exceptions.append({"what": f"seq-{s} block partition re-flowed",
                               "reason": ("our objects are not the same byte length as the sample's, "
                                          "so the certified re-blocker (rvt.reduce.reblock -- the "
                                          "mechanics behind every certified reduction) re-chunked the "
                                          f"unit-0 seq-{s} run; record ORDER is unchanged"),
                               "blocks_parent": b.get("parent"), "blocks_out": b.get("out")})
    if unchanged_slots:
        exceptions.append({"what": f"{len(unchanged_slots)} landed slot(s) byte-identical to the parent",
                           "reason": ("our constructor reproduces the sample's own object for these "
                                      "(empty trackers / machinery with no free value) -- landed, "
                                      "but no bytes to change"),
                           "slots": unchanged_slots[:40]})
    return {
        "streams_differing": streams_diff,
        "only_partition_differs": (set(streams_diff) <= {partition_name}),
        "records_changed_ids": sorted(changed_ids),
        "records_changed_count": recs.get("changed_count"),
        "records_changed_by_seq": {str(s): n for s, n in changed_seqs.items()},
        "records_added_ids": sorted(added_ids),
        "records_removed_ids": sorted(removed_ids),
        "expected_slots": len(expected_slots),
        "unexpected_changed_ids": unexpected_changed,
        "landed_but_unchanged_slots": len(unchanged_slots),
        "id_order_identical_per_seq": recs.get("id_order_identical_per_seq"),
        "block_partition_identical_per_seq": {str(s): b.get("identical")
                                              for s, b in (diff.get("blocks") or {}).items()},
        "elemtable_identical": diff["elemtable"].get("identical"),
        "adocument_identical": diff["latest"].get("identical"),
        "embedded_units_identical": diff.get("embedded_units_identical"),
        "field_diff_examples": recs.get("changed", [])[:4],
        "exceptions": exceptions,
        "problems": problems,
        "assertion_holds": not problems,
    }


def _registration_diff_sample(parent: str, out: str, slots: Sequence[int],
                              limit: int = 6) -> List[dict]:
    """rvt.regdiff registration record of a sample of landed slots, parent vs
    out: an in-place substitution must leave EVERY registration dimension
    (ElemTable row / episodes / owner / band, record positions / run,
    ADocument surface, owned rows) identical -- only the OBJECT differs."""
    rows: List[dict] = []
    try:
        da, db = RD.RegDoc(parent), RD.RegDoc(out)
        for s in list(slots)[:limit]:
            ra = RD.registration_of(da, int(s))
            rb = RD.registration_of(db, int(s))
            dif = RD.diff_registrations(ra, rb)
            # OBJ.* dimensions may differ only in ways an object swap allows
            # (they should not: same class, m_id follows the id, same famId);
            # everything else must be identical
            structural = [d for d in dif if not str(d.get("dimension", "")).startswith("OBJ.")]
            rows.append({"slot": int(s), "class": ra.class_name,
                         "registration_identical": (len(dif) == 0),
                         "non_object_differences": structural[:6],
                         "object_differences": [d for d in dif if str(d.get("dimension", "")).startswith("OBJ.")][:4],
                         "row": ra.row and {k: ra.row.get(k) for k in
                                           ("creation_ep", "modified_ep", "owner_id", "id_band")},
                         "surface_paths": len(ra.registry)})
    except Exception as ex:                                        # pragma: no cover
        rows.append({"error": repr(ex)[:300]})
    return rows


def _parity_report(ctx: "GS.SubstContext", slots: Set[int], *,
                   latest_identical: bool) -> dict:
    """Registry PARITY of the landed slots: the ADocument surface of every
    slot BEFORE the rung (the parent's tree).  With Global/Latest
    byte-identical the AFTER surface is the same tree, so parity is 100% BY
    CONSTRUCTION -- asserted, not assumed: ``latest_identical`` must hold."""
    surf = GS.adoc_surface(ctx.ted_adoc, ctx.tree, set(slots))
    uet = GS._uet_slots(surf)
    return {
        "slots_landed": len(slots),
        "slots_with_registry_surface": len(surf),
        "positional_uet_slots": [{"slot": i, "paths": p} for i, p in sorted(uet.items())],
        "surface_examples": [{"slot": i, "paths": ps[:4], "n_paths": len(ps)}
                             for i, ps in list(sorted(surf.items()))[:8]],
        "latest_byte_identical": bool(latest_identical),
        "parity": ("100% by construction (Global/Latest byte-identical: every registry "
                   "leaf that indexed a slot still indexes the same id, which now carries OUR "
                   "object)" if latest_identical
                   else "NOT PROVEN: Global/Latest changed (an in-place rung must not)"),
        "pairs": len(slots), "pairs_ok": len(slots) if latest_identical else 0,
        "pairs_failed": 0 if latest_identical else len(slots),
    }


# ===========================================================================
# 7. THE RUNG OPERATOR
# ===========================================================================

def previously_landed(out_dir: str, chain: List[str]) -> Dict[int, str]:
    """{slot: rung} landed by the EARLIER rungs of a derivation chain (their
    reports), so a later rung never re-lands / donates a slot that already
    carries one of our objects (the navigator's viewer must not become a
    donor slot for a plan's viewer)."""
    out: Dict[int, str] = {}
    for name in chain:
        p = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                rep = json.load(fh)
        except Exception:
            continue
        for row in rep.get("landed_slots") or []:
            out[int(row["slot"])] = name
    return out


def prior_correspondence(out_dir: str, chain: List[str]) -> Dict[int, int]:
    """{our temporary record id: slot} from the EARLIER rungs' reports.  Our
    house catalog / constructors allocate DETERMINISTIC temporary ids (each
    rung's context starts allocating at the same watermark band, and the
    catalog builds in a fixed order), so an earlier rung's temporary id for
    'our L1' equals this rung's -- a later rung's records that still
    reference the other layer's records resolve straight to the slots that
    layer landed in."""
    out: Dict[int, int] = {}
    # ``chain`` is nearest-first; walk it FARTHEST-first so a nearer rung's
    # entry wins when two rungs' temporary ids collide
    for name in reversed(chain):
        p = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                rep = json.load(fh)
        except Exception:
            continue
        for row in rep.get("landed_slots") or []:
            if row.get("ours_tmp") is not None:
                out[int(row["ours_tmp"])] = int(row["slot"])
    return out


def derivation_chain(rung: Rung3) -> List[str]:
    """Names of the ancestor rungs (nearest first) up to the BASE."""
    chain: List[str] = []
    cur = rung
    seen = set()
    while cur.parent != "BASE" and cur.parent not in seen:
        chain.append(cur.parent)
        seen.add(cur.parent)
        cur = rung_by_name(cur.parent)
    return chain


def substitute_inplace(rung: Rung3, parent_path: str, base_path: str,
                       out_dir: str = OUT_DIR, *, control: Optional[dict] = None) -> dict:
    """Emit ``<out_dir>/<rung.name>.rvt`` = ``parent_path`` with the rung's
    class layer replaced IN PLACE by our constructors' objects; write the
    certification report ``<rung.name>.json``.  Returns the report."""
    t_all = time.time()
    out = os.path.join(out_dir, f"{rung.name}.rvt")
    log(f"\n== {rung.name} :: {rung.label}")
    log(f"   parent {_relp(parent_path)} (base {_relp(base_path)})")
    base_cert = certification_of(base_path)
    report: Dict[str, Any] = {
        "rung": rung.name, "label": rung.label, "kind": rung.kind,
        "mechanism": ("rvt.regadd.substitute_elements -- IN-PLACE, seqs "
                      f"{list(rung.seqs)} (object record only), keep_row=True (ElemTable row "
                      "byte-identical), Global/Latest byte-identical; nothing added, nothing "
                      "deleted; slot-fill " + ("on" if rung.slot_fill else "off")),
        "base": {"file": _relp(base_path), "certification": base_cert,
                 "lineage": BASE_LINEAGE.get(_relp(base_path), "")},
        "control_to_upload_with_batch": control,
        "parent": _relp(parent_path), "parent_rung": rung.parent, "out": _relp(out),
        "description": rung.description, "tests": rung.tests,
        "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
        "stages": [],
    }
    # ---- 1. context + build ------------------------------------------------
    t0 = time.time()
    ctx = GS.SubstContext(parent_path, rung.name)
    sb = build_for(rung, ctx)
    build_s = round(time.time() - t0, 1)
    old_by_class = collections.Counter(ctx.cls_of.get(int(o), "?") for o in sb.old_ids)
    new_by_class = collections.Counter(r.class_name for r in sb.records)
    log(f"   build: OLD candidates {len(sb.old_ids)} {dict(old_by_class.most_common(5))}; "
        f"OUR records {len(sb.records)} {dict(new_by_class.most_common(5))}; "
        f"correspondence {len(sb.corr)} ({build_s}s)")
    report["parent_context"] = {"host_elements": len(ctx.host), "watermark": ctx.watermark}
    report["candidates_old_by_class"] = dict(old_by_class.most_common())
    report["our_records_by_class"] = dict(new_by_class.most_common())
    report["build_notes"] = sb.notes
    report["build_info"] = sb.info
    report["residue_named_by_builder"] = sb.residue
    # ---- 2. plan --------------------------------------------------------------
    protected = previously_landed(out_dir, derivation_chain(rung))
    plan = plan_inplace(ctx, sb, slot_fill=rung.slot_fill, protected=set(protected))
    match_hist = collections.Counter(p.match for p in plan.pairs)
    landed_by_class = collections.Counter(p.cls for p in plan.pairs)
    log(f"   plan: {len(plan.pairs)} landed {dict(match_hist)}; dropped ours "
        f"{len(plan.dropped)}; residue olds {len(plan.residue)}; class mismatches "
        f"{len(plan.class_mismatch)}; protected slots skipped {len(plan.protected_skipped)}")
    report["plan"] = {
        "landed": len(plan.pairs), "by_match": dict(match_hist),
        "landed_by_class": dict(landed_by_class.most_common()),
        "dropped_ours": len(plan.dropped), "residue_olds": len(plan.residue),
        "class_mismatch": plan.class_mismatch,
        "protected_slots_from_earlier_rungs": plan.protected_skipped[:60],
        "notes": plan.notes,
    }
    if not plan.pairs:
        report["FAILED_SELF_CHECK"] = "no landed pairs -- this class layer does not exist in the parent"
        report["verdict"] = "NOT-BUILT"
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: nothing to substitute (the layer does not exist here)")
        return report
    # ---- 3. retarget + self-check ----------------------------------------------
    t0 = time.time()
    prior_map = prior_correspondence(out_dir, derivation_chain(rung))
    records_by_id, rt_rep = retarget(ctx, sb, plan, seqs=rung.seqs, prior_tmp_to_slot=prior_map)
    report["retarget"] = {k: (v if not isinstance(v, list) else v[:40])
                          for k, v in rt_rep.items()}
    report["retarget"]["seconds"] = round(time.time() - t0, 1)
    log(f"   retarget: {rt_rep['records']} records; leaves remapped {rt_rep['leaves_remapped']}; "
        f"other-layer refs resolved (prior-rung {len(rt_rep['dropped_refs_resolved_by_prior_rung'])}, "
        f"by-name {len(rt_rep['dropped_refs_resolved_by_name'])}), neutralised "
        f"{len(rt_rep['dropped_refs_neutralised'])}; self-check failures "
        f"{len(rt_rep['record_selfcheck_failures'])}")
    if rt_rep["record_selfcheck_failures"]:
        report["FAILED_SELF_CHECK"] = (f"{len(rt_rep['record_selfcheck_failures'])} re-targeted "
                                       "record body/bodies not schema-clean / byte-exact")
        report["verdict"] = "NOT-BUILT"
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: {report['FAILED_SELF_CHECK']} -- NO FILE EMITTED")
        return report
    # every new object must reference only ids that exist afterwards
    slots = set(records_by_id)
    live = set(ctx.universe) | slots
    dangle = []
    for slot, by_seq in records_by_id.items():
        for seq, (cid, val) in by_seq.items():
            cname = "ElementHeader" if seq == 101 else ctx.doc.dec.class_name(cid)
            for lf in ctx.ted.leaves(val, cname):
                v = lf.value
                if isinstance(v, int) and v > 0 and v not in live:
                    dangle.append({"slot": slot, "seq": seq, "path": lf.path, "target": v})
    report["new_object_reference_check"] = {"dangling": len(dangle), "examples": dangle[:12]}
    if dangle:
        report["FAILED_SELF_CHECK"] = f"{len(dangle)} unresolved reference(s) in our re-targeted objects"
        report["verdict"] = "NOT-BUILT"
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: {report['FAILED_SELF_CHECK']} -- NO FILE EMITTED")
        return report
    # ---- 4. the in-place substitution (one EditImage, one emission) ------------
    t0 = time.time()
    srep = regadd.substitute_elements(parent_path, out,
                                      {int(k): {int(s): tuple(v) for s, v in bs.items()}
                                       for k, bs in records_by_id.items()},
                                      seqs=tuple(int(s) for s in rung.seqs),
                                      keep_row=True, verify=True, diff=True)
    emit_s = round(time.time() - t0, 1)
    diff = srep.diff or {}
    pname = (diff.get("streams") and (srep.emit or {}).get("partition")) or "Partitions/?"
    log(f"   emit: {srep.op} verdict {srep.verdict} problems {srep.problems}; streams differing "
        f"{(diff.get('streams') or {}).get('differing')} ({emit_s}s)")
    report["substitute"] = {
        "op": srep.op, "verdict": srep.verdict, "problems": srep.problems,
        "seqs_replaced": srep.seqs_replaced, "elemtable_rows": (srep.emit or {}).get("elemtable_count"),
        "elemtable_rewritten": (srep.emit or {}).get("elemtable_rewritten"),
        "latest_rewritten": (srep.emit or {}).get("latest_rewritten"),
        "streams_replaced": (srep.emit or {}).get("streams_replaced"),
        "seconds": emit_s,
    }
    # ---- 5. certification -----------------------------------------------------
    t0 = time.time()
    byte_delta = _byte_delta_assertions(diff, slots=slots, seqs=rung.seqs, partition_name=pname)
    parity = _parity_report(ctx, slots, latest_identical=bool((diff.get("latest") or {}).get("identical")))
    reg_sample = _registration_diff_sample(parent_path, out, sorted(slots), limit=6)
    try:
        import genesis_triage as GT
        cen = GT.census(out)
    except Exception as ex:                                        # pragma: no cover
        cen = {"error": repr(ex)[:300]}
    coherence = {
        "save_units": cen.get("save_units"), "contentdocs_entries": cen.get("contentdocs_entries"),
        "contenttable_records": cen.get("contenttable_records"),
        "adocument_clean": cen.get("adocument_clean"),
        "coherent": (cen.get("save_units") is not None
                     and cen.get("save_units", 0) - 1 == cen.get("contentdocs_entries")
                     == cen.get("contenttable_records")),
    }
    report["byte_delta"] = byte_delta
    report["parity"] = parity
    report["registration_diff_sample"] = reg_sample
    report["validator"] = srep.validator
    report["structural"] = srep.structural
    report["census"] = {k: cen.get(k) for k in ("path", "elements", "file_size", "save_units",
                                                   "contentdocs_entries", "contenttable_records",
                                                   "adocument_clean") if k in cen}
    report["census"]["classes_top"] = dict(list((cen.get("classes") or {}).items())[:30])
    report["coherence"] = coherence
    report["certification_seconds"] = round(time.time() - t0, 1)
    # ---- 6. the correspondence + queues (the record) ------------------------
    slot_referrers = {p.slot: p.slot_referrers for p in plan.pairs}
    report["correspondence"] = [
        {"ours_tmp": p.ours, "slot": p.slot, "class": p.cls, "match": p.match,
         "role_group": p.role_group, "slot_referrers": p.slot_referrers,
         "our_name": (GS._rec_name(_rec) if (_rec := next((r for r in sb.records
                                                        if int(r.elem_id) == p.ours), None)) else "")}
        for p in sorted(plan.pairs, key=lambda x: x.slot)][:400]
    report["correspondence_note"] = ("all pairs stored" if len(plan.pairs) <= 400
                                     else f"{len(plan.pairs)} pairs; storing the first 400")
    report["landed_slots"] = [{"slot": p.slot, "class": p.cls, "match": p.match,
                               "ours_tmp": p.ours} for p in plan.pairs]
    report["ours_not_landed"] = {
        "count": len(plan.dropped),
        "by_class": dict(collections.Counter(d["class"] for d in plan.dropped).most_common()),
        "examples": plan.dropped[:24],
        "meaning": ("our records that found NO in-place slot in the parent (the parent lacks "
                    "an element of the class, or fewer than we build); landing them requires "
                    "the ADD path -- deliberately NOT this ladder's variable"),
    }
    report["residue_olds_left_in_place"] = {
        "count": len(plan.residue),
        "by_class": dict(collections.Counter(r["class"] for r in plan.residue).most_common()),
        "meaning": ("the parent's candidate elements our set did not land on (surplus sample "
                    "instances / companions): left EXACTLY as they were -- residue for the census"),
    }
    # ---- 7. verdict -------------------------------------------------------------
    problems: List[str] = []
    if srep.verdict != "VALID":
        problems += [f"regadd: {p}" for p in (srep.problems or [])]
    val = srep.validator or {}
    if not (val.get("ok") and val.get("errors") == 0):
        problems.append(f"validator errors={val.get('errors')}")
    if not (srep.structural or {}).get("ok"):
        problems.append("structural proof failed")
    if not byte_delta["assertion_holds"]:
        problems += byte_delta["problems"]
    if not parity["latest_byte_identical"]:
        problems.append("Global/Latest not byte-identical (parity unproven)")
    if not coherence["coherent"]:
        problems.append("four-registry document coherence broken")
    regdiff_bad = [r for r in reg_sample if not r.get("registration_identical")
                   and r.get("non_object_differences")]
    if regdiff_bad:
        problems.append(f"{len(regdiff_bad)} sampled slot(s) show a NON-object registration difference")
    if rt_rep["dropped_refs_neutralised"]:
        report.setdefault("warnings", []).append(
            f"{len(rt_rep['dropped_refs_neutralised'])} record body/bodies had references to our "
            f"NOT-LANDED records neutralised (listed in retarget.dropped_refs_neutralised)")
    report["problems"] = problems
    report["verdict"] = "VALID" if not problems else "NOT-CLEAN"
    if problems:
        report["FAILED_SELF_CHECK"] = "; ".join(problems)
    report["bytes"] = os.path.getsize(out) if os.path.exists(out) else None
    report["seconds"] = round(time.time() - t_all, 1)
    _write_report(out_dir, rung.name, report)
    log(f"   byte-delta: only-partition {byte_delta['only_partition_differs']}; changed "
        f"{byte_delta['records_changed_count']} of {byte_delta['expected_slots']} slots "
        f"(unchanged {byte_delta['landed_but_unchanged_slots']}); ElemTable identical "
        f"{byte_delta['elemtable_identical']}; ADocument identical {byte_delta['adocument_identical']}")
    log(f"   validator: {'VALID' if val.get('ok') else 'INVALID'} errors={val.get('errors')} "
        f"warnings={val.get('warnings')}; structural ok={(srep.structural or {}).get('ok')}; "
        f"coherence {coherence['save_units']}/{coherence['contentdocs_entries']}/"
        f"{coherence['contenttable_records']}; regdiff sample "
        f"{sum(1 for r in reg_sample if r.get('registration_identical'))}/{len(reg_sample)} identical")
    log(f"   -> {_relp(out)} {report['bytes']:,} B  VERDICT {report['verdict']}"
        f"{('  *** ' + report['FAILED_SELF_CHECK']) if problems else ''} ({report['seconds']}s)")
    for m in (val.get("error_messages") or [])[:4]:
        log(f"      ERROR {m}")
    return report


def _write_report(out_dir: str, name: str, rep: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))


# ===========================================================================
# 8. Yn -- THE RESIDUE CENSUS (report rung)
# ===========================================================================
#: extra residue buckets for the in-place ladder (added to
#: genesis_substitute's _RESIDUE_REASONS vocabulary)
_EXTRA_BUCKETS: List[Tuple[Set[str], str, str]] = [
    ({"AppearanceAssetElem", "PropertySetElement", "PropertySetLibrary"},
     "material-companions",
     "the sample materials' render-asset / thermal-physical property-set companions -- our "
     "palette carries none; left in place (a removal rung's business)"),
    ({"PenWidthTableElem"},
     "family-scoped-pen-tables",
     "the 8 curtain-SYSTEM-family-scoped pen tables (m_famId != -1) -- the PROJECT table is ours"),
    ({"BrowserOrganization"},
     "surplus-sample-instances",
     "the sample's non-default browser schemes our two house schemes did not land on"),
    ({"MaterialElem", "FillPatternElem", "LinePatternElem", "Level", "PrintSettings",
      "WorksharingViewModeSettings", "GeoSite", "DBViewPlan", "DBViewDrafting", "DBView3d",
      "Viewer", "Viewport", "DBDrawing", "ExtentElem", "SunAndShadowSettings",
      "SunAnnotationElem", "ModelClipBox", "Viewer3d"},
     "surplus-sample-instances",
     "sample instances of classes our rungs DID substitute, beyond our set's size (extra "
     "materials / patterns / plan-less levels / view companions) -- left as they were"),
    ({"RbsDbViewSystemNavigator"},
     "landed-elsewhere-check",
     "should be landed by Y2 -- if it appears here the plan skipped it"),
    ({"RoomElem", "LevelRoomPlan", "AreaElem", "SpaceElem"},
     "content-removal-candidate",
     "sample room / plan-topology content (a placed room + its LevelRoomPlan companion) -- "
     "placeable CONTENT: a removal rung"),
]


def _residue_bucket(cls_name: str) -> Tuple[str, str]:
    bucket, reason = GS._residue_reason(cls_name)
    if bucket == "unclassified":
        for classes, b, r in _EXTRA_BUCKETS:
            if cls_name in classes:
                return b, r
    return bucket, reason


def run_residue_census(rung: Rung3, subject: str, base_path: str, out_dir: str = OUT_DIR,
                       *, ledger: bool = True) -> dict:
    """Yn: which elements of the deepest rung file are STILL AUTODESK'S (never
    landed on), bucketed by class + reason; which of OUR records found no
    slot anywhere in the ladder (aggregated from the rung reports); plus the
    provenance ledger for the container layer.  Report only."""
    t_all = time.time()
    log(f"\n== {rung.name} :: {rung.label}")
    log(f"   subject {_relp(subject)}")
    chain = [n for n in reversed(derivation_chain(rung))]           # base-side first
    landed = previously_landed(out_dir, chain)                     # slot -> rung
    # the rung that landed each slot (chain order: earliest first wins... keep latest? in-place
    # slots are never re-landed, so first == only)
    dropped_all: Dict[str, dict] = {}
    for name in chain:
        p = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            rep = json.load(fh)
        onl = rep.get("ours_not_landed") or {}
        if onl.get("count"):
            dropped_all[name] = {"count": onl.get("count"), "by_class": onl.get("by_class")}
    doc = Document.from_file(subject)
    ours_by_rung: Counter = collections.Counter()
    ours_by_class: Counter = collections.Counter()
    residue: Counter = collections.Counter()
    for e in doc.et_by_id:
        cls_name = doc.class_of(e) or "?"
        if int(e) in landed:
            ours_by_rung[landed[int(e)]] += 1
            ours_by_class[cls_name] += 1
        else:
            residue[cls_name] += 1
    buckets: Dict[str, dict] = {}
    for cls_name, n in residue.most_common():
        bucket, reason = _residue_bucket(cls_name)
        b = buckets.setdefault(bucket, {"elements": 0, "classes": {}, "reason_examples": []})
        b["elements"] += n
        b["classes"][cls_name] = n
        if len(b["reason_examples"]) < 3 and reason not in b["reason_examples"]:
            b["reason_examples"].append(reason)
    residue_rows = [{"class": c, "count": n, "bucket": _residue_bucket(c)[0],
                     "reason": _residue_bucket(c)[1]} for c, n in residue.most_common()]
    report: Dict[str, Any] = {
        "rung": rung.name, "label": rung.label, "kind": rung.kind,
        "subject": _relp(subject), "parent_rung": rung.parent,
        "base": {"file": _relp(base_path), "certification": certification_of(base_path)},
        "description": rung.description, "tests": rung.tests,
        "elements_total": len(doc.et_by_id),
        "landed_ours": {"elements": sum(ours_by_rung.values()),
                        "by_rung": dict(ours_by_rung), "by_class": dict(ours_by_class.most_common()),
                        "meaning": ("elements whose seq-102 OBJECT is now OUR constructor's, at "
                                    "Autodesk's own id / row / registration (in-place)")},
        "residue_still_autodesk": {"elements": sum(residue.values()), "classes": len(residue),
                                   "by_bucket": buckets, "table": residue_rows},
        "ours_not_landed_across_ladder": dropped_all,
        "genesis_candidate": (_relp(subject) if sum(residue.values()) == 0 else None),
        "stages": [],
    }
    log(f"   elements {len(doc.et_by_id):,}: LANDED-OURS {sum(ours_by_rung.values()):,} "
        f"(by rung {dict(ours_by_rung)}); RESIDUE {sum(residue.values()):,} "
        f"({len(residue)} classes)")
    for bkt, b in sorted(buckets.items(), key=lambda kv: -kv[1]["elements"]):
        top = dict(sorted(b["classes"].items(), key=lambda kv: -kv[1])[:6])
        log(f"      {bkt:34s} {b['elements']:5d}  {top}")
    if dropped_all:
        log(f"   ours-not-landed across the ladder: "
            f"{ {k: v['count'] for k, v in dropped_all.items()} }")
    if ledger:
        t0 = time.time()
        try:
            import genesis_assemble as GA
            rep_l = GA.run_ledger_v2(subject, json_out=os.path.join(out_dir, f"{rung.name}_provenance.json"))
            summ = GA.summarize_ledger(rep_l)
            report["provenance_ledger"] = summ
            gl = summ.get("global_latest") or {}
            report["stages"].append({"stage": "provenance ledger v2 (--baseline all --streams)",
                                     "seconds": round(time.time() - t0, 1)})
            log(f"   ledger: bytes identical-to-baseline {summ['bytes']['identical_pct']}% "
                f"(excl. schema {summ['bytes']['excluding_schema_identical_pct']}%); ours "
                f"{summ['bytes']['ours_pct']}%; Global/Latest {gl.get('identical_pct')}% identical")
        except Exception as ex:                                    # ledger is advisory
            report["provenance_ledger_error"] = repr(ex)[:400]
            log(f"   ledger: skipped ({ex!r})")
    report["seconds"] = round(time.time() - t_all, 1)
    report["verdict"] = "GENESIS-CANDIDATE" if sum(residue.values()) == 0 else "RESIDUE-LISTED"
    _write_report(out_dir, rung.name, report)
    log(f"   -> {rung.name}.json  VERDICT {report['verdict']} ({report['seconds']}s)")
    return report


# ===========================================================================
# 9. probes.json (the upload manifest, BISECTION-FIRST)
# ===========================================================================
#: bisection-first upload order: the deepest cumulative rung first (a PASS
#: proves the whole chain in one verdict), then the biggest single-layer
#: substitution, then the two single-change probes, then the intermediates
UPLOAD_ORDER = ["Y9", "Y6", "Y_pen", "Y_cat", "Y1", "Y2", "Y3", "Y4", "Y5", "Y7", "Y8"]


def write_probes_manifest(out_dir: str = OUT_DIR, base_path: str = DEFAULT_BASE,
                          control: Optional[dict] = None) -> str:
    reps: Dict[str, dict] = {}
    for rung in RUNGS:
        p = os.path.join(out_dir, f"{rung.name}.json")
        if os.path.exists(p):
            with open(p) as fh:
                reps[rung.name] = json.load(fh)
    base_cert = certification_of(base_path)
    entries: List[dict] = []
    for order, name in enumerate(UPLOAD_ORDER, 1):
        rung = rung_by_name(name)
        rep = reps.get(name) or {}
        if rung.alias_of:
            target = reps.get(rung.alias_of) or {}
            entries.append({
                "order": order, "rung": name, "alias_of": rung.alias_of,
                "file": f"{_relp(out_dir)}/{rung.alias_of}.rvt",
                "note": (f"IDENTICAL to {rung.alias_of} ({rung.alias_of} is the base + only the pen "
                         "table in place); upload ONCE, record the verdict for both names"),
                "base": {"file": _relp(base_path), "certification": base_cert},
                "the_ONE_thing_it_tests": rung.tests,
                "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
                "verdict_of_alias_target": target.get("verdict", "not built"),
                "control_to_upload_with_batch": control,
            })
            continue
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        plan = rep.get("plan") or {}
        entries.append({
            "order": order, "rung": name,
            "file": f"{_relp(out_dir)}/{name}.rvt",
            "class_layer_substituted": rung.label,
            "base": {"file": _relp(base_path), "certification": base_cert,
                     "lineage": BASE_LINEAGE.get(_relp(base_path), "")},
            "derived_from": rep.get("parent") or (
                _relp(base_path) if rung.parent == "BASE" else f"{_relp(out_dir)}/{rung.parent}.rvt"),
            "parent_rung": rung.parent,
            "passing_sibling": (
                "the certified base itself (staged as the control)" if rung.parent == "BASE"
                else f"{rung.parent}.rvt (this rung's parent: PASS-parent + FAIL-here convicts "
                     f"exactly THIS rung's class layer)"),
            "the_ONE_thing_it_tests": rung.tests,
            "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
            "mechanism": rep.get("mechanism"),
            "elements_substituted_in_place": {"landed": plan.get("landed"),
                                              "by_class": plan.get("landed_by_class"),
                                              "by_match": plan.get("by_match")},
            "ours_not_landed": (rep.get("ours_not_landed") or {}).get("by_class"),
            "residue_left_in_place": (rep.get("residue_olds_left_in_place") or {}).get("count"),
            "byte_delta": ({k: bd.get(k) for k in ("only_partition_differs", "records_changed_count",
                                                    "expected_slots", "unexpected_changed_ids",
                                                    "records_added_ids", "records_removed_ids",
                                                    "elemtable_identical", "adocument_identical",
                                                    "assertion_holds")} if bd else None),
            "registry_parity": (rep.get("parity") or {}).get("parity"),
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"), "warnings": v.get("warnings")},
            "structural_ok": (rep.get("structural") or {}).get("ok"),
            "document_coherence": rep.get("coherence"),
            "verdict": rep.get("verdict", "not built"),
            "self_check": rep.get("FAILED_SELF_CHECK"),
            "bytes": rep.get("bytes"),
            "control_to_upload_with_batch": control,
            "report": f"{_relp(out_dir)}/{name}.json",
        })
    yn = reps.get("Yn") or {}
    manifest = {
        "stream": "genesis-rebase (THE SUBSTITUTION LADDER v3 -- rebased on a CERTIFIED base, "
                  "pure IN-PLACE object substitution)",
        "situation": (
            "ORCHESTRATOR VERDICT #15 (2026-08-04): K1 -- the base of the entire X-rung / S / R / C / "
            "P program -- FAILS on its own (crash -1073741831, no Revit-DocumentCorruption line, "
            "'Design is empty'); nothing K1-derived ever passed; verdicts #9-#14's conclusions are "
            "RETRACTED artefacts of the broken base. This ladder re-points the (sound) substitution "
            "engine at a CERTIFIED base (K4: family-free, four-registry coherent, viewer-PASSED) and "
            "uses IN-PLACE substitution -- zero registration motion -- so the ONE variable of every "
            "rung is the CONTENT of our objects at Autodesk's own registrations."),
        "the_operation": (
            "In-place substitution (rvt.regadd.substitute_elements): our constructor's OBJECT record "
            "(seq-102) replaces the sample's at the SAME element id -- same ElemTable row (episodes / "
            "owner / vintage byte-identical), same record position, same registry slots; Global/Latest "
            "and Global/ElemTable are BYTE-IDENTICAL to the parent; nothing added, nothing deleted. Our "
            "records land on their role correspondent (X-ladder correspondence rules) or, without one, "
            "a free same-class donor slot (slot-fill); every rung asserts validator 0 errors, the "
            "structural proof, four-registry coherence, registry parity (by construction, asserted), a "
            "rvt.regdiff registration-diff sample, and the rvt.regadd byte-delta table (ONLY the "
            "landed slots' object records change; exceptions listed)."),
        "base": {"file": _relp(base_path), "certification": base_cert,
                 "lineage": BASE_LINEAGE.get(_relp(base_path), "")},
        "standing_control": (control or {"note": "not staged (run without --manifest-only)"}),
        "controls_discipline": (
            "EVERY batch is uploaded with the certified control CTRL_K4_base.rvt (md5-identical "
            "to the certified base). If the CONTROL fails, the batch is VOID (oracle / service "
            "health) and NOTHING about our constructors is read from it -- re-run the batch. Only "
            "with the control PASSING are the probe verdicts read."),
        "upload_order_bisection_first": [e["rung"] for e in entries],
        "reading_the_results": {
            "how": ("Upload in the listed order (control first). Y9 is the deepest CUMULATIVE rung: "
                    "Y9 PASS proves EVERY constructor of this ladder loads at Autodesk's "
                    "registrations in one verdict (then only Yn's residue queue + the add path "
                    "remain). Y9 FAIL -> read Y6 (the biggest single layer, cumulative through the "
                    "settings), Y_pen and Y_cat (single-change, straight off the base) to bracket the "
                    "first failing layer; then the intermediates Y1..Y5 / Y7 / Y8 in order -- the "
                    "first FAIL whose parent PASSED convicts exactly that rung's class layer "
                    "(named in 'class_layer_substituted'), with every registration variable already "
                    "eliminated by construction."),
            "Y_pen FAIL": ("even ONE our-object at Autodesk's registration fails: our object CONTENT "
                           "grammar is the defect (diff the pen record vs the base's id 2); expect "
                           "the whole ladder to fail until fixed."),
            "Y_pen PASS + Y_cat FAIL": "our object-styles VALUES are the reader's objection (the catalog question, isolated).",
            "Y_pen + Y_cat PASS, Y6 FAIL": ("a settings-layer constructor (Y2..Y5) is rejected -- the "
                                            "intermediates name it."),
            "Y6 PASS, Y9 FAIL": "the palette (Y7), the datum/identity layer (Y8) or the view layer (Y9): the intermediates name it.",
            "ALL PASS": ("EVERY constructor this ladder owns loads at Autodesk's registrations. What "
                         "remains: (1) Yn's residue queue (classes without constructors / removal "
                         "candidates / product data); (2) the ADD path -- landing our slot-less "
                         "records (235 catalog rows, filters, house schemes, text types) is a "
                         "REGISTRATION question, now testable one variable at a time on this "
                         "certified base; (3) the container layer (History / DIT / Formats / the "
                         "Forge corpus) -- own-save + counsel territory."),
        },
        "residue_census": ({"subject": yn.get("subject"), "verdict": yn.get("verdict"),
                            "elements_total": yn.get("elements_total"),
                            "landed_ours": (yn.get("landed_ours") or {}).get("elements"),
                            "landed_by_rung": (yn.get("landed_ours") or {}).get("by_rung"),
                            "residue_elements": (yn.get("residue_still_autodesk") or {}).get("elements"),
                            "residue_by_bucket": {k: {"elements": v.get("elements"), "classes": v.get("classes")}
                                                  for k, v in ((yn.get("residue_still_autodesk") or {})
                                                               .get("by_bucket") or {}).items()},
                            "ours_not_landed_across_ladder": yn.get("ours_not_landed_across_ladder"),
                            "report": f"{_relp(out_dir)}/Yn.json"} if yn else None),
        "probes": entries,
        "derivation_chain": [f"{r.name} <- {r.parent}" for r in RUNGS if r.kind != "alias"],
    }
    p = os.path.join(out_dir, "probes.json")
    os.makedirs(out_dir, exist_ok=True)
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"\n[probes] wrote {_relp(p)} ({len(entries)} entries)")
    return p


# ===========================================================================
# 10. DRIVER
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default=DEFAULT_BASE,
                    help="the CERTIFIED base file (default: experiments/genesis/triage/K4.rvt)")
    ap.add_argument("--out-dir", default=OUT_DIR, help="output directory")
    ap.add_argument("--only", default="", help="comma list of rungs to build (Y1,Y_cat,...)")
    ap.add_argument("--manifest-only", action="store_true", help="only (re)write probes.json")
    ap.add_argument("--no-ledger", action="store_true", help="Yn: skip the provenance ledger")
    ap.add_argument("--allow-uncertified", action="store_true",
                    help="build on a base NOT listed as viewer-certified (never for a real batch)")
    args = ap.parse_args(argv)
    base_path = os.path.abspath(args.base)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.exists(base_path):
        log(f"base {base_path} does not exist")
        return 2
    cert = assert_certified(base_path, allow_uncertified=args.allow_uncertified)
    log(f"[base] {_relp(base_path)} -- CERTIFIED: {cert.get('proves')}")
    log(f"[base] lineage: {BASE_LINEAGE.get(_relp(base_path), '(unrecorded)')[:160]}...")
    control = stage_control(base_path, out_dir)
    log(f"[control] staged {control['file']} (md5 {control['md5']}) -- upload with EVERY batch")
    t0 = time.time()
    want = [s.strip() for s in args.only.split(",") if s.strip()]
    if not args.manifest_only:
        for rung in RUNGS:
            if want and rung.name not in want:
                continue
            if rung.kind == "alias":
                continue                                  # Y_pen == Y1 (manifest only)
            parent = parent_path_of(rung, base_path, out_dir)
            if not os.path.exists(parent):
                log(f"\n== {rung.name}: parent {_relp(parent)} missing -- SKIPPED (build {rung.parent} first)")
                continue
            try:
                if rung.kind == "report":
                    run_residue_census(rung, parent, base_path, out_dir, ledger=not args.no_ledger)
                else:
                    substitute_inplace(rung, parent, base_path, out_dir, control=control)
            except Exception as ex:                           # a rung that cannot build is a FINDING
                import traceback
                tb = traceback.format_exc()
                log(f"\n== {rung.name}: BUILD ABORTED -- {ex!r}\n{tb}")
                _write_report(out_dir, rung.name, {"rung": rung.name, "label": rung.label,
                                                  "verdict": "NOT-BUILT", "abort": repr(ex),
                                                  "traceback": tb})
                bad = os.path.join(out_dir, f"{rung.name}.rvt")
                if os.path.exists(bad):
                    os.remove(bad)                        # never leave a half-built rung
                if not want:
                    break                                 # cumulative ladder stops honestly
    write_probes_manifest(out_dir, base_path, control)
    log("\n=== SUBSTITUTION LADDER v3 (in place, base K4) SUMMARY ===")
    for rung in RUNGS:
        p = os.path.join(out_dir, f"{rung.name}.json")
        if rung.kind == "alias" or not os.path.exists(p):
            continue
        with open(p) as fh:
            rep = json.load(fh)
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        plan = rep.get("plan") or {}
        log(f"  {rung.name:<6} {rep.get('verdict', '?'):<10} validator ok={v.get('ok')} "
            f"errors={v.get('errors')} warnings={v.get('warnings')}  landed "
            f"{plan.get('landed', '-') if plan else '-'}  changed "
            f"{bd.get('records_changed_count', '-')}  latest-identical "
            f"{bd.get('adocument_identical', '-')}  {rep.get('bytes', 0) or 0:>9,} B  {rung.label[:56]}")
    log(f"total {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
