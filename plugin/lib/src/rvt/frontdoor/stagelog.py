"""rvt.frontdoor.stagelog -- the front door's name for the shared quiet-stage log.

The three front-door routes (``build.log`` #312, ``route.log`` #188/#330,
``edit.log`` #373) import :func:`stage_stdout` from here; its body lives in
the stdlib-only leaf :mod:`rvt._logsink` (issue #424) so ``tools/rvt_job.py``
and any other entry point can share the one open-at-call-time /
line-buffered / degrade-with-a-note implementation without paying for the
``rvt.frontdoor`` package import.  The contract is documented there.
"""
from __future__ import annotations

from .._logsink import stage_stdout

__all__ = ["stage_stdout"]
