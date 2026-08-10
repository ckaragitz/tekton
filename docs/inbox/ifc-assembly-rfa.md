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
