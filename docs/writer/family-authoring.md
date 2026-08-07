# Family authoring — reconnaissance and the writer's plan

Stream: `families` (2026-08-03). Code: `src/rvt/families.py` (`family_documents`,
`dump_family`, `self_family_of_unit`, `FamilyIndex`, `encoder_roundtrip`,
`content_documents_by_guid`, `emit_rfa` = F1/F2, `verify_rfa`); dumps + built
`.rfa` files in `experiments/families/`; tests `tests/test_families.py` (14
pass). Confidence tags: **[V]** verified on the corpus by code, **[H]**
hypothesis (needs Revit acceptance), **[D]** design decision. Companion:
`docs/writer/mutation-plan.md` (instance authoring — solved and accepted).

**Status 2026-08-03 late:** F0 ✅ container round-trip; **F1 ✅ BUILT** — a
full-pipeline re-emit of the sample `.rfa` in which EVERY element record of
the family document was decoded and re-serialized by our encoder
(byte-identical: 1,992 elements × 3 seqs), re-blocked with our gzip, every
framed stream carrying REAL recomputed CRCIO ECC, container by our CFB writer
(`experiments/families/F1_rfa_full_reencode.rfa`, self-verify green); **F2 ✅
BUILT** — F1 + one type-parameter default changed with a recomputed record
stamp (`F2_rfa_type_param_edit.rfa`). Both await the Revit/APS acceptance gate.

## 0 · TL;DR

Placing INSTANCES of loaded families is solved. Authoring a NEW placeable
asset (the "Chicago plenum recessed light") means authoring a **family
document**. Tonight's reconnaissance establishes, with code and dumps:

1. A project embeds one **family document per loaded family** as its own
   **save unit** in `Partitions/<N>` (unit 0 = host; rme has **305** embedded
   units, rac 163). The link host → unit is the host `Family` element's
   `m_oFamDoc.m_contentDocGUID` **==** the unit-separator GUID **==** the
   `Global/ContentDocuments` key [V, 147/159 rme + 82/94 rac families resolve;
   the remainder are system / in-place families with no document]. Nested
   families are further top-level units (flat storage, not nested).
2. An embedded family document is a **complete small Revit document**
   (self-`Family`, `Ref. Level`, category/style copies, views, sketches,
   RefPlanes, solid forms with real `GElement` solids, `ParamElemFamily`
   parameters, `ConnectorElem` MEP connectors) and **decodes 100% clean with
   the existing decoder** — 605/605 records for the recessed lighting
   fixture, 551/551 for the 208 V panelboard [V].
3. An **`.rfa` file is the identical container + the identical
   `Formats/Latest` schema** (sha256 `6459a9a9…`, byte-equal to the 2026 project
   schema), with **one save unit = the family document**, the same `Global/*`
   streams (same 8-byte prefixes), the same per-page CRCIO ECC (full-page
   trailers reproduced byte-exact by `rvt.ecc.frame_stream`), plus a plain
   Atom-XML **`PartAtom`** stream (unframed) [V]. **Our existing writer chain
   (CFB + gzip + framing + ECC) emits `.rfa` unchanged.** F0 (container
   round-trip of the 2026 sample .rfa) passes `--verify` tonight.
4. Type/parameter definitions live at the **host** (host `Family.m_pFamilyTypes`
   + host `FamilySymbol`s); geometry, parameter defaults and connectors live
   in the **embedded document**; a `m_big2SmallMap2` on the host `Family`
   maps HOST ids (categories/styles/param elements) → EMBEDDED ids. **In a
   standalone `.rfa` the type table lives INSIDE the document** — its
   self-`Family.m_pFamilyTypes` carries every type's name + parameter set
   (sample rfa: 4 types, `m_idx` = current type; `m_familyParams` == the
   current type's set) [V].
5. **Our encoder re-serializes family documents byte-identically** — every
   record (seq 101/102/103) of the sample `.rfa` (1,993), the rme recessed
   lighting fixture (606) and the rme 208 V panelboard (552) decodes and
   re-encodes to identical bytes (`experiments/families/encoder_roundtrip.json`)
   [V]. F1 (full re-encode + real ECC + our CFB) and F2 (one type-parameter
   edit, stamp recomputed) are BUILT and self-verified (§6).
6. Every embedded document's `ADocument` is locatable in
   `Global/ContentDocuments` by its GUID (305/305 rme) with a fixed entry
   grammar, and its serialization is the SAME `ADocument` a standalone file
   stores in `Global/Latest` with `ElemTable`/`History` inlined instead of
   externalized (§2.1) — the extraction route (F3b) is a mechanical
   inline↔externalized transform [V structure].

Decision [D]: **the first family-authoring target is a standalone `.rfa`**
(clone-and-mutate a family document with no host coupling), then loading
that family into a project (Revit/APS `LoadFamily`, or later our own embedded
route). Rationale in §5.

## 1 · How families are stored [V]

Sample: `samples/rmebasicsampleproject.rvt`, `Partitions/14`
(`experiments/families/inventory_rme.json`).

| item | value | evidence |
|---|---|---|
| save units | 306 = host + 305 embedded documents | `StreamWalker.units`; every unit ≥1 opens with a 28-byte separator carrying a GUID + u32 counter |
| unit 0 | host project, 28,132 records/seq = `Global/ElemTable` count = partition header `elem_table_count` | `test_units_and_host_document` |
| separator counter | == the unit's element-record count (sentinel excluded) | 224/229/612 … all match |
| ids | file-wide unique across all units | `test_element_ids_unique_across_units` (0 overlaps) |
| host → doc | host `Family.m_oFamDoc → FamilyDocument.m_contentDocGUID` == unit separator GUID == `Global/ContentDocuments` key | 147/159 rme, 82/94 rac; e.g. panel family 454674 → GUID `159ccbc8-40de-40ce-82d1-902658f7302b` → unit 243 |
| host → doc ids | `FamilyDocument.m_big2SmallMap2`: `{host id → embedded m_id64}` for the categories/styles/param elements the family uses and the family's own parameter elements | 454674: host 277 (category) → 786406 (embedded CategoryElem); host 454678 → 786443 |
| unresolved families | `m_oFamDoc` null: system families (mullions) and in-place massing ("Sporthalle1", "water") — no document | 12/159 rme, 12/94 rac |
| nesting | a family document's nested-family `Family` elements carry their own `m_contentDocGUID` → their own top-level unit (305 units ≫ 147 host families) | e.g. panel unit contains `Family` 786736 "Section Tail - Upgrade" with contentDoc `4fa25e75…` |
| ContentDocuments entry | `key(GUID) → the embedded document's serialized ADocument + its inline 40-byte element table`; `table_count` == unit counter; the `element_id` after tag 0x0ae9 == the doc's own self-`Family` id (NOT a host id) | entry 0: table_count 224 == unit 1 counter 224, element_id 800414 = a Family in unit 1 |

### 1.1 What a family document contains [V]

`dump_family(idx, unit)` on unit 271, "M_Plain Recessed Lighting Fixture"
(`experiments/families/dump_rme_plain_recessed_light.json`, ids
772,858–887,427, 605 records/seq, decode **605/605 clean** in seq 102 and 103):

| class | count | role | seq-103 rep |
|---|---:|---|---|
| `CategoryElem` / `GStyleElem` | 84 / 84 | private copies of the categories/subcategories the family uses (mapped from host by `big2SmallMap`) | dummy |
| `Family` | 4 | the doc's **self-Family** (772891, all-zero `m_famDocGUID`, no contentDoc, category `-2001120` LightingFixtures, 37 `m_familyParams`) + 3 nested annotation families | dummy |
| `FamilySurrogate` / `FamSymSurrogate` / `FamilySymbol` | 3 / 4 / 4 | nested-family types placed in the family's views (NOT the family's own types) | GElement |
| `Level` | 1 | "Ref. Level" (`m_text`) | dummy |
| `RefPlane` | 13 | reference planes (`m_text` e.g. "Center (Front/Back)"), each a `DatumPlaneGeomStep` + `Face → Plane` | dummy |
| `SketchPlane` / `VarSketch` / `CurveElem` | 22 / 13 / 33 | profile sketches: `VarSketch` (plane, `m_sketchPlaneId`) + `CurveElem` lines/arcs (`m_pCurveDriver.m_pCrv = GLine/GArc`) grouped by `CellList.SketchMembership.m_groupId` | GElement (curves) |
| `ExtrusionElem` | 5 | solid forms: `ExtrusionGStep` (face/edge history tags), params `-1001800`=start `-1001801`=end offset (ft) [H: BIP names], `m_categoryId` (subcategory), `m_materialId` | **GElement solid** (planar faces, edge loops, 3,060 B) |
| `FamilyGeomCombination` | 1 | the join of the 5 solids (`AddGeomToCombinationGStep`) | GElement |
| `ImposterLight` | 1 | the **light source** element: photometric params (`-1150128`/`-1150127` emit shape dims, `-1010505` tilt π/2) | GElement |
| `ConnectorElem` | 1 | the **electrical connector**: `ConnectorElemDomainElectrical{ m_dVoltage 1291.67 (=120 V ÷ 0.3048²), m_dApparentLoadPhase1, m_dPowerFactor 0.95, m_idLoadClassification, m_nNumberOfPoles 1, "Power Connection" }`, `m_oPlaneRef` → host face (`GeomOnPlaneRef.m_geomRef.m_elemId` = an extrusion) | dummy |
| `ParamElemFamily` | 7 | user-defined family parameters (`m_pParamDef.m_caption`: "Ballast Voltage", "Length", "Width", "Depth"; `m_specTypeId` unit spec; `m_instanceParam`) | dummy |
| views/dims/text/settings | ~350 | the family editor's views, dimensions, styles, settings — clonable ballast | mixed |

The self-Family's 37 `m_familyParams` carry the type defaults, including
verified electrical/photometric values (rme units are internal:
value_display = internal × 0.3048² for W/VA/V):

| paramId | internal | ≈ display | meaning |
|---|---:|---:|---|
| `-1140004` | 688.89 | 64 W | wattage [V unit-consistent] |
| `-1010503` | 5699.84 | 529.5 VA | apparent load [H] |
| conn `m_dVoltage` / param 772892 | 1291.67 | 120 V | voltage [V] / user "Ballast Voltage" |
| `-1150107` | 4230 | 4230 K | initial colour temperature [H] |
| `-1150103`, `-1150104..8`, `-1150142` | … | … | photometric block: intensity, efficacy, IES web (`-1150142` = the IES text stored as UTF-16), `-1140034` = "1x42A12.ies" filename [H names, values V] |
| 772893 / 772894 / 772895 | 3.937 / 0.984 / 0.492 ft | 1200 × 300 × 150 mm | Length / Width / Depth (the troffer dims; user params) [V] |

**Where types live [V]:** in a PROJECT the loaded family's TYPES are
host-side — host `Family.m_pFamilyTypes` (`FamilyTypeTable{m_idx,
m_pairs[{name, params}]}`) plus one host `FamilySymbol` per loaded type
(`m_symbolInfo.m_name`, e.g. the panelboard's `'400 A'`); the embedded
self-Family's `FamilyTypeTable` is empty and the embedded doc holds geometry,
parameter DEFINITIONS/defaults and connectors, with parameter definitions on
BOTH sides (host param `Element` ids ↔ embedded `ParamElemFamily`) tied by
`big2SmallMap2`. In a STANDALONE `.rfa` the type table is inside the
document: the self-Family's `FamilyTypeTable` holds all types (sample rfa:
`' '`, `'0610 x 0160mm'`, `'0762 x 0762mm'`, `'0610 x 0915mm'`; `m_idx` = 2 =
current; `m_familyParams` == the current type's parameter set; user params
are positive `paramId`s = the doc's `ParamElemFamily` element ids — 4208
Height / 4209 Width / 4253 Length / 5812 Radius, feet). Loading an `.rfa`
therefore creates the host-side `Family` + `FamilySymbol`s FROM this table.

## 2 · What an `.rfa` file is [V]

`vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa` (a 2026
furniture family; opened by `rvt.container.open_rvt` unchanged):

| aspect | finding |
|---|---|
| container | CFB v4, streams: `BasicFileInfo, Contents, Formats/Latest, Global/{ContentDocuments, DocumentIncrementTable, ElemTable, History, Latest, PartitionTable}, PartAtom, Partitions/69, RevitPreview4.0, TransmissionData` — the project set + `PartAtom` |
| schema | `Formats/Latest` inflates to 496,597 B, sha256 `6459a9a93ebde32c…` **== the 2026 project schema** ⇒ decoder AND encoder reuse as-is |
| element data | ONE `Partitions/69`, ONE save unit (unit 0) = the family document (1,992 records/seq, **1,992/1,992 decode clean**); same block/record/sentinel framing |
| self-Family | id 17, name `''`, category `-2000080` (Furniture), nil `m_famDocGUID` — identical structure to an embedded unit's self-Family |
| `Global/*` prefixes | Latest=5, ContentDocuments=1, DIT=1, History=1, ElemTable=0, PartitionTable=0 — same constants as projects |
| ECC | full-page trailers of `Formats/Latest`, `Global/Latest`, `Partitions/69` reproduced **byte-exact** by `rvt.ecc.frame_stream` ⇒ same CRCIO framing |
| `PartAtom` | 4,046 B **plain Atom XML** (`<entry xmlns=… A="urn:schemas-autodesk-com:partatom">`), title, OmniClass category, Revit grouping, `<A:features>` parameter list; NOT ECC-framed (add to the unframed set with BasicFileInfo/TransmissionData/RevitPreview4.0) |
| F0 | `python -m rvt.roundtrip <rfa> out.rfa --verify` → OK (identical streams, olefile-strict + compoundfiles clean) — `experiments/families/F0_rfa_container_roundtrip.rfa` |

**Conclusion:** an `.rfa` is a project-shaped container whose single save unit
is the family document. **We can WRITE `.rfa` with the same writer chain**;
the only new stream is the trivial `PartAtom` XML. An embedded family unit +
its `ContentDocuments` ADocument entry is essentially the payload of a
standalone `.rfa` (this is what Revit's "Save family out of project" does).

**F1 (built, self-verified) [V mechanism, H acceptance]:**
`experiments/families/F1_rfa_full_reencode.rfa` — `rvt.families.emit_rfa`.
`Partitions/69`: every seq-101/102/103 record of the family document was
DECODED and RE-SERIALIZED by `rvt.encode` (1,992 elements + sentinel per seq,
byte-identical), payloads spliced at the original block boundaries and
re-gzipped by us (level 3 + sync-flush), stream truncated after its end
record; every framed stream (`Formats/Latest`, `Contents`, all `Global/*`,
`Partitions/69`) re-gzipped and re-framed with REAL recomputed CRCIO ECC;
the unframed metadata streams (`BasicFileInfo`, `TransmissionData`,
`RevitPreview4.0`, plain-XML `PartAtom`) copied byte-for-byte; container by
our CFB writer (462,848 B). Read-back: 18 gzip members / 0 CRC failures, 5
full pages / 0 ECC mismatches, walker clean, 1,993/1,993/1,993 records,
1,992/1,992 seq-102 records decode clean, element-id sequences == source,
inflated `Global/*` + schema payloads == source. `rvt.validate` reports the
IDENTICAL findings on F1 as on the original Autodesk `.rfa` (its 5 "errors" —
missing `ProjectInformation`, unframed `PartAtom`, `ElemTable`/`DIT` decode —
are validator gaps for family files, not writer defects; 30,353 refs
checked, 0 decode failures on both) → `docs/inbox/families.md`.
**F2 (built) [V mechanism, H acceptance]:**
`experiments/families/F2_rfa_type_param_edit.rfa` = F1 + ONE type-parameter
default changed: type `'0610 x 0160mm'`, user param 4253 "Length"
2.001312 ft (610 mm) → 3.0 ft (914.4 mm) inside the self-Family's
`FamilyTypeTable`, record re-encoded with a recomputed adler32 stamp
(`3935391679 → 3522383392`, 10 bytes changed, record length unchanged; the
CURRENT type — hence the cached solid — untouched). Reads back as 3.0 with a
valid stamp. Expectation in Revit: the Family Types dialog shows Length 914
for that type.

### 2.1 The `ContentDocuments` entry grammar — embedded ⇄ standalone [V]

`content_documents_by_guid(idx)` locates every embedded document's
`ADocument` in `Global/ContentDocuments` by searching its unit-separator
GUID — **305/305 on rme** (`experiments/families/cd_family_documents_rme.json`).
Every entry has the SAME shape (corrects the earlier "non-null lead
pointers" note — the family entries' pointers ARE null; the old
`content.scan_content_documents` under-count has another cause):

| offset (rel. GUID) | size | field | evidence |
|---:|---:|---|---|
| −16 | 4 | u32 X (varies, e.g. 0x4974) | entry lead word |
| −12 | 12 | `a3 03 ff ff ff ff a2 03 ff ff ff ff` | null lead pointers, identical for all 305 |
| 0 | 16 | content-document GUID (== unit separator GUID) | 305/305 |
| 16 | 4 | u32 `adoc_len` | consecutive entries spaced exactly `adoc_len + 36` |
| 20 | `adoc_len` | serialized `ADocument`, lead u16 `0x001c` | class id 0x1c |

Comparing the recessed light's CD `ADocument` head with the sample `.rfa`'s
`Global/Latest` (inflated, prefix u64 5):

```
CD entry (embedded): 1c 00 | ff ff ff ff c9 05 00 00 00 00 | ff ff ff ff a7 03 01 00 00 00 | ff ff ff ff a0 01 | ff ff ff ff 66 10 | ff ff ff ff 38 05 | ff ff ff ff f8 0f 00 00 00 00 | ff ff ff ff e9 0a | 1b cb 0b 00 …  (self-Family 772,891)
.rfa Global/Latest : 1c 00 | 00 00 00 00 00 00 00 00 | 00 00 ff ff ff ff a7 03 01 00 00 00 | ff ff ff ff a0 01 | ff ff ff ff 66 10 | 00 00 00 00 | ff ff ff ff f8 0f 00 00 00 00 | ff ff ff ff e9 0a | 11 00 00 00 … (self-Family 17)
```

Same `ADocument` field sequence (0x3a7 ContentTable, 0x1a0, 0x1066, 0xff8,
0x0ae9 = self-Family id, …); the embedded copy INLINES `ElemTable` (0x5c9)
and `DocumentHistory` (0x538) where the standalone file externalizes them to
`Global/ElemTable` / `Global/History` (those pointer slots read 0). ⇒ the
**F3b extraction** (embedded lighting-fixture doc → standalone `.rfa`) is a
mechanical transform: unit records → `Partitions/N` (drop the separator; the
run becomes unit 0), CD `ADocument` → `Global/Latest` with the inline
`ElemTable`/`History` split OUT into their `Global/*` streams, remaining
`Global/*` + `PartAtom` templated from the sample `.rfa`. The `ADocument`
field-level decoder needed for the split is R3 (still open; `global_latest.py`
is a framing mapper only), but every input byte is now addressable.

## 3 · The clone-and-mutate recipe for a new luminaire family [D]

Author the plenum recessed light by cloning the closest real specimen — the
embedded **"M_Plain Recessed Lighting Fixture"** document (unit 271 of rme,
host family 365618, category LightingFixtures, 1 type, 1 electrical connector,
5 extrusions + 1 combination + 1 light source) — or, preferably, a
**standalone lighting-fixture `.rfa` donor** (§5, F3).

The donor supplies every field the spec does not name (views, styles, load
natures, dimension chains, sketch grids…). The writer patches:

| edit | where | fields |
|---|---|---|
| family name | host `Family.m_name` (project) / `PartAtom <title>` + `BasicFileInfo` path (rfa) | AString |
| type name / new type | host `FamilySymbol.m_symbolInfo.m_name` + host `Family.m_pFamilyTypes.m_pairs[]` | AString + params clone |
| dimensions (aperture Ø, trim, housing depth) | embedded self-`Family.m_familyParams[paramId]` defaults + `FamilyTypeTable` pair values; the driven sketch `CurveElem` `GLine/GArc` (`m_origin`, `m_dirVec`, `m_endParams`) and `ExtrusionElem` start/end params (`-1001800/-1001801`) | doubles (feet) |
| geometry solid | `ExtrusionElem` seq-103 `GElement`: rigid-transform / rebuild face `Plane`s + `EdgeLoop` envelopes (same trick as instance reps); or emit `SerializedDummy` and rely on regeneration [H — F4 decides] | GElement or dummy |
| lumens / wattage / voltage / CCT | self-`Family.m_familyParams` (`-1140004` wattage, `-1150107` CCT, photometric `-1150103..`), `ConnectorElem.m_pDomain` (`m_dVoltage`, `m_dApparentLoadPhase1`, `m_dPowerFactor`, poles), user `ParamElemFamily` values | doubles (internal units: display ÷ 0.3048² for W/V/VA) |
| connector | keep the donor's `ConnectorElem` (electrical, "Power Connection"); optionally set poles/voltage/load — its `m_oPlaneRef` must reference a face of a kept extrusion (`m_geomTag`) | ids/tags from donor |
| identity | new ids for every element in the doc IF written into a project (file-wide uniqueness) — standalone `.rfa`: ids may be kept | i64 ids + `adler32` stamps + `ElemRec`s |
| document identity | new `m_contentDocGUID` (project) / `BasicFileInfo` GUIDs + `History` episode (rfa), like the project save bookkeeping | GUIDs |

Everything above is a decoded-dict edit + re-encode through the existing
`rvt.encode.encode_record` (stamp = `adler32(u16 class + object)`), then the
proven block/gzip/ECC/CFB chain — no new binary primitives.

### 3.1 Referencing a family document from the host (embedded route) [V structure]

For a NEW embedded family (later phase), the host must gain: (1) a new save
unit in `Partitions/<N>` = separator{new GUID, record count} + the document's
records (3 seqs, sentinels, footer) — units 1..k are copied verbatim, ours is
appended before the stream end record; (2) a `Global/ContentDocuments` entry
keyed by the new GUID (GUID-sorted map) holding the document's ADocument +
inline element table; (3) a host `Family` element (`m_oFamDoc{
m_contentDocGUID = new GUID, m_big2SmallMap2 = host→embedded id map}`,
`m_familyIds`, category, `m_pFamilyTypes`), one host `FamilySymbol` per type,
their `ElementHeader`s + `ElemRec`s; (4) the host save bookkeeping
(`mutation-plan.md` §7). Entry framing per §2.1 (u32 X + null lead
pointers + GUID + u32 adoc_len + ADocument, entries back-to-back with 36 B of
framing); `families.content_documents_by_guid` addresses all 305 rme entries.
The older `content.scan_content_documents` under-counts (32/305) for a
reason OTHER than the pointer nullness (all family entries carry null lead
pointers) — inbox note revised; the writer for this route should build
entries from the §2.1 grammar rather than depend on that scanner.

## 4 · Referential map of the recessed-light document [V]

From the dumped headers (seq 101 `ElementParents`):
extrusion 773293: `m_deletion = [772891 (self family), 773292 (its
VarSketch), 773293 (self)]`, `m_appearanceParents = [self family, sketch]`,
`m_regenOnly = [127]` (internal graphics category); the connector 773363's
`m_oPlaneRef.m_geomRef.m_elemId` → an extrusion face (`m_geomTag`);
`CurveElem.m_famId` = the doc self-family, `m_ownerDBViewId` = a doc view;
`VarSketch.m_sketchPlaneId` → its `SketchPlane`; nested annotation families'
`FamSymSurrogate.m_elemId` → their `FamilySymbol`. **All references are
INSIDE the document except the categories/styles/params, which are the doc's
own copies (mapped from the host via `big2SmallMap`, or self-contained in an
`.rfa`).** ⇒ a family document is a closed graph: safe to transplant wholesale.

## 5 · Risk list

| risk | note | mitigation |
|---|---|---|
| R1 no standalone LIGHTING `.rfa` (2026) donor on disk | we only hold a 2026 furniture `.rfa`, plus the embedded lighting doc inside rme | ask the user/brothers for one standard Autodesk lighting-fixture `.rfa` (2026), OR implement CD-entry decoding to EXTRACT unit 271 + its ADocument from rme into an `.rfa` (F3b) |
| R2 cached solid vs edited params | families store real `GElement` solids for forms; a depth/profile edit that leaves the cached solid stale may render wrong or fail regen | F4 tests param-only edit vs param+solid rebuild vs `SerializedDummy` rep; rebuilding a planar-face extrusion solid is mechanical (faces are `Plane`s + `EdgeLoop` envelopes) |
| R3 `Global/Latest` / CD `ADocument` not yet decoded field-by-field | needed only for the extraction route (F3b): split the inline `ElemTable` (0x5c9) / `History` (0x538) out of the embedded ADocument | clone the donor `.rfa`'s `Global/Latest` verbatim (route a, done in F1/F2); write the ADocument field decoder against `Formats/Latest` (`ADocument` v2662, 19 fields) only if F3b is chosen — every input byte is now addressable (§2.1) |
| R4 embedded-route CD entry write | the entry grammar is now known (§2.1); the old scanner's under-count is irrelevant | build new CD entries from the §2.1 layout when the embedded route is taken; not needed for the `.rfa` route |
| R5 `PartAtom` fidelity | Revit reads title/category/parameters from it for the type catalog UI; a mismatch may only mislabel, but keep it consistent | regenerate the XML from the mutated params (schema is public Atom + `urn:schemas-autodesk-com:partatom`) |
| R6 version pin | families are per-release like projects (`Partitions/69` in 2026, 58 in 2016); an `.rfa` newer than the target Revit will not load | keep the brothers' Revit version pinned; 2026 corpus today |
| R7 lighting photometrics semantics | BIP ids `-1150xxx` observed but names inferred [H] | keep donor values; only override wattage/CCT/voltage/dims whose meaning is unit-verified |
| R8 project-load of our `.rfa` | our `.rfa` must survive Revit's family LOAD into a project (which re-embeds it) | this is the acceptance gate for F1–F5; a load exercises the whole document, stricter than the translator |

## 6 · Experiment sequence [D]

Same discipline as walls/instances: one variable per file, run through the
Windows/APS gate. Outputs to `experiments/acceptance/F*.rfa`.

| id | build | expectation | de-risks |
|---|---|---|---|
| **F0** ✅ | container round-trip of `racbasicsamplefamily-2026.rfa` (`rvt.roundtrip --verify`) | done — stream-identical | rfa container = rvt container |
| **F1** ✅ built | FULL pipeline re-emit of the sample `.rfa`: every record decoded → re-encoded by our encoder → re-blocked → re-gzip → real ECC → our CFB, zero semantic change (`experiments/families/F1_rfa_full_reencode.rfa`; `emit_rfa`; self-verify green — 0 CRC / 0 ECC / 1,992/1,992 clean, id sets == source) | opens in the family editor identical to the original | encoder + framing + ECC + container on family classes |
| **F2** ✅ built | F1 + one type-parameter default changed (type `'0610 x 0160mm'` Length 4253: 610 mm → 914.4 mm in the self-Family's `FamilyTypeTable`, stamp recomputed; current type / cached solid untouched) (`F2_rfa_type_param_edit.rfa`) | Family Types dialog shows Length 914 for that type | param edit + `adler32` stamp on a family object |
| **F3a** | obtain a standalone Autodesk lighting-fixture `.rfa` (2026) → repeat F1 on it | opens | domain donor in hand (preferred) |
| F3b | (only if no donor) extract unit 271 "M_Plain Recessed Lighting Fixture" from rme into a synthesized `.rfa`: unit records → `Partitions/N` unit 0; its CD `ADocument` (§2.1) → `Global/Latest` with inline `ElemTable`/`History` split out to their `Global/*` streams; other `Global/*` + `PartAtom` templated from the sample rfa | opens as a family | family extraction; needs the ADocument field decoder (R3) |
| **F4** | recessed-can geometry: change the extrusion depth (`-1001801`) three ways — (a) param only, (b) param + rebuilt planar-solid `GElement`, (c) param + `SerializedDummy` rep | which one loads/renders correctly | R2 (the load-bearing geometry question) |
| **F5** | rename family (`PartAtom`, BasicFileInfo; Revit takes the family NAME from the file name) + set wattage `-1140004` / CCT `-1150107` / connector voltage-poles + dims via user params | Family loads, schedules the new values, connector reports 120 V / load | electrical + photometric edits |
| F6 | profile edit: rewrite the profile sketch `CurveElem`s (a 4-line rectangle → new Ø / a `GArc` circle) + regenerate | new aperture shape | full geometry authoring |
| F7 | LOAD the F5 `.rfa` into rme (Revit UI / APS) and place it (existing `add_family_instance`) — or the native embedded route (§3.1) | luminaire in the project, circuitable | end-to-end product path |

DONE for this stream = the inventory code + dumps + this plan (met, plus F1
and F2 built as a bonus). **Acceptance gate next:** run
`F1_rfa_full_reencode.rfa` (T0 — must open identical) and
`F2_rfa_type_param_edit.rfa` through the Windows/APS translator or Revit's
family editor. A pass on F1 proves the entire native writer chain on family
files; a pass on F2 proves edited + re-stamped family objects load.

## 7 · Confidence / unknowns

| claim | status |
|---|---|
| unit 1..k = embedded family documents; host `Family.m_contentDocGUID` == separator GUID == CD key; ids file-wide unique; counter == record count | **V** (rme 147/159, rac 82/94, code + tests) |
| a family document is a closed, fully decodable object graph (self-Family, sketches, RefPlanes, forms w/ GElement solids, connectors, params) | **V** (605/605, 551/551, 1992/1992 clean) |
| our encoder re-serializes family documents byte-identically (all 3 seqs) | **V** (1993 + 606 + 552 records, 0 failures) |
| `.rfa` = same CFB + same schema + same framing/ECC + one unit + plain-XML `PartAtom`; our writer emits it unchanged | **V** (schema sha match, full-page trailers byte-exact, F0 verify, F1 built + self-verified, validator parity with the original) |
| project: types host-side (`FamilyTypeTable` + `FamilySymbol`), doc-side geometry/param-defaults/connectors, tied by `big2SmallMap2`; standalone rfa: types inside the doc's self-Family `FamilyTypeTable` | **V** structure |
| every embedded ADocument is GUID-addressable in `ContentDocuments`; same ADocument as `Global/Latest` with `ElemTable`/`History` inlined | **V** structure (305/305; lead-byte comparison) |
| BIP semantics for wattage/voltage/dims | **V** (unit-consistent values); photometric `-1150xxx` names **H** |
| cached solid can be left stale / dummied and regenerates | **H — F4** |
| a re-emitted / mutated `.rfa` opens in Revit and loads into a project | **H — F1/F2 built, awaiting the acceptance gate** |

## 8 · Reproduction

```
.venv/bin/python -m rvt.families            # inventories + dumps + encoder_roundtrip.json
                                            # + cd_family_documents_rme.json + F1/F2 .rfa + reports
.venv/bin/python -m rvt.families --no-experiments   # inventories + dumps only
.venv/bin/python -m pytest tests/test_families.py -q                              # 14 passed
.venv/bin/python -m rvt.roundtrip vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa \
    experiments/families/F0_rfa_container_roundtrip.rfa --verify                  # F0
# python:
#   from rvt.families import FamilyIndex, family_documents, dump_family, emit_rfa
#   idx = FamilyIndex.open('rmebasicsampleproject'); rows = family_documents(idx)
#   dump_family(idx, unit=next(r['unit'] for r in rows if 'Recessed' in (r['family_name'] or '')))
#   emit_rfa(SAMPLE_RFA, 'out.rfa', edits=[{'param_id': 4253, 'value': 3.0, 'type_name': '0610 x 0160mm'}])
```
