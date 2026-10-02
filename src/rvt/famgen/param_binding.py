"""param_binding -- a family parameter ASSOCIATED to a solid's property (#877).

Revit stores "this parameter drives that property" on the element itself: a
``FamilyParametrizedElemParamsCell`` in its cell list holding
``m_paramDrivenData`` entries ``{m_famParamId, m_elemPropId, m_geomTag -1,
m_bIsSymbol False}``, and the parameter among the element header's deletion
parents.  A private census of the owner's reference library (421 families, counts
only) pins the two properties authored here:

* ``-1006205`` VISIBLE, driven by a Yes/No parameter: 764 extrusions, 396 curves,
  308 model texts, 170 geometry combinations, and sweeps / blends / revolutions;
* ``-1002107`` MATERIAL, driven by a material parameter (``ParamDefMaterialBrowse``,
  661 associations: 367 extrusions, 154 geometry combinations, blends, revolutions,
  sweeps) -- and the bound solid's own ``m_materialId`` is the parameter's current
  value (226 / 226 sampled), the parameter in its deletion parents (every sampled
  bound solid, both properties).

The cell sits before the element's ``PatternHelper`` (the order the clearance
zones' visibility binding, #690, and our connectors already write).  Associations
to NESTED family parameters (positive property ids on a nested ``FamilyInstance``)
are a separate, later item.  That Revit honours a binding -- the solid hides, its
material follows the parameter -- needs a desktop verdict (hard rule 4).
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

#: the solid's Visible property (Yes/No)
ELEM_PROP_VISIBLE = -1006205
#: the solid's Material property (an element id)
ELEM_PROP_MATERIAL = -1002107
#: the element classes a solid property binding is written on
SOLID_CLASSES = ("ExtrusionElem", "SweepElem", "BlendElem", "RevolutionElem")


class BindingError(ValueError):
    """The binding cannot be written (no solid in the form, the wrong parameter kind)."""


def solid_of(form: Any):
    """The one solid element of a form (``geometry.FormBundle``)."""
    solids = [e for e in form.elements if e.class_name in SOLID_CLASSES]
    if len(solids) != 1:
        raise BindingError(f"a {form.kind!r} form has {len(solids)} solids, not one")
    return solids[0]


def bind(element: Any, param: Any, prop: int) -> None:
    """Associate ``param`` (a family parameter element) to ``element``'s property
    ``prop``: the entry in its parametrized-params cell (created before the
    ``PatternHelper`` when absent; a second binding of the same property is
    replaced, never duplicated) and the parameter in its deletion parents."""
    cells = element.obj["m_cellList"]["value"]["m_cells"]
    entry = {"m_famParamId": int(param.elem_id), "m_elemPropId": int(prop),
             "m_geomTag": -1, "m_bIsSymbol": False}
    cell = next((c for c in cells
                 if str(c.get("ptr_class", "")).endswith("FamilyParametrizedElemParamsCell")), None)
    if cell is None:
        cell = {"ptr_class": "FamilyParametrizedElemParamsCell", "pid": -1,
                "value": {"m_paramDrivenData": []}}
        at = next((i for i, c in enumerate(cells)
                   if str(c.get("ptr_class", "")).endswith("PatternHelper")), len(cells))
        cells.insert(at, cell)
    data = cell["value"]["m_paramDrivenData"]
    data[:] = [d for d in data if d.get("m_elemPropId") != int(prop)] + [entry]
    parents = element.header["m_parents"]["value"]
    parents["m_deletion"] = sorted(set(parents["m_deletion"]) | {int(param.elem_id)})


def _kind(param: Any) -> str:
    return str(param.refs.get("kind") or param.refs.get("spec") or "")


def bind_visibility(form: Any, param: Any) -> None:
    """A Yes/No ``param`` drives whether the form's solid is visible."""
    from .skeleton import SPEC_YESNO
    if _kind(param) not in ("ParamDefYesNo", SPEC_YESNO):
        raise BindingError(f"visibility is driven by a Yes/No parameter, not {_kind(param)!r}")
    bind(solid_of(form), param, ELEM_PROP_VISIBLE)
    form.params["visibility_param"] = param.refs.get("caption") or param.elem_id


def bind_material(form: Any, param: Any, material_id: int) -> None:
    """A material ``param`` drives the form's solid material.  ``material_id`` is
    the parameter's current value (the ``MaterialElem`` its rows hold): the solid
    carries it as its own ``m_materialId``, as every bound solid of the library does."""
    from .skeleton import SPEC_MATERIAL
    if _kind(param) not in ("ParamDefMaterialBrowse", SPEC_MATERIAL):
        raise BindingError(f"a material is driven by a material parameter, not {_kind(param)!r}")
    solid = solid_of(form)
    bind(solid, param, ELEM_PROP_MATERIAL)
    solid.obj["m_materialId"] = int(material_id)
    form.params["material_param"] = param.refs.get("caption") or param.elem_id


def add_material_parameter(doc: Any, name: str, material_id: int, *,
                           group: Optional[str] = None):
    """A family MATERIAL parameter whose value on every EXISTING type is
    ``material_id`` (the row's ``m_elemId``; :func:`rvt.famgen.skeleton.family_param_value`).
    A type added afterwards starts every parameter at 0.0, as ``FamilyDoc.add_type``
    does: give it ``{param.elem_id: {"m_elemId": material_id}}`` in its row."""
    from . import skeleton as SK
    return doc.add_family_parameter(name, SK.SPEC_MATERIAL,
                                    group or "autodesk.parameter.group:materials-1.0.0",
                                    default={"m_elemId": int(material_id)})


def bound(element: Any) -> Iterable[dict]:
    """The ``m_paramDrivenData`` entries an element carries (read-back helper)."""
    for c in element.obj["m_cellList"]["value"]["m_cells"]:
        if str(c.get("ptr_class", "")).endswith("FamilyParametrizedElemParamsCell"):
            yield from c["value"]["m_paramDrivenData"]
