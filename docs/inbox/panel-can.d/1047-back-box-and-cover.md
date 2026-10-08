# #1047 -- a can-and-cover panelboard constructor (steer #1046)

## What was built
`src/rvt/famgen/panel_can.py`, `make_panel_can(...)`. It is a second panelboard, modelled the way a
prefab / rough-in library models one: the back box and the cover. Every parameter name is ours.

- **Back box.** Five plates (back, two sides, bottom, top), each `Box Thickness` (1/8 in, a type
  parameter locked by its constant formula), open at the front. The back sits on the wall plane
  y = 0 and the box bottom at `Mounting Height`, whose default puts the box top at 78 in.
- **Cover.** One plate on the box front.
  - With `Surface Cover` on, it is the box's size.
  - With `Surface Cover` off (`Flush Cover` = `not(Surface Cover)`), it laps the opening by 1/2 in
    on every side.
  - `Cover Width` / `Cover Height` / `Cover Offset` are formulas of the switch, and each labels
    the cover's own dimension.
  - `Show Cover` is bound to the cover's visibility (#877 binding).
- **Clearance zones.** The #882 zones and switches, in front of the box front and above the box
  top, with size parameters that label the zones' own dimensions:
  - `Minimum Clearance Width` (30 in, 110.26(A)(2)) and `Clearance Width` =
    `if(Width < Minimum Clearance Width, Minimum Clearance Width, Width)`.
  - `Front Clearance Depth`: a one-sided drive anchored on the Depth drive's front plane, so the
    zone follows the box.
  - `Top Clearance Height`.
  - `Front Clearance To Floor` with `Front Clearance Height` =
    `if(to floor, Mounting Height + Height, Height)`, measured down from the box top. The zone's
    floor is its own plane, coincident with the origin elevation plane.
    - Authored only when the working space reaches exactly the box top.
    - A box mounted so low that the 110.26(A)(3) height (6 1/2 ft) passes its top keeps the code
      height and says so in a note.
- **Circuiting.** `Voltage`, `Number of Poles`, `Power Factor`, `Apparent Load`,
  `Load Classification` and `Motor`, associated to the power connector on the box top.
  - Poles use the `ParamDefNoOfPoles` storage (1..3).
  - The load class is an `ElectricalLoadClassificationParamDef` parameter valued with the
    connector's own load class.
  - Two round conduit connectors sit on the box top and bottom.
- **Section headers.** Four text parameters whose formula is their own label.
- **Drives.**
  - In plan: Width / Cover Width / Depth / Clearance Width, plus Front Clearance Depth.
  - In height: Mounting Height / Height / Cover Offset / Cover Height / Front Clearance Height /
    Top Clearance Height, plus two locked unlabelled wall-thickness heights.
  - Every drive is all-or-nothing, and a refusal is a note.
- **Type row and standards.** One type row, added before any parameter. The standards step
  (#601) is followed by the catalog facts as the tagging-contract values, as `make_panelboard`
  writes them.
- **CLI.** `tools/make_family.py panel-can [--cover flush] [--mounting-height IN]
  [--width/--height/--depth IN] [--param-profile …]`.

## Evidence

**Validation.** `rvt_validate` family mode reports VALID with 0 errors, and provenance is ok, on
all of:
- 2026: surface, flush, a box mounted at 24 in, and a given 26 x 60 x 6 in box;
- 2025 and 2024, inside `release_build_context`.

**Drives.** Five in-plane drives and 8 / 8 height specs are wired, with 0 refusals.

**Anatomy.** Measured with `tools/family_anatomy.py compare` against the owner's reference
panelboard. These are aggregate counts only; the reference stays in the git-ignored `samples/`.

| measure | reference | make_panelboard | panel_can | panel_can + owner's profile |
|---|---|---|---|---|
| shortfalls (measures where ours is short) | -- | 33 | 28 | 21 |
| parameters | 60 | 26 | 47 | 60 |
| per instance | 34 | 4 | 26 | 26 |
| formulas | 27 | 2 | 13 | 18 |
| Yes/No | 15 | 5 | 10 | 11 |
| labelled dimensions | 30 | 3 | 11 | 11 |
| connectors | 3 | 1 | 3 | 3 |
| solids / voids | 2 / 2 | 9 / 0 | 8 / 0 | 8 / 0 |
| placed nested families | 2 | 0 | 0 | 0 |

The "owner's profile" column is the #866 mechanism (`ProfileRequest`) reading the owner's own
library profile. It is private and never committed; it adds the library's 13 shared parameters at
their GUIDs.

**Tests.** `tests/test_panel_can_1047.py`: 15 passed.

## Findings
- **A parameter added before any type row keeps no value.** `FamilyDoc._register_param` only
  `setdefault`s on existing rows, and the default type the writer adds later carries 0.0 for every
  parameter. The first build validated **VALID with every value 0**, Width 0 included. The test
  that reads the type row caught it; the validator does not. The constructor now adds its type
  first. A validator rule for "a labelled length parameter whose value is 0" is worth a separate
  issue.
- **Apparent load: -1140004, not -1140005.** In a private census of the reference library, the
  power connector's apparent load is associated through -1140004 in 21 of 23 bindings, not the
  -1140005 `skeleton.ELEM_PROP_APPARENT_LOAD` holds. `panel_can` binds -1140004; the engine
  constant is #1051.

## Limits (stated, not hidden)
- **The box is five plates.** The reference cuts one box solid with a void, plus a void of four
  mounting holes; void extrusions are #1049.
- **Not yet built:**
  - model text (ID, part number): #1050;
  - nested zone / tracking families;
  - left / right shift of the working space.
- **Names.** The owner's library names arrive through their own profile at build time (#1048):
  the shared ones today, and our own parameters renamed once #1048 lands.
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
