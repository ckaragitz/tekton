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

import dataclasses
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import CERTIFIED_YEARS, load_tool, pinned_base    # noqa: E402
from rvt import global_framing as GF                           # noqa: E402
from rvt import partitions as P                                # noqa: E402
from rvt import versions as V                                  # noqa: E402
from rvt.frontdoor import release_ctx as RC                    # noqa: E402

FOREIGN_FIRST = sorted(CERTIFIED_YEARS, key=lambda y: y == V.LATEST_RELEASE)
FOREIGN = [y for y in FOREIGN_FIRST if y != V.LATEST_RELEASE]      # the 2025/2024 pins
OLD_NAME, NEW_NAME = "GEN B1 - Basement", "OUR B1 - Basement"      # same length, on every pin
N = 20


@pytest.fixture(scope="module")
def inspect_tool():
    return load_tool("rvt_inspect")


@pytest.fixture(scope="module")
def edit_text():
    return load_tool("rvt_edit_text")


def _native_constants() -> dict:
    """Everything a leaked context would leave rebound: the partition framing
    table, plus what the instrument ladder swaps on top of it (records32's
    ``iter_records``, the default ADocument decoder, a Global-stream token)."""
    from rvt import adocument as ADOC
    from rvt import objects as O
    from rvt.famgen import famdoc_adoc as FDA
    snap = {k: getattr(P, k) for k in V.framing_table(V.LATEST_RELEASE)}
    snap.update(active_release=RC.active_release(), iter_records=O.iter_records,
                adoc_decoder=ADOC._DECODER, family_end_record=FDA.FAMILY_END_RECORD)
    return snap


@pytest.fixture(autouse=True)
def _no_leak():
    before = _native_constants()
    assert before["active_release"] is None
    yield
    assert _native_constants() == before


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


def _rewrite_stream(src: str, dst: str, name: str, damage) -> None:
    """``src`` re-emitted as ``dst`` with stream ``name``'s RAW bytes replaced
    by ``damage(raw)`` -- every other entry byte-identical."""
    from rvt.cfb_writer import write_cfb
    from rvt.container import open_rvt
    from rvt.roundtrip import read_entries
    with open_rvt(src) as d:
        raw = d.raw(name)
    write_cfb(dst, [dataclasses.replace(e, data=damage(raw))
                    if (e.entry_type == "stream" and e.path == name) else e
                    for e in read_entries(src)])


def _partition_of(path: str) -> str:
    from rvt.container import open_rvt
    with open_rvt(path) as d:
        return d.partition_streams()[0]


def test_damaged_partition_is_reported_not_raised(inspect_tool, tmp_path, capsys):
    """First 16 bytes of Partitions/<N> zeroed: the stream header parses under
    no release -- the walk says so on its own line and in the summary."""
    src = pinned_base(FOREIGN_FIRST[0])
    pname = _partition_of(src)
    bad = str(tmp_path / "hdr_zeroed.rvt")
    _rewrite_stream(src, bad, pname, lambda raw: bytes(16) + raw[16:])
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
    bad = str(tmp_path / "schema_dmg.rvt")
    _rewrite_stream(pinned_base(FOREIGN_FIRST[0]), bad, "Formats/Latest",
                    lambda raw: raw[:2000] + bytes(64) + raw[2064:])
    rc, out, err = _run(inspect_tool, capsys, bad, "--records", str(N))
    assert rc == 1 and "streams (" in out
    assert "\nschema (Formats/Latest): unreadable (ParseError: " in out
    assert "decoding first" not in out and err == ""


def test_truncated_file_is_reported_not_raised(inspect_tool, tmp_path, capsys):
    """A 64 KiB head of a pin still opens as CFB but its schema inflates to
    nothing: reported as unreadable, exit 1."""
    bad = str(tmp_path / "truncated.rvt")
    with open(pinned_base(FOREIGN_FIRST[0]), "rb") as fh, open(bad, "wb") as out_fh:
        out_fh.write(fh.read(65536))
    rc, out, err = _run(inspect_tool, capsys, bad, "--records", str(N))
    assert rc == 1 and "\nschema (Formats/Latest): unreadable (" in out and err == ""


def test_non_container_exits_2(inspect_tool, tmp_path, capsys):
    src = pinned_base(FOREIGN_FIRST[0])
    bad = str(tmp_path / "cfb_zeroed.rvt")
    shutil.copyfile(src, bad)
    with open(bad, "r+b") as fh:
        fh.write(bytes(512))                                  # the CFB header sector
    rc, out, err = _run(inspect_tool, capsys, bad, "--records", str(N))
    assert rc == 2 and "cannot open as an .rvt container" in err and out == ""
    rc, out, err = _run(inspect_tool, capsys, str(tmp_path / "missing.rvt"))
    assert rc == 2 and "no such file" in err
