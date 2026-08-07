"""Deep-mine the geometry-history grammar of every INSTANCED FamilySymbol
across the four samples (the 201 corpus symbols + per-sample instanced sets)."""
import json, sys, collections
sys.path.insert(0, "src")
from rvt.mutate import Document

SAMPLES = ["samples/rstbasicsampleproject.rvt", "samples/rstadvancedsampleproject.rvt",
           "samples/racbasicsampleproject.rvt", "samples/rmebasicsampleproject.rvt"]

def dist(c):
    return dict(sorted(collections.Counter(c).items(), key=lambda kv: -kv[1])[:8])

rows = []
for s in SAMPLES:
    doc = Document.from_file(s)
    # instanced symbols: any FamilyInstance's header InstanceInfo m_symbolId / obj m_masterSymbolId
    used = collections.Counter()
    for iid in doc.ids_of_class("FamilyInstance"):
        v = doc.value(iid) or {}
        ms = v.get("m_masterSymbolId")
        if isinstance(ms, int) and ms > 0:
            used[ms] += 1
    for sid in doc.ids_of_class("FamilySymbol"):
        if used.get(sid, 0) == 0:
            continue
        v = doc.value(sid) or {}
        gs = v.get("m_geomSteps")
        gt = v.get("m_pGeomTable")
        gsv = (gs.get("value") or {}) if isinstance(gs, dict) else {}
        gtv = (gt.get("value") or {}) if isinstance(gt, dict) else {}
        steps = gsv.get("m_bRepFormGList") or []
        stepinfo = []
        n_ids = 0
        for st in steps:
            sv = st.get("value") or {}
            fh = sv.get("m_faceHistTable") or []
            eh = sv.get("m_edgeHistTable") or []
            ch = sv.get("m_curveHistTableSet") or []
            stepinfo.append({"cls": st.get("ptr_class"), "ver": sv.get("m_version"),
                             "flags": sv.get("m_flags"), "id": sv.get("m_id"),
                             "fh": len(fh), "eh": len(eh), "ch": len(ch),
                             "rev": len(sv.get("m_edgeHistTableReverse") or [])})
        tab = gtv.get("m_table") or []
        gen_ids = collections.Counter()
        for r in tab:
            gen_ids[r.get("m_geomGeneratorId")] += 1
        rep = doc.value(sid, 103) or {}
        gi = rep.get("m_GInfo") or {}
        subs = [x.get("ptr_class") for x in (rep.get("m_subNodes") or []) if isinstance(x, dict)]
        other = {k: len(gsv.get(k) or []) for k in ("m_nonBRepGList","m_bRepAdjustGList","m_bRepCutOutGList","m_bRepPostCutOutGList","m_bRepTweakGList")}
        rows.append({
            "sample": s, "symbol": sid, "n_inst": used[sid],
            "cat": doc.category_of(sid),
            "list_flags": gsv.get("m_flags"), "idCounter": gsv.get("m_idCounter"),
            "latest": tuple(gsv.get("m_latestGStepTypeInPrevRegenCycle") or []),
            "other_lists": tuple(sorted((k, n) for k, n in other.items() if n)),
            "snapshots": tuple(k for k in ("m_bRepFormSnapshot","m_bRepAdjustSnapshot","m_bRepCutOutSnapshot","m_bRepPostCutOutSnapshot") if gsv.get(k) is not None),
            "n_steps": len(steps), "steps": stepinfo,
            "table_rows": len(tab), "gen_ids": dict(gen_ids),
            "bigTableOwner": gtv.get("m_bigTableOwner") is not None,
            "refPntMirrored": gtv.get("m_refPntMirrored"),
            "n_refFaces": len(v.get("m_refFaces") or []),
            "n_strongRefs": len(v.get("m_strongRefs") or []),
            "n_g2m": len(v.get("m_geomTag2MaterialId") or []),
            "hasParamDef": v.get("m_hasParamDefValue"),
            "root_cat": gi.get("m_categoryId"), "root_tag_is_self": gi.get("m_tag") == sid,
            "root_flags": gi.get("m_flags"), "gElemType": rep.get("m_gElemType"),
            "rep_flags": rep.get("m_flags"),
            "subs": tuple(subs),
        })
    print(s, "instanced symbols mined:", sum(1 for r in rows if r["sample"] == s), flush=True)

print("TOTAL", len(rows))
inv = {}
for key in ("list_flags", "idCounter", "latest", "other_lists", "snapshots", "n_steps",
            "bigTableOwner", "refPntMirrored", "hasParamDef", "root_tag_is_self",
            "gElemType", "rep_flags", "root_flags"):
    inv[key] = {str(k): v for k, v in dist([r[key] for r in rows]).items()}
print(json.dumps(inv, indent=1, default=str))
step1 = [r["steps"][0] for r in rows if r["n_steps"] == 1]
print("single-step: cls", dist([s["cls"] for s in step1]), "ver", dist([s["ver"] for s in step1]),
      "flags", dist([s["flags"] for s in step1]), "id", dist([s["id"] for s in step1]))
multi = [r for r in rows if r["n_steps"] != 1]
print("multi/zero-step symbols:", len(multi), [(r["symbol"], r["n_steps"], [s["cls"] for s in r["steps"]]) for r in multi[:8]])
# table rows == id space?
ok = sum(1 for r in rows if r["n_steps"] >= 1 and r["table_rows"] == sum(s["fh"]+s["eh"]+s["ch"] for s in r["steps"]))
print("table_rows == sum(hist rows):", ok, "/", len(rows))
print("gen_id values dist:", dist([tuple(sorted(r["gen_ids"].items())) for r in rows][:0] or []))
allgen = collections.Counter()
for r in rows:
    for k, n in r["gen_ids"].items():
        allgen[k] += n
print("gen ids overall:", dict(allgen))
print("refFaces dist:", dist([r["n_refFaces"] for r in rows]))
print("strongRefs dist:", dist([r["n_strongRefs"] for r in rows]))
print("g2m dist:", dist([r["n_g2m"] for r in rows]))
print("subs dist:", dist([r["subs"] for r in rows]))
print("root_cat is -1:", sum(1 for r in rows if r["root_cat"] == -1), "else sample:", dist([r["root_cat"] for r in rows]))
json.dump(rows, open("experiments/hostpair/_survey/mined_rows.json", "w"), indent=0, default=str)
