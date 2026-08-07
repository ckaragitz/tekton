# HONEST STATUS — what is production-ready today vs landing next

One truth table. Every row is tied to evidence you can open. If a
capability isn't marked **proven** here, don't promise it to a customer.

Status legend:
- **proven-in-viewer** — passed Autodesk's own reading pipeline
  (viewer.autodesk.com / Model Derivative, the same stack Revit uses).
  Recorded in `docs/acceptance-log.md`.
- **verified-locally** — measured by our own tests/linters and reproducible
  on the sample files (numbers pasted in `PLAYBOOK-claude-code.md`).
- **in-progress** — being built; do not offer for real work.

## 1. The IFC pipeline (Tier 1) — USE FOR REAL WORK TODAY

| Capability | Status | Evidence |
|---|---|---|
| Design v2 exporter (`ifc-export.js`, drop-in `toIfc`): real insertion points, extruded solids, one shared type per typeName, instancing, clearance exclusion, multi-storey | verified-locally | TRACKER F3; node harness + ifcopenshell validation (TRACKER F6); `skills/tekton-ifc/tests/` |
| Validate an IFC → score / tier / ranked fixes / element inventory | verified-locally | Real run pasted in PLAYBOOK-claude-code §1: Chicago v1 export = 31.4/100, Tier 0, schema errors 0 |
| Harden an IFC → Tier 1 (types, extrusions, insertion points recovered, GlobalIds kept) | verified-locally | Real run in PLAYBOOK-claude-code §2: **31.4 → 89.0**, Tier 0 → Tier 1 (partial), 10/11 elements recovered, reopens with 0 schema errors (TRACKER F5) |
| Generate Tier-1 IFC from a spec (room + panelboards + transformers; single equipment) | verified-locally | `spec/examples/electrical-room.json` → 100/100 Tier 1, deterministic (PLAYBOOK-claude-code §3); single Eaton panel run in JOB-TEMPLATES/single-equipment-panelboard.md |
| Panel-schedule psets → Revit shared parameters (name/datatype 1:1 map) | verified-locally | `skills/tekton-ifc/references/shared-parameters-mapping.md`; the firm's `panelboard-shared-parameters.txt` (design-ground-truth §3) |
| Live sandbox reality (Cowork `pip install ifcopenshell`, wheel availability, egress) | in-progress | TRACKER F8 open. Local + macOS/manylinux wheels confirmed; a live Cowork tenant not yet tested. Fallback: pre-staged wheels (PLAYBOOK-cowork-and-chat) |

**What Tier 1 is:** correctly-categorized, correctly-placed Revit elements
(DirectShape in the right category) with your schedule data as instance
parameters — movable, taggable, schedulable, dimensionable, on sheets.
**What it is not:** parametric families or working electrical
connectors/circuits. That's Tier 2 (below).

## 2. Native `.rvt` — read side (the reverse-engineered engine)

| Capability | Status | Evidence |
|---|---|---|
| Open any 2026 `.rvt`, enumerate streams, decode the element table and every element object | verified-locally | TRACKER A2b/A4/A10: schema 4,690 classes; 85,814/85,814 records decode on racbasic; corpus 99.69% |
| Audit a model: counts by class, levels, electrical circuits (panel, V, poles, load), symbols vs instances | verified-locally | Real audit of `rmebasicsampleproject.rvt` pasted in JOB-TEMPLATES/model-audit-and-fix.md (28,132 elements, 4 levels, 187 circuits) |
| Ground-truth oracle harness (2023/2024 files + shipped exports/CSVs) | verified-locally | TRACKER A11, `tests/oracle/`, `docs/streams/11-oracle.md` |

## 3. Native `.rvt` — WRITE side

| Capability | Status | Evidence |
|---|---|---|
| Container round-trip (rebuild the compound file, streams identical) opens in Autodesk's reader | **proven-in-viewer** | acceptance-log **V0** PASS (2026-08-02): full 3D + full sheet set render (TRACKER D0) |
| Whole-file rewrite — every framed byte re-emitted by us (recompress + real recomputed ECC page trailers + CFB) | **proven-in-viewer** | acceptance-log **V15** PASS (2026-08-03): "THE NATIVE .rvt WRITER IS PROVEN END-TO-END" (TRACKER D3, D2 ECC cracked) |
| First authored content change — edit text/content inside a native record and have Revit render it | **proven-in-viewer** | acceptance-log **V18/V19** PASS (2026-08-03): our title text renders on the cover sheet (TRACKER D5) |
| Object codec byte-exact (decode/encode all element records) | verified-locally | TRACKER D4: 1,153,554 records, 397 classes, 100.000% |
| Geometric mutation (move a wall, change a level elevation) | in-progress | TRACKER D6 open |
| Element CREATION — add a wall / a family instance / a spec-driven room into a template `.rvt` | **proven-in-viewer** (structural) | V20 (created column), V21 (batch of 4), V22 (created wall) all translated (acceptance log Batches 5-6); `spec_to_rvt.py` generated the electrical room (12 elements); visual eyeball of created geometry pending |
| IFC / spec → native `.rvt` (`revgen rvt --spec ... -o out.rvt`) | in-progress | TRACKER D8 open — the end-goal path; today deliver Tier-1 IFC instead |
| Selling `.rvt`-write commercially | blocked (legal, not technical) | TRACKER D9 — legal review before any commercial `.rvt`-write; family beta unaffected |

So: whole-file `.rvt` read/rewrite and text content edits are **real and
proven by Autodesk's reader**. Making Revit create **new native equipment**
from your data is the next milestone and is **not** ready — until it is,
new equipment ships as Tier-1 IFC plus a Tier-2 handoff table.

## 4. The rules that don't change

- **Tier 2 (native families with connectors/circuits) never comes from
  IFC.** Revit's IFC importer does not create functioning electrical
  connectors, circuits, or native panel schedules from any IFC. Say this to
  the GC before you start (`skills/tekton-ifc/SKILL.md` §1).
- **IFC is version-agnostic; `.rvt` is not.** A `.rvt` cannot be opened
  by any Revit older than the one that saved it. Before ANY `.rvt`
  deliverable, get the recipient's exact Revit version (Help → About).
  Which version the brothers' firm runs is still an open question in
  TRACKER — answer it and we lock the target ceiling.
- **No Autodesk APS / Design Automation.** User decision (twice); the writer
  is our own. Don't propose APS as a workaround (TRACKER Epic C removed).
- **Validate before you deliver, always** — even our own exports go through
  validate → harden → report (`SKILL.md` rule 7).

## 5. Recommended defaults for the brothers, right now

| Job | Do this today |
|---|---|
| Electrical room / equipment for a coordination model or submittal | Design → v2 export → Cowork harden → Link IFC in Revit (Tier 1). Templates: `electrical-room-package.md`, `single-equipment-panelboard.md`. |
| "What's in this Revit file they sent us?" | tekton-native audit (read-only). Template: `model-audit-and-fix.md`. |
| Fix a label/title/text inside a `.rvt` | Proven — ask us to run the content edit; get the Revit version first. |
| Make Revit contain a NEW native panelboard family WITH circuits | **Panels + transformers PROVEN (V20-V28); circuits BUILT and graph-verified (V29, viewer verdict pending)** — panel schedules render in Revit from these circuits; validate in desktop Revit before promising a schedule. |

*Last reconciled with `docs/acceptance-log.md` and `TRACKER.md` on
2026-08-03. When a viewer PASS lands for D6/D7/D8, promote its row here and
add the log entry link.*
