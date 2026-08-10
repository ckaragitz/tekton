#!/usr/bin/env python3
"""rvt_edit_text.py -- the PROVEN authored-content-change recipe (V18/V19).

This is the exact pipeline that put our text on Autodesk's rendered title
sheet (docs/acceptance-log.md, batch 4). It performs a SIZE-PRESERVING text
edit inside a seq-102 element record of a Partitions/<N> stream and re-emits
the whole file through the real writer:

    decode segment  -> find the containing record  -> edit bytes
    -> record stamp = adler32(u16 class_id + object bytes)   (recomputed)
    -> re-block (recompress each block: zlib level 3 + sync-flush,
                 recompute the framing `B` field and its trailer mirror)
    -> truncate cleanly at the stream end record
    -> ecc.frame_stream(logical)        (real CRCIO page trailers)
    -> write_cfb(...)                    (rebuild the compound file)

Then it READS THE OUTPUT BACK and runs the self-checks (CRC, ECC, walker,
stamp) before declaring success -- the same gate rvt_selfcheck.py applies.

The whole job runs under the INPUT file's own release (issue #116, the
pattern rvt_edit.py uses since #70): a Revit 2025/2024 project is walked
and re-framed with its release's block/trailer tags, read from
``rvt.partitions`` at call time -- never a module-level copy of the 2026
tag. The output keeps the input's release.

The edit is SIZE-PRESERVING on purpose: same byte length keeps every
record `psize`, every block boundary and every id offset valid without
touching the ElemTable / increment bookkeeping. Growing a record is a
different, larger operation (element records must be re-framed and the
save recorded) -- do not fake it by padding: use the element-creation API.

Usage (in the plugin: ``python <skill>/scripts/_bootstrap.py run rvt_edit_text.py ...``):
    python rvt_edit_text.py in.rvt --old "OLD TEXT" --new "NEW TEXT" -o out.rvt
        [--utf16] [--seq 102] [--partition Partitions/21]

  --utf16   the target string is stored as UTF-16LE (most Revit text: names,
            titles). Default ASCII/UTF-8 (e.g. the RTF blob used by V18).
  Both spellings are tried automatically if the exact one is not found.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "src"))     # plugin layout

from rvt import ecc  # noqa: E402
from rvt import partitions as P  # noqa: E402
from rvt.cfb_writer import write_cfb  # noqa: E402
from rvt.container import open_rvt  # noqa: E402
from rvt.frontdoor.release_ctx import enter_host_release  # noqa: E402
from rvt.objects import iter_records  # noqa: E402
from rvt.roundtrip import read_entries  # noqa: E402
from rvt.writer import gzip_member  # noqa: E402

HDR102 = 16   # seq 102/103 record header: i64 id + u32 stamp + u32 psize


def stamp_of(seg: bytes, rec) -> int:
    body = seg[rec.seg_offset + HDR102: rec.seg_offset + HDR102 + rec.body_size]
    return zlib.adler32(body) & 0xFFFFFFFF


def find_partition(doc, prefer: str | None) -> str:
    names = doc.partition_streams()
    if prefer:
        if prefer not in names:
            raise SystemExit(f"partition {prefer!r} not in file (have {names})")
        return prefer
    if len(names) != 1:
        raise SystemExit(f"file has {len(names)} partition streams {names}; pass --partition")
    return names[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="input .rvt (never modified)")
    ap.add_argument("--old", required=True, help="text to replace")
    ap.add_argument("--new", required=True, help="replacement text (must be the SAME length)")
    ap.add_argument("-o", "--output", required=True, help="output .rvt path")
    ap.add_argument("--utf16", action="store_true", help="treat the text as UTF-16LE (default ascii/utf-8)")
    ap.add_argument("--seq", type=int, default=102, help="record stream to edit (default 102)")
    ap.add_argument("--partition", default=None, help="e.g. Partitions/21 (auto if only one)")
    a = ap.parse_args(argv)

    enc = "utf-16-le" if a.utf16 else "utf-8"
    old_b, new_b = a.old.encode(enc), a.new.encode(enc)
    if len(old_b) != len(new_b):
        print(f"ERROR: size-preserving edit required: old={len(old_b)}B new={len(new_b)}B.\n"
              "  Pad your replacement to the same character count, or use the element-creation\n"
              "  API for a real content change (see SKILL.md).", file=sys.stderr)
        return 2
    if not os.path.isfile(a.path):
        ap.error(f"input .rvt not found: {a.path}")
    try:
        doc = open_rvt(a.path)
    except Exception as e:  # not CFB / not readable
        print(f"ERROR: cannot open as an .rvt container: {e}", file=sys.stderr)
        return 2

    # walk, edit, re-frame AND read back under the INPUT file's own release
    with contextlib.ExitStack() as stack:
        note = enter_host_release(stack, a.path)
        if note:
            print(f"warning: {note}", file=sys.stderr)
        return _edit(a, doc, old_b, new_b)


def _edit(a: argparse.Namespace, doc, old_b: bytes, new_b: bytes) -> int:
    with doc:
        pname = find_partition(doc, a.partition)
        logical = doc.logical(pname)
        try:
            w = P.StreamWalker(logical, inflate=True, keep_data=True)
        except Exception as e:  # noqa: BLE001 -- a header no release in force parses: refuse, never trace back
            print(f"ERROR: input partition does not walk cleanly: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        if w.errors:
            print(f"ERROR: input partition does not walk cleanly: {w.errors[:3]}", file=sys.stderr)
            return 2
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        seg_blocks = [b for b in blocks if b.seq == a.seq]
        seg = bytearray(b"".join(b.data for b in seg_blocks))

        i = seg.find(old_b)
        if i < 0:
            # try the other encoding automatically
            alt = a.old.encode("utf-16-le" if not a.utf16 else "utf-8")
            j = seg.find(alt)
            if j >= 0:
                print(f"note: found the text as {'utf-16-le' if not a.utf16 else 'utf-8'}; using that")
                old_b, new_b, i = alt, a.new.encode("utf-16-le" if not a.utf16 else "utf-8"), j
                if len(old_b) != len(new_b):
                    print("ERROR: size mismatch after encoding switch", file=sys.stderr)
                    return 2
            else:
                print(f"ERROR: text {a.old!r} not found in seq-{a.seq} of {pname} "
                      f"(tried utf-8 and utf-16-le).", file=sys.stderr)
                return 2

        # locate the containing record; recompute its stamp after the edit
        target = None
        for rec in iter_records(bytes(seg), a.seq):
            start = rec.seg_offset + HDR102
            if start <= i < start + rec.body_size:
                target = rec
                break
        seg[i:i + len(old_b)] = new_b
        if target is None or target.elem_id == -1:
            print("WARNING: containing record not found; editing bytes without a stamp update")
        elif a.seq in (102, 103):
            old_stamp = target.stamp
            new_stamp = stamp_of(seg, target)
            struct.pack_into("<I", seg, target.seg_offset + 8, new_stamp)
            print(f"record id={target.elem_id} class=0x{target.class_id:x} psize={target.body_size} "
                  f"@seg+{target.seg_offset}: stamp 0x{old_stamp:08x} -> 0x{new_stamp:08x}")

        # split the edited segment back into block payloads (identical lengths)
        payloads, p = {}, 0
        for b in seg_blocks:
            payloads[b.index] = bytes(seg[p:p + len(b.data)])
            p += len(b.data)
        assert p == len(seg)

        # re-emit every block: recompress, recompute framing B (+ mirror trailer)
        out = bytearray()
        cursor = 0
        for b in blocks:
            payload = payloads.get(b.index, b.data)
            out += logical[cursor:b.member_offset]
            hdr_start = len(out) - (b.member_offset - b.hdr_offset)
            gz = gzip_member(payload, level=3, sync_flush=True)
            nb = 8 + len(gz)
            struct.pack_into("<I", out, hdr_start + 10, nb)
            out += gz
            out += struct.pack("<HI", P.TRAILER_TAG, nb)
            cursor = b.member_offset + b.member_len + 6
        out += logical[cursor:]
        w2 = P.StreamWalker(bytes(out), inflate=False, keep_data=False)
        if w2.errors:
            print(f"ERROR: re-framed partition does not walk: {w2.errors[:3]}", file=sys.stderr)
            return 1
        new_logical = bytes(out[:w2.end_offset + len(w2.end_record)])

    raw = ecc.frame_stream(new_logical)          # real CRCIO page trailers
    entries = [dataclasses.replace(e, data=raw)
               if (e.entry_type == "stream" and e.path == pname) else e
               for e in read_entries(a.path)]
    os.makedirs(os.path.dirname(os.path.abspath(a.output)) or ".", exist_ok=True)
    write_cfb(a.output, entries)
    print(f"written: {a.output} ({os.path.getsize(a.output):,} bytes)")

    # ---- read back through the same gate as rvt_selfcheck.py ----
    with open_rvt(a.output) as d:
        crc_bad = sum(0 if m.crc_ok else 1 for m in d.members(pname))
        r = d.raw(pname)
        ecc_bad = sum(1 for k in range(len(r) // ecc.PAGE_STRIDE)
                      if ecc.page_trailer(r[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD])
                      != r[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE])
        wv = P.StreamWalker(d.logical(pname), inflate=True, keep_data=True)
        seg2 = b"".join(b.data for b in sorted(wv.blocks, key=lambda x: x.hdr_offset) if b.seq == a.seq)
        tot = okc = 0
        if a.seq in (102, 103):
            for rec in iter_records(seg2, a.seq):
                if rec.elem_id == -1 or rec.body_size < 2:
                    continue
                tot += 1
                okc += (stamp_of(seg2, rec) == rec.stamp)
        print(f"read-back: CRC failures {crc_bad}; ECC mismatches {ecc_bad}; "
              f"walker errors {len(wv.errors)}")
        if tot:
            print(f"read-back: seq-{a.seq} stamps valid {okc}/{tot} ({'OK' if okc == tot else 'STALE'})")
        print(f"read-back: new text present {new_b in seg2}; old text present {old_b in seg2}")
        ok = crc_bad == 0 and ecc_bad == 0 and not wv.errors and (tot == 0 or okc == tot) and new_b in seg2
    print(("SELF-CHECK PASS -> next gate: Autodesk Viewer acceptance" if ok
           else "SELF-CHECK FAIL -> do not deliver; see counts above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
