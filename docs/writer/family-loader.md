# FAMILY LOADER — inserting our family documents into a project (`rvt.famload`)

Stream: **genesis-loader** (the K4-FAIL branch), 2026-08-03. Companion modules:
`src/rvt/famload.py` (the loader + the four-registry census + the L-proof
ladder), `src/rvt/famgen/heads.py` (our twelve annotation-head families).
Reuses (imports, never edits) the asset-forge factory's L1/L2/L3 machinery
(`rvt.famgen.factory.{parse,assemble,insert}_content_documents`,
`build_family_save_unit`, `splice_save_unit`, `author_embedded_adocument`),
the family skeleton (`rvt.famgen.skeleton.FamilyDoc`), the commit / manipulate
/ ADocument codecs, and the triage stream's removal tools (for L2).

Confidence tags: **[V]** verified byte-for-byte / by machine proof on the
corpus, **[H]** hypothesis / inferred, **[U]** unknown (viewer question).

---

## 0. What "loading a family" means in the file

A loaded family = an **embedded family document** (a complete small Revit
document, its own save unit) **plus** a host-side layer that binds it, and a
document GUID that must appear COHERENTLY in FOUR places.

### 0.1 The four registries (a document GUID lives in four places) [V]

| # | where | what | codec |
|---|---|---|---|
| 1 | `Partitions/<N>` | a new SAVE UNIT: 28-byte separator `{u16 0x3a3, i32 -1, u16 0x3a2, u32 record_count, GUID(16, bytes_le)}` + per-seq segments 101/102/103 (whole records, our gzip, block A/B/C by the corpus identity) + sentinels + 18-byte terminator + 0x0f3f footer + the `Data generated ...` magic; inserted before the stream end record, every existing unit byte-preserved | `factory.build_family_save_unit` + `factory.splice_save_unit` |
| 2 | `Global/ContentDocuments` | one entry `separator + GUID + u32 adoc_len + the embedded ADocument + u32 adoc_len (mirror)`, entries GUID-sorted, 14-byte end record (SOLVED grammar) | `factory.insert_content_document` |
| 3 | `Global/Latest` ADocument `m_oContentTable.m_ContentRecSet` | record `{m_pHostDocument weak 1, m_ContentKey.m_guidKey = GUID, m_author, m_history{m_originalElementId -1, m_creationDate ep, m_lastModificationDate ep, m_lastUserModificationDate -1}, m_EpisodeCounts [{first: {m_id: ep}, second: unit_records}]}` | `famload.register_in_host_adocument` |
| 4 | `Global/Latest` ADocument `AppInfoManager[FamilyMgr].m_arrLoadedFamilyInfo` (AppInfo slot 0) | entry `{m_surrogateId = the FamilySurrogate id, m_familyDocGUIDs [GUID]}` | `famload.register_in_host_adocument` |

`Global/PartitionTable` is the **workset table** (class 0xc80, `Workset1`,
one row on rstbasic) — NOT a per-document index; loading adds **no** row
there [V]. `ElementTrackingData.m_symbols` is appended only when the host
already tracks the family's category (rstbasic tracks NO annotation-head
symbols; the level-head category has no row) [V].

**Coherence rule** (the instrument `famload.four_registry_census`):
`save_units − 1 == ContentDocuments entries == ContentTable records ==
|FamilyMgr document GUIDs|` AND the four GUID sets are equal. rstbasic /
K1 / R9 / G1_candidate (empty) are coherent; the viewer-FAILED R9b / R10b
splices reconciled only registries 1–2 [V]. Every loader output is
coherent by construction and re-checked after writing.

### 0.2 The host-side element layer (annotation flavour) [V]

Decoded from rstbasic's `M_Level Head - Circle1` (host `Family` 1388845,
`FamilySymbol` 1417017, `FamilySurrogate` 1388865, `FamSymSurrogate`
1417014, `ParamElemFamily` twins 1390070/71/73):

| element | key fields | header (flags / view-flags) |
|---|---|---|
| `ParamElemFamily` **twin** (one per family user parameter) | the embedded parameter object with FOUR rewrites: `m_id`, `m_pParamDef.m_paramElemId` → host id; `m_famId` → host Family; `m_typeId` → `revit.local.family:<32-hex session guid><%08x host id>-1.0.0`. `m_designOptionId` **keeps −4** on the host twin | `family_id` = host Family, deletion `[Family, self]` (8202 / −32768) |
| `FamilySurrogate` | `m_elemId` = host Family, `m_name` = family name, `m_categoryId`, `m_previewElemId` −1, `m_guid` = **constant** `e3e052f8-0156-11d5-9301-0000863f27ad` (identical on all 159 rme surrogates + rstbasic), `m_bIsAdaptive` False | deletion `[Family, self]` (10 / **−32640**) |
| host `Family` | our self-Family TRANSFORMED: `m_name` = family name (the embedded self-Family's name is empty), `m_famDocGUID` minted, `m_surrogateId`, `m_path ''`, `m_partType` **−1** (annotation), `m_oFamDoc = FamilyDocument{m_contentDocGUID = GUID, m_big2SmallMap2 = [(host twin → embedded param)…], m_coreIds}`, `m_familyIds` narrowed to the host twins (each keeping its embedded ABSORBED index), `m_pFamilyTypes` = **one leading blank `' '` row** (= current values keyed by the twins; the annotation family's TYPES live as FamilySymbols), one `DBViewInfoForPreview` (viewFamily 107, viewType 6), `FamilyReferenceIdxMgr` (origin planes' absorbed indices → code 10), the empty `FamDimConstrMgr` KEPT, doc-only state (`m_fsdos` / `m_refs` / `m_deletableElements`) emptied | deletion = core ids ∪ twins ∪ {surrogate, self} (10 / −32768) |
| `FamilySymbol` (per type) | `m_symbolInfo{m_name = type name}`, `m_familyId` = host Family, `m_partitionSurrogateId` = its FamSymSurrogate, `m_pParams` = the type's rows keyed by the TWIN ids, `m_hasParamDefValue` 1, `m_active`, `FamilySymbolPatternHelper` cell, empty move-restriction `Matrix{0×3}`, `m_outline`; seq-103 rep = **SerializedDummy** (see §5.2) | `category` = the family category, deletion `[Family, twins…, symbol surrogate, self]`, bbox (2218 / −32768) |
| `FamSymSurrogate` (per symbol) | `m_elemId` = symbol, `m_name` = type name, `m_categoryId`, `m_famSurrogateId` = the FamilySurrogate | deletion `[surrogate, self, symbol]`, regenOnly `[Family]` (10 / −32640) |

`m_big2SmallMap2` maps HOST ids → EMBEDDED ids: in the Autodesk file it covers
the parameter twins AND every family-scoped host child (subcategory
`GStyle`/`Category` rows, fonts, text/tag/leader/filled-region types) AND the
host CORE resources the document references. OUR documents carry NO
subcategories / fonts / styles (the S0 reduction) and reference NO host
catalog rows, so our big2small = twins only and `m_coreIds` = the host's
category-projection `GStyleElem` rows when present (empty on a base without
them) [H — the completeness of core ids is an acceptance question, H4].

### 0.3 Ids [V]

Element ids are unique file-wide and the host `ElemTable`'s
`IdentifierSource.m_last` watermark spans embedded documents (rstbasic
footer 1,472,524 > every embedded document id 1,393,072..1,471,960). The
loader builds each family document in a block ABOVE the host watermark,
allocates that family's host elements ABOVE its document, and lets
`rvt.commit` raise the watermark to the highest host element — which
therefore covers the embedded ids (asserted in `verify_loaded_project`).

---

## 1. The loader pipeline (`famload.load_family_documents`)

```
survey_host        -> watermark, load episode, partition name, category GStyles,
                      usage referrers, the four registries BEFORE
per family: build the FamilyDoc above the watermark (builder(start_id))
            -> LoadPlan (GUID, host ids, twins, absorbed indices, core ids)
            -> author host elements (twins, FamilySurrogate, host Family,
               FamilySymbol(s), FamSymSurrogate(s))
roundtrip gate     -> every host record encodes + decodes back BYTE-EXACT
                      (LoaderError otherwise; nothing is written)
per family: factory.author_embedded_adocument (L3) + build_family_save_unit (L2)
PASS 1  rvt.commit.commit_new_elements: host elements into save-unit 0 +
        ElemTable rows + identity (BasicFileInfo / DIT usernames ours)
PASS 2  splice every save unit (sequential, before the end record);
        insert every ContentDocuments entry (GUID-sorted merge);
        edit the host ADocument (register N ContentTable records +
        N FamilyMgr entries [+ ETD]); re-encode (decodes clean);
        CRCIO-reframe the three touched streams; write
PASS 3  (optional) usage repointing via rvt.manipulate: each referrer's
        usage field := our symbol; our symbol added to (the old one dropped
        from) the referrer's m_parents.m_deletion; records re-encoded
        byte-exact, stamps recomputed
VERIFY  container / ECC / walker / stamps; four_registry_census COHERENT
        and every GUID of ours in all four; ElemTable rows + watermark;
        every host element decodes and the linkage fields chain
        (Family <-> content GUID / surrogate / symbols / twins); the loaded
        family shows up in rvt.families.family_documents; rvt.validate = 0
        errors.  ok = all of the above.
```

`load_family_document` is the one-family front door; `load_family_documents`
loads N families in ONE write (all host elements in one commit, all units in
one splice pass, one ADocument edit). A dry run (`out_rvt=None`) builds and
gates everything without writing.

### 1.1 Usage repointing (the outside references into a family layer) [V]

The ONLY outside references into a project's loadable-family layer are
USAGE fields on attribute / type elements (the K3 finding):
`LevelAttributes / GridAttributes / CalloutTag / ViewportAttributes
.m_familyTagId`, `SectionAttributes.m_sectionHeadFamilyTagId /
.m_sectionTailFamilyTagId`, `InteriorElevAttributes.m_elevationSymbolId`,
`StructSettingsElem.m_bcFixedFamilyId` — each naming a `FamilySymbol` id,
plus that symbol in the referrer's seq-101 `m_parents.m_deletion` [V rstbasic
LevelAttributes 305 → symbol 1417017 in both]. `UsageRepoint(referrer_class,
field, family_key, only_if_set)`: `only_if_set=True` switches an EXISTING head
to ours (L1b / L2); `False` also gives a `−1` field a head (the L3 case on the
constructed base).

---

## 2. Our head-family set (`rvt.famgen.heads`)

The twelve annotation-head families a minimal project's view / datum /
annotation types default to (the set the viewer-FAILED R10b kept), rebuilt as
OURS. Category / parameter facts decoded from rstbasic's own head families
[V]; every value ours; the parameter SET mirrors the Autodesk family each
stands in for.

| key | our name (type) | category | parameters | stands in for (rstbasic) |
|---|---|--:|---|---|
| `section_head_open` | RW Section Head - Open | −2000400 | Radius | M_Section Head - No Arrow (unit 17) |
| `section_head_filled` | RW Section Head - Filled | −2000400 | Radius | M_Section Head - Filled (35) |
| `section_tail_filled` | RW Section Tail - Filled | −2000400 | Width, Height | M_Section Tail - Filled (44) |
| `section_tail_horizontal` | RW Section Tail - Horizontal | −2000400 | Width, Height | M_Section Tail - Filled Horizontal (5) |
| `level_head` | RW Level Head - Circle | −2006020 | Name, Elevation, Radius | M_Level Head - Circle1 (34) |
| `grid_head` | RW Grid Head - Circle | −2006040 | Radius, Name | M_Grid Head - Circle1 (23) |
| `callout_head` | RW Callout Head | −2000538 | Radius | M_Callout Head1 (6) |
| `elevation_body` | RW Elevation Mark Body | −2006045 | Radius | M_Elevation Mark Body_Circle-12mm1 (20) |
| `elevation_pointer_1` | RW Elevation Mark Pointer | −2006045 | Radius | M_Elevation Mark Pointer_Circle-12mm (13) |
| `elevation_pointer_2` | RW Elevation Mark Pointer 2 | −2006045 | Radius | M_Elevation Mark Pointer_Circle-12mm1 (52) |
| `view_title` | RW View Title | −2000515 | Line Length | M_View Title (26) |
| `boundary_condition` | RW Boundary Condition - Fixed | −2005301 | Radius, Width, Length | M_Boundary Condition-Fixed (25) |

Each is a from-scratch `FamilyDoc`: self-Family (the head's OST category,
`m_partType` −1), Reference Level + level type, the two origin reference
planes, the units registry, the 1-plan-view constellation, the parameters +
ONE type — 19–21 elements, every record byte-exact through the encode/decode
round trip, deliverable BOTH as a standalone `.rfa` (family-mode VALID, 0
errors) and as an embeddable document for the loader.

**Autodesk-name assertion:** our names contain no `M_` / `Autodesk` / `Revit`
marks; text parameters (Name / Elevation) are `ParamDefValue` with the string
spec in our skeleton (the sample uses the `ParamDefString` class) — a
documented divergence of our own family, not a copy.

---

## 3. The L-proof ladder (`experiments/genesis/loader/`, `probes.json`)

Ordered by information value; every file self-verified (four registries
coherent, `rvt_validate` VALID 0 errors, ECC / walker / stamps clean).

| probe | base | what it is | reads |
|---|---|---|---|
| **L1a** `L1a_rstbasic_loaded_levelhead.rvt` | rstbasic (PASS) | + our level head LOADED, referenced by nothing | the pure LOADER MECHANISM proof on a passing base |
| **L1b** `L1b_rstbasic_our_heads_active.rvt` | rstbasic (PASS) | + all twelve loaded + every SET head usage field (11 of rstbasic's 43; the 32 already `−1` stay `−1`) switched to OUR symbols | are annotation-skeleton families acceptable ACTIVE heads (the content question) |
| **L3** `L3_G1_candidate_our_heads.rvt` | G1_candidate (FAIL) | + all twelve loaded + its level type's `m_familyTagId` → our level head | **the K4-FAIL FIX CANDIDATE** |
| **L3b** `L3b_G1_candidate_our_heads.rvt` | G1_candidate (FAIL) | + our level head only + the same repoint | the minimal K4-FAIL fix variant |
| **L2** `L2_K1_our_heads.rvt` | K1 (verdict pending) | our twelve loaded + repointed, then the twelve like-category AUTODESK head families (296-element layer + 12 documents) removed COHERENTLY | our heads as substitutes on the full Autodesk skeleton |
| `head_<key>.rfa` ×12 | — | the standalone family form | family-editor acceptance of our annotation-head document |

Reading tree (also in `probes.json:reading_the_results`):

* **L1a FAIL** → loader defect (registry / record shape); everything else moot.
* **L1a PASS & L1b PASS** → our skeleton heads are acceptable ACTIVE heads;
  family-document CONTENT is not required by the reader.
* **L1a PASS & L1b FAIL** → a referenced head needs real content (detail
  geometry / label / view constellation) — the head-CONTENT ladder is the
  next stream and L3 cannot pass with these families.
* **L3 PASS** → embedded family documents were the K4-FAIL fix; the genesis
  base opens with OUR loaded families.
* **L3 FAIL (L1a/L1b PASS)** → family documents alone don't fix the base —
  the residual is the base's other missing skeleton content (K5x / K6
  verdicts); read the card message.
* **L2 FAIL (K1 & L1b PASS)** → the Autodesk head-family REMOVAL took a
  needed family-scoped host row — bisect against L1b.
* A card message DIFFERENT from `Revit-DocumentCorruption` on any file is a
  spotlight.

### 3.1 L2 recipe (all intermediates coherent) [V machine-checked]

1. Load our twelve into K1 + repoint the head usage fields to our symbols
   (`only_if_set`) — the Autodesk heads become unreferenced by any usage field.
2. `_head_family_layer`: the Autodesk head families = host `Family` elements
   whose `m_categoryId` ∈ the seven head categories, minus our own new
   families; the layer = symbols / surrogates / twins / family-scoped children
   by the linking-field fixpoint (12 families, 296 elements on K1).
3. `genesis_triage.neutralise_referrers` (residual host referrers),
   `genesis_triage.remove_documents` (12 units + entries + ContentTable +
   FamilyMgr, 0 residual GUID bytes), `rvt_reduce.maxgc` + `delete_elements`
   (the 296-element layer).  Final registries 53/52/52 coherent, validator 0
   errors.  Tags / spot elevations / view references / the title block /
   curtain families STAY.

---

## 4. Machine proofs of this session

* Loader unit path — every host record encode→decode byte-exact (7 elements
  / 21 records per family; 201/201 records for a 12-family G1 load); every
  embedded ADocument decodes clean + round-trips; every save unit assembles
  and its splice re-walks with identical id sets across seqs 101/102/103.
* Four-registry coherence after every write (rstbasic 53→54, 53→65;
  G1_candidate 1→2, 1→13; K1 53→65→53) + our GUIDs present in all four.
* `rvt_validate` VALID / 0 errors on L1a, L1b, L3, L3b, L2 and all twelve
  `.rfa` (family mode); ECC / gzip-CRC / walker / adler32 stamps clean.
* Usage repointing: 11 fields on rstbasic (L1b; the 32 unset `−1` fields of
  its 43 correctly skipped), 1 on G1_candidate (L3, `only_if_set=False`),
  re-encoded byte-exact with recomputed stamps
  (`rvt.manipulate.verify_manipulated`: 0 CRC / 0 ECC / 0 walker /
  stamps_ok / 0 ISIZE-identity mismatches); each referrer's header deletion
  list carries our symbol.
* `tests/test_famload.py` — 12 tests, 2.3 s (head builders + round-trip;
  embedded-unit contract; `.rfa` emission + family-mode validation; the
  census on the sample + the genesis base; the dry-run plan / gate; a full
  load + repoint into G1_candidate with read-back of the usage field, the
  header deletion, the host Family / symbol linkage; multi-family registry
  motion; `only_if_set` semantics; the below-watermark refusal).

---

## 5. Acceptance questions (what only the viewer / Revit can answer)

### 5.1 H1 — the embedded document's all-null AppInfoManager
Our embedded `ADocument` (`factory.author_embedded_adocument`) carries the
239-slot `AppInfoManager` with EVERY slot null; the specimen embedded head
document populates ~110 family-editor registries. Unchanged from the
asset-forge L3 open question. **[U]**

### 5.2 H2 — the annotation symbol's SerializedDummy rep
The specimen head symbol carries a cached seq-103 `GElement` graphics tree
(the drawn head) plus `m_geomSteps` / `m_pGeomTable` / `m_refFaces` /
`m_tagNoteData` bookkeeping; OURS is a `SerializedDummy` with the
bookkeeping empty — Revit must regenerate the symbol graphics from the family
document (which, for our families, contains no detail geometry). **[U]**

### 5.3 H3 — the head SHAPE / label is absent (the content gap)
Our head documents are annotation SKELETONS: no symbolic `CurveElem`s /
`FilledRegion`s (the head shape) and no `TagNote` label. No stream has
constructors for those (family skeleton = S0-shape; geometry stream =
solids; no label specimen reconstruction). **This is exactly what L1b
measures**: whether a REFERENCED head must carry content or merely be a
coherent loaded document. **[U]**

### 5.4 H4 — core-id / big2small completeness
Our host Families bind only the host's category-projection `GStyleElem` rows
as `m_coreIds` (rstbasic has them for all seven head categories; G1_candidate
has none, so its heads carry `m_coreIds = []` — reported in each probe's
`plans[].notes`), and `m_big2SmallMap2` covers only the parameter twins
(our documents reference no host catalog rows, so there is nothing else to
map). The specimen twins 45+ style / category / font rows. **[U]**

### 5.5 H5 — load episode / author
The ContentTable record's author is `rvt-writer`; the load reuses the
host's current save episode (no new History episode / DIT record is
minted). **[H — the sample's records span three episodes each; a single
current-episode count is the minimal legal form]**

### 5.6 H6 — the host FamilyTypeTable shape
Host `FamilyTypeTable` = one blank `' '` row (the annotation flavour, V on
the specimen); OUR embedded document ALSO carries its single named type in
its own type table (the specimen embedded head document's type table is
EMPTY — the type lives only as the host FamilySymbol). **[H]**

---

## 6. Unknowns / not built

1. **The head content ladder** — detail-geometry (`CurveElem` symbolic
   lines / arcs in the family plan view, `FilledRegion`s) and label
   (`TagNote` bound to a parameter) constructors do not exist in any stream;
   if L1b FAILS they are the next work (specimens: rstbasic units 34 / 26 /
   17, the smallest heads).
2. **Loading a family from an `.rfa` path** — `load_family_document` takes
   our `FamilyDoc` objects / builders (constructed families), NOT an
   arbitrary `.rfa` file to be decoded into a `FamilyDoc` (a decode-to-builder
   route no stream has). The brief's `family_doc_or_rfa_path` signature is
   met for the `FamilyDoc` half only.
3. **Placed instances** — annotation heads are referenced by usage fields,
   never placed; the loader authors NO `FamilyInstance` (the asset-forge
   `rvt.famgen.loader` covers placement for component families).
4. **Family-scoped host children** — the Autodesk host carries subcategory
   rows / fonts / attribute types per loaded head (its documents reference
   them); ours creates none because our documents reference none. If the
   reader wants a head family's subcategory rows regardless, that is a new
   host-side authoring rung (specimen: rstbasic 1388846..1388864).
5. **`ElementTrackingData` for annotation categories** — appended only into
   an EXISTING category row; whether a NEW row is required is unmeasured
   (rstbasic tracks none of the head categories).
6. **The L2 "21 families" reading** — the charter's 21 = R10b's kept set
   (12 heads + title block + curtains); L2 replaces the twelve LIKE-CATEGORY
   heads and keeps tags / title block / curtains (each a separate probe if a
   verdict points at them).

---

## 7. Reproduce

```
.venv/bin/python -m rvt.famgen.heads                 # the twelve standalone .rfa
.venv/bin/python -m rvt.famload --proofs            # rfas + L1a/L1b/L3/L3b/L2 + probes.json (~3 min)
.venv/bin/python -m rvt.famload --host <rvt> --out <rvt> --families all   # ad-hoc load
.venv/bin/python -m rvt.famload --census <file>     # the four-registry census
.venv/bin/python -m pytest tests/test_famload.py -q # 12 tests
```
