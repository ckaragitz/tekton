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

PR #324 (eng #154) pins that fixture's parity leg as `xfail(strict=True)`
citing #155 (IfcDoor dropped by steplite).  With this branch steplite keeps
the door, so that strict xfail must flip.  #324 had not merged when this
branch was cut (`origin/main@950d4b6`); the flip (remove the xfail flag,
re-pin `d_wall_opening_door.expected.json` via
`tools/dev/make_ifc_fixtures.py --update-expected`, one expectation change:
the door appears as a recorded `proxy` product exactly as under
ifcopenshell) is done on this branch after rebasing onto the merged #324 —
see BRANCH STATE for whether that has happened at the head you are reading.

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
* Pending at this head: the `d_wall_opening_door` xfail flip + re-pin waits
  for #324 to merge (previewed in a scratch worktree: with this steplite over
  #324's head, exactly that fixture moves — door `D-1` appears as recorded
  `proxy` equipment + one `family_plans` entry — its parity leg XPASSes
  strictly, every other fixture stays on its pin, #159's xfail stays).  After
  the merge: rebase, drop the `parity_xfail` + the #155 note in
  `tools/dev/make_ifc_fixtures.py`, `--update-expected`, re-run
  `tests/test_ifc_conformance.py`, push, report the new head.
* Staged vs shipped: nothing staged for the viewer (no certification claim);
  the reader change ships in the plugin mirrors.
