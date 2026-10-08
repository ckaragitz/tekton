# docs/plans/ -- plans that are too long for an issue body (steer #1059)

In this repo **the issue is the charter**: title = the checkable DONE, body = Why / DONE /
Territory / Evidence / Context (`CLAUDE.md` §4). Most work needs nothing more.

A plan goes here when it does not fit that shape: a multi-step design, a probe ladder, anything
a session drafted in plan mode. The rule is the same one the rest of the process follows --
nothing lives only in a session:

* name it `docs/plans/<issue>-<slug>.md` (the issue number first, like a record fragment);
* commit it on the issue's branch and link it from the issue (the claim comment is the usual
  place), so the next session finds it from GitHub;
* keep it current while the work runs: it says *how*, the issue says *who and what*, and
  `KNOWLEDGE.md` says what was decided and why;
* when the issue closes, `git mv` it to `docs/archive/<YYYY-MM>/plans/` in the PR that closes it
  (`docs/archive/README.md`). An open file here means an open issue.

Plan mode writes to a folder outside the repository unless the project setting
`"plansDirectory": "docs/plans"` is present in `.claude/settings.json`. That setting is **not in
the repository yet** (a change to the settings file is the owner's to accept); until it lands,
move a plan-mode file here by hand before you rely on it.
