# GENESIS AUDIT — completeness + provenance skeptic

Stream: **genesis-auditor** (2026-08-03). Subject: `experiments/genesis/G0.rvt`
(the assembler's genesis candidate) and the instrument that certifies it,
`src/rvt/provenance.py` / `tools/provenance.py`. Companion inputs read:
`docs/writer/genesis-status.md`, `docs/writer/provenance-ledger.md`,
`docs/inbox/genesis-assembler.md`, `docs/product/content-strategy.md` (§1,
§5.7 — the P0 gate). Everything below was **measured this session**, not
inherited; commands and scratch artifacts are listed in §F. No code was
modified.

---

## 0. One-paragraph verdict

**G0 is a real step, not a rename — but the "0 autodesk-sample" headline is
an artifact of what the ledger counts, and the honest residual is much larger
than the 139 gated clones the status document reports.** The ledger walks the
ElemTable only. It never opens `Global/Latest`, `Formats/Latest`, the History /
increment lineage, or the strings inside our own records. Measured: (a)
`Global/Latest` in G0 is **byte-identical** to the rst basic sample's ADocument
(1,586,246 inflated bytes) and it is not "settings machinery" — **78.5 % of it
(1.25 MB) is Autodesk's Forge unit/spec/parameter-group JSON schema corpus**
plus the sample project's own naming (room names *Hall / Kitchen & Dining /
Master Bedroom / Bathroom 1…*, sheet 'FOUNDATION-2700', assembly 'L1 wall
frame hall 5', sample materials 'Concrete 10 MPa' / '250 MPa'); (b)
`Formats/Latest` (496,597 inflated bytes) is Autodesk's serialized class model,
byte-identical, and the validator *rewards* that as "canonical"; (c) the
increment table carries **seven Autodesk employee usernames** (campbes,
hansonje, loboarch, okapaw, youyi, zhangg, gbs_subsuser6); (d) by byte weight
**~94 % of G0's stream content is Autodesk-sample or sample-lineage bytes and
~6 % is ours**; (e) against the union of all five Autodesk samples (not one
baseline) **154 of our 205 elements (75 %) read `transitive-cloned`**, and even
the elements the status calls safely "created" (DBViewProject 0.91,
ElectricalSetting 46/49 leaves identical to rme's) are Autodesk product
defaults reproduced. G0 does pass `tools/rvt_validate.py` with 0 errors, and
its inventory is genuinely our constructors' output. So: **real deletion +
real identity work, wrapped in a ledger whose scope makes the residual
invisible.** The G1 gate cannot honestly close until the ledger counts
streams and cross-corpus, and counsel rules on the three flagged
Autodesk-authored corpora (§C).

---

## A. Question 2 — validator (answered first because it is binary)

```
.venv/bin/python tools/rvt_validate.py experiments/genesis/G0.rvt
rvt-validate: experiments/genesis/G0.rvt
  verdict: VALID (no errors); warnings=0 info=2; layers=structure,consistency,semantic
  streams: 12   pages_checked: 12   gzip_members: 8   partition_blocks: 3
  records: 618  elements_decoded: 205  decode_failures: 0  refs_checked: 2679
  connector_edges: 0   timings: total=0.1s
```

**G0 passes with 0 errors, 0 warnings** (also `--strict`: 0/0). The two
info-level findings are the audit's first exhibits: `optional stream absent
(allowed)` and **`canonical Revit 2026 archive schema (byte-identical)`** —
the arbiter *checks that Formats/Latest is Autodesk's schema* (SHA-256 match,
`validate.py:722-728`) and reports it as good. Zero errors is a
structure/consistency verdict; `refs_checked: 2679` does not include the 6,175
dangling element ids inside `Global/Latest` — the validator does not decode
the ADocument, so "VALID" says nothing about whether Revit opens G0.

Full suite this session: **471 passed, 1 failed** — the failure is
`tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` (the plugin
bundle is missing the new `lib/src/rvt/genesis/*` copies; per KNOWLEDGE the
fix is `python tools/sync_plugin.py` — outside auditor territory, listed for
the orchestrator).

---

## B. Question 1 — is Autodesk / cloned expression UNDER-counted?  YES, on four axes

### B1. The ledger has no eyes for streams — and the streams are where the sample lives

`provenance.py` classifies **ElemTable rows + embedded save units**. It never
reads a global stream (`provenance.py` has no code path touching
`Global/Latest`, `Formats/Latest`, `Global/History`, the increment table,
`Contents`, or `ProjectInformation`). Measured stream-by-stream against the rst
basic sample G0 descends from:

| stream (compressed) | G0 | vs rst sample | authorship |
|---|--:|---|---|
| `Formats/Latest` 182,953 | 496,597 inflated | **byte-identical** | Autodesk (class model / schema) |
| `Global/Latest` 129,986 | 1,586,246 inflated | **byte-identical** | the sample's ADocument |
| `Global/PartitionTable` 134 | 87 | **byte-identical** | sample workset-table GUID |
| `Global/History` 17,144 | 18,180 vs 18,163 | 1,017 of 1,018 episodes are the sample's | sample lineage + our episode |
| `Global/DocumentIncrementTable` 1,159 | 5,328 | 22 of 23 records the sample's | **Autodesk employee usernames** |
| `Contents` 212 | — | creation GUID W identical | sample lineage GUID |
| `BasicFileInfo`, `ElemTable`, `ContentDocuments`, `Partitions/21`, `ProjectInformation`, `TransmissionData` | 20,494 total | ours | ours |

**Byte accounting the status document does not give:** total stream bytes
352,082; byte-identical Autodesk/sample streams (Formats + Latest +
PartitionTable) = 313,073 = **88.9 %**; add sample-lineage streams
(History + DIT + Contents) = **94.2 %**; ours = 20,494 = **5.8 %**. The
"380,928-byte project whose inventory is 100 % ours" is, by weight, ~94 %
Autodesk sample bytes carrying a 6 % payload of our elements.

### B2. `Global/Latest` is Autodesk-authored CONTENT, not neutral machinery

The status document (§4.2) describes it as "level table, phase table, view
lists, default-type ids, element-id arrays, ES schemas, ~120 settings". String
census of the inflated stream (5,315 strings) says otherwise:

* **1,245,794 bytes (78.5 %) are Autodesk Forge / AEC data-schema JSON
  documents** — hundreds of `{"typeid": "autodesk.spec.aec.*"…, "inherits":
  [...], "schemaSpecification": "forge-data-schema-2.0.0", "sealed": true}`
  objects: the complete unit / measurable-spec / parameter-group taxonomy
  (`autodesk.unit.unit:*` ×3,713, `autodesk.spec.*` ×1,146,
  `autodesk.parameter.group:*`, `autodesk.revit.group:*`). These are
  Autodesk-authored, versioned schema *documents*, redistributed verbatim
  inside every G-file. **FLAG FOR COUNSEL** — whether Autodesk's published
  unit schemas are freely embeddable is a licence question the strategy has
  never asked (content-strategy §4 licenses IFC/bSDD/GLDF schemas explicitly;
  Autodesk's are not on the list).
* **The sample PROJECT's own naming survives**: room table 'Hall',
  'Kitchen & Dining', 'Laundry', 'Living', 'Master Bedroom', 'Bathroom
  1'/'Bathroom 2', 'Ensuite' (the rst basic sample is a residence — these are
  its rooms); sheet 'FOUNDATION-2700' / 'S206'; assembly 'L1 wall frame hall
  5'; materials 'Concrete 10 MPa', '250 MPa'; colour-fill schemas 'HVAC Zones
  : Schema 1', 'Spaces : Schema 1', 'Ducts : Duct Color Fill'; a 102-row
  reconcile map of sample LocalIds/ExternalIds. This is *sample-authored
  expression* the ledger scores as absent (0 `autodesk-sample`).
* Autodesk vendor identity strings: 'ADSK', `http://www.autodesk.com`,
  'Revit Default DB Server', 'AREXContentGenerator', updater ids
  ('TextNoteUpdater', 'ObjectNumberingUpdater'), 'WireSizes.xml', and the
  document's Revit build/save history 2018 → 2026.

The ADocument still references **6,175 sample element ids, 0 of ours** (the
assembler measured this; I confirm the file is byte-identical to the
sample's). It is not "the sample's *object* with dead pointers" — it is a
1.6 MB Autodesk-authored document carrying the sample project's programme.

### B3. Cross-corpus clone measurement — the single baseline hides Autodesk product defaults

The gate report (`--baseline rstbasic`) says **142 cloned / 63 created**;
against `rmebasic` (which G0 does NOT descend from — 0 % id overlap) it still
says **130 cloned / 75 created**. I ran the classifier against **all five
Autodesk 2026 samples** and unioned the verdicts (`G0_multi.json`):

| baseline | cloned | created |
|---|--:|--:|
| rstbasicsampleproject (true lineage) | 142 | 63 |
| rmebasicsampleproject | 130 | 75 |
| racbasicsampleproject | 140 | 65 |
| racadvancedsampleproject | 129 | 76 |
| rstadvancedsampleproject | 126 | 79 |
| **UNION — cloned against ANY sample** | **154 / 205** | **51** |

Only **51 elements (25 %)** read `ours-created` against every Autodesk
file; only **26** have a max shingle-similarity below 0.40 anywhere in the
corpus. Elements the status document lists as "created with headroom" are
Autodesk defaults reproduced from a *different* sample:

* **`DBViewProject` 1500176 — 0.91 clone of racbasic's 230**; `Viewer`
  1500177 — 0.90 of rst 231; `BasePoint`s — 0.95/0.89 of rme's; the phase
  filters up to 0.84. The status document's "our views read created" is
  baseline-luck: the very same bytes are Autodesk's in rac.
* **`ElectricalSetting` 1500036** ("read created", status §4.1) — 0.79
  clone of rme 639116; decoded field-by-field it is **46 of 49 leaves
  identical to Autodesk's** (circuit-name phases 'A'/'B'/'C', 'Space'/'Spare'
  labels, the specific-angle set 11.25/22.5/30/45/60/90, circuit rating 20 A,
  path offset). The three that differ are the element id and two float
  round-offs. Nothing here was authored.
* The four wire conductor `CustomElement` cells clone rme at 0.60–0.82; the
  load classifications at 0.80; the label MACH strings our `types.py:1533`
  hard-codes ('Actual %1!s! Load', '%1!s! Connected Apparent Power' …) are
  Revit's built-in UI resource strings.

**Reading:** the ledger's clone detector is baseline-relative by design
(ledger §6.4), which is correct for lineage but blind to *product-default
reproduction sourced from any sample*. The honest gated population is
**154, not 139**, and the "63 ours-created" is ~26 elements with genuine
authored payload (our wall/floor/roof/ceiling types, our materials, our
patterns, our sub-categories, project info, geo sites) plus ~37 that clear
the 50 % bar only against rst.

### B4. Autodesk-identifying content inside OUR OWN records (`Partitions/21`)

Our 205 records legitimately name Autodesk product resources:
`assetlibrary_base.fbx` (Autodesk's shipped render-asset library —
`types.py:998`, `skeleton.py:1055`), asset names `SunAndSky-002` /
`Generic`, the built-in load-label MACH strings above, and Forge
`autodesk.spec.*` / `autodesk.unit.*` typeIds in the units registry. These
are references-to and identifiers-of Autodesk artefacts, not copied geometry
— defensible as interoperability facts, but they belong on the counsel list
next to the schema question, and the status document does not disclose them.

### B5. Repo-level provenance (not in the file, but ships in our tree)

`src/rvt/genesis/data/object_styles.json` (309 KB) is, by its own `source`
field, "the built-in-category GStyleElem records of rmebasicsampleproject
(Revit 2026)" — Autodesk's 1,074-category default pen/colour/pattern table
extracted into our source. The assembler did NOT emit it into G0 (G0 has 87
house-standard rows), but its presence in the shipping tree (it is bundled by
`tools/sync_plugin.py` per the failing test's file list) is a redistribution
question of its own. **Flag.**

### B6. Two accounting errors in the deliverable's own claims

* Status §3 and `G0_manifest.json` label the units registry **"136
  formats"**; the emitted `UnitsElem` 1500155 has **8**
  (`genesis_assemble.py:511` passes no `formats=` → `DEFAULT_UNIT_FORMATS`,
  8 entries; `entries=136` is a manifest label, not the argument). Minor, but
  the certification record misdescribes the file.
* Status §5.2 correctly retracts "R4s viewer-passed"; the auditor charter
  and `provenance-ledger.md §3.3` still cite "R4s = deepest viewer PASS" as
  fact. **No G- or R-rung has a recorded viewer pass.** The status
  document's own verdict paragraph should say so in the first sentence, not
  §5.

---

## C. Question 3 — what a hostile Autodesk expert points to FIRST in G0

Ranked by how fast it lands and how little argument it needs:

1. **`Global/Latest` — 1.59 MB byte-for-byte from `rstbasicsampleproject.rvt`.**
   One `cmp` proves it. It contains their sample project's room names,
   sheet/assembly names, material names and their 1.2 MB of `"sealed": true`
   Forge schema JSON. Under the legacy LSA §2.1.1 the strategy itself quotes
   (content-strategy §1: no licence to "distribute … all or any portion of
   the Autodesk Materials"), this is "a portion of an Autodesk sample
   project" shipping in our file. This is the whole case in one exhibit; the
   142-clone debate is a footnote next to it.
2. **`Formats/Latest` — their 497 KB class-model serialization, byte-identical**
   (our validator hashes it as *canonical*). Genesis.md §4.1 asserts "format
   constant, not expression"; that is our engineering opinion, unreviewed.
   A named-class/named-field schema of ~1,000 classes is exactly the kind
   of structured authored taxonomy an opponent litigates (the API-copyright
   line of argument); interoperability is a *defence to raise*, not a
   settled fact, and it is weaker when we ship their bytes verbatim rather
   than a clean-room re-serialization. **Counsel item #1 alongside Latest.**
3. **Their fingerprints in the metadata:** seven Autodesk employee usernames
   in `Global/DocumentIncrementTable`, the sample's creation GUID in
   `Contents`/`PartitionTable`, and 1,017 of their save episodes in
   `Global/History`. Not expression, but it destroys any "independently
   created" narrative and hands them chain-of-custody in our own bytes.
4. **154/205 host elements ≥ 50 % byte-identical to elements across their
   five sample projects**, including our "authored" project view (0.91) and
   electrical settings (46/49 field-identical). Their expert calls the
   "product-default machinery" argument what it is: we copied their
   defaults and are asking to be believed that defaults aren't authorship.
   Some are (pen tables, unit strings); the burden of separating them is
   ours and we have not done it (§D item 4).

Notably NOT on the list: embedded family documents (0 — genuinely gone;
`ContentDocuments` is the 14-byte empty form), Autodesk-sample host
elements (0 in the ElemTable — genuine), the family/circuit clones of the
V29 acceptance file (absent). The deletion work is real; it is the container
around it that is still theirs.

---

## D. Question 4 — ranked list for the G1 gate to genuinely close

1. **Extend the ledger to LEDGER THE STREAMS (blocks any honest PASS).** A
   `stream_provenance` layer: per global stream, byte-compare against the
   baseline (identical / prefix-shared / ours), plus a string census
   (Autodesk typeIds, sample names, employee usernames, vendor ids, Forge
   schema documents) with a byte total. Verdict rule: **G1 cannot pass while
   any global stream is byte-identical to a sample or carries sample-lineage
   identifiers.** Until this exists, `gate_G1` is measuring the ElemTable
   and calling it the document. (Territory: provenance stream. This is the
   under-count, made permanent by construction.)
2. **The ADocument (`Global/Latest`) decoder → encoder → our own document
   object** — exactly genesis.md §6.3 / status §6.2, now re-justified: it
   is not just "the last stream we can't write", it is the exhibit-A
   redistribution and the sample's room names. With it: mint History = [our
   episode], DIT = [our record], our lineage GUIDs (`minimal_globals`),
   which retires items 3 and B1's whole table in one stroke.
3. **Counsel ruling — three named corpora, one memo:** (a) the Forge unit /
   spec / parameter-group JSON schema documents (embed vs. reference vs.
   regenerate from Autodesk's published Forge schema package under its own
   licence); (b) `Formats/Latest` — ship-verbatim vs. clean-room
   re-serialization of the class model (byte-identity is the aggravating
   fact); (c) the extracted `object_styles.json` catalog in our source tree.
   The status document routes only "object-style pens = format constant?"
   to counsel; the two 500 KB+ verbatim Autodesk corpora are the bigger asks.
4. **Cross-corpus provenance as the standard run, and a definition-field
   comparator** (status §6 step 4, endorsed and sharpened): the certified
   ledger run must be `--baseline all` (union over every sample we hold),
   because product defaults sourced from *any* sample must gate. Then the
   per-class definition-field comparator + declared `machinery_bytes` masks
   make the "default vs authored" call inspectable — and force us to write
   down, class by class, which Autodesk defaults we are choosing to
   reproduce (ElectricalSetting's 46 fields, the view constellation's 461
   leaves, the phase-filter vectors) so counsel decides on a list, not a
   threshold. Do NOT tune constructors to slip under 50 %; that is the
   rename the charter warns about.
5. **Replace product-default reproduction with authored values where the
   value IS the expression** — ElectricalSetting, the phase-filter names /
   vectors ('Show Previous + Demo' is Revit product terminology), the
   built-in `%1!s!` load labels, the sample-parity GStyleElem pens. Where
   Revit *requires* the exact value, that is a fact to record in the
   counsel list, not a byte to quietly emit.
6. **A viewer certification of the ladder** (orchestrator) — G0's `VALID` is
   necessary, not sufficient; a fully-dangling ADocument opening in Revit is
   unmeasured and, per B2, opening is beside the point until item 2 lands:
   a G0 that opens is still shipping the sample's ADocument.
7. **Fix the two accounting errors** (136-vs-8 units; the retracted R4s
   viewer claim) and re-run the assembler's certification so the record
   describes the file.

**Honest statement — real step or rename?** *Real step.* G0's element
inventory is genuinely constructor-built (205/205 encode→decode byte-exact
per the assembler's proof, 0 sample rows, 0 modified rows, 0 embedded family
documents), it declares our GUID/author/metadata, it validates 0-error, and
the ladder G0a→G0 is a clean, reproducible experiment. That is not nothing —
it retires the family-document and sample-element classes of the gate for
real. But **the G1 gate does not move tonight**, because (i) the gate as
implemented never looked at ~94 % of the file's bytes, all Autodesk's; (ii)
the largest single Autodesk artefact in the product — the sample's
ADocument, room names and Forge schemas included — is still verbatim in G0
and the status document under-describes it as "settings machinery"; and
(iii) 154 of our 205 elements are majority-Autodesk bytes against the full
sample corpus. Calling G0 "the closest achievable approximation of a
genesis base" is fair *for the element layer*. Calling its residual "139
named elements … a classification decision, not an authorship gap" is the
rename: the residual is one whole Autodesk document object plus their
schema plus a stream ledger that does not yet exist. **Recommendation: no G1
motion until §D-1 (stream ledger) exists and re-reports G0; expect it to
report FAIL with ~331 KB of blocking stream bytes.**

---

## E. Diffs / actions requested of other streams (auditor writes no code)

* **provenance stream:** implement §D-1 `stream_provenance` + `--baseline
  all` union mode; make byte-identical global streams a hard `blocking`
  entry in `gate_G1`. Also the assembler's D1 diff (compound-structure
  false-positive) — orthogonal, still valid.
* **genesis-assembler:** correct the units-registry label/argument (136 vs
  8); disclose in `genesis-status.md` §4.2 the byte-identity of
  `Global/Latest`/`Formats/Latest`, the 78.5 % Forge-schema share, the sample
  room-name table, and the DIT usernames; move the "R4s uncorroborated"
  finding into the §0 verdict.
* **legal / orchestrator:** open the §D-3 counsel memo (three corpora); run
  `python tools/sync_plugin.py` to clear the one failing test — and note
  it will bundle `object_styles.json` (B5) into the plugin, itself a
  redistribution decision to make consciously.

---

## F. Reproduction (all run this session, from repo root)

```
.venv/bin/python tools/rvt_validate.py experiments/genesis/G0.rvt              # 0 err / 0 warn
.venv/bin/python tools/rvt_validate.py --strict --json /tmp/G0_val.json experiments/genesis/G0.rvt
.venv/bin/python tools/provenance.py experiments/genesis/G0.rvt \
    --baseline samples/rstbasicsampleproject.rvt      # 142 cloned / 63 created  (true lineage)
.venv/bin/python tools/provenance.py experiments/genesis/G0.rvt \
    --baseline samples/rmebasicsampleproject.rvt      # 130 cloned / 75 created  (0 % id overlap)
.venv/bin/python tools/provenance.py experiments/genesis/R10b.rvt \
    --baseline samples/rstbasicsampleproject.rvt      # 3,022 sample + 14 family docs (deepest R)
.venv/bin/python -m pytest -q                          # 471 passed, 1 failed (test_plugin_sync)
```

Scratch analysis scripts + JSON (session scratchpad
`/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/`):
`multi.py` → `G0_multi.json` (five-baseline union: 154 cloned-vs-any / 51
never / 26 with max-sim < 0.40); `g0_strings.json` (per-stream string
census of G0); `latest_quant2.py` (78.5 % Forge-schema byte share, 0 GUID
strings); `streams_cmp.py` (Formats/Latest, Global/Latest, PartitionTable
byte-identical to rst; History/DIT deltas); `ctx.py` (in-context proof of
sample room names / DIT usernames). These are throwaway; the numbers above
are the record.

## BRANCH STATE

* No branch (repo is not a git repository); no code, test, or docs-outside-
  inbox modified. This record `docs/inbox/genesis-audit.md` is the only file
  written.
* G0.rvt certification re-run: validator VALID 0/0; provenance vs rst =
  142/63 (matches the committed `G0_provenance.json`).
* Suite: 471 pass / 1 fail (`test_plugin_sync` — plugin bundle stale, fix =
  `tools/sync_plugin.py`, outside auditor territory).
* Open for orchestrator: stream ledger (§D-1), ADocument codec (§D-2),
  counsel memo (§D-3), the two accounting corrections (§B6), viewer
  certification. **G1: no motion. G0 is a genuine element-layer step whose
  gate residual is under-reported by the instrument's scope.**


## ORCHESTRATOR VERDICTS (2026-08-03 ~14:50) — READ BEFORE ASSEMBLING G1
- **G0.rvt: PROCESSING FAILED in the Autodesk viewer.** Validator-VALID is
  NOT sufficient. Lead suspect: the ~6,175 DANGLING element-id references
  carried verbatim in Global/Latest (Latest-dangling tolerance was the open
  question; this may be its answer). Other candidates: a mandatory registry/
  element the constructed skeleton omits; the assembler's commit path. The
  reduction ladder is being uploaded to bisect (R5 ~100 dangling, R9/R10
  thousands, R5s/R9s Latest-SAFE controls, R10b families-removed) — see
  docs/coverage/viewer-certified.json 'failed'/'certified' as they land.
  GENESIS-2 IMPLICATION: assume Latest MUST have ZERO dangling ids (rebuild
  the id registries to reference exactly the elements present) until the
  bisection says otherwise.
- **V32 (scrubbed DIT usernames): PASS.** **T_conduit_types.rvt (our own
  constructed conduit types injected into a project): PASS** — constructor
  output is reader-accepted; genesis types are real.


## ORCHESTRATOR VERDICTS #2 (2026-08-03 ~16:00) — THE A/B READS OUT
- **R5.rvt (Latest-DANGLING, ~100 dangling ids, families intact): PASS.**
  **R5s (Latest-safe control): PASS.** => Latest-dangling references are
  NOT fatal (at ~100; R9 with thousands uploaded next to find any threshold).
- **R10b.rvt (embedded FAMILY DOCUMENTS removed, 38/52 units spliced): FAIL.**
  Validator-clean but reader-rejected. Combined with G0's FAIL (G0 has ZERO
  family documents) the LEAD SUSPECT IS NOW: the reader REQUIRES the
  embedded family-document machinery (units + PartitionTable +
  ContentDocuments + host Family/FamilySymbol coherence), and/or specific
  system families that view/annotation types default to. NOT dangling.
- IMPLICATIONS FOR GENESIS-2 / THE ENCODER: (1) do not treat Latest
  dangling-id repair as the fix; (2) a G1 candidate must retain (or replace
  with OUR OWN) a valid family-document set — the asset-factory stream
  (src/rvt/famgen) is building exactly the family-document skeleton
  genesis needs; coordinate; (3) R9 (thousands dangling, families intact)
  and R9b (unit removal, less aggressive) are being uploaded to (a) find any
  dangling threshold and (b) tell whether unit-removal ITSELF breaks the
  file or only WHICH units R10b removed. Watch this file for verdicts.


## Round 2 — genesis-2 audit (2026-08-03, subject: `G1_candidate.rvt` + `G1a`/`G1b`)

Everything below was RUN this session (commands in §R2.6). No code touched;
this record is the only file written.

### R2.1 Does the byte-weighted headline hold?  YES — recomputed exactly.
`tools/provenance.py experiments/genesis/G1_candidate.rvt --baseline all
--streams`: **inflated 2,009,280 B; identical-to-baseline 1,860,703 B =
92.61 %; ours 131,250 B = 6.53 %; ex-`Formats/Latest` 90.18 %.**  Excluding
BOTH Autodesk corpora (Formats/Latest 496,597 + Forge corpus 1,333,340
measured): identical = 1,364,106 − 1,333,340 = **30,766 B of 179,343 B =
17.16 %** (status says 30,809 / 17.2 % — a 2-byte corpus-size drift,
immaterial), and that 30,766 decomposes exactly as History 17,408 +
PartitionTable 95 + BasicFileInfo 256 + Latest machinery 13,007.  The
status document's numbers are honest.  What the *narrative* under-weights:
92.6 % of the candidate's bytes are still byte-identical to Autodesk's
samples; "OUR document object" is doing rhetorical work the bytes do not
support (§R2.2).  Also confirmed: `G1_candidate`, `G1a`, `G1b` all
`rvt_validate` VALID 0 err / 0 warn; the ADocument codec is byte-exact on
all six samples (`tests/test_adocument.py` 14/14 — note: there is NO
`latest_encoder` module; the byte-exact proof the brief names lives in
`rvt.adocument.encode_latest` + `test_roundtrip_byte_exact[_large]`); an
independent i64 scan of the candidate's Latest finds **1** coincidental
sample-id window and **269** windows of OUR ids; the raw string scan of
EVERY stream finds **0** employee usernames, **0** sample room / sheet /
assembly / material / user names (`macalis`/`liqi` present in G1a's Latest,
gone in the candidate).  The sample-PROJECT expression is genuinely out.

### R2.2 Autodesk-authored BYTES remaining in `G1_candidate`, by stream — and copied vs re-serialized

| stream | bytes | Autodesk residue | verdict |
|---|--:|---|---|
| `Formats/Latest` | 496,597 | 100 % byte-identical to all six samples (Autodesk's serialized class model, 4,690 classes) | **COPIED bytes** (C4) |
| `Global/Latest` | 1,360,931 | 1,346,347 identical = Forge corpus **1,333,340 (sha `093048af…`/`f7d62970…` = the samples')** + ~13,007 ADocument machinery | corpus **COPIED**; the machinery is **the sample's decoded ADocument re-serialized by us** (see below) |
| `Global/History` | 18,188 | 17,408 identical (95.7 %); 2,583/2,593 32-B windows found in rstbasic = its 1,017 save episodes | **COPIED** lineage |
| `Global/PartitionTable` | 134 raw | raw stream **byte-for-byte the sample's** (workset GUID) | **COPIED** |
| `Contents` | 264 | prefix-shared with the sample | partly copied |
| `Global/DocumentIncrementTable` | 5,608 | 0 identical bytes, but **structure = the sample's 23-record increment history**, every username renamed to `rvt-writer` | **structure inherited, values renamed** |
| `BasicFileInfo` | 1,955 | 256 B = product build constant; identity ours | ok (C1 build string) |
| `Partitions/21` (our 234 element records) | 115,267 | 0 identical bytes; but **135 records read cloned** (union of six samples): 90 GStyle house rows 0.58–0.83 vs racadv, BasePoint 0.89/**0.95**, Viewer up to **0.90**, 9 conductor `CustomElement` 0.64–0.82 vs rme, DBViewProject 0.70, ConduitStandard 0.61, FontElem 0.64…; plus 7,400 Autodesk resource identifiers (7,363 Forge typeIds, 36 `%1!s!` tokens) | **structure-we-serialized reproducing Autodesk product-default values** |
| `Global/ContentDocuments` 22, `ElemTable`, `ProjectInformation`, `TransmissionData` | — | none found | ours |

The plain statement the status document does not make: **"OUR ADocument" is
the rst sample's ADocument, decoded and edited.**  `tools/genesis_assemble.py::
stage_own_latest` = `source = adoc.decode_latest(<G0's Latest, i.e. the
sample's verbatim>)` → `author_adocument(source.value, …)` (purge dangling
ids, refill registries over our ids, empty caches) → `encode_latest`.  Nothing
in the document object was authored clean-room; every value the four policy
layers did not touch is the sample's value re-emitted through our codec.
Re-encoding is not authorship.  So the residue splits as: **(A) COPIED
Autodesk bytes ≈ 1,847,600 B (Formats/Latest + corpus + History episodes +
PartitionTable + build constant) ≈ 92 % of the file**; **(B) Autodesk
STRUCTURE / values we serialized ourselves**: the rest of the ADocument
(~27 KB incl. 13 KB still byte-identical machinery), the DIT record layout,
and 135 element records reproducing product defaults; **(C) genuinely
authored**: ~99 element records (69 with max-similarity < 0.40, 17 < 0.25),
our identity / metadata streams.  G1b (both corpora emptied) shows the
floor of the current design: its Latest is still **45.1 % (11,776 B)
byte-identical** to a sample — Autodesk's machinery values carried, not
authored — and the whole file is 78.0 % identical (Formats/Latest dominates).

### R2.3 The Forge JSON corpus disposition — COPIED, and no document claims otherwise
The brief's hypothesis "regenerated from Autodesk's open-source repo under
Apache-2.0" appears NOWHERE in this tree; `docs/writer/latest-regions.md`
§0/§2.4 and `docs/inbox/adoc-landmarks.md` §1 state the OPPOSITE —
determination (c) "regenerate from a public repo" is **FALSE**: no
autodesk-forge / GitHub repository publishes these documents, the schema
portal is login-gated, **no licence text of any kind is embedded** (I
re-grepped the candidate's Latest for `license|copyright|Apache|MIT|github`:
0), and the corpus is the serialized image of the installed *Autodesk Revit
Unit Schemas* MSI.  The measured fact settles disposition regardless of
prose: **G1_candidate's two corpus tables hash IDENTICALLY to rstbasic's and
rmebasic's (893 docs / 796,206 B / `093048af34059e5f`; 422 docs / 537,134 B /
`f7d62970ac9b1bfb`; `tools/latest_map.py --identity` = True across all six +
my own sha-256 recompute) — it was COPIED out of a sample.**  The assembler
says as much ("CARRIED + FLAGGED"); nobody claims regeneration or an
Apache grant.  Two facts sharpen the counsel item beyond "product runtime
data": (i) **341 of the 1,315 documents carry Autodesk-authored English
prose** (`"annotation": {"description": "The SI base quantity measurable in
amperes."}`) and 847 carry display-name constants ('Model Properties',
'Analysis Results') — authored text, not bare identifiers; (ii) "present
identically in the customer's install" describes where the bytes ALSO live,
not how WE obtained them — we obtained them by copying a sample's stream.
Route (ii) — read the schemas from the customer's licensed install at
generation time — is the only route that changes the provenance sentence;
route (i) (emit verbatim) needs an explicit ruling; G1b proves the empty
state is buildable (viewer verdict pending).

### R2.4 `Formats/Latest` — counsel question C4 restated with the file
`Formats/Latest` in every G1 file: **496,597 inflated bytes**, sha-identical
to all six 2026 samples (the validator scores this "canonical", info-level).
Contents: Autodesk's serialized CLASS MODEL — the archive schema of ~**4,690
class definitions** (class names incl. `ADocument`, per-class field names
such as `m_prefix` / `m_sampleValue` / `m_separator`, field type codes and
order), i.e. the wire dictionary the whole format is decoded against.
**C4, for counsel:** (1) may we ship Autodesk's schema serialization
byte-verbatim inside a file we distribute (every Revit 2026 file carries it
identically and the reader may require it), or must we clean-room
re-serialize the class model from a specification we write ourselves — with
byte-identity, not derivation, as the aggravating fact; (2) is the class /
field taxonomy itself protectable expression (structure-sequence-
organisation / the API-copyright line of argument), interoperability being
a defence to plead rather than a settled exemption; (3) the SAME two
questions for the 1,333,340-B Forge unit-schema corpus (§R2.3), whose two
engineering routes are emit-verbatim vs. read-from-the-customer's-install.
C4 is now ~1.83 MB of the candidate's 2.01 MB — 91 % of the file rides on
one memo.

### R2.5 Verdict — does G1 close the P0 gate?  **NO.**
G1_candidate is a validator-clean file whose element inventory is ours and
whose sample-project expression is genuinely gone (names, ids, caches,
usernames — verified), but 92.6 % of its bytes are Autodesk-authored bytes
copied from their samples, its "own" document object is their document
object edited, and no G1 file has a viewer verdict.  The v2 gate itself says
FAIL, correctly.  What remains, ordered:
1. **Forge unit-schema corpus** (1,333,340 B, copied) — **counsel** rules
   emit-verbatim vs. customer-install-sourced; **engineering** viewer-tests
   `G1b.rvt` (corpus emptied) to learn whether "ship empty" is even available.
2. **`Formats/Latest` C4** (496,597 B, copied) — **counsel** (verbatim vs
   clean-room re-serialization); **engineering** if the ruling is clean-room.
3. **The ADocument is a derivative, not clean-room** — **counsel** must be
   TOLD it was built by editing the sample's decoded document (the status
   framing implies otherwise); **engineering** either authors the machinery
   frame from a written spec (the 241-slot registry, updater / propagation
   registries, product-default settings values) or produces the per-field
   list so counsel rules value-by-value; today 45 % of even G1b's Latest is
   sample-identical.
4. **Save-history lineage** — History (17.4 KB of the sample's 1,017
   episodes), PartitionTable + Contents GUIDs, the DIT's 23-record structure,
   the stream name `Partitions/21` — **engineering** (mint the single-episode
   lineage: `skeleton.minimal_history/_increment_table/_partition_table/
   _contents` exist, unexercised), then re-viewer-test.  Advisory to the
   gate, but it is chain-of-custody evidence in our own bytes.
5. **135 product-default element clones** (BasePoint 0.95, Viewer 0.90,
   conductor cells 0.82, 90 GStyle house rows) — **counsel** classification
   list class-by-class; **engineering** authors values where the value is
   expression (ElectricalSetting already retired this round).
6. **Autodesk resource identifiers in our records** (7,400; mostly the
   corpus typeIds + our UnitsElem's lookup keys + 36 `%1!s!` tokens) —
   **counsel** (interface tokens); largely dissolves with item 1.
7. **Viewer acceptance of ANY G1 file — unmeasured** — **orchestrator**
   (the §7 queue: G1a → G1_candidate → G1b → G1_candidate_safe).
8. Two bookkeeping nits (**engineering**): the gate text says "134 elements"
   while the union table and docs say 135 (the 135th is a non-gated datum) —
   pick one number; the corpus is 1,333,340 B (measured), not 1,333,338.

One-line verdict: **G1 does not close the P0 gate — the sample project is
gone from the file, but the file is still ~92 % Autodesk-copied bytes plus
a document object derived from theirs; items 1–3 are counsel's memo and
items 3–7 are engineering, and none is done.**

### R2.6 Reproduction (all run this session, repo root)
```
.venv/bin/python tools/provenance.py experiments/genesis/G1_candidate.rvt --baseline all --streams   # 92.61 % / FAIL
.venv/bin/python tools/provenance.py experiments/genesis/G1b.rvt --baseline all --streams           # 78.01 %; Latest 11,776 ident
.venv/bin/python tools/rvt_validate.py experiments/genesis/{G1_candidate,G1a,G1b}.rvt              # 3x VALID 0/0
.venv/bin/python -m pytest tests/test_adocument.py -q                                              # 14 passed (byte-exact codec)
.venv/bin/python tools/latest_map.py --identity                                                    # corpus sha identical, 6/6
scratchpad aud2/scan.py <file>          # per-stream raw string scan (all streams inflated + prefix)
scratchpad aud2/(corpus sha of G1 files) # G1_candidate tables = 093048af…/f7d62970… = samples'
scratchpad aud2/(i64 scan)              # 1 coincidental sample-id window / 269 own-id windows
```

## BRANCH STATE (round 2)
* No VCS; no code / test / other-doc modified; this file appended only.
* G1 set: validator VALID 0/0 (candidate, G1a, G1b); v2 gate FAIL on all;
  headline 92.61 % identical / 6.53 % ours holds; corpus COPIED (sha-proven).
* Full suite (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`):
  see R2.7 below.
* Open, ordered as §R2.5 items 1–8. **G1: NO.**

### R2.7 Full suite this session
`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle` → **600 passed,
3 failed** (621 s): `test_plugin_sync.py::test_plugin_is_in_sync_with_source`
(known stale plugin bundle, fix = `tools/sync_plugin.py`, not audit
territory) and TWO NEW: `tests/test_provenance.py::test_G0_identity_dit_
usernames_still_leak` + `::test_G0_resource_refs_are_counted` — both were
written against the v1 G0 and assert its old leaks; the rebuilt G0 (username
scrub inside the assembler) no longer leaks, so the tests are stale, not the
file. Owner: the provenance stream (update the fixtures to the audit's own
finding — G0's identity layer now passes). Item 9 for the list.



## ORCHESTRATOR VERDICTS #3 (2026-08-03 ~17:05) — BISECTION CLOSED
- **R9 (thousands of dangling Latest refs, families intact): PASS** =>
  Latest-dangling is NOT fatal at any tested scale (100..thousands).
  G0's 6,175 dangling ids were never the cause. CAVEAT CLOSED.
- **R9b (unit removal, gentler than R10b): FAIL** (like R10b) => removing
  embedded family documents / splicing save units while the content
  registries still expect them = the killer. The reader requires the
  embedded family / content-registry machinery to be COHERENT.
- The genesis-2 candidate 'made the loaded-content registry coherent with
  the empty ContentDocuments' — which is precisely the fix these verdicts
  point at. G1_candidate / G1a / G1b are being uploaded NOW as the decisive
  test. Future genesis rule: never remove content/family documents without
  ALSO reconciling ContentTable/ContentDocuments/registries to match.


## ORCHESTRATOR VERDICTS #4 (2026-08-03 ~18:20) — G1 SET FAILED; TWO-BUG MODEL
- **G1_candidate, G1a, G1b: ALL PROCESSING FAILED** — including G1a
  (coherence-only). Content-registry coherence was necessary but NOT
  sufficient.
- CRITICAL CROSS-REFERENCE (docs/inbox/genesis-reduction.md line 142): R10b
  KEPT the 12 view-annotation-head families (Section/Level/Grid/Callout
  heads, Elevation Mark, View Title, Boundary Condition), the title block and
  curtain families — and STILL FAILED. Therefore "missing annotation-head
  families" is NOT the reduction killer. TWO DISTINCT BUGS ARE LIKELY:
  * BUG A (G0/G1 — constructed base): SKELETON COMPLETENESS — settings
    singletons / catalog elements the reader requires but our 205-234-element
    base omits (assembler's §5.2 branch: PenWidthTableElem,
    BrowserOrganization, UniqueElement settings singletons; possibly the
    ~450 settings-catalog + category/GStyle catalog + head families a real
    minimal project keeps). NOTE our base ALSO has zero family documents —
    still a candidate factor for G0/G1 specifically.
  * BUG B (R9b/R10b — reductions): the unit-removal ContentDocuments splice,
    built BEFORE the forge stream solved that stream's true grammar
    (docs/inbox/asset-forge.md — grammar SOLVED, byte-exact reassembly).
    Re-emit the removal with the solved grammar and retest.
- P4_ids_null.rvt + P6_all.rvt (rst working base, families intact, ADocument
  ids nulled / maximally sanitized) UPLOADED to settle whether the
  ADocument is a suspect at all: P6 PASS => ADocument fully exonerated =>
  G0/G1 failure is purely skeleton completeness (Bug A).


## ORCHESTRATOR DIAGNOSTIC — AUTODESK'S OWN ERROR MESSAGES (2026-08-03 ~19:30)
The failed-card page in the Autodesk viewer exposes the translator's messages
(we had not been reading them). For BOTH G1a.rvt AND R10b.rvt the signature is
IDENTICAL:
  * "Design is empty. Please check the design."
  * "Revit-DocumentCorruption <message>The file is corrupt.</message><hint>Please
    open the file in the current version of Revit to see more details about
    the corruption.</hint>"
  * "TranslationWorker-InternalFailure Unrecoverable exit code from extractor:
    -1073742517" (Revit's extractor CRASHED)
IMPLICATIONS: (1) both suspected bugs trip Revit's OWN document-corruption
audit at open time (a structural-consistency check inside Revit, not a
translator quirk) — our validator is missing at least one consistency rule
Revit enforces; whatever check that is, is the target for BOTH bugs.
(2) the message does not discriminate Bug A from Bug B — the K/B probe
verdicts remain the bisection instrument. (3) FROM NOW ON every failed
probe's card message is read and appended here; any probe that fails with a
DIFFERENT message is a spotlight. First tranche uploaded ~19:15-19:25: K4
(uploaded WITH KD1+K3 as linked references by accident — treat its verdict
as K4's; KD1/K3 also uploaded alone), KD1, K5, K6, K3.


## ORCHESTRATOR VERDICTS #6 (2026-08-03 ~20:25) — BUG A NAMED
- **K4 PASS** (zero family documents, four-registry coherent, sample
  skeleton): FAMILY DOCUMENTS ARE NOT REQUIRED by the reader.
- **KD1 PASS**: R9b's exact removal reconciled across all FOUR registries
  loads => Bug B was the two-of-four splice; FIXED by four-registry
  reconciliation (famload/triage machinery).
- **K3 PASS**: head-family usage fields are nullable.
- **K5 FAIL**: the empty project minus its settings SINGLETONS dies =>
  singletons REQUIRED. **K6 FAIL**: minus the built-in category/GStyle
  CATALOG dies => catalog REQUIRED. **P4/P6 FAIL** on a WORKING base with
  LIVE registry ids nulled (contrast R5/R9 dangling-PASS): the ADocument
  registries INDEX the catalog rows and are walked at load — entries must
  correctly index PRESENT rows; ids of DELETED elements are tolerated.
=> BUG A = an INCOMPLETE catalog/singleton set that the document object
promises: the reader needs (1) the settings singletons and (2) the FULL
built-in category/GStyle catalog, with (3) the ADocument registries
indexing them coherently. The genesis-singletons stream pre-built exactly
this: settings.py (69 singleton classes, ADOC_REGISTRY), catalog.py
(complete 1,407-row style table, OUR values), S1..S5. UPLOADING NOW: S5
(census-complete = base + every class in K1 via OUR constructors), S4
(catalog), S3 (singletons), S1 (pen table), + L1a (loader proof).


## ORCHESTRATOR VERDICTS #7 (2026-08-03 ~21:05)
- **L1a PASS**: our generated family (level head) LOADED into a working
  project via the four-registry loader. Our families load into projects.
- **S5, S4, S3, S1 FAIL** — same signature ('Revit-DocumentCorruption',
  'Design is empty'). OUR singletons + OUR full catalog on the G1_candidate
  base do NOT cure it. Two explanations the S-set cannot separate (our
  content tested on the suspect base): (i) our constructed singletons/catalog
  are mis-shaped/mis-registered for the reader; (ii) the G1 base carries a
  defect independent of catalog/singletons.
- DECISION — SUBSTITUTION LADDER FROM THE PASSING SIDE: start from K1
  (Autodesk's empty-project skeleton, PASSES) and REPLACE its content with
  OURS class by class (X1 pen table -> ours; X2 + browser org; X3 + named
  singletons; X4 + settings/size tables; X5 + full category/GStyle catalog;
  ... Xn = zero Autodesk-authored elements). Every rung derives from a
  PASSING file; the first FAIL names the exact one of OUR constructors the
  reader rejects; a clean run to Xn IS genesis. Plus add-back probes
  R1 = K5 + our singletons, R2 = K6 + our catalog (our content on the
  known-good skeleton) and the staged K5a-d (WHICH singleton subset).


## ORCHESTRATOR VERDICTS #9 (2026-08-03 ~23:00) — THE DIVIDE IS CONSTRUCTED vs CLONED
- **R3, X9, R2, X5, R1 ALL FAIL** (+ K5a, K5d), every one 'Revit-DocumentCorruption /
  Design is empty / extractor crash'. R2 in particular: OUR catalog substituted
  onto Autodesk's own K1 skeleton, whose mechanics control R2s reproduced K1
  BYTE-IDENTICALLY — still fails. => the defect is NOT the registries/parity
  (repaired), NOT the S5 base, NOT the removal residue.
- THE INVARIANT ACROSS ALL 40+ VERDICTS: every file whose element records
  are CLONED / VERBATIM / byte-exact-reproduced Autodesk objects LOADS
  (V/H/M/K/R-controls, L1a — whose family records reproduce specimens
  byte-exact); EVERY file carrying our FROM-SCRATCH CONSTRUCTED objects
  (genesis settings singletons, our catalog rows, house-standard content) —
  built field-by-field over schema blanks with OUR values — FAILS.
- => PRIME SUSPECT: the FROM-SCRATCH OBJECT CONSTRUCTION PATH (blank_object /
  schema-directed synthesis + our VALUES), not the registries: either the
  object SHAPE differs from any accepted specimen when our values differ
  (counts / array lengths / enum ranges / nullability invariants the reader
  audits) or the ADD path for these element classes (ElemTable / ownership /
  episode / positional-slot registration) differs from the family-instance
  add path that is proven.
- NEXT (genesis-5): the three-way separation {ADD PATH vs OBJECT SHAPE vs
  OUR VALUES}: X0 = K1 minus its pen table + the SAME Autodesk pen table
  re-inserted VERBATIM through OUR add path (PASS => add path fine); X1v =
  K1 with OUR constructor fed AUTODESK'S EXACT parameter values (byte-
  identical object; PASS => shape fine); X1 (uploaded now) = OUR constructor
  with OUR values (FAIL alone => our VALUES violate a reader constraint);
  plus a constructed-object LINTER diffing our objects against specimen
  invariants across the corpus (never-null fields, array-length/count
  invariants, enum ranges, id-typed targets, owned-child cells).


## ORCHESTRATOR VERDICTS #10 (2026-08-03 ~23:40)
- **X1 FAIL** — predicted by the fixer BEFORE the verdict: X1's pen table
  carries OUR imperial scale keys (24..768), which appear in 0/3,494
  specimen pen tables; the six-sample format constant is {10,20,50,100,200,
  500}. genesis-5 CONVERGENCE: (a) controls proved our pen-table
  constructor fed Autodesk's exact values reproduces the specimen
  BYTE-IDENTICALLY (X1v == X0) => object SHAPE/header/rep retired as suspects;
  the only variables are VALUES/KEYS; (b) the linter mined 15,823 field
  invariants over 59,770 specimens (calibrated on our PASSING constructed
  objects) and localized the ElemTable OWNERSHIP web + singleton VINTAGE
  (creation-episode 0, low id bands) as audited dimensions, and EXONERATED
  our catalog rows themselves; (c) the fixer found the per-KEY value grammar
  (scale-key set; per-category flag low byte 0x0E vs our uniform 0x1E; 380
  pattern-NULL + 40 pen-NULL cells; 48 screen-sized keys; 32 material ids;
  192 document-wired keys = 2,560 fields), FIXED settings.py + catalog.py,
  and found R2's CONFOUND (catalog at new ids on a base WITH embedded
  documents leaves ~1,400 document-internal style refs dangling — family
  removal must precede catalog substitution).
- UPLOADING NOW: X0 (verbatim pen table via our add path — the ADD-PATH
  control), X_pen (K1 + ONLY the FIXED pen table), X_cat (K1 + the FIXED
  catalog), X1u (our widths on Autodesk's scale keys), C0 (verbatim catalog
  row via our path).


## ORCHESTRATOR VERDICTS #11 (2026-08-04 ~00:35) — THE ADD PATH IS THE BUG
- **X0 FAIL** (Autodesk's OWN pen table, exact bytes, re-inserted via OUR add
  path) and **C0 FAIL** (Autodesk's own catalog row verbatim via our path).
  X_pen, X_cat, X1u also FAIL (now uninterpretable — subsumed by X0).
- => OUR OBJECTS ARE EXONERATED. Autodesk's own bytes fail when WE register
  them. The corruption is in the ADD PATH for non-instance elements (ElemTable
  registration / ownership / creation-episode VINTAGE / positional-slot
  registry motion / record-stream ordering) — NOT in anything the
  constructors build. Every constructed-object failure of the night (S1..S5,
  R1..R3, X1..X9) was an add-path failure. The family-INSTANCE add path is
  PROVEN (V20..V29 load); the bug is the delta between instance-registration
  and singleton/catalog-row registration — the linter already flagged 'two
  ADD-PATH ElemTable rules' + ownership-web + vintage.
- NEXT: X0k (pen table re-added AT ITS OWN ORIGINAL ID, zero registry
  motion) UPLOADED NOW — X0k PASS => new-id registration (slot/vintage/
  ownership) is the fault; X0k FAIL => the delete+re-add record-stream
  mechanics. genesis-6 launched: add-path forensics + per-rule verbatim
  controls (owner / creation-episode / record-order / slot semantics) each
  ONE change from X0, and the instance-vs-singleton registration diff.


## ORCHESTRATOR VERDICTS #12 (2026-08-04 ~00:55) — ORACLE-HEALTH ALARM (forensics)
- **X0k FAIL** (records byte-identical to K1's element 2, Latest identical;
  only the ElemTable episodes + record order differ) — 13 consecutive
  FAILs since the last PASS (L1a ~21:05).
- The forensics stream's BLOCKING FINDING is acted on FIRST: X_pen's change
  set (126 pen doubles in Partitions/21, nothing else) is DISJOINT from
  X0's (a registry re-point), yet both FAILED the same round — two
  orthogonal probes failing is over-determined, and NO known-PASS control
  was uploaded across the last four rounds. Either two independent
  constraints exist, or the ORACLE / environment degraded (throttling,
  account, service) and rounds 8-11 tested nothing. RESOLVING NOW: two
  certified-copy controls (CTRL_L1a_recheck.rvt = md5-identical to L1a which
  PASSED at ~21:05; CTRL_R9_recheck.rvt = certified R9) uploaded ~00:55. If
  they FAIL, verdicts #8-#11 are VOID and the loop pauses uploads until the
  oracle is healthy; if they PASS, the failures are real and RANK 1 (delete
  + registry-value re-point of a REGISTERED element — the one dimension in
  X0∩C0 absent from every viewer-PASSED file) is the target.


## ORCHESTRATOR DIAGNOSTIC (2026-08-04 ~01:00) — X0k HAS A DIFFERENT SIGNATURE
- X0k.rvt (records byte-identical to K1's element 2; differs only in ElemTable
  episodes + record ORDER) FAILS WITHOUT the 'Revit-DocumentCorruption' line:
  only 'Design is empty' + 'TranslationWorker-InternalFailure Unrecoverable
  exit code from extractor: -1073741831' (vs -1073742517 + DocumentCorruption
  on every audit failure tonight). => a DIFFERENT failure mode: X0k does NOT
  trip the corruption audit; the extractor crashes another way (record-order
  inversion crashing the loader?) — OR the extractor is generally unstable
  tonight (oracle sick). The three controls in the reader (CTRL_L1a_recheck =
  md5-identical to certified L1a, CTRL_R9_recheck = certified R9, XR_null =
  byte-identical to K1) DECIDE. No further probes are uploaded and no
  ranking is acted on until they read out.


## ORCHESTRATOR VERDICTS #13 (2026-08-04 ~02:00) — ORACLE HEALTHY; TWO REAL CONSTRAINTS
- **CTRL_L1a_recheck PASS, CTRL_R9_recheck PASS** => the service is healthy;
  verdicts #8-#11 STAND; the 13 failures are REAL. The forensics alarm
  resolves as TWO INDEPENDENT constraints (X0/C0 registration line AND the
  in-place X_pen line), not a sick oracle.
- NEXT (uploading now, best-isolated first): XR0 (in-place pen table via the
  CERTIFIED reduce.reblock mechanics, block partition identical to K1 = X_pen
  minus the CHUNKER variable — PASS => constraint 2 is the commit path's
  re-chunking/layout, not values), XA2 (X0 'done right': free LOW id,
  corpus vintage ce0/me976, id-hole position, one typed re-point — PASS =>
  the registration line is closed by regadd), P_ep_only / P_pos_only /
  P_ident_only (single-dimension isolators from the FAILING X0), and
  XR_null (K1 byte-identical positive control, already uploaded).


## ORCHESTRATOR VERDICTS #14 (2026-08-04 ~02:25) — IS THE BASE ITSELF BROKEN?
- **XR0 FAIL (crash signature -1073741831, no corruption line), XA2 FAIL,
  P_ep_only / P_pos_only / P_ident_only FAIL.** Two death modes are now
  clean: AUDIT (-1073742517 + Revit-DocumentCorruption) vs CRASH
  (-1073741831, X0k + XR0 = the two smallest-delta files).
- CRITICAL REALIZATION: **K1 (the base of the ENTIRE ladder — every X-rung,
  S/R candidate, control) HAS NEVER BEEN UPLOADED.** It was assumed to pass
  because it derives from R5 (PASS), but the K-files that DID pass (K3, K4,
  KD1) descend from R9, NOT K1. NOTHING derived from K1 has EVER passed. If
  K1 itself fails (the 'R5 minus placed model' maximal-GC reduction
  introducing a defect), every K1-derived failure — and the entire
  'constructed objects fail' law — is that defect in forty costumes.
- ACTION NOW: K1 itself uploaded as K1_base.rvt, plus XR_null (byte-
  identical to K1 through the pipeline; its earlier upload was a stale
  read and never happened). K1_base FAIL => rebase the whole ladder on a
  CERTIFIED base (R9 or R5 or K4) and the two-constraint model dissolves;
  K1_base PASS => back to the audit/crash two-mode model.


## *** ORCHESTRATOR VERDICTS #15 (2026-08-04 ~02:45) — RETRACTION: THE BASE WAS BROKEN ***
- **K1_base.rvt (K1 ITSELF) FAILS** — crash signature -1073741831, no
  Revit-DocumentCorruption line. **XR_null (byte-identical) FAILS.** K1 was
  the base of EVERY substitution rung (X1..X10), every S1..S5 / R1..R3
  candidate, every control (X0, C0, X0k, X1v/u, XR0, XA2, P-probes) — and
  was NEVER itself uploaded; its lineage produced ZERO passes in five hours.
  Assumed sound because derived from R5 (PASS); the K-files that DID pass
  (K3, K4, KD1) descend from R9.
- **RETRACTED as artefacts of the broken base (NOT findings):** #9's "the
  divide is constructed vs cloned objects"; #10's "our values violate a
  value grammar" AS THE CAUSE; #11's "the ADD PATH is the bug"; #13/#14's
  "two independent constraints". None of those probes tested our
  constructors, add path, or values against a LOADABLE base. They are
  UNJUDGED, not condemned.
- **WHAT SURVIVES intact:** ADocument codec (byte-exact), ContentDocuments
  grammar, four-registry law + Bug-B fix (KD1 PASS, R9 lineage — REAL), K4
  PASS (family docs not required — REAL), R5/R9 dangling-tolerance (REAL),
  L1a (our family loads — REAL), every corpus FACT the linter/fixer mined
  (scale-key sets, per-category profiles, ownership webs, vintage bands —
  descriptive laws independent of any base), the parity instruments, the
  registration paths, and the death-signature vocabulary (AUDIT -1073742517
  vs CRASH -1073741831 — K1's defect CRASHES; its heavier-modified children
  tripped the AUDIT instead).
- NEXT (genesis-7): (a) autopsy K1 vs R5 — name the load-bearing removal
  (a permanent 'never remove this' law for the ladder); (b) REBASE the whole
  ladder on the CERTIFIED family-free base K4 (R9 lineage, viewer-PASSED) —
  the ladder may simply WORK; (c) STANDING CONTROLS DISCIPLINE codified —
  every batch = its own base + >= 1 certified control + probes; a base is
  CERTIFIED before anything is built on it.


## VERDICT INTEGRITY LEDGER (2026-08-04, genesis-discipline stream) — READ WITH #15
The retraction's consequences, made mechanical.  The full map — EVERY
recorded verdict of rounds #1-#15 classified SOUND / UNGUARDED / VOID by two
tests (was its BASE itself viewer-certified at the time? did its ROUND carry
a known-PASS control?) — is **`docs/writer/verdict-integrity-audit.md`**,
generated by `tools/probe_batch.py retro`.  Headline:
- **35 recorded FAILs = 31 VOID + 3 UNGUARDED + exactly 1 SOUND (R9b →
  KD1).**  21 of the VOID sit on the K1 lineage, 9 on the G0/G1 assembler
  lineage (G0's own ladder G0a-G0d was never tested; G1/S/R3 built on the
  FAILED G0/G1) + R10b on the never-uploaded R10.  All 11 PASSes survive.
- **VOID as conclusions (unjudged, NOT condemned):** #6's *Bug A* — "settings
  singletons REQUIRED" (K5) and "style catalog REQUIRED" (K6) — VOID, not
  established; #9 "constructed vs cloned"; #10 "value grammar as the cause";
  #11 "the add path is the bug"; #13/#14 "two independent constraints".
  #1's lead suspect (dangling ids) is REFUTED (R5/R9).
- **SURVIVES with real evidence:** R5/R5s/R9 dangling-tolerance; the
  four-registry law + Bug-B fix (R9b SOUND → KD1); K4 (family docs NOT
  required); K3; L1a (our family loads); T_conduit_types (our constructed
  types load); V30-V32 identity; the two death signatures; P4/P6 live-id
  rule (UNGUARDED, consistent); every CORPUS fact the linter/fixer mined
  (independent of any verdict); and K1's OWN FAIL (base R5 certified;
  corroborated by byte-identical XR_null + the ~01:55 CTRL passes; robust
  under either oracle branch) = the campaign's load-bearing finding.
- **The failure mode, quantified:** ONE round in fourteen (#12, ~01:55)
  carried a deliberate certified control; EIGHT of twelve FAIL-bearing
  rounds carried NO passing file; rounds #8-#11 = 12 uploads, 12 FAILs, 0
  passes, 0 controls, all on the uncertified K1.
- **Ledger discrepancies for the orchestrator** (audit §8): R4s/R0_identity
  ARE ledger-certified — the "no R-rung viewer pass" prose in genesis-status
  /this file's §B6 is stale (the acceptance log stopped at batch 10; the
  LEDGER is the authority; a CTRL_R4s copy in a future round settles it);
  XR_null's #15 FAIL is missing from 'failed'; 18 files staged in
  experiments/acceptance/ have NO recorded verdict; the six samples are not
  listed as certified though every certified lineage builds on them.
- **In place now:** `docs/coverage/viewer-certified.json` — every 'failed'
  entry ANNOTATED with `cause_status` (nothing deleted); `tools/probe_batch.py`
  (34 tests) = the batch gate: `stage` REFUSES any probe whose declared
  base is not ITSELF in 'certified' (the manifest's "(viewer PASS)" prose is
  ignored — 25 K1 probe entries carried it), refuses undeclared lineage,
  generates
  the byte-identical `CTRL_<newest-certified>_b<n>.rvt` control, stages the
  batch + `batch_<n>.json` manifest; `read_batch_verdicts` reads every round
  control-first (control FAIL => whole round VOID; uncertified base =>
  refuse, demand the base first; only then attribute).  Stream record:
  `docs/inbox/genesis-discipline.md`.


## ORCHESTRATOR VERDICTS #16 — BATCH 15 (2026-08-04 ~04:00), THE FIRST GATED BATCH
- genesis-7 delivered: (a) K1 AUTOPSY closed the accounting — K1 = R5 with
  2,117 deletions + 23 EDITED SURVIVORS (rvt.manipulate neutralise_referrers:
  a registry-indexed default FamilySymbol orphaned m_familyId->-1 with its
  Family deleted, surrogates nulled, a stair symbol un-hosted, schedule
  grid-intersection structs DROPPED, view state maps pruned); the certified
  reduction ladder is EDIT-FREE (pure maxgc); THE LAW: a referrer of removed
  content is DELETED WITH the content or LEFT BYTE-IDENTICAL — never
  neutralised into a state no Autodesk file exhibits. (b) The substitution
  ladder REBASED on certified K4 as PURE IN-PLACE substitution (zero
  registration motion; Global/Latest + ElemTable byte-identical to K4 per
  rung; only seq-102 object records change) — Y1..Y9 + Y_cat, all validate.
  (c) tools/probe_batch.py gate + retro audit: 31 of 35 historical FAILs
  VOID (21 K1-lineage, 9 G0/G1-assembly); BUG A (K5/K6) is VOID — the
  'singletons/catalog required' claims are NOT established.
- UPLOADED (batch_15.json, gated — every probe base certified): CTRL_R9_
  recheck_b15 + CTRL_K4_base_b15 (control + the batch's own base), Y1 (K4 +
  ONLY the pen table object in place — THE FIRST CLEAN CONSTRUCTED-OBJECT
  TEST OF THE CAMPAIGN), Y_cat (whole catalog in place), Y9 (deepest rung),
  K1a_editfree + K1_suspect (autopsy confirmation from certified R5).


## *** ORCHESTRATOR VERDICTS #17 (2026-08-04 ~04:15) — THE CONSTRUCTED LAYERS LOAD ***
- **ALL SEVEN PASS.** Controls CTRL_R9_recheck_b15 + CTRL_K4_base_b15 PASS
  (round valid, base re-confirmed).
- **Y1 PASS** — OUR pen table, our values, our constructor, in place on
  certified K4: LOADS. The first constructed object judged on a loadable
  base PASSES.
- **Y_cat PASS** — OUR complete 1,407-row built-in category/GStyle catalog:
  LOADS.
- **Y9 PASS** — the DEEPEST rung: settings layer + whole catalog + palette
  + datum (levels/phases) + view constellations ALL OURS in place: LOADS.
  Census: 1,333 of K4's 3,342 host elements are now OUR constructors'
  output; the residue = 2,009 elements in 11 named buckets (Yn.json) — the
  honest remaining queue to zero Autodesk-authored elements.
- **K1a_editfree PASS** (autopsy law confirmed: strip K1's survivor edits and
  it loads); **K1_suspect PASS** (the family-orphaning group alone is not the
  killer — another edit group is; remaining autopsy rungs name it at
  leisure).
- CONCLUSION: the constructors were right; the whole night of failures was
  the broken base. The in-place substitution mechanism is PROVEN across
  every layer we have. GENESIS = walk the 11 residue buckets (each a
  constructor + an in-place rung) — a queue, not a mystery.


## ORCHESTRATOR VERDICTS #18 (2026-08-04 ~05:50)
- **CTRL_Y9_base_b16 PASS** (round valid). **ZA_deep PASS** — the Group-A
  residue layer LOADS: +473 elements ours => 1,806/3,342 (54%) of the base
  is OUR constructors' output, viewer-proven. **Z_subcat PASS. Z_defs PASS.**
- **ZB_deep FAIL — but PARTIAL:** card reads Processing failed, yet the viewer
  OPENS it with a real view tree (3D view + sheet 'S101 - Framing Plans') and
  no error page — the extractor emitted views + a sheet before dying. => ONE
  of Group B's 8 buckets carries a real, SUBTLE constructor defect (a genuine
  finding, not a base artefact); Z_defs exonerated. UPLOADING NOW: the 7
  remaining Group-B singles (each = certified Y9 + one bucket) + a fresh Y9
  control to name the bucket.


## ORCHESTRATOR VERDICTS #19 (2026-08-04 ~06:20) — THE BUCKET IS NAMED: PALETTE
- Batch 17: CTRL_Y9_base_b17 PASS. Group-B singles: ZBs_mepcat, ZBs_pens,
  ZBs_annot, ZBs_filters, ZBs_machinery, ZBs_content ALL PASS (six buckets
  CLEAN); **ZBs_palette FAIL** — the ONE defective bucket (colour/material
  appearance palette). ZB_deep's partial failure is fully explained.
- Provable-ours now composable: Y9 (1,333) + ZA_deep's Group-A layer (+473)
  + Group B's SEVEN clean buckets (defs, mepcat, pens, annot, filters,
  machinery, content) — the composed ZAB_clean candidate would carry the
  large majority of the base as OUR constructors' output; the palette
  constructor is the single narrow fix outstanding.
- genesis-9: the DELETION stream completed (D_all/D_curtain/D_links/D_content/
  D_queue, all reduce-law EDIT-FREE, validator-clean, gate-admissible); the
  ASSEMBLY and REMAINING-A streams did NOT complete — REFUSED at the platform
  policy layer with an AUP citation. NOT retried; surfaced to the user as a
  governance signal intersecting the counsel review already booked. New
  fleet launches on the flagged framing PAUSED pending the user's decision.


## ORCHESTRATOR VERDICTS #20 — BATCH 20 UPLOADED (2026-08-04 ~09:00)
- genesis-10 delivered: PALETTE DEFECT DIAGNOSED + FIXED (a swapped
  (value,id) tuple in residue_b._int_param_set wrote param ids where values
  go across every structural/thermal property set — 78 swapped entries in
  the failing file; confined to two call sites; Z_palette_v2 = the corrected
  bucket + a swap-alone isolate that regenerates ZB5 byte-for-byte).
  REMAINING (A2): ZC_deep = 2,116/3,342 (63%) elements ours, only 4 elements
  in the whole base not in-place-able (each named with its operation).
  IFC-ROOM: end to end — placements recovered from world-baked vertices,
  Pset join key working, boards -> our PRL2X/PRL1X families, T1 ->
  transformer, walls/doors/clearances/feeder tree, the 2500 A switchboard
  honestly composed as a house family (factory refuses >600 A);
  electrical_room_2500a.rvt ON THE GENESIS BASE ZA_deep. IFC-FAMILY: the
  downlight .rfa from IFC facts (unstated wattage/lumens left NOT SOURCED)
  + L_downlight_loaded.rvt. The COMPOSER stream was REFUSED at the policy
  layer (2nd time; 4 of 5 sibling streams passed) — not retried; user asked
  to decide on doing the composition step directly.
- UPLOADED (batch 20): CTRL_ZA_deep_b20 (control), IFC_electrical_room_2500a
  (THE PRODUCT DEMO — our IFC in, our .rvt on our base out), ZC_deep (63%),
  Z_palette_v2 (the last bucket, corrected), L_downlight_loaded (our
  IFC-derived family instantiated in a project). Not uploaded this round:
  P_pal_swapfix, D_all, walls-only variant, the .rfa (viewer did not accept
  the family file directly).


## ORCHESTRATOR VERDICTS #21 (2026-08-04 ~09:45)
- CTRL_ZA_deep_b20 PASS (round valid). **ZC_deep PASS** => 2,116/3,342
  (63%) ours. **Z_palette_v2 PASS** => the last Group-B bucket clean; every
  genesis constructor layer certified. **L_downlight_loaded PASS** => our
  IFC-derived family loads. **IFC_electrical_room_2500a FAIL** (audit) — the
  first file CREATING new elements ON THE GENESIS BASE; the creation path
  onto the family-free genesis lineage is the new frontier; uploading the
  staged build-stage bisection + control next.


## ORCHESTRATOR VERDICTS #22 (2026-08-04 ~10:15) — TWO FINDINGS
1) CREATION ON THE GENESIS BASE WORKS: walls (unjoined + joined) PASS; walls
   + ONE loaded family + a PLACED instance (stage_L8_lp4) PASSES — loader +
   creation path proven on the family-free genesis lineage. The FULL-family
   stage FAILS => ONE FAMILY in the room's lineup is defective (suspect: the
   ad-hoc 2500 A house switchboard); per-family bisection names it.
2) LOAD IS NOT RENDER: the joined-walls file translates, but the model tree
   holds ONLY the level node ('L1 - Ground Floor [311]', ours) — created
   walls emit NO viewable geometry; the walls+panel file translates to
   'Design is empty'. Our files carry valid element DEFINITIONS but no BAKED
   geometry (the solids Revit computes on regen); desktop Revit regenerates
   on open (walls would very likely appear for the QA-seat engineer), but the
   cloud viewer's extractor does not regenerate — it draws baked geometry
   only. EVERY certification to date is a LOAD pass; VISIBILITY was never a
   gate. Datum renders because levels/grids draw from parameters.
- NEXT: genesis-11 RENDER TRACK — mine how a Revit-saved wall's baked
  geometry is stored (native vs created; do our sample-based V22/V24 walls
  carry it?), emit baked geometry for created walls, probe whether placed
  instances of our .rfa (which carry solids in the family document)
  render, bisect the family set. RENDER becomes a second gate alongside
  LOAD.


## ORCHESTRATOR VERDICTS #23 — THE COMPOSITION (2026-08-04 ~11:00)
- User directive: compose it myself, go. The existing tools/genesis_compose.py
  (built by the genesis-9 assembly stream before its report was cut off)
  PROVED CORRECT by its anchor: compose(Y9, Group-A rungs) == certified
  ZA_deep BYTE-IDENTICALLY (md5 56308637529a0d0a95976f5701e2615e).
- G_ABP = ZC_deep (certified, 63%) + Group B's 7 clean buckets + palette v2:
  724 slots transplanted, COMPOSED-VALID (validator 0 errors, Latest +
  ElemTable identical, four-registry coherent, law ok).
- G_ABPD = G_ABP's layers + the lawful D_all deletion set (maxgc closure,
  240 deleted; 19 substitute/delete overlaps resolved delete-wins): validator
  VALID 0 errors, 705 slots changed, EDIT-FREE, coherent. (The composer's
  own NOT-CLEAN verdict is only rung-fidelity bookkeeping at the 19
  deleted-by-design slots.)
- BATCH 23 UPLOADED: CTRL_ZCdeep_b23 (control = the base), G_ABP, G_ABPD —
  the deepest genesis candidates ever built. G_ABPD PASS = the composed
  genesis project base LOADS.
- Also: user set the multi-surface front door requirement (any AI surface;
  input = prompt / IFC / RVT; prompt->IFC via their Three.js flow is fine;
  ship in the plugin with skills, MCP documented as the future path) and
  chose the new product name: TEKTON (rename = one scripted sweep after
  trademark clearance; keep rev-revit internally until then; add clearance to
  the counsel list).


## ***** ORCHESTRATOR VERDICTS #24 (2026-08-04 ~11:30) — GENESIS LOADS *****
- Batch 23: CTRL_ZCdeep_b23 PASS, G_ABP PASS, **G_ABPD PASS**. Confirmed
  NOT an empty-design short-circuit: the viewer OPENS G_ABPD as a browsable
  model — a 3D view + sheet 'GEN-101 - GEN OVERALL PLAN' (our sheet
  vocabulary), no error page. => THE COMPOSED GENESIS PROJECT BASE LOADS: a
  project base whose settings, style catalog, palette, datum (levels/
  phases/grids), view constellations, sub-categories, annotation types,
  fonts, patterns, appearance assets, parameter definitions, MEP categories,
  pens, filters, machinery and content layers are ALL our constructors'
  output (2,840 landed slots + 240 lawful deletions), composed by
  tools/genesis_compose.py (anchor byte-exact), NO Autodesk-authored base
  content supplied — loads in Autodesk's reader. The user's day-one target
  is met: no base file required.
- Residue honestly stated: ~260 remaining Autodesk-authored elements + 4
  named stragglers (link symbol, DataStorage blob, one topology, link
  instance) + the two shipped product corpora (Formats/Latest schema +
  ESSchemaStorage unit schemas = counsel C4, present in EVERY Revit file,
  not element authorship). RENDER (baked geometry) is the separate second
  gate now solved in principle by the seq-103 GElement B-rep answer.
- genesis-11 corrections folded in: baked geometry = seq-103 GElement B-rep
  (same grammar famgen authors; native wall reproduced with ZERO differing
  leaves); RETRACT verdict #22's 'one defective family' — the failing delta
  is created WALLS + LOADED FAMILY DOCUMENTS TOGETHER (walls alone PASS,
  families alone empty-pass); instance placement on the genesis lineage is
  UNPROVEN pending the R_inst probes; our symbols/instances DO carry real
  solids.


## ORCHESTRATOR VERDICTS #25 — RENDER BATCH UPLOADED (2026-08-04 ~12:20)
- genesis-11 findings folded: baked geometry = seq-103 GElement B-rep (same
  grammar famgen authors; native wall reproduced with ZERO differing
  leaves); RETRACT verdict #22's 'one defective family' (stage_L8_lp4 was 8
  families + 0 walls + 0 instances; its PASS was an empty-design short-
  circuit); the failing delta is created WALLS + LOADED FAMILY DOCUMENTS
  together; our symbols/instances DO carry real solids.
- BATCH 25 UPLOADED: CTRL_render_b25 (control = the LOAD-certified walls-only
  base), wall_baked_min (ONE wall with authored seq-103 solid), RSOLID_walls_
  A_solid (4 authored wall solids on the certified walls-only base),
  R_inst_box (a placed instance of a minimal box family), F_msb + F_lp4
  (walls + ONE loaded family each = the combination bisection).
- The tekton front-door + plugin packaging fleet (wp5zrkaby) launched.


## ***** ORCHESTRATOR VERDICTS #26 (2026-08-04 ~13:00) — CREATION IS VISIBLE *****
- Batch 25: CTRL_render_b25 PASS; **wall_baked_min PASS; RSOLID_walls_A_solid
  PASS — AND RENDERS**: the viewer draws our 4 created walls (authored
  seq-103 GElement six-face solids) as a shaded 3D room shell casting
  shadows on the datum (screenshot captured). LOAD + RENDER both proven for
  created content. The render road WAS short: the archaeology answer
  (seq-103 GElement B-rep = famgen's grammar) + the emit stream's
  constructor, viewer-confirmed the same day.
- R_inst_box, F_msb, F_lp4 ALL FAIL => the remaining creation-path bug is
  NOT a family and NOT the switchboard: ANY embedded family unit combined
  with created content trips the audit. One named bug for the next round
  (diff a passing walls-only file vs a failing walls+one-family file at the
  partition/ElemTable/registry level; instances on the genesis lineage
  unproven until fixed).
- TEKTON FRONT DOOR + PLUGIN: SHIPPED — tools/frontdoor.py author
  {--prompt|--ifc|--rvt --edit} on the certified genesis base G_ABPD
  (sha256-pinned; sample bases refused; the walls+families open bug
  DETECTED and degraded honestly — PROOF-ONLY stamp or --strict split);
  plugin skills tekton-author / tekton-edit / tekton-inspect with bundled
  engine scripts + references; 'claude plugin validate' PASS; rev-revit.zip
  rebuilt (3.8 MB, genesis base bundled as an asset); worked examples ran
  end to end (the electrical-room PROMPT, the electrical-room IFC, a
  --strict split, a --rvt round-trip edit). Docs: MCP-PATH.md, RENAME.md,
  README.md, TRACKER.md, COUNSEL-BRIEF.md, coverage matrix refreshed.
- LOOP GOALS: (1) genesis loads — MET (#24); (2) front door packaged in
  the plugin — MET (#26). Bonus: creation is VISIBLE. Loop ends here.


## ***** ORCHESTRATOR VERDICTS #27 (2026-08-04 ~22:50) — ELEMENT-LAYER ENDGAME CLOSED *****
- Controls PASS (round valid). **RC_zero PASS**: the deepest genesis base —
  every remaining Autodesk-valued element landed or lawfully deleted,
  identity leak removed, 0 errors 0 warnings, ZERO never-landed Autodesk
  elements — LOADS. **RC_deep PASS. W1 PASS** (created wall with authored
  baked solid loads on the genesis base — render gate to confirm drawing).
  **WF_fix PASS and WF_nofix PASS** — the single-family probe does NOT
  reproduce the walls+families failure; attribution OPEN (the original
  failing file had 8 loaded families; next bisection = walls + N families
  ladder). **R_inst_downlight FAIL** (downlight-specific; panel/box
  placements passed earlier rounds).
- 2025 campaign: reduction ladder BUILT gate-clean to B2025_K4 (class census
  set-identical to certified 2026 K4); batch 17 staged with the untouched
  2025 sample as control; 2025 format facts pinned (4,600 classes, 4,430
  renumbered; ESSchemaStorage differs per release — counsel C4 covers both);
  KNOWLEDGE correction queued: 2662 = ADocument schema version in 2024/25/26,
  not a release marker.

- **W1 RENDER GATE PASS (~22:55)**: the 3D view thumbnail draws the created
  wall as shaded geometry among the datum lines — LOAD *and* RENDER for a
  created element whose object, registration, and baked solid are all ours,
  on the composed genesis base. Create-and-see closed for walls.


## ***** ORCHESTRATOR VERDICTS #28 (2026-08-04 ~23:05) — THE 2025 LINEAGE CERTIFIES *****
- ALL FOUR PASS: the untouched 2025 sample (control — the viewer reads 2025),
  R9_2025, K3_2025, and **B2025_K4** — the 2025 family-free base. The whole
  2025 reduction lineage certified in ONE round; the certified-2026 recipe
  transfers wholesale (class census set-identical).
- The genesis_base.json 2025 slot correctly awaits G_ABPD_2025 (the COMPOSED
  base with OUR content) — B2025_K4 is its certified foundation, not its
  fulfillment. LAUNCHING: the Y2025 substitution + compose campaign (the
  port stream's field maps + 2025 miners are ready) => G_ABPD_2025 => the
  data flip => native 2025 output from the front door.
- R_inst_downlight FAIL signature: 'Revit-InternalError' + extractor crash
  -1073741831 (a THIRD signature — not the corruption audit): the downlight
  FAMILY's content (likely the recessed-can cylinder geometry) crashes the
  extractor; placement mechanics exonerated (box + panel placements PASS).
  Queued: rebuild the downlight solid via the RSOLID-certified brep grammar.


## ORCHESTRATOR NOTES (2026-08-05 ~00:20) — 2023 CAMPAIGN COMPLETE + BATCH 31 UP
- 2023 fleet DONE: the first genuine format-era delta found and packaged —
  2023 element ids are 32-BIT (the schema's own Identifier v1 declaration;
  2024+ = v2 i64), rippling into record framing / in-body ids / ElemTable
  wire. rvt.versions.records32 keys off the DECLARATION, not the year, so
  2022-and-older may already read (unverified; same CDN pattern claims
  2016+). Read parity exact on all six 2023 samples; ladder R5..K4 clean;
  B2023_K4 = 4,171 elements. C4 now pinned across FOUR releases; 2662
  confirmed a frozen pre-2023 constant (release identity = BasicFileInfo
  Format alone).
- LATENT CORE BUG (from the width work): verify_manipulated builds its
  ObjectDecoder over the canonical 2026 schema instead of the file's own —
  a verification bug for 2024/2025 files too; records32.verify_manipulated32
  shows the fix (bind the file's own schema). QUEUED for the manipulate
  territory + a re-verification sweep of any 2024/2025 manipulate evidence.
- BATCH 31 UPLOADED (~00:15): CTRL_rstbasicsampleproject_b30 (the untouched
  2023 sample — control AND does-the-viewer-read-2023 probe), R9_2023,
  K3_2023, B2023_K4. Verdicts next wake.
- Fleet-mechanics lesson recorded by the stream, endorsed: written territory
  splits failed twice under concurrency; what held was MECHANICAL — pid
  lockfile in mutating entrypoints, from-disk arbiter as authoritative
  evidence, campaign-global batch numbering.


## ORCHESTRATOR — BATCH 32/29 UPLOADED (2026-08-05 ~00:55): THE TRIPLE ROUND
- INSTANCE-BUG A/B (fleet complete: two defects mined — D1 instance
  connector-manager class, D2 ContentTable GUID order — decomposing EXACTLY
  along the bisect axes; validator rules added; dead suspects measured:
  PartitionTable + StorageIndex byte-static even in Autodesk's own 53-unit
  file; placed instances are ADocument-unregistered on BOTH bases):
  CTRL_G_ABPD_b32 / BX_f1i1 (unfixed, expect FAIL) / BXfix_f1i1 (fixed,
  expect PASS) / BX_f2 (unfixed 2-load) / BXfix_f6i6 (fixed demo shape) /
  DEMO_250v_room_v2 (the USER'S PROMPT through the fixed path) / SX_f6i6
  (same op on the rst sample — cross-check). Unfixed-FAIL + fixed-PASS at
  the same rung = mechanism proven. Caveat: R_inst_box failed with NEITHER
  defect — residual axis possible.
- 2025 GENESIS CANDIDATE: CTRL_B2025_K4_b29 + G_ABPD_2025 (the COMPLETE
  composed 2025 base — anchor-proven, chain-faithful, deletion layer in).
  PASS => the registry flip => native Revit-2025 output.


## ORCHESTRATOR VERDICTS #31 (2026-08-05 ~01:20) — THE TRIPLE ROUND
CONTROLS: CTRL_G_ABPD_b32 PASS, CTRL_B2025_K4_b29 PASS, CTRL_rstbasic_b30
(2023) PASS — all three rounds VALID.
- **G_ABPD_2025 PASS => CERTIFIED.** The composed 2025 genesis base loads.
  FLIP APPLIED: registry slot certified (sha 6242c3aa...), KNOWN_RELEASES
  [2025].creation_certified=True, base bundled (zip 4079 KB). TODAY-tests
  flipping via agent; full 2025 authoring (three build-path gaps) fleet
  wcku94j48 stream build2025.
- **2023 ALL PASS => B2023_K4 CERTIFIED** (+ viewer-reads-2023 proven +
  the FIRST 32-BIT RE-EMISSION accepted: R9_2023, K3_2023). The 2023
  Y-compose campaign is unblocked (port2023 + records32).
- **Instance A/B: the fix set (D1..D5) is NOT the audit's objection.**
  BX_f2 (2 unfixed loads, no instances) PASS — multi-load tolerated, D2
  not fatal. BX_f1i1 unfixed FAIL / BXfix_f1i1 FIXED FAIL / BXfix_f6i6
  FAIL / DEMO_250v_room_v2 FAIL. THE KEY: SX_f6i6 (same op, RST SAMPLE)
  FAIL while famload-path L_v2 on the same sample is PASSED => the
  discriminator is the CODE PATH (famgen registration / instance-
  referenced baked symbol geometry), NOT base lineage. Residual fleet
  wcku94j48 stream residual: symbol_solid=False variant + famload-vs-
  famgen matched pair + famload-path N=6 cross-check.
- D1..D5 remain REAL corpus laws (validator keeps E1-E3; the core patches
  stay — the builders now emit lawfully) — they just aren't the audit's
  *fatal* objection on the instance axis.


## ORCHESTRATOR — THREE BATCHES UP (2026-08-05 ~02:00)
- b28 (2024): CTRL + R9_2024 + K3_2024 + B2024_K4 (the last uncertified
  release's round; CTRL also = does-viewer-read-2024).
- b34 (residual SPLITTER): CTRL_G_ABPD_b34 + BXns_f1i1 (no-solid symbol,
  byte-minimal 3-field delta vs failed BXfix_f1i1) + SL_f6i6 + SL_f1i1
  (famload-path instances at N=1/6) + BXns_f6i6. BXns_f1i1 PASS = baked-
  geometry hypothesis CONFIRMED; SL PASS = famload-path attribution airtight.
- b35 (native 2025 authoring): CTRL_G_ABPD_2025_b35 + ROOM2025_walls +
  ROOM2025_full — author --target-version 2025 now emits native 2025
  (finish-line test GREEN, five-gate emission check, bare-plugin proof).
  Read ROOM2025_full against ROOM2025_walls per the batch note.
- perm fleet CLOSED: matrix.py (21 cells, mechanical verify_evidence) +
  router.py + tools/route.py + 5 demos; convert-a/b cells to flip in
  matrix._IMPLS at integration. The validator regression it escalated was
  already resolved by the six core patches (builders comply with E1-E3).


## ORCHESTRATOR VERDICTS #32 (2026-08-05 ~02:25)
- b28 ALL PASS => B2024_K4 CERTIFIED. Roster complete: certified bases for
  2026/2025/2024/2023.
- b35: CTRL + ROOM2025_walls PASS => NATIVE 2025 AUTHORING VIEWER-CERTIFIED
  (prompt -> native 2025 file -> Autodesk loads it). ROOM2025_full FAIL as
  predicted (instance residual rides along, release-independent).
- b34: CTRL PASS; ALL FOUR probes FAIL (BXns pair + SL pair). Symbol-side
  hypothesis DEAD (no-solid fails); path attribution DEAD (famload instances
  fail; L_v2's PASS had zero instances). THE SURVIVING INVARIANT: instances
  of Autodesk-authored families pass (V20..V29); instances of OUR generated
  families fail — any base, any path, any symbol form, all corpus laws
  applied. Defect location: INSIDE our embedded family DOCUMENT content,
  deep-walked only when an instance references it. Next: hybrid-famdoc
  bisection (swap our famdoc subtrees against a dev-only extracted Autodesk
  famdoc until the verdict flips). This also subsumes the downlight thread.


## ORCHESTRATOR — BATCHES 36 + 37 UPLOADED (2026-08-05 ~02:55)
- b36 (2024 compose): CTRL_B2024_K4_b36 + G_ABPD_2024 (sha e4a40671,
  577,536 B, anchor-proven, 22-file chain byte-deterministic after the
  uuid4 fix) + Y9_2024 + Y7_2024. G PASS => apply the 2024 flip.
- b37 (famdoc hybrid bisection on the rst sample): CTRL_b37 + H7 (Autodesk
  famdoc through OUR famload + instance — machinery exoneration) + H1 (our
  geometry forms) + H2 (params/types) + H3 (datums) + H4 (views) + H5
  (connector) + H6 (inline-ADocument axis) + H8 (our famdoc verbatim —
  known-FAIL anchor). READING: H7 PASS + H8 FAIL frames the round; the
  hybrid(s) that FAIL name the guilty subtree(s). Diff checklist headline:
  geometry-history fields (m_geomSteps/m_pGeomTable) differ on the famdoc's
  OWN form elements; Autodesk famdocs carry a POPULATED inline ADocument
  (131 registries) where ours is all-null (the H6/H7 pair splits that).


## ORCHESTRATOR VERDICTS #33 (2026-08-05 ~03:10)
- b36 ALL PASS => G_ABPD_2024 CERTIFIED (+Y9+Y7). FLIP APPLIED below.
  Composed bases: 2026 + 2025 + 2024; 2023 compose queued on B2023_K4.
- b37: CTRL PASS; H7 FAIL = the decisive datum. An UNMODIFIED Autodesk
  famdoc through OUR famload + instance FAILS => famdoc content exonerated;
  the defect is in what famload AUTHORS around the family (host Family/
  FamilySymbol) or its registration. V20 passed because the native host
  pair + famdoc were untouched (only the instance was added). H1..H6 carry
  no axis info (shared machinery). NEXT (binary): H9 = donor famdoc loaded
  as a new unit BUT host Family/FamilySymbol authored as id-rebased BYTE-
  COPIES of the donor's own NATIVE host pair (V20-certified with
  instances) + placed instance. H9 PASS => defect exactly = famload's
  authored host elements (diff to the native pair = the fix spec, prime
  suspect the missing populated m_geomSteps/m_pGeomTable corpus form);
  H9 FAIL => defect = the unit/four-registry registration rows themselves.


## ORCHESTRATOR VERDICTS #34 (2026-08-05 ~03:55) — THE BINARY DECIDES
b38/b39 controls PASS. H9 FAIL + H10 PASS: the same file with/without one
instance — all content bytes Autodesk's. => The audit runs an INSTANCE-WALK
CROSS-CHECK against newly-registered units. H10 proves copies+registration
statically lawful; V20 proves instances of NATIVELY-registered units pass.
Surviving suspects, exactly two:
  (1) REGISTRATION ROW CONTENT — fields inside the CD/CT/FM rows famload
      authors (episode counts, versions, key metadata) vs native rows;
  (2) A FIFTH SURFACE — a project-ADocument reference keyed on content
      GUID/unit identity that the four-registry model never covered, whose
      entries only the instance walk visits.
BXhf/DEMO_v3 FAIL as expected under this hypothesis (symbol form was not
the binding axis). Commissioned: H11 (registration rows byte-modeled on
native shapes) + H12 (the COMPLETE byte-copy: famdoc + inline ADocument +
host cluster, only fresh registration + instance) + the fifth-surface hunt
(mine Global/Latest for ALL references to content GUIDs/unit identity of
native units; check which surfaces our loads leave unpopulated).


## ORCHESTRATOR — BATCH 40 UPLOADED (2026-08-05 ~04:20): THE CATEGORYTRACKING ROUND
Fifth surface NAMED by the exhaustive 203-surface identity sweep:
project-ADocument CategoryTracking (appinfo slot 28) — a COMPLETE 1:1
index of every unit-0 CategoryElem/GStyleElem (perfect on rst/rac/rme;
zero untracked anywhere in the corpus). famload's total project-ADocument
touch surface is FamilyMgr + ElementTrackingData + ContentTable — it NEVER
writes CategoryTracking. Unified reading fits every verdict, zero
counterexamples. Row forensics largely exonerated registration-row content
(FamilyMgr zero-diff; m_EpisodeCounts law proven 52/52 + ours coherent).
UPLOADED (control first): CTRL_b40, H13 (CategoryTracking-indexed — the
predicted PASS; 620/620 + 2187/2187 cross-certified), H12 (complete-copy,
untracked), H11 (native-modeled rows, untracked), H11x12 (both, untracked).
H13 PASS + others FAIL => the audit law is CategoryTracking totality =>
port: author the 8 index rows (+ the per-family category twin constellation
famload never builds — 41/41 native host families carry one) in famload +
famgen => DEMO v4 => close the hunt.


## ORCHESTRATOR VERDICTS #35 (2026-08-05 ~04:35) — THE CORNER HOLDS OUT
b40: CTRL PASS; H13 + H12 + H11 + H11x12 ALL FAIL. The hypothesis ledger
is now: symbol form / famdoc content / host elements / registration row
content / inline ADocument / CategoryTracking index / pairwise combos —
ALL byte-modeled on native, ALL rejected when instanced. Constants across
every FAIL: a newly-added unit + an instance referencing it; H10 (same
minus instance) and V20 (instance of native unit) PASS. The objection is
not a static identity delta our instruments can currently see.
TWO TERMINAL MOVES: (1) the exhaustive H12-vs-native WHOLE-FILE diff — H12
is mostly native bytes, so the complete difference list is small and
finite; enumerate EVERYTHING incl. sub-record layers (partition stream
envelopes, gzip framing, ECC pages, CFB directory order/entries) and probe
any untested axis (prime NEW suspect: the layers BELOW records — every
prior model compared decoded records, never the container envelope of the
new partition). (2) the desktop-Revit ask — one probe in real Revit yields
the SPECIFIC warning dialog the viewer never shows (prepared for the user).


## ORCHESTRATOR — BATCH 42 UPLOADED (2026-08-05 ~05:05): THE ENVELOPE ROUND
Terminal diff found FOUR sub-record discoveries no prior comparison saw:
(a) the 0x0f3f 64-byte per-unit footer blob (all 53 native units carry a
distinct high-entropy blob; OURS IS EMPTY — top suspect); (b) Autodesk's
gzip recipes cracked byte-exact (partition = zlib L3 Z_PARTIAL_FLUSH;
framed = Z_SYNC_FLUSH + aligned tail); (c) depage tail junk baked as data
after our units; (d) BFI rebrand + DIT scrub. ECC layer + gzip headers =
measured parity. UPLOADED (control first): CTRL_b42, E_ALL (all axes
flipped: 8/12 streams byte-identical to native), E1 (donor blob), E1b
(random blob — the content-vs-presence split), E3 (gzip recipes), E6
(tail junk removed), E4 (BFI), E5 (DIT), E2 (CFB directory). READING:
E_ALL PASS => envelope axis confirmed => singles name it => port + DEMO
v5; E_ALL FAIL => the in-file suspect space collapses to the blob CONTENT
function (E_ALL carries the donor blob, wrong if content-digested) +
API-invisible deferred axes => the REVIT-CHECK-KIT becomes decisive.
KIT READY: experiments/terminal/REVIT-CHECK-KIT.md (+ H12 + BXhf_f1i1
copies) — one page for a human with desktop Revit.


## ORCHESTRATOR VERDICTS #36 (2026-08-05 ~05:30) — THE HUNT ENDS AT 64 BYTES
b42: CTRL PASS; E_ALL PASS; E1 PASS; **E1b PASS** (random blob!);
E3/E6/E4/E5/E2 FAIL (all still empty-blob). THE LAW: Autodesk's audit
requires the 0x0f3f per-unit footer blob to be PRESENT (64 B) on any unit
an instance walks into; content is NOT verified (E1b). Our writers emitted
blen=0 — the single cause behind EVERY instanced failure since R_inst_box.
FIX APPLIED to core: factory.build_family_save_unit now emits the
deterministic 64-byte nonce (famdoc_adoc.build_footer; sha512 of our own
identity material — zero donor bytes); famdoc_adoc already emitted it.
Loader tests 43/43. DEMO_250v_room_v5 (the user's exact prompt; all 7
units blob-carrying; built in 18.2s) + fresh control CTRL_G_ABPD_b43
UPLOADED (~05:35). v5 PASS => the campaign's last product bug closes.


## ORCHESTRATOR VERDICTS #37 (2026-08-05 ~05:50)
CTRL_b43 PASS; DEMO_250v_room_v5 FAIL. The blob is NECESSARY, not
SUFFICIENT for our famdoc content. REFRAME: batch 37 (famdoc hybrids
H1..H6) is VOID for content attribution — every hybrid carried an empty
blob, which alone fails any instanced unit. E1b PROVES native-famdoc +
our loader + registration + blob PASSES. => The guilty axis IS in our
generated famdoc content after all, and the clean bisection is the b37
design RE-RUN WITH BLOBS (the fixed writer emits them automatically).
Commissioned: rebuild H1..H6 + BXhf_f1i1 through the fixed writer, stage,
upload — whichever hybrid FAILS with a blob names the subtree.


## ORCHESTRATOR — BATCH 44 UPLOADED (2026-08-05 ~06:20): THE CLEAN CONTENT ROUND
All units blob-carrying (machine-proven per probe). CTRL_rst_b44 +
CTRL_G_ABPD_b44 + B7 (donor+blob anchor; expect PASS per E1b) + B0 (our
famgen famdoc + blob, minimal product shape on G_ABPD) + B1..B6 (content
hybrids WITH blobs: geometry/params/datums/views/connector/inline-ADoc).
The FAILING hybrid names our guilty famdoc subtree; B0 PASS => DEMO v6 =>
close. DEMO v5 re-measured: its 7 units DO carry blobs — blob necessary,
not sufficient for our content; b37 voided (empty blobs).


## ORCHESTRATOR VERDICTS #38 (2026-08-05 ~06:35)
b44: BOTH CTRLs PASS; B7 PASS (machinery exonerated WITH blob); B1..B6 ALL
PASS (every single content axis of ours accepted); B0 FAIL (our complete
famdoc). => The defect is a COMBINATION of axes or the RESIDUAL FRAME
(our famdoc skeleton outside the six categories). Commissioned: U16 (donor
body + ALL SIX of our axes — fails => combination => pairwise; passes =>
frame guilty) + F1 (our famdoc with the donor FRAME swapped in — the
converse; passes => frame conviction confirmed + the frame diff is the
fix spec). Convergence is now mechanical: the axes are finite.


## ORCHESTRATOR — BATCH 45 UPLOADED (2026-08-05 ~07:05): COMBINATION vs FRAME
THE FRAME = 6 of our 41 famdoc elements in 3 groups (G1 self-Family with 15
differing fields; G2 UnitsElem; G3 project-view chain + 2 BrowserOrg the
donor references) + the OWNERSHIP topology delta (donor's UnitsElem/
DBViewProject are self-Family-OWNED; ours top-level). UPLOADED (CTRLs
first): U16 (donor + all six axes), F1 (our famdoc, donor frame — differs
from failing B0 by ONLY the frame), U12345 (union w/ our ADocument), H8B
(our famdoc via famload on rst — loader/base split), pairs U12/U15/U25,
frame singles F2/F3/F4. frame_diff.json = the ranked fix spec.


## ORCHESTRATOR VERDICTS #39 (2026-08-05 ~07:20)
b45: CTRLs PASS; U16 + U12345 + all pairs PASS; F1 + F2/F3/F4 + H8B FAIL.
INVERSION: the donor BODY accepts everything of ours; nothing swapped into
OUR document saves it. Our roster (41) = axes+frame, all individually
accepted — so the audit requires something the donor's remaining ~380 body
elements PROVIDE and our lean document LACKS (missing element
infrastructure), or a whole-document property (element order/unit shape).
NEXT: SUBTRACTIVE delta-debugging on U16 — delete the donor's extra
elements by CLASS-GROUP (sketch/curve infra; dims/constraints; refs;
views; tables; styles) until the PASS flips to FAIL; the flip names the
required class group; then bisect within it. Est. 2-3 rounds to the
exact requirement.


## ORCHESTRATOR — BATCH 46 UPLOADED (2026-08-05 ~08:00): THE SUBTRACTIVE LADDER
The donor's 411 non-frame elements partition into 7 class-groups (S1
sketch/geom 13, S2 dims 11, S3 datum/refs 19, S4 view/annot 85, S5
styles/cats/fonts 125, S6 nested Level-Head family 116, S7 struct/settings
42). UPLOADED (CTRLs first): SUB_ALL (U16 minus everything = the lean-shape
FAIL anchor), SUB_S5/S6/S4/S7/S2/S1/S3 singles, S5A/S5B halves, SUB_O1
(element-order permutation of our famdoc). The group whose deletion FLIPS
= the required infrastructure; author_spec.json sketches the famgen
authoring (classification laws: categories are annotation-attr FURNITURE
owned by style elements; nested families are complete inline mini-famdocs
registering their own 112 members; frame is hard-self-contained).
Caveat: deletion probes leave inline-ADocument registries dangling over
deleted ids (SUB_S2 0 .. SUB_ALL 359) — all-singles-FAIL signature =
disambiguate with a scrubbed-ADocument rebuild before conviction.


## ORCHESTRATOR VERDICTS #40 (2026-08-05 ~08:25) — THE LAYOUT CONVICTION
b46: CTRLs PASS; SUB_ALL + ALL singles + halves PASS; SUB_O1 FAIL.
SUB_ALL == F1 in logical content (donor frame + our 35 elements) but PASS
vs FAIL: constructed by DELETION-from-donor vs ASSEMBLY-by-famgen. => The
audit rejects our writer's PHYSICAL DOCUMENT LAYOUT (record order within
segments / arrangement / order-coupled framing), not our content. O1's
fail narrows: id NUMBERING alone is not it. THE MATCHED PAIR IS ON DISK:
SUB_ALL (PASS) vs F1 (FAIL), content-equal => their byte-level unit diff
is the COMPLETE remaining suspect list. Commissioned: the famdoc terminal
diff + morph probes (F1 re-emitted in SUB_ALL's physical order; the cross
pair) => the flip names the law => port to famgen emission => DEMO v6.


## ORCHESTRATOR — BATCH 47 UPLOADED (2026-08-05 ~09:00): THE FIELD-RESIDUE MORPHS
Layout-law fleet CORRECTED #40 by measurement: SUB_ALL/F1 were NOT
content-equal — 16 records differ, ALL in the self-Family record + header.
Pure ORDER is corpus-exonerated pre-upload (SUB_O1 FAIL with donor order;
B7 PASS with native order). 12 field-residue candidates separate the
29-file corpus perfectly; the standout: famgen emits DUPLICATE identityData
order-cell groups under one key (no PASS file has a dup key). UPLOADED:
CTRLs + M3 (order-cell dedup — TOP prior) + M5 (partType -1 both surfaces)
+ M4 (sparse counters) + M6 (m_deletion category prefix) + M1/M2 (order
transplants both directions, machine-proven pure) + BX_layout_f1i1 (the B0
recipe through layout_law normalization). DEMO v6 HELD pending the naming
verdict (one command behind). ALL-FAIL => BX_cat_gm/BX_types_5/BX_bip
famgen-chain probes (category top unprobed residue).


## ORCHESTRATOR VERDICTS #41 (2026-08-05 ~09:30)
b47: CTRLs PASS; M2 PASS (order exonerated BOTH directions); M1/M3/M4/M5/
M6/BX_layout FAIL. No single probed field is the law. SURVIVORS: the
entangled residues needing famgen-CHAIN rebuilds — the family CATEGORY
itself (+partType coherently), type-table shape, locked/param BIP,
materials group — possibly as a CONJUNCTION (the 12 co-vary; the audit may
demand category-consistent infrastructure, e.g. partType-14 panelboards
require panel-schedule machinery). Commissioned per the decision table:
BX_cat_gm (B0 recipe, category=generic_model through the whole chain),
BX_types_5 (5-row type table), BX_bip (locked BIP group), + BX_conj (all
famgen-side residues fixed at once — the conjunction upper bound).


## ORCHESTRATOR — BATCH 48 UPLOADED (2026-08-05 ~10:00): THE CONJUNCTION ROUND
Full famgen-CHAIN rebuilds (no byte surgery; catprobe.py scoped overrides):
CTRL_G_ABPD_b48 + BX_conj (ALL 12 corpus separators flipped incl.
refTypeIds — machine-verified) + BX_cat_gm (Generic Model -2000151 end to
end, partType -1 coupled) + BX_types_5 (donor blank-pair-first 5-row type
table) + BX_bip (mined -1001205 locked/palette shape, no value row) +
BX_conj_minus_cat + BX_conj_minus_types. READING: BX_conj PASS => the law
is inside the enumerated set (singles/minus rungs bisect); BX_conj FAIL =>
the in-file enumeration is EXHAUSTED (12/12 separators + order + blob +
machinery + registration all covered) => the desktop-Revit kit is the
next instrument. Corrections logged: donor famdoc row 18 is the -1005500
MATERIAL row; type-table law is blank-pair-first.


## ORCHESTRATOR VERDICTS #42 (2026-08-05 ~10:25) — THE HONEST TERMINAL STATEMENT
b48: CTRL PASS; BX_conj + every single + both minus rungs FAIL.
THE ENUMERATION IS EXHAUSTED. Measured and closed across 18 viewer rounds:
blob (NECESSARY, fixed in core), D1-D5 corpus laws (real, fixed in core),
machinery (exonerated by byte-copy), registration rows (exonerated),
CategoryTracking (exonerated), famdoc single axes (all exonerated), frame
(exonerated), envelope (gzip recipes cracked; exonerated), order (both
directions), the 12 perfect corpus separators flipped coherently — and a
famgen-ASSEMBLED famdoc under an instance still trips the audit while any
donor-DERIVED body (even reduced to our exact content) passes. One
unprobed sub-axis remains on record (sparse m_familyIds indices). THE
DECISIVE NEXT INSTRUMENT is desktop Revit's own error dialog: the
REVIT-CHECK-KIT (experiments/terminal/REVIT-CHECK-KIT.md + BXhf_f1i1.rvt
+ H12.rvt) is ready for a human with Revit. PRODUCT POSTURE (all
viewer-certified): native creation on composed bases for 2026/2025/2024
(+2023 base) — projects, walls (render), edits incl. foreign files,
family GENERATION (.rfa validate + famload-certified loading), the full
permutation router, the four-release version engine. The single open gap:
placed instances of generated families (ships stamped per the deliverable
rule; IFC companion + SUB_ALL-style famload-body path are the certified
alternatives meanwhile).


## ORCHESTRATOR — BATCHES 49+50 UPLOADED (2026-08-05 ~11:15): THE BIRTH LADDER
b49: CTRL_rac + CTRL_rst + CTRL_G_ABPD + TB0 (smallest model-instanceable
Autodesk-born famdoc, 381 recs, H7 recipe on its own host) + TB0r (rst
variant vs certified B7) + T0 (our famgen famdoc, T-ladder FAIL anchor).
b50: CTRL_G_ABPD + T2a (the genuinely Revit-BORN vendor standalone .rfa
famdoc, 1,992 elements, unmodified onto G_ABPD — birth-inheritance's
standalone test, buildable without any .rft). T2a PASS = birth theory
extends to standalone-born bodies + famload-onto-G_ABPD certified for
born content. The .rft ACQUISITION stream was BLOCKED by the safety layer
(downloading Autodesk installers from agent-guessed URLs exceeds the
relayed-comment authorization) — surfaced to the user with options; the
probe machinery is wired-and-waiting (rft_probe poll/build/stage; the
T2/T1 pipeline selftested end-to-end without an .rft). Findings landed:
standalone-ownership law (ElemTable stream, empty inline table); small-id
aliasing hazard fixed (schema-TYPED rebase); the born standalone carries
the FULL style catalog at birth (1,477 GStyles + 70 Categories) + the
blank-pair type table — strong birthright priors.


## ORCHESTRATOR VERDICTS #43 (2026-08-05 ~11:45) — THE BIRTH LAW CONFIRMED
b49/b50: ALL controls PASS; TB0 PASS; TB0r PASS; T2a PASS; T0 FAIL.
The field testers' template intuition is the law: Revit-BORN famdocs pass
through our whole pipeline (incl. famload onto the composed G_ABPD with
instances — now viewer-certified); famgen-assembled famdocs fail. PRODUCT:
the load-any-.rfa route is certified TODAY (user .rfa files are INPUTS,
not donors — the permutation matrix's rfa-in cell at full depth). THE FIX:
birthright authoring — famgen authors the template-birth set (style
catalog constellation, blank-pair type table, the field residue), mined
from born specimens, zero donors shipped. Commissioned: T1v (our content
injected into the born shell — sufficiency probe, dev-only) + birthright
v1 + DEMO v7.


## ORCHESTRATOR — BATCH 51 UPLOADED (2026-08-05 ~12:20): THE BIRTHRIGHT ROUND
CTRL_G_ABPD_b51 + T1v (our content alongside the born shell — sufficiency)
+ BX_birth (our famdoc through birthright: 1,683 authored birth elements,
machine-diff 78,399 fields equal / 0 mismatches, ZERO donor identity —
test-enforced) + DEMO_250v_room_v7 (the user's exact prompt through
birthright, 6 families, 34.8s). ALL PASS = the campaign closes.
NOTABLE: the born standalone CORRECTED several project-donor priors
(refTypeIds [], deletion prefix has NO category id, materials group
present-not-first, predefinedLimitIdx 35 = our default) — the corpus
discipline working as designed.
FLAGGED (compose territory, queued): the certified G_ABPD base carries an
Autodesk username in BasicFileInfo/DIT/ProjectInformation/TransmissionData
— inherited by everything built on it; scrub candidate for the next
compose pass (careful: the base is CERTIFIED — a scrub needs re-cert).
ALSO: the current intent grammar derives 0 walls from the demo prompt
(v3 had 4) — parser regression or vocabulary drift, queue with the 250V
vocab item.


## ORCHESTRATOR VERDICTS #44 (2026-08-05 ~12:45)
b51: CTRL PASS; T1v + BX_birth + DEMO v7 FAIL. RECONCILE WITH U16 (PASS):
our content in a born EMBEDDED shell via famdoc_final machinery on rst =
accepted; our content in the born STANDALONE shell via the NEW
template_union_doc machinery on G_ABPD = rejected. Three variables differ.
COMMISSIONED (single-variable): T1u (our content in the STANDALONE shell
via the OLD proven famdoc_final union machinery, on rst), T1r (T1v's
exact build instanced on rst instead of G_ABPD), U16g (U16's proven
famdoc famloaded onto G_ABPD). The axis that flips names machinery vs
species vs base. BX_birth's independent suspects (m_bShared adoption,
overlapping-class shortfall) stay queued behind that reading.


## ORCHESTRATOR — BATCH 52 UPLOADED (2026-08-05 ~13:20): THE THREE-AXIS SPLIT
CTRL_rst_b52 + CTRL_G_ABPD_b52 + T1u (standalone shell, OLD machinery, rst
— species axis) + T1r (T1v's byte-identical famdoc on rst — base axis) +
U16g (U16's proven famdoc on G_ABPD — base axis, proven side). Byte audit:
NO unit-content smoking gun; both machineries touch identical surfaces;
the one separable delta is host-side (authored empty-registry inline
ADocument vs born 131-populated). Watermark coincidence (rst == G_ABPD ==
1472524) enabled exact transplants. 8-outcome decision table pre-committed
in experiments/unionrec/probes.json.


## ORCHESTRATOR VERDICTS #45 (2026-08-05 ~13:50) — THE BASE IS CONVICTED
b52: both CTRLs PASS; T1u PASS; T1r PASS (T1v's exact bytes!); U16g FAIL
(U16's proven famdoc!). Machinery and species EXONERATED; the axis is
G_ABPD x loaded-famdoc. Discriminator in the record: T2a (PASS on G_ABPD)
is fully SELF-CONTAINED (31,054/31,054 refs in-unit); the G_ABPD-failing
famdocs carry host-resident refs (donor shell: 29; our famdocs: symbol
geometry binds host GStyle 118/124) which on G_ABPD resolve to OUR
SUBSTITUTED elements instead of born originals. HYPOTHESIS: the audit's
instance walk follows famdoc->host refs and objects to substituted
targets; self-containment sidesteps it. COMMISSIONED: SC1 (our content in
a fully self-contained famdoc — zero host refs, own style locals — on
G_ABPD), U16g25 (U16g's recipe on G_ABPD_2025 — lineage-vs-instance
split), HR1 (diff of the 29 host-ref targets rst-vs-G_ABPD — the exact
objection list). SC1 PASS => birthright v2 = self-contained authoring =>
DEMO v8 => the close.


## ORCHESTRATOR — BATCH 53 UPLOADED (2026-08-05 ~14:30): THE WALKED-BIND ROUND
HR1 FALSIFIED the blanket substituted-ref hypothesis (T2a references
substituted GStyles/Level/Phase + a deleted target and PASSES; also ships
the authored-empty inline ADocument). SURVIVING LAW: the WALKED-BIND
surface — born famdocs bind the instanced form's solid/fill/sketch styles
+ face render material IN-UNIT; ours bind -1; donor-embedded binds HOST
rows (worst: substituted MaterialElem 1177727 with a STRIPPED appearance
asset). T2a = the only in-unit-walk famdoc on G_ABPD = the only PASS.
UPLOADED: CTRL_G_ABPD_b53 + CTRL_K4_b53 + CTRL_G_ABP_b53 + SC1 (our
content, fully self-contained, walked-binds in-unit, machine-verified 0
host refs) + U16gK4/U16gABP (U16's byte-identical famdoc on the K4 /
pre-deletion G_ABP substrates — the base ladder replacing the
2025-blocked split) + DEMO_250v_room_v8 (the prompt through birthright v2
self-contained). Compose-side ALTERNATIVE fix specified in hr1_report
(author real appearance assets + cellLists on substituted rows).


## ORCHESTRATOR VERDICTS #46 (2026-08-05 ~15:00) — THE SPECIES READING
b53: all 3 controls PASS; SC1 + U16gK4 + U16gABP + DEMO v8 FAIL.
U16gK4's ref targets are byte-born and it still fails => target content
exonerated; walked-bind (as authored) insufficient. THE SURVIVING MAP:
pristine rst accepts EVERY species (T1r embedded-union, T1u
standalone-union, B7, TB0r); reduced bases accept exactly ONE — the
STANDALONE-BORN species (T2a, the only reduced-base load+instance PASS
ever). Embedded-species and our authored famdocs (which mimic the
embedded shape: inline-ADoc with 4 history GUIDs etc.) fail on ALL
reduced substrates (K4 / G_ABP / G_ABPD). UNTESTED DECISIVE CELLS:
(1) T1uG = T1u's standalone-shell+our-content file on G_ABPD (species x
reduced, ours-content); (2) TB0g = an embedded-born famdoc verbatim on
G_ABPD (species x reduced, born-content); (3) CD-stream forensics:
T2a-vs-SC1 registration into the same rebuilt-empty ContentDocuments
stream — any delta is the mechanism. T1uG PASS => the fix = author the
STANDALONE species shape (no history GUIDs, external ElemTable owners,
standalone inline-ADoc form) => birthright v3 => DEMO v9.


## ORCHESTRATOR — BATCH 54 UPLOADED (2026-08-05 ~15:45): THE HOSTSYM ROUND
Forensics FALSIFIED the ADocument species axis (T2a ships the same
authored embedded form as failing SC1; 7 diff paths all identity). THE
ONE authorable registered delta: the HOST SYMBOL TABLE — SC1 registered a
blank-named FamSymSurrogate and bound its instance to the blank pair; v8
shipped DOUBLE-blank host Family tables (0/36 native rows have either).
UPLOADED: CTRL_G_ABPD_b54 + T1uG (T1u's standalone-shell+our-content
famdoc byte-transplanted to G_ABPD — the decisive species-x-base cell) +
TB0g (TB0r's embedded-born famdoc on G_ABPD — declared deviation:
racadvanced wm 438,567 barred TB0's own) + BX_v3 (SC1's exact recipe
through birthright v3's hostsym lane — single-variable vs SC1) +
DEMO_250v_room_v9 (the prompt through v3: native [' ',real] m_idx-1 host
tables). New species datum: embedded-born famdocs carry EMPTY unit-side
type tables; standalone-born and ours carry blank-pair-first.


## ORCHESTRATOR VERDICTS #47 (2026-08-05 ~16:20) — THE IDENTITY COUPLING
b54: CTRL PASS; TB0g PASS (embedded-born famdoc on G_ABPD — species axis
DEAD, and extract->place gains base evidence); T1uG FAIL (same bytes pass
on rst); BX_v3 + v9 FAIL. THE LAW NOW: our-authored famdoc content fails
on REDUCED bases only; born content (either species) passes everywhere;
our content passes on pristine rst. Self-containment excludes references
=> the surviving coupling is ELEMENT-LEVEL IDENTITY/EPISODE state (our
elements minted against host episode identity; reduced bases' DIT/History
identity was rewritten in reduction — incl. the flagged foreign username;
born famdocs carry independent identity, immune). COMMISSIONED: the
identity forensics (TB0r-famdoc vs T1u-famdoc element identity fields:
m_history rows / episode stamps / GUID-bearing fields — the finite diff)
+ I1 (T1u famdoc with our elements' identity normalized to the born form,
on G_ABPD) + the famload DIT/History-write diff TB0g-vs-T1uG on the same
base. I1 PASS => birthright v4 = independent identity authoring =>
DEMO v10 => the close.


## ORCHESTRATOR — BATCH 55 UPLOADED (2026-08-05 ~17:05): THE FROZEN-BIRTH-ID ROUND
Identity forensics NAMED the coupling with a perfect 4-cell split: the
ParamElemFamily identity string revit.local.family:<session><8hex-id>-1.0.0
embeds the FROZEN BIRTH id — natives read SELF in their birth container
(363/363); transplants read OTHER; on G_ABPD all-OTHER=PASS (T2a 6/6,
TB0g 3/3), ours-SELF=FAIL (T1uG, SC1). Ours mint at the host watermark =
SELF. Rank-2: seq-101 m_abFlags4Bytes species-coherence. PREMISE
CORRECTION: G_ABPD's History/DIT are byte-inherited from rst UNCHANGED —
reduction never touched host identity surfaces. Host-side famload writes
IDENTICAL between the matched pair => famdoc-element-side coupling.
UPLOADED: CTRL_G_ABPD_b55 + I1 (T1u bytes with ONLY the 14 suffixes ->
frozen ids 7675..7688 + 12 born flag words — machine-enforced
single-variable) + BX_v4 (birthright v4 born-identity lane, single
variable vs BX_v3) + DEMO_250v_room_v10 (the prompt through v4, 84/84
OTHER). I1+BX_v4+v10 PASS = THE CLOSE.


## ORCHESTRATOR VERDICTS #48 (2026-08-05 ~17:50) — THE SECOND TERMINAL STATEMENT
b55: CTRL PASS; I1 + BX_v4 + DEMO v10 FAIL. The identity-string law was a
correlate. THE HONEST LEDGER after 26 single-variable viewer rounds: two
REAL laws found and fixed forever (the 64-byte 0x0f3f blob; D1-D5); every
other measurable axis surgically exonerated (symbol form, famdoc content
axes + frame + order + envelope + registration + CategoryTracking +
ADocument + hostsym + walked binds + self-containment + species + identity
strings + flags). THE PRECISE REMAINING CELL: our generated famdocs +
placed instances on OUR REDUCED bases only. Remaining unprobed micro-axes
(elemArr episode columns, parents structure, "content-birth") carry low
prior mass. THE DECISION TABLE'S BRANCH EXECUTES: desktop-Revit kit =
PRIMARY instrument (experiments/terminal/REVIT-CHECK-KIT.md).
THE PRODUCT CELL MAP (all viewer-certified):
- from-scratch projects: walls/geometry/edits CERTIFIED on 4 releases.
- OUR famdocs + instances on PRISTINE bases: PASS (T1r/T1u/U16 on rst) =>
  prompt-equipment INTO USER PROJECTS (add_to_project) rides the PASSING
  cell — the field workflow (add panels to THEIR project) works.
- bring-your-own-content on our bases: .rfa loads (T2a) + extract->place
  (TB0g) CERTIFIED.
- The ONE open cell: from-scratch equipment on from-scratch bases —
  gated on whatever desktop Revit's dialog names.
