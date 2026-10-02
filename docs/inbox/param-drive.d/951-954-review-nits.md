# Review nits from #951 and #954

Branch `review-nits`, based on `main` 3e03fd3 (shipped rebased onto 7d2fcde). Five small fixes left as
optional review nits on the merged PRs #951 (#947, the reference index) and
#954 (#948, the hexagon drive).

## What changed

1. **One source for "Not a Reference".** `src/rvt/famload.py`
   `_reference_idx_mgr` compared `m_refName == 12` against a bare literal. It
   now uses `rvt.famgen.loader.NOT_A_REFERENCE`, imported locally because the
   loader already imports famload locally. `loader` asserts this constant
   equals `skeleton.REF_NAME["not_a_reference"]` (the existing #947 test).
2. **#947 record corrected.** The record said the generic model has origin
   codes `[1, 4]`. A `make_generic_model(width_ft, depth_ft, height_ft)`
   build carries `[1, 4, 12]`. `height_ft` is mandatory, so no generic model
   lacks the Case B plane. Its load also changes by -79 inflated bytes in one
   partition on 2026, 2025 and 2024. That was measured pre-fix vs post-fix
   predicate on the same input, with file sizes unchanged. The wireway's
   `[1, 4]` stands. The correction is a dated block under the original
   sentence, which is kept and marked amended.
3. **A missing origin centre plane is a refusal, not a crash.**
   `angular_law.wire_hexagon_drive` re-raises `drive_law.origin_centre_plane`'s
   `ValueError` as `AngularLawError`, as `hexagon_roles` already does for
   `_sketch_lines`. The lookup sits before the first mutation, so the
   all-or-nothing contract holds. `trapeze_nested.make_hex_nut` therefore
   takes its documented fallback: the nut is delivered and the note reads
   "Nut Across Flats carries a VALUE ONLY …" (hard rule 1).
4. **The nest gate judges errors only, on every unit.**
   `nest.verify_nested` used to fail a nest on any constraint-law finding,
   warnings included, and judged unit 0 only. It now:
   - runs `check_file` on unit 0 and on every unit `nested_units` names;
   - fails only on `severity == "error"`, the same filter as
     `tools/self_battery.py`;
   - records the per-unit results as `constraint_law_nested`
     (`{guid: findings}`), plus `constraint_law_errors` (a count) and
     `constraint_law_warnings` (the warning findings themselves, so they are
     kept, not discarded).
   - `constraint_law` (unit 0's full list) is unchanged, so existing
     assertions still hold.
5. **#948 Census 1 recount.** A dated block in
   `948-angular-eq.md` records counts from a scratch script over the private
   library (421 files; not committed, no specimen named). It finds
   502 dims / 71 files / 156 units / 164 locked 60° (74 host, 428 nested).
   That holds for every enumeration that includes unit 0: all units; unit 0
   plus `unit_by_guid`; the same with GUIDs de-duplicated across the library.
   `unit_by_guid` alone gives 428 / 59 / 136 / 154. No unit shares a GUID.
   None of these enumerations reproduces the original 387 / 62 / 113 / 160.
   The 156 units match the record's own law-run count. The per-field rows
   were not recounted.

## Evidence

- **Nested trapeze bytes, nest gate change.** Built with
  `make_archetype(product="strut_trapeze", nested_hardware=True)`, comparing
  base 3e03fd3 against this branch.
  - 2026: 344,064 B, sha256 `4fc7a4b01e7bdc7281c9d359cd87154acbc2ebd7babaf1cb817ea91ba6080406`.
    Identical before and after.
  - 2025: 339,968 B, sha256 `f457c86d2f88e544a3159bd68b1a47d3a1847c6a20786eb56cceecd668bb7981`.
    Identical before and after.
  - Both releases still nest, with no solid fallback: `nested_hardware.ok`
    True. Washer and nut verify `ok`.
  - *Note (review of #957, 2026-10-02):* the two sha256 values above were
    measured on base 3e03fd3. Rebased onto 7d2fcde (which includes #955) the
    independent reviewer measured 2026 `4502dbfe…558e` and 2025 `5925d7a0…006d`,
    again identical at base and head -- the before/after identity holds; the
    absolute hashes moved with the base.
  - The washer and nut nested units are now judged too. 2026: 1 unit, then
    2 units. 2025: the same. All 0 findings, 0 warnings.
- **New module `tests/test_review_nits_951_954.py`:** 7 tests, about 3 s.
  Run against the base tree (3e03fd3) it fails 6 of 7. The 7th pins the
  record correction (`[1, 4, 12]`), which is a fact about base too. The
  module proves:
  - famload follows the constant (monkeypatched);
  - the missing-plane refusal raises `AngularLawError`;
  - the nut is delivered and written with the VALUE ONLY note, and
    `check_file` reports 0 errors on it;
  - a real nest judges its nested unit clean;
  - an injected warning on both units leaves the nest `ok` with 2 warnings
    recorded;
  - an injected error only in the nested unit fails the nest, and no output
    is left behind.

Nothing here claims Revit behaviour (hard rule 4). No desktop or viewer
verdict was taken.

## BRANCH STATE (`review-nits`)

**Files written**

- `src/rvt/famload.py`, `src/rvt/famgen/angular_law.py`,
  `src/rvt/famgen/nest.py`.
- `plugin/lib/src/rvt/{famload.py,famgen/angular_law.py,famgen/nest.py}`:
  regenerated mirrors.
- `tests/test_review_nits_951_954.py` and
  `tests/ci_shard.d/951-954-review-nits.txt`: new.
- `docs/inbox/param-drive.d/947-refindex.md`: dated correction.
- `docs/inbox/param-drive.d/948-angular-eq.md`: dated recount.
- This record.

**Gates**

- pytest: **198 passed, 17 skipped, 0 failed**, in 190 s, over:
  - `test_review_nits_951_954`, `test_loader_refindex_947`;
  - `test_famload`, `test_famload_2025`, `test_famload_batch`,
    `test_famload_determinism_794`, `test_famload_fix`;
  - `test_angular_eq_948`, `test_trapeze_nested_917`, `test_nest_917`,
    `test_nest_locks_917`, `test_nested_heights_940`, `test_plugin_sync`.

  The skips are gated on `samples/`.
- `tools/sync_plugin.py`, then `--check`: in sync (deny-audit clean,
  identity scan == allowlist, assets verified).
- `plugin/scripts/validate_plugin.py`: PASS.
- `tools/dev/check_portable_paths.py`: ok (3,419 paths).

**Staged / shipped:** nothing is staged for the viewer. Nothing is
certified. Follow-up commit on #957: session CI found
`test_conftest_scaffolding::test_every_module_on_the_leak_guard_enters_a_context`
red -- the new module requests `no_release_leak` but enters a release context
only through `nest_family`, which the call-scan cannot see -- so it now stands on
that test's `ADOPTERS` list saying so; the same commit carries the #957 review
nits (`from exc`, `f["severity"]`, the dated sha note above). Pushed as PR #957 (branch `claude/pull-latest-main-1cmo56`).
