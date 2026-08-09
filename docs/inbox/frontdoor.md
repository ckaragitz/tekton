# inbox — frontdoor (THE MULTI-SURFACE FRONT DOOR: one entrypoint, three inputs)

Stream: **frontdoor** (2026-08-04). Charter: build `src/rvt/frontdoor/` +
`tools/frontdoor.py` — ONE `author` entrypoint that authors our `.rvt` from
ANY of THREE inputs (a natural-language PROMPT, an authored IFC, or an
existing `.rvt` + an edit), every route landing in the SAME intent model, the
SAME build step (intent → our `.rvt` ON THE CERTIFIED GENESIS BASE, never an
Autodesk sample) and the SAME deliverable manifest. Territory touched ONLY:
`src/rvt/frontdoor/**` (new), `tools/frontdoor.py` (new),
`tests/test_frontdoor.py` (new), `experiments/frontdoor/**` (new), this
file. NO existing `src/rvt/*.py` or `tools/*` edited — `rvt.ifc.intent`,
`tools/ifc_intent.py` (the ifc-room build stages), `tools/rvt_job.py` (the
certified edit pipeline + gates), `rvt.mutate` / `rvt.manipulate` /
`rvt.famgen` / `rvt.validate` are all IMPORTED (as modules), never modified.

## Result in one screen

* **THE THREE ROUTES WORK, END TO END, ON THE PINNED GENESIS BASE.**
  `frontdoor author --prompt | --ifc | --rvt … --edit` all resolve into
  `rvt.ifc.intent.IntentModel` (spec v2) and build on **`G_ABPD`**
  (sha256-pinned `84173b89…`, ORCHESTRATOR VERDICTS #24; an Autodesk sample
  base is REFUSED; `--base` overrides on the user's authority; the specimen
  ancestor `R5` is pinned too). The four-registry family LOADER, the wall
  add path and the instance placement path — all built on ZA_deep by the
  ifc-room stream — work UNCHANGED on the composed genesis base `G_ABPD`
  (first time anything was authored on the composition; 3,102 → 3,241
  ElemTable rows, watermark 1,472,524 → 1,472,952).
* **THE WORKED PROMPT** — `an electrical room 30x20 ft rated for 2500 A
  service with a main switchboard, two 400 A distribution panels and four
  lighting panels` — resolves with **NO external model call and NO API
  key** (rules-first deterministic parser) into MSB (house switchboard) +
  DP-1/DP-2 (Eaton PRL2X 400 A facts) + LP-1..4, a 9.144 × 6.096 m 4-wall
  room, a feeder tree (MSB → DPs, LPs round-robin on the DPs, UTILITY
  service) → **7 generated families LOADED + 4 walls + 7 placed instances**,
  combined file **validator VALID · 0 errors · four registries coherent ·
  identity PASS**, STAMPED `PROOF-ONLY: walls+families combination
  unverified` (the open bug), in ~14 s. Coverage report: 5 understood
  clauses, 0 ignored words, 0 not-built, 13 flagged defaults.
* **THE PRIMARY PROMPT PATH IS THE DOCUMENTED HANDOFF**: every prompt job
  ALSO emits `scene-brief.json` + `HANDOFF.md` + `PROMPT_TO_IFC.md` — the
  compact scene brief (equipment as `userData.ifc` blocks carrying OUR
  tagging-contract Psets, `stage.ifcMeta`, the room's wall list, the feeder
  tree) any AI surface executes with Three.js exactly per the user's
  three-d-stage method; the exported IFC re-enters through `--ifc`.
  `--handoff-only` skips the fallback build.
* **THE ELECTRICAL-ROOM IFC** (`inputs/ifc/electrical-room-2500a.ifc`) end
  to end through the front door: 12 products resolved (real placements +
  Pset join key), 4 walls + 2 doors, **8 families (7 catalog + the honest
  house switchboard) LOADED + 8 instances**, combined file **VALID · 0
  errors · coherent · identity PASS**; the 4 unmapped kinds (TMGB ground
  bus, conduit run, service entrance, hangers) + the CIRCUITS blocker
  recorded as named degradations (never faked); ~16 s.
* **THE `--rvt` ROUND TRIP**: the room we just authored is EDITABLE through
  the same door — `"move DP-1 to 3,1,4.66; delete LP-4 with cascade; set
  level L1 - Ground Floor elevation to 0.5 ft"` (names / tags / level names
  resolved to ids from the file) → the job runner's certified edit
  pipeline (rvt.manipulate, ONE commit) → structural + validation +
  identity + provenance gates PASS; DP-1 moved, LP-4 gone (6 instances
  remain), the level edited; 1.1 s. `rename`/`set-mark` on OUR instances
  correctly FAIL LOUD (specimen-scaffolded clones carry no instance
  parameter rows — the ifc-room record's named limitation #3) and the
  manifest's CRUD block advertises only what works (move / retype /
  delete) with the reason for the rest.
* **THE OPEN BUG IS DETECTED AND DEGRADED, NEVER SILENTLY SHIPPED.**
  `combination_check()` sees created WALLS + LOADED FAMILY DOCUMENTS
  together (docs/inbox/genesis-audit.md verdict #24) → default = ONE
  combined file whose manifest is STAMPED `PROOF-ONLY: walls+families
  combination unverified`; `--strict` = TWO coordinated files (`-shell.rvt`
  = the 4 walls on the base; `-equipment.rvt` = the 7 loaded families +
  their instances) — each individually **VALID · 0 errors · coherent ·
  identity PASS** and each a viewer-certified SHAPE (walls-only /
  load+placement). Walls-only or families-only intents are `single` (no
  stamp). The manifest names the bug, the mode, the reason, and how to get
  the other mode.
* **`tests/test_frontdoor.py` — 31 passed** (29 s; two are end-to-end
  builds on the real genesis base: the default stamped build, and the
  strict split + a `--rvt` edit chained onto it). Full suite: see BRANCH
  STATE.

## The requirement, point by point

| requirement | delivered |
|---|---|
| ONE entrypoint, THREE inputs | `rvt.frontdoor.author(prompt=… \| ifc=… \| rvt=…, edit=…)` / `tools/frontdoor.py author --prompt \| --ifc \| --rvt … --edit`; exactly one input enforced |
| `--ifc` → `rvt.ifc.intent` (import, not edit) | `frontdoor.intent.intent_from_ifc` = `I.resolve_intent` (pure delegation) |
| `--prompt` primary = documented Three.js/IFC handoff | `prompt_intent.scene_brief` / `write_handoff` + `src/rvt/frontdoor/PROMPT_TO_IFC.md` (coordinates, tagging contract, exporter recipe, what the front door reads back, checklist) |
| `--prompt` fallback = deterministic rules-first parser, no API key, coverage honesty | `prompt_intent.parse_prompt` / `layout_room` / `prompt_to_intent` → the SAME `IntentModel` (contracts via the SAME `normalize_contract`, mapping via the SAME `plan_families`); `PromptCoverage` = understood / ignored words / not-built / defaults / warnings; rides in the manifest |
| `--rvt` → `Document.from_file` + the edit CLI's operations | `edit.parse_edit_spec` (ops.json / inline JSON / edit sentences → the job runner's ops vocabulary; names→ids from the file) → `run_edit` = `tools/rvt_job.py edit` (rvt.manipulate delete/modify/move/retype/cascade + gates), unchanged |
| build on the CERTIFIED GENESIS BASE, hash-pinned, `--base` overrides, NEVER a sample | `base.py` + `assets/genesis_base.json` (G_ABPD pin + certification citation + residue disclosure + specimen ancestor R5 pin; resolution: `--base` → `$RVT_GENESIS_BASE` → pinned repo path → bundled copy; sample refused; pin mismatch refused) |
| reuse the ifc-room build code | `build.py` loads `tools/ifc_intent.py` as a module and drives `stage_families / stage_load / SpecimenSet / stage_walls / stage_equipment / stage_circuits` + its gates — the only new logic is the degrade orchestration |
| detect walls+families, `--strict` = two files, default = stamp; never silent | `intent.combination_check` → `CombinationVerdict{mode: single \| split-strict \| stamp-proof-only, stamp, files, reason}`; `build_intent` executes it; the manifest carries the stamp + `open_bug_text` |
| every route emits the .rvt + a deliverable MANIFEST (route, intent, elements, families, base + certification, validator, stamps, CRUD) | `manifest.py` → `manifest.json` + `MANIFEST.md`: route, inputs, base (pin, certification, warnings), intent summary + json path, build (verdict, files w/ sha256, stages, families, elements created, degradations, circuits blocker, per-file self-checks, deliverability gate), `crud` (per-element move/retype/delete sentences + CLI + ops; `not_available` reasons; layer ops), `coverage_matrix` cells, `honesty` (self-checks vs Autodesk tier, LOAD vs RENDER, PROOF-ONLY stamps, release) |
| both worked examples under experiments/frontdoor/ | `prompt-electrical-room/` (+ `-strict/`), `ifc-electrical-room-2500a/`, plus `rvt-edit-room/` (the round trip); `experiments/frontdoor/README.md` indexes them |
| PACKAGING (code inside the plugin, skill + reference docs, sync_plugin) | engine flows via the existing `src/rvt/**` → `plugin/lib/src/rvt/**` rule (already synced by a packager pass, 12:50); skill body drafted at `src/rvt/frontdoor/SKILL.frontdoor.md` + `assets/README.md` for promotion; the `tools/frontdoor.py` file_maps line is below (sync_plugin.py is outside this territory) |

## Package map (`src/rvt/frontdoor/`)

| module | job |
|---|---|
| `__init__.py` | `author()`/`run()` — the ONE entrypoint; `AuthorRequest` route validation (exactly one input; `--rvt` needs `--edit`); the three route functions; result/manifest wiring |
| `base.py` | GENESIS BASE REGISTRY — `PIN` (from `assets/genesis_base.json`), `resolve_base` (`--base` → env → pinned repo path → bundled; sample refused; pin mismatch refused), `resolve_specimen_source` (R5), `is_autodesk_sample` (mirrors the job runner) |
| `intent.py` | the ONE intent model — re-exports `IntentModel`; `intent_from_ifc`; `summarize`; the OPEN-BUG `combination_check` → `CombinationVerdict` (single / split-strict / stamp-proof-only); `buildable_family_plans` |
| `prompt_intent.py` | (a) `scene_brief` + `write_handoff` (the PRIMARY handoff); (b) the FALLBACK: `parse_prompt` (rules-first vocabulary: rooms + dims + service rating/voltage, switchboards / distribution / lighting / receptacle panelboards / transformers by count-rating-voltage-mains-spaces-sections, recognised-but-unbuilt kinds, levels, `fed from`, `no feeders/walls`), `layout_room` (deterministic room-layout rule), `prompt_to_intent` (→ `IntentModel` with contracts via `normalize_contract`, frames, dims replaced by catalog FACTS, feeder tree, `plan_families`), `PromptCoverage` |
| `edit.py` | the `--rvt` route — `parse_edit_spec` (ops.json / inline JSON / an edit-sentence grammar: delete[cascade] / move to|by [+rotation] / rotate / rename / set-mark / set-level / retype / set-param; refs = ids or names/tags/levels resolved from the file), `editables`, `resolve_ref`, `run_edit` (→ `tools/rvt_job.py edit`) |
| `build.py` | intent → `.rvt` on the genesis base via the ifc-room stages (F/L/W/E/C/V), the DEGRADE orchestration (single / split-strict / stamp-proof-only), created-element harvesting, per-file gates + the deliverability gate |
| `manifest.py` | `build_manifest` / `edit_manifest` / `write_manifest` (json + md); `crud_affordances`; `coverage_cross_reference`; the honesty box |
| `PROMPT_TO_IFC.md` | the AI-surface IFC-authoring instructions (mirrors three-d-stage + the tagging contract) |
| `SKILL.frontdoor.md` | ready-to-drop skill body (`plugin/skills/frontdoor/SKILL.md`) |
| `assets/genesis_base.json`, `assets/README.md` | the base + specimen pins and their documentation |

CLI `tools/frontdoor.py`: `author --prompt TEXT | --ifc FILE | --rvt FILE
--edit SPEC` with `--out`, `--stem`, `--strict`, `--base`, `--specimens`,
`--stages`, `--wall-mode`, `--symbol-hollow`, `--no-validate`,
`--strict-validate`, `--handoff-only`, `--no-handoff`, `--json`,
`--verbose`. Exit 0 = route completed (PROOF-ONLY is still 0), 2 usage,
3 incomplete, 4 self-checks failed.

## Prompt-parser vocabulary (what the fallback understands)

Room: `WxD` in ft (default) / m / mm / in, `by`, `'`, height (`high|tall|
ceiling`), wall thickness, `no walls|equipment only`, `rated for N A
service` (+ a voltage system near it), room nouns (`electrical|switchgear|
transformer|MDF|… room|closet|vault`) — a room noun is a PLACE, never
equipment (`switchgear room` spawns no switchboard). Equipment: count
(digits / number words / plural default), rating (`N A|amp`), `N kVA`, `N
kA`, voltage (`480Y/277 V`, `208Y/120`, `480 V`…), `MCB|main breaker|MLO|main
lugs`, `N-space|circuit`, `N-section`, `flush|surface`, `named X`; kinds:
switchboard (MSB…), distribution / lighting / receptacle panelboard (DP-n /
LP-n / RP-n), panelboard (PP-n), transformer (Tn). Recognised-but-unbuilt
(reported, never dropped): luminaires, generators, UPS, ATS, MCC, busway,
disconnects, receptacles, meters, cable tray, conduit, doors, pads.
Feeders: `fed from`, `no feeders`; else the automatic tree. Defaults are
ALWAYS recorded in the coverage block (12 ft ceiling, 480Y/277 service, DP
= MCB, LP/RP = MLO, 42 spaces, switchboard SCCR 65 kA + section rule…).

Catalog honesty carried through: an **800 A distribution panelboard is
REFUSED** (no Pow-R-Line sizing row); a **500 kVA transformer is REFUSED**
(catalog publishes no dimensions — "Contact Eaton"); a **2500 A switchboard**
becomes the HOUSE switchboard family from prompt-default lineup extents
(flagged prompt-default, not manufacturer data). Refusals become manifest
degradations with the fix, never invented content.

## Worked examples (experiments/frontdoor/, each with manifest.json/.md)

| dir | route / mode | outputs | gates |
|---|---|---|---|
| `prompt-electrical-room/` | prompt, default degrade | `electrical_room_prompt.rvt` (4 walls + 7 fam + 7 inst) + handoff package + 7 `.rfa` | VALID·0·coherent·PASS; STAMP walls+families |
| `prompt-electrical-room-strict/` | prompt `--strict` | `-shell.rvt` (4 walls) + `-equipment.rvt` (7 fam + 7 inst) | both VALID·0·coherent·PASS |
| `ifc-electrical-room-2500a/` | ifc | `electrical-room-2500a.rvt` (4 walls + 8 fam + 8 inst) + 8 `.rfa` | VALID·0·coherent·PASS; 4 unmapped + circuits recorded |
| `rvt-edit-room/` | rvt `--edit` (text) | `electrical_room_prompt.edited.rvt` (DP-1 moved, LP-4 deleted, level edited) | structural/validation/identity/provenance PASS |

All outputs: deliverability gate **PROOF-ONLY, NOT-DELIVERABLE** (the
genesis lineage still fails G1 — recorded, not asserted away; the loaded
families ledger as `transitive-cloned`), and no viewer/Revit acceptance is
claimed.

## Findings worth a KNOWLEDGE.md line

1. **The composed genesis base G_ABPD is buildable-on**: the four-registry
   family loader, the specimen-scaffolded wall add path and the instance
   placement path (all built on ZA_deep) run UNCHANGED on the composition
   (level 311 'L1 - Ground Floor', wall type 600634, R5 specimens; ElemTable
   3,102 → 3,241, watermark 1,472,524 → 1,472,952). The front door pins its
   hash and refuses substitutes.
2. **The intent model IS the multi-surface contract**: a prompt and an IFC
   converge on the same `IntentModel` (same tagging-contract dicts via
   `normalize_contract`, same `plan_families`), so a prompt-only surface
   with NO model call reaches the same build as a Design-authored IFC — and
   the scene brief closes the loop back through IFC.
3. **Front-door instances have no instance parameter rows** (specimen
   scaffolding), so `rename`/`set-mark` are type-level regenerations, not
   edits; the certified edit path fails loud rather than corrupting. Move /
   retype / delete / set-level work on them (verified round trip).

## Named blockers / missing pieces (exact)

1. **CIRCUITS** — a NAMED BLOCKER on the family-free genesis base (no
   `RbsElectricalSystem` specimen; both circuit constructors clone one). The
   feeder tree / circuit PLAN is fully resolved in every intent JSON
   (`feederTree.circuitPlan`) for `rvt.mep add_circuit` / a Revit-side
   add-in. Missing piece: an `RbsElectricalSystem` CONSTRUCTOR (the KNOWLEDGE
   circuit model is its spec).
2. **THE OPEN BUG** — walls + loaded family documents together fail the
   audit (verdict #24 retraction of #22). The front door DEGRADES around it;
   the render/creation stream owns the fix. When fixed: flip
   `combination_check` to `single` for the combination and delete the stamp
   logic (one place).
3. **Face-hosting** of the wall panels on the created walls (they stand
   free-standing upright at the mounting plane, the certified precedent);
   `rvt.hosting` on created walls is the fidelity follow-up.
4. **Instance parameter rows** for our instances (per-instance PanelName /
   mounting height) — the loader's `author_family_instance` writes them
   when IT places; today the tag rides on each board's own family/type.
5. **Prompt parser is rules-first, not an LLM**: it covers the room /
   equipment / feeder grammar above; free-form intent beyond it goes through
   the PRIMARY handoff path (a surface builds the scene). Coverage is always
   stated; nothing is silently invented.

## Requests for the orchestrator

1. **VIEWER-GATE** (base = certified G_ABPD; control = a byte-identical
   copy): `experiments/frontdoor/prompt-electrical-room-strict/
   electrical_room_prompt-shell.rvt` (walls-only on G_ABPD — the certified
   shape on the NEW base) and `…-equipment.rvt` (7 loaded families +
   placement on G_ABPD), then the combined
   `experiments/frontdoor/prompt-electrical-room/electrical_room_prompt.rvt`
   (the open-bug combination — expected FAIL until the render stream fixes
   it; a PASS retires the stamp). Same trio for `ifc-electrical-room-2500a/`.
2. **`tools/sync_plugin.py`** — add the front-door CLI to `file_maps` (the
   engine already flows via `src/rvt/**`), then run the sync:
   ```diff
   --- a/tools/sync_plugin.py
   +++ b/tools/sync_plugin.py
   @@ def mappings():
        (os.path.join(ROOT, "tools", "panel_schedule.py"), "skills/rvt-native/scripts/panel_schedule.py"),
   +    (os.path.join(ROOT, "tools", "frontdoor.py"), "skills/rvt-native/scripts/frontdoor.py"),
   +    (os.path.join(ROOT, "tools", "ifc_intent.py"), "skills/rvt-native/scripts/ifc_intent.py"),
   +    (os.path.join(ROOT, "tools", "rvt_job.py"), "skills/rvt-native/scripts/rvt_job.py"),
   ```
   (the front door loads `ifc_intent.py` and `rvt_job.py` as modules; in
   the plugin layout it looks in `<plugin-root>/tools/` — set
   `RVT_PLUGIN_ROOT` or extend the loader's candidate paths to the scripts
   dir in the packager pass).
3. **Promote the skill**: `src/rvt/frontdoor/SKILL.frontdoor.md` →
   `plugin/skills/frontdoor/SKILL.md`; add `/frontdoor` to the plugin
   commands (`author --prompt|--ifc|--rvt`).
4. **KNOWLEDGE.md** lines to merge: findings 1–3 above.
5. **Missing constructors** (unchanged from the ifc-room record, now on the
   product's critical path): `RbsElectricalSystem` circuit constructor;
   face-SketchPlane hosting on created walls; instance parameter rows.

## How to run

```
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room 30x20 ft rated for \
    2500 A service with a main switchboard, two 400 A distribution panels and four lighting \
    panels" --out out/room [--strict] [--handoff-only]        # ~14 s
.venv/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc \
    --out out/ifc                                             # ~16 s
.venv/bin/python tools/frontdoor.py author --rvt out/room/electrical_room_prompt.rvt \
    --edit "move DP-1 to 3,1,4.66; delete LP-4 with cascade" --out out/edit    # ~1 s
.venv/bin/python -m pytest tests/test_frontdoor.py            # 31 passed (~30 s)
```

## BRANCH STATE

* **DONE** (this session): `src/rvt/frontdoor/` — `__init__.py` (the
  `author` entrypoint, three routes), `base.py` (genesis base registry +
  pin + sample refusal), `intent.py` (the one intent model + the open-bug
  combination detector), `prompt_intent.py` (scene brief / handoff +
  the rules-first fallback parser → the SAME IntentModel), `edit.py` (the
  `--rvt` route → the job runner's certified edit pipeline), `build.py`
  (intent → .rvt on the genesis base via the reused ifc-room stages + the
  three-mode degrade), `manifest.py` (the deliverable manifest json + md),
  `PROMPT_TO_IFC.md`, `SKILL.frontdoor.md`, `assets/genesis_base.json` +
  `assets/README.md`; `tools/frontdoor.py` (CLI); `tests/test_frontdoor.py`
  — **31 passed**; `experiments/frontdoor/` — the worked prompt (default
  stamped + `--strict` split), the electrical-room IFC end to end, the
  `--rvt` round trip, `README.md` index; this record.
* **THE THREE ROUTES WORK**: prompt (handoff + no-API-key fallback build),
  IFC, and rvt-edit all produce `.rvt`(s) + manifest on the pinned
  certified genesis base; every emitted file passes validator (0 errors) +
  registry coherence + identity; the walls+families open bug is stamped
  (default) or split (`--strict`), never silent.
* **BLOCKED, NAMED**: feeder CIRCUITS (no `RbsElectricalSystem` specimen /
  constructor — the circuit plan is ready in every intent); face-hosting;
  instance parameter rows (rename/set-mark on our instances); the
  walls+families open bug itself (render/creation stream).
* **NOT VIEWER-TESTED**: every `.rvt` here is validator/registry/identity-
  clean but AWAITS the orchestrator's viewer gate — no acceptance claim is
  made. Status PROOF-ONLY: the base is the certified genesis composition
  (its documented residue is why the deliverability gate says
  NOT-DELIVERABLE); our added layer (families, walls, instances) is ours.
* **Full suite** (`.venv/bin/python -m pytest tests/ -q`): **1,269 passed,
  2 failed** in 17 min 45 s. The 2 failures are PRE-EXISTING and OUTSIDE
  this stream (`tests/test_provenance.py::test_G0_resource_refs_are_counted`
  and `::test_G0_identity_dit_usernames_still_leak`): stale assertions that
  expect `experiments/genesis/G0.rvt` to still carry the `assetlibrary_
  base.fbx` resource id and the sample's DocumentIncrementTable usernames —
  both leaks the genesis / writer streams have since SCRUBBED (TRACKER G1
  "LEAKS FIXED"; G0.rvt regenerated 2026-08-03 17:15, the tests predate the
  fix). Not touched (rvt.provenance / genesis territory) — flagged here for
  the owner to update the two assertions. All 31 front-door tests pass.

Files (repo root): `src/rvt/frontdoor/**`, `tools/frontdoor.py`,
`tests/test_frontdoor.py`, `experiments/frontdoor/{README.md,
prompt-electrical-room/**, prompt-electrical-room-strict/**,
ifc-electrical-room-2500a/**, rvt-edit-room/**}`,
`docs/inbox/frontdoor.md`.

---

## 2026-08-09 — stream `eng142` (issue #142): the front door stamps the REAL open cell

**Why.** The degrade policy above keyed on "created walls + loaded families in
one file" (verdict #24). The ledger has since said the opposite: walls + a
loaded family PASS (`WF_fix` / `WF_nofix`, genesis-audit #27,
`docs/inbox/genesis-audit.md:1167-1170`), while **placed instances of OUR
generated family documents on OUR composed genesis base** are THE open cell
(verdict #48, `genesis-audit.md:1754-1774`; `ROOM2025_full.rvt` and
`demo-250v-v5/prompt_room.rvt` FAIL in `docs/coverage/viewer-certified.json`;
issue #16). So an equipment-only prompt shipped with `mode=single` and **no**
open-cell stamp, and a walls + loaded-families file got a false one. PG1: a
label may claim neither more nor less than the evidence. Rule 1 unchanged:
every mode delivers its file(s); the stamp is a label after delivery.

**Reproduced first** (main @ 730fe5a, pinned G_ABPD base, this cloud VM):
`frontdoor author --prompt "six 225A panelboards"` → 6 families generated,
loaded, **6 instances placed** → `combination_verdict.mode = "single"`,
`triggers_open_bug = false`, `stamp = null`; honesty stamps =
`['PROOF-ONLY, NOT-DELIVERABLE']` only.

**The truth table now implemented** (`rvt.frontdoor.intent.combination_check(model,
strict=, stages=, composed_base=, loaded_tags=)`; `build.py` passes `opts.stages`
and `composed_base = not base.is_autodesk_sample` — the pinned bases and any
explicit/env genesis override count as our composed lineage; only a
quarantined pristine Autodesk sample does not — and calls it a second time
after the L stage with `loaded_tags = the tags that actually loaded`, so the
verdict follows the load result instead of the plan: a load that degrades to
nothing places nothing and drops the label, a partial load counts only the
instances it can place):

| job shape (what the stages will actually do) | host | `mode` | `triggers_open_bug` | stamp | files |
|---|---|---|---|---|---|
| ≥1 instance of our generated family PLACED (`L`+`E` in stages, buildable plan) — with or without walls | composed base | `stamp-proof-only` | **true** | `PROOF-ONLY: generated-family INSTANCES on a composed genesis base (open cell, docs/inbox/genesis-audit.md #48, issue #16)` | `combined` (delivered) |
| same, `--strict` | composed base | `split-strict` | **true** | none (split instead) | `shell` = walls + LOADED families, no placement (WF_fix shape) + `equipment` = loaded families + PLACED instances (the cell, isolated) — **both delivered** |
| walls + loaded families, NO placement (`--stages FLWV`) | any | `single` | false | none | `combined` |
| walls only / loaded families only / nothing loaded (load degraded → verdict re-derived, stamp dropped) | any | `single` | false | none | `combined` |
| instances placed | NOT our composed base (pristine host: T1r/T1u/U16 PASS) | `single` | false | none (status gate still says PROOF-ONLY) | `combined` |

New verdict fields (additive, JSON too): `n_instances`, `composed_base`, and
the derived `places_instances`. `OPEN_BUG_ID = "generated-family-instances-on-composed-base"`,
`OPEN_CELL_STAMP` exported (`matrix.py` stays import-light and repeats it as
prose; `tests/test_router.py::test_open_cell_caveat_names_the_front_door_stamp`
pins the constant, the matrix caveat and `PERMUTATION-MATRIX.md` together).
Side fix in the single-file branch: the loaded families are harvested into
`elements_created` whenever the output descends from the loaded chain (the FLWV
manifest used to list 4 walls + 7 `.rfa` but not the 7 loaded families). `add_to_project` / `merge_ifc` (out of territory)
call `combination_check(model, strict=)` unchanged and therefore get the
conservative default (`stages` full, `composed_base=True`): an add/merge that
places an instance now carries the open-cell stamp; one that only creates
walls + loads families does not.

**Runtime evidence through the real CLI** (`tools/frontdoor.py author`, pinned
2026 base, `.venv` from `scripts/cloud-setup.sh`, wall time = `time` real):

| shape | command | verdict lines from `manifest.json` | delivered | `tools/rvt_validate.py` | wall |
|---|---|---|---|---|---|
| equipment-only | `--prompt "six 225A panelboards"` | `mode=stamp-proof-only triggers_open_bug=true n_walls=0 n_loaded_families=6 n_instances=6 places_instances=true composed_base=true stamp="PROOF-ONLY: generated-family INSTANCES on a composed genesis base (open cell, docs/inbox/genesis-audit.md #48, issue #16)"` | `out/eq/prompt_room.rvt` (6 rfa, 6 loaded, 6 instances) | ok=True, 0 errors / 1 warning | 15.1 s (17.6 s for the same prompt on main before the change, same VM — no latency cost) |
| walls + loaded families, no placement | room prompt¹ `--stages FLWV` | `mode=single triggers_open_bug=false n_walls=4 n_loaded_families=7 n_instances=0 stamp=null reason="open cell not exercised by this job: 4 walls + 7 loaded families WITHOUT placement -- the WF_fix / WF_nofix certified shape (genesis-audit #27)…"` | `out/flwv/prompt_room.rvt` (4 walls, 7 rfa, 7 loaded families) | ok=True, 0 errors / 1 warning | 16.6 s |
| `--strict` | room prompt¹ `--strict` | `mode=split-strict triggers_open_bug=true n_walls=4 n_loaded_families=7 n_instances=7 files=[shell, equipment] reason="…'shell' (the 4 walls + the 7 loaded families, NO placement -- the WF_fix-certified shape) and 'equipment' (the loaded families + their 7 PLACED instances = the open cell, isolated). Both files are delivered…"` | `out/strict/prompt_room-shell.rvt` (4 walls + 7 loaded families) **and** `out/strict/prompt_room-equipment.rvt` (7 loaded + 7 instances) | both ok=True, 0 errors / 1 warning; manifest self-checks VALID/PASS on both roles | 17.7 s |

¹ `"an electrical room 30x20 ft rated for 2500 A service with a main switchboard, two 400 A distribution panels and four lighting panels"`. Every run: exit 0, `status: PROOF-ONLY (self-checks PASS…)`, honesty box lists the open-cell stamp first when it applies plus the P0 `PROOF-ONLY, NOT-DELIVERABLE` gate; `MANIFEST.md` prints `STAMP: … (a label: the file below is delivered)` and an `open cell:` line citing #48 / #16 and the certified neighbours.

**Also changed:** `matrix.py` `_OPEN_BUG` caveat text + the `intent->rvt`
stage blurb (text only, no cell flips; `verify_evidence` untouched);
`docs/product/PERMUTATION-MATRIX.md` — only the open-cell caveats (prompt→rvt
row, ifc→rvt / spec→rvt "same caveats" words, the ifc+rvt merge caveat, demo3
line, and the "Open bug r2" named gap now marked exonerated); the rfa rows are
#171's and untouched. `manifest.py` renders `open cell:` instead of `open bug:`.
Tests: `test_combination_detected_and_degraded` and
`test_no_combination_when_walls_or_families_only` rewritten to the table above
(equipment-only stamps; FLWV does not; `--strict` files; non-composed host);
`test_manifest_crud_and_honesty_shape` + the e2e genesis test use
`FI.OPEN_CELL_STAMP`; `tests/test_router.py` two e2e assertions now expect the
`generated-family INSTANCES` stamp (they self-skip here: `experiments/genesis`
absent in a cloud clone).

**Follow-ups filed (out of territory, `Refs #142`):** #240 — stale "walls+families"
wording in `tools/frontdoor.py --strict` help (hot file),
`src/rvt/frontdoor/__init__.py` + `SKILL.frontdoor.md` docstrings and
`plugin/skills/tekton-author/references/GENESIS-BASE.md`; and #239 —
`rvt.convert.add_to_project` should pass the target's lineage
(`composed_base = tekton-authored target`) so an add-into-a-pristine-user-project
run rides the certified T1u cell instead of the conservative composed-base label,
and its `--strict` split should adopt the shell = walls + loaded families shape.

### BRANCH STATE (eng142)

* Branch `cam/142-open-cell-stamp` from main @ 730fe5a; PR `Closes #142`.
* Files written: `src/rvt/frontdoor/intent.py`, `src/rvt/frontdoor/build.py`,
  `src/rvt/frontdoor/matrix.py` (caveat text), `src/rvt/frontdoor/manifest.py`
  (one render line), `docs/product/PERMUTATION-MATRIX.md` (open-cell caveats
  only), `tests/test_frontdoor.py`, `tests/test_router.py`, this section; plugin
  mirror regenerated by `tools/sync_plugin.py` (4 files synced).
* Gates (this VM, fresh cloud clone): `tests/test_frontdoor.py` 31 passed / 4
  skipped; `tests/test_router.py` 73 passed / 4 skipped (48 s, includes the
  built-room convert e2e with the new merge stamp assertion);
  `tests/test_plugin_sync.py` 7 passed; `tests/test_convert_combo.py` 3 passed /
  9 skipped; the CI shard (`tests/ci_shard.txt`) result is in the PR body;
  `tools/sync_plugin.py` run + `--check` clean; `plugin/scripts/validate_plugin.py`
  PASS (23 assertions); `tools/dev/check_portable_paths.py` ok (2694 paths).
  Skips are the usual absent `experiments/genesis` / `samples/` gates.
* Shipped vs staged: code + docs shipped in the PR; **no viewer claim** — the
  three CLI outputs above are validator-clean local artifacts (`out/`, ignored),
  not STAGED; nothing in `docs/coverage/viewer-certified.json` changes.
