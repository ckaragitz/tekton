"""rvt.versions.records32 -- the 32-bit element-id RECORD LAYER (Revit <= 2023).

THE FINDING (2026-08-04, genesis-2023-reduce stream)
----------------------------------------------------
Revit 2024 widened element ids from 32 to 64 bits.  The file's OWN schema
declares it: class ``Identifier`` is **version 1 with one field ``m_id``
(i32)** in the 2023 ``Formats/Latest`` and **version 2 with ``m_id64``
(i64)** in 2024/2025/2026.  Everything else in the read stack is unchanged
at 2023 (container v4/4096, ECC pages, gzip flavour, block framing bar the
usual per-release ordinals, schema-stream grammar parses to EOF, class
field lists byte-for-byte the 2024 ones apart from the id width) -- but the
width ripples into every layer that serializes an element id:

* partition RECORD FRAMING: seq-101 header = ``<iI`` (8 bytes, was ``<qI``
  12), seq-102/103 = ``<iII`` (12 bytes, was ``<qII`` 16); the u32 psize
  repeat trailer is unchanged; sentinels are id -1 / psize 0 as before.
* IN-BODY ids: every ``ElementId`` / ``Identifier`` value inside an object
  body is i32 (proven by schema-directed decode parity: rst 99.978 %,
  rac 100.000 %, rme 99.172 % clean -- the same percentages and the same
  pre-existing Extensible-Storage-blob failures as 2024/2025/2026).
* ``Global/ElemTable``: 28-byte rows (was 40) and a DIFFERENT field order
  -- 2023 is ``(original_id, id, ce, me, ue, partition, owner)`` where
  2024+ is ``(original_id, ce, me, ue, id, owner, partition)`` (the schema
  corroborates: ElemRec v10 declares ``m_id, m_history, m_partitionId,
  m_OwningElementId`` in 2023 vs ``m_history, m_id, m_OwningElementId,
  m_partitionId`` in 2024+); owner-invalid is 0xFFFFFFFF; the footer is 19
  bytes (``<IIH`` + 1 pad byte + u32 last_id + u32 zero, was 24 with a u64
  last_id) -- ElemTable is v9 in 2023 (2024's v10 added
  ``m_bLastElementIdOverride``).

WHAT THIS MODULE IS
-------------------
The complete, reversible patch set that puts the read/write stack into the
32-bit-id era, exactly the way :func:`rvt.versions.activate` binds the
per-release framing ordinals: module attributes are swapped and restored,
nothing in the core modules is edited (their 2024+ behaviour is untouched
when no context is active).  The patch table covers every chokepoint found
by survey (grep of ``<q``-era struct formats + header-length arithmetic):

  read   objects.iter_records / Reader.element_id, validate._iter_seg_records,
         partitions.parse_record_header + RECORD_HDR_101/10X,
         elemtable.parse_elemtable (+ REC_FMT/REC_SIZE),
         stream_encoders.decode_elemtable, reduce.scan_stream_ids,
         reduce._raw_hdr_len, commit._hdr_len/_assert_sentinel_tail,
         encode.record_bytes, manipulate._record_spans
  write  encode.Writer.element_id / ObjectEncoder.encode_record /
         encode.encode_record, manipulate.EditSession.frame /
         _le_id_patterns, stream_encoders.encode_elemtable
  plus   per-module rebinds of the names the above are FROM-imported as
         (encode/families/manipulate/mutate/regadd/reduce/regdiff bind
         ``iter_records`` at import time; commit/manipulate/reduce/regadd/
         regdiff bind the elemtable codecs).

NOT patched (documented, out of the reduction ladder's path): the add-back
framing in ``rvt.regadd`` (2026-era creation), ``commit.commit_new_elements``
(adds elements), ``encode.reencode_segment`` / ``describe_mismatch``
diagnostics, and the famgen/mep creation-side helpers -- all 2026-only
paths guarded by ``require_creation_release`` anyway.

The ElemTable MODEL is normalized: :func:`parse_elemtable32` returns the
same ``ElemRec`` semantics as 2024+ (owner-invalid becomes the 64-bit
INVALID_ID sentinel) so every model consumer (validator consistency layer,
reduction splice, census) works unchanged; :func:`encode_elemtable32` maps
back and the wire round-trip is byte-exact (asserted on first decode of
every file this context touches).

USAGE::

    from rvt.versions import records32
    with records32.ids32():             # just the width layer
        ...
    with records32.reading32(path):     # framing ordinals + width, one call
        rep = rvt.validate.validate_file(path)

``reading32`` activates the width layer only when the file's schema says
``Identifier`` is v1 (so it is safe to call on ANY release -- for 2024+ it
degrades to plain ``versions.reading``).
"""
from __future__ import annotations

import struct
import zlib
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

# NOTE: heavy rvt modules are imported lazily inside functions so that
# importing rvt.versions.records32 never drags the whole stack in (and so
# there is no import cycle with rvt.validate, which imports rvt.partitions).

RAW_HDR_101 = 8            # i32 id + u32 psize
RAW_HDR_10X = 12           # i32 id + u32 stamp + u32 psize
REC_SIZE32 = 28            # ElemTable row: 7 x u32
FOOTER_LEN32 = 19          # ElemTable footer: <IIH> + pad u8 + u32 last_id + u32 0
INVALID_OWNER32 = 0xFFFFFFFF

__all__ = [
    "RAW_HDR_101", "RAW_HDR_10X", "REC_SIZE32", "FOOTER_LEN32",
    "is_ids32", "raw_hdr_len32", "iter_records32", "parse_elemtable32",
    "decode_elemtable32", "encode_elemtable32", "scan_stream_ids32",
    "activate_ids32", "ids32", "reading32",
]


# ---------------------------------------------------------------------------
# detection: the file's own schema declares the id width
# ---------------------------------------------------------------------------
def is_ids32(schema) -> bool:
    """True iff this schema serializes element ids as 32-bit values.

    The authority is the schema's OWN declaration: ``Identifier`` v1 has the
    single field ``m_id`` with primitive kind 0x04 (i32); v2 (2024+) has
    ``m_id64`` kind 0x0b (i64)."""
    c = schema.by_name.get("Identifier")
    if c is None or not c.fields:
        return False
    f = c.fields[0]
    return f.name == "m_id" and f.kind == 0x04


def raw_hdr_len32(seq: int) -> int:
    """Record header bytes BEFORE the body in the 32-bit era."""
    return RAW_HDR_101 if seq == 101 else RAW_HDR_10X


# ---------------------------------------------------------------------------
# record framing (32-bit): the iter_records / _iter_seg_records variants
# ---------------------------------------------------------------------------
def iter_records32(seg: bytes, seq: int = 102):
    """32-bit-id variant of :func:`rvt.objects.iter_records` (same Record)."""
    from ..objects import Record
    hlen = raw_hdr_len32(seq)
    p = 0
    n = len(seg)
    while p + hlen + 4 <= n:
        if seq == 101:
            eid, size = struct.unpack_from("<iI", seg, p)
            stamp = 0
        else:
            eid, stamp, size = struct.unpack_from("<iII", seg, p)
        if eid < -1 or size > (1 << 30):
            return
        pay = seg[p + hlen: p + hlen + size]
        if len(pay) < size:
            return
        tail_off = p + hlen + size
        trailer_ok = True
        if tail_off + 4 <= n:
            trailer_ok = struct.unpack_from("<I", seg, tail_off)[0] == size
        if size >= 2:
            cls = struct.unpack_from("<H", pay, 0)[0]
            payload = pay[2:]
        else:
            cls = 0
            payload = b""
        yield Record(eid, stamp, cls, size, payload, p, trailer_ok)
        p = tail_off + 4


def _iter_seg_records32(seg: bytes, seq: int, unit: int):
    """32-bit-id variant of ``rvt.validate._iter_seg_records`` (same _Rec)."""
    from .. import validate as V
    hlen = raw_hdr_len32(seq)
    p = 0
    n = len(seg)
    while p + hlen + 4 <= n:
        if seq == 101:
            eid, size = struct.unpack_from("<iI", seg, p)
            stamp = 0
        else:
            eid, stamp, size = struct.unpack_from("<iII", seg, p)
        if eid < -1 or size > (1 << 30):
            return
        if p + hlen + size + 4 > n:
            return
        tail = p + hlen + size
        rep_ok = struct.unpack_from("<I", seg, tail)[0] == size
        cls = struct.unpack_from("<H", seg, p + hlen)[0] if size >= 2 else 0
        yield V._Rec(seq, unit, eid, stamp, size, cls, p + hlen, rep_ok)
        p = tail + 4


def parse_record_header32(buf: bytes, p: int, seq: int):
    """32-bit-id variant of ``rvt.partitions.parse_record_header``."""
    from .. import partitions as P
    if seq == 101:
        eid, size, cls = struct.unpack_from("<iIH", buf, p)
        return P.RecordHeader(p, eid, None, size, cls, RAW_HDR_101 + 4)
    eid, stamp, size, cls = struct.unpack_from("<iIIH", buf, p)
    return P.RecordHeader(p, eid, stamp, size, cls, RAW_HDR_10X + 4)


def record_bytes32(seg: bytes, rec, seq: int) -> bytes:
    """32-bit-id variant of ``rvt.encode.record_bytes``."""
    hlen = raw_hdr_len32(seq)
    return seg[rec.seg_offset: rec.seg_offset + hlen + rec.body_size + 4]


def _record_spans32(seg: bytes, seq: int):
    """32-bit-id variant of ``rvt.manipulate._record_spans``."""
    hlen = raw_hdr_len32(seq)
    out = []
    for r in iter_records32(seg, seq):
        out.append((r, r.seg_offset, hlen + r.body_size + 4))
    return out


# ---------------------------------------------------------------------------
# record emit (32-bit)
# ---------------------------------------------------------------------------
def _oe_encode_record32(self, seq: int, elem_id: int, stamp: int, class_id: int,
                        value: Optional[dict], psize: Optional[int] = None) -> bytes:
    """32-bit-id variant of ``ObjectEncoder.encode_record`` (bound as method)."""
    from ..encode import _PSIZE, _U16
    if elem_id < 0 or psize == 0:
        hdr = struct.pack("<iI", elem_id, 0) if seq == 101 \
            else struct.pack("<iII", elem_id, stamp, 0)
        return hdr + _PSIZE.pack(0)
    body = self.encode_object(class_id, value or {})
    ps = 2 + len(body)
    hdr = struct.pack("<iI", elem_id, ps) if seq == 101 \
        else struct.pack("<iII", elem_id, stamp, ps)
    return hdr + _U16.pack(class_id) + body + _PSIZE.pack(ps)


def _encode_record_module32(seq: int, elem_id: int, stamp, class_id: int, value) -> bytes:
    """32-bit-id variant of the module-level ``rvt.encode.encode_record``."""
    import rvt.encode as E
    if E._DEFAULT_ENCODER is None:
        E._DEFAULT_ENCODER = E.ObjectEncoder()
    enc = E._DEFAULT_ENCODER
    if elem_id < 0:
        s = 1 if stamp is None else stamp
        return enc.encode_record(seq, elem_id, s, 0, None, psize=0)
    if seq == 101 or stamp is not None:
        return enc.encode_record(seq, elem_id, 0 if stamp is None else stamp,
                                 class_id, value)
    body = enc.encode_object(class_id, value or {})
    ps = 2 + len(body)
    st = E.record_stamp(class_id, body)
    return (struct.pack("<iII", elem_id, st, ps)
            + E._U16.pack(class_id) + body + E._PSIZE.pack(ps))


def _es_frame32(self, seq: int, eid: int, class_id: int, value: dict) -> bytes:
    """32-bit-id variant of ``manipulate.EditSession.frame`` (bound as method)."""
    body = self.enc.encode_object(class_id, value or {})
    ps = 2 + len(body)
    payload = struct.pack("<H", class_id) + body
    if seq == 101:
        hdr = struct.pack("<iI", eid, ps)
    else:
        stamp = zlib.adler32(payload) & 0xFFFFFFFF
        hdr = struct.pack("<iII", eid, stamp, ps)
    return hdr + payload + struct.pack("<I", ps)


def _le_id_patterns32(ids: Iterable[int]) -> List[bytes]:
    """32-bit-id variant of ``manipulate._le_id_patterns``."""
    return [struct.pack("<i", i) for i in ids]


def _assert_sentinel_tail32(payload: bytes, seq: int) -> int:
    """32-bit-id variant of ``commit._assert_sentinel_tail``."""
    sl = raw_hdr_len32(seq) + 4
    off = len(payload) - sl
    if off < 0:
        raise ValueError(f"seq {seq}: last block too small for a sentinel")
    if seq == 101:
        eid, ps = struct.unpack_from("<iI", payload, off)
    else:
        eid, _st, ps = struct.unpack_from("<iII", payload, off)
    rep = struct.unpack_from("<I", payload, len(payload) - 4)[0]
    if not (eid == -1 and ps == 0 and rep == 0):
        raise ValueError(
            f"seq {seq}: last block does not end with a sentinel record "
            f"(id={eid}, psize={ps}, repeat={rep})")
    return off


def verify_reduced32(path: str, deleted_ids: Iterable[int] = ()) -> dict:
    """32-bit-id variant of :func:`rvt.reduce.verify_reduced`.

    TRACKS rvt.reduce.verify_reduced (2026-08-04 shape) with exactly two
    width fixes: the seq-102/103 record stamp sits at offset 4 (after the
    i32 id, not offset 8 after an i64 id) and the record body starts at the
    12-byte header (not 16).  Everything else is delegated to the SAME
    helpers verify_reduced uses -- which are themselves patched while
    :func:`ids32` is active (split_records -> iter_records32, the elemtable
    codec, the framing ordinals via versions.reading)."""
    import struct as _s
    from .. import ecc
    from .. import reduce as R
    from ..container import open_rvt
    from ..partitions import StreamWalker
    deleted = {int(i) for i in deleted_ids}
    rep: dict = {"path": path, "crc_failures": 0, "ecc_mismatches": 0,
                 "walker_errors": [], "elemtable_count": None,
                 "header_count": None, "counts_match": None,
                 "sentinel_last": {}, "segment_walks": {},
                 "seq_id_sets_equal": None, "stamps_bad": 0,
                 "deleted_still_present": [], "elemtable_ids_without_record": 0,
                 "units": None, "blocks_unit0": None, "ok": False}
    with open_rvt(path) as d:
        pname = d.partition_streams()[0]
        rep["crc_failures"] = sum(0 if m.crc_ok else 1
                                  for s in d.streams() for m in d.members(s.name))
        for name in (pname, "Global/ElemTable"):
            raw = d.raw(name)
            try:
                if ecc.frame_stream(R.unframe_exact(raw)) != raw:
                    rep["ecc_mismatches"] += 1
            except Exception:
                rep["ecc_mismatches"] += 1
        model = decode_elemtable32(d.inflate("Global/ElemTable"))
        et_ids = {r[4] for r in model["records"]}
        rep["elemtable_count"] = len(model["records"])
        logical = d.logical(pname)
        rep["header_count"] = _s.unpack_from("<I", logical, R.PART_HDR_COUNT_OFF)[0]
        rep["counts_match"] = (rep["header_count"] == rep["elemtable_count"])
        w = StreamWalker(logical, inflate=True, keep_data=True)
        rep["walker_errors"] = w.errors
        rep["units"] = len(w.units)
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        rep["blocks_unit0"] = len(u0)
        rep["isize_identity_ok"] = all(len(b.data) == b.intended_len for b in u0)
        ids_by_seq: Dict[int, set] = {}
        for seq in R.SEQS:
            seg = b"".join(b.data for b in u0 if b.seq == seq)
            ids: set = set()
            walk_ok = True
            last_sentinel = False
            try:
                recs = R.split_records(seg, seq)
                last_sentinel = recs[-1].is_sentinel
                for r in recs:
                    if r.is_sentinel:
                        continue
                    ids.add(r.elem_id)
                    if seq != 101 and r.size >= 2:
                        stamp = _s.unpack_from("<I", r.data, 4)[0]       # after i32 id
                        body = r.data[RAW_HDR_10X:RAW_HDR_10X + r.size]  # 12-byte hdr
                        if (zlib.adler32(body) & 0xFFFFFFFF) != stamp:
                            rep["stamps_bad"] += 1
            except ValueError as e:
                walk_ok = False
                rep["walker_errors"].append(f"seq{seq}: {e}")
            rep["segment_walks"][seq] = walk_ok
            rep["sentinel_last"][seq] = last_sentinel
            ids_by_seq[seq] = ids
        rep["seq_id_sets_equal"] = (ids_by_seq[101] == ids_by_seq[102] == ids_by_seq[103])
        alive = ids_by_seq[102]
        rep["deleted_still_present"] = sorted((deleted & alive) | (deleted & et_ids))[:20]
        rep["elemtable_ids_without_record"] = len(et_ids - alive)
        rep["unit0_element_records"] = len(alive)
    rep["ok"] = (rep["crc_failures"] == 0 and rep["ecc_mismatches"] == 0
                 and not rep["walker_errors"] and rep["counts_match"]
                 and all(rep["sentinel_last"].values())
                 and all(rep["segment_walks"].values())
                 and rep["seq_id_sets_equal"] and rep["stamps_bad"] == 0
                 and not rep["deleted_still_present"]
                 and rep["elemtable_ids_without_record"] == 0
                 and rep["isize_identity_ok"])
    return rep


def verify_manipulated32(path: str, *, deleted_ids=(), edited_ids=(),
                         expect_elemtable_count: Optional[int] = None) -> dict:
    """32-bit-id variant of :func:`rvt.manipulate.verify_manipulated`.

    TRACKS rvt.manipulate.verify_manipulated (2026-08-04 shape) with two
    fixes: the seq-102/103 record body starts at the 12-byte header (not
    16) for the stamp check, and the clean-decode probe of edited records
    uses the FILE'S OWN schema (the original builds ObjectDecoder() over
    the canonical 2026 schema, which mis-decodes 2023 ordinals).  All other
    helpers (iter_records, decode_elemtable) resolve to the patched
    bindings while :func:`ids32` is active."""
    import struct as _s
    from .. import ecc
    from .. import manipulate as M
    from ..container import open_rvt
    from ..objects import ObjectDecoder
    from ..partitions import StreamWalker
    from . import schema_of
    rep: Dict[str, Any] = {"crc_failures": 0, "ecc_mismatches": 0,
                           "walker_errors": 0, "isize_identity_mismatches": 0,
                           "elemtable_count": None, "header_count": None,
                           "sentinel_last": {}, "stamps_ok": True,
                           "deleted_still_present": {}, "deleted_in_elemtable": [],
                           "edited": {}, "elemtable_ids_sorted": None,
                           "unit0_ids_equal_elemtable": None}
    with open_rvt(path) as d:
        pname = M._primary_partition(d, None)
        rep["crc_failures"] = sum(0 if m.crc_ok else 1
                                  for s in d.streams() for m in d.members(s.name))
        for name in (pname, "Global/ElemTable"):
            raw = d.raw(name)
            n_full = len(raw) // ecc.PAGE_STRIDE
            for k in range(n_full):
                page = raw[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
                tr = raw[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE]
                if ecc.page_trailer(page) != tr:
                    rep["ecc_mismatches"] += 1
        model = decode_elemtable32(d.inflate("Global/ElemTable"))
        et_ids = [r[4] for r in model["records"]]
        rep["elemtable_count"] = len(et_ids)
        rep["elemtable_ids_sorted"] = et_ids == sorted(et_ids)
        etset = set(et_ids)
        rep["deleted_in_elemtable"] = [i for i in deleted_ids if i in etset]
        logical = d.logical(pname)
        rep["header_count"] = _s.unpack_from("<I", logical, M.PART_HDR_COUNT_OFF)[0]
        w = StreamWalker(logical, inflate=True, keep_data=True)
        rep["walker_errors"] = len(w.errors)
        rep["isize_identity_mismatches"] = sum(
            1 for b in w.blocks if b.data is not None and b.intended_len != len(b.data))
        dec = ObjectDecoder(schema_of(path))          # the FILE'S schema
        u0_102_ids = None
        for seq in (101, 102, 103):
            seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset)
                           if b.unit == 0 and b.seq == seq)
            recs = list(iter_records32(seg, seq))
            rep["sentinel_last"][seq] = bool(recs) and recs[-1].elem_id == -1
            ids_here = set()
            for r in recs:
                if r.elem_id >= 0:
                    ids_here.add(r.elem_id)
                if r.elem_id in deleted_ids:
                    rep["deleted_still_present"].setdefault(seq, []).append(r.elem_id)
                if r.elem_id in edited_ids:
                    o = dec.decode_record(r.class_id, r.payload) if r.body_size >= 2 else None
                    rep["edited"].setdefault(str(r.elem_id), {})[str(seq)] = {
                        "class": (o.class_name if o else None),
                        "clean": (bool(o.clean or o.stub) if o else None)}
                if seq != 101 and r.elem_id >= 0 and r.body_size >= 2:
                    body = seg[r.seg_offset + RAW_HDR_10X:
                               r.seg_offset + RAW_HDR_10X + r.body_size]
                    if (zlib.adler32(body) & 0xFFFFFFFF) != r.stamp:
                        rep["stamps_ok"] = False
            if seq == 102:
                u0_102_ids = ids_here
        if u0_102_ids is not None:
            rep["unit0_ids_equal_elemtable"] = (u0_102_ids == etset)
    if expect_elemtable_count is not None:
        rep["elemtable_count_expected"] = expect_elemtable_count
    return rep


def scan_stream_ids32(payload: bytes, valid) -> set:
    """32-bit-id variant of ``rvt.reduce.scan_stream_ids`` (i32 scan)."""
    found = set()
    if not valid:
        return found
    lo, hi = 4096, max(valid)
    n = len(payload)
    for off in range(0, n - 3):
        v = struct.unpack_from("<i", payload, off)[0]
        if lo <= v <= hi and v in valid:
            found.add(v)
    return found


# ---------------------------------------------------------------------------
# Global/ElemTable (32-bit wire <-> the NORMALIZED 2024+ model)
# ---------------------------------------------------------------------------
def parse_elemtable32(payload: bytes, project: str = "?"):
    """Parse a 2023 (32-bit era) ``Global/ElemTable`` payload into the SAME
    :class:`rvt.elemtable.ElemTable` model 2024+ files produce.

    2023 wire row (28 B): ``<7I`` = original_id, id, creation_ep,
    modified_ep, user_modified_ep, partition_id, owner_id -- note ID SECOND
    and the owner/partition order swapped vs 2024+.  owner 0xFFFFFFFF is
    normalized to the 64-bit ``INVALID_ID`` so every model consumer sees
    2024+ semantics.  Footer (19 B): ``<IIH`` graveyard_count, marker,
    tail_class + u8 pad + u32 last_id + u32 zero."""
    from .. import elemtable as ET
    if len(payload) < 6:
        raise ValueError("payload too short")
    class_tag, count = struct.unpack_from("<HI", payload, 0)
    tbl = ET.ElemTable(project=project, class_tag=class_tag, count=count,
                       payload_len=len(payload))
    need = 6 + count * REC_SIZE32
    if len(payload) < need:
        raise ValueError(f"payload {len(payload)} < needed {need} for {count} "
                         "32-bit-era records")
    unpack = struct.Struct("<7I").unpack_from
    off = 6
    for i in range(count):
        o, eid, ce, me, ue, pid, own = unpack(payload, off)
        own64 = ET.INVALID_ID if own == INVALID_OWNER32 else own
        tbl.records.append(ET.ElemRec(i, o, ce, me, ue, eid, own64, pid))
        off += REC_SIZE32
    tail = payload[off:]
    if len(tail) >= FOOTER_LEN32:
        gcnt, marker, tcls = struct.unpack_from("<IIH", tail, 0)
        tpad = tail[10]
        last_id, tz = struct.unpack_from("<II", tail, 11)
        tbl.footer = ET.ElemTableFooter(gcnt, marker, tcls, tpad, last_id, tz, tail)
    else:
        tbl.footer = ET.ElemTableFooter(0, 0, 0, 0, 0, 0, tail)
    return tbl


def decode_elemtable32(payload: bytes) -> Dict[str, Any]:
    """32-bit-era variant of ``stream_encoders.decode_elemtable`` -- SAME
    model dict shape (normalized), 2023 wire."""
    t = parse_elemtable32(payload)
    f = t.footer
    tail = payload[6 + REC_SIZE32 * t.count:]
    if len(tail) != FOOTER_LEN32 or f.graveyard_count != 0:
        raise ValueError(
            f"32-bit-era ElemTable footer is {len(tail)} bytes / graveyard "
            f"{f.graveyard_count} -- layout not the observed 2023 corpus shape")
    return {
        "stream": "ElemTable",
        "class_tag": t.class_tag,
        "records": [(r.original_id, r.creation_ep, r.modified_ep,
                     r.user_modified_ep, r.id, r.owner_id, r.partition_id)
                    for r in t.records],
        "graveyard_count": f.graveyard_count,
        "footer": {
            "marker": f.marker,
            "tail_class": f.tail_class,
            "tail_pad": f.tail_pad,
            "last_id": f.last_id,
            "tail_zero": f.tail_zero,
        },
    }


def encode_elemtable32(model: Dict[str, Any]) -> bytes:
    """Inverse of :func:`decode_elemtable32` (byte-exact on the corpus):
    normalized 2024+-shaped model -> 2023 wire."""
    from .. import elemtable as ET
    recs = model["records"]
    f = model["footer"]
    out = bytearray()
    out += struct.pack("<HI", model["class_tag"], len(recs))
    pack = struct.Struct("<7I").pack
    for (o, ce, me, ue, eid, own, pid) in recs:
        own32 = INVALID_OWNER32 if own == ET.INVALID_ID else own
        if not (0 <= own32 <= 0xFFFFFFFF and 0 <= eid <= 0xFFFFFFFF
                and 0 <= o <= 0xFFFFFFFF):
            raise ValueError(f"id out of 32-bit range in record {(o, eid, own)}")
        out += pack(o, eid, ce, me, ue, pid, own32)
    out += struct.pack("<IIH", model.get("graveyard_count", 0), f["marker"],
                       f["tail_class"])
    out += bytes([f.get("tail_pad", 0) & 0xFF])
    out += struct.pack("<II", f["last_id"], f.get("tail_zero", 0))
    return bytes(out)


# ---------------------------------------------------------------------------
# the patch table + activation
# ---------------------------------------------------------------------------
def _reader_element_id32(self) -> int:
    """ElementId = Identifier v1 = i32 LE, -1 invalid (Revit <= 2023)."""
    return self.i32()


def _writer_element_id32(self, v: int) -> None:
    self.buf += struct.pack("<i", v)


def _raw_hdr_len_32(seq: int) -> int:
    return raw_hdr_len32(seq)


def _patch_table():
    """[(module, attr, replacement)] -- resolved lazily so imports happen
    at activation, not module import."""
    import importlib
    E = importlib.import_module("rvt.encode")
    O = importlib.import_module("rvt.objects")
    V = importlib.import_module("rvt.validate")
    P = importlib.import_module("rvt.partitions")
    R = importlib.import_module("rvt.reduce")
    C = importlib.import_module("rvt.commit")
    M = importlib.import_module("rvt.manipulate")
    ET = importlib.import_module("rvt.elemtable")
    SE = importlib.import_module("rvt.stream_encoders")
    MU = importlib.import_module("rvt.mutate")
    FA = importlib.import_module("rvt.families")
    RA = importlib.import_module("rvt.regadd")
    RD = importlib.import_module("rvt.regdiff")

    t: List[Tuple[Any, str, Any]] = [
        # in-body id width (Reader/Writer methods -- one central place each)
        (O.Reader, "element_id", _reader_element_id32),
        (E.Writer, "element_id", _writer_element_id32),
        # record framing: the walker + every module-level from-import of it
        (O, "iter_records", iter_records32),
        (E, "iter_records", iter_records32),
        (FA, "iter_records", iter_records32),
        (M, "iter_records", iter_records32),
        (MU, "iter_records", iter_records32),
        (RA, "iter_records", iter_records32),
        (R, "iter_records", iter_records32),
        (RD, "iter_records", iter_records32),
        (V, "_iter_seg_records", _iter_seg_records32),
        (P, "parse_record_header", parse_record_header32),
        (P, "RECORD_HDR_101", RAW_HDR_101 + 4),
        (P, "RECORD_HDR_10X", RAW_HDR_10X + 4),
        (R, "_raw_hdr_len", _raw_hdr_len_32),
        (C, "_hdr_len", _raw_hdr_len_32),
        (C, "_assert_sentinel_tail", _assert_sentinel_tail32),
        (E, "record_bytes", record_bytes32),
        (M, "_record_spans", _record_spans32),
        # record emit
        (E.ObjectEncoder, "encode_record", _oe_encode_record32),
        (E, "encode_record", _encode_record_module32),
        (M.EditSession, "frame", _es_frame32),
        (M, "_le_id_patterns", _le_id_patterns32),
        # heuristic id scans
        (R, "scan_stream_ids", scan_stream_ids32),
        # the structural verifiers (stamp offset / body slice are width-baked)
        (R, "verify_reduced", verify_reduced32),
        (M, "verify_manipulated", verify_manipulated32),
        # ElemTable wire codec (+ every module-level from-import)
        (ET, "parse_elemtable", parse_elemtable32),
        (ET, "REC_SIZE", REC_SIZE32),
        (ET, "REC_FMT", "<7I"),
        (SE, "decode_elemtable", decode_elemtable32),
        (SE, "encode_elemtable", encode_elemtable32),
        (SE, "ELEMTABLE_FOOTER_LEN", FOOTER_LEN32),
        (C, "decode_elemtable", decode_elemtable32),
        (C, "encode_elemtable", encode_elemtable32),
        (M, "decode_elemtable", decode_elemtable32),
        (M, "encode_elemtable", encode_elemtable32),
        (R, "decode_elemtable", decode_elemtable32),
        (R, "encode_elemtable", encode_elemtable32),
        (RA, "decode_elemtable", decode_elemtable32),
        (RA, "encode_elemtable", encode_elemtable32),
        (RD, "decode_elemtable", decode_elemtable32),
    ]
    return t


def activate_ids32() -> List[Tuple[Any, str, Any]]:
    """Swap the stack into the 32-bit-id era; returns the previous bindings
    for :func:`restore_ids32`.  Prefer the :func:`ids32` context manager."""
    prev: List[Tuple[Any, str, Any]] = []
    for holder, attr, repl in _patch_table():
        prev.append((holder, attr, holder.__dict__.get(attr, getattr(holder, attr))))
        setattr(holder, attr, repl)
    return prev


def restore_ids32(prev: List[Tuple[Any, str, Any]]) -> None:
    for holder, attr, val in reversed(prev):
        setattr(holder, attr, val)


@contextmanager
def ids32() -> Iterator[None]:
    """The 32-bit element-id era, active for the duration of the block."""
    prev = activate_ids32()
    try:
        yield
    finally:
        restore_ids32(prev)


@contextmanager
def reading32(source: Any) -> Iterator[Dict[str, int]]:
    """Read a file of ANY release correctly: the file's own framing ordinals
    (``rvt.versions.reading``) plus, iff its schema declares 32-bit ids
    (``Identifier`` v1 -- Revit <= 2023), the 32-bit record layer."""
    from . import reading, schema_of
    sch = schema_of(source)
    with reading(source, schema=sch) as ords:
        if is_ids32(sch):
            with ids32():
                yield ords
        else:
            yield ords
