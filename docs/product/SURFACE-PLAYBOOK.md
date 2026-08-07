# SURFACE PLAYBOOK — delivering tekton to each AI surface, fast

Status: 2026-08-04, perf-surfaces stream. Companion pieces:
`tools/surface_bench.py` (the simulated-surface benchmark that backs every
number here), `tests/test_surface_perf.py` (the CI regression gate),
`docs/product/MCP-PATH.md` (the documented future path — not built now).

## The cost model (why this document exists)

On a sandboxed AI surface the expensive unit is not CPU — it is:

1. **The shell invocation.** Every Bash call is a full model round-trip
   (seconds of model latency + tokens), so a flow's cost is dominated by its
   CALL COUNT, not its wall time. The field failure was ~17 setup commands,
   not 17 slow commands.
2. **The cold start.** A fresh VM/container has never seen the plugin: no
   repo, no venv, no caches. Anything that needs `pip install` of a heavy
   binary wheel (ifcopenshell: ~179 MB installed) costs minutes when an
   index is reachable and is IMPOSSIBLE when it is not (the field Cowork
   session had zero PyPI egress). The plugin therefore bootstraps by
   `sys.path` insertion from its own bundled files — never pip.
3. **Statelessness.** On some surfaces nothing persists between calls. Any
   flow that requires call N+1 to remember call N's filesystem breaks there.

Measured baseline (2026-08-04, `tools/surface_bench.py`, shipped-zip/tree
source; bare python 3.9 with numpy, no ifcopenshell, dead proxies):

| job | shell calls | cowork (bare VM) | code_execution (stateless/call) | local (warm repo) |
|---|---|---|---|---|
| preflight | 1 | 0.1s | 0.1s | 0.1s |
| author --prompt (panel) | 1 | 7.0s | 6.7s | 5.1s |
| author --ifc (electrical room) | 1 | BLOCKED (ifcopenshell) | BLOCKED (ifcopenshell) | 29.2s |
| edit round-trip (info+edit+gate) | 3 | 2.0s | 2.6s | 1.9s |
| validate | 1 | 0.5s | 0.7s | 0.5s |
| whole session | 7 | ~10s | ~10s (+0.1s/call unpack) | ~37s |

The engine is NOT the bottleneck anywhere; the choreography is. Keep it at
one-command-per-job and every surface stays interactive.

## The stateless-surface rule (applies everywhere, mandatory on code_execution)

**Never require step N+1 to remember step N's filesystem.** Concretely:

- **Idempotent bootstrap.** `_bootstrap.py` resolves the plugin root by
  walking up from its own file and re-arms the engine on every call —
  calling it twice costs nothing, skipping it never breaks a later call.
  Any future bootstrap step must keep this property (safe to re-run, cheap
  when already done, e.g. "unpack if absent" keyed by content hash).
- **Deterministic paths.** Outputs land where the CALLER said (`--out DIR`),
  inputs are passed as explicit paths on the same command line. No step may
  depend on cwd history, `$TMPDIR` contents from a prior call, or an env
  var exported by an earlier shell (each call re-exports its own via the
  bootstrap).
- **Resumable outputs.** A job writes its full result set (files + manifest
  + JSON summary) in the one call that ran it. If the filesystem is gone
  next call, re-supplying the input file and re-running the ONE command
  reproduces it — no multi-step state to rebuild. Artifacts that a later
  job needs (the authored `.rvt` for an edit) re-enter as explicit inputs
  ("re-upload"), exactly like the user's own files do.
- **No hidden warm state as a correctness dependency.** Caches (bytecode,
  the schema cache) may make call 2 faster than call 1, but no flow may
  REQUIRE the cache to exist.

`tools/surface_bench.py --surfaces codeexec` enforces this by construction:
it wipes the plugin, workdir, TMPDIR, and env before EVERY invocation. If a
flow passes there, it is stateless-safe everywhere.

## Surface 1 — Cowork VM (and claude.ai sandbox sessions)

**Delivery: the plugin mount + skills. Nothing else.** The user (or org
config) installs `tekton-plugin.zip` as a Claude plugin; Cowork mounts the
unzipped plugin folder somewhere arbitrary (spaces, parentheses, mount
prefixes — all fine: root resolution walks up from the bootstrap's own file
and never searches). The five SKILL.md files are the entire interface.

Session shape (what the model should do — see the skill bodies):

1. `python <plugin>/skills/<skill>/scripts/_bootstrap.py` → ONE readiness
   line, <2 s. READY → go. NOT READY → relay the line; it names the one
   thing wrong.
2. ONE job command (`_bootstrap.py run frontdoor.py author … --json`, or
   the `go` one-call dispatch once shipped, which folds step 1 into the
   job call). The printed JSON IS the report — relay it, never re-explore.

Facts the session must assume:

- **No network.** No PyPI egress, no `pip install` ever. The engine +
  vendored olefile are bundled; numpy is preinstalled on the VM;
  ifcopenshell is absent → the `--ifc` read route runs on the bundled
  pure-python fallback when present, else reports BLOCKED in one line
  (never attempts an install).
- **The VM persists for the session** — outputs written under the working
  directory survive across calls; the second job in a session is warm.
  Persistence is a speedup, never a dependency (rule above).
- **Bare python.** Assume ≥3.9, no venv, no site customization. The
  bundled source runs there (`requires-python` in lib/pyproject.toml is a
  pip constraint; the bundle bypasses pip entirely).

## Surface 2 — Messages-API code_execution (stateless containers)

**Delivery: ONE self-contained zip, uploaded once, unpacked once per
container, dispatched through one entry point.** The working recipe:

1. **Upload `tekton-plugin.zip` ONCE via the Files API**
   (`client.beta.files.upload`, beta `files-api-2025-04-14`; the zip is
   ~2.8 MB, far under the 500 MB cap; files persist until deleted, so the
   `file_id` is reusable across conversations — upload once per
   INTEGRATION, not per conversation, and re-send only the id).
2. **Attach it to the request** as a `container_upload` content block; the
   file lands in the container. Declare the code-execution tool
   (`code_execution_20260120`).
3. **First exec call unpacks idempotently to a deterministic path** and
   runs the job in the SAME call — unzip is ~0.1 s, so bootstrap+job is
   still one call:

   ```python
   import zipfile, subprocess, sys
   DEST = "/tmp/tekton-plugin"           # deterministic; keyed location
   if not os.path.isdir(os.path.join(DEST, ".claude-plugin")):   # idempotent
       zipfile.ZipFile("tekton-plugin.zip").extractall(DEST)
   subprocess.run([sys.executable,
       f"{DEST}/skills/tekton-author/scripts/_bootstrap.py",
       "run", "frontdoor.py", "author", "--prompt", PROMPT,
       "--json", "--out", "/tmp/out-job1"], check=False)
   ```

4. **Reuse the container across turns** where latency matters: pass
   `container=response.container.id` on the next request and the unpacked
   plugin + bytecode cache are still there (containers persist ~30 days
   and are reusable). But per the stateless rule, NEVER depend on it —
   the idempotent unpack in every exec snippet makes a fresh container a
   0.1 s detour, not a failure.
5. **One exec call = one job.** The `--json` result is printed to stdout
   and comes back in the tool result; result FILES (the `.rvt`) are
   retrieved via the Files API file ids the code-execution result carries.
   Recommended addition (proposed, not yet shipped): a `__main__.py` at
   the zip root so `python tekton-plugin.zip author --prompt … --json`
   self-extracts (idempotent, hash-keyed dest) and dispatches — collapsing
   even the unpack snippet into a single argv with no inline python.

Facts the exec code must assume:

- **Every invocation may be a fresh container** (new conversation, expired
  container). Cold start = unpack (~0.1 s) + first-import compile (~1-2 s
  extra on the first job). Budget: preflight <2 s, author <20 s hold even
  fully cold — see `tests/test_surface_perf.py`.
- **numpy is preinstalled; ifcopenshell is not.** Treat pip as
  unavailable (the sandbox has no general egress). Same degrade contract
  as Cowork.
- **Inputs re-enter per conversation.** A user `.rvt`/`.ifc` arrives as a
  Files-API upload → `container_upload`; a prior job's output re-enters
  the same way. Deterministic `--out` paths under `/tmp` keep retrieval
  trivial.

## Surface 3 — Claude Design (prompt → Three.js → IFC handoff)

**Claude Design should NOT run python at all.** Its surface-native
strength is the `<three-d-stage>` page: the user co-builds the model as a
Three.js scene and the page's IFC button exports an IFC4 STEP file through
the canonical `ifc-export.js` (`toIfc(THREE, object, meta)`) with the
tagging-contract Psets (`skills/tekton-ifc`). That IFC file IS the
deliverable of the Design session.

The handoff path (both directions already shipped):

- **prompt → Design:** the prompt route always writes the AI-surface
  handoff package (`scene-brief.json`, `HANDOFF.md`, `PROMPT_TO_IFC.md`)
  next to its build — hand these to a Design session and it builds the
  scene with zero python.
- **Design → .rvt:** the exported `.ifc` re-enters tekton on a
  python-capable surface (Cowork / code_execution / local) via ONE
  command: `_bootstrap.py run frontdoor.py author --ifc <file>.ifc --json`.

Do not ship or suggest python bootstrap steps inside Design sessions; the
skill's sandbox scripts (`validate_ifc.py`, `harden_ifc.py`) run on the
python surface the file lands on, not in Design. The division of labor is
the point: geometry authoring where the 3D viewer is, `.rvt` writing where
python is.

## Local Claude Code (the fourth surface, for completeness)

The repo is present and warm; the same skill flows work unchanged (the
plugin folder in the repo IS the plugin). Use `.venv/bin/python` from the
repo root per the repo rule; both optional extras are installed there, so
the `--ifc` route runs natively (~29 s for the flagship room). This is the
only surface where `doctor --install` is normally sensible.

## The rules to fold into every skill body (patch proposal in docs/inbox/perf-surfaces.md)

On a stateless or sandboxed surface, the session MUST:

1. **Always use the one-call dispatch** (`go` once shipped; until then
   readiness + job = two calls, never more). The job's printed JSON is the
   report — relay it verbatim, do not re-open files it already summarized.
2. **Never pip.** No `pip install`, no venv, no `doctor --install` unless
   the USER explicitly asks on a machine with egress. A missing extra is a
   one-line degrade, not an install task.
3. **Never explore.** No `find`/`ls` archaeology, no reading directories to
   "understand the layout", no task boards. The bootstrap owns discovery;
   every path the session needs is in the command's JSON result.
4. **Re-state inputs explicitly.** Pass files by path on the command line
   every time; write outputs under the user's working directory via
   `--out`; assume nothing about what survived from the previous call.

## Benchmarks: how to re-measure

```bash
# full three-surface table (shipped zip), JSON + markdown out
.venv/bin/python tools/surface_bench.py --json bench.json --md bench.md

# after editing plugin/ but before rebuilding the zip
.venv/bin/python tools/surface_bench.py --from-tree

# one surface / job subset while iterating
.venv/bin/python tools/surface_bench.py --surfaces codeexec --jobs preflight,author-prompt
```

The harness builds each surface from scratch (mount-like paths, cleaned
env, dead proxies for the no-network default, per-call re-extraction for
code_execution), counts every shell invocation, and fails RED (exit 1) on
any job whose surface should support it. CI runs the cowork surface via
`tests/test_surface_perf.py` with the ceilings: **preflight < 2 s, author
< 20 s, edit round-trip green, ≤ 5 calls for preflight+author+edit** —
generous on purpose; the point is catching regressions (a reintroduced
pip, an eager heavy import, a new mandatory round-trip), not shaving
tenths.
