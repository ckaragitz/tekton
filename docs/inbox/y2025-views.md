# Y2025 DATUM/VIEWS + RESIDUE RUNGS (Y8/Y9 + RA/RB/RC) — stream y2025-views

Stream: **y2025-views** (2026-08-04, evening).  Charter: the 2026 ladder's
Y8/Y9 + residue A/B/C equivalents on the **certified** 2025 base — Y8_2025
(identity/site/project info + levels/phases), Y9_2025 (the 19 view types +
view constellations + document sun, in the 2025 LAYOUT), then RA_2025 /
RB_2025 / RC_2025 as far as the 2025 corpus supports.  Territory:
`src/rvt/genesis/y2025_b.py`, `tests/test_y2025_b.py`,
`experiments/genesis/subst_k4_2025/{Y8,Y9,RA,RB,RC,Z_R,D_2025,CTRL}*`,
this record.

**DONE conditions met: the WHOLE chain is built and validating —
Y8_2025 → Y9_2025 → RA_2025 → RB1/RB2 (=RB_2025) → Z_RC_2025 →
RC_2025_inplace → RC_2025, every in-place rung validator-0-errors +
byte-delta-vs-parent asserted + `Global/Latest`/`Global/ElemTable`
byte-identical (registry parity by construction), the deletion rung
reduce-law **EDIT-FREE**; everything port2025-adapted; the composer handoff
staged (3 Z rungs + 3 pin-free D specs, discovery dry-run confirmed).
NOTHING of this chain is viewer-certified — every rung is STAGED, its
certification PENDING the next viewer round; the only certified file used
is the base.**

Driver: `.venv/bin/python -m rvt.genesis.y2025_b` (stages
`y89 | ra | rb | rc | probes`, `--rebase`).  Tests:
`tests/test_y2025_b.py` — **22, all green** (artifact tests skip cleanly off
this machine).  Rebuild is **byte-deterministic** (all seven chain md5s
reproduced on a full re-run).

---

## 1. Base + parent resolution (the coordination contract, honored)

* BASE of every rung: `experiments/genesis2025/reduce/B2025_K4.rvt` — the
  viewer-CERTIFIED 2025 family-free base (verdicts #28).  The v3 gate
  (`assert_certified`) passes on the real ledger; **no
  `--allow-uncertified` anywhere in this stream.**
* The settings stream landed `Y1_2025..Y7_2025` into
  `experiments/genesis/subst_k4_2025/` at 23:11–23:12 — **before my first
  emission**, so the prototype-parent path was never needed:
  every report records `parent_mode: settings-chain`; Y8_2025's parent is
  the settings stream's `Y7_2025.rvt` (753,664 B), and slot protection /
  prior correspondence read their `Y1_2025..Y7_2025.json` reports.
  (The module still carries the documented prototype fallback +
  `--rebase`; it went unused.)
* Every emission ran inside `context_y2025` =
  `tools/genesis_2025.py::context_2025` (the SEVEN 2026-baked framing
  constants + the ADocument decoder — the mandated context) **plus** the
  per-release default codecs (`rvt.encode._DEFAULT_ENCODER`,
  `regadd/regdiff.ObjectDecoder`), the 2025 catalog constants, v3
  `_class_id` → `port2025.class_id_2025`, and the port2025 build
  adaptation.  All swaps restore on exit (tested).

## 2. THE CHAIN — all VALID, every gate green

| rung | layer | landed / changed | validator | byte-delta + registries | B |
|---|---|---|---|---|--:|
| Y8_2025 | datum + identity (v3 Y8 = X8 + X9 level/phase split) | 16 / 16 (13 role, 1 role-primary, 1 donor, 1 sibling-donor) | 0E/2W | holds; ADoc+ET identical | 749,568 |
| Y9_2025 | view types + constellations + sun (v3 Y9; **2025 layout**) | 46 / 36 (42 role + 4 donor; 3 Y2-landed slots protected; 10 byte-identical) | 0E/2W | holds; ADoc+ET identical | 749,568 |
| RA_2025 | residue-A round in ONE rung: subcat 169+246, assets 18, fonts 11, levels 7, arrowheads 5, dim styles 4, patterns 4+3, grids 3, grid-head/int-elev/callout 3 | 473 / 431 (42 byte-identical) | 0E/2W | holds; ADoc+ET identical | 598,016 |
| RB1_defs_2025 | the parameter-DEFINITIONS layer: 466 ParamElemExternal at **the 2025 file's own shared-parameter GUID registry keys (466/466 preserved, byte-verified)** + 209 bindings + 108 load-class + 8 project | 791 / 583 (208 reproduced machinery) | 0E/2W | holds; ADoc+ET identical | 602,112 |
| RB2_mepcat_2025 | the MEP catalog: wire insulation 26 / material 4 / temp-rating 3, pipe schedule 13 / connection 8 / material 5, pipe segments 15 | 74 / 40 (34 reproduced) | 0E/2W | holds; ADoc+ET identical | 602,112 |
| RB_2025 | md5-identical alias of RB2 (the round's deep file) | — | — | md5 `3ade6173…` | 602,112 |
| Z_RC_2025 | residue-C **compose-consumable** slice: 27 year schedules named OURS + 2 stale preview caches nulled + the residue drafting view's `RvtLinkOverrides` display map EMPTIED (its seq-102 link-symbol pin) + its header cleaned | 30 slots (seqs 101,102) | 0E/2W | holds; Latest+ET identical | 598,016 |
| RC_2025_inplace | residue-C **overlap** slice: the 5 landed view slots' seq-101 headers minus the RvtLinkSymbol deletion-parent + AreaMeasureElem 9490 unwired from topology 9744 | 6 slots (seqs 101,102) | 0E/2W | holds; Latest+ET identical | 598,016 |
| **RC_2025** | **the lawful straggler deletions** (maxgc): link trio + vendor DataStorage + constraint dim + 3 ref planes + the 9-member room constellation | deleted **17**, PINNED **0** | **0E/1W** | **reduce_law EDIT-FREE** (removed 17, added 0, survivors edited 0); only Partitions/20 + ElemTable differ; Latest byte-identical; 4-registry 1/0/0/0; **0 dangling registry refs to the deleted ids** | 598,016 |

* Wall clock ≈ 14 s (y89) + 3.5 s (ra) + 6 s (rb) + 7 s (rc).
* RC_2025: 3,333 → **3,316 elements**; the validator warning count DROPS
  2→1 — the pre-existing Extensible-Storage decode-gap warning leaves WITH
  the vendor DataStorage blob.
* Every in-place rung: `rvt.regadd.substitute_elements`, keep_row, no id
  added/removed, per-seq order identical, regdiff sample 6/6 identical,
  coherence 1/0/0, per-record 2025 encode→decode→re-encode self-check **0
  failures** across all landed records.

### The 2025-layout proof (the port table's four missed deltas, on-disk)

* `versions.detect_release` = **2025** for every emitted file; the on-disk
  block-header tag set of Y9_2025 and RC_2025 is exactly **{0xed9}** (the
  2025 SegmentMarker; walker 0 errors) — no 2026 framing leaked.
* Every landed view record decoded back from `Y9_2025.rvt`: **no
  `m_viewPositionId`** (DBView), no `m_sheetTitleBlockId` (DBViewDrafting),
  no `m_viewPosition`/`m_viewAnchor` (Viewport v13→10) — pinned in tests
  against the live 2025 schema AND the emitted bytes.
* port2025 adaptation is stamped in every build report;
  **dropped-as-2026-only = 0 records in every rung** — nothing on this
  chain constructs the conductor catalog (see §4).

## 3. RC census — DERIVED from the live graph, not assumed

`rc_census_2025.json` (all sets computed by referrer/field scan; the 2025
sample's ids happen to equal the 2026 lineage's — same authored sample,
per-release saves):

* link trio 1250029/30/31; the symbol pinned by SIX view headers
  (230, 69851, 245443, 1064656, 1454508 + drafting 1457028) **and** the
  drafting view's seq-102 `m_pRvtLinkOverrides.m_displaySettingsMap` (the
  2026 ZC_browse finding, rediscovered here mechanically).
* vendor DataStorage 1382860: **zero referrers**.
* room constellation: topology 9744 + 5 CurveElem + LevelRoomPlan + RoomElem
  + SketchPlane 245433 (closure over the typed graph); held by AreaMeasure
  9490's obj + header wiring (finding-2 shape).  The second measure/topology
  pair (9494/9745) is CONTENT-FREE and stays, exactly as 2026 left it.
* constraint set: LinearDimString 763420 + RefPlanes 699327/699381/763366
  (the planes' EQ constraint names the dim — they leave together).
* Pin-audit before emission (maxgc): {instance+copywatch} 2/2 clean,
  {vendor DS} 1/1, {dim+planes} 4/4; symbol and room PINNED until the
  Z_RC/RC_inplace fixes — after them the full 17-seed deletes with
  **PINNED 0**.

### Charter mapping note (levels/grids/phases)

The charter's Y9 line lumps "levels/grids/phases"; the certified builders
split them and this chain follows the builders: **levels + phases are
Y8_2025** (v3's Y8 = X8 + the level/phase layer of X9 — the in-place split
the 2026 ladder proved: plan↔level binding holds by construction), and
**grids are RA_2025** (residue-A `plan_datum` — the skeleton has no grid
constructor; grids were never a Y-rung class in 2026 either).  All three
layers are in the chain; nothing was dropped by the re-mapping.

## 4. What the 2025 corpus does NOT support / out-of-scope (named per class)

* **The 2026-only conductor catalog** (`CustomElement`, `NamingCell`,
  `RbsConductor{Size,Material,InsulationMaterial,TemperatureRating}`):
  absent from the 2025 class map (schema-pinned in tests).  Charter says
  skip + note: **no rung of this chain constructs it** (0 slots exist, 0
  records built), the port layer's drop channel is armed and reported in
  every build (`build_info.port2025.dropped_2026_only == []`), and the wire
  types' 2025 representation is the string-valued
  `RbsWireType.m_strMaxConductorSize` (port2025 hook).
* **Ours-not-landed** (need the ADD path or a base carrying the class —
  identical to 2026): Y8 → 4 of our 5 phase filters; Y9 → our 3 system text
  types + 3 fonts + 3 categories + 3 styles (the text-type constellation).
* **Year-schedule naming**: the 2026 convention (year name = the wrapped
  OUR day-schedule name) is impossible here — the day schedules are still
  Autodesk residue (the ZC_hvac/residue-a2 groups are NOT in this charter).
  Our names are our own numbering vocabulary (`GEN Operating Year 01..27`);
  27/27 byte-verified in `Z_RC_2025.rvt`.
* **Left with reasons** (RA report `residue_left_in_place`): the
  family-scoped curtain copies (40 CategoryElem + 40 GStyleElem + 24 fonts
  + 8 each of dim styles / interior-elev / callouts / pen tables), the
  placed content (5 CurveElem + LevelRoomPlan + LinearDimString + 4
  LegendComponents — the first three DELETED lawfully at RC_2025; the 2
  curtain-surrogate previews leave with the curtain set).
* **Residue after RC_2025** (`residue_after_RC_2025.json`): 3,316 elements,
  **2,731 landed-ours, 585 residue in 44 classes** — product-data 185
  (HVAC space/building/schedule types — residue-a2's 2026 territory),
  no-constructor 109 (fonts 24, SectionAttributes 10, ColorFillSchema 9 …),
  curtain systems 97 (queue below), content 49 (sketch/ref planes),
  family-scoped subcat 80, electrical catalog 39 (demand factors / load
  classes — constructor exists, ZC_elec territory), surplus 15, conduit
  partial 11.  These are the ZB3..ZB8 + ZC groups — **outside this
  charter's RA/RB/RC scope**, listed for the next streams.
* **Curtain constellation 2025**: computed and handed over —
  `curtain_constellation_2025.json`, **232 elements** (8 families + 8
  surrogates + 72 family DBViewTypes + every m_famId-scoped companion) —
  the coherent-REMOVAL queue (the 2026 D_curtain equivalent; not mine).

## 5. COMPOSER HANDOFF (verified against tools/genesis_compose_2025.py)

The compose stream's `compose_2025.json` names its missing layers as
"Z*-named residue rungs + D_*.json deletion sets" watched under this very
directory.  Staged, and its discovery functions dry-run against the real
tree pick up exactly:

* `R2025:Z_RA_2025` (431-record delta vs `Y9_2025.rvt`),
  `R2025:Z_RB_2025` (623 vs `RA_2025.rvt`), `R2025:Z_RC_2025` (30 vs
  `RB_2025.rvt`) — Z_RA/Z_RB are md5-identical aliases of RA_2025/RB_2025
  with parent-naming reports; slot-DISJOINT from each other and from every
  Y rung, and parent-coherent vs the base at their slots (composition laws
  1/3/4 hold by construction).
* Deletion specs `D_2025_links_pair.json` (1250030+1250031),
  `D_2025_vendor_datastorage.json` (1382860),
  `D_2025_constraint_dim.json` (763420 + 3 planes) — the maxgc-pin-free
  sets — PLUS **`D_2025_stragglers_full.json`**, the 17-id UNION (adds the
  RvtLinkSymbol + the 9-member room constellation), published after the
  compose stream's discovery evolved: their walker now consumes the whole
  declared parent chain incl. `RC_2025_inplace` (linearized last-wins) and
  collapses subset specs onto a union, so the union is pin-free in their
  merge and the final G should reproduce this chain's deletion-applied
  proof file `RC_2025.rvt` (md5 `470087732a98168af313f8a253f65edd`)
  byte-for-byte.  On any compose WITHOUT the fixes the union PINS and the
  compose fails RED (pin evidence) — never a silent partial deletion.
  Verified by dry-running their `discover_deletion_specs` (subset-collapse
  observed: the three singles fold into the union).
* LIVE COMPOSE STATE at record close: the compose stream re-pointed its Y
  layer at THIS directory's certified-base chain (`Y1_2025..Y9_2025` —
  settings + this stream) and composed `compose/G_ABPD_2025.rvt`
  consuming `Z_RA/Z_RB/Z_RC + RC_2025_inplace` + the three subset D specs;
  their first pass read NOT-CLEAN on an internal "rung byte fidelity"
  check (their linearizer's last-wins drops at the five view-header slots
  + AreaMeasure 9490 are the expected exceptions — messaged to the
  integrator, along with the union spec).

## 6. probes.json + upload discipline

`experiments/genesis/subst_k4_2025/probes.json` — merge-written: this
stream's 9 entries added, the settings stream's 9 preserved (keyed by
`stream`).  Bisection-first order for my rungs: **RC_2025 →
RC_2025_inplace → Z_RC_2025 → RB_2025 → RB2 → RB1 → RA_2025 → Y9_2025 →
Y8_2025** (RC_2025 is the deepest cumulative file: one PASS proves the
whole chain + the deletion layer).  Upload every batch with
`CTRL_B2025_K4_base.rvt` (md5-identical to the certified base; staged) +
a certified-2026 control per `tools/probe_batch.py stage`.  Certification
cascades: a parent FAIL voids its children.

## 7. Findings / cross-territory notes (nothing outside my territory edited)

1. **`tools/genesis_deletion.py::adocument_dangling_census` hardwires the
   2026 base** (`Document.from_file(BASE)` at line ~909): unusable inside a
   2025 context (raises the 0x3a3 marker error).  My module censuses the
   dangling ids via the arbiter's own `build_state_v2` Latest/ContentDocs
   scan instead.  Proposed fix (not applied): parameterize `base`.
2. **`residue_a.emit_rung` declares its parent as "base"** — right for 2026
   (Y9 was certified) but on a staged chain the ledger-certified ancestor
   differs; my driver post-stamps the report with the true certified base
   + a note.  Cosmetic; no code change proposed.
3. **port2025 HOOKS on already-2025-shaped sources**: residue planners copy
   decoded-2025 subtrees into constructed objects; a hook (e.g. GeomStep
   `m_oExtraData`, GeomTable ints) would clobber the carried value.  My
   context wraps every hook source-aware (carry when the 2025 field is
   present; synthesize otherwise) — tested.  Worth folding into port2025
   proper if other streams adapt parent-copied objects.
4. **Shared files**: probes.json (merged, foreign entries preserved),
   `CTRL_B2025_K4_base.rvt` (re-staged byte-identical).  `tools/
   sync_plugin.py` run per the standing rule after adding
   `src/rvt/genesis/y2025_b.py` — it synced 16 drifted files (15 from
   other streams' completed work); deny-audit clean, validation passed,
   zip rebuilt.

## SUITE RESULT

`tests/test_y2025_b.py`: **23 passed** (standalone, after the final
artifact + spec regeneration — run twice, byte-deterministic artifacts).
Full suite (`.venv/bin/python -m pytest -q --continue-on-collection-errors`)
launched 23:19 from the repo root; **still running at record-close** (prior
streams' runs took ~31 min wall; at close it was ~4% with 2 F's already in
another stream's territory, consistent with the documented pre-existing
baseline failures).  The tail of its output lands in
`/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/suite_y2025b.txt`
(orchestrator: read the count there, or re-run the command).  This stream
edited NO existing source or test file (purely additive: one new module,
one new test file, artifacts, this record), so the expected delta vs the
last counted baseline (versions stream: 1,284 passed / 4 failed / 5
skipped / 1 collection error, all five defects pre-existing in other
territories) is **+23 passes** from `tests/test_y2025_b.py`, plus whatever
the other concurrent streams (settings / compose / convert / port2023)
added this evening.

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — not a git repo on this machine; no
  branch work (integration is the orchestrator's).
* NEW (this stream's territory):
  * `src/rvt/genesis/y2025_b.py` — the driver (context, adapters, rung
    drivers, RC census, lawful-deletion emitter, composer handoff, probes
    merge)
  * `tests/test_y2025_b.py` (22 green)
  * `experiments/genesis/subst_k4_2025/`: `Y8_2025`, `Y9_2025`, `RA_2025`,
    `RB1_defs_2025`, `RB2_mepcat_2025`, `RB_2025`, `Z_RA_2025`,
    `Z_RB_2025`, `Z_RC_2025`, `RC_2025_inplace`, `RC_2025` (.rvt+.json
    each; RC_2025 md5 `470087732a98168af313f8a253f65edd`, 598,016 B,
    3,316 elements), `D_2025_{links_pair,vendor_datastorage,
    constraint_dim}.json`, `RC_2025_full_straggler_set.spec.json`,
    `rc_census_2025.json`, `residue_after_RC_2025.json`,
    `curtain_constellation_2025.json`, `generic_asset_profile_2025.json`
    (503 specimens over the six 2025 samples)
  * this record
* SHARED (cooperatively written): `probes.json` (merge; settings entries
  preserved), `CTRL_B2025_K4_base.rvt` (byte-identical re-stage),
  `plugin/` (tools/sync_plugin.py per the standing rule).
* Touched OUTSIDE territory: **NOTHING else** — no existing `src/rvt/**`,
  tool, or test edited; §7's fixes are PROPOSED.
* DONE check: **the deepest buildable rung chain is the WHOLE charter chain
  and it validates with assertions** (every in-place rung 0 errors +
  byte-delta + parity + coherence; the deletion rung EDIT-FREE + validator
  0 + stream-identity + registries + zero dangling); everything
  unreachable is named per class (§4).  STOP at READY: nothing uploaded,
  nothing claimed certified; every probe is PENDING the orchestrator's
  viewer round.

## ORCHESTRATOR RELAY (from the integrator, ~23:50)
1. Your artifacts are VERIFIED on disk byte-exact (y2025-views.md present;
   D_2025_stragglers_full.json published; RC_2025.rvt 598,016 B md5
   470087732a98168af313f8a253f65edd — matches your proof claim exactly).
2. Your composer leads are routed to the compose stream via this record —
   it owns G_ABPD_2025 assembly and will consume them here.
3. Your context surfaced a REAL bug, now FIXED: the front-door build
   tripwire only exempted the bundled base path, so an explicit --base
   under experiments/genesis/** (the 2025-base shape) would have failed
   RED mid-build. build.py now allows [opts.base.path, opts.specimen_src];
   probed green; 66/66 covering tests. Your chain tooling doesn't route
   through build_intent and was never affected.
