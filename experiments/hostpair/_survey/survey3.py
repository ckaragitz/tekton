import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document

RST = "samples/rstbasicsampleproject.rvt"
FAM = 1410863
doc = Document.from_file(RST)

# native instances of the family's symbols
inst = []
for iid in doc.ids_of_class("FamilyInstance"):
    v = doc.value(iid) or {}
    if v.get("m_symbolId") in (1411287, 1411406):
        inst.append({"id": iid, "symbol": v.get("m_symbolId"), "phase": v.get("m_createdPhaseId")})
print("NATIVE INSTANCES:", json.dumps(inst[:10]), "count", len(inst))

# who references 1411406 / slave symbols across file
slaves = []
for sid in doc.ids_of_class("FamilySymbol"):
    v = doc.value(sid) or {}
    if v.get("m_masterId", -1) != -1:
        slaves.append((sid, v.get("m_masterId"), v.get("m_familyId")))
print("ALL SLAVE SYMBOLS:", slaves[:20], "count", len(slaves))

# family header
hdr = doc.value(FAM, 101) or {}
par = ((hdr.get("m_parents") or {}).get("value") or {})
print("FAMILY hdr deletion:", par.get("m_deletion"))
print("FAMILY hdr regenOnly:", par.get("m_regenOnly"))
print("FAMILY hdr keys:", sorted(hdr.keys()))
print("FAMILY hdr flags:", hdr.get("m_abFlags4Bytes"), "cat", hdr.get("m_categoryId"), "famId", hdr.get("m_familyId"))
# symbol header
sh = doc.value(1411287, 101) or {}
sp = ((sh.get("m_parents") or {}).get("value") or {})
print("SYMBOL hdr deletion:", sp.get("m_deletion"))
print("SYMBOL hdr regenOnly:", sp.get("m_regenOnly"))
print("SYMBOL hdr flags:", sh.get("m_abFlags4Bytes"), "cat", sh.get("m_categoryId"))
# surrogate header, legend header
for i in (1411267, 1411268, 1411288, 1411406):
    h = doc.value(i, 101) or {}
    p = ((h.get("m_parents") or {}).get("value") or {})
    print(f"hdr {i} {doc.class_of(i)}: flags", h.get("m_abFlags4Bytes"), "deletion", p.get("m_deletion"), "regenOnly", p.get("m_regenOnly"))
