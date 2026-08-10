"""rvt.global_framing -- the Global-stream framing tokens under a release.

``rvt.versions.reading(path)`` re-points the six partition-framing ordinals
inside ``rvt.partitions`` at a file's own release, and that is all the
partition READ path needs.  Three more byte tokens are built from the SAME
class ordinals (``ContentMarker`` / ``ContentKey``) but live as pre-packed
module constants ``versions.reading`` cannot reach:

    rvt.famgen.factory.CD_SEPARATOR      u16 ContentMarker, i32 -1, u16 ContentKey, i32 -1
    rvt.famgen.factory.CD_END_RECORD     u16 ContentMarker, i32 0, i32 -1, u32 0
    rvt.famgen.famdoc_adoc.FAMILY_END_RECORD          u16 ContentMarker, i32 0, i32 -1
    rvt.genesis.skeleton.EMPTY_CONTENT_DOCUMENTS      == CD_END_RECORD

Left at their default-release (2026) values, ``parse_content_documents`` on a
Revit 2025 file finds ZERO entries without raising, and every four-registry
census taken that way reads ``units N / ContentDocuments 0`` -- a false
FOUR-REGISTRY INCOHERENCE on any 2025/2024 file that carries loaded content
(docs/inbox/famload-2025-lane.md).  The ADocument (``Global/Latest``) has the
same problem one layer up: ``rvt.adocument.decode_latest`` with no explicit
decoder decodes against the default-release schema.

This module is the one place those tokens are derived from the ordinals in
force.  :func:`reading` is the strict read-side context (the file's own
schema: partition framing + the 32-bit id layer for <= 2023 files + the
tokens + the ADocument decoder); :func:`enter_own_release` is the lenient
ladder every INSTRUMENT enters (own schema -> the pinned table of the
release ``BasicFileInfo`` declares -> the native constants, reporting the
rung, never raising).  It is a leaf (imports the patched modules lazily),
restores everything LIFO on exit, nests safely, and never touches disk.  The
WRITE-side (creation) context that also swaps encoders, constructor
singletons and the port layer is ``rvt.frontdoor.release_ctx``, which
composes this module rather than duplicating it.

(The deeper fix -- the three constants becoming call-time reads of
``rvt.partitions`` so ``versions.reading`` alone suffices -- touches
famgen.factory / famdoc_adoc / genesis.skeleton and every byte comparison
against them; filed as a follow-up, see the record.)
"""
from __future__ import annotations

import os
import struct
from collections import OrderedDict
from contextlib import ExitStack, contextmanager
from typing import Any, Dict, Iterator, Mapping, Optional

__all__ = ["tokens", "bound", "reading", "enter_own_release", "schema_of"]

#: ``versions.schema_of`` results by (abspath, size, mtime_ns).  NOT a parse
#: cache -- the parse itself is served by ``rvt.schema``'s sha256 memo
#: (#183) whichever way the bytes arrive.  What a hit here skips is the
#: container re-open + ``Formats/Latest`` re-inflate + sha256 that
#: ``versions.schema_of`` pays before it can reach that memo: ~7 ms per
#: repeat :func:`reading` entry of the same file (measured #291: 9 of 18
#: entries hit in a 6-panel prompt job, 1 of 2 in an edit).  Retire it with
#: #251, once :func:`reading` reads the schema once per entry and hands it
#: down.  Tiny LRU; a schema is read-only to every consumer.
_SCHEMAS: "OrderedDict[tuple, Any]" = OrderedDict()
_SCHEMAS_MAX = 4


def schema_of(source: Any):
    """``rvt.versions.schema_of`` minus the re-inflate for on-disk paths seen
    before (keyed by path, size and mtime, so a rewritten file is re-read)."""
    from . import versions as V
    if not isinstance(source, (str, os.PathLike)):
        return V.schema_of(source)
    path = os.path.abspath(os.fspath(source))
    st = os.stat(path)
    key = (path, st.st_size, st.st_mtime_ns)
    hit = _SCHEMAS.get(key)
    if hit is not None:
        _SCHEMAS.move_to_end(key)
        return hit
    schema = V.schema_of(path)
    _SCHEMAS[key] = schema
    while len(_SCHEMAS) > _SCHEMAS_MAX:
        _SCHEMAS.popitem(last=False)
    return schema


def tokens(ordinals: Optional[Mapping[str, int]] = None) -> Dict[str, bytes]:
    """The Global-stream byte tokens for ``ordinals`` (default: whatever
    ``rvt.partitions`` currently holds, i.e. the release ``versions.reading``
    activated -- or the native one outside any context)."""
    if ordinals is None:
        from . import partitions as P
        cm, ck = int(P.CONTAINER_CLASS), int(P.UNIT_INNER_CLASS)
    else:
        cm, ck = int(ordinals["CONTAINER_CLASS"]), int(ordinals["UNIT_INNER_CLASS"])
    end = struct.pack("<HiiI", cm, 0, -1, 0)
    return {
        "CD_SEPARATOR": struct.pack("<HiHi", cm, -1, ck, -1),
        "CD_END_RECORD": end,
        "FAMILY_END_RECORD": struct.pack("<Hii", cm, 0, -1),
        "EMPTY_CONTENT_DOCUMENTS": end,
    }


@contextmanager
def bound(ordinals: Optional[Mapping[str, int]] = None, *,
          schema: Any = None) -> Iterator[Dict[str, bytes]]:
    """Bind the Global-stream tokens (and, given ``schema``, the default
    ADocument decoder) to ``ordinals`` / the ordinals in force; restore on
    exit.  Yields the tokens bound."""
    from . import adocument as ADOC
    from .famgen import factory as FF
    from .famgen import famdoc_adoc as FDA
    from .genesis import skeleton as GSK

    toks = tokens(ordinals)
    saved = [(FF, "CD_SEPARATOR", FF.CD_SEPARATOR),
             (FF, "CD_END_RECORD", FF.CD_END_RECORD),
             (FDA, "FAMILY_END_RECORD", FDA.FAMILY_END_RECORD),
             (GSK, "EMPTY_CONTENT_DOCUMENTS", GSK.EMPTY_CONTENT_DOCUMENTS)]
    FF.CD_SEPARATOR = toks["CD_SEPARATOR"]
    FF.CD_END_RECORD = toks["CD_END_RECORD"]
    FDA.FAMILY_END_RECORD = toks["FAMILY_END_RECORD"]
    GSK.EMPTY_CONTENT_DOCUMENTS = toks["EMPTY_CONTENT_DOCUMENTS"]
    if schema is not None:
        saved.append((ADOC, "_DECODER", ADOC._DECODER))
        ADOC._DECODER = ADOC.ADocumentDecoder(schema)
    try:
        yield toks
    finally:
        for mod, name, val in reversed(saved):
            setattr(mod, name, val)


@contextmanager
def reading(source: Any) -> Iterator[Dict[str, int]]:
    """Read ``source`` under its OWN release: ``records32.reading32`` (framing
    by name from its schema + the 32-bit id layer for Revit <= 2023 files)
    plus :func:`bound` (the Global-stream tokens and the ADocument decoder).
    Strict: an unreadable schema raises.  Yields the ordinals in force."""
    from .versions import records32 as R32
    with R32.reading32(source) as ords, bound(ords, schema=schema_of(source)):
        yield ords


def enter_own_release(stack: ExitStack, path: str) -> Optional[str]:
    """Put ``path``'s OWN release in force on ``stack`` (restored when the
    stack closes; nest-safe inside an outer context) -- the lenient ladder
    every instrument uses:

    the file's own schema (:func:`reading`)  ->  the pinned framing table +
    tokens of the release its ``BasicFileInfo`` declares (a file whose schema
    stream is damaged is still judged as what it is)  ->  nothing (the
    built-in latest-release constants).  Returns None when the schema
    resolved it, else one sentence naming the rung used and why -- callers
    report it, never raise."""
    from . import versions as V
    try:
        stack.enter_context(reading(path))
        return None
    except Exception as e:                           # corrupt / schema-less input
        cause = f"{type(e).__name__}: {e}"
    try:
        year = V.detect_release(path)
        ords = stack.enter_context(V.reading(year=year))   # UnknownRelease if None
        stack.enter_context(bound(ords))
    except Exception:                                # noqa: BLE001
        return (f"own-release framing not resolved ({cause}); checked against "
                f"the built-in latest-release constants")
    return (f"own schema unreadable ({cause}); checked against the pinned "
            f"Revit {year} framing table (the release BasicFileInfo declares)")
