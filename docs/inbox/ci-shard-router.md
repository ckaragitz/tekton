# ci-shard-router — `tests/test_router.py` runs in the per-PR CI shard (issue #102)

Stream: `ci-shard-router` (eng #102, cloud engineer session started by the tech-lead session,
2026-08-09). Charter = issue #102 (Refs #5; regression #354 reached `main` because this file was
unsharded). Territory: `tests/test_router.py` (gate lines only), NEW
`tests/ci_shard.d/102-test-router.txt`, a comment-only correction to `tests/ci_shard.txt`'s
header (tech-lead ruling: the #328 freeze is about appending *entries*; no entry added, removed
or reordered), this record. NOT touched: `src/`, `tools/`, `tests/conftest.py`, hot files.

**Headline finding — why nothing caught #354-class regressions:** this file's `needs_ifc` gate
has been a guaranteed no-op since the steplite fallback (#130). Importing the router loads
`rvt.ifc`, which puts the bundled shim on `sys.path`, so "does `import ifcopenshell` succeed"
was always True: the decorator never skipped anything, the two spec→ifc cases that really need
the wheel were red on every fresh clone, and *that* standing red is what kept the whole file —
matrix honesty gate and doc-drift guard included — out of the per-PR shard. Details in §Finding.

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
  `not IS_STEPLITE` (the engine-owned discriminator, `src/rvt/ifc/steplite.py`) — the same
  test `tests/test_router_release.py::_has_real_ifcopenshell` and `tests/test_steplite.py`
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

| shape (rebased head on `main`@c1b52ed, 113 collected — #363 added 4 wheel-free cases) | passed | skipped | failed | wall |
|---|---|---|---|---|
| baseline `main`@ec62a06 (109 collected), no wheel, `RVT_SKIP_LARGE=1` | 95 | 12 | **2** | 17.9 s |
| **after, no wheel, `RVT_SKIP_LARGE=1` (CI shape)** | **99** | **14** | **0** | 19.5 s |
| after, no wheel, `RVT_SKIP_LARGE=1`, collected after `tests/test_steplite.py` (shim already on `sys.path`) | same two `needs_ifc` skips only (110 p / 25 s for the pair) | | 0 | 18.8 s |
| **after, WITH ifcopenshell 0.8.5, `RVT_SKIP_LARGE=1`** | **101** | **12** | **0** | 19.3 s |
| after, no wheel, large builds ON | 105 | 8 | 0 | 31.8 s |
| after, WITH wheel, large builds ON | 108 | 5 | 0 | 36.6 s |

(Pre-rebase on ec62a06 the same rows read 95/14/0, 97/12/0, 101/8/0, 104/5/0 — the +4 is #363's
cases in every shape; they need no wheel.)

No-wheel skips in the CI shape are exactly `:622 test_e2e_spec_to_ifc` and
`:946 test_route_manifest_shape` (+ the pre-existing `RVT_SKIP_LARGE`, absent-asset and
running-as-root `chmod 0555` skips; under session CI's `uid=nobody` the chmod case runs).
With the wheel the same 99 pass plus the two gated cases run: 101.

Shard: `python3 tools/dev/shard_list.py --print | grep -n test_router` →
`30:tests/test_router_release.py`, `52:tests/test_router.py` (once).
`tests/test_shard_list.py` → 23 passed. `tools/dev/check_portable_paths.py` → ok (2839 paths).
Whole merged shard, CI shape (`env RVT_SKIP_LARGE=1 LANG=C.UTF-8`, no wheel; measured pre-rebase on ec62a06):
before the drop-in **1093 passed / 124 skipped / 3 xfailed in 197.1 s**; with it **1188 passed / 138 skipped /
3 xfailed / 0 failed in 204.3 s** — exactly +95 passed / +14 skipped (the file) and **+7 s wall** (less than the
file's ~19 s alone: imports and the schema cache are already warm mid-shard), well inside the 1500 s
sandbox timeout.

## `tests/ci_shard.txt` header (comment-only, applied on the tech lead's ruling)

The header's "Deliberately NOT in the shard: tests/test_router.py …" paragraph is replaced by
three comment lines pointing at the drop-in. Entries untouched: `shard_list.py --print | wc -l`
= 55 before and after; `tests/test_shard_list.py` 23 passed after the edit.

## Open questions / follow-ups

* #133 (spec→ifc authoring needs the wheel) is the product gap behind the two skips; when it
  lands a stdlib authoring path, the three `@needs_ifc` decorations here become removable and
  the CI shape gains those cases.
* Predicate consolidation — one engine query `rvt.ifc._fallback.ifc_authoring_available()` +
  one `conftest` marker replacing the ~6 hand-rolled real-wheel predicates (and the two still
  permissive ones in `tests/test_convert.py::needs_ifcos`, `tests/test_ifc_family.py::needs_ifc`)
  — is being filed by the tech-lead session (Refs #133 #102), not done here.

## BRANCH STATE

* Branch `cam/102-shard-test-router` from `main`@ec62a06, rebased onto `main`@c1b52ed (after #363); files: `tests/test_router.py`
  (predicate + decorator lines only), `tests/ci_shard.d/102-test-router.txt` (new),
  `tests/ci_shard.txt` (3 comment lines replace 5; entries untouched),
  `docs/inbox/ci-shard-router.md` (this record, new).
* Gates: table above; `tests/test_shard_list.py` 23 passed; portable paths ok;
  `tools/sync_plugin.py --check` → in sync, deny-audit clean (no `src/`/`tools/`/`skills/` touched).
  `/verify` skipped — tests-only diff, no runtime surface. Full suite NOT run (suite coordination).
* Nothing staged for the viewer; no `.rvt`/`.rfa` produced; no certification claim.
