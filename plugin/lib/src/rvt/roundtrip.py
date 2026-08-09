"""Round-trip an existing .rvt (or any CFB file) through :mod:`rvt.cfb_writer`.

Read side uses ``olefile`` (already the project's reader); the write side is
our own pure-Python CFB writer. Directory order, storage tree, CLSIDs, state
bits and creation/modified FILETIMEs are carried over unchanged; only the
physical sector layout, the red/black sibling links and slack bytes are
regenerated (see docs/streams/00-cfb-container.md).

CLI::

    python -m rvt.roundtrip <in.rvt> <out.rvt> [--verify] [--byte-report]
    python -m rvt.roundtrip --params <file.rvt> [...]     # CFB parameter table

``--verify`` reopens BOTH files and asserts identical stream paths, identical
bytes for every stream and identical CLSIDs / state bits / timestamps.
``--byte-report`` states whether the output is byte-identical to the input and,
if not, categorises the differences.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import time
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

import olefile

from .cfb_writer import (
    CfbEntry,
    CfbLayout,
    clsid_to_str,
    write_cfb,
)

ENTRY_TYPES = {
    olefile.STGTY_ROOT: "root",
    olefile.STGTY_STORAGE: "storage",
    olefile.STGTY_STREAM: "stream",
    olefile.STGTY_EMPTY: "unallocated",
}


# --- reading ------------------------------------------------------------------

def _sid_paths(ole: olefile.OleFileIO) -> Dict[int, str]:
    """Map stream-id -> '/'-joined path by walking the storage tree."""
    paths: Dict[int, str] = {0: ""}

    def walk(node, prefix: str) -> None:
        for kid in node.kids:
            p = kid.name if not prefix else prefix + "/" + kid.name
            paths[kid.sid] = p
            if kid.kids or kid.entry_type == olefile.STGTY_STORAGE:
                walk(kid, p)

    walk(ole.root, "")
    return paths


def _iter_direntries(ole: olefile.OleFileIO):
    """Yield every allocated directory entry in stream-id order."""
    for sid in range(len(ole.direntries)):
        e = ole.direntries[sid]
        if e is None:
            try:
                e = ole._load_direntry(sid)      # unreachable-but-allocated entries
            except Exception:
                continue
        if e is None or e.entry_type == olefile.STGTY_EMPTY:
            continue
        yield e


def read_entries(path: str, *, with_data: bool = True) -> List[CfbEntry]:
    """Read every directory entry (in original stream-id order) via olefile.

    ``with_data=False`` skips stream bytes (fast metadata-only pass).
    """
    entries: List[CfbEntry] = []
    with olefile.OleFileIO(path) as ole:
        paths = _sid_paths(ole)
        for e in _iter_direntries(ole):
            etype = ENTRY_TYPES.get(e.entry_type, "unknown")
            if e.sid not in paths and etype != "root":
                # orphaned entry (not reachable from any storage tree): keep it
                # under the root with its raw name so nothing is silently lost.
                paths[e.sid] = e.name
            p = "" if etype == "root" else paths[e.sid]
            data = b""
            if etype == "stream" and with_data and e.size:
                data = ole.openstream(p.split("/")).read()
            entries.append(CfbEntry(
                path=p,
                entry_type=etype,
                data=data,
                clsid=e.clsid,               # '' for CLSID_NULL
                state_bits=e.dwUserFlags,
                ctime=e.createTime,
                mtime=e.modifyTime,
            ))
    return entries


# --- catalog: metadata + per-stream digests --------------------------------------

def _read_header_fields(path: str) -> Dict[str, object]:
    """Parse the raw 512-byte CFB header ([MS-CFB] 2.2)."""
    with open(path, "rb") as f:
        hdr = f.read(512)
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
    minor, major = struct.unpack_from("<HH", hdr, 0x18)
    byte_order, sector_shift, mini_shift = struct.unpack_from("<HHH", hdr, 0x1C)
    (n_dir, n_fat, first_dir, txsig, cutoff, first_minifat, n_minifat,
     first_difat, n_difat) = struct.unpack_from("<9I", hdr, 0x28)
    return {
        "signature": hdr[:8].hex(),
        "header_clsid": hdr[8:24].hex(),
        "minor_version": minor,
        "major_version": major,
        "byte_order": byte_order,
        "sector_size": 1 << sector_shift,
        "mini_sector_size": 1 << mini_shift,
        "reserved_zero": hdr[0x22:0x28] == b"\x00" * 6,
        "num_dir_sectors": n_dir,
        "num_fat_sectors": n_fat,
        "first_dir_sector": first_dir,
        "transaction_signature": txsig,
        "mini_stream_cutoff": cutoff,
        "first_minifat_sector": first_minifat,
        "num_minifat_sectors": n_minifat,
        "first_difat_sector": first_difat,
        "num_difat_sectors": n_difat,
        "file_size": file_size,
        "num_sectors_after_header": (file_size - (1 << sector_shift if major == 4 else 512)) // (1 << sector_shift),
    }


def catalog(path: str, *, hash_streams: bool = True) -> Dict[str, object]:
    """Header parameters + every directory entry (order preserved) + digests."""
    header = _read_header_fields(path)
    rows: List[Dict[str, object]] = []
    with olefile.OleFileIO(path) as ole:
        paths = _sid_paths(ole)
        for e in _iter_direntries(ole):
            etype = ENTRY_TYPES.get(e.entry_type, "unknown")
            p = "" if etype == "root" else paths.get(e.sid, e.name)
            row = {
                "sid": e.sid,
                "path": p,
                "name": e.name,
                "type": etype,
                "color": "black" if e.color else "red",
                "left": None if e.sid_left == 0xFFFFFFFF else e.sid_left,
                "right": None if e.sid_right == 0xFFFFFFFF else e.sid_right,
                "child": None if e.sid_child == 0xFFFFFFFF else e.sid_child,
                "clsid": e.clsid,
                "state_bits": e.dwUserFlags,
                "ctime": e.createTime,
                "mtime": e.modifyTime,
                "start": e.isectStart,
                "size": e.size,
            }
            if etype == "stream" and hash_streams:
                h = hashlib.sha256()
                if e.size:
                    h.update(ole.openstream(p.split("/")).read())
                row["sha256"] = h.hexdigest()
            rows.append(row)
        header["mini_stream_size"] = ole.root.size
        header["num_entries"] = len(rows)
    return {"file": os.path.abspath(path), "header": header, "entries": rows}


# --- round trip -----------------------------------------------------------------

def roundtrip(in_path: str, out_path: str) -> Tuple[CfbLayout, float, float]:
    """Read ``in_path`` fully and re-emit it as ``out_path``.

    Returns (layout, read_seconds, write_seconds).
    """
    t0 = time.time()
    entries = read_entries(in_path)
    t1 = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    layout = write_cfb(out_path, entries)
    t2 = time.time()
    return layout, t1 - t0, t2 - t1


# --- verification ---------------------------------------------------------------

class VerifyResult(NamedTuple):
    """``problems``: real mismatches / reader rejections (empty == identical
    content). ``notes``: informational only (e.g. the optional second reader
    is not installed), never a difference. Truthy iff ``problems`` — so
    ``if verify_pair(a, b):`` still means "differs"; compare ``.problems``,
    not the result, against ``[]``."""
    problems: List[str]
    notes: List[str]

    def __bool__(self) -> bool:
        return bool(self.problems)


def verify_pair(orig_path: str, new_path: str) -> VerifyResult:
    """Assert stream-level equality of two CFB files; returns
    ``VerifyResult(problems, notes)``.

    Checks: identical ordered set of paths/types, identical size + sha256 for
    every stream, identical CLSIDs, state bits and creation/modified FILETIMEs
    for every entry (root included), and that the copy parses with olefile at
    the strict DEFECT_INCORRECT level.
    """
    problems: List[str] = []
    notes: List[str] = []

    # strict re-parse of the output first
    try:
        with olefile.OleFileIO(new_path, raise_defects=olefile.DEFECT_INCORRECT) as ole:
            for d in ole.parsing_issues:
                problems.append(f"olefile parsing issue in output: {d}")
    except Exception as exc:  # pragma: no cover - reported, not raised
        problems.append(f"olefile could not parse output at DEFECT_INCORRECT: {exc!r}")
        return VerifyResult(problems, notes)

    a = catalog(orig_path)
    b = catalog(new_path)
    ea = a["entries"]
    eb = b["entries"]

    if len(ea) != len(eb):
        problems.append(f"entry count differs: {len(ea)} vs {len(eb)}")
    pa = [(r["path"], r["type"]) for r in ea]
    pb = [(r["path"], r["type"]) for r in eb]
    if pa != pb:
        problems.append("directory entry order/paths differ:\n"
                        f"  orig: {pa}\n  new : {pb}")
    if {p for p, _ in pa} != {p for p, _ in pb}:
        problems.append("set of stream/storage paths differs")

    by_path_b = {r["path"]: r for r in eb}
    for ra in ea:
        rb = by_path_b.get(ra["path"])
        if rb is None:
            problems.append(f"missing in output: {ra['path'] or '(root)'}")
            continue
        who = ra["path"] or "(root)"
        if ra["type"] != rb["type"]:
            problems.append(f"{who}: type {ra['type']} vs {rb['type']}")
        if ra["type"] == "stream":
            if ra["size"] != rb["size"]:
                problems.append(f"{who}: size {ra['size']} vs {rb['size']}")
            if ra.get("sha256") != rb.get("sha256"):
                problems.append(f"{who}: stream bytes differ (sha256)")
        if ra["clsid"] != rb["clsid"]:
            problems.append(f"{who}: clsid {ra['clsid']!r} vs {rb['clsid']!r}")
        if ra["state_bits"] != rb["state_bits"]:
            problems.append(f"{who}: state bits {ra['state_bits']:#x} vs {rb['state_bits']:#x}")
        if ra["ctime"] != rb["ctime"]:
            problems.append(f"{who}: ctime {ra['ctime']} vs {rb['ctime']}")
        if ra["mtime"] != rb["mtime"]:
            problems.append(f"{who}: mtime {ra['mtime']} vs {rb['mtime']}")

    # cross-check with the independent 'compoundfiles' reader if installed:
    # its absence is a note; its refusing our output is a problem
    try:
        second = _verify_with_compoundfiles(a, new_path)
    except Exception as exc:                                   # noqa: BLE001
        second = [f"compoundfiles could not read output: {exc!r}"]
    if second is None:
        notes.append("(compoundfiles cross-check skipped: reader not installed)")
    else:
        problems.extend(second)
    return VerifyResult(problems, notes)


def _verify_with_compoundfiles(orig_catalog: Dict[str, object],
                               new_path: str) -> Optional[List[str]]:
    """Read the OUTPUT with the independent ``compoundfiles`` package and make
    sure it sees the same tree and stream sizes; also surface any structural
    warnings it emits. ``None`` == the package is not installed (no verdict)."""
    import importlib.util
    import warnings
    if importlib.util.find_spec("compoundfiles") is None:
        return None
    from compoundfiles import CompoundFileReader           # type: ignore

    problems: List[str] = []
    expected = {r["path"]: r for r in orig_catalog["entries"] if r["type"] != "root"}
    seen: Dict[str, int] = {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reader = CompoundFileReader(new_path)

        def walk(node, prefix: str) -> None:
            for ent in node:
                p = ent.name if not prefix else prefix + "/" + ent.name
                seen[p] = -1 if ent.isdir else ent.size
                if ent.isdir:
                    walk(ent, p)

        walk(reader.root, "")
        reader.close()
    for w in caught:
        problems.append(f"compoundfiles warning on output: {w.category.__name__}: {w.message}")
    for p, r in expected.items():
        if p not in seen:
            problems.append(f"compoundfiles: missing {p}")
        elif r["type"] == "stream" and seen[p] != r["size"]:
            problems.append(f"compoundfiles: {p} size {seen[p]} vs {r['size']}")
    extra = set(seen) - set(expected)
    for p in sorted(extra):
        problems.append(f"compoundfiles: unexpected entry {p}")
    return problems


# --- byte-level diff categorisation ------------------------------------------------

def byte_diff_report(orig_path: str, new_path: str) -> Dict[str, object]:
    """Is ``new`` byte-identical to ``orig``? If not, say WHY, by category.

    Categories reported:
      * ``file size``          - sizes differ
      * ``header fields``      - version/sector size/FAT-DIFAT-dir counts/etc.
      * ``directory order``    - the (path, type) sequence by stream id
      * ``directory tree``     - red/black colours and sibling/child links
      * ``sector layout``      - starting sectors / chain placement
      * ``timestamps`` / ``clsids`` / ``state bits`` - per-entry metadata
      * ``padding / slack``    - non-zero slack bytes in the last sector of a
                                  stream in the original (we always zero-fill)
    """
    same = _files_identical(orig_path, new_path)
    report: Dict[str, object] = {"byte_identical": same, "categories": {}}
    if same:
        return report
    cats: Dict[str, List[str]] = {}

    a = catalog(orig_path, hash_streams=False)
    b = catalog(new_path, hash_streams=False)
    ha, hb = a["header"], b["header"]

    if ha["file_size"] != hb["file_size"]:
        cats["file size"] = [f"orig {ha['file_size']:,} B vs new {hb['file_size']:,} B "
                             f"({ha['num_sectors_after_header']} vs {hb['num_sectors_after_header']} sectors)"]

    hdr_diffs = []
    for k in ("major_version", "minor_version", "sector_size", "mini_sector_size",
              "num_dir_sectors", "num_fat_sectors", "num_minifat_sectors",
              "num_difat_sectors", "first_dir_sector", "first_minifat_sector",
              "first_difat_sector", "transaction_signature", "mini_stream_cutoff",
              "mini_stream_size", "num_entries"):
        if ha.get(k) != hb.get(k):
            hdr_diffs.append(f"{k}: {ha.get(k)} vs {hb.get(k)}")
    if hdr_diffs:
        cats["header fields"] = hdr_diffs

    ea, eb = a["entries"], b["entries"]
    pa = [(r["path"], r["type"]) for r in ea]
    pb = [(r["path"], r["type"]) for r in eb]
    if pa != pb:
        cats["directory order"] = [f"orig {pa}", f"new  {pb}"]

    tree_diffs, layout_diffs, ts_diffs, cls_diffs, state_diffs = [], [], [], [], []
    by_path_b = {r["path"]: r for r in eb}
    for ra in ea:
        rb = by_path_b.get(ra["path"])
        if rb is None:
            continue
        who = ra["path"] or "(root)"
        for k in ("color", "left", "right", "child"):
            if ra[k] != rb[k]:
                tree_diffs.append(f"{who}.{k}: {ra[k]} vs {rb[k]}")
        if ra["type"] in ("stream", "root") and ra["start"] != rb["start"]:
            layout_diffs.append(f"{who}.start_sector: {ra['start']} vs {rb['start']}")
        if ra["ctime"] != rb["ctime"] or ra["mtime"] != rb["mtime"]:
            ts_diffs.append(f"{who}: ({ra['ctime']},{ra['mtime']}) vs ({rb['ctime']},{rb['mtime']})")
        if ra["clsid"] != rb["clsid"]:
            cls_diffs.append(f"{who}: {ra['clsid']!r} vs {rb['clsid']!r}")
        if ra["state_bits"] != rb["state_bits"]:
            state_diffs.append(f"{who}: {ra['state_bits']:#x} vs {rb['state_bits']:#x}")
    if tree_diffs:
        cats["directory tree"] = tree_diffs
    if layout_diffs:
        cats["sector layout"] = layout_diffs
    if ts_diffs:
        cats["timestamps"] = ts_diffs
    if cls_diffs:
        cats["clsids"] = cls_diffs
    if state_diffs:
        cats["state bits"] = state_diffs

    slack = _slack_report(orig_path, a)
    if slack:
        cats["padding / slack"] = slack

    report["categories"] = cats
    return report


def _files_identical(p1: str, p2: str) -> bool:
    if os.path.getsize(p1) != os.path.getsize(p2):
        return False
    with open(p1, "rb") as f1, open(p2, "rb") as f2:
        while True:
            b1 = f1.read(1 << 20)
            b2 = f2.read(1 << 20)
            if b1 != b2:
                return False
            if not b1:
                return True


def _slack_report(path: str, cat: Dict[str, object]) -> List[str]:
    """Report streams in ``path`` whose last sector carries non-zero slack
    bytes (data past the declared stream size). Our writer zero-fills slack
    ([MS-CFB] 2.7 'SHOULD be filled with zeroes'), so this always differs when
    the source writer leaked buffer garbage."""
    out: List[str] = []
    try:
        with olefile.OleFileIO(path) as ole:
            fat = ole.fat
            ss = ole.sector_size
            with open(path, "rb") as f:
                for r in cat["entries"]:
                    if r["type"] != "stream" or r["size"] < 4096:
                        continue
                    nsect = -(-r["size"] // ss)
                    sect = r["start"]
                    for _ in range(nsect - 1):
                        if sect >= len(fat):
                            break
                        sect = fat[sect]
                    if sect >= len(fat):
                        continue
                    f.seek((sect + 1) * ss)
                    last = f.read(ss)
                    used = r["size"] - (nsect - 1) * ss
                    tail = last[used:]
                    if tail.strip(b"\x00"):
                        out.append(f"{r['path'] or '(root)'}: {len(tail)} non-zero slack bytes "
                                   f"after end of stream (first: {tail[:8].hex()})")
    except Exception as exc:
        out.append(f"(slack check failed: {exc!r})")
    return out


# --- reporting helpers ---------------------------------------------------------------

FILETIME_EPOCH_DIFF = 116444736000000000


def _filetime_str(ft: int) -> str:
    if not ft:
        return "0"
    secs = (ft - FILETIME_EPOCH_DIFF) / 1e7
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(secs))


def print_params(path: str) -> None:
    c = catalog(path)
    h = c["header"]
    print(f"# {os.path.basename(path)}  ({h['file_size']:,} bytes)")
    print(f"  CFB v{h['major_version']} (minor {h['minor_version']:#06x}), sector {h['sector_size']} B, "
          f"mini sector {h['mini_sector_size']} B, cutoff {h['mini_stream_cutoff']:#x}")
    print(f"  FAT {h['num_fat_sectors']} · DIFAT {h['num_difat_sectors']} · dir {h['num_dir_sectors']} · "
          f"miniFAT {h['num_minifat_sectors']} sectors; mini stream {h['mini_stream_size']:,} B; "
          f"txsig {h['transaction_signature']}; {h['num_entries']} entries")
    print(f"  {'sid':>3} {'type':7} {'path':30} {'size':>13} {'clsid':10} {'state':>5}  ctime / mtime")
    for r in c["entries"]:
        print(f"  {r['sid']:>3} {r['type']:7} {(r['path'] or '(root)'):30} {r['size']:>13,} "
              f"{(r['clsid'] or 'null'):10} {r['state_bits']:>5}  "
              f"{_filetime_str(r['ctime'])} / {_filetime_str(r['mtime'])}")


def print_byte_report(rep: Dict[str, object]) -> None:
    if rep["byte_identical"]:
        print("byte-identical: YES")
        return
    print("byte-identical: NO")
    for cat, lines in rep["categories"].items():
        print(f"  [{cat}]")
        for ln in lines[:12]:
            print(f"    {ln}")
        if len(lines) > 12:
            print(f"    ... ({len(lines) - 12} more)")


# --- CLI ------------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="rvt.roundtrip", description=__doc__.split("\n\n")[0])
    ap.add_argument("input", help="source .rvt / CFB file")
    ap.add_argument("output", nargs="?", help="destination path for the re-emitted file")
    ap.add_argument("--verify", action="store_true",
                    help="reopen both files and assert stream-level equality")
    ap.add_argument("--byte-report", action="store_true",
                    help="report whether output is byte-identical and categorise differences")
    ap.add_argument("--params", action="store_true",
                    help="just print the CFB parameters/directory of the input")
    ap.add_argument("--json", action="store_true", help="machine-readable catalog output (with --params)")
    a = ap.parse_args(argv)

    if a.params:
        if a.json:
            print(json.dumps(catalog(a.input), indent=2))
        else:
            print_params(a.input)
        return 0
    if not a.output:
        ap.error("output path required (or use --params)")

    layout, tread, twrite = roundtrip(a.input, a.output)
    print(f"round-tripped {a.input} -> {a.output}")
    print(f"  read {tread:.2f}s, write {twrite:.2f}s; v{layout.major_version}, "
          f"{layout.num_sectors + 1} sectors ({layout.file_size:,} B), "
          f"{layout.num_fat_sectors} FAT / {layout.num_difat_sectors} DIFAT / "
          f"{layout.num_dir_sectors} dir / {layout.num_minifat_sectors} miniFAT sectors, "
          f"mini stream {layout.mini_stream_size:,} B")
    rc = 0
    if a.verify:
        problems, notes = verify_pair(a.input, a.output)
        if problems:
            print("VERIFY: FAILED")
            for p in problems:
                print("  - " + p)
            rc = 1
        else:
            print("VERIFY: OK (identical paths, stream bytes, CLSIDs, state bits, timestamps; "
                  "olefile strict clean; second-reader cross-check clean unless noted below)")
        for n in notes:
            print("  note: " + n)
    if a.byte_report:
        print_byte_report(byte_diff_report(a.input, a.output))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
