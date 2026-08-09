"""tests/test_records32.py -- sample-free coverage of the 32-bit record layer.

``rvt.versions.records32`` is the reversible patch set that puts the whole
read/write stack into the Revit <= 2023 era (i32 element ids: 8/12-byte
record headers, 28-byte ElemTable rows with a 19-byte footer, ~40 module
attributes swapped and LIFO-restored).  Until now it was exercised only by
sample-backed tests that skip on a fresh clone, so a refactor of objects /
encode / elemtable / manipulate could break certified-2023 reading with CI
green (#175).  Every fixture below is SYNTHETIC -- packed in this file with
``struct`` from the wire law in docs/writer/format-2023.md; no Autodesk
bytes (CLAUDE.md rule 3).  The one real file touched is our own composed,
certified 2024 base shipped in the plugin, to prove ``reading32`` degrades
to plain framing activation on a 64-bit-id release.

Covers the issue's DONE: (1) framing + sentinel handling of iter_records32
and its siblings; (2) ElemTable32 byte-exact round trip incl. the
INVALID_ID owner normalisation, plus a strict-xfail pinning the documented
row-order disagreement (#174); (3) is_ids32 on stub schemas; (4) ids32()
swaps and restores every patch point, incl. from-import rebinds, on
exception, and nested; (5) reading32 on G_ABPD_2024 yields the 2024
ordinals, never activates ids32, and leaves rvt.partitions as it found it.
"""
import os
import struct
import sys
import zlib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import rvt.versions as V                                             # noqa: E402
from rvt.versions import KNOWN_RELEASES, records32 as R32           # noqa: E402
from rvt import elemtable as ET                                     # noqa: E402
from rvt import encode as E                                         # noqa: E402
from rvt import families as FA                                      # noqa: E402
from rvt import mutate as MU                                        # noqa: E402
from rvt import objects as O                                        # noqa: E402
from rvt import partitions as P                                     # noqa: E402
from rvt import stream_encoders as SE                               # noqa: E402
from rvt.schema import ClassDef, Field, Schema                      # noqa: E402

G24 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2024.rvt")
needs_g24 = pytest.mark.skipif(not os.path.exists(G24),
                               reason="plugin genesis base G_ABPD_2024.rvt absent")


# ---------------------------------------------------------------------------
# synthetic wire builders (docs/writer/format-2023.md section 1)
# ---------------------------------------------------------------------------
def rec32(seq: int, eid: int, cls: int, body: bytes, stamp=None) -> bytes:
    """One 32-bit-era record: i32 id [+ u32 stamp] + u32 psize + u16 class
    + body + u32 psize repeat.  stamp defaults to adler32(class+body)."""
    payload = struct.pack("<H", cls) + body
    ps = len(payload)
    if seq == 101:
        hdr = struct.pack("<iI", eid, ps)
    else:
        if stamp is None:
            stamp = zlib.adler32(payload) & 0xFFFFFFFF
        hdr = struct.pack("<iII", eid, stamp, ps)
    return hdr + payload + struct.pack("<I", ps)


def sentinel32(seq: int) -> bytes:
    """Save-unit sentinel: id -1, psize 0, repeat 0 (stamp 1 on 102/103)."""
    hdr = struct.pack("<iI", -1, 0) if seq == 101 else struct.pack("<iII", -1, 1, 0)
    return hdr + struct.pack("<I", 0)


ET_CLASS_TAG, ET_LAST_ID, ET_MARKER, ET_TAIL_CLASS = 0x055A, 1_472_302, 0xFFFFFFFF, 0x096A


def et32_payload(rows, *, pad=0) -> bytes:
    """A 2023 Global/ElemTable payload.  rows are raw wire 7-tuples in the
    order records32 documents: (original_id, id, ce, me, ue, partition, owner)."""
    out = bytearray(struct.pack("<HI", ET_CLASS_TAG, len(rows)))
    for r in rows:
        out += struct.pack("<7I", *r)
    out += struct.pack("<IIH", 0, ET_MARKER, ET_TAIL_CLASS) + bytes([pad])
    out += struct.pack("<II", ET_LAST_ID, 0)
    return bytes(out)


ROWS = [  # (original_id, id, ce, me, ue, partition, owner) -- id == original_id
    (4096, 4096, 1, 1, 0xFFFFFFFF, 1, 0xFFFFFFFF),
    (4097, 4097, 1, 7, 7, 1, 4096),
    (5120, 5120, 3, 9, 0xFFFFFFFF, 6, 0xFFFFFFFF),
]


def stub_schema(year: int, *identifier_fields) -> Schema:
    """A real (tiny) Schema: the six framing classes carrying `year`'s
    ordinals, plus ``Identifier`` with the given (name, kind) fields --
    everything is_ids32 / ordinals_from_schema / reading consult."""
    s = Schema()
    for const, cls in V.FRAMING_CLASSES.items():
        s.by_name[cls] = ClassDef(KNOWN_RELEASES[year].framing[const], cls, 1, 0)
    if identifier_fields:
        s.by_name["Identifier"] = ClassDef(
            0x14, "Identifier", 1, 0,
            fields=[Field(n, k, 0, 0) for n, k in identifier_fields])
    return s


# ---------------------------------------------------------------------------
# 0. the wire constants are the documented 2023 law
# ---------------------------------------------------------------------------
def test_wire_constants():
    assert R32.RAW_HDR_101 == struct.calcsize("<iI") == R32.raw_hdr_len32(101)
    assert R32.RAW_HDR_10X == struct.calcsize("<iII") == R32.raw_hdr_len32(102) == R32.raw_hdr_len32(103)
    assert R32.REC_SIZE32 == struct.calcsize("<7I")
    assert R32.FOOTER_LEN32 == struct.calcsize("<IIH") + 1 + struct.calcsize("<II")
    assert R32.INVALID_OWNER32 == 0xFFFFFFFF


# ---------------------------------------------------------------------------
# 1. record framing + sentinel handling on synthetic segments
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seq", [101, 102, 103])
def test_iter_records32_walks_records_then_sentinel(seq):
    a = rec32(seq, 4096, 0x0576, b"\x01\x02\x03")
    b = rec32(seq, 4097, 0x0819, b"")
    seg = a + b + sentinel32(seq)
    recs = list(R32.iter_records32(seg, seq))
    assert [r.elem_id for r in recs] == [4096, 4097, -1]
    r0, r1, s = recs
    assert (r0.class_id, r0.payload, r0.body_size, r0.seg_offset) == (0x0576, b"\x01\x02\x03", 5, 0)
    assert (r1.class_id, r1.payload, r1.body_size, r1.seg_offset) == (0x0819, b"", 2, len(a))
    assert all(r.trailer_ok for r in recs)
    assert (s.body_size, s.class_id, s.payload, s.seg_offset) == (0, 0, b"", len(a) + len(b))
    if seq == 101:
        assert r0.stamp == r1.stamp == s.stamp == 0
    else:
        assert r0.stamp == zlib.adler32(struct.pack("<H", 0x0576) + b"\x01\x02\x03") & 0xFFFFFFFF
        assert s.stamp == 1
    # the walk consumed the segment exactly
    assert s.seg_offset + R32.raw_hdr_len32(seq) + 4 == len(seg)


def test_iter_records32_flags_bad_trailer_and_stops_on_garbage():
    good = rec32(102, 4096, 0x25, b"\xAA")
    bad = bytearray(rec32(102, 4097, 0x25, b"\xBB"))
    struct.pack_into("<I", bad, len(bad) - 4, 999)           # psize repeat lies
    recs = list(R32.iter_records32(good + bytes(bad), 102))
    assert [(r.elem_id, r.trailer_ok) for r in recs] == [(4096, True), (4097, False)]
    # id < -1 is not a record: the walker stops instead of yielding junk
    junk = struct.pack("<iII", -7, 0, 3) + b"\x00" * 3 + struct.pack("<I", 3)
    assert [r.elem_id for r in R32.iter_records32(good + junk, 102)] == [4096]
    # a size that overruns the segment stops the walk (truncated tail)
    trunc = rec32(103, 4098, 0x25, b"\xCC" * 8)[:-6]
    assert [r.elem_id for r in R32.iter_records32(good + trunc, 103)] == [4096]
    # a header shorter than hlen + 4 yields nothing
    assert list(R32.iter_records32(b"\xff" * 15, 102)) == []
    assert list(R32.iter_records32(b"", 101)) == []


def test_iter_records32_is_not_the_64bit_walker():
    """The same synthetic bytes read as 64-bit framing must NOT produce the
    32-bit ids -- proves the fixture actually discriminates the two eras."""
    seg = rec32(102, 4096, 0x25, b"\x00" * 6) + sentinel32(102)
    assert [r.elem_id for r in O.iter_records(seg, 102)] != [4096, -1]
    assert [r.elem_id for r in R32.iter_records32(seg, 102)] == [4096, -1]


@pytest.mark.parametrize("seq", [101, 102])
def test_validator_walker32_agrees_with_iter_records32(seq):
    seg = rec32(seq, 4096, 0x0576, b"\x01\x02") + rec32(seq, 4097, 0x25, b"") + sentinel32(seq)
    a = list(R32.iter_records32(seg, seq))
    b = list(R32._iter_seg_records32(seg, seq, unit=0))

    def proj(r):
        return (r.elem_id, r.stamp, r.body_size, r.class_id, r.trailer_ok)
    assert [proj(r) for r in a] == [proj(r) for r in b]
    assert all(r.seq == seq and r.unit == 0 for r in b)
    hlen = R32.raw_hdr_len32(seq)
    assert [r.payload_off for r in b] == [r.seg_offset + hlen for r in a]
    # _iter_seg_records32 requires the trailer to be present (stricter stop)
    assert list(R32._iter_seg_records32(seg[:-4], seq, 0))[-1].elem_id == 4097


@pytest.mark.parametrize("seq", [101, 102, 103])
def test_parse_record_header32_and_spans(seq):
    hlen = R32.raw_hdr_len32(seq)
    body = b"\x10\x20\x30"
    seg = rec32(seq, 4096, 0x0949, body, stamp=0xDEADBEEF) + sentinel32(seq)
    h = R32.parse_record_header32(seg, 0, seq)
    assert (h.offset, h.elem_id, h.body_size, h.cls, h.hdr_len) == (0, 4096, 5, 0x0949, hlen + 4)
    assert h.stamp == (None if seq == 101 else 0xDEADBEEF)
    recs = list(R32.iter_records32(seg, seq))
    assert R32.record_bytes32(seg, recs[0], seq) == seg[:hlen + 5 + 4]
    assert R32.record_bytes32(seg, recs[1], seq) == sentinel32(seq)
    spans = R32._record_spans32(seg, seq)
    assert [(off, ln) for _r, off, ln in spans] == [(0, hlen + 9), (hlen + 9, hlen + 4)]
    assert sum(ln for _r, _off, ln in spans) == len(seg)


@pytest.mark.parametrize("seq", [101, 102, 103])
def test_assert_sentinel_tail32(seq):
    blk = rec32(seq, 4096, 0x25, b"\x00") + sentinel32(seq)
    assert R32._assert_sentinel_tail32(blk, seq) == len(blk) - len(sentinel32(seq))
    with pytest.raises(ValueError, match="does not end with a sentinel"):
        R32._assert_sentinel_tail32(rec32(seq, 4096, 0x25, b"\x00"), seq)
    with pytest.raises(ValueError, match="too small"):
        R32._assert_sentinel_tail32(b"\x00" * 3, seq)


def test_le_id_patterns32_and_scan_stream_ids32():
    assert R32._le_id_patterns32([4096, -1]) == [struct.pack("<i", 4096), b"\xff\xff\xff\xff"]
    valid = {4096, 5000, 70000}
    payload = b"\x00" + struct.pack("<i", 5000) + b"\x07" + struct.pack("<i", 70000) + struct.pack("<i", 123)
    assert R32.scan_stream_ids32(payload, valid) == {5000, 70000}
    assert R32.scan_stream_ids32(payload, set()) == set()
    # ids below 4096 are never reported (system-id floor), even if "valid"
    assert R32.scan_stream_ids32(struct.pack("<i", 12), {12, 4096}) == set()


# ---------------------------------------------------------------------------
# 1b. record emit under ids32(): the patched encoders frame 32-bit records
#     that the 32-bit walker reads back (write/read closure, stub class 0)
# ---------------------------------------------------------------------------
def test_emit32_roundtrips_through_iter_records32():
    with R32.ids32():
        w = E.Writer()
        w.element_id(-1)
        w.element_id(4096)
        assert bytes(w.buf) == struct.pack("<ii", -1, 4096)
        rd = O.Reader(bytes(w.buf))
        assert (rd.element_id(), rd.element_id(), rd.remaining()) == (-1, 4096, 0)
        enc = E.ObjectEncoder()
        for seq in (101, 102, 103):
            assert enc.encode_record(seq, -1, 1, 0, None, psize=0) == sentinel32(seq)
            assert E.encode_record(seq, -1, None, 0, None) == sentinel32(seq)
    # outside the context the same calls are 64-bit again
    w = E.Writer()
    w.element_id(4096)
    assert bytes(w.buf) == struct.pack("<q", 4096)
    assert E.ObjectEncoder().encode_record(102, -1, 1, 0, None, psize=0) != sentinel32(102)


# ---------------------------------------------------------------------------
# 2. Global/ElemTable: 2023 wire <-> normalized model, byte-exact
# ---------------------------------------------------------------------------
def test_elemtable32_round_trip_is_byte_exact_and_normalizes_owner():
    payload = et32_payload(ROWS, pad=1)
    assert len(payload) == 6 + R32.REC_SIZE32 * len(ROWS) + R32.FOOTER_LEN32
    tbl = R32.parse_elemtable32(payload, "synthetic")
    assert (tbl.class_tag, tbl.count, tbl.payload_len) == (ET_CLASS_TAG, 3, len(payload))
    assert tbl.ids() == [4096, 4097, 5120]
    r0, r1, r2 = tbl.records
    assert (r0.index, r0.original_id, r0.creation_ep, r0.modified_ep,
            r0.user_modified_ep, r0.partition_id) == (0, 4096, 1, 1, 0xFFFFFFFF, 1)
    # owner 0xFFFFFFFF on the wire is the 64-bit INVALID_ID in the model ...
    assert r0.owner_id == ET.INVALID_ID and r2.owner_id == ET.INVALID_ID
    assert r1.owner_id == 4096                       # ... a real owner is kept
    assert not any(r.renumbered for r in tbl.records)
    f = tbl.footer
    assert (f.graveyard_count, f.marker, f.tail_class, f.tail_pad, f.last_id, f.tail_zero) == \
           (0, ET_MARKER, ET_TAIL_CLASS, 1, ET_LAST_ID, 0)
    assert f.raw == payload[-R32.FOOTER_LEN32:]
    # the model dict has the 2024+ shape and never leaks the 32-bit sentinel
    model = R32.decode_elemtable32(payload)
    assert model["stream"] == "ElemTable" and model["class_tag"] == ET_CLASS_TAG
    assert model["records"][0] == (4096, 1, 1, 0xFFFFFFFF, 4096, ET.INVALID_ID, 1)
    assert R32.INVALID_OWNER32 not in {r[5] for r in model["records"]}
    assert model["footer"] == {"marker": ET_MARKER, "tail_class": ET_TAIL_CLASS,
                               "tail_pad": 1, "last_id": ET_LAST_ID, "tail_zero": 0}
    # ... and encodes back to the identical bytes
    assert R32.encode_elemtable32(model) == payload
    # empty table: header + footer only
    empty = et32_payload([])
    assert R32.encode_elemtable32(R32.decode_elemtable32(empty)) == empty


def test_elemtable32_is_not_the_64bit_codec():
    """A 2023 payload is refused by the 2024+ codec and vice versa, and the
    32-bit codec agrees with the 64-bit MODEL for the same logical rows."""
    p32 = et32_payload(ROWS)
    with pytest.raises(ValueError):
        SE.decode_elemtable(p32)
    m32 = R32.decode_elemtable32(p32)
    p64 = SE.encode_elemtable(m32)                   # same model, the other era's wire
    assert len(p64) == 6 + ET.REC_SIZE * len(ROWS) + SE.ELEMTABLE_FOOTER_LEN != len(p32)
    assert SE.decode_elemtable(p64)["records"] == m32["records"]
    with pytest.raises(ValueError):
        R32.decode_elemtable32(p64)


def test_elemtable32_refuses_malformed():
    with pytest.raises(ValueError, match="too short"):
        R32.parse_elemtable32(b"\x00" * 5)
    with pytest.raises(ValueError, match="needed"):
        R32.parse_elemtable32(struct.pack("<HI", ET_CLASS_TAG, 2) + b"\x00" * 30)
    payload = et32_payload(ROWS)
    # footer of the wrong length / non-empty graveyard -> decode refuses
    with pytest.raises(ValueError, match="footer"):
        R32.decode_elemtable32(payload + b"\x00")
    grave = bytearray(payload)
    struct.pack_into("<I", grave, 6 + R32.REC_SIZE32 * len(ROWS), 1)
    with pytest.raises(ValueError, match="graveyard 1"):
        R32.decode_elemtable32(bytes(grave))
    # a short footer still parses (lenient parse, strict decode)
    t = R32.parse_elemtable32(payload[:-3])
    assert t.footer.last_id == 0 and len(t.footer.raw) == R32.FOOTER_LEN32 - 3
    # encode refuses ids that cannot fit the 32-bit wire
    m = R32.decode_elemtable32(payload)
    m["records"][0] = (1 << 33,) + m["records"][0][1:]
    with pytest.raises(ValueError, match="32-bit range"):
        R32.encode_elemtable32(m)


def test_elemtable32_renumbered_row_round_trips_byte_exact():
    """Whatever the field order, a row whose first two u32 differ survives
    decode -> encode unchanged (the reduction/edit paths only need that)."""
    payload = et32_payload([(4096, 4099, 1, 2, 2, 1, 0xFFFFFFFF)])
    assert R32.encode_elemtable32(R32.decode_elemtable32(payload)) == payload
    (rec,) = R32.parse_elemtable32(payload).records
    assert {rec.id, rec.original_id} == {4096, 4099} and rec.renumbered


@pytest.mark.xfail(strict=True, reason=(
    "#174: records32 reads the ElemTable32 row as (original_id, id, ...) while the "
    "file's own schema (ElemRec: m_id, m_history, ...) and port2023's reference "
    "parser put m_id FIRST; indistinguishable while id == original_id, which holds "
    "on every corpus row -- flips to pass when #174 settles the order"))
def test_elemtable32_row_order_follows_schema_m_id_first():
    # schema order on the wire: m_id=4099, m_history.original=4096
    payload = et32_payload([(4099, 4096, 1, 2, 2, 1, 0xFFFFFFFF)])
    (rec,) = R32.parse_elemtable32(payload).records
    assert (rec.id, rec.original_id) == (4099, 4096)


# ---------------------------------------------------------------------------
# 3. is_ids32: the schema's own Identifier declaration decides
# ---------------------------------------------------------------------------
def test_is_ids32_on_stub_schemas():
    assert R32.is_ids32(stub_schema(2023, ("m_id", 0x04))) is True             # 2023: v1 i32
    assert R32.is_ids32(stub_schema(2024, ("m_id64", 0x0B))) is False          # 2024+: v2 i64
    assert R32.is_ids32(stub_schema(2023, ("m_id", 0x0B))) is False            # right name, wrong kind
    assert R32.is_ids32(stub_schema(2023, ("m_id64", 0x04))) is False          # right kind, wrong name
    assert R32.is_ids32(stub_schema(2023, ("m_id", 0x04), ("m_x", 0x0B))) is True   # first field rules
    assert R32.is_ids32(stub_schema(2023)) is False                             # no Identifier class
    no_fields = stub_schema(2023)
    no_fields.by_name["Identifier"] = ClassDef(0x14, "Identifier", 1, 0)
    assert R32.is_ids32(no_fields) is False                                     # class without fields


@needs_g24
def test_is_ids32_false_on_our_2024_base_schema():
    sch = V.schema_of(G24)
    f = sch.by_name["Identifier"].fields[0]
    assert (f.name, f.kind) == ("m_id64", 0x0B)
    assert R32.is_ids32(sch) is False


# ---------------------------------------------------------------------------
# 4. ids32(): every patch point swapped, LIFO-restored, on exception, nested
# ---------------------------------------------------------------------------
def _bound(holder, attr):
    """The value bound RIGHT NOW (class __dict__ first, exactly what
    activate_ids32 records, so method identity compares apples to apples)."""
    return holder.__dict__.get(attr, getattr(holder, attr))


def _bindings(table):
    return {(h, a): _bound(h, a) for h, a, _r in table}


def _assert_active(table):
    for holder, attr, repl in table:
        assert _bound(holder, attr) is repl, (holder, attr)


def _assert_inactive(table):
    for holder, attr, repl in table:
        assert _bound(holder, attr) is not repl, (holder, attr)


def _assert_restored(before, table):
    for key, val in _bindings(table).items():
        assert val is before[key], key


def test_patch_table_shape():
    table = R32._patch_table()
    named = {(h, a) for h, a, _ in table}
    assert len(named) == len(table), "a (module, attr) pair is patched twice"
    for holder, attr, _repl in table:
        assert hasattr(holder, attr), (holder, attr)     # nothing is ADDED, only swapped
    _assert_inactive(table)                              # inactive at rest
    import rvt.commit as C
    import rvt.manipulate as M
    import rvt.reduce as RD
    for pair in [(O, "iter_records"), (MU, "iter_records"), (RD, "iter_records"),
                 (O.Reader, "element_id"), (E.Writer, "element_id"),
                 (P, "parse_record_header"), (P, "RECORD_HDR_101"), (P, "RECORD_HDR_10X"),
                 (SE, "decode_elemtable"), (SE, "encode_elemtable"), (SE, "ELEMTABLE_FOOTER_LEN"),
                 (C, "decode_elemtable"), (M, "verify_manipulated"), (RD, "verify_reduced"),
                 (E.ObjectEncoder, "encode_record"), (M.EditSession, "frame")]:
        assert pair in named, pair


def test_ids32_swaps_every_patch_point_and_restores_lifo():
    table = R32._patch_table()
    before = _bindings(table)
    orig_iter = O.iter_records
    assert MU.iter_records is orig_iter and FA.iter_records is orig_iter   # from-imports
    with R32.ids32():
        _assert_active(table)
        # the from-import rebinds moved together with the defining module
        assert O.iter_records is MU.iter_records is FA.iter_records is R32.iter_records32
        assert SE.decode_elemtable is R32.decode_elemtable32
        assert (P.RECORD_HDR_101, P.RECORD_HDR_10X) == (R32.RAW_HDR_101 + 4, R32.RAW_HDR_10X + 4)
        assert (ET.REC_SIZE, ET.REC_FMT) == (R32.REC_SIZE32, "<7I")
        assert SE.ELEMTABLE_FOOTER_LEN == R32.FOOTER_LEN32
    _assert_restored(before, table)
    assert O.iter_records is MU.iter_records is FA.iter_records is orig_iter


def test_ids32_restores_on_exception():
    table = R32._patch_table()
    before = _bindings(table)
    with pytest.raises(RuntimeError, match="boom"):
        with R32.ids32():
            _assert_active(table)
            raise RuntimeError("boom")
    _assert_restored(before, table)


def test_ids32_nests_and_unwinds_in_order():
    table = R32._patch_table()
    before = _bindings(table)
    with R32.ids32():
        _assert_active(table)
        with R32.ids32():                        # re-entrant
            _assert_active(table)
            with pytest.raises(KeyError):
                with R32.ids32():
                    raise KeyError("inner")
            _assert_active(table)                # inner unwind restored to ACTIVE, not to rest
        _assert_active(table)
    _assert_restored(before, table)


def test_activate_restore_pair_is_the_context_manager_contract():
    table = R32._patch_table()
    before = _bindings(table)
    prev = R32.activate_ids32()
    try:
        assert len(prev) == len(table)
        _assert_active(table)
    finally:
        R32.restore_ids32(prev)
    _assert_restored(before, table)


def test_port2023_id32_is_the_same_context():
    """port2023.id32 / iter_records_2023 are thin delegations (one era, one
    patch set) -- pinned so the two names cannot drift apart again."""
    from rvt.genesis import port2023 as P23
    with P23.id32():
        assert O.iter_records is R32.iter_records32
    assert O.iter_records is not R32.iter_records32
    seg = rec32(102, 4096, 0x25, b"") + sentinel32(102)
    assert [r.elem_id for r in P23.iter_records_2023(seg, 102)] == [4096, -1]


# ---------------------------------------------------------------------------
# 5. reading32 on our composed 2024 base: 2024 ordinals, NO ids32, restored
# ---------------------------------------------------------------------------
# every rvt.partitions global reading()/activate() swaps, plus the three ids32 adds
_P_NAMES = tuple(V._PATCHED_NAMES) + ("RECORD_HDR_101", "RECORD_HDR_10X", "parse_record_header")


def _p_snapshot():
    return {n: getattr(P, n) for n in _P_NAMES}


def _assert_p_restored(before):
    for n, v in _p_snapshot().items():
        assert v is before[n], n


def _assert_framing_bound(ords):
    for const in V.FRAMING_CLASSES:
        assert getattr(P, const) == ords[const], const
    assert P.TERMINATOR == struct.pack("<HIIII", ords["BLOCK_TAG"], 0, 0, 0, 0)


@needs_g24
def test_reading32_on_2024_base_is_framing_only_and_restores():
    table = R32._patch_table()
    before_ids, before_p = _bindings(table), _p_snapshot()
    assert P.BLOCK_TAG == KNOWN_RELEASES[2026].framing["BLOCK_TAG"]      # 2026 at rest
    with R32.reading32(G24) as ords:
        assert ords == KNOWN_RELEASES[2024].framing
        _assert_framing_bound(ords)
        # ... but the id width layer is NOT active on a 64-bit-id release
        _assert_inactive(table)
        assert (P.RECORD_HDR_101, P.RECORD_HDR_10X) == \
               (before_p["RECORD_HDR_101"], before_p["RECORD_HDR_10X"])
    _assert_p_restored(before_p)
    _assert_restored(before_ids, table)


@needs_g24
def test_reading32_restores_partitions_on_exception():
    before_p = _p_snapshot()
    with pytest.raises(ZeroDivisionError):
        with R32.reading32(G24) as ords:
            _assert_framing_bound(ords)
            1 / 0
    _assert_p_restored(before_p)


@pytest.mark.parametrize("year,identifier,want32", [
    (2023, ("m_id", 0x04), True),
    (2024, ("m_id64", 0x0B), False),
])
def test_reading32_activates_ids32_iff_schema_declares_identifier_v1(
        monkeypatch, year, identifier, want32):
    """No file: schema_of (the seam reading32 resolves at call time) returns
    a stub schema; the real reading -> ordinals_from_schema -> activate chain
    binds that schema's ordinals, and ids32 is entered iff Identifier is v1."""
    table = R32._patch_table()
    before_ids, before_p = _bindings(table), _p_snapshot()
    monkeypatch.setattr(V, "schema_of", lambda _src: stub_schema(year, identifier))
    with R32.reading32("synthetic-source") as ords:
        assert ords == KNOWN_RELEASES[year].framing
        _assert_framing_bound(ords)
        if want32:
            _assert_active(table)
        else:
            _assert_inactive(table)
    _assert_p_restored(before_p)
    _assert_restored(before_ids, table)
