# THE REQUIRED SET — what EVERY reader-accepted Revit project contains

Stream: **genesis-triage-census** (2026-08-03). Instrument: `src/rvt/census.py`
(new; `tests/test_census.py`). Companion record: `docs/inbox/genesis-triage-census.md`.
Everything below is MEASURED this session on the files themselves — no verdict is
inherited. Reproduce: `.venv/bin/python -m rvt.census --certified` (~15 s, 38 files).

The method is the one the two failed nights lacked: build the model of what a
loadable file MUST contain from **positive evidence only** — the intersection over
every file Autodesk's own reader ACCEPTS — instead of from what our validator or a
deletion cascade happens to tolerate. Then diff the six REJECTED files against it.

---

## 0. One-screen verdict

* **Corpus:** 32 reader-ACCEPTED files (the six 2026 samples incl. the German
  worksharing `dach` project + every `viewer-certified.json:certified` file on disk
  — `experiments/acceptance/V15_regzip_ecc_full.rvt` is listed but absent) vs the
  6 reader-REJECTED files (`G0`, `G1_candidate`, `G1a`, `G1b`, `R9b`, `R10b`).
* **The candidate MANDATORY set = 149 element classes present in EVERY accepted
  file.** Its hard core: **70 classes carry the IDENTICAL count in all 32 files**
  (a residential rst reduction, an MEP model, a German worksharing project — same
  numbers): the document-settings singleton constellation + the compiled-in
  MEP/analysis catalogs. This is the strongest positive evidence the format has
  given us.
* **BUG A (G0 / G1a / G1_candidate / G1b — all four have byte-IDENTICAL element
  inventories, 234 elements / 47 classes) misses 110 of the 149 core classes,
  including 62 of the 70 invariant ones**, is 16–40× short on the ones it has
  (`GStyleElem` 94 vs an accepted floor of 1,533; `CategoryElem` 7 vs 284), and
  carries **zero family machinery** where every accepted file carries ≥ 21 host
  families, ≥ 13 with embedded documents, ≥ 52 embedded content-document units.
  Verdict #4's Bug-A hypothesis ("skeleton completeness — settings singletons /
  catalogs") is now a measured list, ranked in §2 and Appendix A.
* **BUG B (R9b / R10b) is attributed BELOW the element layer:** `R9` (PASS) and
  `R9b` (FAIL) have **identical host inventories (3,709 elements, 162 classes,
  count-for-count)**; the only difference is content-document machinery —
  units 53→15, `ContentDocuments` entries 52→14 (GUID-coherent among themselves),
  while the ADocument's **`ContentTable` still lists 52 records → 38 DANGLING
  content records** (`content_records_without_document = 38`). The
  `ContentDocuments` framing hypothesis is **CLOSED by measurement**: R9b's and
  R10b's CD streams already parse and reassemble BYTE-EXACT through the solved
  grammar (§3.3) — the CD half of the splice is not malformed.
* **The DBViewType default-head-family question is answered, and it EXONERATES
  the reference:** the English samples' 72 `DBViewType.m_famId` references point at
  the eight document-less curtain-wall SYSTEM families, never at annotation heads;
  the accepted `dach` sample's 23 view types reference **no family at all**. A
  DBViewType that references nothing (G1's shape) is an ACCEPTED shape (§4).

---

## 1. Method (what `rvt.census` measures per file)

| layer | measurement | source |
|---|---|---|
| element classes | histogram of seq-102 records of the HOST document = partition save-unit 0, filtered by `Global/ElemTable` ids | `FamilyIndex.unit_records(0)`, `parse_elemtable` |
| streams | every OLE stream + raw size; the `Partitions/<N>` names | `RvtDocument.streams()` |
| save units | total units, GUID-less (host) units, GUID units (= embedded documents) | `StreamWalker` via `FamilyIndex` |
| coherence | the three GUID sets: partition units ↔ `Global/ContentDocuments` entries ↔ ADocument `ContentTable.m_ContentRecSet` (dangling counts both ways) | solved CD codec (`famgen.factory.parse_content_documents`) + `rvt.adocument` |
| families | host `Family` census: name, has-embedded-document (its `m_oFamDoc.m_contentDocGUID` resolves to a unit) | element decode |
| DBViewType | every `m_famId` / `m_sectionAttrId` / `m_calloutAttrId` / `m_elevatnAttrId` / `m_defaultTemplateId` / … target: class, exists?, family-with-document? | element decode |

Diffs: `mandatory_set` (∩ classes over the accepted set, min/max count),
`class_presence` (N/32), `missing_from` / `rank_suspects` (mandatory classes
absent in a rejected file, ranked by universality → central count),
`count_shortfall` (present but below the accepted minimum),
`stream_unit_matrix`. The accepted set is dominated by three lineages
(rst-reductions, rme-electrical, rac-manipulation) plus the four independent
sample projects; **`R9` (3,709 elements) is the deepest accepted element
inventory and single-handedly sets 39 of the class minima and, by its PASS,
proves 81 classes OPTIONAL.** Every "min" below is therefore "the smallest count
in an accepted file", not a proven floor — except the 70 invariant classes, which
are constant across all 32.

---

## 2. The ranked mandatory-set table

Full 149 rows in **Appendix A** (`class | 32/32 | min | max | in G1 | in R10b |
verdict | min set by`). The load-bearing tiers:

### 2.1 Tier 1 — INVARIANT COUNT in every accepted file (70 classes; 62 absent from the G-files)

The same number of elements of these classes in all 32 files, from a 3,709-element
reduction to the 49,776-element German project. They are Revit's per-project
compiled-in machinery: settings singletons (count 1) and product catalogs.

| class | count (32/32) | in G1 | class | count (32/32) | in G1 |
|---|--:|--:|---|--:|--:|
| `HVACLoadSpaceTypeElem` | 125 | 0 | `KeynoteTable` | 1 | 0 |
| `HVACLoadBuildingTypeElem` | 33 | 0 | `AssemblyCodeTable` | 1 | 0 |
| `RbsPipeConnectionType` | 8 | 0 | `AllProjectRevisions` | 1 | 0 |
| `RbsPipeMaterialType` | 5 | 0 | `RevisionNumberingSequence` | 2 | 0 |
| `NumberingSchema` | 3 | 0 | `PenWidthTableElem`* | 8–11 | 0 |
| `BasePoint` | 2 | 2 | `BrowserOrganization`* | 11–12 | 0 |
| `GeoSite` | 2 | 2 | `RbsDuct/Pipe/Wire/CableTray/Conduit` `SettingsElem` (5) | 1 each | 0 |
| `AutoJoinTracker` | 1 | 0 | `RbsDuct/Pipe/Wire` `SizesElem` (3) | 1 each | 0 |
| `WallJoinDefaultSetting` | 1 | 0 | `StructSettingsElem` | 1 | 0 |
| `AreaSettingsElem` | 1 | 0 | `ReinforcementSettings` | 1 | 0 |
| `GraphicsCache` | 1 | 0 | `RbsDbViewSystemNavigator` | 1 | 0 |
| `MEPSystemTracker` / `MEPNetworkTracker` / `MEPComponentTracker` | 1 each | 0 | `ReconcileBrowserSettingsElem` | 1 | 0 |
| … 57 count-1 singletons in total | 1 | 8 present† | (`PenWidthTable`/`BrowserOrg` vary 8–12, listed here for the theme) | | |

† The 8 invariant classes G1 already has: `AllProjectPhases`, `BasePoint`×2,
`DBViewProject`, `ElectricalSetting`, `GeoSite`×2, `ProjectInfo`, `TrueNorth`,
`UnitsElem` — exactly the assembler's 5 populated `UniqueElementsTracking` slots +
the geo pair + the units element. \* strictly Tier 2 (count varies 8–12) but
part of the same settings constellation. **The 62 absent invariant classes are the
census's independent restatement of genesis-2's "67 empty singleton slots"** — two
different instruments (the ADocument's positional `UniqueElementsTracking` table
and the element census) name the SAME gap. Full list of the 62: Appendix A rows
marked `count invariant` with `in G1 = 0`.

### 2.2 Tier 2 — present in EVERY accepted file, count varies (79 classes)

The catalog / graphic-machinery floor. `min` = the smallest count any accepted
file carries; `min set by` names the file that carries it.

| class | min | max | in G1 | verdict | min set by |
|---|--:|--:|--:|---|---|
| `GStyleElem` | 1,533 | 5,596 | **94** | REQUIRED-class; G1 16× short | R9/R10b (the object-styles catalog) |
| `CategoryElem` | 284 | 4,076 | **7** | REQUIRED-class; G1 40× short | R9 |
| `FontElem` | 96 | 3,315 | **3** | REQUIRED-class; G1 32× short | R9 |
| `SketchPlane` | 32 | 1,449 | 2 | REQUIRED-class | R9 |
| `MaterialElem` | 23 | 213 | 13 | REQUIRED-class | R9 |
| `DBViewType` | 23 | 102 | **3** | REQUIRED-class (view-type set) | dach |
| `TextNoteAttributes` | 25 | 1,155 | 3 | REQUIRED-class | R9 |
| `Family` / `FamilySurrogate` | 21 | 284 | **0** | REQUIRED-class (family floor, §3.2) | R9 |
| `TagNoteAttributes` | 20 | 850 | 0 | REQUIRED-class | R9 |
| `PropertySetElement` | 20 | 67 | 0 | REQUIRED-class | R9 |
| `LeaderStyle` | 19 | 810 | 0 | REQUIRED-class | R9 |
| `AppearanceAssetElem` | 18 | 265 | 0 | REQUIRED-class | R9 |
| `FamilySymbol` / `FamSymSurrogate` | 17 | 1,157 | **0** | REQUIRED-class | R9 |
| `FilledRegionAttributes` | 16 | 762 | 0 | REQUIRED-class | R9 |
| `ParamElemFamily` | 13 | 2,353 | 0 | REQUIRED-class | R9 |
| `DimensionStyle` | 12 | 24 | 0 | REQUIRED-class | R9 |
| `BrowserOrganization` | 11 | 12 | 0 | REQUIRED-class (settings constellation) | rst lineage |
| `RbsPipeScheduleType` | 10 | 13 | 0 | REQUIRED-class (MEP catalog) | rst lineage |
| `PenWidthTableElem` | 8 | 11 | 0 | REQUIRED-class (element id 2 in every sample) | rst lineage |
| `ColorFillSchema` | 9 | 18 | 0 | REQUIRED-class | R9 |
| `FillPatternElem` | 9 | 257 | 5 | REQUIRED-class | R9 |
| `LinePatternElem` | 7 | 172 | 4 | REQUIRED-class | R9 |
| `Viewport` / `DBDrawing` / `Viewer` | 8 / 6 / 5 | 607 / 478 / 272 | 4 / 4 / 3 | REQUIRED-class (view frames) | R9 |
| `CurveElem` | 5 | 5,704 | 0 | present-everywhere, min tiny | R9 |
| `FamilyInstance` / `LinearDimString` | 1 / 1 | 5,638 / 3,822 | 0 | present-everywhere, min 1 (R9's pinned residue — likely OPTIONAL) | R9 |

G1's fourteen "present but short" classes (`count_shortfall`):
`CategoryElem` 7/284 (0.03), `FontElem` 3/96 (0.03), `GStyleElem` 94/1,533 (0.06),
`SketchPlane` 2/32, `TextNoteAttributes` 3/25, `DBViewType` 3/23 (0.13), `Viewport`
4/8, `Level` 2/4, `FillPatternElem` 5/9, `MaterialElem` 13/23, `LinePatternElem` 4/7,
`Viewer` 3/5, `DBDrawing` 4/6, `ConduitStandardType` 4/5.

### 2.3 Tier 3 — OPTIONAL by positive evidence (an accepted file lacks it)

**91 classes present in all six samples are RELEASED by an accepted reduction —
81 of them by R9 alone.** These are settled and must not be chased: the whole
placed-model / host-content stack (`SWall`, `Floor`, `RoofAttributes`,
`StackedWallType`, `SysPanelFamSym`/`SysMullionFamSym`, all stairs / railings /
rebar / MEP curve TYPES, `CustomElement`, `Hub`, `VarSketch`, `ReferencePoint`,
`ZoneElement` …), the annotation content (`IndependentTag`, `TextNote`,
`FilledRegion` — R4s/R5 too), schedules (`ScheduleInstance`, `PanelScheduleTemplate`,
`DBViewSchedule` — R5), and — notably — several TRACKER singletons the intuition
would call mandatory: **`HubsTracker`, `GCSTracker`, `InitialViewSettings`,
`PostedWarningElem`, `AllPlanTopologies` are all OPTIONAL** (R9 has none and
PASSES). Also OPTIONAL at the stream level: `RevitPreview4.0` (present only in the
rme/rac lineages; every rst-lineage certified file lacks it).

---

## 3. Streams and save units

### 3.1 Every accepted file has the same 12 streams — and so do the G-files
`BasicFileInfo`, `Contents`, `Formats/Latest`, `Global/ContentDocuments`,
`Global/DocumentIncrementTable`, `Global/ElemTable`, `Global/History`,
`Global/Latest`, `Global/PartitionTable`, `ProjectInformation`, `TransmissionData`
+ exactly one `Partitions/<N>` (dach: two, `Partitions/84`+`/85`). Stream PRESENCE
is not a differentiator for any of the six failures; the failures are inside the
streams.

### 3.2 Save-unit KINDS — the family-document floor
Every accepted file has 1 GUID-less unit (the host document; dach 2, one per
partition stream) + ≥ **52 GUID units = embedded content documents** (min set by
the whole rst lineage: `V18`, `R0_identity`, `R4s`, `R5`, `R9` all carry exactly
52; rme 305, rac 163, racadv 121, rstadv 180, dach 1,243). Host `Family` elements:
min 21 (R9: 8 document-less curtain-wall system families + 13 loadable
families with documents); the family-name intersection of the English-lineage
accepted files = **the 8 curtain-wall SYSTEM families** (`Rectangular / Circular /
L / V / Trapezoid / Quad Corner Mullion`, `System Panel`, `Empty System Panel`,
all document-less) **+ 5 annotation families with documents** (`M_Section Head -
Filled`, `- No Arrow`, `M_Section Tail - Filled`, `- Filled Horizontal`,
`M_View Title`); dach carries the localized equivalents (`Rechteckiger Pfosten`,
`Systemelement` …), so the requirement — if it is one — is the curtain-wall
system-family SET, not the English names. **All four G-files: 0 host families,
0 embedded units.** Whether the reader requires ≥1 embedded document is NOT
answerable from this corpus alone: no accepted file has zero, and both files that
reduced the count (R9b/R10b) confound it with Bug B — hence probe A3 below.

### 3.3 The coherence tuple — Bug B measured
`(ContentDocuments entries, GUID units, ADocument ContentTable records)`:

| file | reader | CD entries | GUID units | ContentTable | dangling content records | coherent |
|---|---|--:|--:|--:|--:|:--:|
| rst / R0 / R4s / R5 / R9 (accepted) | PASS | 52 | 52 | 52 | 0 | yes |
| every other accepted file | PASS | = units | = CT | = CD | 0 | yes |
| **R9b, R10b** | **FAIL** | **14** | **14** | **52** | **38** | **no** |
| G0 (rebuilt v2, sample ADocument carried) | (FAIL expected) | 0 | 0 | 52 | 52 | no |
| G1_candidate / G1a / G1b | FAIL | 0 | 0 | 0 | 0 | yes (coherent-EMPTY) |

`R9` (PASS) → `R9b` (FAIL) changes NOTHING in the host element inventory
(`census(R9).classes == census(R9b).classes`, asserted by
`tests/test_census.py::test_bug_b_is_below_the_element_layer`). The whole of
Bug B lives in the three streams above. And the framing hypothesis is retired:
R9b's / R10b's `Global/ContentDocuments` payloads parse and reassemble
**byte-exact** through the asset-forge SOLVED codec (14 entries, GUID-sorted, the
14-byte end record, the `u64 1` prefix) — the CD half of the "malformed splice"
already conforms to the solved grammar. What is left is the ADocument's **38
`ContentTable.m_ContentRecSet` records naming GUIDs that no longer exist**
(each record = `m_ContentKey.m_guidKey` + `m_author 'Autodesk Revit'` + history +
episode counts) and, secondarily, the `Partitions/21` unit splice itself.

---

## 4. The DBViewType default-family finding

* In every English-lineage accepted file (samples, reductions, V/H/M/T files) the
  91–102 `DBViewType`s carry **72 `m_famId` → `Family`** references — 9 view types
  per each of the **eight document-less curtain-wall SYSTEM families** (never an
  annotation head), plus `m_calloutAttrId → CalloutTag` 54, `m_sectionAttrId →
  SectionAttributes` 27, `m_elevatnAttrId → InteriorElevAttributes` 9,
  `m_pocheMatId → MaterialElem` 1 (rme/V-files add `m_defaultTemplateId → DBViewPlan`
  2). Zero dangling; every target exists; every `Family` target is document-less.
  (The reduction record's `Family ← DBViewType ×72` pin is these curtain families,
  not head families. The 12 annotation-head families are referenced only by their
  OWN family-scoped children — `CategoryElem`/`GStyleElem`/`FontElem`/text types
  with `m_famId` = the family — never from a view type or attribute.)
* **The accepted `dach` sample has 23 DBViewTypes with ZERO `m_famId` references**
  (10 callout / 4 section / 1 elevation attribute refs, 3 template refs). A view
  type that references NO default family is therefore an **accepted shape** — G1's
  three `DBViewType`s (`GEN 3D View / Floor Plan / Ceiling Plan`, all refs `-1`) are
  NOT the head-family kind of defect. The residual DBViewType concern is COUNT
  (3 vs the accepted floor of 23, dach) and the attribute companions G1 lacks
  entirely (`CalloutTag` min 4, `SectionAttributes` min 2, `InteriorElevAttributes`
  min 1, `ViewportAttributes` min 1 — all Tier 2 REQUIRED-class).

---

## 5. Top hypotheses and the single probe each needs

Each probe differs from a KNOWN-PASSING (or the failing) file by ONE class of
change so PASS/FAIL attributes cleanly; each must pass `tools/rvt_validate.py`.

### BUG A (G0 / G1 — constructed base) — ranked

1. **A1 — the settings-singleton / compiled-catalog CONSTELLATION is missing.**
   Evidence: 62 classes with an IDENTICAL count in all 32 accepted files are absent
   from every G-file (Tier 1: the 5 `Rbs*SettingsElem` + 3 `*SizesElem`,
   `HVACLoadSpaceTypeElem` 125, `HVACLoadBuildingTypeElem` 33, `RbsPipeConnection/
   MaterialType`, `KeynoteTable`, `AssemblyCodeTable`, `StructSettingsElem`,
   `AutoJoinTracker`, `WallJoinDefaultSetting`, `GraphicsCache`,
   `RbsDbViewSystemNavigator`, `ReconcileBrowserSettingsElem`, `MEP*Tracker` ×3,
   `NumberingSchema` 3, `RevisionNumberingSequence` 2, … full list Appendix A) plus
   the count-varying settings machinery `PenWidthTableElem` 8, `BrowserOrganization`
   11. The same gap is the ADocument's 67 empty `UniqueElementsTracking` slots.
   **Probe A1 = `G1_candidate` + the 62 invariant-class element groups transplanted
   from a sample (they are product-default machinery, count-identical everywhere),
   with the positional singleton slots + `ElementTrackingData` entries registered —
   ONE class of change (settings constellation) on the failing base.** The
   passing-side twin, if the reduction stream can build it: R11 = R9 further
   reduced to `{Tier-1 ∪ Tier-2 catalogs, keeper views, families}` only.
2. **A2 — the category / object-styles CATALOG is an order of magnitude short.**
   G1 has 94 `GStyleElem` / 7 `CategoryElem` / 3 `FontElem`; the accepted floor is
   1,533 / 284 / 96 (R9/R10b — the full built-in category catalog is what NO
   accepted reduction could drop; the reduction record calls it "format
   infrastructure"). **Probe A2 = `G1_candidate` + the full object-styles catalog
   only** (the extracted 1,074-category `object_styles.json` table → ~284
   sub-`CategoryElem` + ~1,533 `GStyleElem` + their `FontElem`s), nothing else
   changed. PASS → the catalog depth was the floor; then A1 becomes optional.
3. **A3 — ZERO family machinery** (0 host `Family`/`FamilySymbol`, 0 embedded
   units, 0 CD entries; accepted floor 21 / 17 / 52; the curtain-wall system-family
   octet is in every accepted file). Weakest of the three because no accepted file
   isolates it (dach's family-free view types + R10b's kept families argue both
   ways). **Probe A3 = `G1_candidate` + ONE coherent embedded family** (asset-forge
   L1–L5: our panelboard document + its `ContentDocuments` entry + save unit + host
   `Family`/`FamilySymbol` + one `ContentTable` record, all four registries
   coherent) — or the curtain-wall system-family octet (document-less, no L1–L3
   needed) as the cheaper variant.

Recommended order: **A2 then A1 as ONE combined "K-floor" build first** (both are
"catalog constellation the census says every project carries"), because they are
constructible today from data already in the tree, then A3. If the K-floor file
(G1 + catalogs + constellation, still zero families) PASSES, Bug A is closed and
families are optional; if it FAILS with the constellation complete, A3 is the last
rung.

### BUG B (R9b / R10b — the unit-removal reductions) — ranked

1. **B1 — 38 DANGLING content records in the ADocument `ContentTable`** (measured
   above: 52 records vs 14 documents). **Probe B1 = R9b + `ContentTable.m_ContentRecSet`
   purged to the 14 surviving GUID records** (the ADocument codec's
   `write_with_latest`; every other byte identical to R9b). PASS → Bug B was the
   stale content registry and the splice mechanics are sound. This is verdict #3's
   "registries still expect them" made exact — and it is a THIRD registry the
   genesis-2 candidate got right (its ContentTable IS empty; the candidate fails for
   Bug A instead).
2. **B2 — the `Partitions/21` unit splice** (38 units cut out: separators / unit
   counters / footers). No positive evidence either way; the census only proves the
   REMAINING structure walks clean. **Probe B2 = R9 with the 38 CD entries removed
   AND `ContentTable` purged to 14, but the partition stream UNTOUCHED** (the 38
   units left orphaned in `Partitions/21`, exactly as R9 already leaves the docs of
   its deleted families orphaned): PASS → the unit splice is the culprit; FAIL →
   orphaned units in the partition stream are themselves fatal (which R9's own
   PASS with 39 orphan documents makes unlikely — a further point for B1).
3. **B3 — `Global/ContentDocuments` framing: CLOSED, no probe needed.** R9b's and
   R10b's CD payloads reassemble byte-exact through the solved grammar (this
   session); the "splice predates the solved grammar" premise of verdict #4 is
   true of the code's age but not of its output for the CD stream.

---

## 6. What the census cannot say (honest limits)

* PASS-corpus minima are "smallest observed", not floors — 39 of them are just
  R9's residue. Only the 70 invariant classes are evidence-strong.
* No accepted file has < 52 embedded documents, < 21 families, or < 3,709
  elements; the census cannot prove any of those floors are 0. Bug A's ranking
  (A1/A2 before A3) rests on the strength of the Tier-1 evidence, not on a
  disproof of A3.
* The census is content-blind BELOW the class level except for the coherence
  tuple (it does not diff field values); a required class present with the wrong
  content is invisible here — that is the byte-comparator's / the reader's job.
* dach's localized inventory (German names, 353 classes, worksharing partitions)
  is what makes the intersection meaningful — it removes the "every accepted file
  descends from the same three templates" objection for the 149.

---

## 7. Reproduction

```
.venv/bin/python -m rvt.census samples/rstbasicsampleproject.rvt          # one file
.venv/bin/python -m rvt.census --certified                                # 38 files, ~15 s
.venv/bin/python -m rvt.census --certified --json /tmp/census.json         # + the full JSON
.venv/bin/python -m pytest tests/test_census.py -q                          # 12 passed
```

```python
from rvt.census import (census, run_certified, mandatory_set, missing_from,
                        rank_suspects, count_shortfall, stream_unit_matrix)
rep = run_certified()          # {'mandatory_set', 'suspects_strict', 'streams_units', 'censuses', ...}
g1  = census("experiments/genesis/G1_candidate.rvt")
missing_from(g1, rep["mandatory_set"])      # the 110 Bug-A classes
count_shortfall(g1, rep["mandatory_set"])   # the 14 short classes
```

---

## Appendix A — the full 149-class mandatory set (present in every accepted file)

Ordered by minimum count. `in G1` / `in R10b` = the class count in the failing
`G1_candidate.rvt` / `R10b.rvt` (0 = absent). Verdict: `REQUIRED (count
invariant 32/32)` = Tier 1; `REQUIRED-class (32/32, count varies)` = Tier 2 (the
class is in every accepted file; the minimum is R9's/dach's residue).

| class | in N/N passing | min | max | in G1 | in R10b | verdict | min set by |
|---|--:|--:|--:|--:|--:|---|---|
| `GStyleElem` | 32/32 | 1533 | 5596 | 94 | 1533 | REQUIRED-class (32/32, count varies) | R9 |
| `CategoryElem` | 32/32 | 284 | 4076 | 7 | 284 | REQUIRED-class (32/32, count varies) | R9 |
| `HVACLoadSpaceTypeElem` | 32/32 | 125 | 125 | 0 | 125 | REQUIRED (count invariant 32/32) | all |
| `FontElem` | 32/32 | 96 | 3315 | 3 | 96 | REQUIRED-class (32/32, count varies) | R9 |
| `HVACLoadBuildingTypeElem` | 32/32 | 33 | 33 | 0 | 33 | REQUIRED (count invariant 32/32) | all |
| `SketchPlane` | 32/32 | 32 | 1449 | 2 | 32 | REQUIRED-class (32/32, count varies) | R9 |
| `BuildingOperatingYearSchedule` | 32/32 | 25 | 27 | 0 | 27 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,racadvancedsampleproject+ |
| `HVACLoadScheduleElem` | 32/32 | 25 | 27 | 0 | 27 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,racadvancedsampleproject+ |
| `TextNoteAttributes` | 32/32 | 25 | 1155 | 3 | 25 | REQUIRED-class (32/32, count varies) | R9 |
| `DBViewType` | 32/32 | 23 | 102 | 3 | 91 | REQUIRED-class (32/32, count varies) | dach-sample-project |
| `MaterialElem` | 32/32 | 23 | 213 | 13 | 23 | REQUIRED-class (32/32, count varies) | R9 |
| `Family` | 32/32 | 21 | 284 | 0 | 21 | REQUIRED-class (32/32, count varies) | R9 |
| `FamilySurrogate` | 32/32 | 21 | 284 | 0 | 21 | REQUIRED-class (32/32, count varies) | R9 |
| `PropertySetElement` | 32/32 | 20 | 67 | 0 | 28 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,rmebasicsampleproject+ |
| `TagNoteAttributes` | 32/32 | 20 | 850 | 0 | 20 | REQUIRED-class (32/32, count varies) | R9 |
| `LeaderStyle` | 32/32 | 19 | 810 | 0 | 19 | REQUIRED-class (32/32, count varies) | R9 |
| `AppearanceAssetElem` | 32/32 | 18 | 265 | 0 | 18 | REQUIRED-class (32/32, count varies) | R9 |
| `ParamElemElectricalLoadClassification` | 32/32 | 18 | 126 | 0 | 0 | REQUIRED-class (32/32, count varies) | racadvancedsampleproject,M2_delete_cascade_rac |
| `FamSymSurrogate` | 32/32 | 17 | 411 | 0 | 17 | REQUIRED-class (32/32, count varies) | R9 |
| `FamilySymbol` | 32/32 | 17 | 1157 | 0 | 17 | REQUIRED-class (32/32, count varies) | R9 |
| `FilledRegionAttributes` | 32/32 | 16 | 762 | 0 | 16 | REQUIRED-class (32/32, count varies) | R9 |
| `ParamElemFamily` | 32/32 | 13 | 2353 | 0 | 13 | REQUIRED-class (32/32, count varies) | R9 |
| `DimensionStyle` | 32/32 | 12 | 24 | 0 | 12 | REQUIRED-class (32/32, count varies) | R9 |
| `BrowserOrganization` | 32/32 | 11 | 12 | 0 | 11 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `RbsPipeScheduleType` | 32/32 | 10 | 13 | 0 | 13 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,racbasicsampleproject+ |
| `ColorFillSchema` | 32/32 | 9 | 18 | 0 | 10 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject |
| `FillPatternElem` | 32/32 | 9 | 257 | 5 | 9 | REQUIRED-class (32/32, count varies) | R9 |
| `AreaTypeElem` | 32/32 | 8 | 16 | 0 | 8 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `LoadNatureElem` | 32/32 | 8 | 9 | 0 | 8 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `PenWidthTableElem` | 32/32 | 8 | 11 | 0 | 9 | REQUIRED-class (32/32, count varies) | dach-sample-project |
| `RbsPipeConnectionType` | 32/32 | 8 | 8 | 0 | 8 | REQUIRED (count invariant 32/32) | all |
| `Viewport` | 32/32 | 8 | 607 | 4 | 8 | REQUIRED-class (32/32, count varies) | R9 |
| `LinePatternElem` | 32/32 | 7 | 172 | 4 | 7 | REQUIRED-class (32/32, count varies) | R9 |
| `DBDrawing` | 32/32 | 6 | 478 | 4 | 6 | REQUIRED-class (32/32, count varies) | R9 |
| `ConduitStandardType` | 32/32 | 5 | 7 | 4 | 5 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,racadvancedsampleproject+ |
| `CurveElem` | 32/32 | 5 | 5704 | 0 | 5 | REQUIRED-class (32/32, count varies) | R9 |
| `LegendComponent` | 32/32 | 5 | 308 | 0 | 5 | REQUIRED-class (32/32, count varies) | R9 |
| `RbsPipeMaterialType` | 32/32 | 5 | 5 | 0 | 5 | REQUIRED (count invariant 32/32) | all |
| `Viewer` | 32/32 | 5 | 272 | 3 | 5 | REQUIRED-class (32/32, count varies) | R9 |
| `CalloutTag` | 32/32 | 4 | 11 | 0 | 9 | REQUIRED-class (32/32, count varies) | dach-sample-project |
| `Level` | 32/32 | 4 | 100 | 2 | 9 | REQUIRED-class (32/32, count varies) | rmebasicsampleproject,V23_electrical_room+ |
| `RbsWireMaterialType` | 32/32 | 4 | 8 | 0 | 4 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `RefPlane` | 32/32 | 4 | 462 | 0 | 21 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject |
| `SunAndShadowSettings` | 32/32 | 4 | 389 | 4 | 4 | REQUIRED-class (32/32, count varies) | R9 |
| `ElectricalDemandFactorDefinition` | 32/32 | 3 | 21 | 5 | 0 | REQUIRED-class (32/32, count varies) | racadvancedsampleproject,M2_delete_cascade_rac |
| `ElectricalLoadClassification` | 32/32 | 3 | 21 | 6 | 0 | REQUIRED-class (32/32, count varies) | racadvancedsampleproject,M2_delete_cascade_rac |
| `ExtentElem` | 32/32 | 3 | 378 | 3 | 3 | REQUIRED-class (32/32, count varies) | R9 |
| `Grid` | 32/32 | 3 | 27 | 0 | 3 | REQUIRED-class (32/32, count varies) | R9 |
| `ImageHolder` | 32/32 | 3 | 97 | 0 | 3 | REQUIRED-class (32/32, count varies) | rmebasicsampleproject,V23_electrical_room+ |
| `ImageSymbol` | 32/32 | 3 | 97 | 0 | 3 | REQUIRED-class (32/32, count varies) | rmebasicsampleproject,V23_electrical_room+ |
| `LoadCaseElem` | 32/32 | 3 | 11 | 0 | 8 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject |
| `NumberingSchema` | 32/32 | 3 | 3 | 0 | 3 | REQUIRED (count invariant 32/32) | all |
| `SunAnnotationElem` | 32/32 | 3 | 298 | 0 | 3 | REQUIRED-class (32/32, count varies) | R9 |
| `AreaMeasureElem` | 32/32 | 2 | 4 | 0 | 2 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `AreaSchemePlanTopologies` | 32/32 | 2 | 6 | 0 | 6 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,racadvancedsampleproject+ |
| `BasePoint` | 32/32 | 2 | 2 | 2 | 2 | REQUIRED (count invariant 32/32) | all |
| `DBViewPlan` | 32/32 | 2 | 170 | 2 | 2 | REQUIRED-class (32/32, count varies) | R9 |
| `GeoLocation` | 32/32 | 2 | 3 | 2 | 2 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `GeoSite` | 32/32 | 2 | 2 | 2 | 2 | REQUIRED (count invariant 32/32) | all |
| `ParamBinding` | 32/32 | 2 | 219 | 0 | 129 | REQUIRED-class (32/32, count varies) | racbasicsampleproject,V22_first_created_wall |
| `ParamElemExternal` | 32/32 | 2 | 466 | 0 | 14 | REQUIRED-class (32/32, count varies) | racadvancedsampleproject,M2_delete_cascade_rac |
| `ProjectPhase` | 32/32 | 2 | 3 | 2 | 2 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `RbsWireInsulationType` | 32/32 | 2 | 26 | 0 | 26 | REQUIRED-class (32/32, count varies) | rmebasicsampleproject,V23_electrical_room+ |
| `RevisionNumberingSequence` | 32/32 | 2 | 2 | 0 | 2 | REQUIRED (count invariant 32/32) | all |
| `SectionAttributes` | 32/32 | 2 | 12 | 0 | 10 | REQUIRED-class (32/32, count varies) | dach-sample-project |
| `ActiveGeoLocationTrackingElement` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AllProjectPhases` | 32/32 | 1 | 1 | 1 | 1 | REQUIRED (count invariant 32/32) | all |
| `AllProjectRevisions` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AnalyticalToPhysicalRelationManager` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AreaReportSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AreaSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AssemblyCodeTable` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AssemblyTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AutoCamSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `AutoJoinTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `BasicWallType` | 32/32 | 1 | 33 | 3 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `CableTraySettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `CableTraySizesElem` | 32/32 | 1 | 2 | 1 | 1 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `CircuitNamingTypeSetting` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ConduitSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ConduitSizesElem` | 32/32 | 1 | 2 | 1 | 1 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `CoordinateSystemDisplayElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `DBView3d` | 32/32 | 1 | 103 | 1 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `DBViewDrafting` | 32/32 | 1 | 22 | 0 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `DBViewProject` | 32/32 | 1 | 1 | 1 | 1 | REQUIRED (count invariant 32/32) | all |
| `DaylightSourceIdSet` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `DefaultDivideSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `Dwg2dExportUserSettingsData` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ElectricalSetting` | 32/32 | 1 | 1 | 1 | 1 | REQUIRED (count invariant 32/32) | all |
| `EnergyDataSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ExternalParamLock` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `FabricationServiceSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `FabricationSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `FabricationSettingsElement` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `FamilyInstance` | 32/32 | 1 | 5638 | 0 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `FloorAttributes` | 32/32 | 1 | 40 | 1 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `GraphicsCache` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `GridAttributes` | 32/32 | 1 | 3 | 0 | 1 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,racbasicsampleproject+ |
| `HalftoneUnderlaySettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `InteriorElevAttributes` | 32/32 | 1 | 11 | 0 | 9 | REQUIRED-class (32/32, count varies) | dach-sample-project |
| `KeynoteTable` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `KeynoteTagsOnSheetsTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `KeynotingSystem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `LayoutNodesTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `LevelAttributes` | 32/32 | 1 | 6 | 1 | 1 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `LightSchemeElement` | 32/32 | 1 | 96 | 1 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `LinearDimString` | 32/32 | 1 | 3822 | 0 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `MEPComponentTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `MEPHiddenLineSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `MEPNetworkDataElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `MEPNetworkTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `MEPSystemTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ModelClipBox` | 32/32 | 1 | 96 | 1 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `MultipleValuesIndicationSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ParamElemProject` | 32/32 | 1 | 13 | 0 | 0 | REQUIRED-class (32/32, count varies) | racbasicsampleproject,V22_first_created_wall |
| `PhaseFilterElem` | 32/32 | 1 | 14 | 5 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `PipeSegment` | 32/32 | 1 | 15 | 0 | 15 | REQUIRED-class (32/32, count varies) | R4s |
| `PrintSettings` | 32/32 | 1 | 10 | 0 | 3 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,racadvancedsampleproject+ |
| `ProjectCopySettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ProjectInfo` | 32/32 | 1 | 1 | 1 | 1 | REQUIRED (count invariant 32/32) | all |
| `ProjectRevision` | 32/32 | 1 | 2 | 0 | 1 | REQUIRED-class (32/32, count varies) | rstbasicsampleproject,rstadvancedsampleproject+ |
| `RbsDbViewSystemNavigator` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RbsDuctSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RbsDuctSizesElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RbsPipeSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RbsPipeSizesElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RbsWireSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RbsWireSizesElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RbsWireTemperatureRatingType` | 32/32 | 1 | 3 | 0 | 3 | REQUIRED-class (32/32, count varies) | rmebasicsampleproject,V23_electrical_room+ |
| `ReactionsUpToDateElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ReconcileBrowserSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `ReinforcementSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RevisionCloudsOnSheetsTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RouteAnalysisSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `RvtLinkInstanceAppearanceParentElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `SSEPointVisibilitySettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `STEPExportSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `SheetsInSheetCollectionTracker` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `SketchGridAppearanceParentElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `StructSettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `StructuralConnectionSettings` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `TrueNorth` | 32/32 | 1 | 1 | 1 | 1 | REQUIRED (count invariant 32/32) | all |
| `UnitsElem` | 32/32 | 1 | 1 | 1 | 1 | REQUIRED (count invariant 32/32) | all |
| `Viewer3d` | 32/32 | 1 | 96 | 1 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `ViewportAttributes` | 32/32 | 1 | 5 | 0 | 1 | REQUIRED-class (32/32, count varies) | R9 |
| `WallJoinDefaultSetting` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `WorksetVisibilitySettingsElem` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |
| `WorksharingViewModeSettings` | 32/32 | 1 | 2 | 0 | 2 | REQUIRED-class (32/32, count varies) | rstadvancedsampleproject,racadvancedsampleproject+ |
| `ZoneScheme` | 32/32 | 1 | 1 | 0 | 1 | REQUIRED (count invariant 32/32) | all |