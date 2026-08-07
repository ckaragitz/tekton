import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document
doc = Document.from_file("samples/rstbasicsampleproject.rvt")
v = doc.value(1411287) or {}
gs = ((v.get("m_geomSteps") or {}).get("value") or {})
steps = gs.get("m_bRepFormGList") or []
print("GeomStepList flags", gs.get("m_flags"), "idCounter", gs.get("m_idCounter"),
      "latest", gs.get("m_latestGStepTypeInPrevRegenCycle"),
      "other lists:", {k: len(gs.get(k) or []) for k in ("m_nonBRepGList","m_bRepAdjustGList","m_bRepCutOutGList","m_bRepPostCutOutGList","m_bRepTweakGList")},
      "snapshots:", {k: (gs.get(k) is not None) for k in ("m_bRepFormSnapshot","m_bRepAdjustSnapshot","m_bRepCutOutSnapshot","m_bRepPostCutOutSnapshot")})
st = steps[0]
sv = st.get("value") or {}
print("step class", st.get("ptr_class"), "version", sv.get("m_version"), "flags", sv.get("m_flags"), "id", sv.get("m_id"), "pElem", sv.get("m_pElem"), "extra", sv.get("m_oExtraDatas"))
fh = sv.get("m_faceHistTable") or []
eh = sv.get("m_edgeHistTable") or []
ch = sv.get("m_curveHistTableSet") or []
rh = sv.get("m_edgeHistTableReverse") or []
print("faceHist", len(fh), "edgeHist", len(eh), "curveHist", len(ch), "edgeRev", len(rh))
def keyshape(rows, kname):
    out = []
    for r in rows[:40]:
        k = ((r.get(kname) or {}).get("m_keys"))
        out.append((r.get("m_id"), k))
    return out
print("faceHist rows:", keyshape(fh, "m_faceHist"))
print("edgeHist rows:", keyshape(eh, "m_edgeHist"))
print("curveHist rows:", keyshape(ch, "m_curveHist"))
gt = ((v.get("m_pGeomTable") or {}).get("value") or {})
tab = gt.get("m_table") or []
print("geomTable rows", len(tab), "row shapes:", tab[:8], "...", tab[-4:])
print("bigTableOwner", gt.get("m_bigTableOwner"), "refPntMirrored", gt.get("m_refPntMirrored"))
print("refFaces:", json.dumps((v.get("m_refFaces") or [])[:6], default=str)[:600])
print("n refFaces", len(v.get("m_refFaces") or []))
print("strongRefs:", json.dumps(v.get("m_strongRefs"), default=str)[:400])
print("geomTag2MaterialId:", v.get("m_geomTag2MaterialId"))
print("cutPlaneHeights:", v.get("m_cutPlaneHeights"), "outline:", v.get("m_outline"))
# rep root
r = doc.value(1411287, 103) or {}
gi = r.get("m_GInfo") or {}
print("rep root GInfo:", gi, "elementId", r.get("m_elementId"), "gElemType", r.get("m_gElemType"), "flags", r.get("m_flags"))
subs = r.get("m_subNodes") or []
print("rep subNodes:", [s.get("ptr_class") for s in subs if isinstance(s, dict)])
def walkg(node, depth=0):
    if not isinstance(node, dict): return
    cls = node.get("ptr_class")
    val = node.get("value") or {}
    gi = val.get("m_GInfo") or {}
    if cls:
        print("  "*depth + f"{cls} tag={gi.get('m_tag')} cat={gi.get('m_categoryId')} ctrl={gi.get('m_controlCommand')} flags={gi.get('m_flags')}"
              + (f" nfaces={len(val.get('m_pFaces') or [])} nedges={len(val.get('m_pEdges') or [])} geomTag={val.get('m_geometryTag')}" if cls=='Geometry' else ""))
    for s in val.get("m_subNodes") or []:
        walkg(s, depth+1)
for s in subs:
    walkg(s, 1)
