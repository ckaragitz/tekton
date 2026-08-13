# 723 — `coord.py reserve` reads the batch files on main NUL-clean; the brief names records raw

Fragment of the `autonomy` stream (index: `docs/inbox/autonomy.md`; the `/batches` mechanism is its
"Viewer batch numbers at fan-out scale (#285)" section). Issue #723. Refs #540 #285 #302.

## What was wrong (measured)

`tools/dev/coord.py`'s `reserve` / `batchjudge` learn "which batch numbers are already on `main`" from a
`--tree` file the recipe fills with `git ls-tree -r --name-only HEAD -- experiments/`, and read it with
`fh.read().split()` — a **whitespace** split — under git's default `core.quotePath`. Over a repo holding
`experiments/acceptance/batch_56.json`, `experiments/w x/batch_57.json` and `experiments/métier/batch_58.json`
(git writes the last as `"experiments/m\303\251tier/batch_58.json"`), with no reservation and no open PR:

```
BEFORE  line-form tree.txt   reserve --k 2 -> 57 .. 58     (57 split in two, 58 quoted: only 56 survived — both RE-ISSUED)
BEFORE  -z tree.txt          reserve --k 2 -> 15 .. 16     (one unsplittable token: nothing survived, back to the floor)
AFTER   line-form tree.txt   reserve --k 2 -> 59 .. 60
AFTER   -z tree.txt          reserve --k 2 -> 59 .. 60
```

Fail-open in the one guard that exists to stop two sessions staging the same numbers (#285). Latent today — every
batch file on `main` is ASCII `experiments/acceptance/batch_N.json` — but `experiments/<stream>/**` is free-form.
Second reader, cosmetic: `tools/dev/techlead.py recent_records()` (`git log --name-only`) put a record named
`docs/inbox/café notes.md` on the planner brief as `"docs/inbox/caf\303\251 notes.md"`.

## What changed

- `tools/dev/coord.py`: `tree_names(text)` reads the `--tree` file NUL-separated when a NUL is present, else one
  name per **line** — never per blank; `batch_numbers()` drops a surrounding pair of git C-quotes before matching
  (only the ASCII `batch_<n>.json` tail carries the number, `(?:.*/)?` swallows the escaped middle, so no full
  unquoting is needed). Both CLI consumers (`reserve`, `batchjudge`) go through it. Net effect: the documented `-z`
  recipe, the older line recipe, quoted or raw names — every producer yields the same `on_main`. The module docstring
  and the `--tree` help now document `git ls-tree -r -z --name-only HEAD -- experiments/ > tree.txt` as the recipe.
- `tools/dev/techlead.py`: `recent_records()` runs git with `-c core.quotePath=false` (the #540 fix, one token).
- **Recipe location (DONE 3):** the tech-lead session runs `coord.py reserve` by hand over API-fetched inputs plus a
  local `git ls-tree` (AUTONOMY.md §12c "Claims" row; CLAUDE.md §2), and the recipe text it follows is `coord.py`'s
  own docstring/help — updated here. `.github/workflows/coord.yml` (dispatch-only reference design under #302) is
  **not** touched: its line-form `ls-tree` output is now read correctly anyway, quoted names included, so the
  reference stops being fail-open without a workflow-file edit.
- Tests: new `tests/test_coord_723.py` (8 rows; drop-in `tests/ci_shard.d/723-coord-batch-names.txt`) feeds the reader
  REAL `git ls-tree` output in both shapes from a throwaway repo — `on_main == {56, 57, 58}` for `-z` and line form;
  the mechanism pinned (a whitespace reading of the same line output still loses 57); end to end through the CLI,
  `reserve --k 2` answers 59..60 for both shapes and `batchjudge` does not call a PR that *edits* the existing
  `experiments/w x/batch_57.json` a clash with the issue 57..58 was reserved for; `tree_names` unit row (NUL wins over
  newline; a NUL-separated name may itself hold a newline; unbalanced quotes are left alone). One row in
  `tests/test_techlead.py`: a `docs/inbox/rig-café notes.md` record is listed raw. **Engine swap:** all 8 coord rows
  and the techlead row FAIL over `origin/main`'s tools (the first draft of the end-to-end row passed over main — an
  open PR adding `batch_59` masked the misread by setting the ceiling — and was reworked until it failed for the
  bug's own reason); all pass over the fix.

## BRANCH STATE

- Branch `cam/723-coord-batch-names` from `main` @ `3df18e4`; files: `tools/dev/coord.py` (`_unquoted`,
  `tree_names`, `batch_numbers` un-quotes, CLI reader, docstring + `--tree` help), `tools/dev/techlead.py` (one `-c`),
  `tests/test_coord_723.py` (new), `tests/ci_shard.d/723-coord-batch-names.txt` (new), `tests/test_techlead.py`
  (+1 test), this fragment (new; index untouched).
- No `src/`, `plugin/`, `skills/`, workflow or hot file touched. Gates: `tests/test_coord_723.py` +
  `tests/test_coord.py` + `tests/test_techlead.py` + `tests/test_records_layout.py` green;
  `check_portable_paths.py` ok; `sync_plugin.py --check` in sync (see the PR for the pushed head's counts; the
  sandboxed shard's counts go in the merge comment).
- Shipped on merge; nothing staged.
