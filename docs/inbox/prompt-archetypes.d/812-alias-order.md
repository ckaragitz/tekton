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

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py` — `_alias_patterns(p, alias_first=...)` returns
  `(length, rank, pattern)` in the requested order; `_alias_re` (new, shared);
  `resolve_prompt` reserves every alias occurrence against shorter aliases,
  binds under both orders, keeps (bindings, intact phrases, then alias-first),
  and claims the winner's intact phrases into `used`.
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

**Gates (round 2)**: 70 passed / 4 xfailed; 8/8 mutants killed; archetype,
taxonomy and lighting-control-panel suites green; `sync_plugin.py --check` in
sync. Full suite **not** run; `session_ci.sh` runs the shard on the head.

**Shipped vs staged**: shipped.
