#!/usr/bin/env python
"""famload_lane.py -- THE 2025 FAMLOAD / INSTANCE LANE PROBES + STAGED BATCH
(famload-2025-lane stream, issue #14; record docs/inbox/famload-2025-lane.md).

Builds three single-variable probes on the CERTIFIED composed 2025 base,
each through a lane that -- before this stream -- died on a 2025 host with
``unexpected Partitions header: v=9 cls=0x391`` (gap B), runs the FIVE-GATE
emission check on every one, and stages the viewer batch through the
``tools/probe_batch.py`` gate (control = a byte-identical copy of the
certified ``G_ABPD_2025``).  Nothing is uploaded here: a session STAGES and
stops at READY; a human uploads and records verdicts (CLAUDE.md rule 4).

    probe                lane (called BARE on the 2025 host)          instance?
    FL25_head            rvt.famload (four-registry) -- section head   no
    L25_panel_noinst     rvt.famgen.loader -- generated panelboard      no
    ATP25_lp1            rvt.convert.add_to_project (prompt + RVT)      YES (1)

Reading order control -> FL25_head -> L25_panel_noinst -> ATP25_lp1.  The
first two are the NO-INSTANCE shapes that pass on 2026 (L1a / BX_f2 / H10);
they ask the one question batch 35 never isolated: does the 2025 four-
registry WRITE (ContentDocuments tokens 0x391/0x390, unit separator, 0x0eee
footer, ContentTable/FamilyMgr rows under the 2025 schema) satisfy
Autodesk's 2025 reader?  ATP25_lp1 adds the ONE variable of the OPEN cell
(a placed instance of our generated family on our composed base) -- it is
expected to share that cell's fate; a FAIL there with the two loads PASS
re-reads as the release-independent residual, not a 2025 regression.

Outputs are NOT byte-deterministic (the loaders mint uuid4 document /
session GUIDs -- issue #9), so the batch must be staged on the machine
that uploads it:

    .venv/bin/python experiments/frontdoor2025/famload_lane.py build   # probes + five-gate report
    .venv/bin/python experiments/frontdoor2025/famload_lane.py stage   # gate + control + batch_N.json
    .venv/bin/python experiments/frontdoor2025/famload_lane.py all     # both

``build`` needs only the bundled base (plugin/assets/genesis, in git); when
the ledger path of the certified base (experiments/genesis/subst_k4_2025/
compose/G_ABPD_2025.rvt, git-ignored) is absent it is materialised from the
bundled copy after a sha256 check against the registry pin -- the same
bytes the ledger certified, so the staged control is byte-identical.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import rvt.versions as V                                       # noqa: E402
from rvt.frontdoor import base as B                            # noqa: E402

OUT_DIR = os.path.join(HERE, "famload_lane")
REPORT = os.path.join(HERE, "famload_lane_report.json")
PROBES_JSON = os.path.join(HERE, "probes.json")
LEDGER_BASE_REL = V.KNOWN_RELEASES[2025].genesis_base
LEDGER_BASE = os.path.join(ROOT, LEDGER_BASE_REL)

PROBES = [
    {"name": "FL25_head", "lane": "rvt.famload.load_family_document",
     "instance": False,
     "contents": "the certified 2025 base + ONE constructor-built annotation "
                 "family (RW Section Head - Open) loaded four-registry; NO instance"},
    {"name": "L25_panel_noinst", "lane": "rvt.famgen.loader.load_family_into_project(place=False)",
     "instance": False,
     "contents": "the certified 2025 base + ONE generated Eaton PRL1X 400 A "
                 "panelboard family loaded four-registry; NO instance"},
    {"name": "ATP25_lp1", "lane": "rvt.convert.add_to_project('add a 100 A lighting panel')",
     "instance": True,
     "contents": "the certified 2025 base + ONE generated 100 A lighting "
                 "panelboard family loaded four-registry + ONE placed instance "
                 "(constructed-specimen scaffolding, free-standing)"},
]


_sha256 = B.sha256_of


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(p: str) -> str:
    return os.path.relpath(os.path.abspath(p), ROOT)


def _emission_check():
    spec = importlib.util.spec_from_file_location(
        "emission_check", os.path.join(HERE, "emission_check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                                # type: ignore[union-attr]
    return mod.check_emission


def ensure_ledger_base() -> str:
    """The certified 2025 base at its LEDGER path.  Materialised from the
    bundled copy (sha256 == the registry pin == the ledger's bytes) when the
    git-ignored compose output is absent (fresh clone / cloud session)."""
    want = str((B.PIN.release_slot(2025) or {}).get("sha256") or "").lower()
    if os.path.isfile(LEDGER_BASE):
        got = _sha256(LEDGER_BASE)
        if want and got != want:
            raise SystemExit(f"{LEDGER_BASE_REL} sha256 {got[:16]}.. != pin {want[:16]}..")
        return LEDGER_BASE
    bundled = B.resolve_base(target_release=2025)             # pin-verified
    if want and bundled.sha256.lower() != want:
        raise SystemExit("bundled 2025 base does not match the registry pin")
    os.makedirs(os.path.dirname(LEDGER_BASE), exist_ok=True)
    shutil.copyfile(bundled.path, LEDGER_BASE)
    assert _sha256(LEDGER_BASE) == want
    print(f"[lane] materialised {LEDGER_BASE_REL} from the bundled copy (sha256 {want[:16]}..)")
    return LEDGER_BASE


def build() -> Dict[str, Any]:
    from rvt import famload as FL
    from rvt.famgen import heads as H
    from rvt.famgen import loader as L
    from rvt.convert import add_to_project as ATP
    from rvt.frontdoor import release_ctx as RC

    base = ensure_ledger_base()
    os.makedirs(OUT_DIR, exist_ok=True)
    check = _emission_check()
    rep: Dict[str, Any] = {"stream": "famload-2025-lane (issue #14)",
                           "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "base": _rel(base), "base_sha256": _sha256(base),
                           "probes": []}
    t0 = time.time()

    # FL25_head -- the four-registry annotation loader, bare
    out = os.path.join(OUT_DIR, "FL25_head.rvt")
    res = FL.load_family_document(base, H.family_load("section_head_open"), out,
                                  name="section_head_open",
                                  report_path=os.path.join(OUT_DIR, "FL25_head.load.json"))
    ver = res.proofs.get("verify_written") or {}
    rep["probes"].append({**PROBES[0], "file": _rel(out), "ok": bool(res.ok),
                          "registries": ver.get("registries"),
                          "host_linkage_ok": (ver.get("host_linkage") or {}).get("ok")})

    # L25_panel_noinst -- the component loader, bare, no placement
    out = os.path.join(OUT_DIR, "L25_panel_noinst.rvt")
    res2 = L.load_family_into_project(base, out, place=False, validate=True,
                                      report_path=os.path.join(OUT_DIR, "L25_panel_noinst.load.json"))
    ver2 = res2.proofs.get("verify") or res2.proofs.get("verify_written") or {}
    rep["probes"].append({**PROBES[1], "file": _rel(out), "ok": bool(res2.ok),
                          "stop_reason": res2.stop_reason,
                          "symbol_id": res2.plan.symbol_id if res2.plan else None,
                          "family_id": res2.plan.host_family_id if res2.plan else None,
                          "verify_keys": sorted(ver2)[:12]})

    # ATP25_lp1 -- prompt + RVT(2025) -> RVT(2025), one placed instance
    atp_dir = os.path.join(OUT_DIR, "ATP25_lp1")
    rec = ATP.add_to_project("add a 100 A lighting panel", base, atp_dir, stem="ATP25_lp1")
    out = rec["files"]["combined"]
    final = os.path.join(OUT_DIR, "ATP25_lp1.rvt")
    shutil.copyfile(out, final)
    rep["probes"].append({**PROBES[2], "file": _rel(final), "ok": not rec["errors"],
                          "errors": rec["errors"], "created": rec["created"],
                          "census": (rec["validation"].get("combined") or {}).get("census"),
                          "target_release": rec["target"]["release"]})
    assert RC.active_release() is None

    # the five-gate emission check on every probe (release-aware validator,
    # 2025 framing only, four registries coherent)
    all_pass = True
    for p in rep["probes"]:
        path = os.path.join(ROOT, p["file"])
        em = check(path, 2025)
        p["md5"] = _md5(path)
        p["bytes"] = os.path.getsize(path)
        p["emission"] = {"pass": em["pass"],
                         "gates": {k: v.get("pass") for k, v in em["gates"].items()}}
        p["census_after"] = em["gates"].get("G5_registries")
        all_pass = all_pass and bool(em["pass"]) and bool(p["ok"])
        print(f"[lane] {p['name']:<18} ok={p['ok']} five-gate={'PASS' if em['pass'] else 'FAIL'} "
              f"{p['bytes']:,} B md5 {p['md5']}")
    rep["all_pass"] = all_pass
    rep["seconds"] = round(time.time() - t0, 1)
    with open(REPORT, "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    print(f"[lane] report -> {_rel(REPORT)}  all_pass={all_pass}  ({rep['seconds']} s)")
    return rep


def stage(note: str = "") -> Dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "probe_batch", os.path.join(ROOT, "tools", "probe_batch.py"))
    PB = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(PB)                                 # type: ignore[union-attr]
    base = ensure_ledger_base()
    files = [os.path.join(OUT_DIR, f"{p['name']}.rvt") for p in PROBES]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"build first: missing {[_rel(m) for m in missing]}")
    note = note or (
        "famload-2025-lane (issue #14): the three load/place lanes called BARE on the "
        "certified G_ABPD_2025 (host release context). Control = byte-identical copy of "
        "the CERTIFIED G_ABPD_2025. Reading order: control -> FL25_head (famload head, no "
        "instance) -> L25_panel_noinst (famgen loader, generated panel, no instance) -> "
        "ATP25_lp1 (add_to_project: generated panel + ONE placed instance = the OPEN cell's "
        "variable). The two no-instance loads isolate the 2025 four-registry WRITE; "
        "ATP25_lp1 is expected to share the open instance-audit cell's fate (release-"
        "independent) -- its FAIL with both loads PASS is the residual, not a 2025 defect. "
        "Five-gate emission check green on all three (experiments/frontdoor2025/"
        "famload_lane_report.json).")
    man = PB.stage_batch(files, control_from=base, manifest_override=PROBES_JSON, note=note)
    print(f"[lane] STAGED batch {man['batch']}: "
          + ", ".join(os.path.basename(e['staged_as'] or e['file']) for e in man['entries']))
    print("[lane] READY -- stop here; a human uploads control-first and records verdicts.")
    return man


def main(argv: List[str]) -> int:
    cmd = argv[0] if argv else "all"
    if cmd == "build":
        rep = build()
        return 0 if rep["all_pass"] else 1
    if cmd == "stage":
        stage()
        return 0
    if cmd == "all":
        rep = build()
        if not rep["all_pass"]:
            print("[lane] NOT staging: a probe failed its gates")
            return 1
        stage()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
