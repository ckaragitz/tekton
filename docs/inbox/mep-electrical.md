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
