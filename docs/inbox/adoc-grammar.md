# ADOC-GRAMMAR — the ADocument object-graph grammar (Global/Latest) — SOLVED

Stream: **adoc-grammar** (2026-08-03). Territory: `src/rvt/adocument.py`,
`tests/test_adocument.py`, `docs/writer/adocument.md`, this record,
`experiments/genesis/latest/*`. No existing `src/rvt/*.py` module edited.
Full spec: `docs/writer/adocument.md`.

## Verdict

**`Global/Latest` is fully decoded and byte-exactly re-encodable on all six
samples and on G0.** The hypothesis held: it is `u64 5` + `{u16 class 0x1c,
ADocument object graph}` + `u32 0`, serialized by the SAME schema-directed
codec as element records (parent-first fields, one breadth-first FIFO of
deferred pointer bodies). `rvt.objects.ObjectDecoder` decodes it with two
hooks — (a) the archive-pid seed is `{1}` (the DOCUMENT is object #1, so the
first indexed sub-object is pid 2; the element decoder's `{1, 2}` seed made
that token look like a back-reference), (b) a lifted container cap for
dach's 2 MB steel-model `char[]` blob — and `rvt.encode.ObjectEncoder`
re-serializes the decoded tree byte-for-byte with no change at all. There is
no compression, no externalized landmark region, no missing container
class. **The "ADocument encoder — no encoder exists; biggest engineering
block" (TRACKER G1a) is technically closed by the existing codec pair;**
the remaining work is content authorship + acceptance, staged as the A0–A4
proof ladder below.

## Coverage (structured decode per sample)

| sample | payload | structured decode | left over | errors | decode→encode |
|---|--:|--:|---|--:|---|
| racbasic | 1,500,644 | 1,500,640 (100.0000 %) | `u32 0` | 0 | byte-exact |
| rstbasic | 1,586,246 | 1,586,242 | `u32 0` | 0 | byte-exact |
| racadv | 1,645,873 | 1,645,869 | `u32 0` | 0 | byte-exact |
| rstadv | 1,704,781 | 1,704,777 | `u32 0` | 0 | byte-exact |
| rme | 4,655,284 | 4,655,280 | `u32 0` | 0 | byte-exact |
| dach | 4,762,933 | 4,762,929 | `u32 0` | 0 | byte-exact |
| G0.rvt | 1,586,246 | 1,586,242 | `u32 0` | 0 | byte-exact (= rst sample) |

`python -m rvt.adocument --json` reproduces this table and writes
`experiments/genesis/latest/adoc_<sample>.json` (top-level field
summaries: counts + first 5 items, the 241-slot AppInfo table, byte
attribution, id/string censuses).

## Field map (short form — full table in docs/writer/adocument.md §2)

19 fields, schema order. Externalized (null/empty here, body in its own
stream): `m_elemTable` → ElemTable, `m_pHistory` → History,
`m_pPartitionTable` → PartitionTable; `m_appInfoArr` is EMPTY (app-infos hang
off the manager). Inline owned graphs: `m_oContentTable` (GUID-keyed
loaded-content registry — the wave-1 "GUID map"), `m_pAppInfoManager` (the
**fixed 241-slot AppInfo registry** — 227/241 slots the same class in all
six, 168 always populated; slot table `APPINFO_SLOTS` in the module),
`m_pStyleSettings` (9 style-table pointer stubs), `m_pSteelModelInfo`
(steel-model blob), `m_oNobleSecondaryData` (NOBLE analysis caches — the
room-name colour-fill results, 3.0 MB of MEP network data in rme),
`m_oExServicesUsed` (empty). Scalars: `m_ownerFamilyId`/`…GroupId` −1,
`m_devBranchInfo{1, 2662}`, three false bools, empty `m_executedUpgrades`,
`m_storedByRevitBuild` build-string list.

## The audit's questions, answered

* **Which field holds the 6,175 dangling references?** Measured 6,342
  distinct / 9,738 total ElementId refs in G0's ADocument, **all** dangling
  (0 of them in G0's 205-row ElemTable). 99.7 % sit under
  `m_pAppInfoManager` in the per-category/per-kind element REGISTRIES:
  `CategoryTracking` 2,799, `ElementTrackingData` 1,246,
  `StructuralElemSetTracking` 490, `ExternalParamTracking` 467,
  `NumberingAppInfo` 365, `AppInfoSystemFamiliesNames` 364,
  `ParamBindingTracking` 209, `BasedOnTracker` 159 … (+ 14 in ContentTable,
  45 in NOBLE colour fills). These are id INDEXES over the sample's element
  set — for our own document they must be empty or reference only our ids.
* **The Forge unit/spec/parameter JSON corpus (78.5 % of the stream)** =
  `ESSchemaStorage.m_storedForgeSchemas` (893 pairs, 796,204 B) +
  `.m_storedParameterSchemas` (422 pairs, 537,134 B), plain UTF-16LE
  `(typeid, json)` AString pairs — **byte-identical in all six samples**,
  i.e. a Revit-2026 shipped constant like `Formats/Latest`, not sample
  authorship. Also in that class: `m_schemaUsageMap` = the runtime
  Extensible-Storage schema table (GUID → full ESSchema, 175 in dach).
* **The sample's own naming**: room names live in the NOBLE colour-fill
  result caches (`ColorFillSecondaryData.m_colorFillResults[].m_paramStorage`);
  sheet/assembly names ('FOUNDATION-2700', 'L1 wall frame hall 5') in
  `NewItemNumber.m_items[].m_lastItemName`; the user 'liqi' in
  `WorksharingDisplaySettingsTracking.m_userToSettingsMap`; 52 `"Autodesk
  Revit"` author strings in `ContentTable.m_ContentRecSet` — which G0 still
  carries although G0 has NO content documents (**flag for the genesis
  assembler**: G0's ADocument advertises 52 loaded content records over an
  empty ContentDocuments).
* **Wave-1 retirements**: the "LZ-compressed continuation" is FALSE (plain
  AStrings; nothing below the outer gzip is compressed); the "0x644 GUID
  map = external services" is really the ContentTable; the "u32-keyed
  table, u32 0xf1" is the 241-slot AppInfo container (0xf1 = 241).

## Ranked list of undecoded regions

**Empty.** The only bytes outside the structured decode are the constant
trailing `u32 0` (semantics unknown; encoder appends verbatim). Structurally
decoded but semantically opaque: `SteelModelInfo.m_steelModelLatest`
(dach's 2,085,221-byte embedded Advance-Steel model), two steel-connection
`PreviewImagePng` char blobs (dach). Everything else is named fields.

## What ships to the ENCODER / GENESIS streams (ranked backlog)

1. **A-ladder viewer certification** (files on disk; each isolates one
   hypothesis) — orchestrator to submit in order:
   `experiments/genesis/latest/G0_A0.rvt` (control: Latest re-serialized +
   recompressed, payload identical), `G0_A1.rvt` (**authored ADocument**:
   our own `m_storedByRevitBuild` — the G1a gate proof), `G0_A2.rvt` (+
   Forge corpora emptied: 1.59 MB → 252 KB, exhibit-A gone), `G0_A3.rvt` (+
   sample naming scrubbed: numbering names, worksharing user map, NOBLE
   colour-fill caches), `G0_A4.rvt` (+ ContentTable registry emptied). All
   five `tools/rvt_validate.py` **VALID, 0 errors / 0 warnings**, and each
   re-decodes to exactly the tree we authored. A PASS on A2–A4 retires the
   audit's whole §B2/§C-1 exhibit set for Global/Latest.
2. **A5 — tracking-registry purge** (not built): remove the 6,342 dangling
   ids from the ~60 registry AppInfos. Generic rule available now that the
   decode is schema-directed: every value whose schema type is ElementId
   (0x14) inside a container, id ∉ ElemTable → drop the element / map
   entry; then `commit`. Needs a schema-typed tree walk (the flattened i64
   loses the type; walk value+schema in parallel, or teach the decoder to
   tag ElementId leaves — a one-line hook in the subclass).
3. **A6 — the minimal / owned document**: `FIELD_MAP` with our values;
   168 mandatory AppInfo slots present-but-empty vs. `m_pAppInfoManager`
   null; `ESSchemaStorage` per counsel; `ContentTable` mirroring OUR family
   symbols. `test_minimal_authored_document_roundtrip` already proves the
   codec accepts an all-empty tree.
4. Semantics of the trailing `u32 0`, `ESSchemaStorage.m_dirty`,
   `SchemaUsageInfo.m_contentDocsKeys` — low priority, no writing impact
   (all round-trip verbatim).

## Diffs requested of other streams (I edit only my territory)

* **`src/rvt/validate.py` (validation stream)** — add an ADocument layer:
  ```python
  # after the existing global-stream structural checks
  from .adocument import decode_latest, STREAM as LATEST_STREAM, TRAILER
  payload = doc.inflate(LATEST_STREAM, 0)
  adoc = decode_latest(payload)
  if adoc.errors:
      report.error("latest-decode", f"ADocument decode error: {adoc.errors[0]}")
  elif adoc.trailer != TRAILER:
      report.warning("latest-trailer", f"unexpected Latest trailer {adoc.trailer.hex()}")
  else:
      report.info("latest-decode",
                  f"ADocument decoded 100 % ({adoc.coverage['deferred_bodies']} objects)")
  # dangling-reference count (the audit's blind spot):
  dangling = set(adoc.element_ids()) - elemtable_ids
  report.info("latest-refs", f"{len(dangling)} ADocument id-refs not in ElemTable")
  ```
  and swap the `refs_checked` semantics to include these.
* **`src/rvt/provenance.py` (provenance stream)** — the stream ledger the
  audit demands can now be OBJECT-level for Latest, not just byte-level:
  compare `adoc.summary()['appinfo_slots']`, the forge-corpus hashes, the
  registry id-sets and the string census against each baseline; a
  byte-identical Latest is `blocking`, and per-registry overlap gives the
  clone verdict Global/Latest never had.
* **object-decoder / estorage streams** — `ESSchemaStorage.m_schemaUsageMap`
  is the runtime ES schema table (GUID → ESSchema field list); resolve the
  corpus's remaining `ESEntity.m_blob` failures against
  `open_document_object(path).appinfo('ESSchemaStorage')['m_schemaUsageMap']`.
* **genesis-assembler** — G0's inherited ADocument lists 52 loaded-content
  records (`ContentTable.m_ContentRecSet`) although G0 ships zero content
  documents; and `python tools/sync_plugin.py` must be re-run — the plugin
  drift test (`test_plugin_sync`) now also lists `src/rvt/adocument.py`.

## How to use the codec (for the encoder stream)

```python
from rvt.adocument import open_document_object, decode_latest, encode_latest, \
    write_with_latest, transform_build_list, FIELD_MAP, APPINFO_SLOTS
adoc = open_document_object("experiments/genesis/G0.rvt")   # ADocument, 100 %
tree = adoc.value                                            # plain dict
tree = transform_build_list(tree, ["our build string"])     # or any edit
payload = encode_latest(tree)                                # u16 class + object + u32 0
write_with_latest("experiments/genesis/G0.rvt", "out.rvt", payload)  # framed, CFB rebuilt
```

## Verification

* `pytest tests/test_adocument.py -q` → **14 passed** (2.1 s): full
  coverage 6/6, byte-exact round trip, framing constants, slot-table
  constancy, field-map ⇔ schema order, minimal-authored-document round
  trip, transform re-decodability, base decoder untouched.
* Full suite `.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`
  → **494 passed, 1 failed** = the pre-existing `test_plugin_sync`
  (plugin bundle out of sync with source; fix `python tools/sync_plugin.py`,
  outside this territory — flagged by the auditor before me; my new module
  is one more source file it will need to bundle).
* Proof files (`python -m rvt.adocument --proofs`), `tools/rvt_validate.py`
  on each: **VALID (0 errors, 0 warnings)** ×5:
  ```
  experiments/genesis/latest/G0_A0.rvt  380,928 B  Latest payload 1,586,246 (identical to source)
  experiments/genesis/latest/G0_A1.rvt  380,928 B  payload 1,585,552  (authored build list)
  experiments/genesis/latest/G0_A2.rvt  307,200 B  payload   252,212  (+ Forge corpora emptied)
  experiments/genesis/latest/G0_A3.rvt  307,200 B  payload   216,596  (+ sample names scrubbed)
  experiments/genesis/latest/G0_A4.rvt  307,200 B  payload   211,740  (+ content registry emptied)
  ```

## BRANCH STATE

* Not a git repo; nothing branched. Files WRITTEN (all inside my territory):
  `src/rvt/adocument.py` (new), `tests/test_adocument.py` (new),
  `docs/writer/adocument.md` (new), `docs/inbox/adoc-grammar.md` (this),
  `experiments/genesis/latest/adoc_<six samples>.json`,
  `experiments/genesis/latest/G0_A{0..4}.rvt`. No existing module edited;
  `rvt.objects` module globals untouched (asserted by a test).
* DONE per charter: field map (§2 / `FIELD_MAP`), coverage 100 % / 0 error
  on 6+1 files with byte-exact round trip, ranked undecoded-region list
  (empty; two opaque-blob labels), ranked backlog for the encoder stream,
  five validator-clean viewer candidates ordered by what each proves.
* Open for the orchestrator: submit A0–A4 to the viewer; apply the
  validate.py hook and provenance object-ledger diffs; run
  `tools/sync_plugin.py`; retire `docs/streams/03-global-latest.md` §4.8
  ("compressed continuation") and TRACKER's "no encoder exists" line for
  G1a — the codec is `rvt.adocument`.
