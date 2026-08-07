# Inbox — skill-architect (revit-bridge master SKILL) — 2026-08-02

Out-of-scope observations for the orchestrator, produced while writing
`skills/revit-bridge/{SKILL.md, references/tagging-contract.md,
references/authoring-rules.md, references/sop-design-authoring.md,
references/sop-harden-deliver.md}`.

## 1. Files SKILL.md references that other agents own — link check

At write time these EXISTED and I aligned the docs to their real CLIs /
signatures (verified by running/reading them): `assets/ifc-export.js` (v2,
exports `toIfc`, VERSION 2.0.0), `assets/example-model.js` (exports
`buildExampleModel(THREE)` + `exampleMeta(overrides)`),
`scripts/validate_ifc.py` (`<file> [--json out.json] [--quiet]`, exit
0/2, score+tier verdict), `scripts/harden_ifc.py` (`<in> -o <out>
[--report x.json] [--keep-clearance-as-space] [--no-remove-phantoms]
[--no-create-types] [--no-extrusions]`, exit 0/1/2), `scripts/bridge_lib.py`,
`scripts/generate_ifc.py` (`--spec spec.json -o out.ifc [--validate]`, spec
`equipment[]` array).

Still PENDING (referenced by exact path in SKILL.md, must exist before the
skill ships or SKILL.md needs a follow-up edit):
`references/revit-import-fidelity.md`, `references/mep-class-map.md`,
`references/shared-parameters-mapping.md`, `references/revit-versions.md`,
`scripts/report.py`, `scripts/requirements.txt`. SKILL.md/SOP already
carry explicit fallbacks for a missing `report.py` and `requirements.txt`,
so nothing breaks, but the reference `.md` files are load-bearing for
§6/§9. Suggest a repeatable check: my scratchpad `check_skill.py` (parses
frontmatter, lists every referenced `references|assets|scripts/*` path
with EXISTS/PENDING) — worth promoting to `tools/check_skill.py` (I did
not, `tools/` is off-limits to me).

## 2. Contradiction with my brief: harden DOES recover extrusions

My slice brief implied hardening cannot fix geometry ("interpret the
report"). The real `harden_ifc.py` DOES convert tessellation that is a
provable upright box into `IfcExtrudedAreaSolid` **and** relocates the
placement to the box base-centre. Measured on the real sample:
score 31.4 → 89.0, `identity_placements 11 → 1`,
`products_converted_to_extrusions 10`, `shared_types_created 4`. I wrote
the SKILL to the tool's real behaviour (it's a big selling point), stating
the true limit: non-box soup and baked rotations remain source-only fixes.
KNOWLEDGE.md's "hardening" description may deserve the same update.

## 3. Pinned three@0.184.0 import map — SRI hashes are NOT in the repo

`docs/design-ground-truth.md` §2 mandates the exact import map "with SRI
integrity hashes" but the hashes appear nowhere in this repo. SKILL.md §4.1
therefore instructs: keep an existing project's map byte-for-byte, and
when creating from scratch use the unpkg URLs and copy `integrity` from
Design's "3D object" skill/page — never invent hashes. ACTION: someone
with Design access should paste the exact `<script type="importmap">`
block (with `integrity`) into the skill (suggest
`assets/page-skeleton.html`) so a cold session never has to fetch it.

## 4. Voltage pset typing conflict (ground truth vs the real sample)

design-ground-truth §3 specifies `Voltage[voltage]` →
`IfcElectricVoltageMeasure`, and the firm's shared-params file declares
`Voltage(ELECTRICAL_POTENTIAL)` (a number). But the real sample
`bs-area-e-electrical-room.ifc` emits `Voltage` as
`IFCLABEL('480Y/277 V')` (a string — the *system* description, not a
number). The validator flags this as "untyped electrical values" (6 in the
sample). I standardised the contract on the numeric measure
(`Voltage: {value:208, type:'voltage'}`) to match the shared-params file,
and recommend a SEPARATE label prop (e.g. `SystemVoltage: '208Y/120 V'`)
for the human-readable system string. `references/shared-parameters-
mapping.md` (other agent) should adopt the same rule, or explicitly
decide otherwise, so tags/models/params agree.

## 5. Sample has NO type objects

Ground truth §5 says v1 emits types via `IfcRelDefinesByType` (one per
element). The saved sample has **zero** `IFCRELDEFINESBYTYPE` / type
objects (validate: `0 type objects, 11 untyped`) — because that
particular model's meta carried no `typeName`. Not a doc error, just note
that the "duplicated types" defect only manifests when `typeName` is set;
the harden path creates shared types for untyped identical elements
regardless (verified: 4 created).

## 6. Suggested TRACKER additions (orchestrator to decide)

- F2a: reconcile SKILL.md §5.4 with the eventual `scripts/report.py` CLI
  (I documented `report.py <hardened> --before <input> -o report.md` as the
  intended interface + a manual fallback).
- F4a: pin the SRI import map (item 3).
- F4b: decide the Voltage typing convention repo-wide (item 4).
- F5a: add `tools/check_skill.py` link checker (item 1) to the verify loop.
