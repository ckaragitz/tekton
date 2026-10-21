# #1067 -- no negative zero, and a note never prints a size like a different one

Stream **panel-can** (tech-lead session, 2026-10-13). Closes #1067. Refs #1063 #1053.

## What changed
These are the low findings of #1063's independent review (verdict NITS).
- **No negative zero.** Every size is read with `+ 0.0`. A flush lap of `-0.0` used to print
  "-0 in" and write the trim formulas with a negation around the 0 constant (`Width + -0'`).
- **A note never prints a size so that it reads as a different value.** A size is printed with
  more digits only when `:g` would read the same as a different value set beside it (the built size,
  or the 1/32 in threshold):
  - "box thickness 0.0312499999 in (built 0.03125 in)", where it used to read "0.03125 in (built
    0.03125 in)";
  - "flush lap 0.0312499999 in (built 0 in)", where it used to read "0.03125 in", the threshold
    itself.
- **A lap of exactly 1/32 in is a lap**, pinned by read-back.
- **The test comment** on the inside check says what it tests.

## Evidence
`tests/test_panel_can_1047.py`: 62 passed. The 4 new cases pin:
- the trim formulas read back identical for laps of -0.0 and 0.0, with no "-0 in" in any note;
- a 1/32 in lap's trim, read back as width + 1/16 in;
- both near-threshold notes.

Four single-line mutations each fail the file:
- `+ 0.0` dropped;
- the lap snap `<` → `<=`;
- the extra digits dropped;
- the threshold left out of the note's comparison.

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/panel_can.py`;
  - `tests/test_panel_can_1047.py`;
  - this fragment;
  - the plugin mirror.
- **Gates:** in the PR body. Nothing is staged for the viewer.
