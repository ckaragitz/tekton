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
  - **Not-valid-UTF-8 law** (per name). The CLI now decodes `git ls-files -z` with `surrogateescape` (bytes-faithful:
    the name reaches `check()` instead of arriving pre-mangled by `replace`), and `check()` reports
    `not valid UTF-8: b'…\xe9…'` for a name carrying surrogate-escaped bytes (spelled as the bytes they are), or
    `not valid UTF-8 (U+FFFD where a reader replaced an undecodable byte): '…�…'` for the residue a `replace`
    reader leaves — which is how `ci_fresh.sh`'s unchanged reader still feels the law. `main()` prints with
    `backslashreplace` so a problem line quoting such a name raw (the record-layout law does) can never kill the report.
  - **Normalisation law** (cross-file, same shape and ordering contract as the case law, printed after every case
    group): names equal under NFC that are not byte-equal → `normalisation-only collision (breaks macOS checkouts):
    [...]`, the group spelled with `ascii()` because the twins print identically otherwise. The case law's key became
    `NFC(name).lower()` (was `name.lower()`), so a pair differing by case AND form — `Café.md` NFC vs `café.md` NFD,
    one file only on a case-insensitive volume, caught by neither law if they stayed independent — is the case law's;
    a group differing ONLY by form is left to the normalisation law (no double report); a repeated identical name stays
    a case group exactly as before (ci_fresh's add/add detection depends on it). So a name that twins one sibling by
    case and another by form is reported once under each law, deterministically (dict insertion order, as the case
    law always was). Every pre-existing row of `tests/test_portable_paths.py`, `tests/test_records_layout.py` and
    `tests/test_ci_fresh.py` is byte-identical in outcome; this checkout's own verdict is unchanged (`ok: 3115`).
  - Still stdlib-only and self-contained (`unicodedata`); `python3 -I` / load-by-path unaffected. Cost: two
    `unicodedata.normalize` calls per name — the CLI over this checkout's 3115 names goes from ~35 to ~48 ms per run
    (interpreter start-up included; mean of 5).
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
  normalisation law alone; case+form pair → case law alone; a three-name group → once per law; lone NFC/NFD, an ASCII
  lookalike, and a repeat change nothing); a decoding row (surrogateescape residue → bytes wording, `replace` residue
  → U+FFFD wording, valid non-ASCII clean); a CLI row through real `git ls-files -z` over a repo holding the twins and
  the Latin-1 name (Linux only: APFS/NTFS cannot create them — that is the law) asserting exit 1 and the exact report,
  in git's byte order. `tests/test_ci_fresh.py` — the merge-time row above (skipped on macOS, where git precomposes an
  NFD add). **Engine swap:** all 5 new/extended rows FAIL over `origin/main`'s checker.

## BRANCH STATE

- Branch `cam/724-portable-utf8-nfc` from `main` @ `ecbe74c`; files: `tools/dev/check_portable_paths.py`,
  `tests/test_portable_paths.py`, `tests/test_ci_fresh.py` (+1 row), `CLAUDE.md` (one clause, hot file), this
  fragment (new; index untouched). No `src/`, `plugin/`, `skills/` or workflow file touched; both test modules were
  already in the shard (`tests/ci_shard.d/522-portable-paths.txt`, `487-ci-fresh.txt`), so no drop-in is added.
- Gates: see the PR body for the pushed head's counts; the sandboxed shard's counts go in the merge comment.
- Shipped on merge; nothing staged.
