# ci_fresh: `FRESH(disjoint drift)` — a merge-time judge for code drift that provably cannot meet the PR (#539)

Stream record of engineer session eng #539 (session `session_01SAGYNTERz4vwLy5LfaXUbH`, wave 27, branch
`cam/539-ci-fresh-disjoint-drift`). Territory: `tools/dev/ci_fresh.sh` (the code-drift branch + header), NEW
`tools/dev/ci_fresh_drift.py` (the judge, a new module in the same territory), `tests/test_ci_fresh.py`, one sentence in
`docs/process/AUTONOMY.md` §12c, one clause in `.github/prompts/tick.md` §2, this record. Not touched: `session_ci.sh`
(its JSON already records `main` and `head`; the PR's file list comes from git), `tests/conftest.py` (used as is).

**Scope note (why the diff is not the issue body's DONE verbatim).** #539's body asks for `git merge-tree --write-tree`
to supply the post-merge name set of the docs-ADD branch. The tech-lead brief for this wave re-scoped the issue to the
*successor rule* — tolerate unrelated CODE drift — which needs the same primitive and more; the re-scope is recorded on
the issue (🔒 comment). What the body wanted is present where the new path needs it (a non-clean merge-tree → STALE
naming the paths; git < 2.38 → cannot judge; the merged tree's full name list is run through
`check_portable_paths.check()`); the docs-ADD branch keeps its #522 approximation untouched (the brief: "keep the existing
docs-only rule"). Folding that branch into the judge is follow-up F1 below.

## Why

`ci_fresh.sh` judged a stored sandboxed-CI verdict FRESH only while `origin/main` was the commit the run merged with,
or had drifted by tolerated docs. Every unrelated *code* merge therefore cost every open PR a ~7-minute `session_ci.sh`
re-run before it could be merged, even when the PR's files and the drifted files were disjoint and the merge was clean —
merges serialise behind CI runs (#487), so on a busy afternoon the queue was mostly re-runs.

## What "cannot meet" means here — and what it does not

The merged tree is `NOW + the PR's change`; the run tested `WAS + the PR's change`; `NOW` went through the same gate
when it landed. A shard test changes colour only if what it executes or reads meets BOTH changes at once. The docs-only
rule proves that cannot happen (docs are inert except the SHARD_READS files, and the runtime audit #523 keeps that list
true). **No static rule can prove it for code**: in this repo almost every test's execution cone runs through
`rvt.frontdoor` or the plugin bootstrap, so "some test executes both changes" is nearly always true; whether they
*interact* is semantics. So `FRESH(disjoint drift)` is a calibrated bet, not a proof: it refuses every coupling a cheap
static reading can SEE (below), fails closed on every doubt, and leaves exactly one class unjudged, stated in the judge's
header and here: **coupling through an unchanged third file** (main changes `rvt.x`; the PR changes a caller of `rvt.y`;
`rvt.y` uses `rvt.x`) and names assembled at run time inside files neither side changed. Concrete instance from today's
replay: #563 (`release_ctx.py`) after #565 (`tools/surface_bench.py` + its tests) reads FRESH(disjoint drift);
`surface_bench` drives `go author` in a subprocess, which executes `release_ctx` — no import, no name links them, only
behaviour. It was in fact safe (565 reclassified a prerequisite message), but the judge cannot know that; it bets.
The tech lead can refuse the bet wholesale without a code change: `CI_FRESH_STRICT=1` in the environment makes code
drift STALE exactly as before.

## What was built

`tools/dev/ci_fresh_drift.py` (stdlib, ~320 lines incl. a 50-line header that states the rules once), run by
`ci_fresh.sh` as `python3 -IB "$REPO/tools/dev/ci_fresh_drift.py" WAS NOW HEAD PR SHARD_READS` only on the code-drift
branch (the awk `BLOCK` list non-empty) and never when `CI_FRESH_STRICT` is set. Division of labour after /simplify:
the judge prints ONE payload line and exits 0/4/2; the shell owns the one envelope (`FRESH(disjoint drift) was=… now=…
<payload>` / `STALE was=… now=… changed=<name3> (<payload>) -> re-run …` / `cannot judge PR n: <payload> (was=… now=…
changed=…)`) and treats anything else — a traceback (rc 1), an empty payload, a killed interpreter — as `cannot judge …
the disjoint-drift judge failed (rc=N; …)`, exit 2. The only code the judge executes besides git plumbing is this
checkout's `check_portable_paths.py` and `shard_list.py`, loaded by path from its own directory (`-I`: never through
`sys.path`) — the drop-in law (`DROPIN_DIR`, `DROPIN_NAME`, `parse()`) therefore has one home, not a copy. Rules, in
the order they are checked (the first that fails is the STALE reason printed inside the parenthesis):

1. **Shape.** `HEAD` is a commit in this clone; `WAS` is an ancestor of `NOW`; `HEAD` has exactly one merge base with
   `NOW`, itself an ancestor of `WAS` (a head rebased past the run, or a trunk that is not a descendant of the recorded
   main, is not argued about — drive 3's first attempt below shows the latter firing).
2. **Names.** Both change sets — main: `WAS..NOW`; PR: `merge-base..HEAD`; `git diff --name-status --no-renames -z`,
   so a rename is a D plus an A and both names count — hold only plain names (`[A-Za-z0-9_./+-]`), only `A`/`M` entries
   (any **deletion, rename or type change on either side is STALE**: a vanished path can be reached through a name
   computed at run time, `load_tool("genesis_%d" % year)`), and at most **200 paths a side**.
3. **Gates.** Neither side touches: the shard machinery (`tests/conftest.py` — and any `conftest.py`, `pytest.ini`,
   `tox.ini`, `setup.cfg`, `setup.py`, `sitecustomize.py`, `usercustomize.py`, `*.pth`, `tests/__init__.py` wherever they
   lie — `tests/ci_shard.txt`, `tools/dev/shard_list.py`, `session_ci.sh`, `ci_fresh.sh`, the judge itself,
   `check_portable_paths.py`, `pyproject.toml`, `scripts/cloud-setup.sh`); the whole-tree checkers `session_ci.sh` runs
   and their law data (`tools/sync_plugin.py`, `tools/plugin_identity_allowlist.json`, `plugin/scripts/validate_plugin.py`,
   `tests/test_plugin_sync.py`, `test_plugin_validate.py`, `test_ci_fresh.py`, `test_shard_list.py`,
   `test_portable_paths.py`); the pinned assets and manifests (`plugin/assets/`, `src/rvt/frontdoor/assets/` + mirror,
   `plugin/.claude-plugin/`); a SHARD_READS doc (the ERE is handed in from `ci_fresh.sh`'s one line, still the single
   source `tests/conftest.py` lifts). A shard drop-in `tests/ci_shard.d/<n>.txt` is NOT a gate — every engine PR carries
   one, so treating it as one would make the rule dead on arrival — but it passes only when **every test it enrols is
   itself changed on the same side** (enrolling an unchanged, pre-existing test into the shard is precisely a test the
   other side's change never ran under); anything else in that directory (README) is a gate. The gate list is a hand
   list and a stale entry would fail *open*, so `tests/test_ci_fresh.py` pins that every entry is a tracked path, that
   every file `session_ci.sh` executes (its `$REPO/tools/…` helpers and each `step <name> "$PY" <path>`) is in it, and
   that the judge holds no private copy of the drop-in law.
4. **Disjoint.** Added/modified docs outside SHARD_READS are set aside on both sides (inert — the docs-only rule's
   ground); every remaining path changed on both sides → STALE naming it.
5. **Uncoupled, both directions**, on file TEXT read from git blobs with one `git cat-file --batch` per side (data:
   regex over lines; nothing imported, nothing executed): (a) import lines of every changed `.py` — absolute and
   **relative** (`from . import x`, `from ..mutate import y`, resolved against the file's own dotted name; 260+ such lines
   in `src/rvt`), `import a.b as c, d`, `from X import a, b` (an item that is a module file of either tree names `X.a`;
   anything else — a re-exported attribute, `*`, a `(` list continued on later lines — names the package `X` itself, so
   façade re-exports through `__init__` are covered) — against the other side's changed modules by **import-chain
   relation** (equal, or one a package prefix of the other: importing `rvt.frontdoor.manifest` is coupled to a changed
   `src/rvt/frontdoor/__init__.py` and `src/rvt/__init__.py` too); (b) **names**: the other side's repo-relative path,
   basename, dotted module name and — for `tools/`, `tests/`, `scripts/` and root files, which are loaded by bare name
   (`load_tool("x")`, `python tools/x.py`, `-m x`) — the stem, each as a whole token anywhere in the text (this is what
   caught #581-old naming `rvt_selfcheck.py` in its test while #577 changed it); (c) **names built at run time**: a loader
   call (`import_module`, `__import__`, `load_tool`, `spec_from_file_location`, `runpy`) whose first argument is neither
   a plain literal nor a plain variable reaches *everything* the other side changed, unless the template is written in the
   call (`import_module(f"rvt.mep.{mod}")` → reaches what `rvt.mep.` begins); a templated literal anywhere in the file
   that looks like a module/path (`rvt.…`, `….py`, `tools/…`, `tests/…`, `test_…`, `genesis_…`, no blanks — a message
   such as `f"tools/x.py not found at {p}"` is not one) reaches every changed path, module or stem its literal prefix
   begins (`f"rvt.genesis.port{year}"` in `release_ctx.py` couples it to `rvt.genesis.port*`, not to the world — the
   first draft's "coupled to everything" turned 11 % of the repo's `.py` files into permanent STALE, measured: 43/400;
   the prefix form flags 16, all genuine builders). Lines that do not parse as an import statement are prose (docstring
   lines starting "from the file import spells it…" exist in `estorage.py`) and name nothing — real code with such a
   line would not have compiled under the run being judged.
6. **Clean.** `git merge-tree --write-tree --name-only --no-messages NOW HEAD` — the merge in the object store, no
   checkout, no worktree (git ≥ 2.38; the VM has 2.43; older git answers usage/129 → `cannot judge …  needs git >= 2.38`)
   — exits 0, and the merged tree's full `ls-tree` name list passes this checkout's `check_portable_paths.check()`
   (git merges `src/NEW.py` and `src/new.py` without a word; the checker does not).

Every git call other than the two that answer through exit 1 (`merge-base --is-ancestor`, `merge-tree`) turns a non-zero
exit into `cannot judge` (exit 2); a non-blob object where a file text is expected (a submodule entry) likewise.

## Evidence

**Tests** — `tests/test_ci_fresh.py` 23 → 52 collected (50 passed / 2 skipped here: gawk, busybox absent). Pre-existing
rows: every verdict and exit code unchanged; the seven rows whose scenario IS code drift (the code-drift row, the four
SHARD_READS/deletion rows, the blank-name row, the awk row's second half) now assert through `stale_reason()` — same
`STALE was=… now=… changed=…` frame, exit 4, plus the parenthesised reason the judge gives (the docs-ADD rows already
carried one); this is the one deliberate deviation from "rows byte-identical", made so a declined tolerance says *why*.
New rows (each was red against `main`'s helper — `cannot judge`/old STALE line — and is green now): disjoint uncoupled
clean drift incl. a drop-in enrolling its own new test → `FRESH(disjoint drift) … main=4 pr=1`; same path both sides;
nine coupling shapes (absolute import, reverse direction, relative import, `from . import mod`, façade import, bare-name
load, loader on an expression, `%`-template reaching its prefix, f-string template in the call); six gate shapes on
either side (conftest, ci_shard.txt, session_ci.sh, README in ci_shard.d, the ledger on the PR side, a drop-in
enrolling an unchanged test); rename on main and rename on the PR (both names in `changed=`, deletion half → STALE);
merge conflicts between disjoint sets (file vs directory) and between docs set aside as inert (same doc both sides);
case-twin across the two sides caught by the checker over the merged tree; > 200 paths → not judged; head rebased past
the recorded main; head absent from the clone; `CI_FRESH_STRICT`; a template that cannot reach stays FRESH; three
fail-closed rows through one PATH-shim helper (the judge's interpreter dying → `cannot judge … failed (rc=1; …)`; git
without `--write-tree`, usage exit 129 → `cannot judge …  needs git >= 2.38 …`; any other git failure under the judge,
`merge-base` exit 128 → `cannot judge …`), all exit 2 with the reason on the one line; the trusted-side pin extended to
the judge (same verb deny-list as the helper plus `sys.path`; the only code it loads is `trusted("check_portable_paths")`
and `trusted("shard_list")` by path); and the gates meta-test above.

**Driven for real (/verify)** — a scratch clone of this checkout with the four working-tree tools copied in, real PR
heads fetched (`refs/pull/<n>/head`, and #581's pre-rebase head `06b34cc` by full SHA), hand-written run JSONs of
`session_ci.sh`'s shape under `.git/session-ci/ci/`, and this checkout's local `main` moved to the historical trunk
commit so the script's own `git fetch origin main` sees "main as it was then":

```
--- PR 571 (CI'd against 37aa9c4) while origin/main = 4bd7ecf (#572 + #568 landed since)
STALE was=37aa9c47… now=4bd7ecff… changed=plugin/lib/src/rvt/frontdoor/manifest.py,plugin/skills/tekton-native/scripts/rvt_inspect.py,src/rvt/frontdoor/manifest.py,… (main changes tools/sync_plugin.py, a gate: shard machinery, a whole-tree checker or its law data) -> re-run tools/dev/session_ci.sh 571
exit=4
--- PR 578 (CI'd against 4bd7ecf) while origin/main = 59c8d0a (#571 landed since)
FRESH(disjoint drift) was=4bd7ecff… now=59c8d0a5… main=3 pr=3 (disjoint from the 3 non-docs paths PR 578 changes: not imported or named either way, no gate touched, merge clean)
exit=0
--- same, CI_FRESH_STRICT=1
STALE was=4bd7ecff… now=59c8d0a5… changed=tests/test_surface_bench_reason.py,tests/test_surface_perf.py,tools/surface_bench.py (CI_FRESH_STRICT is set: code drift is never judged, only re-run) -> re-run tools/dev/session_ci.sh 578
exit=4
--- same, expected head = another PR's
WRONG-HEAD json=4896e31c… now=a9c9f770… (the stored run is for another head: run tools/dev/session_ci.sh 578)
exit=5
--- PR 581's pre-rebase head 06b34cc (CI'd against 9fc890c) while origin/main = 6084e78 (#577 landed since)
STALE was=9fc890c7… now=6084e784… changed=plugin/lib/src/rvt/native_framing.py,plugin/skills/tekton-native/scripts/rvt_inspect.py,plugin/skills/tekton-native/scripts/rvt_selfcheck.py,… (PR 581's tests/test_rvt_edit_refusal.py names plugin/skills/tekton-native/scripts/rvt_selfcheck.py, changed on main) -> re-run tools/dev/session_ci.sh 581
exit=4
    git merge-tree --write-tree --name-only origin/main 06b34cc: docs/inbox/edit-text-own-release.md, exit 1   (the record conflict the tech lead hit; the judge stops one rule earlier)
--- (operator slip kept as evidence) the same 581 drive with origin/main accidentally left at 59c8d0a, OLDER than the recorded main:
STALE … (the recorded main is not an ancestor of origin/main (trunk rewritten)) …  exit=4   — rule 1 fails closed
```
(SHAs shortened here only; the tool prints them in full.)

**Replay on today's history** (real refs: `git fetch origin "+refs/pull/<n>/head:refs/pr/<n>"`; for each PR,
`WAS` = its merge base, `NOW` = the first-parent `main` commit just before its own squash — i.e. the drift it was
actually re-run for; the judge invoked directly with those SHAs, since the run JSONs are gone):

| PR | drift it met | verdict | reason |
|---|---|---|---|
| #578 | #571 | **FRESH(disjoint drift)** main=3 pr=3 | — |
| #563 | #565 | **FRESH(disjoint drift)** main=2 pr=8 | — (the bet's exposed flank, see above) |
| #568 | #570 + #572 | STALE | main changes `tools/sync_plugin.py` (#572 made `rvt_inspect` a generated mirror — a whole-tree law) |
| #571 | #572 + #568 | STALE | same |
| #572 | #570 | STALE | PR changes `tools/sync_plugin.py` |
| #543 | 1 commit | STALE | main changes `tools/sync_plugin.py` |
| #549, #556 | … | STALE | main changes `tests/conftest.py` (#558) |
| #558 | … | STALE | PR changes `tests/conftest.py` |
| #550 | … | STALE | `tekton_env.py` does `import rvt` — on one import chain with main's `rvt.famgen.geometry` |
| #554 | … | STALE | `release_ctx.py` imports `rvt.famgen.skeleton`, changed on main |
| #541 | … | STALE | PR changes `docs/process/AUTONOMY.md` (SHARD_READS) |
| #581 (pre-rebase head `06b34cc`, fetched by SHA) | #577 | STALE | its test names `rvt_selfcheck.py`, changed by #577 — and `git merge-tree` of the pair exits 1 on `docs/inbox/edit-text-own-release.md`, the record conflict the tech lead hit |

So on today's traffic the rule would have saved 2 of 12 re-runs; the rest were STALE for reasons a human would also
call real (a mirror-generator change, conftest churn, direct imports). The yield is whatever fraction of a day's merges
are process/tests/tools-local; the safety argument does not depend on it.

**Cost.** Full FRESH path (3 merge-base, 2 diff, 2 cat-file --batch, 2 ls-tree, merge-tree, ls-tree of the merged
tree + `check()` over ~3 000 names): 101–109 ms on #563/#578; 49 ms to a STALE on #541's 121-file drift; merge-tree
alone 8 ms. Against a 7-minute re-run.

**Gates run** — see BRANCH STATE.

## Findings

- The brief's condition (3) listed `tests/ci_shard.d/**` as machinery. Taken literally the rule never fires (every
  engine PR adds a drop-in; so does most drift). The hazard a drop-in carries is specific — it can enrol a pre-existing
  test that never ran with the other side's change — and is checked exactly (rule 3); a drop-in that enrols only its own
  side's changed tests is data. Flip it back to a gate in one line (`GATES`) if the tech lead disagrees.
- "No false FRESH, ever" is attainable for docs drift and unattainable for code drift by any static rule short of
  executing the shard; the record says so rather than implying otherwise, and `CI_FRESH_STRICT` exists for the day the
  bet is not wanted.
- `git merge-tree --name-only` names a file-vs-directory conflict as the parked path (`lib~<oid>`), not `lib`; the
  reason relays git's names verbatim.

## /simplify pass (four angles) — what changed after the first green

Applied: the judge prints a payload and the shell owns the one envelope (was: two owners of the line format plus a
`CHANGED3` argv slot echoed back and a `case "$RC:$LINE"` string sniff); the head-present check moved into the judge's
rule 1 (was pasted twice in bash); `shard_list.py` loaded by path instead of a copied `DROPIN_NAME` + a re-spelled
`parse()`; `check_portable_paths.py` resolved from the judge's own directory instead of argv; the gate/SHARD_READS check
and the docs set-aside folded into `changed()`; `except Exception` → `cannot judge: <Type>: <msg>` (an unlisted exception
used to lose its reason to a bare rc=1); one `few()` for the three "name the first, count the rest" sites; one
`import_items()` for the two import-list parses; a `Side` tuple instead of five positional arguments; the needle scan
made linear (one alternation regex per direction, the per-target pass only for a file that hits — the efficiency reviewer
measured 26 s per direction at 200 × 200 large files for the quadratic form, ~0.8 s after); tests: `fresh_disjoint()`
and `shim_path()` helpers, the reason strings inline in the parametrize tables, spelling-level source asserts replaced by
a third shim row, the gates meta-test added (the one fail-open seam the altitude reviewer found).
Skipped, with reason: folding the docs-ADD heredoc into the judge (F1 — would touch the byte-identical docs-only rows;
follow-up sized); `CI_FRESH_STRICT` defaulting from `.github/autonomy.json` (outside territory; the STALE line already
says when it fired, and tick.md names the switch); one `ROOTS` table behind `TEMPLATED`/`PY_ROOTS`/`BY_STEM` (low value,
regex readability cost).

## Follow-ups (searched: none filed)

- F1 — fold the docs-ADD collision heredoc of `ci_fresh.sh` into the judge as a second entry point (one loader, one
  place that runs `check()` over a name set, one findings format). Keep its no-merge approximation there rather than
  `merge-tree` (git < 2.38 clones would otherwise regress from FRESH(docs-only) to cannot-judge) — or take the issue
  body's original bullet 1 and accept that floor. Kept out of this PR to leave the docs-only rows byte-identical.
- F2 — `sync_plugin.py` as a hard gate is today's dominant STALE; a finer rule ("the other side touches nothing under a
  mirrored root") is possible but needs the mirror map out of `sync_plugin.py` as data.
- F3 — `CI_FRESH_STRICT`'s default could live in `.github/autonomy.json` (`pipeline.judge_code_drift`) with the env var
  as the in-tick override, so the policy is visible in the ledger (S-2026-08-09-b).

BRANCH STATE
- branch: cam/539-ci-fresh-disjoint-drift (from origin/main 6ee6f27)
- files: tools/dev/ci_fresh_drift.py (new), tools/dev/ci_fresh.sh, tests/test_ci_fresh.py, docs/process/AUTONOMY.md
  (one sentence, §12c Merge row), .github/prompts/tick.md (one clause, §2), docs/inbox/ci-fresh-merge-tree.md (this)
- gates: `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_ci_fresh.py tests/test_shard_list.py
  tests/test_portable_paths.py tests/test_docs_read_audit.py -q -rs` → 85 passed / 3 skipped (gawk, busybox, the audit's
  self-test reader); + `tests/test_techlead.py` → 116 passed / 3 skipped for the five files; `python3
  tools/dev/check_portable_paths.py` → ok: 2981 tracked paths; `bash -n tools/dev/ci_fresh.sh` clean (no shellcheck on
  this VM); `tools/sync_plugin.py --check` in sync, `validate_plugin.py` PASS (tools/dev is not mirrored; run for the
  template); whole merged shard `pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)` on the rebased
  tree (origin/main fa797d4): 2034 passed / 134 skipped / 3 xfailed / **1 failed = the new gates meta-test, only because
  `tools/dev/ci_fresh_drift.py` was still untracked when that run read `git ls-files`**; staged and re-run: passes (a
  clean whole-shard count follows in the PR thread)
- staged vs shipped: nothing staged; no viewer batch; no plugin/src change
