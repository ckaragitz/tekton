#!/usr/bin/env python3
"""ifc_flow.py -- the tekton-ifc skill's documented flow on a foreign IFC in
ONE process: validate -> harden -> re-validate the hardened file -> report.

Usage:
    python ifc_flow.py <in.ifc> --out <dir> [--json] [--quiet]
        [--keep-clearance-as-space] [--no-remove-phantoms]
        [--no-create-types] [--no-extrusions]

The same four steps the CLIs compose one at a time (validate_ifc.py,
harden_ifc.py, validate_ifc.py again, report.py) -- those stay for composing
by hand -- but here ifcopenshell is imported once, the input is parsed and
analysed once and the hardened output once (harden_ifc.harden_analysed
takes the input's report and hands back the output's), so a sandbox pays one
shell round-trip instead of four and two analyses instead of four (issue
#754).  Writes under <dir>:

    validate.json        the full validate_ifc.py report of the input
    hardened.ifc         harden_ifc.py's rewrite (every product GlobalId kept)
    harden.json          harden_ifc.py's action/diff report
    validate-after.json  the full report of the hardened file (it is reopened)
    report.md            report.py's delivery report OF THE HARDENED FILE with the before/after section

and prints ONE summary: with --json a single JSON object (before/after score
+ tier + schema errors, the verdict `line`, the harden actions, the files by
role, per-stage seconds), otherwise a short human summary.  Every file is
written whatever the verdict -- a hardened file with schema errors is
delivered AND reported, never withheld.

Exit codes (the folder's uniform ones):
    0  the flow ran and the hardened file reopens with 0 schema errors
    1  the flow ran but the hardened file has schema errors (files present)
    2  usage / I/O error (missing input, not IFC, output dir not writable) -- no output dir is
       created for an input that does not parse
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_lib as bl  # noqa: E402  (first, like every tool here: a bare interpreter names numpy)
import ifcopenshell  # noqa: E402
import harden_ifc  # noqa: E402
import report as report_md  # noqa: E402

#: what the flow writes under --out, by role, in step order
FILES = {"validate": "validate.json", "hardened": "hardened.ifc", "harden": "harden.json",
         "validate_after": report_md.AFTER_REPORT, "report": "report.md"}


def _score(rep: dict) -> dict:
    """``{"score", "tier", "schema_errors"}`` of a full analysis report."""
    sc = rep["score"]
    return {"score": sc["score"], "tier": sc["tier"],
            "schema_errors": rep["schema"].get("n_errors")}


def run_flow(in_path: str, out_dir: str, **harden_opts) -> dict:
    """The four steps in-process; returns the summary envelope.  Raises what
    the steps raise (the CLI turns an unreadable input into exit 2)."""
    paths = {role: os.path.abspath(os.path.join(out_dir, name)) for role, name in FILES.items()}
    stages = []

    @contextlib.contextmanager
    def timed(name: str):
        t0 = time.time()
        yield
        stages.append({"stage": name, "seconds": round(time.time() - t0, 3)})

    with timed("validate"):
        model = ifcopenshell.open(in_path)          # an unparseable input fails here, before any output exists
        rep0 = bl.analyze(in_path, model=model)
        os.makedirs(out_dir, exist_ok=True)
        bl.dump_json(rep0, paths["validate"])
    with timed("harden+re-validate"):          # harden reopens its output and analyses it (the re-validation)
        res, rep1 = harden_ifc.harden_analysed(in_path, paths["hardened"], rep0, model=model, **harden_opts)
        bl.dump_json(res, paths["harden"])
        bl.dump_json(rep1, paths["validate_after"])
    with timed("report"):
        with open(paths["report"], "w") as fh:
            fh.write(report_md.render(rep1, res, source=os.path.basename(in_path)) + "\n")

    before, after = _score(rep0), _score(rep1)
    ok = after["schema_errors"] == 0
    line = (f"hardened: score {before['score']} -> {after['score']}, 0 schema errors after, "
            f"{len(paths)} files under {os.path.abspath(out_dir)}" if ok else
            f"the hardened file has {after['schema_errors']} schema error(s) -- delivered under "
            f"{os.path.abspath(out_dir)}, fix before linking")
    return {
        "engine": "tekton-ifc flow", "engine_version": bl.ENGINE_VERSION,
        "input": os.path.abspath(in_path), "out_dir": os.path.abspath(out_dir),
        "ok": ok, "line": line,
        "before": before, "after": after,
        "actions": res["actions"],
        "files": paths,
        "stages": stages,
        "seconds": round(sum(s["seconds"] for s in stages), 3),
    }


def human_summary(env: dict) -> str:
    b, a = env["before"], env["after"]
    L = [f"tekton-ifc flow: {os.path.basename(env['input'])} -> {env['out_dir']}",
         "=" * 78,
         f"score         : {b['score']}/100 -> {a['score']}/100",
         f"tier          : {b['tier']} -> {a['tier']}",
         f"schema errors : {b['schema_errors']} -> {a['schema_errors']} after hardening",
         f"verdict       : {env['line']}",
         "actions       : " + ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in env["actions"].items() if v),
         "stages        : " + " · ".join(f"{s['stage']} {s['seconds']:.2f}s" for s in env["stages"])
         + f"  (total {env['seconds']:.2f}s, one process)",
         "files:"]
    L += [f"  {os.path.basename(p)}" for p in env["files"].values()]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input", help="IFC (STEP) file to validate, harden and report on")
    ap.add_argument("--out", required=True, help="directory for the five output files (created)")
    ap.add_argument("--json", action="store_true", help="print the one JSON summary instead of the human one")
    ap.add_argument("--quiet", action="store_true", help="print nothing (the exit code and files are the result)")
    harden_ifc.add_harden_args(ap)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        print(f"error: no such file: {args.input}", file=sys.stderr)
        return 2
    try:
        env = run_flow(args.input, args.out, **harden_ifc.harden_kwargs(args))
    except Exception as e:  # not IFC / parse failure / unwritable output
        print(f"error: could not run the flow on {args.input}: {e}", file=sys.stderr)
        return 2
    if not args.quiet:
        print(json.dumps(env, indent=2, default=str) if args.json else human_summary(env))
    return 0 if env["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
