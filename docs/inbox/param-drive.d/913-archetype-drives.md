# 913 — every sheet-metal / channel archetype built with its parts constrained

Stream: **param-drive** (fragment; index `../param-drive.md`). Steer **#913** (*"stop
making test families continue to structure our code off the reference families dont stop
until everything is complete"*), plan step 4. Builds on #904 (`904-drive-law.md`,
`904-follow.md`). No probe families were made for this change, per the steer.

## What was built

- **`drive_law.wire_attach(doc, items, axis)`** moves part edges with their drive
  planes, at their current offsets. Each edge gets a plane at its offset from the plane
  it rides, held there by a locked unlabelled dimension. That is the P2 rung's chain,
  desktop-verified (#904 "Follow" ladder). Every item is checked before the first
  mutation, and an edge is never locked twice.
  - **Riding:** an item whose edges both follow the same plane moves rigidly with it (a
    tray rail on the Tray Width plane).
  - **Stretching:** an item whose two edges follow different planes stretches between
    them (a box wall between top and bottom).
- **The factory.** A drive spec may carry `attach: {"lo": [...], "hi": [...], "span":
  [...]}`. It is all-or-nothing, never undoes the drive it builds on, and is noted when
  refused. The summary note names the riding parts.
- **`drive_law.drivable_spec`** decides which parameter specs a dimension may be
  labelled with. It accepts exactly the four specs Revit-born families use, from a
  corpus census of labelled dimensions: length (2,504), conduit size (92), cable-tray
  size (19) and pipe size (8). Everything else is refused, as before for anything but
  length.
- **Archetypes.** Each one's own dimensions are now family parameters with distinct
  captions; the overall Width/Depth/Height stay the bounding box. Each gets symmetric
  in-plane drives:

  | Archetype | Drive | What moves |
  |---|---|---|
  | **Cable tray** | **Tray Width** (the category's standard parameter, cable-tray-size spec) | rungs locked; both rails, web and flanges, ride it |
  | | **Length** | all six rail parts |
  | **Wireway** | **Wireway Width** | bottom and cover locked; the sides ride it |
  | | **Length** | all four parts |
  | **Junction box** | **Box Width** | back, top/bottom walls and cover locked; the side walls ride it |
  | | **Box Height** | back and cover locked; top/bottom walls ride it; the side walls stretch between |
  | **Strut channel** | **Length** | webs and lips at both ends; a slotted back's end segments |
  | | **Section Width** | the back locked; the webs and lips ride it |

- **The lighting control panel is unchanged here.** The family-anatomy suite pins it as
  its unconstrained baseline. Its Cabinet Width drive (`_lcp_drives`, written) lands
  with its height and depth in its own change, with the pins updated deliberately.

## Evidence

- Every archetype for 2026 and 2025 is VALID with 0 errors and PROVENANCE-CLEAN. On
  read-back of the written file, every sketch lock lies on its plane:

  | Archetype | Locks | Off-plane |
  |---|---|---|
  | cable tray | 44 | 0 |
  | wireway | 16 | 0 |
  | junction box | 24 | 0 |
  | strut channel | 20 | 0 |
  | trapeze | 56 | 0 |

  There are 0 `m_constrInfo` and 0 unclean records.
- **`tests/test_archetype_drives_913.py`:** 18 tests.
  - Per archetype: the drives wired, the counts, symmetric ends, and no refusal notes.
  - Every lock in the written file on its plane.
  - The slotted channel's end segments.
  - The drivable specs: four accepted, everything else refused.
  - The control panel still unconstrained.

## Open

- **A desktop verdict for each archetype.** The mechanisms are verified one by one; the
  assembled families are not (hard rule 4).
- **Heights and depths** (tray depth, wireway height, box depth) need the extrusion end,
  #787 Case B (`height_law`, in progress).
- **Rung spacing:** the rungs keep their pitch when Length flexes, and the end bays absorb
  it. A labelled rung pitch needs an array or formula lane.
- **The lighting control panel and the panelboard** (#914) get their drives in their own
  changes.
- **The conduit** is a horizontal cylinder (rotated B-rep): its length is the extrusion
  end, and its diameter is #916.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/drive_law.py`: `wire_attach`, `DRIVABLE_SPECS` / `drivable_spec`.
- `src/rvt/famgen/factory.py`: the `attach` spec plumbing and the summary note.
- `src/rvt/famgen/archetypes.py`: per-archetype `family_params` / `drives`.
- `plugin/lib/…`: mirrors.
- `tests/test_archetype_drives_913.py`: new.
- `tests/ci_shard.d/913-archetype-drives.txt`: new.
- this fragment.

**Gates:** see the PR.

**Shipped vs staged:** shipped wired. No assembled family has a desktop verdict.
