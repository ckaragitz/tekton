# genesis-substitute — THE SUBSTITUTION LADDER (workstream record, 2026-08-03)

Charter: the constructive twin of the reduction ladder, and the path that
CANNOT dead-end.  Start from K1 (Autodesk's empty-project skeleton,
viewer-PASSED) and REPLACE its Autodesk-authored content with OUR
constructors' output CLASS BY CLASS, cumulatively, one class(-group) per
rung, every rung derived from a PASSING file, with every ADocument
registry re-pointed to our ids EXACTLY as the sample's indexed the
originals (parity ASSERTED), and every emitted file validator-clean.  The
first rung the viewer rejects names the exact one of OUR constructors the
reader disagrees with; a clean run to Xn is the genesis base modulo the
residue Xn lists.

Territory touched ONLY: `tools/genesis_substitute.py` (new),
`tests/test_genesis_substitute.py` (new, 9 pass),
`experiments/genesis/subst/*` (10 rung `.rvt` + per-rung `.json` reports +
`probes.json` + `Xn.json` + `Xn_provenance.json`),
`docs/writer/substitution-ladder.md` (new — the full design/results
document; READ IT for the method, the correspondence rules per rung and
the KNOWLEDGE findings), this record.  NO existing `src/rvt/*.py`, tool or
test edited — every dependency (`rvt.reduce` / `rvt.manipulate` /
`rvt.commit` / `rvt.adocument` / `rvt.genesis.settings` / `catalog` /
`house_standard` / `skeleton` / `types`, `tools/rvt_reduce.py`,
`tools/genesis_assemble.py`, `tools/genesis_triage.py`) is IMPORTED.
No browser / viewer use: the ten `.rvt` are LEFT ON DISK for the
orchestrator's queue.

## Result in one screen

**TEN cumulative rungs built, EVERY ONE validator-VALID (0 errors),
structurally proven, four-registry coherent, and 100 % registry-parity —
all the way from Autodesk's skeleton down to a 4,346-element file whose
settings layer, catalog, palette, identity and document skeleton are
OURS.**  Reproduce: `.venv/bin/python tools/genesis_substitute.py` (~4 min).

| # | rung | substitutes | corr / unmapped / new-only | referrers re-pointed | parity | after | verdict |
|--:|---|---|---|--:|---|--:|---|
| 1 | **X1** | project PenWidthTableElem (id 2, the census's #1 singleton suspect) | 1 / 0 / 0 | 0 | 1/1 | 24,615 el | VALID |
| 2 | **X2** | 11 BrowserOrganizations + system-navigator constellation + reconcile-browser + construction-set | 10 / 7 / 2 | 1 | 10/10 | 24,610 | VALID |
| 3 | **X3** | StructSettings, wall-join, auto-join, keynote table (EMPTY, ours) + system, initial view | 6 / 0 / 0 | 1 | 6/6 | 24,610 | VALID |
| 4 | **X4** | RbsWire/Pipe/Duct Settings + Sizes (OUR NEC / ASME / ASTM / SMACNA data), conduit + cable-tray settings | 8 / 0 / 0 | 2 | 8/8 | 24,610 | VALID |
| 5 | **X5** | 51 remaining settings singleton / tracker classes | 53 / 3 / 0 | 117 | 53/53 | 24,607 | VALID |
| 6 | **X10** | loadable-family layer + ALL 52 documents REMOVED (K3+K4's viewer-PASSED op) | 1,196 deleted | 28 | coherence 1/0/0/0 | 5,336 | VALID |
| 7 | **X6a** | the 1,407-row built-in GStyle catalog → OUR complete catalog (1:1 by category × type) | 1,407 / 0 / 0 | 99 | 1,407/1,407 | 5,336 | VALID |
| 8 | **X7** | line/fill patterns + materials + assets → our palette (many-to-one by role) | 81 / 466 / 0 | 305 | 81/81 | 4,811 | VALID |
| 9 | **X8** | units, true north, sites/geo-locations, base points, project info | 8 / 1 / 0 | 144 | 8/8 | 4,811 | VALID |
| 10 | **X9** | the document skeleton: levels + phases + filters + 19 view types + EVERY view + text types | 67 / 467 / 0 | 80 | 67/67 | 4,346 | VALID |
| — | **Xn** | residue check: OURS 1,584 / K1-inherited 2,762 in 9 named buckets, 0 unclassified | — | — | — | 4,346 | RESIDUE-LISTED |

Arbiter batch (pasted, this session): `tools/rvt_validate.py --quiet
experiments/genesis/subst/X*.rvt` → 10 × `OK errors=0 warnings=1` (the one
warning = the pre-existing Extensible-Storage decode gap on 7 residue
elements, untouched).

Recommended upload order = derivation order: **X1, X2, X3, X4, X5, X10, X6a,
X7, X8, X9** (`probes.json:upload_order`).  Every rung is cumulative; the
first FAIL whose parent PASSED convicts exactly that rung's class group.

## THE finding that shaped the ladder (order)

A measurement on the X5 base found **1,421 of the built-in catalog rows'
referrers INSIDE the embedded family documents** (uneditable by the host
path) + 238 Family / 228 FamilySymbol referrers.  The catalog CANNOT be
substituted while documents pin it, so the family-layer removal (the
brief's X10 = K3+K4's viewer-PASSED operation) is derived right after X5
and the catalog rungs derive from it.  On the X10 output ZERO referrers
live in documents.  (Full reasoning: `docs/writer/substitution-ladder.md
§3`.)  Second order finding: **plan views are BOUND to levels**
(`DBViewPlan.m_genElemId` = its generating level, and the
`LevelPlanViewTracking` level→plan map indexes both), so views + levels +
phases are ONE coherent substitution (X9), the level correspondence
DERIVED from the plan correspondence — with X8 (units / site / info)
before it.

## The method's proof of value: what the PARITY assertion caught

The validator reported 0 errors, yet the before/after registry-parity
table FAILED on X9's first build with two GENUINE registry defects — the
exact class of mis-registration this workstream exists to eliminate:

1. Our plan 2 was orphaned from `LevelPlanViewTracking.m_levelIdToPlanViewIds`
   (wrong plan→level field; the fix reads `DBViewPlan.m_genElemId`).
2. Our X3 `InitialViewSettings` VANISHED (UET slot 43 went empty): the
   reduction ladder's ownership set kills view-referencing trackers with
   their views — right for a reduction, wrong for a substitution.  Fix:
   `SUBST_CHILD_CLASSES` (trackers that only REFERENCE the seed survive and
   are re-pointed).

Both fixed; both would have been invisible without asserting parity.
**Validator-clean and registry-correct are different gates.**

## New format / method findings (evidence — merge into KNOWLEDGE.md)

(Complete list with [V] evidence in `docs/writer/substitution-ladder.md
§7`; the headline items:)

1. **Reference discovery MUST be schema-typed** — the untyped byte-scan
   referrer path is FOOLED for low ids (the pen table's id 2 gets ~40
   false referrers from geometry-step counters); the arbiter-typed graph
   finds none.  `genesis_substitute.TypedEditor` (over
   `AdocGraphEditor.iter_leaves`) is the safe primitive for records AND
   the ADocument.
2. **Substitution ownership ≠ reduction ownership** (`SUBST_CHILD_CLASSES`).
3. **A plan's level is `m_genElemId`**; `LevelPlanViewTracking` maps
   level → plan ids (load-walked).
4. **A real file's built-in style rows == exactly our catalog's ENUM**
   (1,074 + 333) — the catalog substitution is a true 1:1.
5. **Embedded documents pin the host catalog** (1,421 typed edges) — the
   removal must precede any catalog substitution.
6. **The four-registry document removal composes with a substituted
   settings layer** (X10 VALID over X1..X5, 0 residual GUID bytes).
7. `standard_settings(tier="all")` is not sliceable by class (its MEP
   tracker constellation is self-wired) — assemble class by class from
   the CURRENT file's wiring.
8. MEP catalog names need normalization ('Aluminium'); uncovered catalog
   symbols get NO rows (documented), never invented data.

## The correspondence rules and OUR-data provenance per rung

`docs/writer/substitution-ladder.md §4` gives the per-rung rules.  Two
provenance notes for the ledger reader:
* **X4's size tables are OUR DATA, authored in the tool as published
  dimensional facts** (like the NEC tables the settings stream already
  cites): ASME B36.10M sch 40/80, ASME B36.19M 10S, ASTM B88 copper types
  K/L/M (OD + wall → ID), our SMACNA duct series, NEC ampacity.  Range
  choice is ours; the numbers are standards facts.
* **X7's palette is the house standard's** (4 line patterns, 5 fill
  patterns, 13 materials incl. our four phase-override materials — no
  Autodesk asset binding, no property sets); the 131 AppearanceAssetElem
  naming Autodesk's `assetlibrary_base.fbx` and the property-set data are
  DELETED, not carried.

## The residue (Xn) = the honest work queue

After X9: 4,346 host elements — **1,584 OURS** (ids ≥ 1,500,000, 99
classes), **2,762 K1-inherited RESIDUE** (140 classes), 0 unclassified.
The nine buckets (counts / disposition) are tabled in
`docs/writer/substitution-ladder.md §6`; ranked as the next queue:

1. **The subcategory / line-style layer** (932 el: 386 CategoryElem + 546
   GStyle rows) — Revit's auto-created angle-bracket line styles +
   template subcategories — **NO our-constructor: the X6b GAP.**  Needs a
   "built-in subcategory table" constructor (the ~30 required-token line
   styles every project auto-creates) before it can be substituted.
2. **Parameter definitions + bindings** (791 el) — a GC-removal rung (the
   R10 class group) is the cheap route; a definition constructor the
   thorough one.
3. **Annotation attribute types + fonts + misc machinery** (312 el, no
   constructors) and **the HVAC space-type database** (212 el, product
   data → counsel/removal).
4. **MEP catalogs** (314 el, constructors exist / partial) and **system
   family types** (constructor-partial) — catalog + system-types rungs.
5. **The 8 curtain-wall SYSTEM families** (106 el incl. their 72
   family-scoped view types) — no constructor.
6. **Datum / model-line / legend CONTENT** (93 el) — removal or a
   datum-content rung.  **The linked Revit model** (2 el) — REMOVE.

**Container layer (out of every element rung's scope):** the ledger on X9
reports 65.8 % of inflated bytes identical to a baseline (`Formats/Latest`
schema, the Forge corpus + our re-encoded ADocument machinery in
`Global/Latest` 96.5 % identical, History / DIT / partition-table
lineage) — the own-save + counsel (C4) territory the genesis audit names.
A viewer PASS of X9 proves OUR CONSTRUCTORS load; it does NOT by itself
deliver the sample-free container.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/manipulate.py` (manipulation stream)** — `referrers()` /
  `candidate_referrers()` should offer a TYPED mode (walk records with the
  arbiter's `_RefDecoder` / the `AdocGraphEditor` leaf walker) or at least
  warn on target ids < 10^5: the byte-scan false positives on low ids are a
  silent corruption hazard for any caller that re-points what it finds.
* **`src/rvt/genesis/settings.py` (singletons stream)** — expose the
  standard constellation as PER-CLASS builders with explicit wiring
  parameters (X5 had to re-assemble it class by class because
  `standard_settings(tier=...)`'s MEP tracker constellation is self-wired);
  consider a `wire_sizes` variant that documents uncovered catalog
  symbols; the `_norm_name('aluminium')` normalization belongs there too.
* **`src/rvt/genesis/catalog.py`** — a "built-in SUBCATEGORY table"
  generator (the X6b gap): the required-token angle-bracket line styles +
  standard subcategories every project auto-creates (an enum-like registered
  set, like the graphic-category enum) is the missing constructor named by
  Xn's largest bucket.
* **`src/rvt/validate.py` (validation stream)** — a registry-parity /
  registry-coherence layer: each present singleton's id sits in its
  registry surface (`settings.ADOC_REGISTRY`), each level appears in
  `LevelPlanViewTracking` with its plans, `DBViewTypesForNewLevel` /
  `SymbolIdMgr` defaults resolve — this stream's parity assertion is the
  reference implementation and caught two 0-error-validator defects.
* **`tools/genesis_assemble.py` (genesis-2)** — the genesis base of record
  should now be built the SUBSTITUTION way (start from the passing
  skeleton, replace by class with parity asserted) rather than assembled
  cold onto a constructed base; `_house_records` + `_rewire_subset` here
  show how to slice the house catalog per layer with current-file wiring.
* **`tools/sync_plugin.py`** — this stream adds NO `src/` module (a tool
  only), so nothing new to sync; the pre-existing plugin-drift test is
  untouched.

## Open questions (need the viewer / a decision)

* The ten verdicts, IN UPLOAD ORDER; read per §8 of the ladder document.
  Every branch of the interpretation is pre-stated in each rung's
  `if_PASS` / `if_FAIL`.
* The two TOKEN questions riding on X7 (probe rows): does the reader key on
  the sample's `'<Solid fill>'` NAME (ours is a structural zero-grid solid
  under our own name) and on a `'Default'`-named material (ours has none)?
  If X7 FAILS with those in the card message, they are REQUIRED TOKENS for
  the counsel list.
* Whether the K1-inherited dangling view ids in `DBViewInfo.m_DBViewsIndex`
  (present in every PASSING K/X file, so tolerated) should be purged for
  the base of record — cosmetic, not a load question.
* The X6b constructor (subcategory layer) — build it, or take the removal
  route for the un-referenced part first?

## Proposed next tasks (orchestrator decides)

1. Upload the ten rungs in order; read the first FAIL against its parent.
2. If X1..X5 all PASS: retire the S-set / singleton question (the S5 FAIL
   was the G1 base) and merge findings 1–2, 7–8 into the singletons stream.
3. If X6a PASSES: the catalog counsel item is now purely a legal decision
   (a full table over their enum, our values) — engineering proven.
4. Whatever PASSES becomes the base of record; then work Xn's queue in
   §"residue" order: the X6b subcategory constructor; a param-definitions
   GC rung; the link removal; the datum-content rung; MEP catalog +
   system-types rungs — each as a further rung of THIS ladder (the tool
   is table-driven: one `Rung(...)` + one `build_*` per class group).
5. Fold this stream's parity assertion into `rvt.validate` (see Diffs).

## Verification

* `tools/rvt_validate.py` on all ten rung files → `OK errors=0 warnings=1`
  ×10 (pasted above); per-rung reports carry the structural proof, the
  four-registry census, the parity table and the referrer-repoint log.
* `.venv/bin/python -m pytest tests/test_genesis_substitute.py -q` → **9
  passed** (typed-walk correctness on the pen-table false positives + the
  DBViewProject regen edges; the surface / path-normalization rules; the
  substitution ownership set; one end-to-end X1 with parity + certification
  + registry read-back; the new-record dangling-reference REFUSAL guard;
  built-ladder report + manifest consistency).
* Full suite: see BRANCH STATE.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files:
`tools/genesis_substitute.py`, `tests/test_genesis_substitute.py` (9
pass), `docs/writer/substitution-ladder.md`,
`docs/inbox/genesis-substitute.md` (this file), and under
`experiments/genesis/subst/`: `X1 X2 X3 X4 X5 X10 X6a X7 X8 X9 .rvt` + one
`.json` report each + `probes.json` + `Xn.json` + `Xn_provenance.json`
(+ `.txt`).  Every emitted `.rvt` = validator VALID (0 errors),
structural proof clean, four-registry coherent, registry parity 100 %.
Full suite this session (`.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle`): **736 passed, 3 failed** (13:40).  This stream's
9 tests are among the 736.  The 3 failures are the pre-existing,
other-stream ones every recent record lists — none touching this stream's
files: `test_plugin_sync.py::test_plugin_is_in_sync_with_source` (the
plugin-bundle drift; this stream adds NO `src/` module, so nothing new to
sync — fix remains the orchestrator's `python tools/sync_plugin.py` run)
and `test_provenance.py::{test_G0_resource_refs_are_counted,
test_G0_identity_dit_usernames_still_leak}` (the STALE assertions pinning
the pre-genesis-2 G0 defects; their owner's diff is in
docs/inbox/genesis-2.md).  Ledger caveat recorded in Xn: the byte-shingle
element classifier reads many of OUR no-free-choice machinery records
(empty trackers, catalog rows) as 'transitive-cloned' — the singletons
stream's documented limitation; Xn's own id-band split (OURS 1,584 /
residue 2,762) is the authoritative element accounting for this ladder.
STOPPED AT READY — the ten rungs await the orchestrator's viewer gate;
Xn's residue queue is the recorded next work.
