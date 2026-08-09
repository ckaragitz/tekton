# perf-family-load — N families in ONE host pass + per-stage timings (issue #124)

Stream: `eng124` (engineer session under the tech-lead session; branch
`cam/124-family-load-batch`). Refs #124, #110 (latency epic), #108 /
S-2026-08-09-g (latency is first-class on the plugin/skill path; done only
with a measured before/after from a bare surface). Follows PR #237 (ECC
encoder, 22 s → 10.6 s on its VM) and PR #141 (lazy ifcopenshell); leaves
the schema-cache memo to #183 (its share is measured below, not touched).

## 1. What was built

1. **`rvt.famgen.loader.load_families_into_project(host, out, products)`** —
   the batched component loader. `products` are `FamilyProduct`s or
   callables `f(start_id) -> FamilyProduct` (each family is regenerated above
   the ids the previous one allocated, exactly the ladder the chain produced).
   ONE `survey_host`, every family authored + round-trip-gated in memory
   (`_author_load`, the front half now shared with the single loader), ONE
   `Global/Latest` decode → N `register_in_host_adocument` → ONE encode +
   re-decode proof, N GUID-sorted `ContentDocuments` inserts, ONE
   `commit_new_elements` (every host element of every family into save-unit 0
   + ElemTable), N `splice_save_unit` in load order, ONE `write_cfb`, ONE
   `verify_loaded_projects` (file-level checks once, per-plan slices).
   Returns `BatchLoadResult{ok, out_path, loads[LoadResult…], shared,
   stop_reason, first_failure}`. The loader is single-pass and honest: a
   family whose authoring gates fail stops the batch *there* (the id ladder
   needs every earlier family) and the prefix is written; the file is
   verified once and every family gets its verdict. The *policy* — keep the
   deepest good prefix, and if a written family fails verification drop it +
   everything after it and load the prefix again (one more pass, logged) —
   lives in the front door's `stage_load_batched`, so the chain's "deepest
   good load" degrade is unchanged and a bad family costs a pass, never the
   families before it.
   The single `load_family_into_project` now runs on the same three helpers
   (`_author_load`, `_edit_host_registries`, `_commit_and_write`) and
   `verify_loaded_project(path, plan)` is the one-plan view of
   `verify_loaded_projects` with its historical report shape (every proofs
   key the tools/tests read is preserved — pinned by a test).
   `provenance_ours` accepts the already-open `FamilyIndex`.
2. **`rvt.frontdoor.build.stage_load_batched`** — stage L of the build in
   one host pass (same record shape as `tools/ifc_intent.stage_load`:
   `loads/loaded/final/n_loaded/blocker` + the private hand-offs to stage E,
   plus `mode`, `host_passes`, `shared_proofs`, `verify`). `_stages/` now
   holds `stage_L_loaded.rvt` (+ `.load.json`) instead of
   `stage_L0_base … stage_L6_pp6` (14 files → 3 for the flagship job).
   `tools/ifc_intent.py` is untouched (out of territory; its own `room` CLI /
   the certified `stage_L8` lineage keep chaining), and so is
   `rvt.convert.add_to_project`, which still calls the chained
   `R.stage_load` — see follow-ups.
3. **Per-stage wall time in the manifest**: `BuildResult.as_json()` now
   emits `stages` (it never did — `build.stages` was `null` in every
   manifest), and every stage (F, L, specimens, W, E, C, V) runs inside one
   `_timed_stage` context that stamps `seconds` (perf_counter, 0.01 s) on
   its entry — one clock for the whole column; V additionally carries the
   per-gate split `gates: {validate, census, identity, status_gate}`.
4. **`tools/surface_bench.py`** reads the breakdown back
   (`stage_breakdown()` → `JobResult.breakdown` → JSON + one line per author
   job in the markdown notes: `job 8.8s = F 4.5s · L 1.6s (1 pass, 6/6) ·
   … · V 1.7s`) and gains the flagship job **`go-author-6panels`** ("an
   electrical room with 6 panels") in the default job order, so the number
   this epic tracks is a standing measurement, not a one-off.

## 2. Evidence — before/after (this VM: cloud CCR, 4 vCPU Xeon @ 2.80 GHz, Python 3.11.15)

Bare surface exactly as DONE (3): `tools/sync_plugin.py` → unzip
`tekton-plugin.zip` to a temp dir → `/usr/bin/python3` (**no numpy, no
olefile**) → `skills/tekton-author/scripts/_bootstrap.py go author --prompt
"…" --out out/jN --json`, env scrubbed of `TEKTON_ROOT`/`RVT_*`. BEFORE zip
built from `main @ a0183b7` (post-#237/#141/#245), AFTER zip from this
branch; every run READY, `result.ok true`, exit 0, combined file VALID 0
errors. "cold" = the first process in a fresh unzip (no `.pyc`), "warm" =
later processes (no cross-process cache exists on this path; warm ≈ cold).

| measure (bare `/usr/bin/python3`, no numpy) | BEFORE (`main`) | AFTER (this branch) | ratio |
|---|---|---|---|
| `go author` **6 panels** — `go.job_seconds`, cold (1st process after unzip) / 2nd | **15.41 / 14.41 s** | **8.52 / 9.08 s** | 0.55–0.63× |
| same, warm, 3 runs (median) | 14.82 / 15.80 / 15.08 (**15.08 s**) | 8.54 / 8.58 / 8.89 (**8.58 s**) | **0.57× (−43 %)** |
| same, process wall (warm median) | 15.35 s | 8.81 s | 0.57× |
| same job re-measured on the FINAL tree (after the `/simplify` pass), zip rebuilt: warm ×3 / fresh-unzip cold | — | 8.60 / 8.15 / 8.47 s; cold 9.19 s ¹ | 0.54–0.61× |
| `go author` **1 lighting panel** — job_seconds cold / warm ×2 | 3.84 / 4.31 / 4.65 s | 3.84 / 3.90 / 3.91 s | 0.87–1.0× (not slower) |
| L stage (6 families), manifest `build.stages[L].seconds` | n/a in manifest (`null`); in-repo A/B with the chained `ifc_intent.stage_load` wired in (intermediate commit of this branch): **7.62 s**, 6 host passes | **1.5–2.0 s**, 1 host pass | ~0.23× |
| container rewrites for the L stage (6 families) | 6 (+6 pass-1 temps) | **1** (+1 pass-1 temp) | |
| `_stages/` files for the 6-panel job | 14 (7 × ~0.6 MB `.rvt` + 6 `.load.json` + walls) | 3 | |
| `surface_bench --zip … --python-bare /usr/bin/python3` cowork **go-author-6panels** | **15.4 s** | **9.0 s** | 0.58× |
| surface_bench cowork go-author-prompt (1 panel) / author-prompt / edit-roundtrip / validate | 3.7 / 4.4 / 1.8 / 0.9 s | 3.8 / 4.4 / 1.9 / 0.9 s | flat |
| surface_bench codeexec go-author-6panels | 15.6 s | 9.8 s | 0.63× |
| surface_bench session total cowork / codeexec (9 calls, incl. the new job) | 26.8 / 28.8 s | **20.6 / 22.9 s** | 0.77× / 0.80× |
| in-repo (`.venv`, numpy present) 6-panel `frontdoor.py author` build.seconds, `--target-version` 2026 / 2025 / 2024 | 16.6 s (chained A/B, 2026) | **10.4 / 10.8 / 10.1 s**; L = 1.73 / 2.02 / 1.96 s, 1 pass each | |

¹ One final-tree run taken seconds after `sync_plugin.py` re-zipped on the
same disk read 18.6 s, *all of it in stage F* (13.8 s vs its usual 4.8 s —
code this branch does not touch; L was 1.96 s in that run) and is discarded as
host contention, exactly as #237's record discarded its 22.9 s run; the seven
quiet final-tree runs agree within 1.1 s.

Issue target (adapted DONE): a further ≥ 30 % off the 6-panel job vs this
VM's own baseline → **met: −43 % warm (15.08 → 8.58 s), −45 % cold
(15.41 → 8.52 s)**; the original issue's ≤ 12 s absolute target (from a 22 s
baseline) is met with margin; the 1-panel job is not slower (3.84 → 3.84 s
cold, 4.48 → 3.91 s warm median). Per-stage AFTER (warm, bare, 6 panels):
**F 4.5 s · L 1.6 s (1 pass, 6/6) · specimens 0.15 s · W 0.3 s · E 0.3 s ·
V 1.5 s** = job 8.5 s.

(surface_bench's `author-ifc` FAIL on both numpy-less columns is the
pre-existing #127, unchanged by this branch; the bench exits 1 for it in both
runs.)

### Output equivalence (chain vs batch) — proven, not assumed

Same inputs, `uuid.uuid4` replaced by the same deterministic counter in both
arms (the job is otherwise non-deterministic run-to-run: fresh family /
document GUIDs, #168/#9), 3 panelboards onto `G_ABPD.rvt`:

* plans identical: content GUIDs, famDoc GUIDs, host Family / Symbol /
  surrogate / twin ids ladder identically (family i+1 above family i's top id);
* streams **byte-identical**: `Global/ElemTable`, `Global/ContentDocuments`,
  `Global/Latest`, `Global/History`, `Global/PartitionTable`,
  `Global/DocumentIncrementTable`, `Formats/Latest`, `Contents`,
  `ProjectInformation`, `TransmissionData`;
* `Partitions/21`: same 4 units with the same GUIDs in the same order, same
  23 blocks, **every block's unit/seq/record-count/flags/inflated payload
  identical and every gzip member the same length**; the end record proper
  identical. What differs is not content: (a) `BasicFileInfo.last_save_path`
  = the pass-1 temp *name* (`chain_L3…` vs `batch_L…`; the deliverable's BFI
  is rewritten by stage E anyway), and (b) the bytes *after* the partition end
  record — see finding 3: each container rewrite re-frames the previous
  read's final-page ECC trailer junk into the logical stream, so the chain
  carries three increments of it (base 1,862 B tail → 2,036 → 2,237 → 2,623)
  and the batch one (2,111 B, = what a single certified load carries).
* the written batch file: four-registry census coherent (units / CD / CT
  GUID sets == our 3 GUIDs), `rvt.validate` VALID 0 errors, structure layer
  clean, every plan's unit / ElemTable ids / ContentTable / FamilyMgr /
  tracking / family-inventory / provenance checks green — on the 2026 base and
  (2 families) on the 2025 base under its own release (`detect_release` 2025).
* front door, 6-panel prompt, `--target-version` 2026 / 2025 / 2024: `ok`,
  6/6 loaded in 1 pass, 6 `.rfa` + 6 loaded + 6 placed + 4 walls,
  `tools/rvt_validate.py` → `VALID (no errors)` (warnings 1 / 0 / 0), census
  coherent, identity PASS — same element census as the chained build.

All of the above is pinned sample-free in `tests/test_famload_batch.py`.

## 3. Gates run

* `tests/test_famload_batch.py` (new, sample-free, in `tests/ci_shard.txt`):
  **12 passed** in 25 s — batch loads N ok with laddered ids; four-registry
  coherent + VALID; ONE container write for N (seam on `cfb_writer.write_cfb`:
  batch 1 vs chain 2 for two families); chain ≡ batch logically (above);
  authoring failure stops the batch there / nothing loadable writes no file;
  single-loader report shape unchanged; 2025 base under its own release;
  manifest `build.stages[*].seconds` are numbers incl. the V gate split;
  a 2-panel prompt loads in `host_passes == 1` with one `_stages`
  intermediate and a whole deliverable; `stage_load_batched` degrades to the
  deepest good prefix when a family cannot be built (blocker names it, one
  pass); `surface_bench.stage_breakdown` reads the breakdown back.
* `tests/test_frontdoor.py tests/test_target2025.py tests/test_go_target_version.py`
  → 47 passed / 12 skipped; `tests/test_famgen_loader.py test_famgen_factory.py
  test_famload.py test_famload_2025.py test_hostsym_product.py test_bootstrap.py
  test_coldstart.py test_surface_perf.py test_plugin_sync.py
  test_bare_family_validate.py test_target2025.py` → **111 passed / 49
  skipped** (skips = the `samples/`-gated loader/famload files, absent in a
  cloud clone — the refactored single loader is exercised sample-free by
  `test_famload_2025::test_famgen_loader_bare_on_the_2025_base`,
  `test_hostsym_product` dry runs and the new shape test).
* `tools/sync_plugin.py` run (2 files mirrored: `plugin/lib/src/rvt/frontdoor/build.py`,
  `plugin/lib/src/rvt/famgen/loader.py`; deny-audit clean; zip 5022 KB),
  `--check` clean; `plugin/scripts/validate_plugin.py` PASS;
  `tools/dev/check_portable_paths.py` ok.
* Outputs validate 0 errors on 2026 / 2025 / 2024 (§2).
* Full suite NOT run (SUITE-COORDINATION).

## 4. Findings

1. **Where the flagship job's time goes now** (AFTER, cProfile of the bare
   6-panel job, 15.8 s profiled ≈ 8.5 s wall): stage **F** `stage_families`
   7.3 s cum = 46 % — six standalone `.rfa` deliverables each *written +
   validated twice-over + provenance-scanned* (`factory.write` 1.2 s/family:
   `validate_family_file` 0.62, `provenance_scan_v2` 0.34, `emit_family_rfa_v2`
   0.22); stage **L** 3.6 s = 23 % (of which `verify_loaded_projects` 1.2,
   `survey_host` 0.36, six round-trip gates 0.26); **V** ≈ 1.9 s
   (`status_gate` 1.1 = a full provenance baseline scan, census 0.4);
   W + E + specimens < 1 s.
2. **#183's share, measured (not implemented here):**
   `schema_cache.parse_cached` is still called **66×** for ≤ 3 distinct
   bundled digests = **6.56 s cum of 15.8 s profiled (~42 %)**
   (`payload_to_schema` 4.68, `_tuple_to_field` 2.39 s tottime over 834 k
   calls, `marshal.loads` 1.61 s over 203 loads); callers: `versions.schema_of`
   26×, `families.FamilyIndex` 20×, `validate._load_schema` 13×,
   `mutate.Document.from_file` 6×. Batching already removed 31 of the BEFORE's
   97 calls (fewer surveys/verifies); an in-process memo keyed by digest would
   remove ~63 more → an estimated further **≈ 3 s off the 8.5 s job (→ ~5.5 s)**
   and ~1 s off the 1-panel job. That is now the single biggest lever.
3. **Pre-existing writer hygiene, surfaced by the equivalence proof (filed as
   a follow-up, not fixed here — outside territory):** `container.depage()`
   leaves the final partial page's ECC trailer as "harmless trailing junk" at
   the end of every logical stream it reads, and `commit_new_elements` keeps
   `raw[end_offset:]` whole when it re-frames the partition — so **every
   container rewrite bakes the previous read's trailer junk in after the
   partition end record and adds a fresh trailer**. N chained edits accumulate
   N junk increments (the 6-panel chain: +6; walls +1; equipment +1); the
   batch cuts the L stage's share to one. Revit tolerates it (the certified
   WF_fix / stage_L8 lineage was built by chained loads), but it is silent
   growth of non-content bytes in a deliverable and an avoidable diff between
   otherwise-identical files; the fix is to truncate at the true end record
   (its grammar is known) or de-page by the pad field (#236's "one deframer").
4. The `--ifc` route goes through the same `build.py` L stage, so
   multi-family IFC jobs get the same cut. `rvt.convert.add_to_project` (the
   `--rvt` "add our equipment to your project" route) does **not**: it calls
   the chained `tools/ifc_intent.stage_load` directly (both out of this
   stream's territory) — one stage-L implementation for both callers is a
   follow-up. `tools/ifc_intent.py room` (dev CLI) chains by design.
5. `/simplify` review outcomes worth keeping: the degrade *policy* was moved
   out of the engine primitive into `stage_load_batched` (the loader no
   longer loops); an `RVT_FAMLOAD_CHAIN` A/B env hatch was removed again (an
   undeclared special case; the before/after is main-zip vs branch-zip and
   reproducible from git); `verify_written` now gets a *set* of expected ids
   (batching had turned its per-record membership test into O(N × host
   records): 112 ms → 38 ms at N = 6); ContentDocuments is assembled once via
   `assemble_content_documents` instead of N insert/parse cycles; the splice
   asserts the spliced unit GUID == the plan's (famload's rule). Skipped with
   reason: converging `rvt.famload._load_family_documents`' PASS-1/PASS-2
   block (a near copy of `_commit_and_write` for the annotation-family
   flavour) — its 12 tests are 100 % sample-gated, so it cannot be refactored
   with evidence in a cloud clone (follow-up); dropping the pre-write
   ADocument re-decode gate (~110 ms, duplicated by the read-back) — kept as
   the cheap fail-before-write proof the single loader always had.

## 5. Follow-ups (numbers above; filed/commented per §6 of the charter)

* **F stage: 1.2 s per generated `.rfa` in self-checks** — validate each
  family file once (family mode) instead of validate + verify + provenance as
  three full decodes, or gate the per-family provenance scan behind the
  job-level status gate that rescans everything anyway. Est. −2.5 s on the
  6-panel job. (new issue, Refs #124 #108)
* **#183 schema-cache memo** — share measured in finding 2 (comment on #183/#110).
* **Partition tail junk per rewrite** — finding 3 (new issue, Refs #124 #236).
* **One stage L for both callers** — `add_to_project` onto
  `load_families_into_project` (or `ifc_intent.stage_load(batched=True)`),
  retiring the duplicated record-shape producer; and `famload`'s PASS-1/2
  block onto `_commit_and_write` (owner-machine, sample-gated tests).
* V stage `status_gate` 1.1 s = a second full provenance pass over the
  deliverable right after `validate` decoded it; L-stage verify re-parses the
  schema for its `FamilyIndex` (~95 ms) and decodes the ADocument a third
  time (~110 ms) — candidates once #183's memo lands (note on #110).
* #184 (surface_bench + `test_surface_perf` gain the 6-panel job with a
  ceiling): the bench half is done here (`go-author-6panels`); the CI ceiling
  half remains.

## BRANCH STATE

* Branch `cam/124-family-load-batch` from `main @ a0183b7`; PR closes #124.
* Files written: `src/rvt/famgen/loader.py` (+`_AuthoredLoad`/`_author_load`,
  `_framed_load_records`, `_edit_host_registries`, `_commit_and_write`,
  `BatchLoadResult`, `load_families_into_project`, `verify_loaded_projects`,
  `_plan_host_ids`; single loader + `verify_loaded_project` re-expressed on
  them; dead `_framed_records` removed; `ACCEPTANCE_LEDGER`,
  `_require_ids_above`, `_write_report`; `provenance_ours(fidx=)`), `src/rvt/frontdoor/build.py` (+`_timed_stage`,
  `_load_entry`, `stage_load_batched` (+ the prefix degrade policy), every
  stage under the one clock, V-stage entry with per-gate split, `stages` in
  `as_json`), `tools/surface_bench.py` (+`stage_breakdown`, `_fmt_breakdown`,
  `JobResult.breakdown`, job `go-author-6panels`), `tests/test_famload_batch.py`
  (new, 12 tests), `tests/ci_shard.txt` (+1 line), this record; sync mirrors
  `plugin/lib/src/rvt/{frontdoor/build.py,famgen/loader.py}`.
* `src/rvt/frontdoor/manifest.py`, `src/rvt/famload.py`: no change needed
  (the manifest already copied `build.stages`; the prompt path never used the
  four-registry loader).
* Gates: §3, all green locally.
* Nothing staged for the viewer: no framing/codec change; the loaded content
  is logically identical to the chained build (§2) and the front door's
  outputs keep their existing honesty stamps (placed instances on a composed
  base = the open cell, PROOF-ONLY) — no certification claim is made or
  changed; no `.rvt`/`.rfa` committed; no ledger change; `tekton-plugin.zip`
  regenerated locally, not committed.
