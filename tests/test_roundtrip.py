"""Round-trip and container-writer tests for the CFB (OLE2) writer.

Run:
    /Users/ck/dev/things/rev-revit/.venv/bin/python -m pytest tests/test_roundtrip.py -v -s

* Every one of the six Revit 2026 samples is round-tripped through
  ``experiments/roundtrip/<name>.rvt`` and must come back stream-equal
  (paths, bytes, CLSIDs, state bits, timestamps), re-parse cleanly with a
  strict ``olefile`` and with the independent ``compoundfiles`` reader.
* The 139 MB ``dach-sample-project`` case is marked ``slow``; set
  ``RVT_SKIP_LARGE=1`` to skip it (it takes ~1 s here, timing is printed).
* ``test_byte_level_report`` never asserts byte identity: it REPORTS whether
  each output is byte-identical to its input and categorises the diffs.
* Synthetic tests cover the writer paths the samples do not: DIFAT sectors
  (needed only past 109 FAT sectors), empty streams, deep nesting, and the
  directory-tree ordering rules.
"""
from __future__ import annotations

import os
import struct
import time
import warnings

import olefile
import pytest

from rvt.cfb_writer import (
    CfbEntry,
    ENDOFCHAIN,
    FREESECT,
    NOSTREAM,
    cfb_name_key,
    write_cfb,
)
from rvt.roundtrip import (
    byte_diff_report,
    catalog,
    roundtrip,
    verify_pair,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
OUT = os.path.join(ROOT, "experiments", "roundtrip")

SMALL = [
    "rstbasicsampleproject",
    "racbasicsampleproject",
    "racadvancedsampleproject",
    "rmebasicsampleproject",
    "rstadvancedsampleproject",
]
LARGE = ["dach-sample-project"]
ALL = SMALL + LARGE

skip_large = pytest.mark.skipif(
    os.environ.get("RVT_SKIP_LARGE") == "1",
    reason="RVT_SKIP_LARGE=1 (139 MB dach sample skipped)")


def _sample(name: str) -> str:
    p = os.path.join(SAMPLES, name + ".rvt")
    if not os.path.exists(p):
        pytest.skip(f"sample missing: {p}")
    return p


# --- 1. stream-level round trip of all six samples ------------------------------

@pytest.mark.parametrize(
    "name",
    [pytest.param(n) for n in SMALL]
    + [pytest.param(n, marks=[pytest.mark.slow, skip_large]) for n in LARGE],
)
def test_roundtrip_stream_equality(name: str) -> None:
    src = _sample(name)
    dst = os.path.join(OUT, name + ".rvt")
    t0 = time.time()
    layout, tread, twrite = roundtrip(src, dst)
    problems = verify_pair(src, dst)
    dt = time.time() - t0
    print(f"\n[{name}] {layout.file_size:,} B out, v{layout.major_version}, "
          f"{layout.num_fat_sectors} FAT/{layout.num_difat_sectors} DIFAT sectors; "
          f"read {tread:.2f}s write {twrite:.2f}s total(incl. verify) {dt:.2f}s")
    assert layout.major_version == 4, "Revit 2026 files are CFB v4 (4096-byte sectors)"
    assert layout.sector_size == 4096 and layout.mini_sector_size == 64
    assert problems == [], "round trip mismatch:\n  " + "\n  ".join(problems)


# --- 2. byte-level comparison (REPORT ONLY, never asserts identity) --------------

def test_byte_level_report(capsys) -> None:
    """States, per sample, whether output is byte-identical to the input and
    categorises differences. Purely informational."""
    with capsys.disabled():
        print("\n=== byte-level comparison report ===")
        for name in ALL:
            if name in LARGE and os.environ.get("RVT_SKIP_LARGE") == "1":
                print(f"[{name}] skipped (RVT_SKIP_LARGE=1)")
                continue
            src = _sample(name)
            dst = os.path.join(OUT, name + ".rvt")
            if not os.path.exists(dst):
                roundtrip(src, dst)
            rep = byte_diff_report(src, dst)
            ident = rep["byte_identical"]
            print(f"[{name}] byte-identical: {'YES' if ident else 'NO'}")
            for cat, lines in rep.get("categories", {}).items():
                print(f"    {cat}: {len(lines)} difference(s); e.g. {lines[0]}")
    # A category set is well-formed and the report always answers the question
    for name in SMALL:
        rep = byte_diff_report(_sample(name), os.path.join(OUT, name + ".rvt"))
        assert isinstance(rep["byte_identical"], bool)
        if not rep["byte_identical"]:
            assert rep["categories"], "differences must be categorised"


# --- 3. writer unit tests (no samples needed) ----------------------------------------

def _strict_read(path: str) -> olefile.OleFileIO:
    return olefile.OleFileIO(path, raise_defects=olefile.DEFECT_INCORRECT)


def _no_compoundfiles_warnings(path: str) -> None:
    """Second, independent CFB reader check.  ``compoundfiles`` is an
    optional dev extra (not a declared dependency): absent, the strict
    olefile assertions above still gate the writer -- skip only this
    cross-check, don't fail the test."""
    try:
        from compoundfiles import CompoundFileReader
    except ImportError:
        pytest.skip("compoundfiles not installed (optional cross-check reader)")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        r = CompoundFileReader(path)
        list(r.root)
        r.close()
    msgs = [f"{w.category.__name__}: {w.message}" for w in caught]
    assert msgs == [], "compoundfiles warnings: " + "; ".join(msgs)


def test_synthetic_small(tmp_path) -> None:
    entries = [
        CfbEntry("", "root", mtime=133863496043040000),
        CfbEntry("Formats", "storage", ctime=1, mtime=2),
        CfbEntry("Global", "storage", ctime=3, mtime=4),
        CfbEntry("Contents", "stream", data=b"C" * 212),
        CfbEntry("Empty", "stream", data=b""),
        CfbEntry("Global/Nested", "storage", ctime=5, mtime=6),
        CfbEntry("Global/Nested/Deep", "stream", data=b"deep!" * 3),
        CfbEntry("Formats/Latest", "stream", data=bytes(range(256)) * 20),   # 5120 B regular
        CfbEntry("Global/Latest", "stream", data=b"G" * 4095),               # 4095 -> mini
        CfbEntry("Global/Exact", "stream", data=b"X" * 4096),                # 4096 -> regular
    ]
    out = str(tmp_path / "small.cfb")
    layout = write_cfb(out, entries)
    assert layout.major_version == 4 and layout.num_difat_sectors == 0
    assert layout.file_size == os.path.getsize(out)

    with _strict_read(out) as ole:
        assert ole.parsing_issues == []
        assert ole.openstream("Global/Nested/Deep").read() == b"deep!" * 3
        assert ole.openstream("Global/Latest").read() == b"G" * 4095
        assert ole.openstream("Global/Exact").read() == b"X" * 4096
        assert ole.openstream("Formats/Latest").read() == bytes(range(256)) * 20
        assert ole.get_size("Empty") == 0
        assert ole.direntries[0].name == "Root Entry"
        # cutoff: 4095 bytes must live in the mini stream, 4096 must not
        latest = [e for e in ole.direntries if e is not None and e.sid == 8][0]
        exact = [e for e in ole.direntries if e is not None and e.sid == 9][0]
        assert latest.is_minifat is True and exact.is_minifat is False
        # timestamps preserved on storages
        formats = [e for e in ole.direntries if e is not None and e.name == "Formats"][0]
        assert (formats.createTime, formats.modifyTime) == (1, 2)
    _no_compoundfiles_warnings(out)


def test_empty_stream_and_no_ministream(tmp_path) -> None:
    """No mini streams at all: mini FAT chain absent (header ENDOFCHAIN, count 0)
    and the root's start sector ENDOFCHAIN ([MS-CFB] 2.4)."""
    entries = [
        CfbEntry("", "root"),
        CfbEntry("Big", "stream", data=b"b" * 10000),
        CfbEntry("Zero", "stream", data=b""),
    ]
    out = str(tmp_path / "nomini.cfb")
    layout = write_cfb(out, entries)
    assert layout.num_minifat_sectors == 0 and layout.mini_stream_size == 0
    hdr = open(out, "rb").read(512)
    first_minifat, n_minifat = struct.unpack_from("<II", hdr, 0x3C)
    assert first_minifat == ENDOFCHAIN and n_minifat == 0
    with _strict_read(out) as ole:
        assert ole.openstream("Big").read() == b"b" * 10000
        assert ole.get_size("Zero") == 0
        assert ole.root.isectStart == ENDOFCHAIN and ole.root.size == 0
    _no_compoundfiles_warnings(out)


def test_difat_sectors_v3(tmp_path) -> None:
    """Force the DIFAT path (only needed past 109 FAT sectors). With v3
    512-byte sectors 109 FAT sectors map 6.8 MB, so a ~12 MB stream needs
    DIFAT sectors ([MS-CFB] 2.5). Both readers must accept the result."""
    payload = os.urandom(12 * 1024 * 1024 + 7)
    entries = [
        CfbEntry("", "root"),
        CfbEntry("Blob", "stream", data=payload),
        CfbEntry("Small", "stream", data=b"s" * 100),
    ]
    out = str(tmp_path / "difat.cfb")
    layout = write_cfb(out, entries, major_version=3)
    assert layout.major_version == 3 and layout.sector_size == 512
    assert layout.num_fat_sectors > 109
    assert layout.num_difat_sectors >= 1
    # header: DIFAT count/start, v3 => Number of Directory Sectors MUST be 0
    hdr = open(out, "rb").read(512)
    n_dir = struct.unpack_from("<I", hdr, 0x28)[0]
    difat_start, n_difat = struct.unpack_from("<II", hdr, 0x44)
    assert n_dir == 0
    assert n_difat == layout.num_difat_sectors and difat_start == layout.first_difat_sector
    with _strict_read(out) as ole:
        assert ole.num_difat_sectors == layout.num_difat_sectors
        assert ole.openstream("Blob").read() == payload
        assert ole.openstream("Small").read() == b"s" * 100
    _no_compoundfiles_warnings(out)


def test_many_entries_multiple_dir_sectors(tmp_path) -> None:
    """More than 32 entries -> more than one 4096-byte directory sector, and
    a big sibling tree in one storage. Free entries pad the last dir sector."""
    entries = [CfbEntry("", "root"), CfbEntry("dir", "storage")]
    payloads = {}
    for i in range(70):
        name = f"stream_{i:02d}"
        data = (name.encode() * (i + 1)) * (100 if i % 3 == 0 else 1)
        entries.append(CfbEntry(f"dir/{name}", "stream", data=data))
        payloads[name] = data
    out = str(tmp_path / "many.cfb")
    layout = write_cfb(out, entries)
    assert layout.num_dir_sectors == 3   # 72 entries * 128 B / 4096
    with _strict_read(out) as ole:
        names = sorted("/".join(p) for p in ole.listdir())
        assert names == sorted(f"dir/{n}" for n in payloads)
        for n, d in payloads.items():
            assert ole.openstream(f"dir/{n}").read() == d
        # free directory entries: type 0, zero name length, NOSTREAM pointers
        raw = open(out, "rb").read()
        dir_off = 4096 + layout.first_dir_sector * 4096
        used = len(entries) * 128
        for k in range(used, layout.num_dir_sectors * 4096, 128):
            e = raw[dir_off + k: dir_off + k + 128]
            assert e[64:68] == b"\x00\x00\x00\x00"      # namelen 0, type 0, colour 0
            assert struct.unpack_from("<III", e, 68) == (NOSTREAM, NOSTREAM, NOSTREAM)
            assert e[80:] == b"\x00" * 48
    _no_compoundfiles_warnings(out)


def test_name_ordering_key() -> None:
    """[MS-CFB] 2.6.4: shorter names sort first, then uppercase code units."""
    names = ["Latest", "History", "ElemTable", "PartitionTable",
             "ContentDocuments", "DocumentIncrementTable", "b", "A"]
    ordered = sorted(names, key=cfb_name_key)
    assert ordered == ["A", "b", "Latest", "History", "ElemTable",
                       "PartitionTable", "ContentDocuments", "DocumentIncrementTable"]
    assert cfb_name_key("abc") == cfb_name_key("ABC")   # case-insensitive equality


def test_sibling_tree_is_valid_bst(tmp_path) -> None:
    """Every storage's sibling tree must be a valid BST under the CFB name key
    with all-black nodes (root black, no red at all) for many child counts."""
    for count in (1, 2, 3, 7, 8, 20, 33, 64):
        entries = [CfbEntry("", "root"), CfbEntry("d", "storage")]
        for i in range(count):
            entries.append(CfbEntry(f"d/n{i:03d}", "stream", data=bytes([i % 256]) * (i + 1)))
        out = str(tmp_path / f"tree{count}.cfb")
        write_cfb(out, entries)
        with olefile.OleFileIO(out) as ole:
            ents = {e.sid: e for e in ole.direntries if e is not None}
            d = [e for e in ents.values() if e.name == "d"][0]
            assert d.color == 1

            def check(sid, lo, hi, seen):
                if sid == NOSTREAM:
                    return
                e = ents[sid]
                assert e.color == 1, "all nodes black"
                key = tuple(cfb_name_key(e.name))
                assert (lo is None or lo < key) and (hi is None or key < hi), "BST order"
                assert sid not in seen
                seen.add(sid)
                check(e.sid_left, lo, key, seen)
                check(e.sid_right, key, hi, seen)

            seen: set = set()
            check(d.sid_child, None, None, seen)
            assert len(seen) == count


def test_writer_rejects_bad_input(tmp_path) -> None:
    with pytest.raises(ValueError):
        write_cfb(str(tmp_path / "x.cfb"), [CfbEntry("a", "stream")])          # no root
    with pytest.raises(ValueError):
        write_cfb(str(tmp_path / "x.cfb"),
                  [CfbEntry("", "root"), CfbEntry("a", "stream"), CfbEntry("a", "stream")])
    with pytest.raises(ValueError):
        write_cfb(str(tmp_path / "x.cfb"),
                  [CfbEntry("", "root"), CfbEntry("bad:name", "stream")])   # illegal char
    with pytest.raises(ValueError):
        write_cfb(str(tmp_path / "x.cfb"),
                  [CfbEntry("", "root"), CfbEntry("Missing/child", "stream")]) # orphan parent


def test_catalog_reports_sample_parameters() -> None:
    """Every original sample is a CFB v4 file (4096-byte sectors), null CLSIDs,
    zero state bits, and the schema stream is byte-identical (498,766 B).
    Cross-checks the facts recorded in docs/streams/00-cfb-container.md."""
    for name in SMALL:
        c = catalog(_sample(name), hash_streams=False)
        h = c["header"]
        assert h["major_version"] == 4 and h["sector_size"] == 4096
        assert h["mini_sector_size"] == 64 and h["mini_stream_cutoff"] == 0x1000
        assert h["transaction_signature"] == 0 and h["num_difat_sectors"] == 0
        assert all(r["clsid"] == "" for r in c["entries"])
        assert all(r["state_bits"] == 0 for r in c["entries"])
        assert c["entries"][0]["name"] == "Root Entry" and c["entries"][0]["ctime"] == 0
