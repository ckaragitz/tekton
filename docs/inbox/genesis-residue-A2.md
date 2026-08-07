# genesis-residue-A2 — THE REMAINING UNSUBSTITUTED CLASSES (Group-A round 2) — workstream record

Charter: take the disposition list of `docs/inbox/genesis-residue-A.md` — the
residue classes the first Group-A round did not reach, each with a stated
owning rung (`residue_after_ZA_deep.json` disposition "outside both
charters", ~373 elements) — and, working from the CERTIFIED **ZA_deep**, for
each such class group (excluding what the deletion stream and Group B already
own): (1) census the class in the six samples + ZA_deep (free value vs
format-constant machinery), (2) author OUR constructor in
`src/rvt/genesis/residue_a2.py` (our values as plain data + mined constants;
empty-machinery classes REPRODUCED and declared "nothing of ours to reject"),
(3) emit the in-place rung `ZC_<group>` = ZA_deep + that group substituted in
place (validator 0 errors, registry parity, byte-delta-vs-ZA_deep = only that
group's object records — ASSERTED), plus the cumulative `ZC_deep`; and STATE
honestly every element that cannot be substituted in place, with its required
operation.

**Territory touched ONLY:** `src/rvt/genesis/residue_a2.py` (new),
`tests/test_residue_a2.py` (new, 43 pass), `experiments/genesis/subst_k4/
residue_a2/*` (7 `.rvt` + one `.json` certification report each + `probes.json`
+ the frozen HVAC-type enums + the two censuses + the staged control), this
record.  No existing `src/rvt/*.py`, tool, test or `.rvt` was edited; every
dependency (`rvt.genesis.{types,settings,house_standard,residue_a,residue_b}`,
`rvt.regadd` / `rvt.regdiff` / `rvt.mutate`, and the certification helpers of
`tools/genesis_substitute_v3.py`) is IMPORTED.  No browser / viewer use: the
seven files + the control + `probes.json` are left for the orchestrator's
queue.

## Result in one screen

**Every remaining-class group of the disposition list is BUILT and VALID from
the certified ZA_deep, by pure in-place substitution of OUR constructors'
objects (or byte-identical REPRODUCTION of the pure machinery): 7 files, every
one validator-VALID (0 errors), structurally proven, four-registry coherent,
`Global/Latest` + `Global/ElemTable` BYTE-IDENTICAL to ZA_deep, nothing added
or deleted, registry parity 100 % (asserted), the byte-delta assertion holding
(ONLY the landed slots' seq-102 object records change), ZERO dangling
references in our objects, and a per-class FIELD-DELTA table proving exactly
which object fields carry OUR value.  What cannot be substituted in place is
LISTED with its operation (4 elements: the link pair, the DataStorage vendor
blob, the room's plan topology).**  Reproduce (~12 s):
`.venv/bin/python -m rvt.genesis.residue_a2`.

After `ZC_deep`: **2,116 of the base's 3,342 host elements (63 %) are OUR
constructors' output** (up from 1,806 = 54 % in ZA_deep); the residue = 1,226
= 1,222 owned by other streams (Group B's classes not yet composed onto this
base + the deletion stream's constellations) + the 4 not-in-place-able.

Base: `experiments/genesis/subst_k4/residue_a/ZA_deep.rvt` — CERTIFIED
(ledger: "*** GROUP-A RESIDUE LOADS ***", VERDICTS #18).  Control:
`residue_a2/CTRL_ZA_deep_base.rvt` (md5 `56308637529a0d0a95976f5701e2615e`,
byte-identical to ZA_deep — read FIRST; a failing control voids the round).
Independent arbiter (this session): `tools/rvt_validate.py --quiet
residue_a2/*.rvt ZA_deep.rvt` → 9 × `OK errors=0 warnings=1` (the warning =
the standing Extensible-Storage decode gap on the 1 DataStorage element — the
very element this record lists as delete-only).  `tools/probe_batch.py check
residue_a2/ZC_*.rvt` → **ADMISSIBLE** (every probe's base = ZA_deep
`[certified]`, declared by `probes.json`).

| # | rung | class layer substituted IN PLACE | slots | changed | byte-identical (reproduced) | left (stated) | verdict |
|--:|---|---|--:|--:|--:|--:|---|
| 1 | **ZC_deep** | ALL groups below at once (bisection-first) | 310 | 269 | 41 | 4 | VALID |
| 2 | **ZC_hvac** | the HVAC / energy web: 27 day schedules → OUR schedule library; 27 year schedules (reproduced 365-day wrappers); 125 space types + 33 building types = interface enum identity KEPT, every settings value OURS | 212 | 185 | 27 (year schedules) | 0 | VALID |
| 3 | **ZC_elec** | 18 load classifications (3 reserved roles + 15 of ours) + 21 demand factors → OUR NEC-cited rules, the id-wired web preserved | 39 | 39 | 0 | 0 | VALID |
| 4 | **ZC_conduit** | 5 conduit standards + the conduit size table + the cable-tray size list → OURS (NEC Ch.9 / NEMA VE-1 facts) | 7 | 7 | 0 | 0 | VALID |
| 5 | **ZC_systype** | residue system types: wall + floor type over OUR palette materials; ASTM A1064 fabric wire + sheet | 4 | 4 | 0 | 0 | VALID |
| 6 | **ZC_analysis** | 8 area types + 5 empty plan topologies REPRODUCED; our area-report settings; OUR EMPTY assembly-code table; 10 colour schemes; 8 load cases + 8 natures | 41 | 28 | 13 (8 area types + 5 topologies) | 2 (topo 9744, DataStorage) | VALID |
| 7 | **ZC_browse** | 5 surplus browser organizations → 5 more of ours; the sheet-view constellation ADOPTED (our sheet identity, link overrides emptied) + its drawing reproduced | 7 | 6 | 1 (the drawing) | 2 (link pair) | VALID |

Upload order (`probes.json:upload_order_bisection_first`): **CTRL first, then
ZC_deep, then ZC_hvac, ZC_elec, ZC_conduit, ZC_systype, ZC_analysis,
ZC_browse.**  ZC_deep PASS retires every class this stream can retire; a
ZC_deep FAIL is read through the six singles (each derives DIRECTLY from
ZA_deep, so the first single FAIL with the control PASSING convicts exactly its
group; the reproduced-machinery slots are byte-identical and can never be the
cause).

## THE method, and why the probes are clean

Every rung is `rvt.regadd.substitute_elements(seqs=(102,), keep_row=True)` on
the certified ZA_deep: OUR constructor's seq-102 OBJECT replaces Autodesk's at
the SAME element id — same ElemTable row, same record position, same registry
slots; nothing added, nothing deleted.  The ONE variable of a rung is the
CONTENT of our objects at Autodesk's own registrations; the emission and
certification are the residue-A rung emitter (`residue_a.emit_rung`, imported)
so every report carries the same instruments (validator, structural proof,
four-registry census, registry parity, `rvt.regdiff` registration sample,
byte-delta assertion table, FIELD-DELTA table, object self-check, dangling-
reference check).

This stream's census sorted every residue class into five honest
categories, and the rungs implement each:

* **A. INTERFACE-KEYED SETTINGS** — a per-release ENUM the reader keys on,
  whose VALUES are the document's settings: the **125 HVAC space types and 33
  building types** (`m_eSpaceType` / `m_eBuildingType` → canonical name;
  IDENTICAL in all six samples including the German-language file whose
  schedule / load-nature names ARE localized — i.e. a locale-independent
  reader-fixed list = the public gbXML / ASHRAE space- and building-type
  enumerations), the **8 built-in area types** (`m_eSpaceType` per area
  scheme), the **load-classification signature ROLES** (`m_signitureType`:
  exactly one motor = 1 / other = 2 / spare = 3 per project, 6/6 samples).
  The enum identity is REPRODUCED from the slot; the values are OURS —
  `rvt.genesis.catalog`'s law "THE ENUM IS A FORMAT CONSTANT, THE VALUES ARE
  OURS".  (Frozen once: `residue_a2/hvac_type_enums.json`, derived by
  `derive_hvac_type_enums()` which reads ONLY the enum keys + canonical names
  and asserts identity across the corpus — no density / setpoint / schedule
  value is ever read from any file.)
* **B. NAME-KEYED CATALOG CONTENT** — free values with our naming: day
  schedules, demand factors, load classifications, load natures / cases,
  conduit standards + sizes, cable-tray widths, colour schemes, browser
  organizations, fabric types, the wall / floor types → OUR library at the
  slots (extending the house standard where the base carries more slots than
  the library has entries, the Group-B precedent).
* **C. PURE MACHINERY** — no free value at all: `AreaTypeElem` (area-scheme
  wiring + enum), the empty `AreaSchemePlanTopologies` holders,
  `BuildingOperatingYearSchedule` (365 day-slot ids wrapping ONE day
  schedule, uniform 27/27), the sheet's `DBDrawing` (viewport list) →
  REPRODUCED byte-identical; the byte-delta table then lists these 41 slots as
  "landed but byte-identical" — the machine-checked statement that there is
  NOTHING OF OURS TO REJECT (Group B's machinery-reproduction proof method,
  `genesis-residue-B.md` finding 8).
* **D. PRODUCT DATA WE EMPTY** — the `AssemblyCodeTable` slot EMBEDS
  Autodesk's shipped 795-row UniFormat classification table (byte-identical
  in all six samples = product data) AND names an Autodesk employee's local
  OneDrive path (an identity leak): OUR `AssemblyCodeTable` is EMPTY (the
  KeynoteTable precedent — the shape is exactly the reader-accepted empty
  keynote table: empty `ClassificationEntries` + empty external-reference
  cells).  Both the product data and the leak leave with it.
* **E. NOT IN-PLACE-ABLE** — stated with the required operation (below).

## Census evidence (six samples + ZA_deep; `residue_census.json`, `hvac_type_enums.json`)

* **The HVAC / energy database is a per-release fixed LIST with document
  values.**  125 space types and 33 building types appear in EVERY sample
  (rst / rstadv / rac / racadv / rme / dach), with `m_eSpaceType` 0..124 and
  `m_eBuildingType` 0..32 dense, and **identical canonical names in all six —
  including the German-language dach file** (where the schedule NAMES and the
  load-nature NAMES ARE localized: "Aus - 24 Stunden", "Eigengewicht", …).  The
  values, however, come in TWO distinct sets across the corpus (rst + rac
  carry one hash per type, rstadv / racadv / rme / dach another): two vintages
  of Autodesk's shipped DEFAULTS, i.e. the values are the document's SETTINGS
  layer (user-editable) while the identity is the interface.  Value units
  (verified against the sample magnitudes): power densities in W/ft² × the
  m²→ft² factor 10.7639…, occupant heat gains in W × the same factor, setpoints
  in KELVIN, airflows in ft³/s, occupancy as ft²/person.
* **The schedule model** is a 1:1 web: 27 day schedules (name + 24 hourly
  fractions) ← 27 year schedules (365 day-slot ids, ALL uniform: 365 × the
  one day schedule they wrap, 27/27; no name, no free value) ← the space /
  building types' three schedule ids (occupancy / lighting / power) point at
  YEAR schedules.  In place, our day profile lands at each day slot; the year
  wrapper is reproduced (it now wraps OUR day schedule); the types reference
  OUR year slots by role.
* **Electrical layer wiring.**  18 classifications point at 12 of the 21
  demand-factor slots (three demand slots are SHARED by 4 / 3 / 2
  classifications; 9 are unreferenced); each classification is referenced by
  its 6 `ParamElemElectricalLoadClassification` companions (Group B's ZB1
  layer — id-wired both ways, endgame §2 row 6: "the cleanest cross-group
  case").  Reserved ROLES: exactly one `m_signitureType` 1 (motor), 2 (other),
  3 (spare) per project in all six samples (dach carries a second sig-1 row) —
  the role stays with the slot; our library supplies the role entry.  Rule
  codes verified on the corpus: 0 = constant (47 rows), 3 = COUNT ranges (the
  rme motor rule), 4 = LOAD ranges in internal power units (NEC 220.42
  dwelling tiers, UK socket tiers); code 2 appears only on single-row unity
  factors (never emitted by us).
* **Conduit / tray catalogs.**  `ConduitStandardType` = a name only (EMT /
  IMC / RMC / RNC / RNC Schedule 40 / 80 across the corpus; dach ", EMT," /
  "rmc" typos confirm user content); the size table (`ConduitSizesElem`) is
  keyed by the standard slot ids with rows (nominal / inner / outer / bend
  radius, feet) that DIFFER per sample (metric designators in rst, i.e. NEC
  Chapter 9 Table 4 dimensions with metric nominal designators);
  `CableTraySizesElem` = a width list (16 metric widths in rst).
* **Load natures are free names** (English set Dead / Live / Wind / Snow /
  Roof Live / Accidental / Temperature / Seismic in five samples; GERMAN in
  dach) — content, not a fixed enum; the load-case CATEGORY ids
  (-2005211..-2005218 = dead / live / wind / snow / roof-live / accidental /
  temperature / seismic, aligned with the corpus case names DL1 / LL1 / WIND1
  / SNOW1 / LR1 / ACC1 / TEMP1 / SEIS1) are the interface enum each case picks.
* **Colour schemes** with ZERO entries are corpus-normal (rst 0-entry
  schemes; racadv all-empty); each scheme is keyed by (target category, key
  BuiltInParameter, area scheme, by-range flag).
* **`DBViewDrafting` 1457028 is the sheet view** of the K4 lineage's sheet
  "S101 - Framing Plans": its `DBDrawing` 1457031 lists three viewports — its
  own drafting content 1457030 + viewports 1457043 / 1457044 placing OUR two
  plan views (245443 "L2", 1064656 "L1") — which is exactly why the deletion
  stream measured the constellation 0/7 delete-reachable ("pinned by OUR plans
  ⇒ ADOPT").  Its `m_pRvtLinkOverrides.m_displaySettingsMap[0].first` names the
  `RvtLinkSymbol` 1250029 — the seq-102 pin of the deletion stream's finding 1.
  Corpus census (55 drafting/sheet views): the free fields are exactly the
  identity strings (name, sheet number, date, issue date, drawn / checked /
  designed / approved by) + wiring ids + the link-override map; the ~330
  override-manager / draw-filter / retouch fields are constant machinery.
* **`AreaTypeElem` is pure machinery** (only `m_areaSchemeId` → OUR
  AreaMeasureElems 9490 / 9494 + the built-in area-type enum `m_eSpaceType`
  0..7); the 6 residue `AreaSchemePlanTopologies`: 5 are EMPTY holders
  (scheme × option, empty `PlanTopologies`), 1 (9744) CONTAINS the placed
  room's `LevelRoomPlan` — the room constellation's (deletion finding 2), left.

## The constructors (`src/rvt/genesis/residue_a2.py`)

| constructor | our values (plain data) | interface / machinery kept from the slot | shape |
|---|---|---|---|
| `hvac_day_schedule(name, 24 fractions)` | OUR schedule library — 27 named 24-hour profiles (occupancy / lighting / plug / equipment / HVAC availability for office, classroom, assembly, transit-24h, shop, warehouse, retail, dining, healthcare-24h, residential, recreation, egress, corridor, charging, …) | the slot's cell apparatus (verbatim; a null cell list stays null) | pure |
| `hvac_year_schedule_reproduced(slot)` | — (365-day wrapper of the now-OUR day schedule) | everything | REPRODUCED |
| `hvac_space_type(enum, name, profile, …)` | OUR value profile (36 functional profiles: LPD / EPD / ft²-per-person / OA cfm-per-person + cfm-per-ft² / occupied setpoints / occupant heat gains by activity / plenum-lighting / RH / infiltration / carpet / plenum flag) + OUR year-schedule roles; the 125-way enum → profile classification is ours | `m_eSpaceType` + canonical name (the interface identity), the OA-standard enum, cells | pure |
| `hvac_building_type(enum, name, profile, …)` | OUR 17 building profiles (building-area LPD / EPD / occupancy / OA / setpoints incl. unoccupied cooling / equipment operating window / schedule roles) | `m_eBuildingType` + name, cells | pure |
| `our_load_classification(entry, slot)` | OUR 18-entry library (3 role entries + 15 regular: Lighting-Interior / -Emergency / -Exterior, Receptacle-General / -Dedicated, Data-IT, HVAC-Cooling / -Heating / -Fans, Kitchen, Elevator, EV Charging, Bus Charging, Shop Equipment, Life Safety) + our label templates + abbreviations + space-load class | the demand-slot id, the six companion param ids, the reserved signature ROLE | via `types.new_load_class` |
| `our_demand_factor(rule_key, …)` | OUR NEC-cited rule library (house `continuous125` / `receptacle` / `motor` / `kitchen` / `no_diversity` + 9 extras: welder group 630.12, dwelling lighting 220.42, non-coincident 220.60, fire pump 695, sign 220.14F, track 220.46B, crane group 610.14E, elevator group 620.14, existing recalc 220.87) | cells | via `types.new_demand_factor` |
| `plan_electrical_layer(doc, …)` | (the deterministic assignment: roles by signature, classifications grouped by shared demand slot so a shared slot serves ONE rule of ours, unreferenced demand slots take our extras) | the whole id web | planner |
| `our_conduit_standard / our_conduit_sizes / our_cable_tray_sizes` | our standard SELECTION (EMT / IMC / RMC / PVC-40 / PVC-80) + NEC Ch.9 Table 4 dimensions + Table 2 bend radii + NEMA VE-1 tray widths (published FACTS; the house standard's `CONDUIT_STANDARDS` / `CABLE_TRAY_WIDTHS_IN`) | the standard slot ids the size table is keyed on, cells / param sets | via `types` constructors |
| `our_wall_type / our_floor_type` | 'GEN Wall - Interior Partition 121mm' (gypsum / stud / gypsum) + 'GEN Floor - Concrete Slab 150mm' over OUR palette materials looked up BY NAME in the parent | the type-preview id (its LegendComponent then displays OUR type), cells / param sets / geomSteps | via `types.new_wall_type / new_floor_type` |
| `our_fabric_wire_type / our_fabric_sheet_type` | ASTM A1064 designations (W2.9, WWF 6x6-W2.9xW2.9 — FACTS of the standard) + our sheet make-up (8×20 ft, 6 in spacing, 3 in overhang, 12 in laps, 30.5 kg) | the wire slot, the sheet-material slot, the MasterSymbolCell → SlaveSymbolTracker (Group B's) | pure |
| `our_load_nature / our_load_case` | OUR structural load standard (D / L / Lr / S / W / E / T / Ax names + case names / numbers, mirrored into their AString params) | the case's built-in load-case CATEGORY + its nature-slot wiring | pure |
| `our_area_report_settings(slot)` | our text (settings name, prefixes, font names / sizes) | the unit-format machinery + its own font / internal-category wiring (already ours) | OVERLAY (said so) |
| `our_empty_assembly_code_table(slot)` | EMPTY (no classification rows, no external references) | — | pure |
| `our_color_fill_schema(slot, i)` | our scheme names / titles; our department vocabulary entries on string-keyed room / space schemes, our area-range breakpoints on the by-range scheme, EMPTY elsewhere (auto-populate); our print-safe palette | the (category, parameter, area scheme, by-range) definition pairing, the built-in solid fill token | OVERLAY |
| `our_browser_organization(spec, slot)` | 5 MORE of our organizations ('Views - Level', 'Views - Family and Type', 'Sheets - Series (1 Character)', 'Sheets - Issue Date', 'Sheets - Name') over BuiltInParameter keys | the tree type per slot | via `settings.browser_organization` |
| `our_sheet_view(slot)` | our sheet identity ('GEN Overall Plans' / GEN-101 / 01-01-26 / GEN GEN GEN GEN) + EMPTIED RvtLinkOverrides (we place no linked model — the link symbol's seq-102 pin is REMOVED) | ~460 fields of view machinery + drawing / viewer / viewport / view-type / sketch-plane wiring | OVERLAY |
| `reproduced(class, slot, why)` | — | everything | REPRODUCED |

Every constructor's object encodes → decodes → re-encodes BYTE-EXACT
(`--demo`: 14/14; the tests; the per-rung self-check gate — 310/310 objects
in ZC_deep) and NO object references an id absent from the parent (dangling
check: 0 across all seven files).

### What is a fact vs what is ours (the standard applied throughout)

Where a magnitude is an engineering QUANTITY, the module names the public
source of the FACT it reflects and keeps the SELECTION, naming and assembly
ours: NEC section rules (demand factors, conductor / conduit dimensional
tables), NEMA VE-1 tray widths, ASTM A1064 fabric designations + wire geometry,
ACI small-bar bend minimums, ASCE-7-style load-category symbols, ASHRAE-range
lighting power densities / ventilation rates / occupant heat gains for the
HVAC profiles.  The 125-way space-type → our-profile classification, the
schedule curves, the setpoints, the palettes and every name are ours.  **No
value table is read from any Autodesk file**: the only things read from the
corpus are ENUM keys + canonical names (interface constants, per the catalog
precedent) and our own palette materials' NAMES for the wall-layer lookup.

## FIELD-DELTA (the sharpest statement of what each probe tests)

`ZC_deep.json:field_delta_by_class` — the object fields whose value differs
between the slot's object and ours (everything else is byte-identical
machinery / wiring / interface identity):

* `HVACLoadSpaceTypeElem` (125): the settings block only — LPD / EPD 124,
  cooling / heating setpoints 125, area-per-person 124, sensible / latent
  gains 124, OA per area 45 / per person 42, plenum-lighting 125,
  dehumidification 125, infiltration 125, equipment radiant 125, carpeting 35,
  ACH 11, the three schedule ids 123–124.  `m_eSpaceType` and `m_name`
  identical on all 125.
* `HVACLoadBuildingTypeElem` (33): the same settings block + equipment start
  / end times 30 / 26 + unoccupied cooling setpoint 33.  Identity identical.
* `HVACLoadScheduleElem` (27): `m_strName` 27 + the 24 hourly fractions
  (19–25 per hour).
* `BuildingOperatingYearSchedule` (27): **no entry** — byte-identical.
* `ElectricalLoadClassification` (18): `m_name`, `m_abbreviation`, the six
  label templates 18 each, `m_spaceLoadClass` 9.  Demand id / six companion
  ids / signature roles identical.
* `ElectricalDemandFactorDefinition` (21): `m_name` 21, `m_ruleType` 10,
  `m_values` rows (len 7 / factors / ranges).  Cells identical.
* `ConduitStandardType` (5): `m_symbolInfo.value.m_name` ONLY.
  `ConduitSizesElem`: the row values.  `CableTraySizesElem`: the row list.
* `BasicWallType`: name + the compound-structure fields our different layer
  make-up drives (layers, shell counts, structural index, vertical-region
  grid, coarse fill) + `m_function`.  `FloorAttributes`: name + layers.
  `FabricWireType`: name + the two diameters.  `FabricSheetType`: name +
  spacings / overhangs / laps / dimensions / wire counts / mass.
* `LoadCaseElem` (8): `m_name`, the mirrored AString value, `m_number` 5.
  `LoadNatureElem` (8): `m_name` + mirrored value.  Category / nature wiring
  identical.
* `ColorFillSchema` (10): `m_strName`, `m_title`, `m_colorFillArr` (5 slots
  changed length).  `AreaReportSettingsElem`: font sizes + arc prefix (the font
  names were already Arial = ours).  `AssemblyCodeTable`: the entry lists +
  the two reference lists (795 rows → 0).  `AreaTypeElem` /
  `AreaSchemePlanTopologies` / `DBDrawing`: **no entry** — byte-identical.
* `BrowserOrganization` (5): name + folder definitions.  `DBViewDrafting`
  (1): the eight identity strings + `m_pRvtLinkOverrides.value.
  m_displaySettingsMap.#len` (the link pin, emptied).

## New findings (evidence [V] — merge into KNOWLEDGE.md)

1. **The HVAC space-type / building-type database is an INTERFACE ENUM with
   document VALUES, not sample content and not deletable product data** [V,
   6/6 samples]: 125 space types (`m_eSpaceType` 0..124) and 33 building types
   (`m_eBuildingType` 0..32) with IDENTICAL canonical names in every sample —
   including the German-language file, whose schedule and load-nature NAMES are
   localized — i.e. the reader's fixed type list = the public gbXML / ASHRAE
   90.1 space- and building-type enumerations; the VALUES ship in two Autodesk
   default vintages across the corpus = the settings layer.  ⇒ substitute
   in place with the identity kept and OUR values (this stream's ZC_hvac), NOT
   the endgame's step-23 deletion (which the deletion stream also measured
   5-of-212 PINNED via our EnergyDataSettings + the room).  Value units: power
   densities W/ft² × 10.7639, occupant gains W × 10.7639, setpoints Kelvin,
   airflows ft³/s, occupancy ft²/person.
2. **The HVAC schedule model** [V]: 27 day schedules (name + 24 fractions) ←
   27 year schedules (365 day-slot ids, uniform 27/27 — pure machinery
   wrappers, no name) ← the types' three schedule ids point at YEAR
   schedules.  A day slot substituted in place is transparently re-wrapped
   by its year schedule (byte-identical reproduction) — the schedule library
   swaps with zero registration motion.
3. **The load-classification signature ROLES are reserved slots** [V, 6/6]:
   exactly one `m_signitureType` 1 (motor), 2 (other), 3 (spare) per project;
   `m_spaceLoadClass` 1 = lighting / 2 = power / 0 = none.  An in-place
   library assignment must keep each role at its slot (ours does).  Demand
   rule codes: 0 constant / 3 count ranges / 4 load ranges (internal power
   units); the classification → demand → 6-companion web is id-wired and
   survives substitution on both group sides by construction.
4. **The `AssemblyCodeTable` embeds Autodesk's UniFormat table AND an
   identity leak** [V, byte-identical in 6/6]: 795 `ClassificationEntry` rows
   (the shipped `UniformatClassifications.txt`, embedded verbatim) + external
   resource cells naming an Autodesk employee's local OneDrive / desktop
   paths.  OUR table is EMPTY (the keynote-table precedent's exact shape) —
   the provenance ledger's identity policy applies to ELEMENT strings too
   (Group B's finding 10 extended: worksharing user, printer, and now the
   assembly-code file path).
5. **`AreaTypeElem` and `BuildingOperatingYearSchedule` are pure machinery**
   [V]: no free value (area-scheme wiring + a built-in enum; 365 uniform day
   ids) → reproduced byte-identical; a residue bucket is retired WITHOUT
   authoring when its class has no free value (Group B's finding 8 confirmed
   on three more classes, incl. the sheet's `DBDrawing`).
6. **The K4 lineage's sheet is `DBViewDrafting` 1457028 + `DBDrawing`
   1457031** [V]: a sheet is a drafting-VIEW whose drawing carries the
   viewports (no separate sheet class); this one places OUR two plan views —
   hence the deletion stream's "pinned by OUR plans ⇒ ADOPT".  Its free fields
   are exactly the identity strings + the RvtLinkOverrides map; ADOPTING it in
   place with an EMPTY link-override map removes the `RvtLinkSymbol`'s seq-102
   pin (deletion finding 1), leaving only the seq-101 header pins of OUR view
   slots for the clean-header rung.
7. **Load NATURES are free names, load-case CATEGORIES are the enum** [V]:
   the nature name set is localized in the German file (content), while the
   eight `OST_LoadCases*` category ids are the interface each case picks; a
   nature slot is named for the category of the case referencing it, so the
   case ↔ nature web stays coherent under substitution.
8. **The conduit size table is keyed by the standard slot ids** [V]:
   substituting the standards and the table together (the table re-keyed on
   the SAME slot ids, which now carry OUR standards) keeps the routing web
   coherent with zero motion; the rows are NEC Chapter 9 Table 4 dimensional
   facts in feet.
9. **In-place substitution of an interface-keyed settings web preserves
   every referrer into the web** [V]: OUR EnergyDataSettings' building-type
   id, the room's space-type id, the Group-B companion params'
   `m_idLoadClassification`, the type-preview LegendComponents'
   `m_previewElemId` targets — all point at ids that now carry OUR objects;
   no referrer needs an edit (the residue-A registry-parity property extends
   to the value webs).
10. **The whole disposition list retires in ONE cumulative rung at 310-slot
    scale** [V, ZC_deep]: 269 records changed + 41 reproduced byte-identical,
    validator 0 errors, `Global/Latest` + `Global/ElemTable` byte-identical,
    unit-0 re-blocking re-flows only the seq-102 run, four-registry coherence
    trivially preserved (no document moves); the batch builds in ~12 s.

## What CANNOT be substituted in place (stated, with the required operation)

`probes.json:not_in_place_able_with_operation`, every report's
`residue_left_in_place`, `residue_after_ZC_deep.json`:

| element(s) | operation | why (evidence) |
|---|---|---|
| `RvtLinkSymbol` 1250029 | **DELETE-WITH-CONTENT — after the clean-header rung** | a genesis file links NO model (the symbol names the external sample file `rac_basic_sample_project.rvt` + a relative path). The deletion stream (finding 1) measured it NOT delete-reachable on ZA_deep: OUR OWN Y2 / Y9 view slots' inherited seq-101 headers list it as a deletion parent; THIS stream's `our_sheet_view` REMOVES its remaining seq-102 pin (the sheet's link-override map). Retirement = the substitution stream's clean-header rung (`seqs=(101,102)` on our views) then one maxgc deletion of {symbol + the drafting/sheet-view constellation} — not an in-place slot. |
| `RvtLinkInstance` 1250030 | **DELETE-WITH-CONTENT (emitted: deletion stream `D_links`)** | the placed instance; `D_links` deletes it with OUR CopyWatchProperties 1250031 (our own referrer leaves with it — reduce-law EDIT-FREE). |
| `DataStorage` 1382860 | **DELETE (leaf)** | an Extensible-Storage container whose `ESEntityCell` entity blob is a VENDOR schema this project's decoder does not read (the arbiter's one standing warning). Nothing of ours to express; reproducing it would keep an undecoded third-party blob; zero referrers → the deletion set (endgame step 24). |
| `AreaSchemePlanTopologies` 9744 | **DELETE-WITH-CONTENT with the room constellation** | it CONTAINS the placed room's `LevelRoomPlan` + boundary curves and is PINNED by OUR `AreaMeasureElem` 9490's kept wiring (deletion finding 2). Left byte-identical here; leaves with the room, atomically, after the settings stream's wiring fix. |

## Diffs / hooks proposed for files OUTSIDE this territory (NOT applied)

* **`src/rvt/genesis/house_standard.py`** — the data introduced here belongs
  in the house standard next to `DEMAND_FACTORS` / `LOAD_CLASSIFICATIONS` /
  `CONDUIT_STANDARDS`: `residue_a2.DAY_SCHEDULES` (our schedule library),
  `SPACE_PROFILES` / `SPACE_TYPE_PROFILE` / `BUILDING_PROFILES` /
  `BUILDING_TYPE_PROFILE` (our HVAC standard + the enum classification),
  the extended `DEMAND_RULES` + `LOAD_CLASS_LIBRARY`, `LOAD_NATURE_BY_CATEGORY`
  / `LOAD_CASE_BY_CATEGORY`, `PVC80_STANDARD` (add to `CONDUIT_STANDARDS`),
  `COLOR_FILL_PALETTE` / `DEPARTMENT_VOCABULARY`, `BROWSER_ORGANIZATIONS_EXTRA`,
  `FABRIC_WIRE` / `FABRIC_SHEET`, `SHEET_IDENTITY`.  Kept in `residue_a2` only
  to respect territory.
* **`src/rvt/genesis/types.py::new_load_class`** — hard-codes
  `m_signitureType = 0` (house_standard finding F-HS-4): add a `signature`
  parameter (this stream sets it post-hoc); and `new_demand_factor`'s
  `rule` docstring enum (0 constant / 1 quantity / 2 load / 3 percentage) is
  contradicted by the corpus (0 / 3 count / 4 load — F-HS-3): correct the
  mapping so callers pass raw codes safely.
* **`tools/genesis_deletion.py` / `docs/writer/genesis-endgame.md`** —
  finding 1: the HVAC / energy database (endgame step 23, DEL-hvac) should
  be re-dispositioned to IN-PLACE (this stream's ZC_hvac): the space / building
  types are a reader-fixed interface list with document values, and the
  deletion stream itself measured 5 of 212 pinned by our own settings; the
  `LoadCaseElem` / `LoadNatureElem` / `AreaTypeElem` / `ColorFillSchema` /
  `AreaReportSettingsElem` / `AssemblyCodeTable` rows of step 24 (DEL-misc)
  likewise retire in place here.
* **The substitution stream (clean-header rung, deletion finding 1)** — the
  seq-102 side of the `RvtLinkSymbol` pin is REMOVED by ZC_browse
  (`m_pRvtLinkOverrides.value.m_displaySettingsMap` = [] on the sheet view);
  the remaining pins are the seq-101 header deletion parents of our view slots
  230 / 245443 / 1064656 / 1454508 / 69851 (the clean-header rung's exact
  list, unchanged).
* **The assembly / composition stream** — Group B's 74-element MEP wire /
  pipe catalog + PipeSegment (ZB2_mepcat, viewer-PASS batch 17) and the rest of
  Group B's classes are still residue ON THIS BASE (ZB rungs were built on Y9);
  the ZAB-and-now-ZC composition replays THREE pure-in-place correspondence sets
  (ZA_deep's + ZB_deep's + ZC_deep's, ids preserved, class-disjoint) in one
  `substitute_elements` call over the certified base.  This record's
  `residue_after_ZC_deep.json` is the exact "still Autodesk's after ZC" list
  the composition consumes.
* **`docs/coverage/viewer-certified.json` (orchestrator)** — add the seven ZC
  files + the control as they read out; every report names its base (ZA_deep)
  + certification + control; on ZC_deep PASS, ZC_deep is a certified deep
  base for the composition.
* **KNOWLEDGE.md owner** — merge findings 1–10 (the interface-enum-with-values
  law for the HVAC database, the schedule web, the reserved signature roles,
  the assembly-code product data + identity leak, the sheet model, the
  machinery-reproduction retirements).
* **`tools/sync_plugin.py`** — this stream ADDS a `src/rvt` module
  (`rvt/genesis/residue_a2.py`); the project's standing rule (sync the plugin
  bundle after every `src/rvt` change) makes `tests/test_plugin_sync.py` flag
  drift until the sanctioned regeneration `python tools/sync_plugin.py` is
  run (this session ran it — see BRANCH STATE).

## Pre-specified follow-up variants (ONE change each; build only on a FAIL)

* **ZC_hvac bisection**: `ZC_hvac_sched` (only the 27 day schedules ours; the
  types reproduced) and `ZC_hvac_types` (only the space / building type values
  ours; the day schedules reproduced) — two singles from ZA_deep to separate a
  schedule-object objection from a settings-value / unit objection.  Add
  `ZC_hvac_defaults` (types with the SLOT's own schedule ids, our other values)
  if the schedule re-wiring is the suspect.
* **ZC_elec bisection**: `ZC_elec_labels` (our library but the sample's label
  template phrasing) vs `ZC_elec_rules` (our labels + the slot's own rule
  rows) — isolates the label-token grammar from the rule-row grammar.
* **ZC_analysis bisection**: `ZC_act_empty` (only the empty assembly-code
  table), `ZC_cfs` (only the colour schemes), `ZC_loads` (only cases +
  natures), `ZC_arep` (only the area-report overlay) — the reproduced
  area-type / topology slots ride with every variant (byte-identical, cannot
  fail).
* **ZC_browse bisection**: `ZC_borg` (only the 5 organizations) vs `ZC_sheet`
  (only the sheet overlay); `ZC_sheet_ident` (identity strings only, the
  slot's own link overrides KEPT) to separate the emptied-link-override change
  from the identity change if the sheet is the suspect.
* **ZC_systype bisection**: three single-slot probes (wall / floor / the
  fabric pair) if the four-slot rung fails.

## Instruments this stream adds

* `residue_a2.derive_hvac_type_enums()` / `load_hvac_type_enums()` — the two
  HVAC type enumerations, derived once with a cross-corpus identity assertion
  and frozen (`hvac_type_enums.json`); keys + canonical names only.
* `residue_a2.plan_electrical_layer(doc, class_slots, demand_slots)` — the
  deterministic role / shared-demand-group assignment over any parent's
  electrical web (report: roles, groups, assignment, demand rules,
  unreferenced demand slots).
* `residue_a2.Parent2` — the residue-A `Parent` view extended with the
  parent's own cumulative report, so "residue" means the parent's residue
  exactly (`residue_of(class)`).
* `residue_a2.census_report()` — the residue census of any parent for this
  stream's classes with the per-class field-variation census
  (`residue_census.json`); `residue_after_deep()` — the census after ZC_deep
  with a disposition per class (`residue_after_ZC_deep.json`).
* The five-category residue taxonomy (interface-keyed settings / name-keyed
  catalog / pure machinery / product data we empty / not in-place-able) —
  the sorting every residue class of the campaign fits.

## Open questions (need the viewer / a decision)

* The seven verdicts, in the upload order above (`residue_a2/probes.json`).
  Every branch is pre-stated per probe (`if_PASS` / `if_FAIL`).  ZC_deep PASS
  retires the whole disposition list; a single FAIL names its group.
* Whether the reader accepts OUR HVAC settings VALUES at the space / building
  type enum registrations — the first probe of the value layer of an
  interface-keyed settings web at this scale (158 typed rows).  ZC_hvac
  answers it; the pre-specified schedule-vs-type bisection stands ready.
* Whether the reader tolerates an EMPTY assembly-code table (the keynote-table
  precedent says yes for an empty classification table of the same shape).
* Whether an emptied RvtLinkOverrides map on the sheet view is accepted while
  the `RvtLinkSymbol` still exists (it should be — no map entry is required by
  a link's mere existence; the seq-101 header pins remain until the
  clean-header rung).  If ZC_browse fails on this, `ZC_sheet_ident` (identity
  strings only) is the retreat.
* Whether the reader requires `m_number` uniqueness across load cases (ours are
  1..8 in our category order — unique) and accepts our load-case names in the
  built-in category slots (the German corpus file's arbitrary case names say
  the name is free).
* The four not-in-place-able elements above and their owning rungs (clean-
  header, room-wiring fix, DataStorage leaf deletion) — recorded next work of
  the substitution / settings / deletion streams; nothing of this stream's.
* The container layer + counsel items (own-save, `Formats/Latest`, the Forge
  corpus) — untouched by design (an in-place ladder leaves the ADocument and
  every container stream Autodesk's byte for byte); endgame §6, last.

## Verification

* `.venv/bin/python -m rvt.genesis.residue_a2` → 7 × `VALID` (~12 s); every
  report carries the structural proof, the byte-delta assertion table, the
  parity table, the registration-diff sample, the four-registry census, the
  field-delta table, the object self-check, the dangling-reference check and
  the residue left with reasons; writes `probes.json`,
  `residue_after_ZC_deep.json`, the control.
* `.venv/bin/python -m rvt.genesis.residue_a2 --demo` → 14/14 constructors
  round-trip byte-exact.
* `.venv/bin/python -m rvt.genesis.residue_a2 --census-only` → the residue
  census (`residue_census.json`); `--derive-enums` → the frozen HVAC enums.
* `.venv/bin/python tools/rvt_validate.py --quiet experiments/genesis/subst_k4/residue_a2/*.rvt experiments/genesis/subst_k4/residue_a/ZA_deep.rvt`
  → 9 × `OK errors=0 warnings=1` (independent arbiter, this session).
* `.venv/bin/python tools/probe_batch.py check experiments/genesis/subst_k4/residue_a2/ZC_*.rvt`
  → `ADMISSIBLE` (every probe's base = ZA_deep `[certified]`).
* Read-back of `ZC_deep.rvt` (this session): space type #92 keeps its
  canonical identity with our 0.65 W/ft² LPD and 297.04 K setpoint; #104 is a
  true zero-load plenum (`m_isPlenum` True); year schedule 1471998 wraps day
  slot 105551 = our corridor lighting schedule; classification 113160 =
  'GEN Miscellaneous Loads' at the other-role (sig 2), 113162 = 'GEN Motor
  Loads' (sig 1) with the NEC 430.24 rule, 121664 = 'GEN Spare Capacity'
  (sig 3); the three slots sharing demand 113943 got three continuous-125 %
  classes and 113943 = our continuous-125 % rule; AssemblyCodeTable = 0
  entries / empty references; conduit standards = our EMT / IMC / RMC / PVC-40
  / PVC-80; the sheet view = 'GEN Overall Plans' GEN-101 with an EMPTY
  link-override map; the eight load natures = our D / L / W / S / Lr / Ax / T
  / E; the five browser organizations = ours.
* `.venv/bin/python -m pytest tests/test_residue_a2.py -q` → **43 passed**
  (2.3 s): the claim contract (the disposition list covered exactly = claimed
  ∪ stated; nothing claimed that another stream owns; the four stated
  operations are all deletion forms), the frozen enums + our profile /
  schedule maps' completeness, every pure constructor's byte-exact round trip
  + our-value assertions (interface identity kept, wiring kept, empty
  assembly-code table, NEC size rows, our sheet identity + emptied link
  overrides, the reproduced-machinery contract), the deterministic
  electrical-web assignment (roles by signature, shared demand slots serve one
  rule, unreferenced demand slots take our extras), the plans against the
  certified ZA_deep (per-class slot counts = the disposition list, identity
  kept per slot, year schedules byte-identical, the room's topology + the link
  pair left, no landed slot re-targeted, merge disjoint), an end-to-end
  ZC_conduit emission in a temp dir with the in-place byte-delta law asserted,
  and the committed batch's reports (bisection-first manifest, every report
  VALID with 0 validator errors + 0 dangling references + no unexpected
  changed / added / removed records, ZC_deep's landed classes = the claimed
  set, the reproduced classes absent from the field-delta, the residue-after
  census containing only 'other stream' + the 4 'NOT in-place-able').
* Full suite: see BRANCH STATE.

## BRANCH STATE

No VCS (plain directory).  NEW files, this stream's territory only:
`src/rvt/genesis/residue_a2.py` (constructors + census + the electrical-web
planner + the ZC-ladder driver), `tests/test_residue_a2.py` (43 pass),
`docs/inbox/genesis-residue-A2.md` (this record), and under `experiments/
genesis/subst_k4/residue_a2/`: `ZC_deep.rvt`, `ZC_hvac.rvt`, `ZC_elec.rvt`,
`ZC_conduit.rvt`, `ZC_systype.rvt`, `ZC_analysis.rvt`, `ZC_browse.rvt` +
one `.json` certification report each, `probes.json` (bisection-first
manifest, base ZA_deep certified, control named, the not-in-place-able list),
`CTRL_ZA_deep_base.rvt` (md5-identical to ZA_deep — the batch control),
`hvac_type_enums.json` (the frozen 125 / 33 interface enums with the
cross-corpus identity assertion), `residue_census.json` (this stream's classes
in ZA_deep with the per-class field-variation census),
`residue_after_ZC_deep.json` (the honest 'still Autodesk's after ZC' list:
1,226 elements = 1,222 other streams' + 4 not-in-place-able; 2,116 of 3,342
ours).  NO existing `src/` module, tool, test or `.rvt` edited; no browser /
viewer use.  Every emitted `.rvt` = validator VALID (0 errors), structural
proof clean, four-registry coherent, `Global/Latest` + `Global/ElemTable`
byte-identical to ZA_deep, registry parity 100 % (asserted), byte-delta
assertion holding, zero dangling references, per-class field-delta recorded.

Full suite this session (`.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle`, 17:08): **1,165 passed, 3 failed** of 1,168 — this
stream's 43 tests are among the 1,165.  The 3 failures: (a) `tests/
test_plugin_sync.py::test_plugin_is_in_sync_with_source` — RESOLVED after
the run: this stream ADDED a `src/rvt` module (as did the concurrent
`residue_b2` and `ifc` streams: 6 drifted files), so the plugin bundle
drifted; the project's sanctioned regeneration `python tools/sync_plugin.py`
was run (the standing rule: sync after every `src/rvt` change) — it re-
mirrored `src/rvt` into `plugin/lib/` and rebuilt `rev-revit.zip` (GENERATED
artifacts, no hand edits; NOTE it bundled the concurrent streams' modules at
their current on-disk state — the sync is idempotent, re-run it at the end
if they change further), after which `tests/test_plugin_sync.py` → 2 passed;
(b)+(c) `tests/test_provenance.py::test_G0_resource_refs_are_counted` and
`::test_G0_identity_dit_usernames_still_leak` — the pre-existing, other-
stream STALE assertions every recent record lists (they pin the pre-genesis-2
G0's defects; owner: the provenance stream); neither touches this stream's
files.  Net after the sync: **1,167 pass / 2 known-stale**.  A provenance
ledger v2 of ZC_deep is filed (`residue_a2/ZC_deep_provenance.json`); its
element classifier counts every in-place row as sample-derived by
construction and `Global/Latest` stays the sample's byte for byte by design
(the container layer = the counsel / own-save item), so for this programme
the per-rung landed / residue accounting (this record's censuses) is the
authority (endgame §7).
STOPPED AT READY — the seven files + control await the orchestrator's viewer
batch (`tools/probe_batch.py stage experiments/genesis/subst_k4/residue_a2/
ZC_{deep,hvac,elec,conduit,systype,analysis,browse}.rvt --control-from
experiments/genesis/subst_k4/residue_a/ZA_deep.rvt`); read the control first,
then ZC_deep; the singles only on a ZC_deep FAIL.  The four not-in-place-able
elements (link pair, DataStorage, the room's topology) and the other streams'
queues are the recorded remaining work; the ZAB + ZC composition on this base
is the assembly stream's next input.
