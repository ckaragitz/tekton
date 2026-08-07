# PROVENANCE LEDGER — making the cutover gate checkable

`src/rvt/provenance.py` + `tools/provenance.py` (2026-08-03; **v2 rev the
same night** — see §0).

## 0. v2 CORRECTION — the honest, stream-aware, multi-baseline headline (READ FIRST)

The v1 instrument (§1–§7 below, retained) walked **only the ElemTable**,
against **one** baseline. The genesis audit (`docs/inbox/genesis-audit.md`)
caught it reporting `0 autodesk-sample` on `experiments/genesis/G0.rvt` — a
file whose **bytes** are ~94 % Autodesk (the sample's `ADocument` carried
verbatim in `Global/Latest`, Autodesk's class model in `Formats/Latest`, the
sample's save history and Autodesk employee usernames in
`Global/History` / `Global/DocumentIncrementTable`). Every earlier headline
in §3 that counts elements only is therefore **SUPERSEDED as a G1 statement**
(the numbers are correct for what they measured; what they measured was not
the document). v2 makes the under-count structurally impossible:

**G0.rvt — CORRECTED, certified run** (`tools/provenance.py
experiments/genesis/G0.rvt --baseline all --streams --json
experiments/genesis/provenance/G0_v2.json`; text in `G0_v2.txt`):

* **Byte-weighted (stream ledger):** of **2,218,218** total inflated bytes,
  **94.91 % identical-to-baseline**, 0.15 % modified-lineage, **4.94 % ours**.
  Excluding the schema stream `Formats/Latest` (counsel C4, reported
  separately): of 1,721,621 bytes, **93.44 % identical**, 0.20 %
  modified-lineage, **6.36 % ours** — the auditor's "~94 % / ~6 %", now
  produced by the instrument itself.

  | stream / unit | role | inflated | identical | class | which baseline |
  |---|---|--:|--:|---|---|
  | `Global/Latest` (the ADocument) | **E** gated | 1,586,254 | **1,586,254 (100 %)** | identical | rstbasicsampleproject |
  | `Formats/Latest` (class model) | schema (C4) | 496,597 | 496,597 (100 %) | identical | all six samples |
  | `Global/PartitionTable` | fingerprint | 95 | 95 (100 %) | identical | rstbasicsampleproject |
  | `Global/History` | fingerprint | 18,188 | 17,408 (95.7 %) | modified-lineage | rstbasicsampleproject |
  | `Global/DocumentIncrementTable` | fingerprint | 5,336 | 4,608 (86.4 %) | modified-lineage | rstbasicsampleproject |
  | `BasicFileInfo` | fingerprint | 1,915 | 256 (13.4 %) | modified-lineage | (version-marker block) |
  | `Contents` | fingerprint | 264 | 0 (prefix-shared 68 %) | prefix-shared | rstbasicsampleproject |
  | `Global/ContentDocuments` | **E** gated | 22 | 0 | ours | — |
  | `Global/ElemTable` | fingerprint | 8,238 | 0 | ours | — |
  | `Partitions/21#host` (our 205 records) | host-records | 100,354 | 0 (4 KB granularity) | ours | — |
  | `ProjectInformation`, `TransmissionData` | fingerprint | 955 | 0 | ours | — |
  | embedded family save units | **E** gated | — | — | **none present (0)** | genuinely gone |

* **Multi-baseline (union over all six samples), elements:** **154 of 205
  transitive-cloned, 51 ours-created** (single-baseline rst reported 142/63).
  Per baseline: rst 142, rme 130, racbasic 140, racadv 129, rstadv 126,
  dach unmatched (no lineage; wrong file). Of the 51 "created", **26 have
  max-similarity < 0.40 against every sample, 6 below 0.25** — the rest are
  Autodesk product-default values reproduced. The named exhibits the audit
  found are now attributed by the instrument: **`DBViewProject` 1500176 =
  0.91 structural clone of racbasic's `DBViewProject` 230** (rst calls it
  created — baseline luck); **`ElectricalSetting` 1500036 = 0.79 clone of
  rme's `ElectricalSetting` 639116** (and racadvanced's / rstadvanced's);
  `Viewer` 1500177 = 0.90 of racbasic 231; `BasePoint`s 1500161/2 =
  0.89–0.95 of racadvanced/rme; the three `DBViewType`s = 0.68–0.71 of
  racbasic's. Derived-element attribution (which sample owns the closest
  specimen): racadvanced 114, racbasic 16, rme 14, rst 8, rstadvanced 2.
* **Autodesk resource refs (G1c): 7,438** in document content — 7,350 in
  `Global/Latest` (7,292 Forge `autodesk.*` typeIds + `forge-data-schema`
  + `Autodesk` ×52 + `ADSK` + `AREXContentGenerator` / `Revit Default DB
  Server` + one `autodesk.com`), and **88 inside OUR own `Partitions/21`
  records** (`assetlibrary_base.fbx` ×35, the `%1!s!` MACH load-label
  templates ×24, Forge typeIds ×21, `SunAndSky` ×8) carried by **20 host
  elements** (15 `MaterialElem`, 4 load-label / units elements). The schema
  stream's own identifiers are tallied separately (counsel C4).
* **Identity (G2 policy):** `BasicFileInfo` is now OURS (author / username
  `rvt-writer`, `last_save_path` = `G0.rvt`, fresh document GUID) — but
  **`Global/DocumentIncrementTable` still signs 22 of 23 save episodes with
  Autodesk employee usernames** (loboarch ×9, okapaw ×4, xuew ×3, youyi ×2,
  zhangg, gbs_subsuser6, campbes, hansonje). The writer's V32 scrub post-dates
  `G0.rvt` on disk; the ledger flags it until G0 is regenerated.
* **G1 v2 verdict: FAIL — four independent blockers.** 150 Autodesk-derived
  elements in expression-bearing categories (154 clones minus 4 report-only
  datums); **1,586,254 bytes byte-identical to baseline in an
  expression-bearing stream** (the ADocument — the audit's exhibit A);
  7,438 Autodesk resource identifiers; 1 identity violation (22 employee
  usernames). Plus one **counsel item C4** (schema stream byte-identical —
  not a mechanical blocker, a decision) and five lineage-fingerprint
  advisories (History / DIT / Contents / PartitionTable / BFI). This is the
  G1 sub-gate decomposition in the TRACKER: G1a = the 1.59 MB stream blocker
  (ADocument encoder), G1b = the 154 clones + 25 high-similarity "created",
  G1c = the 7,438 refs, G1d = this instrument (now DONE).

The **G1 verdict is recomputed honestly**: PASS now requires zero derived
elements AND **zero identical-to-baseline bytes in the expression-bearing
streams** (`Global/Latest`, `Global/ContentDocuments`, every family save
unit) AND zero `autodesk-resource-refs` AND OUR identity — with
`Formats/Latest` reported as `schema-stream (counsel C4)`, not counted. A run
that ledgers only some layers can only "pass" those layers and is labelled
`NOT a G1 certification` (`gate_G1.certifies_G1 == false`) — an
element-only PASS can never again read as the document passing.

**How v2 works** (all in `provenance.py`, v1 API unchanged and green):
- *Stream ledger* (`content_units`, `stream_ledger`): every OLE stream is
  one unit (member-bearing streams = 8-byte prefix + all inflated gzip
  members; raw streams = de-paged bytes); every `Partitions/N` yields the
  host unit `#host` plus one unit `#uK`+GUID per embedded family save unit
  (blocks inflated per unit). Classification per unit: whole-content sha1
  identity against any baseline unit (any name), exact common-prefix against
  the same-named / same-GUID counterpart, and an **rsync-style block cover** —
  the baselines are indexed as 4,096-byte (plus 256-byte for OLE streams under 4 MB)
  aligned blocks (weak rolling checksum + blake2b), the candidate is scanned
  with a rolling weak hash at every offset (vectorised via numpy prefix
  sums), verified by strong hash; low-entropy (≤ 2 distinct byte values)
  blocks are excluded so zero-padding is never "copying". identical =
  whole match; prefix-shared = same-named common prefix ≥ 50 %;
  modified-lineage = ≥ 10 % of bytes exist in a baseline; else ours. The
  three buckets partition each unit (identical + lineage-remainder + ours ==
  inflated) so the byte-weighted percentages sum to 100. Baseline block
  indexes are disk-cached (`experiments/genesis/provenance/.cache/`, keyed
  by size+mtime): first six-sample run indexes ~1.3 GB inflated in ~13 s
  total (index cache ~29 MB), cached re-run ~8 s.
- *Multi-baseline* (`classify_elements_multi`, `--baseline` repeatable or
  `all`): the v1 classifier is run per baseline; the union takes precedence
  sample > modified > cloned > created > unmatched (ties broken by highest
  clone similarity), and each verdict carries `attribution` (which baseline)
  and `baselines` (every reading). `dach`'s "205 unmatched" (ids below its
  watermark, absent from it) correctly loses to the samples that explain
  them.
- *Resource refs* (`scan_resource_refs`, `resource_ref_report`): nine
  patterns (`RESOURCE_PATTERNS`), matched over a NUL-collapsed buffer so
  ASCII and UTF-16LE strings hit in one pass; per stream/unit and per host
  ELEMENT.
- *Identity* (`identity_report`): author `Autodesk Revit` / client
  `RevitApplication`, employee usernames (BFI or any DIT episode), a template
  path in `last_save_path`, or a document/episode GUID equal to any
  baseline's = blocking; a non-product author string = counsel-C1 advisory.
- CLI (`tools/provenance.py`): `--baseline` repeatable / `all` / `auto` /
  `self`; `--streams --strings --identity` all default ON (`--no-*` gives the
  v1 element-only run); exit `0` = G1 certified PASS, `2` = FAIL, `3` = the
  ledgered layers pass but it is not a full certification. Tests: 22 in
  `tests/test_provenance.py` (11 v1 + 11 v2), all green.

**What honest closure now takes** (each is a specific blocker in
`G0_v2.json`, not a slogan): (G1a) an `ADocument` (`Global/Latest`)
decoder→encoder emitting OUR document object — retires the 1.59 MB byte
blocker and, with our History/DIT/Contents lineage, all five fingerprints;
(G1b) our own default values for the 154 clones + 25 high-similarity
"created" (view constellation, ElectricalSetting, phase filters, GStyleElem
pens) — the certified run must stay `--baseline all` so a default sourced
from ANY sample gates; (G1c) parameterise the 88 resource refs in our
constructors and rule on the 7,350 in the ADocument (they leave with G1a);
regenerate `G0.rvt` through the current writer to clear the 22 DIT
usernames; and counsel C4 on `Formats/Latest`. Only when
`gate_G1.certifies_G1` reads `true` on a `--baseline all --streams` run has
G1 closed.

*The rest of this document is the v1 record, retained; its element-only
headlines (e.g. §3, and the "142 cloned / 63 created" G0 numbers cited
elsewhere) are superseded as G1 statements by §0 above.*

`docs/product/content-strategy.md` sets the P0 shipping gate: **nothing ships
until the base document contains NO Autodesk-authored expression** — not just
"no families", but system-family TYPES (wall / duct / pipe / conduit /
cable-tray types), view templates, object styles, fill / line patterns, text
and dimension styles, annotation symbols, shared-parameter definitions,
keynote and load-classification settings. Until now that gate was a slogan.
The provenance ledger is the instrument that makes it a NUMBER: run it on any
candidate `.rvt` and **G1 passes iff the report shows ZERO
`autodesk-sample` and ZERO `transitive-cloned` elements in every
expression-bearing category** (and zero Autodesk-sample embedded family
documents).

## 1. What it classifies

For EVERY element of the host document (against a reference Autodesk sample,
the *baseline*, that the candidate descends from):

| provenance | rule | meaning |
|---|---|---|
| `autodesk-sample` | id in baseline, same class, byte-identical seq-102 object (+ seq-101 header, seq-103 rep) | Autodesk's original object, untouched |
| `ours-modified` | id in baseline, same class, payload differs | a sample element WE edited — still derived expression |
| `ours-created` | id NOT in baseline and above the baseline's id watermark (`IdentifierSource.m_last`), with no lineage into sample expression | genuinely ours |
| `transitive-cloned` | created (as above) but it REFERENCES a sample-authored definition (its family symbol / wall type / cable type ...) or its body is a STRUCTURAL CLONE of a sample specimen (>= 50 % 16-byte-shingle overlap) | cloned geometry / parameters of an Autodesk element is still derived expression **until the family / type itself is ours** — the honest state of everything our create machinery emits today |
| `unmatched` | id not in baseline and not above the watermark, or a class collision at the same id | wrong baseline (or renumbered); never passes a gate |

Embedded family DOCUMENTS (partition save units 1..k) are ledgered as units:
a unit whose separator GUID (== a host `Family.m_oFamDoc.m_contentDocGUID`)
exists in the baseline is an Autodesk family document; an unknown GUID is
ours / imported.

Every element is then binned into a **legal category** (18, of which 15 are
*expression-bearing* = named by the gate): embedded family documents,
loadable families, family types (symbols), system-family types, views &
templates, object styles, fill / line patterns & materials, text /
dimension / arrowhead types, annotation symbols & title blocks, parameter
definitions, phases / design options, project info & settings, MEP /
electrical definition tables, plus the honest extras the samples force:
placed model content (the sample's geometry), view-owned 2D / annotation
content, datums (levels / grids — report-only), internal bookkeeping
(report-only). **Coverage: zero unmapped classes across all six 2026
samples** (the taxonomy is checked class-by-class; `unmapped` is itself a
gated category so a new class can never slip through silently).

## 2. Running it

```
tools/provenance.py FILE.rvt --baseline all --streams --json out.json      # THE certified run (v2)
tools/provenance.py FILE.rvt --baseline samples/rst.rvt --baseline samples/rme.rvt   # multi
tools/provenance.py FILE.rvt --baseline auto     # picks the best-overlapping samples/*.rvt
tools/provenance.py FILE.rvt --baseline self     # a sample against itself
tools/provenance.py FILE.rvt --strict            # also gate datums / bookkeeping
tools/provenance.py FILE.rvt --no-streams --no-strings --no-identity   # v1 element layer only
```

Exit code `0` = G1 **certified** PASS (all four layers ran, none blocks),
`2` = fails, `3` = the ledgered layers pass but it is not a full G1
certification — usable as a CI gate.  (v1 note: `--streams/--strings/
--identity` default ON since v2; `--no-*` reproduces the v1 element-only run.) Output: a
`category x provenance` table (`E` = expression-bearing), per-class detail
with example element ids **+ resolved names**, the embedded-unit table, and
the G1 verdict with its blocking list. `--json` writes the complete report
(per-element verdicts for every created / modified element, with clone
lineage). Runtime: 0.3 s (rst 6.7 MB) to 2.5 s (rme 32 MB, 28 k elements),
dach 139 MB in ~4 s.

## 3. The three commissioned reports (`experiments/genesis/provenance/*.json`)

### 3.1 A fresh Autodesk sample against itself — `rme_self_baseline.json`

`rmebasicsampleproject.rvt` vs itself: **28,132 / 28,132 `autodesk-sample`,
305 embedded family documents, all Autodesk.** This is the calibration run —
the instrument reads a pristine sample as 100 % Autodesk-authored across every
category, which is what makes a future "0" believable.

| category (E = gated) | count |
|---|--:|
| Embedded family documents (units) E | 305 |
| Loadable families E | 513 (159 Family + 159 FamilySurrogate + 192 FamSymSurrogate + 3) |
| Family types (symbols) E | 1,067 (574 FamilySymbol, 257 mullion, 208 panel syms ...) |
| System-family types E | 126 (23 piping-system, 10 wall, 10 conduit, 8 floor, 7 cable-tray types ...) |
| Views & view templates E | 943 |
| Object styles E | 3,483 (2,459 GStyleElem + 1,020 CategoryElem + 4) |
| Patterns / materials E | 1,429 (750 fonts, 241 appearance assets, 192 materials, 69 line + 66 fill patterns ...) |
| Text / dimension / arrowhead types E | 864 (241 text, 215 leader/arrowhead, 214 tag, 128 filled-region attrs ...) |
| Annotation symbols & title blocks E | 62 |
| Parameter definitions E | 1,438 (1,331 family, 60 load-classification, 20 property sets, 12 bindings, 8 shared ...) |
| Phases / design options E | 18 |
| Project info & settings E | 35 |
| MEP / electrical definition tables E | 317 (125 space types, 33 building types, 12 demand factors, wire / pipe tables ...) |
| Datums (report-only) | 131 |
| Placed model content E | 10,751 |
| View-owned 2D / annotation content E | 6,529 |
| Internal bookkeeping (report-only) | 426 |

G1: **FAIL — 27,880 Autodesk-derived elements in expression-bearing
categories.** (13 more report-only + datums make the 28,132.)

### 3.2 The circuits acceptance file — `V29_room_with_circuits.json`

`experiments/acceptance/V29_room_with_circuits.rvt` (the electrical room
with panels, a transformer, walls and 3 circuits — accepted by the Autodesk
translator) vs `rmebasicsampleproject.rvt`: **28,132 `autodesk-sample` +
16 `transitive-cloned`, 0 created, 0 modified.** This is the honest current
state of our writer: everything it creates is a clone of an Autodesk
specimen, and the ledger says exactly which one.

| created id | class | verdict | lineage the ledger recovered |
|---|---|---|---|
| 888014–888017 | SWall | transitive-cloned | references sample `BasicWallType 563416 "MW 11.5"` via `m_WallAttributesId`; 84–86 % structural clone of sample `SWall 573735` |
| 888018–888023 | FamilyInstance (panels "MDP-1") | transitive-cloned | `m_symbolId` -> sample `FamilySymbol 619617 "400 A"` (`M_Lighting and Appliance Panelboard - 480V MCB - Surface`); 87–88 % clone of instance 742670 |
| 888024–888026 | FamilyInstance (transformers) | transitive-cloned | `m_symbolId` -> sample `FamilySymbol 621228 "45 kVA"` (`M_Dry Type Transformer - 480-208Y120 - NEMA Type 2`); 89 % clone of 624416 |
| 888027–888029 | RbsElectricalSystem (circuits) | transitive-cloned | reference sample `RbsCableType 887996 "XHHW"` (a system-family type) |

G1: **FAIL — 27,896 = 27,880 sample + 16 clones.** The 16 clones live in
`placed-model-content` but their *lineage* is the point: even a "genesis"
file built with this machinery would fail the gate because every panel is
derived from an Autodesk family and every circuit from an Autodesk cable type.
That is the flag content-strategy asked for.

### 3.3 The deepest reductions — the GAP LIST for the assembler

Two files, because "deepest" has two meanings:

**`R4s_deepest_viewer_passed.json`** — `R4s.rvt`, the deepest reduction that
**passed the Autodesk viewer** (safe sweep, 798 deletions, 13,138 elements
kept). Every survivor is byte-identical Autodesk content: G1 **FAILS with
12,986 derived elements** across all 15 expression-bearing categories (150
families, 96 symbols, 104 system types, 541 views, 2,803 styles, 843
patterns/materials, 302 text/dim types, 27 annotation symbols, 971 param
defs, 21 phases, 38 settings, 376 MEP definitions, 1,464 placed model, 5,198
2D/annotation) **plus all 52 embedded Autodesk family documents.** The safe
sweep is garbage collection, not de-authoring.

**`R4_deepest_skeleton.json`** — `R4.rvt`, the deepest structural skeleton
(closure delete, 11,097 deletions, 2,839 elements kept; not viewer-passed,
Latest-dangling). This is the sharpest picture of the **irreducible core the
assembler must re-author**:

| category | count | what it is | assembler action |
|---|--:|---|---|
| Object styles | **2,801** | 2,183 GStyleElem + 616 CategoryElem + 2 ModelGraphicsStyle | regenerate from OUR category / style catalog via the encoder — the single biggest block |
| Embedded family documents | **52** | Autodesk families copied byte-for-byte (the reducer never touches embedded save units 1..k) | drop the units, then load ONLY our own generated families (needs the ContentDocuments encoder + id remap) |
| Phases / design options | 14 | 7 phase filters, 3 design options, 2 phases, sets | author (trivial tables) |
| Project info & settings | 13 | geo site/location, base points, units, true north, worksharing settings | author from our project template |
| Datums | 9 | levels | author (report-only, but the assembler writes them anyway) |
| Views & view templates | 1 | one DBViewType | author at least one view + type (a project with zero views may not open — the R2 probe) |
| Parameter definitions | 1 | KeynoteTable | author or omit |

So the distance from "deepest reduction" to "genesis base" is dominated by
**(a) the 2,801-object category / style table and (b) the 52 embedded
family documents** — both are things the assembler must PRODUCE, not merely
delete, which is exactly why reduction alone can never satisfy the gate.
`R4s`/`R4` also confirm the reducer's blind spot: it deletes host elements
only, so every reduction keeps 100 % of the embedded Autodesk families.

## 4. All four provenance verdicts are exercised on real files (tests)

`tests/test_provenance.py` (11 tests, ~6 s): taxonomy coverage (zero unmapped
on rst + rme), explicit category assertions, self-baseline == all sample,
V29 == 28,132 sample + 16 clones with the exact class mix and named lineage
(BasicWallType / FamilySymbol / RbsCableType), `M3_modify.rvt` -> exactly 2
`ours-modified` (a Level + a FamilyInstance, "differs in object"), R2s
reduction == pure sample survivors, wrong-baseline detection (rme vs the rst
baseline -> 26,900+ `unmatched`, overlap warning, gate refuses), gate logic
(empty ledger passes; one sample loadable family fails; `strict` gates
datums; no baseline never passes), CLI end-to-end (JSON + exit code 2).

## 5. Design decisions worth knowing

- **Watermark rule for creation.** "Created" = absent from the baseline AND
  id above the baseline's `IdentifierSource.m_last`. The ElemRec
  `creation_ep` is NOT usable: our commit path reuses an existing episode
  (KNOWLEDGE §commit layer), so episodes cannot distinguish our elements.
- **Two independent clone detectors.** (1) *Lineage*: references from the
  created element's three record streams (seq 101/102/103, via
  `mutate._collect_ids`, minus geometry-index false positives such as
  `m_geomSteps…m_faces[i].m_id`) into sample elements of a lineage-bearing
  category (families, symbols, system types, styles, patterns, text types,
  annotation symbols, param defs, MEP definitions). (2) *Structural*:
  16-byte-shingle overlap of the created payload against a per-class index
  of baseline payloads; >= 50 % => clone (walls score 84–86 %, instances
  87–89 %). Both are reported (`lineage`, `clone_of`, `clone_similarity`) so
  the verdict is inspectable, not asserted. A future genesis file whose
  instances reference OUR families and share no specimen bytes will read
  `ours-created`.
- **Wrong-baseline safety.** An id that is neither in the baseline nor above
  the watermark is `unmatched`, which blocks the gate; a candidate whose id
  overlap with the baseline is < 90 % raises a `WARNING: baseline mismatch`.
  `--baseline auto` picks the samples/*.rvt with the best ElemTable
  id-set Jaccard so a human can't feed the wrong reference silently.
- **Report-only categories.** Datums (levels / grids) and internal
  bookkeeping are counted but not gated by default (a "Level 1 at 0.0" is
  not expression; trackers are machine state). `--strict` gates them too
  for the conservative reading. The gate list itself is a legal decision;
  `CATEGORIES[...] [1]` (expression_bearing) is the one-line switch counsel
  can flip.
- **`unmapped` is a gated category.** A class the taxonomy has never seen is
  treated as expression-bearing until reviewed — the instrument fails
  closed. Today: 0 unmapped across all six samples.

## 6. Known limits (honest list)

1. `ours-modified` compares record bytes only; it does not say WHAT changed
   (a location move and a parameter edit look the same). The report keeps
   which seqs differ (`differs in object+header`).
2. Structural clone detection is a shingle heuristic with a fixed 50 %
   threshold; a heavily reworked clone could fall below it — but such an
   element still trips the lineage detector as long as it references a
   sample type. An element that is BOTH structurally novel AND references
   nothing Autodesk-authored reads `ours-created`, by design.
3. The embedded-unit ledger keys on the save-unit separator GUID. Only a
   subset of units link to a host `Family` name via
   `m_oFamDoc.m_contentDocGUID` (rst: 41/52; rme: 147/305); the rest report
   GUID + block/record counts only (nested families and annotation-family
   documents are reached through a different id path — resolvable once the
   ContentDocuments object array is decoded).
4. Provenance is relative to the SUPPLIED baseline. A candidate assembled
   from two samples would need two runs; the tool ledgers against one
   reference at a time and flags the rest as `unmatched`.
5. The category taxonomy is our engineering reading of "what matters
   legally"; the expression-bearing flags are the review surface for
   counsel (`docs/product/content-strategy.md` §5).

## 7. How the assembler should use it

Every genesis milestone gets a ledger run committed next to the file:
`tools/provenance.py candidate.rvt --baseline <the sample its skeleton
came from> --json experiments/genesis/provenance/<name>.json`. The
milestone is done when the gap list is empty — not before. The current gap
list (R4 skeleton) is the assembler's ordered work queue: **object-style /
category catalog encoder (2,801) -> family-document removal + our-family
loader (52) -> phases/settings/levels/view-type authoring (~38).**
