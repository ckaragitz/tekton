# GENESIS 2025 — THE REDUCTION LADDER (G25-1 + G25-2): sample → B2025_K4

Stream: **genesis-2025-reduce** (2026-08-04).  Charter: re-run the certified
2026 recipe (rstbasic → maxgc R-rungs → K3 usage-nulls → K4 family-free,
four-registry coherent) on Autodesk's Revit-2025 rst basic sample, gate
EVERY rung on validator-0-errors + `rvt.reduce_law.assert_edit_free` + the
four-registry census, pin the 2025 format data the creation side needs, and
stage the viewer batch (viewer signed out — nothing uploaded; the
orchestrator uploads when the session returns).

**DONE conditions met: B2025_K4 exists, validator-clean, law-clean,
four-registry coherent; format facts pinned (`docs/writer/format-2025.md`);
batch staged (`experiments/genesis2025/batch_17.json` + `probes.json`).**

Driver: `tools/genesis_2025.py` (subcommands ladder / k3k4 / formats /
stage / all).  Tests: `tests/test_genesis_2025.py` (22, all green).

---

## 1. THE LADDER — every rung validator-0-errors + law-clean + censused

**Sample chosen: `samples/2025/rstbasicsampleproject.rvt`** — because the
certified 2026 lineage (R5..R9 → K3 → K4 → substitution → G_ABPD) was
built on the RST BASIC sample and this campaign is the mechanized re-run
of that exact recipe (plan §2/§3: same lineage sample or the comparison
means nothing); it is also the smallest of the six samples, exactly as in
2026.  Shape on load: 13,861 host elements, 31,936 ids file-wide, 53 save
units = 52 embedded family documents — the same 52-document count as the
2026 rst sample.  Everything ran inside
`rvt.versions.reading` + the `context_2025` patch set (§4).  Seeds are the
certified 2026 seeds (`rvt_reduce.stage_seed_v2`), deletion is maxgc, the
emitters are the certified `rvt.reduce.delete_elements` /
`genesis_triage.remove_documents` — no new mechanism was invented.

| rung | recipe | deleted | kept | size (B) | structural | validator E/W | reduce_law | units/CD/CT/FMguids |
|---|---|--:|--:|--:|:--:|:--:|:--:|:--:|
| R5_2025 | annotation + schedules (maxgc) | 5,279 | 8,582 | 5,963,776 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 |
| R6_2025 | + views except {3D}+Level 1 | 5,601 | 8,260 | 5,898,240 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 |
| R7_2025 | + unused types/materials/patterns | 6,847 | 7,014 | 5,500,928 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 |
| R8_2025 | + options/phases/links/topologies | 6,865 | 6,996 | 5,500,928 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 |
| R9_2025 | + family layer hosts + placed model | 10,164 | 3,697 | 3,293,184 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 |
| K3_2025 | R9 + loadable-family USAGE nulled | 0 (modify) | 3,697 | 3,293,184 | ok | 0/2 | modify: 9 edits, **exactly the neutralised set** | 53/52/52/52 |
| **B2025_K4** | K3 − family layer − ALL 52 docs, 4-registry | 364 elems + 52 units | **3,333** | **851,968** | ok | **0/2** | **EDIT-FREE** (vs K3) | **1/0/0/0 COHERENT** |

Verdict lines pasted (validator + law), per rung — the driver aborts the
ladder on any non-green, so these are the actual gate outputs:

```
[R5_2025] deleted 5,279 / kept 8,582 | 5,963,776 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52
[R6_2025] deleted 5,601 / kept 8,260 | 5,898,240 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52
[R7_2025] deleted 6,847 / kept 7,014 | 5,500,928 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52
[R8_2025] deleted 6,865 / kept 6,996 | 5,500,928 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52
[R9_2025] deleted 10,164 / kept 3,697 | 3,293,184 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52
[K3_2025] layer 364 elements (13 loadable families); referrers edited 9; edits==neutralised: True; validator_ok=True (errors 0); units 53 CD 52 CT 52 FM 52
[B2025_K4] docs removed 52 (units 53->1, CD 52->0, CT 52->0, FM 50->9); layer deleted 364; 851,968 B; structural=True validator_ok=True (errors 0); law=EDIT-FREE; residual-guid-bytes 0; units 1 CD 0 CT 0 FM 0 coherent=True
```

* `reduce_law.assert_edit_free` for every REDUCTION rung compares against
  the byte state of its parent over all three record seqs (the k1-autopsy
  instrument): R5..R9 vs the untouched sample, B2025_K4 vs K3_2025 — all
  **EDIT-FREE, 0 survivors edited, 0 ids added** (the 2026 K1 lesson
  enforced mechanically; the driver raises and stops on violation).
  The literal guard outputs:

```
[EDIT-FREE] R5_2025 vs rstbasic-2025 (sample): removed 5,279, added 0, common 26,657, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R6_2025 vs rstbasic-2025 (sample): removed 5,601, added 0, common 26,335, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R7_2025 vs rstbasic-2025 (sample): removed 6,847, added 0, common 25,089, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R8_2025 vs rstbasic-2025 (sample): removed 6,865, added 0, common 25,071, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R9_2025 vs rstbasic-2025 (sample): removed 10,164, added 0, common 21,772, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] B2025_K4 vs K3_2025: removed 18,439, added 0, common 3,333, SURVIVORS EDITED 0 (vindicated 0)
```

  (The `common` universe counts EVERY save unit's records, so untouched
  embedded family documents are proven byte-identical too; B2025_K4's
  `removed 18,439` includes the 52 spliced documents' record ids.)
* **K3_2025 is the one declared MODIFY rung** (exactly the certified 2026
  K3 recipe — usage nulls via the M3-certified path, viewer-certified as
  its own probe in the 2026 round 5).  The law instrument
  (`check_reduction`, non-raising) proves: **removed 0, added 0, survivors
  edited 9, and the edited set == the neutralised-referrer set EXACTLY**
  (`edits_are_exactly_the_neutralised_referrers: true`).  Edit classes =
  the 2026 K3 signature verbatim: SectionAttributes ×2, LevelAttributes,
  ViewportAttributes, GridAttributes, InteriorElevAttributes, CalloutTag,
  StructSettingsElem, CopyWatchProperties.  Policy consulted:
  `reduce_law.law_policy().permits("neutralise-referrers", "research-probe")`
  → ALLOW-NOTED; K3_2025 goes to the viewer as its own candidate-base, and
  B2025_K4's verdict is only read with K3_2025's (the 2026 protocol).
* Four-registry census every rung (save units − 1 == ContentDocuments
  entries == ContentTable records == FamilyMgr doc-GUIDs): 52/52/52/52
  through K3; **B2025_K4 = 1 unit / 0 / 0 / 0** — zero embedded documents,
  all four registries coherent, **residual GUID bytes in
  Latest+ContentDocuments = 0**.  (FamilyMgr keeps 9 entries with zero doc
  GUIDs — the curtain-wall SYSTEM families, exactly the 2026 K4 shape.)
* Validator depth (not just the verdict): B2025_K4 = 12 streams, 23
  partition blocks, 10,002 records, 3,333 elements decoded, 52,319 refs
  checked, 1 decode failure (the pre-existing Extensible-Storage blob gap
  class every release shows) — 0 errors / 2 warnings, the same E/W class
  as the untouched 2025 sample in the versions stream's parity table.
* On-disk framing proof: every partition block header of every emitted
  rung carries the 2025 SegmentMarker ordinal **0xed9** (checked directly:
  `{0xed9}` is the complete header-tag set of B2025_K4's 23 and R9_2025's
  230 blocks; walker 0 errors) and `versions.detect_release` reads every
  rung as **2025**.

### B2025_K4 vs the certified 2026 K4 — the shapes match

| | K4 (2026, viewer-certified) | B2025_K4 |
|---|--:|--:|
| elements | 3,342 | 3,333 |
| save units / CD / CT | 1 / 0 / 0 | 1 / 0 / 0 |
| class census | — | **set-identical: no class present in one and absent from the other** |
| loadable families removed | 13 | 13 (same names: section/level/grid/callout/elevation heads, A1 metric, M_View Title, M_HSS Square-Column, boundary condition) |
| embedded documents removed | 52 | 52 |

The 9-element count difference is the small per-release content drift
inside shared classes (e.g. slightly different numbers of style rows), not
a structural difference.

## 2. THE 2025 FORMAT DATA — pinned (`docs/writer/format-2025.md`)

Machine-readable: `experiments/genesis2025/format_facts_2025.json`.
Highlights (full tables in the doc):

* **Formats/Latest 2025**: 484,585 B, 4,600 classes, sha256 `c964f9aa…`
  (matches the `rvt.versions` pin; byte-identical across all six 2025
  samples — re-verified).
* **Class diff 2026→2025** (by NAME, both schemas parsed fresh): 4,584
  shared names, of which **4,430 RENUMBERED** and only 154 keep their
  ordinal; **106 classes only in 2026** (enumerated — includes the whole
  conductor catalog + numbering machinery of plan §5a.1); **16 only in
  2025** (enumerated — none constructed by genesis).  Confirms the
  versions stream's counts exactly.
* **ESSchemaStorage / product corpus 2025**: 1,174 (typeid,json) pairs in
  two tables (889 unit + 285 spec/parameter-group), **1,120,410 B**,
  corpus sha256 `5331797d80e9a0ad…`, byte-identical across all six 2025
  samples.  2026 reference measured with the same instrument: 1,315 pairs
  / 1,333,340 B.  **The corpora differ materially between releases (the
  spec table 285 vs 422 pairs) — per plan §7, the counsel C4 brief should
  name both** (2025: 1,120,410 B `5331797d…`; 2026: 1,333,340 B
  `99554c01…`).
* **Identity markers**: BasicFileInfo `Format: 2025`, build
  `Development Build`; ElemTable lead tag 0x5ab (=ElemTable), footer tail
  class 0x93b (=IdentifierSource); History lead tag 0x51d — all ordinals,
  all round-trip through the decoders automatically.
* **FINDING (corrects a KNOWLEDGE.md gloss)**: the Global/History
  upgrade-version list ends **2662 in 2024, 2025 AND 2026** (190 entries,
  identical list), and **ADocument's schema `version` stamp is 2662 in all
  three releases' own schemas** — 2662 is NOT "Revit 2026"; the document
  format version froze at ≤2024 and the release-authoritative marker is
  BasicFileInfo `Format:` (what `rvt.versions.detect_release` keys on).
  A 2025 (or 2024) writer writes 2662 unchanged.

## 3. THE STAGED VIEWER BATCH — `experiments/genesis2025/` (batch 17)

The viewer is signed out; nothing was uploaded.  Staged through the
`tools/probe_batch.py` gate (`stage_batch`, batch_n=17 — continuing the
global numbering; `experiments/acceptance/` holds 15–16):

| order | file | kind | base (declared in probes.json) |
|--:|---|---|---|
| 0 | `CTRL_rstbasicsampleproject_b17.rvt` | control | byte-identical copy of `samples/2025/rstbasicsampleproject.rvt` (md5-verified == the 2025 sample, != the 2026 one) |
| 1 | `R5_2025.rvt` | candidate-base | the 2025 sample |
| 2 | `R9_2025.rvt` | candidate-base | the 2025 sample |
| 3 | `K3_2025.rvt` | candidate-base | `reduce/R9_2025.rvt` |
| 4 | `B2025_K4.rvt` | candidate-base | `reduce/K3_2025.rvt` |

* **Every 2025 file is a candidate-base** — nothing 2025 is in the ledger
  yet, so nothing here is a "probe" in the gate's sense; certification
  cascades down the lineage (a parent FAIL voids its children — encoded in
  `probes.json` per-entry if_PASS/if_FAIL).
* **The control doubles as plan risk #1's answer** ("does the viewer
  accept 2025 uploads at all?"): it is Autodesk's own untouched 2025
  bytes — certified by construction (`probe_batch` `sample` status).  If
  the CONTROL fails, the oracle cannot read 2025 uploads and every other
  verdict in the round is VOID (`read_batch_verdicts` handles this).
* `probes.json` follows the probe_batch schema (BASE_KEYS `base` +
  `parent_rung`; `probe_batch.resolve_base` verified to resolve all four
  from both the staged copies and the reduce/ originals).
* Basenames are collision-free vs every prior upload (2026 rungs were
  `R5.rvt`/`K4.rvt`; these are `R5_2025.rvt`/`B2025_K4.rvt`).
* Recommended reading order (also in the manifest): control → R5_2025 →
  R9_2025 → K3_2025 → B2025_K4.
* Canonical paths for the ledger + future base declarations: the
  `reduce/` originals (`experiments/genesis2025/reduce/B2025_K4.rvt` …) —
  that is the `file` field of each batch entry, so a candidate-base PASS
  certifies THAT path; substitution rungs (G25-3+) should declare
  `"base": "experiments/genesis2025/reduce/B2025_K4.rvt"`.

## 4. THE BAKED-TAG FINDING — plan §7's named risk was REAL, in SEVEN places

`rvt.versions.reading` patches `rvt.partitions` module globals — but the
EMIT path keeps module-LOCAL copies of the framing ordinals that the patch
cannot reach.  Running the ladder without fixing these would have written
**2026 block tags into 2025 files** (silently, since our own walker would
then be patched to read them back).  Found by grep before the first emit,
patched (and restored) by `tools/genesis_2025.py::context_2025`:

| module.attr | kind | 2026 value baked | used by |
|---|---|---|---|
| `rvt.reduce.BLOCK_TAG` | local literal (reduce.py:59) | 0x0F28 | `NewBlock.frame` — every re-blocked block header |
| `rvt.reduce.BLOCK_TRL_TAG` | from-import of writer | 0x0F21 | block trailer mirror |
| `rvt.manipulate.BLOCK_TAG` / `.TRAILER_TAG` | from-imports of partitions (manipulate.py:76) | 0x0F28/0x0F21 | the modify path's block re-framing (K3) |
| `rvt.commit.BLOCK_TRL_TAG` | from-import of writer | 0x0F21 | commit re-framing |
| `rvt.writer.BLOCK_TRL_TAG` | module constant | 0x0F21 | `reframe_blocks` |
| `rvt.famgen.factory.CD_SEPARATOR` / `CD_END_RECORD` | packed literals (factory.py:1469-71) | 0x3A3/0x3A2 | ContentDocuments parse/assemble (K4's registry-coherent doc removal) — 2025 needs 0x391/0x390 |
| `rvt.adocument._DECODER` | cached 2026-schema decoder | whole 2026 class map | `decode_latest`/`encode_latest` defaults — the ADocument registry reconciliation must decode with the FILE's schema |

`context_2025` is the working recipe (patch on enter, restore on exit,
verified by `tests/test_genesis_2025.py::test_context_2025_patches_and_
restores_every_local_tag`).

### Proposed cross-territory diff (versions stream / orchestrator — NOT applied)

Fold the local copies into `rvt.versions.activate` so `reading()` covers
the emit path too.  Sketch (`src/rvt/versions/__init__.py`):

```python
# after the partitions patch in activate():
_LOCAL_COPIES = (
    ("rvt.reduce", "BLOCK_TAG", "BLOCK_TAG"),
    ("rvt.reduce", "BLOCK_TRL_TAG", "TRAILER_TAG"),
    ("rvt.manipulate", "BLOCK_TAG", "BLOCK_TAG"),
    ("rvt.manipulate", "TRAILER_TAG", "TRAILER_TAG"),
    ("rvt.commit", "BLOCK_TRL_TAG", "TRAILER_TAG"),
    ("rvt.writer", "BLOCK_TRL_TAG", "TRAILER_TAG"),
)
# + famgen.factory CD_SEPARATOR/CD_END_RECORD from CONTAINER_CLASS/
#   UNIT_INNER_CLASS, + adocument._DECODER from the active schema.
# Patch lazily (only modules already in sys.modules, or import-on-demand);
# record prev values in the same restore dict reading() already keeps.
```

The long-term fix is for those modules to read `partitions.BLOCK_TAG` at
call time (one-line changes in reduce/manipulate/commit) — then only the
famgen + adocument patches remain.  Until either lands, any 2025 emit MUST
go through `genesis_2025.context_2025` (the tests pin this).

## 5. PROPOSED KNOWLEDGE.md / versions.md touch-ups (orchestrator merges)

1. KNOWLEDGE.md "Partitions" bullet — "upgrade format-version list (ends
   **2662 = Revit 2026** in all six)" → 2662 is the ADocument schema
   version in 2024/2025/2026 alike (§2 finding); the parenthetical should
   read "ends 2662 — the ADocument schema version, stable 2024–2026".
2. docs/inbox/versions.md open question "the 2025 `Global/Latest`
   unit/spec corpus + `ESSchemaStorage` pins (campaign step G25-0)" →
   ANSWERED: pins live in `docs/writer/format-2025.md` §3 /
   `format_facts_2025.json` (this stream ran the G25-0 measurement).
3. genesis-2025-plan.md §3 G25-1/G25-2 status → rungs BUILT + staged
   (batch 17), awaiting viewer certification; §7 "tool assumptions" risk →
   CONFIRMED + patch set documented (§4 above).

## 6. TESTS + SUITE

* `tests/test_genesis_2025.py` — **22 tests, all green, 0.33 s**
  (context patch/restore; per-rung validator/structural/law verdicts;
  K3's edits==neutralised invariant; four-registry coherence incl.
  B2025_K4 = 1/0/0/0; B2025_K4 detects as 2025 + walks clean with 1 unit;
  staged control byte-identity (== 2025 sample, != 2026 sample); probes
  lineage resolvable via `probe_batch.resolve_base`; format pins match
  `rvt.versions`; class-diff confirms the plan's portability table; the
  2662 release-stability finding).  Every artifact-dependent test skips
  cleanly off this machine.
* Full suite: see SUITE RESULT below.

## SUITE RESULT

Full suite (`.venv/bin/python -m pytest -q --continue-on-collection-errors`)
launched 22:36 from repo root; **still running at record-close** (the prior
stream's run took 31:45 wall).  The tail of its output lands in
`/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/suite_result.txt`
(orchestrator: read it there, or re-run the command).  What is known now:

* `tests/test_genesis_2025.py` (this stream's 22 tests): **22 passed, 0.33 s**
  — run standalone twice after the final artifact regeneration.
* `tools/sync_plugin.py --check`: "plugin in sync with source (deny-audit
  clean, assets verified)", exit 0 — re-verified after all writes.
* This stream edited NO existing source or test file (purely additive:
  one new tool, one new test module, artifacts, two new docs), so the only
  deltas vs the versions stream's counted baseline (**1,284 passed /
  4 failed / 5 skipped / 1 collection error — all five defects pre-existing
  and in other streams' territories, see docs/inbox/versions.md §SUITE**)
  are +22 passes from `tests/test_genesis_2025.py`, i.e. the expected
  full-suite outcome is **1,306 passed / 4 failed / 5 skipped / 1 error**
  unless another concurrent stream moved the baseline.

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — no git branch work (repo has no
  commits; integration is the orchestrator's).
* NEW (this stream's territory):
  * `tools/genesis_2025.py` — the driver (context_2025 patch set, ladder,
    K3/K4, format facts, staging)
  * `experiments/genesis2025/reduce/{R5,R6,R7,R8,R9}_2025.rvt+.json`,
    `K3_2025.rvt+.json`, `B2025_K4.rvt+.json` (sha256 B2025_K4
    `276be333493b6c5c…`, 851,968 B)
  * `experiments/genesis2025/{probes.json, batch_17.json,
    CTRL_rstbasicsampleproject_b17.rvt, R5_2025.rvt, R9_2025.rvt,
    K3_2025.rvt, B2025_K4.rvt}` (the staged batch),
    `experiments/genesis2025/format_facts_2025.json`
  * `docs/writer/format-2025.md`
  * `tests/test_genesis_2025.py` (22 green)
  * this record
* Touched OUTSIDE territory: **NOTHING** — no `src/rvt/**`, no existing
  tool or test edited; the §4/§5 diffs are PROPOSED, not applied.
  `experiments/genesis2025/subst/` (portability-2025.json + builtin
  category/style profiles, 22:35–22:36) belongs to a SIBLING stream
  (constructor retarget, G25-3) — untouched by me; no file collisions
  (mine are `reduce/`, the batch files and the two manifests).
* DONE check: **B2025_K4 validator-clean (0 errors) + law-clean
  (EDIT-FREE vs K3_2025; every reduction rung EDIT-FREE vs its parent) +
  four-registry coherent (1/0/0/0, residual GUID bytes 0); format facts
  pinned; batch staged with the sample control.**  STOP at READY: nothing
  uploaded (viewer signed out), nothing certified, no substitution rungs
  run — B2025_K4 is a CANDIDATE base until the orchestrator's viewer round
  reads out; `KNOWN_RELEASES[2025].creation_certified` stays False.
