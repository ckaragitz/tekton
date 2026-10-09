# #1062 -- the notes name the size the user gave; the snap boundaries are read back

## What changed
These are the nits from #1053's fifth independent review; its verdict was NITS, and the file was
already correct.
- **The GIVEN note names the size the user gave**, and the size built where a snap changed it:
  - `flush lap 0.02 in (built 0 in)`;
  - `box thickness 0.01 in (built 0.03125 in)`.

  It used to print the built value as the given one.
- **A mounting height of `-0.0`** is read as 0, so no note says "-0 in".

## Evidence
`tests/test_panel_can_1047.py`: 58 passed. The 6 new cases pin:
- the note, both with and without a snap;
- the refusal of a box exactly 1/32 in below the floor;
- that a lap too short to build is no lap in the file: the trim size and bottom are read back equal
  to a lap of 0;
- that the room inside is measured with the wall as built.

Five single-line mutations each fail the file:
- the note printing the built size;
- the refusal floor `<=` → `<`;
- the short lap built at 1/32 in instead of 0;
- the inside check using the wall as given;
- the signed zero kept.

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/panel_can.py`;
  - `tests/test_panel_can_1047.py`;
  - this fragment;
  - the plugin mirror.
- Nothing is staged.
