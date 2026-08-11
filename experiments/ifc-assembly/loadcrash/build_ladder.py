"""PROOF-ONLY probe ladder: isolate WHY Revit's Insert > Load Family crashes.

One variable at a time, same emit path (rvt.frontdoor.famspec) for every rung,
so the only difference between L1 and L2 is the NUMBER OF SOLIDS.
"""
import os, json
from rvt.frontdoor import famspec as FS
from rvt.ifc.assembly_parts import read_assembly

OUT = "experiments/ifc-assembly/loadcrash"
IFC = os.environ.get("LADDER_IFC", "")   # the trapeze-hanger IFC (not in the repo)
os.makedirs(OUT, exist_ok=True)
rows = []
if not IFC or not os.path.isfile(IFC):
    raise SystemExit("set LADDER_IFC=<path to the multi-product IFC> first "
                     "(L0 needs no IFC; L1/L1b/L2 measure one)")

def emit(stem, kw):
    prod = FS.build("generic_model", kw)
    path = os.path.join(OUT, stem + ".rfa")
    rep = FS.write(prod, path, report_path=os.path.join(OUT, stem + ".report.json"))
    v = rep.get("validate") or {}
    v = v.get("family_mode") or v
    n = len(kw.get("parts") or []) or 1
    rows.append({"rung": stem, "solids": n, "bytes": os.path.getsize(path),
                 "verdict": v.get("verdict"), "errors": v.get("n_errors"),
                 "provenance_ok": (rep.get("provenance") or {}).get("ok")})
    print(f"  {stem:28s} solids={n:4d}  {os.path.getsize(path)//1024:4d} KB  "
          f"{v.get('verdict')} {v.get('n_errors')} err")

# L0 -- the floor: one box, nothing to do with the IFC at all
emit("L0_one_box", {"width_ft": 1.0, "depth_ft": 1.0, "height_ft": 1.0,
                    "name": "L0 One Box"})

# L1 -- the hanger with decomposition OFF: 13 solids, one per IFC product
m13 = read_assembly(IFC, decompose=False)
emit("L1_hanger_13_solids", {"parts": m13.to_parts(), "name": "L1 Hanger 13 Solids",
                             "source": "IFC mesh (decompose off)"})

# L2 -- the hanger as shipped: 103 solids.  ONLY difference from L1.
m103 = read_assembly(IFC, decompose=True)
emit("L2_hanger_103_solids", {"parts": m103.to_parts(), "name": "L2 Hanger 103 Solids",
                              "source": "IFC mesh (decompose on)"})

# L1b -- 13 solids but ONLY the two struts+caps (the axis-aligned ones), 4 solids
sub = [p for p in m13.parts if "Strut" in p.name or "End Cap" in p.name]
emit("L1b_four_solids", {"parts": [p.to_part() for p in sub],
                         "name": "L1b Four Solids", "source": "IFC mesh (subset)"})

with open(os.path.join(OUT, "ladder.json"), "w") as fh:
    json.dump({"stamp": "PROOF-ONLY", "rows": rows}, fh, indent=1)
print("\nladder.json written")
