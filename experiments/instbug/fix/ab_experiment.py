#!/usr/bin/env python
"""A/B experiment for the product-path bug (instbug-fix stream).

A (PASS shape, = WF_nofix recipe): certified walls_only + ONE loaded box
family (rvt.famgen.loader, place=False).  The only commit ran BEFORE the
splice existed.

B (FAIL shape, = F_* recipe): ZA_deep + the SAME box family loaded first,
THEN the same 4 walls committed (tools/ifc_intent.stage_walls) -- a
commit_new_elements over a stream that already carries our spliced unit.

Final content of A and B is the same (genesis lineage + 4 walls + box
family); every structural difference between them is caused purely by the
operation ORDER and is a candidate for the bug.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "src")
TOOLS = os.path.join(ROOT, "tools")
for p in (SRC, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import ifc_intent as T                      # noqa: E402
from rvt.ifc import intent as I             # noqa: E402

BASE_ZA = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a", "ZA_deep.rvt")
WALLS_ONLY = os.path.join(ROOT, "experiments", "ifc_room", "electrical_room_2500a_walls_only.rvt")
SPECIMEN_SRC = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")
IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
OUT = HERE


def _wm(path):
    from rvt.mutate import Document
    from rvt.container import open_rvt
    from rvt.elemtable import parse_elemtable
    with open_rvt(path) as f:
        et = parse_elemtable(f.inflate("Global/ElemTable", 0))
    return int(et.footer.last_id)


def main():
    sys.path.insert(0, TOOLS)
    import importlib.util
    spec = importlib.util.spec_from_file_location("render_probes_mod",
                                                  os.path.join(TOOLS, "render_probes.py"))
    RP = importlib.util.module_from_spec(spec)
    sys.modules["render_probes_mod"] = RP
    spec.loader.exec_module(RP)

    rep = {}
    model = I.resolve_intent(IFC)
    specimens = T.SpecimenSet(SPECIMEN_SRC)

    # ---- A: walls_only + box load (WF_nofix shape) -------------------------
    a_path = os.path.join(OUT, "AB_A_wallsfirst.rvt")
    wm_a = _wm(WALLS_ONLY)
    box_a = RP.make_bare_box_product(start_id=wm_a + 1)
    res_a = RP.load_room_family(WALLS_ONLY, a_path, box_a)
    rep["A"] = {"out": a_path, "ok": bool(res_a.ok), "stop": res_a.stop_reason,
                "plan": {k: getattr(res_a.plan, k) for k in
                         ("guid", "host_family_id", "surrogate_id", "symbol_id",
                          "symbol_surrogate_id", "instance_id")},
                "twins": dict(res_a.plan.twin_of)}

    # ---- B: ZA_deep + box load, then walls (F shape) -----------------------
    tmp = os.path.join(OUT, "AB_B_step1_loaded.rvt")
    wm_b = _wm(BASE_ZA)
    box_b = RP.make_bare_box_product(start_id=wm_b + 1)
    res_b = RP.load_room_family(BASE_ZA, tmp, box_b)
    b_path = os.path.join(OUT, "AB_B_loadfirst.rvt")
    wrec, wout = T.stage_walls(model, tmp, b_path, specimens, wall_mode="min")
    rep["B"] = {"out": b_path, "load_ok": bool(res_b.ok),
                "plan": {k: getattr(res_b.plan, k) for k in
                         ("guid", "host_family_id", "surrogate_id", "symbol_id",
                          "symbol_surrogate_id", "instance_id")},
                "twins": dict(res_b.plan.twin_of),
                "walls_ok": bool(wrec.get("ok")),
                "wall_ids": [w.get("elem_id") for w in wrec.get("walls") or []],
                "walls_error": wrec.get("error") or wrec.get("blocker")}

    with open(os.path.join(OUT, "ab_build.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
