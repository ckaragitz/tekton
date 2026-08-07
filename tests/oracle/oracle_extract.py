"""oracle_extract.py -- summarise everything we can currently read from a .rvt
WITHOUT full object decoding, for any Revit release (2023/2024/2026 verified).

    .venv/bin/python tests/oracle/oracle_extract.py <file.rvt> [--refresh]
                                                             [--json out.json]

Produces (and caches under tests/oracle/cache/<basename>.rvt.summary.json):

  * meta      release / build / GUIDs from BasicFileInfo (rvt.meta)
  * streams   OLE stream inventory + gzip member/CRC health (rvt.container)
  * schema    the file's OWN Formats/Latest parsed with the wave-1 grammar
              (release-independent): class count, framing tags by name
  * elemtable Global/ElemTable ids (64-bit >=2024, 32-bit <=2023 records)
  * partitions per Partitions/<N>: framing walk (blocks, CRC), and per-seq
              record counts BY CLASS NAME (class_word -> schema name), record
              id sets, id-width auto-detected (u32 <=2023, i64 >=2024)
  * strings   decoded UTF-16 / ASCII strings from Global/* and the partition
              record bodies, attributed to the record class they live in,
              classified (name / path / guid / schema noise) via
              rvt.strings_scan.classify

The summary JSON is the cheap-to-reload input for compare_oracle.py.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import struct
import sys
import time
import zipfile
import io

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

from rvt.container import open_rvt  # noqa: E402
from rvt import meta as M  # noqa: E402
from rvt import strings_scan as SS  # noqa: E402
import rvt_release as R  # noqa: E402

CACHE_DIR = R.CACHE_DIR

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

RE_U16 = SS.RE_U16          # UTF-16LE ascii-ish runs >= 4 chars
RE_ASC = SS.RE_ASC          # ascii runs >= 5 chars


def file_key(path: str) -> str:
    st = os.stat(path)
    h = hashlib.sha256(f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()
    return f"{os.path.basename(path)}.{h[:10]}"


def cache_path(path: str) -> str:
    return os.path.join(CACHE_DIR, f"{file_key(path)}.summary.json")


# --------------------------------------------------------------------------
# ElemTable (release-aware: 40-byte recs >= 2024, 28-byte recs <= 2023)
# --------------------------------------------------------------------------

def parse_elemtable_any(payload: bytes) -> dict:
    """Return {class_tag, count, rec_size, ids} choosing 40- vs 28-byte recs."""
    if len(payload) < 6:
        return {"error": "short"}
    class_tag, count = struct.unpack_from("<HI", payload, 0)
    # >=2024 (64-bit ElementId): {u64 orig, u32 ce, u32 me, u32 ue, u64 id, i64 owner, u32 part} = 40 B
    # <=2023 (32-bit ElementId): {u32 orig, u32 id, u32 ce, u32 me, u32 ue, u32 part, i32 owner} = 28 B
    for rec_size, fmt, id_idx in ((40, "<QIIIQqI", 4), (28, "<IIIIIIi", 1)):
        need = 6 + count * rec_size
        if len(payload) >= need and len(payload) - need < 64:
            ids = []
            off = 6
            up = struct.Struct(fmt).unpack_from
            for _ in range(count):
                vals = up(payload, off)
                ids.append(vals[id_idx])     # m_id
                off += rec_size
            return {"class_tag": class_tag, "count": count, "rec_size": rec_size,
                    "id_width": 8 if rec_size == 40 else 4,
                    "ids_sorted": all(ids[i] < ids[i + 1] for i in range(len(ids) - 1)),
                    "id_min": min(ids) if ids else None,
                    "id_max": max(ids) if ids else None,
                    "ids": ids, "trailer_len": len(payload) - need}
    return {"class_tag": class_tag, "count": count, "error": "no record size fits",
            "payload_len": len(payload)}


# --------------------------------------------------------------------------
# record layout detection (u32 ids <= 2023, i64 ids >= 2024)
# --------------------------------------------------------------------------

def _try_layout(seg: bytes, fmt: str, tail: int = 0):
    st = struct.Struct(fmt)
    hl = st.size
    p = 0
    n = len(seg)
    recs = 0
    while p + hl <= n:
        vals = st.unpack_from(seg, p)
        size = vals[-2]
        if size > (1 << 26) or size > n:
            break
        recs += 1
        p += hl + size + tail
    return p, recs


def detect_record_layout(seg: bytes, seq: int) -> str:
    """Return a struct format for one record header of this seq segment.

    Candidates (little-endian):
        seq 101 : '<qII' (i64 id, u32 size, u32 cls)  [>=2024]
                  '<III' (u32 id, u32 size, u32 cls)  [<=2023]
        seq 10x : '<qIII' (i64 id, u32 stamp, u32 size, u32 cls) [>=2024]
                  '<IIII' (u32 id, u32 stamp, u32 size, u32 cls) [<=2023]
    The layout that walks the whole segment (coverage == len) wins.
    """
    if not seg:
        return "<qII" if seq == 101 else "<qIII"
    cands = ["<qII", "<III"] if seq == 101 else ["<qIII", "<IIII"]
    best, best_cov, best_n = cands[0], -1.0, -1
    for fmt in cands:
        cov, n = _try_layout(seg, fmt)
        c = cov / len(seg)
        if c > best_cov or (c == best_cov and n > best_n):
            best, best_cov, best_n = fmt, c, n
    return best


def iter_records(seg: bytes, seq: int, fmt: str):
    st = struct.Struct(fmt)
    hl = st.size
    p = 0
    n = len(seg)
    while p + hl <= n:
        vals = st.unpack_from(seg, p)
        eid = vals[0]
        size = vals[-2]
        cls = vals[-1] & 0xFFFF
        stamp = vals[1] if len(vals) == 4 else None
        if size > (1 << 26) or size > n:
            return
        yield eid, stamp, size, cls, p, hl
        p += hl + size


# --------------------------------------------------------------------------
# string scanning
# --------------------------------------------------------------------------

def _clean(t: str) -> str:
    return t.strip().strip("\x00")


def scan_strings(data: bytes, minu: int = 4):
    """Yield (offset, encoding, text) for UTF-16LE and ASCII runs."""
    for m in RE_U16.finditer(data):
        t = m.group().decode("utf-16-le", "replace")
        yield m.start(), "utf16", t
    for m in RE_ASC.finditer(data):
        yield m.start(), "ascii", m.group().decode("ascii", "replace")


def interesting(t: str) -> bool:
    t = _clean(t)
    if len(t) < 3:
        return False
    # drop obvious binary garbage: mostly punctuation
    letters = sum(ch.isalnum() for ch in t)
    return letters >= max(2, len(t) // 3)


# --------------------------------------------------------------------------
# main extraction
# --------------------------------------------------------------------------

def extract(path: str, refresh: bool = False, quiet: bool = False) -> dict:
    cp = cache_path(path)
    if not refresh and os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)
    t0 = time.time()
    log = (lambda *a: None) if quiet else (lambda *a: print(*a, file=sys.stderr))
    doc = open_rvt(path)
    out: dict = {"file": os.path.abspath(path), "basename": os.path.basename(path)}

    # -- meta ---------------------------------------------------------------
    bfi = M.parse_basic_file_info(doc.raw("BasicFileInfo"))
    release = str(bfi.get("format") or bfi.get("version") or "?")
    out["meta"] = {
        "release": release,
        "build": bfi.get("build"),
        "path": bfi.get("path"),
        "worksharing": bfi.get("worksharing"),
        "structure_version": bfi.get("structure_version"),
        "guids": bfi.get("guids"),
        "central_version_number": bfi.get("central_version_number"),
    }
    log(f"[extract] {os.path.basename(path)} release={release} build={bfi.get('build')}")

    # ProjectInformation (partatom zip) values -> project name etc.
    proj_vals = []
    try:
        pi = doc.raw("ProjectInformation")
        zf = zipfile.ZipFile(io.BytesIO(pi))
        xml = zf.read(zf.namelist()[0]).decode("utf-8", "replace")
        for m in re.finditer(r">([^<>]{2,})<", xml):
            v = m.group(1).strip()
            if v:
                proj_vals.append(v)
        out["meta"]["project_information"] = proj_vals[:60]
    except Exception as e:  # noqa: BLE001
        out["meta"]["project_information_error"] = str(e)

    # -- streams ------------------------------------------------------------
    streams = []
    for s in doc.streams():
        mem = doc.members(s.name)
        streams.append({
            "name": s.name, "raw_size": s.size,
            "members": len(mem),
            "inflated": sum(m.inflated for m in mem),
            "all_crc_ok": all(m.crc_ok for m in mem) if mem else None,
        })
    out["streams"] = streams

    # -- schema (own Formats/Latest) ---------------------------------------
    cm = R.class_map(doc, release)
    tags = R.framing_tags(cm)
    out["schema"] = {
        "sha256": cm.sha256, "inflated_size": cm.inflated_size,
        "n_classes": cm.n_classes, "n_fields": cm.n_fields,
        "parsed_bytes": cm.parsed_bytes,
        "parsed_fraction": round(cm.parsed_bytes / max(cm.inflated_size, 1), 4),
        "desync": cm.desync,
        "framing_tags": {"block_SegmentMarker": tags.block,
                         "trailer_SegmentCheckback": tags.trailer,
                         "footer_SignatureMarker": tags.footer,
                         "container_ContentMarker": tags.container,
                         "inner_ContentKey": tags.inner,
                         "source": tags.source},
        "key_class_ids": {n: cm.name_to_id.get(n) for n in (
            "ADocument", "ElemTable", "DocumentHistory", "DocumentIncrementTable",
            "ContentMarker", "SegmentMarker", "SerializedDummy", "GElement",
            "ElementHeader", "Wall", "SWall", "Level", "FamilyInstance",
            "Floor", "RoomElem", "Symbol", "FamilySymbol", "WallType",
            "CurtainGridLine", "GStyleElem", "CategoryElem")},
    }
    log(f"[extract] schema: {cm.n_classes} classes, {cm.n_fields} fields, "
        f"parsed {out['schema']['parsed_fraction']:.1%}, block tag 0x{tags.block:x}")

    # -- elemtable ---------------------------------------------------------
    try:
        payload = b"".join(doc.inflate_all("Global/ElemTable"))
        et = parse_elemtable_any(payload)
        ids = et.pop("ids", [])
        et["class_tag_name"] = cm.name(et.get("class_tag", -1)) if "class_tag" in et else None
        out["elemtable"] = et
        out["elemtable_ids"] = ids
        log(f"[extract] elemtable: count={et.get('count')} rec_size={et.get('rec_size')} "
            f"id range {et.get('id_min')}..{et.get('id_max')}")
    except Exception as e:  # noqa: BLE001
        out["elemtable"] = {"error": str(e)}
        out["elemtable_ids"] = []

    # -- partitions --------------------------------------------------------
    parts = []
    class_word_counts: collections.Counter = collections.Counter()      # seq102 (objects)
    class_word_counts_101: collections.Counter = collections.Counter()
    class_word_counts_103: collections.Counter = collections.Counter()
    record_ids_102: set = set()
    id_to_cls_102: dict = {}
    string_records: dict = collections.defaultdict(list)   # text -> [(seq,cls,eid)]
    class_strings: dict = collections.defaultdict(collections.Counter)  # clsname -> text counter
    total_records = 0
    id_width = None
    for sname in doc.partition_streams():
        clean = R.depage(doc.raw(sname))
        pp = R.walk_partition(clean, tags)
        pinfo = {
            "name": sname,
            "raw_size": len(doc.raw(sname)), "clean_size": len(clean),
            "header": {"version": pp.header.version,
                       "class_ordinal": pp.header.class_ordinal,
                       "class_name": cm.name(pp.header.class_ordinal),
                       "elem_count_field": pp.header.elem_table_count},
            "n_blocks": len(pp.blocks),
            "blocks_crc_ok": sum(1 for b in pp.blocks if b.crc_ok),
            "blocks_isize_ok": sum(1 for b in pp.blocks if len(b.data) == b.intended_len),
            "n_units": pp.n_units,
            "walk_errors": pp.errors[:5],
            "seqs": {},
        }
        for seq in pp.seqs():
            seg = pp.segment(seq)
            fmt = detect_record_layout(seg, seq)
            if id_width is None:
                id_width = 8 if fmt.startswith("<q") else 4
            cnt: collections.Counter = collections.Counter()
            nrec = 0
            endp = 0
            ids = set()
            for eid, stamp, size, cls, off, hl in iter_records(seg, seq, fmt):
                nrec += 1
                cnt[cls] += 1
                ids.add(eid)
                endp = off + hl + size
                if seq == 102:
                    id_to_cls_102[eid] = cls
                    # strings inside the element object body
                    body = seg[off + hl: off + hl + size]
                    if size >= 8:
                        clsname = cm.name(cls)
                        for m in RE_U16.finditer(body):
                            t = _clean(m.group().decode("utf-16-le", "replace"))
                            if interesting(t):
                                if len(string_records[t]) < 4:
                                    string_records[t].append((seq, cls, eid))
                                class_strings[clsname][t] += 1
            pinfo["seqs"][str(seq)] = {
                "layout": fmt, "segment_len": len(seg),
                "walked": endp, "walk_complete": endp == len(seg),
                "records": nrec, "distinct_ids": len(ids),
                "class_counts": {cm.name(k): v for k, v in cnt.most_common()},
            }
            if seq == 101:
                class_word_counts_101.update(cnt)
            elif seq == 102:
                class_word_counts.update(cnt)
                record_ids_102 |= ids
            else:
                class_word_counts_103.update(cnt)
            total_records += nrec
        parts.append(pinfo)
        log(f"[extract] {sname}: blocks={len(pp.blocks)} crc_ok="
            f"{pinfo['blocks_crc_ok']} records(seq102)="
            f"{pinfo['seqs'].get('102', {}).get('records')}")
    out["partitions"] = parts
    out["id_width_bytes"] = id_width
    # LIVE class census: only ids present in Global/ElemTable are current
    # elements; partition streams also retain superseded object versions and
    # graveyard records from earlier save units.  Count each live id once by
    # the class of its latest (last-written) seq102 record.
    live_ids = set(out.get("elemtable_ids") or [])
    live = collections.Counter(cm.name(id_to_cls_102[i]) for i in live_ids if i in id_to_cls_102)
    out["class_counts_live"] = dict(live.most_common())
    out["class_counts_latest_all"] = dict(collections.Counter(
        cm.name(c) for c in id_to_cls_102.values()).most_common())
    out["live_ids_in_records"] = sum(live.values())
    out["live_ids_total"] = len(live_ids)
    out["class_word_counts_seq102"] = {cm.name(k): v for k, v in class_word_counts.most_common()}
    out["class_word_counts_seq101"] = {cm.name(k): v for k, v in class_word_counts_101.most_common()}
    out["class_word_counts_seq103"] = {cm.name(k): v for k, v in class_word_counts_103.most_common()}
    out["record_ids_seq102"] = sorted(record_ids_102)
    out["id_to_cls_seq102"] = {str(k): cm.name(v) for k, v in id_to_cls_102.items()}
    out["total_records"] = total_records

    # -- strings from Global/* + raw metadata --------------------------------
    global_strings: collections.Counter = collections.Counter()
    string_streams: dict = collections.defaultdict(set)
    for sname in ("Global/Latest", "Global/ContentDocuments", "Global/PartitionTable"):
        if not doc.has(sname):
            continue
        try:
            blob = b"".join(doc.inflate_all(sname))
        except Exception:  # noqa: BLE001
            continue
        for off, enc, t in scan_strings(blob):
            t = _clean(t)
            if interesting(t):
                global_strings[t] += 1
                if len(string_streams[t]) < 3:
                    string_streams[t].add(sname)
    # attributed record strings (seq102) also count
    for t, recs in string_records.items():
        global_strings[t] += len(recs)

    # classify + keep the name-like ones, plus everything for lookup
    names = []
    for t, n in global_strings.most_common():
        klass = SS.classify(t)
        # strings_scan.classify() calls anything containing '"' schema/json;
        # rescue human names like '8" Interior Partition' (inch marks).
        if klass == "schema" and not any(tok in t for tok in ("{", "}", "[", "]", "\":", "<", ">", "xml")):
            klass = "name"
        if klass in ("name", "path", "guid", "unit", "version") or n >= 2:
            names.append({"text": t, "count": n, "class": klass,
                          "streams": sorted(string_streams.get(t, set())),
                          "records": [[cm.name(c), eid] for (_, c, eid) in string_records.get(t, [])][:3]})
    out["strings"] = {
        "total_distinct": len(global_strings),
        "kept": len(names),
        "items": names[:6000],
        "class_strings_top": {k: [t for t, _ in v.most_common(15)]
                              for k, v in sorted(class_strings.items())
                              if k in ("SWall", "Wall", "WallType", "SWallType", "Level",
                                       "FamilyInstance", "FamilySymbol", "Symbol",
                                       "Floor", "FloorType", "RoomElem", "Grid",
                                       "MaterialElem", "AppearanceAssetElem",
                                       "GridType", "ViewSheet", "DBViewType") },
    }
    log(f"[extract] strings: {len(global_strings)} distinct, kept {len(names)}")

    out["timing_s"] = round(time.time() - t0, 2)
    doc.close()
    with open(cp, "w") as f:
        json.dump(out, f)
    log(f"[extract] cached -> {cp} ({out['timing_s']}s)")
    return out


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def print_summary(s: dict, top: int = 25) -> None:
    m = s["meta"]
    print(f"== {s['basename']}  Revit {m['release']}  build {m['build']}")
    print(f"   doc guid {(m.get('guids') or {}).get('unique_document_guid')}  "
          f"central v{m.get('central_version_number')}  id_width={s.get('id_width_bytes')}B")
    sc = s["schema"]
    print(f"   schema: {sc['inflated_size']:,} B, {sc['n_classes']:,} classes, "
          f"{sc['n_fields']:,} fields, grammar-parsed {sc['parsed_fraction']:.1%}"
          f"{' (desync: ' + sc['desync'].split(':')[0] + ')' if sc['desync'] else ''}")
    ft = sc["framing_tags"]
    print(f"   framing: SegmentMarker=0x{ft['block_SegmentMarker']:x} "
          f"SegmentCheckback=0x{ft['trailer_SegmentCheckback']:x} "
          f"SignatureMarker=0x{ft['footer_SignatureMarker']:x} "
          f"ContentMarker=0x{ft['container_ContentMarker']:x}")
    et = s.get("elemtable", {})
    print(f"   ElemTable: count={et.get('count')} rec={et.get('rec_size')}B "
          f"ids {et.get('id_min')}..{et.get('id_max')} class_tag=0x{et.get('class_tag', 0):x}"
          f" ({et.get('class_tag_name')})")
    print(f"   streams ({len(s['streams'])}): " +
          ", ".join(f"{x['name']}[{x['members']}m{'' if x['all_crc_ok'] in (True, None) else '!'}]"
                    for x in s["streams"]))
    print(f"   partitions: {len(s['partitions'])}, total records {s['total_records']:,}")
    for p in s["partitions"]:
        q = p["seqs"].get("102", {})
        print(f"     {p['name']:16s} blocks={p['n_blocks']:4d} crc_ok={p['blocks_crc_ok']:4d} "
              f"units={p['n_units']:3d} elem_field={p['header']['elem_count_field']:6d} "
              f"seq102 recs={q.get('records', 0):6d} walk={'OK ' if q.get('walk_complete') else 'BAD'} "
              f"errs={len(p['walk_errors'])}")
    print(f"   seq102 object records by class ({sum(s['class_word_counts_seq102'].values()):,} raw / "
          f"{s.get('live_ids_in_records', 0):,} live-in-ElemTable):")
    live = s.get("class_counts_live", {})
    for name, n in list(s["class_word_counts_seq102"].items())[:top]:
        print(f"     {n:7d} raw  {live.get(name, 0):7d} live  {name}")
    print(f"   seq101 classes: {dict(list(s['class_word_counts_seq101'].items())[:3])}")
    print(f"   seq103 classes: {dict(list(s['class_word_counts_seq103'].items())[:3])}")
    print(f"   strings: {s['strings']['total_distinct']:,} distinct, "
          f"{s['strings']['kept']:,} kept. sample names:")
    shown = 0
    for it in s["strings"]["items"]:
        if it["class"] == "name" and shown < 12:
            rec = f" in {it['records'][0][0]}" if it["records"] else ""
            print(f"     {it['count']:5d}x {it['text'][:60]!r}{rec}")
            shown += 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rvt", nargs="?", default=os.path.join(
        ROOT, "vendor/magnetar-revit-test-datasets/Revit/2024_Core_Interior.rvt"))
    ap.add_argument("--refresh", action="store_true", help="ignore the cache")
    ap.add_argument("--json", help="also write the summary JSON here")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args(argv)
    s = extract(args.rvt, refresh=args.refresh)
    print_summary(s, top=args.top)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(s, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
