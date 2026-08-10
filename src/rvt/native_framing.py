"""rvt.native_framing -- "is this OPEN document natively framed, or must its
own release be entered before its partitions can be walked?"

Every read-side CLI that walks ``Partitions/<N>`` of a user's file
(``tools/rvt_selfcheck.py`` #518, ``tools/rvt_inspect.py`` #533, and the
next one) needs the same two moves, and each used to carry them word for
word (#567):

* :func:`natively_framed` -- ask the engine's own header parser
  (``partitions.parse_stream_header`` on each partition's logical bytes of
  the ALREADY OPEN container) whether every partition parses with the
  container class bound in ``rvt.partitions`` right now.  True for a
  native-release file: nothing to enter, nothing more to import.  No
  ``detect_release`` re-open, no schema parse.
* :func:`enter_files_release` -- otherwise import the wanted ladder LAZILY
  and enter it once on the caller's ``ExitStack``: the read-side instrument
  ladder ``global_framing.enter_own_release`` (default; reads every release
  the engine can read) or, with ``host=True``, the authoring context
  ``frontdoor.release_ctx.enter_host_release``.  Both return a note and never
  raise for the file they are handed (#535); so does this.

Why a module of its own and not a corner of ``global_framing``: the native
path must import nothing it did not import before (S-2026-08-09-g; measured
in docs/inbox/edit-text-own-release.md 518.1: an eager ladder import cost a
2026 file +40 ms from a bare unzip).  This module imports only
``rvt.partitions``, which anyone about to walk a partition already holds, so
the one module a native run gains is this file; either ladder is imported
only when the predicate says the file is foreign or damaged.
"""
from __future__ import annotations

from contextlib import ExitStack
from typing import Any, Optional

from . import partitions as P

__all__ = ["natively_framed", "enter_files_release"]


def natively_framed(doc: Any) -> bool:
    """True when every ``Partitions/<N>`` header of the open document ``doc``
    already parses with the container class bound in ``rvt.partitions`` right
    now -- a native-release file (or the release already in force): nothing to
    enter, nothing more to import.  Anything else -- a foreign release, a
    damaged header -- is False and asks the version model."""
    try:
        for name in doc.partition_streams():
            P.parse_stream_header(doc.logical(name))     # raises on any other container class
    except Exception:  # noqa: BLE001 -- damage is an answer here, not an error
        return False
    return True


def enter_files_release(stack: ExitStack, doc: Any, path: str, *,
                        host: bool = False) -> Optional[str]:
    """Put ``path``'s OWN release in force on ``stack`` unless the open
    document ``doc`` is already natively framed (then: enter nothing, import
    nothing).  ``host=False`` enters the read-side instrument ladder
    (``global_framing.enter_own_release``); ``host=True`` the authoring
    context (``release_ctx.enter_host_release``).  Returns None when nothing
    had to be said, else the ladder's one sentence naming the rung the file
    is judged on instead -- callers report it; this never raises."""
    if natively_framed(doc):
        return None
    if host:                                   # foreign files only: keep the native path light
        from .frontdoor.release_ctx import enter_host_release
        return enter_host_release(stack, path)
    from .global_framing import enter_own_release
    return enter_own_release(stack, path)
