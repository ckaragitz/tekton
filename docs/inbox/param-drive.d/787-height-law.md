# #787 Case B — a parameter drives an extrusion's height (plan step 3 of #913)

**Stream:** param-drive. **Refs:** #787, #913, #904, #912 (built on #912; merged in #923).

## What was built

- `src/rvt/famgen/height_law.py` (new): `wire_height_drive(doc, *, caption, lo_z, hi_z,
  targets, locked=False)` plus `wire_height_specs(doc, specs, ext_of)` for declarative
  specs. It locks the start and end cap faces of extrusions to horizontal reference
  planes, and those planes are held by elevation dimensions.
  - It runs every check before its first mutation, so a refusal leaves the document
    unchanged.
  - It adds two checks the scratch prototype lacked: a profile with no curves, and a
    target that is not an extrusion, are both refused before any mutation.
- `Archetype.heights` (`archetypes.py`): `vals -> [{caption | None, locked, lo, hi,
  name_lo, name_hi, parts: {part name: faces}}]`.
  - `lo` / `hi` are either a z in feet (0.0 is the origin elevation plane) or the name
    an earlier spec gave a plane, which is how the chains are built.
  - The trapeze gets `_trapeze_heights`. Per tier it wires Strut Height, Strut
    Thickness ×2, Washer Thickness below and above, and a locked nut height past each
    washer. Tier Spacing chains the tier bases, and Rod Below Bottom Nut and Rod Above
    Top Tier set the rod ends.
- `factory._make_generic_multipart(heights=...)`:
  - Height specs are wired after the in-plane drives and before `finalize()`.
  - Each spec is all-or-nothing. A refused spec becomes a `doc.notes` line and never
    raises (hard rule 1).
  - `doc.born_drive_law` is set when a drive **or** a height is wired, so `finalize`
    writes no back-edges and `apply_born_inplane_law` runs after it.
  - `prod.heights` carries the report. The single-prism path notes that heights were
    not wired.
- Honesty updates:
  - The trapeze `lod_note` says the heights are authored from the corpus law.
  - A new `limits` entry says that **no Case B element has a desktop verdict**, and
    lists the parameters that still only carry values.
  - The taxonomy note is updated to match.

## The one deliberate change from the prototype: surface-only horizontal planes

The user's horizontal planes are authored in the Revit-born surface-only form, not
the prototype's drawn-ends form. The origin elevation plane keeps its born drawn
template form (refName 12, definesOrigin, drawn in the Front elevation, cutVec (0,1,0),
SketchMembership + PatternHelper cells, held to the Level by a flags-14 Alignment).

**Born form, from a census of 823 surface-only horizontal planes in 160 born files**
(field facts and counts only; no specimen is named):

| Field | Born value | Count |
|---|---|---|
| free end / bubble end / cutVec / refPointsForNewViews | all zero | defines the set |
| genDbViewId | -1 | 823 / 823 |
| DatumPlaneGeomStep | version 1, flags 761725 | 817 / 823 |
| step list | flags 11, latestGStepType [0,0,0,0,0], idCounter 2 | 817 / 823 |
| GeomTable maxSafeTag / lastChecked | -1 / -1 | 823 / 823 |
| cell list | none | 789 / 823 |
| header abFlags4Bytes | 10 | ≈800 / 823 |
| header deletion | [Family, self] | ≈800 / 823 |
| header regenOnly / appearance | empty | ≈800 / 823 |
| refName | 14 or 12 | 14 is the larger group |
| face GInfo flags | 524804 | 823 / 823 |
| face surface | equals m_pSurface | 823 / 823 |

The axis pair (-1,0,0) / (0,-1,0), which gives a +Z normal, is the modal pair (383).

**Read-back comparison.** Our written 2025 trapeze was compared field by field with
born surface-only planes on three specimens.
- On the specimen that uses the same axis pair, the **only** differences are
  `m_familyId`, `m_refName` (ours 14, that specimen 12; both attested) and `m_text`.
- The other two specimens differ in the in-plane axis pair (both attested). One of
  them also has header flags 2058 and a PatternHelper cell, the minority form.

**Read-back on 2026 and 2025:** 17 of 17 user planes are surface-only, exactly the
form above. The encoder accepted it, the validator reported 0 errors, and 0 records
decoded unclean. The fallback to the prototype's form was not needed.

## Evidence (numbers)

**Trapeze at default size (2 tiers):** 17 dimensions (13 labelled, 4 locked
unlabelled), 18 planes (17 surface-only plus the origin plane), 116 face locks, and
58 / 58 extrusions locked on both faces. These are the prototype's numbers.
- **2026:** VALID, 0 errors (`tools/rvt_validate.py`), 0 / 755 records decoded unclean.
- **2025:** the same result, 0 errors.
- **Read-back of the written file:** every flags-14 face lock's face z equals its
  plane z to within 1e-9 (116 / 116). `m_paramExprs`, `m_drivenDimSegs`,
  `m_dimSegDataMap`, `m_fixedRefs` and `m_propagatedDrivers` rows are present for
  every locked face (116 / 116).
- **3 tiers:** every height spec is wired, and every extrusion is locked on both faces.

**Refusals.** Each of these is refused, and the written file's SHA-256 equals the
build without the height spec (11 parametrised cases):
- a value mismatch;
- a face that is not on its plane;
- lo > hi;
- a NaN plane;
- an unknown part;
- an unnamed plane reference;
- a non-length parameter;
- an unknown parameter;
- an unlocked unlabelled dimension;
- a floating chain;
- a bad face map.

Two more cases are covered by their own tests:
- **A face locked twice:** the build equals the build with only the first spec.
- **A third dimension between positioned planes:** refused with "over-constrains".

## Remaining differences from born (ranked)

1. **No desktop verdict for any Case B element** (hard rule 4). This covers the face
   locks, the manager rows, the surface-only planes and the added origin plane.
2. **The origin elevation plane is new to our documents.** It is born field for field
   except GeomTable `m_maxSafeTag`: ours is -1, the specimens have 0.
   - The 2026 schema has no such field.
   - The 2025/2024 release port writes -1 for it (`release_ctx`), so the object's
     value cannot reach the file.
   - This is the same as every drawn plane we already author.
3. **View choice.** The dimensions and locks are drawn in Front (planeNormal = Front's
   view direction). Both Front and Left are attested.
4. **`m_refName` 14 on user planes.** 12 is also common in born files; both are attested.
5. **The nut height is a locked unlabelled dimension.** Born families nest the nut and
   do not have one; nested families are a separate route.

## Open questions

- Whether the owner should get one Case B desktop pair before the trapeze carries
  heights by default. Today the heights are authored and stamped unverified, and
  delivery is never gated on that.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/height_law.py`: new.
- `src/rvt/famgen/archetypes.py`: `Archetype.heights`, `_trapeze_heights`,
  the trapeze `lod_note` and `limits`.
- `src/rvt/famgen/factory.py`: the `heights=` plumbing in `make_generic_model`,
  `_make_generic_multipart` and `make_archetype`, plus `born_drive_law` and the notes.
- `src/rvt/famgen/taxonomy.py`: the trapeze note.
- `plugin/lib/src/rvt/famgen/*`: mirrors, regenerated by `tools/sync_plugin.py`.
- `tests/test_height_law_787.py` and `tests/ci_shard.d/787-height-law.txt`: new.
- `tests/test_drive_follow_904.py`: its labelled-parameter assertion now covers
  plan-view dimensions only, since elevation height dimensions now label other
  parameters.
- This fragment.

**Gates**
- `tests/test_height_law_787.py`: 20 passed.
- The listed suites together (height law, drive law, drive follow, strut trapeze 899,
  famgen archetypes, famgen factory, family anatomy 837, plugin sync, constraint law):
  **531 passed / 5 skipped**.
- `test_archetype_alias_order_812.py` and `test_inventory.py`: 199 passed /
  14 skipped / 5 xfailed.
- `sync_plugin.py`: rebuilt. `sync_plugin.py --check`: in sync.
- `validate_plugin.py`: PASS.
- Portable paths: ok.

**Shipped vs staged:** the code is committed on the branch only. No viewer batch and
no desktop pair is staged. Nothing is claimed to flex.
