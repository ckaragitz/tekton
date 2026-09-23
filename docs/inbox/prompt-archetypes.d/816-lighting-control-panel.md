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

## Review round 1 — `nits`, two fixed before merge

**Pattern collisions — fixed.** My archetype matched bare `relay panel` and
`\blcps?\b`. The reviewer ran four prompts through the route; on the branch each
returned `ok: True` with a *lighting* control panel, where `main` refused:
"a generator relay panel", "a protective relay panel", "a fire alarm relay
panel", "an AHU with an LCP" (in HVAC, LCP is a *local* control panel). That is a
different product under the requested name — S-2026-08-11-c's "never a silent
substitution", and this PR would have introduced it. I traced the *build* to the
archetype patterns and narrowed them to `lighting control panel` / `lighting
relay panel`; no collision prompt builds this product now, and tests pin all six
as must-not-resolve.

**My trace was incomplete, and round 2 caught it.** I checked
`taxonomy.resolve`, which matches whole phrases only and returned nothing. But
the route reads prompts with `taxonomy.scan`, which *does* match the row's
aliases `relay panel` and `lcp` inside a sentence. So the collision prompts no
longer build the wrong product, but each refusal still names the lighting
control panel, and after this PR describes it as "a family this engine
generates" (on `main` it said "no archetype generates it").

**The alias stays, on purpose.** I removed `relay panel` / `lcp` from the
taxonomy row to fix the wording, and "a generator relay panel" then built an
**Eaton PRL2X panelboard**: the prompt grammar reads any unclaimed "… panel" as a
catalog panelboard. On `main` the same substitution already happens for "a pump
/ generator / elevator / BMS control panel", with a clean `OK` status. The
ambiguous alias was the only thing shielding these prompts from it — "a
generator relay panel" and, per round 3, "a protective relay panel". A misworded
refusal is a lesser harm than a wrong, manufacturer-branded file, so the change
was reverted and the real fix is **#825 (P0)**: recognise genuinely ambiguous
names as ambiguous, and never let "… panel" fall to a panelboard.

**The Z axis was never checked — fixed.** The reviewer applied three Z mutations
that survived every test (top wall raised above the box, latch dropped to z = 0,
left wall full height overlapping the caps). The tests now pin the top and
bottom walls at [H−g, H] and [0, g], the side walls at [g, H−g], the back and
door full height, and the latch at mid-height. All three mutations now die, and
so does restoring either ambiguous pattern:

| mutant | dies in |
|---|---|
| top wall raised to z = H | 1 |
| latch dropped to z = 0 | 1 |
| left wall full height | 1 |
| bare `relay panel` pattern restored | 4 |
| bare `LCP` pattern restored | 2 |

Baseline and restore both **17 passed**.

**The caveat printed on this build — fixed.** `matrix.py:133` and `:502` list the
products the archetype registry generates, and that caveat was printed on the
lighting control panel's own output without naming it. Both updated. The rendered
`docs/product/PERMUTATION-MATRIX.md` does not carry that caveat text (0
occurrences of either version), so nothing to regenerate.

**Filed rather than folded in:**

- **#822 (P0)** — #816's DONE 5. Re-measured before filing: of 83 kinds, **78
  have a category, and 63 have no builder** on this branch (64 on `main`, so this
  PR closes exactly one), across electrical 12, lighting 11, fire alarm 6,
  technology 7, mechanical 15, plumbing 11, fire protection 1. `luminaire` is in
  the list although the matrix calls luminaires catalog-backed, so that one needs
  checking before it is counted as a gap.
- **#823** — a prompt naming two products builds only the catalog one:
  "a lighting control panel and a panelboard" delivers the panelboard and drops
  the panel. Reproduced; pre-existing on `main` per the reviewer.
- **#824** — the list of generated products is hand-written in several places
  (including `SKILL.md`, a hot file); derive it from the registry. Round 2 found
  a sixth, `docs/product/PERMUTATION-MATRIX.md:61`, which this PR updates.
- **#825 (P0)** — "a pump / generator / elevator / BMS control panel" silently
  builds an Eaton PRL2X panelboard on `main`. Found while fixing round 2.

The reviewer also noted this archetype inherits **#812**: "a lighting control
panel 48 in tall 4 in deep" resolves height 4 in, stamped `given`. Not introduced
here; #812's fix covers it.

The reviewer reproduced, independently: the refusal on `main` and delivery on the
branch, placement of every part at the defaults, the 6.75 in reasoning (the
factory takes depth as the bounding box's y-extent, `factory.py:1139`), all-
nominal provenance, #817 pre-existing, mirrors blob-identical, and the bare-unzip
plugin run (0.9 s, 233,472 bytes).

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
- `src/rvt/frontdoor/matrix.py` — the two lists of generated products name the
  lighting control panel (round 1).
- `docs/product/PERMUTATION-MATRIX.md` — its own list of generated products
  names the lighting control panel (round 1, with `matrix.py` -- the #821 commit message says so; this line said round 2 until #828's round-1 review).
- `tests/test_archetype_lighting_control_panel_816.py` — new, 17 tests: the lane
  and a strict builder probe, every naming resolving all-nominal, a stated size
  becoming given, the part set, placement by position (mounting plane, walls
  closing the box, door as the front face, latch proud of it on the right),
  refusal-by-name of an impossible sheet, the route end to end, and (round 1)
  six must-not-resolve prompts plus the Z placement of every part.
- `tests/ci_shard.d/816-lighting-control-panel.txt` — new.
- this fragment.

**Gates** (at the merged head `2f4b0b5`): archetype + taxonomy + router + new
module 385 passed / 5 skipped; session CI 3892 passed / 140 skipped / 4
xfailed; `sync_plugin.py --check` in sync. Full suite **not** run.
(Repaired by #812's PR: this block previously listed round-0 gates.)

**Shipped vs staged**: shipped. No viewer batch.
