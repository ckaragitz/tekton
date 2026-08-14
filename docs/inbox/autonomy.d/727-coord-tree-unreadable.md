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
  - `on_main_batches(text, src)` is the law: the `--tree` text is either **empty** (nothing under `experiments/` on
    the default branch yet — legal) or names **at least one** path under `experiments/`; a non-empty text with none is
    never git's answer to the recipe but exactly what an unreadable producer decodes to (UTF-16 with or without BOM —
    every ASCII character carries a NUL, so no NUL-split chunk can spell `experiments/` — a listing of the wrong tree,
    an OEM code page, HTML), and is refused with `InputError` — never read as an empty `on_main`. No encoding sniffing:
    the invariant catches every such producer structurally, where BOM/NUL-pattern detection would be one special case
    per producer and still miss BOM-less UTF-16BE (the altitude reviewer probed the edges: a cp1252/Latin-1 producer
    passes *correctly* — ASCII prefix and `batch_N.json` tail survive `surrogateescape`; PowerShell 7's `-z` output
    through a pipeline gains a trailing `\r\n` pseudo-name, which is why the law is "any", not "all"; a PS5 `>` of an
    *empty* listing — `FF FE` alone — is refused rather than read as empty: erring closed, and the message names the fix).
    `tree_names()` (the tokenizer every `--tree` caller uses) drops a leading UTF-8 BOM (Windows PowerShell's `Out-File
    -Encoding utf8`, the producer the refusal recommends there because it exists on 5.1 and 7 alike) instead of leaving
    it glued to the first name. `tree_input(path)` = the bytes-faithful `open()` from #723 + the law labelled with the
    file; `json_input(path)` = `json.load` whose failure (garbage, truncated, HTML, UTF-16 — the same PowerShell `>`
    writes `reg.json`/`prs.json` that way too) names the file. `main()` now runs the parsed subcommand through `run(a)`
    and turns `InputError` and any `OSError` carrying a filename into **one stderr line + exit 2** — for every
    subcommand (`reserve`, `batchjudge`, `queue`, `locks`, `similar`, `rivals`, `reqfile`), one mechanism rather than a
    `reserve`-only special case (no caller distinguishes exit 1 from 2; `techlead.py` imports functions, never the CLI);
    stdout stays empty so a caller's `out=$(…)` gets no half-answer, and the dispatch-only `coord.yml` reference (its
    call sites run under `set -euo pipefail`, `local` declared on its own line) would abort the step before any comment
    instead of posting a floor answer. Two residues named, not fixed: `coord.yml`'s own `2>/dev/null || : > tree.txt`
    fallback and any `> tree.txt` whose git fails leave a 0-byte — legal — file (reference design, untouched under #302;
    and the tool is deliberately repo-blind), so `reserve`'s reply now **states what it saw** — `(registry: #N; highest
    batch on main: 62)` / `…: none` — making a floor answer visible to the human reading it; and `reqfile`'s plain-text
    `open().read()` would still traceback on a non-UTF-8 requirements file (legacy drop-box lane, out of territory).
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
- Tests: new `tests/test_coord_727.py`, 29 rows, stdlib only (drop-in `tests/ci_shard.d/727-coord-tree-unreadable.txt`):
  UTF-16 / UTF-16LE / UTF-16BE trees × {`reserve`, `batchjudge`} → exit 2, empty stdout, ONE stderr line naming
  `--tree <path>`, "none under experiments/", the recipe and the PowerShell producer; the mechanism pin (bytes-faithful
  decoding of UTF-16 yields names, none under `experiments/`, and the pre-law arithmetic answers `BATCH_FLOOR+1`);
  UTF-8-BOM trees in line / CRLF / `-z` shape with the top number on the first line → `lo == 61` (a lost first line
  answers 58) and the reply says `highest batch on main: 60`; empty / `\n` / `\r\n` / BOM+`\r\n` trees →
  `BATCH_FLOOR+1`, exit 0, silent stderr, reply `highest batch on main: none`; a listing of the wrong tree →
  refused, message pointing at the EMPTY-file convention; a missing `--tree`/`--registry`/`--prs` → one line
  `cannot read <path>: No such file or directory`; garbage / UTF-16 / empty JSON in `--registry`/`--prs` → one line
  `<path>: not readable JSON (…)`; `queue`/`locks`/`reqfile` word a missing file the same way; `on_main_batches` unit
  row (the tokenizer drops the BOM in both shapes, `-z` and line shapes agree, the refusal carries its label,
  `InputError` is a `ValueError`, a whole-repo listing that does hold an `experiments/` name is read, not refused).
  **Engine swap:** over `origin/main`'s `coord.py` 28 of the 29 rows FAIL (the BOM-led-JSON row included: main's
  plain `json.load` tracebacks on the BOM); the one that passes there is the mechanism pin, which asserts main's own
  arithmetic by design.
- `/simplify` pass (reuse / simplification / efficiency / altitude, four independent reviewers) — taken: the module
  docstring no longer re-spells the recipe beside `TREE_RECIPE` (two hand-maintained copies had already drifted once
  per PR); the BOM strip moved from the law into `tree_names()` (a property of `--tree` text, so every tokenizer caller
  is BOM-safe); the law takes a `src` label instead of `tree_input` catching and re-wrapping its exception; the refusal
  lost ~50 redundant characters; `e.strerror or e` lost its dead fallback; the reply's "highest batch on main" clause
  (altitude's mitigation for the 0-byte residue); in the tests an invisible literal U+FEFF became `\ufeff`, `run()`
  defaults its inputs so the missing/garbage rows stop restating them, one `cli()` runner, the other-subcommands row is
  parametrized, an implied assertion dropped. Measured clean by the efficiency reviewer: over the real 1448-name tree
  the law costs 0.49 ms vs 0.47 ms before (`removeprefix` without a BOM returns the same object; `any()` stops at the
  first name); over the UTF-16 copy it is *faster* (6.9 vs 11.6 ms — the raise skips the regex pass); the module runs
  in ~1 s (one ~36 ms subprocess per row). Skipped: `encoding="utf-8-sig"` on the *tree* open instead of the text-level
  strip (would take the BOM out of the unit-testable law's reach), and a `text_input()` for `reqfile` (above).
- Independent review of head `1636f27` (fresh context, told the author is the would-be merger; sandboxed CI on that head:
  pass, shard 2689 passed / 132 skipped / 3 xfailed in 438 s): 🟡 nits only — taken in the next head: `json_input()`
  reads `utf-8-sig`, so a BOM-led `reg.json` / `prs.json` written by the very producer the tree refusal recommends is
  read like plain UTF-8 instead of being refused for its BOM (measured by the reviewer: `locks --comments <EF BB BF[]>`
  → rc 2 before), plus one test row for it; this block's gate list named a test module that does not exist
  (`tests/test_shard_list.py` is meant). Left as ruled: whitespace-only tree text (`"   \n"`) is refused as one name
  rather than read as empty — errs closed, no producer emits it. The reviewer's own law probe (24 files + 31 synthesized
  texts, PR vs main): all 8 legitimate shapes of main's real tree → 36 batches, top 62 on both; every UTF-16/-32 copy →
  main empty `on_main`, PR refused; C-quoted / Latin-1 / cp1252 names counted; other subcommands byte-identical to main
  on good input; accepted the beyond-territory pieces (`main()`→`run()`, the reply clause, `--full-tree`) as verified
  harmless — recorded here as the merge note asks.

## BRANCH STATE

- Branch `cam/727-coord-tree-unreadable` from `main` @ `b30c868`; files: `tools/dev/coord.py` (`TREE_RECIPE`,
  `InputError`, `on_main_batches`, `tree_input`, `json_input`, `main()`→`run()` split, BOM strip in `tree_names`, the
  reply clause, docstring + `--tree` help),
  `tools/dev/techlead.py` (one comment), `tests/test_coord_727.py` (new), `tests/ci_shard.d/727-coord-tree-unreadable.txt`
  (new), `tests/test_coord_723.py` (fixture docstring only), `docs/inbox/autonomy.d/723-coord-batch-names.md` (one
  sentence, marked), this fragment (new; index untouched).
- No `src/`, `plugin/`, `skills/`, workflow or hot file touched. Gates: see the PR body for the pushed head's counts
  (`tests/test_coord_727.py`, `tests/test_coord_723.py`, `tests/test_coord.py`, `tests/test_techlead.py`,
  `tests/test_records_layout.py`, `tests/test_shard_list.py`; `check_portable_paths.py`; `sync_plugin.py --check`); the
  sandboxed shard's counts go in the merge comment.
- Shipped on merge; nothing staged.
