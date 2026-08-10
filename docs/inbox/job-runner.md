# job-runner — record + plugin-skill SOP for the FRONT DOOR (`tools/rvt_job.py`)

Stream: `job-runner` (workstream agent, 2026-08-03). Territory kept:
`tools/rvt_job.py`, `tests/test_job.py`, `experiments/job/*`,
`docs/writer/job-runner.md`, this file. No edits to `src/rvt/{mutate,
commit, manipulate, validate, identity, provenance, hosting, ...}.py`,
`tools/{spec_to_rvt, ifc_to_spec, seed_audit, provenance, rvt_validate}.py`
or existing tests — every needed behaviour was reachable by IMPORTING them;
the two source-level fixes this stream would want are written up as
proposed hooks below (exact diffs, for the orchestrator).

Full CLI reference: `docs/writer/job-runner.md`.

## What was built

`tools/rvt_job.py` — the deterministic, no-LLM runner with three entry
modes and hard gates (structural / `rvt.validate` 0-errors / identity) plus
the honest P0 base-provenance status, writing a deliverable manifest next
to every output:

* **(A) CREATE** `create --spec job.json [--base base.rvt] -o out.rvt` —
  seed audit (blocks on NOT-READY, proceeds on USABLE with the gap list) →
  the certified `spec_to_rvt.build` (walls / equipment / circuits), or the
  hosting-extended builder when an equipment item names a `hostWall`
  (`rvt.hosting`: SketchPlane + face-hosted instance) →
  `commit_new_elements` with OUR identity → gates → manifest.
* **(B) EDIT** `edit in.rvt --ops ops.json -o out.rvt` — every manipulate
  op (delete/rename/set-mark/set-level/set-param/move/retype) planned by
  `rvt.manipulate` and committed in ONE `commit_plans`; `add-instance` /
  `add-circuit` ops run as a `rvt.mutate` create stage on that result;
  identity scrubbed post-commit (commit_plans never touches BasicFileInfo)
  → gates → manifest.
* **(C) FROM-IFC** `from-ifc design.ifc [--base base.rvt] -o out.rvt` —
  `ifc_to_spec.extract` → `out.rvt.spec.json` → the (A) pipeline (the
  Claude-Design / Chicago-plenum flow).

## End-to-end proofs (`experiments/job/`) — all four VALIDATE 0 ERRORS

Every file passed `rvt.validate` (all layers) with **zero errors**, our
identity, and structural verification, and every manifest honestly stamps
`PROOF-ONLY, NOT-DELIVERABLE` because the base is the Autodesk MEP sample
(P0 gate G1 fails: 27,8xx sample-derived elements).

| proof | validator summary (verbatim from the run) |
|---|---|
| `create.rvt` (room-spec.json, 15 elements: 3 walls, 6 panels, 3 xfmrs, 3 auto circuits) | `PASS (errors=0 warnings=2)`; structural PASS; identity PASS |
| `create_hosted.rvt` (hostWall variant: 6 panels face-mounted on the new north wall via `rvt.hosting`, 21 elements) | `PASS (errors=0 warnings=2)`; structural PASS; identity PASS |
| `from_ifc.rvt` (hardened.ifc: 4 shell walls + 6 panels + 3 xfmrs, 13 elements) | `PASS (errors=0 warnings=2)`; structural PASS; identity PASS |
| `edit.rvt` (ops.json on rmebasicsampleproject: rename+mark panel 581483, move+rot90 transformer 624416 [origin x -49.435 → -44.435 ft, verified], delete air terminal 430715) | `PASS (errors=0 warnings=1)`; structural PASS (0 CRC / 0 ECC / 0 walker / 0 ISIZE mismatch, ElemTable 28132 → 28131, deleted absent, unit-0 ids == ElemTable); identity PASS |

The two persistent validator WARNINGS on every rme-derived file are
pre-existing and out of scope: the 1,171 Extensible-Storage
`FamilyInstance`s that fail schema decode (known corpus gap) and, on
create outputs, the reader-tolerated block A/C counter defect from
`commit.py`. Manifests + validation JSONs sit next to each file.

## Findings worth the orchestrator's attention

1. **Identity-scrub vs. validator conflict (real, cross-module).**
   `rvt.identity` mints a fresh Unique Document GUID while the minimal
   commit reuses the current History episode, so the validator's L2 check
   *BasicFileInfo GUID == History[0]* fires an **error** on every
   identity-scrubbed file — including the Autodesk-**accepted**
   `V30_own_identity_keep_author.rvt` and `V31_own_identity_own_author.rvt`
   (both validate `errors=1` right now), which falsifies the validator's
   "accepted ⇒ 0 errors" calibration claim. The runner resolves it in its
   own territory by handing the scrub the base's `History[0]` GUID
   (`identity={"document_guid": History[0]}`; post-commit `scrub_identity`
   in edit mode), giving our identity AND coherence — both gates pass.
   Source-level fixes are the hooks below.
2. **`--no-provenance` / degraded modules can never manufacture
   deliverability** — they degrade the status to NOT-DELIVERABLE by
   construction. Automation fails RED, never skips green.
3. **The structural gate had to be calibrated to the validator** —
   `verify_manipulated` reports the reader-tolerated `isize_identity`
   counter defect that every `commit_new_elements` output carries; treating
   it as a hard failure would fail every add-instance edit while the
   validator (correctly) rates it a warning. The gate now records it as a
   warning and lets `rvt.validate` own severity.

## Proposed hooks (exact diffs — NOT applied, other agents' territory)

**H1 · `src/rvt/identity.py` / commit path — identity scrub should record
a real save episode**, so a FRESH document GUID stays coherent instead of
the runner reusing `History[0]`:

```diff
--- a/src/rvt/commit.py  (identity block ~L177)
+++ b/src/rvt/commit.py
     try:
         from .identity import own_basic_file_info
+        from .streams_edit import record_save            # new episode row
         bfi = next((e for e in entries
                     if e.entry_type == "stream" and e.path == "BasicFileInfo"), None)
         if bfi is not None:
-            new_streams["BasicFileInfo"] = own_basic_file_info(
-                bfi.data, out_path=out_path, **(identity or {}))
+            guid = (identity or {}).get("document_guid") or str(uuid.uuid4())
+            # prepend a History episode with the SAME guid (+ DIT increment
+            # + BFI increments) so 'BFI GUID == History[0]' holds by
+            # construction: record_save(new_streams, episode_guid=guid)
+            record_save(new_streams, entries, episode_guid=guid)
+            new_streams["BasicFileInfo"] = own_basic_file_info(
+                bfi.data, out_path=out_path,
+                **({**(identity or {}), "document_guid": guid}))
```
(and `manipulate.commit_plans` should call the same identity+save block —
today it never touches BasicFileInfo, which is why the runner has to scrub
identity itself after an edit.)

**H2 · `src/rvt/validate.py` L1024 — re-calibrate the GUID check against
the V30/V31 acceptance evidence** (Autodesk accepts a fresh document GUID
that mismatches History[0]), i.e. downgrade to a warning like the other
reader-tolerated invariants:

```diff
--- a/src/rvt/validate.py
+++ b/src/rvt/validate.py
             if hist is not None and hist["entries"]:
                 if str(bfi["unique_document_guid"]).lower() != \
                         str(hist["entries"][0][0]).lower():
-                    rep.error(L_CONSISTENCY, "BasicFileInfo",
-                              "Unique Document GUID != History entry[0] GUID")
+                    # READER-TOLERATED (V30/V31 = fresh GUID after the
+                    # identity scrub, both TRANSLATED by Autodesk): a
+                    # warning by default, an error under strict.
+                    (rep.error if self.strict else rep.warn)(
+                        L_CONSISTENCY, "BasicFileInfo",
+                        "Unique Document GUID != History entry[0] GUID")
```
Either hook alone closes the loop; H1 is the more correct (a save that
changes the identity IS a save episode). The runner works today without
either.

## Plugin-skill SOP snippet — how `/revit-job` drives the front door

Paste into the plugin's `SKILL.md` (the skill owns prompt → spec; the runner
owns spec → file):

> ### `/revit-job` — from a user request to a Revit file
>
> 1. **Understand the request.** Two shapes:
>    * *"Build me X"* (a room, a lineup, a floor of equipment) → CREATE.
>    * *"In this file, do Y"* (user attached a `.rvt`) → EDIT.
>    * User attached an **IFC** exported from Claude Design → FROM-IFC.
> 2. **CREATE:** write a `spec.json` (metres, degrees) from the request —
>    `levels`, `walls` (start/end/height/thickness/type), `equipment`
>    (`kind` ∈ panelboard | switchboard | transformer | lightfixture;
>    `name`, `position`, `elevation`, `rotationDeg`, `typeName`, ratings in
>    `psets`; add `"hostWall": "<wall id>"` to wall-mount an item),
>    optional `circuits`. Show the user the spec summary (counts, positions)
>    and any assumption you made, then run:
>    `python tools/rvt_job.py create --spec spec.json [--base seed.rvt] -o out.rvt [--auto-circuits]`
>    (`--base` = the firm's own seed project when they have one; without it
>    the output is research-template-based and will be marked PROOF-ONLY.)
> 3. **EDIT:** translate each requested change into `ops.json` ops
>    (`delete{id,cascade}`, `rename{id,name}`, `set-mark{id,mark}`,
>    `set-level{id,elevation_ft|_m}`, `set-param{id,param_id,value}`,
>    `move{id,to|delta,rotation_deg}`, `retype{id,symbol}`,
>    `add-instance{name,symbol,level,position_ft,rotation_deg}`,
>    `add-circuit{panel,load,...}`). Resolve names → element ids first with
>    `python tools/rvt_edit.py FILE info` / `deps --id N`; confirm the id
>    list with the user before deleting; then run
>    `python tools/rvt_job.py edit in.rvt --ops ops.json -o out.rvt`.
>    A `delete` that has dependents fails LOUDLY (exit 2) with the
>    dependents/referrers list in the manifest — show it and ask whether
>    to re-run with `"cascade": true`.
> 4. **FROM-IFC:** harden the attached IFC (`harden_ifc.py`), then
>    `python tools/rvt_job.py from-ifc hardened.ifc [--base seed.rvt] -o out.rvt`
>    and show the user `out.rvt.spec.json` (what was extracted) before the
>    build claims.
> 5. **Read the manifest, not the console.** Open `out.rvt.manifest.json`
>    and report to the user in this order:
>    * **`status`** — say VERBATIM. If it is `PROOF-ONLY, NOT-DELIVERABLE`,
>      tell the user: *"This file is a working proof, not a delivered
>      product — it is built on an Autodesk sample base
>      (`gates.base_provenance.reason`). Do not hand it to a client."*
>      Never soften this.
>    * **Elements created / edits applied** (`elements.created`,
>      `edit.log`, `edit.deleted_ids`), and everything **skipped** —
>      `gates.seed_audit.gaps` (each gap has a plain-English `fix`) and
>      any `SKIP`/`WARN` lines in `build.log`.
>    * **Validation** — `gates.validation.errors` (must be 0) and the count
>      of warnings; offer `out.rvt.validation.json` on request.
>    * **What to check in Revit** (§ below).
> 6. **Non-zero exit** = a hard gate failed; the manifest `status` names
>    which (`FAILED (validation)` etc.). Do NOT retry blindly — surface
>    `gates.<gate>` (`top_findings` for validation, `issues` for identity,
>    the dependents report for a planning failure) and ask the user.
>
> **"Here is your file + what to check in Revit"** (say after a green run):
> the created elements sit at the spec origin `--offset-m` (default 10,
> −25 m world offset); confirm the level datums match the spec elevations;
> panelboards placed **free-standing** unless `hostWall` was set (then
> confirm each panel reports its wall as host after regeneration);
> transformers/switchboards are floor-standing at their spec z; circuits
> (if `--auto-circuits` or spec `circuits`) show in the panel's circuit
> list — panel **schedules** are not authored yet, only the circuits;
> any equipment kind reported `NEEDS-FAMILY` (e.g. trapeze hangers) is
> ABSENT and must be placed manually or added to the seed. If Revit
> reports a repair on open, capture the message — it is a certification
> signal for the writer team.

## CELL TABLE

| category | verb | status | proof file | notes |
|---|---|---|---|---|
| front-door / create | create (spec→rvt, walls+equip+circuits, seed audit, identity, validate, provenance) | PROVEN-viewer-pending | experiments/job/create.rvt | 15 elements from room-spec.json; VALIDATES 0 errors; identity ours; manifest PROOF-ONLY (sample base); certified spec_to_rvt recipe unchanged |
| front-door / create-hosted | create with wall-mounted equipment (rvt.hosting) | PROVEN-viewer-pending | experiments/job/create_hosted.rvt | 6 SketchPlanes + 6 face-hosted panels on the created north wall + 3 circuits (21 elements); VALIDATES 0 errors; exercises H2/H3 hosting through the front door |
| front-door / from-ifc | create from Claude-Design IFC (ifc_to_spec → spec → rvt) | PROVEN-viewer-pending | experiments/job/from_ifc.rvt | hardened.ifc → 13 elements, zero hand-authoring; VALIDATES 0 errors; derived spec saved as from_ifc.rvt.spec.json |
| front-door / edit | edit (rename + set-mark + move/rotate + delete, ONE manipulate commit, identity scrub) | PROVEN-viewer-pending | experiments/job/edit.rvt | panel 581483 renamed 'PP-1B-JOB' + Mark 'JOB-EDIT', xfmr 624416 +5 ft X & rot 90, air terminal 430715 deleted (verified re-read); VALIDATES 0 errors |
| front-door / edit-add | edit with add-instance stage (mutate + commit_new_elements on the manipulated file) | VALIDATES | tests/test_job.py::test_edit_mode_add_instance_stage (rstbasic, tmp) | proves the two-stage edit (manipulate commit then create stage) and that the structural gate defers the reader-tolerated counter defect to the validator |
| front-door / gates | fail-loud gate contract (seed NOT-READY blocks, dependents block, no partial writes, --no-provenance = NOT-DELIVERABLE) | VALIDATES | tests/test_job.py (6 tests) | test_edit_mode_fails_loudly_on_bad_target: exit 2 + FAILED manifest + nothing written |

BRANCH STATE: DONE — `tools/rvt_job.py` (create / edit / from-ifc + hard gates + honest deliverable manifest), `tests/test_job.py` (6/6 pass), `docs/writer/job-runner.md`, this record with the plugin SOP; four validated proof files under `experiments/job/`; identity-vs-validator conflict resolved in-territory with source-level hooks H1/H2 proposed above; full suite result recorded in the final report.

---

## eng #433 — 2026-08-10 — an abort is ONE `[rvt_job] FAILED (…)` line on stderr, never a traceback

Stream: `eng433` (engineer session under the tech-lead session; branch `cam/433-rvt-job-planning-one-line` from
`origin/main` @ f05db8b; fresh cloud clone, no `samples/`). Closes #433; Refs #424 (which found it), #267 / #396 (the
`--json` envelope), #111 (the `go edit` law it applies). Territory used: `tools/rvt_job.py` (the two planning handlers,
`_dispatch`'s last resort, one new 6-line helper `_failed`, the module docstring's OUTPUT MODES paragraph),
`tests/test_go_edit.py` (+2 tests, 1 extended), this section; mirrors regenerated by `tools/sync_plugin.py`
(`plugin/lib/tools/rvt_job.py`, `plugin/skills/tekton-{author,edit,native}/scripts/rvt_job.py`). Not touched:
`tools/frontdoor.py`, `src/rvt/frontdoor/edit.py`, `src/rvt/_logsink.py`, `tests/test_stagelog.py`, `tests/ci_shard.txt`
(no new test *file*: `tests/test_go_edit.py` is already in the shard, so no `ci_shard.d` drop-in either).

### What was built

* **One law for every abort of the ops/create door, in both output modes:** stderr carries exactly ONE
  `[rvt_job] FAILED (<stage>: <ExceptionType>: <message>)` line; the Python traceback — kept, it is the only diagnostic of
  a genuine engine fault — is *progress*, so it is printed on **stdout**, which is exactly the channel `--json` already
  streams into `<out>.log` (named in `output.log` of the ONE JSON and of the stub manifest on disk) and which the front
  door's `--rvt --edit` route already captures into `edit.log`. `tools/rvt_job.py::_failed(stage, exc)` (new, beside
  `_write_stub_manifest`) does the three moves — `traceback.print_exc(file=sys.stdout)`, the one stderr line, return the
  status string — and the three handlers that used to call bare `traceback.print_exc()` (stderr) now call it:
  `create_from_spec`'s planning `except` (`stage="planning"`, exit 2, stub manifest as before), `_cmd_edit`'s generic
  planning `except` (same), and **`_dispatch`'s last-resort `except Exception`** (`stage=args.mode`, exit 1). The third is
  judged the same law, not a different one: what reaches it in practice is an unusable input — `--ops`/`--spec` missing or
  not JSON, `--base` missing, the research template's sample absent on a bare surface — and `main()`'s `--json` stub for
  exactly that path has promised since #267 that *"the reason is the one line on stderr"*, which was false (a 626–1,237 B
  traceback) until now. The `DependentsError` branch already printed one line and no traceback; untouched. No status text,
  exit code, manifest key or gate changed; the happy path is byte-identical (table below).
* **Text mode, author's call (the issue left it open):** the same law, mode-free — no `_RUN["json"]` flag, no branch. A
  terminal user still sees everything (traceback on stdout above the `[rvt_job] manifest:` line, the one-liner on stderr);
  `2>&1` output only changes order. The alternative — keep the traceback on stderr in text mode — was rejected on evidence,
  not taste: the front door's `--rvt --edit` route drives this door **in text mode, in-process, with only stdout captured**
  (`src/rvt/frontdoor/edit.py:381-384`), so `frontdoor.py author --rvt G_ABPD_2025.rvt --edit "move 311 to 3,1,4.66"
  --json` (an edit the front door's own id check passes but the engine cannot plan: a Level has no InstanceInfo) put an
  **840 B traceback on the front door's stderr** on `main` — the very envelope #373/#424 promise as "one JSON, 0 B stderr".
  Mode-free, that route now gets the traceback inside `edit.log` (where its manifest already points) and 100 B / one line
  on stderr; a text-mode flag would have kept the 840 B *and* added the line.
* **The `_dispatch` stub now names the reason** (`/simplify` altitude lens, inside the same handler): `_failed` also
  remembers its status in `_RUN["status"]` (a third run-state key beside `log` / `manifest`, reset per `main()`), and
  `main()`'s `--json` stub for a run that died before any manifest of its own uses it — so an unusable `--ops`/`--spec`
  yields `status: "FAILED (edit: JSONDecodeError: …)"` in the ONE JSON itself instead of `"FAILED (exit 1) before anything
  was written; the reason is the one line on stderr"` (which sent a skill session to parse stderr — the opposite of #267's
  "nothing else to read or parse"). The generic text remains for the two aborts that print their own line and return
  without raising (input `.rvt` not found → exit 1; `ops.json` not a non-empty list → exit 2), where it is still true.
* **The `degradations` keeper (tech-lead comment on #433, from #436's review) — option taken: document now, fold filed as
  #440.** The module docstring's OUTPUT MODES paragraph now says a log that cannot be opened adds ONE `degradations` note to
  the printed object only (not to the on-disk manifest), and states the abort law. Folding the note into the on-disk
  manifest (#424's follow-up 3) is the right end state but cannot land from this territory alone: `tests/test_stagelog.py:231`
  compares printed-minus-`("exit_code", "degradations")` against the file and goes red the moment the file gains the key,
  and that test file is outside #433's fence. The whole patch, for #440 (≈8 lines, no behaviour change beyond the file
  gaining the key and the docstring losing its caveat):
  ```diff
  --- tools/rvt_job.py
  -_RUN: Dict[str, Any] = {"log": None, "manifest": None, "status": None}
  +_RUN: Dict[str, Any] = {"log": None, "manifest": None, "status": None, "degradations": []}
   def _record_manifest(manifest: dict) -> None:
       if _RUN["log"]:
           manifest["output"]["log"] = _RUN["log"]
  +    if _RUN["degradations"]:
  +        manifest["degradations"] = list(_RUN["degradations"])
       _RUN["manifest"] = manifest
   …main():
  -    _RUN.update(log=None, manifest=None, status=None)
  +    _RUN.update(log=None, manifest=None, status=None, degradations=[])
  -    notes: List[str] = []
  -    with stage_stdout(…, on_degrade=notes.append):
  +    with stage_stdout(…, on_degrade=_RUN["degradations"].append):
   …
  -    doc = dict(_RUN["manifest"], exit_code=rc)
  -    if notes:
  -        doc["degradations"] = notes
  +    doc = dict(_RUN["manifest"], exit_code=rc)
  --- tests/test_stagelog.py:231
  -        assert {k: v for k, v in doc.items() if k not in ("exit_code", "degradations")} == json.load(fh)
  +        assert {k: v for k, v in doc.items() if k != "exit_code"} == json.load(fh)
  ```
  The second keeper on that comment (retire the `rvt/frontdoor/stagelog.py` re-export shim) is filed as #441 — it touches
  `build.py` / `edit.py` / `router.py`, none of them this issue's.
* **Tests (`tests/test_go_edit.py`, bare `-I -S` plugin copy at a path with spaces, sample-free, already in the CI shard):**
  one shared assertion helper `_aborted(r, doc, out, code, status_prefix)` pins the abort shape — exit code, `go.stdout` /
  `go.exception` absent, `result.status` prefix, `output.written false` + nothing at `out`, **`r.stderr.splitlines() ==
  ["[rvt_job] " + result.status]` and `"Traceback"` not in stderr**, and the traceback present in `result.output.log` (kept,
  off stderr). `test_go_ops_door_unplannable_op_is_one_json_stub` (extended) runs it for the unplannable op (exit 2,
  `FAILED (planning: `, `999999999` in the status); new `test_go_create_door_unplannable_spec_is_one_json_stub` for a spec
  the builder cannot plan (a level with no `id`, 2026 base, via `tekton-author`'s copy — the one with `spec_to_rvt.py`
  beside it; exit 2); new `test_go_ops_door_unusable_input_is_one_line_too` for the `_dispatch` path (a non-JSON `--ops`:
  exit 1, `status` prefix `FAILED (edit: JSONDecodeError: `). +2 bare subprocesses ≈ +1.0 s of shard time (a `create`
  twin of the dispatch case was dropped in `/simplify` as the same code path for +0.4 s). The happy-path case
  `test_go_ops_door_result_is_the_manifest` (rc 0, `stderr == ""`, printed == on-disk minus `exit_code`, `output.log`
  named) is untouched and green.

### Evidence — before / after stderr bytes from a BARE surface

Bare = each build's `tekton-plugin.zip` (`tools/sync_plugin.py` from `origin/main` @ f05db8b = "before", from this head =
"after") unzipped under `/tmp/bare433/{before,after}`, system `/usr/local/bin/python3` 3.11.15 (no numpy), uid `nobody`
(`runuser -u nobody`), `env -u PYTHONPATH -u TEKTON_ROOT`, out dirs with spaces, interleaved before/after ×3, then the final head (after `/simplify`) ×3 more for the
"after" rows (all runs of a row identical except wall time; the two `_dispatch` rows are the only ones `/simplify` changed). Flow: `skills/tekton-edit/scripts/_bootstrap.py go rvt_job.py …` (`go` appends
`--json`); inputs `ops.json = {"ops":[{"op":"set-level","id":1351691,"elevation_ft":5}]}`,
`bad.json = [{"op":"set-level","id":999999999,"elevation_ft":5}]`,
`badspec.json = {"project":{"name":"x"},"levels":[{"name":"Level 1"}],"walls":[],"equipment":[]}`, `notjson.txt = {oops`.

| `go rvt_job.py …` (bare, nobody) | build | rc | stdout | **stderr** | stderr content | `result.status` | `output.log` | wall (3 runs) |
|---|---|---|---|---|---|---|---|---|
| `edit G_ABPD_2025.rvt --ops ops.json -o "happy out/edited.rvt"` (happy) | before | 0 | 10,585 B, ONE JSON | **0 B** | — | `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` | named, 18 lines | 1.73 / 1.27 / 1.22 s |
| same | after | 0 | 10,577 B, ONE JSON | **0 B** | — | identical; `edited.rvt` 598,016 B **`cmp`-identical to before's** | named, 18 lines | 1.44 / 1.19 / 1.19 s |
| `edit G_ABPD_2025.rvt --ops bad.json -o bad/never.rvt` (unplannable op) | before | 2 | 1,400 B, ONE JSON stub | **679 B, 10 lines** | `Traceback (most recent call last): … rvt.manipulate.ManipulationError: element 999999999 is a None, not a Level` | `FAILED (planning: ManipulationError: element 999999999 is a None, not a Level)` | named (2 lines) | 0.62 / 0.63 / 0.61 s |
| same | after | 2 | 1,394 B, ONE JSON stub | **89 B, 1 line** | `[rvt_job] FAILED (planning: ManipulationError: element 999999999 is a None, not a Level)` | identical | named; now also holds the traceback (2 → 12 lines) | 0.63 / 0.64 / 0.55 s |
| `create --spec badspec.json --base G_ABPD.rvt --allow-not-ready -o …` via **tekton-author**'s copy (unplannable spec) | before | 2 | 2,622 B, ONE JSON stub | **980 B, 14 lines** | `Traceback … KeyError: 'id'` | `FAILED (planning: KeyError: 'id')` | named | 0.50 / 0.49 / 0.50 s |
| same | after | 2 | 2,617 B, ONE JSON stub | **44 B, 1 line** | `[rvt_job] FAILED (planning: KeyError: 'id')` | identical | named, + traceback | 0.49 / 0.54 / 0.55 s |
| same `create` via tekton-edit's copy (no `spec_to_rvt.py` beside it — by design, creation is the author skill's) | before | 2 | 1,992 B stub | **640 B, 7 lines** | `Traceback … RuntimeError: spec_to_rvt unavailable: FileNotFoundError: …/tekton-edit/scripts/spec_to_rvt.py` | `FAILED (planning: RuntimeError: spec_to_rvt unavailable: …)` | named | 0.18 / 0.20 / 0.16 s |
| same | after | 2 | 1,984 B stub | **187 B, 1 line** | `[rvt_job] FAILED (planning: RuntimeError: spec_to_rvt unavailable: FileNotFoundError: [Errno 2] No such file or directory: '…/spec_to_rvt.py')` | identical | named, + traceback | 0.17 / 0.18 / 0.16 s |
| `edit … --ops notjson.txt -o nj/never.rvt` (`_dispatch` path) | before | 1 | 930 B, `main()`'s stub | **1,237 B, 23 lines** | `Traceback … json.decoder.JSONDecodeError: …` | `FAILED (exit 1) before anything was written; the reason is the one line on stderr` (it was not one line) | named | 0.60 / 0.57 / 0.51 s |
| same | after | 1 | 952 B, stub | **118 B, 1 line** | `[rvt_job] FAILED (edit: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1))` | **`FAILED (edit: JSONDecodeError: …)`** = the stderr line (final head; the first draft kept the generic text) | named, holds the traceback | 0.54 / 0.56 / 0.54 s |
| `edit … --ops missing.json -o no/never.rvt` (`_dispatch` path) | before | 1 | 930 B stub | **626 B, 11 lines** | `Traceback … FileNotFoundError: … 'missing.json'` | same stub | named | 0.54 / 0.56 / 0.51 s |
| same | after | 1 | 930 B stub | **96 B, 1 line** | `[rvt_job] FAILED (edit: FileNotFoundError: [Errno 2] No such file or directory: 'missing.json')` | **`FAILED (edit: FileNotFoundError: … 'missing.json')`** = the stderr line | named, holds the traceback | 0.54 / 0.55 / 0.54 s |

Every row, both builds: `go.stdout` absent, `go.exception` absent, `result.exit_code == rc`, `output.written false` on the
aborts and nothing written under the out dir but `<out>.log` + `<out>.manifest.json`. Wall time unchanged within noise on
every row (the fix removes a `print_exc` to one stream and adds it to another). The 8-byte stdout differences are the
build dir names (`before`/`after`) inside the echoed paths.

Repo (`.venv`, CPython 3.11.15, root), same inputs, `tools/rvt_job.py … --json` directly: unplannable op stderr **636 B →
89 B (1 line)**, `<out>.log` 2 → 12 lines (gains the traceback), ONE JSON 968 → 965 B (path), rc 2 → 2; create with the
bad spec on `G_ABPD.rvt` **880 B → 44 B**; text mode (`edit … --ops bad.json -o t/never.rvt`, no `--json`): rc 2, stderr
89 B = the one line (was the 636 B traceback), stdout 822 B = `[rvt_job] planning …` + the traceback + `[rvt_job]
manifest: …`. **Through the front door** (`tools/frontdoor.py author --rvt plugin/assets/genesis/G_ABPD_2025.rvt --edit
"move 311 to 3,1,4.66" --out X --json`, an edit its own resolver accepts but the engine cannot plan): before rc 3, ONE JSON
(`status FAILED (planning: ManipulationError: element has no InstanceInfo (not a placed instance))`, `errors []`,
`manifest` = `json, md, edit.log`), **stderr 840 B traceback**, `edit.log` 2 lines; after rc 3, the identical JSON, **stderr
100 B = the one `[rvt_job] FAILED (planning: …)` line**, `edit.log` 2 → 15 lines (progress + traceback + manifest line). (An
edit the resolver itself rejects — `set level 999999999 …` — never reaches the job: rc 3, `errors` = `edit not understood:
element id 999999999 does not exist in this file`, stderr 0 B on both builds.)

### Gates (final tree, after `/simplify` + `/verify`)

* `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_go_edit.py -q -rs` → **9 passed** (4.4 s; 7 pre-existing + 2
  new, 1 extended). With `tests/test_stagelog.py`: 17 passed, 1 skipped (the `chmod 0555` case as root).
* Neighbours (first draft, before `/simplify`; the final tree re-ran them inside the whole shard below):
  `tests/test_go_edit.py tests/test_stagelog.py tests/test_frontdoor.py tests/test_router.py tests/test_edit_own_release.py tests/test_job.py tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py tests/test_shard_list.py tests/test_plugin_validate.py`
  → **268 passed, 27 skipped** in 94 s — every skip pre-existing (`RVT_SKIP_LARGE` router cases, `samples/` absent for
  `test_job.py` ×4 and the front door's sample cases, no numpy-capable bare `python3` for `test_surface_perf.py` ×5, the
  `chmod 0555` cases as root).
* **The whole merged CI shard** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`):
  first draft → **1496 passed, 134 skipped, 3 xfailed** in 346 s; final tree → **1496 passed, 134 skipped, 3 xfailed** in 350 s (same counts: the test count did not change between drafts; every skip is a pre-existing `samples/`-, numpy-, `RVT_SKIP_LARGE`- or root-gated case).
* `tools/sync_plugin.py` (4 mirrors of `rvt_job.py` re-synced, deny-audit clean, identity scan == allowlist, zip 5,216 KB)
  then `--check` → "plugin in sync with source"; `plugin/scripts/validate_plugin.py` → PASS (25 assertions);
  `tools/dev/check_portable_paths.py` → ok (2897 paths). No new test file → no `tests/ci_shard.d/` drop-in.
* `/verify` (final tree): the bare table above (final zip, uid nobody, system `python3`): happy `go rvt_job.py edit` rc 0 /
  stderr 0 B / delivered 598,016 B `cmp`-identical to main's and `rvt_validate.py` → `VALID (no errors); warnings=0`; the
  four abort rows one line each; `go author --prompt "an electrical room with 6 panels" --out "out j1"` from the same bare
  unzip → `go.ready true` (`tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | …`), rc 0,
  stderr 0 B, 4.46 s, `result.status PROOF-ONLY (self-checks PASS …)`, `manifest` = `build.log, json, md`, `files` =
  `combined, families_dir`. Repo: `frontdoor.py author --rvt plugin/assets/genesis/G_ABPD_2025.rvt --edit "set level 311
  elevation to 5 ft" --out out/verify/e --json` → rc 0, stderr 0 B, `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`,
  `manifest` = `edit.log, json, md`, `rvt_validate.py G_ABPD_2025.edited.rvt` → `VALID (no errors); warnings=0`; the
  `"move 311 …"` planning-abort run as in the evidence paragraph (rc 3, one stderr line, traceback in `edit.log`).
  "Validates 0 errors", never "loads" (rule 4): nothing here is a certification claim; no format byte changed.
* Full suite NOT run (SUITE-COORDINATION).

### `/simplify` (4 lenses) — applied / skipped

Applied: `_failed`'s docstring cut from 6 lines of law-plus-history to 3 (history lives here); the module docstring's
`degradations` caveat moved out of a nested parenthesis into its own sentence; the three abort tests share one
`_aborted(…)` assertion helper instead of three pasted 5-assert blocks; the `create` twin of the `_dispatch` test dropped
(same code path, +0.4 s of shard for nothing new — efficiency lens); **`_RUN["status"]`** so `main()`'s pre-manifest stub
names the real reason (altitude lens: the JSON exists so nothing else needs parsing; the first draft's test had to assert
the reason on `r.stderr`, encoding the gap). Confirmed right as-is: "traceback follows `sys.stdout`" is the documented seam of
the shared sink (`_logsink.py`: capture is `sys.stdout`-level only) that all three quiet callers — `main()`'s `<out>.log`,
`run_edit`'s `edit.log`, `go()`'s buffer — agree on, whereas writing to `_RUN["log"]`'s handle would serve `--json` only;
three `except` sites calling one helper rather than one deep catch (the two planning sites hold a half-built manifest the
stub must carry and return exit 2, `_dispatch` is the context-free last resort returning 1); the `DependentsError` branch
left hand-rolled (custom status, deliberately no traceback — routing it through `_failed` needs two parameters for one
caller); `traceback` import still live (its one use is `_failed`). Skipped, with reason: folding `degradations` into the
on-disk manifest (altitude lens agrees it is the right end state) — needs `tests/test_stagelog.py`, outside the fence →
#440 with the patch above.

### Findings / follow-ups (outside this territory — filed, not done)

1. **#440** — fold the `degradations` note into the on-disk manifest (patch above; `tools/rvt_job.py` + `tests/test_stagelog.py:231`).
2. **#441** — retire the `rvt/frontdoor/stagelog.py` re-export shim (the tech-lead comment's second keeper; `build.py` /
   `edit.py` / `router.py` / `tests/test_stagelog.py`, one mechanical PR when nobody holds those files).
3. Not filed (observation, not yet task-shaped): the front door's `--rvt --edit --json` route still puts this door's ONE
   abort line on **its** stderr (100 B where its envelope says 0 B) because `run_edit` captures the in-process job's stdout
   only (`edit.py:381`). Whether the front door should also fold the job's stderr line into `edit.log` / its `errors` (it
   already carries the identical text in `status`) is a call for the next holder of `src/rvt/frontdoor/edit.py`; today's
   100 B one-liner replaces an 840 B traceback, so it is strictly better than `main` either way.
4. Not filed (by design, recorded so nobody re-discovers it): `go rvt_job.py create …` from the **tekton-edit** skill fails at
   planning with `spec_to_rvt unavailable` — that skill ships no `spec_to_rvt.py`; creation is `tekton-author`'s /
   `tekton-native`'s (`tools/sync_plugin.py:143-145`), and the skills route creation through `go author`, not this door.

## BRANCH STATE (eng #433)

* Branch `cam/433-rvt-job-planning-one-line` from `origin/main` @ f05db8b; PR closes #433.
* Files written: `tools/rvt_job.py` (`_failed` new; the two planning handlers + `_dispatch`'s call it; `_RUN["status"]` +
  its reset + the stub's use of it in `main()`; module docstring OUTPUT MODES), `tests/test_go_edit.py` (`_aborted` helper,
  1 test extended, 2 new), `docs/inbox/job-runner.md` (this section). Regenerated mirrors (`tools/sync_plugin.py`):
  `plugin/lib/tools/rvt_job.py`, `plugin/skills/tekton-{author,edit,native}/scripts/rvt_job.py`.
* Not touched: `tools/frontdoor.py`, `src/rvt/**`, `plugin/skills/*/SKILL.md`, `tests/test_stagelog.py`, `tests/ci_shard.txt`
  / `tests/ci_shard.d/`, `TRACKER.md`, `KNOWLEDGE.md`, the ledger.
* Gates: as listed above, all green; nothing staged for the viewer (no format bytes changed — the happy-path edit output is
  `cmp`-identical to `main`'s; no certification claim).
* Shipped vs staged: everything in this PR ships; nothing awaits a human. Follow-ups filed: #440, #441.
* Scratch (not committed): `/tmp/bare433/{before,after,work}` (the two unzipped builds + every run's stdout/stderr/log),
  the scratchpad's `before/`, `after/`, `bare.sh`, `main-wt/` (an `origin/main` worktree used only to build the "before" zip).
