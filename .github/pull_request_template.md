<!-- One issue = one branch (from main, never stacked on another PR's branch) = one PR. `coord` checks the linked issue / claim / overlap the moment this opens; CI + claude-review run automatically, a bounded auto-fix may push to your branch, automerge squash-merges when green + approved (a green + approved DRAFT is marked ready and merged after 90 quiet minutes — label `wip` to hold it), and closes the linked issue. If the bots cannot finish it, the issue is re-queued with this branch named; humans are only pinged for the short list in docs/process/AUTONOMY.md §10. For a partial, write "Refs #N" — never "does not close #N" (GitHub closes it anyway). -->
Closes #

- [ ] I was that issue's assignee before starting (self-assign, `/claim` or `/next`; no ⛔ from the `coord` bot), and searched open issues/PRs for the same work
- [ ] Any steer my human gave me during this work is logged as a `steer` issue (`/steer`), and follow-ups I found are filed as task issues (`Refs #…`), not left in prose

## What changed and why
<!-- 2-5 lines. What the change does, not how you found it. -->

## Stream record
- Record: `docs/inbox/<stream>.d/<issue>-<slug>.md` fragment (preferred — a new file nobody else appends to; index `docs/inbox/<stream>.md` exists) or `docs/inbox/<stream>.md`, ending with a `BRANCH STATE` block (`docs/inbox/README.md`) — [ ] included / updated in this PR
- Learnings for KNOWLEDGE.md (if any): `docs/inbox/learned-<slug>.md` — [ ] included  [ ] n/a

## After opening
- [ ] Auto-fix turned on for this PR (cloud: CI bar → Auto-fix / "auto-fix this PR"; terminal: `/autofix-pr`)

## Gates run (paste counts / outputs)
- [ ] Stream-local tests: `.venv/bin/python -m pytest tests/test_<yours>.py -q` → 
- [ ] New fresh-clone-safe test file for the CI shard? → added a drop-in `tests/ci_shard.d/<issue>-<slug>.txt` (never edited `tests/ci_shard.txt`)  [ ] n/a
- [ ] Touched `src/`, `tools/`, `skills/`, or `plugin/`? → `tools/sync_plugin.py` run, `--check` clean, `plugin/scripts/validate_plugin.py` OK
- [ ] …and the product still works from a bare unzip: `tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py` green (or `tools/surface_bench.py` output pasted)
- [ ] Produced `.rvt`/`.rfa` output? → `tools/rvt_validate.py` 0 errors + `tools/provenance.py` clean
- [ ] Did NOT run the full suite concurrently with others (see docs/inbox/SUITE-COORDINATION.md)

## Viewer certification (only if this PR claims a file "loads")
- [ ] Batch STAGED via `tools/probe_batch.py stage` (certified base + byte-identical control) — batch #: 
- [ ] Verdicts recorded in `docs/coverage/viewer-certified.json` + `docs/inbox/genesis-audit.md` (by whoever uploaded)
- [ ] n/a — no certification claim in this PR

## Hard-rule self-check
- [ ] Output is always delivered (gates are labels, never refusals)
- [ ] Nothing reads an Autodesk install directory
- [ ] Zero donor bytes in anything shippable; sample-derived material only in git-ignored / PROOF-ONLY paths
- [ ] Hot files touched? (`tools/frontdoor.py`, `plugin/skills/*/SKILL.md`, `src/rvt/versions/`, `src/rvt/frontdoor/base.py`, `TRACKER.md`, `KNOWLEDGE.md`, `viewer-certified.json`) → issue is labelled `hot-file` and this PR is tiny
