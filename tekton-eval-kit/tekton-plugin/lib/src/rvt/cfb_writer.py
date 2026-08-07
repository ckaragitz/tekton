"""Pure-Python OLE2 / Compound File Binary (CFB) *writer*.

The container layer needed to emit ``.rvt`` files (and any other CFB
document). Implements Microsoft's public specification
"[MS-CFB]: Compound File Binary File Format" (version 12.0, 2024-04-23).
Section numbers cited below refer to that document:

* 2.1  Sector numbers and types (FREESECT / ENDOFCHAIN / FATSECT / DIFSECT,
       offset = (sector + 1) * sector_size).
* 2.2  Compound File Header (512-byte header; v4 pads the header sector to
       4,096 bytes with zeroes; 109-entry DIFAT array in the header).
* 2.3  FAT sectors (128 or 1,024 entries; entries past end-of-file MUST be
       FREESECT).
* 2.4  Mini FAT / mini stream (streams < 4,096 bytes live in 64-byte mini
       sectors inside the root object's stream).
* 2.5  DIFAT sectors (needed once there are more than 109 FAT sectors).
* 2.6  Directory sectors: 128-byte entries, red-black sibling tree per
       storage (2.6.4), root entry rules (2.6.2), free entries (2.6.3).
* 2.7  User-defined data sectors (slack SHOULD be zero-filled).
* 2.9  Size limits (v3 <= 2 GB).

Public API::

    from rvt.cfb_writer import CfbEntry, write_cfb
    layout = write_cfb("out.rvt", entries)

``entries`` is an ordered list of :class:`CfbEntry`. The list ORDER is the
directory order: entry ``i`` becomes stream ID ``i`` in the directory sector
chain, exactly as in the original file, so a round trip can preserve the
original directory layout. Entry 0 must be the root (``entry_type="root"``).
Each entry keeps its full storage path, CLSID, state bits and
creation/modified FILETIMEs; stream entries also carry their bytes.

What the writer chooses itself (and therefore may differ from a file written
by Windows' Structured Storage): the physical sector layout (contiguous,
FAT sectors first), the red/black sibling-tree links inside each storage
(rebuilt as a balanced, all-black binary search tree, explicitly permitted by
2.6.4), and zero-filled slack in the last sector of every stream (2.7).

No dependencies outside the standard library.
"""
from __future__ import annotations

import struct
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

# --- constants ([MS-CFB] 2.1, 2.6.1) ---------------------------------------

MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"        # 2.2 header signature

MAXREGSECT = 0xFFFFFFFA
DIFSECT = 0xFFFFFFFC       # sector holds a DIFAT sector
FATSECT = 0xFFFFFFFD       # sector holds a FAT sector
ENDOFCHAIN = 0xFFFFFFFE    # last sector of a chain
FREESECT = 0xFFFFFFFF      # unallocated sector

NOSTREAM = 0xFFFFFFFF      # 2.6.1 empty sibling/child pointer

# Object Type field (2.6.1)
STGTY_UNALLOCATED = 0x00
STGTY_STORAGE = 0x01
STGTY_STREAM = 0x02
STGTY_ROOT = 0x05

RED = 0x00
BLACK = 0x01

MINI_SECTOR_SHIFT = 6                 # 64-byte mini sectors (MUST, 2.2)
MINI_SECTOR_SIZE = 1 << MINI_SECTOR_SHIFT
MINI_STREAM_CUTOFF = 0x1000           # MUST be 0x1000 (2.2)
MINOR_VERSION = 0x003E                # SHOULD be 0x003E (2.2)
BYTE_ORDER = 0xFFFE                   # MUST (2.2)
DIR_ENTRY_SIZE = 128                  # fixed (2.6.1)
HEADER_DIFAT_ENTRIES = 109            # DIFAT slots in the header (2.2/2.5)

ROOT_NAME = "Root Entry"              # MUST (2.6.2)

_ILLEGAL_NAME_CHARS = set('/\\:!')    # 2.6.1


# --- data model --------------------------------------------------------------

@dataclass
class CfbEntry:
    """One directory entry (root, storage or stream).

    * ``path``  - "/"-joined path relative to the root; "" for the root itself
                  (e.g. "Global/Latest", "Formats", "").
    * ``entry_type`` - "root", "storage" or "stream".
    * ``data``  - stream bytes (streams only).
    * ``clsid`` - object class GUID: "" / None for CLSID_NULL, a GUID string
                  ("D4590F81-...") or 16 raw little-endian bytes.
    * ``state_bits`` - user flags (dwUserFlags), storages/root only.
    * ``ctime`` / ``mtime`` - raw Windows FILETIME (uint64, 100 ns since 1601).
    """

    path: str
    entry_type: str
    data: bytes = b""
    clsid: Union[str, bytes, None] = ""
    state_bits: int = 0
    ctime: int = 0
    mtime: int = 0

    # -- helpers ---------------------------------------------------------
    @property
    def name(self) -> str:
        return ROOT_NAME if self.entry_type == "root" else self.path.rsplit("/", 1)[-1]

    @property
    def parent_path(self) -> str:
        return self.path.rsplit("/", 1)[0] if "/" in self.path else ""

    @property
    def is_root(self) -> bool:
        return self.entry_type == "root"

    @property
    def is_storage(self) -> bool:
        return self.entry_type in ("root", "storage")

    @property
    def is_stream(self) -> bool:
        return self.entry_type == "stream"


@dataclass
class CfbLayout:
    """What the writer decided - handy for tests, docs and diffing."""

    major_version: int
    sector_size: int
    mini_sector_size: int
    num_entries: int              # directory entries actually used
    num_dir_sectors: int
    num_fat_sectors: int
    num_difat_sectors: int
    num_minifat_sectors: int
    mini_stream_size: int         # bytes (multiple of 64)
    num_sectors: int              # sectors after the header
    file_size: int
    first_dir_sector: int
    first_minifat_sector: int
    first_difat_sector: int
    # per stream-id (list index): (start_sector_or_minisector, is_mini)
    starts: Dict[int, Tuple[int, bool]] = field(default_factory=dict)


# --- helpers -----------------------------------------------------------------

def clsid_to_bytes(clsid: Union[str, bytes, None]) -> bytes:
    """CLSID_NULL for ''/None, else GUID string or 16 raw bytes -> 16 bytes.

    On disk a GUID is stored in the mixed-endian ``uuid.UUID.bytes_le`` layout.
    """
    if clsid is None or clsid == "" or clsid == b"":
        return b"\x00" * 16
    if isinstance(clsid, (bytes, bytearray)):
        b = bytes(clsid)
        if len(b) != 16:
            raise ValueError(f"CLSID bytes must be 16 long, got {len(b)}")
        return b
    return uuid.UUID(str(clsid).strip("{}")).bytes_le


def clsid_to_str(clsid: Union[str, bytes, None]) -> str:
    """Normalise any CLSID form to olefile's string form ('' for null)."""
    b = clsid_to_bytes(clsid)
    if not b.strip(b"\x00"):
        return ""
    return str(uuid.UUID(bytes_le=b)).upper()


def _utf16_units(name: str) -> List[int]:
    raw = name.encode("utf-16-le")
    return list(struct.unpack("<%dH" % (len(raw) // 2), raw))


def cfb_name_key(name: str) -> Tuple[int, List[int]]:
    """Directory ordering key per [MS-CFB] 2.6.4: shorter names sort first,
    then compare each UTF-16 code unit after simple uppercase conversion."""
    units = _utf16_units(name)
    up = []
    for u in units:
        c = chr(u)
        cu = c.upper()
        # simple (single code unit) case conversion only; surrogates and
        # multi-char expansions ("ß" -> "SS") are left untouched (2.6.4 note).
        if len(cu) == 1 and ord(cu) <= 0xFFFF and not (0xD800 <= u <= 0xDFFF):
            up.append(ord(cu))
        else:
            up.append(u)
    # length compared via the Directory Entry Name Length field, i.e.
    # (code units + 1 for the terminating null) * 2
    return (len(units), up)


def _validate_name(name: str) -> None:
    if not name:
        raise ValueError("empty directory entry name")
    if len(_utf16_units(name)) > 31:  # 64-byte field incl. UTF-16 NUL (2.6.1)
        raise ValueError(f"name too long (>31 UTF-16 units): {name!r}")
    bad = _ILLEGAL_NAME_CHARS.intersection(name)
    if bad:
        raise ValueError(f"illegal characters {sorted(bad)} in name {name!r}")


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


# --- directory tree ([MS-CFB] 2.6.4) ----------------------------------------

def _build_balanced_tree(sorted_ids: Sequence[int],
                         left: Dict[int, int], right: Dict[int, int]) -> int:
    """Build a balanced binary search tree over the (already name-sorted)
    sibling stream-ids by recursive median split. Fills ``left``/``right``
    with sibling links and returns the sub-tree root id (or NOSTREAM).

    Every node is coloured black by the caller: 2.6.4 states "the simplest
    implementation of the preceding invariants would be to mark every node as
    black, in which case the tree is simply a binary tree" - i.e. an all-black
    binary search tree satisfies every MUST in 2.6.4 (root black, no two
    consecutive red nodes, sorted order).
    """
    if not sorted_ids:
        return NOSTREAM
    mid = len(sorted_ids) // 2
    sid = sorted_ids[mid]
    left[sid] = _build_balanced_tree(sorted_ids[:mid], left, right)
    right[sid] = _build_balanced_tree(sorted_ids[mid + 1:], left, right)
    return sid


# --- the writer --------------------------------------------------------------

def write_cfb(path: str,
              entries: Sequence[CfbEntry],
              *,
              major_version: int = 4) -> CfbLayout:
    """Write a Compound File Binary document containing ``entries`` to ``path``.

    ``entries`` is the ordered directory: entry ``i`` is stream ID ``i``.
    ``entries[0]`` must be the root. ``major_version`` selects v3 (512-byte
    sectors) or v4 (4,096-byte sectors, the value Revit 2026 uses).
    Returns a :class:`CfbLayout` describing the emitted geometry.
    """
    if major_version not in (3, 4):
        raise ValueError("major_version must be 3 or 4")
    if not entries or entries[0].entry_type != "root":
        raise ValueError("entries[0] must be the root storage (entry_type='root')")

    sector_shift = 12 if major_version == 4 else 9        # 2.2
    ss = 1 << sector_shift                                # sector size
    eps = ss // 4                                        # FAT entries per sector
    n = len(entries)

    # -- validate names, hierarchy, uniqueness (2.6.1, 2.6.4) ----------------
    index_by_path: Dict[str, int] = {}
    for i, e in enumerate(entries):
        if e.entry_type == "root":
            if i != 0:
                raise ValueError("only entries[0] may be the root")
            key = ""
        else:
            if e.entry_type not in ("storage", "stream"):
                raise ValueError(f"bad entry_type {e.entry_type!r} for {e.path!r}")
            if not e.path:
                raise ValueError("non-root entry needs a path")
            _validate_name(e.name)
            key = e.path
        if key in index_by_path:
            raise ValueError(f"duplicate directory path {key!r}")
        index_by_path[key] = i

    children: Dict[int, List[int]] = {i: [] for i, e in enumerate(entries) if e.is_storage}
    for i, e in enumerate(entries):
        if i == 0:
            continue
        parent = index_by_path.get(e.parent_path)
        if parent is None:
            raise ValueError(f"parent storage {e.parent_path!r} of {e.path!r} not found")
        if not entries[parent].is_storage:
            raise ValueError(f"parent of {e.path!r} is not a storage")
        children[parent].append(i)

    for parent, kids in children.items():
        seen = {}
        for k in kids:
            up = tuple(cfb_name_key(entries[k].name)[1])
            if up in seen:
                raise ValueError(
                    f"duplicate name {entries[k].name!r} inside {entries[parent].path or '/'}")
            seen[up] = k

    # -- classify streams: mini (<4096) vs regular (2.2 cutoff, 2.6.3) ------
    mini_ids: List[int] = []
    regular_ids: List[int] = []
    for i, e in enumerate(entries):
        if not e.is_stream:
            continue
        if len(e.data) == 0:
            continue                        # empty: start = ENDOFCHAIN
        if len(e.data) < MINI_STREAM_CUTOFF:
            mini_ids.append(i)
        else:
            regular_ids.append(i)
    if major_version == 3:
        for i in regular_ids:
            if len(entries[i].data) > 0x80000000:      # 2.6.1 / 2.9
                raise ValueError("stream too large for a version-3 (512-byte) file")

    # -- mini stream + mini FAT (2.4) -----------------------------------------
    starts: Dict[int, Tuple[int, bool]] = {}
    mini_chunks: List[bytes] = []
    minifat: List[int] = []
    mini_next = 0
    for i in mini_ids:
        data = entries[i].data
        nsect = _ceil_div(len(data), MINI_SECTOR_SIZE)
        starts[i] = (mini_next, True)
        for s in range(mini_next, mini_next + nsect - 1):
            minifat.append(s + 1)
        minifat.append(ENDOFCHAIN)
        pad = nsect * MINI_SECTOR_SIZE - len(data)
        mini_chunks.append(data + b"\x00" * pad)
        mini_next += nsect
    mini_stream = b"".join(mini_chunks)
    num_mini_sectors = mini_next
    assert len(mini_stream) == num_mini_sectors * MINI_SECTOR_SIZE

    n_minifat = _ceil_div(num_mini_sectors * 4, ss)   # mini FAT sectors
    n_ministream = _ceil_div(len(mini_stream), ss)     # sectors holding the mini stream
    n_dir = _ceil_div(n * DIR_ENTRY_SIZE, ss)          # directory sectors (2.6)

    # -- solve FAT / DIFAT sizes (2.3, 2.5) ------------------------------------
    reg_sectors = {i: _ceil_div(len(entries[i].data), ss) for i in regular_ids}
    content = n_dir + n_minifat + n_ministream + sum(reg_sectors.values())

    def difat_needed(nfat: int) -> int:
        if nfat <= HEADER_DIFAT_ENTRIES:
            return 0
        return _ceil_div(nfat - HEADER_DIFAT_ENTRIES, eps - 1)

    n_fat = max(1, _ceil_div(content, eps))
    while True:
        n_difat = difat_needed(n_fat)
        total = n_fat + n_difat + content
        if n_fat * eps >= total:
            break
        n_fat = _ceil_div(total, eps)
    n_difat = difat_needed(n_fat)
    n_sect = n_fat + n_difat + content        # sectors after the header

    # -- assign the physical layout (all chains contiguous) -----------------
    # [FAT][DIFAT][DIR][MINIFAT][MINISTREAM][streams in directory order]
    fat_first = 0
    difat_first = fat_first + n_fat
    dir_first = difat_first + n_difat
    minifat_first = dir_first + n_dir
    ministream_first = minifat_first + n_minifat
    cur = ministream_first + n_ministream
    for i in regular_ids:
        starts[i] = (cur, False)
        cur += reg_sectors[i]
    assert cur == n_sect

    # -- FAT array (2.3) -------------------------------------------------------
    fat: List[int] = [0] * n_sect
    for s in range(fat_first, difat_first):
        fat[s] = FATSECT
    for s in range(difat_first, dir_first):
        fat[s] = DIFSECT

    def chain(first: int, count: int) -> None:
        for s in range(first, first + count - 1):
            fat[s] = s + 1
        if count:
            fat[first + count - 1] = ENDOFCHAIN

    chain(dir_first, n_dir)
    chain(minifat_first, n_minifat)
    chain(ministream_first, n_ministream)
    for i in regular_ids:
        chain(starts[i][0], reg_sectors[i])
    # entries covering past the last used sector MUST be FREESECT (2.3)
    fat.extend([FREESECT] * (n_fat * eps - n_sect))
    assert len(fat) == n_fat * eps

    # -- DIFAT: header array + DIFAT sectors (2.2, 2.5) -----------------------
    fat_sector_list = list(range(fat_first, fat_first + n_fat))
    header_difat = fat_sector_list[:HEADER_DIFAT_ENTRIES]
    header_difat += [FREESECT] * (HEADER_DIFAT_ENTRIES - len(header_difat))
    difat_sectors: List[bytes] = []
    rest = fat_sector_list[HEADER_DIFAT_ENTRIES:]
    per = eps - 1
    for k in range(n_difat):
        chunk = rest[k * per:(k + 1) * per]
        chunk += [FREESECT] * (per - len(chunk))
        nxt = difat_first + k + 1 if k + 1 < n_difat else ENDOFCHAIN
        difat_sectors.append(struct.pack("<%dI" % eps, *chunk, nxt))

    # -- directory tree links (2.6.4) ------------------------------------------
    left: Dict[int, int] = {}
    right: Dict[int, int] = {}
    child: Dict[int, int] = {}
    for parent, kids in children.items():
        ordered = sorted(kids, key=lambda k: cfb_name_key(entries[k].name))
        child[parent] = _build_balanced_tree(ordered, left, right)

    # -- directory entries (2.6.1, 2.6.2, 2.6.3) ------------------------------
    dir_bytes = bytearray()
    for i, e in enumerate(entries):
        name = ROOT_NAME if e.is_root else e.name
        name_utf16 = name.encode("utf-16-le")
        name_field = name_utf16 + b"\x00\x00"
        name_len = len(name_field)                       # bytes incl. NUL
        if e.is_root:
            obj_type = STGTY_ROOT
            if num_mini_sectors:
                start = ministream_first
                size = len(mini_stream)
            else:                                          # no mini stream (2.4)
                start = ENDOFCHAIN
                size = 0
        elif e.is_storage:
            obj_type = STGTY_STORAGE
            start = 0                                      # MUST be 0 (2.6.1)
            size = 0
        else:
            obj_type = STGTY_STREAM
            size = len(e.data)
            if size == 0:
                start = ENDOFCHAIN                         # empty stream
            else:
                start = starts[i][0]
        entry = struct.pack(
            "<64sHBBIII16sIQQIQ",
            name_field.ljust(64, b"\x00"),
            name_len,
            obj_type,
            BLACK,                                          # colour (2.6.4)
            left.get(i, NOSTREAM),
            right.get(i, NOSTREAM),
            child.get(i, NOSTREAM),
            clsid_to_bytes(e.clsid),
            e.state_bits & 0xFFFFFFFF,
            e.ctime & 0xFFFFFFFFFFFFFFFF,
            e.mtime & 0xFFFFFFFFFFFFFFFF,
            start,
            size,
        )
        assert len(entry) == DIR_ENTRY_SIZE
        dir_bytes += entry
    # free entries fill the rest of the last directory sector (2.6.3):
    # all zero except sibling/child ids = NOSTREAM
    free_entry = (b"\x00" * 68 + struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM)
                  + b"\x00" * 48)
    assert len(free_entry) == DIR_ENTRY_SIZE
    while len(dir_bytes) < n_dir * ss:
        dir_bytes += free_entry
    assert len(dir_bytes) == n_dir * ss

    # -- mini FAT sectors (2.4): pad to whole sectors with FREESECT ---------
    minifat_padded = minifat + [FREESECT] * (n_minifat * eps - len(minifat))
    minifat_bytes = struct.pack("<%dI" % len(minifat_padded), *minifat_padded) if minifat_padded else b""

    # -- header (2.2) -----------------------------------------------------------
    hdr = bytearray()
    hdr += MAGIC
    hdr += b"\x00" * 16                                     # CLSID_NULL
    hdr += struct.pack("<HH", MINOR_VERSION, major_version)
    hdr += struct.pack("<HH", BYTE_ORDER, sector_shift)
    hdr += struct.pack("<H", MINI_SECTOR_SHIFT)
    hdr += b"\x00" * 6                                       # reserved
    hdr += struct.pack("<I", n_dir if major_version == 4 else 0)   # csectDir (v3 MUST be 0)
    hdr += struct.pack("<I", n_fat)
    hdr += struct.pack("<I", dir_first)
    hdr += struct.pack("<I", 0)                              # transaction signature
    hdr += struct.pack("<I", MINI_STREAM_CUTOFF)
    hdr += struct.pack("<I", minifat_first if n_minifat else ENDOFCHAIN)
    hdr += struct.pack("<I", n_minifat)
    hdr += struct.pack("<I", difat_first if n_difat else ENDOFCHAIN)
    hdr += struct.pack("<I", n_difat)
    hdr += struct.pack("<109I", *header_difat)
    assert len(hdr) == 512
    hdr += b"\x00" * (ss - 512)                              # v4: zero-fill to 4096

    # -- emit ---------------------------------------------------------------------
    fat_bytes = struct.pack("<%dI" % len(fat), *fat)
    assert len(fat_bytes) == n_fat * ss
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(fat_bytes)                                   # FAT sectors
        for b in difat_sectors:                              # DIFAT sectors
            f.write(b)
        f.write(dir_bytes)                                   # directory chain
        f.write(minifat_bytes)                               # mini FAT chain
        if n_ministream:
            f.write(mini_stream)
            f.write(b"\x00" * (n_ministream * ss - len(mini_stream)))
        for i in regular_ids:                                # regular stream chains
            data = entries[i].data
            f.write(data)
            slack = reg_sectors[i] * ss - len(data)
            if slack:
                f.write(b"\x00" * slack)                     # zero slack (2.7)
        file_size = f.tell()
    assert file_size == (n_sect + 1) * ss, (file_size, n_sect, ss)

    return CfbLayout(
        major_version=major_version,
        sector_size=ss,
        mini_sector_size=MINI_SECTOR_SIZE,
        num_entries=n,
        num_dir_sectors=n_dir,
        num_fat_sectors=n_fat,
        num_difat_sectors=n_difat,
        num_minifat_sectors=n_minifat,
        mini_stream_size=len(mini_stream),
        num_sectors=n_sect,
        file_size=file_size,
        first_dir_sector=dir_first,
        first_minifat_sector=minifat_first if n_minifat else ENDOFCHAIN,
        first_difat_sector=difat_first if n_difat else ENDOFCHAIN,
        starts=starts,
    )


# --- demo ----------------------------------------------------------------------

def _demo() -> None:
    """Write a small synthetic compound file and read it back with olefile."""
    import os
    import tempfile

    entries = [
        CfbEntry("", "root", mtime=133863496043040000),
        CfbEntry("Formats", "storage", ctime=133863496023580000, mtime=133863496043030000),
        CfbEntry("Global", "storage", ctime=133863496031090000, mtime=133863496031620000),
        CfbEntry("Contents", "stream", data=b"hello mini stream " * 10),
        CfbEntry("BasicFileInfo", "stream", data=b"\x01\x02" * 300),
        CfbEntry("Formats/Latest", "stream", data=bytes(range(256)) * 400),   # 102,400 B regular
        CfbEntry("Global/Latest", "stream", data=b"G" * 5000),
        CfbEntry("Global/History", "stream", data=b""),                        # empty stream
    ]
    fd, tmp = tempfile.mkstemp(suffix=".cfb")
    os.close(fd)
    layout = write_cfb(tmp, entries)
    print(f"wrote {tmp}: {layout.file_size:,} bytes, v{layout.major_version}, "
          f"{layout.num_fat_sectors} FAT / {layout.num_dir_sectors} dir / "
          f"{layout.num_minifat_sectors} miniFAT sectors, mini stream {layout.mini_stream_size} B")
    try:
        import olefile
        with olefile.OleFileIO(tmp, raise_defects=olefile.DEFECT_INCORRECT) as ole:
            for parts in ole.listdir(streams=True, storages=True):
                p = "/".join(parts)
                if ole.get_type(parts) == olefile.STGTY_STREAM:
                    print(f"  {p:30s} {ole.get_size(parts):>10,}")
                else:
                    print(f"  {p + '/':30s} storage")
            assert ole.openstream("Global/Latest").read() == b"G" * 5000
            assert ole.openstream("Contents").read() == b"hello mini stream " * 10
        print("olefile read-back OK")
    finally:
        os.unlink(tmp)


if __name__ == "__main__":
    _demo()
