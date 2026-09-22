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

## The first fix was incomplete, on the very lane it cited

#808's independent review found three blocking gaps **after** four mutants
and a green CI had already said the change was done. All three were live on
the IFC assembly lane, which this record had named as motivation:

| gap | measured at the first head |
|---|---|
| `length_ft` never enumerated — the AXIAL and dominant dimension of the `cylinder_x`/`cylinder_y` shapes `assembly_parts` emits | `cylinder_x length_ft=1e12` → **BUILT, 93 elements** |
| a `polygon` ring never checked — a polygon's size lives in its vertices, not a named scalar | `vertices` spanning 1e12 → **BUILT, 95 elements** |
| `_make_generic_multipart`'s own bounding box — named in #806 DONE 1, given no check at all | relied entirely on per-part checks |

End to end, with the reviewer's measured fit: a 1 in conduit 40 m long read
with a metre/millimetre mix-up (×1000) fits `cylinder_x length_ft=131200
radius_ft=41.7` and **built 93 elements — a 24.8-mile conduit** with
`width_in` 1,574,400 stamped `given source='ifc body'`. Exactly the scenario
this record used to justify the work, still shipping.

**The fix is now structural rather than another list of fields.** The
assembly's own bounding box is checked, which catches the space instead of
the instances — including a case neither the reviewer nor I had written a
repro for: *two perfectly ordinary 1 ft boxes a billion feet apart*, where
every per-part check passes and no enumeration of part fields could ever
catch it. The per-part checks stay as defence in depth, because they name the
offending field more precisely than a bounding box can.

This is the same lesson as #801's host-axis sweep, learned again one PR
later: **enumerating the instances loses to bounding the space**, and a green
mutation table over the instances you thought of says nothing about the ones
you did not.

Three smaller gaps from the same review, each real:

- **`NaN` bypassed both ends.** Every comparison with NaN is False, so it
  passed `<= 0` *and* `> MAX_BODY_FT` and died deeper as `ValueError:
  extrusions here are extrude-DOWN: start > end` — no field name, not even a
  `FactoryError`. `inf` was already refused correctly.
- **The boundary was untested.** Flipping `>` to `>=` left all eleven
  original tests green, because none of them sat on it.
- **The constant's VALUE was unpinned.** Mutating `MAX_BODY_FT` to
  `105_600_000.0` — a 20,000-mile bound, i.e. the guard effectively off —
  also left every test green. Now pinned as an order-of-magnitude range, so
  re-tuning stays possible and silently disabling does not.

## Evidence

Baseline **27 passed**, and the whole table below was re-measured at this
head after round 3 caught three rows that had been carried forward and one
sentence claiming — falsely — that they had not been.

That sentence is the finding worth keeping: it was an assertion about my own
rigour, printed directly above the numbers it was wrong about. The rows said
`remove the NaN guard | 1`, `loosen MAX_BODY_FT 1000x | 2` and
`remove the assembly bbox checks | 1 (the billion-feet-apart case)`; measured,
they are 3–4, 6 and 3, and *the billion-feet-apart case no longer exists* —
round 2 replaced it with the ±53,000 ft parametrization. A stale row is a
small thing; a stale row under a claim of freshness is the thing this record
keeps having to document.

| mutant | dies in |
|---|---|
| remove the constructor bound | 6 tests |
| bound height only, not width/depth | 2 tests (width, depth) |
| lane stops citing the row | 1 test (the row-citation case) |
| the two bounds drift apart | 1 test (the shared-bound case) |
| remove all three assembly bbox checks | 3 (the x / y / z parametrization) |
| drop `length_ft` from the enumerated fields | 1 test (the conduit case) |
| remove the polygon ring guard | 1 test (the profile case) |
| `>` → `>=` at the boundary | 1 test (the exactly-at-bound case) |
| loosen `MAX_BODY_FT` 1000× (i.e. the guard effectively off) | 6 |
| drop `v != v` from the finiteness guard | 3 |

One process note on that table: the first attempt at the bbox row **did not
apply** — shell quoting mangled the anchor, the mutation count came back 0,
and the run reported "19 passed". That is a non-run, not a survival, and
recording it as evidence would have been a fourth instance of the pattern
#801 documents. Re-run from a script file with an assert on the anchor, it
dies correctly.

 Note the lane-citation mutant does **not** break delivery —
the factory refusal plus the archetype fall-through still ship a file. That is
defence in depth working, not a gap in the test.

Gates: 61 test files naming `famgen.factory` / `famspec_from_sheet` /
`specsheet` / `assembly_parts` → 1651 passed, 126 skipped, plus one failure that is **pre-existing
on `main`** (`test_famdoc_scan_fp.py`, reproduced from a clean `git archive`
export and filed as **#807**, which also covers why it was invisible: that file
is not in the CI shard).

## Round 2 found the bound leaking through the fields NEXT to the ones it fixed

Round 1 closed `length_ft`, the polygon ring and the assembly bbox. Round 2
then found four more, and the pattern is worth naming: **each one was a field
adjacent to a field I had just guarded.**

| gap | before | why it slipped |
|---|---|---|
| `center=(nan, 0)` | BUILT, type row `Width = -inf ft`, VALID 225,280 bytes | `min`/`max` SKIP NaN rather than propagating it, so `x0=+inf, x1=-inf` and `W=-inf` — which is not `> MAX_BODY_FT` |
| `base_z_ft = nan` / `inf` | bare `ValueError: extrusions here are extrude-DOWN` | never passed through the checker at all |
| a 1 ft box at `center=(1e9, 0)` | BUILT, VALID, type row honestly `Width = 1.000 ft` | EXTENT was bounded; PLACEMENT was not |
| only the X axis of the bbox pinned | deleting the depth and height lines left 19/19 green | the test varied one axis |

`center=(nan,0)` is #806's exact symptom — a VALID file carrying an absurd
dimension — one field over from where it had just been fixed. The checker now
rejects any non-finite value, and `base_z_ft` / `center` go through it like
every other field.

**Two masking effects the first attempt at these tests hid**, both found by
mutating rather than reading:

- The new origin-distance guard *masked* the bbox depth/height checks:
  deleting either left the suite green, because a part at `center=(0,1e9)`
  trips both. The cases now put the extent past the bound while keeping every
  coordinate inside it (±53,000 ft against a 105,600 ft bound), so only the
  bbox check can catch them.
- The per-part `center` check *masked* the assembly origin check for the same
  reason. The pinning case is now a 2 ft polygon ring whose vertices sit
  1,000,000 ft out: profile width 2 ft, `center` absent, bbox 2 ft across —
  every per-part field passes and only the assembly-level distance guard
  sees it. (1e6 and not 1e9: at 1e9 the `+2` is lost to float precision and
  the ring degenerates into `ValueError: profile vertices are collinear` long
  before the guard is reached.)

## Where hard rule 1 actually stands on this change

The PR body originally carried a blanket "output always delivered — the
archetype lane stands in". **That is true on the spec-sheet lane and false on
the `ifc → rfa` assembly lane**, and the body becomes the squash message.
Measured, by rewriting one unit line in a real fixture to `.MEGA.,.METRE.`:

```
ok: False
files: ['assembly_parts', 'product_facts']      <- no 'rfa' key
status: FAILED (famspec->rfa: part 'box': height_ft is 748,031.50 ft (141.7 miles) …)
```

`_assembly_rfa` **is** the fall-through for that route, so when it refuses
there is no further lane to stand in. This is consistent with the
pre-existing "no measurable solid → FAILED, no file" path rather than new
withholding, and the user moves from *a wrong 141-mile file* to *no file plus
a named reason* — which is the better outcome. But it is a real boundary
judgement about hard rule 1 and it is recorded as one, not asserted away with
a checkbox.

## No false refusals, on every tracked IFC in the repo

The placement checks added in round 2 are the most likely source of a false
refusal, so the sweep is over **every tracked `.ifc`**, not just `inputs/`:

```
read_assembly -> to_parts -> make_generic_model
built=25  refused=0  skipped=9 (AssemblyError: no measurable solid -- the documented path)
largest legitimate overall dimension: 224.57 ft (rme_QUARANTINED.ifc)
margin: 470x
```

An earlier draft quoted **36.28 ft / 2911x**, which is true only of the
20-fixture `inputs/` set and flattering because of it. The wider set is the
honest denominator, and 470x is still three orders of margin.

The distance-from-origin check is unreachable from the product lane in any
case: `router.py` calls `read_assembly` with `recentre=True`, and after
recentring the largest `|coord|` across all fixtures is 112.29 ft (174.15 ft
before). It guards direct callers of the constructor, not the route.

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

- `src/rvt/famgen/factory.py` — `MAX_BODY_FT`; `_check_body_size` (upper
  bound + a non-finite guard covering NaN and ±inf); the single-prism
  height/width/depth checks; the per-part checks including `length_ft`, the
  polygon ring, `base_z_ft` and `center`; and the assembly-level bounding-box
  and distance-from-origin checks
- `src/rvt/specsheet/famspec_from_sheet.py` — `_max_body_ft()` and the
  row-citing refusal
- `tests/test_famgen_size_bound_806.py` (new),
  `tests/ci_shard.d/806-size-bound.txt`

Gates: on the PR's CI comment, pinned to the head SHA.

Staged, not shipped: nothing.
