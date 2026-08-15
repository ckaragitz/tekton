"""tools/dev/check_portable_paths.py -- the portable-paths gate as a pure function plus a CLI over `git ls-files`.

`check(names)` is the seam tools/dev/ci_fresh.sh imports at merge time to re-run THE gate over the post-merge name
set (#522), so its contract is pinned here: every portability law (per-name and the cross-file case-twin law) reported
as (problem line, names involved) in the order the CLI prints them, no git and no filesystem behind it (the docs/inbox
record-layout law check() also carries since #638 is pinned in tests/test_records_layout.py, same shape). The CLI is
pinned too -- its output did not change when the seam went in. Fresh-clone runnable: stdlib (+ git for the CLI rows).
Non-ASCII names below are spelled with escapes on purpose: an NFC/NFD pair is invisible in source (#724).
"""
import sys

import pytest

from conftest import HAVE_GIT, ROOT, git, git_commit, load_tool

checker = load_tool("dev/check_portable_paths")
LONG = "x/" + "y" * 240
NFC, NFD = "w/caf\u00e9.md", "w/cafe\u0301.md"                        # café precomposed / e + COMBINING ACUTE ACCENT: two names to git, one file to APFS
LATIN1 = b"w/latin1\xe9.md".decode("utf-8", "surrogateescape")       # a cp1252/Latin-1 tool's é: not UTF-8 at all, as this CLI's gatherer hands it over


def test_check_reports_every_law_with_the_names_involved_in_cli_order():
    names = ["w/a.md", "w/A.md", "w/aux.md", "w/b:c.md", NFC, "w/d./e.md", LATIN1, LONG, "w/inbox/foo.md", NFD, "w/inbox/foo.md", "src/ok.py"]
    assert checker.check(names) == [
        ("reserved device name on Windows: 'w/aux.md'", ["w/aux.md"]),
        ("illegal character for Windows: 'w/b:c.md'", ["w/b:c.md"]),
        ("trailing dot/space in component: 'w/d./e.md'", ["w/d./e.md"]),
        ("not valid UTF-8: b'w/latin1\\xe9.md'", [LATIN1]),
        ("path too long (242 > 240): x/%s..." % ("y" * 98), [LONG]),
        ("case-only collision (breaks case-insensitive filesystems): ['w/a.md', 'w/A.md']", ["w/a.md", "w/A.md"]),
        ("case-only collision (breaks case-insensitive filesystems): ['w/inbox/foo.md', 'w/inbox/foo.md']", ["w/inbox/foo.md", "w/inbox/foo.md"]),   # a repeated name (both sides of a merge add it) is a group too
        ("normalisation-only collision (breaks macOS checkouts): ['w/caf\\xe9.md', 'w/cafe\\u0301.md']", [NFC, NFD]),   # after every case group; ascii()-spelled, or the twins would print identically
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


def test_names_a_macOS_checkout_folds_together_are_refused_once_per_law_they_break():
    """#724: APFS/HFS+ are normalisation-insensitive the way NTFS is case-insensitive, so NFC/NFD twins are the second
    cross-file law. The two laws partition cleanly and deterministically: a pair differing only by form is the
    normalisation law's alone; a pair differing by case AND form (Café NFC vs café NFD -- one file only on a
    case-insensitive volume) is the case law's alone; a name that twins one sibling by case and another by form shows up
    once under each; a lone NFC or NFD name, or a repeated identical one, changes nothing that was true before."""
    UPPER = "w/Caf\u00e9.md"
    case = lambda group: ("case-only collision (breaks case-insensitive filesystems): %r" % group, group)
    norm = lambda group: ("normalisation-only collision (breaks macOS checkouts): %s" % ascii(group), group)
    assert checker.check([NFC, NFD]) == [norm([NFC, NFD])]
    assert checker.check([UPPER, NFD]) == [case([UPPER, NFD])]
    assert checker.check([NFC, UPPER, NFD]) == [case([NFC, UPPER, NFD]), norm([NFC, NFD])]
    assert checker.check([NFC]) == checker.check([NFD]) == checker.check([NFC, "w/cafe.md"]) == []
    assert checker.check([NFD, NFD]) == [case([NFD, NFD])]                       # a repeat stays the case law's group, exactly as for ASCII names...
    assert checker.check([NFC, NFC, NFD]) == [norm([NFC, NFC, NFD])]             # ...unless a form-twin rides along: then the whole group is the normalisation law's, once
    assert checker.check(["w/J\u030c.md", "w/\u01f0.md"]) == [case(["w/J\u030c.md", "w/\u01f0.md"])]   # fold on the DEcomposed form: capital J + caron has no precomposed spelling, the small letter has
    assert checker.check(["w/stra\u00dfe.md", "w/strasse.md"]) == []            # lower(), not casefold(): these are two files on every filesystem in use here


def test_a_name_that_is_not_valid_utf8_is_refused_however_the_gatherer_decoded_it():
    """#724: git stores bytes; a name written by a cp1252 tool cannot be checked out sanely on macOS or by most Windows
    tooling. This CLI decodes `git ls-files -z` with surrogateescape (the law then spells the real bytes);
    tools/dev/ci_fresh.sh decodes with `replace` and is deliberately left alone, so the U+FFFD it leaves behind is
    refused too -- worded as the property of the name it is, since check() cannot know who replaced the byte."""
    assert checker.check([LATIN1]) == [("not valid UTF-8: b'w/latin1\\xe9.md'", [LATIN1])]
    replaced = b"w/latin1\xe9.md".decode("utf-8", "replace")
    assert checker.check([replaced]) == [("replacement character U+FFFD in name (an undecodable byte was replaced somewhere upstream): 'w/latin1\\ufffd.md'", [replaced])]


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


@pytest.mark.skipif(not HAVE_GIT, reason="needs git")
@pytest.mark.skipif(sys.platform in ("win32", "darwin"), reason="APFS folds the twins / refuses the Latin-1 name at creation, NTFS likewise -- that is the law")
def test_the_cli_reads_names_bytes_faithfully_and_names_both_new_laws(git_repo, monkeypatch, capsys):
    """End to end through `git ls-files -z`: the gatherer must hand check() the NFD twin unchanged and the Latin-1 name
    un-mangled (surrogateescape), and printing the verdict must not die on that name (#724)."""
    git_commit(git_repo, {NFC: "c\n", NFD: "d\n", LATIN1: "l\n", "w/ok.md": "o\n"}, "names a macOS checkout cannot hold")
    if len(git(git_repo, "ls-files").splitlines()) < 4:      # ASCII-safe: under the rig's default core.quotePath git C-quotes all three names
        pytest.skip("this filesystem folded the twins or refused a name: nothing to gather")
    monkeypatch.chdir(git_repo)
    assert checker.main() == 1
    assert capsys.readouterr().out == ("NON-PORTABLE PATHS:\n"
                                       "  not valid UTF-8: b'w/latin1\\xe9.md'\n"
                                       "  normalisation-only collision (breaks macOS checkouts): ['w/cafe\\u0301.md', 'w/caf\\xe9.md']\n")   # git ls-files order (bytes: e+CC 81 sorts before C3 A9)
