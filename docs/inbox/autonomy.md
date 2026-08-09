# autonomy — sessions own the backlog; the pipeline needs no human (issue #55, steer #54)

Stream record. Territory: `.github/**` (workflows, prompts, issue forms, config, PR
template), `tools/dev/{techlead,coord}.py`, `tests/test_techlead.py`, `tests/ci_shard.txt`,
`.claude/**`, `CLAUDE.md` (hot file — #55 carries `hot-file`), `docs/process/AUTONOMY.md`,
`docs/PROGRAM.md`, `docs/STEERING.md`, `docs/requirements/README.md`, this record. No engine,
plugin or skills paths.

## What was asked (verbatim steer, logged as #54 before anything was built)

> … I still feel like we need an official task board. His CC also said humans are still
> required for the requirements gathering and making tickets or tasks but I disagree with this
> approach. When one of us introduces or volunteers a new requirement or steers you, log it,
> track it, etc. But otherwise you (CC) should be figuring out what needs to be done based on
> the overall or general project goals and program goals. You are our tech leads … So come up
> with a system, log it and document it, make it known to any Claude code session going
> forward, and make sure everyone uses it. Also find a solution to making sure the code to PR
> to review to fix to merge workflow is entirely automated end to end with zero human
> intervention. Remember that we all may turn off our computers or stop our CC sessions at
> times and pick up in a fresh one randomly later

## What was built

**The system** is specified in `docs/process/AUTONOMY.md` (roles, artifacts, the loop, labels,
bots, what still needs a human and why, knobs, failure modes) and made binding + auto-loaded
through `CLAUDE.md` (§4 rewritten around "sessions are the tech leads; humans steer"; the two
planning inputs `docs/PROGRAM.md` and `docs/STEERING.md` are `@`-imported so every session has
the goals and the standing steers in context). Concretely:

| Piece | Files | Runs on |
|---|---|---|
| Steer log — 4 channels: session `/steer`, the *🧭 Steer* issue form, `/steer <text>` comment anywhere, free-form issue → `intake` | `.claude/commands/steer.md`, `.github/ISSUE_TEMPLATE/steer.yml`, `coord.yml` (claim job + issue-intake job), `techlead.py steer`, `coord.py taskshape` | GITHUB_TOKEN |
| Goals + standing steers, auto-loaded | `docs/PROGRAM.md`, `docs/STEERING.md`, `CLAUDE.md` imports | — |
| The board (pinned issue #56, label `board`) | `board.yml` → `techlead.py board` (classify → render → upsert → pin) | GITHUB_TOKEN, hourly + issue/PR/workflow events |
| Tech-lead planner (scheduled + on steer) and the same charter for sessions (`/techlead`) | `techlead.yml`, `.github/prompts/techlead.md`, `techlead.py brief`, `.claude/commands/techlead.md` | Claude token; 6-hourly (3 of 4 ticks exit in the gate when nothing needs judgement) |
| Unattended worker + rebase mode | `worker.yml`, `.github/prompts/worker.md`, `techlead.py pick` | Claude token; 2-hourly, WIP ≤ 2, ≤ 4 runs/day, `auto` label gate |
| Pipeline dead-ends removed | `automerge.yml` (close linked issues after merge; quiet green approved drafts auto-ready; review re-request; conflict → rebase dispatch; `AUTOMERGE_TOKEN` optional for workflow PRs; `duplicate-pr`), `claude-review.yml` (dispatchable; 80 turns; verdict rescue pass; reset-aware budget 3; exhaustion → `bot-stuck`), `techlead.py sweep` (re-queue stuck after 24 h as `ready`+`retry`, free dead worker leases, nudge/close stale drafts) | mixed |
| Queue semantics shared by `/next`, the worker and the board | `coord.py queue` (ready, unassigned, not gated, not in review unless `retry`, not `bot-working`; P0 > P1 > rest, oldest first) | — |
| Session-side "make sure everyone uses it" | `.claude/settings.json` SessionStart banner (`techlead.py hello`, live counts when a token is available, offline-safe), `/steer` `/techlead` `/board` commands, PR template checkbox, START HERE #25 rewritten, board footer | — |
| Knobs + pause | `.github/autonomy.json` (read from the default branch at run time by every bot); label `bots-paused` on the board issue | — |

Dogfooded in the same session: steer #54 (verbatim, then `triaged` with a comment linking
what it became), task #55 (`Refs #54`, `from-steer`, claimed), board placeholder #56, START HERE
#25 rewritten, standing steers S-2026-08-09-a/b recorded. A second steer arrived mid-work and
went through the same path first: **#58** — *"Sessions are the tech leads AND they can work on
code themselves … AND they can call other subagents as the hands OR start up and communicate with
additional CCR sessions as the engineers"* → S-2026-08-09-c, the charter's "a tech lead here also
builds" preamble, `CLAUDE.md` §4 wording, AUTONOMY §2 (new *Hands* row) / §6, and the new
`/fanout` session command (engineer sessions via the CCR `create_session`/`send_message` tools,
one issue each claimed with `/claim`; subagents with worktree isolation for pieces of the
session's own issue).

## Second pass (four-angle cleanup review + the live `claude-review` run on PR #57)

- **Live finding:** the review action refuses to run when the PR's `claude-review.yml` differs
  from `main`'s (its log: "workflow file must … have identical content to the version on the
  repository's default branch"), so PR #57 can never get an AI verdict — and neither can any PR
  that edits the reviewer. Everything upstream ran as designed on that head (PR/SHA resolution,
  config fallback `max_fix_attempts=3`, `continue-on-error` letting the verdict step run and fail
  red on purpose). New rule in `automerge`: *no verdict + PR touches `claude-review.yml` →
  `needs-human` immediately* (not a 4 h re-request loop); board lane + AUTONOMY §10/§13 rows.
- **Two real defects caught by review:** `board.yml` lacked `checks: read` / `actions: read`
  (CI state and bot health would have rendered as "no checks" on this private repo); the board's
  blocker logic had drifted from automerge (`wip` hold, `merge-when-green`, and `needs-issue`,
  which automerge never blocks on). Fixed, and pinned by tripwire tests: labels automerge acts
  on ⊂ `LABELS` and known to `pr_status`; verdict/attempt/reset/exhausted markers spelled
  identically on both sides; automerge's closing-keyword grammar is now coord's (`CLOSES_PY`
  inline snippet, tested against `coord.refs()` on six bodies incl. `Closes: #N` and HTML
  comments); `autonomy.json` complete + equal to `DEFAULTS` + equal to every `jq // N` fallback.
- **Efficiency:** per-PR API calls 5–8 → 3 (+2 only in the lanes that need mergeability / the
  head-commit date); no second full snapshot after a sweep (issues re-fetched only); PR comments
  reused from the snapshot; `worker_runs_today` stops at the cap and skips sub-3-minute runs;
  `hello` makes three small filtered queries instead of paging every open issue; automerge fetches
  each PR's comments once (was up to 4×), takes all PR fields from one `gh pr list`, guards label
  writes, fetches review runs lazily; board drops `automerge` from its `workflow_run` triggers and
  settles 45 s. Board rows use absolute UTC stamps, so an unchanged repo re-renders byte-identical
  (modulo the stamp line) instead of drifting every hour.
- **Simplification:** repo-relative client paths (no `{r}` placeholder), one `_requeue_issue`,
  `is_stuck` / `is_bot_pr` / `closing_map` helpers, `coord.HELD`, dead fields/params removed,
  `REVIEW_LIB` shared by both claude-review jobs, two cron entries instead of hour arithmetic in
  `techlead.yml`, knobs handed to worker/planner by `techlead.py pick` / `config` instead of
  re-`jq`ing the file.
- **Security review notes:** actions stay referenced by major tag (`@v1`/`@v6`, the repo's
  existing convention — SHA pinning filed as a follow-up hardening task); the worker's tool
  surface is deliberately a session's (documented trust model, AUTONOMY §9); dropped the
  redundant bare `python` glob.

## Evidence

- `tests/test_techlead.py` — 22 tests (config merge; **autonomy.json complete == DEFAULTS ==
  every workflow `jq // N` fallback**; review-state parsing incl. budget reset; CI gate ==
  automerge's; PR status lanes in automerge order incl. absolute auto-ready ETA, `wip` hold,
  `merge-when-green`, reviewer-edit, needs-issue-as-note, bot-stuck; **shared vocabulary
  tripwire** (labels + markers vs automerge/claude-review text); **closing-keyword grammar**
  (automerge's inline snippet vs `coord.refs()`); workflows only create labels `LABELS` owns;
  classify sections/health/pause; board completeness + hour-later re-render identical + AUTONOMY
  anchor; brief; pick: retry-first / continue on open PR / continue on body-recorded branch,
  auto-only, hot-file skip, WIP, cap, pause, disabled, any-ready, dispatch, `max_turns` output;
  sweep timings incl. wip exemption; steer spec; queue rules; HTTP client repo-relative URLs,
  paging, `comment_once` with/without prefetched bodies, `unassign`, errors; upsert create+pin /
  skip-identical; CLI `hello` offline, `steer --dry-run`, `config`) → **22 passed**; with
  `tests/test_coord.py` → **33 passed** (1.0 s). Added to `tests/ci_shard.txt`; whole shard
  locally: **129 passed, 23 skipped** (39.8 s).
- Board/brief/pick/sweep rendered from a fixture mirroring the live repo on 2026-08-09 (26 open
  issues, PRs #40/#57-59 shapes) — output reviewed by eye (scratch `tl/board.md`).
- `actionlint 1.7.12 -shellcheck` over all nine workflows: **0 errors**; the only remaining
  shellcheck notes are three info/warning-level ones in pre-existing `coord.yml` sweep lines
  (SC2016/SC2059/SC2034). All workflow + issue-form YAML parses; `bash -n` clean on all 35 `run:`
  blocks.
- **Live on GitHub at PR #57's first head:** `CI` green (py3.11 + py3.12, shard incl. the new test
  file); `main`'s automerge posted its draft-green comment (pipeline alive); the new
  `claude-review.yml` ran up to the model call and demonstrated the reviewer-edit refusal above.
- Gates: `check_portable_paths` ok (2634 tracked + the new files are plain ASCII names),
  `sync_plugin.py --check` in sync (tools/dev is not mirrored into the plugin),
  `validate_plugin.py` PASS (23 assertions).
- NOT run here: the workflows themselves (they only execute from `main`; `pull_request_target`
  / `schedule` / `issues` / `workflow_run` cannot be exercised from a branch), and a live board
  render (this sandbox's token is MCP-only: `GET /issues` → 403). Post-merge verification plan
  below.

## Findings

- **Bot merges did not close linked issues** (#50 after #51): confirmed and fixed structurally in
  automerge (explicit `gh issue close --reason completed` per closing ref).
- **The 40-turn review cap was the most frequent stall** (#51 twice at 41/44 turns) → 80 turns +
  a rescue pass + `continue-on-error` so the verdict steps still run + automerge re-request.
- **`GITHUB_TOKEN`-raised events do not trigger workflows** — so `/steer` via `coord` and the
  `intake` label wake the planner with an explicit `workflow_dispatch` (allowed), and every bot
  action is written to converge on the next scheduled run anyway.
- **Workflow-file PRs are the one platform-imposed human gate** (Actions token may not merge
  them). Mitigations: logic lives in `tools/dev/*.py` + prompts + `autonomy.json` (all
  bot-mergeable); optional `AUTOMERGE_TOKEN` documented; this PR is that one hand-merge.
- The GitHub Projects (v2) board was considered and rejected as the *primary* board: it needs a
  PAT for anything beyond built-in automations and cannot show "why is this PR not merging".
  The rendered issue can; a Projects mirror stays possible later (`area:process` follow-up if
  anyone wants the kanban view).

## Post-merge verification (scheduled from the authoring session)

1. `board` run on the merge push? (no — first run is the next issue/PR event or :20 cron):
   board #56 body replaced by the render, pinned (or pin skipped with a logged reason).
2. `coord`: comment `/steer test …` on #56 → steer issue appears, planner dispatched.
3. `techlead` first scheduled/dispatched run: gate outputs, `plan` job posts a planning note on
   #56, #54 gets `triaged`.
4. `worker` 2-hourly: `pick` output (expect "nothing eligible" until the planner marks `auto`),
   then a real run → PR by `claude[bot]` → CI → review → merge → issue closed by automerge.
5. `automerge`: PR #40 (green, approved, draft, quiet for a day) is auto-readied and merged on
   the first sweep after merge — the live proof of the quiet-draft rule; #37 closes with it.
Anything off → fix in `tools/dev/techlead.py` / prompts (bot-mergeable) where possible.

## Open questions (filed or to be filed by the planner, not left here)

- Should the worker be allowed `hot-file` one-liners (`worker.allow_hot_file`)? Default off.
- A `windows-latest` CI job (O2) will double CI minutes; the board's Health line should grow a
  minutes estimate if the owner wants to watch spend (`area:process`, P2).

## BRANCH STATE

- Branch `claude/team-status-check-ezhl90` from `main@bd8b50e`; PR closes #55, refs #54.
- Files: listed in the table above + `docs/requirements/README.md`, `.github/pull_request_template.md`,
  `tests/ci_shard.txt`.
- Gates: 33 stream-local tests green; CI shard 129 passed / 23 skipped locally and green on
  GitHub; actionlint 0 errors; portable paths (2654) / plugin drift / plugin structure clean.
  Full suite not run (process-only change; nothing under `src/`, `plugin/`, `skills/`).
- Shipped vs staged: everything ships with the merge; the workflows go live on `main` only —
  **owner squash-merges this PR by hand** (it changes `.github/workflows/**`, and it edits the
  reviewer, which therefore cannot review it). Live artifacts already exist: #54 and #58
  (steers, triaged), #55 (task), #56 (board placeholder), #25 (rewritten). Follow-ups filed as
  task issues by this session in its tech-lead role: SHA-pin third-party actions; single GraphQL
  query for the board snapshot.

## Day-one live fixes (issue #64) and the session-merge path (issue #62), same session

Observed within minutes of #57 landing (board render 06:25 UTC, run list): (1) `board.yml` ran
~30 times in 3 minutes — label/assignment events from the planner pass and the engineers' claims
plus `workflow_run` fan-out — 29 cancelled by the concurrency group, each still a billed runner
start; (2) a *cancelled* `render` run attached to PR #63's head read as "🟥 CI red (render)" on
the board and would have blocked automerge, and the same would have hit every engineer PR opened
during a busy spell. Fixes: board triggers bounded to a 20-min cron + issue/PR open/close/ready
(automerge, planner and worker dispatch a refresh themselves after changing state); one shared
ignore-list of the bots' own job names (`BOT_CHECK_NAMES` in techlead.py == `IGNORED_CHECKS` in
automerge.yml), with a tripwire test that parses every non-CI workflow's job ids/names and fails
if one is missing, and asserts CI's own jobs are *not* ignored.

Steer #61 ("let's fix it and keep the show running") made the workflow-file gate a **session's**
job: automerge now labels such PRs (and reviewer-edit PRs) `session-merge` with a comment telling
the next coding session to check CI + verdict (or read the diff) and squash-merge with its own
credentials; the board shows them in review as "waiting for any coding session", not under
*Waiting on a human*; the SessionStart banner prints "MERGE FIRST: PR #…"; `CLAUDE.md` §4 step 1
and AUTONOMY §7/§10/§13 say so. `needs-human` is left for a merge GitHub itself refused. The
planner had already filed this as #62 from the steer and opened #63 for the STEERING row — the
loop closing on itself. Tests: 35 passed (2 new tripwires); actionlint clean; gates clean.
This PR (#62 + #64) is itself a workflow-file PR: merged by the authoring session once CI is green.

## Single-owner fixing (steer #67 → issue #69), same session

Question from ck: do the sessions' PR subscriptions duplicate the repo bots, given review/CI
latency and sessions that vanish? Audit: review, merge, claims, board/planning are single-owner;
**fixing was not** — `ci-autofix` (on red CI) and the review job's inline fix pass started within
minutes of a push while the subscribed authoring session did the same. Change: the review job only
reviews; a new dispatch-only `fix` job (mode=fix) handles red CI + 🛑 findings for the *current*
head; `automerge` dispatches it once per (sha, attempt) only when `now − max(head commit, red-CI
completion, 🛑 verdict comment, last attempt marker) ≥ pipeline.fix_grace_minutes` (15), from the
default branch (so branches with an older reviewer copy still work; review re-requests too). The
fix job re-fetches before pushing and yields to a newer head. Effect: a live session always goes
first; an abandoned PR is picked up within ≈ grace + one sweep; no double-fixing; and one
immediate 60-turn fix pass per 🛑 is no longer spent when the author fixes it two minutes later.
Tests: 36 passed (new tripwire: dispatch string, `mode` input, no inline fix, no `workflow_run`).
First engineer PR of the fan-out went through the untouched pipeline end-to-end meanwhile: #68
(issue #9) — CI green, ✅ review, automerge, issue closed, zero human involvement.

## Hardening the session-merge path (issue #88), same session

An automated security review of `main` objected — fairly — that reviewer-edit PRs were being offered
to a session with no verdict at all, and that the authoring session merged its own workflow PRs
(#57/#65/#78). Kept the owner's intent (nothing waits on a human click) but restored an independent
check: automerge no longer special-cases reviewer edits; the generic no-verdict path re-requests the
review from **the default branch's reviewer**, which the action accepts even when the PR edits
`claude-review.yml`; `session-merge` is only ever applied on the approved path (✅/🟡 verdict for the
exact head + green CI), its comment/banner/CLAUDE.md text require re-checking both at merge time,
`--match-head-commit`, reading the workflow diff, and preferring a non-author session; a workflow
PR for which no independent verdict can be produced within the re-request window becomes
`needs-human` = `merge-when-green` from a collaborator other than the author (last resort, not the
default). Also least privilege: `worker.yml`/`techlead.yml` model jobs drop to `actions: read`; a
separate `refresh-board` job holds `actions: write`. This PR is itself the first to go through the
hardened path (it edits automerge but not the reviewer: verdict from its own run, then a session
merge with `--match-head-commit`).

**Found while dogfooding #89 (review dispatched from `main` by hand):** the review action rejects
every run "initiated by non-human actor" unless `allowed_bots` names it — and it was empty. That
silently broke every automerge-dispatched review re-request and fix pass, coord's planner
wake-ups, automerge's rebase dispatch, and the review of any PR *authored* by the planner or the
worker (`claude[bot]`) — why #63/#73 sat verdict-less. Every `claude-code-action` step
(`claude-review.yml` ×3, `techlead.yml`, `worker.yml`, `claude.yml`) now sets
`allowed_bots: "github-actions[bot],github-actions,claude[bot],claude"` (our own bots only, both
spellings), pinned by a test. The same review also caught a real thrash in my `needs-human`
self-heal: it must not apply when GitHub refused the merge at this head (a persistent refusal
would be retried every sweep); the lift is now scoped by reason via the per-head marker comments
(`review-stuck-<sha>` lifts on approval, `merge-failed-<sha>` holds, no marker for the current head
= head moved → re-evaluate). Note: `worker.yml`'s `refresh-board` job now also fires after a
`rebase`-mode run (the old inline step exited first) — intentional and harmless (idempotent
dispatch; a rebase push changes the board anyway).

## Claims at real-time scale (steer #90), same session

ck asked how three people's agents avoid taking each other's work "at lightning speed". Model kept
and made explicit: pull, don't push (S-2026-08-09-f). Two real gaps closed: (1) the lock knew
logins, not sessions — `/next`/`/claim` now write session-tagged lock markers
(`<!-- lock by session token -->`, `coord.py standing_locks`), `/next` is serialized per login,
`/claim s=<tag>` refuses an issue another session of the same login locked < 2 h ago, and
`techlead.py mine` gives a fresh session the resume rule (this-session / active-elsewhere / idle);
(2) the ~1-minute cross-login race — `/next` and `/claim` now VERIFY (earliest standing assignee by
event replay + earliest standing lock) after a settle delay and retry the next candidate for the
loser instead of a late ⛔; `techlead.py claim <n>` does the same from a session. `/release`, the
reaper and the re-queue sweep post unlock markers so old locks lapse. Also: verdict markers are now
matched by a ≥ 12-hex prefix of the head in automerge/claude-review (the reviewer dropped the last
digit of a SHA once on #89; that can no longer stall a PR).

**Review rounds on #107 (independent reviewer from `main`), for the record:** (1) a re-lock comment
carrying unlock + fresh lock in one body self-cancelled the fresh lock (`>` → `>=`: unlocks in a comment
apply before its locks); (2) a stray `lc-5.json` from a local drive of `first_lock` was committed
(`first_lock` now writes to `mktemp`); (3) cross-login races were judged by two authorities that can
disagree inside the settle window (assignment-event order vs lock-comment order), leaving a "loser" still
assigned. Resolution: ONE authority per question — across logins the earliest standing assignee wins
(exactly `single-holder`'s rule), between sessions of one login the earliest standing lock *of that
login* picks the session (`first_lock <issue> <login>`, `claim()` filters its own login's locks). A request
whose assignment was first therefore wins even if a rival's lock comment posted earlier; the rival (not
first assignee) unassigns and yields; a request that finds its own *other* session's lock first keeps the
login's assignment and drops only its own lock. No branch can now report a loss while leaving a stale
assignment.

## Viewer batch numbers at fan-out scale (#285), same session, 2026-08-09

**Failure observed:** two wave-5 engineer PRs (#277 wall solids for #144, #283 identity rungs for
#134) both added `experiments/acceptance/batch_57/58/59.json` with different contents and both
told the human uploader "batches 57/58/59" (#145, #19). Cause: `probe_batch.py stage` numbers a
batch "highest local `batch_<n>.json` + 1" and both branches were cut from the same `main`
(highest 56). Caught by hand this time (older PR #277 kept the numbers; #283 restaged as 60–62 with
`--batch`); at 4–5 engineers per wave, most genesis/render work ending in STAGE, it would recur every
wave — and a verdict "for batch 57" that means two files is a bookkeeping fault in the one instrument
rule 4 makes authoritative. An integer, campaign-global, monotone counter has to stay (`"batch": n`
in manifests, `CTRL_*_b<n>` control names, `--batch type=int`, `batch_(\d+)` parsers in ~20 tools,
every `ORCHESTRATOR VERDICTS` section) — so the fix is an allocator, not a new id scheme.

**Fix, same pattern as the claim locks:** one server-side authority instead of N checkouts racing.
- `/batches [k]` on any issue or PR → `coord` (repo-wide concurrency group `batches`, so two requests
  are strictly ordered) runs `tools/dev/coord.py reserve`: `N..N+k-1`, N = 1 + max(highest
  `experiments/**/batch_<n>.json` on the default branch — read from the runner's own clone with
  `git ls-tree`, no API call —, highest earlier reservation, highest batch file any open PR adds,
  and never below `HISTORICAL_ROUNDS`); records `<!-- batches by lo hi issue token -->` on the ONE
  `batch-registry` issue (created on first use, `tracking`); replies in place with the command.
  Idempotent per requesting comment; all wording rendered by the tested python, bash only posts.
- The reservation reaches the code that picks numbers: `probe_batch.next_batch_number()` honours
  `RVT_BATCH_FLOOR=<N>` — the seam every stager shares (only `probe_batch.py stage` has `--batch`;
  ~13 other tools compute their own number through that function) — and `stage` prints a
  reserve-first note when it had to choose locally.
- Safety net: `coord.py batchjudge` judges ALL open PRs at once (a number belongs to the *issue* it
  was reserved for — every engineer session runs under one login —, unreserved numbers to the OLDEST
  PR adding them; everyone else must move, each mover gets a distinct target range). It runs when a
  PR opens / is edited (`pr-check`, after a 1-call probe that the PR adds a batch file at all) and
  hourly in `sweep` — deliberately NOT on `synchronize`: a runner per push of every PR (~150/day at
  today's pace) to catch a few events per wave was the wrong price; hourly re-judging costs one PR
  listing + a local tree read. Movers get `batch-clash` + one comment per number set with the exact
  range/command; the label clears itself; **automerge holds `batch-clash`** so the ledger can never
  receive two files behind one number; the worker's rebase mode refuses to hand-merge an add/add
  batch manifest (it cannot restage) and labels the PR instead.
- CLAUDE.md §2 (+ env var list), the `/fanout` engineer brief and AUTONOMY §12b/§13 say
  reserve-then-stage; `batch-clash` / `batch-registry` join `techlead.py LABELS` (wording owner).

**Simplify pass (4 reviewers) changed the first draft materially:** dropped `synchronize` (efficiency),
tree via `git ls-tree` instead of the recursive-tree API (0.7 MB/call), one all-PR judge instead of a
per-PR `batchclash` + rival-flagging pair, python renders every message and owns the 1..9 bound and the
idempotency rule (bash formatted ranges three different ways), registry labels created through the
shared `label` helper, `linked` derived from the PR bodies already in `prs.json`, the floor now agrees
with `probe_batch.HISTORICAL_ROUNDS` (a test pins the pair), and the reservation is consumable by every
stager through `RVT_BATCH_FLOOR` (altitude: "the reservation could not reach the code that picks
numbers"). Not taken: allocation by create-only git ref push (elegant, token-free, but unverifiable
whether the cloud git proxy accepts a non-`refs/heads/` namespace, and a second coordination substrate
next to issue comments); a token-free git floor inside `probe_batch` (network in a pure-local tool) —
noted on #8, whose campaign-global local numbering is the complementary half.

Evidence: `tests/test_techlead.py::test_viewer_batch_numbers_are_reserved_server_side_and_clashes_are_judged`
replays today's #277/#283 case (newer told 60..62; a reservation for #134 flips ownership; a PR that
reserved on itself owns its range; two movers get 60 and 61..63; re-run of a recorded request answers
57..59/seen; two reservations in one sweep never overlap; CLI round trip of `reserve` + `batchjudge`;
wiring needles incl. "no synchronize", the automerge hold and the rebase rule) — 29 passed; shellcheck
clean on every touched step; `sync_plugin.py --check` clean (probe_batch mirrors regenerated);
validate_plugin PASS; portable paths ok. First live proof is necessarily post-merge (`pull_request` /
`issue_comment` runs use `main`'s helper; the bootstrap guard skips until then): this session posts the
first `/batches` and records the reply on #285.

## The pipeline moved onto the sessions (steer #302), same session, 2026-08-09

The owner declined to fund Actions minutes or a self-hosted runner ("Not going to do any of that. Not
paying."). Logged as steer #302; #300 closed *not planned*, #301 (minute cuts) closed as superseded.
Design change instead of billing: GitHub stays the ledger; compute moves to the sessions.
- `tools/dev/session_ci.sh <pr>` — the CI job as the tech-lead session runs it: head merged with
  `origin/main` in a root-owned worktree; portable-paths (trusted checker) over the PR's file names;
  then the PR tree EXPORTED into a box owned by `nobody`, and `sync_plugin --check`, `validate_plugin`,
  the whole `tests/ci_shard.txt` run as `nobody` under `unshare -n` with `env -i` (no network, no
  credentials, no access to the session's files or the trusted checkout); one JSON verdict line.
  Two sandbox artefacts fixed on the way: the box must live under `/tmp` (every parent traversable by
  `nobody`), and `TMPDIR` must be OUTSIDE the tree (repo-relative path logic in `probe_batch` tests).
  With those the sandboxed shard equals the unsandboxed one test-for-test (703/703 on #299's head).
- `tools/dev/review_brief.md` — the reviewer charter for a fresh context (subagent), same standard as
  the old bot plus an execution rule (PR code only through the sandbox) and the "grep every consumer
  of a changed contract" lesson; returns `✅/🟡/🛑 … VERDICT=`.
- Merge rule: same-tick evidence only (this tick's CI pass + this tick's spawned reviewer's approve/nits
  for the exact head), re-read the head, `merge_pull_request` squash; markers are posted for humans and
  tools but never trusted as authorisation (one GitHub identity for all sessions). A background
  security review of the plan drove both the sandbox and this rule.
- Every `.github/workflows/*` is now `workflow_dispatch`-only (dispatch inputs preserved), so events
  stop producing failed runs and e-mails; tests pin "dispatch-only + the two instruments checked in".
Evidence, first afternoon: #299 (703 passed, 🟡) → d6019ff; #297 (755, 🟡) → c66333e; #304 (787, 🟡,
rule-3 audit of synthetic fixtures) → 2c91fd6; #306 (789, 🟡, allowlist re-measured 41/41 by the
reviewer's own instrument) → 5b6b5a8; #293 (822 after FIVE rounds — each round found one more consumer
of a changed z contract until the tech lead directed a structural settlement: world z canonical,
`level` an annotation) → f3ac44e; #308 (813, 🟡, 1-type loader ids byte-identical to main) → 109345e.
Merges by the session identity fire the `Closes #N` linker; branch protection did not object.
Throughput cost: ~3 min CPU per shard run + one reviewer subagent per head; merges land per tick.
Review of this very PR (#309) by a fresh context returned 🛑 with three real holes in the first checked-in
`session_ci.sh`, all fixed before merge: root read the PR-controlled `tests/ci_shard.txt` from the box AFTER
sandboxed code had run there (a planted symlink exfiltrated root-only file lines into the posted summary —
now read from the git blob on the trusted side, validated as plain `tests/*.py` paths, empty list refused,
`--` before the paths, and the summary reduced to a pytest-shaped tally); the privileged scratch defaulted into
world-writable `/tmp` (now `REPO/.git/session-ci`, 0700, must be an own non-symlink dir; `/tmp/tekton-ci`
parent root-owned) and steps had no PID namespace, so a `nobody` daemon could outlive a run and prepare traps
(now `unshare -n -m -p -f --mount-proc --kill-child` + `--bounding-set=-all --no-new-privs`; verified a
`setsid sleep` no longer survives); and the new test imported PyYAML, which no extra declares (now textual).
Plus: PR number validated, `origin/main` refreshed before the merge test, one run per PR (`flock`).

BRANCH STATE (cam/302-session-hosted-pipeline): `.github/workflows/*.yml` (dispatch-only), `tools/dev/session_ci.sh`,
`tools/dev/review_brief.md`, `CLAUDE.md` §4 banner, `docs/process/AUTONOMY.md` §12c, `docs/STEERING.md`
S-2026-08-09-i, `.claude/commands/fanout.md`, `tests/test_techlead.py`, this record. Gates: `tests/test_techlead.py`
green; portable paths ok; plugin untouched (`--check` in sync). Shipped when merged; the fresh-session hourly
ticker with a lease is the next slice of #302.
