# family-plan-fault-status — a planning FAULT is distinguishable from a fact REFUSAL (#462)

Stream: eng #462 (branch `cam/462-family-plan-fault-status`), follow-up of #442 / PR #457.
Territory: `src/rvt/ifc/intent.py::plan_families` (+ the `FamilyPlan.status` comment),
the ONE degradation f-string in `src/rvt/frontdoor/build.py`, tests, mirrors, this record.

## Why

#442 gave `plan_families` a per-item backstop: an unexpected exception out of
`plan_family_for(e)` is recorded for THAT item and every other item still plans (rule 1).
It reused the policy word `'refused'` — the same status an honest `FactoryError` earns when
the catalog has no member for a rating — so `summarize()['family_plans_by_status']` could not
tell a resolver **bug** (a traceback we should fix) from missing **facts** (the user should pick
a covered rating), and `frontdoor.build`'s degradation line appended *"the facts store never
invents dimensions/ratings; supply the missing facts or choose a covered rating"* to both —
misleading advice when the cause is our code.

## What was built

| File | Change |
|---|---|
| `src/rvt/ifc/intent.py` | `plan_families`' backstop sets `status="faulted"` (refusal text `"<Type>: <message>"` and the one note unchanged); its docstring and the `FamilyPlan.status` comment list the five statuses and which two are built. Nothing else in the file touched (`write_intent`'s writer line is #481's). |
| `src/rvt/frontdoor/build.py` | the degradation loop: a `faulted` plan reads `"<tag> (<kind>): NOT built -- planning FAULT: <refusal> (a resolver bug; the file is delivered without this item -- please report it)"`; every other non-buildable status keeps the existing wording + facts hint byte-for-byte. |
| `tests/test_intent_schedule_scalars.py` | the #442 backstop test updated **deliberately**: `("T1", "faulted")`, counts `{"resolved": 2, "faulted": 1}`, docstring says why. |
| `tests/test_intent_faulted.py` (new, shard drop-in `tests/ci_shard.d/462-family-plan-fault-status.txt`) | 4 tests: (1) device resolver forced to raise → the receptacles' plans `faulted` with the reason, the 5000 kVA transformer stays an honest `refused` (`FactoryError: no variant match…`), DP-1 `resolved`; `buildable_family_plans` = DP-1 only; counts `{"resolved": 1, "refused": 1, "faulted": 4}`. (2) through `FD.author(prompt=…)` with `_resolve_xfmr_facts` raising for the 75 kVA item only: delivered (`ok`, no errors, combined `.rvt` on disk, DP-1 generated + placed), `build.degradations` carries the FAULT wording for T1 and the facts hint for the honest T2 refusal, `MANIFEST.md` renders the FAULT line, summary `{"resolved": 1, "faulted": 1, "refused": 1}`. (3) the shard tripwire: no plan is `faulted` on the seven prompt fixtures the front-door suites build from, OUR two bundled example IFCs (`inputs/ifc/*.ifc`), and OUR IFC round trip (prompt → intent → IFC4 → intent = `{"resolved": 5}`); every status seen ⊆ {resolved, house, refused, unmapped}. (4) catalog-free: an item whose planning raises is `faulted` next to an `unmapped` neighbour; counts `{"unmapped": 1, "faulted": 1}`. |
| `plugin/lib/src/rvt/{ifc/intent.py,frontdoor/build.py}` | byte-identical mirrors via `tools/sync_plugin.py`. |

Verified by reading, no change needed (as the issue predicted):
- `rvt.frontdoor.intent.buildable_family_plans` (`status in ("resolved", "house")`) and
  `build.py`'s `not in ("resolved", "house")` gate exclude `faulted` exactly as they excluded
  `refused`; `summarize()` counts by whatever status string a plan carries, so `faulted` shows
  separately with no code change in `src/rvt/frontdoor/intent.py` (not touched).
- `tools/ifc_intent.py::stage_families` records `{"built": False, "reason": plan.refusal or f"status {plan.status}"}` — the reason already echoes the refusal text; not touched (eng #475's file).
- `src/rvt/frontdoor/manifest.py` renders `build.degradations` verbatim (`- **degradation**: …`); no schema change.
- `src/rvt/convert/add_to_project.py:491` has its own degradation loop *without* the facts hint
  (`"… NOT built -- family plan faulted: RuntimeError: …"`) — honest as is; outside territory, left.
- Nothing reads a `FamilyPlan` back from JSON with an enum check (`intent_to_json` / `as_json`
  echo the string; `prompt_intent`'s coverage audit echoes `{tag: status}`), so the new word
  needs no reader change.

## Evidence (numbers)

**(a) 6-panel prompt, main vs head — identical after masking the noise class.**
Driver: `FD.author(prompt="an electrical room with 6 panels", no_handoff=True)` run from an
`origin/main` worktree (6c2afd7) twice and from this head once; manifests flattened to leaves.
- main₁ vs main₂ (the noise class): 2844 leaves each, **147 differ, 0 after mask** — the mask is
  exactly what two identical-code runs disagree on: out-dir-bearing paths
  (`.path/.relpath/.in/.out/.final/.dir/.report/.base/.log/.file/.cli`, `families_dir`,
  `entrypoint`, `out_dir`, `intent.json`), per-run content GUIDs (`…guid`, `…_guids[i]`) and the
  hashes they move (`sha256`, `md5`), `seconds`, `generated_at`, per-gate timings.
- main₁ vs **head**: 2844 leaves each, 149 differ, **0 after the same mask**.
  `MANIFEST.md` main vs head: 3 lines differ — timestamp, the base's absolute path (worktree vs
  checkout, same sha256 `84173b8960b8cbba…`), the combined file's sha256 (GUID noise; both
  692224 bytes). `family_plans_by_status {"resolved": 6}`, `degradations []` on both.

**(b) forced-fault job, main vs head — same delivery, honest words.**
Driver: `_resolve_xfmr_facts` wrapped to raise `RuntimeError("resolver bug (evidence)")` for the
75 kVA item only, then `FD.author(prompt="an electrical room with a 400 A distribution panel, a
75 kVA transformer and a 5000 kVA transformer", no_handoff=True)` (the test does the same through
`monkeypatch.setattr(I, "_resolve_xfmr_facts", faulty)`).
- Both: `ok True` (CLI rc 0), status `PROOF-ONLY (self-checks PASS; …)`, `errors []`, files
  `{families_dir, combined: prompt_room.rvt}` — 606208 bytes both, validator `n_errors 0`,
  `elements_created` = 1 family(.rfa) + 1 loaded-family + 1 equipment-instance + 4 walls, same
  out-dir listing (MANIFEST.md, build.log 1003 B, intent.json 23504 B, manifest.json, the .rvt).
- Masked manifest diff main → head: 1089 → 1090 leaves, **5 differ after mask, all intended**:
  `build.degradations[0]` (wording), `intent.summary.family_plans[1].status` refused → faulted,
  `intent.summary.audit.family_plans.T1` refused → faulted, `family_plans_by_status.refused`
  2 → 1, `family_plans_by_status.faulted` ∅ → 1.
- `MANIFEST.md` wording diff (out dir normalised; timestamp/base-path/sha lines omitted):
  ```
  < - family plans: resolved 1, refused 2
  > - family plans: resolved 1, faulted 1, refused 1
  < - **degradation**: T1 (transformer): NOT built -- family plan refused: RuntimeError: resolver bug (evidence) (the facts store never invents dimensions/ratings; supply the missing facts or choose a covered rating)
  > - **degradation**: T1 (transformer): NOT built -- planning FAULT: RuntimeError: resolver bug (evidence) (a resolver bug; the file is delivered without this item -- please report it)
  ```
  T2's honest refusal line (`family plan refused: FactoryError: no variant match … (the facts
  store never invents …)`) is byte-identical on both.

**(c) product surface.** `tools/sync_plugin.py` synced 2 files, deny-audit clean, identity scan
== allowlist, `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
`check_portable_paths.py` ok (2919 paths). Bare unzip of the rebuilt `tekton-plugin.zip` +
system `python3` (3.11, `env -i`): `skills/tekton-author/scripts/_bootstrap.py go author
--prompt "an electrical room with 6 panels" --out out/j1 --json` → `ready true`, preflight
`tekton: READY | … | genesis verified (Revit 2026) | …`, `exit_code 0`, job `ok`, 4.9 s wall,
**stderr 0 bytes**, job manifest `family_plans_by_status {"resolved": 6}`, `degradations []`.

**(d) tests.** `tests/test_intent_faulted.py` 4 passed (3.2 s);
`tests/test_intent_schedule_scalars.py tests/test_intent_device_plan.py tests/test_shard_list.py`
66 passed; whole merged shard: see BRANCH STATE.

## Findings / follow-ups

- Filed **#492** (`Refs #462`): `'unmapped'` plans (ground bus, conduit runs, …) still get the
  facts hint appended in `build.py` although their reason is "no constructor for this kind /
  recorded only" — as misleading there as it was for the fault case, but outside this issue's
  DONE (the wording predates #442); and `add_to_project.py`'s parallel degradation loop should
  share ONE formatter with `build.py` so a sixth status cannot fork the wording a third time
  (left alone here: outside territory, and it never carried the hint).
- `/simplify` (4 angles): reuse → the e2e test now gates on `conftest.pinned_base(2026)` (the
  certified pin or a clean skip) instead of a fourth hard-coded asset path; efficiency → clean
  (+3.2 s on the shard, all in the one load-bearing `FD.author` job); simplification → test 1/3
  trimmed of assertions other suites own; the optional `build.py` loop reshuffle skipped to keep
  the shared-file diff to the one branch; altitude → "appropriately shallow for the territory"
  (statuses are bare literals module-wide; an enum would touch ~8 sites for one value), the two
  deeper items are #492.

BRANCH STATE: `src/rvt/ifc/intent.py` (backstop status + two doc comments), `src/rvt/frontdoor/build.py`
(one degradation branch), their two `plugin/lib` mirrors, `tests/test_intent_faulted.py` (new, 4 tests),
`tests/ci_shard.d/462-family-plan-fault-status.txt` (new), `tests/test_intent_schedule_scalars.py`
(the #442 backstop test updated deliberately), this record. Gates: stream-local 4 + 66 passed;
sync `--check` clean, validate_plugin PASS, portable paths ok, bare-unzip `go author` READY / rc 0 /
stderr 0 B; merged CI shard (`RVT_SKIP_LARGE=1 … -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`):
1634 passed, 170 skipped, 4 xfailed, 0 failed in 5 min 55 s. Nothing staged for the
viewer; no certification claim; no hot file, no NO-GO file touched. Shipped = the PR; nothing else pending.
