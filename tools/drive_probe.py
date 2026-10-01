#!/usr/bin/env python3
"""drive_probe.py -- stage the single-variable IN-PLANE drive probe pair (#787).

    python tools/drive_probe.py OUT_DIR [--release 2026|2025|2024 ...]

Builds, per release, two one-box generic-model families with labelled Width
and Depth dimensions driving the box's sketch, rewritten to the Revit-born law
(``rvt.famgen.drive_law``):

  DriveProbe_P_<rel>.rfa  -- the full born law, WITH the sketch regen edge
  DriveProbe_C_<rel>.rfa  -- identical except the VarSketch header's
                             m_regenOnly keeps the Level only (the control)

The desktop check is one question per file: in Family Types, change Width
from 2' 0" to 3' 0" and press Apply -- does the box get wider?  P flexing and
C not = the regen edge is the cause; both = another law item; neither = the
chain is still short (Case B and the remaining items are next).  Writes
PROBE.json next to the files with the exact difference.  Nothing here claims
a family flexes (hard rule 4).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import drive_law as DL          # noqa: E402
from rvt.famgen import factory as F             # noqa: E402
from rvt.frontdoor import release_ctx as RC     # noqa: E402

BOX = {"shape": "box", "name": "probe body", "width_ft": 2.0, "depth_ft": 1.0,
       "height_ft": 1.5}


def _one(out_dir: str, rel: int, variant: str) -> dict:
    prod = F.make_generic_model(parts=[dict(BOX)], name="DriveProbe",
                                drive=True)
    law = DL.apply_born_inplane_law(prod.doc, regen_edge=(variant == "P"))
    path = os.path.join(out_dir, f"DriveProbe_{variant}_{rel}.rfa")
    res = prod.write(path)
    return {"file": os.path.basename(path), "ok": bool(res.get("ok", True)),
            "validate": (res.get("validate") or {}).get("family_mode", {}).get("verdict"),
            "errors": (res.get("validate") or {}).get("family_mode", {}).get("n_errors"),
            "law": {k: v for k, v in law.items() if k != "sketches"},
            "sketches": {str(k): v for k, v in law["sketches"].items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out_dir")
    ap.add_argument("--release", type=int, action="append", default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    rels = a.release or [RC.native_release()]
    report = {"issue": 787, "variable": "VarSketch header m_regenOnly includes the "
              "reference planes its lines are locked to (P) vs the Level only (C)",
              "files": []}
    for rel in rels:
        base = None if rel == RC.native_release() else RC._bundled_base_of(rel)
        if rel != RC.native_release() and base is None:
            print(f"no bundled base for Revit {rel}", file=sys.stderr)
            return 2
        for variant in ("P", "C"):
            if base is None:
                report["files"].append(_one(a.out_dir, rel, variant))
            else:
                with RC.release_build_context(base):
                    report["files"].append(_one(a.out_dir, rel, variant))
    with open(os.path.join(a.out_dir, "PROBE.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    for f in report["files"]:
        print(f"{f['file']}: {f['validate']} errors={f['errors']} "
              f"locks={len(f['law']['locks'])} backedges_cleared={f['law']['constr_info_cleared']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
