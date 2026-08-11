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

#: Forge spec ids, all VERIFIED present in the format's own units table
#: (``famgen/assets/family_units.json``) and observed on Revit's default
#: family templates.
SPEC_LENGTH = "autodesk.spec.aec:length-1.0.0"
SPEC_ANGLE = "autodesk.spec.aec:angle-1.0.0"
SPEC_NUMBER = "autodesk.spec:spec.number-1.0.0"

#: Parameter groups observed on the default templates [VERIFIED rft].
GROUP_DIMENSIONS = "autodesk.parameter.group:dimensions-1.0.0"
GROUP_MATERIALS = "autodesk.parameter.group:materials-1.0.0"
GROUP_MECHANICAL = "autodesk.parameter.group:mechanical-1.0.0"

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
    spec: str = SPEC_LENGTH
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
