#!/usr/bin/env python3
"""make_probes.py -- the SINGLE-VARIABLE viewer pair for the native feeder
circuits of issue #146 (PROOF-ONLY; builds, validates, writes probes.json;
does NOT stage -- staging + upload + verdicts belong to a reserved batch).

Variable = the circuit layer ON / OFF, everything else identical:

  CTRL_G_ABPD_circuits146.rvt   byte-identical copy of the certified base
  C146_off.rvt                  the DONE prompt's room WITHOUT circuits
                                (--stages FLWEV: no stage C, E wires nothing)
  C146_on.rvt                   the same room WITH the 6 feeder circuits
                                (stage E as shipped: instances + circuits in
                                one commit)

Both probes carry PLACED INSTANCES of our generated families = the OPEN
CELL (docs/inbox/genesis-audit.md #48, issue #16), so 'on' can only be read
RELATIVE to 'off': identical card/failure => the circuit layer adds no new
defect; 'off' FAIL + 'on' a DIFFERENT failure => the circuit records are a
second defect; both PASS => circuits certified with the instances.  A
control FAIL voids the round.

NEXT single variable if 'on' fails where 'off' does not (issue #360, from
#353's review): the constructed template ships m_circuitPathMode / m_nNumRuns
/ m_nextFreeSectionId / m_pathOffsetAllDevice at schema default 0, but the
checked-in census experiments/genesis/lint/invariants/RbsElectricalSystem.json
has them CORPUS-CONSTANT 2 / 1 / 1 / 30000.0 (188/188 specimens).  Apply the
four together as ONE variable ('C146_on_pathconst' vs 'C146_on'), bisect only
if the card flips.  Recorded in probes.json as "next_single_variable"; the
shipped values are NOT changed until a viewer verdict says so (rule 4).

    .venv/bin/python experiments/mep/circuits146/make_probes.py [--target-version 2026]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

PROMPT = ("electrical room 30x20 ft with a 2000A main switchboard, two 400A "
          "distribution panels and four lighting panels")

#: the candidate for the round AFTER the on/off pair (docs/inbox/mep-electrical.md § eng360)
NEXT_SINGLE_VARIABLE = {
    "why": ("eng146 shipped these four RbsElectricalSystem fields at schema default as 'not "
            "derivable'; the checked-in corpus census shows each is constant over 188/188 "
            "specimens -- the highest-prior circuit-layer variable, applied together first"),
    "census": "experiments/genesis/lint/invariants/RbsElectricalSystem.json",
    "fields": {"m_circuitPathMode": {"shipped": 0, "census": 2, "support": "188/188"},
               "m_nNumRuns": {"shipped": 0, "census": 1, "support": "188/188"},
               "m_nextFreeSectionId": {"shipped": 0, "census": 1, "support": "188/188"},
               "m_pathOffsetAllDevice": {"shipped": 0.0, "census": 30000.0, "support": "188/188"}},
    "probe": "C146_on_pathconst = C146_on with the four census values (one variable); "
             "control + C146_off + C146_on unchanged",
    "not_a_candidate": "m_nPhaseInfo (0:1 / 1:124 / 2:33 / 3:30 -- not constant)",
    "status": "NOT built, NOT staged, shipped template unchanged (viewer-gated decision)",
}


def _md5(p: str) -> str:
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(p: str) -> str:
    return os.path.relpath(os.path.abspath(p), ROOT).replace(os.sep, "/")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-version", type=int, default=2026)
    ap.add_argument("--out", default=HERE)
    a = ap.parse_args(argv)
    from rvt.frontdoor import author
    from rvt.frontdoor.base import resolve_base
    from rvt.frontdoor.build import load_ifc_room_module
    R = load_ifc_room_module()          # the SAME module object the build calls into

    out = os.path.abspath(a.out)
    base = resolve_base(target_release=a.target_version).path
    kw = {} if a.target_version == 2026 else {"target_version": a.target_version}
    # 'on' = the shipped path (front door, all stages)
    on_dir = os.path.join(out, "_on")
    r_on = author(prompt=PROMPT, out=on_dir, no_handoff=True, **kw)
    on_src = r_on.manifest["build"]["files"]["combined"]["path"]
    on = os.path.join(out, "C146_on.rvt")
    shutil.copyfile(on_src, on)
    # 'off' = the same job without stage C (stage E then wires no circuit)
    off = os.path.join(out, "C146_off.rvt")
    r_off = author(prompt=PROMPT, out=os.path.join(out, "_off"), no_handoff=True,
                   stages="FLWEV", **kw)
    shutil.copyfile(r_off.manifest["build"]["files"]["combined"]["path"], off)
    ctrl = os.path.join(out, "CTRL_" + os.path.splitext(os.path.basename(base))[0]
                        + "_circuits146.rvt")
    shutil.copyfile(base, ctrl)

    probes = []
    for path, key, circ in ((off, "off", r_off), (on, "on", r_on)):
        val = R.validate_rvt(path)
        rb = R.read_back_circuits(path)
        b = circ.manifest["build"]
        probes.append({
            "file": _rel(path), "probe": f"C146_{key}", "kind": "probe",
            "base": _rel(base), "md5": val["md5"],
            "validator": val["verdict"], "validator_errors": val["n_errors"],
            "circuits": rb["n"], "circuit_links_ok": rb["links_ok"],
            "instances": len([c for c in b["elements_created"]
                              if c["kind"] == "equipment-instance"]),
            "walls": len([c for c in b["elements_created"] if c["kind"] == "wall"]),
            "identity_gate": (b["validation"]["combined"].get("identity") or {}).get("status"),
            "tests": ("the DONE prompt's room with the feeder circuit layer "
                      + ("ON (6 constructed RbsElectricalSystem, both-side links)"
                         if key == "on" else "OFF (instances carry free slots only)")),
            "variable": "circuits " + key,
            "stamp": "PROOF-ONLY: generated-family INSTANCES on a composed genesis base "
                     "(open cell, docs/inbox/genesis-audit.md #48, issue #16)",
        })
    manifest = {
        "stream": "mep-electrical / issue #146: native feeder circuits, single-variable pair",
        "issue": 146, "target_version": a.target_version, "prompt": PROMPT,
        "base": {"file": _rel(base),
                 "certification": {"file": _rel(base),
                                   "proves": "pinned composed genesis base of this release "
                                             "(docs/coverage/viewer-certified.json)"}},
        "standing_control": {"file": _rel(ctrl), "identical_to": _rel(base), "md5": _md5(ctrl),
                             "purpose": "byte-identical certified base; read FIRST, a FAIL "
                                        "voids the round"},
        "read_order": "control, then C146_off (the open instance cell alone), then C146_on",
        "reading_the_results": {
            "control FAIL": "environment/oracle problem -- round VOID",
            "off FAIL, on FAIL with the same card": "circuit layer adds no new defect; the "
                                                    "instance cell (#16) masks it -- re-run "
                                                    "the pair when #16 closes",
            "off FAIL, on FAIL differently / earlier": "the circuit records are a second, "
                                                       "independent defect -- bisect the "
                                                       "RbsElectricalSystem field table in "
                                                       "docs/inbox/mep-electrical.md",
            "off PASS, on FAIL": "the circuit layer alone fails -- same bisection",
            "both PASS": "feeder circuits certified together with the instances",
        },
        "not_staged": ("deliberately NOT staged by the authoring session (issue #146 stops "
                       "at validator + readback); reserve a batch (/batches 1) and run "
                       "tools/probe_batch.py stage --manifest experiments/mep/circuits146/"
                       "probes.json --batch <N>"),
        "next_single_variable": NEXT_SINGLE_VARIABLE,
        "probes": probes,
    }
    path = os.path.join(out, "probes.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(json.dumps({"probes_json": _rel(path),
                      "probes": [{k: p[k] for k in ("probe", "validator", "validator_errors",
                                                    "circuits", "circuit_links_ok",
                                                    "instances", "md5")} for p in probes],
                      "control_md5": manifest["standing_control"]["md5"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
