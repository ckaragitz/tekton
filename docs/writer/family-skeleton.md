# FAMILY SKELETON — the from-scratch scaffolding of a Revit family document

Stream: **family-skeleton** (2026-08-03). Code: `src/rvt/famgen/skeleton.py`
(constructors + the `FamilyDoc` builder + the two delivery forms), tests
`tests/test_famgen_skeleton.py` (14 pass), record
`docs/inbox/family-skeleton.md`, artefacts
`experiments/families/genesis/S0_empty_family.rfa` (skeleton only) and
`S0_electrical_family.rfa` (electrical variant). Companion:
`docs/writer/family-authoring.md` (the reconnaissance this map is built on)
and `docs/writer/genesis-skeleton.md` (the PROJECT skeleton whose building
blocks are reused). Claim tags: **VERIFIED** (byte-exact reconstruction of
a real specimen record from parameter values, or an invariant checked across
the specimen set), **INFERRED** (consistent with all evidence, not proven),
**UNKNOWN** (settled only by a Revit / family-editor open test).

Product sentence served: *"build me an Eaton panel with X and Y"* — the
platform must CREATE the family (the asset), not only place it. This stream
delivers the FAMILY DOCUMENT everything else is authored into; the geometry
(solid forms / profile sketches) is the next stream's territory.

---

## 0. The headline: the family skeleton is constructible from scratch

Every skeleton class is built FIELD BY FIELD from plain parameters (no
`.rfa` opened as a template, no cloned payload — `rvt.genesis.types.
blank_object` supplies the pure-schema default and the constructor overlays
the values). Feeding a constructor the specimen's own parameter values
reproduces the **original record bytes** of the real element, adler32 stamp
included:

| object | class | specimen(s) | bytes (obj / hdr / rep) | byte-exact |
|---|---|---|---:|:--:|
| Reference Level "Ref. Level" | `Level` | .rfa 21 | 788 / 175 / 22 | ✓ / ✓ / ✓ |
| level type "Level 1" | `LevelAttributes` | .rfa 18, rme 786447, rac 1072206 | 247 / 191 / 22 | 9/9 ✓ |
| origin plane "Center (Front/Back)" (refName 4) | `RefPlane` | rme 786474 | 816 / 151 / 22 | ✓ / ✓ / ✓ |
| origin plane "Center (Left/Right)" (refName 1) | `RefPlane` | rme 786476 | 816 / 151 / 22 | ✓ / ✓ / ✓ |
| named plane "Front" (refName 7), "Left" (0) | `RefPlane` | rme 786475, .rfa 48 | 788·786 / 151 / 22 | ✓ / ✓ / ✓ |
| family parameter Height / Width / Length | `ParamElemFamily` | .rfa 4208 / 4209 / 4253 | 456·454 / 143 / 22 | 9/9 ✓ |
| power connector, 3-pole 208 V (panelboard) | `ConnectorElem` | rme 786876 | 908 / 159 / 22 | ✓ / ✓ / ✓ |
| power connector 120 V, param-driven (light) | `ConnectorElem` | rme 773363 | 992 / 167 / 22 | ✓ / ✓ / ✓ |
| power connector 120 V, param-driven (receptacle) | `ConnectorElem` | rme 847095 | 960 / 175 / 22 | ✓ / ✓ / ✓ |
| the SELF-Family (4 types, 6 params, 1,881-entry index, dim exprs) | `Family` | .rfa 17 | 26,535 / 15,199 / 22 | ✓ / ✓ / ✓ |

45 records byte-exact in the harness. The remaining specimen deltas on the
other documents are per-family VALUES (Autodesk's authoring `m_path`, a
lighting family's `m_lightSourceDefBits`, floating-point drift in plane
axes) — enumerated in §9, never layout.

Both from-scratch documents (S0, S0e) encode → decode → re-encode
byte-stable (63 / 75 records), form CLOSED graphs (every referenced id is an
element of the document), emit as standalone `.rfa` containers that read
back clean and validate with **0 errors** in family mode.

---

## 1. The specimen set

Eight family documents across categories — the `.rfa` and the embedded
documents (save units) of the sample projects:

| doc | category | records | notes |
|---|---|---:|---|
| `racbasicsamplefamily-2026.rfa` unit 0 | Furniture (-2000080) | 1,992 | standalone; types INSIDE the doc |
| rme unit 243 "…Panelboard - 208V MLO" | Electrical Equipment (-2001040) | 551 | face-hosted, 1 connector, part type 14 |
| rme unit 149 "…Dry Type Transformer - NEMA 3R" | Electrical Equipment | 548 | 1 connector |
| rme unit 271 "M_Plain Recessed Lighting Fixture" | Lighting Fixtures (-2001120) | 605 | ImposterLight, param-driven connector |
| rme unit 119 "M_Duplex Receptacle" | Electrical Fixtures (-2001060) | 621 | param-driven connector |
| rac unit 120 "White Porcelain Plate" | Generic Models (-2000151) | 594 | NO geometry (2D symbols only) |
| rac unit 157 "Side Table 2 (2)" | Furniture | 650 | metric datum (98.4 ft line) |
| rac unit 126 "fire place hang" | Generic Models | 725 | |

Intersecting their class histograms: **64 classes are present in ALL
eight** (`GStyleElem` 84–1477, `CategoryElem` 70–94, `FontElem`, 19–31
`DBViewType`s, sketch planes / grids / dimensions, load natures, 4
`DBViewSection` elevations, 2 `DBViewPlan`s, 1 `DBViewProject`, 1 `Level`
+ 1 `LevelAttributes`, `RefPlane` ≥ 8, `ParamElemFamily` ≥ 3, 2
`BrowserOrganization`, `UnitsElem`, `TrueNorth`, `SunAndShadowSettings`, …).
That population is the **family TEMPLATE's ballast** (a family template
`.rft` is itself an old document: fonts, dimension styles, arrowheads,
nested section-head annotation families, load natures) — exactly analogous
to the ~3,000 template elements of a project. As with the project skeleton,
we do **not** clone the ballast; we build the load-bearing subset and put
the rest to the reduction ladder (§10).

## 2. The skeleton classes (built) vs. the ballast (not built)

| built by `famgen.skeleton` | class | constructor |
|---|---|---|
| the document's own family | `Family` (self) | `new_self_family` |
| Reference Level + its type | `Level` "Ref. Level", `LevelAttributes` "Level 1" | `new_family_level`, `new_family_level_type` |
| origin reference planes + authored planes | `RefPlane` | `new_center_reference_planes`, `new_reference_plane` / `FamilyDoc.add_reference_plane` |
| family parameters | `ParamElemFamily` (+ the FamilyTypeTable / FamilyParams value shape) | `new_family_parameter`, `family_param_value`, `family_type_table` |
| the units registry | `UnitsElem` | `rvt.genesis.skeleton.new_units_elem` (reused) |
| the plan-view constellation the datums are drawn in | `DBViewProject`, `DBViewType` 'Floor Plan', `DBViewPlan` "Ref. Level" + Viewer / DBDrawing / Viewport / ExtentElem / SketchPlane / SunAndShadowSettings | `rvt.genesis.skeleton` view constructors (reused verbatim, re-owned by the self-Family) |
| MEP: power connector + electrical domain | `ConnectorElem` + `ConnectorElemDomainElectrical` (+ `FamilyParametrizedElemParamsCell`) | `new_electrical_connector`, `electrical_domain`, `phase_loads_va`, `FamilyDoc.add_electrical_connector` |
| the doc's own load classification | `ElectricalLoadClassification` | `rvt.genesis.types.new_load_class` (reused) via `FamilyDoc.add_load_classification` |

| NOT built (ballast — reduction ladder, §10) | why |
|---|---|
| 70–94 `CategoryElem` + 84–1,477 `GStyleElem` (object-style copies) | the family's private copy of the object-styles registry; S0 references categories by built-in id only |
| fonts, dimension/leader/text/spot styles, arrowheads, fill patterns | annotation ballast; `rvt.genesis.types` has constructors when needed |
| ceiling plan, 4 elevations (`DBViewSection`), 3D view, drafting views | further views; the S0 constellation is the 1-plan reduction |
| load natures / load cases (`LoadNatureElem`/`LoadCaseElem` × 8) | structural template ballast |
| nested annotation families (`FamilySurrogate`/`FamSymSurrogate`/`FamilySymbol`, section heads) | Autodesk annotation content — never carried |
| sketch grids, browser organisations, export settings singletons | template ballast |

---

## 3. `Family` — the SELF-Family [VERIFIED byte-exact, .rfa 17]

The one `Family` element every other element's `m_famId` points at; a
nested family is a *further* `Family` element (with its own document GUID)
— the self-Family has an all-zero `m_famDocGUID` and a null `m_oFamDoc`
(it IS the document). 26,535 bytes on the `.rfa`. Load-bearing fields
(`new_self_family(elem_id, category_id, ...)`, all others are the
`DEFAULT_FAMILY_FLAGS` / blank-schema defaults):

| field | meaning | value / source | tag |
|---|---|---|---|
| `m_categoryId` | the family CATEGORY (built-in OST id) | ctor `category_id` | V |
| `m_pFamilyTypes` | `FamilyTypeTable{ m_idx = current type, m_pairs[] = { name, params:{ m_params[], m_geomRefHandles } } }` — **all TYPES of a standalone family live here**; an embedded document has `m_idx = -1`, `m_pairs = []` (types are HOST-side `FamilySymbol`s) | `types` / `FamilyDoc.add_type` | V (both forms) |
| `m_familyParams` | `FamilyParams{ m_params[], m_geomRefHandles }` = the CURRENT type's values (== `m_pairs[m_idx].params`) | derived in `FamilyDoc.finalize` | V |
| param value entry (`FamilyParamValue`) | `{ m_str, m_oExpression, m_value (double), m_elemId (ElementId-valued params, e.g. materials), m_paramId (BIP < 0 or ParamElemFamily id > 0), m_int (enum / yes-no), m_instance, m_reporting }` | `family_param_value` | V |
| `m_cellList` | ONE `FamilyParamsOrderCell{ m_sortedParams[]: { m_groupTypeId (Forge group id), m_paramIds[] } }` — the properties-palette group ordering | `param_groups` / `finalize` | V |
| `m_familyIds` | `ElementIdIndexPairSet{ m_data[]: { m_elementId, m_index } }` — EVERY element of the document → a monotonic "absorbed" index; `m_nextAbsorbedIndex` = max index + 1 (3170 on the .rfa) | `element_ids` (+ `element_index` for exact reproduction) | V |
| `m_lockedParameterIdsForDirectManipulation` | length params (+ cost / offset BIPs) Revit locks against direct manipulation | `locked_param_ids`; default = the SPEC_LENGTH params | V shape / I default |
| `m_famCatalogKeys` | 5 empty `AStringWrapper`s (type-catalog keys) | `cat_keys` | V |
| `m_oFamDimConstrMgr` | `FamDimConstrMgrImpl{ m_pFam→self, m_paramExprs[] (param↔labelled-dimension expressions), m_drivenDimSegs, m_lockedDimSegs, m_eqDimSegs, m_reportingDimSegs, m_ignoredDimValueExprs }` — empty for a document without labelled dimensions | `dim_constr_mgr` (blank by default) | V shape |
| `m_partType` | 0 normal (furniture / generic / lighting), 14 panelboard [names I: 15 transformer, 16 switchboard] | `part_type` | V values |
| `m_isWorkPlaneBased`, ~85 more `m_b*` / `m_is*` / `m_e*` flags & enums | behaviour: `DEFAULT_FAMILY_FLAGS` (the shared specimen values; e.g. `m_eBraceRepType 1`, `m_eStructMaterialType 4`, `m_bUsePreCutShape True`, `m_isUserCreated True`) | ctor `overrides` for the per-family ones | V shared / per-family values in §9 |
| `m_appVersionAtLoad` / `AtInitialLoad` | -2 on native 2026 documents (2134 on 2009-era content) | `app_version_at_load` | V values / I meaning |
| `m_name` | '' in a standalone `.rfa` (the family NAME is the file name / PartAtom title) | | V |
| `m_path` | Autodesk stores the authoring file path (`C:\…\Panelboard\`) — **OURS ''** (an identity leak we want gone) | | V |
| `m_designOptionId` | **-1 on the self-Family** (every OTHER family-doc element carries **-4**, see §8) | | V |
| header (seq 101) | category -1, flags 26, `m_deletion` = EVERY element of the document + self (the family owns its elements: 313 ids on the panelboard) | `finalize` seeds it | V |
| seq 103 | `SerializedDummy` | | V |

## 4. The Reference Level [VERIFIED byte-exact, .rfa 21]

`new_family_level(elem_id, self_family_id, level_type_id, gen_view_id=…)`.
Exactly ONE `Level` per family document, named **"Ref. Level"**, elevation
0. Structure = the project skeleton's `Level` (`DatumPlaneGeomStep` +
inline `Face`/`Plane`, pointer archive indices 3/4/5) with the family
deltas:

| field | family doc | project (for contrast) | tag |
|---|---|---|---|
| `m_famId` | the self-Family | -1 | V |
| `m_designOptionId` | **-4** | -1 | V |
| `m_pParamValueSetInt` | PRESENT, **empty** | `[(-1007112, 1)]` (LEVEL_IS_STRUCTURAL) | V |
| `DatumPlaneGeomStep.m_flags` | **0** | 1 | V |
| `m_isBuildingStory` | True | template-dependent | V |
| datum line | `m_freeEnd (0,0,0)` → `m_bubbleEnd (30,0,0)` imperial (98.4 ft = 30 m metric) | | V |
| `m_sheetTextHeight` | 0.015625 (3/16 in) imperial / 0.05126 metric | | V |
| `m_v2Datum` | False (True only on ancient content, rac side table) | | V |
| header | category -2000240, flags 2058 (2074 .rfa / 10 old plate), vvf -4225, deletion [self-Family, level type, self], regenOnly [the plan view], appearance [level type, plan view] | | V |

`new_family_level_type` = `LevelAttributes` **"Level 1"** (the type of the
Ref. Level): `m_bRoomComputationHeightAutomatic` **True** with height 0
(projects: False + 4 ft) [V]; params `-1008002 = 0`, `-1008001 = 1`;
header regenOnly `[-1007109]` (a built-in parameter id as regen parent
[V id, I name]); deletion = self-Family + line category + its GStyle +
leader category + font + head-symbol + self. In the templates those five
references point at object-style copies + a nested "Level Head" annotation
family — **-1 in genesis** (the head symbol is Autodesk content; -1 =
'Symbol: <none>' [UNKNOWN whether the editor tolerates the unset head]).

## 5. Reference planes [VERIFIED byte-exact, 5 specimens]

`new_reference_plane(elem_id, self_family_id, name, ref_name, free_end,
bubble_end, normal, gen_view_id, extent, defines_origin, locked, ...)`. A
`RefPlane` is a `Level`-shaped datum (same GeomStep / Face / Plane / datum
line) + the reference tail:

| field | meaning | tag |
|---|---|---|
| plane frame | X = unit(free→bubble), Y = `normal`, origin = line midpoint (per-plane drift on old planes); `m_cutVec` = X × Y (the sketching view direction) | V |
| `m_refName` | the **"Is Reference"** role: 0 Left, 1 Center (Left/Right), 2 Right, 3 Front, 4 Center (Front/Back), 5 Back, 6 Bottom, 7 Center (Elevation), 8 Top, 12 Not a Reference, 13 Strong, 14 Weak | V values (0–5, 7, 12, 14 observed) / I names 6, 8, 13 |
| `m_definesOrigin` | the plane pins the family origin (True on the two centre planes + the templates' Left/Front helpers) | V |
| `m_genDbViewId` + header deletion | the PLAN VIEW the plane was drawn in — every specimen plane has one and lists it as a deletion parent ⇒ **a reference plane requires a view** | V |
| `m_cellList` | `[SketchMembership{ m_groupId -1 }, PatternHelper]` (an old .rfa plane omits the SketchMembership: `sketch_member=False`) | V |
| `DatumPlaneGeomStep.m_flags` | 0 | V |
| `m_sheetTextHeight` | 0.0078125 (3/32 in) | V |
| `m_locked` | True on the two origin centre planes | V |
| `m_subcategoryId` | -1 (or a subcategory `CategoryElem`) | V |
| header | category -2000530, flags 2058, deletion [self-Family, self, gen view (+ subcategory)] | V |

**The origin trio** every family document carries (`new_center_reference_
planes` + the Ref. Level): "Center (Front/Back)" (refName 4, the XZ
plane, line along +X), "Center (Left/Right)" (refName 1, the YZ plane,
line along +Y), both `m_definesOrigin` + `m_locked`, and the Ref. Level
(horizontal). Their intersection = the family INSERTION POINT / origin
(`new_family_document(origin=…)`).

## 6. Family parameters [VERIFIED byte-exact, .rfa 4208/4209/4253]

`new_family_parameter(elem_id, self_family_id, name, spec_type_id,
group_type_id, family_guid, ...)` = one `ParamElemFamily`:

| field | value | tag |
|---|---|---|
| `m_pParamDef` | `ParamDefValue{ m_caption = the name, m_typeId = "revit.local.family:<32-hex guid><%08x elem id>-1.0.0", m_paramElemId, m_specTypeId = Forge spec (`autodesk.spec.aec:length-1.0.0`, `…electrical:potential-1.0.0` …), m_groupTypeId = Forge group (`autodesk.parameter.group:dimensions-1.0.0` …), m_restriction 1, m_userVisible True, m_boundless False }` (a material-valued parameter uses `ParamDefMaterialBrowse` instead — `m_unassignedString`, `m_extraButtonFlag -1`, `m_includeParams`) | V |
| the 32-hex guid | a per-creation-session GUID shared by parameters created together (4208/4209 share one, 4253 has another) — OURS is a fresh uuid4 per family | V structure / I meaning |
| `m_instanceParam` | False = TYPE parameter, True = instance | V |
| VALUES | not on the element: in the self-Family's `FamilyTypeTable` rows keyed by this element id (positive `m_paramId`) | V |
| header | category -1, flags 8218, deletion [self-Family, self] | V |

**Built-in TYPE parameters (product data)** ride in the same type rows as
BIP entries: `-1010104 Manufacturer`, `-1010103 Model`, `-1010109
Description`, `-1010108 URL`, `-1010105 Type Comments` (AString via
`m_str`), `-1001205 cost` (double) [ids V in the .rfa's identityData
ordering group; names I]. `FamilyDoc.add_type(name, {…, 'manufacturer':
'…', 'model': '…'})` writes them — this is where a manufacturer's FACTS
(catalog number, rating text) attach to OUR family. Electrical / lighting
built-ins observed on the specimens: `-1140004` wattage (64 W → 688.89
internal), `-1150107` initial colour temperature, `-1010503` apparent
load — internal electrical units = display ÷ 0.3048² [V unit rule].

## 7. The electrical connector [VERIFIED byte-exact, 3 specimens]

`new_electrical_connector(elem_id, self_family_id, host_element_id,
host_geom_tag, location, direction, u_axis, voltage_v, poles,
load_class_id, apparent_load_va, power_factor, param_bindings, ...)`:

| field | meaning | tag |
|---|---|---|
| `m_oPlaneRef` | `GeomOnPlaneRef{ m_geomRef → the HOST FACE (element id + m_geomTag, e.g. tag 2 = the top face of an extrusion), m_offset (UV on the face), m_angle, m_flip }` — a connector is a frame ON A FACE | V |
| `m_pFaceU` / `m_pFaceV` | two inline `Face`/`Plane`s at the connector point: U = (direction, u_axis), V = (u_axis, direction × u_axis); envelope = `m_grepSize` (the drawn arrow size, 0.492 ft = 150 mm) | V |
| `m_oEdgeLoopRef` | `EdgeLoopRef{ m_sortedTagArr = the host face's edge tags }` ([3,4,8,17] on a box top; empty for a datum host) | V |
| `m_geomSteps` | one `ConnectorElemGStep` (face history keys `[6,0,-1]`/`[6,1,-1]`, flags 237373); GeomTable rows `(-1, 1, 1)` | V |
| `m_pDomain` → `ConnectorElemDomainElectrical` | `m_dVoltage` (V ÷ 0.3048²: 208 V → 2238.89, 120 V → 1291.67), `m_dApparentLoadPhase1..3` + `m_dApparentLoad` (VA ÷ 0.3048²; **load law below**), `m_dPowerFactor`, `m_nNumberOfPoles` (1 / 2 / 3), `m_idLoadClassification` (an `ElectricalLoadClassification` — the DOC'S OWN copy in a standalone family; a HOST id in an embedded doc), `m_systemType` (30 = Power‑Balanced / **31 = Power‑Unbalanced**, the specimens' value [V] — API `ElectricalSystemType`), `m_powerFactorState` 1 = Lagging (API `PowerFactorStateType`), `m_bIsConnectorPrimary` (**one primary per family**, law below), `m_strConnectorDescription` | V |
| `m_cellList` (**parameter association**) | `FamilyParametrizedElemParamsCell{ m_paramDrivenData[]: { m_famParamId (a ParamElemFamily id or a BIP), m_elemPropId, m_geomTag -1, m_bIsSymbol False } }` + `PatternHelper` — the family editor's "associate family parameter": `m_elemPropId -1140002` = the connector VOLTAGE, `-1140005` = APPARENT LOAD; e.g. the receptacle's voltage is driven by its 'Switch Voltage' user parameter and its load by 'Load'; the light's load by the wattage BIP `-1140004` | V |
| header | category -2007000, flags 2058, deletion [self-Family, host face element, load classification, the driving user params, self] | V |
| seq 103 | `SerializedDummy` (connectors carry no cached geometry) | V |

**Load + primary law of the electrical domain (#164)** — sourced from
Autodesk's *public* API reference and product help (no install directory,
no sample bytes), consistent with the three byte‑verified specimens:

| rule | in the file | source (short quote) |
|---|---|---|
| system type codes | `m_systemType` 30 = Power‑Balanced, 31 = Power‑Unbalanced (6 = PowerCircuit is a *circuit's* type). Every specimen — Revit's own panelboard / fixture / receptacle connector — is **31** [V]; the factory emits 31 only. | Revit API `ElectricalSystemType` enumeration ("all the possible electrical system types for a connector object"): `PowerBalanced 30`, `PowerUnBalanced 31`, `PowerCircuit 6` — <https://www.revitapidocs.com/2026/90f62108-9cd1-a66a-a123-8372307f4e7f.htm> |
| unbalanced (31): load lives per phase | `m_dApparentLoadPhase1..poles` carry the load; a connector's *whole* load is split equally over its poles (`phase_loads_va`: 75 kVA, 3‑pole → 25 / 25 / 25 kVA = 269 097.76 internal each); an explicit per‑phase list is written as given; phases beyond `poles` are 0; `m_dApparentLoad` = **0.0** [V on all specimens] | Help *Connector Properties*: "Apparent Load Phase 1 … Active only when Balanced Load is False and System Type is Power"; Phase 2 "… and Number of Poles >1"; Phase 3 "… >2"; "Apparent Load … Active only when Balanced Load is True" — <https://help.autodesk.com/cloudhelp/2020/ENU/Revit-Model/files/GUID-3DE410FC-7BB7-44FD-B75E-A02C4F42C1AD.htm>. Total = "Apparent Load Phase A + Apparent Load Phase B + Apparent Load Phase C" — help *About Load Calculations* <https://help.autodesk.com/view/RVT/2025/ENU/?guid=GUID-EE3F38E5-44A7-4991-BA99-7AC8732DBEDF> |
| balanced (30): load lives in `m_dApparentLoad` | `m_dApparentLoad` = the total; the phase fields are written as its equal split so both readings agree. **No type‑30 specimen has been decoded** — the semantics are documented, the on‑disk value of the inactive phase fields is UNOBSERVED; exposed as `system_type='power_balanced'`, not used by the factory. | same help page ("Apparent Load … Active only when Balanced Load is True and System Type is Power"); API `ElectricalSystem.ApparentLoadPhaseA/B/C` — "This property only available when System Type is Power!" <https://www.revitapidocs.com/2023/35b66d8e-eafe-f6ba-1d11-4bcac26c2ea8.htm> |
| one primary connector per family | `m_bIsConnectorPrimary` True on exactly one electrical connector; `factory.add_connector` marks the document's first connector primary and refuses a second; transformer: primary winding True, secondary False | Help *Connector Properties*: "A single connector of each discipline is allowed to be primary in each family. The family's electrical data that displays in a schedule is derived from the primary connector"; API `ConnectorElement.IsPrimary` — "Identifies if this is the primary connector in the family" <https://www.revitapidocs.com/2022/92a0eddf-2414-903f-8872-898442426ded.htm>; `ConnectorElement.AssignAsPrimary` — "promote this connector as primary, and the rest of connectors in this system will be assigned as secondary" <https://www.revitapidocs.com/2022/c6c21445-5e95-e15b-743d-f8fdfb369e79.htm> |
| power factor state | `m_powerFactorState` 1 = Lagging (0 = Leading) [V 1 on all specimens] | API `PowerFactorStateType`: `Lagging 1`, `Leading 0` — <https://www.revitapidocs.com/2026/bb418213-600f-ca37-e1a0-a09df497ecac.htm> |

None of this is a "loads in Revit" claim: the values are what the format
and Autodesk's documentation say a reader shows; certification stays with
the viewer ledger (rule 4).

`FamilyDoc.add_electrical_connector(voltage=208, poles=3, apparent_load_va=
…, power_factor=…, load_class='Power', bind_voltage_param='Panel
Voltage', bind_load_param='Apparent Load')` builds the connector FROM THE
CALC-ENGINE VALUES (`rvt.electrical`) and associates it to the type
parameters (only the document's first connector is primary). `host_element_id`/`host_geom_tag` name the face; **when the
document has no solid yet (S0e) the connector references the Ref. Level
datum face — UNKNOWN acceptance** (every real connector sits on a solid
face; the solid is the geometry stream's job — the connector's face host is
the one field that stream must re-point).

## 8. Document-wide constants [VERIFIED]

| constant | value | tag |
|---|---|---|
| object `m_designOptionId` of every family-doc element | **-4** (headers keep -1); the self-Family alone is -1 | V (the family "main model" sentinel [I]) |
| `m_famId` of every element | the self-Family id (`Element.m_famId`); header `m_familyId` likewise | V |
| ids | file-wide unique; a family document is a **closed graph** — every reference stays inside the document except category / style / parameter copies (self-contained in a standalone `.rfa`, mapped from the host via `big2SmallMap` when embedded) | V |
| seq-103 rep of skeleton elements | `SerializedDummy` (2 bytes, stamp `0x0069003C`) | V |
| record stamp | `adler32(u16 class_id + object bytes)`; sentinel stamp 1 | V |

## 9. Per-family VALUES (parameters of the constructors, not layout)

The byte-exact reconstructions used the specimen's own values for
these; a genesis family sets them from its own facts:

| field | varies per family | genesis default |
|---|---|---|
| self-Family `m_omniClassCode` / `m_seekItemId` | Autodesk taxonomy / catalog ids (`23.40.20.14.17`, `Table-End-0000-CAN-ENU`) | **''** (no Autodesk taxonomy — content policy) |
| `m_path` | Autodesk's authoring path | **''** |
| `m_eRenderModelType` (0/3), `m_isVertical`, `m_bIsSavable`, `m_bShared`, `m_enableCuttingInViews`, `m_elevationFixed` | family behaviour choices | `DEFAULT_FAMILY_FLAGS` (`overrides={…}`) |
| `m_defaultHostThickness` / `m_defaultHeightAboveLevel` | 0.0 or the `-1e30` "no default" sentinel | 0.0 |
| `m_lightSourceDefBits` (132), `m_eProteinRenderType` | lighting families with a light source | 0 |
| Level `m_v2Datum`, plane axis drift, sheet text heights | template lineage / units | imperial defaults |

## 10. Delivery form 1 — the standalone `.rfa` [S0 / S0e BUILT, VALIDATED]

`FamilyDoc.to_rfa(path)` (`emit_family_rfa`). An `.rfa` = the project
container with ONE save unit (`docs/writer/family-authoring.md` §2):

| stream | source | tag |
|---|---|---|
| `Partitions/<N>` | **OURS end to end** (`build_partition_stream`): 18-byte header (u64 9, u16 0x3a3, i32 0, u32 elem_table_count) + one block run per seq (whole records, flags 4, our gzip, A/B/C computed) + the 18-byte unit terminator + `0x0f3f` footer blob + the format's UTF-16 'Data generated by …' magic + the end record; N = DIT record count − 1 (**`Partitions/0`** for our one-episode document) [V relation on the projects; the N a reader expects for a family is I] | V framing |
| `Global/ElemTable`, `History`, `DocumentIncrementTable`, `PartitionTable`, `ContentDocuments` (empty), `Contents`, `BasicFileInfo` | **OURS**: `rvt.genesis.skeleton.minimal_globals` — ONE save episode, the cross-stream invariants by construction (History 1 == DIT 1 == BFI increments 1; DIT id_pair (0,1); BFI GUID == History[0]; author `rvt-writer`), real CRCIO ECC via `rvt.ecc` | V invariants |
| `PartAtom` | **OURS**: plain Atom XML in the partatom namespace — title = the family name, our category label, OUR product name, the type list; no Autodesk taxonomy terms / OmniClass (`build_part_atom`); UNFRAMED | V |
| `TransmissionData` | **OURS** (no external references) | V |
| `Formats/Latest` | the per-release schema — a FORMAT CONSTANT (byte-identical in every 2026 file) carried from the donor container | V constant |
| `Global/Latest` | the serialized **ADocument** — **NO ENCODER EXISTS** (TRACKER gate **G1a**, the same open gate as the project genesis stream); carried from the donor `.rfa`, so it references the donor's element ids (dangling in S0, exactly as G0's Global/Latest does) | **OPEN GATE** |
| unit footer blob (64 B) + stream end record (92 B) | opaque format bytes from the donor [U semantics; V15/V20 proved the reader accepts foreign / re-blocked content beside them] | U |
| container | our CFB writer (`rvt.cfb_writer`) | V |

**S0** (`build_s0`) = the skeleton only: self-Family, Ref. Level +
LevelAttributes, the two centre planes, UnitsElem, the 1-plan view
constellation, Length/Width/Height parameters, ONE type ('Standard': 600 ×
300 × 150 mm + description / manufacturer / model text) — 21 elements, NO
geometry. **S0e** (`build_s0e_electrical`) adds the electrical machinery:
a panelboard-part-type family with Panel Voltage / Apparent Load / W / H /
D parameters, the doc's own load classification and ONE 3-pole 208 V
power connector associated to the type's voltage/load parameters — 25
elements. Both:

* self-verify green (`verify_family_rfa`: 0 gzip CRC failures, 0 ECC
  mismatches, walker clean, 22 / 26 records per seq (elements + sentinel),
  21 / 25 clean seq-102 decodes, identical id sets across the 3 seqs);
* `validate_family` (family mode) → **VALID, 0 errors, 0 warnings**
  (360 / 400+ references checked). Under the raw PROJECT-calibrated
  validator the only findings are the three **family-file-shape gaps**
  (§11) — a strict subset of the FIVE the untouched Autodesk `.rfa` itself
  shows (whose ElemTable / DIT additionally fail our decoders; OURS decode).

Reproduce: `.venv/bin/python -m rvt.famgen.skeleton` (writes S0 + S0e +
`*_validate.json`); `.venv/bin/python -m pytest tests/test_famgen_skeleton.py -q`.

## 11. Delivery form 2 — the embedded save unit [SPEC + BYTES]

`FamilyDoc.to_embedded_unit()` (`build_embedded_unit`) returns the pieces
+ the loader CONTRACT (the project-side loader — forge stream — owns the
insertion; this stream supplies the document):

| piece | content | tag |
|---|---|---|
| `separator` | 28 bytes: u16 0x3a3, i32 -1, u16 0x3a2, u32 record_count, 16-byte GUID (= `content_doc_guid` = the ContentDocuments key = the host Family's `m_oFamDoc.m_contentDocGUID`) | V framing |
| `segments` | per-seq record bytes (sentinels included) of the unit; the loader RE-IDs every element into the host id space (ids are file-wide unique) and re-blocks | V |
| `content_documents_entry` | the entry grammar the loader writes: u32 lead + `a3 03 ff ff ff ff a2 03 ff ff ff ff` (null lead pointers) + GUID + u32 adoc_len + the document's serialized **ADocument** (inline ElemTable 0x5c9 + History 0x538) — the ADocument encoder is the open gate (G1a), so the entry is SPECIFIED, not built | V grammar / gate |
| `host_side` | host `Family{ m_oFamDoc{ m_contentDocGUID, m_big2SmallMap2 }, m_pFamilyTypes (types are HOST-side in a project) }` + one `FamilySymbol` per type + ElemRecs + the save bookkeeping (mutation-plan §7) | V structure |

The clean API for the forge stream: `unit = doc.to_embedded_unit()` →
`unit['separator']`, `unit['segments']`, `unit['content_doc_guid']`,
`unit['record_count']`, `unit['type_names']`, `unit['content_documents_
entry']`, `unit['host_side']`.

## 12. Confidence / unknowns (ranked open questions)

| # | question | how settled |
|---|---|---|
| 1 | Does the family editor OPEN a document with only the S0 constellation (1 plan view; no object-style copies, no fonts, no elevations, no nested annotation families)? | Revit / APS open test of `S0_empty_family.rfa` — the family analogue of the project skeleton's R-ladder |
| 2 | Does a foreign `Global/Latest` (the donor .rfa's ADocument) block the open? | same open test; retiring it = the ADocument encoder (**G1a**, the biggest shared block) |
| 3 | `Partitions/0` — does the reader require the N of the family templates (69 in 2026)? | open test; the parameter is trivially adjustable (`_partition_stream_name`) |
| 4 | A power connector referenced to a DATUM plane (S0e) instead of a solid face | open test after the geometry stream re-points it at a real face |
| 5 | `LevelAttributes` with -1 line/leader category, font and head-symbol | open test |
| 6 | RefPlane `m_refName` names for codes 6 / 8 / 13; `m_restriction 1`; `m_powerFactorState 1`; `-1007109` name | inferred; cosmetic |
| 7 | Hosted families (`host='wall'/'ceiling'/'face'`): the host placeholder + host-face geometry ref (`m_oHostFaceGeomRef`, work-plane-based flag) | not built — recorded as a spec note; the panelboard specimen (face-hosted, work-plane-based) is the reference |

## 13. Proposed core diff (outside this stream's territory)

`src/rvt/validate.py` is project-calibrated; `famgen.skeleton.validate_
family` applies family mode at runtime (PartAtom unframed; ProjectInform
ation not required) and S0/S0e are VALID under it. To make
`tools/rvt_validate.py` itself report 0 errors on `.rfa` files, apply
(6 lines, `_layer_structure`):

```
-        for req in REQUIRED_STREAMS:
+        is_family = "PartAtom" in names            # .rfa: PartAtom replaces ProjectInformation
+        required = tuple(s for s in REQUIRED_STREAMS
+                         if not (is_family and s == "ProjectInformation"))
+        for req in required:
             if req not in names:
```
plus `UNFRAMED_STREAMS = frozenset({..., "PartAtom"})` (plain Atom XML,
never CRCIO-framed). With it, S0 / S0e validate 0 errors and the Autodesk
`.rfa`'s remaining findings drop to its ElemTable/DIT decode gaps (KNOWN,
`docs/inbox/families.md` §4).
