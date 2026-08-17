# install_schema: no schema cache file at all — nothing on disk can fail a job through it (#208)

Stream: `cam/208-schema-cache-peruser` · issue #208 (P1, `area:frontdoor` `area:plugin`, from steer #108's
requirements sweep, program goals PG1/PG3) · territory `src/rvt/frontdoor/standalone.py` (+ one dead line in
`src/rvt/frontdoor/release_ctx.py`), `plugin/skills/_shared/tekton_schema.py`, `tests/test_install_schema_208.py` (new,
+ `tests/ci_shard.d/208-install-schema-in-memory.txt`), two existing rows in `tests/test_frontdoor_standalone.py` /
`tests/test_lazy_schema_wrapper.py`, this record, notes appended to `docs/inbox/install-schema.md` and
`docs/inbox/standalone.md`. No hot file touched. (The record keeps the issue's name; the fix outgrew "per-user".)

## What was wrong (hard rule 1, for the second person on the box)

`standalone.install_schema()` reroutes every default-schema chokepoint to the installed base's embedded
`Formats/Latest`, in memory. As its step (a) it **also** wrote those ~497 KB to
`tempfile.gettempdir()/tekton-schema-cache/Formats_Latest_<sha16>.bin` — one fixed name shared by every account,
bare `os.makedirs` + `open(…, "wb")`, no error handling — and re-pointed `rvt.schema.DEFAULT_PATH` at the file "for
any code comparing/opening the path directly". `build.py::_build_intent_inner` wraps the install in
`except Exception → errors.append("schema install from base failed: …"); return`, so on any box where another
account ran first (CI runner, shared Linux host, this very cloud image: `/tmp/tekton-schema-cache` is root-owned
`755` here) the second account got preflight READY and then, 0.75 s into every job, `FAILED (schema install from
base failed: PermissionError: [Errno 13] Permission denied: '…/tekton-schema-cache/Formats_Latest_6459a9a93ebde32c.bin')`,
`files: {}` — nothing built, nothing delivered.

## What was built

**Step (a) is retired.** `install_schema()` now installs `default_schema_loader(schema, rvt.schema.DEFAULT_PATH)`
and seeds the singletons — exactly the in-memory contract `release_ctx` has always installed for the 2025/2024
targets (which ship certified files that way) — touches no filesystem, and leaves `DEFAULT_PATH` alone; its report
says `rvt.schema.load_schema default path -> installed schema, in memory (DEFAULT_PATH untouched)`. With no write
there is nothing for a foreign-owned directory, a full disk, a read-only container or a missing temp dir to break.
Alongside: `bundled_schema()` stops retaining the raw stream in `_SCHEMA_STATE["blob"]` (only step (a) read it;
~0.5 MB per process), and `release_ctx`'s dead `"blob": b""` goes with it.

The plugin's lazy wrapper (`plugin/skills/_shared/tekton_schema.py::install`) used "the default path is a real
file" as its arm-time sentinel for *two* things: the research corpus, and "the host already ran `install_schema()`"
(via the cache file). The second is now asked of the host's state (`sys.modules.get("rvt.frontdoor.standalone")`
— never imported *for* the check, so arming stays ~0 ms) and answers `host-installed`; arming after a completed
install still wraps nothing (#376's property, re-pinned in `test_lazy_schema_wrapper`).

Consumers of `DEFAULT_PATH`-as-a-file, verified over the whole tree: `rvt.schema.schema_available()` (has the
bundled-base fallback), the engine's original `load_schema` when a pre-install holder calls it (see the hazard note
below — it gets *better*), `tools/make_family.py:85` and two test fixtures (`isfile → else activate()`, idempotent),
the lazy wrapper's sentinel (above), and two tests that copied the cache file as a "verbatim explicit path" specimen
(they now inflate the installed base's own stream). Nothing on the product path ever read the file back — a second
process must inflate and hash the base before it can even *name* the cache file, so "cached" saved nothing.

### Why not the first design (a per-user, private, atomic, never-fatal cache)

The first cut kept step (a) and hardened it: `$RVT_SCHEMA_CACHE_DIR` else `<tmp>/tekton-schema-cache-<uid>`, the
directory `lstat`-checked to be a real directory owned by this uid and not group/other-writable (a predictable name
in a shared `/tmp` is a symlink-plant target), `mkstemp` + `os.replace`, and any `OSError` → served from memory. It
worked (same `nobody` evidence as below, plus a name-squat case) and passed 7 adversarial rows. The `/simplify` pass
(altitude) then measured what the file is *for* and found: nothing reads it; the certified foreign-release path
already runs without it; the fallback branch was byte-for-byte that design and its own test proved a full 2026 build
delivers on it. Keeping (a) meant ~65 lines of security-grade filesystem policy across three OSes, a new public
function, an env knob whose documented read-side target (`assets/schema_cache`, user-owned `755`) *passes* the
private-dir check so the write would land inside the bundle and ship in the zip, 160 lines of adversarial tests, and
two behavioural tiers forever. Retiring (a) is −6 net lines in the engine and one behaviour.

It also closes a documented hazard instead of preserving it: `docs/inbox/install-schema.md`'s decision table
(row 5) — the engine's `load_schema(path=DEFAULT_PATH)` binds its default at *definition* time, so once (a)
re-pointed the module global, a held original `load_schema()` on a bare machine compared the old corpus path with the
new global, skipped the bundled fallback and `open()`ed the absent corpus. With the global never re-pointed, that call
now takes the fallback. That table measured "retire (b), keep (a)" and "retire (a)+(b)"; "retire (a), keep (b)+(c)"
is the variant it never measured and the one this stream proves — all three of its reasons for keeping (b) stand
untouched (a note under this stream's name is appended there).

## Evidence

**Bare surface, second OS user — the issue's exact scenario** (this cloud image; `tekton-plugin.zip` rebuilt by
`tools/sync_plugin.py` from each tree and unzipped root-owned/world-readable; a private `TMPDIR=/tmp/t208` (`1777`)
holding a **root-owned `755`, empty `tekton-schema-cache/`**; system Python 3.11.15; run as `nobody` (uid 65534)):

```
runuser -u nobody -- env -i PATH=… HOME=/tmp/t208/home TMPDIR=/tmp/t208 LANG=C.UTF-8 \
  python3 -I skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 2 panels" --out … --json
```

| | BEFORE (`main` c3ed04e) | AFTER (this branch) |
|---|---|---|
| exit / `go.exit_code` | **3 / 3** | **0 / 0** |
| `result.status` | `FAILED (schema install from base failed: PermissionError: [Errno 13] Permission denied: '/tmp/t208/tekton-schema-cache/Formats_Latest_6459a9a93ebde32c.bin')` | `PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)` |
| `result.files` | `{}` | `{families_dir: …/families, combined: …/prompt_room.rvt}` |
| `result.errors` | the same sentence | `[]` |
| wall / `job_seconds` | 0.75 s (died) | 3.49 s / 3.32 |
| stderr | 0 bytes | 0 bytes |
| written under `TMPDIR` | — | **nothing** (no `tekton-schema-cache-*` of any kind); 0 `__pycache__` in the read-only plugin dir |
| delivered file | none | `tools/rvt_validate.py … --json` → `ok: true`, `{error: 0, warning: 1, info: 2}` (the warning is the known Extensible-Storage decoder gap) — "validates 0 errors", not "loads" (rule 4) |

(The intermediate per-user-cache build measured the same AFTER — exit 0, 3.36 s — plus a squat case: root
pre-creating `tekton-schema-cache-65534` still delivered via the memory tier with the directory left empty. Recorded
because it is what showed the file buys nothing: identical job time with and without it.)

**In process.** `tests/test_install_schema_208.py` (2 rows): row 1 booby-traps `builtins.open` (any write mode),
`os.makedirs`, `os.mkdir`, `tempfile.gettempdir`, `tempfile.mkstemp` to raise `PermissionError` for the duration of
a fresh `install_schema()` — it completes, `DEFAULT_PATH` is unchanged, `"blob"` is not retained, the report line
is the one above, every default-path loader (`schema/objects/encode/adocument`, no-arg / `None` / the default path)
answers with the installed object, `schema_available()` is `True`, and a second call is `["(already installed)"]`;
row 2 is the issue's DONE row whole — fresh install, then a real prompt build on the native pin: `ok`, combined
`.rvt` on disk, `DEFAULT_PATH` still untouched. Engine swap over `main`'s `standalone.py`: **2 failed** (row 1: the
trapped `makedirs` raises straight through the old step (a); row 2: `DEFAULT_PATH` re-pointed at
`/tmp/tekton-…93ebde32c.bin`); over this branch: **2 passed** (2.9 s, 2.8 of it the build).

## Gates (final head)

* `tests/test_install_schema_208.py tests/test_frontdoor_standalone.py tests/test_lazy_schema_wrapper.py`: 14 passed / 1 skipped.
* wider ring — `tests/test_frontdoor.py tests/test_frontdoor_209.py tests/test_conftest_scaffolding.py
  tests/test_convert_combo.py tests/test_coldstart.py tests/test_bootstrap.py tests/test_plugin_sync.py
  tests/test_schema_gate.py tests/test_schema_memo.py tests/test_required_settings.py tests/test_rvt_analyze.py
  tests/test_surface_perf.py tests/test_edit_text_release.py` (`RVT_SKIP_LARGE=1`): **197 passed / 14 skipped**.
* `tools/sync_plugin.py` (2 files mirrored, deny-audit clean, identity scan 82 hits / 0 mismatches, zip 5389 KB) →
  `--check`: in sync; `plugin/scripts/validate_plugin.py`: PASS (25 assertions).
* `/simplify` ran (reuse / simplification / efficiency / altitude); altitude's finding *is* the design above;
  efficiency confirmed the retired file saved no work (a warm re-entry's remaining 1.7 ms is `bundled_base_path()`'s
  per-call sha256 of the base — pre-existing, filed below). `/verify` surfaces: bare-unzip `go` (above), validator on
  the delivered file, the front door via the suites.

## Follow-ups (filed as issues, `Refs #208`)

* `install_schema()`'s idempotent re-entry still costs ~1.7 ms because `bundled_schema()` → `bundled_base_path()`
  re-hashes the 581 KB pinned base on every call before the "(already installed)" early-out; a job re-enters it from
  several callers. Cheap to fix (check `_SCHEMA_STATE` before resolving), perf-stream shaped (S-2026-08-09-g wants a
  bench before/after).
* Test scaffolding: the "reinstall the schema chokepoints and restore them" fixture now exists in three test modules
  (`test_frontdoor_standalone` inline, `test_lazy_schema_wrapper::lazy`, `test_install_schema_208::reinstall`) — a
  `schema_reinstall` fixture in `tests/conftest.py` is the third-copy consolidation (`area:process`, P2).

## BRANCH STATE

* Branch `cam/208-schema-cache-peruser` from `main` @ c3ed04e; files: `src/rvt/frontdoor/standalone.py`,
  `src/rvt/frontdoor/release_ctx.py` (−1 dead entry), `plugin/skills/_shared/tekton_schema.py`,
  `tests/test_install_schema_208.py` (new), `tests/ci_shard.d/208-install-schema-in-memory.txt` (new),
  `tests/test_frontdoor_standalone.py`, `tests/test_lazy_schema_wrapper.py`, `docs/inbox/schema-cache-peruser.md`
  (this), notes in `docs/inbox/install-schema.md` / `docs/inbox/standalone.md`, mirrors under `plugin/lib/` by
  `tools/sync_plugin.py`.
* Shipped vs staged: engine + plugin behaviour change ships with the merge; nothing viewer-gated (no `.rvt` bytes
  change — the schema served is the same object either way; validator counts on the delivered file identical
  before/after for root).
* Gates: as above, all green on the final head; session-hosted CI + independent review recorded on the PR.
