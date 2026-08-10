# steplite-parity — foreign classes stay in the IfcProduct / IfcElement closures (stream record)

**Stream:** steplite-parity (issue #155; perf-deps territory).  **Date:** 2026-08-09.
**Charter (the issue's DONE):** steplite — THE IFC reader on bare surfaces —
must give the same `by_type` / `is_a` answers as ifcopenshell for entity
classes outside its transcribed attribute subset, so the same IFC converts
to the same product set on a Cowork VM (no wheel) and on a laptop (wheel);
explicit rows for the common building / electrical-MEP classes, ports,
systems and void/fill relations; pinned + parity tests; dependency audit
updated; plugin mirrors regenerated.

## What landed

1. **`src/rvt/ifc/ifc4_parents.py`** (new, generated, our own text) — the
   complete IFC4 entity hierarchy as `PARENT: {"IfcChild": "IfcParent" | None}`,
   776 entities, 59 roots, no attribute lists, imports nothing.  Produced by
   **`tools/dev/gen_ifc4_parents.py`** (new, dev-only): it reads
   `entity.name() -> entity.supertype().name()` out of a locally installed
   ifcopenshell's `schema_by_name("IFC4")` — i.e. buildingSMART's public
   IFC4 ADD2 TC1 EXPRESS declarations — and writes them down as python
   source with a provenance header; `--check` exits 1 on drift (a test runs
   it when the wheel is importable).  ifcopenshell is an input of the
   GENERATOR only; nothing new is imported at runtime (hard rule 3: schema
   facts, zero vendor file bytes; `pyproject.toml` untouched).
2. **`src/rvt/ifc/steplite.py`** — the class tree is now the UNION of the
   transcribed `_SCHEMA` rows and `ifc4_parents`:
   * `is_a(name)` walks the unified parent chain; `is_a()` returns the true
     CamelCase for every IFC4 entity (was `Ifc` + title-case guess);
   * `by_type(name)` closes over every IFC4 subtype whether or not steplite
     transcribes its attributes; sibling order = ifcopenshell's
     `entity.subtypes()` order, which is **case-sensitive** CamelCase
     (`IfcCShapeProfileDef` before `IfcCircleProfileDef`,
     `IfcRelConnectsPortToElement` before `IfcRelConnectsPorts` — the only
     two IFC4 parents where that differs from case-insensitive; found by the
     new subtype-order cross-check, not by luck); instances per class in
     **file order** (was id-sorted) because that is what ifcopenshell keeps
     for `by_type` and for the inverse attributes — identical on every
     writer that numbers records as it emits them (all reference files,
     all conformance fixtures), a parity fix on hand-edited files;
   * attribute access for an untranscribed IFC4 class serves the positional
     attributes of its nearest transcribed ancestor (a true prefix of its
     STEP arguments: `GlobalId, OwnerHistory, Name, Description, ObjectType,
     ObjectPlacement, Representation, Tag` for anything under IfcElement);
     only its own leaf attributes raise, with a message naming what IS
     served; `by_guid` indexes those entities too;
   * new transcribed rows (own attributes in exact IFC4 order): IfcDoor,
     IfcWindow, IfcColumn, IfcBeam, IfcMember, IfcPlate, IfcFooting, IfcRoof,
     IfcStair, IfcRailing, IfcCurtainWall, IfcFurnishingElement,
     IfcElectricMotor, IfcElectricGenerator, IfcProtectiveDevice,
     IfcFlowFitting, IfcCableCarrierFitting, IfcJunctionBox,
     IfcFlowStorageDevice, IfcElectricFlowStorageDevice, IfcOutlet,
     IfcElectricAppliance, IfcAudioVisualAppliance, IfcPort,
     IfcDistributionPort, IfcGroup, IfcSystem, IfcDistributionSystem, IfcZone,
     IfcDoorType, IfcWindowType, IfcRelNests, IfcRelVoidsElement,
     IfcRelFillsElement, IfcRelConnectsPorts, IfcRelConnectsPortToElement,
     IfcRelAssigns, IfcRelAssignsToGroup — plus the three TRUE intermediate
     supertypes the old table had flattened away (IfcNamedUnit over
     IfcSIUnit / IfcConversionBasedUnit, IfcQuantitySet over
     IfcElementQuantity, IfcPropertyAbstraction over IfcProperty) so every
     row's parent is the real IFC4 supertype and the union tree has exactly
     one parent per class.
3. **Tests** (`tests/test_steplite.py` +7, `tests/fixtures_ifc_foreign.py`
   new hand-authored fixture, 4.6 KB of STEP, ids deliberately non-ascending):
   * always (no ifcopenshell): pinned `by_type('IfcProduct')` (26 ids) and
     `IfcElement` (20) lists incl. four classes with NO row (IfcSensor,
     IfcSanitaryTerminal, IfcChimney, IfcRamp); closures at every level;
     served prefix / raising leaf attributes / inverse / by_guid on
     untranscribed classes; every new row's own attributes; a `python -S`
     child proving it on a bare interpreter; `_SCHEMA` parents == the
     generated table for every row;
   * with ifcopenshell: the programmatic cross-check — every `_SCHEMA` row's
     supertype and FULL attribute list == `schema_by_name("IFC4")`
     declarations (196 rows checked; documented allowances: the two
     `IfcCartesianPointList*` rows carry IFC4x1's trailing OPTIONAL
     `TagList`, `IfcTriangulatedIrregularNetwork` is IFC4x1-only), sibling
     order == `subtypes()` order for every parent, generator `--check`
     clean, and full parity on the fixture (by_type at 30 class levels,
     300+ attribute comparisons, inverses, psets, types).

## Evidence

Cross-check pasted from the session (the same loop the test runs):
`checked 197 rows, 2 mismatches` before allowances → the 2 are the
pre-existing deliberate `TagList` extensions; **0 mismatches on every row
added or re-parented here**.

`frontdoor author --ifc usecases/chicago-plenum-electrical-room/generated.ifc --out <tmp> --json`
(the use case carries an `IfcDoor` D-E101 + `IfcDoorType` +
`IfcRelVoidsElement` / `IfcRelFillsElement`):

| | ifcopenshell 0.8.5 | `RVT_STEPLITE_FORCE=1` (steplite) |
|---|---|---|
| before (`main@950d4b6`) — MANIFEST equipment | **18**: proxy×2, wall×3, transformer×3, distribution_panelboard×3, receptacle_panelboard×3, support×4 | **17**: proxy×1 (IfcDoor dropped), rest identical |
| before — `intent.json` bytes | 142 633 | 132 878 |
| after (this branch) — MANIFEST equipment | **18** (unchanged; `cmp` of intent.json before/after: identical) | **18**: proxy×2, wall×3, transformer×3, distribution_panelboard×3, receptacle_panelboard×3, support×4 |
| after — `intent.json` bytes | 142 633 | 142 633 — **byte-identical to the ifcopenshell one modulo `source.path`** (`diff` of the two documents with `source.path` removed: empty) |
| after — delivered `generated.rvt` | `rvt_validate` ok, **0 errors** (1 known DataStorage decoder-gap warning) | `rvt_validate` ok, **0 errors** (same warning) |
| exit / status | 0 / `PROOF-ONLY (self-checks PASS …)` — delivered, stamped | 0 / same |

## Conformance fixture `d_wall_opening_door` (#324)

PR #324 (eng #154) pinned that fixture's parity leg as `xfail(strict=True)`
citing #155 (IfcDoor dropped by steplite).  #324 merged (`main@efcf81c`)
while this branch was in flight; rebased onto it, the conformance module
showed exactly the previewed shape — `d_wall_opening_door` off its pin and
its parity leg `XPASS(strict)`, every other fixture on its pin, #159's xfail
intact.  Flipped DELIBERATELY on this branch: `parity_xfail` removed and the
#155 note rewritten to the landed fact in `tools/dev/make_ifc_fixtures.py`,
then `RVT_STEPLITE_FORCE=1 … make_ifc_fixtures.py --update-expected` →
`expected: 1 re-pinned ['d_wall_opening_door']`.  The one expectation change,
explained: door `D-1` now appears (a) in `equipment` as a recorded `proxy`
(`ifcClass IfcDoor`, `has_body true`, insertion `[3.45, 2.0, 0.0]`, dims
`0.9 × 0.05 × 2.1`, level L1, `position_source placement-chain + local
geometry`) and (b) in `family_plans` as `proxy / unmapped` — byte-for-byte
what real ifcopenshell already produced for this fixture, which is why the
parity leg now passes instead of xfailing.  Nothing else in any
`.expected.json` moved; `make_ifc_fixtures.py --check` → `ok: 9 fixtures`.
After the flip: `tests/test_ifc_conformance.py` WITH ifcopenshell **28 passed
/ 1 xfailed** (#159 only); WITHOUT **20 passed / 9 skipped** (parity legs skip
by design).

## Findings

* ifcopenshell's `by_type` sibling order is `entity.subtypes()` order =
  case-SENSITIVE CamelCase, while its `schema.declarations()` list is
  case-INsensitive; the old comment ("alphabetical CamelCase") was right by
  construction, the distinction only becomes observable with
  `IfcCShapeProfileDef` / `IfcRelConnectsPortToElement` in the tree.
* ifcopenshell keeps instances per class in FILE order for both `by_type`
  and inverse attributes (`ContainedInStructure`, `IsDefinedBy`);
  `get_inverse` is set-like.  steplite now matches the first two and keeps
  its documented id-ascending `get_inverse`.
* Per-schema hierarchies remain out of scope: an IFC2X3-only class
  (`IfcElectricDistributionPoint`, #159) or IFC4X3's renamed supertypes
  (`IfcBuiltElement`, `IfcFacility`) are read through the IFC4 tables — an
  IFC4X3 `IfcWall` still answers `is_a('IfcBuildingElement')` here where
  ifcopenshell would say `IfcBuiltElement`.  The generator takes the schema
  name as a constant, so a per-schema table is a small follow-up if a real
  IFC4X3 input shows up.

## /simplify (4 angles) — applied vs kept

Applied: the `_transcribed_ancestor` helper is gone (the AttributeError now
lists the attribute names that ARE served — more actionable, one tree walk
fewer); `__getattr__` flattened (`attr in attrs`); `_full_attrs` memoised
with `functools.lru_cache` instead of a hand cache; `_TYPED_CAMEL` folded
into `_CAMEL`; `by_guid` asks `is_a("IfcRoot")` instead of probing the
attribute prefix; the "beyond IFC4" allowances live next to the rows as
`_BEYOND_IFC4` data (read by the cross-check) instead of three test
literals; the generator takes `--schema` and derives the module name (the
seam #159 would otherwise have to cut); test boilerplate de-duplicated
(`_run_bare`, `_assert_element_utils_equivalent`, `_assert_attrs_equivalent`
now owns the raises-not-differs rule; a tautological assert fixed; the
PredefinedType table moved into the fixture module).  Efficiency was
measured, not guessed: steplite import +1.0 ms warm / ~+2.5 ms first run and
+250 KiB on the IFC-only path (never on prompt jobs), `is_a` / attribute
access equal or faster, uncached `by_type('IfcProduct')` 7 → 24 µs once per
(file, name) against a 165 ms parse — negligible; the optional trim
(emitting pre-keyed tables from the generator) was not taken.

Kept deliberately (design fork, noted for the tech lead rather than filed):
generating the FULL attribute table for all 776 entities and deleting the
hand rows.  It would remove the two-table seam and the ancestor-prefix
rule, at ~+30 KB shipped; it also changes the module's stated character
("hand-transcribed subset, verified") and rewrites ~200 rows two other
streams touched this week, and the issue's contract names the parent-map +
explicit-rows design.  The always-on test keeps the two tables coherent in
the meantime; if foreign inputs keep needing leaf attributes, that is the
next step and the generator is one `decl.attributes()` loop away from it.

## BRANCH STATE

* Branch `cam/155-steplite-parity` from `origin/main@950d4b6`; PR `Closes #155`.
* Files: `src/rvt/ifc/steplite.py`, `src/rvt/ifc/ifc4_parents.py` (new,
  generated), `tools/dev/gen_ifc4_parents.py` (new, dev-only),
  `tests/fixtures_ifc_foreign.py` (new), `tests/test_steplite.py` (+7 tests,
  helpers consolidated), `docs/writer/dependency-audit.md`,
  `docs/inbox/steplite-parity.md` (this), and the `tools/sync_plugin.py`
  mirrors `plugin/lib/src/rvt/ifc/steplite.py`,
  `plugin/lib/src/rvt/ifc/ifc4_parents.py` (new).  `pyproject.toml`
  untouched (no new runtime dependency).
* Gates on the final diff — WITH ifcopenshell 0.8.5 (`.venv`):
  `tests/test_steplite.py tests/test_ifc_intent.py tests/test_ifc_read_fallback.py
  tests/test_frontdoor.py tests/test_plugin_sync.py tests/test_bootstrap.py
  tests/test_coldstart.py` → **145 passed / 4 skipped** (the 4 = samples-gated
  frontdoor cases); `tests/test_surface_perf.py` 5 skipped (no bare python3
  with numpy on this host — pre-existing).  WITHOUT ifcopenshell (fresh
  `uv venv` + `.[test]` only = CI shape): `tests/test_steplite.py
  tests/test_ifc_read_fallback.py tests/test_frontdoor.py` → **77 passed /
  16 skipped**; `tests/test_ifc_intent.py` alone → 1 skipped (module skips
  by design without the wheel; #320 tracks its collection-order issue).
  `tools/sync_plugin.py` synced the 2 mirrors, `--check` in sync;
  `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok; `tools/dev/gen_ifc4_parents.py
  --check` ok.
* /verify (runtime): the front-door table above on the final head (18 = 18,
  intent.json byte-identical, both `.rvt` validate 0 errors, exit 0, stamped
  PROOF-ONLY and delivered); plus the PRODUCT path — `tekton-plugin.zip`
  rebuilt, unzipped to a temp dir, `env -i … python skills/tekton-author/scripts/_bootstrap.py
  go author --ifc generated.ifc --out out/j1 --json` with a numpy-only
  interpreter (no ifcopenshell → the SHIPPED steplite + ifc4_parents):
  `tekton: READY … 0.026s`, exit 0, `equipment (18)` incl. the door,
  `created: 0 walls, 9 equipment instances, 9 loaded families`, delivered
  `in.rvt` → `rvt_validate` ok / 0 errors.  (With `python3 -S` = no numpy the
  same job exits 3 `FAILED (numpy is required here …)` with the manifest still
  written — the documented numpy floor of the intent route, unchanged.)
* Rebased onto `origin/main@efcf81c` (= merged #324); the `d_wall_opening_door`
  flip is ON this branch (see the section above): files
  `tools/dev/make_ifc_fixtures.py` (registry note + `parity_xfail` only) and
  `tests/ifc_conformance/d_wall_opening_door.expected.json` (re-pinned).
  `tests/test_ifc_conformance.py`: 28 passed / 1 xfailed with the wheel,
  20 passed / 9 skipped without.
* Staged vs shipped: nothing staged for the viewer (no certification claim);
  the reader change ships in the plugin mirrors.

---

## eng #337 — 2026-08-10: the class tree is chosen per FILE_SCHEMA (IFC4X3)

**Charter (issue #337's DONE):** an IFC4X3 file's `IfcWall` answers
`is_a('IfcBuiltElement')` / `by_type('IfcBuiltElement')` as ifcopenshell does;
per-schema parent table generated by `gen_ifc4_parents.py --schema
IFC4X3_ADD2`; steplite selects the table from the parsed `FILE_SCHEMA`
(IFC4X3* → the 4x3 table, else IFC4); IFC2X3 / IFC4 files keep today's
answers; a hand-written IFC4X3 fixture with pinned ids, equal to
ifcopenshell's when importable; dependency audit updated; import cost
recorded.  This section is written by the eng #337 session; the text above
is #155's and untouched.

### What landed

1. **`src/rvt/ifc/ifc4x3_add2_parents.py`** (new, GENERATED, our own text):
   876 `"IfcChild": "IfcParent"` rows, `SCHEMA = "IFC4X3_ADD2"`, imports
   nothing.  **Exactly what the generator reads:** `tools/dev/gen_ifc4_parents.py
   --schema IFC4X3_ADD2` calls `ifcopenshell.ifcopenshell_wrapper.schema_by_name("IFC4X3_ADD2")`
   on the locally installed ifcopenshell 0.8.5 wheel (the EXPRESS schema is
   compiled into the wheel — no network access, nothing fetched at test or
   import time), iterates `schema.declarations()`, keeps the `entity`
   declarations only, and for each takes two identifiers: `entity.name()` and
   `entity.supertype().name()` (or `None` for a root).  **The output is
   names / parent-names only** — no attribute lists, no type / select / enum
   declarations, no WHERE rules, no documentation strings, no bytes of any
   vendor *file*; `git grep -c "': " src/rvt/ifc/ifc4x3_add2_parents.py` = 876
   dict rows and nothing else but the provenance docstring.  The generator
   change itself is docstring-level (`{built}` so the 4x3 module's example
   sentence says IfcBuiltElement; `--check` on the IFC4 module still prints
   `ok: … matches the IFC4 declarations`, i.e. `ifc4_parents.py` is
   byte-unchanged).
2. **`src/rvt/ifc/steplite.py` — one `_Tree` per schema version instead of one
   module-global tree.**  `_Tree(generated PARENT, rows)` builds what used to
   be the module globals (`camel`, `parent`, `children`, memoised
   `full_attrs`, `camel_of`); `_TREE_SPECS = {"IFC4": (ifc4_parents, {},
   _BEYOND_IFC4), "IFC4X3": (ifc4x3_add2_parents, _SCHEMA_IFC4X3,
   _BEYOND_IFC4X3)}`; `_tree_for(identifier)` maps the FILE_SCHEMA identifier
   to its general version with the same rule ifcopenshell uses (`IFC4X3_ADD2`
   / `ifc4x3_tc1` → `IFC4X3`) and builds that version's tree on first use
   (`importlib`), falling back to IFC4's for any version without a spec
   (IFC2X3 — #159 —, IFC4X1, IFC4X2, garbage).  `File._tree` is set from the
   header before the DATA records are read; `Entity.is_a` / `__getattr__` and
   `File.by_type` consult the file's tree; `File.schema` now returns the
   general version (`IFC4X3`) and `File.schema_identifier` the full upper-cased
   identifier (`IFC4X3_ADD2`), exactly ifcopenshell's pair (was: the raw
   string for both — identical for every IFC4 input, so no IFC4 output moved).
   **Placement rule inside a tree:** the generated table places every class it
   declares (it *is* the schema fact); a row's own parent slot only places a
   class the table lacks (the deliberate beyond-schema rows:
   `IfcTriangulatedIrregularNetwork` for IFC4, `IfcPresentationStyleAssignment`
   for IFC4X3).  For IFC4 that is observationally identical to before (every
   row's parent already equalled the table's — tested since #155).
3. **The IFC4X3 row delta `_SCHEMA_IFC4X3` (8 entries, same row shape) —
   "attribute renames hoisted per schema":** drop `IfcBuildingElement` /
   `IfcBuildingElementType` (renamed), add `IfcBuiltElement` /
   `IfcBuiltElementType` / `IfcFacility` (so every transcribed class's
   supertype is transcribed in this tree too), replace `IfcProperty` (`Name,
   Specification` — Description renamed, same position), `IfcObjectPlacement`
   (`PlacementRelTo`, hoisted) and `IfcLocalPlacement` (`RelativePlacement`
   only; its full list is unchanged, `IfcGridPlacement` gains the hoisted slot
   automatically).  `_BEYOND_IFC4X3 = {IfcPresentationStyleAssignment: None}`
   keeps that IFC4-deprecated / 4.3-deleted class readable for writers that
   only bump the schema string.  The issue allowed leaving attribute
   differences for later and listing them; they were small enough to close
   here, and leaving them would have made `.Specification` raise and
   `IfcGridPlacement` mis-map on real 4x3 files while the class tree claimed
   parity — so the record lists them as *done*, not deferred.
4. **Tests** (`tests/test_steplite.py`: 22 → 29 collected; new hand-authored
   `tests/fixtures_ifc4x3.py`, 3.0 KB of our own STEP text,
   `FILE_SCHEMA(('IFC4X3_ADD2'))`, ids deliberately non-ascending):
   * always-on (no ifcopenshell): pinned `by_type('IfcProduct')` (12 ids in
     ifcopenshell's IFC4X3 DFS order — IfcBuiltElement subtypes first, then
     `IfcDistributionBoard` < `IfcElectricDistributionBoard`, then storey,
     `IfcFacility` → building, site), `by_type('IfcBuiltElement')` (6),
     `is_a('IfcFacility')` on the building, `IfcWallType` as
     `IfcBuiltElementType`, two IFC4X3-only classes with NO row (`IfcKerb`,
     `IfcDistributionBoard`: closures + IfcElement prefix served, leaf raises —
     the same helper now checks #155's four IFC4 ones), `.Specification` served
     / `.Description` raises on a 4x3 property, psets with type + occurrence
     override, the hoisted `PlacementRelTo` chain resolving to the right world
     offset; tree selection + `schema`/`schema_identifier` spelling for
     IFC4 / IFC2X3 / IFC4X1 / ifc4x3_add2 / IFC4X3_TC1 / IFC4X3 (an IFC4X3
     wall is an IfcBuiltElement, every other wall an IfcBuildingElement);
     per-tree invariants (rows ⊂ generated table ∪ beyond, every transcribed
     class's tree parent transcribed, delta rows name their true supertype,
     drops gone from the 4x3 tree only); a `python -S` child proving an IFC4
     file never imports the 4x3 table and a 4x3 file reads on the stdlib alone;
   * with ifcopenshell: the declaration cross-check now runs per tree
     (supertype + FULL attribute list of every row, sibling order ==
     `subtypes()` for every parent, no undeclared sibling except a beyond
     row), `gen_ifc4_parents.py --schema … --check` for both tables, and full
     parity on the 4x3 fixture (by_type at 27 class levels, 250+ attribute
     comparisons with raises-not-differs for the two row-less classes,
     inverses, psets, types, placements).

### Evidence — the parity numbers

The record's cross-check (every `_SCHEMA` row's supertype + full attribute
list vs `schema_by_name("IFC4X3_ADD2")`), re-run on `main@b169376` first:
**`checked 198 rows; 31 differences`** (the issue quoted 28 from an older row
count) = 21 supertype renames (`IfcBuilding → IfcFacility`; 15 ×
`IfcBuildingElement → IfcBuiltElement`; 5 × `IfcBuildingElementType →
IfcBuiltElementType`) + 3 classes absent from IFC4X3 (`IfcBuildingElement`,
`IfcBuildingElementType`, `IfcPresentationStyleAssignment`) + 5 ×
`IfcProperty*.Description → Specification` + 2 × `PlacementRelTo` hoist
(`IfcObjectPlacement`, `IfcGridPlacement`); plus 35 parents whose sibling
order differed only by IFC4X3-only classes missing from the IFC4 table.
**On this branch, the same loop against each tree's own schema:
`IFC4 rows checked 197 diffs [] order diffs []` and `IFC4X3_ADD2 rows checked
198 diffs [] order diffs []` — 31 → 0, nothing remaining** (the 3 absent
classes are the 2 dropped rows + the 1 declared beyond row, each asserted as
such).  This loop is now `test_schema_rows_match_declarations[IFC4|IFC4X3]`.

Backend agreement on files (ifcopenshell 0.8.5 vs `RVT_STEPLITE_FORCE=1`):

| input | ifcopenshell | steplite |
|---|---|---|
| `tests/fixtures_ifc4x3.py` fixture | `schema IFC4X3 / IFC4X3_ADD2`, wall `is_a('IfcBuiltElement')` True, `by_type('IfcBuildingElement')` *raises* | same pair, True, `[]` (documented: steplite returns `[]` where the library raises for an undeclared name) — every other query in the parity test equal |
| `frontdoor author --ifc usecases/chicago-plenum-electrical-room/generated.ifc` (IFC4) | exit 0, PROOF-ONLY delivered, 18 equipment, `intent.json` 147 159 B | exit 0, same, 18, **byte-identical modulo `source.path`**; both `generated.rvt` validate `error 0 / warning 1 (known DataStorage gap) / info 2` |
| the same file relabelled `FILE_SCHEMA(('IFC4X3_ADD2'))` (a realistic "writer bumped the string" 4x3 input; it carries no IfcPresentationStyleAssignment) | exit 0, `source.schema "IFC4X3"`, 18 equipment | exit 0, **byte-identical to the ifcopenshell one modulo path**; vs the IFC4 run only `description` (file name) and `schema` differ; both `.rvt` validate 0 errors |

Cost (electrical-room reference IFC, 577 entities, medians of 15–21 child
processes, this VM): steplite-only import **7.94 / 8.10 ms on main vs 8.18 /
8.06 ms here — unchanged within noise**; import memory +31 KiB (the `_Tree`
class + delta dicts); **the IFC4X3 tree costs +0.96 ms and +291 KiB the first
time an IFC4X3 file is opened in a process, never otherwise** (asserted by the
`-S` test); `is_a(name)` × 577: 0.18–0.19 ms → 0.20–0.24 ms (one extra
attribute hop, ~50 ns/call); named-attribute access, uncached
`by_type('IfcProduct')` (25–26 µs) and parse time (≈ 200 ms) unchanged.

### /simplify (4 angles) — applied vs kept

Applied: the IFC4X3 branch in `_tree_for` became the declarative
`_TREE_SPECS` registry + one build path (altitude: #159 is now one registry
row + `--schema IFC2X3` + its delta, and the identifier is parsed by ONE rule
shared with `File.schema` instead of a regex here and a `startswith` there);
`_Tree` lost the test-only `name` / `beyond` slots (tests take beyond/delta/module
from `_TREE_SPECS`); `TypedValue.is_a()` no longer reaches into a class tree
(`_TYPED_CAMEL` + the title-case guess directly — typed values are simple
types); the delta merge is one dict comprehension; tests: `import importlib`
at top, a shared `_write_min_step` (also used by the string-decoding test), a
shared `_assert_untranscribed_elements` for #155's and #337's row-less
classes (fixture dict shapes aligned), redundant identity/facility asserts
removed.  Measured, not guessed: see the cost paragraph; the reviewers'
"cache the tree on the Entity" idea costs 8 B × entities for ~50 ns and was
not taken.

Kept deliberately (noted for the tech lead, not filed): (a) dropping the
parent slot from the ~200 `_SCHEMA` rows now that the generated table places
declared classes — it would rewrite every row two other streams touched this
week for no behavioural change; the always-on test keeps row parents truthful
meanwhile; (b) `write_fixture` is the same 4-line helper in three
`tests/fixtures_ifc_*.py` modules — sharing it means editing two fixture
modules outside this territory for four lines; (c) the generator's `{built}`
docstring parameter instead of a schema-neutral sentence, because the neutral
sentence would re-generate `ifc4_parents.py` (docstring bytes) outside the
issue's territory.

### Follow-ups

* #159 (IFC2X3) inherits the seam: `gen_ifc4_parents.py --schema IFC2X3` →
  `ifc2x3_parents.py`, a `_SCHEMA_IFC2X3` delta for the rows whose positional
  attributes differ, one `_TREE_SPECS` row; commented on #159.
* No new issue filed: nothing found that is not already #159's.

### BRANCH STATE

* Branch `cam/337-steplite-ifc4x3` from `origin/main@b169376`; PR `Closes #337`.
* Files: `src/rvt/ifc/steplite.py`, `src/rvt/ifc/ifc4x3_add2_parents.py`
  (new, generated), `tools/dev/gen_ifc4_parents.py`, `tests/test_steplite.py`,
  `tests/fixtures_ifc4x3.py` (new), `docs/writer/dependency-audit.md` (§3
  paragraph; the "still out of scope" line now names IFC2X3 only),
  `docs/inbox/steplite-parity.md` (this section), and the `tools/sync_plugin.py`
  mirrors `plugin/lib/src/rvt/ifc/steplite.py`,
  `plugin/lib/src/rvt/ifc/ifc4x3_add2_parents.py` (new).  `pyproject.toml`
  untouched; no new runtime dependency; no CI-shard drop-in needed
  (`tests/test_steplite.py` is already in `tests/ci_shard.txt`; the fixture
  module is not a test file).
* Gates on the final diff — WITH ifcopenshell 0.8.5: `tests/test_steplite.py`
  **29 passed**; `tests/test_ifc_read_fallback.py tests/test_ifc_conformance.py
  tests/test_ifc_census.py tests/test_ifc_intent.py tests/test_ifc_intent_units.py
  tests/test_lazy_ifc_import.py` **83 passed / 1 xfailed** (#159's pin).
  WITHOUT ifcopenshell (wheel uninstalled = CI shape): `tests/test_steplite.py`
  **15 passed / 14 skipped**; with the three neighbours **53 passed / 26
  skipped**.  `tools/sync_plugin.py` synced 2 mirrors, `--check` in sync
  (deny-audit clean, identity scan == allowlist); `plugin/scripts/validate_plugin.py`
  PASS (25 assertions); `tools/dev/check_portable_paths.py` ok;
  `gen_ifc4_parents.py --check` ok for both schemas.
* /verify (runtime): the table above (front door under both backends on the
  IFC4 use case and its IFC4X3-relabelled copy: exit 0, PROOF-ONLY delivered,
  18 = 18, intent.json byte-identical modulo path, every `.rvt` validates 0
  errors); plus the PRODUCT path — `tekton-plugin.zip` rebuilt, unzipped to a
  temp dir, a numpy-only interpreter (no ifcopenshell, no repo on `sys.path` →
  the SHIPPED steplite + both generated tables):
  `python skills/tekton-author/scripts/_bootstrap.py go author --ifc <file> --out … --json`
  → `tekton: READY … 0.025s`, exit 0, PROOF-ONLY delivered for both
  `examples/electrical-room-2500a.ifc` (schema IFC4, 12 equipment) and the
  relabelled 4x3 room (schema IFC4X3, 18 equipment), both `.rvt` validate
  `error 0`.  With plain `python3` (no numpy) the same job is `READY` at
  preflight and exits 3 `FAILED (numpy is required here …)` with the manifest
  written — the documented numpy floor of the intent route, unchanged.
* Staged vs shipped: nothing staged for the viewer (no certification claim);
  the reader change ships in the plugin mirrors.
