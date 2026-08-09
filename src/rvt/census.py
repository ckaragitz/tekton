"""census.py -- the REQUIRED-SET CENSUS: what does EVERY reader-accepted
Revit project contain?

Positive-evidence model of the mandatory element / stream / save-unit set,
built from the files Autodesk's own reader ACCEPTS (`docs/coverage/
viewer-certified.json` 'certified') versus the ones it REJECTS ('failed'),
plus the six pristine samples.  It answers, per file:

* the element-CLASS census of the host document (unit 0 seq-102 records
  whose id is in ``Global/ElemTable``), with counts;
* the OLE stream inventory (name, raw size) and the ``Partitions`` save-unit
  KINDS (unit 0 = host document, units 1.. = embedded family documents);
* the three-way content COHERENCE tuple -- ``Global/ContentDocuments``
  entries, embedded save units, and the ADocument's
  ``ContentTable.m_ContentRecSet`` count (the Bug-B killer per orchestrator
  verdict #3 is these three disagreeing);
* the host ``Family`` census: which families have an embedded document
  (content-doc GUID -> unit) and which are document-less system families;
* the ``DBViewType`` reference finding: what each view type's ``m_famId`` /
  ``m_*AttrId`` / ``m_defaultTemplateId`` fields reference, whether the
  targets exist, and (for ``Family`` targets) whether the family has an
  embedded document.

The diff functions turn a set of censuses into the ranked table:
``mandatory_set`` (intersection of classes over every accepted file, with the
minimal count observed), ``rank_suspects`` (classes present in ALL accepted
files but absent / zero in a rejected file = Bug-A suspects for the
constructed G-files, Bug-B suspects for the R9b/R10b splices), and
``stream_unit_matrix`` (streams and save-unit kinds).

Public API::

    census(path) -> dict                       # one file
    mandatory_set(censuses) -> dict            # class -> {n_files, min, max}
    missing_from(census, mandatory) -> list    # mandatory classes absent here
    rank_suspects(passing, failing) -> dict    # per failing file, ranked
    stream_unit_matrix(censuses) -> dict
    dbviewtype_report(census) -> dict          # already inside census(...)
    run(paths...) / run_certified() -> dict    # the whole corpus at once

Demo (repo root)::

    python -m rvt.census samples/rstbasicsampleproject.rvt
    python -m rvt.census --certified                 # every certified+failed+sample
    python -m rvt.census --certified --json out.json

Everything is read-only; no file is modified.  Every file is read under its
OWN release (``rvt.global_framing.enter_own_release``: partition framing,
the ContentDocuments tokens and the ADocument decoder follow the file), so a
Revit 2025 / 2024 project is censused, not refused -- and each census
records its ``release``.  Class inventories differ per release, so the
corpus runner keeps releases apart: the top-level diff tables are the
reference (latest) release's, every other release seen gets its own entry
under ``by_release``.  A full run over the six samples + every certified /
failed file takes ~30 s (the ADocument decode of each ``Global/Latest``
dominates).
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLES_DIR = os.path.join(ROOT, "samples")
CERTIFIED_JSON = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")

SAMPLES = ("rstbasicsampleproject", "rstadvancedsampleproject", "racbasicsampleproject",
           "racadvancedsampleproject", "rmebasicsampleproject", "dach-sample-project")

#: DBViewType ElementId-valued fields we resolve (the default head / tag
#: attribute chain the reduction record §4 attributed the family floor to).
DBVIEWTYPE_REF_FIELDS = ("m_famId", "m_sectionAttrId", "m_calloutAttrId",
                         "m_elevatnAttrId", "m_defaultTemplateId",
                         "m_previewElemId", "m_pocheMatId", "m_renderStyleId")


# ---------------------------------------------------------------------------
# per-file census
# ---------------------------------------------------------------------------

def _stream_inventory(f) -> Dict[str, Any]:
    """{name: raw_size} for every OLE stream, plus partition stream names."""
    streams = {s.name: s.size for s in f.streams()}
    return {"streams": dict(sorted(streams.items())),
            "partition_streams": list(f.partition_streams())}


def _content_documents(f) -> Dict[str, Any]:
    """Global/ContentDocuments: entry count via the solved grammar (famgen)."""
    name = "Global/ContentDocuments"
    if not f.has(name):
        return {"present": False, "entries": 0, "payload_bytes": 0, "guids": []}
    payload = b"".join(f.inflate_all(name))
    out: Dict[str, Any] = {"present": True, "payload_bytes": len(payload)}
    try:
        from .famgen.factory import parse_content_documents
        entries, tail = parse_content_documents(payload)
        out.update({"entries": len(entries),
                    "guids": [g for g, _ in entries],
                    "tail_bytes": len(tail),
                    "clean_tail": len(tail) == 14})
    except Exception as ex:                                    # pragma: no cover
        out.update({"entries": None, "guids": [], "parse_error": repr(ex)})
    return out


def _adocument_facts(path: str) -> Dict[str, Any]:
    """Decode Global/Latest (the ADocument) for the coherence-relevant facts:
    ContentTable record count and the payload size.  Best effort."""
    try:
        from .adocument import open_document_object
        adoc = open_document_object(path)
    except Exception as ex:
        return {"decoded": False, "error": repr(ex)}
    v = adoc.value if isinstance(adoc.value, dict) else {}
    ct = (v.get("m_oContentTable") or {}).get("value") or {}
    recs = ct.get("m_ContentRecSet")
    guids: List[str] = []
    if isinstance(recs, list):
        for r in recs:
            if isinstance(r, dict):
                g = ((r.get("m_ContentKey") or {}).get("m_guidKey"))
                if g:
                    guids.append(str(g))
    return {
        "decoded": True,
        "clean": bool(adoc.clean),
        "payload_bytes": adoc.consumed if hasattr(adoc, "consumed") else None,
        "content_table_records": (len(recs) if isinstance(recs, list) else None),
        "content_table_guids": guids,
    }


def _class_of(fi, unit_recs: dict, eid) -> str:
    r = unit_recs.get(eid)
    return fi.class_name(r.class_id) if r is not None else "MISSING"


def dbviewtype_report(fi, host_ids: set) -> Dict[str, Any]:
    """The DBViewType default-family question, measured on ONE file.

    For every host ``DBViewType`` element: its name, and for each reference
    field in :data:`DBVIEWTYPE_REF_FIELDS` the target id, the target's class
    (``MISSING`` if the id is not a host element), and -- when the target is a
    ``Family`` -- the family name and whether it carries an embedded document
    (its ``m_oFamDoc.m_contentDocGUID`` resolves to a partition save unit).
    """
    u0 = fi.unit_records(0).get(102, {})
    vt_ids = [i for i in fi.ids_of_class(0, "DBViewType") if i in host_ids]
    rows = []
    field_targets: Counter = Counter()
    family_targets: Counter = Counter()
    dangling: Counter = Counter()
    for i in vt_ids:
        v = fi.value(0, i) or {}
        name = ((v.get("m_symbolInfo") or {}).get("value") or {}).get("m_name")
        refs = {}
        for fld in DBVIEWTYPE_REF_FIELDS:
            t = v.get(fld)
            if not isinstance(t, int) or t in (-1, None):
                continue
            tcls = _class_of(fi, u0, t)
            entry: Dict[str, Any] = {"id": t, "class": tcls}
            field_targets[(fld, tcls)] += 1
            if tcls == "MISSING":
                dangling[fld] += 1
            elif tcls == "Family":
                fv = fi.value(0, t) or {}
                g = ((fv.get("m_oFamDoc") or {}).get("value") or {}).get("m_contentDocGUID")
                entry["family_name"] = fv.get("m_name")
                entry["family_has_document"] = fi.unit_by_guid.get(g) is not None
                family_targets[(fv.get("m_name"), entry["family_has_document"])] += 1
            refs[fld] = entry
        rows.append({"id": i, "name": name, "system_family_idx": v.get("m_systemFamilyIdx"),
                     "refs": refs})
    return {
        "n_viewtypes": len(vt_ids),
        "n_with_famId": sum(1 for r in rows if "m_famId" in r["refs"]),
        "field_target_classes": {f"{fld}->{cls}": n
                                 for (fld, cls), n in sorted(field_targets.items())},
        "famId_families": {f"{nm} (doc={'yes' if doc else 'no'})": n
                           for (nm, doc), n in sorted(family_targets.items(),
                                                     key=lambda kv: -kv[1])},
        "dangling_ref_fields": dict(dangling),
        "rows": rows,
    }


def census(path: str, *, with_dbviewtype: bool = True,
           with_adocument: bool = True) -> Dict[str, Any]:
    """Full census of ONE ``.rvt``: classes, streams, units, coherence,
    families, DBViewType references.  Read-only, and read under the file's
    OWN release (entered once here, restored on return, nest-safe inside a
    caller's context); ``release`` is the year its BasicFileInfo declares and
    ``release_note`` appears only when the own schema could not settle the
    framing (the fallback rung taken, one sentence)."""
    from contextlib import ExitStack
    from .global_framing import enter_own_release

    path = path if os.path.isabs(path) else os.path.join(ROOT, path)
    with ExitStack() as stack:
        note = enter_own_release(stack, path)
        out = _census(path, with_dbviewtype=with_dbviewtype,
                      with_adocument=with_adocument)
    if note:
        out["release_note"] = note
    return out


def _census(path: str, *, with_dbviewtype: bool, with_adocument: bool) -> Dict[str, Any]:
    t0 = time.time()
    from .container import open_rvt
    from .elemtable import inflate_global_stream, parse_elemtable
    from .families import FamilyIndex
    from .versions import detect_release

    out: Dict[str, Any] = {"file": os.path.relpath(path, ROOT),
                           "size_bytes": os.path.getsize(path),
                           "release": detect_release(path)}

    # -- container: streams, ContentDocuments, ElemTable ---------------------
    with open_rvt(path) as f:
        out.update(_stream_inventory(f))
        out["content_documents"] = _content_documents(f)
        try:
            et = parse_elemtable(
                inflate_global_stream(f.raw("Global/ElemTable")).payload, out["file"])
            et_ids = {r.id for r in et.records}
            out["elemtable_rows"] = len(et.records)
        except Exception as ex:                                # pragma: no cover
            et_ids = set()
            out["elemtable_rows"] = None
            out["elemtable_error"] = repr(ex)

    # -- element census (host document = unit 0, filtered by the ElemTable) --
    fi = FamilyIndex.open(path)
    u0 = fi.unit_records(0).get(102, {})
    host_ids = set(u0) & et_ids if et_ids else set(u0)
    classes = Counter(fi.class_name(r.class_id) for eid, r in u0.items()
                      if eid in host_ids)
    out["host_records"] = len(host_ids)
    out["unit0_records"] = len(u0)
    out["classes"] = dict(classes.most_common())
    out["n_classes"] = len(classes)

    # -- save units: host document(s) + embedded family documents ------------
    # A family document unit carries a GUID (= its ContentDocuments key); the
    # host document unit (unit 0) is GUID-less, and a second GUID-less unit
    # appears with a second Partitions stream (workshared / dach).
    unit_guids = {u.guid for u in fi.units if u.guid}
    cd_guids = set(out["content_documents"].get("guids") or [])
    out["units"] = {
        "total": len(fi.units),
        "guidless_units": sum(1 for u in fi.units if not u.guid),
        "family_documents": len(unit_guids),
        "units_without_cd_entry": len(unit_guids - cd_guids),
        "cd_entries_without_unit": len(cd_guids - unit_guids),
    }
    out["content_documents"].pop("guids", None)

    # -- host families: which have embedded documents ------------------------
    fams = [i for i in fi.ids_of_class(0, "Family") if i in host_ids]
    with_doc, without_doc = [], []
    for fam in fams:
        fv = fi.value(0, fam) or {}
        g = ((fv.get("m_oFamDoc") or {}).get("value") or {}).get("m_contentDocGUID")
        (with_doc if fi.unit_by_guid.get(g) is not None else without_doc).append(fv.get("m_name"))
    out["families"] = {"host_families": len(fams),
                       "with_document": len(with_doc),
                       "without_document": len(without_doc),
                       "names_with_document": sorted(map(str, with_doc)),
                       "names_without_document": sorted(map(str, without_doc))}

    # -- the coherence tuple -----------------------------------------------------
    if with_adocument:
        out["adocument"] = _adocument_facts(path)
    ct = out.get("adocument", {}).get("content_table_records")
    ct_guids = set(out.get("adocument", {}).get("content_table_guids") or [])
    u = out["units"]
    coh: Dict[str, Any] = {
        "content_documents_entries": out["content_documents"].get("entries"),
        "embedded_units": u["family_documents"],
        "content_table_records": ct,
    }
    if ct is not None:
        # the Bug-B measurement: ContentTable records naming a GUID that has
        # no ContentDocuments entry / no partition save unit = DANGLING.
        coh["content_records_without_document"] = len(ct_guids - cd_guids)
        coh["documents_without_content_record"] = len(cd_guids - ct_guids)
        coh["coherent"] = (unit_guids == cd_guids == ct_guids)
    else:
        coh["coherent"] = unit_guids == cd_guids
    out["coherence"] = coh
    if "adocument" in out:
        out["adocument"].pop("content_table_guids", None)

    if with_dbviewtype:
        rep = dbviewtype_report(fi, host_ids)
        rep.pop("rows")                       # keep the per-file record compact
        out["dbviewtype"] = rep
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


# ---------------------------------------------------------------------------
# corpus-level diffs
# ---------------------------------------------------------------------------

def mandatory_set(censuses: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Classes present in EVERY census (the candidate MANDATORY set), with the
    minimal / maximal count observed and the file count.

    Returns ``{class: {"n_files": N, "min": m, "max": M}}`` sorted by min
    count descending; ``n_files`` == ``len(censuses)`` for every entry.
    """
    if not censuses:
        return {}
    common = set.intersection(*(set(c["classes"]) for c in censuses))
    out: Dict[str, Dict[str, int]] = {}
    n = len(censuses)
    for cls in common:
        counts = [c["classes"][cls] for c in censuses]
        out[cls] = {"n_files": n, "min": min(counts), "max": max(counts)}
    return dict(sorted(out.items(), key=lambda kv: (-kv[1]["min"], kv[0])))


def class_presence(censuses: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Union view: every class seen anywhere -> {n_files present, min, max}."""
    n = len(censuses)
    seen: Dict[str, List[int]] = {}
    for c in censuses:
        for cls, k in c["classes"].items():
            seen.setdefault(cls, []).append(k)
    return {cls: {"n_files": len(v), "of": n, "min": min(v), "max": max(v)}
            for cls, v in sorted(seen.items(), key=lambda kv: (-len(kv[1]), kv[0]))}


def missing_from(census_: Dict[str, Any], mandatory: Iterable[str]) -> List[str]:
    """Mandatory classes with count 0 (absent) in this census."""
    have = census_["classes"]
    return sorted(cls for cls in mandatory if have.get(cls, 0) == 0)


def count_shortfall(census_: Dict[str, Any],
                    mandatory: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    """Mandatory classes this file HAS, but with FEWER than the minimum any
    accepted file carries -- ranked by relative deficit.  (A constructed base
    with 94 GStyleElem rows vs an accepted minimum of 1,533 is 'present' yet
    an order of magnitude short.)"""
    rows = []
    for cls, st in mandatory.items():
        have = census_["classes"].get(cls, 0)
        if 0 < have < st["min"]:
            rows.append({"class": cls, "have": have, "min_in_passing": st["min"],
                         "max_in_passing": st["max"],
                         "ratio": round(have / st["min"], 3)})
    rows.sort(key=lambda r: (r["ratio"], -r["min_in_passing"]))
    return rows


def rank_suspects(passing: Sequence[Dict[str, Any]],
                  failing: Sequence[Dict[str, Any]],
                  *, min_presence: float = 1.0) -> Dict[str, Any]:
    """For each failing file: the classes present in (a fraction >=
    ``min_presence`` of) the passing files but ABSENT in it, ranked by the
    minimal count the passing files carry (higher min count = more central
    machinery = higher rank).  ``min_presence=1.0`` = present in EVERY
    accepted file (the strict candidate MANDATORY set)."""
    presence = class_presence(passing)
    n_pass = len(passing)
    core = {cls: st for cls, st in presence.items()
            if st["n_files"] >= max(1, int(min_presence * n_pass))}
    out: Dict[str, Any] = {"n_passing": n_pass, "core_classes": len(core),
                           "min_presence": min_presence, "failing": {}}
    for fc in failing:
        missing = []
        for cls, st in core.items():
            if fc["classes"].get(cls, 0) == 0:
                missing.append({"class": cls, "present_in": st["n_files"],
                                "of": n_pass, "min_count_in_passing": st["min"],
                                "max_count_in_passing": st["max"]})
        missing.sort(key=lambda r: (-r["present_in"], -r["min_count_in_passing"], r["class"]))
        out["failing"][fc["file"]] = {"host_records": fc.get("host_records"),
                                     "n_classes": fc.get("n_classes"),
                                     "missing_core_classes": missing,
                                     "n_missing": len(missing)}
    return out


def stream_unit_matrix(censuses: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Which OLE streams every file has, and the save-unit-kind / coherence
    picture per file (host units, family units, CD entries, ContentTable)."""
    if not censuses:
        return {}
    stream_sets = [set(c["streams"]) for c in censuses]
    common = set.intersection(*stream_sets)
    union = set.union(*stream_sets)
    per_file = {}
    for c in censuses:
        per_file[c["file"]] = {
            "partition_streams": c.get("partition_streams"),
            "units_total": c["units"]["total"],
            "family_documents": c["units"]["family_documents"],
            "cd_entries": c["content_documents"].get("entries"),
            "content_table_records": (c.get("adocument") or {}).get("content_table_records"),
            "content_records_without_document":
                (c.get("coherence") or {}).get("content_records_without_document"),
            "coherent": (c.get("coherence") or {}).get("coherent"),
            "host_families": (c.get("families") or {}).get("host_families"),
            "families_with_document": (c.get("families") or {}).get("with_document"),
            "missing_streams": sorted(union - set(c["streams"])),
        }
    return {"streams_in_every_file": sorted(common),
            "streams_union": sorted(union),
            "per_file": per_file}


# ---------------------------------------------------------------------------
# corpus runners
# ---------------------------------------------------------------------------

def load_certified(path: str = CERTIFIED_JSON) -> Dict[str, List[str]]:
    """Read the orchestrator's viewer-certified.json -> {'certified': [...],
    'failed': [...]} of repo-relative file paths."""
    with open(path) as fh:
        j = json.load(fh)
    return {"certified": [e["file"] for e in j.get("certified", [])],
            "failed": [e["file"] for e in j.get("failed", [])]}


def run(paths: Sequence[str], **kw) -> List[Dict[str, Any]]:
    """Census a list of files (repo-relative or absolute); skips missing."""
    out = []
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if not os.path.exists(full):
            out.append({"file": p, "error": "missing"})
            continue
        try:
            out.append(census(full, **kw))
        except Exception as ex:                                # pragma: no cover
            out.append({"file": p, "error": repr(ex)})
    return out


def _corpus_tables(passing: Sequence[Dict[str, Any]],
                   failing: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The diff tables over ONE release's passing / failing censuses."""
    return {
        "passing_files": [c["file"] for c in passing],
        "failing_files": [c["file"] for c in failing],
        "mandatory_set": mandatory_set(passing),
        "class_presence_passing": class_presence(passing),
        "suspects_strict": rank_suspects(passing, failing, min_presence=1.0),
        "suspects_loose": rank_suspects(passing, failing, min_presence=0.85),
        "streams_units": stream_unit_matrix(list(passing) + list(failing)),
    }


def run_certified(include_samples: bool = True, *,
                  reference_release: Optional[int] = None, **kw) -> Dict[str, Any]:
    """The whole positive/negative corpus: six samples + every certified
    (PASS) + every failed (FAIL) file, plus all the diff tables.

    Releases are kept apart (a mandatory set is an intersection of class
    inventories, and those differ per release): the top-level tables are
    computed over the ``reference_release`` files only (default: the latest
    release we know, ``rvt.versions.LATEST_RELEASE`` -- what this runner
    measured before older-release files could be read at all), and every
    release seen gets the same tables under ``by_release[year]``.
    ``censuses`` holds every file read, each with its ``release``."""
    from .versions import LATEST_RELEASE
    ref = int(reference_release or LATEST_RELEASE)
    lists = load_certified()
    passing_paths = list(lists["certified"])
    if include_samples:
        passing_paths = [os.path.join("samples", s + ".rvt") for s in SAMPLES] + passing_paths
    passing = [c for c in run(passing_paths, **kw) if "error" not in c]
    failing = [c for c in run(lists["failed"], **kw) if "error" not in c]
    years = sorted({c.get("release") for c in passing + failing} | {ref},
                   key=lambda y: (y is None, y))
    by_release = {y: _corpus_tables([c for c in passing if c.get("release") == y],
                                    [c for c in failing if c.get("release") == y])
                  for y in years}
    out = dict(by_release[ref])
    out["reference_release"] = ref
    out["by_release"] = by_release
    out["censuses"] = {c["file"]: c for c in passing + failing}
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_census(c: Dict[str, Any]) -> None:
    print(f"== {c['file']}  ({c['size_bytes']:,} B)")
    if c.get("release_note"):
        print(f"   release: {c['release_note']}")
    print(f"   host_records={c['host_records']}  classes={c['n_classes']}  "
          f"units={c['units']['total']} (family docs {c['units']['family_documents']})  "
          f"CD entries={c['content_documents'].get('entries')}  "
          f"ContentTable={ (c.get('adocument') or {}).get('content_table_records') }  "
          f"coherent={c['coherence']['coherent']}")
    fams = c["families"]
    print(f"   host families={fams['host_families']} (with doc {fams['with_document']}, "
          f"system/no-doc {fams['without_document']})")
    top = list(c["classes"].items())[:12]
    print("   top classes: " + ", ".join(f"{k} {v}" for k, v in top))
    dv = c.get("dbviewtype")
    if dv:
        print(f"   DBViewType n={dv['n_viewtypes']} with famId={dv['n_with_famId']} "
              f"dangling={dv['dangling_ref_fields']}")


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_json = None
    if "--json" in argv:
        i = argv.index("--json")
        out_json = argv[i + 1]
        del argv[i:i + 2]
    if "--certified" in argv:
        rep = run_certified()
        print(f"passing files: {len(rep['passing_files'])}   failing: {len(rep['failing_files'])}")
        for year, sub in rep["by_release"].items():
            if year != rep["reference_release"]:
                print(f"   release {year}: passing {len(sub['passing_files'])}  "
                      f"failing {len(sub['failing_files'])}  "
                      f"mandatory classes {len(sub['mandatory_set'])}  (by_release)")
        print(f"mandatory classes (in EVERY accepted file): {len(rep['mandatory_set'])}")
        for cls, st in list(rep["mandatory_set"].items())[:40]:
            print(f"   {cls:32s} min={st['min']:5d} max={st['max']:6d}")
        print("suspects (strict) per failing file:")
        for fname, s in rep["suspects_strict"]["failing"].items():
            print(f"   {fname}: {s['n_missing']} missing core classes "
                  f"(host_records {s['host_records']})")
        if out_json:
            with open(out_json, "w") as fh:
                json.dump(rep, fh, indent=1, default=str)
            print(f"wrote {out_json}")
        return 0
    paths = argv or [os.path.join("samples", "rstbasicsampleproject.rvt")]
    results = run(paths)
    for c in results:
        if "error" in c:
            print(f"== {c['file']}: ERROR {c['error']}")
        else:
            _print_census(c)
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(results, fh, indent=1, default=str)
        print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
