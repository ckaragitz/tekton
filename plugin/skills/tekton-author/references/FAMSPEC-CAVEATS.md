# famspec caveats — what to say when a `route.py --rfa` family is delivered

Read only when the family you are writing a famspec for uses one of the
categories or shapes below. Everything here is a LABEL that rides with the
delivered `.rfa` (the deliverable rule); none of it is a reason to refuse.

## Category ids: most are now verified, a few are still inferred

`"category"` resolves through `_resolve_category` in
`lib/src/rvt/famgen/skeleton.py`, which tags each id itself; the evidence
behind each tag is `lib/src/rvt/famgen/category_facts.py`.

| status | categories |
|---|---|
| **template-verified** — the id comes from that category's own Revit family template, i.e. Revit's own declaration (issue #516) | `casework`, `door`, `window`, `mechanical_equipment`, `plumbing_fixture`, `specialty_equipment`, `data_device`, `fire_alarm_device`, `telephone_device`, `structural_framing`, `structural_column`, `structural_foundation`, `structural_stiffener`, `furniture_system`, `entourage`, `planting`, `parking`, `site`, `detail_item`, `profile`, `curtain_wall_panel`, `baluster`, `railing_support`, `railing_termination`, `duct_fitting` |
| **desktop-verified** — a family of ours has opened in that branch of Revit's category tree | `furniture`, `generic_model`, `lighting_fixture`, `electrical_equipment` (+ the `panelboard` / `switchboard` / `transformer` product sets), `electrical_fixture` |
| **sample-verified** — a real element in a Revit-born sample carries the id | `lighting_device`, `cable_tray_fitting`, `conduit_fitting` |
| **inferred** — a published BuiltInCategory constant nothing has exercised | `pipe_accessory`, `duct_accessory`, `cable_tray`, `conduit`, `communication_device`, `security_device`, `nurse_call_device` |

Set the real category either way — an inferred id is far more useful than
`generic_model`. Add the caveat line only for an **inferred** one: *"category
id inferred, not verified: tell me if it lands in the wrong branch of the
category list."*

**What "template-verified" does and does not buy.** It settles the *id* —
that is the number Revit itself puts on a family of that kind. It does not
prove *our* family appears under that branch of the Project Browser, which
is still a Revit-side observation. So a template-verified category needs no
"is this id right?" caveat, but a family in an unusual category is still
worth one line asking the user to confirm where it landed.

**Seven ids were wrong before #516 and silently built the wrong kind of
family** — most sharply, `fire_alarm_device` pointed at `OST_DuctTerminal`,
so asking for a fire-alarm device produced an *air terminal*, and
`security_device` pointed at Fire Alarm Devices. If you have delivered a
family in one of `casework`, `fire_alarm_device`, `telephone_device`,
`security_device`, `lighting_device`, `cable_tray_fitting`,
`conduit_fitting` from an older build, it carries the wrong category and
should be regenerated.

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
