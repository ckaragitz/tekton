#!/usr/bin/env python3
"""validate_ifc.py -- schema validation + Revit-fidelity linter for an IFC file.

Usage:
    python validate_ifc.py <file.ifc> [--json out.json] [--quiet]

Prints a graded human summary to stdout (schema validity, entity histogram,
element inventory, geometry / placement / type / instancing / phantom /
spatial / pset / unit audits, and an overall Tier score with the top fixes)
and optionally writes the full machine-readable report as JSON.

Exit codes:
    0  analysis ran (regardless of the file's quality -- the report is the verdict)
    2  file could not be opened / is not IFC
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_lib  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", help="IFC (STEP) file to analyse")
    ap.add_argument("--json", dest="json_out", help="write the full report as JSON to this path")
    ap.add_argument("--quiet", action="store_true", help="suppress the human summary")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.file):
        print(f"error: no such file: {args.file}", file=sys.stderr)
        return 2
    try:
        rep = bridge_lib.analyze(args.file)
    except Exception as e:  # not IFC / parse failure
        print(f"error: could not analyse {args.file}: {e}", file=sys.stderr)
        return 2
    if not args.quiet:
        print(bridge_lib.human_summary(rep))
    if args.json_out:
        bridge_lib.dump_json(rep, args.json_out)
        print(f"\nfull report -> {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
