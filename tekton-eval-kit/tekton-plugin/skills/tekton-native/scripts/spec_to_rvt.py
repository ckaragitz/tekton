#!/usr/bin/env python3
"""spec_to_rvt.py — generate a NATIVE .rvt from a building/room spec.

    python tools/spec_to_rvt.py --spec usecases/chicago-plenum-electrical-room/room-spec.json \
        --out experiments/acceptance/V23_electrical_room.rvt [--offset-m 10 -25]

Consumes the same spec format the IFC generator uses (metres, degrees;
walls with start/end/height/type, equipment with kind/position/rotation/
elevation) and drives the proven authoring pipeline against a template
project that already has the needed wall types and equipment symbols
loaded (default: the Revit MEP sample 'rmebasicsampleproject'):

    Document.add_wall / Document.add_family_instance   ->  NewElements
    Document.serialize                                 ->  framed records
    commit.commit_new_elements                          ->  the .rvt file
    commit.verify_written                                ->  structural proof

Placement patterns (from KNOWLEDGE.md):
  - transformers / switchboards are floor-standing (level-hosted, hostId -1)
  - panelboards are wall/face-hosted families; hosting on NEWLY created
    walls needs SketchPlanes on those walls (phase 2), so this v1 places
    panels FREE-STANDING at their spec positions (host removed). If Revit
    rejects an unhosted wall family, use --panel-host <SketchPlaneId> to
    host panels on an existing face instead.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.commit import commit_new_elements, verify_written  # noqa: E402
from rvt.mutate import Document  # noqa: E402

FT_PER_M = 3.280839895

# Template project -> the loaded content we author with.
TEMPLATES = {
    "rmebasicsampleproject": {
        "sample": "samples/rmebasicsampleproject.rvt",
        "levels": {"L1": 378117, "L2": 378118},          # Level 1 / Level 2
        "wall_type": 563416,                                # most-used basic wall
        "equipment": {
            # kind -> (symbol_id, template_instance_id, hosting)
            "panelboard": (619617, 742670, "free"),   # 480V MCB Surface :: 400 A
            "transformer": (621242, 624416, "free"),  # Dry Type Transformer :: 500 kVA
            "switchboard": (629946, None, "free"),
        },
    },
}


def m2ft(v: float) -> float:
    return float(v) * FT_PER_M


# ---------------------------------------------------------------------------
# Auto-discovery for an ARBITRARY template file (the plugin path): resolve
# levels / wall types / equipment symbols by NAME, not by hardcoded ids.
# ---------------------------------------------------------------------------
KIND_KEYWORDS = {
    "panelboard": ("panelboard", "panel", "distribution board"),
    "switchboard": ("switchboard", "switchgear", "circuit breaker switchboard"),
    "transformer": ("transformer", "xfmr"),
    "lightfixture": ("light", "luminaire", "fixture"),
}
ELEC_EQUIP_CAT = -2001040  # OST_ElectricalEquipment
LIGHT_FIXTURE_CAT = -2001120  # OST_LightingFixtures
KIND_CATEGORY = {"lightfixture": LIGHT_FIXTURE_CAT}  # kinds outside electrical equipment


def _tokens(s: str):
    """Lowercase tokens, splitting letter/digit runs ('480y' -> '480','y',
    '400a' -> '400','a') so ratings match across '480Y/277 V' vs '480V'."""
    out = set()
    for chunk in re.split(r"[^a-z0-9]+", (s or "").lower()):
        for t in re.findall(r"[a-z]+|[0-9]+", chunk):
            if len(t) > 1 or t.isdigit():
                out.add(t)
    return out


def _amperage(name: str) -> int:
    """Largest 'NNN A' ampere rating found in a symbol name (0 if none)."""
    vals = [int(m) for m in re.findall(r"(\d{2,5})\s*a\b", (name or "").lower())]
    return max(vals) if vals else 0


def discover_template(doc, spec: dict) -> dict:
    """Build a TEMPLATES-style config by inspecting a loaded Document."""
    tpl = {"levels": {}, "wall_type": None, "equipment": {}}
    # levels: match spec level names, else map in elevation order
    lv = doc.levels()
    by_name = {str(l.get("name", "")).strip().lower(): l["id"] for l in lv}
    ordered = [l["id"] for l in sorted(lv, key=lambda x: x.get("elevation", 0.0))]
    for i, sl in enumerate(spec.get("levels", []) or [{"id": "L1", "name": "Level 1"}]):
        want = str(sl.get("name", "")).strip().lower()
        tpl["levels"][sl["id"]] = by_name.get(want, ordered[min(i, len(ordered) - 1)] if ordered else None)
    if "L1" not in tpl["levels"] and ordered:
        tpl["levels"]["L1"] = ordered[0]
    # wall type: most-instanced basic wall
    wt = doc.wall_types_with_instances()
    if wt:
        tpl["wall_type"] = max(wt.items(), key=lambda kv: len(kv[1]))[0]
    # equipment: score symbols in the electrical-equipment category
    all_syms = doc.symbols()
    for kind, keys in KIND_KEYWORDS.items():
        cat = KIND_CATEGORY.get(kind, ELEC_EQUIP_CAT)
        syms = [s for s in all_syms if s.get("category") == cat]
        want_tokens = set()
        wants_mcb = wants_mlo = False
        for eq in spec.get("equipment", []):
            if str(eq.get("kind", "")).lower() != kind:
                continue
            want_tokens |= _tokens(eq.get("typeName", ""))
            # electrical ratings hidden in psets (voltage, bus/mains rating, breaker style)
            for pname, props in (eq.get("psets") or {}).items():
                for pk, pv in (props or {}).items():
                    val = pv.get("value") if isinstance(pv, dict) else pv
                    want_tokens |= _tokens(str(val))
                    if pk.lower() in ("mainstype",):
                        vl = str(val).lower()
                        wants_mcb |= "breaker" in vl
                        wants_mlo |= "lug" in vl
        best, best_score = None, -1
        for s in syms:
            name = f"{s.get('family_name','')} {s.get('symbol_name','')}"
            low = name.lower()
            if not any(k in low for k in keys):
                continue
            score = 10 + 3 * len(want_tokens & _tokens(name))
            if wants_mcb and "mcb" in low:
                score += 4
            if wants_mlo and "mlo" in low:
                score += 4
            if not (wants_mcb or wants_mlo) and "mcb" in low:
                score += 1          # main-breaker panel = the safe generic default
            # tie-break: larger ampere rating in the type name is the more
            # representative distribution panel (0.001-scaled so it never
            # outranks a real token match)
            score += _amperage(name) * 0.001
            if score > best_score:
                best, best_score = s, score
        if best:
            tpl["equipment"][kind] = (best["symbol_id"], None, "free")
    return tpl


def build(spec: dict, template_key: str, offset_m=(0.0, 0.0), panel_host=None,
          template_rvt: str | None = None, wall_type_override: int | None = None,
          auto_circuits: bool = False):
    if template_rvt:
        doc = Document.from_file(template_rvt)
        tpl = discover_template(doc, spec)
    else:
        tpl = TEMPLATES[template_key]
        doc = Document.load(template_key)
    if wall_type_override:
        tpl["wall_type"] = int(wall_type_override)
    ox, oy = m2ft(offset_m[0]), m2ft(offset_m[1])
    default_level = tpl["levels"]["L1"]
    level_map = {}
    for lv in spec.get("levels", []):
        level_map[lv["id"]] = tpl["levels"].get(lv["id"], default_level)

    records, plans, log = [], [], []
    elements, by_name = [], {}

    # ---- walls -------------------------------------------------------------
    wall_type = tpl.get("wall_type")
    tpl_wall = doc._template_wall(wall_type) if wall_type else None
    if wall_type is None and spec.get("walls"):
        log.append("SKIP  walls: template has no placed wall to clone (place one wall of the desired type in the template)")
    for w in (spec.get("walls", []) if wall_type is not None else []):
        p0 = (m2ft(w["start"][0]) + ox, m2ft(w["start"][1]) + oy, 0.0)
        p1 = (m2ft(w["end"][0]) + ox, m2ft(w["end"][1]) + oy, 0.0)
        h = m2ft(w.get("height", 3.0))
        el = doc.add_wall(default_level, wall_type, p0, p1, height=h, template_id=tpl_wall)
        elements.append(el)
        log.append(f"wall  {w.get('id','?'):10s} id={el.elem_id} type={wall_type} "
                   f"{p0[:2]} -> {p1[:2]} ft, h={h:.2f} ft")

    # ---- equipment ---------------------------------------------------------
    for eq in spec.get("equipment", []):
        kind = str(eq.get("kind", "")).lower()
        if kind not in tpl["equipment"]:
            log.append(f"SKIP  {eq.get('name','?')}: unsupported kind {kind!r}")
            continue
        sym, tinst, hosting = tpl["equipment"][kind]
        if tinst is None:
            tinst = doc._template_instance(sym, doc.category_of(sym))
        x, y = eq["position"][0], eq["position"][1]
        z = float(eq.get("elevation", 0.0))
        pos = (m2ft(x) + ox, m2ft(y) + oy, m2ft(z))
        rot = math.radians(float(eq.get("rotationDeg", 0.0)))
        lvl = level_map.get(eq.get("level", "L1"), default_level)
        host_id = None
        if kind == "panelboard" and panel_host is not None:
            host_id = int(panel_host)
        el = doc.add_family_instance(sym, lvl, position=pos, rotation=rot,
                                     host_id=host_id, template_instance_id=tinst)
        elements.append(el)
        by_name[str(eq.get("name", ""))] = (el, kind)
        log.append(f"equip {eq.get('name','?'):12s} {kind:11s} id={el.elem_id} symbol={sym} "
                   f"at ({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.2f}) ft rot={eq.get('rotationDeg',0)}deg "
                   f"{'host='+str(host_id) if host_id else 'free-standing'}")

    # ---- circuits ----------------------------------------------------------
    # explicit: spec["circuits"] = [{"panel": name, "load": name, "description",
    #   "rating", "poles", "number"}]; auto: each transformer/switchboard on its
    # own breaker off the first panelboard. Panel + load must both be created
    # in this same run (mutual connector links are wired before serialization).
    circuits = list(spec.get("circuits") or [])
    if auto_circuits and not circuits:
        panels = [n for n, (e, k) in by_name.items() if k == "panelboard"]
        loads = [n for n, (e, k) in by_name.items() if k in ("transformer", "switchboard")]
        if panels:
            for i, ln in enumerate(loads, 1):
                circuits.append({"panel": panels[0], "load": ln, "number": str(i),
                                 "description": f"{ln} feeder"})
    for i, c in enumerate(circuits, 1):
        pn, ln = str(c.get("panel", "")), str(c.get("load", ""))
        if pn not in by_name or ln not in by_name:
            log.append(f"SKIP  circuit {pn}->{ln}: both ends must be created in this run")
            continue
        cel = doc.add_circuit(by_name[pn][0], by_name[ln][0],
                              number=str(c.get("number", i)),
                              description=c.get("description") or f"{ln} feeder",
                              rating=c.get("rating"), poles=c.get("poles"))
        elements.append(cel)
        log.append(f"circ  {c.get('number', i)!s:6} id={cel.elem_id} panel {pn} -> load {ln}  "
                   f"({cel.notes[0].split(';')[1].strip() if len(cel.notes[0].split(';'))>1 else ''})")

    # ---- serialize AFTER wiring (connector back-links land in the records)
    for el in elements:
        records.append(dict(doc.serialize(el)))
        plans.append(el.elemrec)
    return records, plans, log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="spec.json -> native .rvt")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--template", default="rmebasicsampleproject", choices=list(TEMPLATES),
                    help="named research template (used only when --template-rvt is absent)")
    ap.add_argument("--template-rvt", default=None,
                    help="PATH to ANY template .rvt (walls + equipment loaded). Preferred / plugin path.")
    ap.add_argument("--wall-type", type=int, default=None, help="override the wall type element id")
    ap.add_argument("--auto-circuits", action="store_true",
                    help="create one circuit per transformer/switchboard off the first panelboard")
    ap.add_argument("--offset-m", nargs=2, type=float, default=[10.0, -25.0],
                    metavar=("X", "Y"), help="place the spec origin at this world offset (metres)")
    ap.add_argument("--panel-host", default=None,
                    help="SketchPlane id to face-host panelboards on (default: free-standing)")
    a = ap.parse_args(argv)

    spec = json.load(open(a.spec))
    records, plans, log = build(spec, a.template, tuple(a.offset_m), a.panel_host,
                                template_rvt=a.template_rvt, wall_type_override=a.wall_type,
                                auto_circuits=a.auto_circuits)
    print(f"planned {len(records)} elements from {os.path.basename(a.spec)}:")
    for line in log:
        print("  " + line)
    if not records:
        print("nothing to write")
        return 1

    src = os.path.abspath(a.template_rvt) if a.template_rvt else os.path.join(ROOT, TEMPLATES[a.template]["sample"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    rep = commit_new_elements(src, a.out, records, plans)
    ids = [p.elem_id for p in plans]
    v = verify_written(a.out, ids)
    print(f"\nwritten: {a.out} ({os.path.getsize(a.out):,} bytes)")
    print(f"  ElemTable {rep.elemtable_count_before} -> {rep.elemtable_count_after}; "
          f"CRC failures {v['crc_failures']}; ECC mismatches {v['ecc_mismatches']}; "
          f"walker errors {v['walker_errors']}; stamps ok {v['stamps_ok']}")
    found = {s: sum(1 for x in v['new_ids_found'][s].values() if x['clean']) for s in (101, 102, 103)}
    print(f"  new elements decoding clean per seq: {found} (expect {len(ids)} each); "
          f"counts match {v['elemtable_count'] == v['header_count']}; "
          f"sentinels last {all(v['sentinel_last'].values())}")
    ok = (v['crc_failures'] == 0 and v['ecc_mismatches'] == 0 and v['walker_errors'] == 0
          and v['stamps_ok'] and all(n == len(ids) for n in found.values()))
    print("  VERDICT:", "STRUCTURALLY VALID" if ok else "CHECK REPORT")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
