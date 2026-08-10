"""tests/conftest.py's runtime docs-read audit (#523) and its shared throwaway-git helpers.

The audit is a `sys.addaudithook` recorder: every `open` of a file under <repo>/docs by this test process is
recorded with the test id that made it, and at session end each recorded path must be matched by SHARD_READS as
tools/dev/ci_fresh.sh spells it -- the runtime complement of the static AST tripwire in tests/test_ci_fresh.py,
which cannot see a docs read made through a variable, a glob, or src/tools code a test merely calls.

Pinned here: the recorder (every open shape, relative/bytes/PathLike paths, attribution, never raising), the judge
(covered / offender / recorded-but-unenforced), the report lines, that SHARD_READS and the shard file list come from
their one source each, the END-TO-END wiring (a child pytest run of the self-test reader below exits 1 naming test
id + path for a docs file outside SHARD_READS, and 0 for one inside it), and the `git_repo` fixture.

House rule for THIS file: real docs/ file names are never spelled as string literals -- tests/test_ci_fresh.py's
static scanner reads this file too and would (rightly, for a literal) count them as reads; the self-test's target
travels through an environment variable instead, which is exactly the indirection class only the runtime audit sees.
Fresh-clone runnable; stdlib + git only.
"""
import io
import os
import pathlib
import posixpath
import re
import subprocess
import sys

import pytest

from conftest import (AUDITED_DIR, DOCS_AUDIT, ROOT, DocsReadAudit, ci_shard_files, docs_audit_lines, git, git_commit,
                      shard_reads_pattern)

ME = "tests/test_docs_read_audit.py"
SELFTEST = "RVT_DOCS_AUDIT_SELFTEST"           # set to a path relative to <repo>/docs: the self-test reader opens it
LEDGER = "coverage/viewer-certified.json"      # relative to docs/: inside SHARD_READS, read by the shard since ever
OUTSIDE = "STEERING.md"                        # relative to docs/: tracked, outside SHARD_READS, read by no test


def test_recorder_sees_every_open_shape_attributes_it_and_never_raises(tmp_path, monkeypatch):
    rec = DocsReadAudit(str(tmp_path))
    target = tmp_path / AUDITED_DIR / "inbox" / "zz-fixture.md"
    target.parent.mkdir(parents=True)
    target.write_text("x\n", encoding="utf-8")
    rec("open", (str(tmp_path / "elsewhere.txt"), "r", 0))                  # not under the audited dir
    rec("import", ("json", None, None, None, None))                         # not an open event
    rec("open", (3, "r", 0)); rec("open", (None, "r", 0))                   # an fd / nothing: no path to judge
    rec("open", (object(), "r", 0))                                         # undecodable: swallowed, never raised
    assert rec.reads == {}
    rec.enter(None, "tests/test_a.py::test_abs")
    rec("open", (str(target), "r", 0))                                      # absolute str
    rec.enter(tmp_path / "tests" / "test_b.py", "tests/test_b.py::test_rel")   # a path that is not a file -> rel ""
    monkeypatch.chdir(tmp_path)
    rec("open", (os.path.join(AUDITED_DIR, "inbox", "zz-fixture.md"), "rb", 0))            # relative to cwd
    rec("open", (os.fsencode(str(target)), None, 0o600))                                    # bytes, os.open shape
    rec("open", (target, "r", 0))                                                            # PathLike
    rec("open", (os.path.join(str(tmp_path), "tests", "..", AUDITED_DIR, "inbox", ".", "zz-fixture.md"), "r", 0))   # un-normalised
    key = posixpath.join(AUDITED_DIR, "inbox", "zz-fixture.md")
    assert rec.reads == {key: {("", "tests/test_a.py::test_abs"), ("", "tests/test_b.py::test_rel")}}
    real = tmp_path / "tests" / "test_c.py"
    real.parent.mkdir()
    real.write_text("", encoding="utf-8")
    rec.enter(real, "tests/test_c.py::t")                                   # an existing file under root -> its posix relpath
    assert rec.context == ("tests/test_c.py", "tests/test_c.py::t")
    rec.enter(pathlib.Path("/definitely/elsewhere/test_d.py"), "")          # outside root, no id -> session context
    assert rec.context == ("", "<session>")


@pytest.mark.skipif(DOCS_AUDIT is None, reason="the audit is switched off in this process (RVT_DOCS_AUDIT=0)")
def test_the_installed_hook_records_real_reads_of_the_ledger_by_this_very_test(request):
    ledger = os.path.join(ROOT, AUDITED_DIR, *LEDGER.split("/"))
    pathlib.Path(ledger).read_bytes()                                        # pathlib -> io.open
    with io.open(ledger, "rb"):
        pass
    os.close(os.open(ledger, os.O_RDONLY))                                   # the os.open shape (mode None)
    with open(os.path.relpath(ledger), "rb"):                                # relative to the invocation cwd
        pass
    key = posixpath.join(AUDITED_DIR, LEDGER)
    assert (ME, request.node.nodeid) in DOCS_AUDIT.reads[key], DOCS_AUDIT.reads.get(key)
    assert re.match(shard_reads_pattern(), key)                              # ...and it is a covered read, so this test is no offender


def test_judge_sorts_reads_into_covered_offenders_and_unenforced_and_the_report_names_test_id_and_path(tmp_path):
    rec = DocsReadAudit(str(tmp_path))
    d = AUDITED_DIR
    rec.reads = {
        posixpath.join(d, "coverage", "l.json"): {("tests/test_in.py", "tests/test_in.py::a"), ("tests/test_out.py", "tests/test_out.py::b")},
        posixpath.join(d, "S.md"): {("tests/test_in.py", "tests/test_in.py::c[x-1]")},          # shard file, unmatched -> offender
        posixpath.join(d, "writer", "n.md"): {("tests/test_out.py", "tests/test_out.py::e")},    # non-shard test file -> unenforced
        posixpath.join(d, "P.md"): {("", "<session>"), ("tests/fixtures_x.py", "tests/test_out.py::f")},   # session / helper context -> enforced
    }
    v = rec.judge(r"^%s/(coverage/|product/M[.]md$)" % d, ["tests/test_in.py"])
    assert v["covered"] == {posixpath.join(d, "coverage", "l.json"): ["tests/test_in.py::a", "tests/test_out.py::b"]}
    assert v["offenders"] == {posixpath.join(d, "S.md"): ["tests/test_in.py::c[x-1]"], posixpath.join(d, "P.md"): ["<session>", "tests/test_out.py::f"]}
    assert v["unenforced"] == {posixpath.join(d, "writer", "n.md"): ["tests/test_out.py::e"]}
    short = docs_audit_lines(v)
    assert short[:5] == ["  FAIL %s   (opened by the CI shard, NOT covered by SHARD_READS)" % posixpath.join(d, "P.md"),
                         "         <- <session>", "         <- tests/test_out.py::f",
                         "  FAIL %s   (opened by the CI shard, NOT covered by SHARD_READS)" % posixpath.join(d, "S.md"),
                         "         <- tests/test_in.py::c[x-1]"]
    assert any("SHARD_READS in tools/dev/ci_fresh.sh" in line for line in short) and not any(line.startswith(("  ok", "  --")) for line in short)
    full = docs_audit_lines(v, everything=True)
    tags = [line.split()[0] for line in full if not line.startswith("         <-")]
    assert tags[:4] == ["FAIL", "FAIL", "ok", "--"] and ("  --   %s   (not a CI-shard file: recorded, not enforced)" % posixpath.join(d, "writer", "n.md")) in full
    many = {posixpath.join(d, "Q.md"): ["t::%d" % i for i in range(6)]}
    assert docs_audit_lines({"offenders": {}, "covered": many, "unenforced": {}}, everything=True) == \
        ["  ok   %s" % posixpath.join(d, "Q.md")] + ["         <- t::%d" % i for i in range(6)]      # complete, never truncated
    assert docs_audit_lines({"offenders": {}, "covered": many, "unenforced": {}}) == []             # nothing to say on a clean run


def test_SHARD_READS_and_the_shard_list_come_from_their_one_source_each(tmp_path):
    pattern = shard_reads_pattern()
    with open(os.path.join(ROOT, "tools", "dev", "ci_fresh.sh"), encoding="utf-8") as fh:
        assert "SHARD_READS='%s'" % pattern in fh.read()
    rx = re.compile(pattern)
    assert rx.match(posixpath.join(AUDITED_DIR, LEDGER)) and not rx.match(posixpath.join(AUDITED_DIR, OUTSIDE))
    other = tmp_path / "no_reads.sh"
    other.write_text("#!/usr/bin/env bash\nset -eu\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no SHARD_READS"):
        shard_reads_pattern(str(other))
    shard = ci_shard_files()                                                 # tools/dev/shard_list.py's merge (pinned by tests/test_shard_list.py)
    assert ME in shard and "tests/test_router.py" in shard and len(shard) > 40


def _child_run(target):
    """This file's self-test reader in a child pytest (its own interpreter, its own hook), told to open docs/<target>."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env[SELFTEST] = target
    env.pop("RVT_DOCS_AUDIT", None)                                          # the child audits even if this process opted out
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", ME + "::test_zz_selftest_reader"],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    return out.returncode, out.stdout


def test_session_wiring_end_to_end_an_uncovered_docs_read_fails_the_run_naming_test_and_path_a_covered_one_does_not():
    rc, out = _child_run(OUTSIDE)
    assert rc == 1, out
    assert "1 passed" in out                                                 # the test itself passed: the AUDIT failed the run
    assert "docs-read audit FAILED" in out
    assert "  FAIL %s   (opened by the CI shard, NOT covered by SHARD_READS)\n         <- %s::test_zz_selftest_reader\n" % (posixpath.join(AUDITED_DIR, OUTSIDE), ME) in out
    assert "SHARD_READS in tools/dev/ci_fresh.sh" in out
    rc, out = _child_run(LEDGER)                                             # the control: same road, a covered file
    assert rc == 0, out
    assert "1 passed" in out and "docs-read audit" not in out.split("test session starts")[-1]


def test_zz_selftest_reader():
    """Driven by the end-to-end test above through a child pytest; inert (skipped) in every other run.  It reads the
    docs file named by $RVT_DOCS_AUDIT_SELFTEST through a variable -- the shape no static scan can attribute."""
    target = os.environ.get(SELFTEST)
    if not target:
        pytest.skip("self-test reader: only driven by test_session_wiring_end_to_end... through %s" % SELFTEST)
    with open(os.path.join(ROOT, AUDITED_DIR, *target.split("/")), "rb") as fh:
        assert fh.read(1)


def test_the_shared_git_repo_fixture_makes_a_hermetic_repo_on_main(git_repo):
    first = git_commit(git_repo, {"a.txt": "one\n", "d/b.txt": "two\n"}, "first")
    second = git_commit(git_repo, {"a.txt": "more\n"}, "second", delete=("d/b.txt",))
    assert re.fullmatch(r"[0-9a-f]{40}", first) and re.fullmatch(r"[0-9a-f]{40}", second) and first != second
    assert git(git_repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert git(git_repo, "ls-files") == "a.txt" and (git_repo / "a.txt").read_text(encoding="utf-8") == "one\nmore\n"
    assert git(git_repo, "log", "--format=%an <%ae> %s").splitlines() == ["t <t@t> second", "t <t@t> first"]
    assert git(str(git_repo), "rev-list", "--count", "HEAD") == "2"        # str or Path cwd alike
    with pytest.raises(subprocess.CalledProcessError):
        git(git_repo, "rev-parse", "--verify", "-q", "refs/heads/nope")
