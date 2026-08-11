# famspec caveats — what to say when a `route.py --rfa` family is delivered

Read only when the family you are writing a famspec for uses one of the
categories or shapes below. Everything here is a LABEL that rides with the
delivered `.rfa` (the deliverable rule); none of it is a reason to refuse.

## Category ids: five are desktop-verified, the rest are inferred

`"category"` resolves through `_resolve_category` in
`lib/src/rvt/famgen/skeleton.py`, which tags each id itself.

| status | categories |
|---|---|
| **desktop-verified** — a family of ours has opened in that branch of Revit's category tree | `furniture`, `generic_model`, `lighting_fixture`, `electrical_equipment` (+ the `panelboard` / `switchboard` / `transformer` product sets), `electrical_fixture` |
| **inferred** — Revit's published BuiltInCategory constants, not yet seen opening under that branch (issue #516) | `mechanical_equipment`, `plumbing_fixture`, `specialty_equipment`, `casework`, `pipe_accessory`, `duct_accessory`, `cable_tray` / `cable_tray_fitting`, `conduit` / `conduit_fitting`, `lighting_device`, `fire_alarm_devices`, `data_devices`, `communication_device`, `security_device`, `nurse_call_device`, `telephone_device`, `structural_framing`, `structural_column`, `door`, `window` |

Still set the real category — an inferred id is far more useful than
`generic_model` — and add one line to the delivery: *"category id inferred,
not desktop-verified: tell me if it lands in the wrong branch of the
category list."*

**`door` / `window` carry a second caveat.** Revit's own doors and windows
are wall-HOSTED families that cut their opening; ours are free-standing
bodies filed under Doors / Windows (hosted-family scaffolding is not built).
Their standard set is mostly Revit built-ins (`Width`, `Height`, `Rough
Width/Height`, `Sill Height` …) which tekton lists but never authors —
`go make_family.py standards door` shows 6 authored parameters and 11
"Revit provides it" rows, and Revit provides them only if it really treats
the family as a Door, which is the unverified part. Fine for a door leaf,
hatch or unit as an *object*; not a placeable, wall-cutting door. Say so.

## Shapes: what is exact, what is drawn-only, what is approximated

| `shape` | what the file carries | say |
|---|---|---|
| `box`, `polygon`, `cylinder` (vertical) | one extrusion, exact | nothing extra |
| `cylinder_x`, `cylinder_y` | a TRUE cylinder lying along X / Y **as drawn**: the form is authored vertical and its cached B-rep frame is rotated onto the axis (desktop-verified round in the Front elevation, #591 round 4). The sketch underneath is still vertical, so Revit may regenerate the body upright the first time the form is edited — not measured either way. | "the wheels/pipe runs are true cylinders as delivered; do not edit those forms in the family editor — they may stand back up" — never promise they stay editable as drawn |
| `sphere`, `dome`, `cone` | a STACK of discs (`segments`, default 16, max 64), each sized at its mid-height; the result reports authored ÷ true volume, e.g. at 16 segments sphere 1.002, dome 1.0005, cone 0.999 (a mid-sampled stack over-fills a sphere/dome slightly and under-fills a cone) | "approximated as N stacked discs (volume ratio R)" — quote the ratio from the result, not an adjective |
| a curved outline you polygonised yourself | your polygon, exact to what you wrote | that you approximated it, and with how many points |

True spheres and editable rotated forms need element classes the engine
does not author yet; until then the rows above are the honest story.
