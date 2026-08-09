#!/usr/bin/env python3
"""Which LeaderStyle (arrowhead) parameter id is the ANGLE and which is the SIZE (#343)?

Two verbs, both read only tracked repo files (derived statistics / decoded JSON of our own
births -- never anything under samples/):

  table        the corpus reading. Prints, per param id, the value distribution of every
               Revit-born arrowhead the tracked tree pairs an id with a value for:
                 * experiments/genesis/subst_k4/residue_a/invariants/LeaderStyle.json -- 1024
                   arrowheads / 6 sample projects: the id ENUM, the merged value histogram split
                   into a radians cluster (>= 0.1) and a feet cluster (< 0.1), and the first-seen
                   (id, value) insertion order of the two histograms;
                 * experiments/genesis/subst_k4/residue_a/Z_annot.json -- LeaderStyle id 285, the
                   certified PARENT's own pairs next to OURS;
                 * experiments/birthright/template_birth.json -- the 7 arrowheads of the birth
                   template, (id, value) pairs + the type name (one is literally 'Diagonal 1/8"');
                 * plugin/assets/genesis/G_ABPD.rvt -- what OUR certified 2026 base carries today
                   (skipped with a note if the engine is not importable).
  fingerprint  the byte-identity instrument for the rename: builds every arrowhead the engine
               can emit (arrowhead_type defaults + the demo call, the house arrowhead and each
               secret role through inplace_arrowhead, with and without the width-pen int set),
               encodes each with the genesis encoder and prints {case: sha256, pairs} as JSON.
               Run it on main and on the branch; `diff` of the two outputs must be empty.

  python3 tools/dev/arrow_param_ids.py table [--md]
  .venv/bin/python tools/dev/arrow_param_ids.py fingerprint > before.json   (needs the engine)
"""
import argparse, collections, hashlib, json, math, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INVARIANT = os.path.join(ROOT, "experiments/genesis/subst_k4/residue_a/invariants/LeaderStyle.json")
Z_ANNOT = os.path.join(ROOT, "experiments/genesis/subst_k4/residue_a/Z_annot.json")
BIRTH = os.path.join(ROOT, "experiments/birthright/template_birth.json")
BASE_2026 = os.path.join(ROOT, "plugin/assets/genesis/G_ABPD.rvt")
SIZE_ID, ANGLE_ID = IDS = (-1006414, -1006426)      # the verdict this tool establishes (section 3)
WIDTH_PEN_ID = -1006447
RADIANS_FLOOR = 0.1          # no arrow SIZE in feet reaches 0.1 ft (30 mm); no arrow ANGLE is below 5.7 deg
DOT_TICK_TYPE = 11           # the filled 'Elevation Target' dot: the one arrowhead with angle 0.0


def _load(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _engine() -> None:
    """Make `rvt` importable (idempotent); only the verbs that need the engine call it."""
    src = os.path.join(ROOT, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _pairs(obj: dict, kind: str = "Double") -> list:
    """[(param id, value)] of an object's ParamValueSet<kind>, in file order ([] if null)."""
    ps = ((obj.get(f"m_pParamValueSet{kind}") or {}).get("value") or {}).get("m_paramSet") or []
    cast = float if kind == "Double" else int
    return [(int(p["m_paramId"]), cast(p["m_value"])) for p in ps if isinstance(p, dict)]


def _name(obj: dict):
    return ((obj.get("m_symbolInfo") or {}).get("value") or {}).get("m_name")


def _cluster(v: float) -> str:
    return "radians" if v >= RADIANS_FLOOR else "feet"


def _pretty(v: float) -> str:
    """A value as an engineer reads it: degrees if it is a round angle, else inches / mm."""
    deg = math.degrees(v)
    if v >= RADIANS_FLOOR and abs(deg - round(deg)) < 1e-6:
        return f"{round(deg)} deg"
    inch = v * 12.0
    for den in (1, 2, 4, 8, 16, 32, 64, 128, 256):
        if abs(inch * den - round(inch * den)) < 1e-9:
            return f'{round(inch * den)}/{den}"' if den > 1 else f'{round(inch)}"'
    return f"{v * 304.8:.3f} mm"


def _cell(v: float) -> str:
    return f"{v!r} = {_pretty(v)}"


def invariant_reading(path: str = INVARIANT) -> dict:
    d = _load(path)
    p = d["paths"]
    ids = p["m_pParamValueSetDouble->ParamValueSetDouble.m_paramSet[].m_paramId"]
    vals = p["m_pParamValueSetDouble->ParamValueSetDouble.m_paramSet[].m_value"]
    hist = {float(k): int(n) for k, n in vals["values"].items()}
    clusters = {"radians": {}, "feet": {}}
    for v, n in hist.items():
        clusters[_cluster(v)][v] = n
    return {
        "n_specimens": d["n_specimens"], "files": len(d["per_file"]),
        "set_len": p["m_pParamValueSetDouble->ParamValueSetDouble.m_paramSet.#len"]["values"],
        "id_counts": {int(k): int(n) for k, n in ids["values"].items()},
        "id_first_seen": int(next(iter(ids["values"]))),
        "value_first_seen": float(next(iter(vals["values"]))),
        "value_range": [vals["num_min"], vals["num_max"]],
        "histogram_overflow": bool(vals["overflow"]),
        "histogram_covered": sum(hist.values()), "histogram_total": int(vals["n_seen"]),
        "clusters": {c: {"n": sum(h.values()), "values": sorted(h.items())} for c, h in clusters.items()},
    }


def z_annot_reading(path: str = Z_ANNOT, elem_id: int = 285) -> dict:
    """{'parent': [(id, value)...], 'ours': [...]} of the LeaderStyle field-diff entry `elem_id`."""
    def find(o):
        if isinstance(o, dict):
            if o.get("id") == elem_id and any((f or {}).get("class_parent") == "LeaderStyle"
                                              for f in o.get("field_diff", [])):
                return o
            o = list(o.values())
        if isinstance(o, list):
            for v in o:
                hit = find(v)
                if hit:
                    return hit
        return None

    entry = find(_load(path))
    if not entry:
        return {}
    side = {"parent": {}, "ours": {}}
    for f in entry["field_diff"]:
        path = f.get("path", "")
        if ".m_paramSet[" in path:
            idx = int(path.split("m_paramSet[")[1].split("]")[0])
            leaf = path.rsplit(".", 1)[1]
            for who in side:
                side[who].setdefault(idx, {})[leaf] = f[who]
    return {who: [(int(r["m_paramId"]), float(r["m_value"])) for _, r in sorted(rows.items())]
            for who, rows in side.items()}


def birth_reading(path: str = BIRTH) -> list:
    rows = []
    for i, be in enumerate(_load(path).get("birth_elements", [])):
        obj = be.get("obj") if isinstance(be, dict) else None
        if not isinstance(obj, dict) or "m_tickType" not in obj:
            continue
        pairs = _pairs(obj)
        if {pid for pid, _ in pairs} != set(IDS):
            continue
        nm = _name(obj)
        if isinstance(nm, dict):                                   # scrubbed secret name -> its stem
            nm = (nm.get("__author__") or {}).get("shape_stem", "?") + "…"
        rows.append({"index": i, "name": nm, "tick_type": obj.get("m_tickType"), "pairs": pairs})
    return rows


def base_reading(path: str = BASE_2026) -> list:
    _engine()
    from rvt.mutate import Document                                  # noqa: E402
    doc = Document.from_file(path)
    rows = []
    for e in doc.et_by_id:
        if doc.class_of(int(e)) == "LeaderStyle":
            v = doc.value(int(e)) or {}
            rows.append({"id": int(e), "name": _name(v), "tick_type": v.get("m_tickType"), "pairs": _pairs(v)})
    return rows


def per_id_table(z: dict, birth: list) -> dict:
    """{id: {'radians': Counter, 'feet': Counter}} over every Revit-born (id, value) pair."""
    t = {pid: {"radians": collections.Counter(), "feet": collections.Counter()} for pid in IDS}
    for pid, v in z.get("parent", []) + [p for r in birth for p in r["pairs"]]:
        t[pid][_cluster(v)][float(f"{v:.12g}")] += 1          # 1/64" arrives in two float spellings
    return t


def cmd_table(md: bool) -> int:
    def head(*cols):
        if md:
            print("| " + " | ".join(cols) + " |")
            print("|" + "---|" * len(cols))

    def row(*cells):
        print(("| " + " | ".join(cells) + " |") if md else "  " + " ; ".join(cells))

    inv = invariant_reading()
    z = z_annot_reading()
    birth = birth_reading()
    print("# LeaderStyle arrow parameter ids -- corpus reading (#343)\n")
    print(f"## 1. invariants/LeaderStyle.json: {inv['n_specimens']} Revit-born arrowheads, {inv['files']} projects\n")
    print(f"* every arrowhead carries a ParamValueSetDouble of exactly {list(inv['set_len'])} entries; "
          f"id multiset {inv['id_counts']} (each id once per arrowhead)")
    print(f"* value RANGE {inv['value_range']}; top-{sum(len(c['values']) for c in inv['clusters'].values())} "
          f"histogram covers {inv['histogram_covered']}/{inv['histogram_total']} values "
          f"(overflow={inv['histogram_overflow']}) and splits into two magnitude clusters with nothing between "
          f"0.0105 and 0.26:")
    for c in ("radians", "feet"):
        cl = inv["clusters"][c]
        print(f"  * {c:7s} cluster: {cl['n']:4d} values -- " +
              ", ".join(f"{_pretty(v)} x{n}" for v, n in sorted(cl['values'], key=lambda kv: -kv[1])))
    print(f"* insertion order of the two histograms (= paramSet[0] of the first arrowhead scanned): "
          f"first id {inv['id_first_seen']}, first value {inv['value_first_seen']} "
          f"({_pretty(inv['value_first_seen'])}, {_cluster(inv['value_first_seen'])})")
    print("  -> the invariant alone proves one id is always an angle and the other always a length "
          "(2 ids x 1024, two disjoint clusters of ~1024 each) and points at -1006426 = angle via "
          "insertion order; the PAIRED sources below settle it.\n")
    print("## 2. Paired (id, value) evidence from Revit-born records in the tracked tree\n")
    head("source", "arrowhead", f"{ANGLE_ID} carries", f"{SIZE_ID} carries")
    if z:
        pz = dict(z["parent"])
        row("Z_annot.json id 285 (certified PARENT)", "SecretInternalLinAngArrowhead…",
            _cell(pz[ANGLE_ID]), _cell(pz[SIZE_ID]))
    for r in birth:
        p = dict(r["pairs"])
        row(f"template_birth.json [{r['index']}] tick {r['tick_type']}", str(r["name"]),
            _cell(p[ANGLE_ID]), _cell(p[SIZE_ID]))
    print("\n## 3. Per-id distribution over those Revit-born pairs\n")
    head("param id", "n", "radians-range values (0.1..pi/2)", "feet-range values (< 0.1 ft)", "verdict")
    for pid, cl in per_id_table(z, birth).items():
        rad, ft = cl["radians"], cl["feet"]
        verdict = "ANGLE (radians)" if rad and not ft else "SIZE (feet)" if not rad else "mixed"
        if rad and set(ft) == {0.0}:
            verdict = f"ANGLE (radians; the one 0.0 is the 'Filled Elevation Target' dot, tick {DOT_TICK_TYPE})"
        row(str(pid), str(sum(rad.values()) + sum(ft.values())),
            ", ".join(f"{_pretty(v)} x{c}" for v, c in sorted(rad.items())) or "—",
            ", ".join(f"{_pretty(v)} x{c}" for v, c in sorted(ft.items())) or "—", verdict)
    print("\n## 4. What OUR certified 2026 base carries today (plugin/assets/genesis/G_ABPD.rvt)\n")
    try:
        ours = base_reading()
    except Exception as ex:                                        # engine not importable here
        print(f"  (skipped: {type(ex).__name__}: {ex})")
        ours = []
    if ours:
        head("id", "name", "tick", "paramSet as written")
    for r in ours:
        row(str(r["id"]), str(r["name"]), str(r["tick_type"]),
            " ".join(f"({pid}, {_cell(v)})" for pid, v in r["pairs"]))
    if z.get("ours"):
        print(f"\n  Z_annot.json id 285 OURS side: {z['ours']}  (radians under {SIZE_ID}, feet under {ANGLE_ID})")
    print(f"\nVERDICT: {ANGLE_ID} = arrow ANGLE (radians), {SIZE_ID} = arrow SIZE (feet) in every Revit-born "
          f"record; residue_a.py's names had them the other way round, and our certified bases carry our "
          f"angle under {SIZE_ID} and our size under {ANGLE_ID} (bytes kept; see #343's record).")
    return 0


def fingerprint() -> dict:
    _engine()
    from rvt.genesis import residue_a as RA                                        # noqa: E402
    from rvt.genesis.types import _S, blank_object, element_defaults, symbol_defaults  # noqa: E402
    enc = _S()[1]
    cases = {}

    def add(key, obj):
        body = enc.encode_object(obj.class_id, obj.value)
        cases[key] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                      "double_pairs": _pairs(obj.value), "int_pairs": _pairs(obj.value, "Int"),
                      "name": _name(obj.value)}

    add("arrowhead_type/defaults", RA.arrowhead_type(RA.gen("Arrow Filled 20 Degree"), category_id=99, elem_id=5))
    add("arrowhead_type/demo", RA.arrowhead_type(RA.gen("Arrow Filled 20 Degree"),
                                                 category_id=5_000_300, elem_id=5_000_301))
    add("arrowhead_type/no-width-pen", RA.arrowhead_type("X", category_id=7, angle_deg=35.0, size_mm=4.5,
                                                          width_pen=None, elem_id=8))
    for role in list(RA.SECRET_ARROW_ROLES) + ["", "Unlisted"]:
        for with_int in (True, False):
            slot = blank_object("LeaderStyle")                     # a Revit-shaped slot: angle id first
            element_defaults(slot, 285, double_params={ANGLE_ID: 0.5235987755982984, SIZE_ID: 0.001302083333333333},
                             int_params=({WIDTH_PEN_ID: 1} if with_int else None), design_option=-4)
            name = f"SecretInternal{role}547r36186" if role else "Arrowhead 30 Degree"
            symbol_defaults(slot, name)
            slot["m_categoryId"] = 286
            slot["m_tickType"] = 0
            add(f"inplace_arrowhead/{name}/int={with_int}", RA.inplace_arrowhead(slot))
    return cases


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="verb", required=True)
    sub.add_parser("table").add_argument("--md", action="store_true", help="markdown tables")
    sub.add_parser("fingerprint")
    a = ap.parse_args(argv)
    if a.verb == "table":
        return cmd_table(a.md)
    json.dump(fingerprint(), sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
