# famspec-contract — the structured family request, written down and wired for every kind (issue #162)

Stream: `famspec-contract` (eng #162, cloud engineer session, 2026-08-09) · Refs #108 (requirements
sweep wave 2, axis RFA/families), #94, #99, #5 · program goal PG1 (honest capability table),
S-2026-08-04-a (drivable from any AI surface with structured input).

## Why

The router's `rfa` input accepted exactly one famspec kind (`{"kind": "downlight"}`, the measured
product archetype — owner-machine only), refused the three catalog constructors the prompt/IFC lanes
already use with `UNSUPPORTED-FAMSPEC-KIND`, and there was **no written contract** for what a famspec
may contain. A stranger or another AI surface could not ask for "an Eaton 225 A panel family" as
structured input; `rfa → rfa` was a MISSING cell.

## What was built

| Piece | Where | What |
|---|---|---|
| **The contract** | `spec/famspec.schema.json` (new, JSON Schema **draft-07**, our own text) | `kind ∈ {panelboard, transformer, luminaire, downlight}` selects the constructor; a `oneOf` of four `additionalProperties:false` objects whose fields **mirror the constructor's keyword arguments** (`rvt.famgen.factory.make_panelboard / make_transformer / make_luminaire`, `rvt.ifc.famfrom_ifc.make_downlight`) minus `start_id`; luminaire's own `kind` is spelt `fixture` (because `kind` selects the constructor); optional route field `target_version` (integer year, same meaning as `--target-version`, the CLI flag wins); optional `shared_params` (path, or `"default"` = OUR `usecases/eaton-panelboard/panelboard-shared-parameters.txt` from #340); `types` = multi-type selectors (number \| `'400A'` string \| per-type object). Vendor/line/fixture strings are *described*, not enum-pinned — the catalog grows and refusal-by-name is the factory's job. |
| **Worked examples** | `spec/examples/famspec-{panelboard,transformer,luminaire}.json` (new) | eaton pow-r-line 225 A / 42 sp / 208Y/120 MCB surface `LP-1`; eaton 45 kVA 480→208Y/120; lithonia 2x4 recessed troffer 4000 K. |
| **The contract in code** | `src/rvt/frontdoor/famspec.py` (new module, import-light: json/os/re + `.base`) | `schema_path()/schema()` (repo `spec/`, else the plugin's mirrored copy via `standalone.plugin_root()`, negative-cached); `check_schema()` = a **stdlib-only validator** for the draft-07 subset the schema uses (type/enum/const/required/properties/additionalProperties/oneOf/anyOf/local `$ref`/minimum/maximum/exclusiveMinimum/minLength/minItems/items/pattern; `oneOf` failures reported for the branch whose `kind` matches, not all four) — **no `jsonschema` dependency added** (the repo has none to reuse: only `experiments/gen_ifc_min.py` imports it); `validate()` degrades to built-in kind/target_version checks where the schema file is not shipped; `normalise()` → `(kind, constructor kwargs, route options)`; `build()` / `write()` / `is_refusal()` / `constructor_name()` so the router holds no per-kind logic. |
| **Router dispatch** | `src/rvt/frontdoor/router.py` | `_FAMSPEC_KINDS = famspec.KINDS` (all four); new route **`rfa_generate`** (`rfa → rfa`: famspec → OUR standalone `.rfa` via `_emit_at_target`, so `--target-version` behaves exactly as prompt→rfa; a `.rfa` path alone → the clear line); `rfa_load`'s famspec lane generalised from downlight-only to every kind (emit the `.rfa`, then the **existing** `_load_family` → `famfrom_ifc.load_into_project` → `rvt.famload` four-registry load, `core_categories` = the built document's own `category_id`); invalid famspec → `INVALID-FAMSPEC` / `UNSUPPORTED-FAMSPEC-KIND (x)` + ONE clear line naming the field; constructor refusal → `FAILED (famspec->rfa: …)` + "REFUSED BY NAME" line; status via the shared `_convert_status` (OK / DELIVERED WITH A RED GATE / FAILED); stamp `FAMSPEC_STAMP` (PROOF-ONLY) on every famspec deliverable; `_target_base` memoised per route (`RouteResult._bases`, not serialised) so a route that emits then loads states the version block once; `_settle_ifc_clause()` in `_emit_at_target`: the fallback line keeps its "IFC alongside" promise only when `_emit_ifc_addition` actually wrote one (a famspec resolves no room intent → the line says so instead). |
| **Matrix** | `src/rvt/frontdoor/matrix.py` | new stage `famspec->rfa`; `rfa → rfa` flipped MISSING → **WORKS** (`rfa_generate`); `rfa → rvt` / `rfa+rvt → rvt` stages + caveats rewritten (`_RFA_INPUT` form (a) = all four kinds per the schema, `_RFA_FAMSPEC_ENV` = catalog kinds run anywhere / downlight owner-machine, new `_FAMSPEC_GATES` = validator+provenance gated, no standalone `.rfa` of ours in the ledger, delivered regardless). Census 21 cells: **18 works / 1 partial / 2 missing** (was 17/1/3). |
| **Doc** | `docs/product/PERMUTATION-MATRIX.md` | No generator exists (`tests/test_router.py::test_permutation_matrix_doc_agrees_with_machine_matrix` pins the hand-kept doc to the machine matrix cell-for-cell): census line, inputs bullet, `rfa → rvt` / `rfa → rfa` / `rfa+rvt → rvt` rows and the named-gaps list edited by hand to match. |
| **CLI** | `tools/route.py` | usage examples + `--rfa` help name the four kinds and the schema (no behaviour change; `--json` is still ONE document). |
| **Plugin** | `tools/sync_plugin.py` map + regenerated mirrors | `spec/famspec.schema.json` + the three examples mirrored to `plugin/skills/tekton-native/examples/` (beside `building.schema.json`), where `famspec.schema_path()` finds them in a bare bundle; `plugin/lib/src/rvt/frontdoor/{famspec,router,matrix}.py` regenerated. |
| **Tests** | `tests/test_router.py` §2b (+2 stale cases updated) | 28 new cases, **all runnable on a fresh clone without `samples/` and without ifcopenshell** (verified with ifcopenshell shadowed by an ImportError stub): schema is draft-07 and covers every kind; **schema fields == `inspect.signature(make_<kind>)`** per catalog kind; the three examples validate + normalise; 8 invalid famspecs named by the stdlib validator and turned into the clear line by the router; rich shapes (types/target_version/shared_params default) accepted; `.rfa` path alone → clear line; **e2e `rfa → rfa` per kind** (VALID 0 errors, provenance ok, `validate_file(family=True)` 0 errors, `provenance_scan` ok, PROOF-ONLY stamp, manifest); **e2e `rfa → rvt` per kind onto the pinned base** (load ok, project VALID 0 errors, registries coherent + ours_in_all_four, no "Revit" claim in the status, no instance placed); catalog refusal by name; target_version field vs flag (2025 match → `.rfa` IS 2025; flag wins; 2023 → delivered native + the line without an IFC promise); `route.py run --rfa FAMSPEC --output rfa --json` is ONE document; `explain --inputs rfa --output rfa` exit 0. `test_cli_explain_missing_cell` now uses `rfa → ifc`; `test_unwired_famspec_kind…` became `test_unknown_famspec_kind_is_one_clear_line[rvt|rfa]`. |

## Evidence (fresh cloud clone: no `samples/`, no `extracted/`; numbers, not adjectives)

The two DONE commands per kind (`tools/route.py run --output {rfa,rvt} --rfa spec/examples/famspec-<kind>.json --out …`):

| kind | `--output rfa` | family | elements | types | family-mode validator | `rvt_validate.py --family` | `make_family.py provenance` | `.rfa` bytes | s | `--output rvt` (pinned G_ABPD 2026) | project validator | census | s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| panelboard | OK | Panelboard 208Y/120 225A MCB 42ckt Surface | 45 | `225A MCB 42ckt` | VALID 0 err | error 0 / warning 0 | ok=True (4/4 checks) | 221,184 | 0.3 | OK, host family 1472570 / symbol 1472587 | 0 errors (`rvt_validate.py`: 0 errors, 1 known DataStorage decode-gap warning of the base) | coherent, ours in all four | 1.5 |
| transformer | OK | Dry Type Transformer 45kVA 480-208Y/120 | 43 | `45 kVA 480-208Y/120` | VALID 0 err | 0 | ok=True | 217,088 | 0.1 | OK | 0 errors | coherent | 1.2 |
| luminaire | OK | Recessed Troffer 2x4 38W | 39 | `2x4 38W 4000K` | VALID 0 err | 0 | ok=True | 217,088 | 0.1 | OK | 0 errors | coherent | 1.3 |

- `--json` on all six: stdout parses as ONE JSON document, stderr 0 bytes, stage chatter in `<out>/route.log` (#313/#188 contract intact).
- Version: famspec `target_version: 2025` → `.rfa` detected as Revit **2025** (`status: match`, caveat "taken from the famspec"); `--target-version 2024 --output rvt` → `.rfa` **2024** + loaded `.rvt` **2024**, VALID 0 errors; `--target-version 2023` → both delivered at 2026, `status: fallback`, ONE "target 2023 requested…" caveat, line ends "no IFC rides beside a FAMILY request…" (no false IFC promise), errors 0.
- Negative: `{"kind":"panelboard","mains":225}` → `INVALID-FAMSPEC`, line names `unknown field 'mains' (allowed: …)`, exit 4; `{"kind":"switchboard"}` → `UNSUPPORTED-FAMSPEC-KIND (switchboard)`; `mains_a: 5000` → `FAILED (famspec->rfa: no sizing rows for 5000.0 A mains; tabulated: [100, 225, 400, 600])` + "REFUSED BY NAME"; a `.rfa` path with `--output rfa` → `UNSUPPORTED-INPUT-FORM`, exit 4. No tracebacks anywhere.
- Multi-type + shared: `types: [225, "400A", {"mains_a": 600, "type_name": "600A big"}], shared_params: "default"` → 3 type rows, 11 shared parameters at OUR GUIDs, VALID.
- **Bare surface**: `tekton-plugin.zip` unzipped to a temp dir, `env -i` + system `python3` 3.11 (no numpy, olefile vendored via `tekton_env.ensure_engine`), no repo on `sys.path`: schema found at `<plugin>/skills/tekton-native/examples/famspec.schema.json`; all six kind×cell routes `ok=True` (0.1–0.4 s emit, 1.2–1.3 s load); a bad famspec is named in the bundle too. (Exposing `route.py` itself as a skill verb is not part of this issue — the skills reach the engine through `go`; see follow-ups.)
- `tools/route.py matrix`: `rfa → rfa WORKS route=rfa_generate`, `rfa → rvt … stages: famspec->rfa -> rfa-load -> …`, "21 cells: 18 works / 1 partial / 2 missing", **evidence self-audit clean** (21 cells, 23 stages, 5 chains), exit 0. `verify_evidence()` is exercised by `test_evidence_self_audit_is_clean` (it caught the missing record on the first run — working as designed).

## Gates run (this session, this head)

- `tests/test_router.py`: **104 passed, 4 skipped** (worked .rvt absent; family container archetype absent = downlight famspec, owner machine; genesis/specimen ancestor absent ×2), 25 s. Under `RVT_SKIP_LARGE=1` with ifcopenshell hidden and no samples: the 28 new §2b cases + the doc/audit/coherence cases **59 passed, 1 skipped**.
- `tests/test_router_release.py tests/test_frontdoor.py tests/test_famgen_factory.py tests/test_target2025.py`: **129 passed, 17 skipped** (all skips = absent samples/bases), 40 s.
- `tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_plugin_validate.py tests/test_surface_perf.py`: **34 passed, 5 skipped**.
- `tools/sync_plugin.py` → synced, deny-audit clean, identity scan == allowlist, zip rebuilt; `--check` → in sync, exit 0. `plugin/scripts/validate_plugin.py` → PASS (25 assertions). `tools/dev/check_portable_paths.py` → ok. `tools/route.py matrix` → exit 0, audit clean.
- `/simplify` (4 reviewers) → 12 findings applied (see "Router dispatch" row: `_convert_status` reuse, `plugin_root()` reuse, category from the built doc, memoised `_target_base` instead of caveat filtering, IFC clause settled at emit time, write/refusal dispatch in `famspec.py`, dead fallbacks removed, tests tidied); 1 skipped (below). `/verify` → see the PR body (run before the commit).

## Findings

1. **The fallback line over-promised for family requests.** `rvt.frontdoor._resolve_base_and_version` (hot file) bakes "the IFC alongside is version-agnostic" into every fallback line; `_emit_ifc_addition` writes an IFC only when there is a room intent or a source IFC. prompt→rfa always has an intent, so nobody noticed; a famspec has neither. Fixed at emit time in the router (`_settle_ifc_clause`, keyed on `vb['ifc_addition']`); the deeper fix belongs in the resolver (follow-up).
2. **A route that emits and then loads resolved `--target-version` twice**, re-stating the version caveat and (potentially) the resolver's errors. Memoising `_target_base` per `RouteResult` fixed both without string filtering.
3. `famfrom_ifc.load_into_project` declares `core_categories=(OST_LightingFixtures,)` by default — right for the downlight, wrong for a panelboard going through the same helper. `_load_family` now takes the category from the document being loaded (`prod.doc.category_id`), for the downlight lane too.
4. The plugin ships the router but no `route.py`/`go route` verb; famspec requests from a skill session would go through Python today. Not this issue's DONE; noted below.

## Open questions / follow-ups (searched before filing; filed as task issues where new)

- **Resolver-level IFC clause** (`rvt.frontdoor._resolve_base_and_version` should append the IFC sentence only when an IFC is written) — hot file `src/rvt/frontdoor/__init__.py`; small `hot-file` task.
- **`go route …` / famspec verb on the skill surface** so a bare plugin session can pass a famspec without writing Python (touches `plugin/skills/_shared/tekton_env.py` + SKILL.md hot files) — task for the plugin surface epic (#110) owners to sequence.
- **Downlight famspec on the bundled base** — already the named gap "famfrom_ifc emits on the bundled container" (PERMUTATION-MATRIX named gaps; #161 is the adjacent luminaire-downlight regression). No new issue.
- **Viewer/desktop round for one famspec `.rfa` + its loaded project** (needs-viewer / needs-revit-desktop): would move the famspec lane from validator-gated to ledgered. Candidate for the next STAGED batch by whoever holds a `/batches` reservation; not staged here (no reservation, and the loaded-family-without-instance shape is already the certified WF shape).
- Option considered and skipped in `/simplify`: shipping the schema as `rvt` package data (`src/rvt/frontdoor/assets/`) instead of probing the plugin's examples dir — would duplicate the DONE-named `spec/famspec.schema.json`; revisit if the engine is ever pip-installed without the plugin tree.

## BRANCH STATE

- Branch `cam/162-famspec-kinds` from `main` @ 935b419; one PR, `Closes #162`.
- Files written: `spec/famspec.schema.json` (new), `spec/examples/famspec-{panelboard,transformer,luminaire}.json` (new), `src/rvt/frontdoor/famspec.py` (new), `src/rvt/frontdoor/router.py`, `src/rvt/frontdoor/matrix.py`, `docs/product/PERMUTATION-MATRIX.md`, `tests/test_router.py`, `tools/route.py` (help text), `tools/sync_plugin.py` (mirror map), `docs/inbox/famspec-contract.md` (this record); regenerated mirrors `plugin/lib/src/rvt/frontdoor/{famspec,router,matrix}.py`, `plugin/skills/tekton-native/examples/famspec*.json`. No hot file touched (`tools/frontdoor.py`, SKILL.md, `src/rvt/versions/`, `src/rvt/frontdoor/base.py`, TRACKER/KNOWLEDGE, ledger untouched); `rvt.famgen.factory` untouched (constructors called as they are).
- Gates: listed above, all green on this head. Nothing STAGED for the viewer (no batch reserved; not required by the DONE). Shipped = code + contract + tests + docs; certification state unchanged (PROOF-ONLY stamps ride every famspec output).

---

## eng #361 — 2026-08-10 — famspec kind `device` (the wiring-device family through the router's rfa cells)

Stream: `famspec-contract` continued (eng #361, cloud engineer session `session_01RUCj179tWnLvwQ1Q2t3xJW`, started
by the tech-lead session) · Refs #166 (shipped `rvt.famgen.factory.make_device`), #162 (the contract above),
#359 (the room build placing devices — a different lane, untouched here) · PG3 / PG6.

### Why

`make_device(kind, mounting_height_in=None, voltage=120, va=180)` (duplex receptacle 5-15R / 5-20R, single-pole
switch, 4 in square junction box; category Electrical Fixtures) existed only behind the repo CLI
`tools/make_family.py device`; the famspec — the product's structured family request on every surface — refused
`{"kind": "device"}` with `UNSUPPORTED-FAMSPEC-KIND`. The plugin ships the schema and the router, not `make_family.py`.

### What was built (all inside the issue's territory)

| Piece | Where | What |
|---|---|---|
| Contract | `spec/famspec.schema.json` | `"device"` added to the `kind` enum and the `oneOf`; new `definitions/device` (`additionalProperties:false`): `device` = **enum of `rvt.famgen.factory.DEVICE_KINDS`** (`duplex-receptacle` / `duplex-receptacle-20a` / `switch` / `junction-box`; it is make_device's own `kind`, renamed because `kind` selects the constructor — the luminaire/`fixture` precedent), `mounting_height_in` (> 0), `voltage` (the shared voltage shape), `va` (≥ 0: a switch / junction box books none), + common `name` / `solid` / `target_version` / `shared_params`. No `types` (make_device is single-type). Top description + the downlight note now say "four catalog kinds". |
| Worked example | `spec/examples/famspec-device.json` (new) | `{"kind":"device","device":"duplex-receptacle","mounting_height_in":18,"voltage":120,"va":180}`. |
| Contract in code | `src/rvt/frontdoor/famspec.py` | `CATALOG_KINDS` gains `device` (so `KINDS` = panelboard, transformer, luminaire, device, downlight); the per-kind rename became one table `OWN_KIND_FIELD = {"luminaire": "fixture", "device": "device"}` used by `normalise()`; `build()` needed nothing (`getattr(factory, f"make_{kind}")`). |
| Router | `src/rvt/frontdoor/router.py` (famspec dispatch wording only) | `_FAMSPEC_KINDS_ALT` derives the "'panelboard' \| … \| 'downlight'" alternatives of the rfa clear line from `FS.KINDS` instead of a hand-typed four-kind string; `_r_rfa_generate` docstring. **No dispatch code changed** — the #162 design (validate → normalise → `FS.build`) carried the new kind as intended. |
| Matrix | `src/rvt/frontdoor/matrix.py` (caveat wording + one evidence pointer) | `famspec->rfa` stage impl names `make_device`; `_RFA_INPUT` / `_RFA_FAMSPEC_ENV` list `device`; `rfa → rvt` famspec caveat: "all five kinds LOAD … the device kind lands UNPLACED as an Electrical Fixtures host family, category −2001060"; `rfa → rfa` cell: evidence `worked:spec/examples/famspec-device.json` added, first caveat lists `device` and carries **re-measured** fresh-clone element counts (the old "45 / 43 / 39" predates the shared view constellation of S-2026-08-10-a: today panelboard 87 / transformer 75 / luminaire 81 / device 73). No cell status flipped; `verify_evidence()` clean (21 cells, 23 stages, 5 chains). `_CATALOG` (shared with the prompt/IFC cells) deliberately **left as is**: on `main` the prompt lane still does not build device families (`R-1: NOT built`, see finding 2), so listing the device there would over-claim for `prompt → rfa`. |
| CLI | `tools/route.py` | `--rfa` help lists `'device'`. |
| Skill reference | `plugin/skills/tekton-author/references/CATALOG-FACTS.md` (hand-authored reference, not a SKILL.md) | the wiring-device row now names the famspec kind `device`, its fields, how a plugin session reaches it (`rvt.frontdoor.router.route({"rfa": {…}}, "rfa"\|"rvt")`; repo `tools/route.py run --rfa '{…}' --output rfa\|rvt`), and the honest status: validator-green + provenance clean + PROOF-ONLY, **not viewer-certified as these artifacts** (rule 4); the "until #361 lands" wording retired. |
| Tests | `tests/test_router.py` §2b | kinds pin updated (+ `oneOf` order == `FS.KINDS`); the **schema-fields == `inspect.signature(make_<kind>)`** law now parametrised over `FS.CATALOG_KINDS` (device included, rename via `FS.OWN_KIND_FIELD`); new `test_famspec_device_field_enumerates_the_factory_device_kinds` (schema enum == `factory.DEVICE_KINDS`, no `types`, normalise renames `device`→`kind`, an alias like `outlet` is a schema line); +2 invalid-famspec rows (`mounting_height` typo → "unknown field", `toaster` → "is not one of"); the per-kind e2e `rfa → rfa` test now also asserts the **category reported by the writer AND read back from the written file** (`RfaSource(rfa).facts.category`: −2001040 / −2001040 / −2001120 / **−2001060**); the per-kind e2e `rfa → rvt` test asserts the host Family's category in the load report's family inventory; the ONE-JSON CLI test also runs the issue-title form `--rfa '{"kind": "device", "device": "duplex-receptacle"}'` inline. `FAMSPEC_EXAMPLES` is keyed on `CATALOG_KINDS`, so every existing per-kind case picked the device up by itself. `tests/test_router.py` is already in the CI shard (`tests/ci_shard.d/102-test-router.txt`) — no new test file, no new drop-in. |

### Evidence (fresh cloud clone, no `samples/`; this head)

`tools/route.py run --output rfa --rfa spec/examples/famspec-<kind>.json --json` (exit 0, stdout = ONE JSON document each):

| kind | family | elements | types | family-mode validator | provenance | category (report / read back) | `.rfa` bytes | emit s |
|---|---|---|---|---|---|---|---|---|
| panelboard | Panelboard 208Y/120 225A MCB 42ckt Surface | 87 | `225A MCB 42ckt` | VALID 0 err | ok | Electrical Equipment / −2001040 | 225,280 | 0.4 |
| transformer | Dry Type Transformer 45kVA 480-208Y/120 | 75 | `45 kVA 480-208Y/120` | VALID 0 err | ok | Electrical Equipment / −2001040 | 225,280 | 0.4 |
| luminaire | Recessed Troffer 2x4 38W | 81 | `2x4 38W 4000K` | VALID 0 err | ok | Lighting Fixtures / −2001120 | 225,280 | 0.4 |
| **device** | **Duplex Receptacle NEMA 5-15R 120V** | **73** | `NEMA 5-15R 120V` | **VALID 0 err** | **ok** | **Electrical Fixtures / −2001060** | 225,280 | 0.4 |

Independent gates on the device `.rfa`: `tools/rvt_validate.py … --family --json` → `ok: true`, error 0 / warning 0 / info 2, 73 elements decoded, 0 decode failures, 1,239 refs checked; `tools/make_family.py provenance …` → `"ok": true`; `rvt.convert.rfa_load.RfaSource(rfa).facts` → category **−2001060**, part_type 0, types `['NEMA 5-15R 120V']`, release 2026.

Every device kind through both cells (`R.route({"rfa": {"kind": "device", "device": K}}, "rfa" | "rvt")`, default host = pinned `G_ABPD` 2026):

| device | family | elements | family-mode | prov | read-back cat | emit s | `--output rvt` | project validator | census coherent / ours in all four | load s |
|---|---|---|---|---|---|---|---|---|---|---|
| duplex-receptacle | Duplex Receptacle NEMA 5-15R 120V | 73 | VALID 0 | ok | −2001060 | 0.4 | OK, host family 1472598, category −2001060 | VALID 0 errors | True / True | 1.5 |
| duplex-receptacle-20a | Duplex Receptacle NEMA 5-20R 120V | 73 | VALID 0 | ok | −2001060 | 0.2 | OK, −2001060 | VALID 0 | True / True | 1.5 |
| switch | Single Pole Switch Single Pole 120V | 73 | VALID 0 | ok | −2001060 | 0.2 | OK, −2001060 | VALID 0 | True / True | 1.5 |
| junction-box | Junction Box 4in Square 120V | 73 | VALID 0 | ok | −2001060 | 0.2 | OK, −2001060 | VALID 0 | True / True | 1.6 |

- Per release: `{"kind":"device","device":"switch","mounting_height_in":44,"target_version":2025}` `--output rfa` → `.rfa` IS **2025** (`status: match`, caveat "target_version=2025 taken from the famspec"); `{"device":"junction-box","va":0,"voltage":"277"}` `--output rvt --target-version 2024` → `.rfa` **2024** + loaded `.rvt` **2024**, project validates 0 errors.
- Negative, one clear line each, `INVALID-FAMSPEC`, exit 4, no traceback: `"device":"toaster"` → `$.device: 'toaster' is not one of ['duplex-receptacle', 'duplex-receptacle-20a', 'switch', 'junction-box']`; `"mounting_height": 44` → `$: unknown field 'mounting_height' (allowed: device, kind, mounting_height_in, name, shared_params, solid, target_version, va, voltage)`; `"va": -1` → `$.va: -1 < minimum 0`.
- `tools/route.py matrix` → 21 cells: 18 works / 1 partial / 2 missing (unchanged), evidence self-audit clean; `route.py explain --inputs rfa --output rfa` lists `worked:spec/examples/famspec-device.json` and the five-kind caveat, exit 0. Honest status everywhere: validator-green + PROOF-ONLY, never "certified" (rule 4).

### Gates run (this head)

- `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_router.py tests/test_famgen_factory.py tests/test_router_release.py -q -rs` → **179 passed, 17 skipped** (skips: `RVT_SKIP_LARGE` ×10, worked .rvt absent, chmod-as-root, rme/rst samples absent ×5), 43 s. The famspec/rfa subset alone: 51 passed, 2 skipped, 14 s.
- `tools/sync_plugin.py` → synced (mirrors `plugin/lib/src/rvt/frontdoor/{famspec,router,matrix}.py`, `plugin/skills/tekton-native/examples/famspec.schema.json`), deny-audit clean, identity scan == allowlist, validation passed, zip rebuilt; `--check` → in sync, exit 0. `plugin/scripts/validate_plugin.py` → PASS (25 assertions). `tools/dev/check_portable_paths.py` → ok (2869 → 2870 tracked paths).
- `/simplify` (4 reviewers): applied — the router's second hand-typed kinds join now reuses `_FAMSPEC_KINDS_ALT`; numerals dropped from prose ("every famspec kind LOADS", "the catalog kinds (…)") so the next kind touches fewer lines; the test's category oracle spelt with `SK.OST_*` + `SK.category_label`; the device schema test trimmed of assertions the parametrised cases already make; the CATALOG-FACTS row tightened. Skipped with reason: the inline-JSON CLI run stays (only success-path test of the issue-title command form, ~0.4 s).
- `/verify` (drove `tools/route.py`, this head): `run --output rfa --rfa '{"kind":"device","device":"duplex-receptacle","mounting_height_in":18,"voltage":120,"va":180}' --json` → rc 0, stderr 0 bytes, ONE JSON: `ok true`, `rfa_generate`, `OK (device family 'Duplex Receptacle NEMA 5-15R 120V' … 73 elements … provenance ok=True; validator family-mode VALID 0 errors)`, PROOF-ONLY stamp; `rvt_validate.py <rfa> --family` → VALID, error 0 / warning 0 / info 2; `make_family.py provenance` → `"ok": true`; `RfaSource(rfa).facts` → −2001060 / part_type 0 / `['NEMA 5-15R 120V']` / 2026. `run --output rvt --rfa spec/examples/famspec-device.json --target-version 2025 --json` → rc 0, `rfa_load`, releases `{'rfa': 2025, 'loaded_rvt': 2025}` `match`, host family 1472522 category −2001060, project VALID 0 errors (independent `rvt_validate.py` on the loaded 2025 file: error 0 / warning 0). `--rfa '{"kind":"device","device":"toaster"}'` → rc 4, the one clear line. `explain --inputs rfa --output rfa` lists `famspec-device.json`; `matrix` audit clean. **Bare plugin surface** (`tekton-plugin.zip` unzipped, `env -i`, system python3 3.11, no repo on `sys.path`): schema found at `skills/tekton-native/examples/famspec.schema.json`; device `rfa` OK 0.66 s, device `rvt` (junction-box, va 0) OK "project validates 0 errors" 1.54 s, `"device":"outlet"` → INVALID-FAMSPEC line.

### Findings

1. **The #162 design held**: adding a catalog kind is schema + one tuple entry + one rename-table entry; the router needed no dispatch change. The only code smell was three hand-typed "'panelboard' | 'transformer' | 'luminaire' | 'downlight'" strings (router clear line, matrix caveats, CLI help) — the router's is now derived from `FS.KINDS`; the matrix/CLI ones stay literal (they are prose pinned by review, and `matrix.py` must not import-cycle through famspec's kinds for wording).
2. **Companion bug confirmed live on `main` (not fixed here — outside "famspec dispatch only")**: `route.py run --output rfa --prompt "… 3 duplex receptacles"` → `R-1: NOT built -- None` ×3. `router._families_from_model` (router.py ~960) reads `f['status']` / `f['refusal']`; `tools/ifc_intent.stage_families` writes `reason`. Two-line fix (`f.get('reason') or f.get('status')`), but `tools/ifc_intent.py` is held by eng #359 and the router function is the prompt→rfa lane, so it is filed as a follow-up task (below) rather than folded in.
3. The prompt lane does not build device families on `main` (same probe: 1 panel `.rfa`, three device plans NOT built) — which is why the shared `_CATALOG` caveat was not widened; #359 owns that lane.

### Follow-ups / patches for files outside this territory

- **`tools/sync_plugin.py` mirror map (one word)** — the worked device example is not mirrored into the bundle (the schema is, so the kind WORKS from a bare plugin; only the example file is missing beside `famspec-{panelboard,transformer,luminaire}.json`). Wanted patch, for whoever next holds `tools/sync_plugin.py` (or this branch if the tech lead widens the territory):
  ```diff
  -    for k in ("panelboard", "transformer", "luminaire"):       # the worked famspecs
  +    for k in ("panelboard", "transformer", "luminaire", "device"):   # the worked famspecs
  ```
- **`docs/product/PERMUTATION-MATRIX.md`** (held by eng #359 / PR #400 this wave) — three prose spots should list the fifth kind once #400 lands: line ~13 inputs bullet `{"kind": panelboard | transformer | luminaire | device | downlight, …}`; the `rfa → rfa` row: dispatch list `make_panelboard` / `make_transformer` / `make_luminaire` / **`make_device`** / `famfrom_ifc.make_downlight`, worked examples `spec/examples/famspec-{panelboard,transformer,luminaire,device}.json`; the `rfa + rvt → rvt` row: "famspec (any of the **five** kinds)". `test_permutation_matrix_doc_agrees_with_machine_matrix` compares cell statuses only, so it stays green either way.
- **SKILL.md line (hot file, not touched)** — wanted in `plugin/skills/tekton-native/SKILL.md` (or tekton-author) where structured inputs are listed: "a famspec JSON (`examples/famspec.schema.json`: kind = panelboard | transformer | luminaire | device | downlight) generates OUR `.rfa`; `device` = duplex receptacle / 20 A receptacle / switch / junction box (Electrical Fixtures), validator-green, PROOF-ONLY".
- Follow-up task filed: the `reason` vs `status`/`refusal` key mismatch (finding 2), `Refs #361`.

### BRANCH STATE

- Branch `cam/361-famspec-device` from `main` @ b169376; one PR, `Closes #361`.
- Files written: `spec/famspec.schema.json`, `spec/examples/famspec-device.json` (new), `src/rvt/frontdoor/famspec.py`, `src/rvt/frontdoor/router.py` (wording), `src/rvt/frontdoor/matrix.py` (caveats + 1 evidence pointer), `tools/route.py` (help), `tests/test_router.py`, `plugin/skills/tekton-author/references/CATALOG-FACTS.md`, `docs/inbox/famspec-contract.md` (this section); regenerated mirrors `plugin/lib/src/rvt/frontdoor/{famspec,router,matrix}.py`, `plugin/skills/tekton-native/examples/famspec.schema.json`. No hot file, no NO-GO file, no `TRACKER.md`; `rvt.famgen.factory` read-only.
- Gates: above, green on this head. Nothing STAGED for the viewer (not in the DONE; the device lane is validator-gated + PROOF-ONLY like the other famspec kinds). Shipped = contract + example + tests + reference prose.
