"""rvt.specsheet.pdftext -- a stdlib-only PDF text extractor with POSITIONS.

WHY.  #688 makes a user-supplied spec sheet a first-class INPUT: the honest
route to a manufacturer's real dimensions, because the user handed us the
document that states them (#685 forbids recalling them from model knowledge).
Reading a PDF normally means a wheel -- pdfplumber, PyMuPDF, pdfminer -- and
this engine declares exactly ONE runtime dependency (``olefile``).  The same
answer that worked for IFC works here: implement the narrow slice we actually
need, in pure stdlib, and let the heavyweight library be an OPTIONAL extra for
the cases the slice cannot reach.  ``rvt.ifc.steplite`` is the precedent.

WHAT THIS READS.  Text-layer PDFs -- the kind a vendor's spec sheet almost
always is, because it was typeset, not scanned.  For each page it returns the
drawn text **with its position on the page**, which is the part that matters:
a spec sheet's meaning lives in its table layout, and a reader that returns a
flat string has thrown away the columns.

WHAT THIS DOES NOT READ, and says so rather than guessing:

* **Scanned / image-only pages.**  No OCR, ever, in this module.  A page whose
  content stream draws no text is reported ``unreadable`` with the reason; it
  is never "read" as an empty table, because an empty table silently becomes
  "the sheet states nothing" and then a family gets built at nominal sizes
  while the user believes their document was used.
* **Encrypted PDFs.**  Reported, not attempted.
* Exotic encodings we cannot resolve are surfaced per-glyph as U+FFFD rather
  than being dropped, so a mangled cell is VISIBLE in the parsed-table report
  (#688 DONE 4) instead of quietly becoming a wrong number.

DESIGN NOTES, each one a decision that cost thought:

* **Objects are found by scanning, not by trusting the xref table.**  Real
  vendor PDFs are frequently produced by tools that leave a stale or
  slightly-wrong xref; every PDF viewer in the world has a "reconstruct"
  path for exactly this.  We go straight to the reconstruct path: regex for
  ``N G obj`` and index what is actually there.  Incremental updates (the
  same object number appearing twice) resolve to the LAST definition, which
  is what an xref would have pointed at.
* **Only FlateDecode is implemented** (zlib, stdlib).  It is what essentially
  every modern producer emits.  LZW/RunLength/DCT are named and refused, not
  half-decoded.
* **The text matrix is tracked properly** (Tm/Td/TD/T*/TL and the font size
  and horizontal scale), because table reconstruction needs real coordinates.
  Getting this wrong yields plausible text in the wrong order -- the worst
  possible failure for a document we are about to turn into dimensions.
"""
from __future__ import annotations

import math
import re
import zlib
from typing import Dict, List, Optional, Tuple

__all__ = ["PdfError", "UnreadablePdf", "Glyph", "Page", "read_pdf"]


class PdfError(Exception):
    """The file is not a PDF we can parse at all."""


class UnreadablePdf(PdfError):
    """A PDF we can open but whose text we cannot honestly recover.

    Distinct from :class:`PdfError` on purpose: the caller reports this to the
    user as "your sheet could not be read, here is why", and still delivers an
    archetype family (hard rule 1).  It is never downgraded to "no values".
    """


class Glyph:
    """One run of text drawn at one place on the page.

    ``x``/``y`` are PDF user-space points with the origin at the BOTTOM-left,
    which is what the format uses; the table builder flips to reading order.
    """

    __slots__ = ("text", "x", "y", "size", "font", "width")

    def __init__(self, text: str, x: float, y: float, size: float, font: str,
                 width: float = 0.0):
        self.text, self.x, self.y, self.size, self.font = text, x, y, size, font
        #: how far the pen moved drawing this run -- the MEASURED advance from
        #: the font's own widths, not an estimate from len(text).  The layout
        #: layer needs a run's right edge to tell "two words" from "two
        #: columns", and guessing it is how a reader invents columns.
        self.width = width

    @property
    def x1(self) -> float:
        return self.x + self.width

    def __repr__(self) -> str:                                    # pragma: no cover
        return "Glyph(%r, x=%.1f..%.1f, y=%.1f, size=%.1f)" % (
            self.text, self.x, self.x1, self.y, self.size)


class Page:
    """One page's drawn text runs, plus why it may be empty."""

    __slots__ = ("number", "glyphs", "width", "height", "note")

    def __init__(self, number: int, glyphs: List[Glyph],
                 width: float, height: float, note: str = ""):
        self.number, self.glyphs = number, glyphs
        self.width, self.height, self.note = width, height, note

    @property
    def has_text(self) -> bool:
        return any(g.text.strip() for g in self.glyphs)


# ---------------------------------------------------------------------------
# object layer
# ---------------------------------------------------------------------------

_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b")
#: the spec requires the encryption dictionary to be an INDIRECT object,
#: so this shape keeps every genuinely encrypted file and stops the word
#: appearing inside an uncompressed stream from refusing a readable one
_ENCRYPT = re.compile(rb"/Encrypt\s+\d+\s+\d+\s+R")


def _find_objects(raw: bytes) -> Dict[int, bytes]:
    """Every ``N G obj … endobj`` body in the file, by object number.

    Later definitions win: that is what an incremental update means, and what
    a correct xref would have resolved to.
    """
    out: Dict[int, bytes] = {}
    marks = [(int(m.group(1)), m.start(), m.end()) for m in _OBJ.finditer(raw)]
    for i, (num, _hstart, start) in enumerate(marks):
        # upper bound: the NEXT object's header.  Then the LAST `endobj`
        # inside that extent, not the first -- a deflate payload can contain
        # the bytes `endobj`, and the real one always follows it.
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(raw)
        end = raw.rfind(b"endobj", start, stop)
        out[num] = raw[start:end if end != -1 else stop]
    return out


def _dict_of(body: bytes) -> bytes:
    """The object's dictionary bytes (``<< … >>``), balanced."""
    i = body.find(b"<<")
    if i == -1:
        return b""
    depth, j = 0, i
    while j < len(body) - 1:
        two = body[j:j + 2]
        if two == b"<<":
            depth += 1
            j += 2
            continue
        if two == b">>":
            depth -= 1
            j += 2
            if depth == 0:
                return body[i:j]
            continue
        j += 1
    return body[i:]


def _name(d: bytes, key: bytes) -> Optional[bytes]:
    m = re.search(re.escape(key) + rb"\s*/([A-Za-z0-9#\-+.]+)", d)
    return m.group(1) if m else None


def _int(d: bytes, key: bytes) -> Optional[int]:
    m = re.search(re.escape(key) + rb"\s+(\d+)(?!\s+\d+\s+R)", d)
    return int(m.group(1)) if m else None


def _ref(d: bytes, key: bytes) -> Optional[int]:
    m = re.search(re.escape(key) + rb"\s+(\d+)\s+\d+\s+R", d)
    return int(m.group(1)) if m else None


def _refs(d: bytes, key: bytes) -> List[int]:
    m = re.search(re.escape(key) + rb"\s*\[(.*?)\]", d, re.S)
    if not m:
        one = _ref(d, key)
        return [one] if one is not None else []
    return [int(x) for x in re.findall(rb"(\d+)\s+\d+\s+R", m.group(1))]


def _filters(d: bytes) -> List[bytes]:
    """Every filter name on this stream, in order.

    BOTH spellings the format allows: ``/Filter /FlateDecode`` and
    ``/Filter [/FlateDecode]`` (and a chain, ``[/ASCII85Decode
    /FlateDecode]``).  The array form is legal and common, and reading only
    the first spelling meant an array-filtered stream looked UNFILTERED --
    so the compressed bytes were handed on as content, no text parsed out of
    them, and a perfectly readable sheet was reported as a scan.  A wrong
    refusal is worse than a named one.
    """
    m = re.search(rb"/Filter\s*(\[[^\]]*\]|/[A-Za-z0-9#\-+.]+)", d)
    if not m:
        return []
    return re.findall(rb"/([A-Za-z0-9#\-+.]+)", m.group(1))


def _stream_bytes(body: bytes) -> Optional[bytes]:
    """Decoded stream payload, or None when there is no stream.

    Only FlateDecode is supported; anything else raises so the caller can name
    the filter it refused rather than returning mangled bytes.
    """
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    start = m.end()
    d = _dict_of(body)
    # /Length is the format's own answer to "where does the payload end";
    # searching for `endstream` guesses, and deflate bytes can spell it.
    n = _int(d, b"/Length")
    end = -1
    if n is not None and 0 <= n <= len(body) - start:
        tail = body[start + n:start + n + 32]
        if b"endstream" in tail or not tail.strip():
            end = start + n
    if end == -1:
        end = body.find(b"endstream", start)
    payload = body[start:end if end != -1 else len(body)]

    filters = _filters(d)
    if not filters:
        return payload
    if filters != [b"FlateDecode"]:
        raise UnreadablePdf(
            "stream filter %s is not supported by the stdlib reader "
            "(only FlateDecode); install the optional [pdf] extra"
            % " ".join("/" + f.decode("latin-1") for f in filters))
    try:
        return zlib.decompress(payload)
    except zlib.error:
        # Producers sometimes leave a stray byte before the deflate stream.
        for skip in (1, 2):
            try:
                return zlib.decompress(payload[skip:])
            except zlib.error:
                continue
        try:
            return zlib.decompressobj().decompress(payload)
        except zlib.error as exc:
            raise UnreadablePdf("a content stream did not inflate: %s" % exc)


# ---------------------------------------------------------------------------
# encoding: code bytes -> unicode
# ---------------------------------------------------------------------------

_BFCHAR = re.compile(rb"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE = re.compile(rb"beginbfrange(.*?)endbfrange", re.S)
_HEXPAIR = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_HEXTRIPLE = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")


def _utf16be(h: bytes) -> str:
    try:
        return bytes.fromhex(h.decode("ascii")).decode("utf-16-be", "replace")
    except (ValueError, UnicodeDecodeError):
        return "�"


def _tounicode_map(cmap: bytes) -> Dict[int, str]:
    """Parse a /ToUnicode CMap's bfchar and bfrange sections.

    This is the ONLY reliable route from a subset font's arbitrary codes to
    real characters, which is why a spec sheet's "62.0" can otherwise come
    back as gibberish.
    """
    out: Dict[int, str] = {}
    for block in _BFCHAR.findall(cmap):
        for src, dst in _HEXPAIR.findall(block):
            out[int(src, 16)] = _utf16be(dst)
    for block in _BFRANGE.findall(cmap):
        for lo, hi, dst in _HEXTRIPLE.findall(block):
            a, b = int(lo, 16), int(hi, 16)
            base = _utf16be(dst)
            if len(base) == 1 and b >= a and b - a < 65536:
                for k in range(a, b + 1):
                    out[k] = chr(ord(base) + (k - a))
    return out


class _Font:
    """What we need to turn code bytes into text AT THE RIGHT X.

    Two halves, and the second one is the half that is usually skipped:

    * ``tounicode`` / ``two_byte`` -- what the codes MEAN.
    * ``widths`` / ``default_width`` -- how far each code ADVANCES the pen,
      in 1/1000 em.  Without this a reader has no way to move the text matrix
      after drawing, so every run inside one ``TJ`` array lands at the same x
      and a whole table row collapses into a single cell.  A spec sheet is
      read for its COLUMNS, so losing them loses the document.

    ``width_source`` records which of ``/Widths`` (simple fonts), ``/W``
    (Type0 CID fonts) or ``estimated`` supplied them; an estimate is surfaced
    as a page note rather than passed off as a measurement.
    """

    __slots__ = ("tounicode", "two_byte", "widths", "default_width",
                 "width_source")

    def __init__(self, tounicode: Optional[Dict[int, str]] = None,
                 two_byte: bool = False,
                 widths: Optional[Dict[int, float]] = None,
                 default_width: float = 500.0,
                 width_source: str = "estimated"):
        self.tounicode, self.two_byte = tounicode, two_byte
        self.widths = widths or {}
        self.default_width = default_width
        self.width_source = width_source

    def codes(self, raw: bytes) -> List[int]:
        step = 2 if self.two_byte else 1
        return [int.from_bytes(raw[i:i + step], "big")
                for i in range(0, len(raw) - step + 1, step)]

    def decode(self, raw: bytes) -> str:
        if self.tounicode:
            return "".join(self.tounicode.get(c, "�")
                           for c in self.codes(raw))
        if self.two_byte:
            return raw.decode("utf-16-be", "replace")
        # WinAnsi is a superset of Latin-1 for the printable range, and every
        # spec sheet number lives there.
        return raw.decode("latin-1", "replace")

    def advance(self, raw: bytes, size: float, char_space: float,
                word_space: float, hscale: float) -> float:
        """Pen movement for ``raw``, in unscaled text-space units.

        PDF 32000 9.4.4: tx = ((w0/1000 - Tj/1000) * Tfs + Tc + Tw) * Th.
        ``Tw`` applies to single-byte code 32 only -- a rule that matters
        here because a Type0 sheet would otherwise gain a space's width at
        every 0x0020 CID and drift its columns rightwards down the page.
        """
        total = 0.0
        single = not self.two_byte
        for code in self.codes(raw):
            w = self.widths.get(code, self.default_width)
            total += w / 1000.0 * size + char_space
            if single and code == 32:
                total += word_space
        return total * hscale


_NUMS = re.compile(rb"[-+]?\d*\.?\d+")


def _simple_widths(fd: bytes, objs: Dict[int, bytes]) -> Optional[Dict[int, float]]:
    """``/FirstChar`` + ``/Widths`` of a simple font, by character code."""
    first = _int(fd, b"/FirstChar")
    if first is None:
        return None
    m = re.search(rb"/Widths\s*(\[[^\]]*\]|\d+\s+\d+\s+R)", fd, re.S)
    if not m:
        return None
    blob = m.group(1)
    if not blob.startswith(b"["):
        num = int(re.match(rb"(\d+)", blob).group(1))
        body = objs.get(num, b"")
        payload = None
        try:
            payload = _stream_bytes(body)
        except UnreadablePdf:
            payload = None
        blob = payload if payload else body
    vals = [float(v) for v in _NUMS.findall(blob)]
    if not vals:
        return None
    return {first + i: w for i, w in enumerate(vals)}


def _cid_widths(fd: bytes, objs: Dict[int, bytes]) -> Tuple[Optional[Dict[int, float]], float]:
    """A Type0 font's ``/W`` array and ``/DW``, through its descendant.

    ``/W`` has two shapes -- ``c [w1 w2 ...]`` and ``c_first c_last w`` --
    and both appear in the wild, so both are read rather than assuming the
    producer used the tidy one.
    """
    desc_nums = _refs(fd, b"/DescendantFonts")
    if not desc_nums:
        return None, 1000.0
    dd = _dict_of(objs.get(desc_nums[0], b""))
    dw = _int(dd, b"/DW")
    default = float(dw) if dw is not None else 1000.0
    m = re.search(rb"/W\s*\[(.*?)\]\s*(?:/|>>)", dd, re.S)
    if not m:
        return None, default
    body = m.group(1)
    out: Dict[int, float] = {}
    pos = 0
    tok = re.compile(rb"\[([^\]]*)\]|([-+]?\d*\.?\d+)")
    items: List[object] = []
    for t in tok.finditer(body):
        if t.group(1) is not None:
            items.append([float(v) for v in _NUMS.findall(t.group(1))])
        else:
            items.append(float(t.group(2)))
    while pos < len(items):
        c = items[pos]
        if not isinstance(c, float):
            pos += 1
            continue
        nxt = items[pos + 1] if pos + 1 < len(items) else None
        if isinstance(nxt, list):
            for i, w in enumerate(nxt):
                out[int(c) + i] = w
            pos += 2
        elif isinstance(nxt, float) and pos + 2 < len(items) \
                and isinstance(items[pos + 2], float):
            lo, hi, w = int(c), int(nxt), float(items[pos + 2])
            if 0 <= hi - lo < 65536:
                for k in range(lo, hi + 1):
                    out[k] = w
            pos += 3
        else:
            pos += 1
    return (out or None), default


def _load_fonts(objs: Dict[int, bytes], res_dict: bytes) -> Dict[str, _Font]:
    fonts: Dict[str, _Font] = {}
    fm = re.search(rb"/Font\s*(<<.*?>>|\d+\s+\d+\s+R)", res_dict, re.S)
    if not fm:
        return fonts
    blob = fm.group(1)
    if not blob.startswith(b"<<"):
        num = int(re.match(rb"(\d+)", blob).group(1))
        blob = _dict_of(objs.get(num, b""))
    for name, num in re.findall(rb"/([A-Za-z0-9#\-+.]+)\s+(\d+)\s+\d+\s+R", blob):
        fd = _dict_of(objs.get(int(num), b""))
        tu_ref = _ref(fd, b"/ToUnicode")
        tmap = None
        if tu_ref is not None and tu_ref in objs:
            try:
                payload = _stream_bytes(objs[tu_ref])
            except UnreadablePdf:
                payload = None
            if payload:
                tmap = _tounicode_map(payload)
        subtype = _name(fd, b"/Subtype") or b""
        two = subtype == b"Type0"
        if two:
            widths, default = _cid_widths(fd, objs)
            src = "/W" if widths else "estimated"
        else:
            widths, default = _simple_widths(fd, objs), 500.0
            src = "/Widths" if widths else "estimated"
        fonts[name.decode("latin-1")] = _Font(
            tmap, two, widths, default, src)
    return fonts


# ---------------------------------------------------------------------------
# content stream -> positioned text
# ---------------------------------------------------------------------------

_TOKEN = re.compile(rb"""
      (?P<str>\((?:\\.|[^()\\])*\))       # (literal string), escapes honoured
    | (?P<hex><[0-9A-Fa-f\s]*>)           # <hex string>
    | (?P<name>/[A-Za-z0-9#\-+.]+)
    | (?P<num>[-+]?\d*\.?\d+)
    | (?P<arr>[\[\]])
    | (?P<op>[A-Za-z'"*]+)
""", re.X | re.S)

_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b",
            b"f": b"\f", b"(": b"(", b")": b")", b"\\": b"\\"}


def _unescape(s: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(s):
        c = s[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        nxt = s[i + 1:i + 2]
        if nxt in _ESCAPES:
            out += _ESCAPES[nxt]
            i += 2
        elif nxt.isdigit():
            m = re.match(rb"[0-7]{1,3}", s[i + 1:])
            out.append(int(m.group(0), 8) & 0xFF)
            i += 1 + len(m.group(0))
        else:
            i += 2
    return bytes(out)


def _mul(m: List[float], n: List[float]) -> List[float]:
    """Compose two PDF 3x2 affine matrices, ``m`` then ``n``."""
    return [m[0] * n[0] + m[1] * n[2],
            m[0] * n[1] + m[1] * n[3],
            m[2] * n[0] + m[3] * n[2],
            m[2] * n[1] + m[3] * n[3],
            m[4] * n[0] + m[5] * n[2] + n[4],
            m[4] * n[1] + m[5] * n[3] + n[5]]


_IDENT = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

#: an inline image's payload is raw binary between ``ID`` and ``EI``; left in
#: the token stream it can spell out operators that were never drawn.
_INLINE_IMAGE = re.compile(rb"\bBI\b.*?\bID\b.*?\bEI\b", re.S)


class _Marker:
    """Array open-bracket sentinel on the operand stack."""
    __slots__ = ()


class _Str(bytes):
    """A STRING operand, tagged so it can never be mistaken for a number.

    Both arrive from the tokenizer as ``bytes``, and inside a ``TJ`` array
    the two are interleaved: ``[(a) -120 (b)]``.  Deciding which is which by
    trying ``float()`` works only until a string IS numeric -- and on a spec
    sheet that is the normal case, because the values are numbers::

        [(62.0)] TJ          -> float(b"62.0") succeeds -> read as a KERN,
                                and the number is silently dropped
        [(6) 0 (2.0 in)] TJ  -> "6" read as a kern -> the value becomes
                                "2.0 in", a WRONG dimension carrying a
                                citation to the user's own document

    The second is the worse one by far: it is exactly what
    :mod:`rvt.specsheet.sheet` promises cannot happen.  Found by the
    independent review of #688, which measured it against pdfminer on the
    same bytes (it reads ``Height 62.0 in``; we read ``2.0 in``).  The
    fixture could not catch it because every value in it contained a space,
    so ``float()`` always failed and the ambiguous path was never taken.
    """
    __slots__ = ()


def _text_ops(content: bytes,
              fonts: Dict[str, _Font]) -> Tuple[List[Glyph], List[str]]:
    """Walk the content stream, tracking BOTH matrices, emitting glyphs.

    Returns the glyphs and any honest remarks about the reading (today: a
    font whose advance widths had to be estimated, which shifts columns).

    Two things here are not optional for a table:

    * **The CTM is composed with the text matrix.**  A producer that wraps a
      table in ``q 1 0 0 1 72 640 cm ... Q`` puts every glyph 72pt right and
      640pt up of where the text matrix alone says.  Ignoring that does not
      corrupt the text -- it silently moves the whole table, and any
      column/row tolerance tuned on one file stops working on the next.
    * **The pen advances after every drawn run** by the font's own widths
      (:meth:`_Font.advance`).  Without it, the runs of one ``TJ`` array pile
      up at a single x.
    """
    glyphs: List[Glyph] = []
    notes: List[str] = []
    stack: List[object] = []
    ctm = list(_IDENT)
    gstack: List[List[float]] = []
    tm = list(_IDENT)
    tlm = list(_IDENT)
    size, leading, font_name = 12.0, 0.0, ""
    char_space, word_space, hscale = 0.0, 0.0, 1.0
    cur = _Font()
    estimated: set = set()

    def num(v) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    def emit(raw: bytes) -> None:
        nonlocal tm
        txt = cur.decode(raw)
        M = _mul(tm, ctm)
        tx = cur.advance(raw, size, char_space, word_space, hscale)
        if txt.strip():
            scale = math.hypot(M[2], M[3]) or 1.0
            # the advance is in TEXT space; the run's on-page width is that
            # advance carried through the same matrix the origin went through
            glyphs.append(Glyph(txt, M[4], M[5], size * scale, font_name,
                                tx * math.hypot(M[0], M[1] or 0.0)))
            if cur.width_source == "estimated" and font_name:
                estimated.add(font_name)
        tm = _mul([1.0, 0.0, 0.0, 1.0, tx, 0.0], tm)

    for m in _TOKEN.finditer(_INLINE_IMAGE.sub(b" ", content)):
        kind = m.lastgroup
        tok = m.group()
        if kind == "str":
            stack.append(_Str(_unescape(tok[1:-1])))
        elif kind == "hex":
            h = re.sub(rb"\s", b"", tok[1:-1])
            if len(h) % 2:
                h += b"0"
            try:
                stack.append(_Str(bytes.fromhex(h.decode("ascii"))))
            except ValueError:
                stack.append(_Str(b""))
        elif kind == "arr":
            if tok == b"[":
                stack.append(_Marker())
            else:
                items: List[object] = []
                while stack and not isinstance(stack[-1], _Marker):
                    items.append(stack.pop())
                if stack:
                    stack.pop()
                stack.append(list(reversed(items)))
        elif kind in ("name", "num"):
            stack.append(tok)
        elif kind == "op":
            op = tok
            if op == b"q":
                gstack.append(list(ctm))
            elif op == b"Q":
                ctm = gstack.pop() if gstack else list(_IDENT)
            elif op == b"cm" and len(stack) >= 6:
                ctm = _mul([num(x) for x in stack[-6:]], ctm)
            elif op == b"BT":
                tm = list(_IDENT)
                tlm = list(_IDENT)
            elif op == b"Tf" and len(stack) >= 2:
                size = num(stack[-1])
                nm = stack[-2]
                font_name = (nm[1:].decode("latin-1")
                             if isinstance(nm, bytes) and nm.startswith(b"/")
                             else "")
                cur = fonts.get(font_name, _Font())
            elif op == b"TL" and stack:
                leading = num(stack[-1])
            elif op == b"Tc" and stack:
                char_space = num(stack[-1])
            elif op == b"Tw" and stack:
                word_space = num(stack[-1])
            elif op == b"Tz" and stack:
                hscale = num(stack[-1]) / 100.0
            elif op in (b"Td", b"TD") and len(stack) >= 2:
                dx, dy = num(stack[-2]), num(stack[-1])
                if op == b"TD":
                    leading = -dy
                tlm = _mul([1.0, 0.0, 0.0, 1.0, dx, dy], tlm)
                tm = list(tlm)
            elif op == b"Tm" and len(stack) >= 6:
                tlm = [num(x) for x in stack[-6:]]
                tm = list(tlm)
            elif op == b"T*":
                tlm = _mul([1.0, 0.0, 0.0, 1.0, 0.0, -leading], tlm)
                tm = list(tlm)
            elif op == b"Tj" and stack:
                if isinstance(stack[-1], _Str):
                    emit(stack[-1])
            elif op == b"TJ" and stack:
                arr = stack[-1]
                if isinstance(arr, list):
                    for t in arr:
                        # a tagged string is TEXT, whatever it looks like:
                        # "62.0" is a value on a spec sheet, not a kern
                        if isinstance(t, _Str):
                            emit(t)
                            continue
                        if isinstance(t, bytes) and t.startswith(b"/"):
                            continue
                        if isinstance(t, bytes):
                            try:
                                adj = float(t)
                            except (TypeError, ValueError):
                                continue
                            # kerning in 1/1000 em: a large negative one IS a
                            # column gap, so it moves the pen like any advance
                            tm = _mul([1.0, 0.0, 0.0, 1.0,
                                       -adj / 1000.0 * size * hscale, 0.0], tm)
            elif op in (b"'", b'"'):
                tlm = _mul([1.0, 0.0, 0.0, 1.0, 0.0, -leading], tlm)
                tm = list(tlm)
                if stack and isinstance(stack[-1], _Str):
                    emit(stack[-1])
            stack = []
    if estimated:
        notes.append(
            "no advance widths declared for font(s) %s -- glyph x positions "
            "on this page are estimated at 0.5 em and columns may be off"
            % ", ".join(sorted(estimated)))
    return glyphs, notes


# ---------------------------------------------------------------------------
# public entry
# ---------------------------------------------------------------------------

def read_pdf(path: str, max_pages: int = 64) -> List[Page]:
    """Every page's positioned text.

    :raises PdfError: the file is not a PDF.
    :raises UnreadablePdf: it is a PDF whose text cannot honestly be
        recovered (encrypted, image-only, an unsupported stream filter).
        The caller reports the reason and still delivers (hard rule 1).
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    if not raw.startswith(b"%PDF"):
        raise PdfError("not a PDF (no %%PDF header): %s" % path)
    if _ENCRYPT.search(raw):
        raise UnreadablePdf(
            "the PDF is encrypted; the stdlib reader does not decrypt")

    objs = _find_objects(raw)
    if not objs:
        raise UnreadablePdf("no PDF objects found -- the file may be truncated")

    page_nums = _page_objects(objs)
    if not page_nums:
        raise UnreadablePdf("no /Page objects found")

    capped = ""
    if len(page_nums) > max_pages:
        # silently dropping pages 65+ of a 100-page submittal turns
        # "we did not look" into "the sheet does not say so", and
        # ParsedSheet.questions() then asks about a field the document
        # answers on page 80
        capped = ("this PDF has %d pages; only the first %d were read "
                  "(max_pages=%d)" % (len(page_nums), max_pages, max_pages))

    pages: List[Page] = []
    for n, num in enumerate(page_nums[:max_pages], start=1):
        body = objs.get(num, b"")
        d = _dict_of(body)
        w, h = _media_box(d, objs)
        res = _resources(d, objs)
        fonts = _load_fonts(objs, res)
        note = ""
        chunks: List[bytes] = []
        for cnum in _refs(d, b"/Contents"):
            cbody = objs.get(cnum)
            if cbody is None:
                continue
            try:
                payload = _stream_bytes(cbody)
            except UnreadablePdf as exc:
                note = str(exc)
                payload = None
            if payload:
                chunks.append(payload)
        glyphs, gnotes = (_text_ops(b"\n".join(chunks), fonts)
                          if chunks else ([], []))
        if gnotes:
            note = "; ".join([note] + gnotes) if note else "; ".join(gnotes)
        if not glyphs and not note:
            note = ("page draws no text -- it is probably a scanned image; "
                    "this reader does no OCR")
        pages.append(Page(n, glyphs, w, h, note))
    if capped and pages:
        pages[-1].note = "; ".join(x for x in (pages[-1].note, capped) if x)
    return pages


def _page_objects(objs: Dict[int, bytes]) -> List[int]:
    """Page object numbers in document order where the tree is walkable,
    else every /Type /Page object in file order (a stale tree must not lose
    the content we can plainly see)."""
    root = None
    for num, body in objs.items():
        d = _dict_of(body)
        if _name(d, b"/Type") == b"Catalog":
            root = _ref(d, b"/Pages")
            break
    ordered: List[int] = []
    if root is not None:
        seen = set()

        def walk(n: int) -> None:
            if n in seen or n not in objs:
                return
            seen.add(n)
            d = _dict_of(objs[n])
            t = _name(d, b"/Type")
            if t == b"Page":
                ordered.append(n)
                return
            for kid in _refs(d, b"/Kids"):
                walk(kid)

        walk(root)
    if ordered:
        return ordered
    return [n for n, b in sorted(objs.items())
            if _name(_dict_of(b), b"/Type") == b"Page"]


#: the PDF default page size, used whenever /MediaBox is absent
#: or unreadable
_LETTER = (612.0, 792.0)


_BOX = re.compile(rb"\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)")


def _media_box(d: bytes, objs: Dict[int, bytes], depth: int = 8) -> Tuple[float, float]:
    """The page size, following BOTH ways the format lets a page get one.

    ``/MediaBox`` is an INHERITABLE attribute: a producer whose pages share a
    size states it once on the ``/Pages`` node and omits it from every page,
    which is the common case and the one a docstring here previously
    misnamed as the indirect-reference case (#688 third review -- measured:
    a parent carrying ``[0 0 1224 792]`` gave 612x792).  Both are followed:
    the value may also be an indirect reference at either level.

    ``depth`` bounds the parent walk, because a malformed file can point a
    page at itself and ``read_sheet`` must never hang or raise.
    """
    m = _BOX.search(d[d.find(b"/MediaBox"):]) if b"/MediaBox" in d else None
    if not m:
        ref = _ref(d, b"/MediaBox")
        if ref is not None and ref in objs:
            m = _BOX.search(objs[ref])
    if not m and depth > 0:
        parent = _ref(d, b"/Parent")
        if parent is not None and parent in objs:
            return _media_box(_dict_of(objs[parent]), objs, depth - 1)
    if not m:
        return _LETTER                             # US Letter, the PDF default
    try:
        x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
    except ValueError:
        # `[- - - -]` and `[. . . .]` both match the character class and both
        # fail float().  Found by the #688 review, which fuzzed 1200 random
        # corruptions and 180 truncations and got exactly TWO escapes, both
        # here -- and an escape here is not cosmetic: `read_sheet` documents
        # that it never raises for a bad document, so the caller can report
        # the reason and still deliver (hard rule 1).  A page size we cannot
        # read is not a reason to lose the page.
        return _LETTER
    w, h = abs(x1 - x0), abs(y1 - y0)
    return (w or _LETTER[0], h or _LETTER[1])


def _resources(d: bytes, objs: Dict[int, bytes]) -> bytes:
    m = re.search(rb"/Resources\s*(<<.*?>>|\d+\s+\d+\s+R)", d, re.S)
    if not m:
        return b""
    blob = m.group(1)
    if blob.startswith(b"<<"):
        return blob
    num = int(re.match(rb"(\d+)", blob).group(1))
    return _dict_of(objs.get(num, b""))
