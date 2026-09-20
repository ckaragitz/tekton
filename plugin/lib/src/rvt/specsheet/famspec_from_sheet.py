"""rvt.specsheet.famspec_from_sheet -- a read spec sheet becomes a famspec.

#688 DONE 1 and 5.  :mod:`rvt.specsheet.sheet` turns a PDF into cited values;
this turns those values into the kwargs a family constructor takes, and it is
deliberately the ONLY place that mapping lives, so "what the sheet said" and
"what we built" can be compared row by row.

WHY ``generic_model`` AND NOT A CATALOG KIND.  A catalog kind
(``panelboard``, ``transformer``, …) resolves its dimensions from a record we
hold, and passing sheet-read numbers into one would silently overwrite a
sourced fact with a different sourced fact.  The sheet lane is the opposite
case: we hold no record, the user handed us the document, and the geometry is
theirs.  ``make_generic_model`` is built for exactly that -- geometry supplied
by the caller, every dimension carrying its source -- with one change this
module needed: those dimensions are ``fact`` here, not ``given``, because
they were read off a published document rather than typed by a caller.

THE IDENTITY LANE (#688 DONE 5), and why it is honest here and nowhere else.
Everywhere else in this engine, putting a manufacturer and part number on a
generated family is forbidden: S-2026-08-11-c says the model may not recall a
manufacturer's data, and ``archetypes.manufacturer_claim`` exists to say
loudly that a named item is *not* what was delivered.  On this lane the user
supplied the document that states the name, the model and the dimensions
together.  Wearing the part number is then a report of their document, not a
claim of ours -- so identity parameters are set, and every one of them cites
the page it came from.

WHAT IS REFUSED, by name, without withholding the file (hard rule 1):

* a sheet with **no dimensions** cannot size a body -- the caller is told
  which fields were found instead, and the archetype lane can still deliver;
* a dimension the sheet states in a unit we do not convert;
* an **assumed** unit (``SheetValue.unit_source == "declared"``) is refused
  for geometry specifically.  A rating whose unit we assumed is a rating with
  a caveat; a *dimension* whose unit we assumed is a body of the wrong size,
  and 25x is the distance between millimetres and inches.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from .sheet import ParsedSheet, SheetValue

__all__ = ["SheetPlan", "plan_from_sheet"]

#: sheet key -> the ``make_generic_model`` kwarg it sizes, in feet
_DIMS = {"height_in": "height_ft", "width_in": "width_ft", "depth_in": "depth_ft"}

#: sheet key -> Revit identity parameter. These are the three the format
#: itself defines for a family's identity; anything else stays a plain
#: parameter rather than being promoted into the identity block.
_IDENTITY = {"manufacturer": "Manufacturer", "model": "Model"}

#: sheet key -> a text parameter carried onto the family
_TEXT = {"voltage": "Voltage", "enclosure": "Enclosure Rating",
         "series": "Series", "mounting": "Mounting", "ip_rating": "IP Rating"}

#: sheet key -> a plain numeric parameter carried onto the family. The value
#: is stored as the sheet stated it: these are the document's own numbers and
#: a silent conversion here would put a different number behind its citation.
_NUMERIC = {"amps": "Amps", "sccr_ka": "SCCR",
            "kva": "kVA", "watts": "Watts", "lumens": "Lumens",
            "cct_k": "CCT", "phases": "Phases", "frequency_hz": "Frequency",
            "temperature_c": "Ambient Temperature"}

#: sheet key -> (the CATEGORY-STANDARD parameter it fills, sheet unit ->
#: Revit internal unit).  A key here must NOT also be in ``_NUMERIC``: the
#: standards table (#601) already authors the parameter at its own storage
#: class, and authoring a second one of the same name would win the race and
#: demote a mass to a bare number.  ``standard_values`` takes internal units,
#: so the conversion is exact and named rather than implied.
_STANDARD_VALUES = {"weight_lb": ("Weight", "mass"),
                    # text, so no conversion -- but they are standards-table
                    # rows on this category and authoring them as plain text
                    # parameters put them under group `identity` instead of
                    # `materials`, shadowing the table's own entries
                    "material": ("Material", ""),
                    "finish": ("Finish", "")}


class SheetPlan:
    """What a sheet can and cannot build, with every value's citation."""

    __slots__ = ("kind", "kwargs", "used", "refused", "document", "name")

    def __init__(self, kind: str, kwargs: Dict[str, Any],
                 used: List[Tuple[str, SheetValue]],
                 refused: List[str], document: str, name: str):
        self.kind, self.kwargs = kind, kwargs
        #: (constructor kwarg or parameter caption, the SheetValue behind it)
        self.used = used
        #: one line per thing the sheet stated that could not be used
        self.refused = refused
        self.document, self.name = document, name

    #: every kwarg ``make_generic_model`` needs to size a rectangular body.
    #: It requires ``height_ft`` AND (``vertices`` OR ``width_ft`` +
    #: ``depth_ft``), and this lane never supplies ``vertices`` -- a spec
    #: sheet states a table, not a profile.
    REQUIRED = ("height_ft", "width_ft", "depth_ft")

    @property
    def buildable(self) -> bool:
        """Can ``make_generic_model`` actually build this?

        It asked only about ``height_ft`` once, and the gap cost the file: a
        sheet stating a height and no width took the buildable branch, the
        constructor raised, and the route returned before the archetype
        fallback -- delivering NOTHING, which is hard rule 1 broken by an
        off-by-two predicate. The router now also falls through on any build
        failure, so this is the honest answer rather than the only defence.
        """
        return all(self.kwargs.get(k) for k in self.REQUIRED)

    def missing_dimensions(self) -> List[str]:
        return [k for k in self.REQUIRED if not self.kwargs.get(k)]

    def citations(self) -> List[str]:
        return [f"{what} <- {v.citation(self.document)}" for what, v in self.used]

    def as_json(self) -> Dict[str, Any]:
        return {"kind": self.kind, "name": self.name,
                "document": os.path.basename(self.document),
                "buildable": self.buildable,
                "kwargs": {k: v for k, v in self.kwargs.items()
                           if k not in ("identity", "text_params",
                                        "numeric_params", "standard_values")},
                "identity": dict(self.kwargs.get("identity") or {}),
                "text_params": dict(self.kwargs.get("text_params") or {}),
                "numeric_params": dict(self.kwargs.get("numeric_params") or {}),
                "standard_values": dict(self.kwargs.get("standard_values") or {}),
                "citations": self.citations(),
                "refused": list(self.refused)}


def _to_internal(unit_kind: str, value: Any) -> Any:
    """A sheet-stated value -> the internal unit ``standard_values`` expects.

    The factory owns the conversion constants (``rvt.famgen.factory.pounds``
    is exact by the pound's definition), so this asks it rather than keeping
    a second copy of a physical constant that could drift.  Imported at call
    time: :mod:`rvt.specsheet` is a reader and must stay importable without
    the family engine behind it.
    """
    from ..famgen import factory as _F
    if unit_kind == "mass":
        return _F.pounds(float(value))
    return value


def _family_name(by_key: Dict[str, SheetValue], document: str) -> str:
    """Prefer what the sheet calls the product; fall back to the file name.

    Never invents a name: a sheet that states neither manufacturer nor model
    yields the document's own stem, which is at least something the user can
    recognise.
    """
    maker = by_key.get("manufacturer")
    model = by_key.get("model")
    parts = [str(v.value).strip() for v in (maker, model) if v is not None]
    if parts:
        return " ".join(parts)
    return os.path.splitext(os.path.basename(document))[0] or "Spec Sheet Product"


def plan_from_sheet(parsed: ParsedSheet) -> SheetPlan:
    """A :class:`~.sheet.ParsedSheet` -> a ``generic_model`` famspec plan.

    Never raises: an unreadable or dimensionless sheet comes back as a plan
    whose ``buildable`` is False and whose ``refused`` says why, so the
    caller can report the reason and still deliver an archetype.
    """
    by_key = parsed.by_key()
    refused: List[str] = []
    #: sheet keys already refused BY NAME above, so the unconsumed-key sweep
    #: at the end does not say something different about the same row
    refused_keys: set = set()
    used: List[Tuple[str, SheetValue]] = []
    kwargs: Dict[str, Any] = {}

    if parsed.unreadable:
        refused.append(parsed.unreadable)

    for key, kw in _DIMS.items():
        v = by_key.get(key)
        if v is None:
            continue
        if v.unit_assumed:
            # the one place an assumed unit is fatal rather than caveated
            refused.append(
                f"{key}: the sheet states no unit for this row, so the value "
                f"{v.raw!r} cannot size a body -- millimetres and inches "
                f"differ by 25x. Stated at {v.citation(parsed.path)}")
            refused_keys.add(key)
            continue
        kwargs[kw] = float(v.value) / 12.0
        used.append((kw, v))

    # WHAT IS MISSING, said once and accurately. The earlier wording here --
    # "the body uses what it does state" -- was false in exactly the case that
    # produced it: a body needs all three, so a sheet short of one sizes
    # nothing at all and the archetype lane has to stand in.
    have = {kw for kw in _DIMS.values() if kwargs.get(kw)}
    short = [kw for kw in SheetPlan.REQUIRED if kw not in have]
    if short:
        stated = ", ".join(sorted(by_key)) if by_key else "nothing we recognise"
        refused.append(
            "no body can be sized from this sheet: it states no "
            + ", ".join(k[:-3] + "_in" for k in short)
            + ", and a solid needs height, width and depth together. "
            + f"The sheet did state {stated}")

    identity: Dict[str, str] = {}
    for key, caption in _IDENTITY.items():
        v = by_key.get(key)
        if v is not None:
            identity[caption] = str(v.value)
            used.append((f"identity:{caption}", v))

    text: Dict[str, str] = {}
    for key, caption in _TEXT.items():
        v = by_key.get(key)
        if v is not None:
            text[caption] = str(v.value)
            used.append((caption, v))

    standard: Dict[str, Any] = {}
    for key, (caption, unit_kind) in _STANDARD_VALUES.items():
        v = by_key.get(key)
        if v is None:
            continue
        if v.unit_assumed:
            refused.append(
                f"{caption}: unit assumed, not read ({v.citation(parsed.path)})")
            refused_keys.add(key)
            continue
        standard[caption] = _to_internal(unit_kind, v.value)
        used.append((f"standard:{caption}", v))

    numeric: Dict[str, Any] = {}
    for key, caption in _NUMERIC.items():
        v = by_key.get(key)
        if v is None:
            continue
        numeric[caption] = v.value
        used.append((caption, v))
        if v.unit_assumed:
            # not fatal for a rating -- but it must not pass as a reading
            refused.append(
                f"{caption}: unit assumed, not read ({v.citation(parsed.path)})")

    if identity:
        kwargs["identity"] = identity
    if text:
        kwargs["text_params"] = text
    if numeric:
        kwargs["numeric_params"] = numeric
    if standard:
        kwargs["standard_values"] = standard

    name = _family_name(by_key, parsed.path)
    kwargs["name"] = name
    # the citation that rides every dimension into the fact sheet
    kwargs["source"] = "spec sheet: %s" % os.path.basename(parsed.path)
    # the dimensions were READ off a published document, not typed by a
    # caller -- the distinction #688 DONE 3 exists to keep
    kwargs["dim_provenance"] = "fact"

    # A row that named NO field we know is already shown as `unmapped`. A row
    # that named a field we DO know but that no table above consumes was shown
    # nowhere and carried nowhere -- `length_in` and `diameter_in` are in
    # `vocab.FIELDS` and in none of the maps here, so a cable tray's headline
    # "Overall Length 120 in" was dropped in silence while the body was built
    # from the other three. The caveat promised "every row read but not used";
    # this is what makes that true.
    # A key already refused for a SPECIFIC reason must not collect a second,
    # weaker and untrue one: "Weight: unit assumed, not read" followed by
    # "weight_lb: this lane has no place to put it" said two different things
    # about one row, and the second was false -- the lane has a place; the
    # missing unit was the problem (#798 review round 2).
    taken = {v.key for _what, v in used} | refused_keys
    for key in sorted(by_key):
        if key in taken:
            continue
        v = by_key[key]
        refused.append(
            f"{key}: read and understood, but this lane has no place to put "
            f"it -- stated at {v.citation(parsed.path)}")

    for page, row, text_line in parsed.unmapped[:40]:
        refused.append(f"p{page} r{row}: not used -- {text_line[:80]}")

    return SheetPlan("generic_model", kwargs, used, refused, parsed.path, name)
