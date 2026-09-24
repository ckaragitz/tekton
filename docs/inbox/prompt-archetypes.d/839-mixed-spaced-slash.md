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

## Round 2 — the round-1 fraction set was too narrow when a unit follows

🛑 on `b69b9a9`. Round 1 applied the 2/3/4/8/16/32/64 set everywhere, so
**"cable tray wide 2 1/5 in" fell back to 2.0, stamped `given`** (main 2.2).
Inside a cross it was worse: "a 2 1/5 x 4 in wireway" lost the cross, and the
noun rule read W4 H4. A glued plural "1 1/2ins" was 1.0, and "2 1/2x4 in"
went nominal. On the reviewer's generator, 17,681 prompts were right on main
and false `given` on the head. **My slash-token sweep had only 2-to-64
denominators with units**, so round 1's "0 worse" held for my shapes only.
That is the same lesson as #828.

**Fix: the rule depends on what follows the fraction.**
- A fraction **followed by a unit or by the `x` of a cross** is always a
  fraction of that unit, whatever its denominator. That is main's reading,
  kept.
- **With no unit after it**, it must be proper, over 2/3/4/8/16/32/64, and end
  at whitespace or punctuation. This is the voltage / 4/0 / 24/7 / "3/4w"
  case from round 1.

| instrument | prompts | `main` wrong | head wrong | worse than `main` |
|---|---|---|---|---|
| denominators /5 /6 /10 /12 /20 /100 /2 × 3 separators × in/inch/"/ins, crosses | 31,590 | 3,150 | 3,150 | **0** |
| slash tokens after a number | 19,440 | 7,020 | 3,132 | **0** |
| every hyphen × slash spacing | 18,000 | 13,500 | 0 | **0** |
| #828 corpus | 269,361 | — | — | 0 outputs change |
| fuzzers 1–3, seed 1 | 60,000 | — | — | **0** |

The 3,150 denominator-sweep failures are the same prompts on `main`:
number-first phrases with a glued "ins" ("1 1/2ins tall"). `_UNITS` has no
"ins", which is filed separately.

Tests: **84 passed** across `test_mixed_spaced_839.py` and
`test_fraction_parse_831.py`. There are 8 unit rows (/5 /10 /12 /20, "ins"),
4 cross rows, a thirds-without-unit row, and a 5,000+ prompt denominator
sweep. Mutants, 7/7 killed:
- the round-1 set everywhere (14);
- no cross `x` after a fraction (4);
- no "ins" (3);
- letters allowed after a unit-less fraction (2);
- any fraction in either alternative (11, 3);
- no thirds (1; it survived until the unit-less row was added).

One branch of round 2 was **removed rather than tested**: it allowed a cross
`x` after a *unit-less* fraction. The unit branch already covers that, so a
mutant dropping it changed nothing.
## Round 3 — a hyphen before the unit, the grammar's own separator

🛑 on `2270f66`. `_FRAC_UNIT_AHEAD` allowed only spaces before the unit, but
the prompt grammar's separator is `_SEP = [\s-]*`. So
**"conduit length 10 5/12-ft" fell back to 10.0 `given`**, and "width 24
1/5-inch" to 24.0. On the reviewer's generator that was 3,150 false `given`
with an explicit unit. My round-2 denominator sweep joined units only with a
space: **the same blind spot a fourth time.**

**Fix:** `[\s-]*` before the unit, and the typographic marks `″ ”` (inch) and
`′ ’` (foot) count as units after a fraction.

| instrument | prompts | `main` wrong | head wrong | worse than `main` |
|---|---|---|---|---|
| the test's denominator generator, now with `-in` `-inch` `″` | 21,600 | 0 | 0 | **0** |
| my denominator sweep (round 2) | 31,590 | 3,150 | 3,150 | **0** |
| slash tokens after a number | 19,440 | 7,020 | 3,132 | **0** |
| every hyphen × slash spacing | 18,000 | 13,500 | 0 | **0** |
| #828 corpus | 269,361 | — | — | 0 outputs change |
| fuzzers 1–3, seed 1 | 60,000 | — | — | **0** |

**Not changed, by the round-1 design (non-blocking in the review):** an
off-set fraction with no unit after it ("cable tray wide 12 1/5" at the end of
a prompt) still falls back to the whole number, 12 `given`, where `main`
gives 12.2. This is the other side of keeping "width 12 480 / 277 V" at 12.
A unit-less "1/5" is rare in a dimension prompt, and a voltage or wire size
after a unit-less number is not.

A number-first phrase with a typographic inch mark ("a 2″ wide cable tray")
is dropped on `main` too, because `_UNITS` has no `″`. That is added to #844
with "ins".

Tests: **92 passed** (8 new hyphen / typographic rows, and a hyphen-unit axis
in the denominator sweep). Mutants: **9/9 killed**. The two new ones are no
hyphen before the unit (7) and no typographic inch marks (3); the round-2
seven were re-run with their moved anchors.

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py`: `_NUM_CORE`.
- `plugin/lib/src/rvt/famgen/archetypes.py`: mirror.
- `tests/test_mixed_spaced_839.py`: new, 50 tests (rows, slash-token rows,
  hyphen rows, unit, hyphen-unit and cross rows, the spacing and denominator
  sweeps).
- `tests/test_fraction_parse_831.py`: a pointer comment on two unit rows (DONE 4).
- `tests/ci_shard.d/839-mixed-spaced.txt`: new.
- this fragment.

**Gates (round 3)**: 92 passed across `test_mixed_spaced_839.py` and
`test_fraction_parse_831.py`; 9/9 mutants killed; plugin in sync. Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: shipped; no file-format change.
