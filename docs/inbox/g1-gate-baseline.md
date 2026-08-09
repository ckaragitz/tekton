# g1-gate-baseline — the status gate ledgers a build on OUR pinned base against the base's true residue (issue #143)

Stream `eng143` (engineer session for #143, P1, PG1 honesty). Territory used:
`tools/rvt_job.py` (the gate), `tools/ifc_intent.py` (`status_gate` pass-through),
`src/rvt/provenance.py` (one new provenance class + one kwarg), `src/rvt/frontdoor/manifest.py`
(one MANIFEST.md line), **new** `src/rvt/frontdoor/census.py` + `src/rvt/frontdoor/assets/genesis_census.json`
(the authorship census, mirrored into the plugin), **new** `tools/genesis_census.py` (derives the
census from tracked evidence), **new** `tests/test_status_gate.py` (in `tests/ci_shard.txt`).
No hot file touched (`base.py` is imported read-only; `versions/` used via `rvt.versions.reading`).

## Result in one screen

* **Before** (main `a5a853f`, `frontdoor author --prompt "an electrical room with 6 panels"`):
  `status_gate = {base_is_autodesk_sample: false, g1.verdict: "FAIL — 3,058 Autodesk-derived
  element(s) in expression-bearing categories", blocking incl. loadable-families transitive-cloned 6
  + family-types-symbols transitive-cloned 6 (OUR famgen families) + object-styles autodesk-sample
  1,591 + parameter-definitions 822 …, provenance_totals {autodesk-sample: 3,102, ours-created: 102,
  transitive-cloned: 16}, reason: "P0 genesis gate G1 fails (the base carries derived expression
  that G1 blocks) … Nothing built on a sample base is a product"}`. Cause, exactly as the issue
  says: `provenance_gate` ran `rvt.provenance` with the output's OWN composed base as the
  "Autodesk baseline", so every element inherited from OUR base read `autodesk-sample` and every
  created element referencing our own category styles / wall type read `transitive-cloned`.
* **After** (this branch, same command, all three targets, file delivered + `rvt_validate` 0 errors each):

  | target | base_kind | ours by composition | residue (byte-identical to ancestor) | G1 blockers | created | reason cites |
  |---|---|--:|--:|--:|---|---|
  | 2026 `G_ABPD` | pinned-composed-genesis | 2,680 / 3,102 | 422 (349 machinery, 35 coincident, 27 RC-year, 2 RC-preview, 9 straggler; 11 never authored) | **395** (was 3,058) | 118 ours-created, **0** transitive-cloned | G2 #19 · G3 #23 · residue #21; no "sample base" |
  | 2025 `G_ABPD_2025` | pinned-composed-genesis | 2,391 / 3,316 | 925 (585 never authored + 340 re-emitted identically) | 890 | 108 ours-created, 10 transitive-cloned (finding F2) | same |
  | 2024 `G_ABPD_2024` | pinned-composed-genesis | 2,355 / 3,278 | 923 (586 + 337) | 889 | 108 / 10 (F2) | same |

  Status stays the LABEL `PROOF-ONLY, NOT-DELIVERABLE` (G2/G3/residue genuinely open); the
  sentence ends "PROOF-ONLY is a label: the file is delivered." A base that IS an Autodesk sample
  keeps the v1 sentence verbatim ("…the base is an Autodesk sample project … Nothing built on a
  sample base is a product"); an explicit user `--base` with no census is worded as
  "user-supplied base with no authorship census" (everything inherited ledgered as the base's —
  nothing presumed ours).
* Wall time unchanged (steer #108): prompt job 10.4 s before / 10.4 s after (repo, `.venv`);
  bare unzip + system Python `go author` 8.4 s READY exit 0; the gate itself 0.7 s (was 0.75 s).
  The census lookup is one sha256 of the 580 KB base + a 38 KB JSON load.

## What was built

1. **The authorship census of the pinned bases** — `tools/genesis_census.py {build,check,show}`
   writes `src/rvt/frontdoor/assets/genesis_census.json` (schema `tekton.frontdoor.genesis-census/1`,
   keyed by base sha256, 38 KB, mirrored to `plugin/lib/…` by `sync_plugin.py`). For each certified
   pin it opens the pinned `.rvt` (ids + classes, under `rvt.versions.reading` for 2025/2024) and
   walks the composition chain from the compose manifest: every rung's certified report
   (`landed_slots`; `byte_delta.records_changed_ids` / `changed_ids`), aliases resolved
   (`Z_RA_2025 → RA_2025`, `Z_RB → RB → RB2_mepcat → RB1_defs`), recursively through `parent`
   until the file no rung produces (= the reduced sample K4 / B2025_K4 / B2024_K4, recorded as
   `ancestor`). `identical_to_ancestor` = base ids NO rung changed. **The law is the provenance
   instrument's own byte law** (byte-identical to the sample ⇒ `autodesk-sample`): slots our
   constructors landed but re-emitted byte-identically (content-free machinery, coincident
   designation facts) stay IN the residue — reported with their recorded disposition, never argued
   away — so the census claims nothing `tools/provenance.py --baseline all` would not on the
   owner's machine. **Cross-check:** on 2026 the chain method reproduces the byte-ground-truth
   `experiments/genesis/subst_k4/residue_c/census.json` (seq-102 compare vs K4, genesis-12 §1.1)
   **id for id: 422 = 422, 11 never authored** — which is what licenses the same method on
   2025/2024, where no byte census was ever tracked (their 585/586 never-authored counts equal
   `residue_after_RC_{2025,2024}.json` exactly).
2. **`rvt.frontdoor.census`** — `load()`, `for_file(path)` (exact-sha match or `None`),
   `BaseCensus{residue_ids, never_authored_ids, summary()}`.
3. **`rvt.provenance`** — new class `ours-composed` (`P_COMPOSED`, in `PROVENANCES`, not in
   `DERIVED`); `classify_elements(..., composed_residue_ids=)` / `provenance(..., composed_residue_ids=)`:
   baseline ids outside the residue → `ours-composed` (inherited or edited), residue ids keep
   `autodesk-sample`/`ours-modified`, the clone index is restricted to residue specimens and lineage
   only follows sample verdicts — so created content is `transitive-cloned` only through the true
   residue. Report gains `baseline_kind` + `composed{…}`; `format_report` prints one line. v1
   behaviour byte-for-byte when the kwarg is absent (multi-baseline forces it off).
4. **`tools/rvt_job.provenance_gate`** — looks the base up (`_base_census`, never for a
   sample-named path), passes the residue, records `base_kind ∈ {pinned-composed-genesis,
   autodesk-sample, user-base}` + `residue` summary, and words the reason by kind (`_gate_reason`,
   `PINNED_BASE_OPEN_GATES`). `tools/ifc_intent.status_gate` passes `base_kind`/`residue` through;
   `manifest.py` renders one "base authorship (issue #143 census)" line under Build.
5. **`tests/test_status_gate.py`** (10 tests, 14 s, fresh-clone): census asset current (rebuilds
   byte-identically) · covers every certified pin with residue in the hundreds · 2026 chain ≡ byte
   truth · census applies only to exact bytes · gate on each pinned base (kind, label, totals,
   blockers 100–1000 all `autodesk-sample`, reason cites G2/G3/#19/#21/#23, no "sample base") ·
   sample wording unchanged · user-base wording · end-to-end prompt job: 0 transitive-cloned, no
   loadable-families / placed-model-content / embedded-family-documents blockers, file delivered,
   MANIFEST.md line present.

## Findings

* **F1 — the ~260 of verdict #24 vs the 422 measured.** `genesis_base.json`'s
  `residue_disclosure` still says "~260 Autodesk-authored elements remain"; genesis-12 measured 422
  serialization-identical on the shipped `G_ABPD` (38 with genuine Autodesk values, 384
  machinery/coincident) and retired the 38 in `RC_zero` — which is certified but NOT the pin. The
  gate now reports the measured 422 with dispositions; re-pinning to `RC_zero` (issue #21's lane)
  drops it to 384 and `tools/genesis_census.py build` follows automatically (the test goes red on a
  re-pin without a rebuild). Not touched here: `genesis_base.json` wording belongs with the re-pin — filed as **#275**.
* **F2 — a real per-release gap the honest gate now surfaces.** On 2025/2024 our 4 walls reference
  `BasicWallType 600634` and our 6 loaded families reference `ElectricalLoadClassification 113944`,
  both still byte-identical to the Autodesk ancestor on those bases (the 2026-only rungs
  `ZC_systype` / `ZC_elec` were never ported to the 2025/2024 lanes — `residue_after_RC_2025.json`
  buckets "constructor-partial: BasicWallType 1", "constructor-exists: ElectricalLoadClassification
  18"). So 10 created elements are correctly `transitive-cloned` there and 0 on 2026. Follow-up
  filed as **#274** (port the two rungs to the 2025/2024 compose; owner-machine + viewer-gated).
* **F3 — instrument note.** `residue_c.census` needs the git-ignored K4 bytes; the rung-chain
  derivation needs only tracked JSON + the pinned file, and the two agree exactly on 2026. That
  makes the census reproducible in CI and on any contributor's clone — the asset is checked, not
  trusted.

## How to run

```bash
.venv/bin/python tools/genesis_census.py show          # one screen per pinned base
.venv/bin/python tools/genesis_census.py build         # after any re-pin (then tools/sync_plugin.py)
.venv/bin/python -m pytest tests/test_status_gate.py -q
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/g1 --json
python3 -c "import json;print(json.load(open('out/g1/manifest.json'))['build']['status_gate']['reason'])"
```

## BRANCH STATE

* Branch `cam/143-g1-gate-baseline` from `main@a5a853f`; PR closes #143.
* Files: `tools/genesis_census.py` (new), `src/rvt/frontdoor/census.py` (new),
  `src/rvt/frontdoor/assets/genesis_census.json` (new, generated), `src/rvt/provenance.py`,
  `tools/rvt_job.py`, `tools/ifc_intent.py`, `src/rvt/frontdoor/manifest.py`,
  `tests/test_status_gate.py` (new) + `tests/ci_shard.txt`, this record, a pointer header in
  `docs/inbox/frontdoor.md`; plugin mirrors regenerated by `tools/sync_plugin.py`
  (`plugin/lib/src/rvt/{provenance.py,frontdoor/census.py,frontdoor/manifest.py,frontdoor/assets/genesis_census.json}`,
  `plugin/lib/tools/{rvt_job,ifc_intent}.py`, `plugin/skills/*/scripts/{rvt_job,ifc_intent}.py`).
* Gates: `tests/test_status_gate.py` 10 passed; neighbours `test_frontdoor test_router test_job
  test_provenance test_plugin_sync test_bootstrap test_coldstart test_surface_perf
  test_plugin_validate` (counts in the PR); `sync_plugin.py --check` clean; `validate_plugin.py`
  PASS (24 assertions); portable paths ok (2718); bare unzip `go author` READY 8.4 s; three CLI
  runs (2026/2025/2024) delivered + `rvt_validate` 0 errors (1/0/0 warnings — the standing
  DataStorage ES-blob decode gap on 2026).
* Shipped vs staged: everything ships with the merge; no viewer claim (the pinned bases' bytes are
  untouched — the census READS them), so no probe batch.
