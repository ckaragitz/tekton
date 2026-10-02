"""The cyclic garbage collector's pacing for ONE build job (#932).

A build allocates millions of small dicts and lists (object trees it
constructs, encodes, decodes and checks) and keeps large decoded trees and
caches alive for the whole job.  Under the interpreter's default pacing
(a generation-0 pass every 700 net container allocations) that churn
promotes the long-lived trees into the oldest generation and triggers
repeated FULL collections that re-traverse all of them: measured on the
6-panel prompt job, 12 full passes cost ~0.9 s of a ~6.6 s job -- the
largest single line of its profile -- while finding almost no garbage.

:func:`build_gc` paces the collector for the duration of one job: a young
pass every 50,000 net allocations and the older generations correspondingly
rarer.  Collection still runs (cyclic garbage is still reclaimed, memory
stays bounded); only how often it re-walks long-lived objects changes.  The
collector never decides what a build writes, so every output byte is the
same either way -- it only decides when unreachable cycles are freed.

The previous thresholds come back when the outermost scope exits; nested
scopes (a route calling the front door) leave the outer pacing alone.
"""
from __future__ import annotations

import contextlib
import gc
from typing import Iterator, Tuple

#: (gen0, gen1, gen2) thresholds during a build job
BUILD_THRESHOLDS: Tuple[int, int, int] = (50_000, 20, 100)

_DEPTH = [0]


@contextlib.contextmanager
def build_gc() -> Iterator[None]:
    """Pace the cyclic GC for one build job (see the module docstring)."""
    if _DEPTH[0]:
        _DEPTH[0] += 1
        try:
            yield
        finally:
            _DEPTH[0] -= 1
        return
    before = gc.get_threshold()
    _DEPTH[0] = 1
    gc.set_threshold(*BUILD_THRESHOLDS)
    try:
        yield
    finally:
        _DEPTH[0] = 0
        gc.set_threshold(*before)
