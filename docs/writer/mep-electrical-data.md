# MEP electrical data — wiring, electrical settings, panel data (CRUD)

Stream: `mep-electrical` (wave: MEP writer). Module:
`src/rvt/mep/electrical_data.py`. Tests: `tests/test_mep_electrical_data.py`
(24 fast + 1 end-to-end). Proof harness:
`experiments/mep/electrical/make_electrical.py` → five `.rvt` proof files +
`experiments/mep/electrical/manifest.json`. Companions: `docs/writer/
mutation-plan.md` (create), `docs/writer/manipulation.md` (edit / delete).
Confidence tags: **[V]** verified on the corpus / by structural proof,
**[H]** hypothesis (needs Revit acceptance), **[D]** design decision.

## 0 · TL;DR

Three electrical data categories an MEP contractor edits daily are now
full CRUD on top of the proven writer core, all against the Revit MEP
sample (`rmebasicsampleproject.rvt`, Revit 2026):

| category | class(es) | read | create | modify | delete |
|---|---|---|---|---|---|
| **wires** (home runs / branch wiring on plans) | `RbsWireCurve` (class 0x0ddb, OST_Wire −2008039), owned by a plan view | `wires()`, `wire_info()`, `wires_of_circuit()` | `add_wire()` / `add_home_run()` **+ device connector back-links in the same commit** | (endpoints move with their devices) | `delete_wire()` (tag cascade, back-links neutralised) |
| **electrical settings** | `RbsVoltageType`, `RbsDistributionSysType`, `RbsWireType` (+ Revit-2026 `CustomElement` conductor material/insulation/temperature/size), `ElectricalDemandFactorDefinition`, `ElectricalLoadClassification` (+ 6 `ParamElemElectricalLoadClassification`), `ElectricalSetting`, `RbsWireSettingsElem`, `RbsWireSizesElem` | `electrical_settings()` | `add_voltage_type / add_distribution_system / add_demand_factor / add_load_classification` | `set_demand_factor / set_voltage_type / rename_setting / set_load_classification / modify_setting` | (deletable via `manipulate.delete_element`) |
| **panel data** | panelboard `FamilyInstance` params + its `RbsElectricalSystem` circuits' `m_number` / `m_nStartSlot` | `panels()`, `panel_info()`, `panel_circuits()`, `check_panel_numbering()` | — | `renumber_circuits()` (Revit's own two-column rule), `rename_panel()` | — |

A **combined commit** (`commit_electrical`) lands new elements AND in-place
record edits in ONE re-emit of save-unit 0 — required by wiring, where a
new wire and its devices' connector back-links are inseparable. Every
proof file passes the writer's structural verifier and
`tools/rvt_validate.py` (structure + consistency + semantic) with **zero
errors** (§9).

## 1 · WIRES — the on-disk model of `RbsWireCurve`

Ground truth: 1,045 wires in the rme host document, e.g. wire 469465
(a home run in plan view 455447 carrying circuits 469428/469434/469513).

### 1.1 The three records

| seq | class | content |
|---|---|---|
| 101 | `ElementHeader` (0x05e5) | `m_categroryId = −2008039` (OST_Wire); **`m_ownerViewId = the plan view`** (wires are VIEW-SPECIFIC annotation-like elements); `m_pBBox = null`; parents §1.4 |
| 102 | `RbsWireCurve` (0x0ddb) | the object (§1.2), ~1,075 bytes |
| 103 | `GElement` (136 B) | a small view-graphics rep: `m_GInfo{m_categoryId 55172 (the wire graphics style), m_tag = elem id, m_flags 561156}`, `m_subNodes []`, EMPTY boxes (`±1e30`), `m_elementId = id`, `m_gElemType 3` — constant across all 1,045 wires; clone + patch the two ids |

### 1.2 The `RbsWireCurve` object [V, all 1,045 decode clean and re-encode byte-exact]

Chain `Element → CurveElem(-ish) → RbsWireCurve`. The fields that carry the
wiring semantics:

| field | meaning | value / rule |
|---|---|---|
| `m_ownerDBViewId` | the plan view owning the wire (7 views own the sample's wires) | **must** be a plan view; header `m_ownerViewId` mirrors it |
| `m_assocLevelId` | level | the view's level |
| `m_idType` | the `RbsWireType` (all 1,045 = 261496 'XHHW') | |
| `m_pDesignPropManager -> ElectricalDomainDesignPropertyManager` | **`m_setidCircuits: [circuit ids]`** — the circuits this wire carries (a home run can carry several: 550×1, 213×2, 251×3, 31 unassigned); `m_nHotAdjustment / m_nNeutralAdjustment / m_nGroundAdjustment` = tick-mark ± ; `m_idDownstreamCircuit −1` | **ONE-WAY link: circuits never reference their wires** [V: circuit 469428 does not mention wire 469465 anywhere] |
| `m_rgPoints` | the drawn path: `[start, mid, end]` (1,041/1,045 have 3 points; 4 have 2) | start = conn 0 end, end = conn 1 end |
| `m_pCurveDriver -> RbsCurveDriver -> GLine` | the CHORD: `m_origin = start`, `m_dirVec = unit(end − start)` (3D), `m_endParams = [0, |end − start|]` (feet) [V: 469465 chord 3.9149 = distance of its endpoints] | recomputed for a new wire |
| `m_eType` | Revit `WiringType`: **0 = arc [V, every corpus wire]**, 1 = chamfer **[H — the API enum; no chamfer specimen in the sample]**; `m_bDrawCircularArc` true for arcs | `add_wire(wiring_type='arc'|'chamfer')` |
| `m_bDynamicUpdateEnds [b0, b1]` | **b_i = true iff end i is connected to a device** (400/400 sampled wires) | derived from the connections |
| `m_bStartOffsetInitialized / m_bEndOffsetInitialized`, `m_start/endOffsetVectorXYZ` | tiny end offsets from the device connector; the home run's FREE start end has offset uninitialised | new wires: zero offsets, initialised = connected |
| `m_vNormal` | `[0,0,1]` | |
| `m_iEndReference` | 0 on all 1,045 | |
| params | `ParamValueSetInt {−1140107: 4}` (constant on every wire) [H: conductor count]; `ParamValueSetAString {−1001203 (Mark): "1".."N"}` — marks are unique small integers | new wire Mark = max existing + 1 |

### 1.3 Connectivity — the connector closure [V]

`m_pConnectorManager -> RbsCurveConnectorManager` with **exactly two
`Connector`s** (`m_nIndex 0` = the start end at `paramOnCurve 0.0`,
`m_nIndex 1` = the end end at `paramOnCurve 1.0`), each carrying
`SegmentConnectorPosition / SegmentConnectorDataModifier /
SegmentConnectorCalculation` modifiers. Reference pattern (from 469466, a
branch wire between receptacles 467291 and 467473):

```
wire.conn[0].m_arrRefs = [ {wire, 1, connType 1},      # its own sibling end
                           {467291, 1, connType 1} ]    # the device at the start
wire.conn[1].m_arrRefs = [ {wire, 0, connType 1},
                           {467473, 1, connType 1} ]    # the device at the end
device 467473 .conn[1].m_arrRefs ⊇ [ {wire, 1, connType 1} ]   # BACK-LINK
```

* The two ends of one wire reference **each other** (`connType 1`) — the
  same "curve internal" linkage MEP duct/pipe curves use.
* Wire ↔ device is **two-sided** (`connType 1` both ways): creating a wire
  therefore requires **editing the connected devices' records** so their
  connector `m_arrRefs` gain `{wire, wire_conn, 1}` — hence
  `commit_electrical` (§7). A one-sided link is exactly the "cloned
  template connector" defect `rvt_validate` warns on (strict-mode error).
* Wire connectors target **only devices** — lighting fixtures (−2001120),
  electrical fixtures (−2001060), switch devices (−2008087) — and always the
  device's **connector index 1** (2,003/2,003 corpus edges). **A wire never
  connects to a panel:** external-target pattern (start, end) over 1,045
  wires = (1,1) 974 branch, (0,1) 37 **home runs (start end FREE)**, (1,0)
  18, (0,0) 16 unconnected. A HOME RUN is simply a wire whose start end
  references no device; Revit draws the arrowhead there and points it at
  the circuit's panel by regeneration (the arrow style is
  `RbsWireSettingsElem.m_idWireHomeRunArrowLeaderStyle` = LeaderStyle
  583374). Home-run wires' free ends sit ~4–10 ft from the device toward the
  panel, at z 0 [V: 469465 free end 9.97 ft from PP-1B vs its device end
  6.42 ft].

### 1.4 `ElementParents` of a wire (specimen 469465) and the new-wire lists

| list | specimen contents | new wire |
|---|---|---|
| `m_deletion` | wire type 261496, level 378117, view 455447, device 467473, circuits 469428/469434/469513, self | `{wire_type, level, view, devices…, circuits…, self}` |
| `m_regenOnly` | 55172 (wire `GStyleElem`), 293123 (`RbsWireSettingsElem`), the OTHER wires 469466/469467 meeting at the same device, panel 581483 (the first circuit's panel), 583374 (home-run arrow `LeaderStyle`) | the same styles/settings + the circuits' panels + the wires already on the shared device connectors |
| `m_appearanceParents` | 55172, wire type, level, device | 55172 + wire type + level + end device |
| `m_deferredParents` | 712554 (`MEPSystemTracker`) | the file's `MEPSystemTracker` |

Delete (`delete_wire`) = `manipulate.delete_element(cascade=True)`: the only
hard dependent is the wire's tag (`IndependentTag`, an annotation deletion
child); the devices (connector back-links) and the neighbouring wire
(its `m_regenOnly` mention) are soft referrers, neutralised [V: 469465 → 1
dependent tag 471062, referrer 467473; 469466 → referrers 467291, 467473,
469465].

## 2 · ELECTRICAL SETTINGS — decoded and editable [V, all classes decode clean and re-encode byte-exact]

All settings elements are geometry-free `Element`s (seq-103 rep =
`SerializedDummy`), category-tagged, with `m_parents.m_deletion` listing
themselves plus what they reference. Names live in `m_symbolInfo.m_name`
for the *Type classes and in `m_name` for the definitions.

### 2.1 Voltage definitions — `RbsVoltageType` (cat −2008040)

| id | name | actual | min | max |
|---:|---|---:|---:|---:|
| 55359 | 120 | 120 | 110 | 130 |
| 142450 | 208 | 208 | 200 | 220 |
| 277806 | 240 | 240 | 220 | 250 |
| 277807 | 277 | 277 | 260 | 280 |
| 277808 | 480 | 480 | 460 | 490 |

Fields `m_dActualVoltage / m_dMinVoltage / m_dMaxVoltage` in **internal
units = V ÷ 0.3048² ** (240 V → 2583.3385; 277 → 2981.60) — the same
feet-based factor as apparent power below. `add_voltage_type(doc, "347",
347, 330, 360)`; `set_voltage_type(doc, id, volts=…, min_volts=…,
max_volts=…)`.

### 2.2 Distribution systems — `RbsDistributionSysType` (cat −2008041)

| id | name | `m_idVll` → V | `m_idVlg` → V | `m_kPhase` | `m_kConfig` | `m_iNumWires` |
|---:|---|---|---|---|---|---:|
| 277809 | 120/240 Single | 240 | 120 | 0 (single) | 0 | 3 |
| 277810 | 480/277 Wye | 480 | 277 | 1 (three) | 1 (wye) | 4 |
| 55360 | 120/208 Wye | 208 | 120 | 1 | 1 | 4 |

`m_highLegPhase −1` everywhere; header `m_deletion = {Vlg, Vll, self}`
(deleting a voltage deletes the systems using it). A panel binds to its
system via the ElementId parameter `−1140064` (§3). `add_distribution_
system(doc, name, vll=…, vlg=…, phase='single'|'three',
config='single'|'wye', num_wires=n)` accepts existing ids or
same-run NewElements. **[H]** a delta / high-leg system needs an
`m_kConfig` value and an `m_highLegPhase` the corpus never shows.

### 2.3 Wire types — `RbsWireType` (cat −2008039) and the conductor domains

Two types (261496 'XHHW', 55171 'THWN'): `m_strConduitType`
("Non-Magnetic"), `m_dNeutralMultiplier`, `m_eNeutralMode`,
`m_bNeutralIncludedInBalancedLoad`, `m_bShareNeutral / m_bShareGround`,
and four ids — `m_idMaterial / m_idTempratureRating / m_idInsulation /
m_idMaxConductorSize` — that in Revit **2026 point at `CustomElement`s**
(887961.. — a `CellList` holding an `RbsConductorMaterial` /
`RbsConductorTemperatureRating` / `RbsConductorInsulationMaterial` /
`RbsConductorSize` cell plus a **`NamingCell{m_name}`** = "Copper" / "60"
/ "XHHW" / "2000"). The legacy `RbsWireMaterialType` (Copper/Aluminium/
Steel/…) and `RbsWireInsulationType` elements still exist as the keys of
the ampacity table `RbsWireSizesElem.m_mapMaterials` (material →
temperature rating → `m_arrWireSizes[{m_strSize '12', m_dAmpacity 20 A,
m_dDiameter, m_bInUse}]`). `wire_types()` resolves all names; edits go
through `modify_setting()` (e.g. `m_bShareGround`).

### 2.4 Demand factors — `ElectricalDemandFactorDefinition` (cat −2008142)

`m_name`, `m_ruleType`, `m_values[] = {m_factor, m_minRange, m_maxRange}`
(apparent-power bounds in internal VA units; `1e30` = unbounded),
`m_additionalLoad`, `m_includeAdditionalLoad`. The three rule types the
sample uses [V]:

| rule | meaning | specimen |
|---|---|---|
| 0 | constant factor | 'HVAC' 1.0, 'Lighting' 1.25, 'Water Heater' 1.25 |
| 3 | per-object ranking table (motors: 125 % of the largest, 100 % of the rest — NEC 430.24) | 'Motor' `[(1.25, 0..1), (1.0, 1..∞)]` |
| 4 | connected-load range table | 'Receptacles' `[(1.0, 0..10 kVA), (0.5, 10 kVA..∞)]` — exactly **NEC 220.44** (10,000 VA / 0.3048² = 107,639.1 internal) |

`add_demand_factor(doc, name, factor=1.0 or [(f, min_va, max_va)…],
rule_type)`; `set_demand_factor(doc, id, factor, row=0, min_va=, max_va=)`.

### 2.5 Load classifications — `ElectricalLoadClassification` (cat −2008143) = a CLOSURE

Each of the 10 classifications OWNS its own demand factor definition and
**six `ParamElemElectricalLoadClassification`** parameter elements
(cat −2008148), cross-referenced both ways [V, 10/10]:

```
ElectricalLoadClassification 690425 'Receptacles'
  m_demandFactorId          -> 690424 (its ElectricalDemandFactorDefinition)
  m_totalLoadParamElemId    -> 690427  'Receptacles Connected Apparent Power'
  m_estLoadParamElemId      -> 690426  'Receptacles Demand Apparent Power'
  m_totalCurrentParamElemId -> 749580  'Receptacles Connected Current'
  m_estCurrentParamElemId   -> 749581  'Receptacles Estimated Demand Current'
  m_demandFactorParamElemId -> 749582  ('… Demand Factor')
  m_actualSpaceLoadParamElemId -> 749583 ('Actual … Load')
  m_signitureType 0|1|2|3, m_spaceLoadClass 0|1|2, m_abbreviation
each ParamElem…: m_idLoadClassification -> 690425 (BACK), m_pParamDef.m_paramElemId = own id,
  m_typeId = 'revit.local.classification:' + <32-hex creation-session GUID> + <8-hex OWN ELEMENT ID> + '-1.0.0'
  (749580 = 0xB700C -> '...000b700c-1.0.0'; params created together share the GUID) [V]
headers: classification.m_deletion = {factor, self, the 6 params};
         param.m_deletion = {classification, self};  factor.m_deletion = {self}
```

`add_load_classification(doc, name, abbreviation, demand_factor=1.0)`
authors the whole closure (1 factor + 1 classification + 6 params = 8 new
elements) with fresh `m_typeId`s (one shared session GUID, per-element
8-hex id suffix) and the mutual parent lists; captions are the donor's
with the name swapped ('EV Charging Connected Current', …).

### 2.6 Singletons

* `ElectricalSetting` 639116: circuit naming (`m_circuitNamePhaseA/B/C`
  = A/B/C, `m_circuitSequenceValue`), `m_spaceLabel/m_spareLabel`
  ('Space'/'Spare'), default `m_circuitRating` 20 A, `m_circuitPathOffset`
  9.02 ft, load-calc flags, permitted `m_specificAngles`.
* `RbsWireSettingsElem` 293123: `m_wireTickMarkStyle`, connector separator
  `m_strElectricalConnectorSeparator` ('-'), `m_dWiringCrossingGap`,
  `m_idWireHomeRunArrowLeaderStyle` (583374), tick-mark/description styles.
* `RbsWireSizesElem` 293190 (the ampacity table above),
  `CircuitNamingTypeSetting` 885628, `MEPSystemTracker` 712554.

## 3 · PANEL DATA — the panel and its circuit slots

### 3.1 The panel's own data (`FamilyInstance`, cat −2001040) [V, PP-1A 622027]

| datum | location | value |
|---|---|---|
| name | AString param **−1140078** `RBS_ELEC_PANEL_NAME` | 'PP-1A' |
| mark | AString param −1001203 | '20' |
| distribution system → voltages | **ElementId param −1140064** → `RbsDistributionSysType` 55360 ('120/208 Wye' → 208 / 120 V) | |
| mains rating | `m_pInstParams` double **−1140082** [H name `MCB rating`] | 100.0 (A) |
| max poles / spaces | `m_pInstParams` int **−1140079** [H name] | 12 / 42 |
| enclosure, mounting | `m_pInstParams` −1140083 'Type 1', −1140081 'Surface' | |
| per-panel numbering option | `m_pDesignPropManager -> ElectricalFamInstDesignPropertyManager.m_eCircuitNumberingOption` | 0 |
| load data | same manager: `m_oLoadClassificationsData` maps classification id → apparent/demand power (internal VA), `m_dDemandLoad / m_dApparentLoad`, per-phase blocks | |
| slots | connectors: `1` = the panel's own supply; **`50000, 50001, …` = the per-circuit SLOT connectors** (PP-2B: 22 slots for 22 circuits, never shared) | |

`panel_info()` resolves all of it; `rename_panel()` = `manipulate.
rename_panel` (BIP −1140078).

### 3.2 A circuit's schedule fields (`RbsElectricalSystem`) [V]

The panel a circuit belongs to = the target of its LAST connector
(`connType 4`, one of the panel's 50000-series slots). Its schedule
placement:

| field | meaning |
|---|---|
| `m_number` | the circuit-number STRING as it prints on the panel schedule: `'1'`…`'42'` for 1-pole; **`'20,22,24'`** for a multi-pole (the same-parity slots it spans, comma-separated); `''` on the 37 unassigned circuits |
| `m_nStartSlot` | the first slot (integer) — equals the first number in `m_number` |
| `m_nPoles` | 1 / 2 / 3 |
| `m_circuitConnType` | 1 assigned to a panel, 0 unassigned |
| `m_circuitType` 0 (circuit), `m_systemType` 6 (power), `m_dRating` (A), `m_strDescription` (load name), `m_strLoadClassifications` ('Receptacles', 'Lighting; Other') |

### 3.3 The numbering rule — `layout_circuits()` [V by reproduction]

Revit lays a panelboard out in **two columns**: odd slots (1,3,5,…) and
even slots (2,4,6,…); an *n*-pole breaker occupies *n* consecutive slots
of ONE column (same parity, step 2). The observed assignment rule:

> in schedule order, place each circuit at the **lowest** start slot *s*
> such that *s*, *s*+2, …, *s*+2(*n*−1) are all free; `m_number` =
> `str(s)` for 1-pole, `"s,s+2,…"` otherwise; `m_nStartSlot` = *s*.

Applied to the sample's untouched panels this reproduces Autodesk's own
numbers **value-for-value**: PP-2B (471596): singles 1..19, the 3-pole
'EP-2' at **20,22,24**, then singles 21, 23; PP-3B (503195): singles 1..18,
'EP-3' at **19,21,23** (test `test_layout_rule_reproduces_autodesk_
numbering`). Empty slots below the top are legitimate SPACES (a schedule
need not be full: PP-3B's slots 20/22 are open next to the 3-pole).

`renumber_circuits(doc, panel[, order])` re-lays a panel out with this
rule and writes each circuit's `m_number` + `m_nStartSlot` in place
(`manipulate.modify_element`, byte-exact re-encode); it returns **no
plans** when the panel already conforms (idempotent — PP-2B / PP-3B) and
otherwise the ModifyPlans that close the holes: PP-1A (622027, 17 circuits,
hole at slot 2) → contiguous 1..17 (16 circuits renumbered); LP-2
(471705, holes at 1/14/19) → 1..17. `check_panel_numbering()` reports
overlaps / mixed-parity multi-poles / number-string mismatches (hard
errors), spaces and `compact` (whether renumber would change anything).
[D] Derived per-load caches (a receptacle's cached
`RBS_ELEC_CIRCUIT_NUMBER`, a panel schedule view's cells) are NOT
rewritten — Revit recomputes them on open, the same caveat as renaming a
panel (`manipulation.md` §4).

## 4 · CREATE recipes

### 4.1 `add_wire(doc, circuits, from_device, to_device=None, *, wiring_type='arc'|'chamfer', view_id=None, ...) -> WirePlan`

1. **View** — a wire is view-specific: `view_id` or infer the plan view
   owning the wires already attached to those devices / carrying those
   circuits (`_infer_wire_view`); no candidate ⇒ refuse (a view is
   mandatory).
2. **Donor** — clone a real 3-point wire, preferring one from the same view.
3. **Endpoints** — branch: A = `from_device`'s supply connector position,
   B = `to_device`'s (connector index = 1, positions taken from the other
   wires already on that connector, else the instance origin); home run
   (`to_device=None`): A = a FREE point 4 ft from the device toward the
   circuit's panel at z 0 (or `free_point_ft`), B = the device. Mid point
   = chord midpoint bulged 12 % (arc) or straight (chamfer).
4. **Object** — identity reset; `m_ownerDBViewId`; `m_setidCircuits =
   sorted(circuits)`; `m_rgPoints [A, mid, B]`; GLine chord (§1.2); end
   flags (`m_bDynamicUpdateEnds = [A connected, True]`, offsets 0);
   `m_eType` 0/1 (+ `m_bDrawCircularArc`); the two connectors' `m_arrRefs`
   rebuilt per §1.3 (sibling + device refs, `paramOnCurve` 0/1,
   calculation modifiers zeroed); Mark = max wire mark + 1.
5. **Header** — `m_ownerViewId`; parents per §1.4.
6. **Rep** — clone the donor GElement, patch `m_tag` / `m_elementId`.
7. **Device back-links** — for each connected device a `ModifyPlan`
   (`_link_device_to_wire`) appending `{wire, wire_conn, 1}` to the
   device's connector `m_arrRefs` in the shared edit session (several wires
   to one device accumulate in one working copy). Returned as
   `WirePlan(wire, device_plans, home_run, view_id, circuits)`.

`add_home_run(doc, circuit, device=None)` = the circuit's first member
load + `to_device=None`.

### 4.2 Settings creation

Every settings creator clones a real specimen of its class (so the ~30
Element base fields and the class defaults are correct by construction),
resets identity (`m_id`, `m_famId/…`, flags), patches the semantic fields
and rebuilds the header parents (`m_deletion = {self, referenced ids}`,
other lists empty). Reps are `SerializedDummy` (donors carry none).

## 5 · MODIFY / DELETE (thin, on `rvt.manipulate`)

All modifies are `manipulate.modify_element` JSON-path edits (byte-exact
re-encode + fresh adler32 stamp, block re-emitted): `set_demand_factor`
(`m_values[row].m_factor/…`), `set_voltage_type` (`m_dActualVoltage/…`),
`rename_setting` (`m_symbolInfo.value.m_name` or `m_name`),
`set_load_classification` (`m_abbreviation`, …), `modify_setting`
(anything), `renumber_circuits` (`m_number`, `m_nStartSlot`),
`rename_panel` (BIP −1140078). `delete_wire` = `manipulate.
delete_element(cascade=True)`. Any settings element is deletable through
`manipulate.delete_element` (its `m_deletion` closure cascades: a voltage
type takes its distribution systems, a classification takes its factor +
params).

## 6 · The combined commit — `commit_electrical(src, out, doc, new_elements=, plans=)`

The core writer had two disjoint paths — `commit.commit_new_elements`
(insert new records + ElemRecs, no edits) and `manipulate.commit_plans`
(remove / replace records + drop ElemRecs, no inserts). Wiring needs both
in one file (new wire + edited devices), so this module composes the
public pieces of both into ONE re-emit of save-unit 0:

```
per seq (101/102/103): apply_edits_to_segment(removals, replacements)   # manipulate
                       insert the new elements' framed records immediately
                       BEFORE the trailing sentinel (id -1)             # commit
                       chunk_segment -> blocks (ISIZE identity)          # manipulate
Global/ElemTable: drop removed rows, add ElemRecs (streams_edit.elemtable_add_element,
                  existing max episode), watermark raised, count in the
                  partition header (offset 14)
both streams re-paged with real CRCIO ECC (ecc.frame_stream); CFB re-written;
save-history streams untouched (minimal-commit policy, as both parents);
BasicFileInfo identity scrub OPT-IN (own_identity=False by default, see §8-C1).
```

`verify_electrical(path, new_ids, edited_ids, deleted_ids)` =
`manipulate.verify_manipulated` (CRC / ECC / walker / ISIZE / stamps /
counts / sentinels / unit-0 ids == ElemTable / edited-and-new records
decode clean in all seqs) + a `structurally_valid` verdict.

**Generic hook this replaces [D]:** ideally `manipulate.commit_plans`
would accept a `new_elements=` argument (or `commit.commit_new_elements`
a `plans=`); the exact composition is `commit_electrical` (≈60 lines) —
lift it into `manipulate.py` when the streams merge.

## 7 · Proof files (`experiments/mep/electrical/`, `make_electrical.py`)

Each is written by the real writer, structurally verified, validated by
`tools/rvt_validate.py` (all three layers, **0 errors**) and semantically
re-read (`Document.from_file`). Full evidence in `manifest.json`.

| file | verb | proves |
|---|---|---|
| `wire_create.rvt` | CREATE + edit | a HOME RUN (free arrow start end → device) and a chamfered BRANCH wire (device ↔ device) for existing circuit 469513 (panel PP-1A slot 50016); the two connected receptacles are edited in the same commit so their supply connectors reference the wires back — the connector graph stays symmetric (no one-way-link warning) |
| `wire_delete.rvt` | DELETE | wire 469466 removed (3 records + ElemRec); its devices' back-links and the neighbouring wire's header mention neutralised |
| `settings_modify.rvt` | MODIFY ×7 | demand factor 'HVAC' 1.0→0.85; voltage '120' max 130→132 V; distribution system '120/240 Single' renamed '240/120 Single Phase' (longer string, block re-flow); wire type 'XHHW' share-ground off; load classification 'Receptacles' abbreviation 'RCPT'; ElectricalSetting default circuit rating 20→30 A; wire tick-label separator '-'→'/' |
| `load_class_create.rvt` | CREATE ×11 | load classification 'EV Charging' as its full closure (own demand factor + 6 parameter elements, mutual parents, fresh `m_typeId`s) + a new '600/347 Wye' distribution system on two new voltage definitions (347 V / 600 V) |
| `panel_renumber.rvt` | MODIFY | `renumber_circuits` on real panels PP-1A (hole at 2 → 1..17) and LP-2 (holes 1/14/19 → 1..17): 16 + 17 circuits rewritten; the rule first reproduces Autodesk's own numbering on the untouched PP-2B / PP-3B |

## 8 · Confidence / unknowns

| claim | status |
|---|---|
| wire model: view-owned, `m_setidCircuits` one-way, two curve connectors with sibling + device refs, home run = free start end, devices reference wires back on conn 1 | **V** (1,045 wires, 2,003 device edges, referential closure) |
| `m_eType` 0 = arc | **V** (all corpus wires); 1 = chamfer **H** (API enum, no specimen) |
| `m_bDynamicUpdateEnds` = connection state | **V** (400/400) |
| new-wire clone recipe (endpoints, connectors, flags, parents) is what Revit needs | **H** — internally consistent, referentially and connector-graph clean, validator-clean; only Revit acceptance can judge (regeneration re-derives the tick marks / arrow / end snapping) |
| voltage / VA internal unit = SI ÷ 0.3048² | **V** (5 voltages, the 10 kVA receptacle threshold) |
| distribution system / voltage / wire-type / demand-factor / load-classification field maps | **V** (all specimens decode + round-trip byte-exact) |
| load classification = closure with own factor + 6 param elems, mutual parents, `m_typeId` = session GUID + 8-hex element id | **V** (10/10); a NEW closure being accepted **H** |
| panel numbering rule (two-column, same-parity lowest fit) | **V by reproduction** on PP-2B / PP-3B incl. 3-pole spans |
| renumber = rewriting `m_number` + `m_nStartSlot` suffices (schedule caches recomputed) | **H** |
| BIP names −1140107 (conductor count), −1140082 (mains), −1140079 (max poles) | **H** (ids/values V, names inferred) |
| distribution config beyond single/wye (delta, high-leg) | **not implemented** (no corpus specimen) |

**Open items:** O1 wire acceptance — does Revit's translator regenerate
our wires' arrows/tick marks and keep the connector links (the H-column
question for every MEP curve)? O2 whether an unassigned wire (empty
`m_setidCircuits`) is legal (31 corpus wires carry 0 circuits — likely
yes). O3 `m_kConfig` codes for delta systems; O4 the six ParamElem
`m_eType` codes (0/1/3 observed) map to spec types (apparent power /
current / …) — cloned per donor field, unverified individually; O5
whether Revit renumbers our renumbered panel differently when the panel's
`m_eCircuitNumberingOption` ≠ 0 (all corpus panels are 0).

**Cross-stream conflict found (not mine to fix, C1):** `identity.
own_basic_file_info` (writer identity gate G2, added 2026-08-03) replaces
`BasicFileInfo`'s Unique Document GUID without prepending the matching
`Global/History` episode, so every fresh `commit.commit_new_elements`
output now FAILS `rvt_validate` L2 ("Unique Document GUID != History
entry[0] GUID") — the verified invariant `BFI GUID == History[0]`.
`commit_electrical` therefore ships the scrub as **opt-in**
(`own_identity=False` default) so the proof files validate clean; the fix
is either (a) `own_basic_file_info` keeps `unique_document_guid = History
entry[0]` and only scrubs path/user/central identity, or (b) the create
commits also prepend the History episode (`streams_edit.record_save`),
making the new GUID legitimate — see `docs/inbox/mep-electrical.md`.

## 9 · Reproduction

```
.venv/bin/python experiments/mep/electrical/make_electrical.py     # 5 files + manifest.json
.venv/bin/python -m pytest tests/test_mep_electrical_data.py -q        # 25 passed (1 slow e2e)
.venv/bin/python tools/rvt_validate.py experiments/mep/electrical/*.rvt
.venv/bin/python -m rvt.mep.electrical_data samples/rmebasicsampleproject.rvt settings|wires|panels|panel 622027
```
