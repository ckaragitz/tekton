# perf-deps — kill the heavy dependencies (stream record)

**Stream:** perf-deps.  **Date:** 2026-08-04.
**Charter:** dependency audit of everything the plugin's runtime paths can
reach; a stdlib-only IFC4 STEP subset parser; retarget the IFC read paths
onto it by import fallback (no edits to the consumer modules); prove
intent-equality on both reference IFCs; before/after numbers from a
simulated bare VM.

## What landed

1. **`src/rvt/ifc/steplite.py`** — stdlib-only IFC4 STEP reader for the
   read-path subset (tokenizer + lazy entity graph; IFC4 inheritance slice
   for `is_a`/`by_type` with ifcopenshell's declaration-tree DFS ordering;
   psets with ifcopenshell's exact merge semantics incl. the trailing
   `"id"` key and type-pset inheritance; typed values; unit scale;
   pure-python `get_local_placement`; `get_inverse`; header access).
   Imports nothing beyond the stdlib.
2. **`src/rvt/ifc/_ifcos_shim/ifcopenshell/`** — a real package named
   `ifcopenshell` (with `util.element` / `util.unit` / `util.placement`
   submodules) backed by steplite.  Selection is ordinary import
   resolution, not monkeypatching: `tekton_env.ensure_engine` APPENDS the
   shim dir to `sys.path` (and the child `PYTHONPATH`) only when
   `importlib.util.find_spec("ifcopenshell")` is None.  The shim also
   STANDS DOWN by itself: if a real distribution is importable anywhere
   else on `sys.path` it loads that instead (so a later
   `doctor --install` or a preinstalled library always wins, even for
   children that inherited the shim on PYTHONPATH).
   `RVT_STEPLITE_FORCE=1` forces the pure-python backend (tests use it).
   `ifcopenshell.api/.geom/.validate` are deliberately NOT served — IFC
   *authoring* (tekton-ifc skill) still requires the real library and says
   so with the same ModuleNotFoundError as an absent install.
3. **`plugin/skills/_shared/tekton_env.py`** (fair game per charter):
   `_append_env_path` helper; the fallback block in `ensure_engine`
   (find_spec-guarded append); doctor now reports "steplite fallback
   active" distinctly, keeps the real library installable via
   `doctor --install`, and no longer tells users to pip-install anything
   for IFC *reads*.  `preflight`'s `extras` key set is unchanged
   (`{numpy, ifcopenshell}`) so tests/test_bootstrap.py's contract holds.
4. **`tests/test_steplite.py`** — 11 tests: attribute-for-attribute
   equality vs ifcopenshell 0.8.5 on BOTH reference IFCs (2 135 + 545
   comparisons), by_type ordering, psets/unit/placement/inverse/get_type
   equality, full-pipeline BYTE-equality across backends (subprocess
   pair), stdlib-only run under `python -S`, parser primitives + STEP
   string escapes, shim stand-down, and the ensure_engine fallback from
   the synced plugin tree.  ifcopenshell-dependent tests skip cleanly
   where it is absent.
5. **`docs/writer/dependency-audit.md`** — the honest import graph of every
   runtime path with measured wheel sizes, install times, and per-route
   before/after numbers (summarised below).
6. Plugin re-synced (`tools/sync_plugin.py`), zip rebuilt; steplite + shim
   ship inside `lib/src/rvt/ifc/`.

## Equivalence (the DONE bar)

* Both reference IFCs (`electrical-room-2500a.ifc`,
  `chicago-plenum-downlight.ifc`) run through BOTH parsers:
  `resolve_intent → intent_to_json` and `product_facts →
  to_facts_record + full dump` are **byte-equal** (`cmp` clean on the
  285 KB intent JSON; facts record + full dump identical; validator clean
  on both).  No deltas to explain.
* Every entity / attribute / pset / placement / ordering equal (zero
  mismatches across 2 680 attribute comparisons).

## Numbers (simulated bare VM: fresh TMPDIR, unzipped tekton-plugin.zip only, system python, `env -i`)

* Install cost killed: `pip install ifcopenshell` = **40.4 MB wheel
  (+7.1 MB deps: numpy, shapely, lark, isodate, dateutil, six,
  typing_extensions), 233 MB installed, 11.0 s on a fast office link**
  (minutes on a slow VM; impossible on a network-less sandbox) → **zero**
  for all IFC reads.
* product-facts route: **0.68 s total first process, zero installs**
  (was: install + 0.9 s).
* intent route, first process on the box: **1.50 s** (steplite,
  numpy-only box) vs **4.98 s** (ifcopenshell installed — its first
  import compiles the 190 MB package); pyc-warm processes: 0.77 s vs
  0.78 s (steplite parses the 687 KB room file ~0.16 s slower, offset by
  the 0.30 s import it avoids).  `import ifcopenshell` = 0.297 s pyc-warm
  vs shim 0.022 s.
* intent route still needs numpy (5.1 MB wheel / 34 MB / 6.9 s cold
  install; commonly preinstalled on AI sandboxes).  The facts/family
  route needs NOTHING.
* author `--prompt` end-to-end from the bare plugin with the fallback
  active: works, `errors: []`, 6.5–8 s (dominated by the build itself;
  run on a machine shared with other fleets — user time 6.2–6.5 s).

## Patches delivered (NOT applied — outside this stream's territory)

**P1 — make `rvt.ifc.intent`'s ifcopenshell import lazy** (finding F2:
when ifcopenshell IS installed, the guarded top-level `try: import
ifcopenshell` succeeds and every author/edit/convert process eagerly pays
its import — 0.30 s pyc-warm, ~4.5 s first-ever — even for prompt-only
jobs).  Suggested minimal edit, mirroring the `_lazyimp` pattern the
perf-coldstart stream already used for numpy; grep confirms
`_HAVE_IFCOS` has no consumers outside intent.py:

```diff
--- a/src/rvt/ifc/intent.py
+++ b/src/rvt/ifc/intent.py
@@
-try:  # ifcopenshell is required to READ an IFC; keep the module importable
-    import ifcopenshell  # type: ignore
-    import ifcopenshell.util.element as _ue  # type: ignore
-    _HAVE_IFCOS = True
-except Exception:  # pragma: no cover - the sandbox always has it
-    ifcopenshell = None  # type: ignore
-    _ue = None           # type: ignore
-    _HAVE_IFCOS = False
+# LAZY (perf-deps): the ifcopenshell import (real library OR the bundled
+# steplite shim) loads on first IFC read, so importing this module -- which
+# the whole front door does -- never pays the 190 MB package's import cost
+# on prompt-only jobs.  resolve_intent() gates on _load_ifcos().
+ifcopenshell = None  # type: ignore
+_ue = None           # type: ignore
+_HAVE_IFCOS: Optional[bool] = None
+
+
+def _load_ifcos() -> bool:
+    global ifcopenshell, _ue, _HAVE_IFCOS
+    if _HAVE_IFCOS is None:
+        try:
+            import ifcopenshell as _i  # type: ignore
+            import ifcopenshell.util.element as _e  # type: ignore
+            ifcopenshell, _ue, _HAVE_IFCOS = _i, _e, True
+        except Exception:
+            _HAVE_IFCOS = False
+    return bool(_HAVE_IFCOS)
@@ def resolve_intent(ifc_path: str, *, plan_families_flag: bool = True) -> IntentModel:
-    if not _HAVE_IFCOS:
+    if not _load_ifcos():
         raise IntentError("ifcopenshell is required to read IFC")
```

**P2 (note, no diff)** — `tools/ifc_to_spec.py` (legacy front door, also
synced into two skills) imports `ifcopenshell.geom` + numpy eagerly; it is
superseded by `rvt.ifc.intent` and is NOT covered by the steplite shim
(geometry kernel).  Recommend retiring it from the skill scripts or gating
its import behind its CLI entry.

## Coordination notes for the orchestrator

* `plugin/skills/_shared/tekton_env.py` was concurrently extended by the
  perf-coldstart stream (`go` dispatch, schema cache, `_lazyimp`); my two
  edits (fallback block in `ensure_engine`, doctor extras wording +
  `_append_env_path`) merged cleanly on top and the bare-VM author run
  passes with both streams' changes live.
* `inputs/ifc/electrical-room-2500a.intent.json` (written today by another
  stream) was NOT touched; my equivalence artifacts live in the session
  scratchpad only.
* New-work proposal: apply P1 (one-line-ish latency win for every
  installed-ifcopenshell environment); consider P2.

## BRANCH STATE

* Repo: `/Users/ck/dev/things/tekton`, branch `main` (unborn — no commits
  yet in this shared tree); nothing committed by this stream, per the
  shared-tree convention the other streams are following.
* Files ADDED by this stream:
  `src/rvt/ifc/steplite.py`,
  `src/rvt/ifc/_ifcos_shim/ifcopenshell/__init__.py`,
  `src/rvt/ifc/_ifcos_shim/ifcopenshell/util/{__init__,element,unit,placement}.py`,
  `tests/test_steplite.py`,
  `docs/writer/dependency-audit.md`,
  `docs/inbox/perf-deps.md` (this file).
* Files EDITED by this stream:
  `plugin/skills/_shared/tekton_env.py` (fallback block in
  `ensure_engine`, `_append_env_path`, doctor extras wording — fair game
  per charter).
* Plugin tree: re-synced via `tools/sync_plugin.py` (steplite + shim now
  bundled under `plugin/lib/src/rvt/ifc/`); `tekton-plugin.zip` rebuilt;
  `--check` clean at hand-off.
* Off-limits files: untouched (`tools/frontdoor.py`, `plugin/skills/*/
  SKILL.md`, `src/rvt/frontdoor/base.py`, `src/rvt/versions/`,
  `src/rvt/ifc/intent.py`, `src/rvt/ifc/product_facts.py` — the last two
  retargeted purely by import fallback; the optional latency patch P1 is
  delivered above, not applied).
* Test suite (run 2026-08-04→05 on the shared moving tree, `RVT_SKIP_LARGE=1`
  — the un-gated run exceeds the session harness's 10-minute command ceiling;
  it was observed to ~17% twice before the ceiling killed it — chunked into
  7 file-groups): **1627 passed, 42 skipped, 4 failed** of 1673.
  `tests/test_steplite.py`: 11/11 green.  The 4 failures are NOT this
  stream's (proof below):
  - `test_router.py::test_e2e_prompt_rvt_edit`,
    `test_surface_perf.py::test_bare_author_prompt_under_20s`,
    `test_surface_perf.py::test_bare_edit_roundtrip_works_and_bounded` —
    both files landed from other streams DURING this stream's run; the
    underlying condition is the frontdoor author exiting 4 with
    `"ok": false, "status": "SELF-CHECKS FAILED (combined)"` on a bare
    /usr/bin/python3 (3.9).  Reproduced from a fresh plugin copy **with the
    steplite shim deleted** — identical exit 4 / self-check failure, so it
    is independent of perf-deps (the author's own bundled-surface
    self-checks vs the new bench's expectations; frontdoor/perf-coldstart
    seam).
  - `test_y2025_a.py::test_probes_manifest` — `KeyError: 'certified_by'`,
    genesis-stream manifest churn; no perf-deps surface involved.
  - `test_plugin_sync` failed once mid-session purely because the convert
    stream landed new files after this stream's sync; green after
    re-running `tools/sync_plugin.py` (drift is inherent to the shared
    moving tree — the last sync of this session left `--check` clean).

## eng #160 — 2026-08-10: one-pass inverse indexes for large IFCs (issue #160)

**Charter (issue #160, Refs #108/#110/#113, PG6 + S-2026-08-09-g):** steplite's
inverse attributes (`IsDefinedBy` / `IsTypedBy` / `ContainedInStructure`, and
`get_psets` / `get_type` on top of them) scanned every relationship of the class
per (class, attr, id) key — O(products x rels), so `resolve_intent` on a
2000-product export went 9x slower for 4x the input.  DONE = one-pass indexes,
identical answers and ordering, a probe with before/after from one machine, a
non-slow guard test.

### What landed

1. **`src/rvt/ifc/steplite.py` — `File._inverse_rel`** now serves every inverse
   attribute from a per-(rel class, related attr) index `{related id: (rels…)}`
   built by ONE pass over that class on first use (the old `_inverse_cache`
   keyed per id is gone; `_inverse_index` replaces it).  Same contract as the
   scan it replaces, now written down in its docstring: rels of the EXACT class
   in FILE order, each rel once even when it lists the id twice, `()` for an id
   no rel names; a dangling `#ref` in any rel of the class still raises
   `StepLiteError` on first access.  Nothing any accessor RETURNS changed —
   `get_inverse` (already a whole-file one-pass index since day one; the
   `IfcStyledItem` lookups in `rvt.ifc.intent` go through it), `by_type`,
   attribute access, `get_psets` / `get_type` are untouched.  `IfcRelAggregates`
   is consumed by `rvt.ifc.intent` through ONE `by_type` scan, never per
   product, so it needed no index (the generic index would serve a future
   `Decomposes` accessor for free).  +17 / −12 lines.
2. **`tools/dev/ifc_perf_probe.py`** (new, stdlib + engine): writes
   `perf_<n>.ifc` with OUR emitter (`rvt.frontdoor.ifc_out.write_intent_ifc` fed
   a synthetic duck-typed intent model: a 4-wall room shell + n products cycling
   panelboard / transformer / receptacle / switchboard, each with its
   tagging-contract pset, boards chained by `FedFrom`) into a scratch dir, then
   measures each (backend, n) in a FRESH child: `open_s`, `read_slice_s` (the
   read layer alone: `get_psets` + `get_type` + `ContainedInStructure` for every
   product), `resolve_s` (`resolve_intent`, its own open included), `maxrss_mb`
   (the child's OWN VmHWM — `ru_maxrss` after exec is seeded with the parent's
   high-water mark on Linux, which charged the generator's memory to every
   child in the first draft: caught and fixed, readings re-taken).  `--src DIR`
   points the children at another checkout's `src/` (a worktree of `main`) so
   before/after come from one machine, one interpreter, one set of files.
3. **`tests/test_steplite.py` §8** (+3 tests, ~4 s together; the file is already in
   `tests/ci_shard.txt`, so no drop-in was needed):
   `test_inverse_attribute_semantics_are_kept_by_the_index` (stdlib-only min
   STEP file hitting every corner: file order with `#12` written before `#11`,
   an id listed twice in one rel, an id no rel names, exact-class filtering,
   type-pset-first `get_psets` layering, `get_inverse` id order);
   `test_read_layer_is_linear_on_a_2000_product_file` — the SHARP guard,
   stdlib-only and in-process: generates perf_2000 (0.2 s), runs the whole read
   layer over its 2 004 products and asserts < 2 s (0.05 s now, 9.4 s with the
   per-id scan on the same VM — the issue's literal "perf_500 resolve < 5 s"
   guard alone would NOT have caught a reintroduction, since the scan only cost
   0.5 s at n=500 here / 2.2 s on the issue's VM); and
   `test_large_ifc_resolves_without_the_quadratic_scan` — the issue's literal
   DONE line: perf_500 through `resolve_intent` on the forced shim in a child,
   500 equipment / 4 walls, `resolve_s < 5 s` (1.1 s).
4. Plugin mirror re-synced (`plugin/lib/src/rvt/ifc/steplite.py`); `--check` clean.

### Equivalence (results AND ordering identical to main)

* `tests/test_steplite.py`: **31 passed** (29 pre-existing incl. the two-backend
  BYTE-equality of `resolve_intent → intent_to_json` + `product_facts` on both
  reference IFCs, + the 2 new), real ifcopenshell 0.8.5 present so no parity
  test skipped.
* main (`cd2d5a2`, a `git worktree`) vs head, both under `RVT_STEPLITE_FORCE=1`,
  one dump script per file recording `intent_to_json(resolve_intent(f))` **plus,
  for EVERY entity id in the file, `get_inverse` ids, `ContainedInStructure` /
  `IsDefinedBy` / `IsTypedBy` rel ids and, for every IfcObjectDefinition,
  `get_psets` (key order kept) and `get_type`**; `json.dumps` of the two dumps
  compared as strings → **IDENTICAL for all 18 files**: `inputs/ifc/electrical-room-2500a.ifc`
  (577 ids), `inputs/ifc/chicago-plenum-downlight.ifc` (147), all 10
  `tests/ifc_conformance/*.ifc` (71–225 ids each, incl. the IFC2X3 one), the 4
  `usecases/*/*.ifc` (92–727), and the generated `perf_500.ifc` (9 430 ids) and
  `perf_2000.ifc` (37 555 ids, a 14.6 MB dump; main needed 14.6 s of resolve +
  ~20 min of per-id scans to produce it, head 6.7 s + seconds).  0 differing
  bytes anywhere; the dump script and both dump trees stayed in the session
  scratchpad (generated / derived, not committed).
* Front door, `RVT_STEPLITE_FORCE=1 tools/frontdoor.py author --ifc <f>
  --target-version 2025 --json`, main-worktree `PYTHONPATH` vs head: see the
  table below — `manifest.json` identical after masking the noise class
  (out-dir paths, `seconds`/timings), `intent.json` byte-identical.

### Numbers — before (main `cd2d5a2`, `--src` = a worktree of it) / after (this branch), ONE machine

Cloud VM (Linux 6.18, 4 vCPU, CPython 3.11.15), the fresh `.venv` from
`scripts/cloud-setup.sh` (engine + `test` extra; the real ifcopenshell 0.8.5
wheel happened to be present, so the comparison rows are from THIS machine, not
borrowed from the issue's).  Same generated files for every row
(`perf_100/500/2000/10000.ifc` = 0.17 / 0.86 / 3.5 / 17.8 MB, 101 / 501 / 2 001 /
10 001 products); every (backend, n) in its own fresh child; seconds.
`slice` = the read layer alone (get_psets + get_type + ContainedInStructure for
every product); `resolve` = `resolve_intent` incl. its own open; RSS = the
child's VmHWM.

| n | backend | open | slice **before → after** | resolve **before → after** | peak RSS MB before → after |
|---:|---|---:|---:|---:|---:|
| 100 | steplite | 0.03–0.05 | 0.021 → **0.003** | 0.31 → 0.38 | 46 → 46 |
| 100 | ifcopenshell | 0.02 | 0.04–0.05 | 0.25–0.29 | 174 |
| 500 | steplite | 0.16–0.17 | 0.48 → **0.015** | 1.26 → **1.06** | 58 → 58 |
| 500 | ifcopenshell | 0.05–0.07 | 0.07–0.09 | 1.16–1.33 | 187 |
| 2000 | steplite | 0.60–0.69 | 9.36 → **0.053** | 12.03 → **4.59** | 102 → 102 |
| 2000 | ifcopenshell | 0.26–0.28 | 0.26–0.28 | 6.19–6.73 | 233 |
| 10000 | steplite | 3.6–4.5 | 315.3 → **0.31** | **420.2 → 68.4** | 365 → 362 |
| 10000 | ifcopenshell | 1.6 | 1.3–1.5 | 68.5–69.4 | 486 |

* **Acceptance line of #160 — steplite/ifcopenshell `resolve` ratio at n=2000:
  before 1.94x (12.03 / 6.19; the issue's own VM had 2.7x), after 0.68x
  (4.59 / 6.73) — target was ≤ 1.5x.**  At n=500 1.06 vs 1.16–1.33; at n=10000
  1.00x (68.4 vs 68.5).  The read layer alone is now 4–5x *faster* than the
  C++ library's Python binding for this slice at every size (0.053 s vs 0.28 s
  at 2000, 0.31 s vs 1.5 s at 10000) and linear (x5 input → x5.8); before, it
  was x19.5 for x4 input (0.48 → 9.36 s) — the quadratic the issue measured.
  (At n=100 everything is inside process noise: `resolve` 0.31 vs 0.38 s moved
  by the same 0.07 s as `open`, whose code is unchanged; the slice itself went
  0.021 → 0.003 s.)
* **perf_10000 < 60 s / < 500 MB:** memory yes (362 MB steplite; ifcopenshell
  itself needs 486 MB); time **no — 68 s, but identically 68 s on real
  ifcopenshell**: what is left is `rvt.ifc.intent`'s own feeder-tree pass
  (`_norm_tag` rebuilds the normalised known-tag map per `FedFrom` cell →
  O(fed x equipment) `re.sub` calls, 5.1 s of a 13.2 s *profiled* resolve at
  n=2000, ~50 s at n=10000), which is FENCED territory this wave (#498) and not
  a reader property.  Filed as **#519** (task-shaped, `Refs #160`, gating note
  for the tech lead); with it perf_10000 lands well under 30 s on both backends.
  Before this change the steplite child needed **420 s** for perf_10000 (315 s
  of it the read layer: ~10⁴ products x 1.25·10⁴ rels x 2 passes; that one
  "before" row shared the VM with the shard run, so read it as ±20 %, the
  order of magnitude is the point) — 6.1x slower than ifcopenshell there, 1.00x now.
* Parse (`open`) is untouched and linear (0.6 s / 3.5 MB, 4.5 s / 17.8 MB —
  ~2.3x the C++ parser); it is now the largest steplite-side cost and the
  obvious next lever if a future export makes it matter (not this issue).
* Front door, `RVT_STEPLITE_FORCE=1 frontdoor.py author --ifc F --target-version 2025 --json`,
  main worktree vs head: `electrical-room-2500a.ifc` 5.2 s vs 5.3 s wall,
  `perf_500.ifc` 107.8 s vs 110.3 s wall (both dominated by the 500-family
  build, not the read; run while another core was busy with the before-probe,
  so ±3 %) — stdout JSON identical but `seconds`; `intent.json` byte-identical
  (213 894 B / 3 786 079 B); `manifest.json` identical after masking the noise
  class = {`content_guid` / `guid` UUIDs, `generated_at`, `md5`, `sha256`,
  `seconds`, the `gates` timing seconds, out-dir + checkout paths}, a class
  established by diffing TWO head runs of the same input first (they differ in
  exactly those keys and nothing else); the built `.rvt` differs in sha only
  through those GUIDs/timestamps, 757 760 B / 5 038 080 B both sides.

### Findings

* F1 — the fix is where the issue said it was; `get_inverse` was never part of
  the problem (already a one-pass whole-file index), and `IfcRelAggregates` has
  no per-product accessor to index.
* F2 — **#519**: `rvt.ifc.intent._norm_tag` is the next quadratic (both backends).
* F3 — measuring child memory with `ru_maxrss` under `subprocess` on Linux is
  wrong whenever the parent is fat: exec() seeds the child's maxrss with the
  parent's high-water mark.  The probe reads `/proc/self/status` VmHWM instead
  (documented in its docstring); worth remembering for `tools/surface_bench.py`-style
  harnesses (#113's territory — noted here, not touched).
* F4 — the synthetic model generator (`ifc_perf_probe.synthetic_model(n)`) is a
  reusable "large IFC of our own bytes" source for any future scale test (it is
  what the new shard test uses at n=500).

### BRANCH STATE (eng #160)

* Branch `cam/160-steplite-inverse-index` from `main` @ `cd2d5a2`; PR closes #160.
* Files: `src/rvt/ifc/steplite.py` (edit: `_inverse_rel` + `File.__init__` slot),
  `plugin/lib/src/rvt/ifc/steplite.py` (generated mirror via `tools/sync_plugin.py`),
  `tools/dev/ifc_perf_probe.py` (new), `tests/test_steplite.py` (+§8, 2 tests,
  `import importlib.util`), `docs/inbox/perf-deps.md` (this section only).
  No hot file, no fenced file, no NO-GO file touched; `tests/ci_shard.txt`
  untouched (test_steplite.py was already in it — no drop-in needed).
* Not committed (scratch only): the generated `perf_*.ifc`, before/after probe
  JSON, the 18+18 parity dumps and the dump script, the front-door out dirs.
* Gates on this head: `tests/test_steplite.py` 32 passed / 0 skipped (8 s);
  `tools/sync_plugin.py` run + `--check` "plugin in sync with source";
  `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `check_portable_paths.py` ok (2933 paths); whole merged shard
  (`shard_list.py --print`, 83 files, `RVT_SKIP_LARGE=1 -p no:cacheprovider`) —
  counts in the PR body for the exact pushed SHA.  `/simplify` (4 angles) applied:
  the perf_500 test now drives the probe's own `measure()` instead of a second
  hand-rolled child, tag prefixes folded into `_KINDS`, backends parsed once,
  int-keyed `files`, duplicated VmHWM rationale and index comments trimmed, and a
  STRUCTURAL assertion (exactly three `(class, attr)` indexes exist after the
  slice) added next to the 2 s bound so a reintroduced per-id scan fails
  deterministically, not only by wall clock; skipped with reason: building the
  synthetic model from `rvt.ifc.intent` dataclasses instead of `SimpleNamespace`
  (`write_intent_ifc` is duck-typed by contract — `getattr(model, …, None)`
  throughout — and the dataclass constructors change far more often than the
  attribute names it reads), and dropping measured numbers from test docstrings
  (this repo's convention is numbers, not adjectives).  `/verify`: front door
  `author --ifc` under the forced shim on the reference room and on perf_500 →
  `PROOF-ONLY (self-checks PASS)`, `ok: true`, `errors: []`, both `.rvt`
  validate 0 errors / 0 warnings; `--ifc` on a non-STEP file → exit 3, `FAILED
  (IFC intent failed: StepLiteError: … not an ISO-10303-21 (STEP) file)`, no
  traceback; **bare unzip of the rebuilt `tekton-plugin.zip`, `go author --ifc
  examples/electrical-room-2500a.ifc --target-version 2025 --json` with the shim
  serving (`IS_STEPLITE=True`, bundled `lib/src/rvt/ifc/steplite.py` carrying
  `_inverse_index`) → rc 0, `PROOF-ONLY (self-checks PASS)`, 5.8 s wall, combined
  `.rvt` validates 0 errors** (system `python3` here lacks numpy, which the IFC
  intent route documents as required — it answered with the one-line install
  hint, rule 1 intact for the prompt route; the run above used the venv
  interpreter with `RVT_STEPLITE_FORCE=1` so the SHIPPED reader, not the wheel,
  was exercised).
* Cosmetic follow-up noted, not filed (no user-visible value on its own): the
  three `if attr == …` inverse branches in `Entity.__getattr__` could become a
  3-row `{attr: (rel class, related attr)}` table now that the index behind them
  is generic.
* Follow-ups filed: #519.  Nothing staged for the viewer (no `.rvt` claim).
