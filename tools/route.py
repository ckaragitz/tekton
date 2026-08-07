#!/usr/bin/env python3
"""route.py -- ANY PERMUTATION: {prompt, ifc, rvt, rfa, spec} in -> {rvt, rfa, ifc} out.

    route.py run --output rvt --prompt "an electrical room 30x20 ft ..."
    route.py run --output rvt --prompt "..." --via ifc          # prompt->IFC->RVT chain
    route.py run --output rvt --ifc design.ifc
    route.py run --output rvt --ifc design.ifc --rvt mine.rvt   # merge onto your file
    route.py run --output rvt --rvt in.rvt --prompt "delete DP-1 with cascade"
    route.py run --output rvt --rfa '{"kind": "downlight"}'     # famspec -> .rfa -> loaded .rvt
    route.py run --output ifc --spec room-spec.json
    route.py run --output rfa --prompt "a 75 kVA transformer"

    route.py matrix [--json]        # the live permutation truth table
    route.py explain --output rvt --inputs prompt,ifc           # one cell

The router (rvt.frontdoor.router) looks the request up in the PERMUTATION
MATRIX (rvt.frontdoor.matrix), composes the EXISTING certified stages, and
DELIVERS: the output file + every intermediate artifact + a route manifest
(route.json / ROUTE.md) with stamps, caveats and the evidence the matrix
cites.  Unsupported cells come back as ONE clear line naming the closest
supported route -- never a traceback.

The three classic routes stay available verbatim on tools/frontdoor.py
(author --prompt / --ifc / --rvt); this tool is the superset.

Exit codes: 0 = the route completed and delivered; 2 = usage error;
3 = the route ran but did not complete; 4 = unsupported cell (the clear
line was printed); 1 = unexpected error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "lib", "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

EX_OK, EX_ERR, EX_USAGE, EX_INCOMPLETE, EX_UNSUPPORTED = 0, 1, 2, 3, 4


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="route",
        description="THE PERMUTATION ROUTER: any subset of {prompt, ifc, rvt, "
                    "rfa, spec} in -> {rvt, rfa, ifc} out, composed from the "
                    "certified stages, honestly labelled.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="execute one route")
    pr.add_argument("--output", required=True, choices=("rvt", "rfa", "ifc"),
                    help="what to produce")
    ins = pr.add_argument_group("inputs (any combination)")
    ins.add_argument("--prompt", default=None, metavar="TEXT",
                     help="natural language (authoring prompt, or the edit "
                          "sentence when combined with --rvt)")
    ins.add_argument("--ifc", default=None, metavar="FILE.ifc")
    ins.add_argument("--rvt", default=None, metavar="FILE.rvt",
                     help="an existing project (edit target / merge base / "
                          "load host / seed)")
    ins.add_argument("--rfa", default=None, metavar="FAMSPEC|FILE",
                     help="a famspec JSON ({'kind': 'downlight', ...}, inline "
                          "or a .json path); a bare .rfa path is answered "
                          "with the honest matrix row")
    ins.add_argument("--spec", default=None, metavar="SPEC.json",
                     help="a building/room spec (spec/building.schema.json)")
    outg = pr.add_argument_group("output & policy (passed through to the stages)")
    outg.add_argument("--out", "-o", default=None, metavar="DIR",
                      help="output directory (default: experiments/routes/"
                           "<inputs>-to-<output>-<stamp>)")
    outg.add_argument("--stem", default=None)
    outg.add_argument("--via", default=None, choices=("ifc", "family"),
                      help="chain selector: 'ifc' = prompt->IFC->RVT; "
                           "'family' = product-IFC->rfa->loaded rvt")
    outg.add_argument("--strict", action="store_true",
                      help="walls+families open bug -> two coordinated files")
    outg.add_argument("--base", default=None, metavar="FILE.rvt",
                      help="build base override (Autodesk samples refused)")
    outg.add_argument("--target-version", type=int, default=None)
    outg.add_argument("--stages", default=None,
                      help="build stage subset FLWECV (build cells only)")
    outg.add_argument("--no-validate", action="store_true")
    pr.add_argument("--json", action="store_true", help="print the result JSON")

    pm = sub.add_parser("matrix", help="print the live permutation truth table")
    pm.add_argument("--json", action="store_true")

    pe = sub.add_parser("explain", help="explain one cell")
    pe.add_argument("--output", required=True, choices=("rvt", "rfa", "ifc"))
    pe.add_argument("--inputs", required=True,
                    help="comma-separated input kinds, e.g. prompt,rvt")
    pe.add_argument("--json", action="store_true")
    return ap


def cmd_run(a) -> int:
    from rvt.frontdoor import router as R
    inputs = {k: getattr(a, k) for k in ("prompt", "ifc", "rvt", "rfa", "spec")
              if getattr(a, k) is not None}
    opts = {}
    for k in ("out", "stem", "via", "strict", "base", "target_version",
              "stages", "no_validate"):
        v = getattr(a, k, None)
        if v not in (None, False):
            opts[k] = v
    try:
        res = R.route(inputs, a.output, **opts)
    except R.RouteError as e:
        print(f"[route] usage error: {e}", file=sys.stderr)
        return EX_USAGE
    except KeyboardInterrupt:
        return EX_ERR
    except Exception:                                            # noqa: BLE001
        traceback.print_exc()
        return EX_ERR
    if a.json:
        print(json.dumps(res.as_json(), indent=1, default=str))
    else:
        _print_result(res)
    if res.line and not res.ok and not res.files:
        return EX_UNSUPPORTED
    return EX_OK if res.ok else EX_INCOMPLETE


def _print_result(res) -> None:
    print("\n=== tekton route ===")
    c = res.cell or {}
    if c:
        print(f"  cell      : {'+'.join(c.get('inputs') or [])} -> "
              f"{c.get('output')}  [{c.get('status')}]")
    if res.route:
        print(f"  route     : {res.route}")
    print(f"  ok        : {res.ok}")
    print(f"  status    : {res.status}")
    if res.line:
        print(f"  >> {res.line}")
    if res.out_dir:
        print(f"  out dir   : {res.out_dir}")
    for k, v in (res.files or {}).items():
        rl = (res.releases or {}).get(k)
        print(f"  file      : {k} -> {v}" + (f"  (Revit {rl})" if rl else ""))
    for s in res.stamps:
        print(f"  STAMP     : {s}")
    for cv in res.caveats[:8]:
        print(f"  caveat    : {cv}")
    for k, v in (res.manifest_paths or {}).items():
        print(f"  manifest  : {k} -> {v}")
    for e in res.errors[:6]:
        print(f"  error     : {str(e).splitlines()[0][:200]}")
    print(f"  seconds   : {res.seconds}")


def cmd_matrix(a) -> int:
    from rvt.frontdoor import matrix as MX
    if a.json:
        print(json.dumps(MX.as_json(), indent=1, default=str))
        return EX_OK
    print("\ntekton PERMUTATION MATRIX -- inputs {prompt, ifc, rvt, rfa, spec} "
          "-> outputs {rvt, rfa, ifc}")
    print("(machine truth: src/rvt/frontdoor/matrix.py; rendered doc: "
          "docs/product/PERMUTATION-MATRIX.md)\n")
    for row in MX.matrix_rows():
        ins = "+".join(row["inputs"])
        status = row["status"].upper()
        if row["status"] == "missing":
            print(f"  {ins:14s} -> {row['output']:3s}  {status:8s} "
                  f"{row['missing_reason']}")
        else:
            print(f"  {ins:14s} -> {row['output']:3s}  {status:8s} "
                  f"route={row['route']}  stages: {' -> '.join(row['stages'])}")
    print("\nchains (opts --via):")
    for name, ch in MX.CHAINS.items():
        print(f"  {name:24s} [{ch['status']}] {' -> '.join(ch['stages'])}")
    print("\nany other (inputs, output) combination is answered with the "
          "matrix row + the closest supported route in one clear line.")
    probs = MX.verify_evidence()
    if probs:
        print(f"\nWARNING: {len(probs)} evidence citations FAILED the "
              "self-audit (run tests/test_router.py):")
        for p in probs[:10]:
            print(f"  ! {p}")
        return EX_INCOMPLETE
    print(f"\nevidence self-audit: every citation checks out "
          f"({len(MX.CELLS)} cells, {len(MX.STAGES)} stages).")
    return EX_OK


def cmd_explain(a) -> int:
    from rvt.frontdoor import matrix as MX
    kinds = [k.strip() for k in a.inputs.split(",") if k.strip()]
    bad = [k for k in kinds if k not in MX.INPUT_KINDS]
    if bad:
        print(f"[route] unknown input kind(s): {', '.join(bad)}", file=sys.stderr)
        return EX_USAGE
    c = MX.cell_for(kinds, a.output)
    if c is None:
        print(MX.unsupported_line(kinds, a.output))
        return EX_UNSUPPORTED
    if a.json:
        print(json.dumps(c.as_json(), indent=1, default=str))
        return EX_OK
    print(MX.describe_cell(c))
    for e in c.evidence:
        print(f"  evidence : {e}")
    for cv in c.caveats:
        print(f"  caveat   : {cv}")
    if c.hint:
        print(f"  hint     : {c.hint}")
    if c.status == MX.STATUS_MISSING:
        print("  " + MX.unsupported_line(kinds, a.output))
        return EX_UNSUPPORTED
    return EX_OK


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "matrix":
        return cmd_matrix(a)
    if a.cmd == "explain":
        return cmd_explain(a)
    ap.error("unknown command")
    return EX_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
