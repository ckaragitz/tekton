# swept-solids-arbitrary-axis — issue #514 probe A PASSED

Stream: #514 (the LOD ceiling — revolved and swept solids). Windows laptop,
fresh clone, desktop Revit 2026 available on the same machine, so every claim
below that says "opens" is a real desktop verdict, not a validator result.

## Why

A user brought a wire-mesh cable tray exported as IFC4 (`IfcCableCarrierSegment`,
71 `IfcSweptDiskSolid` bodies) and the `ifc → rfa` route refused it:

```
FAILED (ifc->parts: no measurable solid -- body is not tessellated
        (only meshes are measured))
```

Two separate causes, both fixed here.

## What was built

**1. `IfcSweptDiskSolid` is readable.** `steplite` carried no attribute rows for
it: `by_type()` found the 71 bodies because class names are parsed, but every
read of `.Directrix` / `.Radius` raised *"outside the read-path attribute
subset"*. Rows added for `IfcSweptDiskSolid` and `IfcSweptDiskSolidPolygonal`
with their true supertypes from the generated tables. (The same gap, and the
same fix, applies to `IfcRelAssociates(Material)` and the `IfcMaterial*`
definitions — see the material commits on this branch.)

**2. `rvt.famgen.orient` — rigid re-orientation of an authored solid.** Rather
than re-deriving the six-face topology template (`docs/writer/family-geometry.md`
§3, every rule stamped `[V]` against specimens), it builds the prism exactly as
today — upright, verified — and applies ONE rigid transform to the finished
record.

* `rotation_from_z(direction)` — shortest-arc Rodrigues rotation.
* `rotate_record(obj, R, offset)` — rotate, then move points.
* `place_along(elements, start, end)` — a rod from `start` to `end`.

## Evidence

### Why Z-only extrusion cannot express a cable tray

Every form `geometry.py` authors is extruded along −Z. Measured over the 911
wire segments of the user's tray, by **wire length**:

| segment direction | % of length |
|---|---|
| Y horizontal | 53.2 % |
| X horizontal | 25.6 % |
| Z vertical | **14.9 %** |
| diagonal (the formed bends) | 6.3 % |

Only 14.9 % is a standing cylinder. A cable tray is mostly wires running
*along* it, which is exactly what the vocabulary could not express.

### Probe A — the single-variable pair (DESKTOP PASS)

Two families whose ONLY difference is that the variable's solid is rotated by
`rotation_from_z((0,1,0))`:

| file | rotated fields | validator | **desktop Revit 2026** |
|---|---|---|---|
| `rod_A_control_upright.rfa` | 0 | VALID (0 errors) | opens, stands upright |
| `rod_B_along_Y.rfa` | 57 | VALID (0 errors) | **opens, lies down, clean circular end cap** |

So a form whose baked B-rep is rotated **while its sketch stays on the
Ref. Level datum** is accepted. That was the one question the probe existed to
answer, and it is the result the rest of this depends on.

### The tray (DESKTOP PASS)

911 rods authored in 2.1 s, written and validated in 4.4 s total:

```
family-mode VALID (0 errors, 0 warnings)
13,923 records / 4,640 elements / 0 decode failures / 82,590 refs checked
835,584 B
```

Overall envelope, computed from the authored geometry: **12.00 × 118.00 ×
3.82 in**, against the IFC's own description *"12 in wide x 4 in deep, 118 in
section"*. 3.82 in centreline + 0.18 in wire diameter = 4.00 in outside. The
dimensions were never read from that text — the agreement is independent
confirmation the placement is right.

Opened in desktop Revit 2026: renders as a real wire mesh tray — longitudinal
wires, formed U-rungs, top edge wires. **No envelopes, no approximations**:
every one of the 911 rods is a true cylinder on its own axis.

## Findings

* **The uv pairs are why this is cheap.** Face-frame uv coordinates are
  expressed in their own frame, so a global rotation leaves them correct by
  construction. Topology, tags, loop links and coedge direction flags never
  move. That is what made re-orientation a ~120-line module instead of a
  rewrite of the topology template.
* **`m_keys` is not a vector.** It carries history tags like `[3, i, -1]` —
  three integers that look exactly like a coordinate. Rotating them would
  corrupt the element history silently. The field list is an ALLOW-LIST for
  precisely this reason, and a "rotate any 3-element list" implementation
  would have shipped a broken family that still validated.
* **Points and directions must be kept apart.** `m_center` / `m_origin` /
  `m_or` rotate *and* translate; `m_xVec` / `m_yVec` / `m_zVec` / `m_dirVec` /
  `m_vecInPlane` rotate *only*. Translating a frame axis makes every face frame
  drift with the body's position.
* `rotation_from_z` returns exactly the identity for +Z, so upright bodies stay
  bit-identical to the verified path — this change cannot regress existing
  families, and `det = +1` guarantees no mirroring.

## Open questions

* **Not wired into the router.** The tray was built by a script; `route.py run
  --output rfa --ifc <file>` still refuses a swept-disk IFC. The assembly lane
  (`rvt.ifc.assembly_parts`) needs to measure swept disks alongside meshes.
  That is the obvious follow-up and belongs in its own issue.
* **Bend fidelity.** The formed bends arrive as short chord rods (6.3 % of
  length). Faithful to the IFC's own polyline directrix, but a true arc sweep
  would be better.
* **A drawable tray is a different feature.** The user's real requirement is a
  tray drawn with the cursor — a LINE-BASED family whose `Length` is driven by
  the drawn line. Nothing in the engine models line-based families
  (`m_bIsHostBased` / `m_bHasBaseArrays` are hard-coded `False`), formulas are
  not serialized, and arrays are not authored. Filed separately; the
  parametric-drive law (#372) already provides the flexing half.

## BRANCH STATE

* Branch: `ckaragitz12/materials-from-ifc`, cut from `main`, rebased on
  `59a89d8`. Not stacked on any other PR.
* Files written:
  * `src/rvt/famgen/orient.py` (new)
  * `src/rvt/ifc/materials.py` (new)
  * `src/rvt/ifc/steplite.py` (attribute rows: swept disk + material classes)
  * `src/rvt/famgen/skeleton.py` (`SPEC_MATERIAL` → `ParamDefMaterialBrowse`)
  * `plugin/lib/src/rvt/**` (generated mirrors, via `tools/sync_plugin.py`)
  * `docs/inbox/swept-solids-arbitrary-axis.md` (this record)
* Gates: `tools/sync_plugin.py` full build exit 0 (deny-audit clean, identity
  scan 105 files + 105 zip members, 0 mismatches) then `--check` in sync;
  `plugin/scripts/validate_plugin.py` PASS; `tools/dev/check_portable_paths.py`
  ok; famgen + IFC suites green (counts in the PR).
* Staged vs shipped: shipped. No viewer-certification claim — the desktop
  verdicts above are desktop Revit, recorded per hard rule 4, not a ledger
  entry.
