"""The partition stream's TAIL: what follows the stream end record (#938).

A ``Partitions/<N>`` logical stream is ``header + units + end record``.  In a
Revit-born file the EXACT logical stream (``ecc.unframe_stream``, the final
CRCIO block's data length decoded from its pad-count field) ends AT the
10-byte end record ``u16 CONTAINER_CLASS, i32 0, i32 -1`` -- 0 bytes after it
on all six project samples (``docs/writer/content-splice.md`` row 11).  A
de-paged stream (``container.depage`` / ``RvtDocument.logical``) does not: its
last chunk carries the final block's pad-count + parity, which the partition
walker folds into its ``end_record`` (everything from the end offset on).  A
writer that re-frames that ``end_record`` as content bakes one generation of
the source's ECC parity into the new file's logical stream.

Our certified lineage already carries such a tail: the three bundled composed
bases end on the end record plus 1,272 (2026) / 2,116 (2025) / 1,252 (2024)
bytes, and the viewer certified them that way.  So the law the project
loaders keep is not "end exactly" (that would change the certified bases'
own bytes, unevidenced on 2025/2024) but:

    a load never changes the host's tail -- the written partition's exact
    content after the end offset is byte-identical to the HOST's exact
    content after its end offset.

Before #938 each project load added two generations of stale parity (pass 1
``commit_new_elements`` re-framed the host's de-paged tail; pass 2 re-read the
pass-1 file de-paged): +660 B (2026), +1,051 B (2025), +645 B (2024) per load.

Release-agnostic: the walker reads the release's own framing ordinals, so
callers run inside the file's release context (the loaders already do;
instruments use ``global_framing.enter_own_release``).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

__all__ = ["exact_tail", "host_tail", "keep_host_tail", "check_tail"]


def exact_tail(raw: bytes) -> Optional[Tuple[bytes, int, bytes]]:
    """``(exact_logical, end_offset, tail)`` of a CRCIO-framed partition
    stream, ``tail`` = the exact content from the end record on (end record
    included).  None when the final block does not decode exactly (an
    Autodesk-born partial block with heap bytes in its pad region -- those
    verify by syndrome in ``rvt.validate``, never by exact re-encode)."""
    from . import ecc
    from .partitions import StreamWalker
    try:
        ex = ecc.unframe_stream(raw)
    except ValueError:
        return None
    end = int(StreamWalker(ex, inflate=False, keep_data=False).end_offset)
    return ex, end, ex[end:]


def host_tail(path: str, partition: Optional[str] = None) -> Optional[bytes]:
    """The exact tail of ``path``'s partition stream (the first one when
    ``partition`` is None); None when it cannot be decoded exactly."""
    from .container import open_rvt
    with open_rvt(path) as f:
        pn = partition or f.partition_streams()[0]
        got = exact_tail(f.raw(pn))
    return None if got is None else got[2]


def keep_host_tail(pass_raw: bytes, tail: Optional[bytes]) -> Tuple[bytes, Dict[str, Any]]:
    """The logical partition content to splice into, from the RAW stream a
    writer's earlier pass framed (``pass_raw``; always exactly decodable --
    we framed it): its exact content cut right after the host's ``tail``.
    The pass's own tail is the host's tail followed by the stale parity the
    pass re-framed as content; that suffix is dropped.  When the host tail is
    unknown (None) or the pass's tail does not start with it, the exact
    content is returned whole (no generation is added by THIS read; the
    report says nothing was trimmed); a pass stream that does not decode
    exactly at all is returned de-paged, as every writer read it before #938."""
    from . import ecc
    got = exact_tail(pass_raw)
    if got is None:                       # not ours-framed: never expected
        # fall back to what the writers read before #938 -- the de-paged
        # stream, which never raises (#942 review); nothing is trimmed
        from .container import depage
        return depage(pass_raw), {"host_tail_bytes": None, "stale_bytes_dropped": 0,
                                  "kept_host_tail": False,
                                  "why": "pass stream did not decode exactly (de-paged whole)"}
    ex, end, pass_tail = got
    if tail is None:
        return ex, {"host_tail_bytes": None, "stale_bytes_dropped": 0, "kept_host_tail": False,
                    "why": "host tail not exactly decodable (Autodesk-born final block)"}
    if not pass_tail.startswith(tail):
        return ex, {"host_tail_bytes": len(tail), "stale_bytes_dropped": 0, "kept_host_tail": False,
                    "why": "the pass's tail does not start with the host's tail"}
    return ex[:end + len(tail)], {"host_tail_bytes": len(tail),
                                  "stale_bytes_dropped": len(pass_tail) - len(tail),
                                  "kept_host_tail": True}


def check_tail(path: str, expected: Optional[bytes] = None,
               partition: Optional[str] = None) -> Dict[str, Any]:
    """Read ``path``'s partition back and judge its tail: it must start with
    the release's end record; with ``expected`` (the host's exact tail) it
    must EQUAL it.  ``ok`` False names a defect; ``ok`` None = not judgeable
    (the final block does not decode exactly).  ``stray_bytes`` = bytes after
    the 10-byte end record (0 in a Revit-born file)."""
    from .container import open_rvt
    from .famgen import famdoc_adoc as FDA
    end_record = FDA.FAMILY_END_RECORD           # the release-bound token (global_framing.bound)
    with open_rvt(path) as f:
        pn = partition or f.partition_streams()[0]
        got = exact_tail(f.raw(pn))
    rep: Dict[str, Any] = {"partition": pn}
    if got is None:
        rep.update(ok=None, why="final block not exactly decodable")
        return rep
    _ex, end, tail = got
    starts = tail.startswith(end_record)
    rep.update(end_offset=end, tail_bytes=len(tail), starts_on_end_record=starts,
               stray_bytes=(len(tail) - len(end_record)) if starts else None)
    ok = starts
    if expected is not None:
        rep["expected_tail_bytes"] = len(expected)
        rep["equals_host_tail"] = (tail == expected)
        ok = ok and tail == expected
    rep["ok"] = bool(ok)
    return rep
