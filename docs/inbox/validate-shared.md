# validate-shared — exempt `_`-prefixed infrastructure dirs from the SKILL.md rule (issue #34)

Stream: `clkaragitz/34-validate-shared` · Territory: `plugin/scripts/validate_plugin.py` · 2026-08-07

## What was built

`check_skills()` now treats `_`-prefixed directories under `plugin/skills/`
as shared infrastructure, not skills: they are exempt from the SKILL.md
requirement and reported with an `ok` line naming the exemption. Rationale
pinned in the code comment: `skills/_shared/tekton_env.py` is the zero-pip
bootstrap (hand-authored per CLAUDE.md §3b), the plugin loader only
enumerates skill dirs carrying a SKILL.md, and the D9 load test enumerated
exactly 5 skills WITH `_shared` present. No dummy SKILL.md added (it would
enumerate as a sixth skill).

## Evidence (numbers)

- Before (clean main, any OS): `assertions passed: 23 / FAILURES: 1 /
  x skills/_shared: SKILL.md missing`, exit 1.
- After: `assertions passed: 24 / RESULT: PASS`, exit 0.
- `tests/test_plugin_sync.py`: 6/7 pass; the 1 failure is
  `test_plugin_is_in_sync_with_source` flagging ONLY
  `assets\schema_cache\index.json` — the known Windows separator churn
  (issue #33), reproduced on clean main on Windows, green on POSIX.

## BRANCH STATE

- Files written: `plugin/scripts/validate_plugin.py` (+7 lines), this record.
- Gates: `validate_plugin.py` exit 0 (24 assertions); `sync_plugin.py
  --check` flags only the #33 Windows churn (not touched here);
  no `src/` change → no mirror sync needed.
- Staged vs shipped: no viewer round (validator-only change, no output files).
- Unblocks: #2 CI v1 (validate_plugin is one of its three required checks —
  it must exit 0 on main for the workflow to be green).
