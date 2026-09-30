"""equipment_clearance -- clearance zones on every generated equipment family, with
Yes/No parameters bound to their visibility (steer #882, on #818 / #820 / #690).

Every electrical-equipment family we generate carries its clearance zones by
default ("That should always be added to the equipment"):

* a FRONT working-space zone, sized by the NEC 110.26(A) table in
  :mod:`rvt.famgen.clearance` (depth by voltage to ground and Condition, width
  the greater of the equipment's or 30 in, height the greater of 6 1/2 ft or the
  equipment's, measured from the floor), starting at the working face (-y);
* a TOP zone: the 110.26(E)(1) dedicated equipment space for the kinds that rule
  names (panelboards, switchboards, ...), else a NOMINAL ventilation clearance
  above the top (a transformer's is its nameplate marking, NEC 450.9 -- so it is
  stated as nominal and overridable, never presented as code).

Their visibility is switchable from the family's parameters, the way the owner's
library structures it (measured privately, counts only): a master instance
toggle, plus a Front and a Top toggle; each zone is shown by
``and(master, its own)``, a Yes/No formula (#850) on a parameter BOUND to the
zone's visibility -- ``FamilyParametrizedElemParamsCell`` entry
``{m_famParamId: <that parameter>, m_elemPropId: -1006205}`` on the extrusion,
the driving parameter in its header's ``m_deletion`` list: the association Revit
writes for a solid's Visible property (764 solids so bound in the owner's library,
and the same cell our connectors already carry for voltage / load).

The zones are painted with a graphics-only magenta, half-transparent material
(steer #884: "transparent and purple ... just like eVolve").  Honest limits, said
in the family's notes: no subcategory yet (#883), and "the toggle hides the zone" is a
claim only a desktop / viewer verdict can make (hard rule 4) -- the file carries
the binding, nothing more is asserted.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from . import clearance as CL

#: the element property a Yes/No parameter drives to show / hide a solid ("Visible")
ELEM_PROP_VISIBLE = -1006205

#: our parameter names (our own words; never a library's)
P_SHOW = "Show Clearances"
P_FRONT = "Show Front Clearance"
P_TOP = "Show Top Clearance"
P_FRONT_ON = "Front Clearance Visible"
P_TOP_ON = "Top Clearance Visible"
#: every parameter the zones add, in the order they are authored
TOGGLE_PARAMS = (P_SHOW, P_FRONT, P_TOP, P_FRONT_ON, P_TOP_ON)

#: the zones' look (steer #884, "transparent and purple ... just like eVolve"): a
#: graphics-only material, shaded by its colour -- magenta, half see-through
CLEARANCE_MATERIAL = "Clearance Zone"
CLEARANCE_RGB = (255, 0, 255)
CLEARANCE_TRANSPARENCY = 0.5
OST_MATERIALS = -2000700

#: a transformer's (and any kind without a dedicated space) top zone: NOMINAL
NOMINAL_TOP_FT = 1.0
GROUP_VISIBILITY = "autodesk.parameter.group:visibility-1.0.0"


def bind_visibility(form, param) -> None:
    """Bind ``param`` (a Yes/No family parameter element) to the Visible property of
    the extrusion in ``form``: the association cell between the extrusion helper and
    the pattern helper, and the parameter in the header's deletion parents."""
    ext = next(e for e in form.elements if e.class_name == "ExtrusionElem")
    cells = ext.obj["m_cellList"]["value"]["m_cells"]
    cell = {"ptr_class": "FamilyParametrizedElemParamsCell", "pid": -1, "value": {
        "m_paramDrivenData": [{"m_famParamId": int(param.elem_id),
                               "m_elemPropId": ELEM_PROP_VISIBLE,
                               "m_geomTag": -1, "m_bIsSymbol": False}]}}
    at = next((i for i, c in enumerate(cells)
               if str(c.get("ptr_class", "")).endswith("PatternHelper")), len(cells))
    cells.insert(at, cell)
    parents = ext.header["m_parents"]["value"]
    parents["m_deletion"] = sorted(set(parents["m_deletion"]) | {int(param.elem_id)})
    form.params["visibility_param"] = param.refs.get("caption") or param.elem_id


def new_family_material(doc, name: str, rgb, transparency: float):
    """A graphics-only ``MaterialElem`` in a FAMILY document (no appearance asset,
    shaded by ``m_color`` -- the shape Revit's own analytical-surface materials
    have), owned by the self-Family: the project writer's
    :func:`rvt.genesis.types.new_material` object under a family element header
    (Materials category, deletion parents = itself + the family, seq-103 dummy),
    as a Revit-born family's materials carry.  Added to ``doc``; returned."""
    from ..genesis import types as TY
    from . import skeleton as SK
    fam = doc.self_family.elem_id
    eid = SK._alloc(doc.ids)
    rec = TY.new_material(str(name), tuple(rgb), elem_id=eid, transparency=float(transparency))
    obj = rec.obj
    obj["m_famId"] = int(fam)
    hdr = SK.element_header("MaterialElem", category=OST_MATERIALS,
                            deletion=sorted({eid, int(fam)}), flags=67108878,
                            family_id=fam)
    el = SK.SkelElement(eid, "MaterialElem", hdr, obj, None, kind="material",
                        refs={"name": str(name), "family": fam})
    doc.add(el)
    return el


def apply_material(form, material) -> None:
    """Paint ``form``'s extrusion with ``material``: its ``m_materialId``, every cached
    face's render style, and the material among the element's deletion parents."""
    mid = int(material.elem_id)
    ext = next(e for e in form.elements if e.class_name == "ExtrusionElem")
    ext.obj["m_materialId"] = mid
    parents = ext.header["m_parents"]["value"]
    parents["m_deletion"] = sorted(set(parents["m_deletion"]) | {mid})

    def paint(v):
        if isinstance(v, dict):
            if "m_renderStyleId" in v:
                v["m_renderStyleId"] = mid
            for x in v.values():
                paint(x)
        elif isinstance(v, list):
            for x in v:
                paint(x)
    for e in form.elements:
        paint(e.obj)
        if e.rep:
            paint(e.rep)
    form.params["material"] = material.refs.get("name")


def add_clearance_zones(doc, add_box_form, *, kind: str, width_ft: float, depth_ft: float,
                        height_ft: float, body_center=(0.0, 0.0), base_z_ft: float = 0.0,
                        front_y_ft: Optional[float] = None, front_dir: int = -1,
                        floor_z_ft: float = 0.0, mounting_note: str = "",
                        voltage_to_ground: Optional[float] = None,
                        condition: Optional[int] = None,
                        top_ft: Optional[float] = None) -> Dict[str, Any]:
    """Author the front and top clearance zones of equipment whose body spans
    ``width_ft`` x ``depth_ft`` in plan (centred on ``body_center``) from ``base_z_ft``
    to ``base_z_ft + height_ft`` above the family origin, plus the Yes/No parameters
    that show them.

    ``front_y_ft`` / ``front_dir`` = the working face's y and the direction the
    working space extends (-1 = toward -y; default: the body's -y face);
    ``floor_z_ft`` = the floor relative to the origin (0 for floor-standing kinds; a
    wall-hung cabinet's floor is below its origin, stated in ``mounting_note``).  The
    working space is measured from that floor (110.26(A)(3)).  ``add_box_form`` is
    the factory's form author.  Returns the report block (sizes, sources,
    assumptions, forms)."""
    from . import skeleton as SK
    cx, cy = float(body_center[0]), float(body_center[1])
    if front_y_ft is None:
        front_y_ft = cy - depth_ft / 2.0 if front_dir < 0 else cy + depth_ft / 2.0
    top_of_equipment = base_z_ft + height_ft
    ws = CL.working_space(equipment_width_ft=width_ft,
                          equipment_height_ft=top_of_equipment - floor_z_ft,
                          voltage_to_ground=voltage_to_ground, condition=condition)
    try:
        ded = CL.dedicated_space(kind, equipment_width_ft=width_ft, equipment_depth_ft=depth_ft)
    except CL.ClearanceError:
        ded = None
    if ded is not None and ded.applies:
        top_h, top_src = float(ded.height_above_ft), f"{ded.source} ({ded.status})"
    else:
        top_h = float(top_ft) if top_ft else NOMINAL_TOP_FT
        top_src = ("given" if top_ft else
                   f"NOMINAL {top_h * 12:g} in ventilation clearance above the top -- not a "
                   f"code value (a transformer's is its nameplate marking, NEC 450.9); "
                   f"override it with the equipment's own")
    front = add_box_form(doc, ws.width_ft, ws.depth_ft, ws.height_ft, base_z_ft=floor_z_ft,
                         center=(cx, front_y_ft + front_dir * ws.depth_ft / 2.0))
    front.params.update({"role": "clearance: front working space", "source": ws.source})
    top = add_box_form(doc, width_ft, depth_ft, top_h, base_z_ft=top_of_equipment,
                       center=(cx, cy))
    top.params.update({"role": "clearance: top", "source": top_src})
    mat = new_family_material(doc, CLEARANCE_MATERIAL, CLEARANCE_RGB, CLEARANCE_TRANSPARENCY)
    apply_material(front, mat)
    apply_material(top, mat)

    yes = SK.SPEC_YESNO
    doc.add_family_parameter(P_SHOW, yes, GROUP_VISIBILITY, is_instance=True, default=1)
    doc.add_family_parameter(P_FRONT, yes, GROUP_VISIBILITY, is_instance=False, default=1)
    doc.add_family_parameter(P_TOP, yes, GROUP_VISIBILITY, is_instance=False, default=1)
    f_on = doc.add_family_parameter(P_FRONT_ON, yes, GROUP_VISIBILITY, is_instance=True,
                                    formula=f"and({P_SHOW}, {P_FRONT})", default=1)
    t_on = doc.add_family_parameter(P_TOP_ON, yes, GROUP_VISIBILITY, is_instance=True,
                                    formula=f"and({P_SHOW}, {P_TOP})", default=1)
    bind_visibility(front, f_on)
    bind_visibility(top, t_on)
    report = {
        "front": {"width_ft": ws.width_ft, "depth_ft": ws.depth_ft, "height_ft": ws.height_ft,
                  "source": ws.source, "verified": ws.verified, "status": ws.status,
                  "assumed": dict(ws.assumed)},
        "top": {"height_ft": top_h, "source": top_src},
        "floor_z_ft": floor_z_ft, "mounting": mounting_note,
        "toggles": [P_SHOW, P_FRONT, P_TOP],
        "forms": [front, top],
    }
    doc.notes.append(
        f"clearance zones (steer #882): front working space {ws.depth_ft:g} ft deep x "
        f"{ws.width_ft * 12:g} in wide x {ws.height_ft:g} ft high ({ws.source}; "
        f"{ws.status}); top zone {top_h * 12:g} in ({top_src}); shown by '{P_SHOW}' (per "
        f"instance) with '{P_FRONT}' / '{P_TOP}' (per type), each bound to its zone's "
        f"visibility -- NOT yet verified in Revit (hard rule 4); the zones are ordinary "
        f"solids painted '{CLEARANCE_MATERIAL}' (magenta, {CLEARANCE_TRANSPARENCY:.0%} "
        f"transparent, a graphics-only material; no subcategory yet, #883)"
        + (f"; {mounting_note}" if mounting_note else ""))
    for k, v in ws.assumed.items():
        doc.notes.append(f"clearance assumption -- {k}: {v}")
    return report
