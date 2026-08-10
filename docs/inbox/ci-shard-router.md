# ci-shard-router — `tests/test_router.py` runs in the per-PR CI shard (issue #102)

Stream: `ci-shard-router` (eng #102, cloud engineer session started by the tech-lead session,
2026-08-09). Charter = issue #102 (Refs #5; regression #354 reached `main` because this file was
unsharded). Territory: `tests/test_router.py` (gate lines only), NEW
`tests/ci_shard.d/102-test-router.txt`, this record. NOT touched: `src/`, `tools/`,
`tests/ci_shard.txt` (frozen, #328 — comment-only patch below), `tests/conftest.py`, hot files.

## Why

`tests/test_router.py` carries two gates that must run on every PR — the permutation-matrix
evidence self-audit and the `docs/product/PERMUTATION-MATRIX.md` ↔ machine-matrix drift guard —
but it was kept out of the shard because "the spec->ifc cases need ifcopenshell". Measured on
this fresh clone (no `samples/`, no wheel, `RVT_SKIP_LARGE=1`) before any change:
**2 failed / 95 passed / 12 skipped, 17.9 s** — `test_e2e_spec_to_ifc` and
`test_route_manifest_shape` crash with `ModuleNotFoundError: No module named 'ifcopenshell.api'`
(spec→ifc AUTHORS through `ifcopenshell.api`; the bundled steplite shim only reads).

## Finding that shaped the fix: the file's `needs_ifc` gate was a guaranteed no-op

`needs_ifc` was `skipif(not _has_ifcopenshell())` with `_has_ifcopenshell()` = "does
`import ifcopenshell` succeed". Since the steplite fallback (#130), `import rvt.ifc` appends
`src/rvt/ifc/_ifcos_shim` to `sys.path` in every process — and importing
`rvt.frontdoor.router` (module top of this test file) already imports `rvt.ifc`. Probe on the
no-wheel venv: `find_spec("ifcopenshell")` is `None` before and **truthy after**
`from rvt.frontdoor import matrix, router`; `test_router._has_ifcopenshell()` → `True`.
So on a fresh clone the eight `@needs_ifc` decorations never skipped anything (baseline `-rs`
shows zero "ifcopenshell absent" skips): the prompt→ifc, ifc→ifc, rvt→ifc and ifc-merge cases
have been running — and passing — on the shim all along, while the two spec→ifc cases were
simply undecorated. Decorating them with the old predicate would have changed nothing.

## What changed (gates only — no assertion touched)

* `_has_ifcopenshell()` now answers "is a REAL wheel importable": `import ifcopenshell`, then
  `not IS_STEPLITE and "_ifcos_shim" not in __file__` — the same test
  `tests/test_router_release.py::_has_real_ifcopenshell` and `tests/test_steplite.py`
  (`HAVE_IFCOS`) already use; no new shared predicate, `conftest.py` untouched. It is
  order-independent: identical result whether the file is collected alone or after a module
  that already put the shim on `sys.path` (measured both ways, below). Skip reason now says
  `ifcopenshell wheel absent (steplite shim only reads)`.
* `@needs_ifc` sits on **exactly** the three cases that proved to need `ifcopenshell.api`
  (no wheel, large builds ON, old permissive predicate → these three FAIL, everything else
  passes or skips on absent owner-machine assets): `test_e2e_spec_to_ifc`,
  `test_route_manifest_shape`, and `test_e2e_spec_to_rfa_chain` (already decorated; its first
  stage is `spec->ifc`; `@skip_large` hides it in CI anyway).
* The dead decorator is **removed** from the seven cases that do not author IFC through the
  wheel — `test_e2e_prompt_to_ifc_round_trips`, `test_e2e_ifc_normalize`,
  `test_e2e_rvt_to_ifc_round_trips_a_built_room`, `test_e2e_merge_ifc_into_project` (all four
  measured green on the shim, no wheel, large builds on) and `test_e2e_famspec_downlight_loaded`,
  `test_e2e_prompt_via_ifc_to_rvt_chain`, `test_e2e_ifc_to_rvt` (owner-machine-gated here; IFC
  *read* direction, served by steplite by design). Because the old gate never fired, removing it
  is behaviour-preserving everywhere; keeping it under the now-strict predicate would have newly
  hidden tests that pass today (the strict-everywhere variant measured 93 passed / 16 skipped —
  rejected for that reason).
* NEW `tests/ci_shard.d/102-test-router.txt` lists `tests/test_router.py`
  (`tests/ci_shard.txt` itself not edited).

## Evidence (this clone: no `samples/`/`extracted/`, Python 3.11.13, `uv venv` + `-e ".[test]"`; second venv adds `.[ifc]` = ifcopenshell 0.8.5)

`tests/test_router.py` alone, `-q -p no:cacheprovider`:

| shape | passed | skipped | failed | wall |
|---|---|---|---|---|
| baseline `main`@ec62a06, no wheel, `RVT_SKIP_LARGE=1` | 95 | 12 | **2** | 17.9 s |
| **after, no wheel, `RVT_SKIP_LARGE=1` (CI shape)** | **95** | **14** | **0** | 18.8 s |
| after, no wheel, `RVT_SKIP_LARGE=1`, collected after `tests/test_steplite.py` (shim already on `sys.path`) | same two `needs_ifc` skips only (106 p / 25 s for the pair) | | 0 | 17.4 s |
| **after, WITH ifcopenshell 0.8.5, `RVT_SKIP_LARGE=1`** | **97** | **12** | **0** | 19.2 s |
| after, no wheel, large builds ON | 101 | 8 | 0 | 27.5 s |
| after, WITH wheel, large builds ON | 104 | 5 | 0 | 31.6 s |

No-wheel skips in the CI shape are exactly `:626 test_e2e_spec_to_ifc` and
`:950 test_route_manifest_shape` (+ the pre-existing `RVT_SKIP_LARGE`, absent-asset and
running-as-root `chmod 0555` skips; under session CI's `uid=nobody` the chmod case runs).
With the wheel the same 95 pass plus the two gated cases run: 97.

Shard: `python3 tools/dev/shard_list.py --print | grep -n test_router` →
`30:tests/test_router_release.py`, `52:tests/test_router.py` (once).
`tests/test_shard_list.py` → 23 passed. `tools/dev/check_portable_paths.py` → ok (2839 paths).
Whole merged shard, CI shape (`env RVT_SKIP_LARGE=1 LANG=C.UTF-8`, no wheel):
before the drop-in **1093 passed / 124 skipped / 3 xfailed in 197.1 s**; with it **1188 passed / 138 skipped /
3 xfailed / 0 failed in 204.3 s** — exactly +95 passed / +14 skipped (the file) and **+7 s wall** (less than the
file's ~19 s alone: imports and the schema cache are already warm mid-shard), well inside the 1500 s
sandbox timeout.

## Patch carried for the frozen file (not applied here — `tests/ci_shard.txt` is outside this territory)

Its header still says the file is "Deliberately NOT in the shard"; whoever next holds
`tests/ci_shard.txt` can drop these four comment lines (entries unchanged, so
`test_shard_list.py`'s no-growth pin is unaffected):

```
-# Deliberately NOT in the shard:
-#   tests/test_router.py  — test_e2e_prompt_to_rfa needs the git-ignored
-#                           extracted/racbasicsampleproject corpus (owner
-#                           machine), and the spec->ifc cases need
-#                           ifcopenshell, which is an optional dep.
```

## Open questions / follow-ups

* #133 (spec→ifc authoring needs the wheel) is the product gap behind the two skips; when it
  lands a stdlib authoring path, the three `@needs_ifc` decorations here become removable and
  the CI shape gains those cases.
* Other files still carry the permissive "does `import ifcopenshell` succeed" predicate
  (`tests/test_convert.py::needs_ifcos`, `tests/test_ifc_family.py::needs_ifc`); whether they are
  equally dead depends on their import order — worth one census pass when #133 or a
  shared-marker cleanup touches them (not filed separately: no failing case observed).

## BRANCH STATE

* Branch `cam/102-shard-test-router` from `main`@ec62a06; files: `tests/test_router.py`
  (predicate + decorator lines only), `tests/ci_shard.d/102-test-router.txt` (new),
  `docs/inbox/ci-shard-router.md` (this record, new).
* Gates: table above; `tests/test_shard_list.py` 23 passed; portable paths ok;
  `tools/sync_plugin.py --check` → in sync, deny-audit clean (no `src/`/`tools/`/`skills/` touched).
  `/verify` skipped — tests-only diff, no runtime surface. Full suite NOT run (suite coordination).
* Nothing staged for the viewer; no `.rvt`/`.rfa` produced; no certification claim.
