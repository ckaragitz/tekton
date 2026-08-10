# BARE-IFC-PREREQ — the `--ifc` route's one prerequisite, stated up front on the bare plugin surface (issue #127)

Stream: **bare-ifc-prereq** (2026-08-10, issue #127, branch `cam/127-bare-ifc-prereq`,
engineer session started by the tech-lead session for the fan-out).

Charter (issue #127, narrowed by the tech lead for this wave): on the bare-plugin
surface (unzipped `tekton-plugin.zip`, system `python3` **without numpy** — the
Windows/macOS/locked-VM default), `go author --ifc <file>` must either return a
built `.rvt` or state its prerequisite **once, up front** — in the preflight/READY
line and in the ONE JSON envelope — never a mid-job traceback or a vague failure;
the prompt and edit routes must stay exactly as fast and as quiet as today (PG3,
S-2026-08-09-g).  Option **A** of the issue (a numpy-free `rvt.ifc.intent`) is
measured below and filed as a follow-up: the module is FENCED this wave (P0 #498)
and the change is not "a few lines".

**DONE state delivered (option B + the front-door boundary):**
`_bootstrap.py --json` / the READY line declare the ifc-route capability
(`routes.ifc = {ok, needs, fix}`, line segment `ifc-route OK` / `ifc-route needs
numpy (python -m pip install numpy)`); `go author --ifc …` on a numpy-less
interpreter answers ONE JSON with `go.prerequisite`, `go.ready:false`, a
relayable `tekton: NOT READY for --ifc | …` line, exit 3, 0 B stderr and **no job
attempted**; with numpy present nothing is gated and the job builds as before
(READY, rc 0, VALID 0/0); the front door's own message for the same condition
(the `run frontdoor.py author --ifc` / `tools/frontdoor.py` path) is one whole
sentence naming the extra and the fix instead of a status cut at 160 chars
mid-fix; five shard tests pin both states and the table↔engine agreement.**

---

## 1. What happens today on `main` (measured first, as asked)

Cloud VM, `/usr/bin/python3` 3.11.15 with **no numpy and no olefile** (vendored
olefile kicks in), `env -i PATH=/usr/bin:/bin HOME=/tmp`, bare unzip of the zip
built from `origin/main` @ fdcbf12:

| call | rc | stdout | stderr | wall |
|---|---|---|---|---|
| `_bootstrap.py --json` (preflight) | 0 | one JSON, `ok:true`, `extras.numpy:false`, line `tekton: READY \| … \| family-donor missing \| out-dir OK \| 0.064s` — **nothing about the ifc route** | 0 B | 0.08 s |
| `go author --ifc electrical-room-2500a.ifc --target-version 2025 --out out/i1 --json` | 3 | one JSON: `go.ready:true`, `go.preflight_line: "tekton: READY …"`, then `result.status: "FAILED (IFC intent failed: ImportError: numpy is required here (IFC placement / geometry resolution) but is not installed: No module named 'numpy'. One-time fix: python)"` ← the 160-char status cap cuts the fix mid-word; `result.errors[0]` has the whole `_lazyimp` sentence; `files:{}`; manifest written | 0 B | 0.61 s |

So the earlier reports were right: **no traceback, one JSON, exit 3, an install
hint** — honest.  What was missing is exactly the tech lead's remaining DONE:
READY preceded a guaranteed FAILED (a skill session could not know before
starting the job), the envelope had no structured prerequisite, and the status
line a skill relays verbatim was cut mid-fix.

## 2. What was built

| File | Change |
|---|---|
| `plugin/skills/_shared/tekton_env.py` (hand-authored, stdlib-only) | `ROUTE_EXTRAS = {"ifc": ("numpy",)}` — the one table; `_route_capability(extras)` → `preflight()["routes"] = {prompt:{ok,needs}, ifc:{ok,needs[,fix]}, rvt:{ok,needs}}` from the `find_spec` probe preflight already did (nothing imported, +0 ms); READY line gains `ifc-route OK` / `ifc-route needs numpy (python -m pip install numpy)`; `_route_words(cap)` is the ONE wording (`OK` / `needs numpy (python -m pip install numpy)`) the READY line, `go` and `doctor` all print; `_gated_route(script, args)` spots `--ifc FILE` / `--ifc=FILE` on a front-door call (deliberately the front door only: gating a sibling script on a guess would be a refusal of a job that might build); `go()` short-circuits such a job when `routes.ifc.ok` is false through the same exit-3 block the environment-NOT-READY path uses (`go.ready:false`, `go.exit_code:3` — now present on both NOT-READY shapes, `go.preflight` detail, `result:null`) plus `go.prerequisite = {route, needs, fix}` and `go.preflight_line = "tekton: NOT READY for --ifc \| ifc-route needs numpy (python -m pip install numpy) -- one-time; the other routes are READY without it"` — which the SKILL.md's existing rule (*`go.ready:false` → relay `preflight_line` verbatim, it names the one thing wrong*) already handles with **zero SKILL.md edits**; `doctor` prints its ifc hint from the same table; docstrings say so. |
| `src/rvt/_lazyimp.py` (where the error is raised, +10 lines) | `ExtraNotInstalled(ImportError)` carrying `name=` (the missing module) and `hint` — the proxy used to raise a bare `ImportError(msg)` with no `name`, forcing callers to dig in `__cause__`; every existing `except ImportError` still catches it. |
| `src/rvt/frontdoor/__init__.py` `_route_ifc` (the boundary, 6 lines) | `except ExtraNotInstalled` (narrow: a genuinely broken bundle still reaches the generic handler truthfully) ahead of the generic one: `IFC intent failed: the --ifc route needs numpy, not installed on this interpreter -- one-time fix: python -m pip install numpy (--prompt / --rvt run without it)` from `e.name`, exactly 160 chars so `status = FAILED (…)` carries it whole (coupling noted in the comment); keeps the `IFC intent failed:` prefix `router.py`'s nothing-buildable detection keys on. `src/rvt/ifc/intent.py` untouched (FENCED). |
| `tests/test_coldstart.py` (+5 tests, already in the shard) | `test_preflight_states_ifc_route_needs_numpy_when_absent` (`-I -S`), `…_ok_when_numpy_present` (`-I`, skips without numpy), `test_go_author_ifc_without_numpy_states_prerequisite_once` (rc 3, stderr `""`, one JSON, `go.prerequisite.needs == ["numpy"]`, NOT READY line, `result is None`, no `job_seconds`, out dir never created), `test_ifc_route_prerequisite_table_matches_the_engine` (drift guard: `run frontdoor.py author --ifc` under `-I -S` stops on exactly that extra, whole status, manifest still written — turns red the day the route goes numpy-free so the table must follow), `test_go_author_ifc_with_numpy_is_not_gated` (`-I`, `--stages W`, 2.5 s). |
| `plugin/lib/src/rvt/frontdoor/__init__.py`, `plugin/lib/src/rvt/_lazyimp.py` | byte-identical mirrors written by `tools/sync_plugin.py`. |
| `docs/inbox/bare-ifc-prereq.md` | this record. |

Not touched (per territory): `tools/frontdoor.py`, every `SKILL.md`, `tools/surface_bench.py`, `src/rvt/ifc/intent.py`, `tests/ci_shard.txt` (no new test *file*, so no drop-in needed — `tests/test_coldstart.py` is already in the merged shard).

## 3. Evidence — before/after from a bare unzip, `env -i PATH=/usr/bin:/bin`, `/usr/bin/python3` (no numpy)

Zips: **before** = `tools/sync_plugin.py` on a `git worktree` of `origin/main` @ fdcbf12 (5 378 210 B); **after** = this branch (5 379 532 B).  Same VM, nothing else running, 5+5 **interleaved** runs per job (`scratchpad/interleave.sh`), wall = shell-measured, medians:

| call (bare python3, no numpy) | before: rc / stderr / wall median (min–max) | after: rc / stderr / wall median (min–max) | envelope |
|---|---|---|---|
| `_bootstrap.py --json` | 0 / 0 B / 0.076 s (0.074–0.077) | 0 / 0 B / 0.077 s (0.072–0.082) | + `routes`; line + `ifc-route needs numpy (python -m pip install numpy)` |
| `go author --prompt "an electrical room 12x10 ft with one lighting panel" --target-version 2025` | 0 / 0 B / 2.610 s (2.566–3.823) | 0 / 0 B / 2.636 s (2.579–3.486) | `go` keys identical (`exit_code, job_seconds, one_call, preflight_line, preflight_seconds, ready, seconds, verb`); `result.status PROOF-ONLY (self-checks PASS …)`, `files {combined, families_dir}` both sides |
| `go edit assets/genesis/G_ABPD_2025.rvt set-level --id 1351691 --elevation-ft 5.0 -o …` | 0 / 0 B / 0.680 s (0.631–0.763) | 0 / 0 B / 0.643 s (0.632–0.714) | `go` keys identical (+`inputs`); `result.ok true`, gates `structural PASS … \| validation PASS (0 errors, 0 warnings)` both sides |
| `go author --ifc electrical-room-2500a.ifc --target-version 2025` | 3 / 0 B / 0.407 s (0.380–0.411); `go.ready:true`, READY line, `result.status FAILED (…One-time fix: python)` (cut) | 3 / 0 B / **0.076 s** (0.073–0.098); `go.ready:false`, `go.prerequisite {route:ifc, needs:[numpy], fix:"python -m pip install numpy"}`, `go.preflight_line "tekton: NOT READY for --ifc \| ifc-route needs numpy (python -m pip install numpy) -- one-time; the other routes are READY without it"`, `go.exit_code 3`, `result:null`, no `out/` dir created | prerequisite stated once, up front |
| `run frontdoor.py author --ifc …` (the bench's path, no `go` gate) | 3 / 0 B; status cut mid-fix | 3 / 0 B; `status == "FAILED (IFC intent failed: the --ifc route needs numpy, not installed on this interpreter -- one-time fix: python -m pip install numpy (--prompt / --rvt run without it))"`, manifest written | whole sentence |

**Prompt and edit: unchanged** — medians within run-to-run noise (±0.04 s on 2.6 s / 0.65 s), identical key sets, 0 B stderr, same rc.  Preflight cost of the capability table: +0.000 s (it reuses the `find_spec` result `extras` already computed).

**numpy present (repo `.venv`, `python -I`, same after-unzip, same `env -i`):** `go author --ifc electrical-room-2500a.ifc --target-version 2025 --out out/ifc-numpy --json` → rc 0, 0 B stderr, 7.97 s wall, line `tekton: READY | … | ifc-route OK | …`, `go.ready:true`, no `prerequisite` key, `result.status PROOF-ONLY (self-checks PASS; …)`, `files {combined: …/electrical-room-2500a.rvt, families_dir}`, `release.output 2025`, `this_file validated-not-certified (our gate: combined: VALID 0 errors / 0 warnings …)`; `tools/rvt_validate.py` on that `.rvt`: `ok true, error 0, warning 0, info 2`.

**`tools/surface_bench.py --zip {before,after}.zip --surfaces cowork,codeexec,local --jobs preflight,go-author-prompt,author-ifc,go-edit --python-bare /usr/bin/python3`** (run while `tests/test_frontdoor.py` was also running, so absolute seconds carry contention noise; the classification is the point):

| job | before cowork / codeexec / local | after cowork / codeexec / local |
|---|---|---|
| preflight | 0.1 / 0.1 / 0.1 s | 0.1 / 0.1 / 0.1 s |
| go-author-prompt | 2.9 / 3.1 / 3.3 s | 3.2 / 2.9 / 2.4 s |
| author-ifc | 0.4 s FAIL / 0.6 s FAIL / 7.5 s PASS | 0.4 s FAIL / 0.5 s FAIL / 11.5 s PASS |
| go-edit | 0.8 / 1.1 / 0.8 s | 0.7 / 1.1 / 0.6 s |

The bench still says `FAIL` for the bare `author-ifc` because its classifier (`job_author_ifc`) only special-cases the word `ifcopenshell`; teaching it `BLOCKED (prerequisite stated by preflight: routes.ifc)` is `tools/surface_bench.py` = #113's file, out of this territory → follow-up below with the patch.  Its `reason` is now the whole front-door sentence instead of `…(or run the skill'`.

## 4. Option A, measured: why a numpy-free `--ifc` route is not "a few lines"

The only numpy import on the route is `src/rvt/ifc/intent.py:84` (`np = lazy_import("numpy", …, hint="IFC placement / geometry resolution")`); steplite already replaces ifcopenshell, so **numpy is the honest minimum and the whole prerequisite**.  But `intent.py` (3 291 lines, FENCED under #498 this wave) has **159 `np.` call sites over 25 distinct APIs** — `array ×57, ndarray ×48 (annotations), dot ×15, linalg.norm ×11, asarray ×10, round ×8, eye ×7, cross ×6, mean ×5, zeros ×4, vstack ×4, unique ×3, append ×3, sort/ptp/isclose/c_/allclose ×2, sum/ones/linalg.inv/lexsort/argsort/arctan/abs ×1` — plus 23 sites of ndarray-only syntax (`m[:3, :3]` slice assignment, `@`, `.T`, `.tolist()`).  Two honest routes to A: (i) rewrite the placement-chain / footprint math on plain lists (the 4×4 chain is ~40 lines; `unique`/`lexsort`/`ptp` over vertex clouds is the long tail), or (ii) a stdlib `numpy`-subset shim served the way steplite serves `ifcopenshell` (zero edits to intent.py, but a mini-ndarray with 2-D slicing and `@` is a real module + a parity suite).  Either is M-sized and lives in a fenced file → filed, not done here.  Cost of *not* doing A today: the two real sandboxes (Cowork, code-execution) ship numpy (bench note), so exposure is Windows/macOS system Pythons and locked VMs — who now get the prerequisite in the first 0.08 s instead of after starting a job.

## 5. Findings

1. `preflight.extras.ifcopenshell` reads `true` on a bare box because `ensure_engine` has already put the steplite shim dir on `sys.path` (by design, #130) — so `extras` answers "importable", not "the real library"; `doctor` distinguishes the two (`IS_STEPLITE`).  Left as is; noted so nobody reads it as "ifcopenshell installed".
2. On the before run the failed ifc result carried `release.requested: null / resolution: "unspecified"` although `--target-version 2025` was passed — `_route_ifc` resolves base+version only after the intent resolved (`if model is not None`).  Harmless now that `go` never reaches it without numpy, but the `run frontdoor.py` path still shows it; belongs to the front door's manifest/target_status owners, mentioned for them (not filed: cosmetic on a FAILED result).
3. The `go` NOT-READY envelope previously had no `exit_code` key (early return before it was set) while SKILL.md lists `exit_code` among `go`'s keys; both NOT-READY exits now carry `exit_code: 3`.

4. Review pass (`/simplify`, four angles) — applied: one wording helper instead of three
   renderings; `ExtraNotInstalled` in `_lazyimp` so the boundary catches narrowly and reads
   `e.name`; no closure / no duplicated `go.route`; both NOT-READY exits share one block and
   both carry `exit_code`; tests probe numpy with `find_spec` (no numpy import at collection).
   Skipped, on purpose: (a) gating every `go` target that names an `.ifc` (route.py,
   ifc_intent.py, ifc_to_spec.py also stop on numpy mid-job) — a false gate is a refusal
   (hard rule 1) and only the front door's failure is proven by a test here; listed as a
   follow-up candidate instead; (b) moving `ROUTE_EXTRAS` into a light engine module
   (`rvt.ifc._fallback`) the bootstrap already imports — plausible, but the territory put the
   table in the bootstrap and the subprocess drift guard is the binding either way.

## 6. Follow-ups (searched first: no existing issue for either)

- **A — numpy-free `--ifc` intent resolution** (`src/rvt/ifc/intent.py` placement-chain + footprint math on stdlib, or a steplite-style numpy-subset shim), DONE = `go author --ifc` under `python3 -I -S` builds the combined `.rvt`, VALID 0, `surface_bench author-ifc PASS` on cowork/codeexec with `numpy=NO`, and `test_ifc_route_prerequisite_table_matches_the_engine` flipped to assert success + `ROUTE_EXTRAS` emptied.  Blocked on the #498 fence lifting for `intent.py`.  → filed as **#552** (`Refs #127 #498`, `blocked` until the fence lifts).
- **surface_bench: classify a preflight-stated prerequisite as BLOCKED, not FAIL** (`tools/surface_bench.py`, #113's territory).  Patch, for whoever holds the file:
  ```python
  # job_preflight: keep the capability table
  state["preflight"] = {..., "routes": pf.get("routes", {})}
  # job_author_ifc, before the ifcopenshell special-case:
  cap = (state.get("preflight") or {}).get("routes", {}).get("ifc")
  if cap is not None and not cap.get("ok"):
      return job.blocked(f"ifc route prerequisite stated by preflight: needs "
                         f"{' + '.join(cap.get('needs') or ['?'])} ({cap.get('fix')})")
  ```
  DONE = bench exits 0 on a numpy-less image with `author-ifc BLOCKED (…needs numpy…)`, still FAIL on any other ifc failure; `tests/test_surface_bench_reason.py` gains the case.  → filed as **#553** (`Refs #127 #113`, `ready`, `good-first-pick`).

## 7. Gates run (this session)

- `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_coldstart.py tests/test_bootstrap.py tests/test_plugin_sync.py tests/test_surface_perf.py tests/test_surface_bench_reason.py -q -rs` → **47 passed** (19.7 s); the 5 new tests alone: 5 passed in 3.6 s.
- `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_frontdoor.py tests/test_ifc_intent_units.py -q -rs` → **89 passed, 5 skipped** (pinned-base-absent ×1, samples ×1, RVT_SKIP_LARGE ×2, root-chmod ×1).
- `.venv/bin/python tools/sync_plugin.py` then `--check` → *plugin in sync with source (deny-audit clean, identity scan == allowlist, assets verified)*; `plugin/scripts/validate_plugin.py` → *25 assertions, PASS*; `python3 tools/dev/check_portable_paths.py` → *ok: 2941 tracked paths are portable*.
- `/verify` (drive the real surfaces, after the review fixes, rebuilt zip): bare unzip + `env -i` + `/usr/bin/python3`: `_bootstrap.py` → `tekton: READY | … | ifc-route needs numpy (python -m pip install numpy) | …`, rc 0, 0 B stderr; `go author --ifc … --target-version 2025` → one JSON, `go.ready:false`, `go.prerequisite {route: ifc, needs: [numpy], fix}`, `exit_code 3`, `result null`, 0 B stderr; `run frontdoor.py author --ifc …` → rc 3, whole-sentence status, 0 B stderr; `doctor` → `the --ifc route needs numpy (python -m pip install numpy)`; `go author --prompt "an electrical room with 6 panels" --target-version 2025` → READY, rc 0, job 6.0 s, `PROOF-ONLY (self-checks PASS …)`, `files {combined: prompt_room.rvt, families_dir}`, `VALID 0 errors / 0 warnings`, 0 B stderr. Repo `.venv` (numpy present): `tools/frontdoor.py author --ifc plugin/skills/tekton-author/examples/electrical-room-2500a.ifc --target-version 2025` → rc 0, `PROOF-ONLY (self-checks PASS …)`, `errors []`, `tools/rvt_validate.py` on the combined `.rvt` → ok, 0 errors / 0 warnings / 2 info; probe `--ifc README.md` → `FAILED (IFC intent failed: Error: Unable to parse IFC SPF header)`, rc 3 (a non-prerequisite failure still reaches the generic handler, not misreported as a missing extra).
- Whole merged CI shard (`RVT_SKIP_LARGE=1 … pytest -q -p no:cacheprovider $(shard_list.py --print)`): before the review fixes **1810 passed, 133 skipped, 3 xfailed** (471 s); on the final head **1810 passed, 133 skipped, 3 xfailed** (460 s).

## BRANCH STATE

- **Branch:** `cam/127-bare-ifc-prereq` from `origin/main` @ fdcbf12.
- **Files written:** `plugin/skills/_shared/tekton_env.py`, `src/rvt/_lazyimp.py`, `src/rvt/frontdoor/__init__.py` (+ mirrors `plugin/lib/src/rvt/{_lazyimp,frontdoor/__init__}.py` via sync), `tests/test_coldstart.py`, `docs/inbox/bare-ifc-prereq.md`.
- **Shipped vs staged:** everything ships with the plugin (hand-authored bootstrap + mirrored engine); nothing viewer-gated, no batch staged, no `.rvt` bytes committed.
- **Gates:** stream-local 47 passed; frontdoor + ifc-intent units 89 passed / 5 skipped; sync `--check` clean; validate_plugin PASS; portable paths ok; merged shard on the final head **1810 passed, 133 skipped, 3 xfailed** (460 s; identical counts before the review fixes).
- **Open:** the two follow-ups in §6 — #552 (option A behind the #498 fence) and #553 (bench BLOCKED classification in #113's file).
