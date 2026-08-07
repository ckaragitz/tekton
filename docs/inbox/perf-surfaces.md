# inbox — perf-surfaces (SURFACE BENCHMARKS + PLAYBOOKS)

Stream: PERF-SURFACES (2026-08-04/05). Charter: build the simulated surface
harness (`tools/surface_bench.py`), benchmark the canonical skill jobs on
three bare environments approximating Cowork / code_execution / local,
write the per-surface delivery playbook (`docs/product/SURFACE-PLAYBOOK.md`),
fold the stateless-surface rules into a skill-body patch (proposed below,
NOT applied — bodies are frozen for this stream), and land a CI perf
regression gate (`tests/test_surface_perf.py`).

## Verdict in one screen

* **The harness exists and every number below came from it.** Three
  constructed bare environments: `cowork` (mount-like path with spaces and
  parens, bare non-venv python, cleared env, dead HTTP proxies as the
  no-network default, session-persistent fs), `codeexec` (STRICTLY
  stateless: fresh plugin re-extract + fresh workdir + fresh TMPDIR +
  `PYTHONDONTWRITEBYTECODE` before EVERY shell invocation; artifacts from
  earlier steps re-staged as explicit inputs = the "re-upload"), `local`
  (repo present, repo interpreter, warm). It counts WALL TIME and SHELL
  INVOCATIONS per canonical job, prints/writes a markdown table + full
  JSON, and exits 1 on any FAIL.
* **BEFORE (the shipped `tekton-plugin.zip`, 22:44 build): the edit
  round-trip was BROKEN on ALL THREE surfaces** — `rvt_edit.py set-level`
  → `rvt.manipulate.verify_manipulated` → no-arg `ObjectDecoder()` →
  `FileNotFoundError: <root>/extracted/racbasicsampleproject/
  Formats__Latest.gz/000.bin`. The exact field-bug class the standalone
  stream killed for the AUTHOR path, alive on the EDIT path (their reroute
  is activated inside the front door's build; nothing armed it for
  rvt_edit/rvt_job). Fixed this stream (fair-game territory): NEW module
  `plugin/skills/_shared/tekton_schema.py` installs a LAZY wrapper on
  `rvt.schema.load_schema` — an existing explicit path loads as before;
  the default (missing) path triggers ONE `rvt.frontdoor.standalone
  .install_schema()` activation and answers from the bundled base's
  embedded schema. Armed from `tekton_env.ensure_engine()` (~16 ms to arm
  = one `import rvt.schema`; the ~60 ms parse only happens if a decoder is
  actually needed — never during preflight). After: edit round-trip PASS
  on all three surfaces, structural verify clean (0 crc / 0 ecc / 0 walker,
  stamps ok). The sibling schema-cache stream then composed with it
  cleanly (their `_install_schema_cache` docstring documents the split:
  my wrapper decides WHERE schema bytes come from, theirs makes parsing
  them cheap).
* **AFTER (all sibling streams landed in-tree): every canonical job PASSES
  on every surface — zero FAIL, zero BLOCKED.** The two headline unlocks
  are theirs, measured here: the steplite `_ifcos_shim` makes `import
  ifcopenshell` resolve with ZERO install (preflight now reports
  `ifcopenshell=yes` on the bare no-network surfaces) so the flagship
  `--ifc electrical-room-2500a` builds end-to-end on a bare sandbox; and
  the `go` dispatch collapses readiness+job into ONE shell call
  (`go author --prompt … --json` → one combined JSON envelope), verified
  by the harness's `go-author-prompt` job.
* **The CI gate is live and green**: `tests/test_surface_perf.py` — 4
  tests, ~17 s — drives the harness's cowork surface against the plugin
  WORKING TREE and asserts: bare-env preflight **< 2 s** in ONE call;
  `author --prompt` **< 20 s** in ONE call; the edit round-trip **PASSES**
  in exactly 3 calls (guards the fix above); and the
  preflight+author+edit session stays **≤ 5 shell calls** (the
  choreography budget — a new mandatory round-trip in any flow fails CI).
  Ceilings are deliberately generous (baseline is ~20x under them); the
  point is catching a reintroduced pip, an eager heavy import, or a
  schema re-parse on the readiness path.
* **The playbook is written**: `docs/product/SURFACE-PLAYBOOK.md` — the
  cost model (round-trips and cold starts, not CPU), the
  stateless-surface rule (idempotent bootstrap / deterministic paths /
  resumable outputs / caches never load-bearing), and per-surface
  delivery: Cowork = plugin mount + skills, nothing else; code_execution
  = ONE self-contained zip uploaded ONCE via the Files API
  (`files-api-2025-04-14`, file_id reusable across conversations) +
  `container_upload` + an idempotent unpack-and-run in the SAME exec call
  (+ `container_id` reuse as a speedup, never a dependency); Claude
  Design = NO python at all — prompt → Three.js `<three-d-stage>` → IFC4
  export is the surface-native path, the .ifc re-enters via `--ifc` on a
  python surface.

## The benchmark tables (measure before claiming)

BEFORE — shipped `tekton-plugin.zip` (Aug 4 22:44 build), quiet machine:

| job | calls | cowork | codeexec (stateless) | local |
|---|---|---|---|---|
| preflight | 1 | 0.1s | 0.1s (+0.1s extract) | 0.1s |
| author --prompt (panel) | 1 | 7.5s | 7.7s | 4.6s |
| author --ifc (elec. room) | 1 | **BLOCKED** ifcopenshell | **BLOCKED** ifcopenshell | 28.8s |
| edit round-trip | 3 | **FAIL** schema path | **FAIL** schema path | **FAIL** schema path |
| validate | 1 | 0.6s | 0.8s | 0.4s |

AFTER-1 — tree with ONLY this stream's lazy-schema fix (quiet machine):
edit round-trip **PASS 2.0s / 2.6s / 1.9s** (3 calls incl. the mandatory
gate); everything else unchanged (author 7.0/6.7/5.1s — run-to-run noise
vs BEFORE; preflight unregressed at 0.1s wall, 0.016s internal).

AFTER-2 — tree with ALL sibling streams landed (`go`, steplite shim,
schema cache, frontdoor matrix/router). **Caveat: measured under load
average 65** (sibling fleets running full suites on this machine), which
inflates every wall time — preflight's pure-python internal timer alone
went 0.016s → ~0.1s, and the author job's own internal timer read
10-12s across repeats. Treat ratios between surfaces as sound and
absolute times as upper bounds; re-run on a quiet machine is one command
(below).

| job | calls | cowork | codeexec (stateless) | local |
|---|---|---|---|---|
| preflight | 1 | 0.3s | 0.2s (+0.2s extract) | 0.3s |
| author --prompt | 1 | 12.1s | 12.2s | 10.0s |
| **go author --prompt (ONE call)** | **1** | 11.4s | 12.4s | 11.3s |
| author --ifc (elec. room) | 1 | **66.5s PASS** | **92.5s PASS** | 62.7s |
| edit round-trip | 3 | 3.0s | 5.6s | 3.9s |
| validate | 1 | 0.8s | 1.4s | 1.0s |
| whole session | 8 | 94s | 124s (+1.9s total extract) | 89s |

Reading the table:
- The zip extract a stateless container pays is **~0.1-0.3 s per call**
  (2.8 MB zip) — the "unpack once per container" saving is real but small
  in wall time; its true value is choreography (no separate bootstrap
  call). Re-uploading bytes is never needed: the Files API file_id
  persists.
- `go` = the session in ONE round-trip. Two-call flow ≈ same wall time;
  the saving is the round-trip itself (seconds of model latency + tokens
  per call on a real surface, not visible in this wall-clock table).
- **OPEN (for whoever owns the next perf pass): author --prompt may have
  gained ~2x wall time with the sibling landings** (4.3-7.5s → 10-12s
  internal). Under load-65 I cannot separate contention from real cost
  (candidates: the shim making `import ifcopenshell` succeed on the
  prompt path's `rvt.ifc.intent` import; frontdoor matrix/router doing
  more per build). The 20 s CI ceiling still holds with 2x margin even
  under load. Quiet-machine check:
  `.venv/bin/python tools/surface_bench.py --from-tree --surfaces local --jobs preflight,author-prompt`.

Raw JSON for all three runs is reproducible via the harness; numbers above
are from `bench-before.json` / `bench-after.json` / `bench-after2.json`
generated this session.

## Known costs, quantified (the charter's three targets)

1. **ifcopenshell**: 179 MB installed footprint in the repo venv; import
   0.16 s once installed. On a fresh sandbox the INSTALL was the cost —
   minutes with an index, impossible without egress (both real sandboxes
   have no general egress). The sibling steplite shim retires this for
   the READ path (zero install); the real wheel remains optional for
   authoring/validation surfaces and stays a `doctor --install` concern.
2. **Cold-start compute**: `import rvt` is 0.2 ms (lazy `__init__` — the
   research-grade modules objlint/regdiff/genesis miners are NOT imported
   by the runtime paths); the 500 KB `Formats/Latest` schema parse is
   ~58 ms via `standalone.install_schema` (and now cheaper again via the
   sibling `.tksc` cache); `import rvt.schema` 16 ms; `import
   rvt.container` 8 ms. Cold-start is dominated by interpreter+numpy
   startup and first-import bytecode compilation (~1-2 s stateless), not
   by tekton's own data.
3. **Choreography**: the canonical five-job session is 7 shell calls (8
   with the go variant measured alongside); the go dispatch makes the
   author session 1. The old field session was ~17 setup commands before
   any job — that class of flow is now structurally impossible to need.

## PATCH PROPOSAL — skill bodies (apply by the skill-body owner; bodies frozen for this stream)

Add to every tekton SKILL.md body (author/edit/inspect/native; wording per
body as fits), after the readiness step:

> **On a sandboxed or stateless surface (Cowork, code_execution):**
> - Use the one-call dispatch: `python <plugin>/skills/<skill>/scripts/
>   _bootstrap.py go <job …> --json` — inline readiness + the job + ONE
>   combined JSON. Fall back to the two-call form (readiness, then
>   `run …`) only if `go` is unavailable.
> - **Never pip.** No `pip install`, no venv, no `doctor --install`
>   unless the user explicitly asks on a machine with network egress. A
>   missing extra is a one-line degrade in the JSON, not an install task.
> - **Never explore.** No filesystem archaeology, no `find`/`ls` to
>   "understand the layout", no task lists. The bootstrap owns discovery;
>   every path you need comes back in the command's JSON.
> - **Assume nothing persists between calls.** Pass inputs by explicit
>   path every time; write outputs under the user's working directory via
>   `--out`; a later step re-supplies earlier outputs as inputs.

## PATCH PROPOSAL — engine-level schema fallback (optional, integrator's call)

The `_shared` lazy fallback covers every documented flow (all skill flows
enter via `_bootstrap.py`, whose `ensure_engine` arms it). Direct engine
importers (`PYTHONPATH=lib/src python -c "from rvt.manipulate import …"`)
still hit the raw default path. If wanted, the same three-line fallback
belongs at the bottom of `rvt.schema.load_schema` (src/rvt/schema.py —
NOT edited by this stream; other fleets active):

```python
def load_schema(path: str = DEFAULT_PATH) -> Schema:
    if not os.path.isfile(path):          # bare machine: no research corpus
        from .frontdoor import standalone  # lazy; reroutes chokepoints once
        standalone.install_schema()
        return standalone.bundled_schema()
    with open(path, "rb") as fh: ...
```

## PROPOSAL — `__main__.py` at the plugin zip root (small, high leverage)

`python tekton-plugin.zip go author --prompt … --json` would make the zip
itself the entry point on code_execution: `__main__.py` (zip root =
`plugin/__main__.py`) self-extracts idempotently to
`<tmp>/tekton-plugin-<zip-sha12>/` (zipimport serves imports but the
engine open()s data files — the base .rvt, facts store — so extraction is
required) and re-execs `skills/tekton-author/scripts/_bootstrap.py` with
the passed argv. One exec call = bootstrap + job with no inline python in
the tool call. ~30 lines; sync_plugin picks it up automatically. Left
unbuilt to avoid colliding with the packaging stream's zip work mid-flight.

## Files (this stream)

* `tools/surface_bench.py` — NEW. The harness: three surfaces, six jobs
  (preflight, author-prompt, go-author-prompt [auto-SKIP on plugin builds
  predating `go`], author-ifc, edit-roundtrip, validate), invocation
  counting, per-call statelessness for codeexec, dead-proxy no-network
  guard, markdown table + JSON emitters, `run_bench()` for programmatic
  use. Zip source by default, `--from-tree` for dev.
* `tests/test_surface_perf.py` — NEW. The CI gate (4 tests, ~17 s):
  preflight < 2 s @ 1 call; author < 20 s @ 1 call; edit round-trip PASS
  @ 3 calls; session ≤ 5 calls. Skips loudly if the host has no bare
  python3 with numpy.
* `plugin/skills/_shared/tekton_schema.py` — NEW. The lazy bundled-schema
  fallback (edit-path fix; details above).
* `plugin/skills/_shared/tekton_env.py` — EDITED (fair game): +
  `_install_lazy_schema()` armed from `ensure_engine` after `import rvt`.
  (The same file also carries the sibling streams' `go`, schema-cache and
  ifcos-shim landings — coordinated live, no conflicts.)
* `docs/product/SURFACE-PLAYBOOK.md` — NEW. The per-surface delivery
  playbook (summarized above).
* `docs/inbox/perf-surfaces.md` — this record.

## BRANCH STATE (integration)

* Files EDITED by this stream: `plugin/skills/_shared/tekton_env.py`
  (the `_install_lazy_schema` hook only). Files NEW:
  `tools/surface_bench.py`, `tests/test_surface_perf.py`,
  `plugin/skills/_shared/tekton_schema.py`,
  `docs/product/SURFACE-PLAYBOOK.md`, `docs/inbox/perf-surfaces.md`.
  Frozen territory untouched (tools/frontdoor.py, SKILL.md bodies,
  src/rvt/frontdoor/base.py, src/rvt/versions/, src/rvt/** generally).
  Patches for skill bodies + src/rvt/schema.py delivered above, NOT
  applied.
* **Zip: REBUILT mid-stream by the integrator (23:27 build)** — it now
  ships this stream's `tekton_schema.py` + hook AND the sibling shim /
  schema-cache / `go`; spot-checked from the zip: preflight READY with
  `ifcopenshell=yes`, `go author --prompt` PASS in ONE call (20.1s cold,
  under load-65). `sync_plugin --check` still shows drift for two
  even-newer sibling modules (`genesis/port2024.py`,
  `convert/extract_family.py`) — normal mid-flight; whoever closes last
  re-syncs. Final shipped-zip AFTER table on a quiet machine is one
  command: `.venv/bin/python tools/surface_bench.py --json bench.json`.
* Suite (full `tests/`, chunked serially 2026-08-05 ~00:10 tree state,
  quiet machine): **1662 passed, 6 failed, 2 skipped** (85 files; the
  live tree gained sibling test files during the run — count is
  timestamped, not eternal). ALL 6 failures trace to two SIBLING streams'
  in-flight work, none to this stream's modules:
  - 1x `test_genesis_assemble.py::test_ladder_end_to_end` — four-registry
    incoherence on the G0a assembler build vs base R10b (genesis streams'
    active rebase territory).
  - 5x sharing ONE root cause: `test_router.py` 3x E2E ("SELF-CHECKS
    FAILED (combined)") + `tests/test_surface_perf.py` 2x (author +
    edit-roundtrip). **THE PERF GATE CAUGHT A LIVE REGRESSION**: between
    23:27 (everything green, incl. from the rebuilt zip) and ~23:55, the
    instbug-fix stream landed its VALIDATOR LAW (`src/rvt/validate.py`:
    placed FamilyInstances must carry `FamilyInstanceConnectorManager`,
    never base `ConnectorManager` — corpus 13,636/13,636) and the fix
    layer module `src/rvt/famload_fix.py`, but NOT yet the wiring that
    makes the product path apply it (grep: nothing imports famload_fix).
    Every combined build with a placed instance now reports
    `SELF-CHECKS FAILED (combined)` / validator error `instance 1472584:
    ConnectorManager` — exactly their charter's defect D1
    (docs/inbox/instbug-fix.md), law landed ahead of emitter fix. Their
    record has since CLOSED (00:1x): the fix layer is proven
    (`famload_fix.fixed_product_path()`, 13/13 stream tests, probes VALID
    0 errors under the new rule, zero false positives over 81 certified
    files) and the PRODUCT wiring is delivered as exact §DIFFS for the
    owning streams — deliberately NOT applied. Until the integrator
    applies instbug-fix §DIFFS, every frontdoor prompt/ifc combined build
    reports SELF-CHECKS FAILED, and `test_router` (3) +
    `test_surface_perf` (2) stay red — CORRECTLY. They flip green with
    the diffs applied, zero changes on this stream's side. Verified
    order-independent (standalone rerun fails identically).
* DONE = harness + three-surface before/after tables + playbook +
  regression gate: **met**. Open items handed forward: (1) the
  instbug-fix wiring landing flips test_router + test_surface_perf green
  — re-run `pytest tests/test_surface_perf.py -q` after; (2) the possible
  ~2x author-prompt slowdown under the new landings (quantify on a quiet
  machine; one command, above); (3) the genesis_assemble ladder failure
  belongs to the genesis streams.
