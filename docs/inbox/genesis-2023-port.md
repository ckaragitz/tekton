# GENESIS 2023 — CONSTRUCTOR PORTABILITY + MINERS (the 32-bit-id release)

Stream: **genesis-2023-port** (2026-08-04).  Charter: (1) own-field
signatures for every rvt.genesis-constructed class, 2026 pin vs 2023
schema + specimen decode -> the CONFIRMED portability table, the known
movers each established independently; (2) the field maps in
`src/rvt/genesis/port2023.py`, delegating to port2025/port2024 layers
where layouts coincide, recorded; (3) the miners re-run over the 2023
corpus and frozen (category enum + cuttability, per-key style profiles,
pen-table scale keys, palette property-set invariants, defaults);
(4) ported-constructor output validated against 2023 specimens byte-level
where the method allows.

**DONE conditions met: the confirmed table is frozen (four-way annotated
vs 2025 AND 2024); the field maps are implemented, hook-tested,
round-trip byte-exact under the 2023 codec and byte-exact against 2023
specimens; all five miners are frozen; 30 tests green.  NOTHING is
viewer-certified — no Revit-2023 file has ever been uploaded; every
downstream certification is the reduce/ladder streams' batch law.**

Deliverables:

1. `src/rvt/genesis/port2023.py` — the portability layer (2023 pin +
   cross-check, the id32/reading-2023 delegates over
   `rvt.versions.records32`, the `adapt()`/`adapt_record()` field-map
   engine with the 2023 hook set, five miners, selftest CLI)
2. `experiments/genesis2023/miners/portability-2023.json` — the CONFIRMED
   table (frozen; re-derivable via `--verify`)
3. `experiments/genesis2023/miners/` — `builtin_category_enum_2023.json`,
   `builtin_style_profile_2023.json`, `pen_table_2023.json`,
   `palette_invariants_2023.json`, `defaults_2023.json`
4. `tests/test_port2023.py` — 30 tests, all green
5. `samples/2023/SOURCES.md` (acquisition co-record; see §0)
6. this record

---

## 0. ACQUISITION (coordination note — dual-stream, same minute)

samples/2023/ did not exist at stream start.  Per the never-idle rule this
stream fetched `rstbasicsampleproject.rvt` first (plain HTTPS GET from
`revit.downloads.autodesk.com/download/2023RVT_RTM/Docs/InProd/` — the
pattern held, no login), then staged rac/rme via download-to-scratch +
atomic move-if-absent; the 2023 REDUCE stream landed the full six-file
set concurrently (the guard worked — no clobbering; identical bytes, same
URLs).  This stream wrote `samples/2023/SOURCES.md` (URL + sha256 +
DEV-ONLY quarantine, all six hashes re-verified on disk) and verified the
plugin deny-scan: **no sample leak** (`tools/sync_plugin.py --check`
reports only 5 drift files from other streams' pending syncs — none
sample-related, none mine).  All six files: `Format: 2023`, build
`20220401_1515(x64)`; `Formats/Latest` byte-identical across all six =
**462,765 B, sha256 bce7907b…, 4,418 classes / 11,866 fields** (the
per-release schema-constant law holds one release further back).  The
reduce stream's `experiments/genesis2023/format_facts_2023.json`
independently records the identical pin.

## 1. THE 2023 FORMAT MODEL — every layer measured, one real delta

Layer-by-layer verdict on the 2023 samples (nothing assumed from 2024/25):

| layer | 2023 verdict |
|---|---|
| CFB container | UNCHANGED — v4, 4096-byte sectors (same as 2024/2025/2026) |
| ECC page framing | UNCHANGED — 102 pages verify on rst |
| gzip flavour | UNCHANGED — 395/395 members CRC-ok on rst |
| block framing | UNCHANGED bar the usual per-release ordinals, resolved BY NAME: BLOCK 0x0E4E / TRAILER 0x0E47 / FOOTER 0x0E61 / CONTAINER 0x0365 / UNIT_INNER 0x0364 / PT 0x0BC0 — 387 blocks, 0 walker errors |
| schema-stream grammar | UNCHANGED — parses to EOF, 0 unresolved refs |
| **record layer** | **CHANGED — 32-bit element ids** (the 2024 id-widening, walked backwards) |
| stamp formula | UNCHANGED — adler32(class‖body), 63,648/63,648 rst records |
| ADocument shape | registry classes port (BrowserOrganizationTracking = the same 3-field split as 2024/2025); ElemTable v9 drops 2024's `m_bLastElementIdOverride` |

The id width is DECLARED BY THE FILE'S OWN SCHEMA: `Identifier` v1 =
`m_id` kind 0x04 (i32) in 2023; v2 = `m_id64` kind 0x0b (i64) in 2024+
(`port2023.id_width_from_schema`).  It ripples into: record headers
(seq-101 `<iI` 8 B, seq-102/103 `<iII` 12 B, 4-byte −1 sentinel), every
in-body ElementId/Identifier, and the ElemTable (28-byte rows, 19-byte
footer with a u32 `IdentifierSource.m_last`).  With ONLY the width layer
added, the whole read stack runs at parity: rst walks completely (95,631
records, 0 partial segments / bad sentinels / bad trailers) and seq-102
decodes **99.98 % clean (31,817/31,824)** — the same percentages and the
same 7 pre-existing RebarShape/DataStorage Extensible-Storage gaps every
release shows.  (The reduce stream's parity_2023.md independently shows
all six 2023 samples VALID at the same rates.)

MID-STREAM CONVERGENCE: the reduce stream landed
`rvt.versions.records32` (the stack-wide 32-bit patch set) and
`rvt.versions.schema_2023` + `KNOWN_RELEASES[2023]` while this stream was
building its own narrower context.  Per the charter's reuse rule,
port2023's `id32()` / `reading_2023()` / `iter_records_2023` are now THIN
DELEGATES over `records32.ids32/reading32/iter_records32`, and the schema
pin loads via `schema_2023.load` with this stream's independently measured
constants RE-ASSERTED on every load (two streams cross-checking).
`tests/test_port2023.py::test_class_id_2023_matches_framing_ordinals`
asserts my pin == KNOWN_RELEASES[2023] (framing, sha256, size, class
count, all 23 anchors).

**One latent records32 defect found (proposed fix, not applied — their
territory):** `records32.parse_elemtable32`/`encode_elemtable32` read/write
the ElemTable row as `(original_id, id, …)`, but the 2023 schema declares
ElemRec = `(m_id, m_history{originalElementId,…}, m_partitionId,
m_OwningElementId)` — id FIRST — and the schema field order IS the wire
order (proven in 2024, whose wire exactly follows ITS schema's
history-first order; and the schema-directed id32 decode of the whole 2023
ElemTable stream agrees with the id-first read).  Byte-indistinguishable
today: id == original_id in 49,845/49,845 rows across the three 2023
basics, and reduction preserves that.  Proposed one-liner in records32:
swap `o, eid` in `parse_elemtable32`'s unpack and `encode_elemtable32`'s
pack.  port2023 keeps `parse_elemtable_2023` as the schema-ordered
REFERENCE implementation;
`test_reference_elemtable_parser_agrees_with_records32_on_corpus` proves
both parsers agree on every corpus row (and will fail loudly if a future
file breaks the id==orig premise).  (Also cosmetic: the 19-byte footer's
"pad" byte in records32 is actually the serialized
`m_bExpandAllOnLoad` bool — same bytes, better name.)

## 2. THE CONFIRMED PORTABILITY TABLE (frozen; four-way annotated)

Method = port2025's §6 re-run for 2023: harvest every CODE-position class
literal from the genesis constructors (326 names; the three port layers
excluded), expand with every base class on their chains (403), per class
compare own-field signatures `(name, kind, flags, count, type_NAME,
extra, element)` + flattened parent-first chain + versions, 2026 pin vs
2023 pin; every non-IDENTICAL row annotated `vs_2025` AND `vs_2024`
(nothing assumed monotonic).  Result (`portability-2023.json`):

| verdict | classes | notes |
|---|--:|---|
| IDENTICAL | 280 | Element, Symbol, SerializedDummy, PartitionTable, DocumentIncrementTable, GStyleElem, CategoryElem, Level, … |
| LAYOUT-DELTA | 104 | 42 are REORDER-ONLY (below); 18 differ from 2024's deltas |
| MISSING-2023 | 16 | 2024's 13 + `FabricationServiceSettings`, `SSEPointVisibilitySettings` (both constructed by settings; emit nothing on 2023) + `DrawOrderMgrBase` (chain row, never constructed) |
| VERSION-ONLY | 3 | DataStorage v3→0, ElementHeader v25→24, FabricationSettings v6→4 — free |

**THE REORDER WAVE (2023-new, the headline non-monotonic finding):**
42 classes — Material, WallType, Floor, CurveElem, RoomElem,
ColorFillSchema, DimensionStyle, GStyle, GFace, AssemblyType,
FamilyInstance, SunAndShadowSettings, SymbolIdMgr, … — carry the SAME
field set as 2026 in a DIFFERENT serialization order, mostly WITHOUT a
version bump (Material is v13 in both).  2024 re-ordered wholesale;
version numbers cannot be trusted, only each file's own schema.  The
target-chain walk absorbs all 42 with zero hooks.

**Known movers, each established independently for 2023:**

* `DBView` v99→98 — `m_viewPositionId` dropped (as 2024/2025) + order +
  `m_pDetailDrawOrderMgr` pointee re-shaped (below).  Hits every
  constructed view class.
* `DBViewDrafting` v12→10 — drops `m_sheetCollectionId` +
  `m_sheetTitleBlockId`, and has **NO `m_scheduleInstanceIds`** (that
  field is 2024-ONLY: present in 2024, absent in 2023 AND 2025 — a
  one-release field).  2023 ≠ 2024 here, verified both directions.
* `Viewport` v13→10 — drops `m_viewPosition`, `m_viewAnchor` AND
  `m_oPlaceholderBoxOutline`.  **2024 is ALSO v10 yet keeps
  m_oPlaceholderBoxOutline** — same class version, different layout
  across releases (the strongest version-numbers-lie specimen yet).
* `BrowserOrganizationTracking` v6→5 — the same three-ElementId split as
  2024/2025 (port2025 tree-code hooks delegate verbatim).
* `GeomTable` — same two 2023-only leading ints; corpus default (−1, −1)
  re-mined (dominant across 7,081 censused rst GeomTables).
* Wire/conductor — the 6 conductor-catalog classes + 2 data bases
  MISSING (as 2024/2025); `RbsWireType` v5→2 id→size-label string;
  `RbsWireSettingsElem` v13→12 three doubles (+ order differs vs 2026);
  `RbsWireSizesElem` v8→3 drops `m_bInitialized`.

**2023-new layout deltas beyond the wave (and beyond 2024's table):**

* `ParamDef` v6→5 (base of all 12 ParamDef* storage classes):
  `m_groupTypeId` (ForgeTypeId) → `m_groupElemId` (ElementId — the
  classic BuiltInParameterGroup id).  Hooked via an 18-entry map mined by
  JOINING the same parameters (caption key) across the 2023/2026 rst+rme
  samples: 460 joined, ZERO conflicts (`identityData→-5000100`,
  `dimensions→-5000101`, `construction→-5000103`, `graphics→-5000104`,
  `materials→-5000105`, `plumbing→-5000111`, `structural→-5000112`,
  `mechanical→-5000113`, `constraints→-5000119`, `text→-5000123`,
  `electricalLighting→-5000124`, `electricalLoads→-5000125`,
  `mechanicalLoads→-5000126`, `mechanicalAirflow→-5000127`,
  `electrical→-5000130`, `greenBuilding→-5000157`,
  `analysisResults→-5000161`, `''→-1`).  Tokens our constructors use that
  the corpus does not witness (`general`, `data`, `electricalCircuiting`)
  → −1, the corpus's own no-group value (43 corpus params), with an adapt
  note.
* `ElectricalLoadClassification` v7→5: `m_signitureType` (int enum,
  house_standard F-HS-4: 1 motor / 2 other / 3 spare / else 0) → two
  bools `m_motor`/`m_spare`.  Mined BOTH sides of the rme sample:
  2023 'Motor'=(T,F), 'Spare'=(F,T), all eight others (F,F); 2026 same
  names carry 1/3/(0|2).  Hooked from the source's own enum.
  (Finding for residue_b: the load-class param CAPTIONS also differ —
  2023 "X Connected"/"X Estimated Demand" vs 2026 "X Connected Apparent
  Power"/"X Demand Apparent Power", 42 captions each way.)
* `StructSettingsElem` v25→22 — EIGHT 2026-only fields dropped (the
  loads-display-scaling block; 2024/2025 dropped one).  Free (walk).
* `GRep` v6→5 (base of every GElement rep): 2026-only `m_elementId`
  (raw i64 kind 0x0b — itself a 64-bit-era addition) dropped.  Free.
* `DrawOrderMgrBase` MISSING-2023: its two weakref fields live directly
  on 2023's `DrawOrderMgr` (chain re-shape).  The skeleton's
  `m_pDetailDrawOrderMgr` body carries the same three fields by name — no
  hook; 45/45 rst views carry the pointer SET matching the skeleton's
  shape (m_pADoc weak-1, m_pDBView weak-2, m_aDrawOrder []).
* Also: `ElemTable` v10→9 (drops 2024's `m_bLastElementIdOverride`),
  `ElementParents` v13→12, `EnergyDataSettings` v15→14,
  `ConstructionSetBase` v4→3, `ViewportAttributes` v4→4(!) drops
  `m_preserveTitlePosition`, `IckyExcludedCategoriesSetPtrWrapper`
  v18→17 GAINS `m_bMassShellExcluded` (corpus False 19/19 = blank — no
  hook), `RbsDuctSettingsElem` v15→13 (2024's kinematic-viscosity rename
  PLUS drops `m_enableNetworkBasedCalculations`), `ElectricalLoadClassification`
  order, `HVACLoadScheduleElem` order-swap (as 2024).  Not constructed
  (name-collision/regen-classref rows, recorded with provenance):
  `FamilyBase` v48→47 (+2023-only `m_bAdHoc`), `IndependentTag` v22→20
  (+`m_taggedEntitiesCell`, `m_leaderEndCondition`), `Rebar` v57→54,
  `Family`, `Section`.

## 3. THE FIELD MAPS — `rvt.genesis.port2023` (wrapper; 2026 constructors untouched)

`adapt()` walks the TARGET 2023 chain field-by-field (port2025's verbatim
method, bound to the 2023 pin): carry same-name fields (recursively
adapting nested values; classrefs re-verified against the 2023 map),
synthesize 2023 schema-blanks, apply `HOOKS_2023`.  2026-only fields
disappear by construction; ids are RANGE-CHECKED into the 32-bit space
(constructor ids ≥ 2³¹ refuse loudly).  `adapt_record()` produces the
2023 `PortedRecord`; `Missing2023` for the 13 constructed no-twin classes.

DELEGATIONS (each precondition asserted in tests, never assumed):

* **rvt.versions.records32 / schema_2023** — the whole 32-bit context +
  schema pin (§1).
* **port2025** — `PortabilityError`, `_AdaptContext`, the
  dec-parameterised blank machinery, `_hook_sort_param_id`,
  `_hook_numbering_min_digits`, `_hook_numbering_matching`,
  `_browser_tracking_tree`, and BOTH numbering hooks
  (`ParameterBasedPartitionDescriptionCreator`, `NumberingSchemaType`,
  nested `ControlledConstDocAccess` all LAYOUT-IDENTICAL 2023==2025;
  GUID table equal — so 2025 blanks ARE 2023 blanks).
* **port2024** — the seven AutoCam rename hooks (2023 v5 ==
  2024 v5 field-for-field), `_hook_duct_viscosity` (same kinematic
  rename; the 2023 rst specimen carries the same bit-exact value),
  `_hook_mep_network_map` (same re-type; empty-only).
* 2023-NEW hooks (this stream's): `ParamDef.m_groupElemId`,
  `ElectricalLoadClassification.m_motor`/`m_spare`; plus the 2023-mined
  re-statements of the shared hooks (GeomTable, wire settings/type, GDI,
  reinforcement, browser org/tracking, numbering).
  DELIBERATELY ABSENT, like port2024: the GeomStep rename hook (2023 has
  NO extra-data field; drops by construction).

Round-trip gate: every adapted object encode→decode→re-encode BYTE-EXACT
under the 2023 codec inside `id32()` — the 17-record battery (wall,
material, line/fill pattern, floor, wire type, distribution system,
numbering schema, pen table, browser org, struct/keynote/wire/
reinforcement settings, autocam, duct, tracker) ALL clean + byte-exact;
5 refusals correct.  Corpus-shape parity: adapted key sets == decoded
2023 sample key sets per class (tested for 8 classes).

## 4. MINERS — all five frozen under `experiments/genesis2023/miners/`

* **category enum 2023** (`builtin_category_enum_2023.json`): **1,053
  categories (327 cuttable)**, identical across the three 2023 basics
  (2024: 1,068/331; 2026: 1,074) — cuttability IDENTICAL on every id
  shared with 2026 (tested).
* **per-key style profile 2023** (`builtin_style_profile_2023.json`):
  **1,380 (category, style-type) keys over 4,140 rows** (2024: 1,399 over
  4,197).
* **pen table 2023** (`pen_table_2023.json`): project table is elem 2 in
  ALL THREE basics; scale keys **[10, 20, 50, 100, 200, 500]**, **16
  pens**, persp/draft **−1** — the 2026 constant HOLDS at 2023; the pen
  constructor ports value-unchanged.
* **palette invariants 2023** (`palette_invariants_2023.json`): **129
  PropertySetElements** (rst 56 / rac 53 / rme 20); `laws_hold=True` —
  param-id ASCENDING in every container, built-in param ids ALL negative,
  `m_pElementIdParams` PRESENT-EMPTY in 129/129 (residue_b2's corpus laws
  hold one release back).
* **defaults 2023** (`defaults_2023.json` — the value-constant census
  with per-specimen provenance): wire settings **0.02 / 0.03 /
  303.15000000000003 K** (rst 102129, rme 293123 — equal to 2024/2025);
  GeomTable dominant **(−1, −1)** over 7,081 censused; GDI False (2/2
  MGS, 66/66 VDM); ReinforcementSettings flag True (rst 137426); wire max
  size label '2000' (rst 55171, rme 261496); NumberingSchema oracle =
  the SAME three GUIDs as 2024/2025 (rst 1218729/1218730/1457391,
  minDigits 1, matching True, creator `{m_ccda{weakref 1},
  m_partitionParameterId −1154614}`); the ParamDef group witnesses (18
  ids); the load-class bool split.

## 5. SPECIMEN VALIDATION (byte-level, where the method allows)

Inside `id32()` against the 2023 rst sample (same specimen element ids as
every release's sample):

* OUR adapted `AutoCamSettingsElem` == specimen **102842** BYTE-EXACT
  (326 B) — the 2026 constructor's byte-exact claim re-proven on 2023
  through the delegated rename hooks.
* OUR adapted empty `MEPNetworkTracker` == specimen **1468014**
  BYTE-EXACT (80 B) — through the map re-type hook.
* OUR `pen_width_table` LAYOUT == specimen **2** BYTE-EXACT (1,169 B)
  with the specimen's own vectors re-fed (widths are values, not format).
* Specimen decode→re-encode round-trip CLEAN + BYTE-EXACT for one host
  specimen of EVERY ported constructor class — 23 classes including
  ParamElemExternal 21308 (the group hook's class),
  ElectricalLoadClassification 113160, DBViewDrafting 1456977,
  PropertySetElement 1463266, GStyleElem 1661 — the 2023 encode stack is
  proven on real bodies, 32-bit ids included.
* The ElemTable parse is verified against the schema-directed id32 decode
  of the whole stream (13,821/13,821 rst rows + the m_last watermark
  1,472,302 == max id).

## 6. FINDINGS for other territories (exact; none applied outside mine)

1. **records32 ElemTable row order** (reduce stream, §1): swap `o, eid`
   in `parse_elemtable32` unpack + `encode_elemtable32` pack to the
   schema-declared id-first order.  Corpus-invisible today; latent for
   any future id≠orig row.  Footer "pad" byte = `m_bExpandAllOnLoad`.
2. **port2025/port2024 harvest coupling** (both port streams): their
   harvests exclude only their own/older port layers, so port2023.py's
   landing adds `Identifier` (+`ParamDef` to the harvested set) to their
   universes.  Effect measured: universe 403→404, one new IDENTICAL row
   (`Identifier`) each, all other verdicts unchanged; both suites still
   pass (50/50) and their self-refreshing frozen-table tests have
   ALREADY rewritten `portability-2025.json` / `portability-2024.json`
   with the +1 row (their write=True design).  Proposed one-liners:
   port2024 `_PORT_LAYERS += ("port2023.py",)`; port2025 adopt the same
   exclusion tuple (it currently excludes only itself, so it also scans
   port2024.py).  Landing those reverts both universes to 403 on next
   derive.
3. **residue_b, for an eventual 2023 build**: the load-classification
   param captions are 2023-different ("Connected"/"Estimated Demand"
   phrasings, §2); the three unwitnessed group tokens map to −1.
4. **versions model**: `KNOWN_RELEASES[2023].creation_certified` stays
   False — correct; a Y2023 substitution ladder should re-point the
   port2025 runner pattern at `port2023.adapt_record` + the frozen 2023
   enum/profile, exactly as `run_ladder2025.py` did (not this stream's
   charter; the reduce stream owns the 2023 base lineage).

## Open questions carried forward

* Does the Autodesk viewer accept 2023 uploads at all?  (The reduce
  stream's batch control decides; nothing here uploads.)
* The three unwitnessed parameter-group tokens: if a future 2023 corpus
  file witnesses `general`/`data`/`electricalCircuiting` groups, extend
  `PARAM_GROUP_ELEM_2023` (the miner asserts every mined id is
  corpus-witnessed).
* A 2023 ladder/composer first run should watch for further baked-width
  literals on the WRITE side beyond records32's table (its "NOT patched"
  list names the 2026-only creation paths).

---

## SUITE RESULT (final, 2026-08-04)

`.venv/bin/python -m pytest -q --continue-on-collection-errors` from the
repo root, after all edits: see BRANCH STATE below (`tests/test_port2023.py`
30/30 green in-suite and standalone; `test_port2024.py` +
`test_port2025.py` 50/50 green with port2023.py present).

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — git repo exists on branch `main`
  with NO commits (staged tree from another stream); this stream made no
  git operations — integration is the orchestrator's.
* NEW (this stream's territory):
  * `src/rvt/genesis/port2023.py`
  * `tests/test_port2023.py` (30 green)
  * `experiments/genesis2023/miners/` — `portability-2023.json`,
    `builtin_category_enum_2023.json`, `builtin_style_profile_2023.json`,
    `pen_table_2023.json`, `palette_invariants_2023.json`,
    `defaults_2023.json`
  * `samples/2023/SOURCES.md` (+ this stream fetched
    `rstbasicsampleproject.rvt`; the other five landed from the reduce
    stream — §0)
  * this record
* Touched OUTSIDE territory: **no file edits**.  Two side effects,
  measured and recorded: (a) running the sibling port suites let their
  own write=True frozen-table tests refresh `portability-2025.json` /
  `portability-2024.json` (+1 `Identifier: IDENTICAL` row each — §6.2);
  (b) `samples/2023/` co-populated with the reduce stream (§0).
* DONE check: confirmed table ✓ (frozen, four-way annotated, known movers
  independent); field maps ✓ (hooked, delegations asserted, round-trip
  byte-exact, 32-bit-range-guarded); miners ✓ (all five frozen);
  validation ✓ (three byte-exact specimen matches + 23 specimen
  round-trips + ElemTable-vs-schema proof).  STOP at READY: nothing
  uploaded, nothing claimed certified.
