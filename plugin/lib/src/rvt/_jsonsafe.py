"""rvt._jsonsafe -- every JSON tekton writes is strictly parseable.

Python's ``json`` echoes a non-finite float as a bare ``Infinity`` /
``-Infinity`` / ``NaN`` token, which strict parsers (browsers' ``JSON.parse``,
jq, Go) reject; ``default=`` is never consulted for floats and
``allow_nan=False`` alone would *raise* mid-delivery (hard rule 1: never).
So every JSON sink on the front-door path goes through this module: one
:func:`json_safe` walk turns a non-finite float from ANY source (a computed
ratio, a degenerate extent, a timing -- not only the pset values
``rvt.ifc.intent._finite_or_text`` already catches at read time) into its text
``'inf'`` / ``'-inf'`` / ``'nan'`` (the same spellings), THEN dumps with
``allow_nan=False`` so a value the walk missed fails loudly in a test, never
silently as an unparseable file in a user's run (#461, after #442).

Three entry points, one walk:

* :func:`write` -- the path-owning file writer (parent dir made, ``utf-8``,
  the walk, ``allow_nan=False``): ``scene-brief.json``, the edit ``ops.json``
  echo, ``tools/ifc_intent``'s stage records, ``rvt.ifc.famfrom_ifc``'s
  reports, ``tools/rvt_job``'s manifests / validation / spec JSON (#475);
* :func:`dump` -- for a caller that already holds the file handle
  (``write_intent``, ``manifest.write_manifest``, the router's and
  ``standalone``'s writers, #461);
* :func:`dumps` -- the ``--json`` stdout documents a skill session parses
  (``tools/rvt_job``, ``tools/route``).

A ``default=`` hook's result is walked too: ``tools/rvt_job._jsonable``
expands a dataclass / ``to_json()`` object into a dict at dump time, and a
non-finite float inside it must land as text like any other, not trip
``allow_nan=False`` mid-delivery.

The walk is a no-op on finite data: dict order, ints, bools, strings and
finite floats pass through untouched, so a document that carried no
non-finite value is byte-for-byte what plain ``json.dump`` wrote.  Stdlib
only and a LEAF (like ``rvt._logsink``): ``rvt.ifc`` and ``rvt.frontdoor``
modules and repo tools import it, and it must never pull either package.
"""
from __future__ import annotations

import json
import math
import os
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


def _walked(default: Any) -> Any:
    """``default`` whose result goes through the walk as well."""
    if default is None:
        return None
    return lambda o: json_safe(default(o))


def dump(obj: Any, fh, *, default: Any = str, **kw: Any) -> None:
    """``json.dump(json_safe(obj), fh, allow_nan=False, default=str, **kw)``
    -- for a writer that already holds the file handle."""
    json.dump(json_safe(obj), fh, allow_nan=False, default=_walked(default), **kw)


def dumps(obj: Any, *, default: Any = str, **kw: Any) -> str:
    """The string twin of :func:`dump` -- what a ``--json`` stdout printer
    prints."""
    return json.dumps(json_safe(obj), allow_nan=False, default=_walked(default), **kw)


def write(path: str, obj: Any, *, indent: Any = 1, default: Any = str, **kw: Any) -> str:
    """Write ``obj`` as strict JSON to ``path`` (parent directory made,
    ``utf-8``, the walk, ``allow_nan=False``) and return ``path`` -- the ONE
    stanza every job-dir JSON file writer would otherwise repeat.  An
    ``OSError`` is the caller's to catch where losing the file is tolerable."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        dump(obj, fh, indent=indent, default=default, **kw)
    return path
