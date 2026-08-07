#!/usr/bin/env python3
"""render_probes.py -- INSTANCE-RENDER probes + THE ROOM'S FAMILY-LAYER
BISECTION on the certified genesis base (workstream: render-instances).

Two questions this stream owns (docs/inbox/render-instances.md):

(A) LOAD IS NOT RENDER.  Every acceptance to date is a LOAD (translation)
    pass; visibility was never a gate.  The walls-only files translate but
    their model tree holds only the level node (walls = SerializedDummy rep,
    the cloud extractor does not regenerate).  Our generated .rfa families DO
    carry baked six-face solids (rvt.famgen.geometry, byte-exact).  So: does
    a PLACED INSTANCE of OUR family produce viewable geometry?  ->  the
    R_inst_* probes = the certified base + ONE loaded family + ONE placed
    instance, NO walls (the instance is both the render subject and the
    element that forces Revit's document-corruption audit to actually run):

      R_inst_box       -- a MINIMAL family: one bare famgen solid box (no
                          connector, no tagging-contract parameters) -- the
                          purest "does an instance of our family render" test
      R_inst_panel     -- the room's PRL1X panelboard (LP-4) + one instance
      R_inst_downlight -- the IFC-derived downlight (experiments/families/ifc)
                          + one instance

(B) THE ROOM'S FAMILY LAYER, BISECTED.  Measured this session (build_record +
    the four files' bytes -- see docs/inbox/render-instances.md):
      * stage_L8_lp4  = ZA_deep + ALL 8 room families, NO walls, NO
        instances -- viewer verdict "Design is empty" (recorded PASS).  A
        symbol-only file gives the extractor nothing to regenerate; it is
        NOT an audited pass of the family layer.
      * walls_only    = ZA_deep + 4 walls -- PASS under a REAL audit (walls
        are model elements; the tree shows the level node).
      * stage_W_loaded_walls = the two together -- FAIL (audit -1073742517).
        Byte-diff vs stage_L8: exactly the 4 wall records (identical, modulo
        id, to walls_only's) + 4 ElemTable rows + BasicFileInfo identity;
        the 8 embedded family units and every existing record are UNCHANGED.
      => the loaded family layer has NEVER survived a real audit on the
         genesis base; the walls merely forced one.  There is no evidence
         yet that "one family is defective" -- nor that any is exonerated.
    ->  the F_<family> probes = ZA_deep + ONE family loaded + the room's 4
        walls (the audit-forcing agent, proven audit-clean on their own):
        one file per family.  Reading them together with the R_inst probes
        separates {a defective single family} from {any-family / loader-
        on-genesis defect} from {wall x loaded-family interaction}.

Every emitted .rvt: certified validator 0 errors; probes.json declares the
CERTIFIED base ZA_deep + a byte-identical control; the gate check runs.
PROOF-ONLY research artefacts (the base is the sample-derived genesis
lineage; our added layer -- families, walls, instances -- is ours).

TERRITORY: tools/render_probes.py, experiments/ifc_room/render_probes/**,
docs/inbox/render-instances.md.  IMPORTS (never edits) rvt.famgen /
rvt.famload / rvt.mutate / rvt.commit / rvt.validate / rvt.ifc and the
sibling tool tools/ifc_intent.py (its certified stage machinery: SpecimenSet,
stage_walls, the instance scrub / frame helpers).  No browser: the outputs
sit on disk for the orchestrator's viewer gate, and probes.json says what
each rendered model tree should contain.

    python tools/render_probes.py                  # everything (~40 s)
    python tools/render_probes.py --only forensics # the reproducible premise refutation
    python tools/render_probes.py --only assay     # the static per-family assay
    python tools/render_probes.py --only rinst     # the render probes
    python tools/render_probes.py --only fset      # the F_ family bisection set
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import shutil
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for _p in (SRC, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ifc_intent as T                      # noqa: E402  (sibling tool: imported, never edited)
from rvt.ifc import intent as I             # noqa: E402

FT_PER_M = 3.280839895013123

# --- the certified base + specimen source (identical to the ifc-room stream)
BASE = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a", "ZA_deep.rvt")
SPECIMEN_SRC = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")
IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
ROOM_DIR = os.path.join(ROOT, "experiments", "ifc_room")
FAMILY_DIR = os.path.join(ROOM_DIR, "families")
OUT_DIR = os.path.join(ROOM_DIR, "render_probes")
DOWNLIGHT_RFA = os.path.join(ROOT, "experiments", "families", "ifc",
                             "chicago_plenum_downlight.rfa")

#: OST built-ins
OST_ELECTRICAL_EQUIPMENT = -2001040
OST_LIGHTING_FIXTURES = -2001120

#: the room's family set, in the tag order the pipeline built them
ROOM_TAGS = ["MSB", "DP-1", "DP-2", "LP-1", "LP-2", "LP-3", "T1", "LP-4"]


# ===========================================================================
# small helpers
# ===========================================================================

def _relp(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return r if not r.startswith("..") else p
    except ValueError:
        return p


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _log(msg: str) -> None:
    print(f"[render_probes] {msg}", flush=True)


def _jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def _tag_slug(tag: str) -> str:
    return tag.lower().replace("-", "")


# ===========================================================================
# families: the room's set (rebuilt EXACTLY as the ifc-room pipeline did) +
# the two render-only families (bare box, IFC downlight)
# ===========================================================================

def resolve_intent() -> Any:
    """The room's resolved intent (positions / mapping / walls / feeders)."""
    return I.resolve_intent(IFC)


def build_room_product(model, tag: str, start_id: int):
    """Rebuild one of the room's mapped families at ``start_id`` -- the SAME
    constructor + kwargs the ifc-room stage_load used (T.build_product), so
    the F_<tag> family layer is content-identical to the room's."""
    plan = model.plan_for(tag)
    if plan is None or plan.status not in ("resolved", "house"):
        raise KeyError(f"no buildable plan for {tag}")
    return plan, T.build_product(plan, start_id=start_id, solid=True)


def make_bare_box_product(*, start_id: int = 1000, name: str = "Render Probe Box",
                          width_ft: float = 2.0, depth_ft: float = 2.0,
                          height_ft: float = 3.0):
    """The MINIMAL render family: an Electrical-Equipment document (the SAME
    category / part-type shape and scaffolding the room's boards use -- no new
    category variable) carrying exactly ONE bare famgen solid BOX form, three
    dimension parameters, one type row -- and NO connector, NO tagging-
    contract parameters, NO identity built-ins.  The purest 'does a placed
    instance of our family produce viewable geometry' subject."""
    from rvt.famgen import factory as F
    from rvt.famgen import skeleton as SK
    from rvt.famgen import geometry as G

    facts = F.FactSheet(subject=f"render probe box {width_ft:g}x{depth_ft:g}x{height_ft:g} ft",
                        catalog="none (render probe, no product)", variant="render-box")
    facts.set("width_ft", float(width_ft), kind="given", note="render probe geometry, not a product")
    facts.set("depth_ft", float(depth_ft), kind="given")
    facts.set("height_ft", float(height_ft), kind="given")
    facts.notes.append("RENDER PROBE: a bare solid box, no manufacturer / catalog / connector "
                       "content -- the purest instance-render subject.")

    doc = SK.new_family_document("electrical_equipment", name,
                                 part_type=SK.PART_TYPE["normal"],
                                 work_plane_based=False, start_id=int(start_id),
                                 plane_length_ft=max(6.0, height_ft * 1.5))
    doc.notes.append("render probe: floor-standing box on the Reference Level, no connector, "
                     "no tagging contract -- solid geometry only")
    pW = doc.add_family_parameter("Width", F.SPEC["length"], F.GROUP["dimensions"])
    pD = doc.add_family_parameter("Depth", F.SPEC["length"], F.GROUP["dimensions"])
    pH = doc.add_family_parameter("Height", F.SPEC["length"], F.GROUP["dimensions"])
    doc.add_type("standard", {pW.elem_id: float(width_ft), pD.elem_id: float(depth_ft),
                              pH.elem_id: float(height_ft),
                              "description": (f"render probe: bare {width_ft:g} x {depth_ft:g} x "
                                              f"{height_ft:g} ft solid box, no connector")})
    fb = F.add_box_form(doc, float(width_ft), float(depth_ft), float(height_ft),
                        base_z_ft=0.0, center=(0.0, 0.0), rep=G.REP_SOLID)
    fb.params.update({"role": "render probe solid box (baked six-face B-rep)",
                      "dims_ft": [width_ft, depth_ft, height_ft]})
    doc.finalize()
    prod = F.FamilyProduct("box", doc, facts, forms=[fb], file_stem="render_probe_box")
    prod.notes.append("render probe: one baked solid box, no connector, no contract "
                      "parameters -- the minimal instance-render subject")
    return prod


# ===========================================================================
# loading (each family through the loader IT is proven with)
# ===========================================================================

def load_room_family(host_rvt: str, out_rvt: str, product) -> Any:
    """The room's mechanism: rvt.famgen.loader.load_family_into_project,
    place=False (the stage_L8 loader).  Returns the LoadResult."""
    from rvt.famgen import loader as L
    return L.load_family_into_project(host_rvt, out_rvt, product=product, place=False,
                                      symbol_solid=True,
                                      report_path=out_rvt + ".load.json", validate=False)


def load_downlight(host_rvt: str, out_rvt: str) -> Dict[str, Any]:
    """The downlight's mechanism: rvt.ifc.famfrom_ifc.load_into_project
    (rvt.famload four-registry loader = the certified L1a / L_downlight
    path), place=False.  Returns a dict {ok, symbol_id, family_id, ...}."""
    from rvt.ifc import famfrom_ifc as FI
    rep = FI.load_into_project(host_rvt, out_rvt,
                               report_path=out_rvt + ".load.json",
                               core_categories=(OST_LIGHTING_FIXTURES,))
    out: Dict[str, Any] = {"ok": bool(rep.ok), "stop_reason": getattr(rep, "stop_reason", ""),
                           "error": getattr(rep, "error", None),
                           "loader": getattr(rep, "loader", None), "plans": rep.plans}
    if rep.plans:
        p0 = rep.plans[0]
        # famload's LoadPlan.as_json is dataclasses.asdict: symbol_ids is a
        # list (one per type); symbol_id is a property, not a field
        syms = p0.get("symbol_ids") or []
        out["symbol_id"] = (p0.get("symbol_id") or (syms[0] if syms else None)
                            or p0.get("host_symbol_id"))
        out["family_id"] = p0.get("host_family_id") or p0.get("family_id")
        out["guid"] = p0.get("guid")
        out["core_ids"] = p0.get("core_ids")
    out["validate_project_mode"] = getattr(rep, "validate_project_mode", None)
    return out


# ===========================================================================
# instance placement -- the room's stage-E mechanics, for ONE instance with an
# explicit position / frame / category (no walls)
# ===========================================================================

def _yaw_frame(yaw_deg: float) -> List[List[float]]:
    a = math.radians(float(yaw_deg))
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def place_one_instance(src_rvt: str, out_rvt: str, *, specimens, symbol_id: int,
                       family_id: Optional[int], product,
                       position_m: Sequence[float], frame3x3: List[List[float]],
                       category: int, tag: str, connector_manager: bool
                       ) -> Dict[str, Any]:
    """Place ONE free-standing instance of our loaded symbol into ``src_rvt``
    -> ``out_rvt``, by the ifc-room stage-E recipe: R5 specimen scaffolding
    injected, ``Document.add_family_instance`` (symbol == masterSymbol,
    host -1, on the ground level), the explicit orientation frame written
    into ``m_Trf``, the cross-category specimen residue scrubbed (header
    category -> ``category``), then ``commit_new_elements`` + read-back.

    ``connector_manager``: True = the loader's connector-slot manager for
    the product (the room's pattern); False = no connector manager at all
    (the bare box has no connectors -- an equipment instance may carry an
    empty manager, but the purest render subject carries none).
    """
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements, verify_written
    rec: Dict[str, Any] = {"tag": tag, "in": _relp(src_rvt), "out": _relp(out_rvt),
                           "ok": False}
    t0 = time.time()
    doc = Document.from_file(src_rvt)
    rec["specimens"] = specimens.inject_into(doc)
    lvl = T._pick_level(doc, 0.0)
    rec["level"] = lvl
    tpl = specimens.instance_id
    if tpl is None:
        rec["blocker"] = ("no free-standing FamilyInstance specimen (family-free base + "
                          "no ancestor instance): rvt.mutate.add_family_instance clones the "
                          "placement scaffolding")
        return rec
    pos_ft = tuple(float(c) * FT_PER_M for c in position_m)
    yaw = math.atan2(float(frame3x3[1][0]), float(frame3x3[0][0])) if frame3x3 else 0.0
    el = doc.add_family_instance(int(symbol_id), lvl, position=pos_ft,
                                 rotation=float(yaw), template_instance_id=tpl)
    T._apply_frame(el, frame3x3, pos_ft)
    if connector_manager and product is not None:
        el.obj["m_pConnectorManager"] = T._connector_manager_for(product, 0)
    else:
        el.obj["m_pConnectorManager"] = None
    scrub = T._scrub_instance(el, doc, our_symbol=int(symbol_id), our_family=family_id,
                              spec_symbol=specimens.instance_symbol,
                              spec_category=specimens.instance_category,
                              category=int(category))
    dangling = doc.check_references(el)
    recs = doc.serialize(el)
    if recs is None:
        raise RuntimeError("rvt.encode not available: cannot serialize the instance")
    crep = commit_new_elements(src_rvt, out_rvt, [dict(recs)], [el.elemrec])
    ver = verify_written(out_rvt, [el.elemrec.elem_id])
    rec.update(T._commit_summary(crep, ver, [el.elemrec.elem_id]))
    rec.update({
        "elem_id": el.elem_id, "symbol": int(symbol_id), "family": family_id,
        "category": int(category), "position_m": [round(float(c), 4) for c in position_m],
        "position_ft": [round(c, 3) for c in pos_ft],
        "yaw_deg": round(math.degrees(yaw), 2), "frame3x3": frame3x3,
        "connector_manager": bool(connector_manager and product is not None),
        "scrub": scrub, "dangling_refs": dangling[:16], "n_dangling": len(dangling),
        "notes": el.notes,
    })
    rec["ok"] = bool(rec.get("structurally_valid"))
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


# ===========================================================================
# the gates every emitted .rvt passes
# ===========================================================================

def validate_rvt(path: str) -> Dict[str, Any]:
    return T.validate_rvt(path)


def census(path: str) -> Dict[str, Any]:
    return T.registry_census(path)


def identity(path: str) -> Dict[str, Any]:
    return T.identity_gate(path)


def content_census(path: str) -> Dict[str, Any]:
    """Element-layer census of a project file: walls / instances / families
    / symbols in the host document (unit 0) + embedded family documents,
    plus (for instance-bearing files) the RENDER-RELEVANT representations:
    the seq-103 rep class of each FamilySymbol / FamilyInstance (baked
    ``GElement`` = geometry the extractor can draw without regenerating,
    vs ``SerializedDummy`` = relies on Revit regeneration) and the number
    of baked solids in the embedded family document."""
    from rvt.families import FamilyIndex
    from rvt.famload import four_registry_census
    out: Dict[str, Any] = {}
    try:
        fi = FamilyIndex(path)
        hist = fi.class_histogram(0)
        out["host_records"] = int(sum(hist.values()))
        for cls in ("SWall", "FamilyInstance", "Family", "FamilySymbol", "SketchPlane"):
            out[cls] = int(hist.get(cls, 0))
        c = four_registry_census(path)
        out["family_documents"] = int(c.get("contentdocs_entries") or 0)
        out["save_units"] = int(c.get("save_units") or 0)
        out["four_registry_coherent"] = bool(c.get("coherent"))
        # render-relevant reps (only when instances / symbols are present)
        if hist.get("FamilyInstance") or hist.get("FamilySymbol"):
            reps = render_reps(path)
            if reps:
                out["render_reps"] = reps
    except Exception as e:                                   # honest capture
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def render_reps(path: str) -> Dict[str, Any]:
    """The seq-103 representation classes of the FamilySymbol(s) and
    FamilyInstance(s) in the host document, plus the embedded family
    document's baked-solid (``ExtrusionElem`` GElement) count.  A symbol
    whose rep is a real ``GElement`` (with ``m_pGeomTable``) carries BAKED
    symbol geometry (the rvt.famgen loader authors it from our solid); a
    ``SerializedDummy`` symbol relies on Revit REGENERATION (the rvt.famload
    loader) -- the LOAD-IS-NOT-RENDER hinge."""
    from rvt.mutate import Document
    from rvt.families import FamilyIndex
    reps: Dict[str, Any] = {"symbols": {}, "instances": {}}
    doc = Document.from_file(path)
    for sid in doc.ids_of_class("FamilySymbol"):
        r = doc.record(sid, 103)                             # the graphics REP
        d = doc.decode(sid, 103) if r is not None else None
        cls = (getattr(d, "class_name", None) or (type(d).__name__ if d else None))
        v = getattr(d, "value", None) or {}
        obj = doc.value(sid) or {}                           # the seq-102 symbol OBJECT
        reps["symbols"][int(sid)] = {
            "rep_class": cls, "rep_body_bytes": (r.body_size if r else None),
            "rep_subnodes": (len(v.get("m_subNodes") or []) if isinstance(v, dict) else None),
            # the geometry-history tables the famgen loader authors live on the
            # symbol OBJECT (seq 102): m_pGeomTable + m_geomSteps
            "object_has_geom_table": bool(obj.get("m_pGeomTable")),
            "object_has_geom_steps": bool(obj.get("m_geomSteps")),
        }
    for iid in doc.ids_of_class("FamilyInstance"):
        r = doc.record(iid, 103)
        d = doc.decode(iid, 103) if r is not None else None
        reps["instances"][int(iid)] = {
            "rep_class": (getattr(d, "class_name", None) or (type(d).__name__ if d else None)),
            "rep_body_bytes": (r.body_size if r else None),
        }
    try:                                                    # unit 1 = the (single) embedded doc
        fi = FamilyIndex(path)
        h1 = fi.class_histogram(1)
        reps["embedded_doc_solids"] = int(h1.get("ExtrusionElem", 0))
        reps["embedded_doc_records"] = int(sum(h1.values()))
    except Exception:                                       # no embedded unit -> omit
        pass
    # one-line reading
    sym_classes = {s.get("rep_class") for s in reps["symbols"].values()}
    if sym_classes == {"GElement"}:
        reps["symbol_geometry"] = ("BAKED (GElement symbol rep with geom table -- the "
                                   "rvt.famgen loader authors it from our solid): the "
                                   "extractor can draw it WITHOUT regenerating")
    elif sym_classes == {"SerializedDummy"}:
        reps["symbol_geometry"] = ("DUMMY (SerializedDummy symbol rep -- the rvt.famload "
                                   "loader): symbol graphics exist only if Revit REGENERATES "
                                   "from the family document's solids")
    else:
        reps["symbol_geometry"] = f"mixed: {sorted(str(x) for x in sym_classes)}"
    return reps


# ===========================================================================
# (A) the R_inst render probes
# ===========================================================================

def build_rinst_probes(model, specimens, out_dir: str) -> List[Dict[str, Any]]:
    """R_inst_box / R_inst_panel / R_inst_downlight, each = ZA_deep + one
    loaded family + one placed instance, NO walls."""
    reports: List[Dict[str, Any]] = []
    scr = os.path.join(out_dir, "_build")
    os.makedirs(scr, exist_ok=True)
    wm = T.host_watermark(BASE)

    # ---- R_inst_box ------------------------------------------------------
    rec: Dict[str, Any] = {"probe": "R_inst_box", "kind": "probe", "base": _relp(BASE)}
    try:
        # the STANDALONE .rfa is built at start_id 1000 (the family-file
        # convention every stream's .rfa follows -- and REQUIRED here: the v2
        # emitter's donor-id guard is an UNALIGNED i64 byte scan, and project-
        # scale ids (watermark+1 = 0x16780D...) contain byte windows such as
        # 78 16 00 00 00 00 that read unaligned as small "donor" ids (5752
        # = 0x1678) -> a guard false-positive; see the record).  The LOADED
        # document is rebuilt at the host watermark, as the room's stage L does.
        rfa = os.path.join(out_dir, "families", "render_probe_box.rfa")
        os.makedirs(os.path.dirname(rfa), exist_ok=True)
        rec["family_rfa"] = _relp(rfa)
        rec["family_rfa_report"] = _emit_clean_rfa(make_bare_box_product(start_id=1000), rfa)
        prod = make_bare_box_product(start_id=wm + 1)
        loaded = os.path.join(scr, "box_loaded.rvt")
        res = load_room_family(BASE, loaded, prod)
        rec["load"] = {"ok": bool(res.ok), "stop_reason": res.stop_reason,
                       "loader": "rvt.famgen.loader.load_family_into_project(place=False)",
                       "symbol_id": res.plan.symbol_id if res.plan else None,
                       "family_id": res.plan.host_family_id if res.plan else None,
                       "content_guid": res.plan.guid if res.plan else None,
                       "core_ids": (list(getattr(res.plan, "core_ids", []) or [])
                                    if res.plan else None)}
        if not res.ok:
            raise RuntimeError(f"box load failed: {res.stop_reason}")
        out = os.path.join(out_dir, "R_inst_box.rvt")
        inst = place_one_instance(
            loaded, out, specimens=specimens,
            symbol_id=res.plan.symbol_id, family_id=res.plan.host_family_id, product=None,
            position_m=(2.0, -2.0, 0.0), frame3x3=_yaw_frame(0.0),
            category=OST_ELECTRICAL_EQUIPMENT, tag="BOX", connector_manager=False)
        rec["instance"] = inst
        rec["file"] = _relp(out)
        rec["family"] = {"name": prod.name, "kind": "bare solid box (render probe)",
                         "forms": [f.params for f in prod.forms],
                         "connectors": len(prod.doc.connectors),
                         "parameters": sorted(prod.doc.params),
                         "elements": len(prod.doc.elements)}
        rec["expected_tree"] = _expected_tree("Electrical Equipment", prod.name, "standard",
                                               position_m=(2.0, -2.0, 0.0),
                                               body="one 2 x 2 x 3 ft solid box standing on the floor "
                                                    "near (2 m, -2 m)")
        rec["ok"] = bool(inst.get("ok"))
    except Exception as e:
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc(limit=8)
    reports.append(rec)
    _log(f"R_inst_box: ok={rec['ok']} -> {rec.get('file') or rec.get('error')}")

    # ---- R_inst_panel (the room's PRL1X = LP-4) --------------------------
    rec = {"probe": "R_inst_panel", "kind": "probe", "base": _relp(BASE)}
    try:
        plan, prod = build_room_product(model, "LP-4", wm + 1)
        loaded = os.path.join(scr, "panel_loaded.rvt")
        res = load_room_family(BASE, loaded, prod)
        rec["load"] = {"ok": bool(res.ok), "stop_reason": res.stop_reason,
                       "loader": "rvt.famgen.loader.load_family_into_project(place=False)",
                       "symbol_id": res.plan.symbol_id if res.plan else None,
                       "family_id": res.plan.host_family_id if res.plan else None,
                       "content_guid": res.plan.guid if res.plan else None,
                       "core_ids": (list(getattr(res.plan, "core_ids", []) or [])
                                    if res.plan else None)}
        if not res.ok:
            raise RuntimeError(f"panel load failed: {res.stop_reason}")
        eq = next((e for e in model.equipment if e.tag == "LP-4"), None)
        if eq is None:
            raise KeyError("LP-4 not in the intent's equipment")
        out = os.path.join(out_dir, "R_inst_panel.rvt")
        # free-standing at LP-4's intent insertion point + upright frame (the
        # room's exact placement of LP-4, minus the walls it would sit on)
        inst = place_one_instance(
            loaded, out, specimens=specimens,
            symbol_id=res.plan.symbol_id, family_id=res.plan.host_family_id, product=prod,
            position_m=tuple(eq.insertion_m), frame3x3=[list(map(float, r)) for r in eq.frame3x3],
            category=OST_ELECTRICAL_EQUIPMENT, tag="LP-4", connector_manager=True)
        rec["instance"] = inst
        rec["file"] = _relp(out)
        rec["family"] = {"name": prod.name, "kind": "PRL1X receptacle panelboard (LP-4)",
                         "constructor": plan.constructor, "kwargs": plan.kwargs,
                         "connectors": len(prod.doc.connectors),
                         "parameters": len(prod.doc.params), "elements": len(prod.doc.elements)}
        rec["expected_tree"] = _expected_tree("Electrical Equipment", prod.name,
                                               f"{int(plan.kwargs.get('mains_a', 225))}A MB "
                                               f"{int(plan.kwargs.get('spaces', 42))}ckt",
                                               position_m=tuple(eq.insertion_m),
                                               body="the PRL1X enclosure box (20 x 48 in face, "
                                                    "~5.75 in deep) standing UPRIGHT at LP-4's "
                                                    "east-wall spot (4.455, -0.55, 1.543) m -- no "
                                                    "wall present, the box floats where the wall "
                                                    "would be")
        rec["placement_note"] = ("identical to the room's LP-4 placement (intent frame, "
                                 "upright 3x3) but with NO walls in the file")
        rec["ok"] = bool(inst.get("ok"))
    except Exception as e:
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc(limit=8)
    reports.append(rec)
    _log(f"R_inst_panel: ok={rec['ok']} -> {rec.get('file') or rec.get('error')}")

    # ---- R_inst_downlight (the IFC-derived family) -----------------------
    rec = {"probe": "R_inst_downlight", "kind": "probe", "base": _relp(BASE)}
    try:
        loaded = os.path.join(scr, "downlight_loaded.rvt")
        ld = load_downlight(BASE, loaded)
        rec["load"] = {k: ld.get(k) for k in ("ok", "stop_reason", "error", "loader",
                                              "symbol_id", "family_id", "guid", "core_ids",
                                              "validate_project_mode")}
        if not ld.get("ok") or not ld.get("symbol_id"):
            raise RuntimeError(f"downlight load failed: {ld.get('stop_reason') or ld.get('error')}")
        out = os.path.join(out_dir, "R_inst_downlight.rvt")
        # a fixture floating at ceiling height, level frame (its housing rises
        # above the trim / ceiling plane at z 0 of the family)
        inst = place_one_instance(
            loaded, out, specimens=specimens,
            symbol_id=int(ld["symbol_id"]), family_id=ld.get("family_id"), product=None,
            position_m=(0.0, -2.0, 2.4), frame3x3=_yaw_frame(0.0),
            category=OST_LIGHTING_FIXTURES, tag="DOWNLIGHT", connector_manager=False)
        rec["instance"] = inst
        rec["file"] = _relp(out)
        rec["family"] = {"name": "Chicago-plenum recessed downlight (IFC-derived)",
                         "source_rfa": _relp(DOWNLIGHT_RFA),
                         "loader": "rvt.famload.load_family_document (its certified path)"}
        rec["expected_tree"] = _expected_tree("Lighting Fixtures",
                                               "Chicago plenum recessed downlight (CP-6-LED)",
                                               "CP-6-LED", position_m=(0.0, -2.0, 2.4),
                                               body="the downlight assembly (can, trim disc, frame "
                                                    "plate, J-box, driver box, bar hangers -- 8 "
                                                    "solids, ~2.2 ft across) floating at ceiling "
                                                    "height (2.4 m) near the origin")
        rec["ok"] = bool(inst.get("ok"))
    except Exception as e:
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc(limit=8)
    reports.append(rec)
    _log(f"R_inst_downlight: ok={rec['ok']} -> {rec.get('file') or rec.get('error')}")

    # ---- the wall-hosted variant: FEASIBILITY (recorded, not faked) -----
    reports.append(_wallhost_feasibility())
    return reports


def _emit_clean_rfa(product, path: str) -> Dict[str, Any]:
    """Emit ``product`` as a standalone .rfa through the ASSAY-CLEAN family
    path (rvt.famgen.famdoc_adoc.emit_family_rfa_v2 = our family ADocument,
    our footer, the 10-byte end constant), then the certified family-mode
    validator + the byte-level provenance ledger.  (The room's stage-F used
    the old FamilyProduct.write -> donor-graft emitter -- see the assay
    section of the record; the render family goes the clean path.)"""
    from rvt.famgen import famdoc_adoc as FA
    rep: Dict[str, Any] = {"path": _relp(path)}
    try:
        emit = FA.emit_family_rfa_v2(product.doc, path, mode="candidate",
                                     footer_mode="nonce", write_reports=False)
        rep["emitted"] = True
        rep["adocument"] = {k: (emit.get("adocument") or {}).get(k)
                            for k in ("conclusion", "registries", "residual")}
        val = FA.validate_family_file(path)
        rep["validate"] = {"family_mode": val.get("family_mode"),
                           "ok": bool(val.get("ok")), "gate_note": val.get("gate_note")}
        prov = FA.provenance_scan_v2(path, our_ids={int(e.elem_id)
                                                     for e in product.doc.elements})
        rep["provenance"] = {"ok": bool(prov.get("ok")),
                             "checks": prov.get("checks"),
                             "failed": prov.get("failed_checks") or prov.get("failed")}
        rep["ok"] = bool(rep["validate"]["ok"] and rep["provenance"]["ok"])
    except Exception as e:                                   # pragma: no cover
        rep["ok"] = False
        rep["error"] = f"{type(e).__name__}: {e}"
        rep["traceback"] = traceback.format_exc(limit=6)
    return rep


def _expected_tree(category: str, family: str, ftype: str, *, position_m, body: str) -> Dict[str, Any]:
    """What the viewer's MODEL TREE should show for a rendered instance."""
    return {
        "if_RENDER": (f"model tree: level node 'L1 - Ground Floor [311]' -> a CATEGORY node "
                      f"'{category}' -> family '{family}' -> type '{ftype}' -> ONE instance "
                      f"node with an eye toggle; the 3D view shows {body} "
                      f"(position {tuple(round(float(c), 3) for c in position_m)} m)"),
        "if_LOAD_but_no_render": ("the file translates but the tree still holds ONLY the level "
                                  "node ('Design is empty' or datum-only) -> the instance's "
                                  "symbol graphics were NOT drawn: the family document's baked "
                                  "solid does not survive to the extractor, or the FamilySymbol "
                                  "geometry (SerializedDummy) is not regenerated by the viewer"),
        "if_FAIL": ("PROCESSING FAILED with Revit-DocumentCorruption (-1073742517) -> the "
                    "loaded-family layer (or the instance) fails the audit on the genesis "
                    "base; read together with the F_ set (walls as the audit-forcer)"),
    }


def _wallhost_feasibility() -> Dict[str, Any]:
    """The wall-face-HOSTED variant the charter asks about.  On the family-
    free genesis base a face-SketchPlane specimen is required by
    rvt.hosting; and any wall-hosted file is walls + a loaded family = the
    exact combination that FAILS today.  Recorded, not faked."""
    rec: Dict[str, Any] = {"probe": "R_inst_panel_wallhost", "kind": "not_built"}
    try:
        from rvt.mutate import Document
        from rvt import hosting as H
        doc = Document.from_file(BASE)
        try:
            tpl = H.find_face_sketchplane_template(doc)
            rec["face_sketchplane_template_in_base"] = tpl
        except Exception as e:
            rec["face_sketchplane_template_in_base"] = None
            rec["template_lookup"] = f"{type(e).__name__}: {e}"
    except Exception as e:                                   # pragma: no cover
        rec["template_lookup"] = f"{type(e).__name__}: {e}"
    rec["reason_not_built"] = (
        "A wall-hosted instance needs (1) walls in the file and (2) a face-SketchPlane specimen "
        "for rvt.hosting.add_sketchplane_on_wall / host_instance_on_wall (certified H1/H2 on "
        "the MEP sample).  On the family-free genesis base ZA_deep there are no walls and no "
        "face-SketchPlane specimen, so hosting would clone R5 templates AND require the wall "
        "stage.  Crucially, walls + a loaded family is the very combination this stream shows "
        "FAILING (stage_W_loaded_walls) -- a wall-hosted render probe would read on TWO "
        "confounded variables (the hosting AND the failing interaction) until the interaction is "
        "understood.  The free-standing R_inst probes are therefore PRIMARY; the wall-hosted "
        "question is deferred behind the F_-set bisection (and behind emitting baked wall "
        "geometry, since an instance hosted to an UN-RENDERED wall has nothing to sit on visually).")
    return rec


# ===========================================================================
# (B) the F_ per-family bisection set
# ===========================================================================

def build_family_bisection(model, specimens, out_dir: str,
                           tags: Sequence[str] = ROOM_TAGS) -> List[Dict[str, Any]]:
    """F_<tag>.rvt = ZA_deep + ONE room family loaded + the room's 4 walls
    (mode 'min' -- the exact wall layer of the certified walls_only, which
    PASSED).  The walls force the document-corruption audit that stage_L8
    ('Design is empty') never ran; each file exercises ONE family under it."""
    reports: List[Dict[str, Any]] = []
    scr = os.path.join(out_dir, "_build")
    os.makedirs(scr, exist_ok=True)
    wm = T.host_watermark(BASE)
    for tag in tags:
        slug = _tag_slug(tag)
        rec: Dict[str, Any] = {"probe": f"F_{slug}", "kind": "probe", "tag": tag,
                               "base": _relp(BASE)}
        t0 = time.time()
        try:
            plan, prod = build_room_product(model, tag, wm + 1)
            loaded = os.path.join(scr, f"{slug}_loaded.rvt")
            res = load_room_family(BASE, loaded, prod)
            rec["load"] = {"ok": bool(res.ok), "stop_reason": res.stop_reason,
                           "symbol_id": res.plan.symbol_id if res.plan else None,
                           "family_id": res.plan.host_family_id if res.plan else None,
                           "content_guid": res.plan.guid if res.plan else None,
                       "core_ids": (list(getattr(res.plan, "core_ids", []) or [])
                                    if res.plan else None)}
            if not res.ok:
                raise RuntimeError(f"{tag} load failed: {res.stop_reason}")
            out = os.path.join(out_dir, f"F_{slug}.rvt")
            wrec, wout = T.stage_walls(model, loaded, out, specimens, wall_mode="min")
            rec["walls"] = {"ok": bool(wrec.get("ok")), "n_walls": len(wrec.get("walls") or []),
                            "new_ids": wrec.get("new_ids"),
                            "elemtable_after": wrec.get("elemtable_after"),
                            "n_dangling_per_wall": [w.get("n_dangling") for w in wrec.get("walls") or []],
                            "verify": wrec.get("verify"),
                            "error": wrec.get("error"), "blocker": wrec.get("blocker")}
            if not wout:
                raise RuntimeError(f"{tag} wall stage failed: {wrec.get('error') or wrec.get('blocker')}")
            rec["file"] = _relp(out)
            rec["family"] = {"name": prod.name, "constructor": plan.constructor,
                             "kwargs": plan.kwargs, "status": plan.status,
                             "connectors": len(prod.doc.connectors),
                             "parameters": len(prod.doc.params),
                             "elements": len(prod.doc.elements),
                             "part_type": prod.doc.part_type,
                             "work_plane_based": bool(prod.doc.work_plane_based)}
            rec["composition"] = ("ZA_deep + ONE family (loaded, place=False, the stage-L "
                                  "loader) + the room's 4 walls (mode 'min') -- the walls are "
                                  "the audit-forcing agent, identical to the certified "
                                  "walls_only wall layer")
            rec["ok"] = True
        except Exception as e:
            rec["ok"] = False
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc(limit=8)
        rec["seconds"] = round(time.time() - t0, 1)
        reports.append(rec)
        _log(f"F_{slug}: ok={rec['ok']} -> {rec.get('file') or rec.get('error')} "
             f"({rec['seconds']}s)")
    return reports


# ===========================================================================
# the static per-family assay (family-mode validator + provenance +
# structure), incl. the house switchboard vs a factory panelboard
# ===========================================================================

def _family_doc_shape(rfa_path: str) -> Dict[str, Any]:
    """Decode a standalone .rfa's family document: class histogram, part
    type / category of its Family record, connector count, param count."""
    from rvt.families import FamilyIndex
    out: Dict[str, Any] = {}
    fi = FamilyIndex(rfa_path)
    hist = fi.class_histogram(0)
    out["records"] = int(sum(hist.values()))
    out["class_histogram_top"] = dict(sorted(hist.items(), key=lambda kv: -kv[1])[:14])
    for cls in ("Family", "FamilySymbol", "ConnectorElem", "ExtrusionElem", "CurveElem",
                "ParamElemFamily", "RefPlane", "SketchPlane", "VarSketch", "GenSweptSolid",
                "ElectricalLoadClassification", "UnitsElem", "Level"):
        out[cls] = int(hist.get(cls, 0))
    fams = fi.ids_of_class(0, "Family") if hasattr(fi, "ids_of_class") else []
    if fams:
        v = fi.value(0, fams[0]) or {}
        out["family_part_type"] = v.get("m_partType")
        out["family_category"] = v.get("m_categoryId")
        out["family_work_plane_based"] = v.get("m_workPlaneBased")
        si = (v.get("m_symbolInfo") or {}).get("value") or {}
        out["family_name"] = si.get("m_name")
    return out


def assay_family_file(rfa_path: str, tag: str) -> Dict[str, Any]:
    """The certified family-mode validator + the v2 provenance ledger + the
    document shape, for one .rfa."""
    from rvt.famgen import famdoc_adoc as FA
    rec: Dict[str, Any] = {"tag": tag, "path": _relp(rfa_path),
                           "size": os.path.getsize(rfa_path), "md5": _md5(rfa_path)}
    try:
        val = FA.validate_family_file(rfa_path)
        fm = val.get("family_mode") or {}
        rec["family_mode"] = {"verdict": fm.get("verdict"), "n_errors": fm.get("n_errors"),
                              "n_warnings": fm.get("n_warnings"),
                              "errors": (fm.get("errors") or [])[:6]}
        raw = val.get("arbiter_raw") or {}
        rec["arbiter_raw"] = {"verdict": raw.get("verdict"), "n_errors": raw.get("n_errors")}
        rec["validate_ok"] = bool(val.get("ok"))
        rec["gate_note"] = val.get("gate_note")
    except Exception as e:
        rec["family_mode"] = {"error": f"{type(e).__name__}: {e}"}
        rec["validate_ok"] = False
    try:
        prov = FA.provenance_scan_v2(rfa_path)
        checks = prov.get("checks") or {}
        rec["provenance"] = {
            "ok": bool(prov.get("ok")),
            "verdict": prov.get("verdict"),
            "n_checks": len(checks),
            "checks": {k: bool(v) for k, v in checks.items()},
            "failed_checks": [k for k, v in checks.items() if not v],
            "adocument": {kk: (prov.get("adocument") or {}).get(kk)
                          for kk in ("conclusion", "dangling_refs", "donor_id_byte_hits",
                                     "our_refs", "decodes_clean")
                          if isinstance(prov.get("adocument"), dict)},
        }
    except Exception as e:
        rec["provenance"] = {"ok": False, "error": f"{type(e).__name__}: {e}",
                             "traceback": traceback.format_exc(limit=4)}
    try:
        rec["shape"] = _family_doc_shape(rfa_path)
    except Exception as e:
        rec["shape"] = {"error": f"{type(e).__name__}: {e}"}
    return rec


def static_family_assay(model, out_dir: str) -> Dict[str, Any]:
    """Per-family static verdict for the room's 8 families (as built by the
    room, in experiments/ifc_room/families/) + the switchboard-vs-panel
    structural comparison + the emission-path finding."""
    assay: Dict[str, Any] = {"families": [], "notes": []}
    stems: Dict[str, str] = {}
    for fn in sorted(os.listdir(FAMILY_DIR)):
        if fn.endswith(".rfa"):
            stems[fn.split("_", 1)[0].upper()] = os.path.join(FAMILY_DIR, fn)
    tag_of_stem = {"MSB": "MSB", "DP1": "DP-1", "DP2": "DP-2", "LP1": "LP-1",
                   "LP2": "LP-2", "LP3": "LP-3", "LP4": "LP-4", "T1": "T1"}
    for stem, path in stems.items():
        tag = tag_of_stem.get(stem, stem)
        rec = assay_family_file(path, tag)
        assay["families"].append(rec)
        fm = rec.get("family_mode") or {}
        _log(f"assay {tag:5s}: family-mode {fm.get('verdict')} ({fm.get('n_errors')} err) "
             f"provenance ok={rec.get('provenance', {}).get('ok')} "
             f"size {rec['size']}")
    # ---- the switchboard vs a factory panelboard (structure, not bytes) ----
    try:
        assay["switchboard_vs_panel"] = compare_switchboard_to_panel(model)
    except Exception as e:
        assay["switchboard_vs_panel"] = {"error": f"{type(e).__name__}: {e}",
                                        "traceback": traceback.format_exc(limit=6)}
    # ---- the emission-path finding ------------------------------------------
    sizes = {rec["tag"]: rec["size"] for rec in assay["families"]}
    assay["emission_path"] = {
        "room_rfa_sizes": sizes,
        "old_donor_graft_size": 270336,
        "v2_clean_size": 278528,
        "finding": ("every room .rfa is 270,336 B = the OLD factory emitter's size "
                    "(FamilyProduct.write -> skeleton.emit_family_rfa: donor Global/Latest + "
                    "donor footer + donor end parity, per docs/inbox/asset-assay.md), NOT the "
                    "assay-clean v2 emitter (rvt.famgen.famdoc_adoc.emit_family_rfa_v2, "
                    "278,528 B).  The STANDALONE room .rfa artefacts therefore carry the assay's "
                    "known provenance debt.  This does NOT bear on the room's LOAD/audit "
                    "question: the stage-L loader builds each embedded family document from the "
                    "FamilyDoc OBJECT, never from the .rfa file -- the loaded project files contain "
                    "our constructed documents, not the donor Latest."),
        "recommendation": ("switch stage_families to the clean emitter "
                           "(FamilyProduct.write -> emit_family_rfa_v2, the family-genesis "
                           "stream's standing request) before any standalone .rfa is treated as "
                           "an artefact of record; the render family (render_probe_box.rfa) is "
                           "emitted through the clean path here"),
    }
    return assay


def compare_switchboard_to_panel(model) -> Dict[str, Any]:
    """The house switchboard (the brief's prime suspect) vs a factory PRL
    panelboard and the factory transformer: document shape, parameters,
    connector hosting -- the assayer's structural comparison."""
    prods = {}
    for tag in ("MSB", "LP-4", "T1"):
        try:
            _plan, prod = build_room_product(model, tag, 1000)
            prods[tag] = prod
        except Exception as e:
            prods[tag] = e
    rows = {}
    for tag, prod in prods.items():
        if isinstance(prod, Exception):
            rows[tag] = {"error": f"{type(prod).__name__}: {prod}"}
            continue
        doc = prod.doc
        hist: Dict[str, int] = {}
        for el in doc.elements:
            hist[el.class_name] = hist.get(el.class_name, 0) + 1
        conns = []
        for c in doc.elements:
            if c.class_name == "ConnectorElem":
                notes = getattr(c, "notes", None) or []
                conns.append({"elem_id": c.elem_id,
                              "host_face_note": next((n for n in notes if "face" in n), None)})
        rows[tag] = {
            "family_name": doc.name,
            "kind": prod.kind,
            "category": doc.category_id,
            "part_type": doc.part_type,
            "work_plane_based": bool(doc.work_plane_based),
            "elements": len(doc.elements),
            "class_histogram": dict(sorted(hist.items())),
            "n_parameters": len(doc.params),
            "parameters": sorted(doc.params),
            "types": [n for n, _v in doc.types],
            "n_connectors": len(doc.connectors),
            "connectors": conns,
            "forms": [{"kind": f.kind, **{k: v for k, v in f.params.items()
                                          if k in ("role", "width_ft", "depth_ft",
                                                   "height_ft", "base_z_ft", "rep")}}
                      for f in prod.forms],
            "facts_assumed": prod.facts.assumed(),
            "facts_unverified": prod.facts.unverified(),
        }
    # deltas: switchboard vs the panelboard
    msb, lp4 = rows.get("MSB", {}), rows.get("LP-4", {})
    delta: Dict[str, Any] = {}
    if "error" not in msb and "error" not in lp4:
        delta = {
            "part_type": {"MSB": msb.get("part_type"), "LP-4": lp4.get("part_type"),
                          "note": "16 = switchboard (the class the sample panelboard factory "
                                  "never emitted before this stream) vs 14 = panelboard"},
            "work_plane_based": {"MSB": msb.get("work_plane_based"),
                                 "LP-4": lp4.get("work_plane_based"),
                                 "note": "MSB is floor-standing (like the certified T1); LP-4 is "
                                         "face-hosted-shaped (work-plane-based)"},
            "parameters_only_in_msb": sorted(set(msb.get("parameters", [])) -
                                             set(lp4.get("parameters", []))),
            "parameters_only_in_lp4": sorted(set(lp4.get("parameters", [])) -
                                             set(msb.get("parameters", []))),
            "class_histogram_delta": {
                k: {"MSB": msb.get("class_histogram", {}).get(k, 0),
                    "LP-4": lp4.get("class_histogram", {}).get(k, 0)}
                for k in sorted(set(msb.get("class_histogram", {})) |
                                set(lp4.get("class_histogram", {})))
                if msb.get("class_histogram", {}).get(k, 0) != lp4.get("class_histogram", {}).get(k, 0)},
            "elements": {"MSB": msb.get("elements"), "LP-4": lp4.get("elements")},
            "n_connectors": {"MSB": msb.get("n_connectors"), "LP-4": lp4.get("n_connectors")},
        }
    return {"products": rows, "msb_vs_lp4_delta": delta,
            "reading": ("The house switchboard is composed from the SAME building blocks as "
                        "the certified transformer (floor-standing box + top-face connector) and "
                        "the panelboard (the 11-parameter tagging contract) -- see the deltas.  "
                        "Nothing structural distinguishes it from families that load: it "
                        "loads together with the other seven in stage_L8_lp4 (viewer 'Design "
                        "is empty', i.e. translated), and every static gate passes.  The static "
                        "assay finds NO defect in the switchboard; the room's failure is NOT "
                        "attributable to it on any evidence in hand.  The F_msb probe (below) "
                        "tests it under a REAL audit for the first time.")}


# ===========================================================================
# FORENSICS -- the composition matrix + the PASS-vs-FAIL record diff that
# refute the "one defective family" premise (reproducible, from the bytes)
# ===========================================================================

#: the ifc-room files this stream's charter rests on + their recorded verdicts
ROOM_FILES = [
    ("ZA_deep (base)", os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a",
                                    "ZA_deep.rvt"), "PASS (certified)"),
    ("stage_L8_lp4", os.path.join(ROOM_DIR, "stage_L8_lp4.rvt"),
     "'PASS' recorded -- viewer showed 'Design is empty' (symbol-only file)"),
    ("walls_only", os.path.join(ROOM_DIR, "electrical_room_2500a_walls_only.rvt"),
     "PASS (real audit; tree shows the level node)"),
    ("walls_only_unjoined", os.path.join(ROOM_DIR, "electrical_room_2500a_walls_only_unjoined.rvt"),
     "PASS"),
    ("stage_W_loaded_walls", os.path.join(ROOM_DIR, "stage_W_loaded_walls.rvt"),
     "FAIL (Revit-DocumentCorruption audit -1073742517)"),
    ("electrical_room_2500a", os.path.join(ROOM_DIR, "electrical_room_2500a.rvt"),
     "FAIL (audit)"),
]


def composition_matrix() -> List[Dict[str, Any]]:
    """Per ifc-room file: family documents / walls / instances / host
    record count, from the bytes -- the matrix that shows stage_L8_lp4 is
    the FULL 8-family load with NO walls and NO instances."""
    rows: List[Dict[str, Any]] = []
    for label, path, verdict in ROOM_FILES:
        row: Dict[str, Any] = {"file": _relp(path), "label": label, "recorded_verdict": verdict}
        if not os.path.exists(path):
            row["error"] = "missing"
            rows.append(row)
            continue
        c = content_census(path)
        row.update({"family_documents": c.get("family_documents"),
                    "save_units": c.get("save_units"),
                    "walls": c.get("SWall"), "instances": c.get("FamilyInstance"),
                    "families_host": c.get("Family"), "symbols": c.get("FamilySymbol"),
                    "host_records": c.get("host_records"),
                    "four_registry_coherent": c.get("four_registry_coherent")})
        rows.append(row)
    return rows


def record_diff(path_pass: str, path_fail: str) -> Dict[str, Any]:
    """Record-by-record diff of two project files' partition streams (all
    save units, all three seqs, the corrected record framing) + a stream-
    level diff.  Used on stage_L8_lp4 (PASS) vs stage_W_loaded_walls (FAIL)
    to prove the FAIL delta is EXACTLY the wall layer."""
    from collections import defaultdict
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    from rvt.objects import iter_records

    def streams(p):
        out = {}
        with open_rvt(p) as d:
            for s in d.streams():
                lg = d.logical(s.name)
                out[s.name] = (len(lg), hashlib.sha256(lg).hexdigest())
        return out

    def records(p):
        with open_rvt(p) as d:
            lg = d.logical(d.partition_streams()[0])
        w = StreamWalker(lg, inflate=True, keep_data=True)
        seg: Dict[Tuple[int, int], bytes] = defaultdict(bytes)
        for b in sorted(w.blocks, key=lambda x: x.hdr_offset):
            seg[(b.unit, b.seq)] += b.data
        recs: Dict[Tuple[int, int], Dict[int, str]] = {}
        for (u, s), data in seg.items():
            hl = 12 if s == 101 else 16
            m = {}
            for r in iter_records(data, s):
                m[r.elem_id] = hashlib.md5(
                    data[r.seg_offset: r.seg_offset + hl + r.body_size + 4]).hexdigest()
            recs[(u, s)] = m
        return recs, len(w.errors)

    sa, sb = streams(path_pass), streams(path_fail)
    stream_diff = {n: {"pass": sa.get(n), "fail": sb.get(n),
                       "identical": (n in sa and n in sb and sa[n][1] == sb[n][1])}
                   for n in sorted(set(sa) | set(sb))}
    ra, ea = records(path_pass)
    rb, eb = records(path_fail)
    per_seq: Dict[str, Any] = {}
    total_changed = total_lost = 0
    for k in sorted(set(ra) | set(rb)):
        a, b = ra.get(k, {}), rb.get(k, {})
        new = sorted(set(b) - set(a))
        lost = sorted(set(a) - set(b))
        changed = sorted(i for i in set(a) & set(b) if a[i] != b[i])
        total_changed += len(changed)
        total_lost += len(lost)
        if new or lost or changed:
            per_seq[f"unit{k[0]}_seq{k[1]}"] = {"added": new, "lost": lost,
                                                   "changed": changed}
    return {
        "pass_file": _relp(path_pass), "fail_file": _relp(path_fail),
        "walker_errors": {"pass": ea, "fail": eb},
        "streams_differing": sorted(n for n, v in stream_diff.items() if not v["identical"]),
        "streams_identical": sorted(n for n, v in stream_diff.items() if v["identical"]),
        "record_delta": per_seq,
        "existing_records_changed": total_changed,
        "records_lost": total_lost,
        "units_1_to_8_identical": all(ra.get(k) == rb.get(k)
                                      for k in set(ra) | set(rb) if k[0] > 0),
        "conclusion": (
            "the FAIL file differs from the PASS file by ONLY the added wall records "
            "(4 per seq) + ElemTable rows + BasicFileInfo identity; zero existing records "
            "changed or lost; embedded family units 1..8 identical"
            if total_changed == 0 and total_lost == 0 else
            f"WARNING: {total_changed} existing records changed / {total_lost} lost -- "
            f"inspect record_delta"),
    }


def forensics(out_dir: str) -> Dict[str, Any]:
    """The reproducible refutation of verdict #22's premise."""
    rec: Dict[str, Any] = {"composition_matrix": composition_matrix()}
    l8 = os.path.join(ROOM_DIR, "stage_L8_lp4.rvt")
    sw = os.path.join(ROOM_DIR, "stage_W_loaded_walls.rvt")
    wo = os.path.join(ROOM_DIR, "electrical_room_2500a_walls_only.rvt")
    if os.path.exists(l8) and os.path.exists(sw):
        rec["diff_stageL8_PASS_vs_stageW_FAIL"] = record_diff(l8, sw)
    if os.path.exists(wo) and os.path.exists(sw):
        # the wall layer in the two contexts: compare the 4 wall OBJECTS
        rec["wall_layer_comparison"] = _compare_wall_layers(wo, sw)
    rec["reading"] = (
        "stage_L8_lp4 = ZA_deep + ALL 8 room families (incl. the 2500 A house switchboard), "
        "0 walls, 0 instances; its recorded 'PASS' was 'Design is empty' (a symbol-only file "
        "the extractor short-circuits -- NOT an audited pass of the family layer).  walls_only "
        "(0 families, 4 walls) PASSES a real audit.  stage_W_loaded_walls (8 families + 4 "
        "walls) FAILS, and it differs from stage_L8 by EXACTLY the 4 wall records -- which are "
        "byte-identical (modulo id) to walls_only's PASSING walls.  =>  no evidence any single "
        "family is defective; the loaded family layer has never survived a real audit on the "
        "genesis base; the walls merely forced one.  The F_ set (walls as forcer) and the R_inst "
        "set (an instance as forcer) name it.")
    return rec


def _compare_wall_layers(walls_only: str, stage_w: str) -> Dict[str, Any]:
    """The 4 wall objects in the PASS context (walls_only) vs the FAIL
    context (stage_W): identical modulo their own file-specific ids?"""
    from rvt.mutate import Document

    def canon(obj, id_map):
        def m(v):
            if isinstance(v, dict):
                return {k: m(x) for k, x in sorted(v.items())}
            if isinstance(v, list):
                return [m(x) for x in v]
            if isinstance(v, int) and not isinstance(v, bool):
                return id_map.get(v, v)
            return v
        return json.dumps(m(obj), sort_keys=True, default=str)

    dp, df = Document.from_file(walls_only), Document.from_file(stage_w)
    wp, wf = dp.ids_of_class("SWall"), df.ids_of_class("SWall")
    ip = {eid: f"W{i}" for i, eid in enumerate(wp)}
    if_ = {eid: f"W{i}" for i, eid in enumerate(wf)}
    per_wall = []
    all_same = True
    for i in range(min(len(wp), len(wf))):
        row: Dict[str, Any] = {"wall": f"W{i}", "id_pass_ctx": wp[i], "id_fail_ctx": wf[i]}
        for seq in (101, 102, 103):
            ap, af = dp.decode(wp[i], seq), df.decode(wf[i], seq)
            vp = getattr(ap, "value", ap)
            vf = getattr(af, "value", af)
            same = canon(vp, ip) == canon(vf, if_)
            row[f"seq{seq}_identical_modulo_id"] = same
            all_same = all_same and same
        per_wall.append(row)
    return {"walls_pass_ctx": wp, "walls_fail_ctx": wf, "per_wall": per_wall,
            "wall_objects_identical_modulo_ids": bool(all_same),
            "conclusion": ("the wall layer is byte-identical (modulo its own ids) in the "
                           "PASS context (walls_only) and the FAIL context (stage_W): the "
                           "walls are NOT the discriminator; the loaded family layer is"
                           if all_same else
                           "wall objects DIFFER between contexts -- inspect per_wall")}


# ===========================================================================
# gates over every emitted project file
# ===========================================================================

def gate_file(path: str) -> Dict[str, Any]:
    val = validate_rvt(path)
    cen = census(path)
    idg = identity(path)
    cont = content_census(path)
    return {"path": _relp(path), "md5": val.get("md5"), "size": val.get("size"),
            "validate": {"verdict": val.get("verdict"), "n_errors": val.get("n_errors"),
                         "n_warnings": val.get("n_warnings"),
                         "errors": val.get("errors")},
            "four_registry_coherent": cen.get("coherent"),
            "family_documents": cen.get("contentdocs_entries"),
            "save_units": cen.get("save_units"),
            "identity_gate": idg.get("status"), "identity_issues": idg.get("issues"),
            "content": cont,
            "self_checks_ok": (val.get("verdict") == "VALID"
                               and idg.get("status") == "PASS"
                               and cen.get("coherent") is not False)}


# ===========================================================================
# probes.json + control
# ===========================================================================

def make_control(out_dir: str) -> str:
    """Byte-identical copy of the certified base under a control name."""
    ctrl = os.path.join(out_dir, "CTRL_ZA_deep_render.rvt")
    shutil.copyfile(BASE, ctrl)
    return ctrl


def write_probes_manifest(out_dir: str, rinst: List[Dict[str, Any]],
                          fset: List[Dict[str, Any]], gates: Dict[str, Dict[str, Any]],
                          control_path: str) -> str:
    def entry(rep: Dict[str, Any]) -> Dict[str, Any]:
        f = rep.get("file")
        if not f:
            return {"probe": rep.get("probe"), "kind": "not_built",
                    "error": rep.get("error") or rep.get("reason_not_built")}
        g = gates.get(f, {})
        e: Dict[str, Any] = {
            "file": f, "probe": rep["probe"], "kind": "probe",
            "base": _relp(BASE),
            "md5": g.get("md5"), "validator": g.get("validate", {}).get("verdict"),
            "validator_errors": g.get("validate", {}).get("n_errors"),
            "four_registry": g.get("four_registry_coherent"),
            "family_documents": g.get("family_documents"),
            "identity_gate": g.get("identity_gate"),
            "content": g.get("content"),
            "self_checks_ok": g.get("self_checks_ok"),
        }
        if rep["probe"].startswith("R_inst"):
            e["composition"] = ("ZA_deep + ONE loaded family + ONE placed free-standing instance, "
                                "NO walls -- the instance is the render subject AND the model "
                                "element that forces the corruption audit")
            e["expected_model_tree"] = rep.get("expected_tree")
            e["family"] = {k: v for k, v in (rep.get("family") or {}).items()
                           if k in ("name", "kind", "connectors", "parameters", "elements",
                                    "constructor", "source_rfa", "loader")}
            e["placement"] = {k: (rep.get("instance") or {}).get(k)
                              for k in ("elem_id", "symbol", "family", "category",
                                        "position_m", "position_ft", "yaw_deg",
                                        "connector_manager", "n_dangling")}
            if rep.get("placement_note"):
                e["placement_note"] = rep["placement_note"]
            reps = (g.get("content") or {}).get("render_reps") or {}
            if reps:
                e["render_reps"] = reps
                sg = str(reps.get("symbol_geometry") or "")
                if sg.startswith("BAKED"):
                    e["render_prediction"] = ("symbol geometry is BAKED (GElement + geom "
                                              "table, our solid) -> if the extractor draws "
                                              "family instances at all, THIS instance should "
                                              "render; a no-render here indicts the symbol "
                                              "GElement grammar (loader hypothesis [H]) or the "
                                              "instance rep, not regeneration")
                elif sg.startswith("DUMMY"):
                    e["render_prediction"] = ("symbol rep is a SerializedDummy (needs "
                                              "regeneration) -> expected NOT to render if the "
                                              "extractor does not regenerate (the walls "
                                              "finding); the family document's 8 solids are the "
                                              "only baked geometry.  Contrast with the two "
                                              "GElement-symbol probes = the render A/B")
        else:
            e["composition"] = rep.get("composition")
            e["family"] = {k: v for k, v in (rep.get("family") or {}).items()
                           if k in ("name", "constructor", "status", "part_type",
                                    "work_plane_based", "connectors", "parameters")}
            e["walls"] = {k: (rep.get("walls") or {}).get(k)
                          for k in ("n_walls", "new_ids", "n_dangling_per_wall")}
            e["tests"] = (f"{rep.get('tag')} ALONE under a real audit: this ONE family loaded on "
                          f"ZA_deep + the audit-forcing wall layer (identical to the certified "
                          f"walls_only walls, which PASSED)")
            e["if_PASS"] = (f"{rep.get('tag')}'s family document + host layer survives Revit's "
                            f"corruption audit on the genesis base")
            e["if_FAIL"] = (f"{rep.get('tag')} fails the audit ALONE -> read the whole F_ set: one "
                            f"FAIL among passes = a defective single family; ALL F_ files FAIL "
                            f"= the loader-on-genesis-base / any-family defect (not this one)")
        return e

    manifest = {
        "stream": ("render-instances: (A) INSTANCE-RENDER probes -- do placed instances of OUR "
                   "families produce viewable geometry (LOAD IS NOT RENDER); (B) THE ROOM'S "
                   "FAMILY LAYER BISECTED under a real audit (one F_ file per room family, the "
                   "walls as the audit-forcing agent).  All on the certified genesis base ZA_deep."),
        "base": {
            "file": _relp(BASE),
            "certification": {
                "file": _relp(BASE),
                "proves": ("ZA_deep = certified deep genesis rung (ORCHESTRATOR VERDICTS #18: "
                           "ZA_deep PASS); re-confirmed as the ifc-room control in batches "
                           "20/21 -- the family-free base every probe here declares"),
            },
        },
        "standing_control": {
            "file": _relp(control_path),
            "identical_to": _relp(BASE),
            "md5": _md5(control_path) if os.path.exists(control_path) else None,
            "purpose": ("byte-identical copy of the certified base under a new name -- read "
                        "FIRST; a control FAIL voids the round (oracle / environment)"),
        },
        "critical_premise_correction": {
            "recorded_verdict_22_claim": ("'walls + ONE loaded family + a PLACED instance "
                                          "(stage_L8_lp4) PASSES => the FULL-family stage failing "
                                          "means ONE family is defective'"),
            "measured_fact": ("stage_L8_lp4.rvt = ZA_deep + ALL 8 room families (incl. the 2500 A "
                              "house switchboard), NO walls, NO instances (build_record stage L: "
                              "chained load_family_into_project(place=False) x8; the file's bytes: "
                              "9 save units / 8 ContentDocuments / 0 SWall / 0 FamilyInstance). "
                              "'lp4' is only the LAST of the 8 chained loads.  Its viewer verdict "
                              "was 'Design is empty' -- a symbol-only file the extractor short-"
                              "circuits, NOT an audited pass of the family layer."),
            "the_real_delta": ("stage_W_loaded_walls (FAIL) minus stage_L8_lp4 (empty-design PASS) "
                               "= EXACTLY the 4 wall records (byte-identical, modulo id, to the "
                               "PASSING walls_only walls) + 4 ElemTable rows + BasicFileInfo "
                               "identity; the 8 embedded family units and all 3,486 existing records "
                               "are UNCHANGED (measured record-by-record this session).  The walls "
                               "PASS alone on ZA_deep; the same walls FAIL when the loaded family "
                               "layer is present.  => the loaded family layer has never survived a "
                               "real audit on the genesis base; the walls only FORCED one.  There is "
                               "NO evidence that a single family is defective, and NO family is "
                               "exonerated."),
            "consequence": ("(i) instance PLACEMENT on the genesis base is UNPROVEN (the only file "
                            "with placed instances, electrical_room_2500a, FAILED); the R_inst "
                            "probes are the first clean instance-on-genesis tests.  (ii) 'rvt.mutate "
                            "creation proven on the genesis lineage' holds for WALLS only."),
        },
        "read_order": ("CTRL first (round validity); R_inst_box (the purest render + first clean "
                       "instance-on-genesis test); R_inst_panel (the room's own family placed); "
                       "F_lp4 (ONE loaded family under a real audit -- the walls as forcer); "
                       "then F_msb (the switchboard the void verdict blamed) and the rest of the "
                       "F_ set as budget allows; R_inst_downlight (IFC-derived family, a second "
                       "loader) last."),
        "reading_the_matrix": {
            "control FAIL": "oracle / environment problem -- every verdict VOID",
            "R_inst_box PASS + tree shows the instance": ("baked family solids DO render through the "
                                                        "instance path; RENDER becomes a real gate; "
                                                        "and add_family_instance is proven on the "
                                                        "genesis base for the first time"),
            "R_inst_box translates but tree = level only": ("LOAD but no RENDER for instances too "
                                                          "-> the extractor does not draw our symbol "
                                                          "geometry (SerializedDummy symbol rep / "
                                                          "family-solid path); the render track needs "
                                                          "baked GElement geometry"),
            "R_inst_box FAIL (audit)": ("the loaded family layer (or the instance) fails the audit "
                                        "with NO walls present -> the defect is the family/loader "
                                        "layer on the genesis base, not a wall interaction"),
            "F_x: exactly ONE fails": "THAT family is defective (the charter's original hypothesis)",
            "F_x: ALL fail": ("no single family is guilty: the loader-on-genesis-base output fails "
                              "the audit for ANY family once an audit-forcing element is present -- "
                              "cross-read R_inst (family + instance, no walls) to name it as the "
                              "family layer vs the wall x family interaction"),
            "F_x: ALL pass": ("each family survives alone -> the failure needs the multi-family "
                              "load or is specific to stage_W's exact construction; upload the "
                              "existing stage_W_loaded_walls twin as the confirming control"),
            "R_inst_panel PASS but F_lp4 FAIL": ("the SAME family passes with an instance and "
                                                 "fails with walls -> a wall x loaded-family "
                                                 "interaction (the wall commit over a file "
                                                 "carrying embedded family documents)"),
            "RENDER A/B (box+panel vs downlight)": ("box + panel carry BAKED symbol geometry (a "
                                                    "GElement symbol rep + geom table, the "
                                                    "rvt.famgen loader); the downlight's symbol is "
                                                    "a SerializedDummy (rvt.famload).  Box/panel "
                                                    "RENDER + downlight NOT = symbol geometry must "
                                                    "be BAKED (no regeneration in the extractor); "
                                                    "all three render = the extractor draws from "
                                                    "the family document / regenerates; none render "
                                                    "= the render path needs baked geometry on the "
                                                    "INSTANCE rep or the symbol GElement grammar is "
                                                    "off"),
        },
        "probes": [entry(r) for r in rinst + fset if r.get("file") or r.get("error")
                   or r.get("kind") == "not_built"],
    }
    path = os.path.join(out_dir, "probes.json")
    _jdump(path, manifest)
    return path


def gate_dry_run(files: List[str]) -> Dict[str, Any]:
    return T.gate_dry_run(files)


# ===========================================================================
# main
# ===========================================================================

def run(only: Sequence[str], out_dir: str = OUT_DIR,
        f_tags: Sequence[str] = ROOM_TAGS) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    started = time.time()
    record: Dict[str, Any] = {
        "pipeline": "render_probes.run", "base": _relp(BASE),
        "specimen_source": _relp(SPECIMEN_SRC), "ifc": _relp(IFC),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "proof_only": ("PROOF-ONLY research artefacts: base = certified genesis lineage "
                       "(sample-derived, in-place substituted); added layer = OUR constructors' "
                       "families + walls + instances; NOT a deliverable to any third party"),
        "stages": {},
    }
    everything = not only
    want = lambda s: everything or s in only            # noqa: E731

    _log("resolving the intent ...")
    model = resolve_intent()
    record["intent"] = {"equipment": len(model.equipment),
                        "walls": len(model.room.walls) if model.room else 0,
                        "plans": [(p.tag, p.status) for p in model.family_plans]}

    if want("forensics"):
        _log("forensics: composition matrix + PASS-vs-FAIL record diff ...")
        record["stages"]["forensics"] = forensics(out_dir)
        fx = record["stages"]["forensics"]
        d = fx.get("diff_stageL8_PASS_vs_stageW_FAIL") or {}
        _log(f"  diff: changed={d.get('existing_records_changed')} lost={d.get('records_lost')} "
             f"units1..8 identical={d.get('units_1_to_8_identical')}")

    if want("assay"):
        _log("static per-family assay ...")
        record["stages"]["assay"] = static_family_assay(model, out_dir)

    specimens = None
    if want("rinst") or want("fset"):
        _log(f"loading specimen scaffolding from {os.path.basename(SPECIMEN_SRC)} ...")
        specimens = T.SpecimenSet(SPECIMEN_SRC)
        record["specimens"] = {"source": _relp(SPECIMEN_SRC),
                               "wall": specimens.wall_id, "wall_type": specimens.wall_type,
                               "instance": specimens.instance_id,
                               "instance_symbol": specimens.instance_symbol,
                               "instance_category": specimens.instance_category}

    rinst: List[Dict[str, Any]] = []
    fset: List[Dict[str, Any]] = []
    if want("rinst"):
        _log("building the R_inst render probes ...")
        rinst = build_rinst_probes(model, specimens, out_dir)
        record["stages"]["rinst"] = rinst
    if want("fset"):
        _log("building the F_ per-family bisection set ...")
        fset = build_family_bisection(model, specimens, out_dir, tags=f_tags)
        record["stages"]["fset"] = fset

    # ---- gates over every emitted project file --------------------------
    emitted = [r["file"] for r in rinst + fset if r.get("file")]
    gates: Dict[str, Dict[str, Any]] = {}
    if emitted:
        _log(f"gating {len(emitted)} emitted files (validator / registries / identity) ...")
        for rel in emitted:
            ap = os.path.join(ROOT, rel) if not os.path.isabs(rel) else rel
            g = gate_file(ap)
            gates[rel] = g
            _log(f"  {os.path.basename(rel):22s} {g['validate']['verdict']} "
                 f"({g['validate']['n_errors']} err, {g['validate']['n_warnings']} warn); "
                 f"registries coherent={g['four_registry_coherent']}; "
                 f"famdocs={g['family_documents']}; identity {g['identity_gate']}; "
                 f"walls={g['content'].get('SWall')} inst={g['content'].get('FamilyInstance')}")
        record["gates"] = gates
        ctrl = make_control(out_dir)
        record["control"] = {"file": _relp(ctrl), "md5": _md5(ctrl),
                             "identical_to": _relp(BASE), "base_md5": _md5(BASE)}
        pj = write_probes_manifest(out_dir, rinst, fset, gates, ctrl)
        record["probes_manifest"] = _relp(pj)
        record["gate_dry_run"] = gate_dry_run(
            [os.path.join(ROOT, r) for r in emitted])
        _log(f"gate dry-run: {record['gate_dry_run']}")

    record["seconds"] = round(time.time() - started, 1)
    built = [r for r in rinst + fset if r.get("kind") != "not_built"]
    record["all_ok"] = all(r.get("ok") for r in built) if built else None
    rp = os.path.join(out_dir, "render_probes.json")
    _jdump(rp, record)
    _log(f"record -> {_relp(rp)} ({record['seconds']}s); all_ok={record['all_ok']}")
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="render probes + the room's family-layer "
                                             "bisection (render-instances stream)")
    ap.add_argument("--only", action="append", default=[],
                    choices=["forensics", "assay", "rinst", "fset"],
                    help="run only these stages (repeatable); default = all")
    ap.add_argument("-d", "--dir", default=OUT_DIR)
    ap.add_argument("--tags", default=",".join(ROOM_TAGS),
                    help="comma list of room family tags for the F_ set")
    a = ap.parse_args(argv)
    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    rec = run(a.only, out_dir=a.dir, f_tags=tags)
    print(json.dumps({"all_ok": rec.get("all_ok"),
                      "emitted": sorted(rec.get("gates", {}).keys()),
                      "seconds": rec["seconds"]}, indent=1))
    return 0 if rec.get("all_ok") is not False else 2


if __name__ == "__main__":
    raise SystemExit(main())
