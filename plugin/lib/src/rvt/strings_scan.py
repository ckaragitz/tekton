"""strings_scan.py -- orientation index of human-meaningful values in .rvt data.

Sweeps every inflated gzip member (extracted/<file>/<Stream>.gz/NNN.bin) plus
the small raw metadata streams (BasicFileInfo, Contents, TransmissionData,
ProjectInformation zip -> project.xml, RevitPreview4.0) for:

  * UTF-16LE strings (>= 4 chars), noting whether a uint32 LE char-count
    length prefix immediately precedes the string (the Revit ``AString``
    serialization: uint32 count + UTF-16LE code units, no terminator).
  * ASCII / UTF-8 strings (>= 5 chars).
  * GUIDs -- text form (ascii + utf16) and 16-byte binary form (Windows
    ``bytes_le`` layout) matched against the set of GUIDs discovered in text
    plus every GUID in the Global/History table.
  * A curated needle list (level/grid/wall/... names, project info values,
    usernames, paths) with the exact BasicFileInfo / ProjectInformation
    strings of the file being scanned added automatically.

Outputs (per file, name shortened e.g. racbasicsampleproject -> racbasic):
  extracted/_index/strings_<short>.jsonl   one JSON object per string hit
  extracted/_index/guids_<short>.jsonl     one JSON object per GUID hit

Every record carries: file, stream, member, offset (byte offset inside the
inflated member or raw stream), encoding, class, text, ctx (32 bytes hex).

Usage:
  .venv/bin/python src/rvt/strings_scan.py            # racbasic + rstbasic
  .venv/bin/python src/rvt/strings_scan.py --all      # all six samples
  .venv/bin/python src/rvt/strings_scan.py --file racbasicsampleproject
  .venv/bin/python src/rvt/strings_scan.py --needles-only
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import struct
import sys
import uuid
import zipfile

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides
EXTRACTED = os.path.join(ROOT, "extracted")
INDEX_DIR = os.path.join(EXTRACTED, "_index")

SHORT = {
    "racbasicsampleproject": "racbasic",
    "rstbasicsampleproject": "rstbasic",
    "racadvancedsampleproject": "racadvanced",
    "rstadvancedsampleproject": "rstadvanced",
    "rmebasicsampleproject": "rmebasic",
    "dach-sample-project": "dach",
}
DEFAULT_FILES = ["racbasicsampleproject", "rstbasicsampleproject"]
ALL_FILES = [
    "racbasicsampleproject",
    "rstbasicsampleproject",
    "racadvancedsampleproject",
    "rstadvancedsampleproject",
    "rmebasicsampleproject",
    "dach-sample-project",
]

# raw (non-gzip / small) streams worth scanning directly
RAW_STREAMS = [
    "BasicFileInfo.bin",
    "Contents.bin",
    "TransmissionData.bin",
    "ProjectInformation.bin",
    "RevitPreview4.0.bin",
]

# ---------------------------------------------------------------------------
# needles
# ---------------------------------------------------------------------------

BASE_NEEDLES = [
    "Level 1", "Level 2", "Level 3", "Grid", "Grid 1", "Wall", "Basic Wall",
    "Walls", "Generic - 200mm", "Generic - 300mm", "Floor", "Roof", "Door",
    "Window", "Room", "Sheet", "View", "Floor Plan", "3D View", "Elevation",
    "Section", "Autodesk", "Autodesk Revit", "Revit", "Workset1", "GLOBAL",
    "Family", "Wall Sweep", "millimeters", "meters", "ENU",
    "C:\\Users\\", "C:\\Program", "\\Desktop\\", "OneDrive",
]

RE_U16 = re.compile(rb"(?:[\x20-\x7e\t\r\n]\x00){4,}")
RE_ASC = re.compile(rb"[\x20-\x7e]{5,}")
RE_GUID_A = re.compile(
    rb"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
RE_GUID_U = re.compile(
    rb"(?:[0-9a-fA-F]\x00){8}-\x00(?:[0-9a-fA-F]\x00){4}-\x00(?:[0-9a-fA-F]\x00){4}-\x00"
    rb"(?:[0-9a-fA-F]\x00){4}-\x00(?:[0-9a-fA-F]\x00){12}"
)


def ctx_hex(data: bytes, off: int, before: int = 16, after: int = 16) -> str:
    lo = max(0, off - before)
    return data[lo:off + after].hex()


# ---------------------------------------------------------------------------
# string classification
# ---------------------------------------------------------------------------

_SCHEMA_TOKENS = (
    "autodesk.unit", "autodesk.spec", "autodesk.parameter", "autodesk.category",
    "unit:", "symbol:", "spec.", '"id":', '"typeid"', '"constants"',
    '"inherits"', "texture_", "common_", "Schema", "UIDefinition",
    "Implementation", "AssetLib", "adsk", "urn:", "xmlns", "<?xml", "</",
    "assettype", "localname", "keyword", "swatch", "assetlibrary",
)


def classify(text: str) -> str:
    t = text.strip()
    tl = t.lower()
    if RE_GUID_A.fullmatch(t.strip("{}").encode()) or (RE_GUID_A.search(t.encode()) and len(t) <= 40):
        return "guid-text"
    if ":\\" in t or t.startswith("\\\\") or (
        "/" in t and any(t.lower().endswith(e) for e in (".xml", ".png", ".fbx", ".txt", ".rfa", ".rvt", ".dwg", ".ies"))
    ) or ("Mats/" in t) or ("\\" in t and "." in t):
        return "path"
    if any(tok in t for tok in _SCHEMA_TOKENS) or any(tok in tl for tok in ("autodesk.unit", "autodesk.spec")):
        return "schema"
    if re.fullmatch(r"[0-9.,+\-eE %'/\"x]+", t):
        return "number"
    if len(t) <= 3:
        return "short"
    # debris filters (IEEE doubles / element ids that happen to be printable)
    if not re.search(r"[A-Za-z]{3,}", t):
        return "noise"
    if len(set(t)) <= 3 or not re.search(r"[aeiouyAEIOUY]", t):
        return "noise"  # 'UUUUU', ';UUUU'
    top = collections.Counter(t).most_common(1)[0][1]
    if top / len(t) > 0.55:
        return "noise"  # '@TUUUUUu?', '{{{{{{'
    # json / structured fragments
    if t.startswith(('{', '}', '[', ']', '"')) or '"' in t:
        return "schema"
    return "name"  # candidate human-authored / display name


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------

def iter_sources(filedir: str):
    """Yield (stream, member, data, base_offset).

    member is the inflated-member index for gzip payloads, 'gapN' for raw
    bytes of a compressed stream NOT covered by any carved gzip member
    (offset then = absolute offset inside the raw stream), '' for raw streams.
    """
    base = os.path.join(EXTRACTED, filedir)
    # inflated members
    for entry in sorted(os.listdir(base)):
        if not entry.endswith(".gz"):
            continue
        stream = entry[:-3]
        gzdir = os.path.join(base, entry)
        members = sorted(m for m in os.listdir(gzdir) if m.endswith(".bin"))
        for m in members:
            path = os.path.join(gzdir, m)
            with open(path, "rb") as fh:
                yield stream, m[:-4], fh.read(), 0
        # raw gaps of the compressed stream (bytes not covered by any member):
        # these hold the 8-byte Global/* headers, the per-block Partitions
        # framing, the post-deflate trailers -- and uncompressed records.
        idx_path = os.path.join(gzdir, "index.json")
        raw_path = os.path.join(base, stream + ".bin")
        if os.path.exists(idx_path) and os.path.exists(raw_path):
            try:
                idx = json.load(open(idx_path))
                raw = open(raw_path, "rb").read()
            except Exception:
                idx, raw = None, b""
            if idx:
                prev = 0
                k = 0
                spans = []
                for m in sorted(idx.get("members", []), key=lambda x: x["offset"]):
                    if m["offset"] > prev:
                        spans.append((prev, m["offset"]))
                    prev = max(prev, m["offset"] + m["consumed"])
                if prev < len(raw):
                    spans.append((prev, len(raw)))
                for (a, b) in spans:
                    if b - a >= 4:
                        yield stream + " [rawgap]", f"gap{k}", raw[a:b], a
                    k += 1
    # raw streams
    for raw in RAW_STREAMS:
        path = os.path.join(base, raw)
        if not os.path.exists(path):
            continue
        data = open(path, "rb").read()
        yield raw[:-4] + " [raw]", "", data, 0
        if raw == "ProjectInformation.bin":
            try:
                zf = zipfile.ZipFile(io.BytesIO(data))
                for name in zf.namelist():
                    yield "ProjectInformation:project.xml", "", zf.read(name), 0
            except zipfile.BadZipFile:
                pass


# ---------------------------------------------------------------------------
# BasicFileInfo / ProjectInformation seed values
# ---------------------------------------------------------------------------

def basicfileinfo_values(filedir: str) -> dict:
    """Extract key strings + GUIDs from BasicFileInfo (UTF-16LE text)."""
    path = os.path.join(EXTRACTED, filedir, "BasicFileInfo.bin")
    out = {"guids": [], "strings": [], "username": None}
    if not os.path.exists(path):
        return out
    d = open(path, "rb").read()
    # try both alignments
    text = ""
    for start in (0, 1):
        try:
            t = d[start:].decode("utf-16-le", "replace")
        except Exception:
            continue
        if t.count("\r\n") > text.count("\r\n"):
            text = t
    out["text"] = text
    for m in RE_GUID_U.finditer(d):
        g = m.group().decode("utf-16-le").lower()
        if g not in out["guids"]:
            out["guids"].append(g)
    for m in RE_GUID_A.finditer(d):
        g = m.group().decode().lower()
        if g not in out["guids"]:
            out["guids"].append(g)
    mu = re.search(r"Username:[ \t]*([^\r\n]*)", text)
    if mu:
        out["username"] = mu.group(1).strip() or None
    for key in ("Central Model Path", "Last Save Path", "Build"):
        mm = re.search(rf"{key}:\s*([^\r\n]+)", text)
        if mm:
            out["strings"].append(mm.group(1).strip())
    return out


def project_information_values(filedir: str) -> list[str]:
    """Element values inside the ProjectInformation partatom XML."""
    path = os.path.join(EXTRACTED, filedir, "ProjectInformation.bin")
    vals: list[str] = []
    if not os.path.exists(path):
        return vals
    try:
        zf = zipfile.ZipFile(open(path, "rb"))
        xml = zf.read(zf.namelist()[0]).decode("utf-8", "replace")
    except Exception:
        return vals
    for m in re.finditer(r">([^<>]{3,})<", xml):
        v = m.group(1).strip()
        if v and v not in vals:
            vals.append(v)
    return vals


# ---------------------------------------------------------------------------
# History GUID table
# ---------------------------------------------------------------------------

def history_guids(filedir: str) -> list[dict]:
    """Decode the Global/History episode-GUID table.

    Layout (racbasic, inflated member 000):
      0x00  u16 0x0538 ... u32 count (0x350)      -- header
      0x16  4 x 16-byte GUID slots (creator / owner ids; 3 equal + 1 null + 1)
      0x66  u32 n=190, u32 offsets/ids[...]        -- an index array
      ...   u32 count again, then count records of 16-byte GUID (+1 byte)
    We locate the record run heuristically: the u32 count value followed by
    count 17-byte records whose 16 bytes look like RFC4122 v4 GUIDs.
    """
    path = os.path.join(EXTRACTED, filedir, "Global__History.gz", "000.bin")
    if not os.path.exists(path):
        return []
    d = open(path, "rb").read()
    cands = []
    # find candidate v4 guids
    for i in range(len(d) - 16):
        b = d[i:i + 16]
        if (b[7] >> 4) == 4 and (b[8] & 0xC0) == 0x80:
            u = uuid.UUID(bytes_le=bytes(b))
            cands.append({"offset": i, "guid": str(u)})
    if not cands:
        return []
    # the table = the longest run of candidates spaced exactly 17 bytes apart
    offs = {c["offset"]: c for c in cands}
    best_run: list[dict] = []
    seen = set()
    for c in cands:
        o = c["offset"]
        if o in seen:
            continue
        run = []
        while o in offs:
            run.append(offs[o])
            seen.add(o)
            o += 17
        if len(run) > len(best_run):
            best_run = run
    if not best_run:
        return []
    # the run start is preceded by a u32 record count; use it to read the
    # full table (some records are v1 / non-v4 GUIDs and break the lattice).
    start = best_run[0]["offset"]
    if start >= 4:
        (count,) = struct.unpack_from("<I", d, start - 4)
        if 0 < count <= 100000 and start + count * 17 <= len(d):
            table = []
            for k in range(count):
                o = start + k * 17
                u = uuid.UUID(bytes_le=bytes(d[o:o + 16]))
                table.append({"offset": o, "guid": str(u), "flag": d[o + 16]})
            return table
    return best_run


# ---------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------

def scan_file(filedir: str, out_strings, out_guids, *, quiet=False):
    short = SHORT.get(filedir, filedir)
    bfi = basicfileinfo_values(filedir)
    piv = project_information_values(filedir)
    hist = history_guids(filedir)

    known_guids: dict[str, str] = {}
    for g in bfi["guids"]:
        known_guids.setdefault(g, "basicfileinfo")
    for h in hist:
        known_guids.setdefault(h["guid"], "history-table")
    known_guids.pop("00000000-0000-0000-0000-000000000000", None)  # nil GUID matches everywhere

    # one compiled pattern for all binary forms of the known GUIDs
    bin_map: dict[bytes, tuple[str, str]] = {}
    for g in known_guids:
        u = uuid.UUID(g)
        bin_map[u.bytes_le] = (g, "bin-le")
        bin_map.setdefault(u.bytes, (g, "bin-be"))
    re_bin = re.compile(b"|".join(re.escape(p) for p in bin_map), re.DOTALL) if bin_map else None

    needles = list(BASE_NEEDLES)
    if bfi.get("username"):
        needles.append(bfi["username"])
    needles += bfi.get("strings", [])
    needles += piv
    needles += list(bfi["guids"])
    needles = list(dict.fromkeys(n for n in needles if n))

    needle_hits = collections.defaultdict(lambda: collections.Counter())
    stream_stats = collections.defaultdict(lambda: collections.Counter())
    name_counter = collections.Counter()
    guid_locations = collections.defaultdict(list)
    needle_bytes = [(nd, nd.encode("utf-16-le"), nd.encode("utf-8")) for nd in needles]

    n_strings = 0
    n_guids = 0
    n_noise = 0
    for stream, member, data, base_off in iter_sources(filedir):
        skey = f"{stream}/{member}" if member else stream
        # --- curated needles (counted over the raw bytes, both encodings)
        for nd, u16b, u8b in needle_bytes:
            k = data.count(u16b) + data.count(u8b)
            if k:
                needle_hits[nd][skey] += k
        # --- utf16 strings
        for m in RE_U16.finditer(data):
            off = m.start()
            raw = m.group()
            try:
                text = raw.decode("utf-16-le")
            except UnicodeDecodeError:
                continue
            nchars = len(text)
            lp = False
            if off >= 4:
                (plen,) = struct.unpack_from("<I", data, off - 4)
                lp = plen == nchars
            cls = classify(text)
            stream_stats[skey][cls] += 1
            stream_stats[skey]["utf16_total"] += 1
            if cls == "noise":
                n_noise += 1
                continue
            rec = {
                "file": short, "stream": stream, "member": member,
                "offset": off + base_off, "encoding": "utf-16le", "class": cls,
                "len": nchars, "len_prefixed": lp, "text": text[:300],
                "ctx": ctx_hex(data, off),
            }
            out_strings.write(json.dumps(rec) + "\n")
            n_strings += 1
            if cls == "name":
                name_counter[(text, skey)] += 1
        # --- ascii strings
        for m in RE_ASC.finditer(data):
            off = m.start()
            text = m.group().decode("ascii")
            cls = classify(text)
            stream_stats[skey]["ascii_total"] += 1
            if cls in ("noise", "number", "short"):
                n_noise += 1
                continue  # geometry/float debris -- counted, not recorded
            rec = {
                "file": short, "stream": stream, "member": member,
                "offset": off + base_off, "encoding": "ascii", "class": cls,
                "len": len(text), "len_prefixed": False, "text": text[:300],
                "ctx": ctx_hex(data, off),
            }
            out_strings.write(json.dumps(rec) + "\n")
            n_strings += 1
            stream_stats[skey]["ascii_kept"] += 1
            if cls == "name":
                name_counter[(text, skey)] += 1
        # --- text guids
        for m in RE_GUID_A.finditer(data):
            g = m.group().decode().lower()
            rec = {"file": short, "stream": stream, "member": member,
                   "offset": m.start() + base_off, "form": "text-ascii", "guid": g,
                   "known": known_guids.get(g), "ctx": ctx_hex(data, m.start())}
            out_guids.write(json.dumps(rec) + "\n")
            guid_locations[g].append(skey)
            n_guids += 1
        for m in RE_GUID_U.finditer(data):
            g = m.group().decode("utf-16-le").lower()
            rec = {"file": short, "stream": stream, "member": member,
                   "offset": m.start() + base_off, "form": "text-utf16", "guid": g,
                   "known": known_guids.get(g), "ctx": ctx_hex(data, m.start())}
            out_guids.write(json.dumps(rec) + "\n")
            guid_locations[g].append(skey)
            n_guids += 1
        # --- binary matches of known guids (bytes_le and network order)
        if re_bin is not None:
            for m in re_bin.finditer(data):
                g, form = bin_map[m.group()]
                rec = {"file": short, "stream": stream, "member": member,
                       "offset": m.start() + base_off, "form": form, "guid": g,
                       "known": known_guids.get(g), "ctx": ctx_hex(data, m.start())}
                out_guids.write(json.dumps(rec) + "\n")
                guid_locations[g].append(skey)
                n_guids += 1

    if not quiet:
        print(f"\n=== {filedir} ({short}) ===")
        print(f"  strings recorded: {n_strings:,} (noise/short/number strings counted but not recorded: {n_noise:,})   guid hits: {n_guids:,}")
        print(f"  BasicFileInfo username: {bfi.get('username')}")
        print(f"  BasicFileInfo GUIDs: {', '.join(bfi['guids']) or '(none)'}")
        print(f"  Global/History GUID table: {len(hist)} entries"
              f" (first = {hist[0]['guid'] if hist else '-'} @0x{hist[0]['offset']:x})" if hist else "")
        print("\n  -- per-stream string classes (utf16 strings)")
        print(f"  {'stream':36s} {'utf16':>7s} {'name':>6s} {'schema':>7s} {'path':>5s} {'guid':>5s} {'noise':>6s} {'ascii':>7s} {'kept':>6s}")
        # aggregate by stream (collapse members)
        agg = collections.defaultdict(collections.Counter)
        for skey, cnt in stream_stats.items():
            agg[skey.split('/')[0]] += cnt
        for skey, cnt in sorted(agg.items()):
            skl = skey if len(skey) <= 36 else skey[:33] + "..."
            print(f"  {skl:36s} {cnt['utf16_total']:7d} {cnt['name']:6d} {cnt['schema']:7d}"
                  f" {cnt['path']:5d} {cnt['guid-text']:5d} {cnt['noise']:6d} {cnt['ascii_total']:7d} {cnt['ascii_kept']:6d}")
        print("\n  -- needle hits (needle -> top locations)")
        for nd in needles:
            hits = needle_hits.get(nd)
            if not hits:
                print(f"  {nd!r:60s} : (none)")
                continue
            top = ", ".join(f"{k}x{v}" for k, v in hits.most_common(4))
            print(f"  {nd!r:60s} : {sum(hits.values())} -> {top}")
        print("\n  -- BasicFileInfo GUID cross reference")
        for g in bfi["guids"]:
            locs = collections.Counter(guid_locations.get(g, []))
            where = ", ".join(f"{k}x{v}" for k, v in locs.most_common(8)) or "(no other occurrence)"
            print(f"  {g} -> {where}")
        if hist:
            # do history-table GUIDs occur outside History?
            outside = collections.Counter()
            for h in hist:
                for loc in guid_locations.get(h["guid"], []):
                    if not loc.startswith("Global__History"):
                        outside[loc] += 1
            print(f"\n  -- Global/History table: {len(hist)} GUID records, "
                  f"first at 0x{hist[0]['offset']:x}, stride 17.  Occurrences of table"
                  f" GUIDs outside History: {sum(outside.values())} "
                  f"{dict(outside.most_common(8))}")
        print("\n  -- top 40 candidate user-authored names")
        for (text, skey), n in name_counter.most_common(40):
            print(f"  {n:5d}  {skey:40s} {text[:70]!r}")
    return {
        "strings": n_strings, "guids": n_guids, "needle_hits": needle_hits,
        "stream_stats": stream_stats, "names": name_counter,
        "history": hist, "known_guids": known_guids, "guid_locations": guid_locations,
        "bfi": bfi, "piv": piv,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true", help="scan all six sample files")
    ap.add_argument("--file", action="append", help="specific extracted/<dir> to scan")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    files = args.file or (ALL_FILES if args.all else DEFAULT_FILES)
    os.makedirs(INDEX_DIR, exist_ok=True)
    results = {}
    for f in files:
        short = SHORT.get(f, f)
        sp = os.path.join(INDEX_DIR, f"strings_{short}.jsonl")
        gp = os.path.join(INDEX_DIR, f"guids_{short}.jsonl")
        with open(sp, "w") as fs, open(gp, "w") as fg:
            results[f] = scan_file(f, fs, fg, quiet=args.quiet)
        if not args.quiet:
            print(f"\n  wrote {sp}\n  wrote {gp}")
    return results


if __name__ == "__main__":
    main()
