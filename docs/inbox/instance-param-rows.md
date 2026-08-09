# instance-param-rows — `set_param` upserts absent param rows on our own output (issue #186)

Stream: `eng186` (engineer session under the tech-lead session; branch
`cam/186-instance-param-rows`). Closes #186 (and the folded-in DONE of its
duplicate #215). Refs #108 (requirements sweep wave 1), #117 (next EDIT
viewer batch — the new edit shape is LISTED there, not certified), PG6
(engine depth where users hit walls), PG1 (a hole inside a claimed
`prompt+rvt -> rvt` WORKS cell). Precedents: `docs/inbox/perm-matrix.md`
follow-up 4 ("Instance param rows on created instances — the demo5
finding"), `docs/inbox/mep-devices.md` ("AString Mark holder created for a
family that had none", `rvt.mep.devices._set_param_astring`).

## 1. Problem (measured on a fresh cloud clone, no samples/)

```
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with a 400A distribution panel" --out out/a --json   # exit 0, 3.5 s
.venv/bin/python tools/frontdoor.py author --rvt out/a/prompt_room.rvt --edit "rename panel DP-1 to DPX; set mark of DP-1 to M-7" --out out/b0 --json
  -> exit 3, ok=false, "FAILED (planning: ManipulationError: element 1472592: parameter -1140078 not present in any param set (available: []))"
```

The placed panel (FamilyInstance **1472592**, category -2001040, symbol
1472586) decodes with **all four** Element param holders null
(`m_pParamValueSetDouble/Int/AString/ElementId = None`) and an empty
`m_pInstParams.m_params`; its FamilySymbol is the same. `manipulate.set_param`
(`find_param` → raise) could only MODIFY an existing row, so the two most
natural follow-up edits — Panel Name (-1140078) and Mark (-1001203) — had
nothing to modify. `move` / `rotate` / `delete` on the same file were fine
(1.3 s, hard gates PASSED).

## 2. What was built

* **`src/rvt/manipulate.py`**
  * `PARAM_HOLDERS` — the four holder fields → owned-pointer class. Shape
    learned from rows that DO exist on the pinned composed 2026 base's own
    elements (BasicWallType 600634 AString, DBViewPlan 245443 Int,
    LeaderStyle 1471069 Double, Viewer 1457029 ElementId):
    `{"ptr_class": "ParamValueSet<Kind>", "pid": -1, "value": {"m_paramSet": [{"m_paramId", "m_value"}, ...]}}`
    — identical to what `genesis.skeleton.param_set_*` and
    `mep.devices._set_param_astring` already author. Zero donor bytes: the
    row and holder are authored dicts encoded by the file's own schema.
  * `KNOWN_PARAM_HOLDERS` (id → holder) + `param_holder_for(param_id, value)`
    — which holder a NEW row belongs to: the known text built-ins (Mark,
    Panel Name, door number, type name, room/space name + number) are
    AString whatever python type the value arrives as (`set-param … value 7`
    from JSON is still text); otherwise str → AString, float → Double,
    bool/int → Int (an ElementId row is passed explicitly with `holder=`, a
    bare int being indistinguishable). Replaces the dead `_param_holder_for`.
  * `param_row_edit(val, param_id, value, holder=None) -> (path, new, note)`
    — the ONE pure place the row/holder shape is authored: either the
    holder's row list with the row appended, or the whole holder object
    when the pointer is null; usable with `set_path` on raw dicts at create
    time (the `mep/*` `_set_astring_param` copies can migrate onto it —
    follow-up #289) or through `modify_element` on committed elements.
  * `set_param(..., holder=None)` is now an **upsert**: existing row (any
    holder or `m_pInstParams`) → modified in place as before, never
    duplicated (AString/Double rows now coerce the value to str/float on
    the modify path too, so a Mark of `7` no longer hands the encoder an
    int); absent row → `param_row_edit` applied via `modify_element`.
    Objects that do not declare the holder field still raise loudly, naming
    the element and class. Each insert plan carries a note
    (`authored ParamValueSetAString holder for absent parameter -1140078` /
    `inserted parameter -1001203 row into existing m_pParamValueSetAString`)
    that lands in the job manifest.
  * `modify_element` records `copy.deepcopy(new)` in its `FieldChange`, so
    a second insert on the same element no longer aliases the first plan's
    `after` in the manifest (cosmetic, found while reading the manifest of
    the two-op edit).
* **`tests/test_manipulate.py`** — module fixture `prompt_room` builds
  "an electrical room with a 400A distribution panel" on the pinned plugin
  base (`plugin/assets/genesis/G_ABPD.rvt`, no samples/) and asserts the
  four-holders-null precondition; `renamed_room` applies rename + set-mark
  in one session and commits once (shared by two tests). Four new tests:
  insert-when-absent for the AString holder (holder authored then row
  appended, first plan's `after` not aliased by the second,
  `verify_manipulated` healthy, re-read rows == `[Panel Name DPX, Mark M-7]`,
  `inventory.element_name == "DPX"`, decode clean 100 %), insert-when-absent
  for a Double holder **and** an ElementId holder via `holder=` (Int holder
  stays null), modify-when-present without duplicating (re-edit → `DPY` /
  Mark `8` passed as an int lands as `"8"`, still two rows, no authoring
  note), and the pure `param_holder_for` / `param_row_edit` table + refusals.
* **`tests/test_frontdoor.py`** — `test_e2e_rename_and_set_mark_on_our_own_output`
  (reuses the existing `identity_job` module fixture, so no extra build):
  the DONE sentence through `FD.author(rvt=..., edit=...)` → ok, ops
  `[rename, set-mark]`, hard gates passed, `editables` shows the instance
  renamed to `DPX`, rows == `[DPX, M-7]`. Runs in the CI shard
  (`tests/test_frontdoor.py` is listed in `tests/ci_shard.txt`).
* `tools/rvt_edit.py` / `tools/rvt_job.py` needed no change (they already
  call `rename_panel` / `set_mark` / `set_param`); `tools/ifc_intent.py`
  untouched (#277 territory).

## 3. Evidence (branch head, fresh clone, `.venv` from `scripts/cloud-setup.sh`)

| step | command | result |
|---|---|---|
| build | `frontdoor.py author --prompt "an electrical room with a 400A distribution panel" --out out/a --json` | exit 0, ok, PROOF-ONLY (self-checks PASS), 3.5 s |
| **the DONE edit** | `frontdoor.py author --rvt out/a/prompt_room.rvt --edit "rename panel DP-1 to DPX; set mark of DP-1 to M-7" --out out/b --json` | **exit 0, ok=true, "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)", 1.4 s** (before: exit 3 in 0.3 s; a working `move` was 1.3 s → no regression) |
| gates in `out/b/prompt_room.edited.rvt.manifest.json` | structural PASS (`verify_manipulated`: crc/ecc/walker/isize 0, stamps ok, ElemTable 3125 == headers, edited 1472592 seq 101/102/103 clean), validation PASS, identity, base_provenance | `hard_gates_passed: true` |
| validator | `tools/rvt_validate.py out/b/prompt_room.edited.rvt --json out/b/v.json` | **0 errors** / 1 warning (the base's pre-existing DataStorage ES-blob decoder gap) / 2 info |
| re-read | `Document.from_file(out/b/...)`: `editables()["instances"] == [{"id": 1472592, "name": "DPX", ...}]`; `m_pParamValueSetAString == {"ptr_class": "ParamValueSetAString", "pid": -1, "value": {"m_paramSet": [{"m_paramId": -1140078, "m_value": "DPX"}, {"m_paramId": -1001203, "m_value": "M-7"}]}}`; decode clean 655/655 bytes; the edited element re-encodes byte-exact (EditSession `_orig_bytes_check`) | ✔ |
| rows-already-exist case | `frontdoor.py author --rvt out/b/prompt_room.edited.rvt --edit "rename panel DPX to DPY; set mark of DPX to M-8" --out out/c` | exit 0, hard gates PASSED, rows → `[DPY, M-8]` (still 2, modified in place), validator 0 errors |
| other edits, original file | `move DP-1 by 2,0` / `rotate DP-1 by 90` / `delete DP-1` | each exit 0, hard gates PASSED |
| other edits, edited file | `move DPX by 2,0` / `rotate DPX by 90` / `delete DPX` on `out/b/...` | each exit 0, hard gates PASSED |
| other releases | same build+edit with `--target-version 2025` and `2024` | build exit 0; edit exit 0, hard gates PASSED, 1.5 s / 1.4 s; validator 0 errors / 0 warnings on both |
| tests | `.venv/bin/python -m pytest tests/test_manipulate.py tests/test_frontdoor.py -q` | **52 passed, 9 skipped** (the 9 are the sample-dependent cases), 14.1 s; `tests/test_plugin_sync.py` 7 passed; `tests/test_mep_views_spaces.py` (a `set_param` caller) 15 skipped — sample-gated |
| plugin | `tools/sync_plugin.py` (1 file mirrored: `plugin/lib/src/rvt/manipulate.py`), `--check` in sync, `plugin/scripts/validate_plugin.py` PASS (24 assertions), `tools/dev/check_portable_paths.py` ok (2740 paths) | ✔ |
| provenance | `tools/provenance.py out/verify/b/prompt_room.edited.rvt --baseline all --streams --json …` | identity ok: author/client `rvt-writer`, username blank, violations `[]`, advisories `[]` |
| `/verify` — bare unzip of the rebuilt `tekton-plugin.zip`, system `python3` 3.11, no repo on the path | `go author --prompt "an electrical room with a 400A distribution panel"` → preflight `tekton: READY`, exit 0, 3.2 s; `go edit out/j1/prompt_room.rvt rename-panel --id 1472592 --name DPX -o … --json` → ok, structural PASS + validation PASS (0 errors), 0.77 s; `go edit … set-mark --id 1472592 --mark M-7` on that → ok, 0 errors, 0.76 s; `go author --rvt out/j1/prompt_room.rvt --edit "rename panel DP-1 to DPX; set mark of DP-1 to M-7"` → ok, hard gates PASSED, 1.2 s | ✔ (before this branch all three edit calls exited non-zero with the ManipulationError) |
| `/simplify` | 4-angle review of the diff; applied: `_param_rows` + pure `param_row_edit` extraction, `KNOWN_PARAM_HOLDERS` table instead of an AString-only set, table-driven coercion on both branches, shared `renamed_room` fixture, `holder=` exercised, self-referential assert dropped | skipped as out of territory → follow-up **#289**: migrate `mep/*` `_set_astring_param` copies (incl. `mep/conduit.py`'s silent no-op on a null holder) onto `param_row_edit`; plumb `op["holder"]` through `tools/rvt_job.py` `set-param` |

Name resolution note for users/skills: clauses in one `--edit` sentence
resolve names against the file **as opened**, so the second clause refers
to the panel by its *old* name (`set mark of DP-1 ...`, not `of DPX`) — the
existing front-door behaviour, unchanged here.

## 4. Viewer status (rule 4)

Nothing here is certified. The edit shape "FamilyInstance whose AString
holder was authored by `set_param` (Panel Name + Mark rows) on the composed
2026/2025/2024 bases" is **listed for the next EDIT viewer batch on #117**
(comment posted there with what to stage: base = the prompt room built on
the pinned base, probe = the same file after the DONE edit, control = a
byte-identical copy of the base); a session STAGES, a human uploads.

## 5. Findings / open questions

* Every Element-derived object on our bases declares the four holder
  fields (Level, ProjectInfo, views… all have them, null or not), so the
  "no holder field" refusal is a guard for exotic classes, not a path any
  current edit takes.
* `editables()` rows carry `name` (Panel Name wins once present) but not the
  Mark; resolving an instance *by mark* in a later edit sentence works only
  when the instance has no panel/family name. Small front-door follow-up if
  wanted (`src/rvt/frontdoor/edit.py`, not this stream's territory).
* `tests/test_manipulate.py` is not in `tests/ci_shard.txt`; its new cases
  need only the pinned base (5 s). The front-door case covers the DONE in
  CI; adding the file to the shard is a one-line follow-up for whoever owns
  the shard list.

## BRANCH STATE

* Branch `cam/186-instance-param-rows` from `main` @ a5dd53b.
* Files: `src/rvt/manipulate.py`, `plugin/lib/src/rvt/manipulate.py`
  (regenerated mirror), `tests/test_manipulate.py`, `tests/test_frontdoor.py`
  (+1 case), `docs/inbox/instance-param-rows.md` (this record).
* Gates: stream-local tests 52 passed / 9 skipped; plugin sync `--check`
  clean; `validate_plugin.py` PASS; portable paths ok; `rvt_validate.py`
  0 errors on every cited output (2026 / 2025 / 2024, first edit and
  re-edit).
* Shipped in the engine + plugin mirror; nothing staged for the viewer by
  this branch (listed on #117); no hot file touched.
