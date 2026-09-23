# 816 — a prompt for a lighting control panel builds one instead of refusing

Stream: **prompt-archetypes** (fragment; index `../prompt-archetypes.md`).
Issue **#816** (P0), branch `cam/816-lighting-control-panel`. Found by **the
owner's own use-case test** — "create a Lighting Control Panel for me an RFA" —
not by the loop.

## The defect

From a clean `git archive` of `main` at `f7710b3`, `rvt.__file__` printed:

```
$ tools/route.py run --prompt "create a lighting control panel family" --output rfa --json
exit=3   ok: False   files: {}
status: FAILED (prompt->intent: ... 'lighting control panel' -> Lighting control / relay
        panel: Electrical Equipment; NOT buildable here -- ... no catalog record is held
        and no archetype generates it ...)
```

It recognised the product and named its Revit category correctly, then withheld
output: hard rule 1, and S-2026-08-10-e ("not a refusal").

**Cause:** `taxonomy.py:167` registered the kind with **no mechanism**, so its
lane derived to `none` (`taxonomy.py:102`), and `archetypes.py` had no builder.

## What was built

A `lighting_control_panel` archetype and its taxonomy link
(`archetype:lighting_control_panel`).

- **Parts** (S-2026-08-10-e, LOD-400 — real parts, not a labelled box): back,
  four walls, door, and a latch on the door's right edge.
- **Upright**: the back sits on the mounting plane (y = 0), the cabinet projects
  toward −Y, and the height runs along Z — so the family's Front elevation shows
  the door. (`junction_box` lies face-up with its cover toward +Z; a wall cabinet
  does not.)
- **Nominal sizes for the product CLASS**, each stamped `nominal` with its basis
  and overridable by the prompt: 20 in wide (the standard panelboard cabinet box
  width), 30 in tall, 6 in deep, 14 gauge (0.0747 in). No manufacturer dimension
  is claimed.
- **Category** `electrical_equipment`, standard values `Mounting: surface`,
  `Material: steel` — the same as the `wireway` archetype in that category.
- **Limits, stated in the archetype**: the relays, low-voltage section, barrier
  and knockouts are not modelled; the door is a solid panel, not hinged; a NEMA
  rating is a parameter slot, not a claim.

**Not substituted.** The nearest existing archetype, `junction_box`, is
`electrical_fixture` — wrong category, so it would have scheduled and circuited
wrong in Revit while wearing the requested name (S-2026-08-11-c).

## Evidence

Through the route, from this branch:

```
ok: True   status: OK (Lighting Control Panel - Surface: 7-part .rfa generated at
                       standard nominal sizes; 0 dimension(s) from the prompt, 4 nominal)
rfa: Lighting_Control_Panel_-_Surface_20_in.rfa   233,472 bytes
validator: 0 errors, 0 warnings     provenance scan: ok     category: Electrical Equipment
```

**Placement, not just count.** The report omits part positions, so a cabinet
whose seven parts were stacked at the origin would look the same by count. The
overall depth decides it: `overall_depth_in = 6.75` = 6 in cabinet + 0.75 in
latch, running from the mounting plane to the latch face. Stacked, it would be
5.85 (the walls' inner depth). The tests assert placement by position directly.

**Suites.** `test_famgen_archetypes.py` + `test_taxonomy_692.py`: **221 passed**
(217 before — the registry-wide parametrized tests picked the new entry up on
their own). With the new module: **234 passed**.

**The file was delivered to the owner before this PR went through review.**
Recorded because that is out of the normal order. The owner asked for a quick
test, and hard rule 1 is about output reaching the person who asked. The file was
validated first, and the owner was told it came from an unreviewed branch.

## Findings filed, not folded in

- **#817** — every archetype family stamps its overall dimensions `given` while
  every input was `nominal`. Pre-existing on `main` (reproduced on the cable
  tray), so not this PR's to fix; this PR's family carries it too.
- **#818** (owner steer), from the owner's verdict on the file: *"Very Good, but
  for the future you need to know NEC code in order to get the clearances on
  there"*, and *"clearances need to be toggleable within the family
  parameters"*. The clearance work is **#819** (the NEC 110.26 table as cited
  data) and **#820** (the clearance solid and a Show Clearance Yes/No parameter);
  the toggle's critical path is **#690**. This PR ships **without** clearances on
  purpose: it fixes a refusal, and holding a no-file bug until a feature lands
  would keep withholding output.
- #816's own DONE 5 — how many taxonomy kinds are recognised but have lane
  `none` and refuse the same way — is still open. This one was found because a
  human asked; the rest should be found by measurement.

## Two errors of mine along the way

- My first taxonomy test called `TX.kind(...)` and `TX.lane(...)`, which do not
  exist. The real API is `TX.get(key)`, `Kind.lane` as a property, and
  `builder_available(row, strict=True)` — the last a stronger assertion than the
  one I had guessed at, since it imports and proves the builder.
- The report's `center=[0, 0]` for every form was my own `.get` fallback, not
  data. I checked it against the overall depth before trusting either reading.

## Hard rule 4

Delivered and validated, **not certified**. No generated standalone `.rfa` of
ours is in `docs/coverage/viewer-certified.json`.

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py` — `_lighting_control_panel` builder and the
  `lighting_control_panel` registry entry.
- `src/rvt/famgen/taxonomy.py` — the kind now declares
  `archetype:lighting_control_panel` and a note.
- `tests/test_archetype_lighting_control_panel_816.py` — new, 13 tests: the lane
  and a strict builder probe, every naming resolving all-nominal, a stated size
  becoming given, the part set, placement by position (mounting plane, walls
  closing the box, door as the front face, latch proud of it on the right),
  refusal-by-name of an impossible sheet, and the route end to end.
- `tests/ci_shard.d/816-lighting-control-panel.txt` — new.
- this fragment.

**Gates**: 234 passed (archetype + taxonomy + new module); `sync_plugin.py`
mirrors regenerated; portable paths ok. Full suite **not** run.

**Shipped vs staged**: shipped. No viewer batch.
