# pipeline-automation — close the last gaps between "PR opened" and "merged" and automate requirement distribution

Issue: #48. Session: owner-directed cloud session, 2026-08-09.

## What was built

**A. Merge-pipeline dead-end fix (observed live on PR #45 the same day):**
a PR head pushed via an API/app token got zero CI check runs; `automerge`
refused ("no checks exist for `a653031`") and then could only comment — the
PR sat until a human (this session) pushed a merge commit by hand.

- `ci.yml`: `workflow_dispatch` added, so CI can be started on any ref.
- `automerge.yml`: `actions: write`; on a zero-check head it now verifies the
  branch tip still equals the PR head SHA, dispatches **CI** on the branch
  (once per SHA, guarded by the `<!-- automerge:ci-dispatch-<sha> -->` comment
  marker), and only falls back to the old "push a commit" comment when the
  dispatch itself fails. Every other refusal path is unchanged.

**B. Requirements distribution with no human routing** (the repo's ticketing
system stays GitHub Issues; what was manual was intake and dispatch):

- `requirements.yml` (new, token-free): `docs/requirements/*.md` merged to
  `main` → one issue per file, labels = `ready` + `from-requirement` + front
  matter, deduped forever by a `<!-- requirement-file: <path> -->` body
  marker. `auto: claude` in front matter mentions `@claude` in the issue so
  `claude.yml` implements it end-to-end (needs the Anthropic secret).
  `README.md`/`TEMPLATE.md` document the format and are excluded from intake.
- `coord.yml` claim job: **`/next`** — assigns the commenter the
  highest-priority (P0 > P1 > rest), oldest, unassigned `ready` issue.
  Race between two `/next`s resolves via the existing single-holder guard.
- `coord.yml` sweep: **stale-claim reaper** — an issue held 72 h+ with no
  open PR closing it (per `coord.py rivals`, so drafts count as alive) and
  no activity is unassigned back to the queue; `needs-viewer`,
  `needs-revit-desktop`, `owner-machine` are exempt. Sweep now checks out
  `tools/dev` (sparse) for this.
- `tools/dev/coord.py`: new `reqfile` subcommand — stdlib-only front-matter
  parser (title / labels / auto; heading, then filename fallback; malformed
  front matter degrades to body, never an error).
- CLAUDE.md §4: documents `/next`, the drop-box, the reaper, and the
  zero-check CI dispatch.

## Evidence

- `tests/test_coord.py`: 7 existing + 4 new (`reqfile` front matter/labels,
  heading + filename fallbacks, malformed-front-matter degradation,
  mid-document `---` rule not treated as front matter, CLI) = **11 passed**.
- Workflow YAML parses clean (PyYAML load of all 6 files).
- `tools/dev/check_portable_paths.py` ok; `tools/sync_plugin.py --check`
  clean; `plugin/scripts/validate_plugin.py` PASS (23 assertions). No
  `src/`/`skills/` files touched.

## What is deliberately NOT automated here

- Adding the `CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_API_KEY` secret and
  installing the Claude GitHub App: owner-only, cannot be done from a
  session; without it `claude-review`/`ci-autofix`/`claude` stay red by
  design and only the `merge-when-green` label path merges.
- Repo settings: *auto-delete head branches* and *allow Actions to create
  PRs* (both Settings checkboxes; the sweep's fallback paths cover their
  absence).
- Writing the requirement itself — that is the one human step by design.

## Open questions

- Should `/next` respect an `area:` preference (e.g. `/next area:famgen`)?
  Left out until someone asks.
- Reaper window (72 h) is a guess; tune from real queue behaviour.

## BRANCH STATE

- Branch: `claude/pr-monitoring-merge-kvzh9t`, issue #48, single PR.
- Files: `.github/workflows/{ci,automerge,coord,requirements}.yml`,
  `tools/dev/coord.py`, `tests/test_coord.py`,
  `docs/requirements/{README,TEMPLATE}.md`, `CLAUDE.md`, this record.
- Gates: test_coord 11 passed; portable paths ok; sync --check clean;
  validate_plugin PASS; YAML parse ok.
- Staged vs shipped: everything in this branch ships together; nothing
  staged elsewhere. NOTE: PR touches `.github/workflows/**` → bots cannot
  merge it; the owner squash-merges by hand.
