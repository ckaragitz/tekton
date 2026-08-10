"""tests/conftest.py's runtime docs-read audit (#523) and its shared throwaway-git helpers.

The audit is a `sys.addaudithook` recorder: every `open` of a file under <repo>/docs by this test process is
recorded with the test id that made it, and at session end each recorded path must be matched by SHARD_READS as
tools/dev/ci_fresh.sh spells it -- the runtime complement of the static AST tripwire in tests/test_ci_fresh.py,
which cannot see a docs read made through a variable, a glob, or src/tools code a test merely calls.

Pinned here: the recorder (every open shape, relative/bytes/PathLike paths, attribution, never raising), the rule
(covered / offender / recorded-but-unenforced) through both channels -- per test (`offences`) and at session end
(`judge`, fail-closed and worded as such when the rules cannot be read, every read then kept as unjudged) -- the
report header (distinct files, not rows) and lines, that SHARD_READS and the shard file list come from their one
source each, collector attribution (Module AND Class collectors carry their file, the directory and session do not),
that executing conftest twice in one interpreter adopts the installed recorder instead of stacking a second hook, the
END-TO-END wiring twice (a child pytest run of the self-test reader below: a docs file outside SHARD_READS makes that
test red in pytest's own tally + exit 1 + a section naming path and reader; a file inside it: green, silent -- and, on
a hermetic copy of the rig, a read made while a CLASS is collected: unenforced when its file is outside the shard, an
offender named with the class when inside), and the `git_repo` fixture.

House rule for THIS file: real docs/ file names are never spelled as string literals -- tests/test_ci_fresh.py's
static scanner reads this file too and would (rightly, for a literal) count them as reads; the self-test's target
travels through an environment variable instead, which is exactly the indirection class only the runtime audit sees.
Fresh-clone runnable; stdlib + git only.
"""
import importlib.util
import io
import os
import pathlib
import posixpath
import re
import shutil
import subprocess
import sys

import pytest

import conftest
from conftest import (AUDITED_DIR, DOCS_AUDIT, ROOT, SESSION_ID, DocsReadAudit, audit_failed, ci_shard_files, collector_module,
                      docs_audit_header, docs_audit_lines, git, git_commit, shard_reads_pattern)

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
    rec.enter(None, "tests")                                                # a directory collector: no module -> session level
    rec("open", (str(target), "r", 0))                                      # absolute str
    rec.enter(tmp_path / "tests" / "test_b.py", "tests/test_b.py::test_rel")   # an item: its module, as a root-relative posix path
    assert rec.context == ("tests/test_b.py", "tests/test_b.py::test_rel")
    monkeypatch.chdir(tmp_path)
    rec("open", (os.path.join(AUDITED_DIR, "inbox", "zz-fixture.md"), "rb", 0))            # relative to cwd
    rec("open", (os.fsencode(str(target)), None, 0o600))                                    # bytes, os.open shape
    rec("open", (target, "r", 0))                                                            # PathLike
    rec("open", (os.path.join(str(tmp_path), "tests", "..", AUDITED_DIR, "inbox", ".", "zz-fixture.md"), "r", 0))   # un-normalised
    key = posixpath.join(AUDITED_DIR, "inbox", "zz-fixture.md")
    assert rec.reads == {key: {("", "tests"), ("tests/test_b.py", "tests/test_b.py::test_rel")}}
    rec.enter(pathlib.Path("/definitely/elsewhere/test_d.py"), "")          # outside root, no id -> session context
    assert rec.context == ("", SESSION_ID)


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


def test_judge_sorts_reads_into_covered_offenders_and_unenforced_and_the_report_names_test_id_and_path(tmp_path, monkeypatch):
    rec = DocsReadAudit(str(tmp_path))
    d = AUDITED_DIR
    rec._rules = (re.compile(r"^%s/(coverage/|product/M[.]md$)" % d), frozenset(["tests/test_in.py"]))   # a synthetic SHARD_READS + shard
    rec.reads = {
        posixpath.join(d, "coverage", "l.json"): {("tests/test_in.py", "tests/test_in.py::a"), ("tests/test_out.py", "tests/test_out.py::b")},
        posixpath.join(d, "S.md"): {("tests/test_in.py", "tests/test_in.py::c[x-1]")},          # shard module, unmatched -> offender
        posixpath.join(d, "writer", "n.md"): {("tests/test_out.py", "tests/test_out.py::e")},    # non-shard module -> unenforced
        posixpath.join(d, "P.md"): {("", SESSION_ID), ("", "tests")},                            # session / directory-collector level -> enforced
    }
    assert rec.offences(("tests/test_in.py", "tests/test_in.py::c[x-1]")) == [posixpath.join(d, "S.md")]   # the per-test channel...
    assert rec.offences(("tests/test_in.py", "tests/test_in.py::a")) == [] == rec.offences(("tests/test_out.py", "tests/test_out.py::e"))
    assert rec.offences(("", "tests")) == [posixpath.join(d, "P.md")]
    v = rec.judge()                                                                              # ...and the session-end verdict agree
    assert v is rec.verdict and audit_failed(v)
    assert v["covered"] == {posixpath.join(d, "coverage", "l.json"): ["tests/test_in.py::a", "tests/test_out.py::b"]}
    assert v["offenders"] == {posixpath.join(d, "S.md"): ["tests/test_in.py::c[x-1]"], posixpath.join(d, "P.md"): [SESSION_ID, "tests"]}
    assert v["unenforced"] == {posixpath.join(d, "writer", "n.md"): ["tests/test_out.py::e"]}
    assert v["unjudged"] == {} and v["error"] is None
    assert docs_audit_header(v).startswith("4 repo docs/ file(s) opened by this test process; ")
    two_buckets = dict(v, offenders={posixpath.join(d, "S.md"): ["tests/test_in.py::c"]}, unenforced={posixpath.join(d, "S.md"): ["tests/test_out.py::e"]})
    assert docs_audit_header(two_buckets).startswith("2 repo docs/ file(s) ")                    # S.md under two buckets + l.json: distinct files, not rows
    short = docs_audit_lines(v)
    assert short[:5] == ["  FAIL %s   (opened by the CI shard, NOT covered by SHARD_READS)" % posixpath.join(d, "P.md"),
                         "         <- " + SESSION_ID, "         <- tests",
                         "  FAIL %s   (opened by the CI shard, NOT covered by SHARD_READS)" % posixpath.join(d, "S.md"),
                         "         <- tests/test_in.py::c[x-1]"]
    assert any("SHARD_READS in tools/dev/ci_fresh.sh" in line for line in short) and not any(line.startswith(("  ok", "  --")) for line in short)
    full = docs_audit_lines(v, everything=True)
    tags = [line.split()[0] for line in full if not line.startswith("         <-")]
    assert tags[:4] == ["FAIL", "FAIL", "ok", "--"] and ("  --   %s   (not a CI-shard file: recorded, not enforced)" % posixpath.join(d, "writer", "n.md")) in full
    clean = dict(v, offenders={}, covered={posixpath.join(d, "Q.md"): ["t::%d" % i for i in range(6)]}, unenforced={})
    assert docs_audit_lines(clean, everything=True) == \
        ["  ok   %s" % posixpath.join(d, "Q.md")] + ["         <- t::%d" % i for i in range(6)]      # complete, never truncated
    assert docs_audit_lines(clean) == [] and not audit_failed(clean)                            # nothing to say on a clean run

    def unreadable():
        raise ValueError("no SHARD_READS line")
    monkeypatch.setattr("conftest.shard_reads_pattern", unreadable)                             # cannot judge -> fail CLOSED, named
    blind = DocsReadAudit(str(tmp_path))
    assert blind.judge() == {"offenders": {}, "covered": {}, "unenforced": {}, "unjudged": {}, "error": "ValueError: no SHARD_READS line"}
    assert audit_failed(blind.verdict)                                                           # not one read recorded, and still red: it cannot vouch
    assert docs_audit_header(blind.verdict).startswith("0 repo docs/ file(s) opened ")           # ...without pretending a file was opened
    blind.reads = dict(rec.reads)
    assert blind.offences(("", "tests")) == []                                                   # the per-test channel stays quiet...
    v = blind.judge()                                                                            # ...the session verdict says why, in its own words,
    assert v["error"] == "ValueError: no SHARD_READS line" and audit_failed(v)                   # and keeps every read it could not judge
    assert (v["offenders"], v["covered"], v["unenforced"]) == ({}, {}, {})
    assert v["unjudged"] == {path: sorted(rid for _, rid in ctx) for path, ctx in rec.reads.items()}
    lines = docs_audit_lines(v)
    assert lines[0].startswith("  FAIL the audit could not judge any read (ValueError: no SHARD_READS line) -- fail closed: ")
    assert lines[1:3] == ["  ??   %s   (recorded, could not be judged)" % posixpath.join(d, "P.md"), "         <- " + SESSION_ID]
    assert not any("NOT covered" in line or line.startswith(("  ok", "  --")) for line in lines) and lines == docs_audit_lines(v, everything=True)


def test_SHARD_READS_and_the_shard_list_come_from_their_one_source_each(tmp_path):
    rx = re.compile(shard_reads_pattern())                                   # tools/dev/ci_fresh.sh's own line
    assert rx.match(posixpath.join(AUDITED_DIR, LEDGER)) and not rx.match(posixpath.join(AUDITED_DIR, OUTSIDE))
    other = tmp_path / "no_reads.sh"
    other.write_text("#!/usr/bin/env bash\nset -eu\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no SHARD_READS"):
        shard_reads_pattern(str(other))
    shard = ci_shard_files()                                                 # tools/dev/shard_list.py's merge (pinned by tests/test_shard_list.py)
    assert ME in shard and "tests/test_router.py" in shard and len(shard) > 40


class TestCollectorAttribution:
    """A method on purpose: its parent IS a ``pytest.Class`` collector, its grandparent the ``pytest.Module`` -- real
    nodes to hand to conftest's ``collector_module`` (what ``pytest_collectstart`` attributes reads through)."""

    def test_module_and_class_collectors_carry_their_file_the_directory_and_session_do_not(self, request):
        cls, mod = request.node.parent, request.node.parent.parent
        assert isinstance(cls, pytest.Class) and isinstance(mod, pytest.Module) and not isinstance(mod.parent, (pytest.Module, pytest.Class))
        assert collector_module(cls) == collector_module(mod) == mod.path == pathlib.Path(ROOT, *ME.split("/"))
        assert collector_module(mod.parent) is None and collector_module(request.session) is None      # tests/ (Dir) and the Session
        rec = DocsReadAudit(ROOT)
        rec.enter(collector_module(cls), cls.nodeid)                          # a read while this class is collected belongs to THIS module...
        assert rec.context == (ME, ME + "::TestCollectorAttribution")
        rec._rules = (re.compile("^$"), frozenset())                          # ...so under a shard that lacks the module it is unenforced,
        rec("open", (os.path.join(ROOT, AUDITED_DIR, OUTSIDE), "r", 0))       # never "opened by the CI shard" (a synthetic event: nothing is opened)
        assert rec.offences(rec.context) == [] and rec.judge()["unenforced"] == {posixpath.join(AUDITED_DIR, OUTSIDE): [cls.nodeid]}
        rec.enter(collector_module(mod.parent), mod.parent.nodeid)            # while a directory collector's read stays session level: enforced
        rec("open", (os.path.join(ROOT, AUDITED_DIR, OUTSIDE), "r", 0))
        assert rec.offences(rec.context) == [posixpath.join(AUDITED_DIR, OUTSIDE)]


@pytest.mark.skipif(DOCS_AUDIT is None, reason="the audit is switched off in this process (RVT_DOCS_AUDIT=0)")
def test_executing_conftest_a_second_time_adopts_the_installed_recorder_instead_of_stacking_a_hook():
    spec = importlib.util.spec_from_file_location("conftest_executed_twice", conftest.__file__)
    twice = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(twice)                                            # a second module object from the same file, same interpreter
    assert twice.DOCS_AUDIT is DOCS_AUDIT is getattr(sys, conftest.AUDIT_SENTINEL)   # one recorder (an audit hook cannot be removed: never add a 2nd)
    assert twice.DocsReadAudit is not DocsReadAudit                           # (it really was executed again: its classes are new objects)


CLASS_COLLECT_READER = '''"""A NON-shard file whose CLASS collection opens a docs file (pytest_generate_tests for a method)."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def pytest_generate_tests(metafunc):
    if "width" in metafunc.fixturenames:                  # runs while the Class collector collects test_width
        with open(os.path.join(ROOT, %r, %r), encoding="utf-8") as fh:
            metafunc.parametrize("width", [len(fh.readline())])

class TestCollected:
    def test_width(self, width):
        assert width > 0
'''


def test_wiring_end_to_end_a_docs_read_during_class_collection_belongs_to_its_module_unenforced_outside_the_shard_red_inside(tmp_path):
    """A hermetic copy of the rig (this conftest + the two dev tools + a shard list, the engine from the real src/):
    a test file that is NOT in that copy's shard opens <copy>/docs/<x> while its CLASS is collected -> attributed to
    the file, so: recorded, listed as unenforced, exit 0 (before #542 the Class collector had no module, the read
    counted as session level and the very same run was red).  Control: list the file in the copy's shard -> the same
    read is an offender, exit 1, named with the class as its reader."""
    for rel in ("tests/conftest.py", "tools/dev/ci_fresh.sh", "tools/dev/shard_list.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(ROOT, *rel.split("/")), tmp_path / rel)
    (tmp_path / AUDITED_DIR).mkdir()
    (tmp_path / AUDITED_DIR / "zz-bite.md").write_text("a line the collector reads\n", encoding="utf-8")
    (tmp_path / "tests" / "test_zz_class_collect.py").write_text(CLASS_COLLECT_READER % (AUDITED_DIR, "zz-bite.md"), encoding="utf-8")
    reader = "tests/test_zz_class_collect.py::TestCollected"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", RVT_DOCS_AUDIT="report", PYTHONPATH=os.path.join(ROOT, "src"), TEKTON_ROOT=ROOT)

    def run(shard):
        (tmp_path / "tests" / "ci_shard.txt").write_text(shard, encoding="utf-8")
        out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_zz_class_collect.py"],
                             cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)
        return out.returncode, out.stdout
    rc, out = run("tests/test_other.py\n")                                    # the reader is not a shard file
    assert rc == 0, out
    assert "1 passed" in out and "error" not in out.lower() and "docs-read audit FAILED" not in out
    assert "  --   %s/zz-bite.md   (not a CI-shard file: recorded, not enforced)\n         <- %s\n" % (AUDITED_DIR, reader) in out, out
    rc, out = run("tests/test_zz_class_collect.py\n")                         # the control: now it is one
    assert rc == 1, out
    assert "1 passed" in out and "docs-read audit FAILED" in out
    assert "  FAIL %s/zz-bite.md   (opened by the CI shard, NOT covered by SHARD_READS)\n         <- %s\n" % (AUDITED_DIR, reader) in out, out


def _child_run(target):
    """This file's self-test reader in a child pytest (its own interpreter, its own hook), told to open docs/<target>."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env[SELFTEST] = target
    env.pop("RVT_DOCS_AUDIT", None)                                          # the child audits even if this process opted out
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", ME + "::test_zz_selftest_reader"],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    return out.returncode, out.stdout


def test_session_wiring_end_to_end_an_uncovered_docs_read_fails_the_run_naming_test_and_path_a_covered_one_does_not():
    path, reader = posixpath.join(AUDITED_DIR, OUTSIDE), ME + "::test_zz_selftest_reader"
    rc, out = _child_run(OUTSIDE)
    assert rc == 1, out
    assert "1 passed, 1 error" in out                                        # its assertions passed; the audit made IT red, in pytest's own tally
    assert "ERROR at teardown of test_zz_selftest_reader" in out and "docs-read audit (#523): this test opened %s --" % path in out
    assert "docs-read audit FAILED" in out                                   # ...and the session-end section names path + every reader
    assert "  FAIL %s " % path in out and "\n         <- %s\n" % reader in out and "SHARD_READS in tools/dev/ci_fresh.sh" in out
    rc, out = _child_run(LEDGER)                                             # the control: same road, a covered file
    assert rc == 0, out
    assert "1 passed" in out and "error" not in out and "docs-read audit" not in out


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
