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

## Round 5 — a rejected fraction re-read from its own middle

🛑 on `eae984c`. The round-4 blocker was confirmed fixed, with 0 of 6,688
improper spaced tokens × 19 tails worse than main. **A new regression, the
#839 defect itself:** when the mixed reading rejected an off-set unit-less
fraction, the match started again *at the fraction*. The `_NUM` lookbehind
blocked only a single space, so a hyphen, a double space or a tab slipped
through:
- **"cable tray 24 - 5/12 wide"** → 0.42 in `given` (main 24.42).
- "conduit 10 - 5/12 long" → 0.42 ft `given`.
- "cable tray 12  5/12 wide" (two spaces) → 0.42 in `given`.

On the reviewer's generator, 10,080 prompts were right on main and gave the
fraction alone on the head. My round-4 sweeps were alias-first with single
spaces, which is the separator blind spot for the sixth time.

**Fixes:**
- **A fraction may not start after a digit followed by up to four spaces or
  hyphens.** The first version of this barred *any* number there, and the
  fuzzers caught 9 / 11 / 16 prompts worse, because " - " also separates
  phrases ("tall of 1/2 - 46 1/8 in long" lost its 46). It now applies only
  when a fraction follows.
- **A spaced slash's denominator may not start a number either.** Without
  this, "24 - 5 / 12 wide" re-matched at "12 wide".
- **A spaced two-digit denominator must be one a measurement uses: 10, 12,
  16, 20, 32 or 64** (one-digit denominators are unchanged). This answers the
  reviewer's non-blocking finding 2: "12 / 24" and "24 / 48" are low-voltage
  pairs and "9 / 23" is a date. They joined as proper fractions ("wireway
  width 12 12 / 24 in the room" → 12.5).
- **A quote mark is a unit only when it closes the number.** "width 20
  12 / 24 'LCP-1'" read the tag's opening quote as feet and made a 246 in
  panel. That a bare "width 20 'LCP-1'" is read as 20 ft happens on main
  too, and is a separate issue.
- **A proper measuring fraction that ends the prompt now joins.** This
  retires the round-3 trade-off: "cable tray wide 2 1/5" was 2.0 `given`
  and is now 2.2. It was the one shape still right on main and wrong here,
  660 prompts on the generator below.

| instrument | prompts | right on `main`, wrong on head | notes |
|---|---|---|---|
| number-first × 9 separators (" - ", "- ", "  ", tab, "--" …) × 12 fractions × spaced/unspaced slash × 4 tails × 3 phrasings, every in/ft alias | 114,048 | **0** | 30,800 better; 22,000 wrong → nominal; **4,224 right → nominal**. These are hyphen and double-space off-set fractions, left nominal as the reviewer's own fix did. |
| round-4 slash-token sweep | 33,592 | **0** | every non-measuring token gives the whole number, except 2,040 unspaced improper tokens ahead of a unit word ("6 480/277 in the room"), which are byte-identical to main (#843) |
| fuzzers 1–3 | 60,000 | **0** | 0 better |

**Test gaps (finding 3) covered:**
- "wireway width 12 1 / 2" → 12.5 is now pinned.
- The exhaustive sweep now runs n in 1..99 against d in 1..130, so three-digit
  denominators never join.

Tests: **137 passed** in the two files (95 in `test_mixed_spaced_839.py`);
**343** across the five neighbouring suites plus `test_plugin_sync.py`.

Mutants: **7/7 killed**:
- no end-of-prompt join;
- the extended lookbehind applied to every number;
- no slash-denominator lookbehind;
- one-character separators only;
- any two-digit denominator;
- the opening quote as a unit, twice. This survived until a row with a real
  fraction before a tag was added.

## Round 6 — a fixed lookbehind list cannot say "after a whole number"

🛑 on `c699827`. The round-5 fixes held only for the shapes the tests used.
The reviewer's generators (1.2 million prompts) found three blocking shapes:

1. **The slash branch had lost main's tail.** Main read "24 / 3/4" as one
   token that no number reads. The head stopped at "24 / 3" and stamped
   **8 in `given`**:
   - "wireway width 8 / 4/0 AWG" gave a 2 in wireway;
   - the phrase-list generator produced 11,520 of these.
2. **Five or more separator characters got through.** "cable tray 24
   5/12 wide" with five spaces gave 0.42 in `given` again. The lookbehind
   list stopped at four characters, and no fixed-width list can cover a run
   of any length.
3. **The same list also barred fractions after digits that are not a whole
   number.** Examples: a tag ("EMT for LP-1 - 3/4 in conduit" gave nominal,
   main 0.75), 480/277's tail, a cross, and separators the mixed grammar
   never accepts ("--", " / "). That cost 118,236 stated dimensions main
   read right.

The reviewer also found (non-blocking) that the end-of-prompt lookahead was
quadratic on long whitespace runs.

**The fix replaces the lookbehind list with one pre-pass,
`_mask_orphan_fractions`, which `resolve_prompt` runs on the lower-cased
prompt before any pattern.** It looks for three things together:
- a real number start (not a tag's "LP-1", not a voltage's tail);
- a separator the mixed grammar itself accepts (whitespace, or a hyphen with
  optional whitespace, of any length);
- a fraction after it that the mixed reading of that number does *not*
  reach.

Such a fraction is blanked with a same-length neutral mark, so every offset
holds and nobody reads it. The whole number still reads alone ("width 12
480 / 277 V" is 12). `_NUM` is back to main's lookbehind.

**Also:**
- **Main's `N / M/D` tail is restored on the slash**, not on the hyphen,
  where "24 - 120/208 V" would join the voltage again.
- **The unit-less fraction set is now every proper *measuring* fraction.**
  That is a one-digit denominator, or 10, 12, 16, 20, 32 or 64, ending at
  whitespace or punctuation. It was 2/3/4/8/16/32/64 only, so "sheet
  thickness 1 - 5 / 12 each" fell back to 1.0 `given` where the user wrote
  1 5/12. That narrow set guarded against voltages and dates, which round 5's
  measuring set already excludes. This also retires round 5's separate
  end-of-prompt branch.
- **A quote is a unit only when it closes the number, in `_UNITS` too.**
  "width 20 'LCP-1'" was 240 in on main as well.
- **"N / M/D" never becomes N / M.**

**Measured against main.** Nothing regressed on any generator:

| instrument | prompts | right on `main`, wrong on head |
|---|---|---|
| new: tags before a fraction, separators 1–7 characters wide (spaces, tabs, non-breaking, hyphen runs), phrase lists joined by " - ", " -- ", " / ", ",", "\|", fraction tails, typographic units, 3 seeds | 180,000 | **0** in the reviewer's two false-`given` classes (fraction alone, N ÷ numerator). The head has 6,009 fewer "fraction alone" and 21 fewer "N ÷ numerator" than main. |
| fuzzers seeds 1–3 | 60,000 | **0** (0 better) |

The 43 head-only hits my classifier flags in the first row are all whole
numbers from *other* phrases in the same prompt ("wide 6 4/0 each" → 6) that
happen to equal another token's fraction. None is a fraction read alone.

**Ambiguous, stated:** a designator or tag number followed by a separator
and a fraction now reads as a mixed number. For example, "wireway for rev 3
- 1 / 2 inch long" gives 3 1/2 in where main gives 1/2 in, and "no. 3  3/4
ft" works the same way.

**Speed:** "cable tray wide 12 5 / 12" + 16,000 spaces + "x" takes 16.4 s,
against main's 7.9 s. Main's resolver is already quadratic on long
whitespace runs because `_SEP` appears twice; round 5's head took 26.7 s.
Ordinary prompts are unaffected. This is not pinned by a test (wall-clock
tests are flaky under CI load) and is recorded here instead.

**Tests:**
- **169 passed** in the two files: 127 in `test_mixed_spaced_839.py`, plus
  `test_fraction_parse_831.py`.
- 178 passed with `test_plugin_sync.py`.
- A wider run over every prompt, archetype, taxonomy, fraction, intent,
  spec-sheet and route suite (`RVT_SKIP_LARGE=1`) gave 4,855 passed and 3
  failed:
  - `test_catchain.py` ×2, which **fail on a main export too**, so they are
    not caused by this PR;
  - `test_plugin_sync.py`, run before the mirror was synced (it is now).

**Mutants: 9/9 killed:**
- no mask;
- mask after any digit;
- mask after "--" and " / ";
- no slash tail;
- the tail on the hyphen too;
- the narrow unit-less set;
- the opening `"` as inches;
- the opening `'` as feet;
- mask only when no number reads.

Two survived until their rows were added: a tag before a rejected spaced
fraction ("conduit for LP-1 - 5 / 11 in dia"), and a `"` after a length in
feet ('conduit length 10 "L-2"').

## Round 7 — the quote rule broke feet-inch notation; a conductor count became a length

🛑 on `4cdb9cd`. The round-6 fixes were confirmed. Two new false-`given`
regressions against main turned up, both from my own round-6 changes:

1. **The quote rule in `_UNITS` also applies to quotes touching the
   number.** "A quote is a unit only when nothing alphanumeric follows it"
   turned feet-inch notation and "24"W" forms into the parameter's own unit:
   - `height 7'0"` gave 7 in (main 84);
   - `length 60"L` gave 60 ft (main 5);
   - `24"wide, 4"deep, 12'long` lost all three.

   That was 14,539 diffs on the reviewer's quote generator. **My round-6
   generators never put a quote after a number.**
2. **A conductor count before a wire size became a dimension.** In "20 ft
   long 3-4/0 AWG", the mask blanked only "4/0", so the 3 stood alone and
   took the length: 3 ft. Main read "3-4/0" as no number at all. The
   reviewer's oracle sweep found 1,782 of these, every one of this shape.

**Fixes:**
- **A quote is a unit when it touches the number** (`(?<=\d)"`, and in the
  fraction lookahead a quote directly after the fraction), **or when nothing
  alphanumeric follows it.** A quote after a space that opens a word is still
  a tag ("width 20 'LCP-1'" is 20).
- **`_mask_orphan_fractions` blanks the whole token** (whole number,
  separator and fraction) when the separator is a hyphen, or when the
  fraction is an unspaced wire size (`/0`). That is main's reading. A spaced
  slash keeps its whole number, as main does: "width 12 480 / 277 V" is 12,
  and "trade size 2 4 / 0 conductors" is a 2 in conduit. That row caught a
  first version that blanked the spaced form too.

**Measured against main:**

| instrument | prompts | right on `main`, wrong on head |
|---|---|---|
| new: every in/ft alias × " and ' touching the number, followed by nothing / a letter / a digit / a word / a tag / feet-inch, both phrasings; and conductor counts N-a/0, N a/0, N a / 0 × 4 tails after a stated dimension | 18,184 | **0** (identical to main on every prompt) |
| round-6 generator (tags, separators 1–7 wide, phrase lists), 3 seeds | 180,000 | **0** in either false-`given` class (6,128 fewer than main); the 36 flagged are whole numbers from other phrases, as in round 6 |
| fuzzers seeds 1–3 | 60,000 | **0** |

**Stated, non-blocking (the reviewer's):**
- **The wider unit-less set joins spaced proper fractions that are counts.**
  "width 30 3 / 4 conductors" gives 30.75 (main 30); main already joins the
  unspaced form.
- **"20 ft long 1-1/2 in rails" gives a 1/8 ft length on main and here
  alike.** It is the alias-first reading (#880).

**Tests:** 188 passed in the two files (146 in
`test_mixed_spaced_839.py`), and 394 with the neighbouring suites and
`test_plugin_sync.py`.

**Mutants: 7/7 killed:**
- touching `"` not a unit;
- touching `'` not a unit;
- a touching quote after a fraction not a unit;
- never blank the whole token;
- no `/0` rule;
- the `/0` rule on spaced slashes too;
- no hyphen rule.

Two survived until their rows were added: `10 5/11'L`, and `20 ft long
3-5/11 each`.

## Round 8 — a tight hyphen before " / " is a list, not a mixed number

🛑 on `8488385`. The round-7 fixes were confirmed on the head and on the
tree merged with main. One new false-`given` class turned up: a hyphen
token before a " / " list separator. Main never joined a spaced slash after
"N-M", so it read the next phrase; this head read "N-M / D" as N M/D.
- **False `given`:**
  - `pull box / levels 2-3 / 12" wide` gave a 2.25 in width (main 12);
  - `emt / rev 2-3 / 12 feet long` gave 2.25 ft.
- **Dropped:** when the mixed reading was rejected, the round-7 whole-token
  mask took the next phrase's number with it. `rooms 101-104 / 24" wide`
  lost its width.
- **#839's own defect returned:** `rooms 101-104 / 1 5/8 in tall` gave 5/8
  alone.

On the reviewer's grid this was 73 false `given` and 54 drops in 152 " / "
prompts, and 0 with "," or " - ".

**Fix (one place, the mask pre-pass):** `_is_list_slash`. A tight hyphen
before a spaced slash is a **list** unless both of these hold:
- the fraction is a proper inch fraction (n < d, d a power of two);
- the prompt uses no other spaced slash.

For a list, the slash and its spaces are blanked, so neither side reads
across it and the next phrase's number stands. "a 2-1 / 2 in conduit"
(#839's own sweep) is still 2 1/2. A first version also put a
spacing-agreement rule into `_NUM_CORE`; the mask already decides every
case, so it was removed as dead code, with 0 outputs changed (checked on
180,000 prompts).

The branch is rebased on main `71ead7c`, which now carries #828's resolver
changes in the same file.

**Measured against main `71ead7c`:**

| instrument | prompts | right on `main`, wrong on head |
|---|---|---|
| new: 12 hyphen tokens (levels 2-3, rev 2-3, grid 4-7, rooms 101-104, 480-277, 12-18, LP-1, 3-4/0, 1-1/2 …) × separators " / ", ", ", " - ", " \| " × 6 dimension spellings × in/ft aliases | 12,672 | **0** (identical to main) |
| round-7 quote and conductor-count generator | 18,184 | **0** (identical to main) |
| round-6 generator, 3 seeds | 180,000 | **0** in either false-`given` class (6,220 fewer than main; the 36 flagged are whole numbers from other phrases, as before) |
| fuzzers seeds 1–3 | 60,000 | **0** |

**Stated, non-blocking (the reviewer's):** typographic marks (’ ″ ” ′) count
as units after a fraction, but `_UNITS` does not know them, so `tall 1 - 5 /
8’` reads 1.625 in. Main does the same on the unspaced form ("tall 1-5/8’"
is 1.625 in). This is #844, which should also cover ’/′ on inch parameters.

**Tests:**
- 202 passed in the two files.
- 628 with #812's, #816's, #820's and the archetype, intent and plugin
  suites, all on the rebased tree.

**Mutants: 3/3 killed:**
- never a list;
- an improper inch fraction joins;
- other slashes ignored.

The improper case survived until "junction box grid 4-7 / 4 in wide" was
added.

## Round 9 — the list rule needed no heuristic; two mask edge cases

🛑 on `9a1294d`. The round-8 fix was confirmed. Overall the head is far ahead
of main: on the reviewer's 60,000-prompt grid, 17,689 prompts main gets
wrong are read right. **26 regressions remained, in three classes:**

1. **The whole-token mask could start at a fraction's denominator.** In
   "tall = 3 / **4** - 277/480 v", blanking the rejected "4 - 277/480" ate
   the 4 of "3 / 4", leaving 3.0 `given` (main 0.75).
2. **A blank let an orphaned fraction through.** In "rooms 101-104/1 5/8 in
   tall", blanking "101-104/1" left " 5/8", and `_NUM`'s `(?<!\d )` guard
   saw a blank, not a digit, before the space. That gave 0.625 `given`
   (main nominal): #839's own defect again.
3. **Round 8's "lone inch fraction" exception had no reliable signal.** Its
   "no other spaced slash" check missed every other separator, so "pull box
   | levels 2-3 / 8 in wide" was 2.375 (main 8). The same held for `/`,
   `//`, `;`, `,`, ` - `, and for 4, 8 and 16 in sizes.

**Fixes:**
- **A match whose whole number is a fraction's denominator is skipped**
  (`\d\s*/\s*$` before it). This is the reviewer's tested fix.
- **The blank counts as a digit in `_NUM`'s guard** (`(?<![\d\x00] )`).
  Also the reviewer's tested fix.
- **A tight hyphen before a spaced slash is now always a list.**
  `_is_list_slash` and its power-of-two exception are gone. Mixed numbers
  are written "2-1/2" or "2 - 1 / 2". **The one spacing given up**, "a 2-1 /
  2 in conduit", now reads as a list (2 in; *main reads 2.0 too, corrected in round 10*). It is
  pinned as a strict xfail. The #839 spacing sweep leaves out its 2,700
  asymmetric prompts: 15,300 remain, all right.

The branch is rebased on main `f1672e4` (`archetypes.py` unchanged there
since `71ead7c`).

**Measured against main `f1672e4`:**

| instrument | prompts | right on `main`, wrong on head |
|---|---|---|
| list generator, now with separators " / ", "/", " // ", "; ", ", ", " - ", " \| " | 22,176 | **0** |
| round-7 quote and conductor-count generator | 18,184 | **0** (identical) |
| round-6 generator, 3 seeds | 180,000 | **0** in either false-`given` class (6,211 fewer than main; the 38 flagged are whole numbers from other phrases, as before) |
| fuzzers seeds 1–3 | 60,000 | **0** |

In the list generator, the only differences from main are 44 prompts like
"cable tray/rooms 101-104/12 wide", where main gives a wrong 109.67 `given`
and the head leaves the value nominal.

**Stated, non-blocking (the reviewer's):** " - " as a list separator is
ambiguous with the mixed-number grammar. "junction box - qty 4 - 5 / 8"
wide" gives 4.625, as main gives 4.25 for the tight "qty 4 - 1/4 in". A
`_NOT_A_SIZE_LEAD` guard on the whole number could cover it; that belongs
with #880's alias-first rating guard.

**Tests:** 215 passed and 2 xfailed in the two files (175 tests in
`test_mixed_spaced_839.py`); 641 passed and 7 xfailed with the neighbouring
suites.

**Mutants: 4/4 killed:**
- a denominator may start a token;
- the blank is not a digit;
- inch fractions still join (round 8's rule);
- never a list.

## Round 10 — the whole-token mask ate the next mixed number's whole number

🛑 on `2459a04`. All three round-9 fixes were confirmed. The head reads about
28,600 of the reviewer's 80,000 prompts better than main. **One new
regression, in #839's own class:**
- "cable tray, floors 2 - 3 / 24 - 1/2 in wide": the rejected "2 - 3 / 24"
  was blanked whole, including the 24 that starts the next mixed number.
  "1/2 in" was then read alone: **0.5 `given`** (main 24.5).
- The same shape dropped main's right answers to nominal ("floors 2 - 3 /
  2 1/2 in diameter").
- The chained form "floors 2 - 3 / 1 / 4" rung centres" gave 4.0 (main 0.25).

On the reviewer's two grids: 7 and 10 fractions read alone, and 11 and 16
values lost.

**Fix (the reviewer's, tested as a mutant):** when the slash is spaced and
its denominator opens another number (a mixed number, or a further slash),
the mask blanks only up to the denominator, so the next number reads. The
spaced-slash condition is needed: without it, round 9's tight-slash rows
("rooms 101-104/1 5/8 in tall") break, and the mutant test kills that
variant.

**Record correction:** round 9 said main reads "a 2-1 / 2 in conduit" as
0.5. **Main reads it as 2.0, the same as the head.** So the spacing given up
is a false `given` on both trees, not a regression; it stays a strict xfail.

**Stated, non-blocking (the reviewer's):**
- **" - " as a list separator joins into a mixed number with a spaced
  slash.** For example, "phase 3 - 3 / 16 in. thickness" gives 3.1875, and
  "9 / 23 / 26 - 1 / 4 inches" gives 26.25. Main does the same with a tight
  slash. These belong with #880's rating and lead-word guard.
- **An alias-led thickness can take a feet value from the next phrase.**
  "32 1/10 in sheet thickness: 34 - 5/ 12' long" gives 413 on the head.
  Main gives 413 for the tight form and 408 for a plain "34'".

**Measured against main `f1672e4`** (`archetypes.py` is unchanged on `be0a350`):

| instrument | prompts | right on `main`, wrong on head |
|---|---|---|
| list generator, 7 separators | 22,176 | **0** (the same 44 main-wrong → nominal) |
| quote and conductor-count generator | 18,184 | **0** (identical) |
| round-6 generator, 3 seeds | 180,000 | **0** in either false-`given` class (6,211 fewer than main) |
| fuzzers seeds 1–3 | 60,000 | **0** |

**Tests:** 228 passed and 2 xfailed in the two files (188 in
`test_mixed_spaced_839.py`, with the reviewer's 13 probes as rows); 654
passed and 7 xfailed with the neighbouring suites.

**Mutants: 2/2 killed:**
- the denominator branch off;
- no spaced-slash condition.

---

## Round 11 — the round-10 branch freed a whole number and a range's end

🛑 on `4cd2a6f`. The round-10 rows held. **Two regressions came from round 10's own branch:**
- **The whole number was blanked even with no hyphen.** The branch blanked from the whole
  number whenever the denominator opened another number, so a voltage pair or wire size before
  a fraction ate the dimension that preceded it.
  - "conduit trade size 1 120 / 208 3/4 in conduit" gave **208.75 `given`** (main 1).
  - "lighting control panel width 20 277 / 480 3/4 in conduit" lost the width to nominal (main 20).

  The function's docstring ("a SPACED slash keeps its whole number, as main does") was untrue at
  `4cd2a6f`, and the round-10 section above did not say the branch also did this.
- **A range opened by the denominator lost its start.** On main, "18 - 24" after "6 - 12 /" is one
  token that reads as nothing. Blanked up to it, its "24" read alone.
  - "cable tray 6 - 12 / 18 - 24 in wide" gave **width 24 `given`** (main nominal).
  - "wireway width 12 480 / 277 - 6 in tall" gave height 6 (main: height follows the width, 12).

**Fix (the reviewer's, tested):**
- A token with no hyphen blanks only from the numerator, so the whole number stays.
- A denominator after "/ " that opens an "N - M" range is kept, so the range stays one unreadable
  token as on main.
- The "/ " condition matters: after a tight "/", main reads the range's end
  ("strut channel depth 6  277 /12 - 36 long" is a 36 ft length), and so does this.

**Measured** against main (`archetypes.py` unchanged since `f1672e4`; main is `be0a350`) and
against round 10 (`4cd2a6f`):

| instrument | prompts | round 11 vs main | round 11 vs round 10 |
|---|---|---|---|
| round-6 generator, 3 seeds | 166,781 unique | 18,410 differ (round 10's measured improvements) | 11 differ, all toward main: 8 return exactly to main's reading, 3 restore one of main's values while keeping a round-10 improvement on another |
| list generator, 7 separators | 22,176 | the same 44 main-wrong → nominal | identical |
| quote and conductor-count generator | 18,184 | identical | identical |
| fuzzers seeds 1–3 | 60,000 | identical | identical |

So round 10's "0 worse than main" results stand: no prompt moved away from main.
*(Corrected in round 12: that sentence was wrong. These generators compare trees but
hold no oracle for "worse", and they do not produce the shapes round 12 found — three
classes that read worse than main, two of them since round 9.)*

**Not blocking (the reviewer's; main does the same):** two phrases run together with no
punctuation, where the second uses round 9's tight-hyphen + spaced-slash list form, can still
lend a number across the boundary. "cable tray deep 12 3 /4in rung centres of 4-3 / 16 in" gives
rung spacing 12.75. Main gives 12.75 for the unspaced form too. This is main's existing tiebreak
between reading the alias first and the number first.

**Tests:**
- 240 passed and 2 xfailed in the two files: 200 in `test_mixed_spaced_839.py`, with the
  reviewer's 10 repros and its 2 tight-slash guard rows. Each row asserts main's full `given` set.
- 666 passed and 7 xfailed with the neighbouring suites.
- 117 passed in the four prompt-intent suites.

**Mutants: 3/3 killed:**
- whole number blanked regardless of hyphen (7 failures);
- the "/ " guard dropped (3);
- the range clause dropped (6).

---

## Round 12 — a list after a slash, a slash-glued number, and a glued denominator

🛑 on `28a958b`. Both round-11 cases were confirmed fixed. **Three classes still read worse than
main**, and the round-11 sentence "no prompt moved away from main" was wrong:
1. **Round 9's denominator skip ran before round 8's list rule**, so a tight-hyphen list after a
   slash read as a mixed number again. Round 8 read these as main does.
   - "cable tray levels 1 / 2-3 / 12\" wide" gave **2.25 `given`** (main 12).
   - "cable tray 3 / 2-3 / 6 in deep" gave 2.5 (main 6).
2. **The list rule blanked a slash that touches the next number**, which freed that number.
   Main never reads a number glued to a slash.
   - "cable tray levels 2-3 /4 / 6 in deep" gave **0.667** (main 6).
   - "a 2-3 /4 in conduit" gave **4 in `given`** (main nominal).
3. **Round 10's denominator branch freed a slash-glued denominator** on its mixed-number
   alternative. Round 11 had guarded only the range alternative.
   - "a 2 120 /208 3/4 in conduit" gave **208.75 in `given`** (main nominal).

**Fix (the reviewer's, tested):**
- The list rule runs before the denominator skip.
- The list rule leaves a slash that touches the next number unless that number opens a mixed
  number.
- The "/ " guard covers both alternatives of the denominator branch.

**Measured:**
- **The reviewer's generators** (the evidence for these shapes):
  - 96,711 prompts of dimensions next to distractors;
  - 150,000 random mixed/slash prompts.

  Every prompt where the fix differs from `28a958b` either returns exactly to main's reading
  (204 and 3,029) or moves toward the intended value (3). None reads worse than main.
- **The cost:** some slash-glued garbage shapes, where main was already wrong, return to main's
  wrong reading instead of round 10's better one. For example, "a 1\t12 /2 - 1/2 in strut" gives
  0.5, as main does.
- **This session's generators**, against round 11:
  - round-6 generator, 166,781 unique prompts: 3 changed, all 3 back to main's reading;
  - list, quote/conductor and fuzzer sets (100,360): identical.

**Tests:**
- 250 passed and 2 xfailed in the two files: 210 in `test_mixed_spaced_839.py`, with the 10
  repros as rows pinning main's full `given` set.

**Mutants: 3/3 killed:**
- skip before the list rule (4 failures);
- glued slash blanked (5);
- guard on the range only (9).

---

## Round 13 — round 12's glued-slash exception, and main's "N / D/x" tail

🛑 on `797947a`. **Two classes read worse than main:**
1. **Round 12's list rule kept a glued slash unless a mixed number followed.** That exception
   brought round 12's class 3 back through the list rule. It was already present at `c74f6ac`,
   `4cd2a6f` and `28a958b`.
   - "a 1-120 /208 3/4 in conduit" gave **208.75 in `given`** (main nominal).
   - "cable tray width 24 2-120 /208 1/2 in deep" added depth 208.5.
2. **Round 10's denominator branch freed the D/x of main's "N / D/x" tail.** It did this through
   its `\s*/\s*\d` alternative. Main keeps "3 / 120/208" as one token that no number reads.
   - "cable tray levels 2 - 3 / 120/208 in deep" gave **0.577 in `given`** (main nominal).

**Correction to round 12:** "None reads worse than main" held only for prompts where round 12
differed from round 11. Class 1 was unchanged by round 12 and still read worse.

**Mutant counts:** the round-12 counts (4, 5, 9) are for this session's mutant definitions. The
reviewer's reproductions gave different counts (3, 4, 3–6). Every variant is killed.

**Fix (the reviewer's, tested):**
- The list rule always keeps a slash that touches the next number.
- A denominator after "/ " that opens a slash token, where that token is no measuring fraction,
  stays one token as on main.

**What it gives up:** about 58 improvements that only the exception produced. Their syntax is the
same as "1-120 /208 3/4", and no rule tells them apart without a magnitude heuristic.
- "levels 2-3 /12 1/2 in wide" read 12.5; it now reads nominal, as on main.
- "2-3 /2 - 1 / 2 in" read 2.5; it now reads 0.5, as on main.

**Known trades, stated (the reviewer's; not regressions introduced this round):**
- **A list value after a whole number.** A spaced, improper "N / D" after a whole number is
  blanked whole, so a list value that main read is lost. "cable tray, rooms 101 102 / 12 in deep"
  gives nominal (main 12). This is the round-4/5 trade that guards "width 12 480 / 277 in": the
  two shapes differ only in their numbers.
- **A list item shaped like a mixed number.** It reads as one: "a 10 ft long 2 - 3 / 4 conduit"
  gives 2.75 (main 10). That is the feature itself — "2 - 3 / 4" is how #839's users write 2¾.

**Measured:**
- **The reviewer's runs:**
  - Round 12's 96,711-prompt oracle generator: target-lost 277 both before and after the fix.
    All 277 are the same "2 - 3 / 4" list item, the second trade above.
  - Main wrong, now right: 5,672 → 5,614.
  - Round 12's 150,000-prompt random set: 1,486 prompts change against `797947a`, and all
    1,486 return exactly to main's `given` set.
  - The reviewer's own 127,520 prompts: every change returns exactly to main's reading.
- **This session's generators, against round 12:** 0 of 267,141 changed. They do not produce
  these shapes. They compare trees and hold no oracle for "worse", so the reviewers' runs are
  the evidence.

**Tests:**
- 258 passed and 2 xfailed in the two files: 218 in `test_mixed_spaced_839.py`, with 8 rows
  pinning main's full `given` set.
- 684 passed and 7 xfailed with the neighbouring suites.
- 117 passed in the prompt-intent suites.

**Mutants: 2/2 killed:**
- the round-12 exception restored (6 failures);
- the tail skip dropped (4).

---

## Round 14 — main moved under the branch: the strut trapeze

🛑 on `f557781`: **no parser counterexample, but the PR turned main red.**

**What changed on main.** The rounds since round 10 said main's `archetypes.py` was unchanged
since `f1672e4`. That stopped being true at `b05f7af` (#899) and `1a835d4` (#907), which added a
`strut_trapeze` archetype with:
- bounded parameters;
- a `count` unit;
- `settle`-derived values;
- `noun_leads` and `phrases`.

**Which tests failed.** On the merge with `1a835d4`, two sweeps failed, all on that archetype. The
PR's own sweeps did not know three things:
- A value outside a parameter's range stays nominal by design. "strut trapeze 1-1/2 in long"
  keeps the 30 in nominal, because strut length must exceed 6 in.
- A value that `settle` derives is not a stray. A strut length also yields a rod spacing.
- Main's noun-lead rule then takes some of the out-of-range values.

**Fix (the reviewer's, tested).** Rebased onto `1a835d4`. The sweeps skip out-of-range values, and
the stray check ignores `Resolved.derived`. No parser change this round.

**Measured against `1a835d4`:**
- **The reviewer's oracle generator:** 220,000 prompts, every archetype including the trapeze, 13
  spacings, and noise (voltages, AWG including 3-4/0, dates, ranges, lists, tags, NEMA).
  - 58 prompts read main-nominal → head-wrong.
  - 396 read main-correct → head-wrong or nominal.
  - Every one of these 454 equals main's own reading of the same prompt with its slash closed up
    ("2 - 1 / 2" → "2-1/2"). That is the existing #812 ambiguity between two phrases, plus the
    stated trades. So the new spacing reads as main reads the tight form.
- **This session's generators** compare trees and hold no oracle for "worse":
  - Quote/conductor (23,192) and fuzzers (60,000): identical to main.
  - List generator (26,208): the same 44 main-wrong → nominal, plus 6 trapeze rows of the same
    shape. For example, "strut trapeze/rooms 101-104/12 long" gives nominal; main gives 109.67.
  - Round-6 generator (169,095): a sample of the trapeze differences is the same classes as on
    every other archetype.
    - Fractions now join their whole number: "12\t3 / 4 in slot centers" gives 12.75 (main 0.75).
    - Noise fractions are dropped: "#10     5 / 12 in. channel height" gives nominal (main 0.42).
    - Stated trades, for example "1     12/24 each" gives 1 (main 1.5).
- **Found on the way, main's own:** a rod inset of half the strut length or more settles a zero or
  negative rod spacing stamped `given`. Filed as #911.

**Tests:**
- 258 passed and 2 xfailed in the two files.
- 830 passed and 7 xfailed with the neighbouring suites and main's new ones (`test_strut_trapeze_899`,
  `test_drive_law_904`, `test_fan_coil_893`, `test_panelboard_detail_892`).
- 117 passed in the prompt-intent suites.

**CI:** the first run on `f557781` was stopped by the shard's 1500 s limit at 88%. It shared four
cores with the reviewer's generators. Earlier runs took 904–938 s. That was not a test failure, and
the run is repeated on the new head.

**Performance — found by CI, fixed on the branch.**
- **What CI showed.** The shard was killed at its 1500 s limit (88%) on `a090d21` too, with the box
  to itself.
- **The cause.** The PR's number grammar made `resolve_prompt` **2.5× slower** than main: 3.40 vs
  1.35 ms per prompt on 2,730 three-phrase strut-trapeze prompts. The regex cache was not
  thrashing; both trees use 171 distinct patterns. The patterns were 11× longer (mean 1,739 vs 156
  characters):
  - `_PROPER_SPACED` spelled every numerator out ("63|62|…|1");
  - `_NUM_CORE` held `_MIXED_FRAC` twice;
  - every alias pattern embeds `_NUM`, and the cross pattern embeds three copies.
- **The two rewrites** (`_NUM`: 2,786 → 872 characters):
  - `_one_to(n)` spells 1..n compactly ("[1-9]|[1-5]\d|6[0-3]"). It is checked against 0..129 for
    every n.
  - The hyphen-joined mixed fraction is folded into the first alternative. No other alternative
    can match at the same start, because only "1,200" has a comma after its digits.
- **Result:**
  - 2.09 ms per prompt, 1.5× main's 1.35.
  - Output is identical to the pre-rewrite head on all 278,495 generator prompts (169,095 + 26,208 +
    23,192 + 60,000).
  - 748 tests passed and 2 xfailed across the touched suites.
- **What is main's own:** `tests/test_archetype_alias_order_812.py` alone takes 385 s on main (about
  30 s before #899), because it sweeps every parameter triple and the trapeze has about 13
  parameters. Filed as #918.

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py`: the number grammar.
  - `_NUM_CORE`: the spaced-slash mixed forms, and main's slash tail kept.
  - `_MIXED_FRAC`, `_PROPER_SPACED`, `_FRAC_UNITLESS`, `_FRAC_UNIT_AHEAD`,
    `_SPACED_DENOMS`.
  - The quote-mark units in `_UNITS`.
  - `_NUM`'s guard.
  - `_one_to` (round 14: the compact numerator ranges).
  - `_WHOLE_THEN_FRACTION` / `_mask_orphan_fractions` (new).
  - `resolve_prompt` now masks `low` first.

  *(Corrected in round 9: this line used to list only `_NUM_CORE`.)*
- `plugin/lib/src/rvt/famgen/archetypes.py`: mirror.
- `tests/test_mixed_spaced_839.py`: new, 218 tests (rows, slash-token rows,
  hyphen rows, unit, hyphen-unit and cross rows, the spacing and denominator
  sweeps, the round-11 to round-13 rows that pin main's full reading; the sweeps skip
  out-of-range values and settled values, round 14).
- `tests/test_fraction_parse_831.py`: a pointer comment on two unit rows (DONE 4).
- `tests/ci_shard.d/839-mixed-spaced.txt`: new.
- this fragment.

**Gates (round 14, rebased onto `1a835d4`)**: 258 passed + 2 xfailed across the two files
(830 + 7 xfailed with the neighbouring suites and main's new trapeze/drive-law/fan-coil/panelboard
suites; 117 in the prompt-intent suites); plugin in sync.

**Gates (round 13)**: 258 passed + 2 xfailed across the two files (684 + 7 xfailed with
the neighbouring suites; 117 in the prompt-intent suites); 2/2 round-13 mutants killed; plugin
in sync.

**Gates (round 12)**: 250 passed + 2 xfailed across the two files (676 + 7 xfailed with the
neighbouring suites; 117 in the prompt-intent suites); 3/3 round-12 mutants killed; plugin
in sync.

**Gates (round 11)**: 240 passed + 2 xfailed across the two files (666 + 7
xfailed with the neighbouring suites; 117 in the prompt-intent suites); 3/3 round-11
mutants killed; plugin in sync.

**Gates (round 10)**: 228 passed + 2 xfailed across the two files (654 + 7
xfailed with the neighbouring suites); 2/2 round-10 mutants killed; plugin
in sync.

**Gates (round 9)**: 215 passed + 2 xfailed across the two files (641 + 7
xfailed with the neighbouring suites, on the tree rebased onto `f1672e4`);
4/4 round-9 mutants killed; plugin in sync.

**Gates (round 8)**: 202 passed across the two files (628 with the
neighbouring suites, on the tree rebased onto main `71ead7c`); 3/3 round-8
mutants killed; plugin in sync.

**Gates (round 7)**: 188 passed across the two files (394 with the
neighbouring suites and `test_plugin_sync.py`); 7/7 round-7 mutants killed;
plugin in sync.

**Gates (round 6)**: 169 passed across the two files (178 with
`test_plugin_sync.py`); 9/9 round-6 mutants killed; plugin in sync.

**Gates (round 5)**: 137 passed across `test_mixed_spaced_839.py` and
`test_fraction_parse_831.py` (343 with the neighbouring suites and
`test_plugin_sync.py`); 7/7 round-5 mutants killed; plugin in sync. Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: shipped; no file-format change.
