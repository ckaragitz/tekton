#!/usr/bin/env python
"""Validator regression for the loaded-content rule (instbug-fix stream).

Runs rvt.validate over EVERY viewer-certified file still on disk (docs/
coverage/viewer-certified.json 'certified') plus the six samples, asserting
the new loaded-content checks introduce NO new ERROR on any viewer-PASSED
file; and over the known audit-FAILED product-path files, recording which
now flag (detection evidence, not a requirement).
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.validate import validate_file          # noqa: E402

SAMPLES = ["rstbasicsampleproject", "rstadvancedsampleproject",
           "racbasicsampleproject", "racadvancedsampleproject",
           "rmebasicsampleproject", "dach-sample-project"]

FAILED_PRODUCT_PATH = [
    "experiments/frontdoor/demo-250v/prompt_room.rvt",
    "experiments/ifc_room/electrical_room_2500a.rvt",
    "experiments/ifc_room/stage_W_loaded_walls.rvt",
    "experiments/ifc_room/render_probes/R_inst_box.rvt",
    "experiments/ifc_room/render_probes/F_lp4.rvt",
    "experiments/ifc_room/render_probes/F_msb.rvt",
]

#: ledger entries whose recorded 'PASS' the campaign itself retracted as a
#: NON-TEST of the layer the loaded-content rule checks — flagged by the
#: rule and classified here, never silently excluded.
KNOWN_NONTEST = {
    "experiments/ifc_room/stage_L8_lp4.rvt": (
        "its viewer 'PASS' was the 'Design is empty' extractor short-circuit "
        "(docs/inbox/render-instances.md §1; verdict #25 RETRACTION in "
        "docs/inbox/genesis-audit.md; the discipline stream's control-source "
        "warning) — the loaded-family layer was NEVER audited in it; the file "
        "IS unsorted (8 chained famgen loads), so the E2 error states a true "
        "fact about an unaudited file, not a false positive on an audited pass"),
}


def reclassify(json_path):
    """Re-apply the KNOWN_NONTEST classification to an existing regression
    JSON (measurement unchanged -- only the false-positive bookkeeping)."""
    out = json.load(open(json_path))
    fps, nontest = [], []
    for rel, rec in out.get("certified", {}).items():
        if rec.get("loaded_content_errors"):
            if rel in KNOWN_NONTEST:
                rec["known_nontest"] = KNOWN_NONTEST[rel]
                nontest.append(rel)
            else:
                fps.append(rel)
        rec.pop("known_nontest", None) if rel not in KNOWN_NONTEST else None
    out["new_false_positives"] = fps
    out["known_nontest_flags"] = nontest
    out["ok"] = not fps
    with open(json_path, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"reclassified: false positives {fps}; known non-test flags {nontest}; "
          f"ok={out['ok']}")
    return 0 if out["ok"] else 1


def main():
    if "--reclassify" in sys.argv:
        return reclassify(os.path.join(HERE, "validator_regression.json"))
    cov = json.load(open(os.path.join(ROOT, "docs", "coverage",
                                      "viewer-certified.json")))
    certified = [e["file"] for e in cov["certified"] if isinstance(e, dict)]
    certified += [f"samples/{s}.rvt" for s in SAMPLES]
    out = {"certified": {}, "failed_product_path": {}, "new_false_positives": []}
    t0 = time.time()
    for rel in certified:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            out["certified"][rel] = {"status": "NOT-ON-DISK"}
            continue
        try:
            r = validate_file(p)
        except Exception as e:                                  # noqa: BLE001
            out["certified"][rel] = {"status": "VALIDATOR-CRASH",
                                     "error": f"{type(e).__name__}: {e}"}
            out["new_false_positives"].append(rel)
            continue
        lc_errors = [f"{f.where}: {f.message}"[:200] for f in r.errors
                     if "loaded-content" in f.where]
        rec = {"errors": len(r.errors), "warnings": len(r.warnings),
               "loaded_content_errors": lc_errors}
        if r.errors:
            rec["first_errors"] = [f"[{f.layer}] {f.where}: {f.message}"[:200]
                                   for f in r.errors[:3]]
        out["certified"][rel] = rec
        if lc_errors:
            if rel in KNOWN_NONTEST:
                rec["known_nontest"] = KNOWN_NONTEST[rel]
                out.setdefault("known_nontest_flags", []).append(rel)
            else:
                out["new_false_positives"].append(rel)
    for rel in FAILED_PRODUCT_PATH:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            out["failed_product_path"][rel] = {"status": "NOT-ON-DISK"}
            continue
        r = validate_file(p)
        out["failed_product_path"][rel] = {
            "errors": len(r.errors),
            "loaded_content_errors": [f"{f.where}: {f.message}"[:160]
                                      for f in r.errors
                                      if "loaded-content" in f.where],
            "now_detected": any("loaded-content" in f.where for f in r.errors)}
    out["seconds"] = round(time.time() - t0, 1)
    out["ok"] = not out["new_false_positives"]
    rp = os.path.join(HERE, "validator_regression.json")
    with open(rp, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    n_files = sum(1 for v in out["certified"].values() if v.get("status") != "NOT-ON-DISK")
    n_miss = sum(1 for v in out["certified"].values() if v.get("status") == "NOT-ON-DISK")
    n_det = sum(1 for v in out["failed_product_path"].values()
                if v.get("now_detected"))
    print(f"certified checked: {n_files} (+{n_miss} not on disk); "
          f"new false positives: {len(out['new_false_positives'])} "
          f"{out['new_false_positives'][:4]}; known non-test flags: "
          f"{out.get('known_nontest_flags', [])}")
    print(f"failed product-path files now flagged by the rule: {n_det}/"
          f"{len([v for v in out['failed_product_path'].values() if v.get('status') != 'NOT-ON-DISK'])}")
    print(f"ok: {out['ok']}  ({out['seconds']}s) -> {rp}")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
