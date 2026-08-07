# tekton-ifc engine (`scripts/`)

The Python engine the **tekton-ifc** skill drives inside a Cowork /
claude.ai **Linux code-execution sandbox** (no Claude Code, no local
install). The skill's `SKILL.md` playbook decides *which* tool to run; this
folder is *how*.

## How the sandbox runs it

Every session starts cold, so the skill always does:

```bash
# 1. install (fast: two wheels, no compilers) -- once per session
pip install -r scripts/requirements.txt

# 2. run whichever tool the user's request needs (they compose):
python scripts/validate_ifc.py <in.ifc> --json validation.json
python scripts/harden_ifc.py   <in.ifc> -o <in.hardened.ifc> --report harden.json
python scripts/generate_ifc.py --spec <spec.json> -o <out.ifc> --validate
python scripts/report.py       validation.json [--compare harden.json] -o report.md
```

All four are plain CLIs: they take the user's attached file (Cowork mounts
attachments into the sandbox filesystem), write outputs next to it (or to a
folder Cowork can see), and print a human summary to stdout that Claude
relays. Nothing needs network *after* the pip install. If the sandbox has no
egress even for pip, the wheels must be pre-staged (see "Sandbox limits").

## The tools

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `validate_ifc.py` | any IFC | text summary + `--json` full report | Schema validation (ifcopenshell) **and** a Revit-fidelity linter: entity histogram, element inventory (class / predefined type / name / tag / type / storey), geometry audit (tessellated vs extruded/swept vs brep -> predicted Revit result, % tessellated, triangle counts), placement audit (identity/origin placements = baked coordinates), type audit (duplicate types, untyped elements), instancing audit, phantom-annotation-solid detection, spatial audit, pset/parameter inventory + consistency, unit audit, and an overall **Tier score** with the top 5 fixes. |
| `harden_ifc.py` | existing IFC | rewritten IFC + `--report` JSON diff | Rewrites toward Tier 1 **without changing intended geometry**: merges duplicate types with identical `(class, Name)` (rewires `IfcRelDefinesByType`); creates one shared type per group of identical untyped elements; moves psets that are identical on every occurrence onto the type; repairs empty owner-history fields; removes phantom annotation solids (or `--keep-clearance-as-space` converts axis-aligned box clearances to `IfcSpace .INTERNAL.`); replaces tessellated geometry that is **provably** an upright box (8 corners forming a rectangular prism, rotation about Z allowed) with `IfcExtrudedAreaSolid` + a real placement at the box's base-centre (recovering an insertion point + yaw) — only when exact; assigns missing spatial containment; **preserves every element GlobalId**; reopens the output and prints a before/after diff with the schema-error count. |
| `generate_ifc.py` | building spec JSON (`spec/building.schema.json` + the **MEP `equipment` profile**) | new IFC4 file (deterministic) | Levels/storeys, footprint auto-walls, explicit walls, floors, flat roofs, doors/windows with real voided openings, rooms -> `IfcSpace`, plus `equipment[]` (`panelboard`/`transformer`/`lightfixture`/`switchgear`/`proxy`: name, level, `position [x,y]` m, `rotationDeg`, `elevation` = mounting height, `dims {w,d,h}`, optional `ifcClass`/`predefinedType`/`typeName`, typed `psets`, `typePsets`) emitted as box extrusions with correct classes/predefined types, ONE shared type per `(class, typeName)` via `IfcRepresentationMap`/`IfcMappedItem` instancing, typed psets, containment. Same spec -> **byte-identical** output (seeded GUIDs, fixed timestamps). Minimal legal spec: `{"levels":[{"name":"Level 1","elevation":0}],"equipment":[{"kind":"panelboard","name":"B-HG4","position":[0,0]}]}`. |
| `report.py` | `validation.json` (+ optional `harden.json`) | Markdown report | The human delivery report the skill returns: the Tier 1 / Tier 2 framing, exactly what will and won't be editable in Revit per element, before/after table, top fixes, and how the psets map onto the panelboard shared-parameters file. |

Shared library: `bridge_lib.py` (analysis engine: geometry classification,
box-recovery, all audits, scoring). The CLIs import it from the same folder.

## Exit codes (uniform)

- `0` — success. For `validate_ifc.py` this means *the analysis ran*; the
  verdict is in the report/JSON, so a Tier-0 file still exits 0.
- `1` — the produced/validated output has schema errors (harden, generate
  `--validate`).
- `2` — usage or I/O error (missing file, unreadable spec, not IFC).

## Expected outputs (from the reference runs in this repo)

- `validate_ifc.py samples/design-ifc/bs-area-e-electrical-room.ifc`
  -> score ~31/100, **Tier 0**: 11/11 tessellated, 11/11 identity placements,
  0 type objects (11 untyped), single storey, no spaces, `Voltage` stored as
  a label. Full JSON via `--json`.
- `harden_ifc.py` on that sample -> `experiments/hardened/bs-area-e-hardened.ifc`:
  score ~89, 10/11 elements converted to extrusions (61 boxes), 4 shared
  types created, insertion points recovered, reopens with **0 schema errors**,
  all 11 GlobalIds preserved.
- `generate_ifc.py --spec spec/examples/electrical-room.json` ->
  `experiments/out/electrical-room.ifc`: score **100/100 Tier 1**, 0%
  tessellated, 6 shared types, 1 space, byte-deterministic.

## Sandbox limits to watch (verify empirically inside Cowork)

- **Network for pip.** `pip install -r requirements.txt` needs PyPI egress.
  If the sandbox blocks it, the skill must ship the two wheels
  (`ifcopenshell-0.8.5-...-manylinux_2_28_x86_64.whl`, `numpy-*.whl`) as
  skill assets and `pip install --no-index --find-links ./wheels ...`.
- **Wheel platform.** The Cowork sandbox is Linux x86_64 (manylinux) — that is
  what the pinned wheel targets. macOS arm64 also has a wheel (used to build
  this repo). Python 3.9–3.13 wheels exist for 0.8.5.
- **Time/memory.** All four tools run in well under a second and a few tens of
  MB on the sample; the geometry kernel (OpenCascade) is *not* used, so large
  files scale with entity count only. Very large real projects (100 MB+ IFC)
  are the only case likely to approach sandbox limits.
- **No APS/Autodesk calls happen here** — that is the Tier 2 escalation path
  and belongs behind an MCP with credentials, not in the sandbox.
