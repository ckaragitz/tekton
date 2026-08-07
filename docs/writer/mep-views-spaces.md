# MEP panel schedule views + spaces / rooms / space tags

Stream: `mep-schedules` (wave: MEP CRUD fleet). Module:
`src/rvt/mep/views_spaces.py`. Tests: `tests/test_mep_views_spaces.py`
(14 fast + 1 slow write/verify). Proof harness:
`experiments/mep/schedules/make_views_spaces.py` (proof `.rvt` files under
`experiments/mep/schedules/` and `experiments/mep/spaces/`, plus
`manifest.json` in each). Record: `docs/inbox/mep-schedules.md`.
Confidence tags: **[V]** verified on the corpus / by structural proof,
**[H]** hypothesis (only Autodesk acceptance can judge), **[D]** design
decision.

## 0 · TL;DR

These are the DELIVERABLE-facing electrical elements: a file that arrives
with its panel schedules and its named/numbered spaces is a finished
deliverable, not a bare model.

* A **panel schedule view** is a `PanelScheduleView` (class `0x0b48`,
  `TableView > DBView > Element`) rooting an **8-element owned cluster**
  (Viewer, DBDrawing → Viewport, 2–4 FontElem, CategoryElem → GStyleElem).
  It names its panel by `TableView.m_targetId` and its layout by
  `m_idTemplate` (a `PanelScheduleTemplate`). **The table's cell VALUES are
  computed by Revit on open** — the stored ~150 KB table is layout +
  parameter bindings only (every `TableCellData.m_oCalculatedValue` is
  null, every body data cell's `m_text` is `""`) **[V]**. Creating the view
  cluster rewired to a panel is therefore sufficient
  (`add_panel_schedule_view`) **[H — viewer pending]**.
* An MEP **space** is a `RoomElem` (class `0x0ec8`) with category
  `OST_MEPSpaces` (−2003600); an architectural **room** is the same class
  with `OST_Rooms` (−2000160) **[V]**. It is POINT-placed (`m_point` xy on
  `m_levelId`); its extents/area/volume/loads are computed by Revit's room
  computation from the bounding elements — the corpus's stored solid,
  bounding lists and topology-circuit id are caches (`add_space` emits a
  `SerializedDummy` rep and invalidates the caches) **[H]**. Spaces are
  **zoned**: `m_zoneElementId` ↔ `ZoneElement.m_spaceIds` is TWO-SIDED
  **[V]** (`add_zone` + `add_space` write both sides).
* A **space tag** is a `RoomTag` (class `0x0ecc`) with category
  `OST_MEPSpaceTags` (−2000485), owned by the plan view it is drawn in
  (`m_ownerDBViewId`), pointing at the space through
  `m_taggedRoomElemId.m_linkInstOrHostId` (`add_space_tag`) **[V]**.
* Rename / delete are the manipulate path proven on real elements: a
  space's name/number are the `ROOM_NAME` (−1006900) / `ROOM_NUMBER`
  (−1006901) AString parameters; a schedule view's name is
  `DBView.m_viewName`; deleting a view cascades to its OWNED cluster,
  deleting a space cascades to its tag(s) and neutralises the zone's /
  plan-topology's mentions **[V — 4 proof files]**.

## 1 · Panel schedule views — what a `PanelScheduleView` IS

### 1.1 The element and its references (specimen 742926 'MDP-1', target 742670)

`PanelScheduleView` (`0x0b48`, chain `TableView > DBView > Element`),
seq-102 object ~153 KB, seq-103 `SerializedDummy`, header category
`-2001118`. The fields that matter:

| field | value on 742926 | meaning |
|---|---|---|
| `TableView.m_targetId` | **742670** (a `FamilyInstance`) | **the PANEL this schedule shows** |
| `PanelScheduleView.m_idTemplate` | 638860 | the `PanelScheduleTemplate` ('Branch Panel') |
| `DBView.m_viewName` | `'MDP-1'` | the schedule name (= the panel's name) |
| `PanelScheduleView.m_outOfDate` | `false` | freshness flag (Revit's "update panel schedule") |
| `PanelScheduleView.m_cachedSlotNumbers` | `[0..27, 0]` | cached circuit-slot layout |
| `TableView.m_fontIds` | `[742930, 742933]` | this view's OWN FontElems |
| `TableView.m_colorToCategoryIdMap` | `[{16777216: 742931}]` | this view's OWN CategoryElem |
| `DBView.m_dbDrawingId` / `m_viewerId` | 742929 / 742927 | this view's DBDrawing / Viewer |
| `DBView.m_dbViewTypeId` | 56406 | the shared 'Panel Schedule' `DBViewType` |
| `PanelScheduleView::m_oTableData` | `PanelScheduleData` (4 sections) | the LAYOUT (below) |

All 24 rme panel schedule views follow this exactly (`m_targetId` = one of
the 24 panelboards, template 638860 or 638864 'Switchboard').

### 1.2 The stored table is layout, not values [V]

`PanelScheduleData` (`0x0b41`, `TableData > CellInterface`) carries 4
`TableSectionData` sections: header (10 rows × 7 cols), body (28 rows ×
15 cols on MDP-1), summary (9 × 7), footer (6 × 2). A cell census over the
whole table of 742926:

| section | label texts (`m_cellType 0`) | parameter cells (`m_cellType 2`, `m_paramId`) | data cells (`m_cellType 3`) | `m_oCalculatedValue != null` |
|---|---|---|---|---|
| header | 'Branch Panel:', 'Location:', 'Volts:', 'A.I.C. Rating:', … | −1140078 Panel Name, −1140169, −1140064, −1140080, −1140141, −1140147, −1140139, −1140081, −1140148, −1140082, −1140083, −1140140, −1140149 | 44 empty | **0** |
| body | 'CKT', 'Circuit Description', 'Trip', 'Poles', 'A', 'B', 'C', 'Total Load:', 'Legend:' | −1140053 CKT, −1140054 Description, −1140055, −1140164/5/6 | 336 with `m_text == ""` | **0** |
| summary | 'Load Classification', 'Connected Load', 'Demand Factor', … | −1140068, −1140069, −1140152, −1140153 | 43 empty | **0** |
| footer | 'Notes:' | −1140150 | 10 empty | **0** |

So circuit descriptions, per-phase loads and totals are **never stored**;
they are computed on open from the panel's `RbsElectricalSystem`s. The
consequence for the writer: **creating the view element (with our panel's
circuits already authored by `Document.add_circuit`) is enough** — Revit
renders the table. `m_outOfDate = true` (+ an emptied slot cache) is the
honest state for a schedule whose panel's circuits are not the specimen's;
Revit's schedule updater regenerates the row set. **[H — the primary
proof sets `m_outOfDate = true`; the control proof
`panel_schedule_view_current.rvt` sets it false with the cloned cache, to
isolate the flag if the viewer objects to one.]**

### 1.3 The owned cluster [V]

Ownership = `Global/ElemTable.m_OwningElementId`. The complete cluster of
742926 (all seq-103 reps are `SerializedDummy`):

| id | class | owner | cross-references |
|---|---|---|---|
| 742926 | `PanelScheduleView` | — | `m_targetId=742670`, drawing 742929, viewer 742927, fonts [742930, 742933], category 742931 |
| 742927 | `Viewer` | 742926 | `m_dbViewId = 742926` |
| 742928 | `Viewport` | **742929** | mentions the view + drawing + viewer |
| 742929 | `DBDrawing` | 742926 | `m_viewports = [742928]` |
| 742930 | `FontElem` | 742926 | references the view |
| 742931 | `CategoryElem` | 742926 | references the view + its style 742932 |
| 742932 | `GStyleElem` | **742931** | references the category |
| 742933 | `FontElem` | 742926 | references the view |

(Older views own 4 fonts instead of 2 — a 9-element cluster.) The view's
header `m_deletion` lists {the panel, self, the whole cluster, template,
load classifications 638824/638828, `DBViewType` 56406, phase filter
375, styles 201/55150, phase 86961}; the **panel's own header lists the
view in `m_regenOnly`** (742670 → 742926) — the only referrer of the view
outside its cluster (byte search).

### 1.4 `PanelScheduleTemplate` [V]

`{m_name (AString), m_oTableData (the template layout, 138–825 KB),
m_categoryId}`; rme catalog: 638860 'Branch Panel', 638861 'Branch
Panel 2', 638862 'Branch Panel 1' (−2008145 branch panels), 638863
'Data Panel' (−2008147), 638864 'Switchboard' (−2008146), 639167
'Pre2011 Branch Template'. `panel_schedule_templates(doc)` lists them; a
view is bound to one by `m_idTemplate`.

### 1.5 Plain schedules (`DBViewSchedule`) — READ note

The rme has 15 `DBViewSchedule` (equipment / space / zone schedules,
e.g. 692166 'Electrical Equipment Connection Schedule', 532978 'Space
Schedule', 693070 'Mechanical Equipment Schedule'): a `ScheduleDefinition`-
style object with `m_oTableData` + `m_mainScheduleInstanceIds`, no
per-target id — they QUERY a category, so newly created spaces/panels
appear in them automatically at regeneration. Not authored here (creating
a *new* equipment schedule = the same clone pattern; out of scope).

## 2 · Spaces / rooms — what a `RoomElem` IS

### 2.1 Specimen 379575 (space 'Technology' 28, inside room 573809)

| field | value | new value written by `add_space` |
|---|---|---|
| category (header) | −2003600 `OST_MEPSpaces` (rooms: −2000160) | by `kind='space'|'room'` |
| `m_point` | `[63.6266, 118.2791]` (project ft) | the placement point (must be INSIDE the enclosure) |
| `m_levelId` / `m_upperLevelId` / `m_assocLevelId` | 378117 | the level |
| `m_upperOffset` / `m_height` / `m_lowerOffset` | 12.467 / 12.467 / 0 | the volume height |
| `m_zoneElementId` / `m_zoneSchemeId` | 379574 / 293241 | our zone (or existing / −1) |
| `m_SpaceRoomLocationInfo` | `{m_linkInstOrHostId: 573809}` = the arch ROOM it sits in | `room_id` or −1 |
| `m_volumeBoundingElems` | 7 `RoomBoundingItem`s = the bounding walls | the caller's `bounding_walls` (cache) |
| `m_referenceFaces` (seq-102) | 2 `Face{Plane}` at the point: z = base (tag 226) and base+upperOffset (tag 227) | rebuilt at the new point |
| `m_pPlacement` (`RoomTagPlacement`) | `{ref0 573608, off −4.5589; ref1 573607, off +7.3944}` | anchored to two bounding walls (§2.3) |
| `m_cachedCircuitId` | `{m_id: 39}` → a circuit in `LevelRoomPlan` 379577's `PlanTopology` | `{m_id: 0}` (topology is recomputed) |
| `m_loadPerLoadClass`, `m_dActual*/m_dDesign*/m_dCalculated*` | computed load / airflow caches | zeroed |
| AString params −1006901 / −1006900 | `'28'` / `'Technology'` | `number` / `name` |
| `m_geomSteps` (`RoomElemReferencePlanesStep` + `RoomCreate3dGeometryGStep`) | the regeneration recipe | kept (donor clone) |
| seq-103 | 8.7 KB `GElement` (the computed solid) | **`SerializedDummy`** [H] |

Same class, same field set for rooms and spaces (rooms: zone −1). 165
`RoomElem` in rme = 87 spaces + 78 rooms; 2 rooms are unplaced
(`m_bIsLocationless`, refs −1) — excluded from specimen selection.

### 2.2 Zones [V]

`ZoneElement` (class `0x11e4`, `OST_HVACZones` −2008107): `m_spaceIds` =
the member list (two-sided with each member's `m_zoneElementId`),
`m_phaseId`, `m_zoneSchemeId` 293241, `m_bDefault` (only the project's
'Default' zone **293242** has it, with `m_spaceIds == []` — no sample
space is left in the Default zone, so its membership storage is
unattested), calculated loads/perimeter/ref-point (recomputed). Because
the member list is two-sided and lives on an EXISTING element for
existing zones, `add_space(zone=...)` supports: `'new'` (default — a fresh
`add_zone`, shared by the session, both sides written in-plan), a planned
`NewElement` zone, an existing zone id (**its member list is NOT edited**
— the create path never edits existing records; pair with a modify pass),
or `None` (unzoned, how rooms are stored).

### 2.3 `RoomTagPlacement` offset semantics [V]

`m_offset_i` = the signed perpendicular distance from wall `m_ref_i`'s
location line to the point, **positive to the RIGHT of the wall's drawing
direction**: `(P − start) · (dy, −dx)`. Reproduced exactly for both
anchors of 379575 (wall 573608: −4.5589; wall 573607: +7.3944 —
`test_space_is_roomelem_with_point_zone_and_tag`).
`placement_from_walls` picks the nearest wall + its most perpendicular
partner. The identical placement is mirrored on the space's tag.

### 2.4 Referrers of a space (delete concerns)

Byte search over 379575: the space is mentioned by the fixtures inside it
(their `m_pDesignPropManager.m_idSpace` + header parents), its zone
(`m_spaceIds`), its tag (`m_taggedRoomElemId`), `LevelRoomPlan` 379577
(the level's `PlanTopology` cache) and `AllPlanTopologies` 293355. The
manipulate delete path handles them (tag = annotation dependent,
cascaded; the others = referrers, neutralised).

## 3 · Space tags — what a `RoomTag` IS (specimen 379576)

`RoomTag` (class `0x0ecc`), category −2000485, seq-103 `SerializedDummy`:
`m_ownerDBViewId = 379500` ('Level 1 HVAC Zone Plan', a `DBViewPlan`) —
the tag is view-specific annotation; `m_taggedRoomElemId =
{m_linkInstOrHostId: 379575}`; `m_symbolId = 351633` ('Space Tag'
`FamilySymbol`, a direct symbol — no per-host clone); head at the space
point (`m_oTagOrientationCell.m_headLocation`, `m_isSpatialElementTag =
true`); `m_pPlacement` == the space's; `m_zoneSchemeId`. Header:
`m_ownerViewId = the view`, `m_deletion = {zoneScheme, symbol, view,
space, self, the two placement walls}`, `m_regenOnly = [AreaSettings
85092, the arch room]`, `m_appearanceParents = {symbol, space, room}`.
87/87 rme space tags reference their space this way; 83/87 anchor to 2
`SWall`s, 4 to `CurveElem` (room-separation lines).

## 4 · The API (`rvt.mep.views_spaces`)

```
# create (return planned NewElements; write with commit_elements / commit_new_elements)
add_panel_schedule_view(doc, panel, *, template=None, name=None,
                        out_of_date=True, specimen_id=None) -> [view, ...cluster]
add_zone(doc, *, name=None, level_id=None, template_id=None, phase_id=None) -> zone
add_space(doc, level_id, point, name=None, number=None, *, upper_offset=None,
          upper_level_id=None, lower_offset=0.0, bounding_walls=(), zone='new',
          room_id=-1, phase_id=None, kind='space', template_id=None) -> space
add_room(doc, level_id, point, name=None, number=None, **kw) -> room   # unzoned
add_space_tag(doc, space, *, view_id=None, symbol_id=None, head_offset=(0,0)) -> tag
commit_elements(src_rvt, out_path, doc, elements=None, *, identity=None) -> CommitReport

# modify / delete existing elements (rvt.manipulate plans -> commit_plans)
rename_panel_schedule_view(doc, view_id, name) -> ModifyPlan
delete_panel_schedule_view(doc, view_id, cascade=True) -> DeletePlan
link_schedule_view_into_existing_panel(doc, panel_id, view_id) -> ModifyPlan   # header back-link
rename_space(doc, space_id, *, name=None, number=None) -> [ModifyPlan]
delete_space(doc, space_id, cascade=True) -> DeletePlan

# read
panel_schedule_templates(doc), find_panel_schedule_view_specimen(doc, template_id=None),
owned_cluster(doc, root_id), describe_panel_schedule_view(doc, view_id),
find_space_specimen(doc, level_id=None, kind), space_tags_of(doc, space_id),
placement_from_walls(doc, point, walls), describe_space(doc, space_id)
```

Every create function follows the mutation-plan clone recipe: pick a real
specimen (§5), deep-copy its seq-101 header / seq-102 object (rep =
`SerializedDummy`), mint id(s) above the watermark, rewrite the identity /
placement / reference fields tabulated in §1–3, rebuild `ElementParents`,
and let `check_references` prove closure. The schedule-view cluster is
cloned WHOLE with a **full-tree id remap** (`_remap_all` — needed because
the cluster stores ids under non-`Id` keys such as the `"second"` of the
`m_colorToCategoryIdMap` pairs and inside plain lists) mapping
{specimen cluster → new ids, specimen panel → our panel}; ownership rows
are preserved through the remap.

### 4.1 The ownership hook (`commit_elements`) [D]

`rvt.commit.commit_new_elements` writes every new `ElemRec` with an
INVALID `m_OwningElementId`; the schedule-view cluster's OWNER links (the
delete-cascade signal, §1.3) must be written. `commit_elements` supplies
each plan's `owner_id` to the `elemtable_add_element` that `commit`
imports — a scoped wrapper, so `commit.py` (out of this stream's
territory) is untouched. The equivalent one-line `commit.py` change is
recorded in `docs/inbox/mep-schedules.md` §"Diffs for the orchestrator".

### 4.2 Identity coherence (a cross-stream defect, worked around) [V]

`commit_new_elements` runs the G2 identity scrub, which mints a fresh
`BasicFileInfo` Unique Document GUID **without** recording a new
`Global/History` episode — tripping the validator's L2 rule *"BFI Unique
Document GUID == History entry[0] GUID"* on EVERY file made by the create
path (the older H1..H3 proofs predate the scrub). `commit_elements` keeps
the two coherent by passing `identity={'document_guid': History entry-0
GUID}` (overridable). The proper fix (a new History episode, or the
scrub deferring to the History GUID) belongs to the commit/identity
stream — flagged in the record.

## 5 · Specimen selection [D]

| target | specimen | why |
|---|---|---|
| schedule view | `find_panel_schedule_view_specimen`: a view already on the requested template, else the smallest owned cluster (742926 'MDP-1', 8 elements) | the whole cluster comes along; matching template ⇒ matching layout |
| space / room | `find_space_specimen`: a PLACED `RoomElem` of the wanted category, same level preferred, smallest object | the geometry recipe (`m_geomSteps`) and domain fields are correct by construction |
| zone | a real member-holding zone (379574) — never the Default | keeps `m_bDefault` semantics honest |
| space tag | `_space_tag_specimen`: a real space tag whose space is on the target level (so its view is a plan of that level) | reuses a valid plan view + tag symbol |

## 6 · Proof files (`experiments/mep/schedules/`, `experiments/mep/spaces/`)

Built by `experiments/mep/schedules/make_views_spaces.py`; each is proven
structurally (`verify_written` / `verify_manipulated`: 0 CRC failures, 0
ECC mismatches, 0 walker/ISIZE errors, stamps ok, sentinels last, header
count == ElemTable count, unit-0 ids == ElemTable ids), re-read
semantically (the readback in `manifest.json`), and gated by
`tools/rvt_validate.py` = **VALID, 0 errors** on every file (the same 2
pre-existing warnings the certified H1 file carries: the block A/C
counter identity on 3 spliced blocks — a `commit.py` splice defect — and
the known ES-blob decode gap of the source sample).

| file | verb | what it proves |
|---|---|---|
| `schedules/panel_schedule_view.rvt` | create | NEW 480 V panel 888014 + transformer & receptacle loads + 2 `RbsElectricalSystem` circuits + its `PanelScheduleView` **888019** rewired to the new panel (`m_targetId`), template 'Branch Panel', `m_outOfDate = true`, 8-element cluster with faithful owner links, panel header `m_regenOnly ∋ 888019` |
| `schedules/panel_schedule_view_current.rvt` | create (control) | same, `m_outOfDate = false` + cloned slot cache — flag control |
| `schedules/panel_schedule_view_rename.rvt` | modify | view 709455 'LP-1' → 'LP-1-RENAMED' (`DBView.m_viewName`, byte-exact re-encode of a 153 KB record) |
| `schedules/panel_schedule_view_delete.rvt` | delete | view 709461 'EP-3' + its owned 9-element cluster removed (cascade), the panel's `m_regenOnly` mention neutralised |
| `spaces/space_create.rvt` | create | 4 NEW walls closing a 20×16 ft electrical room + NEW `ZoneElement` 888018 + NEW space **888019** 'ELECTRICAL ROOM' E101 at the room centre (bounding cache = the 4 walls, placement anchored to 2 of them) + its NEW space tag 888020 in 'Level 1 HVAC Zone Plan'; zone lists the space |
| `spaces/space_rename.rvt` | modify | space 379575 'Technology' 28 → 'ELEC EQUIP RM' 128 (both AString params) |
| `spaces/space_delete.rvt` | delete | space 379575 + its tag 379576 (cascade); zone 379574's member list and the plan topology's mentions neutralised |

## 7 · Confidence / unknowns

| claim | status |
|---|---|
| `PanelScheduleView.m_targetId` = the panel; `m_idTemplate` = the template; view = 8-element owned cluster; panel back-links the view in `m_regenOnly` | **V** (24/24 views, byte-search closure) |
| schedule cell VALUES are not stored (all `m_oCalculatedValue` null, body data cells empty) | **V** (full census of 742926) |
| space = `RoomElem` + `OST_MEPSpaces`, name/number = params −1006900/−1006901, zone membership two-sided, tag = `RoomTag` + `OST_MEPSpaceTags` owned by a plan view | **V** |
| `RoomTagPlacement.m_offset` = signed distance, right-of-direction positive | **V** (both anchors of 379575 reproduced) |
| byte-exact codec round trip for every class involved (`PanelScheduleView` 153 KB, `PanelScheduleTemplate`, Viewer/DBDrawing/Viewport/FontElem/CategoryElem/GStyleElem, `RoomElem` 11 KB + its GElement, `RoomTag`) | **V** (40/40 records) |
| a rewired view cluster + `m_outOfDate=true` yields a working panel schedule in Revit | **H — viewer/Revit pending** (control variant provided) |
| a POINT-placed space with a `SerializedDummy` rep inside same-run walls is computed by Revit's room computation on open (no LevelRoomPlan/AllPlanTopologies registration written) | **H — pending**; fallback = author against an existing enclosed room and set `room_id`/`bounding_walls` from it |
| a NEW `ZoneElement` alongside the Default zone is accepted; Default-zone membership storage | **H** (create) / **[open]** (default) |
| space tag placed in the specimen's plan view of the level | **H** (matches 87/87 corpus tags) |
| owner links written by the create hook are what Revit expects for view-owned children | **H** (corpus-identical) |

**Open items:** O1 `BIP_ZONE_NAME` (−1114300) is inferred from the two
zones' values ('1' / '0'); O2 arch-room ⇄ space linkage
(`m_SpaceRoomLocationInfo`) is set only when the caller names the room —
auto-detecting the enclosing room needs a point-in-room test on the room's
solid (its `GElement` outline is available); O3 `HVACLoadSpaceTypeElem`
(space type 584650 'Office - Enclosed') is cloned from the specimen —
expose `space_type_id` when the type catalog is decoded; O4 a NEW
`DBViewSchedule` (equipment/space schedule) is READ-only here; O5 the
schedule view is not placed on a sheet (`Viewport`/`m_sheetViewportElemId`
untouched) — sheet placement is the documentation stream's territory.

## 8 · Reproduction

```
.venv/bin/python experiments/mep/schedules/make_views_spaces.py          # all 7 proof files + manifests
.venv/bin/python -m pytest tests/test_mep_views_spaces.py -q -m 'not slow'  # 14 fast tests
.venv/bin/python -m pytest tests/test_mep_views_spaces.py -q               # + the write/verify test
.venv/bin/python tools/rvt_validate.py experiments/mep/schedules/*.rvt experiments/mep/spaces/*.rvt
```
