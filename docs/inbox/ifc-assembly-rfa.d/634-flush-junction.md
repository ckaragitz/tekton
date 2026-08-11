# eng #634 — a member FLUSH with another member's edge decomposes into its slabs: an ambiguous slice is stitched one shell band at a time (2026-08-11)

*Fragment of the `ifc-assembly-rfa` stream (index: `docs/inbox/ifc-assembly-rfa.md`, left untouched —
the issue text predates the fragment convention and asked for "a new dated section at the end of the
index"; docs/inbox/README.md (#636) supersedes that), written by engineer session eng #634 (wave 41) on
branch `cam/634-flush-junction` from `main` @ 7cb0cc7 (i.e. after #713 / #637 landed). One PR, one
voice; nobody else appends here.*

Refs #634 (this task); #621 (which measured and pinned the case), #609 / #637 (the contact and crossing
laws this must not disturb), #623 / #628 (reference rows). PG1, PG6.

## The defect, reproduced on `main` @ 7cb0cc7 first

Two shells in **contact** whose rings meet at ONE welded slice vertex with two **coincident spokes**:

* a member **flush** with the block's edge — its side face lying IN the block's end face (the commonest
  lug / stud / plate placement there is), so at every slab through the member each shell carries its
  own copy of that one boundary direction away from the shared corner;
* two touching faces whose **triangulation diagonals cross at the slab's height** — a member centred
  on a face of the same aspect (the issue's 1×1×2 m member half-way up a 3×3×6 m column): at the mid
  slab both faces' segments split at the same point, two bundles of two.

`_stitch` welds every segment by its 2-D end points whichever shell it came from; `_junction_pairs`
sorts the four spokes by angle and probes each wedge's bisector; the zero-width wedge between the two
copies probes ON the doubled face, where |winding| reads 0.5 + 0.5 = 1, so both neighbouring wedges
claim one spoke → `None` → the slice is AMBIGUOUS → `decompose_slabs` refuses → the whole body ships as
ONE prism, `kept as a single prism (…): box lane: not axis-aligned (…), then slab lane: ambiguous slice
at z = … ft (regions touch at a point or an edge; the ring set is not guessed)`. Honest (delivered,
caveated, never a loss — pinned until now by `test_a_flush_face_pair_is_kept_as_one_honest_prism_not_lost`), but
a 2×6×3 m block with a flush 0.5×1×0.5 m lug ships as a 1.138× envelope instead of block + lug, at
every triangle order. Whether a given (placement × yaw) hits it is decided by whether the two shells'
copies of the shared corner column round to the same nanometre after yaw (each shell interpolates its
OWN vertical edge): the issue's `(-1.25, 2.5, 1.25) @ 12°` and `(1.25, 2.5, 0) @ 33°` do at 101/101
orders; the same lug at 33° / −5° happens not to weld and already decomposed on `main`.

Diagnostic dump of the issue's first fixture at the lug band (`main`): junction at (−5.2555, 8.9453) ft,
degree 4, spokes 12.0° (block top, 3.28 ft) / **−78.0° (block side, 9.84 ft) / −78.0° (lug side, 1.64
ft)** / −168.0° (lug top, 0.82 ft) → `slice_loops` = `None`. Same shape at 33° and at 0° (where the box
lane never asks).

## Mechanism chosen: (b) — per-shell-band stitching inside `slice_loops`, run only where today's weld refused (territory: `slice_loops` + one new private helper `_stitch_bands`; `_stitch` / `_junction_pairs` byte-intact)

**Why (b) and not (a).** Option (a) — teach `_junction_pairs` to tell two coincident spokes apart by
which way the shorter one "peels off" at its far end — reasons about a fact the 2-D slice has already
thrown away and has to re-derive it from geometry that is not reliable: the *shorter* spoke is not
always the member's (the block's side segment is split wherever ITS diagonal crosses the slab, which
can be a hand's width from the corner), the far end of either spoke can itself be another junction
(the diagonal case is exactly that: two bundles at one vertex, and a flush member on a centred face
has both kinds in one slice), and following chains through degree-2 vertices until they turn is a
walk with its own failure modes. Option (b) uses the fact directly: **the mesh knows which copy is
whose.** A closed shell's triangles straddling the plane form closed *bands* — consecutive triangles
share the mesh edge the plane cuts between them — so a band meets itself exactly two segments to a cut
edge, and the two copies of a flush boundary are *different mesh edges of different bands*. Stitch each
band on its own and the coincident spokes never meet; nothing is guessed, and the diagonal case needs
no second rule (each band is degree 2 at the crossing point: both of its segments there were cut from
its own diagonal).

**What was built** (`src/rvt/ifc/assembly_parts.py`, +75 / −5 lines of code and docstring; nothing else
in the module moves — `_stitch`, `_junction_pairs`, `ring_nesting`, `_probe_clear_of`, the whole #637
crossing path, `decompose_slabs`, `read_assembly`, every constant: byte-intact):

* `slice_loops` records, per segment, the two mesh edges the plane cut it from (`cut_from[i]` = two
  `(p, q)` 3-D point pairs — one tuple per crossing edge on straddling triangles only; no work on the
  others). It calls `_stitch(segs, inside)` exactly as before and, **only if that returns `None`**,
  returns `_stitch_bands(segs, cut_from, inside)` instead. So every slice `main` settles is settled by
  the same call with the same arguments → identical rings (DONE 3, measured below: 1189 contact runs +
  20 reference rows + 184 500 random runs' non-ambiguous classes, all identical).
* `_stitch_bands(segs, cut_from, inside)` — union-find over segments keyed by cut edge (an edge is named
  by its two end points rounded to `_WELD`, order-free, so an STL-style soup with unshared vertices
  welds exactly as the 2-D weld does); fewer than two bands → `None` (nothing to tell apart: today's
  answer stands); otherwise each band goes through the *same* `_stitch(band, inside)` — same parity
  check, same `_junction_pairs` with the same body oracle for any junction a band has on its own — and
  any band that does not stitch → `None`. The rings of all bands are returned together, unordered and
  un-nested like `_stitch`'s.
* Downstream is unchanged and already fit for what comes out: the block ring and the lug ring now
  share an edge (each with its own µm rounding) and a corner — precisely #621's face pair plus #609's
  corner, which `ring_nesting` judges from a probe standing clear of the other ring; `_ring_cuts` may
  find a hair-angle cut between the two copies of the shared edge, `_overlay` reads its depth < 
  `MIN_EXTENT_FT` → contact, not a crossing → untouched (#637's `contact is not a crossing` test pins
  exactly this). No merge fires, no credit is taken, `crossings_merged 0`.

**Why this cannot manufacture a loss the weld would have refused** (the doctrine question). The band
split only *removes* foreign spokes from a junction; it never invents a pairing. Within a band a vertex
has degree 2 by construction unless the band is degenerate or fused through a non-manifold / duplicated
edge, and then the same `_junction_pairs` runs with the same whole-body oracle, where foreign material
in a wedge can only ADD a hit → a double claim → `None`; it cannot flip a pairing silently (short of an
oppositely wound overlapping shell, which poisons every winding test in the module alike and whose mesh
volume is meaningless). Odd soup degree at a point implies odd degree in some band → that band refuses.
Open chains refuse by parity. So the fallback's outputs are a subset of "each shell's own section",
and its refusals are today's prism. **No volume backstop, no tolerance touched, no authored-side
credit, no change to `_conserves`** — the flush pair conserves because block + lug rings are exact, and
`fill_after` reads 1.00.

**The genuinely ambiguous residue, kept honest.** A shell exported TWICE (duplicated lug): its two
copies carry identical welded edges → ONE band whose every vertex is a junction of two coincident
spoke pairs → `_stitch` refuses it alone → `None` → the attributed prism, 21/21 and 13/13 orders (pinned:
`test_what_no_band_can_tell_apart_is_still_the_honest_prism`; and it is now the "ambiguous slice"
example in `tests/test_ifc_assembly_623.py`, see *Tests* below). Bands fused through a shared
non-manifold edge, T-junction (non-conforming) shells whose pieces do not close band by band, and a
single shell touching itself with coincident spokes likewise stay `None`.

## Evidence (all `RVT_STEPLITE_FORCE`-equivalent: no ifcopenshell in the cloud VM; one driver — `python tests/test_ifc_assembly_634.py <named|random|contact|reference|timing>` — run against both engines by `PYTHONPATH` swap over a `git worktree` of `main` @ 7cb0cc7; oracle = the test module's OWN shoelace / signed-tetrahedra / even-odd arithmetic on the micron-rounded coordinates the file carries, never an engine function)

**Named flush placements and diagonals** — 8 flush placements (the issue's two; −y-edge flush; a lug on
the +y face flush with the +x edge; edge-flush AND top-flush = a shared 3-D corner; a stud on a 1×4×4
slab; a 3 m member against a 0.5 m plinth; a member wider than the face, overhanging the other edge) +
a block with a flush lug at EACH end of one face (three shells) + the issue's column/member diagonal
pair with the standard mesh (diagonals cross at the mid slab) and with the member's touching face
re-triangulated (diagonals on one LINE) = 11 bodies × yaws {12, 33, −5, 5, −17, 45, 0.05, 0} × **101
seeded triangle orders = 8 888 runs per engine**:

| | `main` @ 7cb0cc7 | this branch |
|---|---|---|
| yaw ≠ 0 (7 777 runs) | **4 848 kept prisms** `ambiguous slice` (48 whole cells of 101/101: authored ÷ oracle 1.1379 lug rows, 1.1633 +y lug, 1.2713 stud, **5.0455 tall member**, 1.5294 wide member, 1.2329 two lugs, 1.1786 diagonals) + 2 929 slabs (the 29 cells whose corner copies happen not to weld) | **7 777 × slabs**, authored ÷ oracle **1.000000..1.000000 in every cell**, parts 3 / 4 / 5 (two lugs) as geometry dictates, `holes_filled 0`, `crossings_merged 0`, member present (its centre held by its own part, the block's by another) at every order |
| yaw 0 (1 111) | boxes ×2 (×3 two lugs), exact | identical — the band stitch is never asked |
| the issue's two fixtures @ 12° / 33°, 101 orders each | 202/202 kept 1.137931 | 202/202 slabs ×4 / ×3, 1.000000 |
| silent losses (authored < oracle·(1−1e-6) without `kept_prism`) | 0 | **0** |

**#621's randomised face-sharing search, re-run with the same shape** (block ∈ {1..6}³ m, member 0.5–2 m
a side on a random face ±x/±y/top, lateral centred / FLUSH / random, vertical base / mid / top-flush /
taller; seeds 1, 2, 3 × 300 configurations × yaws {0, 5, 12, 33, −5} × 41 orders = **N = 184 500 runs per
engine**, 341 s / 348 s; the generator is this module's `_random_face_pairs`, not #621's unrecorded
script, so the shares differ from its 17.7 % — both engines ran the SAME 184 500 bodies):

| class | `main` @ 7cb0cc7 | this branch |
|---|---|---|
| silent losses | **0** | **0** |
| `kept: dropped material` | 0 | 0 |
| `kept: ambiguous slice` ("not decomposable") | **19 926** (10.8 %; every `*/flush/*` side-face kind at yaw ≠ 0 with fill < 0.90, AND 3 157 `*/centred/mid` runs = the diagonal-crossing case) | **0** |
| slabs | 111 438 | **131 364** (= 111 438 + 19 926 exactly) |
| boxes (yaw 0) · single prism (fill ≥ 0.90, nothing attempted) | 32 882 · 20 254 | 32 882 · 20 254 (identical) |
| worst ∣authored − oracle∣ ⁄ oracle over all decompositions | 5.30e-10 | 5.30e-10 |
| genuinely ambiguous residue | — | 0 in this search (no duplicated / fused shells are drawn; the residue class is pinned separately above) |

Per-kind tables for both engines are in the sweep output (61 kinds; every non-ambiguous cell identical
count for count, every ambiguous count moved to slabs). A CI-sized slice (seed 634, 40 × {12, 33} × 3 =
240 runs) is a test.

**Reference rows — re-measured IDENTICAL except the one this issue inverts** (parts / lane / authored ÷
mesh; `diff` of the two engines' outputs shows exactly one line):

| body | `main` @ 7cb0cc7 | this branch |
|---|---|---|
| 900 mm strut 0.0 / 0.1 / 0.2 / 0.5 / 0.8° | boxes ×3 1.000000 / slabs ×3 1.000002 / 1.000006 / 1.000022 / 1.000064 | identical |
| 50 µm-mismatch strut 0° / 12° (hairline) | boxes ×3 1.000000 / slabs ×3 0.999622 | identical |
| 8-band frustum · 12-band cone · 24-band 64-side frustum | slabs ×8 0.999442 · ×12 0.998513 · ×24 0.997532 | identical |
| plate + 6 mm² pin 7° · U-channel 4° / 30° · chamfered square 22.5° (#628) | slabs ×1 0.999943 · ×3 0.999997 / 1.000003 · prism ×1 1.000001 | identical |
| lattice 3³ / 9³ (#623) · sunk lug 1 cm @ 12° (#637) | boxes ×27 exact / kept (work budget → part budget) · slabs ×3, merged 1 | identical |
| #621 face pair 12° · #609 corner pair 12° | slabs ×4 1.000000 · slabs ×3 1.000000 | identical |
| **flush lug 12° (#634)** | **kept ×1 1.137931 (ambiguous slice)** | **slabs ×4 1.000000 — by design** |
| #609 corner pairs 4 positions × 6 yaws × 41 = 984 + #621 face pairs 5 × 41 = 205, per run (class, parts, ratio, holes, merged) | 1 025 × slabs 3 + 164 × slabs 4 | **`diff` EMPTY over all 1 189 lines** |
| `tests/test_ifc_assembly_637.py` (20 tests) with only its flush row's expectation changed | green | green |
| `tools/route.py matrix` | sha256 `7dae5d40…`, 39 lines | **byte-identical** |

**Router, end to end** (`RVT_STEPLITE_FORCE=1 .venv/bin/python tools/route.py run --ifc X --output rfa
--out D --json`, same IFC bytes, `main`'s engine by `PYTHONPATH=../tekton-main/src`):

```
flush_lug_12.ifc  (the issue's fixture: 2x6x3 block + 0.5x1x0.5 lug on -x, +y edge flush, yaw 12; identity order)
  main:   OK (1-part generic_model .rfa ...) · 1 of 1 part(s) are ENVELOPES ... Flush 88%
          · kept as a single prism (the decomposition was refused, never silently accepted): Flush -- box lane: not
            axis-aligned (...), then slab lane: ambiguous slice at z = 4.9213 ft (regions touch at a point or an edge; ...)
          parts: 1 polygon, h 9.843 ft
  branch: OK (4-part generic_model .rfa ...) · slab decomposition improved Flush (4 solids, fill 0.88 -> 1.00)
          decomposed: parts 4, slabs 3, holes_filled 0, crossings_merged 0, fill_after 1.0 · kept_prism [] · no ENVELOPE
          caveat, no crossing caveat · part heights 4.101 / 1.640 / 1.640 / 4.101 ft (block / block + lug / block)
flush_lug_base_33.ifc (issue's second): main 1-part + prism caveat (z = 0.8202 ft) -> branch OK (3-part ...), fill 0.88 -> 1.00
two_flush_lugs_m17.ifc: main 1-part, Flush 81% -> branch OK (5-part ...), fill 0.81 -> 1.00
diag_column_member_12.ifc: main 1-part, 85%, ambiguous at z = 9.8425 ft (the mid slab) -> branch OK (4-part ...), 0.85 -> 1.00
tall_member_plinth_45.ifc: main 1-part, **Flush 20%** -> branch OK (3-part ...), fill 0.20 -> 1.00
```
All five branch outputs: `tools/rvt_validate.py --family` **VALID (no errors); warnings=0 info=2**;
`tools/make_family.py provenance` **ok: true, findings []**. No certification claimed (rule 4): VALID is
a fact about the files, not about Revit; nothing staged for the viewer.

**Cost.** The main path pays one tuple per crossing edge on straddling triangles (the `(p, q)` pair
riding along with the 2-D point it already computed) and one list append per segment; the band stitch
itself runs only where the weld refused. Best-of-5 `read_assembly`, ms, `main` → branch, measured twice
each while the random sweeps were loading the VM (so read the pairs, not the absolutes): strut 0°
1.97/1.97 → 2.29/2.02, strut 0.1–0.8° 1.64–1.83 → 1.62–1.88, mismatch strut 1.78–1.95 → 1.65–1.94,
8-band frustum 14.9–16.0 → 15.3–16.4, 12-band cone 23.6–25.6 → 24.3–25.5, 24×64 frustum 142–152 →
147, lattice 3³ 46.8–48.7 → 46.9–51.2, lattice 9³ 185–192 → 189–194, sunk lug 1.89–1.97 → 1.99–2.01,
face pair 1.68–1.76 → 1.81–1.83, corner pair 1.63–1.72 → 1.71, **flush lug 1.44–1.52 → 2.02–2.15 (it
now slices three slabs and nests them instead of refusing at the first)**. Within noise everywhere off
the flush path.

## Tests

New module `tests/test_ifc_assembly_634.py` (**11 tests, ~4 s**) + drop-in `tests/ci_shard.d/634-flush-junction.txt`
(resolves in `tools/dev/shard_list.py --print`); generators imported from `tests/test_ifc_assembly.py`
(`_face_pair`, `_corner_pair`, `_FACE_PAIRS`, `_triangle_orders`, `_box_mesh`, `_yaw`, `_strut`, …) and
`_shells` from `tests/test_ifc_assembly_637.py`; the module doubles as the record's sweep driver
(`__main__`). What it pins: `_stitch_bands` on hand-made segments (the flush square pair: `_stitch` →
`None`, bands → rings of area 16 + 1, `ring_nesting` `[0, 0]`, and an STL-style soup naming its own
copies of every end point welds the same); its refusals (bands fused through a shared edge → `None`, a
single band → `None`, a band missing a segment → `None`); `slice_loops` on the flush lug and on both
diagonal bodies = two rings of the right areas, side by side; **the issue's two fixtures over 101 orders
each (202 runs) ⇒ slabs, `holes_filled 0`, authored == oracle to 1e-5, member present**; all eight
placements × seven yaws × 13 orders (728 runs) likewise; two flush lugs in one slice (5 parts, both lugs
held); both diagonal bodies × seven yaws (101 orders at 12°, 7 elsewhere; 286 runs, 4 parts); **the
duplicated flush lug stays the attributed prism ×13**; the 0° box-lane control; the CI slice of the
random search (0 losses, 0 dropped-material, worst ≤ 1e-5, no flush draw kept, some flush draw slabs);
the router delivering `OK (4-part …)` with `fill 0.88 -> 1.00`, no prism caveat, no crossing caveat.
Against `main`'s engine the module fails 9/11 by design (2 by missing symbol, 7 by behaviour) and the
0° control passes on both.

**Three existing assertions changed, each BY DESIGN and each the same fact** (flagged here because two
of them sit outside the territory the tech lead drew, and leaving them red was the only alternative):

1. `tests/test_ifc_assembly.py::test_a_flush_face_pair_is_kept_as_one_honest_prism_not_lost` — DONE 4:
   inverted and renamed `test_a_flush_face_pair_is_block_plus_lug_not_one_prism` (a test asserting the
   opposite of its name would read as a rule-1 regression in every future failure report; the docstring
   names the old test): the same two pairs × 11 orders now assert slabs, `holes_filled 0`, ≥ 3 parts,
   authored == mesh to 1e-5. Nothing else in that file touched.
2. `tests/test_ifc_assembly_637.py::test_reference_rows_read_exactly_as_on_main` — its `flush lug 12
   (#634)` row pinned `(1, "kept", 1.137931)` as a reference; expectation changed to `(4, "slabs", 1.0)`
   with a comment; the other 13 rows and 19 tests untouched and green.
3. `tests/test_ifc_assembly_623.py` — two attribution tests borrowed #634's flush lug as their example
   of *an* ambiguous slice (`…refusals_are_attributed…` and `test_an_undecomposable_yawed_body_names_both_lanes`);
   the fixture is swapped for a new `_dup_lug(off, yaw)` helper there (#621's lug exported twice —
   genuinely ambiguous before and after, 21/21 orders; `tests/test_ifc_assembly_634.py` imports it for
   its residue test rather than hand-rolling the same slices) and every assertion about the refusal
   wording is unchanged.

## Neighbouring cases NOT changed, on purpose

* The refusal sentence `ambiguous slice at z = … (regions touch at a point or an edge; the ring set is
  not guessed)` lives in `decompose_slabs` (outside this territory) and still describes what now
  reaches it (a band ambiguous on its own, or one fused band); not reworded.
* T-junction (non-conforming) shells whose own band does not close edge-to-edge stay the prism where
  the weld also failed; a conforming re-mesh or the general winding-across-segments cure (#715's
  direction) would be the fix, not a looser weld here.
* #715 (nested crossings), #613 (by-construction overlap accounting) untouched; the flush pair takes no
  credit from either.

## BRANCH STATE (eng #634)

Branch `cam/634-flush-junction` from `main` @ 7cb0cc7; one issue, one PR (`Closes #634`). Files:
`src/rvt/ifc/assembly_parts.py` (`slice_loops` records `cut_from` and falls back to the new
`_stitch_bands`; nothing else) + its `plugin/lib/src/rvt/ifc/assembly_parts.py` mirror via
`tools/sync_plugin.py`; `tests/test_ifc_assembly_634.py` (new); `tests/ci_shard.d/634-flush-junction.txt`
(new); this fragment (new); and the three by-design expectation edits listed under *Tests*
(`tests/test_ifc_assembly.py` one test inverted per DONE 4; `tests/test_ifc_assembly_637.py` one
reference row; `tests/test_ifc_assembly_623.py` one fixture helper + two call sites). Not touched:
`router.py`, `frontdoor/**`, `famgen/**`, `steplite`, `tools/`, any hot file, the stream index,
`_junction_pairs` / `_stitch` / the #637 helpers.

Gates (cloud session, fresh clone, no `samples/`, no ifcopenshell): stream-local gate
`RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_ifc_assembly_634.py tests/test_ifc_assembly.py
tests/test_ifc_assembly_637.py tests/test_ifc_assembly_623.py tests/test_ifc_assembly_628.py
tests/test_router.py tests/test_records_layout.py -q` — see the PR body / report for the exact counts
of the pushed head (one of the skips is `test_router`'s read-only-dir case, which only skips as root);
whole merged CI shard `RVT_SKIP_LARGE=1 pytest -q -p no:cacheprovider $(tools/dev/shard_list.py --print)`
— counts in the PR body against `main`'s from the worktree; `/simplify` on the diff (taken: the edge key
as one welded expression + `defaultdict` bands + a trimmed docstring in `_stitch_bands`, `_yaw` instead of
hand-rolled rotations, an explicit slice height, `_dup_lug` shared with #623's module, `Counter`s in the
driver, the inverted test renamed; skipped: hoisting #637's inline reference-row table into a shared
helper — it would rewrite a #637 test outside this territory — and rebuilding `cut_from` in a second pass
only on failure — measured within noise, and one pass is the simpler code); `/verify` = the
router driven on the five flush IFCs above (transcript + VALID + provenance); `tools/sync_plugin.py` →
`--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py`
ok; `tools/route.py matrix` byte-identical (`7dae5d40…`, 39 lines). Nothing staged for the viewer, no
ledger entry, no certification claimed. Merge is the tech lead's (regime #302); this session never merges.
