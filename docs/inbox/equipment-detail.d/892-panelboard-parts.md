# 892 — a generated panelboard is built from its real parts

Stream **equipment-detail** (tech-lead session, 2026-10-01). Issue #892.

**Ask.** The owner wrote: "With all the input and principles you have learned. Build be a 225A Panel board for Branch Power." Generated panelboards were still one box plus their clearance zones. #879 had already fixed the same thing for transformers ("this looks absolutely nothing like a transformer").

## What was built

**`equipment_detail.panelboard_parts(W, D, H, flush=)`** lays out the cabinet front on the box face (+y; a flush box's face is the wall at y = 0). Every proportion is nominal:
- a front trim, 3/16 in thick;
- a door, 1/8 in thick, inset 6.5 % of W at the sides (clamped 0.75–1.5 in) and 4.5 % of H at the ends (clamped 1–2.5 in);
- 2 hinges on the door's left edge as you face it (+x), at 1/5 and 4/5 of its height;
- a latch handle and a key lock on the right (−x), at mid height;
- 6 trim screws at the corners and the mid-sides;
- a nameplate at the top of the door.

A flush trim laps the wall opening by 0.75 in all round. `front_proud_ft` gives how far the hardware stands proud of the face.

**`make_panelboard`** authors those parts after the catalog box:
- The box stays form 0, so the Width/Depth drive and the top-face connector are untouched.
- The NEC working space now starts in front of the door hardware.
- The dummy variant stays one box.

## Evidence

- `tests/test_panelboard_detail_892.py` (7 tests):
  - the parts stand on the face, within the box outline, under 1 in proud;
  - the hand of the hinges and latch;
  - the flush lap;
  - a refused box;
  - the 225 A / 42-circuit / 208Y/120 PRL1X (20 × 48 × 5.75 in catalog box) authored with its parts, a 3 ft working space starting at the hardware, VALID with 0 errors and provenance ok;
  - the dummy variant.
- Updated pinned counts: `test_famgen_factory.py` (composition, multi-type), `test_family_anatomy_837.py` (16 forms) and `test_equipment_clearance_882.py` (the zone starts at the hardware).
- The famgen, plugin and bootstrap suites: 920 passed / 59 skipped.
- **Delivered to the owner:** `Panelboard_225A_MCB_42ckt_208Y120_BranchPower_R2026/R2025.rfa`, built with their private parameter profile. Both are VALID with 0 errors under `rvt_validate` and family mode, with provenance ok and 16 forms.
- The first build put the latch on the viewer's left. It was caught in a rendered preview and fixed before delivery: facing the door from +y, your left is +x.

## Open

- No desktop verdict on the look (hard rule 4).
- The parts do not follow a Width or Height edit: they are authored at the primary type's box, as the transformer's are.
- The dead front, breakers and directory card are inside the door and not modelled.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`.
- Written:
  - `src/rvt/famgen/equipment_detail.py` (`panelboard_parts`, `front_proud_ft`, `PANEL_DETAIL_NOTE`), `src/rvt/famgen/factory.py` (`make_panelboard`);
  - `tests/test_panelboard_detail_892.py` and its drop-in;
  - the three count updates, this fragment, and the mirrors.
- Staged: nothing.
- No certification claim.
