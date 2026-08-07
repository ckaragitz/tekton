# systemtypes — workstream record (SYSTEM-FAMILY TYPES + STYLES SYNTHESIS, 2026-08-03)

Charter: synthesize OUR OWN system-family types and document-standard
elements — the expression that survives a family-free reduction and is not
a loadable family: wall (with compound-structure layers) / floor / roof /
ceiling types; conduit types (+ standard + sizes) with fitting hooks; cable
tray types; wire types (+ conductor definition cells); the electrical
settings elements (voltage definitions, distribution systems, load
classifications, demand factors, the ElectricalSetting singleton); object
styles / CategoryElem + GStyleElem; line & fill patterns; a material; text
types.  Deliverable = pure CONSTRUCTORS taking plain parameters (mm, volts,
names, RGB), each emitting a COMPLETE valid `(class_id, obj_dict,
header_dict)` shaped for the record machinery, with NO cloned Autodesk
payload; documented field maps; encode round-trip tests; injected proof
files validating clean.  Serves TRACKER P0 gate **G1 GENESIS BASELINE**.

Territory touched ONLY: `src/rvt/genesis/__init__.py`,
`src/rvt/genesis/types.py`, `src/rvt/genesis/data/object_styles.json`,
`tests/test_genesis_types.py`, `experiments/genesis/types/*`,
`docs/writer/genesis-types.md`, this file.  No orchestrator-owned or
protected `src/rvt/*.py` file was edited; no browser used.

## Deliverables

| item | path | state |
|---|---|---|
| constructor engine (29 element constructors + `GenesisCatalog` + `blank_object` schema skeleton + `element_header`) | `src/rvt/genesis/types.py` (2,117 lines) | done |
| package init | `src/rvt/genesis/__init__.py` | done |
| built-in object-styles product-constant table (1,074 categories; 1,239/1,407 entries cross-file-confirmed) | `src/rvt/genesis/data/object_styles.json` | done (extracted, provenance in-file) |
| field-by-field definition maps + rules | `docs/writer/genesis-types.md` | done |
| tests (46: skeleton round-trips, constructor round-trips, grid/shell/key rules, units, no-corpus guard, parametric reproduction) | `tests/test_genesis_types.py` | pass |
| injection proof driver | `experiments/genesis/types/make_type_proofs.py` | done |
| PROOF FILES (51 injected type records, 3 files) | `experiments/genesis/types/T_walltype.rvt`, `T_conduit_types.rvt`, `T_settings.rvt` + `T_*.json`, `proof_summary.json` | **all VALIDATE OK, 0 errors** |

Reproduce: `.venv/bin/python -m rvt.genesis.types` (52-record demo
catalog: encode→decode clean + byte-exact 52/52, 0 dangling refs);
`.venv/bin/python experiments/genesis/types/make_type_proofs.py` (~3.5 min:
build 3 catalogs, commit into copies of the MEP sample, read back,
validate); `.venv/bin/python -m pytest tests/test_genesis_types.py`.

## Files the orchestrator should VIEWER-TEST

`experiments/genesis/types/T_walltype.rvt`, `T_conduit_types.rvt`,
`T_settings.rvt` — each = the untouched MEP sample + a batch of NEW
document standards created purely from our parameters (list of what to look
for per file is in the matching `T_*.json` → `catalog.records[].kind` and
each type's `m_symbolInfo.m_name`, all prefixed **"GEN "**).  What a pass
proves per file:

* `T_walltype.rvt`: our BasicWallType 'GEN Interior - 124mm Partition' and
  'GEN Exterior - 200mm Concrete' appear in the wall type selector and render
  (compound structure + our materials + our fill/line patterns); our floor,
  roof and ceiling types appear in their type selectors.
* `T_conduit_types.rvt`: 'GEN EMT'/'GEN RMC' conduit standards + the sizes
  singleton (a *second* ConduitSizesElem — see risk R3), two conduit types,
  two cable-tray types, our wire type + its 4 conductor cells, three wire
  symbol types (Electrical Settings > Wiring / Conduit dialogs).
* `T_settings.rvt`: 'GEN 120/208/277/480' voltage definitions and the two
  wye distribution systems (Electrical Settings > Voltage / Distribution),
  three demand factors + load classifications, two text types (with owned
  font/category/style), one sub-category with its own line style.

## What was proven (three independent proof levels)

**P1. Schema completeness (no viewer needed).**  A schema-directed skeleton
(`blank_object(class)`, walking the class chain parent-first through the
canonical `Formats/Latest` field list) yields an encoder-ready dict for ANY
of the 4,690 classes; every constructor overlays only definitional fields.
All 30 target classes' skeletons and every constructor's output encode
with `rvt.encode` and decode back with `rvt.objects` **clean, byte-exact,
value-equal** (tests).  The whole 52-record demo catalog: 52/52.

**P2. PARAMETRIC REPRODUCTION (the strongest evidence short of the viewer).**
Autodesk's OWN types re-created from their plain parameters diff to **zero
fields — object AND seq-101 header**: RbsVoltageType '240'; distribution
systems 120/240-single & 480/277-wye; ConduitStandardType 'EMT'; the
ConduitSizesElem and ElectricalSetting singletons; RbsConduitType 'RNC Sch
80'; RbsCableTrayType (ladder); the 4 conductor CustomElement cells + RbsWireType
'XHHW'; the 3 wire symbol types; ElectricalDemandFactorDefinition;
ElectricalLoadClassification (given its param-elem ids); LinePatternElem
'Dash'/'Dot'; FillPatternElem 'Diagonal crosshatch'; RoofAttributes
'Generic - 400mm'; CompoundCeilingType; the OST_Walls object-style rows
(GStyleElem ids 30/31); a sub-CategoryElem + its GStyleElem; and the complete
4-element text type '1/8" Arial'.  BasicWallType 'Exterior - Block on Mtl.
Stud' (7 layers, two 0-width membranes) reproduces its compound structure,
vertical-region grid, shell counts, ref-face keys AND its GElement rep
exactly — the only diff is the pre-Revit-4.0 legacy `m_segRefFaceKeysPre40`
list; German wall/floor types differ only in the firm-specific shared
parameter we deliberately never clone.  => the field maps are RIGHT, not
just self-consistent.

**P3. Injection through the real writer + the arbiter.**  51 new type
records committed via `rvt.commit.commit_new_elements` into copies of the MEP
sample: read-back shows CRC 0 / ECC 0 / walker 0 / stamps ok / sentinels
last / ElemTable count == header count / all new seq-102 objects decode
clean; `tools/rvt_validate.py` = **OK, 0 errors** on all three (2 warnings
each = the two PRE-EXISTING conditions: the commit path's advisory A/C
block-counter defect and the sample's own 1,171 Extensible-Storage records).

## Evidence log

### E1. The type "definition vs machinery" split is stable per class
A field-variance census over every instance of each class in rme
(CONST-across-instances = machinery, VARY = definition/identity) is the
basis of every field map in `docs/writer/genesis-types.md`; e.g. among 10
RbsConduitTypes only name / standard / fitting ids / preview / with-fitting
vary; roughness (0.0003), max sizes (8 ft), profile class and branch flags
are constant.

### E2. Volts internal unit = W·ft² conversion — SOLVED
`m_dActualVoltage` = volts × 10.7639104167 exactly (240 → 2583.33850001,
120 → 1291.66925, 208 → 2238.89 per KNOWLEDGE): the metric watt's m²
converted to ft², i.e. electrical potential in kg·ft²/(s³·A).  Amps,
demand factors and power factors are stored raw; ampacity-correction bands
are Kelvin (294.15 K = 21 °C).  Codified in `types.volts()`.

### E3. Compound-structure vertical-region grid rule — RECOVERED (walls only)
Regions = non-zero-width layers (0-width membranes get none); boundary
segments at cumulative widths (origin 0 at exterior face, ids 0..B-1),
two face segments per region at 0 and sampleHeight (ids B+2r/B+2r+1),
region r = segments [left, bottom, right, top], array order faces-then-
boundaries; `regionToLayerMap` skips membranes; shell counts = layers
before/after the contiguous structure run; ref-face keys 29 (core ext) /
30 (core int) / 31,32,33 (in-shell / in-core boundaries, counting).
Reproduced BYTE-EXACT on 1-layer, 6-layer (racbasic timber) and 7-layer
(US block) walls.  Floors/roofs/ceilings carry NO grid (null).

### E4. Types own COMPANION elements (the object graph a type really is)
* text type = 4 elements: TextNoteAttributes + owned FontElem + owned
  CategoryElem + that category's GStyleElem (font.m_ownerId = type,
  category.m_ownerId = type, owned companions carry object
  `m_designOptionId = -4` while headers say -1);
* wire type → 4 conductor `CustomElement` cells (`CellList{<RbsConductor*>,
  NamingCell{name}}`) which live in a catalog PARALLEL to the three
  `RbsWire*Type` symbol types the sizes table keys on;
* conduit definition = standard element + sizes SINGLETON row + type;
* load classification → its demand-factor definition + SIX auto-created
  `ParamElemElectricalLoadClassification` schedule-column parameters
  (m_*ParamElemId) — those companions belong to a parameter-elements stream
  (left -1 by default; the constructor accepts them).
* the header `m_deletion` list must enumerate self + every owned/referenced
  companion (owned companions also list their OWNER) — reproduced exactly.

### E5. The OBJECT-STYLES table is a Revit product constant, and we captured it
Built-in-category `GStyleElem` records (negative `m_categoryId`, owner -1,
`m_gstyleType` 1 projection / 2 cut): 1,074 categories in BOTH rme and rst;
**1,239/1,407 (category, role) entries are byte-identical across the two
unrelated projects** → the pens/patterns are Autodesk defaults, not authored
content (interoperability data like the class map).  Bundled as
`src/rvt/genesis/data/object_styles.json` with a per-entry `confirmed`
flag; positive pattern/material ids are file-local and mapped to names or
-1.  Object-style rows are the LOW ids (30, 31, …) created first in every
project.

### E6. seq-103 reps of types
Every type/standard/settings class carries `SerializedDummy` **except
BasicWallType**, which carries a small formulaic EMPTY GElement geometry
cache (empty Geometry sub-node pid 3, ±1e30 boxes, `m_gElemType` 3) —
reproduced exactly (`_empty_type_rep`).

## Gotchas found (for KNOWLEDGE.md merge)

1. **G2 identity writer breaks an L2 invariant.** `rvt.commit` →
   `rvt.identity.own_basic_file_info` stamps a FRESH document GUID into
   BasicFileInfo but does not prepend a matching `Global/History` episode,
   so `rvt.validate` reports the consistency ERROR "Unique Document GUID !=
   History entry[0] GUID" on EVERY committed file today.  The proofs pass
   `identity={"document_guid": <template's own GUID>}` (an existing commit
   parameter) so the arbiter judges only the injected types.  Proper fix
   (out of my territory, commit.py/identity.py/streams_edit.py): when the
   identity scrub assigns a new GUID it must also prepend a History episode
   with that GUID (streams_edit.record_save), or reuse History[0].  Exact
   suggestion below (§Diffs D1).
2. `field_key` shadowing + fixed INLINE arrays: `WallType.m_bordMullions` is
   kind 0x0d with a FIXED count (2) whose element is itself a fixed pair —
   a skeleton must recurse fixed-array-of-array (a naive `[]` truncates the
   decode 16 bytes early).  Handled in `_blank_field`.
3. Two 0-width membrane layers must NOT create grid regions (the
   `regionToLayerMap` is a bijection onto non-zero layers) — reproducing the
   US block wall depends on it.
4. `m_pParamValueSetInt` on the German wall/floor types holds a firm's
   SHARED parameter (id 564501): sample content, never cloned — the ONLY
   object diff vs those specimens, by design.
5. Positive `m_linePatternId` / `m_materialElemId` inside object styles are
   file-local element ids (rme walls point at material 24 'Default Wall');
   only names / built-in negatives (-3000010 SOLID) are portable.

## Diffs / hooks proposed for orchestrator-owned files (NOT applied)

**D1 — commit.py identity/History coherence (fixes the validator error every
commit currently produces).**  Minimal-risk option: default the identity
GUID to the template's existing document GUID (keeps BFI == History[0]),
scrubbing only path/username/central identity:

```diff
--- a/src/rvt/commit.py
+++ b/src/rvt/commit.py
@@ (step 3. identity)
-        if bfi is not None:
-            new_streams["BasicFileInfo"] = own_basic_file_info(
-                bfi.data, out_path=out_path, **(identity or {}))
+        if bfi is not None:
+            ident = dict(identity or {})
+            if "document_guid" not in ident:
+                # keep BFI GUID == History[0] (L2 invariant); a NEW
+                # document GUID requires a matching History episode
+                # (streams_edit.record_save) -- see docs/inbox/systemtypes.md
+                from .stream_encoders import decode_basic_file_info
+                ident["document_guid"] = decode_basic_file_info(
+                    bfi.data)["unique_document_guid"]
+            new_streams["BasicFileInfo"] = own_basic_file_info(
+                bfi.data, out_path=out_path, **ident)
```

The principled fix instead prepends a History episode carrying the new
GUID (streams_edit.record_save) — the orchestrator's G2 call.

**D2 — a generic mutate hook (optional, only if the orchestrator wants
`Document`-level ergonomics).**  Genesis needs NO change to mutate.py: a
`TypeRecord` converts to `mutate.NewElement` (`.as_new_element()`) and the
catalog commits through `commit_new_elements` directly.  If a document-level
API is wanted anyway, one method suffices:

```diff
--- a/src/rvt/mutate.py
+++ b/src/rvt/mutate.py
@@ class Document:
+    def add_element(self, class_name: str, class_id: int, obj: dict,
+                    header: dict, rep: dict | None = None,
+                    kind: str = "element") -> NewElement:
+        """Register a pre-built (obj, header[, rep]) as a new element:
+        allocates the id (obj['m_id'] / rep tag already set by the caller
+        or patched here), builds the ElemRecPlan and appends to
+        self.new_elements so serialize()/diff()/plan() cover it."""
+        eid = int(obj.get("m_id") if obj.get("m_id") not in (None, -1)
+                  else self.next_id())
+        obj["m_id"] = eid
+        el = NewElement(eid, kind, class_name, class_id, header, obj, rep,
+                        self._new_elemrec(eid), template_id=-1)
+        self.new_elements.append(el)
+        return el
```

## Open questions (need the viewer / a decision)

* Do the readers require a `LegendComponent` type-preview element
  (`m_previewElemId`) for host types?  All Revit-authored host/curve types
  point at one; ours carry -1 (as the settings types do).  If the viewer
  balks at T_walltype/T_conduit_types, adding a preview LegendComponent
  constructor is the next task.
* T_conduit_types adds a SECOND `ConduitSizesElem` / `CableTraySizesElem`
  (document singletons) alongside the template's — semantically odd but the
  only way to inject-prove the constructor into a live template; the genesis
  base will carry exactly one.  Watch whether the viewer objects.
* Text-type font `m_size` is paper height in feet; whether Revit also
  requires the FontElem name to match an installed font at open (Arial is
  safe) is untested.
* Whether an `ElectricalLoadClassification` with all six
  `m_*ParamElemId = -1` is accepted (real ones always have the companions)
  — decides whether a parameter-elements stream must run before genesis
  load classes are viewer-safe.

## Proposed next tasks (orchestrator decides)

1. Viewer-test `T_walltype.rvt`, `T_conduit_types.rvt`, `T_settings.rvt`
   (this stream's acceptance); record in `docs/acceptance-log.md`.
2. Fold this into the GENESIS BASE writer: emit the demo catalog
   (`demo_catalog()`) + `default_object_styles()` (full table) as the
   settings/types layer of the family-free document — needs the
   `Global/Latest` (ADocument) encoder that indexes default type ids
   (genesis.md §6.3) to reference them.
3. `DimensionStyle` constructor (mapped in §11 of the field doc; needs its
   4 companion category/style elements + unit-format enums).
4. `RbsWireSizesElem` (NEC ampacity/correction table) as a data-driven
   constructor; `ParamElemElectricalLoadClassification` companions.
5. Apply D1 (identity/History) so every commit validates clean without the
   template-GUID workaround.

## Full-suite result at handoff

`RVT_SEG_CACHE=<segcache> .venv/bin/python -m pytest tests/ -q` →
**434 passed, 2 failed** (8 min 19 s).  Both failures are OUTSIDE this
stream and unrelated to it:

1. `tests/test_mep_views_spaces.py::test_schedule_view_and_space_write_and_verify`
   — a concurrent stream's brand-new module (`src/rvt/mep/views_spaces.py`)
   still being edited while the suite ran (its walker reports 1 error in
   ITS own write path); no genesis code involved.
2. `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` — the
   plugin bundle has drifted from source for the 12 new/changed source
   files landed by FIVE concurrent streams (mep/*, estorage.py, identity.py,
   provenance.py, and this stream's genesis/*); resolved by the
   plugin-packager / orchestrator running `python tools/sync_plugin.py`
   once all streams merge (plugin/ + rev-revit.zip are not my territory).

This stream's own module: `tests/test_genesis_types.py` = **46/46 pass**.

BRANCH STATE: no VCS in repo (plain directory); all work is uncommitted
files at the paths above — src/rvt/genesis/{__init__.py,types.py,
data/object_styles.json}, tests/test_genesis_types.py,
experiments/genesis/types/{make_type_proofs.py, T_walltype.rvt,
T_conduit_types.rvt, T_settings.rvt, T_*.json, proof_summary.json},
docs/writer/genesis-types.md, docs/inbox/systemtypes.md.  All three
proof files validate 0 errors; demo catalog 52/52 round-trip; test module
46/46 pass.  READY.
