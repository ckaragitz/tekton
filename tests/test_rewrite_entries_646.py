"""``rvt.roundtrip.rewrite_entries`` after #646: bytes-like edits (``bytes`` / ``bytearray`` / ``memoryview``,
outright or returned by a callable) all land as the same bytes and anything else is a ``TypeError`` before a
byte is written; ``src == dst`` goes through a sibling temp file + ``os.replace`` so a write that dies half way
leaves the source intact and no temp behind; ``dst``'s directory is required, never created; and the engine
sites folded onto the pass in #646 keep their contracts (``adocument.write_with_latest``'s missing-stream
error, ``convert.modify_family._patch_partatom``'s in-place PartAtom rewrite, ``manipulate.commit_plans`` in
place == apart).  Pinned genesis bases only (fresh-clone safe); the byte identity of the folds themselves (old
hand-rolled loops vs the API, 32 outputs over three pins) is the sha256 table in the #646 record."""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest

import conftest as C
from rvt import roundtrip as RT
from rvt.cfb_writer import CfbEntry
from rvt.roundtrip import read_entries, rewrite_entries

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture(scope="module")
def pin() -> str:
    if not C.CERTIFIED_YEARS:
        pytest.skip("no certified pinned base")
    return C.pinned_base(C.FOREIGN_FIRST[0])


def _streams(path) -> dict:
    return {e.path: e.data for e in read_entries(os.fspath(path)) if e.entry_type == "stream"}


# --- (2) bytes-like edits ---------------------------------------------------------------------------------------

def test_every_bytes_like_edit_lands_as_the_same_bytes(pin, tmp_path):
    payload = b"ours \x00\xff now" * 3
    ref = Path(rewrite_entries(pin, tmp_path / "bytes.rvt", {"Global/History": payload})).read_bytes()
    for i, edit in enumerate((bytearray(payload), memoryview(payload),
                              lambda raw: bytearray(payload), lambda raw: memoryview(payload))):
        out = rewrite_entries(pin, tmp_path / f"like{i}.rvt", {"Global/History": edit})
        assert Path(out).read_bytes() == ref
    assert _streams(tmp_path / "bytes.rvt")["Global/History"] == payload
    assert type(read_entries(str(tmp_path / "like1.rvt"))[1].data) is bytes            # stored as plain bytes


@pytest.mark.parametrize("edit", ["text, not bytes", 5, lambda raw: raw.decode("latin-1"), lambda raw: None])
def test_an_edit_that_is_not_bytes_like_is_a_typeerror_before_anything_is_written(pin, tmp_path, edit):
    with pytest.raises(TypeError, match=r"stream 'Global/History'.*bytes-like"):
        rewrite_entries(pin, tmp_path / "never.rvt", {"Global/History": edit})
    assert not (tmp_path / "never.rvt").exists()


# --- (2) in place: sibling temp + os.replace ------------------------------------------------------------------------

class _DiskFull:
    """A ``write_cfb`` that writes half of what the real one would, then dies -- the torn write the in-place
    path must survive."""

    def __init__(self, monkeypatch):
        self.paths = []
        real = RT.write_cfb

        def dying(path, entries, *a, **kw):
            self.paths.append(path)
            scratch = path + ".whole"
            real(scratch, entries, *a, **kw)
            whole = Path(scratch).read_bytes()
            os.remove(scratch)
            with open(path, "wb") as fh:
                fh.write(whole[: len(whole) // 2])
            raise OSError(28, "No space left on device (injected)")
        monkeypatch.setattr(RT, "write_cfb", dying)


def test_a_write_that_dies_half_way_leaves_the_in_place_source_intact_and_no_temp_behind(pin, tmp_path, monkeypatch):
    victim = Path(shutil.copyfile(pin, tmp_path / "victim.rvt"))
    before = victim.read_bytes()
    full = _DiskFull(monkeypatch)
    with pytest.raises(OSError, match="injected"):
        rewrite_entries(victim, victim, {C.partition_of(pin): C.zero_partition_header})
    assert victim.read_bytes() == before                                          # not torn, not half-edited
    assert sorted(os.listdir(tmp_path)) == ["victim.rvt"]                          # the temp left with the error
    assert len(full.paths) == 1 and full.paths[0] != str(victim)                   # the bytes never aimed at src
    assert os.path.dirname(full.paths[0]) == str(tmp_path)                         # sibling => same filesystem


def test_a_distinct_dst_is_written_directly_as_before(pin, tmp_path, monkeypatch):
    full = _DiskFull(monkeypatch)
    with pytest.raises(OSError, match="injected"):
        rewrite_entries(pin, tmp_path / "apart.rvt", {})
    assert full.paths == [str(tmp_path / "apart.rvt")]                             # no temp for the ordinary case


def test_in_place_keeps_the_files_mode_equals_apart_and_cleans_up(pin, tmp_path):
    name = C.partition_of(pin)
    inplace = Path(shutil.copyfile(pin, tmp_path / "inplace.rvt"))
    os.chmod(inplace, 0o644)
    assert rewrite_entries(inplace, inplace, {name: C.zero_partition_header}) == str(inplace)
    apart = rewrite_entries(pin, tmp_path / "apart.rvt", {name: C.zero_partition_header})
    assert inplace.read_bytes() == Path(apart).read_bytes()
    assert stat.S_IMODE(os.stat(inplace).st_mode) == 0o644                        # not mkstemp's 0600
    assert sorted(os.listdir(tmp_path)) == ["apart.rvt", "inplace.rvt"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks on this platform")
def test_a_dst_that_links_to_src_rewrites_the_file_not_the_link(pin, tmp_path):
    real = Path(shutil.copyfile(pin, tmp_path / "real.rvt"))
    link = tmp_path / "link.rvt"
    try:
        os.symlink(real, link)
    except OSError:                                                                # pragma: no cover
        pytest.skip("cannot create a symlink here")
    name = C.partition_of(pin)
    rewrite_entries(real, link, {name: C.zero_partition_header})                   # same file, two spellings
    assert link.is_symlink() and os.readlink(link) == str(real)
    apart = rewrite_entries(pin, tmp_path / "apart.rvt", {name: C.zero_partition_header})
    assert real.read_bytes() == Path(apart).read_bytes()


def test_dsts_directory_is_required_never_created(pin, tmp_path):
    with pytest.raises(FileNotFoundError):
        rewrite_entries(pin, tmp_path / "no" / "such" / "dir" / "x.rvt", {})
    assert not (tmp_path / "no").exists()


# --- (1) the folded engine sites keep their contracts ----------------------------------------------------------------

def test_write_with_latest_replaces_only_global_latest_and_refuses_a_file_without_one(pin, tmp_path):
    from rvt.adocument import STREAM, decode_latest, encode_latest, write_with_latest
    from rvt.container import open_rvt
    from rvt.frontdoor.release_ctx import host_release_context
    out = str(tmp_path / "latest.rvt")
    with host_release_context(pin):                                                # a foreign pin's ADocument, by name
        with open_rvt(pin) as f:
            lat = decode_latest(f.inflate(STREAM))
        rep = write_with_latest(pin, out, encode_latest(lat.value, trailer=lat.trailer))
        with open_rvt(out) as f:
            assert decode_latest(f.inflate(STREAM)).clean
    assert rep["out"] == out and rep["framed"] == len(_streams(out)[STREAM])
    before, after = _streams(pin), _streams(out)
    assert list(after) == list(before) and all(after[p] == before[p] for p in before if p != STREAM)
    headless = rewrite_entries(pin, tmp_path / "headless.rvt", {STREAM: None})
    with pytest.raises(KeyError, match="no stream 'Global/Latest'"):
        write_with_latest(headless, str(tmp_path / "never.rvt"), b"\x00\x00")
    assert not (tmp_path / "never.rvt").exists()


def test_patch_partatom_renames_in_place_and_touches_nothing_else(pin, tmp_path):
    from rvt.convert.modify_family import _patch_partatom
    xml = '<?xml version="1.0"?><entry><title>PANEL A</title><family><title>PANEL A</title></family></entry>'
    fam = rewrite_entries(pin, tmp_path / "withatom.rfa", {}, extra=[CfbEntry("PartAtom", "stream", data=xml.encode())])
    before = _streams(fam)
    assert _patch_partatom(fam, [("NOT THERE", "X")])["changed"] is False
    assert _streams(fam) == before                                                 # unchanged => not rewritten
    rep = _patch_partatom(fam, [("PANEL A", "PANEL B-646"), ("", "ignored")])
    assert rep["changed"] is True and rep["replaced"] == [{"old": "PANEL A", "new": "PANEL B-646", "occurrences": 2}]
    after = _streams(fam)
    assert after["PartAtom"] == xml.replace("PANEL A", "PANEL B-646").encode() and rep["bytes"] == len(after["PartAtom"])
    assert list(after) == list(before) and all(after[p] == before[p] for p in before if p != "PartAtom")
    assert sorted(os.listdir(tmp_path)) == ["withatom.rfa"]                        # in place, no temp behind


def test_commit_plans_in_place_equals_apart(pin, tmp_path):
    from rvt import manipulate as M
    from rvt.frontdoor.release_ctx import release_build_context
    from rvt.mutate import Document
    inplace = shutil.copyfile(pin, tmp_path / "inplace.rvt")
    apart = str(tmp_path / "apart.rvt")
    with release_build_context(pin):
        doc = Document.from_file(pin)
        lvl = doc.levels()[0]["id"]
        plan = M.set_level_elevation(doc, lvl, doc._level_elevation(lvl) + 1.25)
        M.commit_plans(pin, apart, [plan])
        M.commit_plans(str(inplace), str(inplace), [plan])
    assert Path(inplace).read_bytes() == Path(apart).read_bytes() != Path(pin).read_bytes()
    assert sorted(os.listdir(tmp_path)) == ["apart.rvt", "inplace.rvt"]
