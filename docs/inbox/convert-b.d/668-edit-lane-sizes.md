# 668-edit-lane-sizes -- the family edit lane treats Revit's SIZE specs as the lengths they are: `Tray Width=4 in` → 0.3333 ft, `=100 mm` → 0.32808 ft, a bare `=4` refused like any length, `=4 kg` refused by name (convert-B stream, eng #668)

**Issue:** #668 (Refs #659 #665 #601 #660; follow-up filed here: #678 — the inch/foot MARK tokens are unreachable, pre-existing).
**Date:** 2026-08-11. **Session:** eng #668 (cloud, `cse_01D6Z8VcgQBYxyM2VCi7VyBJ`), started by the tech-lead session.
**Base:** `main` @ 345493c (#669). Index: `docs/inbox/convert-b.md` (left untouched, as #659 did). Written in this
engineer's voice; no other record edited. The collaborator's session was live on #591 in `src/rvt/famgen/**` +
`src/rvt/frontdoor/**` throughout — both read-only here; nothing under them was edited.

## Why

Since #601 the category tables author size parameters under Revit's discipline SIZE specs, not `aec:length`:
`Tray Width` / `Tray Height` (`electrical:cableTraySize`), `Nominal Diameter` (`electrical:conduitSize`, `piping:pipeSize`),
`Duct Width` / `Duct Height` (`hvac:ductSize`), connection sizes (`piping:pipeSize`), wire diameters
(`electrical:wireDiameter`). Revit stores every one of them in **feet** — they are lengths with a discipline-specific
display — but `_convert_value`'s table branch matched only the `:length` marker, so after #665 a size fell into the
generic refusal (*no conversion for unit 'in' on spec …cableTraySize…*) even with `=4 in`, while a bare `=4` was stored
as 4 **ft** silently: the exact opposite of the length policy ("units are never guessed", S-2026-08-11-a).

## What landed

`src/rvt/convert/modify_family.py` — the converter only; `_UNIT_TOKENS`, `_SPEC_UNITS`, `_converted_units()` and every
message string are untouched.

1. **The spec family is derived from the units table, not listed twice (DONE 1).** The law encoded is Revit's own: *a
   spec DISPLAYED in a plain length unit is a length by dimension, and the internal unit of the length dimension is the
   foot, whatever the discipline calls the spec.* `_feet_specs()` (lazy, `lru_cache`d, ~0.4 ms once per process) reads
   the format's own units table — `famgen/assets/family_units.json`'s `m_formatOptionsMap` (spec id → display unit id),
   the same table `standards.check_specs` verifies every authored spec id against, opened through the one named path
   constant `standards._UNITS_ASSET` (a `tests/test_transformer_mass_630.py` precedent; a third `os.path.join` copy of
   the path was the alternative) — and keeps every spec whose display unit is one of `_LENGTH_DISPLAY_UNITS =
   ("feet", "feetFractionalInches", "inches", "fractionalInches", "meters", "millimeters")`. That short marker list is of
   **display units** (a closed, release-stable vocabulary: the four imperial names are every plain-length unit our table
   uses, the two metric ones the ids the repo already sources verbatim), not of spec ids (an open list that grows with
   every discipline); compound units that merely mention feet/inches (`feetPerMinute`, `squareInches`, `inchesOfWater…`)
   are other dimensions and deliberately absent. Today the derived set has **23** members: `aec:length`, the five the
   issue names (`cableTraySize`, `conduitSize`, `wireDiameter`, `ductSize`, `pipeSize`) and 17 more that are all
   genuinely feet-stored (`hvac:ductInsulationThickness` / `ductLiningThickness` / `roughness`, `piping:pipeDimension` /
   `pipeInsulationThickness` / `roughness`, `structural:barDiameter` / `crackWidth` / `displacement` /
   `reinforcementCover|Length|Spacing` / `sectionDimension` / `sectionProperty`, `infrastructure:stationingInterval`,
   `aec:sheetLength` / `decimalSheetLength`). A `Size`/`Diameter` name-suffix heuristic was rejected (misses
   `roughness` / `displacement` / insulation thicknesses; would catch a non-length "size" if one appears); five literal
   markers (the issue's own suggestion) would re-break on the next discipline spec.
2. **One line in `_convert_value`.** Before the existing `_SPEC_UNITS` loop: `key = ":length" if _unversioned(spec) in
   _feet_specs() else spec` and the loop matches markers against `key` — a spec stored in feet is matched AS `:length`,
   so it gets the length row verbatim: `in / ft / mm / m` (and `inch(es)` / `feet` / `foot`) × the existing factors, the
   note `"<cap>: 4 in -> 0.333333 ft (CAVEAT: type-table value only; …)"` (the geometry caveat is apt: these are
   fitting dimensions), a bare number → `"<cap> is a LENGTH: give an explicit unit (in / ft / mm / m) -- units are never
   guessed"` (the issue's DONE 1 wording, = #659's pinned length wording), a unit of another kind → `"<cap> is a length;
   got unit 'kg'"`. `_unversioned` strips the `-1.0.0` suffix on both sides so a version bump cannot split the match.
3. **The generic refusal's offer stays truthful and byte-identical (DONE 3).** `_converted_units()` lists *units*, and a
   size accepts exactly the length units already listed; #665's pinned offer string is unchanged (its module is green
   beside the new one, and the new module re-asserts the length / mass / Hz / lm / K rows and the efficacy refusal via
   #659's own constants — imported, not copied).
4. **/simplify** (four angles, subagents) — taken: the `_spec_units_row` helper + `Optional[tuple]` return I first wrote
   was folded into the one `key = …` line above (zero new names in the dispatch); `_feet_specs`' docstring cut to two
   lines and the `_SPEC_UNITS` cross-reference comment dropped (the size list had crept into four paragraphs of prose);
   the test's verbatim re-implementation of the JSON comprehension dropped (membership asserts carry the law); the two
   metric display-unit names added (altitude: a metric units table would otherwise silently degrade to pre-#668
   refusal — safe, but avoidable at zero cost). Not taken, recorded: deriving *mass* the same way (`poundsMass` maps to
   exactly the one spec already on its literal row — no behavioural gain; the shape belongs to #660); replacing every
   row's substring marker with a display-unit → kind lookup (the general form — #660's registry, see follow-ups).
   Reuse angle: nothing duplicated (no version-strip helper, no parsed spec→unit view, no "stored in feet" predicate
   exists anywhere in `src/`; `rvt_to_ifc._param_value` has the same `aec:length`-only blind spot but offers nothing to
   call). Efficiency angle: clean — the JSON read is off the import path and once per process; import weight flat
   (below).

## Evidence

**Read-backs, one cable-tray fitting** — `make_generic_model(parts=[12x12x4 in box], name="Tray Elbow 12x4",
category="cable_tray_fitting", standard_values={"Tray Width": 1.0, "Tray Height": 4/12})` written the product's way
(`standalone_family_write`: family-mode VALID 0 errors, provenance ok; `Tray Width` reads back spec
`autodesk.spec.aec.electrical:cableTraySize-1.0.0`, carrier `m_value`, 1.0 ft), edited with
`python -m rvt.convert.edit_family tray.rfa -o <dir> --set …`, value read back with
`inventory_family(out).param_by_caption("Tray Width")["current"]`:

| `--set` | `main` @ 345493c | this branch |
|---|---|---|
| `Tray Width=4 in` | **refused**: `ERROR: Tray Width: no conversion for unit 'in' on spec autodesk.spec.aec.electrical:cableTraySize-1.0.0 (this lane converts: current a / amp / amps; potential v / volt / volts; length ft / feet / foot / ' / in / inch / inches / " / mm / m; …; mass kg / lb / lbs / lbm) -- give a supported unit, or a bare number ONLY if …`, exit 2 | **0.3333333333333333 ft**, note `Tray Width: 4 in -> 0.333333 ft (CAVEAT: type-table value only; the authored solid is not re-derived -- regenerate from the facts sidecar for geometry-true resizing)`, exit 0, VALID (no errors) warnings=0, provenance `"ok": true`; output md5 `38b91d1e29c3` == **byte-identical** to `main`'s bare `--set "Tray Width=0.3333333333333333"` output (main stores a bare size as feet) — the conversion adds nothing but the arithmetic |
| `Tray Width=100 mm` | refused (same message, `'mm'`), exit 2 | **0.32808398950131235 ft** (= 0.1 / 0.3048), note `Tray Width: 100 mm -> 0.328084 ft (CAVEAT: …)`, exit 0, VALID warnings=0, provenance ok, md5 `cd5ef1f097d6` |
| `Tray Width=4` (bare) | **stored 4.0 (= 4 ft) silently**, no note, exit 0 | **refused before anything is written**: `ERROR: Tray Width is a LENGTH: give an explicit unit (in / ft / mm / m) -- units are never guessed`, exit 2, out dir empty (no manifest, no `.rfa`) |
| `Tray Width=4 kg` | refused by the generic message (`no conversion for unit 'kg' on spec …cableTraySize…`), exit 2 | refused **by kind**: `ERROR: Tray Width is a length; got unit 'kg'`, exit 2, nothing written |
| `Tray Width=12 in` / `=300 mm` (the issue's DONE 2 rows) | refused | 1.0 ft / 0.984251968503937 ft (tests) |

**One conduit fitting** (`category="conduit_fitting"`, `Nominal Diameter` = `electrical:conduitSize`, 1/12 ft): `=27 mm` →
0.08858267716535433 ft, `=1.25 in` → 0.10416666666666666 ft (both exit 0, VALID (no errors) warnings=0, provenance ok);
bare `=1.25` → `ERROR: Nominal Diameter is a LENGTH: give an explicit unit (in / ft / mm / m) -- units are never guessed`,
exit 2. Controls on the same fitting: `Bend Radius=6 in` (`aec:length`) → 0.5 ft with `main`'s note text; `Width=600 mm`
→ 1.968503937007874 ft + #659's pinned `LENGTH_NOTE_600MM`; `Width=600` refused as on `main`.

Every successful edit above: `tools/rvt_validate.py --family` → `verdict: VALID (no errors); warnings=0`,
`tools/make_family.py provenance` → `"ok": true`; the route's own gates in each manifest: family-mode VALID 0 errors,
release preserved, re-read ok, structural_ok. Validator-green is a fact about the file, not evidence Revit opens it
(rule 4); no certification claimed, ledger untouched.

**Tests** — new module `tests/test_edit_family_size_668.py` (29 rows, ~2 s): 18 pure-converter rows (the derivation law:
the five size specs + `aec:length` ∈ `_feet_specs()`, mass / mass-per-length / number / W / lm/W / hvac velocity
(`feetPerMinute`) / area / volume / angle ∉; every length token → feet with the note; a bare number refused on each of the
five size specs with the exact wording; kg / lb / V / Hz / W refused by kind; `4 cm` refused as on a plain length; the
#665 rows + offer re-asserted through #659's constants) + 11 on the written tray and conduit fittings through
`edit_family.main` and the `modify_family` text / JSON routes (read-backs, the current-defaults mirror + the one type row
both carry the value, neighbours untouched, refusals exit 2 with nothing written, VALID 0 errors + provenance clean after
each edit) + `tests/ci_shard.d/668-edit-lane-sizes.txt` (never `tests/ci_shard.txt`). `tests/test_edit_family_mass_659.py`
untouched and green (helpers `_cli_edit` / `_currents` / `_assert_valid_and_ours` and its pinned strings are imported from
it, as the charter allowed). Gate counts and the whole-shard run are in the PR body.

**Import weight** (S-2026-08-09-g), this VM, best of 5, `python -X importtime -c "import rvt.convert.modify_family"`
cumulative: `main` 101.1 ms → branch 97.6 ms (noise; `famgen.standards` was already imported via `factory`, the JSON read
is deferred to the first converted double: 0.40 ms once, ~2 KB frozenset pinned).

## Findings / follow-ups

* **#678 (filed): the inch / foot MARK tokens are unreachable.** `_UNIT_TOKENS` has `"` → in and `'` → ft, but
  `_convert_value` strips trailing quotes off the value first, so `Width=4"` is refused as unitless on `main` and here
  alike while the generic refusal *offers* both marks. Pre-existing; a `4"` size row had to be dropped from the new tests.
* **For #660 (commented there): the general form of this fix.** `standards` should expose
  `spec_dimension(spec_id) -> (kind, internal unit, display unit)` derived from `family_units.json` with the display-unit →
  dimension table owned once (imperial + metric names); `_SPEC_UNITS` rows keyed by kind; then `_feet_specs`,
  `_LENGTH_DISPLAY_UNITS` and the `standards._UNITS_ASSET` reach-in leave the convert package. Not doable here without
  editing famgen (another session's live territory).
* **`rfa_modify` matrix cell wording** (`src/rvt/frontdoor/matrix.py:689`, "amps as-is, volts, kVA; lengths REQUIRE an
  explicit unit, never guessed") still does not name mass / Hz / lm / K / W (#665) or say that sizes are lengths (#668).
  `route.py matrix` is byte-identical to `main` (this issue's DONE 3) and `frontdoor/**` was the collaborator's live
  territory this session — the one-line wording refresh is noted on #660 to ride with the registry (as #659 already
  parked it), not filed a third time.
* `rvt_to_ifc._param_value` keys its length export on `aec:length` only (reuse review) — sizes exported to IFC psets are
  presumably written as raw feet; not verified here, worth one look by whoever next touches convert-a's rvt→ifc lane.

## BRANCH STATE

* Branch `cam/668-edit-lane-sizes` from `origin/main` @ 345493c. Files: `src/rvt/convert/modify_family.py`,
  `plugin/lib/src/rvt/convert/modify_family.py` (mirror via `tools/sync_plugin.py`), `tests/test_edit_family_size_668.py`
  (new), `tests/ci_shard.d/668-edit-lane-sizes.txt` (new), this fragment (new).
* Gates: stream-local suite (`test_edit_family_size_668 + _mass_659 + modify_family_carrier + convert + convert_combo +
  records_layout`, `RVT_SKIP_LARGE=1`) `main` 49 passed / 17 skipped → branch 78 passed / 17 skipped (the 17 skips are
  the pre-existing acceptance-fixture / large-file skips in `test_convert*`); whole merged shard: see PR body;
  `sync_plugin.py` run + `--check` clean; `validate_plugin.py` PASS (25 assertions); `check_portable_paths.py` ok (3051
  paths); `shard_list.py --print | grep -c test_edit_family_size_668` = 1; `route.py matrix` md5 `e9e2cc8d7f15` on both
  sides (byte-identical, 3181 bytes).
* Shipped vs staged: engine + mirror + tests ship with the merge; nothing STAGED for the viewer (no certification claim);
  no hot file touched; `TRACKER.md` / `KNOWLEDGE.md` / `matrix.py` / famgen untouched.
