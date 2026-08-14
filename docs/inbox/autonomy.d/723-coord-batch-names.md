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

- `tools/dev/coord.py`: `tree_names(text)` reads the `--tree` file NUL-separated when a NUL is present; otherwise one
  name per git **line** — split on `"\n"` exactly (git's own terminator: `str.splitlines()` would also cut a raw
  U+2028/U+2029/U+0085 inside a name, which the path gate admits and a `core.quotePath=false` producer emits raw), a
  CRLF producer's `"\r"` dropped, git's surrounding C-quotes stripped there (only the ASCII `batch_<n>.json` tail is
  read downstream and `(?:.*/)?` swallows an escaped middle, so no full unquoting is needed; `batch_numbers()` itself
  stays producer-agnostic because the `gh` API paths it also sees are never quoted). Never per blank. The CLI opens the
  file bytes-faithfully (`newline=""`, `errors="surrogateescape"`) and `BATCH_FILE_RE` gained `re.S`/`\Z`, so a
  `-z`-fed name holding a raw CR/LF or a non-UTF-8 byte is neither dropped nor a `UnicodeDecodeError`. Both CLI
  consumers (`reserve`, `batchjudge`) go through it: the documented `-z` recipe, the older line recipe under either
  quoting setting, quoted or raw — every producer yields the same `on_main`.
- **Recipe (DONE 3):** the tech-lead session runs `coord.py reserve` by hand over API-fetched inputs plus a local
  `git ls-tree` (AUTONOMY.md §12c "Claims" row; CLAUDE.md §2), following `coord.py`'s own module docstring and
  `--tree` help — both now say `git ls-tree -r -z --name-only origin/main -- experiments/ > tree.txt` (`origin/main`,
  not `HEAD`: a session asks about the default branch from whatever it has checked out). `.github/workflows/coord.yml`
  (dispatch-only reference design under #302) is **not** touched: its line-form output is now read correctly anyway,
  quoted names included, so the reference stops being fail-open without a workflow-file edit; give it `-z` whenever
  that file is next opened for another reason.
- `tools/dev/techlead.py`: `recent_records()` runs git with `-c core.quotePath=false` (the #540 fix, one token; the
  why lives in its docstring).
- Tests: new `tests/test_coord_723.py` (12 rows; drop-in `tests/ci_shard.d/723-coord-batch-names.txt`) feeds the reader
  REAL `git ls-tree` output of a throwaway repo (`experiments/acceptance/batch_56.json`, `experiments/w x/batch_57.json`,
  `experiments/métier/batch_54.json`, `experiments/ls<U+2028>sep/batch_58.json`) in three shapes — `-z`, line form
  under default quoting, line form under `core.quotePath=false` — and asserts `on_main == {54, 56, 57, 58}` for each;
  pins the mechanism (a whitespace reading of the same line output keeps only 56); end to end through the CLI,
  `reserve --k 2` answers 59..60 for every shape and `batchjudge` does not call a PR that *edits* the existing
  `experiments/w x/batch_57.json` a clash with the issue 57..58 was reserved for; a git-free byte-level CLI row (a `-z`
  tree holding a raw CR, a raw LF and a Latin-1 byte: all three numbers counted, exit 0); a `tree_names` unit row (NUL
  wins; CRLF dropped; quotes stripped; U+2028 is not a line end; an unbalanced quote errs towards "taken"). One row in
  `tests/test_techlead.py`: a `docs/inbox/rig-café notes.md` record is listed raw. **Engine swaps:** 11 of the 12 coord
  rows and the techlead row FAIL over `origin/main`'s tools (the 12th is the mechanism pin, which asserts main's own
  arithmetic by design); 5 rows also fail over this branch's first head `5facefb` (`splitlines()` + a plain UTF-8
  `open()`), which is how the review pass's residual findings were pinned before being fixed. Two vacuity traps met on
  the way and removed: an open PR adding `batch_59` masked the misread by setting the ceiling, and the top number
  sitting under a directory the raw-line misreading happens to keep gave the right answer for the wrong reason — the
  top number now sits under the U+2028 directory every misreading loses.
- `/simplify` pass (reuse / simplification / efficiency / altitude, four independent reviewers) — taken: quote-stripping
  moved out of `batch_numbers()` into the line branch (no `_unquoted` helper left to collide by name with the existing
  `coord.unquoted`), `split("\n")` for `splitlines()`, the bytes-faithful `open()` + `re.S`/`\Z`, `origin/main` in the
  recipe, techlead's why-comment moved into the docstring, the redundant module-level git skip and a dead fixture entry
  dropped, the CLI test helper writes the three input files itself; skipped: module-scoping the `trees` fixture
  (~0.17 s and 36 git processes saved per run, judged not worth leaving the shared function-scoped `git_repo`
  primitive), and unifying the three test modules' 2-line coord-CLI runners into `conftest.py` (the #636 convention
  prefers not touching shared test files for that little).
- Independent review of head `07b1d50` (fresh context, told the author is the would-be merger): 🟡 nits only, all
  four taken in the next head — `recent_records()` decodes git's now-raw UTF-8 output explicitly
  (`encoding="utf-8", errors="replace"`; the locale codec would have garbled a non-ASCII record on a cp1252 Windows
  `brief` — `café` → `cafÃ©` — or crashed it outright on a name carrying one of the five bytes cp1252 leaves undefined
  (0x81 0x8D 0x8F 0x90 0x9D, e.g. `č` = C4 8D); a regression class main's C-quoted ASCII could not hit — wording
  corrected under #727 after measurement), its test blanks `GIT_CONFIG_GLOBAL`/system config so
  the row is not vacuous on a machine whose own gitconfig sets `quotePath=false` (verified: fails over main's
  `techlead.py` under such a config), the recipe fetches before it reads (`git fetch -q origin main && …` — a stale
  `origin/main` is the likeliest real way to hand out a taken number), and the `trees` fixture docstring no longer
  claims byte-exactness it does not have. The reviewer's own break attempt (28 hostile batch paths + 9 decoys, six
  producer shapes): head 0 lost / 0 extra in every shape; main loses 25/28 (line form) and 28/28 (`-z`).

## BRANCH STATE

- Branch `cam/723-coord-batch-names` from `main` @ `3df18e4`; files: `tools/dev/coord.py` (`tree_names`,
  `BATCH_FILE_RE` flags, CLI reader + `open()`, docstring + `--tree` help), `tools/dev/techlead.py` (one `-c` + docstring),
  `tests/test_coord_723.py` (new), `tests/ci_shard.d/723-coord-batch-names.txt` (new), `tests/test_techlead.py`
  (+1 test), this fragment (new; index untouched).
- No `src/`, `plugin/`, `skills/`, workflow or hot file touched. Gates: `tests/test_coord_723.py` +
  `tests/test_coord.py` + `tests/test_techlead.py` + `tests/test_records_layout.py` green;
  `check_portable_paths.py` ok; `sync_plugin.py --check` in sync (see the PR for the pushed head's counts; the
  sandboxed shard's counts go in the merge comment).
- Shipped on merge; nothing staged.
