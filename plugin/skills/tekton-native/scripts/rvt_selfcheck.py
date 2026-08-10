#!/usr/bin/env python3
"""rvt_selfcheck.py -- the mandatory validation SOP for ANY .rvt we produce.

Run this on every .rvt before it is handed to a human or uploaded to the
Autodesk Viewer. It performs the four self-checks that our proven writer
pipeline is judged against (see SKILL.md "Validation SOP"):

  1. gzip integrity   -- every gzip member of every stream has a valid
                          CRC32/ISIZE trailer after de-paging.
  2. page ECC          -- every FULL 64,896-byte page of every CRCIO-framed
                          stream re-encodes to its stored 353-byte trailer
                          (the code from src/rvt/ecc.py, cracked from
                          Utility.dll CRCIO.cpp). A single mismatch means
                          Autodesk's reader will attempt "repair" / reject.
  3. block walker      -- every Partitions/<N> stream re-frames cleanly:
                          all block headers/trailers parse, `B` fields match,
                          no walker errors, stream end record found.
  4. record stamps     -- every seq-102 element record's u32 stamp equals
                          adler32(u16 class_id + object bytes). (Autodesk's
                          reader does NOT validate stamps -- V18 proved that --
                          but a wrong stamp signals a botched edit, so we
                          treat it as a hygiene FAIL you should investigate.)

The file is judged under ITS OWN release (issue #518, the pattern
rvt_edit.py / rvt_edit_text.py use since #70 / #116): a Revit 2025/2024
project's Partitions/<N> streams are walked with that release's container
class and block/trailer tags, read from ``rvt.partitions`` at call time --
never a module-level copy of the 2026 constants. A native file (every
partition header already parses with the natively bound container class)
enters no context and imports nothing extra, so the common path costs what
it always did. A partition that cannot be walked at all (damaged header,
unknown release) is a walker error and a FAIL verdict, not a traceback.

Exit codes: 0 = all checks pass; 1 = at least one check failed;
2 = not a readable .rvt / CFB container.

Usage (in the plugin: ``python <skill>/scripts/_bootstrap.py run rvt_selfcheck.py ...``):
    python rvt_selfcheck.py path/to/file.rvt [--json out.json] [--max-partition-pages N]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "src"))     # plugin layout

from rvt import ecc  # noqa: E402
from rvt import partitions as P  # noqa: E402
from rvt.container import open_rvt  # noqa: E402
from rvt.native_framing import enter_files_release  # noqa: E402
from rvt.objects import iter_records  # noqa: E402

# Streams stored with NO CRCIO paging (their parsers consume every byte).
UNFRAMED = {"BasicFileInfo", "ProjectInformation", "TransmissionData", "RevitPreview4.0"}


def check_gzip(doc) -> dict:
    total = bad = 0
    per = {}
    for s in doc.streams():
        n = b = 0
        for m in doc.members(s.name):
            n += 1
            b += 0 if m.crc_ok else 1
        if n:
            per[s.name] = {"members": n, "crc_failures": b}
        total += n
        bad += b
    return {"members": total, "crc_failures": bad, "streams": per}


def check_ecc(doc, max_pages: int | None) -> dict:
    tot = bad = 0
    per = {}
    for s in doc.streams():
        name = s.name
        if name in UNFRAMED:
            continue
        raw = doc.raw(name)
        n_full = len(raw) // ecc.PAGE_STRIDE
        limit = n_full if max_pages is None else min(n_full, max_pages)
        b = 0
        for k in range(limit):
            page = raw[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
            tr = raw[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE]
            if ecc.page_trailer(page) != tr:
                b += 1
        if limit:
            per[name] = {"full_pages_checked": limit, "ecc_mismatches": b}
        tot += limit
        bad += b
    return {"full_pages_checked": tot, "ecc_mismatches": bad, "streams": per}


def check_partitions(doc, stamps: bool = True) -> tuple[dict, dict]:
    """The block-walker check and (unless ``stamps`` is False) the adler32
    stamp check of every seq-102 record, from ONE walk per Partitions/<N>
    stream, one partition held at a time. A stream that cannot be walked at
    all (damaged header, unknown release) is one walker error carrying the
    exception text -- a FAIL verdict downstream, never a traceback."""
    out = {}
    errors = checked = ok = 0
    for name in doc.partition_streams():
        try:
            w = P.StreamWalker(doc.logical(name), inflate=True, keep_data=stamps)
        except Exception as e:  # noqa: BLE001 -- the damage judge reports, it does not raise
            out[name] = {"blocks": 0, "walker_errors": 1, "first_errors": [f"{type(e).__name__}: {e}"]}
            errors += 1
            continue
        out[name] = {"blocks": len(w.blocks), "walker_errors": len(w.errors),
                     "first_errors": [str(e) for e in w.errors[:3]]}
        errors += len(w.errors)
        if stamps:
            seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.seq == 102)
            for rec in iter_records(seg, 102):
                if rec.elem_id == -1 or rec.body_size < 2:
                    continue
                body = seg[rec.seg_offset + 16: rec.seg_offset + 16 + rec.body_size]
                checked += 1
                ok += (zlib.adler32(body) & 0xFFFFFFFF) == rec.stamp
    return ({"partitions": out, "walker_errors": errors},
            {"records_checked": checked, "stamps_valid": ok, "stamp_failures": checked - ok})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="the .rvt file to validate")
    ap.add_argument("--json", help="write the full result as JSON to this path")
    ap.add_argument("--max-partition-pages", type=int, default=None,
                    help="cap ECC pages per stream (speed); default = every full page")
    ap.add_argument("--skip-stamps", action="store_true", help="skip the (slow-ish) stamp walk")
    a = ap.parse_args(argv)

    if not os.path.exists(a.path):
        print(f"ERROR: no such file: {a.path}", file=sys.stderr)
        return 2
    try:
        doc = open_rvt(a.path)
    except Exception as e:  # not CFB / not readable
        print(f"ERROR: cannot open as an .rvt container: {e}", file=sys.stderr)
        return 2

    # walk the partitions under the FILE's own release (a native file enters
    # nothing); a file whose release cannot be entered is still checked
    # (release-blind) and fails honestly -- a note, never a raise (#535)
    with contextlib.ExitStack() as stack, doc:
        note = enter_files_release(stack, doc, a.path, host=True)
        if note:
            print(f"warning: {note}", file=sys.stderr)
        gz = check_gzip(doc)
        ec = check_ecc(doc, a.max_partition_pages)
        wk, st = check_partitions(doc, stamps=not a.skip_stamps)
        if a.skip_stamps:
            st["skipped"] = True

    result = {"file": a.path, "size": os.path.getsize(a.path),
              "gzip": gz, "ecc": ec, "walker": wk, "stamps": st}
    fails = []
    if gz["crc_failures"]:
        fails.append(f"gzip CRC failures: {gz['crc_failures']}")
    if ec["ecc_mismatches"]:
        fails.append(f"ECC page mismatches: {ec['ecc_mismatches']} (Autodesk reader will reject)")
    if wk["walker_errors"]:
        fails.append(f"partition walker errors: {wk['walker_errors']}")
    if st.get("stamp_failures"):
        fails.append(f"stale record stamps: {st['stamp_failures']} (hygiene; investigate the edit)")
    if fails and note:          # the verdict explains itself; a note alone never fails a file
        fails.append(f"judged without its release context ({note})")
    result["verdict"] = "FAIL" if fails else "PASS"
    result["failures"] = fails
    if note:
        result["release_note"] = note

    print(f"== rvt_selfcheck: {a.path} ({result['size']:,} bytes) ==")
    print(f"  1 gzip members : {gz['members']} verified, {gz['crc_failures']} CRC failures")
    print(f"  2 page ECC     : {ec['full_pages_checked']} full pages checked, {ec['ecc_mismatches']} mismatches")
    print(f"  3 block walker : {sum(p['blocks'] for p in wk['partitions'].values())} blocks in "
          f"{len(wk['partitions'])} partition stream(s), {wk['walker_errors']} errors")
    if a.skip_stamps:
        print("  4 record stamps: skipped (--skip-stamps)")
    else:
        print(f"  4 record stamps: {st['stamps_valid']}/{st['records_checked']} seq-102 stamps valid")
    print(f"  VERDICT        : {result['verdict']}" + (f"  -> {'; '.join(fails)}" if fails else ""))
    print("  (next gate: upload to viewer.autodesk.com for Autodesk-reader acceptance)")

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        with open(a.json, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"  json           : {a.json}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
