"""M4 -- is the Partitions re-blocking byte-clean?  Compare X_pen's block
sequence vs K1's: per-block payload identity, so we know the ONLY change is
element 2's object.  Also dump the full pen vectors of both."""
import os, sys, struct
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt.container import open_rvt
from rvt.partitions import StreamWalker
from rvt.objects import iter_records, ObjectDecoder

K1 = os.path.join(ROOT, "experiments/genesis/triage/K1.rvt")
XPEN = os.path.join(ROOT, "experiments/genesis/subst_v2/X_pen.rvt")


def blocks(path):
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        bl = sorted(w.blocks, key=lambda x: x.hdr_offset)
        return [(b.unit, b.seq, b.flags, b.n_records, len(b.data), b.data) for b in bl]


A = blocks(XPEN)
B = blocks(K1)
print("block counts:", len(A), len(B))
diffs = 0
for i, (a, b) in enumerate(zip(A, B)):
    same_meta = a[:5] == b[:5]
    same_data = a[5] == b[5]
    if not (same_meta and same_data):
        diffs += 1
        print(f"  block {i}: unit={a[0]} seq={a[1]} flags={a[2]} A={a[3]} len={a[4]} | "
              f"K1 unit={b[0]} seq={b[1]} flags={b[2]} A={b[3]} len={b[4]} | data_equal={same_data}")
print(f"blocks differing: {diffs} of {len(B)}")

# full pen vectors
DEC = ObjectDecoder()


def pen(path):
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        seg = b"".join(b.data for b in u0 if b.seq == 102)
        for r in iter_records(seg, 102):
            if r.elem_id == 2:
                o = DEC.decode_record(r.class_id, r.payload)
                return o.value["m_pPenWidthTable"]["value"]


pa, pb = pen(XPEN), pen(K1)
MM = 304.8
for label, t in (("X_pen(ours)", pa), ("K1", pb)):
    print(f"\n== {label}")
    for p in t["m_modelPenInfo"]:
        print(f"  scale 1:{p['m_invertedScale']:>4}: mm=", [round(x * MM, 4) for x in p["m_pens"]])
    print("  perspective mm=", [round(x * MM, 4) for x in t["m_perspectiveModelPenInfo"]["m_pens"]],
          "invsc", t["m_perspectiveModelPenInfo"]["m_invertedScale"])
    print("  draft       mm=", [round(x * MM, 4) for x in t["m_draftPenInfo"]["m_pens"]],
          "invsc", t["m_draftPenInfo"]["m_invertedScale"])
# monotonicity check on ours
def mono(v):
    return all(v[i] <= v[i + 1] for i in range(len(v) - 1))
print("\nours monotone per vector:",
      [mono(p["m_pens"]) for p in pa["m_modelPenInfo"]],
      mono(pa["m_perspectiveModelPenInfo"]["m_pens"]), mono(pa["m_draftPenInfo"]["m_pens"]))
print("K1   monotone per vector:",
      [mono(p["m_pens"]) for p in pb["m_modelPenInfo"]],
      mono(pb["m_perspectiveModelPenInfo"]["m_pens"]), mono(pb["m_draftPenInfo"]["m_pens"]))
# other pen-table fields
for k in pa:
    if k not in ("m_modelPenInfo", "m_perspectiveModelPenInfo", "m_draftPenInfo"):
        print("other field", k, "ours=", pa.get(k), "K1=", pb.get(k))
