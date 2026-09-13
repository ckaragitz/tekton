"""fixtures_pdf.py -- build small, REALISTIC PDFs from the stdlib, so the
spec-sheet reader (#688) can be measured instead of described.

Why a writer and not a checked-in sample: a vendor's spec sheet is a
third-party document and this repo is public (hard rules 3 and 6), so no real
sheet may be committed.  A writer is also the better instrument -- every
fixture states the x/y it drew at, so a test can assert the reader recovered
*those* coordinates rather than "some plausible numbers".

The font is deliberately MONOSPACE-by-declaration (every ``/Widths`` entry is
600/1000 em), which makes each glyph's advance exactly ``0.6 * size``.  That
is what lets ``test_specsheet_pdftext_688`` predict the x of the n-th
character instead of merely checking it increased.

What can be varied, because each one is a real failure mode of real sheets:

``compress``      FlateDecode (the default) or a raw stream.
``stale_xref``    write an xref whose offsets are WRONG -- the reader is
                  documented as reconstructing rather than trusting it.
``draw``          ``"Tm"`` (one absolute placement per cell), ``"TJ"`` (a
                  whole row in one kerned array -- the case that collapses
                  into a single cell if the pen never advances), or ``"cm"``
                  (the row wrapped in ``q <translate> cm ... Q``).
``font``          ``"simple"`` (WinAnsi Type1) or ``"type0"`` (2-byte CIDs
                  with a ``/ToUnicode`` CMap and a ``/W`` array -- what a
                  subset-embedded sheet actually looks like).
``filter_name``   force an unsupported filter, to pin the named refusal.
``no_text``       emit a content stream that draws no text at all: the
                  scanned-sheet case, which must be REPORTED, never read as
                  an empty table.
"""
from __future__ import annotations

import zlib
from typing import Dict, List, Optional, Sequence, Tuple

#: (x, y, text) in PDF user space, origin bottom-left
Draw = Tuple[float, float, str]

PAGE_W, PAGE_H = 612.0, 792.0

#: every code advances this many 1/1000 em -- see the module docstring
WIDTH = 600.0

#: what ``WIDTH`` means for a glyph drawn at ``size``
def advance(size: float, n_chars: int = 1) -> float:
    return WIDTH / 1000.0 * size * n_chars


def _esc(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        b = ch.encode("latin-1", "replace")
        if b in (b"(", b")", b"\\"):
            out += b"\\" + b
        else:
            out += b
    return bytes(out)


def _content(draws: Sequence[Draw], size: float, draw: str) -> bytes:
    """The page's content stream, in one of the three shapes above."""
    if draw == "TJ":
        # every draw on one baseline becomes ONE kerned array: the pen must
        # advance by the font's widths or all of them land at the first x
        by_y: Dict[float, List[Draw]] = {}
        for d in draws:
            by_y.setdefault(round(d[1], 3), []).append(d)
        parts = [b"BT", b"/F1 %g Tf" % size]
        for y in sorted(by_y, reverse=True):
            row = sorted(by_y[y], key=lambda d: d[0])
            parts.append(b"1 0 0 1 %g %g Tm" % (row[0][0], y))
            arr, pen = [], row[0][0]
            for x, _y, text in row:
                gap = x - pen
                if arr:
                    # PDF kerning is SUBTRACTED, in 1/1000 em of the size
                    arr.append(b"%g" % (-gap / size * 1000.0))
                arr.append(b"(%s)" % _esc(text))
                pen = x + advance(size, len(text))
            parts.append(b"[" + b" ".join(arr) + b"] TJ")
        parts.append(b"ET")
        return b"\n".join(parts)

    parts = []
    for x, y, text in draws:
        body = [b"BT", b"/F1 %g Tf" % size]
        if draw == "cm":
            # the table is laid out relative to a translated CTM: the glyph's
            # real page position is Tm x CTM, not Tm
            parts.append(b"q 1 0 0 1 %g %g cm" % (x, y))
            body.append(b"1 0 0 1 0 0 Tm")
        else:
            body.append(b"1 0 0 1 %g %g Tm" % (x, y))
        body.append(b"(%s) Tj" % _esc(text))
        body.append(b"ET")
        parts.append(b"\n".join(body))
        if draw == "cm":
            parts.append(b"Q")
    return b"\n".join(parts)


def _type0_content(draws: Sequence[Draw], size: float) -> bytes:
    """The same draws as 2-byte CIDs -- CID == Unicode code point here, which
    is what the /ToUnicode CMap this fixture writes declares."""
    parts = [b"BT", b"/F1 %g Tf" % size]
    for x, y, text in draws:
        hexed = "".join("%04X" % ord(ch) for ch in text).encode("ascii")
        parts.append(b"1 0 0 1 %g %g Tm" % (x, y))
        parts.append(b"<" + hexed + b"> Tj")
    parts.append(b"ET")
    return b"\n".join(parts)


def _tounicode(codes: Sequence[int]) -> bytes:
    body = [b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap",
            b"1 begincodespacerange <0000> <FFFF> endcodespacerange"]
    chunk = [c for c in sorted(set(codes))]
    body.append(b"%d beginbfchar" % len(chunk))
    for c in chunk:
        body.append(b"<%04X> <%04X>" % (c, c))
    body.append(b"endbfchar")
    body.append(b"endcmap CMapName currentdict /CMap defineresource pop end end")
    return b"\n".join(body)


def build_pdf(path: str,
              pages: Sequence[Sequence[Draw]],
              size: float = 10.0,
              compress: bool = True,
              stale_xref: bool = False,
              draw: str = "Tm",
              font: str = "simple",
              filter_name: Optional[str] = None,
              no_text: bool = False,
              encrypt: bool = False) -> str:
    """Write a PDF at ``path`` and return it.  See the module docstring."""
    objs: List[bytes] = []                       # 1-based object bodies

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    catalog = add(b"")                           # 1, filled below
    pages_o = add(b"")                           # 2
    font_o = add(b"")                            # 3 (+ descendants)

    kids: List[int] = []
    for draws in pages:
        if no_text:
            payload = b"0 0 1 RG 72 72 400 400 re S"
        elif font == "type0":
            payload = _type0_content(draws, size)
        else:
            payload = _content(draws, size, draw)
        if filter_name:
            filt = b"/Filter /" + filter_name.encode("ascii")
            raw = payload
        elif compress:
            filt, raw = b"/Filter /FlateDecode", zlib.compress(payload)
        else:
            filt, raw = b"", payload
        cnum = add(b"<< /Length %d %s >>\nstream\n" % (len(raw), filt)
                   + raw + b"\nendstream")
        pnum = add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %g %g] "
                   b"/Resources << /Font << /F1 %d 0 R >> >> "
                   b"/Contents %d 0 R >>" % (pages_o, PAGE_W, PAGE_H,
                                             font_o, cnum))
        kids.append(pnum)

    objs[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_o
    objs[pages_o - 1] = (b"<< /Type /Pages /Kids [" +
                         b" ".join(b"%d 0 R" % k for k in kids) +
                         b"] /Count %d >>" % len(kids))

    if font == "type0":
        codes = sorted({ord(ch) for pg in pages for _x, _y, t in pg for ch in t})
        tu = _tounicode(codes)
        tu_raw = zlib.compress(tu) if compress else tu
        tu_o = add(b"<< /Length %d %s >>\nstream\n"
                   % (len(tu_raw), b"/Filter /FlateDecode" if compress else b"")
                   + tu_raw + b"\nendstream")
        w_arr = b" ".join(b"%d [%d]" % (c, int(WIDTH)) for c in codes)
        desc_o = add(b"<< /Type /Font /Subtype /CIDFontType2 "
                     b"/BaseFont /AAAAAA+Probe /DW 1000 /W [%s] "
                     b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
                     b"/Supplement 0 >> >>" % w_arr)
        objs[font_o - 1] = (b"<< /Type /Font /Subtype /Type0 "
                            b"/BaseFont /AAAAAA+Probe /Encoding /Identity-H "
                            b"/DescendantFonts [%d 0 R] /ToUnicode %d 0 R >>"
                            % (desc_o, tu_o))
    else:
        widths = b" ".join([b"%d" % int(WIDTH)] * 95)
        objs[font_o - 1] = (b"<< /Type /Font /Subtype /Type1 "
                            b"/BaseFont /Helvetica /FirstChar 32 /LastChar 126 "
                            b"/Widths [%s] /Encoding /WinAnsiEncoding >>" % widths)

    buf = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: List[int] = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(buf))
        buf += b"%d 0 obj\n" % i + body + b"\nendobj\n"

    xref_at = len(buf)
    buf += b"xref\n0 %d\n" % (len(objs) + 1)
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        # a STALE xref points everywhere but at the object: the reader is
        # documented as reconstructing, and this is what proves it does
        buf += b"%010d 00000 n \n" % (0 if stale_xref else off)
    trailer = b"<< /Size %d /Root %d 0 R" % (len(objs) + 1, catalog)
    if encrypt:
        trailer += b" /Encrypt %d 0 R" % catalog
    trailer += b" >>"
    buf += b"trailer\n" + trailer + b"\nstartxref\n%d\n%%%%EOF\n" % xref_at

    with open(path, "wb") as fh:
        fh.write(bytes(buf))
    return path


# ---------------------------------------------------------------------------
# a spec sheet shaped like the real thing
# ---------------------------------------------------------------------------

#: A two-column "Specifications" table plus an identity block, in the shape
#: vendors actually publish.  Values are INVENTED for this fixture -- no
#: manufacturer's document was read to produce them, and nothing here may be
#: treated as a fact about any real product (hard rule 3).
SHEET_ROWS: List[Tuple[str, str]] = [
    ("Height", "62.0 in"),
    ("Width", "20-1/2 in"),
    ("Depth", "5.75 in"),
    ("Weight", "145 lb"),
    ("Voltage", "480Y/277 V"),
    ("Main Bus Rating", "400 A"),
    ("Short Circuit Rating", "65 kAIC"),
    ("Enclosure", "NEMA 1"),
]


def spec_sheet_draws(x_label: float = 72.0, x_value: float = 300.0,
                     y_top: float = 700.0, dy: float = 18.0) -> List[Draw]:
    """The identity block + the table above, as positioned draws."""
    out: List[Draw] = [
        (x_label, y_top + 3 * dy, "PROBEWORKS INDUSTRIES"),
        (x_label, y_top + 2 * dy, "Catalog Number: PW-400-42-NEMA1"),
        (x_label, y_top + dy, "Specifications"),
    ]
    for i, (label, value) in enumerate(SHEET_ROWS):
        y = y_top - i * dy
        out.append((x_label, y, label))
        out.append((x_value, y, value))
    return out
