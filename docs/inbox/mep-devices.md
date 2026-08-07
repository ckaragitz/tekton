# Inbox — MEP stream "devices" (electrical devices + fixture instances)

Agent: mep-devices (wave: MEP product bar), 2026-08-03.
Full spec: `docs/writer/mep-devices.md`. Module: `src/rvt/mep/devices.py`.
Tests: `tests/test_mep_devices.py` (18 passed). Proofs + manifest:
`experiments/mep/devices/{*.rvt, make_devices.py, manifest.json}`.

## What was built

Full CRUD over the point-hosted electrical categories a contractor touches
(receptacles / switches & sensors / lighting-fixture INSTANCES / data-comm-
fire-security devices / floor & free devices), placing only from families
ALREADY LOADED in the target file, plus circuits over MULTIPLE loads.

* CREATE — `add_wall_device` (dummy-plane-on-face = the 98 % corpus pattern,
  or a real `GeomOnPlaneRef` face reference; planes shared between devices),
  `add_device_on_plane` (any existing / planned plane), `add_ceiling_plane` +
  `add_light_fixture` (down-facing ceiling work plane — the corpus never
  references a Ceiling element), `add_level_datum_plane` + `add_floor_device`
  (`OnDatumPlaneRef -> level` plane, or truly free), `add_multi_load_circuit`
  (N receptacles on one 20 A circuit off one panel, real-model closure).
* EDIT (wrappers over `rvt.manipulate`, device semantics added):
  `set_device_mark`, `set_mounting_height`, `move_device_along_host`
  (slides ON the face), `rehost_device` (to another face: host id + frame +
  header parents), `retype_device`, `delete_device` (clean detach: circuit /
  wires / panel referrers neutralised, host plane and circuit survive, tags
  cascaded), `device_placement`.
* Created devices are "nativeised": space/room resolved into
  `ElectricalFamInstDesignPropertyManager` + the exact native header-parent
  shape (space/room, UnitsElem, geo-tracker, MEP system tracker, family),
  Mark holder created for families that never had one (switches). This is
  higher fidelity than the bare `rvt.hosting` output.

## Corpus findings (evidence in mep-devices.md §1-§5)

1. Wall receptacles/switches are hosted (416/424, 63/63) on a vertical
   `DummyPlaneRef` work plane COINCIDENT with the wall face; only 8 receptacles
   use a `GeomOnPlaneRef` into the wall.
2. Ceiling lights (410/410) stand on horizontal DOWN-FACING `DummyPlaneRef`
   planes at the ceiling underside (48 planes); NO plane in the file references
   a `Ceiling` element. Fixture Z = the plane's -Z, rotated in-plane.
3. Level hosting = `OnDatumPlaneRef` plane whose `m_datumPlaneId` IS the level
   (specimen 573289 + instances 579920-23). Free (`hostId -1`) is for
   equipment-style families only.
4. Multi-load circuits: one connector per load (connType 1 -> load's supply
   connector) + FINAL base connector (connType 4 -> panel's next free
   50000-series slot); `baseConnectorIdArray = {self, LAST}`; every load and
   the panel back-link (connType 4). Internal volts / VA = SI / 0.3048^2.
5. **CORRECTION for KNOWLEDGE.md ("Electrical circuits" section):**
   `m_pathNodes[0].m_elemId` = the PANEL (base equipment), verified 171/171
   circuits that have path nodes — NOT "first load". `mutate.Document.
   add_circuit` writes the first load there; `devices.add_multi_load_circuit`
   writes the panel. (Suggested KNOWLEDGE edit + a one-line change in
   `add_circuit`: `nd["m_elemId"] = panel.elem_id` — writer core, not
   touched here.)

## Findings for other streams (please act — writer core is off-limits for me)

A. **Identity scrub breaks the validator's L2 invariant on EVERY
   `commit_new_elements` output.** The G2 scrub (`identity.own_basic_file_info`,
   called inside `commit_new_elements`) mints a fresh Unique Document GUID but
   the minimal commit adds NO History episode => `tools/rvt_validate.py`
   ERROR "Unique Document GUID != History entry[0] GUID" on every created file
   (the H-files / V-files made after G2 landed likely fail it too — re-check).
   My proofs pass `identity={"document_guid": <template's own GUID>}` to stay
   self-consistent and validator-clean. Real fix (identity / save-history
   stream): mint the GUID AND prepend a History episode with it
   (`streams_edit.record_save()`), or make the scrub's default keep the GUID
   until the full save-record path is wired.
B. **Create-path block-counter defect (commit.py) — the only strict-gate
   finding on my created files** ("3 blocks whose A/C violate the ISIZE
   identity"; tolerated by Autodesk, V20-V29). Root cause: `commit._hdr_len`
   returns 12/16 (record header bytes) but the ISIZE identity uses the
   wave-1 record length 16/20 (header + 4-byte trailing psize repeat), so C is
   off by 4*A on the 3 spliced blocks. `manipulate.chunk_segment` uses the
   correct `record_header_len(seq)` (my edit/delete proofs are strict-clean).
   Exact generic-hook diff for `src/rvt/commit.py` (orchestrator to apply):

       - c_new = len(payload) - _hdr_len(b.seq) * a_new - adj
       + c_new = len(payload) - record_header_len(b.seq) * a_new - adj

   with `from .partitions import record_header_len` (leave `_hdr_len` for the
   sentinel-length maths, which needs the 12/16 header size).

## Proof files — validation summary (manifest.json)

All six: STRUCTURALLY VALID (0 CRC failures, 0 ECC mismatches, 0 walker
errors, stamps ok, counts match, sentinels last), semantic readback OK, and
`tools/rvt_validate.py` = **0 ERRORS** each (default oracle-calibrated
gate). Strict "circuit-ready" gate: PASS on the edit/delete files; on the four
created files the ONLY strict finding is the writer-core counter defect (B) —
zero connector / reference / circuit / dangling findings from this module.
Warnings on every file = the known 1,171-record Extensible-Storage decode gap
(pre-existing corpus fact).

## Open items / proposed follow-ups

* O1 circuiting EXISTING devices/panels needs the two-sided connector edit
  applied as in-place edits inside ONE commit (`commit_new_elements` +
  `commit_plans` are separate paths today) — a combined create+edit commit
  would unlock it; the parallel `rvt.mep.electrical_data` stream mentions a
  `commit_electrical` combined commit which would be the natural home.
* O4 deleting the last load of a circuit leaves an empty member connector;
  Revit may drop such a circuit — a "delete circuit when emptied" policy
  should be decided at the manipulate layer.
* O5 new panels have a fixed 50000-series slot count (4 on the 208 V MLO
  family); >4 circuits per NEW panel needs appended Connector objects with
  fresh archive pids (an encoder-level facility: renumber-pids-in-a-cloned-
  subtree).
* Autodesk-viewer certification of the six proof files is the remaining
  [H] -> [V] step (orchestrator's browser run).

## CELL TABLE

| category | verb | status | proof file | notes |
|---|---|---|---|---|
| receptacle | CREATE | PROVEN-viewer-pending | experiments/mep/devices/receptacle_wall_hosted.rvt | Standard duplex on a NEW DummyPlaneRef work plane coincident with the east wall's room face (98% corpus pattern) + GFCI on a GeomOnPlaneRef face plane (m_elemId=wall 573609, tag 5); 1.5/3.5 ft AFF; Marks R-101/R-102; space/room set; validates 0 errors |
| switch | CREATE | PROVEN-viewer-pending | experiments/mep/devices/receptacle_wall_hosted.rvt | single-pole switch S-101 SHARING the receptacle's plane at 3.65 ft AFF (plane sharing = corpus norm); AString Mark holder created for a family that had none |
| lighting_fixture | CREATE | PROVEN-viewer-pending | experiments/mep/devices/light_ceiling_hosted.rvt | 2 recessed troffers on ONE new down-facing ceiling plane (z 20.51 = ceiling 580538 underside, Z=(0,0,-1), schedule to Level 2) + a pendant on the EXISTING ceiling plane 442678; the 410/410 corpus pattern (no ceiling reference) |
| floor_device | CREATE | PROVEN-viewer-pending | experiments/mep/devices/floor_device.rvt | floor receptacle work-plane-hosted on a NEW OnDatumPlaneRef plane -> LEVEL 1 (m_datumPlaneId=378117) + a FREE-standing 15 kVA transformer (hostId -1, level-based) |
| circuit_multi_load | CREATE | PROVEN-viewer-pending | experiments/mep/devices/multi_load_circuit.rvt | ONE 20 A / 120 V / 1 P circuit #1 "Receptacles" carrying FOUR new receptacles (2 walls, 2 shared planes) off a new 208 V panel: 4 load connectors (connType 1) + base connector -> panel slot 50000 (connType 4); every load + the panel back-link (connType 4); baseConnectorIdArray={self,LAST}; pathNode0=panel; 4x180 VA + 120 V in internal units; validator connector-graph + circuit checks clean |
| panelboard | CREATE | PROVEN-viewer-pending | experiments/mep/devices/multi_load_circuit.rvt | 208 V MLO 400 A panel (LP-DEV1) hosted on the EXISTING electrical-room plane 581481 (instances sharing an existing plane), slot allocated to the new circuit |
| receptacle | MODIFY | PROVEN-viewer-pending | experiments/mep/devices/device_modify_move.rvt | Mark of existing receptacle 467473 set to R-EDITED (byte-exact re-encode + splice; validator 0 errors, strict-clean) |
| receptacle | MOVE | PROVEN-viewer-pending | experiments/mep/devices/device_modify_move.rvt | 467523 slid +2.0 ft along its wall and +0.5 ft up WITHIN its host plane (0 off-plane, host kept); 467456 RE-HOSTED to the east-wall plane 453884 (m_hostId, frame = new plane frame, mounting point ON it, header deletion parent swapped) |
| receptacle | RETYPE | PROVEN-viewer-pending | experiments/mep/devices/device_modify_move.rvt | 467480 Standard (342654) -> GFCI (342652): symbolId + masterSymbolId + rep + parents remapped |
| receptacle | DELETE | PROVEN-viewer-pending | experiments/mep/devices/device_delete.rvt | circuited receptacle 467291 removed; its circuit 469428's member connector, 2 wires and the panel bookkeeping neutralised (nothing dangling); shared host plane 467294 and the circuit survive; strict-clean |
| lighting_fixture | DELETE | PROVEN-viewer-pending | experiments/mep/devices/device_delete.rvt | pendant 444176 removed with its 2 IndependentTags cascaded; circuit 473648 + 6 wires neutralised; strict-clean |
| lighting_fixture | MOVE / RETYPE | VALIDATES | (module functions move_device_along_host / rehost_device / retype_device apply to any face-hosted instance; exercised on receptacles in the proof, unit-tested generically) | verbs are category-agnostic (same FamilyInstance record shape); no separate light-specific proof file built — cheap to add on request |
| junction box / disconnect / data-comm-fire-security devices | CREATE..DELETE | VALIDATES (no loaded family in the template) | — | same code path as receptacle/switch (add_wall_device / add_ceiling / add_floor with any loaded symbol of those categories); the rme sample loads no j-box / disconnect / data-device family to instantiate, so no proof file — needs a template that has one loaded (or the family-authoring stream) |
| circuit to EXISTING panel | CREATE | BLOCKED (phase 2) | — | needs the two-sided connector edit as in-place record edits inside one combined create+edit commit (open item O1) |

BRANCH STATE: mep-devices — module + 18 tests + 6 proof files complete; all six proofs STRUCTURALLY VALID, semantic readback OK and 0 validator errors (edit/delete files strict-clean, created files strict-blocked ONLY by the writer-core counter defect diff'd above); full suite result reported by the agent; viewer certification pending; two writer-core findings (identity/History GUID, commit.py counter) filed above for the orchestrator.
