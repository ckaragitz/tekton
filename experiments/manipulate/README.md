# experiments/manipulate — proof files for the manipulation API

Produced by `make_proofs.py` (rerun to regenerate; ~6 min). Full
machine-readable proof record: `proofs.json`. Six-file robustness pass:
`robustness.py` → `robustness.json`. Spec: `docs/writer/manipulation.md`.

Every `.rvt` below is written by the real writer and PASSED
`rvt.manipulate.verify_manipulated`: 0 CRC failures, 0 ECC-trailer
mismatches, 0 framing-walker errors, 0 block ISIZE mismatches, adler32
stamps valid, per-seq sentinels last, partition-header count == ElemTable
count, unit-0 seq-102 id set == ElemTable id set, deleted ids absent (all
seqs + ElemTable), edited records decode cleanly — AND a semantic re-read
(`Document.from_file(out)`) confirming the change took. Autodesk-Viewer
acceptance is the remaining oracle (orchestrator uploads these).

| file | source template | what it proves |
|---|---|---|
| `M1_delete.rvt` | rmebasicsampleproject | **delete, no dependents:** isolated air terminal 430715 (category −2008013) removed — its 3 records gone from unit 0, its `ElemRec` gone (count 28,132 → 28,131), id watermark unchanged. |
| `M2_delete_cascade.rvt` | rmebasicsampleproject | **delete WITH dependents:** wall 573703 (`SWall`). Without cascade `delete_element` raises `DependentsError` reporting 17 dependents (2 face `SketchPlane`s → 10 face-hosted plumbing fixtures at depth 2, 4 `LinearDimString`s, a `RoomTag`); `cascade=True` deletes all 18 elements and neutralises 37 referrers (24 `RbsPipeCurve` connector refs, 3 `RbsPipingSystem`s, 3 `RoomElem`s, 3 `VarSketch`es, 2 `LevelRoomPlan`s, 2 joined `SWall`s). Count 28,132 → 28,114. |
| `M3_modify.rvt` | rmebasicsampleproject | **modify parameters:** Level 2 (378118) elevation 12.467 → 14.467 ft (both Plane origins in the Level object); panelboard 581483 'Panel Name' `PP-1B` → `PP-1B-RENAMED` (BIP −1140078) and 'Mark' `15` → `15-EDITED` (BIP −1001203). Re-read confirms all three. |
| `M4_move_retype.rvt` | rmebasicsampleproject | **move + retype:** free-standing transformer 624416 translated +5 ft X (`InstanceInfo.m_Trf.m_or`, mirrored `m_instOrigin`, header bbox and the cached seq-103 `GElement` transforms/boxes all rewritten consistently) and retyped 500 kVA (symbol 621242) → 75 kVA sibling (621232), header appearance/deletion parents remapped. Re-read: Δ = (5,0,0) ft exactly, `symbolId == masterSymbolId == 621232`. |
| `M1_delete_rac.rvt` | racadvancedsampleproject | **delete, no dependents** on a file the tools were NOT built on: isolated structural framing instance 201309 (M_W-Wide Flange). Count 17,231 → 17,230. |
| `M2_delete_cascade_rac.rvt` | racadvancedsampleproject | **delete WITH dependents (host wall + door):** wall 144180 hosting door 145999. `DependentsError` reports the door (hosted), the door's tag 216514 (depth 2), the wall's tag 216554 and a `LinearDimString`; cascade removes the 5; 12 referrers neutralised (4 joined `SWall`s incl. the neighbour whose windows listed 144180 in `m_deletion`, those 2 windows, 3 `CurveElem`s, 2 ceiling `VarSketch`es — the ceiling KEEPS its sketch minus the wall constraint — and a `LevelRoomPlan`). Count 17,231 → 17,226. |
| `M3_modify_rac.rvt` | racadvancedsampleproject | **modify parameters:** level '03 - Floor' (136342) 24.934 → 25.934 ft; door 147834 'Mark' `130A` → `130A-EDITED`. Re-read confirms both. |
| `M4_move_retype_rac.rvt` | racadvancedsampleproject | **move + retype:** dining table 180360 translated +5 ft X TOGETHER WITH its 4 ElemTable-owned chair sub-instances (`include_owned`), then retyped 0915 mm (180235) → 1525 mm (180237). Re-read: Δ = (5,0,0) ft, `symbolId == masterSymbolId == 180237`. |

Reproduce:

```
.venv/bin/python experiments/manipulate/make_proofs.py   # writes the 8 files + proofs.json
.venv/bin/python experiments/manipulate/robustness.py    # writes robustness.json
```
