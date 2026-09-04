#!/usr/bin/env python
"""self_battery.py -- build EVERY product the engine can make and run EVERY
in-session instrument on each, fixing before shipping (steer #765).

Owner: "you should be able to test every possible item possible and debug and
make it right."  This is that, minus the one thing no sandbox contains
(Revit itself, hard rule 4): every constructor x variant is BUILT, written,
re-decoded, validated, and checked for internal contradictions and corpus
divergence -- with no user in the loop.  A FAIL here is a bug to fix before
anything ships; a PASS is necessary, never sufficient.

Instruments per artefact:
  build       the constructor itself (an exception is a FAIL, hard rule 1)
  write       the standalone .rfa emitter
  validate    tools/rvt_validate.py (0 errors required)
  law         famgen.constraint_law.check_file (graph coherence)
  corpus      famgen.conformance against samples/rft (skips when absent)
  reread      full re-decode of every element (round-trip)

USAGE:  .venv/bin/python tools/self_battery.py [--out out/battery] [--only k1,k2]
Exit 0 = every artefact passed every applicable instrument.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

IN = 1.0 / 12.0


def _catalog() -> Dict[str, Callable[[], Any]]:
    """Every product the engine claims to make, one thunk each.  New
    constructors get a row HERE or the battery is lying about 'every'."""
    from rvt.famgen import factory as F
    from rvt.famgen import revolve as RV

    def _multi(name, parts):
        return lambda: F.make_generic_model(parts=parts, name=name,
                                            category="generic_model",
                                            source="self battery")

    jobs: Dict[str, Callable[[], Any]] = {
        "panelboard": lambda: F.make_panelboard(name="B_panel"),
        "panelboard_types": lambda: F.make_panelboard(name="B_panelT",
                                                      types=["225A", "400A"]),
        "transformer": lambda: F.make_transformer(name="B_xfmr"),
        "luminaire_troffer_2x4": lambda: F.make_luminaire(
            kind="recessed-troffer", size="2x4", name="B_trof24"),
        "luminaire_troffer_2x2": lambda: F.make_luminaire(
            kind="recessed-troffer", size="2x2", name="B_trof22"),
        "luminaire_downlight": lambda: F.make_luminaire(
            kind="recessed-downlight", name="B_down"),
        "device_receptacle": lambda: F.make_device(name="B_recep"),
        # 600 A is the top of the sizing table; 2500 A (a real switchboard)
        # is an honest refusal today and its support is a filed gap.
        "panelboard_600A": lambda: F.make_panelboard(name="B_600", mains_a=600),
        # -- every generic part shape, one artefact each -------------------
        "shape_box": _multi("B_box", [
            {"name": "b", "shape": "box", "width_ft": 1, "depth_ft": 1,
             "height_ft": 1}]),
        "shape_polygon": _multi("B_poly", [
            {"name": "p", "shape": "polygon", "height_ft": 1,
             "vertices": [(0, 0), (1, 0), (1.2, 0.6), (0.5, 1), (-0.2, 0.6)]}]),
        "shape_cylinder": _multi("B_cyl", [
            {"name": "c", "shape": "cylinder", "radius_ft": 0.5,
             "height_ft": 1}]),
        "shape_cylinder_x": _multi("B_cylx", [
            {"name": "cx", "shape": "cylinder_x", "radius_ft": 0.4,
             "length_ft": 2.0, "center": (0, 0), "base_z_ft": 0}]),
        "shape_cylinder_y": _multi("B_cyly", [
            {"name": "cy", "shape": "cylinder_y", "radius_ft": 0.4,
             "length_ft": 2.0, "center": (0, 0), "base_z_ft": 0}]),
        "shape_sphere_stack": _multi("B_sph", RV.sphere_parts(0.5)),
        "shape_dome_stack": _multi("B_dome", RV.dome_parts(0.5)),
        "shape_cone_stack": _multi("B_cone", RV.cone_parts(0.5, 1.0)),
        "shape_mixed_assembly": _multi("B_mixed", [
            {"name": "base", "shape": "box", "width_ft": 2, "depth_ft": 2,
             "height_ft": 0.2},
            {"name": "mast", "shape": "cylinder", "radius_ft": 0.1,
             "height_ft": 3, "base_z_ft": 0.2},
            {"name": "arm", "shape": "cylinder_y", "radius_ft": 0.08,
             "length_ft": 1.5, "center": (0, 0.75), "base_z_ft": 3.0},
        ]),
    }
    # constructors that may not exist on this trunk yet: probe and include
    for opt, key, mk in (
        ("make_archetype", "archetype_cable_tray",
         lambda F=F: F.make_archetype(product="cable_tray")),
    ):
        if hasattr(F, opt):
            jobs[key] = mk
    return jobs


def _run_one(key: str, thunk: Callable[[], Any], out_dir: str,
             oracle_inv: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from rvt.famgen import conformance as CO
    from rvt.famgen import constraint_law as CL

    row: Dict[str, Any] = {"artefact": key, "steps": {}, "ok": False}
    t0 = time.time()
    path = os.path.join(out_dir, f"{key}.rfa")

    def _fail(step: str, exc: BaseException) -> Dict[str, Any]:
        row["steps"][step] = f"FAIL {type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc()[-1200:]
        row["seconds"] = round(time.time() - t0, 2)
        return row

    try:
        prod = thunk()
    except BaseException as e:                                    # noqa: BLE001
        return _fail("build", e)
    row["steps"]["build"] = "ok"
    try:
        prod.write(path)
    except BaseException as e:                                    # noqa: BLE001
        return _fail("write", e)
    row["steps"]["write"] = f"ok ({os.path.getsize(path)} bytes)"

    # validator, in-process (0 errors required).  The REAL validator lives at
    # rvt.validate (tools/rvt_validate.py is a thin CLI shim with no Validator
    # class) -- the first cut imported the shim, got AttributeError, and
    # counted the dead instrument as SKIP-therefore-pass: a family with
    # validator errors sailed through the battery (#770 review, measured).
    # An instrument crash is a FAIL here, never an invisible skip.
    try:
        from rvt.validate import validate_file
        rep = validate_file(path, family=True)
        errs = [f for f in rep.findings if f.severity == "error"]
        row["steps"]["validate"] = ("ok" if not errs
                                    else f"FAIL {len(errs)} error(s): "
                                         + "; ".join(f.message for f in errs[:3]))
    except BaseException as e:                                    # noqa: BLE001
        row["steps"]["validate"] = f"FAIL instrument ({type(e).__name__}: {e})"

    try:
        fs = CL.check_file(path)
        bad = [f for f in fs if f["severity"] == "error"]
        row["steps"]["law"] = ("ok" if not bad
                               else "FAIL " + bad[0]["message"][:140])
    except BaseException as e:                                    # noqa: BLE001
        return _fail("law", e)

    if oracle_inv:
        try:
            findings = CO.check_doc(prod.doc, oracle_inv)
            qs = [f for f in findings if f["severity"] == "question"]
            row["steps"]["corpus"] = ("ok" if not qs else
                                      f"QUESTION x{len(qs)}: " + qs[0]["message"][:120])
        except BaseException as e:                                # noqa: BLE001
            row["steps"]["corpus"] = f"SKIP ({type(e).__name__})"
    else:
        row["steps"]["corpus"] = "SKIP (no samples/rft corpus)"

    # full re-decode round trip
    try:
        from rvt.families import FamilyIndex
        from rvt.objects import ObjectDecoder
        idx = FamilyIndex(path)
        dec = ObjectDecoder(idx.schema)
        n = bad = 0
        for seq, m in idx.unit_records(0).items():
            for eid, r in m.items():
                n += 1
                try:
                    dec.decode_record(r.class_id, r.payload)
                except BaseException:                             # noqa: BLE001
                    bad += 1
        row["steps"]["reread"] = (f"ok ({n} records)" if not bad
                                  else f"FAIL {bad}/{n} records undecodable")
    except BaseException as e:                                    # noqa: BLE001
        return _fail("reread", e)

    row["ok"] = not any(str(v).startswith(("FAIL", "QUESTION"))
                        for v in row["steps"].values())
    row["seconds"] = round(time.time() - t0, 2)
    return row


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "battery"))
    ap.add_argument("--only", default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)

    oracle_inv = None
    rft = os.path.join(ROOT, "samples", "rft")
    if os.path.isdir(rft):
        from rvt.famgen import conformance as CO
        # the FULL corpus, never a subsample: at limit=12 the oracle derived
        # three CONSTANT "laws" (m_referenceType, m_instanceParam,
        # m_isWorkPlaneBased) that the 108-template corpus dissolves -- the
        # hosted templates and duct fittings carrying the other value simply
        # sorted later alphabetically.  6 seconds buys laws that are true.
        oracle_inv = CO.mine(rft).invariants()

    jobs = _catalog()
    if a.only:
        keep = {k.strip() for k in a.only.split(",")}
        jobs = {k: v for k, v in jobs.items() if k in keep}
    rows = []
    for key, thunk in jobs.items():
        row = _run_one(key, thunk, a.out, oracle_inv)
        mark = "PASS" if row["ok"] else "FAIL"
        worst = next((f"{s}: {v}" for s, v in row["steps"].items()
                      if str(v).startswith(("FAIL", "QUESTION"))), "")
        print(f"[{mark}] {key:28} {row['seconds']:6.2f}s  {worst[:110]}")
        rows.append(row)
    report = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "passed": sum(r["ok"] for r in rows), "total": len(rows),
              "rows": rows}
    rp = os.path.join(a.out, "battery.json")
    with open(rp, "w") as fh:
        json.dump(report, fh, indent=1)
    print(f"\n{report['passed']}/{report['total']} passed -> {rp}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
