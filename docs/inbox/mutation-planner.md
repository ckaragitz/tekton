# inbox — mutation-planner (writer wave): out-of-scope findings for the orchestrator

Deliverables: `docs/writer/mutation-plan.md` (the writer's algorithm),
`docs/writer/template-catalog.md`, `docs/writer/specimens/` (19 annotated
real elements + `make_specimens.py`), `src/rvt/mutate.py` (planner:
`Document.add_wall / add_family_instance / diff / plan`),
`tests/test_mutate.py` (13 pass). Please merge into KNOWLEDGE.md:

## 1. SOLVED — the record `stamp` (KNOWLEDGE unknown B8, 10-objects §11)

The `u32 stamp` in every seq-102/103 record header = **`zlib.adler32(u16
class_id + object bytes)`** — Adler-32, NOT crc32. Verified 287,441 /
287,441 records (racbasic + rme + racadv, seq 102 and 103), zero exceptions.
Corollaries: the id −1 sentinel's stamp 1 = adler32(empty); the seq-103
`SerializedDummy` constant 0x0069003C = adler32(`2c 0f`). The writer can
compute it after serialization (`rvt.mutate.record_stamp`). Please update
10-objects §11 and KNOWLEDGE "Partitions".

## 2. CORRECTION — save units are DOCUMENTS, not incremental saves

KNOWLEDGE "blocks group into save units (racbasic 164): unit 0 = original
save; each unit … = one incremental save" is wrong. **Unit 0 = the host
(project) document: its seq-102 record ids == the `Global/ElemTable` id set
EXACTLY** (racbasic 8,401 = 8,401; rme 28,132; racadv 17,231 — set
equality). **Units 1…k = one embedded content/family document each**,
preceded by the 28-byte separator whose GUID = that document's
`Global/ContentDocuments` key and whose `u32 counter` = the document's
record count (racbasic unit 1: GUID 34b22600-… = CD entry-0 key, counter
225 = its 225-record element table; unit 0 + Σ counters = 85,814 = all
records). ElementIds are unique file-wide across host + embedded documents
(rme: 142,174 records, 0 duplicates). Also: each unit's per-seq segment
ends with exactly one id −1 sentinel record (last record, not first).

## 3. `Partitions/<N>` naming = increment history, `DocumentIncrementTable` DECODED

`Global/DocumentIncrementTable` is a plain schema object (`u16 0x53c` +
`DocumentIncrementTable{m_increments, m_localIncrements, m_permutation}`
+ `u32 0`) that `ObjectDecoder.decode_record(0x53c, payload[2:])` decodes
cleanly. Each `DocumentIncrement` (0x53a) = ONE SAVE: `m_majorVersion`,
`m_userName` (zhangg / hansonje / loboarch / suju / campbes / xuew /
guanq), `m_atimeStamp.m_lsb` = Unix save time (racbasic: 2015-11-09 →
2025-03-13, 16 saves), `m_greatest` = max EpisodeId, `m_totalEpisodes`,
`m_incrementVersions[{caused, m_totalElements}]` where the last row's
`m_totalElements` = the partition record count (85,814), and per-stream
revision counters that go +1 per save. `Partitions/N` N = current major
version − 1 (racbasic 16 rows → /15, rme 15 → /14, racadv 14 → /13,
rstbasic 22 → /21, dach 86 → /84,85); the "first u32 = max(N)+1" in
KNOWLEDGE is just the container count. => saves do NOT append units and
do NOT create new partition streams; the stream is rewritten wholesale.

## 4. `Global/*` object streams are uniform: `u16 class + object + u32 0`

`Global/ElemTable`, `DocumentIncrementTable` (and by wave-1 evidence
`History`) all decode as ONE schema object with the ordinary object
decoder followed by a `u32 0` trailer. ElemTable's "footer" fully decodes:
`m_graveyardRecs []`, `m_pSource -> IdentifierSource{m_last = 1,098,947}`
= the id watermark (last issued ElementId; class 0x96a name resolved),
`m_bExpandAllOnLoad/m_bLastElementIdOverride = false`. `elemtable.py`'s
ad-hoc footer fields (`marker`, `tail_class`, `tail_pad`, `last_id`,
`tail_zero`) can be replaced by the schema decode; the id watermark it
extracts is right. Recommend: retire the hand parsers of ElemTable /
DocumentIncrementTable / History in favour of `ObjectDecoder` on the
stream's lead class (B2 in 10-objects). `Global/Latest` also STARTS as
`ADocument` (0x1c) under the object decoder (m_storedByRevitBuild = the
build-string list per save, ends "Revit 2026 … 20250227_1515") but its
pointer/object-index framing diverges after 16.5 KB — the global-latest
agent should try the schema decoder there rather than the wave-1 heuristics.

## 5. Bug: `content.py::scan_content_documents` mis-frames rme

On `rmebasicsampleproject` the marker/GUID scanner reports only 32
ContentDocuments entries while the partition holds 305 embedded-document
units; entries ≥ 17 have garbage owner ids (2233790934208769370 …) and
absurd `table_count`s — the entry framing there is a variant not handled.
The `owner` (`m_ownerFamilyId`) values of clean entries do resolve to
`Family` elements (rme entries 0–16: 800414, 801955 … all `Family`),
confirming §4.5 of 06-content-history — but the map is incomplete/garbled
for the extended-entry files. Suggest re-deriving ContentDocuments through
the schema decoder (ADocument-shaped objects) rather than marker scanning.

## 6. Hosting / instantiation facts (for KNOWLEDGE and the product spec)

- Doors (16/16) and windows (17/17): `InstanceInfo.m_symbolId` ≠
  `m_masterSymbolId` — every host-cut instance references a per-host
  geometry-symbol CLONE (an unnamed `FamilySymbol` carrying cut loops); the
  master type is `m_masterSymbolId`. Placing a door = instance + clone
  (reusable if a same-type door already sits in a same-type wall).
- Free-standing and face-based instances use `symbolId == masterSymbolId`
  directly (202/495 racbasic; ALL rme electrical equipment). All rme
  panelboards/transformers/receptacles are face-hosted:
  `m_workPlaneBased = true`, `m_hostId` = a **SketchPlane** element on the
  host face, and several instances share one SketchPlane (581482–581485 on
  581481). Placing equipment on a face already carrying equipment needs
  NO new SketchPlane.
- Levels/grids/families/circuits have `SerializedDummy` reps; walls,
  rooms, symbols, wall types and instances carry `GElement` reps. Instance
  reps are ~300–600-byte formulaic `GElement{GInstance{InstanceInfo}}`
  (clonable); wall reps are 4–56 KB solids (regenerate — open acceptance
  question, mutation-plan T2).
- Unit-0 record order is neither id, episode nor dependency order (2,698 of
  4,239 sampled parent refs point forward) — consistent with an unordered
  container's iteration; treat as arbitrary but keep it identical across
  the three seqs.
- `ElementHeader` field is spelled `m_categroryId` (sic, in the schema).
- racbasic Level 800333 "Level 1" is an in-place-family-owned level
  (`m_unplacedOwnerId` 800214) sitting in the host ElemTable — filter
  levels on `m_unplacedOwnerId == -1`.
- Category id guesses that need a BuiltInCategory table (not in the
  schema): −2000080 furniture, −2000100 casework, −2001140 = mechanical
  equipment (WSHPs/cooling towers — NOT furniture), −2001160 plumbing
  fixtures, −2001300/−2001330 columns/structural columns, −2001350
  speciality equipment, −2001360/−2001370 planting/entourage, −2008037 =
  the `m_categroryId` of `RbsElectricalSystem` records (electrical circuit
  systems). A BuiltInCategory/BuiltInParameter id table is wanted
  corpus-wide (add to the enum-table task, B5).

## 7. Product implication (for the orchestrator / skill design)

Instantiating LOADED types is cheap (clone + patch); LOADING a new family
= writing a new embedded document (unit + ContentDocuments entry + Family/
FamilySymbol elements + its own element table) — an order of magnitude
harder. Therefore: **curate one rich seed template per discipline
pre-loaded (in real Revit, via the brothers' seat) with every family the
product line needs**, re-extract it, and let the generator only ever
instantiate. The building-spec JSON should map abstract types onto the
seed catalog (`template-catalog.md`).
