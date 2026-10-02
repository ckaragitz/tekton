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
    # the same, as a LIST (#714): a pset shared by several products names no
    # single part, and ``owner``'s ", "-joined string cannot say so when a
    # product's own name holds a comma
    owners: Dict[int, List[str]] = {}
    # and by IFC entity id (#967 review): two products with one name, or an
    # unnamed one, are still distinct owners
    owner_ids: Dict[int, List[int]] = {}
    try:
        for rel in f.by_type("IfcRelDefinesByProperties"):
            pdef = getattr(rel, "RelatingPropertyDefinition", None)
            if pdef is None:
                continue
            names, ids = [], []
            for o in (getattr(rel, "RelatedObjects", None) or ()):
                names.append(str(getattr(o, "Name", "") or ""))
                ids.append(_eid(o))
            # a pset linked by SEVERAL relations (the schema forbids it, an
            # exporter may not) keeps every owner, never the last (#967 review)
            # (each product once: the same product linked twice is ONE owner,
            # #972 review)
            k = _eid(pdef)
            for nm, oid in zip(names, ids):
                if oid not in owner_ids.setdefault(k, []):
                    owner_ids[k].append(oid)
                    owners.setdefault(k, []).append(nm)
            owners.setdefault(k, [])
            owner[k] = ", ".join(n for n in owners[k] if n)
    except Exception:                                             # noqa: BLE001
        pass

    seen_names: Dict[str, Tuple[str, Any]] = {}
    # owners of a label's UNREADABLE statements not yet merged into a carried
    # source (#975): an unreadable value is not a statement, but the product it
    # is attached to still holds the label -- counted once a readable value of
    # an attached source exists, whichever order the file gives them in
    pending: Dict[str, List[Tuple[str, int]]] = {}
    # ``skipped`` rows of unattached repeats, per label (#975): re-worded when an
    # occurrence value later replaces the unattached one, so no row is left
    # naming a value that is no longer the carried one
    # (each with its raw and typed value, so the removal test is the same
    # ``_same_statement`` every other comparison here uses, #979)
    unattached_rows: Dict[str, List[Tuple[Dict[str, Any], Any,
                                          Tuple[str, Any]]]] = {}
    try:
        psets = list(f.by_type("IfcPropertySet"))
    except Exception:                                             # noqa: BLE001
        psets = []

    for ps in psets:
        pset_name = str(getattr(ps, "Name", "") or "Pset")
        on = owner.get(_eid(ps), "")
        ons = list(owners.get(_eid(ps), []))
        on_ids = list(owner_ids.get(_eid(ps), []))
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
            typed = _typed(ifc_type, value, length_to_ft)
            if typed is None:
                # one row per unreadable occurrence, whichever comes first in
                # the file (#979): its product may still be named as an owner
                # (#975), so the dropped value must be explained either way
                out["skipped"].append({
                    "name": label, "pset": pset_name, "on": on,
                    "why": f"unreadable value {value!r} ({ifc_type}) dropped; "
                           "it is not a statement"})
                # its owners still hold the label (#967's invariant, #975):
                # merged now when an attached source is carried, else later
                src = out["sources"].get(label)
                if src is not None and src["product_ids"]:
                    _merge_owners(src, ons, on_ids)
                else:
                    held = pending.setdefault(label, [])
                    for nm, oid in zip(ons, on_ids):
                        if oid not in [o for _n, o in held]:
                            held.append((nm, oid))
                continue
            src = out["sources"].get(label)
            if label in seen_names and src is not None:
                prev_src, prev_val = seen_names[label]
                same = _same_statement(src, typed, out["params"].get(label), value)
                if not src["product_ids"] and on_ids:
                    # an occurrence value wins over an UNATTACHED one (no
                    # relation links its pset to a product -- e.g. a type-level
                    # set; IfcRelDefinesByType is not resolved, so the note does
                    # not claim which product's type it was, #973 / #974 review):
                    # the occurrence's value and owners replace it
                    wins = f"the occurrence value {value!r} ({on or pset_name}) wins"
                    if not same:
                        out["skipped"].append({
                            "name": label, "pset": src["pset"], "on": "",
                            "why": f"unattached value {prev_val!r} not carried; {wins}"})
                    # earlier unattached repeats are re-worded against the value
                    # now carried (#975); one equal to it is no longer a skip
                    for r, rv, rt in unattached_rows.pop(label, []):
                        if _same_statement({"raw_value": rv}, typed, rt, value):
                            out["skipped"].remove(r)
                        else:
                            r["why"] = f"unattached value {rv!r} not carried; {wins}"
                    out["params"][label] = typed
                    seen_names[label] = (f"{on or pset_name}", value)
                    out["sources"][label] = _source(pset_name, on, ons, on_ids,
                                                    ifc_type, value)
                    _merge_owners(out["sources"][label], *_unzip(pending.pop(label, [])))
                    continue
                if not on_ids:
                    # an unattached repeat never contradicts an occurrence value
                    # (#973); between two unattached values the first stays
                    # carried -- worded without a lasting claim, as a later
                    # occurrence value may still replace it (#975)
                    if not same:
                        if src["product_ids"]:
                            why = (f"unattached value {value!r} not carried; the "
                                   f"occurrence value {prev_val!r} ({prev_src}) wins")
                        else:
                            why = (f"unattached value {value!r} not carried; it "
                                   f"differs from the first unattached value "
                                   f"{prev_val!r} ({prev_src})")
                        row = {"name": label, "pset": pset_name, "on": "", "why": why}
                        out["skipped"].append(row)
                        if not src["product_ids"]:
                            unattached_rows.setdefault(label, []).append(
                                (row, value, typed))
                    elif not src["product_ids"]:
                        _upgrade_kind(out, src, label, typed, ifc_type, value)
                    continue
                # every product the label is attached to is recorded, equal
                # value or not, so pset_drive.plan never drives the first one
                # alone (#967 review: a per-occurrence pset is normal input)
                _merge_owners(src, ons, on_ids)
                if same:
                    _upgrade_kind(out, src, label, typed, ifc_type, value)
                else:
                    # the drive plan must see the conflict, not only `skipped`;
                    # "same" is the drive's own tolerance (#972 review, #973)
                    src.setdefault("conflicting_values", []).append(value)
                    out["skipped"].append({
                        "name": label, "pset": pset_name, "on": on,
                        "why": f"already carried from {prev_src} with a "
                               f"different value ({prev_val!r} vs {value!r}); "
                               f"the first is kept"})
                continue
            if label in seen_names:
                continue
            out["params"][label] = typed
            seen_names[label] = (f"{on or pset_name}", value)
            out["sources"][label] = _source(pset_name, on, ons, on_ids, ifc_type, value)
            if on_ids:
                _merge_owners(out["sources"][label], *_unzip(pending.pop(label, [])))
    return out


def _typed(ifc_type: str, value: Any, length_to_ft: float) -> Optional[Tuple[str, Any]]:
    """The carried ``(kind, value)`` of one pset value; None when unreadable."""
    if ifc_type in _LENGTH_TYPES:
        try:
            return ("length", float(value) * length_to_ft)
        except (TypeError, ValueError):
            return None
    if ifc_type in _NUMBER_TYPES:
        try:
            return ("number", float(value))
        except (TypeError, ValueError):
            return None
    if isinstance(value, bool):
        return ("text", "Yes" if value else "No")
    return ("text", str(value))


def _unzip(pairs: List[Tuple[str, int]]) -> Tuple[List[str], List[int]]:
    return [n for n, _o in pairs], [o for _n, o in pairs]


def _merge_owners(src: Dict[str, Any], ons: List[str], on_ids: List[int]) -> None:
    """Record every product of ``on_ids`` on ``src``, each once by entity id."""
    for nm, oid in zip(ons, on_ids):
        if oid not in src["product_ids"]:
            src["product_ids"].append(oid)
            src["products"].append(nm)


def _upgrade_kind(out: Dict[str, Any], src: Dict[str, Any], label: str,
                  typed: Tuple[str, Any], ifc_type: str, value: Any) -> None:
    """A plain number and a length of ONE value are one statement (#974 review);
    the carried kind is the LENGTH whichever came first in the file (#975), so
    file order never decides whether the label can drive a span.  A TEXT value
    that reads as the same number (``IFCLABEL('1574.8')``) ranks below both
    (#979): it yields to the number or the length, never the reverse."""
    kept = out["params"].get(label)
    if kept is None:
        return
    rank = _KIND_RANK.get(typed[0], 0)
    if rank <= _KIND_RANK.get(kept[0], 0):
        return
    if kept[0] == "text":
        # only when the text IS that number, raw against raw -- never feet
        # against file units, never a label that merely compares equal as text
        try:
            as_num = float(src.get("raw_value"))
        except (TypeError, ValueError):
            return
        if not _same_value(as_num, value):
            return
    out["params"][label] = typed
    src["ifc_type"] = ifc_type
    src["raw_value"] = value


#: which carried kind a repeat of ONE value upgrades to (#975, #979)
_KIND_RANK = {"text": 0, "number": 1, "length": 2}


def _source(pset_name: str, on: str, ons: List[str], on_ids: List[int],
            ifc_type: str, value: Any) -> Dict[str, Any]:
    return {"pset": pset_name, "product": on, "products": list(ons),
            "product_ids": list(dict.fromkeys(on_ids)),
            "ifc_type": ifc_type, "raw_value": value, "tier": "given"}


#: two carried LENGTHS closer than this (feet) are one statement -- the drive's
#: own span tolerance (``pset_drive.SPAN_TOL``), so "same" means the same thing
#: to the conflict test and to the span match (#973)
SAME_LENGTH_FT = 1e-6


def _same_statement(src: Dict[str, Any], typed: Tuple[str, Any],
                    kept: Optional[Tuple[str, Any]], raw: Any) -> bool:
    """Is the repeat (``typed``, raw ``raw``) the same statement as the carried
    one?  Two LENGTHS compare converted, to :data:`SAME_LENGTH_FT`; any other
    pairing (a length against a plain number, text, ...) compares the RAW values
    with :func:`_same_value` -- never feet against file units (#974 review)."""
    if kept is not None and kept[0] == "length" and typed[0] == "length":
        return abs(float(kept[1]) - float(typed[1])) <= SAME_LENGTH_FT
    return _same_value(src.get("raw_value"), raw)


def _same_value(a: Any, b: Any) -> bool:
    """Two raw pset values are the same statement: equal, or equal numbers to
    1e-9 relative (float noise, never a tolerance that would hide a real
    difference -- pset_drive's SPAN_TOL is 1e-6 ft on converted lengths)."""
    if a == b:
        return True
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(fa - fb) <= 1e-9 * max(1.0, abs(fa), abs(fb))


def _length_to_ft(f: Any, out: Dict[str, Any]) -> float:
    """The file's length unit expressed in FEET, read from its own
    IfcUnitAssignment.  Falls back to metres and says so.

    Delegates the unit walk to :func:`steplite.calculate_unit_scale`
    (metres per project length unit -- the same conversion-factor chain
    ifcopenshell walks), rather than re-implementing a weaker name-sniffing
    version here (#769 review).  The honesty note is kept: the scale is
    trusted only when the file actually DECLARES a length unit."""
    try:
        from . import steplite
        declares = any(
            str(getattr(u, "UnitType", "") or "") == "LENGTHUNIT"
            for kind in ("IfcSIUnit", "IfcConversionBasedUnit")
            for u in (f.by_type(kind) or ()))
        if declares:
            metres = float(steplite.calculate_unit_scale(f))
            if metres > 0:
                return metres * _FT_PER_M
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
