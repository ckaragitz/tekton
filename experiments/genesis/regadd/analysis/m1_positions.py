"""M1 -- are the unit-0 seq streams id-ascending?  Record positions per seq
across all six samples (+ K1).  Measures: is the record ORDER by elem_id
ascending?  How many inversions?  Where do the low-id singletons sit?"""
import os, sys, json
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rvt.container import open_rvt
from rvt.partitions import StreamWalker
from rvt.objects import iter_records

SAMPLES = ["rstbasicsampleproject", "rmebasicsampleproject", "racbasicsampleproject",
           "racadvancedsampleproject", "rstadvancedsampleproject", "dach-sample-project"]


def unit0_segments(path):
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"{path}: walker errors {w.errors[:2]}")
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        return {s: b"".join(b.data for b in u0 if b.seq == s) for s in (101, 102, 103)}


def analyse(path):
    segs = unit0_segments(path)
    rep = {}
    for seq in (101, 102, 103):
        recs = list(iter_records(segs[seq], seq))
        ids = [r.elem_id for r in recs if r.elem_id >= 0]
        n = len(ids)
        asc = all(ids[i] < ids[i + 1] for i in range(n - 1))
        inv = sum(1 for i in range(n - 1) if ids[i] > ids[i + 1])
        # count of "descents": positions where the sequence steps DOWN
        # longest non-decreasing prefix
        pref = 0
        for i in range(n - 1):
            if ids[i] < ids[i + 1]:
                pref += 1
            else:
                break
        # sorted-order comparison
        srt = sorted(ids)
        same_as_sorted = ids == srt
        # sample of first descents
        descents = []
        for i in range(n - 1):
            if ids[i] > ids[i + 1]:
                descents.append((i, ids[i], ids[i + 1]))
                if len(descents) >= 8:
                    break
        rep[seq] = {"records": n, "strictly_ascending": asc, "equals_sorted": same_as_sorted,
                    "descent_count": inv, "first_ids": ids[:6], "last_ids": ids[-3:],
                    "first_descents(i,prev,next)": descents,
                    "sentinel_last": (recs[-1].elem_id == -1 if recs else None)}
    # cross-seq: same id order across the three seqs?
    id101 = [r.elem_id for r in iter_records(segs[101], 101) if r.elem_id >= 0]
    id102 = [r.elem_id for r in iter_records(segs[102], 102) if r.elem_id >= 0]
    id103 = [r.elem_id for r in iter_records(segs[103], 103) if r.elem_id >= 0]
    rep["cross_seq"] = {"101_eq_102": id101 == id102, "102_eq_103": id102 == id103,
                        "sets_equal": set(id101) == set(id102) == set(id103)}
    return rep


out = {}
K1 = os.path.join(ROOT, "experiments/genesis/triage/K1.rvt")
targets = [("K1", K1)] + [(s, os.path.join(ROOT, "samples", s + ".rvt")) for s in SAMPLES]
for name, path in targets:
    if not os.path.exists(path):
        print(f"skip {name}: {path} missing")
        continue
    try:
        r = analyse(path)
        out[name] = r
        print(f"\n=== {name}")
        for seq in (101, 102, 103):
            s = r[seq]
            print(f"  seq{seq}: n={s['records']:>7} ascending={s['strictly_ascending']} "
                  f"eq_sorted={s['equals_sorted']} descents={s['descent_count']} "
                  f"first={s['first_ids']} last={s['last_ids']}")
            if s['first_descents(i,prev,next)']:
                print(f"          first descents: {s['first_descents(i,prev,next)'][:5]}")
        print(f"  cross-seq id order equal: {r['cross_seq']}")
    except Exception as e:
        print(f"{name}: ERROR {e!r}")
        out[name] = {"error": repr(e)}

with open(os.path.join(os.path.dirname(__file__), "m1_positions.json"), "w") as fh:
    json.dump(out, fh, indent=1, default=str)
print("\nwritten m1_positions.json")
