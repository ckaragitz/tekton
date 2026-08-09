# geo-site-determinism — deterministic `GeoSite.m_sharedCoordGUID` (issue #9)

Stream record for issue #9 ("famgen determinism: replace uuid4 in
skeleton.new_geo_site with a deterministic uuid5 default"), branch
`cam/9-famgen-uuid5`.

## What was built

* `src/rvt/genesis/skeleton.py`
  * `our_guid(purpose, *parts)` — the generic deterministic-GUID helper at
    the lowest genesis layer: `uuid5(uuid5(NAMESPACE_DNS,
    "rvt-writer.gen.<purpose>"), "p1|p2|…")`, i.e. OUR namespace derived
    from the product author placeholder — the same derivation
    `residue_b._stable_guid` ('house-standard') and
    `residue_b2.HOUSE_ASSET_LIBRARY_GUID` hand-roll one layer up.  No donor
    GUID is material.
  * `new_geo_site(...)`: `m_sharedCoordGUID` now defaults to
    `our_guid("geo-site", elem_id, name, lat, lon, tz)` instead of
    `uuid.uuid4()`.  An explicit `shared_coord_guid=` is still honoured
    verbatim (byte-exact specimen test unchanged).
* `src/rvt/genesis/house_standard.py` — the two call sites keep passing no
  GUID (one-line comment): the default is now deterministic per site
  identity, and `y2024_b.context_y2024`'s `_pinned_geo_site` wrapper (which
  only fills a *missing* GUID) keeps overriding it inside the 2024 chain, so
  the certified 2024 lineage's frozen GUIDs are untouched.
* `tests/test_geo_site_determinism.py` — 5 tests (below), added to
  `tests/ci_shard.txt` (fresh-clone green, 0.6 s) so CI enforces the guard.

Note on territory: the issue names `src/rvt/famgen/skeleton.py` ~line 999,
but `new_geo_site` lives in `src/rvt/**genesis**/skeleton.py:999` (the line
number and the `house_standard` call site match genesis, and famgen has no
GeoSite constructor).  The change was made there; nothing under
`src/rvt/famgen/` needed touching.

## Evidence

Matched pass/fail pair, fresh cloud clone (no `samples/`, no `extracted/`),
`house_standard.build_catalog(1_500_000)` built twice and every record's
seq-102 body encoded with the schema codec (234 records):

| code | md5 of all bodies equal across 2 builds | records differing |
|---|---|---|
| `main` (`uuid4` default) | **no** | exactly `[(1500186, GeoSite), (1500187, GeoSite)]` |
| this branch (`uuid5` default) | **yes** (`d3f38677…` both runs) | `[]` |

Tests:

* `tests/test_geo_site_determinism.py` → **5 passed** (same inputs → same
  GUID == the documented derivation; 4 distinct site identities → 4
  distinct GUIDs; GUID is version 5 — every corpus GeoSite GUID is a random
  v4, so ours can never coincide with a donor value; explicit GUID honoured;
  two `build_catalog` runs encode byte-identically record-by-record, the
  Internal/Project pair distinct).
* `tests/test_genesis_skeleton.py tests/test_house_standard.py tests/test_y2024.py tests/test_residue_b.py tests/test_plugin_sync.py`
  (+ the new file) → 96 passed / 43 skipped (corpus-gated skips, expected in a fresh clone).
* `tests/test_famgen_skeleton.py tests/test_famgen_adoc.py` → 8 passed / 25 skipped.
* CI shard (`tests/ci_shard.txt`, `RVT_SKIP_LARGE=1`, now incl. the new
  file) → 134 passed / 23 skipped in 24.5 s.
* `tools/sync_plugin.py` run (mirrors regenerated), `--check` clean;
  `plugin/scripts/validate_plugin.py` OK; `tools/dev/check_portable_paths.py` OK.

End-to-end at the file surface (dev-only scratch probe, nothing staged, no
certification claim): `tools/genesis_substitute_v3.py --base
plugin/assets/genesis/G_ABPD.rvt --only Y1,…,Y8 --no-ledger
--allow-uncertified --out-dir <scratch>` (the pinned plugin copy of the
certified 2026 base is not path-listed in the ledger, hence the override;
29 s for the whole chain in a fresh clone) run twice per code state:

| code | `Y8.rvt` md5, build 1 / build 2 | GeoSite 21747 / 111427 GUIDs |
|---|---|---|
| `main` | `ed8dcba6…` / `ecf0d58a…` — **differ** | random v4, different each build |
| this branch | `61699cbc…` / `61699cbc…` — **identical** | `ed90a9f9-32cf-5493-…` / `cdb3158b-798c-5166-…` (v5), same both builds |

Y1..Y7 were byte-identical across builds in both states (Y8 is the only
rung that rebuilds the datum).  `tools/rvt_validate.py <scratch>/Y8.rvt`
→ 0 errors / 1 warning (the known DataStorage ES-blob decoder gap).
`python -m rvt.genesis.house_standard` twice → rc 0, 234/234 round-trip
byte-exact, 0 dangling, stdout identical.  Probes: `shared_coord_guid=""`
falls back to the deterministic default (same truthiness rule as before);
`latitude_rad=0` (int) and `0.0` give the same GUID (floats normalised
before hashing).

(The bundled `/verify` skill suggests persisting this recipe as
`.claude/skills/verify/SKILL.md`; not done — `CLAUDE.md` §3b keeps
`.claude/skills/` intentionally absent, so the recipe lives here.)

## Findings

* The GUID material is the site's own identity (element id, symbol name,
  lat/long/tz).  Consequence worth knowing: renumbering the catalog
  (`start_id`) or moving the site changes the GUID — by design (a different
  site/document is a different shared-coordinates identity), and still
  deterministic for a given intent.
* `y2024_b._pinned_geo_site` is now redundant for *determinism* but still
  load-bearing for *lineage identity* (it reproduces the exact GUIDs baked
  into the certified `G_ABPD_2024` chain).  Left as is (outside territory);
  retiring it would be a deliberate 2024-chain rebase, not a cleanup.  Its
  comment ("mints uuid4 per call … the ONE nondeterminism") is now stale,
  and `residue_b._stable_guid` could delegate to `skeleton.our_guid`
  byte-identically — both filed as one follow-up task issue (`Refs #9`).

## Open questions

* None blocking.  The other `uuid4` defaults in `genesis/skeleton.py`
  (`build_tables`: document / episode / workset GUIDs) are per-document
  identity minted once per build and are passed explicitly by the chain
  drivers; they were not implicated by the y2024 determinism re-run and are
  out of this issue's scope.

## BRANCH STATE

* Branch `cam/9-famgen-uuid5` from `origin/main` @ `af59d26`.
* Files written: `src/rvt/genesis/skeleton.py`, `src/rvt/genesis/house_standard.py`
  (comment only), `tests/test_geo_site_determinism.py`, `tests/ci_shard.txt`
  (+1 line), `docs/inbox/geo-site-determinism.md`, regenerated mirrors
  `plugin/lib/src/rvt/genesis/{skeleton,house_standard}.py`.
* Gates: stream-local tests green (counts above); sync `--check` clean;
  validate_plugin OK; portable paths OK; CI shard green locally.
* Staged vs shipped: nothing staged for the viewer; no output files; ships
  as a PR closing #9.
