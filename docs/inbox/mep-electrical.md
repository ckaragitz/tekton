# RECORD — mep-electrical: WIRING + ELECTRICAL SETTINGS + PANEL DATA (2026-08-03)

Territory: `src/rvt/mep/electrical_data.py` (+ `src/rvt/mep/__init__.py`),
`tests/test_mep_electrical_data.py`, `experiments/mep/electrical/*`,
`docs/writer/mep-electrical-data.md`, this file. DONE = the cell table
below, every cell backed by a generated proof file that passes
`tools/rvt_validate.py` with ZERO errors — MET (5/5 files PASS,
`experiments/mep/electrical/manifest.json` `all_ok: true`).

## What was built

`src/rvt/mep/electrical_data.py` — full CRUD over the electrical-data slice
of a Revit MEP project, on top of the writer core (never edited):

* **Wires (`RbsWireCurve`, home runs / branch wiring).** Decoded the model
  from the 1,045 rme wires: view-owned (`m_ownerDBViewId`), circuits carried
  in `ElectricalDomainDesignPropertyManager.m_setidCircuits` (a ONE-WAY link
  — circuits never list their wires), a 2-connector
  `RbsCurveConnectorManager` whose ends reference each other AND the
  connected devices (`connType 1`), with the DEVICES referencing the wire
  back on their supply connector (index 1). Home run = a wire whose START
  end has no device (Revit draws the arrow there; wires NEVER connect to a
  panel — 0/2,003 corpus edges). `add_wire(doc, circuits, from_device,
  to_device=None, wiring_type='arc'|'chamfer')` / `add_home_run()` clone a
  real wire, rebuild endpoints/GLine chord/points, the connector closure,
  end flags (`m_bDynamicUpdateEnds` = connection state, 400/400) and the
  header parents, AND emit ModifyPlans that append the back-link to each
  connected device's connector. `delete_wire()` = manipulate cascade delete
  (tag cascades, back-links neutralised).
* **Electrical settings as editable data.** `electrical_settings(doc)`
  inventories voltage types (V ÷ 0.3048² internal units), distribution
  systems (Vll/Vlg resolved), wire types (Revit-2026 conductor
  material/insulation/temperature resolve to `CustomElement`+`NamingCell`
  names), the wire ampacity table, demand factors (rules 0/3/4 = constant /
  motor ranking / NEC 220.44 range table), load classifications (each a
  CLOSURE: own demand factor + six `ParamElemElectricalLoadClassification`
  with `m_typeId = 'revit.local.classification:'+session-GUID+8-hex-elemid`),
  and the `ElectricalSetting` / `RbsWireSettingsElem` singletons. CREATE:
  `add_voltage_type / add_distribution_system / add_demand_factor /
  add_load_classification` (whole closure). MODIFY: `set_demand_factor /
  set_voltage_type / rename_setting / set_load_classification /
  modify_setting` (manipulate JSON-path edits).
* **Panel data.** `panel_info()` (name −1140078, dist system −1140064 →
  voltages, mains −1140082, max poles −1140079, slot connectors 50000-series,
  numbering option), `panel_circuits()`, `check_panel_numbering()`, and
  `renumber_circuits(doc, panel)` implementing Revit's two-column rule
  (n-pole = n same-parity slots, lowest fit), writing `m_number` +
  `m_nStartSlot` per circuit. The rule REPRODUCES Autodesk's own numbering
  on the untouched panels PP-2B / PP-3B including their 3-pole '20,22,24' /
  '19,21,23' circuits (test + manifest).
* **`commit_electrical(src, out, doc, new_elements=, plans=)`** — a combined
  create+edit commit (new records inserted before the sentinel + record
  replacements/removals + ElemTable adds/drops in ONE re-emit of unit 0),
  composed from the public pieces of `commit.py` / `manipulate.py`. Needed
  because a wire and its devices' back-links must land in the same file.
  `verify_electrical()` wraps `verify_manipulated` + a `structurally_valid`
  verdict.

## Evidence

* Full model + evidence + confidence table: `docs/writer/mep-electrical-data.md`.
* Proof files (all PASS: structural VALID, semantic readback OK,
  `rvt_validate` 0 errors — the single warning is the corpus-wide
  pre-existing Extensible-Storage decode gap the untouched sample also has):

| category | verb | status | proof file | notes |
|---|---|---|---|---|
| wires (`RbsWireCurve`) | READ | VALIDATES | (module + tests) | 1,045 wires modelled; view/circuit/connector closure |
| wires | CREATE | VALIDATES | `experiments/mep/electrical/wire_create.rvt` | home run (free arrow end→device) + chamfer branch wire (device↔device) for circuit 469513; devices 466882/467749 back-linked in the same commit; connector graph stays symmetric |
| wires | DELETE | VALIDATES | `experiments/mep/electrical/wire_delete.rvt` | wire 469466 removed; devices 467291/467473 + neighbour wire 469465 neutralised |
| wires | MODIFY | n/a (by design) | — | wire endpoints follow their devices; retag/reroute = delete + create |
| electrical settings | READ | VALIDATES | (module + tests) | 5 voltages, 3 dist systems, 2 wire types (+ conductor domains, ampacity table), 12 demand factors, 10 load classifications, 2 singletons |
| electrical settings | MODIFY | VALIDATES | `experiments/mep/electrical/settings_modify.rvt` | one of every settings class edited (HVAC df 1.0→0.85, 120 V max→132, dist system rename, wire type share-ground, 'Receptacles' abbr, default ckt rating 20→30 A, tick separator) |
| electrical settings | CREATE | VALIDATES | `experiments/mep/electrical/load_class_create.rvt` | load classification 'EV Charging' = full closure (df + 6 params, mutual parents, fresh typeIds) + new '600/347 Wye' dist system on two new voltages; 11 new elements |
| electrical settings | DELETE | (core) | — | via `manipulate.delete_element` (closure cascades: voltage→systems, classification→factor+params) |
| panel data | READ | VALIDATES | (module + tests) | panel params (name/dist-system/voltages/mains/poles/slots) + circuit schedule fields |
| panel data | MODIFY (renumber) | VALIDATES | `experiments/mep/electrical/panel_renumber.rvt` | PP-1A hole@2 → 1..17, LP-2 holes@1/14/19 → 1..17; rule proven = Autodesk's on PP-2B/PP-3B |

  "VALIDATES" = writer structural verify clean + `tools/rvt_validate.py`
  (structure + consistency + semantic) 0 errors + semantic re-read; Autodesk
  viewer certification is the orchestrator's step (files listed below).
* Proof files for the viewer (all under `experiments/mep/electrical/`):
  `wire_create.rvt`, `wire_delete.rvt`, `settings_modify.rvt`,
  `load_class_create.rvt`, `panel_renumber.rvt` (32 MB each, from
  `samples/rmebasicsampleproject.rvt`). Regenerate: `.venv/bin/python
  experiments/mep/electrical/make_electrical.py` (~6 min, prints per-cell
  verdicts, writes `manifest.json`).
* Tests: `tests/test_mep_electrical_data.py` — 24 fast (read model,
  units, layout rule reproduces Autodesk numbering, planning of every
  create/modify/delete incl. byte-clean re-decode of every serialized new
  record) + 1 end-to-end commit test (`slow`, ~1 min).

## Findings worth propagating (KNOWLEDGE candidates)

1. **Wire model** (all §1 of the doc): view-owned; `m_setidCircuits`
   one-way; conn0/conn1 sibling refs + device refs, device back-link on its
   conn 1, connType 1; home run = free start end; `m_bDynamicUpdateEnds` =
   connection state; wire type material/insulation/temperature are Revit-2026
   `CustomElement` conductor definitions (`NamingCell` name), not the legacy
   `RbsWire*Type` elements (those key the `RbsWireSizesElem` ampacity table).
2. **Electrical internal units**: volts AND VA both = SI ÷ 0.3048²
   (240 V → 2583.3385; the NEC 220.44 10 kVA threshold → 107,639.10).
3. **Load classification closure**: classification + its own
   `ElectricalDemandFactorDefinition` + six `ParamElemElectrical
   LoadClassification`, mutual deletion parents; `m_typeId` =
   `revit.local.classification:` + creation-session GUID + 8-hex element
   id + `-1.0.0` (749580 = 0xB700C).
4. **Panel/circuit schedule**: panel binds to its distribution system via
   ElementId param −1140064; circuits' `m_number` string / `m_nStartSlot`
   / `m_nPoles` + the two-column same-parity packing rule (reproduces
   Autodesk exactly); panel slots = 50000-series connectors, one per
   circuit, never shared; `m_circuitConnType` 1 = assigned.

## Gotchas / notes for the orchestrator

* **CROSS-STREAM CONFLICT (not in my territory to fix):**
  `identity.own_basic_file_info` (gate G2, added 2026-08-03 12:34) rewrites
  BasicFileInfo's Unique Document GUID but does NOT prepend the matching
  `Global/History` episode, breaking the verified invariant
  `BFI GUID == History[0] GUID` — so every fresh `commit.commit_new_elements`
  output now FAILS `rvt_validate` L2 ("Unique Document GUID != History
  entry[0] GUID"). The hosting H-files pass only because they predate the
  identity module. `commit_electrical` ships the scrub OPT-IN
  (`own_identity=False` default) so these proofs validate clean. Fix options
  (owner: identity/commit stream): (a) `own_basic_file_info` keeps
  `unique_document_guid`/`central_episode_guid` = History entry[0] and only
  scrubs path/user/central-model identity; or (b) create commits also
  prepend the History episode (`streams_edit.record_save`) so the new GUID
  is legitimate. Until then, VALIDATE ANY create-path proof from other
  streams before certifying — they may fail L2 on this alone.
* Generic hook wished for (exact composition = `commit_electrical`, ~60
  lines): `manipulate.commit_plans(..., new_elements=[...])` (insert new
  framed records before the sentinel + `elemtable_add_element`), so create +
  edit no longer needs a stream-local commit.
* Plugin bundle: adding `src/rvt/mep/` makes `tests/test_plugin_sync.py`
  drift-red until `tools/sync_plugin.py` runs; I ran it (sanctioned mirror,
  as prior streams did) — it may sweep in parallel streams' in-flight files
  and can re-flap while they write source. Re-run before shipping.
* Renumbering rewrites `m_number` + `m_nStartSlot` only; the per-load
  cached `RBS_ELEC_CIRCUIT_NUMBER` and panel schedule VIEW cells are
  derived caches Revit recomputes on open (same policy as `rename_panel`).
* `add_wire` REQUIRES a plan view (wires are view-specific): inferred from
  the devices'/circuits' existing wires, else `view_id=` must be passed.
* Not implemented (no corpus specimen): delta / high-leg distribution
  configs; wire types' `m_kConfig` beyond single/wye; circuiting existing
  loads onto a NEW circuit remains phase 2 (mutation-plan §6.5).

## Reproduction

```
.venv/bin/python experiments/mep/electrical/make_electrical.py           # 5 proofs + manifest.json
.venv/bin/python -m pytest tests/test_mep_electrical_data.py -q              # 25 passed
.venv/bin/python tools/rvt_validate.py experiments/mep/electrical/*.rvt      # 5x VALID
.venv/bin/python -m rvt.mep.electrical_data samples/rmebasicsampleproject.rvt settings
.venv/bin/python -m rvt.mep.electrical_data samples/rmebasicsampleproject.rvt panel 622027
```

Full suite (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`,
run 2026-08-03 13:1x): **377 passed, 3 failed** — all three failures are
OTHER streams' in-flight territory, none touched by this stream:
`tests/test_mep_views_spaces.py::test_schedule_view_and_space_write_and_verify`
(views/spaces stream, an ECC mismatch in their commit),
`tests/test_reduce.py::test_ladder_v2_R5_...` (reduce stream, SWall count),
and `tests/test_plugin_sync.py` (fleet-wide plugin drift: 11 lib files
incl. provenance/identity/genesis/conduit/devices/views_spaces and this
stream's `mep/electrical_data.py` + `mep/__init__.py` — I did NOT run
`tools/sync_plugin.py` (outside territory, and it would freeze parallel
streams' in-flight sources into the bundle); run it once the streams
merge). This stream's own file: `tests/test_mep_electrical_data.py` = 25/25
passed (24 fast in ~8 s + 1 end-to-end commit ~60 s).

BRANCH STATE: mep-electrical COMPLETE — working tree only (no git commit;
repo has no commits yet). New: `src/rvt/mep/electrical_data.py` (+
`src/rvt/mep/__init__.py`), `tests/test_mep_electrical_data.py` (25 pass),
`experiments/mep/electrical/{make_electrical.py, manifest.json,
wire_create.rvt, wire_delete.rvt, settings_modify.rvt, load_class_create.rvt,
panel_renumber.rvt}` (all 5 proofs: structural VALID + rvt_validate 0 errors
+ semantic OK), `docs/writer/mep-electrical-data.md`, `docs/inbox/
mep-electrical.md`. Full suite 377 passed / 3 failed (all foreign, above).
DONE met; STOP.

---

# eng146 — native feeder circuits on the genesis base (issue #146, PR #353)

Stream: `cam/146-native-circuits`, one engineer session (cse_01UQR7uoRdCA8QGcSASquJBz),
2026-08-09. Territory: `src/rvt/frontdoor/standalone.py`, `src/rvt/mutate.py`
(add_circuit template injection only), `tools/ifc_intent.py`
(stage_equipment / stage_circuits), `src/rvt/frontdoor/build.py`,
`src/rvt/frontdoor/matrix.py` (`_CIRCUITS` caveat only) + the pinned doc row,
`tests/test_frontdoor.py`, `tests/test_mep_devices.py`, this header,
`experiments/mep/circuits146/` (probe maker + probes.json; .rvt git-ignored).
One out-of-territory line: `tests/test_frontdoor_standalone.py` pinned the
injected-template set to `{wall, instance}`; it now includes `circuit_id`
(direct consequence, 2 lines).

## What was built

1. **`standalone.electrical_system_template(schema, *, elem_id, n_loads=1, path_offset_ft)`**
   — a CONSTRUCTED `RbsElectricalSystem` clone template built from
   `default_object(schema, …)` of the base's OWN schema, exactly like the
   SWall / FamilyInstance templates. `ConstructedSpecimens.circuit_id`
   (= `CIRCUIT_TID` 990000003) is injected next to the wall/instance templates;
   `inject_into()` reports `circuit_specimen`. Nothing is read from any file;
   `tools/provenance.py` attributes the emitted circuits `ours-created`.
2. **Stages E and C in ONE commit** — `tools/ifc_intent.wire_feeders()` runs
   inside `stage_equipment` after the boards are placed and BEFORE
   serialisation: one `Document.add_circuit(panel, load, number=, start_slot=,
   description=, rating=, poles=, voltage_v=, template_id=specimens.circuit_id)`
   per non-service feeder edge whose two ends were placed; the circuits are
   serialised and committed with the instances (both back-links live in the
   instances' connector objects). Numbers / start slots come from
   `rvt.mep.electrical_data.layout_circuits` per panel (the two-column
   same-parity packing law: first 3-pole feeder `1,3,5`, second `2,4,6`).
3. **Stage C = the readback verifier** — `read_back_circuits(path)` re-opens the
   deepest file and checks the WRITTEN truth: `ids_of_class('RbsElectricalSystem')`,
   base connector `{self, LAST}`, `conn[LAST] -> panel slot` answered by
   `panel.conn[slot] -> {circuit, LAST}`, `conn[0] -> load supply` answered by
   `load.conn[1] -> {circuit, 0}`. `stage_circuits` names a blocker only on a
   shortfall (count < planned, or a one-way link); the manifest's stage-C row
   carries `planned / built / links_ok`.
4. **`mutate.add_circuit`** gained `voltage_v=` (SI → internal ÷0.3048²),
   `start_slot=` (`m_nStartSlot`), and — only for a template that carries NO
   path nodes (the constructed one) — the straight panel→load polyline
   (node 0 = the panel, real; node 1 virtual at the load; `m_dLength` = its
   length). The clone path over a real specimen is byte-for-byte unchanged.
5. Manifest: `elements_created` rows of kind `circuit` (`tag "MSB>DP-1"`,
   `panel/panel_id/panel_slot`, `load/load_id/load_conn`, `number`, `start_slot`,
   `poles`, `rating_a`, `voltage`, `edge_kind`); `dependency_table()` row
   rewritten; matrix `_CIRCUITS` caveat + the `prompt → rvt` doc row rewritten
   to the new truth (still PROOF-ONLY, no certification claim).

## The constructed RbsElectricalSystem — every field, and why

Sources allowed by the issue: the decoded circuit object model
(KNOWLEDGE.md "Electrical circuits", `docs/writer/mep-electrical-data.md` §3.2,
`docs/streams/10-objects.md`, `src/rvt/mep/devices.py` docstrings), the
validator's CIRCUITS / connector-graph invariants, public Revit API enums,
the base's own elements, and the schema default everywhere else. No value is
pasted from a sample; the class SHAPES (which classes hang where) are the
mined law.

| field | value | source |
|---|---|---|
| header `m_classDef` | `RbsElectricalSystem` | the class |
| header `m_categroryId` | −2008037 | BuiltInCategory `OST_ElectricalCircuit` (public enum) |
| header `m_abFlags4Bytes` | 4122 (0x101A) | per-CLASS header species word (docs/inbox/identity.md RANK 2, genesis-fixer G1: constant per class, low byte 0x1A, pattern-cell bit 0x800 clear) — the same treatment as the FamilyInstance (2344) / SWall (6441) templates; a format-bookkeeping constant, not content |
| header `m_pBBox` | null | a system has no spatial extent (rep = SerializedDummy); the base's other non-geometric elements carry null |
| header `m_viewRules` | −4225 | `_element_header` (every constructed template) |
| header parents | deletion {panel, load, self}, appearance {panel, load}, rest empty | `mutate.add_circuit`'s certified recipe (V29 on rme), unchanged; devices.py's richer law (regenOnly {load symbol, ElectricalSetting, CircuitNamingTypeSetting}, deferred {MEPSystemTracker}) is NOT applied — see open questions |
| Element param sets / geomSteps / GeomTable | null | schema default; a system is not geometric |
| `m_cellList` (2026) | `CellList{[ElectricalLoadClassificationsData{4 empty maps}]}` | 2026 keeps a circuit's connected-load data in this cell (class named by the 2026 schema); EMPTY = no load data claimed |
| `m_cellList` (2025/2024) | null | that class version carries the load maps on the element (`m_loadsPerClass` etc., left empty) and the schema names no such cell class → schema default, like the base's other cell-less elements |
| `m_docAccess` | weakref 1 | archive law: pid 1 = the document |
| level / famId / owner view / phases / design option | −1 | a system is not levelled or phased; schema default for ElementId |
| `m_baseConnectorIdArray` | `[{self, LAST, connType 4}]` | validator CIRCUITS invariant; KNOWLEDGE.md model |
| `m_pConnectorMgr` | `RbsSystemConnectorManager` pid 3 | the system-side manager class the schema names (docs/streams/10-objects.md decode); pid 3 = first weakly-referenced object after doc(1)/root(2) (`famgen.geometry.assign_pids` law) |
| its `m_connPtrArray` | `n_loads+1` × `Connector` pids 4.., `m_nIndex` 0..n, `m_arrRefs []`, `m_pElement` weakref 2, `m_mode` 4, `m_modifiers [RbsSystemConnectorModifier{m_pConnector: weakref own pid}]` | class shape per the decode notes; `m_mode` 4 = a logical SYSTEM connector (an instance's physical connector carries 1 — `famgen.loader._connector_slot`); refs are wired by `add_circuit` |
| its `m_modifiers` | `[MEPConnectionBehaviorModifier{m_pConnectorManager: weakref 3}]` | class shape per the decode notes; weak-points at the manager |
| `m_setDeletedConnectors`, `m_rgSections` | [] | schema default |
| `m_strName` | "" | circuits are unnamed systems |
| `m_typeId` | −1 | an electrical circuit has no MEP system-type element; schema default |
| `m_nextFreeSectionId`, `m_numberOfElements(InNetwork)`, `m_systemState` | 0 | **not derivable** → schema default (the documented 9-load decode also shows 0/0 element counts) |
| `m_number` / `m_nStartSlot` | per feeder: `layout_circuits` | mep-electrical-data §3.3 law (reproduces Autodesk's numbering) |
| `m_strDescription` | `"<load> feeder from <panel>"` | ours (the intent's circuitPlan) |
| `m_strLoadClassifications`, `m_strNotes` | "" | no connected-load data claimed |
| `m_cableType` / `m_cableSizeElementId` (2026), `m_idWireType` (2025/24) | −1 | the base carries 0 `RbsWireType`; schema default |
| `m_dRating`, `m_nPoles` | feeder edge (400/100 A, 3 P) | intent |
| `m_dVoltage` | LL volts ÷ 0.3048² (480 V → 5166.68) | KNOWLEDGE.md electrical internal units |
| `m_dApparentLoad`, `m_dTrueLoad`, per-phase data, `m_dVoltageDrop`, `m_dFrame` | 0 | no load calculation is claimed (honest zero) |
| `m_pathNodes` | `[panel (real), load (virtual)]`, `m_dLength` = distance | our own two placements; node 0 = the base equipment (devices.py 171/171 law) |
| `m_pathOffset` | the base's own `ElectricalSetting.m_circuitPathOffset` (9.0223 ft = 2750 mm, a genesis-authored setting) | base fact |
| `m_pathOffsetAllDevice`, `m_circuitPathMode`, `m_nNumRuns`, `m_nPhaseInfo`, `m_nGroupNumber`, `m_nNamingIndex` | 0 | **not derivable from our own knowledge** → schema default (see open questions: PathMode / NumRuns are the two most likely to matter to Revit) |
| `m_circuitConnType` | 1 | §3.2: 1 = assigned to a panel (add_circuit always assigns) |
| `m_circuitType` | 0 | §3.2: 0 = circuit |
| `m_systemType` | 6 | Revit API `ElectricalSystemType.PowerCircuit` (docs/writer/family-skeleton.md) |
| `m_bReserved`, `m_bSlotLocked` | False | schema default |
| seq-103 rep | SerializedDummy | circuits carry no geometry (baked-geometry.md: 187/187 dummy) |

## Evidence (numbers)

DONE prompt: `frontdoor author --prompt "electrical room 30x20 ft with a 2000A
main switchboard, two 400A distribution panels and four lighting panels"`.

| target | exit | stage C | circuits in manifest | `rvt_validate` | `stats.circuits` / `connector_edges` | `ids_of_class('RbsElectricalSystem')` (own release) | readback links |
|---|---|---|---|---|---|---|---|
| 2026 | 0 | ok, planned 6 / built 6 / links_ok | 6 (`MSB>DP-1` 50000↔1 `1,3,5`; `MSB>DP-2` 50001↔1 `2,4,6`; `DP-1>LP-1` 50000 `1,3,5`; `DP-2>LP-2` 50000 `1,3,5`; `DP-1>LP-3` 50001 `2,4,6`; `DP-2>LP-4` 50001 `2,4,6`) | VALID 0 errors / 1 warning (the known DataStorage decoder gap) — default AND `--strict` | 6 / 24 | 6 | all True both sides |
| 2025 | 0 | ok, 6/6, links_ok | same 6 | VALID 0 errors | 6 | 6 | all True |
| 2024 | 0 | ok, 6/6, links_ok | same 6 | VALID 0 errors | 6 | 6 | all True |

Baseline before the change (same prompt, `main` 3583f7e): stage C blocker
"NO CIRCUIT SPECIMEN … an RbsElectricalSystem CONSTRUCTOR is the exact
missing piece", 6 planned / 0 built, degradation in the manifest.
No stage-C degradation after. Job wall time unchanged (4.8–5.4 s).

Provenance (`tools/provenance.py out.rvt --baseline plugin/assets/genesis/G_ABPD.rvt --streams`):
placed-model-content `RbsElectricalSystem: ours-created 6`, `FamilyInstance:
ours-created 7`; totals vs the pinned base `ours-created 127 / ours-modified 1
/ transitive-cloned 18 / identical-to-base 3101`; the emitted circuits carry no
positive id but panel/load/self and no string but our description. With
`--baseline all` (no samples corpus in a cloud clone) the G1 line is the
base's standing "unattributable, 9,178 Autodesk resource identifiers" in BOTH
the before and after runs (3241 → 3247 elements = exactly +6 circuits);
identity ok (author `rvt-writer`, username empty). The G1/G2 gate itself is
#19/#23 territory and unchanged by this stream.

Bare surface: `tekton-plugin.zip` unzipped to a temp dir, system `python3
skills/tekton-author/scripts/_bootstrap.py go author --prompt <DONE prompt>` →
`tekton: READY …`, exit 0, 6 circuits, VALID 0 errors, 5.3 s.

Degrade path (rule 1): with the template absent (`stage_equipment(circuits=False)`
/ a SpecimenSet without `circuit_id`) the job still delivers; stage C reads back
0/6 and the manifest degradation names `NO_CIRCUIT_SPECIMEN`.

## STAGE-ready note (NOT staged — no certification claim)

`experiments/mep/circuits146/make_probes.py` builds the single-variable pair
and writes `experiments/mep/circuits146/probes.json` (files git-ignored):
control `CTRL_G_ABPD_circuits146.rvt` (md5 1f1ff65b… = the pinned base),
`C146_off.rvt` (7 instances, 0 circuits, VALID 0) and `C146_on.rvt` (7 instances,
6 circuits, VALID 0). Both probes carry placed instances of our generated
families = the OPEN CELL (#16), so `on` reads only RELATIVE to `off` (same card
⇒ the circuit layer adds no new defect; a different/earlier failure ⇒ the
circuit records are a second defect → bisect the field table above; both PASS ⇒
certified with the instances). To run it: reserve `/batches 1`, then
`tools/probe_batch.py stage --manifest experiments/mep/circuits146/probes.json --batch <N>`.

## Findings

* The 2025/2024 `RbsElectricalSystem` is a different class VERSION from 2026:
  2026 moved per-class load maps + per-phase doubles into an
  `ElectricalLoadClassificationsData` cell and `m_apparentPerPhaseData`, and
  renamed `m_idWireType` → `m_cableType`(+`m_cableSizeElementId`); 2025/2024
  carry `m_loadsPerClass / m_reactiveLoadsPerClass / m_trueLoadsPerClass`,
  `m_dApparentLoadPhaseA..C`, wire-size strings and `m_nNumHots/Neutrals/Grounds`
  on the element. Building the template from `default_object` of the schema it
  is GIVEN makes it release-native with no port hook (first attempt hard-coded
  the 2026 cell class and crashed on 2025 — fixed by asking the schema).
* `Connector`, `RbsSystemConnectorManager/Modifier`, `MEPConnectionBehaviorModifier`,
  `CircuitPathNode`, `ConnectorId` are field-identical across 2024–2026.
* `ids_of_class(host_only=True)` filters by ElemTable, so an injected template
  is invisible to `_template_circuit()`; the stage passes `template_id=`
  explicitly (and the readback count is therefore exactly the committed set).
* Pre-existing, not touched (loader territory): placed instances' `Connector`
  objects are written with pid −1 while their three modifiers weak-point at
  pid 4 (`famgen.loader._connector_slot`); the archive law would number each
  connector and point its modifiers at it (as this stream's circuit connectors
  do). Certified add_to_project files carry the same shape, so it is tolerated;
  worth a hygiene issue if an instance-axis bisection ever needs it.

## Open questions (for the viewer round, not blockers here)

1. `m_circuitPathMode` / `m_nNumRuns` / `m_nPhaseInfo` / `m_nextFreeSectionId`
   ship at schema default 0 because their law is not ours to state; if desktop
   Revit objects to the circuit layer specifically, these four and the header
   parents (regenOnly ElectricalSetting + CircuitNamingTypeSetting, deferred
   MEPSystemTracker per devices.py's corpus-corrected law) are the first
   single-variable candidates — one at a time, with `C146_off` as the control.
2. KNOWLEDGE.md still says `pathNodes[0].m_elemId = first load`; devices.py's
   later 171/171 census says the PANEL. The constructed path follows devices.py;
   the clone path in `mutate.add_circuit` (rme specimens) is unchanged. A
   KNOWLEDGE.md reconciliation belongs to the orchestrator fold (hot file).

3. Two `/simplify` findings deliberately NOT applied: (a) routing the stage
   through `rvt.mep.devices.add_multi_load_circuit(loads=[load])` instead of
   `mutate.add_circuit` — it is equally clone-only and carries a DIFFERENT
   header-parent recipe (regenOnly/deferred singletons, `hasNonDetermRegenChildren`
   True) than the V29-certified `add_circuit`; unifying the two is a behaviour
   decision for the viewer round, not a cleanup. (b) `release_ctx` port-wraps
   `family_instance_template` / `swall_template` by name; the circuit template
   needs no wrap (built from the release's own schema) but a
   `SA.CONSTRUCTED_TEMPLATES` registry iterated by `release_ctx` would make a
   fourth template impossible to forget — `release_ctx.py` is outside this
   territory; suggested patch: replace the two `swap(SA, ...)` lines with a loop
   over such a registry.

## Gates run

* `tests/test_frontdoor.py tests/test_mep_devices.py tests/test_mep_electrical_data.py
  tests/test_frontdoor_standalone.py tests/test_router.py -q -rs` → see BRANCH STATE.
* `tools/sync_plugin.py` → synced, deny-audit clean, identity scan == allowlist;
  `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok.
* New tests: `test_frontdoor.py` — `test_e2e_feeder_circuits_are_authored_per_release[2026/2025/2024]`,
  `test_e2e_circuits_read_back_with_both_side_links[2026/2025/2024]`,
  `test_circuit_specimen_is_constructed_not_cloned`; `test_mep_devices.py` — four
  sample-free `add_circuit` tests over the constructed template on the bundled
  base (wiring both sides, slot allocation, template immutability, a committed
  one-circuit file strict-VALID + readback). No new test FILE → no ci_shard.d drop-in.

BRANCH STATE (eng146): `cam/146-native-circuits`, PR #353 (ready), rebased on
`origin/main` fba7efb. Files written: `src/rvt/frontdoor/standalone.py`
(`electrical_system_template`, `_circuit_path_offset`, `ConstructedSpecimens.circuit_id`,
dependency row), `src/rvt/mutate.py` (`add_circuit` template injection: path-less
template, `voltage_v`, `start_slot`; `ELEC_INTERNAL_PER_SI`), `src/rvt/mep/devices.py`
(re-exports the constant), `tools/ifc_intent.py` (`wire_feeders`, circuit wiring in
`stage_equipment`, `read_back_circuits`, readback `stage_circuits`, `SpecimenSet.circuit_id`),
`src/rvt/frontdoor/build.py` (stage-C handling, circuit harvest, `circuits="C" in stages`),
`src/rvt/frontdoor/matrix.py` (`_CIRCUITS` text only) + `docs/product/PERMUTATION-MATRIX.md`
row, `tests/test_frontdoor.py` (+7), `tests/test_mep_devices.py` (+4),
`tests/test_frontdoor_standalone.py` (2 lines), `experiments/mep/circuits146/{make_probes.py,
probes.json,.gitignore}`, regenerated `plugin/lib/**` + `plugin/skills/tekton-author/scripts/ifc_intent.py`,
this header. Gates on 180e1cd: 240 passed / 55 skipped / 1 failed (`test_router.py::
test_e2e_prompt_rfa_modify` — reproduces on `origin/main` fba7efb, filed #354, Refs #336);
sync `--check` clean, validate_plugin PASS, portable paths ok, bare-unzip `go author` READY.
Shipped: everything above. Staged for the viewer: NOTHING (probe pair prepared, not staged,
no ledger claim). DONE of #146 met at validator + readback depth on 2026/2025/2024; STOP
after the tech-lead session's CI + review + merge.

---

# eng360 — native-circuit follow-ups from #353's review (issue #360), 2026-08-10

Stream: `cam/360-native-circuits-followups`, one engineer session (eng360). Additions
only; eng146's text above is untouched. Territory: `tools/ifc_intent.py` (stage-C
message + the no-circuit feeder record), `src/rvt/frontdoor/build.py` (4 lines: hand
stage E's record to stage C, name "C not requested" — the one place the front door
calls `stage_circuits`, so unavoidable for the manifest to carry the cause),
`tests/test_mep_devices.py` (+2), `tests/ci_shard.d/146-native-circuits.txt` (new),
`experiments/mep/circuits146/` notes, regenerated mirrors, this header.

## What changed

1. **Stage C names the real cause of a shortfall.** `stage_circuits(model, path,
   equipment=None)` now receives stage E's record and `_circuit_shortfall()` reads
   the cause off it instead of always printing `NO_CIRCUIT_SPECIMEN`:
   * E did not run → `"… stage E (equipment placement) did not run -> no board instance exists to wire"`;
   * E skipped / did not commit → `"… stage E did not commit its instances (+ circuits): <E's reason/blocker/error> …"`;
   * E's own `circuits_blocker` → verbatim (`NO_CIRCUIT_SPECIMEN`, or the new
     `STAGE_C_NOT_REQUESTED`);
   * edges E skipped for an unplaced end → `"… N feeder edge(s) skipped in stage E for an UNPLACED end -- MSB>DP-1: panel not placed (…); …"`.
   `stage_equipment(circuits=False)` with feeder edges in the intent records
   `circuits_blocker = STAGE_C_NOT_REQUESTED` + every edge in `circuits_skipped`
   (reason `"stage C not requested"`), and `build.py` adds the degradation
   `"feeder CIRCUITS not wired: stage C (circuits) NOT requested (--stages lacks 'C') …"`
   — the manifest is no longer silent when `--stages` lacks C.
2. **`_NO_FEEDERS` → `_feeders_unwired(edges=(), blocker=None, reason=None)`**: a new
   dict + new lists per call (stage E `update`s it into its record and appends to the
   lists; the module-level dict was handed out by reference). `circuit_edges(model)` is
   the single definition of "feeder edges that become circuits" (service entrance
   excluded), used by `wire_feeders`, `stage_equipment`, `stage_circuits`, `build.py`.
3. Record / STAGE-note correction (below) — **no shipped value changed**.
4. `tests/test_mep_devices.py` sharded whole (measurement below).

## Correction to eng146's open question 1 — the four "not derivable" path fields are corpus-constant

eng146's field table calls `m_circuitPathMode / m_nNumRuns / m_nextFreeSectionId /
m_pathOffsetAllDevice` "not derivable" and ships them at schema default. The
checked-in census `experiments/genesis/lint/invariants/RbsElectricalSystem.json`
(188 specimens: 187 rme + 1 rac) says otherwise — they are **constant across the
whole corpus**:

| field | shipped today (read back from the DONE prompt's `prompt_room.rvt`, 2026) | census value | support |
|---|---|---|---|
| `m_circuitPathMode` | 0 | **2** | 188/188 |
| `m_nNumRuns` | 0 | **1** | 188/188 |
| `m_nextFreeSectionId` | 0 | **1** | 188/188 |
| `m_pathOffsetAllDevice` | 0.0 | **30000.0** | 188/188 |
| (`m_pathOffset`) | 9.0223 (from the base's `ElectricalSetting`) | 9.0223097 | 188/188 — already agrees |
| (`m_nPhaseInfo`) | 0 | 0:1 / 1:124 / 2:33 / 3:30 | NOT constant — stays out of the first round |
| (`m_systemState`, `m_nGroupNumber`, `m_nNamingIndex`, `m_numberOfElements(InNetwork)`) | 0 | 0 | 188/188 — already agree |

So the first circuits viewer round has an obvious **candidate single variable**: the
four corpus constants `{PathMode 2, NumRuns 1, nextFreeSectionId 1,
pathOffsetAllDevice 30000.0}` applied together as ONE variable against `C146_on` as
shipped (with `C146_off` + the byte-identical control, per eng146's read order), and
bisected only if that flips the card. A corpus constant is a *law we mined*, not donor
content (rule 3: values authored by us from a census, like the 0x0f3f footer law).
**Deliberately not changed here**: the shipped template keeps the schema defaults until
a viewer verdict says otherwise (rule 4 — validator + readback are green either way and
cannot arbitrate); nothing staged, no batch reserved, no ledger claim. The STAGE notes
(`experiments/mep/circuits146/make_probes.py` docstring + the `next_single_variable`
key it writes into `probes.json`) now carry the same candidate so whoever reserves the
batch starts from the census, not from a guess.

## Evidence

* DONE prompt through the front door on this branch (2026): exit 0, stage C
  `ok / planned 6 / built 6 / links_ok`, 6 `circuit` rows, `VALID` 0 errors, no circuit
  degradation, 5.0 s — unchanged from #353.
* Same prompt with `--stages FLWEV`: exit 0, `VALID` 0 errors, 0 circuits, stage E record
  `circuits_blocker = "stage C (circuits) NOT requested (--stages lacks 'C'): …"`, 6 skipped,
  degradation `"feeder CIRCUITS not wired: stage C (circuits) NOT requested …"` (was: silent).
* Unplaced-ends case (test, bundled base, template present, nothing placed): stage C blocker
  `"0 of 6 feeder circuits in the deepest file: 6 feeder edge(s) skipped in stage E for an
  UNPLACED end -- MSB>DP-1: panel not placed (family not loaded / not in the intent); …"` and
  NOT `NO CIRCUIT SPECIMEN` (was: always `NO CIRCUIT SPECIMEN`).
* Shard decision (item 4): `RVT_SKIP_LARGE=1`, no `samples/`: the WHOLE
  `tests/test_mep_devices.py` = **6 passed / 18 skipped / 0 failed in 2.0 s** (the 18 rme
  cases self-skip; the 6 sample-free cases run on the bundled base) → sharded whole via
  `tests/ci_shard.d/146-native-circuits.txt`; no split file needed. Shard 57 → 58 files.

## Gates run

See BRANCH STATE.
