# 825 — "a pump control panel" is not a panelboard

Refs #825 (Refs #805, #821; the shield it extends is #692, the recorded decisions #822).
Stream: `prompt-archetypes`.

## What was wrong

Four prompts returned a clean `OK` and an **Eaton PRL2X 225 A, 42-space, 480Y/277 V
panelboard** — a different product, carrying a real manufacturer's model, with nothing in
the status line saying a substitution had happened. Reproduced on `main` at `a2ff281`
before any change (`parse_prompt`, full table in the test module):

```
a pump control panel        BUILT=['panelboard']
a generator control panel   BUILT=['panelboard']
an elevator control panel   BUILT=['panelboard']
a BMS control panel         BUILT=['panelboard']
```

and three more this round measured that the issue had not listed:

```
a motor control panel       BUILT=['panelboard']
an irrigation control panel BUILT=['panelboard']
a VFD control panel         BUILT=['panelboard']
```

That is the silent substitution S-2026-08-11-c forbids, and worse than a refusal: a
refusal leaves the designer without a file; this handed them a file that looks right, is
named with a real model, and is the wrong equipment — it would be scheduled and circuited
as a panelboard.

## The mechanism, measured

The #692 taxonomy shield marks only the span the taxonomy **matched** as taken:

```python
taken += [(m.start, m.end) for m in kind_mentions if m.key not in _SCENE_KIND]
```

`taxonomy.scan("a pump control panel")` returns one mention, `pump` at chars 2–6. The
trailing `control panel` is **not** in a taken span, so the `panelboard` clause
(`panel\s*boards?|(?:electrical\s+|branch\s+)?panels?`) matched its last word. And
`scan("an elevator control panel")` and `scan("a BMS control panel")` return `[]` — those
are not taxonomy rows at all, so nothing was shielded.

"a fire alarm control panel" and "a protective relay panel" refused only because a
taxonomy row happened to claim the **whole** phrase — the same shield by accident, which
is exactly why #821 kept the `relay panel` alias until this landed.

## The fix: two halves, both needed

1. **No wrong file.** The `panelboard` clause no longer reads a bare `panel` preceded by
   `control`: `(?<!control\s)(?<!control-)panels?`. Fixed-width lookbehinds, which
   Python's `re` requires. `panel\s*boards?` is untouched — "control panelboard" is not a
   phrase anyone writes, and a real panelboard ask must keep working.
2. **The refusal says what it saw.** A `_CONTEXT_PATTERNS` row (`control_panel`,
   `control[\s-]panels?`) reports the phrase, so once the clause stops taking the words
   they are not silently dropped. Where the taxonomy carries the qualifier it names it
   (`pump`, `generator`, `VFD`); where it does not (`elevator`, `BMS`, `motor`), this row
   is the whole report — which is why it names the control panel rather than the qualifier.

Half 1 alone would satisfy "never builds a panelboard" while leaving the designer no
wiser than the wrong file did. Both are tested separately.

## After

```
a pump control panel        REFUSED ('pump' -> Pump: Mechanical...)
a generator control panel   REFUSED ('generator' -> Engine generator...)
a VFD control panel         REFUSED ('VFD' -> Variable frequency drive...)
an elevator control panel   REFUSED ('control panel' -> recognised, NOT modelled...)
a BMS control panel         REFUSED ('control panel' -> ...)
a motor control panel       REFUSED ('control panel' -> ...)
an irrigation control panel REFUSED ('control panel' -> ...)
```

**The control, which matters as much as the fix** — a blanket "panel never builds" would
break the route's main lane, so these are pinned too, and are unchanged:

```
two 225 A panels            BUILT=['panelboard', 'panelboard']
a lighting panel            BUILT=['lighting_panelboard']
a distribution panel        BUILT=['distribution_panelboard']
an electrical panel         BUILT=['panelboard']
a panelboard                BUILT=['panelboard']
a 225 A panel for the controls room   BUILT=['panelboard']   (the word alone never blocks)
```

**The tests were proved to catch the bug, not merely to pass.** With only half 1 reverted
(asserted applied before the run, `__pycache__` cleared, no `git stash` — #802):
`tests/test_control_panel_825.py` → **20 failed, 39 passed**. Restored → **59 passed**.
The 39 that stayed green are the controls, the other-generic-word sweep and the pinned
`outlet` gap, none of which depend on this change.

## DONE 4: no other generic word falls this way — and why, as a law

`taxonomy.AMBIGUOUS_ALONE` holds 13 words (`box drive duct gutter horn meter outlet panel
pipe register smoke switch wrap`). `AMBIGUOUS_ALONE` governs the **taxonomy scan** only; a
grammar clause runs regardless, which is the whole reason this issue existed. Of the 13,
exactly **two** are claimed by a `_KIND_PATTERNS` clause on their own:

```
'outlet'  claimed by ['receptacle_device']
'panel'   claimed by ['panelboard']
```

The other 11 have no builder clause to fall to, which is why `a pull box`, `a safety
switch`, `a water meter`, `an elevator box`, `a BMS switch` … all refuse (12 measured in
the test module). **So this pair is the complete exposure, not a sample** — and the law is
pinned as a test rather than a one-off sweep, so a new ambiguous word that becomes
claimable by a clause goes red.

### The `outlet` half is real, and is filed, not fixed here — #1065

The sibling is the same shape:

```
a medical gas outlet     BUILT=['receptacle_device']
a gas outlet             BUILT=['receptacle_device']
a compressed air outlet  BUILT=['receptacle_device']
a TV / cable / AV / fibre outlet   BUILT=['receptacle_device']
a BMS / elevator outlet  BUILT=['receptacle_device']
a data outlet            REFUSED      <- taxonomy has the row
a telephone outlet       REFUSED      <- same
```

A medical gas outlet is a gas fitting; a fibre/TV/AV outlet is a Data Devices component.
Neither is an Electrical Fixtures receptacle.

It is **not** fixed in this PR deliberately. The receptacle clause is a different product
surface and needs its own decision about which `X outlet` phrases genuinely **are**
receptacles (`duplex`, `quad`, `GFCI`, a bare outlet with a NEMA configuration) — doing
that badly would be worse than the gap. Per §4 it is a follow-up issue, not scope creep:
**#1065**, P1. It is pinned by a test here so it cannot drift unnoticed in either
direction; when #1065 lands that test goes red and is replaced by its module, rather than
#825 quietly appearing to have covered it.

Priority was filed on a measured distinction, not a feeling: the outlet item carries **no
manufacturer model** (`{'kind': 'receptacle_device', 'tag': 'R-1'}`), where #825 handed
over a branded Eaton PRL2X with catalog values. Hence P1 there, P0 here.

## DONE 2 — honestly, partially met

DONE 2 asked that a genuinely ambiguous bare name (`a relay panel`, `an LCP`) be
recognised **as ambiguous** and say which readings exist, so #821's `relay panel` / `lcp`
aliases could come off the lighting-control-panel row.

What is true after this PR: none of them builds a panelboard, each refuses, and each
refusal names what it read. What is **not** done: they still refuse as
`lighting_control_panel` via that alias — a single reading, not a statement of the two
(lighting vs. local control panel). So the aliases still cannot safely come off the row.

The P0 harm — the wrong, branded file — is gone, and the hole those aliases were shielding
is now closed by the clause guard rather than by the aliases, which is the part that
blocked #821. The ambiguity *report* is a separate, smaller piece of work and I have not
claimed it as done. It needs an "ambiguous: readings are X or Y" shape in the intent that
does not exist yet.

## Open questions

- Should `control panel` become a real taxonomy row (with #822's recorded decision) rather
  than a `_CONTEXT_PATTERNS` regex? That would let it carry a category and a per-kind
  decision, and would name the qualifier. It is the tidier home; this PR took the smaller
  change because the P0 was a wrong file shipping today.
- DONE 2's ambiguity reading, above.
- Does any **two-word** generic phrase (not a single `AMBIGUOUS_ALONE` word) reach a
  builder clause the same way? The law pinned here covers single words only.

## BRANCH STATE

**Files written**
- `src/rvt/frontdoor/prompt_intent.py` — the `panelboard` clause lookbehind, and the
  `control_panel` `_CONTEXT_PATTERNS` row (+19 / −1).
- `plugin/lib/src/rvt/frontdoor/prompt_intent.py` — generated mirror, via
  `tools/sync_plugin.py` (not hand-edited).
- `tests/test_control_panel_825.py` (new, 59 tests) + `tests/ci_shard.d/825-control-panel.txt`.
- this record.

No `pytestmark` leak guard: the #707 law is derived **by call**, this module enters no
release context, and the reverse law fails a module that takes the guard without entering
one.

**Gates** (commands as run; `__pycache__` cleared before each)
- `.venv/bin/python -m pytest tests/test_control_panel_825.py -q` — **59 passed**
- the same, with half 1 reverted — **20 failed, 39 passed** (the tests catch the bug)
- `.venv/bin/python -m pytest $(grep -rln 'parse_prompt\|prompt_intent' tests/*.py) -q`
  — **764 passed, 32 skipped, 1 xfailed** (all 21 modules that touch this surface)
- `.venv/bin/python -m pytest tests/test_conftest_scaffolding.py -q` — **29 passed**
- `.venv/bin/python tools/sync_plugin.py --check` — in sync, deny-audit clean, identity
  scan == allowlist (0 mismatches), assets verified
- `.venv/bin/python tools/dev/check_portable_paths.py` — **ok: 3578 tracked paths**
- `.venv/bin/python plugin/scripts/validate_plugin.py` — **PASS**, 25 assertions
- `python3 tools/dev/shard_list.py --print` — the new module is in the merged shard

The full suite was not run (§2: stream-local files only).

**Staged vs shipped:** shipped, and live on the prompt route immediately — this is a
refusal path, not a new capability, and it claims nothing about Revit. No `.rfa` is built
by any test here, so hard rule 4 is not engaged.

**Follow-up filed:** #1065 (the `outlet` half of DONE 4).
