# family-standards — the category → standard parameters table

Stream record. Issue #601 (owner steer, verbatim): *"we need to be working on a set of
standards. every family type has a set of parameters associated with them. you know this.
for instance if i ask for a data devices all parameters that are typically associated
within revit need to be in it, that goes for all of them. you know revit binary and the
python engine is running you should be able to create this. the end goal for us is to be
able to generate anything and everything"*.

Territory: `src/rvt/famgen/standards.py` (new), `src/rvt/famgen/factory.py` (the five
constructors' `standards` / `standard_values` arguments + the report on `FamilyProduct`),
`spec/famspec.schema.json`, `tools/make_family.py` (the `standards` verb),
`tools/sync_plugin.py` (ship `make_family.py` with the author skill),
`plugin/skills/tekton-author/SKILL.md`, `tests/test_famgen_standards.py`.

---

## What was wrong

A generated family carried whatever its constructor happened to author. A generic model —
the route that a prompt or an IFC assembly goes down, i.e. the "generate anything" route —
carried exactly three parameters: `Width`, `Depth`, `Height`, reporting its bounding box.
So "make me a data device" produced a family that was geometrically right and
professionally useless: nothing to schedule it by, nothing to tag it by, no slot for the
port count or the cable category or the mounting height an engineer needs.

## What was built

`rvt.famgen.standards` — a table from **category (or product) → the parameters a family of
that kind is expected to carry**, applied through `FamilyDoc.add_family_parameter`.

27 entries covering every category `skeleton._resolve_category` accepts: electrical
equipment (and the panelboard / switchboard / transformer product sets under it),
electrical fixtures, lighting fixtures, lighting / data / fire-alarm / communication /
security / nurse-call / telephone devices, cable-tray and conduit fittings, mechanical
equipment, plumbing fixtures, pipe and duct accessories, furniture, casework, specialty
equipment, doors, windows, structural framing and columns, and the generic-model
catch-all.

Applied by default in all five constructors (`make_generic_model`, `make_panelboard`,
`make_transformer`, `make_luminaire`, `make_device`); `standards=false` is the off switch
and the regression control. Values are filled only from `standard_values`; everything else
is authored **blank**.

## The three honesty distinctions this table is built on

Each row carries an `origin`, because "Revit has this parameter" and "content in this
category conventionally carries this parameter" are different claims:

| origin | meaning | authored? |
|---|---|---|
| `builtin` | Revit itself gives every family of the category this parameter (Doors' `Width`, a circuited device's `Panel`, the common `Manufacturer` / `Model` / `Cost` …) | **no** — listed for completeness; authoring a duplicate name would collide with Revit's own |
| `contract` | the name comes from an in-repo tagging contract (`factory.PANEL_CONTRACT_PARAMS`, the tekton-ifc shared-parameter mapping) | yes |
| `convention` | the name is the content convention for that category — **INFERRED**; no in-repo verified source says Revit spells it exactly this way | yes |

A `convention` parameter is a real, schedulable family parameter with a correct spec and
group. What is inferred is only its *spelling*, and a project expecting a different one
will not bind to it. The report and the product notes say so on every family.

**The format does not carry Revit's built-in parameter table.** The class schema defines
436 `*Param*` classes but no built-in-id → name → category mapping; that is application
knowledge, not file knowledge. So the only true built-ins bound here are the six whose ids
`skeleton` has verified (Description, Manufacturer, Model, Type Comments, URL, Cost).
Everything else is an ordinary family parameter. This is stated rather than papered over
with invented built-in ids.

## The provenance gate — the thing that keeps the table from being made up

Every **measurable** spec id in the table must be one the format itself declares. The
source is `src/rvt/famgen/assets/family_units.json` — the units table every family document
we author ships — whose `m_formatOptionsMap` enumerates **136 spec ids**. `check_specs()`
fails on any spec id outside it, and `test_famgen_standards.py` runs that gate plus an
independent restatement of it. `text` / `integer` are exempt and explicitly asserted
*absent* from that table (a string has no unit to format), so the exemption is a fact, not
a loophole.

Group ids are the published `autodesk.parameter.group:*` enum, the same constants
`genesis.residue_b` already uses.

Where a quantity has no verified spec id, the row uses `number` or `integer` and **says so
in its note** — e.g. every Yes/No-shaped parameter (`Addressable`, `GFCI Protected`,
`Accessible`) is authored as an integer 0/1 with the note "no Yes/No spec id is in our
verified set". No spec id was guessed to make a row look better.

## A bug the table shape caught

The first cut keyed everything on the OST category, which put `PanelName`, `BusRating`,
`NumberOfCircuits` and `NeutralRating` on **transformers** — they share
`OST_ElectricalEquipment` with panelboards. The shared-parameter test caught it: those
names are rows in the panelboard shared-parameter file, so a transformer came out with 11
shared GUIDs it has no business carrying.

Fixed by splitting: the *category* set (`electrical_equipment`) is what any electrical
equipment carries; `panelboard`, `switchboard` and `transformer` are product sets that
extend it. `canonical_category` prefers a product set over its category, so a constructor
that knows what it is building gets the right one and a bare OST id gets the category's
common set. `_merge` resolves the overlap, first spelling winning, and `check_specs`
fails on any duplicate that escapes it. Regression pinned in
`test_the_panel_only_parameters_are_not_on_every_electrical_equipment`.

## Evidence

| gate | result |
|---|---|
| `python -m rvt.famgen.standards --check` | 27 categories, **0 problems** |
| `tests/test_famgen_standards.py` | **64 passed** |
| `tests/test_famgen_factory.py` + skeleton + adoc + catalog + bare-family | **148 passed, 25 skipped** |
| `tests/test_ifc_family.py test_ifc_assembly.py test_famgen_loader.py test_modify_family_carrier.py` | **81 passed, 16 skipped** |
| `tests/test_router.py` | **138 passed, 8 skipped** |
| `tests/test_rfa_load.py` | **10 passed** |
| `tests/test_place_fixtures.py test_rvt_to_ifc_param_carrier.py` | **25 passed** |
| `tests/test_plugin_sync.py test_bootstrap.py test_coldstart.py test_surface_perf.py` | **47 passed** |
| `tools/sync_plugin.py --check` | in sync, deny-audit clean |
| `plugin/scripts/validate_plugin.py` | PASS, 25 assertions |
| a data-device `.rfa` on the file | 112 elements, family-mode **VALID 0 errors**, provenance ok, 13 standard parameters read back as `ParamElemFamily` at their captions |
| bare unzip + system Python, no repo on the path | `go make_family.py standards data_devices` prints the set; `go route.py run --rfa dev.famspec.json --output rfa` delivers the family with the standards block in its report |

Five pinned-count assertions elsewhere moved from magic numbers to structural ones,
because a family that carries more parameters is now the normal case:

- `test_rfa_load.py` — twins counted off the written file instead of `== 14` (a panelboard
  went 14 → 21 parameters, and the loader authored 21 twins, which is the law holding, not
  breaking).
- `test_place_fixtures.py` — `12 + one twin per parameter` instead of `== 15`.
- `test_rvt_to_ifc_param_carrier.py` — the "nothing degraded to float 0.0" check now runs
  over the parameters that carry values; a blank standard parameter **is** 0.0 on purpose.
- `test_famgen_factory.py` — the device-composition and shared-parameter tests build with
  `standards=False`, which makes them the explicit regression control for this layer, plus
  one new assertion that a transformer's standards promote to shared GUIDs correctly while
  the panel-only names stay off it.

## What is NOT claimed

- **No desktop round.** The enlarged parameter sets validate 0 errors, read back off the
  file and load-plan like any other family; nothing here says desktop Revit has opened one.
  Authoring N family parameters is the same machinery the desktop-verified panelboard (11)
  already ships, repeated — that is a reason to expect it to hold, not evidence that it
  does (hard rule 4).
- **`convention` names are inferred spellings**, per the table above. The right way to
  close that per category is a Revit-born family of that category read back and its
  parameter captions compared — a `needs-revit-desktop` follow-up, not a silent fix.
- **Values are not invented.** A standard parameter nobody supplied a value for is blank.
  The report distinguishes `filled` from the rest, and `values_not_placed` names anything
  the caller passed that matched no parameter.
- The generic-model catch-all deliberately carries only `Material` / `Finish` / `Weight`:
  Generic Models has no category-specific parameter set in Revit, and saying that is more
  useful than padding the row.

## Open questions

1. Which convention spellings does Revit actually use per category? (desktop / Revit-born
   family read-back)
2. Should the standard set be promoted to shared parameters by default, given a project
   binds schedules by GUID? Today it promotes only where the caller's shared-parameter
   file already has a row — which is the conservative, correct behaviour, but a tekton
   shared-parameter file covering the standards would make every generated family
   schedule-compatible across projects.
3. The prompt route still picks the category from the famspec the skill writes. A prompt
   → category inference ("a data outlet" → `data_devices`) would close the last manual
   step; today the skill is told to set it, and the `standards` verb prints the set.

---

## BRANCH STATE

Branch `claude/ifc-exact-box-decomposition`.

Files written:
- `src/rvt/famgen/standards.py` (new, ~700 lines: the table, the origins, `apply`,
  `describe`, `table`, `check_specs`, `units_spec_ids`, a `__main__` for `--check`)
- `src/rvt/famgen/factory.py` — `standards` / `standard_values` on all five constructors
  (default on), `_std` helper, `_standards_note`, `FamilyProduct.standards`, the report in
  `summary()`
- `spec/famspec.schema.json` — `standards` / `standard_values` in `common` and on all five
  kinds; the `category` description now says it also selects the parameter set
- `tools/make_family.py` — the `standards [category] [--json] [--check]` verb
- `tools/sync_plugin.py` — `make_family.py` ships with the author skill
- `plugin/skills/tekton-author/SKILL.md` — set the category, use `parts` for multi-solid
  objects, fill `standard_values` only with what the user said
- `tests/test_famgen_standards.py` (new, 64 tests), `tests/ci_shard.d/601-category-standards.txt`
- five pinned-count assertions relaxed to structural ones (listed above)
- this record

Gates: all green (table above). Plugin re-synced and re-zipped.

Staged vs shipped: everything here is **shipped** in the branch — nothing is staged for a
viewer batch. The desktop question (do the enlarged sets open and load, and are the
convention spellings right) is the open work, and it needs the owner's machine.
