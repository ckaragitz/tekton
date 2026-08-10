# loadcrash — why does Revit's `Insert > Load Family` crash on our generated family?

**PROOF-ONLY.** Dev probe, not product output. The `.rfa` binaries and the per-rung
`*.report.json` (which carry machine-absolute paths) are git-ignored; `ladder.json` is
the tracked manifest.

## The observation

2026-08-10, owner, desktop Revit 2026: the assembly-lane family
(`Back-to-Back_Trapeze_Pipe_Hanger_-_LOD_400.rfa`, 13 IFC products → 103 solids) **opens
fine and its strut slots are correct**, but **`Insert > Load Family` crashed Revit**.

That matters beyond this stream: "our generated families fail once they meet a project"
is the campaign's open cell (`docs/inbox/genesis-audit.md` #31–#48), and a *crash* — as
opposed to an audit rejection — is a new and louder signal than anything logged there.

## The ladder — one variable, solid count

Every rung goes through the SAME emit path (`rvt.frontdoor.famspec.build` / `.write`), so
the only difference between L1 and L2 is how many solids the family holds. All four are
validator-VALID with 0 errors and provenance-clean before they leave here.

| rung | solids | source |
|---|---|---|
| `L0_one_box` | 1 | no IFC at all — a bare `generic_model` box |
| `L1b_four_solids` | 4 | the hanger's two struts + two end caps |
| `L1_hanger_13_solids` | 13 | the hanger, decomposition OFF (one solid per IFC product) |
| `L2_hanger_103_solids` | 103 | the hanger as shipped, decomposition ON |

## How to read the result

- **L0 crashes** → the generated family *document structure* is at fault; nothing to do
  with the IFC lane, and it belongs to the open cell rather than to this stream.
- **L0/L1b/L1 load, L2 crashes** → it is SCALE. Cap solids per family and re-test.
- **L0 loads, L1 crashes** → something specific to the assembly lane's geometry.
- Any **dialog text** Revit shows is worth more than the pass/fail: that is the signal
  issue #16 has been waiting for.

A counter-observation already in hand: our own four-registry loader (`route run --output
rvt --rfa <file>`) puts the same family into a project with the **project validator at 0
errors**, and that lane has certified precedent (`L1a`, `stage_L8_lp4`). So the failure is
specific to Revit's own Load Family path, not to the family being in a project.

## Rebuild

```bash
LADDER_IFC=/path/to/trapeze-hanger.ifc .venv/bin/python experiments/ifc-assembly/loadcrash/build_ladder.py
```
