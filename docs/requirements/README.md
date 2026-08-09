# Requirements drop-box (one intake channel among several)

> **Humans do not need this directory.** The primary way to introduce work is
> to *steer* — tell your session, use the *🧭 Steer* issue form, or comment
> `/steer <text>` anywhere — and the coding sessions (the tech leads here)
> write the requirements and tasks themselves (docs/process/AUTONOMY.md).
> This drop-box remains for the case where a requirement already exists as a
> document — a spec written elsewhere, a session's own decomposition of an
> epic — and should become an issue verbatim on merge.

Drop one markdown file per requirement here (via the normal PR flow); the
moment it merges to `main`, the `requirements` workflow files **one GitHub
issue per file**, labelled `ready` + `from-requirement` + whatever the file's
front matter names. From there the existing machinery takes over: sessions
pull work with `/claim` or `/next`, the `coord` bot enforces one holder per
issue, and the review → auto-fix → automerge pipeline lands the PR.

## File format

```markdown
---
title: Short checkable outcome (optional — else the first `# ` heading is used)
labels: area:engine, P1
auto: claude
---
# Short checkable outcome

What must be true when this is done, with enough context for a session
landing cold: territory (files it may touch), evidence expected, gotchas.
```

- **All front matter is optional** — a bare markdown file with a `# ` heading
  works. Malformed front matter is treated as body text, never an error.
- `labels:` comma-separated; unknown labels are created. Use the existing
  vocabulary where it fits: `P0`/`P1`/`P2`, `area:engine`, `area:plugin`,
  `area:frontdoor`, `area:famgen`, `area:genesis`, `area:docs`,
  `good-first-pick`.
- `auto: claude` makes the filed issue mention `@claude`, so the `claude`
  workflow implements it end-to-end (claim → branch → PR → review → merge)
  with no engineer at all. Requires the repo's Anthropic secret.
- `README.md` and `TEMPLATE.md` are ignored by the intake.

## Rules

- **One file = one issue, forever.** The issue body carries a
  `<!-- requirement-file: ... -->` marker; re-running the workflow never
  duplicates. Editing a file after its issue exists does **not** update the
  issue — discussion and scope changes live on the issue, which is the single
  source of truth once filed.
- Write the title as **the checkable DONE**, not a wish ("famgen: blank-named
  host symbol pairs never emitted", not "improve famgen").
- One requirement per file. If you are tempted to write "and", split it.
- Filename: short kebab-case slug, e.g. `famgen-hostsym-blanks.md`
  (portable-path rules apply — see CLAUDE.md §4).
