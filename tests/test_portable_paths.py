"""tools/dev/check_portable_paths.py -- the portable-paths gate as a pure function plus a CLI over `git ls-files`.

`check(names)` is the seam tools/dev/ci_fresh.sh imports at merge time to re-run THE gate over the post-merge name
set (#522), so its contract is pinned here: every portability law (per-name and the cross-file case-twin law) reported
as (problem line, names involved) in the order the CLI prints them, no git and no filesystem behind it (the docs/inbox
record-layout law check() also carries since #638 is pinned in tests/test_records_layout.py, same shape). The CLI is
pinned too -- its output did not change when the seam went in. Fresh-clone runnable: stdlib (+ git for the CLI rows).
"""
import sys

import pytest

from conftest import HAVE_GIT, ROOT, git, git_commit, load_tool

checker = load_tool("dev/check_portable_paths")
LONG = "x/" + "y" * 240


def test_check_reports_every_law_with_the_names_involved_in_cli_order():
    names = ["w/a.md", "w/A.md", "w/aux.md", "w/b:c.md", "w/d./e.md", LONG, "w/inbox/foo.md", "w/inbox/foo.md", "src/ok.py"]
    assert checker.check(names) == [
        ("reserved device name on Windows: 'w/aux.md'", ["w/aux.md"]),
        ("illegal character for Windows: 'w/b:c.md'", ["w/b:c.md"]),
        ("trailing dot/space in component: 'w/d./e.md'", ["w/d./e.md"]),
        ("path too long (242 > 240): x/%s..." % ("y" * 98), [LONG]),
        ("case-only collision (breaks case-insensitive filesystems): ['w/a.md', 'w/A.md']", ["w/a.md", "w/A.md"]),
        ("case-only collision (breaks case-insensitive filesystems): ['w/inbox/foo.md', 'w/inbox/foo.md']", ["w/inbox/foo.md", "w/inbox/foo.md"]),   # a repeated name (both sides of a merge add it) is a group too
    ]
    assert checker.check(["w/a.md", "src/b.py", "w/console/aux-iliary.md"]) == []   # reserved names are whole stems (up to the first dot), not prefixes


def test_control_characters_and_DEL_are_illegal_while_non_ascii_names_are_portable():
    """The illegal-character class is exactly the byte set git C-quotes even with core.quotePath=false (0x00-0x1f,
    DEL 0x7f, the double quote, the backslash) plus Windows' own <>:|?* -- so tools/dev/ci_fresh.sh may read any docs
    name git still quotes as one this gate refuses (#540; DEL was the one byte the two disagreed on). Bytes above 0x7f
    are somebody's alphabet, not a portability problem: café, ü and a no-break space pass."""
    for bad in ("w/tab\there.md", "w/unit\x1fsep.md", "w/del\x7fete.md", 'w/we"ird.md', "w/back\\slash.md"):
        assert checker.check([bad]) == [("illegal character for Windows: %r" % bad, [bad])], bad
    assert checker.check(["w/inbox/café notes.md", "w/ünïcode.md", "w/nbsp\xa0x.md"]) == []   # w/, not docs/: a docs/ literal here would read as a docs reference to test_ci_fresh.py's SHARD_READS scanner


@pytest.mark.skipif(not HAVE_GIT, reason="needs git")
def test_the_cli_is_check_over_git_ls_files_and_this_checkout_passes(monkeypatch, capsys):
    tracked = [p for p in git(ROOT, "ls-files", "-z").split("\0") if p]
    monkeypatch.chdir(ROOT)
    assert checker.main() == 0
    assert capsys.readouterr().out == "ok: %d tracked paths are portable\n" % len(tracked)


@pytest.mark.skipif(not HAVE_GIT, reason="needs git")
@pytest.mark.skipif(sys.platform == "win32", reason="the offending names cannot be created on Windows -- that is the law")
def test_the_cli_names_every_problem_and_exits_1(git_repo, monkeypatch, capsys):
    git_commit(git_repo, {rel: "x\n" for rel in ("w/A.md", "w/a.md", "w/aux.md", "d./e.md")}, "bad")
    if len(git(git_repo, "ls-files").splitlines()) < 4:
        pytest.skip("case-insensitive filesystem: w/A.md and w/a.md are one file here")
    monkeypatch.chdir(git_repo)
    assert checker.main() == 1
    assert capsys.readouterr().out == ("NON-PORTABLE PATHS:\n"
                                       "  trailing dot/space in component: 'd./e.md'\n"
                                       "  reserved device name on Windows: 'w/aux.md'\n"
                                       "  case-only collision (breaks case-insensitive filesystems): ['w/A.md', 'w/a.md']\n")
