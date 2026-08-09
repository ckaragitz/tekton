"""tools/dev/shard_list.py -- the CI test shard is tests/ci_shard.txt + tests/ci_shard.d/*.txt drop-ins (#328).

Pins the merge rules (union order, dedup, comment stripping, refusal of bad entries and names, non-empty),
that both readers (working tree and git blobs) agree, that every path in the real shard exists, and that
the two consumers (tools/dev/session_ci.sh on the trusted side, the reference ci.yml) use this one helper.
Fresh-clone runnable; stdlib + git only.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, "tools", "dev", "shard_list.py")
_spec = importlib.util.spec_from_file_location("shard_list", HELPER)
sl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sl)

BASE = "# CI shard\n\n# first on purpose\ntests/test_schema_gate.py\ntests/test_frontdoor.py\n  tests/test_versions.py  \n"
BASE_CAP = 51   # tests/ci_shard.txt is frozen for appends (#328): it may shrink, never grow — new entries are drop-ins


def test_union_order_dedup_and_comment_stripping():
    dropins = [("20-b.txt", "tests/test_zeta.py\n# dup of the base file, collapses:\ntests/test_frontdoor.py\n"),
               ("100-a.txt", "\n\ntests/test_alpha.py\r\ntests/test_zeta.py\n"),          # CRLF tolerated; sorts BEFORE 20-b.txt ("1" < "2")
               ("3-c.txt", "# only a comment\n")]
    assert sl.merge(BASE, dropins) == [
        "tests/test_schema_gate.py", "tests/test_frontdoor.py", "tests/test_versions.py",   # base file first, its own order, whitespace stripped
        "tests/test_alpha.py", "tests/test_zeta.py",                                        # 100-a.txt, then 20-b.txt adds nothing new, then 3-c.txt
    ]
    assert sl.parse("  # indented comment\n\t\ntests/x.py\n") == ["tests/x.py"]


@pytest.mark.parametrize("entry", [
    "tests/test_x.py -k nothing", "--co", "-p no:randomly", "tests/../tools/frontdoor.py", "../etc/passwd",
    "tools/dev/coord.py", "tests/test_x.py  # trailing comments are not a thing", "tests/sub dir/test_x.py",
    "/tests/test_x.py", "tests/test_x.pyc", "tests/", "tests/*.py",
])
def test_bad_entries_refuse_the_whole_list(entry):
    with pytest.raises(sl.Refused, match="invalid shard entries"):
        sl.merge(BASE, [("1-x.txt", "tests/test_ok.py\n%s\n" % entry)])
    with pytest.raises(sl.Refused, match="invalid shard entries"):
        sl.merge(entry + "\n", [])                                                          # the base file is held to the same rule


@pytest.mark.parametrize("name", ["bad name.txt", ".hidden.txt", "-rf.txt", "x:y.txt", "ümlaut.txt"])
def test_bad_dropin_names_are_refused(name):
    with pytest.raises(sl.Refused, match="drop-in file names"):
        sl.merge(BASE, [(name, "tests/test_ok.py\n")])


def test_empty_list_is_refused_and_diagnostics_are_bounded():
    with pytest.raises(sl.Refused, match="empty shard"):
        sl.merge("# nothing\n\n", [("1-x.txt", "# still nothing\n")])
    with pytest.raises(sl.Refused) as ei:
        sl.merge("".join("not/a/test/%04d%s\n" % (i, "x" * 500) for i in range(200)), [])
    msg = str(ei.value)
    assert msg.startswith("200 invalid") and len(msg) < 600                                 # PR-controlled text never floods the log


def test_real_shard_from_tree_and_from_git_agree_and_every_path_exists():
    shard = sl.merge(*sl.from_tree(ROOT))
    assert shard[0] == "tests/test_schema_gate.py"                                          # #298: the schema gate sentinel runs first
    assert "tests/test_shard_list.py" in shard                                              # our own drop-in (tests/ci_shard.d/328-shard-list.txt)
    assert len(shard) == len(set(shard))
    missing = [p for p in shard if not os.path.isfile(os.path.join(ROOT, p))]
    assert not missing, "shard lists files that do not exist: %s" % missing
    with open(os.path.join(ROOT, "tests", "ci_shard.txt"), encoding="utf-8") as fh:
        base_only = sl.parse(fh.read())
    assert shard[:len(base_only)] == base_only                                              # drop-ins only ever append
    assert len(base_only) <= BASE_CAP, ("tests/ci_shard.txt is frozen for appends (#328): put new shard entries in "
                                        "tests/ci_shard.d/<issue>-<slug>.txt instead (see tests/ci_shard.d/README)")
    cli = subprocess.run([sys.executable, "-I", HELPER, "--print"], capture_output=True, text=True, check=True).stdout.splitlines()
    assert cli == shard
    if os.path.isdir(os.path.join(ROOT, ".git")) and subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True).returncode == 0:
        tracked = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "tests/ci_shard.txt", "tests/ci_shard.d"],
                                 capture_output=True, text=True, check=True).stdout
        if not tracked.strip():                                                             # blobs == files only when nothing there is uncommitted
            assert sl.merge(*sl.from_git(ROOT)) == shard


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.hooksPath=/dev/null", *args],
                          capture_output=True, text=True, check=True).stdout


def _seed(repo):
    (repo / "tests" / "ci_shard.d").mkdir(parents=True)
    (repo / "tests" / "ci_shard.txt").write_text("# base\ntests/test_one.py\n", encoding="utf-8")
    (repo / "tests" / "ci_shard.d" / "README").write_text("tests/not_read.py\n", encoding="utf-8")            # non-.txt: ignored by both readers
    (repo / "tests" / "ci_shard.d" / "7-x.txt").write_bytes(b"tests/test_two.py\n# caf\xe9 in a comment is fine\n")   # undecodable byte, in a comment
    _git(repo, "init", "-q"); _git(repo, "add", "-A"); _git(repo, "commit", "-qm", "seed")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_tree_and_git_readers_share_one_selection_policy(tmp_path):
    _seed(tmp_path)
    expect = ["tests/test_one.py", "tests/test_two.py"]
    assert sl.merge(*sl.from_tree(str(tmp_path))) == expect == sl.merge(*sl.from_git(str(tmp_path)))
    # the trusted-side property: what a sandboxed step does to the CHECKOUT never changes what --git reads
    (tmp_path / "tests" / "ci_shard.d" / "7-x.txt").unlink(); os.symlink("/etc/hostname", tmp_path / "tests" / "ci_shard.d" / "7-x.txt")
    (tmp_path / "tests" / "ci_shard.d" / "8-planted.txt").write_text("tests/test_evil.py\n", encoding="utf-8")
    assert sl.merge(*sl.from_git(str(tmp_path))) == expect
    with pytest.raises(sl.Refused, match="not a regular file"):                              # ...while the tree reader refuses the symlink outright
        sl.from_tree(str(tmp_path))
    # a COMMITTED symlink drop-in is refused by the git reader too (same policy, not silently skipped)
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-qm", "symlink drop-in")
    with pytest.raises(sl.Refused, match="not a regular file at HEAD"):
        sl.from_git(str(tmp_path))
    cli = subprocess.run([sys.executable, "-I", HELPER, "--git", str(tmp_path)], capture_output=True, text=True)
    assert cli.returncode == 3 and cli.stdout == "" and "refused" in cli.stderr
    _git(tmp_path, "rm", "-q", "tests/ci_shard.d/7-x.txt", "tests/ci_shard.txt"); _git(tmp_path, "commit", "-qm", "no base")
    with pytest.raises(sl.Refused, match="missing at HEAD"):
        sl.from_git(str(tmp_path))


def test_dropin_dir_is_documented_and_kept_clean():
    d = os.path.join(ROOT, "tests", "ci_shard.d")
    assert os.path.isfile(os.path.join(d, "README"))
    for name in os.listdir(d):
        if name != "README":
            assert sl.DROPIN_NAME.match(name), name                                        # a stray non-.txt file would be silently ignored: keep the dir to README + drop-ins
    with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as fh:
        assert "tests/ci_shard.d/" in fh.read()
    with open(os.path.join(ROOT, ".github", "pull_request_template.md"), encoding="utf-8") as fh:
        assert "tests/ci_shard.d/" in fh.read()


def test_reference_ci_yml_uses_the_helper():
    # session_ci.sh's use of the helper (trusted side, main's copy, blobs) is pinned with the other sandbox
    # needles in tests/test_techlead.py::test_workflows_are_dispatch_only_and_the_session_pipeline_is_checked_in
    with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as fh:
        yml = fh.read()
    assert "SHARD_TXT=$(python tools/dev/shard_list.py --print)" in yml and '-- "${SHARD[@]}"' in yml and "grep -vE" not in yml
