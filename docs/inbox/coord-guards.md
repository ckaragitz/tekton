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

* `.github/workflows/coord.yml` — five jobs, `GITHUB_TOKEN` only, no
  third-party actions beyond `actions/checkout` (job roster and the two repo
  settings that make most of the sweep unnecessary are in the file header;
  CLAUDE.md §4 is the user-facing description):
  `claim` (`/claim`·`/release` sugar for surfaces that cannot assign),
  `single-holder` (the actual invariant, on every native `assigned` event:
  replay the issue's assign/unassign events, earliest standing assignee holds
  it, a second assignee is removed with a ⛔ unless a holder added them —
  serialized per issue together with `claim`), `issue-dedup`, `pr-check`
  (stacked-base warning, then needs-issue / late-assign / held-by-other / rival
  PR / negation trap — rivals go through the same `coord.py` parser, not a
  second regex), `sweep` (hourly + on merges GitHub reports: stack rescue, then
  orphan branches; one job so a private repo pays one billed minute per hour,
  not four).
* `tools/dev/coord.py` — stdlib helper: IDF-weighted title-overlap ranking,
  a PR-body parser that mirrors GitHub's closing-keyword linker (including the
  fact that "does **not** close #29" closes #29 — found the hard way while
  editing #40's description tonight; fixed there before merge), and `rivals`
  on top of the same parser.
* `tests/test_coord.py` (7 tests, in `tests/ci_shard.txt`): the fixture is the
  real 32-title issue list from that night; `similar` flags all four real
  duplicate filings against what was already filed (scores 0.54 / 0.54 / 0.35 /
  0.27 vs ≤ 0.24 for everything else) and returns nothing for every one of the
  25 seeded issues; `refs`/`rivals` pinned on a body with every keyword form.
* `CLAUDE.md` §4: claiming = being the assignee (any surface; `/claim` as the
  fallback), one holder enforced; search-before-filing; MCP equivalents for
  cloud sessions; never stack PRs and never delete merged branches by hand
  (why, with #39/#40 as the example); the sweep; item 0 `coord` in "what
  happens after you open a PR"; the two token-free repo checkboxes. PR
  template: assignee checkbox + the "Refs, never *does not close*" rule.

Review pass (`/simplify`, four angles) changed the first cut materially:
the `in-progress` label mirror was dropped (it duplicated assignee state);
the single-holder rule moved from the `/claim` verb onto the native
assignment event; `stack-guard` folded into `pr-check`, gated to body/base
edits; the two 30-minute sweeps became one hourly job (Actions minutes on a
private repo: ~2,900/month → ~730); per-branch and per-PR API calls hoisted;
one closing-keyword parser instead of two. **Live finding from this PR's own
first push:** `pr-link` checked out trunk for a "trusted" helper that trunk
does not have until this merges → red; it now checks out the PR head (sparse,
`tools/dev` only), which also keeps working while a PR conflicts.

## Verification (numbers)

* `actionlint` 1.7 with shellcheck: **0 errors** on `coord.yml` (two
  intentional info notes suppressed: literal backticks in single quotes,
  variable printf format).
* Every step's script extracted from the YAML (helpers inlined) was **dry-run
  against a fake `gh`** serving fixtures that mirror tonight's real state (calls
  logged, `--jq` applied by real jq): single-holder — second self-assignee
  removed, holder-adds-partner allowed, first assignee's own event quiet,
  release-then-reassign ordering resolved from the event log, sole assignee
  quiet; claim free / held / release; pr-check based-on-main / stacked, closes
  held issue + rival #40 → two warnings + `overlap` on both + negation warning,
  no refs → `needs-issue` (including the create-label-on-first-use path), refs
  only → quiet, closes unassigned #44 → author assigned; sweep rescue reopening
  the #39-shaped case (recreate ref → reopen → retarget → delete ref) and *not*
  reopening it when its commit rides in open #40; orphan branch → draft PR, PR
  creation forbidden → tracking issue fallback; issue-dedup #34 → "#26 (open,
  held by @Ckaragitz12) … 54 %".
* Repo gates on this branch: `check_portable_paths` ok, `sync_plugin --check`
  in sync, `validate_plugin` PASS, CI shard **88 passed / 23 skipped**.
* Live: `pr-check` runs from the PR's own copy of the workflow on this PR
  (pull_request events use the head's workflow files) — first push red for the
  trunk-checkout reason above, fixed in the second; `claim`, `single-holder`,
  `issue-dedup` and `sweep` only go live once this is on `main`.

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
* Owner, two checkboxes (no token): *Automatically delete head branches* and
  *Allow GitHub Actions to create and approve pull requests* (see CLAUDE.md §4
  item 6). With the first on, `automerge.yml` should drop `--delete-branch`
  from its `gh pr merge` (that raw ref delete is what closes stacked children —
  cli/cli#1168) or retarget open children before merging; then part 2 of the
  sweep's rescue can go. Not done here: automerge is out of territory.
* `automerge.yml` still carries its own closing-keyword grep and its own copy
  of `comment_once`; when it is next touched, point both at `tools/dev/coord.py`
  / a shared `COORD_LIB` so there is one parser and one helper.
* `ci.yml` could run `actionlint` on workflow changes (pip `actionlint-py`);
  left out to keep this PR off the CI workflow.
* A `windows-latest` CI job (#40 makes the shard green on Windows) is the
  structural fix for the cp1252/zip class of bugs; belongs to #2's follow-up.

## BRANCH STATE

* Branch `claude/team-status-check-ezhl90` from `main` @ `0c5b6d4`.
* Files: `.github/workflows/coord.yml` (new), `tools/dev/coord.py` (new),
  `tests/test_coord.py` (new), `tests/ci_shard.txt` (+1 line),
  `.github/pull_request_template.md`, `CLAUDE.md` (§4 only — hot file, issue
  carries the label), this record. Two commits: first cut, then the
  review-pass refactor + live-test fix.
* Gates: listed above, all green locally. Touches `.github/workflows/**` →
  cannot be bot-merged; owner squash-merges by hand.
* Nothing staged for the viewer; no `.rvt`/`.rfa` produced; no plugin content
  changed (`sync_plugin --check` clean).
