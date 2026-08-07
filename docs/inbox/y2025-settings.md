# Y2025 SETTINGS + CATALOG RUNGS (Y1..Y7_2025 on the CERTIFIED B2025_K4) — workstream record

Stream: **y2025-settings** (2026-08-04, evening).  Charter: mirror the
certified 2026 substitution ladder's Y1..Y7 onto the **viewer-certified**
2025 family-free base `experiments/genesis2025/reduce/B2025_K4.rvt`
(VERDICTS #28 — the whole 2025 reduction lineage certified in one round;
`docs/coverage/viewer-certified.json` lists the base as `certified`, so the
v3 engine's `assert_certified` gate ACCEPTS it — **no `--allow-uncertified`
anywhere in this stream**), using port2025's adapted constructors + the
frozen 2025 miners, all writer work inside
`tools/genesis_2025.py::context_2025`.

**DONE conditions met: Y1_2025..Y7_2025 + the two single-change probes
Y1s_2025 / Y6s_2025 ALL BUILT and VALID — every rung validator 0 errors
(in-context), byte-delta-vs-parent asserted (only that layer's seq-102
records changed; ADocument + ElemTable byte-identical), registry parity,
four-registry coherence 1/0/0 — probes.json written (bisection-first,
every entry citing verdict #28 + the staged control), and the
`tools/probe_batch.py` standing-controls gate reads the batch ADMISSIBLE.**

Driver: `src/rvt/genesis/y2025_a.py`
(`PYTHONPATH=src .venv/bin/python -m rvt.genesis.y2025_a`, ~30 s).
Tests: `tests/test_y2025_a.py` — **24, all green, 0 skips on this machine**.

---

## 1. THE LADDER — nine rungs, all VALID (built 23:11–23:12)

Base: `B2025_K4` (sha256 `276be333493b6c5c…`, 851,968 B, 3,333 host
elements, 1/0/0/0 four-registry coherent).  Engine:
`tools/genesis_substitute_v3.py` IMPORTED and re-pointed (rung table,
`build_for`, `_class_id` swapped process-locally; v3 itself untouched).
Mechanism per rung: `rvt.regadd.substitute_elements` — in place, seq-102
object record only, keep_row, verify+diff.

| rung | layer | parent | landed | changed | unchanged (byte-identical) | bytes | verdict |
|---|---|---|--:|--:|--:|--:|---|
| Y1_2025 | project pen table | BASE | 1 | 1 | 0 | 851,968 | VALID |
| Y2_2025 | browser orgs + navigator constellation | Y1 | 12 (9 role + 3 donor) | 9 | 3 | 851,968 | VALID |
| Y3_2025 | struct/join/keynote singletons | Y2 | 5 | 2 | 3 | 778,240 | VALID |
| Y4_2025 | MEP settings + size tables | Y3 | 8 | 8 | 0 | 774,144 | VALID |
| Y5_2025 | remaining settings/trackers | Y4 | 51 | 11 | 40 | 774,144 | VALID |
| Y6_2025 | the COMPLETE 2025 catalog in place | Y5 | 1,165 | 1,165 | 0 | 770,048 | VALID |
| **Y7_2025** | patterns + materials + palette PROPERTY SETS | Y6 | **60** | 60 | 0 | **753,664** | **VALID** |
| Y1s_2025 | single-change: pen only | BASE | 1 | 1 | 0 | 851,968 | VALID |
| Y6s_2025 | single-change: catalog only | BASE | 1,165 | 1,165 | 0 | 851,968 | VALID |

Per rung, asserted and recorded in `<rung>.json` (verdict = VALID only if
ALL hold; `tests/test_y2025_a.py::test_rung_valid_with_all_assertions`
re-checks every one):

* validator **0 errors / 2 warnings** — the exact E/W class of the
  certified base itself; independently re-run through the 2025 context for
  all 9 rungs + the base (`ok=True errors=0 warnings=2` × 10).
  **CAUTION for other streams: standalone `tools/rvt_validate.py` (no
  release context) reads `errors=4` on EVERY 2025 file — including the
  certified base and Autodesk's untouched sample.  That is the 2026-baked
  CLI framing, not a file defect; in-context validation is authoritative
  (finding §5.1).**
* byte-delta assertion table HOLDS: only `Partitions/20` differs, changed
  ids == the landed slots exactly (unexpected_changed = ∅), **0 ids added,
  0 removed**, per-seq order identical, changed seqs ⊆ {102},
  **`Global/Latest` + `Global/ElemTable` byte-identical to the parent**.
* registry parity (`parity.latest_byte_identical` — by construction,
  asserted), regdiff registration sample identical (6/6 per rung).
* four-registry coherence **1 unit / 0 ContentDocuments / 0 ContentTable**
  every rung (the family-free shape preserved).
* retarget self-check 0 failures (every re-targeted body schema-clean +
  byte-exact re-encodable), 0 dangling refs, **port2025 adaptation stamped;
  0 records dropped as 2026-only** (no rung constructs the conductor
  catalog).
* `versions.detect_release` reads all nine emitted files as **2025**.

Single-change identity: **Y1s_2025 is byte-identical to Y1_2025**
(md5 both) — determinism proven; the manifest notes one upload can serve
both names.  Control: `CTRL_B2025_K4_base.rvt` staged, md5
`1da9813c15efa2a9…` == the certified base exactly.

## 2. THE 2025-SPECIFIC CONTENT — verified on the emitted bytes, not assumed

* **Y1 pen scale keys (charter: verify, never assume)** — preflight
  `pen_scale_key_check` decodes the base's OWN project pen table (elem 2,
  m_famId -1) BEFORE Y1 builds: model scales **[10, 20, 50, 100, 200,
  500]**, 16 pens per scale, perspective/draft markers -1 — exactly our
  constructor's `PEN_SCALE_BREAKPOINTS`; `match=True` recorded in
  probes.json; a mismatch aborts the ladder.  (Confirms the port stream's
  mining with a per-run mechanical gate.)
* **Y2 browser layer** — all 10 emitted BrowserOrganizations carry
  `m_sortParamId` (the 2025 field), zero `m_sortParameter`.  The
  **BrowserOrganizationTracking v6→v5** map (2026's type→org map → three
  2025 ElementId fields) is an ADocument REGISTRY concern an in-place rung
  never writes: `adocument_identical=True` asserted on Y2's byte-delta, and
  the port2025 HOOKS carry all three tracking fields (tested) for the
  composer/assembler path that does write the ADocument.
* **Y4 corrected 2025 defaults** — on disk in `Y4_2025.rvt`:
  `RbsWireSettingsElem` 102129 carries the three 2025-only doubles
  (`m_dMaxVoltageBranchSizing` 0.02, `m_dMaxVoltageFeederSizing` 0.03,
  `m_dAmbientTemperature` 303.15000000000003 K); `RbsWireSizesElem` has NO
  `m_bInitialized` and the 2025 map order.
* **Y6 the 2025 catalog** — built from the 2025-MINED tables (loaders
  redirected for the run): our records **1,399** (the 2025 profile; 2026
  builds 1,407), landing the base's 1,165 rows 1:1 with **234
  ours-not-landed** (2025 enum keys the R9_2025 lineage GC'd away — the add
  path's queue, exactly the 2026 pattern).  The **four keys whose header
  flag word differs between releases** (`-2000710..713:1`) carry
  **0x400201e** in the emitted rows of Y6_2025 AND Y6s_2025; decisive
  constructor-level proof: `catalog.builtin_style_catalog` emits
  0x400200e/1,407 rows ambient (2026) and **0x400201e/1,399 rows inside
  `y2025_context`** — the swap reaches the constructor, and the restore
  leaves the 2026 path untouched.
* **Y7 the palette laws (the 2026 palette lesson)** — the union rung lands
  60 slots: X7's 22 (4 line + 5 fill patterns, 13 house materials) + the
  corrected palette bucket (10 extended surplus materials + **17
  structural + 11 thermal PropertySetElement** re-valued over each slot's
  OWN skeleton — `rvt.genesis.residue_b2`, viewer-certified as
  Z_palette_v2).  On the emitted bytes, all 28 property-set slots:
  **0 swapped (value,id) int-param entries** and **every param array in
  ascending param-id order** (`residue_b2.swapped_int_entries` /
  `param_ids_ascending` over the decoded file); present-empty ElementId
  sets; 0 family mismatches in the role traces.  Residue left honestly:
  18 AppearanceAssetElem + 4 surplus fill + 3 surplus line patterns (no
  constructor / surplus — a removal rung's business).

## 3. HOW IT RUNS — the context discipline

`y2025_a.y2025_context(base, out_dir)` =
**`genesis_2025.context_2025(base)`** (versions.reading + the SEVEN
module-local 2026-baked framing constants + `adocument._DECODER`) **+ the
port-layer swaps** (`encode._DEFAULT_ENCODER`, `regadd/regdiff
ObjectDecoder` → the 2025 pin, `V3._class_id` → by-name 2025 resolution,
the two catalog loaders → the frozen 2025 tables, `V3.RUNGS` → the 2025
rung table, `V3.build_for` → the X7P dispatcher wrapped in the
port2025 `adapt_record` adapter).  Everything restores on exit (the 24-test
run enters/exits the context repeatedly in one process, and the ambient
2026 catalog build still produces the 2026 shape afterward).

The Y7 union's plan safety: the X7 half is planned PROVISIONALLY first
(`plan_inplace` is pure), the palette half claims only the slots that plan
leaves free (4 unconsumed X7 role-sibling material slots were reclaimed by
the extended materials — listed in the report), every palette slot is
already in X7's old_ids so referrer ranking / slot-fill ordering are
unchanged, and the final merged plan is therefore identical for the X7
records.

## 4. THE MANIFEST + THE GATE

`experiments/genesis/subst_k4_2025/probes.json` — 9 entries,
**bisection-first: Y7_2025 (deepest — one PASS proves the whole settings +
catalog + palette chain on 2025), then the singles Y1s_2025 / Y6s_2025,
then Y6..Y1_2025 deep→shallow**.  Every entry: base =
`experiments/genesis2025/reduce/B2025_K4.rvt` + its ledger entry + the
**verdict #28 citation**, the ONE thing it tests, if_PASS / if_FAIL, the
recorded certifications, and the control.  Also recorded: the pen
verification, the Y1s/Y1 byte-identity, and the gate result.

**The standing-controls gate was RUN and ADMITS the batch**
(`tools/probe_batch.py check <all 9> --manifest .../probes.json` →
"ADMISSIBLE — `stage` will add the certified control"; every entry's base
resolves `[certified]`).  Nothing was staged into `experiments/acceptance/`
and nothing uploaded (orchestrator's call):

```
tools/probe_batch.py stage experiments/genesis/subst_k4_2025/Y*.rvt \
    --manifest experiments/genesis/subst_k4_2025/probes.json
```

(The gate proposed `experiments/genesis2025/reduce/R9_2025.rvt` as its
control source; adding a certified-2026 control alongside separates
"oracle broken" / "2025 rejected" / "this rung rejected" as in the port
stream's protocol.)

## 5. FINDINGS for other territories (none applied by me)

1. **Standalone `tools/rvt_validate.py` is 2026-framed**: `errors=4` on
   every 2025 file including the certified base and the untouched sample;
   in-context it reads the same files 0-errors.  One more datum for the
   versions stream's proposal (genesis-2025-reduce §4 / genesis-2025-port
   §4) to fold the framing patch set into `rvt.versions` — the validator
   CLI should detect the release per file and wrap its walk.
2. **Concurrent-stream observations** (coordination, not defects):
   `experiments/genesis/subst_k4_2025/compose/` appeared at 23:10–23:12
   (a composer stream; its `G_Y2025_anchor.rvt` at 23:10 predates my rungs
   — composed from the port stream's `experiments/genesis2025/subst/`
   ladder, not mine; my Y*.rvt finalized 23:11:38–23:12:04, write-once).
   `tools/sync_plugin.py --check` shows drift ONLY on
   `src/rvt/genesis/port2024.py` (a 2024-port stream's in-flight file,
   23:14) — NOT synced by me on purpose; my `y2025_a.py` is already in the
   plugin byte-identically (a sibling's 23:11 sync picked it up).
3. For the Y8/Y9 stream: `previously_landed` over the chain
   Y1_2025..Y7_2025 protects all 1,302 landed slots; the palette traces +
   correspondence live in `Y7_2025.json` (`landed_slots`, `ours_tmp` per
   slot) — `prior_correspondence` resolves cross-rung references exactly as
   in 2026.  Y7_2025 is the parent to build Y8_2025 on.

## 6. WHAT THE VIEWER ROUND DECIDES

* **Y7_2025 PASS** ⇒ every settings/catalog/palette constructor this
  stream owns loads at Autodesk's 2025 registrations; G25's remaining
  element-layer work is the Y8/Y9 datum+view rungs + residue, then compose
  → `experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt` (the
  front-door `genesis_base.json` releases.2025 slot).
* **Y7_2025 FAIL** ⇒ Y1s_2025 (one pen object) and Y6s_2025 (catalog
  alone) bracket the layer; then the intermediates deep→shallow — the
  first FAIL whose parent PASSED convicts exactly that rung's class layer,
  every registration variable eliminated by construction.

## SUITE RESULT

Full suite `.venv/bin/python -m pytest -q --continue-on-collection-errors`
launched 23:15 from the repo root (prior streams' runs took ~31 min wall);
tail lands in
`/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/y2025a_suite_result.txt`.
Known when closing this section:

* `tests/test_y2025_a.py`: **24 passed, 0 skipped, 0.90 s** (standalone,
  twice, after the final artifact build).
* This stream edited NO existing source, tool, or test file (purely
  additive: one new module, one new test module, artifacts, this record),
  so the expected full-suite delta vs the last counted baseline is **+24
  passes**; the count is updated below when the run lands.

**FINAL COUNT (run completed):** see the BRANCH STATE addendum below.

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — no git branch work (repo has no
  commits; integration is the orchestrator's).
* NEW (this stream's territory):
  * `src/rvt/genesis/y2025_a.py` — the glue (rung table, X7P union,
    y2025_context, pen preflight, manifest writer, gate check, driver)
  * `tests/test_y2025_a.py` — 24 green
  * `experiments/genesis/subst_k4_2025/` — `Y1..Y7_2025.rvt+.json`,
    `Y1s_2025.rvt+.json`, `Y6s_2025.rvt+.json`, `CTRL_B2025_K4_base.rvt`,
    `probes.json` (the `compose/` subdirectory there is a SIBLING stream's
    — untouched by me)
  * this record
* Touched OUTSIDE territory: **NOTHING** — no `src/rvt/**` (other than my
  new module), no tools, no existing tests; every cross-release adjustment
  is a process-local swap inside `y2025_context` (restored on exit; §5
  findings are reported, not applied).  Read-only use of the port stream's
  frozen 2025 pins (`experiments/genesis2025/subst/*.json`, mtimes
  unchanged) and of `residue_b2`'s certified constructors.
* DONE check: **Y1..Y7_2025 (+ the two singles) all VALID with every
  charter assertion (validator 0 errors, byte-delta only-that-layer's
  seq-102, registry parity, four-registry coherence) + probes.json + the
  gate ADMISSIBLE.**  STOP at READY: nothing uploaded, nothing staged into
  `experiments/acceptance/`, no certification claimed for any Y*_2025 —
  every verdict is the viewer session's to issue.
