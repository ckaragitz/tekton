# prompt-grammar / #775 — a room noun inside a product name is a product

Fragment of the `prompt-grammar` stream (index: `docs/inbox/prompt-grammar.md`).
Nobody else appends to this file. Closes #775.

## What was wrong

`create a Water closet family` built a **default 30 × 20 ft Electrical Room**.

`_ROOM_NOUNS` carries `closet` — correctly, because "electrical closet" is a
room this route builds — and `_RE_ROOM.search` (`prompt_intent.py:1211`) ran
**before** the taxonomy scan (:1421). So the room regex matched the `closet`
inside a *fixture* phrase, swallowed the noun, and the route answered with its
generic `no family plan in this prompt could be built` line.

Two failures in one: a fixture request silently became a room with invented
dimensions, and the user lost the taxonomy's own honest refusal naming the
fixture and its Revit category.

## What was built

`_pick_room()` returns the first `_RE_ROOM` match whose **noun span** does not
fall inside a taxonomy mention. The test is on the noun span, never the whole
match — which is what keeps `a transformer vault` a room: it overlaps the
`transformer_dry` mention on its *prefix*, not on its noun.

The blast radius is exactly one taxonomy row. `water_closet` is the only row
whose label or aliases contain a `_ROOM_NOUNS` word (grep of
`src/rvt/famgen/taxonomy.py`), and `_RE_ROOM` has no consumer outside
`_pick_room`.

## Evidence (measured, not claimed)

| prompt | before | after |
|---|---|---|
| `create a Water closet family` | room = Electrical Room, 9.144 × 6.096 m, invented | `recognised, NOT built by this route: 'Water closet' -> Plumbing Fixtures` |
| `a water closet next to a transformer vault` | Electrical Room **+ a phantom `transformer` item** | Transformer Vault, `unbuilt=['water closet']`, no phantom |
| `water closet room` | fixture silently swallowed | room + `unbuilt=['water closet']` |
| `an electrical room with a water closet` | Electrical Room + unbuilt | **unchanged** |
| `a transformer vault with a 400 A panel` | Transformer Vault + 1 panel | **unchanged** |
| `electrical closet` / `janitor closet` / `a closet` / `a mechanical space` | rooms | **unchanged** |

`tools/prompt_battery.py --rows`: **99/100 → 100/100**; the one failing row was
`row:water_closet`. Reverting the single hunk returns it to 99/100 — the
anti-vacuity check (#674 round 5).

**Hard rule 1 holds through pre-existing plumbing, not new refusal logic.** On
the `rvt` lane the `PromptError` is caught into `res.errors`
(`frontdoor/__init__.py:502`) and `router.py:1015` catches `_StepFailed` and
falls through to the taxonomy-build / archetype lanes. Worth stating plainly
because the diff *looks* like it adds a refusal: it does not — it replaces a
**generic** failure with the taxonomy's **named** one.

## Latency — a regression found in review and fixed

The first version of this change scanned the taxonomy twice per parse
(`_pick_room` and the `kind_mentions` filter each calling `TX.scan(text)`).
Measured over 50 parses of
`an electrical room 30 x 20 ft with 6 lighting panels and a 75 kVA transformer`:

| | mean |
|---|---|
| `main` | 0.78 ms |
| this change, double scan | 0.91 ms (**+17%**) |
| this change, scanned once | **0.762 ms** |

`parse_prompt` now scans once and passes the mentions into `_pick_room`, which
still scans for itself when called standalone. Plugin-path latency is a
standing product requirement, not internal cleanup (S-2026-08-09-g), so a
+17% parse was not acceptable for a one-row fix.

## Findings

- **The ordering was the bug, not the regex.** Any scan that consumes spans
  before the taxonomy has been consulted can eat a product name. `_pick_room`
  fixes the one instance; the general shape (`consumed`/`taken` bookkeeping
  running in a fixed order) is unchanged and could bite again in another
  clause.
- Found by `tools/prompt_battery.py`, not by a user — steer #765 (sessions test
  and debug everything themselves) working as intended.

## BRANCH STATE

- Branch: `cam/prompt-room-vs-fixture`, from `main` @ `0119d6b`.
- Files written: `src/rvt/frontdoor/prompt_intent.py` (+ its mirror),
  `tests/test_prompt_intent_775.py`, `tests/ci_shard.d/775-prompt-room-vs-fixture.txt`,
  this record.
- Gates: stream-local **9 passed**; with neighbours (`test_frontdoor`,
  `test_router`) **228 passed / 17 skipped**; `prompt_battery --rows` **100/100**;
  `sync_plugin.py --check` clean.
- Shipped: the selection rule and the single-scan fix.
- Staged, not shipped: nothing.
- Not done: the general ordering hazard above — no issue filed, since nothing
  measures it today.
