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

    python tools/make_family.py device --kind duplex-receptacle --height 18 \
        --voltage 120 --va 180 -o out/duplex.rfa    # | switch | junction-box

    python tools/make_family.py proofs            # the three proof families
    python tools/make_family.py provenance <file.rfa>
    python tools/make_family.py loader            # loader readiness (no file)

MULTI-TYPE families (one product line, a type per rating -- issue #163)::

    python tools/make_family.py panelboard --types 225,400,600 --spaces 42 \
        --voltage 480Y/277 --type-catalog -o out/prl2x_mlo.rfa
    python tools/make_family.py transformer --types 30,45,75 -o out/dt3.rfa
    python tools/make_family.py luminaire --kind recessed-troffer --types 30,38,48 \
        --cct 4000 -o out/blt_2x4.rfa

``--types`` = comma-separated catalog selectors along the product's rating
axis (mains A / kVA / input W): ONE .rfa with one type-table row per
selection (per-type dims / ratings / Model, per-type ``assumed_fields`` in
the report's ``family.type_facts``); the first is the primary type whose box
the solid is built at.  ``--type-catalog`` also writes OUR Revit type
catalog ``<stem>.txt`` beside the .rfa from the same facts.

SHARED parameters (schedules / tags bind by GUID -- issue #165)::

    python tools/make_family.py panelboard --mains 400 --spaces 42 --mcb \
        --shared-params usecases/eaton-panelboard/panelboard-shared-parameters.txt \
        -o out/prl2x_shared.rfa

``--shared-params FILE`` = OUR Revit shared-parameter TXT: every family
parameter whose caption + datatype match a ``PARAM`` row is authored SHARED
(``ParamElemExternal``) at the row's GUID, copied verbatim -- the eleven
tagging-contract parameters for the panelboard; every other parameter stays
local.  The report's ``family.shared_parameters`` lists caption -> GUID.
Without the flag every parameter is local (the historical file shape).

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


def _ensure_standalone() -> None:
    """On a machine without the research corpus (fresh clone / cloud
    session), arm the standalone resolvers: the sha-pinned bundled base
    supplies the schema AND the family container writer.  On the owner's
    machine (extracted corpus present) this is a no-op -- the research
    path stays first, bit-for-bit identical to before."""
    from rvt import schema as _RS
    if os.path.isfile(_RS.DEFAULT_PATH):
        return
    from rvt.frontdoor import standalone as SA
    SA.activate()


def _types_arg(raw) -> list:
    """``--types 225,400,600`` -> ['225', '400', '600'] (the factory parses
    each selector; '400A' / '45kVA' / '38W' spellings are fine)."""
    if not raw:
        return []
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _types_flags(p, axis: str) -> None:
    p.add_argument("--types", default=None, metavar="A,B,C",
                   help=f"multi-type family: comma-separated {axis} selectors, one "
                        "type-table row each (first = primary type / the solid's box)")
    p.add_argument("--type-catalog", action="store_true",
                   help="also write OUR Revit type catalog <stem>.txt beside the .rfa")
    p.add_argument("--shared-params", default=None, metavar="FILE",
                   help="OUR shared-parameter TXT: parameters it names are authored "
                        "SHARED at its GUIDs (schedules/tags bind by GUID); default "
                        "= every parameter local")


def _emit(prod, ns) -> dict:
    """Write the optional type catalog, the .rfa (+ report), print, return."""
    out = ns.output or os.path.join(F.FACTORY_OUT, prod.file_stem + ".rfa")
    if ns.type_catalog:
        prod.write_type_catalog(out)                  # first, so the report records it
    rep = prod.write(out, validate=not ns.no_validate)
    _print_report(rep, ns.json)
    return rep


def _print_report(rep: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(rep, indent=1, default=str))
        return
    fam = rep.get("family") or {}
    print(f"family      : {fam.get('family_name')}  [{fam.get('category')}, "
          f"part type {fam.get('part_type')}]")
    print(f"types       : {fam.get('types')}")
    type_facts = fam.get("type_facts") or []
    if len(type_facts) > 1:
        for tf in type_facts:
            print(f"              {tf.get('name')}: assumed {tf.get('assumed_fields')}")
    if fam.get("type_catalog"):
        print(f"type catalog: {fam['type_catalog'].get('path')} "
              f"({len(fam['type_catalog'].get('columns') or [])} columns)")
    print(f"parameters  : {len(fam.get('parameters') or [])} "
          f"({', '.join((fam.get('parameters') or [])[:8])}...)")
    shared = fam.get("shared_parameters") or {}
    if shared:
        print(f"shared      : {len(shared)} at OUR file's GUIDs ({', '.join(sorted(shared))})")
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
                             solid=not ns.dummy, types=_types_arg(ns.types),
                             shared_params=ns.shared_params)
    return 0 if _emit(prod, ns)["ok"] else 1


def cmd_transformer(ns) -> int:
    prod = F.make_transformer(kva=ns.kva, vendor=ns.vendor, primary_v=ns.primary,
                              secondary_v=ns.secondary, solid=not ns.dummy,
                              types=_types_arg(ns.types), shared_params=ns.shared_params)
    return 0 if _emit(prod, ns)["ok"] else 1


def cmd_luminaire(ns) -> int:
    prod = F.make_luminaire(kind=ns.kind, size=ns.size, wattage=ns.wattage,
                            lumens=ns.lumens, cct=ns.cct, voltage=ns.voltage,
                            aperture_in=ns.aperture, solid=not ns.dummy,
                            types=_types_arg(ns.types), shared_params=ns.shared_params)
    return 0 if _emit(prod, ns)["ok"] else 1


def cmd_device(ns) -> int:
    prod = F.make_device(ns.kind, mounting_height_in=ns.height, voltage=ns.voltage,
                         va=ns.va, solid=not ns.dummy, shared_params=ns.shared_params)
    return 0 if _emit(prod, ns)["ok"] else 1


def cmd_proofs(ns) -> int:
    return F.main([] if not ns.no_validate else ["--no-validate"])


def cmd_provenance(ns) -> int:
    rep = F.provenance_scan(ns.path)
    print(json.dumps(rep, indent=1, default=str))
    return 0 if rep.get("ok") else 1


#: the follow-up that owns front-door PLACEMENT of Electrical Fixtures (#166
#: shipped generation + the unplaced load; placement needs loader work)
DEVICE_PLACEMENT_FOLLOWUP = "issue #166 follow-up (Electrical Fixtures placement)"


def cmd_load_device(ns) -> int:
    """LOAD a generated device family UNPLACED through the certified
    four-registry loader (``rvt.famload`` via ``famfrom_ifc.load_into_project``
    -- the famspec -> rvt lane): the host elements carry the family's OWN
    category (Electrical Fixtures).  Default host = the pinned certified
    genesis base (bundled, runs anywhere).  Placement of this category is not
    built yet -- said out loud, never faked (rule 1: the file is delivered)."""
    from rvt.frontdoor.base import resolve_base
    from rvt.ifc import famfrom_ifc as FFI
    host = ns.host or resolve_base().path
    if not ns.no_place:
        print(f"note: placement of Electrical Fixtures is {DEVICE_PLACEMENT_FOLLOWUP}; "
              "loading UNPLACED (family + symbol + registries, no instance)", file=sys.stderr)
    kind, volt = ns.kind, ns.voltage or "120"
    probe = F.make_device(kind, mounting_height_in=ns.height, voltage=volt, va=ns.va)
    rep = FFI.load_into_project(
        host, ns.output, name=probe.file_stem,
        builder=lambda start_id=100000: F.make_device(
            kind, mounting_height_in=ns.height, voltage=volt, va=ns.va,
            start_id=start_id).doc,
        core_categories=(int(probe.doc.category_id),),
        report_path=os.path.splitext(ns.output)[0] + ".json")
    val = rep.validate_project_mode or {}
    print(json.dumps({"ok": bool(rep.ok) and val.get("verdict") == "VALID",
                      "out": rep.out_path, "host": host, "loader": rep.loader,
                      "family": probe.name, "category": "Electrical Fixtures",
                      "placed": False, "placement": DEVICE_PLACEMENT_FOLLOWUP,
                      "validate": {k: val.get(k) for k in ("verdict", "n_errors", "n_warnings")},
                      "plans": [{k: p.get(k) for k in ("family_name", "category", "host_family_id",
                                                       "symbol_ids", "unit")} for p in rep.plans],
                      "stop_reason": rep.stop_reason or rep.error}, indent=1, default=str))
    return 0 if rep.ok and val.get("verdict") == "VALID" else 1


def cmd_load(ns) -> int:
    if ns.family == "device":
        return cmd_load_device(ns)
    from rvt.famgen import loader as L
    host = ns.host or L.DEFAULT_HOST
    ctx = L.survey_host(host)
    prod = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=ns.mains,
                            spaces=ns.spaces, voltage=ns.voltage or "480Y/277", mcb=ns.mcb,
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
    _types_flags(p, "mains-rating (A)")
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
    _types_flags(p, "kVA")
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
    _types_flags(p, "input-wattage (W)")
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

    p = sub.add_parser("device", help="generate a wiring-device family (Electrical Fixtures)")
    p.add_argument("--kind", default="duplex-receptacle", choices=sorted(F.DEVICE_KINDS),
                   help="duplex-receptacle (5-15R) | duplex-receptacle-20a (5-20R) | "
                        "switch (single-pole) | junction-box (4 in square)")
    p.add_argument("--height", type=float, default=None, metavar="IN",
                   help="mounting height above the floor (in); default = the record's "
                        "convention (18 receptacle / 48 switch), flagged assumed")
    p.add_argument("--voltage", default="120", help="connector system voltage (default 120)")
    p.add_argument("--va", type=float, default=180.0,
                   help="booked connector load (VA); 180 = NEC 220.14(I) receptacle unit load")
    p.add_argument("--shared-params", default=None, metavar="FILE",
                   help="OUR shared-parameter TXT (as for the panelboard)")
    p.add_argument("--dummy", action="store_true")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-validate", action="store_true")
    p.set_defaults(func=cmd_device, types=None, type_catalog=False)

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

    p = sub.add_parser("load", help="LOAD a generated panelboard (or device) into a project (.rvt)")
    p.add_argument("-o", "--output", required=True, help="output .rvt path")
    p.add_argument("--host", default=None,
                   help="host .rvt (default: rme sample; --family device: the pinned genesis base)")
    p.add_argument("--family", default="panelboard", choices=["panelboard", "device"],
                   help="which generated family to load (device = Electrical Fixtures, "
                        "four-registry famload lane, always UNPLACED today)")
    p.add_argument("--kind", default="duplex-receptacle", choices=sorted(F.DEVICE_KINDS),
                   help="device kind (with --family device)")
    p.add_argument("--height", type=float, default=None, help="device mounting height (in)")
    p.add_argument("--va", type=float, default=180.0, help="device booked load (VA)")
    p.add_argument("--mains", type=float, default=400)
    p.add_argument("--spaces", type=int, default=42)
    p.add_argument("--voltage", default=None,
                   help="system voltage (default 480Y/277 panelboard / 120 device)")
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
        _ensure_standalone()
        return int(ns.func(ns) or 0)
    except (ValueError, OSError) as e:         # FactoryError, the skeleton's refusals, unreadable inputs
        print(f"factory refused the job: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
