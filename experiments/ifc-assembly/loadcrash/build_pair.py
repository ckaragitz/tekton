"""PROOF-ONLY matched pair: does the Load Family crash come from COUNT or from N-GON parts?

The first ladder was confounded -- L1 (13 solids) had no polygons and L2 (103)
had 14, so its result could not tell the two apart.  These two rungs each hold
ONE thing constant:

  P_boxes103   103 solids, EVERY ONE A BOX    -> count at L2's value, shape mix gone
  P_polys14     14 solids, EVERY ONE AN N-GON -> shape isolated at a count known to load

Read it as:
  boxes103 CRASHES            -> count alone is sufficient; N-gons are not implicated
  boxes103 loads, polys14 CRASHES -> N-gon parts are the cause, not count
  both load                   -> it is the COMBINATION (or something else in L2)
  both crash                  -> two independent causes; treat separately
"""
import os, json, math
from rvt.frontdoor import famspec as FS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
rows = []


def emit(stem, parts, name):
    prod = FS.build("generic_model", {"parts": parts, "name": name,
                                      "source": "synthetic matched pair"})
    path = os.path.join(OUT, stem + ".rfa")
    rep = FS.write(prod, path, report_path=os.path.join(OUT, stem + ".report.json"))
    v = rep.get("validate") or {}
    v = v.get("family_mode") or v
    shapes = sorted({p["shape"] for p in parts})
    rows.append({"rung": stem, "solids": len(parts), "shapes": shapes,
                 "bytes": os.path.getsize(path), "verdict": v.get("verdict"),
                 "errors": v.get("n_errors"),
                 "provenance_ok": (rep.get("provenance") or {}).get("ok")})
    print(f"  {stem:16s} solids={len(parts):4d} shapes={','.join(shapes):8s} "
          f"{os.path.getsize(path)//1024:4d} KB  {v.get('verdict')} {v.get('n_errors')} err")


# --- 103 solids, all boxes: a 0.5 ft grid, nothing exotic ------------------
boxes = []
for i in range(103):
    r, c = divmod(i, 12)
    boxes.append({"shape": "box", "width_ft": 0.4, "depth_ft": 0.4, "height_ft": 0.4,
                  "base_z_ft": 0.0, "center": [c * 0.5, r * 0.5], "name": f"box{i}"})
emit("P_boxes103", boxes, "P Boxes 103")

# --- 14 solids, all N-gons: regular heptagons (7 sides -> polygon, not cylinder)
polys = []
for i in range(14):
    r, c = divmod(i, 5)
    ring = [[c * 1.0 + 0.3 * math.cos(2 * math.pi * k / 7),
             r * 1.0 + 0.3 * math.sin(2 * math.pi * k / 7)] for k in range(7)]
    polys.append({"shape": "polygon", "vertices": ring, "height_ft": 0.4,
                  "base_z_ft": 0.0, "name": f"poly{i}"})
emit("P_polys14", polys, "P Polys 14")

with open(os.path.join(OUT, "pair.json"), "w") as fh:
    json.dump({"stamp": "PROOF-ONLY", "question": "count vs N-gon", "rows": rows}, fh, indent=1)
print("\npair.json written")
