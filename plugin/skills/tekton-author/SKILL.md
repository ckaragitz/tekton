---
name: tekton-author
description: Create a new Revit project or family file from scratch when the user asks to build, generate, author or 'make me' a Revit (.rvt/.rfa) file, a room, an electrical room, walls, a panelboard, switchboard, transformer, lighting layout, or a family — from a plain-English prompt, an IFC file, or an existing .rvt to extend. Asks the recipient's Revit YEAR first (Revit cannot open a newer file; 2026/2025/2024 build natively on certified bases, older years get an honest fallback plus IFC), then runs the tekton front door in ONE call (scripts/_bootstrap.py go author --prompt | --ifc | --rvt --target-version YEAR) and returns the .rvt plus the honest per-release status, PROOF-ONLY stamps and manifest. Also handles 'turn this IFC into Revit' and 'give me the Three.js/IFC handoff for a prompt'. Formats, examples and caveats are in the skill body and references/.

---

# tekton-author — one question, one call, one honest result

tekton authors Revit `.rvt`/`.rfa` files as OUR OWN content on OUR certified
genesis bases — pure Python, no Revit install. `<plugin>` = this plugin's
root (the folder holding `.claude-plugin/`, `skills/`, `lib/`, `assets/`);
this file is `<plugin>/skills/tekton-author/SKILL.md`. Commands run from
anywhere; outputs land under `--out` (use the user's working directory).

## THE DELIVERABLE RULE (non-negotiable)

When the user asks for a `.rvt` or `.rfa` and one can be built, **build it,
write it to disk, and hand it over — always.** PROOF-ONLY stamps, gate
verdicts and version lines are **labels** that ride in the result, **never
refusal logic**: deliver first, then state stamps and caveats plainly. The
ONLY acceptable non-delivery is a genuinely impossible build, reported as
ONE clear line naming the single missing input (the tool prints it). Never
silently substitute IFC for a requested `.rvt` — IFC is an *addition*.
Never lecture before delivering.

## Step 0 — ask the Revit YEAR first (one question, then never again)

Revit cannot open a file saved by a newer release, so before any creation
job ask once — as a picker where the surface has one (AskUserQuestion),
else one plain sentence: **"Which Revit year will open this — 2026, 2025,
2024, or older/unsure?"** If the request already names a year, use it and
skip the question. Show the honest status with the choices:

- **2026 · 2025 · 2024 — supported (`certified-base`)**: built natively on
  that year's composed genesis base, which Autodesk's reader has certified;
  each output passes our validator (0 errors) but is *not itself
  Autodesk-certified* until they open it. Opens in that year **and newer**.
- **Older (2023, 2022 …) — not supported for `.rvt` creation**: say so up
  front. The run still DELIVERS (default-release `.rvt` + one clear line
  that their Revit cannot open it + a version-agnostic **IFC** beside it,
  which any Revit 2019+ links). Offer the IFC as the usable deliverable.
- **Unsure / mixed installs → use 2024**: every supported Revit opens it.

Pass the answer straight through as `--target-version YEAR` (any year is
accepted; the tool owns the guard and degrades honestly — never decide or
stay silent on its behalf). Existing `.rvt` inputs need no question: the
release is auto-detected and kept (below). Per-year detail, edge cases and
wording: `references/REVIT-VERSIONS.md` (read only when needed).

## Step 1 — the job: ONE command, whose JSON IS your report

`go` = readiness check + the job + one combined JSON, in a single call (no
pip, no venv, no `eval`, no separate preflight, no exploring the
filesystem). Exactly one input per call:

```bash
python <plugin>/skills/tekton-author/scripts/_bootstrap.py go author \
    --prompt "an electrical room 30x20 ft rated for 2500 A service with a main switchboard, \
    two 400 A distribution panels and four lighting panels" --target-version 2025 --out out/job1

python <plugin>/skills/tekton-author/scripts/_bootstrap.py go author \
    --ifc <their-file>.ifc --target-version 2024 --out out/job2

python <plugin>/skills/tekton-author/scripts/_bootstrap.py go author \
    --rvt their.rvt --edit "delete DP-1 with cascade; move LP-2 to 3,4" --out out/job3
```

**A 3D OBJECT / SHAPE the user gives you (a Claude Design body, a sketch, a
set of dimensions) is the FOURTH route — do not send it through `--prompt`,
which only knows catalog electrical equipment and would refuse it.** Write
the famspec JSON yourself from what they described and run the router:

```bash
# you author this file from their geometry -- footprint ring in FEET, then height
cat > widget.famspec.json <<'JSON'
{"kind": "generic_model", "name": "My Widget",
 "vertices": [[0,0], [4,0], [4,1.5], [1.5,1.5], [1.5,3], [0,3]],
 "height_ft": 2.5, "source": "claude-design"}
JSON
python <plugin>/skills/tekton-author/scripts/_bootstrap.py go route.py \
    run --rfa widget.famspec.json --output rfa --out out/job4
```

`vertices` = the closed outline of the footprint (3+ points, feet, convex OR
concave, either winding; do not repeat the first point). A box is
`"width_ft"` + `"depth_ft"` instead. Always `"height_ft"`. Optional:
`"target_version"`, `"category"`, `"base_z_ft"`, `"solid"`. NEVER invent
manufacturer, model or rating values for a shape — the geometry is reported
as GIVEN with its source, which is exactly what makes this route honest.

**Anything with more than one solid uses `"parts"`** instead of the single
outline: a list of prisms in the family's frame, each with its own `shape`
(`box`, `cylinder`, `cylinder_x`, `cylinder_y`, `polygon`, `sphere`, `dome`,
`cone`), size, `center` and `base_z_ft` — a cable tray (rails + rungs), a
cart (body + four wheels), any LOD-400 assembly: one family, many solids,
no catalog entry, no donor. `cylinder_x`/`_y` DRAW as true lying cylinders
(a rotated cached B-rep) over a still-vertical sketch, so Revit may stand
them upright on edit — never promise those forms stay editable (wording
per shape and category: `references/FAMSPEC-CAVEATS.md`).

**ALWAYS set `"category"` to what the thing actually is** — `data_devices`,
`lighting_fixture`, `electrical_equipment`, `mechanical_equipment`,
`plumbing_fixture`, `fire_alarm_devices`, `cable_tray_fitting`, `furniture`,
`casework`, `structural_framing`, … — not the `generic_model` default. Five
ids are desktop-verified (same reference); the rest — `door`/`window` too,
also unhosted — ship as "category id inferred, not desktop-verified". It
sets the place in Revit's category tree AND the **standard parameter set**
(a data device's ports / cable category / mounting height / load …, a
luminaire's photometrics, mechanical equipment's airflow). Fill only what
the user told you, feet for lengths (e.g.
`"standard_values": {"Number of Ports": 2}`); the rest stay BLANK on
purpose, never guessed. `"standards": false` drops the set; `go
make_family.py standards <category>` prints a category's exact set, or
plainly that it has none yet — run it first.

If their object is curved, approximate the outline as a polygon and SAY you
did. If they hand you a mesh/solid file (OBJ, glTF, STL, STEP) there is no
reader yet — ask for an IFC export (`--ifc`) or the footprint dimensions.

stdout is ONE JSON object: `go` {`ready`, `preflight_line`, `exit_code`,
`inputs` = auto-detected release of any `.rvt`/`.rfa` you passed} and
`result` {`status`, `files`, `release`, `stamps`, `errors`, `manifest`
paths, `handoff`}. `go.ready:false` → relay `preflight_line` verbatim (it
names the one thing wrong; `family-donor missing` is fine — everything is
built from the bundled bases). Exit 0 = route completed (PROOF-ONLY is
still 0); 2 = usage; 3 = build incomplete (JSON says what stopped and what
was still written); 4 = our own validator failed (deliver the file WITH
that report, said plainly). Never read, probe, list, or request access to
any Autodesk installation directory (Program Files / ProgramData Autodesk
trees, /Applications/Autodesk, family-template folders): every input comes
from this plugin's assets or a file the user supplies.

Useful flags (`go author --help`): `--base FILE.rvt` (a firm's own base; an
Autodesk sample is refused; with a target it must BE that release),
`--strict` (two coordinated files instead of one stamped combined file —
caveat 3), `--handoff-only` (prompt route: only the AI-surface handoff),
`--stages FLWECV` (subset the build), `--specimens FILE.rvt` (expert).

## Step 2 — report, in this order (everything is already in the JSON)

1. **Hand over every path in `result.files`** (plus `result.handoff` on the
   prompt route). The files are the user's regardless of stamps.
2. **The version story from `result.release`:** "built for Revit
   {`output`}; {`opens_in`}". If `release.line` exists (an older/unsupported
   year, or the `--rvt` route on a newer input) relay it **verbatim** and
   hand over the `.rvt` AND `release.ifc_addition`. `target_support` /
   `this_file` are the two honest tiers: base *certified* by Autodesk's
   reader vs this output *validated-not-certified* (accepted by Autodesk
   only after they open it in Revit / the free Autodesk Viewer). If
   `release.ask` is present you forgot step 0 — state the output year now.
3. `result.status` verbatim (`DELIVERABLE …` is the only string meaning
   shippable to third parties; `PROOF-ONLY …` = theirs with named caveats;
   `FAILED (…)` names the stage and the one missing input), then
   `result.stamps` plainly — labels, AFTER the hand-over.
4. Counts and coverage if asked (families generated, elements created,
   circuits; the prompt route's `intent.json` shows what was understood /
   defaulted / recognised-but-not-built — share it so ambiguity is fixed
   there). `result.manifest.md` has the long form; do not re-run anything
   to summarise it.

## The four routes in one breath

- **`--prompt`** parses deterministically (no API key): rooms with
  dimensions and service rating; switchboards / distribution / lighting /
  receptacle panelboards / transformers by count, rating, voltage, mains
  style, spaces; feeders. Recognised-but-not-buildable items (luminaires,
  generators, ATS, MCC …) are listed under `not_built`, never dropped. It
  ALSO writes the AI-surface handoff (`scene-brief.json`, `HANDOFF.md`,
  `PROMPT_TO_IFC.md`) — offer it as an addition: a surface builds the
  three.js scene, exports IFC4, and the file re-enters via `--ifc`
  (`references/PROMPT-TO-IFC.md`).
- **`--ifc`** resolves placements, dims, mounting, the feeder tree, and
  maps every board onto OUR constructors by the tagging-contract Pset join
  key (`references/TAGGING-CONTRACT.md`, `references/CATALOG-FACTS.md`).
  Worked inputs ship in `examples/`.
- **`--rvt --edit`** edits the user's own file by element NAME; its release
  is detected and KEPT (`result.release.input_release`; Revit 2026, 2025 and
  2024 project files open under their own release). Surgical id-based
  detail: the **tekton-edit** skill.
- **a famspec via `route.py --rfa`** GENERATES one family from a structured
  request: the catalog kinds (`panelboard`, `transformer`, `luminaire`,
  `device`) by rating/voltage, or `generic_model` for ANY 3D body whose
  geometry the user gives you (footprint `vertices` + `height_ft`, or
  `width_ft`/`depth_ft`/`height_ft`). This is the route for "turn this
  object/shape into a Revit family". Catalog kinds refuse facts they do not
  have, by name; `generic_model` reports every dimension as GIVEN with its
  source and claims no manufacturer identity.

## Honest caveats (state with the delivery, never instead of it)

1. **Build inputs all ship in the plugin**: the certified bases for 2026,
   2025 and 2024, the family container and the wall/instance templates. A
   user file is only ever an expert override (`--base`, `--specimens`,
   `$RVT_FAMILY_DONOR`).
2. **PROOF-ONLY provenance stamp.** The bases are viewer-certified as OURS
   but their lineage discloses Autodesk-derived residue
   (`references/GENESIS-BASE.md`), so the provenance gate stamps outputs
   PROOF-ONLY for third-party deliverability. The user still gets the file;
   a firm's own base via `--base` changes the verdict.
3. **The open walls+families cell.** Created walls AND our generated,
   placed families in ONE file currently trip Autodesk's audit; each alone
   passes. Default = one combined file stamped `PROOF-ONLY: walls+families
   combination unverified`; `--strict` = TWO coordinated proven files
   (shell + equipment) — offer both, user picks. Same on every release.
4. **LOAD is not RENDER.** Loaded symbols/instances carry real solids;
   created walls load but may not draw yet. Run **tekton-inspect**'s render
   check before promising a picture.
5. **CRUD coverage per category** is measured, not assumed — quote the row
   from `references/CRUD-COVERAGE.md` for the category requested.

## Reference

| Path (under `skills/tekton-author/`) | What |
|---|---|
| `scripts/_bootstrap.py` | `go …` one-call dispatch · bare = readiness line · `run <script> …` · `doctor` |
| `scripts/frontdoor.py` | THE front door (`author` with `--prompt` / `--ifc` / `--rvt --edit`, `--target-version`) |
| `scripts/ifc_intent.py` · `scripts/rvt_validate.py` · `scripts/rvt_job.py` | IFC → intent resolver · the validation gate · the gated job runner |
| `references/REVIT-VERSIONS.md` | per-release honest status, the one-way rule, what to say per case |
| `references/TAGGING-CONTRACT.md` · `references/CATALOG-FACTS.md` | Pset join key · manufacturer facts store |
| `references/PROMPT-TO-IFC.md` · `references/GENESIS-BASE.md` · `references/CRUD-COVERAGE.md` · `references/FAMSPEC-CAVEATS.md` | prompt→IFC flow · the bases + stamps · the capability matrix · famspec caveats |
| `examples/electrical-room-2500a.ifc` · `examples/chicago-plenum-downlight.ifc` | worked IFC inputs (our own authoring) |
| sibling skills | **tekton-edit** (change an existing file) · **tekton-inspect** (validate/QA) · **tekton-ifc** (IFC authoring/hardening) |
