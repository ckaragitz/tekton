# Y9 PROVENANCE — the honest genesis-progress number, byte-weighted

Stream: **genesis-integrate** (2026-08-04).  Subject: `experiments/genesis/subst_k4/Y9.rvt`
— the deepest rung of the substitution ladder v3 REBASED on the certified base K4
(pure IN-PLACE substitution; **Y9 LOADS**, ORCHESTRATOR VERDICTS #17).  Question:
*what fraction of Y9 is ours?*  Two honest answers exist — one counted in
ELEMENTS (the census: 1,333 / 3,342 landed), one weighed in BYTES.  This document
measures the byte-weighted answer per stream, splits it into four provenance
classes, and reconciles it with the element census so both numbers can be quoted
without either lying.

Instruments (all read-only): `tools/provenance.py` (`rvt.provenance` v2,
`--baseline all --streams`), `rvt.mutate.Document` record diffs Y9 ↔ K4 ↔ rst,
`rvt.adocument`'s byte ledger of `Global/Latest`, `rvt.partitions.StreamWalker`,
the ladder's own rung reports (`experiments/genesis/subst_k4/Y*.json`) and
`Yn.json` (the residue census).  Reproduction §7.

---

## 0. Result in one screen

Y9 = **4,385,733 inflated bytes** in 12 streams (0 embedded family documents — K4 is
the family-free base).  Byte-weighted provenance, four classes:

| # | class | bytes | % of file | what it is |
|---|---|--:|--:|---|
| i   | **OUR constructed element expression** | **275,603** | **6.28 %** | the seq-102 OBJECT records of the 1,276 landed slots whose bytes our constructors changed |
| i'  | our constructor output, byte-identical to Autodesk's | 10,363 | 0.24 % | 57 landed slots where our constructor reproduces the sample's own object (empty trackers / default machinery) — ours by construction, Autodesk's by bytes |
| ii  | **Autodesk-authored element residue** | **1,643,673** | **37.48 %** | all three record streams (seq 101/102/103) of the **2,009** never-substituted elements — the Yn residue |
| iii | **the two product corpora** | **1,830,415** | **41.73 %** | `Formats/Latest` schema 496,597 + the ESSchemaStorage Forge unit/parameter-schema corpus inside `Global/Latest` 1,333,818 (counsel C4-class, per-release product constants) |
| iv  | **format / machinery** | **625,679** | **14.27 %** | non-corpus ADocument registry scaffold 246,256; the landed elements' Autodesk-authored headers/reps (seq 101/103) 215,025; `Global/ElemTable` 133,718; fingerprint/identity streams 30,602; content registry 22 + sentinels 56 |
|     | **total** | **4,385,733** | 100.00 % | ✓ |

Read three ways, all true:

* **6.3 % of Y9's bytes are our constructors' expression** (6.5 % counting the
  57 byte-identical constructor slots).  **41.7 % is Autodesk PRODUCT data**
  (the schema + the Forge unit-schema corpus — byte-identical in EVERY 2026
  file; counsel C4's ship-verbatim question, not sample authorship).  **51.7 %
  is Autodesk sample-authored** (element residue 37.5 % + machinery 14.3 %).
* Excluding the two product corpora (constants that are neither ours nor
  authored expression): of **2,555,318** authored/machinery bytes, ours =
  **10.8 %** (11.2 % with the constructor-identical slots), residue elements
  64.3 %, machinery 24.5 %.
* The element census — **1,333 of 3,342 host elements (39.9 %) landed** — is
  exactly reconciled with the byte measure (§4): landed elements are
  registration-cheap and payload-light (settings singletons, catalog rows,
  palette, datum, views ≈ 215 B/object on average); the 2,009-element residue
  holds the heavy payloads (appearance-asset blobs, 466 shared-parameter
  definitions, the assembly-code table, product data ≈ 649 B/object).  Of
  the host unit's **1,589,300 seq-102 object bytes, 18.0 %** are our
  constructor output (17.3 % byte-changed).

The registry / container layer is entirely the certified base's: `Global/Latest`
and `Global/ElemTable` are **BYTE-IDENTICAL to K4** (the in-place ladder's
zero-registration-motion law, re-verified here), every fingerprint stream is
byte-identical to the rst sample, and the ONLY stream that differs from K4 is
`Partitions/21` — where the 1,276 substituted objects live.  Identity (author,
save path, employee usernames in the increment table) is still the sample's
chain of custody: a solved, separable layer (V30–V32 certified) that this
byte measure deliberately excludes and names in §5.

---

## 1. The instrument run

```
.venv/bin/python tools/provenance.py experiments/genesis/subst_k4/Y9.rvt \
    --baseline all --streams --json y9_prov.json          # 9.5 s
```

Baselines (union): the six Autodesk sample projects (`dach`, `racadvanced`,
`racbasic`, `rme`, `rstadvanced`, `rstbasic`); primary = `rstbasicsampleproject`
(Y9's lineage root: rst → R9 → K3 → K4 → Y1…Y9; ElemTable-id overlap 1.0).
The tool's own headline: **"of 4,385,733 total inflated bytes, 75.24 %
identical-to-baseline, 24.76 % modified-lineage, 0.0 % ours"** (72.08 % / 27.92 %
excluding the schema stream).  Its `0.0 % ours` is a BLOCK-GRANULARITY artefact,
not a finding: the stream classifier matches 4,096-byte rolling blocks against
the baselines, and our objects are INTERLEAVED with Autodesk's inside the one host
save unit, so no whole block reads as "ours" — the unit reads `modified-lineage`
(1,037,776 unmatched bytes).  This document's four classes are RECORD-granular
(§3) and are the exact measure; the tool's element / string / identity layers are
used as-is and reconciled in §4.

## 2. Per-stream ledger (bytes vs the six samples)

From the tool's `stream_ledger` (R = role: **E** expression-bearing, **S** schema,
**F** identity/lineage fingerprint, **H** host element records):

| stream / unit | R | inflated | identical to a baseline | class | best baseline | class here (§3) |
|---|:-:|--:|--:|---|---|---|
| `Formats/Latest` | S | 496,597 | 496,597 (100 %) | identical | (all six — the 2026 schema constant) | **iii** product corpus |
| `Global/Latest` | E | 1,580,074 | 1,579,264 (99.95 %) | modified-lineage | rstbasic | **iii** 1,333,818 (ES corpus) + **iv** 246,256 (registry scaffold) |
| `Global/ContentDocuments` | E | 22 | 0 | "ours" (empty registry) | — | iv (0 embedded documents in a family-free base) |
| `Global/ElemTable` | F | 133,718 | 86,528 (64.7 %) | modified-lineage | rstbasic | iv registration machinery (**byte-identical to K4**) |
| `Global/History` | F | 18,171 | 18,171 (100 %) | identical | rstbasic | iv fingerprint |
| `Global/DocumentIncrementTable` | F | 5,094 | 5,094 (100 %) | identical | rstbasic | iv fingerprint (22 employee-signed episodes) |
| `Global/PartitionTable` | F | 95 | 95 (100 %) | identical | rstbasic | iv (workset table) |
| `BasicFileInfo` | F | 2,171 | 2,171 (100 %) | identical | rstbasic | iv identity fingerprint |
| `Contents` | F | 264 | 264 (100 %) | identical | rstbasic | iv (stream index) |
| `ProjectInformation` | F | 969 | 969 (100 %) | identical | rstbasic | iv fingerprint |
| `TransmissionData` | F | 3,838 | 3,838 (100 %) | identical | rstbasic | iv fingerprint |
| `Partitions/21` host unit 0 | H | 2,144,720 | 1,106,944 (51.6 %) | modified-lineage | rstbasic | **i** 275,603 + i' 10,363 + **ii** 1,643,673 + iv 215,081 |
| **total** | | **4,385,733** | 3,299,935 (75.24 %) | | | see §0 |

Stream identity Y9 ↔ K4 (measured directly, byte-for-byte on the logical
streams): **11 of 12 streams identical; only `Partitions/21` differs**.  In
particular `Global/Latest` and `Global/ElemTable` are byte-identical to K4's —
the in-place law held to the deepest rung: **zero registration motion, zero
ADocument motion, zero id-table motion** across 1,333 substitutions.

`Global/Latest` vs the rst SAMPLE differs in only **810 bytes** (99.95 %
identical): those are the K3/K4-lineage registry reconciliation (the
family-layer registrations DROPPED when K3/K4 removed the family documents —
Revit's own deletion semantics), inherited unchanged by Y9.  Nothing in the
ADocument is our expression: the 246,256 non-corpus bytes are the sample's
registry scaffold (CategoryTracking 53,528, AppInfoElementsAssociations 33,526,
NumberingAppInfo 29,071, SymbolIdMgr 19,146, ElementTrackingData 12,948, …) still
indexing the SAME ids — which is precisely why the in-place mechanism loads.

## 3. The record-granular accounting (host unit 0)

Y9's `Partitions/21` inflates to 2,144,720 payload bytes in 18 blocks / 1 save
unit = the three parallel record streams (seq 101 headers 476,410 B; seq 102
objects 1,589,300 B; seq 103 reps 78,954 B) + three sentinel records (56 B).
Zero non-host records (family-free).  Every one of the 3,342 host elements has
exactly one record per seq; the census partitions them:

| group | elements | seq-101 headers | seq-102 objects | seq-103 reps | total bytes | class |
|---|--:|--:|--:|--:|--:|---|
| landed, bytes changed (our expression) | 1,276 | 183,099† | **275,603** | 31,926† | 490,628 | object **i**; hdr/rep iv |
| landed, byte-identical to Autodesk's | 57 | (in †) | 10,363 | (in †) | 10,363 | i' |
| residue (never substituted) | 2,009 | 293,311 | 1,303,334 | 47,028 | **1,643,673** | **ii** |
| sentinels (3, one per seq) | — | 16 | 20 | 20 | 56 | iv |
| **host unit total** | **3,342** | 476,426 | 1,589,320 | 78,974 | **2,144,720** | ✓ (= the inflated block payload) |

† the seq-101 ElementHeader and seq-103 rep of a landed element are the
SAMPLE's bytes — in-place substitution is object-only (`seqs=(102,)`), so a
landed element's id, class, category, ownership web and creation vintage stay
Autodesk's registration.  That is machinery (class iv), and it is what "zero
registration motion" MEANS at the byte level: 215,025 bytes of Autodesk-authored
per-element registration wrapped around 275,603 bytes of our objects.

**What our 275,603 bytes are** (landed-changed seq-102 objects by class): the
built-in category / graphic-style catalog dominates — `GStyleElem` **206,272 B**
(1,172 rows, Y6/X6a); then the MEP size tables `RbsPipeSizesElem` 10,445 +
`RbsWireSizesElem` 5,111 + `RbsDuctSizesElem` 2,831 (our NEC/ASME/ASTM/SMACNA data,
Y4); `UnitsElem` 6,079 (Y8); the view constellation `DBViewPlan` 5,132 +
`DBViewType` 4,964 + `DBView3d` 1,948 + `DBViewProject` 1,921 (Y9); the palette
`MaterialElem` 4,751 + fill/line patterns (Y7); the navigator 2,275 (Y2); `Level`
1,628 + phases (Y8); the settings singletons (Y3/Y5).

**What the residue's 1,643,673 bytes are** — byte-weighted by the Yn buckets
(the honest queue, now sized by payload, not just by count):

| Yn bucket | elements | bytes | % of residue | heaviest classes |
|---|--:|--:|--:|---|
| definitions-removal-candidate | 791 | 422,925 | 25.73 % | ParamElemExternal 273,653 (466 shared-param definitions), ParamElemElectricalLoadClassification 80,376, ParamBinding 64,810 — the R10 param-defs group: a GC-removal rung, or a definition constructor |
| material-companions | 18 | 319,304 | 19.43 % | **AppearanceAssetElem** 316,478 (18 rendering-appearance blobs, ~17.6 KB each) — the palette's Autodesk asset library companions Y7 did not touch |
| no-constructor | 164 | 226,189 | 13.76 % | AssemblyCodeTable **125,370** (ONE element = the Uniformat assembly-code table), PropertySetElement 31,910, DimensionStyle 16,060 |
| product-data | 212 | 187,635 | 11.42 % | BuildingOperatingYearSchedule 88,404, HVACLoadSpaceTypeElem 66,666, HVACLoadBuildingTypeElem 17,641 — the HVAC/energy product database |
| surplus-sample-instances | 41 | 136,399 | 8.30 % | MaterialElem 114,800 (the sample's surplus materials beyond our role palette) |
| gap-X6b + family-scoped | 286 | 99,728 | 6.07 % | GStyleElem 99,728 (project SUBCATEGORY style rows — the X6b constructor gap) |
| gap-X6b | 209 | 77,916 | 4.74 % | CategoryElem 77,916 (subcategory records: angle-bracket line styles, template subcategories) |
| curtain-systems (no constructor) | 97 | 57,996 | 3.53 % | DBViewType 30,456 (curtain-system family-editor view types), curtain machinery |
| content-removal-candidate | 65 | 52,810 | 3.21 % | RefPlane 19,131, datum/room CONTENT that should leave, not be authored |
| constructor-exists | 72 | 32,425 | 1.97 % | classes we DO construct elsewhere but that did not land here (protected slots / no free donor) |
| constructor-partial | 52 | 27,998 | 1.70 % | partially covered classes |
| external-link-removal-candidate | 2 | 2,348 | 0.14 % | the linked-model instance + its type (RvtLinkInstance) |
| **residue total** | **2,009** | **1,643,673** | 100 % | (0 unbucketed) |

Byte-weighting reorders the queue: by ELEMENT COUNT the top buckets are the
definitions (791) and the two subcategory gaps (495); by BYTES the second-largest
item is 18 appearance assets (319 KB) and a single AssemblyCodeTable is 125 KB.
The four largest byte buckets (70.3 % of the residue: definitions 422,925 +
appearance/material companions 319,304 + the no-constructor tables 226,189 +
product data 187,635) are all "remove, or ship product data" questions
(definitions GC, appearance-asset companions, the assembly-code table, the HVAC
product database) rather than constructor gaps — i.e. the genesis endgame is
dominated by counsel / removal decisions, not by missing constructors.  The two
genuine constructor gaps (X6b subcategories 177,644, curtain systems 57,996) are
14.3 % of the residue by bytes.

## 4. Reconciling the element census with the byte measure

The two instruments count differently and BOTH are exact:

| statement | count / bytes | source |
|---|--:|---|
| host elements | 3,342 | ElemTable = K4's (in-place, no add / remove) |
| **landed** (object is our constructor's) | **1,333** = 1,276 changed + 57 identical | union of the nine rung reports' landed slots; the K4 ↔ Y9 record diff finds EXACTLY the 1,276 changed slots (all seq-102 only) = the reports' `records_changed_ids` union (verified equal) |
| landed but byte-identical to the parent | 57 | Y2 4 (default browser organizations) + Y3 3 + Y5 40 (empty settings machinery) + Y9 10 — our constructor reproduces Autodesk's own object; landed, nothing to change |
| **residue** | **2,009** | 3,342 − 1,333; every one bucketed by Yn (0 unclassified) |
| provenance tool, element layer vs rst | 2,059 "autodesk-sample" + 1,283 "ours-modified" | byte comparison of each element's records against the union of the six samples |

The provenance instrument's element verdicts map onto the census with **no
remainder**:

* 2,059 "autodesk-sample" (byte-identical to rst in all three seqs) = **2,002
  residue elements + our 57 landed-but-identical slots**.
* 1,283 "ours-modified" = **our 1,276 landed-changed slots + 7 residue elements
  that differ from rst without being ours**: `SectionAttributes` ×2,
  `ViewportAttributes`, `GridAttributes`, `CalloutTag`, `InteriorElevAttributes`,
  one `DBViewDrafting` — the K3-lineage family-USAGE fields nulled when the
  loadable-family layer left (K3 certified), inherited unchanged through K4.
  Sample-lineage records with one field nulled, correctly classed
  `modified-lineage`, correctly NOT ours.

So the census's **1,333 landed = 39.9 % of ELEMENTS** and this document's
**275,603 B = 6.3 % of BYTES** are the SAME fact seen through registration count
vs payload weight.  The gap is real and informative: a landed element averages
215 B of object (settings singletons, 40-byte catalog rows, view records), a
residue element averages 649 B (appearance blobs, parameter definitions, tables).
Genesis has captured the DENSE-in-registrations layers first; the residue is
dense in payload.  Per-layer object-byte capture of the seq-102 host objects
(1,589,300 B): ours 285,966 (18.0 %); residue 1,303,334 (82.0 %).

## 5. Layers this measure deliberately excludes (named, not hidden)

* **Identity / chain of custody** — the fingerprint streams (30,602 B, all
  byte-identical to rst) carry the sample's `BasicFileInfo` (author `Autodesk
  Revit`, the `C:\Users\hansonje\…\rstbasicsampleproject.rvt` save path, the
  sample's document GUID) and 22 of 22 `DocumentIncrementTable` save episodes
  signed by Autodesk employee usernames.  The provenance gate flags all seven
  identity violations.  This is a SOLVED, separable layer (V30–V32: our identity,
  our author string and scrubbed DIT usernames are each accepted by the reader) —
  applied by `rvt.identity` at delivery time, orthogonal to the element genesis
  measured here.  Genesis-progress numbers must be quoted "excluding the
  identity layer" until it is applied to the ladder's output.
* **Autodesk resource identifiers** — 8,605 (forge-typeid 8,378, `%1!s!`
  resource strings 108, `assetlibrary_base.fbx` 81, …) in 592 host elements'
  records: overwhelmingly the Forge unit typeIds inside our OWN unit/parameter
  objects (a units element must name `autodesk.unit.unit:squareMeters`) plus the
  residue's appearance-asset library references.  These are product IDENTIFIERS
  (the C4/G1c class), not sample authorship; the count falls only when the corpus
  and the appearance companions leave.
* **`RevitPreview4.0`** — absent from Y9 (K4's lineage carries no preview
  stream), so no Autodesk thumbnail PNG rides along.

## 6. What moves the number (the queue, byte-weighted)

Ranked by bytes released to "ours or gone" per action, from §3:

1. **Definitions removal** (R10-style GC of ParamElemExternal / bindings /
   load classifications) — up to 422,925 B out of the residue.
2. **Appearance-asset + surplus-material companions** — 319,304 + 136,399 B
   (either author appearance companions for the palette or remove them with a
   palette-only material set: Y6 PASS + Y7 FAIL would isolate them).
3. **The no-constructor tables + the product database** — the no-constructor
   bucket 226,189 B (dominated by ONE 125,370-byte AssemblyCodeTable, plus
   PropertySetElement 31,910 / DimensionStyle 16,060 …) and the HVAC/energy
   product-data bucket 187,635 B — ship-verbatim vs remove decisions.
4. **The X6b subcategory constructor** — 177,644 B (CategoryElem + subcategory
   GStyleElem), the largest genuine constructor gap.
5. Everything else (curtain systems 57,996, datum/room content removal 52,810,
   constructor-exists/partial 60,423, the linked model 2,348) — 173,577 B.

And on the constants side, counsel C4 alone decides whether the 1,830,415-byte
product-corpus class (41.7 %) is "ship verbatim" (it is a per-release Autodesk
constant in every 2026 file, project or family) or must be reconstructed / dropped
(the family-genesis PURITY mode already proves the family-scale corpus can be
emptied structurally; the project-scale reader tolerance is untested).

## 7. Reproduction (repo root, `.venv/bin/python`)

```
tools/provenance.py experiments/genesis/subst_k4/Y9.rvt --baseline all --streams --json y9_prov.json
# per-stream ledger, element/multi-baseline table, strings, identity  (~9.5 s)
```

The record-granular four-class accounting and the census reconciliation are
computed from the rung reports and two record diffs (Y9 ↔ K4 for the landed
slots — must equal the union of the reports' `byte_delta.records_changed_ids` +
`exceptions[].slots`; Y9 ↔ rst for the identity cross-tab), plus
`rvt.adocument.decode_latest(...).bytes_by_appinfo()` for the ESSchemaStorage
span of `Global/Latest`:

```
from rvt.mutate import Document ; from rvt import adocument as adoc
y9, k4 = Document.from_file(Y9), Document.from_file(K4)
changed = {e for e in y9.et_by_id if any(sig(k4.idx[s].get(e)) != sig(y9.idx[s].get(e)) for s in (101,102,103))}
# -> 1,276, all seq-102; framed record length = (12 if seq==101 else 16) + body_size + 4
adoc.decode_latest(latest_payload).bytes_by_appinfo()["ESSchemaStorage"]  # -> 1,333,818
```

The nine measured invariants (all re-checked this session): Y9's host id set ==
K4's (3,342, no add/remove); every changed record is seq 102; changed set == the
reports' union; `Global/Latest` ≡ K4's; `Global/ElemTable` ≡ K4's; 11/12 streams
≡ K4's; ES corpus = 893 unit + 422 parameter-schema pairs (1,333,338 string
bytes / 1,333,818 ledgered); 0 unbucketed residue elements; four-class sum ==
total inflated bytes.

## Unknowns

* The block-granular stream classifier's `modified-lineage` figure for the
  host unit (1,037,776 unmatched bytes) mixes our 275,603 with re-flowed
  Autodesk bytes around them; it is superseded here by the record accounting and
  should not be quoted as "ours".
* Whether the reader tolerates removing the 1,333,818-byte ES corpus at PROJECT
  scale is untested (family scale: purity mode structurally clean, viewer round
  pending).  The 41.7 % class is a counsel decision until then.
* The 57 landed-but-byte-identical slots are attributed to us by construction
  and to Autodesk by bytes; a stricter reading counts them as neither expression
  (empty machinery) — the tables list them separately for that reason.
