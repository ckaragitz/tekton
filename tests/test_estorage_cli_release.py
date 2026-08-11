"""test_estorage_cli_release.py -- ``python -m rvt.estorage PATH`` (the
Extensible-Storage instrument's CLI) reads a project under ITS OWN release on
every certified pinned base (issue #566, Refs #548 / #533):

* ``--report --walk --roundtrip`` exits 0 with its four sections on the 2024,
  2025 and 2026 pins (main: ``unexpected Partitions header: v=9 cls=0x391 /
  0x37b`` on 2025/2024, before any walk);
* a pin whose archive schema declares no catalog layout the module reads would
  report an honest ``0 schemas (reason)`` -- from the library too: ``schemas()``
  returns an empty catalog carrying the reason, ``locate_schema_map`` its
  documented "nothing located" triple -- instead of raising ``ESSchemaError``
  (since #576 the 2024 pin's older ``m_storedSchemas`` layout is read, so every
  certified pin lists its schemas; tests/test_estorage_catalog_2024.py);
* the native pin enters no release context at all, a foreign one (via
  ``rvt.native_framing``) the instrument ladder ``global_framing.enter_own_release``
  -- and the real ``-m`` door agrees;
* a damaged copy (partition header zeroed) and a missing path are stated
  verdicts (exit 1 / 2 on stderr), never a traceback;
* the native framing constants are back after every run -- the foreign pins
  run first, so a leak would break the following native one.

Run: .venv/bin/python -m pytest tests/test_estorage_cli_release.py -q
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import (CERTIFIED_YEARS, FOREIGN, FOREIGN_FIRST, ladder_constants, partition_of,   # noqa: E402
                      pinned_base, rewrite_stream, zero_partition_header)
from rvt import estorage as ES                                    # noqa: E402
from rvt import global_framing as GF                              # noqa: E402
from rvt import versions as V                                     # noqa: E402

ALL_FLAGS = ("--report", "--walk", "--roundtrip")
pytestmark = pytest.mark.usefixtures("no_release_leak")             # foreign pins run first: a leak breaks the native run


@pytest.fixture
def release_leak_extra():
    """This CLI climbs the instrument ladder: watch what it swaps, too."""
    return ladder_constants


def _run(capsys, *argv):
    """(exit code, stdout, stderr) of one CLI run -- never a traceback."""
    rc = ES.main(list(argv))
    cap = capsys.readouterr()
    assert "Traceback" not in cap.err + cap.out
    return rc, cap.out, cap.err


def _has_catalog_layout(path: str) -> bool:
    """Does ``path``'s own archive schema declare an ES catalog layout the
    module reads (2025+ ``m_schemaUsageMap``, or the older ``m_storedSchemas``
    since #576 -- every certified pin today)?"""
    return ES.catalog_layout(GF.schema_of(path)) is not None


def _assert_full_report(rc: int, out: str, err: str, path: str) -> None:
    assert rc == 0, (out + err)[-800:]
    assert err == ""                                          # certified pin: no release warning
    name = os.path.splitext(os.path.basename(path))[0]
    assert out.startswith(f"loaded {name}: ") and " host elements\nES schema catalog: " in out
    if _has_catalog_layout(path):
        assert " schemas (map count " in out
    else:                                                     # honest, and it says why
        assert "\nES schema catalog: 0 schemas (this file's archive schema has no ES schema catalog class" in out
    assert "\nES report: " in out and "\nround-trip: examined " in out
    assert "DECODE FAIL" not in out and "ROUNDTRIP FAIL" not in out


def _never(*_a, **_k):
    raise AssertionError("enter_own_release reached for a natively framed file")


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_full_report_under_the_files_own_release(year, capsys, monkeypatch):
    """Foreign pins climb the ladder silently; the native pin is read as it
    always was -- the ladder is provably never reached (nothing extra imported)."""
    if year == V.LATEST_RELEASE:
        monkeypatch.setattr(GF, "enter_own_release", _never)
    path = pinned_base(year)
    _assert_full_report(*_run(capsys, path, *ALL_FLAGS), path)


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_library_reports_an_absent_map_instead_of_raising(year):
    """``schemas(path)`` under the file's own release: a catalog either way --
    empty + a stated reason where the pair class is absent (main: ESSchemaError)."""
    path = pinned_base(year)
    with GF.reading(path):
        cat = ES.schemas(path)
    if _has_catalog_layout(path):
        assert len(cat) and cat.map_offset > 0 and cat.note == ""
    else:
        assert len(cat) == 0 and cat.note.startswith("this file's archive schema has no ES schema catalog class")
        gl, _ = ES._global_latest_bytes(path)
        assert ES.locate_schema_map(gl, ES._decoder_for(path)) == (-1, 0, {})   # the documented "nothing located" triple


def test_module_door_on_a_foreign_pin():
    """The real ``python -m rvt.estorage`` door (a fresh interpreter whose
    first estorage import IS ``__main__``) on the oldest certified pin."""
    if not FOREIGN:
        pytest.skip("no certified foreign-release pin")
    path = pinned_base(min(FOREIGN))
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    proc = subprocess.run([sys.executable, "-m", "rvt.estorage", path, "--report", "--walk"],
                          capture_output=True, text=True, env=env, cwd=ROOT, timeout=300)
    assert "Traceback" not in proc.stderr + proc.stdout
    assert proc.returncode == 0, (proc.stdout + proc.stderr)[-800:]
    assert proc.stderr == "" and "\nES schema catalog: " in proc.stdout and "\nES report: " in proc.stdout


@pytest.mark.parametrize("year", [FOREIGN_FIRST[0], FOREIGN_FIRST[-1]] if CERTIFIED_YEARS else [])
def test_damaged_partition_is_a_stated_verdict(year, tmp_path, capsys):
    """First 16 bytes of Partitions/<N> zeroed (on a foreign and on the native
    pin): the header parses under no release -- said on stderr, exit 1."""
    src = pinned_base(year)
    bad = rewrite_stream(src, tmp_path / "hdr_zeroed.rvt", partition_of(src), zero_partition_header)
    rc, out, err = _run(capsys, bad, *ALL_FLAGS)
    assert rc == 1 and out == ""
    assert err.rstrip("\n").splitlines()[-1].startswith(f"ERROR: cannot load {bad}: ValueError: unexpected Partitions header")


def test_missing_path_exits_2(tmp_path, capsys):
    rc, out, err = _run(capsys, str(tmp_path / "missing.rvt"), "--report")
    assert rc == 2 and "no such file" in err and out == ""
