"""test_selfcheck_release.py -- tekton-native's mandatory pre-delivery gate
(``tools/rvt_selfcheck.py``, shipped as ``skills/tekton-native/scripts/
rvt_selfcheck.py``) judges a project under ITS OWN release on every
certified pinned base (issue #518, Refs #116 / #70):

* the four self-checks (gzip CRC / page ECC / block walker / record stamps)
  reach ``PASS`` with every failure count zero on the 2024, 2025 and 2026 pins;
* the output of the release-aware text edit (#116) on a 2025/2024 base -- the
  documented ``edit -> selfcheck`` flow -- passes the gate too;
* a damaged copy -- partition header zeroed, schema stream mangled -- is a
  clean ``FAIL`` verdict (exit 1) or "not a container" (exit 2), never a
  traceback;
* the native framing constants are back after every run -- the foreign
  releases run first, so a leak would break the following native check.

Run: .venv/bin/python -m pytest tests/test_selfcheck_release.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import (FOREIGN, FOREIGN_FIRST, cfb_header_zeroed_copy, load_tool, partition_of,   # noqa: E402
                      pinned_base, rewrite_stream, zero_partition_header, zero_schema_bytes)
from rvt import versions as V                                  # noqa: E402

OLD_NAME, NEW_NAME = "GEN B1 - Basement", "OUR B1 - Basement"      # same length, on every pin
pytestmark = pytest.mark.usefixtures("no_release_leak")             # foreign pins run first: a leak breaks the native run


@pytest.fixture(scope="module")
def selfcheck():
    return load_tool("rvt_selfcheck")


@pytest.fixture(scope="module")
def edit_text():
    return load_tool("rvt_edit_text")


def _run(selfcheck, capsys, path: str, json_out: str):
    """(exit code, the --json report, captured stdout/stderr) of one selfcheck."""
    rc = selfcheck.main([path, "--json", json_out])
    cap = capsys.readouterr()
    assert "Traceback" not in cap.err + cap.out
    with open(json_out, encoding="utf-8") as fh:
        return rc, json.load(fh), cap


def _assert_pass(rc: int, rep: dict, printed: str) -> None:
    assert rc == 0 and rep["verdict"] == "PASS" and rep["failures"] == [], printed[-800:]
    assert rep["gzip"]["crc_failures"] == 0 and rep["gzip"]["members"] > 0
    assert rep["ecc"]["ecc_mismatches"] == 0 and rep["ecc"]["full_pages_checked"] > 0
    assert rep["walker"]["walker_errors"] == 0
    assert all(p["blocks"] > 0 for p in rep["walker"]["partitions"].values())
    st = rep["stamps"]
    assert st["stamp_failures"] == 0 and st["records_checked"] == st["stamps_valid"] > 0
    assert "VERDICT        : PASS" in printed


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_pinned_base_passes_under_its_own_release(year, selfcheck, tmp_path, capsys):
    rc, rep, cap = _run(selfcheck, capsys, pinned_base(year), str(tmp_path / "sc.json"))
    _assert_pass(rc, rep, cap.out)
    assert cap.err == "" and "release_note" not in rep        # certified pin: no release warning


def test_skip_stamps_walks_without_keeping_record_data(selfcheck, tmp_path, capsys):
    rc = selfcheck.main([pinned_base(FOREIGN_FIRST[0]), "--skip-stamps", "--json", str(tmp_path / "sc.json")])
    cap = capsys.readouterr()
    with open(tmp_path / "sc.json", encoding="utf-8") as fh:
        rep = json.load(fh)
    assert rc == 0 and rep["verdict"] == "PASS" and rep["walker"]["walker_errors"] == 0
    assert rep["stamps"] == {"records_checked": 0, "stamps_valid": 0, "stamp_failures": 0, "skipped": True}
    assert "4 record stamps: skipped (--skip-stamps)" in cap.out


@pytest.mark.parametrize("year", FOREIGN)
def test_edit_output_passes_the_gate(year, selfcheck, edit_text, tmp_path, capsys):
    """The SKILL's documented flow on a 2025/2024 file: edit, then selfcheck."""
    edited = str(tmp_path / "edited.rvt")
    rc = edit_text.main([pinned_base(year), "--old", OLD_NAME, "--new", NEW_NAME,
                         "--utf16", "-o", edited])
    assert rc == 0 and "SELF-CHECK PASS" in capsys.readouterr().out
    assert V.detect_release(edited) == year
    rc, rep, cap = _run(selfcheck, capsys, edited, str(tmp_path / "sc.json"))
    _assert_pass(rc, rep, cap.out)


def test_damaged_partition_is_a_fail_verdict_not_a_traceback(selfcheck, tmp_path, capsys):
    """First 16 bytes of Partitions/<N> zeroed: page 0's ECC trailer no longer
    matches and the stream header parses under no release."""
    src = pinned_base(FOREIGN_FIRST[0])
    pname = partition_of(src)
    bad = rewrite_stream(src, tmp_path / "hdr_zeroed.rvt", pname, zero_partition_header)
    rc, rep, cap = _run(selfcheck, capsys, bad, str(tmp_path / "sc.json"))
    assert rc == 1 and rep["verdict"] == "FAIL", cap.out[-800:]
    assert rep["walker"]["walker_errors"] == 1
    assert rep["walker"]["partitions"][pname]["first_errors"][0].startswith("ValueError: unexpected Partitions header")
    assert rep["ecc"]["ecc_mismatches"] == 1
    assert "VERDICT        : FAIL" in cap.out and "partition walker errors: 1" in cap.out


def test_damaged_schema_stream_still_reaches_a_verdict(selfcheck, tmp_path, capsys):
    """A 2025/2024 file whose Formats/Latest is mangled cannot enter its
    release context (#535: the helper raises past its own refusal); the gate
    says so on stderr and still FAILs the file on its own evidence."""
    if not FOREIGN:
        pytest.skip("no certified foreign-release pin")
    bad = rewrite_stream(pinned_base(FOREIGN[0]), tmp_path / "schema_dmg.rvt", "Formats/Latest", zero_schema_bytes)
    rc, rep, cap = _run(selfcheck, capsys, bad, str(tmp_path / "sc.json"))
    assert rc == 1 and rep["verdict"] == "FAIL", cap.out[-800:]
    assert cap.err.startswith("warning: no release context for ")
    assert rep["release_note"].startswith("no release context for ")      # --json says why ...
    assert rep["failures"][-1].startswith("judged without its release context (")   # ... and so does the verdict
    assert rep["gzip"]["crc_failures"] == 1 and rep["walker"]["walker_errors"] == 1


def test_non_container_exits_2(selfcheck, tmp_path, capsys):
    bad = cfb_header_zeroed_copy(pinned_base(FOREIGN_FIRST[0]), tmp_path / "cfb_zeroed.rvt")
    assert selfcheck.main([bad]) == 2
    cap = capsys.readouterr()
    assert "cannot open as an .rvt container" in cap.err and "Traceback" not in cap.err
    assert selfcheck.main([str(tmp_path / "missing.rvt")]) == 2
