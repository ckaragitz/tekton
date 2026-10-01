"""rvt.famgen.nest -- NEST one generated family inside another generated
family document and place N instances of it (issue #917).

Born families nest their hardware: a trapeze nests its rods, nuts and
washers as real family instances rather than drawing them as solids.  The
census of the owner's reference library (development instrument only, counts
in ``docs/inbox/param-drive.d/917-nested.md``) found that a nested family is
stored inside an ``.rfa`` EXACTLY the way a family loaded into a project is:
an extra save unit in the one partition, a ``Global/ContentDocuments`` entry,
a ``ContentTable`` record, a ``FamilyMgr`` entry, and the host-side
``Family`` / ``FamilySurrogate`` / ``FamilySymbol`` / ``FamSymSurrogate`` /
``ParamElemFamily`` twin layer.  So the load half is the project loader
(:mod:`rvt.famgen.loader`, L1-L5) pointed at a FAMILY document as host; what
this module adds is the family-host flavour of that layer and the placed
instances, which the project loader cannot author in a family (it clones a
template instance of the category and a generated family has none).

What a placed nested instance is, decoded from 3,687 free-placed nested
instances (host -1, on the family's Level, not work-plane based) of 313 born
families -- every constant below carries its count:

* ``FamilyInstance``: ``m_famId`` = the HOST's own self-Family, object design
  option -4, ``m_assocLevelId`` = the Level, ``m_hostId`` -1,
  ``m_workPlaneBased`` False, ``m_elevation`` 0 for an unrotated instance
  (1,143 of 1,251 unrotated) -- the height lives in the transform;
  ``InstanceInfo{m_Trf, m_symbolId, m_GRepId 0}``, ``m_masterSymbolId`` = the
  symbol, ``m_instOrigin`` = the transform origin (3,443), ``m_RefDir`` /
  ``m_zAxis`` = transform rows 0 / 2; ``ParamValueSetInt`` with Visible
  (-1006205) = 1 (the 610-instance shape; 3,074 also carry -1140129 = 2,
  meaning unknown, NOT emitted); ``GeomTable`` with one empty generator row
  (3,687); ``CellList{FamilyInstancePatternHelper}`` last (3,687);
  ``FamInstDesignPropertyManager`` (3,685); ``m_famElemVisibility`` 57406
  (3,662); ``m_roomBounding`` True, ``m_bVertical`` True (3,490);
  ``m_pInstParams`` = one row per INSTANCE parameter of the nested family,
  keyed by its host twin (3,658), flags instance/reporting False (3,684).
* its header: category = the nested symbol's (3,687), family = the host
  self-Family (3,687), flags 2856 / view flags -4225 (3,685), regenOnly =
  [nested Family] (3,446), appearance = {host self-Family, symbol, Level},
  deletion = {host self-Family, Level, symbol, itself, its instance-param
  twins}, bounding box == the rep's (3,687).
* its seq-103 rep: ``GElement{m_GInfo{category = the host's GStyleElem of
  the nested category (3,687), tag = itself, flags 557060}, one GInstance
  with the same InstanceInfo (3,639; transform equal 3,687), gElemType 3}``.
* family-host flavour of the loaded layer: nested ``Family`` header flags 10
  (3,685), nested ``FamilySymbol`` header flags 2472 (3,306); the nested
  symbols are NOT tracked in the host ``ElementTrackingData`` (0 of 313
  files), so the project loader's tracking row is not written here.

Not authored here (gaps recorded in the record): locks of an instance's
references to the host's planes (``Alignment`` witnesses at geomTag 1/4),
host-to-nested parameter association (``FamilyParametrizedElemParamsCell``),
work-plane-based / rotated / hosted placement, shared nesting, and the
nested type table's blank leading row the project loader writes (born
nested families carry real types only).

Honesty: everything here is format structure + our own two documents; no
reference-family value enters the output.  Validator green and an empty
constraint-law report are facts about the file; whether Revit opens a family
with nested instances is unverified until a desktop verdict exists (hard
rule 4) -- nothing calls this nesting "working".
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from . import loader as L

#: header flag words of a born family host's nested layer / instances [V counts above]
NESTED_FAMILY_HDR_FLAGS = 10
NESTED_SYMBOL_HDR_FLAGS = 2472
INSTANCE_HDR_FLAGS = 2856
INSTANCE_VIEW_FLAGS = -4225
#: FamilyInstance.m_famElemVisibility.m_flags (3,662 / 3,687)
INSTANCE_VISIBILITY_FLAGS = 57406
#: GElement / GInstance m_GInfo.m_flags (every free nested instance rep)
GINFO_FLAGS = 557060
#: the instance object's design option in a family document
FAMILY_DESIGN_OPTION = -4
#: built-in "Visible" integer parameter
BIP_VISIBLE = -1006205
#: a family is small: refuse runaway placement lists before touching anything
MAX_INSTANCES = 512

ProductArg = Union[Any, Callable[[int], Any]]


class NestError(RuntimeError):
    """A nesting precondition or post-write check failed; no output is left."""


@dataclass
class NestResult:
    ok: bool
    out_path: Optional[str]
    family_name: str = ""
    nested_family_id: int = -1
    symbol_id: int = -1
    instance_ids: List[int] = dc_field(default_factory=list)
    proofs: Dict[str, Any] = dc_field(default_factory=dict)
    notes: List[str] = dc_field(default_factory=list)

    def as_json(self) -> dict:
        return {"ok": self.ok, "out_path": self.out_path,
                "family_name": self.family_name,
                "nested_family_id": self.nested_family_id,
                "symbol_id": self.symbol_id, "instance_ids": list(self.instance_ids),
                "proofs": self.proofs, "notes": list(self.notes)}


# ---------------------------------------------------------------------------
# preconditions (all checked before anything is written)
# ---------------------------------------------------------------------------

def _points(points: Sequence[Sequence[float]]) -> List[Tuple[float, float, float]]:
    if points is None or isinstance(points, (str, bytes)):
        raise NestError("points must be a list of (x, y, z) feet")
    pts = []
    for i, p in enumerate(points):
        try:
            xyz = tuple(float(c) for c in p)
        except (TypeError, ValueError) as exc:
            raise NestError(f"point {i} is not numeric: {p!r}") from exc
        if len(xyz) != 3 or not all(math.isfinite(c) for c in xyz):
            raise NestError(f"point {i} must be three finite numbers (feet), got {p!r}")
        pts.append(xyz)
    if not pts:
        raise NestError("nothing to place: points is empty")
    if len(pts) > MAX_INSTANCES:
        raise NestError(f"{len(pts)} instances exceeds the {MAX_INSTANCES} cap")
    return pts


def _host_frame(host: "L.HostContext") -> Dict[str, int]:
    """The host family document's own self-Family and its one Level."""
    doc = host.doc
    selfs = [f for f in doc.ids_of_class("Family")
             if (doc.value(f) or {}).get("m_surrogateId") == -1
             and not (doc.value(f) or {}).get("m_oFamDoc")]
    if len(selfs) != 1:
        raise NestError(f"host is not a family document: {len(selfs)} self-Family "
                        "elements (want exactly 1)")
    levels = doc.ids_of_class("Level")
    if len(levels) != 1:
        raise NestError(f"host family carries {len(levels)} Levels; nesting places "
                        "on the family's one reference level")
    return {"self_family": int(selfs[0]), "level": int(levels[0])}


# ---------------------------------------------------------------------------
# authoring
# ---------------------------------------------------------------------------

def _ptr(cls: str, value: dict, pid: int = -1) -> dict:
    return {"ptr_class": cls, "pid": pid, "value": value}


def _identity3() -> List[List[float]]:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _instance_info(symbol_id: int, origin: Sequence[float]) -> dict:
    return {"m_Trf": {"m_3x3": _identity3(), "m_or": [float(c) for c in origin]},
            "m_symbolId": int(symbol_id), "m_GRepId": 0,
            "m_cda": {"m_pDoc": {"weakref": 1}}}


def _symbol_extent(authored) -> Tuple[List[float], List[float]]:
    """The nested symbol's own bounding box (its local frame), from the
    authored symbol geometry; a unit box when the symbol has no solid."""
    for e in authored.elements:
        if e.class_name == "FamilySymbol" and e.elem_id == authored.plan.symbol_id:
            bb = (e.rep or {}).get("m_bBox") if isinstance(e.rep, dict) else None
            if bb and len(bb) == 2:
                return [float(c) for c in bb[0]], [float(c) for c in bb[1]]
    return [-0.5, -0.5, 0.0], [0.5, 0.5, 1.0]


def _instance_param_rows(product, plan) -> List[dict]:
    """One row per INSTANCE parameter of the nested family, keyed by its host
    twin, current value kept, instance/reporting flags False [V 3,658/3,684]."""
    fp = ((product.doc.self_family.obj.get("m_familyParams") or {}).get("value") or {})
    rows = []
    for r in fp.get("m_params") or []:
        if not r.get("m_instance"):
            continue
        pid = r.get("m_paramId")
        if not (isinstance(pid, int) and pid in plan.twin_of):
            continue
        r2 = L._dc(r)
        r2["m_paramId"] = int(plan.twin_of[pid])
        r2["m_instance"] = False
        r2["m_reporting"] = False
        rows.append(r2)
    return rows


def author_nested_instance(eid: int, origin: Sequence[float], *, product, plan,
                           frame: Dict[str, int], category: int, gstyle: int,
                           extent: Tuple[List[float], List[float]]):
    """One free-placed nested ``FamilyInstance`` (+ its GElement rep) at
    ``origin`` (feet, family coordinates, unrotated)."""
    from ..genesis.types import blank_object
    from ..genesis.skeleton import element_header
    from .geometry import assign_pids
    sym = int(plan.symbol_id)
    lvl, selff = frame["level"], frame["self_family"]
    org = [float(c) for c in origin]
    lo = [org[k] + extent[0][k] for k in range(3)]
    hi = [org[k] + extent[1][k] for k in range(3)]

    obj = blank_object("FamilyInstance")
    obj.update({
        "m_pParamValueSetInt": _ptr("ParamValueSetInt", {
            "m_paramSet": [{"m_paramId": BIP_VISIBLE, "m_value": 1}]}),
        "m_cellList": _ptr("CellList", {"m_cells": [
            _ptr("FamilyInstancePatternHelper", {"m_PatternPositionMap": [],
                                                 "m_substituteFaceMap": []})]}),
        "m_docAccess": {"m_pDoc": {"weakref": 1}},
        "m_id": int(eid), "m_assocLevelId": lvl, "m_famId": selff,
        "m_unplacedOwnerId": -1, "m_ownerDBViewId": -1, "m_createdPhaseId": -1,
        "m_demolishedPhaseId": -1, "m_designOptionId": FAMILY_DESIGN_OPTION,
        "m_pInstanceInfo": _ptr("InstanceInfo", _instance_info(sym, org)),
        "m_GInstanceId": 0, "m_elevation": 0.0, "m_hostParam": 0.0, "m_hostId": -1,
        "m_pInstParams": _ptr("FamilyParams", {
            "m_params": _instance_param_rows(product, plan),
            "m_geomRefHandles": {"m_offsetGeomMap": []}}),
        "m_instOrigin": list(org), "m_RefDir": [1.0, 0.0, 0.0], "m_zAxis": [0.0, 0.0, 1.0],
        "m_masterSymbolId": sym, "m_ownerElemId": -1, "m_assocSketchPlaneId": -1,
        "m_analyticalTopPlaneId": -1, "m_analyticalBottomPlaneId": -1,
        "m_superInstanceId": -1, "m_scheduleOnlyLevelId": -1,
        "m_famElemVisibility": {"m_flags": INSTANCE_VISIBILITY_FLAGS},
        "m_roomBounding": True, "m_bVertical": True, "m_workPlaneBased": False,
    })
    gt = blank_object("GeomTable")
    gt["m_table"] = [{"m_geomGeneratorId": -1}]
    for k in ("m_maxSafeTag", "m_lastCheckedKingsUserModificationDate"):
        if k in gt:                       # release-dependent fields
            gt[k] = -1
    obj["m_pGeomTable"] = _ptr("GeomTable", gt)
    dpm = blank_object("FamInstDesignPropertyManager")
    obj["m_pDesignPropManager"] = _ptr("FamInstDesignPropertyManager", dpm)
    assign_pids(obj)

    gi = blank_object("GInstance")
    gi.update({"m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                           "m_flags": GINFO_FLAGS},
               "m_instanceInfo": _ptr("InstanceInfo", _instance_info(sym, org)),
               "m_oEmbeddedSymbolGRep": None, "m_tagId": -1,
               "m_forbiddenTarget": {"m_targets": 0}})
    rep = blank_object("GElement")
    rep.update({"m_GInfo": {"m_categoryId": int(gstyle), "m_tag": int(eid),
                            "m_controlCommand": 0, "m_flags": GINFO_FLAGS},
                "m_subNodes": [_ptr("GInstance", gi)],
                "m_bBox": [list(lo), list(hi)], "m_tightbBox": [list(lo), list(hi)],
                "m_elementId": int(eid), "m_gElemType": 3, "m_flags": 0})
    assign_pids(rep)

    ip_ids = [r["m_paramId"] for r in obj["m_pInstParams"]["value"]["m_params"]]
    hdr = element_header("FamilyInstance", category=int(category), family_id=selff,
                         deletion=sorted({selff, lvl, sym, int(eid), *ip_ids}),
                         regen_only=[int(plan.host_family_id)],
                         appearance=sorted({selff, sym, lvl}),
                         flags=INSTANCE_HDR_FLAGS, visible_view_flags=INSTANCE_VIEW_FLAGS,
                         bbox=(lo, hi))
    el = L._skel(int(eid), "FamilyInstance", hdr, obj, rep, kind="nested_instance")
    el.notes.append(f"nested instance of symbol {sym} at {org} on Level {lvl} "
                    "(free placement, unrotated, no locks)")
    return el


def _family_host_flavour(authored) -> None:
    """Born family hosts carry the nested Family / FamilySymbol headers with
    flags 10 / 2472 where the project loader writes 26 / 2488."""
    for e in authored.elements:
        if e.class_name == "Family" and e.elem_id == authored.plan.host_family_id:
            e.header["m_abFlags4Bytes"] = NESTED_FAMILY_HDR_FLAGS
        elif e.class_name == "FamilySymbol" and e.elem_id in authored.plan.symbol_ids:
            e.header["m_abFlags4Bytes"] = NESTED_SYMBOL_HDR_FLAGS


def _edit_family_host_registries(host_rfa: str, authored) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """ContentTable record + FamilyMgr entry + ContentDocuments entry (the
    project loader's L5/L1), WITHOUT the ElementTrackingData symbol row: born
    family hosts never track their nested symbols there (0 / 313)."""
    from . import factory as F
    from ..container import open_rvt
    from ..adocument import decode_latest, encode_latest
    with open_rvt(host_rfa) as f:
        latest_payload = f.inflate("Global/Latest")
        cd_payload = b"".join(f.inflate_all("Global/ContentDocuments"))
    lat = decode_latest(latest_payload)
    if not lat.clean:
        raise NestError("host Global/Latest does not decode clean")
    lv = L._dc(lat.value)
    plan = authored.plan
    saved = (list(plan.symbol_ids), plan.instance_id)
    try:
        # register without any tracking ids (the helper skips empty id lists)
        plan.symbol_ids, plan.instance_id = [], L.INVALID
        reg = L.register_in_host_adocument(lv, plan, category=authored.category,
                                           unit_records=int(authored.unit["record_count"]))
    finally:
        plan.symbol_ids, plan.instance_id = saved
    new_latest = encode_latest(lv, trailer=lat.trailer)
    if not decode_latest(new_latest).clean:
        raise NestError("edited host ADocument does not re-decode clean")
    ents, tail = F.parse_content_documents(cd_payload)
    if any(g == plan.guid for g, _a in ents):
        raise NestError(f"content document {plan.guid} is already nested in the host")
    cd_new = F.assemble_content_documents(
        ents + [(plan.guid, bytes(authored.adocument["payload"]))],
        tail=tail or F.CD_END_RECORD)
    after, _t = F.parse_content_documents(cd_new)
    if plan.guid not in {g for g, _a in after}:
        raise NestError("our ContentDocuments entry did not insert")
    return new_latest, cd_new, {"registrations": reg,
                                "content_documents": {"before": len(ents), "after": len(after)}}


# ---------------------------------------------------------------------------
# verification of the written host
# ---------------------------------------------------------------------------

def verify_nested(path: str, *, nested_family_id: int, symbol_id: int,
                  instance_ids: Sequence[int], guid: str,
                  validate: bool = True) -> Dict[str, Any]:
    """Read the written host back under its own release and prove: the
    nested Family / symbol / every instance decode clean and point at each
    other, the content document + FamilyMgr entry are present, the four
    document registries agree (every born family in the census does: 421 /
    421), the family-mode validator reports 0 errors and the constraint law
    has no findings."""
    from contextlib import ExitStack
    from ..global_framing import enter_own_release
    from ..families import FamilyIndex
    from ..container import open_rvt
    from ..adocument import decode_latest
    from . import constraint_law as CL
    rep: Dict[str, Any] = {"problems": []}
    bad = rep["problems"]
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})

        def val(eid: int) -> dict:
            if eid not in recs:
                bad.append(f"element {eid} missing")
                return {}
            o = fi.decode(0, eid, 102)
            if o is None or not o.clean:
                bad.append(f"element {eid} does not decode clean")
                return {}
            return o.value or {}
        fam = val(nested_family_id)
        fd = ((fam.get("m_oFamDoc") or {}).get("value") or {})
        if fd.get("m_contentDocGUID") != guid:
            bad.append("nested Family does not carry our content GUID")
        sym = val(symbol_id)
        if sym.get("m_familyId") != nested_family_id:
            bad.append("nested symbol does not point at the nested Family")
        for iid in instance_ids:
            o = val(iid)
            ii = ((o.get("m_pInstanceInfo") or {}).get("value") or {})
            if ii.get("m_symbolId") != symbol_id or o.get("m_masterSymbolId") != symbol_id:
                bad.append(f"instance {iid} does not point at symbol {symbol_id}")
            r = fi.decode(0, iid, 103)
            if r is None or not r.clean:
                bad.append(f"instance {iid} rep does not decode clean")
        rep["units"] = len(fi.units)
        with open_rvt(path) as f:
            lat = decode_latest(f.inflate("Global/Latest"))
        mgr = ((lat.value.get("m_pAppInfoManager") or {}).get("value") or {}).get("m_appInfoArr") or []
        fm = next((x.get("value") for x in mgr if isinstance(x, dict)
                   and x.get("ptr_class") == "FamilyMgr"), {}) or {}
        if not any(guid in (e.get("m_familyDocGUIDs") or []) for e in fm.get("m_arrLoadedFamilyInfo") or []):
            bad.append("FamilyMgr has no entry for the nested document")
        from . import factory as F
        with open_rvt(path) as f:
            cd = b"".join(f.inflate_all("Global/ContentDocuments"))
        ents, _tail = F.parse_content_documents(cd)
        rep["content_documents"] = len(ents)
        if guid not in {str(g) for g, _a in ents}:
            bad.append("Global/ContentDocuments has no entry for the nested document")
    from ..famload import four_registry_census
    reg = four_registry_census(path)
    rep["registries_coherent"] = bool(reg.get("coherent"))
    if not reg.get("coherent"):
        bad.append("the four document registries disagree (save units / ContentDocuments / "
                   "ContentTable / FamilyMgr)")
    findings = CL.check_file(path)
    rep["constraint_law"] = findings
    if findings:
        bad.append(f"constraint law: {len(findings)} finding(s)")
    if validate:
        from ..validate import validate_file
        vr = validate_file(path, family=True)
        errs = [f"[{f.layer}] {f.where}: {f.message}" for f in vr.errors]
        rep["validate"] = {"verdict": "VALID" if not errs else "INVALID",
                           "n_errors": len(errs), "n_warnings": len(vr.warnings),
                           "errors": errs[:20]}
        if errs:
            bad.append(f"rvt_validate (family mode): {len(errs)} error(s)")
    rep["ok"] = not bad
    return rep


# ---------------------------------------------------------------------------
# the public entry point
# ---------------------------------------------------------------------------

def nest_family(host_rfa: str, out_rfa: str, child: ProductArg,
                points: Sequence[Sequence[float]], *,
                validate: bool = True) -> NestResult:
    """Embed ``child`` (a :class:`rvt.famgen.factory.FamilyProduct`, or a
    callable ``f(start_id) -> FamilyProduct`` so its ids land above the
    host's) into the generated family ``host_rfa`` and place one unrotated,
    free instance at every point (feet, family coordinates), writing
    ``out_rfa``.

    All or nothing: every precondition is checked and every record is
    authored and round-trip-gated before the one write; the written file is
    then read back (:func:`verify_nested`) and, if any check fails, removed
    and :class:`NestError` raised.  ``child`` must have been built under the
    host's release (build both inside the same ``release_build_context``).
    """
    if not str(host_rfa).lower().endswith(".rfa") or not os.path.isfile(host_rfa):
        raise NestError(f"host must be an existing .rfa: {host_rfa!r}")
    if not str(out_rfa).lower().endswith(".rfa"):
        raise NestError(f"output must be an .rfa path: {out_rfa!r}")
    if os.path.abspath(out_rfa) == os.path.abspath(host_rfa):
        raise NestError("refusing to overwrite the host in place")
    pts = _points(points)
    from ..frontdoor.release_ctx import host_release_context
    with host_release_context(host_rfa):
        return _nest(host_rfa, out_rfa, child, pts, validate=validate)


def _nest(host_rfa: str, out_rfa: str, child: ProductArg,
          pts: List[Tuple[float, float, float]], *, validate: bool) -> NestResult:
    host = L.survey_host(host_rfa, category=None)
    frame = _host_frame(host)
    product = child(int(host.watermark) + 1) if callable(child) else child
    try:
        L._require_ids_above(product, host.watermark)
    except L.LoaderError as exc:
        raise NestError(str(exc)) from exc
    if product.doc.connectors:
        raise NestError("nesting a family with connectors is not supported in this pass")
    cat = L.product_category(product)
    host = L.bind_category(host, cat)
    if host.category_gstyle == L.INVALID:
        raise NestError(f"host family has no GStyleElem for the nested category {cat}: "
                        "a nested family of a category the host does not carry is not "
                        "supported in this pass")
    try:
        authored = L._author_load(product, host, place=False, symbol_solid=True,
                                  circuit_slots=0)
    except L.LoaderError as exc:
        raise NestError(f"loading the nested document failed: {exc}") from exc
    _family_host_flavour(authored)
    plan = authored.plan
    extent = _symbol_extent(authored)
    first = authored.max_host_id + 1
    inst = [author_nested_instance(first + i, p, product=product, plan=plan, frame=frame,
                                   category=cat, gstyle=host.category_gstyle, extent=extent)
            for i, p in enumerate(pts)]
    gate = L._roundtrip_gate(authored.elements + inst)
    if gate.get("failed", 1) != 0 or gate.get("roundtrip_ok", 0) != gate.get("records", -1):
        raise NestError(f"a record failed the encode/decode round trip: {gate.get('failures', [])[:6]}")
    authored.elements = sorted(authored.elements + inst, key=lambda e: e.elem_id)
    new_latest, cd_new, reg = _edit_family_host_registries(host_rfa, authored)

    out_dir = os.path.dirname(os.path.abspath(out_rfa))
    os.makedirs(out_dir, exist_ok=True)
    try:
        wr = L._commit_and_write(host_rfa, out_rfa, host, [authored], new_latest, cd_new,
                                 identity=_host_identity(host_rfa))
    except Exception as exc:                                   # noqa: BLE001
        _discard(out_rfa)
        raise NestError(f"writing the host failed: {type(exc).__name__}: {exc}") from exc
    ids = [e.elem_id for e in inst]
    ver = verify_nested(out_rfa, nested_family_id=plan.host_family_id,
                        symbol_id=plan.symbol_id, instance_ids=ids, guid=plan.guid,
                        validate=validate)
    if not ver["ok"]:
        _discard(out_rfa)
        raise NestError(f"written host failed verification: {ver['problems'][:6]}")
    return NestResult(
        ok=True, out_path=out_rfa, family_name=plan.family_name,
        nested_family_id=plan.host_family_id, symbol_id=plan.symbol_id,
        instance_ids=ids,
        proofs={"roundtrip_gate": {k: gate.get(k) for k in ("records", "roundtrip_ok", "failed")},
                "registries": reg, "write": wr, "verify": ver,
                "load": {k: authored.proofs.get(k) for k in ("plan", "save_unit")}},
        notes=list(host.notes) + [
            "nested instances are free-placed, unrotated and unlocked; host "
            "parameters are not associated to the nested family's",
            "validator green and an empty constraint-law report are facts about "
            "the file; no desktop-Revit verdict exists for nested families "
            "(hard rule 4)"])


def _host_identity(host_rfa: str) -> Dict[str, Any]:
    """The host's own BasicFileInfo username (ours, ``rvt-writer``, on a
    generated family) -- the nested write keeps it rather than blanking it."""
    from ..container import open_rvt
    from ..identity import BFI_STREAM
    from .. import stream_encoders as se
    with open_rvt(host_rfa) as f:
        if not f.has(BFI_STREAM):
            return {"username": ""}
        m = se.decode_basic_file_info(f.raw(BFI_STREAM))
    return {"username": str(m.get("username") or "")}


def _discard(path: str) -> None:
    for p in (path, path + ".pass1.tmp"):
        try:
            os.remove(p)
        except OSError:
            pass
