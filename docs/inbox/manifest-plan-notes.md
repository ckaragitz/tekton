# manifest-plan-notes — schedule-cell notes reach the manifest a user opens (#465)

Stream: eng #465 (session `cse_017htKTwGCJazZJqCHCzzs4k`), branch `cam/465-manifest-plan-notes`.
Refs #442 / #438 (PR #457 review, nit c). Area: frontdoor, PG1 / PG3.

## Why

`rvt.ifc.intent` records ONE honest note per hand-typed / unusable schedule cell on the affected
`FamilyPlan.notes` (`PanelSchedule.MainsRating '100 A' is a text label, not a measure -> read as
100 A`; `DeviceSchedule.Load 'abc' is not a usable apparent load (not a number) -> booked at the
default 180 VA`). Before this branch those notes reached `intent.json` (`familyMapping[].notes`)
only: `manifest.json`'s `intent.summary.family_plans[]` carried
`tag/kind/status/constructor/variant/catalog/refusal`, and `MANIFEST.md`'s Intent section printed
`- family plans: resolved 5` and nothing else. A user whose panel silently rated from another cell
had the one explaining line in a file nobody opens. Rule 1 says caveats ride *after* delivery —
where the caveats are read.

## What was built

- `src/rvt/frontdoor/intent.py::summarize` — every `family_plans[]` row gains `"notes": list`
  (last key; `[]` when none). Nothing else in the summary changes.
- `src/rvt/frontdoor/manifest.py`
  - `_render_md`, Intent section: under the `- family plans: …` row, one indented
    ``  - note: `TAG` — <note>`` line per note per plan, in plan order; nothing when no plan has a
    note (every prompt job). There is no per-plan row in MANIFEST.md's Intent section (only the
    by-status row), so each note line names its plan's tag.
  - the optional third DONE item, done **inside manifest.py** (build.py untouched):
    `plan_note_degradations(intent_summary)` + `DROPPED_CELL_MARK = " is not a usable "` — one
    `build.degradations` line per plan whose notes say a cell was DROPPED / DEFAULTED
    (`LP-1: PanelSchedule.BusRating '4OO A' is not a usable current rating (not a number) ->
    ignored: BusRating reads as an empty cell (fix the schedule cell to book it)`), appended in
    `build_manifest` next to the census / authorship-census lines it already appends there. The
    coerced-label family (`… is a text label, not a measure -> read as …`) stays informational (a
    note line, never a degradation). The marker is the wording
    `rvt.ifc.intent.parse_schedule_scalar` gives every dropped cell (and `parse_device_load` /
    `parse_mounting_height` share it); both route tests import `DROPPED_CELL_MARK` and assert it
    is in the dropped-cell note and not in the coerced-label note, so the seam fails at the seam
    if either side's wording drifts. The right-depth follow-up — `parse_schedule_scalar`
    classifying each note itself (coerced / dropped) so the manifest imports the classification
    instead of matching wording — needs `rvt.ifc.intent`, out of this territory: filed as **#497**
    (`Refs #465`, P2).
  - `#481`'s json writer line (`_jsonsafe.dump`) left alone.
- Tests (only the two named functions touched):
  - `tests/test_intent_schedule_scalars.py::test_a_hand_typed_mains_rating_no_longer_fails_the_ifc_route`
    additionally asserts `summary.family_plans` LP-1 `notes == lp.notes`, R-1..R-4 `notes == []`,
    and MANIFEST.md contains exactly one ``  - note: `LP-1` — …`` line right under
    `- family plans: resolved 5`; `build.degradations` stays `[]` (a coerced label is not a
    degradation).
  - `tests/test_intent_device_plan.py::test_a_hand_typed_load_label_no_longer_fails_the_ifc_route`
    additionally asserts both notes in `summary.family_plans`, exactly one plan carries the
    dropped-cell note, `build.degradations == ["<that tag>: <that note>"]` (was `== []`), and
    MANIFEST.md carries two `  - note:` lines plus the one `- **degradation**:` line.
- Mirrors via `tools/sync_plugin.py` (`plugin/lib/src/rvt/frontdoor/{intent,manifest}.py`).

Intended, visible consequence beyond schedule cells: `FamilyPlan.notes` also carries the house
switchboard's provenance note (`MSB` on `inputs/ifc/electrical-room-2500a.ifc`) and the per-item
backstop's "planning this item raised … NOT built" note; both now print under the family-plans row
too (they explain `house 1` / `refused N` on that very row). Neither contains the dropped-cell
marker, so neither becomes a degradation (a refused plan already has its own degradation line from
the build).

## Evidence (as nobody: fresh cloud clone, `scripts/cloud-setup.sh`, no `samples/`)

Fixture = the one the two tests build: OUR IFC of `an electrical room with a 100 A lighting panel
and 4 duplex receptacles at 44 in AFF` (`prompt_to_intent` → `write_intent_ifc`), with
`MainsRating IFCREAL(100.)` retyped `IFCLABEL('100 A')` (`hand.ifc`), and a second copy that also
retypes `BusRating IFCREAL(100.)` → `IFCLABEL('4OO A')` (letter O; `hand2.ifc`).

`tools/frontdoor.py author --ifc hand.ifc --target-version 2025 --json`, main → head:

- rc 0 → 0; stderr 0 B → 0 B; wall 3.3 s class both; `--json` stdout identical modulo the noise
  class (timestamps, output hashes, seconds, out-dir); status `PROOF-ONLY (self-checks PASS; …)`
  both.
- manifest.json `intent.summary.family_plans[]`: main = no `notes` key on any row; head =
  ```
  LP-1 resolved ["PanelSchedule.MainsRating '100 A' is a text label, not a measure -> read as 100 A"]
  R-1 resolved []   R-2 resolved []   R-3 resolved []   R-4 resolved []
  ```
  `build.degradations` unchanged (the one release-independent KNOWN LIMIT line of a 2025 target).
- MANIFEST.md diff main → head (paths/timestamps aside) = exactly one added line:
  ```
   - family plans: resolved 5
  +  - note: `LP-1` — PanelSchedule.MainsRating '100 A' is a text label, not a measure -> read as 100 A
   - feeder edges: 0
  ```

Same command on `hand2.ifc` (the dropped cell), head:

- `family_plans[LP-1].notes` = `["PanelSchedule.BusRating '4OO A' is not a usable current rating (not a number) -> ignored: BusRating reads as an empty cell (fix the schedule cell to book it)", "PanelSchedule.MainsRating '100 A' is a text label, not a measure -> read as 100 A"]`
- `build.degradations` gains ONE line: `LP-1: PanelSchedule.BusRating '4OO A' is not a usable current rating (not a number) -> ignored: BusRating reads as an empty cell (fix the schedule cell to book it)`
- MANIFEST.md diff main → head = two `  - note:` lines under the family-plans row + one
  `- **degradation**: LP-1: …` line in Build; rc 0, stderr 0 B, status unchanged, LP-1 still built
  and placed (delivery unchanged — a label, rule 1).

6-panel prompt job (`author --prompt "an electrical room with 6 panels" --json`):

- Noise class established by running **main twice**: `generated_at`, the combined file's
  `sha256` / `md5`, every `seconds` value (top-level, per stage, and the stage-V per-gate timings
  `stages[].gates.*`), the six minted family `content_guid` / `guid` values wherever they recur, the
  out-dir path. MANIFEST.md between the two main runs: timestamp + combined sha256 only.
- main vs head, that class masked: manifest.json residual = **exactly six** added
  `"notes": []` keys (one per PP-1..PP-6 plan row, each turning `"refusal": null` into
  `"refusal": null,` + `"notes": []`) and nothing else; MANIFEST.md **byte-identical** (empty
  notes print nothing); `--json` stdout identical; rc 0 both; stderr 0 B both; wall 3.46 / 3.63 s
  (main ×2) vs 3.42 s (head).
- Bare unzip of the rebuilt `tekton-plugin.zip`, system `python3`, no repo on the path:
  `skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/j1 --json`
  → `tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | … | 0.045s`,
  exit 0, stderr **0 B**, job 4.33 s, result `ok: true`, all six plan rows `notes: []`, 0 note
  lines in MANIFEST.md.
- `tools/rvt_validate.py <after>/ifc2/hand2.rvt` → ok, 0 errors / 0 warnings / 2 info (necessary, not
  sufficient — no load claim). The bare-unzip `go author --ifc hand2.ifc` with the VM's system
  `python3` (no numpy) ends `FAILED (IFC intent failed: ImportError: numpy is required here …)`,
  rc 3, stderr 0 B — the pre-existing, designed `rvt._lazyimp` message for the IFC route on a
  numpy-less interpreter, identical on main; not this change.
- Also driven: `usecases/chicago-plenum-electrical-room/hardened.ifc` (rc 0, stderr 0, no plan
  notes → Intent section unchanged) and `inputs/ifc/electrical-room-2500a.ifc` (rc 0, stderr 0,
  the `MSB` house-switchboard note now prints under `family plans: unmapped 4, resolved 7, house 1`;
  degradation count unchanged).

## Gates

- `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_intent_device_plan.py tests/test_intent_schedule_scalars.py -q -rs` → **43 passed** (0 skipped).
- `tools/sync_plugin.py` run → `--check`: plugin in sync (deny-audit clean, identity scan == allowlist);
  `plugin/scripts/validate_plugin.py` → PASS (25 assertions); `tools/dev/check_portable_paths.py` → ok (2926 paths).
- Whole merged CI shard `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)` → **1734 passed, 139 skipped, 3 xfailed** in 315 s on the pushed head (rebased onto 4cc81dd);
  before the rebase (base e3579ea): 1690 / 139 / 3 xfailed, 308 s (the +44 are #493/#494/#495's tests).
- No new test file → no `tests/ci_shard.d/` drop-in (both touched tests are already in the shard).
- No `.rvt` shipped by this PR; the outputs above validated 0 errors inside their own jobs.

## Open questions / follow-ups

- Filed #497 (structured note severity out of the resolver; deletes `DROPPED_CELL_MARK`).
- No router change needed: the router already turns every `build.degradations` entry into a
  caveat, so a dropped cell now also reaches `route.py run`'s one-JSON result.

## BRANCH STATE

- Branch `cam/465-manifest-plan-notes` from `origin/main`, rebased onto 4cc81dd (#493 #494 #495 merged underneath; no overlap); PR opened not-draft, `Closes #465`.
- Files written: `src/rvt/frontdoor/intent.py` (summarize only), `src/rvt/frontdoor/manifest.py`
  (renderer + `plan_note_degradations` hook), `tests/test_intent_device_plan.py`,
  `tests/test_intent_schedule_scalars.py` (one named function each), mirrors
  `plugin/lib/src/rvt/frontdoor/{intent,manifest}.py`, this record.
- Not touched: `rvt.ifc.intent`, `build.py`, `router.py`, any hot file, `tests/ci_shard.txt`.
- Staged vs shipped: nothing staged for the viewer (no load claim); shipped = the manifest change.
- Gates: as above, all green on the pushed head.
