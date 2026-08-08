# coord-guards — token-free coordination bot + protocol rewrite (issue #46)

Stream: orchestrating cleanup session, 2026-08-08 (cloud). Charter: after the
repo's first multi-contributor night, stop sessions from doing the same work
twice, losing stacked PRs, and hiding pushed branches — **without** the
Anthropic-token-backed review/auto-fix bots (the owner does not want a work
token on a personal repo; that decision stays open and this stream does not
touch `automerge.yml` / `claude-review.yml`).

## What happened that this fixes (evidence, first ~3 h after import)

| failure | instances | cost |
|---|---|---|
| Same bug filed twice, minutes apart, by two contributors' sessions | #26/#34 (7 min), #29/#32 (3 min), #27+#37/#33 (5 min) | 3 duplicate issues |
| Same fix built twice | PRs #28/#35 (validate_plugin), #31/#36 → #41 (CI v1) | 4 of 11 PRs closed unmerged (36 %) |
| Issues actually claimed (assigned) before work started | 2 of 27 open | — |
| Stacked PR closed **unmerged** by parent's squash+delete, nobody notified | #39 (2 s after #38 merged); #40 stranded on the dead base | 1 fix (#37) silently off `main` |
| Branch pushed with no issue and no PR | `claude/rfa-revit-api-compat-izqaum`, 39 files, ~1 h invisible | now #44 / #45 |

Root causes, not symptoms: (1) claiming was a `gh` command and cloud sessions
have no `gh`, so nobody claimed; (2) nothing looked for an existing issue at
filing time; (3) automerge's oldest-PR-wins duplicate rule fires at *merge*
time, after the work is done twice; (4) squash+delete vs stacked PRs is a
GitHub behaviour nobody had written down; (5) "push early + draft PR" was
prose only.

## What was built

* `.github/workflows/coord.yml` — seven small jobs, `GITHUB_TOKEN` only, no
  third-party actions beyond `actions/checkout`:
  `claim` (`/claim` / `/release` comments; serialized per issue by a
  concurrency group so two claims seconds apart resolve deterministically),
  `assignment-label`, `issue-dedup`, `pr-link` (needs-issue / late-claim /
  overlap / negation-trap), `stack-guard`, `stack-rescue` (event + 30-min sweep,
  because merges made with the Actions token emit no events; recreates the
  deleted base ref, reopens, retargets, deletes the ref again; skips children
  whose commits already ride in an open PR), `orphan-sweep` (draft PR per orphan
  branch, or a tracking-issue line if the repo forbids Actions-created PRs).
* `tools/dev/coord.py` — stdlib helper: IDF-weighted title-overlap ranking and
  a PR-body parser that mirrors GitHub's closing-keyword linker (including the
  fact that "does **not** close #29" closes #29 — found the hard way while
  editing #40's description tonight; fixed there before merge).
* `tests/test_coord.py` (7 tests, in `tests/ci_shard.txt`): the fixture is the
  real 32-title issue list from that night; `similar` flags all four real
  duplicate filings against what was already filed (scores 0.54 / 0.54 / 0.35 /
  0.27 vs ≤ 0.24 for everything else) and returns nothing for every one of the
  23 unrelated seeded issues.
* `CLAUDE.md` §4: claiming = `/claim`; search-before-filing; MCP equivalents
  for cloud sessions; never stack PRs (why, with #39/#40 as the example);
  orphan sweep; item 0 `coord` in "what happens after you open a PR"; note that
  `coord` + `CI` need no secret. PR template: claim checkbox + the
  "Refs, never *does not close*" rule.

## Verification (numbers)

* `actionlint` 1.7 with shellcheck: **0 errors** on `coord.yml` (two
  intentional info notes suppressed: literal backticks in single quotes,
  variable printf format).
* Every job's script extracted from the YAML (helpers inlined) passes `bash -n`
  and was **dry-run against a fake `gh`** serving fixtures that mirror tonight's
  real state (calls logged, `--jq` applied by real jq): claim free / held /
  re-claim / release / non-collaborator; pr-link no-ref → `needs-issue`,
  unclaimed → late-claim, held-by-other + rival PR #40 → two warnings +
  `overlap` on both, negation → warning; stack-guard; stack-rescue reopening
  #39-shaped case (recreate ref → reopen → retarget → delete ref) and *not*
  reopening it when its commit rides in open #40; orphan-sweep young branch →
  wait, old+ahead → draft PR, PR creation forbidden → tracking issue #77
  fallback; issue-dedup #34 → "#26 (open, held by @Ckaragitz12) … 54 %", #33 →
  #27, unrelated title → silent.
* Repo gates on this branch: `check_portable_paths` ok (2621), `sync_plugin
  --check` in sync, `validate_plugin` PASS, CI shard **88 passed / 23 skipped**.
* Live test still to come: `pr-link` and `stack-guard` run from the PR's own
  copy of the workflow the moment this PR opens (pull_request events use the
  head's workflow files); `claim` / `issue-dedup` / the sweeps only go live once
  this is on `main`.

## Cleanup done alongside (GitHub state, no code)

* #40 retargeted to `main` + `main` merged in (author's commits untouched); it
  now carries #39's zip fix too — title/description say so under an attributed
  header, `Closes #37`; Linux gates re-run on the merged head and posted;
  matched pass/fail pair for the cp1252 crash reproduced on Linux with a forced
  ASCII locale (main: traceback in `manifest.py:370`; #40 head: JSON result).
* #39 annotated (why it closed, where its commit went).
* #32 closed as duplicate of #29, #33 as duplicate of #37 (+#27), each with the
  one detail worth carrying over.
* #44 opened as the charter for the orphan branch and #45 opened from it as a
  draft, with its conflict (`validate_plugin.py` vs #28), hot-file touches and
  suggested split spelled out.

## Open questions / follow-ups (proposed, not claimed)

* Owner decision pending: review/auto-fix bots' token. Everything here is
  independent of it. If they stay off, consider replacing the AI verdict in
  `automerge.yml` with GitHub-native required reviews (1 approval from another
  collaborator) — same "no work token" property.
* Optional repo checkbox: *Allow GitHub Actions to create and approve pull
  requests* (lets `orphan-sweep` open the draft PR itself).
* `ci.yml` could run `actionlint` on workflow changes (pip `actionlint-py`);
  left out to keep this PR off the CI workflow.
* A `windows-latest` CI job (#40 makes the shard green on Windows) is the
  structural fix for the cp1252/zip class of bugs; belongs to #2's follow-up.

## BRANCH STATE

* Branch `claude/team-status-check-ezhl90` from `main` @ `0c5b6d4`.
* Files: `.github/workflows/coord.yml` (new), `tools/dev/coord.py` (new),
  `tests/test_coord.py` (new), `tests/ci_shard.txt` (+1 line),
  `.github/pull_request_template.md`, `CLAUDE.md` (§4 only — hot file, issue
  carries the label), this record.
* Gates: listed above, all green locally. Touches `.github/workflows/**` →
  cannot be bot-merged; owner squash-merges by hand.
* Nothing staged for the viewer; no `.rvt`/`.rfa` produced; no plugin content
  changed (`sync_plugin --check` clean).
