# Generation paths: parameterized building spec -> Revit-editable output

Slice: **gen-paths** (Track B / C research). Author: fleet agent, 2026-08-02.
Companion artefacts: `spec/building.schema.json`, `spec/examples/*.json`,
`experiments/gen_ifc_min.py` (+ `experiments/out/min_house.ifc`).

The question this document answers: given the user's requirement that the
whole system be **repeatable and parameterized** (a versioned building spec
JSON in, deterministic Revit-usable model out), which back-ends are worth
building, in what order, and what fidelity each actually delivers **inside
Revit** (native, host-able, schedulable elements vs. dumb DirectShape solids).

Everything below is sourced (URLs inline) or measured locally (the IFC
experiment). Claims without a source are labelled `[hypothesis]`.

---

## 0. TL;DR / recommendation

| Rank | Path | Native-Revit fidelity | Effort now | Cost | Verdict |
|-----:|------|-----------------------|-----------|------|---------|
| 1 | **spec -> our add-in (Revit API) -> .rvt via APS Automation (Design Automation for Revit)** | **Highest**: real `Wall.Create`, hosted doors/windows, floors, roofs, rooms, types, worksharing-safe. Result is a normal editable `.rvt`. | Medium (one C# DB-add-in + APS plumbing; Autodesk's own SketchIt sample is 200 lines) | Metered per processing-hour + storage; free tier for dev | **Primary production path.** |
| 2 | **spec -> IFC (IfcOpenShell)** | Medium: Link IFC = DirectShapes with correct category + params (viewable, taggable, schedulable, **not** parametric). Open IFC (legacy, IFC2x3) *tries* to nativise simple walls/slabs; results are inconsistent. | **Low, and already working today** (`gen_ifc_min.py` emits a valid IFC4 house with door/window voids) | Free (LGPL) | **Build first (Phase 0/1).** Free, fully local, no Autodesk account, and the same spec compiler front-end is reused by path 1. Ship as the default output; the reference geometry oracle for testing the .rvt path; and the fallback when APS is down. |
| 3 | ODA BimRv SDK (write .rvt without Revit) | High-ish for the subset it can create (basic walls line/arc, floors, openings, DirectShape, family forms); newest file version only; **needs a template .rvt**. | High (C++/.NET SDK, sparse docs, template management) | ODA Sustaining membership (US$7.5k first yr, US$4.5k/yr recurring) **plus** the BimRv special module fee | Fallback if APS is commercially/legally unacceptable. Only sanctioned-ish way to write `.rvt` bytes offline. |
| 4 | pyRevit / Dynamo / Revit MCP importer running **inside desktop Revit** | Highest (same API as path 1) | Low code, but needs a human-attended, licensed, Windows Revit seat per run | Named-user Revit licence | Excellent **dev/acceptance harness** (same C# core can be run interactively for debugging), not a headless product. |
| 5 | Speckle / Hypar / xBIM / IFC.js / gbXML | All bottom out in either IFC or DirectShape-style receives; none give better native fidelity than paths 1-2. | - | - | Not primary. Speckle is a good *transport* if the customer already uses it. |

**Recommendation:** two-back-end architecture behind one spec compiler.

```
spec.json --(validate: spec/building.schema.json)--> normalized model IR
     |-- backend ifc  : IfcOpenShell 0.8.5 (python, local)  -> .ifc   [Phase 1, ships now]
     |-- backend rvt  : APS Automation for Revit (cloud)         -> .rvt   [Phase 2]
     |                    reuses the same C# element-creation core we also run
     |                    interactively (pyRevit/RevitAddin) for debugging [Phase 2b]
     '-- backend odarvt: ODA BimRv (offline .rvt bytes)                 [contingency only]
```

The spec, its defaults engine, the deterministic-GUID scheme and the
geometry normaliser (footprint -> per-level shells, opening placement, roof
form) live **once** in the compiler; back-ends only translate the normalized
IR. That is what makes the system repeatable: identical spec + identical
compiler version = identical GlobalIds/element counts on every back-end.

---

## 1. Path A - IFC via IfcOpenShell (Track B)

### 1.1 Installability (measured)

```
$ uv pip install --python .venv/bin/python ifcopenshell
Resolved 8 packages ... Installed 8 packages
 + ifcopenshell==0.8.5   (+ numpy 2.5, shapely 2.1, lark, isodate, ...)
```

A native **mac-arm64 / CPython 3.12 wheel installs cleanly from PyPI**
(`ifcopenshell-0.8.5`, includes the OpenCascade geometry kernel and
`ifcopenshell.geom`). No conda, no source build needed. Wheels exist for
manylinux/x86_64+aarch64, macOS x86_64+arm64, win_amd64, py3.9-3.13
[hypothesis for 3.13; verified locally for 3.12/arm64]. Fallbacks evaluated
anyway (kept for the record, none needed):

- **Pure-python IFC-SPF writing** is trivial (STEP is a text format: header
  block + `#N=IFCENTITY(...);` lines - our own emitted file head is quoted
  in section 1.3). We would lose the geometry kernel (validation by
  tessellation, booleans, `ifcopenshell.validate`). Viable as a zero-dependency
  degraded mode; not needed while the wheel installs.
- `ifcopenshell.api` (used here) is the high-level, MVD-aware authoring API;
  the older BlenderBIM/Bonsai code paths use the same functions.

### 1.2 The experiment - `experiments/gen_ifc_min.py`

Emits `experiments/out/min_house.ifc`: `IfcProject > IfcSite > IfcBuilding >
2 x IfcBuildingStorey`, 4 `IfcWall` forming an 8 x 6 m room (walls span both
storeys), ground + level-2 `IfcSlab`, an `IfcDoor` and an `IfcWindow` each
filling an `IfcOpeningElement` that voids its host wall, units in metres, an
owner history, `Pset_WallCommon`. Then re-opens the file, runs
`ifcopenshell.validate` (schema + EXPRESS WHERE rules) and tessellates every
product with the OCC kernel to prove the openings really cut the walls.

Measured output (from the script's own run):

```
schema=IFC4  entities=342  size=20042 bytes
  IfcWall x4, IfcSlab x2, IfcDoor x1, IfcWindow x1, IfcOpeningElement x2,
  IfcRelVoidsElement x2, IfcRelFillsElement x2, IfcRelContainedInSpatialStructure x2
  schema validation statements: 0 (0 errors)          <- EXPRESS rules pass
   IfcWall  Wall-0  vol=9.2220 m3   <- 8*0.2*6 = 9.6 minus door 0.9*2.1*0.2 = 0.378  OK
   IfcWall  Wall-2  vol=9.2400 m3   <- 9.6 minus window 1.5*1.2*0.2 = 0.36              OK
   IfcSlab  Slab-*  vol=12.0000 m3  <- 8*6*0.25                                       OK
RESULT: PASS
```

Two IfcOpenShell 0.8.5 gotchas found and worked around (documented in the
script): `geometry.create_2pt_wall` builds the body + placement but does
**not** call `assign_representation` (walls came out geometry-less until we
did); and `ifcopenshell.validate(..., express_rules=True)` imports `_pytest`,
so `pytest` must be installed in the venv (it is now).

The whole build is 0.12 s. The compiler front-end for the real spec drops
straight into `build(params)`.

### 1.3 What an IFC-SPF file physically is

Our generated head (verbatim):

```
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition[DesignTransferView]'),'2;1');
FILE_NAME('/dev/null','2026-08-02T18:...','','','IfcOpenShell 0.8.5','IfcOpenShell 0.8.5','Nobody');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPERSON('rvt-recon','Generator','rvt-recon',$,$,$,$,$);
...
#5=IFCOWNERHISTORY(#3,#4,.READWRITE.,.ADDED.,1785712991,#3,#4,1785712991);
```

Plain ASCII STEP - fully diffable, trivially generated, GUIDs are 22-char
compressed IFC GUIDs which we can seed deterministically from the spec `id`s
so re-runs are byte-stable (needed for the "repeatable" requirement and for
Revit's IFC-GUID -> element tracking on re-link).

### 1.4 What Revit actually does with an IFC (fidelity - the crux)

There are **two** import mechanisms with very different results:

**Link IFC (recommended by Autodesk; supports IFC4).** Revit runs the
open-source IFC importer (github.com/Autodesk/revit-ifc, `Revit.IFC.Import`)
which converts the file into an intermediate `<name>.ifc.RVT` project plus
`<name>.ifc.sharedparameters.txt`, and links that RVT into the host. Every
element becomes a **`DirectShape`** (a boundary-rep solid) whose **category is
set from the IFC-class mapping table** (IfcWall -> Walls, IfcDoor -> Doors,
IfcSlab -> Floors ...), with all IFC properties written as shared parameters.
So: correct category, taggable, schedulable, filterable, materials/graphics
overridable - but **not parametric**: no wall type layers, a linked IfcWall
cannot host a new door, cannot be stretched by grips, no room-bounding
behaviour beyond what DirectShapes offer. Since Revit 2024/2025 a "hybrid"
importer routes geometry through the AnyCAD (ATF) toolkit for better solids
but the output object model is unchanged (`Importer.cs` logs "Hybrid IFC
Import ... DirectShapes imported via AnyCAD").
Sources: Autodesk help "About Revit and IFC" - *"For import (link only),
Revit also supports IFC files based on the bSI IFC4 standard"*
(https://help.autodesk.com/cloudhelp/2025/ENU/Revit-DocumentPresent/files/GUID-6708CFD6-0AD7-461F-ADE8-6527423EC895.htm);
importer source https://github.com/Autodesk/revit-ifc/blob/master/Source/Revit.IFC.Import/Importer.cs;
KB "IFC Import settings in Revit 2025"
(https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/IFC-Import-settings-in-Revit-2025.html);
community write-ups: bimcorner IFC export/import guide
(https://bimcorner.com/ifc-exports-from-revit-done-right/), Arkance "elements
missing / limited functionality"
(https://ukcommunity.arkance.world/hc/en-us/articles/21566204744594),
Dynamo forum "IFC DirectShape wall to Revit wall"
(https://forum.dynamobim.com/t/ifc-directwall-shape-to-revit-wall/100216).

**Open IFC (File > Open > IFC, "legacy" import).** Creates a *new* Revit
project from a template and attempts real conversion. Autodesk's own docs
scope it to **IFC2x3/2x2/2x** ("For import (to open or link) Revit supports
IFC2x3, IFC2x2, IFC2x" - same help page above; help "Open an IFC File"
https://help.autodesk.com/cloudhelp/2023/ENU/Revit-Model/files/GUID-21EFC097-96F3-428A-AFA4-BFEA4EDAB3D2.htm),
so **a nativisation-friendly variant of our output should be IFC2X3, not
IFC4**. Behaviour, from Autodesk forum / community consensus (many threads;
representative: forums.autodesk.com "Converting IFC elements into native
Revit elements (IfcWall -> Revit Wall)" and revit-ifc issue #223
https://github.com/Autodesk/revit-ifc/issues/223):

- Simple prismatic **`IfcWallStandardCase`** (SweptSolid extrusion + Axis
  representation, straight or arc) can become **system-family Basic Walls**;
  `IfcWall` with brep geometry becomes an in-place family / generic model.
  Doors and windows in `IfcOpeningElement`s with `IfcRelFillsElement` come in
  as **in-place families** (correct category, not the standard loadable
  M_Door.rfa families, not re-hostable). Slabs -> floors when they are simple
  extruded profiles. Complex or non-manifold geometry falls back to generic
  models. IFC property data largely does **not** survive on the Open path.
- The Open importer is officially "legacy"; Autodesk's guidance and the whole
  community's is *link, don't open*.

**Implication for us:** IFC is the *free, immediate, always-valid* output and
a first-class deliverable (coordination models, non-Revit consumers, our own
regression oracle), but it will **never** yield a fully native, host-able,
type-driven Revit project. If "editable in Revit" means "move a wall grip and
the doors follow", IFC alone does not get there - only the Revit API does
(path B/C below). We should emit **both** IFC4 (link) and an IFC2X3
`IfcWallStandardCase` flavour (open) from the same spec so the user can pick
per model; the schema's `targets.ifc.emitStandardCaseSubtypes` controls this.

### 1.5 Design rules the IFC back-end must follow to maximise Revit nativisation

Encoded in the schema/compiler; each is a Revit-importer preference observed
in the community sources above:

1. Walls: `SweptSolid` extrusion of a rectangular profile + a 2D `Axis`
   representation, gross (uncut) body, `PredefinedType=STANDARD`
   (`IfcWallStandardCase` for IFC2X3).
2. Openings: never pre-cut the wall body; use `IfcOpeningElement` +
   `IfcRelVoidsElement`, filled via `IfcRelFillsElement` (exactly what
   `gen_ifc_min.py` does - verified by the volume check).
3. One `IfcBuildingStorey` per real level; contain elements in the correct
   storey (Revit maps storeys -> Levels).
4. Metric SI, project origin near the model, `IfcOwnerHistory` present, valid
   GUIDs; small negative coordinates avoided (help page above notes Revit
   misplaces geometry with large negative Cartesian values).
5. Common Psets (`Pset_WallCommon`, `Pset_DoorCommon`...) and quantities so
   the linked DirectShapes carry the data Revit surfaces as parameters.

---

## 2. Path B - APS Automation API for Revit (a.k.a. Design Automation) (Track C)

This is Autodesk's **sanctioned headless Revit**: their cloud runs
`revitcoreconsole.exe` (Revit without UI) against our uploaded add-in, so we
get the *real* Revit API - `Wall.Create`, `Document.NewFloor`,
`FamilyInstance` on a host wall, rooms, phases, types - and download a
genuine `.rvt`. **Autodesk ships a sample that is our exact use case:**
SketchIt - "creates walls and floors from an input JSON file" -> `.rvt`
(https://github.com/Autodesk-Forge/forge-sketchit-revit, engine repo
https://github.com/Autodesk-Forge/design.automation-nodejs-sketchIt; cloned to
`vendor/sketchit/` for reference). Its Revit add-in is ~150 lines.

### 2.1 Concepts (Design Automation v3)

| Concept | What it is | Ours |
|---------|-----------|------|
| **Engine** | Cloud Revit version, alias `Autodesk.Revit+2019` ... `+2026` [hypothesis for 2026 availability; 2025 confirmed by community usage] | `Autodesk.Revit+2026` to match our corpus |
| **AppBundle** | Zipped Autodesk `*.bundle` folder: `PackageContents.xml` + `.addin` + our C# DLL implementing **`IExternalDBApplication`** (DB-level only, no UI namespace) that subscribes to `DesignAutomationBridge.DesignAutomationReadyEvent` | `RvtGen.bundle` |
| **Activity** | Job template: command line `$(engine.path)\\revitcoreconsole.exe /al $(appbundles[RvtGen].path)` + named parameters (input JSON, optional template `.rte`, output `.rvt`) | `RvtGenActivity` |
| **WorkItem** | One run: binds each activity parameter to a signed URL (OSS bucket, S3, or an inline `data:` URL for small JSON) + `onComplete` callback | one per spec |

Auth is 2-legged OAuth (client credentials) with `code:all` + `data:read/write`
scopes; artefacts move through APS Object Storage (OSS) signed URLs. The
Revit sandbox has **no interactive session and no arbitrary network access**
- inputs must be declared parameters; results are uploaded by the service.
Docs entry point: https://aps.autodesk.com/en/docs/design-automation/v3/
(tutorial steps `step4-publish-appbundle`, `step5-publish-activity`,
`step6-post-workitem`); code samples list
https://aps.autodesk.com/en/docs/design-automation/v3/code_samples/code_samples/.

### 2.2 The exact `spec JSON -> cloud Revit -> .rvt` architecture

```
                (once, per compiler version)                          (per generation)
 build RvtGen.dll ─┐                                     spec.json ──validate──▶ normalize (python)
                   ├─▶ POST /appbundles + upload zip            │
                   │   POST /appbundles/RvtGen/aliases/prod   ├─▶ upload spec.norm.json ─▶ OSS signedS3upload
 activity json ────┴─▶ POST /activities + alias                │   (or data: URL if < ~60 KB)
                                                              ▼
   POST /workitems {activityId:"nick.RvtGenActivity+prod",
                    arguments:{ specJson:{verb:get,url:...},
                                template:{verb:get,url:..., optional},   # .rte with our types
                                result:{verb:put,url:<signed PUT>},
                                onComplete:{verb:post,url:<our webhook>} }}
                                                              │
                      cloud: revitcoreconsole loads RvtGen add-in
                      OnStartup -> DesignAutomationReadyEvent ->
                        doc = app.NewProjectDocument(UnitSystem.Metric)  or OpenDocumentFile(template.rte)
                        Transaction: Levels, Grids, Wall.Create(doc, curve, wallTypeId, levelId, height, offset, flip, structural),
                                     doc.Create.NewFloor / Floor.Create, FootPrintRoof, FamilyInstance (doors/windows on host wall),
                                     doc.Create.NewRoom, columns/beams (LoadFamily from bundled .rfa if type missing)
                        doc.SaveAs("result.rvt")
                                                              │
   GET result via signed URL / poll GET /workitems/{id} until success ──▶ result.rvt + report.txt
```

Add-in essentials (mirroring SketchIt `SketchIt.cs`, but spec-driven):
- `[Transaction(Manual)] [Regeneration(Manual)] class RvtGenApp : IExternalDBApplication`;
  `OnStartup` registers the ready handler; **no `TaskDialog`, no UI, no
  document dialogs** (they hang the console engine); `e.Succeeded = true`.
- Element creation strictly inside `Transaction`s; group per element class so
  a failure names the offending spec element in `report.txt` (uploaded as a
  second output) instead of failing the whole work item.
- Type resolution order: (1) type name exists in template `.rte` -> use it;
  (2) `types.*.revit.rfaPath` bundled in the appbundle `Contents/families/` ->
  `doc.LoadFamily`; (3) duplicate the template default type and rename.
  This keeps the spec's `types` library the single source of truth.
- Deterministic ids: after creation set `IfcGUID`/a shared `SpecId`
  parameter from the spec `id` so a *second* run against the previous `.rvt`
  can update in place rather than duplicate (Phase 3 idempotent regeneration).
- The same DLL is also loadable by **pyRevit/RevitPythonShell or as a normal
  external command** on a desktop seat -> identical behaviour interactively,
  which is our debugging harness (see path D).

### 2.3 Cost / entitlement

- APS moved to a **Free tier / Paid tier** model effective **2025-12-08**
  (migration deadline 2026-02-18); the Automation API is one of four *rated*
  APIs, metered by **processing time on the Revit engine**. Free tier includes
  a monthly allowance sufficient for development; paid usage is prepaid Flex
  tokens (min purchase 100, 1-yr expiry) or pay-as-you-go.
  Source: https://aps.autodesk.com/blog/aps-business-model-evolution ,
  pricing hub https://aps.autodesk.com/pricing .
- Historical anchors: cloud credits were 6 credits/processing-hour before
  2022; the 2022+ Flex model rated Automation at ~2 tokens/processing-hour
  (~US$3/token list) [hypothesis for the exact current post-Dec-2025 rate -
  Autodesk announced Automation-for-Revit prices "will increase" but the rated
  page is JS-only; **verify on the pricing page before committing**]. A
  small-building work item is ~1-3 min of engine time, so per-model cost is
  cents; the risk is the fixed engine warm-up per work item, so batch many
  variants per work item where possible.
- Entitlement: any APS developer account can create the app; no desktop Revit
  licence is required for cloud runs (that is the point). Output `.rvt` is a
  normal Autodesk file, licence-clean to distribute.

Verification: the acceptance test is opening `result.rvt` in desktop Revit
(user, Windows) - or, headlessly, a second Automation activity that opens the
result and exports IFC + a JSON element census we diff against the spec.

---

## 3. Path C - ODA BimRv SDK (write `.rvt` bytes without any Autodesk software)

The only reverse-engineered-then-commercialised toolkit that **writes**
`.rvt`. Facts from opendesign.com (product page + FAQ, fetched 2026-08-02:
https://www.opendesign.com/products/bimrv , https://www.opendesign.com/faq/bimrv ,
pricing https://www.opendesign.com/pricing):

- Reads Revit 2011+; **writes only the latest version** ("write support to
  the latest version of RFA/RVT only") with "Full Save ... 100% compatible"
  and incremental save. Roadmap lists 2026 file-format support in the
  2025-12 production release, so BimRv tracks the same release we target.
- **Creation is bounded and template-based**: FAQ - *"A template file must be
  used for creation of a new .rfa or .rvt file."* Creatable set: curve
  elements, materials, **basic Wall (line/arc) and openings**, **Floor**,
  DirectShape/FreeForm, family forms (extrusion/void/geom-combination),
  views, grids, dimensions, text, connectors, site surface, parameters.
  Doors/windows are placed by inserting a **FamilyInstance into the opening**
  (families must exist in the template). Roof/room/stair creation is not in
  the published list [hypothesis: not creatable -> use DirectShape or a
  template that already contains them].
- Licensing: BimRv is an ODA **Special Interest Group extension** requiring
  **Sustaining membership or higher plus the BimRv special module** (FAQ).
  Sustaining = **US$7,500 first year, US$4,500/yr recurring** (pricing page);
  the BimRv module fee is quoted per member (not published) [hypothesis:
  low-five-figures/yr all-in]. Free 60-day trial exists for evaluation.
- C++ core with .NET (`BimRv.NET`) wrapper; VS2015-2022 toolchains; runs on
  Linux/mac/Windows [hypothesis for mac-arm64 wheels of the C++ SDK].

Verdict: technically the closest thing to "emit `.rvt` bytes ourselves", and
strategically it de-risks Track D (their existence proves offline `.rvt`
writing is achievable and their capability list is a scoping guide for our
own writer). But five-figure annual cost + template dependence + narrower
creatable set than the real Revit API make it a **contingency**, not the
primary. Worth a 60-day trial in Phase 3 purely to diff a BimRv-written file
against a Revit-written one for Track D research.

---

## 4. Path D - other spec-driven authoring routes (evaluated, not selected)

| Route | Mechanism | Result in Revit | Why not primary |
|-------|-----------|-----------------|-----------------|
| **pyRevit / RevitPythonShell / Dynamo player** reading our spec JSON | Runs in a *live* desktop Revit session; full Revit API (CPython/IronPython or Dynamo graph) | **Fully native** (identical to path B) | Needs an attended, licensed Windows Revit seat per run - fails "headless & repeatable at scale". Ideal as the **interactive dev harness** for the same C# core. |
| Revit "MCP servers" (community `revit-mcp` bridges) | LLM drives a socket into a running Revit add-in | Native | Same seat requirement; nondeterministic (LLM in the loop) - violates repeatability; keep the LLM at the *spec authoring* layer instead. |
| **Speckle** (spec -> Speckle objects -> Revit connector "receive") | Legacy v2 connector could receive `Objects.BuiltElements.Wall` as native walls with type mapping; the current next-gen connector receives models **as DirectShapes** (native mapping is being re-added; "block to families" for loadable-family geometry) - docs.speckle.systems, speckle.community | DirectShape or partially native | Adds a server + connector dependency to get, at best, what path B gives directly. Good *transport* if the customer's team already lives in Speckle. |
| **Hypar** (Elements C#/JSON) | Cloud functions produce an Elements JSON model; `Hypar for Revit` add-in loads it via per-type *converters*, falling back to DirectShape (docs.hypar.io "Converting Revit to and from Hypar", github.com/ParallaxTeam/HyparElementConverters) | Native only where a converter exists | Same converter-authoring work as our add-in, plus SaaS lock-in. Elements' JSON schema is a good design reference for our spec (levels/spaces/functions). |
| **xBIM (.NET) / web-ifc & IFC.js (TS) / IfcOpenShell (chosen)** | Alternative IFC writers | Same as path A - Revit doesn't care who wrote the STEP file | IfcOpenShell has the strongest python authoring API + kernel; the others matter only if we need a browser-side or C# writer. |
| **gbXML** | Green-Building XML: spaces, surfaces, openings for energy tools | Revit *imports gbXML only into an analytical energy model*, and "Insert > gbXML" mass/space import creates **no walls/doors** | Wrong domain (analysis, not authoring). Emit as an *extra* output from the same spec later if energy analysis is wanted (trivial from our IR). |
| Rhino.Inside.Revit + Grasshopper | Grasshopper definition drives Revit API inside Revit | Native | Attended seat + Rhino licence; parametric graph rather than a spec - reject. |

---

## 5. Comparison matrix

Legend fidelity: **N** = native parametric/host-able Revit elements, **D** =
DirectShape (right category + params, no parametrics), **I** = in-place
family, **X** = geometry lost / not created. Cost is marginal per generated
model unless noted. "Verify" = how we automatically check the output.

| Path | Walls | Doors/Wins | Floors/Roofs | Rooms | Types/families | Effort (eng-weeks) | Cost | Dependencies | Verification |
|------|:----:|:----------:|:-----------:|:-----:|:---:|:---:|------|--------------|--------------|
| A1 IFC4 -> **Link** | D | D | D | D (IfcSpace) | X (params only) | **1** (front-end + this back-end) | $0 | python, ifcopenshell wheel | reopen + `ifcopenshell.validate` + tessellation census (done); Revit link smoke test |
| A2 IFC2x3 std-case -> **Open** | N-ish [hypothesis: type-less generic Basic Wall] | I | N-ish / X | X | X | +0.5 | $0 | same | as A1 + one manual Revit open |
| **B APS Automation** | **N** | **N** (hosted family instances) | **N** | **N** | **N** (loadable .rfa) | **3-4** (C# add-in 1.5, APS plumbing 1, harness 1) | free tier -> ~$ per processing-hour | APS account+app, our C# build (needs a Windows CI or the Revit SDK NuGet on any OS to *compile*; Revit itself not needed), OSS bucket | headless: 2nd DA activity opens result, exports IFC + element census JSON, diff vs spec |
| C ODA BimRv | N (basic wall) | N (family instance in opening; families from template) | N floor / X roof | X | template-bound | 4-6 | $12k+/yr | ODA membership + BimRv module, template .rvt, C++/.NET | round-trip open in BimRv reader + census |
| D pyRevit/Dynamo (attended) | N | N | N | N | N | 1 (reuses B's core) | Revit seat | Windows + Revit + human | live inspection |
| E Speckle receive | D (v3) / N (v2) | D / partial | D | X | X | 2 | free / server | Speckle server + connector + attended Revit | census via Speckle API |

Repeatability (identical spec + compiler => identical output): A, B, C = yes
by construction (deterministic GUID seeding); D = yes if unattended-scripted;
E = no (connector versioning + receive settings).

---

## 6. Phased plan

**Phase 0 - done in this slice.** `spec/building.schema.json` v0.1.0 +
examples; `gen_ifc_min.py` proves the IFC back-end end-to-end (valid IFC4,
kernel-verified voids) and validates the examples against the schema.

**Phase 1 - IFC generator (1-2 weeks, all local, $0).** Promote the
experiment to `src/rvt/gen/`: `spec load -> normalize (defaults engine,
footprint auto-shell, level synthesis, opening placement, roof forms) -> IR ->
IfcOpenShell writer`. Deterministic GlobalIds from `sha1(project.number,
element id)`. CLI `rvtgen ifc spec.json -o out.ifc [--schema IFC4|IFC2X3
--standard-case]`. Golden-file tests: tiny/house/office -> committed `.ifc`,
plus the tessellation-census oracle (`{class: count, total volume}`). Ship.
User acceptance: link + open the three examples in desktop Revit once, record
the observed nativisation table in `KNOWLEDGE.md`.

**Phase 2 - APS Automation `.rvt` back-end (3-4 weeks).**
2a: `RvtGen` C# `IExternalDBApplication` consuming the *normalized IR* (not
the raw spec - normalisation stays in python), unit-tested against the Revit
SDK API surface; SketchIt is the template. 2b: python `rvtgen rvt spec.json`
that uploads IR, posts the work item, polls, downloads `.rvt` + `report.txt`.
2c: verification activity (open result -> IFC export + census JSON) so CI
diffs generated-vs-spec with no human. 2d: pyRevit shim running the same
`RvtGen` core interactively for debugging. Exit criteria: house.json ->
`.rvt` with native, grip-editable, host-able elements, verified by census +
one manual open.

**Phase 3 - hardening.** Idempotent regeneration (update-in-place by
`SpecId`), family library management (bundled `.rfa` set matching
`types.*.revit`), template `.rte` per unit system, worksharing, gbXML side
output, ODA BimRv 60-day trial as a Track-D research spike (diff a BimRv-saved
`.rvt` against a Revit-saved one at the `Partitions/` level).

**Explicitly deferred:** direct binary `.rvt` writing (Track D) - the recon
in this repo is what feeds it; paths B/C give us ground-truth `.rvt` pairs
(spec-known content) to accelerate that decode.

---

## 7. Spec design notes (why `building.schema.json` looks the way it does)

- **Everything defaultable except intent.** Minimal legal document:
  `{"storeys": 2, "footprint": [[0,0],[12,0],[12,8],[0,8]]}` (validated as
  `<inline-minimal>` and `examples/tiny.json`). The `defaults` block is the
  one place a designer re-parameterizes an entire building (storey height,
  wall thickness/type, sill height, roof form...).
- **Shorthand expands, explicit overrides.** `footprint` synthesizes exterior
  walls (`auto-N` ids addressable by openings, e.g. `hostWall: "auto-0"`),
  slabs, roof, rooms; explicit `walls`/`floors`/`roofs` replace autos for the
  levels they touch (see `examples/house.json`: auto shell + explicit
  partitions + explicit gable roof).
- **Levels vs storeys.** Integer `storeys` for the 90% case; explicit `levels`
  (with non-storey datums allowed) when elevations are irregular. Walls carry
  Revit's real constraint model (`level`/`baseOffset`/`topLevel`/`topOffset`
  or unconnected `height`) so the `.rvt` back-end produces constrained walls,
  not unconnected ones.
- **Type library with dual identity.** Each type has an open-format
  description (`layers`/materials/dimensions - what IFC needs) *and* a
  `revit` block (system-family type name or family+type+`rfaPath` - what the
  Revit API needs). Undefined names fall through to "look it up in the
  template" so specs stay small.
- **Grids + grid-referenced columns** (`"grid": "1/A"`, `examples/office.json`)
  because structural regularity is where parameterization pays most.
- **`targets` isolates back-end knobs** (IFC schema/MVD/standard-case
  toggle; Revit engine/template/units) so the abstract building never
  changes to please an exporter.
- **Versioned** (`specVersion`, semver; generator rejects unknown MAJOR),
  `additionalProperties:false` everywhere so typos fail loudly - both are
  what "stable, repeatable input" requires.

## 8. Sources index

- Autodesk help, About Revit and IFC (open = IFC2x3-, link adds IFC4):
  https://help.autodesk.com/cloudhelp/2025/ENU/Revit-DocumentPresent/files/GUID-6708CFD6-0AD7-461F-ADE8-6527423EC895.htm
- Autodesk help, Open an IFC File (new project from template, class-mapping
  file, join options, log file):
  https://help.autodesk.com/cloudhelp/2023/ENU/Revit-Model/files/GUID-21EFC097-96F3-428A-AFA4-BFEA4EDAB3D2.htm
- Revit IFC importer source (link path -> `.ifc.RVT` DirectShapes; hybrid
  AnyCAD import): https://github.com/Autodesk/revit-ifc ,
  `Source/Revit.IFC.Import/Importer.cs`; issue "IFC Import - Link vs Open":
  https://github.com/Autodesk/revit-ifc/issues/223 ; issue "IFC walls are
  just generic models": https://github.com/Autodesk/revit-ifc/issues/571
- Autodesk KB, IFC Import settings in Revit 2025 (legacy vs new engine):
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/IFC-Import-settings-in-Revit-2025.html
- Autodesk forum, "Converting IFC elements into native Revit elements
  (IfcWall -> Revit Wall)":
  https://forums.autodesk.com/t5/revit-architecture-forum/converting-ifc-elements-into-native-revit-elements-e-g-ifcwall/td-p/13424280
- bimcorner, IFC exports from Revit done right: https://bimcorner.com/ifc-exports-from-revit-done-right/
- Autodesk IFC manual (use minimal template; exclusion applies to open only):
  https://autodesk.ifc-manual.com/revit/using-ifc-files-in-revit
- APS Design Automation v3 docs: https://aps.autodesk.com/en/docs/design-automation/v3/
  ; code samples https://aps.autodesk.com/en/docs/design-automation/v3/code_samples/code_samples/
  ; Revit Automation API product page https://aps.autodesk.com/apis-and-services/revit-automation-api
- SketchIt sample (JSON walls/floors -> .rvt, our reference architecture):
  https://github.com/Autodesk-Forge/forge-sketchit-revit ,
  https://github.com/Autodesk-Forge/design.automation-nodejs-sketchIt (vendored `vendor/sketchit/`)
- APS business-model change (free/paid tiers, Flex, dates): https://aps.autodesk.com/blog/aps-business-model-evolution
- ODA BimRv product / FAQ / pricing: https://www.opendesign.com/products/bimrv ,
  https://www.opendesign.com/faq/bimrv , https://www.opendesign.com/pricing
- Speckle Revit receive behaviour (DirectShape settings, block-to-families):
  https://docs.speckle.systems/legacy/user/revit/advanced-settings ,
  https://speckle.community/t/native-element-creation-only-shows-directshape-under-mappings/16712
- Hypar <-> Revit converters: https://docs.hypar.io/a970443a23d441fba11e38b0b4811ab4 ,
  https://github.com/ParallaxTeam/HyparElementConverters
- IfcOpenShell python API (0.8.5) - used and version-pinned in `gen_ifc_min.py`;
  PyPI wheel for macOS arm64 py3.12 verified installable.

## 9. Unknowns

1. Exact post-2025-12 Automation-API rate for the Revit engine (page is
   JS-rendered; confirm on https://aps.autodesk.com/pricing before Phase 2)
   and whether the `Autodesk.Revit+2026` engine alias is already live.
2. Precise element table produced by **Open IFC (legacy)** on Revit 2026 for
   our specific output (which combos become Basic Wall vs in-place vs
   generic) - needs one attended run of `min_house.ifc` (and an IFC2X3
   `IfcWallStandardCase` variant) on the user's Revit. Everything in section
   1.4's Open bullet list is community-sourced `[hypothesis until run]`.
3. Whether the 2025+/2026 "new" (AnyCAD) open path changes any of that
   (settings dialog offers Legacy vs new engine).
4. ODA BimRv module price and whether roofs/rooms are creatable (not in the
   published list); mac-arm64 availability of the C++ SDK.
5. Design Automation work-item processing-time ceiling for Revit (docs quote a
   configurable `limitProcessingTimeSec`; the current maximum is unverified
   here) - relevant only for very large batch specs.
6. Family availability inside the cloud engine: only what the template `.rte`
   and our bundled `.rfa`s contain - the metric M_* families named in the
   schema defaults must be shipped, not assumed present.
