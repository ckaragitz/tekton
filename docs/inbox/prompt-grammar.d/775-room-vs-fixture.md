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

**Two** taxonomy rows are affected, not one — the first draft of this record
said one, and the independent review measured otherwise:

- `water_closet`, whose label contains `closet`;
- `lavatory`, via its folded alias `bathroomsink` — because `_RE_ROOM`
  (`prompt_intent.py:204`) has a trailing `\b` on the noun group but **no
  leading one**, so `room` also matches *inside* `bathroom`.

Measured, main → head: `a bathroom sink` went from `room=Electrical Room,
src='room'` to the taxonomy's `'bathroom sink' -> Lavatory: Plumbing Fixtures`;
`a bathroom sink in an electrical room with 6 panels` bound its room to
`src='room'` (the letters inside "bathroom") on main and binds it to
`src='electrical room'` at the head. Both are improvements, and the second is
one this change was not aiming at.

The missing leading `\b` is left alone deliberately: adding it would stop
`a bathroom` resolving to a room at all, which is a bigger behavioural question
than #775 and has no measurement behind it yet. `_RE_ROOM` has no consumer
outside `_pick_room`.

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

## Hard rule 1 — what actually changes, stated plainly

The diff adds no refusal logic: on the `rvt` lane the `PromptError` is caught
into `res.errors` (`frontdoor/__init__.py:502`) and `router.py:1015` catches
`_StepFailed` and falls through to the taxonomy-build / archetype lanes.

But the observable result for this one prompt **does** change, and the first
draft of this record glossed it. Measured with
`tools/frontdoor.py author --prompt "a water closet"`:

| | main | this head |
|---|---|---|
| file | `prompt_room.rvt`, **581,632 bytes**, VALID / 0 errors, stamped `PROOF-ONLY` | **none** (`"this_file": "not-built"`) |

So a `.rvt` that main produced is gone. Two things make that the right trade,
and a reader should weigh them rather than take the verdict on trust:

1. **What main delivered was a fabrication.** The prompt says "water closet";
   the file was a 30 × 20 ft Electrical Room with no items, dimensions invented
   by the default. Handing that over is the silent substitution rule 1's second
   sentence forbids, not the delivery its first sentence requires.
2. **`a lavatory` already behaves exactly this way on main.** This makes
   `water_closet` consistent with every other unbuildable plumbing row — rows
   `prompt_battery` already blesses — rather than carving out a new exception.

The `rfa` lane and the archetype lane are untouched.

## Latency — a regression found in review and fixed

The first version of this change scanned the taxonomy twice per parse
(`_pick_room` and the `kind_mentions` filter each calling `TX.scan(text)`).
Measured over 50 parses of
`an electrical room 30 x 20 ft with 6 lighting panels and a 75 kVA transformer`:

| | run A | run B |
|---|---|---|
| `main` | 0.78 ms | 0.757 ms |
| this change, **double scan** | 0.91 ms (**+17%**) | 1.017 ms (**+34%**) |
| this change, **scanned once** | 0.762 ms | 0.738 ms |

Three independent measurements on the same box, two by reviewers and one by
the author. They disagree on the *size* of the double-scan penalty — +17% and
+34% — which is what a sub-millisecond benchmark on a shared machine looks
like, and the reason the range is printed rather than the flattering figure.
What all three agree on is the part that matters: scanning twice cost a
measurable amount, and scanning once puts the parse back at `main`'s level
(within noise of it).

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
- Gates: stream-local **9 passed**;
  `pytest tests/test_prompt_intent_775.py tests/test_frontdoor.py tests/test_router.py`
  → **245 collected, 0 failed** (passed/skipped splits as 235/10 here and
  230/15 on the reviewer's box — the skip count depends on which sample files
  are present, so the total is the number worth pinning);
  `prompt_battery --rows` **99/100 → 100/100**; `sync_plugin.py --check` clean.
- Shipped: the selection rule and the single-scan fix.
- Staged, not shipped: nothing.
- Not done: the general ordering hazard above — no issue filed, since nothing
  measures it today.
