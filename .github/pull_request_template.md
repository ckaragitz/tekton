<!-- One issue = one branch (from main, never stacked on another PR's branch) = one PR. `coord` checks the linked issue / claim / overlap the moment this opens; CI + claude-review run automatically, a bounded auto-fix may push to your branch, and automerge squash-merges when green + approved. Humans are only pinged via a `needs-human` label. For a partial, write "Refs #N" — never "does not close #N" (GitHub closes it anyway). -->
Closes #

- [ ] I `/claim`ed that issue before starting (the `coord` bot 🔒-acked it), and searched open issues/PRs for the same work

## What changed and why
<!-- 2-5 lines. What the change does, not how you found it. -->

## Stream record
- Record: `docs/inbox/<stream>.md` (ends with a `BRANCH STATE` block) — [ ] included / updated in this PR
- Learnings for KNOWLEDGE.md (if any): `docs/inbox/learned-<slug>.md` — [ ] included  [ ] n/a

## After opening
- [ ] Auto-fix turned on for this PR (cloud: CI bar → Auto-fix / "auto-fix this PR"; terminal: `/autofix-pr`)

## Gates run (paste counts / outputs)
- [ ] Stream-local tests: `.venv/bin/python -m pytest tests/test_<yours>.py -q` → 
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
