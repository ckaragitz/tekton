"""test_natively_framed.py -- the engine's ONE "is this open document natively
framed, or must its own release be entered first?" predicate + the "enter it
lazily, once, note-never-raise" helper (``rvt.native_framing``, issue #567,
Refs #533 / #518 / #116), and the law that the two read-side CLIs that used
to carry word-for-word copies (``tools/rvt_selfcheck.py``,
``tools/rvt_inspect.py``) call it instead of defining their own:

* ``natively_framed`` is True on the native pin, False on the 2025/2024 pins
  and on a copy whose partition header is zeroed -- and it never raises;
* ``enter_files_release`` enters NOTHING and imports neither ladder for a
  native file; enters the read-side ladder (default) or the authoring context
  (``host=True``) exactly once for a foreign pin, restored when the stack
  closes; and returns each ladder's own note -- never raises -- for a copy
  whose schema stream is mangled;
* importing ``rvt.native_framing`` pulls no ``rvt.frontdoor.*`` and no
  ``rvt.global_framing`` (the native path stays light, S-2026-08-09-g);
* neither tool defines ``natively_framed`` / ``enter_files_release`` or calls
  ``parse_stream_header`` itself any more (an AST law, so a third copy cannot
  creep back).

Run: .venv/bin/python -m pytest tests/test_natively_framed.py -q
"""
from __future__ import annotations

import ast
import contextlib
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import (CERTIFIED_YEARS, FOREIGN, partition_of, pinned_base, rewrite_stream,   # noqa: E402
                      zero_partition_header, zero_schema_bytes)
from rvt import global_framing as GF                           # noqa: E402
from rvt import native_framing as NF                           # noqa: E402
from rvt import partitions as P                                # noqa: E402
from rvt import versions as V                                  # noqa: E402
from rvt.container import open_rvt                             # noqa: E402
from rvt.frontdoor import release_ctx as RC                    # noqa: E402

TOOLS = ["rvt_selfcheck", "rvt_inspect", "rvt_edit_text"]      # every CLI that enters via rvt.native_framing
pytestmark = pytest.mark.usefixtures("no_release_leak")


def _native_pin() -> str:
    if V.LATEST_RELEASE not in CERTIFIED_YEARS:
        pytest.skip("no certified native-release pin")
    return pinned_base(V.LATEST_RELEASE)


def _never(*_a, **_k):
    raise AssertionError("a release ladder was reached for a natively framed file")


# -- the predicate -----------------------------------------------------------

def test_native_pin_is_natively_framed():
    with open_rvt(_native_pin()) as doc:
        assert NF.natively_framed(doc) is True


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_header_zeroed_copy_is_not_natively_framed_and_never_raises(year, tmp_path):
    src = pinned_base(year)
    bad = rewrite_stream(src, tmp_path / "hdr_zeroed.rvt", partition_of(src), zero_partition_header)
    with open_rvt(bad) as doc:
        assert NF.natively_framed(doc) is False


@pytest.mark.parametrize("year", FOREIGN)
def test_foreign_pin_is_native_only_inside_its_own_release(year):
    """False bare; True inside the file's own release context: the predicate
    reads ``rvt.partitions`` at call time, not a copy of the 2026 constants."""
    path = pinned_base(year)
    with open_rvt(path) as doc, contextlib.ExitStack() as stack:
        assert NF.natively_framed(doc) is False
        assert GF.enter_own_release(stack, path) is None
        assert NF.natively_framed(doc) is True


# -- the helper --------------------------------------------------------------

@pytest.mark.parametrize("host", [False, True])
def test_native_file_enters_nothing_and_reaches_no_ladder(host, monkeypatch):
    monkeypatch.setattr(GF, "enter_own_release", _never)
    monkeypatch.setattr(RC, "enter_host_release", _never)
    path = _native_pin()
    with open_rvt(path) as doc, contextlib.ExitStack() as stack:
        assert NF.enter_files_release(stack, doc, path, host=host) is None
        assert RC.active_release() is None
        assert P.CONTAINER_CLASS == V.framing_table(V.LATEST_RELEASE)["CONTAINER_CLASS"]


@pytest.mark.parametrize("year", FOREIGN)
def test_foreign_file_enters_the_read_side_ladder_once(year, monkeypatch):
    monkeypatch.setattr(RC, "enter_host_release", _never)          # default = the instrument ladder only
    path = pinned_base(year)
    want = V.framing_table(year)["CONTAINER_CLASS"]
    with open_rvt(path) as doc:
        with contextlib.ExitStack() as stack:
            assert NF.enter_files_release(stack, doc, path) is None
            assert P.CONTAINER_CLASS == want and RC.active_release() is None
            P.StreamWalker(doc.logical(doc.partition_streams()[0]), inflate=False)   # walks now
        assert P.CONTAINER_CLASS != want                              # restored when the stack closed


@pytest.mark.parametrize("year", FOREIGN)
def test_foreign_file_enters_the_host_context_once_when_asked(year, monkeypatch):
    monkeypatch.setattr(GF, "enter_own_release", _never)           # host=True = the authoring context only
    path = pinned_base(year)
    with open_rvt(path) as doc:
        with contextlib.ExitStack() as stack:
            assert NF.enter_files_release(stack, doc, path, host=True) is None
            assert RC.active_release() == year
            assert P.CONTAINER_CLASS == V.framing_table(year)["CONTAINER_CLASS"]
        assert RC.active_release() is None


def test_damaged_schema_is_each_ladders_own_note_never_a_raise(tmp_path):
    """64 bytes of ``Formats/Latest`` zeroed on a foreign pin: the host context
    cannot be built (its note, nothing entered -- rvt_selfcheck's #535 row);
    the instrument ladder falls back to the pinned table of the release
    ``BasicFileInfo`` declares (its note, and the partitions then walk --
    rvt_inspect's row).  Same sentences the tools printed before #567."""
    if not FOREIGN:
        pytest.skip("no certified foreign-release pin")
    year = FOREIGN[0]
    bad = rewrite_stream(pinned_base(year), tmp_path / "schema_dmg.rvt", "Formats/Latest", zero_schema_bytes)
    with open_rvt(bad) as doc:
        with contextlib.ExitStack() as stack:
            note = NF.enter_files_release(stack, doc, bad, host=True)
            assert note.startswith("no release context for schema_dmg.rvt: its Formats/Latest ")   # by name (#574)
            assert RC.active_release() is None and NF.natively_framed(doc) is False   # nothing entered
        with contextlib.ExitStack() as stack:
            note = NF.enter_files_release(stack, doc, bad)
            assert note.startswith("own schema unreadable (")
            assert note.endswith(f"checked against the pinned Revit {year} framing table "
                                 "(the release BasicFileInfo declares)")
            assert NF.natively_framed(doc) is True                    # the pinned rung is in force: it walks


# -- the native path stays light --------------------------------------------

def test_importing_the_module_pulls_neither_ladder():
    code = ("import sys; sys.path.insert(0, %r); import rvt.native_framing; "
            "print('\\n'.join(sorted(m for m in sys.modules if m.startswith('rvt'))))"
            % os.path.join(ROOT, "src"))
    mods = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True,
                          text=True, cwd=ROOT).stdout.split()
    assert "rvt.native_framing" in mods and "rvt.partitions" in mods
    heavy = [m for m in mods if m.startswith(("rvt.frontdoor", "rvt.global_framing", "rvt.versions",
                                              "rvt.schema", "rvt.famgen", "rvt.genesis"))]
    assert heavy == [], heavy


# -- the law: no private copies in the tools ---------------------------------

@pytest.mark.parametrize("tool", TOOLS)
def test_tool_carries_no_private_copy(tool):
    path = os.path.join(ROOT, "tools", f"{tool}.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not defined & {"natively_framed", "enter_files_release"}, defined
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "parse_stream_header" not in called            # the header probe lives in rvt.native_framing
    imported = {(n.module, a.name) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert ("rvt.native_framing", "enter_files_release") in imported
    # what ships is a byte-identical mirror of this source: tests/test_plugin_sync.py + sync_plugin --check own that
