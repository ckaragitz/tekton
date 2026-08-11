"""PROOF-ONLY, ROUND 1: can a form extrude along a VERTICAL reference plane's
normal, so a wheel is a true cylinder instead of a stack of boxes? (#591)

The owner's verdict on the stacked approximation was blunt -- "These circle
entities need to be a actual sphere, not rectangluar break up" -- and they are
right: slicing a horizontal cylinder in Z gives rectangles no matter how many
slices you take. The roundness is in a plane the contract cannot draw on.

The file's own schema says the format supports the real thing:

    RevolutionElem  <- GenSweep <- Element   (own field: m_sketchId)
    CylSurf   {m_center, m_xVec, m_yVec, m_zVec, m_radius}   -- an explicit AXIS
    ConeSurf  {m_center, m_xVec, m_yVec, m_zVec, m_halfAngle}
    SphereData {m_center, m_rad}   reachable via GeometryVRepImpl.m_sphereDatas

So there are two roads, and this probe walks the cheaper one first:

  R1  a SketchPlane bound to a VERTICAL RefPlane instead of the level datum.
      If Revit accepts it, the profile is drawn on that plane and the form
      extrudes along its normal -- a true horizontal cylinder, and the same
      mechanism gives a strut channel its own C-profile.
  R0  the identical cylinder on the level datum -- the CONTROL that is known
      to load, so an R1 failure cannot be blamed on anything else.

What is NOT yet known, and why this is round 1 of an experiment rather than a
fix: the sketch's 2D frame on a vertical plane (which way u and v point), the
SketchPlane transform that expresses it, and whether the cached B-rep must be
authored in the rotated frame to match. Each is one desktop round away.
"""
import os, json, math
from rvt.famgen import geometry as G, skeleton as SK, factory as F
from rvt.frontdoor import famspec as FS

OUT = os.path.dirname(os.path.abspath(__file__))
rows = []


def write(prod, stem, note):
    path = os.path.join(OUT, stem + ".rfa")
    rep = FS.write(prod, path, report_path=os.path.join(OUT, stem + ".report.json"))
    v = (rep.get("validate") or {}); v = v.get("family_mode") or v
    rows.append({"rung": stem, "note": note, "verdict": v.get("verdict"),
                 "errors": v.get("n_errors"),
                 "provenance_ok": (rep.get("provenance") or {}).get("ok"),
                 "bytes": os.path.getsize(path)})
    print(f"  {stem:20s} {v.get('verdict')} {v.get('n_errors')} err  "
          f"{os.path.getsize(path)//1024:4d} KB  -- {note}")


# R0 -- the control: an ordinary vertical cylinder, known to load
prod = F.make_generic_model(parts=[{"shape": "cylinder", "radius_ft": 1.72,
                                    "height_ft": 0.95}], name="R0 Vertical Cylinder")
write(prod, "R0_vertical_cylinder", "control: cylinder on the level datum (known good)")

# R1 -- the same cylinder, drawn on a VERTICAL RefPlane
doc = SK.new_family_document("generic_model", "R1 Wheel On RefPlane",
                             work_plane_based=False, start_id=1000)
ctx = F.geometry_context(doc)
rp_id = doc.ids.alloc() if hasattr(doc.ids, "alloc") else G._alloc(doc.ids)
rp = SK.new_reference_plane(rp_id, doc.self_family.elem_id, name="Wheel Axis Plane",
                            bubble_end=(0.0, 5.0, 0.0), free_end=(0.0, -5.0, 0.0),
                            normal=(0.0, 0.0, 1.0))
doc.add(rp)
# the wheel profile drawn on that plane; the SketchPlane names the RefPlane as
# its datum and carries the frame that maps the sketch's u/v onto it
id_plane = G._alloc(doc.ids); id_sk = G._alloc(doc.ids)
id_u = G._alloc(doc.ids); id_l = G._alloc(doc.ids); id_ext = G._alloc(doc.ids)
c = G.circle_profile((0.0, 1.72), 1.72)
sp = G.new_sketch_plane(id_plane, ctx, sketch_id=id_sk, datum_id=rp_id,
                        trf3x3=[[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]],
                        origin=[0.0, 0.0, 0.0])
arc_u = G.garc(c.center, c.radius, *G.CircleProfile.ANG_U, tag=0, flags=ctx.gline_flags)
arc_l = G.garc(c.center, c.radius, *G.CircleProfile.ANG_L, tag=1, flags=ctx.gline_flags)
doc.add(sp)
doc.add(G.new_var_sketch_curves(id_sk, ctx, sketch_plane_id=id_plane, user_id=id_ext,
                                curves=[arc_u, arc_l], curve_ids=[id_u, id_l],
                                bbox=[[-1.72, 0.0, 0.0], [1.72, 3.44, 0.0]]))
doc.add(G.new_arc_curve_elem(id_u, ctx, sketch_plane_id=id_plane, sketch_id=id_sk,
                             extrusion_id=id_ext, center=c.center, radius=c.radius,
                             ang0=G.CircleProfile.ANG_U[0], ang1=G.CircleProfile.ANG_U[1],
                             partner_id=id_l, tag=0))
doc.add(G.new_arc_curve_elem(id_l, ctx, sketch_plane_id=id_plane, sketch_id=id_sk,
                             extrusion_id=id_ext, center=c.center, radius=c.radius,
                             ang0=G.CircleProfile.ANG_L[0], ang1=G.CircleProfile.ANG_L[1],
                             partner_id=id_u, tag=0))
doc.add(G.new_cylinder_extrusion(id_ext, ctx, sketch_id=id_sk, sketch_plane_id=id_plane,
                                 circles=[c], start=-0.475, end=0.475, rep=G.REP_SOLID,
                                 material_id=-1, category_id=int(doc.category_id)))
for dim in ("Width", "Depth", "Height"):
    doc.add_family_parameter(dim, F.SPEC["length"], F.GROUP["dimensions"])
doc.add_type("R1 Wheel On RefPlane", {doc.params["Width"].elem_id: 3.44,
                                      doc.params["Depth"].elem_id: 0.95,
                                      doc.params["Height"].elem_id: 3.44,
                                      "description": "wheel drawn on a vertical RefPlane"})
doc.finalize()
write(F.FamilyProduct("generic_model", doc, F.FactSheet(subject="rotate probe"),
                      forms=[], file_stem="r1_wheel_on_refplane"),
      "R1_wheel_on_refplane", "the experiment: profile on a VERTICAL RefPlane")

with open(os.path.join(OUT, "rotate.json"), "w") as fh:
    json.dump({"stamp": "PROOF-ONLY", "round": 1,
               "question": "can a form extrude along a vertical RefPlane's normal",
               "rows": rows}, fh, indent=1)
print("\nrotate.json written")
