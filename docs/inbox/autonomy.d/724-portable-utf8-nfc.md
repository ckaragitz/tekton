# 724 — `check_portable_paths.py` refuses names that are not valid UTF-8 and NFC/NFD twins

Fragment of the `autonomy` stream (index: `docs/inbox/autonomy.md`; the gate's history is its "eng #496" / "eng #522"
sections and `autonomy.d/540-ci-fresh-quoted-docs.md`). Issue #724 — filed from #540's `/simplify` altitude pass.
Refs #540 #522 #496.

## What was missing (measured)

`tools/dev/check_portable_paths.py`'s `check()` is THE names-only gate: a CI step in `session_ci.sh`, and re-run at
merge time by `ci_fresh.sh` over the post-merge name set (#522). Collaborators check out onto NTFS and APFS/HFS+. Two
things those filesystems cannot hold passed the gate:

```
                                                             main @ ecbe74c      this branch
w/latin1<E9>.md   (a cp1252 tool's é: not UTF-8)              accepted            not valid UTF-8: b'w/latin1\xe9.md'
w/café.md NFC  +  w/café.md NFD  (é vs e+U+0301)              accepted (2 files)  normalisation-only collision (breaks macOS checkouts): ['w/caf\xe9.md', 'w/cafe\u0301.md']
w/Café.md NFC  +  w/café.md NFD                               accepted            case-only collision (…): both names  (one file only on a case-INsensitive volume: the case law's)
this checkout (3115 tracked paths, incl. this fragment)       ok                  ok — unchanged
ci_fresh: PR adds docs/inbox/café.md NFC, main adds the NFD   FRESH(docs-only)    STALE … changed=docs/inbox/cafe<U+0301>.md (added on main; PR 24 adds the same
                                                                                  name or a case-twin of it …) — exit 4, no change to ci_fresh.sh
```

APFS is normalisation-insensitive: the NFC and NFD spellings are two names to git and one file to a macOS checkout,
exactly like the case-only twins the gate already refused; HFS+ additionally rewrites NFC to NFD on disk, so such a
pair also means phantom `git status` changes. A name whose bytes are not UTF-8 cannot be created on APFS at all and is
mangled by most Windows tooling. Since #540 `ci_fresh.sh` reads docs drift raw, so at merge time these names are
judged purely by `check()` — the right layering, which makes both laws the checker's to carry.

## What changed

- `tools/dev/check_portable_paths.py`
  - **Encoding law** (per name). The CLI now decodes `git ls-files -z` with `surrogateescape` (bytes-faithful:
    the name reaches `check()` instead of arriving pre-mangled by `replace`), and `check()` reports
    `not valid UTF-8: b'…\xe9…'` for a name carrying surrogate-escaped bytes (spelled as the bytes they are), or
    `replacement character U+FFFD in name (an undecodable byte was replaced somewhere upstream): '…\ufffd…'` — worded as
    a property of the name because the pure function cannot know WHO replaced the byte (a `replace` reader such as
    `ci_fresh.sh`'s unchanged one, whose post-merge run thereby feels the law, or the writing tool itself; a name
    genuinely spelled with U+FFFD is refused as well, which is right for a portability gate). Both scans sit behind
    `str.isascii()`, so an all-ASCII name pays nothing. `main()` prints with `backslashreplace` so a problem line quoting
    such a name raw (the record-layout and path-too-long lines do) can never kill the report — encoding handled at the
    I/O boundary, not inside the pure function.
  - **Normalisation law** (cross-file, same shape and ordering contract as the case law, printed after every case
    group): canonically equivalent names that are not byte-equal → `normalisation-only collision (breaks macOS
    checkouts): [...]`, the group spelled with `ascii()` because the twins print identically otherwise. Keyed on the
    NFD form (equivalent to keying on NFC — each is the unique representative of its canonical-equivalence class;
    compatibility forms such as full-width letters or ligatures are rightly NOT folded: APFS does not fold them
    either). The case law's key became `NFD(name).lower()` (was `name.lower()`): decompose THEN lower, the order the
    filesystems fold in, so capital J + combining caron and precomposed `ǰ` (which has no capital) pair up; `lower()`
    rather than `casefold()` because volumes fold 1:1 — `straße`/`strasse` are two files everywhere and casefolding
    would silently widen the pre-existing law. So a pair differing by case AND form — `Café.md` NFC vs `café.md`
    NFD, one file only on a case-insensitive volume, caught by neither law if they stayed independent — is the case
    law's; a group differing ONLY by form is the normalisation law's alone (no double report); a repeated identical
    name stays a case group exactly as before (ci_fresh's add/add detection depends on it) unless a form-twin rides in
    the same group, in which case the whole group, repeat included, is reported once by the normalisation law. A name
    that twins one sibling by case and another by form is reported once under each law, deterministically (dict
    insertion order, as the case law always was). Both cross-file laws judge whole names, as the case law always has:
    twins differing inside a directory component only (`Docs/a.md` vs `docs/b.md`, an NFC vs NFD spelling of one
    `<stream>.d/`) are not paired — the same gap the case law has carried since #496, filed as its own follow-up
    rather than widened here. Every pre-existing row of `tests/test_portable_paths.py`,
    `tests/test_records_layout.py` and `tests/test_ci_fresh.py` is byte-identical in outcome; this checkout's own
    verdict is unchanged (`ok: 3116 tracked paths`, this fragment included).
  - Still stdlib-only and self-contained (`unicodedata`); `python3 -I` / load-by-path unaffected. Cost, measured over
    this checkout's 3116 names: `check()` best-of-20 5.5 → 6.9 ms; the CLI end to end (interpreter start-up included,
    mean of 10) 36 → 39 ms. The first head paid 5.5 → 13.7 ms / 35 → 48 ms, three quarters of it a per-character
    Python scan for surrogates; the `isascii()` guard plus a compiled class took that back (efficiency review).
- `CLAUDE.md` §4 portable-paths sentence: one clause ("names in valid UTF-8 only, and no two names that differ only
  by Unicode normalisation form"). **Hot file** — this is the PR's only hot-file touch, chartered by the issue; nobody
  held CLAUDE.md (no open PR touches it).
- `tools/dev/ci_fresh.sh`: **unchanged**, as chartered. Ruling on the issue's own wording (recorded here and in the PR):
  DONE (3) asked for the ci_fresh row to be "STALE worded by the checker", but with the helper unchanged a finding that
  holds a PR-added name is answered by the helper's #496 add/add-twin line ("adds the same name or a case-twin of
  it"), and only findings NOT touching a PR-added name show the checker's own line. The row pins the real behaviour —
  STALE, exit 4, main's NFD spelling named — and the slightly narrow phrase "case-twin" is left for #722, which
  rewrites that very program, to generalise. Substance (STALE at merge time instead of FRESH) is what the DONE is for.
- Tests: `tests/test_portable_paths.py` — the CLI-order contract row extended with a Latin-1 name and an NFC/NFD pair
  (per-name law in input order; the normalisation group after every case group); a partition row (form-only pair →
  normalisation law alone; case+form pair → case law alone; a three-name group → once per law; lone NFC/NFD and an
  ASCII lookalike change nothing; a repeat stays a case group, a repeat plus a form-twin is one normalisation group;
  J+caron vs `ǰ` pair; `straße`/`strasse` do not); a decoding row (surrogateescape residue → bytes wording, `replace`
  residue → the U+FFFD wording); a CLI row through real `git ls-files -z` over a repo holding the twins and the Latin-1
  name (Linux only: APFS/NTFS cannot create them — that is the law) asserting exit 1 and the exact report, in git's
  byte order. `tests/test_ci_fresh.py` — the merge-time row above (skipped on macOS, where git precomposes an NFD
  add), and `TWIN_LINE` (which hard-coded "PR 7") became `twin_line(was, now, changed, pr=7)` so the row reuses the
  helper's sentence instead of re-spelling it (reuse review; two existing call sites updated, byte-identical strings).
  **Engine swap:** all 5 new/extended rows FAIL over `origin/main`'s checker.
- `/simplify` pass (reuse / simplification / efficiency / altitude, four independent reviewers) — taken: everything
  above marked with a review, plus `nfd(p)` computed once per name, the case-group condition stated positively, the
  duplicate "valid non-ASCII is clean" assertion dropped, the CLI row's fold probe using the sibling row's
  `git ls-files` idiom (no `import os`). Not taken: hoisting `stdout.reconfigure` to `main()`'s first line (equally
  correct, saves nothing). Notes passed on: #722 must add the same `backslashreplace` at its boundary if it switches
  `ci_fresh.sh`'s reader to surrogateescape (comment left there); component-level twins filed as a follow-up issue.

## BRANCH STATE

- Branch `cam/724-portable-utf8-nfc` from `main` @ `ecbe74c`; files: `tools/dev/check_portable_paths.py`,
  `tests/test_portable_paths.py`, `tests/test_ci_fresh.py` (+1 row), `CLAUDE.md` (one clause, hot file), this
  fragment (new; index untouched). No `src/`, `plugin/`, `skills/` or workflow file touched; both test modules were
  already in the shard (`tests/ci_shard.d/522-portable-paths.txt`, `487-ci-fresh.txt`), so no drop-in is added.
- Gates: see the PR body for the pushed head's counts; the sandboxed shard's counts go in the merge comment.
- Shipped on merge; nothing staged.
