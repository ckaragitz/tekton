# gitattributes-eol — issue #27

## What was built

Two independent Windows defects, found while setting up the first Windows clone
of this repo. The issue originally blamed both on line endings; that was wrong,
and the issue body has been corrected. Only one of them is a line-endings bug —
and it turned out to matter for a different, more serious reason than the one it
was filed for.

**1. `.gitattributes` (new).** `* text=auto eol=lf`, explicit `binary` for Revit
containers and the other binary types, and `-text` exemptions listed
file-by-file for the nine tracked blobs that already store CRLF.

**2. `src/rvt/schema_cache.py` — two lines.** `build_cache()` now emits
`index.json` deterministically across platforms.

## Evidence

### The PDF was silently corrupted on every Windows checkout

Git for Windows ships `core.autocrlf=true` in its system config. Its binary
detection only samples for NUL bytes, so a small PDF with no NUL early in the
file is classified as text and converted on checkout:

```
tekton-eval-kit/Tekton-Eval-Kit-Instructions.pdf
  stored blob  : 11,012 bytes
  working tree : 11,148 bytes    (+136 = one CR per line)
```

`git status` reported the tree **clean** the whole time, because it normalised
the file again when comparing. The corruption is invisible to git and to the
developer. After this branch, a Windows checkout yields 11,012 bytes starting
with `%PDF`.

### `.gitattributes` alone did NOT fix the drift

This is the correction. After adding `.gitattributes` and rebuilding the working
tree, `plugin/assets/schema_cache/index.json` went from 36 CRLF to 0 CRLF — and
`sync_plugin.py --check` **still** exited 1 on the same file. The drift has a
different cause, in the generator:

| | Windows generated | committed (Linux) |
|---|---|---|
| `sources` entries | `assets\genesis\G_ABPD.rvt` | `assets/genesis/G_ABPD.rvt` |
| file size | 1,122 bytes | 1,086 bytes |

Two bugs in `build_cache()`:

1. `os.path.relpath(src, plugin_root)` yields backslashes on Windows. Fixed by
   `.replace(os.sep, "/")` — `index.json` is a byte-compared build artifact, so
   it must not vary by host.
2. `open(path, "w")` in text mode translates `\n` to `\r\n` on Windows. That is
   the whole 36-byte delta: one per line. Fixed with `newline="\n"` (and
   `encoding="utf-8"` while there, per #29).

After both, a Windows box generates a file **byte-identical** to the committed
Linux-generated one (1,086 = 1,086), and the gate passes:

```
$ python tools/sync_plugin.py --check
plugin in sync with source (deny-audit clean, assets verified)
exit=0
```

### Content neutrality of `.gitattributes`

Nine tracked text blobs already store CRLF: vendored `olefile`
(`olefile.py`, `LICENSE.txt`, `CONTRIBUTORS.txt`, in both the `plugin/` and
`tekton-eval-kit/` trees) and `*shared-parameters.txt` in three locations.

A first attempt exempted `_vendor/**` directory-wide. That was wrong and the
check caught it: `-text` stores the working-tree bytes, so a directory-wide rule
captured LF-stored siblings (`_vendor/README.md`, `_vendor/olefile/__init__.py`)
and would have committed their CRLF-polluted working-tree copies. Exempting
file-by-file instead, `git add --renormalize .` stages **zero** content changes.

### Tests

- `tests/test_plugin_sync.py` — **7 passed** on Windows (was 1 failed, 6 passed).
- `tests/test_versions.py`, `tests/test_steplite.py` — green.
- `tests/test_coldstart.py` — 4 failures, identical to unmodified `main` on this
  machine and untouched by this branch. They are #29 (cp1252 text I/O).

## Findings

- **The drift guard was reporting a real defect, not noise.** It just wasn't the
  defect anyone assumed. Worth remembering next time a gate is red only on one
  platform: the first hypothesis (line endings) was plausible, cheap to test, and
  wrong, and the byte-count delta is what disambiguated it — 36 bytes over 36
  lines is a newline bug, not a content bug.
- **`git status` clean is not evidence a working tree matches the repo.** With
  `text=auto` in play, git normalises on compare and will hide a corrupted
  binary indefinitely. The byte-count comparison against `git cat-file blob` is
  the check that actually answers the question.
- Any file this repo generates and then byte-compares must be written with
  POSIX separators and explicit `newline`. `index.json` was the only one caught
  by the drift guard, but the same pattern is likely elsewhere — see #29's AST
  scan, which found 415 unqualified text opens.

## Open questions

- The full `python tools/sync_plugin.py` path still fails on Windows after this
  branch, at `rebuild_zip()`, which shells out to the Unix `zip` binary — filed
  as **#37**. `--check` is unaffected, so #27's DONE is met, but a Windows
  contributor still cannot run the build half of the tool.
- Neither bug here is reachable by CI (#2), which is `ubuntu-latest` only. A
  `windows-latest` job is the only thing that would have caught them, and is
  blocked on #29.

## BRANCH STATE

- Branch: `ckaragitz12/27-gitattributes-eol`, cut from `main` (`284ec48`).
- Files written:
  - `.gitattributes` (new)
  - `src/rvt/schema_cache.py` (2 lines)
  - `plugin/lib/src/rvt/schema_cache.py` (generated mirror, via `tools/sync_plugin.py`)
  - `docs/inbox/gitattributes-eol.md` (this record)
- Gates: `tools/sync_plugin.py --check` exit 0 on Windows;
  `tests/test_plugin_sync.py` 7 passed.
  `plugin/scripts/validate_plugin.py` still exits 1 on this branch — that is
  #26, fixed on PR #28, not in this territory.
- Staged vs shipped: shipped. No viewer certification claim.
