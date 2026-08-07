# CRUD-COVERAGE — the honest capability matrix (create / read / modify / move / retype / delete)

tekton's mandate is that **everything must be creatable, editable AND
deletable.** Progress toward that is a MEASURED NUMBER, not a claim: the
research repo's coverage harness (`tools/coverage.py` over
`docs/coverage/matrix.json`) enumerates 28 element categories × 6 verbs,
and a cell only counts when a proof `.rvt` re-validates with zero errors
(and, for CERTIFIED, when Autodesk's own reader accepted that exact
file per the ledger `docs/coverage/viewer-certified.json`).

**Read this table to the user before promising any category.** Never
round a cell up. `MISSING` means no implementing function exists;
`UNPROVEN` means a function exists but no passing proof file.

## Snapshot 2026-08-03 (last full harness run)

Headline: **53.3% of applicable cells PROVEN** (81 / 152; CERTIFIED +
VALIDATES); **12.5% CERTIFIED** (viewer-accepted); regenerable 66.7%;
0 regressions, 0 failing proofs; 40 unproven, 31 missing, 16 not-applicable.

Legend: **CERT** = certified (validates + viewer-accepted) · **VAL** =
validates (0 errors, viewer pending) · **UNPR** = function exists, no
proof · **MISS** = no function · **NA** = verb does not apply · row% =
proven / applicable for the row.

| category | create | read | modify | move | retype | delete | row% |
|---|---|---|---|---|---|---|---|
| family_instances | CERT | VAL | CERT | CERT | CERT | CERT | 100.0 |
| walls | CERT | VAL | UNPR | MISS | MISS | CERT | 50.0 |
| floors_roofs_ceilings | UNPR | VAL | UNPR | MISS | MISS | UNPR | 16.7 |
| doors_windows | MISS | VAL | VAL | UNPR | UNPR | CERT | 50.0 |
| columns_beams | CERT | VAL | UNPR | UNPR | UNPR | VAL | 50.0 |
| curtain_walls | MISS | VAL | UNPR | MISS | MISS | UNPR | 16.7 |
| stairs_railings | MISS | VAL | UNPR | MISS | MISS | UNPR | 16.7 |
| rooms_spaces | CERT | VAL | VAL | MISS | NA | VAL | 80.0 |
| conduit | VAL | VAL | VAL | VAL | VAL | VAL | 100.0 |
| cable_tray | VAL | VAL | UNPR | UNPR | UNPR | UNPR | 33.3 |
| duct | MISS | VAL | UNPR | MISS | MISS | UNPR | 16.7 |
| pipe | MISS | VAL | UNPR | MISS | MISS | UNPR | 16.7 |
| fittings | VAL | VAL | UNPR | VAL | UNPR | VAL | 66.7 |
| wires | VAL | VAL | MISS | MISS | MISS | VAL | 50.0 |
| electrical_equipment | CERT | VAL | CERT | CERT | CERT | UNPR | 83.3 |
| electrical_devices | VAL | VAL | VAL | VAL | VAL | VAL | 100.0 |
| lighting_fixtures | CERT | VAL | UNPR | UNPR | UNPR | VAL | 50.0 |
| circuits_systems | CERT | VAL | VAL | NA | NA | UNPR | 75.0 |
| panel_schedules | VAL | VAL | VAL | NA | MISS | VAL | 80.0 |
| views_sheets | UNPR | VAL | VAL | NA | MISS | VAL | 60.0 |
| tags_annotation | VAL | VAL | CERT | MISS | MISS | VAL | 66.7 |
| levels | UNPR | VAL | CERT | NA | MISS | UNPR | 40.0 |
| phases | UNPR | VAL | UNPR | NA | NA | UNPR | 25.0 |
| types | VAL | VAL | VAL | NA | NA | UNPR | 75.0 |
| families | MISS | VAL | VAL | NA | NA | UNPR | 50.0 |
| materials | VAL | VAL | UNPR | NA | NA | UNPR | 50.0 |
| parameters | VAL | VAL | CERT | NA | NA | UNPR | 75.0 |
| worksets_links | MISS | VAL | MISS | MISS | MISS | UNPR | 16.7 |

Read is `VAL` across the board (every category decodes from a real
corpus file); the writer's strength is the electrical / MEP surface this
product targets (family instances, electrical equipment / devices,
conduit, fittings, circuits, panel schedules) and its weakness is
architectural depth (floors / roofs, curtain walls, stairs, ducts, pipes,
worksets). State that plainly for an electrical-room job: the room's
walls, its equipment, its circuits and its schedules are on proven ground;
its slab / ceiling / doors are not yet.

## The known harness caveats (also state these)

- **CERTIFIED cells are the trustworthy tier.** `VALIDATES` = our own
  Autodesk-free validator is clean; the Autodesk reader has not yet judged
  that exact file. The harness backlog (H1–H4) adds per-cell semantic
  checks so a green cell must ALSO prove its specific fact (diameter
  changed, instance moved, element gone), and separates the certified
  headline from the merely-validated one.
- The snapshot is dated. The live source of truth is
  `docs/coverage/matrix.json` + the ledger in the research repo; ask the
  orchestrator for a fresh run (`tools/coverage.py run`) before quoting a
  number to a customer.
- Two rows carry a viewer-behaviour caveat rather than a coverage gap:
  created walls historically emitted no baked geometry (LOAD passes,
  RENDER pending the wall B-rep authoring — `references/GENESIS-BASE.md`
  §3), and the walls + loaded-families COMBINATION is the open bug the
  front door degrades around (§3 there).
