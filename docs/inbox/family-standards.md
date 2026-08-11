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

---

# eng #624 (2026-08-11): the author skill's honesty after #583 — inferred category ids, drawn-only lying cylinders, the revolve docstring

*Written by engineer session eng #624 (issue #624). Add-only: the sections above are the
author's and untouched.* Territory: `plugin/skills/tekton-author/SKILL.md` (hot file, the
smallest diff that carries the two statements), a new
`plugin/skills/tekton-author/references/FAMSPEC-CAVEATS.md`, the module docstring of
`src/rvt/famgen/revolve.py` + its `plugin/lib` mirror, this section. No code changed.

## What was wrong, and what the code actually says today

1. **Category ids.** #583's SKILL.md hunk listed `door` and `window` among the categories to
   set. `_resolve_category` (`src/rvt/famgen/skeleton.py`) tags only five ids DESKTOP-VERIFIED
   (`furniture`, `generic_model`, `lighting_fixture`, `electrical_equipment`,
   `electrical_fixture`); every id of the wider set — doors and windows included — is
   `[INFERRED]` from Revit's published constants until a family of ours opens in that branch
   (#516). Doors/windows carry a second gap the others do not: Revit's own are wall-hosted
   families that cut an opening, ours are free-standing (`new_family_doc(host='none')`; hosted
   scaffolding is `[UNKNOWN]` and not built), and `standards door` is 6 authored parameters +
   11 "Revit provides it" built-ins that Revit provides only if it really treats the family as
   a Door. `standards.py` itself keeps real `door` / `window` tables, so the match for "what
   the code says today" is **mark, not drop**: the skill's example list no longer names them,
   and one sentence says every id beyond the verified five — `door`/`window` too, also
   unhosted — ships as "category id inferred, not desktop-verified", with the full
   verified/inferred table and the door/window note in the new reference.
2. **`cylinder_x` / `cylinder_y`.** `factory._add_part` authors the form vertical and
   `geometry.rotate_rep` rotates only the cached B-rep frame (desktop round 4, #591: Front
   elevation a clean circle). `rotate_rep`'s own docstring says the sketch is deliberately
   untouched and the form may "regenerate back to vertical on the first edit — a trade to
   measure, not to assume". The skill now says exactly that in one sentence: true lying
   cylinders AS DRAWN, over a still-vertical sketch, may stand upright on edit, never promise
   those forms stay editable; the reference carries the per-shape wording.
3. **`revolve.py` "always UNDER-fill".** Measured with the module's own `_authored_volume`
   against `_TRUE_VOLUME` (r = 1, cone h = 2, lying cylinder L = 3):

   | segments | sphere | dome | cone | lying cylinder (chord boxes) |
   |---:|---:|---:|---:|---:|
   | 4 | 1.0313 | 1.0078 | 0.9844 | 1.0375 |
   | 16 | 1.0020 | 1.0005 | 0.9990 | 1.0048 |
   | 64 | 1.0001 | 1.0000 | 0.9999 | 1.0006 |

   A mid-sampled slab is neither inscribed nor circumscribed; where the squared radius (or
   chord) is concave in z the midpoint over-estimates, so sphere/dome/lying-cylinder stacks
   OVER-fill and only the cone under-fills. Docstring reworded to say so with the 16-segment
   numbers; wording only, no code path touched; mirror re-synced byte-identical.

## Before → after wording (quoted)

- SKILL.md, parts paragraph — before: *"… size, `center` and `base_z_ft`. That is how a cable
  tray (rails + rungs), a cart (body + four wheels) or any LOD-400 assembly is expressed — one
  family, many solids, no catalog entry and no donor."* → after: *"… size, `center` and
  `base_z_ft` — a cable tray (rails + rungs), a cart (body + four wheels), any LOD-400
  assembly: one family, many solids, no catalog entry, no donor. `cylinder_x`/`_y` DRAW as
  true lying cylinders (a rotated cached B-rep) over a still-vertical sketch, so Revit may
  stand them upright on edit — never promise those forms stay editable (wording per shape and
  category: `references/FAMSPEC-CAVEATS.md`)."*
- SKILL.md, category paragraph — before: *"… `furniture`, `casework`, `door`, `window`,
  `structural_framing`, … — and not the `generic_model` default. The category picks the
  family's place in Revit's category tree AND its standard parameter set: …"* → after:
  *"… `furniture`, `casework`, `structural_framing`, … — not the `generic_model` default. Five
  ids are desktop-verified (same reference); the rest — `door`/`window` too, also unhosted —
  ship as "category id inferred, not desktop-verified". It sets the place in Revit's category
  tree AND the standard parameter set (…)"*; the rest of that paragraph (standard values
  blank unless given, `"standards": false`, `go make_family.py standards <category>`) is the
  same content re-flowed tighter to pay for the two new sentences.
- SKILL.md reference table: `references/FAMSPEC-CAVEATS.md` added to the references row.
- `revolve.py` docstring — before: *"A stack always UNDER-fills a convex body (each slab is
  sized at its mid-height), which is why the ratio is reported rather than assumed away."* →
  after: *"Each slab is sized at its mid-height, so a stack is neither inscribed nor
  circumscribed: half of every slab pokes outside the true surface and half falls inside, and
  the net volume can land on EITHER side of the true one -- mid-sampled discs slightly
  OVER-fill a sphere or dome (1.002 / 1.0005 at 16 segments) and the chord boxes over-fill a
  lying cylinder (1.005), while a cone comes out slightly under (0.999).  Which is why the
  ratio is reported rather than assumed away."*

## SKILL.md weight (S-2026-08-09-g)

| | before (`main` @ dcda26e) | after |
|---|---:|---:|
| `wc -c` bytes | 13 997 | 14 078 (+81, +0.6 %) |
| `wc -w` words | 1 953 | 1 952 |
| ≈ tokens (bytes / 4) | 3 499 | 3 519 (+20) |
| frontmatter `description` | 861 chars, no `<`/`>` | 861 chars, unchanged |

Not quite flat: the two required statements plus the pointer cost ~330 bytes; ~250 of them
were paid for by tightening #583's own paragraph (no content dropped except one redundant
`standard_values` example key and the spelled-out data-device parameter list, which the
`standards` verb prints exactly). All detail — the verified/inferred table, the door/window
hosting note, the per-shape "what to say" table with the measured ratios — lives in the new
reference (3.6 KB), which a session reads only when a famspec uses one of those categories or
shapes.

## Evidence

| gate | before | after |
|---|---|---|
| `.venv/bin/python plugin/scripts/validate_plugin.py` | PASS, 25 assertions (85 referenced paths resolve) | PASS, 25 assertions (86 referenced paths resolve — the new reference + its `lib/` pointer are checked, not skipped) |
| `.venv/bin/python tools/sync_plugin.py` then `--check` | — | synced 1 file (`plugin/lib/src/rvt/famgen/revolve.py`), deny-audit clean, identity scan == allowlist; `--check`: in sync |
| `RVT_SKIP_LARGE=1 pytest tests/test_plugin_validate.py tests/test_plugin_sync.py -q -rs` (no `tests/test_skill_*.py` exist) | 15 passed | 15 passed |
| `python3 tools/dev/check_portable_paths.py` | ok, 3012 paths | ok, 3013 paths |
| `cmp src/rvt/famgen/revolve.py plugin/lib/src/rvt/famgen/revolve.py` | — | identical; module imports, `ast.parse` clean |
| merged CI shard | not run here (docs/docstring-only diff; the tech lead's sandbox runs it) | — |

`/simplify`: a re-read only (prose + docstring). `/verify`: skipped — skill prose, a reference
file and a docstring have no runtime surface to drive; the commit carries the
`No-Verification-Needed:` trailer.

## BRANCH STATE (eng #624)

- Branch `cam/624-skill-honesty` from `main` @ dcda26e; one PR, `Closes #624`.
- Files written: `plugin/skills/tekton-author/SKILL.md` (+18/−17 inside #583's hunk + the
  references-table row), `plugin/skills/tekton-author/references/FAMSPEC-CAVEATS.md` (new),
  `src/rvt/famgen/revolve.py` (docstring only) + `plugin/lib/src/rvt/famgen/revolve.py`
  (regenerated mirror, byte-identical), this section.
- Not touched, on purpose: `standards.py` (eng #622 holds it), `factory.py` / `geometry.py` /
  `skeleton.py`, other skills' SKILL.md, `tools/`, the manifest, the matrix, the ledger.
- Staged vs shipped: everything is shipped in the branch; nothing staged for a viewer batch
  (no output bytes change). The zip is a regenerated, git-ignored artifact.
- Follow-ups: none new — the desktop questions these labels describe are already #516
  (category branches) and the "Edit anything after loading" row of `ifc-assembly-rfa.md`.

---

# eng #622 — one entry per meaning (2026-08-11)

*Section author: eng #622 (cam-karagitz's engineer session for issue #622). Everything above
this line — the #601 author's record and eng #624's section — is untouched; this section
speaks only for #622.*

Issue #622: the independent review of #601's table found quantities a Revit user would see
**twice** in one family — the constructor's filled legacy name next to the table's blank
standard spelling (`Lumens` / `Luminous Flux`, `MountingHeight` / `Mounting Height`,
`Weight` / `Operating Weight`). Steer S-2026-08-11-a wants one parameter per meaning, values
only when known; two spellings of one quantity, one always empty, is worse than either.

Territory used: `src/rvt/famgen/standards.py` (+ mirror), the `factory.py` lines that
author/fill the legacy names (luminaire, device, transformer — nothing else), `tests/test_famgen_standards.py`,
five pinned legacy-name expectations in `tests/test_famgen_factory.py` (listed below — the
unavoidable consequence of the renames), one description string in `spec/famspec.schema.json`
(the device kind's prose named `Load` / `MountingHeight`; string only), this section.

## Every pair found (grep of the table + the five constructors, then a build of one family per category)

Built one family per affected category on `main` and read the `ParamElemFamily` captions back
off the written `.rfa` with `rvt.families.FamilyIndex` (the reader `test_famgen_standards.py`
already uses). Six pairs, all constructor-vs-table; the table itself had **no** internal pair
(`--check` with the new rule: 0 problems before any row changed). Panelboard and the
mechanical-equipment generic route were already clean.

| category / constructor | legacy (filled) | table spelling (blank twin) | decision | why |
|---|---|---|---|---|
| lighting_fixture / `make_luminaire` | `Lumens` | `Luminous Flux` | **constructor renamed** → fills `Luminous Flux` | same spec (`luminous_flux`) and group; a caption rename is structurally inert (same class, deterministic local GUID re-derives from the caption) |
| lighting_fixture / `make_luminaire` | `Color Temperature` | `Initial Color Temperature` | **constructor renamed** | same spec (`cct`); found by the grep, not named in the issue |
| electrical_fixture / `make_device` | `MountingHeight` | `Mounting Height` | **constructor renamed** (type parameter, value 18/44/48 in lands as before) | same spec (`length`, constraints). Counter-consideration recorded: `MountingHeight` is also the IFC-side `DeviceSchedule` pset key (`rvt.ifc.intent.DEVICE_PSET`, prompt_intent / ifc_out / manifest); nothing joins the family caption to that key (grep: no reader of the family's `MountingHeight` outside factory + its tests), so the pset keeps its CamelCase key and the family takes the table's spelling like every other device category |
| electrical_fixture / `make_device` | `Load` | `Apparent Load` | **constructor renamed**; the connector's `bind_load_param` follows (`m_dApparentLoadPhase1` still 180 VA) | same spec (`apparent_power`, electrical_loads); found by the grep. The docstring called `Load` "the receptacle specimen's own binding" — the binding (connector load ↔ a family parameter) is kept, only our caption changes; `Apparent Load` is the connector field's own name and the spelling 12 table categories share |
| transformer / `make_transformer` | `Enclosure` (= "NEMA 2 (indoor)") | `Enclosure Rating` (note: NEMA / IP class) | **constructor renamed** → fills `Enclosure Rating` | same storage (text, identity); the value *is* the NEMA class; found by the grep |
| transformer / `make_transformer` | `Weight` (number, lb) | `Operating Weight` (mass) | **legacy KEPT as the transformer set's single entry, reason in the row's note**; `_EE_COMMON`'s `Operating Weight` dropped for this product only via the greppable `_without(...)` | the specs differ: filling `Operating Weight` means a lb → internal-mass conversion + a mass type-catalog column the factory does not have (`SPEC`, `_TO_INTERNAL`, `TYPE_CATALOG_COLUMNS`; the catalog test pins `Weight##OTHER##`) — a unit change DONE 4 fences off. A vendor with no catalog weight (HPS) now gets ONE blank `Weight` instead of a blank `Operating Weight`, so every transformer names its weight the same way. Follow-up **#630** retires the exception properly |

Observed and deliberately **not** changed (DONE 4 — other table content): a transformer still
lists the common `Voltage` (blank) beside `Primary Voltage` / `Secondary Voltage`, and a
receptacle lists `Wattage` (blank) beside `Apparent Load`. Those are related but distinct
quantities (system voltage vs winding voltages; W vs VA), not two spellings of one, so the
synonym list keeps them apart on purpose and a test pins that it does.

## What was built

- `standards.SYNONYM_GROUPS` — 34 hand-authored groups of trade spellings (rule 3: generic
  industry terms and abbreviations only, no vendor or Autodesk-authored list), first spelling =
  the table's; `standards.meaning_key(name)` folds case / spaces / underscores / hyphens /
  punctuation and maps through the groups (`MountingHeight` == `Mounting Height` needs no row).
- `check_specs()` rule 5: a category listing two spellings of one meaning key is a problem line
  naming both; a spelling claimed by two groups is one too. `python -m rvt.famgen.standards --check`
  → `27 categories, 34 synonym groups, 0 problems`.
- `apply()` guard: a standard parameter whose *meaning* is already on the document (a
  constructor's, or a caller's `text_params` — e.g. an IFC's `CCT`) is skipped with
  `already authored by the constructor as 'CCT' (the same quantity)` — one lookup serves the
  exact-name and the synonym case — and a value offered for a quantity the constructor already
  carries surfaces in `values_not_placed` instead of vanishing. The same key works on the way
  in: `standard_values={"Lumens": 3200}` (a famspec written before the rename) fills
  `Luminous Flux`. This is the belt to the renames' braces: a future constructor or an IFC pset
  cannot reintroduce a blank twin.
- `/simplify` pass (4 review agents): applied — the import-time loop became `_build_synonym_key()`
  (no leaked module names), `apply()`'s exact-name branch folded into the meaning lookup (key
  computed once), `check_specs()` rules 3 and 5 share one bucket dict, messages shortened, the
  transformer rationale stated once in the row note. Declined, with reasons: making `_merge`
  meaning-aware (reuse agent) — it would hide exactly the synonyms the check exists to surface;
  dropping the transformer row in favour of the `apply()` guard alone (altitude agent) — that
  names the weight `Weight` on an Eaton transformer and `Operating Weight` on an HPS one, and
  DONE 1 asks for the kept legacy name to carry its reason *in the table*; #630 removes the row
  either way.
- `_merge` left exact-name on purpose: a meaning-aware merge would *hide* a synonym between a
  product row and a block row instead of letting the check surface it.

## Evidence

| gate | before (main dcda26e) | after |
|---|---|---|
| `python -m rvt.famgen.standards --check` | `27 categories, 0 problems` | `27 categories, 34 synonym groups, 0 problems` |
| planted duplicate (`Lumens`+`Luminous Flux`, `MountingHeight`+`Mounting Height`, `Weight`+`Operating Weight` in a probe category) | — | check reports exactly 1 problem each (`test_a_planted_duplicate_meaning_fails_the_table_check`, 3 cases) |
| `RVT_SKIP_LARGE=1 pytest tests/test_famgen_standards.py tests/test_famgen_factory.py tests/test_rfa_load.py tests/test_place_fixtures.py tests/test_rvt_to_ifc_param_carrier.py -q -rs` | 156 passed, 5 skipped (rme/rst samples absent) | **171 passed, 5 skipped** (+15 new in `test_famgen_standards.py`, one of them from the `/simplify` pass: values fill by meaning) |
| whole merged CI shard (`shard_list.py --print`) | — | see BRANCH STATE |
| every produced `.rfa` (troffer, receptacle, transformer, panelboard, RTU generic) `tools/rvt_validate.py --family` | VALID 0 errors | **VALID 0 errors**, warnings 0 |
| `tools/make_family.py provenance` on the same five | ok / clean | **ok / clean** |
| `tools/route.py matrix` | 3181 bytes | **byte-identical** to a fresh `origin/main` worktree (sha256 prefix `7dae5d40eb461e9a`; nothing in famgen/standards is read by the matrix) |
| `tools/sync_plugin.py` then `--check` | — | 3 files synced (the two mirrors + the famspec example); in sync, deny-audit clean, identity scan == allowlist |
| `plugin/scripts/validate_plugin.py` | — | PASS, 25 assertions |
| `tools/dev/check_portable_paths.py` | — | ok, 3012 paths |
| `/verify` (this repo's build-and-drive recipe): `tools/make_family.py luminaire` / `device --height 18` / `transformer --kva 75` `--json` | — | exit 0 each; family-mode **VALID 0 errors**; provenance ok; `type_facts` carry `Luminous Flux` 4600 / `Initial Color Temperature` 4000, `Apparent Load` 180 / `Mounting Height` 18, `Weight` 570 / `Enclosure Rating` "NEMA 2 (indoor)"; captions read back off each `.rfa`: 23 / 13 / 24, zero meaning twins, zero legacy names |
| bare unzip of the rebuilt `tekton-plugin.zip`, **system** `python3`, no repo on the path: `skills/tekton-author/scripts/_bootstrap.py go route.py run --rfa lum.famspec.json --output rfa` | — | preflight `tekton: READY … 0.067s`, job 1.36 s, exit 0, result `OK (… validator family-mode VALID 0 errors; provenance ok=True)`; the delivered `troffer_2x4_recessed.rfa` reads back 23 captions, zero twins, `Luminous Flux` + `Initial Color Temperature` present |

**Parameter captions read back off the written `.rfa`** (sorted; `FamilyIndex`, `ParamElemFamily`):

- lighting_fixture (`make_luminaire` 2x4 troffer) 25 → 23: gone `Lumens`, `Color Temperature`; the type row now carries `Luminous Flux` = 4600 lm, `Initial Color Temperature` = 4000 K, `Wattage` unchanged.
  after: Apparent Load, Color Rendering Index, Dimming Protocol, Driver Type, Efficacy, Emergency, Height, IES File (URL reference), IP Rating, Initial Color Temperature, Lamp, Length, Light Loss Factor, Load Classification, Luminous Flux, Mounting, Number of Lamps, Operating Weight, Switch ID, Voltage, Warranty Duration, Wattage, Width
- electrical_fixture (`make_device` duplex receptacle) 15 → 13: gone `Load`, `MountingHeight`; `Apparent Load` = 180 VA (connector-bound), `Mounting Height` = 1.5 ft.
  after: Apparent Load, Backbox Size, Device Type, Faceplate Color, GFCI Protected, Load Classification, Mounting, Mounting Height, NEMA Configuration, Number of Gangs, Number of Poles, Voltage, Wattage
- transformer (`make_transformer` 75 kVA Eaton) 26 → 24: gone `Enclosure`, `Operating Weight`; `Enclosure Rating` = "NEMA 2 (indoor)", `Weight` = 570 (lb, number — the kept exception).
  after: Apparent Load, Depth, Enclosure Rating, Frame, Frequency, Height, Impedance, Insulation Class, K-Factor, Load Classification, Mounting, Phases, Primary Voltage, Secondary Voltage, Service Clearance, Sound Level, Taps, Temperature Rise, Voltage, Warranty Duration, Weight, Width, Wires, kVA Rating
- panelboard 21 → 21 and mechanical_equipment (generic RTU box) 21 → 21: unchanged, no pair before or after.

Every family: meaning keys of its captions pairwise distinct (pinned by
`test_every_generated_family_lists_each_quantity_once_and_the_values_still_land`, 5 cases).

**Expectations that flipped, and why** — all five are lines that pinned a legacy *caption*,
nothing structural: `tests/test_famgen_factory.py` L339 (`Lumens`, `Color Temperature` →
the table's two spellings), L383/L392 (device docstring + `sorted(doc.params) ==
["Apparent Load", "Mounting Height", "Voltage"]`), L409 and L778 (`MountingHeight` →
`Mounting Height` as the type-row / `type_facts` key). In `test_famgen_standards.py` the
`common <= xfmr` law became a meaning-key subset plus an explicit
`common - xfmr == {"Operating Weight"} and "Weight" in xfmr`, because the transformer now
carries that one common quantity under its kept legacy name.

## What is NOT claimed

- No desktop round and no viewer batch: caption renames and one dropped row are structurally
  inert (same classes, same specs, VALID 0 errors, provenance clean) — that is a reason to
  expect the verified lineage to hold, not evidence that Revit opened these files (rule 4).
- The synonym list is a hand list; a spelling it does not know is compared by folding only.
  The check is a floor, not an oracle — a new pair it misses is one row away from being caught.

## Follow-ups filed

- **#630** — transformer weight as `Operating Weight` (mass) with a verified lb → mass path; retires the kept exception.
- **#631** — the IFC luminaire route (`famfrom_ifc`, outside this territory) still authors `Lumens` / `Color Temperature` and applies no standards; plus the author-skill reference `CATALOG-FACTS.md` L66 still cites the device's `Load` / `MountingHeight` (prose; SKILL.md untouched, eng #624's area).

## BRANCH STATE

Branch `cam/622-standards-dedup` from `main` @ dcda26e.

Files written: `src/rvt/famgen/standards.py` (synonym vocabulary, `meaning_key`, `_without`,
transformer row, `apply` guard, `check_specs` rule 5, `--check` line, docstring),
`src/rvt/famgen/factory.py` (luminaire `Lumens`/`Color Temperature`, device `Load`/`MountingHeight`
+ its connector binding / docstring / note / one comment, transformer `Enclosure` — the
legacy-name lines only), `tests/test_famgen_standards.py` (+15 tests, one law restated over
meaning keys), `tests/test_famgen_factory.py` (5 caption expectations), `spec/famspec.schema.json`
(one description string), mirrors via `tools/sync_plugin.py` (`plugin/lib/src/rvt/famgen/{standards,factory}.py`,
`plugin/skills/tekton-native/examples/famspec.schema.json`), this section.

Gates: table above; whole merged shard result in the PR body. Staged vs shipped: everything
**shipped** on the branch; nothing staged for a viewer batch (no writer path or base touched).
