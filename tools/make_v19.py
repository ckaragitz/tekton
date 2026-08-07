#!/usr/bin/env python3
"""V19 — first authored change WITH a correct record stamp.

Same size-preserving edit as V18 (cover-sheet RTF title), but the containing
seq-102 record's u32 stamp is recomputed as adler32(u16 class_id + object)
(the mutation-planner's solved rule, 287,441/287,441 verified). V18 (stale
stamp) vs V19 (fresh stamp) together tell us whether stamps are validated.
"""
import dataclasses
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import ecc  # noqa: E402
from rvt.cfb_writer import write_cfb  # noqa: E402
from rvt.container import open_rvt  # noqa: E402
from rvt.objects import iter_records  # noqa: E402
from rvt.partitions import StreamWalker  # noqa: E402
from rvt.roundtrip import read_entries  # noqa: E402
from rvt.writer import BLOCK_TRL_TAG, gzip_member  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "acceptance", "V19_authored_change_stamped.rvt")
PNAME = "Partitions/21"
OLD = b"Basic Structural Sample Project"
NEW = b"REV-REVIT WROTE THIS RVT FILE!!"
assert len(OLD) == len(NEW) == 31
SEQ = 102


def stamp_of(seg: bytes, rec) -> int:
    """adler32 over the record body (u16 class_id + object bytes)."""
    hlen = 16
    body = seg[rec.seg_offset + hlen: rec.seg_offset + hlen + rec.body_size]
    return zlib.adler32(body) & 0xFFFFFFFF


def main() -> None:
    with open_rvt(SRC) as doc:
        logical = doc.logical(PNAME)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        assert not w.errors, w.errors[:3]
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        seg_blocks = [b for b in blocks if b.seq == SEQ]
        seg = bytearray(b"".join(b.data for b in seg_blocks))

        # 1) verify the stamp rule on the first 200 real records
        checked = ok = 0
        for rec in iter_records(bytes(seg), SEQ):
            if rec.elem_id == -1 or rec.body_size < 2:
                continue
            checked += 1
            ok += (stamp_of(seg, rec) == rec.stamp)
            if checked >= 200:
                break
        print(f"stamp rule check: {ok}/{checked} records match adler32(body)")
        assert ok == checked, "stamp rule failed sanity check"

        # 2) find the record containing the title and patch text + stamp
        i = seg.find(OLD)
        assert i >= 0, "title not found in seq-102 segment"
        target = None
        for rec in iter_records(bytes(seg), SEQ):
            start = rec.seg_offset + 16
            end = start + rec.body_size
            if start <= i < end:
                target = rec
                break
        assert target, "containing record not found"
        seg[i:i + len(OLD)] = NEW
        old_stamp = target.stamp
        new_stamp = stamp_of(seg, target)
        struct.pack_into("<I", seg, target.seg_offset + 8, new_stamp)
        print(f"record id={target.elem_id} class=0x{target.class_id:x} psize={target.body_size} "
              f"@seg+{target.seg_offset}; stamp 0x{old_stamp:08x} -> 0x{new_stamp:08x}")

        # 3) split the edited segment back into block payloads (same lengths)
        new_payload = {}
        p = 0
        for b in seg_blocks:
            new_payload[b.index] = bytes(seg[p:p + len(b.data)])
            p += len(b.data)
        assert p == len(seg)

        # 4) re-emit every block (recompress; recompute framing B)
        out = bytearray()
        cursor = 0
        for b in blocks:
            payload = new_payload.get(b.index, b.data)
            out += logical[cursor:b.member_offset]
            hdr_start = len(out) - (b.member_offset - b.hdr_offset)
            gz = gzip_member(payload, level=3, sync_flush=True)
            nb = 8 + len(gz)
            struct.pack_into("<I", out, hdr_start + 10, nb)
            out += gz
            out += struct.pack("<HI", BLOCK_TRL_TAG, nb)
            cursor = b.member_offset + b.member_len + 6
        out += logical[cursor:]
        w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
        assert not w2.errors, w2.errors[:3]
        new_logical = bytes(out[:w2.end_offset + len(w2.end_record)])

    raw = ecc.frame_stream(new_logical)
    entries = [dataclasses.replace(e, data=raw) if (e.entry_type == "stream" and e.path == PNAME) else e
               for e in read_entries(SRC)]
    write_cfb(OUT, entries)
    print(f"V19 written: {OUT} ({os.path.getsize(OUT):,} bytes)")

    # 5) read-back verification incl. re-checking the patched stamp
    with open_rvt(OUT) as d:
        bad = sum(0 if m.crc_ok else 1 for m in d.members(PNAME))
        r = d.raw(PNAME)
        eccbad = sum(1 for k in range(len(r) // ecc.PAGE_STRIDE)
                     if ecc.page_trailer(r[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD])
                     != r[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE])
        wv = StreamWalker(d.logical(PNAME), inflate=True, keep_data=True)
        seg2 = b"".join(b.data for b in sorted(wv.blocks, key=lambda x: x.hdr_offset) if b.seq == SEQ)
        stamps_ok = tot = 0
        for rec in iter_records(seg2, SEQ):
            if rec.elem_id == -1 or rec.body_size < 2:
                continue
            tot += 1
            stamps_ok += (stamp_of(seg2, rec) == rec.stamp)
        print(f"read-back: CRC failures {bad}; ECC mismatches {eccbad}; walker errors {len(wv.errors)}")
        print(f"stamps valid across ALL {tot} seq-102 records: {stamps_ok == tot} ({stamps_ok}/{tot})")
        print(f"new title present: {NEW in seg2}; old present: {OLD in seg2}")


if __name__ == "__main__":
    main()
