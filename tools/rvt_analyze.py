#!/usr/bin/env python3
"""rvt_analyze.py -- ONE-SHOT analysis report for any .rvt / .rfa / .rft.

The debugging front door: everything the separate instruments report about
one document, in one command and one JSON --

* identity      -- BasicFileInfo (format/build/save path), release year,
                   unique document GUID, whether the identity is OURS
                   (rvt-writer) or foreign;
* schema        -- the file's own ``Formats/Latest`` signature (sha256,
                   size, release match, corpus-constant?);
* container     -- OLE streams with sizes, partition streams;
* census        -- element-class histogram of the host document, save
                   units, host families with/without embedded documents,
                   the three-way content COHERENCE tuple (Bug-B metric);
* validation    -- the certified layered validator, family/project mode
                   picked from the stream set (PartAtom => family);
* provenance    -- for our-authored files: the famgen provenance scan
                   (zero-donor-bytes checks) when ``--provenance`` is given.

Usage::

    python tools/rvt_analyze.py FILE.rvt [--json out.json] [--top 25]
        [--no-census] [--no-validate] [--provenance] [--quiet]

Read-only; never modifies the input.  Works from a fresh clone (bundled
schema/base fallbacks) and inside the plugin (same engine).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _identity(path: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.versions import detect_release
    out: Dict[str, Any] = {"path": os.path.abspath(path),
                           "bytes": os.path.getsize(path)}
    with open_rvt(path) as f:
        names = [s.name for s in f.streams()]
        out["kind"] = "family" if "PartAtom" in names else "project"
        raw_bfi = f.raw("BasicFileInfo") if "BasicFileInfo" in names else b""
    try:
        out["release"] = detect_release(path)
    except Exception as ex:                                   # noqa: BLE001
        out["release"] = None
        out["release_error"] = repr(ex)
    try:
        from rvt.identity import DEFAULT_AUTHOR, identity_report
        idr = identity_report(raw_bfi)
        out["basic_file_info"] = {
            k: idr.get(k) for k in ("author", "client_app_name", "format",
                                    "build", "username", "last_save_path",
                                    "locale", "unique_document_guid")
            if idr.get(k)}
        out["identity_ours"] = (idr.get("author") == DEFAULT_AUTHOR
                                or idr.get("client_app_name") == DEFAULT_AUTHOR)
    except Exception as ex:                                   # noqa: BLE001
        out["basic_file_info"] = {"error": repr(ex)}
    return out


def _schema_identity(path: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    from rvt.versions import detect_release_from_schema
    with open_rvt(path) as f:
        blob = f.inflate("Formats/Latest", 0)
    return {"bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "release": detect_release_from_schema(blob)}


def _container(path: str) -> Dict[str, Any]:
    from rvt.container import open_rvt
    with open_rvt(path) as f:
        streams = {s.name: s.size for s in f.streams()}
        parts = f.partition_streams()
    return {"n_streams": len(streams), "streams": streams,
            "partition_streams": list(parts)}


def _validate(path: str, kind: str) -> Dict[str, Any]:
    from rvt.validate import validate_file
    fam = kind == "family"
    rep = validate_file(path, family=fam)
    return {"mode": "family" if fam else "project",
            "verdict": "VALID" if rep.ok else "INVALID",
            "n_errors": len(rep.errors), "n_warnings": len(rep.warnings),
            "errors": [f"[{f.layer}] {f.where}: {f.message}"
                       for f in rep.errors[:12]],
            "warnings": [f"[{f.layer}] {f.where}: {f.message}"
                         for f in rep.warnings[:12]],
            "pages_checked": rep.stats.get("pages_checked")}


def analyze(path: str, *, top: int = 25, with_census: bool = True,
            with_validate: bool = True, with_provenance: bool = False
            ) -> Dict[str, Any]:
    """The full analysis dict (each section independent; a section that
    cannot run records its error instead of killing the report)."""
    rep: Dict[str, Any] = {"tool": "tools/rvt_analyze.py", "schema_version": 1}
    rep["identity"] = _identity(path)
    kind = rep["identity"].get("kind", "project")
    for name, fn in (("schema", lambda: _schema_identity(path)),
                     ("container", lambda: _container(path))):
        try:
            rep[name] = fn()
        except Exception as ex:                               # noqa: BLE001
            rep[name] = {"error": repr(ex)}
    if with_census:
        try:
            from rvt.census import census
            c = census(path)
            classes = c.get("classes") or {}
            rep["census"] = {
                "host_records": c.get("host_records"),
                "n_classes": c.get("n_classes"),
                "top_classes": dict(list(classes.items())[:top]),
                "units": c.get("units"),
                "families": {k: v for k, v in (c.get("families") or {}).items()
                             if not k.startswith("names_")},
                "family_names_with_document":
                    (c.get("families") or {}).get("names_with_document"),
                "coherence": c.get("coherence"),
                "elemtable_rows": c.get("elemtable_rows"),
            }
        except Exception as ex:                               # noqa: BLE001
            rep["census"] = {"error": repr(ex)}
    if with_validate:
        try:
            rep["validation"] = _validate(path, kind)
        except Exception as ex:                               # noqa: BLE001
            rep["validation"] = {"error": repr(ex)}
    if with_provenance and kind == "family":
        try:
            from rvt.famgen import factory as F
            rep["provenance"] = F.provenance_scan(path)
        except Exception as ex:                               # noqa: BLE001
            rep["provenance"] = {"error": repr(ex)}
    return rep


def _print_text(rep: Dict[str, Any]) -> None:
    ident = rep.get("identity") or {}
    bfi = ident.get("basic_file_info") or {}
    print("=" * 66)
    print(f"  {os.path.basename(ident.get('path', '?'))}   "
          f"({ident.get('kind')}, {ident.get('bytes', 0) / 1e6:.1f} MB)")
    print("=" * 66)
    print(f"release        : {ident.get('release')}   "
          f"(format {bfi.get('format')}, build {bfi.get('build')})")
    print(f"identity ours  : {ident.get('identity_ours')}   "
          f"(author {bfi.get('author')!r})")
    if bfi.get("unique_document_guid"):
        print(f"document guid  : {bfi.get('unique_document_guid')}")
    sch = rep.get("schema") or {}
    print(f"schema         : {sch.get('bytes')} bytes, release "
          f"{sch.get('release')}, sha {str(sch.get('sha256'))[:16]}..")
    cont = rep.get("container") or {}
    print(f"container      : {cont.get('n_streams')} streams, "
          f"{len(cont.get('partition_streams') or [])} partition stream(s)")
    cen = rep.get("census") or {}
    if cen and "error" not in cen:
        u = cen.get("units") or {}
        fams = cen.get("families") or {}
        print(f"census         : {cen.get('host_records')} host records in "
              f"{cen.get('n_classes')} classes; units total={u.get('total')} "
              f"family-docs={u.get('family_documents')}")
        print(f"families       : {fams.get('host_families')} host families "
              f"({fams.get('with_document')} with embedded document)")
        coh = cen.get("coherence") or {}
        print(f"coherence      : {'OK' if coh.get('coherent') else 'BROKEN'} "
              f"(ContentDocuments={coh.get('content_documents_entries')}, "
              f"units={coh.get('embedded_units')}, "
              f"ContentTable={coh.get('content_table_records')})")
        top = cen.get("top_classes") or {}
        head = ", ".join(f"{k}x{v}" for k, v in list(top.items())[:8])
        print(f"top classes    : {head}")
    val = rep.get("validation") or {}
    if val:
        print(f"validation     : {val.get('verdict')} "
              f"({val.get('n_errors')} errors, {val.get('n_warnings')} "
              f"warnings, {val.get('mode')} mode)")
        for e in (val.get("errors") or [])[:6]:
            print(f"    ERROR  {e}")
        for w in (val.get("warnings") or [])[:4]:
            print(f"    warn   {w}")
    prov = rep.get("provenance") or {}
    if prov:
        print(f"provenance     : ok={prov.get('ok')}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="rvt_analyze",
        description="one-shot analysis report for a .rvt/.rfa/.rft")
    ap.add_argument("path")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="write the full report as JSON")
    ap.add_argument("--top", type=int, default=25,
                    help="class-histogram entries to keep (default 25)")
    ap.add_argument("--no-census", action="store_true")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--provenance", action="store_true",
                    help="famgen provenance scan (family files)")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress the text report (JSON only)")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.path):
        print(f"error: no such file: {a.path}", file=sys.stderr)
        return 2
    rep = analyze(a.path, top=a.top, with_census=not a.no_census,
                  with_validate=not a.no_validate,
                  with_provenance=a.provenance)
    if not a.quiet:
        _print_text(rep)
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump(rep, fh, indent=1, default=str)
        if not a.quiet:
            print(f"report -> {a.json_out}")
    val = rep.get("validation") or {}
    return 0 if (val.get("n_errors") in (0, None)) else 1


if __name__ == "__main__":
    sys.exit(main())
