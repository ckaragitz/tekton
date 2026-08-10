# ifc-assembly — an arbitrary-geometry IFC becomes ONE multi-part `.rfa`

Stream: **ifc-assembly**. Branch: `claude/ifc-to-rfa-conversion-vo9pcj`.
Refs steer **S-2026-08-10-c** (#498, donor-free families on every route) and the
multi-part factory landed by #515.

## Why

A user handed the session a real IFC — a back-to-back trapeze pipe hanger, LOD 400,
13 products, 76 KB, written by a "Hanger Model Generator" — and asked for a `.rfa`.
The route refused:

```
ifc->facts: ProductFactsError: 13 products with geometry -- name one (product_class= / product_guid=)
```

The refusal was honest but it was the end of the road, and it exposed the real shape
of the gap. `ifc -> rfa` had exactly two lanes:

1. a ROOM IFC whose equipment carries our tagging contract → catalog families, and
2. a single PRODUCT IFC → measured facts → the one wired archetype (`make_downlight`).

Anything else — a fabrication assembly, a vendor LOD-400 export, a Claude Design body,
*several untagged meshes* — fell between them. That is precisely the class of file
#498 names ("when i go to claude design and ask it to build me a 3d object you should
be able to fully convert that to a rfa file").

## What was built

**`src/rvt/ifc/assembly_parts.py`** (new module, new territory) — reads, measures,
decides a shape; never writes a family:

- every `IfcProduct` with a tessellated body is carried through its full
  `IfcLocalPlacement` chain into world feet (project `IfcUnitAssignment` honoured), so
  parts keep their real relative positions instead of piling at the origin;
- each mesh's plan convex hull is fitted to one of the three prisms
  `rvt.famgen.factory.add_generic_part` accepts — **cylinder** (hull radii within
  ±12 % of their mean, ≥ 8 hull points), **axis-aligned box** (hull fills ≥ 98 % of its
  bounding box), else an **N-gon** (decimated to ≤ 48 points; a rotated rectangle is
  exact here) — and extruded over the mesh's Z extent;
- **`fill`** = the mesh's own closed-surface volume (divergence theorem over its
  triangles) ÷ the authored prism's volume. This is the honesty instrument: it says
  per part how much of the authored solid the real body occupies;
- a mesh degenerate in any axis is **skipped by name** with its measured extents, never
  given a guessed thickness; an IFC with nothing measurable raises rather than invents;
- `recentre()` moves the family origin to the assembly's plan centre at its base and
  records the shift, so the mapping back to source IFC coordinates stays exact.

Pure stdlib through the engine's reader selection — **no ifcopenshell needed**.

**`src/rvt/frontdoor/router.py`** — a third `ifc -> rfa` lane, `_assembly_rfa`, tried
**only after** the existing two. The archetype lane keeps its exact behaviour where it
succeeds (early `return`); only where it *raised* does the assembly lane run, and its
error is demoted from `res.errors` to a caveat that names what did not apply. The lane
reuses `_famspec_rfa(res, "generic_model", …)`, so the emit / family-mode validator /
provenance scan / `--target-version` block is the very one the famspec lane uses — no
second emit path.

**`src/rvt/frontdoor/matrix.py`** — the `ifc -> rfa` cell now states three lanes and
carries the massing caveat and the tessellation precondition. `verify_evidence()` is
green.

## Evidence

The user's file, through `tools/route.py run --output rfa` on a **fresh clone**
(uv venv, `.[test]` only, no `samples/`, no ifcopenshell):

```
OK (13-part generic_model .rfa measured from f1256177-trapezehangerb2blod400.ifc)
steps: ifc->intent ok | ifc->facts FAILED | ifc->parts ok | famspec->rfa ok | rfa-emit ok
1.4 s
```

- `.rfa` 232 KB, release **2026**, category **Generic Models**
- family-mode validator **VALID, 0 errors, 0 warnings**; provenance **ok, zero donor hits**
- 13/13 products measured, **0 skipped**: 9 boxes + 4 cylinders
- overall **36.75 × 1.75 × 29.98 in**

Dimensional spot-checks against the real hardware the IFC names (these are the mesh's
own numbers, not catalog facts):

| part | measured | the named product |
|---|---|---|
| Strut Channel P1000 (×2) | 36.00 × 1.62 × 1.625 in | P1000 strut is 1-5/8 in square |
| Threaded Rod 1/2in-13 (×2) | ⌀ 0.500 in × 28.25 in | 1/2-13 all-thread |
| C-Type Beam Clamp (×2) | 2.80 × 1.50 × 2.97 in | B3033 |
| overall span | 36.00 in | "36in span" in the assembly description |

`fill` per part — the approximation, measured:

| part | fill | why |
|---|---|---|
| Threaded Rod | **0.98** | a rod really is its cylinder |
| End Cap | **1.00** | a solid block |
| C-Type Beam Clamp | 0.47 | a C profile in a rectangular prism |
| Channel Nut | 0.49 | chamfers and the spring gone |
| Strut Channel | **0.20** | the C-channel is hollow; the prism is its envelope |
| Rod Hardware (nuts + washers) | 0.18 | discrete nuts spread over 4.6 in, one prism |
| Stitch Weld | 0.08 | intermittent 3 in @ 6 in o.c. beads, one prism |

So: **the assembly is dimensionally right and the massing is honest about being a
massing.** Nine of thirteen parts are envelopes and the file says so, per part, in
numbers.

Gates (fresh clone, this branch):

- `tests/test_ifc_assembly.py` — **24 passed** (0.8 s), no samples needed
- `tests/test_router.py tests/test_ifc_family.py tests/test_ifc_intent.py` — **154 passed, 12 skipped**
- `tests/test_famgen_factory.py tests/test_frontdoor.py` — **142 passed, 10 skipped**
- `tools/sync_plugin.py --check`, `plugin/scripts/validate_plugin.py`,
  `tools/dev/check_portable_paths.py` — see BRANCH STATE

No regression in the two existing lanes: the Eaton product IFC still returns
`1 catalog family .rfa`, the Chicago room IFC still returns `9 catalog family .rfa`,
both through `intent->rfa` with the identical step list.

## Finding: the archetype lane was already donor-gated on a fresh clone

Worth recording because it changes what a stranger sees. Before this branch,
`plugin/skills/tekton-author/examples/chicago-plenum-downlight.ifc` — our own shipped
example — did **not** produce a family on a fresh clone:

```
FAILED (rfa-emit: FileNotFoundError: family container source not found:
        looked for: vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa)
```

The downlight archetype wants a family container out of the quarantined `vendor/`
corpus, which by design is not in a clone. After this branch the same file delivers a
1-part donor-free `generic_model` instead of failing — which is the direction
S-2026-08-10-c points ("where a donor still changes output that difference is
eliminated or recorded as an honest known gap"). On a machine that *does* carry the
corpus the archetype still wins, because the fallback only runs on a raised step.
**That difference — archetype with corpus, generic massing without — is now a recorded
known gap rather than a silent one.** The clean fix is #498's own DONE: the downlight
archetype emitting on the bundled base with no donor at all.

## Open questions / follow-ups (task-shaped, for the queue)

1. **Rotation in the part contract.** `add_generic_part` extrudes in Z only, so a body
   whose natural axis is X or Y is massed by its bounding prism. A per-part
   `rotation_deg` (or an axis) would make the strut channel's *own* C-profile
   expressible and lift its fill from 0.20 toward 1.0. Touches `famgen` — its own issue.
2. **Slab decomposition.** One IFC product → several stacked prisms where the
   cross-section changes with height, and disjoint projected regions → separate parts.
   This is what would capture a C-channel or a hex nut properly. Needs connected-
   component labelling on the projection; the honest metric (`fill`) to judge it by
   already exists.
3. **Swept/CSG bodies.** The lane needs tessellation. An IFC of `IfcExtrudedAreaSolid`
   is skipped by name today; most authoring tools can re-export as a mesh, but reading
   a swept profile directly is a natural extension of `ifc->parts`.
4. **No viewer certification.** Rule 4: this `.rfa` is validator- and provenance-gated,
   **not** certified. No standalone `.rfa` of ours is in the ledger. A batch should be
   STAGED for a viewer round before the matrix claims more than it does today.
5. **Psets are read but not carried.** `Pset_ManufacturerTypeInformation` (PartNumber,
   Reference) rides on all 13 products and is currently dropped. Mapping it to family
   parameters would make the output schedulable — a clear next win.

## BRANCH STATE

Files written:

- `src/rvt/ifc/assembly_parts.py` — new (the measurement; ~470 lines)
- `src/rvt/frontdoor/router.py` — `_r_ifc_to_rfa` fallback + `_assembly_rfa` lane
- `src/rvt/frontdoor/matrix.py` — `ifc->parts` stage + the honest `ifc -> rfa` cell
- `tests/test_ifc_assembly.py` — new, 24 tests, sample-free (synthesises its IFCs)
- `tests/ci_shard.d/498-ifc-assembly.txt` — shard drop-in (never `ci_shard.txt`)
- `docs/inbox/ifc-assembly-rfa.md` — this record

Staged, not shipped: no viewer batch reserved or staged (needs a `/batches` reservation
and a human upload). Nothing in `docs/coverage/viewer-certified.json` was touched.

---

# Round 2 — "needs touch ups": what the follow-ups actually cost

The owner reviewed the hanger `.rfa` ("it did pretty well … still needs touch ups")
and then asked for all four recorded follow-ups now. Two landed, one is a measured
refusal, one is untouched. In order of what was learned.

## 1. Slab decomposition — LANDED, with two guards that earn their keep

`decompose_slabs` cuts a body at its vertex Z levels and authors each slab's REAL
section (`slice_loops` → welded rings, `ring_nesting` → even/odd hole depth), merging
unchanged slabs so a plain rod stays one part.

The first working version looked like a triumph and was wrong:

| product | fill before | fill "after" |
|---|---|---|
| Strut Channel P1000 | 0.20 | **1.09** |
| C-Type Beam Clamp | 0.47 | **1.09** |
| Channel Nut | 0.49 | **1.17** |

A fill above 1.0 is not a better model — it means the authored solid holds LESS
material than the mesh it came from. Tracing it: the strut's slabs carry 21 rings
(the punched slots) with 4 vertices of degree ≠ 2, and the reconciliation was
`sum(net area × h) = 15.6 in³` against a mesh volume of `18.8 in³`. Rings were being
lost and mis-nested, and the pretty number hid it.

Two guards now stand in front of the result:

* **Ambiguous slices are refused.** Any welded vertex with degree ≠ 2 (two regions
  touching at a point, the plane grazing an edge) means the ring set is not determined
  by the segments. `_stitch` returns None and the whole decomposition is discarded.
* **Material must be conserved** (`_conserves`). Filling a hole the part contract
  cannot express only ever ADDS volume; authoring *less* than the mesh holds proves a
  ring was mis-nested or a region went missing. Discarded regardless of fill ratio.

With the guards, the hanger decomposes exactly where it is right and nowhere else:

```
DECOMPOSED  Rod Hardware (nuts + washers) - A   5 solids / 5 slabs   fill 0.18 -> 1.01
DECOMPOSED  Rod Hardware (nuts + washers) - B   5 solids / 5 slabs   fill 0.18 -> 1.01
KEPT PRISM  Strut Channel P1000 (x2)   not decomposable into horizontal slabs …
KEPT PRISM  C-Type Beam Clamp (x2)     not decomposable into horizontal slabs …
KEPT PRISM  Channel Nut (x2)           dropped material (0.592 in3 authored vs 0.693 in3 in the mesh)
```

13 products → **21 solids**. The rod hardware is now five discrete nuts and washers
instead of one 4.6-in cylinder at 18 % fill. Every refusal is named with its reason in
`assembly-parts.json` and in the route's caveats.

**A bug the tests caught, not the demo:** `ring_nesting` originally tested containment
with each ring's *interior* point. For a ring that CONTAINS others, that point sits
inside its own children, so an outer boundary scored depth 2 and would have been
dropped as a hole. Disjoint rings must be tested with a boundary VERTEX. Found by
`test_ring_nesting_marks_a_hole_odd_and_its_island_even`.

## 2. Per-part rotation — NOT DONE, deliberately, and now honestly labelled

This is the strut channel's 0.20 fill, and it is the one item where the right answer
was to stop. `add_generic_part` extrudes along Z only. The C-profile is constant along
**X**, so horizontal slabs cut across it — no amount of slicing expresses it.

Rotating the extrusion means giving `new_sketch_plane` a non-identity 3×3 while it is
bound to the level datum (`OnDatumPlaneRef.m_datumPlaneId`). That is exactly the class
of internal inconsistency the open cell (`genesis-audit.md` #31–#48) is about, it
cannot be certified from a cloud session (rule 4), and a wrong answer here is a family
Revit rejects rather than an obvious error. Filed as its own issue instead; the
decomposition guard means the strut is now *labelled* an envelope rather than silently
mis-modelled.

## 3. Psets → family parameters — LANDED for identity, with an unverified tail

`Pset_ManufacturerTypeInformation` is read per product into a bill of materials and
authored onto the family type verbatim (`make_generic_model(identity=…, text_params=…)`,
an additive factory change). The hanger yields real part numbers:

```
P1001 x2 (strut)  ·  WELD  ·  P2860 x2 (end caps)  ·  B3033 x2 (beam clamps)
ATR-1/2 x2 (rod)  ·  P1010 x2 (channel nuts)  ·  HN-1/2 x10 (rod hardware)
```

`Assembly Tag = TH-B2B-36`, `Source IFC`, `Part Numbers` are authored as text
parameters; `manufacturer` is left **empty** because the source has no Manufacturer
property — absent stays absent.

**Honest limit found while verifying, do not overclaim:** the parameter CAPTIONS reach
`Partitions/0` in the written file, but the type row's TEXT VALUES could not be found
in any inflated stream. This is **not** specific to this change — a catalog panelboard
built through the same `add_type` path behaves identically (`Mains` caption present,
`Eaton` / `PRL` / `225` absent). So "the family schedules its part numbers in Revit"
is **unverified**; what is verified is that the parameters and values are authored on
the document (asserted in-memory) and the captions persist. Whether type-table text
values round-trip through the writer is a pre-existing question for the famgen path,
and it needs a desktop check.

## 4. Swept / CSG bodies — NOT STARTED

`IfcExtrudedAreaSolid` and friends are still skipped by name. Unchanged from round 1.

## Evidence (fresh clone, this branch)

- `tests/test_ifc_assembly.py` — **34 passed** (was 24; +10 for slicing, nesting,
  decomposition, the conservation guard, budgets and the sideways-section case)
- `test_frontdoor_json_strict + test_famgen_factory + test_router` — **261 passed, 13 skipped**
- `test_plugin_sync + test_bootstrap + test_coldstart + test_ifc_family + test_ifc_intent + test_frontdoor` — **129 passed, 9 skipped**
- `sync_plugin --check` clean · `validate_plugin` PASS (25) · portable paths ok (2957)
- The hanger: **21 solids**, `.rfa` VALID 0 errors, provenance clean, release 2026

## BRANCH STATE (round 2)

Files touched on top of round 1: `src/rvt/ifc/assembly_parts.py` (slicing, nesting,
decomposition, guards, psets/BOM), `src/rvt/famgen/factory.py` (additive `identity` /
`text_params` on `make_generic_model`), `src/rvt/frontdoor/router.py` (BOM + caveats,
and the `_jsonsafe` fix CI caught), `tests/test_ifc_assembly.py`, this record.

Still open, unchanged: no viewer certification is claimed; rotation and swept solids
are follow-ups; the type-text-value question above is new and belongs to famgen, not
to this lane.

---

# Round 3 — the strut channel's 0.20 fill is closed, and rotation was never needed

Round 2 recorded per-part rotation as the fix for a section that runs along X, and said
it needed a desktop Revit check to do safely. **That framing was wrong**, and the
correction is the whole of this round.

## The insight

A C-channel is a **union of axis-aligned boxes** — a web plus two flanges. Every one of
those boxes is a plain Z-extruded rectangle, which `add_generic_part` already expresses,
*whichever direction the channel runs*. The extrusion axis of the individual box has
nothing to do with the axis of the channel. So the fix needed no rotation, no
non-identity 3×3 on a datum-bound sketch plane, and no desktop verification to be safe:
it uses the same proven primitive the certified families already use.

Checking the hanger's meshes bore this out immediately — the struts and end caps are
axis-aligned polyhedra:

```
product                                    axis-aligned?   distinct X/Y/Z   grid cells
Strut Channel P1000 (x2)                          True         38/ 6/ 4          555
End Cap (x2)                                      True          2/ 2/ 2            1
C-Type Beam Clamp / rod / nuts / weld            False           …                 …
```

## What was built

`is_axis_aligned` (every face normal parallel to an axis) gates a new `decompose_boxes`:
the body's own vertex coordinates cut space into a grid whose every cell is *wholly*
inside or outside it — that is what axis-aligned means — so one point test per cell
classifies it exactly. Occupied cells are merged greedily into maximal boxes. For a
non-axis-aligned body the function returns None rather than a staircase.

## Two real defects found on the way, both by disbelieving a good-looking number

**1. Parity ray-casting is wrong for welded assemblies.** The first inside-test cast a
skew ray and counted crossings. It reported the strut at ratio 1.139 — authoring less
material than the mesh holds. The strut mesh has **2 non-manifold edges**: "back-to-back"
is two shells welded along a seam, and a ray crossing an *internal* face flips parity, so
solid material reads as empty. Replaced with the **generalised winding number** (sum of
signed solid angles), which is unaffected by internal faces.

**2. Face orientation is the exporter's choice.** With winding in place, *nothing*
decomposed — including the End Cap that had been exact. This IFC winds its triangles so
that inside reads **−1**, not +1. The test must use the magnitude, exactly as
`mesh_volume` already does. One-line fix, total behavioural difference.

## And a finding that changes numbers already shipped

After both fixes the strut still read 1.065 — authored 17.670 in³ against a mesh volume
of 18.820 in³. Bucketing every grid cell by winding number settled it:

```
cells by |winding|:   {0: 202,  1: 241,  2: 112}
volume by bucket:     {0: 77.39, 1: 16.52, 2: 1.15}  in3
union volume            = 17.6703 in3   <- exactly what the boxes authored
sum with multiplicity   = 18.8202 in3   <- exactly what mesh_volume reports
```

The two shells genuinely **overlap** by 1.15 in³. `mesh_volume` is a
multiplicity-weighted sum, **not a union measure** — so for any multi-shell mesh the
`fill` ratios this stream has been reporting (including in the merged PR #556) are
**understated**: their numerator double-counts the overlap. The strut was never really
"20 % full"; its envelope was over-stated by the metric as well as by the massing.
`decompose_boxes` now reports `overlap_ft3` so the discrepancy is visible per product
rather than mysterious, and the box lane's own fill is 1.0 by construction.

## Result on the hanger

| product | before | after |
|---|---|---|
| Strut Channel P1000 - Top | 1 prism, fill 0.20 | **59 boxes, exact** |
| Strut Channel P1000 - Bottom | 1 prism, fill 0.20 | **23 boxes, exact** |
| End Cap ×2 | 1 box, fill 1.00 | unchanged (already exact) |
| Rod Hardware ×2 | 5 slabs, 1.01 | unchanged |
| Channel Nut ×2 | 1 prism, 0.49 | 2 slabs, 1.01 |
| Beam Clamp ×2, Stitch Weld | envelope | unchanged, still labelled |

13 products → **103 solids**, `.rfa` 408 KB, **VALID 0 errors**, provenance clean,
release 2026, 7.2 s end to end. The two struts merge to different box counts (59 vs 23)
because they are mirror images and the greedy merge runs in coordinate order; both
reproduce the same exact union volume.

Still honest envelopes, unchanged and still labelled: the C-Type beam clamps (a curved
casting), the stitch weld (intermittent beads), the threaded rods (a cylinder at 0.98,
which is right).

## Evidence

- `tests/test_ifc_assembly.py` — **43 passed** (was 34): axis-alignment, winding sign
  independence, exact box decomposition, the C-channel case, overlapping shells measured
  as a union, curved bodies refused, budgets refused not truncated.
- `test_router + test_famgen_factory + test_frontdoor_json_strict + test_ifc_family +
  test_ifc_intent + test_frontdoor + test_plugin_sync` — **380 passed, 22 skipped**
- `sync_plugin --check` clean · `validate_plugin` PASS · portable paths ok (2957)

One test was RETIRED rather than fixed: `test_a_body_whose_section_runs_sideways_keeps_
its_prism` asserted the limitation this round removes. It is replaced by
`..._is_now_exact_not_an_envelope`.

## BRANCH STATE (round 3)

Branch `claude/ifc-exact-box-decomposition`, cut from `main` at 152d009 (NOT stacked on
the merged branch). Files: `src/rvt/ifc/assembly_parts.py` (winding number,
`is_axis_aligned`, `decompose_boxes`, the box lane preferred over slabs),
`tests/test_ifc_assembly.py`, this record.

Unchanged and still open: swept/CSG bodies are skipped by name; the famgen type-row
text-value question from round 2; **no viewer certification is claimed** (rule 4) — the
`.rfa` is validator- and provenance-gated only, and a desktop or viewer check is still
the only thing that can say "Revit opens it".

## DESKTOP VERDICT (owner, 2026-08-10) — it opens, and the slots are there

The owner opened `Back-to-Back_Trapeze_Pipe_Hanger_-_LOD_400.rfa` (the round-3 build:
13 IFC products → 103 solids, 408 KB, release 2026) in **desktop Revit** and reports,
verbatim:

> "it opened and all the slots for the channel are in"

This is the arbiter, not our validator (hard rule 4). What it establishes:

1. **A donor-free, self-generated multi-solid family opens in desktop Revit.** Not a
   loaded project, not a catalog family — a `generic_model` composed entirely from a
   caller's IFC mesh, with `PRODUCT_AUTHOR_PLACEHOLDER` identity and zero donor bytes.
   That is #498 / S-2026-08-10-c's own goal demonstrated on a real vendor file.
2. **The exact box decomposition is right in the only way that counts.** The strut's
   punched slots are *visible in Revit* — those slots exist only because
   `decompose_boxes` classified 555 grid cells with a winding-number test and merged the
   occupied ones into 59 (and 23) maximal boxes. A parity ray-cast would have filled
   them in; the round-2 envelope would have been a solid bar. The geometry a human sees
   matches the geometry the numbers claimed.
3. **103 solids in one family is a workable size** — it opened, rather than choking.

What it does NOT establish, and must not be written up as if it did:

* it is **not** a ledger certification. `docs/coverage/viewer-certified.json` records
  `probe_batch` rounds — a certified base plus a byte-identical control per batch — and
  this was a single hand-opened file with no control. The ledger stays untouched.
* the Revit **year** of the desktop that opened it is not yet recorded here, and the
  file is a 2026 build; nor is it recorded whether Revit raised warnings on open, or
  whether the family loads into a *project* and places (a separate step from opening).
  Those are asked, not assumed.

Recorded because it is the first desktop confirmation this stream has, and because it
retires the one remaining reason to doubt the box lane: the slots are the visible
signature of a correct decomposition.

## RETRACTION + a confounded ladder (owner, 2026-08-10) — steer #585

Two things I got wrong, recorded before anything is built on top of them.

### 1. The loader-built `.rvt` was not "a working path today". Retracted.

I sent a project our own four-registry loader had built with the family in it, and called
it a working path that bypasses `Insert > Load Family`. The owner's verdict: **it did not
open**, and:

> "stop that thats not the way we solve these issues"

Two failures in that, not one:

* **Routing around Revit's own path is not a fix.** It hides the defect behind a lane the
  user did not ask for. Logged as steer #585.
* **I called a file usable on the strength of `VALID / 0 errors`.** That is hard rule 4
  restated the hard way — our validator is not the arbiter — and I broke it on a file I
  handed over as a solution. The project-validator result stands as a fact; "so it works"
  never followed from it.

The loader lane's own failure to open is **negative evidence against that lane**, and
belongs with the open cell rather than being quietly dropped.

### 2. The crash ladder was CONFOUNDED. My own README's claim was false.

`build_ladder.py` says "the only difference between L1 and L2 is the NUMBER OF SOLIDS".
It is not:

| rung | solids | shape mix |
|---|---|---|
| L1 | 13 | 9 box + 4 cylinder — **no polygons** |
| L2 | 103 | 87 box + 2 cylinder + **14 polygon** |

L1 → L2 varies solid count **and** introduces N-gon parts. The repo's own evidence
discipline is single-variable experiments with matched pairs, and this was neither.

Owner's results: **L0 (1), L1b (4), L1 (13) all load. L2 (103) crashes.** That is real and
useful — but it narrows the cause to *"something that appears between 13 and 103 solids"*,
which is **count or N-gon parts or both**, not "it is scale" as the README's decision table
asserts. That table is wrong as written and must not be read as settled.

Measured while checking (no Revit needed):

```
rung   solids  elements  id range      classes at L2
L0        1       102    1000..1101    CurveElem 588, SketchPlane 109,
L1b       4       113    1000..1112    VarSketch 103, ExtrusionElem 103
L1       13       168    1000..1167
L2      103       982    1000..1981
```

One hypothesis is already weakened by reading the code rather than guessing: N-gon parts
do **not** ship the regeneration representation any more (#515 removed that fallback), so
polygons and boxes both carry a cached B-rep. That makes shape mix less likely than count
— but "less likely" is not "excluded", and the ladder as built cannot tell them apart.

A clean pair would be **N boxes only** at rising N (13 / 40 / 87 / 103, one shape type
throughout), which isolates count with nothing else moving. Not built here: the owner has
called a halt to how this was being approached, and the next step is theirs to set.

## THE CRASH, NAMED (Revit journals 0040/0041/0042, owner, 2026-08-10)

Revit 2026.5 (Build 20260731_1210) journals. Journal **0040** carries the crash:

```
'onCommand Load a family into the project
'inTransaction MFCdocUI_1:-1 Load Family
'C 10-Aug-2026 18:48:00.888;  DBG_WARN: Invalid idx in VarSketch::getCurveObj:
    line 634 of F:\Ship_5_0\2026_px64\Source\Essentials\EssentialsDB\Sketch\VarSketch.cpp.
'C 10-Aug-2026 18:48:00.889;  captureTryCrash 0xc0000005
```

`0xc0000005` is an access violation, one millisecond after the warning. The file is the
103-solid hanger; it had already **opened** fine in the same session
(`FormOrAbandon::openFromModelPath` succeeded, views drew) — the crash is on `Load Family`
only, exactly as reported.

### We have met this error before, and our own source says so

`src/rvt/famgen/geometry.py` (`new_var_sketch`) already documents this signature verbatim:

> SOLVER STATE (issue #333, desktop round 26 -- the value-edit law): regen resolves each
> curve through `VarSketch::getCurveObj`, which indexes `m_elemRecs`; an empty solver
> "[H: Revit re-solves on edit]" is FALSIFIED -- editing any family parameter raised
> "Invalid idx in VarSketch::getCurveObj (VarSketch.cpp:634)" + the serious-error dialog.

Round 26 hit it by **editing a parameter**; this hits it via **Load Family**. Same
function, same line, same index failure. So this is not a new mystery — it is the #333
law being violated again by some sketch in this document, on a second trigger.

### What the journals also settle: the matched pair was NOT load-tested

Journals 0041 and 0042 record `onCommand Open an existing project` **only** — no
`Load Family`, no `captureTryCrash`:

| journal | files | operation | result |
|---|---|---|---|
| 0040 | hanger 103 solids | open, then **Load Family** | **CRASH** |
| 0041 | L0, L1b, L1, and the loaded .rvt | open only | no crash |
| 0042 | `P_boxes103`, `P_polys14` | open only | no crash |

So **count vs N-gon is still unanswered** — the deciding operation was never run on the
pair. (The `..._loaded.rvt` also appears in 0041 with no crash recorded, which does not
match "it did not open"; worth a second look, but the steer stands regardless.)

### Ruled out from the file side, with evidence rather than guesses

Chased and eliminated, each by direct measurement on the crashing document versus the
loading one:

* **the hard-coded solver pid layout** (`seg_pid = 4 + n + i`) — verified against
  `assign_pids` for rectangles and 3/5/7/12/24/48-gons: pids match and every constraint
  weakref lands on a `VarSketchLineSegObj`. Holds at every shape and count.
* **duplicate element ids** — none, in either document.
* **curve references dangling** — every `m_curveObjIdxMap` entry names a `CurveElem` that
  exists in the document.
* **spurious PP joins from coincidence detection** — `_corner_joins` pairs *any*
  coincident endpoints including non-adjacent edges, which a sliced ring could plausibly
  trigger; measured across all 14 polygon parts of the hanger: **0** non-adjacent
  coincidences.
* **the arc/cylinder sketch quirk** (`m_absorbedCurves != m_elemRecs` on cylinder sketches,
  2 findings per cylinder) — present in the 13-solid document too, which loads. Not
  sufficient to crash.
* **`TRUSTED_MAX_ID = 1450`**, which sits temptingly between the max element id of the
  loading document (1167) and the crashing one (1981) — it is a **class-id** heuristic in
  a name table, unrelated to element ids. Coincidence, not mechanism.

Also read off the journal, incidentally: `Rvt.Attr.Username: rvt-writer` — the placeholder
identity survives into the shipped file as intended — and Revit's expected third-party
dialog ("saved by an application that was not developed or licensed by Autodesk").

### Where this goes next

The failing structure is named (`m_elemRecs` indexing inside a `VarSketch`) and the
governing law is already written down (#333). What is not yet known is **which** of the
103 sketches violates it. Two cheap next moves, in order: run `Load Family` on the
existing pair (it costs two clicks and separates count from N-gon), and bisect the hanger
by halves if the pair comes back inconclusive.
