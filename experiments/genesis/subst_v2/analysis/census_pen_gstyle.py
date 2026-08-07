"""census_pen_gstyle.py -- the linter's method by hand: decode EVERY
PenWidthTableElem + GStyleElem specimen across all six samples, profile every
field (value set / null rate / list-length set / pointer class), then diff
OUR constructors' output against the corpus profile.  Reports every field
where OURS is null/empty/differently-shaped or outside the specimens' value
set.  Writes JSON + a text report to the fixer scratchpad.
"""
from __future__ import annotations

import collections
import json
import os
import sys

ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
SCR = "/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad"
os.environ.setdefault("RVT_SEG_CACHE", os.path.join(SCR, "segcache"))
OUT = os.path.join(SCR, "fixer")

SAMPLES = ["rstbasicsampleproject", "rmebasicsampleproject", "racbasicsampleproject",
           "racadvancedsampleproject", "rstadvancedsampleproject", "dach-sample-project"]

from rvt.mutate import Document                      # noqa: E402
from rvt.genesis import settings as S                 # noqa: E402
from rvt.genesis import catalog as C                  # noqa: E402
from rvt.genesis.types import IdSource, INVALID       # noqa: E402


# ---------------------------------------------------------------------------
# flattening: object dict -> {path: leaf-descriptor}
#   descriptor examples: ("null",), ("bool", v), ("int", v), ("float", v),
#   ("str", v), ("list", len), ("guid", v), ("weakref", n), ("classref", name)
# containers: record ("list", len) at the container path AND recurse into
# elements with path[] (all elements pooled -> per-element field profiles).
# owned pointers: record ("ptr", class or None) then recurse into value.
# ---------------------------------------------------------------------------

def flatten(v, path="", out=None):
    out = collections.defaultdict(list) if out is None else out
    if v is None:
        out[path].append(("null",))
    elif isinstance(v, bool):
        out[path].append(("bool", v))
    elif isinstance(v, int):
        out[path].append(("int", v))
    elif isinstance(v, float):
        out[path].append(("float", v))
    elif isinstance(v, (bytes, bytearray)):
        out[path].append(("bytes", len(v)))
    elif isinstance(v, str):
        out[path].append(("str", v))
    elif isinstance(v, list):
        out[path].append(("list", len(v)))
        for x in v:
            flatten(x, path + "[]", out)
    elif isinstance(v, dict):
        if "ptr_class" in v and "value" in v:            # owned pointer
            out[path].append(("ptr", v.get("ptr_class")))
            flatten(v.get("value"), path, out) if isinstance(v.get("value"), dict) else None
            if isinstance(v.get("value"), dict):
                for k, x in v["value"].items():
                    flatten(x, path + "." + k, out)
        elif "weakref" in v and len(v) == 1:
            out[path].append(("weakref", v["weakref"]))
        elif "classref" in v and len(v) == 1:
            out[path].append(("classref", v["classref"]))
        else:
            out[path].append(("dict",))
            for k, x in v.items():
                flatten(x, path + "." + k, out)
    else:
        out[path].append((type(v).__name__, str(v)))
    return out


def _clean_flatten(v):
    # the ptr branch above double-counts; do a clean recursive walk instead
    out = collections.defaultdict(list)
    _fl(v, "", out)
    return out


def _fl(v, path, out):
    if v is None:
        out[path].append(("null",))
    elif isinstance(v, bool):
        out[path].append(("bool", v))
    elif isinstance(v, int):
        out[path].append(("int", v))
    elif isinstance(v, float):
        out[path].append(("float", v))
    elif isinstance(v, (bytes, bytearray)):
        out[path].append(("bytes", len(v)))
    elif isinstance(v, str):
        out[path].append(("str", v))
    elif isinstance(v, list):
        out[path].append(("list", len(v)))
        for x in v:
            _fl(x, path + "[]", out)
    elif isinstance(v, dict):
        if "ptr_class" in v and "value" in v:
            out[path].append(("ptr", v.get("ptr_class")))
            val = v.get("value")
            if isinstance(val, dict):
                for k, x in val.items():
                    _fl(x, path + "." + k, out)
            elif val is not None:
                _fl(val, path + ".<value>", out)
        elif set(v) == {"weakref"}:
            out[path].append(("weakref", v["weakref"]))
        elif set(v) == {"classref"}:
            out[path].append(("classref", v["classref"]))
        else:
            out[path].append(("dict",))
            for k, x in v.items():
                _fl(x, path + "." + k, out)
    else:
        out[path].append((type(v).__name__, str(v)))


class Profile:
    """Aggregate of many flattened specimens: per path, the multiset of leaf
    descriptor kinds and the value sets."""

    def __init__(self):
        self.n = 0
        self.paths = collections.defaultdict(lambda: {
            "occurrences": 0, "in_n_specimens": 0, "kinds": collections.Counter(),
            "values": collections.Counter(), "list_lengths": collections.Counter(),
            "ptr_classes": collections.Counter(), "null": 0, "floats": []})
        self._sources = collections.defaultdict(set)

    def add(self, flat, tag):
        self.n += 1
        for path, descs in flat.items():
            p = self.paths[path]
            p["in_n_specimens"] += 1
            for d in descs:
                p["occurrences"] += 1
                k = d[0]
                p["kinds"][k] += 1
                if k == "null":
                    p["null"] += 1
                elif k in ("bool", "int", "str", "classref", "weakref"):
                    p["values"][repr(d[1])] += 1
                elif k == "float":
                    p["floats"].append(d[1])
                elif k == "list":
                    p["list_lengths"][d[1]] += 1
                elif k == "ptr":
                    p["ptr_classes"][repr(d[1])] += 1
                self._sources[path].add(tag)

    def summary(self, path):
        p = self.paths.get(path)
        if not p:
            return None
        out = {"occurrences": p["occurrences"],
               "in_specimens": p["in_n_specimens"], "of": self.n,
               "kinds": dict(p["kinds"]), "null": p["null"]}
        if p["values"]:
            vals = p["values"]
            out["distinct_values"] = len(vals)
            out["values_top"] = vals.most_common(12)
        if p["floats"]:
            fl = p["floats"]
            out["float_min"] = min(fl)
            out["float_max"] = max(fl)
            out["float_distinct"] = len(set(round(x, 9) for x in fl))
        if p["list_lengths"]:
            out["list_lengths"] = dict(p["list_lengths"].most_common(12))
        if p["ptr_classes"]:
            out["ptr_classes"] = dict(p["ptr_classes"])
        return out


def diff_ours(ours_flat, prof: Profile, name):
    """List every path where OURS is (a) null/empty but specimens never
    null/empty, (b) a scalar outside the specimen value set (for small sets),
    (c) a list length outside the observed set, (d) a ptr class differing,
    (e) a path specimens ALWAYS carry that ours lacks, (f) a path ours has
    that no specimen has."""
    findings = []
    spec_paths = set(prof.paths)
    our_paths = set(ours_flat)
    for path in sorted(spec_paths | our_paths):
        p = prof.paths.get(path)
        ours = ours_flat.get(path)
        if p is not None and ours is None:
            # specimens carry this path, ours never does
            if p["in_n_specimens"] == prof.n:
                findings.append((0, path, f"OURS MISSING; present in {p['in_n_specimens']}/{prof.n} specimens; kinds={dict(p['kinds'])}"))
            else:
                findings.append((3, path, f"ours lacks (specimens {p['in_n_specimens']}/{prof.n} have it)"))
            continue
        if p is None:
            findings.append((1, path, f"OURS HAS a path NO specimen carries: {ours}"))
            continue
        # both present
        kinds = collections.Counter(d[0] for d in ours)
        # null-ness
        if kinds.get("null") and p["null"] == 0:
            findings.append((0, path, f"OURS NULL but specimens never null (kinds={dict(p['kinds'])})"))
        # empty list vs never-empty
        for d in ours:
            if d[0] == "list":
                if d[1] not in p["list_lengths"]:
                    lens = p["list_lengths"]
                    sev = 0 if (d[1] == 0 and 0 not in lens) else 1
                    findings.append((sev, path, f"our list length {d[1]} not in specimen lengths {dict(lens.most_common(8))}"))
            elif d[0] == "ptr":
                pcs = p["ptr_classes"]
                if repr(d[1]) not in pcs:
                    findings.append((0, path, f"our ptr class {d[1]!r} not in specimen ptr classes {dict(pcs)}"))
            elif d[0] in ("int", "bool", "str", "classref", "weakref"):
                vals = p["values"]
                # only flag when the specimen value set is small (enum-like / constant)
                if vals and repr(d[1]) not in vals and len(vals) <= 12:
                    findings.append((1, path, f"our value {d[1]!r} outside specimen set {dict(vals.most_common(12))} (kind {d[0]})"))
                elif not vals and d[0] != "null":
                    findings.append((0, path, f"our {d[0]} where specimens have kinds {dict(p['kinds'])}"))
            elif d[0] == "float":
                fl = p["floats"]
                if fl:
                    if d[1] < min(fl) - 1e-9 or d[1] > max(fl) + 1e-9:
                        distinct = sorted(set(round(x, 6) for x in fl))
                        findings.append((2, path, f"our float {d[1]!r} outside specimen range [{min(fl)!r}, {max(fl)!r}] distinct={distinct[:12]}"))
                elif "float" not in p["kinds"]:
                    findings.append((0, path, f"our float where specimens have kinds {dict(p['kinds'])}"))
            elif d[0] == "null":
                pass
        # kind mismatch (e.g. ours int, specimens float)
        for k in kinds:
            if k not in p["kinds"] and k != "null":
                findings.append((0, path, f"our leaf KIND {k!r} never seen; specimen kinds {dict(p['kinds'])}"))
    findings.sort()
    return findings


# ---------------------------------------------------------------------------
# collect specimens
# ---------------------------------------------------------------------------

def collect():
    pen_prof = Profile(); pen_hdr = Profile()
    gs_prof = Profile(); gs_hdr = Profile()
    gs_builtin_prof = Profile(); gs_builtin_hdr = Profile()      # host, m_famId==-1, builtin category (<0)
    pen_specimens = []
    gs_examples = {}
    gs_count = collections.Counter()
    pen_scales = collections.Counter()
    pen_widths_all = []
    for s in SAMPLES:
        try:
            doc = Document.load(s)
        except Exception as e:                      # noqa: BLE001
            print(f"!! {s}: load failed: {e}")
            continue
        # ---- pen tables (host + family scoped) ----
        pids = doc.ids_of_class("PenWidthTableElem", host_only=False)
        for pid in pids:
            v = doc.value(pid)
            if v is None:
                continue
            h = doc.decode(pid, 101)
            hv = h.value if h else None
            host = doc.in_host_document(pid)
            tag = f"{s}:{pid}"
            pen_specimens.append({"file": s, "id": pid, "host": host,
                                  "famId": v.get("m_famId"), "obj": v, "hdr": hv})
            fl = _clean_flatten(v)
            pen_prof.add(fl, tag)
            if hv:
                pen_hdr.add(_clean_flatten(hv), tag)
            t = (v.get("m_pPenWidthTable") or {}).get("value") or {}
            for pi in t.get("m_modelPenInfo") or []:
                pen_scales[pi.get("m_invertedScale")] += 1
            # widths in mm
            for key in ("m_modelPenInfo",):
                for pi in t.get(key) or []:
                    pen_widths_all.extend(round(x * 304.8, 4) for x in pi.get("m_pens") or [])
        # ---- gstyles ----
        gids = doc.ids_of_class("GStyleElem", host_only=False)
        for gid in gids:
            v = doc.value(gid)
            if v is None:
                continue
            h = doc.decode(gid, 101)
            hv = h.value if h else None
            host = doc.in_host_document(gid)
            tag = f"{s}:{gid}"
            gs_count[(s, host, v.get("m_famId", -1) == -1, isinstance(v.get("m_categoryId"), int) and v.get("m_categoryId") < 0)] += 1
            fl = _clean_flatten(v)
            gs_prof.add(fl, tag)
            if hv:
                gs_hdr.add(_clean_flatten(hv), tag)
            builtin = (host and v.get("m_famId", -1) == -1 and v.get("m_ownerId", -1) == -1
                       and isinstance(v.get("m_categoryId"), int) and v.get("m_categoryId") < 0)
            if builtin:
                gs_builtin_prof.add(fl, tag)
                if hv:
                    gs_builtin_hdr.add(_clean_flatten(hv), tag)
                if len(gs_examples) < 4 and s not in gs_examples:
                    gs_examples[s] = {"id": gid, "obj": v, "hdr": hv}
        print(f"   [{s}] pen tables {len(pids)}, gstyles {len(gids)}")
    return dict(pen_prof=pen_prof, pen_hdr=pen_hdr, gs_prof=gs_prof, gs_hdr=gs_hdr,
                gs_builtin_prof=gs_builtin_prof, gs_builtin_hdr=gs_builtin_hdr,
                pen_specimens=pen_specimens, gs_examples=gs_examples,
                gs_count=gs_count, pen_scales=pen_scales, pen_widths_all=pen_widths_all)


def main():
    print("== collecting specimens ==")
    R = collect()
    # ---- ours ----
    print("== building OURS ==")
    src = IdSource(2_000_000)
    our_pen = S.pen_width_table(ids=src)
    our_gs = C.builtin_style_catalog(src)[0]              # first row (a projection style)
    # a cut row too
    our_gs_cut = [r for r in C.builtin_style_catalog(IdSource(3_000_000)) if r.refs.get("style_type") == 2][0]

    rep = {}
    # pen table diff (project pen tables only: host + famId==-1) -> profile subset
    print("== diff: pen table (obj) vs ALL pen tables ==")
    f_pen = diff_ours(_clean_flatten(our_pen.obj), R["pen_prof"], "pen")
    print("== diff: pen table (header) ==")
    f_pen_hdr = diff_ours(_clean_flatten(our_pen.header), R["pen_hdr"], "pen_hdr")
    print("== diff: gstyle projection row (obj) vs BUILT-IN host rows ==")
    f_gs = diff_ours(_clean_flatten(our_gs.obj), R["gs_builtin_prof"], "gstyle")
    f_gs_cut = diff_ours(_clean_flatten(our_gs_cut.obj), R["gs_builtin_prof"], "gstyle_cut")
    f_gs_hdr = diff_ours(_clean_flatten(our_gs.header), R["gs_builtin_hdr"], "gstyle_hdr")

    def show(title, findings, cap=200):
        lines = [f"\n### {title}  ({len(findings)} findings)"]
        for sev, path, msg in findings[:cap]:
            lines.append(f"  sev{sev} {path or '<root>'}: {msg}")
        return "\n".join(lines)

    txt = []
    txt.append(f"pen table specimens: {len(R['pen_specimens'])} "
               f"({sum(1 for p in R['pen_specimens'] if p['host'] and (p['famId'] in (None,-1)))} project tables famId=-1 host)")
    txt.append(f"pen model scales histogram (all specimens): {dict(sorted(R['pen_scales'].items()))}")
    widths = sorted(set(R['pen_widths_all']))
    txt.append(f"pen widths mm seen (min..max): {min(widths)} .. {max(widths)}; distinct={len(widths)}: {widths}")
    txt.append(f"gstyle rows by (file, host, famId==-1, builtin cat<0): "
               + json.dumps({repr(k): v for k, v in R['gs_count'].items()}))
    txt.append(show("PEN TABLE object", f_pen))
    txt.append(show("PEN TABLE header (seq101)", f_pen_hdr))
    txt.append(show("GSTYLE projection row object (vs built-in host rows)", f_gs))
    txt.append(show("GSTYLE cut row object", f_gs_cut))
    txt.append(show("GSTYLE header (seq101)", f_gs_hdr))
    text = "\n".join(txt)
    print(text)
    with open(os.path.join(OUT, "census_report.txt"), "w") as fh:
        fh.write(text + "\n")
    # dump the raw profiles for the record
    def prof_json(prof: Profile):
        return {path or "<root>": prof.summary(path) for path in sorted(prof.paths)}
    dump = {
        "pen_object_profile": prof_json(R["pen_prof"]),
        "pen_header_profile": prof_json(R["pen_hdr"]),
        "gstyle_builtin_object_profile": prof_json(R["gs_builtin_prof"]),
        "gstyle_builtin_header_profile": prof_json(R["gs_builtin_hdr"]),
        "gstyle_all_object_profile": prof_json(R["gs_prof"]),
        "pen_specimens": [{k: v for k, v in p.items() if k in ("file", "id", "host", "famId")}
                          for p in R["pen_specimens"]],
        "our_pen_obj": our_pen.obj, "our_pen_hdr": our_pen.header,
        "our_gstyle_obj": our_gs.obj, "our_gstyle_hdr": our_gs.header,
        "our_gstyle_cut_obj": our_gs_cut.obj,
        "findings": {"pen_obj": f_pen, "pen_hdr": f_pen_hdr, "gstyle_obj": f_gs,
                     "gstyle_cut_obj": f_gs_cut, "gstyle_hdr": f_gs_hdr},
        "pen_scales": dict(R["pen_scales"]),
        "pen_widths_mm_distinct": widths,
    }
    with open(os.path.join(OUT, "census_dump.json"), "w") as fh:
        json.dump(dump, fh, indent=1, default=str)
    # also dump each pen specimen fully for hand inspection
    with open(os.path.join(OUT, "pen_specimens_full.json"), "w") as fh:
        json.dump(R["pen_specimens"], fh, indent=1, default=str)
    with open(os.path.join(OUT, "gstyle_examples.json"), "w") as fh:
        json.dump(R["gs_examples"], fh, indent=1, default=str)
    print(f"\nwrote {OUT}/census_report.txt census_dump.json pen_specimens_full.json gstyle_examples.json")


if __name__ == "__main__":
    main()
