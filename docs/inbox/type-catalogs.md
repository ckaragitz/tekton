# type-catalogs — one generated family, N catalog-selected types (#163)

Stream: **type-catalogs** (engineer session eng163, 2026-08-09, issue #163, P1,
area:famgen / area:convert). Territory: `src/rvt/famgen/factory.py`,
`tools/make_family.py`, `src/rvt/famgen/loader.py` (minimal, additive — the
multi-type bug it had is described in §3 and was announced on the issue first),
`src/rvt/convert/edit_family.py` (a 3-line `--type` CLI flag, also announced),
`tests/test_famgen_factory.py`, `tests/test_hostsym_product.py`,
`docs/writer/asset-factory.md` §6 row 4, this record, regenerated `plugin/lib`
mirrors. `src/rvt/famload.py` untouched (it already planned N pairs).
Status: **SHIPPED as a PR — family-mode + project validators 0 errors,
provenance clean; NO certification claim (rule 4: "validates in family mode",
never "loads in Revit"); nothing staged for the viewer.**

## 1. Why

Real electrical content ships ONE family per product line with a TYPE per
rating; ours emitted exactly one type per `.rfa` (asset-factory honest limit
#4), so "an electrical room with 6 panels" generates 6 near-identical families
(and pays the per-family cost six times, #124). The skeleton's type table and
the four-registry loader already took N rows; only the factory API/CLI, a
catalog-driven type list, per-type facts in the report, and the component
loader's per-type symbols were missing.

## 2. What was built

* **`factory.make_panelboard / make_transformer / make_luminaire(types=[…])`**
  — `types` = a list of CATALOG SELECTORS along the product's rating axis
  (panelboard: mains A; transformer: kVA; luminaire: input W), each a bare
  number / `'225A'`-style string, or a dict over the product's per-type fields
  (`mains_a, spaces, mcb, sccr_ka, neutral_rating` | `kva` | `wattage, lumens,
  cct, size, aperture_in`, plus an optional explicit `type_name`). Every
  selection resolves ITS OWN fact sheet (`resolve_*_facts`) and becomes one
  `FamilyTypeTable` row carrying its own dims / ratings / Model / Description
  as parameter VALUES. The FIRST selection is the primary type: the one
  enclosure solid + connector(s) are authored at its dimensions (geometry is
  not label-driven — the honest half of limit #4 that stays open, said out
  loud in the product notes and the doc). Family-level inputs (vendor/line,
  voltage, mounting, kind) stay one per family; the family NAME drops whatever
  varies across the types (`Panelboard 480Y/277 MLO 42ckt Surface`,
  `Dry Type Transformer 480-208Y/120`, `Recessed Troffer 2x4`); the file stem
  names the rating set (`eaton_prl2x_225_400_600a_42sp_480y_277`). Two
  selections that resolve to the same type name → `FactoryError` (never a
  silent duplicate row); a selector key that is family-level → `FactoryError`.
* **Per-type facts in the report** — `FamilyProduct.types: List[TypeRow]`
  (name, its `FactSheet`, its catalog values); `summary()` (= the report's
  `family` block) gains `type_facts: [{name, subject, variant, assumed_fields,
  unverified_fields, values}]`, and the family-level `assumed_fields` /
  `unverified_fields` are now the UNION over the types (identical to before for
  one type) so nothing assumed hides in a row. `facts` (the report's `facts`
  block) stays the primary sheet.
* **`tools/make_family.py --types 225,400,600 [--type-catalog]`** on
  `panelboard` / `transformer` / `luminaire`; the human print lists each type's
  assumed fields; `--type-catalog` writes OUR Revit type catalog `<stem>.txt`
  beside the `.rfa` (`FamilyProduct.write_type_catalog`, `factory.type_catalog_text`):
  header `,<param>##<SPEC>##<UNITS>,…` (LENGTH/INCHES, ELECTRICAL_POTENTIAL/VOLTS,
  ELECTRICAL_CURRENT/AMPERES, ELECTRICAL_APPARENT_POWER/VOLT_AMPERES,
  ELECTRICAL_WATTAGE/WATTS, ELECTRICAL_LUMINOUS_FLUX/LUMENS,
  COLOR_TEMPERATURE/KELVIN, text & counts as OTHER), one row per type from the
  same facts the type table carries, comma-bearing cells quoted, pure ASCII,
  CRLF. Authored by us — zero third-party bytes.
* **`rvt.famgen.loader` — one host FamilySymbol + FamSymSurrogate per
  real-named type** (§3). `rvt.famload` already did; both now agree.
* **`python -m rvt.convert.edit_family <rfa> --set NAME=VALUE --type '<type>'`**
  — the flag scopes every `--set` of the call to ONE type-table row (the engine
  supported type-scoped `set-param` ops since 2026-08-04; only the flag was
  missing).

## 3. The multi-type bug in the component loader (why loader.py changed)

`famload._plan_family` plans one `FamSymSurrogate`+`FamilySymbol` pair per
real-named type. `famgen.loader` — the loader the front door's prompt lane
uses (`frontdoor/build.py → load_families_into_project`) — was single-symbol by
construction: `plan_load` allocated one `symbol_id`/`symbol_surrogate_id`,
`author_family_symbol` was "for our (single) type", `_author_load` appended one
symbol + one sym-surrogate, while `author_host_family` copied EVERY real row of
the unit table into the host Family's `FamilyTypeTable`. A 3-type product would
have landed as a host table `[' ', A, B, C]` with only `A` backed by a symbol
pair — rows without symbols, a shape no native host Family row shows
(hostsym-product §1). Change (additive; a one-type load allocates exactly the
ids it always did — pinned by a test): `LoadPlan` gains `type_names /
symbol_ids / symbol_surrogate_ids` (famload's shape; `type_name / symbol_id /
symbol_surrogate_id` stay = the primary, instance-facing pair); `plan_load`
allocates a pair per extra real type right after the primary's; `_author_load`
authors one symbol (its own type's parameter row, the one authored solid) +
sym-surrogate per pair via `dataclasses.replace(plan, …)` so the
geometry/placement code is untouched; `_plan_host_ids`, the
`ElementTrackingData.m_symbols` registration and the written-file verify's
`symbol_tracked` cover all symbols; the host table's `m_idx` points at the
primary's row; `_type_rows(product, type_name)` reads a named row.

## 4. Evidence (this clone: cloud session, no `samples/`, pinned bases present)

**Default (no `types=`) output is byte-identical to `main`** — the four
default products (panelboard, transformer, troffer, downlight) built on `main`
(c66333e) and on this branch under a fixed-uuid / `PYTHONHASHSEED=0` harness and
compared stream by stream (`scratchpad/cmp_rfa.py`, 12 streams each): **ALL
IDENTICAL** modulo the PartAtom `<updated>` wall-clock stamp (the one field that
is build-time by design); same 217,088-byte containers. In-memory: same name,
stem, single type row values, element (id, class) list and notes as an explicit
one-selector build (`test_default_single_type_structure_unchanged`).

**Multi-type builds, all three kinds** (`make_family.py … --types … --type-catalog`):

| file | types | family name | validate (family mode) | provenance | catalog |
|---|---|---|---|---|---|
| `prl_mlo_3.rfa` `--types 225,400,600 --spaces 42 --voltage 480Y/277` | `225A/400A/600A MLO 42ckt` — Height 48/60/72 in (sizing table), MainsRating 225/400/600, Model PRL2X; assumed per type `[height_in, sccr_ka]` | Panelboard 480Y/277 MLO 42ckt Surface | **VALID 0 errors 0 warnings** (45/45 decode) | ok (v2: 11/11 checks; v1 scan ok) | 604 B, 15 columns |
| `dt3_3.rfa` `--types 30,45,75` | `30/45/75 kVA 480-208Y/120` — frames FR940/FR940/FR942, W 24.88/24.88/30.5 in, weight 409/416/570 lb, Model V48M28T3016/…4516/…7516 | Dry Type Transformer 480-208Y/120 | **VALID 0 errors** (43/43) | ok | 644 B, 13 columns |
| `blt_3.rfa` `--kind recessed-troffer --types 30,38,48 --cct 4000` | `2x4 30W/38W/48W 4000K` | Recessed Troffer 2x4 | **VALID 0 errors** (39/39) | ok | 547 B, 9 columns |

`tools/rvt_validate.py --family` on each: `error 0 / warning 0 / info 2`;
`tools/make_family.py provenance` on each: `ok True` (all four checks).
`rvt.convert.modify_family.inventory_family(...).type_names` == the three names
in order for every kind (test-pinned for panelboard / transformer / troffer /
downlight). Sample catalog (ours):

```
,Width##LENGTH##INCHES,Height##LENGTH##INCHES,Depth##LENGTH##INCHES,Voltage##ELECTRICAL_POTENTIAL##VOLTS,…,MainsRating##ELECTRICAL_CURRENT##AMPERES,…,Manufacturer##OTHER##,Model##OTHER##
225A MLO 42ckt,20,48,5.75,480,…,225,…,Eaton,PRL2X
400A MLO 42ckt,20,60,5.75,480,…,400,…,Eaton,PRL2X
600A MLO 42ckt,20,72,5.75,480,…,600,…,Eaton,PRL2X
```

**Scoped edit** — `python -m rvt.convert.edit_family prl_mlo_3.rfa -o e --set
MainsRating=400 --type '225A MLO 42ckt'`: delivered, family-mode **VALID (0
errors)**, re-read ok (`want 400.0 got 400.0`); the type table read back from
the edited file shows only that row changed (225→400; the 400A/600A rows keep
400/600). Same with `--set MainsRating=800 --type '600A MLO 42ckt'` →
`[225, 400, 800]` (test-pinned).

**Loaders, 3-type panel on the pinned base `G_ABPD.rvt`** — famgen.loader plan:
`type_names` = the 3 names, 3 symbol ids + 3 sym-surrogate ids (primary =
`symbol_id`), host table `[' ', 225A…, 400A…, 600A…]` `m_idx 1`; dry-run load
gate **66/66 records round-trip, 0 failed**; classes `Family 1, FamilySurrogate
1, FamilySymbol 3, FamSymSurrogate 3, ParamElemFamily 14`; each symbol real-named,
`m_partitionSurrogateId` = its own surrogate, carrying ITS row (MainsRating
225/400/600). famload plan: 3/3, `author_host_elements` symbols + surrogates all
real-named, gate 66/66. A REAL written unplaced load (`load_family_into_project
(BASE, out.rvt, …, validate=True)`, 1.6 s): project validator **VALID, 0 errors**
(1 warning = the base's own known DataStorage ES-blob gap), `family_documents`
reads back ONE host family `n_types 3` with symbols `225A/400A/600A MCB 42ckt`,
`big2small_count 14`, `n_connectors 1`. Born-shaped (`[' ', A, B, C]`) tables
still yield zero blank pairs in both loaders.

**Tests** (stream-local, this clone):
* `tests/test_famgen_factory.py tests/test_hostsym_product.py tests/test_famgen_catalog.py`
  → **93 passed, 5 skipped** (the 5 = rme/rst `samples/` absent, pre-existing);
  before this change the same three files were 68 passed / 5 skipped — +18
  factory tests (selectors, one row per selection ×4 kinds, per-type facts,
  naming, duplicate refusal, default-unchanged, catalog text, valid+provenance+
  inventory ×4 kinds, scoped edit, CLI flags) and +7 hostsym tests (famgen
  loader ×5, famload ×2).
* Adjacent suites `test_famgen_loader test_famload test_famload_batch
  test_birthright test_species test_convert test_convert_combo test_rfa_load`
  (`RVT_SKIP_LARGE=1`) → all green (149 passed / 49 skipped for the famgen set;
  48 passed for famload_batch + hostsym + rfa_load). One existing pin
  (`test_famload_batch` asserting the exact key set of the verify's `adocument`
  dict) caught an extra key I had added; folded into `symbol_tracked` instead.
* CI shard (`tests/ci_shard.txt`, 38 files) → **778 passed, 44 skipped, 1
  xfailed** after `sync_plugin` (the pre-sync run showed only the expected
  `test_plugin_is_in_sync_with_source` + the pin above).
* Plugin gates: `tools/sync_plugin.py` → synced 3 files, deny-audit clean,
  validation passed, zip rebuilt (5,090 KB); `--check` → in sync;
  `plugin/scripts/validate_plugin.py` → PASS (24 assertions);
  `check_portable_paths` → ok (2761); `test_plugin_sync test_bootstrap
  test_coldstart test_surface_perf` → 26 passed, 5 skipped.
* **Bare unzip, system Python 3.11, no repo on the path:**
  `skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical
  room with 6 panels"` → preflight `tekton: READY … 0.054s`, exit 0, **4.67 s**
  total (under the 8 s ROOM6 ceiling), `prompt_room.rvt` + 6 `.rfa` delivered,
  combined VALID 0 errors / 1 warning, PROOF-ONLY stamped (the default
  single-type lane — unchanged bytes — is what the front door still uses).

## 5. Findings / follow-ups (filed as issues, not done here)

* **Front door: generate ONE multi-type panel family per (line, voltage,
  mounting) group and place N instances of its types** instead of N families —
  the pay-off of this PR for the 6-panel room (#124's per-family cost ×1
  instead of ×6). Needs `frontdoor/build.py` + the famgen loader's placement to
  bind each instance to the right `symbol_ids[i]`; out of territory here (a
  frontdoor PR is in flight). Filed.
* **Label-driven geometry** (limit #4's open half): a placed non-primary type
  displays the primary's box until `FamDimConstrMgr` expressions bind
  Width/Height/Depth to the extrusion — the geometry stream's recipe §5.
* The downlight record has no wattage, so its generated type name is
  `'<aperture>in <cct>K'`; lumen-package types need the explicit `type_name`
  selector key today (test shows it). Putting lumens into the downlight type
  name would change the default single-type name — deliberately not done in a
  "default unchanged" PR.

## BRANCH STATE

* Branch `cam/163-type-catalogs` from `origin/main` c66333e; commits: loader
  N-pair extension; factory `types=` + TypeRow + type catalog; make_family
  `--types/--type-catalog` + edit_family `--type`; tests; doc row + this record;
  plugin mirrors (`plugin/lib/src/rvt/{famgen/factory.py,famgen/loader.py,convert/edit_family.py}`).
* Gates: all listed in §4, green in this clone; NO full-suite run (charter).
* Shipped vs staged: product code + CLI + tests + docs shipped in the PR;
  **nothing staged for the viewer, no certification claim**; no `.rvt`/`.rfa`/
  `.txt` outputs committed (scratch only, each validated 0 errors / provenance ok).
* Hot files: none touched. `famgen/loader.py` and `convert/edit_family.py`
  edits announced on #163 before they were made (issue comment), kept minimal.
