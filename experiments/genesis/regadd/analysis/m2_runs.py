"""M2 -- what IS the record order?  Split the seq-102 unit-0 id sequence into
maximal ascending runs and inspect the classes / id bands in each run.  Also
correlate record position with ElemTable creation episode."""
import os, sys, json, collections
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rvt.container import open_rvt
from rvt.partitions import StreamWalker
from rvt.objects import iter_records, ObjectDecoder
from rvt.stream_encoders import decode_elemtable


def unit0_recs(path, seq=102):
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        seg = b"".join(b.data for b in u0 if b.seq == seq)
        et = decode_elemtable(f.inflate("Global/ElemTable"))
    return list(iter_records(seg, seq)), seg, et


def analyse(name, path, show_runs=12):
    recs, seg, et = unit0_recs(path)
    # ElemTable: id -> (creation, modified)
    etrow = {int(r[4]): (int(r[1]), int(r[2])) for r in et["records"]}
    dec = ObjectDecoder()
    live = [r for r in recs if r.elem_id >= 0]
    ids = [r.elem_id for r in live]
    n = len(ids)
    # maximal ascending runs
    runs = []
    cur = [0]
    for i in range(1, n):
        if ids[i] > ids[i - 1]:
            cur.append(i)
        else:
            runs.append(cur)
            cur = [i]
    runs.append(cur)
    print(f"\n=== {name}: {n} records, {len(runs)} ascending runs")
    # correlation between position and creation episode
    ceps = [etrow.get(i, (None, None))[0] for i in ids]
    # is creation episode NON-DECREASING along the stream?
    ce_clean = [c for c in ceps if c is not None]
    ce_nondec = all(ce_clean[i] <= ce_clean[i + 1] for i in range(len(ce_clean) - 1))
    ce_desc = sum(1 for i in range(len(ce_clean) - 1) if ce_clean[i] > ce_clean[i + 1])
    print(f"  creation-episode nondecreasing along stream: {ce_nondec} (descents {ce_desc})")
    # first/last few records with class + creation ep
    def desc(i):
        r = live[i]
        ce = etrow.get(r.elem_id, ("?", "?"))
        return f"{r.elem_id}({dec.class_name(r.class_id)},ce={ce[0]})"
    print("  first 10:", [desc(i) for i in range(min(10, n))])
    print("  last 6 :", [desc(i) for i in range(max(0, n - 6), n)])
    # runs summary: for each run, its id range, size, dominant classes, creation-ep range
    print(f"  runs (idx: size, id range, ce range, top classes):")
    for k, run in enumerate(runs[:show_runs]):
        rids = [ids[i] for i in run]
        cls = collections.Counter(dec.class_name(live[i].class_id) for i in run)
        cep = [etrow.get(i, (None,))[0] for i in rids]
        cep = [c for c in cep if c is not None]
        print(f"   run{k:>3}: n={len(run):>5} ids {rids[0]:>9}..{rids[-1]:>9} "
              f"ce {min(cep) if cep else '?'}..{max(cep) if cep else '?'} "
              f"top {cls.most_common(3)}")
    if len(runs) > show_runs:
        print(f"   ... {len(runs) - show_runs} more runs; last run n={len(runs[-1])} "
              f"ids {ids[runs[-1][0]]}..{ids[runs[-1][-1]]}")
    # hypothesis test: order by (creation_ep, id)?
    keyed = sorted(range(n), key=lambda i: (etrow.get(ids[i], (10**9,))[0], ids[i]))
    match_ce_id = all(keyed[i] == i for i in range(n))
    print(f"  order == sorted by (creation_ep, id)? {match_ce_id}")
    # hypothesis: order by modified_ep then id?
    keyed2 = sorted(range(n), key=lambda i: (etrow.get(ids[i], (10**9, 10**9))[1], ids[i]))
    print(f"  order == sorted by (modified_ep, id)? {all(keyed2[i]==i for i in range(n))}")
    return runs


K1 = os.path.join(ROOT, "experiments/genesis/triage/K1.rvt")
analyse("K1", K1)
analyse("rstbasic", os.path.join(ROOT, "samples/rstbasicsampleproject.rvt"))
analyse("rmebasic", os.path.join(ROOT, "samples/rmebasicsampleproject.rvt"))
