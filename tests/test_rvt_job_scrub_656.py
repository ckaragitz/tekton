"""``tools/rvt_job.py::scrub_identity`` after #656 -- the edit lane's in-place ``BasicFileInfo`` rewrite of the job's own
output is ``rvt.roundtrip.rewrite_entries(path, path, {"BasicFileInfo": own_basic_file_info(…)})``, not a private
``read_entries`` loop + ``.idtmp`` rename:

* the scrubbed file is byte-identical to the API driven apart with the same primitive, and asserts OUR identity (author =
  the product placeholder, no username, save path = the basename, the given document GUID -- History[0], as the lane hands
  it) -- ``identity_gate`` PASS -- with the file's mode kept and nothing else in the directory; no GUID given mints a fresh
  one, as main did;
* the ``rvt_job.py edit`` lane (manipulate-only ops -> ``scrub_identity(out, document_guid=History[0])``) on each pin
  delivers a file whose Unique Document GUID is History[0] and whose ``identity`` gate is PASS;
* a ``BasicFileInfo``-less file is still "identity not scrubbed" -- ``RuntimeError`` as on main, now *caused by* the API's
  ``KeyError`` -- raised before a byte is written, and the job's one FAILED line says so plainly;
* a write that dies half way leaves the job's file intact and no temp behind (inherited from ``rewrite_entries``);
* a file the caller may not write is a ``PermissionError`` with nothing written (the API's in-place gate, #661);
* no private ``read_entries`` / ``write_cfb`` loop is left in the scrub.

Pinned genesis bases only (fresh-clone safe); foreign pins scrubbed under their own release context, as the lane does.
The sha256 table of every documented use before == after the fold (three pins) is in the #656 record."""
from __future__ import annotations

import inspect
import json
import os
import re
import shutil
import stat
from pathlib import Path

import pytest

import conftest as C
from rvt import roundtrip as RT
from rvt.container import open_rvt
from rvt.frontdoor.release_ctx import host_release_context
from rvt.identity import BFI_STREAM, PRODUCT_AUTHOR_PLACEHOLDER, own_basic_file_info
from rvt.roundtrip import rewrite_entries
from rvt.stream_encoders import decode_basic_file_info, history_head_guid

pytestmark = pytest.mark.usefixtures("no_release_leak")

FIXED = "00000656-0656-4656-8656-000000000656"
LEVEL_ID = 1351691                                   # "GEN B1 - Basement", present in all three pins
# ``pin`` (the first of FOREIGN_FIRST, module-scoped, a clean skip when none is certified) is conftest's fixture (#679).


def _bfi(path) -> dict:
    with open_rvt(os.fspath(path)) as doc:
        return decode_basic_file_info(doc.raw(BFI_STREAM))


# --- (1)+(2) the fold: in place == the API apart, OUR identity, mode kept, directory clean ------------------------------

@pytest.mark.parametrize("year", C.FOREIGN_FIRST)
def test_scrub_in_place_equals_the_api_apart_and_asserts_our_identity(job, year, tmp_path):
    src = C.pinned_base(year)
    hist0 = history_head_guid(src)                    # the GUID the lane hands the scrub (History[0] coherence)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    victim = Path(shutil.copyfile(src, tmp_path / "a" / "scrubbed.rvt"))
    twin = tmp_path / "b" / "scrubbed.rvt"            # same basename => same save path => comparable bytes
    os.chmod(victim, 0o640)
    with host_release_context(str(victim)):           # foreign pins under their own release, as the lane runs it
        assert job.scrub_identity(str(victim), document_guid=hist0) == {"scrubbed": True, "document_guid": hist0}
    rewrite_entries(src, twin, {BFI_STREAM: lambda raw: own_basic_file_info(raw, out_path=str(twin), document_guid=hist0)})
    assert victim.read_bytes() == twin.read_bytes() != Path(src).read_bytes()
    assert sorted(os.listdir(tmp_path / "a")) == ["scrubbed.rvt"]                  # no .idtmp, no .tmp
    assert stat.S_IMODE(os.stat(victim).st_mode) == 0o640                          # the file's own bits, not mkstemp's
    m, base = _bfi(victim), _bfi(src)
    assert (m["author"], m["client_app_name"]) == (PRODUCT_AUTHOR_PLACEHOLDER, PRODUCT_AUTHOR_PLACEHOLDER)
    assert (m["username"], m["last_save_path"], m["central_model_path"]) == ("", "scrubbed.rvt", "")
    assert m["unique_document_guid"] == m["central_episode_guid"] == hist0
    assert (m["format"], m["build"]) == (base["format"], base["build"])             # the release marker stays
    gate = job.identity_gate(str(victim))
    assert gate["status"] == "PASS", gate["issues"]


def test_no_document_guid_mints_a_fresh_one_as_main_did(job, pin, tmp_path):
    victim = Path(shutil.copyfile(pin, tmp_path / "fresh.rvt"))
    with host_release_context(str(victim)):
        assert job.scrub_identity(str(victim)) == {"scrubbed": True, "document_guid": None}
    guid = _bfi(victim)["unique_document_guid"]
    assert re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", guid) and guid != _bfi(pin)["unique_document_guid"]


# --- (2) the lane: rvt_job.py edit with manipulate-only ops scrubs with History[0] ---------------------------------------

@pytest.mark.parametrize("year", C.FOREIGN_FIRST)
def test_the_edit_lane_delivers_our_identity_coherent_with_history(job, year, tmp_path):
    src = C.pinned_base(year)
    ops = tmp_path / "ops.json"
    ops.write_text(json.dumps([{"op": "set-level", "id": LEVEL_ID, "elevation_ft": 5.0}]))
    out = tmp_path / f"rj{year}" / "out.rvt"
    assert job.main(["edit", src, "--ops", str(ops), "-o", str(out), "--no-provenance"]) == 0
    manifest = json.loads(Path(str(out) + ".manifest.json").read_text())
    assert manifest["gates"]["identity"]["status"] == "PASS", manifest["gates"]["identity"]
    m = _bfi(out)
    assert m["unique_document_guid"].lower() == history_head_guid(src).lower() == manifest["base"]["history_head_guid"].lower()
    assert (m["author"], m["username"], m["last_save_path"]) == (PRODUCT_AUTHOR_PLACEHOLDER, "", "out.rvt")
    assert not [n for n in os.listdir(out.parent) if n.endswith((".idtmp", ".tmp"))]


# --- (3) a BasicFileInfo-less file: "identity not scrubbed", before a byte is written ------------------------------------

def test_a_file_without_basicfileinfo_is_identity_not_scrubbed_plainly(job, pin, tmp_path, capsys):
    victim = Path(C.rewrite_stream(pin, tmp_path / "nobfi.rvt", BFI_STREAM, None))
    before = victim.read_bytes()
    with pytest.raises(RuntimeError, match="BasicFileInfo stream not found; identity not scrubbed") as ei:
        job.scrub_identity(str(victim), document_guid=FIXED)
    assert isinstance(ei.value.__cause__, KeyError) and BFI_STREAM in str(ei.value.__cause__)   # the API's own error
    assert victim.read_bytes() == before and sorted(os.listdir(tmp_path)) == ["nobfi.rvt"]
    capsys.readouterr()
    assert "identity not scrubbed" in job._failed("edit", ei.value)                # the lane's status / manifest line ...
    assert "identity not scrubbed" in capsys.readouterr().err                      # ... and its one stderr line


# --- (3) in place: a dying write leaves the job's file intact; a read-only file is refused before anything is written --

def test_a_write_that_dies_half_way_leaves_the_jobs_file_intact_and_no_temp_behind(job, pin, tmp_path, monkeypatch):
    victim = Path(shutil.copyfile(pin, tmp_path / "victim.rvt"))
    before = victim.read_bytes()
    aimed = []

    def dying(path, entries, *a, **kw):                                            # a torn temp, then ENOSPC
        aimed.append(path)
        Path(path).write_bytes(b"torn")
        raise OSError(28, "No space left on device (injected)")
    monkeypatch.setattr(RT, "write_cfb", dying)
    with pytest.raises(OSError, match="injected"):
        job.scrub_identity(str(victim), document_guid=FIXED)
    assert victim.read_bytes() == before                                            # not torn, not half-scrubbed
    assert sorted(os.listdir(tmp_path)) == ["victim.rvt"]                            # the temp left with the error
    assert len(aimed) == 1 and aimed[0] != str(victim) and os.path.dirname(aimed[0]) == str(tmp_path)


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0,
                    reason="root may write a read-only file; the gate is the OS's, not ours")
def test_a_read_only_file_is_a_permissionerror_with_nothing_written(job, pin, tmp_path):
    victim = Path(shutil.copyfile(pin, tmp_path / "ro.rvt"))
    before = victim.read_bytes()
    os.chmod(victim, 0o444)
    try:
        with pytest.raises(PermissionError):
            job.scrub_identity(str(victim), document_guid=FIXED)
        assert victim.read_bytes() == before and sorted(os.listdir(tmp_path)) == ["ro.rvt"]
        assert stat.S_IMODE(os.stat(victim).st_mode) == 0o444
    finally:
        os.chmod(victim, 0o644)


# --- (1) no private container loop left in the scrub -----------------------------------------------------------------------

def test_no_private_read_entries_write_cfb_loop_is_left_in_the_scrub(job):
    text = inspect.getsource(job.scrub_identity)
    assert "rewrite_entries" in text and not re.search(r"\b(read_entries|write_cfb|cfb_writer|idtmp)\b", text)
