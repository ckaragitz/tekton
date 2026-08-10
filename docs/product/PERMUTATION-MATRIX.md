# The Permutation Matrix — what tekton can route today

**The mandate** (user, verbatim intent): *“we should be able to create rvt
and rfa files from a prompt alone OR take an ifc file and turn into rvt OR
take a prompt and turn into ifc and then turn into rvt OR … think of any
permutation. the goal is to be able to handle any and all situations.”*

The design answer is a **routing matrix over composable stages**, not
per-route code:

- **Inputs** — any subset of `{prompt, ifc, rvt, rfa, spec}`
  (`spec` = the building/room spec JSON, `spec/building.schema.json`
  dialect; `rfa` = a **famspec** JSON `{"kind": panelboard | transformer |
  luminaire | device | downlight, …}` — the written contract is
  `spec/famspec.schema.json` (JSON Schema draft-07, our own text; worked
  examples `spec/examples/famspec-*.json`) — *or* a `.rfa` path; see the
  rfa rows for the honest input contract).
- **Outputs** — one of `{rvt, rfa, ifc}`.
- **Machine truth**: `src/rvt/frontdoor/matrix.py` (`CELLS`/`STAGES`/`CHAINS`).
  `tools/route.py matrix` (and `tools/frontdoor.py matrix`) print the live
  table **and self-audit every evidence citation** (test/worked/record paths
  exist; every `certified:` ref is really in
  `docs/coverage/viewer-certified.json`). `tests/test_router.py` fails the
  suite if any claim goes stale **or if this document disagrees with the
  machine matrix**. On a fresh clone the certified probe *binaries*
  (git-ignored `experiments/**/*.rvt`) are absent — the audit says so as a
  note; the ledger, not the disk, certifies them.
- **Router**: `rvt.frontdoor.router.route(inputs, output, **opts)`,
  CLI `tools/route.py run`. It composes the *existing* stages — the front
  door’s build/edit pipelines and the `rvt.convert` routes — and adds no
  authoring logic of its own. Anything not in the table comes back as
  **one clear line** (the matrix row + the closest supported route), never
  a traceback.
- **Deliverable rule**: gates are labels. Every route **delivers** its
  output file plus *every* intermediate (intent JSON, IFC, families,
  underlying manifests) plus a route manifest (`route.json` / `ROUTE.md`)
  with stamps, caveats and the evidence cited — caveats ride **after**
  delivery, never instead of it.

Status vocabulary — honest per cell:

- **works** — runnable end-to-end today; runnable evidence cited (tests +
  worked manifests; `certified:` where the ledger has it). *Works* is a
  statement about the route, not viewer acceptance of every output: the
  caveats column says exactly what Autodesk’s reader has and has not seen.
- **partial** — the mechanism runs with a *named* caveat/scope gap.
- **missing** — not implemented; the router answers with the clear line.

Live census: **21 cells — 18 works / 1 partial / 2 missing.**

## Single inputs (all 15 cells enumerated)

| in → out | status | route (stages) | evidence (cited by the machine matrix) | honest caveats |
|---|---|---|---|---|
| prompt → rvt | **works** | `prompt_to_rvt` (prompt→intent, handoff, intent→rvt on the certified genesis base) | worked `experiments/frontdoor/prompt-electrical-room/`; `tests/test_frontdoor.py`; certified walls-only + `stage_L8_lp4` shapes | **placed instances** of our generated families on our composed base = THE OPEN CELL (genesis-audit #48, issue #16; walls, loaded families and walls + loaded families are certified — WF_fix/WF_nofix): a job that places instances is delivered **stamped** `PROOF-ONLY: generated-family INSTANCES on a composed genesis base (open cell, docs/inbox/genesis-audit.md #48, issue #16)`; `--strict` splits into shell (walls + loaded families, certified shape) + equipment (the placed instances), both delivered; feeder circuits are **authored** natively (one constructed `RbsElectricalSystem` per non-service feeder edge, wired in the equipment commit and read back; validator CIRCUITS rule 0 errors on 2026/2025/2024 — PROOF-ONLY, no viewer verdict for the circuit layer yet, issue #146; a shortfall is named with the plan, never faked); prompted **receptacles / outlets** (Electrical Fixtures, issues #166 / #359) are parsed, laid out at the ADA/NEC height from `facts/generic/devices-and-mounting.json`, generated as ONE shared `make_device` family per distinct (kind, V, VA, height), **loaded** in the same host pass as the equipment with the family’s own category (−2001060 on surrogates / symbol / tracking row) and **placed** one `FamilyInstance` per device (header category Electrical Fixtures, upright work-plane frame on the wall’s interior face at the AFF height, `m_assocLevelId` = the room’s datum, free-standing like the boards — face-hosting is the fidelity follow-up); manifest kind `fixture-instance` + a device-schedule row each; validator 0 errors on 2026 / 2025 / 2024, each output being that release (`tests/test_place_fixtures.py` pins all three, sample-free); placed instances = the open cell → the same STAMP as the boards; a device family that cannot be authored loads last and costs devices only, never the equipment; PROOF-ONLY until G2/G3 |
| prompt → ifc | **works** | `prompt_to_ifc` (prompt→intent, intent→ifc) | `tests/test_target2025.py` round-trips the emitter against our own resolver; `tests/test_frontdoor.py` (prompted receptacles → `IfcOutlet` → re-entry) | IFC is version-agnostic; re-enters via `--ifc`; prompted wiring devices ride as honest `IfcOutlet` (`POWEROUTLET`) products with their own `DeviceSchedule` pset (Voltage / Load / MountingHeight, issue #166) and read back as `receptacle_device` with the same resolved `make_device` plan (so `--ifc` re-entry loads + places them like the prompt route, #359) — never as extra distribution boards |
| prompt → rfa | **works** | `prompt_to_rfa` (prompt→intent, intent→rfa) | worked families dir; `tests/test_famgen_factory.py`; `tests/test_router_release.py` (per release) | catalog-backed kinds only (panelboard / transformer / luminaire / honest house switchboard); anything without facts is refused by name; prompted receptacles emit ONE shared device `.rfa` (`make_device`, `generic/devices-and-mounting` facts, issues #166 / #359; `tools/make_family.py device --kind duplex-receptacle|switch|junction-box` is the direct repo verb for the other device kinds until the famspec kind `device` lands — issue #361). **Per release** (`--target-version`, all three `→ rfa` cells): 2026 / 2025 / 2024 → the `.rfa` ARE that release (its pinned schema, emitted in the release build context of that year’s certified base; family-mode validator 0 errors); an uncertified (2023) or unknown (2027+) year is never refused and never silent — delivered at Revit 2026 with THE one line (“your Revit N cannot open it”) + a version-agnostic IFC beside; no flag → Revit 2026 and the route JSON says to ask the year. Validator-gated, not viewer-certified per release |
| ifc → rvt | **works** | `ifc_to_rvt` (ifc→intent, intent→rvt) | **certified** `V25_room_from_ifc.rvt`, `V26_room_from_ifc_with_walls.rvt`; worked `ifc-electrical-room-2500a/` | same open-cell/circuits/PROOF-ONLY caveats; a *product* IFC auto-falls back to the family chain (below) |
| ifc → ifc | **works** | `ifc_normalize` (ifc→intent, intent→ifc) | `tests/test_target2025.py`, `tests/test_ifc_intent.py` | normalisation into our tagging-contract dialect; content outside the resolved intent does not survive |
| ifc → rfa | **works** | `ifc_to_rfa` (room: intent→rfa; product: ifc→facts→rfa) | **certified** `L_downlight_loaded.rvt`; `tests/test_ifc_family.py` | room IFCs → catalog families for tagged equipment; product IFCs → the measured **downlight archetype** (the one facts→rfa archetype wired). Per release as the prompt → rfa row (room IFCs: 2026/2025/2024 native, older/unknown → 2026 + the line + the input IFC copied beside); the product-IFC downlight archetype cannot be emitted at 2024 (its arc geometry class `ArcElemCell` is absent from the 2024 schema) → the 2024 context is tried, the reason lands in the line and the family is delivered at 2026, never a failure; 2025 runs in the 2025 context (the product lane itself still needs the family container archetype on disk — owner machine — as the rfa → rvt row says) |
| rvt → rvt | *missing* | — | — | an .rvt alone is a no-op copy; an edit needs instructions → use **prompt+rvt** |
| rvt → ifc | **works** | `rvt_to_ifc` (rvt-read, rvt→intent readback, intent→ifc — `rvt.convert.rvt_to_ifc`) | `tests/test_convert.py`; `tests/test_router.py` (builds a room, exports it, everything survives); worked `experiments/convert/rvt-to-ifc/electrical_room_prompt.ifc` + manifest; record `docs/inbox/convert-a.md` | **the round trip is the acceptance**: the IFC re-resolves through our own resolver and the manifest carries the survival table (acceptance output: equipment 7/7 → 4/4 incl. transformer, walls 4/4; quarantined MEP sample: equipment 29/29, feeder edges 28/28, walls 131/133 honest partial). Scope: levels, straight walls, electrical equipment + tagging-contract values, equipment-to-equipment feeders; the rest is *counted* as not-extracted. A foreign source is delivered with the FOREIGN DESIGN CONTENT (+ QUARANTINED) stamps |
| rvt → rfa | **works** | `extract_family` (rvt-read, rvt→rfa — `rvt.convert.extract_family`, `--family` selector) | `tests/test_convert.py`; `tests/test_router.py` (extract → reload full cycle); worked `experiments/convert/extract-family/DP1_reextracted.*`; **certified** `TB0g.rvt` (extract→place, base level); record `convert-a.md` | our loaded-project outputs extract **clean** (family-mode validator 0 errors) and complete the full cycle generate→load→extract→re-load; a Revit-authored *project-hosted* family is delivered + labelled partial (dangling host-side style/category refs — repatriation is a follow-up); nested family documents refused by name; foreign source → FOREIGN/QUARANTINED stamps. TB0g certifies extract→place *at base level* (embedded-born famdoc + instance on our composed base PASSES); the product lane’s own artifact is validator/census-gated |
| rfa → rvt | **works** | `rfa_load` (famspec: `famspec→rfa` + four-registry `rfa-load`; `.rfa` path: `rfa-classify` → extracted `rfa-reload` \| standalone-born `rfa-born-load`) | **certified** `L1a_rstbasic_loaded_levelhead.rvt`, `L_downlight_loaded.rvt`, `stage_L8_lp4.rvt`, **`T2a.rvt`** (a Revit-born standalone .rfa famloaded onto our composed base + instance), **`TB0g.rvt`**; worked `experiments/rftprobe/probes.json`, `DP1_reextracted.reloaded.rvt.load.json`, `spec/famspec.schema.json`; `tests/test_famload.py`, `tests/test_convert.py`, `tests/test_router.py` (every catalog famspec kind loaded onto the pinned base, fresh clone); records `rfa-load-product.md`, `famspec-contract.md` | **input contract**: (a) famspec JSON `{"kind": panelboard \| transformer \| luminaire \| device \| downlight, <the constructor’s kwargs>}` per **`spec/famspec.schema.json`** (issue #162; `device` = the Electrical Fixtures wiring-device family, issue #361) — generated by its constructor (the `.rfa` rides along), rebuilt above the host watermark and loaded via `rvt.famload`: all five kinds, project validator 0 errors, census coherent (measured on a fresh clone for the four catalog kinds panelboard / transformer / luminaire / device, ~2 s each); a famspec that fails the schema (unknown kind, misspelt field, wrong type) or whose facts the catalog lacks is **one clear line naming the field**, never a traceback or an invented dimension; (b) a `.rfa` tekton **extracted** from a loaded project — reloaded as-is via `rvt.famgen.loader` when its ids sit above the host’s id watermark (the pinned base always qualifies); (c) a **standalone-born** `.rfa` (our own `start_id=1000` deliverables, any Revit-saved 2024–2026 family whose ElemTable our codec parses, an extracted `.rfa` going back into a host that has grown past its ids) **loads** via `rvt.convert.rfa_load` — schema-typed decode-time id remap above the watermark + four-registry `rvt.famload` (validator 0 errors, census coherent; `tests/test_rfa_load.py`, in the CI shard). The *mechanism* is certified (T2a); this lane’s own artifacts are `needs-viewer` — delivered + labelled, never “loads in Revit”. Refused by name: GraveyardRec ElemTable footer (#13), nested family documents, seq-103 classes beyond GElement/SerializedDummy. Default host = the pinned certified genesis base (bundled); pass `--rvt` for your project. **Per release** (`--target-version`, or `target_version` in the famspec; issue #242, `tests/test_router_load_release.py` in the CI shard): with no `--rvt` the host is *that year’s* pinned certified base and the family is emitted **and** loaded under its release — 2026 / 2025 / 2024: the `.rfa` and the loaded project both ARE that release, project validator 0 errors under it, four-registry census coherent (every catalog famspec kind + the standalone-born `.rfa` lane, fresh clone, ~2 s each); an uncertified (2023) or unknown (2027+) year is never refused and never silent — loaded onto the default Revit 2026 base with THE one line (“your Revit N cannot open it”; a family request honestly says no IFC can ride beside it); a family that cannot be emitted at a certified year degrades *once* (block, `.rfa` and host all name the default release); no flag → today’s default base and the route JSON says to ask the year. With `--rvt` see the rfa + rvt row (the host keeps ITS release, stated). Validated per release, **not viewer-certified** (the load certifications are 2026-era files). The **downlight** famspec kind (measured product archetype) still needs the family container archetype on disk (owner machine) until `famfrom_ifc` emits on the bundled base; the four catalog kinds (panelboard / transformer / luminaire / device) run anywhere. PROOF-ONLY stamped |
| rfa → ifc | *missing* | — | — | no family→IFC emitter; author the product IFC from facts, or load the family and export the project (rfa→rvt then rvt→ifc) |
| rfa → rfa | **works** | `rfa_generate` (`famspec→rfa`: `rvt.frontdoor.famspec` validates + dispatches to `rvt.famgen.factory.make_panelboard` / `make_transformer` / `make_luminaire` / `make_device` / `famfrom_ifc.make_downlight`, then `FamilyProduct.write`) | `tests/test_router.py` (schema + examples validate stdlib-only; every catalog kind end to end on a fresh clone: family-mode VALID 0 errors, provenance ok, `rvt_validate --family` 0 errors); `tests/test_famgen_factory.py`; worked `spec/famspec.schema.json`, `spec/examples/famspec-{panelboard,transformer,luminaire,device}.json`; record `docs/inbox/famspec-contract.md` | **the structured family request** (issue #162; `device` = duplex receptacle / 20 A receptacle / switch / junction box, an Electrical Fixtures family, issue #361): a famspec JSON per `spec/famspec.schema.json` — JSON Schema draft-07, our own text: `kind` selects the constructor, every other field mirrors that constructor’s keyword arguments (`tests/test_router.py` pins schema fields == `make_<kind>` signature), optional `target_version` / `shared_params` (`"default"` = OUR shared-parameter file); validated **stdlib-only** (`rvt.frontdoor.famspec.check_schema`, no jsonschema dependency) so a misspelt field or wrong type is one clear line naming it. Output = OUR standalone `.rfa` + its report (family-mode validator, provenance ledger, assumed/user-given fact fields surfaced) + the route manifest — measured on a fresh clone (with the shared family view constellation): panelboard 87 / transformer 75 / luminaire 81 / device 73 elements (category −2001060 read back from the written file), VALID 0 errors, provenance ok, 0.4 s. Catalog scope as prompt → rfa (facts the catalog lacks are **refused by name**); an existing `.rfa` path alone is a no-op → the clear line (edit: prompt+rfa → rfa; load: rfa → rvt). **Per release** as prompt → rfa (`target_version` in the famspec or `--target-version`, the flag wins: 2026/2025/2024 emit AS that year; an uncertified/unknown year → the default release + THE line, which for a family request honestly says no IFC can ride beside it). The downlight kind is owner-machine-only as in the rfa → rvt row. **Viewer**: no standalone `.rfa` of ours is in the certified ledger — the same constructors’ families are certified *loaded* (stage_L8_lp4, L1a); every famspec `.rfa` is stamped PROOF-ONLY and delivered |
| spec → rvt | **works** | `spec_to_rvt` (**chain** spec→ifc→intent→rvt on the genesis base) | **certified** `V23_electrical_room.rvt` (legacy direct); worked `usecases/chicago-plenum…/generated.ifc`; `tests/test_job.py` | the legacy direct build (`tools/rvt_job.py create --spec`, template project) remains as **spec+rvt**; open-cell/PROOF-ONLY caveats ride |
| spec → ifc | **works** | `spec_to_ifc` (deterministic generator) | worked `usecases/…/generated.ifc`; `skills/tekton-ifc/tests` | identical spec → byte-identical IFC |
| spec → rfa | **works** | `spec_to_rfa` (chain spec→ifc→intent→rfa) | worked families dir; `tests/test_famgen_factory.py` | the spec’s *tagged* equipment maps to catalog family plans; catalog scope and per-release behaviour (`--target-version`) exactly as the prompt → rfa row (the spec’s generated IFC is the version-agnostic addition on a fallback) |

## Combinations

| in → out | status | route | evidence | honest caveats |
|---|---|---|---|---|
| prompt + rvt → rvt | **works** | `rvt_edit`: an **edit-shaped** prompt runs the certified edit pipeline (modify / move / retype / delete / cascade, NL or ops.json); an **authoring-shaped** prompt (“add a 100 A lighting panel and a 75 kVA transformer to my project”) runs `rvt.convert.add_to_project` INTO your file | **certified** `M3_modify`, `M4_move_retype`, `M2_delete_cascade`, `M2_delete_cascade_rac` (foreign file); worked `rvt-edit-room/`, `experiments/convert_combo/A1_add_own/` (VALID 0 errors), `A2_add_rme_devonly/` (32.6 MB quarantined MEP sample, VALID 0 errors, census coherent 308 units); `tests/test_convert_combo.py`, `tests/test_router.py`; per-release `tests/test_edit_own_release.py` | edit vs add is decided on the prompt’s *shape* (an edit clause whose name does not resolve stays an edit and is reported, never re-read as an addition). Add branch: new equipment generated zero-donor, four-registry loaded, placed in free floor space beside your content (`--at X Y`, `--level`); the target’s **release preserved** by construction, its schema installed, unsupported releases refused with `creation_status`’s reason. **Per release (edit branch):** the edit runs under the *input file's own* release and the output keeps it — Revit 2026 / 2025 / 2024 projects open, edit, re-emit and validate 0 errors through the front door, `tools/rvt_edit.py` and `tools/rvt_job.py edit` (issue #70); the edit certifications cited are 2026-era files, so 2025/2024 edit outputs are *validated, not yet viewer-certified*; a release we cannot author into (2023 and older) is named and refused by the authoring context, never guessed. **Input era (rvt-read, every `frontdoor author --rvt` job, issue #176):** the input's `BasicFileInfo` era + year are classified *before* anything opens it and ride in the manifest's `input_release` block (the `go edit` / `tools/rvt_edit.py` / `rvt_job.py edit` entries do not carry this gate yet — follow-up) — a known release (2023–2026) proceeds exactly as before; a 2019+-layout file of a year tekton has never read (2019–2022, or newer than the roster) whose own `Formats/Latest` parses is read under that schema and **delivered stamped** `UNVERIFIED-RELEASE: no file of this release has been read by tekton before; validate before trusting`; a pre-2019 layout (`Revit Build:` era, Revit 2008–2018), an undetectable year/schema, or a non-Revit file is **refused up front with one line** (era/year found, the verified floor *read 2023+ / edit 2024+*, and the two remedies: re-save in Revit 2023+ or hand over the IFC) — exit 2, no traceback, nothing withheld because nothing can be built (`tests/test_input_release.py`). **Viewer**: the edit branch is certified; **no add-into artifact has been through Autodesk’s reader** and our generated famdocs under a placed instance are the OPEN CELL — expect the audit to reject the added equipment until it closes (validator/census/release gates run; PROOF-ONLY). Known edit blocker: rename/set-mark on *our created* instances (no param rows yet) |
| ifc + rvt → rvt | **works** | `ifc_merge_into_rvt` — `rvt.convert.merge_ifc`: the IFC’s resolved intent appended INTO your .rvt at a deterministic **disjoint offset** (`--offset DX DY`; `0 0` = the IFC’s own frame) | worked `experiments/convert_combo/B1_merge_ifc_into_own/` (28 created ids, VALID 0 errors), `B2_merge_rst_devonly/` (rst sample, VALID 0 errors; two independent runs converge on identical created ids); `tests/test_convert_combo.py`, `tests/test_router.py` | same INTO-gates as above (validator 0 errors to claim, four-registry census, release preserved, unsupported releases refused by name); an **instance** of our generated family placed into the target ⇒ the open-cell stamp rides exactly as on the front door (`--strict` gives the two-file degrade; walls + loaded families alone do not stamp); **viewer-unverified as a merged artifact**; foreign targets stamped FOREIGN/QUARANTINED; PROOF-ONLY |
| prompt + rfa → rfa | **works** | `rfa_modify` — `rvt.convert.modify_family` (text \| inline JSON \| ops.json; `rvt.convert.edit_family` = the structured-ops surface over the same engine) | worked `experiments/convert_combo/C1_modify_own/`, `C2_rename_family/`, `experiments/convert/edit-family/` (family-mode VALID 0 errors, re-read proven, PartAtom in step); `tests/test_convert_combo.py`, `tests/test_convert.py`, `tests/test_router.py` | one vocabulary: `rename-type \| rename-family \| set-param` (type-scopable); the value carrier follows the parameter's storage class first (`ParamDefString` = text, `ParamDefInt` = integer), the spec of a `ParamDefValue` second, which also drives unit conversion (amps, volts, kVA; **lengths need an explicit unit**); a famspec is not editable (generate first: prompt→rfa). **Partial on foreign Revit-authored .rfa**: read/parse yes, commit blocked by the ElemTable GraveyardRec codec gap (refused by name). Dimension edits change the value only (no constraint graph — regenerate for true geometry). The edited .rfa is validator-gated, not viewer-certified; PROOF-ONLY |
| rfa + rvt → rvt | **works** | `rfa_load` (load into **your** project: famspec (any of the five kinds) and standalone-born `.rfa` via `rvt.famload`; extracted `.rfa` via `rvt.famgen.loader`) | **certified** L1a / L_downlight (rst host), `stage_L8_lp4` (genesis lineage), **T2a** (Revit-born .rfa on the composed base + instance), **TB0g** (embedded-born famdoc on the composed base + instance); worked `DP1_reextracted.reloaded.rvt.load.json`; `tests/test_famload.py`, `tests/test_convert.py`, `tests/test_router.py`, `tests/test_router_load_release.py` | input contract exactly as the rfa→rvt row (famspec per `spec/famspec.schema.json` \| tekton-extracted .rfa \| standalone-born .rfa via the id-remap lane); no instance is placed by this cell (place with prompt+rvt “add …”); on *your* host the same mechanisms + gates run — the viewer evidence is on the rst sample host and our genesis/composed bases; a host of another release loads only where that release’s creation support is certified. **Release** (issue #242): the load runs under **your host’s own** release and the output keeps it (a load cannot transmute a 2025 project into a 2024 one) — the host’s year is auto-detected and stated every time in `route.json.target_version` exactly as the edit route does (`detected` with no flag, `match` / `match-older`, or `fallback` + THE one line “your Revit N cannot open the loaded output … supply a Revit N input file” when a stated `--target-version` is older than the host — never silently ignored); the `.rfa` generated beside it IS the flag’s year and carries its own block under `target_version.rfa`; validator 0 errors on a Revit-2025 host with the flag at 2024 / 2025 / 2026 (`tests/test_router_load_release.py`, fresh clone); PROOF-ONLY |
| prompt + ifc → rvt | *partial* | `ifc_build_then_edit` (build the IFC, then apply the prompt as an edit) | composition of two proven stages | a non-edit prompt cannot merge into the IFC’s intent yet (intent-level merge unbuilt) — the route fails with the edit grammar rather than guessing |
| spec + rvt → rvt | **works** | `spec_on_rvt_seed` (`tools/rvt_job.py create --spec --base`) | **certified** `V23_electrical_room.rvt`; `tests/test_job.py` | your .rvt is the seed/template: seed audit + hard gates; output ledgered against that seed (PROOF-ONLY vs what you supply) |

**Anything else** (e.g. `prompt+spec → rvt`, `rfa → ifc`, any output for an
unlisted combination): the router returns the matrix row and the closest
supported route in one line, exit code 4 — never a traceback.

## Chains (selectable with `--via`, or implicit)

| chain | status | how | evidence |
|---|---|---|---|
| prompt → ifc → rvt | **works** | `route --output rvt --prompt … --via ifc` — the handoff round trip run in-process (intent → our IFC → re-resolved → build) | `tests/test_target2025.py` + demo `experiments/routes/demo3-prompt-via-ifc-rvt/` |
| spec → ifc → rvt | **works** | the canonical `spec → rvt` route | see spec→rvt row |
| ifc → rfa → loaded-rvt | **works** | `--via family` on ifc→rvt, and the automatic product-IFC fallback; **per release** exactly as rfa → rvt (issue #242): the product `.rfa` is emitted in the `--target-version` year’s release context and the default host is that year’s certified base — one resolver, one stated block; the measured downlight archetype itself still needs the family container archetype on disk (owner machine, #94), so on a fresh clone the chain stops at the emit *after* the year was resolved and stated (`tests/test_router_load_release.py` pins that; the end-to-end case self-skips there) | **certified** `L_downlight_loaded.rvt` (2026); per-release outputs validator-gated only |
| prompt → rfa → loaded-rvt | **works** | the F/L stages *inside* prompt→rvt (families generated, loaded, placed) | **certified** `stage_L8_lp4.rvt` |
| rvt → rfa → loaded-rvt | **works** | **extract → place into our projects** in two hops: `route --output rfa --rvt A.rvt --family X`, then `route --output rvt --rfa X.rfa [--rvt B.rvt]` (default host: the pinned base) | **certified** `TB0g.rvt` (base level); worked `DP1_reextracted.reloaded.rvt.load.json`; `tests/test_convert.py`, `tests/test_router.py` |

## Demonstrated end-to-end

`experiments/routes/` (2026-08-04, `route.json` + `ROUTE.md` each):

1. `demo1-prompt-to-rfa` — prompt → **2 .rfa** (validator VALID, provenance ok), 3 s.
2. `demo2-spec-to-ifc` — room-spec → IFC4 (657 entities, deterministic), 0.3 s.
3. `demo3-prompt-via-ifc-rvt` — **the chain** prompt → IFC → .rvt on the
   genesis base (open-cell stamp riding the combined file: instances placed), 23 s.
4. `demo4-rfa-loaded-rvt` — **the combination** famspec → .rfa → four-registry
   **loaded** .rvt (project validates 0 errors), 35 s.
5. `demo5-prompt-rvt-edit` — prompt+rvt edit (move + cascade delete), hard
   gates PASSED, 1.8 s.

The `rvt.convert` cells (2026-08-09, issue #5) are re-run **from a fresh
clone** by `tests/test_router.py` on every invocation (RVT_SKIP_LARGE=1
skips the ~1 min of builds): a small room is built from a prompt on the
pinned base, then exported to IFC (everything survives the round trip), a
family is extracted and reloaded onto the base (project validator 0 errors),
a transformer is **added into** the room and a second room’s IFC is
**merged into** it (both VALID 0 errors, release preserved), and a generated
family is edited (VALID, re-read proven). The recorded numbers are in
`docs/inbox/matrix-flips.md`; the worked proofs of the convert streams live
under `experiments/convert/` and `experiments/convert_combo/`.

## The named gaps (what would flip or deepen cells)

- **Certify the product any-.rfa load lane’s own artifacts** — input form (c) of
  the rfa cells (standalone-born `.rfa`, including our own `.rfa` deliverables)
  is product-wired in `rvt.convert.rfa_load` (issue #99: schema-typed id remap +
  `rvt.famload`; validator 0 errors on the 2026/2025/2024 bases). The *mechanism*
  is certified (T2a: a Revit-born 1,992-element `.rfa` on the composed base with
  an instance); a viewer batch of this lane’s outputs (certified base +
  byte-identical control) is the `needs-viewer` step that removes the caveat.
- **The open cell** (our generated famdocs + placed instances on our composed
  bases fail Autodesk’s audit) — closing it removes the viewer caveat from
  every add-into / merge-into / prompt→rvt output; the desktop-Revit dialog
  is the next instrument (`docs/inbox/genesis-audit.md`).
- **A viewer round for the INTO artifacts** — A1/B1 (our targets) staged behind
  a certified control would move the add/merge cells from gate-checked to
  ledgered (or name the failure).
- **downlight famspec kind on the bundled base** — `rvt.ifc.famfrom_ifc` should
  emit its `.rfa` on the plugin-bundled container instead of the research-corpus
  archetype, so the measured-product downlight famspec runs on a fresh clone
  like the four catalog kinds already do (rfa → rfa / rfa → rvt, issues #162 / #361).
- **GraveyardRec codec** (`rvt.stream_encoders`) — unlocks edits of foreign
  Revit-authored `.rfa` files (prompt+rfa partial → works on foreign files).
- **Host-resource repatriation + nested units** — flips foreign project-hosted
  family extraction from partial to clean.
- **RVT→intent depth** — non-electrical categories, curved/curtain walls,
  circuits to non-equipment loads in `rvt_to_ifc`; and prompt+ifc
  intent-level merge (the one remaining *partial* cell).
- **A viewer/desktop round for a famspec `.rfa` and its loaded project** — the
  standalone catalog-kind famspecs are wired (issue #162, `spec/famspec.schema.json`);
  a STAGED batch (certified base + byte-identical control) of one loaded famspec
  family, plus a desktop family-editor open of the bare `.rfa`, would move the
  rfa → rfa / famspec lane from validator-gated to ledgered.
- **Open bug r2** (walls+families in one file) — **exonerated** (WF_fix /
  WF_nofix PASS, genesis-audit #27); the stamp now keys on the open cell above
  (placed instances), so a walls + loaded-families build without placement
  carries no open-cell stamp. **Instance param rows** — rename/set-mark on our own
  instances. **G2/G3 gates** — flip PROOF-ONLY to DELIVERABLE everywhere.
