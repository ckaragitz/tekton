# THE 2024 SUBSTITUTION CAMPAIGN — Y1..Y9_2024 + residue + G_ABPD_2024 (stream y2024-compose)

Stream: **y2024-compose** (2026-08-05).  Charter: mirror the just-certified
2025 recipe onto the CERTIFIED 2024 family-free base
`experiments/genesis2024/reduce/B2024_K4.rvt` (VERDICTS #32: b28 ALL PASS —
control + R9_2024 + K3_2024 + B2024_K4; `docs/coverage/viewer-certified.json`
lists the base as `certified`, so the v3 engine's `assert_certified` gate
ACCEPTS it — **no `--allow-uncertified` anywhere in this stream**).  Pattern
sources: `src/rvt/genesis/y2025_a.py` (settings/catalog rungs),
`docs/inbox/y2025-views.md` + `y2025_b.py` (views/residue chain),
`tools/genesis_compose_2025.py` (composer + anchor).  Port layer:
`src/rvt/genesis/port2024.py` (the genesis-2024-port stream's confirmed
field maps; `docs/inbox/genesis-2024-port.md`).  Emit context:
`tools/genesis_2024.py::context_2024` everywhere (framing by NAME from the
file's own schema — the 0x0e7c family; the seven module-local patches).

**DONE conditions met: G_ABPD_2024 COMPOSED (COMPOSED-VALID, byte-identical
to the chain's deletion-proof file RC_2024.rvt) + ANCHOR-PROVEN (compose of
the nine Y deltas == Y9_2024.rvt md5-identical) + STAGED (batch_36: CTRL +
G_ABPD_2024 + Y9_2024 + Y7_2024, bisection-first) + FLIP DIFF READY
(real pins, NOT applied — gated on the viewer PASS).  The whole 22-file
chain is BYTE-DETERMINISTIC across a full rebuild (proven twice, see §6).
NOTHING here is viewer-certified yet; every probe is PENDING the
orchestrator's viewer round.  STOP at READY: nothing uploaded.**

Drivers (repo root, `PYTHONPATH=src .venv/bin/python`):

    -m rvt.genesis.y2024_a                       # settings ladder Y1..Y7 + singles (~35 s)
    -m rvt.genesis.y2024_b                       # Y8/Y9 + RA/RB/RC chain (~20 s)
    tools/genesis_2024_compose.py all            # anchor + compose + stage + finishline
    tools/genesis_2024_compose.py flipdiff       # the gated flip (print only)

Tests: `tests/test_y2024.py` — **42, all green** (artifact tests skip
cleanly off this machine).  Canonical suite: **1697 passed / 7 failed / 2
skipped** adopted per `docs/inbox/SUITE-COORDINATION.md` (HARD RULE: no
full-suite runs; this stream ran only its stream-local file — purely
additive territory, so the expected suite delta is +42 passes).

---

## 1. THE SETTINGS LADDER (y2024_a: Y1..Y7_2024 + the two singles) — all VALID

Base: `B2024_K4` (sha256 `505ed303f9c9e89e…`, 831,488 B, 3,295 host
elements, 1/0/0/0 four-registry coherent).  Engine:
`tools/genesis_substitute_v3.py` IMPORTED and re-pointed process-locally
(rung table, `build_for` port2024-wrapped, `_class_id` → by-name against
the 2024 pin, catalog loaders → the 2024-mined tables); v3 untouched.

| rung | layer | landed | changed | bytes | verdict |
|---|---|--:|--:|--:|---|
| Y1_2024 | project pen table | 1 | 1 | 831,488 | VALID |
| Y2_2024 | browser orgs + navigator | 12 | 9 | 831,488 | VALID |
| Y3_2024 | struct/join/keynote singletons | 5 | 2 | 757,760 | VALID |
| Y4_2024 | MEP settings + size tables | 8 | 8 | 753,664 | VALID |
| Y5_2024 | remaining settings/trackers | 48 | 11 | 753,664 | VALID |
| Y6_2024 | the COMPLETE 2024 catalog in place | 1,156 | 1,156 | 749,568 | VALID |
| **Y7_2024** | patterns + materials + palette PROPERTY SETS (X7P union) | **60** | 60 | **733,184** | **VALID** |
| Y1s_2024 | single-change: pen only | 1 | 1 | 831,488 | VALID |
| Y6s_2024 | single-change: catalog only | 1,156 | 1,156 | 831,488 | VALID |

Per rung, asserted and recorded in `<rung>.json`
(`tests/test_y2024.py::test_settings_rung_valid_with_all_assertions`):
validator **0 errors / 2 warnings** IN-CONTEXT (the 2025 lesson holds on
2024: the standalone CLI reads phantom errors on non-2026 files —
in-context validation is authoritative); byte-delta table HOLDS (only the
element partition differs, changed ids == landed slots exactly, 0
added/removed, **`Global/Latest` + `Global/ElemTable` byte-identical**);
registry parity; four-registry coherence 1/0/0; retarget self-check 0
failures; `versions.detect_release` = 2024 on every emitted file.
Pen preflight: base scales [10,20,50,100,200,500], 16 pens/scale,
persp/draft −1 — **match=True** (mined by port2024, re-proven, never
assumed).  **Y1s_2024 byte-identical to Y1_2024** (determinism probe).
`probe_batch.check_batch` dry-run over all nine: **admissible=True**.

### 2024-specific content, verified on the emitted bytes (not assumed)

* **Duct physics (the 2024-new delta)**: the emitted
  `RbsDuctSettingsElem` carries the KINEMATIC viscosity
  `m_dAirViscosity = 0.00016207100394896376` = OUR record's own μ/ρ
  (port2024 hook ν = μ/ρ; Autodesk's own 2024 corpus value for THEIR μ/ρ
  is 0.0001622533748701973 — same arithmetic, our authored physics stays
  self-consistent); the 2026 dynamic-viscosity field is ABSENT.
* **AutoCam re-typed vectors**: emitted `AutoCamSettingsElem` carries the
  seven fixed `double[3]` arrays (`m_sceneFront` [0,1,0], `m_sceneUp`
  [0,0,1] …) — the layout port2024 proved byte-exact vs 2024 rst specimen
  102842.
* **Catalog**: Y6 landed 1,156 GStyleElem rows from the 2024-mined
  enum/profile (1,061 categories / 1,390 keys; the SAME 4 flag words
  differ from 2026 as in 2025 — 0x400200e → 0x400201e; zero differ from
  2025); 234 of our 1,390 rows have no slot in the base (ours-not-landed).
* **Missing-2024 honesty (the not-landed channel)**: Y5 landed 48 (2025:
  51) — the delta is exactly {`MEPNetworkDataElem`,
  `SheetsInSheetCollectionTracker`, `STEPExportSettings`}: those classes
  are absent from the 2024 schema, so the base has NO slots and the
  builders construct NOTHING for them (port2024 drop channel armed, empty;
  pinned by `test_y5_missing_2024_classes_have_no_slots_and_none_landed`).
  `SheetCollection` + `BuildingOperatingYearSchedule` likewise never
  appear (§3).

## 2. THE VIEWS/RESIDUE CHAIN (y2024_b: Y8/Y9 + RA/RB/RC) — all VALID

| rung | layer | landed / changed | validator | B |
|---|---|---|---|--:|
| Y8_2024 | datum + identity (levels/phases/units/site/base points/ProjectInfo) | 16 / 16 | 0E/2W | 729,088 |
| Y9_2024 | view types + constellations + sun (**2024 layout**) | 46 / 36 (10 byte-identical) | 0E/2W | 729,088 |
| RA_2024 | residue-A in ONE rung: subcat 169+246, assets 18, fonts 11, levels 7, arrowheads 5, dim styles 4, patterns 4+3, grids 3, +3 | 473 / 431 (42 identical) | 0E/2W | 577,536 |
| RB1_defs_2024 | 466 ParamElemExternal at **the 2024 file's own shared-parameter GUID registry keys** + 209 bindings + 108 load-class + 8 project | 791 / 583 | 0E/2W | 581,632 |
| RB2_mepcat_2024 | MEP catalog: wire insulation 26 / material 4, pipe schedule 13 / connection 8 / material 5, segments 15 | 74 / 40 | 0E/2W | 581,632 |
| RB_2024 | md5-identical alias of RB2 | — | — | 581,632 |
| Z_RC_2024 | compose-consumable residue-C: 2 stale preview caches nulled + drafting `RvtLinkOverrides` map EMPTIED + header cleaned | 3 slots (seqs 101,102) | 0E/2W | 577,536 |
| RC_2024_inplace | overlap slice: 5 view headers minus the RvtLinkSymbol parent + AreaMeasureElem 9490 unwired from topology 9744 | 6 slots | 0E/2W | 577,536 |
| **RC_2024** | **lawful straggler deletions** (maxgc): link trio + vendor DataStorage + constraint dim + 3 ref planes + 9-member room constellation | deleted **17**, PINNED **0** | **0E/1W** | **577,536** |

* RC_2024: 3,295 → **3,278 elements**; reduce_law **EDIT-FREE** (removed
  17, added 0, edited 0); only the element partition + ElemTable differ;
  Latest byte-identical; 4-registry 1/0/0/0; **release gate ok**
  (detect==2024, on-disk tag set exactly `{0xe7c}`, walker 0 errors) —
  the gate is IN the deletion report (`RC_2024.json`), and
  `test_emitted_file_is_2024_with_2024_framing` re-proves it for
  Y7/Y9/RC/G independently.
* `rc_census_2024.json` — DERIVED from the live typed graph (no prior-
  release id assumed; the 2024 sample's ids equal the 2025/2026 lineage's
  — same authored sample, per-release saves): link trio 1250029/30/31
  (symbol pinned by SIX view headers + the drafting seq-102 map), vendor
  DataStorage 1382860 (zero referrers), room constellation topology 9744
  + 8 companions held by AreaMeasure 9490, constraint dim 763420 + planes
  699327/699381/763366.
* **The 2024-layout proof on disk**: every emitted file detects as 2024
  with tag set {0xe7c}; landed view records decoded back from
  `Y9_2024.rvt` have **no `m_viewPositionId`** (DBView), **no
  `m_sheetCollectionId`** and **`m_scheduleInstanceIds` present-blank**
  (DBViewDrafting — the 2024-only field, corpus blank), no
  `m_viewPosition`/`m_viewAnchor` (Viewport v10); GeomStep's extra-data
  field drops by construction (no hook exists — port2024 §1b-1).  Pinned
  against the live 2024 schema AND the emitted bytes
  (`test_2024_schema_view_layout_deltas`,
  `test_landed_view_records_have_the_2024_layout`).
* **No 2024 year-schedule layer, BY SCHEMA**: `BuildingOperatingYearSchedule`
  is MISSING-2024 (port2024) — the census returns zero such elements and
  `Z_RC_2024` states it honestly (the 2026/2025 year-naming convention has
  no 2024 equivalent).  Pinned by `test_rc_census_year_schedules_empty_by_schema`.
* 2024 asset profile mined fresh from the three quarantined 2024 samples
  (`generic_asset_profile_2024.json`); residue-A self-check re-bound to
  the 2024 codec (`_check_object_2024`); port2024 hooks wrapped
  SOURCE-AWARE (the y2025_b lesson: a hook never clobbers a field a
  parent-copied subtree already carries in 2024 form).
* Composer handoff: `Z_RA_2024`/`Z_RB_2024` md5-identical aliases +
  `Z_RC_2024` direct; deletion specs `D_2024_{links_pair,
  vendor_datastorage,constraint_dim}.json` (pin-free singles) +
  **`D_2024_stragglers_full.json`** (the 17-id union; pin-free only after
  the RC in-place fixes — a compose without them PINS and fails RED).
* `residue_after_RC_2024.json`: 3,278 elements — **2,692 landed-ours,
  586 residue in 45 classes** (curtain constellation 232 handed over in
  `curtain_constellation_2024.json`; ZC/ZB3..ZB8 groups — outside this
  charter, listed for the next streams).

## 3. THE COMPOSER (tools/genesis_2024_compose.py) — anchor + G + batch

* **ANCHOR HOLDS**: compose(B2024_K4, the nine linearized Y2024 rung
  deltas) reproduces `Y9_2024.rvt` **BYTE-IDENTICALLY** (md5
  `b4bc6df0cfcebbd2c5c69c9d76f03398` both sides; COMPOSED-VALID, 1,299
  merged slots; `anchor_2024.json`).
* **G_ABPD_2024 COMPOSED (FULL)**: 9 Y rungs + 4 residue rungs
  (`Z_RA/Z_RB/Z_RC/RC_2024_inplace`, discovered by walking the declared
  parent chain) + the deletion UNION (the three singles collapse onto
  `D_2024_stragglers_full` — subset-collapse observed).  ONE slot
  (1250031) is substituted AND deleted → chain-faithful two-phase compose
  (substitute THEN delete), every assertion battery in both calls.
  Verdict **COMPOSED-VALID, problems []**; release gate ok
  (2024 / {0xe7c}); **FINAL == RC_2024.rvt BYTE-FOR-BYTE** (the
  full-chain replay is exact).
  `experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt` —
  **sha256 `e4a40671d8b6c649f4c8ba2ee45c1843f6d61e722a738cc2c88bd6cdb3dd925a`,
  md5 `3797961599d17d307d5f223d2ce02464`, 577,536 B** — at the EXACT
  relpath `genesis_base.json` releases.2024 reserves.
* **BATCH 36 STAGED** (the charter's four-file bisection round; the
  orchestrator uploads): `CTRL_B2024_K4_b36.rvt` (md5-identical to the
  certified base) → `G_ABPD_2024.rvt` (deepest: everything) →
  `Y9_2024.rvt` (settings+views, no residue) → `Y7_2024.rvt` (settings
  only).  Reading: control FAIL voids the round; G PASS certifies the
  campaign; G FAIL + Y9 PASS convicts residue/deletions; Y9 FAIL + Y7
  PASS convicts datum/views; Y7 FAIL → the per-half probes.json ladders
  (18 entries, both halves, all citing verdict #32) bisect further —
  Y1s_2024 isolates a single object.
* **Finish-line dry run** (`finishline_2024.json`, flip in memory only):
  **WOULD PASS post-flip** — creation_status supported, release_status
  certified, resolve_base → the pinned G (detect 2024), author
  `--target-version 2024` handoff `status=match, output_release=2024`,
  no fallback line.  (The FULL build additionally needs the build-path
  work the build2025 stream generalizes — same three gaps as 2025.)

## 4. THE FLIP DIFF — ready, NOT applied (gate: viewer PASS on G_ABPD_2024)

`tools/genesis_2024_compose.py flipdiff` regenerates this with live pins;
current output (gate status: BLOCKED — not in viewer-certified.json):

```
--- 1. src/rvt/frontdoor/assets/genesis_base.json (releases.2024) ---
     "relpath": "experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt",
-    "sha256": null,
+    "sha256": "e4a40671d8b6c649f4c8ba2ee45c1843f6d61e722a738cc2c88bd6cdb3dd925a",
-    "bytes": null,
+    "bytes": 577536,
-    "status": "pending certification",
+    "status": "certified",

--- 2. src/rvt/versions/__init__.py (KNOWN_RELEASES[2024]) ---
-        samples_dir="samples/2024", creation_certified=False),
+        samples_dir="samples/2024", creation_certified=True,
+        genesis_base="experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt"),

--- 3. tools/sync_plugin.py (the exact shape of the APPLIED 2025 flip) ---
after GENESIS_MANIFEST_2025_SRC (~line 76):
+GENESIS_BASE_2024_SRC = os.path.join(ROOT, "experiments", "genesis",
+                                     "subst_k4_2024", "compose", "G_ABPD_2024.rvt")
+GENESIS_MANIFEST_2024_SRC = os.path.join(ROOT, "experiments", "genesis",
+                                         "subst_k4_2024", "compose",
+                                         "G_ABPD_2024.manifest.json")
in asset_mappings(), after the 2025 pair (~line 205):
+    (GENESIS_BASE_2024_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2024.rvt", True),
+    (GENESIS_MANIFEST_2024_SRC, f"{GENESIS_DST_DIR}/G_ABPD_2024.compose.json", False),
then: tools/sync_plugin.py (re-sync + re-zip).
```

Post-PASS the sha256 above must be re-read from the certified file (it is
frozen now that the chain is byte-deterministic, §6 — but verify against
the uploaded bytes, never assume).

## 5. What the 2024 corpus does NOT support (named per class)

* The 2026-only conductor catalog (`CustomElement`, `NamingCell`,
  `RbsConductor*`): absent from the 2024 map, same refusal as 2025; no
  rung constructs it (drop channel armed and empty in every build).
* The five 2025-era classes (`SheetCollection`,
  `SheetsInSheetCollectionTracker`, `MEPNetworkDataElem`,
  `STEPExportSettings`, `BuildingOperatingYearSchedule`): no slots exist
  in a 2024 document, so the parent-driven builders construct nothing —
  pinned in tests; the drop channel would catch any future constructor
  that tried.
* Ours-not-landed (need the ADD path; identical shape to 2025): Y8 → 4 of
  our 5 phase filters; Y9 → the text-type constellation; Y6 → 234 catalog
  rows the base lacks.

## 6. FINDING: the chain had ONE nondeterminism — found, pinned, proven fixed

A full byte-determinism re-run (rebuild everything, diff 22 md5s) caught
`skeleton.new_geo_site` minting a **fresh random `uuid4` per build** for
`GeoSite.m_sharedCoordGUID` (skeleton.py:999; house_standard passes no
GUID) — the TWO GeoSite records of Y8 differed between runs and the delta
rippled byte-wise through every descendant file including G.  Everything
else reproduced byte-identically (empirical: the record-level diff of two
independent Y9 builds showed exactly those 2 records).

Fix (INSIDE my territory): `y2024_b.context_y2024` swaps
`skeleton.new_geo_site` with a wrapper feeding deterministic uuid5 GUIDs
(namespace `_GEO_GUID_NS`, per-call counter); restored on exit; pinned by
`test_geo_site_guids_are_pinned_deterministic`.  With the pin, **the
ENTIRE 22-file chain (settings + views + residue + aliases + G) is
byte-deterministic across a full rebuild** — proven by two complete
rebuild cycles with identical md5 sets (any lawful GUID is valid content
here: it is our project's shared-coordinates identity, exactly as the
certified 2026/2025 bases froze whatever random GUID their one build
minted).

**Cross-territory note (not applied, for the y2025 streams / skeleton
owner)**: the same variance exists in every chain that rebuilds Y8
(2026/2025 included) — y2025-views' byte-determinism claim holds for its
frozen artifacts but a `--rebase` rebuild of Y8_2025 would shift its
GeoSite GUIDs and every descendant md5.  Proposed proper fix: a
deterministic default (or explicit GUID) at the two house_standard call
sites, or the context-swap pattern used here.

## 7. Other findings / notes

1. `genesis_compose_2025.linearize_chain_specs` + `_report_parent` are
   release-agnostic and are IMPORTED by `genesis_2024_compose.py`
   (verbatim reuse, no fork) — they behaved identically on the 2024 chain
   (subset-collapse + last-wins + continuity all observed working).
2. `genesis_deletion.adocument_dangling_census` still hardwires the 2026
   base (the y2025_b finding applies verbatim); my deletion rung censuses
   dangling ids via `build_state_v2` instead.
3. The `probe_batch` `base_status` for a candidate-base reads
   `"certified (lineage informational only for a candidate-base)"` — a
   startswith match, not equality (test adjusted accordingly).
4. Shared files: `experiments/genesis/subst_k4_2024/probes.json` is
   merge-written by both halves (entries keyed by `stream`); the compose
   dir has its own probes.json for the batch.  `tools/sync_plugin.py` run
   per the standing rule after adding the two `src/rvt/genesis` modules
   (synced 2 files; deny-audit clean; validation passed; zip rebuilt
   4,122 KB).
5. An early batch_36 staging from the pre-pin (nondeterministic) build was
   removed and restaged from the frozen deterministic artifacts BEFORE any
   upload (nothing had left the machine; the staged batch now carries the
   proven bytes).

## SUITE RESULT

Stream-local only, per the SUITE-COORDINATION hard rule:
`tests/test_y2024.py` — **42 passed** (0.7 s), run repeatedly through the
build.  Canonical full-suite count adopted: **1697 / 7 / 2**
(docs/inbox/SUITE-COORDINATION.md; this stream is purely additive — no
existing source, tool, or test file edited — so its expected delta is
+42 passes).

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — not a git repo on this machine; no
  branch work (integration is the orchestrator's).
* NEW (this stream's territory):
  * `src/rvt/genesis/y2024_a.py` — the settings/catalog ladder driver
  * `src/rvt/genesis/y2024_b.py` — the views/datum + residue chain driver
    (context, source-aware hooks, geo-GUID pin, RC census, lawful-deletion
    emitter, D specs, Z aliases, probes merge)
  * `tools/genesis_2024_compose.py` — the composer (context, discovery,
    anchor, two-phase compose, four-file stage, finishline, flipdiff)
  * `tests/test_y2024.py` (42 green)
  * `experiments/genesis/subst_k4_2024/` — `Y1..Y7_2024` + `Y1s/Y6s_2024`
    + `Y8/Y9_2024` + `RA_2024` + `RB1_defs/RB2_mepcat/RB_2024` +
    `Z_RA/Z_RB/Z_RC_2024` + `RC_2024_inplace` + `RC_2024` (.rvt + .json
    each), `CTRL_B2024_K4_base.rvt`, `D_2024_*.json` (3 singles + union),
    `rc_census_2024.json`, `residue_after_RC_2024.json`,
    `curtain_constellation_2024.json`, `generic_asset_profile_2024.json`,
    `probes.json`
  * `experiments/genesis/subst_k4_2024/compose/` — `G_ABPD_2024.rvt`
    (sha256 `e4a40671…`, md5 `37979615…`, 577,536 B) + manifest +
    phase1/inplace intermediates, `G_Y2024_anchor.rvt` + `anchor_2024.json`
    (BYTE_IDENTICAL true), `compose_2024.json` (COMPOSED-VALID, proof
    identical), `finishline_2024.json` (WOULD PASS post-flip),
    `probes.json`, `batch_36.json` + staged copies
  * this record
* SHARED (cooperatively written): `plugin/` via `tools/sync_plugin.py`
  (standing rule; 2 files synced, validation passed).
* Touched OUTSIDE territory: **NOTHING** — no existing source, tool, or
  test edited; §6/§7 fixes are PROPOSED for their owners.
* DONE check: G_ABPD_2024 composed ✓ (COMPOSED-VALID; == RC_2024
  byte-for-byte; release gate 2024/{0xe7c}) + anchor-proven ✓ (md5
  b4bc6df0… both sides) + staged ✓ (batch_36 four-file bisection round,
  control md5-identical to the certified base) + flip diff ready ✓ (real
  pins, gated BLOCKED, not applied).  STOP at READY: nothing uploaded,
  nothing claimed certified; every verdict is the orchestrator's viewer
  round.
