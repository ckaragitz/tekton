"""The stream-record layout law (#636; the convention is docs/inbox/README.md).

A record is docs/inbox/<stream>.md, or that file kept as a short index plus one fragment per PR under
docs/inbox/<stream>.d/ (new files never conflict, shared ends of file do -- #328's drop-in trick). The law is a pure
function over inbox-relative names, `layout_violations(names)`, and since #638 it lives in the merge-time names gate
tools/dev/check_portable_paths.py, whose `check(paths)` calls it: that is the seam tools/dev/ci_fresh.sh re-runs over
the post-merge name set (#522), so an index deleted by a PR while main adds a fragment beside it is STALE there, not
red on main. The law:
  * every <stream>.d/*.md is named <digits>-<slug>.md (issue number first, portable slug after);
  * every <stream>.d/ that holds files has its index <stream>.md.
Pinned on the real docs/inbox as it lies in the WORKING TREE (untracked files are judged too -- stricter than git
locally, identical in CI; #636's own fragment makes it non-vacuous), on a planted tmp_path tree that is lawful first
and lawless after, and through `check()` with repo-relative names. Names only, nothing under docs/ is opened:
registered as such in tests/test_ci_fresh.py NAMES_NOT_READS. Fresh-clone runnable; stdlib only.
"""
import os

import pytest

from conftest import ROOT, load_tool

checker = load_tool("dev/check_portable_paths")
INBOX = os.path.join(ROOT, "docs", "inbox")
OWN = "process-friction.d/636-record-fragments.md"                    # the law's own record, the first fragment ever written


def inbox_names(inbox):
    """Every file under ``inbox`` as an inbox-relative posix name (the gatherer; the law itself never touches a disk)."""
    return sorted(os.path.relpath(os.path.join(base, f), inbox).replace(os.sep, "/")
                  for base, _, files in os.walk(inbox) for f in files)


def test_the_real_inbox_obeys_the_layout_law():
    names = inbox_names(INBOX)
    assert OWN in names and OWN.split("/")[0][:-2] + ".md" in names       # the walker sees fragments: the verdict below is not vacuous
    assert checker.layout_violations(names) == []


def test_a_planted_tree_is_lawful_until_a_bad_fragment_or_an_orphan_directory_is_planted(tmp_path):
    def plant(*rels):
        for rel in rels:
            p = tmp_path.joinpath(*rel.split("/"))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# %s\n" % rel, encoding="utf-8")
        return checker.layout_violations(inbox_names(str(tmp_path)))

    assert plant("solo.md", "shared.md", "shared.d/636-first.md", "shared.d/7-x_y.z-2.md", "shared.d/636-evidence.json",
                 "results/anything.txt", "notes.d.md", "deep.md", "deep.d/1-a.md", "deep.d/sub/free-form.md") == []
    assert plant("shared.d/appendix.md", "orphan.d/636-x.md", "orphan.d/9-evidence.json") == [   # the mutation: same tree, two breaches
        ("orphan.d/ has no index orphan.md beside it", ["orphan.d/636-x.md", "orphan.d/9-evidence.json"]),   # every file the orphan holds is involved
        ("shared.d/appendix.md is not named <issue>-<slug>.md", ["shared.d/appendix.md"])]


@pytest.mark.parametrize("names, expected", [
    (["s.md", "s.d/record.md", "s.d/-636-x.md"], ["s.d/-636-x.md", "s.d/record.md"]),               # no issue number first
    (["s.md", "s.d/636.md", "s.d/636-.md", "s.d/636-bad name.md"], ["s.d/636-.md", "s.d/636-bad name.md", "s.d/636.md"]),   # number, no portable slug
])
def test_misnamed_fragments_are_each_named(names, expected):
    assert checker.layout_violations(names) == [("%s is not named <issue>-<slug>.md" % n, [n]) for n in expected]


def test_check_feels_the_law_over_repo_relative_names_and_only_under_docs_inbox():
    """#638: the merge-time gate is check(paths) over repo-relative names (tools/dev/ci_fresh.sh hands it the post-merge
    set), so the law must fire through it -- with the checker's usual (problem line, names involved) shape and the
    involved names repo-relative again -- for docs/inbox/ paths, and stay silent for the same shapes anywhere else
    (tests/ci_shard.d/ drop-ins are <issue>-<slug>.txt files with no index, lawfully)."""
    merged = ["src/a.py", "docs/inbox/kept.md", "docs/inbox/kept.d/1-x.md",           # a lawful index + fragment
              "docs/inbox/old.d/1-x.md",                                              # main added the fragment, the PR deleted docs/inbox/old.md
              "docs/inbox/kept.d/notes.md",                                           # a fragment named before the law
              "tests/ci_shard.d/328-x.txt", "elsewhere/orphan.d/appendix.md"]        # not records: not judged by this law
    assert checker.check(merged) == [
        ("record layout (docs/inbox/README.md): kept.d/notes.md is not named <issue>-<slug>.md", ["docs/inbox/kept.d/notes.md"]),
        ("record layout (docs/inbox/README.md): old.d/ has no index old.md beside it", ["docs/inbox/old.d/1-x.md"]),
    ]
    assert checker.check(merged[:3] + merged[5:]) == []
