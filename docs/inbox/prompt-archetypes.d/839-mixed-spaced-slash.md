# 839 — a mixed number with a spaced slash was split, and its fraction stamped `given`

Stream: **prompt-archetypes** (fragment; index `../prompt-archetypes.md`).
Issue **#839** (P0), branch `cam/839-mixed-spaced-slash`. Found by the
independent reviewer of #835.

## The defect

`_NUM_CORE` accepted spaces around a mixed number's hyphen but not around its
slash. The prompt route split the number at the slash and read the trailing
fraction on its own:

```
main 16074b6:
  "cable tray 24 - 1 / 2 in wide"   -> width_in    = 0.5    given   (24 1/2)
  "a 2 - 1 / 2 in conduit"          -> diameter_in = 0.5    given
  "strut channel 1 - 5 / 8 in tall" -> height_in   = 0.625  given
  "a 2 1 / 2 in conduit"            -> diameter_in = 2.0    given
  "a 2-1 /2 in conduit"             -> dropped (nominal)
```

`_to_number` already read every one of these strings correctly when handed
them whole (#835's unit rows). The regex never handed them over.

## Fix

In `_NUM_CORE`, the mixed-number alternatives accept `\s*/\s*`, both the
space-separated one ("2 1 / 2") and the hyphenated one ("2 - 1 / 2").

## Evidence

| instrument | prompts | `main` wrong | fix wrong | changed vs `main` |
|---|---|---|---|---|
| every hyphen × slash spacing, every inch parameter, both phrasings, noun first/last | 18,000 | 13,500 | **0** | 13,500 better, **0 worse** |
| the #828 corpus (fuzzers + sweeps, no spaced slashes) | 269,361 | — | — | **0 outputs change** |

- `tests/test_mixed_spaced_839.py`: **11 passed**. On a real `git archive
  origin/main` tree: **7 failed, 4 passed** (the 4 are the forms that always
  worked).
- Mutants (anchor asserted = 1, bytecode off): the space-separated alternative
  unspaced again, killed (2); the hyphenated alternative unspaced again, killed (6).
- Neighbour suites (archetype, taxonomy, spec-sheet, fraction): **603 passed**.
  `sync_plugin.py --check` in sync.

DONE 4 (a comment on #835's unit rows pointing here) waits for #835 to merge.
Those rows are not on `main` yet.

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py`: `_NUM_CORE`.
- `plugin/lib/src/rvt/famgen/archetypes.py`: mirror.
- `tests/test_mixed_spaced_839.py`: new, 11 tests (10 rows + the 18,000-prompt sweep).
- `tests/ci_shard.d/839-mixed-spaced.txt`: new.
- this fragment.

**Gates**: 11 passed; 2/2 mutants killed; 603 neighbour tests passed;
plugin in sync. Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: shipped; no file-format change.
