"""test_input_release.py -- ``author --rvt FILE --edit ...`` classifies the
INPUT's era on every job (issue #176).

* :func:`rvt.meta.classify_bfi_era` tells the two ``BasicFileInfo`` layouts
  apart from their UTF-16LE mirror-text markers -- ``Format: 20xx`` (2019+)
  vs ``Revit Build: ... 20xx ...`` (2008-2018) -- on SYNTHETIC byte strings
  authored here from the documented marker grammar (docs/prior-art.md P1/P3):
  no samples, no donor bytes.
* :func:`rvt.frontdoor.input_release.input_release_block` lands every input
  in exactly one of ``known`` / ``unverified`` / ``refused``, and the
  ``--rvt`` route acts on it: a known release proceeds exactly as before
  (the manifest only GAINS the ``input_release`` block), a 2019+ release
  outside the roster whose own schema parses proceeds stamped
  UNVERIFIED-RELEASE, and a pre-2019 / undetectable / non-Revit input is
  refused with ONE line -- exit 2 at the CLI, no traceback, the refusal
  manifest on disk.

The containers are built in ``tmp_path`` with OUR OWN CFB writer; the
"unverified" input is our tracked, certified 2026 genesis base with its
``BasicFileInfo`` re-encoded (by our encoder) to declare a year tekton has
never read (re-emitted through conftest's ``rewrite_stream``, #639).
Fresh-clone runnable (listed in tests/ci_shard.txt).

Run: .venv/bin/python -m pytest tests/test_input_release.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import rewrite_stream                         # noqa: E402
from rvt import meta                                        # noqa: E402
from rvt import versions as V                              # noqa: E402
from rvt.cfb_writer import CfbEntry, write_cfb              # noqa: E402
from rvt.frontdoor import input_release as IR               # noqa: E402
import rvt.frontdoor as FD                                  # noqa: E402

BASE_2026 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
needs_base = pytest.mark.skipif(not os.path.isfile(BASE_2026),
                                reason="bundled genesis base missing")
LEVEL_EDIT = "set level 1351691 elevation to 5 ft"          # GEN B1 - Basement
UNREAD_YEAR = min(V.KNOWN_RELEASES) - 3                     # a 2019+ year tekton never read


# ---------------------------------------------------------------------------
# synthetic BasicFileInfo byte strings (authored here, from the marker grammar)
# ---------------------------------------------------------------------------

def _utf16(text: str) -> bytes:
    return text.encode("utf-16le")


def bfi_2019(year: object = 2026, *, odd_offset: bool = True) -> bytes:
    """A 2019+-era stream: a binary prologue (odd length, as in real files --
    the mirror text then sits at an odd byte offset) + the UTF-16LE mirror."""
    prologue = b"\x0e\x00\x00\x00\x00\x00\x00\x00\x00\x00" + (b"\x03" if odd_offset else b"")
    mirror = (f"Worksharing: Not enabled\r\nUsername: \r\nCentral Model Path: \r\n"
              f"Format: {year}\r\nBuild: 20250101_0000(x64)\r\nLast Save Path: C:\\job\\a.rvt\r\n")
    return prologue + b"\r\n" + _utf16(mirror) + b"\r\n"


def bfi_2008(year: object = 2014) -> bytes:
    """A 2008-2018-era stream: 'Revit Build: <product> <year> (Build: ...)'."""
    mirror = (f"Worksharing: Not enabled\r\nRevit Build: Revit Architecture {year} "
              f"(Build: 20130308_1515)\r\nLast Save Path: C:\\archive\\old.rvt\r\n")
    return b"\x04\x00\x00\x00\x00" + _utf16(mirror)


@pytest.mark.parametrize("raw,era,year", [
    (bfi_2019(2026), "2019+", 2026),
    (bfi_2019(2019, odd_offset=False), "2019+", 2019),
    (bfi_2019(2031), "2019+", 2031),
    (bfi_2019(""), "2019+", None),                     # marker, no year after it
    (bfi_2008(2014), "2008-2018", 2014),
    (bfi_2008(2008), "2008-2018", 2008),
    (b"\x04\x00\x00\x00\x00" + _utf16("Revit Build: (Build: unknown)\r\n"), "2008-2018", None),
    (b"", "unknown", None),
    (b"\x00" * 300, "unknown", None),
    (b"PK\x03\x04 not a BasicFileInfo at all", "unknown", None),
    (_utf16("Format 2026 Build 2026"), "unknown", None),   # words without the ':' markers
])
def test_classify_bfi_era_on_synthetic_streams(raw, era, year):
    assert meta.classify_bfi_era(raw) == {"era": era, "year": year}


def test_classify_prefers_format_marker_and_reads_only_its_own_line():
    # both markers present (a 2019+ file whose save path mentions the old one):
    # 'Format:' wins; the year is read from the Format line only, never from
    # the Build stamp on the next line
    raw = bfi_2019("20xx") + _utf16("Revit Build: Revit 2012 (Build: 1)\r\n")
    assert meta.classify_bfi_era(raw) == {"era": "2019+", "year": None}


@pytest.mark.parametrize("year,name", [(2026, "G_ABPD.rvt"), (2025, "G_ABPD_2025.rvt"),
                                       (2024, "G_ABPD_2024.rvt")])
def test_classify_our_own_bases_are_2019_era_with_their_year(year, name):
    from rvt.container import open_rvt
    p = os.path.join(os.path.dirname(BASE_2026), name)
    if not os.path.isfile(p):
        pytest.skip(f"bundled base {name} missing")
    with open_rvt(p) as d:
        assert meta.classify_bfi_era(d.raw("BasicFileInfo")) == {"era": "2019+", "year": year}


# ---------------------------------------------------------------------------
# synthetic containers (our own CFB writer) for the three branches
# ---------------------------------------------------------------------------

def _cfb(path, bfi: bytes | None, schema: bytes | None = b"\x00" * 64) -> str:
    entries = [CfbEntry("", "root")]
    if bfi is not None:
        entries.append(CfbEntry("BasicFileInfo", "stream", bfi))
    if schema is not None:
        entries += [CfbEntry("Formats", "storage"), CfbEntry("Formats/Latest", "stream", schema)]
    write_cfb(str(path), entries)
    return str(path)


def _base_declaring(path, year: int) -> str:
    """Our certified 2026 base, byte-identical except that its BasicFileInfo
    (re-encoded by OUR encoder) declares ``year``."""
    from rvt.stream_encoders import decode_basic_file_info, encode_basic_file_info

    def redate(raw: bytes) -> bytes:
        return encode_basic_file_info(dict(decode_basic_file_info(raw), format=str(year)))

    return rewrite_stream(BASE_2026, path, "BasicFileInfo", redate)


def test_floor_is_derived_from_the_version_model():
    floor = IR.verified_floor()
    assert floor["read"] == sorted(V.KNOWN_RELEASES) and floor["read"][0] == min(V.KNOWN_RELEASES)
    assert floor["edit"] == sorted(V.SUPPORTED_CREATION_RELEASES)


@pytest.mark.parametrize("make,era,year,needle", [
    (lambda p: _cfb(p, bfi_2008(2014)), "2008-2018", 2014, "pre-2019 BasicFileInfo layout"),
    (lambda p: _cfb(p, bfi_2019("")), "2019+", None, "no release year"),
    (lambda p: _cfb(p, bfi_2019(UNREAD_YEAR)), "2019+", UNREAD_YEAR, "schema does not parse"),
    (lambda p: _cfb(p, bfi_2019(2026), schema=None), "2019+", 2026, "no Formats/Latest"),
    (lambda p: _cfb(p, None, schema=None), "unknown", None, "no Formats/Latest"),
    (lambda p: (p.write_bytes(b"not a compound file\n"), str(p))[1], "unknown", None, "not an OLE2"),
])
def test_block_refuses_unreadable_inputs_with_one_line(tmp_path, make, era, year, needle):
    blk = IR.input_release_block(make(tmp_path / "in.rvt"))
    assert blk["status"] == "refused", blk
    assert (blk["era"], blk["year"]) == (era, year)
    line = blk["line"]
    assert line.startswith(IR.REFUSED_PREFIX) and "\n" not in line
    assert needle in line
    floor = IR.verified_floor()
    # the ONE line names the verified floor and both remedies
    assert f"reads Revit {floor['read'][0]}+" in line and f"edits Revit {floor['edit'][0]}+" in line
    assert "re-save it in Revit" in line and "IFC" in line


@needs_base
def test_block_known_release_is_cheap_and_unstamped():
    blk = IR.input_release_block(BASE_2026)
    assert (blk["status"], blk["era"], blk["year"]) == ("known", "2019+", 2026)
    assert "stamp" not in blk and "line" not in blk


@needs_base
def test_block_unread_year_with_parseable_schema_is_unverified(tmp_path):
    blk = IR.input_release_block(_base_declaring(tmp_path / "old.rvt", UNREAD_YEAR))
    assert (blk["status"], blk["era"], blk["year"]) == ("unverified", "2019+", UNREAD_YEAR)
    assert blk["stamp"] == IR.UNVERIFIED_STAMP == f"{IR.UNVERIFIED_TAG}: " + blk["stamp"].split(": ", 1)[1]
    assert "older" in blk["note"] and IR.UNVERIFIED_TAG not in blk["note"]
    newer = IR.input_release_block(_base_declaring(tmp_path / "new.rvt", max(V.KNOWN_RELEASES) + 1))
    assert newer["status"] == "unverified" and "newer" in newer["note"]


# ---------------------------------------------------------------------------
# the --rvt route acts on the block (all three branches)
# ---------------------------------------------------------------------------

def _cli():
    p = os.path.join(ROOT, "tools", "frontdoor.py")
    spec = importlib.util.spec_from_file_location("frontdoor_cli_176", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("make", [
    lambda p: _cfb(p, bfi_2008(2016)),
    lambda p: (p.write_bytes(b"\x00" * 4096), str(p))[1],
])
def test_route_refuses_with_exit_2_one_line_and_a_manifest(tmp_path, capsys, make):
    src = make(tmp_path / "their.rvt")
    out = tmp_path / "job"
    # the Python API: the refusal is a FrontDoorError carrying the result
    with pytest.raises(FD.InputReleaseRefused) as ei:
        FD.author(rvt=src, edit="move DP-1 to 3,1,4.66", out=str(out))
    exc = ei.value
    assert isinstance(exc, FD.FrontDoorError)
    assert str(exc).startswith(IR.REFUSED_PREFIX) and "\n" not in str(exc)
    res = exc.result
    assert res.route == "rvt" and res.ok is False and res.status == str(exc)
    man = json.loads((out / "manifest.json").read_text())
    assert man["status"] == str(exc) and man["input_release"]["status"] == "refused"
    assert man["honesty"]["release"] == str(exc)          # not "Revit 2026 target ..."
    assert not res.files and man["output"] in (None, {})
    assert "Input release" in (out / "MANIFEST.md").read_text()
    # the CLI: usage-error exit 2, the one line on stderr, never a traceback
    cli = _cli()
    rc = cli.main(["author", "--rvt", src, "--edit", "move DP-1 to 3,1,4.66",
                   "--out", str(tmp_path / "job2"), "--json"])
    assert rc == cli.EX_USAGE == 2
    err = capsys.readouterr().err
    assert IR.REFUSED_PREFIX in err and "Traceback" not in err


@needs_base
def test_route_known_release_proceeds_as_before_and_reports_the_block(tmp_path):
    r = FD.author(rvt=BASE_2026, edit=LEVEL_EDIT, out=str(tmp_path / "job"))
    assert r.ok, (r.status, r.errors)
    ir = r.manifest["input_release"]
    assert (ir["status"], ir["year"], ir["era"]) == ("known", 2026, "2019+")
    # a KNOWN release carries no UNVERIFIED-RELEASE label anywhere; the edit's own
    # P0 label (PROOF-ONLY, #406) is a stamp like on the create routes and may ride
    assert "UNVERIFIED" not in r.status and not any("UNVERIFIED" in s for s in r.as_json()["stamps"])
    assert r.manifest["target_version"]["input_release"] == 2026     # the #24 block, unchanged


@needs_base
def test_route_unread_release_proceeds_stamped_unverified(tmp_path):
    src = _base_declaring(tmp_path / "old.rvt", UNREAD_YEAR)
    r = FD.author(rvt=src, edit=LEVEL_EDIT, out=str(tmp_path / "job"))
    ir = r.manifest["input_release"]
    assert ir["status"] == "unverified" and ir["year"] == UNREAD_YEAR
    # manifest AND status AND the --json stamps carry it, whatever the edit did
    assert IR.UNVERIFIED_STAMP in r.manifest["honesty"]["proof_only_stamps"]
    assert IR.UNVERIFIED_STAMP in r.as_json()["stamps"]
    assert f"{IR.UNVERIFIED_TAG} (input Revit {UNREAD_YEAR})" in r.status
    # this synthetic input carries a schema tekton CAN read, so the edit is
    # expected to complete and DELIVER (rule 1) -- stamped, never withheld
    assert r.ok, (r.status, r.errors)
    assert r.files.get("edited") and os.path.isfile(r.files["edited"])
