# #1047 -- a back-box-and-trim panelboard constructor (steer #1046)

## What was built
`src/rvt/famgen/panel_can.py`, `make_panel_can(...)`. It is a second panelboard, modelled the way a
prefab / rough-in library models one: the back box and its trim (front cover).

**Names are ours.**
- The trade's words for the parts: back box, trim, surface / flush.
- NEC 110.26's words for the spaces: working space, dedicated equipment space.
- Revit's own terms for the circuiting values.
- Every size that is neither a catalog fact nor a code minimum is a NOMINAL of ours, overridable
  by the caller.
- A user's library names arrive only through their own profile at build time (#1048).

**The parts:**
- **Back box.** Five plates (back, two sides, bottom, top), open at the front.
  - Wall thickness is 1/16 in nominal (`box_thickness_in=` overrides it).
  - The back sits on the wall plane y = 0 and the box bottom at `Mounting Height`, whose default
    puts the box top at 78 in. A box that tall or taller stands on the floor.
  - `Box Thickness` REPORTS the wall. It is a type parameter locked by its constant formula, and
    the walls hold it by locked dimensions, so it is not a drive.
- **Trim.** One plate on the box front.
  - With `Surface Trim` on, it is the box's size.
  - With `Surface Trim` off (`Flush Trim` = `not(Surface Trim)`), it laps the opening by 3/4 in
    per side, nominal (`flush_lap_in=` overrides it).
  - `Trim Width` / `Trim Height` / `Trim Bottom` are formulas of the switch, and each labels the
    trim's own dimension.
  - `Show Trim` is bound to the trim's visibility (#877 binding).
- **Clearance zones.** The #882 zones and switches: the working space starting at the trim's face,
  and the dedicated space above the box top. Their size parameters label the zones' own
  dimensions:
  - `Working Space Minimum Width` (30 in, 110.26(A)(2)) and `Working Space Width` = the greater of
    it and `Width`.
  - The shift (110.26(A)(2) lets the working space sit off-centre as long as it spans the
    equipment):
    - `Working Space Centered`, `Working Space Shift Left` / `Right`;
    - each shift as APPLIED, `if(centred, 0', if(shift < 0', 0', if(shift < room, shift, room)))`,
      where room = `(Working Space Width - Width) / 2`;
    - `Working Space Left Edge` = `Working Space Width / 2 - Shift Right Applied + Shift Left Applied`.
    
    The zone's width is a CHAIN from the origin centre plane: the left edge (at least half the box
    width), then the width from that edge. Every labelled length stays positive at any shift,
    which a symmetric drive about the centre could not do.
  - `Working Space Depth`: a one-sided drive anchored on the plane the trim's face rides (the
    Depth drive's front plane plus one wall), so the zone follows the box.
  - `Dedicated Space Height`.
  - `Working Space From Floor` with `Working Space Height` =
    `if(from floor, Mounting Height + Height, Height)`, measured down from the box top. The zone's
    floor is its own plane, coincident with the origin elevation plane.
    - Authored only when the working space reaches exactly the box top, for a box off the floor.
    - The plane is made only when drives are wired, and removed again if its spec is refused.
- **Circuiting.** `Voltage`, `Number of Poles`, `Power Factor`, `Apparent Load` and
  `Load Classification` are associated to the power connector on the box top; `Motor` is not
  associated.
  - Poles use the `ParamDefNoOfPoles` storage (1..3).
  - The load class is an `ElectricalLoadClassificationParamDef` parameter valued with the
    connector's own load class.
  - Two round conduit connectors sit on the box top and bottom.
- **Section headers.** Four text parameters whose formula is their own label.
- **Drives.**
  - In plan: Width / Trim Width / Depth, the Left Edge -> Width chain, and Working Space Depth.
  - In height: Mounting Height / Height / Trim Bottom / Trim Height / Working Space Height /
    Dedicated Space Height, plus two locked unlabelled wall-thickness heights.
  - **A box on the floor** (78 in or taller by default, or `mounting_height_in=0`): the chain
    starts on the origin plane, and `Mounting Height` is said to label nothing.
  - **A flush trim lapping below the floor:** its bottom and height are said not to be driven.
  - Every drive is all-or-nothing, and a refusal is a note.
- **Type row and standards.** One type row, added before any parameter. The standards step
  (#601) is followed by the catalog facts as the tagging-contract values, as `make_panelboard`
  writes them.
- **CLI.** `tools/make_family.py panel-can [--cover flush] [--mounting-height IN]
  [--width/--height/--depth IN] [--box-thickness IN] [--flush-lap IN] [--param-profile …]`.

## Evidence

**Validation.** `rvt_validate` family mode reports VALID with 0 errors, and provenance is ok, on
all of:
- 2026: surface, flush, a box mounted at 24 in, a given 26 x 60 x 6 in box, an 80 in box on the
  floor, and a box at 0 in, surface and flush;
- 2025 and 2024, inside `release_build_context`.

**Drives.** Six in-plane drives and 8 / 8 height specs are wired, with 0 refusals. The floor-box
variants wire 5 / 5, or 4 / 4 with a flush trim, and say why.

**Anatomy.** Measured with `tools/family_anatomy.py compare` against the owner's reference
panelboard. These are aggregate counts only; the reference stays in the git-ignored `samples/`.

| measure | reference | make_panelboard | panel_can | panel_can + owner's profile |
|---|---|---|---|---|
| shortfalls (measures where ours is short) | -- | 33 | 28 | 20 |
| parameters | 60 | 26 | 53 | 66 |
| per instance | 34 | 4 | 32 | 32 |
| formulas | 27 | 2 | 16 | 21 |
| Yes/No | 15 | 5 | 11 | 12 |
| labelled dimensions | 30 | 3 | 12 | 12 |
| connectors | 3 | 1 | 3 | 3 |
| solids / voids | 2 / 2 | 9 / 0 | 8 / 0 | 8 / 0 |
| placed nested families | 2 | 0 | 0 | 0 |

The "owner's profile" column is the #866 mechanism (`ProfileRequest`) reading the owner's own
library profile. It is private and never committed; it adds the library's 13 shared parameters at
their GUIDs.

**Tests.** `tests/test_panel_can_1047.py`: 20 passed. Values and formulas are READ BACK from the
written file (`FamilyIndex` under its own release); every formula is evaluated against the
written inputs and must equal the written value.

**Mutation check.** 12 single-line mutations each fail the file:
- the flush complement;
- the working-space width / height made type parameters (the writer then drops their formulas);
- the left shift reading the right;
- the apparent-load id back to -1140005;
- the contract values dropped;
- the bottom wall's locked height dropped;
- the trim's or the sides' attach dropped;
- a negative shift unclamped;
- the zone behind the trim;
- the floor branch.

In #1053's first review, 9 of 15 mutations had survived.

## Findings
- **A parameter added before any type row keeps no value.** `FamilyDoc._register_param` only
  `setdefault`s on existing rows, and the default type the writer adds later carries 0.0 for every
  parameter. The first build validated **VALID with every value 0**, Width included. The read-back
  test catches it; the validator does not. The engine trap is #1055 and the validator rule #1056.
- **Apparent load: -1140004, not -1140005.** In a private census of the reference library, the
  power connector's apparent load is associated through -1140004 in 21 of 23 bindings, not the
  -1140005 `skeleton.ELEM_PROP_APPARENT_LOAD` holds. `panel_can` binds -1140004; the engine
  constant is #1051.

## Limits (stated, not hidden)
- **The box is five plates.** The reference cuts one box solid with a void, plus a void of four
  mounting holes. The holes' spacing parameters (and their "mounting holes" section) need the
  holes, so they move to #1049 with the voids. A parameter that drives nothing would claim
  geometry the family does not have.
- **Not yet built:** model text (#1050), and nested zone / tracking families.
- **The working space's code height holds only at the height it was built.** It is drawn to the
  110.26(A)(3) height (6 1/2 ft) when built. A box lowered in Revit draws it lower, and only the
  build-time note says so.
- **Values a user can push past what Revit will dimension:**
  - a flush trim's bottom on a box mounted below the lap;
  - a negative minimum width.
- **Behaviour is unverified.** No switch, resize or connector association has a desktop verdict
  (hard rule 4).

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/panel_can.py` (new);
  - `tools/make_family.py` (the `panel-can` subcommand);
  - `tests/test_panel_can_1047.py` (new);
  - `tests/ci_shard.d/1047-panel-can.txt`;
  - `docs/inbox/panel-can.md`, `docs/inbox/panel-can.d/1047-back-box-and-cover.md`;
  - the plugin mirror via `tools/sync_plugin.py`.
- **Gates:** see the PR body for counts. Nothing is staged for the viewer.
