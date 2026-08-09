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
