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
