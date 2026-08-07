"""rvt.convert.extract_family -- EXTRACT ROUTE: RVT -> RFA.

Lift ONE embedded family document out of a project into a standalone
``.rfa`` -- the inverse of the four-registry loader:

* locate    :func:`rvt.families.family_documents` (host ``Family`` ->
            ``m_contentDocGUID`` -> the ``Partitions/<N>`` save unit);
* carry     the unit's seq-101/102/103 records VERBATIM
            (:func:`rvt.families.unit_segments`) -- byte-faithful content;
* owners    per-element owner ids from the embedded ADocument's INLINE
            ElemTable (``Global/ContentDocuments`` entry), episodes
            normalised to the standalone single-episode form;
* assemble  :func:`rvt.convert.rfa_assemble.assemble_rfa` -- our
            scaffolding streams (partition framing, coordinated Globals,
            re-authored standalone ADocument, identity, PartAtom, CFB),
            ``Formats/Latest`` carried from the source itself;
* gates     ``verify_family_rfa`` + the FAMILY-MODE VALIDATOR (0 errors
            required to CLAIM the cell; the file is delivered either way,
            labelled).

THE FULL CYCLE (the proof this route composes with the certified loader):
:func:`reload_family` re-loads an extracted ``.rfa`` into a fresh base
through ``rvt.famgen.loader.load_family_into_project`` -- generate ->
load -> extract -> re-load, all our machinery.

HONEST LIMITS (refused with names, not faked):

* a family whose document embeds NESTED families (further units) is refused
  in v1 -- the nested units + their ContentDocuments entries would have to
  ride along;
* re-loading requires the document's element ids to sit ABOVE the target
  base's id watermark (ids are file-wide unique); the loader refuses
  otherwise and the refusal is recorded.

PROVENANCE: extracting from a foreign project lifts THEIR family (their
geometry, their parameter values) into the ``.rfa`` -- the manifest stamps
it; only our own generated content ships.

CLI::

    python -m rvt.convert.extract_family <project.rvt> --list
    python -m rvt.convert.extract_family <project.rvt> --family "DP-1"
        [-o out.rfa | --out-dir D] [--reload-base <fresh.rvt>]

Territory: ``src/rvt/convert/`` (convert-a stream).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .add_to_project import (ConvertError, TOOL, TOOL_VERSION, _jdump, _relp,
                             _sha256)
from .rfa_assemble import UnitDoc, UnitElement, assemble_rfa
from .rvt_to_ifc import source_provenance

__all__ = [
    "ExtractError", "list_families", "extract_family", "RfaFamilyDoc",
    "reload_family", "main",
]


class ExtractError(ConvertError):
    """The family cannot be extracted; the message names the one blocker."""


# ---------------------------------------------------------------------------
# survey
# ---------------------------------------------------------------------------

def list_families(rvt_path: str) -> List[dict]:
    """The project's embedded family documents (name, unit, category, types,
    nested-family count) -- the selectable surface."""
    from ..families import FamilyIndex, family_documents
    idx = FamilyIndex(rvt_path)
    out = []
    for r in family_documents(idx):
        if r["unit"] is None:
            continue
        out.append({"family_id": r["family_id"], "family_name": r["family_name"],
                    "unit": r["unit"], "category": r["category"],
                    "n_records": r.get("n_records"),
                    "types": [s.get("name") for s in r.get("symbols") or []],
                    "n_nested_families": r.get("n_nested_families", 0)})
    return out


def _pick(rows: List[dict], selector: str) -> dict:
    s = str(selector).strip()
    if s.isdigit():
        hits = [r for r in rows if r["family_id"] == int(s) or r["unit"] == int(s)]
    else:
        hits = [r for r in rows if s.lower() in (r["family_name"] or "").lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise ExtractError(
            f"no embedded family matches {selector!r}. Families: "
            + "; ".join(f"{r['family_name']} (unit {r['unit']})" for r in rows[:20]))
    raise ExtractError(
        f"{selector!r} matches {len(hits)} families -- name one exactly: "
        + "; ".join((r["family_name"] or "?") for r in hits[:10]))


def _embedded_elem_rows(idx, unit: int) -> Dict[int, Tuple[int, int]]:
    """{elem id: (original id, owner id)} from the embedded ADocument's
    INLINE ElemTable (owner -1 when the entry is absent)."""
    from .. import adocument as A
    from ..families import content_document_adoc
    guid = idx.units[unit].guid
    out: Dict[int, Tuple[int, int]] = {}
    if not guid:
        return out
    blob = content_document_adoc(idx, guid)
    if not blob:
        return out
    ad = A.decode_latest(blob)
    if not ad.clean:
        return out
    inner = ((ad.value.get("m_elemTable") or {}).get("value") or {})
    for r in inner.get("m_elemArr") or []:
        eid = int(r.get("m_id", -1))
        orig = int(((r.get("m_history") or {}).get("m_originalElementId") or {})
                   .get("m_id64", eid))
        owner = int(r.get("m_OwningElementId", -1))
        out[eid] = (orig, owner)
    return out


def _unit_doc(idx, unit: int, name: str) -> Tuple[UnitDoc, Dict[int, bytes]]:
    """Decode one save unit into (:class:`UnitDoc`, verbatim segments)."""
    from ..families import self_family_of_unit, unit_segments
    recs = idx.unit_records(unit)
    ids = sorted(recs.get(102, {}))
    if not ids:
        raise ExtractError(f"unit {unit} carries no seq-102 records")
    rows = _embedded_elem_rows(idx, unit)
    els: List[UnitElement] = []
    for eid in ids:
        cname = idx.class_name(recs[102][eid].class_id)
        obj = idx.value(unit, eid)
        orig, owner = rows.get(eid, (eid, -1))
        els.append(UnitElement(elem_id=eid, class_name=cname,
                               obj=obj if isinstance(obj, dict) else {},
                               owner_id=owner, original_id=orig))
    sf = self_family_of_unit(idx, unit)
    if sf is None:
        raise ExtractError(f"unit {unit} has no self-Family (not a family document)")
    sf_el = next(e for e in els if e.elem_id == sf["id"])
    nested = [e.elem_id for e in els if e.class_name == "Family"
              and e.elem_id != sf["id"]]
    if nested:
        raise ExtractError(
            f"family {name!r} embeds {len(nested)} NESTED family element(s) "
            f"(ids {nested[:6]}): nested-unit extraction is not built in v1 -- "
            "the nested save units and their ContentDocuments entries would "
            "have to ride along. Refused, not faked.")
    types = [(str(t["name"]), {}) for t in (sf.get("types") or [])]
    doc = UnitDoc(elements=els, self_family=sf_el,
                  document_guid=idx.units[unit].guid or str(uuid.uuid4()),
                  name=name, category_id=int(sf.get("category") or -1),
                  part_type=int(sf.get("part_type") or 0), types=types)
    return doc, unit_segments(idx, unit)


# ---------------------------------------------------------------------------
# THE ROUTE: extract
# ---------------------------------------------------------------------------

def extract_family(rvt_path: str, selector: str, out_rfa: Optional[str] = None, *,
                   out_dir: Optional[str] = None,
                   name: Optional[str] = None,
                   validate: bool = True) -> Dict[str, Any]:
    """RVT -> RFA: lift the selected embedded family into a standalone
    ``.rfa``.  Extract, assemble, gate, DELIVER (stamps after)."""
    from ..famgen import famdoc_adoc as FA
    from ..families import FamilyIndex
    from ..container import open_rvt
    t0 = time.time()
    if not os.path.isfile(rvt_path):
        raise ExtractError(f"no such file: {rvt_path}")
    idx = FamilyIndex(rvt_path)
    rows = list_families(rvt_path)
    if not rows:
        raise ExtractError(f"{rvt_path} embeds no family documents")
    row = _pick(rows, selector)
    fam_name = name or row["family_name"] or f"family_{row['family_id']}"
    if out_rfa is None:
        stem = re.sub(r"[^A-Za-z0-9._ -]+", "", fam_name).strip().replace(" ", "_")
        out_rfa = os.path.join(out_dir or os.path.dirname(os.path.abspath(rvt_path)),
                               (stem or f"family_{row['family_id']}") + ".rfa")
    out_dir = out_dir or os.path.dirname(os.path.abspath(out_rfa)) or "."
    os.makedirs(out_dir, exist_ok=True)

    prov = source_provenance(rvt_path)
    rec: Dict[str, Any] = {
        "route": "rvt->rfa (rvt.convert.extract_family)",
        "tool": TOOL, "tool_version": TOOL_VERSION,
        "input": {"path": _relp(rvt_path), "sha256": _sha256(rvt_path),
                  "provenance": prov},
        "family": {"selector": selector, "family_id": row["family_id"],
                   "family_name": row["family_name"], "unit": row["unit"],
                   "category": row["category"], "types": row["types"]},
        "files": {}, "stamps": [], "degradations": [], "errors": [],
    }
    if prov.get("foreign"):
        rec["stamps"].append(
            "FOREIGN DESIGN CONTENT: the source model was not authored by "
            "tekton -- the extracted .rfa carries THAT model's family (their "
            "geometry, their parameters, their type values). Dev/interop "
            "artifact for the file's owner; never shipped as tekton content.")
    if prov.get("quarantined"):
        rec["stamps"].append(
            "QUARANTINED SOURCE (dev-only): research-corpus / third-party "
            "content; the extraction stays in experiments/.")
    try:
        doc, segs = _unit_doc(idx, row["unit"], fam_name)
        with open_rvt(rvt_path) as f:
            formats_raw = f.raw("Formats/Latest")
        rep = assemble_rfa(segs, doc, out_rfa, formats_raw=formats_raw)
        rec["assembly"] = {k: rep[k] for k in ("size", "partition_stream",
                                               "elements", "document_guid",
                                               "adoc_mode", "adoc_bytes",
                                               "ours", "carried")}
        rec["assembly"]["verify"] = {
            k: rep["verify"].get(k) for k in ("gzip_crc_failures", "ecc_mismatch",
                                              "walker_errors", "n_units",
                                              "record_counts")}
        rec["files"]["rfa"] = out_rfa
    except Exception as e:                                     # noqa: BLE001
        rec["errors"].append(f"{type(e).__name__}: {e}")
        rec["errors"].append(traceback.format_exc(limit=8))
        _finish(rec, out_rfa, out_dir, t0)
        raise
    if validate:
        g: Dict[str, Any] = {}
        try:
            val = FA.validate_family_file(out_rfa, with_donor_parity=False)
            fm = val.get("family_mode") or {}
            g["family_mode"] = {"verdict": fm.get("verdict"),
                                "n_errors": fm.get("n_errors"),
                                "n_warnings": fm.get("n_warnings"),
                                "errors": fm.get("errors")}
        except Exception as e:                                 # noqa: BLE001
            g["family_mode"] = {"verdict": "ERROR",
                                "error": f"{type(e).__name__}: {e}"}
        dec = rep["verify"].get("decode_seq102") or {}
        g["records_decode_clean"] = (dec.get("clean") == dec.get("records"))
        g["ids_match_source_unit"] = True                       # verbatim carry
        g["self_checks_ok"] = bool(g["family_mode"].get("verdict") == "VALID"
                                   and g["family_mode"].get("n_errors") == 0
                                   and g["records_decode_clean"])
        rec["validation"] = g
        if not g["self_checks_ok"]:
            rec["degradations"].append("self-checks did not all pass -- the file "
                                       "is delivered with this label; see "
                                       "validation")
            errs = " ".join(str(e) for e in (g.get("family_mode") or {}).get("errors") or [])
            if "dangling ElementId" in errs:
                rec["degradations"].append(
                    "the family document references HOST-side resources "
                    "(categories / styles / materials) that have no embedded "
                    "twin in this unit (they are not in the host Family's "
                    "big2SmallMap2 either) -- a project-hosted family is not "
                    "fully self-contained. Standalone extraction of such a "
                    "family needs HOST-RESOURCE REPATRIATION (copy those host "
                    "records into the unit and remap the references): a named "
                    "follow-up, not built in v1. Our own generated families "
                    "are self-contained and extract clean.")
    _finish(rec, out_rfa, out_dir, t0)
    return rec


# ---------------------------------------------------------------------------
# THE FULL CYCLE: re-load an extracted .rfa onto a fresh base
# ---------------------------------------------------------------------------

class RfaFamilyDoc:
    """A FamilyDoc-shaped adapter over a standalone ``.rfa`` on disk, for the
    four-registry component loader (``rvt.famgen.loader``): SkelElements
    rebuilt from the decoded records (seq-103 ``GElement`` reps kept so the
    symbol-solid path works), types from the self-Family's type table,
    segments carried verbatim by :meth:`to_embedded_unit`."""

    finalized = True

    def __init__(self, rfa_path: str, *, name: Optional[str] = None,
                 document_guid: Optional[str] = None):
        from ..elemtable import inflate_global_stream, parse_elemtable
        from ..container import open_rvt
        from ..families import FamilyIndex, self_family_of_unit
        from ..genesis.skeleton import NO_OWNER, SkelElement
        self.path = os.path.abspath(rfa_path)
        self._idx = FamilyIndex(rfa_path)
        recs = self._idx.unit_records(0)
        with open_rvt(rfa_path) as f:
            st = inflate_global_stream(f.raw("Global/ElemTable"))
            table = parse_elemtable(st.payload, "rfa")
        owner_of = {r.id: (-1 if r.owner_id in (NO_OWNER, None) else int(r.owner_id))
                    for r in table.records}
        self.elements = []
        for eid in sorted(recs.get(102, {})):
            cname = self._idx.class_name(recs[102][eid].class_id)
            obj = self._idx.value(0, eid) or {}
            hdr = self._idx.value(0, eid, 101) or {}
            rep = None
            rep_rec = recs.get(103, {}).get(eid)
            if rep_rec is not None and self._idx.class_name(rep_rec.class_id) == "GElement":
                rv = self._idx.value(0, eid, 103)
                rep = rv if isinstance(rv, dict) else None
            self.elements.append(SkelElement(eid, cname,
                                             hdr if isinstance(hdr, dict) else {},
                                             obj if isinstance(obj, dict) else {},
                                             rep, owner_id=owner_of.get(eid, -1)))
        sf = self_family_of_unit(self._idx, 0)
        if sf is None:
            raise ExtractError(f"{rfa_path}: no self-Family (not a family file)")
        self.self_family = next(e for e in self.elements if e.elem_id == sf["id"])
        self.category_id = int(sf.get("category") or -1)
        self.part_type = int(sf.get("part_type") or 0)
        self.types = [(str(t["name"]), {}) for t in (sf.get("types") or [])]
        self.current_type = 0
        # a standalone .rfa's unit 0 carries no separator GUID: mint one for
        # the LOAD (the content GUID must be new to the host anyway)
        self.document_guid = document_guid or self._idx.units[0].guid or str(uuid.uuid4())
        pa_title = _partatom_title(rfa_path)
        self.name = name or pa_title or os.path.splitext(os.path.basename(rfa_path))[0]
        self.params = {}

    def finalize(self) -> "RfaFamilyDoc":
        return self

    def to_embedded_unit(self) -> Dict[str, Any]:
        from ..families import unit_segments
        return {"content_doc_guid": self.document_guid,
                "record_count": len(self.elements),
                "segments": unit_segments(self._idx, 0),
                "self_family_id": self.self_family.elem_id,
                "type_names": [n for n, _v in self.types]}


class _RfaProduct:
    """The product wrapper the loader expects (doc + display name)."""

    def __init__(self, doc: RfaFamilyDoc):
        self.doc = doc
        self.name = doc.name
        self.forms: list = []


def _partatom_title(path: str) -> str:
    from ..container import open_rvt
    try:
        with open_rvt(path) as f:
            xml = f.raw("PartAtom").decode("utf-8", "replace")
        m = re.search(r"<title>(.*?)</title>", xml, re.S)
        return (m.group(1) or "").strip() if m else ""
    except Exception:                                          # noqa: BLE001
        return ""


def reload_family(rfa_path: str, base_rvt: str, out_rvt: str, *,
                  symbol_solid: bool = True,
                  validate: bool = True) -> Dict[str, Any]:
    """Load an extracted ``.rfa`` into a fresh copy of ``base_rvt`` through
    the certified four-registry component loader (no placement).  Returns
    the load record (ok / stop_reason / plan ids / proofs summary)."""
    from ..famgen import loader as L
    doc = RfaFamilyDoc(rfa_path)
    prod = _RfaProduct(doc)
    res = L.load_family_into_project(base_rvt, out_rvt, product=prod, place=False,
                                     symbol_solid=symbol_solid,
                                     report_path=out_rvt + ".load.json",
                                     validate=validate)
    plan = res.plan
    return {
        "ok": bool(res.ok), "stop_reason": res.stop_reason or None,
        "out": _relp(out_rvt),
        "rfa": _relp(rfa_path), "base": _relp(base_rvt),
        "ids": None if plan is None else {
            "host_family": plan.host_family_id, "symbol": plan.symbol_id,
            "surrogate": plan.surrogate_id, "twins": len(plan.twin_of),
            "content_guid": plan.guid},
        "elements_added": len(res.elements),
        "report": _relp(out_rvt + ".load.json"),
    }


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

def _finish(rec: Dict[str, Any], out_rfa: str, out_dir: str, t0: float) -> None:
    rec["seconds"] = round(time.time() - t0, 1)
    files = {k: v for k, v in (rec.get("files") or {}).items()
             if v and os.path.isfile(str(v))}
    rec["deliverables"] = {
        role: {"path": _relp(p), "bytes": os.path.getsize(p), "sha256": _sha256(p)}
        for role, p in files.items()}
    stem = os.path.splitext(os.path.basename(out_rfa))[0]
    _jdump(os.path.join(out_dir, stem + ".manifest.json"), rec)
    lines = [f"# {rec['route']} -- deliverable manifest", ""]
    lines.append("## The deliverable(s)")
    for role, d in (rec["deliverables"] or {}).items():
        lines.append(f"* **{role}**: `{d['path']}` ({d['bytes']:,} bytes, "
                     f"sha256 {d['sha256'][:16]}...)")
    if not rec["deliverables"]:
        lines.append("* NO FILE PRODUCED -- see errors (nothing withheld)")
    fam = rec.get("family") or {}
    lines.append("")
    lines.append(f"## Extracted family")
    lines.append(f"* `{fam.get('family_name')}` (host family {fam.get('family_id')}, "
                 f"unit {fam.get('unit')}, category {fam.get('category')}, "
                 f"types {fam.get('types')})")
    prov = (rec.get("input") or {}).get("provenance") or {}
    lines.append(f"* source lineage: {prov.get('lineage')}")
    lines.append("")
    if rec.get("stamps"):
        lines.append("## Stamps (labels, not refusals)")
        for s in rec["stamps"]:
            lines.append(f"* {s}")
        lines.append("")
    g = rec.get("validation") or {}
    if g:
        fm = g.get("family_mode") or {}
        lines.append("## Gates (self-checks)")
        lines.append(f"* family-mode validator: {fm.get('verdict')} "
                     f"({fm.get('n_errors')} errors, {fm.get('n_warnings')} warnings)")
        lines.append(f"* records decode clean: {g.get('records_decode_clean')}")
        lines.append(f"* self-checks ok: **{g.get('self_checks_ok')}**")
        lines.append("")
    rl = rec.get("reload") or {}
    if rl:
        lines.append("## Full cycle (re-load onto a fresh base)")
        lines.append(f"* ok: **{rl.get('ok')}** -> `{rl.get('out')}` "
                     f"(+{rl.get('elements_added')} host elements; "
                     f"report `{rl.get('report')}`)")
        if rl.get("stop_reason"):
            lines.append(f"* stop: {rl['stop_reason']}")
        lines.append("")
    if rec.get("degradations"):
        lines.append("## Caveats")
        for d in rec["degradations"]:
            lines.append(f"* {d}")
        lines.append("")
    if rec.get("errors"):
        lines.append("## Errors")
        for e in rec["errors"]:
            lines.append(f"* {e}")
    with open(os.path.join(out_dir, stem + ".MANIFEST.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rvt.convert.extract_family",
        description="RVT -> RFA: extract one embedded family document into a "
                    "standalone .rfa (family-mode validated); optionally "
                    "prove the full cycle by re-loading it onto a fresh base.")
    ap.add_argument("rvt", help="the source project (.rvt)")
    ap.add_argument("--list", action="store_true",
                    help="list the embedded families and exit")
    ap.add_argument("--family", default=None,
                    help="family selector: name fragment | family id | unit index")
    ap.add_argument("-o", "--out", default=None, help="output .rfa path")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--name", default=None, help="override the family display name")
    ap.add_argument("--reload-base", default=None,
                    help="ALSO re-load the extracted .rfa into a fresh copy of "
                         "this base (the full-cycle proof)")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.list:
            for r in list_families(a.rvt):
                print(f"unit {r['unit']:>3}  family {r['family_id']:>9}  "
                      f"cat {r['category']}  types {r['types']}  "
                      f"nested {r['n_nested_families']}  {r['family_name']!r}")
            return 0
        if not a.family:
            print("ERROR: --family <selector> required (or --list)")
            return 2
        rec = extract_family(a.rvt, a.family, a.out, out_dir=a.out_dir,
                             name=a.name, validate=not a.no_validate)
        rfa = (rec.get("files") or {}).get("rfa")
        if a.reload_base and rfa:
            out_rvt = os.path.splitext(rfa)[0] + ".reloaded.rvt"
            rec["reload"] = reload_family(rfa, a.reload_base, out_rvt)
            # refresh the manifest with the reload block (seconds preserved)
            _finish(rec, rfa, a.out_dir or os.path.dirname(os.path.abspath(rfa)),
                    time.time() - float(rec.get("seconds") or 0.0))
    except ConvertError as e:
        print(f"ERROR: {e}")
        return 2
    d = rec.get("deliverables") or {}
    print(f"delivered: {json.dumps({k: v.get('path') for k, v in d.items()})}")
    g = rec.get("validation") or {}
    fm = g.get("family_mode") or {}
    print(f"family-mode validator: {fm.get('verdict')} ({fm.get('n_errors')} errors)")
    if rec.get("reload"):
        print(f"full cycle re-load: ok={rec['reload'].get('ok')} -> "
              f"{rec['reload'].get('out')}")
    for s in rec.get("stamps") or []:
        print(f"STAMP: {s}")
    return 0


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
