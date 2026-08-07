# experiments/frontdoor — the multi-surface FRONT DOOR, worked end to end

Stream: **frontdoor** (2026-08-04). One entrypoint, three inputs:

```
python tools/frontdoor.py author --prompt "TEXT"           [--out DIR] [--strict] [--handoff-only]
python tools/frontdoor.py author --ifc FILE.ifc            [--out DIR] [--strict]
python tools/frontdoor.py author --rvt FILE.rvt --edit "TEXT|ops.json|JSON"   [--out DIR]
```

Every route lands in the SAME intent model (`rvt.ifc.intent.IntentModel`,
spec v2), the SAME build step (intent → our `.rvt` on the CERTIFIED GENESIS
BASE `G_ABPD`, sha256-pinned, never an Autodesk sample) and the SAME
deliverable manifest (`manifest.json` + `MANIFEST.md`). Every `.rvt` here is
**PROOF-ONLY** (self-checks PASS; the deliverability gate says NOT-DELIVERABLE
because the genesis lineage still carries Autodesk-derived expression — see
each manifest's `build.status_gate`). No viewer/Revit acceptance is claimed.

| worked example | route | what it proves | outputs |
|---|---|---|---|
| `prompt-electrical-room/` | `--prompt` (default degrade) | THE WORKED PROMPT — "an electrical room 30x20 ft rated for 2500 A service with a main switchboard, two 400 A distribution panels and four lighting panels" resolved by the built-in fallback parser (NO model call) into MSB + DP-1/DP-2 (Eaton PRL2X 400 A facts) + LP-1..4, a 9.144 × 6.096 m room, a feeder tree; 7 families generated + LOADED onto G_ABPD; 4 walls + 7 instances; combined file **STAMPED** `PROOF-ONLY: walls+families combination unverified` (the open bug); the PRIMARY-path handoff package (`scene-brief.json`, `HANDOFF.md`, `PROMPT_TO_IFC.md`) emitted alongside | `electrical_room_prompt.rvt` (VALID·0 err·coherent·identity PASS), `families/*.rfa` ×7, `intent.json`, `manifest.json/.md` |
| `prompt-electrical-room-strict/` | `--prompt --strict` | the same room DEGRADED to TWO coordinated files instead of one stamped file: `-shell.rvt` = the 4 walls on the base (the viewer-certified walls-only shape) and `-equipment.rvt` = the 7 loaded families + their instances (the certified load+placement shape); each passes its own self-checks | `electrical_room_prompt-shell.rvt`, `electrical_room_prompt-equipment.rvt`, `manifest.json/.md` |
| `ifc-electrical-room-2500a/` | `--ifc` | THE ELECTRICAL-ROOM IFC END TO END — the user's own three-d-stage IFC (`inputs/ifc/electrical-room-2500a.ifc`) resolved by `rvt.ifc.intent` (placement chains + world geometry + tagging-contract Pset join key): 12 products, 4 walls + 2 doors, 8 families (7 catalog + the honest house switchboard), 8 placed instances, the corroborated feeder tree; the four unmapped kinds (ground bus, conduit, service entrance, hangers) and the circuits blocker recorded as honest degradations | `electrical-room-2500a.rvt` (VALID·0 err·coherent·identity PASS), `families/*.rfa` ×8, `intent.json`, `manifest.json/.md` |
| `rvt-edit-room/` | `--rvt … --edit` | THE ROUND TRIP — the room we just authored is fully EDITABLE through the same front door: `"move DP-1 to 3,1,4.66; delete LP-4 with cascade; set level L1 - Ground Floor elevation to 0.5 ft"` parsed (names/tags resolved to ids from the file), planned by rvt.manipulate, ONE commit, structural + validation + identity + provenance gates PASS; DP-1 moved, LP-4 gone (6 instances remain), the level edited | `electrical_room_prompt.edited.rvt`, `ops.json`, `manifest.json/.md`, the job runner's own `.manifest.json` / `.validation.json` |

Regenerate any of them by re-running the command in its `MANIFEST.md`.
Record: `docs/inbox/frontdoor.md`. Engine: `src/rvt/frontdoor/`. Tests:
`tests/test_frontdoor.py` (31, incl. two end-to-end builds).
