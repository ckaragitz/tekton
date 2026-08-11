"""``rvt.roundtrip.rewrite_entries`` -- the engine's ONE "re-emit this container with these streams' raw bytes
replaced / dropped and these entries appended, everything else byte-identical" pass (#640) -- and the four
``rvt.writer`` variant builders folded onto it (``zero_full_trailers_only``, ``corrupt_trailer_bytes``,
``regzip_streams_variant``, ``build_variant``: their documented tools/make_acceptance.py / make_batch2.py uses,
adapted to a pinned base's stream geometry).  Runs on the pinned genesis bases alone (fresh-clone safe); the
byte-identity of the fold itself (old hand-rolled loops vs the API, 39 outputs over three pins) is the sha256
table in the #640 record -- a test cannot re-run loops that no longer exist -- and ``tests/conftest.rewrite_streams``,
now a plain call of the API, keeps its own rows in ``tests/test_conftest_scaffolding.py``."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

import conftest as C
from rvt.container import PAGE_STRIDE, PAGE_TRAILER, depage, open_rvt
from rvt.roundtrip import catalog, rewrite_entries, roundtrip
from rvt import writer as W

pytestmark = pytest.mark.usefixtures("no_release_leak")       # build_variant's partition lane enters a host context


def _directory(path) -> list:
    """Every entry's identity but its bytes: (path, type, clsid, state bits, ctime, mtime), in stream-id order."""
    return [(r["path"], r["type"], r["clsid"], r["state_bits"], r["ctime"], r["mtime"])
            for r in catalog(os.fspath(path), hash_streams=False)["entries"]]


def _paged_stream(path) -> str:
    """A single-member stream of ``path`` with at least one FULL page (so it has 353-byte trailers to touch)."""
    with open_rvt(path) as doc:
        return next(s.name for s in doc.streams()
                    if s.size >= PAGE_STRIDE and len(doc.members(s.name)) == 1)


# --- the API's contract (the wording tests/conftest.rewrite_streams promises its callers) ------------------------

def test_no_edits_is_the_plain_roundtrip_byte_for_byte(pin, tmp_path):
    out = rewrite_entries(pin, tmp_path / "same.rvt", {})
    assert out == str(tmp_path / "same.rvt")                                     # PathLike in, str back
    roundtrip(pin, str(tmp_path / "rt.rvt"))
    assert Path(out).read_bytes() == (tmp_path / "rt.rvt").read_bytes()


def test_an_edit_sees_the_raw_bytes_and_changes_only_its_stream(pin, tmp_path):
    before = C.streams(pin)
    name = C.partition_of(pin)
    seen = []
    out = rewrite_entries(pin, tmp_path / "hz.rvt",
                          {name: lambda raw: seen.append(raw) or C.zero_partition_header(raw)})
    assert seen == [before[name]]                                                # the edit is handed the stored bytes
    after = C.streams(out)
    assert list(after) == list(before)                                           # entry order preserved
    assert after[name] == C.zero_partition_header(before[name]) != before[name]
    assert all(after[p] == before[p] for p in before if p != name)
    assert _directory(out) == _directory(pin)                                    # CLSIDs, state bits, FILETIMEs kept


def test_bytes_replace_none_drops_and_extra_lands_after_the_containers_own_entries(pin, tmp_path):
    before = C.streams(pin)
    twin = C.twin_partition_entry(pin)
    out = rewrite_entries(pin, tmp_path / "multi.rvt",
                          {"Formats/Latest": None, "Global/History": b"ours now"}, extra=[twin])
    after = C.streams(out)
    assert list(after) == [p for p in before if p != "Formats/Latest"] + [twin.path]
    assert after["Global/History"] == b"ours now" and after[twin.path] == twin.data
    assert all(after[p] == before[p] for p in after if p not in ("Global/History", twin.path))


def test_a_name_that_is_no_stream_is_a_keyerror_before_anything_is_written(pin, tmp_path):
    for replace in ({"No/Such/Stream": lambda raw: raw},
                    {C.partition_of(pin): None, "No/Such/Stream": None},        # one good name does not excuse a bad one
                    {"Global": lambda raw: raw}):                                # a STORAGE is not a stream
        with pytest.raises(KeyError, match="no stream"):
            rewrite_entries(pin, tmp_path / "never.rvt", replace)
        assert not (tmp_path / "never.rvt").exists()


def test_src_equal_dst_rewrites_in_place(pin, tmp_path):
    name = C.partition_of(pin)
    inplace = shutil.copyfile(pin, tmp_path / "inplace.rvt")
    rewrite_entries(inplace, inplace, {name: C.zero_partition_header})
    apart = rewrite_entries(pin, tmp_path / "apart.rvt", {name: C.zero_partition_header})
    assert Path(inplace).read_bytes() == Path(apart).read_bytes()


# --- rvt.writer's variant builders, now callers of the API ------------------------------------------------------

def test_zero_full_trailers_only_keeps_every_logical_byte(pin, tmp_path):
    name = _paged_stream(pin)
    before = C.streams(pin)
    rep = W.zero_full_trailers_only(pin, str(tmp_path / "v8.rvt"), [name])
    assert rep == {"streams": [name], "mode": "orig_bytes_zero_trailers"}
    after = C.streams(tmp_path / "v8.rvt")
    assert len(after[name]) == len(before[name]) and after[name] != before[name]
    assert depage(after[name]) == depage(before[name])                           # payload: Revit's own bytes
    assert all(t == bytes(PAGE_TRAILER) for t in W.orig_full_trailers(after[name]))
    assert all(after[p] == before[p] for p in before if p != name)


def test_corrupt_trailer_bytes_flips_exactly_those_bytes(pin, tmp_path):
    name = _paged_stream(pin)
    before = C.streams(pin)
    rep = W.corrupt_trailer_bytes(pin, str(tmp_path / "v9.rvt"), name, page=0, count=3)
    at = PAGE_STRIDE - PAGE_TRAILER
    assert rep == {"stream": name, "page": 0, "flipped_bytes": 3, "at_raw_offset": at}
    after = C.streams(tmp_path / "v9.rvt")
    diff = [i for i, (x, y) in enumerate(zip(before[name], after[name])) if x != y]
    assert diff == [at, at + 1, at + 2] and all(after[name][i] == before[name][i] ^ 0xFF for i in diff)
    assert all(after[p] == before[p] for p in before if p != name)
    with pytest.raises(ValueError, match="no full-page trailer"):                # a sub-page stream has none
        W.corrupt_trailer_bytes(pin, str(tmp_path / "never.rvt"), "Global/PartitionTable")
    with pytest.raises(KeyError):
        W.corrupt_trailer_bytes(pin, str(tmp_path / "never.rvt"), "No/Such/Stream")
    assert not (tmp_path / "never.rvt").exists()


@pytest.mark.parametrize("keep_tail", [128, 0])
def test_regzip_streams_variant_keeps_the_payload(pin, tmp_path, keep_tail):
    name = "Global/History"                                                      # sub-page, single member: batch 2's V10/V11
    out = str(tmp_path / "v10.rvt")
    rep = W.regzip_streams_variant(pin, out, [name], keep_tail_bytes=keep_tail)
    before, after = C.streams(pin), C.streams(out)
    assert rep == {"streams": [{"name": name, "raw_size": len(before[name]), "full_page_trailers": 0,
                               "keep_tail_bytes": keep_tail}]}
    assert len(after[name]) == len(before[name]) and after[name] != before[name]  # our deflate, their geometry
    if keep_tail:
        assert after[name][-keep_tail:] == before[name][-keep_tail:]
    with open_rvt(pin) as a, open_rvt(out) as b:
        assert b.inflate(name, 0) == a.inflate(name, 0) and b.members(name)[0].crc_ok
    assert all(after[p] == before[p] for p in before if p != name)


def test_build_variant_regzips_streams_and_partitions_onto_the_api(pin, tmp_path):
    from rvt.frontdoor.release_ctx import host_release_context
    from rvt.partitions import StreamWalker
    name, out = _paged_stream(pin), str(tmp_path / "v7.rvt")
    with pytest.raises(KeyError, match="streams not in file"):
        W.build_variant(pin, str(tmp_path / "never.rvt"), ["No/Such/Stream"], W.trailer_zero)
    assert not (tmp_path / "never.rvt").exists()
    with host_release_context(pin):                                              # a foreign pin's block tags, by name
        with open_rvt(pin) as doc:
            parts = doc.partition_streams()
        rep = W.build_variant(pin, out, [name], W.trailer_zero, partition_streams=parts)
        assert [s["name"] for s in rep["streams"]] == [name] + parts
        before, after = C.streams(pin), C.streams(out)
        assert list(after) == list(before) and all(after[p] == before[p] for p in before if p not in [name] + parts)
        with open_rvt(pin) as a, open_rvt(out) as b:
            assert b.inflate(name, 0) == a.inflate(name, 0) and len(b.raw(name)) == len(a.raw(name))
            for p in parts:
                wa = StreamWalker(a.logical(p), inflate=True, keep_data=True)
                wb = StreamWalker(b.logical(p), inflate=True, keep_data=True)
                assert not wb.errors and [x.data for x in wb.blocks] == [x.data for x in wa.blocks]
    assert W.verify_readback(out)["crc_failures"] == 0
