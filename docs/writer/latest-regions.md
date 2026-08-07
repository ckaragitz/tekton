# `Global/Latest` — the non-object landmark regions (map + three determinations)

Stream: **adoc-landmarks** (2026-08-03). Tool: `tools/latest_map.py`
(`latest_map(payload)`); per-sample maps: `experiments/genesis/latest/map_<sample>.json`;
tests: `tests/test_latest_map.py`. Record: `docs/inbox/adoc-landmarks.md`.
Scope: the parts of the inflated `Global/Latest` (the serialized `ADocument`,
class 0x1c) that are NOT the schema-directed object graph — the Forge JSON
corpus, the string tables, and the ElementId-reference registries — plus the
three determinations the genesis audit (`docs/inbox/genesis-audit.md` §B2/§D)
asked for. All numbers were measured this session on the six 2026 samples via
`rvt.container.open_rvt(...).inflate('Global/Latest', 0)`.

Prior framing pass to correct: `docs/streams/03-global-latest.md` (wave 1) was
written on the pre-de-paging (garbled) payload. Its "opaque compressed
continuation of the units dictionary (56 % of the stream, byte-oriented LZ
codec)" **does not exist** — it was the page-framing artefact. On the correct
payload the JSON corpus is **plain UTF-16 text end to end**; there is no
second codec. Its region offsets and inflated sizes (racbasic "1,506,910") are
also stale (true size 1,500,644).

---

## 0. Verdict (the three determinations)

**(a) The Forge JSON corpus is IDENTICAL, byte-for-byte, in all six samples —
product data every Revit 2026 file carries, not project data.** Two tables,
893 unit-schema documents (796,206 bytes, sha-256 prefix `093048af34059e5f`)
and 422 spec / parameter-group documents (537,134 bytes, `f7d62970ac9b1bfb`),
= **1,333,340 bytes**, identical hashes in racbasic, rstbasic, racadv,
rstadv, rme and dach (verified: `tools/latest_map.py --identity`). Only the
40-byte header of table 1 differs (it holds the owning element's id). So the
corpus is not "the units the project uses" — every one of the six carries the
complete same set. **Determination: (a), NOT (b).**

**(c) It is Autodesk's *installed* unit-schema set, and it can NOT be
regenerated clean-room from a public open-source repository** — but it is not
sample-project expression either. Public facts (§2.4): Revit installs a
separate component, **"Autodesk Revit Unit Schemas"** (`RevitUnitSchemas.msi`),
into `C:\Program Files\Common Files\Autodesk Shared\Revit Schemas 20XX
Release`; Revit refuses to start without that folder; the six samples' corpus
is the serialized image of that installed schema set (the same `typeid`
namespaces Revit's public API exposes as `UnitTypeId` / `SpecTypeId` /
`SymbolTypeId` / `GroupTypeId`). No `autodesk-forge` GitHub repository
publishes these schema JSON documents; the public Autodesk Schema Repository
Portal (`schema.autodesk.com`) is a login-gated SPA with no anonymous JSON
endpoint we could reach. The identifier SET is fully public (Revit API docs list
every typeid) — the schema DOCUMENTS are Autodesk-authored and ship only with
the product. **No licence text of any kind is embedded in the corpus** (0 of
1,315 documents contain `license`, `copyright`, `Apache`, or terms). So the
corpus stands next to `Formats/Latest`, not next to the room names: it is
*product runtime data present identically in every file* (like the class
schema), and whether we may emit it is the **same counsel question C4**, with
the same two engineering answers on offer — (i) emit the identical bytes every
Revit file carries, or (ii) source them from the customer's own licensed install
(byte-identical). It is NOT "regenerate from an Apache-2.0 repo" — that repo
does not exist. **Determination: (c) is FALSE as stated; the corpus is product
installation data (§2).**

**(2) Strings — PROJECT data vs PRODUCT data are cleanly separable, and the
project data is small.** The project-authored strings (must become OURS in
genesis) are: view names ('Elevation 1', 'Section 1'), sheet numbers ('101',
'A001', 'S206', 'FOUNDATION-2700', '208', '106B'), assembly names ('L1 wall
frame hall 5'), room names ('Hall', 'Kitchen & Dining', 'Master Bedroom',
'Bathroom 1' …, 12 in rstbasic / 11 in racbasic), colour-scheme names and
range labels ('Rooms : Name', 'Areas : Rentable Area', 'Less than 40 m²' …
'360 m² or more'), material names in the analytical tail ('Concrete 10 MPa',
'250 MPa'), the `LB_*` reconcile map (per-element `{LocalId, ExternalId}`
JSON rows keyed to the sample's element ids), and the user names ('macalis',
'liqi'). Everything else that is text is product: the 8 build strings, the
1,315 Forge documents, 'Autodesk Revit' ×N (ExServices vendor), the
secondary-data class names ('ColorFillSecondaryData', 'MEPNetworkSecondaryData'
…), numbering partitions ('Rebar Numbering', 'Fabric Sheets Numbering'), the
`RbsSystem`/`RbsWireCurve` system-class pairs, updater ids
('ObjectNumberingUpdater'), 'WireSizes.xml', 'Revit Default DB Server' /
`http://www.autodesk.com` / 'ADSK', browser-organization folder names ('3D
Views', 'Structural Plans' — product defaults, user-renamable), MEP naming
tokens ('Space Name', 'Number of Circuits', 'Apparent Power'). Full census
per sample in the maps (each string cluster carries a `product / project /
ambiguous` count from `classify_string`).

**(3) The dangling ids are NOT a deleted-element registry — they are the
ADocument's live element indexes.** G0's `Global/Latest` (byte-identical to
rstbasic's, 1,586,246 B) holds **10,002 ElementId64 references to 6,405
distinct rstbasic element ids, 0 to G0's own 205 ids** — every one dangling.
Clustered by contiguity/stride they sit in exactly three registry kinds
(`--dangling`, §4): **id-maps — 4,167 distinct ids** (the BuiltInCategory →
CategoryElem/GStyleElem tables, the (category, graphic-style) pair table, the
parameter-binding map ParamElem → ParamBinding, the Rebar/RebarInSystem
numbering-sequence registries); **id-arrays — 2,724 distinct ids** (per-class
element-id index arrays: every FamilyInstance/wall/load, all MaterialElem,
Fill/LinePatternElem, AppearanceAssetElem, SunAndShadowSettings, the view
list, HVAC/electrical settings catalogs, DBViewType/default-type registry);
**scattered typed pointers — 143 distinct ids** (colour-fill / sketch /
dimension entries inside the NOBLE secondary data). There is no graveyard,
no selection set, no per-view visibility list in this stream: the ADocument
carries the document's **category catalogue, its per-class element index, its
parameter-binding registry and its numbering state** — i.e. the whole element
inventory G0 deleted, still enumerated. This is why "does the reader tolerate
a fully-dangling ADocument" is the load-bearing question: the reader is being
asked to enumerate ~6,400 ids that resolve to nothing.

---

## 1. The byte-region map — how `latest_map` classifies

`latest_map(payload, elem_ids)` → `[{start, end, kind, notes}]`, tiling the
payload exactly (gaps become `unknown`), kinds:

| kind | detector | what it is |
|---|---|---|
| `json-corpus` | `find_json_tables`: `u32 count` + `count ×` (AString `autodesk.*` typeid, AString `{…json…}`) walked to exhaustion | the two Forge schema tables (§2) |
| `string-table` | `scan_strings` (length-prefixed printable UTF-16, ≥60 % ASCII) clustered by ≤256-byte gaps; each cluster carries a product/project/ambiguous count | build list; view/sheet/room/scheme/parameter names; `LB_*` map |
| `id-array` | ElementId64 hits (int64 LE ∈ the file's `Global/ElemTable` id set, id ≥ 100) clustered ≤64 B, dominant stride **8** | `u32 count + n × i64` index arrays |
| `id-map` | same clustering, dominant fixed stride **>8** (12/16/20/24…), plus a second pass merging equal-period runs of small clusters (fixed-size id-keyed records) | id-keyed record tables |
| `object-graph` | the constant 0x53-byte ADocument prologue, `m_oExServicesUsed` GUID map, the u32-keyed manager registry, NOBLE secondary-data blocks (dominated by `*SecondaryData` schema strings), scattered id pointers | typed sub-objects — the schema-directed decoder's territory |
| `unknown` | none of the above | see §5 (dach) |

Coverage (`% of bytes in classified regions`), per sample:

| sample | payload | json-corpus | strings | id-array | id-map | object-graph | unknown | classified |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| racbasic | 1,500,644 | 1,333,376 (88.85 %) | 12,609 | 25,668 | 68,768 | 38,334 | 21,889 | **98.54 %** |
| rstbasic (= G0) | 1,586,246 | 1,333,376 (84.06 %) | 44,181 | 33,646 | 104,829 | 40,376 | 29,838 | **98.12 %** |
| racadv | 1,645,873 | 1,333,376 (81.01 %) | 75,803 | 38,422 | 73,551 | 106,173 | 18,548 | **98.87 %** |
| rstadv | 1,704,781 | 1,333,376 (78.21 %) | 202,455 | 41,569 | 79,756 | 29,169 | 18,456 | **98.92 %** |
| rme | 4,655,284 | 1,333,376 (28.64 %) | 57,979 | 144,847 | 599,645 | 2,374,904 | 144,533 | **96.90 %** |
| dach | 4,762,933 | 1,333,361 (27.99 %) | 181,267 | 250,180 | 172,490 | 535,331 | 2,290,304 | 51.91 % |

The corpus is a fixed **1.33 MB** in every file, so its *share* falls as the
document grows (89 % of racbasic, 28 % of rme/dach). rme's extra 3 MB is the
NOBLE analysis cache (5,230 `ColorFillSecondaryData` + 3,057
`MEPNetworkSecondaryData` "Network Calculation" + HVAC/piping system entries —
object-graph). dach's residue is §5.

Fixed head (identical structure in all six; racbasic offsets):

| off | size | region | note |
|---|--:|---|---|
| 0x0000 | 83 | prologue (`object-graph`) | byte-identical in all six; `1c` = ADocument, `66 0a` = v2662 |
| 0x0053 | 874 | `m_storedByRevitBuild` (`string-table`) | 7–12 build strings, PRODUCT (file lineage) |
| 0x03bd | 15,546 | `m_oExServicesUsed` (`object-graph`) | 163 GUID-keyed entries (52…1,243 across files), vendor "Autodesk Revit" — product service/add-in ids |
| 0x4077 | 1,320 | u32-keyed manager registry (`object-graph`) | 172 singleton managers (keys 2..17x), no element ids |
| 0x4601 | ~21 K + | `m_oNobleSecondaryData` (`object-graph`) | `NobleDocWarnings` + `ColorFillSecondaryData` entries (86 racbasic / 119 rstbasic / 5,230 rme) — the ANALYSIS CACHE, carries the colour-scheme name strings and scattered element ids |
| … | ~90–130 K | element registries (id-array / id-map / string clusters, §4) | view/sheet names, category tables, per-class id indexes |
| `T1` | 796,246 | Forge table 1 (`json-corpus`) | 40-B header + 893 pairs |
| `T1`+ | 8..84 K | ES-schema list (see §2.5) | u32 count + GUID-keyed Extensible-Storage schema descriptors (0 racbasic / 2 rstbasic / 2 rme / 175 dach) — project-specific (add-ins used) |
| `T2` | 537,138 | Forge table 2 (`json-corpus`) | u32 count + 422 pairs |
| tail | 25–90 K | settings tail + `LB_*` + room/level records | numbering, DB server, `RbsSystem` pairs, reconcile map, room names |

`T1` starts at racbasic 0x2218f / rstbasic 0x26c0e / racadv 0x33118 / rstadv
0x2554c / rme 0x264fba / dach 0x2cf6d5.

---

## 2. The Forge JSON corpus — characterization

### 2.1 Framing

Table 1 header (40 bytes): `i64 ownerElementId` (802,435 racbasic;
1,463,828 rstbasic; 258,639 racadv; 254,701 rstadv; 726,113 rme; 4,183,755
dach — the id of the units element that owns the registry, the ONLY
per-project field), `i64 −1`, `i64 1`, `i64 −1`, `u32 1`, `u32 count = 893`.
Then 893 × (AString typeid, AString json). Table 2 = `u32 count = 422` + 422
pairs, separated from table 1 by the ES-schema list (§2.5). Each entry key is
the document's own typeid; the value is a self-contained JSON document
(pretty-printed 3-space in some, compact in others — the mixed formatting is
the fingerprint of concatenating authored schema *files*, not of a serializer).
Example (table 1):

```
key   autodesk.unit.unit:meters-1.0.0
value {
   "annotation": { "description": "Meters are the SI base unit of length." },
   "typeid": "autodesk.unit.unit:meters-1.0.0",
   "inherits": [ "autodesk.unit:unit.primitive.dimensional-1.0.0" ],
   "constants": [
      { "id": "name", "value": "Meters" },
      { "id": "unitSystem", "value": "Metric" },
      { "id": "dimension", "typedValue": { "typeid": "autodesk.unit.dimension:length-1.0.0" } }
   ]
}
```

### 2.2 Content census (namespace of each key)

Table 1 — 893 documents, **the units dictionary** (versions 1.0.0 ×230 /
1.0.1 ×649 / 1.0.2 ×12 / 1.0.3 ×2): `autodesk.unit.symbol` 433 (unit symbol
display defs — prefix/suffix text, e.g. `1:`), `autodesk.unit.unit` 350
(meters, yards, footcandles …), `autodesk.unit.quantity` 76, prefixes 20
(`atto`…), `autodesk.unit.dimension` 7, `autodesk.unit.factor` 7. Values carry
`inherits` (893/893), `constants` (886), `annotation.description` (341).
JSON text ≈ 360 K chars.

Table 2 — 422 documents, **specs (measurable data types) + parameter
groups** (versions 1.0.0 ×263 / 2.0.0 ×149 / 1.0.1 / 2.0.1 / 2.0.2):
`autodesk.spec.aec.structural` 92, `autodesk.revit.group` 75 (Revit's
built-in parameter-group ids), `autodesk.spec.aec.hvac` 64,
`autodesk.parameter.group` 50, `autodesk.spec.aec.electrical` 45,
`autodesk.spec.aec.piping` 33, `autodesk.spec.aec` 28, `.energy` 21,
`autodesk.spec.discipline` 7, `.infrastructure` 3, `autodesk.spec.measurable`
3, `autodesk.range` 1. Exactly ONE value carries `"schemaSpecification":
"forge-data-schema-2.0.0", "sealed": true` (the audit's grep hit) — the
schema-language marker, not a licence.

### 2.3 Identity — the (a)/(b) question, answered

Both table bodies hash identically in all six samples (`--identity`); only
table 1's `ownerElementId` differs. There is no per-project subsetting: a
residence (rstbasic), an MEP building (rme) and a German worksharing project
(dach) carry the same 1,315 documents byte-for-byte. **⇒ product data (a).**
A genesis document may therefore carry EXACTLY these bytes and still not
"copy the sample project": the bytes are Revit's, present in every file the
product writes — but they are Revit's (see 2.4), so this is a counsel item, not
a licence-free constant.

### 2.4 Origin and regenerability — the (c) question

Established from public sources this session:

* Revit installs a separate MSI component, **Autodesk Revit Unit Schemas**
  (`RevitUnitSchemas.msi`), to `C:\Program Files\Common Files\Autodesk
  Shared\Revit Schemas <year> Release`; Autodesk's help article "Missing
  schema folder" states the folder "contains files related to the processing
  of units" and must be present with valid files for Revit to start (repair /
  reinstall / re-run the MSI / copy from a working install are the sanctioned
  fixes). The in-file corpus is the serialized image of that installed set.
* The typeid namespaces are the public Revit API `ForgeTypeId` families
  (`UnitTypeId`, `SymbolTypeId`, `SpecTypeId`, `GroupTypeId`, `DisciplineTypeId`;
  documented on the Revit API reference and "What's New in the Revit 2021 API")
  — so the IDENTIFIER SET is public and enumerable.
* Autodesk operates a public **Schema Repository Portal** (`schema.autodesk.com`,
  a login-gated single-page app); no anonymous JSON endpoint answered, and no
  repository under github.com/autodesk-forge (or elsewhere on GitHub) publishes
  the unit/spec schema documents. There is no `forge-data-schema` open-source
  repo carrying an Apache-2.0 grant for this corpus. **(c) as stated —
  "regenerate from Autodesk's public forge-data-schema repo" — is not
  available.**
* No licence, copyright or terms text appears inside any of the 1,315
  documents.

Practical options for genesis (for counsel, not decided here): (i) emit the
canonical bytes every Revit file already carries (the `Formats/Latest`
argument: product-constant, byte-identical corpus-wide); (ii) at generation
time READ the corpus from the customer's own licensed Revit install (the
`Revit Schemas <year> Release` folder → serialize; result is byte-identical
and never redistributed by us); (iii) test whether a file with an EMPTY units
registry (`count = 0`) opens — unmeasurable without the ADocument encoder and
a viewer probe; noted as the experiment that would retire the question.

### 2.5 The gap between the tables = the Extensible-Storage schema list

`u32 count` + `count` GUID-keyed entries (each: GUID(16), then AStrings such
as the schema name / vendor 'Identity', version records): racbasic **0**
(`00 00 00 00`), rstbasic 2, rme 2, dach **175** (84 KB). This is the
document's registry of Extensible-Storage schema definitions (the runtime ES
schemas KNOWLEDGE's object decoder is missing for `ESEntity.m_blob`). It is
**project-specific** (grows with the add-ins that stored data) — the one
project-varying structure sandwiched inside the product-constant corpus.

---

## 3. String tables — project vs product

Method: every AString outside the head structures and JSON tables is scanned,
clustered by proximity, and each string labelled by a small lexicon
(`classify_string`). Cluster inventory (rstbasic, the G0 lineage):

| cluster (offset) | strings | verdict | purpose |
|---|---|---|---|
| 0x53 | 7 build strings | PRODUCT | `m_storedByRevitBuild` (Revit release lineage 2018→2026) |
| 0x37d… | "Autodesk Revit" ×52 | PRODUCT | ExServicesUsed vendor strings |
| 0x1bfb… | `NobleDocWarnings`, `ColorFillSecondaryData`/'Color Fills'/'Color Fill' ×~119 sets, scheme names 'Rooms : Name' / 'Areas : Gross Building Area' / 'HVAC Zones : Schema 1' / 'Pipes : Pipe Color Fill' / 'Spaces : Schema 1' … | class names PRODUCT; **scheme names PROJECT** | the colour-fill analysis cache — one entry per (view, scheme); the scheme names are user-editable definitions |
| 0xc9d2… | 'Elevation 1', 'S206', 'FOUNDATION-2700', 'Section 1', '101', 'L1 wall frame hall 5' | **PROJECT** | view / sheet / assembly names (the sample's browser index) |
| 0x21e2a… | '3D Views', 'Detail Views (Detail)', 'Elevations (Building Elevation)', 'Structural Plans', 'Renderings' … | product defaults (user-renamable) | `BrowserOrganization` folder titles |
| 0x22f0a…0x26a1a | 'WireSizes.xml', 'Size'/'Space Name'/'Space Number'/'Number of Circuits'/'Apparent Power' …, 'AREXRevitStart', 'Element-Watching-Internal-Updater'/'ObjectNumberingUpdater'/'TextNoteUpdater' pairs, user 'liqi' | PRODUCT except the **user name (PROJECT)** | MEP naming schema tokens; the DMU updater registry; the last-edit user |
| 0xe9288 | 'Identity'/'TCHAR'/'AREXContentGenerator'/'AnalysisId'/'ResultsInvalid'/'DaylightingAnalysisInfo'/'ADSK' | PRODUCT | an ES schema descriptor (Insight daylighting) — vendor 'ADSK' |
| 0x16c729…0x16e33d (post-corpus tail) | 'Stairs System', 'Rebar Numbering'/'Fabric Sheets Numbering'/'Rebar Couplers Numbering', 'http://www.autodesk.com'/'Revit Default DB Server'/'ADSK', (`RbsSystem`, `RbsWireCurve`/`RbsPipeCurve`/`RbsDuctCurve`/`FamilyInstance`/`PanelScheduleView`) pairs, (`RevisionSettings`, `DBViewDrafting`) pairs, user 'macalis' | PRODUCT (+1 user PROJECT) | numbering-partition names; keynote/assembly DB server descriptor; MEP system-class registry; revision settings ↔ view class |
| 0x16e56d… | `LB_Associations` + 103 rows `NNNNNNN.1.EEEEEEE` → `{"Id":k,"LocalId":"…","ExternalId":"…"}`, then `LB_MetaData`/`LB_Version`/`LB_References` + `{"Id":1,"ProjectId":"","LineageId":""…}` | **PROJECT** (keys are the sample's element ids) | the linked-model / cloud-reconcile map — each row binds a sample LocalId to an ExternalId; MUST NOT survive genesis (it names 103 sample ids) |
| 0x176ecc… | 'Bathroom','Bathroom 1','Bathroom 2','Bedroom 1','Bedroom 2','Ensuite','Hall','Kitchen & Dining','Laundry','Living','Master Bedroom','Room','Space' | **PROJECT** | the room/space NAME index (rstbasic = a residence) |
| 0x177e1a… | 'Less than 40 m²','40 m² - 80 m²' … '360 m² or more' | **PROJECT** | the sample's area colour-scheme range labels |
| 0x179e0f… | 'Unassigned' ×N, 'Generic', '250 MPa', 'Concrete 10 MPa' | PRODUCT ('Unassigned','Generic') / **PROJECT** (the two structural material names) | analytical material assignments |

racbasic differs only in its project strings (its own rooms 'Bath', 'Entry
Hall', 'Linen', 'Master Bath', 'Mech.'; sheets 'A001'/'106B'/'208'; user
'liqi'; browser folders incl. 'Sections (Wall Section)'). rme adds thousands
of MEP secondary-data entries (system names 'Mechanical Supply Air 6',
'Domestic Hot Water 1', 'Hydronic Supply' — PROJECT system names; scheme names
'Ducts : Duct Color Fill - Flow' — PROJECT) around PRODUCT class strings
('MEPNetworkSecondaryData', 'Network Calculation', 'PipingSystemVolumeSecondaryData').

**Rule for genesis:** everything in the PROJECT column is sample authorship
(room/space/scheme/view/sheet/assembly/material/system names, the `LB_*`
reconcile rows, the usernames) and cannot ride into a genesis file; the
PRODUCT column is what any blank Revit 2026 document also serializes. The
per-cluster verdicts are machine-checkable in each `map_<sample>.json`
(`product / project / ambiguous` counts on every `string-table` region).

---

## 4. ElementId-reference registries — and G0's 6,405 dangling ids

Method: every 8-byte little-endian value equal to an id in the file's own
`Global/ElemTable` (id ≥ 100; the sub-100 built-in ids collide with counts and
are only trusted inside a cluster) → clustered (gap ≤ 64 B), periodic runs of
small clusters merged, each cluster classified by dominant stride. Counts:
racbasic 6,778 hits / 5,059 distinct; rstbasic 10,002 / 6,405; racadv 9,751 /
5,900; rstadv 9,583 / 6,657; rme 59,485 / 12,785; dach 45,458 / 20,939.

G0 (`--dangling`): `Global/Latest` byte-identical to rstbasic's; G0's
ElemTable = 205 ids (1,500,000–1,500,204); references to OUR ids in Latest =
**0**; references to rstbasic ids = **10,002 hits / 6,405 distinct — all
dangling.** By registry kind (class attribution via the rstbasic partitions,
`Document.class_of`):

| registry (rstbasic offset) | kind | ids | what it is |
|---|---|--:|---|
| 0x0d0e8–0x152ac, 20-byte records `{i64 BuiltInCategory (negative OST_ value), i64 elementId}` (+ occasional u32) | **id-map** | 1,785 (GStyleElem 1,169 / CategoryElem 691) | the **BuiltInCategory → category/graphic-style table** — product-enum keys, project element-id values |
| 0x16544–0x1a1e4, 20-byte `{u32 n, i64 catId, i64 styleId}` | **id-map** | 1,393 (777 GStyleElem / 776 CategoryElem) | the **category ↔ its GStyle** pair table (object-styles catalogue) |
| 0x1e13a–0x21e1e, stride 24 | **id-map** | 775 (ParamElemExternal 466 / ParamBinding 209 / BrowserOrganization 15 …) | the **shared/project parameter → binding registry** |
| 0x17c973–0x17df03 (stride 16) + 0x1ada8–0x1b9dc (stride 8) + 0x17e29b… | id-map / id-array | ~800 (RebarInSystem 448 / Rebar 244 / RebarBarType 74 / RebarHookType / RebarShape) | the **reinforcement numbering registries** ('Rebar Numbering' partitions: element ↔ number) |
| 0x2481f–0x25a03, stride 8 | **id-array** | 512 (FamilyInstance 432 / LineLoad 70 / AreaLoad 10 / SWall 9 …) | a per-class **element-id index** (all placed instances / loads) |
| 0x16c755–0x16d8a9 (+ 0x1a234) stride 8/16 | id-array | 380 (ConceptualConstructionType 36, RbsFluidType 28, RbsWireInsulationType 26, DBViewType 19, TilePatternType 17, DivisionRule 17, RebarShape, RbsPipeScheduleType …) | the **type / default-type registry** (per-class default and system types) |
| 0x1c0bc stride 8 | id-array | 213 (HVACLoadSpaceType 125 / BuildingType 33 / schedules 27+27) | MEP energy-settings catalogue index |
| 0x1d870 (LinePatternElem 137 + rooms), 0x1d4cc (MaterialElem 88), 0xcc78 (FillPatternElem 109 + PostedWarning 22), 0x263f6 (AppearanceAssetElem 142), 0x9f93 (SunAndShadowSettings 90), 0x9c53 (all DBView* 87), 0x1d0fc (DPart/Room/Grid/Level 91), 0x1bb48 (load classifications 152) | **id-arrays** (`u32 count + n×i64`) | per-class element-id index arrays: patterns, materials, appearance assets, sun settings, the view list, datums, electrical load classifications |
| 0x220e6, stride 20/24 | id-map | 84 (LinearDimString 40 / CurveElem 36 / SketchPlane 28 / VarSketch 20 …) | sketch/constraint bookkeeping |
| scattered singletons | object-graph | 143 | colour-fill entries (2 ids each), settings pointers |

Totals for G0: id-maps 4,167 distinct ids, id-arrays 2,724, scattered 143.
**Nothing here is a deletion graveyard or a "safe to leave dangling" list**:
these are the ADocument's LIVE indexes — the category catalogue, the
per-class element index, the parameter-binding registry, the numbering
state, the view list. G0's own 205 elements appear in NONE of them (our
skeleton is invisible to the document object), and 6,405 sample ids are
enumerated as if alive. Answer to the audit's question ("what KIND of
registry"): **the id-to-object element index and the category / parameter /
numbering registries — the tables an editor loads at open time.** This is the
strongest available prediction that G0 will NOT open, and it fixes what the
ADocument encoder must own: not "drop 6,175 dead pointers" but "regenerate
the element index over our 205 ids and the category catalogue over our
categories".

---

## 5. Unknowns / residue

1. **dach (51.9 % classified):** ~2.3 MB in a dozen 50–320 KB high-entropy
   regions (0x25eb1, 0x7ccc7, 0x123ffe, 0x18dba1 …) with no strings and no
   stride-aligned ids — consistent with Extensible-Storage entity payloads /
   worksharing element-version tables of this workshared file. Not framed;
   the other five samples classify ≥ 96.9 %. Whether these blobs must be
   understood before writing a NON-workshared genesis file: probably not
   (they are absent from all five non-workshared samples).
2. The `u32 0xf1` constant and the u32-keyed manager registry semantics
   (172 entries) — inherited from wave 1, still unresolved; carries no ids.
3. The ES-schema list grammar (§2.5) is framed only to entry count + GUID +
   name strings; a full decoder belongs with the `ESEntity.m_blob` work.
4. Whether Revit accepts an ADocument whose units registry is empty or
   whose element indexes are empty — untestable without the ADocument
   encoder + a viewer probe (§2.4 option iii; §4 last paragraph).
5. `classify_string` is a lexicon, not a proof: `ambiguous` counts remain
   in every map (2–40 per file, all short tokens); the PROJECT/PRODUCT
   determination above rests on the clusters, not on every string.

## 6. Reproduce

```
.venv/bin/python tools/latest_map.py racbasicsampleproject   # printable map
.venv/bin/python tools/latest_map.py --all                   # writes experiments/genesis/latest/map_<sample>.json
.venv/bin/python tools/latest_map.py --identity              # JSON corpus byte-identity across the six
.venv/bin/python tools/latest_map.py --dangling              # G0 dangling-id registry study (JSON)
.venv/bin/python -m pytest tests/test_latest_map.py -q       # 8 tests
```
