#!/usr/bin/env python3
"""rvt_edit.py — edit an EXISTING .rvt from the command line (the MANIPULATE
verb): inspect, delete, modify parameters, move, retype. Every write is
followed by the structural self-verification; run tools/rvt_validate.py on
the result for the full pre-flight -- or pass ``--json`` and get the edit,
the structural self-check AND the mandatory validation gate in ONE process
with ONE JSON object on stdout (what ``_bootstrap.py go edit ...`` runs;
issue #111).

    rvt_edit.py FILE info                              # inventory summary
    rvt_edit.py FILE deps   --id 1466502                # dependents report
    rvt_edit.py FILE delete --id 1466502 [--cascade] -o out.rvt
    rvt_edit.py FILE rename-panel --id 742670 --name "HG4" -o out.rvt
    rvt_edit.py FILE set-mark --id 1466502 --mark "P-14" -o out.rvt
    rvt_edit.py FILE set-level --id 311 --elevation-ft 12.0 -o out.rvt
    rvt_edit.py FILE move   --id 1466502 --to 10 4 0 [--rotation-deg 90] -o out.rvt
    rvt_edit.py FILE retype --id 1466502 --symbol 619617 -o out.rvt
    ... any of the above --json                          # ONE JSON: edit + gates

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
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "lib", "src"))     # plugin layout

from rvt.mutate import Document  # noqa: E402
from rvt import manipulate as M  # noqa: E402
from rvt import inventory as INV  # noqa: E402
from rvt import versions as V  # noqa: E402
from rvt.frontdoor.release_ctx import enter_host_release  # noqa: E402
from rvt.frontdoor.target_status import opens_in  # noqa: E402

WRITE_VERBS = ("delete", "rename-panel", "set-mark", "set-level", "move", "retype")


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


def _inventory_summary(doc) -> dict:
    """`info`: the inventory with every list capped at 12 entries (stats whole)."""
    return {k: (v if k == 'stats' else (v[:12] if isinstance(v, list) else v))
            for k, v in INV.inventory(doc).items()}


def _release_block(in_path: str, out_path: str | None) -> dict:
    """Revit N in -> Revit N out, detected from each file's own BasicFileInfo."""
    rin = V.detect_release(in_path)
    rout = V.detect_release(out_path) if out_path and os.path.isfile(out_path) else None
    return {"input": rin, "output": rout, "opens_in": opens_in(rout or rin),
            "line": (f"Revit {rin} in, Revit {rout} out; opens in Revit {rout} and newer, "
                     "never older" if rin and rout else None)}


def _gates(a: argparse.Namespace, rep) -> dict:
    """The structural self-check + THE MANDATORY VALIDATION GATE on the file
    just written, in this process, with rvt_job's own gate verdicts (the
    manifest's ``structural`` / ``validation`` blocks -- so this door and
    the ops door state the very same facts; 0 validator errors REQUIRED,
    the file is delivered either way)."""
    from rvt.frontdoor.edit import load_job_module
    J = load_job_module()
    deleted = list(rep.removed_ids)
    edited = [] if a.cmd == "delete" else [a.id]
    v = M.verify_manipulated(a.out, deleted_ids=deleted, edited_ids=edited)
    structural = J.structural_gate_from_manipulated(v)
    validation = J.validation_gate(a.out, a.out + ".validation.json")
    ok = structural["status"] == "PASS" and validation["status"] == "PASS"
    line = (f"structural {structural['status']} (crc_failures={v.get('crc_failures')}, "
            f"ecc_mismatches={v.get('ecc_mismatches')}, walker_errors={v.get('walker_errors')}, "
            f"stamps_ok={v.get('stamps_ok')}) | validation {validation['status']} "
            f"({validation['errors']} errors, {validation['warnings']} warnings)")
    return {"hard_gates_passed": ok, "line": line,
            "structural": structural, "validation": validation}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    want_json = "--json" in argv                 # position-free: `go edit` appends it last
    argv = [x for x in argv if x != "--json"]
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
    if a.cmd in WRITE_VERBS:                     # `-o out/edited.rvt` into a fresh dir just works
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with contextlib.ExitStack() as stack:
        note = enter_host_release(stack, a.file)
        if note:
            print(f"[rvt_edit] warning: {note}", file=sys.stderr)
        return _run_json(a, note) if want_json else _run(a)


def _edit(a: argparse.Namespace, doc):
    """Plan + commit the ONE write verb; returns the ManipCommitReport."""
    if a.cmd == "delete":
        plans = [M.delete_element(doc, a.id, cascade=a.cascade)]
    elif a.cmd == "rename-panel":
        plans = [M.rename_panel(doc, a.id, a.name)]
    elif a.cmd == "set-mark":
        plans = [M.set_mark(doc, a.id, a.mark)]
    elif a.cmd == "set-level":
        plans = [M.set_level_elevation(doc, a.id, a.elevation_ft)]
    elif a.cmd == "move":
        rot = math.radians(a.rotation_deg) if a.rotation_deg is not None else None
        plans = [M.move_instance(doc, a.id, tuple(a.to), rotation=rot)]
    else:                                                   # retype (argparse guarantees the verb)
        plans = [M.retype_instance(doc, a.id, a.symbol)]
    return M.commit_plans(a.file, a.out, plans)


def _run(a: argparse.Namespace) -> int:
    doc = Document.from_file(a.file)

    if a.cmd == "info":
        print(json.dumps(_inventory_summary(doc), indent=2, default=str))
        return 0
    if a.cmd == "deps":
        print(json.dumps(M.dependency_report(doc, a.id), indent=2, default=str)[:6000])
        return 0

    _report(_edit(a, doc), a.out)
    return 0


def _run_json(a: argparse.Namespace, note) -> int:
    """``--json``: ONE JSON object on stdout carrying everything a skill
    session reports -- the edit's change report, the written file, Revit N
    in / N out, the structural self-check and THE MANDATORY VALIDATION GATE
    (run here, in-process; never skipped) -- so the whole tekton-edit flow is
    ONE shell call (issue #111).  An impossible edit (unknown id, a delete
    with dependents and no --cascade) is ``ok: false`` + ONE ``error`` line
    (+ ``dependents`` when that is the blocker).  Exit 0 = written AND both
    gates PASS; 1 otherwise (a written file is still named: deliver it, then
    say which gate stopped it)."""
    t0 = time.time()
    res: dict = {"ok": False, "command": a.cmd,
                 "input": {"path": os.path.abspath(a.file)}}
    if note:
        res["release_note"] = note
    try:
        doc = Document.from_file(a.file)
        if a.cmd == "info":
            res.update(_inventory_summary(doc), ok=True)
        elif a.cmd == "deps":
            res.update({"id": a.id, "deps": M.dependency_report(doc, a.id), "ok": True})
        else:
            res["id"] = a.id
            rep = _edit(a, doc)
            res["report"] = rep.to_json()
            res["output"] = {"path": os.path.abspath(a.out), "bytes": os.path.getsize(a.out)}
            res["gates"] = _gates(a, rep)
            res["output"]["validation_json"] = res["gates"]["validation"].get("report_json")
            res["ok"] = bool(res["gates"]["hard_gates_passed"])
            res["status_note"] = ("self-checks + validator are necessary, NOT sufficient: "
                                  "'accepted by Autodesk' only after the user opens the file")
    except M.DependentsError as e:
        res["error"] = str(e).splitlines()[0]
        res["dependents"] = (e.report or {}).get("dependents", [])[:50]
    except M.ManipulationError as e:
        res["error"] = f"{a.cmd} impossible: {e}"
    except (ValueError, LookupError) as e:               # unknown id and friends: ONE clear line
        res["error"] = f"{a.cmd} failed: {type(e).__name__}: {e}"
    res["release"] = _release_block(a.file, (res.get("output") or {}).get("path"))
    res["seconds"] = round(time.time() - t0, 3)
    print(json.dumps(res, indent=1, default=str))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
