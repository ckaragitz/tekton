# shard-docs-audit — a runtime record of which repo `docs/` files the CI shard opens (stream record)

**Stream:** shard-docs-audit (eng #523). **Date:** 2026-08-10. **Issue:** #523 (Refs #496, #487 (c)).
**Charter:** complement #528's *static* `SHARD_READS` meta-test (`tests/test_ci_fresh.py`, an AST scan of the shard's
sources) with the exact, general instrument: a `sys.addaudithook` recorder in `tests/conftest.py` that sees every
`open` of a file under `<repo>/docs` made by the test process — through a literal, a variable, a glob or `src/`/`tools/`
code alike — attributes it to the test id that made it, and fails the run at session end when a path the CI shard
opened is not matched by `tools/dev/ci_fresh.sh`'s `SHARD_READS` (read from the script, one source of truth). While
in `conftest.py`: give the throwaway-git-repo helpers that `tests/test_shard_list.py` and `tests/test_ci_fresh.py`
each re-implement one home (#487 (c)).

## What landed

1. **`tests/conftest.py` — the recorder (top of the file, installed before the engine imports so an import-time read
   would be seen too).** `DocsReadAudit(root)` is the audit-hook callable: for the one `open` event (raised alike by
   `builtins.open`, `io.open`, `pathlib.Path.open/read_text/read_bytes`, `os.open`, `io.open_code`) it decodes the path
   (str / bytes / PathLike; fds and `None` are not paths), joins a relative one onto `os.getcwd()`, `normpath`s, and if
   the result lies under `<root>/docs/` records `{"docs/…posix path": {(test module, reader id), …}}`. Cost per audited
   event that is not an `open`: one string compare; per `open` of an absolute path without `docs` in it (imports, tmp
   files — nearly all of them): one substring test; the rest pay a `normpath`. It never raises (a raising audit hook
   breaks the `open()` it watches). Attribution: `pytest_collectstart` (a `pytest.Module` collector → module-level
   reads at import belong to that module, e.g. `tests/test_genesis_identity.py`; the session and directory collectors
   have no module and count as session level) and a `tryfirst` `pytest_runtest_protocol` (before logstart/setup, so
   fixture set-up reads belong to the item that triggered them); anything earlier is `<session>`. `RVT_DOCS_AUDIT` is
   parsed once into `DOCS_AUDIT_MODE`: `0`/`off` skips installing the hook (the documented opt-out; not needed — see
   the numbers), `report` prints every recorded read at session end, anything else is plain on. A one-line
   `pytest_report_header` says whether the audit is on, so a CI log states it.
2. **`tests/conftest.py` — the rule, its two channels, and the wiring.** `shard_reads_pattern()` lifts
   `SHARD_READS='…'` out of `tools/dev/ci_fresh.sh` exactly as #528's meta-test does (that test keeps the pattern inside
   the ERE subset Python's `re` reads identically); `ci_shard_files()` is the merged shard via `tools/dev/shard_list.py`
   through the existing `load_tool` (`merge(*from_tree(ROOT))` — the list `session_ci.sh` runs); `rules()` loads and
   caches both once. One classifier (`DocsReadAudit.kind`): a read is **covered** when `SHARD_READS` matches its path;
   otherwise an **offender** — unless it was made under a test *module that is not in the merged shard*, which is
   **unenforced** (recorded and listed, never failed: the full suite legitimately reads more than CI does, e.g.
   `tests/test_genesis_addback.py` → `docs/writer/registry-parity.md` on the owner's machine; inside `session_ci.sh`
   every collected module is in the shard by construction, so the scoping can only under-enforce a mixed *local* run,
   never CI). Two channels apply it. **Per test:** a `trylast` `pytest_runtest_teardown` (after the real teardown, so a
   session fixture's finalizer reads count) asks `offences(context)` and, if the item opened an uncovered enforced
   path, `pytest.fail(...)`s it — the offender is a normal red test (`ERROR at teardown of …`, `N passed, 1 error`) in
   pytest's own tally, which is exactly the line `session_ci.sh` reports on the PR, so an audit trip never reads as
   "all green, infrastructure flaked" (the independent altitude review's main point; the first cut only flipped the
   exit status). **Per session:** `pytest_sessionfinish` runs `judge()` over every recorded read — this is what catches
   the reads no item owns (conftest import, module collection) — and turns an otherwise green run into exit 1 for
   them; if the rules themselves cannot be read (no `SHARD_READS=` line, unreadable shard list) that is a named
   offender too: fail closed. `pytest_terminal_summary` prints the section: always when there are offenders (red,
   `docs-read audit FAILED`, every offending path with **every** reader id under it — never truncated, fixing needs
   them all — and the two ways out), and the whole census under `RVT_DOCS_AUDIT=report`.
3. **`tests/conftest.py` — the shared git helpers.** `GIT_ENV` (fixed identity, `GIT_CONFIG_GLOBAL=/dev/null`,
   `GIT_CONFIG_NOSYSTEM=1`: a developer's signing key, template dir or `init.defaultBranch` never changes a test repo),
   `git(cwd, *args)` → stripped stdout, raising on failure (60 s timeout); `git_commit(repo, {rel: text}, msg,
   delete=())` → the new HEAD sha (append-write, `add -A`, commit — the exact semantics of `test_ci_fresh.py`'s
   `_commit`); `git_init(path)` → an empty repo on `main` (the primitive for rigs with more than one repository —
   `test_ci_fresh.py`'s upstream + clone); `HAVE_GIT`; and the `git_repo` fixture = `git_init(tmp_path/"repo")` or a
   clean skip without git.
4. **`tests/test_docs_read_audit.py`** (7 tests, ~0.7 s, stdlib + git, in the shard via
   `tests/ci_shard.d/523-docs-read-audit.txt`): the recorder on a temp docs tree (absolute / relative-to-cwd / bytes /
   PathLike / un-normalised paths all land on one posix key; fds, `None`, non-`open` events and undecodable arguments
   are ignored without raising; `enter()` attribution for an item, a directory collector and the session fallback); the
   **installed** hook recording this very test's real reads of the ledger through `pathlib`, `io.open`, `os.open` and a
   cwd-relative `open`; the rule through both channels on synthetic reads (`offences` per context and `judge` agree on
   covered / offender / unenforced; the fail-closed verdict when `SHARD_READS` cannot be read, with the per-test channel
   staying quiet) and the report lines (path + every reader named, silence on a clean run); `SHARD_READS` compiled from
   the script matches the ledger and not `STEERING.md`, a script without the line raises, the shard list contains this
   file; the **end-to-end wiring** as a matched pair — a child pytest (its own interpreter, its own hook) runs this
   file's inert self-test reader told, through `$RVT_DOCS_AUDIT_SELFTEST`, to open `docs/STEERING.md` → `1 passed, 1
   error`, `ERROR at teardown of test_zz_selftest_reader` carrying the audit message, exit **1**, and the section with
   `FAIL docs/STEERING.md … <- tests/test_docs_read_audit.py::test_zz_selftest_reader`; the same child told to open the
   ledger → `1 passed`, exit **0**, no error, no section; and one test that uses the `git_repo` fixture (two commits incl.
   a delete, branch `main`, hermetic identity `t <t@t>`, str-or-Path cwd, failure raises). House rule stated in the
   file: real docs names are never spelled as literals there, because #528's static scanner reads that file too and
   would — rightly, for a literal — count them; the self-test's target travels through the environment, which is
   precisely the indirection class only the runtime audit can see.

## Evidence

**The census (whole merged shard, `RVT_DOCS_AUDIT=report`, this branch):** exactly three repo docs files are opened,
all inside `SHARD_READS`, nothing else —
```
=============================== docs-read audit ================================
3 repo docs/ file(s) opened by this test process; judged against SHARD_READS of tools/dev/ci_fresh.sh (#523)
  ok   docs/coverage/viewer-certified.json
         <- tests/test_docs_read_audit.py::test_the_installed_hook_records_real_reads_of_the_ledger_by_this_very_test
         <- tests/test_genesis_identity.py
         <- tests/test_probe_batch.py::test_real_control_generation_is_byte_identical
         <- tests/test_probe_batch.py::test_the_shipped_pins_alias_the_bundled_bases_against_the_real_ledger
         <- tests/test_rfa_load.py::test_matrix_names_the_new_lane_and_keeps_its_evidence_honest
         <- tests/test_router.py::test_audit_classifies_only_the_binary_class_as_soft
         <- tests/test_router.py::test_evidence_self_audit_is_clean
         <- tests/test_router.py::test_render_text_is_the_shared_printer
  ok   docs/process/AUTONOMY.md
         <- tests/test_techlead.py::test_board_render_is_complete_marked_and_stable_across_renders
         <- tests/test_techlead.py::test_engineers_never_merge_and_waves_are_ledgered
  ok   docs/product/PERMUTATION-MATRIX.md
         <- tests/test_router.py::test_open_cell_caveat_names_the_front_door_stamp
         <- tests/test_router.py::test_permutation_matrix_doc_agrees_with_machine_matrix
```
Compared with #528's static census: the *files* agree exactly (ledger, rendered matrix, `AUTONOMY.md`). The *readers*
differ in the way only a runtime instrument can tell: `tests/test_frontdoor_manifest_pin.py` **names** the ledger path
(it compares the manifest's `certification.ledger` string) but never opens it; `tests/test_genesis_identity.py` opens
the ledger at **import** (module level, attributed to the collector) and `tests/test_rfa_load.py::test_matrix_names_the_new_lane_and_keeps_its_evidence_honest` opens it **through `src/rvt/frontdoor/matrix.py`** — the `src/`-reader class the AST scan states as its blind spot, here seen and covered. None of that changes
`SHARD_READS`; it is what "exact" buys.

**Shown to bite (reverted):** appended to `tests/test_shard_list.py` — a shard file — a test whose docs read goes
through a `src/` function and two variables, a shape #528's scanner resolves to nothing it can name:
```
$ tail -4 tests/test_shard_list.py
def test_zz_injected_indirect_docs_read():      # TEMPORARY (#523 bite demo, reverted): a src/ function opens docs/<name> through variables
    from rvt.convert.add_to_project import _sha256
    sub, name = "docs", "STEERING.md"
    assert _sha256(os.path.join(ROOT, sub, name))
$ .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_shard_list.py tests/test_ci_fresh.py::test_SHARD_READS_covers_every_docs_path_the_ci_shard_reads
........................E.                                               [100%]
==================================== ERRORS ====================================
___________ ERROR at teardown of test_zz_injected_indirect_docs_read ___________
docs-read audit (#523): this test opened docs/STEERING.md -- repo docs/ file(s) NOT covered by SHARD_READS in tools/dev/ci_fresh.sh; add them there if the CI shard really needs them, otherwise stop reading them (the session-end section lists every reader)
============================ docs-read audit FAILED ============================
1 repo docs/ file(s) opened by this test process; judged against SHARD_READS of tools/dev/ci_fresh.sh (#523)
  FAIL docs/STEERING.md   (opened by the CI shard, NOT covered by SHARD_READS)
         <- tests/test_shard_list.py::test_zz_injected_indirect_docs_read
Every repo docs/ file the CI shard opens must be matched by SHARD_READS in tools/dev/ci_fresh.sh, or a docs-only
merge touching it between a PR's sandboxed CI run and its merge stays FRESH on a stale verdict (#476/#487).
Ways out: the shard really needs the file -> add it to SHARD_READS there; otherwise stop reading it from the shard.
=========================== short test summary info ============================
ERROR tests/test_shard_list.py::test_zz_injected_indirect_docs_read - Failed:...
25 passed, 1 error in 0.71s
$ echo $?
1
```
25 passed **including #528's static meta-test** (the last dot: blind to this shape, as it says of itself); the
injected test's own assertion passed and the audit made *it* the red one, in the tally and in the exit code, naming
test id and path twice (its own error, and the section). Before the per-test channel existed the same injection gave
`25 passed` + the section + exit 1 — correct but mute in the tally. Reverted; `git status` shows
`tests/test_shard_list.py` unmodified before the commit.
The static meta-test may stay: it is the cheap per-file tripwire that fails *at the offending file* in well under a
second without running the shard, and it also polices what an excused file hands to `open()`; the runtime audit is
the arbiter that has no blind spot for indirect readers and no excuse list. They cost nothing together (below), so
neither is retired.

**Overhead — merged shard wall time, same machine (4 vCPU cloud VM), idle, `RVT_SKIP_LARGE=1 -q -p no:cacheprovider`:**
```
BEFORE  origin/main d75302b (worktree, no audit)               1797 passed, 133 skipped, 3 xfailed in 385.03s   wall 386.2 s
AFTER   first cut (exit-status channel only), audit on            1803 passed, 134 skipped, 3 xfailed in 370.60s   wall 371.7 s
AFTER   first cut, RVT_DOCS_AUDIT=report -rs                      1803 passed, 134 skipped, 3 xfailed in 380.44s   wall 381.6 s
AFTER   final head (per-test channel added), RVT_DOCS_AUDIT=report 1803 passed, 134 skipped, 3 xfailed in 367.45s   wall 368.8 s
(a first BEFORE taken while this session was still editing files: 375.07s — the run-to-run spread on this VM is ~15 s either way)
```
The audited run collects 7 more tests (this stream's file, ~0.7 s of its own incl. two child pytest start-ups). The
hook's own cost is inside run-to-run noise; `RVT_DOCS_AUDIT=0` exists but nothing needs it.

**Gates.** `tests/test_docs_read_audit.py`: 6 passed, 1 skipped (the inert self-test reader) · `tests/test_ci_fresh.py`
(unchanged; its static meta-test scans the new conftest + test file): 20 passed, 2 skipped (gawk/busybox absent on this image) · `tests/test_shard_list.py`:
24 passed · `python3 tools/dev/check_portable_paths.py`: ok · `tools/sync_plugin.py --check`: clean ·
`plugin/scripts/validate_plugin.py`: PASS · whole merged shard with the audit active: **1803 passed, 134 skipped, 3 xfailed** (main: 1797 / 133 / 3 — the difference is this file's 6 + 1 skip), census above, exit 0.

## Findings / limits, stated

- **Subprocess readers are invisible by construction** (an audit hook lives in one interpreter): a test that runs
  `tools/route.py matrix` as a child process and lets *it* read the ledger is seen by neither instrument. Today every
  such child reads only the ledger/matrix (covered). Propagating the hook into children would mean planting a
  `sitecustomize` on `PYTHONPATH` — a different blast radius; not done.
- Reads at session-fixture *teardown* are attributed to the last item that ran (and can make that item the red one);
  reads before collection to `<session>`. A cached or session-scoped reader's open belongs to the first test that
  triggers it — in a mixed local run that can be a non-shard module (→ unenforced for the run); never in CI, where
  every module is a shard module. Fix an offender in `SHARD_READS` or in the reader, never by reordering.
- The judge keys on the merged shard from the working tree (`from_tree`), like `session_ci.sh`'s pytest step does after
  checkout; a run of a single non-shard file is recorded, never failed.

## /simplify pass (four independent angles) — what was taken, what was not

Taken: `ci_shard_files` goes through the existing `load_tool` instead of a third `importlib` stanza (reuse); the test no
longer re-pins `shard_list.py`'s sentinel order / `--print` agreement (that is `tests/test_shard_list.py`'s job) nor
re-opens the script to find the pattern it just extracted; unused generality dropped (`git(env=, timeout=)`,
`DocsReadAudit(subdir=)`, `ci_shard_files(root=)`); `RVT_DOCS_AUDIT` parsed once (`DOCS_AUDIT_MODE`) instead of three
times three ways; `verdict` declared in `__init__`; one `SESSION_ID` constant; the `isfile` stat per item replaced by
node kind (items and `pytest.Module` collectors carry a module, other collectors do not), which also retired the
`tests/test_*` basename heuristic in the judge for one classifier shared by both channels; the docs-hit relpath is a
prefix slice; **the per-test failure channel** (altitude: an exit-status flip alone never enters the tally
`session_ci.sh` reports); `git_init` exposed as the primitive under `git_repo`. Not taken, with reason: "drop the git
helpers until a consumer migrates" — the issue's DONE asks for them here and the consumers are out of territory this
wave (follow-up below); a `needs_git` marker — no user yet (`test_ci_fresh.py` gates on bash **and** git); moving the
instrument to a `tests/_docs_audit.py` — same depth, and any helper module is scanned by #528 too, so it only pays off
together with the excuse-by-identity follow-up; hoisting `rx.match` out of the per-reader loop — µs once per session,
and it would split the one shared classifier.

## Follow-ups (not done here — territory; filed as #542, one small PR against `tests/test_ci_fresh.py` + `tests/test_shard_list.py`)

- **Adopt the shared git helpers** (eng #522 holds `tests/test_ci_fresh.py` this wave): drop its `GIT_ENV`, `_git`,
  `_commit` for `from conftest import GIT_ENV, git, git_commit, git_init` — `_git(cwd, *a)` → `git(cwd, *a)`,
  `_commit(...)` → `git_commit(...)` (identical semantics: append-write, `add -A`, returns HEAD),
  `_git(up, "init", "-q", "-b", "main")` → `git_init(up)`, `dict(GIT_ENV, PATH=path)` unchanged. Same for
  `tests/test_shard_list.py`'s `_git` (its `-c user.name/-c core.hooksPath` flags are what `GIT_ENV` provides; its bare
  `git init -q` becomes `git_init`, which also ends the `master` + hint noise under a nulled global config) — in
  territory here as "fixture use only", left out to keep this diff to the two new mechanisms.
- **Excuse `tests/conftest.py` by identity in `NAMES_NOT_READS`** ("the runtime instrument: names the audited directory,
  opens nothing by literal" — it stays held to what it hands to `open()`), then spell the docs directory plainly and
  delete the `AUDITED_DIR` indirection; and give both instruments one loader each for the two shared facts
  (`test_ci_fresh._shard_reads` → `conftest.shard_reads_pattern`, its inline `importlib` load of `shard_list.py` →
  `conftest.ci_shard_files`; the ERE-subset guard stays in `test_ci_fresh.py`).
- Optional, `tools/dev/session_ci.sh` (also #522's): its `TAIL` capture could key on the fixed `docs-read audit FAILED`
  banner so the PR comment carries the reason for a session-level (item-less) offender too; item-level ones are already
  in the tally line it greps.

BRANCH STATE (cam/523-docs-read-audit): `tests/conftest.py` (+ `AUDITED_DIR` / `CI_FRESH` / `SESSION_ID` /
`DOCS_AUDIT_MODE`, the `DocsReadAudit` recorder installed before the engine imports, `shard_reads_pattern` /
`ci_shard_files`, the collectstart / runtest_protocol / runtest_teardown / sessionfinish / terminal_summary /
report_header wiring, `GIT_ENV` / `HAVE_GIT` / `git` / `git_init` / `git_commit` / `git_repo`; every pre-existing gate,
helper, hook and fixture byte-intact, only shifted), `tests/test_docs_read_audit.py` (new, 7 tests),
`tests/ci_shard.d/523-docs-read-audit.txt` (new drop-in), this record (new). Nothing under `src/`, `tools/`, `plugin/`,
`skills/`; `tests/test_ci_fresh.py` and `tests/test_shard_list.py` untouched (adoption of the shared helpers = the
follow-up above). Nothing staged for the viewer; no certification claim.

---

## 2026-08-10 — eng #542: the consumers adopt conftest's helpers, and the five keepers from #543's review

**Stream:** shard-docs-audit, continued by eng #542 (issue #542; Refs #523, #528, #487 (c)). Written in this
engineer's voice under its own header; nothing above this rule was edited.

### What landed

1. **`tests/test_ci_fresh.py` adopts the shared helpers** — `from conftest import GIT_ENV, HAVE_GIT, ci_shard_files,
   git, git_commit, git_init, shard_reads_pattern`; its private `GIT_ENV`, `_git`, `_commit`, `_shard_reads` and the
   inline `importlib` load of `tools/dev/shard_list.py` are gone (`SHARD_LIST` with them). Swaps, all mechanical:
   `_git(cwd, …)` → `git(cwd, …)`; `os.makedirs(up)` + `git init -q -b main` → `git_init(up)`; `_commit` →
   `git_commit`; the meta-test's shard list → `ci_shard_files()`; the pattern → `shard_reads_pattern()` behind a local
   `_portable_ere()` that keeps the ERE-subset guard (`[\w/^$|()\[\].-]+`) in this file, as the issue asks; the module
   skip now reads `HAVE_GIT`. **No assertion changed.** One real difference surfaced and was resolved in conftest, not
   papered over here: since #522 this file's `_commit` staged *only the named paths* (`add -A -- <files> <deletes>`) —
   the rig's clone carries untracked copies of `ci_fresh.sh` + `check_portable_paths.py` under `tools/dev/`, and an
   `add -A` of everything would commit them into the PR head, after which `switch --detach origin/main` deletes them
   from the work tree and every `fresh()` call dies. So **`conftest.git_commit` now stages exactly the paths it was
   handed** (docstring says so); for its other user (`test_docs_read_audit.py`'s `git_repo` row, incl. a delete) that is
   the same commit as before.
2. **`tests/test_shard_list.py`** — its `_git` (`git -C repo -c user.name=t -c user.email=t@t -c core.hooksPath=/dev/null`)
   → conftest's `git` (identity and a nulled global/system config come from `GIT_ENV`); the bare `git init -q` in
   `_seed` → `git_init(repo)` (branch `main`, no `init.defaultBranch` hint noise); the module-level `importlib` stanza
   → `load_tool("dev/shard_list")`, the loader `conftest.ci_shard_files()` merges through. Assertions untouched.
   (The issue's Territory lists this file; the wave brief's "NOT shard_list.py" is read as `tools/dev/shard_list.py`,
   which is untouched — flagged in the PR for the reviewer to overrule.)
3. **`tests/conftest.py` — the DocsReadAudit keepers** (every pre-existing gate, fixture and hook byte-intact):
   - **Class collectors carry their module.** `collector_module(collector)` = the path of the collector's nearest
     file-backed ancestor, itself included (`collector.getparent(pytest.File)`): a `pytest.Module`'s own file, a
     **`pytest.Class`**'s file, any other `pytest.File` collector alike; `None` for Session/Dir/Package, which sit
     above every file. `pytest_collectstart` attributes through it. (First cut: an `isinstance(…, (Module, Class))`
     allow-list — the /simplify altitude pass generalised it so the next non-Python collector cannot fall back to
     "session level = enforced", i.e. this very bug, again.) Before, a
     Class collector passed `None` ⇒ session level ⇒ *enforced*: a docs read made while a class's methods are
     collected (`pytest_generate_tests`, a param-id callable) in a **non-shard** file failed a local run of that file
     with the "opened by the CI shard" gloss. Latent (no `pytest_generate_tests` under `tests/` today), real (bite below).
   - **"Could not judge" has its own words.** The verdict is now `{"offenders", "covered", "unenforced", "unjudged",
     "error"}`: when `SHARD_READS` or the shard list cannot be loaded, `error` = `"Type: message"`, every recorded read
     lands in `unjudged` (kept, listed as `??  <path>  (recorded, could not be judged)` with its readers), and the
     section opens with `FAIL the audit could not judge any read (<error>) -- fail closed: …restore them` instead of a
     pseudo-path glossed "opened by the CI shard, NOT covered" and counted as "1 repo docs/ file(s) opened". One
     predicate, `audit_failed(verdict)` (= offenders or error), drives `pytest_sessionfinish`'s exit-1 flip and the
     red banner, so the fail-closed outcome is unchanged: still exit 1 with zero reads recorded.
   - **The header counts files, not rows.** `docs_audit_header(verdict)` counts *distinct* paths across the read
     buckets; a path read by a shard module (offender) and a non-shard module (unenforced) is one file (main summed
     bucket sizes: "2 repo docs/ file(s)" for one file).
   - **Idempotent installation.** `AUDIT_SENTINEL = "_rvt_docs_read_audit"` on `sys`: the first execution creates the
     recorder, `sys.addaudithook`s it and parks it there; a second execution of the file in the same interpreter
     (another import mode, a reload) adopts that recorder instead of stacking a second, unremovable hook.
   - `AUDITED_DIR` stays — the recorder and `tests/test_docs_read_audit.py` (whose house rule keeps real docs names out
     of its literals) build every path from it — but its comment no longer claims it exists for the static scanner's
     sake. Consequently **conftest was *not* added to `NAMES_NOT_READS`**: it names no docs path, so the excuse would be
     unearned, and that list's own comment asks to stay tiny. (The issue's third DONE bullet offered the excuse as the
     way to spell `docs` plainly; with a named constant being ordinary style rather than a dodge, "if and only if it
     must name docs paths" resolves to: it need not.)
4. **`tests/test_docs_read_audit.py`** — three new rows and two extended ones: `TestCollectorAttribution` (a method on
   purpose: its parent *is* a `pytest.Class`, its grandparent the `pytest.Module` — real nodes handed to
   `collector_module`; the class and module map to this file, `tests/` and the session to `None`; a synthetic read under
   the class context is unenforced under a shard lacking the module, the same read under a directory collector is an
   offence); executing `conftest.py` a second time via `importlib` yields new class objects but
   `twice.DOCS_AUDIT is DOCS_AUDIT is sys._rvt_docs_read_audit`; and a **hermetic end-to-end pair**: a tmp copy of the
   rig (this `conftest.py`, `tools/dev/ci_fresh.sh`, `tools/dev/shard_list.py`, a one-line `tests/ci_shard.txt`, a
   `docs/zz-bite.md`, the engine from the real `src/` via `PYTHONPATH`) runs a generated test file whose
   `pytest_generate_tests` opens the docs file while `TestCollected` is collected — not in the copy's shard → `1 passed`,
   exit 0, listed `--  docs/zz-bite.md  (not a CI-shard file…)  <- tests/test_zz_class_collect.py::TestCollected`;
   listed in the shard → exit 1, `FAIL … <- …::TestCollected`. The judge row now also pins `unjudged == {}` /
   `error is None` on a normal verdict, the distinct-file header (4 files; a two-bucket path counted once), and the
   fail-closed verdict's exact shape, header ("0 repo docs/ file(s) opened") and wording with and without recorded reads.

### Evidence

**Stream-local counts, before → after** (`RVT_SKIP_LARGE=1 … -q -rs -p no:cacheprovider`, this VM):
`tests/test_ci_fresh.py` 21 passed / 2 skipped (gawk, busybox absent) → **21 / 2**; `tests/test_shard_list.py` 23 → **23**;
`tests/test_portable_paths.py` 3 → **3**; `tests/test_docs_read_audit.py` 6 passed / 1 skipped → **9 / 1** (the three new
rows; the skip is the inert self-test reader). The four together: 53 passed, 3 skipped → **56 passed, 3 skipped**.

**The #543 bite, reproduced on this branch and reverted** (same injection as above: a `src/` function opening
`docs/STEERING.md` through two variables, appended to `tests/test_shard_list.py`):
```
$ .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_shard_list.py tests/test_ci_fresh.py::test_SHARD_READS_covers_every_docs_path_the_ci_shard_reads
........................E.                                               [100%]
___________ ERROR at teardown of test_zz_injected_indirect_docs_read ___________
docs-read audit (#523): this test opened docs/STEERING.md -- repo docs/ file(s) NOT covered by SHARD_READS in tools/dev/ci_fresh.sh; …
============================ docs-read audit FAILED ============================
1 repo docs/ file(s) opened by this test process; judged against SHARD_READS of tools/dev/ci_fresh.sh (#523)
  FAIL docs/STEERING.md   (opened by the CI shard, NOT covered by SHARD_READS)
         <- tests/test_shard_list.py::test_zz_injected_indirect_docs_read
…
25 passed, 1 error in 0.60s        (exit 1; `git diff tests/test_shard_list.py | grep zz_injected` empty afterwards)
```

**The new bite — a non-shard file whose CLASS collection opens `docs/STEERING.md`, run alone**
(`tests/test_zz_bite_class_collect.py`: `pytest_generate_tests` opens the file to parametrize `TestCollectedByAClass.test_row`; never committed):
```
origin/main 9d4f456 conftest:   1 passed …  docs-read audit FAILED
                                  FAIL docs/STEERING.md   (opened by the CI shard, NOT covered by SHARD_READS)
                                         <- tests/test_zz_bite_class_collect.py::TestCollectedByAClass        exit 1
this branch (RVT_DOCS_AUDIT=report): 1 passed …  docs-read audit
                                  --   docs/STEERING.md   (not a CI-shard file: recorded, not enforced)
                                         <- tests/test_zz_bite_class_collect.py::TestCollectedByAClass        exit 0
```
(the automated form of this pair is the hermetic row in `tests/test_docs_read_audit.py`.)

**Could-not-judge wording, live** (a recorder whose `shard_reads_pattern` is pointed at `/dev/null`):
`audit_failed → True`; header `0 repo docs/ file(s) opened by this test process; …`; first line
`FAIL the audit could not judge any read (ValueError: no SHARD_READS='...' line in /dev/null) -- fail closed: without SHARD_READS from tools/dev/ci_fresh.sh and the merged shard from tools/dev/shard_list.py no docs/ read can be called covered; restore them`.

**Double execution → one recorder:** `tests/test_docs_read_audit.py::test_executing_conftest_a_second_time_adopts_the_installed_recorder_instead_of_stacking_a_hook` (green above).

**Whole merged shard, audit on, `RVT_DOCS_AUDIT=report`, same 4-vCPU VM, sequential runs:**
```
BEFORE  origin/main 9d4f456 (worktree)   1836 passed, 134 skipped, 3 xfailed in 415.84s   wall 417.1 s
AFTER   this branch                      1839 passed, 134 skipped, 3 xfailed in 412.43s   wall 414.0 s   (+3 = this file's new rows)
AFTER   final head (post-/simplify)      1839 passed, 134 skipped, 3 xfailed in 397.14s   wall 398.4 s   (run-to-run spread on this VM ~15-20 s)
```
Census unchanged: the same three `SHARD_READS` paths (`docs/coverage/viewer-certified.json`,
`docs/process/AUTONOMY.md`, `docs/product/PERMUTATION-MATRIX.md`), all `ok`, no `--`/`FAIL` rows; header
`3 repo docs/ file(s) opened…` on all three (`diff` of the three sections: empty).

**Gates:** `python3 tools/dev/check_portable_paths.py` ok; nothing under `src/ tools/ skills/ plugin/` touched, so
`sync_plugin.py --check` / `validate_plugin.py` are moot (run anyway: `plugin in sync with source (deny-audit clean, identity scan == allowlist, assets verified)` / `RESULT: PASS`).

### Limits, restated and extended (keeper 5)

The recorder sees the interpreter's own `open` audit event and nothing else, so some reader classes are outside it
by construction — stated here, **measured** (a throwaway hook in `.venv/bin/python`, this VM), so nobody hunts a
"missed read" in the hook nor distrusts a reader that is in fact seen:
- **subprocesses** (another interpreter: `tools/route.py matrix` run as a child, the child pytest runs above) — as #523 said;
- **C-extension readers that open the file below the Python layer: NOT seen** — `ifcopenshell.open(path)` with the
  real wheel (its C++ STEP reader; opening `inputs/ifc/chicago-plenum-downlight.ifc` raised no `open` event at all) and
  `sqlite3.connect(path)` (raises its own `sqlite3.connect` event, not `open`). **Seen after all**, contrary to the
  review's guess: `numpy.fromfile(path)`, `numpy.load(path)`, `numpy.loadtxt(path)` — numpy opens a path argument
  through Python's `open`, so each raised `('open', 'docs/STEERING.md')`; and `mmap` needs an fd, whose `os.open` is
  seen (the `mmap.__new__` event then names only the fd). None of the unseen kind reads repo `docs/` today
  (ifcopenshell reads `.ifc` inputs; nothing uses sqlite); a future docs reader through such a library must open the
  path in Python and hand over the file object/bytes — or be added to `SHARD_READS` by hand;
- and, in the other direction, **write-mode opens under `docs/` are counted as reads** (`open` raises one event for
  every mode; the hook does not parse `args[1]`). Conservative on purpose: a shard test that *writes* a tracked docs
  file is a bigger smell than one that reads it, and the way out is the same line in the report.

### /simplify pass (four angles) — taken / not taken

Taken: `judge()` picks its classifier once (`kind = …` in the `try`/`except`) instead of re-testing `error` per read
with `rx`/`shard` conditionally unbound; the verdict is built *from* `READ_BUCKETS` (one key list, not two);
`rules()`' docstring follows the new contract; the install block reads the opt-out once; `collector_module` keys on
`getparent(pytest.File)` (above); the two child-pytest launchers in `tests/test_docs_read_audit.py` are one
`_child_pytest(node, cwd=ROOT, **env)` and the trivial `_child_run` wrapper is inlined; `import conftest` there gave way
to `AUDIT_SENTINEL` + a `CONFTEST` path; `tests/test_shard_list.py`'s last two raw `git -C ROOT` calls go through
`conftest.git` (a `try/except` replaces the `.git`-dir + `rev-parse` probe; same assertion). Efficiency: clean — nothing
added to the per-event `__call__` or per-item paths; the hermetic rig costs two child interpreters (~1 s here), which
cannot be one process precisely because of the sentinel (a second in-process session would adopt the first recorder).
Not taken, with reason: moving the ERE-subset guard (`_portable_ere`) *into* `conftest.shard_reads_pattern()` so a
non-portable pattern fails closed in-band on every platform (altitude) — the issue's DONE says the guard stays in
`tests/test_ci_fresh.py`, so it does; noted for the tech lead as a one-line option. A two-field verdict
(`error` + `buckets`) / caching the load failure inside `rules()` — deferred as the reviewers themselves suggest (low
cost today; `audit_failed` is already the one predicate). `tests/test_portable_paths.py`'s private `GIT_ENV` /
`git init` loop / `importlib` stanza (reuse, outside this territory) → filed as #557.

### Follow-ups

- #557 — `tests/test_portable_paths.py` adopts the shared helpers (the last private `GIT_ENV` under `tests/`).
- Optional, for the tech lead: host the ERE-subset guard in `conftest.shard_reads_pattern()` (raise `ValueError` → the
  fail-closed `error` path reports it everywhere, incl. Windows/no-bash where `test_ci_fresh.py` skips).
- The optional `session_ci.sh` `TAIL` keyed on the `docs-read audit FAILED` banner (listed by #523) remains optional
  and outside this territory (`tools/dev/`).

BRANCH STATE (cam/542-conftest-helpers): `tests/conftest.py` (DocsReadAudit: `unjudged`/`error` verdict keys,
`audit_failed`, `READ_BUCKETS`, `docs_audit_header`, `collector_module`, `AUDIT_SENTINEL` install guard, could-not-judge
report wording; `git_commit` stages named paths only; docstrings), `tests/test_ci_fresh.py` (helper adoption only),
`tests/test_shard_list.py` (helper adoption only, incl. its two read-only `git -C ROOT` calls), `tests/test_docs_read_audit.py` (+3 rows, 2 extended, one child-pytest launcher), this section.
No `src/`, `tools/`, `plugin/`, `skills/`; no shard drop-in needed (all four files already in the merged shard);
nothing staged for the viewer; no certification claim.

---

## 2026-08-10 — eng #557: `tests/test_portable_paths.py` adopts conftest's helpers (the last private `GIT_ENV` under `tests/`)

**Stream:** shard-docs-audit, continued by eng #557 (issue #557; Refs #542, #523, #487 (c)). Own header, own voice;
nothing above this rule was edited.

### What landed

`tests/test_portable_paths.py` — helper adoption only: `from conftest import HAVE_GIT, ROOT, git, git_commit, load_tool`.
Its private `GIT_ENV` (byte-identical to conftest's), its own `ROOT`, the module-level `importlib` stanza for
`tools/dev/check_portable_paths.py` (→ `load_tool("dev/check_portable_paths")`, the same shape as
`tests/test_shard_list.py`'s `load_tool("dev/shard_list")`), both `shutil.which("git")` gates (→ `HAVE_GIT`, reason text
`"needs git"` kept so `-rs` reads the same), the raw `git ls-files -z` subprocess (→ `git(ROOT, "ls-files", "-z")`,
NUL-split and filtered exactly as before — `strip()` never eats a NUL) and the mkdir/write + `git init / add -A / commit`
loop of the exit-1 row (→ the `git_repo` fixture + one `git_commit(git_repo, {rel: "x\n" …}, "bad")`; the CLI then runs
in `git_repo` instead of `tmp_path`) are gone; `import importlib.util / os / shutil / subprocess` with them. Every
assertion, test id, skip condition and skip reason is unchanged; the only behavioural nuance is that the throwaway
repo is now born on branch `main` under the hermetic identity (what `git_repo` is for), which the checker never looks at.

### Evidence

- `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_portable_paths.py -q -rs`: **3 passed → 3 passed**;
  `--collect-only -q` ids before/after: `diff` empty (`test_check_reports_every_law_with_the_names_involved_in_cli_order`,
  `test_the_cli_is_check_over_git_ls_files_and_this_checkout_passes`, `test_the_cli_names_every_problem_and_exits_1`).
- `git diff --stat origin/main -- tests/test_portable_paths.py`: 9 insertions, 22 deletions (net −13);
  `git diff origin/main -- tests/test_portable_paths.py | grep "^-" | grep -c assert` → **0** (no assertion line touched).
- The issue's grep: `grep -rn "GIT_ENV = " tests/test_*.py` → nothing (conftest holds the only one);
  `spec_from_file_location` no longer appears in this file. It still appears in ~30 other test files — engine/tool
  loaders outside this family, plus two *process* tests (`tests/test_coord.py` → `tools/dev/coord.py`,
  `tests/test_techlead.py` → `tools/dev/techlead.py`) that are the same `load_tool("dev/…")` swap; outside this
  territory, filed as a follow-up (below) rather than widened here.
- Gates: the four stream-local files (`test_portable_paths`, `test_shard_list`, `test_ci_fresh`, `test_docs_read_audit`)
  `-q -rs -p no:cacheprovider`: **56 passed, 3 skipped** (gawk / busybox absent on this image; the inert self-test
  reader) — identical to eng #542's after-counts; `python3 tools/dev/check_portable_paths.py` → `ok: 2981 tracked paths
  are portable`; whole merged shard: see BRANCH STATE. Nothing under `src/ tools/ plugin/ skills/` touched
  (`sync_plugin.py --check` clean at setup, moot for this diff).
- /simplify (reuse · simplification · efficiency · altitude, four independent passes): clean, nothing to apply. Noted,
  not actionable here: `git_commit` ends with a `rev-parse HEAD` this row discards (one extra ~5 ms git call versus the
  hand-rolled loop — the price of the shared helper); the `skipif(not HAVE_GIT, reason="needs git")` kept on the row that
  now takes the self-skipping `git_repo` fixture is redundant as a *gate* but is what keeps the `-rs` reason identical —
  a shared `needs_git` marker in conftest (as `needs_schema` / `needs_ifc_authoring` already exist; #523 deferred it for
  want of a user — there are three now) would let adopters drop it. Conftest is another engineer's this wave: an option
  for the tech lead, not done.

### Follow-ups

- Filed as #593: `tests/test_coord.py` + `tests/test_techlead.py` load their tool through `conftest.load_tool("dev/coord")` /
  `load_tool("dev/techlead")` instead of private `importlib` stanzas (their `COORD` / `PATH` constants stay — both files
  also run the tool as a child process). XS, tests-only, same evidence shape as this issue.
- Optional (conftest, tech lead's call): a `needs_git = pytest.mark.skipif(not HAVE_GIT, reason="needs git")` marker
  and the `git_repo` fixture's skip reason aligned to it.

BRANCH STATE (cam/557-portable-paths-conftest-helpers): `tests/test_portable_paths.py` (helper adoption only), this
section. No `tests/conftest.py` change, nothing under `src/`, `tools/`, `plugin/`, `skills/`; no shard drop-in needed
(the file is already in the merged shard); nothing staged for the viewer; no certification claim. Whole merged shard on
the final head: `RVT_SKIP_LARGE=1 … -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)` → **2012 passed, 134 skipped, 3 xfailed** in 491 s (docs-read audit on, no section printed = no offender), exit 0.

---

## 2026-08-10 — eng #579: the own-release test scaffolding lives once, in `tests/conftest.py`

**Stream:** tests-release-scaffolding, eng #579 (issue #579; Refs #566, #533, #518, #451). Written in this
engineer's voice under its own header; nothing above this rule was edited (eng #557 adds its own header to this
file in the same wave — different lines).

### What landed

1. **`tests/conftest.py` — one new section, "the shared own-release scaffolding (#579)"**, placed after the `job`
   fixture; every pre-existing gate, fixture and hook is byte-intact — the ONE place pre-existing bytes changed is the
   module docstring (2 lines: its closing clause now also names this section's exports) — plus two new import lines
   (`import dataclasses`; `from rvt import versions as _V`, a name for a module `frontdoor.base` had already loaded —
   `python -c "import conftest"` lists the same twelve `rvt.*` modules before and after). Exports:
   - `FOREIGN_FIRST` = `CERTIFIED_YEARS` with the native release **last** (a context leaked by a 2025/2024 run breaks
     the native run after it, in-process, instead of hiding), `FOREIGN` = the foreign pins alone, same order — the
     exact expressions five files carried (`sorted(…, key=lambda y: y == V.LATEST_RELEASE)`; stable sort ⇒ `FOREIGN`
     is also `[y for y in CERTIFIED_YEARS if y != LATEST]`, the spelling `test_natively_framed` / `test_edit_text_release` used — pinned by the law file);
   - `native_constants()` — the framing table (`V.framing_table(LATEST)` keys read off `rvt.partitions`) +
     `release_ctx.active_release()`; and `ladder_constants()` — what the instrument ladder swaps on top
     (`objects.iter_records`, `adocument._DECODER`, `famdoc_adoc.FAMILY_END_RECORD`), a separate callable so only a
     file that climbs the ladder pays for the famgen import (the issue's ask) and the ONE list to grow when the ladder
     learns another name. Every engine import inside both is lazy: conftest's import-time footprint is unchanged;
   - the leak guard as two fixtures, pytest's own override idiom instead of a parameter smuggled through a module
     global — and **additive**, so no override can drop the base watch: `release_leak_extra` (function-scoped, `None`
     by default; a file overrides it with a zero-arg callable returning more `{name: value}` — `return ladder_constants`)
     and `no_release_leak(release_leak_extra)` (opt-in: `snapshot() = native_constants()` updated with the extra;
     `before = snapshot(); assert before["active_release"] is None; yield; assert snapshot() == before`). Files opt in
     with `pytestmark = pytest.mark.usefixtures("no_release_leak")`, so nothing else in the suite pays for it and no
     file defines a `_no_leak` of its own; set-up/tear-down order relative to the tests' `capsys`/`tmp_path`/`monkeypatch`
     is what the autouse copy had (pytest builds the closure as `autouse, usefixtures, argnames` —
     `_pytest/fixtures.py: deduplicate_names(autousenames, usefixturesnames, argnames)`; the guard is still first);
   - `rewrite_stream(src, dst, name, damage) -> dst` — the superset of the two variants in the tree: `damage(raw)`
     replaces the stream's raw (still paged) bytes, `damage=None` drops the stream (the refusal files' form), every
     other entry byte-identical, `dst` returned as `str` (accepts `Path`); one deliberate tightening: a `name` the
     container lacks is a `KeyError`, where the six-file variant raised from `open_rvt(src).raw(name)` and the
     refusal variant wrote a silent verbatim copy. `read_entries()`' `e.data` **is** `RvtDocument.raw(name)` (both
     `ole.openstream(...).read()`), so dropping the extra `open_rvt` pass changes no byte;
   - `partition_of(path)` (first `Partitions/<N>`), and the damaged-copy recipes by name: `zero_partition_header`
     (`bytes(16) + raw[16:]`, ×5 in the tree), `zero_schema_bytes` (`raw[:2000] + bytes(64) + raw[2064:]`, #518's
     repro, ×6), `truncated_copy(src, dst, size)` (64 KiB / 4 KiB heads), `cfb_header_zeroed_copy(src, dst)` (first
     sector zeroed: same size, not a container).
2. **The six adopters** — helper adoption only; no assertion, test id, parametrize axis or skip condition changed:
   `test_selfcheck_release.py`, `test_inspect_release.py`, `test_edit_text_release.py`, `test_natively_framed.py`,
   `test_estorage_cli_release.py`, `test_edit_own_release.py`. Each lost its `_native_constants` + autouse `_no_leak`
   (→ `pytestmark = usefixtures("no_release_leak")`; `test_inspect_release` / `test_estorage_cli_release` override
   `release_leak_extra` with `return ladder_constants` — exactly the three extra keys their copies watched;
   `test_edit_text_release` overrides it to keep watching `W.BLOCK_TRL_TAG` on top, as its copy did — redundant with
   `TRAILER_TAG` since #467 made it a module `__getattr__`, kept so the assertion is literally the same;
   `test_edit_own_release`'s `pytestmark` became a list: its `skipif` + the `usefixtures`), its `FOREIGN_FIRST`/`FOREIGN`,
   `_rewrite_stream`, `_partition_of`, the two damage lambdas, the inline 64 KiB truncation and the two
   copy-then-zero-512 stanzas; imports that only served the copies (`dataclasses`, `shutil`, `rvt.partitions`,
   `release_ctx` where nothing else used them) went with them (pyflakes clean on all eight files).
   **`test_estorage_cli_release.py` and eng #576:** the tech lead's coordination note (eng #576 flips that file's
   `_has_usage_map_class()` predicate, the two 2024 else-branch strings and one docstring bullet on their head) is
   honoured by construction — this PR touches only its import block, the `FOREIGN_FIRST`/`FOREIGN`/`ALL_FLAGS` lines,
   the `_native_constants`/`_no_leak` block, the `_rewrite_stream`/`_partition_of` block and the two-line body of
   `test_damaged_partition_is_a_stated_verdict`; the docstring, `_has_usage_map_class`, `_assert_full_report` and
   `test_library_reports_an_absent_map_instead_of_raising` are byte-intact, so the two PRs touch disjoint hunks and
   whoever lands second rebases mechanically.
3. **`tests/test_conftest_scaffolding.py`** (new, 13 tests, in the shard via `tests/ci_shard.d/579-scaffolding.txt`) —
   the AST law, **over every `tests/test_*.py`** rather than a list of six (post-/simplify altitude): no module binds
   `_native_constants`/`_no_leak`/`_rewrite_stream`/`_partition_of`, its own `FOREIGN_FIRST`/`FOREIGN`/`NATIVE_LAST`, or
   a top-level shadow of the conftest names — minus a shrinking `EXEMPT` = {`test_rvt_edit_refusal`,
   `test_release_ctx_refusal` (eng #587's, the follow-up below), `test_gates_shared_walk` (a `_rewrite_stream(…, mutate)`
   of another shape)}, itself checked (every exempt file exists and still binds a forbidden name, so the list cannot
   go stale silently). Scope, stated: the law inspects `tree.body` only — module-level `def`/`class`/assignments, which is
   where every copy ever lived; a copy nested inside a class or function would slip past it (acceptable for a ratchet;
   widen to `ast.walk` the day one does). The six adopters keep `no_release_leak` in their `pytestmark` (read from the AST); plus
   behaviour rows: `FOREIGN_FIRST` ordering (native last; `FOREIGN` in the legacy order); `native_constants() ==
   dict(framing_table, active_release=None)` and `ladder_constants()` = exactly the three swaps, disjoint from it; the
   two damage recipes touch exactly their window; `rewrite_stream` on a real pin damages one stream, keeps every other
   stream byte-identical, drops on `None`, `KeyError`s (and writes nothing) on a missing name; `truncated_copy` /
   `cfb_header_zeroed_copy` produce what their names say. Pin-backed rows skip cleanly without a certified pin
   (tracked assets, so they do run in CI).
4. `docs/inbox/tests-release-scaffolding.md` — the record path issue #579's Territory names: a short pointer to this
   section (the wave brief asked for the record here, next to the two earlier conftest hoists), so both hold.

### Evidence
**Per-file collected ids, before → after** (`.venv/bin/python -m pytest <file> -q -rs --collect-only -p no:cacheprovider | tail -1`,
and the id lists themselves `diff`ed — every id identical, no rename, no re-parametrisation):

| file | collected before | collected after | ids `diff` | run before | run after |
|---|---|---|---|---|---|
| `tests/test_selfcheck_release.py` | 9 tests collected | 9 tests collected | empty | 9 passed | 9 passed |
| `tests/test_inspect_release.py` | 13 | 13 | empty | 13 passed | 13 passed |
| `tests/test_edit_text_release.py` | 7 | 7 | empty | 7 passed | 7 passed |
| `tests/test_natively_framed.py` | 17 | 17 | empty | 17 passed | 17 passed |
| `tests/test_estorage_cli_release.py` | 10 | 10 | empty | 10 passed | 10 passed |
| `tests/test_edit_own_release.py` | 11 | 11 | empty | 11 passed | 11 passed |
| the six together (`RVT_SKIP_LARGE=1 RVT_DOCS_AUDIT=report … -q -rs`) | 67 | 67 | — | **67 passed, 0 skipped** in 10.02 s | **67 passed, 0 skipped** in 9.92 s |
| + `tests/test_conftest_scaffolding.py` (new) | — | 13 | — | — | 80 passed in 11.13 s |

Docs-read census of that run: `0 repo docs/ file(s) opened by this test process` before and after.

**The guard still bites** (a throwaway `tests/test_zz_scratch_leak.py`, never committed, `usefixtures("no_release_leak")`
module-wide): a test that rebinds `P.BLOCK_TAG` → `ERROR at teardown`; under a class overriding `release_leak_extra`
with `ladder_constants`, a test that rebinds `objects.iter_records` → `ERROR at teardown` **and** one that rebinds
`P.BLOCK_TAG` → `ERROR at teardown` (the extra cannot drop the base watch); without the extra an `iter_records` rebind
passes, exactly as the four plain copies behaved. **The law bites:** appending `FOREIGN = []` + `def _rewrite_stream(): …`
to `tests/test_selfcheck_release.py` → `test_no_module_carries_a_private_copy` red naming the file and both names
(reverted; `git diff` clean afterwards).

**`git diff origin/main --stat -- tests/`:** conftest + the six adopters `+164 −237` (net **−73** lines; conftest +113
of docstring-heavy helpers, the six files −186); with the new law file (+139) and the one-line drop-in the tests tree
is `+305 −237`. `grep -n "def _native_constants\|def _rewrite_stream" tests/` → `tests/test_release_ctx_refusal.py:72`
and `tests/test_rvt_edit_refusal.py:65` only (eng #587's two, exempt above) — none in the six, none in conftest under
the private names.

**Whole merged shard** (`RVT_SKIP_LARGE=1 RVT_DOCS_AUDIT=report .venv/bin/python -m pytest -q -rs -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`,
same 4-vCPU cloud VM, sequential runs, 101 files on the branch = main's 100 + the law file):
```
origin/main db32071            2012 passed, 134 skipped, 3 xfailed, 3 warnings in 398.35s
this branch, first cut         2024 passed, 134 skipped, 3 xfailed, 3 warnings in 416.47s   (+12 = the law file as first written)
this branch, final head        2025 passed, 134 skipped, 3 xfailed, 3 warnings in 405.96s   (+13 = the law file, post-/simplify; = main + 13, nothing else moved)
```
Skips identical (134, the same `-rs` list: samples/experiments absent, gawk/busybox absent, root chmod, the inert
self-test reader); the 3 warnings are main's (`PytestRemovedIn10Warning: Class-scoped fixture defined as instance
method`). Docs-read census identical on all three runs: `3 repo docs/ file(s) opened…` — `docs/coverage/viewer-certified.json`,
`docs/process/AUTONOMY.md`, `docs/product/PERMUTATION-MATRIX.md`, all `ok`, no `--`/`FAIL` rows.

**Gates:** `python3 tools/dev/check_portable_paths.py` → `ok: 2981 tracked paths are portable` (2984 with the three new
files); nothing under `src/ tools/ skills/ plugin/` touched (`sync_plugin.py --check` moot; `scripts/cloud-setup.sh`
reported `plugin in sync with source` at session start); pyflakes clean on the eight touched test files; `/verify`
skipped — tests-only diff, no runtime surface (commit trailer says so).

### /simplify pass (four angles) — taken / not taken

Taken: **altitude** — the snapshot override became *additive* (`release_leak_extra` merged onto `native_constants()`
inside `no_release_leak`) instead of a replace-the-whole-callable `release_leak_snapshot`, so an override can no longer
forget the framing table, and `native_constants(ladder=True)` (a flag that would have wanted a third sibling for the
refusal files' `RC._REFUSED`/`MU`/`GSK`/`SA` watches) became `native_constants()` + `ladder_constants()` — the refusal
files slot in later as one `release_leak_extra` override each without touching conftest; the AST law runs over every
`tests/test_*.py` with a self-checking `EXEMPT` set instead of enumerating six adopters and special-casing
`test_edit_own_release`, and reads `pytestmark` from the AST instead of substring-matching `ast.unparse`.
**Simplification** — one `os.fspath` per helper instead of eleven; the law's derivable `EXPORTS` list and its restated
`FOREIGN` assertion dropped; one `FORBIDDEN` set over all top-level bound names; the two ladder adopters lost their
`import functools` + `partial` (a one-line `return ladder_constants`); the `test_edit_own_release` comment is one line.
**Efficiency** — clean against "no more work than before" (one *fewer* container open per damaged copy: the old helper
did `open_rvt(src).raw(name)` and then `read_entries(src)`; conftest import time unchanged — `rvt.versions` was already
in `sys.modules` via `_B.release_status`, everything else lazy). **Reuse** — clean: no engine or test helper already did
any of this (nearest are private dev-probe helpers in `tools/regcorner_probe.py` / `tools/terminal_diff.py`).
Not taken, with reason: deriving the watch list from the engine's own rebinding tables (`records32._patch_table()`,
`global_framing`'s inline `saved` list) so it cannot drift — needs an exported table in `src/rvt/`, outside this
tests-only territory (follow-up below); an engine-level `rvt.roundtrip.rewrite(src, dst, replace=…, drop=…)` that
conftest and the ~5 tool/test re-implementations would share — `src/` again (follow-up); a module-scoped `before`
snapshot in the law file to save one 580 KB read — pennies, left simple.

### Follow-ups

- **The three files left alone this wave (eng #587's territory): adopt conftest's scaffolding** — `tests/test_rvt_edit_refusal.py`
  (`NATIVE_LAST`/`FOREIGN` → `FOREIGN_FIRST`/`FOREIGN`; its tuple `_no_leak` → `usefixtures("no_release_leak")`;
  `_rewrite_stream` → `rewrite_stream` (same signature incl. `damage=None`, already returns `dst`); the `raw[:2000]…`
  lambda → `zero_schema_bytes`; its `trunc4k`/64 KiB writes → `truncated_copy`), `tests/test_release_ctx_refusal.py`
  (same four, plus `_constants()`' extras — `RC._REFUSED`, the `MU` class ids, `GSK` minimal_* + `_SCHEMA_CACHE` keys,
  `SA` template fns + `_SCHEMA_STATE` — as one `release_leak_extra` override; note its key is `active`, conftest's is
  `active_release`), `tests/test_edit_status.py` (its 64 KB truncation and Formats/Latest-zeroed builders →
  `truncated_copy` / `rewrite_stream(…, zero_schema_bytes)`); then delete their two lines from `EXEMPT` — the law's
  self-check turns red if you forget. To be filed as a task issue `Refs #579 #587` once #587's PR lands (filing it now
  would only collide with their open territory).
- Candidates outside the issue's list, for whoever next touches them: `tests/test_gates_shared_walk.py`
  (`_rewrite_stream(src, dst, name, mutate: bytearray -> None)` + `_partition` — a `lambda raw: …` away from
  `rewrite_stream`/`partition_of`; exempt today), `tests/test_partition_header_verdict.py` (`_partition`, `_rewrite`),
  `tests/test_readers_own_release.py` (a tuple-shaped `_no_leak` watching FF tokens → `release_leak_extra`),
  `tests/test_validate_release.py` / `tests/test_verify_manipulated_release.py` (inline `framing_table(LATEST)` snapshots).
- Engine altitude (needs `src/`, so not here): export the set of names a release context rebinds (one table the guard
  could read instead of a hand list), and a `rvt.roundtrip` "re-emit with these streams replaced/dropped" primitive.

BRANCH STATE (cam/579-release-scaffolding): `tests/conftest.py` (+ the "shared own-release scaffolding (#579)" section:
`FOREIGN_FIRST`, `FOREIGN`, `native_constants`, `ladder_constants`, fixtures `release_leak_extra` / `no_release_leak`,
`rewrite_stream`, `partition_of`, `zero_partition_header`, `zero_schema_bytes`, `truncated_copy`, `cfb_header_zeroed_copy`;
docstring clause, `import dataclasses`, `from rvt import versions as _V`; every earlier gate/fixture/hook byte-intact),
the six adopters (helper adoption only): `tests/test_selfcheck_release.py`, `tests/test_inspect_release.py`,
`tests/test_edit_text_release.py`, `tests/test_natively_framed.py`, `tests/test_estorage_cli_release.py`,
`tests/test_edit_own_release.py`; new `tests/test_conftest_scaffolding.py` + `tests/ci_shard.d/579-scaffolding.txt`;
`docs/inbox/tests-release-scaffolding.md` (pointer) and this section. No `src/`, `tools/`, `plugin/`, `skills/`;
`tests/ci_shard.txt` untouched; nothing staged for the viewer; no certification claim.
Rebased once onto `280ec51` (after #594 = eng #557's section above, kept as landed, and #599 = eng #576's four hunks in
`tests/test_estorage_cli_release.py`, which git merged conflict-free with this branch's disjoint ones — `git diff
origin/main -- tests/test_estorage_cli_release.py` touches no `_has_catalog_layout` / catalog-string / docstring line);
on the rebased head the six adopters + the law file + `tests/test_estorage_cli_release.py` + `tests/test_estorage_catalog_2024.py`
→ **89 passed** (67 + 13 + #599's 9), docs census 0, portable paths ok (2986).

---

## 2026-08-11 — eng #593: `tests/test_coord.py` and `tests/test_techlead.py` load their tool through `conftest.load_tool`

The last two *process* tests still carried the private module-level loader that #523 gave one home
(`tests/conftest.py::load_tool`) and that #542 / #557 already retired from `test_shard_list.py` / `test_portable_paths.py`:
`tests/test_coord.py` L10–20 (`spec_from_file_location("coord", COORD)` + `module_from_spec` + `exec_module`) and
`tests/test_techlead.py` L18–30 (the same for `tools/dev/techlead.py`). Both are now `from conftest import ROOT, load_tool`
plus `coord = load_tool("dev/coord")` / `tl = load_tool("dev/techlead")` at module level — the exact shape the two earlier
adopters use (neither file monkeypatches the loaded module, so no module-scoped fixture is needed). Their own `ROOT`
computation is dropped for conftest's identical one; `import importlib.util` goes with the stanza. `COORD` / `PATH` / `WF`
stay: both files also run the tool as a child process (`subprocess.run([sys.executable, COORD|PATH, …])`), and
`test_techlead.py` reads `PATH`'s source and globs `WF`. Helper adoption only: every assertion, test id and outcome is
unchanged.

The one nuance the issue asked to check: `load_tool` registers the module as `sys.modules["dev/coord"]` /
`sys.modules["dev/techlead"]` (the private stanzas registered nothing). Neither tool looks itself up by name —
`tools/dev/techlead.py` loads `coord.py` by *path* (its own `spec_from_file_location("coord", HERE/coord.py)`, L54), and
`coord.py`'s only `__name__` use is the `__main__` guard — and no test refers to `sys.modules["coord"|"techlead"]`; the
after-run below is the proof.

### Evidence

- Per file, `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest <file> -q -rs -p no:cacheprovider`, before → after:
  `tests/test_coord.py` **11 passed → 11 passed**; `tests/test_techlead.py` **34 passed → 34 passed** (45 collected, as the
  issue counted; no skips in either, so `-rs` prints no reasons before or after). `--collect-only -q` id lists before/after:
  `diff` empty for both files (11 + 34 ids).
- The issue's gate set, `tests/test_coord.py tests/test_techlead.py tests/test_shard_list.py tests/test_portable_paths.py -q -rs`:
  **71 passed → 71 passed**.
- `grep -n spec_from_file_location tests/test_coord.py tests/test_techlead.py` → nothing.
  `git diff origin/main -- tests/test_coord.py tests/test_techlead.py | grep "^-" | grep -v "^---" | grep -c assert` → **0**.
  `git diff --stat` (tests only): 6 insertions, 10 deletions — net −4 (−2 per file: five stanza/`ROOT` lines out, one
  `from conftest import …` + one `load_tool(…)` line in, `importlib.util` import gone).
- `python3 tools/dev/check_portable_paths.py` → `ok: 2981 tracked paths are portable`. Nothing under `src/ tools/ plugin/
  skills/` touched (`sync_plugin.py --check` clean at cloud-setup; moot for this diff). No other conftest helper is
  duplicated in either file: the three `env = {**os.environ, "GH_TOKEN": "", …}` dicts in `test_techlead.py` scrub tokens
  for the CLI smoke rows — they are not `GIT_ENV` and have no conftest equivalent.
- /simplify: two-line mechanical swap per file; nothing to fold further without leaving the territory.

### Follow-ups

None new. `spec_from_file_location` remains in ~30 engine/tool test files outside the process-test family (each loads a
different `tools/*.py`, several through fixtures that patch the module) — a wider `load_tool` sweep is a separate,
larger call for the tech lead, deliberately not filed as one issue per file.

BRANCH STATE (cam/593-coord-techlead-load-tool): `tests/test_coord.py`, `tests/test_techlead.py` (helper adoption only),
this section. No `tests/conftest.py` change; nothing under `src/`, `tools/`, `plugin/`, `skills/`; no shard drop-in
needed (both files are already in the merged shard, rows 14 and 18 of `shard_list.py --print`); nothing staged for the
viewer; no certification claim. Whole merged shard on the test head (100 files):
`RVT_SKIP_LARGE=1 … -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)` → **2012 passed, 134 skipped,
3 xfailed** in 343 s (docs-read audit on, no section printed = no offender), exit 0 — identical counts to eng #557's run.

---

## 2026-08-11 — eng #602: the two refusal files and `test_edit_status.py` adopt conftest's own-release scaffolding; `EXEMPT` is down to one

**Stream:** eng #602 (issue #602; Refs #579 #587, and #560 / #574 / #559 for the three files' origin). Written in this
engineer's voice under its own header; nothing above this rule was edited.

### What landed — helper adoption only (no assertion, test id, parametrize axis or skip condition changed)

1. **`tests/test_rvt_edit_refusal.py`** — `NATIVE_LAST` / `FOREIGN` → conftest's `FOREIGN_FIRST` / `FOREIGN` (the same
   lists: `NATIVE_LAST` *was* `sorted(CERTIFIED_YEARS, key=lambda y: y == LATEST)`, and the stable sort makes conftest's
   `FOREIGN` equal to the file's `[y for y in CERTIFIED_YEARS if y != LATEST]` — the law file pins that identity); its
   tuple-shaped autouse `_no_leak` → `pytestmark = pytest.mark.usefixtures("no_release_leak")` (no override: the copy
   watched exactly the framing table + `active_release()`, i.e. `native_constants()`); `_rewrite_stream` → `rewrite_stream`
   (same signature incl. the `damage=None` drop; both streams it names — `Global/ElemTable`, `Formats/Latest` — exist on
   every pin, so the hoisted helper's `KeyError`-on-missing-name tightening never fires here); the `raw[:2000] + bytes(64)
   + raw[2064:]` lambda → `zero_schema_bytes`; the `trunc4k` / per-year 64 KiB head writes → `truncated_copy(…, 4096 |
   65536)` (returns `str(dst)`, so the tuple's path element and the `cannot open/plan trunc64k_<year>.rvt: ` prefix are the
   same strings as before). `import dataclasses`, `rvt.partitions as P`, `release_ctx as RC` left with the copies.
2. **`tests/test_release_ctx_refusal.py`** — the same four, plus the issue's one real design point: its `_constants()`
   watched MORE than the framing table (`RC._REFUSED`, the three `MU.CLASS_*` ids, `GSK.minimal_history` /
   `minimal_elemtable` / `sorted(GSK._SCHEMA_CACHE)`, `SA.bundled_base_path` / `family_instance_template` /
   `dict(SA._SCHEMA_STATE)`). `_constants()` is now `dict(native_constants(), refused=…, mu=…, gsk=…, sa=…)` — conftest's
   snapshot plus the same four extras — and reaches the guard through ONE `release_leak_extra` override
   (`return _constants`; additive on top of `native_constants()`, so the overlapping keys are a no-op re-update), exactly
   the seam #579 left for this file, so **no `tests/conftest.py` change was needed**. `_constants` keeps its name because
   `test_setup_failure_after_the_first_swap_restores_everything` snapshots it in its *body* (`before = _constants()` …
   `assert _constants() == before` … `before["mu"][0]`): those three lines are byte-identical; the only spelling that
   moved is the snapshot key `active` → conftest's `active_release`, which no assertion indexes. `import dataclasses`
   stays (the `KNOWN_RELEASES` monkeypatch uses `dataclasses.replace`); `rvt.partitions as P` goes.
3. **`tests/test_edit_status.py`** — `_cut_at_64k(year, dst)` → `truncated_copy(pinned_base(year), dst, 65536)` inside the
   two fixtures (its docstring sentence folded into `trunc64k`'s), the inline Formats/Latest-zeroing `schema_dmg` builder →
   `rewrite_stream(pinned_base(2025), …, "Formats/Latest", zero_schema_bytes)`; `import dataclasses` goes. This file binds
   none of the forbidden names and has no leak guard; none was added (adoption only — a guard would be a new assertion).
4. **`tests/test_conftest_scaffolding.py`** — `EXEMPT` loses `test_rvt_edit_refusal` and `test_release_ctx_refusal`;
   it is now `{"test_gates_shared_walk"}` alone, and the `#:` comment on it no longer says "a copy another stream owns"
   (the survivor is exempt for its `mutate`-shaped helper, #604); and — on the tech lead's ruling in review, since it is
   list data, not law logic — `ADOPTERS` gains `test_rvt_edit_refusal` and `test_release_ctx_refusal`, so
   `test_adopter_keeps_the_leak_guard_on` ratchets the two files this PR turned from an **autouse** guard into a one-line
   `pytestmark` opt-in (the module docstring's "six adopters" / "copies another stream still owns" wording follows).
   That is the ONE intended collection change of the PR: the law file goes 13 → 15 ids (+ the two `[stem]` rows); no
   law logic touched.

### Evidence

**Per-file collected ids and outcomes, before (origin/main `59a89d8`) → after** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest <file> -q -rs -p no:cacheprovider`;
`--collect-only -q` id lists `diff`ed; and the `-v` id+outcome lines of the four files together `diff`ed — empty):

| file | collected before | collected after | ids `diff` | run before | run after |
|---|---|---|---|---|---|
| `tests/test_rvt_edit_refusal.py` | 11 | 11 | empty | 11 passed | 11 passed |
| `tests/test_release_ctx_refusal.py` | 15 | 15 | empty | 15 passed | 15 passed |
| `tests/test_edit_status.py` | 9 | 9 | empty | 9 passed | 9 passed |
| `tests/test_conftest_scaffolding.py` | 13 | 15 | +2: `test_adopter_keeps_the_leak_guard_on[test_rvt_edit_refusal]` / `[test_release_ctx_refusal]`, nothing else | 13 passed | 15 passed |
| the four together (`-q -rs`) | 48 | 50 | the `-v` id+outcome `diff` = exactly those two added `PASSED` rows | **48 passed, 0 skipped** in 5.06 s | **50 passed, 0 skipped** in 5.48 s |

`RVT_DOCS_AUDIT=report` census of that run, before and after: `0 repo docs/ file(s) opened by this test process` — unchanged.

**Removed `assert` lines** (`git diff -U0 -- tests/ | grep '^-\s*assert'`) — exactly the two private leak-guard pairs that
moved into conftest's `no_release_leak`, nothing else; no `assert` line added:
```
-    assert before["active"] is None                      (test_release_ctx_refusal._no_leak)
-    assert _constants() == before                         (test_release_ctx_refusal._no_leak)
-    assert before[1] is None                              (test_rvt_edit_refusal._no_leak)
-    assert ({k: getattr(P, k) for k in V.framing_table(V.LATEST_RELEASE)}, RC.active_release()) == before   (idem)
```
**The guard still bites in both files** (throwaway tests appended, run, reverted; `git diff` clean afterwards): in
`test_release_ctx_refusal.py` a test that does `SA._SCHEMA_STATE["leak"] = 1` → `ERROR at teardown` (the extra is
watched), and one that rebinds a framing-table name on `rvt.partitions` → `ERROR at teardown` (the base watch is not
dropped by the override); in `test_rvt_edit_refusal.py` the framing rebind → `ERROR at teardown`.
**The law bites both ways** (mutations, reverted): appending `def _rewrite_stream(src, dst, name, damage): …` to
`test_rvt_edit_refusal.py` → `test_no_module_carries_a_private_copy` FAILED naming the file; re-adding
`"test_release_ctx_refusal"` to `EXEMPT` → `test_the_exempt_list_only_names_files_that_exist_and_still_need_it` FAILED
with `test_release_ctx_refusal carries no copy any more: drop it from EXEMPT`; deleting the `pytestmark = …usefixtures("no_release_leak")`
line from `test_rvt_edit_refusal.py` → `test_adopter_keeps_the_leak_guard_on[test_rvt_edit_refusal]` FAILED (the new ratchet bites).

`git grep -n "def _rewrite_stream\|def _no_leak\|^NATIVE_LAST\|^FOREIGN" -- tests/` → `tests/conftest.py:250-251`
(`FOREIGN_FIRST` / `FOREIGN`) and `tests/test_gates_shared_walk.py:106` (the exempt `_rewrite_stream(…, mutate)`) only.
`git diff --numstat` on the three adopted files: **+34 −110** (net −76: `test_rvt_edit_refusal` 11/44,
`test_release_ctx_refusal` 16/42, `test_edit_status` 7/24); the law file 2/3. pyflakes clean on all four.
`python3 tools/dev/check_portable_paths.py` → `ok: 2988 tracked paths are portable`. Nothing under `src/ tools/ plugin/
skills/` touched (`sync_plugin.py --check`: `plugin in sync with source` at cloud-setup; moot for this diff). `/verify`
skipped — tests-only diff, no runtime surface (commit trailer says so).

**Whole merged shard** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`,
102 files, same 4-vCPU cloud VM, sequential runs, docs-read audit on — no section printed on any run = no offender):
```
origin/main 59a89d8 (worktree)     2036 passed, 134 skipped, 3 xfailed, 3 warnings in 570.91s
this branch, first cut             2036 passed, 134 skipped, 3 xfailed, 3 warnings in 557.22s
this branch, bc73d8d              2036 passed, 134 skipped, 3 xfailed, 3 warnings in 558.41s   (post-/simplify; = main, nothing moved)
```
The review-round head adds only the two `ADOPTERS` rows in the law file (four files re-run: 50 passed; expected shard = main + 2).
The 3 warnings are main's (`PytestRemovedIn10Warning`); skips identical (134).

### The optional stretch — not taken, and why (each is more than a rename)

- `tests/test_gates_shared_walk.py` (would empty `EXEMPT`): its `_rewrite_stream(src, dst, name, mutate)` takes an
  **in-place** `mutate(bytearray) -> None` (`_smash64`, two local `flip`s, a `lambda raw: _smash64(raw, off)`), and
  `_smash64` is also applied in place inside `_with_second_partition`. Moving to conftest's pure `damage(bytes) -> bytes`
  means either an adapter helper or reshaping `_smash64`/`flip` and `_with_second_partition` — five call sites change
  shape. Mechanical-ish, but not "a lambda away", and its autouse `_constants_restored` (after-only framing check, no
  `active_release`) is not `no_release_leak` either. Filed as its own task issue, #604 (Refs #602 #579), rather than stretched here.
- `tests/test_partition_header_verdict.py`: `_rewrite(src, dst, mutate_by_name: dict, extra=(), drop=())` mutates several
  streams, appends entries and drops a list — a richer primitive than `rewrite_stream`'s one stream; only `_partition` →
  `partition_of` is mechanical, and neither name is on `FORBIDDEN`, so a half-adoption buys nothing. Left.
- `tests/test_readers_own_release.py`: its autouse `_constants_restored` compares `(framing, FF.CD_SEPARATOR,
  FF.CD_END_RECORD, ADOC._DECODER)` before/after but never asserts `active_release() is None` — switching to
  `no_release_leak` + an FF-token `release_leak_extra` would *add* an assertion to 20-odd tests. Not adoption-only. Left.

### /simplify pass (four angles) — taken / not taken

Taken: **simplification** — the first cut's `_extras()` + `_constants()` + `release_leak_extra` trio in
`test_release_ctx_refusal.py` collapsed to `_constants()` + the override (one named callable handed to
`release_leak_extra`, the shape `test_inspect_release` / `test_estorage_cli_release` use); `test_rvt_edit_refusal.bad()`
hoists `any_pin` like its sibling so every `out[...]` entry is one line; the stale "built like test_release_ctx_refusal's"
docstring clause in `test_edit_status.schema_dmg` went with the builder; the `EXEMPT` comment reworded (above).
**Reuse** — clean (nothing left re-implements a conftest helper; the two-line "text file named `.rvt`" builder has no
conftest recipe and conftest is frozen here). **Efficiency** — clean, no more work than before (same container passes per
damaged copy, same pin reads, every `bad` / `trunc64k*` / `schema_dmg` fixture still module-scoped; the guard evaluates
`native_constants()` twice per snapshot in the one file with extras — a handful of `getattr`s). **Altitude** — the seam
used is the designed one; three deeper placements surfaced, all outside this territory, filed as #605: a conftest
`context_constants()` (the write-side sibling of `ladder_constants()` — today three in-process context callers watch three
different subsets of what `host_release_context` swaps), the law's `ADOPTERS` ratchet extended to the two files this PR
turned from an autouse guard into a one-line opt-in (since pulled INTO this PR on the tech lead's ruling — above), and
`test_edit_status.py` opting into the guard at all.

### Follow-ups (filed, task-shaped)

- **#604** — `test_gates_shared_walk.py` adopts `rewrite_stream` / `partition_of` (mutate → damage reshaping) and `EXEMPT` becomes empty. Refs #602 #579.
- **#605** — conftest `context_constants()`; the in-process context callers hand it to `release_leak_extra`; `test_edit_status.py` opts in (its `ADOPTERS` bullet is already done here for the two refusal files; what remains of it is "derive the list"). Refs #602 #579.

BRANCH STATE (cam/602-conftest-adoption): `tests/test_rvt_edit_refusal.py`, `tests/test_release_ctx_refusal.py`,
`tests/test_edit_status.py` (helper adoption only), `tests/test_conftest_scaffolding.py` (the two `EXEMPT` deletions, `ADOPTERS` += the two refusal files, wording),
this section. No `tests/conftest.py` change; nothing under `src/`, `tools/`, `plugin/`, `skills/`; no shard drop-in needed
(all four files already in the merged shard); nothing staged for the viewer; no certification claim.

---

## 2026-08-11 — eng #604: `test_gates_shared_walk.py` adopts conftest's `rewrite_stream` / `partition_of`; the AST law's `EXEMPT` set is empty

**Stream:** eng #604 (issue #604; Refs #602 #579, and #266 / #430 for the file's origin). Written in this engineer's
voice under its own header; nothing above this rule was edited.

### What landed — helper adoption only (no assertion, test id, parametrize axis or skip condition changed)

1. **`tests/test_gates_shared_walk.py`** — the private in-place `_rewrite_stream(src, dst, name, mutate)` (`mutate(bytearray)
   -> None`) and `_partition(path)` are gone; the five call sites go through conftest's pure
   `rewrite_stream(src, dst, name, damage)` / `partition_of(path)`. The reshaping the issue asked for, and nothing else:
   `_smash64(raw, off)` is now a pure damage (`raw[:off] + b"\xff" * 64 + raw[off + 64:]` instead of the slice
   assignment), the two identical local `def flip(raw): raw[_IN_FIRST_MEMBER] ^= 0x04` closures become ONE module-level
   pure damage `_flip_bit(raw)` (the "one tiny local adapter" the DONE allows — kept local, not in conftest, for THIS
   issue: conftest was default-frozen here and the change is adoption-only; /simplify then found that both recipes DO have
   byte-identical siblings elsewhere under `tests/` — see the /simplify section and follow-up #617, which hoists them),
   the `lambda raw: _smash64(raw, _LOST_BODY[name])` keeps its spelling (it now *returns* the damaged bytes),
   and `_with_second_partition` computes `data = _smash64(part.data) if damaged else part.data` instead of smashing a
   `bytearray` in place. `bad = str(tmp_path / "x.rvt"); _rewrite_stream(edited, bad, …)` folds into
   `bad = rewrite_stream(edited, tmp_path / "x.rvt", …)` — the helper returns `os.fspath(dst)`, the same `str` the tests
   handed on before. `from rvt.container import open_rvt` left with `_partition`; `dataclasses` / `read_entries` /
   `write_cfb` stay for `_with_second_partition` (it *adds* a stream — not a `rewrite_stream` shape). The hoisted helper's
   one tightening (a missing stream name is a `KeyError`, never a silent verbatim copy) never fires here: the primary
   partition, `Global/Latest`, `Global/ElemTable` and `Contents` exist in every pin and in the 2025 edit (the identity
   table below built all of them).
2. **`_constants_restored` — left exactly as it is** (DONE bullet 2, first option). Measured, not assumed: with the autouse
   fixture deleted and `pytestmark = [pytest.mark.usefixtures("no_release_leak"), <the skipif>]` in its place the file is
   **12 passed** in 9.13 s — the stricter before/after + `active_release() is None` guard holds on every test (the
   module-scoped `edited` fixture enters `release_build_context` for 2025 and leaves it clean). Not switched here all the
   same, because switching *adds* two assertions to twelve tests (this issue is adoption-only: ids, assertions, outcomes
   identical) and an opt-in adopter belongs on the law's `ADOPTERS` ratchet, which is outside this issue's one-line
   territory in the law file. The measurement is handed to **#605** (whose DONE already says "ADOPTERS covers every file
   … or is derived: every non-exempt file that imports the scaffolding must request `no_release_leak`" — this file now
   imports it and is known to pass under it) as a comment there, not a new issue. Experiment reverted; `git diff` shows
   the fixture untouched.
3. **`tests/test_conftest_scaffolding.py`** — `EXEMPT = set()`; its `#:` comment now says NONE since #604, stays empty, and
   that a file growing a copy again is red in the law rather than a new entry; the module docstring's "minus a short,
   shrinking `EXEMPT` list of files whose copy is not yet conftest-shaped" → "its `EXEMPT` set is empty since #604 and
   must stay so (no file carries a copy of its own)". No law logic, `FORBIDDEN`, `ADOPTERS` or test body touched;
   `test_the_exempt_list_only_names_files_that_exist_and_still_need_it` iterates an empty set and stays collected (15 ids
   before, 15 after).

### Evidence

**`_with_second_partition` (and every other damaged copy) byte-identical, old builder vs new** — asserted BEFORE the old
code was deleted: a throwaway script imported the untouched origin/main module (`OLD._rewrite_stream`, `OLD._partition`,
`OLD._smash64`, `OLD._with_second_partition`, an in-place `flip`) next to the new pure damages on `conftest.rewrite_stream` /
`partition_of`, built every copy the tests build from each pinned base **and** from the 2025 level edit the module fixture
makes (`OLD._edit(2025, …)`), and compared sha256 (the returned second-partition name asserted equal too;
`OLD._partition(src) == partition_of(src)` on all four sources). 28/28 identical:

| source | copy | old sha256[:16] | new sha256[:16] | |
|---|---|---|---|---|
| 2026 | hard | `9fbf59a4bcee601c` | `9fbf59a4bcee601c` | == |
| 2026 | soft | `a068cb52094d02b4` | `a068cb52094d02b4` | == |
| 2026 | twin | `b3caa95661d85dd7` | `b3caa95661d85dd7` | == |
| 2026 | twin_bad | `794d8803dcba8295` | `794d8803dcba8295` | == |
| 2026 | lost-Contents | `16b3a993f9d51e1e` | `16b3a993f9d51e1e` | == |
| 2026 | lost-Global-ElemTable | `72e752e0ec4f75a1` | `72e752e0ec4f75a1` | == |
| 2026 | lost-Global-Latest | `46f717153e829857` | `46f717153e829857` | == |
| 2025 | hard | `6a354496a2fdfff4` | `6a354496a2fdfff4` | == |
| 2025 | soft | `8ef4e5306be3194c` | `8ef4e5306be3194c` | == |
| 2025 | twin | `36ecd172dffac07b` | `36ecd172dffac07b` | == |
| 2025 | twin_bad | `ca68a515dad6a7bd` | `ca68a515dad6a7bd` | == |
| 2025 | lost-Contents | `b840bec9457738a9` | `b840bec9457738a9` | == |
| 2025 | lost-Global-ElemTable | `8e109fa232eaf330` | `8e109fa232eaf330` | == |
| 2025 | lost-Global-Latest | `4ef0d5071e3e5d0a` | `4ef0d5071e3e5d0a` | == |
| 2024 | hard | `1dd9100bf896a48e` | `1dd9100bf896a48e` | == |
| 2024 | soft | `ece08f369d7e021a` | `ece08f369d7e021a` | == |
| 2024 | twin | `3a490b04169ceb24` | `3a490b04169ceb24` | == |
| 2024 | twin_bad | `6a578e8267d3c7c7` | `6a578e8267d3c7c7` | == |
| 2024 | lost-Contents | `c9691cc0c6caa7ac` | `c9691cc0c6caa7ac` | == |
| 2024 | lost-Global-ElemTable | `8dee37646656a843` | `8dee37646656a843` | == |
| 2024 | lost-Global-Latest | `8938c6c31564e270` | `8938c6c31564e270` | == |
| edit2025 | hard | `3a20509796a4568c` | `3a20509796a4568c` | == |
| edit2025 | soft | `77e0a8f3be00b873` | `77e0a8f3be00b873` | == |
| edit2025 | twin | `de0df7f522bfa021` | `de0df7f522bfa021` | == |
| edit2025 | twin_bad | `17859f5a2c971857` | `17859f5a2c971857` | == |
| edit2025 | lost-Contents | `709dec4b62fc0ebe` | `709dec4b62fc0ebe` | == |
| edit2025 | lost-Global-ElemTable | `66d94a534397d165` | `66d94a534397d165` | == |
| edit2025 | lost-Global-Latest | `0ec638dc4722c661` | `0ec638dc4722c661` | == |

(`ALL BYTE-IDENTICAL`; script and copies in the session scratchpad, not committed.)

**Collected ids and outcomes, before (origin/main `15b6fbe`) → after** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest
tests/test_gates_shared_walk.py tests/test_conftest_scaffolding.py -q -rs -p no:cacheprovider`; `--collect-only -q` id
lists `diff`ed → empty; the `-v` id+outcome lines `diff`ed → empty):

| file | collected before | collected after | ids `diff` | run before | run after |
|---|---|---|---|---|---|
| `tests/test_gates_shared_walk.py` | 12 | 12 | empty | 12 passed | 12 passed |
| `tests/test_conftest_scaffolding.py` | 15 | 15 | empty | 15 passed | 15 passed |
| both (`-q -rs`) | 27 | 27 | empty; `-v` outcome diff empty | **27 passed, 0 skipped** in 10.51 s | **27 passed, 0 skipped** in 9.81 s |

`RVT_DOCS_AUDIT=report` census of that run, before and after: `0 repo docs/ file(s) opened by this test process` — unchanged.
`git diff -U0 -- tests/ | grep -E '^[-+]\s*assert'` → nothing: no `assert` line added, removed or reworded.
`git grep -n "def _rewrite_stream" -- tests/` → nothing (exit 1). `git grep -n "_partition(" -- tests/test_gates_shared_walk.py` → nothing.

**The law bites both ways with `EXEMPT` empty** (mutations, reverted, `git diff` clean of them afterwards): appending
`def _rewrite_stream(src, dst, name, damage): …` to `tests/test_gates_shared_walk.py` → `test_no_module_carries_a_private_copy`
FAILED with `{'test_gates_shared_walk': ['_rewrite_stream']} -- import the own-release scaffolding from conftest instead
(#579)` (1 failed, 14 passed); putting `"test_gates_shared_walk"` back into `EXEMPT` →
`test_the_exempt_list_only_names_files_that_exist_and_still_need_it` FAILED with `test_gates_shared_walk carries no copy any
more: drop it from EXEMPT` (1 failed, 14 passed). Green again on revert (15 passed).

`git diff --numstat`: `tests/test_gates_shared_walk.py` **+22 −45**, `tests/test_conftest_scaffolding.py` +4 −4. pyflakes
clean on both. `python3 tools/dev/check_portable_paths.py` → `ok: 2989 tracked paths are portable`. Nothing under `src/ tools/ plugin/ skills/`
touched (`sync_plugin.py --check`: `plugin in sync with source` at cloud-setup; moot for this diff). `/verify` skipped —
tests-only diff, no runtime surface (commit trailer says so).

**Whole merged shard** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`,
102 files, same 4-vCPU cloud VM, sequential runs, docs-read audit on — no section printed on either run = no offender):
```
origin/main 15b6fbe (worktree)     2045 passed, 134 skipped, 3 xfailed, 3 warnings in 435.58s
this branch f908ac4                2045 passed, 134 skipped, 3 xfailed, 3 warnings in 442.15s   (= main, nothing moved)
```
The 3 warnings are main's (`PytestRemovedIn10Warning`); skips identical (134). The /simplify head (`e3bdab1`) and the record
fill-in after it change one docstring line, one `#:` comment line and this file — no non-comment source line — so the branch
run stands for the head (the two files re-run on the head all the same: 27 passed, ids identical).

### /simplify pass (four independent angles) — taken / not taken

Taken: **simplification** — two wording nits: the module docstring's new clause said edits *and* damaged copies are
written "through conftest's `rewrite_stream` / `partition_of`", but the edit is written by `commit_plans`, the twin by
`write_cfb`, and `partition_of` writes nothing → now "the damaged copies via conftest's `rewrite_stream`"; the two-line
`#:` comment above `EXEMPT` restated the module docstring → one line ("none since #604; a regrown copy goes red in the law
below, not in here"). Otherwise clean: every remaining import is live (`open_rvt` correctly gone; `dataclasses` /
`read_entries` / `write_cfb` serve `_with_second_partition`, `P` / `V` the kept fixture), `pname` is a local only where it
is reused after the rewrite and inlined where it is not, no `_partition` / `mutate` leftovers.
**Efficiency** — clean, tallied per call site: container opens per test unchanged (1 `open_rvt` + 1 `read_entries` + 1
`write_cfb` per damaged copy, exactly as before; nothing moved into a fixture); the old `bytearray(e.data)` + `bytes(raw)`
pair becomes slice-concatenation of the same order (≈ equal on a ~MB stream, once per test), and
`_with_second_partition(damaged=False)` drops from two full-stream copies to none (`part.data` by reference).
**Reuse** — clean *for this diff* (no conftest recipe reproduces these bytes: `zero_partition_header` = 16 × `0x00` @ 0,
`zero_schema_bytes` = 64 × `0x00` @ 2000, vs `_smash64` = 64 × `0xff` @ 280 / `_flip_bit` = `^ 0x04` @ 280, so local recipes
are what byte-identity requires; import style matches the sibling adopters), but it and **altitude** both corrected one
claim of my first draft — "no second caller exists" was wrong: `tests/test_partition_header_verdict.py:137` carries a
byte-for-byte `_smash64` (in-place shape; its default `_IN_GLOBAL_BODY = 8+10+200` is the offset this file spells as
`_LOST_BODY["Global/Latest"]`), `:142` `_twin_entry` is the `_with_second_partition` recipe, `:107` / `:112` are a
`_partition` and a multi-stream `_rewrite`; `tests/test_ecc_final_block.py:49` `_flip(raw, at, bit)` is the general pure bit
flip (`_flip_bit` = `_flip(raw, 280, 2)`) and `:130` `_variant` a third single-stream rewrite. None is callable from here
without a cross-test-module import (no sibling does that) and hoisting them is a conftest change with two more adopting
files — outside this adoption-only, conftest-frozen issue — so the right depth is a follow-up, filed as **#617** with those
file:lines, and the record above no longer says "no second caller". Altitude also **agreed** with leaving
`_constants_restored` (an opt-in without an `ADOPTERS` row would be an unratcheted guard; #605 owns that list; 12/12 under
the stricter guard is measured and recorded) and noted that the now-empty `EXEMPT` machinery (a self-check iterating
nothing) would normally be deleted — but #617 widens `FORBIDDEN` to the other spellings, at which point `EXEMPT` may
briefly hold real members again, so keeping it is deliberate, not residue. After the two wording edits the two files are
27 passed again, ids unchanged.

### Follow-ups (searched first; task-shaped)

- **#617** — conftest grows the offset damage recipes (`smash64(off)`, `flip_bit(at, bit)`) + a twin-partition entry
  builder; `test_partition_header_verdict.py` / `test_ecc_final_block.py` / this file adopt them byte-identically and the law's
  `FORBIDDEN` gains the retired spellings (`_partition`, `_rewrite`, `_variant`, `_smash64`, `_twin_entry`). Refs #604 #602 #579.
- No new issue for the guard switch: that this file passes 12/12 under `no_release_leak` is left as a comment on the
  existing **#605** (its `ADOPTERS` / derived-adopters bullet already covers "every file that imports the scaffolding").

BRANCH STATE (cam/604-shared-walk-conftest): `tests/test_gates_shared_walk.py` (helper adoption only),
`tests/test_conftest_scaffolding.py` (`EXEMPT = set()` + its comment and the docstring clause), this section. No
`tests/conftest.py` change; nothing under `src/`, `tools/`, `plugin/`, `skills/`; no shard drop-in needed (both files
already in the merged shard: `tests/ci_shard.d/266-shared-gate-walk.txt`, `579-scaffolding.txt`); nothing staged for the
viewer; no certification claim.

## 2026-08-11 — eng #617: conftest grows `rewrite_streams` / `twin_partition_entry` / `smash64` / `flip_bit`; `test_partition_header_verdict.py`, `test_ecc_final_block.py` and `test_gates_shared_walk.py` drop their private recipes; the AST law forbids the retired spellings

**Stream:** eng #617 (issue #617; Refs #604 #602 #579, and #458 / #501, #294, #266 / #430 for the three files' origins).
Written in this engineer's voice under its own header; nothing above this rule was edited. (The `.d/` fragment
convention of #636 had not landed on `main` (`ca74895`) when this was written, hence a dated section here.)

### What landed — helper adoption only in the three files (no test id, parametrize axis, skip condition or outcome changed)

1. **`tests/conftest.py`** (the own-release scaffolding section only) grows four names, and nothing else changes meaning:
   - `rewrite_streams(src, dst, damages: dict, extra=()) -> str` — the general form of `rewrite_stream`: every
     `{name: damage}` re-emitted as `damage(raw)`, a `None` damage **drops** the stream (the vocabulary
     `rewrite_stream(name, None)` already had — so "drop" is not a second kwarg but the same contract, and a dropped
     name now sits under the same missing-name `KeyError`, which the retired `_rewrite(..., drop=[...])` silently
     lacked), the ready-made `extra` entries appended after the container's own, everything else byte-identical,
     `src == dst` rewrites in place. `rewrite_stream(src, dst, name, damage)` is now literally
     `rewrite_streams(src, dst, {name: damage})` — same signature, same return, same `KeyError`, its scaffolding row
     green unchanged, and the sha table below proves the old body and the new one-loop form emit the same bytes.
   - `twin_partition_entry(src, damage=None) -> CfbEntry` — the first partition renamed to `Partitions/<N+1>` (a
     NON-primary partition once handed to `rewrite_streams(..., extra=[it])`), its raw bytes through `damage` when
     given. This ONE builder replaces `test_partition_header_verdict._twin_entry(src, mutate)` and
     `test_gates_shared_walk._with_second_partition(src, dst, damaged=)` (which was builder + writer in one).
   - `smash64(raw, off) -> bytes` — 64 × `0xff` at `off`. **Shape chosen: a pure `bytes -> bytes` with a required
     `off`, no default and no callable-factory.** Why: the two retired copies disagreed on the default (`280` = inside a
     partition's first block body in shared_walk, `218` = inside a `Global/*` gzip body in header_verdict), so any
     default in conftest would be wrong for one caller; the offsets are framing-layout knowledge that stays with the
     caller (altitude review agreed: if a third file ever needs one, promote a constant built from engine symbols, not
     `44 + 26 + 10 + 200`); and every other conftest recipe is a plain `bytes -> bytes`, so a fixed offset is spelled
     `lambda raw: smash64(raw, OFF)` — the spelling shared_walk's `_LOST_BODY` site already used.
   - `flip_bit(raw, at, bit=0) -> bytes` — `test_ecc_final_block._flip` verbatim (bytearray copy, `^= 1 << bit`), so
     it indexes like `raw[at]` (negative from the end, out of range raises) and serves both the synthetic-stream
     asserts that call it directly and the `rewrite_stream` damages; shared_walk's `_flip_bit(raw)` was
     `flip_bit(raw, 280, 2)`.
2. **`tests/test_partition_header_verdict.py`** — `_partition`, `_rewrite`, `_zero16`, `_smash64`, `_twin_entry` deleted
   (−76 / +27); the 13 call sites go through `partition_of` / `rewrite_stream` / `rewrite_streams` /
   `twin_partition_entry` / `zero_partition_header` / `lambda raw: smash64(raw, _IN_GLOBAL_BODY)`. `_IN_GLOBAL_BODY`
   (the offset, with its comment) stays; `import dataclasses`, `write_cfb`, `read_entries` leave; `CfbEntry` (the
   orphan-stream test) and `open_rvt` (the partitionless test opens the copy) stay. `bad = str(tmp_path / …);
   _rewrite(edited, bad, …)` folds into `bad = rewrite_stream(s)(edited, tmp_path / …, …)` (returns the same `str`).
   The `dataclasses.replace(_twin_entry(edited), data=b"\x00" * 10)` short partition is `twin_partition_entry(edited,
   lambda raw: b"\x00" * 10)` — the same entry (/simplify).
3. **`tests/test_ecc_final_block.py`** — `_flip` and `_variant` deleted (−36 / +15); `flip_bit` is called where `_flip`
   was, `rewrite_stream` where `_variant` was, and the inline `with open_rvt(base) as d: pname =
   d.partition_streams()[0]` is `partition_of(base)`; `import dataclasses` leaves.
4. **`tests/test_gates_shared_walk.py`** — `_smash64`, `_flip_bit`, `_with_second_partition` deleted (−35 / +20); two
   thin local adapters remain, `_hard(raw) = smash64(raw, _IN_FIRST_MEMBER)` and `_soft(raw) = flip_bit(raw,
   _IN_FIRST_MEMBER, 2)` — one-line partial applications (the file's *choice of offset*), each used twice, no byte
   surgery of their own; altitude review: "exactly what the law should permit, not a regrown recipe". The twin tests
   build `twin_partition_entry(edited[, _hard])` and write it with `rewrite_streams(edited, dst, {}, extra=[it])`;
   `second = damaged.path` keeps the one assert that names the second partition textually unchanged. `dataclasses`,
   `write_cfb`, `read_entries` leave. **On territory:** the tech-lead brief named two adopting files; the issue's title,
   DONE and Territory name this third one too, #604's record hands exactly these three recipes to #617, and no open PR
   touches the file — so it is adopted here rather than left as the one place `_smash64` survives (which would have kept
   that spelling out of `FORBIDDEN`). Flagged in the PR for the reviewer to overrule.
5. **`tests/test_conftest_scaffolding.py`** — DATA + wording + behaviour rows, no law logic: `FORBIDDEN` gains the retired
   spellings `_partition _rewrite _variant _zero16 _smash64 _flip_bit _twin_entry _with_second_partition` and the shadows
   `rewrite_streams twin_partition_entry smash64 flip_bit`; **`_flip` is deliberately left out** — too generic a word to
   forbid tree-wide (its `#:` comment says so; see Findings for the honest caveat that `_partition` / `_rewrite` /
   `_variant` are hardly less generic — none collides today, checked over every `tests/test_*.py`); `EXEMPT` stays
   `set()`; `ADOPTERS` untouched; the module docstring names the new clause. Two behaviour rows:
   `test_offset_damage_recipes_are_what_their_names_say` (pure: `smash64` lands 64 × `0xff` at `off` and only there,
   two offsets differ; `flip_bit` flips exactly bit `bit` of byte `at`, default bit 0, negative `at`, involution,
   `IndexError` out of range) and `test_rewrite_streams_damages_drops_and_appends_in_one_pass` (pin-backed: damage +
   drop + append in one call, every other stream byte-identical, `twin_partition_entry`'s path / verbatim data /
   damaged data, `rewrite_streams(pin, dst, {})` byte-identical to `rewrite_stream(pin, dst, pname, identity)`,
   `KeyError` before anything is written). A local `_streams(path)` map dedupes the four `{e.path: e.data …}`
   comprehensions the two pin-backed rows would otherwise spell (/simplify reuse).

### Evidence

**Every damaged copy byte-identical, old private recipe vs new conftest helper** — asserted BEFORE the old code was
deleted (first run against the untouched on-disk modules, 84/84), and re-run on the final head against
`git show origin/main:tests/<file>` copies of the three modules + origin/main's `conftest.py` (loaded under other module
names; shared_walk's copy was given origin/main's `rewrite_stream` for the load, asserted `SW.rewrite_stream is
OLDC.rewrite_stream`). Sources: the three pins + the 2025 level edit both module fixtures make (`OLD._edit(2025, …)`).
Every copy each file builds, including the two **in-place** `rewrite_stream(path, path, …)` shapes the job tests stage
and the `Global/Orphan` extra; the returned second-partition name compared too; `OLD._partition(src) ==
partition_of(src) == OLDC.partition_of(src)` on all four sources; plus 9/9 pure-recipe checks on the synthetic streams
`test_genuinely_corrupted_blocks_still_count` frames (`_flip` vs `flip_bit` at its six (at, bit) pairs, in-place
`_smash64` / `_zero16` vs `smash64(raw, 218)` / `zero_partition_header`, shared_walk's `_smash64` / `_flip_bit` vs
`smash64(raw, 280)` / `flip_bit(raw, 280, 2)`). **84/84 identical, `ALL BYTE-IDENTICAL`** (the `sw.*` rows reproduce
#604's recorded digests, e.g. edit2025 `sw.hard` `3a20509796a4568c`; `hv.twin_ok` == `sw.twin` on every source, as
two spellings of one recipe should):

| source | copy | old sha256[:16] | new sha256[:16] | | second partition (old / new) |
|---|---|---|---|---|---|
| 2026 | hv.primary_hdr0 | `0bc5d18be84103c6` | `0bc5d18be84103c6` | == | |
| 2026 | hv.twin_hdr0 | `3b32a21715b5a8c2` | `3b32a21715b5a8c2` | == | Partitions/22 / Partitions/22 |
| 2026 | hv.both_hdr0 | `e298eb6e963d25ee` | `e298eb6e963d25ee` | == | |
| 2026 | hv.primary_hdr0_w | `d4a621e4b13b6b57` | `d4a621e4b13b6b57` | == | |
| 2026 | hv.twin_et_lost | `c11d06d39023a86d` | `c11d06d39023a86d` | == | |
| 2026 | hv.nopart | `6c061b8abb737237` | `6c061b8abb737237` | == | |
| 2026 | hv.nopart_noet | `09a5c4928bbe6c0f` | `09a5c4928bbe6c0f` | == | |
| 2026 | hv.twin_ok | `b3caa95661d85dd7` | `b3caa95661d85dd7` | == | Partitions/22 / Partitions/22 |
| 2026 | hv.job_hdr0_inplace | `0bc5d18be84103c6` | `0bc5d18be84103c6` | == | |
| 2026 | hv.job_nopart_inplace | `6c061b8abb737237` | `6c061b8abb737237` | == | |
| 2026 | hv.orphan | `bb80d0a23e64dd20` | `bb80d0a23e64dd20` | == | |
| 2026 | ec.et_band | `66dfdb986d2a059e` | `66dfdb986d2a059e` | == | |
| 2026 | ec.trailer_flip | `d019aac99b50a2a8` | `d019aac99b50a2a8` | == | |
| 2026 | ec.final_flip | `dacc2738d0b249b2` | `dacc2738d0b249b2` | == | |
| 2026 | sw.hard | `9fbf59a4bcee601c` | `9fbf59a4bcee601c` | == | |
| 2026 | sw.soft | `a068cb52094d02b4` | `a068cb52094d02b4` | == | |
| 2026 | sw.lost-Contents | `16b3a993f9d51e1e` | `16b3a993f9d51e1e` | == | |
| 2026 | sw.lost-Global-ElemTable | `72e752e0ec4f75a1` | `72e752e0ec4f75a1` | == | |
| 2026 | sw.lost-Global-Latest | `46f717153e829857` | `46f717153e829857` | == | |
| 2026 | sw.twin | `b3caa95661d85dd7` | `b3caa95661d85dd7` | == | Partitions/22 / Partitions/22 |
| 2026 | sw.twin_bad | `794d8803dcba8295` | `794d8803dcba8295` | == | Partitions/22 / Partitions/22 |
| 2025 | hv.primary_hdr0 | `75a6590e32c32a89` | `75a6590e32c32a89` | == | |
| 2025 | hv.twin_hdr0 | `bddf57c0f3b46de9` | `bddf57c0f3b46de9` | == | Partitions/21 / Partitions/21 |
| 2025 | hv.both_hdr0 | `e6875a0505f4ae07` | `e6875a0505f4ae07` | == | |
| 2025 | hv.primary_hdr0_w | `f8bbb544a84a64aa` | `f8bbb544a84a64aa` | == | |
| 2025 | hv.twin_et_lost | `18b36b247ca89825` | `18b36b247ca89825` | == | |
| 2025 | hv.nopart | `123b3e5150f6ddc9` | `123b3e5150f6ddc9` | == | |
| 2025 | hv.nopart_noet | `12de6396c5632cc8` | `12de6396c5632cc8` | == | |
| 2025 | hv.twin_ok | `36ecd172dffac07b` | `36ecd172dffac07b` | == | Partitions/21 / Partitions/21 |
| 2025 | hv.job_hdr0_inplace | `75a6590e32c32a89` | `75a6590e32c32a89` | == | |
| 2025 | hv.job_nopart_inplace | `123b3e5150f6ddc9` | `123b3e5150f6ddc9` | == | |
| 2025 | hv.orphan | `12ddb8c28a82f8ff` | `12ddb8c28a82f8ff` | == | |
| 2025 | ec.et_band | `50cde01980b107fa` | `50cde01980b107fa` | == | |
| 2025 | ec.trailer_flip | `7a4ce61e592b838e` | `7a4ce61e592b838e` | == | |
| 2025 | ec.final_flip | `4a72feb8deef6ce6` | `4a72feb8deef6ce6` | == | |
| 2025 | sw.hard | `6a354496a2fdfff4` | `6a354496a2fdfff4` | == | |
| 2025 | sw.soft | `8ef4e5306be3194c` | `8ef4e5306be3194c` | == | |
| 2025 | sw.lost-Contents | `b840bec9457738a9` | `b840bec9457738a9` | == | |
| 2025 | sw.lost-Global-ElemTable | `8e109fa232eaf330` | `8e109fa232eaf330` | == | |
| 2025 | sw.lost-Global-Latest | `4ef0d5071e3e5d0a` | `4ef0d5071e3e5d0a` | == | |
| 2025 | sw.twin | `36ecd172dffac07b` | `36ecd172dffac07b` | == | Partitions/21 / Partitions/21 |
| 2025 | sw.twin_bad | `ca68a515dad6a7bd` | `ca68a515dad6a7bd` | == | Partitions/21 / Partitions/21 |
| 2024 | hv.primary_hdr0 | `34f183c444a19702` | `34f183c444a19702` | == | |
| 2024 | hv.twin_hdr0 | `fca9fa06d1c003c0` | `fca9fa06d1c003c0` | == | Partitions/22 / Partitions/22 |
| 2024 | hv.both_hdr0 | `03c3703466b707ba` | `03c3703466b707ba` | == | |
| 2024 | hv.primary_hdr0_w | `61cea479db4bfc6a` | `61cea479db4bfc6a` | == | |
| 2024 | hv.twin_et_lost | `d61841cd35e3861d` | `d61841cd35e3861d` | == | |
| 2024 | hv.nopart | `bf2fe57825db9ae1` | `bf2fe57825db9ae1` | == | |
| 2024 | hv.nopart_noet | `0b6628712d039841` | `0b6628712d039841` | == | |
| 2024 | hv.twin_ok | `3a490b04169ceb24` | `3a490b04169ceb24` | == | Partitions/22 / Partitions/22 |
| 2024 | hv.job_hdr0_inplace | `34f183c444a19702` | `34f183c444a19702` | == | |
| 2024 | hv.job_nopart_inplace | `bf2fe57825db9ae1` | `bf2fe57825db9ae1` | == | |
| 2024 | hv.orphan | `4e1d3a098940a561` | `4e1d3a098940a561` | == | |
| 2024 | ec.et_band | `3bbc49568f043f3a` | `3bbc49568f043f3a` | == | |
| 2024 | ec.trailer_flip | `5cdc8d271777c8d7` | `5cdc8d271777c8d7` | == | |
| 2024 | ec.final_flip | `b65b26cb16a9d79c` | `b65b26cb16a9d79c` | == | |
| 2024 | sw.hard | `1dd9100bf896a48e` | `1dd9100bf896a48e` | == | |
| 2024 | sw.soft | `ece08f369d7e021a` | `ece08f369d7e021a` | == | |
| 2024 | sw.lost-Contents | `c9691cc0c6caa7ac` | `c9691cc0c6caa7ac` | == | |
| 2024 | sw.lost-Global-ElemTable | `8dee37646656a843` | `8dee37646656a843` | == | |
| 2024 | sw.lost-Global-Latest | `8938c6c31564e270` | `8938c6c31564e270` | == | |
| 2024 | sw.twin | `3a490b04169ceb24` | `3a490b04169ceb24` | == | Partitions/22 / Partitions/22 |
| 2024 | sw.twin_bad | `6a578e8267d3c7c7` | `6a578e8267d3c7c7` | == | Partitions/22 / Partitions/22 |
| edit2025 | hv.primary_hdr0 | `336e3cd6bb2b5344` | `336e3cd6bb2b5344` | == | |
| edit2025 | hv.twin_hdr0 | `4655bfce39f69b75` | `4655bfce39f69b75` | == | Partitions/21 / Partitions/21 |
| edit2025 | hv.both_hdr0 | `e8b3937f1eb618ef` | `e8b3937f1eb618ef` | == | |
| edit2025 | hv.primary_hdr0_w | `0baf62ba51c3d5ef` | `0baf62ba51c3d5ef` | == | |
| edit2025 | hv.twin_et_lost | `102e422ab3ac82ae` | `102e422ab3ac82ae` | == | |
| edit2025 | hv.nopart | `123b3e5150f6ddc9` | `123b3e5150f6ddc9` | == | |
| edit2025 | hv.nopart_noet | `12de6396c5632cc8` | `12de6396c5632cc8` | == | |
| edit2025 | hv.twin_ok | `de0df7f522bfa021` | `de0df7f522bfa021` | == | Partitions/21 / Partitions/21 |
| edit2025 | hv.job_hdr0_inplace | `336e3cd6bb2b5344` | `336e3cd6bb2b5344` | == | |
| edit2025 | hv.job_nopart_inplace | `123b3e5150f6ddc9` | `123b3e5150f6ddc9` | == | |
| edit2025 | hv.orphan | `1aab52ba54d3b995` | `1aab52ba54d3b995` | == | |
| edit2025 | ec.et_band | `fb178104b785cbf2` | `fb178104b785cbf2` | == | |
| edit2025 | ec.trailer_flip | `5c320ee48d668174` | `5c320ee48d668174` | == | |
| edit2025 | ec.final_flip | `bf74a2582ef6840f` | `bf74a2582ef6840f` | == | |
| edit2025 | sw.hard | `3a20509796a4568c` | `3a20509796a4568c` | == | |
| edit2025 | sw.soft | `77e0a8f3be00b873` | `77e0a8f3be00b873` | == | |
| edit2025 | sw.lost-Contents | `709dec4b62fc0ebe` | `709dec4b62fc0ebe` | == | |
| edit2025 | sw.lost-Global-ElemTable | `66d94a534397d165` | `66d94a534397d165` | == | |
| edit2025 | sw.lost-Global-Latest | `0ec638dc4722c661` | `0ec638dc4722c661` | == | |
| edit2025 | sw.twin | `de0df7f522bfa021` | `de0df7f522bfa021` | == | Partitions/21 / Partitions/21 |
| edit2025 | sw.twin_bad | `17859f5a2c971857` | `17859f5a2c971857` | == | Partitions/21 / Partitions/21 |

(`hv.*` = `test_partition_header_verdict.py`, `ec.*` = `test_ecc_final_block.py`, `sw.*` = `test_gates_shared_walk.py`;
script and copies in the session scratchpad, not committed.)

**Collected ids and outcomes, before (origin/main `ca74895`) → after (head)** — `RVT_SKIP_LARGE=1 .venv/bin/python -m
pytest <the four files> -q -rs -p no:cacheprovider`; `--collect-only -q` id lists `diff`ed per file; the `-v`
id+outcome lines `diff`ed:

| file | collected before | collected after | ids `diff` | run before | run after |
|---|---|---|---|---|---|
| `tests/test_partition_header_verdict.py` | 19 | 19 | empty | 19 passed | 19 passed |
| `tests/test_ecc_final_block.py` | 39 | 39 | empty | 39 passed | 39 passed |
| `tests/test_gates_shared_walk.py` | 12 | 12 | empty | 12 passed | 12 passed |
| `tests/test_conftest_scaffolding.py` | 15 | 17 | + the two new rows, nothing else | 15 passed | 17 passed |
| all four (`-q -rs`) | 85 | 87 | `-v` outcome diff = exactly the two new rows `PASSED` | **85 passed, 0 skipped** in 15.58 s | **87 passed, 0 skipped** in 16.30 s |

`RVT_DOCS_AUDIT=report` census of that run, before and after: `0 repo docs/ file(s) opened by this test process` — unchanged.

**`git diff -U0 origin/main -- tests/ | grep -E '^[-+]\s*assert'`** — in the three adopting files: **no assertion added,
removed or changed in meaning; six lines differ by the helper's name only** (five in
`test_ecc_final_block.py::test_genuinely_corrupted_blocks_still_count`: `_flip(` → `flip_bit(` — the same function body,
9/9 pure checks above on those exact inputs; one in `test_partition_header_verdict.py::test_twin_header_zeroed_is_a_fail_verdict`:
`_errors_at(rep, _partition(edited))` → `_errors_at(rep, partition_of(edited))` — the same `open_rvt(...).partition_streams()[0]`),
and one `-assert` that was no test assertion: `_variant`'s own `assert any(... e.path == stream ...)` missing-name guard,
now `rewrite_streams`' `KeyError`. Every other `+assert` in the diff is in the two new scaffolding rows.
`git grep -n "def _smash64\|def _twin_entry\|def _variant\|def _rewrite(\|def _partition(\|def _flip\|def _with_second_partition\|def _zero16" -- tests/` → nothing (exit 1).

**The law bites with the widened `FORBIDDEN`** (mutation, reverted, `git status` clean of it afterwards): appending a
`def _smash64(raw, off=280): …` to `tests/test_gates_shared_walk.py` and `def _rewrite(…)` / `def _twin_entry(…)` stubs to
`tests/test_partition_header_verdict.py` → `test_no_module_carries_a_private_copy` FAILED with
`{'test_gates_shared_walk': ['_smash64'], 'test_partition_header_verdict': ['_rewrite', '_twin_entry']} -- import the
own-release scaffolding from conftest instead (#579)` (1 failed, 16 passed); green again on revert (17 passed).

`git diff --numstat origin/main -- tests/`: `conftest.py` +49 −11, `test_conftest_scaffolding.py` +58 −10,
`test_ecc_final_block.py` +15 −36, `test_gates_shared_walk.py` +20 −35, `test_partition_header_verdict.py` +27 −76
(net −1 line for four new shared helpers and two new tests). pyflakes clean on all five.
`python3 tools/dev/check_portable_paths.py` → `ok: 3013 tracked paths are portable`. `tools/sync_plugin.py --check` →
`plugin in sync with source` (moot: nothing under `src/ tools/ plugin/ skills/` touched). `/verify` skipped — tests-only
diff, no runtime surface (commit trailer says so).

**Whole merged shard** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`,
same 4-vCPU cloud VM, sequential runs, docs-read audit on — no audit section printed on either = no offender):
```
origin/main ca74895 (worktree)     2171 passed, 134 skipped, 3 xfailed, 3 warnings in 457.46s
this branch on ca74895 (d03646f)   2173 passed, 134 skipped, 3 xfailed, 3 warnings in 470.37s   (= main + the 2 new law rows)
```
= main + the two new scaffolding rows, nothing else moved (run on the /simplify head's tree at base `ca74895`; the record commit after it
touches only this file, and the later rebase onto `6d95f32` — #633, famgen only, no file in common with this diff —
changed nothing under these five files: the four re-run there, 87 passed, ids identical); the 3 warnings are main's (pytest's class-scoped-fixture
deprecation notice); skips identical (134).

### Findings / limits, stated

- **`FORBIDDEN` is a lexical ratchet, and this issue made that more visible, not less.** It now forbids words as generic as
  `_partition` / `_rewrite` / `_variant` tree-wide (the issue's title asked for exactly these; no `tests/test_*.py` binds any
  of them today) while `_flip` is left out for being generic — consistent only as an admission that the mechanism matches
  spellings, not the primitive. The altitude pass named the primitive-level rule ("no test module outside an allow-list
  pairs `read_entries` with `write_cfb`") and two files such a rule would make someone classify once
  (`tests/test_validate_footer_blob.py::strip_footer_blob`, `tests/test_input_release.py`'s synthetic-container builders —
  per the reuse pass neither is byte-for-byte a `rewrite_stream(s)`: one re-frames *logical* bytes, the other builds
  containers). That is law LOGIC, outside this issue's data-lines-only territory in the law file → **#639**.
- **The permanently empty `EXEMPT` set** and its self-check were kept by #604 in case #617 needed a non-empty `EXEMPT`
  again; it did not (nothing was left private that the law can see). Deleting the machinery is also law logic → folded
  into #639's DONE rather than done here.
- **The loop's real home is the engine.** `src/rvt/writer.py:244-361` hand-rolls the same `read_entries` →
  `dataclasses.replace` → `write_cfb` pass four times (`corrupt_trailer_bytes` is a damage recipe living in `src/`), and
  `rvt.cfb_writer` / `rvt.roundtrip` export no rewrite API for either side to call. Out of a tests-only charter → **#640**
  (`area:engine`), with conftest's `rewrite_streams` to become its thin caller.
- Two inline single-bit flips on synthetic ECC blocks in `tests/test_bare_family_validate.py:130-132, 200-202` are
  `flip_bit(blk, p >> 3, p & 7)` / `flip_bit(raw, off, 3)` byte-for-byte (reuse pass). Not module-level helpers, so not the
  law's concern and outside the three files; three lines each — noted here, not worth an issue of their own (#639's
  classification pass will meet them).
- Efficiency, tallied per call site against origin/main (pins are ~0.58 MB; `read_entries` ≈ 1.5 ms, `open_rvt` ≈ 0.3 ms,
  `write_cfb` ≈ 0.7 ms warm): header_verdict and ecc identical opens/reads/writes per test (origin/main's `_twin_entry`
  already did its own open + read); shared_walk's twin test pays **+2 `read_entries` (≈ 3 ms)** because
  `_with_second_partition` reused one entry list for builder and writer while `twin_partition_entry` + `rewrite_streams`
  each read — noise against a test that spends hundreds of ms in the gates, and not worth an `entries=` wrinkle on the
  helper; the new pin-backed scaffolding row costs ≈ 20 ms. Net: a wash.

### /simplify pass (four independent angles) — taken / not taken

Taken: **reuse** — a `_streams(path)` map in the scaffolding file instead of four identical comprehensions (the existing
`rewrite_stream` row's two included; its `dropped` set is now the stream paths rather than every entry path — the assertion
on it reads the same). **Simplification** — `rewrite_stream`'s docstring no longer restates `rewrite_streams`' (one line:
"the one-stream `rewrite_streams`"); `rewrite_streams`' history tail cut to `(the ONE such loop under tests/, #579 / #617)`;
`smash64`'s no-default rationale tightened (kept — the issue asked the shape's *why* to be stated, and the docstring is where
the next caller looks); the short partition built through `twin_partition_entry`'s own `damage` instead of
`dataclasses.replace` around it (drops header_verdict's last `dataclasses` use); `_hard` / `_soft` docstrings say
"= `smash64` / `flip_bit` at `_IN_FIRST_MEMBER`"; the ecc and conftest module-docstring clauses reworded so `flip_bit` does
not read as belonging to `rewrite_stream`. Not taken: dropping `second = damaged.path` (kept on purpose — it is what leaves
that assert line textually identical); trimming the new rows' "second offset differs", "path is N+1" and "one loop behind
both" asserts (each states a piece of the contract independently of the implementation; ≈ 6 lines, kept); forbidding or
un-forbidding the generic words (→ #639, above). **Efficiency** — nothing to fix (above). **Altitude** — (1) drop-as-`None`,
(2) offsets per file, (3) `_hard`/`_soft`: right depth; (4) lexical law and (5) empty `EXEMPT`: → #639; (6) engine API: → #640.

### Follow-ups (searched first — `search_issues` on the law / on a cfb rewrite API: none open or closed; task-shaped)

- **#639** — the scaffolding AST law forbids the private stream-rewrite loop structurally, drops the generic words from
  `FORBIDDEN`, retires the empty `EXEMPT` machinery. Refs #617 #604 #579. P2 · area:process.
- **#640** — `rvt.cfb_writer` grows ONE entry-rewrite API; `writer.py`'s four loops fold onto it; conftest's
  `rewrite_streams` becomes its caller. Refs #617. P2 · area:engine.

BRANCH STATE (cam/617-recipe-hoist): `tests/conftest.py` (scaffolding section: `rewrite_streams`, `twin_partition_entry`,
`smash64`, `flip_bit`; `rewrite_stream` a one-line call of the general form; module docstring clause),
`tests/test_partition_header_verdict.py` / `tests/test_ecc_final_block.py` / `tests/test_gates_shared_walk.py` (helper
adoption only), `tests/test_conftest_scaffolding.py` (`FORBIDDEN` widened + its comment, docstring clause, two behaviour rows,
`_streams`), this section. Nothing under `src/`, `tools/`, `plugin/`, `skills/`; no shard drop-in needed (all four files
already in the merged shard: `tests/ci_shard.d/458-partition-header-verdict.txt`, `294-final-block-law.txt`,
`266-shared-gate-walk.txt`, `579-scaffolding.txt`); nothing staged for the viewer; no certification claim.

## 2026-08-11 — eng #640: the engine grows ONE entry-rewrite pass (`rvt.roundtrip.rewrite_entries`); `writer.py`'s four variant builders fold onto it byte-identically; conftest's `rewrite_streams` becomes its caller

**Stream:** eng #640 (session `eed919cf`). **Issue:** #640 (Refs #617; #579 for the scaffolding, #294 / #236 for
`writer.py`'s variant builders). **Territory used:** `src/rvt/roundtrip.py` (new function), `src/rvt/writer.py` (folds
only), their `plugin/lib` mirrors via `tools/sync_plugin.py`, `tests/conftest.py` (`rewrite_streams` body only), new
`tests/test_cfb_rewrite_entries.py` + `tests/ci_shard.d/640-cfb-rewrite-entries.txt`, this section (appended at the end;
`docs/inbox/README.md` / the `.d/` fragment convention of #643 had not landed on main when this was written). Not touched:
`commit.py` / `manipulate.py` / `reduce.py` and the other same-shape sites (measured below → #646), `src/rvt/versions/**`,
`cfb_writer.py`, `tests/test_conftest_scaffolding.py`, the three #617 adopters.

### What landed

1. **`rvt.roundtrip.rewrite_entries(src, dst, replace, extra=()) -> str`**, `replace: Mapping[str, StreamEdit]` with
   `StreamEdit = bytes | Callable[[bytes], bytes] | None`: for every `{path: edit}` the *stream* at that path gets `edit`
   itself (bytes), `edit(raw)` (callable; raw = the bytes exactly as stored, still paged), or is dropped (`None`); `extra`
   (`CfbEntry`s) appended after the container's own entries; every other entry — order, bytes, CLSIDs, state bits, FILETIMEs
   — carried over exactly as `roundtrip()` does; a path naming no stream of `src` (absent, or a storage) →
   `KeyError("no stream … in …")` raised after the read and **before `dst` is opened**; `src` is read fully (olefile closed)
   before the write, so `src == dst` rewrites in place; PathLike accepted, `str(dst)` returned.
   - **Why `roundtrip.py`, not `cfb_writer.py`** (the issue said pick one and say why): the pass *is* `read_entries` + filter
     + `write_cfb`; `read_entries` (olefile-backed) lives in `roundtrip`, and `cfb_writer` is the leaf, stdlib-only [MS-CFB]
     writer that `roundtrip` already imports and whose docstring promises "no dependencies outside the standard library" —
     the rewrite there would invert that arrow (circular) or drag olefile into the leaf. `roundtrip` already pairs *their*
     reader with *our* writer (`roundtrip()` is `rewrite_entries(src, dst, {})` plus timing and `makedirs`) and re-exports
     `CfbEntry` / `write_cfb` / `read_entries`, so a caller keeps one import line.
   - **Why `-> str`, not `CfbLayout`** (either was allowed): every existing caller uses the path (conftest's helpers and their
     adopters chain `open(rewrite_streams(…))`; `writer.py`'s builders return their own report dicts) and none uses the
     layout; the day one does, it is a one-line change.
   - **Why `bytes` values, a superset of the issue's `Callable | None` signature — the one deliberate deviation, for the
     reviewer to rule on.** Two of the four folded builders (and all eleven measured candidates, #646) hold *precomputed* bytes:
     `build_variant`'s `trailer_fn` can be stateful across streams (`trailer_random_factory`'s RNG is consumed singles-then-
     partitions in sorted order, not directory order), so its bytes must be computed eagerly in the old order, and
     `regzip_*` need the `RvtDocument` view. The first cut kept the literal signature and shipped a private
     `writer._swap_in({name: bytes}) → {name: lambda _old, new=new: new}` adaptor; the /simplify altitude pass called that
     what it is — a special case layered on the shared pass to satisfy a type — and the widening (`edit if
     isinstance(edit, bytes) else edit(e.data)`, one line) deletes the adaptor outright while conftest's contract stays a
     strict subset (its rows green unchanged). If overruled: restore `_swap_in` (6 lines) — bytes on disk identical either way
     (sha table run on both cuts).
2. **`src/rvt/writer.py` — all four hand-rolled passes folded, none left.**
   - `zero_full_trailers_only` → `rewrite_entries(in, out, dict.fromkeys(streams, _zero_full_trailers))`,
     `_zero_full_trailers(raw) = repage_like(depage(raw), raw, trailer_zero)` — a pure function of the stored bytes
     (`doc.logical(name)` *is* `depage(doc.raw(name))`, and `doc.raw` *is* the olefile stream = `CfbEntry.data`), so its
     `open_rvt` pass went too. `streams` is listed once up front (the old body iterated it and then `list()`-ed it again for
     the report — a generator would have reported `[]`; lists, the only documented use, unchanged).
   - `corrupt_trailer_bytes` → `rewrite_entries(in, out, {stream: flip})`, `flip` closing over `start` / `count` / `page` and
     raising the same `ValueError` for a stream with no such full-page trailer — inside the pass, i.e. still before any write
     (the new test asserts no file appears). Its `open_rvt` pass went (same identity).
   - `regzip_streams_variant`, `build_variant` → keep their `open_rvt` block (recompression needs members / prefix / inflate /
     the block walker) and hand the finished `{name: bytes}` map to the pass. `build_variant`'s docstring now states the
     ordering law its stateful `trailer_fn` depends on; its own up-front `KeyError("streams not in file: …")` stays (fires
     before any recompression, with the message `tools/make_acceptance.py` users know).
   - The issue's "name the ones whose shape does NOT match (per-stream state threaded across entries) and leave them":
     **none of the four threads state across *entries*.** The only cross-item state is `trailer_fn`'s across the *streams it
     recompresses*, preserved by computing those bytes eagerly in the old order — the sha table is what proves it. So all four
     fold and nothing was forced. `writer.py` no longer imports `dataclasses`, `CfbEntry`, `write_cfb`, `read_entries`
     (nothing imported those *through* `rvt.writer`: `git grep` over `src/ tools/ tests/` empty).
3. **`tests/conftest.py::rewrite_streams`** — body is `return rewrite_entries(src, dst, damages, extra)`; signature and the
   test-side wording kept, one clause added naming the engine pass. `rewrite_stream`, `twin_partition_entry`, the damage
   recipes, `tests/test_conftest_scaffolding.py` (17 rows green unchanged) and the three #617 adopters: untouched.
4. **`tests/test_cfb_rewrite_entries.py`** (new; pinned bases only; `no_release_leak` on module-wide because the
   `build_variant` row enters a host release context for a foreign pin's partition lane): 5 contract rows (no-edit pass ==
   `roundtrip()` byte-for-byte, PathLike in / `str` back; a callable edit is handed the stored bytes and changes only its stream,
   entry order and directory metadata kept; bytes value replaces, `None` drops, `extra` lands last; absent name / storage name /
   bad name beside a good one → `KeyError` and no file; `src == dst` in place == apart) and 5 rows that are the four builders'
   first direct tests (logical bytes identical + every full trailer zero; exactly the flipped bytes at the documented offset,
   `ValueError` / `KeyError` write nothing; payload identical under our deflate with and without the kept tail; single +
   partition lanes payload-identical per block under the host context, `verify_readback` 0 CRC failures). Shard drop-in
   `tests/ci_shard.d/640-cfb-rewrite-entries.txt`.

### Evidence

**Byte identity of the fold** — origin/main's hand-rolled loops vs the folded functions: sha256 of each public function's
documented use (`tools/make_acceptance.py` V1–V7, `tools/make_batch2.py` V8–V11, adapted to the pins' geometry —
`Global/ElemTable` is sub-page on the pins, so the trailer probes use `Global/Latest` (1 full page) and `Formats/Latest` (2) —
plus an in-place `src == dst` case), per pinned base, foreign pins under `host_release_context` so the partition lanes frame by
name. Driver kept in the session scratchpad (`sha_table.py <outdir> before|after`); the two JSONs compared key by key:
**39/39 EQUAL** — asserted before the old loops left the branch, re-asserted after the rebase onto `6fd74ee` and again after
the `bytes`-value widening (three "after" runs, all equal to "before").

| case \ base (sha256, first 16 hex) | G_ABPD (2026) | G_ABPD_2025 | G_ABPD_2024 |
|---|---|---|---|
| V1 `build_variant(["Global/Latest"], trailer_zero)` | d8c0c31cc2617896 | 13af1abbd4f62952 | e2485918f5fa4c17 |
| V2 `build_variant(["Global/Latest"], trailer_copy)` | f91cbe086608a6f7 | 7f208046fa44f249 | 9f2d342907fa26b2 |
| V3 `build_variant(all single-member gz, trailer_zero)` | 60a497a663329e9c | ae58c2ac139a8c8c | b13da400ce2fbd3c |
| V4 `build_variant(["Formats/Latest"], trailer_zero)` | b4e2b48910d03ad2 | e1fc11a6f3ee5187 | 8f277318852ae2a3 |
| V5 `build_variant(all gz, trailer_random_factory())` | 207290531d72261d | 239dcf276a9fd09b | 0900b351b6e02fe6 |
| V6 `build_variant([], trailer_zero, partition_streams=parts)` | da537172f8f90fbd | 6ff3f7650b21ba96 | 91edf1ee551a8f7e |
| V7 `build_variant(all gz, trailer_zero, partition_streams=parts)` | ae78fe9b7e3ec3ff | b934ba81cb30683c | 81e1d3e2d01b12be |
| V8 `zero_full_trailers_only(["Global/Latest", "Formats/Latest"])` | ee899d8444d5be29 | 1af57818b194071b | d4a0cf5ce6ee1690 |
| V9 `corrupt_trailer_bytes("Global/Latest", 0, 1)` | c709ad20174b6407 | 971eda8995218bfd | d1a7b45ee0360a16 |
| V9b `corrupt_trailer_bytes("Formats/Latest", 1, 3)` | d4074ec9dccb89df | 8033fe665294b136 | 9d9ebb1f0de48e35 |
| V10 `regzip_streams_variant(["Global/History"], keep_tail_bytes=128)` | 696a58fd63b3f545 | 7d672ad620b6bc25 | df8dd2ae68c858e6 |
| V11 `regzip_streams_variant(["Global/History"], keep_tail_bytes=0)` | 9677873f6e9b86d8 | bd8e7e975a6bcb57 | a16819dc61778b6c |
| V12 `build_variant([])` then `corrupt_trailer_bytes(p, p, "Global/Latest", 0, 2)` in place | a06fa543863a21b2 | 6061b0a750742b8a | d0241ca69541b954 |

- `git grep -n "read_entries" -- src/rvt/writer.py`: before **5** (the import + lines 250, 269, 292, 322) → after **0**;
  `write_cfb` / `dataclasses` in `writer.py`: 5 / 5 → 0 / 0. `write_cfb(` occurrences over `src/rvt` (defs, docs, calls): 25 → 21.
- Gate suites, `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_cfb_rewrite_entries.py tests/test_conftest_scaffolding.py
  tests/test_partition_header_verdict.py tests/test_ecc_final_block.py tests/test_gates_shared_walk.py tests/test_roundtrip.py -q
  -rs -p no:cacheprovider` (of the issue's globs only `tests/test_roundtrip.py` exists — no `test_writer*`, no other `test_cfb*`):
  origin/main `6fd74ee` (worktree, new file absent) **90 passed, 12 skipped** → branch **100 passed, 12 skipped** (= main + the
  10 new rows; the 12 skips are `test_roundtrip.py`'s absent samples / `RVT_SKIP_LARGE` / no `compoundfiles`, identical).
- Whole merged shard, sequential, same VM (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3
  tools/dev/shard_list.py --print)`): branch **2214 passed, 134 skipped, 3 xfailed, 3 warnings** in 345 s — the shard now includes the new file's 10 rows, so main `6fd74ee` is expected at 2204 passed with the same skips/xfails (a worktree run of main was started after this line was written; the PR thread carries its measured figure).
- `/verify` (RAN): `python -m rvt.roundtrip plugin/assets/genesis/<pin>.rvt out/verify/rt_<pin>.rvt --verify --byte-report` on
  all three pins → `VERIFY: OK` + `byte-identical: YES` ×3; `tools/rvt_validate.py` on the variant outputs, old loop vs new
  API side by side → identical verdict lines per pair (V10 / V8 / V1: the ECC-damage **errors these damage probes exist to
  produce** — "a zeroed/foreign trailer looks exactly like this" — V9: the 8-parity-bit trailer *warning*, exit 0; V7 2024: the
  known non-CRCIO final block error), i.e. the fold changed what no probe does; `writer.verify_readback` on V10 / V1 / V7 →
  `crc_failures: 0`; bare-unzip surface `tools/surface_bench.py --zip tekton-plugin.zip --json out/verify/bench.json` (42 s wall) → `local` 9/9 PASS (`go author` prompt 1.5 s / 6 panels 3.3 s / ifc 6.1 s READY, `go edit` structural PASS + validation PASS 0 errors), `cowork` / `codeexec` 7 PASS + the same 2 BLOCKED each (the IFC route's stated numpy prerequisite on the simulated no-numpy surfaces — pre-existing, untouched by this diff).
- `tools/sync_plugin.py` → rebuilt, deny-audit clean, identity scan == allowlist; `--check` → `plugin in sync with source`;
  `plugin/scripts/validate_plugin.py` → `RESULT: PASS`; `tools/dev/check_portable_paths.py` → `ok: 3017 tracked paths`.
- pyflakes: `writer.py`, the new test, `conftest.py` clean; `roundtrip.py` reports only the two names already unused on main
  (`sys`, the `clsid_to_str` re-export) — `Iterable` left with the import line this change rewrote anyway.

### Measured candidates NOT folded (territory) → #646

`git grep -n "write_cfb(\|read_entries("` over `src/rvt/` minus the two container modules: 15 modules. **Exactly
`rewrite_entries(src, out, new_streams)`** (precomputed `{path: bytes}`, everything else verbatim, every key just read from the
same container): `commit.py:217-220`, `manipulate.py:1588-1591`, `reduce.py:287-290`, `reduce_v2.py:406-409`,
`famload.py:1304-1309`, `famgen/loader.py:1945-1947`, `families.py:709-712`, `mep/conduit.py:1589-1592`,
`mep/electrical_data.py:1703-1706` — three lines each. **Plus a replaced-exactly-once check:** `adocument.py:700-711` (the API's
`KeyError` covers zero; twice cannot happen). **In place on one stream:** `convert/modify_family.py:534-539`. The one semantic
difference to state per site: today a key that is not a stream of the source is silently not written; under the API it is a
`KeyError`. `reduce*.py`'s outputs are gated by `assert_edit_free` in the genesis lanes (`y2024_b.py` / `y2025_b.py`, rule 5) —
the pass changes no byte, but the fold's sha table must include those lanes. **Not this shape, leave:** `famgen/famdoc_adoc.py:1832`,
`famgen/skeleton.py:3185`, `convert/rfa_assemble.py:175` (entry lists built from scratch), `famgen/geometry.py:2940-3022`
(donor-lineage dev path), `regadd.py:368/604` (holds `self.entries` across many edits; a fold re-reads the file). Searched first
(`search_issues`: only #640 itself); filed **#646** — task-shaped, Refs #640, P2 · area:engine · M.

### /simplify pass (four independent angles) — taken / not taken

Taken: **altitude / simplification** — `replace` accepts `bytes` values and `writer._swap_in` (the constant-lambda adaptor)
is deleted (above, 1·third bullet); `build_variant`'s docstring carries the ordering law the adaptor's docstring used to;
`Union[str, "os.PathLike[str]"]` ×2 → `str | os.PathLike[str]` (3.11 floor), `Union` import gone. **Reuse / simplification** —
`test_conftest_rewrite_streams_is_the_engine_pass` deleted (with `rewrite_streams` a plain call of the API it compared a
function with itself; the scaffolding file's two rows are the delegation's tests) and the second "returns `str`" assert dropped.
Not taken: hoisting the new test's `_streams(path)` / `pin` fixture — verbatim twins of `tests/test_conftest_scaffolding.py:127-136`
— into `conftest.py` (right call, wrong PR: this issue's territory is `rewrite_streams`' *body* and explicitly not the scaffolding
file; two 4-line helpers, noted for #639's classification pass rather than an issue of their own); `verify_pair` instead of the
test's `_directory()` (it also fails on the edited stream's digest, so it cannot express "everything but this stream").
**Efficiency** — nothing to fix: per builder the fold is a wash or cheaper (`zero_full_trailers_only` / `corrupt_trailer_bytes`
lose an `open_rvt` + a duplicate read of the touched stream; the other two do the same opens in a different order; `flip`
captures three ints and a str, for the call's duration).

### Findings / limits, stated

- Error type on a *missing* stream changed for the two builders that lost their `open_rvt` pass: they used to surface olefile's
  `OSError` from `doc.raw(missing)`; they now raise the API's `KeyError` (what `build_variant` already raised). No documented use
  passes a missing name; the new test pins the `KeyError`.
- The sha table and the validator lines are instruments on pins, not Autodesk's reader (rule 4): they prove the fold changed no
  byte of what these dev probes emit and certify nothing; nothing here claims a file loads.

BRANCH STATE (cam/640-rewrite-entries): `src/rvt/roundtrip.py` (+`rewrite_entries`, `StreamEdit`, module-docstring clause,
`dataclasses` / typing imports), `src/rvt/writer.py` (four folds, `_zero_full_trailers`, `build_variant` docstring, imports),
`plugin/lib/src/rvt/{roundtrip,writer}.py` (sync mirrors), `tests/conftest.py` (`rewrite_streams` body → delegation + one
docstring clause), `tests/test_cfb_rewrite_entries.py` (new), `tests/ci_shard.d/640-cfb-rewrite-entries.txt` (new), this
section. No hot file; nothing staged for the viewer; no certification claim; `tekton-plugin.zip` regenerated locally, not
committed; follow-up #646 filed.
