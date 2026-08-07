import json, sys, os
sys.path.insert(0, "src")
from rvt.mutate import Document

RST = "samples/rstbasicsampleproject.rvt"
FAM = 1410863
doc = Document.from_file(RST)

fam = doc.value(FAM) or {}
out = {"family_id": FAM, "class": doc.class_of(FAM), "name": fam.get("m_name"),
       "partType": fam.get("m_partType"), "surrogateId": fam.get("m_surrogateId"),
       "famDocGUID": fam.get("m_famDocGUID"), "categoryId? via header": None}
fdoc = ((fam.get("m_oFamDoc") or {}).get("value") or {})
out["contentDocGUID"] = fdoc.get("m_contentDocGUID")
b2s = fdoc.get("m_big2SmallMap2") or []
out["big2small_rows"] = len(b2s)
out["big2small_sample"] = b2s[:6]
out["coreIds"] = fdoc.get("m_coreIds")
ftt = ((fam.get("m_pFamilyTypes") or {}).get("value") or {})
out["type_table_idx"] = ftt.get("m_idx")
out["type_table_names"] = [p.get("name") for p in ftt.get("m_pairs") or []]
fids = (((fam.get("m_familyIds") or {}).get("value") or {}).get("m_data") or [])
out["familyIds_rows"] = len(fids)
out["familyIds"] = fids[:60]

# constellation: symbols, surrogates, twins
syms = []
for sid in doc.ids_of_class("FamilySymbol"):
    v = doc.value(sid) or {}
    if v.get("m_familyId") == FAM:
        syms.append({"id": sid, "name": ((v.get("m_symbolInfo") or {}).get("value") or {}).get("m_name"),
                     "partitionSurrogateId": v.get("m_partitionSurrogateId"),
                     "active": v.get("m_active"),
                     "geomSteps_none": v.get("m_geomSteps") is None,
                     "geomTable_none": v.get("m_pGeomTable") is None})
out["symbols"] = syms

surs = []
for sid in doc.ids_of_class("FamilySurrogate"):
    v = doc.value(sid) or {}
    if v.get("m_elemId") == FAM:
        surs.append({"id": sid, "name": v.get("m_name"), "categoryId": v.get("m_categoryId"),
                     "previewElemId": v.get("m_previewElemId")})
out["family_surrogates"] = surs

ssurs = []
symids = {s["id"] for s in syms}
for sid in doc.ids_of_class("FamSymSurrogate"):
    v = doc.value(sid) or {}
    if v.get("m_elemId") in symids or (surs and v.get("m_famSurrogateId") == surs[0]["id"]):
        ssurs.append({"id": sid, "name": v.get("m_name"), "elemId": v.get("m_elemId"),
                      "famSurrogateId": v.get("m_famSurrogateId")})
out["famsym_surrogates"] = ssurs

twins = []
for tid in doc.ids_of_class("ParamElemFamily"):
    v = doc.value(tid) or {}
    if v.get("m_famId") == FAM:
        pd = ((v.get("m_pParamDef") or {}).get("value") or {})
        tt = pd.get("m_typeId")
        twins.append({"id": tid, "caption": pd.get("m_caption"),
                      "paramElemId": pd.get("m_paramElemId"),
                      "typeId": (tt.get("m_typeId") if isinstance(tt, dict) else tt),
                      "designOptionId": v.get("m_designOptionId")})
out["twins"] = twins
print(json.dumps(out, indent=1, default=str))
