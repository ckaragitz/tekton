# ci_fresh: `FRESH(disjoint drift)` — a merge-time judge for code drift that provably cannot meet the PR (#539) — PARKED

> **Outcome (2026-08-11): the judge is parked; only its default-path improvement shipped.** After three fix rounds a
> fourth adversarial pass still found false FRESH under `CI_FRESH_JUDGE=1`, and per the tech lead's ruling the PR was
> descoped: `tools/dev/ci_fresh_drift.py`, its rig rows, the `CI_FRESH_JUDGE`/timeout plumbing and the opt-in doc
> clauses were removed on the branch; what merged is the rewritten-trunk check on every path of `ci_fresh.sh` (a recorded
> `main` that `origin/main` no longer descends from is STALE / cannot judge) with its two rows, one sentence in AUTONOMY
> §12c / tick.md §2 pointing here, and this record — kept whole because it says where static judging stops. The judge's
> code lives in this branch's history (`cam/539-ci-fresh-disjoint-drift`, PR #590 commits up to `fe25c59`); the classes
> that still defeated it are listed verbatim in "Parked" at the end; the follow-up issue is #610.

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
**Since the review of `545e3da` the bet is OPT-IN, not opt-out** (ruling below): the standing gate keeps its pre-#539
guarantee — code drift is STALE, byte-identical line — and only a tech lead who exports `CI_FRESH_JUDGE=1`, deliberately,
on a queue-heavy tick, hands code drift to the judge. Why default-off is the right shape *for now*, in one sentence: the
exact alternative — refuse whenever the two changes share one test's import cone — was measured by the reviewer and
degenerates to "always STALE" because `tests/conftest.py` imports `rvt.frontdoor` at start-up (every shard cone ≈ 170
files); it becomes viable the day a runtime import/read audit supplies real per-test cones, and until then a heuristic
that bets belongs behind a switch the merger flips knowingly. (An earlier draft had the inverse switch,
`CI_FRESH_STRICT=1`; every mention of it below is history.)

## What was built

`tools/dev/ci_fresh_drift.py` (stdlib, ~320 lines incl. a 50-line header that states the rules once), run by
`ci_fresh.sh` as `python3 -IB "$REPO/tools/dev/ci_fresh_drift.py" WAS NOW HEAD PR SHARD_READS` only on the code-drift
branch (the awk `BLOCK` list non-empty) and — since the fix round — only when `CI_FRESH_JUDGE=1` is exported, under
`timeout ${CI_FRESH_JUDGE_TIMEOUT:-120}`. Division of labour after /simplify:
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

## Fix round 1 — review of `545e3da` (🛑, an adversarial reviewer with its own rigs), same session

**Ruling adopted (reviewer's option C): the judge ships default-OFF.** `ci_fresh.sh` answers code drift with the
pre-#539 line, byte-identical (`STALE was=… now=… changed=… -> re-run …`, exit 4) unless `CI_FRESH_JUDGE=1` — exactly
`1` — is in the environment; `CI_FRESH_STRICT` is gone; AUTONOMY §12c and tick.md §2 now say "opt-in, taken deliberately
by the tech lead on queue-heavy ticks; the standing gate keeps its pre-#539 guarantee". The seven pre-existing rows the
first round had moved onto `stale_reason()` are back to asserting the byte-identical line (helper `stale()`), each with
the opted-in reason pinned next to it. Then the eight findings, each a real false FRESH or an unbounded cost inside the
rule's own claims, each now a red→green rig row:

1. **Imports are read with `ast`** over the whole blob (data; nothing compiled to run): every `Import`/`ImportFrom`
   wherever it sits — backslash-continued lists (`from pkg import high, \⏎ low` was FRESH: c3), `;` chains and inline
   suites (`import os; from b import B`, `if x: from pkg import low` — c4 — survived only through the name backstop),
   function-level imports; relative levels resolved from `node.level`. A file that does not parse
   (SyntaxError/ValueError/RecursionError/MemoryError) is STALE. The line regex stays as a backstop, united with it.
2. **"Builds names at run time" became "builds OR DISCOVERS"**: `glob/iglob/rglob/listdir/scandir/walk/iterdir` calls,
   `spec_from_file_location`'s PATH (2nd) argument, and every loader call whose deciding argument is not a plain string
   literal — *including a plain variable*, whose exemption the first draft justified with "its literal is in the caller"
   (true only when the caller is a changed file; finding 7) — reach EVERYTHING the other side changed; narrowed only when
   the call spells a literal repo prefix itself: leading literal pieces that start at a tracked top-level directory of
   either tree (`os.path.join(ROOT, "tools", "gen_*.py")` → `tools/gen_`, a glob counting up to its first wildcard;
   `spec_from_file_location("m", os.path.join(ROOT, "tools", "t.py"))` → `tools/t.py`, the NAME argument skipped) or
   in the `rvt.` namespace (`import_module(f"rvt.mep.{mod}")` → `rvt.mep.`). A piece from the middle of a join
   (`base, "gen", name`) proves nothing about where the walk starts and narrows nothing. Templated literals elsewhere in
   the file follow the same prefix law (`"genesis_%d"` and `f"{tool}.py"` now reach everything; `f"rvt.genesis.port{y}"`
   still only `rvt.genesis.port*`). Stated in the header as unjudged: plain concatenation / `os.path.join` pieces with
   no loader or walk call in the changed file. Rows j3 (`for f in os.listdir(TOOLS): n = f[:-3]; load_tool(n)`), j4
   (glob + subprocess, narrowed to `tools/gen_…`), j5 (spec path variable; spec path from literal pieces).
3. **Modes are read** (`git diff --raw -z`): an entry whose new (or, for M, old) mode is not 100644/100755 — a symlink
   120000, a gitlink 160000 — is STALE on either side (m12: a symlinked test importing main's module was judged by its
   target string).
4. **Runner files at any depth**: `pyproject.toml` joined `RUNNER_FILES` (a nested pytest inifile `tests/pyproject.toml`
   was FRESH: e4) and any `__init__.py` under `tests/` is a gate (e5), not only `tests/__init__.py`.
5. **Bounded**: `timeout ${CI_FRESH_JUDGE_TIMEOUT:-120}` around the judge in `ci_fresh.sh` (124, or 127 without
   coreutils, lands in "the disjoint-drift judge failed (rc=…)", exit 2 — k-timeout row with a sleeping python3 shim
   and a 1 s budget); a 2 MB cap per changed blob (`BLOB_LIMIT`, m2 row); and the templated-literal scan is now
   quote-to-quote with a bounded body (`[^'"\s]{2,240}`) checked in two cheap steps instead of one backtracking
   pattern — the reviewer's ~800 KB quote-less `%s%s…` line that hung ~1 h now costs 0.09 s (2 MB of prose 0.17 s,
   1.4 MB of short literals 0.22 s; `ast` on 2 MB ≈ 0.02–2 s).
6. **The recorded head must be a 40-hex id** in the judge (as the docs-ADD arm already demanded); so must `was`/`now`.
   `"head": "HEAD"` in a JSON was argued about — git resolves it — and is now STALE (h2).
7. Wording aligned everywhere (header rule 5, `ci_fresh.sh` header, AUTONOMY, tick): "loader and directory-walk calls
   on anything but plain literals reach everything".
8. **Adjacent pre-existing hole closed**: the docs-only arm never checked `WAS ⊑ NOW`; a rewritten trunk whose tree
   differed by a record read `FRESH(docs-only drift)`. One `git merge-base --is-ancestor` before `DRIFT`: rc 1 → `STALE
   … changed=? (<was> is not an ancestor of origin/main: main rewritten under the verdict)`, other rc → cannot judge
   (row: `commit --amend` of the upstream root adding only `docs/inbox/later.md`).

What held, per the reviewer, recorded for the next reader: exit table intact, ranges right, fail-closed on judge
failure, trusted side never executes PR content, GATES / drop-in / rename / conflict / rewritten-trunk rows correct,
replay reproduced.

**Evidence after the round.** `tests/test_ci_fresh.py` 52 → 65 collected (63 passed / 2 skipped: gawk, busybox);
stream-local five files 132 passed / 3 skipped; portable paths ok (2983); `bash -n` clean. Replay over the same 12 PRs
with the hardened judge: **1 FRESH (#578) / 11 STALE** — #563 flipped to STALE (`release_ctx.py`'s `import_module(name)`
on a plain variable now reaches everything main changed), which is the honest price of finding 7 and exactly the case
the honesty section above worried about. Timings unchanged (≈ 100 ms on the FRESH path). Drive of the real script in
the scratch clone (`origin` = a bare copy whose `main` is moved to the historical trunk; run JSON hand-written):

```
== PR 578, recorded main 4bd7ecff, origin/main now 59c8d0a
   standing gate:      STALE was=# now=# changed=tests/test_surface_bench_reason.py,tests/test_surface_perf.py,tools/surface_bench.py -> re-run tools/dev/session_ci.sh 578        exit=4
   CI_FRESH_JUDGE=1:   FRESH(disjoint drift) was=# now=# main=3 pr=3 (disjoint from the 3 non-docs paths PR 578 changes: not imported or named either way, no gate touched, merge clean)   exit=0
== PR 571, recorded main 37aa9c47, origin/main now 4bd7ecf
   standing gate:      STALE was=# now=# changed=plugin/lib/src/rvt/frontdoor/manifest.py,plugin/skills/tekton-native/scripts/rvt_inspect.py,src/rvt/frontdoor/manifest.py,… -> re-run tools/dev/session_ci.sh 571   exit=4
   CI_FRESH_JUDGE=1:   STALE was=# now=# changed=…same… (main changes tools/sync_plugin.py, a gate: shard machinery, a whole-tree checker or its law data) -> re-run tools/dev/session_ci.sh 571   exit=4
== wrong expected head:  WRONG-HEAD json=# now=# (the stored run is for another head: run tools/dev/session_ci.sh 578)   exit=5
== opt-in, judge stalls (CI_FRESH_JUDGE_TIMEOUT=0.01):  cannot judge PR 578: the disjoint-drift judge failed (rc=124; was=# now=# changed=tests/test_surface_bench_reason.py,tests/test_surface_perf.py,tools/surface_bench.py)   exit=2
== opt-in, "head": "HEAD" in the JSON:  STALE was=# now=# changed=…same… (the recorded head 'HEAD' is not a 40-hex commit id) -> re-run tools/dev/session_ci.sh 578   exit=4
```

## Fix round 2 — delta review of `cc6ae80` (default path confirmed exact; the opt-in judge still had holes), same session

The reviewer confirmed the standing gate byte-identical against `origin/main`'s script in the same rig, docs-only
unchanged, fixes 0/1/3/5/6/7/8 by code + rigs — and found four more false-FRESH shapes inside the OPT-IN judge (the
merger's own bar stays "no false FRESH"). All four fixed, each a red→green row under `CI_FRESH_JUDGE=1`; two nits taken:

- **F1 (blocking) — the piece run never crosses a gap.** Loader/walker calls are now read from the ast, not a text
  window: a call's name/path expression is flattened left to right into literal pieces and gaps (constants cut at a
  `%`/f-field, f-strings, `+` `/` `%` chains, the arguments of an inner `os.path.join(…)` / `Path(…)` after a gap for
  its callee, a walker's receiver first); leading gaps (ROOT, HERE, the callee) are skipped and the run ends at the FIRST
  gap or wildcard after it started. `glob(os.path.join(ROOT, "plugin", "skills", skill, "scripts", "*.py"))` now spells
  `plugin/skills` (reaches everything under it) instead of the fabricated `plugin/skills/scripts` that matched nothing;
  the wildcard control and `Path(ROOT, "plugin", "skills").rglob("*.py")` spell the same. Rows: both shapes vs main
  changing `plugin/skills/tekton-author/scripts/rvt_inspect.py`.
- **F2 (blocking) — pytest 9's other inifiles.** `pytest.toml`, `.pytest.toml`, `.pytest.ini` joined `RUNNER_FILES` (any
  depth; pytest reads them ahead of `pyproject.toml`); rows for all three next to e4.
- **F3 — a literal loader argument is an import.** `import_module("pkg")`, `__import__("pkg")`, `pytest.importorskip("pkg")`
  (new in LOADERS), `load_tool("dev/x")` (→ `dev.x`), `run_module("…")` with a plain literal now name that module in the
  import set, so `related()`'s façade/package logic applies (`import_module("pkg")` vs main's `src/pkg/low.py` behind an
  unchanged `pkg/__init__.py` was FRESH; the statement `import pkg` was already STALE). A literal
  `spec_from_file_location` PATH stays with the name scan. Rows: `import_module("pkg")`, `importorskip("pkg")`; the old
  `load_tool("t")` row now reads "imports t (tools/t.py)" and a new subprocess row keeps the name scan pinned.
- **F4 — discovery outside the list.** `pkgutil.iter_modules` / `walk_packages` and `os.fwalk` are walkers; a `git
  ls-files` / `ls-tree` token in a changed `.py` (this repo's own sweep idiom) is a walk with no literal start = reaches
  everything. Also, since the ast is now the reader: loaders/walkers reached through an alias (`from glob import glob as
  g`, `im = importlib.import_module`) are resolved to what they are; one fetched with `getattr(importlib,
  "import_module")`, or a callee token the text spells more often than the ast sees it called, reaches everything. The
  header's "unjudged, stated" paragraph now names what is left: names joined by plain concatenation/`os.path.join` and
  handed to `open()`/subprocess/exec with no loader or walk call in the changed file, and a loader smuggled past both the
  ast and the token backstop (exec of an encoded string — review, not this judge, is the boundary against a hostile PR).
  Rows: `iter_modules`, a `git ls-files` subprocess, an aliased `glob`, a `getattr` loader.
- Nits taken: F5 — the O(matches × 400) text window is gone with the ast reader (1.8 MB of real `router.py` × 20: parse
  1.2 s + builds 0.5 s; 750 KB of `glob(` is a SyntaxError → STALE in 0.00 s), and the templated-literal prefilter takes
  its directory names from the live tree (`tops`) instead of a hard-coded list; F6 — `git cat-file --batch-check` sizes
  every changed blob BEFORE `--batch` reads any, so a dump on either side is refused unread.

Evidence: `tests/test_ci_fresh.py` 65 → 77 collected (75 passed / 2 skipped); the five stream-local files 144 passed /
3 skipped; portable paths ok (2983); `bash -n` clean; replay unchanged (1 FRESH #578 / 11 STALE, same reasons).

## Fix round 3 (declared the last) — third adversarial pass on `ec53709`, same session

F1–F6 of round 2 confirmed by the reviewer's rigs; a third pass found one more layer under `CI_FRESH_JUDGE=1`. All
five items fixed, each with red→green rows; plus two shapes my own pass added (a dunder call, a loader named in a string):

1. **(blocking) Anchoring.** A literal run is anchored at the repo root only when PROVEN to start there: its only
   leading gap is a recognised root name (`ROOT`, `REPO_ROOT`, `repo_root()`, also as the head field of an f-string) —
   the flattener now emits distinct gaps for a root name, a callee slot and "unknown". A run that starts below anything
   else (`PLUGIN = join(ROOT, "plugin")`, `HERE`, `base`, a module receiver) is UN-anchored and matches at any directory
   boundary (`"/" + prefix in "/" + name`). `(PLUGIN, "skills", skill, "scripts", "*.py")` → `*/skills` reaches
   `plugin/skills/tekton-author/scripts/rvt_inspect.py`; `(PLUGIN / "skills").rglob` the same; `(base, "tools", "dev",
   name)` → `*/tools/dev` reaches `plugin/lib/tools/dev/x.py`; `(HERE, "tools", "*.json")` → `*/tools` reaches
   `tests/tools/x.json`; `(ROOT, "tools", …)` and `f"{ROOT}/tools/…"` stay anchored (`tools`, `tools/gen_`). Four rows.
2. **(blocking) Bare references.** After alias resolution, any `Name`/`Attribute` (Load) that resolves to a loader or
   walker and is not a call's `.func`, not the value of a simple alias assignment, and not a non-dunder attribute's
   receiver reaches everything: `map(importlib.import_module, NAMES)`, `ex.map(load_tool, …)`, `im: Callable = …`,
   `im, g = …, glob.glob`, `(im := …)`, `functools.partial(importlib.import_module)`, `importlib.import_module.__call__(…)`;
   `exec`/`eval`/`compile` of ANYTHING reaches everything (plain-string `exec("from pkg import low")` was FRESH); and a
   loader named in a string constant anywhere (`getattr(importlib, "import_module")`, `globals()[…]["__import__"]`)
   likewise. Nine rows.
3. `.gitattributes` / `.gitmodules` at any depth are runner files (an `eol=crlf` on main rewrites bytes tree-wide on the
   export session_ci runs); row on the main side.
4. The deciding argument of a by-name loader is picked by keyword NAME (`name`/`modname`/`mod_name`/`path_name`),
   never "the first keyword" (`importorskip(reason="x", modname=NAME)` took `"x"`); a relative literal
   (`import_module(".low", package="pkg")`) is no top-level module name and reaches everything. Two rows.
5. Stated AND fixed: `SourceFileLoader` / `SourcelessFileLoader` / `ExtensionFileLoader` join `spec_from_file_location`
   as by-PATH loaders (2nd argument / `path=`); unittest's `discover` is a walker and `loadTestsFromName(s)` a loader; a
   compiled module (`.so/.pyd/.pyc/.pyo/.dll/.dylib`) changed on either side is STALE outright ("judged by nobody").
   Rows: `SourceFileLoader("m", p)`, `discover(join(ROOT, "tests"))` reaching a main-added test, `src/fastmod.so`. The
   header's "unjudged, stated" paragraph was rewritten to claim no more than the code does: what remains is coupling
   through an unchanged third file; a path assembled by plain concatenation/`join` and handed to `open()` or a
   subprocess (`python tools/<name>.py`, `-m <name>`) with no loader, walk, exec or root-anchored template in the changed
   file; a loader or walker the list does not know by name (a third-party finder, a C extension's own dlopen); code
   reached through `sys.path`/`PYTHONPATH`/`.pth` manipulation at run time; references living in files neither side
   changed — and the standing sentence that a hostile PR can always hide a load from a static reader (review is that
   boundary).

Conservatism measured on the real tree after the round: of 405 `.py` files under `src/rvt`, `tests`, `tools`, 140 would
reach everything if changed, 23 spell a narrowed prefix, 242 build nothing, 0 unparsable — the judge still has room to
say FRESH, and every widening this round was toward STALE. Evidence: `tests/test_ci_fresh.py` 77 → 96 collected (94
passed / 2 skipped); five stream-local files 161 passed / 3 skipped; portable paths ok (2990); `bash -n` clean; replay
unchanged (1 FRESH #578 / 11 STALE).

## Parked — the fourth pass on `fe25c59`, and the descoping

The reviewer's fourth adversarial pass confirmed all 17 round-3 shapes STALE and the standing gate byte-identical, then
found one more root cause and three smaller classes of false FRESH under `CI_FRESH_JUDGE=1`. That was past the last
round the ruling allowed, so the judge is parked rather than patched again. **Remaining false-FRESH classes, verbatim,
for whoever picks this up** (each was reproduced on a rig by the reviewer):

- **Receiver dropping in `pieces()`.** On a `Call`, the flattener drops the METHOD RECEIVER and treats every callee
  slot as transparent, so ALL-LITERAL chains read as anchored-at-nothing or as narrower than they are:
  `Path("tests").joinpath("tools").glob("*.json")` vs main's `tests/tools/x.json` → FRESH; likewise
  `Path(__file__).parent.joinpath("tools").glob(...)`, `HERE.joinpath(...)`, `PLUGIN.joinpath("skills").glob("*/scripts/*.py")`,
  `LIB.joinpath("tools").rglob("*.py")`, `run_path(str(Path(ROOT).joinpath("plugin","lib").joinpath("tools","dev",name)))`,
  and zero-argument helpers `join(plugin_dir(), "skills", "*", "scripts", "*.py")` / `join(here(), …)` (a call with no
  arguments contributes only a callee slot, which un-anchors nothing). The fix direction is known — a receiver is a
  path prefix (flatten `func.value` for `joinpath`/`glob`/`rglob`/`iterdir`/`/` chains) and a callee slot with no
  literal before it must count as an UNKNOWN gap unless the callee is a recognised root — but it is a fourth rewrite of
  the same function, which is the signal to stop.
- **`root_dir=` / `dir_fd=` keywords.** `glob("tools/*.json", root_dir=TESTS_DIR)` — the keyword root never
  un-anchors the pattern, so the run reads as repo-root `tools/` while it walks `tests/tools/`.
- **`..` segments.** `join(ROOT, "tests/../tools", "gen_*.py")` keeps the interior `..` inside a literal piece as lead
  (`tests/../tools`), matching nothing, while the walk lands in `tools/`.
- **Blank-containing shell templates.** `check_call("python3 tools/%s.py --check" % tool, shell=True)` — `QUOTED`
  excludes blanks (to skip messages), so a shell command template is never read although rule 5 claims templates.
- **Unlisted discovery.** `shutil.copytree` / archive extraction (`tarfile`, `zipfile`, `shutil.unpack_archive`) of a
  repo subtree, and child `pytest` / `python -m pytest <dir>` runs started from a test, discover files with no walker
  the list knows.
- **Header over-claims.** After each round the "unjudged, stated" paragraph had claimed slightly more than the code did
  (bare references and plain-string `exec` in round 2; the receiver case in round 3). A parked judge must not be revived
  without first making that paragraph the test oracle: every sentence in it a row.

Why parked and not "one more round": the honest reading of four passes is that a static reader of Python call
expressions converges on the real thing only asymptotically — each round closed the reported shapes and every widening
was toward STALE, but each new pass found the next layer at the same place (how a path expression is spelled). The exact
alternative — refuse whenever the two changes share one test's import/read cone — needs real per-test cones, and today
`tests/conftest.py`'s start-up imports make every shard cone ≈ 170 files (measured by the reviewer), so it degenerates
to "always STALE". **The judge becomes worth reviving the day a runtime import/read audit (the #523 machinery already
records docs reads per test; extending it to modules and repo files is the natural route) can supply those cones**; the
follow-up issue below is filed `blocked` on exactly that. Until then code drift = STALE, and the queue cost that
motivated #539 is better attacked by making `session_ci.sh` cheaper or by batching merges per tick.

What the branch history holds for a reviver: the judge at `fe25c59` (ast-based import reading incl. relative levels and
façades; loader/walker classification with alias, bare-reference, exec/getattr/string backstops; the anchored vs
boundary-matched prefix law; modes, sizes, gates, drop-in enrolment, merge-tree + portable-paths over the merged tree;
`timeout` + opt-in plumbing in `ci_fresh.sh`) and 94 rig rows that pin every shape the four passes produced — start by
restoring those rows, then add the "Parked" shapes above as red rows before touching the flattener.

Follow-up filed: "disjoint-drift judge (parked)" — P2, area:process, `blocked` on a runtime import/read audit that can
supply real per-test cones: **#610**.

## Follow-ups (searched: none filed before this stream; F1–F3 are superseded by the parking — kept as history)

- F1 — fold the docs-ADD collision heredoc of `ci_fresh.sh` into the judge as a second entry point (one loader, one
  place that runs `check()` over a name set, one findings format). Keep its no-merge approximation there rather than
  `merge-tree` (git < 2.38 clones would otherwise regress from FRESH(docs-only) to cannot-judge) — or take the issue
  body's original bullet 1 and accept that floor. Kept out of this PR to leave the docs-only rows byte-identical.
- F2 — `sync_plugin.py` as a hard gate is today's dominant STALE; a finer rule ("the other side touches nothing under a
  mirrored root") is possible but needs the mirror map out of `sync_plugin.py` as data.
- F3 — (superseded by the ruling: the switch is `CI_FRESH_JUDGE`, default off) its default could live in `.github/autonomy.json` (`pipeline.judge_code_drift`) with the env var
  as the in-tick override, so the policy is visible in the ledger (S-2026-08-09-b).

BRANCH STATE
- branch: cam/539-ci-fresh-disjoint-drift (rebased on origin/main 5f38b00 for round 1; head reported to the tech lead)
- files: tools/dev/ci_fresh_drift.py (new), tools/dev/ci_fresh.sh, tests/test_ci_fresh.py, docs/process/AUTONOMY.md
  (one clause, §12c Merge row), .github/prompts/tick.md (one clause, §2), docs/inbox/ci-fresh-merge-tree.md (this)
- gates, first head (545e3da): stream-local four files 85 passed / 3 skipped; whole merged shard 2035 passed / 134
  skipped / 3 xfailed on the committed tree (the earlier 1 failed = the gates meta-test reading `git ls-files` before the
  judge was tracked); tech-lead CI on that head 2042 / 131 / 3xf pass; review 🛑 (round 1 above)
- DESCOPED per the tech lead's ruling after the fourth pass (see "Parked"): the branch now carries only the
  rewritten-trunk check in tools/dev/ci_fresh.sh (+ header sentence), two rows in tests/test_ci_fresh.py, one sentence
  each in AUTONOMY §12c / tick.md §2, and this record; tools/dev/ci_fresh_drift.py and all judge rows removed.
  Gates on the descoped tree: five stream-local files 92 passed / 3 skipped (test_ci_fresh.py: main's 23 + 2 new);
  portable paths ok 2989; bash -n clean
- gates, fix round 3 (history): tests/test_ci_fresh.py 94 passed / 2 skipped; five stream-local files 161 passed / 3 skipped;
  portable paths ok 2990; bash -n clean; rebased on the current origin/main before the push
- gates, fix round 2: tests/test_ci_fresh.py 75 passed / 2 skipped; five stream-local files 144 passed / 3 skipped;
  portable paths ok 2983; bash -n clean; rebased on origin/main 828bdae; whole shard left to the tech lead's sandbox
  this round (optional per the review)
- gates, fix round 1: `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_ci_fresh.py tests/test_shard_list.py
  tests/test_portable_paths.py tests/test_docs_read_audit.py tests/test_techlead.py -q -rs` → 132 passed / 3 skipped
  (gawk, busybox, the audit's self-test reader); `python3 tools/dev/check_portable_paths.py` → ok: 2983;
  `bash -n tools/dev/ci_fresh.sh` clean (no shellcheck on this VM); whole merged shard re-run on the round-1 tree — count
  in the PR thread with the new head
- staged vs shipped: nothing staged; no viewer batch; no plugin/src change
