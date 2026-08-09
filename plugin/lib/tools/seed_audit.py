#!/usr/bin/env python3
"""seed_audit.py — is a firm's SEED project ready to author from?

    python tools/seed_audit.py <seed.rvt> [--job usecases/.../room-spec.json]
                             [--json out.json] [--full]

A seed is the firm's own template project, exported once from THEIR
licensed seat: their standards (levels, wall types, view templates,
titleblock, phases) plus one placed instance of every family they build
with. The writer authors by CLONING a placed specimen of each type, so the
audit checks two things:

1. INVENTORY  — what the seed contains, with real names resolved
   (rvt.inventory): levels, wall types (name + thickness + walls placed),
   family symbols (family :: type, category, placed instances, hosting),
   titleblocks, view templates, phases.

2. COVERAGE (with --job spec.json) — for every wall type / door / equipment
   the job asks for: the best matching seed content (spec_to_rvt's scoring:
   kind keyword + name/rating token overlap + MCB/MLO + amperage tie-break)
   or MISSING, each with a plain-English fix telling the firm exactly what to
   add to the seed ("load a panelboard family into your seed and place one
   instance").

Accepts either a .rvt path or a research-corpus name (e.g. rmebasicsampleproject).
A path is read under the seed's OWN Revit release (rvt.global_framing's
lenient ladder, entered once around the audit and restored on exit), so a
firm on Revit 2025 / 2024 audits its own seed; if the seed's schema cannot
settle the framing the report says which fallback was used (``release_note``).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import sys
from contextlib import ExitStack

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import inventory as inv  # noqa: E402
from rvt.global_framing import enter_own_release  # noqa: E402
from rvt.mutate import Document  # noqa: E402

FT_PER_M = 3.280839895


def _load_spec_to_rvt():
    """Reuse spec_to_rvt's scoring vocabulary (single source of truth)."""
    p = os.path.join(HERE, "spec_to_rvt.py")
    s = importlib.util.spec_from_file_location("spec_to_rvt", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_S2R = _load_spec_to_rvt()
_tokens = _S2R._tokens
_amperage = _S2R._amperage
KIND_KEYWORDS = dict(_S2R.KIND_KEYWORDS)
ELEC_EQUIP_CAT = _S2R.ELEC_EQUIP_CAT           # -2001040
LIGHT_FIXTURE_CAT = -2001120
DOOR_CAT = -2000023

# categories in which each spec kind must live
KIND_CATEGORIES = {
    "panelboard": (ELEC_EQUIP_CAT,),
    "switchboard": (ELEC_EQUIP_CAT,),
    "transformer": (ELEC_EQUIP_CAT,),
    "lightfixture": (LIGHT_FIXTURE_CAT,),
}
# family names that trip a kind keyword but are NOT that kind of gear
KIND_EXCLUDE = {
    "panelboard": ("photovoltaic", "solar", "schedule", "curtain", "access",
                   "acoustic", "radiant", "ceiling panel", "wall panel"),
    "switchboard": ("photovoltaic", "solar"),
    "transformer": (),
    "lightfixture": (),
}
# pset keys whose numeric values are electrical RATINGS (voltage / current /
# power) — a candidate must share at least one such number with the request
# to be trusted, so a stray '42 circuits' or '10 kA' can't fake a match.
RATING_KEYS = ("voltage", "busrating", "mainsrating", "ratingkva", "kva",
               "primaryvoltage", "secondaryvoltage", "rating", "amperage",
               "wattage", "loadclassification")

KIND_FIX_HINT = {
    "panelboard": "load a panelboard family (e.g. 'M_Lighting and Appliance "
                  "Panelboard - 480V MCB - Surface') into the seed and place ONE "
                  "instance of the type you build with",
    "switchboard": "load a switchboard/switchgear family into the seed and place "
                   "ONE instance",
    "transformer": "load a dry-type transformer family into the seed and place "
                   "ONE instance (a free-standing floor unit is easiest)",
    "lightfixture": "load a light-fixture family into the seed and place ONE "
                    "instance",
}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def load_document(seed: str) -> Document:
    if os.path.exists(seed):
        return Document.from_file(seed)
    return Document.load(seed)          # research corpus name


# ---------------------------------------------------------------------------
# coverage scoring
# ---------------------------------------------------------------------------
def _pset_tokens(eq: dict) -> tuple[set, bool, bool]:
    want = set(_tokens(eq.get("typeName", "")))
    want |= _tokens(eq.get("description", ""))
    mcb = mlo = False
    for _pn, props in (eq.get("psets") or {}).items():
        for pk, pv in (props or {}).items():
            val = pv.get("value") if isinstance(pv, dict) else pv
            want |= _tokens(str(val))
            if str(pk).lower() == "mainstype":
                vl = str(val).lower()
                mcb |= "breaker" in vl
                mlo |= "lug" in vl
    tn = str(eq.get("typeName", "")).lower()
    mcb |= bool(re.search(r"\bmc?b\b", tn))
    mlo |= "mlo" in tn
    return want, mcb, mlo


def rating_tokens(eq: dict) -> set:
    """Numeric electrical-rating tokens (voltage / current / kVA / W) named by
    the request — the tokens a genuine match must share (e.g. 480, 400, 45)."""
    out: set = set()
    tn = str(eq.get("typeName", "")).lower()
    # numbers glued to an electrical unit in the type name: 400a, 45 kva, 208y, 480v
    for m in re.finditer(r"(\d{2,5})\s*(k?va|kw|w|a\b|amp|v\b|y/)", tn):
        out.add(m.group(1))
    for _pn, props in (eq.get("psets") or {}).items():
        for pk, pv in (props or {}).items():
            key = str(pk).lower()
            if not any(rk in key for rk in RATING_KEYS):
                continue
            val = pv.get("value") if isinstance(pv, dict) else pv
            for t in _tokens(str(val)):
                if t.isdigit():
                    out.add(t)
    return out


def score_equipment(eq: dict, sym: dict, keys: tuple, kind: str = "") -> float | None:
    """spec_to_rvt.discover_template scoring, reproduced per candidate."""
    name = f"{sym.get('family') or ''} {sym.get('symbol') or ''}"
    low = name.lower()
    if not any(k in low for k in keys):
        return None
    if any(x in low for x in KIND_EXCLUDE.get(kind, ())):
        return None
    want, mcb, mlo = _pset_tokens(eq)
    score = 10 + 3 * len(want & _tokens(name))
    if mcb and "mcb" in low:
        score += 4
    if mlo and "mlo" in low:
        score += 4
    if not (mcb or mlo) and "mcb" in low:
        score += 1
    score += _amperage(name) * 0.001
    return score


def audit_equipment(spec: dict, syms: list[dict]) -> list[dict]:
    """One row per DISTINCT (kind, typeName) request, listing the tags asking."""
    groups: dict[tuple, dict] = {}
    order: list[tuple] = []
    for eq in spec.get("equipment", []) or []:
        kind = str(eq.get("kind", "")).lower()
        tn = eq.get("typeName") or ""
        key = (kind, tn)
        if key not in groups:
            groups[key] = {"eq": eq, "tags": []}
            order.append(key)
        groups[key]["tags"].append(str(eq.get("name", "?")))
    rows = []
    for key in order:
        kind, tn = key
        eq = groups[key]["eq"]
        tags = groups[key]["tags"]
        item = tags[0] if len(tags) == 1 else f"{tags[0]}..{tags[-1]} (x{len(tags)})"
        if kind not in KIND_KEYWORDS:
            rows.append({"item": item, "tags": tags, "kind": kind, "want": tn,
                         "status": "NEEDS-FAMILY",
                         "fix": (f"kind {kind!r} has no native family kind in the writer "
                                 f"({', '.join(sorted(KIND_KEYWORDS))} are supported); it "
                                 "would be SKIPPED. Load a matching family into the seed "
                                 "(e.g. a Unistrut trapeze / generic model) and register "
                                 "the kind, or accept omission (DirectShape/generic-model "
                                 "placeholder).")})
            continue
        name = item
        cats = KIND_CATEGORIES.get(kind, (ELEC_EQUIP_CAT,))
        keys = KIND_KEYWORDS[kind]
        cands = []
        for s in syms:
            if s.get("category_id") not in cats:
                continue
            sc = score_equipment(eq, s, keys, kind)
            if sc is not None:
                cands.append((sc, s))
        cands.sort(key=lambda t: -t[0])
        want, mcb, mlo = _pset_tokens(eq)
        ratings = rating_tokens(eq)
        if not cands:
            row = {"item": name, "tags": tags, "kind": kind, "want": tn, "status": "MISSING",
                   "fix": KIND_FIX_HINT.get(kind, "load and place a matching family"),
                   "candidates_in_category": sum(1 for s in syms if s.get("category_id") in cats)}
        else:
            best_sc, best = cands[0]
            sym_tokens = _tokens(f"{best.get('family')} {best.get('symbol')}")
            overlap = sorted(want & sym_tokens)
            rating_hit = sorted(ratings & sym_tokens)
            status = "OK" if (rating_hit or (overlap and not ratings)) else "WEAK"
            fix = None
            if status == "WEAK":
                fix = ("best match shares no voltage/rating with the spec type "
                       f"(wanted {sorted(ratings) or sorted(want)}) — load the exact "
                       f"make/rating (add or rename a type like '{tn}') so schedules "
                       "read correctly")
            if best.get("placed_instances", 0) == 0:
                status = "OK-NO-INSTANCE" if status == "OK" else status
                fix = ((fix + "; " if fix else "") +
                       "the matched type has NO placed instance in the seed — place "
                       "one instance of it (the writer clones a placed specimen; "
                       "otherwise it falls back to another type's instance)")
            row = {"item": name, "tags": tags, "kind": kind, "want": tn, "status": status,
                   "seed_symbol_id": best["id"],
                   "seed": f"{best.get('family')} :: {best.get('symbol')}",
                   "score": round(best_sc, 3), "matched_tokens": overlap,
                   "placed_instances": best.get("placed_instances"),
                   "hosting_pattern": best.get("hosting_pattern"),
                   "runner_up": (f"{cands[1][1].get('family')} :: {cands[1][1].get('symbol')}"
                                 if len(cands) > 1 else None),
                   "fix": fix}
        rows.append(row)
    return rows


def audit_walls(spec: dict, wall_types: list[dict]) -> list[dict]:
    rows = []
    wanted: dict[str, dict] = {}
    default_t = ((spec.get("defaults") or {}).get("wallThickness"))
    for w in spec.get("walls", []) or []:
        t = str(w.get("type") or "(default)")
        thick = w.get("thickness", default_t)
        wanted.setdefault(t, {"count": 0, "thickness_m": thick})
        wanted[t]["count"] += 1
    for tname, info in wanted.items():
        want_tok = _tokens(tname)
        thick_ft = float(info["thickness_m"]) * FT_PER_M if info["thickness_m"] else None
        best, best_sc, best_why = None, -1e9, []
        for wt in wall_types:
            sc, why = 0.0, []
            ov = want_tok & _tokens(f"{wt.get('name') or ''} {wt.get('family') or ''}")
            if ov:
                sc += 3 * len(ov)
                why.append("tokens " + "/".join(sorted(ov)))
            if thick_ft and wt.get("thickness_ft"):
                rel = abs(wt["thickness_ft"] - thick_ft) / thick_ft
                if rel <= 0.10:
                    sc += 6; why.append(f"thickness {wt['thickness_ft']:.3f}ft ~ spec")
                elif rel <= 0.25:
                    sc += 2; why.append(f"thickness within 25% ({wt['thickness_ft']:.3f}ft)")
            if wt.get("walls_using"):
                sc += 0.5          # clonable
            if sc > best_sc:
                best, best_sc, best_why = wt, sc, why
        if best is None or best_sc <= 0.5:
            rows.append({"item": tname, "count": info["count"], "status": "MISSING",
                         "want_thickness_ft": round(thick_ft, 3) if thick_ft else None,
                         "fix": (f"create a wall type named '{tname}' in the seed "
                                 f"({info['thickness_m']*1000:.0f} mm) and PLACE one wall "
                                 "of it — the writer clones a placed wall of the type" )
                         if info["thickness_m"] else
                         f"create and place one wall of type '{tname}' in the seed"})
            continue
        status = "OK" if any("tokens" in w for w in best_why) else "THICKNESS-ONLY"
        fix = None
        if status == "THICKNESS-ONLY":
            fix = (f"no seed wall type is NAMED like '{tname}'; matched by thickness "
                   f"only. Rename '{best['name']}' or add a '{tname}' type so the "
                   "job's type name resolves exactly")
        if not best.get("walls_using"):
            status += "-NOT-PLACED"
            fix = ((fix + "; " if fix else "") +
                   f"'{best['name']}' has NO placed wall in the seed — draw one short "
                   "wall of it (the writer needs a placed specimen to clone)")
        rows.append({"item": tname, "count": info["count"], "status": status,
                     "seed_type_id": best["id"], "seed": best["name"],
                     "thickness_ft": best.get("thickness_ft"),
                     "want_thickness_ft": round(thick_ft, 3) if thick_ft else None,
                     "walls_placed": best.get("walls_using"),
                     "why": best_why, "fix": fix})
    return rows


def audit_levels(spec: dict, levels: list[dict]) -> list[dict]:
    rows = []
    by_name = {str(l.get("name") or "").strip().lower(): l for l in levels}
    ordered = sorted(levels, key=lambda l: (l.get("elevation_ft") or 0.0))
    spec_levels = spec.get("levels") or [{"id": "L1", "name": "Level 1", "elevation": 0}]
    for i, sl in enumerate(spec_levels):
        want = str(sl.get("name", "")).strip()
        hit = by_name.get(want.lower())
        elev_ft = float(sl.get("elevation", 0.0)) * FT_PER_M
        if hit:
            rows.append({"item": want, "status": "OK", "seed_level_id": hit["id"],
                         "seed": hit["name"], "seed_elevation_ft": hit["elevation_ft"]})
        elif ordered:
            fb = ordered[min(i, len(ordered) - 1)]
            rows.append({"item": want, "status": "FALLBACK",
                         "seed_level_id": fb["id"], "seed": fb["name"],
                         "seed_elevation_ft": fb["elevation_ft"],
                         "want_elevation_ft": round(elev_ft, 3),
                         "fix": (f"seed has no level named '{want}'; the writer will use "
                                 f"'{fb['name']}' (elevation-order fallback). Rename/add "
                                 f"a datum '{want}' at {sl.get('elevation', 0)} m to make "
                                 "levels match by name")})
        else:
            rows.append({"item": want, "status": "MISSING",
                         "fix": "seed has NO free levels — add at least one level datum"})
    return rows


def audit_doors(spec: dict, syms: list[dict]) -> list[dict]:
    doors = spec.get("doors") or []
    if not doors:
        return []
    cands = [s for s in syms if s.get("category_id") == DOOR_CAT]
    rows = []
    for d in doors:
        width_mm = int(round(float(d.get("width", 0.9)) * 1000))
        if not cands:
            rows.append({"item": d.get("id", "?"), "status": "MISSING",
                         "want_width_mm": width_mm,
                         "fix": ("seed has NO door family — load a door (e.g. a single "
                                 f"flush ~{width_mm} mm) and place one instance in a wall")})
            continue
        best, best_sc = None, -1
        for s in cands:
            nm = f"{s.get('family') or ''} {s.get('symbol') or ''}"
            sc = 1 + (2 if str(width_mm) in nm.replace(" ", "") else 0)
            sc += 0.5 if s.get("placed_instances") else 0
            if sc > best_sc:
                best, best_sc = s, sc
        rows.append({"item": d.get("id", "?"), "status": "OK" if best_sc >= 3 else "APPROX",
                     "want_width_mm": width_mm,
                     "seed": f"{best.get('family')} :: {best.get('symbol')}",
                     "seed_symbol_id": best["id"],
                     "placed_instances": best.get("placed_instances"),
                     "fix": (None if best_sc >= 3 else
                             f"no {width_mm} mm door type by name — add/rename a type "
                             f"({width_mm} mm wide) so the opening size is exact")})
    return rows


def audit_misc(spec: dict, invd: dict) -> list[dict]:
    rows = []
    if not invd["titleblocks"]:
        rows.append({"item": "titleblock", "status": "MISSING",
                     "fix": "no titleblock family in the seed — sheets cannot be created; "
                            "load your firm titleblock (e.g. E-series 30x42) and set it on "
                            "one sheet"})
    else:
        tb = invd["titleblocks"][0]
        rows.append({"item": "titleblock", "status": "OK",
                     "seed": f"{tb['family']} :: {tb['symbol']}",
                     "placed_instances": tb["placed_instances"]})
    ph = [p["name"] for p in invd["phases"]]
    rows.append({"item": "phases", "status": "OK" if ph else "MISSING", "seed": ph,
                 "fix": None if ph else "seed has no project phases"})
    rooms = spec.get("rooms") or []
    if rooms:
        rows.append({"item": f"rooms x{len(rooms)}", "status": "INFO",
                     "seed": None,
                     "fix": "rooms need bounding walls + a room tag family "
                            "(OST_RoomTags) for tags — verify a room tag is loaded"})
    return rows


# ---------------------------------------------------------------------------
# report assembly
# ---------------------------------------------------------------------------
def audit(seed: str, spec: dict | None) -> dict:
    """Inventory (+ coverage against ``spec``) of ``seed``, read under the
    seed's own release when it is a file on disk."""
    with ExitStack() as stack:
        note = enter_own_release(stack, seed) if os.path.exists(seed) else None
        report = _audit(seed, spec)
    if note:
        report["release_note"] = note
    return report


def _audit(seed: str, spec: dict | None) -> dict:
    doc = load_document(seed)
    invd = inv.inventory(doc)
    report = {"seed": seed, "inventory": invd}
    if spec is None:
        report["coverage"] = None
        return report
    cov = {
        "job": (spec.get("project") or {}).get("name"),
        "levels": audit_levels(spec, invd["levels"]),
        "wall_types": audit_walls(spec, invd["wall_types"]),
        "doors": audit_doors(spec, invd["symbols"]),
        "equipment": audit_equipment(spec, invd["symbols"]),
        "other": audit_misc(spec, invd),
    }
    # what the CURRENT writer would resolve today (verdict cross-check)
    try:
        tpl = _S2R.discover_template(doc, spec)
        cov["writer_would_use"] = {
            "levels": tpl.get("levels"),
            "wall_type": tpl.get("wall_type"),
            "wall_type_name": inv.type_name(doc, tpl["wall_type"]) if tpl.get("wall_type") else None,
            "equipment": {k: {"symbol_id": v[0],
                               "name": " :: ".join(x for x in
                                                  inv.family_and_symbol_names(doc, v[0]) if x)}
                          for k, v in (tpl.get("equipment") or {}).items()},
        }
    except Exception as e:                                   # pragma: no cover
        cov["writer_would_use"] = {"error": str(e)}
    allrows = cov["wall_types"] + cov["doors"] + cov["equipment"] + cov["other"] + cov["levels"]
    n_bad = sum(1 for r in allrows if r["status"] == "MISSING")
    n_warn = sum(1 for r in allrows
                 if r["status"] not in ("OK", "INFO", "MISSING"))
    cov["verdict"] = ("SEED READY" if n_bad == 0 and n_warn == 0 else
                      "SEED USABLE WITH GAPS" if n_bad == 0 else
                      "SEED NOT READY")
    cov["counts"] = {"missing_or_unsupported": n_bad, "warnings": n_warn,
                     "items": len(allrows)}
    report["coverage"] = cov
    return report


def _print(report: dict, full: bool = False) -> None:
    invd = report["inventory"]
    st = invd["stats"]
    print(f"=== SEED AUDIT: {report['seed']}")
    if report.get("release_note"):
        print(f"release: {report['release_note']}")
    print(f"levels ({st['levels']}): " + ", ".join(
        f"{l['name']} @ {l['elevation_ft']:.2f} ft" for l in invd["levels"]))
    print(f"wall types: {st['wall_types']} ({st['wall_types_named']} named)")
    for w in invd["wall_types"][: (999 if full else 8)]:
        t = f"{w['thickness_ft']*304.8:.0f} mm" if w["thickness_ft"] else "-"
        print(f"    {w['id']:>9d}  {str(w['name'])[:38]:38s} {w['kind']:8s} {t:>8s}  "
              f"walls placed: {w['walls_using']}")
    if not full and len(invd["wall_types"]) > 8:
        print(f"    ... {len(invd['wall_types']) - 8} more")
    print(f"family symbols: {st['symbols']} master types "
          f"({st['symbols_named']} named, categories: {st['category_sources']})")
    byc: dict[str, int] = {}
    for s in invd["symbols"]:
        k = s.get("category_label") or s.get("category") or "?"
        byc[k] = byc.get(k, 0) + 1
    top = ", ".join(f"{k} {v}" for k, v in sorted(byc.items(), key=lambda kv: -kv[1])[:8])
    print(f"    by category: {top}")
    if full:
        for s in invd["symbols"]:
            print(f"    {s['id']:>9d} [{s['category_label'] or s['category']}] "
                  f"{s['family']} :: {s['symbol']}  placed {s['placed_instances']} "
                  f"({s['hosting_pattern']})")
    print(f"titleblocks: {len(invd['titleblocks'])}  view templates: "
          f"{len(invd['view_templates'])}  phases: {[p['name'] for p in invd['phases']]}")
    cov = report.get("coverage")
    if not cov:
        print("\n(no --job given: inventory only)")
        return
    print(f"\n=== COVERAGE for job: {cov['job']}")
    for section in ("levels", "wall_types", "doors", "equipment", "other"):
        rows = cov[section]
        if not rows:
            continue
        print(f"-- {section}")
        for r in rows:
            got = r.get("seed")
            line = f"  [{r['status']:<15s}] {str(r.get('item'))[:34]:34s}"
            if got is not None:
                line += f" -> {got}"
            if r.get("placed_instances") is not None:
                line += f"  (placed {r['placed_instances']})"
            if r.get("walls_placed") is not None:
                line += f"  (walls placed {r['walls_placed']})"
            print(line)
            if r.get("fix"):
                print(f"      FIX: {r['fix']}")
    wu = cov.get("writer_would_use") or {}
    if wu.get("wall_type"):
        print(f"-- the writer would pick TODAY: wall type {wu['wall_type']} "
              f"'{wu.get('wall_type_name')}'; equipment "
              f"{ {k: v['name'] for k, v in (wu.get('equipment') or {}).items()} }")
    print(f"\nVERDICT: {cov['verdict']}  {cov['counts']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="audit a firm seed .rvt for authoring readiness")
    ap.add_argument("seed", help="path to the seed .rvt (or a research-corpus project name)")
    ap.add_argument("--job", default=None, help="job spec.json to check coverage against")
    ap.add_argument("--json", dest="json_out", default=None, help="write full report JSON here")
    ap.add_argument("--full", action="store_true", help="print every wall type / symbol")
    a = ap.parse_args(argv)
    spec = json.load(open(a.job)) if a.job else None
    report = audit(a.seed, spec)
    _print(report, full=a.full)
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump(report, fh, indent=1, default=str)
        print(f"\nreport JSON: {a.json_out}")
    cov = report.get("coverage")
    if cov and cov["verdict"] == "SEED NOT READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
