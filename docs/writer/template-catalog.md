# Template catalog — seed documents and their instantiable ids

Agent: `mutation-planner`. Generated from the corpus by the
schema-directed decoder (regenerate: `rvt.mutate.Document.levels()`,
`.symbols(category)`, `.wall_types_with_instances()`; the ad-hoc dump
script is `catalog.py`, see mutation-plan §11). All ids are the
**ElementIds inside the named template file**; they are the referents a
cloned element points at (`m_assocLevelId`, `m_WallAttributesId`,
`InstanceInfo.m_symbolId`, `m_createdPhaseId` …). A new element may only
reference ids that exist in ITS template — never mix templates.

## 1. Template strategy — DECISION

**Two seed documents, chosen by discipline:**

| output | seed template | why |
|---|---|---|
| architectural (levels, grids, walls, doors, rooms) | `racbasicsampleproject.rvt` | small (39 MB raw / 85,814 records), 100 % clean decode, real levels/grids/wall types/door families, plain non-workshared file, accepted by the viewer as a re-containered file (KNOWLEDGE "Container writing — SOLVED") |
| electrical / MEP (panelboards, receptacles, lighting, circuits, spaces) | `rmebasicsampleproject.rvt` | the only sample with electrical infrastructure: 32 electrical-equipment symbols (panelboards 208/480 V MLO/MCB, transformers, switchboards), receptacles, lighting fixtures, 187 real `RbsElectricalSystem` circuits, MEP Spaces, `ElectricalSetting`, voltage/distribution types — everything a circuit needs already exists as elements |

A "generated" file = the seed with (a) unwanted host-document elements
removed later (subtraction, phase 2) and (b) new host-document elements
inserted (this plan, phase 1). Phase 1 never touches the embedded family
documents, so **every loaded family/type below is available to the
writer for free** — the family definitions (geometry, connectors,
parameters) travel inside their embedded-document units, copied verbatim.

Rules the writer must follow (from mutation-plan):

1. Reference only ids present in the SAME template's element table.
2. Instantiate a type only via the pattern its category uses in the corpus
   (§3 free/level, §4 face-hosted, §5 host-cut).
3. A wall type is CLONABLE only if the template already contains a
   straight wall of that type (the clone donor supplies the correct
   compound-structure ref-face offsets and param set) — the
   `wall_types_with_instances()` set. Other listed types need a donor first
   (open work).

## 2. `racbasicsampleproject` — architectural seed

### 2.1 Levels (host document, `Level` 0x09e7, type `LevelAttributes` 305)

| ElementId | name | elevation ft (m) | notes |
|---:|---|---:|---|
| 311 | Level 1 | 0.000 (0.00) | project datum; `m_isBuildingStory` |
| 694 | Ceiling | 8.858 (2.70) | |
| 245423 | Level 2 | 9.843 (3.00) | |
| 196629 | Roof Line | 19.685 (6.00) | |
| 511122 | Foundation | −2.625 (−0.80) | |
| 515270 | Level 1 Living Rm. | −1.804 (−0.55) | |
| (800333) | Level 1 | 0.000 | owned by in-place family 800214 (`m_unplacedOwnerId`) — NOT a project datum; excluded from `levels()` |

Elevation = `Level.m_pSurface -> Plane.m_origin[2]` (feet). Phase created:
`ProjectPhase` element **86961** ("Working Drawings" — the `m_createdPhaseId`
of walls/doors here; the same id names phase "New Construction" in the
rme seed). All project levels share `LevelAttributes` **305** ("8mm
Head"); grids share `GridAttributes` **341** ("6.5mm Bubble").

### 2.2 Wall types (`BasicWallType` 0x025b, name = `SymbolInfo.m_name`)

Instances = straight `GLine`-driven `SWall`s of that type present in the
file (the clone donors). **Only types with ≥ 1 instance are clonable
today.**

| ElementId | name | straight instances (donors) |
|---:|---|---:|
| 232827 | Interior - Partition | 15 (e.g. 429964, 430859, 506386) |
| 458927 | SIP 202mm Wall - conc clad | 8 (704275, 709245, 846939 …) |
| 198367 | Wall - Timber Clad | 8 (422243 = door specimen host, 427092 …) |
| 600634 | CL_W1 | 8 (493612, 628450 …) |
| 711906 | Retaining - 300mm Concrete | 9 (599841, 745997 …) |
| 428955 | SIP 202mm Wall - conc clad (alt id) | 4 |
| 232754 | Interior - 165 Partition (1-hr) | 4 |
| 845480 | Cavity wall_sliders | 1 (977133) |
| 581500 | Foundation - 300mm Concrete | 1 |
| 397 | Exterior - Brick on Mtl. Stud | **0 — not clonable yet** |
| 54538 | Exterior - Block on Mtl. Stud | **0 — not clonable yet** |
| 54537 | Exterior - Brick Over Block w Metal Stud (`StackedWallType`) | stacked — out of scope |

(Also 4 in-place/embedded wall types 1009153/1055052/1047173/1039948
belong to nested family editors — do not use.)

### 2.3 Doors and windows (host-cut families — PHASE 2)

Every door/window instance in the corpus (`OST_Doors` −2000023 ×16,
`OST_Windows` −2000014 ×17) references a **per-host-thickness geometry
symbol clone** (`InstanceInfo.m_symbolId` ≠ `m_masterSymbolId`; the clone
is a `FamilySymbol` with empty name carrying the wall-opening cut loops).
Placing a door therefore needs the master type below **plus** a clone
symbol; the clone can be *shared* with an existing door of the same type
in a wall of the same type (then only the instance is new).

| master symbol | type name | family | family name | existing cut clones (reusable) |
|---:|---|---:|---|---|
| 232780 | 800 x 2100 | 218942 | Single-Flush | 490150 (in "Wall - Timber Clad" wall 422243), 235155, 425293, 431054 |
| 907609 | 1730 x 2134mm | 907033 | M_Double-Flush | 907638 |
| 505854 | 2.027 x 0.945 | 768490 | Pocket_Slider_Door_5851 | 769882, 940117 |
| 866105 | Entrance door | 930303 | Entrance door | 978895, 978910 |
| 910850 | Curtain Wall Dbl Glass | 910123 | Curtain Wall Dbl Glass | 910875 (curtain-panel door) |
| 198366 | Standard (window) | 800493 | Single Window | 818872–818875, 850328 |
| 488864 | 1180 x 1170mm (skylight) | 488274 | M_Skylight | 507058 |

### 2.4 Free-standing families (phase-1 instance recipe: symbol == master)

Placeable with `add_family_instance(symbol_id, level_id, position, rotation)`
(pattern verified on 202/495 racbasic instances):

| symbol | type name | family | category |
|---:|---|---|---|
| 776839 | SunModule SW 245 Silver Mono - 10 Deg. Angle | 772394 Photovoltaic-Panel-SolarWorld | ElectricalEquipment −2001040 |
| 754016 / 802440 | Cooper RSA Profile track / Litecontrol Mod66 pendant | 850938 / 812025 | LightingFixtures −2001120 |
| 990191 / 988018 / 989329 / 735724 / 984471 / 985723 / 997883 | dining chair, bar chair, dining table, lounge chair, cabinet, TV, side table | 989737 / 987233 / 990657 / 732643 / 983520 / 984988 / 997194 | Furniture −2000080 |
| 690047 / 692863 | 4500_Kitchen Island / _DW | 687633 / 690464 | Casework −2000100/−2001000 |
| 697575 | hood enclosure | 697447 | Furniture systems −2001100 |
| 674355 / 680524 / 287141 … | Miele washing machine, cooktop, wall-hung WC | 673141 / 679176 / 285361 | GenericModel −2000151, SpecialityEquipment −2001350 (677680 dryer, 678974 rangehood, 684776 fridge) |

Full symbol table per category: `Document.symbols(category)`.

### 2.5 Rooms

`RoomElem` (14 in the file: 857191–857552, 906922, 940325) — category
`OST_Rooms` −2000160; specimen `rac_room_857346_RoomElem.json`. Room
creation is phase 2 (needs a bounded region + `RoomBoundaryElem` topology).

## 3. `rmebasicsampleproject` — MEP / electrical seed

### 3.1 Levels (type `LevelAttributes` 305)

| ElementId | name | elevation ft (m) |
|---:|---|---:|
| 378117 | Level 1 | 0.309 (0.094) |
| 378118 | Level 2 | 12.467 (3.800) |
| 378119 | Level 3 | 23.950 (7.300) |
| 378120 | Roof Level | 35.761 (10.900) |

(The ~150 further `Level` records named "Ref. Level" / "Ground floor" /
"Referenzebene" belong to the embedded family documents (save units
1..305) — they are NOT host-document elements and must never be
referenced by host elements.)

### 3.2 Wall types (clonable = have straight instances)

| ElementId | name | donors | ElementId | name | donors |
|---:|---|---:|---:|---|---:|
| 563416 | MW 11.5 | 61 | 563418 | STB 25.0 WD 12.0 | 1 |
| 563417 | MW 17.5 | 29 | 563456 | STB 30.0 Rot | 2 |
| 563414 | STB 20.0 | 18 | 563463 | Lamelle 11.5 | 7 |
| 563404 | STB 30.0 | 8 | 563468 | WC Trennwand 5.0 | 7 |

(397 / 54538 / 54537 = the same template-born exterior types as racbasic;
no straight instances here either.)

### 3.3 Electrical equipment symbols (`OST_ElectricalEquipment` −2001040)

The panelboard / transformer / switchboard types the writer can
instantiate. Panelboards are **face-hosted** (§4 of mutation-plan): the
instance references a `SketchPlane` element on the host wall face; four
existing SketchPlanes are shared by multiple panels and can host new ones
(**471504** ×3, **455739** ×3, **581481** ×4 = panels 581482–581485,
**623305** ×2, **624770**, **625760**, **626178**, **691564**, **692964**).

| symbol | type name | family | family name |
|---:|---|---:|---|
| 455409 | 400 A | 454674 | M_Lighting and Appliance Panelboard - 208V MLO - Surface |
| 470440 | (unnamed clone of 455409) | 454674 | M_Lighting and Appliance Panelboard - 208V MLO - Surface — used by panels 581483–581485, 471580, 471596, 503195, 503251 |
| 454655 / 454659 | 125 A / 400 A | 453921 | M_Lighting and Appliance Panelboard - 480V MLO - Surface |
| 470469 / 471762 | (clones) | 453921 | 480V MLO |
| 619611 / 619613 / 619615 / 619617 | 100 A / 125 A / 250 A / 400 A | 741874 | M_Lighting and Appliance Panelboard - 480V MCB - Surface |
| 742645 | (clone of 619611) | 741874 | 480V MCB |
| 620368 / 620370 / 620372 | 100 A / 225 A / 400 A | 619639 | M_Lighting and Appliance Panelboard - 208V MCB - Surface |
| 621226, 621228, 621230, 621232, 621234, 621236, 621238, 621240, 621242, 621244 | 15 / 45 / 30 / 75 / 112.5 / 150 / 225 / 300 / 500 / 750 kVA | 674651 | M_Dry Type Transformer - 480-208Y120 - NEMA Type 2 |
| 621984 / 621986 / 621988 / 621990 / 621992 | 3 / 6 / 9 / 15 / 30 kVA | 621257 | M_Dry Type Transformer - 480-208Y120 - NEMA Type 3R |
| 629944 / 629946 / 629948 | 610x660 / 762x965 / 914x965 mm | 680819 | M_Circuit Breaker Switchboard |

Existing panel instances (naming source for circuits): panel names such
as `PP-1B`, `LP-2B`, `MDP-1`, `TP-1B` are the `RBS_ELEC_PANEL_NAME` string
parameter on the FamilyInstance (in `m_pParamValueSetAString`), and the same
string appears as the feeding circuit's `m_strDescription`.

### 3.4 Electrical fixtures and lighting

| symbol | type name | family | pattern |
|---:|---|---|---|
| 342654 / 342652 | Standard / GFCI | 689475 M_Duplex Receptacle | **symbol == master**, wall-face hosted (host = wall id, e.g. 467291 on wall 467294) |
| 469253 | Plain | 694138 M_Quadruplex Receptacle | wall-face hosted |
| 365612 | 600x600 - 277 | 365618 M_Plain Recessed Lighting Fixture | ceiling-hosted |
| 433674 / 435190 | 100W - 277V / 60W - 277V | 432871 pendant disk / 434429 sconce | face-hosted |
| 446386 / 446390 | 1200mm / 2400mm - 277V | 445471 M_Pendant Light - Linear - 2 Lamp | face-hosted |

### 3.5 Circuits, spaces, settings (referenced, not instantiated)

| element | ids | use |
|---|---|---|
| `RbsElectricalSystem` (circuit) | 187 in file, e.g. 469428 "Power Technology 28" (9 receptacles + panel 581483), 623656 "PP-1B" feeder | clone donor for a NEW circuit: rewrite `m_pConnectorMgr->RbsSystemConnectorManager.m_connPtrArray[].m_arrRefs[].m_id` (loads at `m_nIndex 1 / m_connType 1`, the panel at `m_nIndex 50000+n / m_connType 4`), `m_number`, `m_strDescription`, load figures |
| `RoomElem` spaces | 379575 (contains panels 581483…), 573809-linked room, 293241, 573302, 573390, 573607 … | `ElectricalFamInstDesignPropertyManager.m_idSpace / m_idRoom` on instances |
| `RbsVoltageType` | 55359, 277806 ("240"), … | referenced by distribution systems |
| `RbsDistributionSysType` | 277809 ("120/240 Single") | referenced by panel design props |
| `ElectricalSetting` | 639116 | project-wide electrical settings (single element, do not clone) |
| `ProjectPhase` | 86961 ("New Construction") | `m_createdPhaseId` of instances |

## 4. What is NOT instantiable from these templates (needs a family LOAD first)

Any family/type absent from the seed. Loading a new family = writing a
NEW embedded content document (a Partitions save unit + a
`Global/ContentDocuments` entry + `Family`/`FamilySymbol` host elements +
the family document's element table) — a far larger operation than
placing an instance of a loaded one. Product implication: the building spec
should map its abstract types onto the seed's loaded types (this catalog),
and the seed should be pre-loaded (once, in real Revit) with every family
the product line needs, then re-extracted. This is the leverage point for
the brothers' Revit seat: **curate one rich seed template**, not code a
family loader.

## 5. Cross-template facts

- ElementIds are unique across the whole file (host document AND all
  embedded family documents share one id space; 142,174 rme records, 0
  duplicate ids). New ids must therefore exceed the FILE-WIDE watermark
  (`Global/ElemTable` footer `IdentifierSource.m_last`), which is what
  `Document.next_id()` does.
- Both seeds are template-born from the same Autodesk ancestor: they share
  low ids (categories 1…, `LevelAttributes` 305, `Phase` 86961, wall types
  397/54538) but they are NOT supersets of each other (racbasic ∩ racadv =
  1,588 of 8,401 ids). Never assume an id from one template exists in
  another; always resolve through the catalog.
