# sync-plugin-zip-stdlib — `tekton-plugin.zip` is built with the stdlib, deterministically (issue #37)

Stream: eng #37 (cloud engineer session, fresh clone, 2026-08-09), started by
the tech-lead session under the #302 regime (no Actions; session-hosted CI +
review). Charter (#37, PG3 / O2): `tools/sync_plugin.py rebuild_zip()`
shelled out to the Info-ZIP `zip` CLI, which a stock Windows box does not
have, so the one command CLAUDE.md tells every contributor to run after a
change under `src/`/`tools/`/`skills/` died with `FileNotFoundError` **after**
`plugin/` had already been rewritten — a half-synced tree and no zip.
Territory: `tools/sync_plugin.py` (`rebuild_zip` + two small helpers, nothing
else in the file), `tests/test_sync_zip.py` (new), `tests/ci_shard.txt`
(+1 line), this record. No manifest, skill, hot file or `src/` change.

Credit: an earlier attempt lives on `origin/ckaragitz12/37-sync-plugin-zip-stdlib`
(commit 88397e7; its PR #40 was closed unmerged when the parent branch it was
stacked on was deleted — CLAUDE.md §4 "never stack"). Its shape — a sorted
member walk, `ZipInfo` with a fixed epoch, streaming through `zf.open(zi, "w")`
— is kept here; this branch starts from current `main` (311dee9), adds the
directory entries the CLI emitted (so the entry list is *identical*, not just
the file set), normalises modes and `create_system` so the bytes do not depend
on the building OS, and adds the hermetic test.

## What was built

`tools/sync_plugin.py`:

* `zip_entries(root=PLUGIN) -> [(arcname, abspath | None)]`, sorted; `None`
  marks a directory entry. Rules, measured against what
  `zip -qr Z . -x '*/node_modules/*' -x '*/__pycache__/*' -x '*.rvt' -x '*.DS_Store' -x .DS_Store && zip -qr Z assets -x '*.DS_Store'`
  (Info-ZIP 3.0) actually keeps: contents at the archive **root** (no `./`
  prefix, `/` separators), one entry per directory (empty dirs included, as
  the CLI did), `SKIP_DIR_NAMES` (`__pycache__`, `node_modules`,
  `.pytest_cache`, `.DS_Store`) pruned wholesale at any depth and dropped as
  file names, `.rvt` (case-insensitive) dropped everywhere **except** under
  `assets/` (`ZIP_RVT_PREFIX`) — the certified genesis bases
  `assets/genesis/G_ABPD{,_2025,_2024}.rvt` are the product and stay in.
* `write_zip(zip_path, root=PLUGIN) -> size`: every entry gets
  `ZipInfo(arc, (1980,1,1,0,0,0))`, `create_system = 3`, files
  `external_attr = 0o100644 << 16` + `ZIP_DEFLATED` (zlib default level, the
  CLI's default too), directories `(0o40755 << 16) | 0x10` + stored, streamed
  with `shutil.copyfileobj`. No mtime, umask, uid/gid or OS reaches the bytes.
* `rebuild_zip()` is now `return write_zip(ZIP, PLUGIN)` (mode `"w"`
  truncates; the CLI-era pre-delete existed only because `zip -r` appends).
  `main()` is untouched: sync → schema cache → **deny-audit → asset verify →
  validate → zip → identity scan of tree + zip**, i.e. the deny-audit still
  runs before anything is zipped and the content scan still reads the freshly
  built zip (97 members scanned, 0 mismatches).

`tests/test_sync_zip.py` (3 cases, 0.05 s, hermetic, joins `tests/ci_shard.txt`):
the rule table on a 17-file temp tree (expected entry list spelled out,
including the empty dir, the nested `assets/genesis/deep/H.RVT`, the
proofs-only example dir that keeps its dir entry but loses its `.rvt`);
determinism (two builds byte-identical after touching an mtime; every
`ZipInfo` field pinned; contents round-trip); and one read-only real-tree
case (every *required* `asset_mappings()` base is in the entry list, no
`SKIP_DIR_NAMES` part and no non-asset `.rvt` anywhere).

## Evidence

All from this fresh cloud clone (python 3.11.15, Info-ZIP 3.0 for the baseline).

* **Entry list identical to the CLI build.** Baseline built first from clean
  `main@311dee9` with the old shell-out, listing kept
  (`unzip -Z1 | sort`, 349 entries, 58 of them directories, 3 `.rvt` — the
  genesis bases). New build: 349 entries; `diff old.list new.list` empty.
  `unzip` both and `diff -r`: extracted trees identical (content). The one
  observable difference on extraction: `lib/tools/genesis_assemble.py` (the
  only `100755` file tracked under `plugin/`) now extracts `0644` like every
  other file — it is loaded by path (`famdoc_adoc._ga()`), never executed.
* **Deterministic.** Four full `tools/sync_plugin.py` builds across the
  session (before and after the /simplify refactor):
  `sha256 7f1b185e1ffde28e07c0f1a37bfd246951ad16a09ac44b608cf43ada8cceb90a`
  every time; `cmp` of consecutive builds: byte-identical. (CLI baseline was
  `74cf517e…` and churned per run by construction — it stamps mtimes.)
  Size 5,208,872 B vs the CLI's 5,226,401 B (no UT/ux extra fields).
* **Deliberate tightenings vs the CLI** (none changes the real tree's list):
  junk dirs pruned at *any* depth (a `__pycache__`/`node_modules` directly at
  the plugin root slipped past `*/x/*`; the root holds no `.py`, so it never
  occurred); `.pytest_cache` pruned too, because `SKIP_DIR_NAMES` is the set
  `_shipped_files()` — the deny-audit / identity-scan walk — prunes with:
  before this, a `.pytest_cache` under `plugin/` would have been zipped but
  never audited; `.rvt` match is case-insensitive. Kept as the CLI had it:
  only `.rvt` is dropped by extension (not all of `BINARY_EXT`) — sync's
  `_walk` never copies `.rfa/.mp4/.mov` into `plugin/` in the first place.
* **Gates.** `tests/test_plugin_sync.py tests/test_bootstrap.py
  tests/test_coldstart.py tests/test_surface_perf.py tests/test_sync_zip.py
  -q -rs` → **31 passed, 5 skipped** in 6.8 s (the 5 skips are
  `test_surface_perf.py`: "no bare python3 with numpy on this host",
  pre-existing and host-specific). `tools/sync_plugin.py` full build exit 0
  (`√ Validation passed`, identity scan 97 files + 97 zip members, 0
  mismatches) then `--check` → in sync; `plugin/scripts/validate_plugin.py`
  → PASS (25 assertions); `tools/dev/check_portable_paths.py` → ok (2772).
* **/verify (bare surface, the NEW zip).** Unzipped into a temp dir, repo not
  on the path, `TEKTON_ROOT`/`PYTHONPATH` unset, system `python3` (3.11.15):
  `python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an
  electrical room with 6 panels" --out out/j1 --json` → exit 0,
  `tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit
  2026) | family-donor missing | out-dir OK | 0.046s`, `ready: true`,
  `result.ok: true`, `errors: []`, `prompt_room.rvt` + 6 `.rfa` + HANDOFF /
  MANIFEST delivered (stamped PROOF-ONLY, as always), job 3.3–3.6 s.
* **`tools/surface_bench.py --zip tekton-plugin.zip --json out/bench.json`**
  (37 s wall), old CLI zip vs new stdlib zip, per surface (session totals /
  the three headline jobs, seconds):

  | surface | zip | preflight | go-author-prompt | go-author-6panels | go-edit | session total |
  |---|---|---|---|---|---|---|
  | cowork (bare, unzip once) | old | 0.08 | 1.76 | 3.06 | 0.72 | 9.64 |
  | cowork | **new** | 0.10 | 2.08 | 3.08 | 0.68 | 10.00 |
  | codeexec (fresh extract per call) | old | 0.09 | 2.07 | 3.39 | 1.10 | 11.38 (extract 1.62) |
  | codeexec | **new** | 0.07 | 2.08 | 3.47 | 1.08 | 11.38 (extract 1.37) |
  | local (repo, warm) | old | 0.06 | 1.77 | 3.45 | 0.68 | 14.62 |
  | local | **new** | 0.07 | 1.88 | 3.08 | 0.75 | 14.47 |

  Noise-level either way (single runs on a shared VM); per-call extraction of
  the new zip is not slower (1.37 s vs 1.62 s summed over 10 calls). Both
  runs report the same one non-PASS, `author-ifc` FAIL on the two bare
  surfaces — `/usr/bin/python3` here has no numpy ("numpy is required here
  (IFC placement / geometry resolution)") — identical with the old zip, so
  not this change; already tracked as #127 (and the `}` reason string as
  #287). No new follow-up filed.

## Findings / notes for whoever touches this next

* "Byte-identical on any OS" holds for everything the writer controls; the
  DEFLATE payload additionally depends on the linked zlib (CPython's bundled
  zlib vs a system zlib-ng-compat build can emit different-but-valid streams).
  Same toolchain ⇒ same bytes is what the test asserts; do not "fix" the
  writer if a future cross-OS sha256 comparison differs — compare entry
  lists + CRCs instead.
* The zip's prune set and the audits' prune set are now the same constant
  (`SKIP_DIR_NAMES`); keep it that way — a fourth hand-maintained junk list
  is how "zipped but never audited" happens.
* Windows itself was not available in this session; the claim rests on the
  code path being pure stdlib (`os.walk` + `zipfile`, `/`-normalised
  arcnames, no mode bits read from the filesystem). O2's `windows-latest` CI
  job is where it gets exercised for real.

## BRANCH STATE

* Branch `cam/37-sync-plugin-zip-stdlib` from `main@311dee9`; PR closes #37.
* Files: `tools/sync_plugin.py` (`rebuild_zip` → `zip_entries` + `write_zip`;
  `subprocess` import still used by `validate()`), `tests/test_sync_zip.py`
  (new, 3 cases), `tests/ci_shard.txt` (+1 line), this record. Nothing else.
* Gates: listed above — 31 passed / 5 skipped; build ×4 same sha256; entry
  list == CLI baseline (349); `--check` clean; validate_plugin PASS; portable
  paths ok; bare-unzip `go author` READY/ok; surface_bench pasted.
  /simplify ran (4 reviewers; applied: reuse `SKIP_DIR_NAMES`, name the
  `assets/` prefix, drop the CLI-era pre-delete, derive bases from
  `asset_mappings()` in the test, fixture-ise the temp tree).
* Shipped vs staged: everything is in the PR; `tekton-plugin.zip` is a
  git-ignored build artifact (regenerated, not committed); no viewer round
  implied (packaging only — the shipped `.rvt` bytes are unchanged, verified
  by `verify_assets()` + the identity scan).
