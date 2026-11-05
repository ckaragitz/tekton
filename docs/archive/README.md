# docs/archive/ -- history, kept for provenance (steer #1059)

Read nothing here unless an issue, a record or `KNOWLEDGE.md` sends you. Everything below was
true once and has been superseded; it stays in the repository so citations and `git blame` keep
resolving.

**The rule** (`CLAUDE.md` §4): when a change makes a document stop being true, the same PR
`git mv`s it to `docs/archive/<YYYY-MM>/<the same relative path>`, adds one line to the table
below, and fixes the live references to it. Scratch output, logs and duplicate captures are
deleted, not archived.

| Archived | What | Why / superseded by |
|---|---|---|
| (nothing yet) | | |

**Not archived, on purpose:**

* `docs/inbox/**` -- the stream records. They are evidence, cited by path from code, tests,
  `KNOWLEDGE.md` and other records, and `docs/inbox/README.md` says none are migrated.
* Anything a test or a tool opens (`docs/coverage/viewer-certified.json`, `tests/ci_shard.d/`,
  the fixtures under `spec/`, `inputs/`, `usecases/`): that is a contract, not a document.
* `TRACKER.md` -- the P0 gate definitions (G1-G4) that `docs/PROGRAM.md` PG5 and status strings
  in `tools/` and `src/rvt/` cite by name. Its roadmap half has not been edited since the
  initial import (2026-08-07); bringing it up to date or retiring that half is a `hot-file`
  task for the tech-lead loop, not something to do in passing.
* `AGENT_BRIEF.md` -- already says it is superseded and points at `CLAUDE.md`; other documents
  link to it.
