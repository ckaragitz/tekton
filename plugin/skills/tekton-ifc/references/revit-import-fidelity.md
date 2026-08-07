# Revit ← IFC import fidelity (Revit 2023 · 2024 · 2025 · 2026)

Scope: exactly what Revit does with an IFC file — the three import routes, what
each IFC geometry/data construct becomes, what stays editable, and the MEP
truth. Every claim below is tagged with its evidence:

- **[src]** = read directly from Autodesk's open-source Link-IFC importer,
  `github.com/Autodesk/revit-ifc` (cloned at `vendor/revit-ifc`, master @
  `f534ad1`, targets Revit 2027 API; the import architecture is unchanged
  2019→2027). File paths cited are under `Source/Revit.IFC.Import/`.
- **[docs]** = Autodesk help / Autodesk IFC Manual / Revit API docs (URL in Sources).
- **[forum]** = community source, weaker; **[unverified]** = could not confirm.

---

## TL;DR

1. **There are three routes, and they run different code.**
   - **Link IFC** (Insert ▸ Link IFC) — the recommended path. Runs the
     open-source importer + (since 2024.1) an AnyCAD "hybrid" geometry engine.
     Produces an intermediate `<name>.ifc.RVT` in which **every IfcProduct is a
     `DirectShape`** in the mapped Revit category, plus a `.ifc.log.html` and a
     `.ifc.sharedparameters.txt`. [src `Importer.cs` `ReferenceIFC`; docs]
   - **Open IFC** (File ▸ Open ▸ IFC) — Autodesk's older, closed-source
     "Parametric" engine that converts IFC classes into Revit categories using
     the *Import IFC Class Mapping* table. Only IFC2x3/2x2/2x supported here;
     IFC4+ files are opened with "partial schema support" warnings, IFC4.3
     cannot be opened at all. Most non-architectural classes come in as
     non-parametric geometry; much pset data is lost. [src `Importer.cs`
     `ImportIFC` → `IFCImportFile.Import` (posts `IFCPartialSchemaSupport` for
     IFC4+); docs "About Revit and IFC"; docs IFC Manual]
   - **Link CAD / Import CAD** (Insert tab) does NOT accept IFC. The only
     "import" verbs for IFC are Open and Link (plus API/Design Automation).
2. **Nothing in an IFC becomes a *parametric family*.** In the Link route the
   editability ceiling is: DirectShape (correct category, name, all psets as
   parameters, type = DirectShapeType, movable/copyable/deletable only in the
   intermediate file, geometry never editable). Geometry representation type
   changes *how good the DirectShape is*, not *whether* it is one.
3. **MEP truth: NO connectors, NO circuits, NO systems — ever.** The importer
   contains no `Connector`/`ElectricalSystem`/circuit creation. An
   `IfcDistributionPort` becomes its own little DirectShape (a point + a cone
   arrow) with string parameters ("Flow Direction", "System Type",
   "IfcPort ConnectedTo Name"…). `IfcDistributionSystem` becomes a container
   DirectShape with "SystemClassification"/"SystemName" strings. [src] Real
   connectors/panel schedules require native families placed via the Revit API
   (Tier 2 — Design Automation add-in) or hand-modelling in Revit.
4. **Psets → shared parameters automatically (Link route).** Every
   `IfcPropertySet` property becomes an instance shared parameter bound to the
   element's category, defined in the auto-written
   `<name>.ifc.sharedparameters.txt` (groups "IFC Parameters" and
   "IFC Type Parameters"). Default naming is **`PsetName.PropertyName`** (e.g.
   `PanelSchedule.PanelName`), NOT the bare property name — and the GUIDs are
   the importer's, not your firm's. See `shared-parameters-mapping.md`. [src]
5. **GlobalId is the re-import key.** On reload Revit matches entities to
   existing elements by IfcGUID (stored in the built-in `IFC_GUID` /
   `IFC_TYPE_GUID` parameters) — keep GUIDs stable across re-exports or every
   element is deleted and recreated. [src `IFCImportCache.UseElementByGUID`,
   `IFCGUIDUtil.cs`; docs "About Linking to IFC Files"]

---

## 1. The three routes

### 1.1 Link IFC — `Insert ▸ Link IFC` (recommended, and the only one we should tell users to use)

What happens, verbatim from the code path [src `Importer.cs`]:

- `ImportIFC()` reads the options dictionary. `Intent` defaults to `Reference`
  and `Action` to `Open`; the Link IFC command passes `Intent=Reference,
  Action=Link`. `Reference` intent ⇒ `ReferenceIFC()`; any other intent
  (`Parametric`) ⇒ the closed internal `IFCImportFile.Import()` (= Open IFC).
- `ReferenceIFC` computes `<localname>.ifc.RVT`, and either reuses it
  (timestamp/size/importer-version check via `DocumentUpToDate`) or creates a
  new project from `Application.DefaultIFCProjectTemplate` (falling back to the
  default project template) [`CreateLinkDocument`]. Set a *minimal* IFC
  template in the Import IFC Options dialog to avoid dragging views/families
  into every link. [docs IFC Manual "Using IFC Files in Revit"]
- It writes the sharedparameters sidecar (`IFCImportCache.ReadSharedParametersFile`),
  then walks the IFC project tree creating one Revit element per
  `IfcObjectDefinition` (`IFCObjectDefinition.CreateElement`), then links the
  `.ifc.RVT` into the host as a `RevitLinkType`/`RevitLinkInstance`
  (`IFCImportFile.LinkInFile`).
- Three sidecar files land next to the `.ifc` [docs "Link an IFC File"]:
  `<name>.ifc.RVT` (the real content — never move/rename it),
  `<name>.ifc.log.html` (conversion log, read this when something is missing),
  `<name>.ifc.sharedparameters.txt` (parameter definitions for the host).
- Reload semantics: on host open, Revit compares the IFC's timestamp + size
  and only re-imports if changed (`NeedsReload`); a manual *Reload* forces it
  (`ForceImport=true`). Entities are matched to existing elements by IfcGUID
  [docs "About Linking to IFC Files"; src `NeedsReload`, `UseElementByGUID`].
- Since Revit 2024.1 the geometry engine is selectable via `Revit.ini`
  `[ImportIFC] LinkProcessor` = `Default` | `Legacy` | `AnyCAD`. `Default`
  = the new AnyCAD-assisted "hybrid" processor ("more advanced geometric
  fidelity and stability, but may reduce performance"); `Legacy` = the pure
  open-source engine of 2024.0 and earlier. Either way the output elements are
  DirectShapes. [docs "Link an IFC File" 2026 + Revit API
  `ImportIFCOptions.LinkProcessor`; src `IFCImportOptions.cs` line ~349-355,
  `IFCImportHybridInfo.cs` "Elements imported (DirectShape/DirectShapeTypes)
  by AnyCAD"]
- Positioning: through 2025 the link is placed Origin-to-Origin (IFC origin →
  Revit internal origin); **Revit 2026 adds Auto - Origin to Origin / Auto - By
  Shared Coordinates options**. [docs IFC Manual "New in Revit 2026", "Link an
  IFC File"; src `IFCImportOptions.LinkPosition/LinkOrientation`]

Host-side capabilities of a linked IFC (same as any Revit link): visible in all
views, snappable, dimension-able, taggable (tags can annotate linked elements),
schedulable (schedule with *Include elements in links*), face-hosting for
face-based families; IFC-based walls/floors/doors bound rooms (curtain elements
do not). It is **read-only** — "You will not be able to make changes to the
IFC model in Revit". [docs "About Linking to IFC Files"]

### 1.2 Open IFC — `File ▸ Open ▸ IFC`

- Different engine: closed-source `importer.ProcessIFCProject` inside Revit
  [src `Data/IFCImportFile.Import`]. It "convert[s] IFC classes into Revit Model
  Categories" [Autodesk article title, search-corroborated] using the **Import
  IFC Class Mapping** table (`importIFCClassMapping.txt`, editable in File ▸
  Open ▸ IFC Options). Creates a **new standalone project** from the default IFC
  template; nothing is linked.
- Schema support is IFC2x3-era: "For import (to open or link an IFC file),
  Revit supports … IFC2x3, IFC2x2, and IFC2x. For import (link only), Revit
  also supports … IFC4." [docs "About Revit and IFC", identical wording in the
  2023 and 2026 pages]. The open path posts a `IFCPartialSchemaSupport` failure
  for IFC4+ files [src] and "Opening IFC 4.3 Files in Revit is NOT supported"
  [docs IFC Manual "IFC 4.3 Support"].
- Result: architectural classes (walls, slabs, roofs, columns, doors/windows)
  can arrive as native system-family/loadable elements; classes with no native
  equivalent (all MEP equipment) arrive as in-place-family-style geometry, and
  users consistently report the pset data is largely dropped ("created Inplace
  Families and not containing any of the IFC data") [forum: revit-ifc issue
  #223]. Revit 2025 added: presentation-layer import and an `IfcMaterial`
  shared parameter listing materials on Open [docs IFC Manual "New in 2025"].
- **Use only when the deliverable must be a self-contained `.rvt` with no
  link** and the user accepts data loss. For our electrical gear, Open IFC is
  strictly worse than Link IFC. State this every time it comes up.

### 1.3 API / Design Automation route (same engines, no UI)

The same two engines are reachable programmatically:
`Application.OpenIFCDocument(path, IFCImportOptions)` with
`Intent = IFCImportIntent.Reference|Parametric`, `Action = Open|Link`,
`RevitLinkFileName`, plus `Importer.CreateImporter(doc, path, options)` for
external callers [src `Importer.CreateImporter`, `IFCImportOptions.cs` option
keys: `Intent`, `Action`, `ProcessBoundingBoxGeometry`,
`AlwaysProcessBoundingBoxGeometry`, `CreateDuplicateZoneGeometry`,
`CreateDuplicateContainerGeometry`, `UseStreamlinedOptions`, `DisableLogging`,
`VerboseLogging`, `LinkOrientation`, `LinkPosition`, `ForceImport`,
`CreateLinkInstanceOnly`, `RevitLinkFileName`, `FileSize`,
`FileModifiedTime`, `AlternativeProcessor`]. This is the hook APS Design
Automation uses for a headless IFC→RVT conversion — it produces the *same*
DirectShapes, so it is a validation/packaging convenience, not a fidelity
upgrade.

---

## 2. What each IFC construct becomes (Link IFC, both processors)

Master rule [src `IFCProduct.Create` → `IFCElementUtil.CreateElement` →
`DirectShape.CreateElement(doc, categoryId)`]: **every `IfcProduct` with valid
geometry becomes one `DirectShape`** in the category from the class map (§4),
`ApplicationId` = `88743F28-A2E1-4935-949D-4DB7A724A150`, `ApplicationDataId`
= the IfcGUID. If it has a valid `IfcTypeObject`, a `DirectShapeType` is
created (name = the type's Name) and assigned (`shape.SetTypeId`) [src
`IFCTypeObject.Create` → `IFCElementUtil.CreateElementType`]. Products with
no geometry create nothing (a warning is logged), unless they are containers
(then `CreateDuplicateContainerGeometry` may give them a copy of children's
geometry).

| IFC construct | Revit result | Notes / evidence |
|---|---|---|
| `IfcExtrudedAreaSolid`, `IfcRevolvedAreaSolid`, `IfcSweptDiskSolid`, `IfcSurfaceCurveSweptAreaSolid`, `IfcBooleanResult`/`IfcCsgSolid` | A **true Revit `Solid`** inside the DirectShape (`GeometryCreationUtilities.CreateExtrusionGeometry/CreateRevolvedGeometry/CreateSweptGeometry` + `BooleanOperationsUtils`) | Clean edges/faces, exact volume, snappable planar faces; still a DirectShape. This is the best-case geometry. [src `Data/IFCExtrudedAreaSolid.cs`, `IFCRevolvedAreaSolid.cs`, `IFCSweptDiskSolid.cs`] |
| `IfcFacetedBrep`, `IfcAdvancedBrep`, `IfcClosedShell` | Solid via BRepBuilder when watertight, else falls back to tessellation | [src `Utility/BrepBuilderScope.cs`, `Data/IFCManifoldSolidBrep.cs`] |
| `IfcTriangulatedFaceSet` / `IfcPolygonalFaceSet` / `IfcFaceBasedSurfaceModel` | `TessellatedShapeBuilder` → a `Solid` **if** the mesh is closed and clean, otherwise a **`Mesh`** ("Salvage"/"Mesh" fallback). Meshes: no smooth faces, no volume, painted-looking, worst for snapping. | [src `Utility/TessellatedShapeBuilderScope.cs` target `AnyGeometry`, fallback `Mesh`] — this is what 100% of our v1 exports produce. |
| `IfcMappedItem` (+ `IfcRepresentationMap`) | **Real instancing.** The map becomes one entry in a DirectShape shape library (a `DirectShapeType` named by the map's STEP id); each mapped item is a `GeometryInstance` (`DirectShape.CreateGeometryInstance`) placed by its `IfcCartesianTransformationOperator3D`. Only for uniform (conformal, scale = 1) transforms; non-uniform scale bakes geometry. | [src `Data/IFCRepresentationMap.cs` lines 100–212, `Data/IFCMappedItem.cs` `canCreateType`]. So `IfcMappedItem` instancing shrinks the RVT and gives shared geometry — worth emitting. |
| `IfcTypeObject` (`IfcElectricDistributionBoardType`, …) | `DirectShapeType`, named from the type's Name, category from class map, carries the **type psets** as *type* shared parameters (group "IFC Type Parameters"). One shared type ⇒ one Revit type. | [src `Data/IFCTypeObject.cs`, `Utility/IFCImportCache.cs` "IFC Type Parameters"] |
| `IfcLocalPlacement` / `IfcAxis2Placement3D` | Transform **baked into the geometry** (`IFCDefaultProcessor.ApplyTransforms = true`); the DirectShape has **no separate insertion point or rotation**. Correct placement = correct position, but "rotate about its origin"/"replace with family at insertion point" are not available. | [src `Processors/IFCDefaultProcessor.cs`, `IFCProduct.Create` `transformToUse`] |
| `IfcBuildingStorey` | A real **`Level`** datum in the intermediate file (reuses the template's unconstrained levels first), elevation = placement Z + reference elevation. | [src `Data/IFCBuildingStorey.cs` `Level.Create(doc, totalElevation)`] |
| `IfcSite` / `IfcBuilding` / `IfcProject` | Project Information params (`Original IFC File Name`, projected-CRS params, `SiteName`…); shared coordinates when linking by shared coords. No solids. | [src `Data/IFCProject.cs`, `IFCSite.cs`] |
| `IfcSpace` / `IfcZone` / `IfcSpatialZone` | DirectShape in **Generic Models** (not Rooms!) — "the Rooms category should be used for a real Revit room". Zones optionally get a copy of their spaces' geometry. | [src `IFCCategoryUtil` line ~539; `IFCImportOptions.CreateDuplicateZoneGeometry`] Native Rooms/Spaces must be created in the host by the user. |
| `IfcRelContainedInSpatialStructure` | String params `IfcSpatialContainer` + `IfcSpatialContainer GUID` on each element (the storey name). Element `Level` association follows creation, not a live constraint. | [src `IFCProduct.CreateParametersInternal`] |
| `IfcRelAggregates` (assemblies, containers) | Parent gets a container DirectShape (optionally duplicating children geometry); children reference host via `IfcContainedInHost` / `IfcContainedInHostGUID` params. | [src `IFCElement.cs` lines 202–222] |
| `IfcOpeningElement` + `IfcRelVoidsElement` | Void solids Boolean-cut from the host solid where possible. | [src `IFCProduct.Create` `CutSolidByVoids`] |
| `IfcDistributionPort` | Its own DirectShape (**Generic Models**): a `Point` + a small **cone arrow** revolved solid showing `FlowDirection`; string params `Flow Direction`, `System Type`, `IfcElement ContainedIn IfcGUID/Name`, `IfcPort ConnectedFrom/ConnectedTo IfcGUID/Name`. The host element gets `IfcElement HasPorts IfcGUID N` params. **Not a Revit Connector.** | [src `Data/IFCDistributionPort.cs` lines 120–180, `Data/IFCPort.cs` lines 167–206, `Data/IFCElement.cs` line 242] |
| `IfcDistributionSystem` / `IfcSystem` | A container DirectShape (category by system predefined type, e.g. ELECTRICAL/LIGHTING → Electrical Equipment) with `SystemClassification` + `SystemName` string params; members get `IfcSystem` param. **Not a Revit `ElectricalSystem`/circuit.** | [src `Data/IFCDistributionSystem.cs`] |
| `IfcPropertySet` on element | Instance shared parameters, one per property, typed (see §5) | [src `Data/IFCPropertySet.cs`] |
| `IfcPropertySet` on type | Type shared parameters on the `DirectShapeType` | [src] |
| `IfcElementQuantity` | Same mechanism as psets (quantity name → parameter) | [src `Data/IFCElementQuantity.cs`] |
| `IfcMaterial` / `IfcSurfaceStyle` | Revit materials created/matched by name; colour + transparency applied; `IfcMaterial` string param lists material names | [src `Utility/IFCMaterialCache.cs`, `IFCObjectDefinition.SetMaterialParameter`; docs IFC Manual "New in 2025"] |
| `IfcPresentationLayerAssignment` | `IfcPresentationLayer` string param (Open IFC maps layers since 2025) | [src; docs] |
| `IfcClassificationReference` | `ClassificationCode` params | [src `Data/IFCObjectDefinition.cs`] |
| Standard identity attributes | `IfcName` (also becomes the element's Name where allowed), `IfcDescription` (also `ALL_MODEL_DESCRIPTION`), `IfcTag`, `IfcObjectType`, `IfcPredefinedType`/`PredefinedType`, `IfcElementType`, plus built-in `IFC_GUID` / `IFC_TYPE_GUID`; elements also get an `IfcPropertySetList` string of pset names created (handy schedule filter). | [src `IFCObjectDefinition.cs` `SetName/SetDescription`, `IFCTypeObject.CreatePropertySets` "Type IfcPropertySetList"] |
| Bounding-box-only representation | Imported only if `ProcessBoundingBoxGeometry` allows (default: only when no other rep exists) | [src `IFCProcessBBoxOptions`] |

### 2.1 So what does "editable" mean, exactly? (state this to users)

For an element in the intermediate `.ifc.RVT`, opened directly (not through the link):

| Action | DirectShape | Native family/system element |
|---|---|---|
| See category, filter, view templates, VG overrides | ✅ (mapped category) | ✅ |
| Select, hide, override graphics, assign phase | ✅ | ✅ |
| Move / copy / mirror / rotate / delete | ✅ as a rigid body | ✅ |
| Change instance & type parameters | ✅ (the imported ones are user-editable text/number params) | ✅ |
| Change material | ✅ (Paint / material param) | ✅ |
| Schedule & tag (in host, "Include elements in links") | ✅ | ✅ |
| Edit geometry (grips, dims driving size, family editor) | ❌ never | ✅ |
| Swap type with a manufacturer family, keep insertion point | ❌ (no insertion point/rotation to inherit) | ✅ |
| Host to / cut walls, work-plane-based, nested behaviour | ❌ | ✅ |
| MEP connectors, connect wires/conduit, circuits, panel schedules, load calcs | ❌ | ✅ |

Through the link in the host project **everything is read-only** (that is
what a link is). Editing anything means opening the `.ifc.RVT` itself — and
edits there are overwritten on the next reload of the IFC (Revit re-imports
matched-by-GUID elements). Treat the link as coordination geometry + data,
not as an authoring surface. [docs "About Linking to IFC Files"; forum]

---

## 3. The MEP truth: ports, connectors, circuits (answer: never)

- **Verified in source:** `grep` over the entire importer for `Connector`,
  `ConnectorManager`, `ElectricalSystem`, `MEPSystem`, `Circuit` finds only
  enum names and the `IfcDistributionSystem → MEPSystemClassification`
  *string* map used to fill a text parameter. No connector or system creation
  API is called anywhere in `Revit.IFC.Import` [src, exhaustive grep]. Ports are
  DirectShapes with cone arrows (§2 table). Distribution systems are DirectShapes
  with two text params. This holds for the legacy engine and, per its own
  design ("Keeps track of Elements imported (DirectShape/DirectShapeTypes) by
  AnyCAD"), for the hybrid/AnyCAD engine too [src `IFCImportHybridInfo.cs`].
- **Corroborated by Autodesk:** Autodesk's IFC lead (Angel Velez) on the
  official forum: `IfcDistributionPort` is the IFC entity for connectors and
  "Every software application is going to have different functionality in
  regards to being able to show — or use — connectors"; Revit exports only
  *used* connectors [docs SourceForge ifcexporter thread]. Autodesk KB article
  "How to export system connectors to IFC from Revit to make them editable
  after importing them to Revit" exists precisely because they are *not*
  editable — its resolution (per search snippet) is that linked IFC connectors
  "are not editable and do not contain Revit native properties" [search-
  corroborated; article body 403 to fetch].
- **Consequence for the skill:** never promise circuits, wire/conduit
  connections, panel schedules driven by circuits, or load calculations from
  an IFC. Emitting `IfcDistributionPort`/`IfcRelConnectsPorts` costs a few KB
  and gives the user visible flow-direction arrows plus connectivity text
  params (nice for QA/coordination) — but it is documentation, not a
  functioning system. **Tier 2 (real electrical intelligence) is Revit-API
  only:** an APS Design Automation (or desktop add-in) job that places real
  `Electrical Equipment`/`Lighting Fixture` family instances at our IFC
  insertion points, sets the shared parameters, and calls the electrical API
  to create `ElectricalSystem`s (circuits) — or a human doing the same by hand.

---

## 4. Category assignment (which category a class lands in)

Order of precedence in the Link importer [src `Utility/IFCCategoryUtil.cs`]:

1. If an IFC class-mapping file is loaded in **File ▸ Open ▸ IFC Options**
   (`Application.ImportIFCCategoryTable`), `InitFromFile()` parses it and it
   *replaces* the built-in map (tab-separated: `IfcClass [\t PredefinedType] \t
   RevitCategory \t SubCategory`; category value `DontImport` (or "Don't
   Import") excludes the class; unknown class names/categories are logged and
   skipped) [src lines 649–789]. Note the IFC Manual claims the class-mapping
   settings only affect *Open* — the open-source Link code demonstrably reads
   the same file, so treat the manual's statement as describing Autodesk's
   support scope, not the code. When in doubt, leave the mapping file empty and
   rely on the built-in defaults (below), which are already right for us.
2. Else the hard-coded map applies, resolved most-specific-first:
   (class, PredefinedType, ObjectType) → (class, PredefinedType) → class
   [src `GetEntityCategory` / lines 400–650]. The type object's PredefinedType
   is used when the occurrence's is empty/`NOTDEFINED`.

Built-in defaults for our domain (full table: `mep-class-map.md`):
`IfcElectricDistributionBoard(Type)` → **Electrical Equipment**;
`IfcTransformer(Type)` → **Electrical Equipment**; `IfcLightFixture(Type)` →
**Lighting Fixtures**; `IfcOutletType`/`IfcSwitchingDevice(Type)`/
`IfcJunctionBox(Type)` → **Electrical Fixtures**; `IfcCableCarrierSegment` →
**Cable Tray**; `IfcCableCarrierFitting` → **Cable Tray Fitting**;
`IfcCableSegment` → **Conduit**; `IfcDiscreteAccessory(Type)` →
**Specialty Equipment**; `IfcBuildingElementProxy`, `IfcSpace`,
`IfcElementAssembly`, `IfcFlowSegment/Terminal/Controller` (unqualified) →
**Generic Models**. If something lands in Generic Models, the *class* was
wrong at authoring time — fix the tag and re-export; category edits made inside
Revit die on the next reload.

Subcategories: the importer creates per-class subcategories (e.g. under
Generic Models an `IfcSpace` subcategory) and `IfcOpeningElement`s become a
"Voids"-style subcategory whose visibility can be toggled [src
`IFCCategoryUtil.CreateSubCategories`].

---

## 5. Psets → parameters (and the type detail that will bite you)

Mechanism [src `Utility/ParametersToSet.AddParameterBase`,
`Utility/IFCImportCache.ReadSharedParametersFile`, `Data/IFCPropertySet.cs`,
`Data/IFCPropertySetDefinition.CreatePropertyName`]:

- Before import, Revit swaps its shared-parameter file to
  `<name>.ifc.sharedparameters.txt`, ensures groups **"IFC Parameters"**
  (instance) and **"IFC Type Parameters"** (type), and afterwards restores the
  user's original file. Every parameter the importer needs is created as an
  `ExternalDefinition` in those groups (fresh GUIDs from the importer, not
  yours), and bound with an `InstanceBinding`/`TypeBinding` on the element's
  category, in the properties-palette group **"IFC" (GroupTypeId.Ifc)**.
- **Naming:** the default Revit processor names each pset property
  **`<PsetName>.<PropertyName>`** (e.g. `PanelSchedule.PanelName`,
  `Pset_ElectricDistributionBoardTypeCommon.Reference`); on a *type* element
  a `" Type"` suffix is appended to distinguish it. The alternate scheme
  `<PropertyName>(<PsetName>)` is used only by the streamlined/Navisworks
  processor. If two properties collide, the later one becomes `<name> 2`,
  `<name> 3`… [src `CreatePropertyName`, `IFCProperty.Create` lines 252–269].
  **Always confirm the exact displayed names on one imported element before
  binding tags/schedules** — the naming has changed across processors.
- **Typing:** the property's IFC measure/unit picks the Revit spec:
  `IfcBoolean`→Yes/No, `IfcInteger`/`IfcCountMeasure`→Integer,
  `IfcReal`/`IfcNumericMeasure`→Number, `IfcLengthMeasure`→Length,
  `IfcElectricVoltageMeasure`→Electrical Potential,
  `IfcElectricCurrentMeasure`→Current, `IfcPowerMeasure`→Power,
  `IfcLabel`/`IfcText`/`IfcIdentifier`→Text; unit conversion uses the file's
  `IfcUnitAssignment` [src `Data/IFCSimpleProperty.cs`, `Utility/IFCDataUtil`,
  `IFCUnitUtil`]. **So typing our psets correctly at authoring time
  (`IfcElectricVoltageMeasure`, not `IfcLabel '480Y/277 V'`) is what makes the
  Revit parameter a real voltage rather than text.** (The v1 sample got this
  wrong for Voltage — see `docs/inbox/skill-architect.md` §4.)
- Standard always-present params (all instance, group IFC): `IfcGUID`
  (built-in `IFC_GUID`), `IfcName`, `IfcDescription`, `IfcTag`,
  `IfcObjectType`/`ObjectTypeOverride`, `IfcPredefinedType`, `IfcMaterial`,
  `IfcSpatialContainer` (+ GUID), `IfcSystem`, `IfcZone`, `IfcPresentationLayer`,
  `IfcPropertySetList`; types get `IfcName[Type]`, `IfcDescription[Type]`,
  `IfcObjectType[Type]`, `IFC_TYPE_GUID`.
- Project Information gets `Original IFC File Name`, `Original IFC File Size`,
  `Revit Importer Version`, `Revit File Last Updated`, `Import Method` — how
  the importer decides whether the cached `.ifc.RVT` is stale [src
  `Importer.DocumentUpToDate`, `IFCImportOptions.ImportMethodParameter`].

There is **no user-facing "parameter mapping table" on the import side** —
that dialog exists only for export. Import naming is fixed by the code; the
only levers are (a) what we call the pset/properties in the IFC, and (b) how
the host project consumes the auto-generated shared parameters afterwards.
`shared-parameters-mapping.md` gives the procedure.

---

## 6. GlobalId (IfcGUID) and re-import updates

- Each created element/type stores its IFC `GlobalId` in the built-in
  `IFC_GUID` / `IFC_TYPE_GUID` parameter and its `DirectShape.ApplicationDataId`
  [src `IFCGUIDUtil.cs`, `IFCElementUtil.CreateElement`].
- On reload the importer builds `CreateExistingElementMaps` (GUID → element),
  and `UseElementByGUID<T>()` reuses the existing element (same ElementId!)
  when the GUID matches; unmatched old elements are deleted, new GUIDs create
  new elements [src `IFCImportCache`, docs "About Linking to IFC Files": uses
  "IFC GUIDs to match entities in the IFC file with elements in the Revit
  model"]. **Same GUID ⇒ tags, dimensions, and host-side overrides survive the
  reload; new GUID ⇒ orphaned annotations.** This is why the exporter's
  `meta.guidSeed` (stable GUIDs across re-exports of unchanged elements) is a
  first-class requirement.
- The 22-character IFC GUID is a base64-ish compression of a 128-bit UUID
  (`IFCGUIDUtil` converts both ways); keep the mapping deterministic per
  logical element, never per export run.

---

## 7. DirectShape editability facts (reference)

- A `DirectShape` stores externally created geometry (points, curves, solids,
  meshes) in a chosen model category; it is intended "for importing shapes
  from other data formats such as IFC or STEP" and is **not** a substitute for
  a real Wall/family [docs Revit API dev guide "DirectShape"; Rhino.Inside
  guide]. Its geometry has no defining parameters and cannot be edited in the
  UI; API code must rebuild the shape to change it [forum/DevGuide].
- Categories: only "top-level model categories" that pass
  `DirectShape.IsValidCategoryId` — Electrical Equipment, Lighting Fixtures,
  Electrical Fixtures, Conduits, Cable Trays, Specialty Equipment, Generic
  Models etc. are all valid; the importer falls back to Generic Models when a
  mapped category is invalid (`GetDSValidCategoryId`) [src `IFCElementUtil.cs`
  lines 88–101].
- A `DirectShapeType` gives the DirectShape a Revit "type" (name, type
  parameters, shared shape-library geometry). Imported IFC types map 1:1 onto
  these — so `R3 SHARED TYPES` in our exporter directly reduces type
  proliferation inside Revit.
- Room bounding: DirectShapes in wall/floor/roof/ceiling categories can be
  room-bounding (`DirectShapeOptions`); imported spaces are Generic Models and
  do **not** create Revit Rooms/Spaces (place those in the host and let the
  linked geometry bound them if desired) [src `IFCImportOptions` docs,
  category map comment].

---

## 8. Practical implications for the exporter/hardener (the "so what")

Because everything is a DirectShape in the Link route, the levers that
actually move the needle — in order — are:

1. **Correct class + PredefinedType** ⇒ correct category (Electrical Equipment
   vs Generic Models) and correct default schedules/filters. (`mep-class-map.md`)
2. **Solids over facesets** (`IfcExtrudedAreaSolid` etc.) ⇒ real Revit
   `Solid`s: crisp edges, honest dimensions, snappable faces, section/pattern
   fills, far smaller files — vs meshes that look painted and can't be
   snapped to reliably.
3. **`IfcMappedItem` instancing** ⇒ shared `DirectShapeType` geometry,
   drastically smaller `.ifc.RVT`, one edit surface per type.
4. **Real placements** ⇒ elements sit where the transform says; the position
   is baked, but a correct placement is the difference between "the panel is
   at (12.3, 4.1)" and "everything is at 0,0 with offset vertices" for anyone
   dimensioning or later replacing gear with real families at those points.
5. **Typed psets with our shared-parameter names** ⇒ correctly typed Revit
   parameters (voltage as Electrical Potential), and a clean value-transfer to
   the firm's parameters (`shared-parameters-mapping.md`).
6. **Stable GlobalIds** ⇒ reload-safe (annotations survive re-export).
7. **One shared `IfcTypeObject` per real type** ⇒ one `DirectShapeType`, not
   six identical ones.

What no amount of IFC quality fixes: parametric editing, hosting, connectors,
circuits, native panel schedules, insertion-point family swaps. Those are the
Tier-2 (Revit-API) deliverable.

---

## Sources

Autodesk open source (primary evidence; local clone `vendor/revit-ifc`,
commit `f534ad1`, files under `Source/Revit.IFC.Import/`):
- https://github.com/Autodesk/revit-ifc — README ("This contains the source
  code for Link IFC, IFC export, and the IFC export UI").
- `Importer.cs` — routes: `ImportIFC` (`Intent != Reference` → internal
  `IFCImportFile.Import`, else `ReferenceIFC`), sidecar files, GUID matching,
  reload checks. https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Import/Importer.cs
- `Utility/IFCImportOptions.cs` — option keys, `Intent` = Reference/Parametric,
  `Action` = Open/Link, hybrid (AnyCAD) processor selection via revit.ini.
- `Utility/IFCImportHybridInfo.cs` — AnyCAD hybrid engine also emits
  DirectShapes/DirectShapeTypes.
- `Data/IFCProduct.cs`, `Utility/IFCElementUtil.cs` — every product →
  `DirectShape.CreateElement`; types → `DirectShapeType`.
- `Utility/IFCCategoryUtil.cs` — built-in class→category map + class-mapping
  file parser (`InitFromFile`).
- `Data/IFCDistributionPort.cs`, `Data/IFCPort.cs`, `Data/IFCElement.cs`,
  `Data/IFCDistributionSystem.cs` — ports/systems become DirectShapes + text
  params; no connector/circuit creation.
- `Data/IFCRepresentationMap.cs`, `Data/IFCMappedItem.cs` — mapped items →
  DirectShapeType shape library + `DirectShape.CreateGeometryInstance`.
- `Data/IFCExtrudedAreaSolid.cs`, `Utility/TessellatedShapeBuilderScope.cs`,
  `Utility/BrepBuilderScope.cs` — solids vs mesh fallback.
- `Data/IFCBuildingStorey.cs` — storeys → `Level.Create`.
- `Data/IFCPropertySet.cs`, `Data/IFCPropertySetDefinition.cs`
  (`CreatePropertyName`), `Utility/ParametersToSet.cs`,
  `Utility/IFCImportCache.cs` (`ReadSharedParametersFile`) — pset→parameter
  naming, binding, `<name>.ifc.sharedparameters.txt`.
- `Data/IFCImportFile.cs` — Open route calls closed `importer.ProcessIFCProject`
  and posts `IFCPartialSchemaSupport` for IFC4+.
- `Processors/IFCDefaultProcessor.cs` — `ApplyTransforms = true` (placement
  baked into geometry).

Autodesk documentation:
- Link an IFC File (Revit 2026): https://help.autodesk.com/cloudhelp/2026/ENU/Revit-Model/files/GUID-DE8B322A-A507-4E03-93EC-AA21F354E43B.htm
  (three sidecar files; "In Revit 2024.1 and newer, Link IFC uses a new link
  processor by default…").
- About Linking to IFC Files (2024): https://help.autodesk.com/cloudhelp/2024/ENU/Revit-Model/files/GUID-BAA2ED9C-5107-4F21-ABE1-1ACF609AEEE3.htm
  (read-only; GUID matching on reload; snapping/hosting behaviour).
- Open an IFC File (2023): https://help.autodesk.com/cloudhelp/2023/ENU/Revit-Model/files/GUID-21EFC097-96F3-428A-AFA4-BFEA4EDAB3D2.htm
- About Revit and IFC (supported schemas): https://help.autodesk.com/cloudhelp/2023/ENU/Revit-DocumentPresent/files/GUID-6708CFD6-0AD7-461F-ADE8-6527423EC895.htm
  (identical text in the 2026 page).
- Revit API `ImportIFCOptions.LinkProcessor` (Default/Legacy/AnyCAD): https://www.revitapidocs.com/2025.3/898d7fa7-94d7-0010-1148-2de2d741fa1c.htm
- Autodesk IFC Manual — Link IFC: https://autodesk.ifc-manual.com/revit/using-ifc-files-in-revit/link-ifc ;
  Open IFC: https://autodesk.ifc-manual.com/revit/using-ifc-files-in-revit/open-ifc ;
  Using IFC Files in Revit (import options, class mapping, minimal template):
  https://autodesk.ifc-manual.com/revit/using-ifc-files-in-revit ;
  New in Revit 2025/2026: https://autodesk.ifc-manual.com/revit/new-in-revit-2025 ,
  https://autodesk.ifc-manual.com/revit/new-in-revit-2026 ;
  IFC 4.3 support: https://autodesk.ifc-manual.com/revit/advanced-topics-and-best-practices/ifc-4.3-support
- Autodesk KB article titles (fetch blocked by 403; content corroborated via
  search snippets): "What is the difference between Open IFC vs IFC Link in
  Revit"; "How to export system connectors to IFC from Revit to make them
  editable after importing them to Revit"; "IFC Import settings in Revit
  2024/2025" (revit.ini `[ImportIFC] LinkProcessor=Legacy`).
- Angel Velez (Autodesk) on connectors as IfcDistributionPort:
  https://sourceforge.net/p/ifcexporter/discussion/general/thread/21ab0d35/ [forum]
- Revit API developer guide, DirectShape:
  https://help.autodesk.com/view/RVT/2025/ENU/?guid=Revit_API_Revit_API_Developers_Guide_Revit_Geometric_Elements_DirectShape_html ;
  Rhino.Inside "DirectShapes" comparison table:
  https://www.rhino3d.com/inside/revit/1.0/guides/revit-directshapes
- revit-ifc issue #223 (Link vs Open user report) [forum]:
  https://github.com/Autodesk/revit-ifc/issues/223
