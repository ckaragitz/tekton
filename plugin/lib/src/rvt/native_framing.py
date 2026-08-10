"""rvt.native_framing -- "is this OPEN document natively framed, or must its
own release be entered before its partitions can be walked?"

The two moves every read-side CLI that walks ``Partitions/<N>`` of a user's
file needs (``tools/rvt_selfcheck.py``, ``tools/rvt_inspect.py``; #567):

* :func:`natively_framed` -- the engine's own header parser on each
  partition of the ALREADY OPEN container: True when every header parses with
  the container class bound in ``rvt.partitions`` right now (a native file:
  nothing to enter, nothing more to import); no re-open, no schema parse.
* :func:`enter_files_release` -- otherwise import the wanted ladder LAZILY
  and enter it once on the caller's ``ExitStack``; a note, never a raise.

A module of its own, importing only ``rvt.partitions`` (which anyone about
to walk a partition already holds), so a native run imports neither ladder
and nothing under ``rvt.frontdoor`` (S-2026-08-09-g; the measurements are in
docs/inbox/edit-text-own-release.md 518.1 / 567.1).
"""
from __future__ import annotations

from contextlib import ExitStack
from typing import Optional

from . import partitions as P

__all__ = ["natively_framed", "enter_files_release"]


def natively_framed(doc) -> bool:
    """True when every ``Partitions/<N>`` header of the open document ``doc``
    parses with the container class bound in ``rvt.partitions`` right now;
    a foreign release or a damaged header is False (never a raise)."""
    try:
        for name in doc.partition_streams():
            P.parse_stream_header(doc.logical(name))     # raises on any other container class
    except Exception:  # noqa: BLE001 -- damage is an answer here, not an error
        return False
    return True


def enter_files_release(stack: ExitStack, doc, path: str, *, host: bool = False) -> Optional[str]:
    """Put ``path``'s OWN release in force on ``stack`` unless the open
    document ``doc`` is already natively framed (then: enter nothing, import
    nothing).  Default: the read-side instrument ladder
    ``global_framing.enter_own_release`` (reads every release the engine can
    read); ``host=True``: the authoring context
    ``release_ctx.enter_host_release`` (enters nothing it cannot author into).
    Returns None, or that ladder's one sentence naming the rung the file is
    judged on instead -- callers report it; this never raises."""
    if natively_framed(doc):
        return None
    if host:                                   # foreign files only: keep the native path light
        from .frontdoor.release_ctx import enter_host_release
        return enter_host_release(stack, path)
    from .global_framing import enter_own_release
    return enter_own_release(stack, path)
