"""M3 -- record-level forensic diff of a probe file vs K1: every stream
compared (inflated/logical), every unit-0 record compared per (seq, id),
and the differing records decoded and field-diffed."""
import os, sys, json
ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rvt.container import open_rvt
from rvt.partitions import StreamWalker
from rvt.objects import iter_records, ObjectDecoder
from rvt.encode import record_bytes
from rvt.stream_encoders import decode_elemtable

K1 = os.path.join(ROOT, "experiments/genesis/triage/K1.rvt")
DEC = ObjectDecoder()


def unit0(path):
    """{(seq,eid): framed bytes}, id order per seq, other-unit bytes, streams."""
    out = {}
    order = {}
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        logical = f.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        other_units = {}
        for b in sorted(w.blocks, key=lambda x: x.hdr_offset):
            if b.unit != 0:
                other_units.setdefault(b.unit, []).append(b.data)
        for seq in (101, 102, 103):
            seg = b"".join(b.data for b in u0 if b.seq == seq)
            ids = []
            for r in iter_records(seg, seq):
                fb = bytes(record_bytes(seg, r, seq))
                out[(seq, r.elem_id)] = fb
                if r.elem_id >= 0:
                    ids.append(r.elem_id)
            order[seq] = ids
        streams = {}
        for si in f.streams():
            s = si.name
            try:
                if s.startswith("Global/") or s in ("Formats/Latest", "Contents"):
                    streams[s] = f.inflate(s, 0) if s != "Contents" else f.logical(s)
                else:
                    streams[s] = f.logical(s)
            except Exception as e:
                streams[s] = ("ERR", repr(e))
        other_hash = {u: __import__("hashlib").sha256(b"".join(v)).hexdigest()[:16]
                      for u, v in other_units.items()}
    return out, order, streams, other_hash


def field_diff(a, b, path="", out=None, limit=40):
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append({"path": f"{path}.{k}", "ours": a.get(k, "<absent>"),
                            "k1": b.get(k, "<absent>")})
            else:
                field_diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": f"{path}[len]", "ours": len(a), "k1": len(b)})
        for i, (x, y) in enumerate(zip(a, b)):
            field_diff(x, y, f"{path}[{i}]", out, limit)
    else:
        if a != b:
            out.append({"path": path, "ours": repr(a)[:120], "k1": repr(b)[:120]})
    return out


def diff(probe_path, name):
    print(f"\n=================== {name} vs K1 ===================")
    A, ordA, sA, uhA = unit0(probe_path)
    B, ordB, sB, uhB = unit0(K1)
    # streams
    for s in sorted(set(sA) | set(sB)):
        a, b = sA.get(s), sB.get(s)
        if a == b:
            continue
        la = len(a) if isinstance(a, bytes) else a
        lb = len(b) if isinstance(b, bytes) else b
        print(f"  STREAM DIFF {s}: probe {la} vs K1 {lb}")
    print(f"  embedded units identical: {uhA == uhB} (probe units {sorted(uhA)}, k1 {sorted(uhB)})")
    # record sets
    keys = set(A) | set(B)
    added = sorted(k for k in A if k not in B)
    removed = sorted(k for k in B if k not in A)
    changed = sorted(k for k in keys if k in A and k in B and A[k] != B[k])
    print(f"  records: probe {len(A)} vs K1 {len(B)}; added {len(added)} removed "
          f"{len(removed)} changed {len(changed)}")
    for k in added[:12]:
        seq, eid = k
        cls = None
        r = A[k]
        print(f"    ADDED  seq{seq} id {eid} len {len(r)}")
    for k in removed[:12]:
        print(f"    REMOVED seq{k[0]} id {k[1]} len {len(B[k])}")
    for k in changed[:12]:
        seq, eid = k
        ra, rb = A[k], B[k]
        print(f"    CHANGED seq{seq} id {eid}: probe {len(ra)} B vs K1 {len(rb)} B; "
              f"first diff byte {next((i for i in range(min(len(ra),len(rb))) if ra[i]!=rb[i]), None)}")
        # decode both and field-diff (seq 101/102 only)
        if seq in (101, 102):
            hl = 12 if seq == 101 else 16
            import struct
            psA = struct.unpack_from('<I', ra, hl - 4)[0]
            psB = struct.unpack_from('<I', rb, hl - 4)[0]
            cidA = struct.unpack_from('<H', ra, hl)[0]
            cidB = struct.unpack_from('<H', rb, hl)[0]
            bodyA = ra[hl + 2: hl + psA]
            bodyB = rb[hl + 2: hl + psB]
            dA = DEC.decode_record(cidA, bodyA)
            dB = DEC.decode_record(cidB, bodyB)
            print(f"      classes: probe {DEC.class_name(cidA)} clean={dA.clean} | K1 {DEC.class_name(cidB)} clean={dB.clean}")
            fd = field_diff(dA.value, dB.value)
            for d in fd[:25]:
                print(f"        {d['path']}: probe={str(d['ours'])[:70]}  K1={str(d['k1'])[:70]}")
            if len(fd) > 25:
                print(f"        ... {len(fd)-25} more field diffs")
    # id ORDER comparison for the touched seqs
    for seq in (101, 102, 103):
        oa, ob = ordA[seq], ordB[seq]
        if oa == ob:
            print(f"  seq{seq}: id ORDER IDENTICAL to K1's ({len(oa)} ids)")
        else:
            # where do they differ?
            sa, sb = set(oa), set(ob)
            common = [x for x in oa if x in sb]
            commonB = [x for x in ob if x in sa]
            print(f"  seq{seq}: id order DIFFERS; common-order preserved: {common == commonB}; "
                  f"probe extra {sorted(sa - sb)[:6]} at positions "
                  f"{[oa.index(x) for x in sorted(sa - sb)[:6]]} of {len(oa)}; "
                  f"K1 extra {sorted(sb - sa)[:6]} at positions {[ob.index(x) for x in sorted(sb - sa)[:6]]} of {len(ob)}")


if __name__ == "__main__":
    for name in sys.argv[1:]:
        if os.path.exists(name):
            diff(name, os.path.basename(name))
