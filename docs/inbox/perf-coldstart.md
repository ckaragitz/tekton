# inbox — perf-coldstart (COLD-START CACHES + ONE-CALL DISPATCH)

Stream: PERF-COLDSTART (2026-08-04). Charter: sessions on sandboxed AI
surfaces were "bashing a lot" — every Bash call is a full model round-trip,
pip installs of heavy wheels cost minutes on a fresh VM. (1) profile the
cold path honestly, (2) build-time schema cache, (3) lazy imports of
heavyweight modules, (4) one-call dispatch, (5) before/after numbers.
Territory: `src/rvt/schema_cache.py`, `src/rvt/_lazyimp.py`,
`plugin/skills/_shared/tekton_env.py`, `plugin/skills/*/scripts/
_bootstrap.py`, `tests/test_coldstart.py`, this record.

**Concurrency note (load-bearing for attribution):** this stream ran while
other fleets were landing overlapping work in the same tree.  Mid-stream,
after I posted my plan to the orchestrator, complementary edits appeared
that implement parts of it (marked "[found in tree]" below): the
numpy-free prompt-route call sites, the np-free `Placement` accessors, the
`sync_plugin.py` cache step wired to my `sync_assets()`, most of
`tests/test_coldstart.py`, and the `tekton_schema.py` lazy-schema fallback
+ ifcopenshell steplite shim (separate streams).  Everything was verified
end-to-end by THIS stream regardless of which session typed it; nothing
below is claimed that was not re-run and measured here.

## Verdict in one screen

* **One Bash call per job.** `_bootstrap.py go author --prompt "..." --out d`
  runs inline preflight + the job + prints ONE combined JSON
  (`.go.ready`, `.go.preflight_line`, `.result` = the job's own `--json`).
  The documented two-call flow (preflight, then run) is now compat.  On an
  AI surface this saves a full model round-trip per job — the single
  biggest latency item after pip.  Local wall (loaded machine, interleaved
  A/B): two-call handoff 621 ms vs one-call 226 ms warm.
* **Zero pip for the flagship route.** With numpy ABSENT (`python -I -S`,
  vendored olefile only): `import rvt.frontdoor` works, the prompt parser
  runs, the handoff package emits (exit 0, 0.106 s wall in the bare env),
  and the FULL prompt fallback native build completes and delivers the
  combined `.rvt` + families.  Before: instant `ModuleNotFoundError:
  numpy` at import time for the entire author route, pushing a minutes-long
  `pip install numpy` (fresh-VM measure) onto the hot path.  numpy is now
  needed only by the VALIDATION GATE (ECC page-syndrome math is genuinely
  vectorised) — without it the build still delivers, exit 4, and the
  manifest carries ONE clear line naming numpy (the deliverable rule).
* **Schema parse off the hot path.** `rvt.schema_cache` (NEW): at plugin
  BUILD time (a `sync_plugin.py` step) each bundled release schema is
  parsed once and shipped as `assets/schema_cache/<schema-sha256>.tksc`
  (marshal-v2 of the class table; deterministic bytes — proven identical
  when written by CPython 3.9 and 3.12).  At runtime `rvt.schema.parse` is
  wrapped (armed by `ensure_engine`): sha256 of the input bytes keys the
  cache, hit = reconstruct (~2.2x faster than parsing: 38 ms vs 82 ms on
  the bare env's python 3.9; 21 ms vs 44 ms on 3.12), miss = the real
  parser.  A wrong hit is impossible by construction (the key IS the
  content hash).  Fidelity is proven class-for-class by test.
* **The research modules were already clean.** objlint / regdiff / census /
  miners / render / mep are NOT imported on the author path (measured by
  `-X importtime`: 324 modules, none of them) — no work needed there.
* **The remaining cold-start budget is the BUILD, not the bootstrap.**
  Bootstrap+imports+schema together are ~0.4 s of a ~17-19 s full native
  build (bare env, python 3.9, idle machine).  The build's own hot spots
  (for a future engine stream): stage L family loads 2.3-2.7 s EACH
  (3 loads = 7.3 s = 44% of the 16.6 s build), the rest famgen + walls +
  equipment + validate 0.4 s.
* Full suite + coldstart tests: see BRANCH STATE (bottom).

## 1. The honest profile (bare env, BEFORE any of this stream's changes)

Simulated bare env = fresh TMPDIR containing ONLY the unzipped plugin tree
(no `__pycache__`), system python 3.9.6 (`/usr/bin/python3`), `env -i`
(cleared environment), numpy provided on PYTHONPATH only where stated
(sandboxes normally ship it; the no-numpy rows are the fresh-VM floor).
Idle machine (load < 2). "cold" = no `.pyc` anywhere; "warm" = second run.

| # | measurement (before) | cold | warm |
|---|---|---|---|
| a1 | python startup (`-c pass`) | 0.024 s | — |
| a2 | `_bootstrap.py` preflight line (whole process) | 0.069 s | 0.065 s |
| b | `author --handoff-only` two-call step 2 (whole process) | 0.235 s | — |
| c | engine import (`rvt.frontdoor` cum, `-X importtime`) | 60 ms | — |
| c | of which numpy | 47 ms | — |
| c | `Formats/Latest` inflate from bundled base | 9.5 ms | 8.0 ms |
| c | `rvt.schema.parse` (496,597 B, 4,690 classes) | 67 ms | 67 ms |
| d | FULL `author --prompt` native build (800 A room: 3 families, walls, validate), whole process | 19.3 s | 16.8 / 18.8 / 19.2 s |
| — | same, python without numpy | **crash at import** (`ModuleNotFoundError: numpy` before any work) | — |

`-X importtime` totals for the full run: 0.177 s of import self-time over
324 modules; top offenders numpy 47 ms cum, `rvt.ifc.intent` 53 ms cum
(numpy inside it), everything else < 8 ms.  Imports are NOT the build's
bottleneck — the build compute is (see §6) — but numpy was a hard
IMPORT-TIME dependency, which is the real cost (pip on a fresh VM).

Where the 19 s full build goes (manifest stage timings): `build.seconds`
16.6 s, of which 3 family LOADS at 2.3/2.3/2.7 s; validate 0.4 s.

## 2. Build-time schema cache (`src/rvt/schema_cache.py`, NEW)

* **Format**: `TKSC` magic + `marshal.dumps(payload, 2)` of plain tuples
  (no pickle — loading a hostile file cannot execute code; any structural
  surprise = miss, never a crash).  1,289,337 B for the 2026 schema.
  Deterministic: rebuilds byte-identical, INCLUDING across CPython 3.9 vs
  3.12 (verified), so `sync_plugin.py --check` treats it as an ordinary
  synced asset.
* **Build time**: `python -m rvt.schema_cache build [--plugin-root R]`
  parses the schema embedded in every bundled container
  (`assets/genesis/*.rvt|.rfa`, `assets/family/*`), one cache file per
  UNIQUE schema sha (a release constant however many containers carry it),
  plus `index.json` (sha, bytes, classes, release from the frontdoor pin,
  sources).  `sync_assets()` is the sync-step API: rebuild to temp,
  byte-compare, copy on drift, delete stale — wired into
  `tools/sync_plugin.py` `sync_schema_cache()` [found in tree, uses this
  module exactly as designed; verified: `--check` reports the cache IN
  SYNC and homebrew-3.12 rebuilds produce zero drift].
* **Runtime**: `rvt.schema_cache.install()` wraps `rvt.schema.parse`
  (original kept as `parse._schema_cache_orig`); armed from
  `tekton_env.ensure_engine()` via `_install_schema_cache()` right after
  the `tekton_schema.py` lazy-schema fallback — the two COMPOSE: that
  wrapper decides WHERE schema bytes come from, this one makes
  bytes→parsed-Schema cheap.  Verified composition points: standalone's
  `bundled_schema()` (`_from_cache=True`), the lazy `load_schema` fallback,
  AND `rvt.versions.schema_of()` (release parity — a 2026 container hits
  the cache; an uncached release falls through to the real parser).
  Cache dirs: `$RVT_SCHEMA_CACHE_DIR` →
  `$RVT_PLUGIN_ROOT/assets/schema_cache` → the bundled-engine/repo layouts
  walked from `rvt/__file__`.  Engine use WITHOUT the bootstrap can arm it
  explicitly (`from rvt import schema_cache; schema_cache.install()`).
  Cost of arming: preflight's internal time went 0.013 → 0.026 s in the
  bare env (the lazy-schema + cache installers together); budget is < 2 s.
* **Fidelity**: reconstructed Schema is class-for-class identical (id /
  name / parent / version / offsets / field tuples incl. nested array
  elements / guids / desc_hist / type_refs / top_level) — asserted by
  `tests/test_coldstart.py::test_schema_cache_roundtrip_is_class_for_class_identical`.
  Loaded schemas carry `_from_cache = True` for verifiability.
* **Measured delta** (same blob, same process, min of 3):

  | python | parse | cache load | speedup |
  |---|---|---|---|
  | 3.9.6 (bare env) | 81.6 ms | 38.0 ms | 2.1x |
  | 3.12 (.venv) | 44.4 ms | 20.6 ms | 2.2x |

  Per-process saving ~40-45 ms on the sandbox floor; the schema is parsed
  once per PROCESS (standalone memoises in `_SCHEMA_STATE`), so the cache
  pays on every fresh Bash call that reaches a decoder (builds, edits,
  validates — the edit path hits it via `tekton_schema.py`'s fallback).

## 3. Lazy imports — every changed import, listed

New module `src/rvt/_lazyimp.py` (`lazy_import(name, globals(), binding,
hint)`): a proxy that imports on FIRST ATTRIBUTE ACCESS, rebinds the
owner's global to the real module (zero steady-state indirection), and on
a genuinely missing module raises ImportError at the point of USE naming
the module, the operation, and the one-time fix.  Safe here because all
three patched modules use `from __future__ import annotations` and
evaluate no module-level `np.…` (checked).

| file | before | after (mine) |
|---|---|---|
| `src/rvt/ifc/intent.py` | `import numpy as np` (module level) | `np = lazy_import("numpy", globals(), "np", hint="IFC placement / geometry resolution")` |
| `src/rvt/frontdoor/prompt_intent.py` | `import numpy as np` (module level) | `np = lazy_import("numpy", globals(), "np", hint="prompt-intent numeric math")` |
| `src/rvt/validate.py` | `import numpy as np` (module level) | `np = lazy_import("numpy", globals(), "np", hint="ECC page syndrome math")` |

[found in tree, same stream label, verified here]: the prompt route's np
CALL SITES were then made pure-python so the proxy never fires on it —
`parse_prompt`'s consumed mask `np.zeros(len(text), bool)` → `bytearray`
(+ `sum(consumed)`), `_upright_frame` → `math.hypot` + explicit 3-vector
cross, `I.Placement(np.eye(4), …)` → `I.Placement(I.identity_matrix(), …)`
with `Placement.origin/identity/as_json` + `is_identity` handling ndarray
OR nested lists.  `tools/ifc_to_spec.py` keeps its module-level numpy +
ifcopenshell — it IS the IFC route script (never imported by the prompt
path).  `rvt.provenance` already used function-local numpy imports.
ifcopenshell was already conditional in `rvt.ifc.intent` (try/except) and
a separate stream shipped a pure-python steplite shim
(`rvt/ifc/_ifcos_shim`) — not this stream's work.

Measured effect (bare env, `env -i`, NO numpy anywhere):

| flow | before | after |
|---|---|---|
| `import rvt.frontdoor` / `rvt.validate` | ModuleNotFoundError | OK, `numpy` not in `sys.modules` |
| `go author --handoff-only --prompt …` | crash | **exit 0, 0.106 s** (whole one-call process) |
| full `author --prompt` native build | crash | builds + delivers combined `.rvt` + 3 families; validator ECC tier reports numpy in ONE line; exit 4 (`--no-validate`: exit 0) |

numpy remains REQUIRED for a green validation gate: `ecc_verify_stream`
is the validator's READ path (syndrome-verify + repair of every CRCIO
page) and is genuinely vectorised.  Proposed follow-up for the validator
stream (NOT done here — behavior change): catch the ImportError at the
ECC tier and report `verdict: UNVERIFIED (numpy absent)` instead of
`ERROR`, keeping `self_checks_ok = false` (the gate must not silently
weaken) but making the wording match reality.

### 3a. Exact final import blocks (for reconciling later patches)

Requested by the orchestrator so the deps stream's patches can be rebased
against THIS text instead of hitting a context mismatch.

`src/rvt/ifc/intent.py`, lines 64–89, verbatim:

    from __future__ import annotations

    import json
    import math
    import os
    import re
    from collections import defaultdict
    from dataclasses import dataclass, field as dc_field
    from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

    # LAZY (perf-coldstart): numpy loads on first numeric use, so importing this
    # module -- which the whole front door does -- is instant and survives a
    # sandbox without numpy; the geometry paths are unchanged once touched.
    from .._lazyimp import lazy_import

    np = lazy_import("numpy", globals(), "np",
                     hint="IFC placement / geometry resolution")

    try:  # ifcopenshell is required to READ an IFC; keep the module importable
        import ifcopenshell  # type: ignore
        import ifcopenshell.util.element as _ue  # type: ignore
        _HAVE_IFCOS = True
    except Exception:  # pragma: no cover - the sandbox always has it
        ifcopenshell = None  # type: ignore
        _ue = None           # type: ignore
        _HAVE_IFCOS = False

`src/rvt/frontdoor/prompt_intent.py`, lines 42–57, verbatim:

    from __future__ import annotations

    import json
    import math
    import os
    import re
    from dataclasses import dataclass, field as dc_field
    from typing import Any, Dict, List, Optional, Sequence, Tuple

    # LAZY (perf-coldstart): the prompt route is pure-python end to end; numpy
    # stays un-imported unless a numeric path is actually exercised.
    from .._lazyimp import lazy_import

    np = lazy_import("numpy", globals(), "np", hint="prompt-intent numeric math")

    from ..ifc import intent as I

**Prompt-path numpy answer for the deps stream** (asked by the
orchestrator): numpy is NOT needed anywhere on the prompt path except the
validation gate's ECC syndrome math (`rvt.validate` L1 — genuinely
vectorised `np.unpackbits`/matrix work per page; a pure-python port would
be seconds-per-file).  Parse, layout, intent construction, handoff, famgen,
family load, walls, equipment, census, identity, and the g1 provenance gate
all run numpy-free (proven by the full `-I -S` build).  A stdlib fallback
therefore erases the numpy dependency for everything except a green
validator verdict; the cheapest full erasure is the §3 wording proposal
(state `UNVERIFIED (numpy absent)`), not a syndrome-math port.

## 4. One-call dispatch (`go`)

`tekton_env.py` (fair game, edited): `go(argv, base_dir)` + `cli` wiring +
`_resolve_go_target` — `go author …` routes to `frontdoor.py` (resolved
beside the calling skill, else the canonical copy under
`skills/tekton-author/scripts/` from the plugin root; never a search);
`go SCRIPT.py …` runs any sibling script the same way.  `--json` is
auto-appended for `go author`.  stdout = ONE JSON:

    {"go": {"one_call": true, "ready": true, "preflight_line": "tekton: READY | ...",
            "preflight_seconds": 0.01, "job_seconds": 17.2, "seconds": 17.3,
            "exit_code": 0},
     "result": { ...the front door's own --json result... }}

NOT READY → `.go.preflight` carries the full dict, `.result` null, exit 3,
job never attempted.  A crashing job still yields ONE json
(`.go.exception`, raw stdout tail in `.go.stdout` when non-JSON).  Exit
code = the job's own (0/2/3/4).  `run`, bare preflight, `--json`, `--env`,
`doctor` all unchanged (compat proven by tests).  All four skill
`_bootstrap.py` shims stay byte-identical (re-exporting `go`).

Round-trip math on a real surface: the documented flow was 2 Bash calls
(preflight, then job) = 2 model round-trips; `go` makes it 1.  Local wall
saving is secondary (~0.3-0.4 s: one interpreter+preflight spin-up) — the
round-trip itself (seconds per call on Cowork/code_execution) is the win.

## 5. Before/after, measured

**Idle-machine bare env** (the canonical absolutes, §1 baseline vs the
after tree, system python 3.9, numpy present, `env -i`):

| flow | before | after | delta |
|---|---|---|---|
| readiness + handoff job (the documented skill flow) | 2 Bash calls (0.069 + 0.235 s local; 2 round-trips) | 1 Bash call (`go`, ~0.24 s warm local; 1 round-trip) | −1 model round-trip, −1 process |
| same, numpy absent (fresh VM floor) | crash → `pip install numpy` (minutes) → retry | exit 0, 0.106 s | the pip disappears from the route |
| schema bytes → parsed Schema (per process) | 82 ms (parse) | 38 ms (cache) | −44 ms (2.1x) |
| full native build (800 A room) | 16.8-19.3 s | see A/B below — dominated by build compute this stream did not touch | ~0 (as expected) |

**Loaded-machine interleaved A/B** (other fleets running, load avg 40-70 —
absolutes inflated 3-5x, but each A/B pair sees the same load; medians of
3 pairs, before-tree vs after-tree):

| metric | before | after |
|---|---|---|
| py startup (same binary — load indicator) | 126 ms | 63 ms |
| preflight cold | 220 ms | 200 ms |
| preflight warm | 248 ms | 226 ms |
| handoff TWO-call warm (preflight + run) | 706 ms | 588 ms |
| handoff ONE-call `go` warm | — | **239 ms** |
| in-proc schema parse | 200 ms | 193 ms (unwrapped control) |
| in-proc cache load | — | **86 ms** (hit rate 3/3) |

(The preflight delta is noise; the load-bearing comparisons are two-call
vs one-call and parse vs cache-load, which hold under load.)

The full-build A/B was re-run when the machine quieted; see the appended
FINAL NUMBERS section at the bottom of this record.

## 6. What this stream did NOT do (the next perf targets, with data)

1. **Stage L family loads: 2.3-2.7 s each** — 44% of the build.  The
   twinning/decode work per load looks super-linear in document size;
   worth a dedicated engine stream (cache the decoded base document
   between loads instead of re-decoding per stage?).
2. **famgen + walls + equipment ≈ 8-9 s** for 3 families — second target.
3. Validator ECC wording when numpy is absent (§3 proposal).
4. `--target-version` bases for 2025/2024 will add more bundled schemas —
   `schema_cache build` already handles N containers / N releases
   (one file per unique sha) with zero code change.

## 7. Deliverable patches (NOT applied — owners' files)

### 7a. `plugin/skills/tekton-author/SKILL.md` — the one-call flow

Replace the whole of `## Step 1 — readiness (ONE command, <2 s)` and the
heading + first paragraph of `## Step 2 — the job (ONE command; its
--json IS your report)` with the block below (the inner code fences are
prefixed with a zero-width space so they nest here — STRIP that character
when applying):

```markdown
## The job — ONE command (readiness included)

Exactly one input per call — a prompt, an IFC, or an existing `.rvt`:

​```bash
python <plugin>/skills/tekton-author/scripts/_bootstrap.py go \
    author --prompt "an electrical room 30x20 ft rated for 2500 A service with a main \
    switchboard, two 400 A distribution panels and four lighting panels" --out out/job1

python <plugin>/skills/tekton-author/scripts/_bootstrap.py go \
    author --ifc <their-file>.ifc --out out/job2

python <plugin>/skills/tekton-author/scripts/_bootstrap.py go \
    author --rvt their.rvt --edit "delete DP-1 with cascade; move LP-2 to 3,4" --out out/job3
​```

That ONE command runs readiness + the job and prints ONE JSON object:

- `.go.ready` / `.go.preflight_line` — when `ready` is false, relay the
  line verbatim and stop; it names the one thing wrong and the job was
  never attempted (exit 3).  `family-donor missing` in the line is FINE
  (the family container is built from the bundled genesis base). Never
  read, probe, list, or request access to any Autodesk installation
  directory; a donor comes ONLY from the plugin's bundled assets or a file
  the user supplies.
- `.result` — the deliverable summary, exactly the old step-2 `--json`:
  relay `status` verbatim, hand over `files`, read
  `manifest.honesty.proof_only_stamps` / `build.degradations` /
  the validator summary, `errors` each name their single missing input.

Exit codes unchanged: 0 = route completed (PROOF-ONLY is still 0);
2 = usage; 3 = not ready / build incomplete; 4 = self-checks failed
(deliver the file WITH the failed-self-check report and say plainly it
failed our own validator).  No pip install, no venv, no `eval`, no task
lists, no exploring the filesystem — ONE call does preflight + job +
report.  (`_bootstrap.py` alone still prints just the readiness line;
`_bootstrap.py run frontdoor.py author …` remains as the two-call compat
flow.)
```

…and in the `## Reference` table change the `scripts/_bootstrap.py` row to:

```markdown
| `scripts/_bootstrap.py` | `go` ONE-call flow (preflight+job+one JSON) · readiness line · `run <script> …` launcher · `doctor` |
```

Same pattern applies to the flows in `tekton-edit` / `tekton-inspect` /
`tekton-native` SKILL.md bodies when their fleets free them:
`_bootstrap.py go <script>.py ARGS…` replaces their preflight+run pairs
(the combined-JSON contract is identical; non-`--json` scripts get their
stdout in `.go.stdout`).

### 7b. `KNOWLEDGE.md` proposed entry (orchestrator merges)

> **One Bash call per skill job.** `_bootstrap.py go …` = preflight + job +
> ONE combined JSON (`.go` + `.result`); every extra Bash call on a
> sandboxed surface is a full model round-trip.  numpy/ifcopenshell are
> LAZY: the prompt route (parse → handoff → native build) runs with zero
> extras; only the validation gate's ECC math needs numpy and says so in
> one line.  The parsed `Formats/Latest` ships pre-parsed in
> `assets/schema_cache/` (sha256-keyed, rebuilt by `sync_plugin.py`);
> `rvt.schema.parse` hits it automatically under the bootstrap.

## 8. Files touched by THIS stream

* NEW `src/rvt/schema_cache.py` (+ mirrored `plugin/lib/src/rvt/`) — cache
  build/load/install/sync_assets/CLI; vendored-olefile fallback so
  `sync_plugin.py` runs under any python.
* NEW `src/rvt/_lazyimp.py` (+ mirror) — the lazy-import proxy.
* `src/rvt/ifc/intent.py`, `src/rvt/frontdoor/prompt_intent.py`,
  `src/rvt/validate.py` (+ mirrors) — the three lazy numpy imports (§3
  table; call-site np-free work: [found in tree], verified).
* `plugin/skills/_shared/tekton_env.py` — `_install_schema_cache()`,
  `go()` + `_resolve_go_target()` + cli wiring + docstring.
* `plugin/skills/{tekton-author,tekton-edit,tekton-inspect,tekton-native}/
  scripts/_bootstrap.py` — docstring + `go` re-export; all four
  byte-identical.
* NEW `plugin/assets/schema_cache/{6459a9a9….tksc, index.json}` —
  generated, deterministic, in sync.
* `tests/test_coldstart.py` — [mostly found in tree]; this stream added
  `test_frontdoor_import_is_numpy_free` and
  `test_go_resolves_frontdoor_from_every_skill`.
* `tools/sync_plugin.py` `sync_schema_cache()` — [found in tree, calls
  this stream's `sync_assets()`]; verified green under .venv 3.12 AND
  bare homebrew 3.12.

## BRANCH STATE

* Working tree (repo has no commits yet — same as every stream): all of §8
  present; plugin mirrors byte-equal to src for every file this stream
  touched; `sync_plugin.py --check` shows zero drift for this stream's
  files (remaining drift lines belong to other in-flight fleets:
  `versions/records32.py`, `genesis/port2024.py`, `convert/extract_family.py`).
* `tests/test_coldstart.py`: 11/11 pass (9 [found in tree] + 2 added by
  this stream), re-run green after every tekton_env edit.
* Full suite: see FINAL NUMBERS below (run at stream end as required).
* The bare-env harnesses used for every number in this record:
  scratchpad `profile_cold.py` (single-tree profile) and `ab_profile.py`
  (interleaved A/B) — session-scratchpad only; re-create from this record
  if needed (they are ~150 lines each, described in §1/§5).

## FINAL NUMBERS (appended at stream end)

Second-session merge note: two sessions carried this stream's charter
concurrently; the tree state above is the MERGE (verified: src ==
plugin/lib mirrors byte-equal for every touched file; `tests/
test_coldstart.py` 11/11 green post-merge; schema-cache sync step reports
IN SYNC).  All numbers below were measured by the finishing session on the
merged tree.

**Paired A/B under fleet load** (the load-robust protocol: BEFORE and AFTER
invocations alternate inside one session so both sides see the same
machine; bare envs = fresh TMPDIR + plugin tree only + `env -i` + system
python 3.9.6 + numpy on PYTHONPATH; min over n):

| metric | before | after | n |
|---|---|---|---|
| in-process schema serve (`rvt.schema.parse` call) | 0.138 s | **0.042 s** (served from cache; flag verified per side) | 5 pairs |
| handoff flow: two-call (preflight + run) vs ONE `go` call | 0.554 s | **0.215 s** | 5 pairs |
| preflight alone (alternating order — order-bias controlled) | 0.122 s | 0.127 s (equal within noise; the installers cost ~5 ms) | 6 pairs |
| FULL acceptance `author --prompt` (800 A room): two-call vs `go` | 45.9 min / 48.7 median | 36.5 min / 41.7 median | 3 pairs |

The full-flow delta beyond the ~0.5 s of structural savings (one process +
preflight + parse) is build-compute variance under load — after ≤ before in
all 3 pairs, claimed as "no regression + one model round-trip fewer", NOT
as a build speedup.  Quiet-machine absolutes for the same acceptance run
remain §1's: 16.8–19.3 s warm (system 3.9); the historical "4.3 s warm" was
a repo-venv py3.12 figure — pin the python when quoting it.

**No-numpy acceptance (fresh-VM floor), merged tree, `env -i`, no
site-packages**: `go author --prompt` (800 A room) → ready, builds
end-to-end in 16.1 s job time, writes families + combined `.rvt`; g1 /
census / identity checks all run; the validator's ECC tier reports numpy in
one line; exit 4.  Before the stream: `ModuleNotFoundError: numpy` at
import, nothing built.

**Moderate-load interleaved A/B, full builds included** (load1 ≈ 13-27,
canonical suite running; 2 pairs, min/median; bare envs as above):

| metric | before | after |
|---|---|---|
| handoff two-call (preflight + run) warm | 0.362 s | 0.297 s (numpy import gone) |
| handoff ONE-call `go` warm | — | **0.178 s** (cold 0.193 s) |
| in-proc schema parse vs cache load | 0.111 s | **0.045 s** (hit 2/2) |
| preflight warm | 0.108 s | 0.111 s (installers ≈ +5-10 ms) |
| FULL `author --prompt` 800 A room, cold pyc | 30.15 s | 27.10 s |
| same, warm pyc | 26.20 s | 24.43 s |

Full-build claim stays conservative: after ≤ before in all pairs (schema
cache + import savings ≈ 0.1-0.2 s of it; the rest is merged-tree engine
drift + variance) — "no regression, one round-trip fewer", not "faster
build".

**The field-failure prompt, end to end** ("create an eaton panel for me
with 6 switches" — the exact prompt whose Cowork session opened this whole
effort): bare env, numpy present, ONE `go` call → preflight 0.043 s + job
9.9 s, exit 0, `PROOF-ONLY (self-checks PASS…)`, combined `.rvt` +
families delivered.  The session that failed in the field is now one Bash
call.

**Full suite** — SUPERSEDED-BY-CANONICAL: the snapshot below predates the
orchestrator's instbug-fix builder patches (FamilyInstanceConnectorManager
in famgen/loader + ifc_intent, ContentTable GUID sort, corpus connector
cell, D3 null forms, ProjectPhase fix), after which the orchestrator
verified test_famload_fix + test_frontdoor 44/44, test_router 48/48,
test_surface_perf 4/4 (post plugin-sync), test_famgen_loader 13/13.  The
authoritative count is the fresh canonical run publishing into
`docs/inbox/SUITE-COORDINATION.md` `## RESULT` — adopt that number, not
this snapshot.

Pre-patch snapshot (merged tree, `.venv` py3.12, other fleets still
editing concurrently):

    1664 passed, 7 failed, 2 skipped  (sharded run, 9 shards
    part_0..part_8, all complete; my areas ride in part_0 = 128 passed
    incl. tests/test_coldstart.py 11/11 and test_bootstrap.py)

Failure triage (reproduced + bisected on the settled tree, load ~4):

* FIVE of the seven share ONE root cause, and it is NOT this stream:
  the instbug-fix stream's brand-new validator laws
  (`rvt.validate._check_loaded_content`, 2026-08-05) fire on current build
  content — E3 (`FamilyInstance.m_pConnectorManager` must be null or
  `FamilyInstanceConnectorManager`; the equipment path writes base-class
  `ConnectorManager` on every placed instance) and E2 (`ContentTable`
  ascending ContentKey order; every >= 2-family chained `famgen.loader`
  build violates it).  That turns `test_router` x3 E2E and both
  `test_surface_perf` author/edit jobs into exit-4.  BISECT PROOF: with
  ONLY `validate.py` reverted to its pre-instbug version — every
  perf-coldstart change kept — `test_router::test_e2e_ifc_to_rvt` PASSES
  (25.5 s); with current validate.py it fails.  RESOLVED by the
  orchestrator after this triage: the builders were patched to comply with
  E2/E3 (the right direction — laws kept, builders fixed) and the affected
  suites re-verified green (test_router 48/48, test_surface_perf 4/4).
  Repro artifact: the eaton build's manifest carries the E3 error
  verbatim.
* `test_genesis_assemble::test_ladder_end_to_end` — genesis stream.
* `test_y2025_a::test_probes_manifest` (KeyError 'certified_by') — y2025
  stream.

## Fragments (`docs/inbox/perf-coldstart.d/`, one per PR — `docs/inbox/README.md`)

- `139-partatom-escape.md` — PartAtom XML escape without `xml.sax.saxutils`: 34 stdlib modules (`urllib.request`/`http.client`/`ssl`/`email`) and ~13 ms (repo) / 12–26 ms (bare) off every family-generating job, output byte-identical (#139).
- `747-meta-lazy-xml.md` — `rvt.meta` defers `xml.etree.ElementTree` / `zipfile` to its two parsers (the unused `xml.dom.minidom` import dropped): 14 stdlib modules and ~10 ms of `rvt.meta`'s 12.5 ms off every prompt job, parser output byte-identical; `urllib.parse` turned out to be `pathlib`'s, not ours (#747).
