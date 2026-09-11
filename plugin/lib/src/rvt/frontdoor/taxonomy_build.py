"""rvt.frontdoor.taxonomy_build -- the wire from a RECOGNISED kind to its
CONSTRUCTOR (issue #766).

THE GAP, measured on the day it was filed: ``make_luminaire(kind=
"recessed-troffer", size="2x4")`` is that constructor's DEFAULT
configuration, the taxonomy scans "a 2x4 recessed troffer light fixture"
to ``['troffer', 'luminaire']`` and holds the famspec hint
``{"kind": "luminaire", "fixture": "recessed-troffer"}`` -- and the route
still answered *FAILED (no family plan in this prompt could be built)*,
because nothing ever consulted the hint.  The knowledge and the constructor
existed; the wire did not.

WHAT THIS MODULE IS.  The bridge, kept out of the router so the router only
sequences lanes: :func:`plans` turns a prompt into famspec-constructor plans
via the taxonomy's own hints, and the router builds each through the same
``_famspec_rfa`` path every catalog kind already uses.  Prompt tokens the
grammar can read honestly ride along as constructor parameters:

  * a trade size ``2x2`` / ``2x4`` / ``1x4`` / ``4x4``  -> ``size``
  * a wattage ``38 W`` / ``38-watt``                    -> ``wattage``
  * a kelvin ``3500K`` / ``4000 K``                     -> ``cct``

Everything else stays the constructor's own default -- which is exactly the
nominal-archetype posture of steer #591: deliver the standard product, state
the assumptions, let the prompt override.

WHAT THIS DELIBERATELY DOES NOT DO.  It never invents a mapping: only
mentions whose row both ``builder_available()`` and carries a famspec hint
become plans; everything else stays with the archetype lane and the honest
refusal, in the order the router already sets.  And it never SHRINKS a
mention list into silence -- a recognised-but-unbuildable kind still reaches
the taxonomy's own "NOT buildable here" line downstream.

Territory: frontdoor (new module).  Reads taxonomy + famspec; edits neither.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

#: trade sizes the luminaire lane understands, longest token first.
_SIZE = re.compile(r"\b([124])\s*[xX]\s*([124])\b")

_WATTS = re.compile(r"\b(\d{1,4}(?:\.\d+)?)\s*(?:-\s*)?w(?:atts?)?\b", re.I)

_KELVIN = re.compile(r"\b(\d{3,4})\s*k(?:elvin)?\b", re.I)


# the trade sizes the troffer CATALOG actually holds a member for -- read
# from the factory, never re-listed here.  Before #703 the resolver was
# binary ("2x4" -> the 2BLT4 member, anything else -> 2BLT2, WHICH IS THE
# 2x2), so passing an unsupported size through silently delivered a 2x2
# wearing the caller's size ("4x4 troffer" -> a 2BLT2, measured) -- the
# substitution steer #591 forbids.  The constructor now refuses an unheld
# size by name, and this route keeps DELIVERING by dropping the size and
# saying so.  Deriving the set means adding a member in ONE place makes both
# sides agree; a second hand-kept copy would leave this route dropping a
# size the constructor had just learned to build, with every test green.
# Read lazily and cached, like every other engine import in this module --
# importing the factory to answer a two-element question would put the whole
# famgen import cost on anyone who merely imports this module (S-2026-08-09-g).
@lru_cache(maxsize=1)
def _catalog_sizes() -> frozenset:
    """The troffer trade sizes the catalog holds a member for (factory-owned).

    Cached per process.  ``_catalog_sizes.cache_clear()`` is the supported way
    to re-read it — a test that monkeypatches ``factory._TROFFER_MEMBERS``
    after any earlier call would otherwise keep seeing the old set, silently.
    """
    from ..famgen import factory as _F
    return _F.held_troffer_sizes()


def _params_from_prompt(prompt: str, kind: str) -> Dict[str, Any]:
    """Constructor parameters the prompt states in words the grammar can
    read honestly.  Absent stays absent -- the constructor's own nominal
    defaults are the point, never our guess.  A ``__notes__`` entry carries
    what was HEARD but not passed, so the delivery can say so."""
    out: Dict[str, Any] = {}
    m = _SIZE.search(prompt)
    if m and kind == "luminaire":
        size = f"{m.group(1)}x{m.group(2)}"
        held = _catalog_sizes()
        if size in held:
            out["size"] = size
        else:
            out.setdefault("__notes__", []).append(
                f"the prompt asks for a {size}, which this catalog does not "
                f"hold ({', '.join(sorted(held))}): the default "
                f"member is delivered and this line says so -- NOT a {size}")
    m = _WATTS.search(prompt)
    if m and kind == "luminaire":
        out["wattage"] = float(m.group(1))
    m = _KELVIN.search(prompt)
    if m and kind == "luminaire":
        out["cct"] = float(m.group(1))
    return out


def plans(prompt: str) -> List[Dict[str, Any]]:
    """Famspec-constructor plans for every BUILDABLE kind ``prompt`` names.

    One plan per distinct famspec (a prompt scanning to both ``troffer`` and
    its parent ``luminaire`` builds ONE troffer, not two families), each::

        {"kind": "luminaire", "kw": {...constructor params...},
         "mention": "troffer", "label": "recessed-troffer"}

    Kinds the taxonomy recognises but no lane builds are NOT returned -- the
    router's downstream refusal already relays the taxonomy's own line for
    them (#692), and pretending to plan them would bury it.
    """
    from ..famgen import taxonomy as TX

    out: List[Dict[str, Any]] = []
    seen: set = set()
    try:
        mentions = TX.scan(prompt)
    except Exception:                                             # noqa: BLE001
        return out
    for m in mentions:
        row = TX.get(m.key)
        if row is None:
            continue
        try:
            # builder_available returns (bool, why) -- truth-testing the
            # TUPLE is always True, the exact bug class the #766 battery
            # fixed; unpacked here so the gate actually gates (#768).
            ok, _why = TX.builder_available(row)
            if not ok:
                continue
        except Exception:                                         # noqa: BLE001
            continue
        hint = TX.famspec_hint(row)
        if not hint:
            continue
        try:
            spec = json.loads(hint)
        except (TypeError, ValueError):
            continue
        kind = str(spec.get("kind", "") or "")
        if not kind:
            continue
        key = (kind, tuple(sorted((k, v) for k, v in spec.items()
                                  if k != "kind")))
        if key in seen:
            continue
        seen.add(key)
        spec = dict(spec)
        heard = _params_from_prompt(str(prompt), kind)
        notes = heard.pop("__notes__", [])
        spec.update(heard)
        label = next((v for k, v in spec.items()
                      if k not in ("kind",) and isinstance(v, str)), kind)
        # ONE law for validation and constructor renames: famspec.normalise
        # (luminaire 'fixture' -> the constructor's own 'kind', schema
        # checks).  Re-implementing the rename table here is how the first
        # cut broke: make_luminaire() got an unexpected keyword 'fixture'.
        try:
            from . import famspec as FS
            fkind, kw, ropts = FS.normalise(spec)
        except Exception as exc:                                  # noqa: BLE001
            out.append({"kind": kind, "kw": None, "mention": m.key,
                        "label": label,
                        "invalid": f"{type(exc).__name__}: {exc}"})
            continue
        out.append({"kind": fkind, "kw": kw, "mention": m.key,
                    "label": label, "route_opts": ropts, "notes": notes})
    return out


def describe(plan: Dict[str, Any]) -> str:
    """One caveat-quotable line saying where a plan came from."""
    stated = {k: v for k, v in plan["kw"].items()}
    return (f"'{plan['mention']}' -> {plan['kind']} constructor"
            + (f" ({', '.join(f'{k}={v}' for k, v in sorted(stated.items()))})"
               if stated else " (constructor defaults)"))
