#!/usr/bin/env python3
"""Render NEC-style panelboard schedules + load calcs from a job spec.

    tools/panel_schedule.py --spec job.json --out out_dir

Writes ``<panel>.html`` + ``<panel>.csv`` per panel, a combined
print-ready ``schedules.html``, and ``summary.json`` (the machine-readable
result the tekton-ifc generators consume: circuit ratings/poles for
Document.add_circuit, PanelScheduleCalc / TransformerCalc psets).

This is a DESIGN AID: every value is reviewed by the licensed engineer of
record. See docs/electrical-calcs.md for the formulas and their limits.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from rvt.electrical import job as ejob   # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True, help="electrical job JSON")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    summ = ejob.run(a.spec, a.out)
    if not a.quiet:
        print(f"wrote schedules -> {a.out}")
        for name, p in summ["panels"].items():
            flag = "  !!" if p["warnings"] else ""
            print(f"  panel {name:8s} {p['systemLabel']:22s} "
                  f"connected {p['connectedKVA']:7.2f} kVA  "
                  f"demand {p['demandKVA']:7.2f} kVA = "
                  f"{p['demandAmps']:6.1f} A / bus {p['busRatingA']:g} A  "
                  f"imbalance {p['phaseImbalancePct']:5.1f}%{flag}")
            for w in p["warnings"]:
                print(f"      ! {w}")
        for name, t in summ["transformers"].items():
            lp = (f"{t['loadingPct']:.0f}%" if t['loadingPct'] is not None
                  else "n/a")
            print(f"  xfmr  {name:8s} {t['kva']:>5g} kVA  primary "
                  f"{t['primaryFLA']:5.1f} A -> x125 {t['primaryFLAx125']:5.1f} A "
                  f"-> OCPD {t['primaryOCPD']} A  secondary {t['secondaryFLA']:.1f} A "
                  f"-> {t['secondaryOCPD']} A  loading {lp}")
            for w in t["warnings"]:
                print(f"      ! {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
