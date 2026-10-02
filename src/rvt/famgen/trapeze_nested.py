"""rvt.famgen.trapeze_nested -- the strut trapeze with its washers and nuts as
NESTED families (issue #917 DONE 5; heights #940), opt-in:
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
  drives its height (Case B), and whose instance parameter ``Nut Across Flats``
  drives the hexagon (#948) through ``Nut Half Across Flats`` (= Nut Across
  Flats / 2): the Revit-born hexagon recipe of :mod:`rvt.famgen.angular_law`
  (five locked 60-degree angular dimensions, three EQ dimensions about the
  origin planes, three labelled dimensions; one born element substituted,
  stated there).  The hexagon is drawn in the census orientation (flats square
  to y), 90 degrees from the solid trapeze's nut.

Both children carry their origin elevation plane (the template's horizontal
plane at z 0, the parts' bottom face) with Is-Reference **Center (Elevation)**
(``m_refName`` 7), the born form of a child whose instances are locked by
height (#940 census: 61 / 61 born child documents with a code-7 plane carry it
on their origin elevation plane at z 0, unnamed, drawn; 1,299 others leave that
plane "Not a Reference" (12), which no lock can name).

Per tier and rod, a washer + nut below the channel back and a washer + nut on
the lips (the same positions the solid version draws), each instance locked
THREE ways: its Center (Left/Right) to the Rod Inset plane of its rod (the
planes ``drive_law.wire_follow`` creates), its Center (Front/Back) to the
origin Center (Front/Back) plane, and (#940) its Center (Elevation) to the host
HORIZONTAL plane its bottom face sits on -- the plane the trapeze's height
chain (Tier Spacing / Strut Height / Washer Thickness, #787 Case B) already
places there and the solid version locks that part's face to.  The host's
``Washer Size`` / ``Washer Thickness`` / ``Nut Across Flats`` are associated
to the children's instance parameters (a host TYPE parameter driving a nested
INSTANCE parameter: 2,087 born entries).

#940 census (421 born families, every own nested instance; counts only): a
nested part follows a host HEIGHT by an ``Alignment`` lock of one of its
references to a horizontal host plane in 1,203 instances -- the dominant
mechanism -- against 480 hosted on a SketchPlane over a horizontal RefPlane,
13 labelled ``LinearDimString``s to a horizontal plane and 20 offset built-in
parameter associations.  CG8 judges 467 born elevation locks (tags 1 / 4 on
rotated instances, 6, 7), all holding; for an UNROTATED free instance, the
placement this lane uses, the lockable horizontal reference is the child's
Center (Elevation) (9 locks) or Bottom (1); named references (614 locks) map
through the symbol's geometry table and stay unresolved.

What this lane does NOT do (stated in the product's notes, never hidden):

* nothing here has a desktop-Revit verdict (hard rule 4): validator green, an
  empty constraint-law report with every nested lock judged by CG8 and every
  hexagon angle / EQ / label judged by CG9 / CG10, and coherent registries are
  facts about the file -- whether Revit's solver moves a locked nested instance
  when Tier Spacing changes, or regenerates the nut's hexagon when Nut Across
  Flats changes, is unverified.  That is why the solid version stays the
  DEFAULT (#948 record: the decision and its reason).

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
#: the nut's formula parameter its hexagon's dimensions carry (#948; born: one
#: instance formula parameter labels the hexagon, 32 / 32)
NUT_HALF_ACROSS_FLATS = "Nut Half Across Flats"

#: Is-Reference code of the children's origin elevation plane (#940): Center
#: (Elevation), the code a born child carries when its instances are locked
#: by height (skeleton.REF_NAME)
CENTER_ELEVATION = SK.REF_NAME["center_elevation"]
#: a host horizontal plane at the instance's bottom face (feet)
Z_TOL = 1e-9


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

def origin_elevation_reference(doc) -> int:
    """Give the child's origin elevation plane (the template's horizontal
    plane at z 0 that ``height_law.wire_height_drive`` adds, drawn,
    origin-defining) the Is-Reference code Center (Elevation), so a host can
    lock an instance's height to it (#940).  Returns the plane id; refuses
    unless exactly one such plane exists."""
    from . import constraint_law as CL
    hits = []
    for rp in doc.refplanes:
        o = rp.obj or {}
        if not o.get("m_definesOrigin"):
            continue
        pl = CL.plane_of_any("RefPlane", o)
        if pl is None or abs(abs(pl[1][2]) - 1.0) > CL.PARALLEL_TOL or abs(pl[0][2]) > Z_TOL:
            continue
        hits.append(rp)
    if len(hits) != 1:
        raise NestedHardwareError(f"the child has {len(hits)} horizontal origin planes at z 0; "
                                  "its Center (Elevation) needs exactly one")
    hits[0].obj["m_refName"] = CENTER_ELEVATION
    return hits[0].elem_id


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
    origin_elevation_reference(doc)
    doc.notes.append("nested-hardware child (#917): Washer Size drives the width in x "
                     "and y, Washer Thickness the height; its bottom face's origin "
                     "plane is its Center (Elevation) reference (#940); no desktop "
                     "verdict")
    return _finish(doc, "nested_washer", "square_strut_washer",
                   f"square strut washer {size_ft / IN:g} in x {thickness_ft / IN:g} in", [fb])


def hex_ring(across_flats_ft: float) -> List[List[float]]:
    """The nut's hexagon in the census orientation (#948): flats square to y,
    the ring starting at the 300-degree corner and running counter-clockwise,
    so its six sketch lines are the born H0 .. H5 (bottom-right slant first,
    bottom flat last) that :func:`angular_law.hexagon_roles` reads."""
    import math
    r = across_flats_ft / math.sqrt(3.0)              # centre to corner = the side
    ring = [[r * math.cos(math.radians(a)), r * math.sin(math.radians(a))]
            for a in (300, 0, 60, 120, 180, 240)]
    ring.append(list(ring[0]))
    return ring


def make_hex_nut(start_id: int, *, across_flats_ft: float, height_ft: float,
                 name: str = NUT_FAMILY) -> "F.FamilyProduct":
    """A hex nut centred on the origin, bottom face on the Level, two flats
    square to y (the census orientation, #948).  ``Nut Height`` (instance)
    drives its height; ``Nut Across Flats`` (instance) drives the hexagon
    through ``Nut Half Across Flats`` (= Nut Across Flats / 2), which labels
    the born recipe's dimensions (:func:`angular_law.wire_hexagon_drive`: five
    locked 60-degree angles, three EQs, three labels).  If that wiring is
    refused the nut is still built and the across-flats carries a value only,
    said in the notes."""
    from . import angular_law as AL
    from . import height_law as HL
    doc = _child_doc(name, start_id)
    part = {"shape": "polygon", "name": "nut", "vertices": hex_ring(across_flats_ft),
            "height_ft": height_ft, "center": [0.0, 0.0], "base_z_ft": 0.0}
    fb = F.add_generic_part(doc, part)
    for d in ("Width", "Depth", "Height"):
        doc.add_family_parameter(d, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS)
    af = doc.add_family_parameter("Nut Across Flats", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                  is_instance=True, default=across_flats_ft)
    half = doc.add_family_parameter(NUT_HALF_ACROSS_FLATS, SK.SPEC_LENGTH,
                                    SK.PGROUP_DIMENSIONS, is_instance=True,
                                    formula="Nut Across Flats / 2",
                                    default=across_flats_ft / 2.0)
    nh = doc.add_family_parameter("Nut Height", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                  is_instance=True, default=height_ft)
    corner = across_flats_ft / 3.0 ** 0.5 * 2.0
    doc.add_type(name, {doc.params["Width"].elem_id: corner,
                        doc.params["Depth"].elem_id: across_flats_ft,
                        doc.params["Height"].elem_id: height_ft,
                        af.elem_id: across_flats_ft, half.elem_id: across_flats_ft / 2.0,
                        nh.elem_id: height_ft,
                        "description": "hex nut (nominal, generated)"})
    sk = next(e for e in fb.elements if e.class_name == "VarSketch")
    ex = next(e for e in fb.elements if e.class_name == "ExtrusionElem")
    try:
        hexd = AL.wire_hexagon_drive(doc, sketch=sk, caption="Nut Across Flats",
                                     half_caption=NUT_HALF_ACROSS_FLATS)
    except AL.AngularLawError as exc:                 # all-or-nothing: doc untouched
        hexd = None
        doc.notes.append(f"Nut Across Flats carries a VALUE ONLY: the hexagon drive was "
                         f"refused ({exc})")
    HL.wire_height_drive(doc, caption="Nut Height", lo_z=0.0, hi_z=height_ft,
                         targets=[(ex, ("start", "end"))])
    origin_elevation_reference(doc)
    doc.hexagon_drive = hexd
    if hexd is not None:
        doc.notes.append(
            "nested-hardware child (#917, #948): Nut Height drives the height; Nut "
            "Across Flats drives the hexagon across flats through Nut Half Across "
            "Flats (= Nut Across Flats / 2) with the Revit-born hexagon recipe: 5 "
            "locked 60-degree angular dimensions, 3 EQ dimensions about the origin "
            "planes, 3 labelled dimensions (the born secret-style corner pin is "
            "substituted by a second labelled slant, stated); its bottom face's "
            "origin plane is its Center (Elevation) reference; no desktop verdict "
            "(hard rule 4)")
    else:
        doc.notes.append("nested-hardware child (#917): Nut Height drives the height; "
                         "its bottom face's origin plane is its Center (Elevation) "
                         "reference; no desktop verdict")
    return _finish(doc, "nested_nut", "hex_nut",
                   f"hex nut {across_flats_ft / IN:g} in across flats", [fb])


# ---------------------------------------------------------------------------
# the product: the stripped trapeze that nests its hardware when written
# ---------------------------------------------------------------------------

def height_planes(doc, zs) -> Dict[float, int]:
    """``{z: plane id}`` -- for every height in ``zs`` the ONE horizontal host
    RefPlane through it (the height chain's planes, #787 Case B).  Refuses
    when a height has none or several: an elevation lock must name its plane
    unambiguously (#940)."""
    from . import constraint_law as CL
    horizontal = []
    for rp in doc.refplanes:
        pl = CL.plane_of_any("RefPlane", rp.obj or {})
        if pl is not None and abs(abs(pl[1][2]) - 1.0) <= CL.PARALLEL_TOL:
            horizontal.append((int(rp.elem_id), float(pl[0][2])))
    out: Dict[float, int] = {}
    for z in zs:
        hits = [pid for pid, pz in horizontal if abs(pz - z) <= Z_TOL]
        if len(hits) != 1:
            raise NestedHardwareError(
                f"{len(hits)} horizontal host planes at z {z * 12.0:.6g} in: a nested "
                "instance's Center (Elevation) needs exactly one plane to lock to")
        out[z] = hits[0]
    return out


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
        pos = hardware_positions(values)
        obj.z_planes = height_planes(prod.doc, sorted({o[2] for k in pos for o, _s in pos[k]}))
        return obj

    def _nut_child(self, start_id: int, g: Dict[str, float]):
        """The hex nut child, remembering whether its hexagon drive was wired
        (#948) so the delivered notes say what the nested nut does."""
        prod = make_hex_nut(start_id, across_flats_ft=g["nut_af"], height_ft=g["nut_h"])
        self.nut_hexagon_drive = getattr(prod.doc, "hexagon_drive", None)
        return prod

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
                ("nut", lambda sid: self._nut_child(sid, g), NUT_ASSOCIATIONS)):
            pts = [p for p, _s in pos[key]]
            locks = []
            for k, (p, side) in enumerate(pos[key]):
                locks.append((k, "center_lr", lo if side == "lo" else hi))
                locks.append((k, "center_fb", self.fb_plane))
                # #940: the bottom face follows the host's height chain
                locks.append((k, "center_elevation", self.z_planes[p[2]]))
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
            "(Front/Back) to the origin plane, Center (Elevation) -- each part's "
            "bottom face -- to the host horizontal plane the height chain puts "
            "there, #940)",
            "nested washer: Washer Size drives its width in x and y and Washer "
            "Thickness its height (instance parameters, associated to the host's); "
            + ("nested nut: Nut Across Flats is associated and drives the hexagon "
               "across flats (#948: the Revit-born recipe -- 5 locked 60-degree "
               "angular dimensions, 3 EQ and 3 labelled dimensions of Nut Half "
               "Across Flats = Nut Across Flats / 2, the born secret-style corner "
               "pin substituted by a second labelled slant; no desktop verdict)"
               if getattr(self, "nut_hexagon_drive", None) else
               "nested nut: Nut Across Flats is associated but carries a VALUE ONLY "
               "(its hexagon drive was refused)")
            + ", Nut Height drives its height but has no host parameter to follow",
            "the nested washers and nuts are LOCKED to the host's height planes "
            "(Tier Spacing, Strut Height and Washer Thickness move those planes); "
            "whether Revit moves a locked nested instance with them is unverified "
            "(no desktop verdict)",
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
        try:
            with decode_memo():
                SA._read_back_checks(rep, path, hrep.get("container_source"), FA,
                                     validate=validate, provenance=provenance)
        except Exception as exc:                              # noqa: BLE001 -- hard rule 1
            # the nested file is already at ``path``: a crashing read-back is
            # stamped on the report, never raised past the delivery (#939 review)
            rep["read_back_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            rep.setdefault("caveats", []).append(
                "the delivered file's read-back checks crashed and were not completed")
        rep["ok"] = bool("read_back_error" not in rep
                         and (not validate or (rep.get("validate") or {}).get("ok"))
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
