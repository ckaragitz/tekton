"""test_inspect_release.py -- tekton-native's read-only introspection tool
(``tools/rvt_inspect.py``, shipped as ``skills/tekton-native/scripts/
rvt_inspect.py``) walks a project's records under ITS OWN release on every
certified pinned base (issue #533, Refs #518 / #116 / #70):

* ``--records N`` decodes N clean records against the file's own schema on
  the 2024, 2025 and 2026 pins (main: ``unexpected Partitions header`` on
  2025/2024), and the default listing + schema summary still runs everywhere;
* a native pin enters no release context at all (nothing extra imported),
  a foreign one the instrument ladder ``global_framing.enter_own_release``;
* the output of the release-aware text edit (#116) on a 2025/2024 base
  inspects cleanly -- the documented ``edit -> inspect`` flow;
* a damaged copy -- partition header zeroed, schema stream mangled, CFB
  header gone -- is a reported finding (exit 1 / 2), never a traceback;
* the native framing constants are back after every run -- the foreign
  releases run first, so a leak would break the following native walk.

Run: .venv/bin/python -m pytest tests/test_inspect_release.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import (CERTIFIED_YEARS, FOREIGN, FOREIGN_FIRST, cfb_header_zeroed_copy, load_tool,   # noqa: E402
                      ladder_constants, partition_of, pinned_base, rewrite_stream, truncated_copy,
                      zero_partition_header, zero_schema_bytes)
from rvt import global_framing as GF                           # noqa: E402
from rvt import versions as V                                  # noqa: E402

OLD_NAME, NEW_NAME = "GEN B1 - Basement", "OUR B1 - Basement"      # same length, on every pin
N = 20
pytestmark = pytest.mark.usefixtures("no_release_leak")             # foreign pins run first: a leak breaks the native walk


@pytest.fixture
def release_leak_extra():
    """This tool climbs the instrument ladder: watch what it swaps, too."""
    return ladder_constants


@pytest.fixture(scope="module")
def inspect_tool():
    return load_tool("rvt_inspect")


@pytest.fixture(scope="module")
def edit_text():
    return load_tool("rvt_edit_text")


def _run(inspect_tool, capsys, *argv):
    """(exit code, stdout, stderr) of one inspection -- never a traceback."""
    rc = inspect_tool.main(list(argv))
    cap = capsys.readouterr()
    assert "Traceback" not in cap.err + cap.out
    return rc, cap.out, cap.err


def _assert_records_clean(rc: int, out: str, err: str) -> None:
    assert rc == 0, (out + err)[-800:]
    assert "schema (Formats/Latest, " in out and "ADocument type id: 0x" in out
    assert f"decoding first {N} seq-102 records of ['Partitions/" in out
    assert out.rstrip().endswith(f"decode summary: {{'clean': {N}}}")     # one id= line per counted record
    assert err == ""                                          # certified pin: no release warning


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_records_decode_under_the_files_own_release(year, inspect_tool, capsys):
    rc, out, err = _run(inspect_tool, capsys, pinned_base(year), "--records", str(N), "--classes", "Wall")
    _assert_records_clean(rc, out, err)
    assert "\nclasses matching 'Wall': " in out and "  ArcWall\n" in out


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_default_summary_runs_on_every_pin(year, inspect_tool, capsys, tmp_path):
    dump = str(tmp_path / "schema.json")
    rc, out, err = _run(inspect_tool, capsys, pinned_base(year), "--dump-schema", dump)
    assert rc == 0 and err == ""
    assert out.startswith(f"== {pinned_base(year)} ==\nstreams (") and "Formats/Latest" in out
    assert "schema (Formats/Latest, " in out and "decoding first" not in out
    assert f"class map written: {dump}" in out and os.path.getsize(dump) > 0


def test_native_pin_enters_no_release_context(inspect_tool, capsys, monkeypatch):
    """A native file is walked as it always was: the own-release ladder is
    never reached (so nothing beyond the walk's own modules is imported)."""
    if V.LATEST_RELEASE not in CERTIFIED_YEARS:
        pytest.skip("no certified native-release pin")

    def _never(*_a, **_k):
        raise AssertionError("enter_own_release reached for a native file")
    monkeypatch.setattr(GF, "enter_own_release", _never)
    rc, out, err = _run(inspect_tool, capsys, pinned_base(V.LATEST_RELEASE), "--records", str(N))
    _assert_records_clean(rc, out, err)


@pytest.mark.parametrize("year", FOREIGN)
def test_edit_output_inspects_cleanly(year, inspect_tool, edit_text, tmp_path, capsys):
    """The SKILL's documented flow on a 2025/2024 file: edit, then look at it."""
    edited = str(tmp_path / "edited.rvt")
    rc = edit_text.main([pinned_base(year), "--old", OLD_NAME, "--new", NEW_NAME,
                         "--utf16", "-o", edited])
    assert rc == 0 and "SELF-CHECK PASS" in capsys.readouterr().out
    assert V.detect_release(edited) == year
    _assert_records_clean(*_run(inspect_tool, capsys, edited, "--records", str(N)))


def test_damaged_partition_is_reported_not_raised(inspect_tool, tmp_path, capsys):
    """First 16 bytes of Partitions/<N> zeroed: the stream header parses under
    no release -- the walk says so on its own line and in the summary."""
    src = pinned_base(FOREIGN_FIRST[0])
    pname = partition_of(src)
    bad = rewrite_stream(src, tmp_path / "hdr_zeroed.rvt", pname, zero_partition_header)
    rc, out, err = _run(inspect_tool, capsys, bad, "--records", str(N))
    assert rc == 1, out[-800:]
    assert "schema (Formats/Latest, " in out                # everything release-agnostic still reported
    assert f"  {pname}: cannot be walked (ValueError: unexpected Partitions header" in out
    assert out.rstrip().endswith("decode summary: {'unwalkable': 1}")
    # the same copy without --records never touches the partition: a clean summary
    rc, out, err = _run(inspect_tool, capsys, bad)
    assert rc == 0 and "decoding first" not in out and err == ""


def test_damaged_schema_stream_is_reported_not_raised(inspect_tool, tmp_path, capsys):
    """Formats/Latest mangled: the class map IS the tool's subject, so it says
    the schema is unreadable after the stream listing and stops (exit 1)."""
    bad = rewrite_stream(pinned_base(FOREIGN_FIRST[0]), tmp_path / "schema_dmg.rvt", "Formats/Latest", zero_schema_bytes)
    rc, out, err = _run(inspect_tool, capsys, bad, "--records", str(N))
    assert rc == 1 and "streams (" in out
    assert "\nschema (Formats/Latest): unreadable (ParseError: " in out
    assert "decoding first" not in out and err == ""


def test_truncated_file_is_reported_not_raised(inspect_tool, tmp_path, capsys):
    """A 64 KiB head of a pin still opens as CFB but its schema inflates to
    nothing: reported as unreadable, exit 1."""
    bad = truncated_copy(pinned_base(FOREIGN_FIRST[0]), tmp_path / "truncated.rvt", 65536)
    rc, out, err = _run(inspect_tool, capsys, bad, "--records", str(N))
    assert rc == 1 and "\nschema (Formats/Latest): unreadable (" in out and err == ""


def test_non_container_exits_2(inspect_tool, tmp_path, capsys):
    bad = cfb_header_zeroed_copy(pinned_base(FOREIGN_FIRST[0]), tmp_path / "cfb_zeroed.rvt")
    rc, out, err = _run(inspect_tool, capsys, bad, "--records", str(N))
    assert rc == 2 and "cannot open as an .rvt container" in err and out == ""
    rc, out, err = _run(inspect_tool, capsys, str(tmp_path / "missing.rvt"))
    assert rc == 2 and "no such file" in err
