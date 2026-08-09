#!/usr/bin/env python3
"""Print the CI test shard: tests/ci_shard.txt followed by every tests/ci_shard.d/*.txt drop-in (#328).

Why drop-ins: every PR that shards a new test used to append one line to the same spot of
tests/ci_shard.txt, so any two such PRs conflicted on merge. A PR now adds its own file
tests/ci_shard.d/<issue>-<slug>.txt instead; this helper produces the one list everybody runs.

Rules (the same ones tools/dev/session_ci.sh enforced on the single file before this existed):
  * one path per line; blank lines and whole-line `#` comments are ignored; surrounding whitespace
    (and a Windows CR) is stripped;
  * tests/ci_shard.txt comes first in its own order (tests/test_schema_gate.py stays first), then the
    drop-ins sorted by file name; a path listed twice anywhere is kept once, first occurrence wins;
  * every entry must be a plain test file `tests/[A-Za-z0-9_./-]+.py` with no `..` -- no pytest
    flags, no other directories -- and the resulting list must be non-empty; drop-in file names are
    `[A-Za-z0-9][A-Za-z0-9_.-]*.txt` (anything else in the directory that ends in .txt is refused,
    anything that does not -- README -- is ignored). One bad entry refuses the whole list (exit 3).

Two sources, one merge:
  python3 tools/dev/shard_list.py [--print] [--root DIR]   the working tree (contributors, the reference ci.yml)
  python3 -I REPO/tools/dev/shard_list.py --git WT          git BLOBS of HEAD in worktree WT (session_ci.sh's
      trusted side: `git ls-tree` + `git cat-file` only, never the checked-out files, so nothing a
      sandboxed PR step did to its copy of the tree can change what the privileged side reads)
Stdlib only; prints one path per line on stdout, diagnostics on stderr; exit 0 ok, 3 refused, 2 usage/IO.
"""
import os, re, subprocess, sys

BASE = "tests/ci_shard.txt"
DROPIN_DIR = "tests/ci_shard.d"
ENTRY = re.compile(r"^tests/[A-Za-z0-9_./-]+\.py$")
DROPIN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.txt$")


class Refused(Exception):
    pass


def parse(text):
    """Text of one shard file -> its entries (comments/blanks dropped, whitespace stripped, unvalidated)."""
    lines = (ln.strip() for ln in text.splitlines())
    return [ln for ln in lines if ln and not ln.startswith("#")]


def merge(base_text, dropins):
    """base_text + [(name, text), ...] in any order -> the validated, de-duplicated shard list (raises Refused)."""
    bad = sorted(n for n, _ in dropins if not DROPIN_NAME.match(n))
    if bad:  # diagnostics are bounded: names and entries are PR-controlled text
        raise Refused("drop-in file names must match %s, first: %s" % (DROPIN_NAME.pattern, " ".join(repr(n[:80]) for n in bad[:5])))
    entries = parse(base_text)
    for _, text in sorted(dropins):
        entries.extend(parse(text))
    bad = [e for e in entries if not ENTRY.match(e) or ".." in e]
    if bad:
        raise Refused("%d invalid shard entries (plain tests/*.py paths only), first: %s" % (len(bad), " ".join(repr(e[:80]) for e in bad[:5])))
    shard = list(dict.fromkeys(entries))  # first occurrence wins, order kept
    if not shard:
        raise Refused("empty shard list (bare pytest would collect the whole suite)")
    return shard


def from_tree(root):
    """Read the base file and the drop-ins from a working tree."""
    with open(os.path.join(root, BASE), encoding="utf-8") as fh:
        base_text = fh.read()
    d = os.path.join(root, DROPIN_DIR)
    dropins = []
    for name in (os.listdir(d) if os.path.isdir(d) else []):
        p = os.path.join(d, name)
        if name.endswith(".txt") and os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                dropins.append((name, fh.read()))
    return base_text, dropins


def from_git(worktree):
    """Read the base file and the drop-ins from the git objects of HEAD -- blobs only, never the checkout."""
    def git(*args):
        return subprocess.run(["git", "-C", worktree, *args], capture_output=True, check=True).stdout

    base_sha, dropins = None, []
    for rec in git("ls-tree", "-z", "HEAD", "--", BASE, DROPIN_DIR + "/").split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, otype, sha = meta.split(b" ")
        path, sha = path.decode("utf-8", "replace"), sha.decode()
        if otype != b"blob" or mode not in (b"100644", b"100755"):
            continue  # symlinks, submodules and subtrees are not shard files
        if path == BASE:
            base_sha = sha
        elif path.endswith(".txt"):
            dropins.append((path.rsplit("/", 1)[1], git("cat-file", "blob", sha).decode("utf-8", "replace")))
    if base_sha is None:
        raise Refused("%s is not a regular file at HEAD" % BASE)
    return git("cat-file", "blob", base_sha).decode("utf-8", "replace"), dropins


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."),
                     help="working tree to read (default: the checkout this script lives in)")
    src.add_argument("--git", metavar="WORKTREE", help="read the git blobs of HEAD in this worktree instead of files")
    ap.add_argument("--print", action="store_true", help="print one path per line (the default and only action)")
    a = ap.parse_args(argv)
    try:
        shard = merge(*(from_git(a.git) if a.git else from_tree(a.root)))
    except Refused as e:
        print("shard list refused: %s" % e, file=sys.stderr)
        return 3
    except (OSError, subprocess.CalledProcessError) as e:
        print("shard list unreadable: %s" % e, file=sys.stderr)
        return 2
    sys.stdout.write("".join(p + "\n" for p in shard))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
