# 904 — the in-plane drive as Revit-born families store it, and one parameter driving several parts

Stream: **param-drive** (fragment; index `../param-drive.md`).
Issues **#787** (DONE 1, the in-plane half) and **#904**. Branch
`claude/pull-latest-main-1cmo56`.

## What was learned

A census of the owner's private reference corpus (#836 / #865) covered 421
families made in Revit. They stay quarantined and git-ignored, and none is named
here. Seven were decoded in full under their own schemas, and the rest were
profiled. The findings are posted on #787; in short:

- **Two of our hypotheses are refuted.**
  - The `FamDimConstrMgr.m_paramExprs` "driver tables" are used corpus-wide only
    for extrusion and blend ends with built-in parameters (1175 + 17 entries).
    They never hold a user parameter and are never keyed on a dimension.
  - `m_constrInfo` back-edges appear on no element in any of the 421 files.
- **The in-plane binding** is the labelled dimension's segment `m_paramId`, plus
  per-line sketch locks.
- **How our chain differed from every born specimen:**
  - sketch-lock owner view −1, against our plan view;
  - `m_dimVersion` 6, against our 1;
  - `m_sideRefPlaneCurveBased` True;
  - curve GInfo bit 0x80000;
  - labelled segment flags 0, with header `regenOnly` = `[UnitsElem]`;
  - the back-edges, which born files never carry;
  - the `VarSketch` regen edge.

## Desktop verdict (owner, 2026-10-01)

`tools/drive_probe.py` built a one-box probe pair:
- **P:** the full law.
- **C:** P minus the sketch regen edge.

Read-back showed they differ in exactly one header field. Test: Width from
2' 0" to 3' 0", Apply. Result: **"both widened"**.

- This is the first generated family in this repo whose parameter drives its
  geometry.
- The regen edge is not necessary.
- P is adopted as the authoring law because it matches the corpus.
- The release was not stated.

## What was built

- **`src/rvt/famgen/drive_law.py`.**
  - `apply_born_inplane_law(doc, regen_edge=True)` rewrites a finalized
    document's in-plane chain to the born law and reports exactly what changed.
  - `wire_linear_drive(doc, caption, axis, lo, hi, targets)` makes one family
    parameter drive two new reference planes and locks the chosen edges of
    **several** parts' rectangular sketches to them.
- **`tools/drive_probe.py`:** stages the single-variable probe pair, by release.
- **`factory`.**
  - `make_generic_model(..., drives=[...])` / `_make_generic_multipart` wire the
    drives before `finalize` and apply the born law after it.
  - `make_archetype` passes `Archetype.drives`.
  - A drive that names no part is noted, never raised (hard rule 1).
- **The trapeze declares a Strut Length drive.**
  - Every tier's webs and lips follow on both ends.
  - A slotted back's first and last segments follow on their outer end.
  - At the defaults: 12 parts, 20 locks, one labelled dimension.
  - The archetype's `limits` say it is **wired, with no verdict for this family
    yet**.

## Evidence

- `Strut_Trapeze_30_in_2_Tier`, built for 2026 and 2025:
  - `rvt_validate` ok; family mode VALID, 0 errors; PROVENANCE-CLEAN.
  - Read-back: 20 alignments, all view −1; 1 labelled dimension; 12 sketches
    carrying locks; 0 `m_constrInfo`; 0 unclean records.
- **Staged for the owner:** change Strut Length from 2' 6" to 3' 6" and Apply.
  Verdict pending.

## Open

- **Rod Spacing.** The rods are circles and the washers and nuts move rigidly, so
  this needs centre-line locks or equality dimensions: a new probe.
- **Tier Spacing.** This is the extrusion end (#787 Case B), so it needs its own
  probe pair.
- **Panelboard Width/Depth with the front parts following.** Its first-solid drive
  should move to `drive_law`.
- **Strut Length leaves the rods where they are.** Rod Inset, as a value, goes
  stale when Strut Length is flexed. A formula (`Rod Inset = (Strut Length − Rod
  Spacing) / 2`) is the natural fix once formulas (#862) have a desktop verdict.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/drive_law.py`: new.
- `tools/drive_probe.py`: new.
- `src/rvt/famgen/factory.py`: `drives` plumbing.
- `src/rvt/famgen/archetypes.py`: `Archetype.drives`, `_trapeze_drives`, and the
  limits text.
- `plugin/lib/…`: mirrors.
- `tests/test_drive_law_904.py`: new, 7 tests.
- `tests/ci_shard.d/904-drive-law.txt`: new.
- this fragment.

**Gates**
- `test_drive_law_904`: 7 passed.
- trapeze, famgen_factory, family_anatomy, param_profile, archetypes, panelboard
  detail, equipment clearance, transformer detail, famgen_adoc, bare family
  validate, route, bootstrap, coldstart and surface_perf suites: 758 passed.
- `test_constraint_law`, `test_famgen_parametric` and `test_plugin_sync`: green.
- Plugin in sync; validate PASS; portable paths ok.

**Shipped vs staged:**
- The one-box probe has a desktop verdict.
- The trapeze's Strut Length drive is shipped wired but unverified; its probe is
  staged for the owner.
