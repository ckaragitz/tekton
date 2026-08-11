"""The stream-record layout law (#636; the convention is docs/inbox/README.md).

A record is docs/inbox/<stream>.md, or that file kept as a short index plus one fragment per PR under
docs/inbox/<stream>.d/ (new files never conflict, shared ends of file do -- #328's drop-in trick). The law, as a pure
function over inbox-relative names so a names gate can host it later exactly like tools/dev/check_portable_paths.check:
  * every <stream>.d/*.md is named <digits>-<slug>.md (issue number first, portable slug after);
  * every <stream>.d/ that holds files has its index <stream>.md.
Pinned on the real docs/inbox as it lies in the WORKING TREE (untracked files are judged too -- stricter than git
locally, identical in CI; this PR's own fragment makes it non-vacuous) and on a planted tmp_path tree that is
lawful first and lawless after. Names only, nothing under docs/ is opened: registered as such in
tests/test_ci_fresh.py NAMES_NOT_READS. Fresh-clone runnable; stdlib only.
"""
import os
import re

import pytest

from conftest import ROOT

INBOX = os.path.join(ROOT, "docs", "inbox")
FRAGMENT = re.compile(r"^[0-9]+-[A-Za-z0-9][A-Za-z0-9_.-]*\.md$")   # <issue>-<slug>.md; slug class = tools/dev/shard_list.py DROPIN_NAME's
OWN = "process-friction.d/636-record-fragments.md"                    # this law's own record, the first fragment ever written


def violations(names):
    """Inbox-relative posix file names -> every breach of the layout law, one readable line each, sorted (empty = lawful).
    Only <stream>.d/<file>.md direct children are judged; single-file records, attachments, deeper paths are not."""
    names = set(names)
    out = set()
    for n in names:
        parts = n.split("/")
        if len(parts) != 2 or not parts[0].endswith(".d"):
            continue
        d, leaf = parts
        if d[:-2] + ".md" not in names:
            out.add("%s/ has no index %s.md beside it" % (d, d[:-2]))
        if leaf.endswith(".md") and not FRAGMENT.match(leaf):
            out.add("%s is not named <issue>-<slug>.md" % n)
    return sorted(out)


def inbox_names(inbox):
    """Every file under ``inbox`` as an inbox-relative posix name (the gatherer; the law itself never touches a disk)."""
    return sorted(os.path.relpath(os.path.join(base, f), inbox).replace(os.sep, "/")
                  for base, _, files in os.walk(inbox) for f in files)


def test_the_real_inbox_obeys_the_layout_law():
    names = inbox_names(INBOX)
    assert OWN in names and OWN.split("/")[0][:-2] + ".md" in names       # the walker sees fragments: the verdict below is not vacuous
    assert violations(names) == []


def test_a_planted_tree_is_lawful_until_a_bad_fragment_or_an_orphan_directory_is_planted(tmp_path):
    def plant(*rels):
        for rel in rels:
            p = tmp_path.joinpath(*rel.split("/"))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# %s\n" % rel, encoding="utf-8")
        return violations(inbox_names(str(tmp_path)))

    assert plant("solo.md", "shared.md", "shared.d/636-first.md", "shared.d/7-x_y.z-2.md", "shared.d/636-evidence.json",
                 "results/anything.txt", "notes.d.md", "deep.md", "deep.d/1-a.md", "deep.d/sub/free-form.md") == []
    assert plant("shared.d/appendix.md", "orphan.d/636-x.md") == [                       # the mutation: same tree, two breaches
        "orphan.d/ has no index orphan.md beside it", "shared.d/appendix.md is not named <issue>-<slug>.md"]


@pytest.mark.parametrize("names, expected", [
    (["s.md", "s.d/record.md", "s.d/-636-x.md"], ["s.d/-636-x.md", "s.d/record.md"]),               # no issue number first
    (["s.md", "s.d/636.md", "s.d/636-.md", "s.d/636-bad name.md"], ["s.d/636-.md", "s.d/636-bad name.md", "s.d/636.md"]),   # number, no portable slug
])
def test_misnamed_fragments_are_each_named(names, expected):
    assert violations(names) == ["%s is not named <issue>-<slug>.md" % n for n in expected]
