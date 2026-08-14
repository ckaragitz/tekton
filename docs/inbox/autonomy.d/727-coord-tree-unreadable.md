# 727 — `coord.py reserve` / `batchjudge` fail closed on a `--tree` they cannot read; input files error in one line

Fragment of the `autonomy` stream (index: `docs/inbox/autonomy.md`, "Viewer batch numbers at fan-out scale (#285)").
Issue #727 — the follow-up the independent review of PR #726 (#723) asked for. Refs #723 #285 #302.

## What was wrong (measured)

#723 made the `/batches` guard's `--tree` reader bytes-faithful (`open(newline="", errors="surrogateescape")`) so no
producer can crash it. The flip side, outside the documented bash recipe: a `tree.txt` written by **Windows PowerShell 5**
redirection (`git ls-tree … > tree.txt` is UTF-16LE + BOM there) decoded to text that names nothing under
`experiments/` — one "name" per NUL-separated byte — so `on_main` came out **empty** and `reserve` answered from the
floor. Over a UTF-16 copy of `origin/main`'s real tree (1448 names, top batch 62), empty registry, no open PRs:

```
                          main @ b30c868 (after #726)          this branch
tree8.txt   (the recipe)  reserve --k 2 -> 63..64  exit 0      63..64  exit 0
tree16.txt  (iconv utf-16)reserve --k 2 -> 15..16  exit 0  ✗   exit 2: "--tree …/tree16.txt: 81177 name(s), none under experiments/ -- not readable
                                                               `git ls-tree` output … regenerate it with `<TREE_RECIPE>` … (PowerShell: … Out-File
                                                               -Encoding utf8 …); an EMPTY file is how to say 'no experiments/ on main yet'"
tree8bom.txt (EF BB BF +) reserve --k 2 -> 63..64  exit 0      63..64  exit 0   (BOM dropped; with the TOP number on the first line main
                                                                                 answers one batch LOW — the tests put it there)
empty.txt   (0 bytes)     reserve --k 2 -> 15..16  exit 0      15..16  exit 0   (legal: a repo with no experiments/ yet)
missing.txt               FileNotFoundError traceback, exit 1  exit 2: "coord.py reserve: cannot read …/missing.txt: No such file or directory"
```

15..16 is numbers long since staged: fail-OPEN, silently, in the guard that exists to stop exactly that (#285). Every
earlier reservation's `hi` still lifted the floor in practice and the only documented runner is a Linux tech-lead
session on the bash recipe — hence P2 — but a collision guard has to fail closed on input it cannot read.

## What changed

- `tools/dev/coord.py`
  - `on_main_batches(text)` is the law: the `--tree` text is either **empty** (nothing under `experiments/` on the
    default branch yet — legal) or names **at least one** path under `experiments/`; a non-empty text with none is
    never git's answer to the recipe but exactly what an unreadable producer decodes to (UTF-16 with or without BOM,
    a listing of the wrong tree), and is refused with `InputError` — never read as an empty `on_main`. A leading UTF-8
    BOM (Windows PowerShell's `Out-File -Encoding utf8`, the producer the refusal recommends there because it exists on
    5.1 and 7 alike) is dropped instead of being left glued to the first name. `tree_input(path)` = the bytes-faithful
    `open()` from #723 + that law + the file's name in the refusal; `json_input(path)` = `json.load` whose failure
    (garbage, truncated, HTML, UTF-16 — the same PowerShell `>` writes `reg.json`/`prs.json` that way too) names the
    file. `main()` now runs the parsed subcommand through `run(a)` and turns `InputError` and any `OSError` carrying a
    filename into **one stderr line + exit 2** — for every subcommand (`reserve`, `batchjudge`, `queue`, `locks`,
    `similar`, `rivals`, `reqfile`), one mechanism rather than a `reserve`-only special case; stdout stays empty so a
    caller's `out=$(…)` gets no half-answer, and the dispatch-only `coord.yml` reference (bash `-e`) would fail its step
    loudly instead of posting a floor answer.
  - The recipe is one constant, `TREE_RECIPE`, used by the module docstring, the `--tree` help and the refusal text, and
    it gained `--full-tree`: `git ls-tree -r … -- experiments/` run from a subdirectory (say `tools/`) matches nothing and
    prints an EMPTY tree — which the law must keep legal — so the recipe itself now yields the full listing from any cwd
    (measured here: 0 names from `tools/` without the flag, 1448 with it). One token, same three strings this issue
    already rewrites; called out for the reviewer as the one addition beyond the issue text.
- Wording nits from #726's review, as chartered: `tests/test_coord_723.py` `trees` fixture docstring no longer says the
  `-z` shape's terminator is stripped (`conftest.git()`'s `str.strip()` leaves NULs); `tools/dev/techlead.py`'s decode
  comment and `docs/inbox/autonomy.d/723-coord-batch-names.md` say cp1252 would *garble* (`café`→`cafÃ©`) or crash
  (only on 0x81/0x8D/0x8F/0x90/0x9D, e.g. `č` = C4 8D) — both measured in this session — instead of "would crash".
  The 723 fragment is this stream's and this author's own; the correction is marked as made under #727.
- Tests: new `tests/test_coord_727.py`, 25 rows, stdlib only (drop-in `tests/ci_shard.d/727-coord-tree-unreadable.txt`):
  UTF-16 / UTF-16LE / UTF-16BE trees × {`reserve`, `batchjudge`} → exit 2, empty stdout, ONE stderr line naming
  `--tree <path>`, "none under experiments/", the recipe and the PowerShell producer; the mechanism pin (bytes-faithful
  decoding of UTF-16 yields names, none under `experiments/`, and the pre-law arithmetic answers `BATCH_FLOOR+1`);
  UTF-8-BOM trees in line / CRLF / `-z` shape with the top number on the first line → `lo == 61` (a lost first line
  answers 58); empty / `\n` / `\r\n` trees → `BATCH_FLOOR+1`, exit 0, silent stderr; a listing of the wrong tree →
  refused, message pointing at the EMPTY-file convention; a missing `--tree`/`--registry`/`--prs` → one line
  `cannot read <path>: No such file or directory`; garbage / UTF-16 / empty JSON in `--registry`/`--prs` → one line
  `<path>: not readable JSON (…)`; `queue`/`locks`/`reqfile` word a missing file the same way; `on_main_batches` unit
  row (BOM stripped, `-z` and line shapes agree, `InputError` is a `ValueError`, a whole-repo listing that does hold an
  `experiments/` name is read, not refused). **Engine swap:** over `origin/main`'s `coord.py` 21 of the 25 rows FAIL;
  the 4 that pass there are the three empty-tree rows (legal before and after, by design) and the mechanism pin (which
  asserts main's own arithmetic, by design).

## BRANCH STATE

- Branch `cam/727-coord-tree-unreadable` from `main` @ `b30c868`; files: `tools/dev/coord.py` (`TREE_RECIPE`,
  `InputError`, `on_main_batches`, `tree_input`, `json_input`, `main()`→`run()` split, docstring + `--tree` help),
  `tools/dev/techlead.py` (one comment), `tests/test_coord_727.py` (new), `tests/ci_shard.d/727-coord-tree-unreadable.txt`
  (new), `tests/test_coord_723.py` (fixture docstring only), `docs/inbox/autonomy.d/723-coord-batch-names.md` (one
  sentence, marked), this fragment (new; index untouched).
- No `src/`, `plugin/`, `skills/`, workflow or hot file touched. Gates: see the PR body for the pushed head's counts
  (`tests/test_coord_727.py`, `tests/test_coord_723.py`, `tests/test_coord.py`, `tests/test_techlead.py`,
  `tests/test_records_layout.py`, `tests/test_ci_shard*.py`; `check_portable_paths.py`; `sync_plugin.py --check`); the
  sandboxed shard's counts go in the merge comment.
- Shipped on merge; nothing staged.
