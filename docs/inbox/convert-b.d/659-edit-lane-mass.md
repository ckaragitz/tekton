# 659-edit-lane-mass -- the family edit lane converts a MASS (`lb` → kg via the factory's one constant), refuses a unitless mass like a unitless length, and stops calling measurable specs "dimensionless" (convert-B stream, eng #659)

**Issue:** #659 (Refs #630; follow-ups #660 spec registry — pre-existing —, #663 text grammar — filed here).
**Date:** 2026-08-11. **Session:** eng #659 (cloud, `cse_018s6HB2QR63P3a4ZDWtjQqT`), started by the tech-lead
session. **Base:** `main` after #661 (`_patch_partatom`, a different hunk of the same file) — rebased onto it before
the push, no conflict. Index: `docs/inbox/convert-b.md` (modify_family's originating record; left untouched — the
README makes the index line optional and that EOF is exactly the hot spot #636 exists to avoid). Written in this
engineer's voice; no other record edited.

## Why

#630 (merged as #662) made generated transformers carry a *filled* `Operating Weight`
(`autodesk.spec.aec.structural:mass-1.0.0`, stored in kilograms — Revit's internal mass unit — from the catalog's lb
via `factory.pounds` / `KG_PER_LB = 0.45359237`). The edit lane's spec-driven converter
`rvt.convert.modify_family._convert_value` had branches for current / potential / apparent power / length and then a
catch-all that stored the number as given and, if a unit was typed, appended *"unit 'x' ignored (dimensionless spec
…)"*. On the new mass parameter that meant `--set "Operating Weight=600 lb"` stored **600.0** (Revit reads 600 kg =
1323 lb, a 2.2× error) under a false note, and `=600` with no unit was stored silently although a unitless length is
refused ("units are never guessed"). Before #630 no generated family carried a filled mass, so #630 is what made this
user-facing (P1).

## What landed

`src/rvt/convert/modify_family.py` — the converter only (`_UNIT_TOKENS`, `_convert_value`, its note text, the module
docstring's conversion sentence); `_patch_partatom` and everything #661 touched left alone; no famgen edit.

1. **Mass tokens.** `_UNIT_TOKENS` gains `kg → ("mass", 1.0)` and `lb` / `lbs` / `lbm → ("mass", KG_PER_LB)` with
   `from ..famgen.factory import KG_PER_LB` at module top — the ONE constant (DONE 2; `git grep -n 0.4535 -- src/` →
   `src/rvt/famgen/factory.py:1548` only, pinned by a test that walks `src/rvt`). #660 will move the constant beside
   `volts`; the import moves with it.
2. **One explicit-unit branch for length and mass.** The length branch became a two-row table
   `_EXPLICIT_UNIT_SPECS = ((":length", "length", "in / ft / mm / m", "ft", <the geometry CAVEAT>), (":mass-", "mass",
   "lb / kg", "kg", ""))` driving one loop: no unit → `"<cap> is a MASS: give an explicit unit (lb / kg) -- units are
   never guessed"` (the length wording with the kind and offer substituted — the length strings are byte-identical to
   `main`, pinned); a unit of another kind → `"<cap> is a mass; got unit 'mm'"`; else `value × factor` with the note
   `"<cap>: 600 lb -> 272.155 kg"`. The marker is `":mass-"`, not `":mass"`, so `structural:massPerUnitLength` is not
   scaled by the pound (tested).
3. **The false note is unreachable for measurable specs.** After the specific branches, a unit on a spec that is not
   dimensionless (spec-less double or Revit's unitless `aec:number` — the units table formats it `unit:general`) is
   **refused by name**: `"<cap>: no conversion for unit 'hz' on spec autodesk.spec.aec.electrical:frequency-1.0.0 (this
   lane converts current a / amp / amps; potential v / volt / volts; length ft / … / m; apparent power kva / va; mass kg /
   lb / lbs / lbm) -- give the value in Revit internal units with no unit suffix; units are never guessed"` — the offer
   is generated from `_UNIT_TOKENS` (`_converted_units()`, /simplify) so it cannot fall behind the table; the prefix,
   "no unit suffix" and "units are never guessed" are what the test pins (DONE 1). A bare number on such a spec is stored as
   internal units exactly as before, and the `"unit 'c' ignored (dimensionless spec …number…)"` note survives only where
   it is true. **Decision recorded:** refuse rather than store-with-an-honest-note, because storing `100 W` as 100
   internal (= 9.29 W displayed) is a guessed unit and this lane's law is "never guessed"; and no new `internal` unit
   token was introduced (the issue floated `=<n> internal`) because a bare number already means internal units on every
   non-length/mass spec today and a token accepted on some specs but not others (current/potential check the kind) would
   be a wart — the refusal names the bare-number way forward instead. Reviewer may prefer otherwise; it is a one-line
   change either way.

## Evidence

**Read-backs, one #630 transformer** (`tools/make_family.py transformer --kva 30 --types 30,45,75`, VALID 0 errors,
provenance ok) edited with `python -m rvt.convert.edit_family <rfa> -o <dir> --set …`, value read back with
`inventory_family(...).param_by_caption(...)["current"]`, note = the manifest's `degradations`:

| `--set` | `main` @ 9152c86 | this branch |
|---|---|---|
| `Operating Weight=600 lb` | **600.0**, note `unit 'lb' ignored (dimensionless spec …mass-1.0.0)` | **272.155422** (= 600 × 0.45359237), note `Operating Weight: 600 lb -> 272.155 kg` |
| `Operating Weight=600 lbs` / `=600lbm` | (same as lb) | 272.155422, note names `lbs` / `lbm` |
| `Operating Weight=272.155 kg` | 272.155, note `unit 'kg' ignored (dimensionless …)` | **272.155**, note `272.155 kg -> 272.155 kg`; output `.rfa` md5 == main's (`40aa467b…`) — same bytes, honest note |
| `Operating Weight=600` | **600.0**, no note | **refused**: `ERROR: Operating Weight is a MASS: give an explicit unit (lb / kg) -- units are never guessed`, exit 2, no file |
| `Operating Weight=600 mm` | 600.0 (!), note `unit 'mm' ignored …` | refused: `Operating Weight is a mass; got unit 'mm'` |
| control `Width=600 mm` | 1.968503937007874 ft + the CAVEAT note | identical value, identical note, output md5 equal (`2e0ea6e8…`) |
| control `Width=600` | refused, `Width is a LENGTH: give an explicit unit (in / ft / mm / m) -- units are never guessed` | identical string |
| control `Temperature Rise=115 C` (number spec) | 115.0, note `unit 'c' ignored (dimensionless spec autodesk.spec.aec:number-1.0.0)` | identical value + note, output md5 equal (`8c3f93a7…`) |
| `Frequency=60 Hz` (measurable, no conversion) | 60.0, note `unit 'hz' ignored (dimensionless spec …frequency-1.0.0)` — false | **refused by name** (the wording in item 3) — the one deliberate behaviour change beyond mass; `Frequency=60` → 60.0, no note, as before |

Every successful edit above: `tools/rvt_validate.py --family` → `VALID (no errors); warnings=0`, `tools/make_family.py
provenance` → `"ok": true`; the route's own gates in each manifest: family-mode VALID 0 errors, release preserved,
re-read ok, structural_ok. Validator-green is a fact about the file, not evidence Revit opens it (rule 4); no
certification claimed, ledger untouched.

**Tests** — new module `tests/test_edit_family_mass_659.py` (22 rows, 1.8 s: 15 pure-converter rows incl. the
one-constant law and the `src/rvt` literal scan, 7 on the written transformer through `edit_family.main` and the
`modify_family` text/JSON route: read-backs, refusals, control strings, VALID 0 errors + provenance clean after each
edit) + `tests/ci_shard.d/659-edit-lane-mass.txt` (never `tests/ci_shard.txt`). Gate counts and the whole-shard run
are in the PR body.

**/simplify** (four angles) — taken: the refusal's offer derived from `_UNIT_TOKENS` instead of hand prose (simplification
+ altitude), the one-use `_is_dimensionless` helper inlined with a comment, test rows shared between tiers (`MASS_ROWS`),
on-file rows trimmed to `lb` + `kg` (aliasing is pure-converter coverage), one inventory read per output, no second
validator run on top of the route's own family-mode gate (provenance scan kept — the route does not run one), spec ids
from `standards.SPECS` except the pinned mass id. Not taken, recorded: a lazy `KG_PER_LB` import (efficiency measured
~17 ms on non-validating paths only, flat end-to-end; #660 moves the constant to a light module), the length row's
geometry CAVEAT riding in a units table (altitude — belongs keyed on "dimension parameter"; #660's registry should not
inherit it as a spec column), a units-table-driven dimensionless predicate (would also classify `demandFactor` /
percentage specs; #660's depth, not this converter's).

**Import weight** (steer S-2026-08-09-g), this VM, best of 3: `python -X importtime -c "import
rvt.convert.modify_family"` cumulative 105 ms on `main` → 125 ms here (the top-level `rvt.famgen.factory` import:
skeleton / geometry / standards / catalog). Every product call (`modify_family(validate=True)`) already imports
`rvt.famgen.famdoc_adoc`, which imports `factory` itself, so the end-to-end edit is flat: `python -m
rvt.convert.edit_family xfmr.rfa --set "Width=600 mm"` median of 3 = 0.408 s on `main`, 0.423 s here (noise-level);
only `--inventory` (no validation) pays the ~20 ms.

## Findings / follow-ups

* **#663 (filed): the text grammar cannot set a multi-word caption.** `set Operating Weight 600 lb` →
  `cannot read a number from 'Weight 600 lb'` on `main` and here alike (`_RE_SET` takes the clause's first word as the
  caption); `set OperatingWeight 600 lb` and the structured `--set "Operating Weight=600 lb"` work. Out of this issue's
  territory (grammar, not converter); the new tests spell the text-route caption as one word and say why.
* **#660 (pre-existing): the spec registry.** Frequency (Hz = internal), wattage (W × 1/0.3048²) and the rest of
  `standards.SPECS` get conversions — or stay refused by name — from one table; this PR deliberately adds mass only.
* **Open question for the reviewer / #660:** the `rfa_modify` matrix cell text (`src/rvt/frontdoor/matrix.py:689`)
  still lists "amps as-is, volts, kVA; lengths REQUIRE an explicit unit" and does not mention mass. Left as is —
  `route.py matrix` byte-identical to `main` was this issue's DONE 4 and the router is outside the territory; a one-line
  wording refresh can ride with #660.

## BRANCH STATE

* Branch `cam/659-edit-lane-mass` from `main` (rebased onto the #661 squash before pushing). Files: `src/rvt/convert/modify_family.py`,
  `plugin/lib/src/rvt/convert/modify_family.py` (mirror via `tools/sync_plugin.py`), `tests/test_edit_family_mass_659.py`
  (new), `tests/ci_shard.d/659-edit-lane-mass.txt` (new), this fragment (new; `docs/inbox/convert-b.d/` created, index exists).
* Gates: see the PR body for the exact counts of the stream-local run before/after, the whole merged shard, `sync_plugin
  --check`, `validate_plugin.py`, `check_portable_paths.py`, `shard_list.py --print | grep -c` = 1, `route.py matrix`
  diff vs `main` = empty.
* Shipped vs staged: engine + mirror + tests ship with the merge; nothing STAGED for the viewer (no certification claim);
  no hot file touched; `TRACKER.md` / `KNOWLEDGE.md` untouched.
