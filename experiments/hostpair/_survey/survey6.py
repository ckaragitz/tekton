import json, sys
sys.path.insert(0, "src")
from rvt.mutate import Document
from rvt.families import FamilyIndex

RST = "samples/rstbasicsampleproject.rvt"
CLUSTER = [1410863, 1411267, 1411268] + list(range(1411269, 1411285)) + [1411287, 1411288, 1411406]
doc = Document.from_file(RST)
idx = FamilyIndex(RST)
unit_ids = set(idx.unit_records(36).get(102, {}))
print("unit36 ids:", min(unit_ids), max(unit_ids), len(unit_ids))
cluster = set(CLUSTER)

hits = []
def scan(node, path, eid):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, int) and v in unit_ids:
                hits.append((eid, path + "." + k, v))
            else:
                scan(v, path + "." + k, eid)
    elif isinstance(node, list):
        for j, v in enumerate(node):
            if isinstance(v, bool):
                continue
            if isinstance(v, int) and v in unit_ids:
                hits.append((eid, f"{path}[{j}]", v))
            else:
                scan(v, f"{path}[{j}]", eid)

for eid in CLUSTER:
    for seq in (101, 102, 103):
        v = doc.value(eid, seq)
        if isinstance(v, dict):
            scan(v, f"{eid}.s{seq}", eid)

byfield = {}
for eid, p, v in hits:
    import re
    key = re.sub(r"\[\d+\]", "[]", p.split(".", 1)[1] if "." in p else p)
    key = f"{eid}:{key}"
    byfield[key] = byfield.get(key, 0) + 1
print("EMBEDDED-ID hits by (elem, field-shape):")
for k in sorted(byfield):
    print(" ", k, byfield[k])
print("total", len(hits))
