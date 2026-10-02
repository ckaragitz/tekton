# test-health — #965: the flagship 6-panel perf gate becomes machine-independent

Stream: test-health. Issue #965. Branch `fix-965` from `fe83378` (main).
Territory: `tests/test_surface_perf.py`, `tools/surface_bench.py` (a calibration
job), the FLAGSHIP-PERF-GATE section of `docs/inbox/perf-surfaces.md` (a section
added under this stream's own header), this fragment. No `src/rvt/**` change.

## The problem

`test_bare_go_author_6panels_under_ceiling` asserted the flagship job's wall time
was under 8.0 s (#184). That ceiling was calibrated on a claude.ai/code VM at
3.1–3.4 s. On the session-CI container (4 vCPU, system python 3.11.15), main@fe83378
measures **6.3–7.8 s, median 6.8 s, over 39 samples**. PR #964 went red at 8.26 s.
An absolute ceiling only holds on the machine it was measured on.

How much of the gap is the machine and how much is main? To find out, the old plugin
trees were extracted with `git archive <sha> plugin` and benched on this same container:

| plugin tree | 6-panel wall | author-prompt wall |
|---|---|---|
| main@dc0980f (#184's commit) | 4.4–5.1 s | 3.1–3.5 s |
| main@fe83378 | 6.3–7.8 s | 3.3–4.2 s |

- **The container is about 1.45× slower than the VM.** dc0980f measured 4.4–5.1 s here
  against 3.1–3.4 s on the VM. author-prompt agrees: 3.35 s here against 2.28 s.
- **The rest of the gap is main itself.** The flagship got about 45% slower between
  2026-08-09 and today, on the same machine. Stage breakdown, dc0980f → fe83378:
  F (families) 1.5 → 2.4 s, L (load) 1.3 → 2.3 s. Everything else stayed flat.
- **The old 8.0 s gate let this through,** because on the VM this growth still
  lands under 8 s. Whether the growth is legitimate is not investigated here. Candidate
  causes are the content added since then, such as the view constellation (S-2026-08-10-a)
  and standard parameters (#601). The question is reported upward as a finding.

## Calibration choice

The gate needs a calibration: something whose time tracks how fast the machine is,
without sharing the per-family cost the gate is meant to catch.

Two candidates were tried and rejected:

- **author-prompt, a 1-family build that the fixture already runs.**
  - For: across machines it matched well (6p/author-prompt ratio: 1.44 on this
    container, 1.47 on the VM, both at dc0980f).
  - Against: it shares the engine's code with the job it calibrates. The pre-#292
    regression, a schema re-parse on every decode, slows it too.
  - Result: the ratio for pre-#292 (median 2.02) comes out *below* today's main
    (1.88–2.25, because main grew). The ratio cannot catch a regression that hits
    every job, so it was rejected.
- **go-edit.** Its time depends on the code (it got faster since August), and at 0.8 s
  it is too short to measure reliably. Rejected.

**Chosen: a fixed reference workload** (`surface_bench.reference_samples`).

- **What it is.** A pure-stdlib loop of zlib round-trips, struct parsing, dict churn,
  sort and repr. It uses no engine code. The same bare python runs it with the same
  env, and the loop is timed inside the process. It runs 3 times before the jobs and
  3 times after; the reference value is the min of the 6. Here that is 0.302–0.333 s,
  with a standard deviation of about 3%.
- **How it is exposed.** `run_bench(calibrate=True)` or `--calibrate` adds
  `surfaces[i].calibration`. `calibrated(seconds, cal)` converts a time into reference
  units. The markdown notes also print every job in reference units.
- **The flagship's own noise** (±10%, varying over time rather than with
  `PYTHONHASHSEED`: 4 seeds × 2 runs) dominates. The gate therefore takes 2 flagship
  samples in one session and uses the min. The repeat is a measurement sample, not a
  session call, so the call-budget test counts each job name once.

## The gate (after)

- **`ROOM6_RATIO_CEILING = 24.0`** reference units. This is the min of 2 flagship
  `job_seconds` samples, divided by the reference.
- **`ROOM6_CEILING = 18.0 s`** wall time, on the first sample. It is kept as a runaway
  guard: 2.6× the container's median of 6.8 s. It still fails pre-#237.
- **New opt-in test, `test_room6_gate_catches_injected_regression`.**
  - Enable it with `TEKTON_PERF_SELFTEST=1`. It takes about 25 s.
  - It copies the plugin tree to a scratch directory and patches the copy's
    `stage_families` (both `ifc_intent.py` copies in the plugin) so every family is
    built and written twice.
  - It asserts that the ratio comes out **at or above** the ceiling.
  - Product code is never touched.

Measured on this container, cowork surface, plugin tree. All values are reference
units, min of 2 samples:

| tree | runs | ratio | at 24.0 |
|---|---|---|---|
| main@fe83378, `pytest tests/test_surface_perf.py` | 10 | 19.29, 19.20, 20.50, 18.95, 19.80, 20.91, 20.08, 21.08, 19.12, 19.51 (median 19.6) | **10/10 pass** |
| main@fe83378, bench sessions | 10 | 19.4–21.7 (median 20.1); single samples 19.4–23.4 over 30 | pass |
| main@dc0980f | 3 | 12.9, 14.2, 13.5 | pass |
| injected double .rfa build + write (+32% job time: 6.4 → 8.4–9.0 s) | 3 + 2 pytest | 28.0, 26.3, 25.6; pytest self-test passed 2/2 | **fail** |
| injected double `build_product` only, no write (+10%) | 3 | 21.4, 23.0, 22.0 | pass (below the gate's resolution) |
| pre-#292 (3ff16c6) | 3 | 31.9 / 30.7 / 34.6 | **fail** |
| pre-#256 (5a40b22^) | 2 | 54.8 / 49.9 | **fail** |
| pre-#237 (27e2093^) | 1 | 92.5 | **fail** |

**Resolution.** 24.0 is 1.19× the median of healthy main and 1.03× the slowest
*single* sample ever seen (23.4). The gate fails a flagship regression of about +25%
or more. A +10% regression passes: that is within this container's noise, and the
gate does not claim to catch it.

*Amended after the #970 review (2026-10-02):* under concurrent load (another
sandboxed CI run, load ≈ 1.8) the +32% injection scored **23.74** -- under 24.0 --
so the claim above holds only on a quiet machine. Restated: the gate fails a
steady regression of about **+35% reliably**, about +25% on a quiet machine. The
self-test now injects two extra build+writes per family instead of one (numbers
below). Known asymmetries, stated in the constant's comment: the reference is
the min of six samples and the flagship the min of two, so load inflates the
ratio (≈ 10% headroom on healthy main); a regression hitting only one of the two
flagship samples is invisible to the ratio; the reference loop is CPU-only, so a
machine with unusually slow disk drifts the ratio.

Strengthened self-test, measured on `4054a8f` + this branch (reference units,
min of 2): quiet 35.78, 34.50; under a concurrent flagship pytest run 35.54,
36.47 -- all over 24.0 with ≥ 40% margin. Healthy main in the same session:
19.48, 20.51, 20.06. The self-test now records `injected_room6_ratio` for
`--junitxml` (read with `-o junit_family=legacy`; under xunit2 pytest warns
and omits properties).

**Not measured on a normal cloud VM.** No VM was available in this container. The
ratio is designed to be machine-independent, because the reference and the job are
both timed by the same python on the same machine in the same session. The only
cross-machine evidence is indirect: the product's slowdown factor at dc0980f was
uniform across jobs (about 1.45×). The ratio's VM value is **unknown**. The first VM
or other-machine run should state its number next to `ROOM6_RATIO_CEILING`.

A CLI caveat: `surface_bench.py --calibrate --jobs preflight,go-author-6panels` runs
the flagship first in its session, on a cold `.pyc` cache, and measured 22.97 units.
The gate's fixture runs it after author-prompt and go-edit, with a warm cache. Compare
like with like.

## BRANCH STATE

- **Branch:** `fix-965` from `fe83378`, committed locally. Not pushed, no PR. The
  caller asked for exactly that. *Update:* shipped as PR #970 on
  `claude/pull-latest-main-1cmo56`, rebased onto `4054a8f`; the review follow-up
  (stronger self-test, restated claim) is the second commit.
- **Files:**
  - `tests/test_surface_perf.py`: the ratio gate, the opt-in self-test,
    `ROOM6_CEILING` 8.0 → 18.0 as a runaway guard, 2 flagship samples, and the budget
    test counting each job name once.
  - `tools/surface_bench.py`: `reference_samples` / `calibration` / `calibrated`,
    `run_bench(calibrate=)`, `--calibrate`, and the calibration line in the markdown notes.
  - `docs/inbox/perf-surfaces.md`: a section appended under this stream's header.
  - This fragment.
- **Gates:**
  - `tests/test_surface_perf.py`: 9 passed / 1 skipped (the opt-in), 10/10 runs, about
    21 s each. With `TEKTON_PERF_SELFTEST=1`: 10 passed in 42 s.
  - `tests/test_plugin_sync.py tests/test_records_layout.py tests/test_famload_batch.py`:
    29 passed.
  - `tools/sync_plugin.py` rebuilt the zip, and `--check` reports in sync.
    `surface_bench.py` is not mirrored into the plugin.
  - `plugin/scripts/validate_plugin.py`: PASS (25 assertions).
  - `tools/dev/check_portable_paths.py`: ok.
- **Cost to CI:** the module fixture grows by one more flagship run plus 6 reference
  samples, about +9 s, to about 21 s here.
- **Open:**
  1. The ratio's value on a VM is unmeasured.
  2. Main's flagship grew about 45% since dc0980f (F and L stages). Nobody has decided
     whether that growth is all intended content. It is worth its own issue.
- Nothing staged for the viewer; no hot file touched; no output bytes changed.
