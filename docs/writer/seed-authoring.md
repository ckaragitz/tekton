# Firm-seed authoring — running the writer on the customer's own standards

Status: name resolution SOLVED and shipped (`src/rvt/inventory.py`); seed
readiness audit shipped (`tools/seed_audit.py`). Verified against the
three Revit 2026 samples (rme / rst / rac).

## Why a seed

Until now every generated `.rvt` was authored ON TOP of Autodesk's sample
projects (`rmebasicsampleproject.rvt` etc.). That works technically (the
writer clones a placed specimen and re-commits it) but ships Autodesk's
demo content, German-named wall types and metric library families — not
the customer's standards, titleblock, view templates or families.

A **firm seed** replaces the sample: the firm exports ONE small project
from THEIR licensed seat containing their standards and one placed
instance of every family they build with. From then on every job authors
on the seed with zero Autodesk seat/APS in the creation path; the file only
returns to a licensed engineer's Revit for final QA.

The two blockers were (1) the writer could not see the seed's content —
wall types / symbols / categories came back nameless ("?"), so
`spec_to_rvt.discover_template` could not find a job's `"Painted CMU 8in"`
wall or a specific panel family by name; and (2) a firm had no way to know
whether its seed was complete. Both are addressed below.

## 1. Where names live (verified, all three samples)

| thing | class | field | notes |
|---|---|---|---|
| level | `Level` | `m_text` | elevation = `m_pSurface.m_origin.z` (ft) |
| family symbol / type | `FamilySymbol`, `*Type`, `*Attr(ibutes)` | `m_symbolInfo.value.m_name` | see clones below |
| family | `Family` | `m_name` | 100% present |
| wall type | `BasicWallType`, `StackedWallType`, `CurtainWallType` | `m_symbolInfo.value.m_name` | thickness = Σ `m_pCompoundStructure.value.m_layers[*].m_layerWidth` (ft) |
| view | `DBView*` | `m_viewName` | templates: `m_isTemplate == True` |
| panel schedule template | `PanelScheduleTemplate` | `m_name` | |
| material | `MaterialElem` | `m_pMaterial.value.m_name` | |
| phase | `ProjectPhase` | `m_name` | order from `AllProjectPhases.m_phaseIds` |
| room / space | `RoomElem` | AString params `-1006900` ROOM_NAME, `-1006901` ROOM_NUMBER | |
| placed panel | `FamilyInstance` | AString param `-1140078` RBS_ELEC_PANEL_NAME (e.g. `PP-2B`), `-1001203` Mark | |
| category | header (seq 101) `m_categroryId` | built-in table / `CategoryElem` | see §3 |

### The "nameless symbol" mystery — geometry clones

`m_symbolInfo.m_name` is genuinely EMPTY for 445 of the 632 `FamilySymbol`
records in the rme sample (58/106 rst, 45/142 rac). Those are not real
types: they are **per-instance geometry clones**. Every clone has
`m_masterId` -> the named master symbol (masters have `m_masterId == -1`).
Placed instances point at the clone via `m_pInstanceInfo.value.m_symbolId`
and at the master via `m_masterSymbolId` (e.g. rme instance 471580 'EP-2':
symbol 470440 = clone, master 455409 =
`M_Lighting and Appliance Panelboard - 208V MLO - Surface :: 400 A`,
host = a `SketchPlane`, i.e. face-hosted). This matches KNOWLEDGE's
"per-host geometry-symbol CLONE" for doors/windows — MEP fittings and
face-hosted gear do it too.

Rule implemented in `family_and_symbol_names()`: if a symbol's own name is
empty, follow `m_masterId` (up to 8 hops) to the master's name and family.
`inventory.symbols(masters_only=True)` reports the TRUE type catalog and
counts each master's placed instances by resolving every instance to its
master.

### Name-resolution scoreboard (`python -m rvt.inventory --stats`)

```
project                     levels  walltypes wt thick  symbols sym named fam named  clones clone->name inst named
rmebasicsampleproject        4/4     11/11      10/11       187  187/187   187/187    445   445/445    400/400
rstbasicsampleproject        9/9      4/4        3/4         48   48/48     48/48      58    58/58     400/400
racbasicsampleproject        6/6     11/11      10/11        97   97/97     97/97      45    45/45     400/400
```

**100 % of wall types and 100 % of family symbols (masters AND clones) get
real names on all three samples**; 100 % of levels; every master symbol
gets a family name and a resolved category. (The single wall type without a
thickness per file is the `StackedWallType`, which has no compound
structure of its own — correct.) Every one of rme's 187 master symbols and
rac's 97 resolves to a VERIFIED built-in category; rst has one unknown id
(`-2008165`, a steel "Notch" modifier).

## 2. `src/rvt/inventory.py` — API

```python
element_name(doc, eid) -> str | None          # any element, never invents
type_name(doc, type_id) -> str | None         # symbol/type name (clone-aware)
family_and_symbol_names(doc, symbol_id) -> (family, symbol)
category_name(doc, cat_id) -> str | None      # 'OST_ElectricalEquipment' / file name
category_label(doc, cat_id) -> str | None     # 'Electrical Equipment'
category_source(cat_id) -> 'builtin-verified' | 'builtin-assumed' | 'file' | 'unknown'
inventory(doc) -> {
  levels:      [{id, name, elevation_ft, is_building_story}],
  wall_types:  [{id, class, kind, name, family, thickness_ft, walls_using}],
  symbols:     [{id, family, symbol, category_id, category, category_label,
                 placed_instances, hosting_pattern(free|face|host-cut), is_clone}],
  titleblocks: [{id, family, symbol, placed_instances}],   # OST_TitleBlocks (-2000280)
  view_templates: [{id, class, name}],                    # m_isTemplate views + panel schedule templates
  phases:      [{id, name, description, sequence}],
  stats:       {...% named, category sources...}
}
```

`walls_using` / `placed_instances` matter for authoring: the writer clones
a PLACED specimen, so a named type with zero placements is only a name.
`hosting_pattern` is the majority pattern of a symbol's real instances
(`m_workPlaneBased` -> `face`; `m_hostId != -1` -> `host-cut`; else
`free`), falling back to the family's flags (`m_isWorkPlaneBased`,
`m_bIsHostBased`) when nothing is placed. rme confirms KNOWLEDGE: every
panelboard type is `face`, floor transformers/switchboards are `free`.

Works on the research corpus (`Document.load("rmebasicsampleproject")`)
and on any file (`Document.from_file(path)`, ~2 s for rme).

## 3. Categories — the built-in enum table

Category ids are the header's `m_categroryId`. Negative ids are Autodesk's
fixed public `BuiltInCategory` enum (`OST_*`). **The `.rvt` file contains
NO id->name table for built-in categories** — verified: no `OST_` string in
any inflated stream; `CategoryTable` (0x2e6) holds only `m_pADoc`;
`IFCBuiltInCategoryKey` holds only ElementIds; the `ExportIFCCategoryKey`
name table (`IFCCategoryTemplate`) has zero instances. So a table of the
public constants is embedded, split by evidence:

* `BUILTIN_CATEGORIES_VERIFIED` (~100 entries) — each id's element class and
  example type name in the samples corroborate the meaning (e.g. `-2001040`
  hosts panelboards/transformers, `-2008128` hosts
  `Conduit Body - Type L :: Standard`, `-2003000` hosts profile families).
  Covers 100 % of the master symbols in all three samples.
* `BUILTIN_CATEGORIES_ASSUMED` — public constants recalled from the API docs
  but not exercised by any sample element (cable tray/conduit curves, data/
  fire-alarm/security devices, sheets, groups…). Hints, flagged as such.

Positive category ids are `CategoryElem` (0x2e1) objects in the file
(`m_pCategory.value.m_name`, `m_parentCategoryId` -> built-in parent) —
the user/family sub-categories (616 in rst, e.g. `Overhead Lines` under
`OST_Furniture`).

## 4. `tools/seed_audit.py` — is the seed ready?

```
python tools/seed_audit.py <seed.rvt> [--job spec.json] [--json out.json] [--full]
```

Prints the inventory, then (with `--job`) a per-item COVERAGE report and a
verdict (`SEED READY` / `SEED USABLE WITH GAPS` / `SEED NOT READY`, exit 2
on NOT READY):

* **levels** — spec level names present? Else names the elevation-order
  fallback the writer will use.
* **wall types** — each distinct spec `walls[].type` scored against seed
  wall types by name tokens + thickness (spec metres -> ft, ±10 % / ±25 %);
  flags `THICKNESS-ONLY` (right thickness, wrong/missing name),
  `-NOT-PLACED` (no wall of it to clone), `MISSING`.
* **doors** — needs a symbol in `OST_Doors`; matches width.
* **equipment** — reuses `spec_to_rvt`'s scoring vocabulary (imported, not
  copied: `_tokens`, `_amperage`, `KIND_KEYWORDS`, `ELEC_EQUIP_CAT`) but
  applies it PER SPEC ITEM and per kind CATEGORY (panelboard/switchboard/
  transformer -> `-2001040`, lightfixture -> `-2001120`): 10 + 3×|token
  overlap| + MCB/MLO agreement + amperage tie-break. Flags `MISSING`,
  `WEAK` (no rating/voltage token shared), `OK-NO-INSTANCE` (type loaded
  but nothing placed -> clone falls back), `NEEDS-FAMILY` (kind the writer
  can't build, e.g. IFC proxy hangers).
* **other** — titleblock present (needed for sheets), phases, room tags.

Every non-OK row carries a plain-English **FIX** ("load a panelboard family
into your seed and place ONE instance", "rename 'STB 20.0' or add a
'Painted CMU 8in' type", "the matched type has NO placed instance — place
one"). The report also states what `discover_template` would resolve
TODAY, so the two can be compared.

### DONE run — rme sample vs the electrical-room job

`tools/seed_audit.py samples/rmebasicsampleproject.rvt --job usecases/chicago-plenum-electrical-room/room-spec.json`
=> **SEED USABLE WITH GAPS** (0 missing, 5 warnings):

* B-HG4 / B-HQ1 / B-SHQ1 (480 Y/277, 400 A **MB**) ->
  `M_Lighting and Appliance Panelboard - 480V MCB - Surface :: 400 A`
  (placed 3, face). B-LR1 / B-LQ1 / B-SLQ1 (208 Y/120, 225 A **MLO**) ->
  `… 208V MLO - Surface :: 400 A` (placed 8). MCB vs MLO resolved
  correctly per panel.
* 3× 45 kVA transformers -> `M_Dry Type Transformer - 480-208Y120 - NEMA
  Type 2 :: 45 kVA` — **OK-NO-INSTANCE**: the exact type is loaded but
  never placed (only the 500 kVA is), so the writer would clone another
  type's instance. FIX: place one 45 kVA.
* `Painted CMU 8in` -> `STB 20.0` by **THICKNESS-ONLY** (200 mm ~ 8 in);
  no seed type is named CMU. FIX: rename/add.
* Door D-E101 (914 mm) -> `Drehflügel 1-flg - Stahlzarge :: 76 x 2.26`
  APPROX (760 mm). FIX: add a 914 mm type.
* HGR-01..04 trapeze hangers (`kind: proxy`) -> **NEEDS-FAMILY** (no
  writer kind; would be skipped). FIX: load a strut/trapeze generic-model
  family and register the kind, or accept omission.
* Level `T.O. Structure (20 ft)` -> FALLBACK to `Level 2`.
* Titleblock `A0 metric` (7 sheets), phases Existing / New Construction: OK.

## 5. What a firm must put in its seed (checklist)

1. Levels named as your jobs name them (`Level 1`, `T.O. Structure`…).
2. Every wall type you specify by name, WITH one short placed wall each.
3. Every equipment/fixture/door family you build with, WITH one placed
   instance of each type (free-standing where possible; panels may be
   face-hosted on any wall — the writer strips the host).
4. Your titleblock on at least one sheet; your view templates; your phases.
5. Run `seed_audit.py seed.rvt --job typical-job.json` until it prints
   `SEED READY`.

## Unknowns / limits

* Built-in category names come from the public enum table, not the file;
  ~100 entries are sample-verified, the rest are flagged assumed/unknown.
* Sheets: the sheet element is `DBDrawing` (holds `m_viewports`); sheet
  number/name resolution is not implemented (not needed for authoring).
* `discover_template` in `tools/spec_to_rvt.py` still (a) picks the
  most-instanced wall type ignoring the spec name/thickness and (b) matches
  `lightfixture` inside the electrical-equipment category on the substring
  `light`, so it can return a `M_Lighting … Panelboard` for a light
  fixture. The audit already applies per-item, per-category matching; the
  recommended 5-line wiring diff is in `docs/inbox/seed.md`.
