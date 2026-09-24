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

## Round 4 — a spaced voltage before "in" still joined

🛑 on `dac25ec`. The unit branch accepted a spaced slash with any numerator
and denominator, improper ones included, so round 1's blocker came back
through round 2's branch:
- **"wireway width 12 480 / 277 in the electrical room"** gave 13.73
  `given`. The unit lookahead took the preposition "in" for inches.
- **"lighting control panel width 24 120 / 208 'LP-1'"** gave **294.9 in**
  `given`. The quote was read as feet.
- 12 / 2, 24 / 7, 277 / 480 and "480 / 277 footprint" did the same.

The reviewer counted 19,344 prompts that main gets right and that came back
as a false `given`. My round-3 slash-token sweep missed them because it never
put an "in"-word, a quote or an "x" after a spaced voltage. **That is the
same blind spot for the fifth time.**

**Fix:** only an *unspaced* slash ahead of a unit takes any denominator. That
is main's reading, kept: "10 5/12 ft", and also "12 480/277 in", which main
gives too. A *spaced* slash ahead of a unit must be a proper fraction with at
most two digits on each side (1/5, 5/12, 7/20, 11/12, 13/15). Improper
fractions (480 / 277, 20 / 19, 5 / 5, 4 / 0) never join. The reviewer's
variant dropped spaced off-set fractions altogether, which cost two correct
rows ("12 7 / 20 inches", "24 - 1 / 5-in"). The properness check keeps them.

| instrument | prompts | `main` wrong | head | worse than `main` |
|---|---|---|---|---|
| new: every in/ft alias × 26 slash tokens (voltages, wire, proper, improper, spaced and not) × 19 tails ("in the room", "'LP-1'", "x 365", "footprint", "feet away", units) × 2 separators | 33,592 | — | 11,220 outputs differ | **0 improper tokens given anything but the whole number** |
| fuzzers 1–3 (`fuzz_prompt_dims.py`, 20,000 each) | 60,000 | 11,147 | 11,147 | **0** |
| exhaustive "12 n / d in", n, d in 1..99 | 9,801 | — | 0 wrong (joins iff n < d) | — |

Of the 11,220 differences:
- 6,528 are better: improper → whole number, or a proper fraction before a
  real unit.
- 4,692 are a **stated trade-off**: a proper spaced fraction followed by a
  word that looks like a unit ("wide 6 5 / 12 in the room" → 6.42,
  "6 1 / 5 feet away" → 6 1/5 ft). Main gives the whole number there. A
  whole number followed by a proper fraction reads as a mixed number far more
  often than as two quantities, and the unspaced form ("6 5/12 in the room")
  has read this way on main all along.

**Stated, not covered (reviewer's non-blocking nits):**
- **A unit that is not directly after an off-set fraction falls back to the
  whole number.** Examples: "wide 2 1/5 (in)", "2 1/5, in", "2 1/5“",
  "2 1/5 (56 mm)", "10 5/12 lf" / "linear ft", "2 1/5 or 3 1/5 in". All need
  a /5, /10 or /12 style denominator. This is the round-3 trade-off
  extended; main gives the fraction.
- **Crosses with an off-set unit-less fraction in the 2nd or 3rd position
  drop to nominal.** Examples: "a 4 x 2 1/5 wireway", "4 x 2 1/2 x 6 1/5
  junction box", "trade size 2 4 / 0 in each". No false `given`.

Tests: **110 passed** in the two files (18 new rows, plus the n/d 1..99
sweep); **307** across the five neighbouring suites. Mutants: **7/7 killed**:
- the round-3 regex;
- the reviewer's variant;
- each of the three properness branches removed;
- equal digits allowed, twice.

A trailing-digit guard survived and was removed as dead code, because the
unit lookahead already requires the unit next. The new sweep's output is
byte-identical without it.

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py`: `_NUM_CORE`.
- `plugin/lib/src/rvt/famgen/archetypes.py`: mirror.
- `tests/test_mixed_spaced_839.py`: new, 68 tests (rows, slash-token rows,
  hyphen rows, unit, hyphen-unit and cross rows, the spacing and denominator
  sweeps).
- `tests/test_fraction_parse_831.py`: a pointer comment on two unit rows (DONE 4).
- `tests/ci_shard.d/839-mixed-spaced.txt`: new.
- this fragment.

**Gates (round 4)**: 110 passed across `test_mixed_spaced_839.py` and
`test_fraction_parse_831.py` (307 with the five neighbouring suites); 7/7
round-4 mutants killed; plugin in sync. Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: shipped; no file-format change.
