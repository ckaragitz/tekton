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
