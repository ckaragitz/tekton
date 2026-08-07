# rvt->ifc (rvt.convert.rvt_to_ifc) -- deliverable manifest

## The deliverable(s)
* **ifc**: `experiments/convert/rvt-to-ifc/electrical_room_prompt.ifc` (15,040 bytes, sha256 81348f369d6eb6b0...)

## Provenance
* source lineage: tekton-authored (self-reported BasicFileInfo author)

## Extraction cells (honest per-cell status)
* levels: **works** {"count": 9}
* walls: **works** {"count": 4}
* equipment: **works** {"count": 4}
* feeders: **missing** {"circuits_total": 0, "edges_between_equipment": 0, "circuits_to_other_loads": 0, "circuits_unresolved": 0}

## Round-trip survival (the acceptance)
* equipment: 4/4 survived (tag + kind + position + front)
* walls: 4/4 matched (in 4, resolved 4)
* feeder edges: 0/0 matched
* ALL SURVIVED: **True**
  * MSB: kind switchboard -> switchboard pos-delta [0.0, 0.0, 0.0] survived=True
  * DP-1: kind distribution_panelboard -> distribution_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * LP-1: kind lighting_panelboard -> lighting_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * T1: kind transformer -> transformer pos-delta [0.0, 0.0, 0.0] survived=True

