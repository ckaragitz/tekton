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
