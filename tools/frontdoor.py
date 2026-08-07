#!/usr/bin/env python3
"""frontdoor.py -- THE MULTI-SURFACE FRONT DOOR: ONE entrypoint, THREE inputs.

    frontdoor author --prompt "an electrical room 30x20 ft rated for 2500 A service \\
        with a main switchboard, two 400 A distribution panels and four lighting panels" \\
        [--out DIR] [--strict] [--handoff-only] [--target-version {2026,2025,2024}]

    frontdoor author --ifc design.ifc [--out DIR] [--strict]

    frontdoor author --rvt in.rvt --edit "delete DP-1 with cascade; move LP-2 to 3,4" [--out DIR]
    frontdoor author --rvt in.rvt --edit ops.json                          [--out DIR]

Every route lands in the SAME intent model, the SAME build step (intent ->
our .rvt ON THE CERTIFIED GENESIS BASE -- never an Autodesk sample) and the
SAME deliverable manifest (route, intent, elements created, families
generated, base + certification, validator summary, PROOF-ONLY stamps, CRUD
affordances).  Runs from ANY AI surface (Claude Design / Chat / Cowork,
ChatGPT Work, Gemini, ...) or a shell.

ROUTES
  --prompt  (a) PRIMARY: emits the three-d-stage HANDOFF (scene-brief.json +
            HANDOFF.md + PROMPT_TO_IFC.md) an AI surface executes with Three.js
            -> IFC4 -> back through --ifc.  (b) FALLBACK: a rules-first
            deterministic parser resolves the prompt straight into the intent
            model and builds it -- NO external model call, NO API key; its
            coverage (understood / ignored / defaulted / not-built) rides in
            the manifest.  --handoff-only skips the fallback build.
  --ifc     rvt.ifc.intent (placement chains + world geometry + tagging-
            contract Pset join key) -> intent -> build.
  --rvt     rvt.mutate.Document.from_file + the edit CLI's operations
            (modify / move / retype / delete / cascade) via the job runner's
            certified edit pipeline; --edit takes an edit SENTENCE, an
            ops.json path, or inline JSON.

THE OPEN BUG (walls + loaded families in one file trip Autodesk's audit) is
DETECTED, never silently shipped:  --strict emits TWO coordinated files
(shell + equipment); the default emits ONE combined file STAMPED
'PROOF-ONLY: walls+families combination unverified'.

Exit codes: 0 = the route completed (status in the manifest; PROOF-ONLY is
still 0), 2 = usage / route error, 3 = build/edit did not complete,
4 = self-checks failed, 1 = unexpected error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "lib", "src")):   # repo / plugin layout
    if p not in sys.path:
        sys.path.insert(0, p)

EX_OK, EX_ERR, EX_USAGE, EX_INCOMPLETE, EX_SELFCHECK = 0, 1, 2, 3, 4


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="frontdoor",
        description="THE FRONT DOOR: prompt / IFC / (rvt + edit) -> the ONE intent model -> our "
                    ".rvt on the certified genesis base + a deliverable manifest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="One entrypoint, three inputs -- exactly ONE of --prompt / --ifc / --rvt.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("author", help="author from a prompt, an IFC, or an existing .rvt + edit")
    src = pa.add_argument_group("input (exactly one)")
    src.add_argument("--prompt", default=None, metavar="TEXT",
                     help="a natural-language description (primary: AI-surface handoff; "
                          "fallback: built-in deterministic parser, no API key)")
    src.add_argument("--ifc", default=None, metavar="FILE.ifc",
                     help="an authored IFC (the resolved-placement / Pset-join-key route)")
    src.add_argument("--rvt", default=None, metavar="FILE.rvt",
                     help="an EXISTING Revit project to edit (requires --edit)")
    src.add_argument("--edit", default=None, metavar="TEXT|ops.json|JSON",
                     help="the edit for --rvt: an edit sentence ('delete DP-1 with cascade; "
                          "move LP-2 to 3,4'), an ops.json path, or inline JSON ops")
    outg = pa.add_argument_group("output")
    outg.add_argument("--out", "-o", default=None, metavar="DIR",
                      help="output directory (default: experiments/frontdoor/<name>-<stamp>)")
    outg.add_argument("--stem", default=None, help="output file stem (default: from the input name)")
    pol = pa.add_argument_group("build policy")
    pol.add_argument("--target-version", type=int, choices=(2026, 2025, 2024), default=None,
                     metavar="{2026,2025,2024}",
                     help="the Revit release the RECIPIENT runs (ASK the user first -- Revit "
                          "cannot open a newer file). 2026 = the certified base (default). "
                          "2025 / 2024 = resolve that release's genesis base when its "
                          "campaign certifies; until then the build DELIVERS the 2026 file "
                          "plus one clear line ('target N requested: ...') and a version-"
                          "agnostic IFC addition -- never a silent 2026 file presented as "
                          "the target")
    pol.add_argument("--strict", action="store_true",
                     help="the walls+families OPEN BUG -> emit TWO coordinated files "
                          "(shell + equipment) instead of one stamped combined file")
    pol.add_argument("--base", default=None, metavar="FILE.rvt",
                     help="author on this base instead of the pinned genesis base (an Autodesk "
                          "sample is REFUSED); the pin is hash-verified when omitted")
    pol.add_argument("--specimens", default=None, metavar="FILE.rvt",
                     help="specimen ancestor to clone scaffolding from (default: the pinned R5)")
    pol.add_argument("--stages", default="FLWECV",
                     help="build stages subset: F(amilies) L(oad) W(alls) E(quipment) C(ircuits) "
                          "V(alidate) [default FLWECV]")
    pol.add_argument("--wall-mode", default="min", choices=("min", "unjoin", "raw"),
                     help="wall clone clean-up mode (default min)")
    pol.add_argument("--symbol-hollow", action="store_true",
                     help="loaded symbols without solids (bisection aid)")
    pol.add_argument("--no-validate", action="store_true",
                     help="skip the validation gate (NOT a shippable run; debugging only)")
    pol.add_argument("--strict-validate", action="store_true",
                     help="validator strict mode on the --rvt route")
    pp = pa.add_argument_group("prompt route")
    pp.add_argument("--handoff-only", action="store_true",
                    help="emit the AI-surface handoff (scene brief + instructions) and skip "
                         "the fallback build")
    pp.add_argument("--no-handoff", action="store_true",
                    help="skip the handoff package (fallback build only)")
    pa.add_argument("--json", action="store_true", help="print the result as JSON")
    pa.add_argument("--verbose", "-v", action="store_true", help="stream the build log")
    return ap


def _print_summary(r) -> None:
    print("\n=== tekton front door ===")
    print(f"  route     : {r.route}")
    print(f"  status    : {r.status}")
    tv = (r.manifest or {}).get("target_version") or {}
    if tv.get("line"):
        print(f"  VERSION   : {tv['line']}")
    elif tv.get("requested"):
        print(f"  version   : target {tv.get('requested')} -> output release "
              f"{tv.get('output_release')} ({tv.get('status')})")
    print(f"  out dir   : {r.out_dir}")
    if r.intent_json:
        print(f"  intent    : {r.intent_json}")
    for k, v in (r.handoff or {}).items():
        if k != "primary_path_note":
            print(f"  handoff   : {k} -> {v}")
    for role, p in (r.files or {}).items():
        print(f"  file      : {role} -> {p}")
    for k, v in (r.manifest_paths or {}).items():
        print(f"  manifest  : {k} -> {v}")
    verdict = ((r.manifest or {}).get("build") or {}).get("combination_verdict") or {}
    if verdict.get("stamp"):
        print(f"  STAMP     : {verdict['stamp']}")
    for e in r.errors[:6]:
        print(f"  error     : {str(e).splitlines()[0][:200]}")
    print(f"  seconds   : {r.seconds}")


def cmd_author(a) -> int:
    from rvt import frontdoor as FD
    try:
        req = FD.AuthorRequest(
            prompt=a.prompt, ifc=a.ifc, rvt=a.rvt, edit=a.edit, out=a.out,
            base=a.base, strict=a.strict, handoff_only=a.handoff_only,
            no_handoff=a.no_handoff, stages=a.stages, wall_mode=a.wall_mode,
            specimens=a.specimens, symbol_hollow=a.symbol_hollow,
            no_validate=a.no_validate, strict_validate=a.strict_validate,
            stem=a.stem, quiet=not a.verbose, target_version=a.target_version)
        r = FD.run(req)
    except FD.FrontDoorError as e:
        print(f"[frontdoor] usage error: {e}", file=sys.stderr)
        return EX_USAGE
    except FD.BaseError as e:
        print(f"[frontdoor] base error: {e}", file=sys.stderr)
        return EX_USAGE
    except KeyboardInterrupt:
        return EX_ERR
    except Exception:                                                # noqa: BLE001
        traceback.print_exc()
        return EX_ERR
    if a.json:
        print(json.dumps(r.as_json(), indent=1, default=str))
    else:
        _print_summary(r)
    st = str(r.status).upper()
    if st.startswith("SELF-CHECKS FAILED"):
        return EX_SELFCHECK
    if not r.ok:
        return EX_INCOMPLETE
    return EX_OK


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.cmd == "author":
        return cmd_author(a)
    ap.error("unknown command")
    return EX_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
