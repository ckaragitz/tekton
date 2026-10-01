# #914 — panel drives: every plane on its edge, and the lighting control panel wired

Stream: param-drive. Refs #914 #913 #910 #904 #787 #372 #689. Branch `lcp-panel-914`
(on top of the #919 head: `drive_law` wire_attach / wire_symmetric / wire_follow,
`height_law`, the #910 constraint-law retirement).

## What was built

1. **The panelboard chain puts every plane on its edge** (`param_drive.wire_panelboard_drive`).
   Before, the side planes sat at x = ±W/2 and y = ±D/2 about the origin. The panelboard
   profile spans y = 0..D for a surface panel and -D..0 for a flush one. So the two y-axis
   sketch locks tied their edges to planes 0.24 ft away (constraint law CG7).
   - Now each plane is read off the profile edge it locks.
   - The labelled dimensions' reference points and origins follow the planes.
   - A type-row value that disagrees with the profile is refused with a `ValueError`
     before the first mutation. Before, it was silently drawn.
   - A centred profile gives the same numbers as before, so its output is byte-identical
     (measured below).
2. **The lighting control panel is wired** (`archetypes.py`):
   - `family_params = _box_params("Cabinet")`: Cabinet Width / Height / Depth and Sheet
     Thickness.
   - `drives = _lcp_drives`: Cabinet Width, a symmetric in-plane drive on x. It moves both
     side edges of the back, the top wall, the bottom wall and the door. Wall left rides
     the low end; wall right and the door latch ride the high end (`drive_law.wire_attach`).
   - `heights = _lcp_heights`, the #787 Case B cap-face drives:
     - Cabinet Height: origin → cabinet top, locking the back and door on both faces, the
       bottom wall's base and the top wall's top.
     - Sheet Thickness ×2: origin → the bottom wall's top and the side walls' bases; the
       top wall's base and the side walls' tops → cabinet top.
   - **A second instance of the same defect, found by the refusal.** `make_generic_model(parts=…,
     drive=True)` labels the first solid with the ASSEMBLY's Width/Depth. When the first
     solid is not the footprint (`test_drive_law_904`'s fixture had a second box beside
     it at y = 3), the old chain drew planes 1.5 ft off the solid's edges (base: CG7, 1.5
     ft). That case is now refused and recorded as a note ("parametric drive not wired");
     it never raises, and the other drives still land. The #904 test was moved to a
     stacked second box, and the refusal got its own test.
3. **`constraint_law.check_file` reads a file under its own release** (`enter_own_release`).
   Before, a 2025 file raised `unexpected Partitions header` inside the law. The law
   itself is unchanged.
4. **Tests.**
   - New: `tests/test_panel_drives_914.py`.
   - The #910 strict xfail `test_the_panelboard_chain_is_coherent` is now a plain pass.
   - The #913 "LCP stays unconstrained" pin is replaced, and the LCP was added to its
     EXPECT table.
   - The family-anatomy pins were changed deliberately (next section).

## Family-anatomy baseline (changed on purpose)

The lighting control panel was the profiler's unconstrained baseline: 2 origin planes and
0 dimensions. It is now pinned to what it carries:

| Element | Count | Breakdown |
|---|---|---|
| Planes | 12 | 2 origin centre, 2 width ends, 4 ride planes, the origin elevation plane, 3 surface-only height planes |
| Dimensions | 9 | 4 labelled + 5 locked unlabelled (the EQ and 4 ride offsets) |
| Alignments | 27 | 14 sketch locks, 12 cap-face locks, the origin plane to the Level |

The five plane-mutation tests (Is-Reference pairings, unnamed plane, own/other/nested
owner) re-set *each* plane and count. They now run on a new `unconstrained_two_plane`
fixture, which is the same seven LCP parts built as a plain multi-part generic model with
no drive, i.e. the panel's old shape. A new test pins that fixture to the old numbers.

## Evidence (numbers)

- **CG7 errors before → after** (`constraint_law.check_file` on the written file):

  | Family | Before | After |
  |---|---|---|
  | panelboard | 2 | 0 |
  | panelboard 225A/400A types | 2 | 0 |
  | panelboard flush | 2 | 0 |
  | LCP | 0 (no drive) | 0 (14 sketch locks + 12 face locks) |

- **Byte identity of the centred callers, base vs this branch** (sha256 prefix, same
  inputs): generic single box `5412166132ebb870` = `5412166132ebb870`; troffer
  `5ed3b5e3fbf7e83f` = `5ed3b5e3fbf7e83f`; junction box `5f2f7e03b614dda3` =
  `5f2f7e03b614dda3`. The switchboard (`ifc/intent.py`) is also a centred box. It was not
  measured.
- **Read-back from the written file, 2026 and 2025.** Every sketch lock's GLine ends
  (`m_origin + m_dirVec·t`, t ∈ `m_endParams`) were checked against the lock's plane.
  - 0 off-plane locks for panelboard, panelboard flush, panelboard types, panelboard 600A
    and the LCP.
  - The count read back equals the number authored, and `check_file` returns `[]` on both
    releases.
- **`tools/rvt_validate.py`**: 0 errors / 0 warnings on LCP, panelboard and panelboard
  flush, for both 2026 and 2025 (6 files).
- **Self-battery rows** (panelboard, panelboard_types, panelboard_600A, 3 luminaires,
  archetype cable tray, archetype trapeze): 8/8 ok, law `ok`.
- **Refusals are SHA-identical to the build without the refused drive:**
  - Width drive with a bad part name, a planes/value mismatch, the wrong axis, or a
    caption whose value disagrees.
  - A refused attach: equal to the drive without the attach.
  - A refused height: off-face, unknown part, or an unauthored plane name.
  - A later duplicate height: equal to the good chain.
  - The new `wire_panelboard_drive` refusal adds no element and no plane.

## Open

- **#914 DONE 3 is not done.** It asks for the panelboard to move to `drive_law`
  (`wire_linear_drive` + the born in-plane law) and for the front parts (#897) to ride
  the face plane. This change keeps the old #372 chain and fixes only its geometry
  (DONE 1–2). Moving it would change the panelboard's law (born regen edge, no
  back-edges) and add attach planes. That is a new lane with its own desktop verdict, and
  its Depth is one-sided (see the next item).
- **Depth drives are one-sided.** The LCP's Cabinet Depth (y from the mounting plane at 0
  to the door) and the panelboard's Depth have no symmetric anchor. A one-sided in-plane
  drive needs its fixed end held to the origin centre plane, and no verified rung has that
  mechanism. Cabinet Depth is authored as a parameter but drives nothing.
- **The latch height** stays at mid-door when Cabinet Height flexes; it is not driven.
- **No desktop verdict** exists for the LCP assembly, the corrected panelboard chain, or
  any Case B height (hard rule 4). Planes on their edges is one plausible cause of the
  #372 / #689 failures, and only Revit can say whether it was the cause.
- The self battery has no `lighting_control_panel` row. Adding one would also put it
  through the battery's law step.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/param_drive.py`: planes on the profile edges, the mismatch refusal, and
  dimension points that follow the planes.
- `src/rvt/famgen/archetypes.py`: `_lcp_drives` docstring, new `_lcp_heights`, and the
  LCP registry entry wired (`family_params`, `drives`, `heights`).
- `src/rvt/famgen/constraint_law.py`: `check_file` under the file's own release.
- `plugin/lib/…`: mirrors (`tools/sync_plugin.py`).
- `tests/test_panel_drives_914.py` (new), `tests/ci_shard.d/914-panel-drives.txt` (new).
- `tests/test_constraint_law_910.py`: the xfail flipped.
- `tests/test_archetype_drives_913.py`: the LCP added to EXPECT; the baseline pin
  replaced.
- `tests/test_family_anatomy_837.py`: the LCP re-pinned and the two-plane fixture added.
- `tests/test_drive_law_904.py`: the drive=True fixture is now stacked, plus a new
  refusal test.
- This fragment.

**Gates:**
- `tools/sync_plugin.py` rebuilt the plugin; `--check` is clean.
- `plugin/scripts/validate_plugin.py` PASS (25 assertions).
- `check_portable_paths` ok.
- rvt_validate: 0 errors on 6 files (LCP, panelboard and panelboard flush, each for 2026 and 2025).
- pytest batch 1 (25 files: this test file, 913, 787, 910, constraint_law, 904 drive / follow, 837, 816, 820, 819, 892, famgen_parametric, param_profile 866/875/886, famgen_archetypes, famgen_factory, 882, 692 wiring, 812, 831, 168, plugin_sync, bootstrap): 1075 passed / 1 failed / 5 skipped / 5 xfailed. The one failure was the #904 drive=True fixture described above, since fixed.
- pytest batch 2 (19 files, including test_drive_law_904 again, ifc_intent, famgen catalog / skeleton / geometry, standards, 866, 859, 710): 495 passed / 17 skipped.

**Shipped vs staged:** shipped wired, no viewer batch staged. Authored, and the assembled
family is unverified.

---

## DONE 3 — the panelboard on `drive_law` (branch `panel-drive-law-914`, on `b345288`)

This section is the DONE 3 follow-up. It closes the first "Open" item above.

### What was built

- **`make_panelboard(drive="law")` is now the default.** The old #372 first-solid chain is
  still available as `drive="372"`, and that output is byte-identical to the base (below).
  `drive=None` wires no drive. Any other value raises `FactoryError`.
  - Specs come from `factory._panelboard_drive_specs`, which reads the geometry the
    panelboard was built with. The front parts get unique drive names from
    `_panelboard_named_forms`; the two hinges are told apart by height (`low` / `high`).
  - Wiring is done by `factory._wire_drive_specs` and `_wire_height_spec_list`. These were
    extracted unchanged from the multi-part generic model's code. The LCP, trapeze,
    junction box, cable tray and one-box outputs are byte-identical (below).
  - When at least one spec wires, `born_drive_law` is set, `finalize` writes no back-edges,
    and `apply_born_inplane_law` runs afterwards.
- **Width** (x). The box is centred in x (`center=(0, y_centre)`), so `symmetric: True` is
  sound.
  - **Locked to both Width planes:** the enclosure, the surface trim (full width) and the
    top clearance zone.
  - **Span the planes at fixed insets:** the door and the flush trim (which laps the
    opening by 0.75 in on each side).
  - **Ride one end rigidly:** the hinges ride the +x end and the latch rides the -x end.
  - **Stay where they are:** the nameplate (centred and narrow) and the front working
    space (its width is the 30 in code minimum, not the box width).
- **Depth** (y) is **one-sided**.
  - `drive_law.wire_linear_drive` gains `lo_plane=` / `hi_plane=`: an existing plane can
    stand in for one end. When it does, no new plane is made there, the labelled dimension
    witnesses that plane, and that side's edges are locked to it.
  - The factory spec key is `"lo_plane": "origin"`. Every check still runs before the
    first mutation: the plane must be in the document, square to the axis and exactly at
    `lo` / `hi`, and one plane cannot be both ends.
  - **Surface panel:** the back is held on the origin centre plane (y = 0, the wall plane).
    The face plane moves, and the trim, door, hinges, latch, nameplate and front working
    space ride it (`wire_attach`, locked unlabelled offsets).
  - **Flush panel:** the front is held at y = 0 and the back moves. Nothing rides.
  - In both cases the top zone's footprint follows both edges.
- **Height** uses the `height_law` Case B chain: origin → `cabinet top`.
  - **On the labelled Height chain:** the enclosure (both faces), a surface trim (both
    faces) and the top zone's base.
  - **Riding the cabinet top by locked unlabelled heights:** the door's top, the upper
    hinge, the nameplate, a flush trim's top lap and the top zone's top. Each distinct
    offset gets one plane.
  - **Not driven:** the latch, the lower hinge and the front working space.

### Evidence

- **Wired chain per variant** (from `prod.drives` / `prod.heights`):

  | Variant | Width | Depth | Height |
  |---|---|---|---|
  | surface (also 225/400 A types, 600 A) | 6 locks + EQ; 4 riding parts, 6 planes, 8 locks | 4 locks, `lo` anchored; 7 riding parts, 7 planes, 14 locks | 7 specs, 11 face locks, 6 locked |
  | flush | 4 locks + EQ; 5 riding parts, 8 planes, 10 locks | 4 locks, `hi` anchored | 8 specs, 10 face locks, 7 locked |

- **Profiled anatomy** (two-type panelboard): 23 dimensions (3 labelled, 20 unlabelled),
  44 alignments, 26 reference planes. Before: 2 dimensions, 4 alignments.
- **Read-back from the written file, 2026 and 2025**
  (`test_panel_drives_914::test_every_written_sketch_lock_lies_on_its_plane`): every
  sketch lock's GLine ends lie on its plane, for panelboard, flush, types and 600A.
  - The count read back equals the number authored, and `check_file == []`.
  - Two `drive="372"` keys were added so the old chain is still read back too.
- **`tools/rvt_validate.py`:** ok with 0 errors / 0 warnings on 10 files. That is
  surface, flush, types, 600A and solid=False, each for 2026 and 2025.
- **`tools/self_battery.py`:** 21/21 PASS.
- **Byte identity, base `b345288` vs this branch** (sha256 prefix, same inputs; the base
  build has no `drive` argument):

  | Build | sha256 prefix (both builds) |
  |---|---|
  | panelboard (base default vs `drive="372"`) | `b0b027b7323c46f0` |
  | flush | `cc1536b682497e01` |
  | types | `6072798fc42ae8f4` |
  | LCP | `291e846b72d3cbb7` |
  | trapeze | `701372e1b0150e9d` |
  | junction box | `5f2f7e03b614dda3` |
  | cable tray | `707398489a79868f` |
  | one-box `drive=True` | `4a220f3063c14f87` |

- **Refusals are SHA-identical to the build without the refused spec**
  (`tests/test_panel_drive_law_914.py`):
  - Width with a part name that matches nothing;
  - Width planes that disagree with the row;
  - Depth whose anchor is not at its fixed end;
  - Depth with an anchor that is not `origin`;
  - an attach naming a missing part (equal to the drive without the attach);
  - a locked height off every face (equal to the same build without it);
  - every spec refused, which equals `drive=None` and adds a "panelboard drives NOT wired" note;
  - an anchor off its end, not in the document, or used for both ends, at the
    `drive_law` level (document unchanged).

### Honest limits

- **No desktop verdict for any of this** (hard rule 4).
  - The one-box verdict (#787) used two **new, unanchored** planes about a centred box, and
    only Width was flexed. The anchored one-sided Depth is a new mechanism: a lock to the
    origin centre plane, and a labelled dimension witnessing it.
  - The panelboard's attaches combine Follow-ladder rungs in ways no probe tested.
  - Every Case B height is unverdicted.
  - The notes say all this: "one-sided; no desktop verdict", "assembled family unverified",
    "#787 Case B, NO desktop verdict".
- **Not driven when Height or Depth flexes:**
  - the front working space's height and its floor offset (computed once, from H and the
    nominal mount height);
  - the latch height;
  - the lower hinge.
- **The front working space keeps its x width** when Width flexes. That is right while
  W ≤ 30 in; a wider box is not re-derived.
- **The connector** is face-hosted on the enclosure top and is not separately constrained.
  Whether it follows a Depth/Height flex is Revit's call.
- **The multi-type note** now says the rows label the drive dimensions, authored and
  UNVERIFIED. It replaces "geometry is not label-driven yet".
- **Other users of the #372 chain are unchanged:** the IFC switchboard (`ifc/intent.py`),
  the troffer, `make_generic_model(drive=True)` and `parametric.py`.

### BRANCH STATE (DONE 3)

**Files written**
- `src/rvt/famgen/drive_law.py`: `wire_linear_drive(lo_plane=, hi_plane=)` (anchored end).
- `src/rvt/famgen/height_law.py`: `_surface_only` no longer sets the two `GeomTable`
  fields the native schema lacks (side fix, below).
- `src/rvt/famgen/factory.py`:
  - `_wire_drive_specs` / `_wire_height_spec_list` (extracted, plus the `origin` anchor);
  - `make_panelboard(drive=)`;
  - `_panelboard_named_forms`, `_panelboard_drive_specs`.
- `plugin/lib/…`: mirrors.
- `tests/test_panel_drive_law_914.py` (new, 19 tests), `tests/ci_shard.d/914-panel-drive-law.txt` (new).
- `tests/test_panel_drives_914.py`: the old-chain tests pinned to `drive="372"`, and two
  `_372` read-back keys added.
- `tests/test_family_anatomy_837.py`: the panelboard re-pinned (23 dims / 44 alignments).
  The EQ-mutation test now picks the first *labelled* dimension.
- This section.

**A side fix, found by the gates** (`height_law._surface_only`). Each surface-only
plane set two `GeomTable` fields (`m_maxSafeTag`,
`m_lastCheckedKingsUserModificationDate`) that the native schema does not carry. The
written bytes were exact, but `doc.roundtrip()` read the values back as unequal: 3
failures on the LCP and 17 on the trapeze before this branch. With heights wired, two
panelboard tests in `test_famgen_factory` (which assert a clean roundtrip) went red.
- The fields are no longer set. The 2025/2024 port writes -1 for them anyway.
- The written LCP and trapeze files are byte-identical on 2026
  (`291e846b72d3cbb7`, `701372e1b0150e9d`) and 2025 (`87e9d95fe702bab9`,
  `c61f8ef3d4587f98`), base vs branch.
- The roundtrip now has 0 failures on the LCP, the trapeze and the panelboard.

**Gates:**
- `tools/sync_plugin.py` rebuilt the plugin; `--check` is clean.
- `plugin/scripts/validate_plugin.py` PASS (25 assertions).
- `check_portable_paths` ok.
- `rvt_validate`: 0 errors / 0 warnings on 10 files.
- `self_battery`: 21/21.
- **pytest batch 1** (new file, `test_panel_drives_914`, `conftest_scaffolding`, 913, 816,
  `constraint_law` + 910, 904 drive / follow, `height_law_787`, 882, 819, 820, 892, 837,
  `famgen_parametric`, `param_profile` 866/875/886, `famgen_factory`, `famgen_archetypes`,
  `ifc_intent` + units + classify_equipment, `plugin_sync`, `bootstrap`):
  814 passed / 2 failed / 5 skipped. The 2 failures were the `test_famgen_factory`
  roundtrip pins, fixed by the side fix above.
- **pytest batch 2** (`famgen_factory`, `height_law_787`, 913, both 914 files, `famgen_adoc`,
  determinism 168, `required_settings`, `identity`, `families`, `famdoc_scan` ×2,
  `instance_rows_859`, `hostsym_product`, `famgen_geometry` / `skeleton`, `catchain`,
  `famload_determinism_794`, port2025 / port2024, y2024, formula 850, `coldstart`,
  `conftest_scaffolding`, `plugin_sync`): 546 passed / 3 failed / 72 skipped.
  - The 3 failures are `test_required_settings::test_refplane_cutvec_is_the_plane_normal`
    and `test_catchain`'s `materials_machinery` / `full_conjunction`.
  - They fail with the same messages on base `b345288`, so they predate this branch.

**Shipped vs staged:** wired by default; no viewer or desktop batch staged (steer #913: no
probe families to the owner). Authored, and the assembled family is unverified.
