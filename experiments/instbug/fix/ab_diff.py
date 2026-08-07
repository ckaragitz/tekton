#!/usr/bin/env python
"""Exhaustive structural diff of the A/B order-experiment pair.

A = AB_A_wallsfirst.rvt (PASS shape), B = AB_B_loadfirst.rvt (FAIL shape).
Same final content; report every structural difference, normalized by role.
"""
from __future__ import annotations

import json
import os
import sys
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.container import open_rvt          # noqa: E402
from rvt.partitions import StreamWalker     # noqa: E402
from rvt.elemtable import parse_elemtable   # noqa: E402
from rvt import adocument as A              # noqa: E402
from rvt.mutate import Document             # noqa: E402

PA = os.path.join(HERE, "AB_A_wallsfirst.rvt")
PB = os.path.join(HERE, "AB_B_loadfirst.rvt")


def stream_inventory(path):
    out = {}
    with open_rvt(path) as f:
        for s in f.streams():
            raw = f.raw(s.name)
            out[s.name] = (len(raw), hashlib.md5(raw).hexdigest()[:10])
    return out


def unit0_records(path):
    """Per seq: ordered list of (elem_id, class_id, psize)."""
    from rvt.objects import iter_records
    with open_rvt(path) as f:
        pn = f.partition_streams()[0]
        logical = f.logical(pn)
    w = StreamWalker(logical, inflate=True, keep_data=True)
    per = {}
    for seq in (101, 102, 103):
        seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset)
                       if b.unit == 0 and b.seq == seq)
        per[seq] = [(r.elem_id, r.class_id, r.body_size) for r in iter_records(seg, seq)]
    return per, w


def elemtable(path):
    with open_rvt(path) as f:
        et = parse_elemtable(f.inflate("Global/ElemTable", 0))
    rows = [(r.id, r.original_id, r.creation_ep, r.modified_ep, r.user_modified_ep,
             r.owner_id, r.partition_id) for r in et.records]
    return rows, et


def latest(path):
    with open_rvt(path) as f:
        return A.decode_latest(f.inflate("Global/Latest"))


def leaf_diff(a, b, path="", out=None, maxn=400):
    if out is None:
        out = []
    if len(out) >= maxn:
        return out
    if type(a) is not type(b):
        out.append((path, f"TYPE {type(a).__name__} vs {type(b).__name__}"))
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append((f"{path}.{k}", "MISSING in A"))
            elif k not in b:
                out.append((f"{path}.{k}", "MISSING in B"))
            else:
                leaf_diff(a[k], b[k], f"{path}.{k}", out, maxn)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((path, f"LEN {len(a)} vs {len(b)}"))
            return out
        for i, (x, y) in enumerate(zip(a, b)):
            leaf_diff(x, y, f"{path}[{i}]", out, maxn)
    else:
        if a != b:
            out.append((path, f"{a!r} vs {b!r}"))
    return out


def main():
    build = json.load(open(os.path.join(HERE, "ab_build.json")))
    # role maps: id -> role token
    role_a, role_b = {}, {}

    def add_roles(m, plan, twins):
        m[plan["host_family_id"]] = "FAM"
        m[plan["surrogate_id"]] = "FSUR"
        m[plan["symbol_id"]] = "SYM"
        m[plan["symbol_surrogate_id"]] = "SSUR"
        for i, (emb, tw) in enumerate(sorted(twins.items(), key=lambda kv: int(kv[1]))):
            m[int(tw)] = f"TWIN{i}"
    add_roles(role_a, build["A"]["plan"], build["A"]["twins"])
    add_roles(role_b, build["B"]["plan"], build["B"]["twins"])
    # walls
    da, db = Document.from_file(PA), Document.from_file(PB)
    walls_a = sorted(da.ids_of_class("SWall"))
    walls_b = sorted(db.ids_of_class("SWall"))
    for i, w in enumerate(walls_a):
        role_a[w] = f"WALL{i}"
    for i, w in enumerate(walls_b):
        role_b[w] = f"WALL{i}"
    # embedded doc id ranges (box document)
    pa_lo = min(int(k) for k in build["A"]["twins"])  # embedded param ids are in doc range
    pb_lo = min(int(k) for k in build["B"]["twins"])

    def role(m, eid, lo, hi):
        if eid in m:
            return m[eid]
        if lo <= eid <= hi:
            return f"DOC+{eid - lo}"
        return str(eid)

    print("=" * 90)
    print("1. STREAM INVENTORY")
    ia, ib = stream_inventory(PA), stream_inventory(PB)
    for name in sorted(set(ia) | set(ib)):
        la, lb = ia.get(name), ib.get(name)
        mark = " " if la == lb else "X"
        print(f" {mark} {name:38s} A={la} B={lb}")

    print("=" * 90)
    print("2. UNIT-0 RECORD ORDER (tail 40 records per seq, role-normalized)")
    ra, wa = unit0_records(PA)
    rb, wb = unit0_records(PB)
    # doc id ranges from load jsons
    hi_a = min(build["A"]["plan"][k] for k in ("host_family_id",)) - 1
    hi_b = min(build["B"]["plan"][k] for k in ("host_family_id",)) - 1
    lo_a = 1472525  # walls_only wm + 1 (box doc start, A)
    lo_b = 1472521  # ZA wm + 1 (box doc start, B)
    for seq in (101, 102, 103):
        ta = [(role(role_a, e, lo_a, hi_a), c) for e, c, _ in ra[seq]]
        tb = [(role(role_b, e, lo_b, hi_b), c) for e, c, _ in rb[seq]]
        print(f"  seq {seq}: A n={len(ta)} B n={len(tb)}")
        print("    A tail:", ta[-14:])
        print("    B tail:", tb[-14:])
        if [x for x in ta if not x[0].isdigit()] != [x for x in tb if not x[0].isdigit()]:
            print("    >>> ROLE-SEQUENCE DIFFERS (new records in different order)")

    print("=" * 90)
    print("3. ELEMTABLE (added rows, role-normalized; order position in table)")
    ea, eta = elemtable(PA)
    eb, etb = elemtable(PB)
    pos_a = {r[0]: i for i, r in enumerate(ea)}
    pos_b = {r[0]: i for i, r in enumerate(eb)}
    rows_a = {role(role_a, r[0], lo_a, hi_a): r for r in ea if r[0] >= 1472500}
    rows_b = {role(role_b, r[0], lo_b, hi_b): r for r in eb if r[0] >= 1472500}
    for k in sorted(set(rows_a) | set(rows_b)):
        va, vb = rows_a.get(k), rows_b.get(k)
        fa = (f"pos={pos_a.get(va[0])} ce={va[2]} me={va[3]} ue={va[4]} own={va[5]:x} part={va[6]}" if va else "MISSING")
        fb = (f"pos={pos_b.get(vb[0])} ce={vb[2]} me={vb[3]} ue={vb[4]} own={vb[5]:x} part={vb[6]}" if vb else "MISSING")
        mark = " " if (va and vb and va[2:] == vb[2:]) else "X"
        print(f" {mark} {k:8s} A[{fa}] B[{fb}]")
    print(f"  footer A last_id={eta.footer.last_id} B last_id={etb.footer.last_id}")
    print(f"  n_records A={len(ea)} B={len(eb)}")

    print("=" * 90)
    print("4. LATEST (registries + full leaf diff, id-blind on our ids)")
    la, lb = latest(PA), latest(PB)
    va, vb = la.value, lb.value

    def norm(v, m, lo, hi):
        import copy
        v = copy.deepcopy(v)

        def walk(n):
            if isinstance(n, dict):
                for k, x in list(n.items()):
                    if isinstance(x, bool):
                        continue
                    if isinstance(x, int) and (x in m or lo <= x <= hi):
                        n[k] = role(m, x, lo, hi)
                    elif isinstance(x, str) and len(x) == 36 and x.count("-") == 4:
                        n[k] = "GUID"
                    else:
                        walk(x)
            elif isinstance(n, list):
                for i, x in enumerate(n):
                    if isinstance(x, bool):
                        continue
                    if isinstance(x, int) and (x in m or lo <= x <= hi):
                        n[i] = role(m, x, lo, hi)
                    elif isinstance(x, str) and len(x) == 36 and x.count("-") == 4:
                        n[i] = "GUID"
                    else:
                        walk(x)
        walk(v)
        return v
    na = norm(va, role_a, lo_a, hi_a)
    nb = norm(vb, role_b, lo_b, hi_b)
    diffs = leaf_diff(na, nb)
    print(f"  leaf diffs: {len(diffs)}")
    for p, d in diffs[:60]:
        print(f"   {p}: {d}")

    print("=" * 90)
    print("5. CONTENTDOCUMENTS raw")
    with open_rvt(PA) as f:
        cda = b"".join(f.inflate_all("Global/ContentDocuments"))
    with open_rvt(PB) as f:
        cdb = b"".join(f.inflate_all("Global/ContentDocuments"))
    print(f"  A len={len(cda)} B len={len(cdb)} equal_len={len(cda)==len(cdb)}")
    # compare structure ignoring the GUID bytes + adoc payload
    print("  A head:", cda[:64].hex())
    print("  B head:", cdb[:64].hex())
    print("  A tail:", cda[-20:].hex())
    print("  B tail:", cdb[-20:].hex())

    print("=" * 90)
    print("6. PARTITION LAYOUT (units, blocks, tail)")
    for lbl, (r, w) in (("A", (ra, wa)), ("B", (rb, wb))):
        print(f"  {lbl}: units={len(w.units)} end_off={w.end_offset} end_len={len(w.end_record)}")
    print("  A end_record[68:100]:", wa.end_record[68:100].hex())
    print("  B end_record[68:100]:", wb.end_record[68:100].hex())

    print("=" * 90)
    print("7. WALL RECORD BYTES (role-matched, id-masked)")
    from rvt.objects import iter_records
    def recs_by_id(path):
        with open_rvt(path) as f:
            pn = f.partition_streams()[0]
            logical = f.logical(pn)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        per = {}
        for seq in (101, 102, 103):
            seg = b"".join(b.data for b in sorted(w.blocks, key=lambda x: x.hdr_offset)
                           if b.unit == 0 and b.seq == seq)
            for r in iter_records(seg, seq):
                per[(seq, r.elem_id)] = seg[r.seg_offset:r.seg_offset + (16 if seq == 101 else 20) + r.body_size - (4 if seq == 101 else 4)]
        return per
    rba, rbb = recs_by_id(PA), recs_by_id(PB)
    for i in range(4):
        wa_id, wb_id = walls_a[i], walls_b[i]
        for seq in (101, 102, 103):
            xa, xb = rba.get((seq, wa_id)), rbb.get((seq, wb_id))
            same_len = xa is not None and xb is not None and len(xa) == len(xb)
            print(f"  WALL{i} seq{seq}: A len={len(xa) if xa else None} B len={len(xb) if xb else None} same_len={same_len}")


if __name__ == "__main__":
    main()
