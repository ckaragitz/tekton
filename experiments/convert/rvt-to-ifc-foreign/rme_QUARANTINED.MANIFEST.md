# rvt->ifc (rvt.convert.rvt_to_ifc) -- deliverable manifest

## The deliverable(s)
* **ifc**: `experiments/convert/rvt-to-ifc-foreign/rme_QUARANTINED.ifc` (118,512 bytes, sha256 ce4d251e992b0f8e...)

## Provenance
* source lineage: foreign (native Revit save lineage)

## Stamps (labels, not refusals)
* FOREIGN DESIGN CONTENT: the source model was not authored by tekton -- the exported IFC carries THAT model's design content (their walls, their equipment identities, their parameter values). Dev/interop artifact for the file's owner; never shipped as tekton content.
* QUARANTINED SOURCE (dev-only): the source is research-corpus / third-party sample content; this export exists to prove the converter works on foreign files and stays in experiments/.

## Extraction cells (honest per-cell status)
* levels: **works** {"count": 4}
* walls: **works** {"count": 133}
* equipment: **works** {"count": 29}
* feeders: **works** {"circuits_total": 187, "edges_between_equipment": 28, "circuits_to_other_loads": 122, "circuits_unresolved": 37}

## Round-trip survival (the acceptance)
* equipment: 29/29 survived (tag + kind + position + front)
* walls: 131/133 matched (in 133, resolved 80)
* feeder edges: 28/28 matched
* ALL SURVIVED: **False**
  * EP-2: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * PP-2B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * LP-2: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * PP-3B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * EP-3: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * LP-3: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * CTP: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * AHP: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * LP-1: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * PP-1B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * EP-1A: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * EP-1B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * LP-1B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * MP-1B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * PP-1A: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * TP-1A: kind transformer -> transformer pos-delta [0.0, 0.0, 0.0] survived=True
  * T-SVC: kind transformer -> transformer pos-delta [0.0, 0.0, 0.0] survived=True
  * LP-2B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * MP-2B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * PP-2A: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * TP-2A: kind transformer -> transformer pos-delta [0.0, 0.0, 0.0] survived=True
  * LP-3B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * MP-3B: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * PP-3A: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * TP-3A: kind transformer -> transformer pos-delta [0.0, 0.0, 0.0] survived=True
  * SWB: kind switchboard -> switchboard pos-delta [0.0, 0.0, 0.0] survived=True
  * MDP-1: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * MDP-2: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True
  * MDP-3: kind receptacle_panelboard -> receptacle_panelboard pos-delta [0.0, 0.0, 0.0] survived=True

## Caveats
* round-trip survival is PARTIAL -- see roundtrip table; the IFC is still delivered (the table is the honest label)

