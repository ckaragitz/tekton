"""pytest bootstrap: make ``src/`` importable, register markers, and expose
the ONE schema-availability gate (``HAVE_SCHEMA`` / ``needs_schema``)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from rvt.schema import schema_available                       # noqa: E402

#: The ONE schema gate (``from conftest import HAVE_SCHEMA, needs_schema``):
#: the engine-owned existence check, so only a genuinely absent source skips
#: and a present-but-broken schema FAILS the test that loads it.
HAVE_SCHEMA = schema_available()
needs_schema = pytest.mark.skipif(
    not HAVE_SCHEMA,
    reason="no class schema (extracted corpus and bundled genesis base both absent)")

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
