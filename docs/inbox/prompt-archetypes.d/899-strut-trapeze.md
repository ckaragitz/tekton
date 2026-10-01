# 899 — a prompt for a strut trapeze builds the whole trapeze

Stream: **prompt-archetypes** (fragment; index `../prompt-archetypes.md`).
Issue **#899** (P1, from steer #898), branch `claude/pull-latest-main-1cmo56`.

## The gap

The owner asked for "a 2 tier slotted trapeze with threaded rod with all
parameters needed to adjust the family". On `main` (`be0a350`):

```
route run --prompt "a 2 tier slotted strut trapeze hanger with threaded rod" --output rfa
  -> Strut_Channel_1.625_in_10_ft.rfa: ONE 10 ft channel, 5 forms
     "Ignored words: tier, slotted, trapeze, hanger, threaded, rod"
  -> family parameters: Depth, Finish, Height, Material, Weight, Width
```

## What was built

- **`strut_trapeze` archetype** (`src/rvt/famgen/archetypes.py`). It is made of:
  - N tiers of 1-5/8 in channel, open side up. The default is 2 tiers.
  - Each tier is the existing `_strut_channel` section with its slots really
    absent.
  - Two vertical threaded rods, run full length.
  - A square washer and a hex nut below each tier's back, and the same on its
    lips, at each rod. The nut is a hexagonal prism: 1.5 d across the flats and
    0.875 d tall.
  - The insertion point is the underside of the bottom tier, midway between the
    rods.
  - At the defaults it is 58 parts.
- **Nominal sizes** (all overridable; a stated value is `given`):
  - strut length 30 in, with rods 3 in in from each end (24 in rod spacing);
  - 12 in tier spacing;
  - 3/8 in rod;
  - 24 in of rod above the top tier and a 1 in tail below the bottom nut;
  - slots 1-1/8 in on 2 in centres;
  - 1-5/8 in square washers, 1/4 in thick.
- **Refused by name, never built wrong:**
  - fewer than 1 or more than 6 tiers, or a fractional tier count;
  - a tier spacing that does not clear one channel plus its nuts and washers;
  - an inset that puts the washer past the strut end;
  - rods with no room between them;
  - a rod wider than the channel.
- **Family parameters with values** (new `Archetype.family_params`; `make_archetype`
  merges them into `numeric_params`). There are 18:
  - the count: Number of Tiers (ParamDefInt, stored as an int);
  - the layout: Strut Length, Rod Spacing, Rod Inset, Tier Spacing;
  - the rod: Rod Diameter, Rod Length, Rod Above Top Tier, Rod Below Bottom Nut;
  - the channel: Strut Height, Strut Width, Strut Thickness, Slot Length, Slot
    Spacing;
  - the hardware: Washer Size, Washer Thickness, Nut Across Flats;
  - Overall Height.

  The derived values come from the same `_trapeze_geometry` the builder uses, so
  the parameters and the geometry cannot disagree.
- **Family name:** `Archetype.name_bits` gives "Strut Trapeze 30 in 2 Tier".
- **A count parameter reads a bare number** (`_convert`), so "2 tier" binds. Before
  this, a `count` unit fell through to `None`; no earlier archetype had a count.
- **`_caller_param_row`** stores an `integer` spec as an int. Every caller before
  this one passed a float.
- **Taxonomy:** a `strut_trapeze` kind, archetype lane. The "trapeze strut"
  alias moves to it from `strut_channel`.
- **Aliases left out on purpose:**
  - bare `rod` clashed with `rod inset` and `rod above`;
  - `dia rod` clashed with `rod drop`;
  - `between tiers` clashed with `slot spacing`;
  - bare `washer` clashed with `washer thickness`.

  The #812 sweep, which binds every alias chain across every archetype, found all
  of these: first 214 mis-bound chains, then 163, then 0. Use "3/8 in threaded
  rod" and "18 in tier spacing".

## Evidence

- The six prompt phrasings in the tests resolve to the trapeze with the right
  `given` values. "a 10 ft strut channel" is still a strut channel.
- **Produced files:** "a 2 tier slotted trapeze with threaded rod", built for 2026
  and for 2025.
  - Each is 58 forms with 24 parameters.
  - `rvt_validate`: ok, 0 errors. Family mode: VALID, 0 errors, 0 warnings.
  - Provenance: PROVENANCE-CLEAN.
  - `family_anatomy profile`: 58 solids; parameters 24 (21 ParamDefValue, 1
    ParamDefInt, 2 ParamDefString).
- **Bare unzip** of `tekton-plugin.zip` with system python 3.11: `go route.py run
  --prompt "a 2 tier slotted trapeze with threaded rod" --output rfa` gives
  status `works`, and the `.rfa` is delivered.

## Honest boundary

The parameters carry values. Editing Strut Length or Tier Spacing in Revit
does **not** move the solids, because the parametric drive has no desktop
verdict (#372; #787 is the next probe). A different size is a re-generation, and
the archetype's `limits` say so in every report. Not modelled:
- the threads, the nut chamfers and the forming radii;
- the rod holes (the rod passes through the back);
- the beam clamp at the rod top.

No desktop or viewer verdict exists for this family (hard rule 4).

## Open

- `plugin/skills/tekton-author/SKILL.md` lists the generated products. It is a hot
  file, so `strut_trapeze` is left for a `hot-file` PR. The line to add is
  "`strut_trapeze` (tiers of slotted strut on two threaded rods)".
- Once a geometry drive has a desktop verdict, the trapeze is the natural second
  customer: Tier Spacing and Strut Length are both single-axis drives.

## Review round 1 (head `b03273b`, 🛑) — what changed

The independent reviewer's findings, each fixed and tested:

- **A bare rod size now binds.** "1/2 rod", "5/8 in rod" and `5/8" rod` all bound
  nothing, and the route delivered a 3/8 in rod with no caveat.
  - The `rod` alias is back.
  - A new `Param.not_before` lets an alias refuse a match when the next word belongs
    to another dimension ("rod spacing", "rod inset", "rod above", "rod drop" …).
    It is a negative lookahead in `_alias_patterns`, available to any parameter.
  - The bare aliases that made the text truly ambiguous (`inset`, `drop`,
    `above top tier`, `below bottom nut`) are gone.
- **"1-5/8" names the channel.**
  - A count now takes a whole number only, so "2 tier 1-5/8 strut" no longer reads
    1.625 tiers.
  - `wide` / `width` are off strut length.
  - A new `Archetype.noun_leads` makes a measurement right before "strut" /
    "channel" / "unistrut" in the product name bind the channel height. "a 13/16 in
    strut trapeze" is a 13/16 in tall channel; its width stays 1-5/8 in, as on real
    shallow strut.
  - "a 1-5/8 in wide strut trapeze" now delivers a file. On the old head it
    returned `ok=False` with no file.
- **Rod spacing is an input.** A new `Archetype.settle` hook keeps strut length =
  rod spacing + 2 x inset, whichever two the caller states.
  - A derived value is `given` (the caller's numbers decided it), with the reason
    quoted, and is listed in `Resolved.derived`.
  - An override re-derives instead of keeping a stale derivation.
  - The builder refuses three that disagree.
  - The #812 sweep's `_stray` exempts a derived key only when `settle`, recomputed
    from the prompt's own numbers, gives that exact value. The same treatment
    `follows` already had, and checked rather than waved through.
- **Nits:**
  - The rod-spacing guard is now `max(nut, washer)`.
  - `Overall Height` (a copy of `Rod Length`) is dropped, leaving 17 trapeze
    parameters.

**Gates:**
- trapeze 37 passed;
- the #812 suite, including the 54,336-prompt restatement sweep: 238 passed /
  5 xfailed;
- neighbouring suites plus plugin bootstrap/coldstart: 629 passed / 5 skipped;
- plugin in sync, validate PASS.

Rebuilt 2026 and 2025 `.rfa`: 0 errors, PROVENANCE-CLEAN, 23 parameters.

**Desktop:** the owner opened the round-0 file. Every parameter showed with the
right value, and none drove the geometry (steer #901). The drive is #787's.

## Review round 2 (head `40100d9`, 🛑) — what changed

- **A stated size is never overwritten by a following number.** The new
  `Param.maximum` is the largest value a *prompt* may bind; a famspec override
  is not limited by it.
  - "1/2 in rod 24 in apart" used to read the 24 alias-first as a 24 in rod. Now
    the rod is bounded at 1.5 in, so that reading is refused, the 1/2 binds, and
    "24 in apart" is the rod spacing. The same holds for "… on center" and
    "… 2 ft above".
  - The other trapeze dimensions carry ranges too: strut 6 to 240 in, tiers up
    to 6, and so on.
  - `tiers` minimum went from 1 to 0, because `conv <= minimum` had silently
    refused "a 1 tier trapeze".
- **Any modifier of the noun may lead.** In "1-5/8 in slotted strut trapeze" the
  word "strut" is not the first word after the unit; the rule now scans the whole
  modifier run.
  - "1-5/8 in slotted trapeze" no longer binds a 1.625 in strut, because strut
    length is at least 6 in. It builds at the nominal size.
- **Round 1's `not_before` was removed.** Every phrase it guarded ("rod spacing",
  "rod inset", "rod above", "rod drop", "rod tail", "rod from end") is a longer
  alias of another dimension and claims its text first. The guard then broke
  "rod diameter centers 13 in".
  - Bare `centers` / `centres` are not spacing aliases, because "rod centers"
    would be ambiguous. Use "apart" or "on center".
- **Sweep (#812):**
  - New `_n(p, n)` gives a bounded parameter a distinct in-range stand-in for
    7/13/19. An unbounded parameter (every archetype before this PR) gets exactly
    the old numbers.
  - `_sweep` now also fails a stated key that comes back as settle-derived, as
    the review asked.
- **The status line** counts derived values separately: "2 dimension(s) from the
  prompt, 1 derived from them, …".
- **Gates:**
  - trapeze 49 passed;
  - the #812 suite: 251 passed / 5 xfailed (131,728 chains, the restatement and
    contradiction sweeps, the cross sweep);
  - neighbouring suites plus route and plugin suites: 811 passed / 10 skipped;
  - plugin in sync, validate PASS.

## Review round 3 (head `4f09b6a`, 🛑) — what changed

- **A trapeze length before "strut" / "channel" / "unistrut" is the trapeze's
  length again.**
  - The channel's `height_in` / `width_in` now carry `maximum` 4 in.
  - A noun-lead redirects a value only when it fits that range; otherwise the
    value falls back to the primary.
  - "a 36 in strut trapeze", "a 3 ft strut trapeze", "a 24 in unistrut trapeze"
    and "a 36 in slotted strut trapeze" each give a 36 or 24 in strut and deliver.
    Round 2 bound a 36 in channel, failed the build and delivered no file.
- **Bare `apart` / `on center(s)` are no longer rod-spacing aliases.** "tiers 12 in
  apart" had captured the rod spacing and shrunk the strut. It now binds nothing:
  honest nominal, with tiers 12 in apart by default.
- **An out-of-range number is reported, never silently dropped.**
  `Resolved.out_of_range` lists every phrase stating a bounded dimension that
  stayed nominal, and the route adds a caveat: `NOT USED: "7 tier" -- a Number of
  Tiers of that size is outside the range … (up to 6)`.
- **The restatement scan checks `maximum` too**, consistent with the bind sites.
- **The #812 cross sweep** gives the channel's 12 x 6 in cross the same in-range
  stand-ins through `_n`. Unbounded archetypes keep 12 x 6 exactly.
- **Rebased onto `c56b7cf`** (#902).
- **Gates:**
  - trapeze 61 passed;
  - the #812 suite: 251 passed / 5 xfailed;
  - all related suites plus route and router, plugin and bootstrap suites:
    1076 passed / 10 skipped / 5 xfailed;
  - plugin in sync, validate PASS.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py`: `Archetype.family_params` / `name_bits`, the
  `_hex_nut` / `_trapeze_geometry` / `_strut_trapeze` / `_trapeze_params`
  functions, the `strut_trapeze` entry, and `_convert` for counts.
- `src/rvt/famgen/factory.py`: `make_archetype` authors `family_params`;
  `_caller_param_row` stores an int for integers.
- `src/rvt/famgen/taxonomy.py`: the `strut_trapeze` kind.
- `plugin/lib/…`: mirrors (via `sync_plugin.py`).
- `tests/test_strut_trapeze_899.py`: new, 61 tests after review round 3.
- `src/rvt/frontdoor/router.py`: the archetype status line counts derived values separately.
- `tests/test_archetype_alias_order_812.py`: `_stray` exempts a verified `settle` derivation; `_sweep` rejects a stated key refilled by settle; `_n` gives bounded params in-range numbers.
- `tests/ci_shard.d/899-strut-trapeze.txt`: new.
- this fragment.

**Gates**
- `test_strut_trapeze_899.py`: 20 passed.
- archetype, alias-order (#812 sweep), lighting-control-panel, taxonomy ×4,
  fraction, famgen_factory, family_anatomy and param_profile suites: 788 passed,
  5 skipped, 5 xfailed.
- `sync_plugin.py --check`: in sync. `validate_plugin.py`: PASS. Portable paths:
  ok.
- Full suite not run; `session_ci.sh` runs the shard.

**Shipped vs staged:** shipped as a generated family lane. No viewer batch was
staged.
