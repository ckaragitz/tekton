# GENESIS 2025 — CONSTRUCTOR PORTABILITY + THE Y2025 SUBSTITUTION LADDER (G25-3 + G25-4)

Stream: **genesis-2025-port** (2026-08-04).  Charter: (1) VERIFY the
constructor-portability table of `docs/writer/genesis-2025-plan.md` §5
against reality (schema-directed, each file's own schema); (2) implement
the confirmed field maps as a wrapper layer — `rvt.genesis.port2025` —
over the UNTOUCHED 2026 constructors, and re-mine the 2025-specific format
constants; (3) build the Y2025 in-place substitution ladder on the
reduce2025 stream's `B2025_K4`; (4) stage rungs + probes.json for the
viewer session.

**DONE conditions met: the CONFIRMED portability table is frozen (with
four corrections to the plan — real deltas it missed); the field maps are
implemented, hook-tested and byte-exact under the 2025 schema; the WHOLE
Y2025 ladder (Y1..Y9 + Y_cat + the Yn census) is BUILT and staged — every
rung validator-0-errors, byte-delta assertion holding, ADocument +
ElemTable byte-identical per rung.  NOTHING is viewer-certified: the
viewer session is signed out, every certification is PENDING and marked so
in probes.json.**

Deliverables:

1. `src/rvt/genesis/port2025.py` — the portability layer (verdict differ,
   mined 2025 constants, the `adapt()` /`adapt_record()` field-map engine,
   2025 miners, selftest CLI)
2. `experiments/genesis2025/subst/portability-2025.json` — the CONFIRMED
   table (frozen; re-derivable via `--verify`)
3. `experiments/genesis2025/subst/builtin_category_enum_2025.json` +
   `builtin_style_profile_2025.json` — the 2025-mined catalog constants
4. `experiments/genesis2025/subst/run_ladder2025.py` + the staged rungs
   `Y1..Y9, Y_cat (.rvt+.json)`, `Yn.json`, `CTRL_B2025_K4_base.rvt`,
   `probes.json`
5. `tests/test_port2025.py` — 19 tests, all green
6. this record

---

## 1. VERIFICATION — the confirmed portability table (and what the plan got wrong)

Method = the plan's §6, re-run and frozen: harvest every CODE-position
class literal from `src/rvt/genesis/*.py` (326 names; docstrings skipped),
EXPAND with every base class on their chains (403 classes — the expansion
is what caught the plan's misses), then per class compare 2026 pin vs the
`rvt.versions.schema_2025` pin: own-field signatures `(name, kind, flags,
count, type_NAME, extra, element)`, flattened parent-first chain layout,
class versions.  Result (`portability-2025.json`):

| verdict | classes | notes |
|---|--:|---|
| IDENTICAL | 361 | incl. the entire machinery layer (re-proven: ADocument, Element, Symbol, ElementHeader, GElement, SerializedDummy, ElemTable/ElemRec, History, DIT, PartitionTable) |
| LAYOUT-DELTA | 32 | the plan's 17 families **+ the four misses below** + harvest superset rows (`Family`, `Section` — name-collision literals, not constructed; recorded with provenance) |
| MISSING-2025 | 8 | the conductor catalog: `CustomElement`, `NamingCell`, 4× `RbsConductor*` **+ their bases `CustomElementData`, `ElectricalCustomElementData`** |
| VERSION-ONLY | 2 | `DataStorage` v3→0, `Rebar` v57→56 — free (records carry no version; it lives in the schema stream we ship pinned) |

**CONFIRMED exactly as planned:** the 6 missing conductor classes; the
GeomStep `m_oExtraDatas`→`m_oExtraData` rename (5 GStep constructors);
`RbsWireSettingsElem`'s three 2025-only doubles **0.02 / 0.03 /
303.15000000000003 K** (re-decoded independently from the 2025 **rst**
sample elem 102129 — same values the plan read off the rme sample);
`NumberingSchema` rework; `BrowserOrganization` sortParameter→sortParamId;
`ModelGraphicsStyle`/`ViewDisplayMgr` GDI flags (False in 2/2 and 85/85
decoded 2025 specimens); the 1-field drops (AssemblyCodeTable,
KeynoteTable `m_hasUserCustomizedKeynote`, StructSettingsElem,
RbsWireSizesElem `m_bInitialized`); RbsWireSizesElem map order free under
schema-directed encode.

**FOUR REAL LAYOUT-DELTAS THE PLAN'S §5a TABLE MISSED** (all verified
field-level, all in classes genesis constructs):

1. **`DBView`** — 2026-only own field `m_viewPositionId` (ElementId).
   DBView is the BASE of every view class the skeleton constructs
   (DBView3d, DBViewPlan, DBViewProject, DBViewDrafting,
   RbsDbViewSystemNavigator) — the plan listed the view constellations
   under "185 port AS-IS".  Disposition: dropped for 2025 (skeleton writes
   -1 anyway); handled by the generic walk.
2. **`DBViewDrafting`** — additionally 2026-only `m_sheetTitleBlockId`.
3. **`Viewport` v13→10** — 2026-only `m_viewPosition` (XYZ) and
   `m_viewAnchor` (int); skeleton writes zeros; dropped.
4. **`BrowserOrganizationTracking` v6→5** (ADocument registry class, not
   an element — relevant to the composer/assembler path, NOT written by an
   in-place rung): 2026's map `m_currentBrOrgTypeToBrOrgMap`
   [(tree-type, org-id)] becomes THREE 2025 ElementId fields; hook splits
   by the tree codes (0 views / 1 sheets / 3 schedules; code 4 has no 2025
   field and is dropped).

**VALUE corrections mined from the 2025 corpus** (the plan's guesses vs
the decoded truth):

* `GeomTable` extra ints: corpus default is **(-1, -1)** — 5,620 of 5,637
  decoded 2025-rst GeomTables — NOT the plan's guessed 0/0.
* `ReinforcementSettings.m_numberVaryingLengthRebarsIndividually`: sample
  default **True** (rst 137426), not the blank False.
* `RbsWireType.m_strMaxConductorSize`: the sample stores the bare size
  label (**'2000'**), not "1000 kcmil"; our adapter resolves the LABEL of
  the conductor-size cell the 2026 record references ('500'/'750' for the
  house wire types), falling back to the mined label.
* `NumberingSchema` 2025 oracle fully decoded (rst 1218729 / 1218730 /
  1457391): `m_oPartitionDescriptionCreator` =
  `ParameterBasedPartitionDescriptionCreator{m_ccda{weakref 1},
  m_partitionParameterId}` , `m_minimumNumberOfDigits` 1, `schemaTypeGuid`
  per scope category (`-2009000` e0bc59cf…, `-2009060` 396c2ee8…,
  `-2009016` f90085e5…), `m_isMatchingEnabled` True.
* Pen table: the six model scale breakpoints **[10, 20, 50, 100, 200,
  500]**, 16 pens, persp/draft -1 — **IDENTICAL in 2025** (mined from all
  three 2025 basics; the 2026 constant HOLDS, no port needed).

## 2. THE FIELD MAPS — `rvt.genesis.port2025` (wrapper; 2026 constructors untouched)

`adapt(class_name, obj_2026) -> obj_2025` walks the TARGET 2025 chain
field-by-field: carry same-name fields (recursively adapting nested
owned/inline values — pointer tokens, weak refs, backrefs, fixed arrays,
containers, classrefs re-verified against the 2025 map), synthesize the
2025 schema-blank for fields the 2026 object lacks, apply the per-class
HOOKS (keyed by DECLARING class + field, so inheritance and nesting are
covered uniformly) where blank is not the corpus value.  2026-only fields
disappear by construction.  `adapt_record()` produces a `PortedRecord`
(2025 class ordinals, adapted seq-101/102/103 bodies) and raises
`Missing2025` for the conductor catalog — those constructors emit nothing
on a 2025 build (their 2025 representation IS the wire type's string
field).

Round-trip gate: every adapted object must encode→decode→re-encode
BYTE-EXACT under the 2025 schema.  `--selftest` battery: 13 constructor
records (wall type incl. the GeomStep rename, material, patterns incl. the
GeomTable hook, floor, wire type, NumberingSchema, pen table, browser org,
struct settings, keynote table, wire settings, reinforcement settings) —
ALL clean + byte-exact.  Corpus-shape parity: adapted key sets equal the
decoded 2025 sample's key sets per class (tested).

2025 miners re-run (charter item "the fixer's per-KEY census tools"):

* **category enum 2025**: 1,068 categories (331 cuttable), identical
  across the three 2025 basics; vs 2026's 1,074 — 7 categories are
  2026-only, 1 is 2025-only; cuttability identical on the shared set.
* **per-key style profile 2025**: 1,399 (category, style-type) keys over
  4,197 rows; **1,394 keys carry the same header flag word as 2026, 4
  differ** (`-2000710..713:1` = 0x400200e→0x400201e) — the Y6 rung was
  built with the 2025 profile and the emitted rows carry the 2025 values
  (verified in Y6.rvt, all 4 keys).

## 3. THE Y2025 LADDER — built, every rung VALID, staged

Base: **`experiments/genesis2025/B2025_K4.rvt`** — the reduce2025 stream's
family-free 2025 base (sha256 276be333…, 3,333 host elements, 1/0/0/0
four-registry coherent; lineage in `docs/inbox/genesis-2025-reduce.md`).
**Viewer certification PENDING** — no Revit-2025 file has ever been
uploaded; the ladder was built with `--allow-uncertified`, recorded here
and in every report + probes.json.  The batch law still holds: the base is
staged as the batch control (`CTRL_B2025_K4_base.rvt`, md5-identical), and
round 1's control answers "does the viewer accept 2025 uploads at all"
(plan §7 risk #1) before any rung verdict is read.

Runner: `experiments/genesis2025/subst/run_ladder2025.py` — the certified
v3 ladder (`tools/genesis_substitute_v3.py`) IMPORTED and re-pointed, with
a process context that (a) binds the 2025 framing ordinals
(`rvt.versions.reading`), (b) swaps the per-release default codecs to the
2025 pin for the run (`rvt.adocument._DECODER`,
`rvt.encode._DEFAULT_ENCODER`, the lazy `ObjectDecoder` in
`rvt.regadd`/`rvt.regdiff`), (c) redirects the catalog's enum/profile
loaders to the 2025-mined tables, (d) wraps `build_for` so every X-builder
record passes through `port2025.adapt_record`, and (e) patches the
re-blocker's own framing tags (§4 finding).  All swaps restore on exit;
nothing leaks into the 2026 creation path.

The ladder (all on B2025_K4, cumulative; 29.6 s total):

| rung | landed | changed | validator | byte-delta assertion | ADoc/ET identical | bytes |
|---|--:|--:|---|---|---|--:|
| Y1 pen table | 1 | 1 | VALID 0E/2W | holds | yes/yes | 851,968 |
| Y2 browser+navigator | 12 | 9 | VALID 0E/2W | holds | yes/yes | 851,968 |
| Y3 struct/join/keynote | 5 | 2 | VALID 0E/2W | holds | yes/yes | 778,240 |
| Y4 MEP settings+sizes | 8 | 8 | VALID 0E/2W | holds | yes/yes | 774,144 |
| Y5 remaining settings | 51 | 11 | VALID 0E/2W | holds | yes/yes | 774,144 |
| Y6 GStyle catalog | 1,165 | 1,165 | VALID 0E/2W | holds | yes/yes | 770,048 |
| Y7 palette | 22 | 22 | VALID 0E/2W | holds | yes/yes | 765,952 |
| Y8 datum+identity | 16 | 16 | VALID 0E/2W | holds | yes/yes | 761,856 |
| Y9 view layer | 46 | 36 | VALID 0E/2W | holds | yes/yes | 761,856 |
| Y_cat (single-change) | 1,165 | 1,165 | VALID 0E/2W | holds | yes/yes | 851,968 |

Per rung: `rvt.regadd.substitute_elements` in place (object record only),
`Global/Latest` + `Global/ElemTable` byte-identical to the parent
(asserted), no id added/removed, per-seq order identical, registration
diff sample identical, four-registry coherence 1/0/0/0, retarget
self-check (encode→decode→re-encode under the 2025 schema inside the live
document session) **0 failures across all 2,491 landed records**.
Port2025 adaptation is stamped in every report's build notes; **0 records
dropped as 2026-only** — no ladder rung constructs the conductor catalog
(the wire TYPES that reference it live in the residue, and their 2025 form
is the string field).

Yn census (Y9): **1,326 landed ours** (Y6 1,165 / Y5 51 / Y9 46 / Y7 22 /
Y8 16 / Y2 12 / Y4 8 / Y3 5 / Y1 1) vs **2,007 residue** in 73 classes
(same bucket structure as the 2026 census: definitions 791, X6b gap
286+209, product data 212, no-constructor 163, curtain systems 97, …).
Ours-not-landed: Y6 234 catalog rows (2025 enum rows the base lacks — add
path), Y9 12, Y8 4, Y3 1.

Emitted-file spot-proofs (decoded back through the full 2025 read stack):
`Y4.rvt`'s RbsWireSettingsElem carries 0.02/0.03/303.15…3 and its
RbsWireSizesElem has NO `m_bInitialized` with the 2025 map order;
`Y2.rvt`'s ten substituted BrowserOrganizations all carry `m_sortParamId`
(no `m_sortParameter`); `Y6.rvt`'s four 2025-profile-differing keys carry
the 2025 flag word.

## 4. FINDINGS for other territories (exact, not applied — wraps in my runner)

The plan §7 predicted "each tool's first 2025 run should be watched for a
baked 0x0f28-era literal".  Two found:

1. **`src/rvt/reduce.py:59`** — `BLOCK_TAG = 0x0F28` module constant +
   `from .writer import BLOCK_TRL_TAG`; `NewBlock.frame()` packs both, so
   `rvt.versions.reading` (which patches `rvt.partitions` only) does not
   reach the WRITER side: Y1's first emission failed with `walker errors
   after re-block: unexpected tag 0x0f28 at 18`.  My runner swaps
   `reduce.BLOCK_TAG`/`reduce.BLOCK_TRL_TAG` from the active ordinals.
   Proposed proper fix: re-export both from `rvt.partitions` (or resolve
   via `rvt.versions`) so `reading()` covers the writer;
   the reduce2025 stream's driver hit the same class of issue (its
   `context_2025` §4) — one shared patch set should land in `rvt.versions`.
2. **`tools/genesis_assemble.py` `run_ledger_v2`** — raises
   `ValueError('unexpected Partitions header: v=9 cls=0x3a3')` on a 2025
   file (a baked 2026 ContentMarker ordinal 0x03a3; 2025 is 0x0391).  Only
   advisory (the Yn ledger is skipped and says so); fix = the same
   by-name resolution.
3. **Default-codec singletons are 2026-baked** (by design, documented
   here for the eventual `use_schema()` context of plan §4):
   `rvt.adocument.get_decoder()`, `rvt.encode.encode_record`'s
   `_DEFAULT_ENCODER`, `rvt.regadd.EditImage.decoder`,
   `rvt.regdiff.RegDoc._dec`.  All are constructor-injectable already; the
   runner's context swaps them process-locally.  When G25-3's
   `rvt.genesis.types._S(schema=)` retarget lands, the same context should
   move into `rvt.versions` as e.g. `versions.creating(2025)`.

## 5. WHAT THE VIEWER SESSION MUST DO (the staged batch)

`experiments/genesis2025/subst/probes.json` — 11 entries,
bisection-first order (Y9 → Y6 → Y_pen(=Y1) → Y_cat → Y1..Y8), each
naming its base, parent, the ONE thing it tests, and PENDING status.
Upload with `CTRL_B2025_K4_base.rvt`.  Control FAIL ⇒ batch VOID.  Y9
PASS ⇒ every ported constructor loads at Autodesk's 2025 registrations and
G25-4 closes; then compose (`tools/genesis_compose.py` under the same 2025
context) → `G_ABPD_2025` → G25-5.

**The standing-controls gate was RUN and it REFUSES these rungs today —
correctly** (`tools/probe_batch.py check Y9.rvt Y6.rvt Y1.rvt --manifest
experiments/genesis2025/subst/probes.json`): every rung's declared base
`B2025_K4` is not yet in `viewer-certified.json`, and the gate demands the
base be certified first.  That is the K1 law working, not an obstacle:
the reduce2025 stream's **batch_17** (untouched-2025-sample control →
R5_2025 → R9_2025 → K3_2025 → B2025_K4, every entry a candidate-base) is
the batch that certifies the base.  ORCHESTRATOR SEQUENCE: (1) upload
batch_17; (2) on B2025_K4 = certified, stage THIS ladder through the gate —
`tools/probe_batch.py stage experiments/genesis2025/subst/Y*.rvt
--manifest experiments/genesis2025/subst/probes.json` — which then passes
and adds a certified-2026 control (the gate proposed
`experiments/render/RSOLID_walls_A_solid.rvt`); uploading BOTH controls
(certified-2026 + the 2025 sample) separates "oracle broken" from "the
viewer rejects 2025" from "this rung's content rejected"; (3) read
verdicts via `probe_batch.py verdicts`.

## Open questions carried forward

* Does the Autodesk viewer accept 2025 uploads at all?  (Round-1 control —
  blocks nothing now, decides everything later.)
* The composer + `tools/genesis_compose.py` first 2025 run (same baked-
  literal watch; not exercised this stream — compose needs certified
  rungs first per the batch law).
* `BrowserOrganizationTracking`'s three-field 2025 form matters only to
  the ASSEMBLER path (G0-style, ADocument-authoring) — the in-place ladder
  never writes the ADocument.  The hook is implemented and tested at the
  adapt() level regardless.

---

## SUITE RESULT (final, 2026-08-04)

`.venv/bin/python -m pytest -q --continue-on-collection-errors` from the
repo root: see the BRANCH STATE numbers below (run completed after the
ladder; `tests/test_port2025.py` 19/19 green in-suite and standalone).

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — no git branch work (repo has no
  commits; integration is the orchestrator's).
* NEW (this stream's territory):
  * `src/rvt/genesis/port2025.py`
  * `tests/test_port2025.py` (19 green)
  * `experiments/genesis2025/subst/` — `run_ladder2025.py`,
    `portability-2025.json`, `builtin_category_enum_2025.json`,
    `builtin_style_profile_2025.json`, `Y1..Y9.rvt+.json`,
    `Y_cat.rvt+.json`, `Yn.json`, `CTRL_B2025_K4_base.rvt`, `probes.json`
  * this record
* Touched OUTSIDE territory: **NOTHING** — no existing `src/rvt/**`,
  tools, or tests edited; every cross-release adjustment is a
  process-local wrap inside `run_ladder2025.py` (restored on exit), and
  the proper fixes are PROPOSED in §4.
* DONE check: confirmed portability table ✓ (frozen, with corrections);
  field maps ✓ (hooked, round-trip-gated, corpus-shape-checked); the
  deepest buildable Y2025 ladder ✓ (the WHOLE ladder — deeper than
  "deepest buildable" needed — staged with control + probes.json, every
  certification honestly PENDING).  STOP at READY: nothing uploaded,
  nothing claimed certified.
