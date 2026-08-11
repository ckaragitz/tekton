"""rvt.specsheet.pdftext -- a stdlib-only text-layer PDF reader (specsheet stream).

WHY.  The spec-sheet input lane reads dimensions and ratings out of a
document the USER supplies.  A full PDF library (``pdfplumber`` and its
``pdfminer.six`` dependency) is a heavy install that the engine must not
require: CLAUDE.md section 2 declares ``olefile`` as the ONLY runtime
dependency.  This module implements the narrow slice the lane actually
needs -- *positioned text fragments per page* -- in pure stdlib python, so
a text-layer spec sheet is readable on a BARE interpreter with ZERO pip
installs.  The heavy backend stays optional (``pip install -e ".[pdf]"``)
and wins whenever it is present; see :mod:`rvt.specsheet._backend`, which
copies the selection posture of :mod:`rvt.ifc._fallback` (issue #130).

WHAT IT READS (the slice the table reader consumes):

* the object graph, scanned directly from the file body (``N G obj ...
  endobj``) rather than through ``/XRef`` -- a spec sheet exported by a
  vendor's authoring tool routinely carries a stale or hybrid xref, and
  the body is the ground truth;
* page objects in ``/Type /Page`` order, with inherited ``/Resources``;
* content streams, ``FlateDecode`` (stdlib :mod:`zlib`) or unfiltered;
* the text operators that carry a text layer: ``BT``/``ET``, ``Tf``,
  ``Td``/``TD``/``Tm``/``T*``/``TL``, ``Tj``/``TJ``/``'``/``"``;
* ``/ToUnicode`` CMaps (``beginbfchar`` / ``beginbfrange``), so a subset
  font's byte codes become the characters a human read on the page.

WHAT IT DOES NOT DO -- and says so rather than guessing.  This is the
honesty boundary of the whole lane: a number that is not stated must never
be produced by us.

* **No OCR.**  A scanned sheet has no text layer; :func:`read_pdf` reports
  ``scanned`` per page (a page with zero text fragments) and the caller
  turns that into one clear line, never an empty table that reads as "the
  sheet says nothing".
* **No glyph guessing.**  A byte code with no ``/ToUnicode`` entry and no
  usable simple encoding becomes :data:`UNDECODABLE` (U+FFFD) and the
  fragment is flagged, so a mis-decoded row is visible instead of silently
  becoming a wrong value.
* **No encryption.**  An encrypted document raises :class:`PdfTextError`.
* No geometry, no images, no annotations, no form fields.

TERRITORY (specsheet stream): this module, ``rvt/specsheet/**``,
``tests/test_specsheet_*.py``, ``docs/inbox/specsheet.md``.  Imports
nothing beyond the stdlib.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "PDFTEXT_VERSION", "UNDECODABLE", "PdfTextError", "Fragment", "Page",
    "Document", "read_pdf",
]

#: bumped when extraction behaviour changes in a way a record should name
PDFTEXT_VERSION = "1.0"

#: stands in for a byte code this reader cannot map to a character
UNDECODABLE = "�"


class PdfTextError(ValueError):
    """A PDF this reader cannot honestly read (not a PDF, encrypted, no
    pages, a filter we do not implement).  The message says which, so the
    caller can print one clear line."""


# ---------------------------------------------------------------------------
# extracted shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Fragment:
    """One run of text with the page position it was drawn at.

    ``x`` / ``y`` are PDF user-space points with the origin bottom-left, as
    the content stream states them -- the table reader groups rows by ``y``
    and orders cells by ``x``.  ``undecodable`` is True when any byte in the
    run had no character mapping (the text then carries U+FFFD there).
    """
    text: str
    x: float
    y: float
    size: float = 0.0
    undecodable: bool = False


@dataclass
class Page:
    """One page's text layer, in content-stream order."""
    number: int                                   # 1-based, as a human cites
    fragments: List[Fragment] = dc_field(default_factory=list)

    @property
    def scanned(self) -> bool:
        """True when the page carries no text layer at all (image-only).

        The caller must treat this as "unreadable", never as "empty".
        """
        return not self.fragments

    @property
    def undecodable(self) -> bool:
        return any(f.undecodable for f in self.fragments)


@dataclass
class Document:
    """Every page's text layer, plus what could not be read."""
    pages: List[Page] = dc_field(default_factory=list)
    backend: str = "pdftext"

    @property
    def scanned_pages(self) -> List[int]:
        return [p.number for p in self.pages if p.scanned]

    @property
    def any_text(self) -> bool:
        return any(not p.scanned for p in self.pages)


# ---------------------------------------------------------------------------
# object-graph scan
# ---------------------------------------------------------------------------

_OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.DOTALL)
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.DOTALL)
_DICT_START = b"<<"


@dataclass
class _Obj:
    num: int
    body: bytes                 # everything between "obj" and "endobj"
    stream: Optional[bytes]     # raw (still encoded) stream bytes, if any


def _scan_objects(raw: bytes) -> Dict[int, _Obj]:
    """Every ``N G obj ... endobj`` in the body, later definitions winning
    (an incrementally-updated PDF appends the newer object)."""
    out: Dict[int, _Obj] = {}
    for m in _OBJ_RE.finditer(raw):
        num = int(m.group(1))
        body = m.group(3)
        sm = _STREAM_RE.search(body)
        out[num] = _Obj(num, body, sm.group(1) if sm else None)
    return out


def _dict_of(body: bytes) -> bytes:
    """The object's dictionary bytes (``<<...>>``), balanced, or b''."""
    i = body.find(_DICT_START)
    if i < 0:
        return b""
    depth, j = 0, i
    while j < len(body) - 1:
        pair = body[j:j + 2]
        if pair == b"<<":
            depth += 1
            j += 2
            continue
        if pair == b">>":
            depth -= 1
            j += 2
            if depth == 0:
                return body[i:j]
            continue
        j += 1
    return body[i:]


_NAME_VAL_RE_CACHE: Dict[bytes, re.Pattern] = {}


def _name_value(d: bytes, key: bytes) -> bytes:
    """Raw bytes of the value following ``/key`` in a dictionary.

    Handles the three value shapes this reader meets: a NAME (``/Filter
    /FlateDecode``), an ARRAY (``/Filter [/FlateDecode]``), and a plain
    token run (``/Length 42``, ``/Parent 2 0 R``).  The name case is the
    one that matters most -- a pattern that stops at the first ``/``
    captures an empty string for ``/Filter /FlateDecode``, which silently
    turns a compressed page into "no text" instead of into its rows.
    """
    pat = _NAME_VAL_RE_CACHE.get(key)
    if pat is None:
        pat = re.compile(
            rb"/" + re.escape(key) + rb"\s*"
            rb"(\[[^\]]*\]"            # array:  [/FlateDecode]
            rb"|(?:/[^\s/<>\[\]]+\s*)+"  # one or more names: /FlateDecode
            rb"|[^/>\[\]]*)",            # plain tokens: 42, 2 0 R
            re.DOTALL)
        _NAME_VAL_RE_CACHE[key] = pat
    m = pat.search(d)
    return m.group(1).strip() if m else b""


_REF_RE = re.compile(rb"(\d+)\s+\d+\s+R\b")


def _refs(blob: bytes) -> List[int]:
    return [int(m.group(1)) for m in _REF_RE.finditer(blob)]


# ---------------------------------------------------------------------------
# stream decoding
# ---------------------------------------------------------------------------

def _decode_stream(obj: _Obj) -> bytes:
    """Decoded stream bytes.  Unfiltered and ``FlateDecode`` are supported;
    any other filter raises rather than returning partial text."""
    if obj.stream is None:
        return b""
    d = _dict_of(obj.body)
    filt = _name_value(d, b"Filter")
    raw = obj.stream
    if not filt:
        return raw
    if b"FlateDecode" in filt:
        try:
            data = zlib.decompress(raw)
        except zlib.error:
            # tolerate a stream whose declared length ran past the data
            try:
                data = zlib.decompressobj().decompress(raw)
            except zlib.error as exc:
                raise PdfTextError(
                    f"object {obj.num}: FlateDecode stream is corrupt ({exc})")
        parms = _name_value(d, b"DecodeParms")
        if b"Predictor" in d and b"Predictor" in parms:
            pred = _name_value(parms if parms else d, b"Predictor")
            if pred and pred.split()[0] not in (b"1", b"2"):
                raise PdfTextError(
                    f"object {obj.num}: PNG stream predictor is not supported")
        return data
    known = filt.decode("latin-1", "replace").strip()
    raise PdfTextError(f"object {obj.num}: stream filter {known} is not supported")


# ---------------------------------------------------------------------------
# /ToUnicode CMaps
# ---------------------------------------------------------------------------

_BFCHAR_BLOCK = re.compile(rb"beginbfchar(.*?)endbfchar", re.DOTALL)
_BFRANGE_BLOCK = re.compile(rb"beginbfrange(.*?)endbfrange", re.DOTALL)
_HEXTOK = re.compile(rb"<([0-9A-Fa-f\s]*)>")


def _hex_to_str(h: bytes) -> str:
    """A CMap destination (UTF-16BE code units) as text."""
    b = bytes.fromhex(h.decode("ascii", "ignore").replace(" ", "").replace("\n", ""))
    if not b:
        return ""
    try:
        return b.decode("utf-16-be")
    except UnicodeDecodeError:
        return b.decode("latin-1", "replace")


def _parse_tounicode(data: bytes) -> Dict[int, str]:
    """``{byte code -> text}`` from a ``/ToUnicode`` CMap."""
    cmap: Dict[int, str] = {}
    for blk in _BFCHAR_BLOCK.findall(data):
        toks = _HEXTOK.findall(blk)
        for i in range(0, len(toks) - 1, 2):
            src = toks[i].decode("ascii", "ignore").replace(" ", "")
            if not src:
                continue
            cmap[int(src, 16)] = _hex_to_str(toks[i + 1])
    for blk in _BFRANGE_BLOCK.findall(data):
        # "<lo> <hi> <dst>" triples; the array form "<lo> <hi> [<a> <b>]"
        # is handled by walking tokens in order.
        toks = _HEXTOK.findall(blk)
        i = 0
        while i + 2 < len(toks) + 1 and i + 2 <= len(toks):
            lo_s = toks[i].decode("ascii", "ignore").replace(" ", "")
            hi_s = toks[i + 1].decode("ascii", "ignore").replace(" ", "")
            if not lo_s or not hi_s:
                break
            lo, hi = int(lo_s, 16), int(hi_s, 16)
            dst = _hex_to_str(toks[i + 2])
            if dst and hi >= lo and hi - lo < 65536:
                base = ord(dst[0]) if len(dst) == 1 else None
                for k in range(lo, hi + 1):
                    if base is not None:
                        cmap[k] = chr(base + (k - lo))
                    else:
                        cmap[k] = dst
            i += 3
    return cmap


def _font_cmaps(objs: Dict[int, _Obj], res_blob: bytes) -> Dict[str, Dict[int, str]]:
    """``{font resource name -> cmap}`` for the fonts a page references."""
    out: Dict[str, Dict[int, str]] = {}
    fm = re.search(rb"/Font\s*(<<.*?>>|\d+\s+\d+\s+R)", res_blob, re.DOTALL)
    if not fm:
        return out
    blob = fm.group(1)
    if blob.startswith(b"<<"):
        font_dict = blob
    else:
        ref = _refs(blob)
        if not ref or ref[0] not in objs:
            return out
        font_dict = _dict_of(objs[ref[0]].body)
    for name, num, _gen in re.findall(rb"/([^\s/<>\[\]]+)\s+(\d+)\s+(\d+)\s+R", font_dict):
        fo = objs.get(int(num))
        if fo is None:
            continue
        fd = _dict_of(fo.body)
        tu = _refs(_name_value(fd, b"ToUnicode"))
        if not tu or tu[0] not in objs:
            continue
        try:
            cm = _parse_tounicode(_decode_stream(objs[tu[0]]))
        except PdfTextError:
            continue
        if cm:
            out[name.decode("latin-1", "replace")] = cm
    return out


# ---------------------------------------------------------------------------
# content-stream text extraction
# ---------------------------------------------------------------------------

_ESCAPES = {
    b"n": "\n", b"r": "\r", b"t": "\t", b"b": "\b", b"f": "\f",
    b"(": "(", b")": ")", b"\\": "\\",
}


def _decode_bytes(bs: bytes, cmap: Optional[Dict[int, str]]) -> Tuple[str, bool]:
    """Byte codes -> text, plus "something had no mapping"."""
    if not cmap:
        # simple font: the content bytes are the characters (WinAnsi/Latin-1)
        return bs.decode("latin-1", "replace"), False
    out, bad = [], False
    i = 0
    two_byte = any(k > 0xFF for k in cmap)
    while i < len(bs):
        if two_byte and i + 1 < len(bs):
            code = (bs[i] << 8) | bs[i + 1]
            i += 2
        else:
            code = bs[i]
            i += 1
        ch = cmap.get(code)
        if ch is None:
            out.append(UNDECODABLE)
            bad = True
        else:
            out.append(ch)
    return "".join(out), bad


def _literal_string(src: bytes, i: int) -> Tuple[bytes, int]:
    """Read a ``(...)`` literal starting at ``src[i] == '('``."""
    assert src[i:i + 1] == b"("
    i += 1
    depth = 1
    out = bytearray()
    while i < len(src):
        c = src[i:i + 1]
        if c == b"\\":
            nxt = src[i + 1:i + 2]
            if nxt in _ESCAPES:
                out.extend(_ESCAPES[nxt].encode("latin-1"))
                i += 2
                continue
            if nxt.isdigit():
                j, oct_digits = i + 1, b""
                while j < len(src) and len(oct_digits) < 3 and src[j:j + 1].isdigit():
                    oct_digits += src[j:j + 1]
                    j += 1
                out.append(int(oct_digits, 8) & 0xFF)
                i = j
                continue
            if nxt in (b"\n", b"\r"):
                i += 2
                continue
            out.extend(nxt)
            i += 2
            continue
        if c == b"(":
            depth += 1
        elif c == b")":
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
        out.extend(c)
        i += 1
    return bytes(out), i


_NUM = r"[-+]?\d*\.?\d+"
_N = _NUM.encode()
#: every capture is NAMED -- positional group numbers shift the moment the
#: alternation grows, and a silently-shifted group is exactly the "invent a
#: number" failure this lane must not have.
_OP_RE = re.compile(
    rb"(?P<td>(?P<tdx>" + _N + rb")\s+(?P<tdy>" + _N + rb")\s+(?P<tdop>TD|Td)\b)"
    rb"|(?P<tm>(?:" + _N + rb"\s+){4}(?P<tmx>" + _N + rb")\s+(?P<tmy>" + _N + rb")\s+Tm\b)"
    rb"|(?P<tstar>T\*)"
    rb"|(?P<tl>(?P<tlv>" + _N + rb")\s+TL\b)"
    rb"|(?P<tf>/(?P<tfname>[^\s/<>\[\]]+)\s+(?P<tfsize>" + _N + rb")\s+Tf\b)"
    rb"|(?P<bt>BT\b)|(?P<et>ET\b)"
)


def _page_fragments(content: bytes,
                    cmaps: Dict[str, Dict[int, str]]) -> List[Fragment]:
    """Walk the content stream, tracking the text matrix, and emit one
    :class:`Fragment` per text-showing operator."""
    frags: List[Fragment] = []
    x = y = 0.0
    line_x = line_y = 0.0
    leading = 0.0
    size = 0.0
    cmap: Optional[Dict[int, str]] = None
    i = 0
    n = len(content)

    def show(bs: bytes) -> None:
        nonlocal x
        text, bad = _decode_bytes(bs, cmap)
        if text:
            frags.append(Fragment(text, x, y, size, bad))

    while i < n:
        c = content[i:i + 1]
        if c == b"(":
            s, i = _literal_string(content, i)
            # find the operator that follows the operand(s)
            m = re.match(rb"\s*(Tj|')", content[i:])
            if m:
                if m.group(1) == b"'":
                    line_y -= leading          # ' is T* then Tj
                    x, y = line_x, line_y
                show(s)
                i += m.end()
            continue
        if c == b"[":
            # TJ array: strings interleaved with kerning numbers
            j, depth, parts = i + 1, 1, []
            while j < n and depth:
                cc = content[j:j + 1]
                if cc == b"(":
                    s, j = _literal_string(content, j)
                    parts.append(s)
                    continue
                if cc == b"<" and content[j + 1:j + 2] != b"<":
                    k = content.find(b">", j)
                    if k < 0:
                        break
                    hx = content[j + 1:k].decode("ascii", "ignore")
                    hx = re.sub(r"\s", "", hx)
                    if len(hx) % 2:
                        hx += "0"
                    try:
                        parts.append(bytes.fromhex(hx))
                    except ValueError:
                        pass
                    j = k + 1
                    continue
                if cc == b"]":
                    depth -= 1
                    j += 1
                    break
                j += 1
            m = re.match(rb"\s*TJ\b", content[j:])
            if m:
                show(b"".join(parts))
                i = j + m.end()
                continue
            i = j
            continue
        if c == b"<" and content[i + 1:i + 2] != b"<":
            k = content.find(b">", i)
            if k < 0:
                break
            hx = re.sub(r"\s", "", content[i + 1:k].decode("ascii", "ignore"))
            if len(hx) % 2:
                hx += "0"
            m = re.match(rb"\s*(Tj|')", content[k + 1:])
            if m:
                try:
                    bs = bytes.fromhex(hx)
                except ValueError:
                    bs = b""
                if m.group(1) == b"'":
                    line_y -= leading          # ' is T* then Tj
                    x, y = line_x, line_y
                show(bs)
                i = k + 1 + m.end()
                continue
            i = k + 1
            continue

        m = _OP_RE.match(content, i)
        if m:
            if m.group("td"):
                dx, dy = float(m.group("tdx")), float(m.group("tdy"))
                if m.group("tdop") == b"TD":
                    leading = -dy
                line_x += dx
                line_y += dy
                x, y = line_x, line_y
            elif m.group("tm"):
                line_x, line_y = float(m.group("tmx")), float(m.group("tmy"))
                x, y = line_x, line_y
            elif m.group("tstar"):
                line_y -= leading
                x, y = line_x, line_y
            elif m.group("tl"):
                leading = float(m.group("tlv"))
            elif m.group("tf"):
                cmap = cmaps.get(m.group("tfname").decode("latin-1", "replace"))
                try:
                    size = float(m.group("tfsize"))
                except (TypeError, ValueError):
                    size = 0.0
            elif m.group("bt"):
                x = y = line_x = line_y = 0.0
            i = m.end()
            continue
        i += 1
    return frags


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def _page_objects(objs: Dict[int, _Obj]) -> List[_Obj]:
    """Page objects, in document order where /Kids states one."""
    pages = [o for o in objs.values()
             if re.search(rb"/Type\s*/Page\b(?!s)", _dict_of(o.body))]
    ordered: List[_Obj] = []
    seen = set()
    for o in objs.values():
        d = _dict_of(o.body)
        if not re.search(rb"/Type\s*/Pages\b", d):
            continue
        km = re.search(rb"/Kids\s*\[(.*?)\]", d, re.DOTALL)
        if not km:
            continue
        for num in _refs(km.group(1)):
            kid = objs.get(num)
            if kid is not None and kid.num not in seen and \
                    re.search(rb"/Type\s*/Page\b(?!s)", _dict_of(kid.body)):
                ordered.append(kid)
                seen.add(kid.num)
    for o in sorted(pages, key=lambda o: o.num):
        if o.num not in seen:
            ordered.append(o)
            seen.add(o.num)
    return ordered


def _inherited(objs: Dict[int, _Obj], obj: _Obj, key: bytes) -> bytes:
    """A page attribute, walking ``/Parent`` when the page does not state it."""
    seen = set()
    cur: Optional[_Obj] = obj
    while cur is not None and cur.num not in seen:
        seen.add(cur.num)
        d = _dict_of(cur.body)
        m = re.search(rb"/" + re.escape(key) + rb"\s*(<<.*?>>|\d+\s+\d+\s+R)",
                      d, re.DOTALL)
        if m:
            blob = m.group(1)
            if blob.startswith(b"<<"):
                return blob
            r = _refs(blob)
            if r and r[0] in objs:
                return _dict_of(objs[r[0]].body) or objs[r[0]].body
            return b""
        pr = _refs(_name_value(d, b"Parent"))
        cur = objs.get(pr[0]) if pr else None
    return b""


def read_pdf(path: str) -> Document:
    """Read every page's text layer from ``path``.

    Raises :class:`PdfTextError` when the file is not a readable PDF; a page
    with no text layer is reported as ``scanned`` rather than as empty text.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise PdfTextError(f"cannot read {path}: {exc}")

    if not raw.lstrip()[:5].startswith(b"%PDF-"):
        raise PdfTextError(f"{path} is not a PDF (no %PDF- header)")

    objs = _scan_objects(raw)
    if not objs:
        raise PdfTextError(f"{path}: no PDF objects found (file truncated?)")

    if re.search(rb"/Encrypt\b", raw):
        raise PdfTextError(
            f"{path} is encrypted; this reader does not decrypt PDFs")

    page_objs = _page_objects(objs)
    if not page_objs:
        raise PdfTextError(f"{path}: no page objects found")

    doc = Document(backend="pdftext")
    for idx, po in enumerate(page_objs, start=1):
        res = _inherited(objs, po, b"Resources")
        cmaps = _font_cmaps(objs, res) if res else {}
        d = _dict_of(po.body)
        cm = re.search(rb"/Contents\s*(\[.*?\]|\d+\s+\d+\s+R)", d, re.DOTALL)
        chunks: List[bytes] = []
        if cm:
            for num in _refs(cm.group(1)):
                co = objs.get(num)
                if co is None:
                    continue
                chunks.append(_decode_stream(co))
        content = b"\n".join(c for c in chunks if c)
        frags = _page_fragments(content, cmaps) if content else []
        doc.pages.append(Page(number=idx, fragments=frags))
    return doc
