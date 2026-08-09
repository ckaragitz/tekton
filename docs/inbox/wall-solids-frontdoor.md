# wall-solids-frontdoor — front-door created walls carry authored seq-103 solids (issue #144)

Stream: `wall-solids-frontdoor` · issue #144 (P1, PG6 / RENDER) · branch `cam/144-wall-solids-frontdoor`
· session `eng144` · viewer round: STAGED as batches 57/58/59, human upload tracked in #145.

## What was built

The front door's stage W (`tools/ifc_intent.py::stage_walls`, reused by
`rvt.frontdoor.build`) used to commit every created `SWall` with a 2-byte
`SerializedDummy` seq-103 record, so a prompt/IFC-built room opened in Autodesk's
cloud viewer as datum lines with invisible walls (KNOWLEDGE "LOAD IS NOT RENDER").
Now each created wall carries an **authored six-face `GElement` B-rep** built by
`rvt.render.brep.wall_rep_from_object` — the module behind the two RENDER-certified
ledger entries `experiments/render/RSOLID_walls_A_solid.rvt` and
`experiments/render/g12/W1_gabpd_wall_solid.rvt` — installed as `NewElement.rep`
**before** `Document.serialize`, so the normal `commit_new_elements` path writes it
(no post-hoc `substitute_elements` rewrite, `rvt/mutate.py` untouched).

* `src/rvt/render/brep.py`: `bake_planned_wall(doc, el, *, wall_type_id, height, side_material_id=None)`
  (create-time sibling of `wallgeom.bake_planned_wall`) + `WALL_REPS`; `tools/ifc_intent.py`:
  `stage_walls(..., wall_rep='dummy'|'solid')` dispatches to it in one line. Recipe = W1's exactly: root category `-1`, side/top/bottom material = the wall
  type's own layer `MaterialElem` when it exists in the document
  (`rvt.render.wallgeom.layer_material`, else `-1`), end caps `-1`, no ref-plane
  sub-graphics, face/edge tags read from the wall's own `BaseWallGStep` history
  (`tags.source == 'history'` on the constructed template). Per-wall measured `rep` facts and
  `rec['wall_rep']` land in the stage record; the stage note states mechanism only. An
  unknown `wall_rep` raises (API misuse). The low-level default stays `'dummy'` so the research probe builders
  (`tools/render_probes.py`, `ifc_intent.py room`) keep producing byte-identical files.
* `src/rvt/frontdoor/build.py`: `BuildOptions.wall_rep` (default `default_wall_rep()`
  = `'solid'` unless env `RVT_WALL_REP=dummy`; unknown values → `'solid'`), threaded
  into both `stage_walls` calls (single/stamp and split-strict shell); `_slim_stage`
  keeps `wall_rep` + per-wall `rep`; `elements_created[].rep`. **No `tools/frontdoor.py`
  flag** (hot file untouched) and no `AuthorRequest` field — the env var is the opt-out.
* `src/rvt/frontdoor/manifest.py`: `honesty.tiers.load_vs_render` follows the rep the
  created wall elements actually carry (`LOAD_VS_RENDER['solid'|'dummy']`, the ONE home of
  the certification-state sentence); the solid wording says the
  RENDER mechanism is certified *as a shape* and that **this exact output is
  uncertified until its own viewer batch passes**. `_honesty(None, …)` still works.
* `tests/test_frontdoor_wallsolid.py` (new, fresh-clone, in `tests/ci_shard.txt`).
* Plugin mirrors re-synced (`plugin/lib/src/rvt/frontdoor/{build,manifest}.py`, `plugin/lib/src/rvt/render/brep.py`,
  `plugin/lib/tools/ifc_intent.py`, `plugin/skills/tekton-author/scripts/ifc_intent.py`).

Why `brep` and not `wallgeom.bake_planned_wall` (the second, native-exact
constructor, certified once as `wall_baked_min` on ZA_deep): W1 is the entry
certified **on the pinned composed base itself** with this exact call shape, it needs
no seq-102 bookkeeping normalization (W1 = `mode='min'` clean-up + rep only), and
#144 names it. `wallgeom` stays the independent A/B lens — its `audit` reads our
output back clean (below).

## Evidence (fresh cloud clone, no samples/; numbers, not adjectives)

Reproduction of the bug on `main` @ a5a853f: `frontdoor author --prompt "a room with four walls"`
→ `python -m rvt.render.inspect out/w0/prompt_room.rvt --class SWall`:
`4 elements: 0 carry baked/referenced geometry, 4 do not; seq-103 bytes 8; kinds: dummy=4`.

After the change, `frontdoor author --prompt "an electrical room 30 by 20 ft" --stages WV --target-version V`:

| V | new SWall ids | wall type (thickness ft) | side material | inspect | rvt_validate | census / identity | ElemTable | build s |
|---|---|---|---|---|---|---|---|---|
| 2026 | 1472525–528 | GEN Wall - Interior Partition 121mm (0.397) | 51455 `GEN Metal Stud Framing` | `brep=4`, 4/4 baked, drawable_3d, 1 solid / 6 faces / 12 edges, 3060 B each | VALID, 0 errors, 1 warning (the base's own DataStorage ES-blob decoder gap) | save_units 1, familymgr 9 / PASS (`rvt-writer`) | 3102→3106 | 1.6 |
| 2025 | 1472449–452 | CL_W1 (0.9186) | 600660 | same | VALID, 0 errors, 0 warnings | same / PASS | 3316→3320 | 1.5 |
| 2024 | 1472510–513 | CL_W1 (0.9186) | 600660 | same | VALID, 0 errors, 0 warnings | same / PASS | 3278→3282 | 1.6 |

* Rep bBox = location line ± half type thickness × [0, 12] ft **and** equals the header
  `m_pBBox` on all 12 walls (asserted in the test).
* `python -m rvt.render.wallgeom audit out/ws2026/prompt_room.rvt` (the other
  constructor's read-back): `all_baked True`; every wall `GElement`, `decode_clean True`,
  `audit []`, `inspect {kind: brep, n_faces 6, n_edges 12, drawable_3d True}`.
* Opt-out is byte-exact: `RVT_WALL_REP=dummy frontdoor author --prompt "a room with four walls"`
  → sha256 `f924e5ff…59fcb8` == the pre-change build of the same prompt on `main`.
* Determinism: two default (solid) builds of the same prompt → identical sha256
  `1e07e23a…c414e`; zero differing CFB streams.
* Provenance vs the pinned base (`tools/provenance.py out/ws2026/prompt_room.rvt --baseline plugin/assets/genesis/G_ABPD.rvt --streams`):
  `created_elements` = exactly the 4 SWalls, `modified_elements = []`, streams 99.12 %
  byte-identical to the base + 0.12 % ours. (`--baseline all` has no sample baselines in a
  fresh clone → owner-machine; the instrument's "autodesk-sample" label for whatever
  baseline it is handed is the pre-existing framing noted in docs/product/REQUIREMENTS.md.)
* Bare surface (steer #108): unzip `tekton-plugin.zip` to a temp dir, `env -i … python3
  skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room 30 by 20 ft" --stages WV --out out/j1 --json`
  → `go.ready True`, preflight 0.042 s, job 1.42 s, total **1.46 s**, `wall_rep solid` 4/4,
  VALID, self_checks_ok. Latency before/after for the walls-only prompt job in the repo:
  2.09 s cold / ~1.5 s warm before → 1.56–1.73 s after (the bake is pure dict
  construction; +12,232 B of seq-103 payload per file). No regression.

Deltas vs the certified W1 file, named so the viewer round reads as single variables:
(a) 4 walls in a ring instead of 1 free wall (RSOLID_A certified 4 solid walls in a ring);
(b) on 2026 the side material is the type's own layer material 51455 instead of W1's
hard-coded 600660 (both `MaterialElem`s exist in G_ABPD; on 2025/2024 it resolves to
600660); (c) the wall object is the product's CONSTRUCTED `swall_template` clone (the
LOAD-certified ROOM2025_walls shape) rather than an R5 clone, hence 121 mm on 2026.

## Gates run

* `pytest tests/test_frontdoor_wallsolid.py` → **4 passed** (6.2 s after the /simplify pass; 11.4 s before).
* `pytest tests/test_frontdoor.py tests/test_router.py tests/test_render_wallgeom.py tests/test_render_inspect.py tests/test_frontdoor_standalone.py tests/test_probe_batch.py tests/test_ifc_intent.py`
  → **204 passed, 28 skipped** (57.9 s; skips = corpus/ladder-gated cases, expected in a fresh clone).
  Caveat found while gating: once `probe_batch stage` has copied binaries into
  `experiments/acceptance/`, `rvt.frontdoor.matrix.audit()` treats THIS checkout as an owner
  machine (`_experiment_binaries_present()` = any `experiments/acceptance/*.rvt`) and the 38
  ledger binaries a fresh clone never has turn HARD → 4 `test_router.py` reds locally
  (73 passed / 4 skipped again with the staged copies moved aside; CI unaffected). Filed as a
  process follow-up (fresh-clone staging, #263, should not redden the stager's own audit).
* `/simplify` (4 review lenses) applied: bake moved into the engine, no note surgery, one
  wording home, evidence-keyed honesty, leaner test; outputs sha-identical before/after on
  2026 (`1e07e23a…`), dummy (`f924e5ff…`), 2025 (`86b7ac9a…`), 2024 (`cdec67b3…`).
* `pytest tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py` → **26 passed, 4 skipped**.
* `tools/sync_plugin.py` → synced 4 files, deny-audit clean, validation passed, zip rebuilt;
  `--check` → in sync. `plugin/scripts/validate_plugin.py` → PASS (24 assertions).
  `tools/dev/check_portable_paths.py` → ok.
* `/verify` (this repo's skill) driven: front door ×3 releases, `rvt_validate`, `rvt_analyze`
  (release 2025, identity ours, coherence OK), provenance vs pinned base, bare-unzip `go`.

## Viewer round — STAGED, not uploaded (hard rule 4)

`tools/probe_batch.py check` → ADMISSIBLE (each base recognised as the certified pin by
sha256 via the front-door `manifest.json` beside the probe). `stage`, one batch per
release so each carries its own byte-identical control:

| batch | control (read FIRST) | md5 | probe | md5 |
|---|---|---|---|---|
| `experiments/acceptance/batch_57.json` | `CTRL_G_ABPD_b57.rvt` (== pin sha256 84173b89…) | 1f1ff65b… | `experiments/wall_solids_frontdoor/2026/WSOLID2026_walls.rvt` | 4ef49f8b… |
| `experiments/acceptance/batch_58.json` | `CTRL_G_ABPD_2025_b58.rvt` (== 6242c3aa…) | 47008773… | `experiments/wall_solids_frontdoor/2025/WSOLID2025_walls.rvt` | 54188947… |
| `experiments/acceptance/batch_59.json` | `CTRL_G_ABPD_2024_b59.rvt` (== e4a40671…) | 37979615… | `experiments/wall_solids_frontdoor/2024/WSOLID2024_walls.rvt` | 4e8c99c2… |

Rebuild the probes (binaries are git-ignored) with
`.venv/bin/python tools/frontdoor.py author --prompt "an electrical room 30 by 20 ft" --stages WV --target-version V --stem WSOLIDV_walls --out experiments/wall_solids_frontdoor/V`
then `tools/probe_batch.py stage <that .rvt>`. Reading matrix per batch: control FAIL →
VOID; control PASS + probe LOAD-PASS + 4 walls drawn in {3D} → the front-door solid-wall
shape LOADS and RENDERS on that release (ledger entry by the uploader, hot-file PR);
probe LOAD-PASS but empty model → geometry not drawn: A/B against W1 on the three named
deltas (material first: rebuild with `RVT_WALL_REP` unset after pinning side material to
600660 in a probe-only script); probe LOAD-FAIL while the dummy twin
(`RVT_WALL_REP=dummy`, = the LOAD-certified shape) passes → the bake trips the audit on
the constructed template: bisect rep-only vs W1's R5 clone. STOP AT READY — #145 carries
the upload and the verdict PR.

## Findings

* The `NewElement.rep` hook made this a create-time change with zero writer edits; the
  encoder serializes the GElement tree against each target's own schema inside
  `release_build_context`, so 2025/2024 needed no port work (12/12 walls decode clean
  under their own release).
* On the 2026 pin the constructed template yields the type's true 121 mm thickness where
  W1's R5 clone carried 280 mm ref-face offsets on the same type 600634 — the product
  output is the more self-consistent file (rep bBox == header bBox == type thickness).

## Open questions / follow-ups

* Viewer verdicts for batches 57–59 → #145 (needs-viewer; comment posted there).
* #140 (opt-in `bake_walls`, default OFF) is superseded in mechanism by this issue's
  default-ON-with-opt-out per #144's DONE; left for the tech lead to close or narrow.
* `plugin/skills/tekton-author/references/GENESIS-BASE.md:75` still says walls
  "historically carried a SerializedDummy rep" — accurate as history; a wording refresh
  can ride the next tekton-author reference edit (not a hot file, but outside this territory).

## BRANCH STATE

* Branch `cam/144-wall-solids-frontdoor` from `main` @ a5a853f; commits: engine change +
  test + shard + mirrors; staging declarations + this record; probes' intent.json; the
  /simplify pass (bake into `rvt.render.brep`).
* Files written: `src/rvt/render/brep.py`, `tools/ifc_intent.py`, `src/rvt/frontdoor/build.py`,
  `src/rvt/frontdoor/manifest.py`, `tests/test_frontdoor_wallsolid.py`, `tests/ci_shard.txt`,
  plugin mirrors (5), `experiments/wall_solids_frontdoor/{2026,2025,2024}/{manifest.json,MANIFEST.md,intent.json}`,
  `experiments/acceptance/batch_{57,58,59}.json`, `docs/inbox/wall-solids-frontdoor.md`,
  `docs/inbox/render-emit.md` (own header, pointer only).
* Staged, not shipped: batches 57/58/59 READY in `experiments/acceptance/` (binaries local,
  reproducible by the command above). Nothing recorded in the ledger or genesis-audit.
* Hot files untouched: `tools/frontdoor.py`, `src/rvt/frontdoor/base.py`, `src/rvt/versions/`,
  `docs/coverage/viewer-certified.json`, `KNOWLEDGE.md`, `TRACKER.md`.
