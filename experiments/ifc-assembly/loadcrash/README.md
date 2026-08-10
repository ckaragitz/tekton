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

## RESULT (owner, desktop Revit 2026)

**L0 (1), L1b (4), L1 (13) all load. L2 (103) crashes.**

## …and why that does NOT yet say "scale"

**This ladder is confounded.** It claimed solid count was its only variable. It is not:

| rung | solids | shape mix |
|---|---|---|
| L1 | 13 | 9 box + 4 cylinder — **no polygons** |
| L2 | 103 | 87 box + 2 cylinder + **14 polygon** |

L1 → L2 moves count **and** introduces N-gon parts, so the crash could be either. An
earlier version of this file asserted "it is SCALE"; that was wrong and is retracted.
Reading the code weakens the shape hypothesis without excluding it — #515 removed the
regeneration fallback, so N-gons carry a cached B-rep exactly like boxes.

`build_pair.py` is the matched pair that separates them in two files:

| rung | solids | shapes | isolates |
|---|---|---|---|
| `P_boxes103` | 103 | box only | COUNT at L2's value, shape mix eliminated |
| `P_polys14` | 14 | polygon only | SHAPE at a count already known to load |

- `boxes103` crashes → count alone suffices; N-gons not implicated.
- `boxes103` loads, `polys14` crashes → N-gon parts are the cause, not count.
- both load → it is the combination, or something else in L2 entirely.
- both crash → two independent causes.

Any **dialog text** Revit shows is worth more than the pass/fail — that is the signal
issue #16 has been waiting for.

## Not a route to a fix: building a .rvt off the family

An earlier round offered a project our own four-registry loader had assembled with the
family in it. It **did not open**, and the owner's steer (#585) is explicit:
*"dont try to build a rvt off a family"*. Routing around Revit's own Load Family path is
not how this gets solved, and a `VALID / 0 errors` validator result never meant the file
worked (hard rule 4).

## Rebuild

```bash
LADDER_IFC=/path/to/trapeze-hanger.ifc .venv/bin/python experiments/ifc-assembly/loadcrash/build_ladder.py
```
