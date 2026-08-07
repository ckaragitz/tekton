# validate-plugin-nonskill-dirs — issue #26

## What was built

`plugin/scripts/validate_plugin.py` exited 1 on a clean checkout, unconditionally.
`check_skills()` iterated every directory under `plugin/skills/` and demanded a
`SKILL.md`, but `_shared` is the zero-pip bootstrap package (`tekton_env.py`,
`tekton_schema.py`, `_vendor/olefile` — 7 tracked files) documented in
`CLAUDE.md` §3, not a loadable skill. `check_referenced_paths()` walked the same
directory list.

Fix: one helper, `skill_dirs(d)`, returning only real skill directories —
subdirectories whose name does not start with `_`. Both call sites use it.

## Evidence (numbers, not adjectives)

Before, on a clean checkout of `284ec48`:

```
  assertions passed: 23
  FAILURES: 1
   x skills/_shared: SKILL.md missing
exit=1
```

After:

```
  assertions passed: 23
  RESULT: PASS — plugin structure is valid
exit=0
```

`75 referenced plugin-relative paths resolve on disk` is unchanged before and
after, so skipping `_` dirs loses no reference coverage — `_shared` contributes
no markdown to that scan (`_vendor/README.md` sits one level deeper than the
scanner looks).

Tests: `tests/test_plugin_validate.py` — 3 passed in 0.24s.

## Findings

- The `_` rule also covers `__pycache__`. That matters more than `_shared`:
  `__pycache__` appears under `plugin/skills/` as soon as anything imports from
  there, so before this fix the validator's failure count depended on whether
  the tree had been executed. A fresh clone reported 1 failure; a working tree
  reported 2. Anything walking `skills/` must filter, not enumerate.
- The regression test deliberately asserts `_shared` has **no** `SKILL.md`, to
  block the tempting wrong fix (adding a stub), which would make the bootstrap
  package loadable as a skill.

## Open questions

- `check_referenced_paths()` still carries a vestigial single-element loop
  (`for base, sub in (("skills", None),)`) whose `base`/`sub` are unused. Left
  alone — out of territory for a bug fix this size.

## BRANCH STATE

- Branch: `ckaragitz12/26-validate-plugin-nonskill-dirs`
- Files written:
  - `plugin/scripts/validate_plugin.py` (hand-authored per CLAUDE.md §3b — not a sync mirror)
  - `tests/test_plugin_validate.py` (new)
  - `docs/inbox/validate-plugin-nonskill-dirs.md` (this record)
- Gates: `plugin/scripts/validate_plugin.py` exit 0; `tests/test_plugin_validate.py` 3 passed.
- `tools/sync_plugin.py --check`: not clean on this machine, for an unrelated
  reason — see issue #27 (no `.gitattributes`, so `autocrlf=true` gives Windows
  clones CRLF and the byte-compare against LF-generated content always reports
  `assets/schema_cache/index.json` as drift). Not caused by this branch: the
  same drift is present on unmodified `main` on this machine, and this branch
  touches nothing `sync_plugin.py` mirrors.
- Staged vs shipped: shipped — no viewer certification claim in this PR.
