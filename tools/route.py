#!/usr/bin/env python3
"""route.py -- ANY PERMUTATION: {prompt, ifc, rvt, rfa, spec} in -> {rvt, rfa, ifc} out.

    route.py run --output rvt --prompt "an electrical room 30x20 ft ..."
    route.py run --output rvt --prompt "..." --via ifc          # prompt->IFC->RVT chain
    route.py run --output rvt --ifc design.ifc
    route.py run --output rvt --ifc design.ifc --rvt mine.rvt   # merge onto your file
    route.py run --output rvt --rvt in.rvt --prompt "delete DP-1 with cascade"
    route.py run --output rvt --rvt mine.rvt --prompt "add a 75 kVA transformer to my project"
    route.py run --output rvt --rfa '{"kind": "downlight"}'     # famspec -> .rfa -> loaded .rvt
    route.py run --output rvt --rfa extracted.rfa [--rvt host.rvt]   # reload an extracted family
    route.py run --output ifc --spec room-spec.json
    route.py run --output ifc --rvt project.rvt                 # RVT -> IFC4 (round-trip checked)
    route.py run --output rfa --prompt "a 75 kVA transformer"
    route.py run --output rfa --rvt project.rvt --family DP-1   # extract one embedded family
    route.py run --output rfa --rfa dp1.rfa --prompt "set BusRating 225; rename the type to 225A"

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
                     help="natural language: an authoring prompt; with --rvt "
                          "the edit sentence ('move DP-1 to 3,4') or an "
                          "addition ('add a 75 kVA transformer to my project'); "
                          "with --rfa the family edit ('set BusRating 225')")
    ins.add_argument("--ifc", default=None, metavar="FILE.ifc")
    ins.add_argument("--rvt", default=None, metavar="FILE.rvt",
                     help="an existing project (edit / add / merge target, "
                          "load host, seed, or the source to export / extract from)")
    ins.add_argument("--rfa", default=None, metavar="FAMSPEC|FILE.rfa",
                     help="a famspec JSON ({'kind': 'downlight', ...}, inline "
                          "or a .json path) to GENERATE + load, or a .rfa path "
                          "(the file to edit with --prompt, or a tekton-"
                          "extracted family to reload)")
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
    conv = pr.add_argument_group("convert cells (rvt->rfa extract, add / merge INTO --rvt, rvt->ifc)")
    conv.add_argument("--family", default=None, metavar="SELECTOR",
                      help="rvt->rfa: which embedded family to extract "
                           "(name fragment | family id | unit index)")
    conv.add_argument("--level", default=None, metavar="N|NAME",
                      help="add/merge into --rvt: the target level "
                           "(1-based storey index or name substring)")
    conv.add_argument("--at", type=float, nargs=2, default=None, metavar=("X_M", "Y_M"),
                      help="add into --rvt: explicit anchor in metres (default: "
                           "free floor space east of the target's content)")
    conv.add_argument("--offset", type=float, nargs=2, default=None, metavar=("DX_M", "DY_M"),
                      help="merge into --rvt: explicit offset in metres "
                           "(0 0 = the IFC's own world frame; default: disjoint east)")
    conv.add_argument("--no-roundtrip", action="store_true",
                      help="rvt->ifc: skip the resolve_intent round-trip check")
    pr.add_argument("--json", action="store_true",
                    help="print the result as ONE JSON document on stdout "
                         "(stage progress goes to <out>/route.log)")

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
              "stages", "no_validate", "family", "level", "at", "offset",
              "no_roundtrip"):
        v = getattr(a, k, None)
        if v not in (None, False):
            opts[k] = v
    if a.json:
        opts["quiet"] = True    # stdout is exactly ONE JSON document (issue #188)
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
    """Print the live table + run the evidence self-audit (one renderer,
    rvt.frontdoor.matrix.render_text, shared with tools/frontdoor.py matrix).
    Exit 3 only on HARD audit problems (a citation missing from the ledger /
    the tree); certified probe binaries absent on a fresh clone are a note."""
    from rvt.frontdoor import matrix as MX
    if a.json:
        payload = MX.as_json()
        payload["audit"] = rep = MX.audit()
        print(json.dumps(payload, indent=1, default=str))
        return EX_INCOMPLETE if (rep["ledger_present"] and rep["problems"]) else EX_OK
    text, rep = MX.render_text()
    print(text, end="")
    if rep.get("ledger_present") and rep.get("problems"):
        return EX_INCOMPLETE
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
