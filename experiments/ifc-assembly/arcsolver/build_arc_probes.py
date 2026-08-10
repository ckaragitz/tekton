"""PROOF-ONLY: does an arc's solver record fix Insert > Load Family, and with
WHICH parameter vector?  (#589)

The structural defect is settled: m_elemRecs was empty while m_curveObjIdxMap
named both arcs, so VarSketch::getCurveObj read out of range and Load Family
died at VarSketch.cpp:634.  What the schema does NOT say is the arc's parameter
layout, so that is the one variable here.

  A5_cylinder   m_params = [cx, cy, r, ang0, ang1]   (the arc's 5 DOF; the
                schema's VarSketchArcEndAngleConstrObj implies the end angles
                ARE parameters)
  A3_cylinder   m_params = [cx, cy, r]               (angles held by the curve
                token alone)
  A0_cylinder   the OLD empty solver -- the control that must still crash

Each family is ONE cylinder and nothing else.  Load Family into a new project:
whichever of A5/A3 loads is the layout; A0 crashing confirms the mechanism
rather than some unrelated change.
"""
import os, json
from rvt.famgen import geometry as G
from rvt.frontdoor import famspec as FS

OUT = os.path.dirname(os.path.abspath(__file__))
rows = []


def emit(stem, layout):
    old = G.ARC_SOLVER_PARAMS
    G.ARC_SOLVER_PARAMS = layout
    try:
        prod = FS.build("generic_model", {
            "parts": [{"shape": "cylinder", "radius_ft": 0.5, "height_ft": 2.0}],
            "name": stem})
        doc = prod.doc
        recs = [len(e.obj.get("m_elemRecs") or []) for e in doc.elements
                if e.class_name == "VarSketch" and e.obj.get("m_absorbedCurves")]
        nparams = [len(r["value"]["m_params"]) for e in doc.elements
                   if e.class_name == "VarSketch"
                   for r in (e.obj.get("m_elemRecs") or [])]
        path = os.path.join(OUT, stem + ".rfa")
        rep = FS.write(prod, path, report_path=os.path.join(OUT, stem + ".report.json"))
        v = rep.get("validate") or {}
        v = v.get("family_mode") or v
        rows.append({"rung": stem, "layout": layout, "elemRecs": recs,
                     "params_per_arc": sorted(set(nparams)),
                     "verdict": v.get("verdict"), "errors": v.get("n_errors")})
        print(f"  {stem:16s} layout={layout:22s} elemRecs={recs} "
              f"params/arc={sorted(set(nparams))}  {v.get('verdict')} {v.get('n_errors')} err")
    finally:
        G.ARC_SOLVER_PARAMS = old


emit("A5_cylinder", "center_radius_angles")
emit("A3_cylinder", "center_radius")

# A0: the control -- restore the pre-fix empty solver for one build
_orig = G._curve_solver_obj
try:
    G._curve_solver_obj = lambda *a, **k: None
    import types
    src = G.new_var_sketch_curves
    def _empty(*a, **k):
        el = src(*a, **k)
        el.obj["m_elemRecs"] = []
        el.obj["m_oGuessCache"]["value"]["m_guessArr"] = []
        return el
    G.new_var_sketch_curves = _empty
    prod = FS.build("generic_model", {"parts": [
        {"shape": "cylinder", "radius_ft": 0.5, "height_ft": 2.0}], "name": "A0_cylinder"})
    path = os.path.join(OUT, "A0_cylinder.rfa")
    rep = FS.write(prod, path, report_path=os.path.join(OUT, "A0_cylinder.report.json"))
    v = (rep.get("validate") or {}); v = v.get("family_mode") or v
    rows.append({"rung": "A0_cylinder", "layout": "EMPTY (pre-fix control)",
                 "elemRecs": [0], "params_per_arc": [], "verdict": v.get("verdict"),
                 "errors": v.get("n_errors")})
    print(f"  {'A0_cylinder':16s} layout={'EMPTY (control)':22s} elemRecs=[0]  "
          f"{v.get('verdict')} {v.get('n_errors')} err")
finally:
    G.new_var_sketch_curves = src
    G._curve_solver_obj = _orig

with open(os.path.join(OUT, "arcprobes.json"), "w") as fh:
    json.dump({"stamp": "PROOF-ONLY", "question": "arc solver parameter layout",
               "rows": rows}, fh, indent=1)
print("\narcprobes.json written")
