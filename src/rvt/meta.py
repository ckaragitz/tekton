"""Decoders for the small/metadata streams of a Revit 2026 ``.rvt``.

Covers the six "housekeeping" streams that sit beside the big object
graph:

* ``BasicFileInfo``   -> :func:`parse_basic_file_info`
* ``Contents``        -> :func:`parse_contents`
* ``TransmissionData``-> :func:`parse_transmission`
* ``ProjectInformation`` (a ZIP holding an Autodesk *PartAtom* Atom entry)
                       -> :func:`parse_project_info`
* ``RevitPreview4.0``  -> :func:`extract_preview`
* ``Global/DocumentIncrementTable`` -> :func:`parse_doc_increment`

All functions take the *raw stream bytes* (as dumped by ``tools/extract.py``
into ``extracted/<file>/<Stream>.bin``) and return plain dicts / dataclasses.
Every layout claim is documented in ``docs/streams/02-metadata.md``; fields
that are still guesses are named ``unknown_*`` or carry a ``[hypothesis]``
note in the doc.

Run ``python -m rvt.meta`` (or ``python src/rvt/meta.py``) to dump every
metadata stream of every extracted sample project.
"""
from __future__ import annotations

import io
import json
import os
import re
import struct
import sys
import uuid
import zlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

#: 4-byte magic that opens every "class-serialized" stream
#: (``Contents``, ``RevitPreview4.0``): bytes ``62 19 22 05``.
CLASS_STREAM_MAGIC = 0x05221962

#: gzip magic.
GZIP_MAGIC = b"\x1f\x8b\x08"


class Cursor:
    """Little-endian byte cursor with the primitives Revit's serializer uses."""

    __slots__ = ("b", "o")

    def __init__(self, b: bytes, o: int = 0):
        self.b = b
        self.o = o

    def u8(self) -> int:
        v = self.b[self.o]
        self.o += 1
        return v

    def u16(self) -> int:
        (v,) = struct.unpack_from("<H", self.b, self.o)
        self.o += 2
        return v

    def u32(self) -> int:
        (v,) = struct.unpack_from("<I", self.b, self.o)
        self.o += 4
        return v

    def i32(self) -> int:
        (v,) = struct.unpack_from("<i", self.b, self.o)
        self.o += 4
        return v

    def f64(self) -> float:
        (v,) = struct.unpack_from("<d", self.b, self.o)
        self.o += 8
        return v

    def bytes(self, n: int) -> bytes:
        v = self.b[self.o:self.o + n]
        self.o += n
        return v

    def ustr(self) -> str:
        """u32 char-count prefix, then UTF-16LE (no terminator)."""
        n = self.u32()
        s = self.b[self.o:self.o + 2 * n].decode("utf-16le")
        self.o += 2 * n
        return s

    def guid_binary(self) -> str:
        """16-byte binary GUID in Windows mixed-endian layout."""
        raw = self.bytes(16)
        return str(uuid.UUID(bytes_le=raw))

    def remaining(self) -> int:
        return len(self.b) - self.o


def raw_inflate_after_gzip_header(data: bytes, off: int) -> Tuple[bytes, int]:
    """Inflate the gzip member starting at ``off`` (Revit style).

    Revit's gzip trailers are frequently corrupt, so the project convention is
    to skip the 10-byte header and raw-inflate (``wbits=-15``).  Returns
    ``(payload, end_offset)`` where ``end_offset`` is the offset just after the
    deflate stream (i.e. where the CRC32/ISIZE trailer would begin).
    """
    assert data[off:off + 3] == GZIP_MAGIC, "not a gzip member"
    d = zlib.decompressobj(-zlib.MAX_WBITS)
    out = d.decompress(data[off + 10:]) + d.flush()
    end = len(data) - len(d.unused_data)
    return out, end


# ---------------------------------------------------------------------------
# BasicFileInfo
# ---------------------------------------------------------------------------

#: The two ``BasicFileInfo`` layouts Revit has shipped, told apart by their
#: UTF-16LE mirror-text markers (public prior art: docs/prior-art.md P1/P3 --
#: the Archive Team era table and the DROID container signatures).  The
#: markers are searched as raw byte substrings, so the odd byte offset the
#: mirror text lands at (see :func:`parse_basic_file_info`) does not matter.
BFI_ERA_2019 = "2019+"          # 'Format: 20xx' -- the layout parse_basic_file_info decodes
BFI_ERA_2008 = "2008-2018"      # 'Revit Build: <product> 20xx (Build: ...)' -- never read by tekton
BFI_ERA_UNKNOWN = "unknown"      # neither marker: not a BasicFileInfo we can classify
_ERA_MARKERS = (("Format:".encode("utf-16le"), BFI_ERA_2019),
                ("Revit Build:".encode("utf-16le"), BFI_ERA_2008))
_ERA_YEAR_WINDOW = 256           # bytes of UTF-16LE text scanned after a marker for the year
_YEAR_ON_LINE = re.compile(r"[^\r\n]*?(20\d{2})")   # first 20xx before the line ends


def _year_after(data: bytes, at: int) -> Optional[int]:
    """First ``20xx`` in the UTF-16LE text starting at byte ``at``, on that
    mirror line only, else None."""
    m = _YEAR_ON_LINE.match(data[at:at + _ERA_YEAR_WINDOW].decode("utf-16le", errors="replace"))
    return int(m.group(1)) if m else None


def classify_bfi_era(raw: bytes) -> Dict[str, Any]:
    """Which ``BasicFileInfo`` era a raw stream belongs to, and the release
    year it declares -- WITHOUT assuming the 2019+ binary layout.

    Returns ``{'era': '2019+' | '2008-2018' | 'unknown', 'year': int | None}``:

    * ``'2019+'``     -- the mirror text carries ``Format: 20xx`` (Revit 2019
      and newer; the layout :func:`parse_basic_file_info` decodes).  ``year``
      is that number (None if the marker has no year after it).
    * ``'2008-2018'`` -- no ``Format:`` but a ``Revit Build: ... 20xx ...``
      line (the Revit 2008-2018 layout tekton has never read).  ``year`` is
      the first ``20xx`` on that line, if any.
    * ``'unknown'``   -- neither marker (empty / truncated / not a
      BasicFileInfo stream at all); ``year`` None.

    Total: never raises, whatever the bytes.
    """
    data = bytes(raw or b"")
    for marker, era in _ERA_MARKERS:                # 'Format:' wins when both appear
        i = data.find(marker)
        if i != -1:
            return {"era": era, "year": _year_after(data, i + len(marker))}
    return {"era": BFI_ERA_UNKNOWN, "year": None}


def parse_basic_file_info(data: bytes) -> Dict[str, Any]:
    """Decode ``BasicFileInfo``.

    The stream is a packed binary record (UTF-16LE strings each prefixed by a
    u32 character count, interleaved with u8/u16/u32 scalars), followed by an
    ASCII ``\\r\\n``, a human-readable UTF-16LE "key: value" mirror of the same
    fields, and a final ASCII ``\\r\\n``.  Because the binary section contains
    single u8 flags, the mirror text lands at an odd byte offset, which is why
    naively decoding the whole stream as UTF-16 yields garbage in the middle.
    """
    c = Cursor(data)
    layout: List[Dict[str, Any]] = []

    def rec(name: str, off: int, size: int, typ: str, value: Any) -> None:
        layout.append(dict(field=name, offset=off, size=size, type=typ,
                           value=value if not isinstance(value, str) or len(str(value)) < 200 else str(value)[:60] + "..."))

    o = c.o
    version = c.u32()                       # observed 14 in every 2026 file
    rec("structure_version", o, 4, "u32", version)

    # 10 zero bytes in every sample: [hypothesis] worksharing state (2 bytes)
    # then two empty length-prefixed strings (Username, Central Model Path).
    o = c.o
    ws_state = c.u16()
    rec("worksharing_state", o, 2, "u16", ws_state)
    o = c.o
    username = c.ustr()
    rec("username", o, c.o - o, "ustr", username)
    o = c.o
    central_path = c.ustr()
    rec("central_model_path", o, c.o - o, "ustr", central_path)

    o = c.o; fmt = c.ustr(); rec("format", o, c.o - o, "ustr", fmt)
    o = c.o; build = c.ustr(); rec("build", o, c.o - o, "ustr", build)
    o = c.o; path = c.ustr(); rec("last_save_path", o, c.o - o, "ustr", path)
    o = c.o; ows = c.u32(); rec("open_workset_default", o, 4, "u32", ows)
    o = c.o; spark = c.u8(); rec("project_spark_file", o, 1, "u8", spark)
    o = c.o; central_identity = c.ustr(); rec("central_model_identity", o, c.o - o, "ustr(guid)", central_identity)
    o = c.o; locale = c.ustr(); rec("locale_when_saved", o, c.o - o, "ustr", locale)
    o = c.o; all_saved = c.u8(); rec("all_local_changes_saved_to_central", o, 1, "u8", all_saved)
    o = c.o; central_version = c.u32(); rec("central_version_number", o, 4, "u32", central_version)
    o = c.o; episode_guid = c.ustr(); rec("central_episode_guid", o, c.o - o, "ustr(guid)", episode_guid)
    o = c.o; unique_guid = c.ustr(); rec("unique_document_guid", o, c.o - o, "ustr(guid)", unique_guid)
    o = c.o; increments = c.ustr(); rec("unique_document_increments", o, c.o - o, "ustr(int)", increments)
    o = c.o; model_identity = c.ustr(); rec("model_identity", o, c.o - o, "ustr(guid)", model_identity)
    o = c.o; single_cloud = c.u8(); rec("is_single_user_cloud_model", o, 1, "u8", single_cloud)
    o = c.o; author = c.ustr(); rec("author", o, c.o - o, "ustr", author)
    o = c.o; app = c.ustr(); rec("client_app_name", o, c.o - o, "ustr", app)

    text_off = c.o
    # ASCII CRLF, UTF-16LE mirror text, ASCII CRLF.
    tail = data[c.o:]
    text = ""
    if tail.startswith(b"\r\n"):
        body = tail[2:]
        if body.endswith(b"\r\n"):
            body = body[:-2]
        text = body.decode("utf-16le", errors="replace")
    rec("mirror_text", text_off, len(tail), "crlf+utf16le+crlf", f"{len(text)} chars")

    kv: Dict[str, str] = {}
    for line in text.split("\r\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()

    return {
        "structure_version": version,
        "worksharing_state": ws_state,
        "worksharing": kv.get("Worksharing", "Not enabled" if ws_state == 0 else str(ws_state)),
        "username": username,
        "central_model_path": central_path,
        "format": fmt,
        "version": fmt,
        "build": build,
        "path": path,
        "last_save_path": path,
        "open_workset_default": ows,
        "project_spark_file": spark,
        "locale": locale,
        "all_local_changes_saved_to_central": all_saved,
        "central_version_number": central_version,
        "unique_document_increments": increments,
        "is_single_user_cloud_model": bool(single_cloud),
        "author": author,
        "client_app_name": app,
        "guids": {
            "central_model_identity": central_identity,
            "central_episode_guid": episode_guid,
            "unique_document_guid": unique_guid,
            "model_identity": model_identity,
        },
        "mirror_text": text,
        "mirror_kv": kv,
        "layout": layout,
        "stream_size": len(data),
        "parsed_binary_bytes": text_off,
    }


# ---------------------------------------------------------------------------
# Contents  (class-stream wrapper -> gzip -> fixed-size record)
# ---------------------------------------------------------------------------

def parse_class_stream_header(data: bytes) -> Dict[str, Any]:
    """Decode the 24-byte prologue shared by ``Contents`` and
    ``RevitPreview4.0``::

        +0x00 u32  0x05221962 magic
        +0x04 u32  0x1c (28)         [hypothesis: header/record-format version]
        +0x08 u32  1                 [hypothesis: object count]
        +0x0c u32  0
        +0x10 u32  0x05221962 magic (record start)
        +0x14 u32  class_ref         (0x8000 flag set = inline class definition
                                      follows, low bits = class index;
                                      no flag = index of an already-known
                                      class, varies per document)
    """
    c = Cursor(data)
    m1, v, n, z, m2, ref = struct.unpack_from("<IIIIII", data, 0)
    return {
        "magic_ok": m1 == CLASS_STREAM_MAGIC and m2 == CLASS_STREAM_MAGIC,
        "magic": f"0x{m1:08x}",
        "unknown_28": v,
        "count": n,
        "zero": z,
        "class_ref": ref,
        "class_ref_defines_inline": bool(ref & 0x8000),
        "class_ref_index": ref & 0x7FFF,
        "payload_offset": 24,
    }


def parse_contents(data: bytes) -> Dict[str, Any]:
    """Decode the ``Contents`` stream.

    Wrapper = 24-byte class-stream prologue (``62 19 22 05`` ...), then one
    proper gzip member (its CRC32/ISIZE trailer is VALID here), then a few
    zero bytes and ~42 bytes of stale slack.  The inflated payload is a small
    record: u16 type tag 0x053E, optional owner user name, the partition name
    ``GLOBAL``, the document's creation GUID, the writing build string, and a
    trailing block of per-increment counters that mirrors the last record of
    ``Global/DocumentIncrementTable``.
    """
    hdr = parse_class_stream_header(data)
    payload, gz_end = raw_inflate_after_gzip_header(data, 24)
    trailer = data[gz_end:gz_end + 8]
    crc_ok = size_ok = None
    if len(trailer) == 8:
        crc, isize = struct.unpack("<II", trailer)
        crc_ok = crc == (zlib.crc32(payload) & 0xFFFFFFFF)
        size_ok = isize == len(payload)
    slack = data[gz_end + 8:]

    c = Cursor(payload)
    tag = c.u16()                          # 0x053E in every sample
    has_user = c.u32()                     # 0/1
    user = c.ustr() if has_user else None  # e.g. "Steven Campbell"
    unk_zero1 = c.u32()
    unk_zero2 = c.u32()
    partition = c.ustr()                   # "GLOBAL"
    zero36 = c.bytes(36)                   # 36 zero bytes ([hypothesis] two
                                           # nil binary GUIDs + u32 0)
    one = c.u32()                          # observed 1
    creation_guid = c.guid_binary()        # e3e052f8-0156-11d5-9301-0000863f27ad
                                           # in the RAC/RME/RST-basic templates
    ws_marker = c.u16()                    # 0xFFFF (files without user) or 0
    unk_zero3 = c.u32()
    unk_u8 = c.u8()                        # 0
    build = c.ustr()                       # "20250227_1515(x64)"
    # trailing per-increment block (fixed layout, mirrors the DIT last record)
    hdr5 = [c.u32(), c.u32(), c.u32(), c.i32(), c.u32()]  # (7, a, b, -1, 3)
    unk_u8_2 = c.u8()                      # 1
    unk_u16 = c.u16()                      # 0
    counters: List[int] = []
    while True:
        v = c.i32()
        if v == -1:
            break
        counters.append(v)
    g = c.u32()                            # same value as DIT last-record G
    # two more (i32 -1, u16 id) pairs: constant 1420 / 1426 in every sample
    trailing_pairs: List[Tuple[int, int]] = []
    while c.remaining() >= 6:
        marker = struct.unpack_from("<i", payload, c.o)[0]
        if marker != -1:
            break
        c.i32()
        trailing_pairs.append((-1, c.u16()))
    fixed_tail_zero = payload[c.o:]        # zero fill; payload has fixed size
    return {
        "header": hdr,
        "gzip": {
            "payload_size": len(payload),
            "gzip_end": gz_end,
            "trailer_crc_ok": crc_ok,
            "trailer_isize_ok": size_ok,
            "slack_bytes": len(slack),
        },
        "type_tag": tag,
        "has_username": bool(has_user),
        "username": user,
        "partition_name": partition,
        "creation_guid": creation_guid,
        "worksharing_marker_u16": ws_marker,
        "build": build,
        "unknown_hdr5": hdr5,
        "counters": counters,
        "counter_g": g,
        "trailing_pairs": trailing_pairs,
        "tail_zero_bytes": len(fixed_tail_zero),
        "tail_all_zero": all(x == 0 for x in fixed_tail_zero),
        "misc_zeros": [unk_zero1, unk_zero2, unk_zero3, unk_u8, unk_u8_2, unk_u16, one],
    }


# ---------------------------------------------------------------------------
# TransmissionData
# ---------------------------------------------------------------------------

def parse_transmission(data: bytes) -> Dict[str, Any]:
    """Decode ``TransmissionData``: u32 UTF-16 char count + UTF-16LE XML."""
    (nchars,) = struct.unpack_from("<I", data, 0)
    xml_text = data[4:4 + 2 * nchars].decode("utf-16le")
    size_ok = 4 + 2 * nchars == len(data)
    result: Dict[str, Any] = {
        "char_count": nchars,
        "size_ok": size_ok,
        "xml": xml_text,
        "references": [],
    }
    import xml.etree.ElementTree as ET     # deferred: imported locally by the two parsers (#747)
    try:
        root = ET.fromstring(xml_text)
        result["is_transmitted"] = root.get("isTransmitted")
        result["user_data"] = root.get("userData")
        result["version"] = root.get("version")
        for ref in root.findall("ExternalFileReference"):
            result["references"].append({child.tag: (child.text or "") for child in ref})
    except ET.ParseError as ex:  # pragma: no cover - never seen in corpus
        result["xml_error"] = str(ex)
    return result


# ---------------------------------------------------------------------------
# ProjectInformation  (ZIP -> Atom "PartAtom" XML)
# ---------------------------------------------------------------------------

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "A": "urn:schemas-autodesk-com:partatom",
}


def parse_project_info(data: bytes) -> Dict[str, Any]:
    """Decode ``ProjectInformation``: a ZIP archive with one member, an
    Autodesk *PartAtom* (Atom-syntax) XML document describing the model and its
    Project Information parameters."""
    import xml.etree.ElementTree as ET     # deferred: imported locally by the two parsers (#747)
    import zipfile
    zf = zipfile.ZipFile(io.BytesIO(data))
    members = []
    xml_bytes = b""
    for zi in zf.infolist():
        payload = zf.read(zi)
        members.append({
            "filename": zi.filename,
            "compress_type": zi.compress_type,
            "compressed_size": zi.compress_size,
            "file_size": zi.file_size,
            "dos_date_time": list(zi.date_time),
            "flag_bits": zi.flag_bits,
            "create_system": zi.create_system,
        })
        if payload.lstrip().startswith(b"<?xml") or zi.filename.endswith(".xml"):
            xml_bytes = payload
    out: Dict[str, Any] = {"members": members, "xml": xml_bytes.decode("utf-8", "replace")}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as ex:  # pragma: no cover
        out["xml_error"] = str(ex)
        return out
    a = "{urn:schemas-autodesk-com:partatom}"
    atom = "{http://www.w3.org/2005/Atom}"
    out["title"] = root.findtext(f"{atom}title")
    out["updated"] = root.findtext(f"{atom}updated")
    out["taxonomies"] = [
        {"term": t.findtext(f"{atom}term"), "label": t.findtext(f"{atom}label")}
        for t in root.findall(f"{a}taxonomy")
    ]
    link = root.find(f"{atom}link")
    if link is not None:
        df = link.find(f"{a}design-file")
        out["link"] = {
            "rel": link.get("rel"), "type": link.get("type"), "href": link.get("href"),
            "design_file": {
                "title": df.findtext(f"{a}title"),
                "product": df.findtext(f"{a}product"),
                "product_version": df.findtext(f"{a}product-version"),
                "updated": df.findtext(f"{a}updated"),
            } if df is not None else None,
        }
    # Project Information parameters, grouped
    params: Dict[str, Dict[str, Any]] = {}
    groups: List[Dict[str, Any]] = []
    for feature in root.findall(f".//{a}feature"):
        for group in feature.findall(f"{a}group"):
            gtitle = group.findtext(f"{a}title") or ""
            gparams = []
            for p in list(group):
                if p.tag == f"{a}title":
                    continue
                name = p.tag.split("}")[-1]
                entry = {
                    "name": name,
                    "display_name": p.get("displayName", name.replace("_", " ")),
                    "kind": p.get("type"),          # system | shared
                    "guid": p.get("id"),            # shared-parameter GUID
                    "value_type": p.get("typeOfParameter"),
                    "value": p.text or "",
                    "group": gtitle,
                }
                gparams.append(entry)
                params[name] = entry
            groups.append({"title": gtitle, "parameters": gparams})
    out["groups"] = groups
    out["parameters"] = params
    # convenient standard fields
    for key, name in (("project_name", "Project_Name"), ("project_number", "Project_Number"),
                      ("client_name", "Client_Name"), ("project_address", "Project_Address"),
                      ("project_status", "Project_Status"), ("issue_date", "Project_Issue_Date"),
                      ("author", "Author"), ("organization_name", "Organization_Name"),
                      ("building_name", "Building_Name")):
        if name in params:
            out[key] = params[name]["value"]
    return out


# ---------------------------------------------------------------------------
# RevitPreview4.0  (class-stream, uncompressed, embeds a PNG)
# ---------------------------------------------------------------------------

_TYPE_NAMES = {0x04: "int32", 0x07: "double", 0x0e: "object_ref", 0x02: "byte"}


def _read_class_def(c: Cursor) -> Dict[str, Any]:
    """Read one inline class definition (same record shape as
    ``Formats/Latest``): u16 name length + ASCII name, u16 0, u32 version,
    u32 field count, then per field: u32 name length + ASCII name + type
    descriptor."""
    nlen = c.u16()
    name = c.bytes(nlen).decode("ascii")
    pad = c.u16()
    version = c.u32()
    nfields = c.u32()
    fields = []
    for _ in range(nfields):
        flen = c.u32()
        fname = c.bytes(flen).decode("ascii")
        tcode = c.u16()          # low byte = base type, 0x50xx = array
        textra = c.u16()
        fdesc: Dict[str, Any] = {
            "name": fname,
            "type_code": tcode,
            "type_extra": textra,
            "base_type": _TYPE_NAMES.get(tcode & 0xFF, hex(tcode & 0xFF)),
            "is_array": bool(tcode & 0x5000),
        }
        if (tcode & 0xFF) == 0x0E:      # object reference: u32 0 + i32 target
            fdesc["ref_zero"] = c.u32()
            fdesc["ref_target"] = c.i32()
        fields.append(fdesc)
    return {"name": name, "pad": pad, "version": version, "fields": fields}


def extract_preview(data: bytes, out_png: Optional[str] = None) -> Dict[str, Any]:
    """Decode ``RevitPreview4.0`` and (optionally) write the embedded PNG.

    Layout: 24-byte class-stream prologue; inline class definitions for
    ``FilePreview`` (class ref 0x800C) and ``ARasterImage`` (0x800D); then
    the ``ARasterImage`` instance: u32 0 [hypothesis: instance header],
    ``m_compressedImage`` (u32 byte length + PNG bytes), ``m_dpiX``,
    ``m_dpiY``, ``m_widthInFeet``, ``m_heightInFeet`` (f64) and
    ``m_width``, ``m_height`` (i32).  Consumes the stream exactly.
    """
    hdr = parse_class_stream_header(data)
    c = Cursor(data, 24)
    classes = []
    # first class def belongs to hdr["class_ref"]
    classes.append({"class_ref": hdr["class_ref"], **_read_class_def(c)})
    # subsequent inline definitions are introduced by their own u32 class_ref
    while True:
        peek = struct.unpack_from("<I", data, c.o)[0]
        if peek & 0x8000 and (peek & 0x7FFF) < 0x1000 and data[c.o + 6:c.o + 7].isalpha():
            ref = c.u32()
            classes.append({"class_ref": ref, **_read_class_def(c)})
        else:
            break
    instance_prologue = c.u32()            # 0
    png_len = c.u32()
    png_off = c.o
    png = c.bytes(png_len)
    dpi_x, dpi_y, w_ft, h_ft = c.f64(), c.f64(), c.f64(), c.f64()
    width, height = c.i32(), c.i32()
    dims = None
    if png[:8] == b"\x89PNG\r\n\x1a\n" and png[12:16] == b"IHDR":
        w, h = struct.unpack_from(">II", png, 16)
        dims = (w, h)
    if out_png:
        os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
        with open(out_png, "wb") as fh:
            fh.write(png)
    return {
        "header": hdr,
        "classes": classes,
        "instance_prologue": instance_prologue,
        "png_offset": png_off,
        "png_length": png_len,
        "png_dimensions": dims,
        "dpi": (dpi_x, dpi_y),
        "size_feet": (w_ft, h_ft),
        "size_px": (width, height),
        "consumed": c.o,
        "stream_size": len(data),
        "png_path": out_png,
    }


# ---------------------------------------------------------------------------
# Global/DocumentIncrementTable
# ---------------------------------------------------------------------------

def _parse_increment_table(c: Cursor, count: int) -> List[Dict[str, Any]]:
    recs = []
    for _ in range(count):
        start = c.o
        npairs = c.u32()
        pairs = [(c.i32(), c.i32()) for _ in range(npairs)]
        user = c.ustr()
        zero1 = c.u32()
        id_a = c.u32()
        id_b = c.u32()
        zero2 = c.u32()
        ts = c.u32()
        seq = c.u32()
        elem_id = c.u32()
        counters: List[int] = []
        while True:
            v = c.i32()
            if v == -1:
                break
            counters.append(v)
        g = c.u32()
        flag = c.u8()
        recs.append({
            "offset": start,
            "pairs": pairs,                # first pair key is always -1
            "primary_id": pairs[0][1] if pairs else None,   # [hypothesis] ElementId
            "extra_pairs": pairs[1:],      # [hypothesis] EpisodeId -> count
            "username": user,
            "unknown_zero_1": zero1,
            "id_pair": (id_a, id_b),       # consecutive ids (b == a + 1)
            "unknown_zero_2": zero2,
            "timestamp": ts,
            "time_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
            "sequence": seq,               # 1..N increment number
            "elem_id_repeat": elem_id,     # == primary_id in the newest record, else 0
            "counters": counters,          # 10 monotone int32 watermarks
            "counter_g": g,                # +1 per record
            "flag": flag,                  # 1 = ordinary save [hypothesis]
        })
    return recs


def parse_doc_increment(data: bytes) -> Dict[str, Any]:
    """Decode the inflated ``Global/DocumentIncrementTable`` payload
    (``extracted/<file>/Global__DocumentIncrementTable.gz/000.bin``).

    Structure: u16 tag 0x053C, u32 record count, N variable-length increment
    records (one per document save/version), then the SAME table serialized a
    second time (u32 count + records), then 8 zero bytes.  ``N`` equals the
    "Unique Document Increments" value in ``BasicFileInfo``.

    Pass either the inflated payload or the raw stream (8-byte header + gzip);
    the latter is detected and inflated automatically.
    """
    inflated = data
    hdr8 = None
    if data[8:11] == GZIP_MAGIC:
        hdr8 = data[:8]
        inflated, _ = raw_inflate_after_gzip_header(data, 8)
    c = Cursor(inflated)
    tag = c.u16()
    count = c.u32()
    table1 = _parse_increment_table(c, count)
    t1_end = c.o
    count2 = c.u32()
    table2 = _parse_increment_table(c, count2)
    trailer = inflated[c.o:]
    identical = ([{k: v for k, v in r.items() if k != "offset"} for r in table1]
                 == [{k: v for k, v in r.items() if k != "offset"} for r in table2])
    return {
        "raw_header8": hdr8.hex() if hdr8 else None,
        "type_tag": tag,
        "count": count,
        "records": table1,
        "table1_end": t1_end,
        "count_copy2": count2,
        "copy2_identical": identical,
        "trailer": trailer.hex(),
        "consumed": c.o,
        "inflated_size": len(inflated),
        "increments": count,
        "last_save_utc": table1[-1]["time_utc"] if table1 else None,
        "usernames": sorted({r["username"] for r in table1}),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SAMPLES = [
    "racbasicsampleproject",
    "racadvancedsampleproject",
    "rmebasicsampleproject",
    "rstbasicsampleproject",
    "rstadvancedsampleproject",
    "dach-sample-project",
]


def _root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


def _read(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def dump_file(name: str, verbose: bool = True) -> Dict[str, Any]:
    ex = os.path.join(_root(), "extracted", name)
    res: Dict[str, Any] = {"file": name}
    line = "=" * 78

    # BasicFileInfo
    d = _read(os.path.join(ex, "BasicFileInfo.bin"))
    if d:
        bfi = parse_basic_file_info(d)
        res["basic_file_info"] = {k: v for k, v in bfi.items() if k not in ("layout", "mirror_text", "mirror_kv")}
        if verbose:
            print(f"{line}\n{name} :: BasicFileInfo ({len(d)} bytes)\n{line}")
            for f in bfi["layout"]:
                print(f"  0x{f['offset']:04x} {f['size']:5d}B {f['type']:16s} {f['field']:36s} {f['value']!r}")
            print(f"  -> version={bfi['version']} build={bfi['build']} increments={bfi['unique_document_increments']} "
                  f"worksharing={bfi['worksharing']!r} locale={bfi['locale']}")
            print(f"  -> unique_document_guid={bfi['guids']['unique_document_guid']}")

    # Contents
    d = _read(os.path.join(ex, "Contents.bin"))
    if d:
        co = parse_contents(d)
        res["contents"] = co
        if verbose:
            print(f"{line}\n{name} :: Contents ({len(d)} bytes)\n{line}")
            print(f"  wrapper: class_ref={co['header']['class_ref']} payload={co['gzip']['payload_size']}B "
                  f"crc_ok={co['gzip']['trailer_crc_ok']} slack={co['gzip']['slack_bytes']}B")
            print(f"  tag=0x{co['type_tag']:04x} user={co['username']!r} partition={co['partition_name']!r} "
                  f"guid={co['creation_guid']} build={co['build']}")
            print(f"  hdr5={co['unknown_hdr5']} counters={co['counters']} G={co['counter_g']} "
                  f"trailing={co['trailing_pairs']} tail_zero={co['tail_zero_bytes']}B all_zero={co['tail_all_zero']}")

    # TransmissionData
    d = _read(os.path.join(ex, "TransmissionData.bin"))
    if d:
        tr = parse_transmission(d)
        res["transmission"] = {k: v for k, v in tr.items() if k != "xml"}
        if verbose:
            print(f"{line}\n{name} :: TransmissionData ({len(d)} bytes)\n{line}")
            print(f"  chars={tr['char_count']} size_ok={tr['size_ok']} version={tr.get('version')} "
                  f"isTransmitted={tr.get('is_transmitted')}")
            for r in tr["references"]:
                print(f"    ref elem={r.get('ElementId')} type={r.get('ExternalFileReferenceType')!r} "
                      f"path={r.get('DesiredPath')!r} state={r.get('DesiredLoadState')!r}")

    # ProjectInformation
    d = _read(os.path.join(ex, "ProjectInformation.bin"))
    if d:
        pi = parse_project_info(d)
        res["project_info"] = {k: v for k, v in pi.items() if k != "xml"}
        if verbose:
            print(f"{line}\n{name} :: ProjectInformation ({len(d)} bytes, ZIP)\n{line}")
            for m in pi["members"]:
                print(f"  member {os.path.basename(m['filename'].replace(chr(92), '/'))} "
                      f"{m['file_size']}B (deflated {m['compressed_size']}B)")
            print(f"  title={pi.get('title')!r} updated={pi.get('updated')} "
                  f"product={pi.get('link', {}).get('design_file', {})}")
            for g in pi["groups"]:
                if g["parameters"]:
                    print(f"  group {g['title']!r}:")
                    for p in g["parameters"]:
                        val = p['value'].replace("\n", " ")[:60]
                        print(f"    {p['display_name']} ({p['kind']}) = {val!r}")

    # RevitPreview4.0
    d = _read(os.path.join(ex, "RevitPreview4.0.bin"))
    if d:
        pv = extract_preview(d, os.path.join(ex, "preview.png"))
        res["preview"] = pv
        if verbose:
            print(f"{line}\n{name} :: RevitPreview4.0 ({len(d)} bytes)\n{line}")
            for cls in pv["classes"]:
                fdesc = ", ".join(f"{f['name']}:{f['base_type']}{'[]' if f['is_array'] else ''}" for f in cls["fields"])
                print(f"  class ref=0x{cls['class_ref']:x} {cls['name']} v{cls['version']} {{{fdesc}}}")
            print(f"  png @0x{pv['png_offset']:x} len={pv['png_length']} dims={pv['png_dimensions']} "
                  f"dpi={pv['dpi']} px={pv['size_px']} consumed={pv['consumed']}/{pv['stream_size']} "
                  f"-> {os.path.relpath(pv['png_path'], _root())}")
    else:
        res["preview"] = None
        if verbose:
            print(f"{line}\n{name} :: RevitPreview4.0 absent\n{line}")

    # DocumentIncrementTable
    d = _read(os.path.join(ex, "Global__DocumentIncrementTable.bin"))
    if d:
        dit = parse_doc_increment(d)
        res["doc_increment"] = {k: v for k, v in dit.items() if k != "records"}
        res["doc_increment_records"] = len(dit["records"])
        if verbose:
            print(f"{line}\n{name} :: Global/DocumentIncrementTable ({len(d)} raw / "
                  f"{dit['inflated_size']} inflated)\n{line}")
            print(f"  tag=0x{dit['type_tag']:04x} count={dit['count']} copy2_identical={dit['copy2_identical']} "
                  f"trailer={dit['trailer']} consumed={dit['consumed']}/{dit['inflated_size']}")
            for i, r in enumerate(dit["records"]):
                print(f"   #{r['sequence']:3d} {r['time_utc']} {r['username']:14s} pairs={r['pairs']} "
                      f"ids={r['id_pair']} X={r['elem_id_repeat']} ctr={r['counters']} G={r['counter_g']} "
                      f"fl={r['flag']}")
    return res


def main(argv: List[str]) -> int:
    names = argv[1:] or SAMPLES
    summary = {}
    for n in names:
        if not os.path.isdir(os.path.join(_root(), "extracted", n)):
            print(f"[skip] {n}: not extracted", file=sys.stderr)
            continue
        summary[n] = dump_file(n)
    # compact cross-file summary
    print("\n" + "#" * 78 + "\n# cross-file summary\n" + "#" * 78)
    for n, r in summary.items():
        b = r.get("basic_file_info", {})
        c = r.get("contents", {})
        dit = r.get("doc_increment", {})
        pv = r.get("preview") or {}
        print(f"{n:26s} incr={b.get('unique_document_increments'):>3} "
              f"dit_count={dit.get('count')} contents_user={c.get('username')!r:18s} "
              f"guid={c.get('creation_guid')} preview={pv.get('png_dimensions')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
