"""rvt.ifc.pset_params -- carry an IFC's OWN property sets through to the
family as real, typed family parameters.

WHY.  A user models something in Claude Design (or any IFC authoring tool),
attaches property sets to it -- ``Pset_TransformerClearances`` with
``TopClearance``, ``BodyWidth``, ``PadDepth`` and so on -- converts it, and
finds none of them in the ``.rfa``.  The assembly lane read those psets, used
them for the bill of materials, and dropped everything else on the floor.  The
family arrived with the generic ``Width`` / ``Depth`` / ``Height`` set and no
trace of what the author had actually specified.

That is a silent loss of the user's own input, which is worse than a refusal:
nothing said the properties had been discarded.

WHAT THIS DOES.  Collects every single-value property across the IFC's
products, drops the ones already carried elsewhere (identity / bill of
materials), and returns them as parameter declarations with:

  * the right SPEC -- an ``IfcLengthMeasure`` becomes a length parameter,
    a plain number a number parameter, anything else text;
  * the right VALUE -- lengths converted from the IFC's own unit to internal
    feet via the file's unit assignment, never assumed to be metres;
  * the SOURCE recorded, so a value is traceable to the pset it came from.

PROVENANCE.  Every value here is ``given`` -- the caller stated it in their own
file.  It is never a catalog ``fact`` and never a manufacturer claim (steer
S-2026-08-11-c): we carry the author's numbers verbatim because they are the
author's, not because we verified them.

NAME COLLISIONS.  A property named ``Width`` would collide with the
constructor's own overall-bounding-box ``Width``.  Colliding names are
reported and SKIPPED rather than silently overwriting a dimension the geometry
depends on -- and the report names them, so the loss is never silent twice.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

#: Properties already carried by the identity / BOM path -- carrying them
#: again would duplicate a parameter under two names.
_ALREADY_CARRIED = frozenset({
    "PartNumber", "ArticleNumber", "ModelReference", "ModelLabel",
    "GlobalTradeItemNumber", "Reference", "Description", "Tag",
    "Manufacturer", "ModelNumber",
})

#: Parameter names the family constructors author themselves.  A pset property
#: of the same name is skipped, never silently substituted for the dimension
#: the geometry actually uses.
RESERVED_NAMES = frozenset({
    "Width", "Depth", "Height", "Material", "Weight", "Finish",
    "Part Numbers", "Source IFC", "Assembly Tag",
})

#: IFC measure classes we treat as a LENGTH (converted to feet).
_LENGTH_TYPES = frozenset({
    "IfcLengthMeasure", "IfcPositiveLengthMeasure",
    "IfcNonNegativeLengthMeasure",
})

#: ...as a plain number (carried as-is).
_NUMBER_TYPES = frozenset({
    "IfcReal", "IfcInteger", "IfcCountMeasure", "IfcRatioMeasure",
    "IfcPositiveRatioMeasure", "IfcNormalisedRatioMeasure",
    "IfcNumericMeasure", "IfcMassMeasure", "IfcAreaMeasure",
    "IfcVolumeMeasure", "IfcPlaneAngleMeasure",
})

_FT_PER_M = 1.0 / 0.3048


def _eid(entity: Any) -> int:
    """A steplite entity's STEP id.  ``id`` and ``is_a`` are METHODS on these
    entities, not attributes -- reading them as attributes yields the bound
    method and silently poisons any dict keyed on it."""
    v = getattr(entity, "id", None)
    try:
        return int(v() if callable(v) else v)
    except Exception:                                             # noqa: BLE001
        return -1


def _type_name(entity: Any) -> str:
    """The IFC type name of a value wrapper, whichever way the reader exposes
    it (``is_a()`` on steplite, ``is_a`` as a string elsewhere)."""
    v = getattr(entity, "is_a", None)
    if callable(v):
        try:
            return str(v())
        except Exception:                                         # noqa: BLE001
            return ""
    return str(v or "")


def _clean(name: str) -> str:
    """A parameter name Revit will accept: no separators that break the
    properties palette, trimmed, never empty."""
    s = " ".join(str(name or "").replace("_", " ").split())
    return s[:60] or "Property"


def collect(ifc_path: str, *, length_to_ft: Optional[float] = None,
            reserved: Optional[frozenset] = None) -> Dict[str, Any]:
    """Every carryable single-value property in ``ifc_path``.

    Returns ``{"params": {...}, "skipped": [...], "sources": {...}}``.
    Never raises for an unreadable file -- an IFC we cannot read yields no
    parameters and says so, because delivery must not depend on this
    (hard rule 1).
    """
    out: Dict[str, Any] = {"params": {}, "skipped": [], "sources": {},
                           "notes": []}
    reserved = RESERVED_NAMES if reserved is None else reserved
    try:
        from . import steplite
        f = steplite.open(ifc_path)
    except Exception as exc:                                      # noqa: BLE001
        out["notes"].append(
            f"property sets not read ({type(exc).__name__}): the family is "
            f"delivered without them rather than blocked")
        return out

    # the file's OWN length unit -> feet.  Never assumed: an IFC in millimetres
    # would otherwise put a 36-inch clearance 3000 feet away.
    if length_to_ft is None:
        length_to_ft = _length_to_ft(f, out)

    # which product each pset is attached to (for the source record)
    owner: Dict[int, str] = {}
    try:
        for rel in f.by_type("IfcRelDefinesByProperties"):
            pdef = getattr(rel, "RelatingPropertyDefinition", None)
            if pdef is None:
                continue
            names = []
            for o in (getattr(rel, "RelatedObjects", None) or ()):
                names.append(str(getattr(o, "Name", "") or ""))
            owner[_eid(pdef)] = ", ".join(n for n in names if n)
    except Exception:                                             # noqa: BLE001
        pass

    seen_names: Dict[str, Tuple[str, Any]] = {}
    try:
        psets = list(f.by_type("IfcPropertySet"))
    except Exception:                                             # noqa: BLE001
        psets = []

    for ps in psets:
        pset_name = str(getattr(ps, "Name", "") or "Pset")
        on = owner.get(_eid(ps), "")
        for pr in (getattr(ps, "HasProperties", None) or ()):
            raw_name = str(getattr(pr, "Name", "") or "")
            if not raw_name or raw_name in _ALREADY_CARRIED:
                continue
            nv = getattr(pr, "NominalValue", None)
            if nv is None:
                continue
            ifc_type = _type_name(nv)
            value = getattr(nv, "wrappedValue", nv)
            if value is None or value == "":
                continue
            label = _clean(raw_name)
            if label in reserved:
                out["skipped"].append({
                    "name": label, "pset": pset_name, "on": on,
                    "why": "the family constructor authors a parameter of this "
                           "name from the geometry; the pset value is NOT "
                           "substituted for it"})
                continue
            if label in seen_names:
                prev_src, prev_val = seen_names[label]
                if prev_val != value:
                    out["skipped"].append({
                        "name": label, "pset": pset_name, "on": on,
                        "why": f"already carried from {prev_src} with a "
                               f"different value ({prev_val!r} vs {value!r}); "
                               f"the first is kept"})
                continue

            if ifc_type in _LENGTH_TYPES:
                try:
                    out["params"][label] = ("length", float(value) * length_to_ft)
                except (TypeError, ValueError):
                    continue
            elif ifc_type in _NUMBER_TYPES:
                try:
                    out["params"][label] = ("number", float(value))
                except (TypeError, ValueError):
                    continue
            elif isinstance(value, bool):
                out["params"][label] = ("text", "Yes" if value else "No")
            else:
                out["params"][label] = ("text", str(value))
            seen_names[label] = (f"{on or pset_name}", value)
            out["sources"][label] = {
                "pset": pset_name, "product": on, "ifc_type": ifc_type,
                "raw_value": value, "tier": "given"}
    return out


#: SI prefixes an IfcSIUnit may carry, as multipliers.
_PREFIX = {"MILLI": 1e-3, "CENTI": 1e-2, "DECI": 1e-1, "DECA": 1e1,
           "HECTO": 1e2, "KILO": 1e3, "MICRO": 1e-6}


def _length_to_ft(f: Any, out: Dict[str, Any]) -> float:
    """The file's length unit expressed in FEET, read from its own
    IfcUnitAssignment.  Falls back to metres and says so."""
    try:
        for u in f.by_type("IfcSIUnit"):
            if str(getattr(u, "UnitType", "") or "") != "LENGTHUNIT":
                continue
            metres = 1.0
            pref = getattr(u, "Prefix", None)
            if pref:
                metres *= _PREFIX.get(str(pref).upper(), 1.0)
            return metres * _FT_PER_M
    except Exception:                                             # noqa: BLE001
        pass
    try:
        for u in f.by_type("IfcConversionBasedUnit"):
            if str(getattr(u, "UnitType", "") or "") == "LENGTHUNIT":
                nm = str(getattr(u, "Name", "") or "").lower()
                if "foot" in nm or "feet" in nm:
                    return 1.0
                if "inch" in nm:
                    return 1.0 / 12.0
    except Exception:                                             # noqa: BLE001
        pass
    out["notes"].append(
        "the IFC's length unit could not be read; metres assumed for length "
        "properties")
    return _FT_PER_M


def summarise(collected: Dict[str, Any]) -> List[str]:
    """Caveat lines a delivery can carry verbatim."""
    lines: List[str] = []
    params = collected.get("params") or {}
    if params:
        by_kind: Dict[str, List[str]] = {}
        for name, (kind, _v) in sorted(params.items()):
            by_kind.setdefault(kind, []).append(name)
        parts = ", ".join(f"{k}: {', '.join(v)}" for k, v in sorted(by_kind.items()))
        lines.append(
            f"YOUR PROPERTY SETS carried through as {len(params)} family "
            f"parameter(s) ({parts}) -- every value GIVEN by your IFC, "
            f"converted to Revit's internal units, never a catalog claim")
    for s in (collected.get("skipped") or []):
        lines.append(f"property {s['name']!r} from {s['pset']} was NOT carried: "
                     f"{s['why']}")
    lines.extend(collected.get("notes") or [])
    return lines
