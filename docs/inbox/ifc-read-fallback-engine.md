# ifc-read-fallback-engine — the steplite fallback is selected by the ENGINE (issue #130)

**Stream:** ifc-read-fallback-engine (issue #130, P1, `area:engine` / `area:frontdoor`).
**Date:** 2026-08-09.  **Branch:** `cam/130-steplite-engine-fallback`.
**Charter (the issue's DONE):** with ifcopenshell NOT installed, `tools/frontdoor.py author --ifc
inputs/ifc/electrical-room-2500a.ifc` from a repo checkout returns ok with 4 walls + 8 instances and
`python -m rvt.convert.rvt_to_ifc <that .rvt>` reports the round-trip check `ran: true`; the
`sys.path` append lives in the engine (find_spec-guarded, append never prepend, real install wins,
`RVT_STEPLITE_FORCE=1` still forces steplite); `tekton_env.ensure_engine` keeps working; a new
in-process absence-simulation test joins `tests/ci_shard.txt`; `sync_plugin --check` clean.

## Why (one paragraph)

CLAUDE.md §2 says ifcopenshell is optional because IFC *reading* has a stdlib fallback
(`rvt.ifc.steplite`, served as an `ifcopenshell` look-alike package under `rvt/ifc/_ifcos_shim`).
The fallback was real but its *selection* lived only in the plugin bootstrap
(`plugin/skills/_shared/tekton_env.py::ensure_engine`).  A plain checkout, CI, or a Windows/cloud
contributor without the 40 MB wheel therefore got `IntentError: ifcopenshell is required to read
IFC` from `frontdoor author --ifc`, and `rvt_to_ifc` delivered its IFC with the caveat
`round-trip check did not run`.  Repo, CI and plugin now select the backend by the same engine
code (PG3), which is also a prerequisite for running the whole suite honestly in CI (#133).

## What landed

1. **`src/rvt/ifc/_fallback.py`** (new, stdlib-only, ~70 lines incl. the law's docstring):
   `SHIM_DIR`, `FORCE_ENV`, `ifcopenshell_findable()` (a `find_spec` that treats a *raising* finder
   as "absent"), `ensure_ifc_reader()` — no ifcopenshell findable → **append** the shim dir (never
   first); `RVT_STEPLITE_FORCE=1` → shim **first** (the one explicitly requested case where steplite
   must beat an installed wheel: equivalence tests, backend A/B — the shim's own FORCE check is the
   other half of that law); real library findable → touch nothing; idempotent.
2. **`src/rvt/ifc/__init__.py`**: imports the helper and calls `ensure_ifc_reader()` once.  Every
   read module (`rvt.ifc.intent`, `rvt.ifc.product_facts`) is a submodule, so by the time its
   `import ifcopenshell` runs the shim is importable whenever the real library is not.  The lazy
   `ifcopenshell` import block in `intent.py` (#6 / PR #141) is untouched — it simply resolves to
   whichever backend the package selected.
3. **`plugin/skills/_shared/tekton_env.py::ensure_engine`**: its inline copy of the law is gone —
   importing `rvt.ifc._fallback` *is* the selection; the bootstrap keeps only its own concern,
   exporting the shim dir on `PYTHONPATH` for a skill session's children when it is on `sys.path`
   (an engine mirror older than this change simply gets no export, which is what it did for reads
   anyway).  Behaviour for a skill session is unchanged (`test_bootstrap`, `test_coldstart`,
   `test_steplite`'s bare `-S` ensure_engine test all green).
4. **`tests/test_ifc_read_fallback.py`** (new, 8 tests, ~2 s, fresh-clone runnable, in the CI
   shard): the selection law in-process with the real wheel *hidden* by a meta-path finder when it
   is installed (append-last + idempotent; raising finder = absent; FORCE puts the shim first; real
   install wins with `ifcopenshell.__file__` asserted NOT under `_ifcos_shim` and `sys.path`
   untouched); the law out of process (`import rvt.ifc` alone makes `import ifcopenshell`
   resolvable on any box); `rvt.frontdoor.intent.intent_from_ifc` resolves the tracked example IFC
   through steplite (4 walls, 12 equipment, 8 buildable family plans → the 8 placed instances);
   `rvt_to_ifc.roundtrip_table` **runs** on steplite (4/4 walls); `tekton_env.ensure_engine` twice +
   the engine helper on a bare `-S` interpreter leave exactly one shim entry, appended, exported.
   No module is ever reloaded and no env var leaks (an earlier draft that used
   `importlib.reload` / in-process `ensure_engine` polluted `IntentModel` class identity and
   `RVT_PLUGIN_ROOT` for later tests — caught by running the module ahead of `test_frontdoor` /
   `test_router`, fixed by re-arming intent's lazy proxies via monkeypatch and moving the
   bootstrap composition test out of process).
5. Docstring truth fixes only: `src/rvt/ifc/steplite.py` (SELECTION paragraph) and
   `src/rvt/ifc/_ifcos_shim/ifcopenshell/__init__.py` now name the engine helper as the selector.
6. `tests/ci_shard.txt` += `tests/test_ifc_read_fallback.py`.  `tests/test_router_release.py`
   loses its module-level copy of the append (dead now that `import rvt.frontdoor.router` selects;
   file otherwise untouched, 13 passed / 2 skipped in the no-ifc venv).  Plugin mirror re-synced
   (`plugin/lib/src/rvt/ifc/**`).
7. `/simplify` pass (4 reviewers) applied before the final commit: dropped an unused `backend()`
   helper and a `typing` import from `_fallback.py`, collapsed `tekton_env`'s stale inline copy,
   removed the dead append in `test_router_release.py`, and reduced the test fixture to one undo
   mechanism + one subprocess helper.  Skipped (noted, cross-territory cosmetics): having the shim
   read `FORCE_ENV` from `_fallback` (perf-deps' file), the redundant shim `PYTHONPATH`/`insert`
   set-ups in `test_steplite.py` / `test_lazy_ifc_import.py` that the engine now makes unnecessary
   but harmless, and switching the doctor's extras loop to an engine call.

## Evidence (two venvs on the same cloud VM, Python 3.11; numbers, not adjectives)

`.venv` = `scripts/cloud-setup.sh` (real ifcopenshell 0.8.5 + numpy 2.4.6);
`/tmp/noifc` = `python3 -m venv` + `pip install -e ".[test]"` (numpy, **no** ifcopenshell:
`find_spec('ifcopenshell') → None`).  Absence is proved with the throwaway venv, not only by
env-forcing (the issue's note: subprocess-based standalone tests strip `PYTHONPATH`).

### Before (branch point `5a40b22`, no-ifcopenshell venv)

```
$ /tmp/noifc/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc --out $S/before --json
 "ok": false,
 "status": "FAILED (IFC intent failed: IntentError: ifcopenshell is required to read IFC)",
 "errors": ["IFC intent failed: IntentError: ifcopenshell is required to read IFC"],
$ /tmp/noifc/bin/python -m rvt.convert.rvt_to_ifc $S/before_real/electrical-room-2500a.rvt --out-dir $S/rt_before
delivered: {"ifc": ".../rt_before/electrical-room-2500a.ifc"}
caveat: round-trip check did not run: resolve_intent failed: IntentError: ifcopenshell is required to read IFC
```

### After (this branch, no-ifcopenshell venv)

```
$ /tmp/noifc/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc --out $S/after_noifc --json
ok True | PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)          # 14.9 s wall
elements_created: {'family(.rfa)': 8, 'wall': 4, 'equipment-instance': 8, 'loaded-family': 8}
validation.combined: VALID, n_errors 0                     # == the .venv/real-ifcopenshell run, kind for kind
intent.json byte-equal to the real-ifcopenshell run: True   (129,011 bytes, `source` path excluded)

$ /tmp/noifc/bin/python -m rvt.convert.rvt_to_ifc $S/after_noifc/electrical-room-2500a.rvt --out-dir $S/rt_after
delivered: {"ifc": ".../rt_after/electrical-room-2500a.ifc"}
round trip: equipment 8/8, walls 4/4, all_survived=True     # manifest: roundtrip.ran = true      0.9 s wall

$ /tmp/noifc/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc --target-version 2025 --out $S/i25 --json
ok True | PROOF-ONLY …; release: requested 2025 / output 2025 / resolution match / target_support certified-base   # 15.0 s wall
$ /tmp/noifc/bin/python tools/rvt_validate.py $S/i25/electrical-room-2500a.rvt --json $S/i25.validation.json
ok True, counts {'error': 0, 'warning': 0, 'info': 2}; rvt.versions.detect_release → 2025
$ /tmp/noifc/bin/python -m rvt.convert.rvt_to_ifc $S/i25/electrical-room-2500a.rvt --out-dir $S/rt_i25
round trip: equipment 8/8, walls 4/4, all_survived=True
```

Backend selection, all three modes (`python -c "import rvt.ifc, ifcopenshell; …"`):
no-ifc venv → `steplite`, shim is `sys.path[-1]`; `.venv` → `ifcopenshell`
(`…/site-packages/ifcopenshell/__init__.py`, shim NOT on `sys.path`); `.venv` +
`RVT_STEPLITE_FORCE=1` → `steplite`.

### ifcopenshell vs steplite delta (steer #108: same `.venv`, sequential, `RVT_STEPLITE_FORCE` A/B)

| measure (electrical-room-2500a.ifc, 577 entities / 687 KB) | real ifcopenshell | steplite | note |
|---|---|---|---|
| `resolve_intent` alone (3 runs) | 0.97–1.05 s | 0.83–0.90 s | steplite ~12 % faster on this small file (#160 tracks the 2000-product case where it is 2.7× slower) |
| `frontdoor author --ifc --target-version 2025` job wall (2 runs each) | 15.05 / 15.77 s | 14.88 / 15.66 s | reader is ~6 % of the job; family generation dominates |
| `rvt_to_ifc` incl. round trip, wall | 1.27 / 1.29 s | 0.91 / 1.02 s | real lib's import weight shows on a 1 s process |
| intent.json | — | byte-equal | both target 2026 (default) and 2025 runs |

### Cost of doing the selection at `import rvt.ifc` (bare-surface concern, steer S-2026-08-09-g)

`import rvt.frontdoor, rvt.frontdoor.build, rvt.ifc.intent` in a fresh interpreter, 15 runs,
before = `origin/main`'s `rvt/ifc/__init__.py` copied over this tree, after = this branch:

| interpreter | before median / min | after median / min |
|---|---|---|
| `.venv` (real ifcopenshell present) | 56.4 / 52.5 ms | 58.1 / 53.5 ms |
| `/tmp/noifc` | 55.8 / 51.9 ms | 57.9 / 52.6 ms |

`-X importtime` inside the front-door import: `rvt.ifc._fallback` self 0.2–0.3 ms;
`ensure_ifc_reader()` alone 0.06–0.11 ms; the rest of its ~1.4 ms cumulative is `importlib.util`
(+`threading`) merely being imported *earlier* — `rvt.frontdoor.build` / `router` import it at
module level anyway.  Net: ≤ ~1 ms per process, at the run-to-run noise floor; no new import on
the prompt-only path that was not already there.

### `/verify` (project skill) on the final code

```
# repo checkout, no-ifcopenshell venv
$ /tmp/noifc/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc --target-version 2025 --out $S/final_noifc --json
ok True | PROOF-ONLY (self-checks PASS …); release 2025/2025 match; kinds {'family(.rfa)': 8, 'wall': 4, 'equipment-instance': 8, 'loaded-family': 8}; wall 14.6 s
$ /tmp/noifc/bin/python tools/rvt_validate.py $S/final_noifc/electrical-room-2500a.rvt --json $S/final_v.json
  verdict: VALID (no errors); warnings=0 info=2            # under its own release (2025)
$ /tmp/noifc/bin/python -m rvt.convert.rvt_to_ifc $S/final_noifc/electrical-room-2500a.rvt --out-dir $S/final_rt
round trip: equipment 8/8, walls 4/4, all_survived=True
$ /tmp/noifc/bin/python tools/provenance.py … --baseline all --streams --json …   # ran; fresh clone has no baseline corpora -> 3471 'unbaselined' (this diff changes no writer bytes)

# bare unzip of tekton-plugin.zip (out/verify/pz), PYTHONPATH unset
$ /tmp/noifc/bin/python skills/tekton-author/scripts/_bootstrap.py doctor
tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | … | 0.029s
  extra ifcopenshell: steplite fallback active (pure-python read path, zero install; …)
$ /tmp/noifc/bin/python skills/tekton-author/scripts/_bootstrap.py go author --ifc skills/tekton-author/examples/electrical-room-2500a.ifc --target-version 2025 --out out/j_ifc --json
rc=0, ok True | PROOF-ONLY …, release 2025, combined .rvt -> rvt_validate: VALID (no errors); wall 13.7 s   # numpy present, NO ifcopenshell
$ python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/j1 --json
rc=0, ok True | PROOF-ONLY …, combined delivered; wall 9.7 s                                                  # system python: no numpy, no ifcopenshell
```
(The bare-python `--ifc` case without numpy is #127's, unchanged here.)

### Gates

| gate | no-ifcopenshell venv | `.venv` (real ifcopenshell) |
|---|---|---|
| `tests/test_ifc_read_fallback.py` (new; final form) | 7 passed / 1 skipped (the real-install-wins case), 2.0 s | 8 passed, 2.5 s |
| after `/simplify`: `test_bootstrap test_coldstart test_steplite test_plugin_sync test_ifc_read_fallback` / `.venv`: `+ test_surface_perf`, and `test_ifc_intent → test_ifc_read_fallback → test_frontdoor::…matches_ifc_route_shape → test_steplite → test_router_release → test_lazy_ifc_import` (ordering probe for cross-test pollution) | 37 passed / 8 skipped; 22 passed / 3 skipped | 26 passed / 4 skipped; 61 passed |
| `test_ifc_intent test_ifc_family test_lazy_ifc_import test_ifc_read_fallback test_steplite test_frontdoor test_router test_router_release test_convert test_target2025 test_bootstrap test_coldstart test_plugin_sync` (+ `test_frontdoor_standalone::test_standalone_electrical_room_ifc` in noifc, + `test_engine` in .venv), `RVT_SKIP_LARGE=1` | **166 passed / 59 skipped / 2 failed** — the 2 are `test_router::test_e2e_spec_to_ifc` + `test_route_manifest_shape`, which fail identically at the branch point (spec→ifc *authors* IFC via `ifcopenshell.api`, which steplite deliberately does not serve; `test_router.py` is excluded from the shard for exactly this, #102) | **215 passed / 47 skipped / 0 failed** |
| baseline of the same noifc set at `5a40b22` (before) | 149 passed / 60 skipped / 2 failed (same two) — i.e. +17 tests now *run and pass* without ifcopenshell instead of skipping/failing, incl. `test_standalone_electrical_room_ifc` and `test_target2025::test_ifc_addition_roundtrips_the_intent` | — |
| `tools/sync_plugin.py` → `--check` | clean ("plugin in sync with source (deny-audit clean, assets verified)") | |
| `plugin/scripts/validate_plugin.py` | PASS (24 assertions) | |
| `tools/dev/check_portable_paths.py` | ok | |

## Findings / notes for neighbours

* **#127 (numpy on the bare surface) is untouched and still true:** the reader selection needs
  nothing, but `rvt.ifc.intent`'s placement/geometry maths is numpy; the new tests mark the two
  intent-resolving cases `needs_numpy` citing #127.  With numpy present (CI installs `.[test]`),
  the `--ifc` route is now dependency-complete on a plain checkout.
* **`tests/test_engine.py` cannot even be *collected* without the real ifcopenshell**
  (`skills/tekton-ifc/scripts/bridge_lib.py` imports `ifcopenshell.validate` at module top; no
  importorskip guard) — pre-existing, independent of this change, and squarely the tekton-ifc
  *authoring* surface that legitimately needs the real library.  Relevant to #133's "0 failed
  without ifcopenshell"; noted there rather than fixed here (out of territory).
* Tests that probe "do we have ifcopenshell?" with a bare `import ifcopenshell` now get the shim on
  a no-wheel box as soon as anything has imported `rvt.ifc`.  Probes that need the *authoring*
  surface should test `not getattr(ifcopenshell, "IS_STEPLITE", False)` (as `test_steplite` /
  `test_router_release` already do) or importorskip the submodule they need (`ifcopenshell.api`,
  `.guid`, `.geom`).  In the files run above this changed no outcome except turning skips into
  passes; `test_router`'s two spec→ifc cases were already failing on such a box.
* `RVT_STEPLITE_FORCE=1` is now meaningful from a plain checkout with the wheel installed (before,
  it only worked if you also put the shim on `PYTHONPATH` yourself) — that is what made the
  same-interpreter A/B above a one-variable experiment.

## Open questions

None blocking.  Whether `rvt_to_ifc`'s manifest should record `roundtrip.reader`
(`rvt.ifc._fallback.backend()`) is a nicety for #153's IFC census, not done here (convert
territory).

## BRANCH STATE

* Branch `cam/130-steplite-engine-fallback` from `main@5a40b22`; PR closes #130.
* Files written: `src/rvt/ifc/_fallback.py` (new), `src/rvt/ifc/__init__.py`,
  `src/rvt/ifc/steplite.py` (docstring), `src/rvt/ifc/_ifcos_shim/ifcopenshell/__init__.py`
  (docstring), `plugin/skills/_shared/tekton_env.py`, `tests/test_ifc_read_fallback.py` (new),
  `tests/test_router_release.py` (dead append removed), `tests/ci_shard.txt`, this record; generated mirror `plugin/lib/src/rvt/ifc/**` via
  `tools/sync_plugin.py`.  No hot file touched (`tools/frontdoor.py`, `src/rvt/frontdoor/base.py`,
  `src/rvt/versions/`, `plugin/skills/*/SKILL.md` untouched); `src/rvt/ifc/intent.py` untouched (#6).
* Gates: as tabled above; `sync_plugin.py --check` clean; `validate_plugin.py` PASS; portable paths ok.
* Staged vs shipped: nothing staged for the viewer (no writer bytes change: the built `.rvt` is
  kind-for-kind and validation-identical across backends, intent JSON byte-equal); ships with the PR.
