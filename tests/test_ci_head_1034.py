"""#1034: CI never tests, and the merge gate never accepts, a PR head older than the PR's current one.

On #1031 four ~20-minute session_ci.sh runs tested refs/pr/1031 as first fetched (1499a8b) while the PR moved on
four times, and ci_fresh.sh, comparing only main, said FRESH. Now tools/dev/pr_head.sh re-fetches refs/pr/<n> when
origin's refs/pull/<n>/head differs (session_ci.sh calls it before anything is tested), and ci_fresh.sh reads that
head from origin itself when no <head-sha> is given. Pinned on the same throwaway repos as tests/test_ci_fresh.py.
"""
import os
import shutil
import subprocess

import pytest

from conftest import GIT_ENV, HAVE_GIT, git, git_commit
from test_ci_fresh import rig  # noqa: F401  (the fixture)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PR_HEAD = os.path.join(ROOT, "tools", "dev", "pr_head.sh")

pytestmark = pytest.mark.skipif(not (shutil.which("bash") and HAVE_GIT), reason="needs bash + git")


def _clone(rig):
    return os.path.dirname(os.path.dirname(rig.ci))[: -len(os.sep + ".git")]


def _pr_head(clone, pr=7):
    out = subprocess.run(["bash", PR_HEAD, str(pr)], cwd=clone, env=GIT_ENV,
                         capture_output=True, text=True, timeout=60)
    return out.returncode, out.stdout.strip(), out.stderr.strip()


def _publish(rig, sha, pr=7):
    """origin's refs/pull/<pr>/head -> sha (what GitHub holds for a PR)."""
    git(rig.up, "update-ref", "refs/pull/%d/head" % pr, sha)


def test_a_ref_behind_the_prs_head_is_refreshed(rig):
    clone = _clone(rig)
    git(clone, "update-ref", "refs/pr/7", rig.head)            # what a first fetch left
    newer = git_commit(rig.up, {"src/later.py": "x\n"}, "a later push of PR 7")
    _publish(rig, newer)
    rc, out, err = _pr_head(clone)
    assert (rc, out) == (0, newer), err
    assert git(clone, "rev-parse", "refs/pr/7") == newer
    assert "refreshed refs/pr/7" in err


def test_a_ref_at_the_prs_head_is_left_alone(rig):
    clone = _clone(rig)
    git(clone, "update-ref", "refs/pr/7", rig.head)
    git(clone, "push", "-q", "origin", "%s:refs/pull/7/head" % rig.head)
    rc, out, err = _pr_head(clone)
    assert (rc, out, err) == (0, rig.head, "")


def test_an_origin_without_pr_refs_uses_the_local_ref_and_says_so(rig):
    clone = _clone(rig)
    git(clone, "update-ref", "refs/pr/7", rig.head)
    rc, out, err = _pr_head(clone)
    assert (rc, out) == (0, rig.head) and "used as is" in err
    rc, out, err = _pr_head(clone, pr=8)                        # neither a local ref nor a PR ref
    assert rc == 2 and "no refs/pr/8" in err


def test_an_unreadable_origin_is_a_refusal(rig):
    clone = _clone(rig)
    git(clone, "update-ref", "refs/pr/7", rig.head)
    git(clone, "remote", "set-url", "origin", os.path.join(clone, "no-such-remote"))
    rc, out, err = _pr_head(clone)
    assert rc == 2 and "ls-remote failed" in err


def test_ci_fresh_reads_the_prs_head_from_origin_when_none_is_given(rig):
    git(_clone(rig), "push", "-q", "origin", "%s:refs/pull/7/head" % rig.head)   # the head lives in the clone
    assert rig.fresh() == (0, "FRESH main=%s" % rig.was)       # the verdict is for the PR's head
    newer = git_commit(rig.up, {"docs/inbox/n.md": "n\n"}, "a later push")
    git(rig.up, "update-ref", "refs/heads/main", rig.was)       # main itself unmoved: only the PR moved
    _publish(rig, newer)
    rc, line = rig.fresh()
    assert rc == 5 and line.startswith("WRONG-HEAD json=%s now=%s" % (rig.head, newer)), line


def test_session_ci_confirms_the_head_before_testing_it():
    src = open(os.path.join(ROOT, "tools", "dev", "session_ci.sh"), encoding="utf-8").read()
    assert src.index("tools/dev/pr_head.sh") < src.index('HEAD=$(git rev-parse "refs/pr/$PR")')
    assert "SESSION_CI_OFFLINE" in src
    assert os.access(PR_HEAD, os.X_OK)
