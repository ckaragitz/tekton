# probe-batch-freshclone — the standing-controls gate works on a fresh clone (#131, 2026-08-09)

Stream record for issue #131 (P1, `area:genesis` / `area:process`; sibling of #8, whose
campaign-global numbering + multi-control scope is deliberately NOT absorbed here).
Territory: `tools/probe_batch.py`, `tests/test_probe_batch.py`, this record; read-only use of
`rvt.frontdoor.base.GenesisPin` (hot file, untouched) and of the ledger
`docs/coverage/viewer-certified.json` (hot file, untouched).

## Why

CLAUDE.md §4 says contributors' cloud / fresh-clone sessions STAGE viewer batches and stop at
READY. Before this change they could not stage anything: `Ledger.status()` keyed only on repo
paths under `experiments/` (git-ignored, absent on a fresh clone) and `make_control()` needed a
certified file on disk, so every front-door output was refused as *undeclared* and the gate had
*no* control source — although `plugin/assets/genesis/G_ABPD{,_2025,_2024}.rvt` are tracked,
sha256-pinned, byte-identical copies of ledger-certified files, and every front-door
`manifest.json` already records the base path + sha256 + ledger entry.

## What was built (the law is unchanged; the gate learned where the certified bytes are)

1. **The sha256 alias rule** (module docstring, now part of the batch law).
   `Ledger.status(path)`: the ledger PATH still decides first (`certified` / `sample` /
   `failed`); only a path the ledger has never heard of may be certified **by bytes** — its
   sha256 equals a certified entry's recorded `sha256`, or equals a genesis pin
   (`rvt.frontdoor.base.PIN` release slot → `PinnedBase`) whose pinned relpath is *itself* in
   `certified`. The returned entry is re-keyed to the certified path and stamped
   `aliased_from` / `alias_sha256`. Exact digest equality only: a byte-different file under a
   certified basename stays `unknown`; a path recorded as FAILED stays failed whatever its bytes;
   a pin whose relpath the ledger never certified aliases nothing.
2. **Per-release control fallback.** `make_control(..., release=)` → `Ledger.control_source()`:
   the newest certified `experiments/` file on disk (owner machine, unchanged), else the pinned
   bundled base of the batch's release (`plugin/assets/genesis/*.rvt`, sha-verified against the
   pin, pin relpath ledger-certified). `batch_release()` reads the release off the probes'
   declared bases (the pin whose certified relpath the base IS). Control naming law
   `CTRL_<stem>_b<n>` and the manifest `law` text are unchanged; the control entry additionally
   records `control_certified_as` (the ledger path it is a copy of) + `control_sha256`.
3. **The front door's `manifest.json` is a declaration.** `frontdoor_entries()` yields one
   probe entry per `.rvt`/`.rfa` in `build.files` (create routes) / `output` (edit route), each
   declaring the run's base: `base.sha256` == a genesis pin's digest → that pin's certified
   relpath (matched against *every* release slot, because a `--target-version 2025` manifest
   still embeds the DEFAULT 2026 pin under `base.pin` — see follow-up below); else `base.pin`
   when its digest matches; else the base file itself (explicit `--base` / `$RVT_GENESIS_BASE`
   / the `--rvt` input), which the ledger then judges by path or by bytes like any other base.
   Each entry carries the structured `release` (matched pin, else `target_version.output_release`)
   and `digest_matched`, which `BaseResolution` / `batch_release()` / the CLI read — no prose
   sniffing. `_resolve_entry` gained one general rule on the way: a declared value that names an
   existing file (repo-relative or absolute, any OS) is that file verbatim, before free-text parsing.
   Found automatically in the probe's own directory, or named with `--manifest`. A file the
   manifest did not build is still refused as undeclared.

## Evidence (this cloud session = a fresh clone: no `samples/`, no `experiments/**/*.rvt`)

Wall times: `frontdoor author` (walls-only) 2.6 s; `probe_batch.py check` 0.18 s (was 1.2 s
refusing); `stage` 0.17 s.

**Before** (unchanged tool, same file):
```
$ .venv/bin/python tools/frontdoor.py author --prompt "a room with four walls" --out out/pb --json   # exit 0, 2.6 s
$ .venv/bin/python tools/probe_batch.py check out/pb/prompt_room.rvt                                # exit 2
  probe          out/pb/prompt_room.rvt
      base = None  [undeclared]
      declared by no probes.json entry describes this file
BATCH REFUSED -- 1 violation(s):
  * PROBE out/pb/prompt_room.rvt: NO DECLARED BASE -- no probes.json entry describes this file. ...
(the gate would also add 1 certified control: NONE AVAILABLE)
$ .venv/bin/python tools/probe_batch.py stage out/pb/prompt_room.rvt --out-dir <scratch>            # exit 2, BATCH REFUSED (same violation)
```
while `out/pb/manifest.json` `base` = `{source: pinned-bundled, path: plugin/assets/genesis/G_ABPD.rvt,
sha256: 84173b89…df50, certification.entry: experiments/genesis/subst_k4/compose/G_ABPD.rvt}`.

**After:**
```
$ .venv/bin/python tools/probe_batch.py check out/pb/prompt_room.rvt                                # exit 0
  probe          out/pb/prompt_room.rvt
      base = experiments/genesis/subst_k4/compose/G_ABPD.rvt  [certified; pinned base recognised by sha256]
      declared by out/pb/manifest.json entry 'prompt_room' field 'base' (front-door manifest: base.sha256 84173b8960b8... == the Revit 2026 genesis pin)
ADMISSIBLE -- `stage` will add the certified control (source: plugin/assets/genesis/G_ABPD.rvt) and write the manifest

$ .venv/bin/python tools/probe_batch.py stage out/pb/prompt_room.rvt --note "#131 fresh-clone verification ..."   # exit 0
batch 57 staged -> experiments/acceptance/batch_57.json
reading order (control FIRST):
  0. control        experiments/acceptance/CTRL_G_ABPD_b57.rvt  copy of plugin/assets/genesis/G_ABPD.rvt
  1. probe          out/pb/prompt_room.rvt  base=experiments/genesis/subst_k4/compose/G_ABPD.rvt [certified]

$ md5sum experiments/acceptance/CTRL_G_ABPD_b57.rvt plugin/assets/genesis/G_ABPD.rvt
1f1ff65bd68415a05228d6b6ac2bf271  experiments/acceptance/CTRL_G_ABPD_b57.rvt      # byte-identical to the pinned base ...
1f1ff65bd68415a05228d6b6ac2bf271  plugin/assets/genesis/G_ABPD.rvt
$ sha256sum experiments/acceptance/CTRL_G_ABPD_b57.rvt
84173b8960b8cbba1b096a42ad4a97ed24deba9476ccb05eb8853d4c6d06df50                   # ... == the pin == genesis_base.json
```
Cross-check against the owner's machine: the tracked `experiments/acceptance/batch_39.json`
control (`CTRL_G_ABPD_b39.rvt`, cut from `experiments/genesis/subst_k4/compose/G_ABPD.rvt`)
records md5 `1f1ff65bd68415a05228d6b6ac2bf271` — the same digest as the control this fresh
clone cut from `plugin/assets/genesis/G_ABPD.rvt`. `batch_57.json` control entry:
`control_source: plugin/assets/genesis/G_ABPD.rvt`, `control_certified_as:
experiments/genesis/subst_k4/compose/G_ABPD.rvt`, `control_sha256: 84173b89…df50`; probe entry
`base_status: certified`, `base_declared_by: out/pb/manifest.json … == the Revit 2026 genesis pin`;
`resolve` additionally reports the structured `release: 2026, digest_matched: true`.
The `--target-version 2025` output checks ADMISSIBLE the same way (base
`experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt`, control source
`plugin/assets/genesis/G_ABPD_2025.rvt`).

**STAGE only.** Nothing was uploaded and no verdict written. The verification batch (b57: a
walls-only room, a shape already certified) is *not* proposed as a viewer round, and its `.rvt`
bytes exist only in this ephemeral VM, so `batch_57.json` was deleted again rather than
committed — committing a manifest whose files nobody can upload would only burn a campaign
number (numbering is #8's territory).

**Tests.** `tests/test_probe_batch.py`: 39 passed / 7 skipped (the 7 are the pre-existing
tier-5 real-corpus cases) in 0.7 s on this fresh clone; 12 new tier-6 tests: alias hit via pin,
alias hit via a ledger entry's own `sha256`, alias miss (pin relpath not certified), tampered
copy under a certified basename refused, failed path stays failed with certified bytes,
front-door manifest declaration (own dir and `--manifest`), the 2025 run matched against the
release slot not `base.pin`, a stray file next to a manifest still undeclared, explicit
unpinned base judged by the ledger (refused unknown / admitted by alias), per-release control
fallback through `stage_batch` (name `CTRL_G_ABPD_2025_b77.rvt`, byte-identical, law text
unchanged, round reads INTERPRETED), no control source at all still a refusal, and the shipped
pins aliasing the three bundled bases against the real ledger. The file is now in
`tests/ci_shard.txt` (fresh-clone green, < 1 s). Plugin gates: `tools/sync_plugin.py` synced the
two mirrors (`plugin/lib/tools/probe_batch.py`, `plugin/skills/tekton-author/scripts/probe_batch.py`),
`--check` clean, `plugin/scripts/validate_plugin.py` PASS (24 assertions),
`tests/test_plugin_sync.py test_bootstrap.py test_coldstart.py test_plugin_validate.py` 32 passed,
`tools/dev/check_portable_paths.py` ok.

## Findings / follow-ups (out of territory — filed, not fixed here)

* `rvt.frontdoor.manifest.build_manifest` writes `"pin": PIN.as_json()` — always the DEFAULT
  (2026) pin — even when the resolved base is the 2025/2024 slot, so `base.sha256 != base.pin.sha256`
  on every non-2026 run. The gate works around it by matching against all release slots; the
  manifest should embed the slot it actually resolved. (front-door territory, `manifest.py`.)
* Every prompt-route output is named `prompt_room.rvt`, so two fresh-clone stagings into the
  same `experiments/acceptance/` collide on basename (the gate refuses to overwrite a different
  staged file, by design). Distinct output names per run, or a `stage --as NAME`, would remove
  the manual rename. (front-door naming or #8's staging ergonomics.)
* `plugin/lib/tools/probe_batch.py` in an unzipped plugin has no ledger beside it
  (`docs/coverage/` is not bundled), so the gate is a repo tool, not a plugin-surface tool — as
  before; noted, not changed.

## BRANCH STATE

* Branch `cam/131-probe-batch-fresh-clone` from `main` @ 5a40b22. Files: `tools/probe_batch.py`
  (alias rule, `PinnedBase`/`genesis_pins`, `Ledger.{sha_index,alias,pin_for,pinned_certified_on_disk,control_source}`,
  `frontdoor_entries`, `BaseResolution.{release,digest_matched}`, `batch_release`, `make_control(release=)`,
  the exact-existing-path rule in `_resolve_entry`, dead `find_entry` removed, CLI lines), its two generated
  plugin mirrors, `tests/test_probe_batch.py` (+ tier 6), `tests/ci_shard.txt` (+1 line), this record.
  NOT touched: `docs/coverage/viewer-certified.json`, `src/rvt/frontdoor/base.py`,
  `src/rvt/versions/`, `tools/frontdoor.py`, `KNOWLEDGE.md`, `TRACKER.md`.
* Gates green as listed under Evidence. Staged: nothing (verification batch torn down).
  Shipped: the tool change + tests + record via the PR that closes #131.
