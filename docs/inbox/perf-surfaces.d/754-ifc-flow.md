# perf-surfaces / #754 -- the tekton-ifc flow in ONE call (`ifc_flow.py`, `go-ifc-harden`)

Stream: PERF-SURFACES (index: `docs/inbox/perf-surfaces.md`). Issue #754 (Refs #110, #113, #111; steer #108).
Branch `cam/754-ifc-flow` from `main@4433d17`.

## Why

#113 measured the tekton-ifc skill's documented flow on a foreign IFC (`SKILL.md` 5.2-5.4:
`validate_ifc.py` -> `harden_ifc.py` -> `validate_ifc.py` on the hardened file -> `report.py`)
at FOUR shell calls, each a model round-trip on the Cowork / code-execution surface, each paying
the ~0.5 s ifcopenshell import, and -- reading the code -- the file analysed FOUR times
(`harden_ifc.harden()` already runs `bridge_lib.analyze` on its input and on its reopened
output, so the two `validate_ifc.py` calls repeat work the harden step did). Same shape #111
fixed for `tekton-edit` (3 calls -> 1).

## What was built

* **`skills/tekton-ifc/scripts/ifc_flow.py`** (mirrored into `plugin/skills/tekton-ifc/scripts/`
  by `tools/sync_plugin.py`): `ifc_flow.py IN.ifc --out DIR [--json] [--quiet]` + the four
  `harden_ifc.py` switches (one option table, `harden_ifc.add_harden_args` /
  `harden_kwargs`, shared by both CLIs), one process. Writes `validate.json`, `hardened.ifc`,
  `harden.json`, `validate-after.json`, `report.md` under `DIR` and prints ONE summary
  (`--json`: `ok`, a one-sentence verdict `line`, before/after `{score, tier, schema_errors}`,
  the harden `actions`, the absolute `files` by role, per-stage `stages` + `seconds`;
  otherwise a short human block). Exit 0 = flow ran and the hardened file reopens with 0
  schema errors; 1 = it has schema errors -- **every file still written** (hard rule 1);
  2 = usage / I/O (missing input, not IFC: nothing written). The four CLIs are unchanged and
  still compose by hand.
* **`harden_ifc.harden_analysed(in, out, before_report, *, model=None, ...) -> (result,
  after_report)`**: `harden()` split into the surgery that takes the input's full
  `bridge_lib.analyze` report (STEP ids are the file's own, so the surgery is identical) and
  the already-open `ifcopenshell.file` it was computed on, and returns the reopened output's
  full report next to the action/diff result; `harden()` is now a two-line wrapper with the
  same signature and result, and `bridge_lib.analyze(path, model=None)` accepts an open
  model. So the whole flow **parses the input once, analyses it once, and the output once**
  (was: 4 parses + 4 analyses over 4 processes), with one import instead of three. The
  harden CLI's `--report` JSON is byte-for-byte what it was (and it too now parses its
  output once instead of twice).
* **`tools/surface_bench.py`**: `go-ifc-harden`, an eleventh canonical job right after
  `ifc-harden` (same tekton-ifc session): ONE call of `ifc_flow.py SAMPLE --out DIR --json`.
  Same verdicts as `ifc-harden` -- BLOCKED from the interpreter's own `ModuleNotFoundError`
  at the first import (`_missing_prerequisite`), FAIL for a failed flow (`_why`) or a
  hardened file with schema errors -- both through `_why`, i.e. in the tool's own words (its
  envelope `line`), the delivered files kept as `go-ifc-*` artifacts either way -- and PASS
  with the same breakdown (`_ifc_breakdown` and the BLOCKED verdict `_ifc_skill_blocked` are
  now shared with `ifc-harden`) plus `job_seconds` = the tool's in-process time, so the notes
  read `job 1.2s = validate 0.5s · harden+re-validate 0.6s · report 0.0s; score 35.7 -> 77.0 ...`.
* **`tests/test_surface_perf.py`**: the `ifc_skill_report` fixture runs `ifc-harden` and
  `go-ifc-harden` in ONE cowork session (the before/after pair under the same conditions);
  `test_ifc_skill_flow_hardens_or_states_its_prerequisite` is parametrized over
  `("ifc-harden", 4)` / `("go-ifc-harden", 1)` -- each row held to `IFC_SKILL_CEILING` with its
  call count, `schema_errors_after == 0`, a higher score, and the one-call row **faster than
  the four-call row of the same run** (PASS branch), or BLOCKED with the prerequisite named
  at preflight cost. The ceiling comment records the numbers below.
* **`tests/test_ifc_flow_754.py`** (14 tests, `tests/ci_shard.d/754-ifc-flow.txt`; runs on an
  interpreter WITHOUT the wheels -- verified on a pytest-only venv: 12 passed, 2 skipped):
  the bench row on a fake surface (canonical job after `ifc-harden`; argv shape
  `ifc_flow.py SAMPLE --out DIR --json`; the five files kept; BLOCKED x2 on the shared
  stderr fixtures; exit-1 = FAIL quoting the tool's `line` with the files still kept; exit-2
  = FAIL in the tool's stderr words; no-score = FAIL; the breakdown/notes shape identical to
  `ifc-harden`'s), the tool's contract with ifcopenshell + the three engine modules stubbed
  (five files + one JSON; parsed once, analysed once and THAT report + model handed to
  `harden_analysed`; exit 1 keeps every file; exit 2 writes nothing for a missing or
  unparseable input; harden flags pass through; `--quiet`), and, gated by conftest's ONE
  real-wheel gate `needs_ifc_authoring` (a `find_spec` gate is wrong here: the engine's
  steplite shim answers it once `rvt.ifc` is imported), the real tool on the sample (exit 0,
  five files, score up, 0 schema errors, `report.md` byte-identical to `report.py
  validate.json --compare harden.json`) and a child-process count of `bridge_lib.analyze`
  calls == 2.
* `tests/test_ifc_skill_bench_113.py`: the "ifc-harden is last in JOB_ORDER" pin becomes
  "after the `go` jobs, followed by its one-call form". `skills/tekton-ifc/scripts/README.md`:
  the one-call form first, the compose-by-hand path second, the tools table gains the row,
  and the stale "all four tools run in well under a second" line is replaced by the measured
  numbers (noted on #112).
* NOT in this PR (DONE 4): `SKILL.md` 5.2-5.4 -- hot file, a separate <= 10-line PR after
  this lands (rebase over #112 if that lands first).

## Evidence (this VM, 2026-08-28 01:05-01:10Z, final code, `--from-tree`, `.venv/bin/python` as the bare interpreter: py3.11 + ifcopenshell 0.8.5 + numpy 2.4.6)

`.venv/bin/python tools/surface_bench.py --from-tree --surfaces cowork --jobs ifc-harden,go-ifc-harden --python-bare /home/user/tekton/.venv/bin/python` x3:

| run | `ifc-harden` (4 calls) | `go-ifc-harden` (1 call) | in-process (`job`) |
|---|---|---|---|
| 1 | 3.34 s (validate 0.89 · harden 1.48 · re-validate 0.94 · report 0.03) | 1.56 s (validate 0.60 · harden+re-validate 0.65 · report 0.00) | 1.248 s |
| 2 | 3.32 s (0.91 · 1.56 · 0.83 · 0.03) | 1.55 s (0.60 · 0.61 · 0.00) | 1.217 s |
| 3 | 3.27 s (0.87 · 1.53 · 0.84 · 0.03) | 1.56 s (0.61 · 0.63 · 0.00) | 1.240 s |

(The first cut, before the `/simplify` pass shared the parsed model, measured 1.50-1.68 s /
in-process 1.20-1.35 s over three runs -- the two saved `ifcopenshell.open` parses are
~0.05-0.1 s on this 0.7 MB sample and scale with file size.) All three surfaces, one run:
cowork 3.2 s -> 1.5 s; codeexec 3.2 s + 0.4 s extract -> 1.5 s + 0.1 s extract (the stateless
surface also stops paying three re-extracts); local 3.3 s -> 1.5 s. Both rows: score 35.7 ->
77.0 (Tier 0 (v1-like) -> Tier 1 (partial)), 124 boxes -> extrusions, products 14 -> 13,
GlobalIds 13/13 kept, 0 schema errors after -- the same result. Bare `/usr/bin/python3` (no
wheels): both rows BLOCKED `needs numpy (pip install -r scripts/requirements.txt)` at
0.02-0.03 s, 1 call each.

Note the four-call baseline measures 3.35-3.75 s today against 5.4-5.7 s on 2026-08-27 (#113):
the same code, a quieter VM -- which is why the test compares the two rows **from the same
run**, never against a stored number.

Outputs identical to the four tools run by hand on the same input: `validate.json`,
`validate-after.json`, `harden.json` identical apart from the absolute paths they record;
`report.md` byte-identical; `hardened.ifc` differs in 26 lines -- the owner-history
modification timestamp and the fresh GUIDs of the six synthesised types + their
`IfcRelDefinesByType` -- exactly the 26 lines two runs of `harden_ifc.py` itself differ by.

Gates: `RVT_SKIP_LARGE=1 pytest tests/test_ifc_flow_754.py tests/test_ifc_skill_bench_113.py tests/test_surface_perf.py tests/test_surface_bench_reason.py tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_records_layout.py tests/test_engine.py -q` -> 106 passed, 6 skipped; the same two ifc modules on a pytest-only venv (no numpy, no ifcopenshell) -> 23 passed, 2 skipped; the perf test's PASS branch for both rows also driven by hand with the venv as the bare interpreter (holds); `tools/sync_plugin.py` + `--check` clean; `plugin/scripts/validate_plugin.py` PASS; `tools/dev/check_portable_paths.py` ok (3159 paths).

## Findings

* The four-call flow's real waste was not only the round-trips: `harden_ifc.harden()` already
  analyses its input and its reopened output, so the documented flow analysed the file four
  times. The `analyses` hook halves that without touching what the CLI prints or writes.
* Where the one-call time goes (in-process ~1.23 s of ~1.55 s wall): parse + analyse the
  input ~0.6 s, harden + reopen + re-analysis ~0.63 s, report ~0; the remaining ~0.3 s is
  interpreter start + the one ifcopenshell/numpy import. Inside `bridge_lib.analyze` the
  efficiency reviewer timed `schema_audit` ~0.28 s and `product_inventory` ~0.22 s per
  analysis (independent but sequential; overlapping them would need a forked child --
  noise against the round-trip this tool removes, so not done). The next lever is there,
  not in the flow.
* `/simplify` (four reviewers) applied: `harden_analysed()` returning `(result, after_report)`
  instead of an in/out dict; the parsed model shared with `bridge_lib.analyze(path, model=)`
  (two redundant parses gone, also in the harden CLI); one harden-flag table for both CLIs;
  `files` keyed by role and a verdict `line` in the envelope so the bench's failure reason is
  the tool's own words through `_why`; `schema_errors_after` dropped (= `after.schema_errors`);
  `_tier_name` applied once in `_ifc_breakdown`; the BLOCKED verdict shared (`_ifc_skill_blocked`);
  the two perf tests parametrized; the shared stderr fixtures imported; and the real-wheel gate
  switched from `find_spec` to conftest's `needs_ifc_authoring` (the `find_spec` form went red
  on a `.[test]` venv: the steplite shim answers it). Declined: a third fake Surface folded
  into `_FakeIfcSurface` (different semantics: stdout + a delivered directory), and
  overlapping the two audits inside `analyze`.
* `harden_ifc.py` is not deterministic run-to-run (owner-history timestamp, random GUIDs for
  synthesised types) -- a fact about the tool, recorded here so nobody reads the flow's
  differing `hardened.ifc` as a flow bug; a determinism switch would be its own small issue.
* On junk input ifcopenshell prints an `Exception ignored in: file.__del__` traceback after
  our clean `error:` line (exit 2 either way) -- the wheel's own noise, same for `validate_ifc.py`.

## Open questions / follow-ups

* DONE 4 (SKILL.md 5.2-5.4 documenting the one-call form) -- the hot-file PR, after this merges.
* #112 (SKILL.md weight/split) should describe `ifc_flow.py` as the flow when it rewrites 5.2-5.4.

## BRANCH STATE

* Branch `cam/754-ifc-flow` (from `main@4433d17`). Files: `skills/tekton-ifc/scripts/ifc_flow.py`
  (new), `skills/tekton-ifc/scripts/harden_ifc.py` (the `analyses` hook), `skills/tekton-ifc/scripts/README.md`,
  `plugin/skills/tekton-ifc/scripts/*` (mirror, via sync), `tools/surface_bench.py`,
  `tests/test_surface_perf.py`, `tests/test_ifc_skill_bench_113.py`, `tests/test_ifc_flow_754.py` (new),
  `tests/ci_shard.d/754-ifc-flow.txt` (new), this fragment + one index line in `docs/inbox/perf-surfaces.md`.
* Gates: as listed under Evidence. Nothing shipped beyond the PR; `tekton-plugin.zip` rebuilt
  locally (git-ignored); bench JSON/MD under `out/verify/v754/` (git-ignored), numbers transcribed above.
* Staged vs shipped: nothing staged for the viewer (no `.rvt`/`.rfa` involved).
