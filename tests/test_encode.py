"""Byte-exact decode -> encode round trip (src/rvt/encode.py).

Proves the schema-directed encoder is the exact inverse of the decoder on
REAL partition records: every cleanly-decodable record is decoded, then
re-serialized (header + sizes + class id + object bytes + size trailer) and
the produced bytes must be IDENTICAL to the original record bytes.

Coverage (all full-corpus, no sampling):
    racbasicsampleproject   seq 101, 102, 103   (85,978 records each)
    rmebasicsampleproject   seq 102             (142,480 records; the 1,171
                            Extensible-Storage FamilyInstance records that do
                            not decode are excluded from the tested set --
                            they are outside "the same set that decodes")
    rstbasicsampleproject   Partitions/21 WHOLE-SEGMENT reconstruction for
                            seq 101, 102, 103 (decode all -> re-encode all
                            -> concatenated bytes == concat_segment(seq))

Runtime ~2 min for the whole file.  RVT_SKIP_LARGE=1 skips the corpus
tests (unit tests still run).
"""
from __future__ import annotations

import os
import struct

import pytest

from rvt import objects
from rvt.objects import ObjectDecoder, Reader, iter_records, load_segment
from rvt.encode import (ObjectEncoder, Writer, guid_to_bytes,
                        roundtrip_segment, reencode_segment)

ROOT = objects.ROOT
SCHEMA_JSON = os.path.join(ROOT, "extracted", "_schema", "schema.json")


def _have(project: str) -> bool:
    return (os.path.exists(SCHEMA_JSON)
            and os.path.isdir(os.path.join(ROOT, "extracted", project)))


pytestmark = pytest.mark.skipif(not _have("racbasicsampleproject"),
                                reason="extracted corpus / schema not present")

skip_large = pytest.mark.skipif(
    os.environ.get("RVT_SKIP_LARGE") == "1", reason="RVT_SKIP_LARGE=1")

TARGET = 0.99   # brief: >= 99 % byte-exact of the cleanly-decodable set


# ---------------------------------------------------------------------------
# unit tests -- Writer is the mirror of Reader
# ---------------------------------------------------------------------------

def test_writer_reader_symmetry():
    w = Writer()
    w.i32(-7)
    w.i64(1234567890123)
    w.f64(9.84252)
    w.f32(0.5)
    w.astring("abc")
    w.astring(None)          # null AString sentinel
    w.astring("")            # empty AString
    w.guid("03020100-0504-0706-0809-0a0b0c0d0e0f")
    w.xyz([1.0, 2.0, 3.0])
    w.uv([-0.0, 4.5])
    w.element_id(-1)
    w.u16(0x8CC)
    w.bool(True)
    w.bool(False)
    b = w.bytes()
    r = Reader(b)
    assert r.i32() == -7
    assert r.i64() == 1234567890123
    assert r.f64() == 9.84252
    assert r.f32() == 0.5
    assert r.astring() == "abc"
    assert r.astring() is None
    assert r.astring() == ""
    assert r.guid() == "03020100-0504-0706-0809-0a0b0c0d0e0f"
    assert r.xyz() == [1.0, 2.0, 3.0]
    uv = r.uv()
    assert uv == [0.0, 4.5] and str(uv[0]) == "-0.0"     # -0.0 sign preserved
    assert r.element_id() == -1
    assert r.u16() == 0x8CC
    assert r.bool() is True and r.bool() is False
    assert r.remaining() == 0


def test_guid_bytes_roundtrip():
    raw = bytes(range(16))
    assert guid_to_bytes(Reader(raw).guid()) == raw


def test_astring_surrogate_and_null_edges():
    # a lone surrogate must survive decode -> encode byte-exact
    raw = struct.pack("<I", 3) + "a".encode("utf-16-le") + b"\x00\xd8" + b"b\x00"
    s = Reader(raw).astring()
    w = Writer()
    w.astring(s)
    assert w.bytes() == raw


@pytest.fixture(scope="module")
def enc():
    return ObjectEncoder()


def test_shadowed_field_names_are_disambiguated(enc):
    """PropertySetLibrary re-declares Element.m_locked: distinct keys."""
    dec = enc.dec
    cid = dec.schema.by_name["PropertySetLibrary"].type_id
    keys = set()
    seen = {}
    for cd in dec.chain(cid):
        for f in cd.fields:
            k = objects.field_key(cd, f, seen)
            assert k not in keys
            keys.add(k)
            seen[k] = True
    assert "m_locked" in keys and "PropertySetLibrary::m_locked" in keys


# ---------------------------------------------------------------------------
# corpus round trips
# ---------------------------------------------------------------------------

def _report(name, st):
    rate = st["pass"] / max(st["tested"], 1)
    print(f"\n{name}: records={st['records']} tested={st['tested']} "
          f"pass={st['pass']} ({100 * rate:.4f}%) fail={st['fail']} "
          f"skipped_unclean={st['skipped_unclean']}")
    for fl in st["failures"][:5]:
        print(f"   FAIL {fl}")
    return rate


@skip_large
@pytest.mark.parametrize("seq", [102, 101, 103])
def test_racbasic_record_roundtrip(enc, seq):
    seg = load_segment("racbasicsampleproject", seq, os.environ.get("RVT_SEG_CACHE"))
    st = roundtrip_segment(seg, seq, enc)
    rate = _report(f"racbasic seq{seq}", st)
    assert st["tested"] > 50_000
    assert rate >= TARGET, st["failures"][:3]
    assert st["fail"] == 0, st["failures"][:3]      # observed: 100 %


@skip_large
@pytest.mark.skipif(not _have("rmebasicsampleproject"), reason="rmebasic absent")
def test_rmebasic_seq102_record_roundtrip(enc):
    seg = load_segment("rmebasicsampleproject", 102, os.environ.get("RVT_SEG_CACHE"))
    st = roundtrip_segment(seg, 102, enc)
    rate = _report("rmebasic seq102", st)
    assert st["tested"] > 100_000
    # the only unclean records are the Extensible-Storage FamilyInstances
    assert st["skipped_unclean"] < 0.01 * st["records"]
    assert rate >= TARGET, st["failures"][:3]
    assert st["fail"] == 0, st["failures"][:3]      # observed: 100 %


@skip_large
@pytest.mark.skipif(not _have("rstbasicsampleproject"), reason="rstbasic absent")
@pytest.mark.parametrize("seq", [101, 102, 103])
def test_rstbasic_partition21_whole_segment_roundtrip(enc, seq):
    """Decode ALL records of Partitions/21, re-encode ALL, concatenate ==
    partitions.concat_segment(seq) exactly (non-decodable records and
    save-unit sentinels pass through verbatim)."""
    from rvt.partitions import load_stream
    path = os.path.join(ROOT, "extracted", "rstbasicsampleproject", "Partitions__21.bin")
    seg = load_stream(path).concat_segment(seq)
    assert len(seg) > 1_000_000
    rebuilt, st = reencode_segment(seg, seq, enc)
    print(f"\nrstbasic P21 seq{seq}: {len(seg):,} bytes, {st}")
    assert st["reencoded"] > 30_000
    if rebuilt != seg:
        i = next(i for i in range(min(len(seg), len(rebuilt)))
                 if seg[i] != rebuilt[i])
        pytest.fail(f"segment differs at {i}: {seg[i - 8:i + 8].hex(' ')} "
                    f"vs {rebuilt[i - 8:i + 8].hex(' ')}")
    assert rebuilt == seg
