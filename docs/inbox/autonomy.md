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
Merged as f0bde6a after a third review round (🟡; sandboxed shard 885 passed / 44 skipped / 3 xfailed on the final head);
its three nits (`timeout -k`, loud abort in the brief's recipe, `[ -O "$JAIL" ]`) landed in the follow-up branch cam/302-session-ci-nits.

## CI shard drop-ins + one-run-per-machine + fatal export (issues #328, #329) — eng328, session session_01Jd4Qv6BLvJMjJCtNBSSFwx, 2026-08-09

**Why.** Under the session-hosted pipeline every rebase costs a sandboxed shard re-run (~4 min of tech-lead CPU) plus a
delta review, and `tests/ci_shard.txt` had become the file that forced them: every PR sharding a new test appended one
line at the same spot, so any two such PRs conflicted (#316 vs #310; #324 vs #319, twice — three engineer rebases in one
day for this alone). Separately the #318 review found that `session_ci.sh` only serialized runs of the *same* PR (every
sandboxed step of every PR is uid 65534 under one jail parent, so an overlapping run of PR B could write into PR A's box
while A's shard executed) and that a failed `mkdir`/`tar` export was not fatal.

**What was built.**
- `tools/dev/shard_list.py` (stdlib only, 3.11-isolated-mode clean): the shard = `tests/ci_shard.txt` in its own order
  (`tests/test_schema_gate.py` stays first) + every `tests/ci_shard.d/*.txt` sorted by file name; blank lines and
  whole-line `#` comments dropped, surrounding whitespace/CR stripped, duplicates collapsed (first occurrence wins);
  every entry must match `^tests/[A-Za-z0-9_./-]+\.py$` with no `..` (the exact rule `session_ci.sh` enforced inline
  before), drop-in names must match `[A-Za-z0-9][A-Za-z0-9_.-]*\.txt`, the list must be non-empty — one violation refuses
  the whole list (exit 3, bounded diagnostic: PR-controlled text never floods the log). Two readers, one `merge()`:
  `--root` (working tree; contributors and the reference `ci.yml`) and `--git WT` (git objects of `HEAD` in worktree
  `WT`: `git ls-tree -z` + `git cat-file blob`, regular-file blobs only — symlink/submodule entries are not shard files).
- `tools/dev/session_ci.sh`, line by line: (1) header documents the global lock, the out-of-scope per-run uid, the
  drop-ins, and that setup failures print `{"pr":N,"error":…}` + exit 2; (2) after the per-PR `flock -n 9` a second lock
  `exec 8>"$S/ci/global.lock"; flock -w 5400 8` held until exit — different PRs queue, the same PR still fails fast, no
  cycle (per-PR first, then global); (3) the shard block now runs `python3 -I "$REPO/tools/dev/shard_list.py" --git "$WT"`
  — MAIN's helper by absolute path (never `$WT`/`$BOX` copies), over the merged head's blobs while the root-owned
  worktree still exists and before anything is exported or handed to `nobody`; a non-zero exit becomes the existing
  REFUSED path (`RC=3`), and the old per-entry bash regex loop is kept verbatim as a second gate so the trusted side holds
  even if the helper is ever loosened; `--` before the paths unchanged; (4) the export pipeline's status is captured
  (`pipefail` is on) and after the worktree is dropped the run requires rc 0 **and** `$BOX/tests/ci_shard.txt` **and**
  `$BOX/src/rvt/__init__.py`, else it logs, removes the box, writes `{"pr":N,"head":…,"error":"export"}` and exits 2 —
  the shard never runs over half a tree; (5) `sandbox()` closes fd 8 as well as 9 (`8>&- 9>&-`) so neither lock fd
  reaches PR code; (6) `flock -u 8` at the end. `bash -n` clean; `shellcheck -S warning` clean (shellcheck 0.11.0 from the
  `shellcheck-py` wheel — `/usr/local/bin/shellcheck` is absent on the cloud image; main's copy is equally clean).
- `.github/workflows/ci.yml` (still `workflow_dispatch`-only): the shard step writes `python tools/dev/shard_list.py
  --print` to a file first (a refused list fails the step instead of degrading to bare `pytest`), then
  `pytest -q --durations=10 -- "${SHARD[@]}"`.
- `tests/ci_shard.d/README` (the rules), `tests/ci_shard.d/328-shard-list.txt` (the first drop-in: this stream's own
  test), `tests/test_shard_list.py` (22 tests: union order, dedup, comment/whitespace/CRLF handling, 12 refused entry
  shapes incl. smuggled pytest flags and `..`, 5 refused names, empty list, bounded diagnostics, tree reader == git
  reader == CLI on the real repo, every listed path exists, drop-ins only ever append after the base file, both consumers
  use the helper and the old `git show HEAD:tests/ci_shard.txt | grep` reader is gone, the helper runs before the export),
  `tests/test_techlead.py` pipeline test needles updated (helper-from-`$REPO`, global lock, `8>&- 9>&-`, export check +
  `"error":"export"` exit, and a negative: no `--root`/`$BOX`/`$WT` helper path in the script).
- `CLAUDE.md` §4 CI bullet and `.github/pull_request_template.md` (one checklist line) tell contributors to add
  `tests/ci_shard.d/<issue>-<slug>.txt` instead of editing `tests/ci_shard.txt`.

**Evidence.**
- Shard today (`origin/main` 935b419): 51 entries; `python3 tools/dev/shard_list.py --print | wc -l` → 52 (= 51 + this
  stream's drop-in); `--git "$PWD"` over the committed tree gives the identical list; on `main`'s tree (no drop-in dir)
  the helper's output is byte-identical to `grep -vE '^\s*(#|$)' tests/ci_shard.txt`.
- Trusted-side property, demonstrated on a scratch worktree: with `tests/ci_shard.txt` replaced in the *checkout* by a
  symlink to `/etc/passwd` and a drop-in by a symlink to `/etc/hostname` (uncommitted — what a sandboxed step could do to
  its box), `--git WT` still returned the committed list (blob content); a *committed* symlink drop-in is skipped (mode
  120000 is not a regular blob); a committed drop-in containing `tests/test_x.py -k nothing` / `../etc/passwd` → exit 3,
  whole list refused; a drop-in named `bad name.txt` → exit 3; `tests/ci_shard.txt` deleted at HEAD → exit 3; helper
  missing at `$REPO` → python exit 2 → the script's REFUSED path (`BADSHARD=" (refused by shard_list.py rc=2 …)"`, `RC=3`).
- Before/after, two synthetic PRs each sharding one test, merged into `main` in either order (scratch repo seeded with
  the real `tests/ci_shard.txt`, README and helper):
  ```
  # BEFORE: both append to tests/ci_shard.txt
  git switch -c old-a main; echo tests/test_a.py >> tests/ci_shard.txt; git commit -am A
  git switch -c old-b main; echo tests/test_b.py >> tests/ci_shard.txt; git commit -am B
  main + old-a + old-b  -> CONFLICT (tests/ci_shard.txt)      main + old-b + old-a -> CONFLICT (tests/ci_shard.txt)
  # AFTER: each adds tests/ci_shard.d/<n>-<slug>.txt
  git switch -c new-a main; echo tests/test_a.py > tests/ci_shard.d/501-a.txt; git add -A; git commit -m A
  git switch -c new-b main; echo tests/test_b.py > tests/ci_shard.d/502-b.txt; git add -A; git commit -m B
  main + new-a + new-b  -> clean, shard tail: tests/test_a.py tests/test_b.py
  main + new-b + new-a  -> clean, shard tail: tests/test_a.py tests/test_b.py   (same list either order: sha256 a4e6c1d6490d…)
  ```
- Gates (final head): `tests/test_shard_list.py` 23 passed; `tests/test_techlead.py` 29 passed (52 in 1.1 s together);
  `check_portable_paths.py` ok (2815 paths); `sync_plugin.py --check` in sync (no `src/` touched); `validate_plugin.py`
  PASS. `session_ci.sh` itself was NOT run end-to-end here (needs root + `unshare`/`setpriv` prerequisites and a fetched
  PR ref; the tech-lead session keeps running MAIN's copy against this PR and switches to this copy after merge) — the
  shard-read block was executed verbatim in `bash` against a real worktree instead (53 entries incl. a demo drop-in, first
  = `tests/test_schema_gate.py`, `BADSHARD` empty).

**Cleanup round (four-angle `/simplify` + altitude review, same session, before the PR opened).** Applied: the CLI
lost the unused `--rev`; drop-ins are sorted once (in `merge()`), dedup is `dict.fromkeys`; ONE `git ls-tree` call
lists base + drop-ins; both readers now share one selection policy (a `.txt`/base that is not a regular file is
*refused* by both — the git reader used to skip a committed symlink silently while the tree reader followed it — and
both decode with U+FFFD replacement, so an undecodable byte is a refused entry, never a traceback), pinned by a new
tmp-repo parity test (23 tests now); the `session_ci.sh` needles live only in `tests/test_techlead.py` and were reduced
to invariant tokens (`global.lock` + `flock -w`, `8>&- 9>&-`, the export witnesses, `"error":"export"`, helper-before-
export ordering, negatives for `--root`/`$BOX`/`$WT` copies and the old `git show | grep` reader); `ci.yml` reads the
helper with the same `$(…)` + `mapfile <<<` idiom as the script (no temp file); the altitude finding that mattered most —
*the frozen file itself never said it was frozen* — is fixed at the source: `tests/ci_shard.txt`'s header now says
"FROZEN FOR APPENDS, add `tests/ci_shard.d/<issue>-<slug>.txt`", and `tests/test_shard_list.py` caps the base file at
its current 51 entries (may shrink, never grow) with that message, so an append fails the appender's own test run
instead of conflicting with a stranger later. Declined, with reasons: replacing the retained bash `ENTRY` re-check with
a looser "no leading `-`//, no `..`" invariant (kept character-identical to the helper on purpose: in this script a
second copy that can only be *stricter* than the helper is the acceptable failure direction; loosen both together);
a `fail_setup` function over all five `{"error":…}` exits and closing every fd ≥ 3 structurally in `sandbox()` (both
touch lines outside this territory — good follow-ups for whoever next holds the whole script); folding the base file
into `tests/ci_shard.d/000-core.txt` (contradicts #328's "kept").

**Findings / follow-ups.** `.github/prompts/worker.md` (a prompt an unattended agent executes verbatim, not a workflow)
got the one-line switch to `pytest -q -- $(python3 tools/dev/shard_list.py --print)` in this PR — one line outside the
declared territory, stated here and in the PR. The fix-pass text inside `.github/workflows/claude-review.yml:339` still
spells `$(grep -v '^#' tests/ci_shard.txt | xargs)`: dormant under steer #302, fails *quiet* (runs a shrinking subset)
if ever revived — left for a workflow-file PR and filed as a task issue (`Refs #328`) rather than left in prose. A
distinct throwaway uid per sandboxed run stays out of scope (user namespaces), as #329 states.

BRANCH STATE (cam/328-shard-dropins): `tools/dev/shard_list.py` (new), `tools/dev/session_ci.sh` (shard block, global
lock, fatal export, fd hygiene, header), `.github/workflows/ci.yml` (shard step; dispatch-only unchanged),
`tests/ci_shard.d/README` + `tests/ci_shard.d/328-shard-list.txt` (new), `tests/test_shard_list.py` (new),
`tests/test_techlead.py` (needles), `tests/ci_shard.txt` (header freeze notice only — no entry moved), `.github/prompts/worker.md`
(one line), `CLAUDE.md` §4 one bullet sentence, `.github/pull_request_template.md` one line, this record. Gates as above. Shipped when merged; the tech lead exercises the modified `session_ci.sh` live on the next PR
after switching its checkout to the merged `main`.

## Only the tech lead merges; every wave is written into the ledger (steer #342), same session, 2026-08-10

**What happened.** (1) #358 (squash 3a44f6d, shared `cam-karagitz` identity) reached `main` outside the session
pipeline; (2) the wave-12 reports (#374/#375/#377/#379) arrived after their launch had been compacted out of the tech
lead's context and were read as another tech lead's wave for one tick — settled by the sessions' `parent_session_id` +
tag `wave-12`. Every head still got same-tick sandboxed CI + a verdict (#358 post-merge, recorded on the PR).

**What changed.** The two rules now live where every session loads them: `CLAUDE.md` §4 banner — an engineer session
never merges (any label), a merge is only ever a tech-lead session holding same-tick CI + verdict for the exact head,
which is also how the older "a session squash-merges" lines are to be read; `docs/process/AUTONOMY.md` §12c — the same
in the Merge row and the engineer paragraph, and the fan-out row gains the ledger duty (one board-issue comment
`issue → engineer session id → territory` per wave at launch, sessions tagged `wave-<k>`, read back at the start of every
tick before an unfamiliar report is treated as foreign). `.claude/commands/fanout.md` shrinks to pointers: flat
territory rule (no file in common) + one cap sentence, never-merge inside the engineer prompt's existing parenthetical,
ledger-first as step 3 on the board issue (#56). `tests/test_techlead.py::test_engineers_never_merge_and_waves_are_ledgered`
pins invariant tokens in all three files. (/simplify: 4 angles; applied all — right layer, one canonical place,
ledger-first ordering, standalone test, this record trimmed; the unrelated #381 STEERING row split into its own PR.)
Follow-up filed: a `techlead.py wave` subcommand that writes/reads the ledger as a marker so the duty is code, not prose.

**Evidence.** Wave 13 (#359/#294/#348/#376/#267) launched under the new text, ledger comment on #342 (board from the
next wave on); `tests/test_techlead.py` 30 passed.

BRANCH STATE (cam/342-fanout-never-merge): `CLAUDE.md` (banner sentence), `docs/process/AUTONOMY.md` (§12c: 3 edits),
`.claude/commands/fanout.md`, `tests/test_techlead.py` (+1 test), this section. Docs/process only; shipped when merged
through the session pipeline.

## The wave ledger as code (issue #386), same session, 2026-08-10

**What.** `tools/dev/techlead.py wave post --wave <k> --row <issue> <session> '<territory>' … [--kept …] [--tech-lead …]
[--dry-run]` renders ONE board-issue comment for an engineer wave — the human table AUTONOMY §12c names plus one machine
line per engineer, `<!-- wave:<k> issue=<n> session=<id> territory=<paths> -->` — and posts it idempotently
(`comment_once`, keyed by wave + body digest, so a retried tick does not duplicate it while a deliberate take-over
re-post still lands); `--dry-run` prints it offline for pasting through MCP. `wave live` prints the ledgered rows still
in flight — issue open and assigned, or closed by an open PR (`busy_issue_numbers`, the data `brief` already holds) —
`--all` for every asserted row, and `--from-file <comments JSON>` (the list the API / MCP `issue_read` return) is the
token-less cloud form; `brief` shows one "waves in flight" line at a cost of 0–2 calls (the board's newest ≤ 200
comments are read from the tail, whatever the total). ONE grammar: `WAVE_MARK_RE` built from `WAVE_ID`/`SESSION_ID`/
`TERRITORY_MAX`; `render_wave` validates by round trip and refuses an id that would not parse back instead of
ledgering it dead; ids are never truncated. Markers someone quoted or fenced do not count — `coord.unquoted()` is now
the shared policy helper beside the lock markers (whether `standing_locks` adopts it is a follow-up); a marker is a
reconstruction hint, never authorisation. Recognition ("is this report one of mine?") uses all rows regardless of
state; shepherding uses the in-flight subset. `.claude/commands/fanout.md` step 3 and AUTONOMY §12c name the command
and spell out the token-less read-back rule in one sentence.

**Evidence.** `tests/test_techlead.py` 32 passed: `test_wave_ledger_round_trips_and_ignores_quoted_or_fenced_markers`
(round trip, table edits harmless, quoted/fenced ignored, take-over wins, unparseable ids refused, in-flight = assigned
∪ closed-by-open-PR incl. raw API PR dicts) and `test_wave_cli_is_offline_for_dry_run_and_from_file` (subprocess, no
token: dry-run, clean error without traceback, from-file recognition + `--open`). /simplify: 4 angles, all applied
(one `_wave()` dispatcher, argparse-split rows, strict from-file shape, `when` dropped, comment_once, tail read, 1-call
board lookup shared with `hello`, `unquoted` in coord, doc sentence, in-flight rule). /verify: the CLI driven offline
and wave 14 re-ledgered on #56 with markers through the token-less path (dry-run → MCP comment) — see the PR.

BRANCH STATE (cam/386-wave-ledger): `tools/dev/techlead.py` (ledger functions, `wave` subcommand, brief line,
`fetch_board_issue` shared with `hello`), `tools/dev/coord.py` (`unquoted`), `tests/test_techlead.py` (+2 tests),
`.claude/commands/fanout.md`, `docs/process/AUTONOMY.md` (§12c), this section. Process tooling only; shipped when
merged through the session pipeline.

## The loop survives its session: a lease register + a re-armed watchdog (#302 remainder), same session, 2026-08-10

**What.** (1) The LEASE: issue #410's body (`lease.issue` in `.github/autonomy.json`) carries
a visible `` `techlead-lease session=<id> until=<UTC iso>` `` line plus one human line (/verify found that MCP `issue_read` strips
HTML comments from issue bodies — a comment marker would have made every token-less reader see 'no lease' and TAKE). `tools/dev/techlead.py lease renew --me <id>`
judges it — HOLD (mine → renew), TAKE (none / garbled / released / expired → that holder is gone: write it in my name),
STANDBY (another session, unexpired → exit 5, nothing written) — and writes it over the API, or with
`--from-file <issue JSON | -> --dry-run` prints the judged body for MCP `issue_write` (fail closed: no `--from-file`,
no body; a saved object without a `body` key is an error, never "empty → take"). `lease status` is the read-only view;
`brief` shows the lease at 0 extra calls. One grammar (`LEASE_RE`), validity by round trip. (2) The WATCHDOG: instead of a
fixed fresh-session cron (rejected on review — ~12 fresh CCR sessions a day, each a VM + clone + setup + ~15k tokens,
only to print STANDBY, and ~80 dead sessions a week in the owner's list), a ONE-SHOT routine that spawns a fresh session
is re-armed by every acting tick to now + `lease.minutes` (`update_trigger(run_once_at=…)`); it therefore never fires
while a loop lives and fires exactly `lease.minutes` after the last tick of a dead one — takeover latency = the lease
length (100 min), zero standby cost. The lease still earns its keep as the visible register and for the one case the
watchdog cannot judge: a session presumed dead that comes back (it reads STANDBY and yields). (3) `.github/prompts/tick.md`
is the standalone tick prompt: step 0 = one command (`issue_read` → `lease renew --from-file - --dry-run`; exit 5 →
end the turn; else `issue_write` the body, re-read after a TAKE and yield to a same-minute earlier taker, post the
take-over line on the board) + the watchdog push; then picture (incl. wave-ledger read-back), the session-hosted
pipeline, fan-out by reference to `fanout.md`, backlog, build, report; long ticks re-run step 0 before merging or
fanning out. Both routines' stored prompts are stubs pointing at the file, so edits ship by PR.

**Review round (🛑 → fixed).** The independent review found two real holes: a STANDBY fire ended without re-arming the
watchdog (an early fire at the expiry boundary would have left the loop dead), and the backticked marker plus "pipe the
JSON" invited shell command substitution that erased the marker and yielded TAKE over a live holder. Now ONE invariant:
every outcome (hold / take / standby / damaged) prints `ARM_WATCHDOG_AT` = the lease in force + `lease.watchdog_margin_minutes`
(or now + `lease.minutes` when nothing is in force) and tick.md re-arms the watchdog with it before any turn may end;
the marker is a plain `techlead-lease session=… until=…` line with no shell metacharacters; a body that mentions a lease
without a parseable line (or with an impossible timestamp) is DAMAGED — exit 6, repaired, never taken; `none`/`-` are
reserved; `cse_…` ($CLAUDE_CODE_REMOTE_SESSION_ID) and `session_…` spell one holder; a lapsed lease of my own is HOLD;
`--release` hands back only your own lease (a watchdog-fired session does that at the end so the persistent one
reclaims); `coord.unquoted` also drops MCP-escaped `&gt;` quotes; tick.md names the session-id source, the
missing-routine branch, the prerequisites, and re-reads afresh before merges/fan-out/filing on long ticks.

**Evidence.** `tests/test_techlead.py` (`test_loop_lease_decides_hold_take_standby_and_round_trips`,
`test_lease_cli_is_offline_fail_closed_and_always_arms_the_watchdog`) pin the boundary (until − 1 s standby / at until
take), own-lapsed hold, the three watchdog arm rules, quoted/escaped/fenced markers, damaged bodies, reserved ids,
release rules, fail-closed dry-run; every path also driven by hand offline. /simplify: 4 angles,
applied all but the optional config nesting (kept `lease.{issue,minutes}` top-level; the worker's label lease is a
different substrate). After merge (recorded on #302): the lease written on #410 in this session's name through the
token-less path; the hourly routine's prompt replaced by the stub; the watchdog routine created and armed.

Second review 🟡 → also applied: empty saved input is refused (never "no lease"), the damage hint reads the RAW body (a lease
wholly inside a fence/quote is DAMAGED, not takeable), the margin is clamped ≥ 2 min, a watchdog-fired session re-arms once
more after its release, and the take-over board line skips routine hand-backs. Tests: `tests/test_techlead.py` +
`tests/test_coord.py` 45 passed.

BRANCH STATE (cam/302-loop-lease): `tools/dev/techlead.py` (lease grammar/functions/CLI, shared `body_of`/`load_saved`,
brief line, config default), `tools/dev/coord.py` (`unquoted` drops MCP-escaped quotes), `.github/autonomy.json` (+`lease`),
`.github/prompts/tick.md` (new), `tests/test_techlead.py` (+2), `docs/process/AUTONOMY.md` (§12c row), this section.
Process tooling; shipped when merged.
