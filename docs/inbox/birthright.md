# birthright — THE SUFFICIENCY PROBE + THE AUTHORED BIRTH (2026-08-05)

Stream: **birthright** (post-verdict-#43).  THE CONFIRMED LAW (genesis-audit
verdicts #43 + docs/inbox/rft-probes.md): Revit-BORN famdocs pass the
instance audit through our ENTIRE pipeline (T2a / TB0 / TB0r viewer-PASS);
our from-scratch famgen famdocs fail (T0).  THE FIX = birthright authoring:
famgen AUTHORS what a template birth provides — mined SHAPES re-authored as
our own constructions, ZERO donor bytes in anything shipped.

Tool: `tools/birthright_mine.py` (mine / t1v / build / diff / verify /
stage).  Module: `src/rvt/famgen/birthright.py` v2 (the author lanes + the
opt-in flag; the v1 surface and all 24 rft-probe tests unchanged).  Tests:
`tests/test_birthright.py` (19) + `tests/test_rft_probe.py` (24) — 43
passing.  Diff: `experiments/birthright/authored_vs_mined_diff.json`.

## STAGED (awaiting viewer) — batch 51

`experiments/acceptance/batch_51.json` — CTRL_G_ABPD_b51 FIRST, then
reading order:

1. **T1v** (DEV-ONLY, donor-embedding, quarantined) — the SUFFICIENCY
   probe: our PANELBOARD content (the B0 famdoc's 35 content elements:
   geometry forms, params/types, datums, views, connector — the U16 union
   axes) ADDED ALONGSIDE the born famdoc shell (the vendor
   `racbasicsamplefamily-2026.rfa` famdoc UNMODIFIED, 1,992 elements),
   registered in the BORN self-Family (absorbed indices continue from the
   born counter 3170+), famloaded onto G_ABPD + ONE uniform instance.
   **Add-alongside variant chosen** (charter option b): the ONE thing vs
   certified-PASS T2a is our content riding the born body — removal of the
   vendor furniture would have added a second variable.  2,027 elements,
   md5 `05928639…`, built 4.0 s.
2. **BX_birth** (ZERO donor bytes) — the B0 recipe verbatim (G_ABPD + ONE
   famgen panelboard + ONE instance; bisect_instance_bug chain + demo
   placement under `famload_hostfix.corpus_symbol_form`) with the famdoc
   authored THROUGH `birthright.enabled(...)`: our 41-element famdoc + the
   1,683-element AUTHORED birth set = a 1,724-record unit (counter 1724,
   roster-coupled).  md5 `234ee8a5…`, built 3.3 s.
3. **DEMO_250v_room_v7** (ZERO donor bytes) — the user's exact prompt
   ("an electrical room rated for 250V with 6 panels") end-to-end through
   `rvt.frontdoor.run` with birthright enabled: 6 families × 1,724-record
   units, 6 placed instances, 7 units total all blob-carrying.  Front door
   status PROOF-ONLY (self-checks PASS); walls: the current intent grammar
   derives 0 walls from this prompt (measured; v3's 4-wall shape is not the
   current front door's).  md5 `5c18cb7d…`, built 34.8 s.

Every probe: validator **0 errors** (0 unexpected), coherent four-registry
census, survivor law OK, every unit blob-carrying with the added units'
blobs byte-matching OUR deterministic nonce (machine-verified), instances
dangling-free/registered, corpus-lawful symbol form on every PP- symbol
(BX/DEMO), product `FamilyInstanceConnectorManager` (BX).

### Decision table (probes.json `reading_the_matrix`)

- **T1v PASS + BX_birth PASS + v7 PASS** ⇒ THE CAMPAIGN CLOSES: the birth
  set is sufficient AND our authored birth reproduces it — promote
  birthright to the famgen emission default next session.
- **T1v PASS + BX_birth FAIL** ⇒ the authored birth misses something the
  born shell has.  The FINITE GAP LIST is already on disk:
  `mining_report.json` `dropped` (173 elements with per-element blocking
  refs) + `count_shortfall_overlapping_classes` (see §Mining) +
  `authored_vs_mined_diff.json` (0 mismatches today) — close it entry by
  entry.
- **T1v FAIL** ⇒ our content INTERACTS with a standalone-born shell
  (SUB_ALL accepted the same union in a project-embedded donor body) —
  bisect our axes inside the born shell before trusting any authored birth.
- **BX_birth PASS + v7 FAIL** ⇒ multi-unit propagation is the remaining
  axis; bisect panel count.

## THE MINER — `template_birth.json` (v2 contract, 4.2 MB)

`tools/birthright_mine.py mine` reads the born specimen through the proven
schema-TYPED .rfa reader (rft_probe's small-id-safe machinery) and emits
`experiments/birthright/template_birth.json` (v2; `read_birth_spec` parses
it, v1 specs unchanged).  Source: the vendor standalone .rfa, sha256
`00425e9d0766c3d5…` — DEV/PROOF-ONLY MINING MATERIAL; the spec carries
adoptable laws/shapes as plain JSON, references as symbolic
`{"__eid__": born_id}` / `{"__role__": …}`, identity/content as
`{"__author__": …}` slots.  **Zero donor identity in the spec** (test-
enforced: no GUID values, no user paths, no vendor tokens; the secret-style
naming STEMS ride only inside `shape_stem` slots, digits stripped).

**The birth partition** (rule recorded in the spec): birth = born elements
of classes famgen NEVER authors (ours_count == 0), closed under
references — an element whose refs/owner reach outside {birth set + frame
roles + self-Family} is DROPPED with its blocking refs recorded.
Result: **1,683 of 1,856 candidates** in 47 classes — GStyleElem 1,459
(the full built-in style catalog: 1,407 family-owned rows + 52
CategoryElem-owned locals), CategoryElem 52, FontElem 21, MaterialElem 24,
AppearanceAssetElem 27, LinePatternElem 14, FillPatternElem 7,
DimensionStyle 9 / LeaderStyle 7 / text-tag-spot-section attrs, LoadNature
8 + LoadCase 8, StructConnectionType 5, ElectricalDemandFactorDefinition,
PenWidthTableElem, KeynoteTable, AssemblyCodeTable, BrowserOrganization 2,
the settings singletons.  **173 dropped, all principled**: the nested
Level-Head mini-famdoc constellation drops as a unit (its own
PenWidthTableElem/TrueNorth/BaseLevelTracker/… reference the nested Family
5701), the vendor's furniture annotation content (LinearDimString 32,
Alignment 7, RadialDim 7, TagNote, FilledRegion…), view-coupled elements
(SketchGrid 7, ModelClipBox), and the 36
ParamElemElectricalLoadClassification (blocked by ElectricalLoadClassification
being an overlapping class — ours authors one).  Count-shortfall on
overlapping classes (recorded, NOT topped up in v1): DBViewType 18,
SketchPlane 12, RefPlane 7, Viewer 6, ExtentElem 6, CurveElem 27 (vendor
geometry), ElectricalLoadClassification 5, … — the first places to look on
a BX_birth FAIL.

**Adoption census** (birth elements): 67,513 scalars adopted, 10,886
strings adopted (≤24 chars, `autodesk.*`/`revit.*` vocabulary, schema
class names, `ptr_class`/`classref` always), 9,446 references symbolic,
**36 GUIDs + 300 strings authored** (Material/Keynote/AssemblyCode GUIDs;
AssemblyCodeTable's 285 Uniformat prose descriptions + the vendor's
OneDrive paths + 8 secret-style name tokens + 1 long material name).

**Also mined**: the blank-pair type table (4 pairs, names
`[' ', '0610 x 0160mm', '0762 x 0762mm', '0610 x 0915mm']`, m_idx 2 — the
blank current-values pair FIRST, current = a REAL type); the self-Family
residue (87 adoptable fields after the recorded exclusion policy — product
identity, roster-derived registries, machinery pointers, our-param-space
lists stay OURS); per-element absorbed indices (the template's index
HISTORY: sparse, max 3169 over 1,881 pairs, next = max + 1); the ownership
topology (born self-Family OWNS the frame; our writer left 10 classes
top-level: UnitsElem, DBViewProject, DBViewPlan, DBViewType, Level,
LevelAttributes, RefPlane, ExtentElem, ParamElemFamily,
ElectricalLoadClassification).

### The 12 separators' BORN-side values — and where they CORRECT the priors

The layout-law separators were mined from PROJECT-EMBEDDED donors
(SUB_ALL/B7).  The genuinely-BORN standalone says otherwise on several
axes (recorded in `separators_born`):

| separator | project-donor prior | BORN standalone (this specimen) |
|---|---|---|
| cell groups | materials group present, order materials-first | **constraints, materials, dimensions, identityData** (materials present, NOT first; NO dup identity key) |
| hdr deletion prefix | `[category, -1005500, -1001205, …]` | **`[-1154647, -1001205]`** — NO category id |
| m_refTypeIds | `[4]` | **`[]` (empty — ours was already lawful)** |
| absorbed index | sparse 3165 | sparse, next==max+1 (3170) — the LAW is the history gap, not the constant |
| partType / category | -1 / structural | 0 / furniture (self identity — stays OURS: 14 / electrical equipment) |
| type table | 5 pairs idx 1 | **4 pairs idx 2, blank-pair-first** (the blank-first LAW confirmed standalone) |
| predefinedLimitIdx | 1963 | **35 (== our own default)** |
| locked | [-1001205, dims] | [-1001205, 3 dim params] (same shape) |

## THE AUTHOR LANES — `rvt.famgen.birthright` v2 (opt-in)

`apply_birthright` detects a v2 spec and routes to `apply_birthright_v2`:

- **roster** — `author_birth_block`: every mined birth element CONSTRUCTED
  as our SkelElement (new ids in our document's space, references remapped
  through the id map / frame roles, identity authored: uuid5-deterministic
  GUIDs from OUR family identity, stem+ordinal names, empty blobs).
- **topology** — our top-level frame elements flipped to self-Family
  ownership per the mined flip classes (24 elements on the B0 famdoc).
- **types** — the blank-pair-first table (blank ' ' current-values pair
  inserted, current → the real type), idempotent.
- **fields** — after ONE re-finalize (the chain re-derives table/current/
  cell/locked/index over the full roster): the self-Family residue set
  (on B0 exactly 8 fields differ: `m_eRenderModelType` 0→3, `m_isVertical`
  F→T, `m_bIsSavable` T→F, `m_bShared` F→T, `m_enableCuttingInViews` T→F,
  `m_defaultHostThickness`/`m_defaultHeightAboveLevel` 0→-1e+30,
  `m_elevationFixed` F→T), the deletion prefix `[-1154647, -1001205]`
  prepended, and the absorbed-index HISTORY law (birth elements keep their
  mined indices; our elements continue above the born max; next = max+1 —
  exactly how T1v's registration into the real born shell behaved).

**The opt-in famgen flag**: `with birthright.enabled(spec):` patches the
factory constructors (catprobe precedent — no shared famgen file edited);
every product built inside is born with the authored birth set, and each
application is MACHINE-DIFFED against the mined spec — a mismatch FAILS
the build (never silent drift).

## THE AUTHORED-VS-MINED DIFF (the deliverable)

`experiments/birthright/authored_vs_mined_diff.json` — equality law:
field-model equality MODULO IDENTITY.  On the B0 famdoc: **78,399 fields
byte-equal, 9,446 references equal through the id map, 336 identity slots
authored fresh, 0 mismatches**, over all 1,683 elements; the augmented
1,724-element document round-trip-encodes with **zero failures**.  The
same verify ran inside every BX_birth / DEMO v7 factory application (12
applications, all ok) — `birthright_verified` is a staged gate.

## ZERO-DONOR PROOF CHAIN (shipped probes)

1. Spec-level: no GUID values / vendor identity strings in the spec
   (test-enforced, `tests/test_birthright.py::TestMinedSpec`).
2. Element-level: `birth_verify` — identity slots are AUTHORED values.
3. File-level: the demo's stage-F standalone .rfa (same product + birth
   set) scans **PROVENANCE-CLEAN** ("zero donor ADocument content bytes,
   zero donor element-id references, zero employee paths/usernames").
4. Stream-level: a needle scan of BX_birth/DEMO v7 finds donor identity
   ONLY in `ProjectInformation`/`TransmissionData` — and those hits
   **pre-exist byte-for-byte in the certified G_ABPD base itself** (same
   in B0.rvt; verified this session).  ⇒ FINDING for the orchestrator /
   compose stream: **G_ABPD carries an Autodesk username in
   BasicFileInfo, Global/DocumentIncrementTable, ProjectInformation and
   TransmissionData** — inherited by every probe built on it (including
   certified-PASS controls).  Not introduced by, and not fixable from,
   this stream.

## DEVIATIONS / NOTES (declared)

- The born specimen is the vendor STANDALONE .rfa (the only born specimen
  on hand) — a FURNITURE family, so the birth set is the furniture
  template's; category/partType/omniclass/work-plane/identity stay OURS by
  the recorded exclusion policy.  When a real `.rft` lands, `mine` re-runs
  unchanged on it (the electrical template's birth set would replace this
  one; `rft_probe poll`'s T3 path stays wired to
  `experiments/rft/template_birth.json`, which this stream does NOT write —
  that file belongs to the acquire stream).
- `m_bShared` True is adopted from the specimen (it is a shared family);
  flagged for scrutiny if BX_birth fails.
- v1 birth-partition line: overlapping classes (famgen authors ≥1) are
  never topped up — the shortfall list is the recorded gap.

## BRANCH STATE

- Working tree only (no git repo).  Territory files written:
  `tools/birthright_mine.py` (new), `src/rvt/famgen/birthright.py`
  (v2 lanes appended; v1 surface unchanged), `tests/test_birthright.py`
  (new, 19 tests), `docs/inbox/birthright.md` (this record),
  `experiments/birthright/**` (template_birth.json 4.2 MB,
  mining_report.json, authored_vs_mined_diff.json, T1v.rvt, BX_birth.rvt,
  DEMO_250v_room_v7.rvt, probes.json, accounting.json, _build/),
  staging copies + manifest `experiments/acceptance/batch_51.json`
  (CTRL_G_ABPD_b51 + the three probes; md5-verified).
- Tests: `tests/test_birthright.py` 19 passed + `tests/test_rft_probe.py`
  24 passed (0.25 s together).  NO full-suite run (charter).
- T1v embeds the vendor famdoc: DEV/PROOF-ONLY, quarantined under
  experiments/.  BX_birth + DEMO v7: zero donor bytes (proof chain above).
- NEXT (any session): after the viewer verdicts land for batch 51, read
  them in order T1v → BX_birth → DEMO v7 against the decision table above
  (`experiments/birthright/probes.json` `reading_the_matrix`).  On
  BX_birth FAIL: the gap list = mining_report `dropped` +
  `count_shortfall_overlapping_classes` + the diff.  On all-PASS: promote
  `birthright.enabled` into the famgen emission default (a one-line opt-in
  at the product constructors' call sites) + rebuild acceptance.
