# perf-surfaces / #757 -- SKILL.md §5.2–5.4 teach the one-call flow (DONE 4 of #754)

Stream: PERF-SURFACES (index: `docs/inbox/perf-surfaces.md`). Issue #757 (Refs #754, #112, #110, #113).
Branch `cam/757-skill-one-call` from `main@385b1c3`. Hot-file PR (CLAUDE.md §4): SKILL.md only, +7 lines net.

## What changed

* `skills/tekton-ifc/SKILL.md` (the source; `plugin/skills/tekton-ifc/SKILL.md` is its byte-identical
  mirror through `tools/sync_plugin.py` -- the issue's "the file is a source, not a mirror" note was
  wrong, CLAUDE.md §3b has it right) §5.2 opens with the one-call flow:
  `python scripts/ifc_flow.py path/to/input.ifc --out out --json` -- validate → harden → re-validate
  → report in one process, the five files it writes, the JSON `line` as the verdict, exits 0/1/2 with
  the hard-rule-1 wording (exit 1 delivers everything and says so) -- and names 5.2–5.4 as the
  compose-by-hand path (`validate_ifc.py`, `harden_ifc.py`, `validate_ifc.py` again, `report.py`).
* §5.4's `report.py` example is now the real invocation
  (`report.py out/validate.json --compare out/harden.json -o out/delivery-report.md`); the old
  `report.py out/hardened.ifc --before …` form never existed (noted on #112).
* `skills/tekton-ifc/references/sop-harden-deliver.md` step 8 (+ mirror): the same real `report.py`
  invocation; "omit `--compare` if hardening was skipped" replaces the old "both positions" note.
* Frontmatter untouched; every path the text references exists.

## Evidence

* `plugin/scripts/validate_plugin.py` -> PASS (25 assertions); `tools/sync_plugin.py` + `--check` ->
  "plugin in sync with source"; `tools/dev/check_portable_paths.py` -> ok (3161 paths).
* Both documented commands run verbatim from `plugin/skills/tekton-ifc/` on the plugin's sample:
  `ifc_flow.py … --out out --json` -> exit 0, `line` = "hardened: score 35.7 -> 77.0, 0 schema errors
  after, 5 files under …/out"; `report.py out/validate.json --compare out/harden.json -o
  out/delivery-report.md` -> exit 0, `report -> out/delivery-report.md`.

## Open

* #112 (SKILL.md weight/split) rewrites §5.2–5.4 wholesale; it should keep the one-call form first.
* `references/sop-harden-deliver.md` still walks the four-call runbook (the compose-by-hand detail;
  #112's territory) -- its step 8 carried the same phantom `report.py … --before` line, fixed here
  (not a hot file). Its step 7 "If errors remain, do NOT deliver … stop" contradicts hard rule 1
  (deliver, then caveat) -- noted on #758 for the wording pass.

## BRANCH STATE

* Branch `cam/757-skill-one-call` (from `main@385b1c3`). Files: `skills/tekton-ifc/SKILL.md` and
  `skills/tekton-ifc/references/sop-harden-deliver.md` (sources), their `plugin/skills/tekton-ifc/` mirrors
  (via sync), this fragment + one index line.
* Gates: as above. Nothing shipped beyond the PR (`tekton-plugin.zip` rebuilt locally, git-ignored).
