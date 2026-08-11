"""Stream (re)writer — produce Revit stream bytes and rebuild containers.

This is the write-side counterpart of ``container.py``. It knows how to:

* build a valid gzip member the way Revit's reader expects (10-byte header,
  raw deflate ending in a sync-flush + finish, correct CRC32/ISIZE trailer);
* re-frame a logical stream into pages (64,896-byte payload pages, each
  followed by a 353-byte page trailer) — with pluggable trailer contents,
  because the trailer ("ECC") is the single open question for the writer;
* rebuild a whole .rvt by replacing chosen streams and re-emitting the
  compound file via ``cfb_writer``.

The ``TrailerMode`` axis exists to run the decisive acceptance experiment:
does Autodesk's reader (Viewer / Revit) verify the 353-byte trailers
against page content? See tools/make_acceptance.py.
"""
from __future__ import annotations

import random
import struct
import zlib
from typing import Callable, Dict, Iterable, List, Optional

from . import partitions as _P
from .container import (PAGE_PAYLOAD, PAGE_STRIDE, PAGE_TRAILER,
                        RvtDocument, depage, open_rvt)
from .roundtrip import StreamEdit, rewrite_entries


def __getattr__(name: str):
    """``writer.BLOCK_TRL_TAG`` holds no value of its own: the block trailer
    tag is ``rvt.partitions.TRAILER_TAG`` (rebound BY NAME per release by
    ``rvt.versions.reading``), resolved here at ACCESS time for the one
    remaining ``from ..writer import BLOCK_TRL_TAG`` -- famgen.geometry's
    call-time import, fenced when #467 landed.  Delete with #547."""
    if name == "BLOCK_TRL_TAG":
        return _P.TRAILER_TAG
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# ---------------------------------------------------------------------------
# gzip member construction
# ---------------------------------------------------------------------------

#: Revit's 10-byte gzip header: no name/comment, mtime 0, XFL 0, OS 0x0b.
GZIP_HEADER = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x0b"


def gzip_member(payload: bytes, level: int = 6, sync_flush: bool = True) -> bytes:
    """Return a valid gzip member for ``payload``.

    Mirrors Revit's observed framing: raw deflate that ends with a
    ``00 00 ff ff`` sync-flush block and then a final empty block, followed
    by a correct little-endian CRC32 + ISIZE trailer. (Revit's own
    compressor picks different Huffman decisions, so bytes won't match
    theirs — irrelevant to any conforming inflater.)
    """
    co = zlib.compressobj(level, zlib.DEFLATED, -zlib.MAX_WBITS, 8,
                          zlib.Z_DEFAULT_STRATEGY)
    body = co.compress(payload)
    if sync_flush:
        body += co.flush(zlib.Z_SYNC_FLUSH)
    body += co.flush(zlib.Z_FINISH)
    trailer = struct.pack("<II", zlib.crc32(payload) & 0xFFFFFFFF,
                          len(payload) & 0xFFFFFFFF)
    return GZIP_HEADER + body + trailer


# ---------------------------------------------------------------------------
# Page framing
# ---------------------------------------------------------------------------

TrailerFn = Callable[[int, bytes, Optional[bytes]], bytes]
"""(page_index, page_payload, original_trailer_or_None) -> 353 bytes."""


def trailer_zero(i: int, page: bytes, orig: Optional[bytes]) -> bytes:
    return b"\x00" * PAGE_TRAILER


def trailer_copy(i: int, page: bytes, orig: Optional[bytes]) -> bytes:
    """Copy the original file's trailer for this page position verbatim
    (content will no longer match — tests presence-vs-verification)."""
    return orig if orig is not None else b"\x00" * PAGE_TRAILER


def trailer_random_factory(seed: int = 1234) -> TrailerFn:
    rng = random.Random(seed)

    def fn(i: int, page: bytes, orig: Optional[bytes]) -> bytes:
        return bytes(rng.getrandbits(8) for _ in range(PAGE_TRAILER))

    return fn


def orig_full_trailers(raw: bytes) -> List[bytes]:
    """The 353-byte trailers that follow each FULL page in a raw stream."""
    out = []
    k = 0
    while (k + 1) * PAGE_STRIDE <= len(raw):
        start = (k + 1) * PAGE_STRIDE - PAGE_TRAILER
        out.append(raw[start:start + PAGE_TRAILER])
        k += 1
    return out


def repage_like(new_logical: bytes, orig_raw: bytes, trailer_fn: TrailerFn) -> bytes:
    """Frame ``new_logical`` into pages using the ORIGINAL stream's geometry.

    ``new_logical`` must be padded to the original's logical length so the
    page count and final partial-chunk length match exactly; the output has
    exactly ``len(orig_raw)`` bytes. Full-page trailers come from
    ``trailer_fn``; the final partial chunk (which contains its short trailer
    region) is taken from ``new_logical`` (zero-padded).
    """
    n_full = 0
    while (n_full + 1) * PAGE_STRIDE <= len(orig_raw):
        n_full += 1
    orig_logical_len = len(orig_raw) - n_full * PAGE_TRAILER
    if len(new_logical) != orig_logical_len:
        raise ValueError(
            f"logical length {len(new_logical)} != original logical length "
            f"{orig_logical_len} (pad it first)")
    origs = orig_full_trailers(orig_raw)
    out = bytearray()
    for k in range(n_full):
        out += new_logical[k * PAGE_PAYLOAD:(k + 1) * PAGE_PAYLOAD]
        out += trailer_fn(k, out[-PAGE_PAYLOAD:], origs[k] if k < len(origs) else None)
    out += new_logical[n_full * PAGE_PAYLOAD:]
    assert len(out) == len(orig_raw), (len(out), len(orig_raw))
    return bytes(out)


# ---------------------------------------------------------------------------
# General page framer (page count derived from the new logical length)
# ---------------------------------------------------------------------------

def frame_pages(logical: bytes, trailer_fn: TrailerFn,
                final_trailer_len: Optional[int] = None) -> bytes:
    """Frame an arbitrary logical stream into pages + 353-byte trailers.

    Unlike ``repage_like`` this does not borrow the original's geometry, so
    it works when the payload size changed (e.g. recompressed partitions).
    The final partial page gets a short trailer whose length follows
    Autodesk's proportional rule (~353 * len/65,249) unless overridden;
    its content comes from ``trailer_fn`` truncated. If the trailer bytes
    turn out to be unverified by the reader (see acceptance Batch 1), all
    of this is inert padding and the exact short length won't matter.
    """
    out = bytearray()
    n_full = len(logical) // PAGE_PAYLOAD
    for k in range(n_full):
        page = logical[k * PAGE_PAYLOAD:(k + 1) * PAGE_PAYLOAD]
        out += page
        out += trailer_fn(k, page, None)
    tail = logical[n_full * PAGE_PAYLOAD:]
    out += tail
    if tail:
        if final_trailer_len is None:
            final_trailer_len = max(0, round(PAGE_TRAILER * len(tail) / PAGE_STRIDE))
        if final_trailer_len:
            out += trailer_fn(n_full, tail, None)[:final_trailer_len]
    return bytes(out)


# ---------------------------------------------------------------------------
# Partitions/<N> re-gzip (recompress every block, keep framing consistent)
# ---------------------------------------------------------------------------

BLOCK_HDR_LEN = 26          # u16 BLOCK_TAG (2026: 0x0f28), u32 flags, A, B, C, seq, u32 0
BLOCK_TRL_LEN = 6           # u16 TRAILER_TAG (2026: 0x0f21), u32 B (mirror of header B)


def regzip_partition_logical(doc: RvtDocument, name: str, level: int = 6) -> bytes:
    """Rebuild a ``Partitions/<N>`` LOGICAL stream with our own gzip members.

    Walks the block framing (via ``rvt.partitions.StreamWalker``), and for each
    block re-emits: the original 26-byte header with ``B`` patched to
    ``8 + len(new_gzip)``, our gzip member of the identical inflated payload,
    and the 6-byte trailer ``(TRAILER_TAG, B)`` -- the tag ``rvt.partitions``
    holds NOW (the file's release when a context is in force). Every byte
    between/around blocks (stream header, save-unit separators/terminators/
    footers, end record, tail) is copied verbatim. Uncompressed content is
    bit-identical to the original; only the compressed representation and the
    B fields change.
    """
    logical = doc.logical(name)
    walker = _P.StreamWalker(logical, inflate=True, keep_data=True)
    if walker.errors:
        raise ValueError(f"{name!r}: walker reported errors: {walker.errors[:3]}")
    blocks = sorted(walker.blocks, key=lambda b: b.hdr_offset)
    out = bytearray()
    cursor = 0
    for b in blocks:
        if b.data is None:
            raise ValueError(f"{name!r}: block {b.index} has no inflated data")
        if b.member_offset < b.hdr_offset:
            raise ValueError(f"{name!r}: block {b.index} geometry inconsistent")
        # copy everything up to and including this block's header, verbatim
        out += logical[cursor:b.member_offset]
        hdr_start = len(out) - (b.member_offset - b.hdr_offset)
        new_gz = gzip_member(b.data, level=level)
        new_b = 8 + len(new_gz)
        struct.pack_into("<I", out, hdr_start + 10, new_b)   # patch header B
        out += new_gz
        out += struct.pack("<HI", _P.TRAILER_TAG, new_b)    # trailer mirror
        cursor = b.member_offset + b.member_len + BLOCK_TRL_LEN
    out += logical[cursor:]
    return bytes(out)


# ---------------------------------------------------------------------------
# Stream re-gzip (same payloads, our compressor)
# ---------------------------------------------------------------------------

def regzip_logical(doc: RvtDocument, name: str, level: int = 6,
                   keep_tail_bytes: int = 0) -> bytes:
    """Rebuild a single-member stream's LOGICAL bytes with our own gzip.

    Layout kept: original prefix bytes (everything before the first gzip
    member) + our gzip member (identical inflated payload) + zero padding out
    to the ORIGINAL logical length. If ``keep_tail_bytes`` > 0, the final
    that-many bytes are copied from the ORIGINAL logical (preserving the
    original short final-page trailer region) instead of being zeroed.
    Only streams with exactly one gzip member are supported here.
    """
    members = doc.members(name)
    if len(members) != 1:
        raise ValueError(f"{name!r}: has {len(members)} members; single-member only")
    logical = doc.logical(name)
    prefix = doc.prefix(name)
    payload = doc.inflate(name, 0)
    body = prefix + gzip_member(payload, level=level)
    if len(body) + keep_tail_bytes > len(logical):
        raise ValueError(
            f"{name!r}: our stream {len(body)}+tail > original logical {len(logical)}")
    out = body + b"\x00" * (len(logical) - len(body))
    if keep_tail_bytes:
        out = out[:-keep_tail_bytes] + logical[-keep_tail_bytes:]
    return out


def _swap_in(new_data: Dict[str, bytes]) -> Dict[str, StreamEdit]:
    """A ``rewrite_entries`` replace-map that swaps in raw bytes computed up
    front (the variant builders derive them from the ``RvtDocument`` view, in
    an order a stateful ``trailer_fn`` depends on -- not from each entry as
    the container walk reaches it)."""
    return {name: (lambda _old, new=new: new) for name, new in new_data.items()}


def _zero_full_trailers(raw: bytes) -> bytes:
    """``raw`` with every FULL page's 353-byte trailer zeroed, payload untouched."""
    return repage_like(depage(raw), raw, trailer_zero)


def zero_full_trailers_only(in_path: str, out_path: str, streams: Iterable[str]) -> dict:
    """Keep every logical byte IDENTICAL; zero only the full-page trailers.

    The purest test of trailer verification: compressed bytes are Revit's
    own, untouched — only the 353-byte inter-page trailer records change.
    """
    streams = list(streams)
    rewrite_entries(in_path, out_path, dict.fromkeys(streams, _zero_full_trailers))
    return {"streams": streams, "mode": "orig_bytes_zero_trailers"}


def corrupt_trailer_bytes(in_path: str, out_path: str, stream: str,
                          page: int = 0, count: int = 1) -> dict:
    """Flip ``count`` byte(s) inside one page trailer; nothing else changes.

    Minimal-damage probe: does a single wrong trailer byte break translation
    (and does any auto-repair rescue it)? Trailer of full page ``page`` lives
    at raw offset (page+1)*PAGE_STRIDE - PAGE_TRAILER.
    """
    start = (page + 1) * PAGE_STRIDE - PAGE_TRAILER

    def flip(raw: bytes) -> bytes:
        if start + count > len(raw):
            raise ValueError(f"{stream!r} has no full-page trailer #{page}")
        out = bytearray(raw)
        for i in range(count):
            out[start + i] ^= 0xFF
        return bytes(out)

    rewrite_entries(in_path, out_path, {stream: flip})
    return {"stream": stream, "page": page, "flipped_bytes": count, "at_raw_offset": start}


def regzip_streams_variant(in_path: str, out_path: str, streams: Iterable[str],
                           keep_tail_bytes: int = 0, level: int = 6) -> dict:
    """Recompress single-member streams with our gzip, NO page-trailer change
    beyond what recompression forces. For SUB-PAGE streams (< 64,896 logical
    bytes) there are NO full-page trailers at all, so this isolates the
    'does Autodesk's inflater accept our deflate' question from the ECC one.
    ``keep_tail_bytes`` preserves the original short final trailer.
    """
    new_data = {}
    rep = []
    with open_rvt(in_path) as doc:
        for name in streams:
            logical = regzip_logical(doc, name, level=level, keep_tail_bytes=keep_tail_bytes)
            raw = repage_like(logical, doc.raw(name), trailer_copy)  # sub-page: no full trailers
            new_data[name] = raw
            rep.append({"name": name, "raw_size": len(raw),
                        "full_page_trailers": len(doc.raw(name)) // PAGE_STRIDE,
                        "keep_tail_bytes": keep_tail_bytes})
    rewrite_entries(in_path, out_path, _swap_in(new_data))
    return {"streams": rep}


def build_variant(in_path: str, out_path: str, streams: Iterable[str],
                  trailer_fn: TrailerFn,
                  partition_streams: Iterable[str] = ()) -> dict:
    """Rewrite ``in_path`` to ``out_path`` re-gzipping chosen streams.

    ``streams``: single-member streams — payload recompressed by us and
    re-paged onto the ORIGINAL geometry (identical raw size) via
    ``repage_like``. ``partition_streams``: ``Partitions/<N>`` — every block
    recompressed with consistent block framing, then freshly page-framed
    (raw size shrinks). Every other stream is copied byte-for-byte. Returns
    a report dict. Directory metadata (CLSIDs, timestamps, order) is kept
    via cfb_writer, so only stream *contents* differ.
    """
    report = {"in": in_path, "out": out_path, "streams": []}
    want = set(streams)
    want_part = set(partition_streams)
    with open_rvt(in_path) as doc:
        avail = {s.name for s in doc.streams()}
        missing = (want | want_part) - avail
        if missing:
            raise KeyError(f"streams not in file: {sorted(missing)}")
        new_data = {}
        for name in sorted(want):
            new_logical = regzip_logical(doc, name)
            new_raw = repage_like(new_logical, doc.raw(name), trailer_fn)
            new_data[name] = new_raw
            report["streams"].append({
                "name": name, "kind": "single",
                "raw_size": len(new_raw),
                "orig_raw_size": len(doc.raw(name)),
                "payload": len(doc.inflate(name, 0)),
                "full_page_trailers": (len(doc.raw(name)) // PAGE_STRIDE),
            })
        for name in sorted(want_part):
            new_logical = regzip_partition_logical(doc, name)
            new_raw = frame_pages(new_logical, trailer_fn)
            new_data[name] = new_raw
            report["streams"].append({
                "name": name, "kind": "partition",
                "raw_size": len(new_raw),
                "orig_raw_size": len(doc.raw(name)),
                "logical_size": len(new_logical),
                "orig_logical_size": len(doc.logical(name)),
                "blocks": len(doc.members(name)),
            })
    rewrite_entries(in_path, out_path, _swap_in(new_data))
    return report


def verify_readback(path: str) -> dict:
    """Sanity: our own reader can open the produced file and CRC-verify."""
    with open_rvt(path) as doc:
        bad, tot = 0, 0
        for s in doc.streams():
            for m in doc.members(s.name):
                tot += 1
                bad += 0 if m.crc_ok else 1
        return {"streams": len(doc.streams()), "members": tot, "crc_failures": bad}
