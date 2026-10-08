# docs/plans — open charters and plans only

A plan is the brief for one issue or stream: the owner's words, territory (paths it may write), a checkable DONE, the
gate, the record path, and the issue it answers to. `.claude/settings.json` sets `"plansDirectory": "docs/plans"`, so
plan mode writes here instead of `~/.claude/plans`. Rename the file `<issue>-<slug>.md`, commit it on the issue's
branch, link it from the issue's claim comment, and keep it current. When the issue closes or the stream is abandoned,
`git mv` the plan to `docs/archive/<YYYY-MM>/plans/` in the PR that closes it (`CLAUDE.md` §4). An empty directory here
means nothing is chartered.

The issue says who is doing what; the plan says how; `KNOWLEDGE.md` says what was decided.
