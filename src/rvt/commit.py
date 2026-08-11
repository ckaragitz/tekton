"""commit.py — splice new/edited element records into a .rvt and re-emit it.

This is the writer's final assembly stage. Given a source .rvt and a set of
NEW elements (each = one framed record per seq 101/102/103 plus a 40-byte
ElemRec plan), it:

  1. Appends each element's records to save-unit 0 (the host document) of
     the Partitions/<N> stream, immediately BEFORE each per-seq sentinel
     record (which must remain the last record of the unit's segment).
     Only the LAST block of each seq run is touched; its header counters are
     recomputed (A += n, C via the ISIZE identity), and every block's gzip
     member is recompressed (B recomputed).
  2. Appends the ElemRecs to Global/ElemTable (id-sorted, watermark raised).
  3. Bumps the partition stream header's elem_table_count to match.
  4. Re-frames both streams with real CRCIO ECC and rebuilds the container.

Save-history streams (DocumentIncrementTable / History / BasicFileInfo /
Contents) are deliberately NOT modified in this minimal commit: the new
ElemRecs reuse an EXISTING episode so the History invariant
(count == max(modified_ep) + 1) still holds. A full record_save() can be
layered on later (see rvt.streams_edit).
"""
from __future__ import annotations

import dataclasses
import struct
from typing import Dict, List, Sequence, Tuple

from . import ecc
from . import partitions as _P
from .container import open_rvt
from .partitions import StreamWalker
from .roundtrip import rewrite_entries
from .stream_encoders import (decode_elemtable, encode_elemtable,
                              global_prefix)
from .streams_edit import elemtable_add_element
from .writer import gzip_member

_ISIZE_ADJ = {4: 0, 5: 4, 6: -4, 7: 0}
PART_HDR_COUNT_OFF = 14        # u32 elem_table_count in the 18-byte stream header


def _hdr_len(seq: int) -> int:
    return 12 if seq == 101 else 16


def _sentinel_len(seq: int) -> int:
    return _hdr_len(seq) + 4      # header (psize 0) + u32 repeat


def _assert_sentinel_tail(payload: bytes, seq: int) -> int:
    """Return the offset where the sentinel record starts (payload tail)."""
    sl = _sentinel_len(seq)
    off = len(payload) - sl
    if off < 0:
        raise ValueError(f"seq {seq}: last block too small for a sentinel")
    if seq == 101:
        eid, ps = struct.unpack_from("<qI", payload, off)
    else:
        eid, _st, ps = struct.unpack_from("<qII", payload, off)
    rep = struct.unpack_from("<I", payload, len(payload) - 4)[0]
    if not (eid == -1 and ps == 0 and rep == 0):
        raise ValueError(
            f"seq {seq}: last block does not end with a sentinel record "
            f"(id={eid}, psize={ps}, repeat={rep})")
    return off


@dataclasses.dataclass
class CommitReport:
    partition: str
    new_element_ids: List[int]
    elemtable_count_before: int
    elemtable_count_after: int
    watermark_after: int
    per_seq_bytes_added: Dict[int, int]
    out_path: str


def commit_new_elements(src_rvt: str, out_path: str,
                        records_by_element: Sequence[Dict[int, bytes]],
                        elemrecs: Sequence, *,
                        creation_ep: int | None = None,
                        identity: dict | None = None) -> CommitReport:
    """Append new elements to ``src_rvt`` and write the result to ``out_path``.

    ``records_by_element``: for each new element, {seq: framed_record_bytes}
    for seq in (101, 102, 103). ``elemrecs``: matching ElemRecPlan objects
    (need .elem_id, .original_id, .owner_id, .partition_id). ``creation_ep``
    defaults to the current maximum modified episode in the ElemTable.
    """
    new_streams: Dict[str, bytes] = {}
    with open_rvt(src_rvt) as doc:
        parts = doc.partition_streams()
        if len(parts) != 1:
            raise NotImplementedError(f"expected one partition stream, got {parts}")
        pname = parts[0]
        bfi = doc.raw("BasicFileInfo") if doc.has("BasicFileInfo") else None

        # ---------------- 1. ElemTable ------------------------------------
        et_payload = doc.inflate("Global/ElemTable")
        model = decode_elemtable(et_payload)
        count_before = len(model["records"])
        if creation_ep is None:
            # modified_ep is the 3rd u32 of each ElemRec tuple in this model
            creation_ep = max(r[2] for r in model["records"])
        new_ids = []
        for plan in elemrecs:
            # let streams_edit apply its own defaults for original_id (== id),
            # owner (INVALID) and partition (0); only the episodes are chosen here
            own = plan.owner_id if getattr(plan, "owner_id", -1) not in (None, -1) \
                else 0xFFFFFFFFFFFFFFFF
            elemtable_add_element(model, plan.elem_id,
                                  creation_ep=creation_ep,
                                  modified_ep=creation_ep,
                                  user_modified_ep=creation_ep,
                                  owner_id=own)
            new_ids.append(plan.elem_id)
        count_after = len(model["records"])
        watermark_after = model["footer"]["last_id"]
        et_new_payload = encode_elemtable(model)
        et_logical = global_prefix("Global/ElemTable") + gzip_member(et_new_payload, level=3)
        new_streams["Global/ElemTable"] = ecc.frame_stream(et_logical)

        # ---------------- 2. Partitions/<N> --------------------------------
        logical = doc.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"walker errors on source: {w.errors[:3]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        u0_last: Dict[int, object] = {}
        for b in blocks:
            if b.unit == 0:
                u0_last[b.seq] = b            # last block wins (stream order)
        for seq in (101, 102, 103):
            if seq not in u0_last:
                raise RuntimeError(f"unit 0 has no seq-{seq} blocks")

        overrides: Dict[int, Tuple[bytes, int]] = {}   # block.index -> (payload, added_records)
        added_bytes: Dict[int, int] = {}
        for seq in (101, 102, 103):
            b = u0_last[seq]
            payload = b.data
            ins = _assert_sentinel_tail(payload, seq)
            extra = b"".join(recs[seq] for recs in records_by_element if seq in recs)
            overrides[b.index] = (payload[:ins] + extra + payload[ins:], len(records_by_element))
            added_bytes[seq] = len(extra)

        out = bytearray()
        cursor = 0
        for b in blocks:
            payload = b.data
            add_recs = 0
            if b.index in overrides:
                payload, add_recs = overrides[b.index]
            out += logical[cursor:b.member_offset]
            hdr = len(out) - (b.member_offset - b.hdr_offset)
            gz = gzip_member(payload, level=3, sync_flush=True)
            nb = 8 + len(gz)
            struct.pack_into("<I", out, hdr + 10, nb)          # B
            if add_recs:
                a_new = b.n_records + add_recs
                adj = _ISIZE_ADJ.get(b.flags, 0)
                c_new = len(payload) - (16 if b.seq == 101 else 20) * a_new - adj  # ISIZE identity uses wave-1 hdr lens
                struct.pack_into("<I", out, hdr + 6, a_new)   # A
                struct.pack_into("<I", out, hdr + 14, c_new)  # C
            out += gz
            out += struct.pack("<HI", _P.TRAILER_TAG, nb)   # the tag in force NOW (#467)
            cursor = b.member_offset + b.member_len + 6
        out += logical[cursor:]
        # header elem_table_count += n
        struct.pack_into("<I", out, PART_HDR_COUNT_OFF, count_after)
        # truncate after the end record
        w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
        if w2.errors:
            raise RuntimeError(f"walker errors after splice: {w2.errors[:3]}")
        part_logical = bytes(out[:w2.end_offset + len(w2.end_record)])
        new_streams[pname] = ecc.frame_stream(part_logical)

    # ---------------- 3. identity: the writer OWNS BasicFileInfo (gate G2) ---
    # A generated file never inherits the template's identity (an Autodesk
    # employee's local path + the sample GUIDs). author/client strings are
    # kept by default pending counsel decision C1.
    try:
        from .identity import own_basic_file_info
        if bfi is not None:
            from .stream_encoders import decode_basic_file_info as _dbfi
            _cur_guid = _dbfi(bfi).get("unique_document_guid")
            _ident = dict(identity or {})
            _ident.setdefault("document_guid", _cur_guid)   # keeps History[0] coherence
            new_streams["BasicFileInfo"] = own_basic_file_info(
                bfi, out_path=out_path, **_ident)
    except Exception as exc:                 # never let identity break a commit
        import warnings
        warnings.warn(f"identity scrub skipped: {exc}")

    # ---------------- 3b. identity: own the DocumentIncrementTable usernames --
    # Every save-episode row carries the saving user's name; a clone inherits
    # Autodesk employees' usernames. Rewrite them (same identity policy).
    if "Global/DocumentIncrementTable" not in new_streams:
        try:
            from .identity import own_increment_table_stream
            with open_rvt(src_rvt) as _doc:
                _pref = _doc.prefix("Global/DocumentIncrementTable")
                _infl = _doc.inflate("Global/DocumentIncrementTable", 0)
                _raw = _doc.raw("Global/DocumentIncrementTable")
            new_streams["Global/DocumentIncrementTable"] = own_increment_table_stream(
                _raw, _pref, _infl, username=(identity or {}).get("username", ""))
        except Exception as exc:
            import warnings
            warnings.warn(f"increment-table identity scrub skipped: {exc}")

    # ---------------- 4. write ------------------------------------------------
    rewrite_entries(src_rvt, out_path, new_streams)
    return CommitReport(pname, new_ids, count_before, count_after,
                        watermark_after, added_bytes, out_path)


def verify_written(path: str, expect_ids: Sequence[int]) -> dict:
    """Read a committed file back and prove structural + semantic health."""
    from .objects import ObjectDecoder, iter_records
    rep = {"crc_failures": 0, "ecc_mismatches": 0, "walker_errors": 0,
           "new_ids_found": {}, "elemtable_count": None,
           "header_count": None, "sentinel_last": {}, "stamps_ok": None}
    with open_rvt(path) as d:
        pname = d.partition_streams()[0]
        rep["crc_failures"] = sum(0 if m.crc_ok else 1
                                   for s in d.streams() for m in d.members(s.name))
        for name in (pname, "Global/ElemTable"):
            rep["ecc_mismatches"] += ecc.framing_mismatches(d.raw(name))
        model = decode_elemtable(d.inflate("Global/ElemTable"))
        rep["elemtable_count"] = len(model["records"])
        logical = d.logical(pname)
        rep["header_count"] = struct.unpack_from("<I", logical, PART_HDR_COUNT_OFF)[0]
        w = StreamWalker(logical, inflate=True, keep_data=True)
        rep["walker_errors"] = len(w.errors)
        dec = ObjectDecoder()
        stamps_ok = True
        for seq in (101, 102, 103):
            seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset)
                           if b.unit == 0 and b.seq == seq)
            recs = list(iter_records(seg, seq))
            rep["sentinel_last"][seq] = (recs[-1].elem_id == -1)
            found = {}
            for r in recs:
                if r.elem_id in expect_ids:
                    obj = dec.decode_record(r.class_id, r.payload) if r.body_size >= 2 else None
                    found[r.elem_id] = {"class": r.class_id,
                                        "clean": (obj.clean if obj else None)}
                if seq != 101 and r.body_size >= 2:
                    import zlib
                    body = seg[r.seg_offset + 16: r.seg_offset + 16 + r.body_size]
                    if (zlib.adler32(body) & 0xFFFFFFFF) != r.stamp:
                        stamps_ok = False
            rep["new_ids_found"][seq] = found
        rep["stamps_ok"] = stamps_ok
    return rep
