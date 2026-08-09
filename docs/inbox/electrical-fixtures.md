# electrical-fixtures — the third electrical category: wiring devices generate, load unplaced, and are prompted as planned devices (issue #166)

Stream: `electrical-fixtures` (eng #166, cloud engineer session, 2026-08-09) · Refs #108 (requirements
sweep wave 2, axis RFA / families), #101 (prompt grammar neighbour) · program goal PG6 · follow-ups
filed: **#359** (front door LOADS + PLACES Electrical Fixtures), **#361** (famspec kind `device`).

## Why

The facts for NEMA 5-15R / 5-20R receptacles, the single-pole switch, the 4 in square box and the code
mounting heights were already in the store (`facts/generic/devices-and-mounting.json`), the skeleton
already knew `OST_ElectricalFixtures`, and the prompt parser already recognised "receptacles / outlets" —
but only to report them under `not_built`. This stream makes the category real where our own code can:
a generated family, a CLI verb, an honest load lane, and a prompt/intent that plans and lays the devices
out instead of shrugging.

## The decision the issue asked for (made first): placement is a follow-up (#359)

The DONE said: *"if placement of the new category needs loader work beyond a template-instance mapping,
ship generation + `--no-place` load first and file the placement as a `Refs` follow-up."* It does —
three pieces outside this stream's territory pin the front door's family pipeline to Electrical
Equipment:

| Piece | Where | What pins it |
|---|---|---|
| constructor dispatch | `tools/ifc_intent.py::_constructor_for` (:110-118) | only `make_panelboard` / `make_transformer` / `make_house_switchboard`; a `make_device` plan raises `KeyError` in stage F/L |
| host survey category | `rvt.famgen.loader.load_family_into_project` (:1561) and `load_families_into_project` (:1725) | both call `survey_host(host_rvt)` with its **default** `category=CAT_ELECTRICAL_EQUIPMENT` (the function itself is parameterised) → surrogates / `FamilySymbol` header / tracking row of a fixtures family would carry the equipment category; the batched loader surveys ONE category for N families |
| placement specimen + scrub | `tools/ifc_intent.py::stage_equipment` (:833-868) | clones the certified ancestor's Electrical **Equipment** instance and scrubs with `category=OST_ELECTRICAL_EQUIPMENT` hard-coded; the issue's own measurement (`LoaderError 'no template instance for placement'`) is this |

`tools/ifc_intent.py` / `build.py` were held by #146 during this session, and `loader.py` is not this
stream's territory. So: generation + unplaced load + prompt planning shipped here; load-and-place in the
room build is #359 (P1, ready, body written with the exact file:line evidence above and a no-regression
clause for mixed prompts).

## What was built

| Piece | Where | What |
|---|---|---|
| **Facts gap filled** (facts only, every leaf flagged) | `src/rvt/famgen/facts/generic/devices-and-mounting.json` | `options.plate_in {w,h,t}` on all four variants (single-gang wall plate 2.75 × 4.5 × 0.25 in envelope; 4 × 4 × 1/16 in blank cover for the box) — `assumed`; `options.unit_load_va {180, NEC 220.14(I)}` on the two receptacles — `assumed` (recalled code figure); `options.mounting_height_aff_in {typical 18}` on the box — `assumed`. `python -m rvt.famgen.catalog validate` → `[OK] generic/devices-and-mounting`, 4 variants, **4 fact / 37 assumed / 0 unsourced / 0 missing flags** (was 4 / 30). |
| **Facts resolver** | `rvt.famgen.factory.resolve_device_facts(kind, mounting_height_in=None, voltage=120, va=180)` + `DEVICE_KINDS` / `device_kind()` (aliases: receptacle/outlet/5-15r → duplex-receptacle, 5-20r, toggle-switch/light-switch → switch, jbox/j-box/box → junction-box) | box envelope ← `dims_in` (flag from the record: `assumed` for devices, `fact` for the 4 in square identity); plate ← `options.plate_in`; `mounting_height_in` = given (`given`) else the record's typical (18 receptacle & box / 48 switch, `assumed`, note carried); `ada_reach_range_in [15, 48]` from `line_facts` (`fact`, ADA 308.2.1); `device_rating_v/a` (record); `voltage_v` / `load_va` = the JOB's connector values (`given`; the load note cites the NEC 220.14(I) 180 VA unit load, and says out loud that a switch / box carries no code unit load); `configuration` / `manufacturer='generic'` (`ours`), `model` = the variant. Unknown kind → `FactoryError` naming the known kinds. |
| **The constructor** | `rvt.famgen.factory.make_device(kind, mounting_height_in=None, voltage=120, va=180, solid=True, name=None, start_id=1000, shared_params=None)` | `OST_ElectricalFixtures`, part type 0, **work-plane-based** exactly like the panelboard (family XY = the wall face; *no face-/wall-hosting claim*); parameters `Voltage` (voltage), `Load` (apparent power, electrical-loads group), `MountingHeight` (length, constraints) + the identity built-ins on the ONE type row (`Manufacturer='generic'`, `Model=<variant>`, `Description`); geometry = `G.plate` **faceplate proud of the face** (z 0..t) + `add_box_form` **device box recessed** (z −d..0); ONE connector via the #323 API: `add_connector(face='bottom' = the back of the box, poles=1, voltage_v=120, apparent_load_va=180, primary=True, bind_voltage_param='Voltage', bind_load_param='Load', load_class 'Receptacle' | 'Power')` → Power-Unbalanced (31), load on phase 1, `m_bIsConnectorPrimary True`; `FamilyProduct(kind='device', forms=[plate, box])`, notes surface every assumed field. |
| **CLI** | `tools/make_family.py` | new verb **`device --kind duplex-receptacle|duplex-receptacle-20a|switch|junction-box [--height IN] [--voltage 120] [--va 180] [--shared-params FILE] [--dummy] -o OUT [--json]`**; `load` gains **`--family {panelboard,device} --kind … --height … --va …`**: the device lane loads **UNPLACED** through the certified four-registry loader (`rvt.famload` via `famfrom_ifc.load_into_project`, `core_categories=(the family's own category,)` — the famspec→rvt lane), default host = the pinned genesis base (bundled → runs on a fresh clone), prints one JSON with `placed: false` + the #359 pointer; asking to place prints the honest note and loads unplaced anyway (rule 1). `--voltage` default is now per family (480Y/277 panelboard / 120 device). |
| **Prompt grammar** | `src/rvt/frontdoor/prompt_intent.py` | `receptacle_device` moved from `_UNBUILT_PATTERNS` to `_KIND_PATTERNS` (tag prefix `R`; duplex / convenience / quad / gfci / general-purpose receptacles, (power|wall) outlets, never "receptacle panel"); `PLANNED_ONLY_KINDS = {receptacle_device: "issue #359 …"}`; `_RE_AFF` reads a mounting height ('at 18 in AFF', '44 inches above the finished floor', '1100 mm mounting height' — unit **and** an AFF phrase required, so a count or the room's 'N ft high' is never taken; digits ≤ 4); `PromptItem.height_in`; `_apply_defaults` device branch (120 V, 180 VA, height from OUR facts via `_device_height_default()` — ONE coverage line per clause, stating the `assumed` convention and the ADA 15..48 in FACT); `_contract_for` → a `DeviceSchedule` pset (Voltage 120 V, Phases 1, Wires 2, Load, MountingHeight, Mounting, DeviceType); `_default_dims` from the facts (plate w × h, box depth + plate); layout = **the wall-panel law** (west/east interior faces, upright frame into the room, alternating W/E) with devices sorted after every panel kind and `z = _wall_mount_z(item)` = the AFF height (panels keep 1.42 m); `prompt_to_intent`: `IfcOutlet` / `POWEROUTLET`, description names the height, disposition says "generated-family, NOT loaded/placed by this route yet (#359)", and **`_plan_device()`** replaces the resolver's `unmapped` plan with a real `FamilyPlan(constructor='rvt.famgen.factory.make_device', kwargs, catalog/variant/facts_summary, status='planned', refusal="not a refusal: … #359")`; scene brief: `receptacle_R-n` groups, `DeviceSchedule` pset with typed Load / MountingHeight / DeviceType. The unbuilt-reason prose no longer claims devices are unbuildable and points luminaires at #150. Clause boundaries no longer split on a decimal point inside a number (`\.(?!\d)`) — '1.1 m above the floor' / '7.5 kVA' stay one clause. |
| **IFC intent constants** (only these, per territory) | `src/rvt/ifc/intent.py` | `KIND_BY_CLASS['IfcOutlet'] = 'receptacle_device'`; `GENERATED_KINDS += ('receptacle_device',)` (disposition `generated-family`; audit `load_equipment_unfed` now lists devices honestly). `plan_family_for` untouched (its device branch is #359's, so the IFC route's outlets stay `unmapped` with the generic reason until then). |
| **Docs** | `plugin/skills/tekton-author/references/CATALOG-FACTS.md`, `docs/product/PERMUTATION-MATRIX.md` | store row rewritten (envelopes / unit load / heights / ADA fact); constructor table gains the device row with its honest status (+ fixed the stale `make_lightfixture` name → `make_luminaire` / `make_downlight`); prompt→rvt and prompt→rfa caveat text say what happens to prompted receptacles today. `matrix.py` untouched — no cell's truth changed (`verify_evidence()` green, doc test agrees). |
| **Tests** | `tests/test_famgen_factory.py` (+3 kinds in `ALL_KINDS`, `test_device_facts_resolve_from_the_generic_record`, `test_device_family_composition[3]`, `test_make_family_cli_device_verb_writes_a_valid_rfa`), `tests/test_prompt_intent.py` (+3), `tests/test_frontdoor.py` (+`test_e2e_prompted_receptacles_are_delivered_as_planned_devices`) | all fresh-clone-safe (bundled base + catalog only); all three files are already in the CI shard. |

## Evidence (fresh cloud clone: no `samples/`, no `extracted/`; bundled pinned base G_ABPD)

**Generation — `tools/make_family.py device --kind K -o out.rfa`, then `tools/rvt_validate.py out.rfa --family` and `tools/make_family.py provenance out.rfa`:**

| kind | family name | elements | forms (in) | connector decode ON THE FILE (poles / V / VA ph1 / primary / system) | family-mode validate | `rvt_validate --family` | provenance |
|---|---|---|---|---|---|---|---|
| duplex-receptacle | Duplex Receptacle NEMA 5-15R 120V | 52 | plate 2.75×4.5×0.25 @z0; box 1.9×4.19×2.5 @z−2.5 | 1 / 120 / 180 / True / 31 | VALID 0 err 0 warn | 0 errors, 0 warnings (159 records, 52 elements) | ok, suspects [] (11/11 v2 checks; standalone scan 4/4) |
| switch | Single Pole Switch Single Pole 120V | 52 | same envelope | 1 / 120 / 180 / True / 31 | VALID 0 / 0 | 0 / 0 | ok |
| junction-box | Junction Box 4in Square 120V | 52 | plate 4×4×0.0625; box 4×4×1.5 (facts) | 1 / 120 / 180 / True / 31 | VALID 0 / 0 | 0 / 0 | ok |

Unverified fields surfaced per family: receptacle/switch 11 (`box_*`, `plate_*`, `device_rating_*`, `mounting_height_in`, `voltage_v`, `load_va`); junction box 6 (the box dims are facts).

**Unplaced load — `tools/make_family.py load --family device --kind duplex-receptacle -o dev_loaded.rvt`** (host = `plugin/assets/genesis/G_ABPD.rvt`): loader `rvt.famload.load_family_document (four-registry, L1a mechanism)`, plan category **−2001060**, host Family 1472577 / symbol 1472583, `placed: false`, project validator **VALID, 0 errors / 1 warning**, wall time **2.2 s**.

**The DONE prompt — `tools/frontdoor.py author --prompt 'a room with 4 duplex receptacles' --out out/x --json`:** exit **0**, 1.4 s, status `PROOF-ONLY (self-checks PASS …)`; `intent.summary.equipment_by_kind = {receptacle_device: 4}`, `family_plans_by_status = {planned: 4}` (constructor `make_device`, variant `duplex-receptacle-5-15R`, kwargs `{kind duplex-receptacle, mounting_height_in 18.0, voltage '120', va 180.0}`); insertions (−4.47 | +4.47, y, **0.457 m = 18 in**) upright on W-W / W-E, `equipment_inside_room_ring 4/4`; coverage `not_built []`, `ignored_words []`, defaults state the 120 V / 180 VA NEC line and the 18 in convention + ADA 15..48 in fact; build: `errors []`, combination verdict `single` (n_instances 0 — the open cell is not exercised, so no open-cell stamp; the standing PROOF-ONLY status-gate stamp applies), `elements_created = 4 × wall`, **4 degradation lines** `R-n (receptacle_device): NOT built -- family plan planned: not a refusal: … loads UNPLACED … issue #359`, `prompt_room.rvt` project validator **VALID 0 errors / 1 warning**; MANIFEST.md carries `equipment (4): receptacle_device×4` and both default lines. *Not* 4 placed instances — that half of the DONE is #359, by the DONE's own fallback clause.

**No regression on mixed prompts** (the reason device plans are `planned`, not `resolved`: `stage_load_batched` stops the batch at the first un-authorable family, and `R-1` sorts before `RP-1` / `T1` at equal feeder depth): `'… 150 kVA transformer, a 225 A 208Y/120 receptacle panel and 6 receptacles at 1.1 m above the floor'` → buildable plans `[RP-1, T1]`, `combination_check.n_instances == 2`, feeders `[(T1, RP-1)]`, devices at z 1.1 m after the panel on the same faces; `'… 1600A switchboard, twelve 2x4 LED troffers …'` parses byte-for-byte as on `main` (luminaire still `not_built`).

**Gates:** `tests/test_famgen_factory.py` 57 passed / 5 skipped; `tests/test_prompt_intent.py` + `tests/test_frontdoor.py` (RVT_SKIP_LARGE=1) 82 passed / 4 skipped; `tests/test_router.py -k matrix` 8 passed; `tools/sync_plugin.py` → 4 mirrors regenerated, `--check` clean (deny-audit clean, identity scan == allowlist); `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py` ok (2833 paths). `tests/test_famgen_skeleton.py` does not exist (nothing to run). Full-suite not run (SUITE-COORDINATION).

## Findings

- `survey_host(category=…)` is already parameterised; only its two callers pin the default — #359 is mostly plumbing (`product.doc.category_id`), plus the stage-E specimen/scrub category and `_constructor_for`. Do the category generalisation once for #150 (luminaires) and #359.
- `rvt.famload` (the T2a/L1a-certified mechanism) takes the category from the family document; that is why the device load lane here is `famfrom_ifc.load_into_project`, not `rvt.famgen.loader`.
- Router nit seen while measuring (recorded in #361's Context): `router._families_from_model` reads `f['status']`/`f['refusal']` where `stage_families` writes `reason` → "NOT built -- None" caveats for every unbuilt plan on `route.py run --output rfa --prompt …`.
- The clause-boundary regex treated the '.' in '1.1 m' as a sentence stop; fixed narrowly (`\.(?!\d)`), suites unchanged.

## Open questions

- Face-hosting: real Revit receptacle content is usually wall-/face-hosted; ours is work-plane-based like the panelboard (the certified placement law). Whether an engineer expects hosted behaviour is a PG8 beta question, not assumed here.
- The junction box's "mounting height" has no code meaning; 18 in is an editable placeholder (`assumed`, said in the record's note).

## BRANCH STATE

- Branch `cam/166-electrical-fixtures` from `main` @ fba7efb; PR #358 (`Closes #166`).
- Files written: `src/rvt/famgen/factory.py`, `src/rvt/famgen/facts/generic/devices-and-mounting.json`, `tools/make_family.py`, `src/rvt/frontdoor/prompt_intent.py`, `src/rvt/ifc/intent.py` (two constants), `plugin/skills/tekton-author/references/CATALOG-FACTS.md`, `docs/product/PERMUTATION-MATRIX.md` (caveat prose only), `tests/test_famgen_factory.py`, `tests/test_prompt_intent.py`, `tests/test_frontdoor.py`, this record; regenerated mirrors `plugin/lib/src/rvt/{famgen/factory.py, famgen/facts/generic/devices-and-mounting.json, frontdoor/prompt_intent.py, ifc/intent.py}`.
- Not touched: hot files (`tools/frontdoor.py` used only, `SKILL.md`, `versions/`, `base.py`, TRACKER/KNOWLEDGE, ledger), #146's files (`standalone.py`, `mutate.py`, `mep/devices.py`, `tools/ifc_intent.py`, `build.py`, `matrix.py`), `loader.py`, `router.py`, the #349 census.
- Shipped: generation (3 kinds), CLI verbs, unplaced load lane, prompt/intent planning + layout, docs, tests. Staged for viewer: nothing (no "loads in Revit" claim; validator-green only — rule 4). Follow-ups: #359 (load + place in the room build), #361 (famspec kind `device` + the router caveat-key nit).
