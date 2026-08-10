#!/usr/bin/env python3
"""ifc_intent.py -- IFC INTENT -> OUR PROJECT FILE, END TO END (the ifc-room stream).

Front door onto ``rvt.ifc.intent`` (the resolved, mapped intent -- spec v2)
plus the two generation stages that consume it:

    # 1. resolve the intent (positions from the placement chain + the
    #    world-baked geometry, family mapping by the tagging-contract pset)
    python tools/ifc_intent.py intent inputs/ifc/electrical-room-2500a.ifc \\
        -o inputs/ifc/electrical-room-2500a.intent.json

    # 2. generate OUR family set (.rfa) from the mapping (catalog facts /
    #    house switchboard), each validated in family mode + provenance-scanned
    python tools/ifc_intent.py families inputs/ifc/electrical-room-2500a.ifc \\
        -d experiments/ifc_room/families

    # 3. the PROJECT FILE on the certified genesis base (staged, each stage a
    #    validated checkpoint + json record; a stage failure names the exact
    #    blocker and the pipeline delivers the deepest good file):
    #      F  families (standalone .rfa deliverables)
    #      L  LOAD our families into the base (rvt.famgen.loader, four-registry)
    #      W  the room's WALLS (rvt.mutate add_wall on the base's wall type,
    #         specimen scaffolding from the base's own certified ancestor R5)
    #      E  the EQUIPMENT instances (our symbols, upright/yaw frames from the
    #         intent, category-patched scaffolding, our connector slots) AND,
    #         in the SAME commit, the feeder CIRCUITS (rvt.mutate add_circuit
    #         over the constructed RbsElectricalSystem specimen)
    #      C  the circuit READBACK (count == non-service edges, both-side
    #         connector back-links) -- names a blocker only if circuits are
    #         missing
    #      V  validate every checkpoint + four-registry census + probes.json
    #         (base + control declared) + a probe_batch gate dry-run
    python tools/ifc_intent.py room inputs/ifc/electrical-room-2500a.ifc \\
        -d experiments/ifc_room [--stages FLWECV] [--base <certified.rvt>]

Every emitted .rvt / .rfa is PROOF-ONLY (research artefact, not a
deliverable to a third party): the base is the certified genesis lineage
(ZA_deep = the rstbasic sample project reduced + 54% substituted in place by
OUR constructors -- NOT a clean-room file), our added layer is OURS
(constructor-built families, records authored from format shapes), and the
provenance ledger of each output says so.

TERRITORY: tools/ifc_intent.py (this file), src/rvt/ifc/intent.py,
tests/test_ifc_intent.py, inputs/ifc/*.intent.json, experiments/ifc_room/**,
docs/inbox/ifc-room.md.  Imports (never edits) rvt.mutate / rvt.commit /
rvt.famgen / rvt.famload / rvt.validate / rvt.hosting / rvt.mep.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from rvt.ifc import intent as I  # noqa: E402

FT_PER_M = 3.280839895013123
DEFAULT_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
DEFAULT_OUT = os.path.join(ROOT, "experiments", "ifc_room")
DEFAULT_BASE = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a", "ZA_deep.rvt")
DEFAULT_SPECIMEN_SRC = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")

#: OST built-ins
OST_ELECTRICAL_EQUIPMENT = -2001040
OST_ELECTRICAL_FIXTURES = -2001060
OST_WALLS = -2000011
OST_STRUCT_COLUMNS = -2001300


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
    print(f"[ifc_intent] {msg}", flush=True)


def _jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


# ===========================================================================
# STAGE F -- the generated FAMILIES (.rfa)
# ===========================================================================

#: (kind of plan) -> the constructor
def _constructor_for(plan: I.FamilyPlan):
    from rvt.famgen import factory as F
    if plan.constructor.endswith("make_panelboard"):
        return F.make_panelboard
    if plan.constructor.endswith("make_transformer"):
        return F.make_transformer
    if plan.constructor.endswith("make_device"):
        return F.make_device
    if plan.constructor.endswith("make_house_switchboard"):
        return I.make_house_switchboard
    raise KeyError(f"no constructor for {plan.tag}: {plan.constructor!r}")


def _is_device_plan(plan: I.FamilyPlan) -> bool:
    """A wiring-device plan (``make_device``, Electrical Fixtures).  Devices
    are per-TYPE content, not per-instance: the family name carries no tag
    (so identical devices share ONE family, :func:`family_key`) and device
    families load in the LAST tier (:func:`_load_order`) -- even a lone
    receptacle, so a device family that cannot be authored never costs the
    equipment before it."""
    return bool(plan.constructor) and plan.constructor.endswith("make_device")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def build_product(plan: I.FamilyPlan, *, start_id: int = 1000, solid: bool = True,
                  family_name: Optional[str] = None):
    """Build the FamilyProduct for one mapping-plan entry (fresh id space
    starting at ``start_id`` -- the loader needs ids above the host
    watermark, the standalone .rfa is happy at 1000)."""
    ctor = _constructor_for(plan)
    kw = dict(plan.kwargs)
    if ctor is I.make_house_switchboard:
        kw.update(start_id=start_id, solid=solid)
        return ctor(**kw)
    name = family_name or _family_name_for(plan)
    kw.update(start_id=start_id, solid=solid, name=name)
    return ctor(**kw)


def _family_name_for(plan: I.FamilyPlan) -> str:
    """Per-BOARD family names so each board's tag rides in its own type
    (the Pset values as parameter VALUES on that board's family).  A wiring
    device is the opposite law: its name carries NO tag -- kind, rating and
    mounting height only -- so every device with the same kwargs shares ONE
    family + type (:func:`family_key`)."""
    kw = plan.kwargs
    if plan.constructor.endswith("make_panelboard"):
        role = {"distribution_panelboard": "Distribution Panelboard",
                "lighting_panelboard": "Lighting Panelboard",
                "receptacle_panelboard": "Receptacle Panelboard"}.get(plan.kind, "Panelboard")
        return (f"{role} {plan.tag} {kw['voltage']} {int(kw['mains_a'])}A "
                f"{'MB' if kw['mcb'] else 'MLO'} {int(kw['spaces'])}sp")
    if plan.constructor.endswith("make_transformer"):
        return f"Dry Type Transformer {plan.tag} {kw['kva']:g}kVA {kw['primary_v']}-{kw['secondary_v']}"
    if _is_device_plan(plan):
        kind = str(kw.get("kind") or "device")
        model = str(plan.variant or "")
        words = [" ".join(w.capitalize() for w in kind.split("-")),
                 model[len(kind) + 1:] if model.startswith(kind + "-") else "",
                 f"{kw.get('voltage')}V", f"{float(kw.get('va') or 0):g}VA"]
        if kw.get("mounting_height_in") is not None:
            words.append(f"{float(kw['mounting_height_in']):g}in AFF")
        return " ".join(w for w in words if w)
    return f"{plan.tag} family"


def family_key(plan: I.FamilyPlan) -> Tuple[str, str]:
    """Plans with the same key are ONE generated family (built once, loaded
    once; every equipment item of the key is placed on its symbol).  The key
    is the generated family NAME -- the host's own uniqueness constraint:
    boards, transformers and the house switchboard carry their tag in it ->
    one family each, as before; wiring devices do not -> N receptacles, one
    family."""
    return (plan.constructor, _family_name_for(plan))


def family_groups(model: I.IntentModel) -> Dict[str, List[str]]:
    """The buildable plans grouped into FAMILIES: ``{representative tag:
    [every tag placed on that family]}`` in plan order (:func:`family_key`
    -- one entry per board / transformer, one shared entry per distinct
    wiring device)."""
    from rvt.frontdoor.intent import buildable_family_plans
    reps: Dict[Tuple[str, str], str] = {}
    groups: Dict[str, List[str]] = {}
    for p in buildable_family_plans(model):
        rep = reps.setdefault(family_key(p), p.tag)
        groups.setdefault(rep, []).append(p.tag)
    return groups


def _group_tags(groups: Dict[str, List[str]], rep: str) -> Dict[str, List[str]]:
    """``{"tags": [...]}`` for a record row of a family SHARED by several
    equipment tags; nothing for a one-tag family (rows stay as they were)."""
    tags = groups.get(rep) or [rep]
    return {"tags": list(tags)} if len(tags) > 1 else {}


def stage_families(model: I.IntentModel, out_dir: str) -> Dict[str, Any]:
    """Write one standalone, validated, provenance-scanned .rfa per mapped
    FAMILY (:func:`family_groups`: a board's own family; ONE shared device
    family whose entry lists every device tag under ``tags``).  Returns the
    stage record."""
    fam_dir = os.path.join(out_dir, "families")
    os.makedirs(fam_dir, exist_ok=True)
    rec: Dict[str, Any] = {"stage": "F", "families": [], "dir": _relp(fam_dir)}
    groups = family_groups(model)
    for plan in model.family_plans:
        if plan.status not in ("resolved", "house"):
            rec["families"].append({"tag": plan.tag, "kind": plan.kind, "built": False,
                                    "reason": plan.refusal or f"status {plan.status}"})
            continue
        if plan.tag not in groups:
            continue                                             # rides its group's family
        try:
            prod = build_product(plan, start_id=1000)
            # a device file is named by its family (the shared key); a board's by its tag
            stem = (_slug(prod.name) if _is_device_plan(plan)
                    else f"{plan.tag.lower().replace('-', '')}_{prod.file_stem}")
            path = os.path.join(fam_dir, f"{stem}.rfa")
            rep = prod.write(path)
            entry = {
                "tag": plan.tag, "kind": plan.kind, "built": True, **_group_tags(groups, plan.tag),
                "path": _relp(path), "size": os.path.getsize(path),
                "family_name": prod.name, "constructor": plan.constructor,
                "kwargs": plan.kwargs, "catalog": plan.catalog, "variant": plan.variant,
                "ok": bool(rep.get("ok")),
                "verify": {k: (rep.get("verify") or {}).get(k)
                           for k in ("gzip_members", "gzip_crc_failures",
                                     "ecc_full_pages", "ecc_mismatch")},
                "validate_family_mode": {
                    "verdict": ((rep.get("validate") or {}).get("family_mode") or {}).get("verdict"),
                    "n_errors": ((rep.get("validate") or {}).get("family_mode") or {}).get("n_errors"),
                },
                "provenance_ok": (rep.get("provenance") or {}).get("ok"),
                "provenance_suspects": (rep.get("provenance") or {}).get("suspects"),
                "assumed_fields": prod.facts.assumed(),
                "unverified_fields": prod.facts.unverified(),
                "notes": list(prod.notes),
                "report": _relp(rep.get("report_path", "")),
            }
            rec["families"].append(entry)
            _log(f"F  {plan.tag:5s} -> {os.path.basename(path)} "
                 f"({'OK' if entry['ok'] else 'CHECK'}: validate="
                 f"{entry['validate_family_mode']['verdict']}, provenance ok="
                 f"{entry['provenance_ok']})")
        except Exception as e:                                   # honest capture
            rec["families"].append({"tag": plan.tag, "kind": plan.kind, "built": False,
                                    "error": f"{type(e).__name__}: {e}",
                                    "traceback": traceback.format_exc(limit=6)})
            _log(f"F  {plan.tag:5s} FAILED: {type(e).__name__}: {e}")
    rec["all_ok"] = all(x.get("ok") for x in rec["families"] if x.get("built"))
    rec["built"] = sum(1 for x in rec["families"] if x.get("built"))
    return rec


# ===========================================================================
# host helpers
# ===========================================================================

def host_watermark(path: str) -> int:
    """The id watermark of a project file (ElemTable footer / max id)."""
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    with open_rvt(path) as f:
        raw = f.raw("Global/ElemTable")
    st = inflate_global_stream(raw)
    tbl = parse_elemtable(st.payload, os.path.basename(path))
    last = int(tbl.footer.last_id) if tbl.footer else 0
    mx = max((r.id for r in tbl.records), default=0)
    return max(last, int(mx))


# ===========================================================================
# STAGE L -- LOAD our families into the certified base
# ===========================================================================

#: load order = the feeder tree top-down (source before its loads), one entry
#: per FAMILY (the representative tag of :func:`family_groups`, computed here
#: unless the caller already holds ``groups``); wiring-device families load in
#: the LAST tier, so a device family that cannot be authored can only ever
#: cost devices, never the equipment before it
def _load_order(model: I.IntentModel,
                groups: Optional[Dict[str, List[str]]] = None) -> List[str]:
    plans = {t: model.plan_for(t) for t in (family_groups(model) if groups is None else groups)}
    # roots first: equipment whose feeder source is external (UTILITY/SERVICE)
    fed_by = {ed.target: ed.source for ed in model.feeders}
    depth: Dict[str, int] = {}

    def dep(tag: str, seen=()) -> int:
        if tag in depth:
            return depth[tag]
        src = fed_by.get(tag)
        if src is None or src not in plans or tag in seen:
            depth[tag] = 0
        else:
            depth[tag] = dep(src, seen + (tag,)) + 1
        return depth[tag]

    for t in plans:
        dep(t)
    return sorted(plans, key=lambda t: (_is_device_plan(plans[t]), depth[t], t))


def n_families(loaded: Dict[str, Any]) -> int:
    """Distinct FAMILIES in a stage-L ``loaded`` map (members of a shared
    device family count once)."""
    return sum(1 for d in loaded.values() if not d.get("shared_with"))


def _loaded_group(loaded: Dict[str, Any], groups: Dict[str, List[str]], rep: str,
                  info: Dict[str, Any]) -> None:
    """Record family ``rep`` as loaded for EVERY tag placed on it (stage E
    looks instances up by equipment tag): the representative's entry lists
    a shared family's ``tags``; each member's names it under ``shared_with``
    (the ONE place either field is written)."""
    loaded[rep] = {**info, **_group_tags(groups, rep)}
    for t in groups.get(rep, [rep])[1:]:
        loaded[t] = {**info, "shared_with": rep}


def stage_load(model: I.IntentModel, base_rvt: str, out_dir: str, *,
               symbol_solid: bool = True) -> Dict[str, Any]:
    """Chain the four-registry loader over every mapped family, each load
    onto the previous output.  Returns the stage record with the final path
    (or the deepest good file + the named blocker)."""
    from rvt.famgen import loader as L
    rec: Dict[str, Any] = {"stage": "L", "base": _relp(base_rvt), "loads": [],
                           "final": None, "blocker": None}
    groups = family_groups(model)
    order = _load_order(model, groups)
    current = os.path.join(out_dir, "stage_L0_base.rvt")
    shutil.copyfile(base_rvt, current)
    rec["order"] = order
    products: Dict[str, Any] = {}
    loaded: Dict[str, Any] = {}
    for i, tag in enumerate(order, 1):
        plan = model.plan_for(tag)
        nxt = os.path.join(out_dir, f"stage_L{i}_{tag.lower().replace('-', '')}.rvt")
        entry: Dict[str, Any] = {"tag": tag, "in": _relp(current), "out": _relp(nxt)}
        t0 = time.time()
        try:
            wm = host_watermark(current)
            prod = build_product(plan, start_id=wm + 1, solid=symbol_solid)
            products[tag] = prod
            res = L.load_family_into_project(current, nxt, product=prod, place=False,
                                            symbol_solid=symbol_solid,
                                            report_path=nxt + ".load.json",
                                            validate=False)
            entry.update({
                "ok": bool(res.ok), "stop_reason": res.stop_reason,
                "host_watermark": wm,
                "symbol_id": res.plan.symbol_id if res.plan else None,
                "family_id": res.plan.host_family_id if res.plan else None,
                "surrogate_id": res.plan.surrogate_id if res.plan else None,
                "content_guid": res.plan.guid if res.plan else None,
                "twins": len(res.plan.twin_of) if res.plan else None,
                "elements_added": len(res.elements),
                "proofs": _slim_proofs(res.proofs),
                "acceptance": res.acceptance,
                "seconds": round(time.time() - t0, 1),
                "report": _relp(nxt + ".load.json"),
            })
            if not res.ok:
                entry["blocker"] = res.stop_reason or "load returned ok=False"
                rec["loads"].append(entry)
                rec["blocker"] = f"{tag}: {entry['blocker']}"
                _log(f"L  {tag} FAILED: {entry['blocker']}")
                break
            entry.update(_group_tags(groups, tag))
            _loaded_group(loaded, groups, tag,
                          {"symbol_id": entry["symbol_id"], "family_id": entry["family_id"],
                           "content_guid": entry["content_guid"], "product": prod})
            current = nxt
            _log(f"L  {tag} loaded -> {os.path.basename(nxt)} (symbol {entry['symbol_id']}, "
                 f"family {entry['family_id']}, {entry['elements_added']} host elements, "
                 f"{entry['seconds']}s)")
        except Exception as e:
            entry.update({"ok": False, "error": f"{type(e).__name__}: {e}",
                          "traceback": traceback.format_exc(limit=8),
                          "seconds": round(time.time() - t0, 1)})
            rec["blocker"] = f"{tag}: {type(e).__name__}: {e}"
            rec["loads"].append(entry)
            _log(f"L  {tag} EXCEPTION: {type(e).__name__}: {e}")
            break
        rec["loads"].append(entry)
    rec["loaded"] = {t: {k: v for k, v in d.items() if k != "product"} for t, d in loaded.items()}
    rec["final"] = _relp(current) if loaded else None
    rec["n_loaded"] = n_families(loaded)
    rec["n_planned"] = len(order)
    rec["_products"] = products          # for stage E (not json-serialised)
    rec["_loaded"] = loaded
    rec["_current"] = current
    return rec


def _slim_proofs(proofs: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the load proofs small enough for the record."""
    keep = {}
    for k in ("plan", "roundtrip_gate", "save_unit", "content_documents",
              "adocument_reencode", "commit", "verify", "validate", "census"):
        if k in proofs:
            v = proofs[k]
            if isinstance(v, dict) and k == "plan":
                v = {kk: v[kk] for kk in ("content_guid", "host_watermark", "our_doc_ids", "host_ids")
                     if kk in v}
            keep[k] = v
    return keep


# ===========================================================================
# specimen scaffolding (from the base's own CERTIFIED ancestor)
# ===========================================================================

class SpecimenSet:
    """Placement scaffolding the family-free genesis base lacks: a straight
    SWall of the base's own wall type and a free-standing FamilyInstance,
    borrowed from the base's CERTIFIED ancestor (R5: the same lineage, ids
    continuous -- R5's wall type 600634 IS the wall type ZA_deep still
    carries, its levels / phase are the same elements).  The specimen
    records are used ONLY as clone templates for OUR new elements; they are
    never emitted themselves.
    """

    def __init__(self, source_path: str):
        from rvt.mutate import Document
        self.source_path = source_path
        _log(f"   loading specimen source {os.path.basename(source_path)} ...")
        self.doc = Document.from_file(source_path)
        self.wall_id: Optional[int] = None
        self.wall_type: Optional[int] = None
        self.instance_id: Optional[int] = None
        self.instance_symbol: Optional[int] = None
        self.instance_category: Optional[int] = None
        self.circuit_id: Optional[int] = None
        # a straight wall of any type (prefer the most-instanced type)
        wt = self.doc.wall_types_with_instances()
        if wt:
            best = max(wt.items(), key=lambda kv: len(kv[1]))[0]
            self.wall_type = best
            self.wall_id = self.doc._template_wall(best)
        # a real single-load circuit, when the source carries one
        try:
            self.circuit_id = self.doc._template_circuit()
        except LookupError:
            pass
        # a free-standing symbol==master instance -- prefer the CLEANEST
        # scaffolding: a placed MODEL instance (real level + phase) with NO
        # instance geometry-step history / rebar / cover cells / parameter
        # rows (the door-category record in the rst lineage: its only foreign
        # references are its own symbol / family, which the clone repoints).
        best = None
        for iid in self.doc.ids_of_class("FamilyInstance"):
            v = self.doc.value(iid) or {}
            ii = (v.get("m_pInstanceInfo") or {}).get("value") or {}
            free = (v.get("m_hostId") in (-1, None)) and not v.get("m_workPlaneBased")
            if not (free and ii.get("m_symbolId") == v.get("m_masterSymbolId")):
                continue
            placed = int(v.get("m_assocLevelId") or -1) > 0 and int(v.get("m_createdPhaseId") or -1) > 0
            s = json.dumps(v, default=str)
            baggage = (0 if v.get("m_geomSteps") is None else 4) \
                + (2 if "m_rebarIds" in s else 0) + (2 if "CoverSettingsCell" in s else 0) \
                + (1 if v.get("m_oFamInstUserData") else 0) \
                + (0 if v.get("m_pParamValueSetElementId") is None else 1)
            body = self.doc.record(iid).body_size
            score = ((0 if placed else 8) + baggage, body)
            if best is None or score < best[0]:
                best = (score, iid, ii.get("m_symbolId"))
        if best is not None:
            _score, iid, sym = best
            self.instance_id = iid
            self.instance_symbol = sym
            self.instance_category = self.doc.category_of(iid)
            self.instance_score = _score

    def inject_into(self, target) -> Dict[str, Any]:
        """Copy the specimen records (all three seqs) into ``target``'s
        record index so rvt.mutate can clone them (Formats/Latest is the
        per-release constant: the target's decoder decodes them)."""
        injected = []
        for eid in (self.wall_id, self.instance_id, self.circuit_id):
            if eid is None:
                continue
            for seq in (101, 102, 103):
                r = self.doc.idx[seq].get(eid)
                if r is not None:
                    target.idx[seq][eid] = r
            # drop any stale decode cache
            for seq in (101, 102, 103):
                target._decoded.pop((eid, seq), None)
            injected.append(eid)
        return {"source": _relp(self.source_path), "injected_ids": injected,
                "wall_specimen": self.wall_id, "wall_type": self.wall_type,
                "instance_specimen": self.instance_id,
                "instance_symbol": self.instance_symbol,
                "instance_category": self.instance_category,
                "circuit_specimen": self.circuit_id,
                "instance_specimen_score": getattr(self, "instance_score", None)}


# ===========================================================================
# STAGE W -- WALLS
# ===========================================================================

def _clean_wall_clone(el, doc, spec_id: int, mode: str = "min") -> Dict[str, Any]:
    """Repair what a joined-wall specimen leaves behind in OUR new wall.

    Every same-type specimen in the lineage (R5 / the rstbasic sample) is a
    JOINED, PAINTED wall, so the clone carries: (a) stable face-ref map
    entries whose ``m_geomRef.m_elemId`` name the SPECIMEN and whose
    ``m_setting`` names a paint ``CoverType`` element absent from this
    document, (b) ``WallJoinTweakGStep.m_affectedEdgesTags`` naming the
    specimen's partner walls, (c) join-end / split-face geometry steps and
    cached snapshots of the joined solid, (d) header parents naming the
    Walls-category ``GStyleElem`` (30) that the R9 lineage GC'd away.

    ``mode='min'`` = reference repair only (self-refs -> our id, paint map
    cleared, partner edge tags cleared, header parents filtered to existing
    ids); geometry history + snapshots KEPT (stale-but-tolerated, per the
    certified V22/V26 wall clones which kept their template's history).
    ``mode='unjoin'`` = min + the textbook UNJOINED history (form list =
    BaseWallGStep only, tweak list emptied, cached snapshots nulled -- the
    seq-103 rep is already SerializedDummy, so Revit regenerates the solid).
    """
    log: Dict[str, Any] = {"mode": mode}
    obj = el.obj
    new_id = int(el.elem_id)
    # (a) stable face-ref overrides (paint / split faces) -> none
    cells = ((obj.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
    cleared = 0
    for c in cells:
        cv = c.get("value") if isinstance(c, dict) else None
        if isinstance(cv, dict) and cv.get("m_stableFaceRefsMap"):
            cleared += len(cv["m_stableFaceRefsMap"])
            cv["m_stableFaceRefsMap"] = []
    log["face_ref_overrides_cleared"] = cleared
    # (b) join tweak partner tags + healing parents -> empty
    gsv = ((obj.get("m_geomSteps") or {}).get("value") or {})
    tags_cleared = 0
    for s in gsv.get("m_bRepTweakGList") or []:
        sv = s.get("value") if isinstance(s, dict) else None
        if isinstance(sv, dict):
            if s.get("ptr_class") == "WallJoinTweakGStep":
                tags_cleared += len(sv.get("m_affectedEdgesTags") or [])
                sv["m_affectedEdgesTags"] = []
                sv["m_idGeomJoined"] = []
                sv["m_healingParents"] = []
    log["join_edge_tags_cleared"] = tags_cleared
    # (c) any residual reference to the specimen id -> our id (belt & braces
    #     over rvt.mutate's own _remap_ids)
    def walk(v) -> int:
        n = 0
        if isinstance(v, dict):
            for k, x in list(v.items()):
                if isinstance(x, int) and not isinstance(x, bool) and x == spec_id \
                        and ("Id" in k or "_id" in k or k in ("m_tag", "m_id", "first", "second")):
                    v[k] = new_id
                    n += 1
                else:
                    n += walk(x)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, int) and not isinstance(x, bool) and x == spec_id:
                    v[i] = new_id
                    n += 1
                else:
                    n += walk(x)
        return n
    log["specimen_self_refs_repointed"] = walk(obj)
    # (d) header parents restricted to elements that EXIST here
    hdr = el.header
    parents = ((hdr.get("m_parents") or {}).get("value")) or {}
    for key in ("m_regenOnly", "m_appearanceParents", "m_dependencyParents",
                "m_deferredParents", "m_deferredPropagationParents"):
        lst = parents.get(key)
        if isinstance(lst, list):
            keep = [i for i in lst if not (isinstance(i, int) and i > 0 and not doc.exists(i))]
            if len(keep) != len(lst):
                log.setdefault("header_parents_dropped", {})[key] = [i for i in lst if i not in keep]
                parents[key] = keep
    # deletion set: existing ids only (our id + level + type stay)
    dele = parents.get("m_deletion")
    if isinstance(dele, list):
        keep = [i for i in dele if not (isinstance(i, int) and i > 0 and i != new_id
                                          and not doc.exists(i))]
        if len(keep) != len(dele):
            log.setdefault("header_parents_dropped", {})["m_deletion"] = [i for i in dele if i not in keep]
            parents["m_deletion"] = keep
    if mode == "unjoin":
        # (e) textbook unjoined history
        form = gsv.get("m_bRepFormGList") or []
        keepf = [s for s in form if isinstance(s, dict) and s.get("ptr_class") == "BaseWallGStep"]
        log["form_steps_removed"] = [s.get("ptr_class") for s in form
                                     if not (isinstance(s, dict) and s in keepf)]
        gsv["m_bRepFormGList"] = keepf
        tweak = gsv.get("m_bRepTweakGList") or []
        log["tweak_steps_removed"] = [s.get("ptr_class") for s in tweak if isinstance(s, dict)]
        gsv["m_bRepTweakGList"] = []
        nulled = []
        for k in ("m_bRepFormSnapshot", "m_bRepAdjustSnapshot",
                  "m_bRepCutOutSnapshot", "m_bRepPostCutOutSnapshot"):
            if gsv.get(k) is not None:
                gsv[k] = None
                nulled.append(k)
        log["snapshots_nulled"] = nulled
    return log


#: stage-record note per created-wall seq-103 rep (mechanism only; the
#: certification wording lives in rvt.frontdoor.manifest.LOAD_VS_RENDER)
WALL_REP_NOTE = {
    "solid": ("wall geometry rep = AUTHORED seq-103 GElement solid per wall "
              "(rvt.render.brep.bake_planned_wall, the W1_gabpd_wall_solid recipe; "
              "per-wall facts under 'rep')"),
    "dummy": ("wall geometry rep = SerializedDummy (Revit regenerates the solid from "
              "the type + location line; the certified T2/T3/V22/V26 wall path; the "
              "cloud viewer draws nothing)"),
}


def _pick_level(doc, want_elev_ft: float = 0.0) -> int:
    from rvt.frontdoor.levels import story_levels
    best = min(story_levels(doc), key=lambda l: abs(float(l.get("elevation_ft", 0.0)) - want_elev_ft))
    return int(best["id"])


def _wall_type_of_base(doc) -> Optional[int]:
    ids = doc.ids_of_class("BasicWallType")
    return int(ids[0]) if ids else None


def stage_walls(model: I.IntentModel, src_rvt: str, out_path: str,
                specimens: SpecimenSet, *, level_id: Optional[int] = None,
                wall_mode: str = "min",
                wall_rep: str = "dummy") -> Tuple[Dict[str, Any], Optional[str]]:
    """Add the room's walls to ``src_rvt`` -> ``out_path``.  ``wall_mode``:
    'min' (reference repair, history kept), 'unjoin' (textbook unjoined
    history), 'raw' (no clean-up: the specimen clone as rvt.mutate leaves it).
    ``wall_rep``: 'solid' (authored seq-103 GElement via
    ``rvt.render.brep.bake_planned_wall``; the front door's default through
    ``BuildOptions.wall_rep``) or 'dummy' (SerializedDummy rep -- the research
    probe builders' unchanged default, so their outputs stay byte-identical)."""
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements, verify_written
    from rvt.render.brep import WALL_REPS, bake_planned_wall
    if wall_rep not in WALL_REPS:
        raise ValueError(f"unknown wall_rep {wall_rep!r} (want one of {WALL_REPS})")
    rec: Dict[str, Any] = {"stage": "W", "in": _relp(src_rvt), "out": _relp(out_path),
                           "wall_mode": wall_mode, "wall_rep": wall_rep, "walls": [],
                           "ok": False}
    if not model.room or not model.room.walls:
        rec["blocker"] = "the intent carries no room walls"
        return rec, None
    t0 = time.time()
    try:
        doc = Document.from_file(src_rvt)
        rec["specimens"] = specimens.inject_into(doc)
        wt = _wall_type_of_base(doc)
        if wt is None:
            rec["blocker"] = "the base carries no BasicWallType to type the walls"
            return rec, None
        rec["wall_type"] = wt
        lvl = level_id if level_id is not None else _pick_level(doc, 0.0)
        rec["level"] = lvl
        # the base wall type's real thickness (informational: the IFC shell
        # says 0.2 m; the built wall uses the TYPE's compound structure)
        try:
            wtv = doc.value(wt) or {}
            rec["wall_type_name"] = ((wtv.get("m_symbolInfo") or {}).get("value") or {}).get("m_name")
        except Exception:
            pass
        spec_wall = specimens.wall_id
        if spec_wall is None:
            rec["blocker"] = ("no SWall specimen available (family-free base + no ancestor "
                              "wall): rvt.mutate.add_wall clones a specimen -- an SWall "
                              "CONSTRUCTOR is the missing piece")
            return rec, None
        els = []
        for w in model.room.walls:
            p0 = (w.p0_m[0] * FT_PER_M, w.p0_m[1] * FT_PER_M)
            p1 = (w.p1_m[0] * FT_PER_M, w.p1_m[1] * FT_PER_M)
            h = w.height_m * FT_PER_M
            el = doc.add_wall(lvl, wt, p0, p1, height=h, template_id=spec_wall)
            clean = ({} if wall_mode == "raw"
                     else _clean_wall_clone(el, doc, spec_wall, mode=wall_mode))
            rep = (bake_planned_wall(doc, el, wall_type_id=wt, height=h)
                   if wall_rep == "solid" else None)
            dangling = doc.check_references(el)
            els.append(el)
            rec["walls"].append({
                "id": w.wall_id, "elem_id": el.elem_id, "synthesized": w.synthesized,
                "p0_ft": [round(p0[0], 3), round(p0[1], 3)],
                "p1_ft": [round(p1[0], 3), round(p1[1], 3)],
                "height_ft": round(h, 3), "length_m": round(w.length_m, 3),
                "ifc_thickness_m": w.thickness_m,
                "openings": [o.as_json() for o in w.openings],
                "clone_cleanup": clean,
                "rep": rep,
                "dangling_refs": dangling[:12], "n_dangling": len(dangling),
                "notes": el.notes,
            })
            _log(f"W  {w.wall_id:4s} elem {el.elem_id} {p0} -> {p1} ft h={h:.2f} "
                 f"(dangling refs {len(dangling)}, mode {wall_mode}, rep {wall_rep})")
        # serialize + commit
        records, plans = [], []
        for el in els:
            recs = doc.serialize(el)
            if recs is None:
                raise RuntimeError("rvt.encode not available: cannot serialize walls")
            records.append(dict(recs))
            plans.append(el.elemrec)
        crep = commit_new_elements(src_rvt, out_path, records, plans)
        ids = [p.elem_id for p in plans]
        ver = verify_written(out_path, ids)
        rec.update(_commit_summary(crep, ver, ids))
        rec["ok"] = bool(rec["structurally_valid"])
        rec["seconds"] = round(time.time() - t0, 1)
        rec["notes"] = [
            WALL_REP_NOTE[wall_rep],
            "wall LOCATION LINES are the intent's centerline ring (metres -> feet); "
            "the built thickness is the base wall type's compound structure, not the "
            "IFC's 0.2 m (recorded per wall as ifc_thickness_m)",
            "door OPENINGS are recorded in the intent but NOT cut (no door family / "
            "hosting in v1)",
            f"specimen scaffolding: SWall {spec_wall} cloned from the base's certified "
            f"ancestor {os.path.basename(specimens.source_path)} (same wall type id "
            f"{wt} in both files; the specimen is a clone TEMPLATE, never emitted)",
            "EVERY same-type specimen in the lineage is a JOINED, painted wall -> the "
            f"clone clean-up mode '{wall_mode}' repairs what the clone leaves behind "
            "(per-wall log 'clone_cleanup'): self face-refs repointed, paint face-ref "
            "overrides cleared, join partner edge tags cleared, header parents filtered "
            "to existing ids (the Walls-category GStyle row 30 is one of the 235 catalog "
            "rows the R9 lineage GC'd away -- our headers must not name it); 'unjoin' "
            "additionally trims the history to the textbook unjoined form",
            "OPEN acceptance question this probe answers: placed walls in a file whose "
            "Walls-category projection GStyle row is absent (never before tested -- the "
            "base lineage has no walls); a FAIL here + a card message points at the "
            "ADD-cat rung (the 235 missing built-in category rows)",
        ]
        return rec, out_path if rec["ok"] else None
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc(limit=10)
        rec["seconds"] = round(time.time() - t0, 1)
        _log(f"W  EXCEPTION: {type(e).__name__}: {e}")
        return rec, None


def _commit_summary(crep, ver: dict, ids: Sequence[int]) -> Dict[str, Any]:
    found = {s: sum(1 for x in ver["new_ids_found"][s].values() if x.get("clean"))
             for s in (101, 102, 103)}
    ok = (ver.get("crc_failures") == 0 and ver.get("ecc_mismatches") == 0
          and ver.get("walker_errors") == 0 and ver.get("stamps_ok")
          and all(n == len(ids) for n in found.values()))
    return {
        "elemtable_before": getattr(crep, "elemtable_count_before", None),
        "elemtable_after": getattr(crep, "elemtable_count_after", None),
        "new_ids": list(ids),
        "verify": {"crc_failures": ver.get("crc_failures"),
                   "ecc_mismatches": ver.get("ecc_mismatches"),
                   "walker_errors": ver.get("walker_errors"),
                   "stamps_ok": ver.get("stamps_ok"),
                   "elemtable_matches_header": ver.get("elemtable_count") == ver.get("header_count"),
                   "sentinels_last": all(ver.get("sentinel_last", {}).values())
                   if isinstance(ver.get("sentinel_last"), dict) else ver.get("sentinel_last"),
                   "new_elements_clean_per_seq": found},
        "structurally_valid": bool(ok),
    }


# ===========================================================================
# STAGE E -- EQUIPMENT INSTANCES
# ===========================================================================

def _connector_manager_for(product, circuit_slots: int) -> dict:
    """Our connectors (+ per-feeder panel slots) as the instance connector
    manager, via the loader's own slot builder (unconnected)."""
    from rvt.famgen import loader as L
    facts = L._connector_facts(product)                    # noqa: SLF001 (stable helper)
    slots = [L._connector_slot(int(c.get("index") or 1))   # noqa: SLF001
             for c in facts.get("connectors") or []]
    for k in range(int(circuit_slots)):
        slots.append(L._connector_slot(50000 + k))         # noqa: SLF001
    return {"ptr_class": "FamilyInstanceConnectorManager", "pid": -1,
            "value": {"m_setDeletedConnectors": [], "m_connPtrArray": slots,
                      "m_modifiers": []}}


def _apply_frame(el, frame3x3: List[List[float]], origin_ft: Sequence[float]) -> None:
    """Overwrite a cloned instance's placement transform (both the object's
    InstanceInfo and the cached GElement rep) with the intent's frame."""
    trf = {"m_3x3": [list(map(float, r)) for r in frame3x3],
           "m_or": [float(x) for x in origin_ft]}
    ii = ((el.obj.get("m_pInstanceInfo") or {}).get("value")) or {}
    ii["m_Trf"] = trf
    if el.rep is not None:
        for node in el.rep.get("m_subNodes") or []:
            nv = node.get("value") or {}
            info = ((nv.get("m_instanceInfo") or {}).get("value")) or {}
            if info:
                info["m_Trf"] = copy.deepcopy(trf)


def _scrub_instance(el, doc, *, our_symbol: int, our_family: Optional[int],
                    spec_symbol: Optional[int], spec_category: Optional[int],
                    category: int) -> Dict[str, Any]:
    """Repoint / drop what a cross-category specimen clone leaves behind:
    header category -> ours; residual references to the specimen's symbol ->
    our symbol; parameter-set rows keyed by ParamElem ids that do not exist
    in this document -> dropped (an instance may not name a parameter the
    document does not carry).  Every action is logged."""
    log: Dict[str, Any] = {"category_patched": False, "symbol_refs_repointed": 0,
                           "param_rows_dropped": 0, "structural_fields_reset": []}
    # 1. header category
    hdr = el.header
    if hdr.get("m_categroryId") not in (None, category):
        log["category_from"] = hdr.get("m_categroryId")
        hdr["m_categroryId"] = category
        log["category_patched"] = True
    # 2. residual specimen-symbol references anywhere in the three records
    def walk(v):
        n = 0
        if isinstance(v, dict):
            for k, x in list(v.items()):
                if isinstance(x, int) and spec_symbol is not None and x == spec_symbol:
                    v[k] = our_symbol
                    n += 1
                else:
                    n += walk(x)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, int) and spec_symbol is not None and x == spec_symbol:
                    v[i] = our_symbol
                    n += 1
                else:
                    n += walk(x)
        return n
    n = walk(el.obj) + walk(el.header) + (walk(el.rep) if el.rep is not None else 0)
    log["symbol_refs_repointed"] = n
    # 3. param-set rows keyed by non-existent (specimen-document) ParamElem ids
    dropped = 0
    for set_name in ("m_pParamValueSetDouble", "m_pParamValueSetInt",
                     "m_pParamValueSetString", "m_pParamValueSetElementId"):
        holder = el.obj.get(set_name)
        vals = (holder.get("value") if isinstance(holder, dict) else None)
        if not isinstance(vals, dict):
            continue
        rows = vals.get("m_values") or vals.get("m_params") or None
        key = "m_values" if "m_values" in vals else ("m_params" if "m_params" in vals else None)
        if not isinstance(rows, list) or key is None:
            continue
        keep = []
        for r in rows:
            rv = r.get("value") if isinstance(r, dict) and "value" in r else r
            pid = None
            if isinstance(rv, dict):
                pid = rv.get("m_paramId", rv.get("first"))
            elif isinstance(r, (list, tuple)) and r:
                pid = r[0]
            if isinstance(pid, int) and pid > 0 and not doc.exists(pid):
                dropped += 1
                continue
            keep.append(r)
        if dropped:
            vals[key] = keep
    log["param_rows_dropped"] = dropped
    # 4. class-specific leftovers of the specimen an electrical-equipment
    #    instance does not carry: structural analysis pointers, a door /
    #    window / stair FamInstSpec, per-face cover-paint overrides
    for fld in ("m_pStructuralInfo", "m_analyticalModelId"):
        if fld in el.obj and el.obj[fld] not in (None, -1):
            el.obj[fld] = None if fld == "m_pStructuralInfo" else -1
            log["structural_fields_reset"].append(fld)
    spec = el.obj.get("m_oFamInstSpec")
    if isinstance(spec, dict) and str(spec.get("ptr_class", "")).startswith(("FamInstDoor",
                                                                             "FamInstWindow",
                                                                             "FamInstStair")):
        log["faminst_spec_removed"] = spec.get("ptr_class")
        el.obj["m_oFamInstSpec"] = None
    cells = ((el.obj.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
    cleared = 0
    for c in cells:
        cv = c.get("value") if isinstance(c, dict) else None
        if isinstance(cv, dict) and cv.get("m_stableFaceRefsMap"):
            cleared += len(cv["m_stableFaceRefsMap"])
            cv["m_stableFaceRefsMap"] = []
    if cleared:
        log["face_ref_overrides_cleared"] = cleared
    return log


NO_CIRCUIT_SPECIMEN = (
    "NO CIRCUIT SPECIMEN in the base or the specimen set (rvt.mutate.add_circuit "
    "clones one; the constructed RbsElectricalSystem template is absent) -- the "
    "resolved feeder plan rides in the manifest instead")


#: the ORCHESTRATOR-level name (build_room / the front door own ``--stages``)
#: for stage E's neutral ``circuits_requested: False`` (its caller opted out)
STAGE_C_NOT_REQUESTED = (
    "stage C (circuits) NOT requested (--stages lacks 'C'): the feeder edges stay a "
    "plan in the intent; no RbsElectricalSystem is authored")
CIRCUITS_NOT_REQUESTED_REASON = "circuits not requested by the caller"


def _feeder_voltage_v(text: Any) -> Optional[float]:
    """Line-to-line volts of a feeder edge's voltage text ('480Y/277 V')."""
    return (float(I.parse_voltage(text).get("ll") or 0) or None) if text else None


def circuit_edges(model: I.IntentModel) -> List[Any]:
    """The feeder edges that become circuits (a service entrance is not one)."""
    return [ed for ed in model.feeders if ed.kind != "service"]


def _feeders_unwired(edges: Sequence[Any] = (), reason: Optional[str] = None,
                     blocker: Optional[str] = None) -> Dict[str, Any]:
    """A FRESH feeder record with no circuit wired -- a new dict and new lists
    per call: stage E ``update``s it into its own record and appends to those
    lists, so a shared module-level default would leak between builds.  With
    ``edges``, every one lands in ``circuits_skipped`` for ``reason``;
    ``blocker`` (if any) names what BLOCKED the wiring."""
    return {"circuits": [],
            "circuits_skipped": [{"panel": ed.source, "load": ed.target, "reason": reason}
                                 for ed in edges],
            "circuits_blocker": blocker if edges else None,
            "circuit_template": None}


def wire_feeders(doc, model: I.IntentModel, placed: Dict[str, Any],
                 circuit_template: Optional[int]) -> Tuple[Dict[str, Any], List[Any]]:
    """The feeder CIRCUITS, wired onto the instances ``placed`` ({tag:
    NewElement}) in THIS commit: one ``rvt.mutate.add_circuit(panel, load)``
    per non-service feeder edge whose two ends were both placed, cloned from
    ``circuit_template`` (the constructed RbsElectricalSystem specimen, or a
    real one the specimen source carries).  Circuit numbers / start slots
    follow Revit's two-column same-parity packing rule per panel
    (``rvt.mep.electrical_data.layout_circuits``).  Returns ``(record,
    elements)``: the record keys ``stage_equipment`` merges (circuits /
    circuits_skipped / circuits_blocker / circuit_template) and the circuit
    NewElements the caller serialises with the instances."""
    from rvt.mep.electrical_data import connectors, layout_circuits
    made: List[Any] = []
    edges = circuit_edges(model)
    if edges and circuit_template is None:
        return _feeders_unwired(edges, "no circuit template", blocker=NO_CIRCUIT_SPECIMEN), made
    rec = {**_feeders_unwired(), "circuit_template": circuit_template}
    # per-panel schedule layout (number / start slot), in edge order
    layout: Dict[Tuple[str, str], dict] = {}
    for src in dict.fromkeys(ed.source for ed in edges):
        for row in layout_circuits([{"key": (ed.source, ed.target), "poles": ed.poles or 3}
                                    for ed in edges if ed.source == src]):
            layout[row["key"]] = row
    for ed in edges:
        panel, load = placed.get(ed.source), placed.get(ed.target)
        if panel is None or load is None:
            rec["circuits_skipped"].append({
                "panel": ed.source, "load": ed.target,
                "reason": ("panel" if panel is None else "load")
                          + " not placed (family not loaded / not in the intent)"})
            continue
        lay = layout[(ed.source, ed.target)]
        volts = _feeder_voltage_v(ed.voltage)
        el = doc.add_circuit(panel, load, number=lay["new_number"],
                             start_slot=lay["new_start_slot"],
                             description=f"{ed.target} feeder from {ed.source}",
                             rating=ed.rating_a, poles=ed.poles, voltage_v=volts,
                             template_id=circuit_template)
        own = connectors(el.obj)                     # {0: [(load, conn, 1)], LAST: [(panel, slot, 4)]}
        load_conn, panel_slot = own[0][0][1], own[max(own)][0][1]
        made.append(el)
        rec["circuits"].append({
            "kind": "circuit", "elem_id": el.elem_id,
            "panel": ed.source, "panel_id": panel.elem_id, "panel_slot": panel_slot,
            "load": ed.target, "load_id": load.elem_id, "load_conn": load_conn,
            "number": lay["new_number"], "start_slot": lay["new_start_slot"],
            "slots": lay["new_slots"], "poles": ed.poles, "rating_a": ed.rating_a,
            "voltage": ed.voltage, "voltage_v": volts, "edge_kind": ed.kind,
            "length_ft": round(float(el.obj.get("m_dLength") or 0.0), 3),
            "notes": el.notes,
        })
        _log(f"C  circuit {el.elem_id}: {ed.source} slot {panel_slot} -> {ed.target} "
             f"conn {load_conn} ({lay['new_number']}, {ed.rating_a} A, {ed.poles} P)")
    return rec, made


def _instance_labels(eq: Any, category: int) -> Dict[str, Any]:
    """The manifest-facing labels of a placed instance, decided HERE by the
    one producer (every harvester copies them): ``created_kind`` by header
    category; a wiring device also carries its schedule pset as ``schedule``
    (one device-schedule row per placed device)."""
    if category != OST_ELECTRICAL_FIXTURES:
        return {"created_kind": "equipment-instance"}
    return {"created_kind": "fixture-instance",
            "schedule": dict((eq.psets or {}).get(I.DEVICE_PSET) or {})}


def stage_equipment(model: I.IntentModel, src_rvt: str, out_path: str,
                    specimens: SpecimenSet, loaded: Dict[str, Any], *,
                    level_id: Optional[int] = None,
                    level_ids: Optional[Dict[str, Tuple[int, float]]] = None,
                    circuits: bool = False,
                    ) -> Tuple[Dict[str, Any], Optional[str]]:
    """Place one instance of each loaded family at the intent's insertion /
    frame -> ``out_path``.  The intent's z is WORLD (``rvt.ifc.intent
    .level_elevation`` contract): every instance lands at its world z;
    ``level_ids`` (``rvt.frontdoor.levels.LevelMap`` + its ``""`` fallback)
    only chooses the DATUM each item associates to (``m_assocLevelId`` = its
    ``Equipment.level``'s datum, level-less items the datum nearest 0);
    without a map (research probes, add_to_project) every item lands on
    ``level_id`` (else the story datum nearest 0).

    ``circuits=True`` (the build's stage C) wires the feeder tree in the SAME
    commit (:func:`wire_feeders` over ``specimens.circuit_id``):
    ``rec["circuits"]`` lists them; a missing circuit template is
    ``rec["circuits_blocker"]``, never a stage failure (the instances still
    land).  ``circuits=False`` records ``rec["circuits_requested"] = False``
    with every feeder edge in ``circuits_skipped`` (reason
    :data:`CIRCUITS_NOT_REQUESTED_REASON`) -- a neutral opt-out, no blocker;
    the orchestrator that owns ``--stages`` words it (:data:`STAGE_C_NOT_REQUESTED`)
    so the manifest never goes silent about a plan it did not wire."""
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements, verify_written
    from rvt.frontdoor.levels import resolve as resolve_level
    rec: Dict[str, Any] = {"stage": "E", "in": _relp(src_rvt), "out": _relp(out_path),
                           "instances": [], "ok": False}
    t0 = time.time()
    try:
        doc = Document.from_file(src_rvt)
        rec["specimens"] = specimens.inject_into(doc)
        lvl = level_id if level_id is not None else _pick_level(doc, 0.0)
        rec["level"] = lvl
        lvl_z = float(doc._level_elevation(lvl))          # no-map callers: offsets vs this datum
        tpl = specimens.instance_id
        if tpl is None:
            rec["blocker"] = ("no free-standing FamilyInstance specimen (family-free base + "
                              "no ancestor instance): rvt.mutate.add_family_instance clones "
                              "the placement scaffolding -- a FamilyInstance CONSTRUCTOR is "
                              "the missing piece")
            return rec, None
        # outgoing feeder count per board -> panel circuit slots
        out_edges: Dict[str, int] = {}
        for ed in model.feeders:
            out_edges[ed.source] = out_edges.get(ed.source, 0) + 1
        from rvt.famgen.loader import product_category
        from rvt.famgen.skeleton import category_label
        els = []
        placed: Dict[str, Any] = {}
        for eq in model.equipment:
            if eq.tag not in loaded:
                continue
            info = loaded[eq.tag]
            sym = int(info["symbol_id"])
            fam = info.get("family_id")
            prod = info.get("product")
            cat = product_category(prod) if prod is not None else OST_ELECTRICAL_EQUIPMENT
            ins = eq.insertion_m
            eq_lvl, datum_ft = resolve_level(level_ids, eq.level, (lvl, lvl_z))
            pos_ft = (ins[0] * FT_PER_M, ins[1] * FT_PER_M, ins[2] * FT_PER_M)   # world
            yaw = math.radians(float(eq.yaw_deg))
            el = doc.add_family_instance(sym, eq_lvl, position=pos_ft, rotation=yaw,
                                         template_instance_id=tpl)
            # the intent's full frame (wall gear stands UPRIGHT: a work-plane
            # family free-placed with an explicit 3x3; floor gear = yaw)
            _apply_frame(el, eq.frame3x3, pos_ft)
            # our connectors (+ per-feeder panel slots) instead of the specimen's
            n_slots = out_edges.get(eq.tag, 0)
            if prod is not None:
                el.obj["m_pConnectorManager"] = _connector_manager_for(prod, n_slots)
            scrub = _scrub_instance(el, doc, our_symbol=sym, our_family=fam,
                                    spec_symbol=specimens.instance_symbol,
                                    spec_category=specimens.instance_category,
                                    category=cat)
            dangling = doc.check_references(el)
            els.append(el)
            placed[eq.tag] = el
            rec["instances"].append({
                "tag": eq.tag, "kind": eq.kind, "category": cat, **_instance_labels(eq, cat),
                "elem_id": el.elem_id, "symbol": sym, "family": fam,
                "shared_with": info.get("shared_with"),
                "position_ft": [round(x, 3) for x in pos_ft],
                "position_m": [round(x, 4) for x in ins],
                "level": eq.level, "level_id": eq_lvl,
                "z_above_level_ft": round(pos_ft[2] - datum_ft, 3),
                "yaw_deg": eq.yaw_deg, "frame_kind": eq.frame_kind,
                "frame3x3": eq.frame3x3, "connector_slots_panel": n_slots,
                "scrub": scrub, "dangling_refs": dangling[:16],
                "n_dangling": len(dangling), "notes": el.notes,
            })
            _log(f"E  {eq.tag:5s} elem {el.elem_id} symbol {sym} cat {cat} at "
                 f"{[round(x,2) for x in pos_ft]} ft on level {eq_lvl} {eq.frame_kind} "
                 f"(dangling refs {len(dangling)}, dropped rows {scrub['param_rows_dropped']})")
        # the feeder CIRCUITS, wired onto the just-placed boards pre-serialise
        # (both back-links live in the instances' connector objects)
        crec, cels = (wire_feeders(doc, model, placed, specimens.circuit_id) if circuits
                      else (_feeders_unwired(circuit_edges(model), CIRCUITS_NOT_REQUESTED_REASON), []))
        rec.update(crec, circuits_requested=circuits)
        for cel, crow in zip(cels, rec["circuits"]):
            crow["n_dangling"] = len(doc.check_references(cel))
        els.extend(cels)
        records, plans = [], []
        for el in els:
            recs = doc.serialize(el)
            if recs is None:
                raise RuntimeError("rvt.encode not available: cannot serialize instances")
            records.append(dict(recs))
            plans.append(el.elemrec)
        crep = commit_new_elements(src_rvt, out_path, records, plans)
        ids = [p.elem_id for p in plans]
        ver = verify_written(out_path, ids)
        rec.update(_commit_summary(crep, ver, ids))
        rec["ok"] = bool(rec["structurally_valid"])
        rec["instances_by_category"] = dict(collections.Counter(
            category_label(i["category"]) for i in rec["instances"]))
        rec["seconds"] = round(time.time() - t0, 1)
        rec["notes"] = [
            "placement = FREE-STANDING at the intent's insertion point with the intent's "
            "full frame (wall panels AND wiring devices stand upright via an explicit 3x3, "
            "the family XY on the wall's interior face; the free-standing wall-family "
            "precedent = the certified V23..V29 clones); FACE-HOSTING on the created walls "
            "(rvt.hosting SketchPlane recipe, certified H2 / rvt.mep.devices dummy planes) "
            "is the fidelity follow-up",
            "each instance points at OUR loaded symbol (symbol == masterSymbol) with OUR "
            "connector set (+ one 50000-series slot per outgoing feeder); devices sharing "
            "one family point at the SAME symbol",
            f"feeder circuits in the SAME commit: {len(rec['circuits'])} RbsElectricalSystem "
            f"(template {rec.get('circuit_template')}), {len(rec['circuits_skipped'])} skipped"
            + ("" if circuits else f" -- {CIRCUITS_NOT_REQUESTED_REASON} (circuits=False)")
            + (f" -- blocker: {rec['circuits_blocker']}" if rec.get("circuits_blocker") else ""),
            f"specimen scaffolding: instance {tpl} (category {specimens.instance_category}) "
            f"cloned from the base's certified ancestor "
            f"{os.path.basename(specimens.source_path)}; header category patched to each "
            f"instance's OWN family category ({rec['instances_by_category']}), "
            "specimen-symbol refs repointed, param rows keyed by other-document ParamElems "
            "dropped, structural-analysis leftovers reset (per-instance scrub log recorded)",
        ]
        return rec, out_path if rec["ok"] else None
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc(limit=10)
        rec["seconds"] = round(time.time() - t0, 1)
        _log(f"E  EXCEPTION: {type(e).__name__}: {e}")
        return rec, None


# ===========================================================================
# STAGE C -- CIRCUITS (feeder tree)
# ===========================================================================

def read_back_circuits(path: str) -> Dict[str, Any]:
    """READ BACK every ``RbsElectricalSystem`` committed into ``path`` and
    verify the circuit reference closure on the written bytes: the base
    connector names {self, LAST} (``rvt.validate.check_circuits``);
    conn[LAST] -> a panel slot whose connector points back {circuit, LAST};
    every member conn[i] -> a load connector that points back {circuit, i}.
    Pure readback -- the file is the truth."""
    from rvt.mep.electrical_data import connectors
    from rvt.mutate import Document
    from rvt.validate import check_circuits
    doc = Document.from_file(path)

    def _end(cid: int, i: int, ref: Tuple[int, int, int]) -> Dict[str, Any]:
        """One circuit connector's far end + whether it links back {cid, i}."""
        tid, tix, ctype = ref
        back = connectors(doc.value(tid) or {}).get(tix, []) if doc.exists(tid) else []
        return {"id": tid, "index": tix, "conn_type": ctype,
                "back_link": any(b[:2] == (cid, i) for b in back)}

    rows = []
    for cid in sorted(doc.ids_of_class("RbsElectricalSystem")):
        v = doc.value(cid) or {}
        own = connectors(v)
        idx = sorted(own)
        ends = {i: _end(cid, i, own[i][0]) if own[i] else None for i in idx}
        panel = ends.get(idx[-1]) if idx else None
        loads = [ends[i] for i in idx[:-1]]
        base_ok = not check_circuits([(cid, v)], {cid: own})
        rows.append({
            "elem_id": cid, "number": v.get("m_number"), "start_slot": v.get("m_nStartSlot"),
            "poles": v.get("m_nPoles"), "rating_a": v.get("m_dRating"),
            "connectors": idx, "base_ok": base_ok, "panel": panel, "loads": loads,
            "ok": bool(base_ok and panel and panel["back_link"] and loads
                       and all(l and l["back_link"] for l in loads)),
        })
    return {"path": _relp(path), "circuits": rows, "n": len(rows),
            "links_ok": all(r["ok"] for r in rows)}


def _circuit_shortfall(planned: int, built: int, equipment: Optional[Dict[str, Any]]) -> str:
    """Why the deepest file carries ``built`` != ``planned`` circuits, named
    from stage E's OWN record (the stage that wires them) -- never a guess:
    E did not run / did not commit, E's caller opted out of circuits
    (``circuits_requested`` False = ``--stages`` without C), E's
    ``circuits_blocker`` (no circuit specimen), or the edges it skipped for
    an unplaced end."""
    head = f"{built} of {planned} feeder circuits in the deepest file"
    if equipment is None:
        return (f"{head}: stage E (equipment placement) did not run -> no board "
                "instance exists to wire")
    if not equipment.get("ok"):                          # skipped, blocked, crashed, invalid
        why = (equipment.get("reason") or equipment.get("blocker") or equipment.get("error")
               or "output not structurally valid")
        return (f"{head}: stage E did not commit its instances (+ circuits): {why} "
                "-> nothing wired survives in the deepest file")
    if not equipment.get("circuits_requested", True):
        return f"{head}: {STAGE_C_NOT_REQUESTED}"
    if equipment.get("circuits_blocker"):
        return f"{head}: {equipment['circuits_blocker']}"
    skipped = equipment.get("circuits_skipped") or []
    if skipped:
        return (f"{head}: {len(skipped)} feeder edge(s) skipped in stage E for an UNPLACED "
                "end -- " + "; ".join(f"{s.get('panel')}>{s.get('load')}: {s.get('reason')}"
                                      for s in skipped))
    return (f"{head}: stage E wired {len(equipment.get('circuits') or [])} in its commit "
            "but the readback disagrees -- see readback.circuits")


def stage_circuits(model: I.IntentModel, src_rvt: str,
                   equipment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The circuit READBACK stage.  Stage E wires the feeder circuits in its
    own commit; this stage re-opens the deepest file and checks the written
    truth against the plan: ``ids_of_class('RbsElectricalSystem')`` == the
    non-service feeder edges, and every circuit's both-side back-links
    (:func:`read_back_circuits`).  A shortfall is NAMED (``blocker``) with
    the resolved plan riding along -- never faked -- and the name is the REAL
    cause read off ``equipment`` (stage E's record: :func:`_circuit_shortfall`),
    not a blanket 'no circuit specimen'."""
    rec: Dict[str, Any] = {"stage": "C", "in": _relp(src_rvt), "ok": False,
                           "circuits_planned": [ed.as_json()["circuitPlan"]
                                                for ed in circuit_edges(model)]}
    planned = len(rec["circuits_planned"])
    try:
        rb = read_back_circuits(src_rvt)
    except Exception as e:                                  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["blocker"] = f"circuit readback crashed: {rec['error']}"
    else:
        rec.update(readback=rb, circuits_built=rb["n"], links_ok=rb["links_ok"])
        rec["ok"] = rb["n"] == planned and rb["links_ok"]
        if not rec["ok"]:
            rec["blocker"] = (
                _circuit_shortfall(planned, rb["n"], equipment) if rb["n"] != planned else
                "circuit reference closure INCOMPLETE on readback (a one-way connector "
                "link) -- see readback.circuits")
    rec["notes"] = [
        "PROOF-ONLY: the circuits are OUR constructed RbsElectricalSystem records "
        "(schema-built template, add_circuit-wired in the equipment commit); validator "
        "CIRCUITS rule + this readback are necessary, NOT certification (rule 4: only "
        "Autodesk's reader certifies; no viewer verdict exists for this layer yet)",
    ]
    return rec


# ===========================================================================
# STAGE V -- validation / census / probes / gate dry-run
# ===========================================================================

def validate_rvt(path: str) -> Dict[str, Any]:
    from rvt.validate import validate_file
    t0 = time.time()
    rep = validate_file(path)
    return {
        "path": _relp(path), "md5": _md5(path), "size": os.path.getsize(path),
        "verdict": "VALID" if rep.ok else "INVALID",
        "n_errors": len(rep.errors), "n_warnings": len(rep.warnings),
        "errors": [f.to_json() for f in rep.errors[:20]],
        "warnings": [f.to_json() for f in rep.warnings[:12]],
        "stats": {k: rep.stats.get(k) for k in list(rep.stats)[:24]},
        "seconds": round(time.time() - t0, 1),
    }


def registry_census(path: str) -> Dict[str, Any]:
    try:
        from rvt.famload import four_registry_census
        c = four_registry_census(path)
        return {k: c.get(k) for k in ("save_units", "contentdocs_entries", "contentdocs_guids",
                                       "contenttable_records", "contenttable_guids",
                                       "familymgr_entries", "familymgr_guids", "coherent",
                                       "orphan_units", "unregistered") if k in c}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def identity_gate(path: str) -> Dict[str, Any]:
    """The job runner's identity gate (rvt.identity policy): our author /
    client strings, scrubbed path / username, document GUID coherent with
    History[0].  rvt.commit already applied the scrub at write time; this
    PROVES it (the same gate tools/rvt_job.py records)."""
    try:
        sys.path.insert(0, HERE)
        import rvt_job as J  # type: ignore
        g = J.identity_gate(path)
        return {"status": g.get("status"), "issues": g.get("issues"),
                "identity": g.get("identity"), "history_head_guid": g.get("history_head_guid")}
    except Exception as e:
        return {"status": "ERROR", "issues": [f"{type(e).__name__}: {e}"]}


def status_gate(out_path: str, base_path: str) -> Dict[str, Any]:
    """The job runner's provenance / deliverability gate: ledgers the output
    against its base.  On the pinned composed genesis base the ledger uses
    the base's authorship census (rvt.frontdoor.census, #143) -- only its
    residue is Autodesk-derived, our composed slots and this build's content
    are ours -- and the reason names the still-open gates (G2 #19 / G3 #23 /
    residue #21); the honest status stays PROOF-ONLY, NOT-DELIVERABLE, a
    LABEL recorded beside the delivered file, never a refusal."""
    try:
        sys.path.insert(0, HERE)
        import rvt_job as J  # type: ignore
        g = J.provenance_gate(out_path, base_path)
        return {k: g.get(k) for k in ("status", "deliverable", "base", "base_is_autodesk_sample",
                                       "base_kind", "residue", "census", "ledgered_against",
                                       "g1", "provenance_totals", "created_elements",
                                       "modified_elements", "reason",
                                       "elapsed_s") if k in g}
    except Exception as e:
        return {"status": "PROOF-ONLY, NOT-DELIVERABLE (gate crashed: "
                          f"{type(e).__name__}: {e})", "deliverable": False}


def write_probes_manifest(out_dir: str, base_rvt: str, candidates: List[Dict[str, Any]],
                          control_path: str) -> str:
    """The stream's probes.json: every candidate declares its CERTIFIED
    base + the byte-identical control (the probe_batch gate contract)."""
    manifest = {
        "stream": ("ifc-room (IFC INTENT -> OUR PROJECT FILE on the certified genesis "
                   "base): our loaded families + the room's walls + the equipment "
                   "instances, staged so a viewer FAIL bisects by layer"),
        "base": {
            "file": _relp(base_rvt),
            "certification": {"file": _relp(base_rvt),
                              "proves": ("ZA_deep = certified deep genesis rung (ORCHESTRATOR "
                                         "VERDICTS #18: ZA_deep PASS) -- the family-free base "
                                         "the room is built on")},
            "note": ("every candidate below declares this SAME certified base; the "
                     "internal build order (loaded -> +walls -> +instances) is recorded per "
                     "probe so the first FAIL in the chain names the layer"),
        },
        "standing_control": {
            "file": _relp(control_path),
            "identical_to": _relp(base_rvt),
            "md5": _md5(control_path) if os.path.exists(control_path) else None,
            "purpose": ("byte-identical copy of the certified base under a new name -- "
                        "read FIRST; a control FAIL voids the round (oracle/environment)"),
        },
        "read_order": ("control FIRST (round validity), then loaded-only (does OUR family "
                       "layer load on the family-free base?), then +walls (the certified "
                       "wall add path on this base), then the full room (+ instances -- the "
                       "least certain layer: cross-category placement scaffolding)"),
        "reading_the_results": {
            "control FAIL": "oracle/environment problem -- every verdict VOID",
            "loaded PASS": ("our COMPONENT-family layer (8 families, four registries) loads "
                            "on a family-free base -- the endgame's family-load question "
                            "answered YES"),
            "loaded FAIL": ("the component-family loader on a family-free host is the "
                            "defect (four-registry census / ContentDocuments empty-form / "
                            "AppInfo FamilyMgr) -- bisect with a single-family load"),
            "walls PASS (loaded PASS)": "the certified wall add path holds on this base",
            "full FAIL (walls PASS)": ("the equipment INSTANCE layer -- cross-category "
                                       "specimen scaffolding / upright free-standing frames / "
                                       "our connector managers -- read the card message"),
        },
        "probes": candidates,
    }
    path = os.path.join(out_dir, "probes.json")
    _jdump(path, manifest)
    return path


def make_control(base_rvt: str, out_dir: str) -> str:
    """Byte-identical certified copy under a control name (the gate's own
    stage command regenerates one at batch time; this copy travels with the
    stream so the manifest can name it)."""
    stem = os.path.splitext(os.path.basename(base_rvt))[0]
    ctrl = os.path.join(out_dir, f"CTRL_{stem}_ifcroom.rvt")
    shutil.copyfile(base_rvt, ctrl)
    return ctrl


def gate_dry_run(files: List[str]) -> Dict[str, Any]:
    """probe_batch 'check' in-process: proves the batch is ADMISSIBLE (every
    probe declares a certified base).  The certified CONTROL is generated by
    'probe_batch stage' at batch time, so the pre-made CTRL_ copy this stream
    ships is NOT part of the check list."""
    try:
        sys.path.insert(0, HERE)
        import probe_batch as PB  # type: ignore
    except Exception as e:
        return {"ran": False, "error": f"{type(e).__name__}: {e}"}
    try:
        entries, violations = PB.check_batch(files)
        return {"ran": True,
                "admissible": not violations,
                "violations": list(violations),
                "resolved": [{"file": getattr(e, "file", None),
                              "kind": getattr(e, "kind", None),
                              "base": (getattr(getattr(e, "base", None), "file", None)
                                       or str(getattr(e, "base", None))),
                              "base_certification": str(getattr(e, "base_certification", None))}
                             for e in entries]}
    except Exception as e:
        return {"ran": False, "error": f"{type(e).__name__}: {e}"}


# ===========================================================================
# the ROOM pipeline
# ===========================================================================

def build_room(ifc_path: str, out_dir: str, *, base_rvt: str = DEFAULT_BASE,
               specimen_src: str = DEFAULT_SPECIMEN_SRC,
               stages: str = "FLWECV", intent_out: Optional[str] = None) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    started = time.time()
    record: Dict[str, Any] = {
        "pipeline": "ifc_intent.build_room", "ifc": _relp(ifc_path),
        "base": _relp(base_rvt), "specimen_source": _relp(specimen_src),
        "stages_requested": stages, "stages": [], "outputs": {},
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "proof_only": ("PROOF-ONLY research artefacts: base = certified genesis lineage "
                       "(sample-derived, in-place substituted); added layer = OUR constructors' "
                       "output; NOT a deliverable to any third party"),
    }
    # ---- intent
    model = I.resolve_intent(ifc_path)
    intent_path = intent_out or os.path.join(out_dir, os.path.basename(ifc_path).replace(".ifc", "")
                                              + ".intent.json")
    I.write_intent(model, intent_path)
    record["outputs"]["intent"] = _relp(intent_path)
    _log(f"intent -> {_relp(intent_path)} ({len(model.equipment)} equipment, "
         f"{len(model.room.walls) if model.room else 0} walls, {len(model.feeders)} feeders)")

    # ---- stage F
    if "F" in stages:
        f_rec = stage_families(model, out_dir)
        record["stages"].append(f_rec)
    # ---- stage L
    current = base_rvt
    loaded: Dict[str, Any] = {}
    l_rec = None
    if "L" in stages:
        l_rec = stage_load(model, base_rvt, out_dir)
        loaded = l_rec.pop("_loaded")
        l_rec.pop("_products", None)
        current = l_rec.pop("_current") or base_rvt
        record["stages"].append(l_rec)
        record["outputs"]["loaded"] = l_rec.get("final")
        record["outputs"]["n_families_loaded"] = f"{l_rec['n_loaded']}/{l_rec['n_planned']}"
    # ---- specimens (needed by W and E)
    specimens = None
    if "W" in stages or "E" in stages:
        try:
            if specimen_src and os.path.isfile(specimen_src):
                specimens = SpecimenSet(specimen_src)
            else:
                from rvt.frontdoor.standalone import ConstructedSpecimens
                specimens = ConstructedSpecimens(base_path=base_rvt)
            record["specimens"] = {"source": _relp(specimen_src),
                                   "wall": specimens.wall_id, "wall_type": specimens.wall_type,
                                   "instance": specimens.instance_id,
                                   "instance_symbol": specimens.instance_symbol,
                                   "instance_category": specimens.instance_category}
        except Exception as e:
            record["specimens"] = {"error": f"{type(e).__name__}: {e}",
                                   "traceback": traceback.format_exc(limit=6)}
            _log(f"specimen load FAILED: {e}")
    # ---- stage W (walls onto the loaded file, or the base if loading died)
    walls_out = None
    if "W" in stages and specimens is not None:
        w_out = os.path.join(out_dir, "electrical_room_2500a_walls.rvt" if current == base_rvt
                             else "stage_W_loaded_walls.rvt")
        w_rec, walls_out = stage_walls(model, current, w_out, specimens, wall_mode="min")
        record["stages"].append(w_rec)
        record["outputs"]["walls"] = _relp(w_out) if walls_out else None
        # walls-only-on-base bisection pair: the two clean-up philosophies
        for mode, key in (("min", "walls_only"), ("unjoin", "walls_only_unjoined")):
            wb_out = os.path.join(out_dir, f"electrical_room_2500a_walls_only"
                                           f"{'' if mode == 'min' else '_unjoined'}.rvt")
            wb_rec, wb_ok = stage_walls(model, base_rvt, wb_out, specimens, wall_mode=mode)
            wb_rec["stage"] = f"W-base-{mode}"
            record["stages"].append(wb_rec)
            record["outputs"][key] = _relp(wb_out) if wb_ok else None
        if walls_out:
            current = walls_out
    # ---- stage E
    e_rec = None
    if "E" in stages and specimens is not None:
        if loaded:
            e_out = os.path.join(out_dir, "electrical_room_2500a.rvt")
            e_rec, e_ok = stage_equipment(model, current, e_out, specimens, loaded,
                                              circuits="C" in stages)
            record["outputs"]["room"] = _relp(e_out) if e_ok else None
            if e_ok:
                current = e_out
        else:
            e_rec = {"stage": "E", "skipped": True,
                     "reason": "no families loaded (stage L blocker) -> nothing to place"}
        record["stages"].append(e_rec)
    # ---- stage C (reads stage E's record to name a shortfall's real cause)
    if "C" in stages:
        record["stages"].append(stage_circuits(model, current, e_rec))
    # ---- stage V
    if "V" in stages:
        v_rec: Dict[str, Any] = {"stage": "V", "files": []}
        candidates = []
        outs = record["outputs"]
        probe_files = []
        for key, tests, if_pass, if_fail in (
            ("loaded", "does OUR component-family layer (the mapped families, four registries "
                       "each) LOAD on the family-free certified base?",
             "our generated families load into the genesis base (no placement variable)",
             "the component-family loader on a family-free host is the defect -- census + "
             "single-family bisection"),
            ("walls_only", "the room's four walls (certified wall add path, the base's wall "
                           "type, R5 specimen scaffolding, MINIMAL clone clean-up: reference "
                           "repair only, join history kept) on the certified base alone",
             "the wall add path holds on ZA_deep (with the Walls-category GStyle row absent)",
             "wall clone / commit path on this base, or the missing Walls-category GStyle row "
             "(30) -- compare the '_unjoined' twin and V22/V26 (certified on rme)"),
            ("walls_only_unjoined", "identical to IFCR_walls_only but with the textbook UNJOINED "
                                    "history (join / split-face steps trimmed, cached snapshots "
                                    "nulled -> pure regeneration)",
             "the trimmed unjoined-history variant loads (compare with the kept-history twin)",
             "the history TRIM is the fault if the kept-history twin passes; else the wall "
             "layer itself"),
            ("walls", "loaded families + the room's walls",
             "family layer + wall layer coexist",
             "read the card message; bisect vs loaded-only and walls-only"),
            ("room", "the FULL room: loaded families + walls + the seven boards + T1 as OUR "
                     "instances (free-standing, intent frames, our connector slots)",
             "IFC intent -> our project file end to end LOADS: our families, walls and placed "
             "equipment render",
             "the equipment INSTANCE layer (cross-category scaffolding / upright frames / "
             "connector managers) -- the least-certain layer; read the card message"),
        ):
            p = outs.get(key)
            if not p:
                continue
            ap = os.path.join(ROOT, p) if not os.path.isabs(p) else p
            if not os.path.exists(ap):
                continue
            val = validate_rvt(ap)
            cen = registry_census(ap)
            idg = identity_gate(ap)
            v_rec["files"].append({"key": key, "validate": val, "census": cen,
                                   "identity": idg})
            probe_files.append(ap)
            candidates.append({
                "file": p, "probe": f"IFCR_{key}", "kind": "probe",
                "base": _relp(base_rvt),
                "md5": val["md5"], "validator": val["verdict"],
                "validator_errors": val["n_errors"],
                "four_registry": cen.get("coherent"),
                "identity_gate": idg.get("status"),
                "tests": tests, "if_PASS": if_pass, "if_FAIL": if_fail,
                "self_checks_ok": (val["verdict"] == "VALID"
                                   and idg.get("status") == "PASS"
                                   and cen.get("coherent") is not False),
            })
            _log(f"V  {key:11s} {val['verdict']} ({val['n_errors']} errors, "
                 f"{val['n_warnings']} warnings; registries coherent={cen.get('coherent')}; "
                 f"identity {idg.get('status')})")
        ctrl = make_control(base_rvt, out_dir)
        record["outputs"]["control"] = _relp(ctrl)
        # deliverability status: PROOF-ONLY on a sample-derived base (recorded
        # by the same gate the job runner uses, on the deepest output)
        deepest = _deepest(outs)
        if deepest:
            dp = os.path.join(ROOT, deepest) if not os.path.isabs(deepest) else deepest
            v_rec["status_gate"] = status_gate(dp, base_rvt)
            record["outputs"]["status"] = v_rec["status_gate"].get("status")
            _log(f"V  status: {v_rec['status_gate'].get('status')}")
        pj = write_probes_manifest(out_dir, base_rvt, candidates, ctrl)
        record["outputs"]["probes"] = _relp(pj)
        v_rec["gate_dry_run"] = gate_dry_run(probe_files) if probe_files else None
        record["stages"].append(v_rec)
    record["seconds"] = round(time.time() - started, 1)
    record["deepest_output"] = _deepest(record["outputs"])
    rec_path = os.path.join(out_dir, "build_record.json")
    _jdump(rec_path, record)
    _log(f"build record -> {_relp(rec_path)}; deepest output = {record['deepest_output']}")
    return record


def _deepest(outs: Dict[str, Any]) -> Optional[str]:
    for k in ("room", "walls", "loaded", "walls_only", "walls_only_unjoined"):
        if outs.get(k):
            return outs[k]
    return None


# ===========================================================================
# CLI
# ===========================================================================

def cmd_intent(a) -> int:
    model = I.resolve_intent(a.ifc)
    out = a.out or (os.path.splitext(a.ifc)[0] + ".intent.json")
    I.write_intent(model, out)
    print(f"resolved intent (spec v{I.INTENT_VERSION}): {len(model.equipment)} equipment, "
          f"{len(model.room.walls) if model.room else 0} wall(s), "
          f"{len(model.feeders)} feeder edge(s) -> {out}")
    for e in model.equipment:
        print(f"  {e.tag:9s} {e.kind:23s} at {[round(x, 3) for x in e.insertion_m[:2]]} "
              f"el={round(e.elevation_m, 3)} front={[round(x, 2) for x in e.front_normal[:2]]} "
              f"yaw={round(e.yaw_deg, 1)}  [{e.disposition}]")
    for p in model.family_plans:
        tail = (p.refusal or "")[:70]
        print(f"  map {p.tag:8s} -> {p.status:8s} {p.constructor.split('.')[-1] if p.constructor else '-':24s} "
              f"{p.variant or ''} {tail}")
    for k, v in model.audit.items():
        print(f"  audit {k}: {v}")
    return 0


def cmd_families(a) -> int:
    model = I.resolve_intent(a.ifc)
    rec = stage_families(model, a.dir)
    _jdump(os.path.join(a.dir, "families", "families_record.json"), rec)
    print(json.dumps({k: v for k, v in rec.items() if k != "families"}, indent=1))
    for f in rec["families"]:
        print(f"  {f['tag']:8s} built={f.get('built')} ok={f.get('ok')} "
              f"{f.get('path') or f.get('reason') or f.get('error')}")
    return 0 if rec.get("all_ok") else 2


def cmd_room(a) -> int:
    rec = build_room(a.ifc, a.dir, base_rvt=a.base, specimen_src=a.specimens,
                     stages=a.stages, intent_out=a.intent_out)
    print(json.dumps({"outputs": rec["outputs"], "deepest": rec["deepest_output"],
                      "seconds": rec["seconds"]}, indent=1))
    return 0 if rec["deepest_output"] else 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IFC intent -> our project file (ifc-room stream)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("intent", help="resolve the IFC into intent.json (spec v2)")
    p1.add_argument("ifc", nargs="?", default=DEFAULT_IFC)
    p1.add_argument("-o", "--out", default=None)
    p1.set_defaults(fn=cmd_intent)
    p2 = sub.add_parser("families", help="generate our family set (.rfa) from the mapping")
    p2.add_argument("ifc", nargs="?", default=DEFAULT_IFC)
    p2.add_argument("-d", "--dir", default=DEFAULT_OUT)
    p2.set_defaults(fn=cmd_families)
    p3 = sub.add_parser("room", help="the staged project-file pipeline on the certified base")
    p3.add_argument("ifc", nargs="?", default=DEFAULT_IFC)
    p3.add_argument("-d", "--dir", default=DEFAULT_OUT)
    p3.add_argument("--base", default=DEFAULT_BASE)
    p3.add_argument("--specimens", default=DEFAULT_SPECIMEN_SRC)
    p3.add_argument("--stages", default="FLWECV",
                    help="subset of F(amilies) L(oad) W(alls) E(quipment) C(ircuits) V(alidate)")
    p3.add_argument("--intent-out", default=None)
    p3.set_defaults(fn=cmd_room)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
