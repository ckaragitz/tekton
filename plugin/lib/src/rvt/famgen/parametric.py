"""rvt.famgen.parametric -- THE PARAMETRIC SPINE: declare what a family is
parametric IN, and get the whole drive chain authored from that declaration.

WHY.  Three pieces of the flex chain exist and none of them composes:

* ``param_drive`` (#372) authors the chain correctly but only for ONE shape:
  ``wire_panelboard_drive`` assumes two axes named Width/Height and a
  four-line axis-aligned rectangle. Anything else -- a third axis, a channel
  profile, a tray with a rung pitch, a parameter added later -- has nowhere
  to go.
* ``famdim`` (#689) emits the driver tables the chain was missing, but takes
  a finished document and infers what to drive from whatever labelled dims
  it happens to find.
* ``category_facts`` (#516) knows which template a category belongs to, but
  nothing connects that to what gets built.

This module is the missing declaration in the middle. You say *what the
product is parametric in*; it derives the reference planes, the family
parameters, the labelled dimensions, the alignments and the driver tables,
and it binds the result to the category's own Revit template.

    model = ParametricModel(
        category="cable_tray",
        axes=(DrivenAxis("width",  "Width",  (1, 0, 0), value=2.0),
              DrivenAxis("height", "Height", (0, 1, 0), value=0.5)),
        params=(FreeParam("Rung Spacing", value=0.75),
                FreeParam("Load Rating", spec=SPEC_NUMBER, instance=False)),
    )
    plan(model)              # inspect the whole authoring plan, no document
    wire(doc, model)         # author it

ADDING A PARAMETER AT ANY TIME is then ``model.with_param(FreeParam(...))``
or ``model.with_axis(DrivenAxis(...))`` -- the plan is recomputed, nothing is
hand-wired, and ``check_model`` says up front whether it is authorable.

WHAT IS FACT AND WHAT IS NOT.

* The element shapes (RefPlane, labelled LinearDimString, Alignment,
  VarSketch registration) are DONOR-MEASURED in ``param_drive`` -- fact.
* The category/template binding is TEMPLATE-VERIFIED via ``category_facts``
  where a row exists -- fact.
* The DRIVER TABLE VALUES are a hypothesis ladder (``famdim.RUNGS`` P0-P4).
  Nothing here claims a family flexes in Revit. Until a desktop verdict or a
  Revit-born parametric ``.rfa`` settles a rung, ``wire`` defaults to
  ``famdim.DEFAULT_RUNG`` and every surface stays silent about editability
  (hard rule 4).

KNOWN GAP, stated rather than papered over: an axis whose direction is the
EXTRUSION direction is not driven by the sketch at all -- Revit drives it
from the form's extrusion end, a different binding this module does not
author. ``check_model`` names such an axis instead of authoring something
that silently does nothing. See :data:`OUT_OF_PLANE_GAP`.

Territory: famgen (new module). Imports param_drive/famdim/skeleton; edits
no writer path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import famdim

#: Forge spec ids.  These are NOT re-spelled here: they are the constants
#: ``skeleton`` already carries and ``standards.SPECS`` already gates against
#: the format's own units table.  Writing a fresh plausible-looking spec id is
#: exactly how #516 and #601 happened -- the first cut of this module invented
#: five, three of which were wrong.
from .skeleton import (                                            # noqa: E402
    SPEC_INTEGER, SPEC_LENGTH, SPEC_NUMBER, SPEC_TEXT,
    PGROUP_DIMENSIONS as _PG_DIM, PGROUP_MATERIALS as _PG_MAT,
)

SPEC_ANGLE = "autodesk.spec.aec:angle-1.0.0"   # standards.SPECS['angle'], in
                                               # the units table [VERIFIED]

#: Parameter groups observed on the default templates [VERIFIED rft], taken
#: from skeleton's constants rather than re-spelled.
GROUP_DIMENSIONS = _PG_DIM
GROUP_MATERIALS = _PG_MAT
GROUP_MECHANICAL = "autodesk.parameter.group:mechanical-1.0.0"   # [VERIFIED rft]

#: Why an axis along the extrusion direction is refused rather than authored.
OUT_OF_PLANE_GAP = (
    "an axis parallel to the extrusion direction is not driven by the sketch "
    "profile: Revit drives extrusion depth from the form's extrusion end, a "
    "binding this module does not author. Authoring a sketch-style drive for "
    "it would produce a parameter that changes nothing -- exactly the failure "
    "#689 was opened for -- so it is named instead.")

#: The sketch plane's own two axes.  A driven axis must lie in this plane.
_IN_PLANE = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def _unit(v: Sequence[float]) -> Tuple[float, float, float]:
    x, y, z = (float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0)
    n = (x * x + y * y + z * z) ** 0.5
    if n == 0.0:
        return (0.0, 0.0, 0.0)
    return (x / n, y / n, z / n)


@dataclass(frozen=True)
class DrivenAxis:
    """One direction the product's geometry flexes in, and the family
    parameter that drives it.

    ``value`` is the CURRENT size along the axis in internal feet -- the
    dimension is authored at it, so it must be the size the geometry is
    actually drawn at or Revit is handed a contradiction.

    ``symmetric`` mirrors Revit's own template convention: two side planes at
    +-value/2 about the centre reference. ``symmetric=False`` (one plane
    moving away from a fixed origin plane) is NOT authored yet -- it needs the
    fixed reference pinned in ``m_fixedRefs``, which is rung P3.
    """
    key: str
    parameter: str
    direction: Tuple[float, float, float]
    value: float
    spec: str = SPEC_LENGTH
    group: str = GROUP_DIMENSIONS
    instance: bool = False
    symmetric: bool = True
    minimum: float = 0.0

    @property
    def unit_direction(self) -> Tuple[float, float, float]:
        return _unit(self.direction)

    @property
    def in_plane(self) -> bool:
        d = self.unit_direction
        return abs(d[2]) < 1e-9 and (abs(d[0]) > 1e-9 or abs(d[1]) > 1e-9)


@dataclass(frozen=True)
class FreeParam:
    """A family parameter that is NOT a geometric driver -- a rating, a
    material, a count, a note.  It is authored, grouped and typed exactly
    like a driven parameter; it simply has no dimension behind it.

    ``value`` is filled only when it is KNOWN (measured, given, or a catalog
    fact).  ``None`` means the parameter exists and is empty, which is
    correct -- an invented value is not (steer S-2026-08-11-a).
    """
    name: str
    spec: Optional[str] = SPEC_LENGTH
    group: str = GROUP_DIMENSIONS
    instance: bool = False
    value: Optional[float] = None
    note: str = ""


@dataclass(frozen=True)
class ParametricModel:
    """What a product is parametric in.  Immutable; the ``with_*`` helpers
    return a new model, which is what makes "associate any parameter at any
    time" a normal operation rather than a rewire."""
    category: str
    axes: Tuple[DrivenAxis, ...] = ()
    params: Tuple[FreeParam, ...] = ()
    lod: int = 400
    note: str = ""

    def with_param(self, p: FreeParam) -> "ParametricModel":
        return replace(self, params=self.params + (p,))

    def with_axis(self, a: DrivenAxis) -> "ParametricModel":
        return replace(self, axes=self.axes + (a,))

    def without(self, name: str) -> "ParametricModel":
        return replace(self,
                       axes=tuple(a for a in self.axes if a.parameter != name),
                       params=tuple(p for p in self.params if p.name != name))

    @property
    def parameter_names(self) -> Tuple[str, ...]:
        return tuple([a.parameter for a in self.axes] + [p.name for p in self.params])


# ---------------------------------------------------------------------------
# the category / template binding
# ---------------------------------------------------------------------------

def template_binding(category: str) -> Dict[str, Any]:
    """Tie a model to the Revit family template its category belongs to.

    Returns the category id, the part type and the template that is the
    citation, plus ``evidence``: ``"rft"`` when the category's own default
    template declares it, ``"resolver"`` when only the friendly-name table
    knows it.  Never raises for an unknown category -- it reports what it
    could not establish, because a caller must still be able to deliver
    (hard rule 1).
    """
    out: Dict[str, Any] = {"category": category, "category_id": None,
                           "part_type": None, "template": None,
                           "evidence": None, "notes": []}
    try:
        from . import skeleton as SK
        out["category_id"] = SK._resolve_category(category)
        out["evidence"] = "resolver"
    except Exception as exc:                                      # noqa: BLE001
        out["notes"].append(f"category not resolvable: {exc}")
    try:                       # enrichment; absent until #516 lands
        from . import category_facts as CF
        f = CF.fact(category)
        if f is not None:
            out.update({"category_id": f.category, "part_type": f.part_type,
                        "template": f.template, "evidence": "rft"})
            if category in getattr(CF, "ANNOTATION_KINDS", ()):
                out["notes"].append(
                    "this is an ANNOTATION category (part type -1, view-owned "
                    "instances): model geometry does not belong here")
        elif out["category_id"] is not None:
            out["notes"].append(
                "no default Revit template declares this category, so the id "
                "is the resolver's; see category_facts.STILL_INFERRED")
    except ImportError:
        out["notes"].append("category_facts not available in this build")
    return out


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def check_model(model: ParametricModel) -> List[str]:
    """Everything wrong with a model, as sentences.  Empty means authorable.

    This runs BEFORE anything is built, so a caller learns that an axis is
    un-authorable while it can still choose differently -- rather than
    shipping a parameter that silently drives nothing.
    """
    bad: List[str] = []
    if not model.category:
        bad.append("model has no category")
    seen: Dict[str, str] = {}
    for a in model.axes:
        where = f"axis {a.key!r}"
        if not a.parameter:
            bad.append(f"{where}: no parameter name")
        if a.parameter in seen:
            bad.append(f"{where}: parameter {a.parameter!r} already used by "
                       f"{seen[a.parameter]}")
        seen[a.parameter] = where
        if a.value <= 0.0:
            bad.append(f"{where}: value {a.value} is not positive -- the "
                       f"dimension would be authored at a size the geometry "
                       f"cannot have")
        if a.value < a.minimum:
            bad.append(f"{where}: value {a.value} is below its minimum "
                       f"{a.minimum}")
        if a.unit_direction == (0.0, 0.0, 0.0):
            bad.append(f"{where}: direction is the zero vector")
        elif not a.in_plane:
            bad.append(f"{where}: direction {a.unit_direction} is out of the "
                       f"sketch plane. {OUT_OF_PLANE_GAP}")
        if not a.symmetric:
            bad.append(f"{where}: symmetric=False needs the opposite "
                       f"reference pinned in m_fixedRefs (famdim rung P3), "
                       f"which is not a settled rung -- use symmetric=True")
    for p in model.params:
        if not p.name:
            bad.append("a free parameter has no name")
        if p.name in seen:
            bad.append(f"parameter {p.name!r} is declared twice "
                       f"({seen[p.name]} and a free parameter)")
        seen[p.name] = "free parameter"
    # two axes along the same line cannot both be driven independently.
    # NB the FULL 3-D cross product: using only its z component reads any
    # z-axis as parallel to x and y, which is wrong and buried the real
    # complaint (the out-of-plane one) under two false ones.
    for i, a in enumerate(model.axes):
        for b in model.axes[i + 1:]:
            da, db = a.unit_direction, b.unit_direction
            if da == (0.0, 0.0, 0.0) or db == (0.0, 0.0, 0.0):
                continue
            cx = da[1] * db[2] - da[2] * db[1]
            cy = da[2] * db[0] - da[0] * db[2]
            cz = da[0] * db[1] - da[1] * db[0]
            if (cx * cx + cy * cy + cz * cz) ** 0.5 < 1e-9:
                bad.append(f"axes {a.key!r} and {b.key!r} are parallel: they "
                           f"would drive the same pair of reference planes")
    return bad


# ---------------------------------------------------------------------------
# the plan -- everything that WOULD be authored, as inspectable data
# ---------------------------------------------------------------------------

def plan(model: ParametricModel, *,
         rung: str = famdim.DEFAULT_RUNG) -> Dict[str, Any]:
    """The complete authoring plan, derived with no document in hand.

    A plan is checkable, diffable and testable without building a file --
    which is how "associate any parameter at any time" stays honest: you can
    see exactly what a new parameter adds before authoring it.
    """
    problems = check_model(model)
    binding = template_binding(model.category)
    planes: List[Dict[str, Any]] = []
    dims: List[Dict[str, Any]] = []
    for a in model.axes:
        d = a.unit_direction
        half = a.value / 2.0
        for sign, side in ((-1.0, "low"), (1.0, "high")):
            planes.append({
                "axis": a.key, "side": side, "direction": d,
                "offset": sign * half,
                "role": f"{a.parameter} {side} side reference",
            })
        dims.append({
            "axis": a.key, "parameter": a.parameter, "value": a.value,
            "between": [f"{a.key}:low", f"{a.key}:high"],
            "labelled": True,
        })
    params = [{"name": a.parameter, "spec": a.spec, "group": a.group,
               "instance": a.instance, "drives": a.key, "value": a.value}
              for a in model.axes]
    params += [{"name": p.name, "spec": p.spec, "group": p.group,
                "instance": p.instance, "drives": None, "value": p.value,
                "note": p.note} for p in model.params]
    return {
        "category": model.category,
        "binding": binding,
        "lod": model.lod,
        "authorable": not problems,
        "problems": problems,
        "reference_planes": planes,
        "labelled_dimensions": dims,
        "parameters": params,
        "alignments_per_axis": 2,
        "driver": {
            "rung": rung,
            "description": famdim.describe_rung(rung),
            "status": "HYPOTHESIS -- no desktop verdict has confirmed any "
                      "rung; nothing here claims the family flexes",
        },
        "counts": {"axes": len(model.axes), "free_params": len(model.params),
                   "reference_planes": len(planes),
                   "labelled_dimensions": len(dims),
                   "parameters": len(params),
                   "alignments": 2 * len(model.axes)},
    }


def explain(model: ParametricModel, *,
            rung: str = famdim.DEFAULT_RUNG) -> str:
    """The plan as prose a delivery message can quote verbatim."""
    p = plan(model, rung=rung)
    b = p["binding"]
    lines = [
        f"{model.category} at LOD {model.lod}: "
        f"{p['counts']['axes']} driven axis/axes, "
        f"{p['counts']['free_params']} further parameter(s).",
        f"category id {b['category_id']} "
        f"({'from ' + str(b['template']) if b.get('template') else 'resolver table'}"
        f", evidence {b['evidence']}).",
    ]
    for d in p["labelled_dimensions"]:
        lines.append(f"  {d['parameter']} drives {d['axis']} "
                     f"(2 reference planes at +-{d['value'] / 2.0:g} ft)")
    for q in p["parameters"]:
        if q["drives"] is None:
            val = "empty" if q["value"] is None else f"{q['value']:g}"
            lines.append(f"  {q['name']}: {val} (no geometry behind it)")
    if p["problems"]:
        lines.append("NOT AUTHORABLE AS DECLARED:")
        lines += [f"  - {t}" for t in p["problems"]]
    lines.append(f"driver tables: rung {rung} -- {p['driver']['status']}.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# authoring
# ---------------------------------------------------------------------------

def wire(doc: Any, model: ParametricModel, *,
         rung: str = famdim.DEFAULT_RUNG,
         strict: bool = True) -> Dict[str, Any]:
    """Author the declared chain into ``doc`` (call after the form exists,
    before ``finalize``).

    With ``strict`` (the default) an un-authorable model raises rather than
    half-building one. ``strict=False`` authors what it can and returns the
    problems -- for callers that must deliver something regardless (hard
    rule 1) and will carry the caveat in the delivery.

    Returns the plan, plus what was actually authored.
    """
    p = plan(model, rung=rung)
    if p["problems"] and strict:
        raise ValueError("parametric: model is not authorable as declared:\n  "
                         + "\n  ".join(p["problems"]))
    from . import param_drive as PD

    authored: Dict[str, Any] = {"planes": 0, "dimensions": 0, "alignments": 0,
                                "driver": None, "delegated_to": None}
    in_plane = [a for a in model.axes if a.in_plane]
    if len(in_plane) == 2 and not p["problems"]:
        # the two-in-plane-axes case is exactly what param_drive's
        # donor-measured wiring authors; use it rather than re-deriving it.
        x_axis = min(in_plane, key=lambda a: abs(a.unit_direction[1]))
        y_axis = next(a for a in in_plane if a is not x_axis)
        summary = PD.wire_panelboard_drive(doc, x_caption=x_axis.parameter,
                                           y_caption=y_axis.parameter)
        authored["delegated_to"] = "param_drive.wire_panelboard_drive"
        authored["planes"] = 4
        authored["dimensions"] = 2
        authored["alignments"] = 4
        authored["summary"] = summary
    else:
        authored["notes"] = [
            "no wiring authored: param_drive's donor-measured chain covers "
            "exactly two in-plane axes on a rectangular profile. Other shapes "
            "need their own measured wiring, which is not invented here."]
    if authored["dimensions"]:
        authored["driver"] = famdim.apply_to_doc(doc, rung=rung)
    return {"plan": p, "authored": authored}


# ---------------------------------------------------------------------------
# convenience: the common declaration
# ---------------------------------------------------------------------------

def box_model(category: str, *, width: float, height: float,
              width_param: str = "Width", height_param: str = "Height",
              params: Sequence[FreeParam] = (), lod: int = 400,
              note: str = "") -> ParametricModel:
    """The two-axis rectangular model -- the shape param_drive's measured
    wiring covers, declared rather than hand-wired."""
    return ParametricModel(
        category=category,
        axes=(DrivenAxis("width", width_param, (1.0, 0.0, 0.0), float(width)),
              DrivenAxis("height", height_param, (0.0, 1.0, 0.0), float(height))),
        params=tuple(params), lod=lod, note=note)


# ---------------------------------------------------------------------------
# ANY PARAMETER, FROM A PROMPT -- the kind taxonomy
# ---------------------------------------------------------------------------
#
# A user does not ask for "a driven length axis".  They ask for "a parameter to
# toggle the door swinging open and closed", "a parameter for the finish", "an
# angle for the blade pitch".  Every one of those is a family parameter bound to
# SOMETHING; what differs is what it binds to:
#
#   length   -> a labelled dimension between two reference planes   (AUTHORED)
#   angle    -> a labelled ANGULAR dimension about a reference      (gap)
#   yesno    -> an element's visibility                             (gap)
#   material -> an element's material property                      (gap)
#   data     -> nothing; the parameter is the deliverable           (AUTHORED)
#
# The first and last are authored today.  The middle three all need the SAME
# missing piece -- the table that associates a family parameter with an
# element PROPERTY rather than a dimension segment.  ``m_paramExprs`` is that
# mechanism for dimensions; the schema shows no per-form visibility-parameter
# field, so visibility/material/angle association is the same shape of problem
# and is tracked as one gap, not three.
#
# Hard rule 1 governs the whole table: an unauthorable request is DELIVERED as
# a real, correctly typed, correctly grouped family parameter with an honest
# note that nothing is bound to it yet -- never refused, never silently
# dropped, and never described as working.

#: kind -> (Forge spec, what it binds to, authorable today, the honest note)
#: ``spec`` is None where THIS REPO HOLDS NO VERIFIED SPELLING for that
#: storage class.  A None spec is not a bug and never blocks delivery -- it is
#: the honest state, and inventing an id to fill it is the thing that must not
#: happen (the first cut of this table invented five ids, three of which were
#: measurably wrong and two of which -- bool and reference -- have no verified
#: spelling anywhere in the repo).
PARAM_KINDS: Dict[str, Tuple[Optional[str], str, bool, str]] = {
    "length": (SPEC_LENGTH, "a labelled dimension between two reference planes",
               True, ""),
    "data": (SPEC_NUMBER, "nothing -- the parameter itself is the deliverable",
             True, ""),
    "text": (SPEC_TEXT, "nothing -- the parameter itself is the deliverable",
             True, ""),
    "integer": (SPEC_INTEGER,
                "nothing -- the parameter itself is the deliverable", True, ""),
    "angle": (SPEC_ANGLE, "a labelled angular dimension about a reference",
              False,
              "typed as an angle (a verified spec), but no angular dimension "
              "is bound to it yet: changing it will not rotate anything"),
    "yesno": (None, "an element's visibility", False,
              "requested as a Yes/No. Two things are missing and both are "
              "stated rather than faked: this repo holds no VERIFIED Forge "
              "spec id for a boolean parameter, and the "
              "family-parameter-to-visibility association is not authored. "
              "The request is recorded and delivered; toggling it will not "
              "show or hide anything yet"),
    "material": (None, "an element's material property", False,
                 "requested as a material. This repo holds no VERIFIED Forge "
                 "spec id for a material-reference parameter, and no "
                 "association to a solid's material is authored. The request "
                 "is recorded and delivered; changing it will not restyle "
                 "anything yet"),
}

#: The one missing mechanism behind every unauthorable kind above.  Recorded
#: once, as one gap, because it is one gap.
ASSOCIATION_GAP = (
    "binding a family parameter to an element PROPERTY (visibility, material, "
    "an angle) rather than to a dimension segment. m_paramExprs is that "
    "mechanism for dimensions; the schema exposes no per-form "
    "visibility-parameter field, so the association table for properties has "
    "still to be located. Until it is, these parameters are authored, typed "
    "and grouped correctly but drive nothing -- and say so.")

#: Words a prompt uses for each kind, longest-first so "yes/no" beats "no".
_KIND_WORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("yesno", ("toggle", "yes/no", "yes no", "on/off", "on off", "switch",
               "show/hide", "show or hide", "visible", "visibility", "boolean",
               "checkbox", "open and close", "open/close", "swing")),
    ("angle", ("angle", "rotation", "rotate", "pitch", "tilt", "degrees",
               "swing angle")),
    ("material", ("material", "finish", "colour", "color")),
    ("length", ("width", "height", "depth", "length", "thickness", "diameter",
                "radius", "spacing", "clearance", "size", "offset")),
    ("integer", ("count", "number of", "quantity", "poles", "gangs", "ways")),
    ("text", ("name", "label", "note", "description", "mark", "model number")),
)


#: Where each kind's parameter belongs when the caller does not say.  A
#: Yes/No visibility toggle is not a dimension, and filing it under Dimensions
#: is the kind of small wrongness a user sees immediately in Revit's dialog.
_DEFAULT_GROUP: Dict[str, str] = {
    "length": GROUP_DIMENSIONS,
    "angle": GROUP_DIMENSIONS,
    "material": GROUP_MATERIALS,
    "yesno": "autodesk.parameter.group:visibility-1.0.0",   # [INFERRED]
    "text": "autodesk.parameter.group:text-1.0.0",          # [VERIFIED skeleton]
    "integer": "autodesk.parameter.group:text-1.0.0",
    "data": GROUP_DIMENSIONS,
}

#: Filler a request phrases itself with -- stripped so the PARAMETER NAME is
#: what Revit's dialog should show ("Door Swing"), not the sentence the user
#: typed ("a parameter to toggle the door swinging open and close").
_REQUEST_FILLER = (
    "a parameter to", "a parameter for", "parameter to", "parameter for",
    "add a parameter", "a param for", "a param to", "give me a", "i want a",
    "toggle the", "toggle", "control the", "control", "set the", "the ",
    "a ", "an ",
)

#: Words that describe the MECHANISM rather than the thing, dropped from the
#: end of a derived name ("door swinging open and close" -> "Door Swing").
_NAME_TAIL = ("open and close", "open and closed", "open or close",
              "open/close", "on and off", "yes or no", "swinging", "swing")


def _param_name(text: str) -> str:
    """A short Title Case parameter name from a request sentence.

    Deliberately simple and reversible: a caller who wants an exact name
    passes ``name=``.  Getting this wrong is cosmetic -- getting it wrong
    SILENTLY is not, so the full request is always kept on the record as
    ``requested``.
    """
    t = " ".join(str(text or "").strip().lower().split())
    if not t:
        return ""
    changed = True
    while changed:
        changed = False
        for f in _REQUEST_FILLER:
            if t.startswith(f):
                t = t[len(f):].strip()
                changed = True
    for tail in _NAME_TAIL:
        if t.endswith(tail):
            t = t[: -len(tail)].strip()
    t = t.rstrip(" ,.;:")
    if not t:
        return ""
    words = [w for w in t.split() if w not in ("the", "a", "an", "of", "to")]
    return " ".join(w.capitalize() for w in words[:4])


def classify_request(text: str) -> str:
    """The parameter KIND a user's words are asking for.

    Deliberately small and explainable -- it reads the request's own words and
    falls back to ``data`` rather than guessing something specific.  Callers
    that know better pass ``kind=`` explicitly.
    """
    t = " " + str(text or "").strip().lower() + " "
    for kind, words in _KIND_WORDS:
        if any(w in t for w in words):
            return kind
    return "data"


def request_param(text: str, *, kind: Optional[str] = None,
                  name: Optional[str] = None,
                  group: Optional[str] = None,
                  instance: bool = False,
                  value: Optional[float] = None) -> Dict[str, Any]:
    """Turn a user's request for a parameter into a declaration plus the
    honest note that must ride with it.

        request_param("a parameter to toggle the door swinging open and close")
        -> kind 'yesno', authorable False, a real Yes/No parameter + the note
           that nothing is bound to it yet

    Never refuses: an unbindable request still yields a correctly typed,
    correctly grouped family parameter, because a delivered parameter the user
    can see and bind by hand in the family editor beats no file (hard rule 1).
    """
    k = kind or classify_request(text)
    if k not in PARAM_KINDS:
        raise ValueError(f"unknown parameter kind {k!r}; "
                         f"known: {', '.join(sorted(PARAM_KINDS))}")
    spec, binds_to, authorable, note = PARAM_KINDS[k]
    grp = group or _DEFAULT_GROUP.get(k, GROUP_DIMENSIONS)
    label = name or _param_name(text) or k.title()
    return {
        "kind": k,
        "requested": text,
        "spec_verified": spec is not None,
        "param": FreeParam(name=label, spec=spec, group=grp,
                           instance=instance, value=value, note=note),
        "binds_to": binds_to,
        "authorable": authorable,
        "note": note,
        "gap": None if authorable else ASSOCIATION_GAP,
    }


def add_requested(model: ParametricModel, text: str,
                  **kw: Any) -> Tuple[ParametricModel, Dict[str, Any]]:
    """``model`` + the parameter a user just asked for, and the request record.

    A ``length`` request with a ``value`` becomes a real DRIVEN axis when the
    model has room for one; everything else becomes a declared parameter with
    its note.  Either way the model comes back with the parameter on it.
    """
    req = request_param(text, **kw)
    p = req["param"]
    if req["kind"] == "length" and kw.get("value"):
        used = {a.unit_direction for a in model.axes}
        for d in _IN_PLANE:
            if d not in used:
                axis = DrivenAxis(key=p.name.lower().replace(" ", "_"),
                                  parameter=p.name, direction=d,
                                  value=float(kw["value"]), spec=p.spec,
                                  group=p.group, instance=p.instance)
                if not check_model(model.with_axis(axis)):
                    req["authorable"] = True
                    req["binds_to"] = ("a labelled dimension along "
                                       f"{d} (newly driven)")
                    return model.with_axis(axis), req
        req["note"] = ("both in-plane axes are already driven, so this length "
                       "is authored as a parameter without a dimension")
        req["authorable"] = False
    return model.with_param(p), req
