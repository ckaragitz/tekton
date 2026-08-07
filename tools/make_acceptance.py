#!/usr/bin/env python3
"""Build the Autodesk-Viewer acceptance experiment set.

Each variant isolates ONE hypothesis about what Autodesk's reader requires,
so a single upload session in the Autodesk Viewer (viewer.autodesk.com)
tells us exactly which layers of the .rvt format we may write freely.
Base file: the smallest sample (rstbasicsampleproject, 6.7 MB) for fast
uploads. Results decode as follows (record them in docs/acceptance-log.md):

  V0 opens  -> our CFB container writer is accepted by Autodesk's reader.
  V1 opens  -> the 353-byte page trailers are NOT verified against content;
               the writer is UNBLOCKED (any trailer bytes are fine).
  V1 fails, V2 opens -> reader wants plausible trailer bytes but does not
               check them against content; we can copy trailers from donor
               pages -> still UNBLOCKED.
  V1+V2 fail -> trailers ARE verified against page content; we must
               reproduce the ECC algorithm (see docs/streams/09-page-ecc.md).
  V3 vs V1  -> whether tolerance holds when EVERY stream is re-compressed.
  V4        -> whether recompressing the schema stream (Formats/Latest) is
               tolerated - the stream we will regenerate least, useful control.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.container import open_rvt  # noqa: E402
from rvt.roundtrip import roundtrip  # noqa: E402
from rvt.writer import (build_variant, trailer_copy, trailer_random_factory,  # noqa: E402
                        trailer_zero, verify_readback)

SRC = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "acceptance")


def _single_member_gz_streams(path: str):
    """Streams with exactly one gzip member (safe for regzip_logical)."""
    with open_rvt(path) as doc:
        return [s.name for s in doc.streams()
                if len(doc.members(s.name)) == 1 and not s.name.startswith("Partitions/")]


def _partition_names(path: str):
    with open_rvt(path) as doc:
        return doc.partition_streams()


def verify_partitions(orig_path: str, new_path: str, names) -> dict:
    """Re-parse recompressed partitions and prove element data is unchanged.

    For each Partitions/<N>: walk the new file's block framing (must have no
    errors, every block CRC-valid), and compare the concatenated inflated
    payload of each sub-stream seq (101/102/103) against the original's.
    """
    from rvt.partitions import StreamWalker
    out = {}
    with open_rvt(orig_path) as o, open_rvt(new_path) as n:
        for name in names:
            wo = StreamWalker(o.logical(name), inflate=True, keep_data=True)
            wn = StreamWalker(n.logical(name), inflate=True, keep_data=True)
            seqs = sorted({b.seq for b in wo.blocks})
            seq_equal = {}
            for s in seqs:
                a = b"".join(b.data for b in wo.blocks if b.seq == s and b.data)
                b_ = b"".join(b.data for b in wn.blocks if b.seq == s and b.data)
                seq_equal[str(s)] = (a == b_)
            out[name] = {
                "blocks_orig": len(wo.blocks), "blocks_new": len(wn.blocks),
                "walker_errors_new": wn.errors[:5],
                "all_new_crc_ok": all((b.crc_ok is not False) for b in wn.blocks),
                "seq_payload_identical": seq_equal,
                "PASS": (len(wo.blocks) == len(wn.blocks) and not wn.errors
                         and all(seq_equal.values())),
            }
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    log = {}

    # V0: container-writer control (stream-identical round trip).
    p = os.path.join(OUT, "V0_control_roundtrip.rvt")
    roundtrip(SRC, p)
    log["V0_control_roundtrip"] = {"desc": "CFB round-trip; every stream byte-identical to original",
                                    "readback": verify_readback(p)}

    ELEM = ["Global/ElemTable"]  # 72,440 raw -> 2 pages -> one FULL-page trailer + final
    everything = _single_member_gz_streams(SRC)

    # V1: re-gzip ONE multi-page stream, ALL its page trailers zeroed.
    p = os.path.join(OUT, "V1_elemtable_zero_trailers.rvt")
    r = build_variant(SRC, p, ELEM, trailer_zero)
    log["V1_elemtable_zero_trailers"] = {"desc": "Global/ElemTable recompressed by us; its page trailers ZEROED",
                                         "report": r, "readback": verify_readback(p)}

    # V2: same stream, trailers copied verbatim from the original (mismatched vs new content).
    p = os.path.join(OUT, "V2_elemtable_copied_trailers.rvt")
    r = build_variant(SRC, p, ELEM, trailer_copy)
    log["V2_elemtable_copied_trailers"] = {"desc": "Global/ElemTable recompressed; ORIGINAL trailers copied (content mismatch)",
                                           "report": r, "readback": verify_readback(p)}

    # V3: re-gzip EVERY single-member stream, all trailers zeroed.
    p = os.path.join(OUT, "V3_allstreams_zero_trailers.rvt")
    r = build_variant(SRC, p, everything, trailer_zero)
    log["V3_allstreams_zero_trailers"] = {"desc": "ALL single-member streams recompressed; trailers ZEROED",
                                           "streams": everything, "report": r, "readback": verify_readback(p)}

    # V4: re-gzip only the schema stream (Formats/Latest), trailers zeroed.
    p = os.path.join(OUT, "V4_schema_zero_trailers.rvt")
    r = build_variant(SRC, p, ["Formats/Latest"], trailer_zero)
    log["V4_schema_zero_trailers"] = {"desc": "Formats/Latest recompressed; trailers ZEROED",
                                        "report": r, "readback": verify_readback(p)}

    # V5: everything recompressed with RANDOM trailers (garbage that isn't zero).
    p = os.path.join(OUT, "V5_allstreams_random_trailers.rvt")
    r = build_variant(SRC, p, everything, trailer_random_factory())
    log["V5_allstreams_random_trailers"] = {"desc": "ALL single-member streams recompressed; RANDOM trailers",
                                             "report": r, "readback": verify_readback(p)}

    # V6: recompress the ELEMENT DATA stream (Partitions/21) block-by-block,
    #     re-frame its pages fresh, trailers zeroed. Everything else original.
    parts = _partition_names(SRC)
    p = os.path.join(OUT, "V6_partitions_zero_trailers.rvt")
    r = build_variant(SRC, p, [], trailer_zero, partition_streams=parts)
    log["V6_partitions_zero_trailers"] = {"desc": "Partitions/21 (element data) recompressed block-by-block, re-framed; trailers ZEROED",
                                          "report": r, "readback": verify_readback(p),
                                          "partition_check": verify_partitions(SRC, p, parts)}

    # V7: THE WHOLE FILE re-written by our compressor + framer; trailers zeroed.
    #     Uncompressed content bit-identical to original. If this opens, the
    #     writer is proven and only content SERIALIZATION remains.
    p = os.path.join(OUT, "V7_fullfile_zero_trailers.rvt")
    r = build_variant(SRC, p, everything, trailer_zero, partition_streams=parts)
    log["V7_fullfile_zero_trailers"] = {"desc": "EVERY stream (incl. partitions) recompressed + re-framed by us; trailers ZEROED",
                                       "report": r, "readback": verify_readback(p),
                                       "partition_check": verify_partitions(SRC, p, parts)}

    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(log, fh, indent=2)

    print(f"Acceptance set written to {OUT}\n")
    for k, v in log.items():
        rb = v["readback"]
        size = os.path.getsize(os.path.join(OUT, k + ".rvt"))
        print(f"  {k:34s} {size:>10,} B   readback: {rb['members']} members, "
              f"{rb['crc_failures']} CRC failures")
        print(f"     -> {v['desc']}")


if __name__ == "__main__":
    main()
