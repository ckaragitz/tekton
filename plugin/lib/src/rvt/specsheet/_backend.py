"""rvt.specsheet._backend -- which PDF extractor this process will use.

#688 DONE 2: the engine declares exactly one runtime dependency (``olefile``),
so a spec sheet must be readable with **no new one**.  The stdlib reader
(:mod:`rvt.specsheet.pdftext`) is that guarantee.  An optional ``[pdf]``
extra buys a fuller extractor for the documents the stdlib slice names and
refuses -- exotic stream filters, unusual encodings -- and this module is the
ONE place the choice is made, so every layer above it is backend-agnostic.

The architecture that makes this honest: **both backends produce the same
:class:`~.pdftext.Page` of positioned runs**, and everything downstream
(:mod:`~.layout`, :mod:`~.vocab`, :mod:`~.sheet`) reads only that.  So the
inference -- which cell, which field -- cannot differ between backends, only
the extraction can; and the two can be compared directly on one file, which
is what ``tests/test_specsheet_backend_688.py`` does.

* nothing installed            -> the stdlib reader.
* ``pdfplumber`` importable    -> pdfplumber, adapted to ``Page``/``Glyph``.
* ``RVT_PDF_STDLIB_FORCE=1``   -> the stdlib reader regardless, the one
  explicitly-requested case where it must beat an installed wheel (A/B
  equivalence, and reproducing a user's report from a bare surface).
  Mirrors ``RVT_STEPLITE_FORCE`` in :mod:`rvt.ifc._fallback`.

A backend is never chosen because it gave a "better" answer: that would make
the reading depend on what happens to be installed, and two users would get
two different families from one document with no way to tell why.
"""
from __future__ import annotations

import importlib.util
import os
from typing import List, Tuple

from .pdftext import Glyph, Page, PdfError, UnreadablePdf, read_pdf

__all__ = ["FORCE_ENV", "backend_name", "extract_pages"]

#: set to a non-empty value to pin the stdlib reader over an installed extra
FORCE_ENV = "RVT_PDF_STDLIB_FORCE"

#: the optional extractors this adapter knows, in preference order
_CANDIDATES = ("pdfplumber",)


def backend_name() -> str:
    """``"stdlib"`` or the importable extra that will be used."""
    if os.environ.get(FORCE_ENV):
        return "stdlib"
    for name in _CANDIDATES:
        try:
            if importlib.util.find_spec(name) is not None:
                return name
        except (ImportError, AttributeError, ValueError):
            continue
    return "stdlib"


def _pdfplumber_pages(path: str, max_pages: int) -> List[Page]:
    """pdfplumber's per-character output, adapted to ``Page``/``Glyph``.

    One ``Glyph`` per character: the layout layer merges runs by gap anyway,
    so handing it characters loses nothing and avoids re-deriving pdfplumber's
    own word grouping (whose thresholds are not ours).

    Positions come from each char's own text matrix (``matrix[4]``,
    ``matrix[5]``) where pdfplumber exposes it -- the same quantity the
    stdlib reader records -- and from the glyph box (``x0``, ``y0``)
    otherwise.  Mixing the two silently would make the backends disagree by a
    descender's height on some files and not others.
    """
    import pdfplumber                                   # optional extra

    out: List[Page] = []
    with pdfplumber.open(path) as pdf:
        for n, page in enumerate(pdf.pages[:max_pages], start=1):
            glyphs: List[Glyph] = []
            for ch in (page.chars or []):
                m = ch.get("matrix")
                if m and len(m) >= 6:
                    x, y = float(m[4]), float(m[5])
                else:
                    x, y = float(ch.get("x0", 0.0)), float(ch.get("y0", 0.0))
                glyphs.append(Glyph(
                    str(ch.get("text", "")), x, y,
                    float(ch.get("size", 0.0)) or 1.0,
                    str(ch.get("fontname", "")),
                    float(ch.get("x1", x)) - float(ch.get("x0", x))))
            note = ""
            if not any(g.text.strip() for g in glyphs):
                note = ("page draws no text -- it is probably a scanned "
                        "image; no OCR is attempted")
            out.append(Page(n, glyphs, float(page.width), float(page.height),
                            note))
    return out


def extract_pages(path: str, max_pages: int = 64) -> Tuple[List[Page], str]:
    """``(pages, backend used)``.

    The optional extra's own failures are NOT swallowed into a fallback: if
    it is installed and cannot read the file, that is the answer, reported
    with its reason.  Falling back on failure would mean the same file reads
    differently on two machines and neither user could reproduce the other.
    """
    name = backend_name()
    if name == "stdlib":
        return read_pdf(path, max_pages=max_pages), "stdlib"
    try:
        return _pdfplumber_pages(path, max_pages), name
    except (UnreadablePdf, PdfError):
        raise
    except OSError:
        # A missing or unreadable FILE is a caller bug, not a bad document,
        # and `read_sheet` deliberately lets it raise.  Folding it into
        # UnreadablePdf made that depend on which backend was installed:
        # with the extra, a typo'd path came back as a ParsedSheet saying
        # "pdfplumber could not read this PDF: FileNotFoundError"; without
        # it, the same call raised.  Found by the #688 review -- and it is
        # the exact thing this module claims cannot happen, since the
        # backend is supposed to change the extraction and nothing above it.
        raise
    except Exception as exc:                             # the extra's own errors
        raise UnreadablePdf("%s could not read this PDF: %s: %s"
                            % (name, type(exc).__name__, exc))
