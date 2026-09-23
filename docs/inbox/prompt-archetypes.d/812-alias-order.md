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
dimensions a home.** On a tie it keeps `main`'s alias-first reading.

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

## Evidence

| mutant (anchor asserted from a script) | dies in |
|---|---|
| always alias-first (`main`'s behaviour) | 9 |
| always number-first (my first fix) | 3 |
| both passes alias-first (second pass inert) | 9 |
| tie-break flipped (`>` → `>=`) | **survives** — inert on all 5,488 prompts |

The surviving mutant is recorded, not hidden. Across every chain I can generate,
the two readings never tie with different values in the alias pass, so the
tie-break is not reachable. It stays `>` so that a future tie keeps `main`'s
reading.

`tests/test_archetype_alias_order_812.py`: **39 passed, 3 xfailed**. The property
sweep takes 1.4 s. The three strict xfails are the `W x D`-after-the-noun gap,
split out as **#827** — honest `nominal`, so lower severity.

## Record repair carried from #821 (round-3 nits, same stream)

`816-lighting-control-panel.md` said the kept `relay panel` alias shields "this
one prompt". Round 3 reproduced that it shields at least two: "a protective
relay panel" also builds an Eaton PRL2X panelboard with the alias removed (added
to #825). Its `BRANCH STATE` also listed round-0 gates and omitted
`PERMUTATION-MATRIX.md`. Both corrected in that fragment by this PR, as #821's
merge comment committed to.

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py` — `_alias_patterns(p, alias_first=...)` returns
  `(length, rank, pattern)` in the requested order; `resolve_prompt` binds under
  both orders and keeps the reading with more bindings.
- `plugin/lib/src/rvt/famgen/archetypes.py` — mirror.
- `tests/test_archetype_alias_order_812.py` — new: a 19-row table (value **and**
  provenance), no-stray-`given`, quoted source words, the mechanism, both chain
  witnesses, the geometry end to end, the 5,488-prompt property, and three strict
  xfails for #827.
- `tests/ci_shard.d/812-alias-order.txt` — new.
- `docs/inbox/prompt-archetypes.d/816-lighting-control-panel.md` — repair only.
- this fragment.

**Gates**: 39 passed / 3 xfailed; archetype and lighting-control-panel suites
green; `sync_plugin.py --check` in sync. Full suite **not** run.

**Shipped vs staged**: shipped.
