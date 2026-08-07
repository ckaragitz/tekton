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
