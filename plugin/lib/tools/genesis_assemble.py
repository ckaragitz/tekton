#!/usr/bin/env python
"""genesis_assemble.py — compose the GENESIS CANDIDATES (G0 ladder + the G1
set) of a Revit 2026 project whose ENTIRE inventory AND document object are
AUTHORED BY US, not Autodesk.

This is the ASSEMBLER for TRACKER P0 gate **G1 GENESIS BASELINE**
(``docs/product/content-strategy.md``): the base document must contain NO
Autodesk-authored expression — no sample families, no sample system-family
types, no sample view types / templates / object styles / patterns / text
styles / phases / settings, no sample document object.  The excavation
streams delivered the pieces (deep reduction ladder, provenance ledger v2, the
own-content HOUSE STANDARD, the ADocument codec, the Global/Latest landmark
map and reader-tolerance probes); this tool COMPOSES them into candidate
files and certifies each one with the two arbiters (``tools/rvt_validate.py``
and ``tools/provenance.py --baseline all --streams``).

STRATEGY, part 1 — the G0 ELEMENT LADDER (top-down "hollow-shell" assembly,
see docs/writer/genesis-status.md):

  base    = experiments/genesis/R10b.rvt  — the deepest VALIDATOR-CLEAN
            reduction of rstbasicsampleproject.  It supplies the machinery we
            cannot yet write ourselves: the container, framing, Formats/Latest
            (a per-release format constant) and Global/Latest (the ADocument).
  G0a     = base + OUR content INSERTED at fresh ids above the id watermark:
            the OWN-CONTENT HOUSE STANDARD (rvt.genesis.house_standard: our
            catalog + skeleton, own values, no Autodesk resource identifiers,
            234 elements) — nothing of ours references any Autodesk element.
  G0b     = G0a − every Autodesk host element that maximal garbage collection
            can release (validator-clean by construction).
  G0c     = G0b − all embedded family documents (save units + ContentDocuments
            entries spliced out).
  G0d     = G0c − the now-unpinned residue (second GC pass) = a document
            whose EVERY host element is ours, ZERO Autodesk family documents.
  G0      = G0d + one coordinated OWN SAVE: a fresh History episode whose
            GUID becomes OUR document GUID, DocumentIncrementTable / Contents /
            BasicFileInfo coherent, our authoring identity, EVERY save episode
            re-signed with OUR username (the V32 mechanism), every element
            re-stamped as created in the genesis episode.

STRATEGY, part 2 — GENESIS-2, the G1 SET (this session): replace the ONE
remaining Autodesk stream, ``Global/Latest`` (the serialized ADocument,
byte-identical to the rst sample's in G0 and enumerating ~6,400 dangling
sample element ids — the orchestrator's lead suspect for G0's viewer FAIL),
with an ADocument WE CONSTRUCT from the decoded object graph
(``rvt.adocument`` codec, byte-exact on all six samples):

  G1a            = G0 + OUR ADocument in MAX-SAFETY mode: COHERENCE ONLY —
                   every element-id registry purged of dangling ids (a schema-
                   typed tree walk over ~14.6k ElementId leaves; zero survive)
                   and the loaded-content registry emptied (G0 carries zero
                   content documents).  Nothing repopulated, no string edits,
                   the Forge unit-schema corpus and build history carried.
                   The probe that isolates "does zero-dangling open?".
  G1_candidate   = G0 + OUR ADocument in CANDIDATE mode: the purge + the
                   registries REPOPULATED to index EXACTLY our inventory
                   (category/graphic-style catalogue, per-class trackers, the
                   unique-element table, the view index, level->plan map,
                   default-type map, custom-element type map ...), the sample's
                   name caches / user maps / link-reconcile datasets EMPTIED,
                   the "saved by" build list reduced to the product constant,
                   the Forge unit-schema corpus CARRIED and FLAGGED as the
                   residual (product data identical in all six samples —
                   counsel C4-class, docs/writer/latest-regions.md).
                   THE genesis-2 deliverable.
  G1b            = G1_candidate in MAX-PURITY mode: additionally the Forge
                   corpora emptied, add-in/service descriptor lists emptied,
                   our own honest "saved by" string.  Highest legal purity,
                   lowest reader-acceptance confidence — the probe that
                   measures whether the corpus is load-bearing.
  G1_candidate_safe = the candidate ADocument authored over a G0 whose OWN
                   CONTENT was built with scrub="safe" (asset descriptors /
                   view-visibility policies left at constructor defaults) —
                   the fallback if the content-layer blanking, not the Latest
                   work, is what the reader rejects.

Every rung is validator-VALID (0 errors) or the build refuses to emit it,
and every emitted Latest re-decodes to exactly the tree we authored.  The
provenance ledger v2 (``--baseline all --streams``, all four layers) is run
on every G1 file; the HONEST gate reading is written to G1_provenance.json /
G1_gate.json and quoted in docs/writer/genesis-status.md (v2).

Usage (repo root, .venv python):
    tools/genesis_assemble.py                     # G0 ladder + G0_safe + the G1 set + reports
    tools/genesis_assemble.py --only content      # build + verify OUR content only
    tools/genesis_assemble.py --only ladder       # the G0 ladder only (no G1 set)
    tools/genesis_assemble.py --only g1           # the G1 set from the existing G0.rvt/G0_safe.rvt
    tools/genesis_assemble.py --only maps         # (re)derive G1_registry_maps.json from the samples
    tools/genesis_assemble.py --out DIR           # write elsewhere (default experiments/genesis)

Deliverables written (experiments/genesis/):
    G0a.rvt G0b.rvt G0c.rvt G0d.rvt G0.rvt G0_safe.rvt   G0*_validate/provenance.json
    G1a.rvt G1_candidate.rvt G1b.rvt G1_candidate_safe.rvt
    G1_validate.json  G1_provenance.json (+.txt)  G1_gate.json  G1_authoring.json
    G1_registry_maps.json  G0_manifest.json  G0_pipeline.json  G1_pipeline.json
"""
from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import importlib.util
import json
import os
import struct
import sys
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import ecc                                              # noqa: E402
from rvt import adocument as adoc                                # noqa: E402
from rvt.cfb_writer import write_cfb                             # noqa: E402
from rvt.commit import commit_new_elements, verify_written       # noqa: E402
from rvt.container import open_rvt                               # noqa: E402
from rvt.genesis import house_standard as hs                     # noqa: E402
from rvt.genesis import skeleton as sk                           # noqa: E402
from rvt.genesis import types as ty                              # noqa: E402
from rvt.identity import (own_identity_model,                    # noqa: E402
                          own_increment_table_payload)
from rvt.objects import field_key                                # noqa: E402
from rvt.reduce import delete_elements, verify_reduced           # noqa: E402
from rvt.roundtrip import read_entries                           # noqa: E402
from rvt import stream_encoders as se                            # noqa: E402
from rvt import streams_edit as ed                               # noqa: E402
from rvt.writer import gzip_member                               # noqa: E402

# the reduction driver is a tool, not a package module
_spec = importlib.util.spec_from_file_location(
    "rvt_reduce_tool", os.path.join(ROOT, "tools", "rvt_reduce.py"))
_reduce_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reduce_tool)                          # type: ignore
build_state_v2 = _reduce_tool.build_state_v2
maxgc = _reduce_tool.maxgc
remove_units = _reduce_tool.remove_units

# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------
BASE = os.path.join(ROOT, "experiments", "genesis", "R10b.rvt")
BASELINE = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
SAMPLES_DIR = os.path.join(ROOT, "samples")
OUT_DIR = os.path.join(ROOT, "experiments", "genesis")

#: identity strings we assert (pending counsel decision C1 = the writer's
#: existing placeholder; V31 proved the reader does not gatekeep on these)
AUTHOR = "rvt-writer"
#: username recorded in the own-save's DocumentIncrementTable record — and,
#: since genesis-2, in EVERY save episode (the V32 username-scrub mechanism)
USERNAME = "rvt-writer"
#: fixed timestamp for reproducible builds (2026-08-03T12:00:00Z)
TIMESTAMP = 1785931200
TIMESTAMP_ISO = "2026-08-03T12:00:00Z"

#: OUR project identity — single source of truth for the ProjectInfo
#: element AND the ProjectInformation (partatom) metadata stream.  Since
#: genesis-2 it is read from the own-content HOUSE STANDARD
#: (rvt.genesis.house_standard.PROJECT_INFO — audit item B6 / diff D1).
PROJECT_META = dict(hs.PROJECT_INFO)
PROJECT_META.setdefault("author", AUTHOR)

INVALID = -1
BLACK = 0
SOLID_LP = ty.LINEPATTERN_SOLID                    # built-in solid line "pattern"


def rgbc(r: int, g: int, b: int) -> int:
    """COLORREF r | g<<8 | b<<16."""
    return int(r) | (int(g) << 8) | (int(b) << 16)


# ---------------------------------------------------------------------------
# OUR object-styles HOUSE STANDARD (genesis-2: OWNED BY rvt.genesis.house_standard)
# ---------------------------------------------------------------------------
# The discipline-coded object-styles standard, the sub-category vocabulary and
# every default VALUE now live in the own-content stream's module (audit G1b
# "own values" + G1c "resource identifiers" — docs/inbox/own-content.md).
# The assembler keeps the two names as ALIASES so its tests and manifests read
# the same table the constructors used.

#: discipline -> (projection pen, cut pen, colour)  [our house scheme]
HOUSE_SCHEME: Dict[str, Tuple[int, int, int]] = dict(hs.HOUSE_SCHEME)

#: (built-in category OST id, our label, discipline, cuttable)
HOUSE_CATEGORIES: List[Tuple[int, str, str, bool]] = list(hs.HOUSE_CATEGORIES)


# ---------------------------------------------------------------------------
# OUR CONTENT — the self-contained skeleton + catalog
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class OurContent:
    """Everything WE author for the genesis document."""
    elements: list                       # rvt.mutate.NewElement, id-sorted
    manifest: List[dict]                 # per element: id/class/kind/name/params
    ids: Dict[str, Any]                  # named ids (levels, phases, views ...)
    start_id: int
    last_id: int
    roundtrip: dict
    dangling: List[dict]
    catalog: Any = None                  # rvt.genesis.house_standard.HouseCatalog
    scrub: str = "full"                  # house-standard scrub level applied


def _kind_of(rec) -> str:
    return (getattr(rec, "kind", "") or getattr(rec, "class_name", "") or "?")


def _name_of(rec) -> str:
    """Best-effort human name of a constructed record (for the manifest)."""
    obj = getattr(rec, "obj", None) or {}
    if not isinstance(obj, dict):
        return ""
    for path in (("m_text",), ("m_viewName",), ("m_name",),
                 ("m_symbolInfo", "value", "m_name"),
                 ("m_pMaterial", "value", "m_name"),
                 ("m_pLinePattern", "value", "m_name"),
                 ("m_pFillPattern", "value", "m_name"),
                 ("m_pFont", "value", "m_name"),
                 ("m_pCategory", "value", "m_name")):
        cur: Any = obj
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, str) and cur:
            return cur
    return ""


def build_our_content(start_id: int, *,
                      project_name: str = PROJECT_META["project_name"],
                      project_number: str = PROJECT_META["project_number"],
                      scrub: str = "full") -> OurContent:
    """Compose OUR complete genesis content — catalog + skeleton — allocating
    every id from ONE monotonic source starting at ``start_id`` (which must
    exceed the base document's id watermark so the provenance ledger reads
    every element as CREATED and no id can collide).

    GENESIS-2 (own-content diff D1): the inventory is the OWN-CONTENT HOUSE
    STANDARD (:func:`rvt.genesis.house_standard.build_catalog`) — 234
    elements built purely from OUR value tables (facts / public standards /
    values we invented), with the Autodesk resource-identifier dispositions
    applied (``scrub``: 'full' = descriptors blanked + our visibility policy;
    'safe' = name/label/number overlays only — the fallback the reader-
    tolerance probes bisect against; 'none' = raw constructor output).

    Every cross-reference points at OUR OWN elements; self-containment is
    asserted by the dangling-reference check (must be EMPTY).
    ``project_name`` / ``project_number`` are accepted for API compatibility;
    the values come from ``house_standard.PROJECT_INFO``.
    """
    if scrub not in hs.SCRUB_LEVELS:
        raise ValueError(f"scrub must be one of {hs.SCRUB_LEVELS}")
    cat = hs.build_catalog(int(start_id), scrub=scrub)
    return OurContent(elements=cat.elements, manifest=cat.manifest, ids=dict(cat.ids),
                      start_id=cat.start_id, last_id=cat.last_id,
                      roundtrip=cat.roundtrip(), dangling=cat.dangling(),
                      catalog=cat, scrub=scrub)


def _roundtrip(records) -> dict:
    ok = fail = 0
    failures: List[str] = []
    for r in records:
        rep = r.roundtrip()
        good = rep.get("ok")
        if good is None:                                  # SkelElement shape
            good = all(v.get("clean") and v.get("byte_exact")
                       for k, v in rep.items() if k != "ok")
        if good:
            ok += 1
        else:
            fail += 1
            failures.append(f"{r.class_name}#{r.elem_id}: "
                            f"{ {k: v for k, v in rep.items() if k != 'ok'} }"[:300])
    return {"records": len(records), "ok": ok, "failed": fail, "failures": failures[:20]}


def _dangling_references(records) -> List[dict]:
    """Every positive ElementId one of OUR records references must be another
    of OUR records.  Uses the types stream's reference extractor (which
    excludes the compound-structure / geometry topology subtrees whose small
    integers are indices, not element ids)."""
    mine = {int(r.elem_id) for r in records}
    # small integers that are ENUM values, not element ids
    not_ids = {"m_systemFamilyIdx"}
    bad: List[dict] = []
    for r in records:
        tr = r if isinstance(r, ty.TypeRecord) else r.as_type_record()
        for path, i in ty._element_refs(tr):
            if path.rsplit(".", 1)[-1].split("[")[0] in not_ids:
                continue
            if i > 0 and i not in mine:
                bad.append({"elem_id": int(r.elem_id), "class": r.class_name,
                            "path": path, "target": int(i)})
    return bad


def encode_content(content: OurContent) -> Tuple[List[Dict[int, bytes]], list]:
    """-> (records_by_element, elemrec_plans) for commit_new_elements."""
    recs = [{seq: b for seq, b in zip((101, 102, 103), ty._encode_element(el))}
            for el in content.elements]
    return recs, [el.elemrec for el in content.elements]


# ---------------------------------------------------------------------------
# certification helpers (validator + provenance ledger)
# ---------------------------------------------------------------------------

def run_validator(path: str) -> dict:
    from rvt.validate import validate_file
    t0 = time.time()
    rep = validate_file(path)
    return {"ok": bool(rep.ok), "errors": len(rep.errors),
            "warnings": len(rep.warnings),
            "error_messages": [f"[{f.layer}] {f.where}: {f.message}"[:300]
                               for f in rep.errors[:10]],
            "warning_messages": [f"[{f.layer}] {f.where}: {f.message}"[:200]
                                 for f in rep.warnings[:10]],
            "stats": {k: v for k, v in rep.stats.items()
                      if k in ("streams", "records", "elements_decoded",
                               "refs_checked", "partition_blocks", "decode_failures")},
            "seconds": round(time.time() - t0, 1)}


def run_ledger(path: str, baseline_path: str, json_out: Optional[str] = None) -> dict:
    """Provenance ledger of ``path`` against the sample it descends from.
    Returns a compact summary (the full report is written to ``json_out``)."""
    from rvt.mutate import Document
    from rvt.provenance import provenance, format_report
    t0 = time.time()
    doc = Document.from_file(path)
    base = Document.from_file(baseline_path)
    rep = provenance(doc, base, examples=3, with_units=True)
    rep["elapsed_s"] = round(time.time() - t0, 1)
    if json_out:
        with open(json_out, "w") as fh:
            json.dump(rep, fh, indent=1, default=str)
        with open(os.path.splitext(json_out)[0] + ".txt", "w") as fh:
            fh.write(format_report(rep, show_examples=True, max_classes=12))
    tot = rep.get("provenance_totals", {})
    derived = sum(tot.get(p, 0) for p in ("autodesk-sample", "ours-modified",
                                            "transitive-cloned"))
    per_cat_derived = {}
    for cat, info in rep.get("categories", {}).items():
        n = sum(info["counts"].get(p, 0) for p in
                ("autodesk-sample", "ours-modified", "transitive-cloned"))
        if n:
            per_cat_derived[cat] = n
    return {
        "host_elements": rep.get("host_elements"),
        "totals": tot,
        "derived_total": derived,
        "autodesk_sample": tot.get("autodesk-sample", 0),
        "transitive_cloned": tot.get("transitive-cloned", 0),
        "ours_created": tot.get("ours-created", 0),
        "ours_modified": tot.get("ours-modified", 0),
        "unmatched": tot.get("unmatched", 0),
        "embedded_family_documents": rep.get("embedded_family_documents"),
        "derived_by_category": per_cat_derived,
        "gate_G1": {k: v for k, v in rep.get("gate_G1", {}).items()
                    if k in ("passes", "verdict")},
        "gap_list": rep.get("gate_G1", {}).get("gap_list", []),
        "seconds": rep.get("elapsed_s"),
    }


def certify(path: str, tag: str, out_dir: str) -> dict:
    """Validator + provenance ledger for one emitted file; JSON side files."""
    v = run_validator(path)
    with open(os.path.join(out_dir, f"{tag}_validate.json"), "w") as fh:
        json.dump(v, fh, indent=1)
    p = run_ledger(path, BASELINE, os.path.join(out_dir, f"{tag}_provenance.json"))
    size = os.path.getsize(path)
    print(f"    [{tag}] size {size:>9,} B | validator ok={v['ok']} "
          f"(errors {v['errors']}, warnings {v['warnings']}) | ledger: "
          f"sample={p['autodesk_sample']:,} cloned={p['transitive_cloned']:,} "
          f"created={p['ours_created']:,} modified={p['ours_modified']:,} "
          f"| family docs {p['embedded_family_documents']}")
    return {"file": os.path.relpath(path, ROOT), "bytes": size,
            "validator": v, "provenance": p}


# ---------------------------------------------------------------------------
# ledger v2 state helpers
# ---------------------------------------------------------------------------

def source_watermark(path: str) -> int:
    """``IdentifierSource.m_last`` (ElemTable footer last_id) of a file."""
    with open_rvt(path) as f:
        model = se.decode_elemtable(f.inflate("Global/ElemTable"))
    return int(model["footer"]["last_id"])


def template_document_guid(path: str) -> str:
    """The base document's Unique Document GUID (== History entry[0])."""
    with open_rvt(path) as f:
        raw = f.logical("BasicFileInfo")
    return se.decode_basic_file_info(raw)["unique_document_guid"]


def _lineage_seed(st: dict, lineage_watermark: int) -> set:
    """Every host element that descends from the Autodesk lineage (id <= the
    base's watermark).  OUR elements all sit above it."""
    return {e for e in st["host"] if e <= lineage_watermark}


# ---------------------------------------------------------------------------
# the stages
# ---------------------------------------------------------------------------

def stage_insert(src: str, out: str, content: OurContent, out_dir: str) -> dict:
    """G0a: commit OUR content into a copy of the base, then re-emit through
    the canonical unit-0 re-blocker (an empty delete) so no oversized block
    survives from the append."""
    t0 = time.time()
    recs, plans = encode_content(content)
    tmp = os.path.join(out_dir, "_G0a_appended.rvt")
    doc_guid = template_document_guid(src)
    rep = commit_new_elements(src, tmp, recs, plans,
                              identity={"document_guid": doc_guid,
                                        "author": AUTHOR, "client_app_name": AUTHOR})
    ver = verify_written(tmp, [el.elem_id for el in content.elements])
    clean_ids = sum(1 for s in ver["new_ids_found"].values()
                    for v in s.values() if v.get("clean") is not False)
    # canonical re-blocking pass (identity delete)
    rr = delete_elements(tmp, out, [])
    try:
        os.remove(tmp)
    except OSError:
        pass
    return {"stage": "G0a", "op": "insert our content into the base + re-block",
            "new_elements": len(content.elements),
            "elemtable_after": rep.elemtable_count_after,
            "watermark_after": rep.watermark_after,
            "verify_written": {"crc_failures": ver["crc_failures"],
                               "ecc_mismatches": ver["ecc_mismatches"],
                               "walker_errors": ver["walker_errors"],
                               "stamps_ok": ver["stamps_ok"],
                               "new_records_found": clean_ids},
            "reblock": {"blocks_before": rr.blocks_before, "blocks_after": rr.blocks_after},
            "seconds": round(time.time() - t0, 1)}


def stage_delete_lineage(src: str, out: str, lineage_watermark: int, *,
                         name: str) -> dict:
    """Delete every Autodesk-lineage host element that maximal garbage
    collection can release (validator-clean by construction).  What remains of
    the lineage is exactly what something OUTSIDE the seed still references
    (embedded family-document elements) — the pin evidence names it."""
    t0 = time.time()
    st = build_state_v2(src)
    seed = _lineage_seed(st, lineage_watermark)
    delete, keep, ev = maxgc(st, seed)
    rep = delete_elements(src, out, delete)
    v = verify_reduced(out, delete)
    kept_classes = Counter(st["cls_of"].get(k, "?") for k in keep).most_common(30)
    return {"stage": name, "op": "maximal GC delete of the Autodesk lineage",
            "lineage_seed": len(seed), "deleted": len(delete),
            "lineage_kept_pinned": len(keep),
            "kept_by_class": kept_classes,
            "pin_evidence_top": ev.get("top_pinning_pairs", [])[:12],
            "elemtable_before": rep.elemtable_count_before,
            "elemtable_after": rep.elemtable_count_after,
            "structural_ok": v["ok"], "structural_notes": v.get("walker_errors", [])[:5],
            "seconds": round(time.time() - t0, 1)}, keep


def stage_remove_all_units(src: str, out: str) -> dict:
    """Splice out EVERY remaining embedded family document (save units 1..k
    + their Global/ContentDocuments entries), after asserting no host
    element references any unit-internal id."""
    t0 = time.time()
    from rvt.families import FamilyIndex
    idx = FamilyIndex.open(src)
    st = build_state_v2(src)
    host = set(st["host"])
    unit_ids: Dict[int, set] = {}
    guids: List[str] = []
    for u in idx.units:
        if not u.index:
            continue
        recs = idx.unit_records(u.index)
        uids = set()
        for s in (101, 102, 103):
            uids |= set(recs.get(s, {}).keys())
        unit_ids[u.index] = uids
        if u.guid:
            guids.append(str(u.guid).lower())
    # safety: does any HOST element reference an id inside any unit?
    host_to_unit = []
    for h in host:
        for tgt in st["graph"].get(h, ()):
            for u, uids in unit_ids.items():
                if tgt in uids:
                    host_to_unit.append((h, st["cls_of"].get(h, "?"), u, tgt))
    if host_to_unit:
        return {"stage": "G0c", "op": "remove all embedded family documents",
                "aborted": True, "reason": "host elements still reference unit ids",
                "host_to_unit_refs": host_to_unit[:20],
                "seconds": round(time.time() - t0, 1)}
    urep = remove_units(src, out, set(guids))
    v = verify_reduced(out, [])
    return {"stage": "G0c", "op": "remove all embedded family documents",
            "units_before": urep["units_before"], "units_after": urep["units_after"],
            "removed_units": len(urep["removed_units"]),
            "removed_guids": guids,
            "partition_logical_before": urep["partition_logical_before"],
            "partition_logical_after": urep["partition_logical_after"],
            "cd_entries_before": urep["cd_entries_before"],
            "cd_entries_after": urep["cd_entries_after"],
            "cd_payload_after": urep["cd_payload_after"],
            "structural_ok": v["ok"],
            "seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------------------
# OUR metadata streams (the sample's must not ride along)
# ---------------------------------------------------------------------------
# Two raw (unframed, uncompressed-container) metadata streams inherited from
# the base still carried the SAMPLE's authored project metadata AND an
# Autodesk employee's local file paths — the same "live contamination" the
# identity policy scrubs from BasicFileInfo, in two more streams:
#   * ProjectInformation — a ZIP wrapping the PartAtom-namespace
#     ``project.xml`` (Atom entry: project title + Project Information
#     parameters).  The sample's says <title>rstbasicsampleproject</title>,
#     "Client Name: Autodesk", "Sample House", and its ZIP member NAME is
#     C:\Users\<employee>\AppData\Local\Temp\...project.xml.
#   * TransmissionData — ``u32 UTF-16-code-unit count + UTF-16LE XML``
#     (Autodesk documents Read/WriteTransmissionData): external file
#     references.  The sample's names a keynote table, an assembly-code table
#     and a Revit link — three ELEMENT IDS that no longer exist in G0 — plus
#     C:\Users\<employee>\Desktop\... absolute paths.
# We regenerate both from OUR ProjectInfo values / OUR (empty) external
# reference set.  The XML element names, namespace URIs and structure are
# format vocabulary (interoperability); the VALUES are ours.

PARTATOM_NS = "urn:schemas-autodesk-com:partatom"
ATOM_NS = "http://www.w3.org/2005/Atom"


def our_project_information_zip(document_guid: str, *, filename: str = "G0.rvt") -> bytes:
    """OUR ``ProjectInformation`` stream: ZIP { <name>.project.xml }."""
    import io
    import zipfile
    from xml.sax.saxutils import escape as _x
    pm = PROJECT_META
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<entry xmlns="{ATOM_NS}" xmlns:A="{PARTATOM_NS}">'
        f'<title>{_x(pm["project_name"])}</title>'
        f'<updated>{TIMESTAMP_ISO}</updated>'
        '<A:taxonomy><term>adsk:revit</term><label>Autodesk Revit</label></A:taxonomy>'
        '<A:taxonomy><term>adsk:revit:grouping</term>'
        '<label>Autodesk Revit Grouping</label></A:taxonomy>'
        '<link rel="design-2d" type="application/rvt" href=".">'
        '<A:design-file>'
        f'<A:title>{_x(filename)}</A:title>'
        '<A:product>Revit</A:product>'
        '<A:product-version>2026</A:product-version>'
        f'<A:updated>{TIMESTAMP_ISO}</A:updated>'
        '</A:design-file></link>'
        '<A:features><A:feature><A:title>Project Information</A:title>'
        '<A:group><A:title>Identity Data</A:title>'
        f'<Project_Issue_Date displayName="Project Issue Date" type="system" '
        f'typeOfParameter="Text">{_x(pm["issue_date"])}</Project_Issue_Date>'
        f'<Project_Status displayName="Project Status" type="system" '
        f'typeOfParameter="Text">{_x(pm["project_status"])}</Project_Status>'
        f'<Client_Name displayName="Client Name" type="system" '
        f'typeOfParameter="Text">{_x(pm["client_name"])}</Client_Name>'
        f'<Project_Address displayName="Project Address" type="system" '
        f'typeOfParameter="Multiline Text">{_x(pm["address"])}</Project_Address>'
        f'<Project_Name displayName="Project Name" type="system" '
        f'typeOfParameter="Text">{_x(pm["project_name"])}</Project_Name>'
        f'<Project_Number displayName="Project Number" type="system" '
        f'typeOfParameter="Text">{_x(pm["project_number"])}</Project_Number>'
        '</A:group></A:feature></A:features></entry>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(f"Revit{document_guid}.project.xml",
                             date_time=(2026, 8, 3, 12, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, xml.encode("utf-8"))
    return buf.getvalue()


def our_transmission_data() -> bytes:
    """OUR ``TransmissionData`` stream: NO external file references (G0 has
    no keynote table, no assembly-code table, no links).  Framing = u32
    UTF-16 code-unit count + UTF-16LE XML."""
    xml = ('<?xml version="1.0"?>\n<TransmissionData isTransmitted="false" '
           'userData="" version="5"></TransmissionData>')
    body = xml.encode("utf-16-le")
    return struct.pack("<I", len(body) // 2) + body


def stage_own_save(src: str, out: str, *, project_last_save_path: str = "G0.rvt") -> dict:
    """The genesis SAVE: prepend a History episode whose GUID becomes OUR
    document GUID; make DocumentIncrementTable / Contents / BasicFileInfo
    coherent (record_save); re-stamp every element as created+modified in
    the genesis episode; assert OUR authoring identity in BasicFileInfo."""
    t0 = time.time()
    entries = read_entries(src)
    new_streams: Dict[str, bytes] = {}
    with open_rvt(src) as f:
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
        hist = se.decode_history(f.inflate("Global/History"))
        dit = se.decode_increment_table(f.inflate("Global/DocumentIncrementTable"))
        con = se.decode_contents(f.inflate("Contents"))
        con_prefix = f.prefix("Contents")
        bfi = se.decode_basic_file_info(f.logical("BasicFileInfo"))
        prefixes = {n: f.prefix(n) for n in
                    ("Global/ElemTable", "Global/History",
                     "Global/DocumentIncrementTable")}
        # -- the coordinated save --------------------------------------------
        n_elem = len(et["records"])
        srep = ed.record_save(
            {"History": hist, "DocumentIncrementTable": dit, "Contents": con,
             "BasicFileInfo": bfi},                       # ElemTable episodes set below
            new_element_ids=(), username=USERNAME,
            element_record_count=n_elem, timestamp=TIMESTAMP,
            last_save_path=os.path.basename(out))
        ep = int(srep["episode_id"])
        # every element of this document was created + last modified in the
        # genesis episode (its entire inventory is ours, born in this save)
        et["records"] = [(r[0], ep, ep, ep, r[4], r[5], r[6]) for r in et["records"]]
        # -- OUR identity: EVERY save episode is signed by us (the V32
        #    DocumentIncrementTable username scrub, viewer-PASSED 2026-08-03).
        #    The inherited lineage carried 22 Autodesk-employee usernames — the
        #    provenance ledger v2 identity layer blocks G1 on them.
        scrubbed_usernames = 0
        for key in ("records", "records2"):
            for row in dit.get(key) or []:
                if isinstance(row, dict) and row.get("username") != USERNAME:
                    row["username"] = USERNAME
                    scrubbed_usernames += 1
        # -- OUR identity (author strings; GUID == the new episode's) ------
        bfi2 = own_identity_model(bfi, out_path=out, username=USERNAME,
                                  document_guid=srep["episode_guid"],
                                  author=AUTHOR, client_app_name=AUTHOR,
                                  keep_version_marker=True)
        # keep the increments string coherent (own_identity_model does not touch it)
        bfi2["unique_document_increments"] = bfi["unique_document_increments"]
        bfi2["central_version_number"] = bfi["central_version_number"]
        # -- re-encode + re-frame -------------------------------------------
        new_streams["Global/ElemTable"] = ecc.frame_stream(
            prefixes["Global/ElemTable"] + gzip_member(se.encode_elemtable(et), level=3))
        new_streams["Global/History"] = ecc.frame_stream(
            prefixes["Global/History"] + gzip_member(se.encode_history(hist), level=3))
        new_streams["Global/DocumentIncrementTable"] = ecc.frame_stream(
            prefixes["Global/DocumentIncrementTable"]
            + gzip_member(se.encode_increment_table(dit), level=3))
        new_streams["Contents"] = ecc.frame_stream(
            con_prefix + gzip_member(se.encode_contents(con), level=3))
        new_streams["BasicFileInfo"] = se.encode_basic_file_info(bfi2, regenerate_mirror=True)
        # -- OUR metadata streams (raw, unframed) --------------------------
        stream_names = {s.name for s in f.streams()}
        meta_replaced: List[str] = []
        if "ProjectInformation" in stream_names:
            new_streams["ProjectInformation"] = our_project_information_zip(
                srep["episode_guid"], filename=os.path.basename(out))
            meta_replaced.append("ProjectInformation")
        if "TransmissionData" in stream_names:
            new_streams["TransmissionData"] = our_transmission_data()
            meta_replaced.append("TransmissionData")
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out, out_entries)
    return {"stage": "G0", "op": "coordinated own-save + own identity + own metadata",
            "episode_id": ep, "episode_guid": srep["episode_guid"],
            "document_guid": srep["episode_guid"],
            "history_count": srep["history_count"], "increments": srep["increments"],
            "elements_restamped": n_elem, "author": AUTHOR, "username": USERNAME,
            "dit_usernames_scrubbed": scrubbed_usernames,
            "metadata_streams_replaced": meta_replaced,
            "seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def build_ladder(out_dir: str = OUT_DIR, *, base: str = BASE,
                 scrub: str = "full", tag_prefix: str = "G0",
                 certify_rungs: bool = True) -> dict:
    """Run the whole G0 ladder; return the pipeline record (also written).

    ``scrub`` selects the house-standard scrub level of OUR content
    ('full' = the certified own-content form; 'safe' = the reader-tolerance
    fallback).  ``tag_prefix`` names the emitted rungs (``G0a..G0`` for the
    primary ladder); ``certify_rungs=False`` skips the per-rung validator +
    provenance certification (used for the fast 'safe' twin whose intermediate
    rungs are discarded).
    """
    os.makedirs(out_dir, exist_ok=True)
    t_all = time.time()
    pipe: Dict[str, Any] = {"base": os.path.relpath(base, ROOT),
                            "baseline_sample": os.path.relpath(BASELINE, ROOT),
                            "scrub": scrub, "tag_prefix": tag_prefix,
                            "stages": [], "files": {}}
    wm = source_watermark(base)
    start_id = ((wm // 100_000) + 1) * 100_000
    print(f"== base {os.path.basename(base)}: lineage watermark {wm:,}; "
          f"our ids from {start_id:,}  (scrub={scrub}, prefix={tag_prefix})")
    pipe["lineage_watermark"] = wm
    pipe["our_id_start"] = start_id

    # ---- OUR content --------------------------------------------------------
    t0 = time.time()
    content = build_our_content(start_id, scrub=scrub)
    print(f"== OUR content: {len(content.elements)} elements "
          f"(ids {content.start_id:,}..{content.last_id:,}); round-trip "
          f"{content.roundtrip['ok']}/{content.roundtrip['records']}; "
          f"dangling refs {len(content.dangling)} ({time.time() - t0:.1f}s)")
    for fmsg in content.roundtrip["failures"][:8]:
        print("   ROUNDTRIP FAIL:", fmsg)
    for d in content.dangling[:8]:
        print("   DANGLING:", d)
    if content.roundtrip["failed"] or content.dangling:
        raise SystemExit("OUR content is not clean/self-contained — refusing to assemble")
    kinds = Counter(m["kind"] for m in content.manifest)
    classes = Counter(m["class"] for m in content.manifest)
    if tag_prefix == "G0":
        with open(os.path.join(out_dir, "G0_manifest.json"), "w") as fh:
            json.dump({"generator": "tools/genesis_assemble.py",
                       "author": AUTHOR, "id_range": [content.start_id, content.last_id],
                       "element_count": len(content.manifest),
                       "content_source": "rvt.genesis.house_standard.build_catalog",
                       "scrub": scrub,
                       "by_kind": kinds.most_common(),
                       "by_class": classes.most_common(),
                       "named_ids": content.ids,
                       "roundtrip": content.roundtrip,
                       "dangling_references": content.dangling,
                       "elements": content.manifest}, fh, indent=1)
    pipe["our_content"] = {"elements": len(content.elements),
                           "id_range": [content.start_id, content.last_id],
                           "content_source": "rvt.genesis.house_standard.build_catalog",
                           "scrub": scrub,
                           "by_kind": kinds.most_common(),
                           "roundtrip_ok": f"{content.roundtrip['ok']}/{content.roundtrip['records']}",
                           "dangling_references": len(content.dangling)}

    files = pipe["files"]
    tp = tag_prefix

    def cert(path: str, tag: str) -> dict:
        if certify_rungs:
            return certify(path, tag, out_dir)
        return {"file": os.path.relpath(path, ROOT), "bytes": os.path.getsize(path),
                "validator": run_validator(path), "provenance": None}

    # ---- G0a: insert ---------------------------------------------------------
    G0a = os.path.join(out_dir, f"{tp}a.rvt")
    print(f"== {tp}a: insert our content into the base")
    r = stage_insert(base, G0a, content, out_dir)
    pipe["stages"].append(r)
    files[f"{tp}a"] = cert(G0a, f"{tp}a")

    # ---- G0b: delete the Autodesk lineage (first GC pass) -----------------
    G0b = os.path.join(out_dir, f"{tp}b.rvt")
    print(f"== {tp}b: maximal-GC delete of every Autodesk element")
    r, kept_b = stage_delete_lineage(G0a, G0b, wm, name=f"{tp}b")
    pipe["stages"].append(r)
    files[f"{tp}b"] = cert(G0b, f"{tp}b")

    # ---- G0c: remove every embedded family document ----------------------
    G0c = os.path.join(out_dir, f"{tp}c.rvt")
    print(f"== {tp}c: remove all embedded family documents")
    r = stage_remove_all_units(G0b, G0c)
    pipe["stages"].append(r)
    if r.get("aborted"):
        print("   ABORTED:", r["reason"])
        _write_pipeline(pipe, out_dir, t_all)
        return pipe
    files[f"{tp}c"] = cert(G0c, f"{tp}c")

    # ---- G0d: second GC pass (nothing left to pin the lineage) -------------
    G0d = os.path.join(out_dir, f"{tp}d.rvt")
    print(f"== {tp}d: second GC pass — release the lineage residue")
    r, kept_d = stage_delete_lineage(G0c, G0d, wm, name=f"{tp}d")
    pipe["stages"].append(r)
    files[f"{tp}d"] = cert(G0d, f"{tp}d")

    # ---- G0: the coordinated own-save + our identity -------------------------
    G0 = os.path.join(out_dir, f"{tp}.rvt")
    print(f"== {tp}: coordinated own-save (our episode / GUID / identity / username scrub)")
    r = stage_own_save(G0d, G0)
    pipe["stages"].append(r)
    files[tp] = cert(G0, tp)

    pipe["content_ids"] = {"named": content.ids}
    _write_pipeline(pipe, out_dir, t_all, name=f"{tp}_pipeline.json")
    return pipe


def _write_pipeline(pipe: dict, out_dir: str, t_all: float, name: str = "G0_pipeline.json") -> None:
    pipe["total_seconds"] = round(time.time() - t_all, 1)
    with open(os.path.join(out_dir, name), "w") as fh:
        json.dump(pipe, fh, indent=1, default=str)
    print(f"== pipeline record: {os.path.join(out_dir, name)} "
          f"({pipe['total_seconds']}s total)")



# ===========================================================================
# GENESIS-2 — OUR ADOCUMENT (Global/Latest constructed, not carried)
# ===========================================================================
#
# The stream ``Global/Latest`` is the serialized ``ADocument`` object graph
# (class 0x1c) — decoded/re-encoded byte-exactly by ``rvt.adocument``.  In
# G0 it is the rst sample's document object VERBATIM: 1.59 MB whose element
# registries enumerate ~6,400 element ids of the deleted sample inventory
# (ALL dangling; 0 of ours), whose name caches carry the sample's room /
# sheet / assembly names and usernames, whose loaded-content registry lists 52
# content documents G0 no longer has, and whose ESSchemaStorage carries the
# 1.33 MB Autodesk unit/spec/parameter-group JSON corpus (product data,
# byte-identical in all six samples — docs/writer/latest-regions.md).
#
# GENESIS-2 CONSTRUCTS our own document object from the decoded tree:
#
#   1. a SCHEMA-TYPED PURGE — every value whose serialized type is ElementId
#      (found by walking each object body in parallel with the archive class
#      map, ~14.6k leaves) and whose id is not one of OUR elements is a
#      dangling reference: registry entries keyed by / valuing it are dropped,
#      positional and parallel arrays are nulled in place, scalar members set
#      invalid.  Result: ZERO dangling ElementIds (the orchestrator's ruling
#      after G0 FAILED the Autodesk viewer).  Never touches the fixed 241-slot
#      AppInfo registry itself (its objects carry the archive pids the
#      graph's weak references target).
#   2. COHERENCE — the loaded-content registry (ContentTable) is emptied to
#      match G0's empty Global/ContentDocuments.
#   3. REPOPULATION (candidate/purity modes) — the registries are refilled
#      to index EXACTLY our inventory, driven by semantics DERIVED from the
#      six samples and frozen in ``G1_registry_maps.json`` (position/enum
#      tables that are compiled-in constants, verified cross-sample).
#   4. AUTHORSHIP — the sample's name caches, per-user maps, link-reconcile
#      datasets are emptied; the "saved by" build list becomes the product
#      constant (or, in max-purity mode, our own honest string); the Forge
#      corpus is carried-and-flagged (candidate) or emptied (max-purity).
#
# Every emitted tree is re-encoded, re-decoded and compared for equality
# before a file is written; every file must validate with 0 errors.

#: samples the registry semantics are derived from (dach excluded: workshared,
#: its ADocument classifies 51.9 % — docs/writer/latest-regions.md §5)
DERIVE_SAMPLES = ["rstbasicsampleproject", "racbasicsampleproject", "rmebasicsampleproject",
                  "racadvancedsampleproject", "rstadvancedsampleproject"]
G1_REGISTRY_MAPS = os.path.join(OUT_DIR, "G1_registry_maps.json")

#: the LAST ``m_storedByRevitBuild`` entry of EVERY Revit-2026 file (a product
#: constant identifying the format/build the file conforms to — the same
#: build string ``rvt.identity`` keeps in BasicFileInfo; counsel item C1).
PRODUCT_BUILD_STRING_2026 = "Revit 2026 2026 (2026.000) : 20250227_1515(x64)"
#: OUR honest "saved by" string (max-purity mode; unverified reader tolerance)
OUR_BUILD_STRING = f"{AUTHOR} genesis writer 0.1 (Revit-2026 format, sync 2662) : 20250227_1515(x64)"

#: field paths (Class.field) that are POSITIONAL id arrays — the index, not
#: membership, carries the meaning; dangling ids are nulled in place, never
#: dropped (that would shift positions).  Auto-detection also treats any
#: ElementId container that already contains a -1, and any container in a
#: cross-sample-verified PARALLEL group, as positional.
POSITIONAL_ID_FIELDS = {
    "UniqueElementsTracking.m_elemIds",       # slot -> singleton class (72/72 stable)
    "CategoryToIdMap.m_ids",                  # parallel to m_categoryIds
    "DBViewInfo.m_defaultTemplateIds",        # per-view-type default template
}

#: name caches / per-user maps / lineage datasets holding the SAMPLE
#: PROJECT's authored data — emptied in candidate + purity modes
#: (docs/writer/adocument.md §5, docs/writer/latest-regions.md §3).
SAMPLE_DATA_CACHES = [
    ("NewItemNumber", "m_items"),                          # 'FOUNDATION-2700', 'L1 wall frame hall 5', ...
    ("WorksharingDisplaySettingsTracking", "m_userToSettingsMap"),   # user 'liqi'
    ("TemporaryViewPropertiesMenu", "m_userToRecentlyUsedTVPMap"),   # user 'macalis'
    ("AppInfoElementsAssociations", "m_RepoByName"),           # LB_Associations reconcile map (sample ids as TEXT)
    ("EStorageTracking", "m_trackingItems"),                    # the sample's ES entities (dropped elements)
    ("ExternalParamTracking", "m_companyNameMap"),
    ("ExternalResourceErrorAppInfo", "m_addInInfos"),          # keynote/assembly DB-server descriptor (no keynote table in G0)
]


# ---------------------------------------------------------------------------
# 1. registry semantics derived from the samples (frozen as JSON)
# ---------------------------------------------------------------------------

def derive_registry_maps(samples: Sequence[str] = tuple(DERIVE_SAMPLES),
                         verbose: bool = True) -> dict:
    """Derive the ADocument registry SEMANTICS from the sample corpus.

    * ``UET_POS_TO_CLASS`` — UniqueElementsTracking.m_elemIds is a POSITIONAL
      table: position -> the class of the singleton element it holds
      (verified identical in every sample: a compiled-in registration order).
    * ``DEF_GROUP_TO_CLASS`` — SymbolIdMgr.m_defElementTypeMap key (the
      ElementTypeGroup enum) -> the class of the default type it holds
      (majority; disagreements are only present-vs-absent).
    * ``ETD_SYMBOL_CATEGORY_CLASSES`` / ``ETD_ELEM_CATEGORY_CLASSES`` —
      ElementTrackingData m_symbols / m_elems: built-in category (OST enum) ->
      the classes of the elements it tracks (union over samples).
    * ``CUSTOM_ELEMENT_DATATYPE_GUID_TO_CELL`` — CustomElementTracking map key
      (the custom-element data-type GUID) -> the class of the custom element's
      FIRST cell (its data type: RbsConductorMaterial ...).
    * ``SFN_TRACKED_CLASSES`` — the type classes AppInfoSystemFamiliesNames
      indexes (its integer keys are DOCUMENT-LOCAL allocations: only 30/161
      agree across samples, so keys are never reused, only the class set).
    * ``PARALLEL_GROUPS`` — sibling containers whose lengths are equal in
      EVERY sample where the owning class appears (true parallel arrays, e.g.
      CategoryToIdMap.m_categoryIds/m_ids, SymbolIdMgr.m_paramSetKeys/
      m_paramSets) -> the purge nulls in place instead of dropping.
    """
    from rvt.mutate import Document
    uet: Dict[int, Counter] = collections.defaultdict(Counter)
    det: Dict[int, Counter] = collections.defaultdict(Counter)
    etd_s: Dict[int, Counter] = collections.defaultdict(Counter)
    etd_e: Dict[int, Counter] = collections.defaultdict(Counter)
    cet: Dict[str, Counter] = collections.defaultdict(Counter)
    sfn: Counter = Counter()
    # parallel-group detection: (class, tuple(sorted field names)) -> {sample: equal_lengths?}
    par_seen: Dict[Tuple[str, Tuple[str, ...]], Dict[str, bool]] = collections.defaultdict(dict)
    used: List[str] = []
    for s in samples:
        path = os.path.join(SAMPLES_DIR, f"{s}.rvt")
        if not os.path.exists(path):
            if verbose:
                print(f"   [derive] skip {s} (no file)")
            continue
        t0 = time.time()
        adocx = adoc.open_document_object(path)
        doc = Document.load(s)
        used.append(s)

        def cls(i: int) -> str:
            return (doc.class_of(i) or "?") if i > 0 else str(i)

        u = adocx.appinfo("UniqueElementsTracking") or {}
        for i, e in enumerate(u.get("m_elemIds") or []):
            if e != -1:
                uet[i][cls(e)] += 1
        sm = adocx.appinfo("SymbolIdMgr") or {}
        for p in sm.get("m_defElementTypeMap") or []:
            det[int(p["first"])][cls(p["second"])] += 1
        etd = adocx.appinfo("ElementTrackingData") or {}
        for e in etd.get("m_symbols") or []:
            for i in e["m_elemIdSet"]:
                etd_s[int(e["m_categoryId"])][cls(i)] += 1
        for e in etd.get("m_elems") or []:
            for i in e["m_elemIdSet"]:
                etd_e[int(e["m_categoryId"])][cls(i)] += 1
        ce = adocx.appinfo("CustomElementTracking") or {}
        for p in ce.get("m_dataTypeToElementIdsMap") or []:
            g = str(p["first"]["m_value"])
            for i in p["second"]["m_elemIdSet"]:
                v = doc.value(i) or {}
                cells = ((v.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
                cet[g][cells[0].get("ptr_class") if cells else "?"] += 1
        sf = adocx.appinfo("AppInfoSystemFamiliesNames") or {}
        for p in sf.get("m_idMap") or []:
            for i in p["second"]["m_elementIds"]:
                sfn[cls(i)] += 1
        # parallel containers: for every dict in every appinfo body, sibling
        # list-valued fields with equal length >= 1
        for x in adocx.appinfo_array():
            if not (isinstance(x, dict) and x.get("ptr_class")):
                continue
            _scan_parallel(x.get("value"), x["ptr_class"], par_seen, s)
        if verbose:
            print(f"   [derive] {s}: uet {sum(1 for c in uet.values() if c)} "
                  f"det {len(det)} etd {len(etd_s)}/{len(etd_e)} cet {len(cet)} "
                  f"({time.time() - t0:.1f}s)")

    def majority(c: Counter) -> Optional[str]:
        c2 = Counter({k: v for k, v in c.items() if k not in ("-1", "0", "?")})
        return c2.most_common(1)[0][0] if c2 else None

    uet_map = {str(p): majority(c) for p, c in sorted(uet.items()) if majority(c)}
    det_map = {str(g): majority(c) for g, c in sorted(det.items()) if majority(c)}
    class_to_groups: Dict[str, List[int]] = collections.defaultdict(list)
    for g, c in det_map.items():
        class_to_groups[c].append(int(g))
    etd_sym = {str(k): sorted(x for x in v if not x.startswith(("-", "?", "0")))
               for k, v in sorted(etd_s.items())}
    etd_elm = {str(k): sorted(x for x in v if not x.startswith(("-", "?", "0")))
               for k, v in sorted(etd_e.items())}
    class_to_sym_cat: Dict[str, List[int]] = collections.defaultdict(list)
    for k, cs in etd_sym.items():
        for c in cs:
            class_to_sym_cat[c].append(int(k))
    class_to_elem_cat: Dict[str, List[int]] = collections.defaultdict(list)
    for k, cs in etd_elm.items():
        for c in cs:
            class_to_elem_cat[c].append(int(k))
    cet_map = {g: majority(c) for g, c in cet.items() if majority(c)}
    # parallel groups equal in every sample where present
    parallel: Dict[str, List[List[str]]] = collections.defaultdict(list)
    for (cls_name, fields), by_sample in par_seen.items():
        if by_sample and all(by_sample.values()) and len(by_sample) >= 2:
            parallel[cls_name].append(list(fields))
    maps = {
        "generator": "tools/genesis_assemble.py --only maps",
        "derived_from": used,
        "derived_at": TIMESTAMP_ISO,
        "note": ("Registry SEMANTICS of the ADocument (position / enum tables that are "
                 "compiled-in Revit constants), derived by decoding the samples' "
                 "Global/Latest and attributing each id to its element class. These are "
                 "format facts (like the built-in category enum), not sample expression: "
                 "no id, name or value is copied — only which CLASS a slot / group / "
                 "category / GUID stands for."),
        "UET_POS_TO_CLASS": uet_map,
        "DEF_GROUP_TO_CLASS": det_map,
        "CLASS_TO_DEF_GROUPS": {k: sorted(v) for k, v in sorted(class_to_groups.items())},
        "ETD_SYMBOL_CATEGORY_CLASSES": etd_sym,
        "ETD_ELEM_CATEGORY_CLASSES": etd_elm,
        "CLASS_TO_ETD_SYMBOL_CATEGORIES": {k: sorted(v) for k, v in sorted(class_to_sym_cat.items())},
        "CLASS_TO_ETD_ELEM_CATEGORIES": {k: sorted(v) for k, v in sorted(class_to_elem_cat.items())},
        "CUSTOM_ELEMENT_DATATYPE_GUID_TO_CELL": cet_map,
        "SFN_TRACKED_CLASSES": sorted(c for c in sfn if c and not c.startswith(("-", "?"))),
        "PARALLEL_GROUPS": {k: sorted(map(sorted, v)) for k, v in sorted(parallel.items())},
    }
    return maps


def _scan_parallel(v: Any, cls_name: str, par_seen: dict, sample: str) -> None:
    """Record, for each dict in an AppInfo body, whether each pair of sibling
    list fields has equal length (parallel-array candidates)."""
    if isinstance(v, dict):
        if "ptr_class" in v:
            _scan_parallel(v.get("value"), v["ptr_class"], par_seen, sample)
            return
        lists = {k: x for k, x in v.items() if isinstance(x, list)}
        keys = sorted(lists)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                la, lb = len(lists[a]), len(lists[b])
                if la >= 1 or lb >= 1:
                    key = (cls_name, (a, b))
                    prev = par_seen[key].get(sample, True)
                    par_seen[key][sample] = prev and (la == lb and la >= 1)
        for k, x in v.items():
            _scan_parallel(x, cls_name, par_seen, sample)
    elif isinstance(v, list):
        for x in v:
            _scan_parallel(x, cls_name, par_seen, sample)


def load_registry_maps(path: str = G1_REGISTRY_MAPS, *, derive_if_missing: bool = True) -> dict:
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    if not derive_if_missing:
        raise FileNotFoundError(path)
    print(f"== deriving registry maps (first run) -> {os.path.relpath(path, ROOT)}")
    maps = derive_registry_maps()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(maps, fh, indent=1, sort_keys=True)
    return maps


# ---------------------------------------------------------------------------
# 2. the schema-typed ElementId walker + the dangling-id purge
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _Frame:
    """One enclosing CONTAINER of a leaf: the python list, the index of the
    element the leaf lives inside, and where that container hangs."""
    lst: list
    index: int
    holder_class: str          # class whose body owns the container field
    field: str                 # field key of the container in its holder
    holder: Optional[dict]     # the dict owning the container (None for nested arrays)
    is_eid_container: bool     # container's element type IS ElementId (a set/array of ids)


@dataclasses.dataclass
class _Leaf:
    path: str
    holder: Any                # dict or list holding the leaf
    key: Any                   # field key or index
    value: int
    frames: List[_Frame]       # innermost LAST


class AdocGraphEditor:
    """Schema-typed editing of a decoded ADocument value tree.

    Walks object bodies IN PARALLEL WITH THE ARCHIVE CLASS MAP so that every
    integer whose serialized type is ``ElementId`` / ``Identifier`` (the
    flattened i64) is recognised as an element reference regardless of its
    field name — the id-purge is therefore complete by construction (the
    genesis audit's "6,175 dangling references" are 10,017 ElementId-typed
    leaves in this walk; a key-name heuristic misses e.g. m_DBDrawingsIndex).
    """

    def __init__(self, decoder=None, maps: Optional[dict] = None):
        self.dec = decoder or adoc.get_decoder()
        self.schema = self.dec.schema
        self.eid_types = {t for t in (self.dec.id_ElementId, self.dec.id_Identifier) if t}
        self.maps = maps or {}
        self.parallel: Dict[str, Set[str]] = collections.defaultdict(set)
        for cls_name, groups in (self.maps.get("PARALLEL_GROUPS") or {}).items():
            for g in groups:
                for f in g:
                    self.parallel[cls_name].add(f)

    # -- schema helpers ---------------------------------------------------
    def class_id(self, name: str) -> Optional[int]:
        cd = self.schema.by_name.get(name)
        return cd.type_id if cd else None

    def _is_eid_field(self, f) -> bool:
        return f.kind == 0x0E and (f.flags & 0x0F) == 0 and f.type_id in self.eid_types

    # -- the walk ----------------------------------------------------------
    def iter_leaves(self, value: dict, class_name: str, path: str = "") -> Iterable[_Leaf]:
        """Yield every ElementId-typed leaf under ``value`` (a body of class
        ``class_name``)."""
        cid = self.class_id(class_name)
        if cid is None or not isinstance(value, dict):
            return
        out: List[_Leaf] = []
        self._walk(value, cid, path or class_name, [], out)
        return out

    def _walk(self, value: dict, class_id: int, path: str, frames: List[_Frame],
              out: List[_Leaf]) -> None:
        if not isinstance(value, dict):
            return
        cname = self.dec.class_name(class_id)
        seen: dict = {}
        for cd in self.dec.chain(class_id):
            for f in cd.fields:
                key = field_key(cd, f, seen)
                seen[key] = True
                if key not in value:
                    continue
                self._walk_field(value[key], f, f"{path}.{key}", frames, out,
                                 holder=value, holder_class=cname, fkey=key)

    def _walk_field(self, v, f, fpath, frames, out, *, holder, holder_class, fkey) -> None:
        kind, flags = f.kind, f.flags
        shape = flags >> 4
        if kind in (0x08, 0x09):                      # strings / guids
            return
        if kind == 0x0D:                              # inline array wrapper
            elem = f.element
            if isinstance(v, list) and elem is not None:
                is_eid = self._is_eid_field(elem)
                for i, x in enumerate(v):
                    frames.append(_Frame(v, i, holder_class, fkey, holder, is_eid))
                    self._walk_scalar(x, elem, f"{fpath}[{i}]", frames, out, holder=v, key=i)
                    frames.pop()
            return
        if shape in (0x5, 0x1):                       # container / fixed array
            if isinstance(v, list):
                is_eid = self._is_eid_field(f)
                for i, x in enumerate(v):
                    frames.append(_Frame(v, i, holder_class, fkey, holder, is_eid))
                    self._walk_scalar(x, f, f"{fpath}[{i}]", frames, out, holder=v, key=i)
                    frames.pop()
            return
        self._walk_scalar(v, f, fpath, frames, out, holder=holder, key=fkey)

    def _walk_scalar(self, x, f, xpath, frames, out, *, holder, key) -> None:
        kind, indir = f.kind, f.flags & 0x0F
        if kind == 0x0B:                               # int64: element ids stored as
            # plain integers (e.g. BasedOnTracker.m_nOriginalElemIdAsInt64) —
            # the field NAME is the only marker; treat those as references
            if any(t in f.name for t in ("ElemId", "ElementId", "Id64")):
                if isinstance(x, int) and not isinstance(x, bool):
                    out.append(_Leaf(xpath, holder, key, x, list(frames)))
            return
        if kind != 0x0E:
            return
        if indir == 0:                                 # inline value class
            if f.type_id in self.eid_types:
                if isinstance(x, int) and not isinstance(x, bool):
                    out.append(_Leaf(xpath, holder, key, x, list(frames)))
                return
            if isinstance(x, dict):                    # inline struct (std::pair ...)
                self._walk(x, f.type_id, xpath, frames, out)
            return
        if indir == 3:                                 # weak reference
            return
        if isinstance(x, dict) and "ptr_class" in x:   # owned pointer holder
            cid = self.class_id(x["ptr_class"])
            if cid is not None and isinstance(x.get("value"), dict):
                self._walk(x["value"], cid, f"{xpath}->{x['ptr_class']}", frames, out)

    # -- positional detection -----------------------------------------------
    def _frame_is_positional(self, fr: _Frame) -> bool:
        if f"{fr.holder_class}.{fr.field}" in POSITIONAL_ID_FIELDS:
            return True
        if fr.field in self.parallel.get(fr.holder_class, ()):
            return True
        if fr.is_eid_container and any(isinstance(x, int) and x == -1 for x in fr.lst):
            return True
        return False

    # -- the purge ------------------------------------------------------------
    def purge_dangling(self, body: dict, class_name: str, live_ids: Set[int],
                       label: str = "") -> dict:
        """Remove / null every ElementId leaf whose id (> 0) is not live.

        Returns per-body statistics; mutates ``body`` in place.
        """
        stats = {"body": label or class_name, "leaves": 0, "live": 0, "invalid": 0,
                 "dangling": 0, "nulled": 0, "elements_dropped": 0,
                 "scalars_nulled": 0, "positional_containers": []}
        leaves = list(self.iter_leaves(body, class_name, label or class_name))
        stats["leaves"] = len(leaves)
        drops: Dict[int, Tuple[list, Set[int]]] = {}
        for lf in leaves:
            v = lf.value
            if v <= 0:
                stats["invalid"] += 1
                continue
            if v in live_ids:
                stats["live"] += 1
                continue
            stats["dangling"] += 1
            fr = lf.frames[-1] if lf.frames else None
            if fr is None:
                # scalar member of the body / an inline struct outside any container
                lf.holder[lf.key] = INVALID
                stats["scalars_nulled"] += 1
                continue
            if self._frame_is_positional(fr):
                lf.holder[lf.key] = INVALID
                stats["nulled"] += 1
                pc = f"{fr.holder_class}.{fr.field}"
                if pc not in stats["positional_containers"]:
                    stats["positional_containers"].append(pc)
                continue
            # drop the innermost enclosing container element (the whole record)
            drops.setdefault(id(fr.lst), (fr.lst, set()))[1].add(fr.index)
        for lst, idxs in drops.values():
            for i in sorted(idxs, reverse=True):
                if i < len(lst):
                    if _holds_positive_pid(lst[i]):
                        raise RuntimeError(f"refusing to drop an element holding an archive pid "
                                           f"({stats['body']})")
                    del lst[i]
                    stats["elements_dropped"] += 1
        return stats

    def dangling_ids(self, body: dict, class_name: str, live_ids: Set[int]) -> List[int]:
        return [lf.value for lf in self.iter_leaves(body, class_name, class_name)
                if lf.value > 0 and lf.value not in live_ids]


def _holds_positive_pid(v: Any) -> bool:
    """True if the subtree holds a pointer holder with a positive archive pid
    (an object other weak references may target) — never droppable."""
    if isinstance(v, dict):
        if "ptr_class" in v and isinstance(v.get("pid"), int) and v["pid"] > 0:
            return True
        return any(_holds_positive_pid(x) for x in v.values())
    if isinstance(v, list):
        return any(_holds_positive_pid(x) for x in v)
    return False


# ---------------------------------------------------------------------------
# 3. OUR INVENTORY — what the registries must index (derived from OUR records)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class OurInventory:
    """The facts about OUR elements the ADocument registries index."""
    ids: Set[int]
    by_class: Dict[str, List[int]]
    named: Dict[str, int]
    gstyle_rows: List[dict]        # CategoryTracking.m_gstyleData rows
    category_rows: List[dict]      # CategoryTracking.m_categoryData rows
    level_plan_views: Dict[int, List[int]]   # level id -> plan view ids
    sketch_planes: List[Tuple[int, int]]     # (sketch plane id, owner view id)
    suns: List[int]                # all SunAndShadowSettings ids
    views: List[int]               # every DBView* id (project view first)
    drawings: List[int]            # DBDrawing ids
    custom_element_types: Dict[str, List[int]]   # data-type GUID -> our custom elements
    plan_view_types: List[int]     # DBViewType ids of plan families (new-level defaults)
    base_points: Dict[int, int]    # base point id -> its OST category (-2001271/-2001272)
    project_view: Optional[int] = None
    units: Optional[int] = None
    true_north: Optional[int] = None
    manifest_by_id: Dict[int, dict] = dataclasses.field(default_factory=dict)

    def ids_of(self, *classes: str) -> List[int]:
        out: List[int] = []
        for c in classes:
            out.extend(self.by_class.get(c, []))
        return sorted(out)

    def first_of(self, cls: str) -> Optional[int]:
        v = self.by_class.get(cls) or []
        return v[0] if v else None


def derive_inventory(content: OurContent, maps: dict) -> OurInventory:
    """Build the registry facts from OUR content's own records (no sample
    involved): classes, category / graphic-style rows, plan-view -> level,
    sketch-plane -> owner view, suns, drawings, custom-element data types,
    view-type families, singleton ids."""
    cat = content.catalog
    if cat is None:                                     # legacy shape guard
        raise RuntimeError("OurContent has no catalog — build with build_our_content()")
    manifest_by_id = {m["id"]: m for m in content.manifest}
    by_class: Dict[str, List[int]] = collections.defaultdict(list)
    obj_of: Dict[int, dict] = {}
    for r in cat.records:
        by_class[r.class_name].append(int(r.elem_id))
        obj_of[int(r.elem_id)] = getattr(r, "obj", None) or {}
    for v in by_class.values():
        v.sort()
    ids = {int(r.elem_id) for r in cat.records}
    named = {k: int(v) for k, v in (content.ids or {}).items()}

    # object styles + categories
    gstyle_rows, category_rows = [], []
    for gid in by_class.get("GStyleElem", []):
        o = obj_of.get(gid) or {}
        cat_id = o.get("m_categoryId")
        gtype = o.get("m_gstyleType")
        if isinstance(cat_id, int) and isinstance(gtype, int):
            gstyle_rows.append({"m_categoryId": int(cat_id), "m_gstyleId": gid,
                                "m_gstyleType": int(gtype)})
    for cid in by_class.get("CategoryElem", []):
        o = obj_of.get(cid) or {}
        parent = (((o.get("m_pCategory") or {}).get("value") or {}).get("m_parentCategoryId"))
        if isinstance(parent, int):
            category_rows.append({"m_parentCategoryId": int(parent), "m_categoryId": cid})

    # levels + plan views (m_genElemId of a plan view = its generating level)
    levels = set(by_class.get("Level", []))
    level_plan_views: Dict[int, List[int]] = {lv: [] for lv in sorted(levels)}
    for pv in by_class.get("DBViewPlan", []) + by_class.get("DBViewRCPlan", []):
        gen = (obj_of.get(pv) or {}).get("m_genElemId")
        if isinstance(gen, int) and gen in levels:
            level_plan_views.setdefault(gen, []).append(pv)

    # sketch planes -> owner views (only views that exist)
    view_classes = ("DBViewProject", "DBView3d", "DBViewPlan", "DBViewRCPlan",
                    "DBViewSection", "DBViewDrafting")
    views_all: List[int] = []
    for c in view_classes:
        views_all.extend(by_class.get(c, []))
    view_set = set(views_all)
    sketch_planes = []
    for sp in by_class.get("SketchPlane", []):
        owner = (obj_of.get(sp) or {}).get("m_ownerDBViewId")
        if isinstance(owner, int) and owner in view_set:
            sketch_planes.append((sp, owner))

    suns = list(by_class.get("SunAndShadowSettings", []))
    drawings = list(by_class.get("DBDrawing", []))

    # custom elements by data type (first cell class -> GUID map)
    guid_by_cell = {v: k for k, v in (maps.get("CUSTOM_ELEMENT_DATATYPE_GUID_TO_CELL") or {}).items()}
    custom: Dict[str, List[int]] = collections.defaultdict(list)
    for ce in by_class.get("CustomElement", []):
        cells = (((obj_of.get(ce) or {}).get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
        first = cells[0].get("ptr_class") if cells and isinstance(cells[0], dict) else None
        g = guid_by_cell.get(first) if first else None
        if g:
            custom[g].append(ce)

    # view types of plan families (for the new-level defaults registry)
    plan_view_types = []
    for vt in by_class.get("DBViewType", []):
        fam = ((manifest_by_id.get(vt) or {}).get("params") or {}).get("family", "")
        if fam in ("floor_plan", "ceiling_plan", "structural_plan"):
            plan_view_types.append(vt)

    # base points: OST category by kind (survey/shared vs project)
    base_points = {}
    for bp in by_class.get("BasePoint", []):
        kind = (manifest_by_id.get(bp) or {}).get("kind", "")
        base_points[bp] = -2001271 if "survey" in kind else -2001272

    project_view = named.get("project_view") or (by_class.get("DBViewProject") or [None])[0]
    views_ordered = ([project_view] if project_view else []) + \
        [v for v in views_all if v != project_view]
    return OurInventory(
        ids=ids, by_class=dict(by_class), named=named,
        gstyle_rows=gstyle_rows, category_rows=category_rows,
        level_plan_views=level_plan_views, sketch_planes=sketch_planes,
        suns=suns, views=views_ordered, drawings=drawings,
        custom_element_types=dict(custom), plan_view_types=plan_view_types,
        base_points=base_points, project_view=project_view,
        units=named.get("units") or (by_class.get("UnitsElem") or [None])[0],
        true_north=named.get("true_north") or (by_class.get("TrueNorth") or [None])[0],
        manifest_by_id=manifest_by_id)


# ---------------------------------------------------------------------------
# 4. AUTHORING MODES + the ADocument construction
# ---------------------------------------------------------------------------

AUTHORING_MODES: Dict[str, dict] = {
    # G1a — the coherence probe: only what MUST change (zero dangling ids +
    # the content registry matching the empty ContentDocuments); everything
    # else exactly as the reader-accepted shape.  Isolates "does zero-dangling
    # open?" from every authorship question.  NOT a gate candidate.
    "maxsafety": dict(purge=True, empty_content_table=True, repopulate=False,
                      empty_caches=False, build="keep", forge="carry",
                      purity=False, tag="G1a",
                      desc="MAX-SAFETY: coherence only (zero-dangling purge + empty ContentTable); "
                           "no repopulation, no string edits, corpus + build history carried"),
    # THE genesis-2 deliverable
    "candidate": dict(purge=True, empty_content_table=True, repopulate=True,
                      empty_caches=True, build="product", forge="carry",
                      purity=False, tag="G1_candidate",
                      desc="CANDIDATE: purge + registries repopulated over OUR inventory + sample "
                           "caches emptied + product build constant; Forge corpus carried and FLAGGED "
                           "(counsel C4-class product data)"),
    # the maximum-purity probe
    "maxpurity": dict(purge=True, empty_content_table=True, repopulate=True,
                      empty_caches=True, build="ours", forge="empty",
                      purity=True, tag="G1b",
                      desc="MAX-PURITY: candidate + Forge unit-schema corpora emptied + add-in/service "
                           "descriptors emptied + our honest 'saved by' string"),
}


def _appinfo_body(value: dict, class_name: str) -> Optional[dict]:
    mgr = (value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def _appinfo_bodies(value: dict) -> List[Tuple[str, dict]]:
    out = []
    mgr = (value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") and isinstance(x.get("value"), dict):
            out.append((x["ptr_class"], x["value"]))
    return out


def _row(template: dict, **fields) -> dict:
    """A registry row: the template's full key set (schema field set) with
    OUR values."""
    r = dict(template)
    r.update(fields)
    return r


#: minimal row templates (the exact schema field sets, verified against the
#: decoded samples) for registries we may need to CREATE rows in.
_ROW_TEMPLATES = {
    "GStyleDataItem": {"m_categoryId": -1, "m_gstyleId": -1, "m_gstyleType": 0},
    "CategoryDataItem": {"m_parentCategoryId": -1, "m_categoryId": -1},
    "CurSPRec": {"m_curSPId": -1, "m_dbViewId": -1, "m_famId": -1, "m_type": 0},
    "ETDItem": {"m_categoryId": -1, "m_elemIdSet": []},
    "LevelPlanPair": {"first": -1, "second": {"m_elementIds": []}},
    "CustomTypePair": {"first": {"m_value": "00000000-0000-0000-0000-000000000000"},
                       "second": {"m_elemIdSet": []}},
    "IdMapPair": {"first": 0, "second": {"m_elementIds": []}},
    "DefTypePair": {"first": 0, "second": -1},
    "BuildString": {"m_str": ""},
}


def author_adocument(source_tree: dict, inv: OurInventory, maps: dict, mode: str,
                     *, editor: Optional[AdocGraphEditor] = None) -> Tuple[dict, dict]:
    """CONSTRUCT our ADocument from the decoded source graph.

    Returns ``(tree, report)``: a NEW value tree (the source is untouched)
    plus the authoring report — every policy applied, every count, and the
    residual list (what we chose NOT to repopulate and why).
    """
    if mode not in AUTHORING_MODES:
        raise ValueError(f"unknown authoring mode {mode!r}")
    cfg = AUTHORING_MODES[mode]
    ed_ = editor or AdocGraphEditor(maps=maps)
    tree = copy.deepcopy(source_tree)
    report: Dict[str, Any] = {"mode": mode, "config": {k: v for k, v in cfg.items()},
                              "purge": {}, "registries": {}, "caches": {}, "skipped": [],
                              "warnings": []}
    live = set(inv.ids)

    # ---- 1. schema-typed dangling-id PURGE (every object body) --------------
    purge_rows = []
    total = Counter()
    for cls_name, body in _appinfo_bodies(tree):
        st = ed_.purge_dangling(body, cls_name, live, label=cls_name)
        purge_rows.append(st)
        total.update({k: st[k] for k in ("leaves", "live", "invalid", "dangling",
                                          "nulled", "elements_dropped", "scalars_nulled")})
    for field, cls_name in (("m_oContentTable", "ContentTable"),
                            ("m_oNobleSecondaryData", "NOBLE_SecondaryDataStorage"),
                            ("m_pStyleSettings", "StyleSettings"),
                            ("m_pSteelModelInfo", "SteelModelInfo"),
                            ("m_oExServicesUsed", "ExServicesUsed")):
        holder = tree.get(field)
        body = holder.get("value") if isinstance(holder, dict) else None
        if isinstance(body, dict):
            st = ed_.purge_dangling(body, cls_name, live, label=field)
            purge_rows.append(st)
            total.update({k: st[k] for k in ("leaves", "live", "invalid", "dangling",
                                              "nulled", "elements_dropped", "scalars_nulled")})
    # the ADocument's own scalar ElementIds (owner family / group)
    for k in ("m_ownerFamilyId", "m_ownerFamilyContainingGroupId"):
        v = tree.get(k)
        if isinstance(v, int) and v > 0 and v not in live:
            tree[k] = INVALID
            total["scalars_nulled"] += 1
            total["dangling"] += 1
    report["purge"] = {"totals": dict(total),
                       "bodies": [r for r in purge_rows if r["dangling"] or r["live"]],
                       "policy": "container entries dropped whole; positional / parallel arrays "
                                 "nulled in place; scalar members set -1; the 241-slot AppInfo "
                                 "registry and every archive-pid object untouched"}

    # ---- 2. COHERENCE: the loaded-content registry + session/UI state -----
    if cfg["empty_content_table"]:
        ct = (tree.get("m_oContentTable") or {}).get("value")
        if isinstance(ct, dict):
            n = len(ct.get("m_ContentRecSet") or [])
            ct["m_ContentRecSet"] = []
            report["caches"]["ContentTable.m_ContentRecSet"] = (
                f"emptied ({n} inherited 'Autodesk Revit' content records; G0 carries ZERO "
                f"content documents — Global/ContentDocuments is the empty form)")
        # the project-browser expanded-node SESSION state stores the sample
        # user's expanded tree nodes = sample view/sheet element ids as plain
        # int identifiers (not ElementId-typed): dangling by construction ->
        # emptied in every mode (a document has no expanded nodes at rest)
        bot = _appinfo_body(tree, "BrowserOrganizationTracking")
        if isinstance(bot, dict) and bot.get("m_setExpandedNodes"):
            report["caches"]["BrowserOrganizationTracking.m_setExpandedNodes"] = (
                f"emptied ({len(bot['m_setExpandedNodes'])} sample UI expand-state nodes)")
            bot["m_setExpandedNodes"] = []

    # ---- 3. name caches / user maps / link datasets (sample project data) ---
    if cfg["empty_caches"]:
        for cls_name, field in SAMPLE_DATA_CACHES:
            body = _appinfo_body(tree, cls_name)
            if isinstance(body, dict) and field in body:
                n = len(body.get(field) or [])
                body[field] = []
                report["caches"][f"{cls_name}.{field}"] = f"emptied ({n} sample entries)"
        # NOBLE analysis caches (colour-fill results carrying the room names,
        # MEP network caches): a fresh document has none.
        nob = (tree.get("m_oNobleSecondaryData") or {}).get("value")
        if isinstance(nob, dict):
            for f in ("m_data", "m_primary2SecondaryDataIdMap", "m_enqueuedData2primaryParents",
                      "m_invalidatedInTransaction", "m_invalidatingCandidates"):
                if isinstance(nob.get(f), list) and nob[f]:
                    report["caches"][f"NOBLE.{f}"] = f"emptied ({len(nob[f])} entries)"
                    nob[f] = []
        # the runtime Extensible-Storage schema table: the two inherited entries
        # are the SAMPLE's add-in schemas (AREXContentGenerator, Insight); our
        # document stores no ES data (racbasic: 0 entries proves the empty form)
        es = _appinfo_body(tree, "ESSchemaStorage")
        if isinstance(es, dict) and es.get("m_schemaUsageMap"):
            n = len(es["m_schemaUsageMap"])
            es["m_schemaUsageMap"] = []
            report["caches"]["ESSchemaStorage.m_schemaUsageMap"] = f"emptied ({n} sample add-in ES schemas)"
        # the document-local system-family key allocator (keys are per-doc)
        sfn = _appinfo_body(tree, "AppInfoSystemFamiliesNames")
        if isinstance(sfn, dict):
            sfn["m_idMap"] = []
            sfn["m_newKey"] = 0
            report["caches"]["AppInfoSystemFamiliesNames"] = "reset (rebuilt below when repopulating)"
        # last-used parameter values per category (ParamSetKey/ParamSet
        # parallel arrays): the sample's last-typed names ('Concrete 10 MPa',
        # '250 MPa' analytical materials) and last-used type ids — a fresh
        # document has no such memory; both arrays emptied together.
        sim = _appinfo_body(tree, "SymbolIdMgr")
        if isinstance(sim, dict):
            n = len(sim.get("m_paramSetKeys") or [])
            sim["m_paramSetKeys"] = []
            sim["m_paramSets"] = []
            report["caches"]["SymbolIdMgr.m_paramSetKeys/m_paramSets"] = (
                f"emptied ({n} last-used parameter value sets — the sample's last-typed "
                f"material names lived here)")
        # based-on tracking maps: sample element ids stored as int64 keys
        bot = _appinfo_body(tree, "BasedOnTracker")
        if isinstance(bot, dict):
            for f in ("m_mIdToBasis", "m_mBasisToIdSet"):
                if isinstance(bot.get(f), list) and bot[f]:
                    report["caches"][f"BasedOnTracker.{f}"] = f"emptied ({len(bot[f])} entries)"
                    bot[f] = []
        # numbering registry leftovers (category -> {param -> scheme} maps whose
        # scheme ids the purge already dropped)
        nap = _appinfo_body(tree, "NumberingAppInfo")
        if isinstance(nap, dict):
            for f in ("m_mapCategoriesToParameterIdsToSchemas", "m_mapSchemas",
                      "m_mapSchemaIdsToInfo", "m_schemaIdsToData"):
                if isinstance(nap.get(f), list) and nap[f]:
                    nap[f] = []
                    report["caches"][f"NumberingAppInfo.{f}"] = "emptied"

    # ---- 4. REPOPULATE the registries over OUR inventory -------------------
    if cfg["repopulate"]:
        _populate_registries(tree, inv, maps, report)

    # ---- 5. the "saved by" build list ------------------------------------
    old_builds = [x.get("m_str") if isinstance(x, dict) else x
                  for x in (tree.get("m_storedByRevitBuild") or [])]
    if cfg["build"] == "product":
        tree["m_storedByRevitBuild"] = [dict(_ROW_TEMPLATES["BuildString"], m_str=PRODUCT_BUILD_STRING_2026)]
        report["registries"]["m_storedByRevitBuild"] = (
            f"1 entry (the Revit-2026 product build constant; was {len(old_builds)} entries of "
            f"the SAMPLE's 2018->2026 save lineage)")
    elif cfg["build"] == "ours":
        tree["m_storedByRevitBuild"] = [dict(_ROW_TEMPLATES["BuildString"], m_str=OUR_BUILD_STRING)]
        report["registries"]["m_storedByRevitBuild"] = (
            f"1 entry — OUR authoring string {OUR_BUILD_STRING!r} (was {len(old_builds)} sample "
            f"lineage entries; reader tolerance UNVERIFIED — counsel C1)")
    else:
        report["registries"]["m_storedByRevitBuild"] = (
            f"KEPT the inherited {len(old_builds)}-entry sample save lineage (max-safety)")

    # ---- 6. the Forge unit / spec / parameter-group JSON corpus ---------------
    es = _appinfo_body(tree, "ESSchemaStorage")
    forge_bytes = 0
    if isinstance(es, dict):
        for f in ("m_storedForgeSchemas", "m_storedParameterSchemas"):
            for p in es.get(f) or []:
                forge_bytes += 8 + 2 * len(p.get("first") or "") + 2 * len(p.get("second") or "")
        if cfg["forge"] == "empty":
            n1, n2 = len(es.get("m_storedForgeSchemas") or []), len(es.get("m_storedParameterSchemas") or [])
            es["m_storedForgeSchemas"] = []
            es["m_storedParameterSchemas"] = []
            es["m_dirty"] = 0
            report["forge_corpus"] = {"action": "EMPTIED", "documents_removed": n1 + n2,
                                      "bytes_removed": forge_bytes,
                                      "why": "max-purity: no Autodesk-authored schema documents "
                                             "carried; the reader-tolerance question this file "
                                             "answers (probe P3b analogue)"}
        else:
            report["forge_corpus"] = {"action": "CARRIED", "bytes": forge_bytes,
                                      "documents": (len(es.get("m_storedForgeSchemas") or [])
                                                    + len(es.get("m_storedParameterSchemas") or [])),
                                      "why": "product runtime data byte-identical in ALL SIX "
                                             "samples (Revit Unit Schemas install image) — NOT "
                                             "sample-project expression; NOT regenerable from any "
                                             "public open-source repository (docs/writer/latest-"
                                             "regions.md §2.4 — determination (c) is FALSE); no "
                                             "viewer verdict yet on stubbing/blanking (probes "
                                             "P3a/P3b UNVERIFIED) -> carried and FLAGGED as the "
                                             "residual, counsel C4-class beside Formats/Latest"}

    # ---- 7. max-purity extras --------------------------------------------
    if cfg["purity"]:
        api = _appinfo_body(tree, "APIAppInfo")
        if isinstance(api, dict) and api.get("m_addInNames"):
            report["caches"]["APIAppInfo.m_addInNames"] = f"emptied ({len(api['m_addInNames'])} add-in names)"
            api["m_addInNames"] = []
        dyn = _appinfo_body(tree, "DynamicUpdateAppInfo")
        if isinstance(dyn, dict) and dyn.get("m_modifyingUpdaterInfos"):
            report["caches"]["DynamicUpdateAppInfo.m_modifyingUpdaterInfos"] = (
                f"emptied ({len(dyn['m_modifyingUpdaterInfos'])} Revit updater registrations)")
            dyn["m_modifyingUpdaterInfos"] = []

    # ---- 8. post-conditions --------------------------------------------------
    dangling_after = []
    for cls_name, body in _appinfo_bodies(tree):
        dangling_after.extend(ed_.dangling_ids(body, cls_name, live))
    for field, cls_name in (("m_oContentTable", "ContentTable"),
                            ("m_oNobleSecondaryData", "NOBLE_SecondaryDataStorage")):
        body = (tree.get(field) or {}).get("value")
        if isinstance(body, dict):
            dangling_after.extend(ed_.dangling_ids(body, cls_name, live))
    report["postconditions"] = {
        "dangling_after": len(dangling_after),
        "registered_ids_all_ours": True,   # rows are built ONLY from inv
    }
    if dangling_after:
        raise RuntimeError(f"purge incomplete: {len(dangling_after)} dangling ids remain "
                           f"(e.g. {dangling_after[:5]})")
    return tree, report


def _populate_registries(tree: dict, inv: OurInventory, maps: dict, report: dict) -> None:
    """Refill the registries so they index EXACTLY our inventory (candidate
    / max-purity modes).  Every rule and its derivation is recorded."""
    reg = report["registries"]
    skip = report["skipped"]

    def set_list(cls_name: str, field: str, values: list, note: str = "") -> None:
        body = _appinfo_body(tree, cls_name)
        if isinstance(body, dict) and field in body:
            body[field] = list(values)
            reg[f"{cls_name}.{field}"] = f"{len(values)} of ours" + (f" ({note})" if note else "")
        else:
            skip.append(f"{cls_name}.{field}: registry absent in the base document")

    def set_scalar(cls_name: str, field: str, value: Optional[int], note: str = "") -> None:
        body = _appinfo_body(tree, cls_name)
        if isinstance(body, dict) and field in body:
            body[field] = int(value) if value is not None else INVALID
            reg[f"{cls_name}.{field}"] = (f"= our {note or value}" if value is not None
                                          else f"-1 (we have no {note})")
        else:
            skip.append(f"{cls_name}.{field}: registry absent in the base document")

    # -- per-class id-set trackers (simple m_elemIdSet registries) -------------
    set_list("MaterialTracking", "m_elemIdSet", inv.ids_of("MaterialElem"), "materials")
    set_list("FillPatternTracking", "m_elemIdSet", inv.ids_of("FillPatternElem"), "fill patterns")
    set_list("LinePatternTracking", "m_elemIdSet", inv.ids_of("LinePatternElem"), "line patterns")
    set_list("AppearanceAssetTracking", "m_elemIdSet", inv.ids_of("AppearanceAssetElem"))
    set_list("TilePatternTracking", "m_elemIdSet", inv.ids_of("TilePatternElem"))
    set_list("PropertySetElementTracking", "m_elemIdSet", inv.ids_of("PropertySetElement"))
    set_list("DatumTracking", "m_elemIdSet", inv.ids_of("Level", "Grid", "MultiSegmentGrid",
                                                          "RefPlane", "ReferencePlane"), "levels/datums")
    set_list("PhaseFilterTracking", "m_elemIdSet", inv.ids_of("PhaseFilterElem"), "phase filters")

    # -- UniqueElementsTracking: POSITIONAL singleton table --------------------
    uet = _appinfo_body(tree, "UniqueElementsTracking")
    pos_to_class = maps.get("UET_POS_TO_CLASS") or {}
    if isinstance(uet, dict) and isinstance(uet.get("m_elemIds"), list):
        arr = uet["m_elemIds"]
        filled, missing = [], []
        for i in range(len(arr)):
            cls_name = pos_to_class.get(str(i))
            if not cls_name:
                arr[i] = INVALID
                continue
            ours = inv.by_class.get(cls_name) or []
            if len(ours) == 1:
                arr[i] = ours[0]
                filled.append(f"[{i}]={cls_name}")
            else:
                arr[i] = INVALID
                if not ours:
                    missing.append(f"[{i}] {cls_name}")
                else:
                    skip.append(f"UniqueElementsTracking[{i}] {cls_name}: {len(ours)} candidates, ambiguous")
        reg["UniqueElementsTracking.m_elemIds"] = (f"{len(filled)} singletons of ours: {', '.join(filled)}")
        report["missing_singletons"] = missing            # the settings elements our skeleton lacks
    else:
        skip.append("UniqueElementsTracking: absent")

    # -- singleton scalar registries --------------------------------------------
    set_scalar("UnitsTracking", "m_unitsElemId", inv.units, "UnitsElem")
    set_scalar("SiteMgr", "m_trueNorthId", inv.true_north, "TrueNorth")

    # -- the VIEW index (DBViewInfo) --------------------------------------------
    dbv = _appinfo_body(tree, "DBViewInfo")
    if isinstance(dbv, dict):
        dbv["m_DBViewProjectId"] = inv.project_view if inv.project_view else INVALID
        dbv["m_DBViewSystemNavigatorId"] = INVALID
        dbv["m_DBViewsIndex"] = list(inv.views)
        dbv["m_DBViewTemplates"] = []
        dbv["m_aidSunAndShadowSettings"] = list(inv.suns)
        reg["DBViewInfo"] = (f"project view {inv.project_view}, index of {len(inv.views)} views, "
                             f"{len(inv.suns)} sun-settings, 0 templates, no system navigator")
    else:
        skip.append("DBViewInfo: absent")
    set_list("DBViewTypesForNewLevel", "m_newLevelDBViewTypes", inv.plan_view_types, "plan view types")

    # -- drawings ---------------------------------------------------------------
    set_list("DBDrawingInfo", "m_DBDrawingsIndex", inv.drawings, "drawings")

    # -- level -> plan views ----------------------------------------------------
    lpv = _appinfo_body(tree, "LevelPlanViewTracking")
    if isinstance(lpv, dict) and "m_levelIdToPlanViewIds" in lpv:
        rows = []
        for lv, pvs in sorted(inv.level_plan_views.items()):
            rows.append({"first": lv, "second": {"m_elementIds": list(pvs)}})
        lpv["m_levelIdToPlanViewIds"] = rows
        reg["LevelPlanViewTracking.m_levelIdToPlanViewIds"] = (
            f"{len(rows)} levels -> {sum(len(p) for p in inv.level_plan_views.values())} plan views")

    # -- sketch planes ----------------------------------------------------------
    spi = _appinfo_body(tree, "SketchPlaneInfo")
    if isinstance(spi, dict) and "m_curSPRecs" in spi:
        recs = []
        for sp, view in inv.sketch_planes:
            recs.append({"ptr_class": "CurSPRec", "pid": -1,
                         "value": _row(_ROW_TEMPLATES["CurSPRec"], m_curSPId=sp, m_dbViewId=view)})
        spi["m_curSPRecs"] = recs
        reg["SketchPlaneInfo.m_curSPRecs"] = f"{len(recs)} view sketch-planes of ours"

    # -- the CATEGORY / GRAPHIC-STYLE catalogue --------------------------------
    ctr = _appinfo_body(tree, "CategoryTracking")
    if isinstance(ctr, dict):
        ctr["m_gstyleData"] = [_row(_ROW_TEMPLATES["GStyleDataItem"], **r) for r in inv.gstyle_rows]
        ctr["m_categoryData"] = [_row(_ROW_TEMPLATES["CategoryDataItem"], **r) for r in inv.category_rows]
        reg["CategoryTracking"] = (f"{len(inv.gstyle_rows)} graphic-style rows (our house standard) + "
                                    f"{len(inv.category_rows)} sub-category rows")
    else:
        skip.append("CategoryTracking: absent")

    # -- ElementTrackingData: per-built-in-category type / instance index ------
    etd = _appinfo_body(tree, "ElementTrackingData")
    if isinstance(etd, dict):
        c2sym = maps.get("CLASS_TO_ETD_SYMBOL_CATEGORIES") or {}
        c2elm = maps.get("CLASS_TO_ETD_ELEM_CATEGORIES") or {}
        filled_s, filled_e = Counter(), Counter()

        def add_to(entries: list, cat_id: int, eid: int) -> None:
            for e in entries:
                if e.get("m_categoryId") == cat_id:
                    if eid not in e["m_elemIdSet"]:
                        e["m_elemIdSet"].append(eid)
                    return
            entries.append(_row(_ROW_TEMPLATES["ETDItem"], m_categoryId=cat_id, m_elemIdSet=[eid]))

        syms = etd.get("m_symbols") if isinstance(etd.get("m_symbols"), list) else None
        elems = etd.get("m_elems") if isinstance(etd.get("m_elems"), list) else None
        for cls_name, ids in inv.by_class.items():
            if syms is not None:
                cats = c2sym.get(cls_name) or []
                if len(cats) == 1:
                    for eid in ids:
                        add_to(syms, int(cats[0]), eid)
                        filled_s[cls_name] += 1
                elif len(cats) > 1:
                    skip.append(f"ElementTrackingData.m_symbols {cls_name}: {len(cats)} categories, ambiguous")
            if elems is not None:
                cats = c2elm.get(cls_name) or []
                if cls_name == "BasePoint":
                    for eid in ids:
                        add_to(elems, int(inv.base_points.get(eid, -2001272)), eid)
                        filled_e[cls_name] += 1
                elif len(cats) == 1:
                    for eid in ids:
                        add_to(elems, int(cats[0]), eid)
                        filled_e[cls_name] += 1
                elif len(cats) > 1:
                    skip.append(f"ElementTrackingData.m_elems {cls_name}: {len(cats)} categories, ambiguous")
        reg["ElementTrackingData"] = (f"symbols {dict(filled_s) or '{}'} / elems {dict(filled_e) or '{}'} "
                                       f"(sample shells kept, sets purged then refilled with ours)")

    # -- default types: SymbolIdMgr.m_defElementTypeMap (ElementTypeGroup enum) -
    # Only TYPE-like classes (attributes / types / styles) + Level (group 15
    # = the current level) get a default; single-group classes only.  Our
    # per-category GStyleElem rows / graphics-only materials are NOT "default
    # element types" (group 41 = the built-in line-style default we do not
    # author; group 42 = a rac-only material default).
    sim = _appinfo_body(tree, "SymbolIdMgr")
    if isinstance(sim, dict) and isinstance(sim.get("m_defElementTypeMap"), list):
        c2g = maps.get("CLASS_TO_DEF_GROUPS") or {}
        rows, set_names = [], []
        for cls_name, ids in sorted(inv.by_class.items()):
            groups = c2g.get(cls_name) or []
            if not groups or not ids:
                continue
            typelike = (cls_name.endswith(("Type", "Attributes", "Attr", "Attrs", "Symbol"))
                        or cls_name in ("Level",))
            if not typelike:
                skip.append(f"m_defElementTypeMap {cls_name}: not a type-like class "
                            f"(group {groups[0]}) — no default set")
                continue
            if len(groups) == 1:
                rows.append(dict(_ROW_TEMPLATES["DefTypePair"], first=int(groups[0]), second=ids[0]))
                set_names.append(f"{cls_name}->{groups[0]}")
            else:
                skip.append(f"m_defElementTypeMap {cls_name}: {len(groups)} type-groups "
                            f"{groups[:6]}, one class -> many usage kinds; no default set")
        sim["m_defElementTypeMap"] = rows
        reg["SymbolIdMgr.m_defElementTypeMap"] = f"{len(rows)} defaults: {', '.join(set_names)}"
        # recent-symbol lists: whatever the purge left (empty groups) is inert;
        # a fresh document has no MRU — clear.
        rl = (sim.get("m_systemRecentLists") or {}).get("value") or {}
        if isinstance(rl.get("m_innerMap"), list):
            rl["m_innerMap"] = []

    # -- custom-element data-type registry (conductor cells etc.) -------------
    cet = _appinfo_body(tree, "CustomElementTracking")
    if isinstance(cet, dict) and "m_dataTypeToElementIdsMap" in cet:
        rows = []
        for g, ids in sorted(inv.custom_element_types.items()):
            rows.append({"first": {"m_value": g}, "second": {"m_elemIdSet": list(ids)}})
        cet["m_dataTypeToElementIdsMap"] = rows
        reg["CustomElementTracking"] = (f"{len(rows)} data types -> "
                                         f"{sum(len(v) for v in inv.custom_element_types.values())} cells")

    # -- system-family type index (document-local keys, one per family) ------
    sfn = _appinfo_body(tree, "AppInfoSystemFamiliesNames")
    tracked = set(maps.get("SFN_TRACKED_CLASSES") or [])
    if isinstance(sfn, dict):
        rows: list = []
        key = 0
        for cls_name in sorted(inv.by_class):
            if cls_name not in tracked:
                continue
            ids = inv.by_class[cls_name]
            if not ids:
                continue
            if cls_name == "DBViewType":            # one system family per view type
                for i in ids:
                    rows.append({"first": key, "second": {"m_elementIds": [i]}})
                    key += 1
            else:
                rows.append({"first": key, "second": {"m_elementIds": list(ids)}})
                key += 1
        sfn["m_idMap"] = rows
        sfn["m_newKey"] = key
        sfn["m_bValid"] = True
        reg["AppInfoSystemFamiliesNames"] = f"{len(rows)} system families (keys 0..{max(0, key - 1)}), our types"


# ---------------------------------------------------------------------------
# 5. content census — what strings a tree still carries (for the record)
# ---------------------------------------------------------------------------
#: sample-project strings the audits named (docs/writer/latest-regions.md §3 /
#: adoc-probes) — a genesis document must carry NONE of these.
SAMPLE_STRING_WATCHLIST = [
    "FOUNDATION-2700", "L1 wall frame hall 5", "S206", "Elevation 1", "Section 1",
    "Kitchen & Dining", "Master Bedroom", "Bathroom 1", "Ensuite", "Laundry",
    "Concrete 10 MPa", "250 MPa", "liqi", "macalis", "LB_Associations",
    "Less than 40 m", "360 m", "campbes", "hansonje", "loboarch", "okapaw",
    "youyi", "zhangg", "gbs_subsuser6", "xuew",
]
#: Autodesk / vendor identifier patterns the provenance string layer counts
VENDOR_TOKENS = ["autodesk", "adsk", "arex", "revit default db server", "wiresizes.xml"]


def tree_string_census(tree: dict) -> dict:
    """Every AString in the tree, with the watch-list hits and vendor tokens."""
    strings: List[str] = []
    _collect_all_strings(tree, strings)
    joined_lower = "\x00".join(strings).lower()
    watch = {w: joined_lower.count(w.lower()) for w in SAMPLE_STRING_WATCHLIST
             if w.lower() in joined_lower}
    vendor = {t: sum(1 for s in strings if t in s.lower()) for t in VENDOR_TOKENS}
    forge = sum(1 for s in strings if s.startswith("autodesk.") or '"typeid"' in s)
    return {"strings": len(strings), "chars": sum(len(s) for s in strings),
            "sample_watchlist_hits": watch,
            "vendor_tokens": {k: v for k, v in vendor.items() if v},
            "forge_json_or_typeid_strings": forge}


def _collect_all_strings(v: Any, out: list) -> None:
    if isinstance(v, dict):
        for x in v.values():
            _collect_all_strings(x, out)
    elif isinstance(v, list):
        for x in v:
            _collect_all_strings(x, out)
    elif isinstance(v, str) and v:
        out.append(v)


# ---------------------------------------------------------------------------
# 6. the G1 stage: base file + our ADocument -> a validated candidate file
# ---------------------------------------------------------------------------

def _live_ids_of(path: str) -> Set[int]:
    with open_rvt(path) as f:
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
    return {int(r[4]) for r in et["records"]}


_SAMPLE_ID_UNIVERSE: Optional[Set[int]] = None


def sample_id_universe(min_id: int = 4700) -> Set[int]:
    """Union of every sample document's ElemTable ids (>= min_id: below that
    the values collide with counts / enums / class ordinals) — the id space
    a leaked SAMPLE reference would come from.  Cached."""
    global _SAMPLE_ID_UNIVERSE
    if _SAMPLE_ID_UNIVERSE is None:
        ids: Set[int] = set()
        for name in sorted(os.listdir(SAMPLES_DIR)):
            if not name.endswith(".rvt"):
                continue
            try:
                with open_rvt(os.path.join(SAMPLES_DIR, name)) as f:
                    et = se.decode_elemtable(f.inflate("Global/ElemTable"))
                ids.update(int(r[4]) for r in et["records"])
            except Exception:
                continue
        _SAMPLE_ID_UNIVERSE = {i for i in ids if i >= min_id}
    return _SAMPLE_ID_UNIVERSE


def byte_scan_ids(payload: bytes, id_set: Set[int]) -> dict:
    """The reader-tolerance-probe scan (independent of the schema decode):
    every byte offset read as a little-endian i64; count values that are
    element ids in ``id_set``.  A small false-positive rate is inherent
    (id-shaped windows inside doubles / adjacent fields, ~0.2 % per hit)."""
    hits: Counter = Counter()
    n = len(payload)
    mv = memoryview(payload)
    unpack = struct.Struct("<q").unpack_from
    for off in range(0, n - 7):
        # cheap pre-filter: ids < 2^31 => the top 4 bytes are zero
        if mv[off + 4] or mv[off + 5] or mv[off + 6] or mv[off + 7]:
            continue
        v = unpack(payload, off)[0]
        if v in id_set:
            hits[v] += 1
    return {"hits": sum(hits.values()), "distinct": len(hits),
            "examples": [i for i, _ in hits.most_common(12)]}


def stage_own_latest(base_rvt: str, out_rvt: str, mode: str, inv: OurInventory,
                     maps: dict, out_dir: str, tag: Optional[str] = None) -> dict:
    """Replace ``Global/Latest`` in ``base_rvt`` with the ADocument WE
    construct (``mode``); refresh BasicFileInfo's last-save path; write
    ``out_rvt``.  Returns the stage record incl. the authoring report
    (also written to ``<out_dir>/<tag>_authoring.json``, tag = the output
    file's stem so per-file variants of one mode never overwrite each other).
    """
    t0 = time.time()
    tag = tag or os.path.splitext(os.path.basename(out_rvt))[0]
    # -- decode the base's document object ------------------------------------
    with open_rvt(base_rvt) as f:
        payload = f.inflate(adoc.STREAM, 0)
        bfi_model = se.decode_basic_file_info(f.logical("BasicFileInfo"))
    source = adoc.decode_latest(payload)
    if not source.clean:
        raise RuntimeError(f"{base_rvt}: ADocument does not decode cleanly: {source.errors[:1]}")
    live = _live_ids_of(base_rvt)
    if live != set(inv.ids):
        # the file's inventory is the authority; the derived facts must match
        missing = sorted(set(inv.ids) - live)[:5]
        extra = sorted(live - set(inv.ids))[:5]
        raise RuntimeError(f"{base_rvt}: ElemTable ({len(live)}) != our inventory "
                           f"({len(inv.ids)}): missing {missing} extra {extra}")
    census_before = tree_string_census(source.value)
    id_refs_before = len(source.element_ids())

    # -- author OUR document object ---------------------------------------------
    editor = AdocGraphEditor(maps=maps)
    tree, report = author_adocument(source.value, inv, maps, mode, editor=editor)
    new_payload = adoc.encode_latest(tree)
    # self-check: what we serialize must re-decode to the tree we authored
    back = adoc.decode_latest(new_payload)
    self_ok = back.clean and back.value == tree
    if not self_ok:
        raise RuntimeError(f"{tag}: authored ADocument does not round-trip "
                           f"(errors={back.errors[:2]}, equal={back.value == tree})")
    census_after = tree_string_census(tree)
    # independent byte-level verification (the probe stream's i64 scan): NO
    # sample-document id may survive in the serialized payload; our own ids
    # must be present (positive confirmation the registries carry them)
    scan_samples_before = byte_scan_ids(payload, sample_id_universe())
    scan_samples_after = byte_scan_ids(new_payload, sample_id_universe())
    scan_ours_after = byte_scan_ids(new_payload, set(inv.ids))

    # -- write: Latest replaced + BFI last-save path -----------------------------
    logical = adoc.latest_logical_stream(new_payload, level=3)
    framed = ecc.frame_stream(logical)
    entries = read_entries(base_rvt)
    bfi2 = dict(bfi_model)
    bfi2["last_save_path"] = os.path.basename(out_rvt)
    new_streams = {adoc.STREAM: framed,
                   "BasicFileInfo": se.encode_basic_file_info(bfi2, regenerate_mirror=True)}
    n_latest = sum(1 for e in entries if e.entry_type == "stream" and e.path == adoc.STREAM)
    if n_latest != 1:
        raise RuntimeError(f"expected exactly one {adoc.STREAM} in {base_rvt}, found {n_latest}")
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out_rvt, out_entries)

    # -- the record ---------------------------------------------------------------
    slots = back.appinfo_slots()
    rec = {
        "stage": tag, "mode": mode, "desc": AUTHORING_MODES[mode]["desc"],
        "base": os.path.relpath(base_rvt, ROOT), "out": os.path.relpath(out_rvt, ROOT),
        "latest_payload_before": len(payload), "latest_payload_after": len(new_payload),
        "latest_logical": len(logical), "latest_framed": len(framed),
        "self_decode_ok": bool(self_ok),
        "coverage_after": back.coverage,
        "appinfo_slots_populated": sum(1 for s in slots if s),
        "element_id_refs_before": id_refs_before,
        "element_id_refs_after": len(back.element_ids()),
        "our_ids_referenced_after": len(set(back.element_ids()) & set(inv.ids)),
        "byte_scan": {
            "sample_ids_before": scan_samples_before,
            "sample_ids_after": scan_samples_after,
            "our_ids_after": scan_ours_after,
            "note": ("independent little-endian i64 window scan of the serialized payload "
                     "against the union of every sample document's ElemTable ids (>= 4700); "
                     "a residual hit rate of ~0.2 % per pre-purge hit is expected coincidence "
                     "(id-shaped windows in doubles / adjacent fields), not references"),
        },
        "string_census_before": census_before,
        "string_census_after": census_after,
        "authoring": report,
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(out_dir, f"{tag}_authoring.json"), "w") as fh:
        json.dump(rec, fh, indent=1, default=str)
    return rec


# ---------------------------------------------------------------------------
# 7. certification of a G1 file: validator + provenance ledger v2 (all layers)
# ---------------------------------------------------------------------------

def run_ledger_v2(path: str, json_out: Optional[str] = None,
                  baseline_paths: Optional[List[str]] = None) -> dict:
    """Provenance ledger v2 (--baseline all --streams --strings --identity)."""
    from rvt.mutate import Document
    from rvt.provenance import format_report, provenance
    t0 = time.time()
    bases = baseline_paths or sorted(
        os.path.join(SAMPLES_DIR, p) for p in os.listdir(SAMPLES_DIR) if p.endswith(".rvt"))
    doc = Document.from_file(path)
    baselines = [Document.from_file(b) for b in bases]
    rep = provenance(doc, baselines[0], baselines=baselines, examples=3, with_units=True,
                     streams=True, strings=True, identity=True,
                     cache_dir=os.path.join(OUT_DIR, "provenance", ".cache"), verbose=False)
    rep["elapsed_s"] = round(time.time() - t0, 1)
    if json_out:
        with open(json_out, "w") as fh:
            json.dump(rep, fh, indent=1, default=str)
        with open(os.path.splitext(json_out)[0] + ".txt", "w") as fh:
            fh.write(format_report(rep, show_examples=True, max_classes=8))
    return rep


def summarize_ledger(rep: dict) -> dict:
    """Compact, honest headline of a v2 ledger report."""
    g = rep.get("gate_G1", {})
    sl = rep.get("stream_ledger", {}) or {}
    tot = sl.get("totals") or {}
    tot_ns = sl.get("totals_excluding_schema") or {}
    latest = next((u for u in sl.get("units", []) if u.get("name") == "Global/Latest"), None)
    rr = rep.get("resource_refs") or {}
    idr = rep.get("identity") or {}
    ptot = rep.get("provenance_totals") or {}
    return {
        "file": rep.get("candidate"),
        "gate_verdict": g.get("verdict"),
        "gate_passes": g.get("passes"),
        "certifies_G1": g.get("certifies_G1"),
        "layers": g.get("layers"),
        "blocking": g.get("blocking"),
        "counsel": g.get("counsel"),
        "advisory_count": len(g.get("advisories") or []),
        "elements": {"host": rep.get("host_elements"), "totals": ptot,
                     "multi_baseline": rep.get("multi_baseline_table", {}).get("per_baseline")},
        "bytes": {"total_inflated": tot.get("inflated"), "identical_pct": tot.get("identical_pct"),
                  "ours_pct": tot.get("ours_pct"),
                  "excluding_schema_identical_pct": tot_ns.get("identical_pct"),
                  "excluding_schema_ours_pct": tot_ns.get("ours_pct")},
        "global_latest": ({"inflated": latest.get("inflated"), "class": latest.get("class"),
                           "identical_bytes": latest.get("identical_bytes"),
                           "identical_pct": latest.get("identical_pct"),
                           "ours_bytes": latest.get("ours_bytes"),
                           "best_baseline": latest.get("best_baseline")} if latest else None),
        "resource_refs": {"total": rr.get("total_refs"), "by_pattern": rr.get("by_pattern")},
        "identity_ok": idr.get("ok"),
        "identity_violations": idr.get("violations"),
        "elapsed_s": rep.get("elapsed_s"),
    }


def certify_g1(path: str, tag: str, out_dir: str, *, ledger: bool = True) -> dict:
    """Validator (must be VALID) + provenance ledger v2 for a G1 file."""
    v = run_validator(path)
    with open(os.path.join(out_dir, f"{tag}_validate.json"), "w") as fh:
        json.dump(v, fh, indent=1)
    print(f"    [{tag}] size {os.path.getsize(path):>9,} B | validator ok={v['ok']} "
          f"(errors {v['errors']}, warnings {v['warnings']})")
    out = {"file": os.path.relpath(path, ROOT), "bytes": os.path.getsize(path), "validator": v}
    if ledger:
        rep = run_ledger_v2(path, os.path.join(out_dir, f"{tag}_provenance.json"))
        summ = summarize_ledger(rep)
        out["ledger"] = summ
        gl = summ.get("global_latest") or {}
        print(f"    [{tag}] ledger: {summ['gate_verdict'][:96]}")
        print(f"    [{tag}]   Global/Latest {gl.get('inflated'):,} B, "
              f"{gl.get('identical_pct')}% identical-to-baseline ({gl.get('class')}); "
              f"bytes total identical {summ['bytes']['identical_pct']}% "
              f"(excl. schema {summ['bytes']['excluding_schema_identical_pct']}%); "
              f"resource refs {summ['resource_refs']['total']}; identity ok={summ['identity_ok']}")
    return out


# ---------------------------------------------------------------------------
# 8. orchestration of the G1 set
# ---------------------------------------------------------------------------

def build_g1_set(out_dir: str = OUT_DIR, *, g0: Optional[str] = None,
                 g0_safe: Optional[str] = None, ledger: bool = True,
                 content: Optional[OurContent] = None,
                 content_safe: Optional[OurContent] = None) -> dict:
    """Build the G1 candidates on top of G0 (and the safe twin on G0_safe).

    ``content`` must be the SAME OurContent that G0 was built from (its
    element ids are the file's inventory); when omitted it is rebuilt
    deterministically (the id start is derived from the G0 file itself).
    """
    os.makedirs(out_dir, exist_ok=True)
    t_all = time.time()
    g0 = g0 or os.path.join(out_dir, "G0.rvt")
    if not os.path.exists(g0):
        raise SystemExit(f"{g0} missing — run the G0 ladder first")
    maps = load_registry_maps(os.path.join(out_dir, "G1_registry_maps.json"))
    if content is None:
        content = build_our_content(min(_live_ids_of(g0)))
    inv = derive_inventory(content, maps)
    pipe: Dict[str, Any] = {"base_g0": os.path.relpath(g0, ROOT), "stages": [], "files": {},
                            "registry_maps": os.path.relpath(os.path.join(out_dir, "G1_registry_maps.json"), ROOT),
                            "inventory": {"elements": len(inv.ids),
                                          "classes": len(inv.by_class),
                                          "named": inv.named,
                                          "gstyle_rows": len(inv.gstyle_rows),
                                          "category_rows": len(inv.category_rows),
                                          "views": inv.views, "suns": inv.suns,
                                          "drawings": inv.drawings,
                                          "levels": inv.level_plan_views,
                                          "custom_element_types": {k: len(v) for k, v in inv.custom_element_types.items()}}}
    variants = [("maxsafety", g0, "G1a.rvt"),
                ("candidate", g0, "G1_candidate.rvt"),
                ("maxpurity", g0, "G1b.rvt")]
    # the safe twin (candidate ADocument over the scrub='safe' content base)
    g0_safe = g0_safe or os.path.join(out_dir, "G0_safe.rvt")
    inv_safe = None
    if os.path.exists(g0_safe):
        if content_safe is None:
            content_safe = build_our_content(min(_live_ids_of(g0_safe)), scrub="safe")
        inv_safe = derive_inventory(content_safe, maps)
        variants.append(("candidate", g0_safe, "G1_candidate_safe.rvt"))
    for mode, base, fname in variants:
        out = os.path.join(out_dir, fname)
        tag = os.path.splitext(fname)[0]
        print(f"== {tag}: {AUTHORING_MODES[mode]['desc'][:90]}")
        use_inv = inv_safe if (base == g0_safe and inv_safe is not None) else inv
        try:
            rec = stage_own_latest(base, out, mode, use_inv, maps, out_dir, tag=tag)
        except Exception as e:                                    # keep going, record the failure
            print(f"    [{tag}] BUILD FAILED: {type(e).__name__}: {e}")
            pipe["stages"].append({"stage": tag, "mode": mode, "error": f"{type(e).__name__}: {e}"})
            continue
        rec["stage"] = tag
        auth = rec["authoring"]
        pur = auth["purge"]["totals"]
        bs = rec["byte_scan"]
        print(f"    [{tag}] Latest {rec['latest_payload_before']:,} -> {rec['latest_payload_after']:,} B; "
              f"purged {pur.get('dangling', 0):,} dangling ({pur.get('elements_dropped', 0):,} entries dropped, "
              f"{pur.get('nulled', 0) + pur.get('scalars_nulled', 0):,} nulled); "
              f"id-refs {rec['element_id_refs_before']:,} -> {rec['element_id_refs_after']:,} "
              f"({rec['our_ids_referenced_after']} of ours); self-decode ok={rec['self_decode_ok']}")
        print(f"    [{tag}] byte-scan: sample-id windows {bs['sample_ids_before']['hits']:,} -> "
              f"{bs['sample_ids_after']['hits']} (distinct {bs['sample_ids_after']['distinct']}"
              f"{', e.g. ' + str(bs['sample_ids_after']['examples'][:6]) if bs['sample_ids_after']['hits'] else ''}); "
              f"our-id windows after {bs['our_ids_after']['hits']:,} ({bs['our_ids_after']['distinct']} distinct)")
        cert = certify_g1(out, tag, out_dir, ledger=ledger)
        pipe["stages"].append({k: v for k, v in rec.items() if k != "authoring"} |
                              {"authoring_summary": {"purge_totals": pur,
                                                     "registries": auth["registries"],
                                                     "caches": auth["caches"],
                                                     "forge_corpus": auth.get("forge_corpus"),
                                                     "missing_singletons": auth.get("missing_singletons", []),
                                                     "skipped": auth["skipped"]}})
        pipe["files"][tag] = cert

    # the roll-ups the task names
    cand = pipe["files"].get("G1_candidate", {})
    with open(os.path.join(out_dir, "G1_validate.json"), "w") as fh:
        json.dump({t: c["validator"] for t, c in pipe["files"].items()}, fh, indent=1)
    if cand.get("ledger"):
        # G1_provenance.json = the candidate's full v2 ledger (already written as
        # G1_candidate_provenance.json); copy it under the task's name
        src = os.path.join(out_dir, "G1_candidate_provenance.json")
        if os.path.exists(src):
            import shutil
            shutil.copyfile(src, os.path.join(out_dir, "G1_provenance.json"))
            txt = os.path.splitext(src)[0] + ".txt"
            if os.path.exists(txt):
                shutil.copyfile(txt, os.path.join(out_dir, "G1_provenance.txt"))
    with open(os.path.join(out_dir, "G1_gate.json"), "w") as fh:
        json.dump({t: c.get("ledger") for t, c in pipe["files"].items()}, fh, indent=1, default=str)
    pipe["total_seconds"] = round(time.time() - t_all, 1)
    with open(os.path.join(out_dir, "G1_pipeline.json"), "w") as fh:
        json.dump(pipe, fh, indent=1, default=str)
    print(f"== G1 pipeline record: {os.path.join(out_dir, 'G1_pipeline.json')} "
          f"({pipe['total_seconds']}s)")
    return pipe


def build_all(out_dir: str = OUT_DIR, *, base: str = BASE, ledger: bool = True) -> dict:
    """The full genesis-2 build: G0 ladder (house standard, scrub=full),
    the scrub=safe twin's final rung, then the G1 set."""
    t0 = time.time()
    maps = load_registry_maps(os.path.join(out_dir, "G1_registry_maps.json"))   # derive once, up front
    print("=" * 70)
    print("PART 1 — the G0 ladder (house standard content, scrub=full)")
    print("=" * 70)
    pipe0 = build_ladder(out_dir, base=base, scrub="full", tag_prefix="G0", certify_rungs=True)
    print("=" * 70)
    print("PART 1b — the scrub=safe twin (final rung only, kept as G0_safe.rvt)")
    print("=" * 70)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        pipe0s = build_ladder(tmp, base=base, scrub="safe", tag_prefix="G0S", certify_rungs=False)
        src = os.path.join(tmp, "G0S.rvt")
        if os.path.exists(src):
            import shutil
            shutil.copyfile(src, os.path.join(out_dir, "G0_safe.rvt"))
            print(f"== G0_safe.rvt kept ({os.path.getsize(src):,} B)")
    print("=" * 70)
    print("PART 2 — GENESIS-2: OUR ADocument -> the G1 set")
    print("=" * 70)
    wm = source_watermark(base)
    start_id = ((wm // 100_000) + 1) * 100_000
    content = build_our_content(start_id, scrub="full")
    content_safe = build_our_content(start_id, scrub="safe")
    pipe1 = build_g1_set(out_dir, ledger=ledger, content=content, content_safe=content_safe)
    print(f"== ALL DONE in {time.time() - t0:.1f}s")
    return {"g0": pipe0, "g1": pipe1}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    ap.add_argument("--base", default=BASE, help="base .rvt (default: R10b)")
    ap.add_argument("--only", choices=["content", "ladder", "g1", "maps", "all"], default="all",
                    help="'content' = build + verify OUR content; 'ladder' = the G0 ladder; "
                         "'g1' = the G1 set from the existing G0.rvt (+G0_safe.rvt); "
                         "'maps' = (re)derive G1_registry_maps.json; 'all' (default)")
    ap.add_argument("--no-ledger", action="store_true",
                    help="skip the provenance ledger v2 on the G1 files (fast iteration)")
    args = ap.parse_args(argv)
    if args.only == "maps":
        maps = derive_registry_maps()
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, "G1_registry_maps.json")
        with open(path, "w") as fh:
            json.dump(maps, fh, indent=1, sort_keys=True)
        print(f"wrote {path}: UET {len(maps['UET_POS_TO_CLASS'])} positions, "
              f"def-groups {len(maps['DEF_GROUP_TO_CLASS'])}, "
              f"ETD sym/elem {len(maps['ETD_SYMBOL_CATEGORY_CLASSES'])}/"
              f"{len(maps['ETD_ELEM_CATEGORY_CLASSES'])}, custom types "
              f"{len(maps['CUSTOM_ELEMENT_DATATYPE_GUID_TO_CELL'])}, "
              f"SFN classes {len(maps['SFN_TRACKED_CLASSES'])}, "
              f"parallel groups {sum(len(v) for v in maps['PARALLEL_GROUPS'].values())}")
        return 0
    if args.only == "g1":
        build_g1_set(args.out, ledger=not args.no_ledger)
        return 0
    if args.only == "all":
        build_all(args.out, base=args.base, ledger=not args.no_ledger)
        return 0
    if args.only == "content":
        wm = source_watermark(args.base) if os.path.exists(args.base) else 1_499_999
        c = build_our_content(((wm // 100_000) + 1) * 100_000)
        kinds = Counter(m["kind"] for m in c.manifest)
        print(f"OUR content: {len(c.elements)} elements, ids "
              f"{c.start_id:,}..{c.last_id:,}")
        for k, n in kinds.most_common():
            print(f"   {n:4d}  {k}")
        print(f"round-trip clean+byte-exact: {c.roundtrip['ok']}/{c.roundtrip['records']}"
              f"  failures={c.roundtrip['failed']}")
        for fmsg in c.roundtrip["failures"][:10]:
            print("   FAIL", fmsg)
        print(f"dangling references (self-containment): {len(c.dangling)}")
        for d in c.dangling[:20]:
            print("   ", d)
        return 0 if (not c.roundtrip["failed"] and not c.dangling) else 1
    build_ladder(args.out, base=args.base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
