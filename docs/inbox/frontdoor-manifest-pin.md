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

---

## eng #439 — 2026-08-10: `resolve_base`'s explicit / env branches learn the slot registry

Stream: front door, issue #439 (`hot-file`: `src/rvt/frontdoor/base.py`; Refs #264, PG1). Territory
used: `src/rvt/frontdoor/base.py` (one private helper + the explicit and env branches of
`resolve_base`, nothing else), `tools/probe_batch.py` (the `frontdoor_entries` docstring only),
their three generated mirrors (`plugin/lib/src/rvt/frontdoor/base.py`, `plugin/lib/tools/probe_batch.py`,
`plugin/skills/tekton-author/scripts/probe_batch.py` via `tools/sync_plugin.py`),
`tests/test_frontdoor_manifest_pin.py` (a dated section appended; already in the CI shard via
`tests/ci_shard.d/264-manifest-pin-slot.txt`), this record section. NOT touched:
`src/rvt/frontdoor/__init__.py` / `tests/test_frontdoor.py` (eng #452), `manifest.py` (eng #461),
`versions/`, `tools/frontdoor.py`, any other hot file.

### Why

`resolve_base`'s `--base` and `$RVT_GENESIS_BASE` branches computed `pinned = digest == pin.base_sha256`
— the DEFAULT (2026) record only — whatever the target. A byte-identical copy of
`plugin/assets/genesis/G_ABPD_2025.rvt` handed in by path (a packager, a firm pointing at the
bundled per-release base, the legacy env export) therefore read `pinned False / certified_genesis_base
False` + *"explicit --base is not the pinned genesis base …"* while the very same bytes resolved
through the registry (`--target-version 2025` alone) read pinned/certified — and since #264/#445 the
manifest's digest-chosen `base.pin` block already named the 2025 slot with `pin.sha256 == base.sha256`
right next to `pinned: false`: a visible contradiction (under-claim direction, but wrong).

### What was built

* `rvt.frontdoor.base._certified_slot_for_digest(digest, *, pin=PIN) -> slot | None`: the registry
  slot whose pinned sha256 IS the digest **and** which `release_status(year)` calls certified (slot
  status + sha pin + version model — the same three-source rule the pinned-slot branch obeys); None
  for a firm's own base, a stale copy, or a *pending* slot's bytes.
* The explicit and env branches use it: `pinned = certified = (slot is not None)`,
  `certification = slot["certification"]` (the default slot is synthesized from the default record,
  so a 2026 copy yields `pin.certification` exactly as before). The warning texts, the sample refusal,
  the `_require_base_release` target check, the two pinned branches, `ResolvedBase`'s shape and
  `as_json()` keys are untouched — this changes three labels (`pinned`, `certified_genesis_base`,
  `certification`) and drops one warning; it never changes which file is opened or a single output byte.
* With **no** `--target-version` the digest is matched against every certified slot (DONE 2), so
  `--base <copy of G_ABPD_2025.rvt>` alone is no longer "not the pinned genesis base". With a target,
  a copy of a *different* release's slot still dies in `_require_base_release` (wrong release →
  refused by `_resolve_base_and_version`, unchanged: `--base <2024 copy> --target-version 2025` →
  `refused` before and after).
* `tools/probe_batch.py frontdoor_entries` docstring: the stale *"the base block of a
  --target-version 2025 run still embeds the DEFAULT pin"* is rewritten to what is true since #445
  (`base.pin` IS the resolved slot; the all-slots digest match stays for manifests written before that).
  Code unchanged.
* Side effect worth naming (intended, bytes-neutral): `release_ctx._bundled_base_of(year)` returns
  `rb.path if rb.pinned and rb.certified` from `resolve_base(target_release=year)`; with
  `$RVT_GENESIS_BASE` set to a byte-identical copy of the certified slot it now returns that copy
  (before: None → no bundled donor) — same bytes as our composed base, so rule 3 holds; a foreign env
  base still yields None.

### Evidence (cloud session = fresh clone; bases from `plugin/assets/genesis`; "before" = `origin/main` @ 2767197 in a worktree, "after" = this branch; same copies of the three bundled bases under foreign names in a temp dir)

Command: `tools/frontdoor.py author --prompt "a room with four walls" --base <copy> [--target-version Y] --out <tmp> --json`, reading `manifest.json`'s `base` + `target_version` blocks and the built file's sha256.

| case | before (`main`) | after (head) | built `prompt_room.rvt` sha256[:16] before → after |
|---|---|---|---|
| copy of `G_ABPD.rvt` + `--target-version 2026` | explicit, pinned **True**, cert True, no warning | identical (0 differing manifest leaves) | `45f1795250f529e9` → same |
| copy of `G_ABPD_2025.rvt` + `--target-version 2025` | explicit, pinned **False**, cert False, certification null, warning *"explicit --base is not the pinned genesis base…"*, `pin.id G_ABPD_2025`, `pin.sha == sha` | explicit, pinned **True**, cert True, certification = the 2025 slot's `{ledger, entry, required}`, warnings `[]` | `c589e33275daa235` → same |
| copy of `G_ABPD_2024.rvt` + `--target-version 2024` | as 2025 (False + warning), `pin.id G_ABPD_2024` | pinned **True**, cert True, 2024 slot certification, no warning | `1a97ab56bdb44508` → same |
| copy of `G_ABPD_2025.rvt`, **no** target | pinned False + warning; `target_version` unspecified / `output_release 2026` | pinned **True**, cert True, no warning; `output_release` still **2026** (see Findings, #472) | `c589e33275daa235` → same (a 2025 file either way) |
| copy of `G_ABPD.rvt`, no target | pinned True | identical (0 differing leaves) | `45f1795250f529e9` → same |
| `--target-version 2025`, no `--base` (registry) | pinned-bundled, True/True | identical (0 differing leaves) | `c589e33275daa235` → same |
| `$RVT_GENESIS_BASE=<2025 copy>` + `--target-version 2025` | env, pinned False, warning *"$RVT_GENESIS_BASE is not the pinned genesis base…"* | env, pinned **True**, cert True, no warning | `c589e33275daa235` → same |
| a firm's own 2025 base (a front-door-built 2025 project) ± `--target-version 2025` | explicit, pinned False, warning | **unchanged**: pinned False, same warning (only differing leaves: `status_gate.elapsed_s` and the worktree path in `ledgered_against`) | `9e109bfd8b534c86` → same |
| copy of `G_ABPD_2024.rvt` + `--target-version 2025` | `refused` (wrong release), nothing built | unchanged | — |

Manifest leaf-diff before→after (paths normalised, `generated_at`/`seconds`/`stages` dropped): the
four flipped cases differ in exactly `base.pinned`, `base.certified_genesis_base`,
`base.certification` (null → the slot's entry) and `base.warnings` (the one warning gone) — 8 leaves
each, nothing outside `base`; every other case 0 leaves (or timing/worktree-path only).

Tests (`tests/test_frontdoor_manifest_pin.py`, section "eng #439"): explicit copy per release
(2026/2025/2024) with and without target → pinned/certified/certification == slot's, no warning, and
field-equal to the registry resolution; the same via `$RVT_GENESIS_BASE`; manifest of an explicit
2025/2024 copy → `base.pinned true`, `base.pin.sha256 == base.sha256`, `pin.certification ==
certification`; a foreign file (explicit and env) → pinned False + the warning; a *pending* slot's
bytes (registry copy with the 2025 slot demoted) → not certified; the no-target case pinned to today's
truth (base block right, version block default) plus an `xfail(strict=True)` naming #472 that flips
the day `output_release` follows the base. File: **21 passed, 2 xfailed** (was 9 passed).

### Findings / follow-ups

* **#472 (filed, `ready`, Refs #439)** — keeper 2 of the tech-lead comment: with no `--target-version`,
  `_resolve_base_and_version` (in `src/rvt/frontdoor/__init__.py`, eng #452's territory this wave, so
  not touched here) writes `output_release = PIN.revit_release` (2026) even when the supplied base —
  and the delivered, byte-identical file — is 2025/2024. After this PR the manifest's `base` block is
  the truthful half (`pinned true`, `pin.id G_ABPD_2025`); the version block is #472's, with a 4-line
  patch sketch in the issue (`produced = detect_release(base.path)` exactly as the fallback branch
  already does) and the strict-xfail test here as its tripwire.
* Pre-existing, not mine, not in the shard: `tests/test_target2024.py::test_cli_flag_parses_2024`
  fails on `origin/main` @ 2767197 too (it expects `--target-version 2023` to raise `SystemExit` at
  the CLI, but `tools/frontdoor.py`'s parser takes `type=int` with no `choices` now — any year parses,
  cf. #172); `tools/frontdoor.py` and that test are outside this territory, left alone.
* The tech-lead scope note (ResolvedBase carrying the matched slot/year; `GenesisPin.slot_for_digest`
  / `slot_as_json` so `manifest.resolved_pin`, `probe_batch.frontdoor_entries` and `census.pin_file`
  stop re-deriving slot identity) is deliberately NOT done in this hot-file PR (brief: explicit/env
  branches only, smallest diff; `manifest.py` is eng #461's this wave). `_certified_slot_for_digest`
  is the private seed of that accessor; promoting it to `GenesisPin` + threading a `release` field
  through all four branches is a clean follow-up once `manifest.py` is free.
* `/simplify` (4 angles). Applied: the helper drops a redundant `str(… or "")`, the two branches use
  `dict(slot["certification"]) if slot else {}` instead of a double `or {}` guard, the stale
  `certified:` field comment is corrected; tests reuse `conftest.CERTIFIED_YEARS` / `pinned_base`
  (import only — `conftest.py` itself untouched, eng #470) instead of a local `ALL_YEARS`, copy with
  `shutil.copyfile`, resolve each case once, hoist the `rvt.frontdoor` / `copy` imports. Skipped, with
  reason: (reuse) `census.pinned_sha256s()` and `manifest.resolved_pin()` are the same digest→slot
  scan — both import `base` (circular) and live in held files, so the new helper is the lowest-level
  copy and they should call *it* later, not the reverse; (altitude) `__init__._resolve_base_and_version`'s
  `is_our_default` still compares against the default sha only, so `--base <2025 copy>
  --target-version 2024` is refused where a 2026 copy degrades to the 2024 slot — added to #472
  (same function, same territory) rather than touched here; (efficiency) `release_status` per year
  builds a status dict to read two keys — measured 0.02 ms per `resolve_base` behind a 0.85 ms
  sha256 of the base, once per job: negligible, left readable.
* **#479 (filed, P1 `ready`)** — the whole merged shard is red on `origin/main` @ 2767197 itself:
  `tests/test_manipulate.py::test_job_set_param_op_lands_an_elementid_row_via_holder` imports
  `_load_job` from `test_job`, which #471 moved into `conftest`; reproduced on a clean main worktree,
  outside this territory (`tests/test_manipulate.py`), so reported rather than fixed here.

### `/verify` (final tree, after `/simplify`; the real surfaces)

* `tools/frontdoor.py author --prompt "a room with four walls" --base <copy of G_ABPD_2025.rvt> --target-version 2025 --out … --json`
  → rc 0, `PROOF-ONLY (self-checks PASS …)`, manifest `base`: `explicit pinned=True cert=True`,
  certification = 2025 slot entry, `pin.id G_ABPD_2025`, `pin.sha == sha`, warnings `[]`; built
  `prompt_room.rvt` sha `c589e33275daa235…` (== main's); same for 2024 (`1a97ab56bdb44508…`) and the
  2026 copy (`45f1795250f529e9…`, labels unchanged); `$RVT_GENESIS_BASE=<2025 copy>` → `env`, pinned
  True; a firm's 2025 base → pinned False + the warning, sha `9e109bfd8b534c86…` (== main's).
* `tools/rvt_validate.py` on the three explicit-copy outputs → `ok: true`, VALID, errors 0/0/0
  (the known DataStorage decoder-gap warning on 2026 only).
* `tools/probe_batch.py check <e25>/prompt_room.rvt` → `base = experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt [certified; pinned base recognised by sha256]`, ADMISSIBLE.
* `author --prompt "an electrical room with 6 panels" --base <2025 copy> --target-version 2025` →
  rc 0, families generated + loaded + placed, `release.output 2025`, combined VALID 0 errors / 0
  warnings, base `explicit pinned=True` (this prompt's build is not byte-deterministic run to run —
  two registry-base runs on the same tree also differ — so byte identity is shown on the 4-wall prompt).
* Bare unzip of the rebuilt `tekton-plugin.zip` (temp dir, no repo on the path), system `python3`:
  `skills/tekton-author/scripts/_bootstrap.py go author --prompt "a room with four walls" --target-version 2025 --out out/j25 --json`
  → `tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | …`, `ready true`,
  1.28 s, base `pinned-bundled assets/genesis/G_ABPD_2025.rvt pinned True`, `release.output 2025`,
  built sha `c589e33275daa235…`; and the case this PR changes, `… go author --prompt "a room with four walls" --base <copy of G_ABPD_2025.rvt> --target-version 2025 --out out/e25 --json`
  → READY, 0.84 s, base `explicit pinned True cert True pin.id G_ABPD_2025 pin.sha==sha warnings []`,
  built sha `c589e33275daa235…` (identical bytes to the registry run).

### BRANCH STATE

* Branch `cam/439-resolve-base-slot-registry` from `origin/main` @ 2767197. Files:
  `src/rvt/frontdoor/base.py` (`_certified_slot_for_digest`; explicit + env branches of
  `resolve_base` use it; two field comments), `tools/probe_batch.py` (docstring), the three
  `plugin/` mirrors via `tools/sync_plugin.py`, `tests/test_frontdoor_manifest_pin.py` (+12 cases:
  21 passed / 2 xfailed, was 9), this record section. No new shard drop-in needed (the file is
  already listed by `tests/ci_shard.d/264-manifest-pin-slot.txt`).
* Gates: `tests/test_frontdoor_manifest_pin.py` 21 passed, 2 xfailed; neighbours
  (`test_frontdoor test_probe_batch test_frontdoor_standalone test_go_target_version test_target2024
  test_target2025 test_target_version_first test_router_release` + the plugin surface
  `test_plugin_sync test_bootstrap test_coldstart test_surface_perf`): 223 passed / 31 skipped /
  2 xfailed / 1 failed = the pre-existing `test_target2024.py::test_cli_flag_parses_2024` (fails on
  main too, not in the shard, #172); `tools/sync_plugin.py` synced 3 files then `--check` clean;
  `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py` ok
  (2911 paths). Whole merged CI shard on the final tree (78 files,
  `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`):
  **1629 passed, 139 skipped, 5 xfailed, 1 failed in 289.10 s** — the 1 failed is #479 (red on
  `origin/main` @ 2767197 identically: `test_manipulate.py::…elementid_row_via_holder`, ImportError
  `_load_job`), i.e. this branch adds +12 passed / +2 xfailed and no failure of its own.
* Staged: nothing (labels only; no certification claim, no bytes changed). Shipped: via the PR that
  closes #439. Follow-ups: #472 (version block follows the base; + the `is_our_default` sibling), #479
  (main's red shard test).
