# Examples — the two acceptance use cases, delivered

These are complete, real deliverable bundles produced by running the
`tekton-ifc` engine end to end on the two acceptance use cases (both from
the family's actual Claude Design work). Every number in a
`DELIVERY-REPORT.md` was printed by a validator, not estimated. Use them as
(a) proof of what the plugin delivers today, and (b) copy-paste templates for
your own jobs. The overview across both is `USECASES-OVERVIEW.md`.

> These folders mirror the repo's `usecases/` tree (produced by the
> use-case runner). To refresh them after re-running a use case:
> `rsync -a usecases/<case>/ plugin/examples/<case>/`

## 1. `chicago-plenum-electrical-room/` — DDOT Coolidge, Area E bus-storage electrical room

The real Claude Design IFC export (6 panelboards, 3 transformers, trapeze
hangers, room shell). Demonstrates BOTH delivery paths on one real job:

| File | What it is |
|---|---|
| `original.ifc` | as exported by Design v1 — 31.4/100, Tier 0 (frozen blobs at the origin) |
| `hardened.ifc` | after `/tekton-harden` — 89.0/100, Tier 1 (partial): extrusions + true insertion points recovered, shared types created, GlobalIds preserved |
| `room-spec.json` → `generated.ifc` | the same room regenerated from a parametric spec — 100.0/100, Tier 1 |
| `validation-before/after.json`, `harden-report.json`, `DELIVERY-REPORT.md` | the machine reports and the customer-facing delivery |

## 2. `eaton-panelboard/` — Eaton Pow-R-Line 4 (style) panelboard, parametric

The single-equipment product model from `panel-meta.js`: 480Y/277 V,
3-ph 4-wire, 400 A bus, main breaker, 42 spaces, 65 kA, surface mount;
enclosure **W 0.508 × H 1.372 × D 0.190 m**.

| File | What it is |
|---|---|
| `panel-spec.json` | the full parametric definition (one `equipment` entry, `PanelSchedule` + `Pset_ElectricDistributionBoardTypeCommon` psets, `Pset_ManufacturerTypeInformation` type pset) |
| `panelboard.ifc` | generated from the spec — 98.8/100, Tier 1, IFC4 0 errors, real insertion point, one shared type |
| `panelboard-shared-parameters.txt` | the firm's Revit shared-parameters file (group "Panelboard") the psets are named to match |
| `panelboard-validation.json`, `DELIVERY-REPORT.md` | validation and the delivery report incl. the pset → shared-parameter mapping |

## 5-minute quickstart — regenerate the Eaton panelboard yourself

This is the same command the delivery ran. From the plugin root, with a
Python that has `ifcopenshell` (one-time: `pip install -r
skills/tekton-ifc/scripts/requirements.txt`):

```bash
mkdir -p out
python skills/tekton-ifc/scripts/generate_ifc.py \
    --spec examples/eaton-panelboard/panel-spec.json \
    -o out/eaton-panelboard.ifc --validate
```

You should see the validator finish with `score : 98.8/100`, `tier : Tier
1`, `schema : IFC4 errors=0`, and one `IfcElectricDistributionBoard`
(`PANEL-A`, type `Eaton Pow-R-Line 4 (style) - 400A MB - 42 space`,
`mapped(swept)` geometry). Then in Revit: **Insert → Link IFC** →
`out/eaton-panelboard.ifc`, Positioning "Auto – Origin to Origin"; bind the
parameters using `panelboard-shared-parameters.txt` (see
`DELIVERY-REPORT.md` §"Making the data land as your firm's shared
parameters"). Change any value in `panel-spec.json` (voltage, circuits, the
panel name) and re-run — the export is deterministic and repeatable.

## What these examples are honest about

Both are **Tier 1**: correctly-categorized, correctly-placed,
true-dimension elements carrying your schedule data as parameters. Neither
contains MEP connectors, circuits or a Revit-native Panel Schedule view —
IFC never can. That "Tier 2" is the native-`.rvt` element-creation work
tracked in the `tekton-native` skill (in progress); the specs here (`room-
spec.json`, `panel-spec.json`) are already the exact input that path will
consume, so nothing you enter today is thrown away.
