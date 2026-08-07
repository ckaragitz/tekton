#!/usr/bin/env python3
"""Batch 2 — separate H-ECC (trailers verified/repair) from H-COMP (our
deflate rejected). Batch 1 conflated them; each variant here changes ONE
variable. Base: rstbasicsampleproject.rvt.

  V8  orig compressed bytes, Global/ElemTable full-page trailers ZEROED.
      Only trailer bytes change. FAIL => trailers matter (H-ECC). PASS =>
      trailers ignored, so Batch-1 failures were the recompression (H-COMP).
  V9  orig everything, ONE trailer byte flipped (ElemTable page 0).
      Minimal-damage sensitivity / auto-repair probe.
  V10 recompress ONLY Global/History — a SUB-PAGE stream (17,144 B, no
      full-page trailers exist), original short tail preserved. Isolates
      pure compression compatibility: PASS => Autodesk's inflater accepts
      our deflate (H-COMP dead); FAIL => our deflate framing is rejected.
  V11 same as V10 but tail region zeroed too (does the SHORT final trailer
      matter?).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.writer import (corrupt_trailer_bytes, regzip_streams_variant,  # noqa: E402
                        verify_readback, zero_full_trailers_only)

SRC = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "acceptance")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    log = {}

    p = os.path.join(OUT, "V8_origbytes_zero_trailers.rvt")
    r = zero_full_trailers_only(SRC, p, ["Global/ElemTable"])
    log["V8_origbytes_zero_trailers"] = {"desc": "ElemTable compressed bytes UNTOUCHED (Revit's own); only its full-page trailers zeroed",
                                        "report": r, "readback": verify_readback(p)}

    p = os.path.join(OUT, "V9_one_trailer_byte_flipped.rvt")
    r = corrupt_trailer_bytes(SRC, p, "Global/ElemTable", page=0, count=1)
    log["V9_one_trailer_byte_flipped"] = {"desc": "Everything original; ONE byte flipped in ElemTable's page-0 trailer",
                                          "report": r, "readback": verify_readback(p)}

    p = os.path.join(OUT, "V10_history_regzip_keeptail.rvt")
    r = regzip_streams_variant(SRC, p, ["Global/History"], keep_tail_bytes=128)
    log["V10_history_regzip_keeptail"] = {"desc": "ONLY Global/History (sub-page, no full trailers) recompressed by us; original short tail kept",
                                         "report": r, "readback": verify_readback(p)}

    p = os.path.join(OUT, "V11_history_regzip_zerotail.rvt")
    r = regzip_streams_variant(SRC, p, ["Global/History"], keep_tail_bytes=0)
    log["V11_history_regzip_zerotail"] = {"desc": "ONLY Global/History recompressed; tail (incl. short trailer) zeroed",
                                         "report": r, "readback": verify_readback(p)}

    with open(os.path.join(OUT, "batch2_manifest.json"), "w") as fh:
        json.dump(log, fh, indent=2)
    print("Batch 2 written:")
    for k, v in log.items():
        rb = v["readback"]
        print(f"  {k:34s} {os.path.getsize(os.path.join(OUT, k + '.rvt')):>10,} B  "
              f"{rb['members']} members, {rb['crc_failures']} CRC failures\n     -> {v['desc']}")


if __name__ == "__main__":
    main()
