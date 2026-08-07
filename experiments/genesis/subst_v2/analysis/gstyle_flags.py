"""gstyle_flags.py -- what determines the built-in GStyleElem header's
m_abFlags4Bytes?  Per (category, type) constancy across the 6 files;
correlation with cellList presence / pattern kind / gstyleType / screenSized;
and the raw distinct negative line-pattern / material id sets."""
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


def main():
    flags_by_key = collections.defaultdict(set)          # (cat,type) -> {ab}
    flags_by_key_perfile = collections.defaultdict(dict)  # (cat,type) -> {file: ab}
    corr = collections.Counter()                          # (ab, has_cellList, gtype) -> n
    corr_pat = collections.Counter()
    neg_patterns = collections.Counter()
    neg_materials = collections.Counter()
    pos_patterns = 0
    ab_by_file = collections.defaultdict(collections.Counter)
    n = 0
    for s in SAMPLES:
        doc = Document.load(s)
        for gid in doc.ids_of_class("GStyleElem", host_only=True):
            v = doc.value(gid)
            if not v or v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
                continue
            cat = v.get("m_categoryId")
            if not (isinstance(cat, int) and cat < 0):
                continue
            n += 1
            gt = v.get("m_gstyleType")
            gs = (v.get("m_pGStyle") or {}).get("value") or {}
            pat = gs.get("m_linePatternId")
            mat = gs.get("m_materialElemId")
            if isinstance(pat, int) and pat < 0:
                neg_patterns[pat] += 1
            elif isinstance(pat, int) and pat > 0:
                pos_patterns += 1
            if isinstance(mat, int) and mat < 0:
                neg_materials[mat] += 1
            h = doc.decode(gid, 101)
            if not (h and h.clean):
                continue
            ab = h.value.get("m_abFlags4Bytes")
            key = (cat, gt)
            flags_by_key[key].add(ab)
            flags_by_key_perfile[key][s] = ab
            has_cl = v.get("m_cellList") is not None
            corr[(ab, has_cl, gt)] += 1
            patk = "solid-builtin" if pat == -3000010 else ("neg-other" if isinstance(pat, int) and pat < 0 else
                    ("-1" if pat == -1 else "elem>0"))
            corr_pat[(ab, patk)] += 1
            ab_by_file[s][ab] += 1
    print(f"rows: {n}")
    const = sum(1 for k, v in flags_by_key.items() if len(v) == 1)
    print(f"(cat,type) keys: {len(flags_by_key)}; abFlags CONSTANT across all files carrying the key: {const}")
    # keys present in all 6 files
    six = {k: v for k, v in flags_by_key_perfile.items() if len(v) == 6}
    six_const = sum(1 for k, v in six.items() if len(set(v.values())) == 1)
    print(f"keys present in all 6 files: {len(six)}; of those abFlags constant across the 6: {six_const}")
    var = [(k, v) for k, v in flags_by_key_perfile.items() if len(set(v.values())) > 1]
    print(f"keys whose abFlags VARY across files: {len(var)}; examples:")
    for k, v in var[:15]:
        print(f"   {k}: {v}")
    print("\ncorrelation (abFlags, has_cellList, gstyleType) -> count:")
    for k, c in sorted(corr.items(), key=lambda kv: -kv[1]):
        print(f"   ab={k[0]:>9} (0x{k[0]:08X}) cellList={k[1]!s:5} type={k[2]} : {c}")
    print("\ncorrelation (abFlags, pattern kind) -> count:")
    for k, c in sorted(corr_pat.items(), key=lambda kv: -kv[1]):
        print(f"   ab={k[0]:>9} pattern={k[1]:>14} : {c}")
    print("\nabFlags per file:")
    for f, cnt in ab_by_file.items():
        print(f"   {f}: {dict(cnt)}")
    print("\ndistinct NEGATIVE line-pattern ids on built-in rows:", dict(neg_patterns))
    print("positive (element) pattern ids used on built-in rows:", pos_patterns)
    print("distinct NEGATIVE material ids on built-in rows:", dict(neg_materials))
    with open(os.path.join(OUT, "gstyle_flags.json"), "w") as fh:
        json.dump({"const_keys": const, "keys": len(flags_by_key),
                   "six_keys": len(six), "six_const": six_const,
                   "varying_examples": {str(k): v for k, v in var[:60]},
                   "corr": {str(k): c for k, c in corr.items()},
                   "corr_pat": {str(k): c for k, c in corr_pat.items()},
                   "neg_patterns": {str(k): c for k, c in neg_patterns.items()},
                   "neg_materials": {str(k): c for k, c in neg_materials.items()},
                   "pos_patterns": pos_patterns}, fh, indent=1)


if __name__ == "__main__":
    main()
