import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document

RST = "samples/rstbasicsampleproject.rvt"
doc = Document.from_file(RST)
for i in (1468016, 311, 245423, 1177727, -1005500):
    try:
        print(i, doc.class_of(i))
    except Exception as e:
        print(i, "NOT IN ELEMTABLE", type(e).__name__)

# symbol 1411287 geometry bookkeeping shapes
v = doc.value(1411287) or {}
gs = v.get("m_geomSteps")
gt = v.get("m_pGeomTable")
print("geomSteps type:", type(gs).__name__, (gs.get("ptr_class") if isinstance(gs, dict) else None))
if isinstance(gs, dict):
    gv = gs.get("value") or {}
    print("geomSteps keys:", sorted(gv.keys()))
    print("geomSteps json size:", len(json.dumps(gv, default=str)))
print("geomTable type:", type(gt).__name__, (gt.get("ptr_class") if isinstance(gt, dict) else None))
if isinstance(gt, dict):
    tv = gt.get("value") or {}
    print("geomTable keys:", sorted(tv.keys()))
    for k, val in tv.items():
        if isinstance(val, list):
            print("  geomTable", k, "len", len(val))
    print("geomTable json size:", len(json.dumps(tv, default=str)))
# seq-103 rep of symbol + legend + slave
from rvt.families import FamilyIndex
# unit-0 reps come via doc? use doc.records maybe. Try doc.value(...,103)
for i in (1411287, 1411406, 1411268):
    try:
        r = doc.value(i, 103)
        cls = None
        if isinstance(r, dict):
            cls = r.get("ptr_class") or ("GElement-shape" if "m_pGNode" in r or "m_nodes" in r else list(r.keys())[:6])
        print("rep", i, type(r).__name__, cls)
    except Exception as e:
        print("rep", i, "ERR", type(e).__name__, str(e)[:80])
