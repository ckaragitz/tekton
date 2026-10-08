# ORCHESTRATOR — the state of tekton, as of 2026-10-08

> Read after `CLAUDE.md` and `KNOWLEDGE.md`. This is the one file that says **what is live, how to ship, and what is
> running right now**. A direct session (`CLAUDE.md` §4) that changes any of those three rewrites the affected section
> and bumps the "as of" date in the title, in a tiny `hot-file` PR. If that date is more than 14 days old, treat this
> file as suspect and fix it before you start your own task.
>
> **Provenance of this first version:** written 2026-10-08 from the repo alone (local `main @ 0c5b6d4`, last commit
> 2026-08-07; `origin` not fetched, GitHub not read). Anything the repo could not prove is marked *unknown, verify*.

## What tekton is (one paragraph)

A pure-Python interoperability engine (`src/rvt/`) that reads, creates, edits, validates and converts Autodesk Revit
`.rvt` / `.rfa` containers without a Revit install, an Autodesk seat or APS, shipped as a Claude Code plugin
(`plugin/`, built into `tekton-plugin.zip`). Technical state of the format work: `CLAUDE.md` §5 and `KNOWLEDGE.md`.

## What is live

| Thing | Where | Notes |
|---|---|---|
| Repo | `github.com/ckaragitz/tekton` (private — `CLAUDE.md` rule 6) | `main` is protected: PR + green checks + squash-merge. |
| Work queue | GitHub Issues on that repo | Protocol in `CLAUDE.md` §4. Pinned "START HERE" is #25. Whether the kind / workflow / priority labels introduced on 2026-10-08 exist on GitHub yet: *unknown, verify* (create the missing ones). |
| Merge machine | `.github/workflows/ci.yml`, `claude-review.yml`, `automerge.yml`, `claude.yml` | CI on every PR and push to `main`; AI review with a bounded auto-fix; automerge squash-merges on green + approve/nits. Needs the Claude GitHub App and the `CLAUDE_CODE_OAUTH_TOKEN` (or `ANTHROPIC_API_KEY`) Actions secret — currently set and working: *unknown, verify*. |
| Product artifact | `tekton-plugin.zip` at the repo root (git-ignored; rebuilt by `tools/sync_plugin.py`) | No hosted service and no deploy target exist in this repo. Who holds which build of the zip: *unknown, verify*. |
| Evaluator kit | `tekton-eval-kit/` (tracked) and `tekton-eval-kit.zip` (git-ignored) | A test kit plus an unpacked plugin copy for outside evaluators. Whether and to whom it was sent: *unknown, verify*. |
| Certification ledger | `docs/coverage/viewer-certified.json`; verdict log `docs/inbox/genesis-audit.md` | Autodesk's reader is the arbiter (`CLAUDE.md` rule 4). |

### P0 shipping gates (deliverability)

Carried over from the archived tracker (`docs/archive/2026-10/TRACKER-2026-10.md` §P0, content dated 2026-08-04, last
edited 2026-08-07). Movement since then: *unknown, verify* against the issues, `docs/coverage/viewer-certified.json`
and `docs/inbox/genesis-audit.md`, then correct this table.

| Gate | Status at archive time | Note |
|---|---|---|
| G1 genesis baseline | achieved (verdict #24, 2026-08-04) | Residuals r1 RENDER gate, r2 walls + loaded family documents combination bug, r3 ~260 Autodesk-authored elements + 4 stragglers, r4 counsel C1 / C4 / C5, r5 trademark clearance. `CLAUDE.md` §5 has the later technical picture. |
| G2 own the identity block | in progress | Mechanism is engineering; what the authoring string may assert is counsel question C1. |
| G3 counsel | open | Agenda: `docs/product/COUNSEL-BRIEF.md` (C1, C4, C5, format posture, trademark, manufacturer EULAs, product terms). Meeting outcome: *unknown, verify*. |
| G4b family-genesis residual | open | Donor `Global/Latest` ADocument in generated `.rfa`; footer token goes to counsel C5. |
| G4 content | open | Own parametric families from manufacturer facts. |

**Until G2–G3 clear and r1 / r2 close: no external delivery.** Every manifest stamps `PROOF-ONLY, NOT-DELIVERABLE`
(a label, never a refusal — `CLAUDE.md` rule 1). The strings "TRACKER gates G2/G3" in code and manifests mean these rows.

## How to ship

1. **Gate** (any session): stream-local tests (`.venv/bin/python -m pytest tests/test_<yours>.py -q`);
   `tools/sync_plugin.py --check` clean and `plugin/scripts/validate_plugin.py` OK after any change under `src/`,
   `tools/`, `skills/` or `plugin/`; `tools/rvt_validate.py` 0 errors and `tools/provenance.py` clean on any produced
   `.rvt` / `.rfa`. Never the full suite concurrently (`docs/inbox/SUITE-COORDINATION.md`). Numbers verbatim in the PR.
2. **Merge**: branch → PR with `Closes #N` and the record → CI + `claude-review` + `automerge` (squash). Nobody commits
   to `main` directly. PRs touching `.github/workflows/**` are merged by the owner by hand.
3. **Build the product**: `.venv/bin/python tools/sync_plugin.py` mirrors sources into `plugin/` and rebuilds
   `tekton-plugin.zip`. There is no deploy step; "shipped" means a rebuilt zip handed to someone, and nothing is
   deliverable externally while the P0 gates above are open.
4. **Viewer certification**: contributors STAGE batches (`tools/probe_batch.py stage`) and stop at READY; whoever
   uploads to Autodesk's reader records verdicts in `docs/coverage/viewer-certified.json` and
   `docs/inbox/genesis-audit.md` through a `hot-file` PR. Needs a viewer login, so not from a fresh clone or a cloud
   session.
5. **After shipping**: close the issue with the merge sha and the ship state; ratify the `KNOWLEDGE.md` entries the
   work produced; update this file if what is live or how to ship changed; archive what you ingested.

## What is running now

| What | Session / branch | Resume | Stop when |
|---|---|---|---|
| `automerge` sweep | GitHub Actions schedule, every 30 min (per `automerge.yml`) | — | standing |
| Local worktrees | none besides the main checkout on this machine (2026-10-08) | — | — |
| Cloud sessions, review loops, routines | *unknown, verify* | — | — |

When you start a loop, routine or long-lived session, add a row (what · session/branch · how to resume · when to stop)
and remove it when it ends.

## Open fronts (pointers, not the queue — the queue is Issues)

- **Archived tracker rows are not yet issues.** Rows open at archive time (P0 gates and residuals, Epic P, F7–F9,
  G1–G4 productization, A12, B3, D9 legal review, E1–E3, H1–H4, the open questions) need filing, search first.
- **`docs/inbox/` backlog.** About 150 August records are on `main`, un-ingested and un-archived, and cited by path
  from code comments and docs. Ingesting them (ratify into `KNOWLEDGE.md`, archive, fix references) is its own stream.
- **"START HERE" (#25)** predates the kind / workflow / priority labels; its text needs the same update `CLAUDE.md` got.
- **Citations of `TRACKER.md` in product docs** (`docs/product/COUNSEL-BRIEF.md`, `MCP-PATH.md`, `architecture.md`,
  `plugin/docs/HONEST-STATUS.md` and its eval-kit mirror) still point at the old file; they land on the pointer and
  resolve in the archive. Re-point them when those docs are next reconciled.
- **Rename** to the cleared product name is blocked on trademark clearance (`RENAME.md`).
