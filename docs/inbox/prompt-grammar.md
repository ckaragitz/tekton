# prompt-grammar — restore wall derivation + rating-class voltage vocabulary (issue #1)

Stream: `clkaragitz/1-prompt-grammar` · Territory: `src/rvt/frontdoor/prompt_intent.py`, `tests/test_prompt_intent.py` · 2026-08-07

## What was built

Two behaviours of the rules-first prompt parser, both flagged four times in
the campaign records (genesis-audit: "the current intent grammar derives 0
walls from the demo prompt (v3 had 4) — queue with the 250V vocab item"):

1. **Default room shell.** A NAMED room with no dimensions now yields the
   9.144 x 6.096 m (30 x 20 ft) default shell (`DEFAULT_ROOM_W_M/_D_M`)
   instead of silently degrading to an equipment-only row. The default is
   stated in `coverage.defaults_applied`. `no walls` / `equipment only` and
   prompts with no room noun keep their old behaviour (pinned by tests).
2. **Rating-class voltage vocabulary.** A new amp-less service-voltage
   clause (`_RE_RATED_VOLT`: "rated for 250V", "600V class") resolves the
   service system. UL RATING CLASSES map to the system they imply
   (`RATING_CLASS_TO_SYSTEM`: 250/240 → the 240 V-class system) and the
   mapping is ALWAYS stated in `defaults_applied` — never silent. Real
   systems pass through the existing vocabulary unmapped (480 → 480Y/277,
   600 → 600Y/347). "250V" no longer appears in `ignored_words`.

## Evidence (numbers)

`prompt_to_intent` on the three DONE prompts (was → is):

| prompt | walls | service_voltage | ignored_words |
|---|---|---|---|
| "a 30 by 20 ft electrical room rated for 250V with 6 panels" | 4 → 4 | 480Y/277 → **240** | ['250V'] → **[]** |
| "an electrical room with 6 panels" | **0 → 4** (default shell, stated) | 480Y/277 | [] |
| "an electrical room rated for 250V with 6 panels" (the demo) | **0 → 4** | 480Y/277 → **240** | ['250V'] → **[]** |

Coverage excerpts (demo prompt):
- `defaults_applied` now carries: "room dimensions: 9.144 x 6.096 m (30 x 20 ft)
  DEFAULT room shell — the room was named with no dimensions; say 'W by D ft'
  to size it" and "service voltage: 240 V-class system mapped from the
  prompt's '250 V' rating class (a 250 V rating names the equipment's
  maximum voltage class, not a system voltage)".
- `understood` carries `{"as": "service voltage", "voltage": "240", "rated": "250 V"}`.

End-to-end (Windows, fresh clone, plugin-bundled genesis base via
`RVT_GENESIS_BASE=plugin/assets/genesis/G_ABPD.rvt`): both prompts build
`prompt_room.rvt`, `ok: true`, PROOF-ONLY stamp; `tools/rvt_validate.py`
**0 errors** (2 warnings = the known fresh-clone decoder gaps: 1 DataStorage
ES blob, no `extracted/` corpus).

## Tests

- NEW `tests/test_prompt_intent.py`: 10 tests — rating-class mapped+stated,
  600V stays 600Y/347, 480V unmapped, amp-service clause untouched, default
  shell + stated, explicit dims win, `equipment only` still suppresses,
  no-room-noun stays equipment-only, both demo prompts end-to-end
  (`@needs_catalog`). 10/10 pass.
- `tests/test_frontdoor.py`: 36 passed / 4 skipped (catalog-gated) /
  1 failed = `test_handoff_only_route_writes_the_package`, which fails
  IDENTICALLY on clean main on Windows (cp1252 `UnicodeEncodeError` writing
  '→' in MANIFEST.md) — pre-existing, filed as a follow-up issue, NOT this
  stream.

## Findings (out of scope, filed as issues)

Windows fresh-clone portability, all reproduced on clean main:
1. Manifest writer uses the locale codec (cp1252) → `UnicodeEncodeError` on
   '→'/'®' (breaks `test_handoff_only_route_writes_the_package` and
   `test_bootstrap.py::test_run_launcher_frontdoor_prompt_handoff`).
2. `tools/sync_plugin.py` on Windows: (a) re-zip step dies
   `FileNotFoundError` (subprocess exec of a missing binary); (b) it
   regenerates `plugin/assets/schema_cache/index.json` `sources` with
   backslashes → `--check` permanently flags index.json drift on Windows.
3. `plugin/scripts/validate_plugin.py` fails `skills/_shared: SKILL.md
   missing` (23 other assertions pass) — platform-independent, likely a
   validator/skill-layout drift.

## BRANCH STATE

- Files written: `src/rvt/frontdoor/prompt_intent.py` (+56/-6),
  `plugin/lib/src/rvt/frontdoor/prompt_intent.py` (sync mirror),
  `tests/test_prompt_intent.py` (new), this record.
- Gates: stream-local tests 10/10 + frontdoor 36 pass (1 pre-existing
  Windows failure, baselined on main); `sync_plugin.py` run; `--check`
  clean EXCEPT the known Windows backslash churn in
  `assets/schema_cache/index.json` (finding 2b above — not committed);
  `rvt_validate.py` 0 errors on both built rooms.
- Staged vs shipped: no viewer round needed (`ready` issue, no
  certification claim). Outputs are PROOF-ONLY per the standing gates.
- Follow-ups: the three Windows findings above → new issues, not this PR.

---

# prompt levels honoured — every level clause parsed, stage D binds them to the base's story datums, gear placed per level (issue #147)

Stream: eng #147 · branch `cam/147-prompt-levels` · PR #293 · 2026-08-09 ·
Territory: `src/rvt/frontdoor/prompt_intent.py`, `src/rvt/ifc/intent.py`
(`Equipment.level`, `RoomShell.level`, defaulted level flag),
`src/rvt/frontdoor/levels.py` (NEW, stage D), `src/rvt/frontdoor/build.py`,
`src/rvt/frontdoor/manifest.py`, `src/rvt/frontdoor/ifc_out.py` (storey per level,
fix round), `tools/ifc_intent.py` (`stage_equipment` level selection only),
`tests/test_prompt_intent.py`, `tests/test_frontdoor.py`, `tests/ci_shard.txt`.
No hot file, no `manipulate.py` / `mutate.py` edit (#186's territory — the
certified `set_level_elevation` / `modify_element` / `commit_plans` are called,
not changed).

## What was built

1. **Parser (`parse_prompt`).** The single `_RE_LEVEL.search` became three
   clause kinds, each consumed on EVERY occurrence: a storey COUNT
   (`_RE_STOREYS`: 'two storey', '3-story', 'two floors', 'single storey'), a
   level REFERENCE (`_RE_LEVEL_REF`: 'on level 2', 'the second floor',
   'ground floor', 'at L2', 'top floor'), and the FLOOR-TO-FLOOR height
   (`_RE_F2F`: 'floor to floor 14 ft', '4.2 m floor to floor', 'storey height
   of …') — found before the room-height grammar so 'floor 14' / 'height of
   14 ft' inside it are never a level reference or a clear height. A
   reference binds to the equipment clause it sits in (the clause window,
   extended past a tag list that ran across 'and'); one bound to no clause
   scopes the ROOM (its walls and every unreferenced item). Storeys =
   max(count, every reference); datums sit a floor-to-floor height apart
   (stated clause, else room height + `DEFAULT_FLOOR_ALLOWANCE_M` = 2 ft,
   recorded in `defaults_applied`); an item on the room's level by default is
   STATED when the prompt has more than one storey. Storeys past
   `BUILT_STOREYS = 2` stay in `intent.levels` and land in
   `coverage.not_built` ("storeys beyond 2 (base carries two story levels):
   Level 3 recorded in the intent, NOT created …") — the old clamp to 3 and
   the blanket warning "all equipment is placed on Level 1" are gone. Level
   words are scrubbed from the count head ('level 2 lighting panels' ≠ two
   panels). A prompt silent about levels yields ONE storey flagged
   `default: True` (asserts nothing about the base's datum). `layout_room`
   runs the same rule once per storey (each level's lineup / panel rows start
   afresh; z stays level-relative). `Equipment.level = 'L<n>'`,
   `RoomShell.level`, and the scene brief's per-product `storey` follow.
2. **Stage D (`rvt.frontdoor.levels`, wired in `build._run` right after
   stage P).** `bind_levels` pairs intent levels (lowest first) with the
   base's `is_building_story` datums; `stage_levels` renames (`Level.m_text`
   via `manipulate.modify_element`) and re-elevates
   (`manipulate.set_level_elevation` — both datum-plane origins, exactly the
   M3-certified shape) each datum that differs, ONE `commit_plans`, then
   re-opens the file and proves names/elevations landed with `replaced ==
   the edited datums`, ElemTable count unchanged. Intent levels with no datum
   left come back `not_built` (→ `build.degradations` + MANIFEST.md "level
   NOT created") and map to the top datum at their OWN z. `level_map` =
   `{intent id: (Level id, datum z ft)}` feeds W (walls on the room's datum
   via the existing `level_id=`) and E (`stage_equipment(level_ids=…)`: per
   item `m_assocLevelId` = its storey's datum, z = datum z + level-relative
   z; recorded per instance as `level` / `level_id` / `z_above_level_ft`).
   Nothing to change (defaulted or already-matching levels) → no file, the
   caller keeps its input, output byte-identical to a build without the
   stage. A failed edit degrades to the base's datums (map carries the base's
   elevations) — never withholds.
3. **Manifest.** `build.levels` (the stage record: bound levels with
   before/after name + elevation, `not_built`, `level_map`, commit summary),
   per-instance level facts in `elements_created`, a "levels (…)" line and
   "level NOT created" lines in MANIFEST.md.

Walls: ONE ring on the room's level (v1, as chartered) — `RoomShell.level`
makes "an electrical room on level 2 with 4 panels" put walls AND panels on
Level 2; per-storey rings are named in follow-up #295.

## Evidence (numbers)

DONE prompt `"a two storey electrical building 40 by 30 ft, floor to floor 14
ft, with a main switchboard and four lighting panels on level 2"`, fresh cloud
clone, bundled pinned bases, `tools/frontdoor.py author --prompt … [--target-version Y]`:

| target | exit | manifest `intent.levels` | output story datums (`Document.levels()`) | LP-1..4 `m_assocLevelId` / z ft | MSB | stage D s | `rvt_validate.py` |
|---|---|---|---|---|---|---|---|
| 2026 (before, `main` a5dd53b) | 0 | L1 0 / L2 3.9576 (thrown away) | 311 'L1 - Ground Floor' @0, 245423 'L2 - Second Floor' @12 | **311** / 4.659 | 311 / 0.328 | — | 0 err |
| 2026 | 0 | L1 0.0 / L2 4.2672 | 311 **'Level 1' @0**, 245423 **'Level 2' @14.0** | **245423 / 18.659** (=14+4.659) | 311 / 0.328 | 0.11 | 0 err / 0 warn |
| 2025 | 0 | same | 311 'Level 1' @0, 245423 'Level 2' @14.0 | 245423 / 18.659 | 311 / 0.328 | 0.12 | 0 err / 0 warn |
| 2024 | 0 | same | 311 'Level 1' @0, 245423 'Level 2' @14.0 | 245423 / 18.659 | 311 / 0.328 | 0.11 | 0 err / 0 warn |

- Stage D commit (2026): `replaced [[102,311],[102,245423]]`, `removed []`,
  ElemTable 3102 → 3102 (2025: 3316 → 3316), every other level datum
  (7 'GEN …') and every other record untouched (`reduce_law.element_diff`:
  `modified == {311:[102], 245423:[102]}`, added/removed empty — pinned in
  the test on all three bases); `verify_manipulated`: stamps ok, 0 CRC / ECC /
  walker errors, edited records decode clean as `Level`.
- `coverage.warnings == []` (was `['2 levels created; all equipment is placed
  on Level 1 …']`); `ignored_words == []` (before: 'floor to floor 14 ft' was
  silently swallowed by stopwords); `understood` gains `floor-to-floor
  height`, `storeys 'two storey'`, `equipment level 'on level 2' → L2
  [LP-1..LP-4]`; `defaults_applied` states "MSB: placed on Level 1 (the
  room's level …)".
- 3-storey prompt ("… two distribution panels on level 2 and four lighting
  panels on level 3"): exit 0, file delivered, `intent.levels` L1/L2/L3 @
  0 / 4.2672 / 8.5344, `prompt_coverage.not_built[0].reason` starts "storeys
  beyond 2 (base carries two story levels): Level 3 …", `build.degradations`
  carries "Level 3 (28 ft) NOT created: …", DP-1/2 on 245423 @ 18.659 ft,
  LP-1..4 on 245423 @ 32.659 ft (28 + 4.659), validator 0 errors.
- 1-storey prompt ("an electrical room with 6 panels"): stage D `written:
  false` (defaulted level, 0.03 s), datums untouched ('L1 - Ground Floor' /
  'L2 - Second Floor' @ 0 / 12), `Document.levels()` equal to main's output;
  `reduce_law.element_diff(main, branch)` differs in exactly the six loaded-
  family records in which two runs of MAIN differ from each other (pre-existing
  run-to-run nondeterminism, not this change) — the build path is unchanged
  for every level-silent job; validator 0 errors.
- Wall time (same venv, bundled 2026 base, after merging main incl. #292's
  schema memoization; alternating runs): DONE two-storey prompt main 3.75 /
  3.20 / 3.11 s vs branch 3.31 / 3.29 / 3.31 s wall (build 3.4/3.0/2.9 vs
  3.1/3.1/3.1); the per-stage clock puts stage D at **0.11–0.12 s** when it
  writes (one `Document.from_file` + one `commit_plans` + read-back) and
  **0.03 s** when it does not (level-silent jobs) — i.e. ≤ +0.12 s (≈3.5 %) on
  a job that names levels, ≈ +0.03 s otherwise. (First measurements before the
  main merge: 0.27–0.29 s of an 8.3 s job — the memoization shrank both.)

## Tests

- `tests/test_prompt_intent.py`: 10 → 16 (two-storey levels + per-item
  levels + both clauses consumed; 3 storeys recorded not clamped; room-level
  reference scopes room + gear; ordinal floors + tag list across 'and' + f2f
  sizes clear height; single-storey unchanged + level digit never a count;
  intent model carries levels). 16 passed.
- `tests/test_frontdoor.py`: +5 (stage D on 2026/2025/2024: binds to the two
  story datums only, L3 not built, record diff == the two datums,
  `verify_manipulated` clean, deterministic bytes; no-op when datums already
  match / level defaulted; e2e two-storey job: manifest levels, output datums
  'Level 1'/'Level 2' @ 0/14, LPs `m_assocLevelId` = L2 id at 14 + AFF, MSB +
  walls on L1, validator 0 errors, MANIFEST.md lines). Whole file 55 passed /
  4 skipped (sample-gated) after merging main (#186's rename/set-mark e2e kept
  on its own 1-panel fixture).
- Neighbours: `test_frontdoor_wallsolid.py`, `test_target2025.py`,
  `test_coldstart.py`, `test_bootstrap.py`, `test_plugin_sync.py`,
  `test_lazy_ifc_import.py`, `test_convert_combo.py` green (RVT_SKIP_LARGE=1).

## Findings (filed, not fixed here)

1. **#294 (P1, engine)** — a final partial page of 64,388–64,895 bytes
   encodes to a block exactly `PAGE_STRIDE` long (CRCIO's own geometry), and
   `verify_written` / `verify_manipulated` / `unframe_stream` mistake it for a
   full page → 1 false `ecc_mismatches` → stage W/E declare
   `structurally_valid: False` and drop content on ~0.8 % of writes. The
   validator (syndrome-based) and reopen accept the file. Found because the
   walls-only dummy-rep test build landed in the band once a second modify
   pass existed; P-then-P reproduces it without this stream's code. This PR
   does not touch the codec; the defaulted-level no-op keeps every
   level-silent job byte-identical to main.
2. **#295 (P2)** — create storeys beyond two (`new_level` + `new_plan_view`
   through the create path) and optional per-storey wall rings.
3. Not changed, noted: `set_level_elevation` moves the two datum-plane
   origins only (the certified M3 shape); the level's `m_freeEnd` /
   `m_bubbleEnd` / `m_refPointsForNewViews` z stay at the old elevation, as in
   the certified `M3_modify.rvt`. If desktop Revit draws the datum line at the
   stale z, that is a `manipulate.py` follow-up for its holder, not a
   front-door workaround.
4. `/simplify` (4 reviewers) — applied: ordinals / 'top floor' resolved to ints
   at scan time (no string sentinel through `PromptItem.level`), level refs
   always carry `tags` (bound ⇔ non-empty), one `_in_any` span-overlap helper,
   `double` in `_NUM_WORDS`, one lookbehind branch for 'on/at L2',
   `_layout_storey` extracted (layout body not re-indented), `FT_PER_M`
   imported not redefined, `story_levels` shared with `_pick_level`,
   `level_map(…, landed=)` assigned once + a `""` fallback entry, `resolve()`
   + `room_level_id` so build.py only threads values, empty intent ≡ defaulted
   (one outcome for "asserts nothing"). Declined with reason: skipping stage D
   entirely for defaulted levels (measured 0.03 s — not worth a special case);
   sharing the commit-summary / read-back scaffold with stage P and folding P+D
   into ONE modify pass (touches `project_info.py`, #281's module — worth a
   follow-up, see open questions); dropping `stage_equipment(level_id=)`
   (`rvt.convert.add_to_project` passes it); moving `BUILT_STOREYS` out of
   the parser (the DONE requires the `not_built` entry in prompt coverage,
   which is computed before any base is opened; the constant is documented as
   mirroring the pinned bases and stage D reports the base's real count).

## Fix round after the independent review of `67b61b8` (🛑 → addressed)

The review found two real regressions outside the DONE prompt; both fixed
with tests, plus its four nits:

1. **prompt → IFC addition dropped the storeys** (`ifc_out.py` still wrote ONE
   `IfcBuildingStorey` with raw, now level-relative, z → `route run --output
   ifc` put LP-1..4 on the ground floor; `--via ifc` delivered them on 311).
   Now `write_intent_ifc` writes one storey PER intent level, placed at the
   level's elevation, and contains every product under ITS level's storey with
   level-relative z (level-less objects: the storey nearest 0, z rebased on
   it). Round trip of the DONE prompt through our resolver: 2 storeys, levels
   L1/L2 @ 0/4.2672, LPs `level == 'L2'` z 1.42, MSB + shell on L1
   (`test_prompt_to_ifc_addition_keeps_every_storey`).
2. **Stage D on IFC intents sank / double-offset level-less rooms** (the `""`
   fallback was the LOWEST storey with its z: worked room + a 'Basement' @ −3 m
   → walls −9.84 ft, MSB −9.51; single storey @ +3 m → MSB 20.01 ft). Two
   changes: (a) `""` = the bound datum nearest z = 0 with NO z offset (main's
   `_pick_level` semantics — a level-less item carries world z); (b) the IFC
   resolver now assigns `Equipment.level` / `RoomShell.level` from spatial
   containment (`IfcRelContainedInSpatialStructure`, spaces walked up through
   `IfcRelAggregates`) and rebases `insertion_m[2]` / `elevation_m` /
   `mounting_height_m` / wall `base_m` on that storey — ONE contract for z on
   both routes. Measured through the full 2026 build: Basement variant → 311
   'Basement' @ −9.843, 245423 'Level 1' @ 0, walls base 0, MSB 0.328, LPs
   5.062 ft on 245423 (main's geometry); +3 m variant → 311 'Level 1' @ 9.843,
   walls base 9.843, MSB 10.171 ft (3.1 m, once); both 0 validator errors
   (`test_ifc_products_take_their_storey_with_level_relative_z`,
   `test_stage_d_on_ifc_storeys_never_sinks_or_double_offsets_the_room`). The
   earlier wording here ("gear at the correct absolute z" for the IFC lane) was
   wrong for non-zero storeys and is superseded by this paragraph.
3. Nits: a `default` level never renames OR moves its datum; the not-built
   reason states the one z rule (gear keeps the storey's own z, a room shell
   stands on the top datum — a wall's base is its datum, no base offset is
   authored); a level reference adjacent to the room phrase ("6 panels in an
   electrical room on the second floor", "a second floor electrical room")
   scopes the ROOM (`test_level_reference_adjacent_to_the_room_scopes_the_room`);
   `tests/test_prompt_intent.py` added to `tests/ci_shard.txt`.
4. **Round 2 (re-review of `bbf560d`): the convert lane under the same
   contract.** `rvt_to_ifc` fed the emitter EVERY Level of the source (9 on a
   tekton-authored file: 2 stories + 7 'GEN …' reference datums) with
   level-less gear, so `rvt → ifc` wrote 9 storeys and `ifc → rvt` of that
   file duplicated level names / sank the walls. Fixed on both sides:
   `write_intent_ifc` emits storeys only for levels whose `is_building_story`
   is not False, and only ONE storey when no object carries a level
   (level-blind callers keep main's shape); `rvt_to_ifc._extract_intent` sets
   `ExtractedEquipment.level` / `_Room.level` from `m_assocLevelId` when that
   datum is a building story and rebases z / wall `base_m` on it. Belt and
   braces: `bind_levels` never renames a datum to a name another Level of the
   document keeps (`rename_skipped`, surfaced as a degradation), and
   `_RE_STOREYS` no longer reads '4 level 2 lighting panels' as 4 storeys.
   Evidence: `convert_rvt_to_ifc(<pinned 2026 base>)` → 1 storey ('L1 -
   Ground Floor', no GEN datum); `convert_rvt_to_ifc(<built two-storey job>)`
   → 2 storeys 'Level 1'/'Level 2', LP-1..4 contained under 'Level 2' with z
   1.42, MSB + shell under 'Level 1'; that IFC through `frontdoor author
   --ifc` → 311 'Level 1' @ 0 / 245423 'Level 2' @ 14, unique level names,
   LPs on 245423 @ 18.659 ft, MSB 311 @ 0.328, walls @ 0, no degradations, 0
   validator errors (`test_rvt_to_ifc_of_the_pinned_base_writes_only_its_story_datum`,
   `test_rvt_ifc_rvt_round_trip_keeps_storeys_and_unique_level_names`,
   `test_a_datum_is_never_renamed_to_a_name_another_level_keeps`).
   `src/rvt/convert/rvt_to_ifc.py` is the convert stream's file — edited here
   on the tech lead's explicit instruction (round-2 review), one hunk + the
   `level` field.

## Round 3 (re-review of `79d15dd`): the z contract SETTLED — world z canonical, `level` an annotation

The reviewer found a THIRD consumer of the round-1 "level-relative z" model
(`merge_ifc` / `add_to_project.translate_model`, the `ifc+rvt → rvt` cell:
LP-1..4 landed on 311 @ 4.659 ft instead of 18.659). Rather than patch a
third consumer, the contract is now the one main always had: **every z in the
shared intent model is WORLD** (`Equipment.insertion_m[2]`, `elevation_m`,
`mounting_height_m`, `WallRun.base_m`, `RoomShell.clear['base_m']`), and
`Equipment.level` / `RoomShell.level` are ANNOTATIONS naming the storey. ONE
helper — `rvt.ifc.intent.level_elevation(levels, level)` /
`level_relative_z(z, levels, level)` — serves the two consumers that need a
level-relative z: `ifc_out` (local z under the containing storey = world −
storey elevation, uniformly for levelled and level-less objects) and stage E's
per-instance `z_above_level_ft` report (world − datum z). Consequences:
`_assign_storeys` only sets `level`; `prompt_to_intent` adds the level's
elevation to the layout's above-floor z (LP-1 `insertion_m[2]` = 4.2672 + 1.42
= 5.6872 m, walls `base_m` = the room level's elevation); stage E places every
instance at world z and only picks the DATUM from the level map; `rvt_to_ifc`
annotates `level` from `m_assocLevelId` without touching z; `merge_ifc`,
`add_to_project`, `roundtrip_table` are untouched and correct by default.
Reviewer's repro `route.py run --output rvt --ifc two.ifc --rvt <copy of
G_ABPD.rvt>` → MSB 0.328 ft, LP-1..4 **18.659 ft** (main's numbers);
`test_merge_ifc_of_a_two_storey_ifc_is_world_faithful` pins it. Nits folded:
`_RE_STOREYS` excludes only the singular `level <digit>` ('two storeys 14 ft
floor to floor' and '2 floors 4 m apart' count again); the round-2 round-trip
test carries the numpy gate; the rvt_to_ifc "story nearest 0 not at 0" case is
moot (ifc_out subtracts the CONTAINING storey's elevation from world z for
level-less gear too: world 10 ft under a storey @ 9.84 → local 0.16 → composes
back to 10).

### Audit — every reader of `insertion_m` / `elevation_m` / `base_m` / `mounting_height_m` under `src/` and `tools/` (`grep -rnE`), world or relative, and why it is right now

| Reader (file:line) | Field | Reads as | Why correct after this change |
|---|---|---|---|
| `src/rvt/ifc/intent.py:1083,1121,1135,1141,1150` (`_resolve_equipment_placement`) | insertion / elevation / mounting_height | WRITES world (composed placement × world-baked pts) | the producer of the contract; unchanged from main |
| `src/rvt/ifc/intent.py:1344,1405,1486,1505` (`_extract_room_shell` / `_close_room`) | wall `base_m`, `clear.base_m` | WRITES world (geometry z) | unchanged from main |
| `src/rvt/ifc/intent.py:953-968` (`Equipment.as_json`), `:1207` (`WallRun.as_json`) | all | serialises as stored = world | intent.json now documents world z + `level` |
| `src/rvt/ifc/intent.py:2172-2200` (`level_elevation` / `level_relative_z` / `_assign_storeys`) | insertion (read only by the helper's callers) | derives relative ON DEMAND; `_assign_storeys` no longer touches z | the one place a relative z is computed |
| `src/rvt/ifc/intent.py:2380-2386` (`_audit`), `:2471` (CLI print) | insertion x/y, elevation | x/y only / display | z not used |
| `src/rvt/ifc/intent.py:703-719` (`_collect_items`) | `base_m` | a 4×4 MATRIX named base_m, not a z | unrelated name collision |
| `src/rvt/frontdoor/prompt_intent.py:1202-1265` (`layout_room` / `_layout_storey`) | `PromptItem.insertion_m` | above-ITS-floor (layout-internal dataclass, not the shared model) | converted to world at `:1429-1440` before it enters `Equipment` |
| `src/rvt/frontdoor/prompt_intent.py:1429-1440,1466,1478` (`prompt_to_intent`) | insertion / elevation / mounting_height / base_m | WRITES world = layout z + `level_z[level]`; walls' base = room level elevation | matches the IFC producer; `test_two_storey_intent_model_carries_levels` |
| `src/rvt/frontdoor/prompt_intent.py:1519-1530` (audit), `:1889` (CLI) | insertion x/y | x/y only / display | z not used |
| `src/rvt/frontdoor/prompt_intent.py:1637` (`scene_brief`) | insertion | world → `position_m` (note says world) | Three.js places groups in world; a storey name rides alongside |
| `src/rvt/frontdoor/ifc_out.py:265,297` (`write_intent_ifc`) | wall base_m, insertion | world → LOCAL under the containing storey (`- zoff`, zoff = that storey's elevation) | the storey placement adds it back: chain composes to world; round-trip tests ×3 |
| `src/rvt/frontdoor/intent.py:119` (`summarize`) | insertion | world, rounded for the manifest | display |
| `tools/ifc_intent.py:852-856` (`stage_equipment`) | insertion | world → `position_ft` directly; datum from the level map only for `m_assocLevelId` + the `z_above_level_ft` report | LPs 18.659 on 245423, MSB 0.328 on 311; IFC-route inputs land where main put them |
| `tools/ifc_intent.py:1313-1314` (CLI print) | insertion, elevation | display | — |
| `src/rvt/convert/add_to_project.py:350-351` (`model_bbox_m`) | insertion x/y | plan bbox | z not used |
| `src/rvt/convert/add_to_project.py:384-388` (`translate_model`) | insertion, elevation | world + (dx, dy, target-level dz) | untouched; correct BECAUSE z is world again (`test_merge_ifc_of_a_two_storey_ifc_is_world_faithful`, `test_add_to_project_end_to_end`, `test_merge_ifc_end_to_end`) |
| `src/rvt/convert/merge_ifc.py:58` (via `translate_model`) | insertion | world | same as above; reviewer's repro = main's numbers |
| `src/rvt/convert/rvt_to_ifc.py:257,265,479` (`_extract_walls` / `_extract_equipment`) | base_m, insertion | WRITES world (curve z / `m_Trf` origin) | unchanged from main; `level` annotated separately at `:626-648` |
| `src/rvt/convert/rvt_to_ifc.py:710` (`roundtrip_table`) | insertion | world vs world (re-read IFC composes to world) | no false PARTIAL: both sides world (`test_convert_combo` green) |
| `tools/render_probes.py:511,522` | insertion | world → probe placement | research probes on single-storey intents; world = what they always got |
| `src/rvt/frontdoor/edit.py:179,313`, `tools/rvt_job.py:1044` | `elevation_m` of a `set-level` OP | an edit op's target elevation, not an intent field | unrelated |
| `src/rvt/genesis/residue_a.py:638,1703,1725`, `src/rvt/genesis/house_standard.py:261,1433` | `GRID_CONVENTION['elevation_m']`, `SITE['elevation_m']` | genesis constants | unrelated |
| `src/rvt/ifc/product_facts.py:575` | `storey_elevation_m` (a product-facts key) | the IFC storey's elevation | unrelated to instance z |

## Open questions

- Stages P and D are two open → commit → reopen passes over the same base;
  one shared "base edits" pass (one `Document.from_file`, one `commit_plans`)
  would save ≈ 0.1 s and one intermediate file.
- Binding is by elevation ORDER: an IFC with a basement re-purposes datum 311
  (and its 'L1 - Ground Floor' plan view) as the basement and 245423 as the
  ground floor. Correct as datums; the plan-view names are not renamed (view
  rename is not a certified shape yet).

## BRANCH STATE

- Files written: `src/rvt/frontdoor/prompt_intent.py`, `src/rvt/ifc/intent.py`,
  `src/rvt/frontdoor/levels.py` (new), `src/rvt/frontdoor/build.py`,
  `src/rvt/frontdoor/manifest.py`, `src/rvt/frontdoor/ifc_out.py`,
  `src/rvt/convert/rvt_to_ifc.py` (rounds 2–3: `level` annotation only), `tools/ifc_intent.py`, `tests/test_prompt_intent.py`,
  `tests/test_frontdoor.py`, `tests/ci_shard.txt`, this record; sync
  mirrors `plugin/lib/src/rvt/frontdoor/{prompt_intent,levels,build,manifest,ifc_out}.py`,
  `plugin/lib/src/rvt/ifc/intent.py`, `plugin/lib/tools/ifc_intent.py`,
  `plugin/skills/tekton-author/scripts/ifc_intent.py` (regenerated by
  `tools/sync_plugin.py`, never hand-edited).
- Gates: stream-local tests above; `tools/sync_plugin.py` run + `--check`
  clean; `plugin/scripts/validate_plugin.py` PASS; `check_portable_paths.py`
  ok; `tools/rvt_validate.py` 0 errors on all five cited outputs (2026 / 2025
  / 2024 two-storey, 3-storey, 1-storey); `/simplify` and `/verify` (front
  door per release + bare-unzip `go author`) before the final commit — results
  in the PR body.
- Staged vs shipped: no viewer batch (level rename / re-elevate is the
  certified M3 shape; placed instances remain the open cell and are stamped
  as before). No certification claim.
- Follow-ups: #294, #295.
