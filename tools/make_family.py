#!/usr/bin/env python3
"""make_family.py -- generate a Revit FAMILY (.rfa) from a job spec.

The command-line front door to the asset factory (``rvt.famgen.factory``):
facts (manufacturer dimensions / ratings, provenance-tagged) -> our family
document (skeleton + geometry + electrical connectors) -> a validated
``.rfa`` + a JSON report (facts, verify, validate, provenance ledger).

Usage::

    python tools/make_family.py panelboard --vendor eaton --line pow-r-line \
        --mains 400 --spaces 42 --voltage 480Y/277 --mcb --mounting surface \
        -o experiments/families/factory/eaton_prl_400A_42sp_480Y.rfa

    python tools/make_family.py transformer --kva 75 --primary 480 \
        --secondary 208Y/120 -o out/xfmr_75kVA.rfa

    python tools/make_family.py luminaire --kind recessed-troffer --size 2x4 \
        --wattage 38 --lumens 4600 --cct 4000 --voltage 120-277 \
        -o out/troffer_2x4.rfa

    python tools/make_family.py proofs            # the three proof families
    python tools/make_family.py provenance <file.rfa>
    python tools/make_family.py loader            # loader readiness (no file)

Exit code 0 = the file emitted, verified, validated (0 errors, family mode)
and provenance-clean.  ``--json`` prints the machine-readable report; the
report is always also written beside the output as ``<stem>.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from rvt.famgen import factory as F                            # noqa: E402


def _print_report(rep: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(rep, indent=1, default=str))
        return
    fam = rep.get("family") or {}
    print(f"family      : {fam.get('family_name')}  [{fam.get('category')}, "
          f"part type {fam.get('part_type')}]")
    print(f"types       : {fam.get('types')}")
    print(f"parameters  : {len(fam.get('parameters') or [])} "
          f"({', '.join((fam.get('parameters') or [])[:8])}...)")
    forms = fam.get("forms") or []
    if forms:
        f0 = forms[0]
        dims = [f0.get(k) for k in ("width_ft", "depth_ft", "height_ft")]
        if all(isinstance(x, (int, float)) for x in dims):
            print(f"geometry    : {f0.get('kind')} "
                  f"{dims[0]*12:.2f} x {dims[1]*12:.2f} x {dims[2]*12:.2f} in "
                  f"(rep={f0.get('rep')})")
    print(f"connectors  : {fam.get('connectors')}")
    if fam.get("unverified_fields"):
        print(f"UNVERIFIED  : {fam.get('unverified_fields')} "
              "(assumed / user-given -- surfaced, not silently trusted)")
    v = rep.get("verify") or {}
    print(f"verify      : ok={v.get('ok')} crc_fail={v.get('gzip_crc_failures')} "
          f"ecc_mismatch={v.get('ecc_mismatch')} "
          f"decode={ (v.get('decode_seq102') or {}).get('clean') }/"
          f"{ (v.get('decode_seq102') or {}).get('records') }")
    val = (rep.get("validate") or {}).get("family_mode") or {}
    if val:
        print(f"validate    : {val.get('verdict')} ({val.get('n_errors')} errors, "
              f"{val.get('n_warnings')} warnings)")
    prov = rep.get("provenance") or {}
    if prov:
        print(f"provenance  : ok={prov.get('ok')} checks={prov.get('checks')}")
    print(f"report      : {rep.get('report_path')}")
    print(f"RESULT      : {'OK' if rep.get('ok') else 'NEEDS ATTENTION'} -> {rep.get('path')}")


def cmd_panelboard(ns) -> int:
    prod = F.make_panelboard(vendor=ns.vendor, line=ns.line, mains_a=ns.mains,
                              spaces=ns.spaces, voltage=ns.voltage, mcb=ns.mcb,
                              mounting=ns.mounting, panel_name=ns.name,
                              sccr_ka=ns.sccr, neutral_rating=ns.neutral,
                              solid=not ns.dummy)
    out = ns.output or os.path.join(F.FACTORY_OUT, prod.file_stem + ".rfa")
    rep = prod.write(out, validate=not ns.no_validate)
    _print_report(rep, ns.json)
    return 0 if rep["ok"] else 1


def cmd_transformer(ns) -> int:
    prod = F.make_transformer(kva=ns.kva, vendor=ns.vendor, primary_v=ns.primary,
                              secondary_v=ns.secondary, solid=not ns.dummy)
    out = ns.output or os.path.join(F.FACTORY_OUT, prod.file_stem + ".rfa")
    rep = prod.write(out, validate=not ns.no_validate)
    _print_report(rep, ns.json)
    return 0 if rep["ok"] else 1


def cmd_luminaire(ns) -> int:
    prod = F.make_luminaire(kind=ns.kind, size=ns.size, wattage=ns.wattage,
                            lumens=ns.lumens, cct=ns.cct, voltage=ns.voltage,
                            aperture_in=ns.aperture, solid=not ns.dummy)
    out = ns.output or os.path.join(F.FACTORY_OUT, prod.file_stem + ".rfa")
    rep = prod.write(out, validate=not ns.no_validate)
    _print_report(rep, ns.json)
    return 0 if rep["ok"] else 1


def cmd_proofs(ns) -> int:
    return F.main([] if not ns.no_validate else ["--no-validate"])


def cmd_provenance(ns) -> int:
    rep = F.provenance_scan(ns.path)
    print(json.dumps(rep, indent=1, default=str))
    return 0 if rep.get("ok") else 1


def cmd_load(ns) -> int:
    from rvt.famgen import loader as L
    host = ns.host or L.DEFAULT_HOST
    ctx = L.survey_host(host)
    prod = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=ns.mains,
                            spaces=ns.spaces, voltage=ns.voltage, mcb=ns.mcb,
                            mounting=ns.mounting, solid=True,
                            start_id=ctx.watermark + 1)
    res = L.load_family_into_project(host, ns.output, prod,
                                     place=not ns.no_place,
                                     symbol_solid=not ns.dummy_symbol,
                                     validate=not ns.no_validate,
                                     report_path=os.path.splitext(ns.output)[0] + ".json")
    ver = res.proofs.get("verify_written") or {}
    fam = (ver.get("family_documents") or {}).get("ours") or []
    print(json.dumps({"ok": res.ok, "out": res.out_path,
                      "validate": ver.get("validate"),
                      "family": fam, "instance": ver.get("instance"),
                      "acceptance": res.acceptance,
                      "stop_reason": res.stop_reason}, indent=1, default=str))
    print(f"report -> {res.report_path}")
    return 0 if res.ok else 1


def cmd_loader(ns) -> int:
    out = ns.output or os.path.join(F.FACTORY_OUT, "loader_readiness.json")
    rep = F.loader_readiness(host_rvt=ns.host, out_json=out)
    print(json.dumps({k: v for k, v in rep.items() if k != "spec"},
                     indent=1, default=str))
    print(f"report -> {out}")
    return 0 if rep["built_mechanisms_ok"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="make_family",
        description="Generate a Revit family (.rfa) from a job spec via the asset factory.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("panelboard", help="generate a panelboard family")
    p.add_argument("--vendor", default="eaton")
    p.add_argument("--line", default="pow-r-line")
    p.add_argument("--mains", type=float, default=400, help="mains rating (A)")
    p.add_argument("--spaces", type=int, default=42, help="branch circuit spaces")
    p.add_argument("--voltage", default="480Y/277", help="system voltage, e.g. 480Y/277")
    p.add_argument("--mcb", action="store_true", default=False,
                   help="main circuit breaker (default main lugs only)")
    p.add_argument("--mounting", default="surface", choices=["surface", "flush"])
    p.add_argument("--name", default="PANEL", help="panel schedule name value")
    p.add_argument("--sccr", type=float, default=None, help="SCCR (kA)")
    p.add_argument("--neutral", default="100%", help="neutral rating")
    p.add_argument("--dummy", action="store_true",
                   help="SerializedDummy solid rep (regeneration variant)")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-validate", action="store_true")
    p.set_defaults(func=cmd_panelboard)

    p = sub.add_parser("transformer", help="generate a dry-type transformer family")
    p.add_argument("--kva", type=float, default=75)
    p.add_argument("--vendor", default="eaton")
    p.add_argument("--primary", default="480")
    p.add_argument("--secondary", default="208Y/120")
    p.add_argument("--dummy", action="store_true")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-validate", action="store_true")
    p.set_defaults(func=cmd_transformer)

    p = sub.add_parser("luminaire", help="generate a luminaire family")
    p.add_argument("--kind", default="recessed-troffer",
                   choices=["recessed-troffer", "troffer", "downlight",
                            "recessed-downlight"])
    p.add_argument("--size", default="2x4")
    p.add_argument("--wattage", type=float, default=None)
    p.add_argument("--lumens", type=float, default=None)
    p.add_argument("--cct", type=float, default=None)
    p.add_argument("--voltage", default="120-277")
    p.add_argument("--aperture", type=float, default=None,
                   help="downlight aperture (in)")
    p.add_argument("--dummy", action="store_true")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-validate", action="store_true")
    p.set_defaults(func=cmd_luminaire)

    p = sub.add_parser("proofs", help="build the three proof families")
    p.add_argument("--no-validate", action="store_true")
    p.set_defaults(func=cmd_proofs)

    p = sub.add_parser("provenance", help="provenance-scan an existing .rfa")
    p.add_argument("path")
    p.set_defaults(func=cmd_provenance)

    p = sub.add_parser("loader", help="loader readiness report (no project file)")
    p.add_argument("--host", default=None, help="host .rvt (default: rme sample)")
    p.add_argument("-o", "--output", default=None)
    p.set_defaults(func=cmd_loader)

    p = sub.add_parser("load", help="LOAD the generated panelboard into a project (.rvt)")
    p.add_argument("-o", "--output", required=True, help="output .rvt path")
    p.add_argument("--host", default=None, help="host .rvt (default: rme sample)")
    p.add_argument("--mains", type=float, default=400)
    p.add_argument("--spaces", type=int, default=42)
    p.add_argument("--voltage", default="480Y/277")
    p.add_argument("--mcb", action="store_true", default=False)
    p.add_argument("--mounting", default="surface")
    p.add_argument("--no-place", action="store_true",
                   help="load the family without placing an instance")
    p.add_argument("--dummy-symbol", action="store_true",
                   help="leave the symbol geometry as a SerializedDummy (F4b)")
    p.add_argument("--no-validate", action="store_true")
    p.set_defaults(func=cmd_load)

    ns = ap.parse_args(argv)
    try:
        return int(ns.func(ns) or 0)
    except F.FactoryError as e:
        print(f"factory refused the job: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
