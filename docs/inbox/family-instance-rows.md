# family-instance-rows: a value row carries its parameter's own instance flag (#859)

Stream record for #859. The bug was found by the #842 profiler review; this session
added corroborating evidence while studying the owner's reference pack for #865.

## What was wrong

`FamilyDoc._type_param_entries` (`src/rvt/famgen/skeleton.py`) called
`family_param_value(pid, v)` without `is_instance`. So every row of the
self-Family's `m_familyParams`, and every type row, said `m_instance: False`,
including the rows of instance parameters (`ParamElemFamily.m_instanceParam`
True). Our generated 45 kVA transformer showed it: `Apparent Load` was an instance
parameter by definition and a type parameter by its row.

Revit-born families say `True` there:
- the rme dumps: all 7 checkable rows agree with their definitions;
- the owner's private reference pack: instance-bound shared parameters carry
  `m_instance` True; counts only.

The loader (`src/rvt/famgen/loader.py`, `author_family_instance`) builds a placed
instance's parameter rows from exactly those rows, so a placed instance got no
instance-parameter row at all.

## Fix

`_type_param_entries` passes each parameter's own flag: the definition's
`m_instanceParam`, or `refs["instance"]` for the shared-parameter path that #866
adds. Nothing else changes.

## Evidence

- New `tests/test_instance_rows_859.py`: **3 passed**; with the fix stashed,
  **3 failed**. It checks:
  - every row agrees with its definition, on every type and the current-type set,
    and the document round-trips;
  - a generated transformer marks its instance parameter;
  - loading and placing the transformer into a project the front door builds gives
    the placed instance its parameter row, pointing at the project's own twin;
    the project validates at 0 errors.
- By hand:
  - the transformer `.rfa` has 0 rows disagreeing with their definitions and
    validates at 0 errors;
  - the placed project has 1 instance row on the placed element (0 on `main`), and
    it resolves to a project element;
  - the project validates at 0 errors, with the same single known-decoder-gap
    warning as `main`.
- `RVT_SKIP_LARGE=1 pytest` over the family, loader, front-door and router suites
  (19 files) gives **782 passed, 58 skipped, 0 failed**.
- `tools/sync_plugin.py --check` clean; mirror byte-identical;
  `validate_plugin.py` PASS; `check_portable_paths.py` ok; bare-unzip product
  tests passed.

## Open (this issue)

- #859 DONE (3): this changes the written bytes of every generated family with an
  instance parameter, so a viewer or desktop batch must be staged (hard rule 4).
  It is not staged in this PR, and no certification is claimed.

## BRANCH STATE

- Branch: `claude/eager-franklin-xgzgda`, from `main` @ `82f2683`.
- Files written:
  - `src/rvt/famgen/skeleton.py` (+ its mirror)
  - `tests/test_instance_rows_859.py`
  - `tests/ci_shard.d/859-instance-rows.txt`
  - this record
- Shipped: the instance flag on value rows.
- Staged, not shipped: nothing.
