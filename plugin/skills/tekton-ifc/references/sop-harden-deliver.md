# SOP — Validate, harden, and deliver an IFC for Revit (Workflow B)

Runs in the Cowork / claude.ai code-execution sandbox (a plain Linux
container with Python; NOT Windows, NOT Revit). Follow the numbered steps
in order; each states what "done" looks like. Terms: `SKILL.md` §0.

**One rule above all: the script's own `--help` and its printed output are
authoritative.** The command lines below are the intended interface. Run
`--help` on every script at step 2; if a flag differs, follow the script.
Never invent an output the script did not print. If a script is missing or
crashes, that is a blocker to report, not something to paper over.

## Part 1 — Set up

1. **Locate inputs and make an output folder.**
   ```bash
   cd skills/tekton-ifc
   mkdir -p out
   ls -l path/to/input.ifc            # the user's attachment; note its size
   ```
   *Done when:* you have the absolute path of the input `.ifc` and `out/`
   exists. If the user attached several files, process each through the
   whole SOP separately.
2. **Install the engine and read the CLIs.**
   ```bash
   pip install -r scripts/requirements.txt          # ifcopenshell + numpy; manylinux wheels, no compiler
   # (if requirements.txt is absent: pip install ifcopenshell numpy pytest)
   python -c "import ifcopenshell; print(ifcopenshell.version)"   # e.g. 0.8.x
   python scripts/validate_ifc.py --help
   python scripts/harden_ifc.py   --help
   python scripts/report.py       --help   # may not exist yet; if so, see step 8 for the manual report
   ```
   *Done when:* the import and the validate/harden `--help` succeed. **If `pip install` fails**
   (network egress blocked, no wheel): stop, tell the user validation
   cannot run in this sandbox, run any pure-text degraded mode the validator
   documents in its `--help`, and record "engine unavailable" as a blocker
   in the delivery report. This is the trigger for the project's MCP /
   local-runner escalation — do not fabricate results.

## Part 2 — Validate the input

3. **Run the validator.**
   ```bash
   python scripts/validate_ifc.py path/to/input.ifc --json out/validate.json
   ```
   Exit code `0` = analysed (the report is the verdict); `2` = not a
   readable IFC. Read the whole printed summary. Its parts (SKILL.md §5.2):
   - `schema : IFC4 errors=N warnings=M` — **N > 0 means the file is
     broken** and must be fixed before delivery.
   - `score : x/100` and `tier : …` — the verdict string: `INVALID` /
     `Tier 0 (v1-like)` / `Tier 1 (partial)` / `Tier 1`.
   - audit lines `geometry`, `placements`, `types`, `instancing`,
     `phantoms`, `spatial`, `psets`, `units` + `component scores`.
   - `top fixes (highest impact first)` — the ranked to-do list.
   - `element inventory` — one row per element with class/name/type/
     storey/geometry kind → predicted Revit result.
   **What success looks like** on the raw v1 sample
   `samples/design-ifc/bs-area-e-electrical-room.ifc`:
   `schema errors=0`, `score 31.4/100`, `Tier 0 (v1-like)`, geometry
   `11/11 tessellated`, placements `11/11 identity/origin`, `0 type
   objects`, `9 elements repeat identical geometry unshared`, top fixes =
   [extrusions, placements, types, instancing, storeys+space].
   *Done when:* you have written down N (schema errors), the score, the
   tier string, and the top fixes.
4. **Decide the path from the results.**
   | Result | Do |
   |---|---|
   | errors=0 AND tier is `Tier 1` (not partial) with no top fixes | Skip hardening (no-op). Go to Part 4. |
   | errors=0, tier `Tier 0`/`Tier 1 (partial)`, geometry/placement fixes listed, **and we authored the model in Design** | Re-export from Design with the v2 exporter (`references/sop-design-authoring.md`); do not deliver this file. Only the source can turn general triangle soup into extrusions or un-bake rotations. |
   | errors=0, foreign file (not our exporter), or fixes about types / phantoms / owner history / containment / exact-box geometry | Harden (Part 3) — it fixes exactly these, including converting provably-upright-box tessellation into extrusions with real placements. |
   | errors>0 | Harden (Part 3); if errors survive (step 7), the file must be re-authored — report the exact error lines and stop. |
   Write your decision (one sentence) — it goes in the report.
   *Done when:* the decision is written.

## Part 3 — Harden

5. **Run the hardener.**
   ```bash
   python scripts/harden_ifc.py path/to/input.ifc -o out/hardened.ifc --report out/harden.json
   #   optional flags:
   #     --keep-clearance-as-space   axis-aligned box clearances → IfcSpace .INTERNAL. instead of removal
   #     --no-remove-phantoms        leave suspected annotation solids alone
   #     --no-create-types           don't invent shared types for untyped identical elements
   #     --no-extrusions             don't convert provable boxes to IfcExtrudedAreaSolid
   ```
   Exit codes: `0` ok, `1` the output failed to reopen / has schema
   errors, `2` usage/IO. It prints a **before/after metric table**, an
   **actions log**, and `reopened OK, schema errors after = 0`. Product
   `GlobalId`s are preserved. The transforms it applies:
   - merge duplicate type objects with identical `(class, Name)` into one,
     rewiring `IfcRelDefinesByType`;
   - create ONE shared `IfcXxxType` per group of untyped elements sharing
     (class, predefined type, geometry signature) — six identical panels
     get one `IfcElectricDistributionBoardType`;
   - move psets that are byte-identical across every occurrence onto the
     type; repair empty owner-history person/organisation/application;
   - detect **phantom annotation solids** (clearance/swing/helper names
     and transparent helper geometry) and remove them (or → `IfcSpace`);
   - convert tessellation that is **provably an upright box** (rotation
     about Z allowed) into a real `IfcExtrudedAreaSolid` and move the
     element's placement to the box's base-centre — recovering an
     insertion point + orientation; anything not exactly a box is left
     tessellated;
   - contain orphan elements in the first storey; re-serialize a clean
     STEP file.
   **What success looks like** on the raw v1 sample: entities 329 → 727,
   size 83,780 → 81,767 bytes, `type_objects 0 → 4`,
   `tessellated_elements 11 → 1`, `extruded_solids 0 → 61`,
   `identity_placements 11 → 1`, score `31.4 → 89.0`, tier
   `Tier 0 → Tier 1 (partial)`; actions
   `products_converted_to_extrusions=10, boxes_converted=61,
   shared_types_created=4, owner_history_fields_repaired=2`.
   *Done when:* `out/hardened.ifc` and `out/harden.json` exist and the
   summary ends with `schema errors after = 0`.
6. **Read the actions log and `out/harden.json`.** Note every action count
   and anything reported as not fixed — they go in the report.
7. **Re-validate the hardened file — schema errors must be 0.**
   ```bash
   python scripts/validate_ifc.py out/hardened.ifc --json out/validate-after.json
   ```
   Compare with step 3: `errors` must be 0; the score should rise and the
   tier should improve; remaining top fixes must be source-only ones
   (non-box tessellation, spaces you can't infer) — those become "recommend
   re-authoring in Design" notes.
   *Done when:* `errors=0` on the hardened file. If errors remain, do NOT
   deliver; report the exact error lines and stop.

## Part 4 — Delivery report and the deliverable set

8. **Generate the report.**
   ```bash
   python scripts/report.py out/validate.json --compare out/harden.json -o out/delivery-report.md
   ```
   The report describes the FINAL file, `out/hardened.ifc`: its headline,
   element table and remaining fixes come from `out/validate-after.json`
   (found beside `harden.json` when it is that file's report; `--after
   out/validate-after.json` names it explicitly -- do that whenever the
   calls did not share one working directory), the before → after table from
   `harden.json`, and the first line names both files. (Omit `--compare` if you skipped hardening at
   step 4: the report then describes the validated input.) If
   `scripts/report.py` is absent from this checkout, write
   `out/delivery-report.md` yourself from the same real outputs: the
   `validate_ifc.py` summary of the FINAL file (verdict, element inventory
   with each class → its Revit category per `references/mep-class-map.md`),
   the `harden_ifc.py` before/after table and actions, the Tier 1 / Tier 2
   statement (SKILL.md §1), and the pre-filled Revit checklist (SKILL.md §6).
   Never invent a number.
   *Done when:* `out/delivery-report.md` exists and its category preview
   matches the classes in the inventory at step 3/7.
9. **Assemble the Tier 2 handoff table** (only if the user asked for native
   families/circuits): from `out/validate-after.json`, list per element —
   `Tag/Name | IFC class → target Revit category & suggested family | insertion point (m, from the IfcLocalPlacement) | typeName | key pset values`.
   Append it to the report or a sibling `out/tier2-handoff.md`.
   *Done when:* the table has one row per equipment product.
10. **Deliver in ONE message, in this order:**
    1. `out/hardened.ifc` (or the validated input if hardening was skipped)
       — "this is the file to Link into Revit".
    2. `out/delivery-report.md`.
    3. The shared-parameters guidance: the firm's `.txt` if they supplied
       one, else point to `references/shared-parameters-mapping.md` and
       explain that Link IFC auto-generates `<name>.ifc.sharedparameters.txt`.
    4. The Tier 2 handoff (if produced).
    5. In the message body, restate: the two-tier truth (SKILL.md §1) in
       two sentences, the Link-not-Open instruction (§6.1), and the
       IFC-is-version-agnostic / `.rvt`-is-not warning (§6.4).
    *Done when:* the user has all files plus the three restatements.

## Definition of done for Workflow B

- A validated `.ifc` with **zero ERRORS** (hardened if the input needed it).
- `out/delivery-report.md` (+ optional `tier2-handoff.md`) reflecting the
  real script output — no invented numbers.
- The user received the file, the report, the shared-parameters guidance,
  and the §1/§6.1/§6.4 restatements.
- Every remaining warning is either fixed or explicitly explained as
  source-only with the re-authoring recommendation.

## Common failures at each step

| Step | Failure | Action |
|---|---|---|
| 2 | `pip install ifcopenshell` fails | Sandbox egress/wheel blocker → degraded mode + report blocker; escalate per project MCP path. Never skip validation silently. |
| 3 | `SyntaxError` / cannot parse STEP | File is truncated or hand-edited. Ask for a fresh export. If from our exporter, re-run Design export (Part 5 of the design SOP). |
| 3 | Units flagged non-SI (feet, mm) | Foreign file. Harden may add unit assignments but cannot rescale coordinates safely — warn that dimensions may be wrong and re-authoring in metres is the real fix. |
| 5 | Harden crashes on an entity type | Note the entity, deliver the validated ORIGINAL if it had 0 errors, and report the crash as a tool bug (file a note for the maintainers). |
| 7 | Errors survive hardening | Do not deliver. Return the exact error lines and the re-authoring instruction. |
| 10 | User asks "where is the `.rvt`?" | Re-state SKILL.md §1 and §6.4: IFC is the deliverable; a `.rvt` is Tier 2 (Revit API / APS) and version-locked. |
