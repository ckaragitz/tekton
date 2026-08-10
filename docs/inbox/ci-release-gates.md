# Inbox — ci-release-gates (the per-release acceptance gates + the bare-surface perf gate EXECUTE on a fresh clone and join the shard) — issue #136

## eng #136 — 2026-08-10

Stream: issue #136 (P2, `area:frontdoor` / `area:perf` / `area:process`; PG1, PG3, PG4; Refs #102,
#92, #108, closed #44). Territory used: `tests/test_target2025.py`, `tests/test_target2024.py`,
`tests/test_surface_perf.py`, `tests/ci_shard.d/136-release-gates.txt` (new), this record (new).
NOT touched: anything under `src/`, `tools/` (no `tools/surface_bench.py` pass-through was needed —
see § perf gate), `plugin/`, `skills/`, `tests/ci_shard.txt` (the issue text predates #328; the
drop-in replaces the "gains the three files" line), any hot file.

### Why

The three files are gates that existed but never ran where CI runs. `test_target2025.py` /
`test_target2024.py` hard-coded `GENESIS = experiments/genesis/subst_k4/compose/G_ABPD.rvt` (and
`G25 = …/subst_k4_2025/compose/G_ABPD_2025.rvt`, and `experiments/genesis/R5.rvt` for the "foreign
base" cases) — all git-ignored — so 7 + 5 tests skipped on every fresh clone although the very same
certified bytes ship in `plugin/assets/genesis/` and `resolve_base(target_release=N)` already falls
back to them sha-verified (closed #44). `test_surface_perf.py::_bare_python()` skipped all five perf
tests unless `/usr/bin/python3` could `import numpy`, which neither a claude.ai/code VM nor
ubuntu-latest can — while every job in the canonical session has built on the numpy-free path since
#44 / #127. And `test_target2024.py::test_cli_flag_parses_2024` had been red on `main` for days
(seen by #439 and #472's reviewers): it still expected argparse to reject `--target-version 2023`,
which #172 (issue #24, hard rule 1) deliberately made parse so the engine's guard can DELIVER the
default build + THE honest line + the IFC addition.

### What changed

* **Bases through the registry, not literals.** Both target files take their bases from
  `tests/conftest.py::pinned_base(year)` — THE ONE "certified pinned base of a year, or a clean
  skip" helper the rest of the suite already uses, which is exactly
  `rvt.frontdoor.base.resolve_base(target_release=year).path` (repo pin path on the owner's machine
  → the sha-verified `plugin/assets/genesis` copy on a fresh clone) plus the `pinned and certified`
  check, so a `$RVT_GENESIS_BASE` override can never masquerade as our pin in the "pinned base"
  assertions. Exposed as module fixtures `genesis` (2026) and `g25` / `g24`, requested by the tests
  that read the path and applied as `needs_genesis = pytest.mark.usefixtures("genesis")` /
  `needs_2025_base` / `needs_2024_base` to the ones that only build on it. A skip can now only say
  *why nothing certified resolves on this machine* (bundle absent, or the year not certified —
  which is also how the finish-line tests keep arming themselves: `until_20xx_certifies` became
  redundant with the base fixture and is gone), never "pinned genesis base absent" on a clone that
  ships the base. The 2025 file's private `release_ctx._bundled_base_of(2025)` call is folded into
  the same fixture.
* **"User base of the wrong release is refused" without R5 — decision stated, as asked.** Since
  #483/#490 (`base._certified_slot_for_digest`, three-source rule) a byte-copy of ANY certified slot
  passed as `--base` is recognised as *our base arriving by path* and, with a different
  `--target-version`, resolves the TARGET's own slot (`match`) instead of being refused (#472's
  uniform rule; `docs/inbox/frontdoor-manifest-pin.md` § eng #439 / § eng #472). So a bundled base of
  another release cannot by itself stand in for "a firm's own file". Both behaviours are now pinned
  explicitly, one test each per release:
  * `test_frontdoor_explicit_pinned_base_never_refuses[_2024]` (renamed from
    `…_still_falls_back…`, which *skipped itself* once the release certified, with a reason —
    "the explicit-2026-base path now refuses correctly" — that #24/#472 had made false): the bundled
    default (2026) base passed as an explicit `--base` with target 2025 / 2024 → **`match`**,
    `output_release` = the target, `manifest.base.pinned` true with a `pinned-*` source, the note
    names `--base`, no IFC addition; era-conditioned like every other TODAY-test (→ `fallback` + IFC
    if the slot were not certified), so it never skips.
  * `test_frontdoor_user_base_of_wrong_release_is_refused[_2024]`: the *genuinely foreign* stand-in
    is the bundled 2026 base with the registry match switched off —
    `monkeypatch.setattr(B, "_certified_slot_for_digest", lambda digest, pin=B.PIN: None)`, the exact
    seam `tests/test_frontdoor.py::test_foreign_wrong_release_base_is_still_refused`,
    `tests/test_router_release.py` and `tests/test_frontdoor_manifest_pin.py::_firm_bases` use — so
    the same bytes read as a firm's own 2026 file: → **`refused`**, nothing built, no IFC. Same
    intent and assertions as the R5 version; runs on a fresh clone.
  * The `resolve_base(GENESIS, target_release=2025|2024)` → `VersionError` tests are unchanged and
    still true: `base.py`'s explicit branch keeps `_require_base_release`; the slot-copy degrade lives
    one level up in `frontdoor._resolve_base_and_version`.
* **`test_cli_flag_parses_2024` re-anchored to #172's contract** (the 2025 twin was re-anchored by
  #172 itself; the 2024 copy was missed): `--target-version 2023` parses to `2023` (reaches the
  engine guard; `tests/test_target_version_first.py` pins the delivered fallback end to end), a
  non-integer (`R24`) still exits 2. The comment says why the old `SystemExit` expectation was red.
* **Perf gate runs numpy-free.** `_bare_python()` now returns the first of `/usr/bin/python3`,
  `shutil.which("python3")`, `sys._base_executable` (the interpreter *under* a venv, so a host with
  no system `python3` on those paths still gets a python without the venv's site-packages) that
  exists and meets the plugin's own floor (`MIN_BARE_PY = (3, 9)`, = `tekton_env.MIN_PY`), and only
  as a last resort `sys.executable`; no `import numpy` probe, no skip.
  `tools/surface_bench.run_bench(python_bare=<path>)` already takes an interpreter path, so no bench
  pass-through was needed (territory clause not exercised). Docstring rewritten to say numpy is not
  required and why.
* **Shard drop-in** `tests/ci_shard.d/136-release-gates.txt` lists the three files
  (`test_target2025.py` was already in `tests/ci_shard.txt`; listed twice, runs once — `shard_list`
  rule). Merged shard: 83 → 85 files.

### Evidence (this cloud VM = a fresh clone: no `samples/`, no `experiments/**/*.rvt`, `/usr/bin/python3` = 3.11.15 without numpy; 4 vCPU; base `origin/main` @ cd2d5a2)

`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_target2025.py tests/test_target2024.py tests/test_surface_perf.py -q -rs --durations=15 -p no:cacheprovider`

| | result | skips |
|---|---|---|
| before (main) | **1 failed**, 13 passed, **18 skipped** in 4.25 s | 6 × "pinned genesis base absent" + 1 × "R5 ancestor absent" + 1 × "composed 2025 base absent" (2025 file); 4 × "pinned genesis base absent" + 1 × "R5 ancestor absent" (2024 file); 5 × "no bare python3 with numpy on this host" (perf); red = `test_cli_flag_parses_2024` (`DID NOT RAISE SystemExit`) |
| after (head) | **0 failed, 32 passed, 0 skipped** in 13.73 s | none — not even ifcopenshell-gated ones (the IFC round-trip reads back through the bundled steplite shim since #130/#367) |

`--durations` after: the perf module's one fixture (`bench_report`, all four jobs on `/usr/bin/python3`) 6.62 s setup; `test_END_STATE_2025_family_and_instance_lane` 2.84 s; `test_END_STATE_author_2025_produces_a_2025_file` 1.89 s (newly executing: Format 2025, pinned 2025 schema sha, partitions clean under 2025 ordinals and refused under native); `test_END_STATE_author_2024_produces_a_2024_file` 1.66 s (newly executing, same proof for 2024); `test_ifc_addition_roundtrips_the_intent` 0.43 s; `test_release_ctx_swaps_and_restores_everything` newly executing (< 5 ms).

The four perf jobs under their ceilings — the fixture's own bench call, reproduced verbatim for the per-job split
(`tools/surface_bench.py --from-tree --surfaces cowork --jobs preflight,author-prompt,go-edit,go-author-6panels --python-bare /usr/bin/python3`, "python 3.11.15; numpy=NO"):

| job | shell calls | wall | ceiling |
|---|---|---|---|
| preflight | 1 | 0.1 s | 2.0 s |
| author-prompt | 1 | 2.2 s | 20.0 s |
| go-edit | 1 | 0.5 s (job 0.415 s; validation PASS 0/0 inside the call) | 20.0 s |
| go-author-6panels | 1 | 3.4 s (job 3.3 s: F 1.2 · L 1.0 (6/6) · V 0.5) | `ROOM6_CEILING` 8.0 s |
| session total | **4 calls** | 6.2 s | budget 4 calls |

Per #184's note on the issue: the 6-panel wall on this VM (3.4 s; the fixture run inside pytest measured the
same module at 6.5 s total setup) sits where #299 measured it (3.1–3.7 s), so `ROOM6_CEILING = 8.0` stands
un-widened; the first tech-lead sandbox run of this shard is the runner-measured number to restate next to it
if it differs.

**Whole merged CI shard** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`), once each on the same VM:

| | files | result | wall |
|---|---|---|---|
| before (main's tree, 83 files) | 83 | 1756 passed, 139 skipped, 3 xfailed, 0 failed | 315.97 s (5:16) |
| after (head, 85 files) | 85 | **1781 passed, 131 skipped, 3 xfailed, 0 failed** | 315.23 s (5:15) |

Delta: +25 passed / −8 skipped; wall **+0 s within run-to-run noise** (the added work is ~14 s of test time by
`--durations` — 6.5 s perf fixture + ~7 s of newly-executing target builds — i.e. < 5 % of the shard and inside
its variance on this VM); the shard stays ≈ 5¼ min here, well under the ~8 min line.

### Findings / follow-ups

* None filed. The one product-behaviour question the issue flagged (slot copies degrade rather than refuse)
  was already decided and shipped by #472/#483/#490; the tests now assert that decision instead of skipping
  around it.
* Noted for whoever next touches `test_surface_perf.py`: only on a host with *no* `/usr/bin/python3`,
  no `python3` on PATH **and** no resolvable base interpreter does `_bare_python()` fall to
  `sys.executable`; if that is a venv python the "bare" surface sees the venv's site-packages
  (`pyvenv.cfg` decides that, not `VIRTUAL_ENV`), so the engine could import from the editable install
  rather than the plugin's bundled `lib/` — ceilings and call counts still hold, only the "bundled
  engine" purity weakens. A `-I`/`-S` argv pass-through in `surface_bench.run_bench` would close even that —
  deliberately not done here (no such host on the CI paths this issue targets; the territory clause says
  "only if it proves necessary"). Belongs with the Windows CI job (O2) if it ever bites.
* Off-territory one-liner (hot file, not touched): `tools/frontdoor.py`'s module docstring still
  advertises `--target-version {2026,2025,2024}` although #172 made any year parse; worth folding into
  the next `hot-file` PR that opens that file.

### Gates

* Stream-local: the three files above — 32 passed / 0 skipped / 0 failed; `tests/test_shard_list.py` 23 passed
  (drop-in well-formed, paths exist).
* No `src/` `tools/` `skills/` `plugin/` change → `sync_plugin`/`validate_plugin` not required; run anyway by
  `scripts/cloud-setup.sh` at session start: "plugin in sync with source (deny-audit clean, identity scan ==
  allowlist, assets verified)", portable paths ok (2932). `python3 tools/dev/check_portable_paths.py` re-run on
  the final tree: ok.
* Whole merged shard: table above (0 failed).
* `/simplify` (4 angles: reuse / simplification / efficiency / altitude). Applied: (reuse + altitude) the
  first draft's per-file `_certified_base(year)` helper (`resolve_base(...).path` with a broad `except`)
  duplicated `conftest.pinned_base` and dropped its `pinned and certified` guard → replaced by the
  `genesis` / `g25` / `g24` fixtures over `pinned_base`; (simplification) `until_2025_certifies` /
  `until_2024_certifies` deleted — the base fixture already implies the year is certified; combined
  `status/output_release` and `pinned/source` asserts split into one fact each; `_bare_python()` loop no
  longer lists `sys.executable` twice and uses `sys.exit(version_info < floor)`; docstrings trimmed to the
  contract; (altitude) base interpreter tried before the venv one. Efficiency: clean by measurement —
  base resolution at fixture time is 1.1 ms (2026, one sha256 of 582 KB) / 3.6 ms warm (2025, + one
  BasicFileInfo read), `_bare_python()` runs once per module (one 12 ms subprocess on this host).
  Skipped, with reason: importing `MIN_PY` from `plugin/skills/_shared/tekton_env.py` instead of the
  `MIN_BARE_PY` constant (a `sys.path` insert for one integer pair; the comment cross-references it);
  a shared `foreign_base` fixture for the `_certified_slot_for_digest` monkeypatch (one use per file here;
  the registry-fixture promotion is #472's named base.py follow-up, hot file); recording the chosen bare
  interpreter path in the bench report (`tools/surface_bench.py`, not necessary for the DONE).
* `/verify`: not run — the diff is tests + a shard drop-in + this record, with no runtime surface to drive
  (the surfaces the tests gate were driven directly instead: the bench command above and the shard run).

### BRANCH STATE

* Branch `cam/136-release-gates` from `origin/main` @ cd2d5a2. Files: `tests/test_target2025.py`,
  `tests/test_target2024.py`, `tests/test_surface_perf.py`, `tests/ci_shard.d/136-release-gates.txt` (new),
  `docs/inbox/ci-release-gates.md` (new, this file). Nothing under `src/ tools/ plugin/ skills/`.
* Gates: as above — 32/0/0 stream-local; merged shard 1781 passed / 131 skipped / 3 xfailed / 0 failed in
  315 s (was 1756 / 139 / 3 / 0 in 316 s on main's tree).
* Staged: nothing (no certification claim; no viewer batch). Shipped: via the PR that closes #136.
