"""Core .rvt container access — the spine every decoder plugs into.

An .rvt is an OLE2/CFB compound document. This module gives lazy access to
its streams and transparently handles Revit's storage layering:

* PAGE FRAMING (the critical layer): every raw OLE stream is stored as pages
  of 64,896 (0xFD80) payload bytes, each followed by a 353-byte opaque
  page-trailer block (an integrity/ECC record Revit uses for auto-repair; see
  ZDI's 2025 Revit deserialization research and our own cross-file analysis).
  The trailers sit at raw offsets ``64896 + k*65249``. ``depage()`` strips
  them to recover the *logical* stream. All decoding must operate on the
  logical bytes — reading raw bytes silently garbles data past the first
  page boundary. (An earlier version of this module wrongly diagnosed the
  interleaved trailers as "corrupt gzip trailers" and raw-inflated; that
  yielded plausible-but-wrong output beyond ~64 KB.)
* After de-paging, every gzip member is a textbook gzip stream with a VALID
  CRC32/ISIZE trailer. We verify it.
* ``Global/*`` streams carry a small binary prefix (a per-stream-name
  constant: Latest=5, ContentDocuments/DocumentIncrementTable/History=1,
  ElemTable/PartitionTable=0) before the first gzip member;
  ``Partitions/<N>`` carry a 44-byte header then a run of ~128 KiB gzip
  blocks separated by 26-byte block headers. ``members()`` enumerates the
  gzip members of the *logical* stream; block/record framing lives in the
  ``partitions`` module.

Everything here is read-only; per-stream *semantic* decoders live in sibling
modules (schema, elemtable, partitions, ...).
"""
from __future__ import annotations

import os
import zlib
from dataclasses import dataclass
from typing import Iterator, List

import olefile

GZIP_MAGIC = b"\x1f\x8b\x08"

# Stream page framing (see module docstring / KNOWLEDGE.md).
PAGE_PAYLOAD = 64_896   # 0xFD80 logical bytes per page
PAGE_TRAILER = 353      # opaque per-page trailer block
PAGE_STRIDE = PAGE_PAYLOAD + PAGE_TRAILER  # 65,249


def depage(raw: bytes) -> bytes:
    """Strip the 353-byte page trailers to recover the logical stream.

    Pages are 64,896 payload bytes followed by a 353-byte trailer; the final
    partial page carries a proportionally shorter trailer, which lands after
    the last payload byte and is therefore harmless trailing junk.
    """
    if len(raw) <= PAGE_PAYLOAD:
        return raw
    out = bytearray()
    pos = 0
    n = len(raw)
    while pos < n:
        out += raw[pos:pos + PAGE_PAYLOAD]
        pos += PAGE_STRIDE
    return bytes(out)


@dataclass(frozen=True)
class Member:
    """One gzip member found inside a (de-paged, logical) stream."""

    index: int
    offset: int      # byte offset of the gzip magic within the LOGICAL stream
    consumed: int    # compressed bytes consumed (header + deflate + trailer)
    inflated: int    # decompressed length
    crc_ok: bool     # True when the gzip trailer CRC32/ISIZE verified


@dataclass(frozen=True)
class StreamInfo:
    name: str        # full OLE path, e.g. "Global/Latest"
    size: int        # raw (paged) size in the container


def _inflate_at(data: bytes, off: int):
    """Inflate the gzip member starting at ``off`` in a LOGICAL buffer.

    Returns ``(payload, consumed, crc_ok)`` or ``None`` if not inflatable.
    De-paged data has valid trailers, so the strict gzip wrapper normally
    succeeds and CRC-verifies. A raw-deflate fallback (skip 10-byte header)
    is kept purely as a diagnostic escape hatch; it reports ``crc_ok=False``.
    """
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)  # gzip wrapper, checks CRC
    try:
        out = d.decompress(data[off:]) + d.flush()
        return out, len(data) - off - len(d.unused_data), True
    except zlib.error:
        pass
    d = zlib.decompressobj(-zlib.MAX_WBITS)
    try:
        out = d.decompress(data[off + 10:]) + d.flush()
    except zlib.error:
        return None
    return out, len(data) - off - len(d.unused_data), False


class RvtDocument:
    """Read-only view over a Revit compound file (page-framing aware)."""

    def __init__(self, path: str):
        self.path = path
        self._ole = olefile.OleFileIO(path)
        self._raw_cache: dict = {}
        self._logical_cache: dict = {}
        self._member_cache: dict = {}

    # -- context manager -------------------------------------------------
    def close(self) -> None:
        self._ole.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- inventory --------------------------------------------------------
    def streams(self) -> List[StreamInfo]:
        out = []
        for parts in self._ole.listdir(streams=True, storages=False):
            name = "/".join(parts)
            out.append(StreamInfo(name=name, size=self._ole.get_size(parts)))
        return out

    def has(self, name: str) -> bool:
        return self._ole.exists(name.split("/"))

    # -- bytes ---------------------------------------------------------------
    def raw(self, name: str) -> bytes:
        """The stream exactly as stored in the container (still paged)."""
        if name not in self._raw_cache:
            self._raw_cache[name] = self._ole.openstream(name.split("/")).read()
        return self._raw_cache[name]

    def logical(self, name: str) -> bytes:
        """The stream with page trailers stripped — decode from THIS."""
        if name not in self._logical_cache:
            self._logical_cache[name] = depage(self.raw(name))
        return self._logical_cache[name]

    # -- gzip members ----------------------------------------------------------
    def members(self, name: str) -> List[Member]:
        """Enumerate every gzip member in the logical stream."""
        if name in self._member_cache:
            return self._member_cache[name]
        data = self.logical(name)
        members: List[Member] = []
        pos = 0
        while True:
            i = data.find(GZIP_MAGIC, pos)
            if i < 0:
                break
            r = _inflate_at(data, i)
            if r is None:
                pos = i + 1
                continue
            payload, consumed, crc_ok = r
            members.append(Member(len(members), i, consumed, len(payload), crc_ok))
            pos = i + max(consumed, 1)
        self._member_cache[name] = members
        return members

    def prefix(self, name: str) -> bytes:
        """Bytes before the first gzip member (the stream's binary header)."""
        m = self.members(name)
        data = self.logical(name)
        return data[: m[0].offset] if m else data

    def inflate(self, name: str, index: int = 0) -> bytes:
        """Inflate gzip member ``index`` of the logical stream."""
        m = self.members(name)
        if not m:
            raise ValueError(f"{name!r}: no gzip members (not compressed?)")
        if index >= len(m):
            raise IndexError(f"{name!r}: has {len(m)} member(s), asked for {index}")
        r = _inflate_at(self.logical(name), m[index].offset)
        assert r is not None
        return r[0]

    def inflate_all(self, name: str) -> Iterator[bytes]:
        """Yield each gzip member's payload in stream order."""
        data = self.logical(name)
        for mem in self.members(name):
            r = _inflate_at(data, mem.offset)
            assert r is not None
            yield r[0]

    def concat(self, name: str) -> bytes:
        """All members inflated and concatenated (partition element data)."""
        return b"".join(self.inflate_all(name))

    # -- convenience -------------------------------------------------------
    def partition_streams(self) -> List[str]:
        return sorted(s.name for s in self.streams() if s.name.startswith("Partitions/"))

    def describe(self) -> str:
        rows = [f"{self.path}"]
        for s in self.streams():
            m = self.members(s.name)
            crc = "" if all(x.crc_ok for x in m) else "  [CRC MISMATCH]"
            if not m:
                kind = "raw"
            elif len(m) == 1 and m[0].offset == 0:
                kind = f"gzip -> {m[0].inflated:,}"
            elif len(m) == 1:
                kind = f"hdr{m[0].offset}+gzip -> {m[0].inflated:,}"
            else:
                total = sum(x.inflated for x in m)
                kind = f"{len(m)} blocks -> {total:,}"
            rows.append(f"  {s.name:32s} {s.size:>13,}   {kind}{crc}")
        return "\n".join(rows)


def open_rvt(path: str) -> RvtDocument:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return RvtDocument(path)


if __name__ == "__main__":
    import sys

    paths = sys.argv[1:] or [
        os.path.join(os.path.dirname(__file__), "..", "..", "samples", "racbasicsampleproject.rvt")
    ]
    for p in paths:
        with open_rvt(p) as doc:
            print(doc.describe())
            print()
