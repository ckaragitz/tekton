"""pytest bootstrap: make ``src/`` importable, register markers, and expose
the ONE schema-availability gate (``HAVE_SCHEMA`` / ``needs_schema``), the
ONE real-ifcopenshell gate (``HAVE_IFC_AUTHORING`` / ``needs_ifc_authoring``),
the "certified pinned base of a year, or a clean skip" helper
(``pinned_base`` / ``CERTIFIED_YEARS``), a ``tools/<name>.py`` loader
(``load_tool``) and the ``job`` fixture (``tools/rvt_job.py``)."""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

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
    per process, the one the ``--rvt`` route drives; #470), also aliased as
    ``sys.modules["rvt_job"]`` because ``tools/ifc_intent.py`` does ``import
    rvt_job`` (until the engine registers that name itself, #477).  Patch it
    through ``monkeypatch`` only -- it is shared by every test file."""
    from rvt.frontdoor.edit import load_job_module
    mod = load_job_module()
    sys.modules["rvt_job"] = mod
    return mod


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
