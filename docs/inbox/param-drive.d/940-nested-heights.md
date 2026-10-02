# #940: the nested trapeze hardware follows the host's heights; the hex nut's across-flats

Stream: param-drive. Issue #940, the follow-up to #917's third pass
(`917-nested.md`, gaps 2 and 3). Branch `nested-heights-940`, based on
`origin/main` 96f976f.

The census reads the owner's reference library (421 born families, git-ignored,
development instrument only). Only counts and field values are cited; no
specimen name, parameter name or value reaches the output.

## Census 1: how a born nested part follows a host height

Every own nested instance of every born family (7,845), each mechanism counted
once per instance:

| Mechanism | Instances |
|---|---:|
| `Alignment` lock of an instance reference to a **horizontal** host plane (RefPlane or Level) | **1,203** |
| Hosted on a SketchPlane over a horizontal **RefPlane** (431 of them on a plane a labelled dimension drives) | 480 |
| Hosted on a horizontal face of a nested instance / an extrusion / a curve | 415 / 357 / 18 |
| On a horizontal SketchPlane with no host reference (fixed height) | 395 |
| Labelled `LinearDimString` from an instance reference to a horizontal plane | 13 |
| An offset built-in parameter associated to a host parameter (`FamilyParametrizedElemParamsCell`, BIPs -1001364 / -1001360) | 20 |

2,791 instances in 194 files use at least one; 5,054 use none. The dominant
mechanism is the **elevation lock**. Its instance references:

- **Named references**: 614 locks. The tag is not a child Is-Reference code and
  is not in the nested family's reference index (0 / 614); mapping still
  unresolved, not authorable.
- **Center (Left/Right) or Center (Front/Back) turned horizontal by a rotated
  instance**: 127 + 357 locks, almost all on work-plane-based instances.
- **A horizontal centre reference on an unrotated child**: Center (Elevation)
  (code 7) 9 locks, Bottom (6) 1. This is the only lockable form for a free,
  unrotated instance, which is how every nested instance here is placed.

Every resolvable elevation lock holds: CG8 (below) judges 467 born elevation
locks, 0 findings. The 9 Center (Elevation) locks share the free-instance lock
shape #917 authors: plane first, constrFlags (4, 2), end index (0, 0), flags
14, dimVersion 6, instance geomRef flags 1, header regenOnly {symbol, Level,
UnitsElem}. `m_constrDir` is parallel to the host normal; its sense varies
across all 467.

**The child's side.** 1,404 of 1,846 nested child documents carry a horizontal
origin plane at z 0. Its Is-Reference is "Not a Reference" (12) in 1,299,
Center (Elevation) (7) in 61, Strong (13) in 21, Weak (14) in 9, Top (8) in 3
and Bottom (6) in 1. All 61 code-7 planes are the origin elevation plane in its
template form: unnamed, drawn, cut vector (0, 1, 0), at z 0. A code-7 plane is
listed in the nested family's reference index whenever it exists (61 / 61; the
index name is empty in 58, "Center (Elevation)" in 5). Every locked code is
in the symbol's strong references (code 7: 11 / 11). Code 12 is never in the
reference index (0 / 1,312) and never a strong reference (0 / 3,349).

## Census 2: how a born hexagon resizes across flats

Every closed loop of six equal lines in any sketch of any document, top-level
or nested: **68 hexagons**, 63 of them in nested documents. 37 are extrusion
profiles and 15 are filled regions.

| How the loop is held | Hexagons |
|---|---:|
| **Labelled + EQ + angular EQ** (below) | **32** (7 distinct families; one accounts for 20) |
| Fixed: unlabelled dimensions to planes / locks to other curves | 33 |
| Unconstrained | 3 |

Each of the 32 carries the same 11 constraints:

- **One instance parameter**, a formula of another parameter in 32 / 32,
  labels two `LinearDimString`s from the hexagon's flats to the origin plane
  (value = across flats / 2).
- **3 EQ dimensions** about the origin planes.
- **5 EQ `AngularDim`s** across consecutive sides, which keep it regular.

No profile family and no radial or across-corners dimension was found.

**Why our nut's Nut Across Flats is not wired.** The born mechanism needs
angular EQ dimensions (`AngularDim`), and this engine authors none: no builder,
no generated specimen. Our in-plane drive (`drive_law.wire_linear_drive`) locks
sketch lines to planes on x or y only. Four of a hexagon's six sides lie at
±60°, so they could follow only through joins, and the hexagon would stop being
regular as across-flats changed. **Nut Across Flats therefore stays a
value-only association** (as #917 left it). Authoring `AngularDim` with an EQ
array is a separate piece of work: its own census of the class, the
shape-ladder probes, and a desktop verdict.

## Built

**`src/rvt/famgen/trapeze_nested.py`**

- `origin_elevation_reference(doc)` gives each child's origin elevation plane
  (added by `height_law.wire_height_drive` at z 0, the part's bottom face)
  Is-Reference Center (Elevation), code 7. It refuses unless exactly one
  horizontal origin plane is at z 0. The washer and the nut both call it.
- `height_planes(doc, zs)` finds the one host horizontal RefPlane at each
  height. It refuses when a height has no plane or several.
- `NestedHardwareProduct.adopt` maps every hardware height to its plane
  (`z_planes`). `nest_plan` adds a third lock per instance: Center (Elevation)
  to that plane. The planes are the ones the #787 height chain already makes:
  - tier base / top (Strut Height, Tier Spacing);
  - washer below / above (Washer Thickness);
  - nut below (the locked nut height).

  They are the planes the solid version locks that part's face to.
- The product notes now state the locks and that whether Revit moves a locked
  nested instance is unverified. The module docstring carries the census.

**`src/rvt/famgen/constraint_law.py`**

- **CG8 extended** (`_cg8_frame`): a judged instance lock's `m_constrDir` is
  parallel to the host plane normal, and both `m_refPnts` and `m_oldOrigin`
  lie on the host plane. Each property holds on 2,393 / 2,393 judged born
  locks. A field the lock does not carry is not judged.
- `judged_instance_locks(path)` lists what CG8 judged in a written file, with
  elevation locks marked.
- Over the whole born library: **2,393 locks judged (467 elevation), 0 CG8
  findings, 421 files**.

`nest.py` is unchanged: its lock author already took `center_elevation`, and
the census shape matched it.

## Evidence (read back from the written files)

The default nested trapeze on **2026** and **2025**, and a 3-tier variant
(Tier Spacing 10 in, Washer Thickness 3/16 in) on 2026:

- `rvt_validate` (family mode) VALID, 0 errors.
- Provenance ok.
- `constraint_law.check_file` == [].
- **CG8 judged 48 locks**: 16 instances × {1, 4, 7}. 16 are elevation locks,
  and every one is tag 7. The 3-tier variant: 72 judged, 24 elevation.
- Each elevation lock's plane is horizontal at the instance's transform z, and
  is the `z_planes` entry for it. The instance heights equal the solid
  builder's washer and nut bottom faces, part for part, for both dimension
  sets.
- The nested family's reference index codes are [1, 4, 7], with no 12. Each
  nested symbol's strong references include 1, 4 and 7.
- **Refusals deliver the solid trapeze byte for byte**, on 2026 and 2025:
  - a child without its code-7 plane makes `nest_family` refuse the elevation
    lock;
  - an unresolvable height makes `adopt` fall back.
- The default `make_archetype(product="strut_trapeze")` is untouched. #917's
  byte-identity test still passes.

## The default: stays SOLID (opt-in unchanged)

DONE 3 asks for both halves to hold before re-deciding. They do not:

1. **The nut does not resize** (census 2), which is DONE 2's condition. The
   solid nut does not resize either. Neither version is worse on this point,
   so the nested lane has no advantage that would justify the switch. The
   nested lane does carry an association that looks like it should resize the
   nut, and its notes say it does not.
2. **No desktop verdict** for any nested lock or association, height locks
   included. Neither CG8 nor the validator shows that Revit's solver moves a
   locked nested instance (hard rule 4; steer #913: no probe family to the
   owner).
3. **Cost.** #917 measured the nested write at about 1.8× the solid one on
   2026. This pass adds 16 alignments and was not re-timed.

What would flip it: an `AngularDim` (EQ) author with the census-backed hexagon
recipe, plus a desktop verdict that a nested instance follows a host height
change.

## Gaps, stated plainly

1. **No desktop verdict** (hard rule 4).
2. **Nut Across Flats is value-only.** `AngularDim` is not authored (census 2).
3. **Named-reference elevation locks** (614 born) remain unresolved. Rotated
   and work-plane-based instances (the 484 centre-reference elevation locks)
   are not authored.
4. **Finding outside this territory, `loader.py`.** The loader lists every
   origin plane in the nested family's reference index and in the symbol's
   strong references, including "Not a Reference" (12). Born files never do
   (0 / 1,312 and 0 / 3,349). This pass's children no longer carry a code-12
   origin plane, so the nested trapeze is clean. Any other height-driven
   generated family loaded into a project, or nested, still gets the stray
   entry. Fixing it in `loader._reference_idx_mgr` and the strong-ref list
   changes project-load bytes, so it should be its own issue.
5. Gaps 4-6 of #917's third pass stand: the lane is not reachable from a route,
   the loader end parity is unjudged, and there is no shared nesting.

## BRANCH STATE (`nested-heights-940`)

**Files written**
- `src/rvt/famgen/trapeze_nested.py`: `origin_elevation_reference`,
  `height_planes`, `z_planes`, elevation locks, notes and docstring.
- `src/rvt/famgen/constraint_law.py`: the CG8 frame check
  (`_cg8_frame`), `judged_instance_locks`, docstring.
- `plugin/lib/src/rvt/famgen/{trapeze_nested,constraint_law}.py`: sync
  mirrors.
- `tests/test_nested_heights_940.py` (new) and
  `tests/ci_shard.d/940-nested-heights.txt`.
- `tests/test_trapeze_nested_917.py`: lock counts 16 → 24, judged codes
  {1, 4} → {1, 4, 7}, and the notes assertion follows the new truth.
- This fragment.

**Gates**
- `sync_plugin.py`, then `--check`: in sync. `validate_plugin.py`: PASS (25).
- `pytest`: **292 passed, 0 failed**, over these files:
  - `test_nested_heights_940` (new) and `test_trapeze_nested_917`;
  - `test_nest_917` and `test_nest_locks_917`;
  - `test_strut_trapeze_899`, `test_drive_follow_904`, `test_height_law_787`
    and `test_archetype_drives_913`;
  - `test_constraint_law` and `test_constraint_law_910`;
  - `test_conftest_scaffolding`, `test_plugin_sync` and `test_surface_perf`.
- The first run had 3 failures in `test_nest_locks_917`. Its synthetic locks
  carry no `m_constrDir`, and the frame check had judged the missing field.
  The check now judges only fields the lock carries (never guessed).
- Extended CG8 over the born library (scratch instrument): 2,393 judged, 467
  elevation, 0 findings.

**Shipped vs staged:** the opt-in lane ships with height locks; no route uses
it, and the default is unchanged. Nothing is staged, and no viewer or desktop
batch has been run.
