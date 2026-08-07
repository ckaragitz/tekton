"""pen_deep.py -- the six PROJECT pen tables (m_famId == -1, host doc) side
by side with OURS, field by field: scale sets, pen vectors (mm), monotonicity,
duplicates, header fields, seq-103 rep class, ElemTable row.  Plus the
family-scoped pen tables' scale sets for the full corpus picture."""
from __future__ import annotations

import collections
import json
import os
import sys

ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
SCR = "/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad"
os.environ.setdefault("RVT_SEG_CACHE", os.path.join(SCR, "segcache"))
OUT = os.path.join(SCR, "fixer")

SAMPLES = ["rstbasicsampleproject", "rmebasicsampleproject", "racbasicsampleproject",
           "racadvancedsampleproject", "rstadvancedsampleproject", "dach-sample-project"]

from rvt.mutate import Document          # noqa: E402
from rvt.genesis import settings as S     # noqa: E402

MM = 304.8


def pens_mm(pi):
    return [round(x * MM, 4) for x in pi["m_pens"]]


def analyse_table(v):
    t = (v.get("m_pPenWidthTable") or {}).get("value") or {}
    model = t.get("m_modelPenInfo") or []
    persp = t.get("m_perspectiveModelPenInfo") or {}
    draft = t.get("m_draftPenInfo") or {}
    return {
        "famId": v.get("m_famId"),
        "n_scales": len(model),
        "scales": [pi.get("m_invertedScale") for pi in model],
        "model_pens_mm": {pi.get("m_invertedScale"): pens_mm(pi) for pi in model},
        "persp_scale": persp.get("m_invertedScale"),
        "persp_pens_mm": pens_mm(persp) if persp else None,
        "draft_scale": draft.get("m_invertedScale"),
        "draft_pens_mm": pens_mm(draft) if draft else None,
        "cellList": v.get("m_cellList"),
        "ptr_class": (v.get("m_pPenWidthTable") or {}).get("ptr_class"),
        "top_level_keys": sorted(v.keys()),
    }


def monotone(vec):
    return all(a <= b + 1e-9 for a, b in zip(vec, vec[1:]))


def main():
    project_tables = []
    fam_scale_sets = collections.Counter()
    fam_pen_stats = {"min": 1e9, "max": 0, "non_monotone": 0, "n_vectors": 0,
                     "dup_within_vector": 0}
    seq103_classes = collections.Counter()
    hdr_summary = []
    et_rows = []
    for s in SAMPLES:
        doc = Document.load(s)
        for pid in doc.ids_of_class("PenWidthTableElem", host_only=False):
            v = doc.value(pid)
            if v is None:
                continue
            a = analyse_table(v)
            host = doc.in_host_document(pid)
            # seq 103 class
            r103 = doc.record(pid, 103)
            c103 = doc.dec.class_name(r103.class_id) if r103 else None
            seq103_classes[c103] += 1
            if host and a["famId"] in (None, -1):
                h = doc.decode(pid, 101)
                hv = h.value if h else {}
                et = doc.et_by_id.get(pid)
                project_tables.append({"file": s, "id": pid, "analysis": a,
                                       "seq103": c103,
                                       "header": hv})
                hdr_summary.append({"file": s, "id": pid,
                                    "ab": hv.get("m_abFlags4Bytes"),
                                    "vis": (hv.get("m_viewRules") or {}).get("m_nVisibleViewFlags"),
                                    "cat": hv.get("m_categroryId"),
                                    "fam": hv.get("m_familyId"),
                                    "deletion": (hv.get("m_parents") or {}).get("value", {}).get("m_deletion"),
                                    "regenWildcards": (hv.get("m_parents") or {}).get("value", {}).get("m_regenWildcards"),
                                    "appearance": (hv.get("m_parents") or {}).get("value", {}).get("m_appearanceParents"),
                                    })
                et_rows.append({"file": s, "id": pid,
                                "et": None if et is None else et.__dict__ if hasattr(et, "__dict__") else str(et)})
            else:
                fam_scale_sets[tuple(a["scales"])] += 1
                for sc, vec in a["model_pens_mm"].items():
                    fam_pen_stats["n_vectors"] += 1
                    fam_pen_stats["min"] = min(fam_pen_stats["min"], min(vec))
                    fam_pen_stats["max"] = max(fam_pen_stats["max"], max(vec))
                    if not monotone(vec):
                        fam_pen_stats["non_monotone"] += 1
                    if len(set(vec)) != len(vec):
                        fam_pen_stats["dup_within_vector"] += 1
    ours = S.pen_width_table(elem_id=1600000)
    ours_a = analyse_table(ours.obj)
    print("=" * 78)
    print("THE SIX PROJECT PEN TABLES (host, m_famId == -1) vs OURS")
    print("=" * 78)
    for pt in project_tables:
        a = pt["analysis"]
        print(f"\n[{pt['file']}] id {pt['id']}  seq103={pt['seq103']}  famId={a['famId']}  ptr={a['ptr_class']}")
        print(f"   n_scales={a['n_scales']} scales={a['scales']}")
        for sc, vec in a["model_pens_mm"].items():
            mono = monotone(vec)
            dup = len(set(vec)) != len(vec)
            print(f"     scale {sc:>4}: {vec}  mono={mono} dups={dup} min={min(vec)} max={max(vec)}")
        print(f"   persp scale {a['persp_scale']}: {a['persp_pens_mm']}  mono={monotone(a['persp_pens_mm'])}")
        print(f"   draft scale {a['draft_scale']}: {a['draft_pens_mm']}  mono={monotone(a['draft_pens_mm'])}")
        print(f"   cellList={a['cellList']}")
    print("\nOURS:")
    a = ours_a
    print(f"   n_scales={a['n_scales']} scales={a['scales']}")
    for sc, vec in a["model_pens_mm"].items():
        print(f"     scale {sc:>4}: {vec}  mono={monotone(vec)} min={min(vec)} max={max(vec)}")
    print(f"   persp scale {a['persp_scale']}: {a['persp_pens_mm']}")
    print(f"   draft scale {a['draft_scale']}: {a['draft_pens_mm']}")
    print(f"   top_level_keys equal to specimen? {a['top_level_keys'] == project_tables[0]['analysis']['top_level_keys']}")
    print("\nseq-103 class histogram over ALL pen tables:", dict(seq103_classes))
    print("\nfamily-scoped pen tables: scale-set histogram (top 12):")
    for k, c in fam_scale_sets.most_common(12):
        print(f"   {c:5d}  scales={list(k)}")
    print(f"family-scoped pen stats: {fam_pen_stats}")
    print("\nheaders of the six project pen tables:")
    for hs in hdr_summary:
        print("  ", hs)
    our_h = ours.header
    print("OUR header: ab=%s vis=%s cat=%s fam=%s deletion=%s wildcards=%s appearance=%s" % (
        our_h.get("m_abFlags4Bytes"), (our_h.get("m_viewRules") or {}).get("m_nVisibleViewFlags"),
        our_h.get("m_categroryId"), our_h.get("m_familyId"),
        (our_h.get("m_parents") or {}).get("value", {}).get("m_deletion"),
        (our_h.get("m_parents") or {}).get("value", {}).get("m_regenWildcards"),
        (our_h.get("m_parents") or {}).get("value", {}).get("m_appearanceParents")))
    print("\nElemTable rows of the six project pen tables:")
    for e in et_rows:
        print("  ", e)
    with open(os.path.join(OUT, "pen_deep.json"), "w") as fh:
        json.dump({"project_tables": project_tables, "ours": ours_a,
                   "family_scale_sets": {str(k): v for k, v in fam_scale_sets.items()},
                   "family_pen_stats": fam_pen_stats,
                   "seq103_classes": dict(seq103_classes),
                   "et_rows": et_rows}, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
