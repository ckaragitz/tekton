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

## ROOT CAUSE: an arc sketch promises curves its solver does not hold (#589)

The matched pair came back — both loaded, confirmed present in the family browser, with
only Revit's expected "saved by an application not developed or licensed by Autodesk"
warning. That exonerates the two hypotheses the pair was built to test and leaves exactly
one difference:

| family | sketches whose curve index map is LONGER than its solver records | Load Family |
|---|---|---|
| `P_boxes103` — 103 boxes | 0 | **loads** |
| `P_polys14` — 14 N-gons | 0 | **loads** |
| hanger — 87 box + 14 polygon + **2 cylinder** | **2** | **CRASH** |
| hanger 13-solid — 9 box + **4 cylinder** | **4** | never load-tested |

**Count is exonerated** (103 solids load). **N-gons are exonerated** (they load). The two
cylinders are the whole difference, and the structure is unambiguous:

| shape | absorbed curves | `m_elemRecs` | `m_curveObjIdxMap` | constraints | serFlags |
|---|---|---|---|---|---|
| box | 4 | **4** | 4 | 8 | 32 |
| polygon | 5 | **5** | 5 | 10 | 32 |
| **cylinder** | 2 | **0** | **2** | 0 | 1 |

`VarSketch::getCurveObj` indexes `m_elemRecs` through that map. The map names indices 0
and 1; the array is empty; the read goes out of range. That is `VarSketch.cpp:634` —
**the exact law issue #333 established for line sketches, which the arc path never got.**
#333 reached it by editing a parameter; `Load Family` reaches it too. Filed as **#589**.

### The correction to my own earlier reading

I had written "1, 4 and 13 solids load" into the record and into a decision table. The
journals show journals 0041/0042 ran `Open an existing project` **only** — L0, L1b and L1
were opened, never load-tested. The 13-solid family contains **four** cylinders, so on this
mechanism it should crash too. "It opens" was never evidence about loading, and I treated
it as if it were.

### The fix shipped here, and its boundary

`CYLINDER_AS_POLYGON`: a round profile is still **measured** as a cylinder — the report
still says "cylinder, ⌀0.500 in", the honesty of the measurement is untouched — but it is
**authored** as the mesh's own N-gon hull, which travels the proven line-segment path. It
is also *closer to the source* than an idealised circle, because a tessellated rod arrives
as an N-gon in the first place. The hanger now emits 87 box + 16 polygon, **0** sketches
promising more than they hold, `.rfa` VALID 0 errors, provenance clean.

This is a workaround at the lane, not a fix at the engine. #589 owns the real fix
(author the arc solver records) and needs a desktop verdict to close; the interim is
pinned by two tests so it cannot be mistaken for one:

* `test_an_arc_sketch_still_ships_an_empty_solver_the_engine_bug` — PINS the defect and
  flips when #589 lands.
* `test_the_assembly_lane_never_emits_a_sketch_revit_cannot_load` — the invariant that
  would have caught this before a human ever opened Revit: whatever this lane measures,
  the family it hands the factory must not contain a sketch promising curves its solver
  cannot resolve.

Still unproven until desktop says so (rule 4): that the rebuilt hanger actually loads.

## DESKTOP VERDICT on the arc solver (owner, Revit 2026, 2026-08-10) — #589 mechanism CONFIRMED

| rung | `m_params` per arc | Load Family into a new project |
|---|---|---|
| `A5_cylinder` | `[cx, cy, r, ang0, ang1]` | **loads** |
| `A3_cylinder` | `[cx, cy, r]` | **loads** |
| `A0_cylinder` | *(empty — pre-fix control)* | **CRASHES** |

**The control is what makes this a result.** A0 is the old empty solver and it still dies,
so the two passes cannot be credited to anything else that changed between builds: the
mechanism is exactly the one the journal named — `m_elemRecs` empty while
`m_curveObjIdxMap` names the arcs, an out-of-range read in
`VarSketch::getCurveObj` (`VarSketch.cpp:634`).

### What the pair does NOT settle, and I am not going to pretend otherwise

**Both layouts load, so loading does not discriminate between them.** What the parameter
vector actually governs is how the sketch *flexes* — and that is precisely how #333
surfaced in round 26: not on load, but on **editing a parameter**. A wrong-but-well-formed
vector can load perfectly and misbehave the moment the family is driven.

`ARC_SOLVER_PARAMS` therefore stays at **`center_radius_angles`** (A5) on principle rather
than on this evidence: it matches the arc's real degrees of freedom, and the schema carries
`VarSketchArcEndAngleConstrObj(m_angle, m_end)`, a constraint that only means something if
the end angles ARE parameters. A3 is recorded as an equally load-clean alternative. The
test that would separate them is a **parameter-driven flex on a cylinder**, which is the
#333 trigger and is filed, not fudged.

### Result

`CYLINDER_AS_POLYGON` is back to **False** — the N-gon stand-in was only ever there because
arcs crashed. The hanger is authored as measured again: **87 box + 2 cylinder + 14 polygon**,
0 sketches promising more than their solver holds, `.rfa` VALID 0 errors, provenance clean.
The rods are true cylinders rather than 40-gons.

Two laws are now written down where the next session will hit them:

* `new_var_sketch_curves` carries one solver record per curve, of the class the file's own
  schema gives (`GArc` → `VarSketchArcObj`, `GLine` → `VarSketchLineSegObj`), with the
  guess cache declaring the same parameter vector.
* `test_the_assembly_lane_never_emits_a_sketch_revit_cannot_load` is the invariant: a map
  longer than its records is an out-of-range read inside Revit, and no lane may ship one.

## DESKTOP VERDICT: the parametric drive does NOT work on a generic family — stopped here

Owner, Revit 2026: `parametric_cart` (a driven box deck plus four true cylinder wheels)
— *"parametric cart did not work what so ever"*. The family builds, validates VALID with
0 errors and carries the whole #372 chain (4 side RefPlanes, 4 Alignments registered in
`VarSketch.m_dimIds` / `m_dimData`, labeled Width/Height `LinearDimString`s at the type's
values) — and none of that makes it editable in Revit.

**Structural validity is not behaviour.** That is hard rule 4 for the third time today, and
the third time it was worth having: the validator cannot tell us a family flexes, only
Autodesk's reader can.

`drive` is therefore **off by default** again. Generated families keep exactly the shape
that IS desktop-verified — they open, and they load into a project. The hook stays
(`make_generic_model(drive=True)`) as the starting point for whoever picks this up, along
with what is now known:

* the drive chain applies to a one-box generic model *structurally* — `param_drive` needs
  a 4-line rectangular profile and a plain box already is one, so nothing had to be
  generalised to attach it;
* attaching it is not sufficient. What is missing is behavioural and unmeasured: whether
  the labeled dimension needs a different witness geometry in a family with several
  forms, whether the alignments must name a different sketch plane, or whether a
  multi-solid family needs each solid constrained rather than one.

## Where the four requirements actually stand

| requirement | state |
|---|---|
| Round bodies — wheels, axles, rotated profiles | **DONE, desktop-verified.** True cylinders on a horizontal axis; Front elevation a clean circle. The cached B-rep is what Revit draws (rounds 1–4). |
| Detail by default | **DONE.** Detail is the parts a model emits; the contract carries multi-part objects and refuses bad ones by name. |
| Anything from a prompt | **Contract done.** `parts` in the famspec schema; a 40 ft bus with named solids builds donor-free. The *interview* that turns "make a bus" into that spec is designed, not written. |
| Edit anything after loading | **NOT DONE, and now known to be harder than attaching the drive.** See above. |
| True spheres | **NOT DONE.** `SphereData` is a geometry fingerprint, not a primitive, and the schema has no sphere surface — so it needs `RevolutionElem`, a new element class with no donor to measure. Stacked discs remain, honestly labelled. |

# tech-lead pre-merge fix (eng #609) — 2026-08-11

*Written by engineer session eng #609 (issue #609), on top of `a3506ad`, at the tech lead's
request so #583 can be squash-merged with its author's attribution. Add-only: the sections
above are the author's and untouched.*

The independent merge review of #583 cleared phases 2–4 and found two reproducible PG1
regressions in phase 1 (`assembly_parts.py`): wrong geometry stamped `exact` / "improved".
Both reproduce through `read_assembly` and `route.py run --output rfa` with the test file's
own generators; both are closed here and pinned by tests.

## 1. The box lane called itself exact without checking — now it is held to the mesh

`is_axis_aligned(eps=1e-4)` is an *angle budget* of 0.8°: 1 − cos 0.1° = 1.5e-6 sailed
under it. A 900 mm strut (41 × 41 × 2.5 mm) yawed about Z then cut a grid out of its own
*rotated* vertex coordinates and came back as sliver boxes:

| yaw | a3506ad | this fix |
|---|---|---|
| 0.0° | boxes, 3 parts, authored/mesh 1.000, `exact` | **unchanged** (boxes, 3, 1.000, `exact`) |
| 0.1° | boxes, **13** parts (9 < `MIN_EXTENT_FT`), 1.013, `exact` | slabs, 3 rotated rectangles, 1.000 |
| 0.2° | boxes, **11** parts (8 < MIN), **0.499**, `exact` | slabs, 3, 1.000 |
| 0.5° | boxes, 9 parts (6 < MIN), **1.769**, `exact` | slabs, 3, 1.000 |
| 0.8° | boxes, 10 parts (2 < MIN), **3.037**, `exact` | slabs, 3, 1.000 |

(min authored extent 1.3e-5 ft on head vs 0.0082 ft = the wall after; `main` authors every
yawed case as the same 3 exact slabs.) Three guards, each sufficient for this case, because
"exact" is a claim worth over-determining:

* `is_axis_aligned` eps **1e-9** — float noise, not an angle: an aligned face has two normal
  components that are exactly zero.
* `decompose_boxes` refuses a grid with **any cell thinner than `MIN_EXTENT_FT`** in any axis
  — the signature of a nearly-aligned body, and a box Revit could not keep anyway.
* `read_assembly` accepts the box lane only when `vol is not None` and
  **|boxes + overlap − mesh| ≤ 1e-6 · mesh** (`EXACT_REL_TOL`); otherwise it falls through to
  slabs, then the prism — always delivered (rule 1). The cell guard bounds the welding noise
  this check can see: coordinates weld to 1e-9 ft, so a cell ≥ 0.0013 ft is perturbed by at
  most 2 × 0.5e-9 / 0.0013 = 7.7e-7 < 1e-6 relative; measured residual on the fixtures 3–5e-8.

## 2. A solid ring read as a hole — `ring_nesting` no longer trusts a vertex

Junction resolution (round 3's `_junction_pairs`) lets two solids touch at a point, so a
ring's first vertex can be the *shared* corner; `_point_in_ring(rings[i][0], other)` then
read a SOLID ring as depth 1 and `decompose_slabs` dropped it as a hole. `_conserves`' 2 %
slack hid any member under 2 % of the body. Sweep (7 corner configs × yaws × triangle
orders, which move the stitch start): **head 55 / 1085 runs authored less than the mesh with
no `kept_prism` and no caveat** (e.g. 6 m cube + 1×1×2 m member, yaw 5°: the member vanishes,
7628 vs 7699 ft³); `main` 0 / 1085.

* `ring_nesting` now probes with `_interior_probe`: the midpoint of the ring's longest edge
  nudged inward by 1e-6 of its length — strictly inside its own ring, outside every disjoint
  neighbour, never a vertex, and hugging the boundary so a ring that contains others is still
  not counted inside them. **After: 0 / 3360** (7 configs × 8 yaws incl. 0°, 45°, 0.05° × 60
  orders); every run decomposes (420 boxes, 2940 slabs), authored = mesh to 1e-6, zero prisms.
* Backstop: `decompose_slabs` reports `section_volume_ft3` (the sliced sections *before* the
  48-vertex cap) and `read_assembly` **refuses a slab set that filled no hole yet holds less
  than the mesh by more than 1e-6** → honest prism + "dropped material" caveat. Judging the
  undecimated sections keeps a capped 72-gon from being mistaken for a lost ring; the 2 %
  `_conserves` slack still applies on top (main parity for filled holes / overlapping shells).

## 3. Found on the way: the measurements were origin-relative

Tightening to 1e-6 exposed that `mesh_volume` summed tetrahedra about the **world origin** and
`_polygon_area` shoelaced about it too. Decomposition runs *before* `recentre`, i.e. at site
coordinates: an aligned strut placed 500 m out missed the box check (residual 2.7e-6), at 5 km
`mesh_volume` itself was 0.6 % off, at 50 km every lane collapsed to a 5.6× prism. Both now
sum about a local vertex (the theorem holds about any apex); the strut takes the same lane
with the same residual (3e-8) at 0 m, 500 m, 50 km and UTM-scale (500 km, 4800 km) offsets.
Same signatures, same tests, strictly more accurate.

## 4. The caveat names the lane

`router.py` (the one wording line): `box decomposition improved …` when `method == "boxes"`,
`slab decomposition improved …` otherwise — per record, so a mixed assembly reads right.

## Evidence

* Repros through `tools/route.py run --ifc … --output rfa --json`: strut 0.0/0.1/0.2/0.5/0.8°
  and the corner pair (yaw −5°, an order that lost the member on head) → 6 × `OK (3-part
  generic_model .rfa)`, methods boxes/slabs×5, **6 × `rvt_validate --family` VALID 0 errors
  (0 warnings), 6 × `make_family.py provenance` ok, 0 hits.** No certification claimed (rule 4).
* `tests/test_ifc_assembly.py`: **68 passed** (55 the author's, all green incl. the 0.0°
  exact-box tests, + 13 added: alignment eps, sliver grid, yawed channel ×4, box lane takes
  the unyawed strut AND is held to the mesh volume, shared-vertex nesting, interior probe,
  corner pair over 100 vertex orders × 2 yaws, no-hole loss refused, precision at site
  coordinates, caveat wording on a mixed assembly). All 13 fail on a3506ad's engine.
* Stream-local gate `test_ifc_assembly + test_router + test_famgen_factory + test_frontdoor`
  (`RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1`): a3506ad **329 passed / 24 skipped** → see BRANCH
  STATE for the after count and the merged shard.
* `route.py matrix` byte-identical to a3506ad (39 lines); `sync_plugin` synced 2 files then
  `--check` clean; `validate_plugin` PASS (25 assertions); portable paths ok (2981).

## Not touched, on purpose

famgen/**, standards, SKILL.md, the PR body, the author's tests and record sections. Still open
and filed elsewhere per #609's context list (#564 target-version fallback, `fit_solid` cylinder
misfit of yawed thin bars, face-contact loss on main too, duplicate-meaning standard params).
One thing this session could not measure: the real hanger sample is absent from a cloud clone,
so "Strut Channel P1000 → 59 exact boxes" was not re-run; by the noise bound above its
union + overlap should sit ~1e-7 from `mesh_volume` if its two shells are each closed — if they
are not, the box lane now declines the `exact` stamp and the strut goes to slabs/prism with a
caveat, which is the honest outcome.

## BRANCH STATE (eng #609)

Branch `claude/ifc-exact-box-decomposition` (PR #583), commits added ON TOP of `a3506ad` — no
rebase, no force-push, no merge of main. Files: `src/rvt/ifc/assembly_parts.py` (+ its
`plugin/lib` mirror via `sync_plugin`), `src/rvt/frontdoor/router.py` (the one caveat statement, +
mirror), `tests/test_ifc_assembly.py` (13 tests appended, none of the author's touched), this section.

Gates on the final tree (cloud session, fresh clone, no `samples/`):
* `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest test_ifc_assembly test_router test_famgen_factory
  test_frontdoor`: a3506ad **329 passed / 24 skipped → 342 passed / 24 skipped** (0 failed).
* Whole merged shard `pytest -q -p no:cacheprovider $(tools/dev/shard_list.py --print)`:
  **1986 passed / 134 skipped / 3 xfailed, 0 failed** (8 min 31 s).
* `/verify` (drive the router): strut 0.0/0.2/0.5° + corner pair → 4 × OK, boxes/slabs/slabs/slabs,
  caveat names the lane, authored/mesh = 1.0000000, VALID 0 errors, provenance ok. `/simplify` run on
  this diff (reuse `_conserves`/`_tri0`, simpler probe, one route run in the caveat test).
* `route.py matrix` unchanged · `sync_plugin --check` clean · `validate_plugin` PASS · portable paths ok.

Shipped vs staged: engine + tests shipped on the branch; nothing staged for the viewer, no ledger
entry, no certification claimed. Follow-up filed separately (per-lane volume ledger so a body that
DID fill a hole cannot hide a lost member inside the 2 % slack; `MIN_EXTENT_FT` handled three ways in
one file) — `Refs #609`.

## Round 2 (eng #609, after the tech lead's delta review of fc69382)

The independent review re-measured and accepted the substance (strut → 3 conserved slabs at
0.1–0.8°, boxes at 0.0°; 0 silent corner-pair losses; the local-apex sums; caveat wording; rule 1)
and sent back **two over-broad guards** — both the belt-and-braces parts, not the root-cause
fixes — plus a test nit. All three taken as asked:

1. **The strict no-hole slab backstop is REMOVED** (and `section_volume_ft3` with it); the slab
   lane keeps main's `_conserves(dv, vol)` 2 % envelope exactly. It had treated the lane's own
   declared approximations as lost rings — midpoint under-integration of a taper, skipped hairline
   Z levels, dropped slivers. Reviewer's cases, base a3506ad / fc69382 / this round:
   8-band reducer frustum: 8 slabs (0.9994) / **1 prism** / 8 slabs (0.9994) · 12-band cone: 12 /
   **1** / 12 · square pyramid frustum: 6 / **1** / 6 · U-strut with a 50 µm flange mismatch at 0°:
   3 exact boxes / **1 bar** / 3 exact boxes, at 12°: 3 slabs / **1 bar** / 3 slabs · plate + 6 mm²
   pin yawed: plate (+sliver dropped) / **35 mm block** / plate. The by-construction identity that
   would make a lost ring impossible without penalising approximations stays with #613 (extended
   there: sliver / thin-level accounting).
2. **The box-lane extent guard moved from raw grid cells to the MERGED boxes**: a hairline grid
   step that merges away (the 50 µm mismatch) keeps the exact lane; only a produced box thinner
   than `MIN_EXTENT_FT` refuses it. eps 1e-9 + the 1e-6 volume identity still stop the yawed-strut
   regression on their own (0.1–0.8° → 3 slabs, 1.000).
3. **The e2e corner-pair test now permutes triangle ORDER** (seeded `rng.shuffle`) on the member
   positions that actually trip a3506ad — (−3.5, +3.5) at 5°/12°/33°, (−3.5, −3.5) at −5°: 21 of
   its 160 runs lose the member on a3506ad (verified by running the file against that engine:
   `(-3.5, 3.5, 5.0)` → 2 parts, 7628 < 7699 ft³, no `kept_prism`), 0 on this head.

Tests (13 of mine, reshaped; the author's 55 untouched): the strict-backstop test is replaced by
`test_the_slab_lane_keeps_its_declared_approximations` (reducer ⇒ 8-solid stack; mismatch strut ⇒
boxes ×3 exact at 0°, 3 slabs at 12°) and the grid test by
`test_a_sliver_box_refuses_the_box_lane_a_hairline_step_does_not`. Cross-checked by swapping engines
under the same test file: **a3506ad 12 fail / 56 pass** (all by behaviour), **fc69382 2 fail**
(exactly findings 1 and 2), **this round 68 pass**.

Evidence on the final tree: `route.py run --output rfa` on strut 0.0/0.2/0.5°, mismatch 0°/12°,
frustum, cone, corner pair (an order that loses the member on a3506ad) → 8 × OK; parts
3/3/3/3/3/8/12/3; methods boxes/slabs/slabs/boxes/slabs/slabs/slabs/slabs; authored÷mesh
1.0000/1.0000/1.0000/1.0000/0.9996/0.9994/0.9983/1.0000; 8 × VALID 0 errors 0 warnings; 8 ×
provenance ok. Sweeps unchanged: strut 0.1–0.8° → slabs ×3 at 1.000; 3360 pair runs (half with
order shuffles) → 0 silent losses, |authored − mesh| ≤ 1e-6 every run; placements at 500 m / 50 km /
UTM → same lanes incl. the mismatch strut's 3 boxes. `test_ifc_assembly + test_router` 200 passed /
14 skipped; 4-file gate 342 passed / 24 skipped; `sync_plugin` → `--check` clean; `validate_plugin`
PASS; portable paths ok; `route.py matrix` identical to a3506ad.

## BRANCH STATE (eng #609, round 2)

Second add-only commit on `claude/ifc-exact-box-decomposition` on top of fc69382 (parent chain
a3506ad ← fc69382 ← this); no rebase, no force-push, no merge of main. Files this round:
`src/rvt/ifc/assembly_parts.py` (+ `plugin/lib` mirror), `tests/test_ifc_assembly.py` (my section
only), this record. `router.py` untouched this round. Nothing staged for the viewer; no
certification claimed.

## eng #620 (2026-08-11): a yawed thin bar is never a giant cylinder in `fit_solid`

**The defect (pre-existing on `main` at e621ab6, found by two reviews of #583).** `fit_solid` read a
hull as a CIRCLE on one test only: 8+ hull points whose radii about their centroid agree to ±12 %.
The corners of any long thin bar are all half a diagonal from its centre, so the moment a yaw's
rounding noise (hull weld at 1e-9, `%.6f` STEP text) keeps a few near-collinear points on the hull,
the bar has 8 "equidistant" hull points and fits a cylinder of r = half its LENGTH:

* in memory (`_yaw(_u_channel())`, `_strut(deg)`): the 4 × 1 × 1 m U at 5°/30° → **cylinder
  r = 6.73 ft (2.05 m), fill 0.085**; the 900 × 41 × 41 mm strut at 0.1°/12° → **cylinder
  r = 1.48 ft, fill 0.010**;
* through the IFC path (`write_ifc` → `read_assembly`, 0.25°…45° in 0.25° steps, both bodies):
  **72 of 360 reads (20 %) mis-fit as that cylinder** on `main`; which yaws hit depends only on
  coordinate noise;
* usually the slab lane rescues it (fill 0.01 → 1.00, three exact rotated rectangles), but when both
  lanes refuse **the cylinder is what ships**: a 2 m × 100 mm rail of 70 stacked plates (widths
  alternating by 2 mm → 70 Z levels > `MAX_SLABS`, yawed 10° → no box lane) routes on `main` to a
  1-part `.rfa` whose only solid is **an r = 3.28 ft drum, 6 % full, wider than the body's own
  bounding box** (`ASSEMBLY LANE: … (cylinder x1)`, `Rail 6%` envelope, `kept as a single prism`).

**The law now (`_fit_circle`, the only helper `fit_solid` gained; nothing else in the module
touched).** Equidistant hull points are necessary, not sufficient — the circle must also BE the
outline:

1. 8+ hull points with radii spread ≤ `CYLINDER_TOLERANCE` (0.12) — unchanged (the ≥ 8 guard just
   moved inside the helper);
2. **hull area ≥ `CYLINDER_MIN_PLAN_FILL` (0.85) × πr²** — the intrinsic roundness law, identical at
   every yaw: a regular 8-gon fills 90.0 % of its circle, a 12-gon 95.5 %, a 16-gon 97.4 %; the
   4 × 1 bar's corners fill 30 %, a 2 × 1 bar's 51 %, a chamfered square's 64 %;
3. **radius ≤ (1 + `CYLINDER_TOLERANCE`) × the body's smaller plan half-extent** — the authoring
   bound in the family's frame (the fitted solid never outgrows the mesh's own bounding box): a
   regular 8-gon's circumradius is 8.2 % over its apothem, so every real tessellation passes; the
   U's r = 6.73 ft against a 2.2 ft half-extent and the strut's 1.48 ft against 0.07 ft do not. Not
   redundant with law 2: a two-flat shaft fills 90 % of its circle yet is 25 % wider than its
   flats; and not sufficient alone: a 2 × 1 bar at 45° has a square bounding box and slips past it
   at 1.05 — law 2 refuses that one (51 %).

A hull refused as a circle falls through to the existing box / N-gon branches untouched, i.e. it is
authored as its own oriented envelope (the rotated rectangle, exact in plan).

**Why the floor is on PLAN fill and not on fill against the mesh volume** (the issue offered
"e.g. < 0.5"; it said choose and document, this is the choice). Law 3 *is* a fill floor — since the
cylinder and the hull prism share the height, `hull_area / πr²` equals the cylinder's volume fill
divided by the hull prism's, so a cylinder can never again hold less than 85 % of what its own hull
would — but it is deliberately not a floor on raw `mesh volume / cylinder volume`. That number
cannot tell a false cylinder from a hollow true one: a thin-wall conduit or copper tube is a genuine
cylinder holding 0.12–0.25 of its envelope (EMT ¾″ ≈ 0.20, type-M copper ≈ 0.12), the yawed U a false
one holding 0.085 — no threshold parts them, and 0.5 would have re-authored every hollow pipe,
today a true `cylinder` part, as a 32/48-gon extrusion of the same volume (the slab lane fills the
bore and is then "no closer than the single prism", so the kept prism is what ships for tubes).
The plan laws refuse both repros at every yaw with or without a mesh volume (`fill=None` inputs are
covered too) and leave every round outline alone.

**Before / after** (`fit_solid` on the fixture meshes in feet with their real `mesh_volume`;
"half-ext" = smaller plan half-extent of the bbox):

| body | e621ab6 (main) | this branch |
|---|---|---|
| U-channel 4×1×1 m, t = 0.1, yaw 5° | **cylinder r = 6.7276 ft, fill 0.0848** (half-ext 2.21 ft) | polygon (rotated 4×1 rect), fill 0.2800 |
| U-channel, yaw 30° | **cylinder r = 6.7276 ft, fill 0.0848** (half-ext 4.70 ft) | polygon, fill 0.2800 |
| U-channel, yaw 0° / 0.3° / 12° / 45° | box / polygon ×3, fill 0.28 | unchanged |
| strut 900×41×41 mm, t = 2.5, yaw 0.1° | **cylinder r = 1.4777 ft, fill 0.0102** (half-ext 0.070 ft) | polygon, fill 0.1755 |
| strut, yaw 12° | **cylinder r = 1.4777 ft, fill 0.0102** (half-ext 0.373 ft) | polygon, fill 0.1755 |
| strut, yaw 0° / 0.2° / 0.5° / 0.8° / 45° | box / polygon ×4, fill 0.1755 | unchanged |
| CONTROL pipe r = 50 mm, h = 1 m, 12-gon, yaw 0° / 7° / 13° / 22.5° | cylinder r = 0.1640 ft, fill 0.9549 | identical |
| CONTROL pipe 16-gon, yaw 0° / 7° / 13° / 22.5° | cylinder r = 0.1640 ft, fill 0.9745 | identical |
| rod r = 0.5, 40-gon · reducer frustum 32-gon | cylinder 0.9959 · cylinder 0.5796 | identical |
| regular N-gon prisms, N = 8/9/10/12/24/64/200 × yaw 0/5/11.25/22.5/30° | cylinder | cylinder (35/35) |
| chamfered 2×1 bar, chamfered 1×1 square (8 hull pts), yaw 0/20/45° | cylinder | box at 0°, polygon yawed |
| yaw sweep 0…90° × 0.25°, U + strut, in memory (722 fits) | cylinder at the noise-selected yaws | **0 cylinders**; fill ≥ 0.1755 / 0.28 at every yaw |

**Through the router** (`RVT_STEPLITE_FORCE=1 tools/route.py run --ifc X --output rfa --json`,
same IFC bytes on both trees; every branch output `rvt_validate --family` VALID 0 errors 0 warnings,
`make_family.py provenance` ok, findings []):

| IFC | e621ab6 | this branch |
|---|---|---|
| `strut_yaw2.ifc` (900 mm strut, 2°) | OK 3-part; `slab decomposition improved Strut (3 solids, fill 0.01 -> 1.00)` — the 0.01 is the phantom cylinder | OK 3-part, polygon ×3; `… fill 0.18 -> 1.00`; parts byte-for-byte the same three rectangles |
| `u_yaw4.ifc` (4×1 m U, 4°) | OK 3-part; `… U (3 solids, fill 0.08 -> 1.00)` | OK 3-part; `… fill 0.28 -> 1.00` |
| `tower_yaw10.ifc` (2 m × 100 mm rail, 70 plates, 10°) | OK **1-part (cylinder x1)**, `Rail 6%` ENVELOPE, kept as a single prism (slab lane over budget) — ships an r = 3.28 ft drum | OK **1-part (polygon x1), fill 0.99**, no envelope caveat, no decomposition attempted (0.99 ≥ `DECOMPOSE_FILL`) |
| `strut_yaw12.ifc`, `strut_yaw01.ifc`, `u_yaw30.ifc` | 3 slabs each (these yaws happen not to hit through `%.6f`) | identical parts; `fill_before` 0.1755 / 0.1755 / 0.28 |
| `pipe16_yaw7.ifc` (control) | 1-part cylinder r = 0.164 ft, fill 0.9745 | identical |

Transcript of the strut run on this branch (trimmed to the assembly caveats):
```
$ RVT_STEPLITE_FORCE=1 .venv/bin/python tools/route.py run --ifc strut_yaw2.ifc --output rfa --out br_strut_yaw2 --json
ok= True | OK (3-part generic_model .rfa measured from strut_yaw2.ifc)
  caveat: ASSEMBLY LANE: 3 IFC product(s) measured into prisms (polygon x3), overall 35.47 x 2.85 x 1.61 in; every dimension is GIVEN by your mesh …
  caveat: slab decomposition improved Strut (3 solids, fill 0.18 -> 1.00)
  parts: Strut [1/3] polygon 1.0 · Strut [2/3] polygon 1.0 · Strut [3/3] polygon 1.0   decomposed: Strut slabs 0.1755 -> 1.0   kept_prism: []
  validate: VALID (no errors); warnings=0 info=2      provenance: ok, findings []
```

**Knock-on, checked rather than assumed.** `fill_before` feeds two decisions in `read_assembly`:
whether to decompose at all (`< DECOMPOSE_FILL`) and whether the slab result beat the single prism
(`vol/dv < before + 0.02`). Both now compare against the body's real best prism instead of a
phantom 1–8 %, which is the intended meaning; every existing lane test is unchanged and green
(strut 0.1–0.8° → 3 slabs at 1.000, mismatch strut boxes/slabs, reducer 8 slabs, corner pairs, site
coordinates, caveat wording). No caveat text, no lane, no budget, no nesting code was edited.

**Tests** — appended to `tests/test_ifc_assembly.py` only (a new `eng #620` section; the 68
existing tests untouched): the two repros in memory (U at 5°/30°, strut at 0.1°/12° ⇒ polygon, no
`radius_ft`, fill = the unyawed body's), a 0…90° × 0.25° sweep of both bodies (never a cylinder,
envelope inside its own bbox), the control pipe (12/16-gon × yaw 0/7/22.5° ⇒ cylinder, r exact,
fill ≈ 1 and = N/(2π)·sin(2π/N)), the two refusals in isolation (chamfered 2×1 / 1×1 vs a regular
octagon), the lanes-off delivery of the U at 4° — a yaw that mis-fits through the IFC path on e621ab6 —
(polygon 0.28; lanes on ⇒ still 3 exact slabs), and
the end-to-end rail both lanes refuse (ships polygon 0.99, no `kept_prism`). Swapping engines under
the same file: **e621ab6 → 8 of the 14 new tests fail, all by behaviour (the 6 control-pipe
cases pass on both engines, as a control must), this head → 82 passed.**

## BRANCH STATE (eng #620)

Branch `cam/620-cylinder-fit-floor` from `main` @ 47296f1; one issue, one PR (`Closes #620`).
Files: `src/rvt/ifc/assembly_parts.py` (`CYLINDER_MIN_PLAN_FILL`, `_fit_circle`, the cylinder
branch of `fit_solid`, docstrings; +`__all__` entry) + its `plugin/lib` mirror via `sync_plugin.py`;
`tests/test_ifc_assembly.py` (appended section); this record section. Not touched: `router.py`
(eng #564), famgen, `route.py`, SKILL.md, any hot file, earlier sections of this record.
Gates: `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_ifc_assembly.py tests/test_router.py -q -rs`
main **200 passed / 14 skipped** (test_ifc_assembly 68) → branch **214 passed / 14 skipped**
(test_ifc_assembly 82); whole merged CI shard (`shard_list.py --print`) — see the PR body for the
count on the final head; `route.py matrix` byte-identical to main (sha256 7dae5d40…); 6 routed
`.rfa` VALID 0 errors + provenance ok; `sync_plugin.py` → `--check` clean; `validate_plugin.py`
PASS; `check_portable_paths.py` ok. Nothing staged for the viewer, no ledger entry, no
certification claimed (rule 4): "VALID" above is a fact about the files, not about Revit.

# eng #564 — `--target-version` survives the archetype → assembly hand-off (2026-08-11)

*Written by engineer session eng #564 (issue #564) on branch `cam/564-assembly-target-version`,
cut from `main` at 47296f1 (after #583's squash e621ab6). Add-only: every section above is
another author's and untouched.*

## The bug, reproduced on this head's parent

Fresh clone, `RVT_STEPLITE_FORCE=1`, no `samples/`. Two fixtures from this test file's own
generator: `one.ifc` = one 1.0 × 1.0 × 0.1 m box; `two.ifc` = that box + a 24-gon post.
`tools/route.py run --ifc X --output rfa [--target-version N] --json`, then `releases`, the
`target_version` block and `rvt.versions.detect_release` on the delivered bytes:

| input | flag | `main` 47296f1 | this branch |
|---|---|---|---|
| one.ifc | 2025 | `releases.rfa` **2026**, block `fallback`/2026, bytes 2026; caveat "target 2025 requested: this family emit cannot run at Revit 2025 yet (facts->rfa: FamFromIfcError: the IFC facts lack required housing geometry …)" — **twice** | `releases.rfa` **2025**, block `match`/2025, bytes **2025**; no "cannot run" caveat; status `OK (1-part generic_model .rfa measured from one.ifc) by the ASSEMBLY lane, after the archetype lane failed at facts->rfa` |
| one.ifc | 2024 | 2026 / `fallback` / bytes 2026, same dead-lane caveat twice | **2024** / `match` / bytes **2024** |
| one.ifc | (none) | 2026 / `unspecified` | 2026 / `unspecified` (unchanged but for the status suffix) |
| two.ifc | 2025 | 2025 / `match` / bytes 2025 | 2025 / `match` / bytes 2025 |
| two.ifc | 2024 | 2026 / `fallback` / bytes 2026, line names `famspec->rfa: KeyError: "class 'ArcElemCell' not in the archive class map"` | identical — a **genuine** fallback of the lane that DID produce the file (the post is an arc sketch; 2024 has no `ArcElemCell` port: already filed as #241, not re-filed) |
| two.ifc | (none) | 2026 / `unspecified` | 2026 / `unspecified` |

All six branch outputs: `tools/rvt_validate.py --family` VALID, 0 errors, 0 warnings, 2 info
(a fact about the files, not a claim that Revit opens them — rule 4; nothing certified here).

## Mechanism (confirmed, one correction to the issue text)

`_r_ifc_to_rfa` tries the archetype lane (`_product_rfa`) and, on `_StepFailed`, falls
through to `_assembly_rfa`. For a single product `ifc->facts` succeeds, so the failure
happens *inside* `_emit_at_target`: the Revit-N attempt raises, the degrade branch rewrites
the memoised block in place to `status: fallback / output_release: 2026`, re-points
`res._bases[N]` at the default base, appends its line as a caveat, copies the IFC beside as
the "version-agnostic addition" — and then the native re-run raises **too**. The lane
produced nothing, but its fallback story stayed behind. The assembly lane's own
`_emit_at_target` got the memo hit, saw `fallback`, skipped the release context, appended the
same line again and emitted native. With two products the archetype lane dies at
`ifc->facts`, *before* any release context, so nothing was poisoned — which is why that case
was right. Correction: on today's `main` the in-context failure is `facts->rfa:
FamFromIfcError` (a box has no downlight housing), not the vendor-donor lookup the issue
quotes from the #556 review sandbox; the mechanism is the same either way.

## The fix: `_emit_at_target` commits its version story only once the lane delivered

Of the two fixes the DONE allows I took the one inside `_emit_at_target` (the invariant "a lane
that delivered nothing leaves no version state behind" belongs to the function that mutates
that state; clearing it from `_r_ifc_to_rfa` would reach into four private effects and the
next multi-lane route would re-learn #564). First cut restored the state on a double failure;
the pre-commit review pointed out that nothing `emit()` runs reads the block, the memo, the
caveat or the IFC copy — the memo re-point only serves a LOAD that runs *after* the function
returns — so the final form is simpler: the degrade branch now only labels the failed attempt
and prepares the story (`status: fallback`, `output_release`, `pending`, the line); the native
`emit()` runs; **then** the memo is re-pointed at the default base, the block updated in place,
the IFC addition written, the clause settled and the line appended. If the native run raises,
none of that happens: no stale `fallback`, no dead lane's caveat, no orphan IFC copied into
`--out` (on `main` `one.ifc` was copied beside a file that then matched). The `refused` shim
follows the same order. A degrade whose native re-run succeeds ends in the identical state as
before (`test_famspec_target_version_field_and_flag`'s 2023 case, green); the assembly lane's
own genuine degrade (the arc post at 2024) still tells its own `fallback` line, once. `router.py`
as a whole: −14 / +24 lines, docstring sentence and the status suffix below included. The "target line twice"
of finding 6 was this bug's echo and is gone with it.

Finding 2, the half that fits these lines: the demotion now rides on `res.status` (`… by the
ASSEMBLY lane, after the archetype lane failed at <stage>`), the one line a skill relays, not
only in a caveat. The other half — "restrict the fall-through to `ifc->facts` failures" — is
deliberately **not** taken: the very case this issue is about fails at `facts->rfa` (a body
the archetype does not model), so that allow-list would turn the 1-product box back into a
refusal; telling a legitimate "not a downlight" apart from a downlight regression needs a
typed refusal from `famfrom_ifc`, which is `src/rvt/ifc/**` — outside this territory and
eng #620's live file. Findings 3–6 untouched (not mine; #241 covers the 2024 arc gap seen above).

## Evidence

Tests added to `tests/test_ifc_assembly.py` (my section at the end, the generators reused):
`test_a_single_product_ifc_is_emitted_at_the_target_release[2025|2024]` (releases ==
detect_release == N, block `match`, no dead-lane caveat, no `ifc` role, status names both
lanes), `test_a_single_product_ifc_without_a_target_stays_native`,
`test_a_two_product_ifc_at_2025_stays_2025`. Against `main`'s `router.py` under the same test
file: 3 fail / 1 pass (the two single-product cases on the release itself; the 2-product case
only on the new status suffix); on this head 4 pass.

Driven by hand on the final tree (`.claude/skills/verify`, router surface), all from a fresh
cloud clone with `RVT_STEPLITE_FORCE=1`: the six `route.py run --output rfa` transcripts in the
table above (status / `releases` / block / `detect_release` on the bytes); every one of the six
`.rfa` → `tools/rvt_validate.py --family`: `VALID (no errors); warnings=0 info=2`, and their emit
reports' provenance scan `ok: true, suspects []` (the standalone `make_family.py provenance`
still refuses a 2025/2024 family — "unexpected Partitions header: v=9" — that is #408/#94, not
new). No orphan IFC beside a matched file: `--out` of `one.ifc @2025` now holds `T.rfa`,
`T.report.json`, `assembly-parts.json`, `product-facts.json`, `route.json`, `route.log`,
`ROUTE.md` and nothing else. Neighbouring lanes through the changed function: famspec
`rfa → rfa @2025` → `match`/2025, no line; `@2023` (resolver fallback, the story committed after
the native emit) → delivered 2026 + the resolver's line once, "no IFC rides" clause, 0
duplicate caveats; `ifc → rvt --via family @2025` on `one.ifc` (archetype-only chain) → `FAILED
(facts->rfa: …)` rc 3, no traceback, nothing delivered and — new — nothing promised either (on
`main` that failure still copied `one.ifc` into `--out` and left a "cannot run at 2025 … the IFC
alongside" line for a lane that produced no file). `route.py explain --output rfa --inputs ifc`
unchanged; `route.py matrix` byte-identical to `main` (3181 bytes, sha256 7dae5d40eb46…).

Gates: `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_router.py
tests/test_ifc_assembly.py tests/test_frontdoor.py -q -rs` → **before 285 passed / 19 skipped,
after 289 passed / 19 skipped** (the 4 new; skips = RVT_SKIP_LARGE, absent samples/ifcopenshell,
root-chmod, unchanged); whole merged shard (`shard_list.py --print`) → first run **1 failed /
2146 passed / 134 skipped / 3 xfailed**, the one failure being
`test_router_load_release.py::test_ifc_family_chain_honours_and_states_the_year`, whose
fresh-clone branch pinned the very artefact this issue removes (`status == "fallback"` +
`pending` for the `ifc → rvt --via family` chain that writes **no** file on a clone, #94) — under
either variant of the DONE's option (b) that assertion flips, so its three fresh-clone lines now
pin what is true (block stays the resolver's `match`, the Revit-N attempt is in the trace
labelled `attempt`, no "cannot run" caveat, no `ifc` role); the owner-machine branch of that test
and `test_degraded_emit_loads_onto_the_default_base_it_names` (degrade + successful native → the
full fallback story + LOAD on the default base) are untouched and green (file: 21 passed). **That
test file is the one touch outside the named territory — flagged for the reviewer; the alternative
is option (a), which keeps it green by leaving the dead lane's promise + orphan IFC on that chain.**
Shard re-run on the final tree → **2147 passed / 134 skipped / 3 xfailed, 0 failed** (6 m 57 s);
`tools/sync_plugin.py` → `--check` clean ("plugin in sync with source"); `validate_plugin.py`
PASS (25 assertions); `check_portable_paths.py` ok (3010 paths). `/simplify` ran on the diff (4
reviewers; the altitude + efficiency findings are the reorder described above, the rest were
"clean" or cosmetic and skipped); `/verify` = the drives in this section.

## Follow-up filed

**#625** — the assembly lane's *genuine* fallback (the arc post at 2024) says "no IFC rides beside a
FAMILY request" although the user supplied an IFC: `_famspec_rfa` never forwards `source_ifc`.
Three lines in `router.py`, outside this DONE; task-shaped, `Refs #564`, P2 / good-first-pick.
Nothing filed for findings 3–6 (not mine; searched: the 2024 arc gap is #241).

## BRANCH STATE (eng #564)

Branch `cam/564-assembly-target-version` from `main` 47296f1; one PR, `Closes #564`. Files:
`src/rvt/frontdoor/router.py` (`_emit_at_target` reorder + the `_r_ifc_to_rfa` status suffix;
+24 / −14) and its `plugin/lib/src/rvt/frontdoor/router.py` mirror via `sync_plugin.py`;
`tests/test_ifc_assembly.py` (one appended section, 4 tests, generators reused, nothing above it
edited); `tests/test_router_load_release.py` (3 assertions + docstring of ONE test's fresh-clone
branch, see Gates — outside the named territory, flagged); this record section. No matrix / cell / SKILL.md / hot-file change; nothing staged for
the viewer; no certification claimed — "VALID 0 errors" above is a validator fact, not a Revit
verdict (rule 4). Merge is the tech lead's (regime #302); this session never merges.

# eng #625 — the assembly lane's genuine fallback carries the source IFC beside the `.rfa` (2026-08-11)

*Written by engineer session eng #625 (issue #625, filed by eng #564 above) on branch
`cam/625-assembly-fallback-ifc`, cut from `main` at 55cc977 (= #627's squash). Add-only: every
section above is another author's and untouched.*

## The gap, reproduced on 55cc977

Fresh cloud clone, `RVT_STEPLITE_FORCE=1`, no `samples/`; `one.ifc` / `two.ifc` from this test
file's generator (box; box + 24-gon post); `tools/route.py run --ifc X --output rfa
--target-version N --json` and, for the famspec-only lane, `--rfa spec/examples/famspec-luminaire.json`:

| input @ year | `main` 55cc977 | this branch |
|---|---|---|
| two.ifc @2024 | ok, `releases.rfa` 2026, block `fallback`/2026, `pending` = `famspec->rfa: KeyError: "class 'ArcElemCell' not in the archive class map"` (#241); `ifc_addition: null` ("no intent resolved: nothing to emit"); line ends **"… your Revit 2024 cannot open it; no IFC rides beside a FAMILY request (it resolves no room intent) -- state the recipient's Revit year and re-run"**; `files` = assembly_parts, rfa, rfa_report; `--out` = ROUTE.md, T.report.json, T.rfa, assembly-parts.json, route.json, route.log | ok, 2026, `fallback`/2026, same `pending`; `ifc_addition` = `<out>/two.ifc` ("the input IFC, copied beside the build (already version-agnostic)"); line ends **"… your Revit 2024 cannot open it; the IFC alongside is version-agnostic (links into Revit 2019+)"** — the archetype lane's wording, byte for byte, because it is the same `_emit_at_target` branch; `files` gains `ifc`; `--out` gains `two.ifc` (byte-identical to the input); the line is ONE caveat, as before |
| two.ifc @2023 | (resolver fallback, uncertified year) delivered 2026 + the resolver's line ending "no IFC rides…" | delivered 2026 + the resolver's line ending "the IFC alongside is version-agnostic…", `two.ifc` beside, `files.ifc` set — the same mechanism covers both fallback sources |
| two.ifc @2025 | `match`/2025, bytes 2025, no line, no `ifc` role | identical (nothing copied, nothing said) |
| one.ifc @2025 | `match`/2025 by the ASSEMBLY lane after the archetype lane failed at facts->rfa; no `ifc` role | identical |
| famspec luminaire @2023 | `fallback`/2026, line ends "no IFC rides beside a FAMILY request…", no `ifc` role | identical — a famspec-only request still has no IFC and says so |
| famspec luminaire @2024 | `match`/2024 | identical |
| one.ifc → rvt `--via family` @2025 (#627's dead-lane case) | `FAILED (facts->rfa: …)` rc 3, block stays `match`, no line, no IFC copied, `--out` = ROUTE.md, product-facts.json, route.json, route.log | identical — #627's "a lane that delivered nothing states nothing and copies nothing" is untouched: the copy still happens only inside `_emit_at_target` after the native emit returned |

Status lines unchanged in every row. `tools/route.py matrix` byte-identical to `main` (3181 bytes,
sha256 7dae5d40eb46…). Every `.rfa` above (six) → `tools/rvt_validate.py --family`: `VALID (no
errors); warnings=0 info=2` — a validator fact about the files, not evidence that Revit opens them
(rule 4; nothing certified or staged here).

## The change

`router.py`, plumbing only (+10 / −4, docstring lines included): `_famspec_rfa` grows a keyword-only
`source_ifc: Optional[str] = None` and forwards it to `_emit_at_target(..., source_ifc=source_ifc)`;
`_assembly_rfa` passes `source_ifc=ifc_path`. The two famspec-only callers (`_r_rfa_generate`,
`_r_rfa_load`) pass nothing, so `_emit_ifc_addition` still finds no IFC and no model there and
`_settle_ifc_clause` still rewrites their line to "no IFC rides…". No wording, matrix, cell or
resolver change: the assembly lane now simply reaches the branch of `_emit_ifc_addition` the
archetype lane (`_product_rfa`, which already passed `source_ifc=ifc_path`) always reached. On a
`match` `_emit_ifc_addition` returns at its first line, so forwarding the path costs nothing there.

## Evidence

Tests appended to `tests/test_ifc_assembly.py` (a new section at the end; nothing above it edited,
the generators reused):
`test_an_assembly_fallback_carries_the_source_ifc_beside_the_rfa[2024|2023]` (block `fallback`,
`.rfa` delivered native and detected as such, `files["ifc"]` inside `--out`, basename `two.ifc`,
bytes == the input, `ifc_addition` names it, line keeps "IFC alongside is version-agnostic" and never
says "no IFC rides", stated exactly once, status names the ASSEMBLY lane),
`test_an_assembly_match_copies_no_ifc_and_says_nothing_extra` (two.ifc @2025: `match`, no `ifc`
role, no `two.ifc` in `--out`, no line), `test_a_famspec_only_fallback_still_says_no_ifc_rides`
(a donor-free `generic_model` famspec @2023: delivered native, no `ifc` role, no `.ifc` in `--out`,
line "cannot open it … no IFC rides"). The 2024 case carries a guard so it outlives #241: the famspec
constructor is wrapped to refuse inside any non-native release context (today the arc post already
raises there by itself; once 2024 gains `ArcElemCell` the guard keeps the test about this plumbing,
not about that gap); the 2023 case needs no guard (resolver fallback). Against `main`'s `router.py`
under the same test file: **2 failed / 2 passed** (both fallback years red on `KeyError: 'ifc'`; the
match and famspec-only pins already true); on this head **4 passed**. The famspec-only wording is
also pinned independently by `test_router.py::test_famspec_target_version_field_and_flag` and
`test_router_load_release.py` (both untouched, green).

Gates: `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_router.py tests/test_ifc_assembly.py
tests/test_router_load_release.py tests/test_frontdoor.py -q -rs` → **before 324 passed / 19 skipped,
after 328 passed / 19 skipped** (the 4 new; skips = RVT_SKIP_LARGE, absent samples / ifcopenshell, root chmod —
unchanged); whole merged shard (`shard_list.py --print`, `RVT_SKIP_LARGE=1 -p no:cacheprovider`) →
**(running at first push; counts recorded in the next commit of this section and the PR body)**; `tools/sync_plugin.py` → `--check` clean ("plugin in sync with source");
`validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok (3012 paths). `/simplify` ran on
the diff (4 reviewers): applied — the degrade guard raises *before* calling the real constructor (no
wasted build once #241 closes; the assertions never read the reason), a call-site comment that restated
the docstring dropped (`_product_rfa` passes the same keyword bare), the famspec-only test says why it
exists beside `test_router`'s catalog-gated pin; skipped — folding the match test's four negative
assertions into eng #564's `test_a_two_product_ifc_at_2025_stays_2025` and pointing that test at the new
`_two_products` helper (both would edit another author's section; the cost kept is one extra ~1 s route
per run — a later fold is welcome); altitude: "clean — the explicit keyword is the pattern
`_families_from_model` and `_product_rfa` already use". `/verify` = the router drives above re-run on the
final tree (same numbers), plus a junk `--ifc README.md @2024` probe: rc 4, `FAILED (ifc->parts: … not an
ISO-10303-21 (STEP) file)`, two one-line errors, no traceback, nothing copied into `--out`; emit reports'
provenance `ok: true, suspects []` on two24 / two25 / fam23.

## BRANCH STATE (eng #625)

Branch `cam/625-assembly-fallback-ifc` from `main` 55cc977; one PR, `Closes #625`. Files:
`src/rvt/frontdoor/router.py` (`_famspec_rfa` keyword + forward, `_assembly_rfa` call; +10 / −4) and
its `plugin/lib/src/rvt/frontdoor/router.py` mirror via `sync_plugin.py`; `tests/test_ifc_assembly.py`
(one appended section, 4 tests); this record section. Nothing else: no `src/rvt/ifc/**` (eng #621),
no famgen, no `tools/route.py`, no matrix / cell / SKILL.md / hot file; nothing staged for the viewer;
no certification claimed. No follow-up filed: the one adjacent wart (the resolver adds the "IFC
alongside" clause before knowing whether an IFC is written, so `_settle_ifc_clause` has to strip it)
is already named as a follow-up in `_settle_ifc_clause`'s docstring and lives in
`rvt.frontdoor._resolve_base_and_version` = `base.py`, a hot file. Merge is the tech lead's (regime
#302); this session never merges.
