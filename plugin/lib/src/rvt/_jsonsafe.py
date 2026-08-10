"""rvt._jsonsafe -- every JSON the front door writes is strictly parseable.

Python's ``json`` echoes a non-finite float as a bare ``Infinity`` /
``-Infinity`` / ``NaN`` token, which strict parsers (browsers' ``JSON.parse``,
jq, Go) reject; ``default=`` is never consulted for floats and
``allow_nan=False`` alone would *raise* mid-delivery (hard rule 1: never).
So every front-door writer -- ``rvt.ifc.intent.write_intent``,
``rvt.frontdoor.manifest.write_manifest``, the router's report / manifest
writers, ``rvt.frontdoor.standalone``'s report writer -- goes through
:func:`dump`: one :func:`json_safe` walk turns a non-finite float from ANY
source (a computed ratio, a degenerate extent, a timing -- not only the pset
values ``rvt.ifc.intent._finite_or_text`` already catches at read time) into
its text ``'inf'`` / ``'-inf'`` / ``'nan'`` (the same spellings), THEN dumps
with ``allow_nan=False`` so a value the walk missed fails loudly in a test,
never silently as an unparseable file in a user's run (#461, after #442).

The walk is a no-op on finite data: dict order, ints, bools, strings and
finite floats pass through untouched, so a manifest that carried no
non-finite value is byte-for-byte what plain ``json.dump`` wrote.  Stdlib
only and a LEAF (like ``rvt._logsink``): ``rvt.ifc.intent`` and three
``rvt.frontdoor`` modules import it, and it must never pull either package.
"""
from __future__ import annotations

import json
import math
from typing import Any


def json_safe(obj: Any) -> Any:
    """``obj`` with every non-finite float replaced by its text ('inf' /
    '-inf' / 'nan'); dicts, lists and tuples walked into copies; everything
    else returned untouched (``default=`` still handles it at dump time)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else str(obj)
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj


def dump(obj: Any, fh, *, default: Any = str, **kw: Any) -> None:
    """``json.dump(json_safe(obj), fh, allow_nan=False, default=str, **kw)``
    -- the one call every front-door JSON writer makes."""
    json.dump(json_safe(obj), fh, allow_nan=False, default=default, **kw)
