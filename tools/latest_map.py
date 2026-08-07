#!/usr/bin/env python3
"""Byte-region map of ``Global/Latest`` (the serialized ``ADocument``).

``latest_map(payload)`` classifies the NON-OBJECT LANDMARK REGIONS inside the
inflated ``Global/Latest`` payload:

* ``json-corpus``   - the two Autodesk Forge unit/spec schema tables
                       (u32 count + count x (AString typeid, AString json)).
* ``string-table``  - the ``m_storedByRevitBuild`` build list plus every other
                       cluster of length-prefixed UTF-16 strings (element /
                       view / sheet / room / scheme / parameter names).
* ``id-array``      - u32 count + n x ElementId64 (stride-8 id runs).
* ``id-map``        - id-keyed fixed-stride record runs (stride 12..64).
* ``object-graph``  - typed sub-objects: the ADocument prologue, the
                       GUID-keyed ExServicesUsed map, the u32-keyed manager
                       registry, the NOBLE secondary-data (analysis cache)
                       block, and scattered typed-pointer/id records.
* ``unknown``       - everything not otherwise claimed.

Returns ``[{start, end, kind, notes}]`` sorted, non-overlapping, plus a
coverage figure (% of bytes in classified regions).

Companion analyses (used by ``docs/writer/latest-regions.md``):

* the JSON corpus is CHARACTERIZED (per-table typeid namespace census,
  sha-256, cross-sample byte identity),
* AString clusters are classified PRODUCT vs PROJECT by a small lexicon,
* ElementId64 references are cross-checked against a supplied id set
  (the sample's ``Global/ElemTable`` ids) and clustered by contiguity /
  stride into id-arrays vs id-maps vs scattered pointers.

CLI::

    .venv/bin/python tools/latest_map.py                # racbasic
    .venv/bin/python tools/latest_map.py --all          # all six samples ->
        experiments/genesis/latest/map_<sample>.json
    .venv/bin/python tools/latest_map.py --dangling     # G0 dangling-id study
"""
from __future__ import annotations

import argparse
import bisect
import collections
import glob
import hashlib
import json
import os
import re
import struct
import sys
from typing import Iterable, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

SAMPLES = [
    "racbasicsampleproject",
    "rstbasicsampleproject",
    "racadvancedsampleproject",
    "rstadvancedsampleproject",
    "rmebasicsampleproject",
    "dach-sample-project",
]

KINDS = ("json-corpus", "string-table", "id-array", "id-map",
         "object-graph", "unknown")

# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

_ASTR_MAX = 200_000


def astring_at(d: bytes, p: int, max_len: int = _ASTR_MAX):
    """(text, end) if a plausible AString (u32 count + UTF-16LE) sits at p."""
    if p < 0 or p + 4 > len(d):
        return None
    n = struct.unpack_from("<I", d, p)[0]
    if n == 0 or n > max_len:
        return None
    e = p + 4 + 2 * n
    if e > len(d):
        return None
    try:
        s = d[p + 4:e].decode("utf-16-le", "strict")
    except Exception:  # noqa: BLE001
        return None
    return s, e


def printable(s: str) -> bool:
    """Human text: >= 60 % ASCII-printable, remainder Latin-1/typographic
    (units like 'm²', degree signs), no control chars."""
    if not s.strip():
        return False
    n_ascii = 0
    for c in s:
        o = ord(c)
        if 0x20 <= o < 0x7F:
            n_ascii += 1
        elif 0xA0 <= o < 0x2000 or 0x2000 <= o <= 0x206F:
            continue
        else:
            return False
    return n_ascii >= 0.6 * len(s)


def sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


# ---------------------------------------------------------------------------
# (1) the Forge JSON corpus
# ---------------------------------------------------------------------------

_TYPEID_PREFIX = re.compile(rb"a\x00u\x00t\x00o\x00d\x00e\x00s\x00k\x00\.\x00")


def find_json_tables(d: bytes) -> list[dict]:
    """Locate every (u32 count + count x (AString typeid, AString json)) table.

    Table header (40 bytes before the first entry): i64 elementId, i64 -1,
    i64 1, i64 -1, u32 1, then the u32 count. The elementId is the owning
    element (project-specific); everything after it is the corpus.
    """
    tables: list[dict] = []
    covered = 0
    for m in _TYPEID_PREFIX.finditer(d):
        p = m.start() - 4
        if p < covered:
            continue
        r = astring_at(d, p, 400)
        if r is None or not r[0].startswith("autodesk."):
            continue
        pairs = []
        q = p
        while True:
            r1 = astring_at(d, q, 400)
            if r1 is None:
                break
            k, q2 = r1
            if not k.startswith("autodesk."):
                break
            r2 = astring_at(d, q2)
            if r2 is None:
                break
            v, q3 = r2
            if not v.lstrip().startswith("{"):
                break
            pairs.append((k, v))
            q = q3
        if len(pairs) < 2:
            continue
        declared = struct.unpack_from("<I", d, p - 4)[0] if p >= 4 else None
        # canonical 40-byte owner header {i64 ownerId, i64 -1, i64 1, i64 -1,
        # u32 1, u32 count}; the second (spec) table has only the u32 count
        # preceded by a project-specific u32 GUID-count + GUID list.
        if p >= 40 and d[p - 32:p - 24] == b"\xff" * 8:
            hdr = p - 40
            owner = struct.unpack_from("<q", d, hdr)[0]
        else:
            hdr, owner = p - 4, None
        body = d[p:q]
        ns = collections.Counter()
        for k, _ in pairs:
            pre = re.sub(r"-[0-9.]+$", "", k.split(":")[0])
            ns[pre] += 1
        tables.append({
            "header_start": hdr,
            "start": p,            # first entry
            "end": q,
            "declared": declared,
            "count": len(pairs),
            "sha256_16": sha16(body),
            "namespaces": dict(ns.most_common()),
            "owner_element_id": owner,
        })
        covered = q
    return tables


# ---------------------------------------------------------------------------
# (2) strings
# ---------------------------------------------------------------------------

# lexicon for PROJECT vs PRODUCT classification of an AString cluster
_PRODUCT_EXACT = {
    "Autodesk Revit", "NobleDocWarnings", "ColorFillSecondaryData",
    "Color Fills", "Color Fill", "MEPNetworkSecondaryData",
    "Network Calculation", "HvacSystemSecondaryData",
    "PipingSystemSecondaryData", "PipingSystemVolumeSecondaryData",
    "System Volumes", "RbsSystem", "RbsWireCurve", "RbsPipeCurve",
    "RbsDuctCurve", "RbsFlexDuctCurve", "FamilyInstance", "IndependentTag",
    "PanelScheduleView", "RevisionSettings", "DBViewDrafting", "DBViewSchedule",
    "LB_Associations", "LB_MetaData", "LB_Version", "LB_References",
    "Rebar Numbering", "Fabric Sheets Numbering", "Rebar Couplers Numbering",
    "http://www.autodesk.com", "Revit Default DB Server", "ADSK",
    "Stairs System", "WireSizes.xml", "Revit", "AREXRevitStart",
    "Element-Watching-Internal-Updater", "ObjectNumberingUpdater",
    "TextNoteUpdater", "AREXContentGenerator", "TCHAR", "Identity",
    "AnalysisId", "ResultsInvalid", "int", "DaylightingAnalysisInfo",
    "Size", "Space Name", "Space Number", "Number of Circuits",
    "Apparent Power", "Connected Apparent Power", "Demand Apparent Power",
    "Connected Current", "Demand Current", "Duct System", "Duct Systems",
    "Piping System", "Piping Systems", "Unassigned", "Generic",
    "3D Views", "Floor Plans", "Structural Plans", "Renderings",
    "Graphical Column Schedules",
}
_PRODUCT_PREFIX = (
    "Revit 20", "Autodesk", "Detail Views (", "Drafting Views (",
    "Elevations (", "Sections (", "autodesk.",
)


def classify_string(s: str) -> str:
    """'product' (Revit ships it), 'project' (sample/user authored) or
    'ambiguous'."""
    t = s.strip()
    if not t:
        return "ambiguous"
    if t in _PRODUCT_EXACT or t.startswith(_PRODUCT_PREFIX):
        return "product"
    if t.startswith("{") and t.endswith("}"):
        return "project"          # LB_* reconcile-map JSON rows
    if re.fullmatch(r"\d+\.\d+\.\d+", t):
        return "project"          # LocalId.ver.ExternalId reconcile keys
    if " : " in t:                # "<category> : <scheme name>" color schemes
        return "project"
    if re.search(r"\bm²\b|\bmm\b|\bMPa\b", t):
        return "project"
    if t in {"Bath", "Bathroom", "Bedroom", "Hall", "Kitchen & Dining",
             "Laundry", "Living", "Master Bedroom", "Ensuite", "Room", "Space",
             "Linen", "Mech.", "Entry Hall", "Master Bath", "liqi", "macalis"}:
        return "project"
    if re.fullmatch(r"[A-Z]?\d{2,4}[A-Za-z]?", t):   # sheet numbers 101 / A001 / S206
        return "project"
    return "ambiguous"


def scan_strings(d: bytes, exclude: list[tuple[int, int]], minlen: int = 3,
                 maxlen: int = 400) -> list[tuple[int, str]]:
    """Every plausible printable AString outside the excluded ranges."""
    ex = sorted(exclude)
    out: list[tuple[int, str]] = []
    p, n = 0, len(d)
    while p < n - 4:
        skip = False
        for a, b in ex:
            if a <= p < b:
                p, skip = b, True
                break
        if skip:
            continue
        L = struct.unpack_from("<I", d, p)[0]
        if minlen <= L <= maxlen and p + 4 + 2 * L <= n:
            raw = d[p + 4:p + 4 + 2 * L]
            try:
                s = raw.decode("utf-16-le")
            except Exception:  # noqa: BLE001
                p += 1
                continue
            if printable(s):
                out.append((p, s))
                p += 4 + 2 * L
                continue
        p += 1
    return out


def cluster_strings(strings: list[tuple[int, str]], maxgap: int = 256):
    """Group strings whose gap to the previous string end is <= maxgap."""
    clusters: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = []
    prev_end = None
    for p, s in strings:
        end = p + 4 + 2 * len(s)
        if cur and prev_end is not None and p - prev_end <= maxgap:
            cur.append((p, s))
        else:
            if cur:
                clusters.append(cur)
            cur = [(p, s)]
        prev_end = end
    if cur:
        clusters.append(cur)
    return clusters


# ---------------------------------------------------------------------------
# (3) ElementId64 references
# ---------------------------------------------------------------------------

def scan_ids(d: bytes, idset: set[int], minid: int = 100) -> list[tuple[int, int]]:
    """Every offset where an int64-LE equals an id in ``idset`` (id >= minid).

    ids below ``minid`` (1..99, the built-in early elements) collide with
    counts/enums too often to be trusted outside a detected cluster.
    """
    hits: list[tuple[int, int]] = []
    n = len(d) - 8
    up = struct.unpack_from
    for p in range(0, max(n, 0)):
        if d[p + 4] | d[p + 5] | d[p + 6] | d[p + 7]:
            continue
        v = up("<I", d, p)[0]
        if v >= minid and v in idset:
            hits.append((p, v))
    return hits


def cluster_ids(hits: list[tuple[int, int]], maxgap: int = 64):
    if not hits:
        return []
    clusters = []
    cur = [hits[0]]
    for h in hits[1:]:
        if h[0] - cur[-1][0] <= maxgap:
            cur.append(h)
        else:
            clusters.append(cur)
            cur = [h]
    clusters.append(cur)
    return clusters


def merge_periodic(clusters: list[list[tuple[int, int]]],
                   max_period: int = 1024, min_run: int = 4):
    """Second-pass merge: runs of small clusters whose START-to-START
    distance is constant (a fixed-size id-keyed record repeated) become one
    cluster. Returns (merged_clusters, set_of_indices_consumed)."""
    out = []
    i = 0
    n = len(clusters)
    while i < n:
        j = i
        if i + 1 < n:
            period = clusters[i + 1][0][0] - clusters[i][0][0]
            k = i
            while (k + 1 < n and 0 < period <= max_period
                   and clusters[k + 1][0][0] - clusters[k][0][0] == period):
                k += 1
            if k - i + 1 >= min_run:
                merged = [h for c in clusters[i:k + 1] for h in c]
                out.append(merged)
                i = k + 1
                continue
        out.append(clusters[i])
        i += 1
    return out


def classify_id_cluster(c: list[tuple[int, int]]) -> tuple[str, dict]:
    """id-array (dominant stride 8), id-map (dominant fixed stride 12..64),
    else object-graph (scattered pointers inside typed records)."""
    strides = [c[i + 1][0] - c[i][0] for i in range(len(c) - 1)]
    sc = collections.Counter(strides)
    n = len(c)
    info = {"n": n, "distinct": len({v for _, v in c}),
            "strides": sc.most_common(3)}
    if n < 3:
        return "object-graph", info
    (s0, k0) = sc.most_common(1)[0]
    frac = k0 / max(len(strides), 1)
    if s0 == 8 and frac >= 0.5:
        return "id-array", info
    if s0 > 8 and frac >= 0.45:
        return "id-map", info
    # periodic record runs merged by merge_periodic: the two most common
    # strides (record period + in-record gap) alternate
    if len(sc) <= 4 and n >= 8 and all(s > 8 for s, _ in sc.most_common(2)):
        return "id-map", info
    return "object-graph", info


# ---------------------------------------------------------------------------
# (4) fixed head structures
# ---------------------------------------------------------------------------

PROLOGUE_LEN = 0x53


def parse_head(d: bytes) -> list[dict]:
    """Prologue (0..0x53), build-string list, ExServicesUsed GUID map,
    the u32-keyed manager registry, up to the NOBLE secondary-data anchor."""
    out = []
    if len(d) >= 4 and struct.unpack_from("<I", d, 0)[0] == 0x1C:
        out.append({"start": 0, "end": min(PROLOGUE_LEN, len(d)),
                    "kind": "object-graph",
                    "notes": "ADocument prologue (constant across samples): "
                             "class 0x1c, externalized member tokens, "
                             "version 2662"})
    p = PROLOGUE_LEN
    # build strings
    if p + 4 <= len(d):
        cnt = struct.unpack_from("<I", d, p)[0]
        q = p + 4
        builds = []
        for _ in range(cnt if cnt < 64 else 0):
            r = astring_at(d, q, 400)
            if r is None:
                break
            builds.append(r[0])
            q = r[1]
        if builds:
            out.append({"start": p, "end": q, "kind": "string-table",
                        "notes": f"m_storedByRevitBuild: {len(builds)} build "
                                 f"strings (PRODUCT: Revit release history "
                                 f"{builds[0].split(' - ')[0][:12]}..; "
                                 f"file-lineage, not project expression)"})
            p = q
    # ExServicesUsed GUID map: ptr(-1,cls) u32 1 u32 count
    if d[p:p + 4] == b"\xff\xff\xff\xff":
        try:
            cls = struct.unpack_from("<H", d, p + 4)[0]
            one, count = struct.unpack_from("<II", d, p + 6)
            q = p + 14
            ok = 0
            for _ in range(count):
                q += 4                      # u32 flag
                q += 16                     # GUID
                r = astring_at(d, q, 100)
                if r is None:
                    break
                q = r[1]
                q += 8                      # ElementId64 -1
                a, b, tag, npairs = struct.unpack_from("<IIiI", d, q)
                q += 16
                if npairs > 256:
                    break
                q += 8 * npairs
                ok += 1
            out.append({"start": p, "end": q, "kind": "object-graph",
                        "notes": f"m_oExServicesUsed GUID-keyed map (class "
                                 f"0x{cls:x}): {count} entries parsed {ok}; "
                                 f"vendor 'Autodesk Revit' service/add-in "
                                 f"registry (product identifiers)"})
            p = q
        except Exception:  # noqa: BLE001
            pass
    # manager registry: u32 1, u32 0xf1, then keyed entries
    if p + 8 <= len(d) and struct.unpack_from("<II", d, p) == (1, 0xF1):
        q = p + 8
        key = struct.unpack_from("<I", d, q)[0]
        nent = 0
        while q + 4 <= len(d):
            k = struct.unpack_from("<I", d, q)[0]
            if k != key:
                break
            nxt = None
            for r in range(q + 4, min(q + 96, len(d) - 4)):
                if struct.unpack_from("<I", d, r)[0] == key + 1:
                    nxt = r
                    break
            nent += 1
            key += 1
            if nxt is None:
                q += 10
                break
            q = nxt
        out.append({"start": p, "end": q, "kind": "object-graph",
                    "notes": f"u32-keyed singleton-manager registry: {nent} "
                             f"entries (key -> u16 class + mostly-default "
                             f"body); document machinery, no element ids"})
        p = q
    return out


# ---------------------------------------------------------------------------
# the map
# ---------------------------------------------------------------------------

def _merge(regions: list[dict], total: int) -> list[dict]:
    """Sort, resolve overlaps (earlier/longer wins), fill gaps as unknown."""
    regions = [r for r in regions if r["end"] > r["start"]]
    regions.sort(key=lambda r: (r["start"], -(r["end"] - r["start"])))
    out: list[dict] = []
    cur = 0
    for r in regions:
        s, e = max(r["start"], cur), r["end"]
        if e <= s:
            continue
        if s > cur:
            out.append({"start": cur, "end": s, "kind": "unknown", "notes": ""})
        rr = dict(r)
        rr["start"], rr["end"] = s, e
        out.append(rr)
        cur = e
    if cur < total:
        out.append({"start": cur, "end": total, "kind": "unknown", "notes": ""})
    return out


def latest_map(payload: bytes, elem_ids: Optional[set[int]] = None,
               with_details: bool = False) -> list[dict]:
    """Region map of a ``Global/Latest`` payload.

    ``elem_ids`` (the file's ``Global/ElemTable`` id set) enables the
    ElementId reference analysis; without it id regions are not detected.
    """
    d = payload
    regions: list[dict] = []
    regions.extend(parse_head(d))

    # JSON corpus
    tables = find_json_tables(d)
    json_ranges = []
    for i, t in enumerate(tables):
        json_ranges.append((t["header_start"], t["end"]))
        top = ", ".join(f"{k}={v}" for k, v in
                        list(t["namespaces"].items())[:6])
        regions.append({
            "start": t["header_start"], "end": t["end"], "kind": "json-corpus",
            "notes": (f"Forge schema table #{i + 1}: declared {t['declared']}, "
                      f"parsed {t['count']} (typeid, json) pairs; owner "
                      f"ElementId64 {t['owner_element_id']}; body sha256 "
                      f"{t['sha256_16']}; namespaces: {top}"),
        })

    # strings outside the JSON tables and the head structures
    head_end = max((r["end"] for r in regions if r["kind"] != "json-corpus"),
                   default=0)
    exclude = json_ranges + [(0, head_end)]
    strings = scan_strings(d, exclude)
    for cl in cluster_strings(strings):
        a = cl[0][0]
        b = cl[-1][0] + 4 + 2 * len(cl[-1][1])
        classes = collections.Counter(classify_string(s) for _, s in cl)
        uniq = list(dict.fromkeys(s for _, s in cl))
        sample = "; ".join(u[:40] for u in uniq[:4])
        kind = "string-table"
        # secondary-data / analysis-cache blocks are typed objects whose
        # bytes are dominated by their schema-name strings
        if any(s.endswith("SecondaryData") or s == "Network Calculation"
               for _, s in cl):
            kind = "object-graph"
        notes = (f"{len(cl)} strings ({len(uniq)} unique); "
                 f"product {classes.get('product', 0)} / project "
                 f"{classes.get('project', 0)} / ambiguous "
                 f"{classes.get('ambiguous', 0)}; e.g. {sample}")
        if kind == "object-graph":
            notes = "NOBLE secondary-data / analysis-cache entries: " + notes
        regions.append({"start": a, "end": b, "kind": kind, "notes": notes})

    # ElementId references
    id_summary = None
    if elem_ids:
        hits = scan_ids(d, elem_ids)
        clusters = merge_periodic(cluster_ids(hits))
        kinds = collections.Counter()
        in_cluster = 0
        for c in clusters:
            k, info = classify_id_cluster(c)
            kinds[k] += 1
            in_cluster += len(c)
            a, b = c[0][0], c[-1][0] + 8
            regions.append({
                "start": a, "end": b, "kind": k,
                "notes": (f"ElementId64 references: {info['n']} hits, "
                          f"{info['distinct']} distinct ids, strides "
                          f"{info['strides']}"),
                "_ids": sorted({v for _, v in c}) if with_details else None,
            })
        id_summary = {"hits": len(hits),
                      "distinct": len({v for _, v in hits}),
                      "clusters": len(clusters),
                      "cluster_kinds": dict(kinds)}
    merged = _merge(regions, len(d))
    if id_summary is not None:
        merged.append({"start": len(d), "end": len(d), "kind": "unknown",
                       "notes": "id-summary " + json.dumps(id_summary)})
    return merged


def coverage(regions: list[dict], total: int) -> dict:
    per = collections.Counter()
    for r in regions:
        per[r["kind"]] += r["end"] - r["start"]
    classified = total - per.get("unknown", 0)
    return {
        "total": total,
        "classified": classified,
        "classified_pct": round(100.0 * classified / total, 2) if total else 0.0,
        "by_kind": {k: per.get(k, 0) for k in KINDS},
        "by_kind_pct": {k: round(100.0 * per.get(k, 0) / total, 2)
                        for k in KINDS} if total else {},
    }


# ---------------------------------------------------------------------------
# sample plumbing
# ---------------------------------------------------------------------------

def load_payload(sample_or_path: str) -> bytes:
    from rvt.container import open_rvt
    path = sample_or_path
    if not os.path.exists(path):
        path = os.path.join(ROOT, "samples", sample_or_path + ".rvt")
    return open_rvt(path).inflate("Global/Latest", 0)


def load_elem_ids(sample_or_path: str) -> set[int]:
    from rvt.container import open_rvt
    from rvt.elemtable import parse_elemtable
    path = sample_or_path
    if not os.path.exists(path):
        path = os.path.join(ROOT, "samples", sample_or_path + ".rvt")
    et = parse_elemtable(open_rvt(path).inflate("Global/ElemTable", 0), path)
    return {r.id for r in et.records}


def map_sample(sample: str, out_dir: Optional[str] = None,
               quiet: bool = False) -> dict:
    d = load_payload(sample)
    ids = load_elem_ids(sample)
    regions = latest_map(d, ids)
    for r in regions:
        r.pop("_ids", None)
    cov = coverage(regions, len(d))
    tables = find_json_tables(d)
    doc = {
        "sample": sample,
        "payload_bytes": len(d),
        "elemtable_ids": len(ids),
        "coverage": cov,
        "json_tables": [{k: v for k, v in t.items()} for t in tables],
        "regions": regions,
    }
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"map_{sample}.json"), "w") as f:
            json.dump(doc, f, indent=1)
    if not quiet:
        print(f"{sample}: {len(d):,} B, {len(regions)} regions, "
              f"classified {cov['classified_pct']}% "
              f"(json {cov['by_kind_pct']['json-corpus']}% / strings "
              f"{cov['by_kind_pct']['string-table']}% / id-array "
              f"{cov['by_kind_pct']['id-array']}% / id-map "
              f"{cov['by_kind_pct']['id-map']}% / object-graph "
              f"{cov['by_kind_pct']['object-graph']}%)")
    return doc


def corpus_identity(samples: Iterable[str] = SAMPLES) -> dict:
    """Are the JSON tables byte-identical across the samples? (determination a)"""
    per = {}
    for s in samples:
        d = load_payload(s)
        per[s] = [(t["count"], t["end"] - t["start"], t["sha256_16"])
                  for t in find_json_tables(d)]
    shas = {tuple(x[2] for x in v) for v in per.values()}
    return {"per_sample": per, "byte_identical": len(shas) == 1}


# ---------------------------------------------------------------------------
# G0 dangling-id study
# ---------------------------------------------------------------------------

def dangling_study(g0_path: str = "experiments/genesis/G0.rvt",
                   lineage: str = "rstbasicsampleproject") -> dict:
    """Classify the registries the dangling ids in G0's inherited
    Global/Latest sit in. G0's Latest is byte-identical to the lineage
    sample's; its ElemTable holds only our ids, so every lineage-id reference
    is dangling."""
    from rvt.container import open_rvt
    from rvt.elemtable import parse_elemtable
    gp = g0_path if os.path.exists(g0_path) else os.path.join(ROOT, g0_path)
    g0 = open_rvt(gp)
    latest = g0.inflate("Global/Latest", 0)
    g0_ids = {r.id for r in parse_elemtable(g0.inflate("Global/ElemTable", 0),
                                             gp).records}
    lineage_ids = load_elem_ids(lineage)
    lin_payload = load_payload(lineage)
    identical = hashlib.sha256(latest).digest() == hashlib.sha256(lin_payload).digest()
    hits = scan_ids(latest, lineage_ids | g0_ids)
    ours = [(p, v) for p, v in hits if v in g0_ids]
    dangling = [(p, v) for p, v in hits if v in lineage_ids and v not in g0_ids]
    clusters = merge_periodic(cluster_ids(hits))
    kind_counts = collections.Counter()
    kind_ids = collections.defaultdict(set)
    biggest = []
    # class attribution needs the lineage sample's partitions
    class_of = None
    try:
        from rvt.mutate import Document
        doc = Document.from_file(os.path.join(ROOT, "samples", lineage + ".rvt"))
        class_of = doc.class_of
    except Exception:  # noqa: BLE001
        pass
    for c in clusters:
        k, info = classify_id_cluster(c)
        kind_counts[k] += 1
        for _, v in c:
            kind_ids[k].add(v)
        if info["n"] >= 40:
            cls = collections.Counter()
            if class_of:
                for _, v in c:
                    cls[class_of(v) or "?"] += 1
            biggest.append({"start": c[0][0], "end": c[-1][0] + 8, "kind": k,
                            "n": info["n"], "distinct": info["distinct"],
                            "strides": info["strides"],
                            "classes": cls.most_common(6)})
    biggest.sort(key=lambda x: -x["n"])
    return {
        "g0_latest_bytes": len(latest),
        "g0_latest_identical_to_lineage": identical,
        "g0_elemtable_ids": len(g0_ids),
        "our_ids_referenced": len({v for _, v in ours}),
        "dangling_hits": len(dangling),
        "dangling_distinct_ids": len({v for _, v in dangling}),
        "cluster_count": len(clusters),
        "cluster_kinds": dict(kind_counts),
        "distinct_ids_by_kind": {k: len(v) for k, v in kind_ids.items()},
        "largest_clusters": biggest[:24],
    }


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sample", nargs="?", default="racbasicsampleproject")
    ap.add_argument("--all", action="store_true", help="map all six samples")
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments", "genesis", "latest"))
    ap.add_argument("--identity", action="store_true", help="cross-sample JSON identity check")
    ap.add_argument("--dangling", action="store_true", help="G0 dangling-id study")
    ap.add_argument("--json", action="store_true", help="print machine JSON")
    a = ap.parse_args(argv)
    if a.identity:
        r = corpus_identity()
        print(json.dumps(r, indent=1) if a.json else
              f"byte-identical across {len(r['per_sample'])} samples: "
              f"{r['byte_identical']}\n" +
              "\n".join(f"  {k}: {v}" for k, v in r["per_sample"].items()))
        return 0
    if a.dangling:
        r = dangling_study()
        print(json.dumps(r, indent=1))
        return 0
    if a.all:
        for s in SAMPLES:
            map_sample(s, out_dir=a.out)
        return 0
    doc = map_sample(a.sample, out_dir=a.out, quiet=a.json)
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        for r in doc["regions"]:
            if r["kind"] == "unknown" and (r["end"] - r["start"]) < 64:
                continue
            print(f"  {r['start']:#010x}-{r['end']:#010x} {r['end']-r['start']:>9,} "
                  f"{r['kind']:<13} {r['notes'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
