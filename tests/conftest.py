"""pytest bootstrap: make ``src/`` importable, register markers, and expose
the ONE schema-availability gate (``HAVE_SCHEMA`` / ``needs_schema``), the
ONE real-ifcopenshell gate (``HAVE_IFC_AUTHORING`` / ``needs_ifc_authoring``),
the "certified pinned base of a year, or a clean skip" helper
(``pinned_base`` / ``CERTIFIED_YEARS``), a ``tools/<name>.py`` loader
(``load_tool``) and the ``job`` fixture (``tools/rvt_job.py``); plus the
runtime docs-read audit (``DOCS_AUDIT``: which repo ``docs/`` files did this
test process open, checked at session end against ``tools/dev/ci_fresh.sh``'s
``SHARD_READS``, #523) and the shared throwaway-git-repo helpers
(``GIT_ENV`` / ``git`` / ``git_commit`` / ``HAVE_GIT`` / the ``git_repo`` fixture)."""
import importlib.util
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


# ---- runtime docs-read audit (#523) -- installed BEFORE the engine imports below, so an import-time read is seen too --

#: the audited top-level directory of the repo.  A plain name on purpose: this module is itself scanned by the static
#: tripwire in tests/test_ci_fresh.py, to which a "docs" component inside a join reads as "opens all of docs/".
AUDITED_DIR = "docs"
CI_FRESH = os.path.join(ROOT, "tools", "dev", "ci_fresh.sh")


class DocsReadAudit:
    """A ``sys.addaudithook`` callable recording every ``open`` (builtins/io/pathlib/os.open/open_code all raise
    the one ``open`` event) whose normalised path lies under ``<root>/<subdir>/``, keyed by repo-relative posix path,
    with the context (test file, test id) that was current when it happened.  Exact where the static scan of
    tests/test_ci_fresh.py is heuristic: a read through a variable, a glob or ``src/``/``tools/`` code is seen the
    same as a literal one.  Not seen, by construction: reads made by a *subprocess* (another interpreter).
    Cost: one string compare per audited event, a normpath per ``open`` -- measured on the merged shard: noise."""

    SESSION = ("", "<session>")             # context outside any test or collector: conftest import, sessionstart

    def __init__(self, root, subdir=AUDITED_DIR):
        self.root = os.path.abspath(root)
        self.subdir = subdir
        self.prefix = os.path.join(self.root, subdir) + os.sep
        self.context = self.SESSION            # (repo-relative posix path of the test file or "", display id)
        self.reads = {}                        # "docs/x/y.md" -> {context, ...}

    def __call__(self, event, args):
        if event != "open":
            return
        try:
            p = args[0]
            if p is None or isinstance(p, int):                     # an fd being wrapped, not a path
                return
            p = os.fsdecode(p)                                       # str / bytes / PathLike alike
            if os.path.isabs(p):
                if self.subdir not in p:                             # the common case (imports, tmp files) ends here
                    return
            else:
                p = os.path.join(os.getcwd(), p)
            p = os.path.normpath(p)
            if p.startswith(self.prefix):
                rel = os.path.relpath(p, self.root).replace(os.sep, "/")
                self.reads.setdefault(rel, set()).add(self.context)
        except Exception:                        # noqa: BLE001 -- a raising audit hook breaks the open() it watches: never
            pass

    def enter(self, path, nodeid):
        """Attribute what follows to ``nodeid`` (a test item or a collector); ``path`` = its file, if any."""
        rel = ""
        if path is not None:
            ap = os.path.abspath(os.fspath(path))
            if ap.startswith(self.root + os.sep) and os.path.isfile(ap):
                rel = os.path.relpath(ap, self.root).replace(os.sep, "/")
        self.context = (rel, nodeid or self.SESSION[1])

    def judge(self, allowed, shard):
        """The verdict against ``allowed`` (SHARD_READS, an ERE also valid as a Python re) for the files in ``shard``
        (repo-relative test paths, the merged CI shard): a read is an OFFENDER when its path is not matched and it was
        made at session/collection level, by a tests/ helper context, or by a test file that is in the shard; reads by
        test files outside the shard are listed, not enforced (the full suite legitimately reads more than CI does).
        -> {"offenders": {path: [ids]}, "covered": {path: [ids]}, "unenforced": {path: [ids]}}"""
        rx, shard = re.compile(allowed), set(shard)
        out = {"offenders": {}, "covered": {}, "unenforced": {}}
        for path, contexts in sorted(self.reads.items()):
            for rel, nodeid in sorted(contexts):
                is_test_file = rel.startswith("tests/") and os.path.basename(rel).startswith("test_")
                if rx.match(path):
                    kind = "covered"
                elif is_test_file and rel not in shard:
                    kind = "unenforced"
                else:
                    kind = "offenders"
                out[kind].setdefault(path, []).append(nodeid)
        return out


def shard_reads_pattern(script=CI_FRESH):
    """``SHARD_READS`` exactly as tools/dev/ci_fresh.sh spells it (one source of truth; tests/test_ci_fresh.py keeps
    it inside the ERE subset Python's ``re`` reads identically)."""
    with open(script, encoding="utf-8") as fh:
        m = re.search(r"^SHARD_READS='([^']*)'", fh.read(), re.M)
    if m is None:
        raise ValueError("no SHARD_READS='...' line in %s" % script)
    return m.group(1)


def ci_shard_files():
    """The merged CI shard (tests/ci_shard.txt + tests/ci_shard.d/*.txt) via tools/dev/shard_list.py -- exactly the
    file list tools/dev/session_ci.sh runs."""
    sl = load_tool("dev/shard_list")
    return sl.merge(*sl.from_tree(ROOT))


def _install_docs_audit():
    """``RVT_DOCS_AUDIT=0`` (or ``off``) skips the hook entirely -- the documented opt-out should it ever cost time;
    ``RVT_DOCS_AUDIT=report`` additionally prints every recorded read at session end (offenders always print)."""
    if os.environ.get("RVT_DOCS_AUDIT", "1").strip().lower() in ("0", "off", "no", "false"):
        return None
    audit = DocsReadAudit(ROOT)
    sys.addaudithook(audit)
    return audit


#: the process-wide recorder (``from conftest import DOCS_AUDIT``); ``None`` when opted out.
DOCS_AUDIT = _install_docs_audit()

from rvt.frontdoor import base as _B                          # noqa: E402
from rvt.ifc._fallback import ifc_authoring_available            # noqa: E402
from rvt.schema import schema_available                       # noqa: E402

#: The ONE schema gate (``from conftest import HAVE_SCHEMA, needs_schema``):
#: the engine-owned existence check, so only a genuinely absent source skips
#: and a present-but-broken schema FAILS the test that loads it.
HAVE_SCHEMA = schema_available()
needs_schema = pytest.mark.skipif(
    not HAVE_SCHEMA,
    reason="no class schema (extracted corpus and bundled genesis base both absent)")

#: The ONE real-ifcopenshell gate (``from conftest import HAVE_IFC_AUTHORING,
#: needs_ifc_authoring``): the engine-owned query (#367), True only for a REAL
#: wheel with ``ifcopenshell.api`` -- the bundled steplite shim, which is on
#: ``sys.path`` in every process that imported ``rvt.ifc``, never counts, so
#: "does ``import ifcopenshell`` succeed" is NOT this question.  Gate only what
#: AUTHORS IFC through the wheel or compares against the real library; IFC
#: *reading* is served by the shim by design and must stay ungated.
HAVE_IFC_AUTHORING = ifc_authoring_available()
needs_ifc_authoring = pytest.mark.skipif(
    not HAVE_IFC_AUTHORING,
    reason="real ifcopenshell wheel absent (optional `ifc` extra; the bundled steplite shim only reads)")

#: The release years whose PINNED composed genesis base is certified
#: (``from conftest import CERTIFIED_YEARS``) -- the parametrize axis of every
#: "on each certified pin" test; tracked assets, so fresh-clone safe.
CERTIFIED_YEARS = [y for y in _B.PIN.release_years() if _B.release_status(y)["certified"]]


def pinned_base(year: int) -> str:
    """The certified PINNED base of ``year`` -- or a clean skip: the bundle may
    be absent, and ``$RVT_GENESIS_BASE`` may point the resolver at a firm's
    own (non-pinned) base, whose authorship these tests cannot speak to."""
    try:
        rb = _B.resolve_base(target_release=year)
    except _B.BaseError as e:                         # pragma: no cover - bundle absent
        pytest.skip(f"pinned base for {year} unavailable: {e}")
    if not (rb.pinned and rb.certified):              # pragma: no cover - override in force
        pytest.skip(f"Revit {year}: the resolved base is not the certified pin "
                    f"({rb.path}; $RVT_GENESIS_BASE / --base override) -- these tests are of the pin only")
    return rb.path


def load_tool(name: str):
    """``tools/<name>.py`` executed as module ``name`` and registered in
    ``sys.modules`` under that name.  A fresh module per call: request it
    through a module-scoped fixture so one test file's patches never reach
    the next."""
    if name == "rvt_job":
        raise ValueError("rvt_job is the `job` fixture (ONE module object per process, #470), not load_tool")
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="session")
def job():
    """``tools/rvt_job.py`` -- the front door's job runner -- via the engine's
    cached loader (``rvt.frontdoor.edit.load_job_module``: ONE module object
    per process, registered as ``sys.modules["rvt_job"]`` by the engine
    itself -- the one the ``--rvt`` route AND ``tools/ifc_intent.py``'s gates
    drive; #470 / #477).  Patch it through ``monkeypatch`` only -- it is
    shared by every test file."""
    from rvt.frontdoor.edit import load_job_module
    return load_job_module()


#: the git-ignored research dirs: a FileNotFoundError under one of these
#: means "fresh clone without the research corpus / built ladders", never
#: "our code broke" -- those tests self-skip (CLAUDE.md: many tests
#: self-skip when samples/ or built ladders are absent).  samples/,
#: extracted/ and vendor/ are pure inputs; experiments/ holds the probe
#: ladders built on the owner's machine -- a test that BUILDS there fails
#: at build time with its own error, so a missing-file READ still cleanly
#: separates "not built here" from a genuine failure.
_RESEARCH_INPUT_DIRS = tuple(
    os.path.join(ROOT, d) + os.sep
    for d in ("samples", "extracted", "vendor", "experiments"))


def _missing_research_input(exc) -> str | None:
    if not isinstance(exc, FileNotFoundError):
        return None
    cand = exc.filename or (exc.args[0] if exc.args and
                            isinstance(exc.args[0], str) else "")
    ap = os.path.abspath(str(cand))
    if any(ap.startswith(d) for d in _RESEARCH_INPUT_DIRS):
        return ap
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when in ("setup", "call") and rep.outcome == "failed" \
            and call.excinfo is not None:
        path = _missing_research_input(call.excinfo.value)
        if path:
            rep.outcome = "skipped"
            rel = os.path.relpath(path, ROOT)
            rep.longrepr = (str(item.fspath), item.location[1] or 0,
                            f"Skipped: research input not in this clone: {rel}")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: large-file round trip (skip with RVT_SKIP_LARGE=1)")


# ---- runtime docs-read audit: pytest wiring (recorder + judge are defined at the top of this file) ------------------

def docs_audit_lines(verdict, everything=False):
    """The report: offenders always (they fail the run), the rest when ``everything``.  A tagged line per path, then
    one indented line per reader (test id) -- complete, never truncated: fixing an offender needs every id."""
    def rows(tag, bucket, gloss):
        return [line for path, ids in sorted(verdict[bucket].items())
                for line in ["  %-4s %s%s" % (tag, path, gloss)] + ["         <- %s" % i for i in ids]]
    lines = rows("FAIL", "offenders", "   (opened by the CI shard, NOT covered by SHARD_READS)")
    if everything:
        lines += rows("ok", "covered", "") + rows("--", "unenforced", "   (not a CI-shard file: recorded, not enforced)")
    if verdict["offenders"]:
        lines += ["Every repo docs/ file the CI shard opens must be matched by SHARD_READS in tools/dev/ci_fresh.sh, or a docs-only",
                  "merge touching it between a PR's sandboxed CI run and its merge stays FRESH on a stale verdict (#476/#487).",
                  "Ways out: the shard really needs the file -> add it to SHARD_READS there; otherwise stop reading it from the shard."]
    return lines


def pytest_collectstart(collector):
    if DOCS_AUDIT is not None:
        DOCS_AUDIT.enter(getattr(collector, "path", None), collector.nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    if DOCS_AUDIT is not None:                  # before logstart/setup, so fixture set-up reads belong to the item too
        DOCS_AUDIT.enter(getattr(item, "path", None), item.nodeid)


def pytest_sessionfinish(session, exitstatus):
    """Judge once, at the end; offenders turn an otherwise green run into exit 1 (the terminal section says why)."""
    if DOCS_AUDIT is None:
        return
    try:
        DOCS_AUDIT.verdict = DOCS_AUDIT.judge(shard_reads_pattern(), ci_shard_files())
    except Exception as e:                      # noqa: BLE001 -- cannot judge = fail closed, and say so
        DOCS_AUDIT.verdict = {"offenders": {"(the audit could not judge: %s: %s)" % (type(e).__name__, e): ["<session>"]},
                              "covered": {}, "unenforced": {}}
    if DOCS_AUDIT.verdict["offenders"] and session.exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    verdict = getattr(DOCS_AUDIT, "verdict", None)
    if verdict is None:
        return
    everything = os.environ.get("RVT_DOCS_AUDIT", "").strip().lower() == "report"
    if not (verdict["offenders"] or everything):
        return
    bad = bool(verdict["offenders"])
    terminalreporter.section("docs-read audit%s" % (" FAILED" if bad else ""), sep="=", red=bad, bold=bad)
    terminalreporter.line("%d repo docs/ file(s) opened by this test process; judged against SHARD_READS of tools/dev/ci_fresh.sh (#523)"
                          % sum(len(verdict[k]) for k in ("offenders", "covered", "unenforced")))
    for line in docs_audit_lines(verdict, everything):
        terminalreporter.line(line, red=bad and line.startswith("  FAIL"))


def pytest_report_header(config):
    if DOCS_AUDIT is None:
        return "docs-read audit: off (RVT_DOCS_AUDIT=%s)" % os.environ.get("RVT_DOCS_AUDIT", "")
    return "docs-read audit: on -- repo docs/ opens are judged against SHARD_READS (tools/dev/ci_fresh.sh) at session end; RVT_DOCS_AUDIT=report lists them, =0 turns it off"


# ---- the shared throwaway-git-repo helpers (#487 (c) / #523): one home instead of a copy per process test ---------

#: a hermetic git environment: fixed identity, no user/system config, no hooks -- so a developer's signing key,
#: template dir or `init.defaultBranch` never changes what a test repo looks like.
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
HAVE_GIT = shutil.which("git") is not None


def git(cwd, *args, env=None, timeout=60):
    """``git <args>`` in ``cwd`` under ``GIT_ENV`` (+ ``env`` overrides); raises on failure; -> stripped stdout."""
    return subprocess.run(["git", *map(str, args)], cwd=os.fspath(cwd), env=dict(GIT_ENV, **(env or {})), check=True,
                          capture_output=True, text=True, timeout=timeout).stdout.strip()


def git_commit(repo, files, msg, delete=()):
    """Append ``files`` ({relpath: text}), remove ``delete`` (relpaths), commit everything as ``msg`` -> the new HEAD sha."""
    for rel, text in files.items():
        path = os.path.join(os.fspath(repo), rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    for rel in delete:
        os.remove(os.path.join(os.fspath(repo), rel))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def git_repo(tmp_path):
    """A fresh, empty git repository on branch ``main`` at ``tmp_path/"repo"`` (skips cleanly without git).
    Fill it with ``git_commit(repo, {...}, "msg")``; drive it with ``git(repo, ...)``."""
    if not HAVE_GIT:
        pytest.skip("needs the git executable")
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    return repo
