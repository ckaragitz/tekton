# frontdoor: a late route exception still yields the ONE result naming the delivered file (#209)

Stream: `cam/209-frontdoor-late-exception` · issue #209 (P1, `area:frontdoor` `area:plugin`, from steer #108's
requirements sweep, program goal PG1) · territory `src/rvt/frontdoor/__init__.py`, `tests/test_frontdoor_209.py`
(+ `tests/ci_shard.d/209-frontdoor-late-exception.txt`, one `ADOPTERS` line in `tests/test_conftest_scaffolding.py`),
this record. `tools/frontdoor.py` (hot) untouched — it
already prints `r.as_json()` for whatever `run()` returns.

## What was wrong (hard rule 1, seen from the stranger's side)

`rvt.frontdoor.run()` called the route function bare. Anything that threw *after* the build — measured: the
`UnicodeEncodeError` `manifest.write_manifest` raises writing `MANIFEST.md` (`open(mp, "w")`, no `encoding=`) on a
non-UTF-8 locale (#29); equally a full disk or a read-only subdirectory — left `run()` by traceback. The CLI's generic
`except Exception: traceback.print_exc(); return EX_ERR` then printed no `--json` document, the plugin's `go` reported
`result: null` with exit 1, and the skill told its user the job had failed — while `prompt_room.rvt`, `families/` and
`intent.json` sat in `--out`. Delivered to disk, withheld from the conversation.

## What was built

`run()` now creates the `AuthorResult` shell itself and **hands it to the route** (`_route_prompt` / `_route_ifc` /
`_route_rvt` take `res`; they used to construct an identical one locally — `_route_rvt_inner`, `_refuse_rvt_input`,
`InputReleaseRefused.result`, `build_intent → _build_intent_inner` and the router's `impl(res, …)` already work this
way), and the routes gather their `errors` directly on it. Then it guards the call:

* `FrontDoorError` (incl. `InputReleaseRefused`, #176) and `BaseError` **re-raise unchanged** — a refused *request*
  keeps its one line and the CLI's usage-error exit 2, no traceback, exactly as before;
* any other `Exception` → `_failed_late(res, exc)`: everything the route had recorded before it died survives *as
  recorded* — `files` exactly as `build_intent` / `run_edit` named them (nothing is re-guessed from disk, so
  `edit.py`'s raw-basename `Office Tower.edited.rvt` and `build.py`'s withholding of a structurally invalid
  `-equipment.rvt` both hold), `intent_json`, `handoff`, the manifest dict (so `as_json()` still carries the release
  line and the PROOF-ONLY `stamps`), the errors gathered so far — and only the verdict is overwritten:
  `FAILED (post-build error: <Type>: <message>; delivered anyway: prompt_room.rvt, families/)` (files first,
  directories last), or `FAILED (<Type>: <message>; no output file was recorded)` when the route had recorded no file. The cause
  clause is `rvt._clause.cause_clause` (the engine's one clip rule, #587); `errors` gains one relayable sentence
  (`prompt route raised UnicodeEncodeError: …`) plus the traceback's last six frames — inside the document instead of
  replacing it. `KeyboardInterrupt`/`SystemExit` are not `Exception`s and still propagate.

Why not the first draft (a table of per-route deliverable names re-read from disk with an mtime filter): the
`/simplify` pass (reuse + simplification + altitude, independently) showed it was a second copy of the naming law and
wrong on arrival — the `--rvt` route names its output from the *raw* stem while the table predicted the sanitised one
(`Office Tower.rvt` → looks for `Office_Tower.edited.rvt`, reports "no output file was recorded" with the file on disk: #209
reintroduced), the `--ifc` fallback copy is `basename(source)`, not `<stem>.ifc`, and the scan dropped the manifest
the route already held (no stamps/release in the FAILED document). Passing `res` in needs no names and no mtimes.

Router (`route run … --output rvt`, which composes `author()`): the author step now *returns* — its step record says
`ok: True` (it ran) — with the FAILED status, the delivered file and the sentence in `errors`, where it used to raise
into `_StepFailed`; `RouteResult.ok` is `False` either way. `_r_ifc_build_then_edit` reads `r1.files["combined"]`,
which the build only records for a complete combined file, so it never edits a half-written one. Not done, on
purpose: nothing retries the manifest write (the crash may recur or have truncated it — `as_json()["manifest"] == {}`
is pinned); the underlying #29 encoding error is its own issue — this change is what makes *any* such late error
survivable.

## Evidence

Engine swap — `tests/test_frontdoor_209.py` (8 rows) over `origin/main`'s `src/rvt/frontdoor/__init__.py`:
**8 failed** (2 of them only because the refused-request stubs use the new 3-argument route signature); over this
branch: **8 passed in 3.0 s** (one real prompt build on the 2026 pin; every other row stubs the route).

In-process repro (`FD.author(prompt="an electrical room with 2 panels", no_handoff=True)` with `write_manifest`
raising the #29 `UnicodeEncodeError`):

| | BEFORE (`c9e124d`) | AFTER |
|---|---|---|
| `run()` | `UnicodeEncodeError` escapes | returns the `AuthorResult` it handed the route |
| on disk | `_stages build.log families intent.json prompt_room.rvt` | same |
| `status` | — | `FAILED (post-build error: UnicodeEncodeError: 'ascii' codec can't encode character '—' in position 0: ordinal not in range(128); delivered anyway: prompt_room.rvt, families/)` |
| `files` | — | `{families_dir: …/families, combined: …/prompt_room.rvt}` (as `build_intent` named them) |
| `as_json()["stamps"]` | — | `['PROOF-ONLY: generated-family INSTANCES on a composed genesis base (open cell, …)', 'PROOF-ONLY, NOT-DELIVERABLE']`; `release` block present (`opens_in`, `target_support`, …) |
| `errors` | — | `[…, 'prompt route raised UnicodeEncodeError: …', 'Traceback (most recent call last): … in _route_prompt … res.manifest_paths = MF.write_manifest(…']` |

Bare surface, DONE (3) — `tekton-plugin.zip` rebuilt by `tools/sync_plugin.py`, unzipped to a temp dir (its
`lib/src/rvt/frontdoor/__init__.py` byte-identical to this branch's), system Python 3.11, a genuinely ASCII locale
(`-I` ignores `PYTHONUTF8`, so UTF-8 mode is switched off with `-X utf8=0`; probe: `utf8_mode=0
preferredencoding=ANSI_X3.4-1968 stdout=ascii fs=ascii`):

```
LC_ALL=C PYTHONCOERCECLOCALE=0 python3 -I -X utf8=0 skills/tekton-author/scripts/_bootstrap.py \
    go author --prompt "an electrical room with 2 panels" --out out/jascii --json
```

| | BEFORE (main's `frontdoor/__init__.py` dropped into the same unzip) | AFTER |
|---|---|---|
| exit / `go.exit_code` | 1 / 1 | 3 / 3 (`INCOMPLETE`) |
| `result` | `null` | the document: `status` = `FAILED (post-build error: UnicodeEncodeError: 'ascii' codec can't encode character '—' in position 23: ordinal not in range(128); delivered anyway: prompt_room.rvt, families/)`, `files` = `{families_dir: out/jascii/families, combined: out/jascii/prompt_room.rvt}`, `stamps` = the two PROOF-ONLY stamps, `release.opens_in` = `Revit 2026 and newer -- never an older Revit`, `errors[0]` = the note the route had gathered before dying (`handoff package failed: UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2 …`) |
| stderr | `Traceback … UnicodeEncodeError: 'ascii' codec can't encode character '—' in position 23` | empty (0 bytes) |
| on disk | `MANIFEST.md(truncated) _stages build.log families intent.json manifest.json prompt_room.rvt scene-brief.json` | same |
| `job_seconds` | — | 3.42 |

The delivered `out/jascii/prompt_room.rvt` validates: `tools/rvt_validate.py … --json` → `ok: true`, counts
`{error: 0, warning: 1, info: 2}` (the warning is the known Extensible-Storage decoder gap), 3402 elements decoded —
"validates 0 errors", not "loads" (rule 4).

## CI / review rounds (session-hosted, regime #302)

* head `52de9df`: sandboxed CI **fail** — `1 failed, 2701 passed, 132 skipped, 3 xfailed` (571 s): `tests/test_conftest_scaffolding.py::test_every_module_on_the_leak_guard_enters_a_context` — the new module requested
  `no_release_leak` while entering no release context (a native 2026 build enters none; law #605/#707). Independent
  review 🟡 nits only (aliasing verified success-path neutral, refusals verified to propagate, mirror byte-identical);
  nits: the empty-files wording could over-claim in the sliver before `res.files` is assigned; status may exceed the
  160-char reason convention (bounded by `cause_clause`); the guard exercised no real unwind.
* fix-up head: the one real-build row now builds for the FIRST FOREIGN certified pin (`target_version=2024` here), so
  the front door enters `release_build_context` before the manifest write dies and the guard (with the write-side
  `context_constants` watch) proves nothing stayed entered — `release.requested == release.output == 2024` in the
  FAILED document; the module stands in the scaffolding law's `ADOPTERS` with that reason; empty-files wording is now
  `FAILED (<Type>: <message>; no output file was recorded)`. `tests/test_frontdoor_209.py
  tests/test_conftest_scaffolding.py` → 28 passed (6.0 s). Sandboxed CI of head `ddcae5d`: **pass** — `2703 passed, 132 skipped,
  3 xfailed` (579 s), merge with main clean; delta review 🟡 (verified: the context is entered for 2024 and exits normally before
  the crash, so the guard proves the END STATE — a foreign enter/exit plus a late crash leaves nothing entered — not an exception
  unwinding *through* the context; two stale wordings in the test name / drop-in comment) → fixed in the next head (comment +
  rename only).

## Gates run

* `tests/test_frontdoor_209.py`: 8 passed (3.0 s) — real build + manifest crash (files, stamps, release, traceback
  tail); crash before the build ("no output file was recorded", a stale `prompt_room.rvt` in a reused `--out` never named);
  verdict overwritten while earlier errors survive (ENOSPC wording); the `--rvt` route's raw-basename `edited` file;
  `FrontDoorError`/`BaseError` propagate; the router relays the salvaged result; the CLI child prints the document
  with exit 3 and no traceback on stderr.
* stream-local: `RVT_SKIP_LARGE=1 pytest tests/test_frontdoor.py tests/test_frontdoor_209.py
  tests/test_frontdoor_json_strict.py tests/test_out_dir_guard.py tests/test_router.py tests/test_edit_text_release.py
  tests/test_intent_faulted.py tests/test_frontdoor_standalone.py tests/test_router_release.py` → **330 passed,
  18 skipped** in 131 s (skips = samples-gated rows, unchanged).
* happy paths on the final engine (the `/verify` recipe): `tools/frontdoor.py author --prompt "an electrical room with 6
  panels" --out out/verify/p --json` → exit 0, `PROOF-ONLY (self-checks PASS; …)`, files `combined` + `families_dir`,
  manifest `json`/`md`/`build.log`, `rvt_validate` → `ok: true {error: 0, warning: 1, info: 2}`; `tools/route.py run
  --output rvt --prompt … --json` → exit 0, `ok: true`, step `rvt.frontdoor:author ok`; bare unzip `go author --prompt
  "an electrical room with 6 panels"` (system Python 3.11) → `ready: true`, exit 0, same status, `job_seconds` 4.44.
* `tools/sync_plugin.py` (1 file synced, deny-audit clean, validation passed, zip rebuilt 5389 KB);
  `tools/sync_plugin.py --check` → in sync; `plugin/scripts/validate_plugin.py` → PASS;
  `tests/test_plugin_sync.py tests/test_records_layout.py tests/test_shard_list.py` → 37 passed;
  `tools/dev/check_portable_paths.py` → `ok: 3119 tracked paths are portable`.

## BRANCH STATE

* files: `src/rvt/frontdoor/__init__.py` (`run()` owns and passes the result; `_failed_late`; routes take `res` and
  gather errors on it), its mirror `plugin/lib/src/rvt/frontdoor/__init__.py` (generated by `tools/sync_plugin.py`),
  `tests/test_frontdoor_209.py`, `tests/ci_shard.d/209-frontdoor-late-exception.txt`, `tests/test_conftest_scaffolding.py`
  (one `ADOPTERS` line), `docs/inbox/frontdoor-late-exception.md`.
* gates: as listed above (module 8 passed; stream-local 330 passed / 18 skipped; plugin sync/structure/records/portable
  green); session-hosted CI + independent review recorded on the PR by the tech-lead loop.
* staged vs shipped: nothing viewer-facing; no ledger change; no new dependency.
