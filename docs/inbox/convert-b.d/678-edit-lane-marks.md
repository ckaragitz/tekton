# 678-edit-lane-marks -- the family edit lane reads the trade's inch / foot MARKS: `Width=4"` → 0.3333 ft, `Depth=2'` → 2 ft, `1'6"` / `1' 6"` / `1'-6"` → 1.5 ft; a mark on a non-length spec refused by name; a bare number refused as before (convert-B stream, eng #678)

**Issue:** #678 (filed by eng #668; Refs #668 #659 #665 #660).
**Date:** 2026-08-11. **Session:** eng #678 (cloud, `cse_01HFvUTQBrkCD9rV1rNLy8VG`), started by the tech-lead session.
**Base:** `origin/main` @ ea6b875 (#679). Index: `docs/inbox/convert-b.md` (left untouched). Written in this engineer's
voice; no other record edited. The collaborator's session (clkaragitz) was live in `src/rvt/famgen/**` +
`src/rvt/frontdoor/**` throughout — both read-only here; the front door's NL `--edit` grammar (`rvt.frontdoor.edit`) is
theirs and out of scope. This is the structured `--set` path of `python -m rvt.convert.edit_family`, the JSON ops, and
`modify_family`'s own text grammar — all three share the one converter.

## Where exactly the mark was lost (proven at Python level, no shell involved)

`src/rvt/convert/modify_family.py:300` (as merged by #665/#680): `_convert_value` opened with

    txt = str(raw).strip().strip("\"'")

`str.strip("\"'")` removes quote characters from BOTH ends, so a TRAILING mark went before the number/unit regex
(`(-?\d+(?:[.,]\d+)?)\s*([A-Za-z\"']*)`, which would have captured it) ever ran:

| raw (the exact `str` the converter received) | after the strip | regex unit | result on `main` |
|---|---|---|---|
| `4"` | `4` | `''` | `Width is a LENGTH: give an explicit unit (in / ft / mm / m) -- units are never guessed` |
| `2'` | `2` | `''` | same refusal |
| `1'6"` / `1' 6"` | `1'6` / `1' 6` | no match | `Width: cannot read a number from "1'6"` |
| `"600 mm"` | `600 mm` | `mm` | 1.9685 ft (fine) |

Shell quoting was never the cause: `python3 -c 'print(repr(sys.argv[1]))' 'Width=4"'` prints `'Width=4"'`, and
`edit_family._flag_ops` splits on the first `=` only, so `4"` reached `_op_set` → `_convert_value` intact and died on
that line. `_UNIT_TOKENS['"'] = ("length", 1/12)` and `_UNIT_TOKENS["'"] = ("length", 1.0)` were always there and
`_converted_units()` always OFFERED both marks — the lane just could not accept what it offered.

## What landed (option (a) of the issue's DONE 1, compound included — it was six lines)

`src/rvt/convert/modify_family.py` — the value normalisation in front of the regex only; `_UNIT_TOKENS`, `_SPEC_UNITS`,
`_feet_specs`, `_converted_units()` and every refusal string are untouched.

1. **`_unwrap_measure(txt)`** replaces the blanket strip for numeric carriers: ONE pair of quotes that cleanly WRAPS the
   whole value comes off (`"600 mm"` → `600 mm`, `'4"'` → `4"`, `"2'"` → `2'`, `"4"` → `4`) and **nothing else is
   stripped** — so `4"`, `2'`, `1'6"` and the JSON-ops spelling `4 "` (`{"value": 4, "unit": "\""}` is normalised to
   `4 "` by `edit_family.normalize_ops`) reach the number/unit regex with their mark and hit `_UNIT_TOKENS` like any unit
   word, while every other quote arrangement reaches the regex verbatim and is REFUSED: `4''` (two apostrophes typed
   for an inch), `4'"`, `4""`, `600 mm"` name what they got (*Width is a length; got unit "''"* — the length row's
   wrong-kind wording for an unknown token; *no conversion for unit "''" on spec …angle…* off the table), and `''4''`,
   `'4''`, `"4""`, a stray `"600 mm` are *cannot read a number from …*. A pair whose inside starts or ends with the
   same quote (`'4''`, `''4''`) is deliberately **not** a clean wrap, so two apostrophes are never re-read as one foot
   mark. The first cut of this PR still carried main's leniency for stray quotes (leading quotes off, trailing quotes
   off unless a digit preceded them) and thereby collapsed `4''` / `4'"` / `''4''` to `4'` = 4 **feet** — a 12× misread
   the tech-lead review caught (S-2026-08-11-a); the leniency is gone, not patched. `m_str` keeps the old
   `strip("\"'")` byte-for-byte (`'DP-7'` → `DP-7`, and a text value ending in digit+quote still loses the quote exactly
   as on main).
2. **Feet-and-inches** `_RE_FEET_INCHES = (-?)(\d+)\s*'\s*-?\s*(\d+(?:\.\d+)?)\s*"` — `1'6"`, `1' 6"`, `1'-6"`,
   `0'4.5"`, `-1'6"` — is folded to inches (`18`, unit `"`) before the ordinary path **wherever a unit means something**
   (`measurable`: not an integer carrier, not Revit's unitless `number`, not spec-less — the same predicate the generic
   *no conversion for unit …* refusal already used, now named once and shared), so it converts through the ONE length
   row (sizes included, #668) and on any other measurable spec is refused by name exactly like a lone inch mark
   (`Operating Weight is a mass; got unit '"'`). Where a unit is *ignored* there is no one number written in `1'6"`, so
   it stays "cannot read a number" exactly as on main — never an 18 or a 1.5 the user did not type (a `/simplify`
   altitude finding, pinned by a test). The 12 is the table's own (`_INCHES_PER_FOOT = _UNIT_TOKENS["'"] / _UNIT_TOKENS['"']`
   factors, exactly `12.0`), not a second literal.
3. The conversion note quotes a mark the way it was typed — `Width: 4" -> 0.333333 ft (CAVEAT …)`, `Width: 2' -> 2 ft`,
   `Width: 18" -> 1.5 ft` — instead of `4 "`: a non-alphabetic unit hugs its number, unit words keep `600 mm` (one
   conditional on the shared line; every #665/#680 pinned note string is unchanged).

**Semantic consequences, all intended and all in the direction of "units are never guessed":** a mark is now a real
unit token on every measurable spec, so `BusRating=225"` (main: mark stripped, 225 A stored silently) is now refused as
*BusRating is a current (amps); got unit '"'*; `Fitting Angle=45"` (`aec:angle`, no conversion here; main stored 45
silently) is refused *no conversion for unit '"' on spec autodesk.spec.aec:angle …*; an `m_int` carrier notes *unit
'"' ignored (integer parameter)* for `3"` where main said nothing (and stores 3, as main did). A merely WRAPPED number
(`"4"`, `'2'`) is still a bare number and still refused on a length/size/mass with the pinned wording. Stray unmatched
quotes that main's blanket strip silently tolerated (`"600 mm`, `600 mm"`) are now refused by name instead — the price
of never reading `''` as a foot. `--set` refusals happen in `parse` before anything is written (exit 2, empty out dir)
— rule 1 is untouched: a successful edit always delivers, stamped.

## Evidence

**The real CLI, same argv on both sides** (`out/verify/tray.rfa` = a cable-tray fitting written the product's way via
`make_generic_model(category="cable_tray_fitting", standard_values={"Tray Width": 1.0, "Tray Height": 4/12})` +
`standalone_family_write`; `Width` is `aec:length`, `Tray Width` is `electrical:cableTraySize`):

```
argv value Python received: 'Width=4"'        main: ERROR: Width is a LENGTH: give an explicit unit (in / ft / mm / m) -- units are never guessed   exit=2, 0 files
                                               branch: delivered … family-mode validator: VALID (0 errors); re-read ok: True; Width current=0.3333333333333333
argv value Python received: "Width=2'"        main: same refusal, exit=2                       branch: VALID (0 errors); Width current=2.0
argv value Python received: 'Width=1\'6"'     main: ERROR: Width: cannot read a number from "1'6"   branch: VALID (0 errors); Width current=1.5
argv value Python received: 'Tray Width=1\' 6"'   branch: VALID (0 errors); Tray Width current=1.5
argv value Python received: 'Tray Width=4"'   main: ERROR: Tray Width is a LENGTH: …            branch: VALID (0 errors); Tray Width current=0.3333333333333333
argv value Python received: "Width=4''"       branch: ERROR: Width is a length; got unit "''"            exit=2, 0 files  (never 4 ft)
argv value Python received: 'Width=4\'"'      branch: ERROR: Width is a length; got unit '\'"'           exit=2, 0 files
argv value Python received: "Width=''4''"     branch: ERROR: Width: cannot read a number from "''4''"    exit=2, 0 files
```
Every edited `.rfa`: `tools/rvt_validate.py --family` → `verdict: VALID (no errors); warnings=0`, exit 0;
`tools/make_family.py provenance` → `ok=True suspects=0`. **Control:** `--set 'Width=4 in'` and `--set 'Width=4"'`
write byte-identical families — md5 `be215d7ae874baf8c8703786e4aa8d70` both (the manifests differ only in the note's
`4 in` / `4"`); the test module re-asserts the identity on `Width` and on `Tray Width`.

**Tests** — new module `tests/test_edit_family_marks_678.py` (50 tests) + drop-in `tests/ci_shard.d/678-edit-lane-marks.txt`
(`shard_list.py --print` lists it once, line 118). Tier 1 (pure converter): the eight forms (`4"`, `2'`, `1'6"`, `1' 6"`,
`1'-6"`, `'4"'`, `"2'"`, `4 "`) × {`Width` length, `Tray Width` size} with the exact note; marks are the table's own
tokens (`'"' == in`, `"'" == ft`); a mark / compound on a mass and on a current refused by name; bare and wrapped-bare
refused with #659's / #668's pinned wording × {length, size}; the issue's DONE 2 controls (`'DP-7'` on `m_str`,
`"600 mm"`) unchanged; `m_int` ignores a lone mark with a note; `1'6"` stays "cannot read a number" on an integer /
`number` / spec-less parameter; unreadable junk (`6"1'`, `1'6`, `1' x 6"`, `"600 mm`, `'4"`) still says "cannot read a
number"; the ambiguous arrangements (`4''`, `4'"`, `4""`, `600 mm"` by name; `''4''`, `'4''`, `"4""`, `"1'6""`
unreadable) × {length, size}, plus `45''` on an angle and `600''` on a mass, never yield a value; `_unwrap_measure`
itself pinned (one clean pair off, everything else verbatim). Helpers
(`_param`, `_cli_edit`, `_currents`, `_same_bytes`, `_assert_valid_and_ours`, `_write_fitting`,
`_assert_refused_and_nothing_written`) and every pinned string are imported from the #659 / #668 modules, not copied.
Tier 2 (on the written fitting through `edit_family.main`): `4"` / `2'` / `1'6"` / `1' 6"` × {length, size} read back in
feet via `inventory_family`, the raw value verbatim in the manifest's `edit`, VALID 0/0 + release preserved + re-read +
provenance clean, the neighbour of the other kind unmoved; the md5 identity control × 2; `Tray Width="4"`,
`Fitting Angle=45"`, `Width=4''`, `Width=4'"` and `Width=''4''` refused before anything is written (exit 2, empty dir,
the exact refusal is the last line); `Tray Type='Ladder'`
lands as `Ladder`; the JSON ops route inline (`{"value": "4\""}`, `{"value": "1'6\""}`) and structured
(`{"value": 2, "unit": "'"}` → `2 '` → 2.0 ft, note `2'`); the text grammar `set TrayWidth 4"` → 1/3 ft.

Gate counts: see BRANCH STATE and the PR body.

## Findings / open questions

* The decimal-comma oddity is pre-existing and untouched: `_RE_NUMBER_UNIT` accepts `1,5` and `.replace(",", "")` turns
  it into `15` (a thousands-separator reading). The compound regex deliberately takes `.` decimals only for the inch
  part so it does not inherit that. Not filed — nobody has typed a comma yet; whoever touches the number regex next
  should decide thousands vs decimal explicitly.
* `''` (two apostrophes typed for an inch mark) is **refused by name** (*got unit "''"* / *no conversion for unit "''"*),
  exit 2, nothing written — deliberately not mapped to inches (it is indistinguishable from a doubled foot mark, and a
  silent choice either way is a guess); the user re-types `4"` or `4 in`. `1'` `6"` given as two `--set`s is two edits
  of the same parameter (last wins), not a compound — not asked for.
* The `rfa_modify` matrix cell wording still does not enumerate units (parked on #660 by #659/#668); `route.py matrix`
  is byte-identical here by this issue's DONE.

## BRANCH STATE

* Branch `cam/678-edit-lane-marks` from `origin/main` @ ea6b875, rebased onto 40fd512 (#695) after review — no overlap.
  Files: `src/rvt/convert/modify_family.py`,
  `plugin/lib/src/rvt/convert/modify_family.py` (mirror via `tools/sync_plugin.py`), `tests/test_edit_family_marks_678.py`
  (new), `tests/ci_shard.d/678-edit-lane-marks.txt` (new), this fragment (new). The two existing edit-lane test modules
  are imported for helpers/pinned strings only, not edited.
* Gates: stream-local suite (`test_edit_family_marks_678 + _size_668 + _mass_659 + modify_family_carrier + convert +
  convert_combo + records_layout`, `RVT_SKIP_LARGE=1 -q -rs`): `main` 78 passed / 17 skipped (without the new module) →
  branch 128 passed / 17 skipped after the review fix (123/17 at the first head; the 17 skips are the pre-existing
  acceptance-fixture / `RVT_SKIP_LARGE` skips in `test_convert*.py`; every #665/#680 row green untouched); whole merged
  CI shard: see PR body (2481 passed / 135 skipped / 3 xfailed / 0 failed on the first head 86e54fe; re-run on the
  review-fix head reported there); `sync_plugin.py` run + `--check` clean ("plugin in sync with source");
  `validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok (3067 tracked paths after the rebase);
  `route.py matrix` md5 `e9e2cc8d7f15e6ce6b1d6c5a68e59502` on both sides.
* Shipped vs staged: engine + mirror + tests ship with the merge; nothing STAGED for the viewer (no certification claim —
  VALID is a fact about the file, rule 4); no hot file touched; famgen / frontdoor / `TRACKER.md` / `KNOWLEDGE.md`
  untouched; no follow-up issue needed (compound support landed here).
