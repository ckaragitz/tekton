# #975: four edge cases in `pset_params.collect` left by #974's review

Stream: param-drive. Issue #975. Base `main` 0c93e62.

## What changed (`src/rvt/ifc/pset_params.py`)
1. **An unreadable value still names its product.** Before this fix, a statement like
   `IFCLENGTHMEASURE('abc')` was dropped completely, along with its owners.
   - Example: `tank_shell` with BodyWidth 1574.8 and `pad_slab` with BodyWidth 'abc'.
     The plan drove `tank_shell` alone. Before #974 it was value-only, "attached to 2
     products".
   - Fix: #967's invariant is back. Every product the label is attached to is
     recorded, whether or not the values are equal.
   - Order-free. If the unreadable statement comes first, its owners wait in a
     per-label `pending` map. They merge when a readable value from an attached pset
     is carried, either as a fresh entry or as an occurrence replacing an unattached
     value.
   - An unreadable value never becomes a parameter. A label whose only value is
     unreadable stays absent from `params` and `sources`.
2. **A plain number and a length of one value carry the length.** Before this fix,
   `IFCREAL(1574.8)` followed by `IFCLENGTHMEASURE(1574.8)` kept the kind `number`,
   so the label was value-only. The reverse order drove.
   - Fix: `_upgrade_kind` changes the kind to `length` when the two are the same
     statement (`_same_statement`). It also updates `params` and the source's
     `ifc_type` and `raw_value`.
   - Applies to attached repeats and to unattached-vs-unattached repeats.
3. **No skip row is left claiming something false.**
   - Two unattached values: the row now reads "unattached value X not carried; it
     differs from the first unattached value Y (pset)". It no longer says "is kept".
   - Those rows are tracked per label. When an occurrence value later replaces the
     unattached one, each row is reworded to "...; the occurrence value Z (product)
     wins".
   - A row whose value equals the occurrence value is removed, because that value
     is carried.
4. **Record correction.** `973-pset-override.md` now has a dated "Correction (#975)"
   section. It fixes the stale quote "type-level value X overridden by the occurrence
   value Y" and the two incomplete bullets. The original text is left as merged.

Refactor: `_merge_owners()` replaces the inline owner-merge loop, and `_unzip()` was
added.

## Evidence
- `tests/test_pset_edges_975.py`: 5 tests, at least one per case (case 4 is the
  record correction).
  - With `0c93e62`'s module swapped in: **5 failed**. With the fix: **5 passed**.
  - Tests:
    - `test_an_unreadable_value_after_still_counts_its_product`
    - `..._before_...` (also checks a lone unreadable label stays absent)
    - `test_a_real_then_a_length_of_one_value_still_drives`
    - `test_two_unattached_rows_stay_true_when_an_occurrence_wins` (file order
      unattached 1500, unattached 1600, occurrence 1574.8)
    - `test_an_unattached_repeat_equal_to_the_occurrence_is_no_skip`
- No existing test was re-pinned. The new wording keeps the substring "first
  unattached value", so `test_two_unattached_values_keep_the_first_and_say_so`
  passes unchanged.
- Results:

  | Run | Result |
  |---|---|
  | `test_pset_edges_975` + `test_pset_override_973` + `test_review_nits_967_970` + `test_pset_drive_714` | 48 passed. The #714 fixture's 7 drives are unchanged. |
  | `test_ifc_assembly*.py` + `test_router*.py` (`RVT_SKIP_LARGE=1`) | 339 passed, 12 skipped |
  | `test_plugin_sync.py` | 9 passed |
  | `tools/sync_plugin.py --check` | clean |
  | `validate_plugin.py` | PASS |
  | `check_portable_paths.py` | ok |

## Open questions
- Suppose the only readable value is unattached and an unreadable value sits on a
  product. The owners stay pending and the row says "attached to no product". This
  is honest because no readable statement ties the value to that product. It is
  still a judgement call, recorded here.

## BRANCH STATE
- Files:
  - `src/rvt/ifc/pset_params.py` (+ the `plugin/lib` mirror via `sync_plugin.py`)
  - `tests/test_pset_edges_975.py` (new)
  - `tests/ci_shard.d/975-pset-edges.txt` (new)
  - this fragment
  - the appended correction in `973-pset-override.md`
- Committed locally on `fix-975`. Not pushed, nothing staged for the viewer, and no
  Revit claim (hard rule 4).
