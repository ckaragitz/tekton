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
  - The archetype's `limits` cite the owner's verdict on #904: Strut Length
    drives the strut ends. They also say the rods and hardware do not follow it
    yet.

## Evidence

- `Strut_Trapeze_30_in_2_Tier`, built for 2026 and 2025:
  - `rvt_validate` ok; family mode VALID, 0 errors; PROVENANCE-CLEAN.
  - Read-back: 20 alignments, all view −1; 1 labelled dimension; 12 sketches
    carrying locks; 0 `m_constrInfo`; 0 unclean records.
- **Desktop verdict (owner, 2026-10-01):** *"it changes the lengths but the rest
  of the elements need to be constrained and move with it"*. Strut Length drives
  every tier's strut ends across 12 parts, which is the second desktop pass. The
  hardware does not follow yet (steer #908, next).

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

## Review round 1 (head `f2f8890`, 🛑)

- **The PR body.** It said "does not close #904", and GitHub's linker ignores the
  "not". It is reworded as a Refs-only partial.
- **Back-edges.** A document carrying the law (`doc.born_drive_law`, set when
  drives are wired) gets **no** back-edges from `finalize`. There are no more
  "22 written, then 22 cleared" notes.
- **`wire_linear_drive` refuses planes that disagree with the parameter's
  current value.** In the factory that means it is noted and left unwired, never
  raised. It also passes the view sketch plane as the labelled dimension's regen
  parent, and notes when a document has no `UnitsElem`.
- **The trapeze `limits` now say** that the rods, washers and nuts stay put, and
  that Rod Inset, Rod Spacing and Width no longer describe the geometry after a
  flex.

## Review round 2 (head `534a6ae`, 🛑)

- **A refused drive left half a chain in the delivered file:** 2 RefPlanes and 2
  Alignments in the pre-law form, plus the sketch registration, because the value
  check ran after the first `doc.add`. Now every check runs before the first
  mutation: the value, each target's rectangle and the sides. The test asserts
  that the document equals the no-drive control, class by class.
- **`doc.born_drive_law`** is set only when at least one drive actually wired.
- **The verdict's head.** The owner's trapeze verdict was on `f2f8890`. Since
  then exactly one field differs in the trapeze: the labelled dimension's header
  `m_appearanceParents` gains the view SketchPlane, matching the verified one-box
  probe. `m_constrInfo` is never written instead of written and then cleared, and
  the file is identical. The archetype's "(owner's desktop verdict)" refers to
  that run.

## Review round 3 (head `0743de7`, 🛑)

- **`wire_linear_drive` refuses, before its first mutation, every drive that
  would build a valid but wrong file:**
  - (i) an edge not on its plane: both ends of each locked edge must sit at the
    plane coordinate;
  - (ii) a rotated quad, which `_classify_rect` accepted;
  - (iii) `lo >= hi`;
  - (iv) a non-finite plane;
  - (v) a parameter that is not a length (`m_specTypeId` must be the length
    spec).

  `targets` is materialised first, because a generator would be spent by the
  checks.
- **The factory refuses** a drive naming a part that is missing or not unique,
  instead of silently dropping the name or driving only the last duplicate.
- **The notes say what the document carries.** "Parameter drives wired: Strut
  Length moves 20 part edge(s) on 12 part(s)" replaces the stale "REPORTED only"
  first-solid note. The law note names the lanes that have verdicts.
- **A comment records** that the law runs after the content-derived GUID is
  sealed (#168) and is deterministic.
- **Text fixes:** the taxonomy note and the limits text are corrected (Rod Spacing
  stays true after a flex; Rod Inset and Width do not).
- **Tests:** one per case, each compared with the no-drive control class by class.
  8 of them fail on the round-2 code.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/drive_law.py`: new.
- `tools/drive_probe.py`: new.
- `src/rvt/famgen/factory.py`: `drives` plumbing.
- `src/rvt/famgen/archetypes.py`: `Archetype.drives`, `_trapeze_drives`, and the
  limits text.
- `plugin/lib/…`: mirrors.
- `tests/test_drive_law_904.py`: new, 18 tests after review round 3.
- `tests/ci_shard.d/904-drive-law.txt`: new.
- this fragment.

**Gates**
- `test_drive_law_904`: 18 passed (8 of them fail on the round-2 code, as intended).
- trapeze, famgen_factory, family_anatomy, param_profile, archetypes, panelboard
  detail, equipment clearance, transformer detail, famgen_adoc, bare family
  validate, route, bootstrap, coldstart and surface_perf suites: 758 passed.
- `test_constraint_law`, `test_famgen_parametric` and `test_plugin_sync`: green.
- Plugin in sync; validate PASS; portable paths ok.

**Shipped vs staged:**
- The one-box probe has a desktop verdict.
- The trapeze's Strut Length drive has its desktop verdict (#904), on `f2f8890`;
  the shipped file differs from that one in one field.
- The "Follow" probe ladder (9 rungs, for the rods and hardware) is staged with
  the owner (#904).
