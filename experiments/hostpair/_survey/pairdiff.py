import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "tools")
from rvt.mutate import Document
import residual_probe as R

RST = "samples/rstbasicsampleproject.rvt"
H7L = "experiments/famdoc_bisect/_build/H7/H7_load.rvt"
nat = Document.from_file(RST)
h7 = Document.from_file(H7L)

pairs = [("Family", 1410863, 1472942), ("FamilySymbol", 1411287, 1472947),
         ("FamilySurrogate", 1411267, 1472945), ("FamSymSurrogate", 1411288, 1472946),
         ("ParamElemFamily.twin", 1411280, 1472943)]
out = {}
for label, a, b in pairs:
    av, bv = nat.value(a) or {}, h7.value(b) or {}
    d = R.diff_objects(av, bv)
    ah, bh = nat.value(a, 101) or {}, h7.value(b, 101) or {}
    dh = R.diff_objects(ah, bh)
    ar, br = nat.record(a, 103), h7.record(b, 103)
    out[label] = {"obj": d, "hdr": dh,
                  "rep": {"A": (nat.class_of(a, 103) if ar else None),
                          "B": (h7.class_of(b, 103) if br else None)}}
print(json.dumps(out, indent=1, default=str))
