# ifc-authoring-gate — ONE engine query + ONE conftest marker for "is a REAL ifcopenshell wheel here" (issue #367)

Stream: `ifc-authoring-gate` (eng #367, cloud engineer session started by the tech-lead session,
2026-08-10). Charter = issue #367 (Refs #133 #102 #298; the IFC-side twin of the one schema gate).
Territory: `src/rvt/ifc/_fallback.py` (+ a re-export line in `src/rvt/ifc/__init__.py`),
`tests/conftest.py`, gate/import lines ONLY in the test files listed below, NEW
`tests/test_ifc_authoring_gate.py` + its drop-in `tests/ci_shard.d/367-ifc-authoring-gate.txt`,
the regenerated mirror `plugin/lib/src/rvt/ifc/{__init__,_fallback}.py`, this record.
NOT touched: `src/rvt/ifc/steplite.py`, `intent.py`, hot files, `tests/ci_shard.txt`, any assertion.

## Why

PR #366 (`docs/inbox/ci-shard-router.md`) found that the permissive predicate — "does
`import ifcopenshell` succeed" — has been a guaranteed no-op since the steplite fallback (#130):
importing `rvt.ifc` (which the old `conftest.py` already did transitively at collection start —
measured: `import conftest` → `rvt.ifc` in `sys.modules`, shim dir on `sys.path`) appends the
bundled shim to `sys.path`, so the import always succeeds. Six-plus test modules each answered
"is the real wheel here" their own way: two still permissive (no-ops), four sturdy but
hand-rolled (`not IS_STEPLITE`, `PathFinder` minus the shim dir, …). One question, one answer.

## What was built

**Engine — `src/rvt/ifc/_fallback.py::ifc_authoring_available() -> bool`** (chosen home: the
module that owns `SHIM_DIR` and the backend *selection*; `rvt/ifc/__init__.py` stays the
import-light caller and merely re-exports it, so `from rvt.ifc import ifc_authoring_available`
also works). True iff the `ifcopenshell` this process would import is a REAL distribution whose
package dir ships `api/__init__.py` (the authoring surface — a plain file check, nothing
imported). "Real" = the `importlib.util.find_spec("ifcopenshell")` origin is **not** under any
`_ifcos_shim` copy (keyed on the path segment, so the plugin mirror / an unzipped bundle's shim
never counts either); and — added after the in-session review, because a skill child inherits the
shim on `PYTHONPATH`, i.e. AHEAD of site-packages — when the first hit *is* the shim the query
answers the way the shim's own stand-down law does: the real distribution further along
`sys.path` (a `PathFinder` pass over the shim-free entries) wins unless `RVT_STEPLITE_FORCE`
pins the reader-only shim, in which case it truthfully says False for that process. Measured
end-to-end with `PYTHONPATH=src:src/rvt/ifc/_ifcos_shim` in both venvs × FORCE unset/`1`: the
query equals `not IS_STEPLITE` of the module `import ifcopenshell` then yields in all four rows
(no wheel: False/False; wheel: **True** without FORCE, False with it). No side effects beyond
`find_spec` (a submodule `find_spec("ifcopenshell.api")` would import the parent — avoided); a
raising finder counts as absent (same law as `ifcopenshell_findable`, now sharing one
`_ifcopenshell_spec()` helper); memoised with `functools.lru_cache` (a wheel does not appear
mid-process; backend flips happen in child interpreters). Order-independent: no wheel → `None`
before the shim is on the path, a shim origin after → False both ways; a wheel → True whether the
shim sits behind it (appended) or ahead of it (PYTHONPATH). Documented in the function and the
module docstring. In both real shapes every old predicate and the new query agree — measured
below. Considered and rejected: making the shim's own `_find_real_spec()` call this helper — the
shim is `ifcopenshell/__init__` itself and must stay self-contained at import time (importing
`rvt.ifc._fallback` from inside it would run `rvt.ifc`'s package init mid-import); the two rules
now agree by construction (mine excludes *every* shim copy, a superset of its "not myself").

**Suite — `tests/conftest.py`**: `HAVE_IFC_AUTHORING = ifc_authoring_available()` and
`needs_ifc_authoring = skipif(not HAVE_IFC_AUTHORING, reason="real ifcopenshell wheel absent
(optional `ifc` extra; the bundled steplite shim only reads)")`, right under the schema gate it is
modelled on, with the rule spelled out: gate only what AUTHORS through the wheel or compares
against the real library; IFC *reading* is served by the shim and stays ungated.

**Per test file (gate/import lines only; no assertion edited anywhere):**

| file | old predicate | change | wheel-needing? |
|---|---|---|---|
| `tests/test_router.py` | `_has_ifcopenshell()` = `not IS_STEPLITE` (#366) → `needs_ifc` on 3 cases | predicate deleted; the same 3 cases wear `@needs_ifc_authoring` | yes — spec→ifc authors via `ifcopenshell.api` |
| `tests/test_router_release.py` | `_has_real_ifcopenshell()` = `not IS_STEPLITE` inside `needs_spec_authoring` | term replaced by `HAVE_IFC_AUTHORING` | yes (spec→ifc) |
| `tests/test_ifc_conformance.py` | `HAVE_REAL_IFCOS` = `PathFinder` over `sys.path` minus shim (#324) | replaced by `HAVE_IFC_AUTHORING`; `SHIM_DIR`/`importlib.machinery` gone | yes — real-library parity fixture |
| `tests/test_ifc_intent.py` | module-level `importorskip` + `IS_STEPLITE` skip (#320/#327) | module-level `if not HAVE_IFC_AUTHORING: pytest.skip(...)`, then plain `import ifcopenshell` | yes — synthetic builders author via `ifcopenshell.file`/`.guid` |
| `tests/test_steplite.py` | `HAVE_IFCOS = not IS_STEPLITE` after a `try: import ifcopenshell.util.*` | `HAVE_IFCOS = HAVE_IFC_AUTHORING`; the `_ifcos/_ue/_up/_uu` handles imported only when True | yes — parser equivalence against the real library |
| `tests/test_ifc_census.py` | in-test `try import` + `IS_STEPLITE` skips | `@needs_ifc_authoring` on `test_census_identical_under_real_ifcopenshell` | yes — real-library parity |
| `tests/test_engine.py` | in-function `pytest.importorskip("ifcopenshell")`; module **errored at collection** without the wheel (`bridge_lib` imports `ifcopenshell.validate` at top) | module-level `HAVE_IFC_AUTHORING` skip; the in-function line is a plain import | yes — the tekton-ifc scripts import `.api/.validate/.geom` |
| `tests/test_convert.py` | permissive `_have_ifcopenshell()` → `needs_ifcos` on 2 rvt→ifc cases | **gate removed** (dead): rvt→ifc is our stdlib writer, its round trip READS via the shim | no |
| `tests/test_ifc_family.py` | permissive `HAVE_IOS` term in 4 gates | **term removed** (always True): `product_facts` READS via the shim | no |
| `tests/test_target2025.py` | permissive `_have_ifcopenshell()` on `test_ifc_addition_roundtrips_the_intent` (not in the issue's grep; found by a wider sweep) | **gate removed** (dead): `write_intent_ifc` is our writer, the resolver reads via the shim; measured passing on the shim | no |
| `tests/test_ifc_read_fallback.py` | `skipif(REAL_SITE is None)` on `test_real_install_wins_and_path_is_untouched` (found by the review pass) | that one decorator → `@needs_ifc_authoring`; `REAL_SITE` stays — it is a site-dir *value* the `_HideReal` finder needs, not a gate | yes — needs a real install on `sys.path` |

Intentionally left alone: `tests/test_lazy_ifc_import.py` and the child-interpreter scripts inside
`test_steplite.py` / `test_ifc_read_fallback.py` that assert `IS_STEPLITE` as the *thing under
test*, and `plugin/skills/_shared/tekton_env.py`'s doctor line (it reports which backend the
process *imported*; `IS_STEPLITE` on the live module is the right instrument there).

**New** `tests/test_ifc_authoring_gate.py` (9 cases, fresh-clone safe, in the shard via the
drop-in): nothing findable → False; the shim (repo copy and a mirrored path, parametrised) is
findable yet never counts; a fake real package counts iff it ships `api/__init__.py`
(parametrised); **shim ahead of a fake wheel on `sys.path` → True, and False once
`RVT_STEPLITE_FORCE=1`** (the stand-down mirror); a raising finder → False; exactly one
`find_spec` then memo, and asking never imports `ifcopenshell`; the live answer equals
`not IS_STEPLITE` of what `import ifcopenshell` yields in this process (and `import
ifcopenshell.api` works whenever it says True).

## Evidence — the two shapes, per file (`RVT_SKIP_LARGE=1 LANG=C.UTF-8`, `-q -rs -p no:cacheprovider`, this cloud clone: no `samples/`/`extracted/`/`vendor/`, Python 3.11)

Shape A = fresh `uv venv .venv` + `-e ".[test]"` (no wheel). Shape B = `uv venv .venv-ifc` +
`-e ".[test,ifc]"` (ifcopenshell **0.8.5**). "before" = `main`@e54f13f, "after" = this branch.

| file | A before | A after | B before | B after |
|---|---|---|---|---|
| `test_router.py` | 99 p / 14 s | 99 p / 14 s | 101 p / 12 s | 101 p / 12 s |
| `test_router_release.py` | 12 p / 2 s | 12 p / 2 s | 14 p | 14 p |
| `test_convert.py` | 2 p / 8 s | 2 p / 8 s | 2 p / 8 s | 2 p / 8 s |
| `test_ifc_family.py` | 16 p / 3 s | 16 p / 3 s | 16 p / 3 s | 16 p / 3 s |
| `test_ifc_conformance.py` | 22 p / 10 s | 22 p / 10 s | 31 p / 1 xf | 31 p / 1 xf |
| `test_ifc_intent.py` | 1 s (module) | 1 s (module) | 28 p | 28 p |
| `test_steplite.py` | 11 p / 11 s | 11 p / 11 s | 22 p | 22 p |
| `test_ifc_census.py` | 9 p / 1 s | 9 p / 1 s | 10 p | 10 p |
| `test_engine.py` | **1 error (collection: `No module named 'ifcopenshell.validate'`)** | **1 s (module)** | 6 p / 6 s | 6 p / 6 s |
| `test_target2025.py` | 7 p / 8 s | 7 p / 8 s | 7 p / 8 s | 7 p / 8 s |
| `test_ifc_read_fallback.py` | 7 p / 1 s | 7 p / 1 s | 8 p | 8 p |
| `test_ifc_authoring_gate.py` (new) | — | 9 p | — | 9 p |

("after" columns are the final head, re-measured after the review-pass edits.) Skip lists diffed
before↔after per file and shape with line numbers normalised: identical sets of cases; only skip
*reasons* changed wording (router ×2, census ×1, read_fallback ×1 now say the conftest reason;
ifc_family's two `needs_emit` skips no longer mention ifcopenshell). 0 failed everywhere.

**Newly-genuine skips (formerly not a clean skip) — the complete list:**
* `tests/test_engine.py` (whole module, shape A): was a *collection error* on every wheel-less
  clone; now one module-level skip with the conftest reason. With the wheel the same 6 pass / 6
  skip (samples-gated) as before. No case that used to run stopped running in either shape.

That is the only row that moved. No formerly no-op gate was turned strict over a case that runs
on the shim: the three permissive sites (`test_convert`, `test_ifc_family`, `test_target2025`)
guarded read-direction cases, so the dead gate was *removed* (the #366 precedent), not tightened.
Extra proof for `test_convert` (its two de-gated cases are asset-gated in a fresh clone): the
acceptance room was rebuilt from its prompt with `tools/frontdoor.py author --prompt …` into the
scratch dir, copied onto the git-ignored `experiments/frontdoor/prompt-electrical-room/` paths, and
`tests/test_convert.py` then ran **6 passed / 4 skipped in both shapes** —
`test_rvt_to_ifc_roundtrip_survives_on_own_output` PASSED on the shim (round trip `ran: True`,
`all_survived: True`, equipment 7/7, `ifcopenshell.IS_STEPLITE` True); the copies were deleted
afterwards (`git status` clean of them).

Other gates: `tests/test_schema_gate.py tests/test_shard_list.py` → 27 passed (23 shard-list after
the drop-in: `shard_list.py --print` line 58 = `tests/test_ifc_authoring_gate.py`);
`tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_ifc_read_fallback.py
tests/test_lazy_ifc_import.py` → 26 passed / 1 skipped; order/interaction runs
(`read_fallback + authoring_gate + steplite + router`, shape A → 124 p / 27 s;
`steplite + authoring_gate + read_fallback + ifc_intent`, shape B → 66 p) green.
`tools/sync_plugin.py` → synced 2 files, deny-audit clean, validation passed, zip rebuilt;
`--check` → in sync; `plugin/scripts/validate_plugin.py` → PASS (25 assertions);
`tools/dev/check_portable_paths.py` → ok (2855 paths). Whole merged CI shard: see BRANCH STATE.

`/verify` (the issue's recipe): bare unzip of the rebuilt `tekton-plugin.zip`, `env -i` system
`/usr/bin/python3` 3.11: `python3 -c "import sys; sys.path.insert(0,'lib/src'); from
rvt.ifc._fallback import ifc_authoring_available as f; print(f())"` → **False**; same from the
no-wheel `.venv` → **False**; from `.venv-ifc` (0.8.5) → **True** (and `F.__file__` is the unzipped
copy, i.e. the mirror carries the query). Product smoke from the same bare unzip:
`python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 2
panels" --out … --json` → `go.ready: True`, `result.ok: True`.

In-session review pass (`/simplify`, four angles) — applied: the stand-down-aware branch above
(altitude); `SHIM_DIR` derived from the one `_SHIM_MARK` literal; the gate test parametrised, its
tautological marker case dropped, redundant `import ifcopenshell` lines removed where a submodule
import already binds the name; per-file gate comments cut to one line; the `REAL_SITE` decorator
migrated. Declined: dropping the memo (the issue's DONE asks for it; efficiency measured the whole
query at ~0.1 ms first call, conftest import unchanged at ~5 ms, no `ifcopenshell`/`numpy` pulled
in); promoting `test_ifc_read_fallback`'s `no_real_ifcopenshell` fixture into conftest (a second
file's fixture, no need — the query's input is `find_spec`, which the new tests stub directly).

## Findings / follow-ups

* `tests/test_engine.py` had been a collection *error* (not a skip) on every wheel-less clone since
  `bridge_lib` grew its top-level `ifcopenshell.validate` import; it is not in the shard so nothing
  was red, but `pytest tests/` on a fresh clone showed 1 error. Now a clean skip. If the tekton-ifc
  skill is ever meant to run wheel-less that is #133's territory, not a test-gate question.
* No case newly ran and failed, so nothing to file under the rule-4 lineage clause.
* Under a *globally* exported `RVT_STEPLITE_FORCE=1` the query says False (the process imports the
  reader-only shim), so the two real-library parity legs (`test_ifc_conformance` real fixture,
  `test_ifc_census` parity case) would skip where the old `PathFinder`-minus-shim form ran them in
  a FORCE-stripped child. Nobody runs the suite that way (the tools set FORCE per child and pop it
  from the parent); documented in the docstring, not special-cased.

## BRANCH STATE

* Branch `cam/367-ifc-authoring-gate` from `main`@e54f13f. Files: `src/rvt/ifc/_fallback.py`,
  `src/rvt/ifc/__init__.py`, `plugin/lib/src/rvt/ifc/{_fallback,__init__}.py` (regenerated),
  `tests/conftest.py`, gate lines in `tests/test_{router,router_release,convert,ifc_family,
  ifc_conformance,ifc_intent,steplite,ifc_census,engine,target2025,ifc_read_fallback}.py`, new
  `tests/test_ifc_authoring_gate.py` + `tests/ci_shard.d/367-ifc-authoring-gate.txt`, this record.
  PR #379.
* Gates: tables above. Whole merged CI shard (`shard_list.py --print`, 58 files,
  `RVT_SKIP_LARGE=1 LANG=C.UTF-8 -q -p no:cacheprovider`) on the final code: **shape A (no wheel)
  1235 passed / 138 skipped / 3 xfailed / 0 failed in 169.4 s** vs `main`@e54f13f measured the same
  way in a worktree **1226 / 138 / 3 xf** (Δ = +9 passed = the new gate file; `test_engine.py` is
  not in the shard); **shape B (ifcopenshell 0.8.5) 1261 passed / 111 skipped / 4 xfailed / 0
  failed in 179.1 s**. Full suite NOT run (suite coordination). Nothing staged for the viewer; no
  `.rvt`/`.rfa` shipped (the scratch acceptance build and `out/verify/` were evidence only); no
  certification claim.
