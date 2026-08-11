# eng #630 — the transformer's weight is `Operating Weight`, a mass (2026-08-11)

*Fragment of the `family-standards` stream (index: `docs/inbox/family-standards.md`). Written by
eng #630 (cam-karagitz's engineer session for issue #630); nobody else appends here.*

Issue #630 (filed by eng #622): #622 made every generated family list each quantity once, and the
dry-type transformer's one surviving weight entry was the legacy `Weight` — a plain `number` in
lb — because `factory` had no mass path: no `SPEC["mass"]`, no lb → internal-mass conversion in
`_TO_INTERNAL`, no mass column in `TYPE_CATALOG_COLUMNS` (the catalog pinned `Weight##OTHER##`).
`rvt.famgen.standards` carried that as a stated exception, `_without(_EE_COMMON, "Operating Weight")`
plus a row note. So the transformer was the one piece of electrical equipment whose weight was a
unitless number under a different name than the panelboard / switchboard / mechanical sets.
Steer S-2026-08-11-a: one parameter per meaning, correct types, values only when known.

Territory used: `src/rvt/famgen/factory.py` (the transformer constructor + `SPEC` /
`_TO_INTERNAL` / `TYPE_CATALOG_COLUMNS` and the new `KG_PER_LB` / `pounds`), `src/rvt/famgen/standards.py`
(the transformer row, the retired `_without` helper, one docstring paragraph), their two
`plugin/lib` mirrors via `tools/sync_plugin.py`, NEW `tests/test_transformer_mass_630.py` +
`tests/ci_shard.d/630-transformer-mass.txt`, six flipped expectations in
`tests/test_famgen_factory.py` / `tests/test_famgen_standards.py` (listed below), this fragment.
Not touched beyond that one line: `skeleton.py`'s store points (#647), any other constructor, `SKILL.md`, `src/rvt/ifc/**`,
`family_units.json` (mass was already there — see below).

## What was built

- **`factory.SPEC["mass"] = standards.SPECS["mass"]`** = `autodesk.spec.aec.structural:mass-1.0.0` —
  no new literal: the id our own units table (`assets/family_units.json`, `m_formatOptionsMap`)
  already declares, formatted in `autodesk.unit.unit:poundsMass-1.0.1`, accuracy 0.01. Mass was
  **not** missing from the units table; nothing there changed.
- **`factory.KG_PER_LB = 0.45359237`, `factory.pounds(lb)`, `_TO_INTERNAL["mass"] = pounds`.**
  The internal mass unit is **kilograms**, not the display unit. Sources, both in-repo and
  verified rather than assumed: (a) the file's internal system is (kg, ft, s) — the basis
  `genesis.settings` already states and uses for `m_dAirDensity` (`_KG_M3_TO_INTERNAL = 0.3048**3`,
  "kg/m^3 -> kg/ft^3") and `genesis.residue_b` for stress (`PA_TO_INTERNAL = 0.3048`,
  "Pa -> kg/(ft s^2)"); (b) `skeleton`'s VERIFIED electrical factor: 208 V reads back 2238.89 =
  208 / 0.3048² — V = kg·m²/(s³·A), so a store that rescales volts by the length factor *alone*
  has a kilogram mass basis (a pound-mass basis would read 208 V as 4935.9). Autodesk's published
  API developer guide (Units: "seven base quantities, each with its own internal unit … Mass:
  kilogram") says the same; it was read, not copied. 1 lb = 0.45359237 kg is the international
  pound's *definition*, so the factor is exact. `pounds()` sits in `factory.py` next to
  `_TO_INTERNAL` rather than beside `skeleton.volts` because `skeleton.py`'s unit helpers are
  #647's territory this round (moving it is part of follow-up #660).
- **`TYPE_CATALOG_COLUMNS["mass"] = ("MASS", "POUNDS_MASS")`** → header
  **`Operating Weight##MASS##POUNDS_MASS`**, cell in lb. Why that token pair: every existing row of
  the table obeys one law — TYPE = the parameter data type in upper snake case (Autodesk's "Create a
  Type Catalog": engineering types spelled `discipline_datatype`, e.g.
  `ELECTRICAL_APPARENT_POWER`, structural/common ones bare, e.g. the documented `FORCE##KIPS`,
  `LENGTH##FEET`), UNITS = the unit id our units table names for the spec, upper snake case
  (`voltAmperes` → `VOLT_AMPERES`, `kelvin` → `KELVIN`, `inches` → `INCHES`). Applied to mass:
  `structural:mass` → `MASS`, `unit:poundsMass` → `POUNDS_MASS`. **Marked INFERRED in the code
  comment**: no Revit-exported transformer catalog is in the repo to quote the token from, and the
  public help page lists only a "sample" of types. The failure mode is honest: a wrong catalog token
  makes Revit's *catalog import* complain about that column; it can never mis-scale the family's
  own stored kg value, and the `.rfa` is unaffected (the catalog is the optional `--type-catalog`
  sidecar). The DONE's fallback (`OTHER` with the displayed unit) was not taken because the law
  above is the same one the seven shipped columns were built by.
- **`make_transformer`** authors `Operating Weight` (mass, Identity Data) **always** — Eaton and
  HPS name every parameter identically — and each type that publishes `weight_lb` feeds
  `("Operating Weight", "mass", lb)` through `_add_type_row`, the single entry list that gives the
  type table kg and the catalog row lb (they cannot drift). The rule is **per type** (the
  `/simplify` round retired the family-level `has_weight` flag): a type without a published weight
  stays a blank 0.0 on its row and gets an empty catalog cell — never an invented `0` lb beside a
  sibling's real weight. HPS (no published weight at all): blank parameter, no weight column,
  exactly as before under the old name. No shipped vendor mixes weighted and weightless types, so
  default outputs are identical under either rule (sha table below unchanged by that edit).
- **`write_type_catalog`'s report names inferred columns**: `INFERRED_CATALOG_SPECS = ("mass",)`;
  when a catalog carries such a column the report gains `inferred_columns`
  (`["Operating Weight##MASS##POUNDS_MASS"]`) and a `note` saying the declaration is inferred and
  that a rejected catalog import never touches the family's stored value — the `_standards_note`
  precedent (INFERRED status surfaces where a user reads, not only in source). Absent otherwise, so
  panelboard / luminaire / HPS reports are unchanged.
- **`standards.py`**: the transformer row is `_merge((its nine own rows), _EE_COMMON)` — the
  `_without(...)` carve-out, its four-line note and the `_without` helper (no other caller) are
  gone; the module docstring's "where a legacy spelling is KEPT" sentence now says no product set
  carves an exception. `SYNONYM_GROUPS` untouched (`Operating Weight` / `Weight` / `Unit Weight`
  were already one group), so `apply` reports `Operating Weight` as "already authored by the
  constructor" and never adds a twin.

## Read-backs (the instrument: `standalone_family_write(timestamp=0)` on the bundled base, then `rvt.convert.modify_family.inventory_family` + a `FamilyIndex` walk of `m_pFamilyTypes`)

| transformer | before (main 697928f) | after |
|---|---|---|
| Eaton 75 kVA, captions matching *weight* | `Weight` — `autodesk.spec.aec:number-1.0.0`, ParamDefValue, m_value **570.0** | `Operating Weight` — `autodesk.spec.aec.structural:mass-1.0.0`, ParamDefValue, group identityData, m_value **258.5476509** (= 570 × 0.45359237) |
| Eaton 30/45/75 kVA, per type row | `Weight` 409.0 / 416.0 / 570.0 | `Operating Weight` 185.51927933 / 188.69442592 / 258.5476509 kg |
| HPS 75 kVA | `Weight` (number) 0.0 | `Operating Weight` (mass) **0.0** — blank |
| meaning twins on the document (`meaning_key`) | none (`Weight` alone) | none (`Operating Weight` alone); `Weight` appears in no caption list |
| Eaton vs HPS parameter name sets | equal (24 = 24) | equal (24 = 24) |

Catalog header, Eaton (quoted off `out/630/eaton.txt`, `make_family.py transformer --types 30,45,75 --type-catalog`):

- before: `…,Temperature Rise##OTHER##,Weight##OTHER##,Frame##OTHER##,…` with cells `409` / `416` / `570`
- after: `…,Temperature Rise##OTHER##,Operating Weight##MASS##POUNDS_MASS,Frame##OTHER##,…` with cells `409` / `416` / `570` (lb, unchanged)
- HPS before and after: no weight column (`…,Temperature Rise##OTHER##,Frame##OTHER##,…`).

## Every other constructor is content-identical

Instrument (the #649 one, restated in a scratch script): build each constructor with the
per-document `uuid4` pinned to a counter, `standalone_family_write(…, timestamp=0)`, sha256 over
every CFB stream (name + length + bytes) with PartAtom's `<updated>` / `<A:updated>` stamps
blanked. Two consecutive runs of unmodified `main` agree on all eleven rows (checked before
trusting it — the first attempt missed the namespaced `<A:updated>` stamp and disagreed; instrument
fixed, readings retaken).

| constructor (defaults unless noted) | before (main 697928f) | after | family-mode / provenance (after) | params |
|---|---|---|---|---|
| `make_panelboard` | `ead55425de5f6d9e` | `ead55425de5f6d9e` SAME | VALID 0 err / ok | 21 → 21 |
| `make_transformer(kva=75)` (Eaton) | `00a6d945a9f13ce2` | `5b04a5480f395d92` **DIFF — intended** | VALID 0 err / ok | 24 → 24 |
| `make_transformer(kva=30, types=[30,45,75])` | `2c74d6b089a51d01` | `cb6f551db4fdcc41` **DIFF — intended** | VALID 0 err / ok | 24 → 24 |
| `make_transformer(kva=75, vendor="hps")` | `c5dcc42a8f76ab1b` | `55226dad26c37b41` **DIFF — intended** (spec id + caption) | VALID 0 err / ok | 24 → 24 |
| `make_luminaire` (troffer) | `2b11d57a6fa37440` | SAME | VALID 0 err / ok | 23 → 23 |
| `make_luminaire(kind="downlight", aperture_in=6)` | `abc4629e9767b898` | SAME | VALID 0 err / ok | 23 → 23 |
| `make_device` | `dda2b82fc429b8b3` | SAME | VALID 0 err / ok | 13 → 13 |
| `make_generic_model` (box, mechanical_equipment) | `bf0ed3a7d094b1e1` | SAME | VALID 0 err / ok | 21 → 21 |
| `make_generic_model` (data device, `standard_values`) | `5284e50cf892b356` | SAME | VALID 0 err / ok | 16 → 16 |
| `famfrom_ifc.make_downlight` (tracked IFC) | `8342c79c43ffe6d8` | SAME | VALID 0 err / ok | 33 → 33 |
| `intent.make_house_switchboard` (2500 A 480Y/277) | `280fd78db685d046` | SAME | VALID 0 err / ok | 24 → 24 |

## Evidence

| gate | before (main 697928f) | after |
|---|---|---|
| `RVT_SKIP_LARGE=1 pytest tests/test_transformer_mass_630.py tests/test_famgen_standards.py tests/test_famgen_factory.py tests/test_famgen_catalog.py tests/test_standards_apply_safe.py tests/test_rfa_load.py tests/test_place_fixtures.py -q -rs` | 245 passed, 5 skipped (rme/rst samples absent) | **254 passed, 5 skipped** (+9 = the new module) on d8b3caa; after the #658 fold-in (+2 tests) and with `tests/test_famgen_skeleton.py` + `tests/test_plugin_sync.py` added to the set: **278 passed, 14 skipped** (the 9 extra skips are skeleton's sample-.rfa cases) |
| `python -m rvt.famgen.standards --check` | 27 categories, 35 synonym groups, 0 problems | 27 categories, 35 synonym groups, **0 problems** |
| `tools/route.py matrix` | 3181 bytes, sha256 `7dae5d40eb461e9a…` | **byte-identical** (`cmp` clean) |
| `tools/make_family.py transformer --types 30,45,75 --type-catalog --json` (Eaton) → `rvt_validate.py --family` / `make_family.py provenance` | VALID 0 / ok | **VALID (no errors), warnings 0** / **ok**; `Operating Weight` reads back mass, m_value 185.519… on the current (30 kVA) type |
| same, `--vendor hps --kva 75` | VALID 0 / ok | **VALID (no errors)** / **ok**; `Operating Weight` mass, 0.0; report has no `inferred_columns` (no weight column) |
| `/verify`: `frontdoor author --prompt "an electrical room with a 75 kVA transformer and 4 panels"` (generates, loads, places T1) → `rvt_validate prompt_room.rvt` | PROOF-ONLY (self-checks PASS); VALID 0 errors / 1 warning / 2 info | **identical**: PROOF-ONLY (self-checks PASS); VALID 0 / 1 / 2; `F T1 -> t1_xfmr_75kva_480_208y_120.rfa (OK: validate=VALID, provenance ok=True)`, `E T1 elem … (dangling refs 0, dropped rows 0)`; the loaded `.rfa` family-mode VALID 0 |
| `tools/sync_plugin.py` → `--check`; `validate_plugin.py`; `check_portable_paths.py` | — | 2 mirrors written, in sync (deny-audit clean, identity scan == allowlist); PASS (25 assertions); ok |
| whole merged CI shard `RVT_SKIP_LARGE=1 pytest -q -p no:cacheprovider $(tools/dev/shard_list.py --print)` (109 files) | — | **2289 passed, 134 skipped, 3 xfailed, 0 failed** in 539 s on the final tree |

**Pinned expectations that flipped, and why** (each is the direct consequence of the rename +
unit change; none was loosened):

- `tests/test_famgen_factory.py::test_multi_type_rows_carry_per_type_facts` — `TypeRow.as_json()["values"]["Weight"]` → `["Operating Weight"]`, still `[409, 416, 570]` (catalog rows carry lb).
- `tests/test_famgen_factory.py::test_write_type_catalog_lands_beside_the_rfa_and_in_the_report` — `"Weight##OTHER##"` → `"Operating Weight##MASS##POUNDS_MASS"` in the report's columns.
- `tests/test_famgen_standards.py::test_the_panel_only_parameters_are_not_on_every_electrical_equipment` — the "both product sets extend the category set" law was stated over meaning keys with `common - xfmr == {"Operating Weight"}`; it is now stated by name (`common <= xfmr`, `"Weight" not in xfmr`) — stricter.
- `tests/test_famgen_standards.py::test_the_transformer_keeps_weight_as_its_single_weight_entry_with_a_stated_reason` → **inverted** into `test_every_equipment_set_names_its_one_weight_entry_operating_weight_mass` (the issue's DONE 3 names this inversion): every equipment set incl. the transformer has `Operating Weight` (mass) and no `Weight`; the transformer's tail is `_EE_COMMON` verbatim.
- `tests/test_famgen_standards.py::test_every_generated_family_lists_each_quantity_once_and_the_values_still_land[make_transformer]` — filled `{"Operating Weight", …}`, gone `{"Enclosure", "Weight"}` (was filled `Weight`, gone `Operating Weight`).
- `tests/test_famgen_standards.py::test_the_transformer_connector_and_catalog_follow_the_renamed_enclosure_but_keep_weight` → renamed `…_and_the_mass_weight`: type-row value `570 * KG_PER_LB`, header `Operating Weight##MASS##POUNDS_MASS`, HPS carries `Operating Weight` blank and no `Weight`.

## What is NOT claimed

- No desktop round, no viewer batch: the change swaps one measurable `ParamDefValue`'s spec id
  (number → structural mass) and caption on the transformer; blank mass `Operating Weight`
  parameters of exactly this shape already ship on every panelboard / switchboard / luminaire the
  standards table touches. Validator-green + provenance-clean is necessary, not certification
  (hard rule 4); honest status unchanged, `route.py matrix` byte-identical.
- The `MASS##POUNDS_MASS` catalog token is inferred from the vocabulary's law, not quoted from a
  Revit export (see above). The first desktop session that loads the Eaton family *with* its
  catalog settles it; if Revit rejects the column the fix is one tuple.

## `/simplify` round (4 agents: reuse / simplification / efficiency / altitude)

Applied: the per-type weight entry (`has_weight` retired — finding shared by simplification and
altitude); the `KG_PER_LB` and `TYPE_CATALOG_COLUMNS` comments cut to the law + one inline
`[INFERRED]` tag (the derivation lives here); the constructor's four-line changelog comment → one
line; the `standards` docstring sentence made grammatical and history-free; the inferred catalog
token surfaced in `write_type_catalog`'s report (altitude 6); tests — the `hasattr(ST, "_without")`
deletion-pin, the `_EE_COMMON` tail-slice pin, the volts / apparent-power "argument by test"
assertions and the duplicated `[409, 416, 570]` as_json check dropped, the on-file test
parametrized on kwargs + the primary type's lb directly, module-scoped `eaton` / `hps` fixtures
(efficiency: three redundant builds, ~50 ms), and `factory.SPEC ⊆ standards.SPECS` pinned
value-for-value instead of rewriting `factory.SPEC` (altitude 2's minimum ask). Declined, with
reason: moving `pounds` beside `skeleton.volts` and adding `MASS` to `skeleton.SHARED_DATATYPE_SPECS`
— `skeleton.py` is #647's territory this round (filed, below); aliasing `factory.SPEC = standards.SPECS`
wholesale — widens the factory's authorable set to 40 keys with no converters / catalog columns
behind them, i.e. the registry follow-up's job, not a rename PR's; hoisting `_write_valid` /
read-back helpers into `tests/conftest.py` — shared test infrastructure outside this territory
(three modules now copy them; noted for the registry follow-up).

**The edge this PR opened, and closed in the same PR (#658, tech-lead ruling — territory extended to
exactly one line of `skeleton.py` + its mirror + one test):** the mass parameter is now authored on
the constructor's own (unguarded) path, and `skeleton.SHARED_DATATYPE_SPECS` had no `MASS` token,
so a *user* shared-parameter file with a row `Operating Weight / MASS` made
`make_transformer(shared_params=…)` raise `ValueError … declares DATATYPE 'MASS' but the family
authors it as '…structural:mass-1.0.0'` — a non-delivery (hard rule 1) even on an undocumented
input (reproduced on the first head d8b3caa; `main` built the same file only because the parameter
was `Weight`; `make_panelboard` built and *skipped* the parameter). Fix:
`SHARED_DATATYPE_SPECS["MASS"] = ("autodesk.spec.aec.structural:mass",)`. After: the same file →
`make_family.py transformer --types 30,45,75 --shared-params <file> --json` **ok, family-mode VALID
0, provenance ok / 0 suspects, `rvt_validate --family` VALID warnings=0**, `shared_parameters`
= `{Mounting, Operating Weight → the row's GUID, Phases, Voltage, Wires}`; on the file the
`Operating Weight` `ParamElemExternal` decodes with `m_guidValue` = the row's GUID, `m_specTypeId`
mass, `m_typeId` = `shared_param_type_id(guid)`; `make_panelboard` with the file promotes it too
(no skip). A `NUMBER` row for the mass parameter still raises the datatype guard (kept). Default
builds (no file) byte-identical: the sha table above re-taken after the line — unchanged.

## Follow-ups (searched first — none existed; filed task-shaped with `Refs #630`)

- **#658** (P1, area:famgen) — filed for the edge above, then **closed by this PR** on the tech
  lead's ruling (`Closes #658`).
- **#659** (P1, area:engine) — the edit lane's `_convert_value` has no mass branch:
  `edit_family --set "Operating Weight=600 lb"` stores 600 (kg) with a false "dimensionless" note;
  reuse `KG_PER_LB`, refuse a unitless mass like a unitless length. P1 because this PR is what puts
  a filled mass value in users' hands.
- **#660** (P2, area:famgen) — one spec registry per key (id, converter, catalog token + provenance,
  shared DATATYPE token) with a coverage test; homes `pounds` beside `volts` and retires the four
  hand-kept lists that let #658/#659 happen.

## BRANCH STATE (eng #630)

- Branch `cam/630-transformer-mass` from `main` @ 697928f (rebased on 61988e3); PR #662, `Closes #630`, `Closes #658`.
- Files written: `src/rvt/famgen/factory.py`, `src/rvt/famgen/standards.py`,
  `plugin/lib/src/rvt/famgen/{factory,standards}.py` (mirrors, via `tools/sync_plugin.py`),
  `src/rvt/famgen/skeleton.py` (one `SHARED_DATATYPE_SPECS` line, #658) + its mirror,
  `tests/test_transformer_mass_630.py` (new, 10 tests / 11 cases), `tests/ci_shard.d/630-transformer-mass.txt` (new),
  `tests/test_famgen_factory.py` (2 expectations), `tests/test_famgen_standards.py` (4 tests),
  `docs/inbox/family-standards.d/630-transformer-mass.md` (this fragment; the `.d/` is new, the
  index `docs/inbox/family-standards.md` is untouched).
- Gates: the tables above; whole merged CI shard count in the PR body. Staged vs shipped: nothing
  staged (no viewer batch); shipped = the code + tests above. `out/630/*.rfa|txt` are local
  verification outputs, not committed.
