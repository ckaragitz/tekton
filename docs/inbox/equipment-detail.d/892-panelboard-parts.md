# 892 — a generated panelboard is built from its real parts

Stream **equipment-detail** (tech-lead session, 2026-10-01). Issue #892.

**Ask.** The owner wrote: "With all the input and principles you have learned. Build be a 225A Panel board for Branch Power." Generated panelboards were still one box plus their clearance zones. #879 had already fixed the same thing for transformers ("this looks absolutely nothing like a transformer").

## What was built

**`equipment_detail.panelboard_parts(W, D, H, flush=)`** lays out the cabinet front on the box face (+y; a flush box's face is the wall at y = 0). Every proportion is nominal:
- a front trim, 3/16 in thick;
- a door, 1/8 in thick, inset 6.5 % of W at the sides (clamped 0.75–1.5 in) and 4.5 % of H at the ends (clamped 1–2.5 in);
- 2 hinges on the door's left edge as you face it (+x), at 1/5 and 4/5 of its height;
- a latch handle on the right (−x), at mid height;
- a nameplate at the top of the door.

The first version also had 6 trim screws and a separate key lock. They were dropped after session CI, for latency (see Evidence).

A flush trim laps the wall opening by 0.75 in all round. `front_proud_ft` gives how far the hardware stands proud of the face.

**`make_panelboard`** authors those parts after the catalog box:
- The box stays form 0, so the Width/Depth drive and the top-face connector are untouched.
- The NEC working space now starts in front of the door hardware.
- The dummy variant stays one box.

## Evidence

- `tests/test_panelboard_detail_892.py` (8 tests; the flush factory test was added after review):
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

- **Latency** (S-2026-08-09-g). The flagship `go author "an electrical room with 6 panels"` builds and loads six panel families, so every part is paid twelve times.
  - The first version had 13 front parts. Session CI failed `test_surface_perf.py::test_bare_go_author_6panels_under_ceiling` at 9.55 s against the 8.0 s ceiling. My local run measured 8.28 s.
  - Two changes:
    - `rvt.genesis.types.blank_object` keeps one prototype per class, inside the release-swapped state dict, and returns a fast deep copy. An isolated panel build plus write went from 0.67 s to 0.40 s. It barely moves the flagship (family build 1.9 s → 1.78 s on main).
    - The front was cut to 6 parts. The screws and the separate key lock are sub-inch at project scale.
  - `tools/surface_bench.py --from-tree --surfaces local --jobs go-author-6panels`, interleaved runs on the same VM:

    | | runs | median |
    |---|---|---|
    | main | 5.16, 5.48, 5.79 s | 5.48 s |
    | this PR | 6.01, 6.62, 6.05 s | 6.05 s |

  - **Correction (#893 PR).** The independent reviewer of #897 ran 6 interleaved runs on each side:

    | | runs | median |
    |---|---|---|
    | main | 6.14, 5.12, 5.18, 5.38, 5.70, 5.35 s | 5.37 s |
    | this PR | 7.10, 5.87, 6.46, 6.05, 6.34, 6.37 s | 6.36 s |

  - So the front costs about **+1.0 s (+18 %)**, not +0.6 s as my 3-run sample above said, with about 1.6 s left under the ceiling. Session CI passed the gate at head `a88fafc`.
  - **Tiny boxes (#893 PR).** A box under 6 in wide or 12 in high has no room for the door. `panelboard_parts` refuses it, and `make_panelboard` then delivers the box with a "front NOT drawn" note (hard rule 1).
  - The stage split is about +0.3 s in F (build) and +0.3 s in L (load).

## Open

- No desktop verdict on the look (hard rule 4).
- The parts do not follow an edit of the driven parameters (Width and Depth). They are authored at the primary type's box, as the transformer's are. A Depth edit moves the box face, while the front parts and the working-space start stay at the original D. Height is not driven at all.
- The dead front, breakers and directory card are inside the door and not modelled.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`.
- Written:
  - `src/rvt/famgen/equipment_detail.py` (`panelboard_parts`, `front_proud_ft`, `PANEL_DETAIL_NOTE`), `src/rvt/famgen/factory.py` (`make_panelboard` and its docstring);
  - `src/rvt/genesis/types.py` (the `blank_object` prototype cache);
  - `tests/test_panelboard_detail_892.py` and its drop-in;
  - the three count updates, this fragment, and the mirrors.
- Staged: nothing.
- No certification claim.
