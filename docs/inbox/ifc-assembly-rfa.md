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
