"""rvt.specsheet._backend -- selection of the PDF READ backend.

CLAUDE.md section 2 declares ``olefile`` the ONLY runtime dependency, so a
PDF library must never become a required install.  This module is THE place
the spec-sheet lane's backend is chosen, and it copies the posture of
:mod:`rvt.ifc._fallback` (issue #130), which does the same job for IFC:

* a real ``pdfplumber`` installed (``pip install -e ".[pdf]"``) -> use it;
* nothing installed -> use the bundled stdlib reader
  :mod:`rvt.specsheet.pdftext`, so a text-layer sheet still reads on a bare
  interpreter with ZERO pip installs;
* ``RVT_PDFLITE_FORCE=1`` -> force the stdlib reader even when the wheel is
  present (the equivalence tests and backend A/B).

ONE DELIBERATE DIFFERENCE FROM ``_fallback``.  ``rvt.ifc`` fell back by
appending a look-alike ``ifcopenshell`` package to ``sys.path``, because its
consumer modules already said ``import ifcopenshell`` and must not be
edited.  This lane has no such constraint -- every consumer is ours and new
-- so the selection is an ordinary function call and no path is mutated.
The user-visible contract is the same (optional heavy backend, stdlib
fallback, force env, an availability predicate); only the mechanism is
simpler, and nothing global is touched.

Both backends return the SAME :class:`~rvt.specsheet.pdftext.Document`
shape, in the same coordinate convention (PDF user space, origin
bottom-left), so the table reader cannot tell them apart.
"""
from __future__ import annotations

import functools
import importlib.util
import os
from typing import List

from .pdftext import Document, Fragment, Page, PdfTextError, read_pdf

__all__ = [
    "FORCE_ENV", "BACKEND_DIST", "pdf_backend_installed", "using_stdlib_reader",
    "backend_name", "read_document",
]

#: set to a non-empty value to force the stdlib reader over an installed wheel
FORCE_ENV = "RVT_PDFLITE_FORCE"

#: the optional distribution the ``[pdf]`` extra installs
BACKEND_DIST = "pdfplumber"

_FINDER_ERRORS = (ImportError, AttributeError, ValueError)


@functools.lru_cache(maxsize=1)
def _spec_found() -> bool:
    try:
        return importlib.util.find_spec(BACKEND_DIST) is not None
    except _FINDER_ERRORS:
        # a broken install or an import blocker counts as "not there"; the
        # stdlib reader then serves, which is the safe direction
        return False


def pdf_backend_installed() -> bool:
    """Is the real :mod:`pdfplumber` importable in this process?"""
    return _spec_found()


def using_stdlib_reader() -> bool:
    """Will :func:`read_document` use the bundled stdlib reader?"""
    if os.environ.get(FORCE_ENV):
        return True
    return not pdf_backend_installed()


def backend_name() -> str:
    """The backend a report should name: ``pdftext`` or ``pdfplumber``."""
    return "pdftext" if using_stdlib_reader() else BACKEND_DIST


def _read_with_pdfplumber(path: str) -> Document:
    """Read through the optional wheel, into OUR Document shape.

    pdfplumber reports ``top`` growing DOWNWARD from the page top; the
    stdlib reader reports PDF user-space ``y`` growing UPWARD from the
    bottom.  Converting here (``y = height - top``) is what lets the table
    reader stay identical for both backends.
    """
    import pdfplumber                                   # noqa: PLC0415

    doc = Document(backend=BACKEND_DIST)
    try:
        with pdfplumber.open(path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                height = float(page.height or 0.0)
                frags: List[Fragment] = []
                for w in page.extract_words(use_text_flow=False,
                                            keep_blank_chars=False):
                    text = str(w.get("text", ""))
                    if not text:
                        continue
                    top = float(w.get("top", 0.0))
                    size = float(w.get("bottom", top)) - top
                    frags.append(Fragment(text=text,
                                          x=float(w.get("x0", 0.0)),
                                          y=height - top,
                                          size=size if size > 0 else 10.0))
                doc.pages.append(Page(number=idx, fragments=frags))
    except Exception as exc:                            # noqa: BLE001
        # never let the optional backend's own exception type escape as a
        # traceback -- hard rule 1: this becomes one clear line upstream
        raise PdfTextError(f"{os.path.basename(path)}: {BACKEND_DIST} could "
                           f"not read this PDF ({exc})") from exc
    if not doc.pages:
        raise PdfTextError(f"{os.path.basename(path)}: no page objects found")
    return doc


def read_document(path: str) -> Document:
    """Read ``path`` with whichever backend is selected."""
    if using_stdlib_reader():
        return read_pdf(path)
    return _read_with_pdfplumber(path)
