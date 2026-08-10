# How work flows in tekton — humans steer, coding sessions are the tech leads, bots carry the pipeline

This is the operating system of the repository: who decides what gets built, where that is
written down, and how a change travels from an idea to `main` with nobody clicking anything.
`CLAUDE.md` §4 is the terse, always-loaded version every coding session obeys; this page is the
full reference with the reasoning. It was mandated by the people who own the project (steer
[#54](https://github.com/ckaragitz/tekton/issues/54)) after an earlier process left humans
writing the tickets: *"you (CC) should be figuring out what needs to be done based on the
overall project goals … You are our tech leads … you are in charge of the task list and reqs and
stories … we can steer you."*

## 1. Principles

1. **Sessions own the backlog.** Requirements, stories, tasks, priorities, retirement — written
   by the coding sessions (interactive or unattended) from the program goals. Humans never have
   to file a ticket, assign, review, merge, or close anything.
2. **Humans steer, and steers are sacred.** Anything a human volunteers — a want, an opinion, a
   priority call, a correction — is obeyed, **logged verbatim the moment it is heard**, and traced
   to the issues it produced. A steer that conflicts with a hard rule (`CLAUDE.md` §1) is not
   silently dropped either: it becomes a `needs-decision` issue that says so.
3. **No state in anyone's head.** People switch laptops off; sessions end mid-sentence and resume
   as strangers. Everything lives in GitHub — issues, labels, PRs, comments, the records in
   `docs/inbox/` — and every automation runs server-side in Actions. A session that vanishes
   loses nothing but its own scrollback.
4. **The pipeline has no silent human dead-ends.** From pushed code to merged PR, every state
   either advances by itself or lands, labelled, in the one place humans look (the board's
   *Waiting on a human* section) with the reason.
5. **Deterministic where possible, judgement where needed, bounded always.** Queue order, board,
   hygiene, merge rules are plain code on the built-in `GITHUB_TOKEN`. Triage, planning,
   implementing, reviewing use a model — with per-run caps, WIP limits, a daily budget, a pause
   switch, and an audit trail (planning notes, verdict markers).

## 2. Roles

| Role | Who | Does | Never has to |
|---|---|---|---|
| **Steerer** | any human on the repo (owner, Chase, …) | says what they want, in plain words, wherever convenient; answers `needs-decision` questions; does the few physical things in §10 | write tickets, groom, assign, review, merge, close, keep a session alive |
| **Tech lead** | every coding session — yours, anyone's, and the scheduled `techlead` planner — following one charter (`.github/prompts/techlead.md`) | logs steers, triages them into requirements, keeps the queue stocked and ordered from `docs/PROGRAM.md`, retires the obsolete, decides what the unattended worker may take, leaves planning notes — **and then builds** (below): tech lead and engineer are the same session (steer #58) | wait for permission to plan; stop at planning |
| **Engineer** | every coding session (the same one that just tech-led), the scheduled `worker` (`.github/prompts/worker.md`), and any *engineer sessions* a tech-lead session starts | claims one issue, branches, implements per `CLAUDE.md`, opens the PR | shepherd the PR afterwards — the bots do |
| **Hands** | subagents inside a session; extra cloud (CCR) sessions a tech-lead session starts and talks to (`/fanout`) | subagents: sub-tasks of the session's own issue, integrated into its one PR; engineer sessions: one whole issue each, claimed with `/claim`, same protocol as anyone | hold state — everything they do surfaces as claims, branches, PRs, comments |
| **Pipeline bots** | `coord`, `CI`, `claude-review`, `automerge`, `board` (GitHub Actions) | claim enforcement, intake, review + bounded auto-fix, auto-ready, merge, issue closing, re-queueing, the board | — |
| **Orchestrator (legacy name)** | was a rotating human; now = the tech-lead loop above | the only orchestration left to humans is listed in §10 | — |

## 3. Artifacts — where the truth lives

| Artifact | What it is | Who writes it | Loaded into sessions |
|---|---|---|---|
| `docs/PROGRAM.md` | program goals + current objectives, ordered — what tech leads plan *from* | sessions (via PR); humans steer it | yes — imported by `CLAUDE.md` |
| `docs/STEERING.md` | ledger of standing human steers (rules/preferences) with IDs | tech leads, one row per standing steer | yes — imported by `CLAUDE.md` |
| **Steer issues** (label `steer` / `intake`) | each human input, verbatim, attributed, timestamped; comments = follow-up steers | whoever hears it (session, `/steer`, the form, `coord` intake) | via the brief / board |
| **Task issues** | the backlog: title = checkable DONE; body = Why / DONE / Territory / Evidence / Context; labels = priority + area + state + provenance | tech leads (`from-steer`, `planned`), sessions mid-work (follow-ups) | via `/next`, brief |
| **The board** (issue labelled `board`, pinned) | rendered live view: in progress · in review + exact merge blocker · next up · waiting on a human · steers · done · health | `board.yml` → `tools/dev/techlead.py board`, hourly + on events | `/board`, SessionStart banner |
| Planning notes | one comment per planner pass on the board issue: what was triaged/filed/closed and why | the tech lead that ran the pass | — |
| `docs/inbox/<stream>.md` | per-workstream record with evidence and `BRANCH STATE` | the engineer | on demand |
| `TRACKER.md`, `KNOWLEDGE.md` | curated roadmap summary; institutional memory (hot files) | tech leads via small PRs | `KNOWLEDGE.md` on demand |
| `.github/autonomy.json` | the knobs (§11) | anyone via PR (bot-mergeable) | read at run time by every bot |

## 4. The loop

```mermaid
flowchart TD
    H([human says something]) -->|session hears it: /steer<br/>form · /steer comment · free-form issue| S[steer / intake issue<br/>verbatim, attributed]
    S -->|labeled → techlead.yml now<br/>or ≤ 6 h schedule<br/>or any session: /techlead| T{{tech-lead pass<br/>charter: .github/prompts/techlead.md}}
    G[(docs/PROGRAM.md<br/>docs/STEERING.md)] --> T
    T -->|files / grooms| Q[task issues<br/>ready · P* · area:* · auto?]
    T -->|standing guidance| G
    T -->|planning note| B
    Q -->|/next or claim<br/>human-started session| E1[engineer session]
    Q -->|worker.yml every 2 h<br/>ready + auto, WIP ≤ 2| E2[unattended worker]
    E1 --> PR[PR: Closes #n]
    E2 --> PR
    PR --> CI[CI] --> R{{claude-review<br/>verdict marker per SHA}}
    R -->|changes or CI red:<br/>session pushes first;<br/>after 15 quiet min automerge<br/>dispatches the bot fix pass| F[fix pushes] --> CI
    R -->|approve / nits + green| M[automerge: squash, delete branch,<br/>close linked issues]
    R -->|budget exhausted| K[bot-stuck → sweep re-queues issue<br/>ready + retry, same branch] --> Q
    PR -->|draft, green, approved,<br/>quiet ≥ 90 min| RD[auto-marked ready] --> M
    PR -->|conflicts| RB[worker rebase mode] --> CI
    M --> B[[📋 board re-renders]]
    Q --> B
    S --> B
```

Timings (CI ≈ 1–2 min, AI review ≈ 5–15 min per push): **fixing is single-owner** — on red CI or
a 🛑 verdict the authoring session (subscribed to its PR) has `fix_grace_minutes` (15) after the
last signal to push; only then does `automerge` dispatch one bot fix pass for the current head
(the same path carries a PR whose session or laptop went away; worst case ≈ grace + one 30-min
sweep). A missing review verdict is re-requested after 20 min and parked `bot-stuck` after 4 h;
a stuck PR's issue is re-queued after 24 quiet hours; an untouched draft is nudged at 5 days and
closed (branch kept, issue re-queued) at 14; a dead worker lease is freed after 3 h; an abandoned
human claim (no PR, no activity) after 72 h.

## 5. How humans steer (pick whichever is at hand)

| Channel | How | What happens |
|---|---|---|
| Talk to your session | just say it | the session runs `/steer` → a `steer` issue exists before it acts; it obeys immediately and/or files derived work |
| GitHub, one box | *Issues → New → 🧭 Steer the tech leads* (works on the phone app) | issue lands with label `steer` → planner triggered within a minute |
| Any issue or PR thread | comment `/steer <what you want>` | `coord` copies it verbatim into a new `steer` issue, links back, wakes the planner |
| Just file an issue any old way | free-form text, no template | `coord` labels it `intake` (no DONE section = human input, not a task) → same triage |
| A document | drop a markdown file in `docs/requirements/` via PR (legacy drop-box) | `requirements.yml` files a `ready` + `from-requirement` issue on merge |
| Emergency brake | put label `bots-paused` on the board issue | planner + worker idle; reviews/merges continue; remove the label to resume |

What comes back: a comment on the steer restating it and linking every issue it became; the
issues carry `from-steer` and `Refs #<steer>`; standing guidance gets a row in `docs/STEERING.md`
(and thereby into every future session's context); the board shows the steer until triaged.
Disagree with the reading? Reply on the steer — replies are steers.

## 6. Session protocol (human-started sessions) — the short form is `CLAUDE.md` §4

Every session, in this order, before writing code: (1) `git fetch` / start from `main`;
(2) service your own open PRs (red CI, 🛑 review, `bot-stuck`); (3) **log any steer** your human
gave you (`/steer`); (4) if there are untriaged steers, or `ready & unassigned` is below the
floor, run a tech-lead pass (`/techlead`, ≤ 10 min, bounded by the charter); (5) resume your
assigned issue or take the head of the queue (`/next`); claim → branch from `main` → push early →
draft PR with `Closes #n` — the tech lead builds, in the same session; (6) more independent
ready issues than one session can hold? `/fanout`: start engineer sessions (cloud/CCR, one issue
each, they `/claim` and follow this same protocol; you check on and message them) or use
subagents as hands for pieces of your own issue — while you keep building yours. When you stop
— for an hour or forever — push, and make the PR body or the record say where things stand. The bots take the PR the rest of the way: review, bounded
fixes, auto-ready after 90 quiet minutes if green and approved, squash-merge, issue closed, board
updated. If it cannot be finished automatically it is re-queued with your notes for the next
session, not left for a human to notice.

## 7. Labels and states

| Label | Meaning | Set by |
|---|---|---|
| `steer` / `intake` | human input awaiting triage (verbatim) / free-form human issue | form, `/steer`, sessions / `coord` |
| `triaged` | steer processed; derived issues linked | tech lead |
| `from-steer` · `planned` · `from-requirement` | provenance of a task issue | tech lead / `requirements.yml` |
| `ready` | doable now from a fresh clone; unassigned = free (`/next` hands out the head) | tech lead |
| `P0` `P1` `P2` · `area:*` · `good-first-pick` · `hot-file` · `epic` | priority · subsystem · onboarding-friendly · serialized file · parent of tasks | tech lead |
| `blocked` · `needs-viewer` · `needs-revit-desktop` · `owner-machine` · `needs-decision` | gated on something/someone physical (§10) — never in the queue | tech lead |
| `auto` | cleared for the unattended worker (criteria in the charter §4) | tech lead |
| `bot-working` | leased by the worker right now (yields to a human `/claim`) | `worker.yml` |
| `retry` | re-queued after a stuck/stale attempt: continue the named branch | board sweep |
| `bot-stuck` (PR) | bots exhausted the fix budget or cannot get a verdict; issue will be re-queued | `claude-review` / `automerge` |
| `needs-rebase` (PR) · `duplicate-pr` (PR) · `stale` (PR) | conflicts, rebase job dispatched · second PR for one issue, older wins · untouched draft | `automerge` / sweep |
| `session-merge` (PR) | a workflow-file PR that already has a ✅/🟡 verdict for its exact head + green CI, which the Actions token may not merge: the next coding session (preferably not the author's) re-checks both, reads the diff, and squash-merges with its own credentials | `automerge` |
| `needs-human` (PR) | GitHub itself refused the merge, or no independent verdict could be produced for a workflow-file PR (a non-author collaborator applies `merge-when-green`) | `automerge` |
| `wip` · `do-not-merge` · `merge-when-green` (PR) | hold a draft from auto-ready · hold anything · human substitute for the AI verdict (non-author) | humans / sessions |
| `needs-issue` · `overlap` · `stacked` (PR) | no `Closes #n` · issue held by someone else or rival PR · based on another PR's branch | `coord` |
| `board` · `tracking` · `bots-paused` | the board issue · context-only issues · pause switch (on the board issue) | system / humans |

## 8. The bots

| Workflow | Runs on | Token | Does |
|---|---|---|---|
| `coord.yml` | comments, issue open/assign, PR open/edit, hourly | built-in | `/claim` `/release` `/next` `/steer`; one holder per issue; intake labelling + duplicate hints; PR↔issue link/overlap/stacked checks; stacked-PR rescue; orphan-branch draft PRs; 72 h stale-claim reaper |
| `board.yml` | every 20 min; issues/PRs opening, closing, becoming ready; dispatched by automerge/planner/worker after they change state | built-in | hygiene sweep (re-queue stuck, free dead leases, nudge/close stale drafts) then re-render + pin the board |
| `CI` (`ci.yml`) | every PR push, `main`, dispatch | built-in | portable paths, plugin drift, plugin structure, fast test shard (py3.11 + 3.12) |
| `claude-review.yml` | every PR push; dispatch `mode=review` (re-request) / `mode=fix` (from automerge, after the grace) | Claude | review → verdict marker per head SHA (rescue pass if missing); job `fix` = the bounded fix pass for red CI + 🛑 findings at the current head (budget 3, reset-aware; yields if the branch moved); exhaustion → `bot-stuck` |
| `automerge.yml` | CI/review finishing, labels, every 30 min | built-in (+ optional `AUTOMERGE_TOKEN`) | zero-check CI dispatch; review re-request; quiet-draft auto-ready; conflict → rebase dispatch; squash-merge; close linked issues; duplicate parking; `session-merge` labelling for what only a session may merge |
| `techlead.yml` | every 6 h, on `steer`/`intake` labels, dispatch | Claude | the tech-lead pass (§4 of the charter): triage, groom, replenish, `auto` marking, planning note; ≤ 5 new issues/run; may open one docs PR |
| `worker.yml` | every 2 h, dispatch (also `mode=rebase` from automerge) | Claude | pick (deterministic) → lease → implement per `CLAUDE.md` → PR `Closes #n`; WIP ≤ 2 bot PRs, ≤ 4 runs/day |
| `requirements.yml` | push to `main` under `docs/requirements/` | built-in | legacy drop-box: one issue per requirement file |
| `claude.yml` | `@claude` mentions | Claude | answer / push a change on request |

"Claude" token = the repo secret `CLAUDE_CODE_OAUTH_TOKEN` (or `ANTHROPIC_API_KEY`) — the
owner's personal choice for this personal repo. Without it the model-backed rows are skipped or
red by design and the loop degrades gracefully: humans' own sessions do the planning at session
start and shepherd their PRs (per-PR Auto-fix in cloud sessions), while `coord`, `board`, `CI`
and `automerge`'s label path keep working on the built-in token.

## 9. What the bots will and will not do on their own

They will: file, edit, relabel, and close issues; comment; open PRs; push commits to PR branches
(fixes, conflict merges); mark quiet drafts ready; squash-merge green + approved PRs; delete
merged branches; close linked issues; re-queue stuck work; pin and rewrite the board issue.

They will not: force-push; push to `main`; merge anything red, unreviewed, conflicting, or held;
edit `.github/workflows/**` in unattended runs; strip a gate label to make work look ready; assign
a human; act on a steer that breaks a hard rule; run the full test suite; touch anything under
the git-ignored third-party dirs; certify a file as loading in Revit (only the ledger does).

Trust model of the model-backed runs: their inputs are this private repository's files and
issues/comments written by its collaborators; the worker's tool surface is deliberately the same
a human-started session has (it must run the stream's tests and tools), the planner's is
issue/label/docs-only, the reviewer's is read + comment. None holds a secret beyond its own
GitHub/Claude token, and everything they push still passes CI + review + the merge gate. Actions
are referenced by major-version tag (`@v1`, `@v6`), the convention this repo already ran on;
pinning them to commit SHAs is a filed hardening task, not a blocker.

## 10. What still needs a human, and why

This is the complete list. Everything on it shows up in the board's *Waiting on a human* section
with the reason; nothing else should ever wait on a person — if it does, that is a bug in this
system (file it, `area:process`).

| Needs a person | Why it cannot be automated | How it is surfaced | Optional way to remove it |
|---|---|---|---|
| ~~Merging a PR that changes `.github/workflows/**`~~ — **not a human's job any more** (steer #61) | GitHub forbids the *Actions token* from merging workflow changes, but a coding session acts under a person's GitHub identity and may | PR labelled `session-merge` + comment; board *In review* lane; SessionStart banner "MERGE FIRST" | any session, at session start: CI green + verdict stands → `gh pr merge <n> --squash` (or MCP `merge_pull_request`). Hands-free alternative: owner adds a fine-grained PAT (contents + pull requests + workflows: write) as secret `AUTOMERGE_TOKEN`. Logic lives in `tools/dev/*.py` + prompts + `autonomy.json` precisely so workflow files rarely change. |
| Reviewing a PR that changes `claude-review.yml` itself | its own `pull_request` review run refuses a copy that differs from `main`'s (observed on #57) | `automerge` re-requests the review from **`main`'s reviewer**, which judges it like any diff; the verdict is required before `session-merge` is offered (#88) | if even that yields no verdict within the re-request window: `needs-human` = a collaborator other than the author applies `merge-when-green`; keep reviewer edits in tiny dedicated PRs |
| `needs-decision` issues | money, legal/counsel (C1/C4/C5, trademark), going public, product direction calls the steerers reserved | issue label; board; planning note | answer in a comment (it is a steer); the tech leads proceed |
| Viewer certification uploads (`needs-viewer`) | Autodesk's viewer needs an interactive login; rule 4 makes it the arbiter | sessions STAGE batches (`probe_batch.py stage`) and stop at READY; board lists them | none by design (no APS — rule 7) |
| Desktop-Revit checks (`needs-revit-desktop`) | needs a licensed desktop install a bot may not touch (rule 2) | label; board | none by design |
| `owner-machine` work | needs the quarantined `samples/` corpus that must never leave that machine (rule 3/6) | label; board | run a session on that machine; it follows the same protocol |
| Keeping the lights on | the Claude token expires yearly; Actions minutes and model usage are billed to the owner | `claude-review` goes red / planner+worker skipped → board Health line | renew `claude setup-token`; tune cadence in `autonomy.json` |
| One-time repo settings | only an admin can tick them | noted here | *Settings → General → Automatically delete head branches*; *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests* (lets `coord` open orphan draft PRs and the bots mark drafts ready); pin the board issue if the token could not |

## 11. Knobs, budgets, and the pause switch

`.github/autonomy.json` is **authoritative and complete** (every key the bots read is in it) and
is read from the default branch at run time. `tools/dev/techlead.py` carries the same values as
`DEFAULTS` only to survive a missing/garbled file, and the two token-only workflows carry them as
`jq` fallbacks for the same reason; `tests/test_techlead.py` fails if any of the three disagree,
so a knob change is one edit to the JSON (plus the test telling you if a fallback needs the same
number). Values at the time of writing:

| Key | Value | Effect |
|---|---|---|
| `planner.ready_floor` / `ready_ceiling` | 4 / 12 | replenish below the floor; never file past the ceiling |
| `planner.max_new_issues_per_run` · `max_turns` | 5 · 60 | per-pass caps |
| `worker.enabled` · `eligible` | true · `auto` | `auto` = only issues the tech lead cleared; `any-ready` = any queue head |
| `worker.wip_limit` · `max_runs_per_day` · `allow_hot_file` · `max_turns` | 2 · 4 · false · 120 | unattended throughput and blast radius |
| `pipeline.quiet_minutes` | 90 | green + approved draft with no commits this long → auto-ready → merge |
| `pipeline.max_fix_attempts` · `fix_grace_minutes` | 3 · 15 | bot fix passes per PR since the last budget reset · how long after the last signal (push / red CI / 🛑 / previous attempt) a live session has the PR to itself before a bot fix pass is dispatched |
| `pipeline.review_wait_minutes` · `review_stuck_minutes` | 20 · 240 | how long automerge waits for a running review before re-requesting it · before parking the PR `bot-stuck` |
| `pipeline.requeue_stuck_after_hours` · `stale_draft_days` · `close_stale_days` · `worker_lease_hours` | 24 · 5 · 14 · 3 | hygiene timings |
| `pause_label` | `bots-paused` | label on the board issue pauses planner + worker |

Rough running cost at defaults (private repo): Actions minutes ≈ automerge 48×/day + coord
24×/day + board ~40×/day, each well under a minute, plus CI per push; model usage ≈ one review
(+ maybe a fix) per push, ≤ 4 planner passes/day (three of them exit early when nothing needs
judgement), ≤ 4 worker runs/day. Halve the crons or lower the caps in `autonomy.json` if the
owner's plan feels it; set `worker.enabled=false` to keep planning but stop unattended coding.

## 12. Changing this system

- Behaviour of the board, queue, pick, sweep, steer log: `tools/dev/techlead.py` /
  `tools/dev/coord.py` (+ `tests/test_techlead.py`, `tests/test_coord.py` in the CI shard) —
  ordinary PRs, bot-mergeable.
- What the planner/worker *do*: `.github/prompts/*.md` — ordinary PRs. Knobs:
  `.github/autonomy.json`.
- Triggers, permissions, secrets: `.github/workflows/*.yml` — the one kind of PR the owner merges
  by hand (or `AUTOMERGE_TOKEN`). Keep YAML thin for exactly this reason.
- The rules sessions follow: `CLAUDE.md` §4 (hot file: tiny PR, `hot-file` issue) and this page.
- Process changes are work like any other: an issue (`area:process`), a record, a PR. Steers about
  the process are steers.

## 12b. Claims at real-time scale (steer #90): pull, lock per session, verify

Nobody assigns work here. Every actor pulls the head of the one shared queue and the lock is taken
at that moment by one central authority (`coord`, server-side) — never by N laptops racing:

| Step | Mechanism |
|---|---|
| take the head | `/next [s=<session>]` comment anywhere → coord picks from `coord.py queue` (ready, unassigned, not gated / in review / worker-leased; P0 → P1 → oldest) |
| lock | GitHub's assignee field + a 🔒 comment carrying `<!-- lock by=… session=… token=… -->` |
| verify before confirming | after assigning, coord settles a few seconds, replays the issue's assignment events (earliest standing assignee) **and** reads the standing locks (earliest wins); only if both are this request does it reply 🎯 — otherwise it undoes the assignment, posts ↩️ + an unlock marker, and tries the next candidate (up to 6) |
| same person, several sessions | `/next` is serialized per login (concurrency group), so two sessions of one login are handled one after the other and get different issues; `/claim s=<tag>` on an issue locked < 2 h ago by another session of the same login is refused (⛔ "your other session holds it"; `take-over` overrides when that session is gone) |
| backstop | `single-holder` evicts any second assignee added by any route within a minute (⛔ naming the holder) |
| session side | `TEKTON_SESSION=<tag>`; `techlead.py claim <n>` = claim-and-verify (exit 4 + holder if not yours); `techlead.py mine` = the resume rule: 🟢 this session's / ⛔ active elsewhere (hands off) / 🟡 idle ≥ 2 h (resumable) |
| unlock | `/release` (posts `<!-- unlock by=… -->`), the 72 h reaper, the stuck-PR re-queue, or the merge closing the issue |
| viewer batch numbers (#285) | the same pattern for the one campaign-global counter sessions used to race on: `/batches <k>` on any issue/PR → coord (one repo-wide concurrency group) reserves `N..N+k-1` above everything on the default branch, every earlier reservation (a marker on the one `batch-registry` issue) and every `batch_<n>.json` any open PR adds, and replies with `probe_batch.py stage --batch N` / `RVT_BATCH_FLOOR=N` (honoured by `probe_batch.next_batch_number()`, so every stager sees it); `coord.py batchjudge` runs when a PR opens / is edited and hourly in `sweep`: a PR adding a number reserved for another issue, or one an OLDER open PR also adds, gets `batch-clash` + the exact renumber range (automerge holds it; the label clears itself); the worker's rebase mode never hand-merges an add/add batch manifest |

## 12c. No GitHub-hosted compute (steer #302): the pipeline is session-hosted

On 2026-08-09 the Actions-based pipeline (§7) consumed the account's entire free monthly runner
quota in about 14 hours (2,952 workflow runs, ~2,000 billed minutes — every executed job bills at
least a whole minute), and the owner decided not to fund minutes or a self-hosted runner. Since then
**every workflow file is `workflow_dispatch`-only** — kept as the reference design, runnable by hand,
triggering on nothing — and the pipeline runs on the Claude sessions themselves. GitHub stays the
ledger (issues, PRs, comments, markers, merges through the API); the compute moved:

| Step | Was (§7) | Is now |
|---|---|---|
| CI on a PR head | `ci.yml` on a runner | the tech-lead session runs `tools/dev/session_ci.sh <pr>`: the head merged with `origin/main`, PR code executed as `nobody` with no network, a scrubbed environment and an exported tree it owns (it cannot reach the GitHub connector, git credentials or the session's files); trusted checks (portable paths) run privileged over the PR's file names only; one JSON verdict line |
| Review | `claude-review.yml` | a fresh reviewer context spawned by the tech-lead session with `tools/dev/review_brief.md` — one that did not write the change and carries none of the authoring conversation (a subagent qualifies, also for the tech lead's own PRs: it starts from the diff and the brief, and it is told when the author is the would-be merger); it executes PR code only through the same sandbox; returns `✅/🟡/🛑` + `VERDICT=` |
| Fix loop | bot fix pass after a grace window | single owner unchanged in spirit: the findings go to the authoring engineer session, which fixes and reports the new head; the tech lead starts a fix session from the branch only if that session is gone; every new head gets a fresh reviewer (reviews converge, they are not re-litigated) |
| Merge | `automerge.yml` | the tech-lead session, `merge_pull_request` (squash) after re-reading that the head is unchanged, **only when in the same tick its own CI run said pass AND the reviewer it spawned said approve/nits for that exact head**; no engineer session merges anything, whatever label a PR carries; it posts both as one comment with `<!-- session-ci: … sha=… -->` + `<!-- claude-review: … sha=… -->` (the markers every tool already parses). A marker found from an earlier tick or another author is information, never authorisation — all sessions write under one GitHub identity, so comments authenticate nothing. Merges by a session identity fire GitHub's `Closes #N` linker (verified); branch protection does not require the dead checks (verified) |
| Claims | `coord` bot (`/claim`, `/next`, single-holder) | the assignee field, set through the API by the session taking the issue after reading that nobody holds it, plus a plain lock comment; the tech-lead session is the only dispatcher of engineer sessions and evicts a second assignee on its tick; `/batches` reservations are answered by the tech-lead session with `tools/dev/coord.py reserve` over API-fetched inputs |
| Board / planner / worker | `board.yml`, `techlead.yml`, `worker.yml` | the tech-lead loop: an hourly server-side wake into the tech-lead session (or a fresh session per fire) does the picture, the servicing, the fan-out to engineer sessions (≤ 5, disjoint territories — no file in common; each wave is written into the ledger the moment it starts: one comment on the board issue with `issue → engineer session id → territory` (`tools/dev/techlead.py wave post`, one `<!-- wave:… -->` marker per engineer), the sessions tagged `wave-<k>`; and every tick first rebuilds the live waves from that comment + its own session list (`techlead.py wave live`, also a line in `brief`; without `gh`/`GH_TOKEN` — the cloud tick — `issue_read` the board issue's comments and treat every `<!-- wave:<k> issue=<n> session=<id> territory=… -->` line that is not inside a `>` quote or a ``` fence as this loop's own engineer, latest line per (wave, issue) wins, so a take-over is re-posted under the same wave id; `wave live --from-file <saved comments JSON>` applies exactly those rules) before treating an unfamiliar engineer report as someone else's — a loop's memory can be compacted away, GitHub's cannot, #342) and the planning pass; the board issue is updated from that tick |

What an **engineer session** does differently: claims by self-assigning; ignores GitHub checks
(there are none, or instantly-failed ones with `runner_id 0` — meaningless either way); runs its gates locally and pastes counts;
after pushing, REPORTS the head SHA to the tech-lead session instead of waiting for bots; fixes on
the same branch when findings come back; and never merges — not its own PR, not anyone's (#342: one
engineer PR reached `main` outside the pipeline under the shared identity; its head was verified after
the fact, which is luck, not process). Everything else in `CLAUDE.md` §4 (one issue = one branch =
one PR from `main`, records, territories, hard rules) is unchanged.

Cost of the model: a shard run is ~3 min of the tech-lead session's CPU per head and a review is one
subagent per head, so merges land in batches per tick rather than continuously; six PRs went through
it on its first afternoon (#299, #297, #304, #306, #293 after five review rounds, #308) with zero
runner minutes and zero human clicks. If minutes ever exist again, re-enable at most a nightly `main`
CI inside the free quota — never per-push / per-comment / per-label triggers.

## 13. Failure modes and how each heals

| Failure | What happens |
|---|---|
| Session dies mid-work, branch pushed, no PR | `coord` sweep opens a draft PR for the orphan branch after 20 min (or lists it on a tracking issue) |
| Session dies with a green, approved draft | `automerge` marks it ready after 90 quiet min and merges |
| Two people claim one issue | `/next` and `/claim` verify first-holder + first-lock before confirming and retry for the loser; `single-holder` removes any later assignee within a minute (⛔ comment) |
| Two sessions of ONE person want the same issue | `/next` serialized per login → different picks; `/claim s=<tag>` refused while another session's lock is < 2 h old; `techlead.py mine` tells a fresh session what is resumable |
| Session dies with a red / 🛑 PR | after `fix_grace_minutes` with no push, automerge dispatches the bot fix pass (≤ 3 attempts, one per sha/attempt); then `bot-stuck` → after 24 h the issue is `ready`+`retry`, unassigned, pointing at the branch; `/next` or the worker continues it with a fresh budget |
| Session and bot both want to fix the same head | cannot happen by construction: bots act only after the grace window and only if the head has not moved; the fix job re-fetches before pushing and yields to a newer head; sessions seeing a `🔧 dispatched` marker for their head let it push |
| Claim abandoned without a PR | 72 h reaper unassigns; issue back in the queue |
| Review run ends without a verdict (turn cap, crash) | rescue pass in the same run; else `automerge` re-requests the review; after 4 h `bot-stuck` |
| PR edits `claude-review.yml` (its own review run refuses modified copies) | `automerge` re-requests the review from `main`'s reviewer; with a ✅/🟡 verdict + green CI it becomes `session-merge`; with none obtainable, `needs-human` (non-author `merge-when-green`) |
| A bot's own check run (cancelled board `render`, coord `pr-check`, …) lands on a PR head | not CI: the merge gate and the board ignore bot job names (`BOT_CHECK_NAMES` / `IGNORED_CHECKS`, pinned by tests) |
| PR branch carries an older copy of `claude-review.yml` than `main` (dispatched review refuses to run) | the re-request comment says so; merging `main` into the branch (any session, or the worker's rebase mode) re-arms the review on the new head |
| Bot merge did not close the linked issue | `automerge` closes linked issues itself after every merge |
| PR conflicts with `main` | `automerge` dispatches the worker's rebase mode; result re-reviewed and merged |
| Two PRs for one issue | newer gets `duplicate-pr`; planner closes the worse one; `coord` warned at open time |
| Two parallel PRs stage viewer batches under the same numbers (both took "highest local + 1" from the same `main`) | prevented by `/batches <k>` reservations (+ `RVT_BATCH_FLOOR`); caught anyway by `coord`'s batch judge at PR open/edit and hourly (`batch-clash` + renumber command on the PR that must move — the newer or unreserved one; automerge holds it), and the rebase worker refuses to hand-merge the manifest — so a recorded verdict never names a number that means two files |
| Worker run dies after leasing | lease freed after 3 h by the board sweep |
| Planner files junk | bounded to 5/run; everything it did is in its planning note; humans steer ("stop filing X"), which outranks its judgement next pass; `bots-paused` stops it cold |
| No Claude token / token expired | model rows go red/skipped, visible in board Health; token-free rows keep the queue, claims, board and label-path merges working; sessions plan and shepherd manually |
| GitHub API hiccup in a sweep | every bot action is idempotent (marker comments, labels); the next run converges |
| Actions quota exhausted / no runners (every job `runner_id 0`) | nothing depends on runners any more (§12c): sessions run CI in the sandbox, review, and merge through the API; the workflow files are dispatch-only reference designs |
