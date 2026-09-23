# 831 — "13/16 in" was read as 1 3/16 in, and a "3/0" sheet row failed the pdf route

Stream: **prompt-archetypes** (fragment; index `../prompt-archetypes.md`).
Issue **#831** (P0), branch `cam/831-fraction-parse`. Found by the independent
reviewer of #828 (round 2); on `main`, not caused by #828.

## The defects

**1. The prompt route misread every fraction with a two-digit numerator.**
`archetypes._to_number` removed all whitespace first, so "1 3/16" and "13/16"
became the same string. The mixed-number pattern `(\d+)[-\s]?(\d+)/(\d+)` ran
first, with an **optional** separator, and won:

```
main:  "strut channel 13/16 in tall"  ->  height_in = 1.1875  given   (13/16 = 0.8125)
main:  "strut channel 15/16 in tall"  ->  height_in = 1.3125  given
```

13/16 in is a standard shallow-strut depth, so this is a realistic prompt: a
wrong number stamped `given`, the same class as #812.

**2. The spec-sheet route crashed on a zero denominator.** Found while checking
whether any other parser shares defect 1 (it does not: `sheet._MIXED` requires
its separator). `sheet._num` divided by the denominator unguarded. "3/0" and
"4/0" are everyday AWG sizes on electrical sheets:

```
main:  read_sheet(<a sheet whose Width row says "3/0 in">)  ->  ZeroDivisionError
main:  route --pdf that.pdf --prompt "a lighting control panel" --output rfa
       ->  FAILED (pdf->sheet: ZeroDivisionError: division by zero), no file
```

No file breaks hard rule 1. `_to_number` already had this guard, with a
comment giving the same reason. The sheet reader was written later and never
got it.

## Fix

- `_to_number`: normalises whitespace and no longer deletes it. A mixed number
  needs its separator (a hyphen, a space, or " - "). Commas are removed only as
  digit grouping (`1,200`), so `12,00` is now `None` rather than 1200. The prompt
  regex `_NUM_CORE` never produced that string anyway.
- `sheet._num`: a zero denominator returns `None`. The row is then reported as
  "not a single quantity … left unset" by the existing path, and the route
  delivers.

## Evidence

`tests/test_fraction_parse_831.py`, 30 tests:
- every n/d with n in 1..99 and d in {2, 4, 8, 16, 32, 64}, plain and as mixed
  numbers (whole numbers 1, 2 and 12; separators `-`, space and ` - `),
  checked against `fractions.Fraction` for **both** parsers;
- zero denominators;
- grouping;
- six prompts end to end;
- the sheet reader and the pdf route on a synthetic sheet (`fixtures_pdf`, no
  vendor bytes) with rows "3/0 in" and "13/16 in".

```
fix:   30 passed
main:  12 failed, 18 passed   (a real `git archive origin/main` tree -- a first run
       with PYTHONPATH pointed at main silently imported the worktree's src via
       conftest.py, and "passed" there proved nothing)
```

| mutant (anchor asserted = 1, bytecode off) | result |
|---|---|
| separator optional again | killed (3) |
| strip every space first again | killed (4) |
| sheet plain fraction unguarded | killed (4) |
| sheet mixed number unguarded | killed (2) |

The neighbouring suites (spec-sheet, archetype, taxonomy) plus this one: **592
passed**. `sync_plugin.py --check` in sync.

**Seen, not in scope:** with that sheet and a prompt, the route falls back to the
archetype lane with "0 dimension(s) from the prompt". The sheet's readable
height (62 in) and depth (13/16 in) are not used, because the sheet does not
size a whole family. That is the #688 lane's existing rule, not a parse
defect. It is recorded here in case it is not intended.

---

## BRANCH STATE

**Files written**
- `src/rvt/famgen/archetypes.py`: `_to_number`.
- `src/rvt/specsheet/sheet.py`: `_num`, the zero-denominator guard.
- `plugin/lib/…`: mirrors (via `sync_plugin.py`).
- `tests/test_fraction_parse_831.py`: new, 30 tests.
- `tests/ci_shard.d/831-fraction-parse.txt`: new.
- this fragment.

**Gates**: 30 passed; 4/4 mutants killed; 592 passed across the neighbouring
suites; plugin in sync. Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: shipped. No file-format change; nothing to certify.
