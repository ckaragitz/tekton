"""tools/dev/ci_fresh.sh -- a sandboxed-CI verdict is only valid against the `main` it was merged with (#487).

Incident #476: two PRs, each green against the origin/main of its own session_ci.sh run, collided semantically once
both landed. So session_ci.sh records that trunk as "main" in its one-line JSON, and the tick merges only when
ci_fresh.sh says FRESH against the origin/main re-fetched right before the merge. Tolerated drift = added/modified
docs/** that no shard test opens; everything else (code, the ledger/matrix/AUTONOMY docs, a docs deletion) is STALE.
Pinned here on a throwaway `git init` repo, plus the JSON field itself and the optional <head-sha> refusal.
Fresh-clone runnable: stdlib + git + bash only (skips where bash or git is absent).
"""
import json
import os
import shutil
import subprocess
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, "tools", "dev", "ci_fresh.sh")
SESSION_CI = os.path.join(ROOT, "tools", "dev", "session_ci.sh")

pytestmark = pytest.mark.skipif(not (shutil.which("bash") and shutil.which("git")), reason="needs bash + git")

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
E40 = "e" * 40


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True, timeout=60).stdout.strip()


def _commit(repo, files, msg, delete=()):
    for rel, text in files.items():
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    for rel in delete:
        os.remove(os.path.join(repo, rel))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def _verdict(ci_dir, pr, **fields):
    with open(os.path.join(ci_dir, "%d.json" % pr), "w", encoding="utf-8") as fh:
        json.dump({"pr": pr, **fields}, fh)


@pytest.fixture
def rig(tmp_path):
    """An upstream repo + a clone of it that carries a COPY of the helper at tools/dev/ (so the script's own
    `dirname $0/../..` resolution is what is tested) and a stored pass verdict for PR 7 against the clone's origin/main."""
    up, clone = str(tmp_path / "upstream"), str(tmp_path / "clone")
    os.makedirs(up)
    _git(up, "init", "-q", "-b", "main")
    _commit(up, {"src/a.py": "a\n", "docs/x.md": "d\n", "docs/inbox/old.md": "o\n", "docs/coverage/viewer-certified.json": "{}\n"}, "one")
    _git(str(tmp_path), "clone", "-q", up, clone)
    os.makedirs(os.path.join(clone, "tools", "dev"))
    shutil.copy(HELPER, os.path.join(clone, "tools", "dev", "ci_fresh.sh"))
    ci = os.path.join(clone, ".git", "session-ci", "ci")
    os.makedirs(ci)
    was = _git(clone, "rev-parse", "origin/main")
    _verdict(ci, 7, head=E40, main=was, verdict="pass")

    def fresh(*argv):
        out = subprocess.run(["bash", os.path.join(clone, "tools", "dev", "ci_fresh.sh"), *(map(str, argv or (7,)))],
                             cwd=clone, env=GIT_ENV, capture_output=True, text=True, timeout=60)
        return out.returncode, out.stdout.strip()
    return types.SimpleNamespace(up=up, ci=ci, was=was, fresh=fresh)


def test_unchanged_main_is_fresh(rig):
    assert rig.fresh() == (0, "FRESH main=%s" % rig.was)
    assert rig.fresh(7, E40) == (0, "FRESH main=%s" % rig.was)          # with the expected head: same answer when it matches a pass


def test_docs_only_drift_is_fresh_and_says_so(rig):
    now = _commit(rig.up, {"docs/x.md": "more\n", "docs/inbox/record.md": "new\n", "docs/STEERING.md": "| row |\n"}, "docs only")
    assert rig.fresh() == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))


def test_code_drift_is_stale_names_the_first_three_paths_and_exits_4(rig):
    now = _commit(rig.up, {"docs/x.md": "more\n", "src/a.py": "b\n", "tests/ci_shard.d/9-x.txt": "tests/test_b.py\n",
                           "tools/t.py": "t\n", "src/z.py": "z\n"}, "code moved under the verdict")
    rc, line = rig.fresh()
    assert rc == 4, line
    assert line == "STALE was=%s now=%s changed=src/a.py,src/z.py,tests/ci_shard.d/9-x.txt,… -> re-run tools/dev/session_ci.sh 7" % (rig.was, now), line   # docs/x.md is not counted; 4 blocking paths -> 3 named + ellipsis


@pytest.mark.parametrize("files,delete,blocking", [
    ({"docs/coverage/viewer-certified.json": " \n"}, (), "docs/coverage/viewer-certified.json"),        # tests/test_router.py + test_probe_batch.py open the ledger
    ({"docs/product/PERMUTATION-MATRIX.md": "| cell |\n"}, (), "docs/product/PERMUTATION-MATRIX.md"),   # test_router.py compares the rendered matrix
    ({"docs/process/AUTONOMY.md": "words\n"}, (), "docs/process/AUTONOMY.md"),                          # test_techlead.py pins needles in it
    ({"docs/x.md": "more\n"}, ("docs/inbox/old.md",), "docs/inbox/old.md"),                              # matrix.py cites records by existence: a deletion is drift
])
def test_docs_the_shard_reads_and_docs_deletions_are_stale(rig, files, delete, blocking):
    now = _commit(rig.up, files, "docs the gates can feel", delete=delete)
    assert rig.fresh() == (4, "STALE was=%s now=%s changed=%s -> re-run tools/dev/session_ci.sh 7" % (rig.was, now, blocking))


def test_missing_or_pre_487_json_exits_3_and_bad_usage_2(rig):
    rc, line = rig.fresh(8)                                             # no run stored for this PR
    assert rc == 3 and line.startswith("MISSING ") and "8.json" in line
    _verdict(rig.ci, 9, head=E40, verdict="pass")                       # a verdict written before session_ci.sh recorded "main"
    rc, line = rig.fresh(9)
    assert rc == 3 and line.startswith('MISSING "main"'), line
    with open(os.path.join(rig.ci, "5.json"), "w", encoding="utf-8") as fh:
        fh.write("not json\n")                                          # a truncated/garbled result file is MISSING too, never FRESH
    assert rig.fresh(5)[0] == 3
    assert rig.fresh("7x")[0] == 2


def test_expected_head_refuses_a_json_for_another_head_or_a_non_pass(rig):
    rc, line = rig.fresh(7, "f" * 40)
    assert rc == 5 and line.startswith("WRONG-HEAD json=%s now=%s" % (E40, "f" * 40)), line
    _verdict(rig.ci, 4, head=E40, main=rig.was, verdict="fail")
    assert rig.fresh(4) == (0, "FRESH main=%s" % rig.was)               # without a head the helper judges main only (the tick read the verdict itself)
    rc, line = rig.fresh(4, E40)
    assert rc == 5 and line.startswith("NOT-PASS verdict=fail"), line


def test_unknown_recorded_main_fails_closed(rig):
    """A `main` this clone has never seen (trunk rewritten, or a JSON copied from another checkout) cannot be diffed:
    that is STALE, never FRESH."""
    _verdict(rig.ci, 6, head=E40, main="1" * 40, verdict="pass")
    rc, line = rig.fresh(6)
    assert rc == 4 and line.startswith("STALE was=%s now=" % ("1" * 40)) and "changed=?" in line


def test_session_ci_records_the_main_it_merged_and_the_helper_stays_trusted_side():
    # session_ci.sh's other needles (sandbox, locks, shard reader, the merge with "$MAIN") are pinned in tests/test_techlead.py
    src = open(SESSION_CI, encoding="utf-8").read()
    assert src.index('HEAD=$(git rev-parse "refs/pr/$PR")') < src.index("MAIN=$(git rev-parse --verify -q origin/main)") < src.index("git worktree add --detach")   # captured with the head, before the merge test
    assert 'rev-list --count "HEAD..$MAIN"' in src and 'merge --no-edit "$MAIN"' in src                                     # merged with the sha it records, not the ref name
    assert '"$HEAD" "$MAIN" "$MERGE"' in src and '"head":head,"main":main,' in src                                          # emitted right after "head"
    helper = open(HELPER, encoding="utf-8").read()
    assert os.access(HELPER, os.X_OK) and helper.startswith("#!/usr/bin/env bash")
    assert "SESSION_CI_DIR:-$REPO/.git/session-ci" in helper and "SESSION_CI_DIR:-$REPO/.git/session-ci" in src           # one scratch layout, two readers
    for needle in ("git checkout", "git switch", "worktree add", "pytest", "refs/pr/"):     # it never touches PR code: our own JSON + git plumbing on main only
        assert needle not in helper, needle
