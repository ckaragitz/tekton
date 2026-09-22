# generated-size-bound — a generated body cannot be absurdly large

Charter: **#806**, found by the standing test/debug loop (#805) hunting
adversarial spec sheets. `Refs #805`.

## What was wrong

The generic-model constructors bounded dimensions at `<= 0` and nothing else.
So a spec-sheet row reading `999999999999 in` produced:

```
height_in fact: {'value': 999999999999.0, 'provenance': 'fact',
                 'source': 'spec sheet: adv_huge-int.pdf'}
kwargs: height_ft = 83333333333.25        (~15.8 million miles)
plan.refused: []                           <- no caveat either
BUILT: 105 elements
WROTE 229376 bytes | validator: VALID 0 errors
```

**Every gate we had passed it**, and the number was stamped `fact` and cited
to the user's own document — which is worse than an unlabelled guess, because
the citation is what tells a reader to trust it.

It was an oversight rather than a decision: the catalog constructors in the
same file already bound their inputs by name (*"exceeds the tabulated box"*,
*"exceeds the member's maximum"*), and someone clearly thought about
degenerate sizes and stopped at zero. `generic_model` — the one lane that
takes arbitrary caller input — was the one without a ceiling.

**Not sheet-specific.** Reproduced by calling the constructor directly, so it
reached the IFC assembly lane (where a metre/millimetre mix-up is a 1000×
error and common in real files) and any `generic_model` famspec too.

## What the bound is, and what it is not

`MAX_BODY_FT = 105_600.0` (~20 miles) is a **sanity bound, not a mined format
law**, and the distinction is stated in the constant's own docstring because
it is the kind of thing that gets quoted later as if it were certified:

- `rvt.validate` has no magnitude rule, `docs/writer/` records no extent
  limit, and nothing here has been checked against Autodesk's reader
  (hard rule 4).
- The number is Revit's widely-documented ~20-mile working extent, cited as a
  **floor on absurdity** rather than as a certified limit. A body bigger than
  this is a misparsed row, a metre/millimetre mix-up or a typo far more often
  than a product anyone makes.

The refusal names the field, the value, the bound **and** the miles, because
"too large" without the numbers leaves the caller guessing which of their
three inputs was wrong.

## One bound, two checkers

The sheet lane refuses the row *itself* so the caveat can cite page and row —
`height_in: '999999999999 in' is past the sanity bound … Stated at
adv_huge-int.pdf p1 r3` — rather than only reporting the converted feet, which
the user would have to map back to their own document.

That checker **imports** `MAX_BODY_FT` rather than restating it. Two copies of
a number like this drift silently: the lane would refuse at one size and the
constructor at another, with the caveat quoting whichever fired.
`test_the_lane_and_the_factory_share_ONE_bound` pins it.

## Hard rule 1 holds

The route still delivers. An absurd sheet falls through to the archetype lane
and returns a nominal family with the refusal as its first caveat:

```
ok: True | rfa delivered: True
THE SHEET DID NOT SIZE THIS FAMILY: height_in: '999999999999 in' is past the
sanity bound for a generated body …
```

Worth noting that this fall-through was built in #798 for a different trigger
(a sheet short of a dimension) and caught this one for free. Structural fixes
pay twice; trigger-specific ones do not.

## Evidence

| mutant | dies in |
|---|---|
| remove the constructor bound | 4 tests (all three fields + the multipart path) |
| bound height only, not width/depth | 2 tests (width, depth) |
| lane stops citing the row | 1 test (the row-citation case) |
| the two bounds drift apart | 1 test (the shared-bound case) |

Baseline 11 passed. Note the lane-citation mutant does **not** break delivery —
the factory refusal plus the archetype fall-through still ship a file. That is
defence in depth working, not a gap in the test.

Gates: 56 test files naming `famgen.factory` / `famspec_from_sheet` /
`specsheet` → 1557 passed, 126 skipped, plus one failure that is **pre-existing
on `main`** (`test_famdoc_scan_fp.py`, reproduced from a clean `git archive`
export and filed as **#807**, which also covers why it was invisible: that file
is not in the CI shard).

## Open questions

- **Should `rvt.validate` grow a magnitude rule?** Then a file arriving from
  anywhere is caught, not just one we authored this run. Deliberately out of
  scope here: the validator is a shared surface and a new rule needs its own
  evidence that it never fires on the three certified bases.
- The bound is uniform across categories. A conduit run and a switchboard have
  very different plausible maxima, and a per-category bound would catch more —
  but it needs sourced numbers per category, which we do not have.

## BRANCH STATE

Branch `cam/806-size-bound`, `Closes #806`, `Refs #805`.

Files written:

- `src/rvt/famgen/factory.py` — `MAX_BODY_FT`, `_check_body_size`, and the
  three call sites (single-prism height/width/depth, and the parts builder)
- `src/rvt/specsheet/famspec_from_sheet.py` — `_max_body_ft()` and the
  row-citing refusal
- `tests/test_famgen_size_bound_806.py` (new),
  `tests/ci_shard.d/806-size-bound.txt`

Gates: on the PR's CI comment, pinned to the head SHA.

Staged, not shipped: nothing.
