"""M5 -- what determines the unit-0 record order?  Test the topological
hypothesis: for every element at stream position p, do its OUTBOUND
references (typed graph) point FORWARD (to later positions) or BACKWARD?
A dependents-first (reverse-topological) order => references point FORWARD.
Also test: within an ascending run, are the elements a DFS-like chain?"""
import os, sys, json, collections
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rvt_reduce as RR
from rvt.container import open_rvt
from rvt.partitions import StreamWalker
from rvt.objects import iter_records

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "experiments/genesis/triage/K1.rvt")

# stream order (seq 102)
with open_rvt(path) as f:
    pname = f.partition_streams()[0]
    w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
    u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
    seg = b"".join(b.data for b in u0 if b.seq == 102)
order = [r.elem_id for r in iter_records(seg, 102) if r.elem_id >= 0]
pos = {e: i for i, e in enumerate(order)}
print(f"{path}: {len(order)} unit-0 elements")

st = RR.build_state_v2(path)          # typed graph: graph[e] = set of ids e references
graph = st["graph"]
host = set(st["host"])
fwd = bwd = self_ref = to_absent = 0
per_class = collections.Counter()
cls_of = st["cls_of"]
edges = 0
sample_bwd = []
for e, targets in graph.items():
    if e not in pos:
        continue
    pe = pos[e]
    for t in targets:
        if t == e:
            self_ref += 1
            continue
        pt = pos.get(t)
        if pt is None:
            to_absent += 1
            continue
        edges += 1
        if pt > pe:
            fwd += 1
        else:
            bwd += 1
            if len(sample_bwd) < 15:
                sample_bwd.append((e, cls_of.get(e), t, cls_of.get(t), pe, pt))
print(f"typed edges within unit0: {edges}; FORWARD (target later) {fwd} "
      f"({fwd/max(edges,1):.1%}); BACKWARD {bwd} ({bwd/max(edges,1):.1%}); "
      f"to-absent(embedded/deleted) {to_absent}")
print("sample backward edges (referrer,class -> target,class @ positions):")
for e, ce, t, ct, pe, pt in sample_bwd:
    print(f"   {e}({ce})@{pe} -> {t}({ct})@{pt}")

# Are backward edges concentrated in particular referrer classes?
bwd_cls = collections.Counter()
fwd_cls = collections.Counter()
for e, targets in graph.items():
    if e not in pos:
        continue
    for t in targets:
        if t == e or t not in pos:
            continue
        (fwd_cls if pos[t] > pos[e] else bwd_cls)[cls_of.get(e)] += 1
print("\nbackward-edge referrer classes:", bwd_cls.most_common(12))
print("forward-edge referrer classes:", fwd_cls.most_common(8))
