# eng #637 — a member SUNK into a block never vanishes: crossing slice rings are one outline before anything is nested (2026-08-11)

*Fragment of the `ifc-assembly-rfa` stream (index: `docs/inbox/ifc-assembly-rfa.md`, left untouched),
written by engineer session eng #637 on branch `cam/637-crossing-rings` from `main` @ 6f33fb7.
One PR, one voice; nobody else appends here (docs/inbox/README.md, #636).*

Refs #637 (this task); #609 / #621 / #635 (the corner- and face-CONTACT laws this must not disturb),
#634 (flush contact, still an honest prism), #613 (the by-construction accounting idea), #583 round 2
(why there is no volume backstop here either). PG1.

## The defect, reproduced on `main` @ 6f33fb7 first

When a small member is genuinely **sunk** into a bigger one — the two shells interpenetrate — a
horizontal slice through the shared band yields two rings that **cross**. `ring_nesting` asks "is ring
*i* inside ring *j*?" from one interior probe of *i* standing clear of *j* (`_probe_clear_of`, #621);
for a crossing pair that question has no single answer: the probe beside the lug's *buried* long edge
says "inside the block" (depth 1 → a hole → dropped, `holes_filled 1`), the probe beside its *free*
long edge says "outside" (depth 0 → a solid). Which edge is drawn first is decided by where the stitch
started, i.e. by triangle order. In the hole case the lug is gone and the block ring alone is authored
in that band: authored ÷ mesh = 0.9931 (lug 0.7 % of the body), inside `_conserves`' 2 % slack →
accepted, **no `kept_prism`, no caveat**; the route says `slab decomposition improved Pair (3 solids,
fill 0.88 -> 1.01)`, the `1.01` being the only tell — the #621 signature moved from a shared face to a
buried one. A second failure hides in the same rows: when the *block's* probe (midpoint of its 4 m edge)
falls inside the stud ring, the BLOCK reads as the hole, 12 % of the body goes, `_conserves` catches it
and the whole body ships as one prism "dropped material" — honest, but a 1×4×4 m slab + stud delivered
as a 1.5×4×4 box for a nesting accident.

Reproduction (`RVT_STEPLITE_FORCE=1`, fresh cloud clone, one script run against both engines; the
#621 face-pair generator with the lug pushed `sink` metres INTO the block; judged against the exact
**union** volume = block + lug − sink·(lug face), because the mesh's own divergence volume counts the
buried part twice; 41 seeded triangle orders per cell = the identity order + 40 shuffles):

| set (× yaws {−17°, 5°, 12°, 33°} × 41 orders) | `main` @ 6f33fb7 | this branch |
|---|---|---|
| 2×6×3 block + 0.5×1×0.5 lug on +x, sunk 1 / 2 / 5 cm (492 runs) | **164 silent losses** (4 whole cells 41/41: 1 cm @ −17° and 12°, 5 cm @ 5° and 12°), authored 0.99310·mesh, `holes_filled 1`, parts 3; the other 328 runs parts 4 (block ×3 + lug, the buried part authored TWICE: 1.00014–1.00069 × union) | **0 lost, 0 kept**; 492 × slabs, parts 3 (block / block-with-lug outline / block), `crossings_merged 1`, `holes_filled 0`, authored ÷ union = 1.000000 at every order |
| same lug half-way up the −x face, sunk 1 / 2 / 5 cm (492) | **99 silent losses** (5° @ 1 cm 17/41; 33° @ 2 cm and 5 cm 41/41) | 0 lost, 0 kept; parts 3, identical outline at every order |
| 1×4×4 slab + 0.5 m stud at the base, sunk 1 / 2 / 5 cm (492) | **75 silent losses** (0.99225·mesh) **+ 204 honest-but-needless prisms** (17/41 in every cell: the SLAB read as the hole, "dropped material 854 331 vs 984 007 in3") | 0 lost, 0 kept; 492 × slabs, parts 2 (slab-with-stud outline / slab above) |
| **total 1476 runs** | **338 silent losses + 204 kept prisms + 934 double-authored** | **1476 conserved decompositions, deterministic per body** |
| randomised sunk boxes (seed 637: block ∈ {1..6}³ m, member 0.2–1.5 m, sunk 1 mm … 60 % of its depth into ±x, random y/z, yaws {−17, 5, 12, 33, 45, 0.05, 71}) — 300 configs × 4 orders = 1200 | 45 silent losses + 143 "dropped material" prisms | 0 lost, 0 kept (468 of the runs merge a crossing; the rest are members proud enough that fill ≥ 0.90 kept the single prism on both trees, or sunk < `MIN_EXTENT_FT`) |

(The issue measured 3/36 on one placement; the rate is placement × yaw × order roulette — whole cells
are 41/41.) Sunk by *less* than `MIN_EXTENT_FT` (0.2 / 0.3 mm): 41/41 conserved on both trees — that is
#621's contact law answering, by design (below).

## What was built — the union, checked against the body (territory: the slice → nesting path of `assembly_parts.py` only)

> **Where this landed after four review rounds (read the round sections below for the path):** clean
> crossings — nothing else of the slice inside the pair's common region, the body two shells deep there —
> merge into one outline with `shared = ∣a∩b∣` credited exactly; nested crossings (a bar through a hollow
> member's bore, a rod down it) refuse honestly to the single prism and are #715's to merge. The helper
> set that ships: `_ring_cuts`, `_split_ring`, `_overlay`, `_closed`, `_clip`, `_beside`,
> `_union_of_crossing`, `_first_crossing`, `_merge_crossing_rings`.

**Chosen handling: UNION (the issue's preferred), with the attributed refusal as the fallback inside
it — not refuse-only.** Refuse-only was measured first and rejected: it turns every interpenetration
whose shared volume exceeds the 2 % slack (a bar run through a post, two equal bars crossing, two lugs
in one band) into a single prism where `main` at least delivered overlapping solids in its lucky
orders; and "treat crossing rings as disjoint" (author both, overlapping) was rejected because it
authors the buried material twice by construction and makes the slab lane disagree with the box lane,
which already authors the *union* of overlapping shells at 0° and credits the overlap
(`test_overlapping_shells_are_measured_as_a_union_not_counted_twice`). The union makes the two lanes
one law.

Six private helpers (the sixth added in round 2 below), called from `decompose_slabs` between `slice_loops` and `ring_nesting`; nothing
else in the module moves (`slice_loops`, `_stitch`, `_junction_pairs`, `ring_nesting`,
`_probe_clear_of`, `fit_solid`, `decompose_boxes`, every constant, `EXACT_REL_TOL`, the 2 % slack, the
#652 budgets, the #666 caliper law: byte-intact):

* **`_ring_cuts(a, b)`** — every PROPER crossing of an edge of `a` with an edge of `b` (both segment
  parameters strictly inside (0, 1)); touching at an end or running parallel is not a cut, so a shared
  corner (#609) or an exactly shared edge (#621) yields none. O(n·m) over two small rings, and only for
  pairs whose bounding boxes overlap by more than `MIN_EXTENT_FT` in both axes.
* **`_split_ring(ring, at)`** — the ring's edges as segments, cut at those points, so a crossing is a
  vertex both rings share *exactly* (one computed point, used on both sides).
* **`_union_of_crossing(a, b, cuts, twice)`** — the pieces of either boundary whose midpoint lies
  inside the other ring are interior to the union and dropped; the rest is welded back into rings by
  the *existing* `_stitch` — the union's outline plus any pocket the two enclose (its own ring, nested
  later as the hole it is). Three things are **checked, not assumed**: (1) **depth** — if no dropped
  piece lies `MIN_EXTENT_FT` or more inside the other ring the pair is in CONTACT, not crossing, and
  is returned untouched (`([], 0.0)`) for `ring_nesting` to judge exactly as before; (2) **the body's
  own word** — the deepest point of every dropped run, nudged 1e-7 ft into its own ring, must read
  |winding number| ≥ 1.5 (inside TWO shells) or the merge is refused (`None`): a ring that bounds a
  hole, a shell wound the other way, a piece mis-sided by rounding is never merged away; (3)
  **closure** — the kept pieces must meet exactly two to a vertex, or `None`. Only then is the shared
  area `area(a) + area(b) − area(union)` reported.
* **`_first_crossing(rings, twice)`** — the first bbox-gated pair that really crosses, with its union;
  `()` when none does; `None` when a pair crosses but the union is refused.
* **`_merge_crossing_rings(rings, twice)`** — merge that pair and look again until no pair crosses
  (a merged outline can cross a third ring: two lugs in one band, lugs crossing each other); returns
  `(rings, pairs merged, shared area)` or `None`; bounded by the square of the ring count.

`decompose_slabs` refuses a `None` with its own attributed reason — `slab lane: crossing rings at z =
… ft (sections that cross where the body does not hold two overlapping shells, or do not merge into
closed outlines; not guessed)` → `kept_prism` → the honest single prism, delivered (rule 1) — and
otherwise nests the merged set as before, returning two more numbers: `crossings_merged` and
`overlap_ft3` (shared area × slab height, summed).

**The conservation law compares like with like — the box lane's law, not a new one.** The mesh's
divergence volume counts interpenetrating shells' shared material twice; the union authors it once.
`read_assembly` already accepts the box lane only when `boxes + overlap_ft3` reproduces the mesh; the
slab branch now checks `_conserves(authored + overlap_ft3, mesh)` with the **same 2 % slack**, reports
`fill_after = (mesh − overlap) ÷ authored` (so an honest merge reads 1.00, never the tell-tale 1.01),
and every decomposed record now carries `crossings_merged` (0 for the box lane and for slabs that
merged nothing — a stable shape, like `holes_filled`) plus, when material was shared, the existing
`mesh_overlap_in3` + note (one mechanism for both lanes, the slab wording appended); a model note (`N crossing
section(s) merged (Pair: 1, 610.24 in3 shared): those shells INTERPENETRATE …`) rides `model.notes`,
which the router already relays as a caveat — so `router.py` is untouched and the matrix byte-identical.
Why this is not the backstop #583 round 2 removed, nor the tautology #613 warns about: the credit only
ever *adds* to the authored side (it cannot penalise a taper, a hairline level or a sliver), and it is
granted only for regions the 3D body itself confirmed as double material at merge time — a nesting
mistake produces no credit, so a lost ring is exactly as visible to `_conserves` as it was. When the
credit is not enough (it never was in 2 700+ runs) the refusal says how much of the gap the mesh
counts twice.

**Why `MIN_EXTENT_FT` is the contact/crossing threshold and not a new constant.** `_probe_clear_of`
(#621) distrusts any probe closer than `MIN_EXTENT_FT` to the other ring and moves on to the next
edge; so a lug sunk *less* than that is already read from its free edge → two solids (measured: 0.2 /
0.3 mm sunk → 41/41 conserved on `main`), and a lug sunk *more* than that is exactly where the buried
probe becomes "trustworthy" and the roulette begins (0.5 mm → 41/41 lost on `main`). The merge takes
over at precisely that depth (test: `10 − 2·MIN_EXTENT_FT` merges, `10 − 2e-6` at a hair of an angle
does not), so there is no band where neither law answers and none where both do.

## Evidence

**Reference rows — re-measured IDENTICAL** (one script, both engines, same IFC bytes; parts / lane /
authored ÷ mesh; the diff of the two outputs is empty):

| body | `main` @ 6f33fb7 | this branch |
|---|---|---|
| 900 mm strut 0.0 / 0.1 / 0.2 / 0.5 / 0.8° | boxes ×3 1.000000 / slabs ×3 1.000002 / 1.000006 / 1.000022 / 1.000064 | identical |
| 50 µm-mismatch strut 0° / 12° (hairline) | boxes ×3 1.000000 / slabs ×3 0.999622 | identical |
| 8-band reducer frustum · 12-band cone | slabs ×8 0.999442 · slabs ×12 0.998513 | identical |
| plate + 6 mm² pin 7° · U-channel 4° / 30° · 70-plate rail 10° | slabs ×1 0.999942 (sliver dropped) · slabs ×3 0.999997 / 1.000003 · prism ×1 1.010104 | identical |
| chamfered square 22.5° (#628) · lattice 3³ / 9³ (#623) · flush lug 12° (#634) | prism ×1 1.000001 · boxes ×27 exact / kept prism (work budget, then part budget 81 solids) · kept prism 1.1379 (ambiguous slice) | identical |
| #609 corner pairs, 4 positions × yaws {5, 12, 33, −5, 45, 0.05} × 41 orders = 984 | 984 × slabs ×3, max ∣authored−mesh∣/mesh 1.5e-7, holes 0 | identical (no merge fires: 0 cuts) |
| #621 face pairs, 5 × 41 orders = 205 | 205 × slabs ×3/×4, max off 7.6e-11, holes 0 | identical (cuts exist at µm depth → contact → untouched) |
| #620 fit rows / #628 caliper rows / #626 floor | their modules green | green, `fit_solid` byte-intact |

**Harder interpenetrations** (13 orders each; `main` → branch): bar 3×0.4×0.4 m run THROUGH a 2 m
post @ 12° — kept prism "dropped material" ×13 → **slabs ×3** (post / post-with-two-stubs 12-gon /
post), shared 19 527.6 in³ = 0.3200 m³ = exactly the buried bar; two equal bars crossing @ 20° — 2
overlapping bars → **one plus-shaped outline**, area 2·3·0.4 − 0.16 m² exact; two lugs sunk 2 cm into
opposite faces in one band — 5 parts (both lugs double-authored) → **3 parts, `crossings_merged 2`**;
lug sunk 2 cm with its top flush with the block's top — **13/13 LOST on `main`** → conserved, 2 parts;
lug sunk 2 cm in x and flush in y (µm-collinear edges) → conserved, 3 parts; block + two lugs that
also cross EACH OTHER → 5 parts, `crossings_merged 4`, conserved; a 16-gon boss straddling a plate's
edge → merged, 3 parts; a radial pin sunk into a 32-gon tube's WALL → merged, bore filled as every hole
is. **Refused, attributed, delivered as the prism** (by design): the same pin driven on into the
tube's BORE (the deepest dropped boundary lies in the void: |w| = 1), and a lug shell wound the other
way (|w| = 0 where they overlap; its mesh volume is meaningless anyway) — both `slab lane: crossing
rings at z = …`. Site coordinates: the sunk pair placed at (500, 300), (50 000, 80 000) and UTM-scale
(5e5, 4.8e6) m merges identically (3 parts, authored = union to 1e-7) — the 1e-7 ft nudge is ~30 ulp at
1.6e7 ft. Total decompositions run for this record ≈ 9 000, all on 24–400-triangle bodies (seconds).

**Cost.** The no-crossing path pays one bbox test per ring pair per slice, and `_ring_cuts` only for
pairs whose boxes overlap — inside which an edge pair whose extents miss skips the arithmetic (that is
what keeps nested round rings cheap: a tube's bore in its skin overlaps by bbox at every slab yet no
edge pair's extents meet). Measured best-of-5 `read_assembly`, `main` → branch: sunk lug 1.03 → 1.29
ms (it now merges), #621 face pair 1.04 → 1.21, #609 corner pair 1.05 → 1.25, strut 1.13 → 1.16,
8-band frustum 13.2 → 13.5, 24-band 64-side frustum 121 → 122–132 (noise), lattice 3³ 38 → 39,
lattice 9³ 176 → 178–195 (single runs, noise), 64-gon tube with nested bore ring 9.3 → 10.2 ms (12.4
before the extent gate). The oracle (one `winding_number` per dropped run, i.e. two per merged pair per
slab) is paid only where a crossing was found.

**Layer, and why not deeper (asked in review).** All three contact/crossing defects (#609 corner, #621
face, #637 buried face) are one fact: rings cut from *different* shells are not a planar partition. The
general cure — keep a slice segment only where the body's winding number differs across it — is two
solid-angle sums over every triangle per segment per slab, exactly the #623 blow-up's shape (tens of
seconds on a lattice); detecting the crossing in 2D and asking the body once per dropped run is the
affordable form of the same question, and the docstring says a fourth symptom should buy the general
one. Teaching `ring_nesting` to treat crossers as non-nesting was the rejected "author both" option
above and would still need `_ring_cuts`.

**Router, end to end** (`RVT_STEPLITE_FORCE=1 .venv/bin/python tools/route.py run --ifc X --output rfa
--out D --json`, same IFC bytes, `main`'s engine swapped in by stashing the one file):

```
sunk_1cm_12.ifc  (2x6x3 block + 0.5x1x0.5 lug sunk 1 cm into +x, yaw 12; identity triangle order)
  main:   OK (3-part generic_model .rfa ...) · slab decomposition improved Pair (3 solids, fill 0.88 -> 1.01)
          decomposed: parts 3, slabs 3, holes_filled 1, fill_after 1.0069 · kept_prism [] · part heights 3.360 / 1.640 / 4.843 ft
          (the 1.640 ft lug band is the BLOCK ring alone: the lug is gone, and nothing says so)
  branch: OK (3-part generic_model .rfa ...) · slab decomposition improved Pair (3 solids, fill 0.88 -> 1.00)
          + caveat: 1 crossing section(s) merged (Pair: 1, 305.12 in3 shared): those shells INTERPENETRATE, so each such
            slice was authored as ONE outline (their union), and the shared material the mesh counts twice was credited ...
          decomposed: parts 3, holes_filled 0, crossings_merged 1, mesh_overlap_in3 305.12, fill_after 1.0 · polygon points 8 / 15 / 8
sunk_2cm_m17.ifc (the issue's case, identity order): main OK 4-part (block x3 + lug, buried part authored twice, "1.00")
          -> branch OK 3-part, crossings_merged 1, 610.24 in3 shared, outline 14 points
stud_1cm_12.ifc  (1x4x4 slab + stud at its base): main OK 2-part fill 0.79 -> 1.01, holes_filled 1 (stud LOST)
          -> branch OK 2-part fill 0.79 -> 1.00, crossings_merged 1, 152.56 in3 shared
bar_through_post_12.ifc: main OK 1-part + "kept as a single prism ... slab decomposition dropped material (488189.818 in3
          authored vs 517481.219 in3 in the mesh)" -> branch OK 3-part, crossings_merged 1, 19527.60 in3 shared, no prism caveat
```
All four branch outputs: `tools/rvt_validate.py --family` **VALID (no errors); warnings=0 info=2**;
`tools/make_family.py provenance` **ok: true, findings []**. No certification claimed (rule 4): VALID is
a fact about the files, not about Revit. `tools/route.py matrix`: sha256 `7dae5d40…`, 39 lines, on both
trees — **byte-identical**.

**Tests** — new module `tests/test_ifc_assembly_637.py` (14 tests, ~4 s) + drop-in
`tests/ci_shard.d/637-crossing-rings.txt`; generators imported from `tests/test_ifc_assembly.py`
(`_face_pair`, `_corner_pair`, `_FACE_PAIRS`, `_triangle_orders`, `_strut`, `_strut_mismatch`,
`_frustum`, `_u_channel`, `_box_mesh`, `_prism_mesh`, `_yaw`, …), `_623` (`_lattice`) and `_628`
(`_chamfered`, `_tube`) — none of those files edited. What they pin: proper cuts only (corner / exact
edge / nested / apart → none); the union of two crossing rectangles is the 8-vertex outline of area
100 + 3 − 1 with shared area 1, a plus is one 12-gon, a bar closing a C returns outline + pocket and
the pocket nests as a hole; µm-deep contact at a hair of an angle has cuts yet is NOT merged and
`ring_nesting` still says `[0, 0]`, while `2·MIN_EXTENT_FT` deep IS merged; a merge the body does not
back (`twice` false) and kept pieces that do not close (exactly collinear flush edge) are `None`;
several rings crossing one are all merged; `decompose_slabs` on the sunk pair reports
`crossings_merged 1`, `overlap_ft3` = the buried volume, `volume_ft3` = the union, band area − block
area = exactly the proud part of the lug; **the five sunk rows over 101 + 4×41 = 265 seeded orders ⇒
conserved-or-kept, and in fact slabs, merged, `holes_filled 0`, `fill_after ≤ 1`, authored = union to
1e-5, 3 (or 2) parts every run**; the through-bar / plus / two-lug / mutual-lug bodies decompose and
conserve; the boss and the tube-wall pin merge; the flipped shell and the pin-into-bore refuse with the
attributed reason through both `decompose_slabs(refusal=…)` and `read_assembly`; site coordinates; the
router delivers the sunk pair `OK (3-part …)` with the merge caveat and no prism caveat; the 14
reference rows and the 984 + 205 contact runs read exactly as on `main`. Against `main`'s engine the
module fails by `AttributeError` on the helpers and by behaviour on every sunk row.

## Round 2 (after the tech lead's review of ac6800e): the credit is net of what a shell's own hole holds

The independent review reproduced everything above and sent back one blocking point, taken as asked.
`shared = area(a) + area(b) − area(union)` treats both crossing rings as solid discs; a shell whose
section carries a ring of its own *inside* the common region — one that crosses nothing — was
credited as double material there. Reviewer's body: a 1.4×0.7×0.2 m plate slotted THROUGH a 32-gon
pipe (r 0.5, bore 0.3; wider than the bore, narrower than the skin, so it crosses the OUTER ring only
and swallows the bore ring whole): merged, 3 parts, `holes_filled 3`, but `overlap_ft3` = 0.12703 m³
against the true |w| ≥ 1.5 volume 0.07084 m³ — the excess is exactly the bore-in-plate, 8 % of the
mesh handed to `_conserves`' authored side (no acceptance flipped, but unjustified credit per the
#583 doctrine), and `fill_after` 0.669 for a true 0.735.

**Fix, on the body's evidence** — `_enclosed_correction(a, b, others, twice)`, applied in
`_first_crossing` where all the slice's rings are in hand: every OTHER ring whose interior probe lies
inside both `a` and `b` is asked at that probe whether the body is doubled there, and its area enters
the shared area with sign `[doubled here] − [doubled just outside it]` (outside = the smallest
enclosed ring around it, else the common region itself, which the merge already verified as doubled).
So a bore subtracts itself, an island of two shells inside that bore (a rod down the pipe, also
through the plate) adds itself back, a third shell's ring changes nothing, and nothing enclosed means
nothing to do — read from the body, never from the nesting being corrected. A hole ring that only
*partly* overlaps the other shell must cross it and is therefore a crossing pair of its own (merged or
refused there), so the piecewise reading is complete for the arrangement; the docstrings' "lower
bound" wording is replaced by what it now is (holes discounted; a shell nested *whole* inside another
crosses nothing and stays #613's). Cost: crossing path only — one `_interior_probe` + two
point-in-ring tests per other ring of the slice, one oracle call per enclosed ring.

| body (12 orders each unless noted) | ac6800e | this round |
|---|---|---|
| plate through pipe @ 12° (the review's probe) | overlap 0.12703 m³ ("7751.66 in3 shared"), fill_after 0.669 | **0.0708409 m³ = (∣skin∩plate∣ − ∣bore∣)·h to 1e-7** ("4322.98 in3"), fill_after **0.7354**; still 3 parts, holes 3, merged 1, every order |
| same + a 16-gon rod down the bore, through the plate | — | overlap **0.076964 m³ = (∣skin∩plate∣ − ∣bore∣ + ∣rod∣)·h** exactly, 6 parts, 9/9 orders |
| loss table (1476 sunk runs) · random 1200 · harder shapes · reference rows · #609 984 · #621 205 | as above | **identical** (0 lost / 0 kept; diff of the reference outputs still EMPTY; no enclosed ring exists in any of them, so no number moved) |
| router: sunk 1 cm @ 12° / 2 cm @ −17° / base stud / bar through post | as above | identical transcripts (305.12 / 610.24 / 152.56 / 19527.60 in3); + `plate_through_pipe_12.ifc` → `OK (3-part …)`, `slab decomposition improved PlatePipe (3 solids, fill 0.58 -> 0.74)`, `1 crossing section(s) merged (PlatePipe: 1, 4322.98 in3 shared)`; all five VALID 0/0, provenance ok; matrix `7dae5d40…` unchanged |

Two review nits also taken: the test module's `_SUNK` comment now says which row does what on `main`
(the issue's named placement, 2 cm @ −17°, double-authors 41/41 on this generator; the 1 cm @ 12° and
5 cm @ 5° rows are the 41/41 silent losses; the base stud rows mix losses/doubles with 17/41 prisms),
matching the tables above; and the stream-local count is environment-dependent by one test
(`test_router`'s read-only-dir case skips when running as root: 284 passed / 14 skipped here, 285 / 13
in the tech lead's sandbox).

Tests: `tests/test_ifc_assembly_637.py` 14 → **16** (`_enclosed_correction` on hand-made rings: empty /
not enclosed / bore −4 / bore + rod −3 / third shell 0, and the merge carrying bore and rod along
un-merged with shared 40 − 4 + 1; the plate-through-pipe body with and without the rod over 7 orders
each, pinning `mesh_overlap_in3` to the geometric value at 1e-5 and `fill_after` to (mesh − doubled) ÷
authored).

## Round 3 (after the delta review of 8a679e3): the common region is read face by face, and a bore against a bar is passed over, not merged or refused

The delta review confirmed the wide-plate class exact and found the hole in round 2's completeness claim: a
bar **narrower than the bore** (plate 1.4×0.5×0.2 through the r 0.5 / bore 0.3 pipe) makes the BORE ring
cross the plate ring too. Round 2 admitted an "other" ring by ONE interior probe and, depending on which
pair the stitch listed first, credited the whole disc overlap (probe outside the strip: 0.0953 m³, +8 % of
the mesh unjustified), subtracted the whole bore (probe inside: 0.0391, under), or refused ((bore, plate)
visited first: the deepest dropped run lies in the void) — three outcomes for one body; truth 0.0434946.

**What changed** (same territory; `_enclosed_correction` is gone, its job done properly inside the merge):

* `_overlay(a, b, cuts)` — both boundaries cut and sided against the other ring → (outside pieces, inside
  pieces, depth); the one loop `_union_of_crossing` and `_clip` share. `_closed(pieces)` — the degree-2
  check + `_stitch`, shared likewise.
* `_clip(c, other)` — the part of ring `c` inside `other`, as rings: itself when nested whole, nothing
  when apart / in mere contact (depth < `MIN_EXTENT_FT`) / holding `other` inside itself (it draws no
  boundary in there), the stitched lens when they cross; `None` if a real crossing will not close.
* `_union_of_crossing(a, b, cuts, others, twice)` now reads the shared area **face by face**: every
  other ring of the slice is clipped to the common region (`_clip(c, a)` then `_clip(·, b)`) and asked at
  its own interior probe whether two shells overlap there; the common region itself is asked `_beside`
  the dropped piece standing clearest (≥ `MIN_EXTENT_FT`) of the partner and of everything clipped in —
  never at a point inside a clipped piece, which is what made round 2's deepest-run probe land in the
  bore by tessellation luck. `shared = |a∩b| + Σ ([doubled in piece] − [doubled just outside it])·|piece|`.
  If no clear standpoint exists or the body is NOT two deep there, the pair is **passed over**
  (`(None, 0.0)`): a bore ring against the bar through it is not a merge to make — the bar's crossing
  with the SKIN is, and once that is made the bore crosses nothing. `_first_crossing` returns `None`
  (refuse → attributed prism) only when pieces do not close, or when pairs cross yet none is two shells
  deep where they overlap (a bar lodged across the bore *inside* the wall; a shell wound the other way).
  So the listing order can no longer change an outcome: the only order-dependent step left is which
  backed pair merges first, and union is associative.

**Re-measured against an independent Sutherland–Hodgman clip** (four half-plane clips in the test /
probe script, no engine code), 7 triangle orders per cell:

| body | truth (m³) | 8a679e3 | this round |
|---|---|---|---|
| plate 1.4×0.7 through pipe, yaws 0/5/12/33/45/77 | 0.0708409 | exact | **exact, every yaw and order** (0.0708408–0.0708410) |
| plate 1.4×**0.5** (the review's counter-example), yaws 0/5/12/33/45/77 | 0.0434946 | 0.0953 / 0.0391 / refusal by order | **0.0434945–0.0434947 at every yaw, all 7 orders one number**; fill_after 0.7223 (= truth) |
| plate 1.4×**0.3** (narrower than the bore itself), same yaws | 0.0245747 | (refused by probe luck) | **exact everywhere** |
| 0.5 plate + 16-gon rod down the bore | 0.0496175 | — | 0.0496176, 6 parts |
| pin 0.5×0.1×0.1 driven through the wall 0.1 INTO the bore | 0.0020000 | refused (documented) | **merged, 0.0020000** = its buried wall length, 9/9 orders |
| pin in the wall only · two pipes under one plate | 0.0009754 · 0.1416818 | exact · exact | exact · exact (5 parts, merged 2) |
| bar 0.8 long lodged across the bore inside the skin · lug shell wound the other way | — | — · refused | **refused ×7** (attributed `crossing rings at z = …`, prism delivered) · refused ×7 |
| loss table 1476 · random 1200 · harder shapes · reference rows (diff vs main) · #609 984 · #621 205 | | | **identical** (0/0; EMPTY diff; no other ring reaches into any of their crossings) |
| router: the four round-1 IFCs + plate_through_pipe_12 | | | identical transcripts; + `narrow_plate_through_pipe_12.ifc` → `OK (3-part …)`, `fill 0.58 -> 0.72`, `1 crossing section(s) merged (PlatePipe: 1, 2654.21 in3 shared)` (= 0.0434946 m³); all six VALID 0/0 + provenance ok; matrix `7dae5d40…` unchanged |

Timing (best of 5, ms, main → now): sunk lug 1.03 → 1.7 (it merges and now clips), face pair 1.04 → 1.05,
corner pair 1.05 → 1.3, frustum 8 13.2 → 12.0, strut 1.13 → 0.96, lattice 3³ 38 → 33, 64-gon tube 9.3 →
8.5 — noise either way off the crossing path. Tests 16 → **18**: `_clip` (nested / holding / apart /
grazing / crossing / unclosable), the face-wise shared area on hand-made rings incl. the narrow-bore lens,
the passed-over bore pair, three listing orders settling identically, the lodged bar refusing; the review's
literal numbers pinned against the test's own Sutherland–Hodgman (0.63513466612 m², 0.0708409, 0.0434946);
the pipe bodies end to end — plate 0.7 / 0.5 (four yaws) / 0.3, rod add-back, pin into bore — each over 7
orders asserting `mesh_overlap_in3` == oracle at 1e-5, `fill_after` == (mesh − doubled)/authored, and one
number across orders; the refusal test now uses the lodged bar (the pin into the bore merges correctly).
BRANCH STATE counts refreshed below (the second nit).

## Round 4 — the ruling: clean crossings merge exactly; nested ones refuse honestly (follow-up #715)

The round-3 review (recorded publicly with the ruling at
https://github.com/ckaragitz/tekton/pull/713#issuecomment-5258619255) confirmed everything with at most
one nesting level exact and order-free (plate 0.7/0.5/0.3, rod, pin, two pipes, grazing to the floor,
three-plate star, plus + square; lodged bar / flipped shell refused) and found the same flaw one level
further down: pipe + a rod r 0.22 down the bore + a bar 0.3 wide (the rod *wider* than the bar) → 12/15
orders credited ∣skin∩bar∣·h (+21.7 % of the overlap), 3/15 the truth, both accepted; pipe-in-pipe + bar
likewise. Cause: each clipped piece's doubledness was still read at ONE interior probe, which can sit
inside a smaller piece nested in it. That is the fourth symptom the docstring said should buy the general
cure, and the tech lead **ruled** the scope for this PR: **merge only CLEAN crossings** — a pair whose
common region no other ring of the slice reaches into (every `_clip` against it empty) and where the
standpoint confirms two shells; `shared = ∣a∩b∣` exactly. Any pair with a third ring clipped into its
common region is **passed over**; a slice left with an unmerged crossing **refuses** → attributed
`kept_prism` → the honest single prism, delivered (#637 DONE 2 allows the refusal). The face-by-face sign
bookkeeping is removed from the shipped path; `_overlay` / `_closed` / `_clip` stay (they decide "clean"
and serve the follow-up). Both non-blocking items are in: the standpoint is kept `MIN_EXTENT_FT` clear
of *every* other ring's boundary, not only of clipped pieces (so a bar lying tangent to a bore — whose
crown vertex sits ON the bar's edge — is asked from inside the wall and merges, 0.0192639 m³ exact ×7,
instead of refusing needlessly), and the vertex-on-edge case is noted below. The follow-up is filed as
**#715** — read doubledness by winding across slice segments so nested crossings merge — with today's
oracle bodies and numbers as its acceptance table (Refs #637 #613).

| body (7 orders each) | round 3 (dc7dbbb) | this round |
|---|---|---|
| CLEAN — sunk lug rows (1476), random sunk boxes (1200), bar through post, equal / thin bars crossing, two lugs one band, lug sunk + flush top / flush side, 16-gon boss on a plate edge, pin in a pipe WALL (0.0009754 m³), bar tangent to the bore's crown (0.0192639) | merged, exact | **identical** — merged, exact, one number per body |
| NESTED — plate 0.7 / 0.5 / 0.3 through the pipe × yaws 0/5/12/33/45/77 · 0.5 plate + rod · pin driven INTO the bore · two pipes under one plate · block + two lugs crossing EACH OTHER (three deep) · bar 1 cm into the bore | merged (exact at this level; wrong one level down per the review) | **refused ×7 each, one outcome**: `slab lane: crossing rings at z = … (interpenetrating shells whose crossing is nested -- a third section inside it, e.g. a bar through a hollow member's bore -- or not two shells deep, or whose outlines do not close; only clean crossings are merged, the rest is not guessed)` → 1-part prism ≥ mesh |
| not two deep anywhere — bar lodged across the bore inside the skin · lug shell wound the other way | refused | refused (same reason) |
| reference rows (diff vs main) · #609 984 · #621 205 · matrix | EMPTY · identical · `7dae5d40…` | **EMPTY · identical · `7dae5d40…`** |
| router: sunk 1 cm / 2 cm / stud / bar through post | 305.12 / 610.24 / 152.56 / 19527.60 in³ merged | identical |
| router: `plate_through_pipe_12.ifc` · `narrow_plate_through_pipe_12.ifc` | `OK (3-part …)` 4322.98 · 2654.21 in³ | **`OK (1-part generic_model .rfa …)` + `kept as a single prism (the decomposition was refused, never silently accepted): PlatePipe -- box lane: not axis-aligned (…), then slab lane: crossing rings at z = 1.6404 ft (interpenetrating shells whose crossing is nested …)`**; both VALID 0/0, provenance ok |

**Known limits, stated (per the review's note):** a vertex of one ring lying exactly ON another ring's
edge is not a proper cut (`_ring_cuts` takes both parameters strictly inside (0, 1)); with the µm noise
two independently written shells carry that is a measure-zero coincidence, and where it does happen
(the tangent bar's bore crown) the pair is judged by `_interior_probe` containment — clean and merged
in that case, or, if two such vertices made pieces fail to close, refused. Contact below `MIN_EXTENT_FT`
is never a crossing (unchanged since round 1).

Tests 18 → **19**: `only clean crossings merge …` (clean with nothing / a far ring / a tangent hole →
∣a∩b∣; a bore under, a bore across, a bore + far ring, any oracle → passed over `(None, 0.0)`; not two
deep → passed over; the bore's own pair passed over; six listing orders of a nested slice all `None`;
the lodged bar `None`; three orders of a clean slice all merge); the interpenetration test's mutual-lug
row now asserts the refusal ×7; `a clean crossing of a hollow member is credited exactly` (pin in wall,
tangent bar vs the test's Sutherland–Hodgman, one number ×7); `a bar through a pipe's bore is a nested
crossing and ships as the honest prism` (plate 0.7 @ 12/45, 0.5 @ 12/0/45/77, 0.3, rod, pin into bore,
two pipes — each ×7: 1 part, `kept_prism` with the reason, no `decomposed`, authored ≥ mesh); the
oracle-numbers test keeps 0.63513466612 / 0.0708409 / 0.0434946 pinned as #715's acceptance values.

## Neighbouring cases NOT changed, on purpose (candidates for follow-ups, none filed as blocking)

* **An island read as a hole** — a bolt passing clean through a plate with no crossing in the plate's
  slab (its ring nested inside the plate's): even-odd depth 1 → "hole" → filled. The authored geometry
  is *correct* (the plate ring covers it), but the bolt-in-plate volume is double-counted by the mesh
  and not credited, so a fat enough bolt (> 2 % of the body inside the plate) is refused as "dropped
  material" and ships as one prism. That is exactly **#613's DONE 1** (`shell_overlap_ft3` for odd-depth
  rings the body reads as |w| ≥ 1.5) — not re-filed; a note on #613 says the crossing case now feeds
  `overlap_ft3` through the same `read_assembly` credit, so #613 should add to that key rather than
  invent a second one.
* **Every NESTED crossing refuses** under the round-4 ruling (a bar through a hollow member's bore, a
  rod down it, members crossing each other inside a third): honest prism today, exact merge is #715's.
  A bar lodged across a bore *inside* the wall and a shell wound the other way refuse too (not two deep
  anywhere).
* **`fit_solid`'s `fill` for overlapping shells can exceed 1** (two 1 m cubes half-merged: mesh 2.0
  m³ over a 1.875 m³ envelope → fill 1.07 ≥ `DECOMPOSE_FILL`, so no decomposition is attempted and the
  envelope ships). Pre-existing, harmless (an envelope is delivered and called one), outside territory.
* #634's flush lug is still the honest prism (reference row); #613's by-construction accounting is
  untouched.

## BRANCH STATE (eng #637)

Branch `cam/637-crossing-rings` from `main` @ 6f33fb7; one issue, one PR (`Closes #637`). Files:
`src/rvt/ifc/assembly_parts.py` (`_ring_cuts`, `_split_ring`, `_merge_crossing_rings`, `_first_crossing`,
`_overlay`, `_closed`, `_clip`, `_beside`, `_union_of_crossing` new; `decompose_slabs` calls the merge, refuses `None`
with its own reason and returns `crossings_merged` / `overlap_ft3`; `read_assembly`'s slab branch
credits `overlap_ft3` in `_conserves` and `fill_after`, words the refusal, records `crossings_merged`
(zero-filled on the box lane too) + the shared-material note, adds the model note) + its `plugin/lib`
mirror via `tools/sync_plugin.py`; `tests/test_ifc_assembly_637.py` (new);
`tests/ci_shard.d/637-crossing-rings.txt` (new); this fragment (new). Not touched: `router.py`,
`famgen/**`, `steplite`, `frontdoor/**`, `tests/test_ifc_assembly.py`, any hot file, the stream index.

Gates (cloud session, fresh clone, no `samples/`; the PR body carries the same numbers per head) —
stream-local gate `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_ifc_assembly_637.py
tests/test_ifc_assembly.py tests/test_ifc_assembly_623.py tests/test_ifc_assembly_628.py
tests/test_router.py tests/test_records_layout.py -q -rs`: main @ 6f33fb7 **270 passed / 14 skipped**
→ round 1 284/14 → round 2 286/14 → round 3 (rebased on de292a8) 288/14 → round 4 **289 passed / 14
skipped**, 0 failed (one of the 14 skips is `test_router`'s read-only-dir case, which only skips as root
— a non-root sandbox reads one more pass and one fewer skip); whole merged CI shard `RVT_SKIP_LARGE=1
pytest -q -p no:cacheprovider $(tools/dev/shard_list.py --print)` on the round-4 tree: **2610 passed /
137 skipped / 3 xfailed, 0 failed (8 min 11 s)** (round 1: 2613, round 2: 2615 pre-rebase / 2607
post-rebase — #711 re-parametrised shard tests, round 3: 2609); `/simplify` on the diff (round 1);
`/verify` = the router driven on the six IFCs above, every round; `tools/sync_plugin.py` → `--check` clean; `plugin/scripts/validate_plugin.py` PASS;
`tools/dev/check_portable_paths.py` ok (3098); drop-in resolves in `tools/dev/shard_list.py --print`;
`tools/route.py matrix` byte-identical (`7dae5d40…`, 39 lines). Nothing staged for the viewer, no
ledger entry, no certification claimed.
