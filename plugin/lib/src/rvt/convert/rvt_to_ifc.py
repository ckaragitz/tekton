"""rvt.convert.rvt_to_ifc -- EXPORT ROUTE: RVT -> intent -> IFC4.

The missing export direction of the routing matrix: read a project's
CONTENT back out of the ``.rvt`` (no Revit involved) into the SAME intent
shape every creation route resolves to, and emit IFC4 through the EXISTING
intent->IFC emitter -- nothing here re-implements a stage:

* read      :meth:`rvt.mutate.Document.from_file` + :mod:`rvt.inventory`
            + :class:`rvt.families.FamilyIndex` (certified read/inventory
            stages);
* model     duck-typed to the resolver's own dataclasses
            (:class:`rvt.ifc.intent.WallRun` / :class:`FeederEdge`) plus a
            small equipment record carrying exactly the fields the emitter
            reads;
* emit      :func:`rvt.frontdoor.ifc_out.write_intent_ifc` (the certified
            intent->IFC stage: deterministic IFC4, tessellated boxes, the
            tagging-contract psets as the join key).

WHAT IS EXTRACTED (each an honest, separately-reported cell):

* levels            name + elevation (``m_text`` / ``m_pSurface.m_origin.z``);
* walls             every straight (GLine-driven) ``SWall``: centerline
                    p0->p1 from the curve driver, thickness from the wall
                    TYPE's compound structure, height from the wall height
                    parameter (-1001101 / -1001105), base from the curve z;
* equipment         every ``FamilyInstance`` of OST_ElectricalEquipment:
                    family :: symbol identity, position + full frame from
                    ``InstanceInfo.m_Trf`` (yaw vs upright decided by the
                    3x3's family-Z row -- the same convention the build
                    stage writes), and the TAGGING-CONTRACT parameter
                    VALUES read from the family document's own
                    ``ParamElemFamily`` captions + type-table rows
                    (spec-driven unit conversion back to metres / volts),
                    plus instance-level PanelName / Mark AStrings;
* feeder edges      every ``RbsElectricalSystem`` circuit whose panel-side
                    AND load-side connector references both resolve to
                    extracted equipment (rating / poles / number ride
                    along); circuits to non-equipment loads are counted,
                    not faked.

ROUND TRIP IS THE ACCEPTANCE: the emitted IFC re-resolves through
``rvt.ifc.intent.resolve_intent`` and the manifest carries the SURVIVAL
TABLE (tags / kinds / walls / positions in-RVT vs in-IFC-intent).

PROVENANCE: an IFC exported from someone else's model carries THEIR design
content.  The manifest stamps the source lineage (tekton-authored vs
Autodesk-sample vs unknown) and quarantined sources are labelled dev-only.

RELEASE: the source is read under its OWN Revit release
(``rvt.global_framing.enter_own_release``), so a 2025 / 2024 project exports
like a 2026 one; ``input.provenance.format`` names that release and a
degraded source records the fallback rung taken as a caveat.

CLI::

    python -m rvt.convert.rvt_to_ifc <in.rvt> [-o out.ifc | --out-dir D]
                                     [--no-roundtrip] [--max-walls N]

Territory: ``src/rvt/convert/`` (convert-a stream).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
import traceback
from contextlib import ExitStack
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..global_framing import enter_own_release
from .add_to_project import (ConvertError, TOOL, TOOL_VERSION, _jdump, _relp,
                             _sha256, quarantined_input)

__all__ = [
    "RvtReadError", "ExtractedEquipment", "ExtractedModel", "extract_intent",
    "convert_rvt_to_ifc", "roundtrip_table", "main",
]

M_PER_FT = 0.3048
_ELEC_FACTOR = 1.0 / (0.3048 ** 2)          # internal -> volts is the inverse

OST_ELECTRICAL_EQUIPMENT = -2001040
BIP_WALL_HEIGHT = -1001101
BIP_WALL_USER_HEIGHT = -1001105
BIP_PANEL_NAME = -1140078
BIP_MARK = -1001203

#: ALL_MODEL_* built-in family params worth carrying by contract name
_BUILTIN_CAPTIONS = {-1010103: "ModelLabel", -1010104: "Manufacturer",
                     -1010109: "Description", -1010106: "TypeComments",
                     -1010105: "FamilyName"}

#: equipment-tag token embedded in our generated family names (MSB, DP-1,
#: LP-4, T1, ...) -- the fallback join key when no PanelName param exists
_TAG_TOKEN_RX = re.compile(r"\b(MSB|MDP(?:-\d+)?|SWBD|[A-Z]{1,4}-\d+|[A-Z]{1,2}\d{1,3})\b")

#: the provenance stamp a foreign-source export must carry (dev-only rule)
FOREIGN_CONTENT_STAMP = (
    "FOREIGN DESIGN CONTENT: the source model was not authored by tekton -- "
    "the exported IFC carries THAT model's design content (their walls, their "
    "equipment identities, their parameter values). Dev/interop artifact for "
    "the file's owner; never shipped as tekton content.")


class RvtReadError(ConvertError):
    """The .rvt cannot be read back (bad file / no partition streams)."""


# ---------------------------------------------------------------------------
# the extracted model (duck-typed for rvt.frontdoor.ifc_out.write_intent_ifc)
# ---------------------------------------------------------------------------

@dataclass
class ExtractedEquipment:
    """One equipment instance, carrying exactly the fields the intent->IFC
    emitter reads (plus extraction provenance for the manifest)."""
    elem_id: int
    tag: str
    name: str
    kind: str
    ifc_class: str
    insertion_m: List[float]
    front_normal: List[float]
    frame_kind: str                     # 'yaw' | 'upright'
    dims_m: Dict[str, float]
    contract: Dict[str, Any]
    fed_from: Optional[str] = None
    family_name: Optional[str] = None
    symbol_name: Optional[str] = None
    family_unit: Optional[int] = None
    contract_source: List[str] = dc_field(default_factory=list)
    notes: List[str] = dc_field(default_factory=list)

    def as_json(self) -> Dict[str, Any]:
        return {"elem_id": self.elem_id, "tag": self.tag, "name": self.name,
                "kind": self.kind, "ifc_class": self.ifc_class,
                "insertion_m": [round(x, 4) for x in self.insertion_m],
                "front_normal": [round(x, 4) for x in self.front_normal],
                "frame_kind": self.frame_kind,
                "dims_m": {k: round(v, 4) for k, v in self.dims_m.items()},
                "family": self.family_name, "symbol": self.symbol_name,
                "family_unit": self.family_unit,
                "contract": {k: v for k, v in self.contract.items()
                             if not str(k).startswith("_")},
                "fed_from": self.fed_from,
                "contract_source": list(self.contract_source),
                "notes": list(self.notes)}


class _Room:
    """Duck-typed room shell: the fields ``write_intent_ifc`` reads."""

    def __init__(self, name: str, walls: list):
        self.name = name
        self.walls = walls
        self.doors: list = []
        self.clear: Dict[str, Any] = {}
        self.info = {"RoomName": name}


class ExtractedModel:
    """Duck-typed intent model: the fields ``write_intent_ifc`` reads, plus
    the extraction report for the manifest."""

    def __init__(self, *, project_name: str, source_path: str):
        self.project_name = project_name
        self.source_path = source_path
        self.schema = "rvt-readback"
        self.levels: List[dict] = []
        self.room: Optional[_Room] = None
        self.equipment: List[ExtractedEquipment] = []
        self.feeders: list = []
        self.extraction: Dict[str, Any] = {}

    def by_tag(self, tag: str) -> Optional[ExtractedEquipment]:
        for e in self.equipment:
            if e.tag == tag:
                return e
        return None


# ---------------------------------------------------------------------------
# per-cell extractors
# ---------------------------------------------------------------------------

def _extract_levels(doc) -> List[dict]:
    out = []
    for i, lv in enumerate(doc.levels(), 1):
        out.append({"id": f"L{i}", "name": lv.get("name") or f"Level {i}",
                    "elevation": round(float(lv["elevation_ft"]) * M_PER_FT, 6),
                    "elem_id": lv["id"],
                    "is_building_story": lv.get("is_building_story")})
    return out


def _double_param(v: dict, param_id: int) -> Optional[float]:
    ds = ((v.get("m_pParamValueSetDouble") or {}).get("value") or {})
    for p in ds.get("m_paramSet") or []:
        if p.get("m_paramId") == param_id:
            return float(p.get("m_value"))
    return None


def _astring_param(v: dict, param_id: int) -> Optional[str]:
    ds = ((v.get("m_pParamValueSetAString") or {}).get("value") or {})
    for p in ds.get("m_paramSet") or []:
        if p.get("m_paramId") == param_id:
            s = p.get("m_value")
            return str(s).strip() or None if s is not None else None
    return None


def _extract_walls(doc, wall_thickness_m: Dict[int, float],
                   wall_type_names: Dict[int, Optional[str]],
                   max_walls: Optional[int] = None) -> Tuple[list, List[dict]]:
    """Straight SWalls -> :class:`rvt.ifc.intent.WallRun` list + detail rows."""
    from ..ifc.intent import WallRun
    runs, rows = [], []
    ids = doc.straight_walls()
    skipped = 0
    for i, wid in enumerate(ids, 1):
        if max_walls is not None and len(runs) >= max_walls:
            skipped += 1
            continue
        v = doc.value(wid) or {}
        drv = ((v.get("m_pCurveDriver") or {}).get("value") or {})
        crv = (drv.get("m_pCrv") or {}).get("value") or {}
        org = crv.get("m_origin") or [0.0, 0.0, 0.0]
        d = crv.get("m_dirVec") or [1.0, 0.0, 0.0]
        ep = crv.get("m_endParams") or [0.0, 1.0]
        p0 = [(org[0] + d[0] * ep[0]) * M_PER_FT, (org[1] + d[1] * ep[0]) * M_PER_FT]
        p1 = [(org[0] + d[0] * ep[1]) * M_PER_FT, (org[1] + d[1] * ep[1]) * M_PER_FT]
        type_id = v.get("m_WallAttributesId")
        thick = wall_thickness_m.get(type_id)
        h_ft = _double_param(v, BIP_WALL_HEIGHT)
        if h_ft is None:
            h_ft = _double_param(v, BIP_WALL_USER_HEIGHT)
        notes = []
        if thick is None:
            thick = 0.1
            notes.append(f"wall type {type_id} has no compound-structure "
                         "thickness: 0.1 m assumed")
        if h_ft is None or h_ft <= 0:
            h_ft = 8.0
            notes.append("no wall height parameter: 8 ft assumed")
        runs.append(WallRun(wall_id=f"w{i}", p0_m=p0, p1_m=p1,
                            thickness_m=round(float(thick), 6),
                            height_m=round(float(h_ft) * M_PER_FT, 6),
                            base_m=round(float(org[2]) * M_PER_FT, 6),
                            derived_from=[f"SWall {wid}"]))
        rows.append({"elem_id": wid, "type_id": type_id,
                     "type_name": wall_type_names.get(type_id),
                     "p0_m": [round(x, 4) for x in p0],
                     "p1_m": [round(x, 4) for x in p1],
                     "thickness_m": round(float(thick), 4),
                     "height_m": round(float(h_ft) * M_PER_FT, 4),
                     "base_m": round(float(org[2]) * M_PER_FT, 4),
                     "level_id": v.get("m_assocLevelId"), "notes": notes})
    return runs, rows + ([{"skipped_beyond_max_walls": skipped}] if skipped else [])


# ---- the family-document tagging contract ---------------------------------

_SPEC_LEN = "autodesk.spec.aec:length"
_SPEC_POT = "autodesk.spec.aec.electrical:potential"
_SPEC_APP = "electrical:apparent_power"


def _family_param_defs(idx, unit: int) -> Dict[int, Tuple[str, str]]:
    """{ParamElemFamily id: (caption, spec type id)} of one family unit."""
    out: Dict[int, Tuple[str, str]] = {}
    for eid in idx.ids_of_class(unit, "ParamElemFamily"):
        v = idx.value(unit, eid) or {}
        pd = ((v.get("m_pParamDef") or {}).get("value") or {})
        cap = str(pd.get("m_caption") or "").strip()
        spec = str(((pd.get("m_specTypeId") or {}) or {}).get("m_typeId") or "")
        if cap:
            out[eid] = (cap, spec)
    return out


def _param_value(row: dict, spec: str) -> Any:
    """A type-table / family-param row -> a human-unit value, spec-driven."""
    s = row.get("m_str") or ""
    if s:
        return s
    iv = row.get("m_int")
    if iv not in (None, 0) and "int64" in spec:
        return int(iv)
    if "spec.string" in spec:
        return s or None
    if "int64" in spec:
        return int(iv or 0)
    val = float(row.get("m_value") or 0.0)
    if _SPEC_LEN in spec:
        return round(val * M_PER_FT, 6)                 # ft -> m
    if _SPEC_POT in spec or _SPEC_APP in spec:
        return round(val / _ELEC_FACTOR, 6)             # internal -> V / VA
    return round(val, 6)


def _family_contract(idx, unit: int, type_name: Optional[str]) -> Tuple[Dict[str, Any], List[str]]:
    """The tagging-contract values of one embedded family document: caption ->
    value from the named type's rows (fallback: the current defaults)."""
    from ..families import self_family_of_unit
    defs = _family_param_defs(idx, unit)
    sf = self_family_of_unit(idx, unit)
    if sf is None:
        return {}, ["family unit has no self-Family"]
    src: List[str] = []
    # prefer the named type's rows
    fam_v = idx.value(unit, sf["id"]) or {}
    ftt = ((fam_v.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    rows = None
    if pairs:
        pick = None
        if type_name:
            for pr in pairs:
                if str(pr.get("name")) == str(type_name):
                    pick = pr
                    break
        pick = pick or pairs[0]
        rows = list(((pick.get("params") or {}).get("m_params")) or [])
        src.append(f"family type table row {pick.get('name')!r}")
    if not rows:
        fp = ((fam_v.get("m_familyParams") or {}).get("value") or {})
        rows = list(fp.get("m_params") or [])
        src.append("self-Family current defaults (m_familyParams)")
    out: Dict[str, Any] = {}
    for row in rows:
        pid = row.get("m_paramId")
        cap, spec = defs.get(pid, (None, ""))
        if cap is None:
            cap = _BUILTIN_CAPTIONS.get(pid)
            spec = "spec.string"
        if cap is None:
            continue
        val = _param_value(row, spec)
        if val not in (None, ""):
            out[cap] = val
    return out, src


def _classify(name: str, contract: Dict[str, Any]) -> str:
    """Mirror of the resolver's OWN precedence (``rvt.ifc.intent.
    _classify_equipment``), so the kind label the round trip re-derives from
    the emitted IFC agrees with the label extracted from the RVT."""
    from ..ifc.intent import parse_voltage
    # hay mirrors the resolver's inputs: the product NAME + TAG (PanelName);
    # the Description deliberately stays out (the resolver does not hay it)
    hay = " ".join(str(x) for x in (name, contract.get("PanelName")) if x).lower()
    if "switchboard" in hay or "switchgear" in hay:
        return "switchboard"
    if "transformer" in hay:
        return "transformer"
    v = contract.get("Voltage")
    ll = None
    if isinstance(v, str):
        ll = parse_voltage(v).get("ll")
    elif isinstance(v, (int, float)):
        ll = float(v)
    bus = None
    try:
        bus = float(contract.get("BusRating")) if contract.get("BusRating") is not None else None
    except (TypeError, ValueError):
        pass
    if re.search(r"receptacle|appliance", hay) or (ll is not None and ll <= 240):
        return "receptacle_panelboard"
    mains = str(contract.get("MainsType") or "").lower()
    if re.search(r"lighting|lp-", hay) or (bus is not None and bus <= 225
                                           and "lugs" in mains):
        return "lighting_panelboard"
    if re.search(r"distribution|dp-", hay) or (bus is not None and bus >= 250):
        return "distribution_panelboard"
    return "panelboard"


def _voltage_string(name: str, contract: Dict[str, Any]) -> None:
    """Fold a '480Y/277' system found in the name/description back into the
    contract's Voltage (the resolver parses the Y-system string)."""
    hay = " ".join(str(x) for x in (name, contract.get("Description")) if x)
    m = re.search(r"(\d{3}Y\s*/\s*\d{2,3})", hay)
    if m and not isinstance(contract.get("Voltage"), str):
        contract["Voltage"] = re.sub(r"\s", "", m.group(1)) + " V"


def _extract_equipment(doc, idx) -> Tuple[List[ExtractedEquipment], List[dict]]:
    from ..families import family_documents
    from ..inventory import family_and_symbol_names
    unit_of_family = {r["family_id"]: r["unit"]
                      for r in family_documents(idx) if r["unit"] is not None}
    out: List[ExtractedEquipment] = []
    skipped: List[dict] = []
    seen_tags: Dict[str, int] = {}
    for iid in doc.ids_of_class("FamilyInstance"):
        cat = doc.category_of(iid)
        if cat != OST_ELECTRICAL_EQUIPMENT:
            continue
        v = doc.value(iid) or {}
        ii = ((v.get("m_pInstanceInfo") or {}).get("value") or {})
        trf = ii.get("m_Trf") or {}
        orr = trf.get("m_or")
        r3 = trf.get("m_3x3")
        if not orr or not r3:
            skipped.append({"elem_id": iid, "why": "no InstanceInfo transform"})
            continue
        sym = ii.get("m_symbolId")
        fam_name, sym_name = family_and_symbol_names(doc, sym) if sym not in (None, -1) else (None, None)
        fam_id = (doc.value(sym) or {}).get("m_familyId") if sym not in (None, -1) else None
        unit = unit_of_family.get(fam_id)
        contract: Dict[str, Any] = {}
        srcs: List[str] = []
        if unit is not None:
            contract, srcs = _family_contract(idx, unit, sym_name)
        # instance-level AStrings override / fill
        pn = _astring_param(v, BIP_PANEL_NAME)
        mark = _astring_param(v, BIP_MARK)
        if pn:
            contract["PanelName"] = pn
            srcs.append("instance RBS_ELEC_PANEL_NAME")
        name = fam_name or sym_name or f"equipment {iid}"
        tag = str(contract.get("PanelName") or mark or "").strip()
        if not tag:
            # families without a PanelName param (e.g. the transformer) embed
            # the tag in the family name: 'Dry Type Transformer T1 75kVA ...'
            m = _TAG_TOKEN_RX.search(name or "")
            tag = m.group(1) if m else (name.split()[0] if name else f"EQ{iid}")
        if tag in seen_tags:                      # tags must be unique join keys
            seen_tags[tag] += 1
            tag = f"{tag}#{seen_tags[tag]}"
        else:
            seen_tags[tag] = 1
        kind = _classify(name, contract)
        _voltage_string(name, contract)
        famz = r3[2]
        notes: List[str] = []
        if abs(float(famz[2])) > 0.9:             # family +Z up => yaw transform
            frame_from_transform = "yaw"
            fx, fy = -float(r3[1][0]), -float(r3[1][1])   # front = -famY
        else:                                     # upright work-plane transform
            frame_from_transform = "upright"
            fx, fy = float(famz[0]), float(famz[1])       # front = famZ
        n = math.hypot(fx, fy)
        front = [fx / n, fy / n, 0.0] if n > 1e-9 else [0.0, -1.0, 0.0]
        # the EMITTED frame kind follows the resolver's kind vocabulary
        # (panelboards = wall gear / upright; switchboards, transformers,
        # everything else = floor gear / yaw), so the IFC box convention and
        # the round-trip recovery agree; the raw transform stays recorded
        frame_kind = ("upright" if kind in ("distribution_panelboard",
                                            "lighting_panelboard",
                                            "receptacle_panelboard", "panelboard")
                      else "yaw")
        if frame_kind != frame_from_transform:
            notes.append(f"instance transform is {frame_from_transform}-shaped "
                         f"but kind {kind!r} emits with the resolver's "
                         f"{frame_kind} convention (position = the family "
                         "origin either way)")
        dims: Dict[str, float] = {}
        for cap, dk in (("Width", "w"), ("Depth", "d"), ("Height", "h")):
            val = contract.get(cap)
            if isinstance(val, (int, float)) and float(val) > 0:
                dims[dk] = float(val)
        if not dims:
            notes.append("no Width/Depth/Height family params: emitter box "
                         "defaults (0.6 x 0.3 x 1.2 m) apply")
        eq = ExtractedEquipment(
            elem_id=iid, tag=tag, name=name, kind=kind,
            ifc_class=("IfcTransformer" if kind == "transformer"
                       else "IfcElectricDistributionBoard"),
            insertion_m=[float(orr[0]) * M_PER_FT, float(orr[1]) * M_PER_FT,
                         float(orr[2]) * M_PER_FT],
            front_normal=front, frame_kind=frame_kind, dims_m=dims,
            contract=contract, family_name=fam_name, symbol_name=sym_name,
            family_unit=unit, contract_source=srcs, notes=notes)
        if unit is None:
            eq.notes.append("no embedded family document resolved (system/"
                            "foreign family): identity from names only")
        out.append(eq)
    return out, skipped


def _conn_refs(v: dict) -> List[Tuple[int, List[Tuple[int, int, int]]]]:
    """[(connector index, [(target id, target index, connType), ...]), ...]"""
    mgr = ((v.get("m_pConnectorMgr") or v.get("m_pConnectorManager") or {})
           .get("value") or {})
    out = []
    for c in mgr.get("m_connPtrArray") or []:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        refs = [(int(r.get("m_id", -1)), int(r.get("m_nIndex", -1)),
                 int(r.get("m_connType", -1))) for r in cv.get("m_arrRefs") or []]
        out.append((int(cv.get("m_nIndex", -1)), refs))
    return out


def _extract_feeders(doc, equipment: List[ExtractedEquipment]) -> Tuple[list, Dict[str, Any]]:
    """Circuits (RbsElectricalSystem) -> FeederEdges between extracted
    equipment; everything else is counted, never faked."""
    from ..ifc.intent import FeederEdge
    by_id = {e.elem_id: e for e in equipment}
    edges: List = []
    stats = {"circuits_total": 0, "edges_between_equipment": 0,
             "circuits_to_other_loads": 0, "circuits_unresolved": 0}
    for cid in doc.ids_of_class("RbsElectricalSystem"):
        stats["circuits_total"] += 1
        v = doc.value(cid) or {}
        conns = _conn_refs(v)
        panel_id = None
        load_ids: List[int] = []
        for _idx, refs in conns:
            for tid, _tix, ctype in refs:
                if tid <= 0:
                    continue
                if ctype == 4 and panel_id is None:
                    panel_id = tid
                elif ctype != 4:
                    load_ids.append(tid)
        # single-connector-shape fallback: last conn's ref = the base equipment
        if panel_id is None and conns and conns[-1][1]:
            panel_id = conns[-1][1][0][0]
        if panel_id is None:
            stats["circuits_unresolved"] += 1
            continue
        panel = by_id.get(panel_id)
        if panel is None:
            stats["circuits_unresolved"] += 1
            continue
        matched = False
        for lid in load_ids:
            load = by_id.get(lid)
            if load is None:
                continue
            matched = True
            ed = FeederEdge(source=panel.tag, target=load.tag, kind="feeder",
                            from_pset=False,
                            rating_a=(float(v["m_dRating"]) if v.get("m_dRating") else None),
                            poles=(int(v["m_nPoles"]) if v.get("m_nPoles") else None))
            ed.notes.append(f"from circuit {cid} (number {v.get('m_number')!r})")
            edges.append(ed)
            if load.fed_from is None:
                load.fed_from = panel.tag
        if matched:
            stats["edges_between_equipment"] += 1
        else:
            stats["circuits_to_other_loads"] += 1
    return edges, stats


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

def source_provenance(rvt_path: str) -> Dict[str, Any]:
    """Lineage of the source model, read from its own BasicFileInfo."""
    from ..container import open_rvt
    from ..meta import parse_basic_file_info
    author = fmt = None
    try:
        with open_rvt(rvt_path) as f:
            bfi = parse_basic_file_info(f.raw("BasicFileInfo"))
        author = str(bfi.get("author") or "")
        fmt = str(bfi.get("format") or "")
    except Exception as e:                                     # noqa: BLE001
        return {"lineage": "unknown", "error": f"{type(e).__name__}: {e}",
                "foreign": True, "quarantined": quarantined_input(rvt_path)}
    ours = author.lower() in ("rvt-writer", "tekton")
    quarantined = quarantined_input(rvt_path)
    return {
        "author": author, "format": fmt,
        "lineage": ("tekton-authored (self-reported BasicFileInfo author)"
                    if ours else "foreign (native Revit save lineage)"),
        "foreign": not ours,
        "quarantined": quarantined,
    }


# ---------------------------------------------------------------------------
# the extraction
# ---------------------------------------------------------------------------

def extract_intent(rvt_path: str, *, max_walls: Optional[int] = None) -> ExtractedModel:
    """Read ``rvt_path`` back into the intent-shaped :class:`ExtractedModel`
    (under the file's own release; the whole read happens inside it)."""
    with ExitStack() as stack:
        if os.path.isfile(rvt_path):
            enter_own_release(stack, rvt_path)
        return _extract_intent(rvt_path, max_walls=max_walls)


def _extract_intent(rvt_path: str, *, max_walls: Optional[int]) -> ExtractedModel:
    if not os.path.isfile(rvt_path):
        raise RvtReadError(f"no such file: {rvt_path}")
    from ..families import FamilyIndex
    from ..inventory import wall_types
    from ..mutate import Document
    try:
        doc = Document.from_file(rvt_path)
        idx = FamilyIndex(rvt_path)
    except Exception as e:
        raise RvtReadError(f"cannot read {rvt_path}: {type(e).__name__}: {e}") from e

    model = ExtractedModel(project_name=doc.project, source_path=os.path.abspath(rvt_path))
    model.levels = _extract_levels(doc)

    wts = wall_types(doc)
    thick = {w["id"]: float(w["thickness_ft"]) * M_PER_FT
             for w in wts if w.get("thickness_ft")}
    tnames = {w["id"]: w.get("name") for w in wts}
    runs, wall_rows = _extract_walls(doc, thick, tnames, max_walls=max_walls)
    if runs:
        model.room = _Room(f"{doc.project} (extracted)", runs)

    model.equipment, eq_skipped = _extract_equipment(doc, idx)
    model.feeders, feeder_stats = _extract_feeders(doc, model.equipment)

    # the emitter takes levels[0] as THE storey: put the dominant level first
    lvl_use: Dict[Any, int] = {}
    for wid in doc.straight_walls():
        lid = (doc.value(wid) or {}).get("m_assocLevelId")
        lvl_use[lid] = lvl_use.get(lid, 0) + 1
    for e in model.equipment:
        lid = (doc.value(e.elem_id) or {}).get("m_assocLevelId")
        lvl_use[lid] = lvl_use.get(lid, 0) + 1
    if lvl_use and model.levels:
        dominant = max(lvl_use, key=lambda k: lvl_use[k])
        model.levels.sort(key=lambda l: (l.get("elem_id") != dominant,
                                         l["elevation"]))

    model.extraction = {
        "cells": {
            "levels": {"status": "works", "count": len(model.levels)},
            "walls": {"status": "works" if runs else
                      ("missing" if not doc.ids_of_class("SWall") else "partial"),
                      "count": len(runs), "detail": wall_rows},
            "equipment": {"status": "works" if model.equipment else "missing",
                          "count": len(model.equipment),
                          "skipped": eq_skipped},
            "feeders": {"status": ("works" if model.feeders else
                                   ("missing" if not feeder_stats["circuits_total"]
                                    else "partial")),
                        **feeder_stats},
        },
        "not_extracted": [
            "non-electrical-equipment categories (lighting fixtures, mechanical, "
            "doors, ...) are inventoried by rvt.inventory but not exported in v1",
            "curved walls / curtain walls (only straight GLine-driven SWalls export)",
        ],
    }
    return model


# ---------------------------------------------------------------------------
# the round trip (the acceptance)
# ---------------------------------------------------------------------------

def _point_seg_dist(p: Sequence[float], a: Sequence[float], b: Sequence[float]) -> float:
    ax, ay, bx, by = float(a[0]), float(a[1]), float(b[0]), float(b[1])
    px, py = float(p[0]), float(p[1])
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def roundtrip_table(model: ExtractedModel, ifc_path: str,
                    pos_tol_m: float = 0.005) -> Dict[str, Any]:
    """Re-resolve the emitted IFC with ``rvt.ifc.intent.resolve_intent`` and
    build the survival table (tags / kinds / positions / walls)."""
    try:
        from ..ifc.intent import resolve_intent
    except Exception as e:                                     # noqa: BLE001
        return {"ran": False, "why": f"resolver import failed: {e}"}
    try:
        back = resolve_intent(ifc_path)
    except Exception as e:                                     # noqa: BLE001
        return {"ran": False, "why": f"resolve_intent failed: {type(e).__name__}: {e}",
                "traceback": traceback.format_exc(limit=4)}
    rows: List[dict] = []
    ok_all = True
    for e in model.equipment:
        b = back.by_tag(e.tag)
        if b is None:
            rows.append({"tag": e.tag, "survived": False, "why": "tag missing"})
            ok_all = False
            continue
        dpos = [abs(b.insertion_m[i] - e.insertion_m[i]) for i in range(3)]
        dot = (b.front_normal[0] * e.front_normal[0]
               + b.front_normal[1] * e.front_normal[1])
        row = {"tag": e.tag, "kind_in": e.kind, "kind_out": b.kind,
               "kind_ok": b.kind == e.kind,
               "dpos_m": [round(x, 5) for x in dpos],
               "pos_ok": max(dpos) <= pos_tol_m,
               "front_ok": dot > 0.99,
               "survived": (b.kind == e.kind and max(dpos) <= pos_tol_m and dot > 0.99)}
        ok_all = ok_all and row["survived"]
        rows.append(row)
    walls_in = len(model.room.walls) if model.room else 0
    walls_out = len(back.room.walls) if back.room else 0
    # wall geometry: every extracted centerline survives when its MIDPOINT
    # lies on some resolved run's centerline (the resolver may merge
    # collinear segments / extend corners, so segment containment -- not
    # midpoint identity -- is the fair test)
    wall_match = 0
    if model.room and back.room:
        for w in model.room.walls:
            mid = ((w.p0_m[0] + w.p1_m[0]) / 2, (w.p0_m[1] + w.p1_m[1]) / 2)
            tol = max(w.thickness_m, 0.08)
            if any(_point_seg_dist(mid, bw.p0_m, bw.p1_m) <= tol
                   for bw in back.room.walls):
                wall_match += 1
    edges_in = {(ed.source, ed.target) for ed in model.feeders}
    edges_out = {(ed.source, ed.target) for ed in back.feeders}
    table = {
        "ran": True,
        "equipment": rows,
        "equipment_survived": f"{sum(1 for r in rows if r.get('survived'))}/{len(rows)}",
        "walls_in": walls_in, "walls_out": walls_out,
        "walls_matched": f"{wall_match}/{walls_in}",
        "feeder_edges_in": sorted(map(list, edges_in)),
        "feeder_edges_out_matched": sorted(map(list, edges_in & edges_out)),
        "feeder_edges_ok": edges_in <= edges_out,
        "all_survived": bool(ok_all and wall_match == walls_in
                             and edges_in <= edges_out),
    }
    return table


# ---------------------------------------------------------------------------
# THE ROUTE
# ---------------------------------------------------------------------------

def convert_rvt_to_ifc(rvt_path: str, out_ifc: Optional[str] = None, *,
                       out_dir: Optional[str] = None,
                       roundtrip: bool = True,
                       max_walls: Optional[int] = None) -> Dict[str, Any]:
    """RVT -> IFC4.  Extract, emit, round-trip-check, DELIVER (stamps after).

    Returns the manifest record; the IFC + ``<stem>.manifest.json`` /
    ``MANIFEST.md`` land beside it (``out_dir`` defaults to the IFC's
    directory).  The source's own release is entered once here, around the
    whole route; a fallback rung, if taken, is a caveat in the manifest."""
    with ExitStack() as stack:
        note = enter_own_release(stack, rvt_path) if os.path.isfile(rvt_path) else None
        return _convert_rvt_to_ifc(rvt_path, out_ifc, out_dir=out_dir,
                                   roundtrip=roundtrip, max_walls=max_walls,
                                   release_note=note)


def _convert_rvt_to_ifc(rvt_path: str, out_ifc: Optional[str], *,
                        out_dir: Optional[str], roundtrip: bool,
                        max_walls: Optional[int],
                        release_note: Optional[str]) -> Dict[str, Any]:
    from ..frontdoor.ifc_out import write_intent_ifc
    t0 = time.time()
    if out_ifc is None:
        stem = os.path.splitext(os.path.basename(rvt_path))[0]
        out_ifc = os.path.join(out_dir or os.path.dirname(os.path.abspath(rvt_path)),
                               stem + ".ifc")
    out_dir = out_dir or os.path.dirname(os.path.abspath(out_ifc)) or "."
    os.makedirs(out_dir, exist_ok=True)

    prov = source_provenance(rvt_path)
    rec: Dict[str, Any] = {
        "route": "rvt->ifc (rvt.convert.rvt_to_ifc)",
        "tool": TOOL, "tool_version": TOOL_VERSION,
        "input": {"path": _relp(rvt_path), "sha256": _sha256(rvt_path),
                  "provenance": prov},
        "files": {}, "stamps": [], "degradations": [], "errors": [],
    }
    if prov.get("foreign"):
        rec["stamps"].append(FOREIGN_CONTENT_STAMP)
    if prov.get("quarantined"):
        rec["stamps"].append(
            "QUARANTINED SOURCE (dev-only): the source is research-corpus / "
            "third-party sample content; this export exists to prove the "
            "converter works on foreign files and stays in experiments/.")
    if release_note:
        rec["degradations"].append(f"source release: {release_note}")

    try:
        model = _extract_intent(rvt_path, max_walls=max_walls)   # already in the release
        rec["extraction"] = model.extraction
        rec["levels"] = model.levels
        rec["equipment"] = [e.as_json() for e in model.equipment]
        rec["feeder_edges"] = [{"from": ed.source, "to": ed.target,
                                "rating_a": ed.rating_a, "poles": ed.poles}
                               for ed in model.feeders]
        note = (f"exported from {os.path.basename(rvt_path)} by {TOOL}"
                + (" -- FOREIGN design content, dev-only" if prov.get("foreign") else ""))
        write_intent_ifc(model, out_ifc, note=note)
        rec["files"]["ifc"] = out_ifc
    except Exception as e:                                     # noqa: BLE001
        rec["errors"].append(f"{type(e).__name__}: {e}")
        rec["errors"].append(traceback.format_exc(limit=8))
        _finish(rec, out_ifc, out_dir, t0)
        raise

    if roundtrip:
        rec["roundtrip"] = roundtrip_table(model, out_ifc)
        if not rec["roundtrip"].get("ran"):
            rec["degradations"].append("round-trip check did not run: "
                                       + str(rec["roundtrip"].get("why")))
        elif not rec["roundtrip"].get("all_survived"):
            rec["degradations"].append(
                "round-trip survival is PARTIAL -- see roundtrip table; the IFC "
                "is still delivered (the table is the honest label)")
    else:
        rec["degradations"].append("round-trip check skipped (--no-roundtrip)")

    _finish(rec, out_ifc, out_dir, t0)
    return rec


def _finish(rec: Dict[str, Any], out_ifc: str, out_dir: str, t0: float) -> None:
    rec["seconds"] = round(time.time() - t0, 1)
    files = {k: v for k, v in (rec.get("files") or {}).items()
             if v and os.path.isfile(str(v))}
    rec["deliverables"] = {
        role: {"path": _relp(p), "bytes": os.path.getsize(p), "sha256": _sha256(p)}
        for role, p in files.items()}
    stem = os.path.splitext(os.path.basename(out_ifc))[0]
    _jdump(os.path.join(out_dir, stem + ".manifest.json"), rec)
    lines = [f"# {rec['route']} -- deliverable manifest", ""]
    lines.append("## The deliverable(s)")
    for role, d in (rec["deliverables"] or {}).items():
        lines.append(f"* **{role}**: `{d['path']}` ({d['bytes']:,} bytes, "
                     f"sha256 {d['sha256'][:16]}...)")
    if not rec["deliverables"]:
        lines.append("* NO FILE PRODUCED -- see errors (nothing withheld)")
    lines.append("")
    lines.append("## Provenance")
    prov = (rec.get("input") or {}).get("provenance") or {}
    lines.append(f"* source lineage: {prov.get('lineage')}")
    lines.append("")
    if rec.get("stamps"):
        lines.append("## Stamps (labels, not refusals)")
        for s in rec["stamps"]:
            lines.append(f"* {s}")
        lines.append("")
    ex = (rec.get("extraction") or {}).get("cells") or {}
    if ex:
        lines.append("## Extraction cells (honest per-cell status)")
        for cell, st in ex.items():
            lines.append(f"* {cell}: **{st.get('status')}** "
                         + json.dumps({k: v for k, v in st.items()
                                       if k not in ("status", "detail", "skipped")},
                                      default=str))
        lines.append("")
    rt = rec.get("roundtrip") or {}
    if rt.get("ran"):
        lines.append("## Round-trip survival (the acceptance)")
        lines.append(f"* equipment: {rt.get('equipment_survived')} survived "
                     f"(tag + kind + position + front)")
        lines.append(f"* walls: {rt.get('walls_matched')} matched "
                     f"(in {rt.get('walls_in')}, resolved {rt.get('walls_out')})")
        lines.append(f"* feeder edges: {len(rt.get('feeder_edges_out_matched') or [])}"
                     f"/{len(rt.get('feeder_edges_in') or [])} matched")
        lines.append(f"* ALL SURVIVED: **{rt.get('all_survived')}**")
        for r in rt.get("equipment") or []:
            lines.append(f"  * {r.get('tag')}: kind {r.get('kind_in')} -> "
                         f"{r.get('kind_out')} pos-delta {r.get('dpos_m')} "
                         f"survived={r.get('survived')}")
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
        prog="rvt.convert.rvt_to_ifc",
        description="RVT -> IFC4: extract a project's content back to the "
                    "intent shape and emit IFC through the certified "
                    "intent->IFC emitter (round-trip checked).")
    ap.add_argument("rvt", help="the source .rvt")
    ap.add_argument("-o", "--out", default=None, help="output .ifc path")
    ap.add_argument("--out-dir", default=None,
                    help="output directory (default: beside the IFC)")
    ap.add_argument("--no-roundtrip", action="store_true",
                    help="skip the resolve_intent round-trip check")
    ap.add_argument("--max-walls", type=int, default=None,
                    help="cap the exported wall count (dev; excess reported)")
    a = ap.parse_args(argv)
    try:
        rec = convert_rvt_to_ifc(a.rvt, a.out, out_dir=a.out_dir,
                                 roundtrip=not a.no_roundtrip,
                                 max_walls=a.max_walls)
    except (ConvertError, RvtReadError) as e:
        print(f"ERROR: {e}")
        return 2
    d = rec.get("deliverables") or {}
    rt = rec.get("roundtrip") or {}
    print(f"delivered: {json.dumps({k: v.get('path') for k, v in d.items()})}")
    if rt.get("ran"):
        print(f"round trip: equipment {rt.get('equipment_survived')}, walls "
              f"{rt.get('walls_matched')}, all_survived={rt.get('all_survived')}")
    for s in rec.get("stamps") or []:
        print(f"STAMP: {s}")
    for w in rec.get("degradations") or []:
        print(f"caveat: {w}")
    return 0


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
