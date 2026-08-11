"""PROOF-ONLY round 4: is the CACHED B-REP what Revit draws? (#591)

Rounds 1-3 changed the sketch three different ways and Revit drew the same flat
disc every time:

  R1  SketchPlane bound to a vertical RefPlane        -> no change
  R2  ExtrusionElem.m_alwaysRefPlaneNorm = True       -> no change
  R3  OnDatumPlaneRef.m_vecInPlane set properly       -> no change

Three negatives with one shape between them: nothing in the SKETCH moves the
geometry.  And `cyl_surf` hard-writes m_zVec = [0, 0, 1], so every cylinder we
have ever authored declares a VERTICAL axis in world coordinates inside its
cached B-rep -- which would explain all three at once, if the B-rep is what
renders.

R4 rotates ONLY the cached B-rep (positions and directions together, 90 deg
about X) and leaves the sketch exactly as it was.

  R4 shows a cylinder LYING ON ITS SIDE -> the B-rep drives the display. Wheels
     are reachable today, and the parametric side must then be made to agree or
     the form regenerates back to vertical on the first edit -- a trade to
     measure next, not to assume.
  R4 still shows a flat disc -> the B-rep does not drive it either, and the
     honest conclusion is that the form's direction is fixed by the element kind
     itself: RevolutionElem (and, for a sphere, SphereData) is the only road.

R0 remains the control.
"""
import os, json
from rvt.famgen import geometry as G, skeleton as SK, factory as F
from rvt.frontdoor import famspec as FS

OUT = os.path.dirname(os.path.abspath(__file__))
ROT_X90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]   # z axis -> +y

prod = F.make_generic_model(parts=[{"shape": "cylinder", "radius_ft": 1.72,
                                    "height_ft": 0.95}],
                            name="R4 Wheel Rotated Brep")
doc = prod.doc
rotated = 0
for e in doc.elements:
    if e.class_name == "ExtrusionElem" and e.rep is not None:
        G.rotate_rep(e.rep, ROT_X90, pivot=(0.0, 0.0, 0.475))
        rotated += 1
path = os.path.join(OUT, "R4_wheel_rotated_brep.rfa")
rep = FS.write(prod, path, report_path=os.path.join(OUT, "R4_wheel_rotated_brep.report.json"))
v = (rep.get("validate") or {}); v = v.get("family_mode") or v
print(f"  R4_wheel_rotated_brep  reps rotated={rotated}  {v.get('verdict')} "
      f"{v.get('n_errors')} err  {os.path.getsize(path)//1024} KB")
with open(os.path.join(OUT, "r4.json"), "w") as fh:
    json.dump({"stamp": "PROOF-ONLY", "round": 4,
               "question": "does the cached B-rep drive what Revit draws",
               "reps_rotated": rotated, "verdict": v.get("verdict"),
               "errors": v.get("n_errors")}, fh, indent=1)
