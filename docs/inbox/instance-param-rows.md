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

---

# 2026-08-09 — stream `eng289`: the five hand-rolled param-row upserts delegate to `manipulate` (issue #289)

Stream: `eng289` (engineer session under the tech-lead session; branch
`cam/289-param-row-helpers` from `main` @ 109345e). Closes #289. Refs #186
(the follow-up its /simplify pass filed), PG6. Written in this stream's
voice under its own header; §1–§5 above are `eng186`'s and untouched.

## A. What was built

* **`src/rvt/manipulate.py`** — `upsert_param_row(val, param_id, value, *, holder=None) -> note`,
  the raw-dict twin of `set_param` placed next to `param_row_edit`: a row
  present in the holder is modified in place (never duplicated); an absent
  one is inserted by applying `param_row_edit` with `set_path` — so a null
  holder pointer is AUTHORED, never a silent no-op. `_coerce_value(holder, value)`
  now carries the modify-path coercion for both `upsert_param_row` and
  `set_param` (text → str, double → float, Int/ElementId as given; a NEW
  row's `int()` stays in `param_row_edit`, on purpose). Nothing else in the
  #186 helpers changed. *Territory note:* the issue allowed `manipulate.py`
  "only if the pure helpers move"; they did not move, but without this one
  9-line function the "modify the present row" half of the shape would
  itself have been re-spelled at five sites — the reviewer may push back.
* **The five sites** now have one-line bodies (names, signatures, callers
  unchanged): `mep/devices.py _set_param_astring`, `mep/electrical_data.py` /
  `mep/views_spaces.py` / `mep/conduit.py _set_astring_param` →
  `upsert_param_row(obj, pid, value, holder="m_pParamValueSetAString")`;
  `mutate.Document._set_param(obj, set_name, pid, value)` →
  `upsert_param_row(obj, pid, value, holder=set_name)`. `devices`' vestigial
  `-> bool` (its one caller ignored it) and `mutate`'s `False`-on-null return
  are gone. **conduit's helper no longer drops a Mark on a null holder.**
* **Import direction — decided: lazy, not a leaf module.** `mep → manipulate`
  was already the direction (`electrical_data` at module level, the other
  three lazily inside functions — kept in each file's existing style).
  `mutate` imports `upsert_param_row` inside `_set_param`: `import rvt.mutate`
  measures 42 ms and `import rvt.manipulate` 86 ms (it pulls `encode`,
  `cfb_writer`, `commit`, `writer`); a module-level edge would put those
  ~45 ms on every read-only `import rvt.mutate` for two wall-height rows,
  and `manipulate → mutate` is itself lazy in two places, so a lazy edge the
  other way cannot cycle. Moving `PARAM_HOLDERS` / `param_row_edit` /
  `set_path` / `ManipulationError` into a new leaf module would be the
  structurally cleaner end state but a larger move of #186's "one place"
  for no behavioural gain — left as a follow-up candidate, not done here.
* **`tools/rvt_job.py`** `set-param` passes `holder=op.get("holder")` and
  logs it; **`src/rvt/frontdoor/edit.py`** vocabulary now reads
  `set-param{id,param_id,value,holder?} (holder = m_pParamValueSet{AString|Double|Int|ElementId}; only needed to type an ABSENT row, e.g. an ElementId -1 is a bare int)`.
* **`tests/test_manipulate.py`** (+7 cases, pinned base only, no samples/):
  `test_upsert_param_row_pure` (author null holder → insert into existing →
  modify in place with coercion, never duplicated; ElementId via `holder=`;
  untouched holders stay null; non-Element object raises);
  `test_mep_astring_helpers_author_a_null_holder[conduit|electrical_data|views_spaces|devices]`
  (each helper on `{"m_pParamValueSetAString": None}` authors the exact
  `PARAM_HOLDERS` shape, then modifies in place);
  `test_mutate_set_param_authors_a_null_double_holder`;
  `test_job_set_param_op_lands_an_elementid_row_via_holder` — drives
  `tools/rvt_job.py edit` (the ops.json door) on the prompt-built room with
  `{"op":"set-param","id":…,"param_id":-1002050,"value":-1,"holder":"m_pParamValueSetElementId"}`
  + a holder-less Int op: rc 0, hard gates passed, validation PASS, log
  names the holder, `verify_manipulated` healthy, rows re-read
  `ElementId == [{-1002050: -1}]`, `Int == [{-1001200: 3}]`, AString still
  null. Reuses `test_job._load_job` rather than a third copy of the loader.
* Plugin mirrors regenerated by `tools/sync_plugin.py` (11 files:
  `plugin/lib/src/rvt/{manipulate,mutate,frontdoor/edit,mep/*}.py`,
  `plugin/lib/tools/rvt_job.py`, the three `plugin/skills/*/scripts/rvt_job.py`).

## B. Grep proof — no upsert literal outside the one place

```
$ grep -rnE '"pid": *-1' src/rvt --include=*.py | grep -i 'paramvalueset\|m_paramSet'
src/rvt/manipulate.py:877:#: ``{"ptr_class": cls, "pid": -1, "value": {"m_paramSet": [{"m_paramId",      <- the PARAM_HOLDERS doc comment
$ grep -rnE '"ptr_class": *"ParamValueSet' src/rvt --include=*.py
(no hits — the only authored holder object is param_row_edit's `{"ptr_class": PARAM_HOLDERS[holder], "pid": -1, ...}` at manipulate.py:948)
```
Remaining `ParamValueSet…` class-name mentions under `src/rvt/` are readers
(`convert/rvt_to_ifc.py`, `render/wallgeom.py`, `inventory.py`,
`frontdoor/project_info.py`, `mep/electrical_data.py` getters) and
whole-element *constructors* (`famgen/skeleton.py` `param_set_*`,
`famgen/geometry.py _owned("ParamValueSetInt"|"…Double")`,
`frontdoor/standalone.py:587 _ptr("ParamValueSetDouble", {"m_paramSet": []})`),
which the issue explicitly allows.

## C. Byte-identity proof for existing callers (behaviour unchanged where the holder exists)

No mep *devices job* can run on the pinned base without `samples/` (it has
0 device symbols / 0 FamilyInstances / 0 wires or conduits to clone —
checked), so the proof is taken at the two levels that ARE reachable here:

1. **Helper level, real objects, real encoder.** `helper_bytecmp.py`
   (scratch instrument): the OLD bodies copied verbatim from `main`
   @109345e vs the NEW ones, each applied to a deep copy of a real Element
   object decoded from `plugin/assets/genesis/G_ABPD.rvt` and re-encoded
   with the file's own schema (`ObjectEncoder(decoder=doc.dec).encode_object`).
   Specimens: AString holder present (BasicWallType 600634, ProjectInfo
   49504) × {modify-present, insert-absent} × 4 mep helpers; AString holder
   null (Level 311/694/196629/245423) × insert × the 3 helpers that already
   authored (old conduit no-op'd there — that is the bug, not an identity
   case); Double holder (BasicWallType 600634, LeaderStyle 1471069 /
   1468024 / 285 / 296 / 23773) × {modify, insert} for `Document._set_param`.
   **39 matched old/new pairs, 0 byte differences, 0 dict differences**
   (row key order `{"m_value","m_paramId"}` vs `{"m_paramId","m_value"}` in
   old `mutate` is invisible to the schema-driven encoder, as expected).
2. **File level, the create path that reaches `Document._set_param`.**
   `frontdoor.py author --prompt "an electrical room with 6 panels"` writes
   walls through `create_wall → _set_param(…Double, BIP_WALL_HEIGHT…)`.
   Whole-file `cmp` is not a valid instrument (two builds on unmodified
   `main` already differ at byte 24661 — GUIDs/timestamps), so `reccmp.py`
   hashes the raw seq-101/102/103 record bytes (`u16 class_id + payload`)
   of every Wall / FamilyInstance / FamilySymbol / Level: main-vs-main =
   63 records, 0 differ (instrument valid); **main-vs-branch = 63 records,
   0 differ.**

## D. Evidence (branch head, fresh cloud clone, `.venv` from `scripts/cloud-setup.sh`)

| step | command | result |
|---|---|---|
| tests (stream-local) | `.venv/bin/python -m pytest tests/test_manipulate.py tests/test_mep_devices.py tests/test_mep_conduit.py tests/test_mep_electrical_data.py tests/test_mep_views_spaces.py tests/test_frontdoor.py tests/test_job.py -q -rs` | **77 passed, 81 skipped** (per file: manipulate 14p/5s, mep_devices 0p/18s, mep_conduit 0p/12s, mep_electrical_data 2p/23s, mep_views_spaces 0p/15s, frontdoor 59p/4s, job 2p/4s — every skip is `samples/` gated) |
| plugin | `tools/sync_plugin.py` (11 mirrored) → `--check`: "plugin in sync with source (deny-audit clean, identity scan == allowlist, assets verified)"; `plugin/scripts/validate_plugin.py`: PASS (25 assertions); `python3 tools/dev/check_portable_paths.py`: ok, 2768 paths | ✔ |
| /verify build | `frontdoor.py author --prompt "an electrical room with a 400A distribution panel" --out out/verify289/a --json` | exit 0, ok, PROOF-ONLY (self-checks PASS) |
| **the DONE op** | `rvt_job.py edit base_copy.rvt --ops ops.json -o e/edited.rvt` with `[{set-param -1002050=-1 holder=m_pParamValueSetElementId}, {set-param -1001200=2.5}, {set-mark M-9}]` | log `op1 set-param id=1472592 param -1002050 -> -1 (m_pParamValueSetElementId)`; structural PASS, **validation PASS errors=0** warnings=1 (the base's known DataStorage ES-blob gap), identity PASS, STATUS PROOF-ONLY (hard gates PASSED), 0.77 s; re-read: ElementId `[{-1002050: -1}]`, Double `[{-1001200: 2.5}]`, AString `[{Mark: "M-9"}]`, Int null; decode clean 681/681 |
| re-edit (rows present → modified in place) | same door on `e/edited.rvt` with ElementId 311 / Double 4.0 | validation PASS errors=0; rows `[{-1002050: 311}]` / `[{-1001200: 4.0}]`, still one each |
| NL door | `frontdoor.py author --rvt base_copy.rvt --edit "rename panel DP-1 to DPX; set mark of DP-1 to M-7"` | exit 0, hard gates PASSED, rows `[DPX, M-7]`, `rvt_validate` 0 errors |
| other releases | build with `--target-version 2025` / `2024`, then the same holder ops through `rvt_job.py edit` | both: hard gates PASSED, `rvt_validate` **0 errors / 0 warnings**, rows landed identically (read back under `host_release_context`) |
| provenance | `tools/provenance.py e/edited.rvt --baseline all --streams` | author `rvt-writer`, username blank, no identity violations |
| bare surface | unzip rebuilt `tekton-plugin.zip`, system `python3` 3.11, no repo on path: `go author --prompt …` → `tekton: READY`, exit 0, 2.1 s; `go rvt_job.py edit out/j1/prompt_room.rvt --ops ops.json -o out/j2/edited.rvt` (holder op + set-mark) → exit 0, hard gates PASSED, validation errors=0, 0.79 s; `go author --rvt … --edit "rename panel DP-1 to DPX; set mark of DP-1 to M-7"` → ok, hard gates PASSED, 0.78 s | ✔ |
| /simplify | 4-angle pass on the diff; applied: shared `_coerce_value`, dropped vestigial returns, tighter docstrings/vocabulary, reuse of `test_job._load_job` | skipped → follow-ups below |

Nothing here is certified or staged for the viewer (rule 4): the edit
shape is the #186 one already listed on #117; this branch adds no new
on-disk shape (byte-identical where holders exist; the ElementId/Int
holder authoring is #186's `param_row_edit`, now merely reachable from
ops.json).

## E. Follow-ups (searched first; filed as #311, `Refs #289`)

* Retire the four one-line `mep/*` AString wrappers (call
  `manipulate.upsert_param_row` at their ~8 call sites) and, if wanted, move
  the pure param-row helpers into a leaf module both `mutate` and
  `manipulate` import eagerly — outside this issue's "helper bodies only"
  territory.
* User-level holder aliases in the ops vocabulary (`holder: "ElementId"`
  instead of the internal field spelling), mapped in `manipulate` +
  `rvt_job` together.

## BRANCH STATE (eng289)

* Branch `cam/289-param-row-helpers` from `main` @ 109345e; PR opened ready (not draft) per the session-hosted regime (#302).
* Files: `src/rvt/manipulate.py`, `src/rvt/mutate.py`,
  `src/rvt/mep/{conduit,devices,electrical_data,views_spaces}.py`,
  `src/rvt/frontdoor/edit.py`, `tools/rvt_job.py`, `tests/test_manipulate.py`,
  `docs/inbox/instance-param-rows.md` (this section), regenerated mirrors
  under `plugin/lib/**` and `plugin/skills/{tekton-author,tekton-edit,tekton-native}/scripts/rvt_job.py`.
* Gates: stream-local 77 passed / 81 skipped; sync `--check` clean;
  `validate_plugin.py` PASS; portable paths ok; `rvt_validate` 0 errors on
  every cited output (2026/2025/2024); byte-identity 39/39 helper pairs +
  63/63 element records.
* Shipped in engine + plugin mirror; nothing staged; no hot file touched.
