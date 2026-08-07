import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document
doc = Document.from_file("samples/rstbasicsampleproject.rvt")
for SID in (876569, 509468):
    r = doc.value(SID, 103) or {}
    v = doc.value(SID) or {}
    print("=== symbol", SID, ((v.get("m_symbolInfo") or {}).get("value") or {}).get("m_name"), "cat", doc.category_of(SID))
    def walkg(node, depth=1):
        if not isinstance(node, dict): return
        cls = node.get("ptr_class")
        val = node.get("value") or {}
        gi = val.get("m_GInfo") or {}
        extra = ""
        if cls == "Geometry":
            extra = f" nfaces={len(val.get('m_pFaces') or [])} nedges={len(val.get('m_pEdges') or [])} geomTag={val.get('m_geometryTag')}"
        print("  "*depth + f"{cls} tag={gi.get('m_tag')} cat={gi.get('m_categoryId')} ctrl={gi.get('m_controlCommand')} flags={gi.get('m_flags')}" + extra)
        for s in val.get("m_subNodes") or []:
            walkg(s, depth+1)
    gi = r.get("m_GInfo") or {}
    print(f" root tag={gi.get('m_tag')} cat={gi.get('m_categoryId')} flags={gi.get('m_flags')} gElemType={r.get('m_gElemType')}")
    for s in r.get("m_subNodes") or []:
        walkg(s)
    # refFaces: how do they relate to solid faces?
    rf = v.get("m_refFaces") or []
    print(" refFaces:", len(rf))
    for f in rf[:12]:
        fv = (f.get("value") or {}) if isinstance(f, dict) else {}
        gi = fv.get("m_GInfo") or {}
        surf = fv.get("m_pSurf") or {}
        print("   Face tag", gi.get("m_tag"), "flags", gi.get("m_flags"), "pid", f.get("pid"), "surf", surf.get("ptr_class"),
              "origin", ((surf.get("value") or {}).get("m_origin")))
    # step face hist for cross-ref
    gs = ((v.get("m_geomSteps") or {}).get("value") or {})
    st = (gs.get("m_bRepFormGList") or [{}])[0]
    sv = st.get("value") or {}
    print(" faceHist:", [(x.get("m_id"), (x.get("m_faceHist") or {}).get("m_keys")) for x in sv.get("m_faceHistTable") or []])
    print(" strongRefs geomTags:", [x.get("m_geomTag") for x in v.get("m_strongRefs") or []])
    print(" g2m:", v.get("m_geomTag2MaterialId"))
