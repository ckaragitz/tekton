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
| `RVT_SKIP_LARGE=1 pytest tests/test_famgen_standards.py tests/test_famgen_factory.py tests/test_rfa_load.py tests/test_place_fixtures.py tests/test_rvt_to_ifc_param_carrier.py -q -rs` | 156 passed, 5 skipped (rme/rst samples absent) | **172 passed, 5 skipped** (+16 new in `test_famgen_standards.py`: 14 with the change, one from the `/simplify` pass — values fill by meaning — and one from the review round — two spellings in `values` fill once, loser reported) |
| whole merged CI shard (`shard_list.py --print`, 104 files) | — | **2182 passed, 134 skipped, 3 xfailed, 0 failed** in 602 s on `e34b517` (the reviewed head); the review-round delta (`apply()` wording + the `values` collision report, record) re-ran the five gate files: 172 passed / 5 skipped |
| every produced `.rfa` (troffer, receptacle, transformer, panelboard, RTU generic) `tools/rvt_validate.py --family` | VALID 0 errors | **VALID 0 errors**, warnings 0 |
| `tools/make_family.py provenance` on the same five | ok / clean | **ok / clean** |
| `tools/route.py matrix` | 3181 bytes | **byte-identical** to a fresh `origin/main` worktree (sha256 prefix `7dae5d40eb461e9a`; nothing in famgen/standards is read by the matrix) |
| `tools/sync_plugin.py` then `--check` | — | 3 files synced (the two mirrors + the famspec example); in sync, deny-audit clean, identity scan == allowlist |
| `plugin/scripts/validate_plugin.py` | — | PASS, 25 assertions |
| `tools/dev/check_portable_paths.py` | — | ok, 3013 paths (after the rebase onto `main` @ ca74895, which added eng #624's `FAMSPEC-CAVEATS.md`; 3012 before it) |
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

## Review round (tech-lead verdict on e34b517: 🟡 nits, all four judgment calls accepted)

- Applied: (2) two spellings of one quantity in `standard_values` (`{"Lumens": …, "Luminous Flux": …}`) no longer collapse last-wins silently — the table's own spelling wins, else the first given, and the loser is named in `values_not_placed` (pinned by `test_two_spellings_of_one_quantity_in_values_fill_it_once_and_report_the_loser`); (3) the by-meaning skip now reads `already on the document as '<name>' (the same quantity)` because the carrier may be a caller's text parameter, not the constructor's — the by-name skip keeps `already authored by the constructor`.
- Kept as is, noted: (4) the `ShortCircuitRatingkA` synonym row lists `AIC Rating` beside `SCCR`. Strictly, AIC is a protective device's interrupting capacity and SCCR the assembly's withstand rating; on a panelboard/switchboard *family* they are quoted as the one kA figure a user schedules, so the row treats them as one slot rather than authoring both — a category that genuinely needs the two apart drops `AIC Rating` from the row and the check stays green.
- Mechanical: rebased onto `main` @ ca74895; the record conflict with eng #624's section resolved by keeping both (theirs as landed, then this one); the doubled `---` before this section is gone.

## Follow-ups filed

- **#630** — transformer weight as `Operating Weight` (mass) with a verified lb → mass path; retires the kept exception.
- **#631** — the IFC luminaire route (`famfrom_ifc`, outside this territory) still authors `Lumens` / `Color Temperature` and applies no standards; plus the author-skill reference `CATALOG-FACTS.md` L66 still cites the device's `Load` / `MountingHeight` (prose; SKILL.md untouched, eng #624's area).

## BRANCH STATE

Branch `cam/622-standards-dedup`, cut from `main` @ dcda26e, rebased onto `main` @ ca74895 for the review round
(the only conflict was this file: eng #624's section had landed at the same EOF — kept as landed, this section after it).

Files written: `src/rvt/famgen/standards.py` (synonym vocabulary, `meaning_key`, `_without`,
transformer row, `apply` guard, `check_specs` rule 5, `--check` line, docstring),
`src/rvt/famgen/factory.py` (luminaire `Lumens`/`Color Temperature`, device `Load`/`MountingHeight`
+ its connector binding / docstring / note / one comment, transformer `Enclosure` — the
legacy-name lines only), `tests/test_famgen_standards.py` (+16 tests, one law restated over
meaning keys), `tests/test_famgen_factory.py` (5 caption expectations), `spec/famspec.schema.json`
(one description string), mirrors via `tools/sync_plugin.py` (`plugin/lib/src/rvt/famgen/{standards,factory}.py`,
`plugin/skills/tekton-native/examples/famspec.schema.json`), this section.

Gates: table above; whole merged shard result in the PR body. Staged vs shipped: everything
**shipped** on the branch; nothing staged for a viewer batch (no writer path or base touched).

---

# eng #631 — the IFC luminaire route carries the table too (2026-08-11)

*Section author: eng #631 (cam-karagitz's engineer session for issue #631, filed by eng #622).
Everything above this line is untouched; this section speaks only for #631.*

Issue #631 (Refs #622 #601 #498): after #622/#633 the factory's `make_luminaire` fills the
Lighting Fixtures table's spelling (`Luminous Flux` / `Initial Color Temperature`), but the
IFC → family route `rvt.ifc.famfrom_ifc.make_downlight` still authored its own `Lumens` /
`Color Temperature` **and applied no category standards at all** — so the same luminaire,
born from an IFC instead of a prompt, named the photometric pair differently and carried none
of the 19 authored Lighting Fixtures standard parameters. The author-skill reference
`CATALOG-FACTS.md` L66 also still described the device family with the retired `Load` /
`MountingHeight`.

Territory used: `src/rvt/ifc/famfrom_ifc.py` (+ its `plugin/lib` mirror), `tests/test_ifc_family.py`
(the pinned captions/counts), NEW `tests/test_famfrom_ifc_standards.py` + `tests/ci_shard.d/631-famfrom-ifc-standards.txt`,
`plugin/skills/tekton-author/references/CATALOG-FACTS.md` (that one sentence), this section.
**One line outside the listed territory, flagged for the reviewer:** `spec/famspec.schema.json`
— the `downlight` kind gains the two `$ref`s to `common.standards` / `common.standard_values`
every catalog kind already lists (string-only schema; without them the famspec surface would
refuse `{"kind":"downlight","standards":false}` as INVALID-FAMSPEC although the constructor now
accepts it, breaking the schema's own promise that fields mirror the constructor's kwargs);
its `plugin/skills/tekton-native/examples/` copy follows via `sync_plugin`. Not touched:
`standards.py`, `factory.py`, `router.py`, `src/rvt/ifc/*` other than `famfrom_ifc.py`,
any `SKILL.md`, the tracked `tekton-eval-kit/` snapshot (it carries an older copy of
`CATALOG-FACTS.md`; a frozen kit, not the plugin source).

## What was built

- `make_downlight(..., standards=True, standard_values=None)` — the same two switches every
  factory constructor takes. The constructor **no longer authors the photometric pair itself**:
  it hands the `lumens` / `cct` job values it actually has (None = not sourced = not offered)
  to the factory's own standards step, `factory._std(doc, "lighting_fixture", standards, values)`
  → `rvt.famgen.standards.apply` — the exact call `make_luminaire` makes, hard-rule-1 guard
  included (a standards fault becomes a note, never a failed delivery) — keyed by the table's spelling
  (`PHOTOMETRIC_JOB_VALUES = (("lumens_lm", "Luminous Flux"), ("cct_k", "Initial Color Temperature"))`).
  The table owns the parameter (spelling, spec `luminousFlux` / `colorTemperature`, group
  `lightPhotometrics` — identical to what the constructor used to author), so there is one code
  path deciding how a standard parameter is spelled, and `apply`'s meaning guard (#622) makes a
  second name for the same quantity impossible: a caller's `standard_values={"CCT": 2700}` or
  `{"Lamp Lumens": 650}` (IFC-pset habits) fills the table's entry instead of growing a twin.
  `standard_values` fills any other entry the caller knows; everything else is an honest blank.
- The four parameters the constructor still authors itself because it binds or fills them
  (`Wattage`, `Voltage` — the connector's bindings; `Lamp`, `Mounting` — CCEA pset strings) are
  exactly the four `apply` reports skipped `already authored by the constructor`; the other 15
  authored rows are added → the standard downlight carries **33** parameters (18 own + 15), was 20.
- `DownlightProduct.standards` carries the `apply` report and `summary()["standards"]` exposes
  it, the same shape `factory.FamilyProduct` has — so the route manifest says which standard
  parameters an IFC-born family got, which were filled, which are blanks.
- `standards=False` = the IFC contract + connector parameters only (18; no photometric pair —
  they are standard parameters of the category and arrive with the table; a `lumens=` / `cct=`
  the caller gave is then named in a `doc.notes` line, never silently dropped). Nobody calls it;
  it is the regression control, as in the factory.
- Docstrings (module, `make_downlight`) say all of the above; `CATALOG-FACTS.md` L66 now reads
  "bound to `Voltage` / `Apparent Load`), `Mounting Height` from the facts".

## Evidence

Instrument for the caption lists: build the family, write it with
`rvt.frontdoor.standalone.standalone_family_write` (bundled genesis base — the donor-free
product path; `DownlightProduct.write_rfa`'s default container is the git-ignored vendor
archetype, absent here, which is issue #94's territory, not this one), then read every
`ParamElemFamily` caption back off the `.rfa` with `rvt.families.FamilyIndex` — the
`test_famgen_standards.py` method. Fresh cloud clone, no `samples/` / `vendor/`, steplite reader.

**IFC-born luminaire** (`make_downlight`, `inputs/ifc/chicago-plenum-downlight.ifc`) — 20 → 33 captions,
family-mode VALID 0 errors, provenance ok/clean before and after:

- before (main @ ca74895): Aperture, Aperture Diameter, Bar Hanger Span, CCEA Rating, **Color Temperature**, Frame Length, Frame Width, Housing, Housing Diameter, Housing Height, Lamp, Lens Diameter, **Lumens**, Mounting, Overall Height, Photometric Web File, Trim, Trim Diameter, Voltage, Wattage
- after: Aperture, Aperture Diameter, Apparent Load, Bar Hanger Span, CCEA Rating, Color Rendering Index, Dimming Protocol, Driver Type, Efficacy, Emergency, Frame Length, Frame Width, Housing, Housing Diameter, Housing Height, IP Rating, **Initial Color Temperature**, Lamp, Lens Diameter, Light Loss Factor, Load Classification, **Luminous Flux**, Mounting, Number of Lamps, Operating Weight, Overall Height, Photometric Web File, Switch ID, Trim, Trim Diameter, Voltage, Warranty Duration, Wattage

**Prompt-born luminaire** (`factory.make_luminaire()`, 2x4 troffer) — 25 on main (pre-#633, with the
`Lumens`/`Luminous Flux` + `Color Temperature`/`Initial Color Temperature` twins) → 23 after #633, unchanged by this PR:

- after: Apparent Load, Color Rendering Index, Dimming Protocol, Driver Type, Efficacy, Emergency, Height, IES File (URL reference), IP Rating, Initial Color Temperature, Lamp, Length, Light Loss Factor, Load Classification, Luminous Flux, Mounting, Number of Lamps, Operating Weight, Switch ID, Voltage, Warranty Duration, Wattage, Width

**Shared quantities** (captions on both files): before — 6 (`Color Temperature`, `Lamp`, `Lumens`,
`Mounting`, `Voltage`, `Wattage`, i.e. the IFC-born file shared only the *legacy* names with the
prompt-born file's twins); after — 19, every one spelled identically on both: Apparent Load, Color
Rendering Index, Dimming Protocol, Driver Type, Efficacy, Emergency, IP Rating, Initial Color
Temperature, Lamp, Light Loss Factor, Load Classification, Luminous Flux, Mounting, Number of Lamps,
Operating Weight, Switch ID, Voltage, Warranty Duration, Wattage. Only-on-IFC-born = its 9 measured
dimensions + 4 CCEA strings + `Photometric Web File`; only-on-prompt-born = `Length`/`Width`/`Height`
+ `IES File (URL reference)`. Meaning keys pairwise distinct on both files (zero twins).

| Gate | Before (main @ ca74895) | After |
|---|---|---|
| `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_famgen_standards.py tests/test_famgen_factory.py tests/test_famfrom_ifc_standards.py tests/test_ifc_family.py tests/test_ifc_assembly.py tests/test_router.py -q -rs` | 359 passed, 22 skipped (new module absent) | see PR body (same files + the new module) |
| `python -m rvt.famgen.standards --check` | `27 categories, 0 problems` (main) / `… 34 synonym groups, 0 problems` (#633) | `27 categories, 34 synonym groups, 0 problems` |
| `tools/route.py matrix` | 3181 bytes, sha256 `7dae5d40eb461e9a…` | byte-identical (`cmp` clean) |
| `tools/rvt_validate.py --family` on the IFC-born and prompt-born `.rfa` | VALID 0 errors, 0 warnings | VALID 0 errors, 0 warnings |
| `tools/make_family.py provenance` on both | `ok: true`, `clean: true` | `ok: true`, `clean: true` |
| `tools/route.py run --ifc inputs/ifc/chicago-plenum-downlight.ifc --output rfa` (fresh clone) | exit 0, ASSEMBLY lane after the archetype lane's `rfa-emit` FileNotFoundError (vendor container absent — #94) | identical behaviour; this PR does not touch the emit path |
| `tools/sync_plugin.py` → `--check`; `plugin/scripts/validate_plugin.py`; `tools/dev/check_portable_paths.py` | — | in sync (2–3 files mirrored), PASS (25 assertions), ok |

**Pinned expectations that moved, and why:** `tests/test_ifc_family.py` — the caption list of
`test_downlight_parameters_and_type` (the two photometric names → the table's; plus
`not {"Lumens","Color Temperature"} & caps` and `len == N_PARAMS`), the blank-value asserts
(`Luminous Flux` / `Initial Color Temperature` == 0.0 — unsourced, never invented), the caption
set now asserted as `OWN_PARAMS | authored_params("lighting_fixture")` (derived, so a row added
to the table by another stream does not red this file), and the two counts that were the literal
`20`: `ParamElemFamily` in the read-back test and `len(plan["twin_of"])` in the slow rst-load test
now compare against `len(product.doc.params)` (33 today). **Those last two tests are `needs_emit` /
`needs_load` (vendor archetype / rst sample) and SKIP on this surface — the fresh-clone read-back in
`test_famfrom_ifc_standards.py` (33 captions off the bundled-base `.rfa` == the document's set) is
what observes the number here, not those two tests.**

**`/simplify` round (4 agents):** applied — `factory._std` instead of a bare `standards.apply` (reuse: the hard-rule-1 guard lives in one place and both luminaire routes fail the same way); the `standards=False` + given-`lumens` case says so in a note instead of dropping the value silently (altitude); the explanation kept once in `make_downlight`'s docstring, one-liners elsewhere; `N_PARAMS = 33` replaced by derived sets/counts; the new tests share `_twins` / `_differing` helpers, the two value tests are one parametrized test, the on-file test reuses the module fixtures. Declined — appending `factory._standards_note` to `prod.notes` (`make_luminaire` does not either; `apply` already writes the `doc.notes` line); hoisting `_std` into `standards` and applying the table in the one model-family constructor that still applies none (`intent.make_house_switchboard`; `famgen.heads` builds annotation heads, which have no table by design) — shared infrastructure outside this territory → follow-up below.

## What is NOT claimed

- No desktop round, no viewer batch: 13 more `ParamElemFamily` records + 2 renamed captions on a
  family document whose classes, specs, connector and geometry are unchanged; VALID 0 errors and
  provenance clean is a fact about the file, not evidence Revit opens it (rule 4). The certified
  `L_downlight_loaded.rvt` in the ledger predates this and is not re-certified by it.
- `Photometric Web File` (this route) and `IES File (URL reference)` (the factory) are one
  quantity under two captions and are **still** two captions: neither is in the category table,
  no synonym row folds them, and converging them needs a row in `standards.SYNONYM_GROUPS` plus
  one caption change — `standards.py` is outside this territory → follow-up #641.
- The famspec `downlight` lane and the ifc → rfa *archetype* lane still cannot emit on a fresh
  clone (vendor container default in `write_rfa`) — pre-existing, tracked by #94; the evidence
  above shows the same document emits VALID + provenance-clean through `standalone_family_write`
  on the bundled base, which is the fact #94 needs.

## Follow-ups

- Filed **#642**: one shared standards step for every family constructor (`standards.apply_safe` = today's `factory._std`, used by factory / famfrom_ifc / `intent.make_house_switchboard` — the last one, an Electrical Equipment switchboard, applies no table today although `standards` has a `switchboard` set) — area:famgen, Refs #631 #601.
- Filed **#641**: the photometric-web reference caption (`Photometric Web File` vs `IES File (URL reference)`)
  as one synonym group + one surviving caption (area:famgen, Refs #631).
- Existing: #94 (fresh-clone rfa-emit for the downlight/famspec lanes on the bundled base).

## BRANCH STATE (eng #631)

Branch `cam/631-famfrom-ifc-standards`, cut from `main` after #633's squash landed (developed
against `origin/cam/622-standards-dedup` read-only while #633 was in the tech lead's CI; never
stacked on it).

Files written: `src/rvt/ifc/famfrom_ifc.py` (import `standards`, `STD_CATEGORY`,
`PHOTOMETRIC_JOB_VALUES`, `DownlightProduct.standards` + `summary()`, `make_downlight`
signature/docstring, the photometric pair routed through `factory._std` → `standards.apply`,
module docstring),
`tests/test_famfrom_ifc_standards.py` (new, 9 tests / 10 cases), `tests/ci_shard.d/631-famfrom-ifc-standards.txt`
(new), `tests/test_ifc_family.py` (captions + derived `OWN_PARAMS` / counts), `spec/famspec.schema.json` (two `$ref`s
on the downlight kind — flagged above), `plugin/skills/tekton-author/references/CATALOG-FACTS.md`
(one sentence), mirrors via `tools/sync_plugin.py` (`plugin/lib/src/rvt/ifc/famfrom_ifc.py`,
`plugin/skills/tekton-native/examples/famspec.schema.json`), this section.

Gates: table above + the whole merged CI shard count in the PR body. Staged vs shipped:
everything **shipped** on the branch; nothing staged for a viewer batch (no writer path, base
or certified file touched).

# eng #642 — one standards step for every constructor; given values land in their storage class (2026-08-11)

Issue #642 (Refs #631 #622 #601; steer S-2026-08-11-a "standard parameters everywhere, values
only when known"). Branch `cam/642-standards-apply-safe` from `main` @ 3f18806 (#633 and #644
merged). Territory as chartered: `src/rvt/famgen/standards.py`, the `_std` definition + call
lines of `src/rvt/famgen/factory.py`, the standards call of `src/rvt/ifc/famfrom_ifc.py`, the
standards application of `intent.make_house_switchboard`, mirrors via `sync_plugin`, a new test
module + shard drop-in, this section. Nothing geometric, no writer path, no SKILL.md, no router.

## What was built

- **`standards.apply_safe(doc, category, on=True, values=None, **kw) -> report | None`** — today's
  `factory._std` body, hoisted next to `apply`: `on` False → `None` (and see below); `on` True →
  `apply(...)`; a fault inside the standards module → a `doc.notes` line
  `category standards NOT applied (<Exc>: …)` and `None`, never a failed build (rule 1).
  `factory._std` is **removed** (grep: nothing outside `factory.py` / `famfrom_ifc.py` imported it;
  the one prose mention left is `tests/test_famfrom_ifc_standards.py`'s module docstring, untouched).
  Every model-family constructor now makes this one call: `make_panelboard`, `make_transformer`,
  `make_luminaire`, `make_device`, `make_generic_model` (both bodies — it used a *bare*
  `standards.apply` before, so a table fault there raised instead of noting), `famfrom_ifc.make_downlight`,
  and `intent.make_house_switchboard`. `factory` imports `standards` at module level (it is a table;
  the four lazy in-function imports went with `_std`).
- **Coercion by spec (#642 comment (a))** — `standards.coerce_value(spec_key, value)`: `text` → `str`,
  `integer` → `int` (whole numbers only: `2`, `2.0`, `" 4 "`; `2.5` refused), every measurable spec →
  `float`; a numeric string is the number it spells; anything else raises. `apply` runs every given
  value through it before `add_family_parameter(default=…)`, so `skeleton.family_param_value` files
  `90` for the number-spec `Color Rendering Index` in `m_value` (90.0), not `m_int` beside a 0.0.
  A value that cannot be written leaves the parameter **blank** and is named in a new report key
  `values_unusable` (`[{"name", "why"}]`) and in the `doc.notes` line — coerced, never guessed
  (`"3000K"` is *not* read as 3000). A `None` value is no value (blank, unreported). No change to
  `skeleton.family_param_value` was needed: the entry's spec is known in `apply`, which is where the
  storage class is decided; `skeleton` stays type-driven for every other caller.
- **`standards=False` + offered values (#642 comment (b))** — `apply_safe(on=False, values)` writes ONE
  note naming every non-None offered key: `standards off (<category>): the given [...] are NOT
  authored (they are standard parameters of the category)`. That subsumes the downlight's own
  #644 note (removed from `famfrom_ifc` — job values and caller values now land in the same line,
  which is what `test_famfrom_ifc_standards::test_standards_false_is_the_regression_control` keeps
  asserting) and gives the factory constructors, the generic model and the switchboard the same
  behaviour they lacked.
- **The house switchboard carries the Electrical Equipment `switchboard` set** —
  `make_house_switchboard(..., standards=True, standard_values=None)`; `apply_safe(doc, "switchboard", …)`
  before `finalize`; `FamilyProduct(standards=report)` so `summary()["standards"]` reaches the route
  manifest like every other family. Its nine pset ratings (`BusRating`, `MainsType`, `MainsRating`,
  `ShortCircuitRatingkA`, `Sections`, `Voltage`, `Phases`, `Wires`, `Mounting`) are exactly the nine
  the report skips `already authored by the constructor`; eight rows are added blank (`Bus Material`,
  `Frequency`, `Enclosure Rating`, `Apparent Load` (instance), `Load Classification`,
  `Service Clearance`, `Operating Weight`, `Warranty Duration`) → 16 → **24** parameters, `filled == []`
  (the intent holds no value for any of them; nothing invented).
- **Table row moved to the contract spelling** — the switchboard set listed `Number of Sections`
  (convention, identity group) while the constructor authors and fills `Sections`, which is a key of
  the tekton-ifc tagging contract (`rvt.ifc.intent.CONTRACT_KEYS`, `SwitchboardSchedule.Sections`
  written by `prompt_intent` / `ifc_out`). By this module's own doctrine (#622: one entry per meaning;
  a contract name beats a convention) the row is now `Sections` (integer, electrical,
  `origin=contract`) and `("Sections", "Number of Sections", "Section Count")` is a synonym group, so
  a caller's `Number of Sections` folds onto it instead of growing a twin. No other caller names the
  `switchboard` table (grep), so no existing family's bytes moved. The module docstring's `contract`
  definition now also names `rvt.ifc.intent.CONTRACT_KEYS`.

## Evidence

**Instrument for byte identity.** `standalone_family_write(product, <fixed path>, timestamp=0)` on the
bundled base, then a sha256 over every CFB stream (name + length + bytes) with two nondeterministic
fields neutralised the same way on both sides: the per-document `uuid4` GUID (`skeleton.new_family_document`,
#9) pinned to a counter, and `PartAtom`'s wall-clock `<updated>` stamps blanked. Two consecutive runs
of unchanged `main` agree on all ten rows (checked before trusting it). The standalone `.rfa` lane
emits on the 2026 base only (`RVT_GENESIS_BASE=` the 2025/2024 pins → `EncodeError: missing field
'm_steelModelLastSTC_hash'` on main already — pre-existing, not this issue), so "per pinned base" for
families is the 2026 column; the three releases are covered by the room build below.

| constructor (defaults unless noted) | before (main @ 3f18806) | after | family-mode / provenance (after) | params |
|---|---|---|---|---|
| `make_panelboard` | `afa6c53c758bcb27` | `afa6c53c758bcb27` SAME | VALID 0 err / ok | 21 → 21 |
| `make_transformer` | `78d1cef1f19d4adb` | `78d1cef1f19d4adb` SAME | VALID 0 err / ok | 24 → 24 |
| `make_luminaire` (troffer) | `f42d879b7ed5ac40` | `f42d879b7ed5ac40` SAME | VALID 0 err / ok | 23 → 23 |
| `make_luminaire(kind="downlight", aperture_in=6)` | `ffbad173dff31c42` | `ffbad173dff31c42` SAME | VALID 0 err / ok | 23 → 23 |
| `make_device` | `bb4496e33488ee8a` | `bb4496e33488ee8a` SAME | VALID 0 err / ok | 13 → 13 |
| `make_generic_model` (box) | `6ca41f0ba943b755` | `6ca41f0ba943b755` SAME | VALID 0 err / ok | 6 → 6 |
| `make_generic_model(parts, category="data_devices", standard_values={ports 2, "Cat6A"})` | `bebbe5b60c61f350` | `bebbe5b60c61f350` SAME | VALID 0 err / ok | 16 → 16 |
| `famfrom_ifc.make_downlight` (tracked IFC) | `b3cba4c559b065c5` | `b3cba4c559b065c5` SAME | VALID 0 err / ok | 33 → 33 |
| `intent.make_house_switchboard` (2500 A 480Y/277) | `1f90a61923c67d2a` | `b76695f0b1a4733b` **DIFF — intended, DONE (4)** | VALID 0 err / ok | 16 → 24 |
| `make_luminaire(standard_values={"Color Rendering Index": 90})` | `2bc80a435d7944f7` | `3605601a05b8f360` **DIFF — intended, DONE (2)** | VALID 0 err / ok | 23 → 23 |

**CRI read-back off the written `.rfa`** (`FamilyIndex`: the `Color Rendering Index` `ParamElemFamily`
id → its `FamilyParamValue` on the type row and in `m_familyParams`):
before `{'2x4 38W 4000K': m_value 0.0, m_int 90; <current>: m_value 0.0, m_int 90}` →
after `{'2x4 38W 4000K': m_value 90.0, m_int 0; <current>: m_value 90.0, m_int 0}`. Pinned by
`test_the_written_luminaire_reads_back_cri_90_as_the_value`.

**The room build with a switchboard**, `frontdoor author --prompt "an electrical room with a 2500A
main switchboard, a 75 kVA transformer and 4 panels" --target-version {2026,2025,2024}` then
`rvt_validate` on `prompt_room.rvt`: before and after identical — 2026 `error 0 / warning 1 / info 2`,
2025 `0/0/2`, 2024 `0/0/2`, status PROOF-ONLY (self-checks PASS), `errors: []`; the built
`msb_switchboard_msb_2500a_480y_277.rfa` family-mode VALID 0 errors, provenance ok, 24 parameters,
`standards.category == "switchboard"`, loads and circuits (`F MSB … OK`, `E MSB elem …`, `C circuit … MSB slot …`)
on all three. (The issue's literal prompt "an electrical room with 6 panels" plans no switchboard —
12 panelboards — so it cannot observe DONE (4); it validates 0 errors on all three releases before and
after as well.)

| Gate | Before (main @ 3f18806) | After |
|---|---|---|
| `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_famgen_standards.py tests/test_famgen_factory.py tests/test_famfrom_ifc_standards.py tests/test_ifc_family.py tests/test_intent*.py tests/test_rfa_load.py tests/test_place_fixtures.py -q -rs` | 230 passed, 8 skipped | + `tests/test_standards_apply_safe.py` (46) + `tests/test_ifc_intent.py` (module-skips here: samples): **276 passed, 9 skipped** |
| `python -m rvt.famgen.standards --check` | 27 categories, 34 synonym groups, 0 problems | 27 categories, **35** synonym groups, 0 problems |
| `tools/route.py matrix` | 3181 bytes | byte-identical (`cmp` clean) |
| `tools/sync_plugin.py` → `--check`; `validate_plugin.py`; `check_portable_paths.py` | — | 4 mirrors written, in sync; PASS (25 assertions); ok (3015 paths) |
| whole merged CI shard `pytest $(tools/dev/shard_list.py --print)` | — | see PR body |

**Pinned expectation that moved, and why:** `tests/test_famgen_standards.py::test_the_contract_origin_is_only_used_for_names_the_repo_really_carries`
took `factory.PANEL_CONTRACT_PARAMS` as the whole contract; the switchboard's `Sections` is a
contract key of `rvt.ifc.intent.CONTRACT_KEYS` (the pset join keys), so the test's contract set is now
the union of the two — the assertion (every `origin=contract` name is really in an in-repo contract)
is unchanged in intent and stricter sources were not loosened.

## What is NOT claimed

- No desktop round, no viewer batch: the switchboard gains 8 `ParamElemFamily` records of the kind
  the certified panelboard lineage already carries; the CRI fix changes which slot of an existing
  `FamilyParamValue` holds the number. VALID 0 errors + provenance clean + loads-and-circuits in our
  own loader are facts about the files, not evidence Revit opens them (rule 4).
- `coerce_value` does not parse units or suffixes (`"65 kA"`, `"3000K"`, `"480Y/277"`): such a value is
  reported unusable and the slot stays blank. Values are still expected in internal units, as `apply`'s
  docstring has always said; a famspec that wants unit-bearing strings needs the schedule-scalar parser
  (`intent.parse_schedule_scalar`) in front of it — not built here.
- `FeederEntry` (also a `CONTRACT_KEYS` member the switchboard authors) is not added to the table; the
  row set was touched only where a twin would otherwise have grown.
- The storage class is decided in `standards.apply` (where the entry's spec is known), not in
  `skeleton` — by charter. Constructor literals and famspec fields that bypass the table still depend
  on the author writing `90.0`, not `90` → follow-up #647 moves the rule into `FamilyDoc`'s store points.

**`/simplify` round (4 agents):** applied — the coercion block unpacks the caller's `(spelling, value)`
once; the "placed" meanings are tracked in the loop instead of re-derived afterwards; the "a `None`
value is no value" rule lives once (`_offered`, used by `apply` and `apply_safe`); in the new tests the
identity lambdas went, one `_type_values` and one `_write_valid` helper replaced three inline copies,
the change-detector shrank to "`factory._std` is gone", and the CRI read-back is additionally asserted
in the edit lane's own vocabulary (`convert.modify_family.inventory_family(path).param_by_caption(...)`
→ `carrier == "m_value"`, `current == 90.0`). Declined — editing the stale `factory._std` mention in
`tests/test_famfrom_ifc_standards.py`'s docstring and hoisting the write/read-back helpers into
`conftest.py` (outside this territory); a `CONTRACT_NAME_SOURCES` constant in `standards.py` (it would
make `famgen` import `rvt.ifc` — the wrong direction; the docstring names the sources instead); a shared
storage-class map for `_blank` / `coerce_value` (three lines, one file). The altitude finding is #647.

**`/verify` (the product surface, final diff):** `tools/route.py run --output rfa --rfa '{"kind":
"luminaire", "standard_values": {"Color Rendering Index": 90, "CCT": 3500}}'` → exit 0, `status: OK (…
provenance ok=True; validator family-mode VALID 0 errors)`; `rvt_validate --family` on the delivered
`troffer_2x4_recessed.rfa` VALID, `make_family.py provenance` `ok: true / clean: true`;
`inventory_family` reads `Color Rendering Index: carrier=m_value current=90.0` (raw type row
`{'m_value': 90.0, 'm_int': 0}`); the report lists `filled ['Color Rendering Index']`,
`values_not_placed ['CCT']` (its slot is the constructor's own `Initial Color Temperature`, 4000 K from
the catalog — #622 behaviour, unchanged). The unusable probe `{"Color Rendering Index": "ninety",
"Driver Type": 5}` → still exit 0 / OK / VALID (rule 1), `filled ['Driver Type']`,
`values_unusable [{'name': 'Color Rendering Index', 'why': "'ninety' cannot be written as number …"}]`
and the note line says so. The switchboard room prompt on 2026/2025/2024 after the final diff: room
`error 0` ×3, switchboard family 24 parameters, `standards.category == "switchboard"` ×3.

## Follow-ups

- Filed **#647**: `FamilyDoc` stores every type-row value in its parameter's storage class (the rule
  moves from `standards.apply` into `skeleton`'s store points) — area:famgen, Refs #642.

## BRANCH STATE (eng #642)

Branch `cam/642-standards-apply-safe` from `main` @ 3f18806. Files written:
`src/rvt/famgen/standards.py` (`apply_safe`, `coerce_value`, coercion + `values_unusable` in `apply`,
switchboard `Sections` row + synonym group, docstrings), `src/rvt/famgen/factory.py` (`_std` removed,
six call lines → `ST.apply_safe`, module-level import), `src/rvt/ifc/famfrom_ifc.py` (the call line +
its now-subsumed off-note, import, docstring), `src/rvt/ifc/intent.py` (`make_house_switchboard`:
two kwargs, one call, `standards=` on the product, docstring), `tests/test_standards_apply_safe.py`
(new, 46 cases), `tests/ci_shard.d/642-standards-apply-safe.txt` (new), `tests/test_famgen_standards.py`
(the one contract-set expectation above), mirrors via `tools/sync_plugin.py`
(`plugin/lib/src/rvt/{famgen/factory,famgen/standards,ifc/famfrom_ifc,ifc/intent}.py`), this section.
Everything **shipped** on the branch; nothing staged for a viewer batch (no writer path, base or
certified file touched).
