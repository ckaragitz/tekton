# frontdoor-manifest-pin — `manifest.json` `base.pin` names the slot the run resolved (#264)

## eng #264 — 2026-08-10

Stream: front door (`src/rvt/frontdoor/`), issue #264 (Refs #131, PG1 lineage honesty).
Territory used: `src/rvt/frontdoor/manifest.py`, `src/rvt/frontdoor/__init__.py` (one helper),
`tests/test_frontdoor_manifest_pin.py` (new), `tests/ci_shard.d/264-manifest-pin-slot.txt`
(new), the two generated mirrors under `plugin/lib/src/rvt/frontdoor/`, this record.
NOT touched: `src/rvt/frontdoor/base.py` (hot), `tools/probe_batch.py`, `tools/frontdoor.py`,
`src/rvt/versions/`, `docs/coverage/viewer-certified.json`, `KNOWLEDGE.md`, `TRACKER.md`.

## Why

`build_manifest` wrote `m["base"]["pin"] = PIN.as_json()` — always the DEFAULT (2026) record —
so a `--target-version 2025` (or 2024) run recorded the 2025 base's path + sha256 under `base`
and the 2026 pin under `base.pin`: `base.sha256 6242c3aa… != base.pin.sha256 84173b89…`,
`base.pin.relpath = …/subst_k4/compose/G_ABPD.rvt`, and `base.certification.entry` (the 2025
ledger entry) disagreed with `base.pin.certification.entry` (the 2026 one). Anyone reading the
manifest for lineage got the wrong certified base; `tools/probe_batch.py frontdoor_entries` had to
match the digest against every release slot to work around it (#131 record § Findings).

## What was built

* `rvt.frontdoor.manifest.resolved_pin(base, release=None, *, pin=PIN)` — the pin block for the
  slot the run's base answers to. Slot choice: the registry slot whose pinned sha256 IS
  `base.sha256` (every pinned resolution; also a `--base` copy that happens to be certified
  bytes); failing that, `release`; failing that (or for an unknown / unpinned year), the registry
  default. The default release returns `PIN.as_json()` byte-for-byte (2026 unchanged); any other
  slot overrides `id`, `relpath`, `sha256`, `bytes`, `lineage`, `revit_release`, `certification`
  from `PIN.release_slot(year)`; `residue_disclosure` and `specimen_ancestor` (registry-wide) ride
  along. `build_manifest` writes `"pin": resolved_pin(base, _version_release(version))`, where
  `_version_release` reads the front door's own version block: `output_release` (what was
  produced), else `requested` (a refused run produced nothing but still names what it was resolved
  against), else None.
* `MANIFEST.md` base section: the per-release slots' certification carries `ledger` / `entry` /
  `required` but no prose `proves` / `verdict`, so 2025/2024 manifests printed an empty
  `- certification:` + `- verdict:`. They now cite the ledger entry
  (`` - certification: `docs/coverage/viewer-certified.json` entry `…/G_ABPD_2025.rvt` — <required> ``);
  a slot with `proves`/`verdict` (2026) renders exactly as before.
* `rvt.frontdoor._explicit_or_pin` (the stand-in `ResolvedBase` a manifest gets when resolution
  failed) names the target release's own slot path (`PIN.candidate_paths(relpath=slot)[0]`, the
  same "pinned-repo" definition `resolve_base` uses) when the registry has one, so even a refused
  `--target-version 2025` manifest's `base.path` and `base.pin` agree.
* `/simplify` pass (4 angles): applied — `resolved_pin` takes the release as an int (the version
  block is read in one place, `_version_release`), early-return structure, one `update` for the
  slot keys, `_explicit_or_pin` reuses `candidate_paths`, test constants `DEFAULT_YEAR` /
  `OTHER_YEARS`. Skipped (hot file, follow-ups): the deeper home is `ResolvedBase` carrying the
  matched slot/year and a `GenesisPin.slot_for_digest` / `slot_as_json` so `manifest.py`,
  `probe_batch.frontdoor_entries` and `census.pin_file` stop re-deriving slot identity by digest
  — folded into #439's territory note below.
* No accessor was missing on the hot file: `PIN.release_years()` / `PIN.release_slot(year)`
  sufficed. A nicer home for the slot→JSON mapping would be `GenesisPin` itself; offered as a
  patch, not applied (hot file):

  ```python
  # src/rvt/frontdoor/base.py, class GenesisPin  (optional follow-up, not in this PR)
  def slot_as_json(self, year: int) -> Dict[str, Any]:
      """as_json() for one release slot (the default release == as_json())."""
      out, slot = self.as_json(), self.release_slot(int(year))
      if int(year) == int(self.revit_release) or not (slot or {}).get("sha256"):
          return out
      out.update({k: slot.get(k) for k in ("id", "relpath", "sha256", "bytes")},
                 revit_release=str(int(year)), certification=dict(slot.get("certification") or {}))
      if slot.get("lineage"):
          out["lineage"] = slot["lineage"]
      return out
  ```

## Evidence (this cloud session = a fresh clone: no `samples/`, bases from `plugin/assets/genesis`)

Command: `tools/frontdoor.py author --prompt "a room with four walls" --target-version Y --out <tmp>/pbY --json`,
run on `origin/main` @ f05db8b (before) and on this branch (after), Y ∈ {2026, 2025, 2024}, plus
no `--target-version`.

| Y | `base.path` (basename) | `base.sha256` | `base.pin.relpath` (after) | `base.pin.sha256 == base.sha256` | `base.pin.certification == base.certification` |
|---|---|---|---|---|---|
| 2026 | `G_ABPD.rvt` | `84173b8960b8…` | `experiments/genesis/subst_k4/compose/G_ABPD.rvt` | True (was True) | True |
| 2025 | `G_ABPD_2025.rvt` | `6242c3aaccf8…` | `experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt` (was `…/subst_k4/compose/G_ABPD.rvt`) | True (was False) | True (was False) |
| 2024 | `G_ABPD_2024.rvt` | `e4a40671d8b6…` | `experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt` (was `…/subst_k4/compose/G_ABPD.rvt`) | True (was False) | True (was False) |
| none | `G_ABPD.rvt` | `84173b8960b8…` | `experiments/genesis/subst_k4/compose/G_ABPD.rvt` | True | True |

* `manifest.json` before→after diff (paths normalised, `generated_at` dropped): **2026: 10 lines,
  all stage timings / `seconds`**; 2025: the `base.pin` block only (+ timings); 2024: same.
* `MANIFEST.md` before→after: 2026 identical but the timestamp line; 2025/2024: the empty
  `- certification:` / `- verdict:` pair replaced by the one ledger-entry line.
* Built files unchanged: `prompt_room.rvt` sha256 before == after for all three
  (`45f1795250f529e9…` / `c589e33275daa235…` / `1a97ab56bdb44508…`); `tools/rvt_validate.py`
  on the three after-files: `ok: true`, errors 0/0/0 (warnings 1/0/0 — the known DataStorage
  decoder-gap warning on 2026).
* `tools/probe_batch.py check <tmp>/pb2025/prompt_room.rvt` → `base = experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt [certified; pinned base recognised by sha256]`, ADMISSIBLE
  (unchanged behaviour: the all-slots match still wins when pins are present); with pins
  disabled (`frontdoor_entries(manifest, pins=())`, the new test) the declaration now comes
  straight from `base.pin` and is the 2025 relpath — DONE bullet 3.
* Edit route: `author --rvt <pb2025>/prompt_room.rvt --edit "delete <wall>"` → its manifest's
  `base` block is `{note, input_file, input_is_autodesk_sample}` — it carries no `pin`, so there is
  nothing to make consistent there (input release 2025 detected, status `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`).
* Explicit copy of a certified slot: `--base plugin/assets/genesis/G_ABPD_2025.rvt --target-version 2025`
  → `base.pin` names the 2025 slot and `base.pin.sha256 == base.sha256` (digest rule), but
  `base.pinned = false` / "not the pinned genesis base" warning — that judgement is `base.py`'s
  explicit branch comparing only against the default sha; filed as #439 (hot file), not fixed here.

`/verify` (drove the real surfaces on the final tree):
* `tools/frontdoor.py author --prompt "an electrical room with 6 panels" --target-version 2025 --out out/verify/p25 --json`
  → rc 0, `PROOF-ONLY (self-checks PASS …)`, `base.path …/G_ABPD_2025.rvt`, `base.pin` = `G_ABPD_2025`
  slot, `pin.sha256 == base.sha256`, `pin.certification == base.certification`; same for 2024
  (`G_ABPD_2024`); `tools/rvt_validate.py out/verify/p25/prompt_room.rvt` VALID, errors 0;
  `tools/provenance.py … --baseline all --streams` picks `baseline_kind pinned-composed-genesis`
  (`G_ABPD_2025.rvt`, id overlap 0.9656), the one finding is the pre-existing
  `identity:central_episode_guid identity-not-ours` (G2 / #19, unchanged bytes).
* Probes: `--base plugin/assets/genesis/G_ABPD.rvt --target-version 2025` (our default via a
  path → the slot wins, #24) → base `G_ABPD_2025.rvt pinned-bundled pinned=True`, pin = 2025 slot,
  sha equal; `--target-version 2019` → `fallback`, output 2026, base `G_ABPD.rvt`, pin = default,
  sha equal, the honest line printed.
* Bare unzip of the rebuilt `tekton-plugin.zip`, system `python3`:
  `skills/tekton-author/scripts/_bootstrap.py go author --prompt "a room with four walls" --target-version 2025 --out out/j25 --json`
  → `tekton: READY | … | genesis verified`, `ready: true`, job ok in 1.4 s, manifest `base` =
  `<unzip>/assets/genesis/G_ABPD_2025.rvt pinned-bundled`, `base.pin` = 2025 slot, sha + cert equal.

Gates: `tests/test_frontdoor_manifest_pin.py` 9 passed; neighbours + plugin surface
`tests/test_frontdoor.py tests/test_probe_batch.py tests/test_frontdoor_manifest_pin.py tests/test_shard_list.py tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py`
173 passed / 17 skipped (corpus-absent + "no bare python3 with numpy" skips); `tools/sync_plugin.py`
synced 2 files, `--check` clean, `plugin/scripts/validate_plugin.py` PASS (25 assertions),
`tools/dev/check_portable_paths.py` ok (2897 paths); whole merged CI shard: see BRANCH STATE.

## Findings / follow-ups

* #439 (filed, `hot-file`): `resolve_base(--base X, target_release=N)` should recognise X as
  pinned/certified when its digest is slot N's pin (today only the default pin counts). The same
  PR is the natural place to let `ResolvedBase` carry the matched slot / release and to give
  `GenesisPin` a `slot_for_digest(sha)` + `slot_as_json(year)` (patch above), after which
  `resolved_pin` here shrinks to a lookup and `tools/probe_batch.py`'s "still embeds the DEFAULT
  pin" comment + all-slots scan can retire.
* The per-release slots in `assets/genesis_base.json` cite `ledger` + `entry` + `required` but no
  `proves` / `verdict` prose like the default record; the MD now degrades gracefully, but the
  registry could carry the verdict citation (genesis-audit VERDICTS #28 for the 2025/2024 lineage)
  — registry data, front-door territory, trivially small; not done here to keep the PR to the DONE.

## BRANCH STATE

* Branch `cam/264-manifest-pin-slot` from `origin/main` @ f05db8b. Files: `src/rvt/frontdoor/manifest.py`
  (`resolved_pin`, `build_manifest` uses it, MD certification line), `src/rvt/frontdoor/__init__.py`
  (`_explicit_or_pin` names the target slot), their two `plugin/lib/` mirrors (via `tools/sync_plugin.py`),
  `tests/test_frontdoor_manifest_pin.py`, `tests/ci_shard.d/264-manifest-pin-slot.txt`, this record.
* Gates green as listed under Evidence; whole merged CI shard on the final tree
  (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`,
  72 files incl. the new drop-in): **1473 passed, 165 skipped, 2 xfailed in 325.79 s**
  (pre-`/simplify` run: 1471 passed / 165 skipped / 2 xfailed — the +2 are this file's added tests).
* Staged: nothing (no certification claim). Shipped: the change + tests + record via the PR that closes #264.
