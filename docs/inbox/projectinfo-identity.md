# projectinfo-identity — front-door outputs write THE JOB's identity into ProjectInfo (issue #148)

Stream: `eng148` (engineer session under the tech-lead session; branch
`cam/148-projectinfo-identity`). Closes #148. Refs #108 (requirements
sweep wave 2), #19 (base-level identity scrub — owner-machine; this is the
per-job write, doable on a fresh clone), PG1 (trustworthy, honestly stamped
output), S-2026-08-09-g (latency measured before/after).

## 1. Problem (measured, not assumed)

Every prompt/IFC output shipped the pinned base's ProjectInfo verbatim.
Decoded from `plugin/assets/genesis/G_ABPD.rvt` (element **49504**, class
`ProjectInfo`, category -2003101, seq-102 `m_pParamValueSetAString`):

| BIP id | Revit field | pinned 2026 base | 2025 / 2024 bases |
|---|---|---|---|
| -1006317 | Project Name | `GENESIS Base` | `GENESIS Base` |
| -1006316 | Project Number | `GEN-0000` | `GEN-0000` |
| -1006318 | Project Address | `` | `` |
| -1006319 | Client Name | `rev-revit genesis` | `tekton genesis` |
| -1006320 | Project Status | `Genesis Baseline` | `Genesis Baseline` |
| -1006321 | Project Issue Date | `2026-08-03` | `2026-08-03` |
| -1019005 | Organization Name | `rev-revit` | `tekton` |
| -1019006 | Organization Description | `genesis base document authored by our writer` | same |
| -1019007 | Building Name | `Genesis Base` | `Genesis Base` |
| -1019008 | Author | `rvt-writer` | `rvt-writer` |

…while the manifest of the same job said `project: Electrical Room`. (The
2026 pin predates the `rev-revit` → `tekton` rename in
`house_standard.PROJECT_INFO`; the string survived only inside the binary.)

## 2. What was built

* **`src/rvt/frontdoor/project_info.py` (new, front-door territory)** —
  `ProjectIdentity` (the ten strings; defaults: status
  `PROJECT_STATUS_PROOF_ONLY = "PROOF-ONLY"`, author
  `identity.PRODUCT_AUTHOR_PLACEHOLDER`, everything unknown = blank, never a
  base placeholder), `FIELD_PARAMS` (field → BuiltInParameter id + Revit UI
  label, the ten ids `genesis.skeleton.new_project_info` authors),
  `build_date()` (ISO UTC; honours `SOURCE_DATE_EPOCH`),
  `identity_from_intent(model, issue_date=None)` (name from the intent on
  every route — prompt: the room's name; IFC: `IfcProject.Name` — plus the
  build date; number/client/building/address/organisation stay blank until
  the intent model carries them), `read_project_info(doc)` (decode the
  singleton), and
  **`stage_project_info(src, out, ident)`** = the certified MODIFY shape
  (matrix M3): ten `rvt.manipulate.set_param` edits on ONE existing element,
  ONE `commit_plans` (unit 0 re-emitted, everything else copied), then a
  semantic re-read of the written file proving the record decodes and every
  value landed. No new verbs, no new format work.
* **`src/rvt/frontdoor/build.py`** — stage **P** runs FIRST in `_run`
  (base → `_stages/stage_P_identity.rvt`); `src_base` (the identity-stamped
  base) is what L and W grow on, while `base_path` (the untouched pin) stays
  the P0 provenance gate's reference and the constructed-specimen source. So
  every downstream file — loaded chain, walls, equipment, shell, combined —
  inherits the identity from one edit. `BuildResult.project_info` carries
  the stage record; a failed stage degrades (named degradation, build
  continues on the pinned base — hard rule 1: a missing identity never
  costs the user the file). After the V gates, an executable coupling: if
  the P0 gate ever reports `deliverable` while the written Project Status is
  still `PROOF-ONLY`, a degradation names the stale default.
* **`src/rvt/frontdoor/manifest.py`** — `build.project_info` (identity,
  elem_id, before/after fields, commit report, mismatch) in
  `manifest.json`; one `project information (ProjectInfo 49504): …` line in
  `MANIFEST.md`.
* **Tests (`tests/test_frontdoor.py` §8, in the CI shard, no `samples/`):**
  `test_project_identity_maps_the_ten_builtin_params` (BIP mapping ==
  the ten `house_standard.PROJECT_INFO` fields, defaults, hard-rule-6
  author, `SOURCE_DATE_EPOCH`), `test_stage_p_edits_only_projectinfo_and_is_deterministic[2026|2025|2024]`
  (on each pinned base under its own release context: values land incl.
  number/client/building; `verify_manipulated` clean; **`reduce_law.element_diff(base, out)`:
  removed = added = ∅, modified == {49504: [102]}** — the ProjectInfo record
  is the ONLY pre-existing element whose bytes change; no
  `rev-revit`/`Genesis Base`/`GEN-0000` survives; two runs byte-identical),
  `test_e2e_prompt_output_carries_the_job_identity` (real `FD.author`
  prompt job: combined file decodes with the intent's name, `PROOF-ONLY`,
  today's date, `rvt-writer`; manifest json+md say so; validator 0 errors).
  `tests/test_famload_batch.py`: the `_stages` listing guard (#124, "one load
  intermediate, not one per family") now expects `stage_P_identity.rvt` too
  — the only cross-stream touch, one line, same intent.

## 3. Evidence

**Before / after, decoded from the combined deliverable** (`frontdoor author
--prompt "an electrical room with 6 panels for the Riverside Clinic project"`):

| field | before (main @ a5a853f) | after (this branch) |
|---|---|---|
| Project Name | `GENESIS Base` | `Electrical Room` (= manifest intent.summary.project) |
| Project Number | `GEN-0000` | `` |
| Client Name | `rev-revit genesis` | `` |
| Project Status | `Genesis Baseline` | `PROOF-ONLY` (= the manifest stamp) |
| Project Issue Date | `2026-08-03` | `2026-08-09` (build date, UTC) |
| Organization Name / Description | `rev-revit` / `genesis base document …` | `` / `` |
| Building Name | `Genesis Base` | `` |
| Author | `rvt-writer` | `rvt-writer` (= `identity.PRODUCT_AUTHOR_PLACEHOLDER`, untouched) |

**Per release / route** (real CLI, this VM, fresh clone + `cloud-setup.sh`):

| job | P ok | P seconds | validator (combined) | build seconds |
|---|---|---|---|---|
| `--prompt … 6 panels` (2026) | ✔ | 0.25 | VALID · 0 errors · 1 warning (base's known DataStorage decoder gap) | 7.7–8.1 |
| `--ifc inputs/ifc/electrical-room-2500a.ifc` (2026) | ✔ | 0.56* | VALID · 0 errors | 10.3 |
| `--prompt … --target-version 2025` | ✔ | 0.5* | VALID · 0 errors · 0 warnings | 8.3 |
| `--prompt … --target-version 2024` | ✔ | 0.5* | VALID · 0 errors · 0 warnings | 8.1 |
| bare unzip of `tekton-plugin.zip`, system `python3`, `_bootstrap.py go author --prompt …` | ✔ (`go.ready` true) | 0.41* | VALID · 0 errors | 6.9 wall |

`*` measured before the stage's whole-file `verify_manipulated` sweep was
dropped (see §4); the lean stage is 0.24–0.25 s on every base (re-checked
on the final code: `out/pi3`, P 0.24 s, VALID 0 errors).
`tools/rvt_validate.py` on all four outputs: `{'error': 0}` each.

**Latency (S-2026-08-09-g), same prompt, `--no-handoff`, 3 runs each,
`build.seconds`:** before 7.6 / 7.4 / 7.5 → after 7.7 / 7.7 / 8.1
(**+0.25 s**: open base 0.10 + ten set_param 0.001 + commit 0.05 + re-read
0.10). A first cut that also ran `verify_manipulated` cost 0.50 s; that
sweep (CRC of every member of every stream, ECC of two streams, stamps of
every unit-0 record) is repeated by every downstream stage's
`verify_written` and by the V gates on the files that actually ship, so it
was moved into the test instead of every job.

**Gates:** `tests/test_frontdoor.py` 46 passed / 2 skipped (the two
`needs_genesis` e2e cases, as in any fresh clone); `test_famload_batch.py` +
`test_validate_footer_blob.py` + `test_edit_own_release.py` green;
`test_manipulate.py test_reduce_law.py test_genesis_skeleton.py
test_verify_manipulated_release.py test_surface_perf.py test_coldstart.py`
69 passed / 31 skipped (samples-gated); `tools/sync_plugin.py` run →
`--check` "plugin in sync"; `plugin/scripts/validate_plugin.py` PASS (24
assertions); `tests/test_plugin_sync.py test_bootstrap.py test_coldstart.py
test_surface_perf.py` 26 passed / 4 skipped; `check_portable_paths.py` ok
(2718 → 2720 paths).

## 4. Findings / decisions

1. **First, not last.** Writing the identity once into the base and growing
   everything on it costs one small commit regardless of degrade mode
   (`--strict` would otherwise need one commit per emitted file, in place,
   on the largest files) and makes the DONE's "only ProjectInfo changes"
   assertion a plain `element_diff(base, stage_P)`.
2. **Status is a constant on purpose.** `PROOF-ONLY` is what the P0
   deliverability gate stamps on every output while G2/G3/G4 are open; the
   gate runs at the END of the build, the identity is written at the START,
   so the word is `PROJECT_STATUS_PROOF_ONLY` with a docstring tying it to
   `status_gate`. The day the gate can say `deliverable`, that default must
   follow it (filed below).
3. **Number / client / building are blank today** because
   `rvt.ifc.intent.IntentModel` carries only `project_name`; the spec schema
   (`spec/building.schema.json` `project.{number,buildingName,client,
   organisation,address,issueDate}`), `IfcProject.LongName/Phase` (steplite
   already serves them) and a prompt clause ("… for the Riverside Clinic
   project") are the natural sources. `ProjectIdentity` already has the
   fields (tested on the right BIPs); threading those sources through the
   intent model is a follow-up outside this issue's territory (filed below).
6. **`/simplify` pass (4 reviewers):** applied — `FIELD_PARAMS` as a plain
   field→BIP map, no unused `**known` seam, one clock (`_timed_stage`), the
   stage row via `_slim_stage`, the executable status coupling, honest
   wording about the second identity sink. Skipped with reasons — gating P
   on `opts.stages` (the hot-file CLI hard-codes `--stages FLWECV`, so a `P`
   letter would silently disable the feature; research probes go through
   `tools/ifc_intent.build_room`, which never runs P), literal BIP ints /
   lazy imports (+25 ms import only for non-building importers of
   `rvt.frontdoor.build`), a single-record re-read (~60 ms, more code), one
   `modify_element` instead of ten `set_param` (1 ms; `set-param` is the
   issue-mandated verb).
4. **Out of scope, recorded:** the pinned bases' `ProjectInformation` CFB
   *stream* (the PartAtom zip Revit shows in file properties, not the
   element) still carries the rst sample's residue — title
   `rstbasicsampleproject`, `Client Autodesk`, a `C:\Users\hansonje\…`
   member name. That is base-level identity residue = #19's territory
   (owner-machine + viewer-gated re-pin); `tools/genesis_assemble.py
   our_project_information_zip` is the existing regenerator.
5. The whole build is not byte-deterministic today (each run's `.rfa`s
   differ — #9); what this stream promises and tests is that stage P is a
   pure function of (base bytes, identity): two runs → identical bytes, and
   the only day-varying input, the issue date, honours `SOURCE_DATE_EPOCH`.

## 5. Follow-ups filed

* **#280** — thread project number / client / building / address /
  organisation from the spec `project` block, `IfcProject.LongName/Phase`
  and a prompt "for the … project" clause (plus `--project-*` flags on the
  hot-file CLI, its own tiny PR) into the intent model / `identity_from_intent`
  (`P2 ready area:frontdoor planned auto`, `Refs #148`).
* (noted on #19, not a new issue) the `ProjectInformation` stream residue.

## BRANCH STATE

* Branch `cam/148-projectinfo-identity` from `main @ a5a853f`; PR closes #148.
* Files written: `src/rvt/frontdoor/project_info.py` (NEW),
  `src/rvt/frontdoor/build.py` (stage P + `src_base` threading +
  `BuildResult.project_info`), `src/rvt/frontdoor/manifest.py`
  (`build.project_info` + MD line), `tests/test_frontdoor.py` (§8, 5 tests),
  `tests/test_famload_batch.py` (one expected-listing line), this record.
  Generated mirrors re-synced by `tools/sync_plugin.py`:
  `plugin/lib/src/rvt/frontdoor/{project_info,build,manifest}.py`.
* Not touched: `tools/frontdoor.py`, `src/rvt/frontdoor/base.py`,
  `src/rvt/versions/`, `docs/coverage/viewer-certified.json` (hot files);
  `tools/ifc_intent.py`, `tools/rvt_job.py` (other engineers' hunks);
  `src/rvt/manipulate.py` (reused as-is); `src/rvt/identity.py` (read-only).
* Shipped vs staged: everything above ships with the PR. Nothing STAGED for
  the viewer: the change is one AString-param modify on an element of a
  certified base (the M3 shape); no certification is claimed for it here.
* Scratch artefacts (not committed): `out/pi*`, `out/t_before_*`,
  `out/t_after*` builds used for the tables above.
