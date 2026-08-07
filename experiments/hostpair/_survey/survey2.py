import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document

RST = "samples/rstbasicsampleproject.rvt"
FAM = 1410863
doc = Document.from_file(RST)

# classes of the familyIds row targets + preview + unnamed symbol
ids = list(range(1411267, 1411290)) + [1411406]
rows = {}
for i in ids:
    try:
        cls = doc.class_of(i)
    except Exception:
        cls = None
    rows[i] = cls
print(json.dumps(rows, indent=0))

# every host element whose seq-101 header m_familyId == FAM
mem = {}
for eid in doc.et_by_id:
    try:
        hdr = doc.value(eid, 101) or {}
    except Exception:
        continue
    if hdr.get("m_familyId") == FAM:
        mem[eid] = doc.class_of(eid)
print("HDR-FAMILY MEMBERS:", json.dumps(mem, indent=0))

# the unnamed symbol's flags
v = doc.value(1411406) or {}
print("SYM1411406:", json.dumps({k: v.get(k) for k in ("m_preview","m_active","m_masterId","m_slaveTrackerId","m_ownerInstanceId","m_familyId","m_partitionSurrogateId","m_stretchPrototypeId")}, indent=0))
h = doc.value(1411406, 101) or {}
print("SYM1411406 hdr familyId:", h.get("m_familyId"), "cat:", h.get("m_categoryId"))
v2 = doc.value(1411287) or {}
print("SYM1411287:", json.dumps({k: v2.get(k) for k in ("m_preview","m_active","m_masterId","m_ownerInstanceId","m_hasParamDefValue")}, indent=0))
# preview elem class + value keys
pv = doc.value(1411268)
print("PREVIEW 1411268 class:", doc.class_of(1411268))
if isinstance(pv, dict):
    print("PREVIEW keys:", sorted(pv.keys())[:40])
