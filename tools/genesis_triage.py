#!/usr/bin/env python
"""genesis_triage.py -- BUG-A SKELETON-COMPLETENESS bisection ladder (K-rungs).

The situation this tool bisects (2026-08-03): the Autodesk reader ACCEPTS
deep reductions of a sample (R5, R9 = viewer PASS; families / model /
views / annotation gone, thousands of dangling ADocument refs) but REJECTS
every constructed-base genesis file (G0 / G1a / G1_candidate / G1b = FAIL:
our own 234-element inventory + our own ADocument + ZERO family documents +
5 of 72 settings singletons + a 101-row category/style catalog).  Our
validator calls ALL of them VALID.  Something in the sample's SKELETON that
survives R9 -- settings singletons, the built-in-category graphic-style
catalog, the settings catalogs, or the embedded family documents -- is
required by the reader and absent from our base.

This tool builds a TOP-DOWN ladder of probe files, each derived from a
file the viewer ACCEPTED (or from the previous rung) by removing ONE CLASS
of content, so the first rung the viewer rejects NAMES the required class.
Every rung is emitted through the certified writer path
(``rvt.reduce.delete_elements`` / ``rvt.manipulate.commit_plans``), is
dangling-reference-free by construction (maximal garbage collection over
the arbiter's own reference graph), and must pass ``tools/rvt_validate.py``
with ZERO errors before it is listed.

Branch A -- from R5.rvt (annotation-stripped sample, viewer PASS):
  K1   R5 minus every PLACED model element (walls / instances / rebar /
       rooms / loads / hosted content / model lines) -- an EMPTY PROJECT that
       keeps Autodesk's own skeleton (settings catalogs, categories/GStyles,
       view types + head families, views, phases, levels, project info) =
       "new project from template".  Its class census diffed against
       G1_candidate = docs/writer/skeleton-census.md (the suspect list).
  K2   K1 minus every view except one 3D + one plan (view-minimality).
  K5   K1 minus the document-SETTINGS SINGLETONS G1 lacks (the assembler's
       genesis-2 sec.5.2 hypothesis: PenWidthTableElem, BrowserOrganization,
       StructSettingsElem, the UniqueElement settings singletons).
  K5a  K1 minus PenWidthTableElem (element id 2 in EVERY sample) only.
  K5b  K1 minus BrowserOrganization + system-navigator + browser settings.
  K5c  K1 minus the MEP / structural settings singletons.
  K5d  K1 minus the remaining UniqueElement singletons (K5 - a - b - c).
  K6   K1 minus the built-in-category graphic-style catalog beyond the
       referenced core (+ unreferenced sub-categories / patterns /
       materials / assets) -- G1 authors ~100 rows, the sample carries
       ~1,800.

Branch B -- from R9.rvt (deepest viewer-PASSED reduction: model, views,
types, options and MOST families gone; 52 embedded family documents still
present, 38 of them ORPHANED -- their host Family elements were deleted):
  KD1  R9 minus its 38 ORPHAN embedded documents, removed COHERENTLY: save
       units spliced (partition), Global/ContentDocuments entries removed
       (SOLVED grammar), AND the ADocument ContentTable.m_ContentRecSet
       records for those GUIDs removed.  The Bug-B CONTROL: R9b/R10b did the
       same splice WITHOUT reconciling the ContentTable and FAILED.  If KD1
       passes, coherent unit removal works and the K4 verdict is clean.
  K3   R9 minus the LOADABLE-family layer entirely: the 13 loadable Family
       elements + their symbols/surrogates + every family-scoped child
       (elements whose m_famId names them: sub-categories, styles, fonts,
       attribute types, params, images) + the last placed instance; the
       handful of USAGE fields naming them (level/grid/section head symbol,
       callout head, view-title symbol, struct default column, copy-monitor
       map, area-report fonts) are nulled to -1 / dropped (a MODIFY, the
       M3-certified path).  The 8 curtain-wall SYSTEM families (no
       documents) stay.  All 52 embedded documents remain, now ALL orphaned
       (R9 already tolerates 38 orphans).  = charter K3 "annotation-head
       USAGE removed, documents kept".
  K4   K3 minus ALL 52 embedded family documents, coherently (as KD1: units
       + ContentDocuments + ContentTable) -- ZERO family documents on the
       sample's FULL skeleton (every catalog / singleton / system family
       intact).  THE CRUX PROBE: it recreates the G1 zero-document condition
       from the passing side.  PASS => embedded family documents are NOT
       required (Bug A is a singleton / catalog omission => K5 / K6).
       FAIL (with KD1 + K3 passing) => the reader REQUIRES embedded family
       documents => genesis must carry family documents (asset-forge L4/L5).

Every rung writes experiments/genesis/triage/<K>.rvt + <K>.json (the
attributable evidence: what was deleted / kept / pinned by whom / edited),
plus probes.json (the manifest, ORDERED BY INFORMATION VALUE) and
docs/writer/skeleton-census.md (the K1-vs-G1 class-by-class inverse census).

Usage (repo root):
  .venv/bin/python tools/genesis_triage.py                # everything
  .venv/bin/python tools/genesis_triage.py --only K1,K5   # some rungs
  .venv/bin/python tools/genesis_triage.py --census-only  # census + probes.json

You cannot run the Autodesk viewer from here; every file is a probe for
the orchestrator's certification queue.  READ docs/inbox/genesis-triage-a.md.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import struct
import sys
import time
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import rvt_reduce as RR                                            # noqa: E402
from rvt import ecc                                                 # noqa: E402
from rvt import adocument as adoc                                   # noqa: E402
from rvt.cfb_writer import write_cfb                                # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.reduce import delete_elements, verify_reduced              # noqa: E402
from rvt.roundtrip import read_entries                              # noqa: E402
from rvt.stream_encoders import global_prefix, wrap_global_stream  # noqa: E402
from rvt.writer import gzip_member                                  # noqa: E402

TRIAGE = os.path.join(ROOT, "experiments", "genesis", "triage")
GEN = os.path.join(ROOT, "experiments", "genesis")
R5 = os.path.join(GEN, "R5.rvt")          # viewer PASS (annotation stripped)
R9 = os.path.join(GEN, "R9.rvt")          # viewer PASS (deepest certified)
G1C = os.path.join(GEN, "G1_candidate.rvt")   # viewer FAIL (constructed base)
CENSUS_MD = os.path.join(ROOT, "docs", "writer", "skeleton-census.md")

os.makedirs(TRIAGE, exist_ok=True)


# ===========================================================================
# class taxonomies for the K-rungs
# ===========================================================================
#: PLACED / model content deleted by K1 (an "empty project" keeps every
#: catalog, type, family, view and datum).  = the reduction ladder's
#: MODEL_CLASSES plus the load / analytical / part content that only exists
#: with a model.  CustomElement is EXCLUDED (in rst its instances are the
#: wire/cable conductor CELLS -- settings-catalog data referenced by the
#: wire/cable types, not placed content); datums (grids) stay; sketches and
#: derived trackers join through the ownership fixpoint.
K1_PLACED = (set(RR.MODEL_CLASSES) | {
    "PointLoad", "LineLoad", "AreaLoad", "RoofElem", "CeilingElem",
    "TopographySurface", "ToposolidElem", "BuildingPadElem", "PathReinf",
    "AreaReinf", "FabricSheet", "FabricArea", "Truss", "BeamSystem",
    "StructConnection", "AnalyticalMember", "AnalyticalPanel",
    "AnalyticalNode", "AnalyticalLink", "Hub", "HubsTracker",
    "ReferencePoint", "AssemblyInstance", "Group", "GroupType", "Opening",
    "InsertOpening", "RectOpening", "ArcOpening", "MassLevelData",
    "FormElem", "ImageInstance", "Element",
}) - {"Grid", "MultiSegGrid", "GCSTracker", "CustomElement",
      "ImportInstance", "RvtLinkInstance"}
#: annotation / detail residue R5 could not delete while the model pinned
#: it (locked dimensions, sketch curves, model lines): swept as GARBAGE by
#: K1's second pass once the model is gone -- never neutralised (they are
#: nobody's usage reference).
K1_RESIDUE_SWEEP = set(RR.V2_ANNOTATION) - {
    "LegendComponent",       # legend components live in a (kept) legend view
    "SunAnnotationElem",     # view companion of a kept view's sun settings
    "ModelClipBox",          # a kept 3D view's section box
}

#: the document-settings singleton classes the K5 family bisects.  These are
#: the classes G1_candidate does NOT carry (5 of the sample's 72 populated
#: UniqueElementsTracking slots) plus PenWidthTable / BrowserOrganization,
#: grouped so a K5 FAIL can be re-bisected in one round.
K5A_PENTABLE = {"PenWidthTableElem"}
K5B_BROWSER = {"BrowserOrganization", "RbsDbViewSystemNavigator",
               "ReconcileBrowserSettingsElem", "ConstructionSetProject"}
K5C_MEP_STRUCT = {
    "StructSettingsElem", "ReinforcementSettings", "RbsWireSettingsElem",
    "RbsWireSizesElem", "RbsPipeSettingsElem", "RbsPipeSizesElem",
    "RbsDuctSettingsElem", "RbsDuctSizesElem", "ConduitSettingsElem",
    "CableTraySettingsElem", "MEPSystemTracker", "RouteAnalysisSettings",
    "MEPHiddenLineSettingsElem", "AnalyticalToPhysicalRelationManager",
    "ReactionsUpToDateElem", "AreaReportSettingsElem", "AreaSettingsElem",
    "AreaMeasureElem", "EnergyDataSettings", "ZoneScheme",
    "FabricationSettings", "FabricationServiceSettings",
    "CircuitNamingTypeSetting", "SSEPointVisibilitySettings",
    "StructuralConnectionSettings",  # (ElectricalSetting is one G1 HAS: not seeded)
}
K5D_OTHER_SINGLETONS = {
    "WallJoinDefaultSetting", "AutoJoinTracker", "GCSTracker",
    "KeynoteTable", "KeynotingSystem", "AssemblyCodeTable",
    "InitialViewSettings", "AllProjectRevisions", "ProjectRevision",
    "RevisionNumberingSequence", "NumberingSchema", "PrintSettings",
    "PrintSetup", "ViewSheetSet", "AutoCamSettingsElem",
    "HalftoneUnderlaySettings", "Dwg2dExportUserSettingsData",
    "STEPExportSettings", "ProjectCopySettingsElem", "CopyWatchProperties",
    "DaylightSourceIdSet", "AssemblyTracker", "ExternalParamLock",
    "WorksharingViewModeSettings", "WorksetVisibilitySettingsElem",
    "CoordinateSystemDisplayElem", "ActiveGeoLocationTrackingElement",
    "DefaultDivideSettings", "SketchGridAppearanceParentElem",
    "RvtLinkInstanceAppearanceParentElem", "CurtaSystemFaceManager",
    "PostedWarningElem", "RegenSplitterElem", "SunStudyElem",
    "ModelGraphicsStyle", "AreaSchemePlanTopologies", "AllPlanTopologies",
    "PlanTopology", "MultipleValuesIndicationSettings", "GCSTracker",
    "KeynoteTagsOnSheetsTracker", "LayoutNodesTracker", "MEPComponentTracker",
    "MEPNetworkTracker", "RevisionCloudsOnSheetsTracker",
    "SheetsInSheetCollectionTracker", "MEPAnalyticalModelSettings",
}
K5_ALL = K5A_PENTABLE | K5B_BROWSER | K5C_MEP_STRUCT | K5D_OTHER_SINGLETONS

#: the built-in-category graphic-style CATALOG (K6) plus the pattern /
#: material / asset catalogs the styles reference.
K6_CATALOG = {"CategoryElem", "GStyleElem", "FillPatternElem",
              "LinePatternElem", "MaterialElem", "AppearanceAssetElem",
              "PenWidthTableElem"}

#: the family layer classes (K3); the family-scoped CHILDREN are found by
#: m_famId at run time (any class), these are the roots + type surrogates.
FAMILY_ROOTS = {"Family", "FamilySymbol", "FamilySurrogate",
                "FamSymSurrogate", "AnnotationSymbol", "SysPanelFamSym",
                "SysMullionFamSym", "StairsTriserSymbol", "ParamElemFamily"}


# ===========================================================================
# small utilities
# ===========================================================================

def log(msg: str) -> None:
    print(msg, flush=True)


def census(path: str) -> Dict[str, object]:
    """Class census + content-coherence tuple of a .rvt (read-only).

    classes  : {class_name: count} over the host document (ElemTable ids)
    coherence: partition save units, ContentDocuments entries, and the
               ADocument ContentTable.m_ContentRecSet record count (the
               three numbers the reader wants COHERENT).
    """
    from rvt.mutate import Document
    d = Document.from_file(path)
    classes = Counter((d.class_of(e) or "?") for e in d.et_by_id)
    out: Dict[str, object] = {"path": os.path.relpath(path, ROOT),
                              "elements": len(d.et_by_id),
                              "classes": dict(classes.most_common()),
                              "file_size": os.path.getsize(path)}
    with open_rvt(path) as f:
        # save units
        from rvt.partitions import StreamWalker
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=False, keep_data=False)
        out["save_units"] = len(w.units)
        # ContentDocuments entries (solved grammar)
        try:
            from rvt.famgen.factory import parse_content_documents
            payload = b"".join(f.inflate_all("Global/ContentDocuments"))
            entries, tail = parse_content_documents(payload)
            out["contentdocs_entries"] = len(entries)
            out["contentdocs_clean_tail"] = (len(tail) == 14)
        except Exception as ex:                       # pragma: no cover
            out["contentdocs_entries"] = None
            out["contentdocs_error"] = repr(ex)
        # ADocument ContentTable + FamilyMgr (the two document registries)
        try:
            lat = f.inflate("Global/Latest")
            a = adoc.decode_latest(lat)
            ct = (a.value.get("m_oContentTable") or {}).get("value") or {}
            recs = ct.get("m_ContentRecSet")
            out["contenttable_records"] = len(recs) if isinstance(recs, list) else None
            out["adocument_clean"] = bool(a.clean)
            mgr = (a.value.get("m_pAppInfoManager") or {}).get("value") or {}
            for slot in mgr.get("m_appInfoArr") or []:
                if isinstance(slot, dict) and slot.get("ptr_class") == "FamilyMgr":
                    arr = (slot.get("value") or {}).get("m_arrLoadedFamilyInfo") or []
                    out["familymgr_entries"] = len(arr)
                    out["familymgr_doc_guids"] = sum(len(e.get("m_familyDocGUIDs") or [])
                                                     for e in arr)
        except Exception as ex:                       # pragma: no cover
            out["contenttable_records"] = None
            out["adocument_error"] = repr(ex)
    return out


def validate(path: str) -> dict:
    """tools/rvt_validate.py verdict (0 errors required for every rung)."""
    return RR._run_validator(path)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def write_report(name: str, rep: dict) -> None:
    with open(os.path.join(TRIAGE, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1,
                  default=lambda o: sorted(o) if isinstance(o, set) else str(o))


def _ids_of_classes(st: dict, classes: Iterable[str]) -> Set[int]:
    cs = set(classes)
    return {e for e in st["host"] if st["cls_of"].get(e) in cs}


def _class_hist(st: dict, ids: Iterable[int]) -> List[Tuple[str, int]]:
    return Counter(st["cls_of"].get(e, "?") for e in ids).most_common(80)


def _own_fixpoint(st: dict, seed: Set[int]) -> Set[int]:
    """Grow ``seed`` by ownership children (rvt_reduce's rule) and by
    view-owned content (m_ownerDBViewId of a seeded view), to a fixpoint."""
    seed = set(seed)
    while True:
        add = RR._own_children(st, seed)
        add |= {e for e, ov in st["owner_view"].items()
                if ov in seed and e not in seed and e in st["host"]}
        add -= seed
        if not add:
            break
        seed |= add
    return seed


# ===========================================================================
# generic rung emitter (delete-only rungs)
# ===========================================================================

def gc_rung(name: str, parent_path: str, st: dict, seed: Set[int], *,
            desc: str, tests: str, pass_means: str, fail_means: str,
            extra_pins: Iterable[int] = (), parent_name: str,
            purge_deleted_from_latest: bool = False) -> dict:
    """Emit ``name``.rvt = ``parent_path`` minus maxgc(seed).

    Dangling-free by construction (maximal garbage collection over the
    arbiter's own reference graph): only elements no survivor references are
    deleted; whatever survives inside the seed is attributed to the outside
    class pinning it (``pin_evidence``).  With ``purge_deleted_from_latest``
    the ids DELETED AT THIS RUNG (and only those) are also removed from the
    ADocument's registries (positional slots nulled, container rows dropped
    -- Revit's own deletion semantics; the reference for a registry-indexed
    singleton/catalog test).  The rung is validated (0 errors required) and
    its class census recorded.
    """
    t0 = time.time()
    seed = RR._protect_history(st, set(seed))
    delete, kept, ev = RR.maxgc(st, seed, extra_pins=extra_pins)
    out = os.path.join(TRIAGE, f"{name}.rvt")
    if purge_deleted_from_latest and delete:
        tmp = os.path.join(TRIAGE, f".{name}_pre_purge.rvt")
        delete_elements(parent_path, tmp, delete)
        purge_rep = purge_ids_from_latest(tmp, out, delete)
        os.remove(tmp)
    else:
        delete_elements(parent_path, out, delete)
        purge_rep = None
    struct_ok = verify_reduced(out, delete)
    val = validate(out)
    cen = census(out)
    lat_dangling = len(st["ext"].get("Global/Latest", set()) & delete)
    rep = {
        "rung": name, "kind": "gc-delete", "parent": _relp(parent_path),
        "parent_rung": parent_name, "out": _relp(out),
        "description": desc, "tests": tests,
        "if_PASS": pass_means, "if_FAIL": fail_means,
        "seed": len(seed), "seed_kept_pinned": len(kept), "deleted": len(delete),
        "deleted_by_class": _class_hist(st, delete),
        "kept_seed_by_class": _class_hist(st, kept),
        "pin_evidence": ev,
        "latest_dangling_ids_created": (0 if purge_rep else lat_dangling),
        "latest_purge": purge_rep,
        "structural_ok": bool(struct_ok["ok"]),
        "validator": val,
        "census": cen,
        "seconds": round(time.time() - t0, 1),
    }
    write_report(name, rep)
    log(f"[{name}] {desc}\n"
        f"      parent {parent_name}: seed {len(seed):,} -> deleted {len(delete):,} "
        f"(pinned/kept {len(kept):,}); {cen['elements']:,} elements left, "
        f"{cen['file_size']:,} B; structural={struct_ok['ok']} "
        f"validator_ok={val['ok']} (errors {val['errors']}, warnings {val['warnings']}); "
        f"Latest-dangling +{rep['latest_dangling_ids_created']}"
        f"{' (purged: ' + str(purge_rep['totals']) + ')' if purge_rep else ''}; "
        f"{rep['seconds']}s")
    if not (struct_ok["ok"] and val["ok"] and val["errors"] == 0):
        rep["FAILED_SELF_CHECK"] = True
        log(f"[{name}] *** SELF-CHECK FAILED -- not a valid probe: "
            f"{val.get('error_messages')} {struct_ok if not struct_ok['ok'] else ''}")
    return rep


def purge_ids_from_latest(src: str, out: str, deleted_ids: Iterable[int]) -> dict:
    """Remove EXACTLY ``deleted_ids`` from the ADocument (Global/Latest):
    registry rows keyed by / holding them are dropped, positional / parallel
    array slots nulled to -1, scalar members set -1 -- the genesis-2
    ``AdocGraphEditor`` schema-typed purge (imported, not modified), driven
    with ``live = every id the tree references EXCEPT the deleted set`` so
    that ONLY this rung's deletions are purged and every inherited (already
    dangling, reader-tolerated) reference is left byte-for-byte alone.
    """
    import genesis_assemble as GA
    deleted = {int(i) for i in deleted_ids}
    with open_rvt(src) as f:
        payload = f.inflate("Global/Latest")
    a = adoc.decode_latest(payload)
    tree = json.loads(json.dumps(a.value))
    ed = GA.AdocGraphEditor(maps=GA.load_registry_maps())
    bodies: List[Tuple[str, dict]] = list(GA._appinfo_bodies(tree))
    for field, cls_name in (("m_oContentTable", "ContentTable"),
                            ("m_oNobleSecondaryData", "NOBLE_SecondaryDataStorage"),
                            ("m_pStyleSettings", "StyleSettings"),
                            ("m_pSteelModelInfo", "SteelModelInfo"),
                            ("m_oExServicesUsed", "ExServicesUsed")):
        holder = tree.get(field)
        body = holder.get("value") if isinstance(holder, dict) else None
        if isinstance(body, dict):
            bodies.append((cls_name, body))
    # live = every id already referenced, minus the deleted set
    referenced: Set[int] = set()
    for cls_name, body in bodies:
        for lf in ed.iter_leaves(body, cls_name, cls_name) or []:
            if isinstance(lf.value, int) and lf.value > 0:
                referenced.add(lf.value)
    live = referenced - deleted
    totals = Counter()
    rows = []
    for cls_name, body in bodies:
        st = ed.purge_dangling(body, cls_name, live, label=cls_name)
        rows.append(st)
        totals.update({k: st[k] for k in ("leaves", "dangling", "nulled",
                                          "elements_dropped", "scalars_nulled")})
    for k in ("m_ownerFamilyId", "m_ownerFamilyContainingGroupId"):
        v = tree.get(k)
        if isinstance(v, int) and v in deleted:
            tree[k] = -1
            totals["scalars_nulled"] += 1
    new_payload = adoc.encode_latest(tree)
    back = adoc.decode_latest(new_payload)
    if back.value != tree:
        raise RuntimeError("ADocument re-encode after purge is not lossless")
    adoc.write_with_latest(src, out, new_payload)
    return {"purged_ids": len(deleted & referenced),
            "totals": dict(totals),
            "bodies_touched": [r["body"] for r in rows if r["dangling"]],
            "latest_payload_before": len(payload),
            "latest_payload_after": len(new_payload)}


# ===========================================================================
# Branch A -- from R5.rvt
# ===========================================================================

def _inplace_family_chains(st: dict) -> Set[int]:
    """In-place / model-defined families: Family elements whose definition
    geometry (curves, dims, sketches, ref points) lives in the HOST document
    -- placed content, deleted with the model (Family + FamilySymbol +
    m_famId children + instances)."""
    from rvt import families as FAM
    out: Set[int] = set()
    try:
        famdocs = FAM.family_documents(source_path_of(st))
    except Exception:
        return out
    doc, cls_of = st["doc"], st["cls_of"]
    inplace = {fd["family_id"] for fd in famdocs if fd.get("in_place")}
    if not inplace:
        return out
    out |= inplace
    for e in st["host"]:
        v = doc.value(e)
        if isinstance(v, dict) and v.get("m_famId") in inplace:
            out.add(e)
        elif cls_of.get(e) == "FamilyInstance" and isinstance(v, dict) \
                and v.get("m_masterSymbolId") in out:
            out.add(e)
    return out


def build_K1(st5: dict) -> dict:
    """Two-step: (1) neutralise the SURVIVOR references to the placed model
    (views' hidden-element lists / ad-hoc overrides / schedule columns /
    sheet title-block ids, trackers, plan topologies) exactly as Revit does
    when it deletes an element (the M2-certified soft-referrer rule), then
    (2) maximal-GC the placed model + the annotation residue it releases."""
    t0 = time.time()
    placed = _ids_of_classes(st5, K1_PLACED) | _inplace_family_chains(st5)
    placed = _own_fixpoint(st5, placed)
    step1 = os.path.join(TRIAGE, "K1_step1_neutralised.rvt")
    nrep = neutralise_referrers(st5, placed, step1, name="K1")
    st1 = RR.build_state_v2(step1)
    seed = {e for e in placed if e in st1["host"]}
    seed |= _ids_of_classes(st1, K1_RESIDUE_SWEEP)
    seed = _own_fixpoint(st1, seed)
    rep = gc_rung(
        "K1", step1, st1, seed, parent_name="R5",
        desc="R5 (viewer PASS) minus every PLACED model element (walls, "
             "instances, rebar, parts, rooms, loads, analytical + sketch "
             "content, the in-place family, model lines) plus the annotation "
             "residue that only the model pinned -- after neutralising the "
             "views' references to that content (hidden-element lists, "
             "ad-hoc graphic overrides, schedule column ids, sheet "
             "title-block ids, tracker rows) exactly as Revit's own deletion "
             "does.  Result: an EMPTY PROJECT on Autodesk's own skeleton -- "
             "every settings catalog, category/GStyle row, view type + head "
             "family, view, phase, level, datum, family and type intact.",
        tests="Whether an empty project on the SAMPLE's complete skeleton "
              "(the shape of Autodesk's 'new project from template') opens; "
              "its class census is the reference the skeleton census diffs "
              "against G1_candidate, and it is the parent of K2 / K5x / K6.",
        pass_means="An empty project on Autodesk's skeleton is accepted "
                   "(expected: R9 passed with strictly more removed). K1's "
                   "census = the required-skeleton reference; the K5x/K6 "
                   "verdicts (which subtract suspect classes from THIS file) "
                   "read cleanly.",
        fail_means="Unexpected -- the neutralisation edit itself (hidden-"
                   "element lists / overrides) would be the suspect; K5x/K6 "
                   "would then need re-derivation from R9 instead.")
    rep["parent"] = _relp(R5)
    rep["kind"] = "modify+gc-delete"
    rep["step1_neutralise"] = nrep
    rep["intermediate_not_uploaded"] = _relp(step1)
    rep["seconds"] = round(time.time() - t0, 1)
    write_report("K1", rep)
    return rep


def build_K2(k1_path: str) -> dict:
    st = RR.build_state_v2(k1_path)
    keep = RR._keep_views(st)
    seed = _ids_of_classes(st, RR.V2_VIEWS) - keep
    seed |= _ids_of_classes(st, RR.V2_SCHEDULES)
    seed = _own_fixpoint(st, seed) - keep
    return gc_rung(
        "K2", k1_path, st, seed, parent_name="K1",
        desc="K1 minus every view except one 3D view ({3D}) and one floor "
             "plan (Level 1), plus their view-owned content, sheets, "
             "viewports, schedules and companions.",
        tests="View-minimality on the full skeleton: is one 3D + one plan "
              "enough (G1_candidate has 4 views: project, 3D, 2 plans).",
        pass_means="View minimality is not the constructed base's problem "
                   "(R9, which also keeps only these two views, already "
                   "suggests this).",
        fail_means="The reader needs more of the view constellation than "
                   "{3D}+plan when the FULL skeleton is present -- compare "
                   "K2's kept view/companion classes with G1's.")


def _singleton_ids(st: dict, classes: Iterable[str]) -> Set[int]:
    return _ids_of_classes(st, classes)


def build_K5_family(k1_path: str) -> List[dict]:
    """K5 + the pre-built bisection sub-rungs K5a..K5d, all derived from K1."""
    st = RR.build_state_v2(k1_path)
    reps = []
    variants = [
        ("K5", K5_ALL, "the whole document-settings SINGLETON set G1 lacks "
         "(PenWidthTable, BrowserOrganization + system navigator, "
         "MEP/structural settings singletons, the remaining UniqueElement "
         "singletons)"),
        ("K5a", K5A_PENTABLE, "PenWidthTableElem ONLY (element id 2 in EVERY "
         "sample; the real project pen table + any family-scoped copies)"),
        ("K5b", K5B_BROWSER, "the BrowserOrganization elements + the system "
         "navigator view + browser settings ONLY"),
        ("K5c", K5C_MEP_STRUCT, "the MEP / structural / analysis SETTINGS "
         "singletons ONLY (StructSettings, ReinforcementSettings, RbsWire/"
         "Pipe/Duct/Conduit/CableTray Settings+Sizes, MEPSystemTracker, "
         "area/energy settings)"),
        ("K5d", K5D_OTHER_SINGLETONS, "the REMAINING UniqueElement / project "
         "singletons ONLY (wall-join, auto-join, keynote, revisions, "
         "print/export settings, copy-monitor, trackers, plan topologies)"),
    ]
    for name, classes, what in variants:
        seed = _singleton_ids(st, classes)
        seed = _own_fixpoint(st, seed)
        reps.append(gc_rung(
            name, k1_path, st, seed, parent_name="K1",
            purge_deleted_from_latest=True,
            desc=f"K1 (empty project) minus {what}, by maximal garbage "
                 "collection -- what remains of the class is pinned by a "
                 "named survivor (see pin_evidence); the deleted ids are also "
                 "removed from the ADocument's registries (positional "
                 "singleton-table slots nulled, registry rows dropped) so the "
                 "file matches G1's condition (slot -1, element absent).",
            tests="The genesis-2 assembler's own hypothesis (its sec.5.2): the "
                  "constructed base fills 5 of the sample's 72 populated "
                  "settings-singleton slots and carries NO PenWidthTable / "
                  "BrowserOrganization / system-navigator; is any of the "
                  "removed set REQUIRED by the reader when everything else "
                  "is present?",
            pass_means=("the removed singleton set is NOT required -- retire "
                        "this class from the Bug-A suspect list." if name != "K5"
                        else "NONE of the settings singletons G1 lacks is "
                             "required -- the assembler's sec.5.2 hypothesis "
                             "is REFUTED; Bug A is the catalog (K6) or the "
                             "family documents (K4)."),
            fail_means=("this sub-set contains a REQUIRED singleton -- if K5a.."
                        "K5d were uploaded together the failing sub-rung "
                        "names it; else upload K5a..K5d next." if name == "K5"
                        else "THIS class group is required by the reader: the "
                             "constructed base must build it (constructor "
                             "backlog for the skeleton / systemtypes streams)."),
        ))
    return reps


def build_K6(k1_path: str) -> dict:
    st = RR.build_state_v2(k1_path)
    seed = _ids_of_classes(st, K6_CATALOG)
    return gc_rung(
        "K6", k1_path, st, seed, parent_name="K1", purge_deleted_from_latest=True,
        desc="K1 (empty project) minus the built-in-category graphic-style "
             "CATALOG beyond the referenced core: every CategoryElem / "
             "GStyleElem / fill-pattern / line-pattern / material / "
             "appearance-asset / pen-table element that nothing surviving "
             "references (the object-styles table's un-referenced rows); the "
             "deleted rows are also dropped from the ADocument category / "
             "style / material tracking registries.",
        tests="G1_candidate authors ~101 category/style rows for the categories "
              "its content uses and NO built-in-category style catalog "
              "(rstbasic carries 1,533 GStyleElem + 284 CategoryElem).  Is the "
              "un-referenced part of that catalog required by the reader?",
        pass_means="The un-referenced graphic-style catalog is NOT required -- "
                   "the base only needs the rows its content references "
                   "(exactly what the house standard emits); retire the "
                   "catalog from the Bug-A suspect list.",
        fail_means="The reader REQUIRES the built-in-category graphic-style "
                   "catalog even for un-used categories -- the genesis base "
                   "must generate the full object-styles table (the "
                   "counsel item B5 / `object_styles.json` question becomes "
                   "load-bearing).")


# ===========================================================================
# Branch B -- from R9.rvt : the FAMILY-DOCUMENT question
# ===========================================================================

FAM_USAGE_NOTE = (
    "Family-USAGE fields nulled to -1 (or their map/list entries dropped) so "
    "the loadable-family layer becomes deletable: LevelAttributes / "
    "GridAttributes / CalloutTag / ViewportAttributes .m_familyTagId, "
    "SectionAttributes.m_sectionHead|TailFamilyTagId, InteriorElevAttributes"
    ".m_elevationSymbolId, StructSettingsElem.m_bcFixedFamilyId, "
    "CopyWatchProperties.m_typeCopyMap[*], AreaReportSettingsElem"
    ".m_allSettings[*].m_idFont[*], LegendComponent.m_previewFamily"
    "SurrogateId, and any other survivor field naming a family-layer id.  "
    "Every one is the M3-certified modify path (record re-encoded byte-exact, "
    "stamp recomputed).")


def family_layer(st: dict, *, loadable_only: bool = True) -> dict:
    """The FAMILY LAYER of ``st``: root family elements + type surrogates +
    every family-scoped CHILD (any element whose ``m_famId`` names a family
    in the layer, iterated to a fixpoint) + placed instances of its symbols.

    ``loadable_only`` keeps the curtain-wall SYSTEM families (Rectangular /
    Circular / corner mullions, System Panel, Empty System Panel) OUT of the
    layer: they own no embedded document, and in the sample every one of
    them scopes 9 family-editor DBViewTypes + a PenWidthTable + attribute
    types living in the HOST document (m_famId-scoped) -- exactly the
    system-family machinery a project keeps.  Returns
    {ids, families:{id:name}, children_by_class, docs:[{guid,unit,family}]}.
    """
    doc, cls_of, host = st["doc"], st["cls_of"], st["host"]
    from rvt import families as FAM
    famdocs = FAM.family_documents(source_path_of(st))
    doc_of_family = {fd["family_id"]: fd for fd in famdocs}
    fam_ids = {e for e in host if cls_of.get(e) == "Family"}
    if loadable_only:
        fam_ids = {f for f in fam_ids if doc_of_family.get(f, {}).get("unit") is not None
                   or doc_of_family.get(f, {}).get("content_doc_guid")}
    names = {e: (doc.value(e) or {}).get("m_name") for e in fam_ids}
    # LINKING FIELDS [decoded on rstbasic R9]: family-scoped children carry
    # m_famId == family (categories, styles, fonts, attribute types, params,
    # images); FamilySymbol.m_familyId == family (its m_famId is -1);
    # FamilySurrogate.m_elemId == family; FamSymSurrogate.m_elemId ==
    # symbol (+ m_famSurrogateId); ParamElemFamily is ElemTable-owned by the
    # family (m_OwningElementId); instances name their symbol
    # (m_masterSymbolId / InstanceInfo.m_symbolId).  Fixpoint over all links.
    layer = set(fam_ids)
    et = getattr(doc, "et_by_id", {}) or {}
    changed = True
    while changed:
        changed = False
        for e in host:
            if e in layer:
                continue
            v = doc.value(e)
            if not isinstance(v, dict):
                v = {}
            links = [v.get("m_famId"), v.get("m_familyId"), v.get("m_famSurrogateId")]
            c = cls_of.get(e)
            if c in ("FamilySurrogate", "FamSymSurrogate"):
                links.append(v.get("m_elemId"))
            if c == "FamilyInstance":
                links.append(v.get("m_masterSymbolId"))
                ii = ((v.get("m_pInstanceInfo") or {}).get("value")
                      if isinstance(v.get("m_pInstanceInfo"), dict) else None) or {}
                links.append(ii.get("m_symbolId"))
            r = et.get(e)
            if r is not None:
                own = getattr(r, "owner_id", None)
                if own is not None and 0 < own < (1 << 63):
                    links.append(own)
            if any(isinstance(x, int) and x in layer for x in links):
                layer.add(e)
                changed = True
        # legend components that depict a layer family / symbol (they
        # reference the surrogate); pinned ones (wall/floor-type legends)
        # survive the later maxgc and are attributed there
        for e in _ids_of_classes(st, {"LegendComponent"}) - layer:
            if st["graph"].get(e, set()) & layer or \
               (st["referrers"].get(e, set()) & layer):
                layer.add(e)
                changed = True
    docs = [{"guid": fd.get("content_doc_guid"), "unit": fd.get("unit"),
             "family": fd.get("family_name")} for fd in famdocs
            if fd.get("family_id") in fam_ids]
    return {"ids": layer, "families": names,
            "children_by_class": _class_hist(st, layer - fam_ids), "docs": docs}


def source_path_of(st: dict) -> str:
    return st["src"]


def neutralise_referrers(st: dict, targets: Set[int], out_path: str,
                         *, name: str) -> dict:
    """Emit ``out_path`` = st's file with every SURVIVOR field that names a
    ``targets`` id neutralised (scalar id -> -1, id-list entry removed,
    structured entry mentioning it dropped) -- the manipulate module's
    certified soft-referrer rule (M2/M3 acceptance files).  Targets are NOT
    deleted here.  Returns the field-level edit log."""
    from rvt import manipulate as MP
    doc = st["doc"]
    refmap = MP.referrers(doc, targets)
    sess = MP.session(doc)
    sess.plans.clear()
    plans = []
    edit_log = []
    skipped_embedded = 0
    for rid in sorted(refmap):
        if rid in targets:
            continue
        if rid not in st["host"]:
            # a referrer inside an EMBEDDED document (save units 1..k):
            # only the host document (unit 0) is re-emitted by the modify
            # path -- these edges vanish when the documents themselves are
            # removed (K4) and are reported, not edited.
            skipped_embedded += 1
            continue
        info = refmap[rid]
        pl = MP.ModifyPlan(kind="neutralise", elem_id=rid,
                           class_name=info["class"])
        touched = False
        for seq in sorted(info["refs"]):
            try:
                val = sess.value(rid, seq)
            except Exception as e:                      # left as-is, reported
                edit_log.append({"id": rid, "class": info["class"], "seq": seq,
                                 "error": repr(e)})
                continue
            ed = MP._neutralise(val, targets)
            if not ed:
                continue
            touched = True
            edit_log.append({"id": rid, "class": info["class"], "seq": seq,
                             "edits": ed[:12], "n_edits": len(ed)})
            pl.record_edits.append(sess.replacement(
                rid, seq, f"{name}: neutralise family-layer usage refs"))
        if touched:
            plans.append(pl)
    if not plans:
        # no referrers -- byte-identical copy is pointless but keep the
        # ladder shape: just re-emit via commit_plans with no edits.
        pass
    MP.commit_plans(source_path_of(st), out_path, plans)
    ver = MP.verify_manipulated(out_path, edited_ids=[p.elem_id for p in plans])
    edited_by_class = Counter(e.get("class") for e in edit_log if e.get("n_edits"))
    return {"referrer_elements_edited": len(plans), "edits": edit_log,
            "edits_by_referrer_class": edited_by_class.most_common(30),
            "embedded_document_referrers_not_edited": skipped_embedded,
            "verify": {k: ver[k] for k in ("crc_failures", "ecc_mismatches",
                                            "walker_errors", "stamps_ok",
                                            "elemtable_count",
                                            "isize_identity_mismatches")}}


def _cross_doc_edges(st: dict, targets: Set[int]) -> Dict[Tuple[str, str], int]:
    """Edges from elements INSIDE embedded documents (units 1..k) into
    ``targets`` (host elements): the embedded-document <-> host-catalog
    linkage discovered by this stream (family documents reference the host's
    family-scoped category/style rows, fill patterns, materials, fonts)."""
    cls_of = st["cls_of"]
    out: Counter = Counter()
    for t in targets:
        for r in st["referrers"].get(t, ()):
            if r not in st["host"]:
                out[(cls_of.get(r, "?"), cls_of.get(t, "?"))] += 1
    return out


def build_K3(st9: dict) -> Tuple[dict, str]:
    """R9 with every USAGE field naming the loadable-family layer nulled --
    a pure MODIFY probe; the family layer, its 14 documents and the 38
    orphan documents are all still present (charter K3)."""
    t0 = time.time()
    lay = family_layer(st9)
    F = lay["ids"]
    out = os.path.join(TRIAGE, "K3.rvt")
    nrep = neutralise_referrers(st9, F, out, name="K3")
    val = validate(out)
    cen = census(out)
    # what still references the layer? (host = should be nothing; embedded
    # = the documents' own references, which vanish at K4)
    st1 = RR.build_state_v2(out)
    F1 = {e for e in F if e in st1["host"]}
    host_pins = Counter()
    for f in F1:
        for r in st1["referrers"].get(f, ()):
            if r in st1["host"] and r not in F1:
                host_pins[(st1["cls_of"].get(r, "?"), st1["cls_of"].get(f, "?"))] += 1
    xdoc = _cross_doc_edges(st1, F1)
    rep = {
        "rung": "K3", "kind": "modify (usage-null)", "parent": _relp(R9),
        "parent_rung": "R9 (viewer PASS)", "out": _relp(out),
        "description": (
            "R9 (deepest viewer-PASSED file) with every USAGE field that "
            "names the LOADABLE-family layer nulled: " + FAM_USAGE_NOTE +
            "  The loadable-family layer itself (13 families: annotation heads / "
            "tails, level+grid+callout heads, elevation marks, view title, "
            "boundary condition, A1-metric title block, M_HSS default column; "
            "+ symbols / surrogates + every m_famId-scoped child) is still "
            "PRESENT, as are all 52 embedded family documents.  A pure "
            "record-edit probe (the M3-certified modify path, records "
            "re-encoded byte-exact, stamps recomputed)."),
        "tests": ("Charter K3: annotation-head / tag-family USAGE released -- "
                  "the level type, grid type, callout, viewport, section and "
                  "interior-elevation attributes and StructSettings name NO "
                  "family (-1 = 'none').  Is a view-type / annotation-type "
                  "default of NONE reader-legal?  This is also the mandatory "
                  "parent state of K4 (whose family layer + documents are "
                  "deleted from THIS file)."),
        "if_PASS": ("Head/tag defaults of 'none' are legal; K4's verdict (the "
                    "layer + all documents removed) reads cleanly."),
        "if_FAIL": ("The reader requires the head/tag USAGE fields to name "
                    "real families (a default-head requirement, not a document "
                    "requirement) -- K4's verdict is moot until this is split; "
                    "genesis must author view types WITH head families."),
        "family_layer": {
            "families": lay["families"],
            "size": len(F),
            "children_by_class": lay["children_by_class"],
            "embedded_documents_of_these_families": lay["docs"],
        },
        "neutralise": nrep,
        "residual_host_referrers_of_layer": [f"{a} -> {b} x{n}" for (a, b), n in host_pins.most_common(30)],
        "embedded_document_referrers_of_layer": [f"{a} -> {b} x{n}" for (a, b), n in xdoc.most_common(30)],
        "structural_ok": bool(nrep["verify"].get("walker_errors", 1) == 0
                              and nrep["verify"].get("crc_failures", 1) == 0
                              and nrep["verify"].get("ecc_mismatches", 1) == 0
                              and nrep["verify"].get("stamps_ok", False)),
        "validator": val,
        "census": cen,
        "seconds": round(time.time() - t0, 1),
    }
    write_report("K3", rep)
    log(f"[K3] R9 with the loadable-family USAGE fields nulled (families + docs kept)\n"
        f"      layer {len(F):,} elements ({len(lay['families'])} families); "
        f"referrer elements edited {nrep['referrer_elements_edited']} "
        f"({dict(nrep['edits_by_referrer_class'][:6])}); residual host referrers "
        f"{sum(host_pins.values())}; embedded-doc referrers {sum(xdoc.values())}; "
        f"{cen['elements']:,} elements, {cen['file_size']:,} B; "
        f"validator_ok={val['ok']} (errors {val['errors']}); {rep['seconds']}s")
    if not (rep["structural_ok"] and val["ok"] and val["errors"] == 0):
        rep["FAILED_SELF_CHECK"] = True
        log(f"[K3] *** SELF-CHECK FAILED: {val.get('error_messages')}")
        write_report("K3", rep)
    return rep, out


def _delete_layer_after_docs(name: str, k3_path: str, layer: Set[int],
                             remove_guids: Set[str], *, desc: str, tests: str,
                             pass_means: str, fail_means: str,
                             extra_delete_classes: Iterable[str] = ("LegendComponent",),
                             ) -> dict:
    """Shared body of K4 / K4b: (1) remove the given embedded documents
    coherently from ``k3_path`` (units + ContentDocuments + ContentTable),
    (2) maxgc-delete the family layer (now reference-free) plus any element
    of ``extra_delete_classes`` that referenced it, (3) validate."""
    t0 = time.time()
    tmp = os.path.join(TRIAGE, f".{name}_docs_removed.rvt")
    rrep = remove_documents(k3_path, tmp, remove_guids, reconcile_contenttable=True)
    st = RR.build_state_v2(tmp)
    L = {e for e in layer if e in st["host"]}
    # legend components / other artefacts that (used to) depict the layer
    for cls in extra_delete_classes:
        L |= _ids_of_classes(st, {cls})
    L = RR._protect_history(st, L)
    delete, kept, ev = RR.maxgc(st, L)
    out = os.path.join(TRIAGE, f"{name}.rvt")
    delete_elements(tmp, out, delete)
    os.remove(tmp)
    resid = _residual_guid_hits(out, remove_guids)
    struct_ok = verify_reduced(out, delete)
    val = validate(out)
    cen = census(out)
    rep = {
        "rung": name, "kind": "documents+family-layer removal",
        "parent": _relp(k3_path), "parent_rung": "K3", "out": _relp(out),
        "description": desc, "tests": tests,
        "if_PASS": pass_means, "if_FAIL": fail_means,
        "documents_removed": len(remove_guids),
        "removal": rrep,
        "residual_guid_bytes_in_Latest_and_ContentDocuments": resid,
        "layer_gc": {"seed": len(L), "deleted": len(delete), "kept_pinned": len(kept),
                     "deleted_by_class": _class_hist(st, delete),
                     "kept_by_class": _class_hist(st, kept),
                     "pin_evidence": ev},
        "coherence_after": {
            "save_units": cen.get("save_units"),
            "contentdocs_entries": cen.get("contentdocs_entries"),
            "contenttable_records": cen.get("contenttable_records"),
        },
        "structural_ok": bool(struct_ok["ok"]),
        "validator": val,
        "census": cen,
        "seconds": round(time.time() - t0, 1),
    }
    write_report(name, rep)
    log(f"[{name}] {desc[:96]}...\n"
        f"      docs removed {len(remove_guids)} (units {rrep['units_before']}->"
        f"{rrep['units_after']}, CD {rrep['cd_entries_before']}->"
        f"{rrep['cd_entries_after']}, ContentTable "
        f"{rrep.get('contenttable_records_before')}->{rrep.get('contenttable_records_after')}); "
        f"layer seed {len(L):,} -> deleted {len(delete):,} (kept/pinned {len(kept)}); "
        f"{cen['elements']:,} elements, {cen['file_size']:,} B; "
        f"structural={struct_ok['ok']} validator_ok={val['ok']} "
        f"(errors {val['errors']}); residual-guid-bytes {sum(resid.values())}; "
        f"{rep['seconds']}s")
    if not (struct_ok["ok"] and val["ok"] and val["errors"] == 0):
        rep["FAILED_SELF_CHECK"] = True
        log(f"[{name}] *** SELF-CHECK FAILED: {val.get('error_messages')} "
            f"{struct_ok if not struct_ok['ok'] else ''}")
        write_report(name, rep)
    return rep


# ---------------------------------------------------------------------------
# coherent EMBEDDED-DOCUMENT removal (KD1 / K4)
# ---------------------------------------------------------------------------

def _unit_guid_map(path: str) -> Tuple[list, Dict[str, int]]:
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        ranges, w = RR._unit_ranges(f.logical(pname))
    guid_of_unit = {}
    for idx, guid, s, e in ranges:
        if idx != 0 and guid:
            guid_of_unit[str(guid).lower()] = idx
    return ranges, guid_of_unit


def remove_documents(src: str, out: str, guids_remove: Set[str], *,
                     reconcile_contenttable: bool = True,
                     reconcile_familymgr: bool = True) -> dict:
    """Remove embedded family documents COHERENTLY.  A document GUID lives
    in FOUR places (mapped on rstbasic R9): the save-unit separator inside
    ``Partitions/<N>``, its ``Global/ContentDocuments`` entry, the ADocument
    ``ContentTable.m_ContentRecSet[].m_ContentKey.m_guidKey``, and the
    ADocument ``FamilyMgr.m_arrLoadedFamilyInfo[].m_familyDocGUIDs[]``
    (AppInfo slot 0, one entry per loaded family: ``{m_surrogateId,
    m_familyDocGUIDs}``).  This does (1) splice the units out of the
    partition, (2) re-assemble ContentDocuments without them (SOLVED
    grammar, ``rvt.famgen.factory``, byte-exact on the corpus), (3) drop the
    ContentTable records, (4) remove the GUIDs from the FamilyMgr entries and
    drop every entry that thereby LOSES its documents (a family that only
    exists as an unloaded registry row) -- (3)+(4) are the reconciliation
    the viewer-FAILED R9b/R10b splices lacked.  Touched streams are CRCIO
    re-framed; everything else is byte-preserved.
    """
    from rvt.famgen.factory import (parse_content_documents,
                                    assemble_content_documents, CD_END_RECORD)
    from rvt.partitions import StreamWalker
    want = {str(g).lower() for g in guids_remove}
    rep: Dict[str, object] = {"guids_removed": sorted(want)}
    entries = read_entries(src)
    new_streams: Dict[str, bytes] = {}
    with open_rvt(src) as f:
        pname = f.partition_streams()[0]
        # ---- (1) partition save units ------------------------------------
        logical = f.logical(pname)
        ranges, w = RR._unit_ranges(logical)
        keep_chunks = [bytes(logical[:18])]
        removed_units = []
        for idx, guid, s, e in ranges:
            g = str(guid).lower() if guid else None
            if idx != 0 and g in want:
                removed_units.append({"unit": idx, "guid": g, "bytes": e - s})
                continue
            keep_chunks.append(bytes(logical[s:e]))
        keep_chunks.append(bytes(logical[w.end_offset:]))
        new_logical = b"".join(keep_chunks)
        w2 = StreamWalker(new_logical, inflate=False, keep_data=False)
        if w2.errors:
            raise RuntimeError(f"walker errors after unit removal: {w2.errors[:3]}")
        rep.update({"units_before": len(ranges), "units_after": len(w2.units),
                    "removed_units": removed_units,
                    "partition_bytes_before": len(logical),
                    "partition_bytes_after": len(new_logical)})
        part_logical = bytes(new_logical[:w2.end_offset + len(w2.end_record)])
        new_streams[pname] = ecc.frame_stream(part_logical)
        # ---- (2) Global/ContentDocuments (solved grammar) -------------------
        payload = b"".join(f.inflate_all("Global/ContentDocuments"))
        cd_entries, tail = parse_content_documents(payload)
        kept = [(g, a) for (g, a) in cd_entries if g.lower() not in want]
        new_payload = assemble_content_documents(kept, tail=tail or CD_END_RECORD)
        # grammar self-check: the emitted payload must re-parse to what we kept
        chk, chk_tail = parse_content_documents(new_payload)
        assert [g for g, _ in chk] == [g for g, _ in sorted(
            kept, key=lambda e: __import__("uuid").UUID(e[0]).bytes_le)], "CD reassembly mismatch"
        rep.update({"cd_entries_before": len(cd_entries), "cd_entries_after": len(chk),
                    "cd_payload_before": len(payload), "cd_payload_after": len(new_payload),
                    "cd_tail_ok": chk_tail == (tail or CD_END_RECORD)})
        cd_logical = wrap_global_stream("Global/ContentDocuments", new_payload, level=3)
        new_streams["Global/ContentDocuments"] = ecc.frame_stream(cd_logical)
        # ---- (3)+(4) ADocument registries: ContentTable + FamilyMgr ------
        if reconcile_contenttable or reconcile_familymgr:
            lat = f.inflate("Global/Latest")
            a = adoc.decode_latest(lat)
            v = json.loads(json.dumps(a.value))     # deep copy
            n_before = n_after = None
            fm_before = fm_after = fm_guids_removed = None
            if reconcile_contenttable:
                ct = (v.get("m_oContentTable") or {}).get("value")
                if ct is not None and isinstance(ct.get("m_ContentRecSet"), list):
                    recs = ct["m_ContentRecSet"]
                    n_before = len(recs)
                    ct["m_ContentRecSet"] = [
                        r for r in recs
                        if str(((r.get("m_ContentKey") or {}).get("m_guidKey")) or "").lower()
                        not in want]
                    n_after = len(ct["m_ContentRecSet"])
            if reconcile_familymgr:
                mgr = (v.get("m_pAppInfoManager") or {}).get("value") or {}
                for slot in mgr.get("m_appInfoArr") or []:
                    if not (isinstance(slot, dict) and slot.get("ptr_class") == "FamilyMgr"):
                        continue
                    body = slot.get("value") or {}
                    arr = body.get("m_arrLoadedFamilyInfo")
                    if not isinstance(arr, list):
                        continue
                    fm_before = len(arr)
                    fm_guids_removed = 0
                    kept_entries = []
                    for ent in arr:
                        gl = ent.get("m_familyDocGUIDs")
                        if isinstance(gl, list) and gl:
                            newl = [g for g in gl if str(g).lower() not in want]
                            fm_guids_removed += len(gl) - len(newl)
                            if not newl:
                                continue           # family unloaded: drop entry
                            ent["m_familyDocGUIDs"] = newl
                        kept_entries.append(ent)
                    body["m_arrLoadedFamilyInfo"] = kept_entries
                    fm_after = len(kept_entries)
            new_payload_lat = adoc.encode_latest(v)
            back = adoc.decode_latest(new_payload_lat)
            assert back.value == v, "ADocument re-encode is not lossless"
            lat_logical = wrap_global_stream("Global/Latest", new_payload_lat, level=3)
            new_streams["Global/Latest"] = ecc.frame_stream(lat_logical)
            rep.update({"contenttable_records_before": n_before,
                        "contenttable_records_after": n_after,
                        "familymgr_entries_before": fm_before,
                        "familymgr_entries_after": fm_after,
                        "familymgr_doc_guids_removed": fm_guids_removed,
                        "latest_payload_before": len(lat),
                        "latest_payload_after": len(new_payload_lat)})
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out, out_entries)
    return rep


def _residual_guid_hits(path: str, guids: Iterable[str]) -> Dict[str, int]:
    """Count bytes_le occurrences of each removed GUID anywhere in the
    inflated Global/Latest + Global/ContentDocuments (a residual-reference
    check the record reports; 0 = fully reconciled)."""
    import uuid
    with open_rvt(path) as f:
        blobs = f.inflate("Global/Latest") + b"".join(
            f.inflate_all("Global/ContentDocuments"))
    return {g: blobs.count(uuid.UUID(g).bytes_le) for g in guids}


def orphan_document_guids(path: str) -> Tuple[Set[str], Set[str], dict]:
    """(orphans, referenced) content-document GUIDs of ``path``.

    referenced = documents named by a HOST Family element
    (m_oFamDoc.m_contentDocGUID) + nested closure (a kept document's own
    Family elements naming another document's GUID); orphans = every other
    partition save unit (units 1..k)."""
    from rvt import families as FAM
    ranges, guid_of_unit = _unit_guid_map(path)
    unit_of_guid = {g: u for g, u in guid_of_unit.items()}
    all_guids = set(guid_of_unit)
    famdocs = FAM.family_documents(path)
    referenced: Set[str] = {str(fd["content_doc_guid"]).lower() for fd in famdocs
                            if fd.get("content_doc_guid")}
    # nested closure via Family elements INSIDE kept units
    idx = FAM.FamilyIndex.open(path)
    fam_cls = idx.schema.by_name["Family"].type_id
    changed = True
    while changed:
        changed = False
        for g in list(referenced):
            u = unit_of_guid.get(g)
            if u is None:
                continue
            for eid, r in idx.unit_records(u).get(102, {}).items():
                if r.class_id != fam_cls:
                    continue
                v = idx.value(u, eid) or {}
                ng = ((v.get("m_oFamDoc") or {}).get("value") or {}).get("m_contentDocGUID")
                if ng:
                    ng = str(ng).lower()
                    if ng in all_guids and ng not in referenced:
                        referenced.add(ng)
                        changed = True
    orphans = all_guids - referenced
    info = {"units_total": len(all_guids), "referenced": len(referenced & all_guids),
            "orphans": len(orphans),
            "host_families_with_docs": [
                {"family": fd.get("family_name"), "guid": fd.get("content_doc_guid"),
                 "unit": fd.get("unit")} for fd in famdocs]}
    return orphans, referenced & all_guids, info


def _r9b_removed_guids() -> Set[str]:
    """The EXACT save-unit GUIDs the (viewer-FAILED) R9b splice removed --
    KD1 removes the same set so that KD1-vs-R9b differs ONLY in the
    ContentTable reconciliation (+ the solved-grammar reassembly)."""
    p = os.path.join(GEN, "R9b.json")
    if not os.path.exists(p):
        return set()
    with open(p) as fh:
        j = json.load(fh)
    return {str(u["guid"]).lower() for u in (j.get("removed_units") or []) if u.get("guid")}


def build_KD1(name: str = "KD1", *, familymgr: bool = True) -> dict:
    """R9 minus its ORPHAN embedded documents, coherently (Bug-B control).

    ``KD1`` reconciles BOTH document registries (ContentTable + FamilyMgr);
    ``KD1a`` reconciles the ContentTable only (FamilyMgr entries keep naming
    the removed GUIDs) -- the splitter that tells the two registries apart
    if KD1 passes."""
    t0 = time.time()
    orphans_computed, kept_docs, info = orphan_document_guids(R9)
    r9b = _r9b_removed_guids()
    orphans = r9b or orphans_computed
    info["orphan_source"] = ("R9b.json removed_units (the exact viewer-FAILED "
                             "R9b splice set)" if r9b else "computed (host Family "
                             "GUID refs + nested closure)")
    info["computed_vs_r9b_symmetric_difference"] = (len(r9b ^ orphans_computed)
                                                    if r9b else None)
    out = os.path.join(TRIAGE, f"{name}.rvt")
    rrep = remove_documents(R9, out, orphans, reconcile_contenttable=True,
                            reconcile_familymgr=familymgr)
    resid = _residual_guid_hits(out, orphans)
    struct_ok = verify_reduced(out, [])
    val = validate(out)
    cen = census(out)
    rep = {
        "rung": name, "kind": "document-removal (Bug-B control)",
        "familymgr_reconciled": familymgr,
        "parent": _relp(R9), "parent_rung": "R9 (viewer PASS)", "out": _relp(out),
        "description": (
            "R9 minus EXACTLY the 38 orphan embedded family documents the "
            "(viewer-FAILED) R9b splice removed (documents whose host Family "
            "element R9 had already deleted; the 14 documents of R9's "
            "surviving loadable families are KEPT), but removed COHERENTLY: "
            "partition save units spliced, their Global/ContentDocuments "
            "entries removed with the SOLVED grammar (rvt.famgen parse/"
            "assemble, byte-exact on the corpus), their ADocument "
            "ContentTable.m_ContentRecSet records dropped" +
            (", AND the ADocument FamilyMgr.m_arrLoadedFamilyInfo entries whose "
             "documents vanished dropped (the second loaded-document registry, "
             "AppInfo slot 0, mapped by this stream: a document GUID lives in "
             "the unit separator, its ContentDocuments entry, its ContentTable "
             "record and its FamilyMgr entry -- all four reconciled here)." if familymgr else
             " -- but the FamilyMgr.m_arrLoadedFamilyInfo entries (AppInfo slot 0, "
             "the second loaded-document registry) are left naming the removed "
             "GUIDs.  = KD1 with only the ContentTable reconciled.") +
            "  R9b removed the same 38 units + entries WITHOUT touching either "
            "registry and FAILED."),
        "tests": ("BUG-B control: is COHERENT embedded-document removal "
                  "reader-accepted?  The difference from R9b (FAIL) is the "
                  "registry reconciliation + the grammar-exact reassembly, so "
                  "a PASS convicts registry incoherence as Bug B; and it is the "
                  "prerequisite that makes the K4 (zero-document) verdict "
                  "interpretable." + ("" if familymgr else "  KD1a-vs-KD1 "
                  "splits WHICH registry: KD1 PASS + KD1a FAIL => the FamilyMgr "
                  "entries were the killer, not the ContentTable.")),
        "if_PASS": (("Fully coherent unit removal is accepted: Bug B = the "
                     "missing registry reconciliation (ContentTable and/or "
                     "FamilyMgr -- KD1a tells which), and K4's verdict reads "
                     "cleanly on the family-document question.") if familymgr else
                    "The FamilyMgr entries may name absent documents -- Bug B "
                    "was the ContentTable count alone."),
        "if_FAIL": (("Unit removal is rejected even with every known registry "
                     "reconciled -- a deeper removal defect (a fourth "
                     "coherence surface); K4 cannot be read as a 'documents "
                     "are required' verdict until this passes.") if familymgr else
                    "(with KD1 PASSING) the FamilyMgr loaded-family registry MUST "
                    "be reconciled -- naming a vanished document GUID there is "
                    "fatal (a Bug-B mechanism)."),
        "orphan_analysis": info,
        "removal": rrep,
        "residual_guid_bytes_in_Latest_and_ContentDocuments": resid,
        "coherence_after": {
            "save_units": cen.get("save_units"),
            "contentdocs_entries": cen.get("contentdocs_entries"),
            "contenttable_records": cen.get("contenttable_records"),
            "coherent": (cen.get("save_units", 0) - 1 == cen.get("contentdocs_entries")
                         == cen.get("contenttable_records")),
        },
        "structural_ok": bool(struct_ok["ok"]),
        "validator": val,
        "census": cen,
        "seconds": round(time.time() - t0, 1),
    }
    rep["coherence_after"]["familymgr_entries"] = rrep.get("familymgr_entries_after")
    write_report(name, rep)
    log(f"[{name}] R9 minus {len(orphans)} orphan documents "
        f"({'ContentTable+FamilyMgr' if familymgr else 'ContentTable ONLY'} reconciled) -> "
        f"units {rrep['units_before']}->{rrep['units_after']}, CD entries "
        f"{rrep['cd_entries_before']}->{rrep['cd_entries_after']}, ContentTable "
        f"{rrep.get('contenttable_records_before')}->{rrep.get('contenttable_records_after')}, "
        f"FamilyMgr {rrep.get('familymgr_entries_before')}->{rrep.get('familymgr_entries_after')}; "
        f"coherent={rep['coherence_after']['coherent']} residual-guid-bytes "
        f"{sum(resid.values())}; validator_ok={val['ok']} (errors {val['errors']}); "
        f"{rep['seconds']}s")
    if not (struct_ok["ok"] and val["ok"] and val["errors"] == 0):
        rep["FAILED_SELF_CHECK"] = True
        log(f"[{name}] *** SELF-CHECK FAILED: {val.get('error_messages')}")
        write_report(name, rep)
    return rep


def build_K4(k3_path: str, st9: dict) -> dict:
    """K3 minus the ENTIRE loadable-family layer AND all 52 embedded family
    documents together (the only coherent way to remove either: the
    documents pin the host's family-scoped rows, whose m_famId pins the
    families).  THE CRUX PROBE."""
    lay = family_layer(st9)
    _ranges, guid_of_unit = _unit_guid_map(k3_path)
    all_guids = set(guid_of_unit)
    return _delete_layer_after_docs(
        "K4", k3_path, set(lay["ids"]), all_guids,
        desc=("K3 minus the ENTIRE loadable-family layer AND ALL 52 embedded "
              "family documents, removed together and coherently: (1) every "
              "save unit 1..52 spliced out of Partitions/21, Global/"
              "ContentDocuments emptied to its 14-byte empty form (solved "
              "grammar) and the ADocument ContentTable.m_ContentRecSet "
              "emptied; then (2) the 13 loadable Family elements + their "
              "symbols / surrogates + every m_famId-scoped child (family "
              "sub-categories, styles, fonts, family-scoped text/tag/leader/"
              "dimension/section attribute types, family params, image "
              "symbols) + the depicting legend components deleted by maximal "
              "garbage collection (the documents that pinned those rows are "
              "gone, so the whole layer is now reference-free).  What remains "
              "is the SAMPLE's FULL skeleton -- every settings catalog, every "
              "built-in-category style row, every settings singleton, the 8 "
              "curtain-wall SYSTEM families and their host-scoped family-editor "
              "elements, the 3D + plan views, phases, levels, datums, project "
              "info -- with ZERO loadable families and ZERO embedded documents: "
              "the G1 condition reproduced from the PASSING side (charter K4)."),
        tests=("Does the reader accept a project with ZERO embedded family "
               "documents and ZERO loadable families when the rest of the "
               "skeleton is Autodesk's own?  G0/G1a/G1_candidate/G1b (zero "
               "documents on a CONSTRUCTED 234-element base) all FAILED; this "
               "probe separates the 'zero families/documents' variable from the "
               "'constructed skeleton' variable.  Read WITH KD1 (removal-"
               "mechanism control) and K3 (parent)."),
        pass_means=("Embedded family documents (and loadable families) are NOT "
                    "required.  Bug A is pure skeleton-completeness: a settings "
                    "singleton (a K5x FAIL names it), the built-in-category style "
                    "catalog (K6 FAIL), or another class in the skeleton census; "
                    "genesis need NOT carry family documents."),
        fail_means=("(with KD1 + K3 PASSING) The reader REQUIRES the loadable-"
                    "family / embedded-document machinery even when nothing "
                    "places or references those families: the genesis base MUST "
                    "carry at least a family-document set -> the asset-forge "
                    "L4/L5 host loader is the critical path.  K4b (one loadable "
                    "family + its document kept) then splits 'ANY document' from "
                    "'these specific annotation-head families'."),
    )


def build_K4b(k3_path: str, st9: dict) -> dict:
    """K3 minus the loadable-family layer + documents, EXCEPT one loadable
    family which stays WITH its embedded document (usage still nulled) --
    the follow-up splitter for a K4 FAIL: '>=1 document' vs 'specific heads'."""
    lay = family_layer(st9)
    doc, cls_of = st9["doc"], st9["cls_of"]
    from rvt import families as FAM
    famdocs = {fd["family_id"]: fd for fd in FAM.family_documents(source_path_of(st9))}
    ranges, guid_of_unit = _unit_guid_map(k3_path)
    all_guids = set(guid_of_unit)
    # pick the loadable family with a single, non-nested, mid-size document
    keep_fid = None
    for fid, name in sorted(lay["families"].items(),
                            key=lambda kv: -(famdocs.get(kv[0], {}).get("unit") or 0)):
        fd = famdocs.get(fid) or {}
        if fd.get("content_doc_guid") and not fd.get("n_nested_families"):
            if "View Title" in (name or "") or keep_fid is None:
                keep_fid = fid
                if "View Title" in (name or ""):
                    break
    if keep_fid is None:
        raise RuntimeError("K4b: no loadable family with a document found")
    keep_guid = str(famdocs[keep_fid]["content_doc_guid"]).lower()
    keep_name = lay["families"].get(keep_fid)
    # ids to KEEP: the family + everything scoped to it
    keep_ids: Set[int] = {keep_fid}
    for e in st9["host"]:
        v = doc.value(e)
        if isinstance(v, dict) and v.get("m_famId") == keep_fid:
            keep_ids.add(e)
    layer_wo_keep = set(lay["ids"]) - keep_ids
    remove_guids = all_guids - {keep_guid}
    return _delete_layer_after_docs(
        "K4b", k3_path, layer_wo_keep, remove_guids,
        desc=(f"K3 minus the loadable-family layer and its documents (as K4) "
              f"EXCEPT ONE loadable family kept together with its embedded "
              f"document: '{keep_name}' (family {keep_fid}, document {keep_guid}, "
              f"{len(keep_ids)} family-scoped elements).  Its usage fields were "
              f"already nulled at K3, so nothing REFERENCES it -- it is present, "
              f"loaded, indexed by the ContentTable (1 record) and "
              f"ContentDocuments (1 entry), and unused.  51 of 52 documents "
              f"and the other 12 loadable families are removed exactly as in K4."),
        tests=("The K4 splitter: if K4 (zero documents) FAILS, does keeping ANY "
               "single loadable family with its document (unused, unreferenced) "
               "make the file open?"),
        pass_means=("(given K4 FAIL) The reader requires AT LEAST ONE embedded "
                    "family document / loaded family, not any specific annotation-"
                    "head family: genesis can satisfy the requirement with a "
                    "single generated family document (asset-forge)."),
        fail_means=("(given K4 FAIL) One unused document is not enough -- the "
                    "requirement is the specific view-annotation-head / title-"
                    "block family set the view types default to, or a threshold; "
                    "next ladder: keep the annotation-head families WITH their "
                    "usage fields intact and remove everything else."),
    )


# ===========================================================================
# the inverse skeleton census (docs/writer/skeleton-census.md)
# ===========================================================================
#: heuristic ranking buckets for classes present in K1 but ABSENT from G1
RANK_RULES = [
    (0, "settings-singleton", K5_ALL | {"ElectricalSetting", "UnitsElem",
                                        "ProjectInfo", "AllProjectPhases"}),
    (1, "registry/tracker", {"MEPSystemTracker", "AssemblyTracker",
                             "HubsTracker", "AutoJoinTracker", "GCSTracker",
                             "ScheduleInstanceBaseOnSheetsTracker",
                             "AnalyticalToPhysicalRelationManager"}),
    (2, "category/style-catalog", {"CategoryElem", "GStyleElem", "FillPatternElem",
                                   "LinePatternElem", "MaterialElem",
                                   "AppearanceAssetElem"}),
    (3, "settings-catalog", {"HVACLoadSpaceTypeElem", "HVACLoadBuildingTypeElem",
                             "HVACLoadScheduleElem", "BuildingOperatingYearSchedule",
                             "RbsWireInsulationType", "PipeSegment",
                             "RbsPipeScheduleType", "RbsPipeConnectionType",
                             "RbsPipeMaterialType", "RbsWireMaterialType",
                             "RbsWireTemperatureRatingType", "LoadNatureElem",
                             "LoadCaseElem", "ElectricalLoadClassification",
                             "ElectricalDemandFactorDefinition", "AreaTypeElem",
                             "ColorFillSchema", "ConceptualSurfaceType",
                             "ListConceptualSurfaceTypes", "ImageSymbol",
                             "ImageHolder", "PropertySetElement",
                             "ParameterFilterElement", "AreaMeasureElem"}),
    (4, "view-type/annotation-attributes", {"DBViewType", "TextNoteAttributes",
                                            "TagNoteAttributes", "LeaderStyle",
                                            "DimensionStyle", "SectionAttributes",
                                            "CalloutTag", "InteriorElevAttributes",
                                            "ViewportAttributes", "GridAttributes",
                                            "LevelAttributes", "FilledRegionAttributes",
                                            "FontElem", "SpotElevationStyle",
                                            "MultiSegmentGridType"}),
    (5, "family-layer", FAMILY_ROOTS),
    (6, "view/infrastructure", {"DBViewPlan", "DBView3d", "DBViewProject",
                                 "DBDrawing", "Viewer", "Viewer3d", "Viewport",
                                 "ExtentElem", "ModelClipBox", "SunAndShadowSettings",
                                 "LightSchemeElement", "InitialViewSettings"}),
    (7, "datum/skeleton", {"Level", "Grid", "MultiSegGrid", "BasePoint", "TrueNorth",
                            "GeoSite", "GeoLocation", "ProjectPhase", "PhaseFilterElem",
                            "SketchPlane", "RefPlane", "CurveElem"}),
]


def _rank(cls: str) -> Tuple[int, str]:
    for r, label, s in RANK_RULES:
        if cls in s:
            return r, label
    if cls.endswith(("SettingsElem", "SizesElem", "Setting", "Settings")):
        return 0, "settings-singleton"
    if cls.endswith(("Tracker", "Manager", "Mgr")):
        return 1, "registry/tracker"
    if cls.endswith(("TypeElem", "Type", "Definition", "Classification", "Scheme")):
        return 3, "settings-catalog"
    return 8, "other"


def write_skeleton_census(paths: Dict[str, str]) -> str:
    """docs/writer/skeleton-census.md: class-by-class census of the K
    rungs vs G1_candidate; the ranked suspect list = classes present in K1
    (Autodesk's own empty-project skeleton) but ABSENT from G1_candidate."""
    cens = {}
    for label, p in paths.items():
        if os.path.exists(p):
            cens[label] = census(p)
    k1 = cens.get("K1", {}).get("classes", {}) or {}
    g1 = cens.get("G1_candidate", {}).get("classes", {}) or {}
    labels = [l for l in ("R9", "K1", "K2", "K3", "K4", "K4b", "KD1", "K5", "K6", "G1_candidate")
              if l in cens]
    allcls = set()
    for l in labels:
        allcls |= set((cens[l].get("classes") or {}).keys())
    # ranked suspects: in K1, absent from G1
    suspects = []
    for c in sorted(k1):
        if c not in g1:
            r, lab = _rank(c)
            suspects.append((r, lab, c, k1[c]))
    suspects.sort()
    only_g1 = sorted(c for c in g1 if c not in k1)
    shared = sorted(c for c in g1 if c in k1)
    lines = []
    lines.append("# SKELETON CENSUS -- K-ladder vs the constructed base (Bug-A triage)")
    lines.append("")
    lines.append("Generated by `tools/genesis_triage.py` (genesis-triage-a stream). "
                 "The reference skeleton is **K1** = R5.rvt (viewer PASS) minus "
                 "every placed model element: Autodesk's own EMPTY-PROJECT skeleton "
                 "(the shape of 'new project from template') on the rst basic "
                 "sample.  The subject is **G1_candidate.rvt** (constructed base, "
                 "viewer FAIL).  Every class present in K1 but absent from "
                 "G1_candidate is a Bug-A SUSPECT (the reader may require it); the "
                 "rank orders settings singletons / registries first (the "
                 "assembler's own hypothesis), then the catalogs, then the "
                 "view/annotation type layer, then the family layer.  The K "
                 "rungs are the experiments that decide the classes for real -- "
                 "the census only ranks them.")
    lines.append("")
    lines.append("## Files censused")
    lines.append("")
    lines.append("| label | file | elements | save units | ContentDocs entries | ADoc ContentTable recs | ADoc FamilyMgr entries/guids | size (B) |")
    lines.append("|---|---|--:|--:|--:|--:|--:|--:|")
    for l in labels:
        c = cens[l]
        lines.append(f"| {l} | `{c['path']}` | {c['elements']:,} | {c.get('save_units')} | "
                     f"{c.get('contentdocs_entries')} | {c.get('contenttable_records')} | "
                     f"{c.get('familymgr_entries')}/{c.get('familymgr_doc_guids')} | "
                     f"{c['file_size']:,} |")
    lines.append("")
    lines.append("Document-coherence rule (the Bug-B surface, extended by this stream): a "
                 "document GUID lives in FOUR places -- the save-unit separator in `Partitions/<N>`, "
                 "its `Global/ContentDocuments` entry, the ADocument `ContentTable.m_ContentRecSet` "
                 "record, and the ADocument `FamilyMgr.m_arrLoadedFamilyInfo[].m_familyDocGUIDs` "
                 "(AppInfo slot 0).  Coherent = `save_units - 1 == ContentDocs entries == "
                 "ContentTable records == FamilyMgr doc GUIDs`.  R9 (viewer PASS) is 52/52/52/52; "
                 "the viewer-FAILED R9b/R10b splices are units 15 / entries 14 vs ContentTable "
                 "**52** and FamilyMgr guids **52**; KD1 and K4 keep all four coherent by "
                 "construction.  G1a / G1_candidate are 0/0/0/0 -- COHERENT and still viewer-FAIL, "
                 "which is exactly why Bug A is a skeleton question and not this surface.")
    lines.append("")
    lines.append(f"## Ranked SUSPECTS -- classes in K1 (Autodesk skeleton) but ABSENT from G1_candidate ({len(suspects)})")
    lines.append("")
    lines.append("| rank | bucket | class | count in K1 | in R9? | tested by rung |")
    lines.append("|--:|---|---|--:|:--:|---|")
    r9 = cens.get("R9", {}).get("classes", {}) or {}
    def _rung_for(cls: str, bucket: str) -> str:
        if cls in K5A_PENTABLE: return "K5a"
        if cls in K5B_BROWSER: return "K5b"
        if cls in K5C_MEP_STRUCT: return "K5c"
        if cls in K5D_OTHER_SINGLETONS: return "K5d"
        if cls in K6_CATALOG: return "K6"
        if cls in FAMILY_ROOTS or cls == "FontElem": return "K3/K4"
        if bucket == "settings-catalog": return "K6-partial / (R11 catalog sweep, not built)"
        if bucket == "view-type/annotation-attributes": return "K2 (indirect)"
        return "-"
    for r, lab, c, n in suspects:
        lines.append(f"| {r} | {lab} | `{c}` | {n} | {'yes' if c in r9 else 'no'} | {_rung_for(c, lab)} |")
    lines.append("")
    lines.append("## Classes G1_candidate carries that K1 does NOT (our additions / different content mix)")
    lines.append("")
    lines.append(", ".join(f"`{c}` ({g1[c]})" for c in only_g1) or "(none)")
    lines.append("")
    lines.append("## Shared classes with counts (K1 vs G1_candidate)")
    lines.append("")
    lines.append("| class | K1 | G1_candidate |")
    lines.append("|---|--:|--:|")
    for c in sorted(shared, key=lambda x: -(k1.get(x, 0))):
        lines.append(f"| `{c}` | {k1.get(c, 0)} | {g1.get(c, 0)} |")
    lines.append("")
    lines.append("## Full census matrix (all rungs)")
    lines.append("")
    hdr = "| class | " + " | ".join(labels) + " |"
    lines.append(hdr)
    lines.append("|---|" + "|".join(["--:"] * len(labels)) + "|")
    for c in sorted(allcls, key=lambda x: -(k1.get(x, 0) or 0)):
        row = [str((cens[l].get("classes") or {}).get(c, "")) for l in labels]
        lines.append(f"| `{c}` | " + " | ".join(row) + " |")
    lines.append("")
    txt = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(CENSUS_MD), exist_ok=True)
    with open(CENSUS_MD, "w") as fh:
        fh.write(txt)
    log(f"[census] wrote {os.path.relpath(CENSUS_MD, ROOT)} "
        f"({len(suspects)} suspects; files {labels})")
    return CENSUS_MD


# ===========================================================================
# the probe manifest (ORDERED BY INFORMATION VALUE)
# ===========================================================================
PROBE_ORDER = ["K4", "KD1", "K3", "K5", "K6", "K4b", "KD1a", "K5a", "K5b", "K5c", "K5d", "K1", "K2"]
ORDER_RATIONALE = {
    "KD1a": ("The Bug-B registry splitter: KD1 with ONLY the ContentTable "
             "reconciled (FamilyMgr entries still name the removed documents). "
             "Upload after KD1 passes."),
    "K4": ("THE CRUX -- zero loadable families / zero embedded family documents "
           "on the sample's full skeleton (the G1 condition reproduced from the "
           "passing side).  Its single verdict halves the hypothesis space: "
           "PASS retires the family-document theory of Bug A; FAIL (given "
           "KD1+K3 pass) proves the base needs a family-document set."),
    "KD1": ("The Bug-B control that makes K4 readable: coherent removal of "
            "EXACTLY the 38 units R9b removed (ContentTable reconciled this "
            "time).  Also settles the R9b/R10b mechanism.  Upload together "
            "with K4 + K3."),
    "K3": ("K4's parent: R9 with the head/tag-family USAGE fields nulled, "
           "families + documents still present.  A K4 FAIL is only "
           "interpretable if K3 PASSES."),
    "K4b": ("The K4-FAIL splitter: as K4 but ONE loadable family kept with its "
            "document (unused).  Upload after K4 fails."),
    "K5": ("The assembler's own sec.5.2 hypothesis, tested in one file: the "
           "empty project minus every settings singleton the constructed base "
           "lacks.  PASS refutes it wholesale; FAIL is bisected by K5a..K5d."),
    "K6": ("The empty project minus the un-referenced built-in-category "
           "graphic-style catalog (G1's largest omission by count)."),
    "K5a": "PenWidthTableElem alone (element id 2 in every sample) -- top singleton suspect.",
    "K5b": "BrowserOrganization + system navigator + browser settings alone.",
    "K5c": "MEP / structural / analysis settings singletons alone.",
    "K5d": "The remaining UniqueElement / project singletons alone.",
    "K1": ("Reference rung + census base (expected PASS; the K5/K6/K2 parent). "
           "Upload only if a K5/K6 FAIL needs its parent confirmed."),
    "K2": ("View-minimality on the full skeleton (expected PASS; R9 already "
           "carries only these two views).  Low priority."),
}


def write_probes_manifest(reports: Dict[str, dict]) -> str:
    entries = []
    for name in PROBE_ORDER:
        rep = reports.get(name)
        if rep is None:
            fjson = os.path.join(TRIAGE, f"{name}.json")
            if os.path.exists(fjson):
                with open(fjson) as fh:
                    rep = json.load(fh)
            else:
                continue
        v = rep.get("validator", {})
        entries.append({
            "file": rep.get("out"),
            "order": len(entries) + 1,
            "order_rationale": ORDER_RATIONALE.get(name, ""),
            "derived_from": rep.get("parent"),
            "parent_rung": rep.get("parent_rung"),
            "the_ONE_thing_it_tests": rep.get("tests"),
            "what_it_removes": rep.get("description"),
            "if_PASS": rep.get("if_PASS"),
            "if_FAIL": rep.get("if_FAIL"),
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"),
                          "warnings": v.get("warnings")},
            "structural_ok": rep.get("structural_ok"),
            "elements": (rep.get("census") or {}).get("elements"),
            "coherence": {k: (rep.get("census") or {}).get(k)
                          for k in ("save_units", "contentdocs_entries",
                                    "contenttable_records")},
            "self_check_failed": bool(rep.get("FAILED_SELF_CHECK", False)),
            "report": f"experiments/genesis/triage/{name}.json",
        })
    manifest = {
        "stream": "genesis-triage-a (Bug A: skeleton-completeness bisection)",
        "situation": (
            "The Autodesk reader ACCEPTS deep sample reductions (R5, R9 PASS; "
            "R9 = model/views/types/families' host elements gone, 52 embedded "
            "documents intact) and REJECTS every constructed genesis base "
            "(G0/G1a/G1_candidate/G1b FAIL: 234 own elements, own ADocument, "
            "ZERO family documents, 5/72 settings singletons, 101-row style "
            "catalog).  Our validator calls all of them VALID.  Each probe "
            "below is derived from a viewer-PASSED file (or the previous "
            "rung) by removing ONE class of content, is dangling-reference-"
            "free by construction and validator-VALID (0 errors); the first "
            "rung the viewer REJECTS names the class the reader requires."),
        "ordering": ("Ordered by information value.  Recommended first "
                     "batch: K4 + KD1 + K3 (the family-document question, with "
                     "its control and parent) and K5 + K6 (the singleton and "
                     "catalog questions on the empty-project base); K5a..K5d "
                     "are the pre-built bisection of a K5 FAIL; K1/K2 are the "
                     "reference/parent controls (expected PASS)."),
        "known_passing_anchors": {"R5": "experiments/genesis/R5.rvt (viewer PASS)",
                                  "R9": "experiments/genesis/R9.rvt (viewer PASS, deepest)"},
        "known_failing_subject": {"G1_candidate": "experiments/genesis/G1_candidate.rvt (viewer FAIL)"},
        "reading_the_results": {
            "K4 PASS": "family documents / loadable families NOT required -> Bug A is a singleton (a K5x FAIL names it) or the style catalog (K6 FAIL) or another census class.",
            "K4 FAIL & KD1 PASS & K3 PASS": "the reader REQUIRES the loadable-family / embedded-document machinery -> genesis must ship a family-document set (asset-forge L4/L5); K4b splits 'any one document' from 'the specific head families'.",
            "K3 FAIL": "the head/tag USAGE fields must name real families (a default-head requirement) -> K4 unreadable; genesis must author view types WITH heads.",
            "KD1 FAIL": "even coherent unit removal is rejected -> a third document-coherence surface exists (Bug B is deeper); K4 unreadable.",
            "K5 FAIL": "one of K5a..K5d fails too and names the required singleton group (K5a = PenWidthTable id 2 is the prior).",
            "K6 FAIL": "the un-referenced built-in-category style catalog is required -> genesis must generate the full object-styles table.",
            "all of K3,K4,K5,K6 PASS": "the required class is one the ladder did not isolate (the 19 project DBViewTypes + annotation-attribute types, the settings CATALOGS, grids/refplanes, or the 8 curtain SYSTEM families' host-scoped editor elements) -> next ladder: R9 minus the view-type layer; R9 minus the settings catalogs; R9 minus the curtain-system-family layer.",
        },
        "probes": entries,
        "not_uploaded_intermediates": [
            "experiments/genesis/triage/K1_step1_neutralised.rvt (R5 with the "
            "views'/trackers' references to the placed model neutralised, "
            "model still present) -- the split file if K1 FAILS.",
        ],
    }
    p = os.path.join(TRIAGE, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"[probes] wrote {os.path.relpath(p, ROOT)} ({len(entries)} probes)")
    return p


# ===========================================================================
# driver
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", default="",
                    help="comma list of rungs to build (K1,K2,K3,K4,KD1,K5,K5a,K5b,K5c,K5d,K6)")
    ap.add_argument("--census-only", action="store_true",
                    help="only (re)write skeleton-census.md + probes.json from existing files")
    args = ap.parse_args(argv)
    want = {s.strip() for s in args.only.split(",") if s.strip()}
    reports: Dict[str, dict] = {}
    t0 = time.time()

    if not args.census_only:
        def wanted(*names: str) -> bool:
            return not want or bool(want & set(names))

        # ---------------- Branch A: R5 -> K1 -> (K2, K5*, K6) --------------
        k1_path = os.path.join(TRIAGE, "K1.rvt")
        if wanted("K1", "K2", "K5", "K5a", "K5b", "K5c", "K5d", "K6"):
            if wanted("K1") or not os.path.exists(k1_path):
                log("[state] building on R5.rvt (viewer PASS) ...")
                st5 = RR.build_state_v2(R5)
                reports["K1"] = build_K1(st5)
            if wanted("K2"):
                reports["K2"] = build_K2(k1_path)
            if wanted("K5", "K5a", "K5b", "K5c", "K5d"):
                for r in build_K5_family(k1_path):
                    reports[r["rung"]] = r
            if wanted("K6"):
                reports["K6"] = build_K6(k1_path)

        # ---------------- Branch B: R9 -> KD1/KD1a ; R9 -> K3 -> K4/K4b ---
        if wanted("KD1"):
            reports["KD1"] = build_KD1("KD1", familymgr=True)
        if wanted("KD1a"):
            reports["KD1a"] = build_KD1("KD1a", familymgr=False)
        if wanted("K3", "K4", "K4b"):
            k3_path = os.path.join(TRIAGE, "K3.rvt")
            log("[state] building on R9.rvt (viewer PASS, deepest) ...")
            st9 = RR.build_state_v2(R9)
            if wanted("K3") or not os.path.exists(k3_path):
                r3, k3_path = build_K3(st9)
                reports["K3"] = r3
            if wanted("K4"):
                reports["K4"] = build_K4(k3_path, st9)
            if wanted("K4b"):
                reports["K4b"] = build_K4b(k3_path, st9)

    # ---------------- census + manifest --------------------------------
    paths = {"R9": R9, "K1": os.path.join(TRIAGE, "K1.rvt"),
             "K2": os.path.join(TRIAGE, "K2.rvt"), "K3": os.path.join(TRIAGE, "K3.rvt"),
             "K4": os.path.join(TRIAGE, "K4.rvt"), "K4b": os.path.join(TRIAGE, "K4b.rvt"),
             "KD1": os.path.join(TRIAGE, "KD1.rvt"), "K5": os.path.join(TRIAGE, "K5.rvt"),
             "K6": os.path.join(TRIAGE, "K6.rvt"), "G1_candidate": G1C}
    write_skeleton_census(paths)
    write_probes_manifest(reports)

    # ---------------- summary --------------------------------------------
    log("\n=== TRIAGE SUMMARY (validator = tools/rvt_validate.py; 0 errors required) ===")
    for name in PROBE_ORDER:
        rep = reports.get(name)
        if rep is None:
            j = os.path.join(TRIAGE, f"{name}.json")
            if not os.path.exists(j):
                continue
            with open(j) as fh:
                rep = json.load(fh)
        v = rep.get("validator", {})
        cen = rep.get("census", {})
        log(f"  {name:<4} elements {cen.get('elements'):>6}  units {str(cen.get('save_units')):>3} "
            f"CD {str(cen.get('contentdocs_entries')):>3} CT {str(cen.get('contenttable_records')):>3}  "
            f"validator ok={v.get('ok')} errors={v.get('errors')} warnings={v.get('warnings')}"
            f"{'  *** SELF-CHECK FAILED ***' if rep.get('FAILED_SELF_CHECK') else ''}")
    log(f"total {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
