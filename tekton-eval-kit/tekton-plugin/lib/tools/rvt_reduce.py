#!/usr/bin/env python
"""rvt_reduce.py — staged MINIMAL-DOCUMENT reduction (GENESIS research).

Starting from a real project (default: samples/rstbasicsampleproject.rvt,
the smallest), progressively DELETE content and re-emit with our writer at
each stage, self-validating structurally, to discover the practical
minimal document that Autodesk's reader still accepts (= the future GENESIS
seed) and to map the irreducible core.

Stages (each cumulative on the previous):
  R1  remove all PLACED MODEL elements (instances, walls, floors, footings,
      rebar/analytical/loads/parts/rooms ...) + everything that references
      them (dependency closure: dimensions, tags, sketches, splitters ...).
      Keeps levels/grids/views/families/symbols/project info.
  R2  additionally remove every VIEW except one (a floor plan) plus the
      view-owned/annotation content and sheets/viewports/schedules.
  R3  additionally remove unused symbols / types / attribute elements and
      families (host-document elements only; the embedded family DOCUMENTS
      in save units 1..k are kept byte-for-byte — see genesis.md).
  R4  additionally remove remaining annotation styles / patterns /
      settings singletons that nothing surviving references (maximal
      zero-survivor-dangling sweep).

Every stage is written to experiments/genesis/R<n>.rvt + R<n>.json (report)
and structurally verified (walker / CRC / ECC / counts / sentinels / stamps
/ id-set equality).  A second family of variants R<n>s ("safe") only
deletes what leaves ZERO dangling references anywhere we can see —
including inside Global/Latest and ContentDocuments, which we do not edit —
i.e. a pure garbage-collection sweep from the same seed.

Usage:
  .venv/bin/python tools/rvt_reduce.py            # all stages (ladder v1)
  .venv/bin/python tools/rvt_reduce.py --stage R1 # one stage

LADDER v2 (R5..R10 + R9b/R10b, validator-clean by construction, see the
big header lower in this file and docs/inbox/genesis-reduction.md):
  .venv/bin/python tools/rvt_reduce.py --ladder v2                 # all
  .venv/bin/python tools/rvt_reduce.py --ladder v2 --stage R9      # one
  .venv/bin/python tools/rvt_reduce.py --ladder v2 --naive R6,R9   # +boundary probes
  Outputs experiments/genesis/R5..R10[s|b|naive].rvt + .json + summary_v2.*.
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import time
from collections import Counter, defaultdict
from typing import Iterable, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.container import open_rvt                      # noqa: E402
from rvt.mutate import Document                          # noqa: E402
from rvt.reduce import (analyze_deletion, closure_delete, delete_elements,
                        reference_graph, scan_stream_ids, verify_reduced)  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "genesis")

# ---------------------------------------------------------------------------
# class taxonomies (Revit 2026 schema names; verified against the rstbasic
# census in docs/inbox/genesis.md)
# ---------------------------------------------------------------------------

#: placed / model content: physical instances and model-space semantics
MODEL_CLASSES = {
    "FamilyInstance", "SWall", "Floor", "ContFooting", "DPart", "PartMaker",
    "Rebar", "RebarInSystem", "RebarSystem", "JoistSystem",
    "StairsElement", "StairsRun", "StairsSupport", "StairsPathElement",
    "FormElem", "MassLevelData", "ImportInstance", "RvtLinkInstance",
    "RoomElem", "ZoneElement", "Hub", "AnalyticalMember", "AnalyticalPanel",
    "LineLoad", "AreaLoad", "BoundaryConditions", "ReferencePoint",
    "CustomElement", "RegenSplitterElem", "ImageInstance",
}
#: everything view-scoped: views, view markers, sheets/viewports, schedules,
#: annotation
VIEW_CLASSES = {
    "DBView3d", "DBViewSection", "DBViewPlan", "DBViewDrafting",
    "DBViewSchedule", "DBViewAnonDrafting", "DBViewRendering", "DBViewProject",
    "DBViewGraphSchedColumn", "DBViewTypeAreaPlan", "RbsDbViewSystemNavigator",
    "DBDrawing", "Viewer", "Viewer3d", "Section", "InteriorElev",
    "InteriorElevArrow", "GraphSchedColumnTable", "Viewport", "GCSViewport",
    "ScheduleInstance", "PanelScheduleTemplate", "LevelRoomPlan",
}
ANNOTATION_CLASSES = {
    "TextNote", "LinearDimString", "Alignment", "SpotElevation",
    "IndependentTag", "FilledRegion", "LegendComponent", "SunAnnotationElem",
    "SketchGrid", "ModelClipBox", "ContourSpacingElem",
}
#: singleton / infrastructure classes NEVER deleted (project would be
#: meaningless without them; several are referenced from Global/Latest)
KEEP_ALWAYS = {
    "ProjectInfo", "Level", "BasePoint", "TrueNorth", "GeoSite", "GeoLocation",
    "ActiveGeoLocationTrackingElement", "CoordinateSystemDisplayElem",
    "UnitsElem", "CategoryElem", "GStyleElem", "ModelGraphicsStyle",
    "ProjectPhase", "AllProjectPhases", "PhaseFilterElem", "DesignOption",
    "DesignOptionSet", "WorksharingViewModeSettings",
}


def build_state(src: str) -> dict:
    t0 = time.time()
    doc = Document.from_file(src)
    graph = reference_graph(doc)
    host = set(graph)
    with open_rvt(src) as f:
        lat = f.inflate("Global/Latest")
        cdoc = f.inflate("Global/ContentDocuments")
    ext = {"Global/Latest": scan_stream_ids(lat, host),
           "Global/ContentDocuments": scan_stream_ids(cdoc, host)}
    cls_of = {e: (doc.class_of(e) or "?") for e in host}
    print(f"[state] {len(host):,} host elements, graph edges "
          f"{sum(len(v) for v in graph.values()):,}, Latest refs "
          f"{len(ext['Global/Latest']):,}, ContentDocs refs "
          f"{len(ext['Global/ContentDocuments']):,} ({time.time()-t0:.1f}s)")
    return {"doc": doc, "graph": graph, "ext": ext, "cls_of": cls_of, "host": host}


def ids_by_classes(st: dict, classes) -> set[int]:
    return {e for e, c in st["cls_of"].items() if c in classes}


def protected_set(st: dict) -> set[int]:
    """Elements that must never be deleted (for the CLOSURE variants).

    Infrastructure singletons + ContentDocuments referents + the element
    carrying the highest ``modified_ep`` (deleting it would break the
    History invariant count == max(modified_ep)+1 without a save-history
    rewrite).  Global/Latest referents are NOT protected here — leaving
    them dangling is exactly the empirical probe the closure stages make;
    the R<n>s safe sweep protects them too.
    """
    doc = st["doc"]
    prot = ids_by_classes(st, KEEP_ALWAYS)
    prot |= st["ext"]["Global/ContentDocuments"]
    if doc.et_by_id:
        top = max(doc.et_by_id.values(), key=lambda r: r.modified_ep)
        prot.add(top.id)
    return prot


def seed_for(stage: str, st: dict) -> set[int]:
    doc = st["doc"]
    cls_of = st["cls_of"]
    seed = ids_by_classes(st, MODEL_CLASSES)
    # model CurveElems (3D model lines) vs view-owned detail lines: model
    # lines have no owning view; treat every CurveElem in stage R2+.
    if stage in ("R1", "R1s"):
        return seed
    # R2: also all views but ONE plan view + all annotation
    views = ids_by_classes(st, VIEW_CLASSES)
    plans = sorted(e for e in views if cls_of[e] == "DBViewPlan")
    keep_view = _pick_keep_view(doc, plans, st) if plans else None
    seed |= (views - ({keep_view} if keep_view else set()))
    seed |= ids_by_classes(st, ANNOTATION_CLASSES)
    seed |= ids_by_classes(st, {"CurveElem", "VarSketch", "NonPlanarSketch",
                                 "SketchPlane"})
    if stage in ("R2", "R2s"):
        return seed
    # R3: unused symbols / types / families (all Symbol descendants except
    # those the keeper needs are handled by closure/protection), families +
    # surrogates
    seed |= ids_by_classes(st, {"FamilySymbol", "Family", "FamilySurrogate",
                                 "FamSymSurrogate", "SysPanelFamSym",
                                 "SysMullionFamSym", "AnnotationSymbol"})
    S = doc.dec.schema
    symbol_desc = {c.name for c in S.descendants("Symbol")} | {"Symbol"}
    seed |= {e for e, c in cls_of.items() if c in symbol_desc}
    if stage in ("R3", "R3s"):
        return seed
    # R4: everything else that isn't infrastructure — GC sweep decides
    seed |= {e for e, c in cls_of.items() if c not in KEEP_ALWAYS}
    return seed


def _pick_keep_view(doc, plans, st):
    """Prefer the plan view named like 'Level 1'/'Structural Plan' whose id is
    lowest; fall back to the first plan."""
    best = None
    for e in plans:
        v = doc.value(e) or {}
        name = str(v.get("m_viewName") or "")
        if best is None:
            best = e
        if name.strip() in ("Level 1", "Structural Plan Level 1", "Site"):
            return e
    return plans[0] if plans else best


def gc_sweep(st: dict, seed: set[int], protected: set[int]) -> set[int]:
    """SAFE reduction: delete only what leaves NO dangling reference.

    Iteratively delete every seeded element that no survivor (element or
    external stream) references; deleting can free further seeds.  The
    result never dangles inside the partitions nor inside Global/Latest /
    ContentDocuments (their referents are simply never deleted).
    """
    graph = st["graph"]
    ext_refs = set().union(*st["ext"].values())
    from collections import defaultdict
    referrers = defaultdict(set)
    for e, refs in graph.items():
        for r in refs:
            referrers[r].add(e)
    delete: set[int] = set()
    candidates = set(seed) - protected - ext_refs
    changed = True
    while changed:
        changed = False
        for e in list(candidates - delete):
            live_referrers = {s for s in referrers.get(e, ()) if s not in delete}
            if not live_referrers:
                delete.add(e)
                changed = True
    return delete


def run_stage(stage: str, st: dict, safe: bool) -> dict:
    doc, graph = st["doc"], st["graph"]
    name = stage + ("s" if safe else "")
    prot = protected_set(st)
    seed = seed_for(stage, st) - prot
    if safe:
        delete = gc_sweep(st, seed, prot)
    else:
        delete = closure_delete(graph, seed, protected=prot)
    an = analyze_deletion(doc, graph, delete, st["ext"])
    out = os.path.join(OUT, f"{name}.rvt")
    t0 = time.time()
    rep = delete_elements(SRC, out, delete)
    v = verify_reduced(out, delete)
    size = os.path.getsize(out)
    survivors = Counter(st["cls_of"][e] for e in st["host"] if e not in delete)
    res = {
        "stage": name, "safe_variant": safe, "out": os.path.relpath(out, ROOT),
        "file_size": size, "seed": len(seed), "deleted": len(delete),
        "surviving_elements": rep.elemtable_count_after,
        "elemtable_before": rep.elemtable_count_before,
        "records_removed": rep.records_removed,
        "blocks_before": rep.blocks_before, "blocks_after": rep.blocks_after,
        "structural_ok": v["ok"],
        "verify": {k: v[k] for k in ("crc_failures", "ecc_mismatches", "counts_match",
                                     "seq_id_sets_equal", "stamps_bad", "units",
                                     "blocks_unit0", "isize_identity_ok",
                                     "elemtable_ids_without_record")},
        "walker_errors": v["walker_errors"][:5],
        "dangling": {
            "survivors_with_dangling_refs": an["survivors_with_dangling_refs"],
            "dangling_by_survivor_class": an["dangling_by_survivor_class"][:15],
            "external": {k: an["external"][k] for k in an["external"]},
            "history_invariant_at_risk": an["history_invariant_at_risk"],
        },
        "deleted_by_class": an["deleted_by_class"],
        "top_survivor_classes": survivors.most_common(25),
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, f"{name}.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=lambda o: list(o) if isinstance(o, set) else str(o))
    lat = res["dangling"]["external"].get("Global/Latest", {}).get("dangling")
    print(f"[{name}] deleted {len(delete):>6,} / kept {res['surviving_elements']:>6,} "
          f"| size {size:>9,} B | structural_ok={v['ok']} | survivor-dangling "
          f"{an['survivors_with_dangling_refs']} | Latest-dangling {lat}")
    return res


# ===========================================================================
# LADDER v2 — R5..R9: validator-clean SURGICAL reduction toward the
# irreducible core (deepening the R0..R4 ladder above).
#
# Why a second ladder.  The R<n> closure stages above delete the REFERRERS
# of every deleted element ("closure"), which (a) mistakes ownership /
# constraint references for usage references and so cascades a leaf class
# (a legend component, a locked Alignment, a sketch-constraint dimension)
# straight into the whole structural model, and (b) is stopped from
# deleting protected infrastructure survivors, which then keep dangling
# ids -> R1..R4 all FAIL tools/rvt_validate.py (semantic reference layer;
# 29 / 290 / 1051 / 1871 dangling ids).  The R<n>s safe sweeps pass but
# barely move (they also protect every id merely SCANNED in Global/Latest).
#
# Ladder v2 rules (each stage one surgical class, cumulative seeds):
#   * reference graph = the arbiter's own model: rvt.validate's schema-typed
#     ElementId decoder over EVERY record of EVERY save unit (seq 102 = what
#     the validator gates on, plus seq 101/103 for the reader's benefit).
#   * deletion semantics = MAXIMAL GARBAGE COLLECTION over the cumulative
#     seed: an element may be deleted only if EVERY element that references
#     it is deleted too.  Given seed S, keep K = {s in S referenced from
#     outside S} closed FORWARD inside S (a kept element pins what it
#     references); delete = S - K.  This is dangling-free BY CONSTRUCTION
#     (validator-clean), never cascades outside the seed, handles reference
#     cycles inside the seed, and every survivor of a seeded class is
#     attributable to the outside class pinning it (= irreducible-core
#     evidence).
#   * primary variants R5..R9 ignore Global/Latest / ContentDocuments (the
#     validator does not gate on them; whether the READER tolerates dangling
#     ids inside the serialized ADocument is exactly what a viewer test of
#     this ladder measures); the R<n>s companions additionally pin every id the
#     i64 scan finds in those two streams (the R0/R4s-proven safe rule).
# ===========================================================================

#: annotation content + detail/model lines + schedule views  (R5)
V2_ANNOTATION = {
    "TextNote", "LinearDimString", "Alignment", "SpotElevation",
    "SpotElevationSymbol", "IndependentTag", "FilledRegion",
    "LegendComponent", "SunAnnotationElem", "SketchGrid", "ModelClipBox",
    "ContourSpacingElem", "CurveElem", "RevisionCloud", "Revision",
    "ViewReferencing", "MultiRefAnnotation", "RepeatingDetail",
    "ScheduleGraphics",
}
V2_SCHEDULES = {
    "DBViewSchedule", "DBViewGraphSchedColumn", "GraphSchedColumnTable",
    "ScheduleInstance", "PanelScheduleTemplate", "PanelScheduleView",
    "ScheduleInstanceBaseOnSheetsTracker",
}
#: every view class + view-owned companions  (R6; the two keepers are removed)
V2_VIEWS = {
    "DBView3d", "DBViewSection", "DBViewPlan", "DBViewDrafting",
    "DBViewSchedule", "DBViewAnonDrafting", "DBViewRendering",
    "DBViewGraphSchedColumn", "DBViewTypeAreaPlan",
    "DBDrawing", "Viewer", "Viewer3d", "Section", "InteriorElev",
    "InteriorElevArrow", "GraphSchedColumnTable", "Viewport", "GCSViewport",
    "ScheduleInstance", "PanelScheduleTemplate", "LevelRoomPlan",
    "SunAndShadowSettings", "LightSchemeElement", "ViewportAttributes",
    "SectionAttributes", "InteriorElevAttributes", "ViewSheetSet",
    "PrintSetup", "WorksetVisibilitySettingsElem",
}
#: Symbol-descendant / catalog classes NOT swept as "types" by R7 because
#: they are document infrastructure the empty base keeps (view families,
#: browser organisation, geo site) — R7 sweeps every other Symbol
#: descendant + materials/patterns/appearance assets/property sets.
V2_TYPE_EXCLUDE = {
    "DBViewType", "DBViewTypeAreaPlan", "BrowserOrganization",
    "ConstructionSetProject", "GeoSite", "ProjectPhase",
}
V2_TYPE_EXTRA = {
    "MaterialElem", "AppearanceAssetElem", "PropertySetElement",
    "PropertySetLibrary", "FillPatternElem", "LinePatternElem",
    "AreaScheme", "AreaTypeElem", "ConceptualSurfaceType",
    "ListConceptualSurfaceTypes",
}
#: design options / phases / links / worksets  (R8)
V2_OPTIONS_PHASES = {
    "DesignOption", "DesignOptionSet", "AllPlanTopologies", "PlanTopology",
    "ProjectPhase", "PhaseFilterElem", "AllProjectPhases",
    "RvtLinkSymbol", "RvtLinkInstance", "LinkLoadTable",
    "ImportInstance", "MasterImportSymbol",
}
#: families and everything that only exists as family content  (R9)
V2_FAMILY = {
    "Family", "FamilySymbol", "FamilySurrogate", "FamSymSurrogate",
    "ParamElemFamily", "AnnotationSymbol", "SysPanelFamSym",
    "SysMullionFamSym", "StairsTriserSymbol", "FontElem",
}
#: placed model content that cannot outlive its families (R9): the physical
#: instances plus every model-semantic element that references them
V2_PLACED = set(MODEL_CLASSES) | {
    "PointLoad", "Grid", "MultiSegGrid", "RoofElem", "CeilingElem",
    "TopographySurface", "ToposolidElem", "BuildingPadElem", "PathReinf",
    "AreaReinf", "FabricSheet", "FabricArea", "GCSTracker", "Truss",
    "BeamSystem", "StructConnection",
}
#: BONUS stage R10 — parameter / classification DEFINITION tables the
#: sample authored (shared-parameter defs, project params, their category
#: bindings, electrical load classifications, property sets).  A GC sweep:
#: only the definitions nothing surviving references die.
V2_PARAM_DEFS = {
    "ParamElemExternal", "ParamElemProject", "ParamBinding",
    "ParamElemElectricalLoadClassification", "PropertySetElement",
    "PropertySetLibrary", "ElectricalLoadClassification",
    "ElectricalDemandFactorDefinition", "KeynoteEntry",
}
#: ownership-child classes: co-seeded whenever they reference an already
#: seeded element (a family's own sub-categories/styles/fonts, a type's
#: sub-categories, a view's drawing/viewer/viewports/sun settings/extents)
#: — they are the seeded element's children, not project infrastructure, and
#: would otherwise pin their parent forever.
V2_CHILD_CLASSES = {"CategoryElem", "GStyleElem", "FontElem", "ParamElemFamily",
                    "DBDrawing", "Viewer", "Viewer3d", "Viewport", "GCSViewport",
                    "SunAndShadowSettings", "SunAnnotationElem",
                    "LightSchemeElement", "ExtentElem", "ModelClipBox",
                    # sketch children reference their owning element/instance
                    "VarSketch", "SketchPlane", "NonPlanarSketch",
                    # derived tracker/topology caches referencing model content
                    "HubsTracker", "GCSTracker", "AutoJoinTracker",
                    "ScheduleInstanceBaseOnSheetsTracker", "PlanTopology",
                    "AllPlanTopologies", "PostedWarningElem",
                    "RegenSplitterElem", "SelectionFilterElement",
                    "InitialViewSettings"}

#: the two views the R6+ base keeps: the default 3D view and a floor plan
V2_KEEP_VIEW_NAMES = ("{3D}", "Level 1")


def build_state_v2(src: str) -> dict:
    """Load the source and build the VALIDATOR-EXACT reference graph.

    Edges = every schema-typed ElementId value the object decoder finds in
    every record of every save unit (seq 102 — the validator's gated set —
    plus seq 101 headers and seq 103 reps).  This is the same decoder
    ``rvt.validate`` uses for its dangling-reference layer, so a deletion set
    that leaves this graph consistent leaves the validator with zero
    reference errors.
    """
    t0 = time.time()
    from rvt.validate import _RefDecoder            # the arbiter's own decoder
    doc = Document.from_file(src)
    host = set(doc.et_by_id)                        # unit-0 == host document
    dec = _RefDecoder(doc.dec.schema)
    graph: dict[int, set[int]] = defaultdict(set)
    universe: set[int] = set(host)
    owner_view: dict[int, int] = {}                  # view-owned element -> owner view
    for seq in (102, 101, 103):
        for eid, rec in doc.idx[seq].items():
            universe.add(eid)
            dec.refs = []
            try:
                dec.decode_record(rec.class_id, rec.payload)
            except Exception:
                continue
            for p, v in dec.refs:
                if isinstance(v, int) and v > 0 and v != eid:
                    graph[eid].add(v)
                    fname = p.rsplit(".", 1)[-1]
                    if ("ownerDBViewId" in fname or "ownerViewId" in fname) \
                            and eid not in owner_view:
                        owner_view[eid] = v
    graph = {k: {t for t in v if t in universe} for k, v in graph.items()}
    referrers: dict[int, set[int]] = defaultdict(set)
    for e, rs in graph.items():
        for r in rs:
            referrers[r].add(e)
    cls_of = {e: (doc.class_of(e) or "?") for e in universe}
    with open_rvt(src) as f:
        lat = f.inflate("Global/Latest")
        cdoc = f.inflate("Global/ContentDocuments")
    ext = {"Global/Latest": scan_stream_ids(lat, host),
           "Global/ContentDocuments": scan_stream_ids(cdoc, host)}
    print(f"[state-v2] host {len(host):,} elems, {len(universe):,} ids file-wide, "
          f"{sum(len(v) for v in graph.values()):,} typed edges, Latest-scan "
          f"{len(ext['Global/Latest']):,} ids ({time.time() - t0:.1f}s)")
    return {"doc": doc, "src": src, "graph": graph, "referrers": referrers,
            "cls_of": cls_of, "host": host, "universe": universe, "ext": ext,
            "owner_view": owner_view}


def maxgc(st: dict, seed: Iterable[int], extra_pins: Iterable[int] = ()) -> tuple[set[int], set[int], dict]:
    """Maximal dangling-free deletion inside ``seed`` (see ladder-v2 header).

    Returns (delete, kept_seed, pin_evidence).  ``extra_pins`` are ids treated
    as referenced from outside (e.g. Global/Latest scan hits for the R<n>s
    variants)."""
    graph, referrers, cls_of = st["graph"], st["referrers"], st["cls_of"]
    seed = set(seed)
    keep: set[int] = set()
    direct_pins: dict[int, set[int]] = {}
    for s in seed:
        outs = {r for r in referrers.get(s, ()) if r not in seed}
        if outs:
            keep.add(s)
            direct_pins[s] = outs
    ext = set(extra_pins) & seed
    keep |= ext
    front = set(keep)
    while front:                                    # kept elements pin what they reference
        nxt = set()
        for k in front:
            for t in graph.get(k, ()):
                if t in seed and t not in keep:
                    keep.add(t)
                    nxt.add(t)
        front = nxt
    delete = seed - keep
    # evidence: which OUTSIDE classes directly pin which kept-seed classes
    pins = Counter()
    for k, outs in direct_pins.items():
        for r in outs:
            pins[(cls_of.get(k, "?"), cls_of.get(r, "?"))] += 1
    kept_cls = Counter(cls_of.get(k, "?") for k in keep)
    by_kept: dict = {}
    for (a, b), c in pins.most_common():
        by_kept.setdefault(a, Counter())[b] += c
    ev = {"kept_seed": len(keep), "kept_by_direct_outside_ref": len(direct_pins),
          "kept_by_ext_scan": len(ext - set(direct_pins)),
          "kept_seed_by_class": kept_cls.most_common(40),
          "top_pinning_pairs": [f"{a} <- {b} x{c}" for (a, b), c in pins.most_common(30)],
          "pinners_of_kept_class": {a: cnt.most_common(6) for a, cnt in by_kept.items()}}
    return delete, keep, ev


def _ids_of(st: dict, classes) -> set[int]:
    cs = set(classes)
    return {e for e in st["host"] if st["cls_of"].get(e) in cs}


def _keep_views(st: dict) -> set[int]:
    """The default 3D view and the 'Level 1' floor plan (lowest id per name)."""
    doc, cls_of = st["doc"], st["cls_of"]
    want = {n: None for n in V2_KEEP_VIEW_NAMES}
    for e in sorted(st["host"]):
        c = cls_of.get(e)
        if c not in ("DBView3d", "DBViewPlan"):
            continue
        v = doc.value(e) or {}
        name = str(v.get("m_viewName") or "").strip()
        if name in want and want[name] is None:
            if (name == "{3D}") == (c == "DBView3d"):
                want[name] = e
    keep = {v for v in want.values() if v is not None}
    if len(keep) < 2:                               # fallback: any 3D + any plan
        threes = sorted(_ids_of(st, {"DBView3d"}))
        plans = sorted(_ids_of(st, {"DBViewPlan"}))
        if threes and not any(cls_of.get(x) == "DBView3d" for x in keep):
            keep.add(threes[0])
        if plans and not any(cls_of.get(x) == "DBViewPlan" for x in keep):
            keep.add(plans[0])
    return keep


def _own_children(st: dict, seed: set[int]) -> set[int]:
    """Ownership children of the seed: any CategoryElem/GStyleElem/FontElem/
    ParamElemFamily/... that REFERENCES an already-seeded element (a family's
    sub-categories, styles, fonts and family parameters; a type's own
    sub-category).  Iterated to a fixpoint (children of children)."""
    graph, cls_of = st["graph"], st["cls_of"]
    cand = _ids_of(st, V2_CHILD_CLASSES)
    added: set[int] = set()
    changed = True
    seeded = set(seed)
    while changed:
        changed = False
        for e in cand - seeded:
            if graph.get(e, set()) & seeded:
                seeded.add(e)
                added.add(e)
                changed = True
    return added


def stage_seed_v2(stage: str, st: dict) -> set[int]:
    """CUMULATIVE seed for a ladder-v2 stage (R5..R9)."""
    doc, cls_of = st["doc"], st["cls_of"]
    S = doc.dec.schema
    stages = ["R5", "R6", "R7", "R8", "R9", "R10"]
    upto = stages.index(stage.rstrip("s"))
    seed: set[int] = set()
    keep_views = _keep_views(st)
    symbol_desc = {c.name for c in S.descendants("Symbol")} | {"Symbol"}
    type_classes = (symbol_desc | V2_TYPE_EXTRA) - V2_TYPE_EXCLUDE - V2_FAMILY
    for i in range(upto + 1):
        s = stages[i]
        if s == "R5":
            seed |= _ids_of(st, V2_ANNOTATION | V2_SCHEDULES)
        elif s == "R6":
            seed |= _ids_of(st, V2_VIEWS) - keep_views
        elif s == "R7":
            seed |= _ids_of(st, type_classes)
        elif s == "R8":
            seed |= _ids_of(st, V2_OPTIONS_PHASES)
        elif s == "R9":
            seed |= _ids_of(st, V2_FAMILY | V2_PLACED)
        elif s == "R10":
            seed |= _ids_of(st, V2_PARAM_DEFS)
        # ownership fixpoint: children of seeded elements (view companions,
        # sketches, family/type sub-categories, fonts, family params ...) and
        # VIEW-OWNED content (its m_ownerDBViewId is a seeded view; a view's
        # detail lines/components/tags die with the view) join the seed.
        while True:
            add = _own_children(st, seed)
            add |= {e for e, ov in st["owner_view"].items()
                    if ov in seed and e not in seed and e in st["host"]}
            add -= keep_views
            if not add:
                break
            seed |= add
    return seed - keep_views


def _protect_history(st: dict, seed: set[int]) -> set[int]:
    """Never delete the element carrying the newest modified episode (the
    History invariant count == max(modified_ep)+1)."""
    doc = st["doc"]
    if doc.et_by_id:
        top = max(doc.et_by_id.values(), key=lambda r: r.modified_ep)
        return seed - {top.id}
    return seed


def _run_validator(path: str) -> dict:
    from rvt.validate import validate_file
    rep = validate_file(path)
    errs = rep.errors
    return {"ok": bool(rep.ok), "errors": len(errs),
            "warnings": len(rep.warnings),
            "error_messages": [f"[{f.layer}] {f.where}: {f.message}"[:400] for f in errs[:6]],
            "stats": {k: v for k, v in rep.stats.items()
                      if k in ("streams", "records", "elements_decoded", "refs_checked",
                               "partition_blocks", "decode_failures")}}


def run_stage_v2(stage: str, st: dict, *, safe: bool, out_dir: str = OUT,
                 naive: bool = False) -> dict:
    """Compute + emit + validate one ladder-v2 stage.

    ``naive=True`` deletes the ENTIRE cumulative seed (ignoring pins) —
    the validation-BOUNDARY probe: it shows exactly which reference
    classes break when a removal class is taken past its pinned residue.
    """
    name = stage + ("s" if safe else "") + ("naive" if naive else "")
    seed = _protect_history(st, stage_seed_v2(stage, st))
    pins = set().union(*st["ext"].values()) if safe else set()
    if naive:
        delete, kept, ev = set(seed), set(), {"naive": True}
    else:
        delete, kept, ev = maxgc(st, seed, extra_pins=pins)
    out = os.path.join(out_dir, f"{name}.rvt")
    t0 = time.time()
    rep = delete_elements(st["src"], out, delete)
    v = verify_reduced(out, delete)
    val = _run_validator(out)
    size = os.path.getsize(out)
    cls_of, host = st["cls_of"], st["host"]
    survivors = Counter(cls_of[e] for e in host if e not in delete)
    deleted_cls = Counter(cls_of[e] for e in delete)
    lat_dangling = len(st["ext"]["Global/Latest"] & delete)
    cd_dangling = len(st["ext"]["Global/ContentDocuments"] & delete)
    res = {
        "stage": name, "ladder": "v2", "safe_variant": safe,
        "out": os.path.relpath(out, ROOT), "file_size": size,
        "seed": len(seed), "seed_kept_pinned": len(kept), "deleted": len(delete),
        "surviving_elements": rep.elemtable_count_after,
        "elemtable_before": rep.elemtable_count_before,
        "records_removed": rep.records_removed,
        "blocks_before": rep.blocks_before, "blocks_after": rep.blocks_after,
        "structural_ok": v["ok"],
        "validator": val,
        "latest_dangling": lat_dangling, "contentdocs_dangling": cd_dangling,
        "pin_evidence": ev,
        "deleted_by_class": deleted_cls.most_common(40),
        "top_survivor_classes": survivors.most_common(40),
        "keep_views": {int(e): str((st["doc"].value(e) or {}).get("m_viewName") or "")
                       for e in _keep_views(st)},
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(out_dir, f"{name}.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    print(f"[{name}] deleted {len(delete):>6,} / kept {res['surviving_elements']:>6,} "
          f"| size {size:>9,} B | structural={v['ok']} validator_ok={val['ok']} "
          f"(errors {val['errors']}) | Latest-dangling {lat_dangling} | {res['seconds']}s")
    return res


# ---------------------------------------------------------------------------
# R9b — remove the EMBEDDED FAMILY DOCUMENTS themselves (save units 1..k of
# Partitions/<N> + their Global/ContentDocuments entries), on top of R9.
#
# A project embeds one complete little family document per loaded family:
# its own save unit inside Partitions/<N> (opened by a 28-byte separator
# whose GUID == the host Family's m_oFamDoc.m_contentDocGUID) and a
# self-framed entry in Global/ContentDocuments keyed by the same GUID
# (12-byte marker + GUID + u32 body_size + ADocument body + u32
# size-repeat; entries tile the payload back-to-back).  R9 already deleted
# the host Family/FamilySymbol/instance elements; the units are dead
# weight kept byte-for-byte.  R9b physically removes them.
# ---------------------------------------------------------------------------

def _unit_ranges(logical: bytes):
    """[(unit_index, guid, start, end)] over a Partitions logical stream.

    Unit k (k>=1) starts at its 28-byte separator; unit 0 starts right
    after the 18-byte stream header.  Each range ends where the next unit's
    separator starts (or at the end record for the last one), so the ranges
    tile the stream and any subset can be spliced out losslessly.
    """
    from rvt.partitions import StreamWalker
    w = StreamWalker(logical, inflate=False, keep_data=False)
    if w.errors:
        raise RuntimeError(f"walker errors: {w.errors[:3]}")
    starts = []
    for u in w.units:
        if u.index == 0:
            starts.append(18)
        else:
            fb = w.blocks[u.first_block]
            starts.append(fb.hdr_offset - len(u.prefix_blob) - 28)
    import uuid as _uuid
    out = []
    for i, u in enumerate(w.units):
        end = starts[i + 1] if i + 1 < len(starts) else w.end_offset
        g = u.guid
        if isinstance(g, (bytes, bytearray)):
            try:
                g = str(_uuid.UUID(bytes_le=bytes(g[:16])))
            except Exception:
                g = bytes(g).hex()
        out.append((u.index, g, starts[i], end))
    return out, w


def remove_units(base_rvt: str, out_path: str, guids_to_remove: set) -> dict:
    """Splice save units (by separator GUID) out of ``base_rvt``'s partition
    stream and drop the same GUIDs' entries from Global/ContentDocuments;
    re-frame both streams with CRCIO ECC and rewrite the container.
    Everything else (incl. Global/Latest, History, ElemTable) is untouched.
    """
    import dataclasses as _dc
    from rvt import ecc
    from rvt.cfb_writer import write_cfb
    from rvt.content import scan_content_documents
    from rvt.partitions import StreamWalker
    from rvt.roundtrip import read_entries
    from rvt.stream_encoders import global_prefix
    from rvt.writer import gzip_member

    want = {str(g).lower() for g in guids_to_remove}
    entries = read_entries(base_rvt)
    new_streams = {}
    rep = {"units_before": None, "units_after": None, "removed_units": [],
           "cd_entries_before": None, "cd_entries_after": None,
           "partition_logical_before": None, "partition_logical_after": None,
           "cd_payload_before": None, "cd_payload_after": None}
    with open_rvt(base_rvt) as f:
        pname = f.partition_streams()[0]
        logical = f.logical(pname)
        ranges, w = _unit_ranges(logical)
        rep["units_before"] = len(ranges)
        rep["partition_logical_before"] = len(logical)
        keep_chunks = [bytes(logical[:18])]
        removed = []
        for idx, guid, s, e in ranges:
            g = str(guid).lower() if guid else None
            if idx != 0 and g in want:
                removed.append({"unit": idx, "guid": g, "bytes": e - s})
                continue
            keep_chunks.append(bytes(logical[s:e]))
        keep_chunks.append(bytes(logical[w.end_offset:]))
        new_logical = b"".join(keep_chunks)
        w2 = StreamWalker(new_logical, inflate=False, keep_data=False)
        if w2.errors:
            raise RuntimeError(f"walker errors after unit removal: {w2.errors[:3]}")
        rep["units_after"] = len(w2.units)
        rep["removed_units"] = removed
        rep["partition_logical_after"] = len(new_logical)
        new_streams[pname] = ecc.frame_stream(new_logical)
        # --- Global/ContentDocuments -----------------------------------------
        payload = f.inflate("Global/ContentDocuments")
        cmap = scan_content_documents(payload)
        rep["cd_entries_before"] = len(cmap.entries)
        rep["cd_payload_before"] = len(payload)
        chunks = []
        last = cmap.entries[-1]
        # the last entry carries the map terminator after its size-repeat;
        # never splice past it — if the last entry is removable keep its
        # trailing terminator bytes (entry_len - (u32_1c + 36)).
        kept_n = 0
        for e in cmap.entries:
            g = str(e.key).lower()
            seg = payload[e.offset:e.offset + e.length]
            if g in want:
                if e is last:
                    body_len = e.u32_1c + 36
                    tail = seg[body_len:]
                    if tail:
                        chunks.append(tail)
                continue
            chunks.append(seg)
            kept_n += 1
        new_payload = payload[:cmap.entries[0].offset] + b"".join(chunks)
        rep["cd_entries_after"] = kept_n
        rep["cd_payload_after"] = len(new_payload)
        cd_logical = global_prefix("Global/ContentDocuments") + gzip_member(new_payload, level=3)
        new_streams["Global/ContentDocuments"] = ecc.frame_stream(cd_logical)
    out_entries = [_dc.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out_path, out_entries)
    return rep


def run_stage_r9b(st: dict, r9_delete: set[int], r9_out: str,
                  out_dir: str = OUT, name: str = "R9b") -> dict:
    """R9b: remove every embedded family document whose host Family died in
    R9 AND none of whose element ids any survivor references (name/base
    parametrised so the same surgery can run on R10 -> R10b)."""
    from rvt import families
    t0 = time.time()
    fams = families.family_documents(st["src"])
    idx = families.FamilyIndex.open(st["src"])
    referrers, cls_of = st["referrers"], st["cls_of"]
    survivors = st["universe"] - r9_delete
    fam_cls = idx.schema.by_name["Family"].type_id
    # -- unit -> guid, guid -> unit ------------------------------------------
    guid_of: dict[int, str] = {}
    for u in idx.units:
        if u.index and u.guid:
            guid_of[u.index] = str(u.guid).lower()
    unit_of_guid = {g: u for u, g in guid_of.items()}
    # -- surviving host families pin their content-doc units ---------------
    host_pins: dict[int, list] = defaultdict(list)         # unit -> host families
    for fam in fams:
        u = fam.get("unit")
        if u is None:
            continue
        host_pins[u].append((fam["family_id"], fam.get("family_name"),
                             fam["family_id"] in r9_delete))
    # -- nested references: a Family element INSIDE unit p naming unit c's guid
    nested_children: dict[int, set[int]] = defaultdict(set)   # parent -> children
    for u in guid_of:
        for eid, r in idx.unit_records(u).get(102, {}).items():
            if r.class_id != fam_cls:
                continue
            v = idx.value(u, eid) or {}
            g = ((v.get("m_oFamDoc") or {}).get("value") or {}).get("m_contentDocGUID")
            c = unit_of_guid.get(str(g).lower()) if g else None
            if c is not None and c != u:
                nested_children[u].add(c)
    # -- id-level check: any survivor referencing an id inside the unit ----
    plan = []
    keep_units: set[int] = set()
    for u, g in guid_of.items():
        recs = idx.unit_records(u)
        uids = set()
        for s in (101, 102, 103):
            uids |= set(recs.get(s, {}).keys())
        outside = {r for i in uids for r in referrers.get(i, ())
                   if r in survivors and r not in uids}
        hosts = host_pins.get(u, [])
        alive_host = any(not dead for (_fid, _n, dead) in hosts)
        if alive_host or outside:
            keep_units.add(u)
        plan.append({"unit": u, "guid": g,
                     "host_families": [(n or "?") + ("" if not dead else " [deleted]")
                                       for (_fid, n, dead) in hosts] or ["<nested/no host>"],
                     "unit_ids": len(uids),
                     "surviving_outside_referrers": Counter(
                         cls_of.get(r, "?") for r in outside).most_common(6),
                     "alive_host": alive_host})
    # nested closure: a kept parent keeps the child documents it references
    front = set(keep_units)
    while front:
        nxt = set()
        for u in front:
            for c in nested_children.get(u, ()):
                if c not in keep_units:
                    keep_units.add(c)
                    nxt.add(c)
        front = nxt
    for p in plan:
        p["removable"] = p["unit"] not in keep_units
    removable = [p for p in plan if p["removable"]]
    guids = {p["guid"] for p in removable}
    out = os.path.join(out_dir, f"{name}.rvt")
    urep = remove_units(r9_out, out, guids)
    v = verify_reduced(out, r9_delete)
    val = _run_validator(out)
    res = {"stage": name, "ladder": "v2",
           "rule": "R9 + delete every embedded family DOCUMENT (partition save "
                   "unit + Global/ContentDocuments entry) whose host Family "
                   "died in R9 and whose ids no survivor references",
           "out": os.path.relpath(out, ROOT), "file_size": os.path.getsize(out),
           "family_docs_total": sum(1 for p in plan),
           "family_docs_removed": len(removable),
           "family_docs_kept": [{"unit": p["unit"], "host_families": p["host_families"],
                                 "alive_host": p["alive_host"],
                                 "pinned_by_ids": p["surviving_outside_referrers"]}
                                for p in plan if not p["removable"]],
           "removed_units": urep["removed_units"],
           "unit_splice": {k: urep[k] for k in ("units_before", "units_after",
                                                 "partition_logical_before",
                                                 "partition_logical_after",
                                                 "cd_entries_before", "cd_entries_after",
                                                 "cd_payload_before", "cd_payload_after")},
           "structural_ok": v["ok"],
           "structural_notes": {"units": v.get("units"), "walker_errors": v["walker_errors"][:5]},
           "validator": val,
           "seconds": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, f"{name}.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    print(f"[{name}] units {urep['units_before']} -> {urep['units_after']} "
          f"({len(removable)} family docs removed) | CD entries "
          f"{urep['cd_entries_before']} -> {urep['cd_entries_after']} | size "
          f"{res['file_size']:,} B | structural={v['ok']} validator_ok={val['ok']} "
          f"(errors {val['errors']})")
    return res


def run_ladder_v2(stages: Sequence[str] = ("R5", "R6", "R7", "R8", "R9", "R10"),
                  safe_variants: bool = True, naive_probes: Sequence[str] = (),
                  unit_removal: bool = True) -> list:
    st = build_state_v2(SRC)
    os.makedirs(OUT, exist_ok=True)
    results = []
    deletes: dict[str, set[int]] = {}
    for s in stages:
        r = run_stage_v2(s, st, safe=False)
        results.append(r)
        if s in ("R9", "R10"):
            d, _k, _e = maxgc(st, _protect_history(st, stage_seed_v2(s, st)))
            deletes[s] = d
        if safe_variants:
            results.append(run_stage_v2(s, st, safe=True))
    if unit_removal:
        for s in ("R9", "R10"):
            if s in deletes:
                results.append(run_stage_r9b(st, deletes[s], os.path.join(OUT, f"{s}.rvt"),
                                             name=f"{s}b"))
    for s in naive_probes:
        results.append(run_stage_v2(s, st, safe=False, naive=True))
    with open(os.path.join(OUT, "summary_v2.json"), "w") as fh:
        json.dump(results, fh, indent=1, default=str)
    lines = ["# GENESIS reduction ladder v2 (R5..R10b) — every stage validator-clean", "",
             "| stage | deleted | kept | size (B) | structural | validator errors | Latest-dangling |",
             "|---|---:|---:|---:|:--:|---:|---:|"]
    for r in results:
        lines.append(f"| {r['stage']} | {r.get('deleted', ''):{',' if 'deleted' in r else ''}} | "
                     f"{r.get('surviving_elements', ''):{',' if 'surviving_elements' in r else ''}} | "
                     f"{r['file_size']:,} | {r['structural_ok']} | {r['validator']['errors']} | "
                     f"{r.get('latest_dangling', '')} |")
    with open(os.path.join(OUT, "summary_v2.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default=None,
                    help="R1/R2/R3/R4 (default: all), optionally suffixed 's' for the safe sweep")
    ap.add_argument("--no-safe", action="store_true", help="skip the R<n>s safe variants")
    ap.add_argument("--ladder", default="v1", choices=["v1", "v2"],
                    help="v2 = the R5..R9 validator-clean GC ladder")
    ap.add_argument("--naive", default="",
                    help="ladder v2: comma list of stages to ALSO emit as R<n>naive "
                         "(delete the whole seed; the validation-boundary probe)")
    args = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    if args.ladder == "v2":
        stages = ["R5", "R6", "R7", "R8", "R9", "R10"]
        if args.stage:
            stages = [args.stage.rstrip("s")]
        naive = [s.strip() for s in args.naive.split(",") if s.strip()]
        run_ladder_v2(stages, safe_variants=not args.no_safe, naive_probes=naive)
        return 0
    st = build_state(SRC)
    stages = ["R1", "R2", "R3", "R4"]
    if args.stage:
        base = args.stage.rstrip("s")
        stages = [base]
    results = []
    for s in stages:
        want_safe_only = bool(args.stage and args.stage.endswith("s"))
        if not want_safe_only:
            results.append(run_stage(s, st, safe=False))
        if not args.no_safe:
            results.append(run_stage(s, st, safe=True))
    with open(os.path.join(OUT, "summary.json"), "w") as fh:
        json.dump(results, fh, indent=1)
    print("\nstage      deleted   kept       size  ok    latest_dangling")
    for r in results:
        lat = r["dangling"]["external"].get("Global/Latest", {}).get("dangling")
        print(f"{r['stage']:<8} {r['deleted']:>8} {r['surviving_elements']:>6} "
              f"{r['file_size']:>10,} {str(r['structural_ok']):>5} {lat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
