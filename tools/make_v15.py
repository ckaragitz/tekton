#!/usr/bin/env python3
"""V15 — the end-to-end proof: the WHOLE file re-written by us.

Every ECC-framed stream is decompressed, recompressed by our own gzip
(mimicking Revit's zlib level-3 + sync-flush framing), and re-framed with
REAL, RECOMPUTED CRCIO page trailers (src/rvt/ecc.py, the cracked
Foundation/Utility/CRCIO.cpp bit-interleaved CRC-11 code). Unframed metadata
streams (BasicFileInfo, ProjectInformation, TransmissionData, RevitPreview4.0)
are copied byte-for-byte. Uncompressed CONTENT is identical to the original;
every framed byte on disk is produced by our writer.

If Autodesk's Viewer accepts V15, the native writer is proven end-to-end
and only content serialization remains.
"""
import dataclasses
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import ecc  # noqa: E402
from rvt.cfb_writer import write_cfb  # noqa: E402
from rvt.container import open_rvt  # noqa: E402
from rvt.partitions import StreamWalker  # noqa: E402
from rvt.roundtrip import read_entries  # noqa: E402
from rvt.writer import gzip_member, regzip_partition_logical  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "acceptance", "V15_fullfile_real_ecc.rvt")

# Streams stored raw with NO CRCIO paging (verified: their parsers consume
# every byte as content and re-encoding never reproduces a trailer).
UNFRAMED = {"BasicFileInfo", "ProjectInformation", "TransmissionData", "RevitPreview4.0"}


def build_logical_single(doc, name: str) -> bytes:
    """prefix + our gzip member. The block padding is added by ecc.frame_stream."""
    return doc.prefix(name) + gzip_member(doc.inflate(name, 0), level=3, sync_flush=True)


def build_logical_partition(doc, name: str) -> bytes:
    """Recompress every block with consistent framing, then truncate cleanly
    after the stream end record (dropping the old final-block ECC junk that
    the de-pager left in the tail)."""
    logical = regzip_partition_logical(doc, name, level=3)
    w = StreamWalker(logical, inflate=False, keep_data=False)
    if w.errors:
        raise RuntimeError(f"{name}: walker errors after regzip: {w.errors[:3]}")
    end = w.end_offset + len(w.end_record)
    if 0 < end <= len(logical):
        logical = logical[:end]
    return logical


def main() -> None:
    entries = read_entries(SRC)
    new_data = {}
    report = []
    with open_rvt(SRC) as doc:
        for s in doc.streams():
            name = s.name
            if name in UNFRAMED:
                report.append((name, "copied (unframed metadata)", len(doc.raw(name))))
                continue
            members = doc.members(name)
            if not members:
                report.append((name, "copied (no gzip members)", len(doc.raw(name))))
                continue
            if name.startswith("Partitions/"):
                logical = build_logical_partition(doc, name)
                kind = f"partition regzip ({len(members)} blocks)"
            else:
                logical = build_logical_single(doc, name)
                kind = "regzip"
            raw = ecc.frame_stream(logical)
            new_data[name] = raw
            report.append((name, f"{kind} + REAL ECC framing", len(raw)))
    out_entries = [dataclasses.replace(e, data=new_data[e.path])
                   if e.entry_type == "stream" and e.path in new_data else e
                   for e in entries]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_cfb(OUT, out_entries)
    print(f"V15 written: {OUT} ({os.path.getsize(OUT):,} bytes)\n")
    for name, kind, size in report:
        print(f"  {name:32s} {size:>10,}  {kind}")

    # ---- self-verification: read back, CRC-verify members, ECC-verify pages
    print("\n== read-back ==")
    with open_rvt(OUT) as d:
        bad = tot = 0
        for s in d.streams():
            for m in d.members(s.name):
                tot += 1
                bad += 0 if m.crc_ok else 1
        print(f"  gzip members: {tot}, CRC failures: {bad}")
        # ECC-verify every full page of every re-framed stream via re-encoding
        eccbad = ecctot = 0
        for name in new_data:
            raw = d.raw(name)
            n_full = len(raw) // ecc.PAGE_STRIDE
            for k in range(n_full):
                page = raw[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
                tr = raw[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE]
                ecctot += 1
                if ecc.page_trailer(page) != tr:
                    eccbad += 1
        print(f"  full pages ECC self-check: {ecctot} pages, mismatches: {eccbad}")
        # content identity: inflated payloads equal the original's
        with open_rvt(SRC) as o:
            diff = 0
            for name in new_data:
                if name.startswith("Partitions/"):
                    continue
                if d.inflate(name, 0) != o.inflate(name, 0):
                    diff += 1
            print(f"  single-stream inflated payloads differing from original: {diff}")


if __name__ == "__main__":
    main()
