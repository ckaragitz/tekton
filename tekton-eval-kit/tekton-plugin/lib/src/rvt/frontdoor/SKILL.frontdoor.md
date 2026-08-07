---
name: frontdoor
description: "THE FRONT DOOR to tekton — ONE entrypoint that authors a native Revit .rvt from ANY of three inputs: a natural-language PROMPT (\"an electrical room 30x20 ft rated for 2500 A service with a main switchboard, two 400 A distribution panels and four lighting panels\"), an authored IFC file, or an existing .rvt plus an edit. Use whenever the user wants a Revit deliverable made from a description, from a Claude-Design/Three.js IFC export, or wants an existing .rvt changed (move / delete / retype an element). Every route emits the .rvt(s) PLUS a deliverable manifest that states, honestly, what was built vs degraded, the certified genesis base it was grown on, the validator summary, PROOF-ONLY stamps and how to edit/delete everything it created. Works from any AI surface (Claude Design / Chat / Cowork, ChatGPT Work, Gemini) with no API key."
---

# frontdoor — one entrypoint, three inputs, one honest manifest

Everything below drives ONE command: `python tools/frontdoor.py author ...`
(engine: `<plugin-root>/lib/src/rvt/frontdoor`; install once with
`pip install ./lib`). Read this file before promising anything.

## 0. Setup

```bash
cd <plugin-root>
pip install ./lib                       # the rvt engine (pure Python + numpy; olefile)
pip install ifcopenshell                # only needed for the --ifc route
python tools/frontdoor.py author -h     # confirm the CLI is live
```

The front door authors ON A BASE document. The default is our **certified
genesis base** (`G_ABPD`, sha256-pinned in `lib/src/rvt/frontdoor/assets/
genesis_base.json` — our composed project base with NO Autodesk-authored base
content). It is resolved from `$RVT_GENESIS_BASE`, the repo, or a bundled
copy, and the hash MUST match the pin; an **Autodesk sample project is
REFUSED** as a base, always. `--base <firm.rvt>` uses a base the user
supplies (their responsibility; recorded, never asserted certified).

## 1. The honest status box — say this before any promise

| Route | Status | What is real |
|---|---|---|
| `--ifc` | **BUILT + SELF-CHECKED** | resolves REAL placements from the geometry (the ifc-room resolver), maps every tagged board onto OUR generated families via the schedule Psets, builds walls + families + instances on the genesis base; validator VALID / registries coherent / identity PASS on the worked example |
| `--prompt` PRIMARY | **HANDOFF PACKAGE** | emits `scene-brief.json` + `HANDOFF.md` + `PROMPT_TO_IFC.md`: any AI surface builds the Three.js scene, exports IFC4 with our tagging-contract Psets, and the file re-enters through `--ifc` — the recommended path (the surface's geometry becomes the design) |
| `--prompt` FALLBACK | **BUILT, NO MODEL CALL** | a deterministic rules-first parser resolves the prompt into the same intent model (rooms + service rating, switchboards / distribution / lighting / receptacle panelboards / transformers by count-rating-voltage-mains-spaces, walls, feeders) and builds it; its COVERAGE (understood / ignored / defaulted / not-built) rides in the manifest |
| `--rvt --edit` | **PROVEN edit path** | move / retype / delete(+cascade) / set-level / set-param on the user's file through the certified manipulate pipeline (rename/set-mark work on NATIVE instances; ours carry no instance param rows — the manifest says so) |
| every output | **PROOF-ONLY** | self-checks PASS ≠ Autodesk acceptance; the genesis lineage still fails the P0 deliverability gate (recorded); LOAD ≠ RENDER (created walls carry no baked geometry for the cloud viewer). Never conflate the tiers. |

The **OPEN BUG** you must know cold: created **walls + loaded family
documents in the SAME file** currently trip Autodesk's audit (walls alone
PASS, families alone PASS). The front door NEVER ships that combination
silently: by default it emits one combined file whose manifest is STAMPED
`PROOF-ONLY: walls+families combination unverified`; with `--strict` it
emits TWO coordinated files (`-shell.rvt` = walls, `-equipment.rvt` =
families + instances), each a viewer-certified SHAPE. Tell the user which
they got.

## 2. Which route?

| The user gives you… | Run |
|---|---|
| a sentence describing a room / equipment | `frontdoor author --prompt "…" --out DIR` → hand `HANDOFF.md` + `scene-brief.json` to a Three.js-capable surface (best), OR use the fallback `.rvt` it also built |
| only wants the AI-surface package (no build) | add `--handoff-only` |
| an `.ifc` (from Claude Design / three-d-stage / any exporter following our tagging contract) | `frontdoor author --ifc FILE.ifc --out DIR` |
| an `.rvt` and a change to make | `frontdoor author --rvt FILE.rvt --edit "move DP-1 to 3,4,0; delete LP-4 with cascade" --out DIR` (or `--edit ops.json` / inline JSON) |
| wants two proven-shaped files instead of the stamped combo | add `--strict` (prompt/ifc routes) |

## 3. Commands (copy exactly)

```bash
# PROMPT (handoff + fallback build)
python tools/frontdoor.py author \
  --prompt "an electrical room 30x20 ft rated for 2500 A service with a main switchboard, two 400 A distribution panels and four lighting panels" \
  --out out/room  [--strict] [--handoff-only]

# IFC
python tools/frontdoor.py author --ifc electrical-room.ifc --out out/ifc-room [--strict]

# EDIT an existing .rvt
python tools/frontdoor.py author --rvt out/room/electrical_room_prompt.rvt \
  --edit "move DP-1 to 3,1,4.66; delete LP-4 with cascade" --out out/edit
```

Prompt grammar the fallback understands (state it if the user asks): room
`WxD ft|m` (+ height, wall thickness, `no walls`), `rated for N A
service` (+ voltage system), `<count> <N A> [voltage] [MCB|MLO] [N-space]
switchboard | distribution / lighting / receptacle panel[board]s`,
`<N kVA> transformer`, `fed from`, `no feeders`. Anything it cannot build
(luminaires, generators, UPS, MCC, busway, conduit, doors, pads) is
recognised and reported under `not_built`, never silently dropped.

Edit grammar (`--edit` text): `delete <name|id> [with cascade]`,
`move <ref> to X,Y[,Z] [ft|m] [rotation N deg]`, `move <ref> by dX,dY[,dZ]`,
`rotate <ref> to N deg`, `rename panel <ref> to NAME`, `set mark of <ref>
to MARK`, `set level <ref> elevation to N ft|m`, `retype <ref> to <symbol
id>`, `set parameter <id> of <ref> to VALUE`; clauses separated by `;`.
`<ref>` = an element id or a name / panel tag / level name found in the
file. Or pass an `ops.json` in the job runner's vocabulary.

## 4. What you MUST read back to the user (from `MANIFEST.md`)

1. **Status** and every **PROOF-ONLY stamp** verbatim.
2. What was **created** (walls, families, instances) and every
   **degradation** (unmapped kinds, refused catalog ratings, the circuits
   blocker) — e.g. an 800 A distribution panelboard is REFUSED (no catalog
   sizing row); the front door never invents dimensions or ratings.
3. The **self-checks** per file (validator errors/warnings, registry
   coherence, identity) and the **deliverability gate** verdict.
4. The **CRUD affordances**: the exact `--rvt --edit` sentences that move /
   retype / delete each created element.
5. For prompts: the **coverage** block (understood / ignored words /
   defaults applied / not built).

## 5. Do / Don't

**Do** always run the front door rather than hand-building specs; keep the
Pset property NAMES (`PanelSchedule.PanelName / Voltage / BusRating /
MainsType / NumberOfCircuits / FedFrom`, `SwitchboardSchedule.*`,
`TransformerSchedule.RatingkVA / Primary / Secondary`) when authoring IFC —
they are the join key; report both tiers (self-checks vs Autodesk
acceptance) separately; confirm the user's Revit version (2026 target).

**Don't** point `--base` at an Autodesk sample (refused anyway); don't call a
PROOF-ONLY file a deliverable; don't claim circuits / panel schedules were
authored (they are a named blocker — the circuit PLAN is in the intent JSON
for `rvt.mep` / a Revit-side add-in); don't strip the stamp; don't promise
rename/set-mark on front-door instances (regenerate with a new tag instead).

## 6. Reference

| Path | What |
|---|---|
| `tools/frontdoor.py` | the CLI (`author`) |
| `lib/src/rvt/frontdoor/__init__.py` | `author()` — the ONE entrypoint |
| `lib/src/rvt/frontdoor/prompt_intent.py` | fallback parser + layout + `scene_brief` / `write_handoff` |
| `lib/src/rvt/frontdoor/PROMPT_TO_IFC.md` | the IFC-authoring instructions for AI surfaces |
| `lib/src/rvt/frontdoor/build.py` | intent → .rvt on the genesis base + the walls/families degrade |
| `lib/src/rvt/frontdoor/edit.py` | the `--rvt` route (edit-spec normalisation → job runner) |
| `lib/src/rvt/frontdoor/manifest.py` | the deliverable manifest (route, gates, stamps, CRUD) |
| `lib/src/rvt/frontdoor/assets/genesis_base.json` | the pinned genesis base + certification citation |
| `docs/inbox/frontdoor.md` (repo) | the stream record: worked examples, gates, open items |
