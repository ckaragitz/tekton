# MEP class map — IFC4 entity ↔ Revit category, for our electrical domain

Two tables and one rule.

- **Forward map (§2):** for each thing we model, the best IFC4 entity +
  `PredefinedType`, the Revit category it *imports* into via Link IFC, the
  standard property sets, and the gotchas.
- **Reverse map (§4):** what Autodesk's own *exporter* emits for each Revit
  category, so our IFC looks like Revit-authored IFC (round-trip parity).
- **Rule:** the Revit category is decided **at authoring time by the IFC
  class** (plus `PredefinedType`/`ObjectType` in a few cases). If an element
  lands in *Generic Models*, the class was wrong or unmapped — fix the tag and
  re-export; never re-categorise inside Revit (lost on next reload).

Evidence tags: **[src]** = Autodesk open-source Link-IFC importer
`Utility/IFCCategoryUtil.cs` (built-in entity→category map, verified by
reading the code, commit `f534ad1`); **[ifc4]** = buildingSMART IFC4 (ADD2)
schema; **[pset]** = Autodesk's shipped `IFC Shared Parameters-RevitIFCBuiltIn_ALL.txt`
(the exporter's own pset definitions); **[unverified]** = flagged.

---

## TL;DR (what to put in `userData.ifc.ifcClass` for each object)

| Object | `ifcClass` | `predefinedType` | Lands in Revit category |
|---|---|---|---|
| Panelboard | `IfcElectricDistributionBoard` | `DISTRIBUTIONBOARD` | Electrical Equipment |
| Switchboard / switchgear | `IfcElectricDistributionBoard` | `SWITCHBOARD` | Electrical Equipment |
| MCC | `IfcElectricDistributionBoard` | `MOTORCONTROLCENTRE` | Electrical Equipment |
| Transformer (dry-type / distribution) | `IfcTransformer` | `VOLTAGE` | Electrical Equipment |
| Light fixture (troffer, high-bay, exit) | `IfcLightFixture` | `POINTSOURCE` / `DIRECTIONSOURCE` / `SECURITYLIGHTING` | Lighting Fixtures |
| Receptacle | `IfcOutlet` (+ `IfcOutletType`) | `POWEROUTLET` | Electrical Fixtures |
| Data / AV outlet | `IfcOutlet` | `COMMUNICATIONSOUTLET` / `AUDIOVISUALOUTLET` | Data Devices |
| Junction / pull box | `IfcJunctionBox` | `POWER` (or `DATA`) | Electrical Fixtures |
| Light switch, disconnect switch | `IfcSwitchingDevice` | `TOGGLESWITCH` / `SWITCHDISCONNECTOR` | Electrical Fixtures |
| Circuit breaker (loose device) | `IfcProtectiveDevice` w/ type `IfcProtectiveDeviceType` | `CIRCUITBREAKER` | Electrical Equipment (via `IfcProtectiveDeviceType.CIRCUITBREAKER`) |
| Conduit run | `IfcCableCarrierSegment` | `CONDUITSEGMENT` | **Cable Trays** (see gotcha) |
| Cable tray run | `IfcCableCarrierSegment` | `CABLETRAYSEGMENT` (`CABLELADDERSEGMENT`, `CABLETRUNKINGSEGMENT`) | Cable Trays |
| Tray / conduit fitting | `IfcCableCarrierFitting` | `BEND` / `TEE` / `CROSS` / `REDUCER` | Cable Tray Fittings |
| Wire / feeder run (rarely modelled) | `IfcCableSegment` | `CABLESEGMENT` / `CONDUCTORSEGMENT` / `BUSBARSEGMENT` | Conduits (occurrence) — types w/ CABLE/CONDUCTORSEGMENT → Electrical Equipment |
| Trapeze hanger / strut / support | `IfcDiscreteAccessory` | `BRACKET` (or `USERDEFINED` + ObjectType `TrapezeHanger`) | Specialty Equipment |
| Generator | `IfcElectricGenerator` | `ENGINEGENERATOR` / `STANDALONE` | **Generic Models** unless mapped (see gotcha) |
| UPS / battery / capacitor bank | `IfcElectricFlowStorageDevice` | `UPS` / `BATTERY` / `CAPACITORBANK` | **Generic Models** unless mapped |
| Disconnect (safety switch, fused) | `IfcSwitchingDevice` | `SWITCHDISCONNECTOR` | Electrical Fixtures |
| Motor | `IfcElectricMotor` | `INDUCTION` / `SYNCHRONOUS` … | **Generic Models** unless mapped |
| Room / electrical room volume | `IfcSpace` | (`INTERNAL`) | Generic Models — *not* a Revit Room |
| Equipment we can't classify | `IfcBuildingElementProxy` | `NOTDEFINED` | Generic Models |

---

## 2. Forward map — details, psets, gotchas

Property-set columns list the buildingSMART standard psets we should populate
(names/props confirmed in Autodesk's exporter pset table [pset]). Our own
project psets (`PanelSchedule`, `TransformerSchedule`, `SupportSchedule`) ride
alongside — see `shared-parameters-mapping.md`.

### 2.1 Panelboard / switchboard / MCC — `IfcElectricDistributionBoard`

- Predefined types [ifc4]: `CONSUMERUNIT`, `DISTRIBUTIONBOARD` (panelboard /
  load center — our default), `MOTORCONTROLCENTRE`, `SWITCHBOARD`,
  `USERDEFINED`, `NOTDEFINED`.
- Import: `IfcElectricDistributionBoard(Type)` → **OST_ElectricalEquipment**
  [src line ~445–446]. Also `IfcFlowController` + `CIRCUITBREAKER` and
  `IfcCableSegmentType`/`IfcFlowSegment` `CABLESEGMENT`/`CONDUCTORSEGMENT` land
  in Electrical Equipment [src predefined map].
- Standard psets [pset]: `Pset_ElectricDistributionBoardTypeCommon`
  (Reference, Status), `Pset_ElectricDistributionBoardOccurrence` (IsMain,
  IsSkilledOperator), `Pset_ElectricalDeviceCommon` (NominalCurrent,
  UsageCurrent, NominalVoltage[bounded], NumberOfPoles, RatedCurrent[bounded],
  RatedVoltage[bounded], IP_Code, HasProtectiveEarth, InsulationStandardClass,
  Power, PowerFactor, NominalFrequencyRange, EarthingStyle),
  `Pset_ElectricalDeviceCompliance`, `Pset_ManufacturerTypeInformation`
  (Manufacturer, ModelLabel, ModelReference, ArticleNumber, ProductionYear,
  OperatingWeight, ShippingWeight), quantities `Qto_ElectricDistributionBoard…`
  (IFC4: number of circuits / gross weight live in Qto, not Pset).
- Note [ifc4x3]: IFC4.3 **deprecates** `IfcElectricDistributionBoard` in
  favour of `IfcDistributionBoard`; we author IFC4, so keep the IFC4 name —
  Revit's importer maps both eras.
- Gotcha: schedule-critical values (voltage, phases, bus rating, mains type,
  SCCR, mounting, circuits) are NOT standard IFC4 board props — that is
  exactly why we carry the project pset `PanelSchedule` (matches the firm's
  shared-parameters file). Do both: standard psets for interoperability,
  `PanelSchedule` for the Revit schedule/tags.

### 2.2 Transformer — `IfcTransformer`

- Predefined types [ifc4]: `CURRENT`, `FREQUENCY`, `INVERTER`, `RECTIFIER`,
  `VOLTAGE` (our default for building distribution transformers),
  `USERDEFINED`, `NOTDEFINED`.
- Import: → **OST_ElectricalEquipment** [src line ~560–561].
- Psets [pset]: `Pset_TransformerTypeCommon` (PrimaryVoltage,
  SecondaryVoltage, PrimaryCurrent, SecondaryCurrent, PrimaryFrequency,
  SecondaryFrequency, PrimaryApparentPower, SecondaryApparentPower,
  MaximumApparentPower, RealImpedanceRatio, ImaginaryImpedanceRatio,
  ShortCircuitVoltage[complex], TransformerVectorGroup, SecondaryCurrentType,
  IsNeutralPrimary/SecondaryTerminalAvailable, EfficiencyCurve[table],
  Reference, Status), plus `Pset_ElectricalDeviceCommon`,
  `Pset_ManufacturerTypeInformation`.
- kVA is `IfcPowerMeasure` (SI: use volt-ampere/watt consistently with the
  file's unit assignment). Our `TransformerSchedule` pset carries the
  contractor-facing values (kVA, primary/secondary system strings, taps,
  temp rise, impedance %).

### 2.3 Light fixture — `IfcLightFixture`

- Predefined types [ifc4]: `POINTSOURCE` (most troffers/downlights),
  `DIRECTIONSOURCE` (linear/directional), `SECURITYLIGHTING` (egress/exit),
  `USERDEFINED`, `NOTDEFINED`.
- Import: → **OST_LightingFixtures**; `IfcLamp(Type)` (the lamp inside) →
  **OST_LightingDevices** [src lines ~484–487].
- Psets [pset]: `Pset_LightFixtureTypeCommon` (NumberOfSources,
  TotalWattage[Power], LightFixtureMountingType[PEnum: CABLESPANNED /
  CHAIN / PIPE / POLE / RECESSED / SURFACE / SUSPENDED / TRACKMOUNTED],
  LightFixturePlacingType, MaintenanceFactor, MaximumPlenumSensibleLoad,
  MaximumSpaceSensibleLoad, SensibleLoadToRadiant, ArticleNumber, Reference,
  Status), `Pset_LightFixtureTypeSecurityLighting` (exit-sign specifics),
  `Pset_ElectricalDeviceCommon`, `Pset_ManufacturerTypeInformation`.
- Gotcha: Revit lighting *photometrics* (IES, initial intensity, colour) do
  not exist in a DirectShape — a linked IfcLightFixture renders as geometry
  with a material, it emits no light. Photometric fixtures = native families
  (Tier 2). Plenum-rated is our own `LuminaireSchedule` label/boolean, not an
  IFC4 property.

### 2.4 Receptacles / outlets — `IfcOutlet`

- Predefined types [ifc4]: `AUDIOVISUALOUTLET`, `COMMUNICATIONSOUTLET`,
  `POWEROUTLET`, `DATAOUTLET`, `TELEPHONEOUTLET`, `USERDEFINED`, `NOTDEFINED`.
- Import [src]: the built-in map keys on `IfcOutletType` —
  `POWEROUTLET` → **OST_ElectricalFixtures**; `AUDIOVISUALOUTLET` /
  `COMMUNICATIONSOUTLET` → **OST_DataDevices**; `NOTDEFINED` →
  **OST_GenericModel**. `IfcFlowTerminal.POWEROUTLET` (the IFC2x3 way) also →
  Electrical Fixtures. **Gotcha:** the occurrence class `IfcOutlet` itself has
  no map entry — the category is resolved from its `IfcOutletType`. So **always
  emit an `IfcOutletType` with a real PredefinedType** (or set the occurrence's
  PredefinedType and a type object); an untyped `IfcOutlet` falls to Generic
  Models with a log warning ("Setting IFC entity IfcOutlet to Generic Models").
- Psets [pset]: `Pset_OutletTypeCommon` (IsPluggableOutlet, NumberOfSockets,
  Reference, Status), `Pset_ElectricalDeviceCommon`.

### 2.5 Junction box / pull box — `IfcJunctionBox`

- Predefined types [ifc4]: `DATA`, `POWER`, `USERDEFINED`, `NOTDEFINED`.
- Import: → **OST_ElectricalFixtures** [src lines ~482–483].
- Psets [pset]: `Pset_JunctionBoxTypeCommon` (NumberOfGangs, ClearDepth,
  NominalLength/Width/Height, ShapeType[RECTANGULAR/ROUND/SLOT],
  MountingType/JunctionBoxMountingType[FACENAIL/SIDENAIL/CUT_IN],
  PlacingType[CEILING/FLOOR/WALL], IP_Code, IsExternal, Reference, Status),
  `Pset_JunctionBoxTypeData` (data-box specifics).

### 2.6 Switches and disconnects — `IfcSwitchingDevice`

- Predefined types [ifc4]: `CONTACTOR`, `DIMMERSWITCH`, `EMERGENCYSTOP`,
  `KEYPAD`, `MOMENTARYSWITCH`, `SELECTORSWITCH`, `STARTER`,
  `SWITCHDISCONNECTOR` (safety switch / disconnect), `TOGGLESWITCH` (wall
  switch), `USERDEFINED`, `NOTDEFINED`.
- Import: → **OST_ElectricalFixtures** [src lines ~554–555].
- Psets [pset]: `Pset_SwitchingDeviceTypeCommon` (NumberOfGangs,
  SwitchFunction[ONOFFSWITCH/INTERMEDIATESWITCH/DOUBLETHROWSWITCH],
  HasLock, IsIlluminated, Legend, SetPoint, Reference, Status),
  `Pset_ElectricalDeviceCommon`. Fused disconnects: also
  `Pset_ProtectiveDeviceTypeCommon` if you model the fusing.

### 2.7 Circuit breakers as loose devices — `IfcProtectiveDevice`

- Only if a breaker is a *separate* product (a molded-case breaker in its own
  enclosure). Breakers *inside* a panel are geometry of the panel + rows in the
  panel schedule — not separate IFC products (Revit would make 42 useless
  DirectShapes).
- Predefined types [ifc4]: `CIRCUITBREAKER`, `EARTHINGSWITCH`,
  `EARTHLEAKAGECIRCUITBREAKER`, `FUSEDISCONNECTOR`, `RESIDUALCURRENTCIRCUITBREAKER`,
  `RESIDUALCURRENTSWITCH`, `VARISTOR`, `USERDEFINED`, `NOTDEFINED`.
- Import [src]: unqualified `IfcProtectiveDevice` is **not** in the built-in
  occurrence map ⇒ Generic Models; but `IfcProtectiveDeviceType` →
  Electrical Fixtures, and `(IfcProtectiveDeviceType, CIRCUITBREAKER)` →
  **Electrical Equipment**. So: emit an `IfcProtectiveDeviceType` with
  PredefinedType `CIRCUITBREAKER` (category resolves via the type).
- Psets [pset]: `Pset_ProtectiveDeviceTypeCommon` (RatedShortCircuitCurrent,
  CutOffCurrent, MaximumRatedVoltage, CharacteristicTripCurve[table],
  StandardUsed, ProtectiveTagType, SwitchingDuty, LimitingTerminalSize,
  Reference, Status), breaking-capacity/tripping-unit psets exist for detail.

### 2.8 Conduit and cable tray — `IfcCableCarrierSegment` (+ fittings)

- Predefined types [ifc4]: `CABLELADDERSEGMENT`, `CABLETRAYSEGMENT`,
  `CABLETRUNKINGSEGMENT`, `CONDUITSEGMENT`, `USERDEFINED`, `NOTDEFINED`.
  Fittings `IfcCableCarrierFitting`: `BEND`, `CROSS`, `REDUCER`, `TEE`.
- Import [src lines ~405–410]: **all** `IfcCableCarrierSegment(Type)` →
  **OST_CableTray** and all `IfcCableCarrierFitting(Type)` →
  **OST_CableTrayFitting** — *regardless of predefined type*. So a conduit run
  authored (correctly!) as `IfcCableCarrierSegment.CONDUITSEGMENT` imports into
  the **Cable Trays** category, not Conduits. The **Conduits** category is fed
  only by `IfcCableSegment(Type)` (which semantically is a *cable*, not a
  raceway). This is Autodesk's mapping quirk — and it is symmetric: Revit's
  exporter writes Conduits as `IfcCableCarrierSegment.CONDUITSEGMENT`, so a
  Revit round-trip has the same behaviour.
  **Recommendation:** author conduit honestly as `CONDUITSEGMENT` (correct
  semantics for every other tool + IFC checkers), tell users it will sit in
  the Cable Trays category unless they load the class-mapping file we ship
  (§3), which adds `IfcCableCarrierSegment CONDUITSEGMENT → Conduits`.
- Psets [pset]: `Pset_CableCarrierSegmentTypeCommon` (Reference, Status),
  `Pset_CableCarrierSegmentTypeConduitSegment` (NominalDiameter,
  ConduitShapeType[CIRCULAR/OVAL], IsRigid, NominalLength/Width/Height),
  `Pset_CableCarrierSegmentTypeCableTraySegment` (NominalWidth,
  NominalHeight, NominalLength, HasCover), `Pset_CableCarrierFittingTypeCommon`.
- Gotcha: imported runs are DirectShapes — they are **not** Revit conduit/tray
  system objects: no routing edits, no fittings insertion, no fill %, no
  cable schedules. For dimensioned runs the geometry is fine; for editable
  routing users re-draw natively (or Tier 2 API places real conduit).

### 2.9 Wire / feeder — `IfcCableSegment`

- Usually **not modelled** as 3D geometry (feeders are schedule data / one-
  line data). If modelled: predefined types `BUSBARSEGMENT`, `CABLESEGMENT`,
  `CONDUCTORSEGMENT`, `CORESEGMENT`. Import: `IfcCableSegment(Type)` →
  **OST_Conduit** by default; type/segment with `CABLESEGMENT` /
  `CONDUCTORSEGMENT` → **OST_ElectricalEquipment** [src predefined map].
  Revit's own *Wires* category is a 2D annotation-ish system object — no
  IFC path creates Revit wires.
- Psets [pset]: `Pset_CableSegmentTypeCableSegment`,
  `…ConductorSegment`, `…BusBarSegment`, `Pset_CableSegmentOccurrence`.

### 2.10 Supports / trapeze hangers — `IfcDiscreteAccessory`

- Predefined types [ifc4]: `ANCHORPLATE`, `BRACKET`, `SHOE`, `USERDEFINED`,
  `NOTDEFINED` (IFC4.3 adds `CABLEARRANGER`, `ELECTRICALCROSSING`, etc.).
  For trapeze hangers/strut: `USERDEFINED` + `ObjectType` =
  `'TrapezeHanger'` / `'StrutSupport'`, or `BRACKET`.
- Import: → **OST_SpecialityEquipment** [src lines ~426–427]. (There is a
  Revit "Structural Framing" argument for supports, but Specialty Equipment is
  what the importer gives and it schedules cleanly; leave it.)
- Alternatives: `IfcMechanicalFastener` → Specialty Equipment;
  `IfcElementAssembly` (a whole trapeze as an assembly of parts) → the
  assembly becomes a container DirectShape in Generic Models with children as
  their own DirectShapes — usually overkill; one product per hanger is right.
- Psets [pset]: `Pset_DiscreteAccessoryTypeBracket` (IsInsulated) is thin;
  carry loads/rod size/threaded-rod spec in our `SupportSchedule` pset.

### 2.11 Generators, UPS, motors — the unmapped classes (gotcha)

- Correct IFC4 classes: `IfcElectricGenerator` (`CHP`, `ENGINEGENERATOR`,
  `STANDALONE`), `IfcElectricFlowStorageDevice` (`BATTERY`,
  `CAPACITORBANK`, `HARMONICFILTER`, `INDUCTORBANK`, `UPS`),
  `IfcElectricMotor` (`DC`, `INDUCTION`, `POLYPHASE`,
  `RELUCTANCESYNCHRONOUS`, `SYNCHRONOUS`), `IfcMotorConnection`.
- Import [src]: **none of these has an entry in the built-in map** (the map
  covers appliances/boards/lights/junction boxes/switching but not
  generator/motor/storage). The lookup has **no supertype fallback** — an
  exact-class miss (and a miss on the type object) ⇒ **Generic Models** with a
  log warning [src `GetCategoryIdForEntity`, `GetCategoryElementId`]. This is
  the legacy engine; the AnyCAD hybrid engine's own table is closed
  [unverified whether it does better].
- Psets [pset]: `Pset_ElectricGeneratorTypeCommon`
  (ElectricGeneratorEfficiency, MaximumPowerOutput, StartCurrentFactor),
  `Pset_ElectricFlowStorageDeviceTypeUPS` (`…TypeCommon`: NominalSupplyVoltage,
  NominalFrequency, PowerCapacity…), `Pset_ElectricMotorTypeCommon`
  (MaximumPowerOutput, ElectricMotorEfficiency, FrameSize,
  LockedRotorCurrent, MotorEnclosureType, StartingTime, TeTime).
- **What to do:** keep the honest class (semantics + every other consumer)
  AND ship the import class-mapping file (§3) so they land in Electrical /
  Mechanical Equipment; document that without the mapping file they appear
  under Generic Models. Do **not** mis-class a generator as an
  `IfcElectricDistributionBoard` just to hit a category — that lie propagates
  into every downstream tool and IFC checker.

### 2.12 Rooms / spaces — `IfcSpace`

- `IfcSpace` (PredefinedType `INTERNAL`/`EXTERNAL`/`SPACE`, plus
  `Pset_SpaceCommon`: Reference, Category, OccupancyType, OccupancyNumber,
  Net/GrossPlannedArea, PubliclyAccessible, HandicapAccessible, IsExternal…).
- Import: → **OST_GenericModel** deliberately ("the Rooms category should be
  used for a real Revit room") [src line ~536–540]. The volume comes in as a
  translucent DirectShape solid; it is **not** a Revit Room or Space, does not
  bound, does not host tags/area schemes, and is not visible to Revit's
  space/zone tools.
- **Recommendation:** emit `IfcSpace` (aggregated to the storey via
  `IfcRelAggregates`, not contained) for coordination volume + carrying our
  `RoomInformation` pset — and tell the user that real Revit Rooms/Spaces are
  placed natively in the host (they will bound to the linked geometry). Keep
  `IfcSpace` geometry a simple extrusion so it isn't a mesh blob.
- Storey containment: elements should be contained per storey via
  `IfcRelContainedInSpatialStructure` (Revit sets `IfcSpatialContainer` = the
  storey name; each `IfcBuildingStorey` becomes a real `Level`).

### 2.13 Fallback — `IfcBuildingElementProxy`

- → **OST_GenericModel** [src]. Use only for genuinely unclassifiable gear.
  Some IFC checkers flag proxies; Revit users see "Generic Models" and stop
  trusting the model. `PredefinedType`: `COMPLEX`/`ELEMENT`/`PARTIAL`/
  `PROVISIONFORVOID`/`PROVISIONFORSPACE`/`USERDEFINED`/`NOTDEFINED`.

---

## 3. The import class-mapping file we should ship (fixes the two quirks)

Format (Link *and* Open honour it once loaded via **File ▸ Open ▸ IFC
Options ▸ Load**; Revit ships its own default `importIFCClassMapping.txt`,
reachable through that same dialog — the USER loads it in Revit; we never
read the Revit install) [src `IFCCategoryUtil.InitFromFile`; docs]:

```
# IFC Class Name and Type to Revit Category/Sub-Category Table
# tab-separated: IfcClassName [<tab> IfcType/PredefinedType] <tab> Revit Category <tab> Sub-Category
# "Don't Import" in the category column excludes a class.
IfcCableCarrierSegment	CONDUITSEGMENT	Conduits
IfcCableCarrierFitting	BEND	Conduit Fittings
IfcElectricGenerator		Electrical Equipment
IfcElectricGeneratorType		Electrical Equipment
IfcElectricFlowStorageDevice		Electrical Equipment
IfcElectricFlowStorageDeviceType		Electrical Equipment
IfcElectricMotor		Mechanical Equipment
IfcElectricMotorType		Mechanical Equipment
IfcOutlet	POWEROUTLET	Electrical Fixtures
IfcAudioVisualAppliance		Data Devices
```

**Warning:** when a mapping file loads successfully it *replaces* the whole
built-in map for that import [src `InitializeCategoryMaps`: `if
(!InitFromFile()) InitEntityTypeToCategoryMaps()`], so a shipped file must be
**complete** (start from Revit's own `importIFCClassMapping.txt` and add our
rows) — a five-line file would send every other class to nothing/Generic.
This is an out-of-scope deliverable; noted in `docs/inbox/revit-fidelity.md`.
Until it exists, the default (no file) behaviour above is what users get.

---

## 4. Reverse map — what Revit's own IFC exporter writes per category

Purpose: authoring parity. When a Revit MEP model exports IFC, these are the
entities its categories produce (default category mapping, overridable per
family via the `Export to IFC As` / `Export Type to IFC As` parameters —
`IfcExportAs` syntax `IfcClass.PREDEFINEDTYPE` in Revit ≤2022 [docs IFC Manual
"Category mapping override"]). Matching these keeps our IFC indistinguishable
from Revit-authored IFC.

| Revit category | Exporter's default IFC entity (IFC4 export) | Notes |
|---|---|---|
| Electrical Equipment | `IfcElectricDistributionBoard` (IFC2x3 export: `IfcElectricDistributionPoint`) | Revit substitutes the schema-appropriate class ("Revit will determine the correct IFC entity if there is a discrepancy between IFC2x3 and IFC4") [docs open-source wiki]. Set `Export to IFC As` on transformer families → `IfcTransformer`. |
| Electrical Fixtures | `IfcSwitchingDevice` (switches) / `IfcOutlet` (receptacles) via family override | Category default is coarse; Autodesk's KB explicitly recommends per-family `IfcExportAs` for fixtures [docs bimcorner/manual]. |
| Lighting Fixtures | `IfcLightFixture` | Light Source subcategory not exported. |
| Lighting Devices | `IfcLamp` / `IfcSwitchingDevice` [unverified default] | |
| Data / Communication / Telephone / Fire Alarm / Nurse Call / Security Devices | `IfcCommunicationsAppliance` / `IfcAlarm` / `IfcSensor` etc.; older tables `IfcBuildingElementProxy` | Verify against the installed table [unverified defaults]. |
| Cable Trays | `IfcCableCarrierSegment` `.CABLETRAYSEGMENT` | |
| Cable Tray Fittings | `IfcCableCarrierFitting` | |
| Conduits | `IfcCableCarrierSegment` `.CONDUITSEGMENT` | Hence the round-trip quirk in §2.8. |
| Conduit Fittings | `IfcCableCarrierFitting` | |
| Wires | Not exported | 2D system objects. |
| Specialty Equipment | `IfcDiscreteAccessory` / `IfcBuildingElementProxy` | Supports/hangers should carry `IfcExportAs = IfcDiscreteAccessory.BRACKET`. |
| Mechanical Equipment | `IfcUnitaryEquipment` / `IfcBuildingElementProxy` (family override to `IfcElectricMotor`, `IfcElectricGenerator`, …) | |
| Rooms / Spaces | `IfcSpace` | |
| Generic Models | `IfcBuildingElementProxy` | |

How to check the *actual* defaults on a given machine: **File ▸ Export ▸
IFC ▸ Modify setup ▸ Category Mapping** (Revit 2025+, template-based dialog) or
File ▸ Export ▸ Options ▸ IFC Options (≤2024, backed by Revit's own
`exportlayers-ifc-IAI.txt` mapping file, tab-separated
`Category ⇥ Subcategory ⇥ IfcClassName ⇥ IfcType`) [docs IFC Manual "IFC
Export - Category Mapping"]. Defaults vary slightly by Revit release — treat
the table above as the shape, and read the installed table when exact parity
matters.

---

## 5. `PredefinedType` handling details worth knowing

- The importer takes the occurrence's `PredefinedType`; if empty or
  `NOTDEFINED` it uses the associated type object's `PredefinedType`; the
  `ObjectType` string is consulted only for a few `(class, USERDEFINED,
  ObjectType)` triples (e.g. `IfcAnnotation USERDEFINED CogoPoints`) [src
  `GetCategoryIdForEntity`]. So set PredefinedType on **both** the occurrence
  and the type, identically.
- `USERDEFINED` requires the human-readable subtype in `ObjectType`
  (occurrence) / `ElementType` (type); Revit surfaces it as the
  `IfcObjectType` / `ObjectTypeOverride` parameter.
- The predefined type is written to the `IfcPredefinedType` parameter and,
  where a subcategory is created, becomes part of the subcategory name.

---

## Sources

- Built-in class→category map & class-mapping-file parser [src]:
  https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Import/Utility/IFCCategoryUtil.cs
  (electrical entries at the `InitEntityTypeToCategoryMaps` /
  `m_EntityPredefinedTypeToCategory` blocks; category lookup with no supertype
  fallback in `GetCategoryElementId`; unmapped → Generic Models warning in
  `GetCategoryIdForEntity`). Local: `vendor/revit-ifc/Source/Revit.IFC.Import/Utility/IFCCategoryUtil.cs`.
- Autodesk's IFC4 property-set definitions (exporter's shared-parameter file
  shipped with the add-in) [pset]:
  https://github.com/Autodesk/revit-ifc/blob/master/Install/Program%20Files%20to%20Install/IFC%20Shared%20Parameters-RevitIFCBuiltIn_ALL.txt
- buildingSMART IFC schema docs (entity/predefined-type/pset applicability):
  IFC4x3: https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcElectricDistributionBoard.htm
  (notes IFC4.3 deprecation → IfcDistributionBoard); IFC4 ADD2 TC1 entity
  pages under https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/
  (403 to our fetcher; enumerations quoted from the schema definitions).
- IFC class mapping file format & DontImport: Revit's shipped
  `importIFCClassMapping.txt` (copy: https://sourceforge.net/p/ifcexporter/discussion/general/thread/21e95d26/3885/attachment/importIFCClassMapping.txt);
  Geometry Gym note: https://technical.geometrygym.com/revit/revitifc/ifc-import/ifc-category-mapping [forum]
- Export category mapping & `IfcExportAs`/element-based mapping: Autodesk
  IFC Manual — https://autodesk.ifc-manual.com/revit/ifc-export-category-mapping ,
  https://autodesk.ifc-manual.com/revit/ifc-export-category-mapping/category-mapping-override
- Supported export entities (IFC2x3 vs IFC4 substitution):
  https://sourceforge.net/p/ifcexporter/wiki/Supported%20IFC%20Entities/
- Ground truth for our sample classes: `docs/design-ground-truth.md` §5;
  `samples/design-ifc/bs-area-e-electrical-room.ifc`.
