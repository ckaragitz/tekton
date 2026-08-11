"""rvt.ifc.materials -- read an IFC's OWN material names, colours and
per-product assignment.

WHY: the assembly lane (``rvt.ifc.assembly_parts``) measures every product's
mesh into prismatic solids but drops the IFC's material association entirely,
and the single-product lane (``rvt.ifc.famfrom_ifc``) carries surface-style
colours in the report only ("no material elements are authored -- the S0
discipline: no object-style copies").  A generated family therefore opens with
"No materials in this document" in Revit's Material Browser.

WHAT IS SOURCED HERE: only what the IFC itself declares --
``IfcRelAssociatesMaterial`` (which products carry which ``IfcMaterial``) and
the presentation style chain ``IfcSurfaceStyle -> IfcSurfaceStyleRendering ->
IfcColourRgb``.  Nothing is read from an Autodesk material library: house
doctrine (``docs/writer/house-standard.md`` rule G1b) is that material colours
are OURS, and ``rvt.genesis.house_standard``'s ``material-asset-descriptor``
disposition blanks even the descriptor that merely NAMES Autodesk's shipped
render-asset library.  Values read here are therefore ``given`` (the caller's
own IFC), never ``nominal`` and never a manufacturer claim.

The name join: exporters conventionally give an ``IfcMaterial`` and the
``IfcSurfaceStyle`` that paints it the same Name (verified on the 3D Stage
export: ``enclosure_gray``, ``copper_winding``, ...).  Where the names do not
join, the material is still returned -- with ``rgb=None`` -- so the caller can
author a material and say honestly that no colour was declared for it.

Territory: issue "materials from the IFC" (new module; nothing else in
``rvt.ifc`` changes).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

__all__ = ["MaterialFacts", "read_materials"]


def _rgb255(c) -> Optional[Tuple[int, int, int]]:
    """IfcColourRgb (0..1 reals) -> (r, g, b) 0..255, or None."""
    try:
        vals = (float(c.Red), float(c.Green), float(c.Blue))
    except Exception:
        return None
    out = []
    for v in vals:
        if v != v or v < 0.0:            # NaN / negative -> not a colour
            return None
        out.append(int(round(min(v, 1.0) * 255.0)))
    return (out[0], out[1], out[2])


class MaterialFacts:
    """What the IFC declares about materials, and nothing else.

    ``materials``  {material name: {"rgb": (r,g,b)|None, "products": [guid]}}
    ``by_product`` {product GlobalId: material name}
    ``notes``      honest remarks (unjoined styles, products with no material)
    """

    def __init__(self) -> None:
        self.materials: Dict[str, Dict[str, Any]] = {}
        self.by_product: Dict[str, str] = {}
        self.style_colours: Dict[str, Tuple[int, int, int]] = {}
        self.notes: List[str] = []

    def rgb_for(self, name: str) -> Optional[Tuple[int, int, int]]:
        m = self.materials.get(name)
        return m.get("rgb") if m else None

    def to_json(self) -> Dict[str, Any]:
        return {
            "materials": {n: {"rgb": list(d["rgb"]) if d.get("rgb") else None,
                              "product_count": len(d["products"])}
                          for n, d in sorted(self.materials.items())},
            "assigned_products": len(self.by_product),
            "notes": list(self.notes),
        }


def _surface_style_colours(f) -> Dict[str, Tuple[int, int, int]]:
    """{IfcSurfaceStyle.Name: (r,g,b)} through its rendering's SurfaceColour."""
    out: Dict[str, Tuple[int, int, int]] = {}
    for st in (f.by_type("IfcSurfaceStyle") or []):
        name = str(getattr(st, "Name", "") or "")
        if not name:
            continue
        for item in (getattr(st, "Styles", None) or []):
            col = getattr(item, "SurfaceColour", None)
            rgb = _rgb255(col) if col is not None else None
            if rgb is not None:
                out[name] = rgb
                break
    return out


def _material_names(relating) -> List[str]:
    """Every IfcMaterial name reachable from a RelatingMaterial (plain
    material, list, layer/constituent set) -- first one wins downstream."""
    if relating is None:
        return []
    if relating.is_a("IfcMaterial"):
        n = str(getattr(relating, "Name", "") or "")
        return [n] if n else []
    out: List[str] = []
    for attr in ("Materials", "MaterialLayers", "MaterialConstituents",
                 "MaterialProfiles", "ForLayerSet"):
        seq = getattr(relating, attr, None)
        if seq is None:
            continue
        for m in (seq if isinstance(seq, (list, tuple)) else [seq]):
            out.extend(_material_names(getattr(m, "Material", None) or m))
    return [n for n in out if n]


def read_materials(ifc_path: str) -> MaterialFacts:
    """Read material names, colours and per-product assignment from ``ifc_path``.

    Uses the same reader the rest of the IFC lane picks (ifcopenshell when a
    real wheel is installed, the stdlib ``steplite`` otherwise).
    """
    from . import product_facts as PF          # engine reader selection
    f = PF._open_ifc(ifc_path)

    facts = MaterialFacts()
    facts.style_colours = _surface_style_colours(f)

    for rel in (f.by_type("IfcRelAssociatesMaterial") or []):
        # NOT getattr(..., None): a reader that cannot serve the attribute
        # raises, and swallowing that turns an unreadable file into a silent
        # "this IFC declares no materials".  Say which it was.
        try:
            relating = rel.RelatingMaterial
            related = rel.RelatedObjects or []
        except AttributeError as exc:
            facts.notes.append(f"reader cannot read the material relation: {exc}")
            break
        names = _material_names(relating)
        if not names:
            continue
        name = names[0]
        slot = facts.materials.setdefault(
            name, {"rgb": facts.style_colours.get(name), "products": []})
        for obj in related:
            guid = str(getattr(obj, "GlobalId", "") or "")
            if not guid:
                continue
            slot["products"].append(guid)
            facts.by_product[guid] = name

    unjoined = [n for n, d in facts.materials.items() if not d.get("rgb")]
    if unjoined:
        facts.notes.append(
            "no IfcSurfaceStyle colour joined by name for: " + ", ".join(sorted(unjoined))
            + " -- material authored with no declared colour")
    extra = sorted(set(facts.style_colours) - set(facts.materials))
    if extra:
        facts.notes.append(
            f"{len(extra)} surface style(s) name no IfcMaterial: " + ", ".join(extra[:6]))
    if not facts.materials:
        facts.notes.append("the IFC declares no IfcRelAssociatesMaterial -- "
                           "no materials can be authored from it")
    return facts
