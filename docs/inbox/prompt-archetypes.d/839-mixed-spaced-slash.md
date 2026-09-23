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

DONE 4 is done: after #835 merged, its two unit rows carry a comment
pointing here.

## Round 1 — spaced slashes made a unit-less width swallow a voltage

🛑 on `b4dc331`. With a spaced slash accepted, a whole number followed by any
slash token joined into a "mixed number":

```
"wireway width 12 480 / 277 V"                -> 13.73 given   (main 12)
"lighting control panel width 24 24 / 7 ..."  -> 27.43 given
"conduit trade size 2 4 / 0 conductors"       -> dropped        (main 2)
```

The reviewer's generator (582,269 prompts) found 1,944 prompts right on main
and wrong on the head. **My 18,000-prompt sweep had no token after the
number**, so it could not see this: the same blind spot as #828's rounds.

**Fix.** A mixed number's fraction must be a real fraction of a unit:
- **proper**, over 2, 3, 4, 8, 16, 32 or 64 (`_MIXED_FRAC`), in both
  mixed-number alternatives;
- **ending** there: a unit may follow directly ("3/4in"), and any other letter
  makes it a token ("3/4w", three-phase four-wire).

A failed fraction falls back to the whole number, so "width 12 480 / 277 V"
keeps its 12. This also fixes two defects `main` already had: "width 20
277/480 V" (20.58 on main) and "wide 6 3/4w" (6.75 on main).

| instrument | prompts | `main` wrong | this head wrong | worse than `main` |
|---|---|---|---|---|
| slash tokens after a number (voltages, 4/0, 24/7, 12/2, dates, 3/4w …), every inch alias | 19,440 | 7,020 | 3,132 | **0** (round 0: 3,888) |
| every hyphen × slash spacing | 18,000 | 13,500 | 0 | **0** |
| #828 corpus | 269,361 | — | — | 0 outputs change |
| `fuzz_prompt_dims` generators 1–3, seed 1 | 60,000 | — | — | **0** (0 better) |

The 3,132 still wrong are all "N in ALIAS <slash token>". The alias-first
reading takes a *plain* fraction ("wide 480 / 277") as the value. That is a
separate defect already on `main`, filed on its own.

Tests: **70 passed** (12 slash-token rows, 3 hyphen rows). Mutants, 4 of 4
killed: any fraction in the space-separated alternative (11), any fraction in
the hyphenated one (3; it survived until the hyphen rows were added), no
end-of-fraction lookahead (2), no thirds (1).

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py`: `_NUM_CORE`.
- `plugin/lib/src/rvt/famgen/archetypes.py`: mirror.
- `tests/test_mixed_spaced_839.py`: new, 28 tests (rows, slash-token rows,
  hyphen rows, the 18,000-prompt sweep).
- `tests/test_fraction_parse_831.py`: a pointer comment on two unit rows (DONE 4).
- `tests/ci_shard.d/839-mixed-spaced.txt`: new.
- this fragment.

**Gates (round 1)**: 70 passed across `test_mixed_spaced_839.py` and
`test_fraction_parse_831.py`; 4/4 round-1 mutants killed (2/2 round 0);
plugin in sync. Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: shipped; no file-format change.
