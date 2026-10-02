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

#941 extends the law from the loaders to EVERY project-rewriting writer
(``commit.commit_new_elements`` and its callers -- walls, equipment, mep,
famload pass 1 --, ``manipulate.commit_plans`` -- identity, levels, edits,
famload pass 3 --, ``mep.conduit.commit_created``,
``mep.electrical_data.commit_electrical``, ``reduce.reduce_elements``): each
read its source partition DE-PAGED (``doc.logical``) and kept the walker's
``end_record`` whole, so each added one generation of the source's
final-block parity (+580 / +578 / +526 B per stage on the 6-panel project).
They now read it with :func:`writer_logical` (the exact content, so the
walker's ``end_record`` IS the host's exact tail) and their verifiers judge
the written tail with :func:`tail_verdict`.

Release-agnostic: the walker reads the release's own framing ordinals, so
callers run inside the file's release context (the loaders already do;
instruments use ``global_framing.enter_own_release``).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

__all__ = ["exact_tail", "host_tail", "keep_host_tail", "check_tail",
           "writer_logical", "tail_verdict", "tail_defect"]


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


def writer_logical(doc: Any, pname: str) -> Tuple[bytes, Dict[str, Any]]:
    """The logical partition stream a project-rewriting writer splices into
    (#941): the EXACT content of ``doc``'s ``pname`` (``ecc.unframe_stream``),
    so the partition walker's ``end_record`` is the host's exact tail and a
    writer that keeps ``out[:end_offset + len(end_record)]`` keeps that tail
    byte for byte, adding no generation of stale parity.  When the final block
    does not decode exactly (an Autodesk-born block with heap bytes in its pad
    region) the de-paged stream is returned, as every writer read it before
    #941; the report says which (``exact``).  ``doc``: an open ``RvtDocument``
    (anything with ``raw(name)`` and ``logical(name)``)."""
    from . import ecc
    try:
        return ecc.unframe_stream(doc.raw(pname)), {"exact": True}
    except ValueError:
        return doc.logical(pname), {
            "exact": False,
            "why": "final block not exactly decodable: read de-paged (host tail unknown)"}


def tail_verdict(path: str, host_rvt: Optional[str] = None,
                 partition: Optional[str] = None) -> Dict[str, Any]:
    """:func:`check_tail` of a written file against its HOST's exact tail
    (#941).  With ``host_rvt`` the written tail must equal the host's when the
    host's decodes exactly (``host_tail_known``); otherwise, and without
    ``host_rvt``, only the end-record check runs.  Judged under the written
    file's OWN release framing (``global_framing.enter_own_release``,
    nest-safe), whatever context the caller is in."""
    from contextlib import ExitStack
    from .global_framing import enter_own_release
    try:
        with ExitStack() as stack:
            enter_own_release(stack, path)
            expected = host_tail(host_rvt, partition) if host_rvt else None
            rep = check_tail(path, expected, partition)
    except Exception as e:                     # noqa: BLE001 -- a verifier never raises
        return {"partition": partition, "ok": None,
                "why": f"tail not judgeable: {type(e).__name__}: {e}"}
    if host_rvt:
        rep["host_tail_known"] = expected is not None
    return rep


def tail_defect(rep: Optional[Dict[str, Any]]) -> Optional[str]:
    """The one-line defect a :func:`check_tail` report names when its ``ok``
    is False; None when it is ok or not judgeable."""
    if not rep or rep.get("ok") is not False:
        return None
    if not rep.get("starts_on_end_record"):
        return f"partition tail: does not start on the stream end record ({rep.get('partition')})"
    return (f"partition tail: {rep.get('tail_bytes')} B != the host's "
            f"{rep.get('expected_tail_bytes')} B (stale parity carried as content)")
