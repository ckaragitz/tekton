import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document
from rvt.encode import ObjectEncoder
from rvt.validate import _RefDecoder, find_dangling_refs

RST = "samples/rstbasicsampleproject.rvt"
CLUSTER = [1410863, 1411267, 1411268] + list(range(1411269, 1411285)) + [1411287, 1411288, 1411406]
doc = Document.from_file(RST)
enc = ObjectEncoder()

# ---- roundtrip byte-exactness per element/seq
rt = {"exact": 0, "diff": [], "records": 0}
for eid in CLUSTER:
    for seq in (101, 102, 103):
        r = doc.record(eid, seq)
        if r is None:
            continue
        rt["records"] += 1
        o = doc.decode(eid, seq)
        if o is None or not (o.clean or getattr(o, "stub", False)):
            rt["diff"].append((eid, seq, "not clean"))
            continue
        try:
            body = enc.encode_object(r.class_id, o.value or {})
        except Exception as e:
            rt["diff"].append((eid, seq, f"encode {type(e).__name__}: {e}"))
            continue
        if body == r.payload:
            rt["exact"] += 1
        else:
            rt["diff"].append((eid, seq, f"len {len(body)} vs {len(r.payload)}"))
print("ROUNDTRIP:", json.dumps(rt, default=str)[:2000])

# ---- typed reference census, classified
schema = doc.dec.schema if hasattr(doc.dec, "schema") else None
dec = _RefDecoder(schema) if schema else None
cluster = set(CLUSTER)
host_ids = set(doc.et_by_id)
# embedded unit-36 range: measured donor famdoc ids
from rvt.families import FamilyIndex
idx = FamilyIndex(RST)
recs36 = idx.unit_records(36)
unit_ids = set(recs36.get(102, {}))
cls_count = {"cluster": {}, "embedded_unit36": {}, "host_shared": {}, "negative": {}, "not_resolvable": {}}
examples = {"embedded_unit36": [], "not_resolvable": []}
for eid in CLUSTER:
    for seq in (101, 102, 103):
        r = doc.record(eid, seq)
        if r is None:
            continue
        dec.refs = []
        try:
            dec.decode_record(r.class_id, r.payload)
        except Exception:
            continue
        for p, v in dec.refs:
            if v in cluster:
                b = "cluster"
            elif v in unit_ids:
                b = "embedded_unit36"
            elif v < 0:
                b = "negative"
            elif v in host_ids:
                b = "host_shared"
            else:
                b = "not_resolvable"
            key = f"{eid}.{seq}"
            cls_count[b][key] = cls_count[b].get(key, 0) + 1
            if b in examples and len(examples[b]) < 25:
                examples[b].append((eid, seq, p[-70:], v))
print("REF CENSUS totals:", {k: sum(v.values()) for k, v in cls_count.items()})
print("embedded examples:", json.dumps(examples["embedded_unit36"], default=str)[:1500])
print("not_resolvable:", json.dumps(examples["not_resolvable"], default=str)[:1500])
