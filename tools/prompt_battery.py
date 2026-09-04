#!/usr/bin/env python
"""prompt_battery.py -- run realistic prompts end-to-end and hold the line:
every one either DELIVERS a file or refuses WITH the taxonomy's own
explanation (steer #765 / issue #766 DONE 2).

Sweeps (a) a fixed list of prompts users have actually typed, and (b) every
taxonomy row, prompted by its own primary vocabulary.  A row's outcome must
match what the taxonomy CLAIMS: builder_available -> a file; otherwise -> a
refusal whose status carries "NOT buildable here".  Anything else -- a
silent generic failure, a crash, a claimed-buildable kind that refuses --
is a FAIL to fix in-session before anything ships.

USAGE: .venv/bin/python tools/prompt_battery.py [--out out/prompts] [--rows]
Exit 0 = every prompt held the line.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

#: prompts real users typed (the owner's own, first), plus coverage spread.
FIXED_PROMPTS = (
    "a 2x4 recessed troffer light fixture",
    "generate me a rfa troffer light",
    "create a 4x4 troffer",
    "a 2x2 38W 3500K troffer",
    "a downlight",
    "create a cable tray family",
    "a 24-inch-wide cable tray",
    "create a junction box",
    "a strut channel",
    "a wireway",
    "a 2 1/2 in conduit",
    "an electrical room with 2 panels",
    "a 75 kVA transformer",
    "a duplex receptacle",
    "create a VAV box family",
    "a pad mounted transformer",
    "purple monkey dishwasher",
)


def run_prompt(prompt: str) -> Dict[str, Any]:
    from rvt.frontdoor import router as R
    t0 = time.time()
    row: Dict[str, Any] = {"prompt": prompt}
    try:
        res = R.route({"prompt": prompt}, "rfa", out=tempfile.mkdtemp(),
                      quiet=True)
        row["ok"] = bool(res.ok)
        row["status"] = str(res.status)[:220]
        row["delivered"] = bool(res.files.get("rfa")
                                or res.files.get("families_dir"))
        # the honest set names the taxonomy's OWN refusal lines only: the
        # generic "no family plan" was counted here once and made the law
        # partially vacuous -- the battery would have PASSed the original
        # #766 failure itself, and a prompt regressing from delivery to a
        # generic refusal still passed (#768).
        honest = ("NOT buildable here" in str(res.status)
                  or "recognised, NOT built" in str(res.status)
                  or "nothing to author here" in str(res.status))
        row["held_the_line"] = row["ok"] or honest
    except Exception as exc:                                      # noqa: BLE001
        row["ok"] = False
        row["held_the_line"] = False           # a crash never holds the line
        row["status"] = f"CRASH {type(exc).__name__}: {exc}"
    row["seconds"] = round(time.time() - t0, 2)
    return row


def row_prompts() -> List[Dict[str, str]]:
    from rvt.famgen import taxonomy as TX
    out = []
    for k in TX.kinds():
        vocab = None
        for attr in ("primary", "label", "names", "vocab"):
            v = getattr(k, attr, None)
            if isinstance(v, str) and v:
                vocab = v
                break
            if isinstance(v, (list, tuple)) and v:
                vocab = str(v[0])
                break
        if not vocab:
            vocab = str(getattr(k, "key", "")).replace("_", " ")
        avail = TX.builder_available(k)
        # builder_available returns (bool, why); bool((False, why)) is True,
        # which made every unbuildable row look like a broken claim.
        if isinstance(avail, tuple):
            avail = bool(avail[0])
        out.append({"key": str(getattr(k, "key", "?")),
                    "prompt": f"create a {vocab} family",
                    "claims_buildable": bool(avail)})
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "prompts"))
    ap.add_argument("--rows", action="store_true",
                    help="also sweep every taxonomy row")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    for p in FIXED_PROMPTS:
        r = run_prompt(p)
        mark = "PASS" if r["held_the_line"] else "FAIL"
        print(f"[{mark}] {p[:44]:46} ok={r['ok']} {r['status'][:70]}")
        rows.append(r)

    if a.rows:
        for spec in row_prompts():
            r = run_prompt(spec["prompt"])
            r["taxonomy_key"] = spec["key"]
            r["claims_buildable"] = spec["claims_buildable"]
            # a row that CLAIMS a builder must deliver; the reverse is honest
            if spec["claims_buildable"] and not r["ok"]:
                r["held_the_line"] = False
                r["status"] = "CLAIMED buildable, refused: " + r["status"]
            mark = "PASS" if r["held_the_line"] else "FAIL"
            print(f"[{mark}] row:{spec['key'][:38]:40} ok={r['ok']} "
                  f"{r['status'][:60]}")
            rows.append(r)

    passed = sum(1 for r in rows if r["held_the_line"])
    rp = os.path.join(a.out, "prompt_battery.json")
    with open(rp, "w") as fh:
        json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "passed": passed, "total": len(rows), "rows": rows}, fh,
                  indent=1)
    print(f"\n{passed}/{len(rows)} held the line -> {rp}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
