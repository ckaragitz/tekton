# convert-a — the missing EXPORT/EXTRACT converters (RVT→IFC, RVT→RFA, RFA→RFA)

Stream: convert-a. Date: 2026-08-04. Territory: `src/rvt/convert/**` (shared
with convert-B — see §6), `tests/test_convert.py`, `experiments/convert/**`,
this record.

## 1. What was built (three converters, all NEW modules, composing certified stages)

| # | Route | Module | CLI | Status |
|---|-------|--------|-----|--------|
| 1 | RVT → IFC4 | `src/rvt/convert/rvt_to_ifc.py` | `python -m rvt.convert.rvt_to_ifc <in.rvt> [-o out.ifc] [--out-dir D] [--no-roundtrip] [--max-walls N]` | **works** (round-trip proven) |
| 2 | RVT → RFA | `src/rvt/convert/extract_family.py` (+ shared assembler `src/rvt/convert/rfa_assemble.py`) | `python -m rvt.convert.extract_family <in.rvt> --list \| --family SEL [-o out.rfa] [--reload-base fresh.rvt]` | **works** on our loaded-project outputs (validator 0 errors + full cycle); **partial** on foreign project-hosted families (§4.2) |
| 3 | RFA (+ops) → RFA | `src/rvt/convert/edit_family.py` | `python -m rvt.convert.edit_family <f.rfa> -o D --set "BusRating=225" --rename-type "NEW" [--rename-family N] [--ops ops.json] [--inventory]` | **works** (validator 0 errors, re-read proven) |

Run from repo root with `PYTHONPATH=src .venv/bin/python` (the editable
install's `.pth` still points at the pre-rename path `/Users/ck/dev/things/
rev-revit/src`, so bare `python -m rvt...` fails without PYTHONPATH — worth
a `uv pip install -e .` refresh, orchestrator's call).

Composition, not re-implementation (nothing certified was edited):

* **RVT→IFC**: `rvt.mutate.Document.from_file` + `rvt.inventory` +
  `rvt.families.FamilyIndex` read the project back; the model duck-types the
  resolver's own `WallRun`/`FeederEdge` dataclasses; emission is
  `rvt.frontdoor.ifc_out.write_intent_ifc` verbatim.
* **RVT→RFA**: unit records carried VERBATIM (`rvt.families.unit_segments`);
  scaffolding re-authored by the production writers — partition framing
  `famgen.skeleton.build_partition_stream` + `famdoc_adoc.build_footer` +
  `FAMILY_END_RECORD`; the six coordinated Globals via
  `genesis.skeleton.minimal_globals` over a records-shaped element shim;
  standalone ADocument via `famdoc_adoc.author_family_adocument`
  (mode=candidate, archetype = the bundled certified genesis base — the same
  zero-donor path `standalone_family_write` uses); identity via
  `rvt.identity`; PartAtom via `famgen.skeleton.build_part_atom`;
  `Formats/Latest` carried from the SOURCE file itself.
* **Full cycle**: `RfaFamilyDoc` adapter (SkelElements rebuilt from the .rfa's
  decoded records, GElement reps kept, owners from its own ElemTable) feeds
  `rvt.famgen.loader.load_family_into_project` unchanged.
* **RFA→RFA**: structured-ops layer over convert-B's
  `rvt.convert.modify_family` engine (inventory → one
  `rvt.manipulate.commit_plans` commit of the self-Family record → PartAtom
  follow → gates). See §6 for the deliberate vocabulary boundary.

Every route follows the DELIVERABLE RULE: output file always written +
`<stem>.manifest.json` + `<stem>.MANIFEST.md` beside it; gates are labels;
provenance stamps up front, caveats after.

## 2. Runnable proofs (all outputs under `experiments/convert/`)

### 2.1 RVT→IFC round trip on OUR OWN acceptance output — FULL SURVIVAL

`experiments/frontdoor/prompt-electrical-room/electrical_room_prompt.rvt`
(zero-donor, acceptance lineage) → `experiments/convert/rvt-to-ifc/
electrical_room_prompt.ifc` → back through `rvt.ifc.intent.resolve_intent`.

NOTE — the acceptance output is a SHARED, REGENERABLE artifact: a sibling
stream rebuilt it mid-session (2026-08-05 00:31, new room = MSB + DP-1 +
LP-1 + a dry-type transformer T1). The converter proved FULL survival on
BOTH builds:

* first build (7 boards, the 655,360-byte 2026-08-04 12:49 file): **7/7
  equipment** {MSB, DP-1, DP-2, LP-1..LP-4}, kinds exact, **pos-delta
  [0.0, 0.0, 0.0]**, walls 4/4, all_survived=true (witnessed in-session;
  that run's manifest was superseded on disk by the refresh below);
* current build (4 items incl. the TRANSFORMER): **4/4 equipment**
  {MSB→switchboard, DP-1→distribution_panelboard, LP-1→lighting_panelboard,
  **T1→transformer** (IfcTransformer cell proven on our own content)},
  pos-delta [0.0, 0.0, 0.0], walls **4/4**, `all_survived: true` — the
  manifest now on disk;
* feeder edges 0/0 on both (these builds carry NO circuits — the frontdoor
  records the circuit stage as blocked on the family-free base; the cell
  reports **missing**, never faked);
* the tests SELF-CALIBRATE against whatever the room currently contains
  (full-survival invariant, not hardcoded counts) — hardened live with the
  sibling stream after the regeneration broke the original hardcoded
  7-board expectations in the full-suite run.

Contract values proven read back out of the .rvt (not the sidecars): DP-1
PanelName "DP-1", BusRating 400 A, MainsType MCB, 42 circuits, Manufacturer
Eaton, Voltage re-folded to "480Y/277 V", dims 0.508×0.146×1.524 m from the
family's Width/Depth/Height params (spec-driven internal-unit conversion:
lengths ×0.3048, potential ×0.3048²).

### 2.2 RVT→IFC on a QUARANTINED FOREIGN sample (dev-only proof)

`samples/rmebasicsampleproject.rvt` → `experiments/convert/rvt-to-ifc-foreign/
rme_QUARANTINED.ifc` — output stays in experiments/, manifest stamped
**FOREIGN DESIGN CONTENT** + **QUARANTINED SOURCE (dev-only)**:

* equipment **29/29 survived** the round trip (all 29 electrical-equipment
  instances: panelboards, transformers, the switchboard — tags from instance
  RBS_ELEC_PANEL_NAME, kinds via the resolver's own precedence, positions
  exact);
* **feeder edges 28/28 matched** — the `RbsElectricalSystem` circuit graph
  between equipment (MDP-1→TP-1A→PP-1A, …) survives; 187 total circuits:
  28 equipment-to-equipment edges exported, 122 circuits to non-equipment
  loads + 37 unresolved COUNTED honestly, not exported;
* walls **131/133 matched**: 133 straight walls exported; re-resolving a
  whole building through the ROOM-shell-shaped resolver merges/regroups two
  runs (SWall 573769, SWall 575020 — nearest resolved run 3.9 m / 2.7 m
  away). Honest partial: the walls ARE in the IFC; the re-import grouping is
  the resolver's room-scale scope, not an extraction defect.

### 2.3 RVT→RFA extract + FULL CYCLE on our own output

* `--family "DP-1"` → `experiments/convert/extract-family/DP1_reextracted.rfa`
  — **family-mode validator VALID, 0 errors**; records verbatim (41
  elements); verify: walker clean, 0 gzip/ECC failures, ids match the source
  unit by construction. The MSB house switchboard extracts clean too
  (`MSB_reextracted.rfa`, VALID 0 errors).
* **Full cycle** — generate → load (frontdoor) → EXTRACT → RE-LOAD:
  `DP1_reextracted.rfa` loaded onto a fresh copy of the certified genesis
  base (`experiments/genesis/subst_k4/compose/G_ABPD.rvt`) via
  `rvt.famgen.loader` → `DP1_reextracted.reloaded.rvt`: load ok, roundtrip
  gate 54/54 records, unit spliced (2 save units, id sets identical),
  ContentDocuments entry present, **project validator 0 errors**,
  **four-registry census coherent** (proof JSON beside the file:
  `DP1_reextracted.reloaded.rvt.load.json`).
* Note: a standalone .rfa's single unit carries NO separator GUID (verified
  here — `FamilyIndex.units[0].guid is None` on .rfa), so the reload adapter
  mints the content GUID; the four registries all carry the minted GUID.

### 2.4 RVT→RFA on a foreign family (dev-only; the honest limit found)

`M_Level Head - Circle` (rme, nested-free) extracts and DELIVERS
(`experiments/convert/extract-family-foreign/rme_level_head_QUARANTINED.rfa`,
stamped foreign+quarantined) but family-mode validates INVALID (1 error): 19
dangling references to HOST-side resources (categories ×12, GStyles ×4, fill
patterns ×2, a material) that have **no embedded twin and are not in the host
Family's big2SmallMap2** — a project-hosted Revit-authored family is not
self-contained. Named follow-up: **host-resource repatriation** (copy the
referenced host records into the unit + remap) — not built in v1; the
manifest says exactly this. Our generated families are self-contained and
extract clean, so the shipped path is unaffected.

Also refused honestly: families with NESTED family documents (every rme
electrical family embeds 3–5 nested units) — `ExtractError` names the nested
ids; carrying nested units + their ContentDocuments entries is the second
named follow-up.

### 2.5 RFA→RFA ops edit on the generated Eaton .rfa

`experiments/frontdoor/prompt-electrical-room/families/
dp1_eaton_prl2x_400a_42sp_480y_277.rfa` + ops [set BusRating=225, set
PanelName=DP-7, rename-type "225A MCB 42ckt"] →
`experiments/convert/edit-family/dp1_edited_225A.rfa`:
**family-mode validator VALID 0 errors**, release preserved (2026), semantic
re-read proves all three (BusRating 225.0, PanelName "DP-7", type table +
PartAtom renamed) — independently re-read through `inventory_family` in the
tests. Carries convert-B's P0 proof-only stamp (fleet convention).

## 3. New facts learned (for KNOWLEDGE.md)

1. **The instance transform IS the intent frame.** `FamilyInstance.
   m_pInstanceInfo.m_Trf.m_3x3` rows = family axes in world; row 3 (famZ)
   ≈ ±Z ⇒ yaw frame (front = −famY), else upright work-plane frame (front =
   famZ, famY = up) — the exact inverse of the build stage's `_apply_frame`.
   `m_or` is the intent insertion in feet (back-face-centre for wall gear,
   footprint-centre-at-base for floor gear), so positions round-trip
   mm-exact with no geometry reconstruction.
2. **The tagging contract survives in the family document.** The generated
   families carry the contract as `ParamElemFamily` captions (PanelName,
   Voltage, BusRating, …) + values in the self-Family's type-table rows;
   spec type ids drive the unit conversion back (`length` ×0.3048 → m,
   `electrical:potential` ×0.3048² → V, `current` as-is, int64 in `m_int`,
   strings in `m_str`). ALL_MODEL builtins: −1010103 Model, −1010104
   Manufacturer, −1010109 Description.
3. **Circuit graph readback**: `RbsElectricalSystem` connector refs — the
   connType-4 ref is the panel side, other refs are loads; `m_dRating` /
   `m_nPoles` / `m_number` ride along. Works on foreign files (28 rme
   feeder edges recovered).
4. **A standalone .rfa can be assembled from ANY family unit's raw
   segments** (records verbatim) + re-authored scaffolding; the famgen
   ADocument author accepts a records-shaped shim (`UnitDoc`) — no
   FamilyDoc needed. The embedded ADocument's inline ElemTable
   (`m_elemArr`) supplies per-element owner/original ids.
5. **Foreign embedded families are NOT self-contained**: they reference
   host categories/styles/materials outside `m_big2SmallMap2` (§2.4) — any
   future RVT→RFA on arbitrary user files needs host-resource repatriation.
6. **Kind-label symmetry matters for round trips**: the extractor must
   mirror `rvt.ifc.intent._classify_equipment`'s precedence exactly
   ("appliance" ⇒ receptacle before "lighting"; ll ≤ 240 ⇒ receptacle) and
   the resolver's kind-based floor/wall convention (transformer = floor
   even when the placed transform is upright) or labels/positions drift.

## 4. Honest per-cell status (the matrix rows this stream claims)

| Cell | Status | Evidence |
|------|--------|----------|
| RVT→IFC: levels, walls, equipment(+contract), positions/frames | **works** | §2.1 all_survived=true |
| RVT→IFC: circuits/feeder edges | **works where present** | §2.2 28/28 (own output has none — reported missing) |
| RVT→IFC: foreign file | **works, dev-only, stamped** | §2.2 (walls 131/133 honest partial on re-import grouping) |
| RVT→IFC: non-electrical categories, curved/curtain walls | **missing (recorded)** | manifest `not_extracted` |
| RVT→RFA: our loaded-project outputs | **works** | §2.3 validator 0 errors ×2 |
| RVT→RFA full cycle (reload onto fresh base) | **works** | §2.3 census coherent, validator 0 errors |
| RVT→RFA: foreign project-hosted family | **partial** (delivered + labelled) | §2.4 dangling host refs named |
| RVT→RFA: nested-family documents | **missing (refused by name)** | §2.4 |
| RFA→RFA: set-param / rename-type / rename-family | **works** | §2.5 |

## 5. Files

* `src/rvt/convert/rvt_to_ifc.py` — export route + round-trip table + CLI.
* `src/rvt/convert/rfa_assemble.py` — segments→standalone-.rfa assembler
  (`UnitElement`/`UnitDoc` shims + `assemble_rfa`).
* `src/rvt/convert/extract_family.py` — extract route + `RfaFamilyDoc`
  reload adapter + full-cycle CLI.
* `src/rvt/convert/edit_family.py` — structured-ops edit route + CLI.
* `src/rvt/convert/__init__.py` — ADDITIVE edit only (docstring paragraph +
  four names appended to `__all__`); convert-B's text untouched.
* `tests/test_convert.py` — 10 tests (3 gated by RVT_SKIP_LARGE), all pass.
* `experiments/convert/{rvt-to-ifc,rvt-to-ifc-foreign,extract-family,
  extract-family-foreign,edit-family}/` — the delivered proofs + manifests.

## 6. Coordination with convert-B (same package)

convert-B (combination routes) landed `add_to_project.py` / `merge_ifc.py` /
`modify_family.py` in `src/rvt/convert/` with a delegation hook: its
`parse_family_edit` polls for `rvt.convert.edit_family.parse_family_edit`
and would re-route the live prompt+RFA vocabulary to it. **Deliberately NOT
claimed**: my `edit_family` exposes the structured-ops contract only
(`normalize_ops`/`edit_family`) and defines no `parse_family_edit`, so
convert-B's NL grammar keeps working unchanged (guarded by
`test_edit_family_leaves_nl_vocabulary_to_modify_family`). Merge proposal
for the orchestrator: move the NL grammar into `edit_family` in ONE agreed
change that keeps `modify_family`'s op-dict shape (`rename-type
{type_index, old, name}` / `set-param {param_id, caption, carrier, value,
raw}`) — until then two vocabularies would drift silently.

My modules reuse convert-B's shared plumbing (`ConvertError`, `_sha256`,
`_relp`, `_jdump`, `quarantined_input`, P0 stamp) by import.

Live coordination during the session (messages exchanged with convert-B):
convert-B proved my ops surface end-to-end from their side (their
C4_ops_surface run: VALID 0 errors) and landed TYPE-SCOPED set-param in the
engine; `normalize_ops` now passes an optional `"type"`/`"type_name"`
through as the engine's `"type"` key (scoped edits deliberately skip the
`m_familyParams` current-defaults mirror — engine behaviour). Confirmed to
them: none of `experiments/convert_combo/**` is this stream's work, and I
never wrote to docs/inbox/convert-b.md.

## 6b. PERM-MATRIX registration (for the matrix/router stream — three stale MISSING cells)

`src/rvt/frontdoor/matrix.py` (perm-matrix stream, edited live at 23:15
tonight) still declares three cells MISSING with reasons this stream has
now made stale. Proposed flips (their Cell schema; evidence resolves per
their own test contract — `tests/test_convert.py` exists, certified refs
are in viewer-certified.json):

* `Cell(("rvt",), "ifc")` → `STATUS_WORKS, "rvt_to_ifc"`, stages
  `("rvt->intent-readback", "intent->ifc")`, evidence
  `("test:tests/test_convert.py", "worked:experiments/convert/rvt-to-ifc/electrical_room_prompt.ifc")`,
  notes: round-trip survival table is the acceptance (7/7 equipment, 4/4
  walls on the acceptance output); foreign sources stamped FOREIGN +
  QUARANTINED dev-only. Impl: `rvt.convert.rvt_to_ifc.convert_rvt_to_ifc`.
  The old missing_reason ("no RVT->intent resolver exists") is now false —
  `rvt.convert.rvt_to_ifc.extract_intent` is that resolver.
* `Cell(("rvt",), "rfa")` → `STATUS_WORKS` for OUR OWN loaded-project
  outputs, `"extract_family"`, evidence
  `("test:tests/test_convert.py", "worked:experiments/convert/extract-family/DP1_reextracted.rfa")`,
  notes: family-mode validator 0 errors; full cycle re-load proven; the
  content rule concern in the old missing_reason is HANDLED, not ignored —
  foreign/project-hosted families deliver DEV-ONLY with the FOREIGN +
  QUARANTINED stamps and validate partial (dangling host refs named), so
  the shipped surface remains our regenerable content only. Impl:
  `rvt.convert.extract_family.extract_family`.
* `Cell(("rfa",), "rfa")` → the old missing_reason ("family MODIFICATION
  ... not built") is stale twice over: convert-B's prompt+rfa cell
  (`rvt.convert.modify_family`) and this stream's ops route
  (`rvt.convert.edit_family`, evidence `test:tests/test_convert.py`,
  `worked:experiments/convert/edit-family/dp1_edited_225A.rfa`). The bare
  `("rfa",)->rfa` no-op reasoning stands — the cell should point at BOTH
  instruction-carrying forms (prompt+rfa, rfa+ops).

Left to the matrix stream to apply (their file, their Cell/Stage schema,
their smoke-test wiring); the integrator has been messaged.

## 7. Proposed follow-ups (not started)

1. **Host-resource repatriation** for foreign-family extraction (§2.4).
2. **Nested-unit extraction** (carry child units + CD entries) (§2.4).
3. **Routing-matrix registration**: `tools/frontdoor.py` is frozen for the
   fleets; when it thaws, apply this INTEGRATION PATCH (three delegating
   subcommands; no behaviour change to `author`):

   ```diff
   --- a/tools/frontdoor.py
   +++ b/tools/frontdoor.py
   @@ (end of build_parser(), after the `author` subparser is fully defined)
   +    pe = sub.add_parser("export-ifc", help="RVT -> IFC4 (round-trip checked)")
   +    pe.add_argument("rvt"); pe.add_argument("-o", "--out", default=None)
   +    pe.add_argument("--out-dir", default=None)
   +    pe.add_argument("--no-roundtrip", action="store_true")
   +    px = sub.add_parser("extract-family", help="RVT -> RFA (one embedded family)")
   +    px.add_argument("rvt"); px.add_argument("--family", required=True)
   +    px.add_argument("-o", "--out", default=None); px.add_argument("--out-dir", default=None)
   +    px.add_argument("--reload-base", default=None)
   +    pf = sub.add_parser("edit-family", help="RFA + ops -> RFA (structured edits)")
   +    pf.add_argument("rfa"); pf.add_argument("-o", "--out-dir", required=True)
   +    pf.add_argument("--set", action="append"); pf.add_argument("--rename-type", action="append")
   +    pf.add_argument("--rename-family", default=None); pf.add_argument("--ops", default=None)
   @@ def main(argv=None) -> int:
        if a.cmd == "author":
            return cmd_author(a)
   +    if a.cmd == "export-ifc":
   +        from rvt.convert.rvt_to_ifc import main as _m
   +        return _m([a.rvt] + (["-o", a.out] if a.out else [])
   +                  + (["--out-dir", a.out_dir] if a.out_dir else [])
   +                  + (["--no-roundtrip"] if a.no_roundtrip else []))
   +    if a.cmd == "extract-family":
   +        from rvt.convert.extract_family import main as _m
   +        return _m([a.rvt, "--family", a.family]
   +                  + (["-o", a.out] if a.out else [])
   +                  + (["--out-dir", a.out_dir] if a.out_dir else [])
   +                  + (["--reload-base", a.reload_base] if a.reload_base else []))
   +    if a.cmd == "edit-family":
   +        from rvt.convert.edit_family import main as _m
   +        args = [a.rfa, "-o", a.out_dir]
   +        for s in a.set or []: args += ["--set", s]
   +        for s in a.rename_type or []: args += ["--rename-type", s]
   +        if a.rename_family: args += ["--rename-family", a.rename_family]
   +        if a.ops: args += ["--ops", a.ops]
   +        return _m(args)
   ```

   (Until applied, the `python -m rvt.convert.*` CLIs in §1 are the
   entrypoints; the plugin SKILL.md gains the same three verbs in its own
   unfreeze pass.)
4. `uv pip install -e .` refresh so `python -m rvt...` works without
   PYTHONPATH (the .pth points at the pre-rename path).
5. IFC export of non-electrical categories (needs emitter vocabulary beyond
   boards/transformers/proxies).

## BRANCH STATE

* Working tree: `main` (repo has no commits yet — files on disk only), no
  worktree used.
* New files: `src/rvt/convert/{rvt_to_ifc,rfa_assemble,extract_family,
  edit_family}.py`, `tests/test_convert.py`, `experiments/convert/**`
  (5 proof dirs incl. manifests), this record.
* Edited (additive only): `src/rvt/convert/__init__.py` (docstring paragraph
  + `__all__` extension; convert-B prose untouched).
* Attribution note (two sessions worked this stream's surface tonight —
  keep the trust chain straight): the `_TAG_TOKEN_RX` fallback in
  rvt_to_ifc.py and the self-calibrating test rewrite were authored IN this
  stream's own session (~00:55–00:59, tool-call transcript is the
  authority; the file diffs contain nothing else), after the acceptance
  fixture regenerated at 00:31 exposed the hardcoded expectations. A
  sibling session independently diagnosed the same failure and updated
  this record; its narrative and the preserved suite log are kept, its
  reversed attribution of the code edits is corrected here.
* Frozen files touched: NONE (tools/frontdoor.py, plugin/skills, base.py,
  versions/ untouched; no integration diff needed yet — see §6b / §7.3).
* FULL SUITE (2026-08-05 00:33→00:58, quiet machine): **1696 passed,
  8 failed, 2 skipped in 25:29** (1,682 collected at my run's start; the
  tree gained tests mid-session — live fleet). The 8 fails, attributed:
  * `test_convert.py::test_rvt_to_ifc_roundtrip_survives_on_own_output` —
    THIS stream; cause = the acceptance fixture regenerated mid-suite
    (7-board room → 4-item room) under the test's hardcoded counts; FIXED
    (self-calibrating tests, co-edited with the sibling); `tests/
    test_convert.py` now **10/10 green** against the current tree+fixture.
  * `test_convert_combo.py` ×2 (add_to_project / merge_ifc INVALID
    verdicts) — convert-B territory, same fixture-churn window;
  * `test_famgen_loader.py::test_host_family_is_our_self_family_transformed`,
    `test_genesis_2024.py::test_batch_manifest_number_does_not_collide`,
    `test_genesis_assemble.py::test_ladder_end_to_end`,
    `test_plugin_sync.py::test_no_denylisted_data_in_plugin`,
    `test_y2025_a.py::test_probes_manifest` (KeyError 'certified_by') —
    other streams' territory in a tree being edited by 4+ concurrent
    agents during the run; not touched by this stream (none import
    rvt.convert).
  * Full log preserved in-repo:
    `docs/inbox/results/convert-a-full-suite-20260805-0058.txt`.
* FULL SUITE — THIS SESSION'S OWN FINAL RUN (2026-08-05 01:40→02:06, after
  the test fixes + the integrator's plugin resync): **1713 passed, 5
  failed, 2 skipped in 26:05** (log preserved in-repo:
  `docs/inbox/results/convert-a-full-suite-20260805-0206.txt`). All 10
  `tests/test_convert.py` tests green inside the run. The 5 fails, none in
  this stream's territory:
  * `test_convert_combo.py` ×2 (add_to_project / merge_ifc: combined-output
    validator INVALID) — convert-B's cells, coupled to the REGENERATED
    acceptance fixture; reproduced deterministically here
    (combo+coverage isolation run: same 2 fails, 15 pass) and relayed;
  * `test_genesis_2024.py::test_batch_manifest_number_does_not_collide`,
    `test_genesis_assemble.py::test_ladder_end_to_end`,
    `test_y2025_a.py::test_probes_manifest` (KeyError 'certified_by') —
    other streams' territory (none import rvt.convert).
  * vs the 00:58 run: 8→5 fails (my test fix −1; famgen_loader and
    plugin_sync recovered after the integrator's resync — churn, as
    attributed).
* Fleet note (methodology): a background Bash call hard-caps at 600 s — a
  25-minute full suite launched that way is silently killed at 10 min (log
  frozen mid-dots, task vanishes; two attempts lost to this before
  diagnosis). Run long suites monitor-owned (60-min budget) or chunked.
* DONE check: three converters built in new modules, each with a runnable
  round-trip proof recorded above (re-proven against the regenerated
  fixture, transformer cell included) — MET (with the two named
  foreign-family follow-ups explicitly out of v1).
