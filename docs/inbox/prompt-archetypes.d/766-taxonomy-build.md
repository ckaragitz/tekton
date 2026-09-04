# 766 — the wire from a recognised kind to its constructor

Closes #766. Stream: `prompt-archetypes`.

## The gap, measured

`make_luminaire(kind="recessed-troffer", size="2x4")` is that constructor's
**default configuration**; the taxonomy scans "a 2x4 recessed troffer light
fixture" to `['troffer', 'luminaire']` and holds
`{"kind": "luminaire", "fixture": "recessed-troffer"}` — and the route
answered *FAILED (no family plan …)*. The knowledge and the constructor
existed; nothing consulted the hint.

## The wire

`frontdoor/taxonomy_build.py`: `plans(prompt)` turns taxonomy mentions whose
row is `builder_available()` **and** carries a famspec hint into constructor
plans, deduped per famspec (troffer + its parent luminaire build ONE family).
Validation and constructor renames go through **`famspec.normalise` — one
law**, not a second rename table (the first cut re-implemented it and broke
on `fixture`). The router runs the lane between the scene grammar and the
archetype lane: catalog-backed constructors outrank nominal generation
(steer #591 DONE 6), and unbuildable kinds yield no plan, so the #692
refusal relay keeps the floor untouched.

Prompt tokens ride along only where read honestly: `2x4`/`2x2` → `size`,
`38W` → `wattage`, `3500K` → `cct`. Absent stays absent — the constructor's
nominal defaults are the point.

## The substitution guard, caught before shipping

The troffer catalog resolver is binary: `"2x4"` → 2BLT4, anything else →
2BLT2 **which is the 2x2**. Passing `size="4x4"` through delivered a 2x2
wearing the caller's size (measured: variant `2BLT2`, subject `… 4x4`) — the
exact steer #591 substitution. Unsupported sizes are now HEARD but not
passed: the default member delivers with the first caveat and a status
suffix — *"NOT at the size you named"* — never silently.

## The prompt battery (steer #765 / DONE 2)

`tools/prompt_battery.py`: 17 fixed prompts users actually typed (the
owner's own "generate me a rfa troffer light" first) plus **every taxonomy
row** prompted by its own vocabulary. The law: a row that claims a builder
must DELIVER; anything else must refuse WITH the taxonomy's line; a crash
never holds the line. **100/100 held** after two of the battery's own bugs
were fixed (`builder_available` returns a tuple, and `bool((False, why))` is
True — every unbuildable row briefly looked like a broken claim).

## Evidence

- The owner's failing prompts now deliver: troffer 2x4 / "generate me a rfa
  troffer light" / 4x4 (loud) / 2x2+38W+3500K / downlight.
- Refusal relay intact: VAV box fails WITH "NOT buildable here" (#692 test
  green); archetype lane untouched (cable tray 16-part).
- 410 tests passed, 8 skipped across taxonomy_wiring_692 / router /
  archetypes / taxonomy_build_766; 100/100 prompt battery; sync deny-audit
  clean.

## BRANCH STATE

Files: `src/rvt/frontdoor/taxonomy_build.py` (new), `src/rvt/frontdoor/router.py`
(the lane), `tools/prompt_battery.py` (new), `tests/test_taxonomy_build_766.py`
(11 tests) + shard drop-in, this record. Gates above; all shipped.
