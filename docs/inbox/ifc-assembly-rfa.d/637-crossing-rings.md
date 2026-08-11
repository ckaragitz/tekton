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

**Chosen handling: UNION (the issue's preferred), with the attributed refusal as the fallback inside
it — not refuse-only.** Refuse-only was measured first and rejected: it turns every interpenetration
whose shared volume exceeds the 2 % slack (a bar run through a post, two equal bars crossing, two lugs
in one band) into a single prism where `main` at least delivered overlapping solids in its lucky
orders; and "treat crossing rings as disjoint" (author both, overlapping) was rejected because it
authors the buried material twice by construction and makes the slab lane disagree with the box lane,
which already authors the *union* of overlapping shells at 0° and credits the overlap
(`test_overlapping_shells_are_measured_as_a_union_not_counted_twice`). The union makes the two lanes
one law.

Five private helpers, called from `decompose_slabs` between `slice_loops` and `ring_nesting`; nothing
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

## Neighbouring cases NOT changed, on purpose (candidates for follow-ups, none filed as blocking)

* **An island read as a hole** — a bolt passing clean through a plate with no crossing in the plate's
  slab (its ring nested inside the plate's): even-odd depth 1 → "hole" → filled. The authored geometry
  is *correct* (the plate ring covers it), but the bolt-in-plate volume is double-counted by the mesh
  and not credited, so a fat enough bolt (> 2 % of the body inside the plate) is refused as "dropped
  material" and ships as one prism. That is exactly **#613's DONE 1** (`shell_overlap_ft3` for odd-depth
  rings the body reads as |w| ≥ 1.5) — not re-filed; a note on #613 says the crossing case now feeds
  `overlap_ft3` through the same `read_assembly` credit, so #613 should add to that key rather than
  invent a second one.
* **A pin driven through a tube wall into its bore** refuses (above). Resolving it means verifying
  dropped runs piecewise instead of at their deepest point; not needed for any body on record.
* **`fit_solid`'s `fill` for overlapping shells can exceed 1** (two 1 m cubes half-merged: mesh 2.0
  m³ over a 1.875 m³ envelope → fill 1.07 ≥ `DECOMPOSE_FILL`, so no decomposition is attempted and the
  envelope ships). Pre-existing, harmless (an envelope is delivered and called one), outside territory.
* #634's flush lug is still the honest prism (reference row); #613's by-construction accounting is
  untouched.

## BRANCH STATE (eng #637)

Branch `cam/637-crossing-rings` from `main` @ 6f33fb7; one issue, one PR (`Closes #637`). Files:
`src/rvt/ifc/assembly_parts.py` (`_ring_cuts`, `_split_ring`, `_first_crossing`,
`_merge_crossing_rings`, `_union_of_crossing` new; `decompose_slabs` calls the merge, refuses `None`
with its own reason and returns `crossings_merged` / `overlap_ft3`; `read_assembly`'s slab branch
credits `overlap_ft3` in `_conserves` and `fill_after`, words the refusal, records `crossings_merged`
(zero-filled on the box lane too) + the shared-material note, adds the model note) + its `plugin/lib`
mirror via `tools/sync_plugin.py`; `tests/test_ifc_assembly_637.py` (new);
`tests/ci_shard.d/637-crossing-rings.txt` (new); this fragment (new). Not touched: `router.py`,
`famgen/**`, `steplite`, `frontdoor/**`, `tests/test_ifc_assembly.py`, any hot file, the stream index.

Gates (cloud session, fresh clone, no `samples/`): see the PR body for the exact counts on the final
head — stream-local gate `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_ifc_assembly_637.py
tests/test_ifc_assembly.py tests/test_ifc_assembly_623.py tests/test_ifc_assembly_628.py
tests/test_router.py tests/test_records_layout.py -q -rs` main **270 passed / 14 skipped** → branch
**284 passed / 14 skipped**; whole merged CI shard; `/simplify` on the diff; `/verify` = the router
driven on the sunk pair at −17° and 12° (above); `tools/sync_plugin.py` → `--check` clean;
`plugin/scripts/validate_plugin.py` PASS; `tools/dev/check_portable_paths.py` ok; drop-in resolves in
`tools/dev/shard_list.py --print`; `tools/route.py matrix` byte-identical. Nothing staged for the
viewer, no ledger entry, no certification claimed.
