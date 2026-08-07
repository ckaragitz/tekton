"""M7 -- is the unit-0 order a merge of CREATION-EPISODE cohorts, each
id-ascending?  Test (a) is each creation-episode cohort id-ascending within
the stream, (b) is each cohort CONTIGUOUS, (c) specifically the birth cohort
(creation_ep == 0).  All six samples + K1."""
import os, sys, collections
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt.container import open_rvt
from rvt.partitions import StreamWalker
from rvt.objects import iter_records
from rvt.stream_encoders import decode_elemtable


def load(path):
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        seg = b"".join(b.data for b in u0 if b.seq == 102)
        et = decode_elemtable(f.inflate("Global/ElemTable"))
    order = [r.elem_id for r in iter_records(seg, 102) if r.elem_id >= 0]
    etrow = {int(r[4]): (int(r[1]), int(r[2])) for r in et["records"]}
    return order, etrow


targets = [("K1", os.path.join(ROOT, "experiments/genesis/triage/K1.rvt"))] + [
    (s, os.path.join(ROOT, "samples", s + ".rvt")) for s in
    ["rstbasicsampleproject", "rmebasicsampleproject", "racbasicsampleproject",
     "racadvancedsampleproject", "rstadvancedsampleproject", "dach-sample-project"]]

for name, path in targets:
    if not os.path.exists(path):
        continue
    order, etrow = load(path)
    pos = {e: i for i, e in enumerate(order)}
    by_ce = collections.defaultdict(list)
    for e in order:
        ce = etrow.get(e, (None,))[0]
        by_ce[ce].append(e)
    # (a) per-cohort id-ascending?  (b) contiguous?
    n_coh = len(by_ce)
    asc_ok = cont_ok = 0
    bad_asc = []
    for ce, ids in by_ce.items():
        asc = all(ids[i] < ids[i + 1] for i in range(len(ids) - 1))
        p = [pos[e] for e in ids]
        cont = (max(p) - min(p) + 1) == len(ids)
        asc_ok += asc
        cont_ok += cont
        if not asc and len(bad_asc) < 4:
            # count descents
            d = sum(1 for i in range(len(ids) - 1) if ids[i] > ids[i + 1])
            bad_asc.append((ce, len(ids), d))
    b0 = by_ce.get(0, [])
    b0_asc = all(b0[i] < b0[i + 1] for i in range(len(b0) - 1))
    b0_pos = [pos[e] for e in b0]
    b0_cont = (max(b0_pos) - min(b0_pos) + 1) == len(b0) if b0 else None
    b0_desc = sum(1 for i in range(len(b0) - 1) if b0[i] > b0[i + 1])
    print(f"{name:26s} cohorts {n_coh:>4}: id-ascending {asc_ok}/{n_coh}, "
          f"contiguous {cont_ok}/{n_coh}; BIRTH(ce=0) n={len(b0)} asc={b0_asc} "
          f"desc={b0_desc} contiguous={b0_cont} span [{min(b0_pos) if b0 else '-'}"
          f"..{max(b0_pos) if b0 else '-'}]/{len(order)}")
    if bad_asc:
        print(f"     non-ascending cohorts (ce, n, descents): {bad_asc}")
