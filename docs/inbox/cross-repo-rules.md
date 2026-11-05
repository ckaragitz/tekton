# cross-repo-rules -- the repository's answer to the steerer's cross-repo working rules (#1059)

Stream: one PR, `area:process`, `hot-file` (`CLAUDE.md` §4). Charter: steer #1059.

## What was asked

The steerer keeps a short set of working rules for every repository he works in and wants each
repository's own `CLAUDE.md` to carry the equivalent, because a session that starts from a fresh
clone reads only the repository's copy. #1059 has his words and the six rules in one line each.

## What this repository already did (nothing changed)

| Rule | Already here as |
|---|---|
| Decide who you are first | tech lead vs engineer session / worker / hands (`CLAUDE.md` §4, `docs/process/AUTONOMY.md` §2); engineers never merge (§12c) |
| The queue is Issues; claim before work | assignee + lock comment, verified per session (`AUTONOMY.md` §12b); one issue = one branch = one PR |
| Close only with evidence | merges keyed to an exact head SHA with same-tick CI and an independent verdict |
| One record per stream | `docs/inbox/<stream>.md` or a fragment, ending in `BRANCH STATE` (`docs/inbox/README.md`) |
| Read the state on entry | the session start protocol, the board (#56), the two imported files |

## What was missing, and what this PR adds

1. **A mapping block at the end of `CLAUDE.md` §4** (31 lines): the vocabulary both ways, plus the
   four rules below. It says it is a mapping, and that the text above it wins.
2. **Plans:** `docs/plans/README.md`. The issue stays the charter; a longer plan is
   `docs/plans/<issue>-<slug>.md` on the branch, linked from the issue.
3. **Archive:** `docs/archive/README.md` with the rule, an empty table, and what is not archived
   on purpose.
4. **A date on the objectives:** `docs/PROGRAM.md` "Current objectives" now says *as of
   2026-08-11*, which is what `git blame` gives for the newest line of that list, and carries a
   14-day tripwire.
5. **Say what shipped:** one bullet in the mapping block.
6. **The standing row** S-2026-10-08-a in `docs/STEERING.md`.

## Decisions taken, with the reason

* **No new state file.** The board answers what is running, `docs/PROGRAM.md` what is aimed at,
  `CLAUDE.md` §5 where things stand. A fourth file would be a second copy to keep true.
* **`TRACKER.md` stays.** Nothing opens it by program (`git grep` over `tools/`, `tests/`,
  `scripts/`, `.github/`, `.claude/`: prose and status strings only), but `docs/PROGRAM.md` PG5 and
  status strings in `tools/rvt_job.py` and `src/rvt/` cite its P0 gates by name, and the planner
  charter reads its unchecked items. It is not a claim board. It is a hot file, so it is not
  touched here.
* **Ticket-level priority stays with the sessions.** The cross-repo default gives priority labels
  to the owner; steer #805 decided the opposite for this repository. The mapping says so.
* **Records are not archived.** `docs/inbox/README.md` says none are migrated, and code, tests and
  `KNOWLEDGE.md` cite them by path.
* **One issue, not two.** The process files a task issue per steer (`Refs #<steer>`). This change
  is the steer's only derived work, so the PR closes #1059 directly.

## Open questions (for the tech-lead loop, not answered here)

1. `TRACKER.md` has not been edited since the initial import on 2026-08-07 (26 unchecked boxes,
   35 checked) while `CLAUDE.md` §4 says the loop keeps it current by small PRs. Bring its roadmap
   half up to date, or keep only the gate definitions and archive the rest: a `hot-file` task.
2. The objectives list is dated 2026-08-11, so the new tripwire fires for the next tech-lead
   session. That is intended: the list has not been reconciled with the board since.
3. `"plansDirectory": "docs/plans"` is not in `.claude/settings.json`. A change to that file is
   the owner's to accept, so it is not in this PR; `docs/plans/README.md` says what to do meanwhile.

## Evidence

* `python3 tools/dev/check_portable_paths.py` -> `ok: 3575 tracked paths are portable`.
* `.venv/bin/python -m pytest tests/test_records_layout.py tests/test_techlead.py tests/test_coord.py tests/test_shard_list.py tests/test_pyproject_extras.py -q`
  -> `85 passed` (the tests that open `CLAUDE.md`, `docs/PROGRAM.md` or the records tree).
* No file under `src/`, `tools/`, `skills/` or `plugin/` changed, so the plugin gates do not apply.

## BRANCH STATE

* Branch `cam-ant/1059-cross-repo-rules`, from `origin/main` at `92f8253`.
* Files written: `CLAUDE.md` (+31, §4 only), `docs/PROGRAM.md` (+5), `docs/STEERING.md` (+1 row),
  `docs/plans/README.md` (new), `docs/archive/README.md` (new), this record.
* Gates: portable paths ok; 85 passed (the five test files above). The session CI
  (`tools/dev/session_ci.sh`) and the independent review were NOT run by this session.
* Nothing staged for a viewer; no output files; nothing to rebuild.
* Not merged by its author: it waits for a tech-lead session's CI and verdict on its head SHA.
