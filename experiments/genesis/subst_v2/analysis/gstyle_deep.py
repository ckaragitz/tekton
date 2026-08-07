"""gstyle_deep.py -- built-in-category object-style rows (host doc,
m_famId == -1, m_ownerId == -1, m_categoryId < 0) across all six samples:
per-field value distributions of the object AND the seq-101 header, the
header-category-vs-row-category relationship, the deletion-set rule, the
line-pattern / material usage, per-category value constancy; then OUR
catalog rows (projection + cut) diffed against every distribution."""
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
from rvt.genesis import catalog as C      # noqa: E402
from rvt.genesis.types import IdSource    # noqa: E402


def main():
    D = collections.defaultdict(collections.Counter)          # field -> value counter (object)
    H = collections.defaultdict(collections.Counter)          # field -> value counter (header)
    percat = collections.defaultdict(list)                    # (cat, type) -> [ (file, pen, color, pattern, material) ]
    hdrcat_rule = collections.Counter()                       # header.categroryId vs obj.categoryId relationship
    dele_rule = collections.Counter()                         # deletion set contents rule
    n = 0
    key_sets = collections.Counter()
    gstyle_key_sets = collections.Counter()
    et_stats = collections.Counter()
    examples = []
    hdr_examples = []
    for s in SAMPLES:
        doc = Document.load(s)
        for gid in doc.ids_of_class("GStyleElem", host_only=True):
            v = doc.value(gid)
            if v is None:
                continue
            if v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
                continue
            cat = v.get("m_categoryId")
            if not (isinstance(cat, int) and cat < 0):
                continue
            n += 1
            h = doc.decode(gid, 101)
            hv = h.value if h and h.clean else None
            gs = (v.get("m_pGStyle") or {}).get("value") or {}
            # object scalars
            D["m_gstyleType"][v.get("m_gstyleType")] += 1
            D["m_ownerId"][v.get("m_ownerId")] += 1
            D["m_famId"][v.get("m_famId")] += 1
            D["m_designOptionId"][v.get("m_designOptionId")] += 1
            D["m_assocLevelId"][v.get("m_assocLevelId")] += 1
            D["m_createdPhaseId"][v.get("m_createdPhaseId")] += 1
            D["m_demolishedPhaseId"][v.get("m_demolishedPhaseId")] += 1
            D["m_unplacedOwnerId"][v.get("m_unplacedOwnerId")] += 1
            D["m_ownerDBViewId"][v.get("m_ownerDBViewId")] += 1
            D["m_locked"][v.get("m_locked")] += 1
            D["m_moribund"][v.get("m_moribund")] += 1
            D["m_dummy"][v.get("m_dummy")] += 1
            D["m_id_matches"][v.get("m_id") == gid] += 1
            D["m_pParamValueSetDouble"][None if v.get("m_pParamValueSetDouble") is None else "present"] += 1
            D["m_pParamValueSetInt"][None if v.get("m_pParamValueSetInt") is None else "present"] += 1
            D["m_pParamValueSetAString"][None if v.get("m_pParamValueSetAString") is None else "present"] += 1
            D["m_pParamValueSetElementId"][None if v.get("m_pParamValueSetElementId") is None else "present"] += 1
            D["m_geomSteps"][None if v.get("m_geomSteps") is None else "present"] += 1
            D["m_pGeomTable"][None if v.get("m_pGeomTable") is None else "present"] += 1
            D["m_constrInfo_len"][len(v.get("m_constrInfo") or [])] += 1
            D["m_cellList"][None if v.get("m_cellList") is None else "present"] += 1
            D["m_docAccess"][json.dumps(v.get("m_docAccess"), sort_keys=True)] += 1
            D["m_pGStyle.ptr_class"][(v.get("m_pGStyle") or {}).get("ptr_class")] += 1
            D["m_pGStyle.pid"][(v.get("m_pGStyle") or {}).get("pid")] += 1
            # GStyle sub-object
            D["gs.m_penNumber"][gs.get("m_penNumber")] += 1
            D["gs.m_isScreenSized"][gs.get("m_isScreenSized")] += 1
            pat = gs.get("m_linePatternId")
            mat = gs.get("m_materialElemId")
            D["gs.m_linePatternId_kind"]["neg-builtin" if isinstance(pat, int) and pat < 0 and pat != -1 else
                                          ("-1" if pat == -1 else ("elem>0" if isinstance(pat, int) and pat > 0 else str(pat)))] += 1
            D["gs.m_materialElemId_kind"]["-1" if mat == -1 else ("elem>0" if isinstance(mat, int) and mat > 0 else str(mat))] += 1
            D["gs.m_color"][gs.get("m_color")] += 1
            D["gs.keys"][tuple(sorted(gs.keys()))] += 1
            key_sets[tuple(sorted(v.keys()))] += 1
            percat[(cat, v.get("m_gstyleType"))].append(
                (s, gs.get("m_penNumber"), gs.get("m_color"), pat, mat, bool(gs.get("m_isScreenSized"))))
            # header
            if hv is not None:
                H["m_abFlags4Bytes"][hv.get("m_abFlags4Bytes")] += 1
                H["m_nVisibleViewFlags"][(hv.get("m_viewRules") or {}).get("m_nVisibleViewFlags")] += 1
                H["m_categroryId"][hv.get("m_categroryId")] += 1
                H["m_familyId"][hv.get("m_familyId")] += 1
                H["m_ownerViewId"][hv.get("m_ownerViewId")] += 1
                H["m_designOptionId"][hv.get("m_designOptionId")] += 1
                H["m_unplacedOwnerId"][hv.get("m_unplacedOwnerId")] += 1
                H["m_miscId"][hv.get("m_miscId")] += 1
                H["m_classDef"][json.dumps(hv.get("m_classDef"), sort_keys=True)] += 1
                H["m_pBBox"][None if hv.get("m_pBBox") is None else "present"] += 1
                H["m_regenHistory_len"][len((hv.get("m_regenHistory") or {}).get("m_historyMap") or [])] += 1
                par = (hv.get("m_parents") or {}).get("value") or {}
                H["parents.ptr_class"][(hv.get("m_parents") or {}).get("ptr_class")] += 1
                dele = par.get("m_deletion") or []
                H["parents.m_deletion_len"][len(dele)] += 1
                # deletion rule: does it equal [self]?  contain pattern? material?
                extra = [x for x in dele if x != gid]
                if not extra:
                    dele_rule["[self] only"] += 1
                else:
                    what = []
                    if pat in extra:
                        what.append("pattern")
                    if mat in extra:
                        what.append("material")
                    rest = [x for x in extra if x not in (pat, mat)]
                    if rest:
                        what.append(f"other{sorted(rest)[:3]}")
                    dele_rule["self+" + "+".join(what)] += 1
                H["parents.m_regenOnly_len"][len(par.get("m_regenOnly") or [])] += 1
                H["parents.m_regenWildcards_len"][len(par.get("m_regenWildcards") or [])] += 1
                H["parents.m_appearanceParents_len"][len(par.get("m_appearanceParents") or [])] += 1
                H["parents.m_dependencyParents_len"][len(par.get("m_dependencyParents") or [])] += 1
                H["parents.m_deferredParents_len"][len(par.get("m_deferredParents") or [])] += 1
                H["parents.m_nonDeterm_len"][len(par.get("m_nonDetermRegenChildren") or [])] += 1
                H["parents.m_computedParams_len"][len(par.get("m_computedParametersParents") or [])] += 1
                H["parents.hasNonDeterm"][par.get("m_hasNonDetermRegenChildren")] += 1
                # relationship: header categoryId vs object categoryId
                hcat = hv.get("m_categroryId")
                if hcat == cat:
                    hdrcat_rule["hdr==obj category"] += 1
                elif hcat == -1:
                    hdrcat_rule["hdr -1"] += 1
                else:
                    hdrcat_rule[f"hdr other ({hcat} vs {cat})"] += 1
                if len(hdr_examples) < 3:
                    hdr_examples.append({"file": s, "id": gid, "hdr": hv})
            if len(examples) < 3:
                examples.append({"file": s, "id": gid, "obj": v})
            # ElemTable row
            et = doc.et_by_id.get(gid)
            if et is not None:
                et_stats[("owner", et.owner_id if et.owner_id < 2**63 else -1)] += 1
                et_stats[("partition", et.partition_id)] += 1
        print(f"   [{s}] built-in rows so far: {n}")

    ours = C.builtin_style_catalog(IdSource(1_700_000))
    our_proj = ours[0]
    our_cut = [r for r in ours if r.refs.get("style_type") == 2][0]

    def top(counter, k=10):
        return dict(collections.Counter(counter).most_common(k))

    print("\n" + "=" * 78)
    print(f"BUILT-IN GSTYLE ROWS ANALYSED: {n}")
    print("=" * 78)
    print("\n-- object scalar distributions --")
    for f in sorted(D):
        print(f"  {f}: distinct={len(D[f])} top={top(D[f])}")
    print("\n-- header (seq101) distributions --")
    for f in sorted(H):
        print(f"  {f}: distinct={len(H[f])} top={top(H[f])}")
    print("\n-- header.categroryId vs obj.categoryId --", dict(hdrcat_rule))
    print("-- deletion-set rule --", top(dele_rule, 20))
    print("-- ElemTable owner/partition --", top(et_stats, 10))
    print("-- object top-level key sets --", {str(k): v for k, v in key_sets.items()})

    # per-category constancy of pen/color/pattern across files
    print("\n-- per-(category,type) value CONSTANCY across the 6 files (pen,color,pattern) --")
    const_pen = const_color = const_pat = varying = 0
    pattern_named_cats = collections.Counter()
    material_cats = collections.Counter()
    screensized_cats = collections.Counter()
    for (cat, typ), rows in percat.items():
        pens = set(r[1] for r in rows)
        cols = set(r[2] for r in rows)
        pats = set(r[3] for r in rows)
        mats = set(r[4] for r in rows)
        if len(pens) == 1:
            const_pen += 1
        if len(cols) == 1:
            const_color += 1
        if len(pats) == 1:
            const_pat += 1
        if any(isinstance(p, int) and p > 0 for p in pats) or any(isinstance(p, int) and p < 0 and p not in (-1, -3000010) for p in pats):
            pattern_named_cats[(cat, typ)] += 1
        if any(isinstance(m, int) and m > 0 for m in mats):
            material_cats[(cat, typ)] += 1
        if any(r[5] for r in rows):
            screensized_cats[(cat, typ)] += 1
    total = len(percat)
    print(f"  (category,type) keys: {total}; constant pen across files: {const_pen}; constant color: {const_color}; constant pattern: {const_pat}")
    print(f"  keys where SOME file uses a non-solid pattern (elem>0 or built-in<0 not solid): {len(pattern_named_cats)}")
    print(f"  keys where SOME file points at a MATERIAL element: {len(material_cats)} e.g. {list(material_cats)[:12]}")
    print(f"  keys where SOME file sets m_isScreenSized: {len(screensized_cats)} e.g. {list(screensized_cats)[:12]}")

    # OURS vs distributions
    print("\n" + "=" * 78)
    print("OUR CATALOG ROWS vs THE DISTRIBUTIONS")
    print("=" * 78)
    for label, r in (("projection", our_proj), ("cut", our_cut)):
        v = r.obj
        gs = v["m_pGStyle"]["value"]
        print(f"\n[{label}] our obj: catId={v['m_categoryId']} gstyleType={v['m_gstyleType']} ownerId={v['m_ownerId']} famId={v['m_famId']} "
              f"designOpt={v['m_designOptionId']} pen={gs['m_penNumber']} color={gs['m_color']:#x} pattern={gs['m_linePatternId']} "
              f"material={gs['m_materialElemId']} screenSized={gs['m_isScreenSized']}")
        print(f"    top-level key set in specimen key sets? {tuple(sorted(v.keys())) in key_sets}")
        print(f"    GStyle sub-object key set in specimen sets? {tuple(sorted(gs.keys())) in dict(D['gs.keys'])}")
        hv = r.header
        par = hv["m_parents"]["value"]
        print(f"    hdr: ab={hv['m_abFlags4Bytes']} vis={hv['m_viewRules']['m_nVisibleViewFlags']} "
              f"categroryId={hv['m_categroryId']} familyId={hv['m_familyId']} deletion={par['m_deletion']} "
              f"regenWildcards={par['m_regenWildcards']} appearance={par['m_appearanceParents']}")
        # value-set checks
        checks = [
            ("obj.m_gstyleType", v["m_gstyleType"], D["m_gstyleType"]),
            ("obj.m_ownerId", v["m_ownerId"], D["m_ownerId"]),
            ("obj.m_famId", v["m_famId"], D["m_famId"]),
            ("obj.m_designOptionId", v["m_designOptionId"], D["m_designOptionId"]),
            ("gs.m_penNumber", gs["m_penNumber"], D["gs.m_penNumber"]),
            ("gs.m_color", gs["m_color"], D["gs.m_color"]),
            ("gs.m_isScreenSized", gs["m_isScreenSized"], D["gs.m_isScreenSized"]),
            ("hdr.m_abFlags4Bytes", hv["m_abFlags4Bytes"], H["m_abFlags4Bytes"]),
            ("hdr.m_nVisibleViewFlags", hv["m_viewRules"]["m_nVisibleViewFlags"], H["m_nVisibleViewFlags"]),
            ("hdr.m_familyId", hv["m_familyId"], H["m_familyId"]),
        ]
        for name, val, dist in checks:
            if val not in dist:
                print(f"    !! {name} = {val!r} NOT in specimen value set {top(dist)}")
        # header category rule
        hcat = hv["m_categroryId"]
        print(f"    hdr.categroryId={hcat} vs obj.categoryId={v['m_categoryId']}  (specimen rule: {dict(hdrcat_rule)})")
    with open(os.path.join(OUT, "gstyle_deep.json"), "w") as fh:
        json.dump({"n_rows": n,
                   "object_dist": {f: {str(k): c for k, c in cnt.most_common(40)} for f, cnt in D.items()},
                   "header_dist": {f: {str(k): c for k, c in cnt.most_common(40)} for f, cnt in H.items()},
                   "hdrcat_rule": dict(hdrcat_rule),
                   "deletion_rule": {str(k): c for k, c in dele_rule.most_common(40)},
                   "et_stats": {str(k): c for k, c in et_stats.most_common(20)},
                   "examples": examples, "hdr_examples": hdr_examples,
                   "our_projection": {"obj": our_proj.obj, "hdr": our_proj.header},
                   "our_cut": {"obj": our_cut.obj, "hdr": our_cut.header}},
                  fh, indent=1, default=str)


if __name__ == "__main__":
    main()
