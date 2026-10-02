"""rvt.famgen.trapeze_nested -- the strut trapeze with its washers and nuts as
NESTED families (issue #917 DONE 5), opt-in:
``make_archetype(product="strut_trapeze", nested_hardware=True)``.

Born families nest their hardware (the #917 census: 7,845 nested instances in
313 / 421 born families); the default trapeze draws its washers and nuts as
solids in its own document.  This lane builds the trapeze WITHOUT those solids
and, when it is written, nests two families of OUR OWN making into it with
:func:`rvt.famgen.nest.nest_family` -- never a donor, never a reference family:

* a SQUARE WASHER: one box, whose instance parameter ``Washer Size`` drives its
  width in x AND y (two symmetric in-plane drives, the #787 / #904 law) and
  whose ``Washer Thickness`` drives its height (a #787 Case B cap-face drive);
* a HEX NUT: one hexagonal prism, whose instance parameter ``Nut Height``
  drives its height (Case B).  Its ``Nut Across Flats`` is an instance
  parameter that carries a VALUE ONLY: a hexagon is not a rectangle and no
  verified mechanism resizes it, so it is not wired to the geometry.

Per tier and rod, a washer + nut below the channel back and a washer + nut on
the lips (the same positions the solid version draws), each instance locked by
its Center (Left/Right) to the Rod Inset plane of its rod (the planes
``drive_law.wire_follow`` creates) and by its Center (Front/Back) to the
origin Center (Front/Back) plane; the host's ``Washer Size`` / ``Washer
Thickness`` / ``Nut Across Flats`` are associated to the children's instance
parameters (a host TYPE parameter driving a nested INSTANCE parameter: 2,087
born entries).

What this lane does NOT do (stated in the product's notes, never hidden):

* the nested instances do not follow the trapeze's HEIGHT drives: our children
  carry no Center (Elevation) reference, so they are placed at fixed heights
  and only the in-plane locks hold them -- flexing Tier Spacing, Strut Height
  or Washer Thickness in the host moves the host's planes, not the instances.
  The solid version's washers and nuts do ride those planes.  That is why the
  solid version stays the DEFAULT;
* nothing here has a desktop-Revit verdict (hard rule 4): validator green, an
  empty constraint-law report with every nested lock judged by CG8, and
  coherent registries are facts about the file.

Hard rule 1: a nesting that fails or is refused still DELIVERS -- the solid
trapeze is written at the same path with the reason in the report's notes.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import factory as F
from . import skeleton as SK

IN = 1.0 / 12.0

WASHER_FAMILY = "Square Strut Washer"
NUT_FAMILY = "Hex Nut"

#: host parameter caption -> the child's instance parameter it drives
WASHER_ASSOCIATIONS = {"Washer Size": "Washer Size", "Washer Thickness": "Washer Thickness"}
NUT_ASSOCIATIONS = {"Nut Across Flats": "Nut Across Flats"}


class NestedHardwareError(RuntimeError):
    """The nested-hardware lane cannot be applied (the caller still gets the
    solid trapeze)."""


# ---------------------------------------------------------------------------
# what the host keeps and what moves into the children
# ---------------------------------------------------------------------------

def is_hardware(name: str) -> bool:
    """A washer or nut part of the solid trapeze (``tier i washer below left``)."""
    return " washer " in f" {name} " or " nut " in f" {name} "


def strip_hardware(parts: Sequence[Dict[str, Any]], drives: Optional[List[Dict[str, Any]]],
                   heights: Optional[List[Dict[str, Any]]]
                   ) -> Tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]],
                              Optional[List[Dict[str, Any]]]]:
    """The trapeze without its washer / nut solids: the parts list without
    them, the Rod Inset follow keeping only the rods (wire_follow still makes
    the two Rod Inset planes the nested instances lock to), and the height
    chain keeping every PLANE (Rod Below Bottom Nut is chained from the
    bottom nut's plane) with no washer / nut face locked to it."""
    kept = [p for p in parts if not is_hardware(str(p.get("name") or ""))]
    if len(kept) == len(parts):
        raise NestedHardwareError("the trapeze has no washer or nut parts to nest")
    d2 = None
    if drives is not None:
        d2 = []
        for spec in drives:
            s = dict(spec)
            fol = s.get("follow")
            if fol:
                fol = dict(fol)
                fol["followers"] = [f for f in fol["followers"] if not is_hardware(f["part"])]
                s["follow"] = fol
            d2.append(s)
    h2 = None
    if heights is not None:
        h2 = []
        for spec in heights:
            s = dict(spec)
            s["parts"] = {n: f for n, f in (spec.get("parts") or {}).items()
                          if not is_hardware(n)}
            h2.append(s)
    return kept, d2, h2


def hardware_positions(v: Dict[str, float]) -> Dict[str, List[Tuple[Tuple[float, float, float], str]]]:
    """``{"washer": [(origin, side)], "nut": [...]}`` -- every washer / nut the
    solid trapeze draws, as the ORIGIN of a nested instance (its centre, at
    its bottom face) and the rod side ('lo' / 'hi') it sits on, in the solid
    builder's order (tier, side, below / above)."""
    from .archetypes import _trapeze_geometry
    g = _trapeze_geometry(v)
    out: Dict[str, List[Tuple[Tuple[float, float, float], str]]] = {"washer": [], "nut": []}
    for i in range(g["n"]):
        z0 = i * g["t"]
        for side, x in (("lo", -g["spacing"] / 2.0), ("hi", g["spacing"] / 2.0)):
            out["washer"].append(((x, 0.0, z0 - g["wt"]), side))
            out["nut"].append(((x, 0.0, z0 - g["wt"] - g["nut_h"]), side))
            out["washer"].append(((x, 0.0, z0 + g["H"]), side))
            out["nut"].append(((x, 0.0, z0 + g["H"] + g["wt"]), side))
    return out


# ---------------------------------------------------------------------------
# the two children: our own generated families, with real drives
# ---------------------------------------------------------------------------

def _child_doc(name: str, start_id: int):
    return SK.new_family_document("generic_model", name, work_plane_based=False,
                                  start_id=start_id, plane_length_ft=1.0)


def _finish(doc, kind: str, stem: str, subject: str, forms) -> "F.FamilyProduct":
    from . import drive_law as DL
    doc.born_drive_law = True
    doc.finalize()
    DL.apply_born_inplane_law(doc)
    prod = F.FamilyProduct("generic_model", doc, F.FactSheet(subject=subject),
                           forms=list(forms), file_stem=stem)
    prod.kind = kind
    return prod


def make_washer(start_id: int, *, size_ft: float, thickness_ft: float,
                name: str = WASHER_FAMILY) -> "F.FamilyProduct":
    """A square washer centred on the origin, bottom face on the Level, whose
    INSTANCE parameters drive it: ``Washer Size`` the width in x and in y
    (symmetric about the origin planes), ``Washer Thickness`` the height."""
    from . import drive_law as DL
    from . import height_law as HL
    doc = _child_doc(name, start_id)
    fb = F.add_generic_part(doc, {"shape": "box", "name": "washer", "width_ft": size_ft,
                                  "depth_ft": size_ft, "height_ft": thickness_ft,
                                  "center": [0.0, 0.0], "base_z_ft": 0.0})
    for d in ("Width", "Depth", "Height"):
        doc.add_family_parameter(d, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS)
    size = doc.add_family_parameter("Washer Size", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                    is_instance=True, default=size_ft)
    thk = doc.add_family_parameter("Washer Thickness", SK.SPEC_LENGTH,
                                   SK.PGROUP_DIMENSIONS, is_instance=True,
                                   default=thickness_ft)
    doc.add_type(name, {doc.params["Width"].elem_id: size_ft,
                        doc.params["Depth"].elem_id: size_ft,
                        doc.params["Height"].elem_id: thickness_ft,
                        size.elem_id: size_ft, thk.elem_id: thickness_ft,
                        "description": "square strut washer (nominal, generated)"})
    sk = next(e for e in fb.elements if e.class_name == "VarSketch")
    ex = next(e for e in fb.elements if e.class_name == "ExtrusionElem")
    h = size_ft / 2.0
    for axis in ("x", "y"):
        base = DL.wire_linear_drive(doc, caption="Washer Size", axis=axis, lo=-h, hi=h,
                                    targets=[(sk, ("lo", "hi"))])
        DL.wire_symmetric(doc, base, axis)
    HL.wire_height_drive(doc, caption="Washer Thickness", lo_z=0.0, hi_z=thickness_ft,
                         targets=[(ex, ("start", "end"))])
    doc.notes.append("nested-hardware child (#917): Washer Size drives the width in x "
                     "and y, Washer Thickness the height; no desktop verdict")
    return _finish(doc, "nested_washer", "square_strut_washer",
                   f"square strut washer {size_ft / IN:g} in x {thickness_ft / IN:g} in", [fb])


def make_hex_nut(start_id: int, *, across_flats_ft: float, height_ft: float,
                 name: str = NUT_FAMILY) -> "F.FamilyProduct":
    """A hex nut centred on the origin, bottom face on the Level, two flats
    square to x.  ``Nut Height`` (instance) drives its height; ``Nut Across
    Flats`` (instance) carries the value only -- no verified mechanism resizes
    a hexagon, so it is not wired to the geometry."""
    from . import height_law as HL
    from .archetypes import _hex_nut
    doc = _child_doc(name, start_id)
    part = _hex_nut("nut", across_flats_ft, height_ft, 0.0, 0.0, 0.0)
    fb = F.add_generic_part(doc, part)
    for d in ("Width", "Depth", "Height"):
        doc.add_family_parameter(d, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS)
    af = doc.add_family_parameter("Nut Across Flats", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                  is_instance=True, default=across_flats_ft)
    nh = doc.add_family_parameter("Nut Height", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                  is_instance=True, default=height_ft)
    corner = across_flats_ft / 3.0 ** 0.5 * 2.0
    doc.add_type(name, {doc.params["Width"].elem_id: across_flats_ft,
                        doc.params["Depth"].elem_id: corner,
                        doc.params["Height"].elem_id: height_ft,
                        af.elem_id: across_flats_ft, nh.elem_id: height_ft,
                        "description": "hex nut (nominal, generated)"})
    ex = next(e for e in fb.elements if e.class_name == "ExtrusionElem")
    HL.wire_height_drive(doc, caption="Nut Height", lo_z=0.0, hi_z=height_ft,
                         targets=[(ex, ("start", "end"))])
    doc.notes.append("nested-hardware child (#917): Nut Height drives the height; Nut "
                     "Across Flats carries a value only (a hexagon has no verified "
                     "resize mechanism); no desktop verdict")
    return _finish(doc, "nested_nut", "hex_nut",
                   f"hex nut {across_flats_ft / IN:g} in across flats", [fb])


# ---------------------------------------------------------------------------
# the product: the stripped trapeze that nests its hardware when written
# ---------------------------------------------------------------------------

def _follow_planes(prod) -> Tuple[int, int]:
    for d in getattr(prod, "drives", None) or []:
        fol = d.get("follow") if isinstance(d, dict) else None
        if fol and len(fol.get("planes") or []) == 2:
            return int(fol["planes"][0]), int(fol["planes"][1])
    raise NestedHardwareError("the Rod Inset follow planes were not wired: the nested "
                              "washers and nuts would have nothing to lock to")


class NestedHardwareProduct(F.FamilyProduct):
    """A :class:`FamilyProduct` whose :meth:`write` nests the hardware into the
    written trapeze (two ``nest_family`` passes) and, if that fails for any
    reason, writes the SOLID trapeze instead with the reason noted (hard rule
    1).  ``nested`` holds the outcome of the last write."""

    @classmethod
    def adopt(cls, prod, *, values: Dict[str, float],
              solid: Callable[[], Any]) -> "NestedHardwareProduct":
        obj = cls.__new__(cls)
        obj.__dict__.update(prod.__dict__)
        obj.hardware_values = dict(values)
        obj.solid_fallback = solid
        obj.nested = None
        obj.rod_planes = _follow_planes(prod)
        from . import drive_law as DL
        obj.fb_plane = int(DL.origin_centre_plane(prod.doc, "y").elem_id)
        return obj

    def nest_plan(self) -> Dict[str, Any]:
        """The two nests: points, locks and associations per child."""
        from .archetypes import _trapeze_geometry
        g = _trapeze_geometry(self.hardware_values)
        pos = hardware_positions(self.hardware_values)
        lo, hi = self.rod_planes
        plan = {}
        for key, make, assoc in (
                ("washer", lambda sid: make_washer(sid, size_ft=float(
                    self.hardware_values["washer_size_in"]) * IN, thickness_ft=g["wt"]),
                 WASHER_ASSOCIATIONS),
                ("nut", lambda sid: make_hex_nut(sid, across_flats_ft=g["nut_af"],
                                                 height_ft=g["nut_h"]),
                 NUT_ASSOCIATIONS)):
            pts = [p for p, _s in pos[key]]
            locks = []
            for k, (_p, side) in enumerate(pos[key]):
                locks.append((k, "center_lr", lo if side == "lo" else hi))
                locks.append((k, "center_fb", self.fb_plane))
            plan[key] = {"child": make, "points": pts, "locks": locks,
                         "associate": dict(assoc)}
        return plan

    def write(self, path: str, *, validate: bool = True, provenance: bool = True,
              timestamp: Optional[int] = 0, report_path: Optional[str] = None
              ) -> Dict[str, Any]:
        from . import nest as N
        from ..frontdoor import standalone as SA
        work = tempfile.mkdtemp(prefix="tekton_nest_")
        try:
            try:
                host = os.path.join(work, "host.rfa")
                hrep = F.FamilyProduct.write(self, host, validate=validate,
                                             provenance=False, timestamp=timestamp,
                                             report_path=os.path.join(work, "host.json"))
                if not hrep.get("ok"):
                    raise NestedHardwareError(f"the stripped trapeze host did not verify: "
                                              f"{hrep.get('validate')}")
                plan = self.nest_plan()
                mid = os.path.join(work, "with_washers.rfa")
                rw = N.nest_family(host, mid, plan["washer"]["child"],
                                   plan["washer"]["points"], validate=validate,
                                   locks=plan["washer"]["locks"],
                                   associate=plan["washer"]["associate"])
                os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
                rn = N.nest_family(mid, path, plan["nut"]["child"], plan["nut"]["points"],
                                   validate=validate, locks=plan["nut"]["locks"],
                                   associate=plan["nut"]["associate"])
            except Exception as exc:                          # noqa: BLE001 -- hard rule 1
                return self._deliver_solid(path, exc, validate=validate,
                                           provenance=provenance, timestamp=timestamp,
                                           report_path=report_path)
        finally:
            shutil.rmtree(work, True)
        self.nested = {"ok": True, "washer": rw.as_json(), "nut": rn.as_json()}
        self.nested["washer"]["out_path"] = None             # a temp file, gone
        notes = [
            f"NESTED HARDWARE (#917, opt-in): {len(rw.instance_ids)} washers "
            f"({rw.family_name!r}) and {len(rn.instance_ids)} hex nuts "
            f"({rn.family_name!r}) are nested family instances of our own generated "
            f"families, not solids; {len(rw.lock_ids) + len(rn.lock_ids)} centre-"
            "reference locks (Center (Left/Right) to the Rod Inset planes, Center "
            "(Front/Back) to the origin plane)",
            "nested washer: Washer Size drives its width in x and y and Washer "
            "Thickness its height (instance parameters, associated to the host's); "
            "nested nut: Nut Across Flats is associated but carries a VALUE ONLY "
            "(a hexagon has no verified resize mechanism), Nut Height drives its "
            "height but has no host parameter to follow",
            "the nested washers and nuts do NOT follow the host's height drives "
            "(Tier Spacing, Strut Height, Washer Thickness move the host's planes, "
            "not the instances): our children carry no Center (Elevation) "
            "reference to lock -- the solid version (the default) does ride them",
            "no desktop-Revit verdict exists for nested families, their locks or "
            "their associations (hard rule 4); validator green and an empty "
            "constraint-law report are facts about the file"]
        rep: Dict[str, Any] = {"path": path, "family": self.summary(),
                               "facts": self.facts.as_json(),
                               "container_source": hrep.get("container_source"),
                               "container_mode": hrep.get("container_mode"),
                               "nested_hardware": self.nested,
                               "verify": {"ok": True, "host": hrep.get("verify"),
                                          "washer": rw.proofs.get("verify"),
                                          "nut": rn.proofs.get("verify")}}
        rep["family"]["notes"] = list(rep["family"]["notes"]) + notes
        from ..famgen import famdoc_adoc as FA
        from ..objects import decode_memo
        with decode_memo():
            SA._read_back_checks(rep, path, hrep.get("container_source"), FA,
                                 validate=validate, provenance=provenance)
        rep["ok"] = bool((not validate or (rep.get("validate") or {}).get("ok"))
                         and (not provenance or (rep.get("provenance") or {}).get("ok")))
        return _dump(rep, path, report_path)

    def _deliver_solid(self, path: str, exc: BaseException, **kw) -> Dict[str, Any]:
        """Hard rule 1: the nesting failed, so the SOLID trapeze is delivered
        at ``path`` with the reason stated."""
        why = f"{type(exc).__name__}: {str(exc)[:300]}"
        self.nested = {"ok": False, "refused": why}
        solid = self.solid_fallback()
        line = (f"NESTED HARDWARE REFUSED (#917): {why} -- the SOLID trapeze (washers "
                "and nuts drawn as solids) was delivered instead")
        solid.notes.append(line)
        rep = solid.write(path, **kw)
        rep["nested_hardware"] = self.nested
        rep.setdefault("caveats", []).append(line)
        return _dump(rep, path, kw.get("report_path"))


def _dump(rep: Dict[str, Any], path: str, report_path: Optional[str]) -> Dict[str, Any]:
    from .. import _jsonsafe
    rp = report_path or (os.path.splitext(path)[0] + ".json")
    rep.pop("report_path", None)
    with open(rp, "w") as fh:
        _jsonsafe.dump(rep, fh, indent=1)
    rep["report_path"] = rp
    return rep
