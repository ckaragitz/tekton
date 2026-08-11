#!/usr/bin/env python3
"""Build the #689 parametric-drive probe ladder.

Five .rfa files, identical but for ONE variable each (rvt.famgen.famdim.RUNGS).
The owner opens each in Revit, changes the family's `Width` parameter, and says
whether the geometry moved.  D0 is the control and MUST NOT flex.

    .venv/bin/python experiments/paramdrive/build_ladder.py --out out/probe

PROOF-ONLY.  Nothing here claims a family flexes; that is what the round decides.
"""
from __future__ import annotations
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import standalone as SA                    # noqa: E402
from rvt.famgen import factory as F, famdim as FD, param_drive as PD  # noqa: E402


def build(rung: str, out_dir: str) -> dict:
    """One rung: the SAME box family, driven at the same nominal size, differing
    only in the driver tables famdim writes."""
    SA.activate()
    # width_ft/depth_ft/height_ft: a plain rectangle, the one shape the #372
    # chain is defined for.  2 x 1 x 3 ft so a flex is unmistakable by eye.
    prod = F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0,
                                name=f"Drive Probe {rung}", standards=False)
    doc = prod.doc
    # the #372 chain (side planes + alignments + labelled dims) is already wired
    # by make_generic_model's rectangular path; find the planes for D3's pins
    planes = [e.elem_id for e in doc.elements if e.class_name == "RefPlane"]
    fixed = [(planes[0], (1.0, 0.0, 0.0))] if rung == "D3" or rung == "D4" else None
    rep = FD.apply_to_doc(doc, rung=rung, fixed_refs=fixed)
    path = os.path.join(out_dir, f"drive_{rung}.rfa")
    wrote = prod.write(path, validate=True, provenance=True)
    fam = wrote["validate"]["family_mode"]
    rep.update({"file": os.path.basename(path),
                "validator": f"{fam['verdict']} {fam['n_errors']} errors",
                "provenance_ok": wrote["provenance"]["ok"],
                "elements": wrote["family"]["elements"]})
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/probe")
    ns = ap.parse_args()
    os.makedirs(ns.out, exist_ok=True)
    rows = [build(r, ns.out) for r in FD.RUNGS]
    with open(os.path.join(ns.out, "LADDER.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    for r in rows:
        print(f"{r['rung']}  {r['file']:<16} {r['validator']:<18} "
              f"driven={r['driven_segs']} paramExpr={r['param_exprs']} "
              f"fixedRef={r['fixed_refs']}  <- {r['adds'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
