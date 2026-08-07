"""Byte-exact ENCODERS for the small structured streams the writer regenerates.

For each of the six "table" streams that any model edit invalidates we
provide a symmetric ``decode_<stream>() -> model dict`` and
``encode_<stream>(model) -> bytes`` pair.  The model is a plain, JSON-able
dict (no dataclasses) so it can be logged, diffed and hand-authored; the
encoder is the exact inverse of the decoder:  ``encode(decode(payload)) ==
payload`` byte-for-byte on all six corpus samples (see
``tests/test_stream_encoders.py`` and ``docs/streams/13-stream-encoders.md``).

Streams covered (payload = the INFLATED bytes, before gzip / page framing):

* ``Global/ElemTable``              (ElemTable, class 0x5c9)      prefix u64 0
* ``Global/History``                (DocumentHistory, 0x538)     prefix u64 1
* ``Global/DocumentIncrementTable`` (0x53c)                      prefix u64 1
* ``Global/PartitionTable``         (workset table, 0xc80)      prefix u64 0
* ``Contents``   (DocumentStorageIndexImpl 0x53e) — a 24-byte class-stream
  prologue + gzip, NOT the 8-byte Global prefix
* ``BasicFileInfo`` — raw (uncompressed) packed record + UTF-16 mirror

The 8-byte per-stream constant prefix that precedes the gzip member of
every ``Global/*`` stream is NOT part of the payload; it is handled by
``global_prefix()`` / ``wrap_global_stream()`` explicitly:
Latest=5, ContentDocuments=1, DocumentIncrementTable=1, History=1,
ElemTable=0, PartitionTable=0 (identical in all six samples, KNOWLEDGE.md
"Storage layering").

Framing a logical stream into 64,896-byte pages + 353-byte ECC trailers is
delegated to ``rvt.ecc.page_trailer`` (being cracked by another fleet); until
that module exists ``frame_stream()`` uses an explicit zero placeholder and
reports that the trailers are NOT valid.
"""
from __future__ import annotations

import struct
import uuid
import zlib
from typing import Any, Dict, List, Optional, Tuple

from . import elemtable as _elemtable
from . import meta as _meta
from .writer import gzip_member

# ---------------------------------------------------------------------------
# Global/* envelope: 8-byte per-stream-name constant prefix (u64 LE)
# ---------------------------------------------------------------------------

#: Per-stream-name u64 constant that precedes the gzip member of every
#: ``Global/*`` stream (identical in all six corpus files).
GLOBAL_STREAM_PREFIX: Dict[str, int] = {
    "Latest": 5,
    "ContentDocuments": 1,
    "DocumentIncrementTable": 1,
    "History": 1,
    "ElemTable": 0,
    "PartitionTable": 0,
}


def global_prefix(name: str) -> bytes:
    """The 8-byte constant prefix of ``Global/<name>`` (little-endian u64)."""
    key = name.split("/")[-1]
    if key not in GLOBAL_STREAM_PREFIX:
        raise KeyError(f"no known Global prefix constant for {name!r}")
    return struct.pack("<Q", GLOBAL_STREAM_PREFIX[key])


def wrap_global_stream(name: str, payload: bytes, level: int = 3) -> bytes:
    """LOGICAL stream bytes for ``Global/<name>``: prefix + gzip member.

    (No page framing / ECC — that is the ``frame_stream`` step.)
    """
    return global_prefix(name) + gzip_member(payload, level=level)


def _page_trailer(index: int, page: bytes, orig: Optional[bytes]) -> bytes:
    """ECC page trailer, delegated to ``rvt.ecc`` when it exists.

    Placeholder: 353 zero bytes (NOT accepted by Revit's reader — the ECC
    fleet's ``rvt.ecc.page_trailer(page) -> bytes`` replaces this).
    """
    try:  # pragma: no cover - depends on the ECC fleet's module landing
        from .ecc import page_trailer  # type: ignore
        return page_trailer(page)
    except ImportError:
        from .container import PAGE_TRAILER
        return b"\x00" * PAGE_TRAILER


def frame_stream(logical: bytes) -> Tuple[bytes, bool]:
    """Page-frame a logical stream. Returns ``(raw, trailers_valid)``.

    ``trailers_valid`` is False while ``rvt.ecc`` is unavailable (placeholder
    zero trailers).  Sub-page streams (<= 64,896 B) still carry a short final
    trailer region — mandatory per acceptance test V14.
    """
    from .writer import frame_pages
    try:  # pragma: no cover
        from .ecc import page_trailer  # noqa: F401
        valid = True
    except ImportError:
        valid = False
    return frame_pages(logical, _page_trailer), valid


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _W:
    """Little-endian byte writer (mirror of ``meta.Cursor``)."""

    __slots__ = ("b",)

    def __init__(self) -> None:
        self.b = bytearray()

    def u8(self, v: int) -> None:
        self.b.append(v & 0xFF)

    def u16(self, v: int) -> None:
        self.b += struct.pack("<H", v & 0xFFFF)

    def u32(self, v: int) -> None:
        self.b += struct.pack("<I", v & 0xFFFFFFFF)

    def i32(self, v: int) -> None:
        self.b += struct.pack("<i", v)

    def u64(self, v: int) -> None:
        self.b += struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF)

    def raw(self, v: bytes) -> None:
        self.b += v

    def ustr(self, s: str) -> None:
        """u32 UTF-16 code-unit count + UTF-16LE (Revit AString wire form)."""
        enc = s.encode("utf-16-le")
        self.u32(len(enc) // 2)
        self.b += enc

    def guid(self, g: str) -> None:
        """16-byte Windows mixed-endian GUID from its canonical string."""
        self.b += uuid.UUID(g).bytes_le

    def bytes(self) -> bytes:
        return bytes(self.b)


def _guid_str(raw: bytes) -> str:
    return str(uuid.UUID(bytes_le=raw))


# ---------------------------------------------------------------------------
# Global/ElemTable   (ElemTable object, class 0x5c9)
# ---------------------------------------------------------------------------
#
# payload = u16 class 0x5c9 | u32 N | N x 40-byte ElemRec (sorted by m_id)
#         | u32 graveyard_count(0) | u32 marker 0xffffffff | u16 class 0x96a
#         | u16 0 | u64 last-id watermark | u32 0

ELEMTABLE_FOOTER_LEN = 24


def decode_elemtable(payload: bytes) -> Dict[str, Any]:
    """Model dict for an inflated ``Global/ElemTable`` payload.

    Uses ``rvt.elemtable.parse_elemtable`` (the wave-1 decoder is lossless:
    header + fixed 40-byte records + 24-byte footer account for every byte).
    Records are stored as compact 7-tuples
    ``(original_id, creation_ep, modified_ep, user_modified_ep, id, owner_id,
    partition_id)`` in file (id-sorted) order.
    """
    t = _elemtable.parse_elemtable(payload)
    f = t.footer
    tail = payload[6 + 40 * t.count:]
    if len(tail) != ELEMTABLE_FOOTER_LEN or f.graveyard_count != 0:
        # never observed; a non-empty graveyard would need its own layout
        raise ValueError(
            f"ElemTable footer is {len(tail)} bytes / graveyard {f.graveyard_count}"
            " — GraveyardRec wire layout not observed in corpus")
    return {
        "stream": "ElemTable",
        "class_tag": t.class_tag,
        "records": [(r.original_id, r.creation_ep, r.modified_ep,
                     r.user_modified_ep, r.id, r.owner_id, r.partition_id)
                    for r in t.records],
        "graveyard_count": f.graveyard_count,
        "footer": {
            "marker": f.marker,          # observed 0xFFFFFFFF
            "tail_class": f.tail_class,  # observed 0x096a
            "tail_pad": f.tail_pad,      # observed 0
            "last_id": f.last_id,        # highest ElementId ever issued
            "tail_zero": f.tail_zero,    # observed 0
        },
    }


def encode_elemtable(model: Dict[str, Any]) -> bytes:
    """Inflated ``Global/ElemTable`` payload from the model (byte-exact)."""
    recs = model["records"]
    f = model["footer"]
    out = bytearray()
    out += struct.pack("<HI", model.get("class_tag", 0x05C9), len(recs))
    pack = struct.Struct(_elemtable.REC_FMT).pack
    for r in recs:
        out += pack(*r)
    out += struct.pack("<IIHHQI", model.get("graveyard_count", 0), f["marker"],
                       f["tail_class"], f.get("tail_pad", 0), f["last_id"],
                       f.get("tail_zero", 0))
    return bytes(out)


# ---------------------------------------------------------------------------
# Global/History   (DocumentHistory, class 0x538)
# ---------------------------------------------------------------------------
#
# +0x00 u16 0x538 | +0x02 u16 version(1) | +0x04 10 zero bytes
# +0x0e u32 entry count | +0x12 u32 0 | +0x16 GUID[5] (g,g,g,ZERO,g)
# +0x66 u32 nver | u32 versions[nver] | u32 nent | nent x (16-byte GUID + u8 tag)
# | trailing u32 0

def decode_history(payload: bytes) -> Dict[str, Any]:
    """Model dict for an inflated ``Global/History`` payload.

    Wraps ``rvt.content.parse_history`` and ADDS the two fields that decoder
    drops (they are constant zero in all six samples, but must be captured
    for a lossless inverse):

    * ``pad10``  — the 10 bytes at +0x04..0x0d (hex ``00``*10 in corpus)
    * ``pad_u32`` — the u32 at +0x12 (0 in corpus)
    """
    from .content import parse_history
    h = parse_history(payload)
    return {
        "stream": "History",
        "class_tag": h.class_tag,
        "version": h.version,
        "pad10": payload[0x04:0x0E].hex(),          # ADDED: 10 header pad bytes
        "hdr_count": h.hdr_count,
        "pad_u32": struct.unpack_from("<I", payload, 0x12)[0],  # ADDED
        "header_guids": [str(g) for g in h.header_guids],
        "format_versions": list(h.format_versions),
        "entries": [(str(e.guid), e.tag) for e in h.entries],
        "trailing": h.trailing.hex(),                 # u32 0 in corpus
    }


def encode_history(model: Dict[str, Any]) -> bytes:
    """Inflated ``Global/History`` payload from the model (byte-exact)."""
    w = _W()
    w.u16(model.get("class_tag", 0x0538))
    w.u16(model.get("version", 1))
    w.raw(bytes.fromhex(model.get("pad10", "00" * 10)))
    entries = model["entries"]
    w.u32(model.get("hdr_count", len(entries)))
    w.u32(model.get("pad_u32", 0))
    for g in model["header_guids"]:
        w.guid(g)
    fv = model["format_versions"]
    w.u32(len(fv))
    for v in fv:
        w.u32(v)
    w.u32(len(entries))
    for g, tag in entries:
        w.guid(g)
        w.u8(tag)
    w.raw(bytes.fromhex(model.get("trailing", "00000000")))
    return w.bytes()


# ---------------------------------------------------------------------------
# Global/DocumentIncrementTable   (class 0x53c)
# ---------------------------------------------------------------------------
#
# u16 0x53c | u32 N | N records | u32 N (again) | N records (copy 2) | 8 x 00

def _pack_increment_record(w: _W, r: Dict[str, Any]) -> None:
    w.u32(len(r["pairs"]))
    for k, v in r["pairs"]:
        w.i32(k)
        w.i32(v)
    w.ustr(r["username"])
    w.u32(r.get("unknown_zero_1", 0))
    w.u32(r["id_pair"][0])
    w.u32(r["id_pair"][1])
    w.u32(r.get("unknown_zero_2", 0))
    w.u32(r["timestamp"])
    w.u32(r["sequence"])
    w.u32(r["elem_id_repeat"])
    for c in r["counters"]:
        w.i32(c)
    w.i32(-1)                       # counters terminator
    w.u32(r["counter_g"])
    w.u8(r["flag"])


def decode_increment_table(payload: bytes) -> Dict[str, Any]:
    """Model dict for an inflated ``Global/DocumentIncrementTable`` payload.

    Wraps ``rvt.meta.parse_doc_increment`` and ADDS the second serialized copy
    of the table (``records2``) — the wave-1 decoder only recorded whether
    copy 2 equalled copy 1 (it does, in all six samples) and discarded it, so
    it could not be re-emitted losslessly.
    """
    d = _meta.parse_doc_increment(payload)
    c = _meta.Cursor(payload, d["table1_end"])
    count2 = c.u32()
    records2 = _meta._parse_increment_table(c, count2)   # ADDED: copy 2 kept
    trailer = payload[c.o:]

    def clean(r: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in r.items()
                if k in ("pairs", "username", "unknown_zero_1", "id_pair",
                         "unknown_zero_2", "timestamp", "sequence",
                         "elem_id_repeat", "counters", "counter_g", "flag")}

    return {
        "stream": "DocumentIncrementTable",
        "type_tag": d["type_tag"],
        "records": [clean(r) for r in d["records"]],
        "records2": [clean(r) for r in records2],
        "trailer": trailer.hex(),                    # 8 zero bytes in corpus
    }


def encode_increment_table(model: Dict[str, Any]) -> bytes:
    """Inflated ``Global/DocumentIncrementTable`` payload (byte-exact)."""
    w = _W()
    w.u16(model.get("type_tag", 0x053C))
    recs = model["records"]
    recs2 = model.get("records2", recs)
    w.u32(len(recs))
    for r in recs:
        _pack_increment_record(w, r)
    w.u32(len(recs2))
    for r in recs2:
        _pack_increment_record(w, r)
    w.raw(bytes.fromhex(model.get("trailer", "00" * 8)))
    return w.bytes()


# ---------------------------------------------------------------------------
# Global/PartitionTable   (workset table, class 0xc80)
# ---------------------------------------------------------------------------
#
# u16 0xc80 | u32 version(1) | u32 count | entries | (trailing, empty)
# entry = GUID(16) u32 0 u32 id_a u32 id_b i32 -1 u32 kind u8 flag
#         u32 nchars UTF-16 name  u32[5] tail words (1,1,0,1,0)

def decode_partition_table(payload: bytes) -> Dict[str, Any]:
    """Model dict for an inflated ``Global/PartitionTable`` payload
    (wraps ``rvt.partitions.parse_partition_table``; lossless already)."""
    from .partitions import parse_partition_table
    t = parse_partition_table(payload)
    return {
        "stream": "PartitionTable",
        "class_ordinal": t.class_ordinal,
        "version": t.version,
        "entries": [{
            "guid": _guid_str(e.guid),
            "zero0": e.zero0,
            "id_a": e.id_a,
            "id_b": e.id_b,
            "minus_one": e.minus_one,
            "kind": e.kind,
            "flag": e.tail[0],
            "name": e.name,
            "tail_words": list(e.tail[1:]),
        } for e in t.entries],
        "trailing": t.trailing.hex(),
    }


def encode_partition_table(model: Dict[str, Any]) -> bytes:
    """Inflated ``Global/PartitionTable`` payload (byte-exact)."""
    w = _W()
    w.u16(model.get("class_ordinal", 0x0C80))
    w.u32(model.get("version", 1))
    ents = model["entries"]
    w.u32(len(ents))
    for e in ents:
        w.guid(e["guid"])
        w.u32(e.get("zero0", 0))
        w.u32(e["id_a"])
        w.u32(e["id_b"])
        w.i32(e.get("minus_one", -1))
        w.u32(e["kind"])
        w.u8(e.get("flag", 0))
        w.ustr(e["name"])
        for v in e.get("tail_words", [1, 1, 0, 1, 0]):
            w.u32(v)
    w.raw(bytes.fromhex(model.get("trailing", "")))
    return w.bytes()


# ---------------------------------------------------------------------------
# Contents   (DocumentStorageIndexImpl, class 0x53e)
# ---------------------------------------------------------------------------
#
# Raw stream = 24-byte class-stream prologue (magic 0x05221962, u32 0x1c,
# u32 1, u32 0, magic, u32 class_ref) + gzip member + zero pad + stale slack.
# The INFLATED payload is a fixed-size record (240 B, +4+2n with a username).

CONTENTS_MAGIC = 0x05221962


def decode_contents_prologue(raw: bytes) -> Dict[str, Any]:
    """The 24-byte ``Contents`` class-stream prologue as a dict."""
    m1, v, n, z, m2, ref = struct.unpack_from("<IIIIII", raw, 0)
    if m1 != CONTENTS_MAGIC or m2 != CONTENTS_MAGIC:
        raise ValueError("bad Contents class-stream magic")
    return {"unknown_28": v, "count": n, "zero": z, "class_ref": ref}


def encode_contents_prologue(model: Dict[str, Any]) -> bytes:
    return struct.pack("<IIIIII", CONTENTS_MAGIC, model.get("unknown_28", 0x1C),
                       model.get("count", 1), model.get("zero", 0),
                       CONTENTS_MAGIC, model["class_ref"])


def decode_contents(payload: bytes) -> Dict[str, Any]:
    """Model dict for the INFLATED ``Contents`` payload.

    Independent, fully-lossless decoder (``meta.parse_contents`` folds several
    fields into anonymous ``misc_zeros`` / drops the 36-byte zero block, so it
    cannot be inverted).  Layout — see docs/streams/13-stream-encoders.md.
    """
    c = _meta.Cursor(payload)
    tag = c.u16()                    # 0x053e
    has_user = c.u32()               # 0 / 1
    username = c.ustr() if has_user else None
    zero_a = c.u32()
    zero_b = c.u32()
    partition = c.ustr()             # "GLOBAL"
    zero36 = c.bytes(36)             # 36 zero bytes (two nil GUIDs + u32 0)
    one = c.u32()                    # 1
    creation_guid = c.guid_binary()
    ws_marker = c.u16()              # 0xFFFF (no username) / 0x0000
    zero_c = c.u32()
    zero_d = c.u8()
    build = c.ustr()                 # "20250227_1515(x64)"
    hdr5 = [c.u32(), c.u32(), c.u32(), c.i32(), c.u32()]  # (7, a, b, -1, 3)
    one_b = c.u8()                   # 1
    zero_e = c.u16()                 # 0
    counters: List[int] = []
    while True:
        v = c.i32()
        if v == -1:
            break
        counters.append(v)
    counter_g = c.u32()
    trailing_pairs: List[Tuple[int, int]] = []
    while c.remaining() >= 6:
        if struct.unpack_from("<i", payload, c.o)[0] != -1:
            break
        c.i32()
        trailing_pairs.append((-1, c.u16()))
    tail = payload[c.o:]            # zero fill to the fixed record length
    return {
        "stream": "Contents",
        "type_tag": tag,
        "has_username": bool(has_user),
        "username": username,
        "zero_a": zero_a, "zero_b": zero_b,
        "partition_name": partition,
        "zero36": zero36.hex(),
        "one": one,
        "creation_guid": creation_guid,
        "worksharing_marker_u16": ws_marker,
        "zero_c": zero_c, "zero_d": zero_d,
        "build": build,
        "hdr5": hdr5,
        "one_b": one_b, "zero_e": zero_e,
        "counters": counters,
        "counter_g": counter_g,
        "trailing_pairs": trailing_pairs,
        "tail": tail.hex(),              # 28 zero bytes in every sample
    }


def encode_contents(model: Dict[str, Any]) -> bytes:
    """Inflated ``Contents`` payload from the model (byte-exact)."""
    w = _W()
    w.u16(model.get("type_tag", 0x053E))
    if model.get("has_username"):
        w.u32(1)
        w.ustr(model["username"])
    else:
        w.u32(0)
    w.u32(model.get("zero_a", 0))
    w.u32(model.get("zero_b", 0))
    w.ustr(model.get("partition_name", "GLOBAL"))
    w.raw(bytes.fromhex(model.get("zero36", "00" * 36)))
    w.u32(model.get("one", 1))
    w.guid(model["creation_guid"])
    w.u16(model.get("worksharing_marker_u16",
                    0 if model.get("has_username") else 0xFFFF))
    w.u32(model.get("zero_c", 0))
    w.u8(model.get("zero_d", 0))
    w.ustr(model.get("build", "20250227_1515(x64)"))
    for i, v in enumerate(model["hdr5"]):
        (w.i32 if i == 3 else w.u32)(v)
    w.u8(model.get("one_b", 1))
    w.u16(model.get("zero_e", 0))
    for v in model["counters"]:
        w.i32(v)
    w.i32(-1)
    w.u32(model["counter_g"])
    for _, ident in model.get("trailing_pairs", []):
        w.i32(-1)
        w.u16(ident)
    w.raw(bytes.fromhex(model.get("tail", "00" * 28)))
    return w.bytes()


def encode_contents_stream(prologue: Dict[str, Any], model: Dict[str, Any],
                           level: int = 3, total_size: Optional[int] = None) -> bytes:
    """RAW ``Contents`` stream: 24-byte prologue + gzip member (+ zero pad).

    The original files carry ~42 bytes of stale heap slack after the gzip
    trailer; that is not reproducible (nor read) — we zero-fill to
    ``total_size`` when given, else just append the gzip member.
    """
    body = encode_contents_prologue(prologue) + gzip_member(encode_contents(model), level=level)
    if total_size is not None:
        if len(body) > total_size:
            raise ValueError(f"Contents body {len(body)} > requested {total_size}")
        body += b"\x00" * (total_size - len(body))
    return body


# ---------------------------------------------------------------------------
# BasicFileInfo   (raw, uncompressed)
# ---------------------------------------------------------------------------
#
# packed binary record (u32/u16/u8 scalars + u32-count UTF-16 strings), then
# ASCII CRLF + UTF-16LE "key: value" mirror text + ASCII CRLF.

#: Ordered (label, formatter) pairs for the human-readable mirror block.
_BFI_MIRROR: List[Tuple[str, str]] = [
    ("Worksharing", "worksharing_text"),
    ("Username", "username"),
    ("Central Model Path", "central_model_path"),
    ("Format", "format"),
    ("Build", "build"),
    ("Last Save Path", "last_save_path"),
    ("Open Workset Default", "open_workset_default"),
    ("Project Spark File", "project_spark_file"),
    ("Central Model Identity", "central_model_identity"),
    ("Locale when saved", "locale"),
    ("All Local Changes Saved To Central", "all_local_changes_saved_to_central"),
    ("Central model's version number corresponding to the last reload latest",
     "central_version_number"),
    ("Central model's episode GUID corresponding to the last reload latest",
     "central_episode_guid"),
    ("Unique Document GUID", "unique_document_guid"),
    ("Unique Document Increments", "unique_document_increments"),
    ("Model Identity", "model_identity"),
    ("IsSingleUserCloudModel", "is_single_user_cloud_model_text"),
    ("Author", "author"),
    ("ClientAppName", "client_app_name"),
]


def decode_basic_file_info(raw: bytes) -> Dict[str, Any]:
    """Model dict for the raw ``BasicFileInfo`` stream.

    Wraps ``rvt.meta.parse_basic_file_info`` and flattens it into the exact
    field set the encoder needs.  ADDED for losslessness: the raw
    ``mirror_text`` is retained and the derived ``worksharing_text`` /
    ``is_single_user_cloud_model_text`` strings are captured, because the
    binary→text mapping for worksharing-enabled files is unobserved (all six
    corpus files are "Not enabled").
    """
    b = _meta.parse_basic_file_info(raw)
    g = b["guids"]
    kv = b["mirror_kv"]
    return {
        "stream": "BasicFileInfo",
        "structure_version": b["structure_version"],
        "worksharing_state": b["worksharing_state"],
        "worksharing_text": kv.get("Worksharing", "Not enabled"),
        "username": b["username"],
        "central_model_path": b["central_model_path"],
        "format": b["format"],
        "build": b["build"],
        "last_save_path": b["last_save_path"],
        "open_workset_default": b["open_workset_default"],
        "project_spark_file": b["project_spark_file"],
        "central_model_identity": g["central_model_identity"],
        "locale": b["locale"],
        "all_local_changes_saved_to_central": b["all_local_changes_saved_to_central"],
        "central_version_number": b["central_version_number"],
        "central_episode_guid": g["central_episode_guid"],
        "unique_document_guid": g["unique_document_guid"],
        "unique_document_increments": b["unique_document_increments"],
        "model_identity": g["model_identity"],
        "is_single_user_cloud_model": bool(b["is_single_user_cloud_model"]),
        "is_single_user_cloud_model_text": kv.get(
            "IsSingleUserCloudModel", "True" if b["is_single_user_cloud_model"] else "False"),
        "author": b["author"],
        "client_app_name": b["client_app_name"],
        "mirror_text": b["mirror_text"],
    }


def basic_file_info_mirror_text(model: Dict[str, Any]) -> str:
    """Regenerate the UTF-16 "key: value" mirror block from the fields.

    Reproduces the corpus text byte-for-byte for all six samples (verified by
    ``test_stream_encoders``); lines are joined by CRLF (encoded UTF-16LE).
    """
    lines = []
    for label, key in _BFI_MIRROR:
        lines.append(f"{label}: {model[key]}")
    return "\r\n".join(lines)


def encode_basic_file_info(model: Dict[str, Any],
                           regenerate_mirror: bool = True) -> bytes:
    """Raw ``BasicFileInfo`` stream bytes from the model (byte-exact).

    ``regenerate_mirror=True`` rebuilds the human-readable mirror block from
    the field values (what a writer changing e.g. ``last_save_path`` needs);
    ``False`` re-emits the stored ``mirror_text`` verbatim.
    """
    w = _W()
    w.u32(model.get("structure_version", 14))
    w.u16(model.get("worksharing_state", 0))
    w.ustr(model.get("username", ""))
    w.ustr(model.get("central_model_path", ""))
    w.ustr(model["format"])
    w.ustr(model["build"])
    w.ustr(model["last_save_path"])
    w.u32(model.get("open_workset_default", 3))
    w.u8(model.get("project_spark_file", 0))
    w.ustr(model["central_model_identity"])
    w.ustr(model.get("locale", "ENU"))
    w.u8(model.get("all_local_changes_saved_to_central", 0))
    w.u32(model["central_version_number"])
    w.ustr(model["central_episode_guid"])
    w.ustr(model["unique_document_guid"])
    w.ustr(str(model["unique_document_increments"]))
    w.ustr(model["model_identity"])
    w.u8(1 if model.get("is_single_user_cloud_model") else 0)
    w.ustr(model.get("author", "Autodesk Revit"))
    w.ustr(model.get("client_app_name", "RevitApplication"))
    text = basic_file_info_mirror_text(model) if regenerate_mirror else model["mirror_text"]
    w.raw(b"\r\n" + text.encode("utf-16-le") + b"\r\n")
    return w.bytes()


# ---------------------------------------------------------------------------
# Uniform front door
# ---------------------------------------------------------------------------

#: name -> (decoder, encoder, kind).  kind 'payload' = inflated Global/*
#: payload; 'raw' = whole raw stream; 'contents' = inflated Contents payload.
CODECS = {
    "ElemTable": (decode_elemtable, encode_elemtable, "payload"),
    "History": (decode_history, encode_history, "payload"),
    "DocumentIncrementTable": (decode_increment_table, encode_increment_table, "payload"),
    "PartitionTable": (decode_partition_table, encode_partition_table, "payload"),
    "Contents": (decode_contents, encode_contents, "contents"),
    "BasicFileInfo": (decode_basic_file_info, encode_basic_file_info, "raw"),
}


def roundtrip(name: str, data: bytes) -> Tuple[bool, bytes]:
    """decode -> encode -> compare. Returns ``(byte_exact, encoded)``."""
    dec, enc, _ = CODECS[name]
    out = enc(dec(data))
    return out == data, out


# ---------------------------------------------------------------------------
# demo / __main__ : per-stream x per-file round-trip pass matrix
# ---------------------------------------------------------------------------

def _sample_bytes(sample: str, name: str) -> Optional[bytes]:
    import os
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "extracted")
    root = os.path.normpath(os.path.join(root, sample))
    _, _, kind = CODECS[name]
    if kind == "payload":
        p = os.path.join(root, f"Global__{name}.gz", "000.bin")
    elif kind == "contents":
        p = os.path.join(root, "Contents.gz", "000.bin")
    else:
        p = os.path.join(root, f"{name}.bin")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as fh:
        return fh.read()


def matrix() -> Dict[str, Dict[str, str]]:
    from .meta import SAMPLES
    result: Dict[str, Dict[str, str]] = {}
    for name in CODECS:
        row: Dict[str, str] = {}
        for s in SAMPLES:
            data = _sample_bytes(s, name)
            if data is None:
                row[s] = "MISSING"
                continue
            try:
                ok, _ = roundtrip(name, data)
                row[s] = "PASS" if ok else "FAIL"
            except Exception as e:  # pragma: no cover
                row[s] = f"ERR:{type(e).__name__}"
        result[name] = row
    return result


if __name__ == "__main__":
    from .meta import SAMPLES
    m = matrix()
    short = [s.replace("sampleproject", "").replace("sample-project", "") for s in SAMPLES]
    print(f"{'stream':24s} " + " ".join(f"{x:>8s}" for x in short))
    for name, row in m.items():
        print(f"{name:24s} " + " ".join(f"{row[s]:>8s}" for s in SAMPLES))
