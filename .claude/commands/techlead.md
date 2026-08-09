---
description: Run a tech-lead planning pass now (triage steers/intake into issues, replenish the ready queue from docs/PROGRAM.md, groom labels) — same charter the scheduled planner follows
argument-hint: "[optional focus, e.g. 'only triage steer #61']"
---

Run one tech-lead pass, following `.github/prompts/techlead.md` step by step. Focus (optional): $ARGUMENTS

1. Get the live brief: `python3 tools/dev/techlead.py brief` (needs `gh` auth or `GH_TOKEN`; in a cloud session without either, build the same picture with the GitHub MCP tools: open issues labelled `steer`/`intake` without `triaged`, open `ready` unassigned issues, open PRs and their labels).
2. Read `docs/PROGRAM.md`, `docs/STEERING.md`, and skim `TRACKER.md` + the recently touched `docs/inbox/` records the brief lists.
3. Do the pass: triage every untriaged steer/intake (restate → file derived task issues with `Refs #<steer>` + `from-steer` → record standing guidance in `docs/STEERING.md` on your branch → label the steer `triaged`), groom labels/duplicates/obsolete issues, replenish the queue to the floor from the goals (never past the ceiling or the per-run cap in `.github/autonomy.json`), set/clear `auto` on ready issues per the charter's criteria.
4. Leave the planning note as ONE comment on the board issue (label `board`), ≤ 12 lines, numbers and links only.

Limits from the charter apply to you exactly as to the bot: search before filing, no code edits in this pass, never assign a human, never strip a gate label to make something look ready, never let a steer override CLAUDE.md §1 (file `needs-decision` instead). When done, summarise for your human in three lines what changed on GitHub.
