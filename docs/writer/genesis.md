# GENESIS — synthesizing a valid `.rvt` from nothing

Research plan for the pure-independence proof: a Revit 2026 project file
produced by our writer with **no Autodesk sample as input and no
Autodesk-authored content we don't own**. Companion evidence record:
`docs/inbox/genesis.md`. Reduction engine: `src/rvt/reduce.py`, staged
driver `tools/rvt_reduce.py`, staged outputs `experiments/genesis/R*.rvt`.

Status of this document: **research** (2026-08-03). The reduction ladder is
built and self-validated; the Autodesk-viewer results that decide the
practical minimal document are pending (orchestrator runs them).

---

## 1. Method: reduce to the seed, then synthesize the seed

Genesis is attacked from two ends that meet in the middle:

1. **Reduction (done, tonight).** Take the smallest sample
   (`rstbasicsampleproject.rvt`, 6.7 MB, 13,936 host elements) and DELETE
   content in dependency-safe stages with the new deletion writer, re-emit,
   and viewer-test. The deepest reduction the Autodesk reader still accepts
   is the **practical minimal document** and the immediate GENESIS SEED for
   product work (everything a user models sits on top of it).
2. **Synthesis (planned).** Replace each remaining piece of the seed with
   bytes we generate ourselves: first the streams we can already encode,
   then the two hard object graphs (`Global/Latest`, `Global/ContentDocuments`),
   finally the ~2,800 mandatory settings/style/category elements. When the
   last copied byte is replaced by an encoder call, the file is synthesized
   from nothing.

The reduction stage is not busywork: it (a) proves the DELETE half of the
document-mutation API (create was proven earlier), (b) empirically measures
which references the reader actually validates, and (c) produces the
seed whose byte-diff against a synthesized attempt localizes every failure.

## 2. The deletion writer (`src/rvt/reduce.py`) — how a delete is emitted

Deleting element `E` from the host document (save unit 0):

| step | stream | operation |
|---|---|---|
| 1 | `Partitions/<N>` | drop E's seq-101 / seq-102 / seq-103 records; RE-BLOCK unit 0 (below); patch header `elem_table_count` (u32 @ +14) |
| 2 | `Global/ElemTable` | drop E's 40-byte `ElemRec` (count −1); id watermark `IdentifierSource.m_last` NOT lowered (Revit never reuses ids) |
| 3 | both | re-frame with real CRCIO ECC (`ecc.frame_stream`), rebuild the CFB container |
| — | `Global/Latest`, `ContentDocuments`, `History`, `DocumentIncrementTable`, `BasicFileInfo`, `Contents`, embedded units 1..k | copied VERBATIM (the "minimal commit" convention already proven by the element-creation path) |

**Re-blocking algorithm — now fully characterized and reproduced
byte-for-byte.** Autodesk's writer packs each per-seq record stream into
gzip blocks by: greedily appending whole records while the uncompressed
payload stays ≤ 131,072 bytes (flags 4); a record whose framed length
exceeds 131,072 starts a fresh block and is body-chunked at exactly 131,072
bytes (flags 6 first: header + 131,072 body bytes, flags 7 continuation:
131,072 body bytes, flags 5 last: remaining body + the u32 size-repeat).
Counters: `A` = record headers starting in the block, `C` = record body
bytes in the block, `ISIZE == (rawhdr+4)·A + C + adj(flags)` with
`adj = {4:0, 5:+4, 6:−4, 7:0}`, `rawhdr = 12` (seq 101) / `16` (seq 102/103).
**Proof:** `reblock()` applied to rstbasic's own record streams reproduces
all 213 unit-0 blocks (payloads, flags, A, C) IDENTICALLY, including the 4
spanning chains (test `test_identity_delete_reproduces_original_blocking`).
The sentinel record (id −1, psize 0) stays last per seq.

Structural gate (`verify_reduced`): every gzip CRC verifies; both streams'
CRCIO framing round-trips (`frame_stream(unframe_exact(raw)) == raw`);
walker zero errors; ISIZE identity on every block; ElemTable count ==
partition-header count; sentinels last; the three seqs carry identical id
sets; every record stamp == adler32(class‖body); no deleted id survives; no
ElemTable id lacks a record. All eight staged outputs pass it.

## 3. The staged reductions on disk (`experiments/genesis/`)

Two families per stage: **`R<n>` = closure delete** (also deletes every
surviving element that references a deleted one, so the partitions themselves
never dangle — but `Global/Latest`, which we do not yet rewrite, keeps
dangling ids) and **`R<n>s` = safe sweep** (deletes ONLY what leaves zero
dangling references anywhere, including inside `Global/Latest` /
`ContentDocuments`). All are structurally clean. Source = 13,936 elements,
6,672,384 B.

| file | rule | deleted | kept | size (B) | Latest-dangling | probes |
|---|---|---:|---:|---:|---:|---|
| R1s | safe sweep of the model seed | 31 | 13,905 | 6,672,384 | 0 | 30 unreferenced FamilyInstances gone; the "does DELETE work at all" control |
| R2s | safe sweep + views/annotation seed | 762 | 13,174 | 6,533,120 | 0 | detail lines, text notes, tags, legend components — deepest zero-dangling cut |
| R3s | + symbols/families seed | 763 | 13,173 | 6,533,120 | 0 | ~R2s (Latest protects nearly every symbol) |
| R4s | + everything else | 798 | 13,138 | 6,529,024 | 0 | maximal zero-dangling reduction (garbage collection) |
| R1 | model elements + dependency closure | 7,627 | 6,309 | 4,513,792 | 1,281 | all instances/walls/floors/footings/rebar/analytical/loads/rooms + their dimensions/tags/sketches/curves gone; levels, families, symbols, MOST views kept |
| R2 | + all views + annotation + sketches | 8,335 | 5,601 | 3,895,296 | 1,486 | **zero views survive** (the kept plan cascaded via its references) — probes "is at least one view mandatory" |
| R3 | + all symbols/families/attributes | 9,337 | 4,599 | 3,596,288 | 1,901 | project with document tables but no types |
| R4 | + everything not infrastructure | 11,097 | 2,839 | 2,859,008 | 3,576 | the skeleton: styles + categories + levels + phases + design options + geo + project info + settings singletons |

Ordering of viewer risk (prediction): R1s < R2s ≈ R3s ≈ R4s < R1 < R2 < R3 < R4.
The **decisive experiment is whether R1 opens**: if a translated R1 renders,
the reader tolerates dangling ElementIds inside `Global/Latest` (the
serialized `ADocument`), and reduction can go very deep before we ever have
to encode ADocument ourselves. If R1 fails but R2s passes, ADocument's
element-id tables ARE validated and rewriting `Global/Latest` becomes the
critical path (§6). Test order: R1 first, then binary-search the family it
falls in.

## 4. The irreducible core — what a project must contain (mapped, with evidence)

### 4.1 Container / stream layer (mandatory in EVERY .rvt AND .rfa; verified 7/7 files)

| stream | mandatory | can we encode it today? | evidence |
|---|---|---|---|
| CFB container (v4, 4096-B sectors) | yes | **yes** — `cfb_writer.write_cfb`, accepted by the viewer | all samples + the 2026 .rfa |
| `Formats/Latest` | yes (per-release constant) | **copy** — byte-identical in all six projects and the 2026 .rfa (sha256 6459a9a9…); it is Revit's own class map, not user content | KNOWLEDGE §Schema |
| `BasicFileInfo` | yes | **yes** — `stream_encoders.encode_basic_file_info` | present 7/7 |
| `Contents` (DocumentStorageIndex) | yes | **yes** — `encode_contents` (name/GUID/build index, no sizes) | 7/7 |
| `TransmissionData` | yes | trivial (UTF-16 XML, Autodesk documents `Read/WriteTransmissionData`) | 7/7 |
| `Global/History` | yes | **yes** — `encode_history` (episode list; entry[0] == BFI GUID) | invariant list |
| `Global/DocumentIncrementTable` | yes | **yes** — `encode_increment_table` | 7/7 |
| `Global/PartitionTable` (worksets) | yes | **yes** — `encode_partition_table` (one 'Workset1' entry) | 7/7 |
| `Global/ElemTable` | yes | **yes** — `encode_elemtable` (used by every commit and every reduction tonight) | 7/7 |
| `Partitions/<N>` | yes | **yes** — record encoder + `reblock()` + framing (this stream is now fully round-trippable) | 7/7 |
| `Global/Latest` (ADocument) | yes | **NO — only heuristically analysed** (`global_latest.py`). 1.59 MB inflated in rstbasic; holds document-level tables AND arrays of element ids (§4.4) | the hard part |
| `Global/ContentDocuments` | yes | **NO encoder.** In a project it is the array of embedded content-document (family) objects (1.37 MB inflated in rstbasic, 52 docs); in a family file with no nested content it is **82 raw bytes** → the minimal form exists and is tiny | rfa vs project |
| `ProjectInformation` | project files | ZIP of `project.xml` (partatom namespace) — synthesizable | 6/6 projects, absent in rfa |
| `PartAtom` | family files only | Atom XML — synthesizable | rfa only |
| `RevitPreview4.0` | optional | PNG in the Contents wrapper — omit or generate | optional |

So the writer already OWNS every stream except the two object graphs
(`Global/Latest`, `Global/ContentDocuments`). Those two are the entire
remaining distance to genesis at the stream level.

### 4.2 Cross-stream invariants a synthesized file must satisfy (all verified 6/6)

History count == max(ElemRec.modified_ep)+1; newest DocumentIncrementTable
id_pair == (History count−1, History count); BasicFileInfo 'Unique
Document Increments' == central_version_number == DIT record count; BFI
Unique Document GUID == History entry[0]; Contents counters == newest DIT
counters (index 7 removed) and Contents.G == DIT G; partition header count
== ElemTable count; unit-0 seq-102 id set == ElemTable id set; every element
present in all three seqs; sentinel last per seq; CRCIO ECC on every framed
stream; ids unique file-wide (embedded documents are renumbered into the
host id space — a standalone .rfa uses ids 0..7,674, the same families
embedded in rstbasic occupy 1.2 M..1.47 M).

### 4.3 Element layer — the document skeleton (what R4 keeps; a "File > New (no template)" project also carries these)

Layer-cake by dependency (each layer only references layers above it):

| layer | classes (rstbasic count) | why mandatory |
|---|---|---|
| document singletons | ProjectInfo(1), UnitsElem(1), TrueNorth(1), ActiveGeoLocationTrackingElement(1), CoordinateSystemDisplayElem(1), GeoSite(2), GeoLocation(2), BasePoint(2: project base + survey), WorksharingViewModeSettings(2), KeynoteTable(1), DesignOptionSet(1), DesignOption(3), ~120 `UniqueElement`/tracker/settings singletons (AutoJoinTracker, HubsTracker, ElectricalSetting, StructSettingsElem, Rbs*SettingsElem, …) | referenced from ADocument; Revit creates them in every empty project |
| category / style tables | CategoryElem(616), GStyleElem(2183), ModelGraphicsStyle(2), LinePatternElem(150), FillPatternElem(116), MaterialElem(93), AppearanceAssetElem(131), FontElem, PenWidthTable | the category system is product-defined, identical across projects; ADocument references it directly (small ids < 4,096, created first) |
| phases / options / worksets | ProjectPhase(2), AllProjectPhases(1), PhaseFilterElem(7), workset table stream | every element carries phase created/demolished ids; phase filters are default view state |
| datums | Level(≥1; 9 in rstbasic), the levels' DatumPlane/ExtentElem records | model elements are level-relative; ADocument keeps level references |
| parameter tables | ParamElemExternal(466), ParamBinding(209), ParamElemFamily/Project, PropertySetElement/Library | shared/project parameter definitions and their category bindings; heavily referenced by ADocument |
| view infrastructure | DBViewType(91), at least one DBView (**R2/R3/R4 probe whether zero views translate**), SunAndShadowSettings per view, LevelRoomPlan, view templates | the viewer needs a {3D} or plan to render; Revit refuses to open a project with no views |
| type/attribute defaults | TextNoteAttributes, DimensionStyle, LeaderStyle, FilledRegionAttributes, TagNoteAttributes, Wall/Floor/Roof types, MEP curve types | "default type" ids live in ADocument; symbols reference their category + patterns |
| loaded content | Family + FamilySymbol + FamSymSurrogate/FamilySurrogate (host side), one embedded save unit + one ContentDocuments entry per family | see §5 — needed the moment we want to place anything real |

The census that generated this (296 classes, 13,936 host elements) is in
`docs/inbox/genesis.md`; per-stage survivor censuses are in
`experiments/genesis/R*.json`.

### 4.4 The blocker discovered tonight: `Global/Latest` holds element-id arrays

Scanning the inflated ADocument for host ElementIds finds **6,175 of the
13,936 element ids** referenced from `Global/Latest`, in contiguous
8-byte-stride arrays. Concrete examples in rstbasic: a 30-id FamilyInstance
array at inflated offset 117,704 (preceded by u32 count 30) and a **490-id
array at 149,731** containing essentially every placed structural element
(432 instances, 35 line loads, 9 walls, 5 floors, 5 area loads, 4 footings,
count field 0x1ea). ADocument therefore is not just "settings": it indexes
model content (analytical-model / element-set members `[hypothesis]`).
Consequence: NO deep reduction — and no genesis — is dangling-free until we
can decode-and-re-emit ADocument. `ContentDocuments` by contrast references
almost nothing in the host (its objects point at their own save units by
GUID).

## 5. Content strategy — families we own or may redistribute

A GENESIS project starts EMPTY (no loaded families) or with families whose
provenance is clean:

1. **Our own parametric families** — authored by us as `.rfa`-equivalent
   documents. A family document is the SAME document machinery seen tonight
   in the standalone 2026 `.rfa` (12 streams, one `Partitions/<N>` unit 0,
   Global/Latest = the family's ADocument, ContentDocuments = 82 empty
   bytes, `PartAtom` Atom XML). Synthesizing a family is the same problem
   as synthesizing a project, minus the model content — an EASIER genesis
   milestone, and the recommended FIRST synthesis target.
2. **Manufacturer-published families** (Eaton / Schneider-Square D /
   lighting vendors publish `.rfa` for exactly this use). Their license
   normally permits use in project models; that is content we may load,
   unlike Autodesk's sample-project content. Verify each vendor's terms;
   record the source URL + license in a manifest we ship with generated
   files.
3. **Never** Autodesk sample-project content in the shipped seed. Note the
   distinction: `Formats/Latest` (the class map) and the category/style
   tables are FORMAT constants Revit generates in every file — reproducing
   them is interoperability, not copying creative content; sample geometry,
   sample families and sample views are content and must go (that is exactly
   what R1..R4 strip). `[open — legal review]`

**Loading an external `.rfa` into our synthesized project — feasible via
the document machinery already mapped, with three steps not yet built:**

| step | mechanism | state |
|---|---|---|
| a. import the family's element records as a new embedded save unit (28-byte separator: 0x3a3 / 0x3a2 / counter / document GUID; unit footer) | reuse `reblock` + unit framing from `reduce.py` | framing understood, appender not written |
| b. **renumber** every ElementId in the family's records into fresh host id space (family ids 0..7,674 would collide; Revit itself renumbers — the embedded families in rstbasic occupy 1.2 M–1.47 M) | needs `encode.py` re-encode of every id-bearing field (the codebook flattens ElementId to i64, so the remap is mechanical) | not built |
| c. append the family's ContentDocuments entry (its ADocument-equivalent) keyed by the document GUID | needs a ContentDocuments encoder | **not built — same class of problem as Global/Latest** |
| d. create host-side `Family` + `FamilySymbol` (+ surrogate) elements pointing at the content document, then instances via the proven `add_family_instance` | element-creation path (proven) | schema known, wiring not written |

## 6. The plan (ordered), with the hard parts stated plainly

1. **Viewer-test the ladder** (orchestrator): R1s, R2s, R1, R2, R3, R4 (plus
   R3s/R4s if R2s passes). Record the deepest pass = SEED-0. *If even R1s
   fails, our re-blocked emission itself is at fault (all 213 unit-0 blocks
   are rewritten even when payloads are identical) — diff R0_identity vs
   source first.*
2. **Element-level GC to the true floor.** Whatever passes, iterate the
   safe-sweep with a decoded ADocument reference map (not the heuristic i64
   scan) so protection is exact; measure the real minimum element count.
3. **Encode `Global/Latest` (ADocument, 19 fields, v2662, 1,509-GUID
   trailer + ES-schema table + the id arrays of §4.4).** THE HARD PART:
   ~1.6 MB polymorphic object graph currently only 60–70 % structurally
   mapped by `global_latest.py`. Approach: schema-directed decode (the
   0x1c ADocument class is in `Formats/Latest`; `objects.py` already decodes
   its member classes when they appear as elements) → symmetric encoder →
   round-trip on all six files → then EDIT: remove the id arrays' deleted
   members so R1..R4 become dangling-free. Estimate: the single largest
   remaining engineering task in the project (multi-session).
4. **Encode `Global/ContentDocuments`.** Second hard part; start from the
   82-byte empty form (family file) → project with zero families → project
   with one of OUR families (unlocks §5 step c).
5. **Family genesis first, project genesis second.** A minimal `.rfa`
   (12 streams, one unit, tiny ADocument, empty ContentDocuments) is the
   smallest thing that exercises every encoder; validate by loading it into
   a REAL Revit family editor / the viewer. Then a minimal `.rvt` = the R4
   skeleton with every stream produced by encoders (the ~2,800 skeleton
   elements are serialized from OUR catalog — a JSON dump of the category
   /style/settings tables regenerated by our encoder, not copied bytes).
6. **Prove independence:** genesis file's every stream produced by an
   encoder call from source-controlled data; no `.rvt`/`.rfa` opened at
   build time; CI check that greps the build for sample-file reads.

Candid risk register:
- ADocument may reference much more than the id arrays found by the i64
  scan (small ids < 4,096, packed structures) — the encoder must be
  schema-exact, not scan-based.
- "At least one view" and "ADocument tolerates dangling ids" are the two
  reader behaviours the ladder decides; both could force ADocument encoding
  before ANY deep seed exists.
- The category/style catalog (2,183 styles, 616 categories) is large but
  DETERMINISTIC (identical across projects for a Revit release + template):
  we regenerate it, we do not author it.
- History/BasicFileInfo/DIT save-invariants are already encodable; keeping
  them consistent while deleting is why the max-episode element is
  protected (`docs/inbox/genesis.md` §gotchas).
