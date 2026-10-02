# #979: three gaps in `pset_params.collect` left by #978's review

Stream: param-drive. Issue #979. Base `main` 18153b4.

## What changed (`src/rvt/ifc/pset_params.py`)
1. **A text value that reads as the same number yields to the number or length.**
   Before: `IFCLABEL('1574.8')` then `IFCLENGTHMEASURE(1574.8)` on one product kept
   kind `text`, so the label was value-only; the reverse order drove.
   - `_same_statement` already treated the two as one statement. `_upgrade_kind` now
     ranks the kinds `text < number < length` and upgrades to the higher one.
   - A text value upgrades only when `float(text)` parses and `_same_value` says it is
     the same raw number. A label like `'wide'` never upgrades. Neither does `'12'`
     against 13; that pair is still recorded as a conflict.
   - Also covers `text -> number` (`IFCLABEL('0.5')` then `IFCREAL(0.5)`). The issue
     only named `text -> length`, but without this a label-then-real pair kept the
     kind `text` while real-then-label kept `number`: the same order dependence.
2. **An unreadable value always gets its `skipped` row**, one per occurrence,
   including when it comes first. Before, the row was written only `if label in
   seen_names`. Since #975 its product is counted as an owner, so the plan could say
   "attached to 2 products (…, pad_slab)" with nothing explaining pad_slab's value.
   - A label whose only value is unreadable still never becomes a parameter. It now
     has a row saying the value was dropped.
3. **Repeat-row removal uses `_same_statement`.** `unattached_rows` now keeps each
   row's typed value. When an occurrence value replaces the unattached one, a row is
   removed if `_same_statement` says it is the same statement. That is lengths at
   1e-6 ft, the test the first-unattached comparison already used. Before, it was raw
   `_same_value` at 1e-9 relative.

## Evidence
- `tests/test_pset_last_979.py`: 6 tests.
  - With base `18153b4`'s module swapped in: **5 failed, 1 passed**. The passing one is
    the guard `test_a_label_of_another_or_no_number_never_upgrades`, which passes on
    both by design.
  - With the fix: **6 passed**.
  - Tests per case:
    - Case 1: `test_a_label_then_a_length_of_one_value_still_drives`,
      `..._label_then_a_real_..._carries_the_number`, plus the guard.
    - Case 2: `test_an_unreadable_value_first_still_has_its_row` (plan stays
      value-only, "attached to 2 products"),
      `test_two_unreadable_values_have_one_row_each`.
    - Case 3: `test_an_unattached_repeat_within_drive_tolerance_is_no_skip`. File
      order: unattached 1500, unattached 1574.8001 (3.3e-7 ft away), occurrence
      1574.8.
- **Ordering probe** (scratch, not committed). The #714 fixture with BodyWidth taken
  out of `Pset_Body`. BodyWidth is then stated only by these events:
  - length 1574.8 on tank_shell
  - label '1574.8' on tank_shell
  - real 1574.8 on tank_shell
  - unreadable 'abc' on pad_slab
  - unattached length 1500

  Every ordering of every 1–4 event subset was run: **205 orderings (30 event
  sets), 0 exceptions** at base and at head.

  | Measure | Base | Head |
  |---|---|---|
  | DRIVES lost vs base | — | 0 |
  | DRIVES gained vs base | — | 14 (every one a label-before-length ordering: the intended fix) |
  | Event sets whose (status, kind) depends on file order | 11 | 0 |
  | Orderings with the unreadable event but no unreadable row | 41 | 0 |
- Gates:

  | Run | Result |
  |---|---|
  | `test_pset_last_979` + `test_pset_edges_975` + `test_pset_override_973` + `test_review_nits_967_970` + `test_pset_drive_714` | 54 passed (48 existing, unchanged; the #714 fixture's 7 drives unchanged) |
  | `test_ifc_assembly*.py` + `test_router*.py` (`RVT_SKIP_LARGE=1`) | 339 passed, 12 skipped |
  | `test_plugin_sync.py` | 9 passed |
  | `tools/sync_plugin.py`, then `--check` | clean |
  | `validate_plugin.py` | PASS |
  | `check_portable_paths.py` | ok |

## Open questions
- None new. #975's judgement call still stands: when the only readable value is
  unattached, an unreadable value's owners stay pending.

## BRANCH STATE
- Files:
  - `src/rvt/ifc/pset_params.py` (+ the `plugin/lib` mirror via `sync_plugin.py`)
  - `tests/test_pset_last_979.py` (new)
  - `tests/ci_shard.d/979-pset-last.txt` (new)
  - this fragment
- Committed locally on `fix-979`. Not pushed, nothing staged for the viewer, and no
  Revit claim (hard rule 4).
