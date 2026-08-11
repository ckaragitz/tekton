"""pytest bootstrap: make ``src/`` importable, register markers, and expose
the ONE schema-availability gate (``HAVE_SCHEMA`` / ``needs_schema``), the
ONE real-ifcopenshell gate (``HAVE_IFC_AUTHORING`` / ``needs_ifc_authoring``),
the "certified pinned base of a year, or a clean skip" helper
(``pinned_base`` / ``CERTIFIED_YEARS``), a ``tools/<name>.py`` loader
(``load_tool``) and the ``job`` fixture (``tools/rvt_job.py``); plus the
runtime docs-read audit (``DOCS_AUDIT``: which repo ``docs/`` files did this
test process open, checked at session end against ``tools/dev/ci_fresh.sh``'s
``SHARD_READS``, #523), the shared throwaway-git-repo helpers
(``GIT_ENV`` / ``git`` / ``git_init`` / ``git_commit`` / ``HAVE_GIT`` / the ``git_repo`` fixture)
and the shared own-release scaffolding of the ``test_*_release.py`` files (#579:
``FOREIGN_FIRST`` / ``FOREIGN``, ``native_constants`` / ``ladder_constants`` + the opt-in
``no_release_leak`` fixture, ``rewrite_stream(s)`` / ``partition_of`` / ``twin_partition_entry`` and the damaged-copy
recipes, plus the offset recipes ``smash64`` / ``flip_bit`` (#617), the ``pin`` fixture and the ``streams``
container reader (#670))."""
import dataclasses
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

#: the audited top-level directory of the repo (the recorder below and tests/test_docs_read_audit.py build every path from it).
AUDITED_DIR = "docs"
CI_FRESH = os.path.join(ROOT, "tools", "dev", "ci_fresh.sh")
SESSION_ID = "<session>"                     # the reader id outside any test item or module: conftest import, sessionstart
#: set on ``sys`` once the hook is installed: ONE recorder + ONE (unremovable) audit hook per interpreter, even if this
#: file is executed a second time (another import mode, a reload) -- the second module object adopts the first recorder.
AUDIT_SENTINEL = "_rvt_docs_read_audit"
READ_BUCKETS = ("offenders", "covered", "unenforced", "unjudged")      # the verdict keys that map a docs path -> [reader ids]
#: ``RVT_DOCS_AUDIT``: ``0``/``off`` = do not install the hook (the documented opt-out should it ever cost time);
#: ``report`` = also print every recorded read at session end (offenders always print); anything else = on.
DOCS_AUDIT_MODE = {"0": "off", "off": "off", "no": "off", "false": "off", "report": "report"}.get(
    os.environ.get("RVT_DOCS_AUDIT", "").strip().lower(), "on")


class DocsReadAudit:
    """A ``sys.addaudithook`` callable recording every ``open`` (builtins/io/pathlib/os.open/open_code all raise
    the one ``open`` event) whose normalised path lies under ``<root>/docs/``, keyed by repo-relative posix path,
    with the context (test module, reader id) that was current when it happened.  Exact where the static scan of
    tests/test_ci_fresh.py is heuristic: a read through a variable, a glob or ``src/``/``tools/`` code is seen the
    same as a literal one.  Not seen, by construction: reads made by a *subprocess* (another interpreter) or by a C
    extension that opens the path itself (``ifcopenshell.open``; numpy's readers go through Python's ``open`` and ARE
    seen); a write-mode ``open`` under docs/ counts as a read (the mode is not parsed -- conservative on purpose).
    Cost: one string compare per audited event, a normpath per ``open`` -- measured on the merged shard: noise.

    The rule (``kind``): a read is COVERED when ``SHARD_READS`` matches its path; otherwise it is an OFFENDER --
    unless it was made under a test module that is not in the merged CI shard, which is UNENFORCED (recorded and
    listed, never failed: the full suite legitimately reads more than CI does; inside tools/dev/session_ci.sh every
    collected module is in the shard by construction, so this can only under-enforce a mixed local run, never CI).
    Attribution is "whoever was current": a session fixture's or a cached reader's open belongs to the first test
    that triggers it -- so fix an offender in SHARD_READS or in the reader, never by reordering tests."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.prefix = os.path.join(self.root, AUDITED_DIR) + os.sep
        self.context = ("", SESSION_ID)        # (repo-relative posix path of the current test MODULE or "", reader id)
        self.reads = {}                        # "docs/x/y.md" -> {context, ...}
        self.verdict = None                    # set by judge() at session end; read by the terminal summary
        self._rules = None                     # (compiled SHARD_READS, frozenset(shard)) once loaded

    def __call__(self, event, args):
        if event != "open":
            return
        try:
            p = args[0]
            if p is None or isinstance(p, int):                     # an fd being wrapped, not a path
                return
            p = os.fsdecode(p)                                       # str / bytes / PathLike alike
            if os.path.isabs(p):
                if AUDITED_DIR not in p:                             # the common case (imports, tmp files) ends here
                    return
            else:
                p = os.path.join(os.getcwd(), p)
            p = os.path.normpath(p)
            if p.startswith(self.prefix):
                rel = AUDITED_DIR + "/" + p[len(self.prefix):].replace(os.sep, "/")
                self.reads.setdefault(rel, set()).add(self.context)
        except Exception:                        # noqa: BLE001 -- a raising audit hook breaks the open() it watches: never
            pass

    def enter(self, module_path, reader_id):
        """Attribute what follows to ``reader_id``; ``module_path`` = the test module it belongs to (items, Module and
        Class collectors have one; the session and directory collectors pass None and count as session level)."""
        rel = ""
        if module_path is not None:
            ap = os.path.abspath(os.fspath(module_path))
            if ap.startswith(self.root + os.sep):
                rel = os.path.relpath(ap, self.root).replace(os.sep, "/")
        self.context = (rel, reader_id or SESSION_ID)

    def rules(self):
        """(compiled ``SHARD_READS``, the merged CI shard) -- loaded once, from their one source each; raises if either
        cannot be read (the session-end judge records that as ``error`` and fails the run closed)."""
        if self._rules is None:
            self._rules = (re.compile(shard_reads_pattern()), frozenset(ci_shard_files()))
        return self._rules

    @staticmethod
    def kind(path, module, rx, shard):
        if rx.match(path):
            return "covered"
        return "unenforced" if module and module not in shard else "offenders"

    def offences(self, context):
        """The uncovered, enforced docs paths recorded under ``context`` -- the per-test channel, so an offender is a
        normal red test in pytest's own tally.  [] when the rules cannot be loaded (left to the session-end judge)."""
        try:
            rx, shard = self.rules()
        except Exception:                        # noqa: BLE001
            return []
        return sorted(path for path, contexts in self.reads.items()
                      if context in contexts and self.kind(path, context[0], rx, shard) == "offenders")

    def judge(self):
        """The session-end verdict over every recorded read -> ``self.verdict`` =
        {"offenders": {path: [ids]}, "covered": {…}, "unenforced": {…}, "unjudged": {}, "error": None} -- or, when the
        rules cannot be loaded, ``error`` = "Type: message" and every recorded read lands in ``unjudged`` instead: the
        run fails CLOSED on that (``audit_failed``), in its own words, however few reads there were (even none)."""
        out = dict({bucket: {} for bucket in READ_BUCKETS}, error=None)
        try:
            rx, shard = self.rules()
            kind = lambda path, module: self.kind(path, module, rx, shard)      # noqa: E731
        except Exception as e:                   # noqa: BLE001 -- cannot judge = fail closed, and say so
            out["error"] = "%s: %s" % (type(e).__name__, e)
            kind = lambda path, module: "unjudged"                              # noqa: E731
        for path, contexts in sorted(self.reads.items()):
            for module, reader_id in sorted(contexts):
                out[kind(path, module)].setdefault(path, []).append(reader_id)
        self.verdict = out
        return out


def audit_failed(verdict):
    """Does this verdict fail the run?  An uncovered read by the shard does; so does a judge that could not judge."""
    return bool(verdict["offenders"] or verdict["error"])


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


#: the process-wide recorder (``from conftest import DOCS_AUDIT``); ``None`` when opted out (``RVT_DOCS_AUDIT=0``).
DOCS_AUDIT = None
if DOCS_AUDIT_MODE != "off":
    DOCS_AUDIT = getattr(sys, AUDIT_SENTINEL, None)          # a second execution of this file adopts the first recorder
    if DOCS_AUDIT is None:
        DOCS_AUDIT = DocsReadAudit(ROOT)
        sys.addaudithook(DOCS_AUDIT)
        setattr(sys, AUDIT_SENTINEL, DOCS_AUDIT)

from rvt import versions as _V                                # noqa: E402  (already loaded by frontdoor.base)
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


# ---- the shared own-release scaffolding (#579): one home for what every "under the file's OWN release" test needs --

#: The certified years with the NATIVE release LAST (``from conftest import FOREIGN_FIRST, FOREIGN``): parametrize
#: over ``FOREIGN_FIRST`` and a release context leaked by a 2025/2024 run breaks the native run that follows it in
#: the same process instead of hiding; ``FOREIGN`` = the foreign (2025/2024) pins alone, in the same order.
FOREIGN_FIRST = sorted(CERTIFIED_YEARS, key=lambda y: y == _V.LATEST_RELEASE)
FOREIGN = [y for y in FOREIGN_FIRST if y != _V.LATEST_RELEASE]


def native_constants() -> dict:
    """Everything a leaked release context would leave rebound: the native partition framing table (the one place
    the block tags live, #467) + ``release_ctx.active_release()`` (None outside any context)."""
    from rvt import partitions as P
    from rvt.frontdoor import release_ctx as RC
    snap = {k: getattr(P, k) for k in _V.framing_table(_V.LATEST_RELEASE)}
    snap["active_release"] = RC.active_release()
    return snap


def ladder_constants() -> dict:
    """What the read-side instrument ladder (``global_framing.enter_own_release``) swaps on top of the framing table:
    records32's ``iter_records``, the default ADocument decoder, famdoc's ``FAMILY_END_RECORD``.  A separate callable
    so only the files that climb the ladder pay for the famgen import (hand it to ``release_leak_extra``); the ONE
    list to grow when the ladder learns to swap another name."""
    from rvt import adocument as ADOC
    from rvt import objects as O
    from rvt.famgen import famdoc_adoc as FDA
    return {"iter_records": O.iter_records, "adoc_decoder": ADOC._DECODER, "family_end_record": FDA.FAMILY_END_RECORD}


@pytest.fixture
def release_leak_extra():
    """MORE for ``no_release_leak`` to watch, on top of ``native_constants()`` (which no override can drop): a
    zero-argument callable returning ``{name: value}`` -- override this fixture in a test file
    (``return ladder_constants``); None = nothing extra."""
    return None


@pytest.fixture
def no_release_leak(release_leak_extra):
    """Opt-in per file (``pytestmark = pytest.mark.usefixtures("no_release_leak")``): the test starts outside any
    release context and leaves every watched constant exactly as it found it -- or it is red at teardown."""
    def snapshot():
        snap = native_constants()
        if release_leak_extra is not None:
            snap.update(release_leak_extra())
        return snap
    before = snapshot()
    assert before["active_release"] is None
    yield
    assert snapshot() == before


@pytest.fixture(scope="module")
def pin() -> str:
    """The first of ``FOREIGN_FIRST`` via ``pinned_base`` (a foreign pin when one is certified, so a by-value native
    assumption shows), resolved once per test module; a clean skip when no pin is certified.  Enters no release
    context -- a test that decodes framing enters ``host_release_context(pin)`` itself (#670)."""
    if not CERTIFIED_YEARS:
        pytest.skip("no certified pinned base")
    return pinned_base(FOREIGN_FIRST[0])


def streams(path) -> dict:
    """``{stream path: raw (still paged) bytes}`` of every stream of the container at ``path`` (str or PathLike), in
    directory order -- the before/after census of a ``rewrite_stream(s)`` output (= ``rvt.roundtrip.read_streams``,
    #677)."""
    from rvt.roundtrip import read_streams
    return read_streams(path)


def rewrite_streams(src, dst, damages: dict, extra=()) -> str:
    """``src`` re-emitted as ``dst`` with, for every ``{name: damage}`` in ``damages``, that stream's RAW (still paged)
    bytes replaced by ``damage(raw)`` -- the stream dropped when its ``damage`` is None -- the ready-made ``extra``
    entries (``CfbEntry``, e.g. ``twin_partition_entry``) appended after the container's own, and every other entry
    byte-identical -> ``dst``.  ``src == dst`` rewrites in place.  A name the container does not hold is a KeyError,
    never a silent verbatim copy (the ONE such loop under tests/, #579 / #617 -- and since #640 not even that: it is
    the engine's ``rvt.roundtrip.rewrite_entries``, called here under the test-side names)."""
    from rvt.roundtrip import rewrite_entries
    return rewrite_entries(src, dst, damages, extra)


def rewrite_stream(src, dst, name: str, damage) -> str:
    """The one-stream ``rewrite_streams``: ``name``'s raw bytes -> ``damage(raw)`` (dropped when None) -> ``dst``."""
    return rewrite_streams(src, dst, {name: damage})


def partition_of(path) -> str:
    """The first ``Partitions/<N>`` stream of the container at ``path``."""
    from rvt.container import open_rvt
    with open_rvt(os.fspath(path)) as d:
        return d.partition_streams()[0]


def twin_partition_entry(src, damage=None):
    """``src``'s first partition stream as a ``CfbEntry`` renamed to the NEXT ``Partitions/<N+1>`` -- a second,
    NON-primary partition once handed to ``rewrite_streams(src, dst, {}, extra=[it])`` -- its raw bytes passed
    through ``damage`` when one is given (the primary itself stays untouched)."""
    from rvt.roundtrip import read_entries
    pname = partition_of(src)
    part = next(e for e in read_entries(os.fspath(src)) if e.entry_type == "stream" and e.path == pname)
    head, n = pname.rsplit("/", 1)
    return dataclasses.replace(part, path="%s/%d" % (head, int(n) + 1),
                               data=part.data if damage is None else damage(part.data))


def zero_partition_header(raw: bytes) -> bytes:
    """A ``rewrite_stream`` damage for a ``Partitions/<N>`` stream: its first 16 bytes zeroed -- the stream header
    then parses under no release and page 0's ECC trailer no longer matches."""
    return bytes(16) + raw[16:]


def zero_schema_bytes(raw: bytes) -> bytes:
    """A ``rewrite_stream`` damage for ``Formats/Latest``: 64 bytes zeroed inside its deflate body -- container and
    stream survive, the file's own class schema no longer inflates (#518's repro)."""
    return raw[:2000] + bytes(64) + raw[2064:]


def smash64(raw: bytes, off: int) -> bytes:
    """A ``rewrite_stream`` damage: the 64 bytes at ``off`` overwritten with ``0xff`` -- far beyond CRCIO auto-repair
    wherever they land.  No default ``off``: the useful ones differ per stream kind (``44 + 26 + 10 + …`` = inside a
    partition's first block body, ``8 + 10 + …`` = inside the ONE gzip body of a ``Global/*`` stream) and stay with
    the caller, which fixes one as ``lambda raw: smash64(raw, OFF)``."""
    return raw[:off] + b"\xff" * 64 + raw[off + 64:]


def flip_bit(raw: bytes, at: int, bit: int = 0) -> bytes:
    """A ``rewrite_stream`` damage (and a plain bytes recipe): bit ``bit`` of byte ``at`` flipped, nothing else --
    ONE payload bit inside a page is within Revit's auto-repair envelope; on an ECC trailer / parity byte it is one
    genuine framing mismatch.  ``at`` indexes like ``raw[at]`` (negative counts from the end, out of range raises)."""
    out = bytearray(raw)
    out[at] ^= 1 << bit
    return bytes(out)


def truncated_copy(src, dst, size: int) -> str:
    """The first ``size`` bytes of ``src`` written as ``dst`` -> ``dst`` (64 KiB of a pin still opens as CFB with an
    empty schema; 4 KiB does not open at all)."""
    with open(src, "rb") as fh, open(dst, "wb") as out:
        out.write(fh.read(size))
    return os.fspath(dst)


def cfb_header_zeroed_copy(src, dst) -> str:
    """``src`` copied to ``dst`` with its first sector (the CFB header) zeroed: same size, no longer a container."""
    shutil.copyfile(src, dst)
    with open(dst, "r+b") as fh:
        fh.write(bytes(512))
    return os.fspath(dst)


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

def docs_audit_header(verdict):
    """The section's first line: how many DISTINCT repo docs/ files were opened (a path listed under two buckets -- read
    by a shard and a non-shard module, say -- is one file), and what they were judged against.  Derived from the
    verdict rather than the recorder's ``reads`` so that a synthetic verdict reports the same way."""
    opened = len({path for bucket in READ_BUCKETS for path in verdict[bucket]})
    return "%d repo docs/ file(s) opened by this test process; judged against SHARD_READS of tools/dev/ci_fresh.sh (#523)" % opened


def docs_audit_lines(verdict, everything=False):
    """The report: what fails the run always (offenders; or the reason nothing could be judged, then every unjudged
    read), the rest when ``everything``.  A tagged line per path, then one indented line per reader (test id) --
    complete, never truncated: fixing an offender needs every id."""
    def rows(tag, bucket, gloss):
        return [line for path, ids in sorted(verdict[bucket].items())
                for line in ["  %-4s %s%s" % (tag, path, gloss)] + ["         <- %s" % i for i in ids]]
    if verdict["error"]:
        return (["  FAIL the audit could not judge any read (%s) -- fail closed: without SHARD_READS from tools/dev/ci_fresh.sh and the merged"
                 " shard from tools/dev/shard_list.py no docs/ read can be called covered; restore them" % verdict["error"]]
                + rows("??", "unjudged", "   (recorded, could not be judged)"))
    lines = rows("FAIL", "offenders", "   (opened by the CI shard, NOT covered by SHARD_READS)")
    if everything:
        lines += rows("ok", "covered", "") + rows("--", "unenforced", "   (not a CI-shard file: recorded, not enforced)")
    if verdict["offenders"]:
        lines += ["Every repo docs/ file the CI shard opens must be matched by SHARD_READS in tools/dev/ci_fresh.sh, or a docs-only",
                  "merge touching it between a PR's sandboxed CI run and its merge stays FRESH on a stale verdict (#476/#487).",
                  "Ways out: the shard really needs the file -> add it to SHARD_READS there; otherwise stop reading it from the shard."]
    return lines


def collector_module(collector):
    """The test module a collector's reads belong to = its nearest file-backed ancestor, itself included: a Module's own
    file (reads at import), a Class's file (reads while its methods are collected -- ``pytest_generate_tests``, param-id
    callables), any other ``pytest.File`` collector alike; the Session/Dir/Package sit above every file and have none."""
    owner = collector.getparent(pytest.File)
    return None if owner is None else owner.path


def pytest_collectstart(collector):
    if DOCS_AUDIT is not None:
        DOCS_AUDIT.enter(collector_module(collector), collector.nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    if DOCS_AUDIT is not None:                  # before logstart/setup, so fixture set-up reads belong to the item too
        DOCS_AUDIT.enter(item.path, item.nodeid)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """After the real teardown (so a session fixture's finalizer reads count too): an uncovered docs read made under
    this item makes THIS item red -- an error in pytest's own tally, which is what tools/dev/session_ci.sh reports."""
    if DOCS_AUDIT is not None:
        bad = DOCS_AUDIT.offences(DOCS_AUDIT.context)
        if bad:
            pytest.fail("docs-read audit (#523): this test opened %s -- repo docs/ file(s) NOT covered by SHARD_READS in "
                        "tools/dev/ci_fresh.sh; add them there if the CI shard really needs them, otherwise stop reading them "
                        "(the session-end section lists every reader)" % ", ".join(bad), pytrace=False)


def pytest_sessionfinish(session, exitstatus):
    """Judge every recorded read once, at the end.  Item-level offenders are already red tests; this also catches the
    reads no item owns (conftest import, module collection) and turns an otherwise green run into exit 1 for them."""
    if DOCS_AUDIT is not None and audit_failed(DOCS_AUDIT.judge()) and session.exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    verdict = DOCS_AUDIT.verdict if DOCS_AUDIT is not None else None
    everything = DOCS_AUDIT_MODE == "report"
    bad = verdict is not None and audit_failed(verdict)
    if verdict is None or not (bad or everything):
        return
    terminalreporter.section("docs-read audit%s" % (" FAILED" if bad else ""), sep="=", red=bad, bold=bad)
    terminalreporter.line(docs_audit_header(verdict))
    for line in docs_audit_lines(verdict, everything):
        terminalreporter.line(line, red=bad and line.startswith("  FAIL"))


def pytest_report_header(config):
    if DOCS_AUDIT is None:
        return "docs-read audit: off (RVT_DOCS_AUDIT=%s)" % os.environ.get("RVT_DOCS_AUDIT", "")
    return "docs-read audit: on -- repo docs/ opens are judged against SHARD_READS (tools/dev/ci_fresh.sh); RVT_DOCS_AUDIT=report lists them at the end, =0 turns it off"


# ---- the shared throwaway-git-repo helpers (#487 (c) / #523): one home instead of a copy per process test ---------

#: a hermetic git environment: fixed identity and no user/system config -- so a developer's signing key, template
#: dir or `init.defaultBranch` never changes what a test repo looks like.
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
HAVE_GIT = shutil.which("git") is not None


def git(cwd, *args):
    """``git <args>`` in ``cwd`` under ``GIT_ENV``; raises on failure; -> stripped stdout."""
    return subprocess.run(["git", *map(str, args)], cwd=os.fspath(cwd), env=GIT_ENV, check=True,
                          capture_output=True, text=True, timeout=60).stdout.strip()


def git_init(path):
    """Make ``path`` (created if missing) an empty repository on branch ``main`` -> ``path``.  The primitive under
    ``git_repo``, for rigs that need more than one repository (an upstream and its clone, say)."""
    os.makedirs(os.fspath(path), exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    return path


def git_commit(repo, files, msg, delete=()):
    """Append ``files`` ({relpath: text}), remove ``delete`` (relpaths), commit exactly those paths as ``msg`` -> the new
    HEAD sha.  Only the named paths are staged: anything else lying in the work tree (a rig's untracked helper copies,
    say) never rides along."""
    for rel, text in files.items():
        path = os.path.join(os.fspath(repo), rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    for rel in delete:
        os.remove(os.path.join(os.fspath(repo), rel))
    git(repo, "add", "-A", "--", *files, *delete)
    git(repo, "commit", "-qm", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def git_repo(tmp_path):
    """A fresh, empty git repository on branch ``main`` at ``tmp_path/"repo"`` (skips cleanly without git).
    Fill it with ``git_commit(repo, {...}, "msg")``; drive it with ``git(repo, ...)``."""
    if not HAVE_GIT:
        pytest.skip("needs the git executable")
    return git_init(tmp_path / "repo")
