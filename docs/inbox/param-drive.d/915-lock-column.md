# 915 — the Family Types "Lock" column follows the segment lock bits

Stream: **param-drive** (fragment; index `../param-drive.md`). Issue **#915**, from
steer #913's corpus work. The owner's Family Types screenshot of the #900 trapeze
showed Lock ticked on every length parameter.

## What the corpus showed (counts only, #915)

`Family.m_lockedParameterIdsForDirectManipulation` is empty in 279 of 421 born
families. For parameters that label dimensions, membership matches the segment lock
bit (`m_ArrSegInfo[k].m_flags & 1`) exactly:

| | In the list | Not in the list |
|---|---|---|
| Lock bit set | 262 | 0 |
| Lock bit clear | 0 | 1,994 |

## What was built

- **`skeleton.labelled_lock_state(doc)`** maps each parameter to whether any of its
  labelled segments is locked, across every dimension class carrying `m_ArrSegInfo`
  (linear and radial).
- **`skeleton.sync_locked_params(doc)`** sets the list to exactly the parameters
  with a locked labelled segment. An entry that labels no dimension at all, such as
  the catchain residue's cost built-in, is left as it is.
- **`finalize`** calls it, replacing the old "[INFERRED default]" that listed every
  length parameter.
- **`drive_law.apply_born_inplane_law`** calls it again after it clears the labelled
  segments' flags.

## Evidence

- **Archetypes:** every one now carries `[]`, the born majority. This covers the
  trapeze, cable tray, wireway, junction box, strut channel, lighting control panel
  and conduit.
- **`tests/test_lock_column_915.py`** (10 tests):
  - the list agrees with the lock bits on 7 archetypes;
  - plain length parameters are not listed;
  - setting a segment's lock bit adds its parameter, and clearing the bit removes it;
  - an entry that labels no dimension is kept.
- **Every generated family's bytes change** wherever the list used to be non-empty.
  The gates below are the check.

## Open

- **DONE item 2, the `ParamElemFamily` header flag** (ours 8218, born 8202 in 14,244
  of 14,265) is recorded here and **not changed**. No test yet shows what depends on
  bit 0x10, so it stays until one does.
- **No desktop verdict.** The Lock column is a dialog display. Its Revit check comes
  from the owner's ordinary use, since steer #913 says no probe families go to them.

## Also in this PR: spec arguments that are not lists (#929 review nit)

`make_generic_model(drives=5)`, `heights=5` and `diameters=5` used to raise
`TypeError` out of the factory and withhold the file. That contract predates the
param-drive stream. `factory._spec_list` now coerces a single spec, string or
number into a one-item list and a generator into a list. A malformed argument
therefore becomes a reported "not wired" note and the family is delivered (hard
rule 1). Pinned by `tests/test_spec_lists_929.py` (25 tests). Lists and tuples pass
through unchanged, so no existing output changes.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/skeleton.py`: `labelled_lock_state` and `sync_locked_params`, now
  called from `finalize`.
- `src/rvt/famgen/drive_law.py`: re-syncs after the born law.
- `plugin/lib/…`: mirrors.
- `tests/test_lock_column_915.py`, `tests/ci_shard.d/915-lock-column.txt`: new.
- `src/rvt/famgen/factory.py`: `_spec_list`; `tests/test_spec_lists_929.py` and its
  shard drop-in.
- `tests/test_famgen_skeleton.py`: the old "length params are locked" pin is
  replaced.
- This fragment.

**Gates:** see the PR.

**Shipped vs staged:** shipped. Nothing is staged.
