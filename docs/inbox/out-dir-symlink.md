# inbox — out-dir-symlink (eng #474: the `--out` refusal judges the LEXICAL spelling too)

Stream: eng #474 (2026-08-10), Refs #452 / #425. Charter (issue #474 + the tech-lead brief): `standalone._inside`
compared directories in ONE canonical spelling (`realpath`, case-folded), so an **outward** symlink planted inside
this checkout's git-ignored `samples/` (`<repo>/samples/escape -> /elsewhere`) plus `--out <repo>/samples/escape/j`
was NOT refused: the job delivered physically through the link and every path it reported stayed spelled
`<repo>/samples/escape/j/…`, which `base.is_autodesk_sample()` (a lexical `startswith(<repo>/samples/)`) calls an
Autodesk sample ever after — the mislabel #452 exists to end, surviving in that one shape. Make the refusal hold when
EITHER the lexical (`abspath`, case-folded) OR the physical (`realpath`) spelling lies inside a quarantine root, without
refusing anything legitimately outside and without ever reading an Autodesk directory (rule 2). Territory:
`src/rvt/frontdoor/standalone.py` (§7 `_inside` / `_canon` / `out_dir_refusal` only), `tests/test_out_dir_guard.py`,
this record (a NEW file — `docs/inbox/standalone.md` is PR #493's this hour), the regenerated mirror. NOT
`src/rvt/frontdoor/__init__.py`, NOT `router.py`, NOT `tools/frontdoor.py`.

## What changed (one function, as #452's record proposed)

`src/rvt/frontdoor/standalone.py` §7:

* `_canon(path) -> str` (realpath, case-folded, dir prefix) becomes `_canons(path) -> List[str]`: **every** spelling a
  directory is compared in — the lexical one (`abspath`: what the user typed, what the manifest / `AuthorResult.files` /
  `is_autodesk_sample` will read) and the physical one (`realpath`), each `normcase`d + lower-cased + one trailing sep
  (built on the existing `_spellings` + `_dirp`, so nothing is defined twice).
* `_inside(path, root)` = either spelling of `path` starts with either spelling of `root`. `_nested`, `out_dir_refusal`
  and `forbid_research_inputs`' `outputs` filter call it unchanged, so all three inherit the law; the refusal LINE text
  is byte-identical (the `str(exc) == out_dir_refusal(out)` tests of #452/#473 compare against the function, and the
  wording fragments `test_out_dir_guard` pins did not move).
* `out_dir_refusal`'s second bullet gets the same law in one line: the Autodesk-install markers are tested on the
  lexical string FIRST (short-circuit: an Autodesk-shaped `--out` still costs zero file syscalls, strace below) and then
  on `realpath(ap)` — so `<tmp>/adlink -> …/Program Files/Autodesk/Revit 2026` + `--out <tmp>/adlink/j`, which main
  happily builds a whole job into (9 files, `prompt_room.rvt` among them, measured below), is refused with the
  install-dir line. `/simplify`'s altitude lens flagged the two bullets of one policy function silently disagreeing
  once the first became two-spelling; same law, same function, one `or`.
* Docstrings by altitude: `_canons`/`_inside` state mechanism only ("both spellings", not "any" — see the residual
  below); `out_dir_refusal` alone carries the policy, the #474 shape and the negatives; `forbid_research_inputs`'
  existing "under ANY spelling: symlinked, or differing only in case" is now true for every single-link shape (no edit).

**Residual, stated not hidden:** `_spellings` yields the two *endpoint* spellings (abspath, full realpath), so a
*composed* alias — the CLI invoked through the checkout's real path while `--out` is typed through an inward link to the
checkout (`/a -> <repo>`, `--out /a/samples/escape/j`) AND `samples/escape` is itself an outward link — shares a prefix
with neither spelling of `<repo>/samples` and is not refused (invoke through `/a` and it is: `repo_root()` is then `/a`).
Closing that class means resolving every lexical *prefix* of the path physically (`realpath(ap[:i]) + ap[i:]` per
component boundary — O(depth²) `lstat`s once per job, plus drive-letter care on Windows); not done here: the DONE is the
two-endpoint form, the precondition is three contrivances deep (write access inside git-ignored `samples/` + an inward
alias + invoking through the other name), and no corpus byte becomes readable through any of it. Offered to the tech
lead as a follow-up rather than filed, to keep the queue free of a P3.

Why both spellings and not "lexical only": the inward aliases (#425 review D3/D5, #452's `treelink -> <repo>` and
`/Samples/x`) are only visible physically; the outward link only lexically. Cross pairs (lexical path vs physical root
and v.v.) can only match when the path really is under the root by some name, so they add no false positive: a dir
merely NAMED `samples` elsewhere, an outward link from a non-quarantine dir of the tree (`<repo>/out -> /elsewhere`), and
a link placed OUTSIDE the checkout pointing outside it (`~/home -> /disk`, a `samples/` under it) match under neither
spelling — measured below and pinned in the tests.

Rule 2: the judgement is strings + `realpath` (`lstat`/`readlink` of path components) exactly as before — `_spellings`
already computed both; `out_dir_refusal` still tests the Autodesk-install markers on the lexical string FIRST and returns
before any `realpath` for such a path (strace below: zero file syscalls naming the Autodesk-shaped `--out` on head, as on
main).

## Evidence (uid `nobody`, `env -i`, this checkout = the tree itself; main = a `git worktree` of `origin/main` @ e3579ea with its own `samples/escape`)

Setup per tree `T`: `mkdir T/samples; ln -s /tmp/x474/elsewhere-<tag> T/samples/escape`.

| case | `--out` | main @ e3579ea | this head |
|---|---|---|---|
| **outward link inside `samples/`** (prompt route, `tools/frontdoor.py author --prompt "a room with four walls" --json`) | `T/samples/escape/j` | **rc 0**, `status PROOF-ONLY (self-checks PASS…)`, `files {"combined": "samples/escape/j/prompt_room.rvt"}` (repo-relative — `is_autodesk_sample(<lexical>) -> True`); 9 entries physically in `/tmp/x474/elsewhere-main/j` (`prompt_room.rvt` 581 632 B, manifest, HANDOFF, intent, `_stages/…`) | **rc 2**, stderr ONE line `[frontdoor] usage error: --out refused (nothing built): it lies inside this checkout's quarantined samples/ directory, whose files the build may never read -- choose another --out than /home/user/tekton/samples/escape/j`; stdout 0 bytes; `/tmp/x474/elsewhere-head` empty; `T/samples/escape/j` never created |
| same, **edit route** (`--rvt T/plugin/assets/genesis/G_ABPD_2025.rvt --edit "set level 311 elevation to 5 ft"`) | `T/samples/escape/e` | rc 0, `files {"edited": "/tmp/x474/main/samples/escape/e/G_ABPD_2025.edited.rvt"}`, 7 files physically in `elsewhere-main/e` | rc 2, the same one line (`… than /home/user/tekton/samples/escape/e`), nothing created |
| same, **`tools/route.py run --output rvt --prompt …`** | `T/samples/escape/r` | rc 0, ONE JSON `"ok": true, "status": "PROOF-ONLY (self-checks PASS…)"`, 12 files physically in `elsewhere-main/r` incl. `prompt_room.rvt` | before the rebase (main @ e3579ea underneath): rc 3, ONE JSON `"status": "FAILED (… FrontDoorError: --out refused (nothing built): … than …/samples/escape/r)"` — engine refused, but the router's own `ROUTE.md`/`route.json`/`route.log` still landed through the link; **after rebasing onto 4cc81dd (PR #493 merged, `router.route()` calls `out_dir_refusal` before its own `makedirs`)**: rc 2, stderr ONE line `[route] usage error: --out refused (nothing built): it lies inside this checkout's quarantined samples/ directory, … than /home/user/tekton/samples/escape/r`, stdout empty, `elsewhere-head` 0 entries — the router inherits `_inside` with no change of its own |
| **inward link OUTSIDE the tree pointing INTO `T/samples`** (`ln -s T/samples /tmp/x474/inward-<tag>`) | `/tmp/x474/inward-<tag>/j` | rc 2, the one line, `T/samples/j` absent | rc 2, the one line, `T/samples/j` absent (unchanged: the physical spelling catches it) |
| **merely NAMED** `samples` elsewhere | `/tmp/x474/samples/j-<tag>` | rc 0, `PROOF-ONLY (self-checks PASS…)`, `combined` delivered | rc 0, identical |
| Autodesk-shaped (`strace -f -e trace=%file`) | `"/tmp/x474/Program Files/Autodesk/Revit 2026/j"` | rc 2 (install-dir line); file syscalls naming `Autodesk`: **1** = the `execve` argv itself | rc 2; **1** = the `execve` argv — no `open`/`stat`/`readdir` of it, same as main (re-checked after the second bullet gained its `realpath` leg: still 0 beyond `execve` — the lexical test short-circuits) |
| **link into an Autodesk-named dir** (`/tmp/x474/adlink -> "/tmp/x474/pf/Program Files/Autodesk/Revit 2026"`, a plain tmp dir named like an install dir) | `/tmp/x474/adlink/j-<tag>` | rc 0 — a whole job (9 files, `prompt_room.rvt` among them) written physically under `…/Program Files/Autodesk/Revit 2026/j-main` (first attempt with the target root-owned: rc 1 `PermissionError` from its `makedirs` there) | rc 2, `… it lies inside an Autodesk installation directory, which tekton never reads or writes -- choose another --out than /tmp/x474/adlink/j-head`; target dir empty |
| outward link under strace (head) | `T/samples/escape/s` | — | the only syscalls touching `samples/escape`: 2× `newfstatat(…, AT_SYMLINK_NOFOLLOW)` + 2× `readlink` (the `realpath` walk, which main did too); no `open`, no `mkdir` |

(One instrument note, so nobody misreads a stray number: main's outward prompt and `route.py` runs first showed rc 3
`NO-OUTPUT` when launched with cwd = the *head* tree — `build.files` keeps repo-relative spellings for paths under
`<repo>/`, and `manifest.py`'s `isfile()` then resolved `samples/escape/j/prompt_room.rvt` against the wrong tree.
Re-run with cwd = main's own tree: rc 0 as tabled. The files were physically delivered through the link every time.)

## Tests

`tests/test_out_dir_guard.py` (already in the shard via `tests/ci_shard.d/425-out-dir-guard.txt`; no new drop-in) gains
a `tree` fixture (a checkout root of its own under tmp with a real `samples/` and an `elsewhere/` beside it,
`repo_root` monkeypatched — never near this repo's `samples/`) and a `_symlink()` helper that `pytest.skip`s where the FS
cannot symlink, plus 7 cases: the outward link is refused with the one line (case-blind too), arming with it leaves
`_GUARD["outputs"] == ()`, opens under its lexical spelling still trip, `elsewhere/` stays empty; the inward link outside
the tree is refused by its physical spelling; three negatives (`named`, `tree_out_link` = `<tree>/out -> elsewhere`,
`foreign_link` = `<tmp>/home -> elsewhere` with `samples/j` under it) are NOT refused and are exempt under both
spellings while `<tree>/samples/some.rvt` still trips; a link into a dir named `Program Files/Autodesk/Revit 2026` is
refused with the install-dir line; and end to end `FD.author(prompt=…, out=<tree>/samples/escape/j)` raises
`FrontDoorError` whose `str` == `out_dir_refusal(out)` with nothing created under the link or beyond it. Against main's
`standalone.py` (stashed back) the outward, Autodesk-link and end-to-end cases FAIL (`3 failed, 33 passed`); on this
head `36 passed` — matched pairs. The 29 existing cases and #452/#473's `test_frontdoor.py` refusal tests are untouched
(`/simplify`'s reuse lens noted `_symlink` is the third copy of the symlink-or-skip idiom in this file; the two older
copies live in the frozen tests/fixture and stay as they are this round).

## Follow-up delivered as a patch (outside this territory)

`src/rvt/frontdoor/__init__.py::run.__doc__` still ends "its one known hole -- an outward symlink planted inside
``samples/`` -- is #474's to close." — true until this merges, stale after. The brief put `__init__.py` out of bounds
(PR traffic in that file today), so the one-sentence edit is offered here for the tech lead to wave into this PR or the
next one touching the file:

```diff
-    predicate judges the dir's PHYSICAL location (symlinks resolved, case
-    folded), so every alias of the checkout is caught; its one known hole --
-    an outward symlink planted inside ``samples/`` -- is #474's to close."""
+    predicate judges BOTH the dir's lexical spelling and its physical
+    location (symlinks resolved, case folded), so every alias of the
+    checkout -- and an outward link planted inside ``samples/`` (#474) --
+    is caught."""
```

## Gates

* Stream-local: `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_out_dir_guard.py -q -rs` → **36 passed** (0.17 s;
  29 before + 7); neighbours `tests/test_frontdoor.py -k "out_dir or refus"` → **12 passed / 1 skipped** (chmod-as-root).
* Whole merged CI shard (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`):
  a first reading taken while `/simplify` fixes were still being applied to `standalone.py` showed `1 failed
  (test_plugin_sync::test_plugin_is_in_sync_with_source — the mirror lagged the source at that instant), 1695 passed,
  139 skipped, 3 xfailed` in 496 s and is VOID as a reading (the tree moved under it); the reading that counts is the
  re-run on the final, re-synced tree: **1697 passed / 139 skipped / 3 xfailed / 0 failed** in 471.9 s.
* `tools/sync_plugin.py` → 1 file synced (`plugin/lib/src/rvt/frontdoor/standalone.py`), deny-audit clean, identity scan
  == allowlist, validation passed, zip rebuilt (5237 KB); `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25
  assertions); `tools/dev/check_portable_paths.py` ok (2923 paths with this record).
* `/simplify` (4 lenses): applied — mechanism-only docstrings on `_canons`/`_inside` claiming exactly "both spellings",
  policy + #474 narrative only in `out_dir_refusal` (altitude/simplification); the Autodesk-install bullet judged on both
  spellings (altitude: one policy function, one law); test asserts decoupled from `SA._spellings` and a redundant fixture
  assert dropped (simplification). Skipped — folding the two older symlink-or-skip copies into `_symlink` (reuse: they
  sit in the frozen tests); hoisting `_canons(ap)` out of the 4-root loop (efficiency: 8 → 5 `realpath`s once per job,
  µs, would split `_inside`'s two-argument contract — the lens itself said not worth it).
* `/verify` (this head, uid `nobody`, `env -i`, system `python3` 3.11.15, bare unzip of the rebuilt `tekton-plugin.zip`
  under git-ignored `out/verify/pz`, no repo on the path): `go author --prompt "an electrical room with 6 panels" --out
  out/j1 --json` → rc 0, ONE JSON, `go.ready true`, `exit_code 0`, job 6.7 s, `PROOF-ONLY (self-checks PASS; …)`,
  `combined` + `families_dir`, `errors []`; `rvt_validate` on that `prompt_room.rvt` → `ok true`, 0 errors / 1 (known
  DataStorage) warning, and the same on the merely-named `/tmp/x474/samples/j-head/prompt_room.rvt`. The refusal through
  the bundle too (`lib/samples/escape -> /tmp/x474/elsewhere-head`, `--out lib/samples/escape/pz`): rc 2, `{"go":
  {"ready": true, "exit_code": 2}, "result": null}` + the one stderr line, `elsewhere-head` untouched. Validates, not
  "loads" (rule 4); nothing staged for the viewer. Full suite NOT run (SUITE-COORDINATION); no format byte changes.

## BRANCH STATE (eng #474)

* Branch `cam/474-out-dir-symlink` from `origin/main` @ e3579ea, rebased onto 4cc81dd (#493/#494/#495 merged
  underneath; no conflicts; `sync_plugin.py --check` clean and `tests/test_out_dir_guard.py tests/test_router.py
  tests/test_frontdoor.py -k "out_dir or refus or quarantin"` → 78 passed / 1 skipped on the rebased head).
* Files written: `src/rvt/frontdoor/standalone.py` (§7: `_canon` → `_canons`, `_inside`, `out_dir_refusal`'s docstring
  + the second bullet's `realpath` leg — nothing else in the file), `tests/test_out_dir_guard.py` (+ `tree` fixture,
  `_symlink` helper, 7 cases; the 29 existing untouched), `docs/inbox/out-dir-symlink.md` (this record, new file);
  regenerated mirror `plugin/lib/src/rvt/frontdoor/standalone.py`. No shard drop-in needed (the test file is already
  listed by `tests/ci_shard.d/425-out-dir-guard.txt`).
* Not touched, by instruction: `src/rvt/frontdoor/__init__.py` (stale `run()` docstring sentence — patch above),
  `router.py` (#473 / PR #493 — its own `ROUTE.md`/`route.json`/`route.log` still land through the link before the
  engine refuses), `tools/frontdoor.py`.
* Follow-ups: none filed. Two offered to the tech lead in the PR: (a) the three-line `run()` docstring patch above;
  (b) the composed-alias residual (prefix-wise `realpath`), P3 at most — say the word and it becomes an issue.
* Nothing awaits a human; nothing staged vs shipped — everything in this PR ships.
