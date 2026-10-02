# #969: where the 6-panel job's time went since 2026-08-09, and what came back

**Why.** `go author --prompt "an electrical room with 6 panels"` got about 45% slower on the
session-CI container between `main@dc0980f` (2026-08-09) and `main@fe83378`. Stage F (family
generation) went from 1.5 s to 2.4 s and stage L (family load) from 1.3 s to 2.3 s. Some of this
was always going to be intended content. Steer S-2026-08-09-g counts latency as product
performance, done only with a measured before/after from `tools/surface_bench.py`. #932 had
already won back the overhead #931 introduced. Its open items (each panel is built twice, the
`decode_latest` repeats) were read first and are not redone here.

**Instrument.**
- Each commit was benched from its own `git archive <sha> plugin tools` tree, with ONE bench
  script (ce73a6f's `tools/surface_bench.py`) copied into every tree. Command:
  `surface_bench.py --from-tree --surfaces local --jobs go-author-6panels`, run under
  `/usr/bin/python3` 3.11.15 with no numpy. Values are F, L and `job_seconds` taken from the
  JSON breakdown.
- Commits were **interleaved** round-robin. Each value is the **min** over the warm runs (the
  first run of a fresh tree compiles its `.pyc` and is dropped).
- Container: 4 vCPU. Another process kept the load average at 1.8–2.8 the whole time, which is
  why the runs were interleaved.

## Finding 0: `dc0980f` is not on today's first-parent chain

`git log --first-parent dc0980f..ce73a6f` starts at `6f33fb7`, and `6f33fb7` is a **root
commit**: main's history was rewritten at #708 (2026-08-11). The 181 first-parent commits between
`dc0980f` and the rewrite are still reachable on the old chain. `0cbf7e1` is the old-main tip,
and `6f33fb7` is that tree plus #708. That segment was benched on the old chain (137 commits
touch `plugin/`).

## Attribution (ΔF / ΔL / Δjob in seconds)

Segments with no measurable step are folded together. Single-run noise is about ±0.15 s at n=3
and ±0.1 s at n=5.

| step (commits) | n | ΔF | ΔL | Δjob | what |
|---|---|---|---|---|---|
| `dc0980f`→`c1f5ad8` (13) | 3 | +0.08 | +0.00 | +0.15 | noise |
| →`fba7efb` six donor-measured famdoc laws, desktop rounds 13–25 | 3 | +0.18 | +0.11 | +0.32 | **content** (desktop-verified family laws) |
| `fba7efb`→`53001d9` (11, incl. `8f7a1d9` solver-state / corner-join / classification-table laws +0.15/+0.09, and `53001d9` the parametric-drive law +0.11/+0.13) | 3 | +0.22 | +0.08 | +0.48 | **content** |
| `53001d9`→`1d63c6b` (troffer drive, compiled decode plans) | 3 | −0.15 | −0.09 | −0.49 | overhead won back (decoder plans; mostly V) |
| `1d63c6b`→`4bd7ecf` (42) | 3 | +0.29 | +0.20 | +0.34 | spread thin, no single step above noise (resolve_base, estorage tables, edit-route) |
| `4bd7ecf`→`6f33fb7` (31, incl. the rewrite) | 3 | −0.15 | −0.03 | −0.21 | flat |
| **old chain total `dc0980f`→`6f33fb7`** | 5 | **+0.48** | **+0.40** | **+0.76** | content, desktop-round laws plus parametric drive |
| `6f33fb7`→`50a89ef` (24) | 5 | +0.09 | −0.08 | +0.25 | flat (V and P noise) |
| `50a89ef`→`6f56772` (17: #793/#801 determinism, LCP, NEC 110.26 data, formula trees #862, instance flags #868, profiles #866) | 5 | +0.16 | +0.21 | +0.18 | content |
| →`b9bdfb4` #887: panel and transformer clearance zones + Yes/No toggles, open in 3D at Fine | 5 | +0.22 | +0.27 | +0.52 | **content** (S-2026-09-23-a) |
| `b9bdfb4`→`be0a350` (2) | 5 | −0.01 | +0.04 | +0.07 | flat |
| →`10e844c` #892: panelboard built from its real parts | 5 | +0.49 | +0.51 | +1.18 | **content** |
| `10e844c`→`374ba9f` (8: in-plane drive #904, extrusion heights #923, diameter #929, Lock column #930, …) | 5 | +0.03 | +0.22 | +0.17 | content |
| →`9cdb82d` #931: panel W/D/H through drive_law, front parts ride them | 5 | +0.71 | +0.77 | +1.76 | content + overhead |
| →`9b0b9c7` #932/#933: encoder plans, decode memo, GC pacing, … | 5 | −1.31 | −1.31 | −2.92 | overhead won back (more than #931 added) |
| `9b0b9c7`→`ce73a6f` (16: nesting #936–#949, partition tail #942/#946, duplicate-name #945, …) | 5 | −0.03 | +0.01 | −0.19 | flat |
| **total `dc0980f`→`ce73a6f`** | 5 | **+0.83** | **+1.04** | **+1.77** (4.31 → 6.08 s, +41%) | |

**Reading.**
- Every step above noise is a feature the owner asked for:
  - the desktop-round family laws;
  - the parametric drives (#787/#904/#931);
  - clearance zones with toggles (S-2026-09-23-a);
  - the panelboard's real parts (#892);
  - the Revit-born view set and standard parameters, which ride inside the early old-chain
    steps.
- No merged commit added a standing overhead that later commits did not remove. #931's overhead
  was more than recovered by #932.
- Two pieces of overhead were latent from the start: duplicated encode work, and repeated
  reads and decodes. They are structural, not tied to one commit, and the fixes below remove
  them.

## Fixes (each byte-identical; each measured)

Profile of the current main (cProfile, plus in-process wall timers on named functions) on the
in-process path the front door takes. The front door builds each family standalone (stage F) and
again at the host watermark for the batched load (stage L).

1. **One encode per record shared by the documents of stage F** (`skeleton.shared_record_cache`,
   opened by `tools/ifc_intent.stage_families`).
   - The six standalone panelboards differ only in name, and #932's per-document cache could
     not see across documents. Measured: 795 records were encoded for the first document and
     **27** for each of the other five, where it had been 795 each.
   - The rows are keyed exactly like the per-document cache: pickled record content, plus
     encoder identity, plus the active id writer (the ids32 era). The scope is bounded at
     64 MB and dropped when stage F ends.
2. **The standalone read-back verification inside the checks' decode memo.**
   - `emit_family_rfa_v2(verify=False)` leaves `verify_family_rfa` to `standalone_family_write`.
     There it runs in the same `decode_memo` scope as the validator's two runs and the
     provenance scan, so its seq-102 decode pass serves them.
   - Report identical: `verify` equals what `emit` computed itself.
3. **One decode of the edited host ADocument for its four read-only checks.**
   `adocument.decode_latest_shared` plus the `shared_latest_decodes()` scope around the
   front-door build.
   - The same 1.58 MB `Global/Latest` payload was decoded four times: the loader's
     re-decode proof, `verify_loaded_projects`, the validator's four-registry check, and the
     registry census.
   - Now: 1 decode (0.065 s each on this box). It holds on 2025 too.
   - The key is decoder class + schema object + `Reader.element_id` + payload bytes, in an LRU
     of 2. Callers that edit the tree keep `decode_latest`.
4. **`validate_family`'s two validator runs share one `walk_file`** (#266's `WalkedFile`). The
   file is read, ECC-verified and inflated once instead of twice. Thirty-six family files were
   compared finding by finding: identical. The two runs went from 3.87 s to 3.25 s, about
   17 ms per family.

Tried and **dropped**:
- An iterative or `type() is` string collector for the provenance scans: the recursive original
  was the fastest of three (108 / 140 / 129 ms on a whole project).
- `marshal` record keys: only 7.4 ms vs 8.3 ms per document, not worth the key-injectivity
  argument.
- Sharing the V-stage validator's decode memo with the provenance ledger: `mutate.Document`
  is in that path, and its read-only status was not proven.

### Before / after, per fix (local surface, 6 interleaved rounds, min of 5 warm)

| tree | F | L | V | job | Δjob |
|---|---|---|---|---|---|
| `ce73a6f` (main) | 2.14 | 2.21 | 0.76 | 5.98 | |
| + 1 shared records (`adc3200`) | 1.96 | 2.22 | 0.76 | 5.86 | −0.12 |
| + 2 verify in memo (`ec8fbbd`) | 1.95 | 2.24 | 0.75 | 5.78 | −0.08 |
| + 3 shared Latest decode (`5c6faf3`) | 1.89 | 2.16 | 0.61 | 5.53 | −0.25 |
| + 4 shared walk (`888c524`) | 1.83 | 2.08 | 0.61 | **5.40** | −0.13 |

The total is **−0.58 s (−9.7%)**. A separate 6-round A/B (`ce73a6f` vs `888c524`, local)
gave 6.14 → 5.44 s: F −0.49, L −0.11, V −0.10.

**The gate's own units** (cowork surface, `--calibrate`, 6 interleaved sessions per tree,
`job_seconds` / that session's reference):

| tree | min | median | max |
|---|---|---|---|
| `ce73a6f` | 21.64 | 22.06 | 22.75 |
| head | 19.40 | **20.53** | 20.99 |

Both are under `ROOM6_RATIO_CEILING = 24.0`. (#965 measured 19.6–20.1 for fe83378 on a quieter
container; this one ran at load 2.5–2.8, so compare within the table.)

**Byte identity** was checked at `ce73a6f` and at every fix (`hash_*.json`, 98 entries, all
identical).
- **Bare `go author` jobs**, 2026 and 2025: sha256 of `prompt_room.rvt`, the three stage
  `.rvt`s and the six `.rfa`s. Every text output was compared with timings and paths stripped.
- **In-process standalone writes** inside `release_build_context` on the 2026 and 2025 bundled
  bases: panelboard default, 600 A, `drive=None`, `drive="372"`, `solid=False`, transformer,
  troffer, device, generic box with drive, cable tray, junction box and fan coil. The check
  covered each `.rfa` and its report JSON minus `seconds`.

## Open (what is left, measured)

- **Each panel is still built twice**: standalone at id 1000 in F, and at the host watermark in
  L. Wall timers put the L-side build plus its encodes at about 0.7 s, roughly 12% of the
  job. That is the largest lever left.
  - Re-iding a built document instead of rebuilding it needs a schema-typed shift of every
    ElementId field, plus a fresh content seal.
  - #932 judged that not obviously byte-safe, and so does this pass. It would need its own
    issue with a proof harness.
- `provenance_ours`, in L, decodes our 1,770 unit records: about 0.25 s, which is honest
  read-back. The V-stage validator decodes all 8,062 records of the final file. Neither has a
  read-only twin to share with.
- `_record_key` pickling (about 8 ms per document encode, 30 encodes per job) is the cost of the
  exact-content cache. A cheaper exact key was not found.

## BRANCH STATE

- Branch `fix-969` from `ce73a6f` (worktree `.claude/worktrees/agent-a3d6ba3c7c74c8ee0`).
  Local commits only: not pushed, no PR.
- **Files:**
  - `src/rvt/famgen/skeleton.py`: `shared_record_cache`, `_shared_rows`, the
    `build_unit_segments` lookup, `validate_family` walk.
  - `src/rvt/adocument.py`: `shared_latest_decodes`, `decode_latest_shared`.
  - `src/rvt/famgen/famdoc_adoc.py`: `emit_family_rfa_v2(verify=)`.
  - `src/rvt/frontdoor/standalone.py`: verify inside the memo.
  - `src/rvt/frontdoor/build.py`: the scope around `_build_intent_inner`.
  - `src/rvt/famgen/loader.py`, `src/rvt/validate.py`, `src/rvt/famload.py`: read-only call
    sites moved to `decode_latest_shared`.
  - `tools/ifc_intent.py`: the stage-F scope.
  - Mirrors under `plugin/`, `tests/test_latency_969.py`, `tests/ci_shard.d/969-latency.txt`,
    this fragment, and one index line in `perf-surfaces.md`.
- **Gates.** Gate set as listed in the task; same two runs as the evidence above.

  Run 1 (95.5 s):
  - `tests/test_surface_perf.py`
  - `test_plugin_sync`
  - `test_bootstrap`
  - `test_coldstart`
  - `test_famload_batch`
  - `test_famgen_loader`
  - `test_loader_937_928`
  - `test_partition_tail_941`
  - `test_conftest_scaffolding`
  - `test_latency_969`
  - `test_build_latency_932`
  - `test_records_layout`

  Result: **146 passed / 14 skipped**.

  Run 2 (`RVT_SKIP_LARGE=1`):
  - `test_bare_family_validate`
  - `test_drives_rest_913`
  - `test_famdoc_scan_collision_807`
  - `test_famdoc_scan_fp`
  - `test_famgen_adoc`
  - `test_famgen_skeleton`
  - `test_famload`
  - `test_famload_2025`
  - `test_frontdoor_standalone`
  - `test_partition_header_verdict`
  - `test_partition_tail_938`
  - `test_rfa_load`
  - `test_target2025`
  - `test_nest_917`
  - `test_trapeze_nested_917`
  - `test_genesis_2023`
  - `test_instbug`
  - `test_adocument`
  - `test_validate_footer_blob`
  - `test_validate_release`
  - `test_famload_determinism_794`
  - `test_frontdoor`

  Result: **373 passed / 69 skipped**.

  Other checks:
  - `tools/sync_plugin.py`: rebuilt. `--check`: in sync.
  - `plugin/scripts/validate_plugin.py`: PASS (25).
  - `tools/dev/check_portable_paths.py`: ok.
  - `tools/self_battery.py`: 27/27 PASS.
  - Full suite not run (SUITE-COORDINATION).
- **Shipped vs staged.** Latency only. No output byte changed, nothing is staged for the viewer,
  and nothing is claimed about Revit behaviour (hard rule 4).

### Review of #976 (2026-10-02)
🛑 then fixed: the shared up-front `walk_file` in `validate_family` caught only
`ValueError`, so a CFB with a damaged header (directory index out of range) raised
`OleFileError` (an IOError) out of the validator where it used to get an INVALID
report. It now catches any exception and falls back to `walked = None`, so each
`validate_file` run reports the damage itself, as before. Pinned by
`test_validate_family_on_a_damaged_container_still_reports` (fails without the
fix). The reviewer's 18 other mutated inputs per family (truncations, zeroed
blocks, byte flips, garbage, empty) gave identical reports base vs head, and
byte identity held for nine sandboxed jobs, including all of them run in one
process under one shared-cache scope across 2026 / 2025 / 2024.
