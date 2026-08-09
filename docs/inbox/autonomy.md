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

Dogfooded in the same session: steer #54 (verbatim), task #55 (`Refs #54`, `from-steer`,
claimed), board placeholder #56, standing steers S-2026-08-09-a/b recorded.

## Evidence

- `tests/test_techlead.py` — 19 tests (config merge + on-disk config == DEFAULTS; review-state
  parsing incl. budget reset; CI gate == automerge's; PR status lanes in automerge order incl.
  quiet-draft countdown and bot-stuck; classify sections/health/warnings/pause; board render
  completeness + marker wrap + no-op re-render identical + AUTONOMY anchor exists; brief content;
  pick: retry-first/continue-on-existing-PR, auto-only, hot-file skip, WIP, cap, pause,
  disabled, any-ready, dispatch; sweep: requeue after 24 h only, lease release, nudge/close/wip;
  steer spec; queue rules; HTTP client paging/envelopes/comment_once/errors with a fake
  transport; upsert create + skip-identical; CLI `hello` offline + `steer --dry-run`) → **19
  passed**; with `tests/test_coord.py` → **30 passed** (0.6 s). Added to `tests/ci_shard.txt`.
- Board/brief/pick/sweep rendered from a fixture mirroring the live repo on 2026-08-09 (26 open
  issues, PRs #40/#57-59 shapes) — output reviewed by eye (scratch `tl/board.md`).
- `actionlint 1.7.12 -shellcheck` over all nine workflows: **0 errors**; remaining shellcheck
  notes are info-level in pre-existing `coord`/`automerge` lines (SC2013/SC2016/SC2059/SC2034).
  All workflow + issue-form YAML parses; `bash -n` clean on all 35 `run:` blocks.
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
- Gates: 30 stream-local tests green; actionlint 0 errors; portable paths / plugin drift /
  plugin structure clean. Full suite not run (process-only change; nothing under `src/`,
  `plugin/`, `skills/`).
- Shipped vs staged: everything ships with the merge; the workflows go live on `main` only —
  **owner squash-merges this PR by hand** (it changes `.github/workflows/**`). Live artifacts
  already exist: #54 (steer), #55 (task), #56 (board placeholder).
