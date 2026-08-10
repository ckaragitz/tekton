# install-schema — `install_schema()` stops answering explicit paths with the installed schema (#315)

Stream: `install-schema` · issue #315 (follow-up of #298 / PR #316) · PG3 / PG6 · size S ·
territory: `src/rvt/frontdoor/standalone.py` (`install_schema` step (b) + the 8-line
`default_schema_loader` factory), `src/rvt/frontdoor/release_ctx.py` (`_load_schema_ctx` only,
argued below), `src/rvt/schema.py` (+1 four-line function `load_schema_file`, argued below),
`tests/test_frontdoor_standalone.py`, this record, regenerated
`plugin/lib/src/rvt/{schema,frontdoor/standalone,frontdoor/release_ctx}.py`.
Not touched: `tests/test_schema_gate.py` (see Decision), `src/rvt/frontdoor/base.py`,
`src/rvt/versions/**`, `plugin/skills/_shared/**` (follow-up #376).

## What was built

* **One rule for every chokepoint wrapper: `standalone.default_schema_loader(schema,
  *default_paths)`** returns the `load_schema` replacement: the no-arg call and the named
  default paths answer with `schema` (the *installed base's* class map, the in-memory object);
  **any other path is parsed verbatim** by `rvt.schema.load_schema_file(path)`, so a path that
  does not exist raises `FileNotFoundError` naming it and is never answered with this release's
  schema.
* **`standalone.install_schema()` step (b)** = `default_schema_loader(schema, old_default,
  cache_file)` installed on `rvt.schema` / `rvt.objects` / `rvt.encode` / `rvt.adocument` as
  before. Gone: the closure's `or not os.path.isfile(path): return schema` clause (a typo'd
  2025/2024 schema path silently got whatever release was installed) and its `orig_load`
  delegation to whichever wrapper it had replaced.
* **`release_ctx._load_schema_ctx`** (the scoped + restored twin inside `release_build_context`)
  carried the identical clause and delegation; it is now `SA.default_schema_loader(schema,
  SCHEMA.DEFAULT_PATH)` inside the same `swap(...)` block, restored on exit exactly as before.
  Argued: same bug class, same fix, entirely inside `release_ctx.py`'s own swap; leaving it would
  have kept a silent copy of what #315 removes. (`release_ctx.py` is under `src/rvt/frontdoor/`,
  not the hot `versions/` dir.)
* **`rvt.schema.load_schema_file(path)`** (new, 4 lines; `load_schema` now ends with it —
  behaviour-neutral for `load_schema`). Argued, since `schema.py` was "only if the record argues
  why": the wrappers need a delegation target for explicit paths that is (1) the engine's own
  verbatim `open` + memoized `parse`, and (2) **not** a name any wrapper swaps. Delegating to the
  previously installed `load_schema` — what both closures did — is a chain, and on the product's
  `go` path the link below the bundled wrapper is the plugin's lazy wrapper
  (`plugin/skills/_shared/tekton_schema.py`, armed by `tekton_env.ensure_engine()` first), whose
  rule for a missing path is "run `install_schema()`, then re-ask `rvt.schema.load_schema`" —
  i.e. the bundled wrapper again. Measured on this branch by simulating exactly that chain with
  the `isfile` clause dropped: **`RecursionError` after 0.77 s**, which the lazy wrapper's
  `except Exception` then reports as *"FileNotFoundError: … the bundled-base fallback failed
  (RecursionError: maximum recursion depth exceeded) — the plugin bundle is incomplete"* (false:
  the bundle is fine, the path was wrong). A leaf loader makes every wrapper a leaf. My first cut
  put those three lines in `standalone.py`; two independent `/simplify` reviewers (simplification,
  altitude) flagged that as pure schema I/O living laterally in `frontdoor/` and duplicating
  `load_schema`'s tail, so it moved to its natural home. `schema.py` remains the sole owner of
  the *fallback policy*; nothing about `schema_available()` / the bundled fallback changed.
* **Tests** (`tests/test_frontdoor_standalone.py`): `test_install_schema_seeds_every_chokepoint`
  kept and extended to the contract — no-arg / `None` / `DEFAULT_PATH` (= the cache file) return
  the *same* installed object; an explicit missing path raises `FileNotFoundError` with
  `.filename`; an explicit existing copy of the stream loads that file (same sha). New
  `test_install_schema_behind_the_plugins_lazy_wrapper` arms the real
  `plugin/skills/_shared/tekton_schema.py` first (the `go` order), then a full `install_schema()`,
  and asserts the installed object (`is SA.bundled_schema()`) for the default calls plus
  `FileNotFoundError` through `rvt.schema.load_schema`, `rvt.objects.load_schema` **and a held
  reference to the lazy wrapper**; all four `load_schema` names, `DEFAULT_PATH`, the lazy flag and
  `_SCHEMA_STATE` are monkeypatch-restored; passes in either order with its neighbour and with
  `test_schema_gate.py` after it.

## Decision — step (b) is NOT retired (reduced instead), with the measurements that decide it

DONE (b) asked whether step (b) can go entirely (keep (a)'s `DEFAULT_PATH` → cache-file re-point
and (c)'s singleton seeding; let the engine's native `load_schema()` fallback serve no-arg
calls). Measured in-process on this corpus-less cloud clone (`scratchpad/bench/variants.py`, one
fresh process per row; the product's no-arg chokepoint `ObjectDecoder()` × 200 after
`install_schema(base)`; Python 3.11.15; "retire" rows produced by undoing the swap / the re-point
right after `install_schema` returned):

| variant | base installed | no-arg `ObjectDecoder()` | schema served | explicit missing path |
|---|---|---|---|---|
| OLD (`main` e54f13f) | G_ABPD (2026 pin) | 0.8 µs/call | installed ✔ | **returned the schema (silent)** |
| OLD (`main`) | G_ABPD_2025 | 1.0 µs/call | installed ✔ | **returned the 2025 schema (silent)** |
| **this PR** | G_ABPD | 0.8 µs/call | installed ✔ | `FileNotFoundError` |
| **this PR** | G_ABPD_2025 | 0.9 µs/call | installed ✔ (`c964f9aa…`) | `FileNotFoundError` |
| retire (b), keep (a) | either | **`FileNotFoundError: …/extracted/…/000.bin`** | — | `FileNotFoundError` |
| retire (a)+(b) | G_ABPD | **1668 µs/call** | 2026 ✔ | `FileNotFoundError` |
| retire (a)+(b) | G_ABPD_2025 | **2596 µs/call** | **2026 ✘ (installed was 2025)** | `FileNotFoundError` |

Three independent reasons, any one sufficient:

1. **Not redundant.** The native fallback serves the *pinned 2026 constant*; step (b) serves *the
   installed base's* schema. `install_schema(base_path)` runs with a per-release base
   (`build.py::_build_intent_inner(opts.base.path)`, `standalone.activate`) and with a user's own
   project (`convert/add_to_project._install_target_schema(target_path)` — "the TARGET's own
   embedded schema"). Retired, every no-arg `ObjectDecoder()` / `get_decoder()` in `mutate`,
   `regadd`, `manipulate`, `genesis.types`, `commit`, … decodes a 2025 target against 2026 class
   ordinals (last row).
2. **Retiring (b) alone breaks the bare surface.** `rvt.schema.load_schema(path=DEFAULT_PATH)`
   binds its default at *definition* time; once (a) re-points the module global to the cache
   file, a no-arg native call compares the old corpus path with the new global, skips the
   fallback and `open()`s the absent corpus (row 5). Making that work means changing
   `load_schema`'s signature/policy — pointless given 1.
3. **Latency (S-2026-08-09-g).** Even where it returns the right bytes, the native no-arg path
   costs path probes + a sha256 of the 580 KB base per call: ~2000× the in-memory answer, on a
   chokepoint a job constructs dozens of times.

So (b) stays, minus the swallow and the delegation chain. Consequently DONE (c) does not trigger:
`tests/test_schema_gate.py` keeps its collection-time `LOAD_SCHEMA` binding and is untouched.

## Evidence — bare-surface before/after (`tools/surface_bench.py`; S-2026-08-09-g)

Same VM (4 vCPU, Python 3.11.15), same procedure both sides: `tools/sync_plugin.py` builds
`tekton-plugin.zip` from the tree (`main` e54f13f → *before*; this branch's final head →
*after*), then `surface_bench.py --zip <zip> --jobs preflight,go-author-prompt,go-author-6panels,go-edit`
**three full runs each**, machine otherwise idle; medians of job wall time (individual runs kept
in the session scratchpad `bench/{before,after2}_N.json`). Every cell PASS on both sides.

| surface | job | BEFORE median (3 runs) | AFTER median (3 runs) | Δ |
|---|---|---|---|---|
| cowork (bare python, persistent) | preflight | 0.116 s (0.136 / 0.102 / 0.116) | 0.103 s (0.103 / 0.096 / 0.103) | −0.01 |
| cowork | go-author-prompt | 3.159 s (3.159 / 2.921 / 3.452) | 3.043 s (3.025 / 3.054 / 3.043) | −0.12 |
| cowork | go-author-6panels | 4.750 s (4.750 / 4.592 / 4.780) | 4.490 s (4.505 / 4.452 / 4.490) | −0.26 |
| cowork | go-edit | 1.010 s (1.048 / 1.010 / 0.974) | 0.966 s (0.966 / 0.927 / 0.997) | −0.04 |
| codeexec (fresh extract per call) | preflight | 0.112 s | 0.105 s | −0.01 |
| codeexec | go-author-prompt | 3.161 s | 3.016 s | −0.15 |
| codeexec | go-author-6panels | 5.521 s | 5.039 s | −0.48 |
| codeexec | go-edit | 1.336 s | 1.254 s | −0.08 |
| local (repo, warm) | preflight | 0.081 s | 0.068 s | −0.01 |
| local | go-author-prompt | 2.709 s | 2.457 s | −0.25 |
| local | go-author-6panels | 4.587 s | 4.527 s | −0.06 |
| local | go-edit | 0.953 s | 0.962 s | +0.01 |

Read as: **no slowdown anywhere** (the one +0.01 s is inside run-to-run spread; the small minus
signs are VM noise, not a claimed speed-up — the hot no-arg path is the same tuple test as before,
row 3 of the variants table). An intermediate AFTER on the pre-`/simplify` head (helper in
`standalone.py`) gave the same picture (e.g. cowork go-author-prompt 3.106 s, 6panels 4.752 s).

## Gates (final head)

* `RVT_SKIP_LARGE=1 pytest tests/test_frontdoor_standalone.py tests/test_schema_gate.py
  tests/test_coldstart.py tests/test_bootstrap.py tests/test_famload_batch.py
  tests/test_bare_family_validate.py tests/test_schema_memo.py -q -rs` → **101 passed / 1 skipped
  / 0 failed in 42 s** (the skip: `test_frontdoor_standalone.py:316` "research machine only";
  `test_schema_memo.py` added because `schema.py` changed; the six DONE (d) files alone: 90 / 1
  / 0 on the pre-simplify head). A first post-simplify run failed 3 clean-env tests with
  `ImportError: cannot import name 'load_schema_file' from rvt.schema (…/plugin/lib/…)` — the
  fixture copies the *plugin mirror*, stale until `sync_plugin.py` ran; re-synced → green. Noted
  because it is exactly the "edit source, regenerate mirror" rule of CLAUDE.md §3b doing its job.
* `tools/sync_plugin.py` → synced 3 files (`schema.py`, `frontdoor/standalone.py`,
  `frontdoor/release_ctx.py`), deny-audit clean, assets verified, zip rebuilt (5156 KB);
  `--check` → in sync; `plugin/scripts/validate_plugin.py` → PASS (25 assertions);
  `tools/dev/check_portable_paths.py` → ok (2852 paths).
* `/verify` from a **bare unzip of the rebuilt zip with system `python3` 3.11**, no repo on the
  path, `PYTHONPATH`/`TEKTON_ROOT`/`RVT_*` unset:
  `skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/j1 --json`
  → exit 0, **one JSON document**, preflight line `tekton: READY | python 3.11.15 | engine
  bundled | genesis verified (Revit 2026) | family-donor missing | out-dir OK | 0.059s`,
  `go.ready true`, job 5.0 s, `result.ok true`, `errors []`, `prompt_room.rvt` delivered (stamped
  PROOF-ONLY as always); `tools/rvt_validate.py` on it → ok, **0 errors** / 1 warning (the known
  DataStorage Extensible-Storage decoder gap) / 2 info. And the DONE (a) one-liner from that same
  unzip through the plugin's own bootstrap (`tekton_env.ensure_engine()` → `install_schema()`):
  `load_schema()` → source `assets/genesis/G_ABPD.rvt#Formats/Latest`, 4690 classes, sha
  `6459a9a93ebde32c…`; `load_schema('/nonexistent/2025.bin')` → **`FileNotFoundError:
  /nonexistent/2025.bin`**; `objects.load_schema() is load_schema()` → True.
* `/simplify` (4 angles): reuse — clean; efficiency — clean (hot path unchanged, closures now
  capture less: the `orig_load` chain that pinned earlier wrappers/schemas alive is gone);
  simplification + altitude — applied: one `default_schema_loader` factory instead of two
  hand-synchronised closures, verbatim loader hoisted into `rvt.schema`, narrating comments cut
  to one rule line, test scaffolding reduced (`syspath_prepend` + plain import,
  `shutil.copyfile`, contract asserted as `is SA.bundled_schema()`), `test_schema_gate.py` left
  untouched; follow-up filed rather than footnoted (#376).

## Findings / observations

* **Follow-up #376** (`area:plugin`, outside this territory): the plugin's lazy wrapper still has
  the older shape ("any non-file path → `install_schema()`, then re-ask `rvt.schema.load_schema`").
  Fine in the `go` order (locked by the new test), but armed *after* a completed
  `install_schema()` in a long-lived process a missing explicit path re-enters the wrapper itself
  (install returns "(already installed)" without re-swapping). Not reachable from any shipped
  flow today; its fix is to adopt `default_schema_loader`'s contract.
* No product-path behaviour change except the intended one: after `install_schema()` (or inside a
  release context) an explicit schema path that does not exist raises `FileNotFoundError`
  instead of silently decoding against the installed release.

## Open questions

None.

## BRANCH STATE

* Branch `cam/315-install-schema` from `origin/main@e54f13f`; PR closes #315; follow-up #376 filed.
* Files: `src/rvt/schema.py` (+`load_schema_file`; `load_schema` ends with it),
  `src/rvt/frontdoor/standalone.py` (`default_schema_loader`; step (b) uses it; docstring),
  `src/rvt/frontdoor/release_ctx.py` (`_load_schema_ctx` = the factory),
  `tests/test_frontdoor_standalone.py` (one test extended, one added), this record,
  `plugin/lib/src/rvt/{schema,frontdoor/standalone,frontdoor/release_ctx}.py` (regenerated by
  `tools/sync_plugin.py`, never hand-edited).
* Gates: as above — 101 / 1 skipped / 0 failed; sync `--check` clean; validate_plugin PASS;
  portable paths ok; bare-unzip `go author` READY + 0 validation errors; before/after bench table
  above (no slowdown). GitHub-hosted checks do not exist under steer #302; the tech-lead session
  runs the shard on the PR head and an independent review.
* Shipped vs staged: everything ships with the merge; no `.rvt`/`.rfa` output committed, no
  viewer claim, no probe batch. No shard drop-in: no new test file was created;
  `tests/test_schema_gate.py` (untouched) is already first in the shard, and
  `tests/test_frontdoor_standalone.py` stays out of it as before (it carries two ~4–8 s
  subprocess E2E builds; the two contract tests themselves run in 0.25 s).

---

## eng #376 — 2026-08-10 — the plugin's lazy wrapper adopts the same contract

Stream: `lazy-schema-wrapper` · issue #376 (the follow-up filed above) · PG3 · size XS ·
territory: `plugin/skills/_shared/tekton_schema.py` (hand-authored source, not a mirror),
`tests/test_lazy_schema_wrapper.py` (new) + `tests/ci_shard.d/376-lazy-schema-wrapper.txt`,
this section. Not touched: `src/rvt/**` (reuses #315's `rvt.schema.load_schema_file` and
`standalone.install_schema` / `bundled_schema` as they are), `tekton_env.py` (held by #267),
any SKILL.md.

### What was built

* **`tekton_schema.install()`'s `_load_schema_lazy(path=None)`** now has exactly
  `default_schema_loader`'s shape, with "the installed schema" meaning "activate
  `install_schema()` once, then the schema it installed":
  1. any path that is not `None` / the `DEFAULT_PATH` captured at arm time / the current
     `rvt.schema.DEFAULT_PATH` → `rvt.schema.load_schema_file(path)` — verbatim, never
     activates the fallback, a missing one raises `FileNotFoundError` with `.filename` = that
     path (an engine that predates `load_schema_file` degrades to the wrapped `load_schema`,
     which is verbatim for explicit paths and is not the wrapper);
  2. the default path when the captured default is a real file (research corpus, **or the
     cache file a completed `install_schema()` left as `DEFAULT_PATH` — the armed-after case**)
     → the wrapped loader answers it directly (in memory for the bundled loader; no
     `install_schema()` call, so a host that installed a *different* base is not re-seeded);
  3. the default path on a bare machine → `standalone.install_schema()` once (it re-points
     `rvt.schema/objects/encode/adocument.load_schema` past the wrapper, so the module-level
     names never reach the wrapper again) and `return standalone.bundled_schema()` — the very
     object it installed. **Nothing in the wrapper calls `rvt.schema.load_schema` any more**,
     so there is no path back into itself whatever order it was armed in.
  The signature lost its `path: str = orig_default, _orig=orig_load` defaults (closure
  references instead; `None` is now a first-class default like every other chokepoint loader).
* **Reproduced first** (this branch, before the change; in-process, corpus-less cloud clone):
  `SA.install_schema()` → `tekton_schema.install()` (arms over the bundled loader; status
  `corpus-present` because `DEFAULT_PATH` is the cache file) → `objects.load_schema(None)`
  **and** `schema.load_schema('/nonexistent/x.bin')` both → ~1000 frames of
  `_load_schema_lazy → _schema.load_schema(path)` → `RecursionError` inside
  `bundled_base_path`'s `sha256_of` → reported as *"FileNotFoundError: schema stream not
  found at None and the bundled-base fallback failed (RecursionError: …) — the plugin bundle
  is incomplete"*. So the finding above understated it slightly: in the armed-after order the
  `None` spelling of the default recursed too (only the no-arg call, whose default was the
  existing cache file, escaped through the `isfile` branch). After the change: `None` /
  no-arg / `DEFAULT_PATH` → the installed object (`is SA.bundled_schema()`), missing explicit
  path → `FileNotFoundError('/nonexistent/x.bin')` in 0.000 s with `__cause__ None`.
* **Tests** — new `tests/test_lazy_schema_wrapper.py` (2 tests, 0.20 s, in-process, only the
  pinned plugin base's bytes; every swapped name — the four `load_schema`s, `DEFAULT_PATH`,
  the arm flag, `_SCHEMA_STATE` — monkeypatch-restored, same scaffolding as #315's test):
  `test_armed_after_a_completed_install` (DONE (b): install, then arm; default family `is`
  the installed object through `schema`/`objects`/`adocument`; missing explicit path raises
  `FileNotFoundError` with `.filename` and no `__cause__` through three module names; an
  existing explicit copy parses verbatim to the same sha) and
  `test_explicit_path_never_activates_the_fallback` (the `go` order made deterministic by
  pointing `DEFAULT_PATH` at an absent tmp path: a missing explicit path raises and
  `_SCHEMA_STATE` shows **no** install happened; the first `ObjectDecoder()` installs once,
  re-points the module names past the wrapper, and a held reference to the wrapper keeps
  answering the same object / raising for missing paths; re-arming says `already`). Both
  tests **fail on `main`'s wrapper** (`RecursionError` → the false "bundle is incomplete"
  `FileNotFoundError`) and pass on this branch; order-independent with
  `test_schema_gate.py` and #315's two contract tests in either direction (8 passed both
  ways). Shard drop-in `tests/ci_shard.d/376-lazy-schema-wrapper.txt`.
