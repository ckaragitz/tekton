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

---

## eng #553 — 2026-08-10: `surface_bench` classifies the stated prerequisite as BLOCKED, not FAIL (issue #553)

Stream: **bench-ifc-blocked** (engineer session `cse_011azwEpCuhAiKJMdbmyASiS`, branch
`cam/553-bench-ifc-blocked` from `origin/main` @ 074af6b, started by the tech-lead session).
This section is written by the #553 engineer; §1–§7 and the BRANCH STATE above are the #127
engineer's and are left untouched.

**Charter (issue #553 + the tech lead's brief):** teach `tools/surface_bench.py` that a job the
surface refused to start *because it stated the prerequisite up front* — the `go` envelope's
`go.prerequisite` (`ready:false`, `exit_code 3`, `result null`, since #550) or, for the bench's
`run frontdoor.py author --ifc` job, preflight's `routes.ifc = {ok:false, needs, fix}` — is
`BLOCKED` (an honest surface truth, bench exit 0), shown distinctly from `FAIL` and from a pass
in the table and the JSON (`status:"BLOCKED"`, `prerequisite:{route,needs,fix}` copied through,
`reason` = the preflight line / the stated prerequisite), while every other row's classification
and every timing column stays as it was.  Territory: `tools/surface_bench.py` (classification +
table/JSON rendering only — jobs are launched and timed exactly as before),
`tests/test_surface_bench_reason.py`, this section.  Not touched: `tekton_env.py` (the envelope
is #550's; consumed, not changed), the front door, `tests/ci_shard.txt` (no new test file; the
reason test is already in the shard via `tests/ci_shard.d/287-bench-fail-reason.txt`).
`tools/sync_plugin.py` does not mirror `surface_bench.py` into the plugin (checked: no match), so
the rebuilt zip differs from `main`'s in nothing this PR wrote.

### What was built

| Where in `tools/surface_bench.py` | Change |
|---|---|
| `JobResult` | `prerequisite: dict` (empty by default); `blocked(reason, prerequisite=None)` stores it; `as_dict()` adds a `prerequisite` key **only when set** — so every PASS/FAIL/SKIPPED row's JSON key set is byte-for-byte what it was. |
| `_prerequisite(res)` | the `go` envelope's own `go.prerequisite` when `go.ready` is false and it names `needs`; `None` for every other output (a READY envelope, a FAILED job, an environment-NOT-READY envelope *without* a prerequisite — that one stays FAIL: the surface itself is broken). |
| `_needs_words(prereq)` | `needs numpy (python -m pip install numpy)` — the bootstrap's own wording (`tekton_env._route_words`), so table, JSON and the READY line say the same words. |
| `job_preflight` | keeps `pf["routes"]` in `state["preflight"]` (`{}` on pre-#127 plugin builds); nothing of it reaches the report JSON's surface header (still `python_version` + `extras`). |
| `_job_go_author` (both `go author` jobs) | after the pre-`go` SKIPPED probe and **before** the exit-code check: an envelope carrying `go.prerequisite` → `job.blocked(_why(inv), prerequisite=…)`; `_why` already resolves a `ready:false` envelope to its `preflight_line` (#287), so the reason is that line verbatim. |
| `job_author_ifc` | after "built → PASS" and **before** the `ifcopenshell` special-case (issue DONE 1): `state.preflight.routes.ifc.ok is False` → `BLOCKED -- ifc route prerequisite stated by preflight: needs numpy (python -m pip install numpy)` + `prerequisite {route:"ifc", needs, fix}`; table absent (pre-#127 build / preflight job not run) or `ok:true` → the old path (any other non-ok ifc result is still `FAIL` with its own reason). A job that *built* is PASS whatever the table said. |
| `_cell` | a row with `prerequisite.needs` renders `0.4s BLOCKED (needs numpy)`; a BLOCKED row without one (the `ifcopenshell` case) still renders `0.4s BLOCKED`; PASS/FAIL/skipped cells unchanged. |
| `tests/test_surface_bench_reason.py` (+9 tests, already in the shard) | a `_FakeSurface` whose `run` hands back a canned `Invocation`; rows: synthetic `go` prerequisite envelope → BLOCKED, reason == the NOT-READY-for-`--ifc` line, `prerequisite` carried into `as_dict()`, timing keys present; FAILED envelope → still FAIL, no `prerequisite` key; READY+ok envelope → still PASS; `ready:false` **without** prerequisite → still FAIL; `job_author_ifc` × {routes.ifc not ok → BLOCKED with needs/fix, routes.ifc ok + failed job → FAIL, no routes table → FAIL (pre-#127 unchanged)}; a built ifc job → PASS regardless of the table; `_cell` / `markdown_table` wording (`0.1s BLOCKED (needs numpy)`, `Non-PASS detail: … BLOCKED -- tekton: NOT READY for --ifc …`, no `FAIL` anywhere). |

### Evidence — this cloud VM, `/usr/bin/python3` 3.11.15 with **no numpy** as the bare interpreter, repo `.venv` (numpy present) as `local`

`tools/surface_bench.py --zip <zip> --python-bare /usr/bin/python3 --json bench.json --md bench.md`, all
three surfaces, all eight jobs.  **before** = `tools/surface_bench.py` + zip both from `origin/main` @ 074af6b;
**after** = this branch's bench + the zip rebuilt by `tools/sync_plugin.py` on this head.

Before (main) — bench **exit 1**:

```
| job | shell calls | cowork | codeexec | local |
|---|---|---|---|---|
| preflight | 1 | 0.1s | 0.1s (+0.2s extract) | 0.1s |
| author-prompt | 1 | 2.5s | 2.4s (+0.2s extract) | 2.7s |
| go-author-prompt | 1 | 1.9s | 2.6s (+0.2s extract) | 2.0s |
| go-author-6panels | 1 | 4.0s | 4.6s (+0.1s extract) | 4.2s |
| author-ifc | 1 | 0.3s FAIL | 0.5s (+0.2s extract) FAIL | 6.4s |
| edit-roundtrip | 3 | 1.0s | 1.7s (+0.6s extract) | 1.0s |
| go-edit | 1 | 0.6s | 0.9s (+0.2s extract) | 0.6s |
| validate | 1 | 0.4s | 0.6s (+0.2s extract) | 0.4s |
| **session total** |  | **10.7s / 10 calls** | **13.4s / 10 calls** (+1.8s extract) | **17.3s / 10 calls** |
Non-PASS detail:
- cowork / author-ifc: FAIL -- author --ifc failed: IFC intent failed: the --ifc route needs numpy, not installed on this interpreter -- one-time fix: python -m pip install numpy (--prompt / --rvt run without it)
- codeexec / author-ifc: FAIL -- author --ifc failed: IFC intent failed: the --ifc route needs numpy, … (same)
```

After (head) — bench **exit 0**:

```
| job | shell calls | cowork | codeexec | local |
|---|---|---|---|---|
| preflight | 1 | 0.1s | 0.1s (+0.2s extract) | 0.1s |
| author-prompt | 1 | 2.5s | 2.6s (+0.2s extract) | 2.0s |
| go-author-prompt | 1 | 1.9s | 2.5s (+0.2s extract) | 2.0s |
| go-author-6panels | 1 | 4.3s | 4.7s (+0.2s extract) | 4.1s |
| author-ifc | 1 | 0.4s BLOCKED (needs numpy) | 0.5s (+0.1s extract) BLOCKED (needs numpy) | 6.1s |
| edit-roundtrip | 3 | 1.0s | 1.7s (+0.5s extract) | 1.0s |
| go-edit | 1 | 0.6s | 0.9s (+0.2s extract) | 0.5s |
| validate | 1 | 0.4s | 0.8s (+0.2s extract) | 0.4s |
| **session total** |  | **11.1s / 10 calls** | **13.7s / 10 calls** (+1.7s extract) | **16.3s / 10 calls** |
Non-PASS detail:
- cowork / author-ifc: BLOCKED -- ifc route prerequisite stated by preflight: needs numpy (python -m pip install numpy)
- codeexec / author-ifc: BLOCKED -- ifc route prerequisite stated by preflight: needs numpy (python -m pip install numpy)
```

(Seconds are single runs on a shared VM and carry the usual ±0.3 s noise; nothing in how a job is
launched or timed changed, so they are not a before/after claim — the classification is.)

**JSON diff, before vs after** (`scratchpad/jsondiff.py`: per surface/job compare `status`+`reason`, the key
set, and that `shell_calls / seconds / extract_seconds / invocations` are present): 22 of 24 rows *identical
classification, same key set, timing keys present*; the two reclassified rows:

```
cowork    author-ifc   keys +['prerequisite'] -[] timing-missing=[]
   before: status='FAIL'    reason='author --ifc failed: IFC intent failed: the --ifc route needs numpy, not installed on this interpreter -- one-time fix: python -m pip install numpy (--prompt / --rvt run without it)'
   after : status='BLOCKED' reason='ifc route prerequisite stated by preflight: needs numpy (python -m pip install numpy)' prerequisite={'route': 'ifc', 'needs': ['numpy'], 'fix': 'python -m pip install numpy'}
codeexec  author-ifc   (same)
```

**numpy present on the "bare" interpreter** (`--python-bare $PWD/.venv/bin/python --surfaces cowork,codeexec
--jobs preflight,author-ifc`, same after-zip): `author-ifc` **8.5 s / 7.2 s (+0.3 s extract), PASS** on both,
extras `numpy=yes`, bench exit 0 — the READY path is untouched, as before.

### Findings

1. The bench has no `go author --ifc` job (its ifc row is the `run frontdoor.py` path, which `go`'s gate
   deliberately does not cover — #550 §2), so on today's job list the `go.prerequisite` branch in
   `_job_go_author` is exercised by the unit rows and by `/verify` against the real envelope, not by a bench
   row; the bare `author-ifc` row is reclassified through preflight's `routes.ifc`, exactly the issue's DONE 1.
   Adding a `go-author-ifc` job (one call, the flow the SKILL actually documents) would make the envelope path a
   measured row too — a job-list change, outside "classification only" → searched (no existing issue; #113 is
   the `tekton-ifc` skill flow, a different surface) and filed as **#562** (`Refs #553 #127 #113`, `ready`,
   `good-first-pick`).
2. `go.ready:false` *without* `go.prerequisite` (engine / genesis base / out-dir broken) deliberately stays
   FAIL: that is the surface itself being broken, which is what the bench exists to catch.
3. Review pass (`/simplify`, four angles) — applied: `_d` (dict-or-empty) hoisted to module level so `_why`
   and `_prerequisite` share one shape-check idiom; the "needs a + b" phrasing lives only in `_needs_words`
   (`_cell` calls it with a fix-less dict); no defensive `dict()` copy in `blocked()`; the test fake lost its
   dead `keep_artifact` and builds invocations through the file's existing `_inv`.  Skipped, on purpose:
   unifying the two BLOCKED reason wordings (the brief asks for the preflight line verbatim on the envelope
   path, the issue's DONE names the `author-ifc` wording); the `_why(inv)` re-parse of a 300-byte envelope
   (off the clock, same as every `fail` path); a `_prerequisite` hook in `job_go_edit` (`go edit` is never
   gated — `_gated_route` is front-door-only by design, hard rule 1).

### Gates run (this session, final tree)

- Stream-local: `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_surface_bench_reason.py -q -rs` → **18 passed** (0.09 s; 9 pre-existing + 9 new).
- Neighbours: `tests/test_surface_bench_reason.py tests/test_surface_perf.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_plugin_sync.py -q -rs` → **56 passed** (17.2 s).
- `.venv/bin/python tools/sync_plugin.py` then `--check` → *plugin in sync with source (deny-audit clean, identity scan == allowlist, assets verified)*; `plugin/scripts/validate_plugin.py` → *RESULT: PASS*; `python3 tools/dev/check_portable_paths.py` → *ok: 2955 tracked paths are portable*.
- `/verify` (drive the real surface, rebuilt zip): the full bench above (exit 0, two rows `BLOCKED (needs numpy)`, 22/24 rows identical classification + key set); and the real envelope — bare unzip, `env -i PATH=/usr/bin:/bin`, `/usr/bin/python3 skills/tekton-author/scripts/_bootstrap.py go author --ifc skills/tekton-author/examples/electrical-room-2500a.ifc --target-version 2025 --out out/i1 --json` → rc 3, 0 B stderr, `go.ready False, result None, exit_code 3`; fed through the bench: `_prerequisite → {route: ifc, needs: [numpy], fix: python -m pip install numpy}`, row `BLOCKED | tekton: NOT READY for --ifc | ifc-route needs numpy (python -m pip install numpy) -- one-time; the other routes are READY without it`, cell `0.1s BLOCKED (needs numpy)`, keys `[extract_seconds, invocations, job, prerequisite, reason, seconds, shell_calls, status]`.
- Whole merged CI shard (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`): before the review fixes **1860 passed, 134 skipped, 3 xfailed** (421 s); on the final tree **1860 passed, 134 skipped, 3 xfailed** (406 s).

### BRANCH STATE (eng #553)

- **Branch:** `cam/553-bench-ifc-blocked` from `origin/main` @ 074af6b.
- **Files written:** `tools/surface_bench.py`, `tests/test_surface_bench_reason.py`, `docs/inbox/bare-ifc-prereq.md` (this section only).
- **Shipped vs staged:** dev tool only — `surface_bench.py` is not mirrored into the plugin (`tools/sync_plugin.py` has no entry for it); no plugin bytes change; nothing viewer-gated, no batch, no `.rvt` committed.
- **Gates:** stream-local 18 passed; neighbours 56 passed; sync `--check` clean; validate_plugin PASS; portable paths ok; bench exit 0 with the two bare `author-ifc` rows BLOCKED; merged shard **1860 passed, 134 skipped, 3 xfailed** before the review fixes and **1860 passed, 134 skipped, 3 xfailed** (406 s) on the final tree.
- **Open:** #562 (a `go-author-ifc` bench row so the envelope path is measured, not only unit-tested).

---

## eng #562 — 2026-08-10: `surface_bench` gains the `go-author-ifc` row; `author-ifc` is BLOCKED whatever ran before it (issue #562)

Stream: **bench-go-author-ifc** (engineer session `cse_01KKyqZCWvQ9SjYFNYyavXd3`, branch
`cam/562-go-author-ifc-bench` from `origin/main` @ 7d04c82 — i.e. right on top of #565 —
started by the tech-lead session).  This section is written by the #562 engineer; everything
above (the #127 record and the eng #553 section) is left untouched.

**Charter (issue #562 + the tech lead's brief):** (a) the bench measures `go author --prompt`
(one call) and `author-ifc` (`run frontdoor.py …`, the pre-`go` path) but not the IFC flow the
SKILL actually documents — ONE `_bootstrap.py go author --ifc FILE --target-version N --json`
call, which since #550 is also where a bare surface states the route's prerequisite up front;
add that row, timed and counted like its siblings, classified from the envelope itself
(READY + built → PASS; `go.prerequisite` → BLOCKED via #553's `_prerequisite`; anything else →
FAIL with `_why`; pre-`go` build → SKIPPED).  (b) #565's BLOCKED for `author-ifc` read the route
table the *preflight job* left in `state`, so `--jobs author-ifc` alone on a numpy-less
interpreter still read FAIL / exit 1: make it order-independent with the smallest thing that
works.  Territory: `tools/surface_bench.py` (new job + order fix; launch/timing machinery
reused, not changed), `tests/test_surface_bench_reason.py`, `tests/test_surface_perf.py` (the issue's
third DONE bullet — added on the tech lead's ruling, finding 2), this section.  Not touched:
`tekton_env.py`, the front door,
`tests/ci_shard.txt` (no new test *file* — the reason test is already in the merged shard via
`tests/ci_shard.d/287-bench-fail-reason.txt`).  `surface_bench.py` is still not mirrored into
the plugin: the zip rebuilt on this head is **byte-identical** to the one built from `main`
(`cmp` clean, 5 414 998 B both) — nothing a surface receives changed.

### What was built

| Where in `tools/surface_bench.py` | Change |
|---|---|
| `JOB_ORDER` / `JOBS` / module docstring | `go-author-ifc` right after `author-ifc`; `GO_IFC_TARGET_VERSION = "2025"` (the SKILL tells a session to name the recipient's release; 2025 = a certified base). |
| `_job_go_author(s, state, name, short, route_args)` | the shared `go author` job now takes the *input* part of the argv as `route_args(surface)` (built after the per-call reset, so codeexec's fresh plugin dir is the one named) instead of a prompt string; the two prompt jobs pass `["--prompt", P]` with their **old invocation labels verbatim** (`go author --prompt (panel)` / `(6 panels)`), so their JSON rows are unchanged key for key; the kept artifact is named `basename(combined)` (= `prompt_room.rvt` for the prompt route, exactly as before — checked in both JSONs — and `electrical-room-2500a.rvt` for the ifc route, so `--jobs go-author-ifc,validate` validates the right file instead of a mislabelled one). Classification logic itself untouched: SKIPPED probe → `_prerequisite` BLOCKED → exit/`ok` FAIL → breakdown + degraded-load check → PASS. |
| `job_go_author_ifc` | `_job_go_author(…, "--ifc (electrical room)", lambda s: ["--ifc", <plugin>/skills/tekton-author/examples/electrical-room-2500a.ifc, "--target-version", "2025"])` — ONE call, one invocation on the row. |
| `_probe_preflight(s, state, label)` | the `_bootstrap.py --json` call factored out of `job_preflight`: ONE counted invocation; records `state["preflight"] = {python, extras, routes, internal_seconds}` when READY and `{}` when not (= "asked, not READY"). `job_preflight` = that probe + the same PASS / `preflight not READY: …` FAIL as before (row identical in the diff below). |
| `job_author_ifc` | after "built → PASS" and before reading the table: `if "preflight" not in state` (the preflight job did not run in this bench session) → append `_probe_preflight(s, state, "preflight --json (route table)")` to **this row's** invocations, then classify exactly as #565 does. So alone it is 2 counted calls (job 0.4 s + probe 0.08 s → BLOCKED); in a full session (preflight already asked) it stays 1 call and byte-for-byte the #565 row; a built job never probes; a probe that comes back without a table (pre-#127 build) or NOT READY leaves the old FAIL. |
| `tests/test_surface_bench_reason.py` (+12 tests → 30; already in the shard) | `_FakeSurface` now answers a *sequence* of canned `(stdout, exit)` per call and records each call's label + argv. Rows: `go-author-ifc` is in `JOB_ORDER` right after `author-ifc` and in `JOBS`; its ONE call is `go author --ifc <plugin>/…/electrical-room-2500a.ifc --target-version 2025 --json --out <workdir>/…`; classification from synthetic envelopes with **empty state** — prerequisite envelope → BLOCKED / reason = the NOT-READY-for-`--ifc` line / `prerequisite` carried / cell `0.1s BLOCKED (needs numpy)`, READY + `result.ok` ifc envelope → PASS with `breakdown.job_seconds`, ran-and-failed envelope (`Unable to parse IFC SPF header`) → FAIL quoting `errors[0]`, plain readiness line (pre-`go` build) → SKIPPED; `author-ifc` alone: failed job then a READY probe stating `routes.ifc` not ok → BLOCKED, 2 calls, labels `[author --ifc (electrical room), preflight --json (route table)]`, probe argv `[_bootstrap.py, --json]`, table kept in `state` — and the same job with the table already in state → BLOCKED, same reason, **1** call; alone + probe without a table / probe NOT READY → still FAIL (2 calls, no `prerequisite` key); alone + built → PASS, 1 call, no probe; `job_preflight` READY → PASS + full `state["preflight"]`, NOT READY → FAIL with its line + `state["preflight"] == {}`. |
| `tests/test_surface_perf.py` (+1 test → 6; already in the shard via `136-release-gates.txt`) | `go-author-ifc` appended to the `bench_report` fixture's jobs; `SESSION_CALL_BUDGET` 4 → 5 (comment says why); `test_bare_go_author_ifc_builds_or_states_its_prerequisite` — status ∈ exactly {PASS, BLOCKED}, 1 call, PASS+`job_seconds`+`< AUTHOR_CEILING` when the surface's own preflight says numpy is present, BLOCKED+`needs == ["numpy"]`+`< PREFLIGHT_CEILING` when absent; every pre-existing assertion byte-intact (finding 2 has the measured cost on both interpreters). |

### Evidence — this cloud VM, `/usr/bin/python3` 3.11.15 with **no numpy** (and no olefile) as the bare interpreter, repo `.venv` (numpy present) as `local`

`tools/surface_bench.py --zip <zip> --python-bare /usr/bin/python3 --json … --md …`, all three
surfaces, default job list.  **before** = `origin/main` @ 7d04c82's bench run from a `git worktree`
of it against the zip `tools/sync_plugin.py` builds there; **after** = this branch's bench against
the zip rebuilt on this head (byte-identical to before's).  Runs were sequential, nothing else on
the VM; seconds still carry the usual ±0.5 s single-run noise and are not the claim — the row set,
classification and call counts are.

Before (main @ 7d04c82) — 8 rows, bench exit 0, **10 calls per surface**:

```
| job | shell calls | cowork | codeexec | local |
|---|---|---|---|---|
| preflight | 1 | 0.2s | 0.1s (+0.1s extract) | 0.1s |
| author-prompt | 1 | 3.4s | 3.1s (+0.1s extract) | 2.9s |
| go-author-prompt | 1 | 2.7s | 3.1s (+0.2s extract) | 2.6s |
| go-author-6panels | 1 | 5.1s | 5.4s (+0.2s extract) | 5.4s |
| author-ifc | 1 | 0.4s BLOCKED (needs numpy) | 0.6s (+0.2s extract) BLOCKED (needs numpy) | 7.8s |
| edit-roundtrip | 3 | 1.2s | 1.9s (+0.6s extract) | 1.3s |
| go-edit | 1 | 0.7s | 1.2s (+0.2s extract) | 0.7s |
| validate | 1 | 0.5s | 0.7s (+0.2s extract) | 0.5s |
| **session total** |  | **14.2s / 10 calls** | **15.9s / 10 calls** (+1.7s extract) | **21.3s / 10 calls** |
```

After (head) — 9 rows, bench exit 0, **11 calls per surface** (the new row's one call, nothing else):

```
| job | shell calls | cowork | codeexec | local |
|---|---|---|---|---|
| preflight | 1 | 0.1s | 0.1s (+0.2s extract) | 0.1s |
| author-prompt | 1 | 2.9s | 2.9s (+0.2s extract) | 3.1s |
| go-author-prompt | 1 | 2.3s | 2.9s (+0.2s extract) | 2.6s |
| go-author-6panels | 1 | 5.0s | 5.7s (+0.2s extract) | 4.6s |
| author-ifc | 1 | 0.4s BLOCKED (needs numpy) | 0.6s (+0.2s extract) BLOCKED (needs numpy) | 7.0s |
| go-author-ifc | 1 | 0.1s BLOCKED (needs numpy) | 0.1s (+0.2s extract) BLOCKED (needs numpy) | 8.4s |
| edit-roundtrip | 3 | 1.2s | 1.9s (+0.6s extract) | 1.2s |
| go-edit | 1 | 0.7s | 1.1s (+0.2s extract) | 0.6s |
| validate | 1 | 0.5s | 0.7s (+0.2s extract) | 0.6s |
| **session total** |  | **13.2s / 11 calls** | **16.0s / 11 calls** (+2.2s extract) | **28.1s / 11 calls** |
- local / go-author-ifc stages: job 8.2s = P 0.2s · D 0.2s · F 2.6s · L 2.6s (1 pass, 8/8) · specimens 0.0s · W 0.3s · E 0.2s · C 0.1s · V 0.8s
Non-PASS detail:
- cowork / author-ifc: BLOCKED -- ifc route prerequisite stated by preflight: needs numpy (python -m pip install numpy)
- cowork / go-author-ifc: BLOCKED -- tekton: NOT READY for --ifc | ifc-route needs numpy (python -m pip install numpy) -- one-time; the other routes are READY without it
- codeexec / (the same two lines)
```

So the documented IFC flow is now a measured row: **0.1 s BLOCKED (needs numpy)** on both bare
surfaces (the prerequisite stated up front — a fifth of the 0.4–0.6 s the pre-`go` path spends
starting a job that stops), **8.4 s PASS** with numpy (job 8.2 s inside the call; F 2.6 s + L 2.6 s
for 8/8 families in one host pass), one shell call everywhere.

**JSON diff, before ↔ after** (`scratchpad/jsondiff.py`: per surface/job compare `status`, `reason`,
the key set, `shell_calls` and the invocation labels; check the timing keys are present):
**24 of 24 pre-existing rows identical** on all five counts on all three surfaces; the only difference
is the added row —

```
== cowork: calls 10 -> 11; only-after=['go-author-ifc']
   + go-author-ifc  status='BLOCKED' calls=1 keys=[extract_seconds, invocations, job, prerequisite, reason, seconds, shell_calls, status]
                    reason='tekton: NOT READY for --ifc | ifc-route needs numpy (python -m pip install numpy) -- one-time; the other routes are READY without it'
                    prerequisite={'route': 'ifc', 'needs': ['numpy'], 'fix': 'python -m pip install numpy'}  labels=['go author --ifc (electrical room)']
== codeexec: calls 10 -> 11; (same row)
== local: calls 10 -> 11; only-after=['go-author-ifc']
   + go-author-ifc  status='PASS' calls=1 keys=[breakdown, extract_seconds, invocations, job, reason, seconds, shell_calls, status] reason=''
```

(the `validate` row's input is `artifacts/prompt_room.rvt` before and after on all three surfaces —
the `basename(combined)` artifact name is the old name for the prompt route.)

**`--surfaces cowork --jobs author-ifc` alone, bare interpreter** (the order-dependence #565 left):

| | status / exit | calls | reason |
|---|---|---|---|
| before (main) | **FAIL / exit 1**, 0.6 s | 1 | `author --ifc failed: IFC intent failed: the --ifc route needs numpy, not installed on this interpreter -- one-time fix: python -m pip install numpy (--prompt / --rvt run without it)`; surface header `python ?; extras: ?` |
| after (head) | **BLOCKED (needs numpy) / exit 0**, 0.7 s | 2 (`author --ifc (electrical room)` 0.6 s + `preflight --json (route table)` 0.08 s) | `ifc route prerequisite stated by preflight: needs numpy (python -m pip install numpy)`, `prerequisite {route: ifc, needs: [numpy], fix}`; surface header now filled (`python 3.11.15; extras: … numpy=NO`) |

**`--surfaces cowork,codeexec --jobs go-author-ifc` alone, bare interpreter:** `0.1s BLOCKED (needs numpy)` /
`0.1s (+0.3s extract) BLOCKED (needs numpy)`, 1 call each, exit 0 — no preflight job needed, the envelope
alone decides.  **numpy present on the "bare" interpreter** (`--python-bare $PWD/.venv/bin/python --surfaces
cowork,codeexec --jobs preflight,go-author-ifc,validate`): `go-author-ifc` **9.2 s / 9.0 s (+0.3 s extract) PASS**
(job 9.0 / 8.8 s; L 1 pass, 8/8), and `validate` then gates the ifc-built `artifacts/electrical-room-2500a.rvt` →
PASS (0.6 / 0.9 s); extras `numpy=yes`; exit 0.

### Findings

1. The lazy probe is deliberately **counted on the `author-ifc` row** (2 calls when run alone) rather than
   hidden: on codeexec it is a real re-extract + process, and an uncounted shell call in a harness whose unit
   of cost is the shell call would be the one dishonest number in the table.  In the default job list the
   preflight job has already asked, so the row — and `tests/test_surface_perf.py`'s call budget, which does
   not include `author-ifc` anyway — is unchanged.
2. Issue #562's DONE also names a `tests/test_surface_perf.py` assertion for the new row; the first head of this
   PR (ba028d8) left it out because the brief's territory line did not list that file — the tech lead ruled that
   an accident and asked for it on this branch, so it **is** in the PR (second commit).  What it adds — every
   pre-existing assertion in the file left byte-intact: `"go-author-ifc"` appended to the `bench_report`
   fixture's job list (last, so the four existing rows run exactly as before); `SESSION_CALL_BUDGET` 4 → 5 with
   the comment saying why (the documented IFC flow is ONE call whether it builds or states its prerequisite);
   `test_bare_go_author_ifc_builds_or_states_its_prerequisite`: the row's status ∈ **exactly {PASS, BLOCKED}**
   (FAIL or a silent SKIPPED is red), 1 shell call, and *which* of the two is tied to the surface's own preflight
   `extras.numpy` (= that interpreter's `find_spec("numpy")` under the bench env — numpy is never imported into
   the test process, and the expectation cannot disagree with what the surface itself sees): numpy present →
   PASS + `breakdown.job_seconds` + `seconds < AUTHOR_CEILING` (20 s); absent → BLOCKED +
   `prerequisite.needs == ["numpy"]` + `seconds < PREFLIGHT_CEILING` (2 s: a preflight-cost answer, not a job).
   **Measured shard cost, this VM, plugin tree, cowork surface (the fixture's exact `run_bench` call):**
   numpy-less bare (`/usr/bin/python3`, what `_bare_python()` picks here): row `BLOCKED 0.069 s`, 1 call,
   `needs ['numpy']`; whole file **5 passed in 8.80 / 8.41 s → 6 passed in 9.05 / 8.51 s** (+≈0.1 s, inside
   run-to-run noise); numpy-present bare (the repo `.venv` python forced in as `_bare_python()` — what a CI
   sandbox whose only python3 is the venv gives): row `PASS 8.435 s` (job 8.237 s, 8/8 families, 1 call), whole
   file **5 passed in 8.77 / 9.23 s → 6 passed in 16.64 / 16.67 s** (+≈8 s = the real ifc build); session calls
   4 → 5 on both.  Both branches of the assertion were exercised for real, not only the one this host defaults to.
3. `go author --ifc` on the bundled example plans and loads **8** families in one host pass (L `8/8`), so the
   shared degraded-load guard (`n_loaded < n_planned` → FAIL) covers the ifc row for free; a future ifc build that
   quietly loads 5/8 will read FAIL here, not a fast PASS.
4. Review pass (`/simplify`, four angles) — applied: `_probe_preflight` reads as an early return for NOT READY
   then the one summary dict (no trailing conditional expression); the test fake indexes canned calls strictly
   (an unplanned extra shell call is an `IndexError`, not a silently repeated answer); the built-ifc payload and
   the `author-ifc` BLOCKED wording are module constants shared by the #553 and #562 rows; the pre-#127 probe row
   drops `routes` in the parametrize itself; the preflight-job check is two flat tests instead of one branching
   parametrize.  Skipped, on purpose: hoisting the probe into `bench_surface` (an uncounted call, or a changed
   row/count for `--jobs go-author-ifc` / `go-edit` which need no table — the altitude reviewer agreed the job is
   the right place and `_probe_preflight` is already the reusable seam); dropping `_surface(…, *then)` (three
   multi-call tests use it; the one raw `_FakeSurface(...)` is the non-JSON pre-`go` case).

### Gates run (this session, final tree)

- Stream-local: `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_surface_bench_reason.py -q -rs` → **30 passed** (0.12 s; 18 pre-existing + 12 new); `tests/test_surface_perf.py` → **6 passed** (8.5–9.1 s with the numpy-less `/usr/bin/python3`; 16.6–16.7 s with the venv python forced in as the bare interpreter — both branches green).
- Neighbours: `tests/test_surface_bench_reason.py tests/test_surface_perf.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_plugin_sync.py -q -rs` → **68 passed** (19.0 s).
- `.venv/bin/python tools/sync_plugin.py` then `--check` → *plugin in sync with source (deny-audit clean, identity scan == allowlist, assets verified)*; rebuilt zip byte-identical to main's; `plugin/scripts/validate_plugin.py` → *RESULT: PASS*; `python3 tools/dev/check_portable_paths.py` → *ok: 2960 tracked paths are portable*.
- `/verify` (drive the real surface, zip rebuilt on the **final** tree — still byte-identical to main's — bare `/usr/bin/python3`): full bench exit 0, `go-author-ifc` `0.1s BLOCKED (needs numpy)` / `0.1s (+0.1s extract) BLOCKED (needs numpy)` / `8.5s` PASS, `author-ifc` `0.4s BLOCKED` / `0.6s BLOCKED` / `6.9s`, 11 calls per surface, JSON diff vs before again 24/24 old rows identical + the one added row; `--surfaces cowork,codeexec --jobs author-ifc` alone → `0.6s BLOCKED (needs numpy)` / `0.7s (+0.3s extract) BLOCKED (needs numpy)`, 2 calls each, exit 0 (main: FAIL / exit 1); the earlier `--jobs go-author-ifc` alone (BLOCKED ×2, exit 0) and numpy-present (PASS + validate PASS on the ifc output) runs above.
- Whole merged CI shard (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`): **1909 passed, 134 skipped, 3 xfailed** (479 s) on the final tree.

### BRANCH STATE (eng #562)

- **Branch:** `cam/562-go-author-ifc-bench` from `origin/main` @ 7d04c82.
- **Files written:** `tools/surface_bench.py`, `tests/test_surface_bench_reason.py`, `tests/test_surface_perf.py`, `docs/inbox/bare-ifc-prereq.md` (this section only).
- **Shipped vs staged:** dev tool only — `surface_bench.py` is not mirrored into the plugin; the rebuilt zip is byte-identical to main's; nothing viewer-gated, no batch, no `.rvt` committed.
- **Gates:** stream-local 30 passed; neighbours 68 passed; sync `--check` clean; validate_plugin PASS; portable paths ok; full bench exit 0 (new row BLOCKED on cowork/codeexec, PASS on local; 10 → 11 calls per surface; 24/24 old rows identical); `--jobs author-ifc` alone on the bare interpreter: main FAIL/exit 1 → head BLOCKED/exit 0; merged shard **1909 passed, 134 skipped, 3 xfailed** (479 s).
- **Open:** nothing from the issue's DONE; the perf assertion (finding 2) landed in the second commit on the tech lead's ruling.
