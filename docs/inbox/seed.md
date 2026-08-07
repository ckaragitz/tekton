# INBOX — seed (firm-seed authoring stream)

Territory: `src/rvt/inventory.py`, `tools/seed_audit.py`,
`tests/test_inventory.py`, `docs/writer/seed-authoring.md`, this file.
Full write-up: `docs/writer/seed-authoring.md`.

## DONE = met

1. **Name resolution** (`src/rvt/inventory.py`). Wall types, family
   symbols, families, levels, categories all resolve to real names on ALL
   THREE samples:

   | sample | levels | wall types named | wt thickness | master symbols named | families named | clone symbols named via master |
   |---|---|---|---|---|---|---|
   | rmebasic | 4/4 | **11/11** | 10/11 | **187/187 (100 %)** | 187/187 | 445/445 |
   | rstbasic | 9/9 | **4/4** | 3/4 | **48/48 (100 %)** | 48/48 | 58/58 |
   | racbasic | 6/6 | **11/11** | 10/11 | **97/97 (100 %)** | 97/97 | 45/45 |

   (`.venv/bin/python -m rvt.inventory --stats`; the one wall type per
   file with no thickness is the `StackedWallType`, which has no compound
   structure — correct.) Every master symbol also gets a category: rme
   187/187 and rac 97/97 map to a sample-VERIFIED built-in category; rst
   47/48 (the outlier is `-2008165`, a steel "Notch" modifier).

2. **Seed audit** (`tools/seed_audit.py`). Run on the rme sample vs the
   electrical-room job:

   ```
   .venv/bin/python tools/seed_audit.py samples/rmebasicsampleproject.rvt \
       --job usecases/chicago-plenum-electrical-room/room-spec.json
   ```
   verdict **SEED USABLE WITH GAPS** — 0 missing, 5 warnings: 6 panels
   resolve to the right 480V-MCB / 208V-MLO panelboard types (placed 3 /
   8, face-hosted); the 45 kVA transformer type is loaded but has NO
   placed instance (`OK-NO-INSTANCE` → "place one"); `Painted CMU 8in`
   matches `STB 20.0` by thickness only (200 mm ≈ 8 in) → rename/add;
   door 914 mm has only a 760 mm German type → APPROX; the 4 trapeze
   hangers (`kind: proxy`) → `NEEDS-FAMILY` (the writer has no such
   kind); level `T.O. Structure` → elevation-order FALLBACK; titleblock
   `A0 metric` + 2 phases OK. Full JSON at
   `/private/tmp/.../scratchpad/audit_rme.json` during the run (pass
   `--json` to keep it).

Tests: `tests/test_inventory.py` — 14 tests (built-in table anchors, name
resolution for levels/wall types/symbols/instances, clone resolution,
electrical-equipment hosting patterns, inventory shape, per-sample
resolution stats, the rme audit run and its MCB/MLO + THICKNESS-ONLY +
NEEDS-FAMILY assertions, MISSING fixes for empty seeds).

## Findings worth merging into KNOWLEDGE.md

* **Nameless `FamilySymbol`s are geometry CLONES.** `m_symbolInfo.m_name`
  is empty for 445/632 rme symbols (58/106 rst, 45/142 rac); each has
  `m_masterId` -> the named master (masters have `m_masterId == -1`).
  Instances reference the clone in `m_pInstanceInfo.m_symbolId` and the
  master in `m_masterSymbolId` (rme 471580 'EP-2': symbol 470440 clone,
  master 455409, host = a SketchPlane). MEP fittings clone per size
  (35 clones of `M_Rectangular Duct Elbow - Mitered`). The true type
  catalog = masters only.
* **Name fields:** Level `m_text`; Family `m_name`; all types
  `m_symbolInfo.value.m_name`; views `m_viewName` (+`m_isTemplate`);
  materials `m_pMaterial.value.m_name`; phases `ProjectPhase.m_name`;
  rooms/spaces AString params ROOM_NAME `-1006900` / ROOM_NUMBER
  `-1006901`; placed panels RBS_ELEC_PANEL_NAME `-1140078` (e.g. 'PP-2B'),
  Mark `-1001203`; wall-type family text lives in AString param `-1010105`
  ('Basic Wall' / 'Mauerwerk').
* **Wall-type thickness** = Σ `m_pCompoundStructure.value.m_layers[*].
  m_layerWidth` (ft): rme `STB 20.0` = 0.65617 ft = 200 mm exactly. The
  rme sample's placed wall types are GERMAN-named (`MW 11.5`, `STB 20.0`,
  `Lamelle 11.5`, `WC Trennwand 5.0`); its three unplaced ones are English
  (`Exterior - Brick on Mtl. Stud` …).
* **Built-in category ids are NOT in the file.** No `OST_` string in any
  inflated stream; `CategoryTable` (0x2e6) = only `m_pADoc`;
  `IFCBuiltInCategoryKey` = ElementIds only; `IFCCategoryTemplate` (the
  one class with a `m_categoryName` map) has 0 instances. => the
  BuiltInCategory `OST_*` table must be embedded (done, ~100 verified).
  Positive category ids are `CategoryElem` (0x2e1):
  `m_pCategory.value.m_name` + `m_parentCategoryId` (616 sub-categories
  in rst, e.g. 'Overhead Lines' under -2000080 Furniture).
* **Sample-verified BuiltInCategory values** (element class / example
  proves each): -2001040 ElectricalEquipment, -2001060 ElectricalFixtures
  (GFCI), -2001120 LightingFixtures, -2001140 MechanicalEquipment (WSHP),
  -2008087 LightingDevices ('Single Pole' switch), -2008010 DuctFitting,
  -2008013 DuctTerminal, -2008000 DuctCurves (RbsDuctCurve), -2008015
  DuctSystem (RbsHvacSystem), -2008020 FlexDuctCurves, -2008037
  ElectricalCircuit (RbsElectricalSystem), -2008039 Wire (RbsWireCurve),
  -2008043 PipingSystem, -2008044 PipeCurves, -2008049 PipeFitting,
  -2008050 FlexPipeCurves, -2008126 CableTrayFitting (Channel Horizontal
  Bend), -2008128 ConduitFitting (Conduit Body - Type L), -2003600
  MEPSpaces (RoomElem, MEP file only), -2003200 Areas, -2003000
  ProfileFamilies (mullion/handrail/cable profiles), -2002000
  DetailComponents (AISC section / brick coursing), -2001360 Planting
  ("Red Ash - 25'"), -2001370 Entourage (M_RPC Beetle), -2001350
  SpecialityEquipment ('Aufzug' lift), -2001330 StructuralColumns,
  -2001320 StructuralFraming, -2001300 StructuralFoundation, -2000280
  TitleBlocks ('A0 metric'), plus the standard architectural set
  (-2000011 Walls, -2000023 Doors, -2000014 Windows, -2000032 Floors,
  -2000035 Roofs, -2000038 Ceilings, -2000160 Rooms, -2000240 Levels,
  -2000220 Grids). Full table + assumed set in `inventory.py`.
* **Sheets** = class `DBDrawing` (holds `m_viewports`); 142 host
  DBDrawings in rme, 1,694 records total. Panel schedules = class
  `PanelScheduleView` (category -2001118), templates
  `PanelScheduleTemplate.m_name` ('Branch Panel'). Not needed for
  authoring; noted for whoever does sheets.
* **Two `spec_to_rvt.discover_template` bugs found by the audit's
  side-by-side "writer would pick TODAY" line:** (a) `lightfixture` is
  matched inside `OST_ElectricalEquipment` on the substring `light`, so a
  light-fixture request resolves to `M_Lighting and Appliance Panelboard`
  (a panel!) — the kind needs category -2001120; (b) the wall type is the
  most-instanced one (`MW 11.5`, 115 mm) regardless of the spec's
  `"Painted CMU 8in"` / 200 mm — the audit's THICKNESS-ONLY match to
  `STB 20.0` is the correct pick; (c) it aggregates the psets/tokens of
  ALL equipment of a kind into one token bag, so a job with mixed 480V-MCB
  and 208V-MLO panels picks ONE type for all six (it picked the MLO one)
  — resolution has to happen per spec item, as `seed_audit.audit_equipment`
  does.

## RECOMMENDED integration diff (do NOT apply here — orchestrator owns tools/spec_to_rvt.py)

Wire the resolver into `discover_template()` so wall types match by name /
thickness and light fixtures use their own category. Minimal:

```diff
--- a/tools/spec_to_rvt.py
+++ b/tools/spec_to_rvt.py
@@
 from rvt.commit import commit_new_elements, verify_written  # noqa: E402
 from rvt.mutate import Document  # noqa: E402
+from rvt import inventory as inv  # noqa: E402  (name/category resolution)
@@ def discover_template(doc, spec: dict) -> dict:
-    # wall type: most-instanced basic wall
-    wt = doc.wall_types_with_instances()
-    if wt:
-        tpl["wall_type"] = max(wt.items(), key=lambda kv: len(kv[1]))[0]
+    # wall type: match the spec's type NAME, then thickness, then most-used
+    tpl["wall_type"] = _match_wall_type(inv.wall_types(doc), spec)
@@
-    syms = [s for s in doc.symbols() if s.get("category") == ELEC_EQUIP_CAT]
+    syms = inv.symbols(doc)              # named masters + true categories
     for kind, keys in KIND_KEYWORDS.items():
+        cat = LIGHT_FIXTURE_CAT if kind == "lightfixture" else ELEC_EQUIP_CAT
         want_tokens = set()
```
and inside the symbol loop replace the category test with
`if s.get("category_id") != cat: continue`. The helper (drop-in, mirrors
`seed_audit.audit_walls` scoring):

```python
def _match_wall_type(wall_types, spec):
    want = {str(w.get("type") or "") for w in spec.get("walls", [])} - {""}
    thick = (spec.get("defaults") or {}).get("wallThickness")
    best, best_sc = None, -1.0
    for wt in wall_types:                       # inv.wall_types rows
        sc = sum(3 * len(_tokens(t) & _tokens(f"{wt['name']} {wt['family']}")) for t in want)
        if thick and wt["thickness_ft"] and abs(wt["thickness_ft"] - thick * FT_PER_M) <= 0.1 * thick * FT_PER_M:
            sc += 6
        sc += 0.5 if wt["walls_using"] else -100    # must be clonable
        if sc > best_sc:
            best, best_sc = wt, sc
    return best["id"] if best else None
```
Add `LIGHT_FIXTURE_CAT = -2001120` next to `ELEC_EQUIP_CAT`. Better still:
resolve equipment PER spec item (each panel gets its own best type) rather
than one type per kind — `seed_audit.audit_equipment()` already does this and
can be lifted into `build()` (map `eq -> symbol_id` before the placement
loop). Longer term the whole "resolve job onto seed" step should live in
one shared function used by both `spec_to_rvt.build` and `seed_audit`, so
the audit is guaranteed to predict the writer.

## Open questions

* The customer's real seed will name types in ENGLISH firm-speak; token
  matching handles `480V/400A/MCB/MLO/45 kVA` but a firm that names panels
  by manufacturer catalog number needs a per-firm alias map
  (`typeName -> seed symbol id`) — cheap to add to the job spec as
  `equipment[].seedSymbolId` overrides once a firm exists.
* `BUILTIN_CATEGORIES_ASSUMED` entries (cable tray/conduit curves, low-
  voltage device categories, sheets) are unverified — confirm against the
  first real electrical seed and promote.
* Category `-2008165` (rst 'Notch') is unknown; harmless.

Also fixed in the audit (not in spec_to_rvt): a false-positive class where
`'panel' in name` matched `Photovoltaic-Panel-SolarWorld` in the rac sample —
`KIND_EXCLUDE` word-list + a rule that a match must share a numeric
electrical RATING token (voltage/A/kVA from typeName or rating psets) with
the request, else it is `WEAK`; a stray "42 circuits" / "10 kA" can no
longer fake an OK. rac now audits `SEED NOT READY` (no electrical gear) —
the honest answer for an architectural seed.

BRANCH STATE: clean — new files `src/rvt/inventory.py`, `tools/seed_audit.py`,
`tests/test_inventory.py`, `docs/writer/seed-authoring.md`, `docs/inbox/seed.md`;
no edits to mutate/commit/container/ecc/encode/objects/partitions or
tools/spec_to_rvt.py. Full suite (`pytest tests/ -q --ignore=tests/oracle`):
244 passed, 1 failed — the failure is `tests/test_plugin_sync.py` (PLUGIN
DRIFT on `lib/src/rvt/validate.py`, a file another stream owns; pre-existing,
unrelated to this stream; fix = `python tools/sync_plugin.py` by whoever owns
validate.py). New tests: 14 in tests/test_inventory.py, all green.
