#!/usr/bin/env python3
"""rvt_edit.py — edit an EXISTING .rvt from the command line (the MANIPULATE
verb): inspect, delete, modify parameters, move, retype. Every write is
followed by the structural self-verification; run tools/rvt_validate.py on
the result for the full pre-flight.

    rvt_edit.py FILE info                              # inventory summary
    rvt_edit.py FILE deps   --id 1466502                # dependents report
    rvt_edit.py FILE delete --id 1466502 [--cascade] -o out.rvt
    rvt_edit.py FILE rename-panel --id 742670 --name "HG4" -o out.rvt
    rvt_edit.py FILE set-mark --id 1466502 --mark "P-14" -o out.rvt
    rvt_edit.py FILE set-level --id 311 --elevation-ft 12.0 -o out.rvt
    rvt_edit.py FILE move   --id 1466502 --to 10 4 0 [--rotation-deg 90] -o out.rvt
    rvt_edit.py FILE retype --id 1466502 --symbol 619617 -o out.rvt

The file is opened, planned, re-emitted and verified under ITS OWN Revit
release (a 2025/2024 project keeps its release's framing, id width and
schema; the output declares the input's release) -- issue #70.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "src"))     # plugin layout

from rvt.mutate import Document  # noqa: E402
from rvt import manipulate as M  # noqa: E402
from rvt import inventory as INV  # noqa: E402
from rvt.frontdoor.release_ctx import enter_host_release  # noqa: E402


def _report(rep, out):
    d = rep if isinstance(rep, dict) else getattr(rep, "__dict__", {"result": str(rep)})
    print(json.dumps({k: (str(v) if not isinstance(v, (int, float, str, bool, list, dict, type(None))) else v)
                      for k, v in d.items()}, indent=2, default=str)[:4000])
    if out:
        v = M.verify_manipulated(out)
        print("\nstructural verify:", json.dumps({k: v.get(k) for k in
              ('crc_failures', 'ecc_mismatches', 'walker_errors', 'stamps_ok',
               'elemtable_count', 'header_count') if k in v}, default=str))
        print(f"written: {out} ({os.path.getsize(out):,} bytes)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="edit an existing .rvt")
    ap.add_argument("file", help="input .rvt")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="inventory summary (levels, wall types, symbols)")
    p = sub.add_parser("deps", help="dependents report for an element"); p.add_argument("--id", type=int, required=True)
    p = sub.add_parser("delete", help="delete an element"); p.add_argument("--id", type=int, required=True)
    p.add_argument("--cascade", action="store_true"); p.add_argument("-o", "--out", required=True)
    p = sub.add_parser("rename-panel"); p.add_argument("--id", type=int, required=True)
    p.add_argument("--name", required=True); p.add_argument("-o", "--out", required=True)
    p = sub.add_parser("set-mark"); p.add_argument("--id", type=int, required=True)
    p.add_argument("--mark", required=True); p.add_argument("-o", "--out", required=True)
    p = sub.add_parser("set-level"); p.add_argument("--id", type=int, required=True)
    p.add_argument("--elevation-ft", type=float, required=True); p.add_argument("-o", "--out", required=True)
    p = sub.add_parser("move"); p.add_argument("--id", type=int, required=True)
    p.add_argument("--to", type=float, nargs=3, metavar=("X", "Y", "Z"), required=True)
    p.add_argument("--rotation-deg", type=float, default=None); p.add_argument("-o", "--out", required=True)
    p = sub.add_parser("retype"); p.add_argument("--id", type=int, required=True)
    p.add_argument("--symbol", type=int, required=True); p.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)

    # every verb runs under the INPUT file's own release: a Revit 2025/2024
    # project is opened, planned, re-emitted and verified with its release's
    # framing + codecs (issue #70); a native file enters no context; a release
    # we cannot author into is reported here and fails honestly downstream
    if not os.path.isfile(a.file):
        ap.error(f"input .rvt not found: {a.file}")
    with contextlib.ExitStack() as stack:
        note = enter_host_release(stack, a.file)
        if note:
            print(f"[rvt_edit] warning: {note}", file=sys.stderr)
        return _run(a)


def _run(a: argparse.Namespace) -> int:
    doc = Document.from_file(a.file)

    if a.cmd == "info":
        inv = INV.inventory(doc)
        print(json.dumps({k: (v if k == 'stats' else (v[:12] if isinstance(v, list) else v))
                          for k, v in inv.items()}, indent=2, default=str))
        return 0
    if a.cmd == "deps":
        print(json.dumps(M.dependency_report(doc, a.id), indent=2, default=str)[:6000])
        return 0

    if a.cmd == "delete":
        plan = M.delete_element(doc, a.id, cascade=a.cascade)
        rep = M.commit_plans(a.file, a.out, [plan])
    elif a.cmd == "rename-panel":
        rep = M.commit_plans(a.file, a.out, [M.rename_panel(doc, a.id, a.name)])
    elif a.cmd == "set-mark":
        rep = M.commit_plans(a.file, a.out, [M.set_mark(doc, a.id, a.mark)])
    elif a.cmd == "set-level":
        rep = M.commit_plans(a.file, a.out, [M.set_level_elevation(doc, a.id, a.elevation_ft)])
    elif a.cmd == "move":
        rot = math.radians(a.rotation_deg) if a.rotation_deg is not None else None
        rep = M.commit_plans(a.file, a.out, [M.move_instance(doc, a.id, tuple(a.to), rotation=rot)])
    else:                                                   # retype (argparse guarantees the verb)
        rep = M.commit_plans(a.file, a.out, [M.retype_instance(doc, a.id, a.symbol)])
    _report(rep, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
