#!/usr/bin/env python3
"""(Re)build the analysis corpus from the samples, correctly de-paged.

For every stream in every sample writes into extracted/<file>/:
  <Stream>.bin          raw stream bytes as stored (page-framed)
  <Stream>.logical.bin  de-paged logical stream (decode from this)
  <Stream>.gz/NNN.bin   each gzip member of the logical stream, inflated
  <Stream>.gz/index.json  member offsets (logical), consumed, inflated, crc_ok
  manifest.json          per-stream sizes/hashes/head hex

Supersedes tools/scan_gzip.py, which inflated page-framed bytes and produced
silently garbled output past the first 64,896-byte page boundary.
Uses src/rvt/container.py (the canonical, page-framing-aware reader).
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt.container import open_rvt  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples")
OUT = os.path.join(ROOT, "extracted")


def safe(name: str) -> str:
    return name.replace("/", "__")


def main() -> None:
    grand = 0
    for f in sorted(os.listdir(SAMPLES)):
        if not f.lower().endswith(".rvt"):
            continue
        base = os.path.splitext(f)[0]
        d = os.path.join(OUT, base)
        os.makedirs(d, exist_ok=True)
        manifest = {"file": f, "streams": []}
        with open_rvt(os.path.join(SAMPLES, f)) as doc:
            for s in doc.streams():
                stem = os.path.join(d, safe(s.name))
                raw = doc.raw(s.name)
                logical = doc.logical(s.name)
                with open(stem + ".bin", "wb") as fh:
                    fh.write(raw)
                with open(stem + ".logical.bin", "wb") as fh:
                    fh.write(logical)
                members = doc.members(s.name)
                gzdir = stem + ".gz"
                if os.path.isdir(gzdir):
                    shutil.rmtree(gzdir)
                if members:
                    os.makedirs(gzdir)
                    index = []
                    for m, payload in zip(members, doc.inflate_all(s.name)):
                        with open(os.path.join(gzdir, f"{m.index:03d}.bin"), "wb") as fh:
                            fh.write(payload)
                        index.append({"index": m.index, "offset": m.offset, "consumed": m.consumed,
                                      "inflated": m.inflated, "crc_ok": m.crc_ok})
                    with open(os.path.join(gzdir, "index.json"), "w") as fh:
                        json.dump({"source": safe(s.name) + ".logical.bin", "logical_size": len(logical),
                                   "members": index}, fh, indent=2)
                    grand += len(members)
                manifest["streams"].append({
                    "name": s.name, "raw_size": len(raw), "logical_size": len(logical),
                    "sha256_logical": hashlib.sha256(logical).hexdigest(),
                    "head_hex": logical[:64].hex(), "members": len(members),
                    "all_crc_ok": all(m.crc_ok for m in members),
                })
        with open(os.path.join(d, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)
        print(f"{base}: {len(manifest['streams'])} streams")
    print(f"\nTOTAL gzip members carved (all CRC-verified): {grand}")


if __name__ == "__main__":
    main()
