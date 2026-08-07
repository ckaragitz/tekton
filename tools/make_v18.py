#!/usr/bin/env python3
"""V18 — the FIRST AUTHORED CHANGE: our own text on Autodesk's rendered sheet.

The cover-sheet title lives in a seq-102 element record as an RTF blob
("...\\fs143 Autodesk  Revit\\par / Basic Structural Sample Project\\par").
We replace 'Basic Structural Sample Project' (31 chars) with a 31-char
string of ours — a SIZE-PRESERVING content edit — then re-emit the whole
Partitions/21 stream through OUR pipeline: recompress every block
(recomputing the framing 'B' fields), re-frame with real CRCIO ECC, and
rebuild the compound file. If the viewer renders our title, we have
authored our first change into a native .rvt.
"""
import dataclasses
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import ecc  # noqa: E402
from rvt.cfb_writer import write_cfb  # noqa: E402
from rvt.container import open_rvt  # noqa: E402
from rvt.partitions import StreamWalker  # noqa: E402
from rvt.roundtrip import read_entries  # noqa: E402
from rvt.writer import BLOCK_TRL_TAG, gzip_member  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "acceptance", "V18_first_authored_change.rvt")
PNAME = "Partitions/21"

OLD = b"Basic Structural Sample Project"
NEW = b"REV-REVIT WROTE THIS RVT FILE!!"
assert len(OLD) == len(NEW) == 31, (len(OLD), len(NEW))
TARGET_SEQ = 102


def build_edited_partition(doc) -> tuple[bytes, dict]:
    logical = doc.logical(PNAME)
    w = StreamWalker(logical, inflate=True, keep_data=True)
    assert not w.errors, w.errors[:3]
    blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)

    # locate the string inside the seq-102 segment, then map to its block
    seg_off = 0
    hit = None
    for b in blocks:
        if b.seq != TARGET_SEQ:
            continue
        idx = b.data.find(OLD)
        if idx >= 0:
            hit = (b, idx, seg_off + idx)
            break
        seg_off += len(b.data)
    assert hit, "title string not found in any seq-102 block"
    tblock, tidx, sabs = hit
    info = {"block_index": tblock.index, "offset_in_block": tidx,
            "abs_seq_offset": sabs, "block_flags": tblock.flags}

    out = bytearray()
    cursor = 0
    for b in blocks:
        payload = b.data
        if b is tblock:
            payload = payload[:tidx] + NEW + payload[tidx + len(OLD):]
            assert len(payload) == len(b.data)
        out += logical[cursor:b.member_offset]
        hdr_start = len(out) - (b.member_offset - b.hdr_offset)
        gz = gzip_member(payload, level=3, sync_flush=True)
        new_b = 8 + len(gz)
        struct.pack_into("<I", out, hdr_start + 10, new_b)
        out += gz
        out += struct.pack("<HI", BLOCK_TRL_TAG, new_b)
        cursor = b.member_offset + b.member_len + 6
    out += logical[cursor:]
    # truncate cleanly after the stream end record
    w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
    assert not w2.errors, w2.errors[:3]
    end = w2.end_offset + len(w2.end_record)
    return bytes(out[:end]), info


def main() -> None:
    with open_rvt(SRC) as doc:
        logical, info = build_edited_partition(doc)
    print(f"edit: block {info['block_index']} (seq {TARGET_SEQ}, flags {info['block_flags']}), "
          f"offset {info['offset_in_block']} in block, {info['abs_seq_offset']} in segment")
    raw = ecc.frame_stream(logical)
    entries = [dataclasses.replace(e, data=raw) if (e.entry_type == "stream" and e.path == PNAME) else e
               for e in read_entries(SRC)]
    write_cfb(OUT, entries)
    print(f"V18 written: {OUT} ({os.path.getsize(OUT):,} bytes)")

    # ---- verification: read back, CRC, ECC, and confirm the new text
    with open_rvt(OUT) as d:
        mems = d.members(PNAME)
        bad = sum(0 if m.crc_ok else 1 for m in mems)
        r = d.raw(PNAME)
        eccbad = sum(1 for k in range(len(r) // ecc.PAGE_STRIDE)
                     if ecc.page_trailer(r[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD])
                     != r[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE])
        w = StreamWalker(d.logical(PNAME), inflate=True, keep_data=True)
        seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.seq == TARGET_SEQ)
        print(f"read-back: {len(mems)} members, {bad} CRC failures; ECC page mismatches: {eccbad}; "
              f"walker errors: {len(w.errors)}")
        print(f"new text present: {NEW in seg}; old text present: {OLD in seg}")
        i = seg.find(NEW)
        print(f"context: {seg[max(0, i - 60):i + 40]!r}")


if __name__ == "__main__":
    main()
