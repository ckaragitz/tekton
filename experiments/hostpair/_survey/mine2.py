import json, sys, collections
sys.path.insert(0, "src")
rows = json.load(open("experiments/hostpair/_survey/mined_rows.json"))
rf = [r["n_refFaces"] for r in rows]
print("refFaces min/max:", min(rf), max(rf), "zeros:", sum(1 for x in rf if x == 0))
subs = collections.Counter(tuple(eval(r["subs"]) if isinstance(r["subs"], str) else r["subs"]) for r in rows)
print("ALL subs shapes:")
for k, n in sorted(subs.items(), key=lambda kv: -kv[1]):
    print(" ", n, k)
# find a minimal (GFilter, GFilter, Geometry) example in rst basic
ex = [r for r in rows if (tuple(eval(r["subs"]) if isinstance(r["subs"], str) else r["subs"])) == ("GFilter","GFilter","Geometry") and r["sample"] == "samples/rstbasicsampleproject.rvt"]
print("minimal-shape examples in rstbasic:", [(r["symbol"], r["cat"], r["n_refFaces"], r["n_strongRefs"]) for r in ex][:6])
# g2m zero + strongRefs zero co-occurrence with minimal shape
mini = [r for r in rows if (tuple(eval(r["subs"]) if isinstance(r["subs"], str) else r["subs"])) == ("GFilter","GFilter","Geometry")]
print("minimal-shape: refFaces dist", collections.Counter(r["n_refFaces"] for r in mini))
print("minimal-shape: cats", collections.Counter(r["cat"] for r in mini))
