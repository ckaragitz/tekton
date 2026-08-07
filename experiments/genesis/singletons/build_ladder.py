#!/usr/bin/env python
"""build_ladder.py -- the S-LADDER: pre-built G1 candidates that ADD our
settings-singleton / catalog constructors to the failing constructed base
(G1_candidate), so a K5x / K6 viewer verdict names a class whose FIX FILE
already exists (no cold start).  Workstream: genesis-singletons (the
K5/K6-FAIL branch); constructors: ``rvt.genesis.settings`` +
``rvt.genesis.catalog``; record: ``docs/inbox/genesis-singletons.md``.

Each rung = the base + OUR content, added through the proven commit path
(``rvt.commit.commit_new_elements`` -> the canonical unit-0 re-blocker),
with the ADocument (``Global/Latest``) registries repopulated over the new
ids (``settings.apply_adoc_registry`` via the byte-exact ``rvt.adocument``
codec), then certified: ``rvt.validate.validate_file`` (0 errors required),
the ADocument's own re-decode, and an id byte-scan for dangling
references (must be ZERO -- every id the file references exists in it).

RUNGS (each built directly from the BASE, cumulative content):
  S1  base + our PenWidthTableElem (the K5a class, census #1 suspect)
  S2  S1 + the project-browser constellation: 6 BrowserOrganizations (the
      four 'all' defaults + our two house schemes), the system-navigator
      view + its viewer/viewport/drawing, ReconcileBrowserSettingsElem,
      ConstructionSetProject  (K5b)
  S3  S2 + the named singletons: StructSettingsElem, WallJoinDefaultSetting,
      AutoJoinTracker, KeynoteTable + KeynotingSystem, InitialViewSettings
  S4  S3 + the COMPLETE built-in-category graphic-style catalog: one
      projection GStyleElem per registered graphic category (+ cut where
      cuttable) that the base lacks, OUR discipline scheme (K6)
  S5  S3 + EVERY other constructed settings class (the MEP settings and
      size tables, the tracker set, revisions, print, export, worksharing,
      area, energy, the 16 remaining SYSTEM view types) + the S4 catalog =
      the census-complete candidate (every count-invariant Tier-1 class of
      docs/writer/required-set.md that has a constructor).

Usage (repo root, .venv python):
    experiments/genesis/singletons/build_ladder.py                # all rungs
    experiments/genesis/singletons/build_ladder.py --only S1,S3   # some rungs
    experiments/genesis/singletons/build_ladder.py --base experiments/genesis/G1a.rvt

Outputs (experiments/genesis/singletons/): S1..S5.rvt, S*_report.json (the
per-rung certification record), probes.json (the upload manifest).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import struct
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import adocument as adoc                                  # noqa: E402
from rvt import ecc                                                # noqa: E402
from rvt import stream_encoders as se                              # noqa: E402
from rvt.cfb_writer import write_cfb                               # noqa: E402
from rvt.commit import commit_new_elements, verify_written         # noqa: E402
from rvt.container import open_rvt                                 # noqa: E402
from rvt.reduce import delete_elements                             # noqa: E402
from rvt.roundtrip import read_entries                             # noqa: E402
from rvt.genesis import settings as ST                             # noqa: E402
from rvt.genesis import catalog as CAT                             # noqa: E402
from rvt.genesis.types import IdSource                             # noqa: E402

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
GEN_DIR = os.path.dirname(OUT_DIR)                                 # experiments/genesis
BASE = os.path.join(GEN_DIR, "G1_candidate.rvt")
MAPS = os.path.join(GEN_DIR, "G1_registry_maps.json")
MANIFEST = os.path.join(GEN_DIR, "G0_manifest.json")               # the base's named ids
SAMPLES_DIR = os.path.join(ROOT, "samples")
IDENTITY = {"author": "rvt-writer", "client_app_name": "rvt-writer",
            "username": "rvt-writer"}


# ---------------------------------------------------------------------------
# base facts
# ---------------------------------------------------------------------------

def base_watermark(path: str) -> int:
    with open_rvt(path) as f:
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
    return max(int(r[4]) for r in et["records"])


def base_ids(path: str) -> Set[int]:
    with open_rvt(path) as f:
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
    return {int(r[4]) for r in et["records"]}


def base_doc_guid(path: str) -> str:
    with open_rvt(path) as f:
        bfi = se.decode_basic_file_info(f.logical("BasicFileInfo"))
    return bfi.get("unique_document_guid") or bfi.get("central_model_identity") or ""


def base_named_ids(manifest: str = MANIFEST) -> Dict[str, int]:
    """The house-standard skeleton's named ids (units / phases / views /
    sun / geo / levels) recorded by the assembler's manifest."""
    if not os.path.exists(manifest):
        return {}
    with open(manifest) as fh:
        m = json.load(fh)
    return {k: int(v) for k, v in (m.get("named_ids") or {}).items()}


def base_object_style_categories(path: str) -> Set[int]:
    """Built-in category ids the base already carries object-style rows for
    (its GStyleElem records with a negative m_categoryId)."""
    from rvt.mutate import Document
    doc = Document.from_file(path)
    cats: Set[int] = set()
    for gid in doc.ids_of_class("GStyleElem"):
        v = doc.value(gid) or {}
        cid = v.get("m_categoryId")
        if isinstance(cid, int) and cid < 0:
            cats.add(int(cid))
    return cats


# ---------------------------------------------------------------------------
# rung content builders
# ---------------------------------------------------------------------------

def build_content(rung: str, start_id: int, named: Dict[str, int],
                  base_style_cats: Set[int]) -> Tuple[list, dict]:
    """Return (records, info) for a rung: the settings tier records plus
    (S4/S5) the built-in style catalog rows for categories the base lacks."""
    ids = IdSource(start_id)
    tier = {"S1": "pen", "S2": "browser", "S3": "named",
            "S4": "named", "S5": "all"}[rung]
    cat = ST.standard_settings(ids, tier=tier, doc_ids=named)
    records = list(cat.records)
    info: Dict[str, Any] = {"tier": tier, "settings_records": len(records)}
    if rung in ("S4", "S5"):
        rows = CAT.builtin_style_catalog(ids, exclude_categories=base_style_cats)
        records.extend(rows)
        info["catalog_rows"] = len(rows)
        info["catalog_excluded_base_categories"] = len(base_style_cats)
    info["records"] = len(records)
    info["id_range"] = [start_id, ids.last_issued]
    # self-verification before anything is written
    rt_fail = 0
    fails = []
    for r in records:
        rep = r.roundtrip()
        if not rep["ok"]:
            rt_fail += 1
            fails.append(f"{r.class_name}#{r.elem_id}: {rep}"[:200])
    info["roundtrip_failures"] = rt_fail
    if rt_fail:
        raise SystemExit(f"{rung}: {rt_fail} records not clean/byte-exact: {fails[:3]}")
    return records, info


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------

def stage_commit(base: str, out: str, records: list, guid: str) -> dict:
    """Commit the records into a copy of the base + canonical re-block."""
    t0 = time.time()
    recs = [{seq: b for seq, b in r.encode().items()} for r in
            sorted(records, key=lambda x: x.elem_id)]
    plans = [r.as_new_element().elemrec for r in sorted(records, key=lambda x: x.elem_id)]
    tmp = out + ".append.tmp"
    rep = commit_new_elements(base, tmp, recs, plans,
                              identity=dict(IDENTITY, document_guid=guid))
    ver = verify_written(tmp, [r.elem_id for r in records])
    clean = sum(1 for s in ver["new_ids_found"].values()
                for v in s.values() if v.get("clean") is not False)
    rr = delete_elements(tmp, out, [])                 # canonical re-blocking
    try:
        os.remove(tmp)
    except OSError:
        pass
    return {"op": "commit our elements + re-block",
            "new_elements": len(records),
            "elemtable_after": rep.elemtable_count_after,
            "watermark_after": rep.watermark_after,
            "verify_written": {"crc_failures": ver["crc_failures"],
                               "ecc_mismatches": ver["ecc_mismatches"],
                               "walker_errors": ver["walker_errors"],
                               "stamps_ok": ver["stamps_ok"],
                               "new_records_clean": clean},
            "reblock": {"blocks_before": rr.blocks_before,
                        "blocks_after": rr.blocks_after},
            "seconds": round(time.time() - t0, 1)}


def stage_registries(path_in: str, path_out: str, records: list,
                     maps: dict) -> dict:
    """Decode the file's ADocument, populate the registries over the new
    records (settings.apply_adoc_registry), re-encode + re-frame, rewrite
    the Latest stream + BasicFileInfo's last-save path."""
    t0 = time.time()
    with open_rvt(path_in) as f:
        payload = f.inflate(adoc.STREAM, 0)
        bfi = se.decode_basic_file_info(f.logical("BasicFileInfo"))
    source = adoc.decode_latest(payload)
    if not source.clean:
        raise RuntimeError(f"{path_in}: ADocument decode not clean: {source.errors[:1]}")
    tree = source.value
    report = ST.apply_adoc_registry(tree, records, maps=maps)
    new_payload = adoc.encode_latest(tree)
    back = adoc.decode_latest(new_payload)
    if not (back.clean and back.value == tree):
        raise RuntimeError("authored ADocument does not round-trip")
    # post-condition: every id the document references exists in the file
    ids_in_file = base_ids(path_in)
    refs = set(back.element_ids())
    dangling = sorted(i for i in refs if i > 0 and i not in ids_in_file)
    logical = adoc.latest_logical_stream(new_payload, level=3)
    framed = ecc.frame_stream(logical)
    entries = read_entries(path_in)
    bfi2 = dict(bfi)
    bfi2["last_save_path"] = os.path.basename(path_out)
    new_streams = {adoc.STREAM: framed,
                   "BasicFileInfo": se.encode_basic_file_info(bfi2, regenerate_mirror=True)}
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(path_out, out_entries)
    return {"op": "repopulate ADocument registries over the new ids",
            "registry_report": report,
            "latest_payload_before": len(payload),
            "latest_payload_after": len(new_payload),
            "adoc_element_refs": len(refs),
            "adoc_dangling_ids": dangling[:20],
            "adoc_dangling_count": len(dangling),
            "our_ids_referenced": len(refs & {r.elem_id for r in records}),
            "seconds": round(time.time() - t0, 1)}


def stage_certify(path: str) -> dict:
    from rvt.validate import validate_file
    t0 = time.time()
    rep = validate_file(path)
    return {"ok": bool(rep.ok), "errors": len(rep.errors),
            "warnings": len(rep.warnings),
            "error_messages": [f"[{f.layer}] {f.where}: {f.message}"[:300]
                               for f in rep.errors[:10]],
            "warning_messages": [f"[{f.layer}] {f.where}: {f.message}"[:200]
                                 for f in rep.warnings[:6]],
            "stats": {k: v for k, v in rep.stats.items()
                      if k in ("streams", "records", "elements_decoded",
                               "refs_checked", "partition_blocks", "decode_failures")},
            "seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------------------
# rung driver
# ---------------------------------------------------------------------------

def build_rung(rung: str, base: str, out_dir: str, maps: dict,
               named: Dict[str, int], base_style_cats: Set[int]) -> dict:
    t0 = time.time()
    out = os.path.join(out_dir, f"{rung}.rvt")
    wm = base_watermark(base)
    start = ((wm // 100_000) + 1) * 100_000                 # our ids above the base
    guid = base_doc_guid(base)
    print(f"== {rung}: base {os.path.basename(base)} watermark {wm:,}; our ids from {start:,}")
    records, info = build_content(rung, start, named, base_style_cats)
    by_class = Counter(r.class_name for r in records)
    print(f"   content: {info['records']} records ({len(by_class)} classes); "
          f"round-trip clean {info['records'] - info['roundtrip_failures']}/{info['records']}")
    rep: Dict[str, Any] = {"rung": rung, "base": os.path.relpath(base, ROOT),
                           "file": os.path.relpath(out, ROOT),
                           "content": info,
                           "by_class": dict(by_class.most_common()),
                           "stages": []}
    tmp1 = out + ".commit.tmp"
    r1 = stage_commit(base, tmp1, records, guid)
    rep["stages"].append(r1)
    we = r1['verify_written']['walker_errors']
    n_we = len(we) if isinstance(we, (list, tuple)) else int(we or 0)
    print(f"   commit: {r1['elemtable_after']:,} elements after; "
          f"new records clean {r1['verify_written']['new_records_clean']}; "
          f"walker errors {n_we}")
    r2 = stage_registries(tmp1, out, records, maps)
    rep["stages"].append(r2)
    print(f"   registries: {r2['registry_report']['applied']}; "
          f"ADocument dangling ids {r2['adoc_dangling_count']}")
    for s in r2["registry_report"]["skipped"][:8]:
        print("      skipped:", s)
    try:
        os.remove(tmp1)
    except OSError:
        pass
    r3 = stage_certify(out)
    rep["validator"] = r3
    print(f"   validator: {'VALID' if r3['ok'] else 'INVALID'} "
          f"errors={r3['errors']} warnings={r3['warnings']} "
          f"records={r3['stats'].get('records')} elements={r3['stats'].get('elements_decoded')}")
    for m in r3["error_messages"][:5]:
        print("      ERROR", m)
    rep["bytes"] = os.path.getsize(out)
    rep["seconds"] = round(time.time() - t0, 1)
    rep["verdict"] = ("VALID" if (r3["ok"] and r3["errors"] == 0
                                  and r2["adoc_dangling_count"] == 0) else "NOT-CLEAN")
    with open(os.path.join(out_dir, f"{rung}_report.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    return rep


# ---------------------------------------------------------------------------
# probes.json (the upload manifest)
# ---------------------------------------------------------------------------

PROBE_TEXT = {
    "S1": {
        "adds": "OUR PenWidthTableElem (the real project pen table -- element id 2 "
                "in every Autodesk file; K5a's class; census #1 suspect)",
        "tests": "the reader requires the project pen table",
        "pass": "PenWidthTableElem is the missing singleton (if K5a FAILED); "
                "the constructed base + our pen table opens",
        "fail": "the pen table is not the (only) missing class -> S2/S3/S5",
        "sibling": "experiments/genesis/G1_candidate.rvt (FAIL), "
                   "experiments/genesis/triage/K5a.rvt (its removal probe)",
    },
    "S2": {
        "adds": "S1 + the project-browser constellation: 6 BrowserOrganizations "
                "(the 4 per-tree 'all' defaults + our 2 house schemes), the MEP "
                "system-navigator view (RbsDbViewSystemNavigator + viewer + "
                "viewport + drawing), ReconcileBrowserSettingsElem, "
                "ConstructionSetProject (K5b's population)",
        "tests": "the reader requires the project-browser / system-navigator "
                 "constellation",
        "pass": "K5b's classes were the gap",
        "fail": "browser constellation not sufficient -> S3/S5",
        "sibling": "experiments/genesis/triage/K5b.rvt (its removal probe)",
    },
    "S3": {
        "adds": "S2 + StructSettingsElem, WallJoinDefaultSetting, AutoJoinTracker, "
                "KeynoteTable (empty -- no keynote file) + KeynotingSystem, "
                "InitialViewSettings (the charter's named singletons)",
        "tests": "the named structural / join / keynote / start-view singletons",
        "pass": "the named singleton set completes the required skeleton",
        "fail": "more classes required -> S5 (census-complete)",
        "sibling": "experiments/genesis/triage/K5c.rvt + K5d.rvt",
    },
    "S4": {
        "adds": "S3 + the COMPLETE built-in-category graphic-style catalog "
                "(one projection GStyleElem per registered graphic category + "
                "cut where cuttable, OUR discipline colours/weights) for the "
                "categories the base does not style (K6's population)",
        "tests": "the reader requires the full object-styles table",
        "pass": "the built-in style catalog was the gap (K6 FAILED)",
        "fail": "the catalog is not sufficient -> S5",
        "sibling": "experiments/genesis/triage/K6.rvt (its removal probe)",
    },
    "S5": {
        "adds": "S3 + EVERY other constructed settings singleton (MEP wire/duct/"
                "pipe/conduit/cable-tray settings, duct sizes, the MEP tracker "
                "constellation, all UniqueElement singletons and trackers, "
                "revisions, print, worksharing/export/area/energy settings, "
                "model graphics styles, the 16 remaining SYSTEM view types) "
                "+ the S4 catalog = the census-complete candidate",
        "tests": "everything the K-ladder can name at once (K5 + K6 + view types)",
        "pass": "the required class is among the constructed set -- bisect "
                "downward with S1..S4",
        "fail": "the required class is NOT a settings singleton / style catalog "
                "-> the family layer (K4) or the settings CATALOGS "
                "(HVACLoad space/building types, pipe catalog) named in the record",
        "sibling": "experiments/genesis/triage/K5.rvt + K6.rvt",
    },
}


def write_probes_json(reports: Dict[str, dict], out_dir: str) -> str:
    order = ["S1", "S2", "S3", "S4", "S5"]
    probes = []
    for rung in order:
        rep = reports.get(rung) or {}
        pt = PROBE_TEXT[rung]
        probes.append({
            "file": f"experiments/genesis/singletons/{rung}.rvt",
            "rung": rung,
            "adds": pt["adds"],
            "tests_one_thing": pt["tests"],
            "PASS_means": pt["pass"],
            "FAIL_means": pt["fail"],
            "known_sibling": pt["sibling"],
            "verdict": rep.get("verdict", "not built"),
            "elements_added": (rep.get("content") or {}).get("records"),
            "by_class": rep.get("by_class"),
            "bytes": rep.get("bytes"),
        })
    manifest = {
        "generator": "experiments/genesis/singletons/build_ladder.py",
        "base": os.path.relpath(BASE, ROOT),
        "purpose": ("Pre-built ADD-BACK candidates for the K5x / K6 branch of the "
                    "reader bisection: each S file = the failing constructed base "
                    "(G1_candidate) + OUR constructors' output for the class(es) a "
                    "K-rung FAIL would name -- so the fix for a verdict already "
                    "exists (no cold start). Every file: validator 0 errors, "
                    "ADocument dangling ids 0, registries repopulated over the "
                    "new ids."),
        "reading_the_results": {
            "K5a FAIL": "upload S1 (base + our pen table)",
            "K5b FAIL": "upload S2 (base + our browser constellation)",
            "K5c FAIL": "upload S5 (the MEP settings live only there)",
            "K5d FAIL": "upload S3 then S5 (named singletons, then the whole K5d set)",
            "K6 FAIL": "upload S4 (base + the complete built-in style catalog)",
            "K5 and K6 both FAIL / unclear": "upload S5 (census-complete) first; if it "
                                              "PASSES, bisect downward with S3/S1/S2/S4",
            "upload order by information value": ["S5", "S1", "S4", "S2", "S3"],
        },
        "probes": probes,
    }
    path = os.path.join(out_dir, "probes.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    return path


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=BASE, help="base file (default G1_candidate.rvt)")
    ap.add_argument("--only", default="", help="comma list of rungs to build (S1..S5)")
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    if not os.path.exists(args.base):
        raise SystemExit(f"base not found: {args.base}")
    maps = {}
    if os.path.exists(MAPS):
        with open(MAPS) as fh:
            maps = json.load(fh)
    else:
        print(f"WARNING: {MAPS} missing -- registry population degrades (no UET map)")
    named = base_named_ids()
    base_style_cats = base_object_style_categories(args.base)
    print(f"== base named ids: {sorted(named)}; base object-style categories: "
          f"{len(base_style_cats)}")
    wanted = [x.strip() for x in args.only.split(",") if x.strip()] or \
        ["S1", "S2", "S3", "S4", "S5"]
    t_all = time.time()
    reports: Dict[str, dict] = {}
    for rung in wanted:
        reports[rung] = build_rung(rung, args.base, args.out, maps, named,
                                   base_style_cats)
        print(f"   -> {reports[rung]['file']} {reports[rung]['bytes']:,} B "
              f"verdict {reports[rung]['verdict']} ({reports[rung]['seconds']}s)")
    p = write_probes_json(reports, args.out)
    print(f"== probes manifest: {os.path.relpath(p, ROOT)} "
          f"({round(time.time() - t_all, 1)}s total)")
    bad = [r for r in reports.values() if r["verdict"] != "VALID"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
