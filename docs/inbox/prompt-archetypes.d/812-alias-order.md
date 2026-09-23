# 812 — an alias stole the NEXT phrase's number, and stamped it `given`

Stream: **prompt-archetypes** (fragment; index `../prompt-archetypes.md`).
Issue **#812** (P0), branch `cam/812-alias-steals-number`. Found by the standing
test/debug loop (#805), hunting adversarial prompts on prompt → `.rfa`.

## The defect

```
$ tools/route.py run --prompt "cable tray 24 in wide 4 in deep 20 ft long" --output rfa
  width_in  =   4.0  given     <- the user said 24
  depth_in  = 240.0  given     <- the "20 ft long" value, read as depth
  length_ft =  10.0  nominal   <- the user said 20 ft
  built: side rails 20.0 ft tall
```

Not a parse miss: a wrong number wearing `given`, the tier that means *"you
stated it"*. A comma or "and" between the phrases hid it.

## The size of it — measured, not the one example

A property sweep over **every archetype's** dimensional aliases, with two- and
three-phrase chains in both phrasings ("7 in wide" / "wide 7 in"), in every
order, and no separators. Each generated prompt carries its own oracle: number
*i* belongs to the phrase it is written in.

```
main (git archive, rvt.__file__ printed):  5,488 prompts   4,287 ok   1,201 FAIL (22%)
  cable_tray 644, strut_channel 406, wireway 50, lighting_control_panel 50,
  junction_box 50, conduit 1
this branch:                               5,488 prompts   5,488 ok       0 FAIL
```

e.g. on `main`, "cable tray 7 in rung spacing 13 ft long" gave a **13-foot**
rung spacing, stamped `given`.

## Cause and fix

`_alias_patterns` emits two phrasings per alias, number-first (`24 in wide`) and
alias-first (`wide 24 in`), at the same sort key. Alias-first went first, its
connector is optional, and `_SEP` allows no comma. So it read *alias + whatever
number comes next*, stealing the next phrase's number.

**The fix binds under both orders and keeps the reading that gives more stated
dimensions a home.** Round 1 of the review changed the rest (next section): a
shorter alias may no longer match inside a longer one, and a tie on bindings
goes to the reading that leaves more of the user's other phrases whole, then to
number-first.

## Getting here — three designs, two of them wrong

1. **I posted a "verified" fix on #812 that was wrong:** rank number-first above
   alias-first. It went 10/13 → 13/13 on my table, with suites green. My table had
   no alias-first *chain*, and implementing the fix with a proper table showed it
   broke `width 24 in depth 6 in` — correct on `main`, 6 in depth read as 24.
   Corrected on #812.
2. **Then I cited the wrong witness.** I said a fixed number-first order fails
   `width 24 in depth 6 in`. That was true only of my first *global* rank sort; a
   per-alias number-first order handles it. A mutation run caught this: "always
   number-first" survived every test. The case that actually defeats a fixed
   number-first order is the **param-order-reversed** chain `depth 6 in width 24 in`
   (`width_in` is declared first, so its pattern takes `6 in width`). Measured,
   all four chain shapes under the three candidate orders:

   | prompt | alias-first only | number-first only | two-pass |
   |---|---|---|---|
   | `24 in wide 4 in deep` | W = 4 ✗ | ✓ | ✓ |
   | `4 in deep 24 in wide` | ✓ | ✓ | ✓ |
   | `width 24 in depth 6 in` | ✓ | ✓ | ✓ |
   | `depth 6 in width 24 in` | ✓ | W = 6, D = 4 ✗ | ✓ |

3. **Two-pass**: correct on all four, and on all 5,488.

**One instrument error along the way:** a first search for tie cases reported 110
"ties where the readings differ". It counted `given` values *after* `follows`
(strut width follows height), while the code counts bindings in the alias pass,
before `follows`. The direct test — the real code with `>` against `>=`,
compared over all 5,488 prompts — shows **zero** differing outputs.

## Round 0 evidence (superseded in part by round 1)

| mutant (anchor asserted from a script) | dies in |
|---|---|
| always alias-first (`main`'s behaviour) | 9 |
| always number-first (my first fix) | 3 |
| both passes alias-first (second pass inert) | 9 |
| tie-break flipped (`>` → `>=`) | **survives** — inert on all 5,488 prompts |

Round 0 said here that "the tie-break is not reachable". **That was wrong
outside the generated set**, and the review showed it: over restated prompts the
flip changed 1,759 outputs, and "a long 24 in wide 4 in deep cable tray" was a
tie that both `main` and round 0 got wrong. My generator only ever produced
the prompts I was already thinking about.

## Round 1 — the review found a regression I had introduced

> **Round 2 changed part of this section; see "Round 2" below.** The full-tie
> rule "number-first" was itself a regression and is reverted to `main`'s
> alias-first. The claim "worse than `main` on any prompt in any sweep: 0" held
> only for sweeps with the noun first, and it was wrong.

🛑 on head `59e872a`. **A dimension stated twice, whose alias contains a
shorter alias of another parameter**, got a false `given` from this PR that
`main` did not give:

```
"cable tray 1 in rung width, rung width 1 in"
  main:     rung_width_in = 1 given                      (right)
  59e872a:  rung_width_in = 1 given, width_in = 1 given  (a 1 in tray, "Ladder 1 in")
"strut channel 2 in slot length, slot length 2 in"
  59e872a:  also length_ft = 0.1667 given                (a 2-inch-long strut)
```

The number-first pass bound `rung width` from its first phrase. Its parameter
was then `given`, so its second phrase was nobody's, and `width` matched inside
it. One extra binding, and "more bindings wins" picked the wrong reading. The
reviewer's sweep: 331 of 14,724 prompts right on `main`, wrong on the PR, every
one a restatement.

**Fix 1 — a shorter alias never matches inside a longer one.** Every
occurrence of every alias is recorded up front, bound or not. A candidate match
overlapping an occurrence of a *longer* alias is skipped. Nested pairs this
covers today: `rung width`/`width`, `slot length`/`length`, `section
width`/`width`, `section height`/`height`, `loading depth`/`depth`, `rail
flange`/`flange`, `sheet thickness`/`thickness`, `diameter`/`dia`.

**Fix 2 — the tie-break, now that it is reachable.** In order: more bindings;
then the reading that leaves **more of the prompt's other phrases for its bound
parameters whole**; then number-first. I got the middle rule wrong once more
before landing it. My first version counted only restatements carrying the
*same* value. A mutant (count any value) survived the tests, and the search for
a prompt that told them apart found it was the mutant that was right: with
"wide 7 in loading depth 13 in wide 9 in", the same-value rule tied 2–2 and
number-first read `7 in loading depth` and `13 in wide`, a 13 in wide, 7 in deep
tray. What matters is whether a reading cut the user's phrases apart, not
whether they agree.

### Evidence — every sweep, three heads, `rvt.__file__` checked each run

| sweep (all generated, oracle per prompt) | prompts | `main` | round 0 `59e872a` | this head |
|---|---|---|---|---|
| chains, every alias rotated (in the tests) | 16,344 | 3,564 | 0 | **0** |
| restatements PPQ/PQP/PQQ/QPP (in the tests) | 18,496 | 2,152 | 2,401 | **0** |
| contradictions 7…9, PPQ/PQP/QPP (in the tests) | 13,872 | 1,478 | — | **0** |
| restatements, every alias pair, 3 separators | 8,520 | 1,144 | — | **0** |
| restatements PPQ/PQQ/QPP, every alias of P | 24,096 | 2,312 | — | **0** |
| bare alias before a chain, before the noun | 1,854 | 1,004 | — | 610 |

**Worse than `main` on any prompt in any sweep: 0.** The stray check is
`follows`-aware: a strut width that follows its stated height is `given` by
design, not stray. My first restatement sweep missed this and reported 2,204
failures that were really the oracle's.

**The 610 are ambiguous, not wrong, so they are recorded rather than filed.**
They are prompts like "a rail thickness 7 in loading depth 13 in rung spacing
cable tray", where a multi-word alias in front of a number is a perfectly good
label ("rail thickness 7 in"). My oracle assumed it was an adjective. Single-word
adjectives ("a long 24 in wide …") are the other 394 of that sweep, and number-
first fixes them.

| mutant (anchor asserted = 1, bytecode off, `__pycache__` cleared) | result |
|---|---|
| no nested-alias reservation | killed |
| reserve equal-length aliases too | killed |
| no intact-phrase count | killed |
| intact phrases must carry the same value | killed |
| full tie → alias-first (`main`'s rule) | killed |
| only the alias-first reading | killed |
| only the number-first reading | killed |

Considered and dropped: locating the alias inside each match before the overlap
test. A mutant that used the whole match survived, and it is equivalent: a
match's number and unit are never part of another alias's text. The code now
uses the whole match.

**Review nits addressed.** The chain sweep now uses every alias (rotated), not
just `aliases[0]`. It checks stray `given` values, and it has per-archetype
floors instead of one total (conduit had 8 prompts; now 24 chains, 320
restatements, and floors that fail if an archetype drops out). The #821 record's
"(round 2)" for `PERMUTATION-MATRIX.md` is corrected to round 1.

`tests/test_archetype_alias_order_812.py`: **56 passed, 3 xfailed** in 18.5 s.
The three strict xfails are the `W x D`-after-the-noun gap, split out as
**#827**; they resolve to an honest `nominal`, so lower severity.

## Record repair carried from #821 (round-3 nits, same stream)

`816-lighting-control-panel.md` said the kept `relay panel` alias shields "this
one prompt". Round 3 reproduced that it shields at least two: "a protective
relay panel" also builds an Eaton PRL2X panelboard with the alias removed (added
to #825). Its `BRANCH STATE` also listed round-0 gates and omitted
`PERMUTATION-MATRIX.md`. Both corrected in that fragment by this PR, as #821's
merge comment committed to.

## Round 2 — my tie rule broke the mirror shape, and my sweeps could not see it

🛑 on head `ba36c71`. The reviewer wrote their own random generator: 49,826
prompts; chains of 2 to 4 parameters; 9 unit spellings, fractions and 7
separators; the noun first, last and in the middle. Two failure classes, both
right on `main` and wrong on the head (509 prompts with seed 1, 481 with
seed 2):

1. **A label-first chain, then a bare adjective:** "junction box width 8 in
   height 6 in deep" became height = 8 and depth = 6, both `given`. The two
   readings tie completely, and rule 3 (number-first) picked the wrong one.
   That is the #812 defect again, from the other side. I justified rule 3 with
   the mirror shape ("a long 24 in wide …") and never generated this one.
2. **A restatement just before the noun:** "a 4 in depth, depth 4 in junction
   box" became a 4 in *wide* box. The winning reading left the restated phrase
   outside `used`, and the noun rules then read "4 in junction box" as the
   primary dimension. My three sweeps all put the noun **first**, so none of
   them could produce this. That is why "0 worse than main" was true of my
   sweeps and false of the product.

**Fix.**
- Rule 3 goes back to `main`'s alias-first. With `>=` → `>` as the only
  change, the reviewer measured 0 regressions against `main` on their
  generator.
- The winner's intact phrases are added to `used`, so the noun rules can never
  re-read a restatement.
- The mirror case "a long 24 in wide 4 in deep cable tray" is still wrong, as
  on `main`. It is now a **strict xfail citing #832**, which says why neither
  side of a full tie is safe and what a fix must be measured against.
- The reviewer's suggested intersection rule (keep only the bindings the two
  readings agree on) is recorded there too, with its cost: it turns "junction
  box width 8 in height 6 in deep", which `main` gets right, into all-nominal.

### Evidence — the noun moved, `rvt.__file__` checked each run

A placement sweep (my generator, not the reviewer's): chains, restatements,
contradictions, and a chain with a bare alias before or after it. Every alias of
the restated parameter, the noun first, last and in the middle, with and
without a comma. 132,548 prompts.

| head | wrong | worse than `main` | better than `main` |
|---|---|---|---|
| `main` | 17,301 | — | — |
| round 0 `59e872a` | 17,328 | 1,902 | 1,875 |
| round 1 `ba36c71` | 14,030 | **6,048** | 9,319 |
| this head | **3,502** | **0** | 13,799 |

All 3,502 remaining are the bare-alias shapes (lead-bare 1,648, trail-bare
1,854), which is #832's class. Chains, restatements and contradictions are
**0 in every noun position**.

The tests now cycle the noun position. `_restatements("cycle")` and
`_contradictions("cycle")` put the noun first, last or in the middle in turn:

| sweep (noun cycled) | prompts | `main` | round 0 | round 1 | this head |
|---|---|---|---|---|---|
| restatements | 18,496 | 2,466 | 2,773 | 2,010 | **0** |
| contradictions | 13,872 | 1,543 | 1,611 | 1,692 | **0** |

The table also gains seven of the reviewer's prompts as rows: the three
label-first + bare-adjective chains and the four restatements before the noun.

| mutant (anchor asserted = 1, bytecode off, `__pycache__` cleared) | result |
|---|---|
| no nested-alias reservation | killed |
| reserve equal-length aliases too | killed |
| no intact-phrase count | killed |
| intact phrases must carry the same value | killed |
| **full tie → number-first (round 1's rule)** | **killed** |
| **intact phrases not claimed into `used`** | **killed** |
| only the alias-first reading | killed |
| only the number-first reading | killed |

`tests/test_archetype_alias_order_812.py`: **70 passed, 4 xfailed** in 30.5 s.
The xfails are #827 ×3 and #832 ×1.

**Filed from this round:**
- **#831** (P0): `_to_number` reads "13/16" as 1 3/16. It is on `main` and
  was not caused by this PR; found by the reviewer.
- **#832**: the full-tie ambiguity.

**Lesson, written to the record rather than kept:** a property sweep only proves
what its generator can produce. All three of mine shared one shape (noun
first), so a regression outside that shape was invisible to all of them at
once. The reviewer's generator varied the shape and found it in minutes.

## Round 3 — claiming intact phrases broke cross-dimensions, and again my sweeps could not see it

🛑 on head `403988b`. Round 2 added the winner's intact phrases to `used`. An
intact alias-first match can run into the first number of an "N x N" cross in
front of the noun ("thickness 12" out of "thickness 12 x 6 in"). The claim then
locked the cross rule out, and the noun rule read the **last** number of the
cross as the width:

```
"a 1/8 in sheet thickness, 1/8 in thickness 12 x 6 in wireway"
  main:     W 12 / H 6 given           403988b:  W 6 given (+ H 6)
"a 22 thickness 14 x 19 x 9 in lighting control panel 22 sheet thickness"
  main:     14 / 19 / 9                403988b:  W 9 given, H and D nominal
```

The reviewer found 275–324 regressions per 60,000 prompts. My sweeps never
combined a cross with a restatement. **This is the same failure as rounds 1 and
2: a sweep proves only what its generator can make.**

### What I did differently this round

Before choosing a fix, I wrote a **randomised, shape-varied fuzzer with a
per-prompt oracle** (`tools/dev/fuzz_prompt_dims.py`, committed). It covers
chains of 1–4 parameters, restatements, contradictions, bare aliases, a
cross before the noun, counts ("3 x 10 ft long"), `x` and `by` used as
separators, fractions, 9 unit spellings, 7 connectors, 11 separators, and the
noun first, last, middle or absent. I measured every candidate fix against
`main` on it, and **each candidate I did not take failed there**:

| candidate | worse than `main` per 20,000 (3 seeds) | why rejected |
|---|---|---|
| intact spans not overlapping any cross | 16–22, then 845–962 once `x` separators and counts were generated | blocked "3 x 10 ft long", "wide x deep" |
| the cross rule ignores intact spans (the reviewer's variant) | same as above on the first fuzzer | leaves the binder free to take a cross's number |
| no alias match may overlap any cross (binder too) | 845–962 | "a 3 x 10 ft long cable tray" lost its length |
| alias-first match opening a cross (any unit) | 196–244 | "thickness = 12.5 inches x 9 feet long" lost the thickness |
| **alias-first match whose UNITLESS number opens a cross** (taken) | **10–19, all but one bare-alias** | — |

The rule taken is `opens_cross`, applied in both the binder and the intact
count. An alias-first match whose number has **no unit** and is followed by
`x <digit>` is the first element of a cross, not a phrase. With a unit
("thickness 12.5 in x 9 ft long"), the phrase is complete and the `x` is a
separator. Number-first phrases next to an `x` are left alone ("12 in wide x 4
in deep", "3 x 10 ft long", "24 wide x 4 deep").

### Evidence — this exact tree against `main` (`16074b6`, fraction fix included)

| instrument | prompts | `main` wrong | this head wrong | worse than `main` |
|---|---|---|---|---|
| fuzzer, no-`x` shapes, seeds 1–3 | 60,000 | 12,769 | 4,415 | **49, all bare-alias** |
| fuzzer, with `x`/count shapes, seeds 1–3 | 60,000 | 11,668 | 3,437 | **33: 32 bare-alias, 1 contradiction** |
| restatements / every alias pair / chains / contradictions | 62,875 | 8,508 | **0** | **0** |
| placement (noun first/last/middle, bare aliases) | 132,548 | 17,301 | 3,502 | **0** |
| cross + restatement sweep (new, in tests) | 2,684 | 1,170 | **0** | **0** (403988b: 1,342 wrong) |

The one non-bare regression in 120,000 fuzzed prompts is a contradiction inside a
no-separator chain: "…2 in rail flange 31 in flange rung pitch is 30 inches
deep of 16 5/8 in…". That text reads legitimately both ways, and `main`'s
alias-first reading happens to land right. It is reported, not hidden.

**The bare-alias regressions** (81 in 120,000, against 16,585 fewer wrong overall) are
#832's class. A bare alias next to a number is often a legitimate reading:
"sheet thickness 125 mm wide junction box" can mean 125 mm *wide*. They are
counted on #832 instead of being called "wrong on main too", which was round 2's
over-claim.

**Tests** (`tests/test_archetype_alias_order_812.py`, **89 passed, 4 xfailed**):
- the reviewer's four cross prompts;
- count, separator and "W x D" rows;
- two unitless number-first rows (which kill "opens_cross at any rank");
- two rows where intact phrases must not overlap (which kill the reviewer's
  surviving "no overlap check" mutant: it changed 247 of 269,361 prompts, and
  the head is right in the ones checked);
- the new `_crossed()` sweep.

| mutant (anchor asserted = 1, bytecode off) | result |
|---|---|
| no nested-alias reservation / equal-length reservation | killed / killed |
| no intact count / intact must carry the same value / intact not claimed | killed ×3 |
| full tie → number-first / only alias-first / only number-first | killed ×3 |
| `opens_cross` dropped from the binder / from the intact count | killed / killed |
| `opens_cross` ignores the unit / applies to any rank | killed / killed |
| intact loop: no overlap-with-intact check | killed (was surviving) |
| intact loop: no `inside_longer` | **survives: 0 of 269,361 outputs change** |
| intact loop: no `conv > minimum` | **survives: 0 of 269,361 outputs change** |

The two survivors are kept as consistency guards (the intact count accepts
exactly what the binder would). They are recorded as changing no output, and
are not claimed as tested.

**Filed from this round:** **#834** — a comma with no space after it drops
the next number ("24 in wide,4 in deep"). This is most of what `main` and the
head still get wrong together on the fuzzer (1,729 of about 2,000 non-bare
shared failures).

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py` — `_alias_patterns(p, alias_first=...)` returns
  `(length, rank, pattern)` in the requested order; `_alias_re` (new, shared);
  `resolve_prompt` reserves every alias occurrence against shorter aliases,
  binds under both orders, keeps (bindings, intact phrases, then alias-first),
  and claims the winner's intact phrases into `used`; `opens_cross` keeps a
  unitless alias-first number that opens an "N x N" cross out of both.
- `plugin/lib/src/rvt/famgen/archetypes.py` — mirror.
- `tests/test_archetype_alias_order_812.py` — new: a 30-row table (value **and**
  provenance, incl. restated nested aliases, label-first chains followed by a
  bare adjective, restatements before the noun), no-stray-`given`, quoted
  source words, the mechanism, both chain witnesses, the geometry end to end,
  property sweeps (chains 16,344; restatements 18,496 and contradictions 13,872,
  each noun-first and noun-cycled) with per-archetype floors, three strict
  xfails for #827 and one for #832.
- `tests/ci_shard.d/812-alias-order.txt` — new.
- `docs/inbox/prompt-archetypes.d/816-lighting-control-panel.md` — repair only
  (round 0: the `relay panel` shield and `BRANCH STATE`; round 1: the round tag).
- this fragment.

- `tools/dev/fuzz_prompt_dims.py` — new: the shape-varied fuzzer with a
  per-prompt oracle and `--compare` (dev instrument, not mirrored into the plugin).

**Gates (round 3)**: 89 passed / 4 xfailed; 13/15 mutants killed (the two
survivors change 0 of 269,361 outputs); archetype, taxonomy, spec-sheet and
fraction suites 689 passed / 4 xfailed; `sync_plugin.py --check` in sync.
Full suite **not** run; `session_ci.sh` runs the shard on the head.

**Shipped vs staged**: shipped.
