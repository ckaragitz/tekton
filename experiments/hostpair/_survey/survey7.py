import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document
from rvt.families import FamilyIndex
from rvt import adocument as A
from rvt.container import open_rvt

RST = "samples/rstbasicsampleproject.rvt"
CLUSTER = [1410863, 1411267, 1411268] + list(range(1411269, 1411285)) + [1411287, 1411288, 1411406]
doc = Document.from_file(RST)
idx = FamilyIndex(RST)
unit_ids = set(idx.unit_records(36).get(102, {}))
print("cluster∩unit36:", sorted(set(CLUSTER) & unit_ids))

# ETD row for -2001330
with open_rvt(RST) as f:
    a = A.decode_latest(f.inflate("Global/Latest"))
mgr = (a.value.get("m_pAppInfoManager") or {}).get("value") or {}
for slot in mgr.get("m_appInfoArr") or []:
    if isinstance(slot, dict) and slot.get("ptr_class") == "ElementTrackingData":
        arr = (slot.get("value") or {}).get("m_symbols") or []
        for row in arr:
            if row.get("m_categoryId") == -2001330:
                s = row.get("m_elemIdSet") or []
                print("ETD -2001330 row:", len(s), "ids; has 1411287:", 1411287 in s, "has 1411406:", 1411406 in s)
                break
        else:
            print("ETD: no -2001330 row; categories:", [r.get("m_categoryId") for r in arr][:20])

# session hex across twins of OTHER families
import re
sess = {}
for tid in doc.ids_of_class("ParamElemFamily"):
    v = doc.value(tid) or {}
    pd = ((v.get("m_pParamDef") or {}).get("value") or {})
    tt = pd.get("m_typeId")
    t = tt.get("m_typeId") if isinstance(tt, dict) else tt
    if isinstance(t, str) and t.startswith("revit.local.family:"):
        m = re.match(r"revit\.local\.family:([0-9a-f]{32})([0-9a-f]{8})-", t)
        if m:
            sess.setdefault(m.group(1), []).append((tid, int(m.group(2), 16), v.get("m_famId")))
print("session hex groups:", len(sess))
for k, v in list(sess.items())[:8]:
    print(" ", k, "n =", len(v), "sample:", v[:3])
