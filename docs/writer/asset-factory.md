# Asset factory — job spec → facts → geometry → skeleton → `.rfa` (and the loader)

Stream: **asset-forge** (2026-08-03). Code: `src/rvt/famgen/factory.py`
(the composition layer over the three foundry modules) + `src/rvt/famgen/loader.py`
(the project-side loader, L4/L5), CLI
`tools/make_family.py`, tests `tests/test_famgen_factory.py` (24 pass) + `tests/test_famgen_loader.py` (13 pass),
proofs in `experiments/families/factory/` (three standalone `.rfa` + three loaded `.rvt` + JSON
reports). Record: `docs/inbox/asset-forge.md`.
Foundations (READ THEM): `family-skeleton.md` (the `FamilyDoc` builder),
`family-geometry.md` (the form generators), `facts-store.md` (the
catalog), `family-authoring.md` (what a family document / `.rfa` is), and
THE RULE — `docs/product/content-strategy.md`.

Product sentence served: *"build me an Eaton panel with X and Y and a room
rated for 250 V"* — the platform must CREATE the family (the asset), not
place a library symbol. This document is the pipeline that does it, its
inputs, and its honest limits.

Confidence tags: **[V]** verified by code on the corpus / by round trip,
**[H]** hypothesis awaiting the Revit / viewer acceptance gate,
**[D]** design decision, **[GAP]** deliberately not built.

---

## 0. What the factory is

```
JOB SPEC ──► FACTS ──► FAMILY DOCUMENT ──► GEOMETRY ──► CONNECTORS ──► .rfa
(mains 400 A, (catalog:    (skeleton: self-      (box at the  (on a real     verify +
 42 sp,        20 W ×      Family, Ref.        TRUE dims,   solid FACE,   validate 0
 480Y/277,     5.75 D,     Level, planes,      six-face     tag + edge    errors +
 MCB, surface) height 60,  plan view, params   solid or     tags, voltage provenance
               each value  = the tagging-      dummy rep)   / poles /     ledger
               tagged fact contract NAMES,                 load bound
               | assumed)  facts as VALUES)                 to a param)
                                                                     │
       LOAD (rvt.famgen.loader)  ◄────────────────────────────────────┘
       our document ─► embedded save unit + ContentDocuments entry (L1-L3)
                    ─► HOST elements: param twins, Family, FamilySymbol(+solid),
                       surrogates, one placed FamilyInstance (L4)
                    ─► host ADocument registrations (L5)  ─►  project.rvt
                       (validate 0 errors)
```

* **facts** — `rvt.famgen.catalog`: dimensions / ratings read from published
  documents, per-field `fact` | `assumed`, source URLs, `require()` never
  fabricates. The factory adds a per-family **fact sheet**
  (`FactSheet`, values tagged `fact` / `assumed` / `derived` / `given` /
  `ours`) and refuses jobs it cannot honestly build (`FactoryError`).
* **document** — `rvt.famgen.skeleton.FamilyDoc`: the from-scratch family
  document (self-Family with the type table, Reference Level, origin
  reference planes, units, the plan-view constellation, `ParamElemFamily`
  parameters). The factory picks the category / part type / work-plane
  flag and writes the facts as **type parameter VALUES**.
* **geometry** — `rvt.famgen.geometry`: the enclosure as a rectangular
  extrusion (`SketchPlane` + `VarSketch` + 4 `CurveElem` + `ExtrusionElem`
  with the authored six-face B-rep solid, or a `SerializedDummy` rep).
  `factory.add_box_form(doc, w, d, h, base_z, center)` composes the bundle
  INTO the document before finalisation, so the self-Family owns and
  indexes the form like any element **[V — the composed document
  round-trips 100 % and validates 0 errors]**.
* **connectors** — `factory.add_connector(doc, host=<form>, face='+y'|'top'|…)`:
  a `ConnectorElem` referenced to a real solid FACE of the form (geometry
  tag + the face's edge-loop tags via `factory.box_face()`), which is what
  every real MEP family does **[V — the generated panelboard's connector
  reproduces the specimen's face tag 2 / edge tags `[3, 4, 8, 17]`
  exactly]**. This retires the S0e probe's datum-plane host.
* **delivery** — `FamilyDoc.to_rfa` (the skeleton stream's proven
  emitter): OUR partition save unit + OUR Global streams + OUR `PartAtom` +
  real CRCIO ECC + OUR container; then `verify` + `validate` (family mode)
  + `provenance_scan`, all recorded in a JSON report beside the file.
* **load** — `rvt.famgen.loader.load_family_into_project`: the same
  document embedded INTO a project (§5): its save unit + ContentDocuments
  entry, the HOST-SIDE elements (parameter twins, the host `Family`, a
  `FamilySymbol` carrying our symbol solid, the surrogates, one placed
  `FamilyInstance`) and the host `ADocument` registrations — the written
  project reads back structurally and validates 0 errors.

---

## 1. The job spec (what a request must say)

A job is a small typed spec; the CLI mirrors it. Missing values that are
catalog facts are RESOLVED (never asked twice); values that are ordering
choices are GIVEN by the user and are surfaced as unverified.

| product | required | resolved from facts | user-given (surfaced) |
|---|---|---|---|
| **panelboard** `make_panelboard(vendor, line, mains_a, spaces, voltage, mcb, mounting, panel_name, sccr_ka, neutral_rating)` | vendor + line (`eaton`/`pow-r-line`, `square-d`/`nq`), voltage (`480Y/277`, `208Y/120`, …), mains (A), spaces | box W / D (facts), box H (circuits→height sizing table), voltage class → member (PRL1X/2X/3X), interrupting-kA default, manufacturer / model as VALUES | MCB/MLO, mounting, panel name, neutral rating, SCCR (if not defaulted), bus = mains |
| **transformer** `make_transformer(kva, vendor, primary_v, secondary_v)` | kVA | frame → W/H/D, weight, temp rise, windings, wall bracket / weathershield kit (facts) | primary / secondary voltage, enclosure |
| **luminaire** `make_luminaire(kind, size, wattage, lumens, cct, voltage, aperture_in)` | kind (`recessed-troffer` \| `downlight`) | troffer housing L/W/H, W, lm, K, CRI (facts); IES **URL** | wattage/lumens/cct overrides, voltage; the downlight housing is **ours** (record housing dims are NULL) |

**Refusals (never a fabricated dimension) [V, tested]:**
* `> 42` spaces on a 20-in Pow-R-Line section → multi-section, not sized
  by the record → `FactoryError` (facts-store finding #2);
* 500 kVA transformer → catalog reads "Contact Eaton" → dims null →
  `FactoryError`;
* an unknown vendor / line / luminaire kind → `FactoryError`;
* a mains rating over the member's maximum, a voltage over the member's
  Vac class → `FactoryError`.

**Assumed values are surfaced, not trusted [D]:** e.g. the 480Y/277
panel's box HEIGHT — the PRL2X sizing table is not on the record, so the
height is borrowed from the SHARED box family's PRL1X table (a fact for
PRL1X, `assumed` for PRL2X), snapped up to PRL2X's own tabulated heights
(facts), and reported in `assumed_fields` in the JSON report. The
generated Description says "generated from catalog facts"; the report says
which ones are not.

---

## 2. The three proof families [V — built, verified, validated, provenance-clean]

Reproduce: `.venv/bin/python -m rvt.famgen.factory` or
`.venv/bin/python tools/make_family.py proofs`. All in
`experiments/families/factory/`, each with `<stem>.json` (fact sheet +
verify + validate + provenance).

| file | what | facts (catalog) | elements | verdict |
|---|---|---|--:|---|
| `eaton_prl_400A_42sp_480Y.rfa` | Eaton Pow-R-Line PRL2X, 480Y/277 V 3φ 4W, 400 A **main-breaker**, 42 circuits, surface | box 20.00 W × 5.75 D (fact), 60 H (assumed: shared-box-family PRL1X table, snapped to PRL2X's tabulated 60 in), interrupting 14 kA (fact range low end → assumed default) | 41 | verify OK · **VALID 0 errors 0 warnings** · provenance OK |
| `xfmr_75kVA_480-208Y120.rfa` | Eaton DT-3 DOE-2016, 75 kVA, 480 Δ → 208Y/120, 3φ, 150 °C rise, aluminum, frame **FR942** | 30.50 W × 43.00 H × 24.00 D in, 570 lb (facts) | 39 | verify OK · **VALID 0 errors** · provenance OK |
| `troffer_2x4_recessed.rfa` | Lithonia BLT 2×4 recessed LED troffer (2BLT4-38W) | 47.75 L × 23.75 W × 2.375 H in, 38 W, 4600 lm, 4000 K, CRI 82, 120–277 V (facts); IES = manufacturer **URL** | 35 | verify OK · **VALID 0 errors** · provenance OK |

What each file contains (all decoded back and asserted in the tests):

* **the tagging-contract parameters by NAME** so a project schedule /
  tag keyed on the revit-bridge shared-parameter names binds:
  `PanelName, Voltage, Phases, Wires, BusRating, MainsType, MainsRating,
  ShortCircuitRatingkA, Mounting, NumberOfCircuits, NeutralRating`
  (panelboard; `usecases/eaton-panelboard/panelboard-shared-parameters.txt`),
  plus `Width/Height/Depth` and the identity built-ins **Manufacturer /
  Model / Description** carrying the manufacturer FACTS as VALUES
  (Manufacturer = `Eaton`, Model = `PRL2X`) — never in the family / type
  NAME (content-strategy §5.4). Values in internal units (V/VA/W ÷ 0.3048²,
  A / K / lm raw, lengths in feet) **[V unit rules]**.
* **the enclosure at TRUE dimensions**: an `ExtrusionElem` whose profile
  and depth ARE the catalog numbers (panelboard 20 × 60 in profile, 5.75 in
  depth — decoded back from the file), carrying our authored six-face
  B-rep solid (`--dummy` swaps in the `SerializedDummy` regeneration
  variant).
* **electrical connectors on a real face**: panelboard = one 3-pole 480 V
  power feed on the enclosure's top face (the specimen convention: feeder
  entry on top), its voltage ASSOCIATED to the `Voltage` parameter
  (`FamilyParametrizedElemParamsCell`, `-1140002`) so the type value drives
  the connector; transformer = **two** connectors on the top face
  (primary 480 V, secondary 208 V — the secondary is what feeds a
  downstream panel per the circuit model, its apparent load bound to the
  kVA parameter); troffer = one single-phase 120 V connector, load = the
  wattage (bound to `Wattage`).
* **our PartAtom** (title = the descriptive family name, our product,
  the type list, no Autodesk taxonomy / OmniClass), **our BasicFileInfo /
  TransmissionData**, our Globals (one save episode; the cross-stream
  invariants hold by construction), empty `ContentDocuments`.

---

## 3. The provenance ledger (`provenance_scan`) [V]

Every emitted file is scanned and the report says, per stream, what is
OURS and what is a carried FORMAT constant:

* **family document strings clean** — every seq-102 object of the
  save unit decodes and its strings are scanned for company / author /
  path leakage (`\bAutodesk\b`, `C:\Users\…`, `OmniClass`, sample family
  names). The Forge parameter VOCABULARY (`autodesk.spec.*`,
  `autodesk.parameter.group.*`, `autodesk.unit.*`, `revit.local.family:*`)
  is whitelisted **and listed** in the report — those identifiers are the
  format's interoperability vocabulary every family parameter carries, not
  content.
* **PartAtom ours** (our product, no Autodesk product label, no OmniClass)
  and **BasicFileInfo ours** (author `rvt-writer`, no Windows user path).
* **carried format constants, named:**
  `Formats/Latest` = the per-release schema — its sha256 is checked
  against the corpus digest (`6459a9a9…`), i.e. **provably the format
  constant, not content**;
  `Global/Latest` = the donor container's serialized `ADocument`, DECODED
  by `rvt.adocument` and characterised: 1,727 references to donor element
  ids of which **0 exist in our file** (dangling registry scaffolding) +
  the Revit-shipped Forge unit/spec corpus — **no family geometry, no
  type table, no parameter definitions, no manufacturer content**. It is
  the one honest carried non-constant, retired by authoring our own
  `ADocument` now that the codec exists (§5, and the adoc stream's ladder).
* the report lists the streams that are wholly OURS (the save unit, the
  six Globals, `Contents`, `BasicFileInfo`, `TransmissionData`, `PartAtom`,
  the container / framing / ECC).

---

## 4. What a job spec needs to say to get a family generated [D]

The whole flow reduces to: **name the equipment class + the ratings; the
factory resolves every dimension it can from facts, marks what it can't,
and refuses what would require inventing.**

```python
from rvt.famgen import factory as F

prod = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400,
                         spaces=42, voltage="480Y/277", mcb=True,
                         mounting="surface")
rep = prod.write("out/panel.rfa")          # -> out/panel.json beside it
assert rep["ok"]                              # verify + validate + provenance
prod.facts.assumed()                          # ['height_in', 'sccr_ka'] -> surface these
prod.summary()                                # element / param / form / connector counts
```

CLI equivalents: `tools/make_family.py panelboard --mains 400 --spaces 42
--voltage 480Y/277 --mcb --mounting surface -o out.rfa`, `transformer
--kva 75 --primary 480 --secondary 208Y/120`, `luminaire --kind
recessed-troffer --size 2x4 --wattage 38 --lumens 4600 --cct 4000`,
`provenance <file.rfa>`, `loader`. Exit codes: 0 = emitted + green;
1 = a check failed; **2 = the factory refused the job** (says what to
source or change).

---

## 5. The loader — putting a generated family INTO a project [BUILT]

Code: `src/rvt/famgen/loader.py` (this session). `project_with_generated_panel.rvt`
now EXISTS: our generated Eaton panelboard, embedded as a family document in
a copy of `rmebasicsampleproject.rvt`, loaded as a host Family + FamilySymbol
+ ONE placed instance — validating **0 errors** (`rvt_validate`, all three
layers). The prior session's L1–L3 (below, unchanged) are composed with the
now-built L4 (host elements) and L5 (host ADocument registrations).

### 5.1 The five host mutations — all built

| step | mutation | status |
|---|---|---|
| **L1** | `Global/ContentDocuments` += an entry keyed by our document GUID | **BUILT [V]** grammar solved (5.2), byte-exact corpus round-trip, sorted insert |
| **L2** | `Partitions/<N>` += our save unit before the stream end record | **BUILT [V]** `build_family_save_unit` + `splice_save_unit`; the re-walk of the WRITTEN file shows 307 units, walker-clean, our unit at index 306 |
| **L3** | the entry's payload = our document's serialized `ADocument` | **BUILT [V], acceptance [H]** `author_embedded_adocument`; decodes clean + round-trips; all-null `AppInfoManager` vs the specimen's 110 populated registries = the open acceptance question |
| **L4** | the HOST-SIDE elements (5.4) | **BUILT [V] this session** — landed by `rvt.commit.commit_new_elements` (save unit 0 + `Global/ElemTable`) |
| **L5** | the host `ADocument` (`Global/Latest`) registrations (5.5) | **BUILT [V] this session** — decode → three appends → re-encode (re-decodes clean) |

### 5.2 `Global/ContentDocuments` — GRAMMAR SOLVED [V] (prior session)

```
logical Global/ContentDocuments =
    u64 1                                             (per-stream prefix)
    entry × k, GUID-sorted (bytes_le order):
        u16 0x3a3, i32 -1, u16 0x3a2, i32 -1         (12 B separator token,
                                                      counter = -1)
        GUID (16, bytes_le)                           = the embedded document's
                                                      content GUID (== its
                                                      partition unit's GUID
                                                      == the host Family's
                                                      m_oFamDoc.m_contentDocGUID)
        u32 adoc_len
        ADocument (u16 0x1c + object)                 (INLINE ElemTable 0x5c9
                                                      + DocumentHistory 0x538)
        u32 adoc_len                                  (MIRROR — 305/305)
    end record: u16 0x3a3, i32 0, i32 -1, u32 0       (14 B)
```

### 5.3 The embedded document object (L3) [V structure, H acceptance]

Unchanged: INLINE `ElemTable` (one `ElemRec` per element) + INLINE empty
`DocumentHistory`, empty `ContentTable`, nine `StyleSettings` stubs,
`m_pHostDocument weak 1` / self weak 2, `m_ownerFamilyId` = the self-Family,
`AppInfoManager` = 239 all-null slots **[H]**. NEW: the embedded documents'
elements are NOT rows of the host `Global/ElemTable` (28,132 rows, all
partition 0 — verified: no `786xxx` embedded id has a host row), so our 41
family elements need only their document's own inline ElemTable; only the 19
HOST elements get host rows.

### 5.4 L4 — the host elements [V, this session]

Everything below is decoded from the specimen (host `Family` 454674
'M_Lighting and Appliance Panelboard - 208V MLO - Surface', its embedded
document unit 243, symbol 455409, instance 471580) and built field-by-field
(the genesis / family-skeleton discipline) — see `docs/inbox/asset-forge.md`
for the evidence trail. Ours = 19 host elements for the flagship panel:

* **14 `ParamElemFamily` TWINS** (one per top-level family user parameter;
  the specimen twins 7/7 of its top-level params — the 3 untwinned belong to
  NESTED annotation families). A twin = OUR parameter object with exactly
  four rewrites **[V diff 455334 vs 786844]**: `m_id` / `m_pParamDef.
  m_paramElemId` → the host id, `m_famId` → the host Family, `m_typeId` →
  `revit.local.family:<32-hex session guid><%08x host id>-1.0.0` (one session
  guid per load — [V] all 7 specimen twins share `e16114b1…` + their own id).
  Header `m_familyId` = the host Family; deletion `[Family, self]`; ElemRec
  owner = the host Family **[V]**.
* **`FamilySurrogate`**: `{m_elemId = host Family, m_name = family name,
  m_categoryId, m_previewElemId = -1, m_guid = e3e052f8-0156-11d5-9301-
  0000863f27ad}`. **[V]** all 159 host surrogates carry that ONE GUID (a
  format-level creator identifier); 56/159 carry `previewElemId -1` (the
  other 103 point at `LegendComponent`s of the sample's legend VIEW — project
  content, not a load requirement).
* **the host `Family`** = OUR self-Family object **transformed**, every rule
  from a field-by-field diff of the specimen host Family against its own
  embedded self-Family (519 differing leaves, grouped): id remap (self →
  host id, every family-parameter id `P_i` → its twin `T_i` in
  `m_familyParams` / the type-table rows / the cells / the locked-param ids);
  `m_name` = the family name (the embedded self-Family's is empty);
  `m_famDocGUID` minted; `m_surrogateId` = our surrogate; `m_oFamDoc` =
  registered `FamilyDocument` (pid 3 — the record's first registered object)
  `{m_contentDocGUID = our GUID, m_big2SmallMap2 = [(T_i, P_i)] sorted by host
  id, m_coreIds}`; `m_familyIds` narrowed to the host twins, each keeping its
  embedded counterpart's ABSORBED INDEX **[V: host 455334→1106 ≡ embedded
  786844→1106; 454678→297 ≡ 786443→297]**; a leading blank ' ' row in the
  type table (= the current values) **[V]**; host-only `m_dbviewInfos`
  (preview view infos), the `ConnectorDataCell` summarizing our connector
  (voltage / poles / apparent load rows, the RESOLVED host load
  classification in the `-1140014` row, the `propId → famParam` bindings —
  `-1140002` voltage → our Voltage twin) **[V shape]**, the
  `FamilyReferenceIdxMgr` (reference INDEX → (Is-Reference code, name) —
  **[V]** the map keys are the origin RefPlanes' ABSORBED indices: specimen
  25/26/27 = its origin planes' `m_familyIds` indices), `m_defaultHeight*` =
  −1e30; family-document-only state dropped (`m_oFamDimConstrMgr`, `m_fsdos`,
  `m_refs`, `m_deletableElements`). Header deletion = built-in param ids +
  core ids + twins + self + surrogate; rep `SerializedDummy`.
* **`FamilySymbol`** (our one type): `m_symbolInfo.m_name` (ours), the type
  parameter row (ours, keyed by the twins), `m_familyId` = the host Family,
  `m_partitionSurrogateId` = its `FamSymSurrogate`, and the **SYMBOL
  GEOMETRY** (what placed instances DISPLAY — an instance's own seq-103 rep
  is only `GInstance → symbolId`): `m_geomSteps` = a `BaseFamilySymbolGStep`
  whose history tables map every SYMBOL-SPACE id back to
  `[kind, tag, form-by-ABSORBED-INDEX]` (5 = face `[5, faceTag, absIdx]`,
  3 = edge `[3, edgeTag, absIdx, -1]`, 65 = the solid node `[65, absIdx,
  -1,-1,-1]`, 6 = graph node), `m_pGeomTable` = one `{generator 1}` per id
  0..N, and the seq-103 `GElement` = OUR authored six-face box solid
  (`rvt.famgen.geometry`) re-tagged into the symbol id space (faces/edges
  carry their symbol ids in `GInfo.m_tag`), wrapped in a `GFilter` under a
  root whose `GInfo.m_categoryId` = the host category GStyle (124 =
  Electrical Equipment projection, resolved by category) and `m_tag` = the
  symbol id **[V grammar from 455409; H the id-space semantics of one
  specimen]**. Header carries the CATEGORY (−2001040) and the geometry bbox.
  The `symbol_solid=False` variant (`project_with_generated_panel_dummy.rvt`)
  emits a `SerializedDummy` symbol rep and no history — the F4b "Revit
  regenerates the symbol from the embedded document" question.
* **`FamSymSurrogate`**: `{m_elemId = the symbol, m_name = type name,
  m_categoryId, m_famSurrogateId = the FamilySurrogate}` **[V shape 455410]**.
* **the placed `FamilyInstance`**: `rvt.mutate`'s proven instance recipe
  (clone the placement SCAFFOLDING of the host's specimen instance of the
  category), pointed at OUR symbol with `symbol == masterSymbol` (the free /
  simple pattern — the specimen face-hosted panels use a per-host SLAVE
  geometry symbol whose master is the named type; ours does not), on the
  specimen's face host (SketchPlane 471504, a wall face) 4 ft along the
  wall, with the connector manager REBUILT for our connectors (never the
  template family's 14 slots) and unconnected. Its seq-103 rep = the
  formulaic `GInstance → symbolId`. **[V shape; H the symbol==master face
  placement]**.

Ids: our document allocates ABOVE the host watermark (888,014+ over
888,013) and the host elements above that (Family 888055, twins
888056–069, surrogate 888070, symbol 888071, sym-surrogate 888072, instance
888073); the ElemTable watermark ends at the max host id **[V]**.

**Second-order proof [V]:** on the LOADED project,
`rvt.mutate.Document.from_file(...).symbols()` lists our symbol (family
888055, category −2001040) and the STANDARD `add_family_instance(symbol_id=
our symbol, …)` now works ON OUR NEW SYMBOL (it clones our placed instance
888073 as its template) — the loader bootstraps the first placement (a
brand-new symbol has no instance to clone); thereafter the certified
mutation API places more.

### 5.5 L5 — the host `ADocument` registrations [V, this session]

A whole-tree search of the host `ADocument` for the specimen family /
symbol / GUIDs found exactly THREE registration sites (nothing else); we
append to all three (`register_in_host_adocument`), and the edited tree
re-encodes and re-decodes clean (`rvt.adocument`):

1. `m_oContentTable.m_ContentRecSet` += `{ContentKey guid = our GUID,
   m_author (ours), history{creation/modification episode = the host's
   current episode}, m_EpisodeCounts [(episode, our unit's record count)]}`;
2. `AppInfoManager[FamilyMgr].m_arrLoadedFamilyInfo` += `{m_surrogateId,
   m_familyDocGUIDs [our GUID]}` — **[V]** a single-GUID entry is the norm
   (47/159); extra GUIDs in an entry are the family's NESTED embedded
   documents (the panel specimen's second GUID is its nested "Section Tail"
   annotation family, flattened into the host's ContentDocuments); ours has
   none;
3. `AppInfoManager[ElementTrackingData]` — the per-category symbol / element
   id sets += our symbol / instance ids (sorted).

### 5.6 The write [V]

Two passes over `rvt.roundtrip.read_entries` + `rvt.cfb_writer.write_cfb`:
**pass 1** = `rvt.commit.commit_new_elements` (the certified machinery: our
19 host elements appended to save-unit 0 before each seq sentinel,
`Global/ElemTable` rows + watermark, identity scrub);
**pass 2** = replace `Global/ContentDocuments` (L1), splice our save unit
into `Partitions/<N>` before the end record (L2/L3), replace `Global/Latest`
(L5) — each re-framed with real CRCIO ECC (`ecc.frame_stream`,
`stream_encoders.wrap_global_stream`). Before any byte is written, every
authored record passes an encode → decode byte-exact round-trip gate
(57/57 records).

### 5.7 What the written file proves back [V]

`verify_loaded_project`: container CRC clean + the validator's structure
layer (real ECC verify of every page) VALID; partition walker clean, 307
units, OUR unit at index 306 with our GUID; `Global/ElemTable` 28,151 rows
(28,132 + 19) with all our host ids, watermark 888,073; the host `ADocument`
decodes clean with our ContentTable record, FamilyMgr entry and symbol
tracking; `rvt.families.family_documents` lists ONE new host Family — ours:
name, category −2001040, unit 306, 41 records, 1 type = our symbol,
`big2small_count` 14, 1 connector, 14 family params; the instance's
`InstanceInfo.m_symbolId` = `m_masterSymbolId` = our symbol on host 471504;
targeted provenance (our unit + our host elements only — the host is the
sample by design) finds ZERO suspects. And `rvt_validate` (structure +
consistency + semantic, 427,623 records / 2.57 M references) = **VALID, 0
errors** — its ONE warning is the untouched sample's own known decoder gap
(1,171 Extensible-Storage instance blobs), byte-identical on the baseline;
the load added **no** findings.

---

## 6. Honest limits (what the factory / loader do NOT do)

| # | limit | why / next |
|---|---|---|
| 1 | no `ImposterLight` light-source element in luminaires | the skeleton stream exposes no constructor; photometrics ride as parameters; needs the light-source stream [GAP] |
| 2 | no `.ies` payload, ever | policy: photometry is referenced by manufacturer URL |
| 3 | curved forms are polygonal in the factory (the downlight can is a 4-gon) | the geometry stream's true cylinder is done (`solid_cylinder_brep`); wiring it into the luminaire is a small follow-up |
| 4 | **N types per family — DONE (#163, `docs/inbox/type-catalogs.md`)**: `make_panelboard/transformer/luminaire(types=[…])` / `make_family.py --types 225,400,600` emit ONE family with one type-table row per catalog selection (per-type dims / ratings / Model as VALUES, per-type `assumed_fields` in the report), `--type-catalog` writes OUR `.txt` beside it, and BOTH loaders author one host FamilySymbol + FamSymSurrogate per real-named row (family-mode + project validators 0 errors; **not** a certification claim). **Still open:** no labelled dimensions / formulas — the ONE enclosure solid + connector sit at the primary (first) type's dimensions; the other rows carry their true dims as parameter values only | label-driven geometry is the geometry stream's recipe §5 (`FamDimConstrMgr` expression tables); until then a placed non-primary type DISPLAYS the primary's box |
| 5 | hosted-family scaffolding (`host='wall'/'ceiling'`) is not built | the generated panel is work-plane-based like the specimen; the LOAD places it face-hosted on the sample's wall SketchPlane |
| 6 | family / type NAMES avoid catalog numbers | content-strategy §5.4 unsettled; manufacturer / model ride as parameter VALUES |
| 7 | the load's ACCEPTANCE (5.8) | verify + validate + provenance are green; opening in Revit is the gate |
| 8 | shared-parameter GUID identity | our parameters carry the contract NAMES (local `revit.local.family` identity); binding a schedule to the firm's shared GUIDs is the tagging contract's route-B sidecar on the PROJECT side |
| 9 | acceptance of every generated `.rfa` / `.rvt` | opening in the Revit family editor / the APS translator is the gate (§7) |
| 10 | panelboard vendors: Eaton (Pow-R-Line) + Square D NQ; NF / I-Line and multi-section panels refuse | no circuits→height table on record — `FactoryError`, never a guess |
| 11 | the symbol carries NO reference faces (`m_refFaces` empty) | placed instances offer no reference snapping / alignment to the family's planes; the specimen carries 14 registered `Face` + `Plane` objects; a follow-up once the load is accepted [GAP] |

### 6.1 The load's acceptance ledger [H] — what only Revit can answer

* **H1** the empty embedded `AppInfoManager` (L3);
* **H2** the symbol geometry bookkeeping — history tables + GeomTable +
  the flat id space, inferred from ONE specimen (the `_dummy` variant leaves
  it to Revit's regeneration: the F4a/F4b triage of the geometry stream);
* **H3** `big2SmallMap2` / `coreIds` completeness for a family document
  that carries no category / object-style copies (ours has none; the
  specimen twins 45 style rows);
* **H4** the surrogate `m_previewElemId = -1`, the shared creator GUID,
  the single-GUID FamilyMgr entry;
* **H5** `symbol == masterSymbol` on a face host (the specimen uses a
  per-host slave geometry symbol) and the rebuilt connector manager;
* **H6** the ContentTable author string is ours; the load reuses the host's
  current save episode (no new History / increment row).

---

## 7. Viewer-certification queue (ordered by information value)

All in `experiments/families/factory/`; the `.rvt` files also carry
`.json` reports beside them (plan, per-record ids, every proof).

1. **`project_with_generated_panel.rvt` — THE LOAD PROOF (this session).**
   The rme sample + OUR generated Eaton 480Y/277 V 400 A MCB 42-circuit
   panelboard loaded (host Family 888055 'Panelboard 480Y/277 400A MCB
   42ckt Surface', symbol 888071 '400A MCB 42ckt') + ONE instance
   (888073) placed on the sample's wall SketchPlane 471504 (~4 ft along
   the wall from the sample's own panel). Expectation: the project opens;
   the Project Browser lists our family under Electrical Equipment; the
   instance shows a 20 × 60 × 5.75 in surface panel; its properties show
   our contract parameters / Manufacturer Eaton / Model PRL2X and a 480 V
   3-pole feed connector. **A pass proves families are generated AND
   loadable/placeable end to end.** On a fail: (a) does the project OPEN
   (host-side records) — compare `project_with_loaded_panel.rvt`; (b) is
   the family LISTED (Family/twins/registrations); (c) does the instance
   DISPLAY (symbol geometry — compare `project_with_generated_panel_
   dummy.rvt`); (d) does the family open in the editor (L3 —
   compare the standalone `eaton_prl_400A_42sp_480Y.rfa`).
2. **`project_with_generated_panel_dummy.rvt`** — identical but the
   symbol geometry is a `SerializedDummy` for Revit to REGENERATE from
   the embedded document (F4b); answers H2 by contrast with #1.
3. **`project_with_loaded_panel.rvt`** — the family LOADED but NOT
   placed (in the browser, no instance); isolates the load from the
   placement / symbol-geometry variables.
4. **`eaton_prl_400A_42sp_480Y.rfa`** — the flagship standalone family
   (Electrical Equipment / panelboard part type; the eleven contract
   parameters + Manufacturer Eaton / Model PRL2X / Description as values;
   20 × 60 × 5.75 in box; 480 V 3-pole `Voltage`-driven connector). Its
   pass triages #1's failure mode (d) and proves the generated FAMILY.
5. **`xfmr_75kVA_480-208Y120.rfa`** — free-standing flavour + two
   connectors (480 V primary / 208 V secondary).
6. **`troffer_2x4_recessed.rfa`** — the Lighting Fixtures category +
   photometric parameters, no light-source element.

---

## 8. Reproduction

```
.venv/bin/python -m rvt.famgen.factory                      # 3 standalone proofs + reports
.venv/bin/python -m rvt.famgen.loader                       # the load ladder (3 .rvt + reports, ~5 min)
.venv/bin/python tools/make_family.py panelboard --mains 400 --spaces 42 \
    --voltage 480Y/277 --mcb --mounting surface -o out.rfa
.venv/bin/python tools/make_family.py load -o out.rvt   [--no-place] [--dummy-symbol]
.venv/bin/python tools/make_family.py provenance out.rfa
.venv/bin/python tools/make_family.py loader              # fast readiness JSON, no project file
.venv/bin/python -m pytest tests/test_famgen_factory.py -q          # 24 passed
.venv/bin/python -m pytest tests/test_famgen_loader.py -q           # 13 passed (one real load, ~2 min)
```
