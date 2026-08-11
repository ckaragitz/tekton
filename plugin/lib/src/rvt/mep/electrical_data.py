"""electrical_data.py — WIRING + ELECTRICAL SETTINGS + PANEL DATA (MEP stream).

Full create / read / modify / delete over the electrical-data slice of a
Revit MEP project, on top of the proven writer core (``rvt.mutate`` for
new elements, ``rvt.manipulate`` for in-place edits, one combined commit
here):

WIRES (``RbsWireCurve``, category ``OST_Wire`` = -2008039) — the arcs /
chamfers drawn on plans between fixtures and back to the panel (home runs).
    read      wires(doc) / wire_info(doc, wid)
    create    add_wire(doc, circuits, from_device, to_device=None, ...)
              (``to_device=None`` -> HOME RUN: a free arrow end pointing to
              the panel;  a device at both ends -> a branch wire)
    delete    delete_wire(doc, wid)             (cascades the wire tag,
              neutralises the devices' connector back-links)

ELECTRICAL SETTINGS as EDITABLE data:
    read      electrical_settings(doc)  -> voltage types, distribution
              systems, wire types (+ material / insulation / temperature
              rating), demand factors, load classifications, the
              ElectricalSetting / RbsWireSettingsElem singletons
    create    add_voltage_type / add_distribution_system / add_demand_factor
              / add_load_classification (+ its 6 parameter elements)
    modify    set_demand_factor / set_voltage_type / rename_setting /
              modify_setting (generic field edit) -> ModifyPlan

PANEL DATA integrity:
    read      panels(doc) / panel_info(doc, panel) / panel_circuits(doc, panel)
              check_panel_numbering(doc, panel)   (gaps / overlaps / parity)
    modify    renumber_circuits(doc, panel)  -> the circuits' m_number /
              m_nStartSlot re-laid-out with Revit's own two-column rule
              (proven to reproduce Autodesk's numbering on the untouched
              panels of the sample byte-for-byte in value)

COMMIT / VERIFY (create + edit + delete in ONE re-emit of save-unit 0):
    commit_electrical(src_rvt, out_path, doc, new_elements=..., plans=...)
    verify_electrical(path, new_ids=..., edited_ids=..., deleted_ids=...)

Every recipe here is derived from real specimens in the Revit MEP sample
(``rmebasicsampleproject``: 1,045 wires, 187 circuits, 20 panels, 5 voltage
types, 3 distribution systems, 12 demand factors, 10 load classifications);
see ``docs/writer/mep-electrical-data.md`` for the decoded model, the
evidence and the confidence per claim.

CLI::

    python -m rvt.mep.electrical_data samples/rmebasicsampleproject.rvt settings
    python -m rvt.mep.electrical_data samples/rmebasicsampleproject.rvt wires [n]
    python -m rvt.mep.electrical_data samples/rmebasicsampleproject.rvt panels
    python -m rvt.mep.electrical_data samples/rmebasicsampleproject.rvt panel 622027
"""
from __future__ import annotations

import copy
import dataclasses
import json
import math
import re
import struct
import sys
import uuid
import zlib
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .. import commit as _commit
from .. import ecc
from .. import inventory as inv
from .. import manipulate as M
from .. import stream_encoders as SE
from ..commit import PART_HDR_COUNT_OFF
from ..container import open_rvt
from ..manipulate import (BLOCK_BUDGET, DeletePlan, FieldChange, ModifyPlan,
                          apply_edits_to_segment, chunk_segment)
from ..mutate import (CLASS_GELEMENT, CLASS_SERIALIZED_DUMMY, Document,
                      ElemRecPlan, NewElement)
from ..partitions import StreamWalker
from ..roundtrip import rewrite_entries
from ..stream_encoders import global_prefix
from ..streams_edit import elemtable_add_element
from ..writer import gzip_member

# decode/encode_elemtable and _assert_sentinel_tail are read via ``SE.`` /
# ``_commit.`` at call time: records32.ids32() rebinds them BY NAME there (#467)

# ---------------------------------------------------------------------------
# constants (all corpus-verified against rmebasicsampleproject unless [H])
# ---------------------------------------------------------------------------

#: classes owned by this stream (schema names)
CLS_WIRE = "RbsWireCurve"
CLS_CIRCUIT = "RbsElectricalSystem"
CLS_VOLTAGE = "RbsVoltageType"
CLS_DIST_SYS = "RbsDistributionSysType"
CLS_WIRE_TYPE = "RbsWireType"
CLS_WIRE_MATERIAL = "RbsWireMaterialType"
CLS_WIRE_INSULATION = "RbsWireInsulationType"
CLS_WIRE_TEMP = "RbsWireTemperatureRatingType"
CLS_WIRE_SIZES = "RbsWireSizesElem"
CLS_WIRE_SETTINGS = "RbsWireSettingsElem"
CLS_DEMAND_FACTOR = "ElectricalDemandFactorDefinition"
CLS_LOAD_CLASS = "ElectricalLoadClassification"
CLS_LOAD_CLASS_PARAM = "ParamElemElectricalLoadClassification"
CLS_ELEC_SETTING = "ElectricalSetting"
CLS_SYSTEM_TRACKER = "MEPSystemTracker"

#: built-in categories (OST_*)
OST_Wire = -2008039
OST_ElectricalEquipment = -2001040
OST_ElectricalFixtures = -2001060
OST_LightingFixtures = -2001120
OST_ElectricalCircuit = -2008087            # switch systems / devices
OST_ElecDistributionSys = -2008041
OST_VoltageType = -2008040
OST_DemandFactor = -2008142
OST_LoadClassification = -2008143

#: built-in parameters
BIP_ALL_MODEL_MARK = -1001203               # wire / instance 'Mark' (AString)
BIP_RBS_ELEC_PANEL_NAME = -1140078          # panel name (AString)
BIP_ELEC_WIRE_NUM_CONDUCTORS = -1140107     # int, 4 on every corpus wire [H name]
BIP_ELEC_PANEL_DIST_SYSTEM = -1140064       # ElementId -> RbsDistributionSysType
BIP_ELEC_PANEL_MAINS = -1140082             # FamilyParams double (100.0 A) [H name]
BIP_ELEC_PANEL_MAX_POLES = -1140079         # FamilyParams int (12) [H name]

#: connector reference kinds (Connector.m_arrRefs[].m_connType)
CONN_LOGICAL = 1     # wire<->device, wire end<->its sibling end
CONN_SYSTEM = 4      # circuit<->device / circuit<->panel slot back-links

#: Revit WiringType enum (RbsWireCurve.m_eType); every corpus wire is an arc
WIRING_ARC = 0       # [V] 1,045/1,045 corpus wires
WIRING_CHAMFER = 1   # [H] Revit API WiringType::Chamfer

#: internal-unit conversion: Revit stores electrical potential and apparent
#: power in feet-based internal units (kg*ft^2/(s^3*A) etc.), i.e. the SI
#: value divided by 0.3048^2 (verified: 240 V -> 2583.3385, 10 kVA -> 107639.10)
FT2 = 0.3048 ** 2                            # 0.09290304

DEG = math.pi / 180.0


# ===========================================================================
# 0 · units
# ===========================================================================
def volts_to_internal(v: float) -> float:
    """SI volts -> Revit internal electrical-potential units (V / 0.3048^2)."""
    return float(v) / FT2


def internal_to_volts(x: Optional[float]) -> Optional[float]:
    return None if x is None else float(x) * FT2


def va_to_internal(va: float) -> float:
    """Volt-amperes (or watts) -> internal apparent-power units (VA / 0.3048^2)."""
    return float(va) / FT2


def internal_to_va(x: Optional[float]) -> Optional[float]:
    return None if x is None else float(x) * FT2


# ===========================================================================
# 1 · small decoded-dict helpers
# ===========================================================================
def _v(x):
    """Unwrap an owned-pointer holder {'ptr_class','pid','value'} -> value dict."""
    if isinstance(x, dict) and "value" in x and isinstance(x.get("value"), dict):
        return x["value"]
    return x if isinstance(x, dict) else {}


def _symname(v: dict) -> Optional[str]:
    """A *Type element's name (m_symbolInfo.m_name)."""
    si = _v(v.get("m_symbolInfo"))
    n = si.get("m_name")
    return n if isinstance(n, str) else None


def _conn_manager(v: dict) -> Optional[dict]:
    for key in ("m_pConnectorManager", "m_pConnectorMgr"):
        h = v.get(key)
        if isinstance(h, dict) and isinstance(h.get("value"), dict):
            return h["value"]
    return None


def connectors(v: dict) -> Dict[int, List[Tuple[int, int, int]]]:
    """{connector nIndex: [(target_id, target_index, connType), ...]}."""
    mgr = _conn_manager(v) or {}
    out: Dict[int, List[Tuple[int, int, int]]] = {}
    for c in mgr.get("m_connPtrArray") or []:
        cv = _v(c)
        idx = cv.get("m_nIndex")
        if not isinstance(idx, int):
            continue
        refs = []
        for r in cv.get("m_arrRefs") or []:
            if isinstance(r, dict) and isinstance(r.get("m_id"), int):
                refs.append((r["m_id"], r.get("m_nIndex"), r.get("m_connType", 0)))
        out.setdefault(idx, []).extend(refs)
    return out


def _connector_dict(v: dict, index: int) -> Optional[dict]:
    """The mutable Connector value dict with m_nIndex == index."""
    mgr = _conn_manager(v) or {}
    for c in mgr.get("m_connPtrArray") or []:
        cv = _v(c)
        if cv.get("m_nIndex") == index:
            return cv
    return None


def _elem_id(x: Union[int, NewElement, None]) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, NewElement):
        return x.elem_id
    return int(x)


def _astring_param(v: dict, param_id: int) -> Optional[str]:
    ps = _v(v.get("m_pParamValueSetAString")).get("m_paramSet") or []
    for p in ps:
        if isinstance(p, dict) and p.get("m_paramId") == param_id:
            s = p.get("m_value")
            return s if isinstance(s, str) else None
    return None


def _set_astring_param(v: dict, param_id: int, value: str) -> None:
    M.upsert_param_row(v, param_id, value, holder="m_pParamValueSetAString")


def _elementid_param(v: dict, param_id: int) -> Optional[int]:
    ps = _v(v.get("m_pParamValueSetElementId")).get("m_paramSet") or []
    for p in ps:
        if isinstance(p, dict) and p.get("m_paramId") == param_id:
            return p.get("m_value")
    return None


def _double_param(v: dict, param_id: int) -> Optional[float]:
    ps = _v(v.get("m_pParamValueSetDouble")).get("m_paramSet") or []
    for p in ps:
        if isinstance(p, dict) and p.get("m_paramId") == param_id:
            return p.get("m_value")
    return None


def _instparam(v: dict, param_id: int):
    """A FamilyParams entry (m_str / m_value / m_int) by id, or None."""
    for p in (_v(v.get("m_pInstParams")).get("m_params") or []):
        if isinstance(p, dict) and p.get("m_paramId") == param_id:
            return p
    return None


def _instance_origin(v: dict) -> Optional[List[float]]:
    ii = _v(v.get("m_pInstanceInfo"))
    t = (ii.get("m_Trf") or {}).get("m_or")
    if t:
        return [float(t[0]), float(t[1]), float(t[2])]
    o = v.get("m_instOrigin")
    if o:
        return [float(o[0]), float(o[1]), float(o[2])]
    return None


def _one(doc: Document, cls: str) -> Optional[int]:
    ids = doc.ids_of_class(cls)
    return ids[0] if ids else None


# ===========================================================================
# 2 · READ: electrical settings inventory
# ===========================================================================
def voltage_types(doc: Document) -> List[dict]:
    """Every ``RbsVoltageType``: name + nominal / min / max volts (SI)."""
    out = []
    for i in doc.ids_of_class(CLS_VOLTAGE):
        v = doc.value(i) or {}
        out.append({
            "id": i, "name": _symname(v),
            "volts": internal_to_volts(v.get("m_dActualVoltage")),
            "min_volts": internal_to_volts(v.get("m_dMinVoltage")),
            "max_volts": internal_to_volts(v.get("m_dMaxVoltage")),
        })
    out.sort(key=lambda r: (r["volts"] or 0.0))
    return out


def distribution_systems(doc: Document) -> List[dict]:
    """Every ``RbsDistributionSysType``: name, phase/config/wires, resolved
    line-line / line-ground voltages (via m_idVll / m_idVlg -> RbsVoltageType)."""
    vt = {r["id"]: r for r in voltage_types(doc)}
    out = []
    for i in doc.ids_of_class(CLS_DIST_SYS):
        v = doc.value(i) or {}
        vll, vlg = v.get("m_idVll"), v.get("m_idVlg")
        out.append({
            "id": i, "name": _symname(v),
            "phase": {0: "single", 1: "three"}.get(v.get("m_kPhase"), v.get("m_kPhase")),
            "config": {0: "single/other", 1: "wye"}.get(v.get("m_kConfig"), v.get("m_kConfig")),
            "num_wires": v.get("m_iNumWires"),
            "high_leg_phase": v.get("m_highLegPhase"),
            "vll_id": vll, "vll": (vt.get(vll) or {}).get("volts"),
            "vlg_id": vlg, "vlg": (vt.get(vlg) or {}).get("volts"),
        })
    return out


def _named(doc: Document, eid) -> Optional[str]:
    """Name of a settings-domain element: a *Type's m_symbolInfo.m_name, a
    definition's m_name, or a Revit-2026 ``CustomElement`` conductor
    material / insulation / temperature / size (its ``NamingCell.m_name``)."""
    v = doc.value(eid) if isinstance(eid, int) and eid > 0 and doc.exists(eid) else None
    if not v:
        return None
    n = _symname(v)
    if n:
        return n
    if isinstance(v.get("m_name"), str):
        return v["m_name"]
    for cell in (_v(v.get("m_cellList")).get("m_cells") or []):
        cv = _v(cell)
        if cell.get("ptr_class") == "NamingCell" and isinstance(cv.get("m_name"), str):
            return cv["m_name"]
    return None


def wire_types(doc: Document) -> List[dict]:
    """``RbsWireType`` s with material / insulation / temperature names resolved
    (in Revit 2026 those point at ``CustomElement`` conductor definitions
    whose name lives in a ``NamingCell``)."""
    def name_of(eid):
        return _named(doc, eid)
    out = []
    for i in doc.ids_of_class(CLS_WIRE_TYPE):
        v = doc.value(i) or {}
        out.append({
            "id": i, "name": _symname(v),
            "material_id": v.get("m_idMaterial"), "material": name_of(v.get("m_idMaterial")),
            "insulation_id": v.get("m_idInsulation"), "insulation": name_of(v.get("m_idInsulation")),
            "temperature_rating_id": v.get("m_idTempratureRating"),
            "temperature_rating": name_of(v.get("m_idTempratureRating")),
            "max_conductor_size_id": v.get("m_idMaxConductorSize"),
            "conduit_type": v.get("m_strConduitType"),
            "neutral_multiplier": v.get("m_dNeutralMultiplier"),
            "neutral_mode": v.get("m_eNeutralMode"),
            "neutral_in_balanced_load": v.get("m_bNeutralIncludedInBalancedLoad"),
            "share_neutral": v.get("m_bShareNeutral"),
            "share_ground": v.get("m_bShareGround"),
        })
    return out


def wire_type_domains(doc: Document) -> dict:
    """The wire-type value domains: materials, insulations, temperature ratings."""
    def rows(cls):
        return [{"id": i, "name": _symname(doc.value(i) or {})}
                for i in doc.ids_of_class(cls)]
    return {"materials": rows(CLS_WIRE_MATERIAL),
            "insulations": rows(CLS_WIRE_INSULATION),
            "temperature_ratings": rows(CLS_WIRE_TEMP)}


def demand_factors(doc: Document) -> List[dict]:
    """Every ``ElectricalDemandFactorDefinition``: name, rule type, factor
    table (ranges converted from internal apparent-power units to VA)."""
    out = []
    for i in doc.ids_of_class(CLS_DEMAND_FACTOR):
        v = doc.value(i) or {}
        vals = []
        for x in v.get("m_values") or []:
            hi = x.get("m_maxRange")
            vals.append({
                "factor": x.get("m_factor"),
                "min": internal_to_va(x.get("m_minRange")),
                "max": (None if (hi is None or hi >= 1e29) else internal_to_va(hi)),
            })
        out.append({
            "id": i, "name": v.get("m_name"),
            "rule_type": v.get("m_ruleType"),           # 0 constant, 3 per-object rank, 4 load range
            "values": vals,
            "additional_load": internal_to_va(v.get("m_additionalLoad")),
            "include_additional_load": v.get("m_includeAdditionalLoad"),
        })
    return out


LOAD_CLASS_PARAM_FIELDS = (
    "m_totalLoadParamElemId",       # '<name> Connected Apparent Power'
    "m_estLoadParamElemId",         # '<name> Demand Apparent Power'
    "m_totalCurrentParamElemId",    # '<name> Connected Current'
    "m_estCurrentParamElemId",      # '<name> Estimated Demand Current'
    "m_demandFactorParamElemId",    # '<name> Demand Factor'
    "m_actualSpaceLoadParamElemId",  # 'Actual <name> Load'
)


def load_classifications(doc: Document) -> List[dict]:
    """Every ``ElectricalLoadClassification`` with its demand factor and its
    six ``ParamElemElectricalLoadClassification`` parameter elements."""
    df = {r["id"]: r for r in demand_factors(doc)}
    out = []
    for i in doc.ids_of_class(CLS_LOAD_CLASS):
        v = doc.value(i) or {}
        dfid = v.get("m_demandFactorId")
        out.append({
            "id": i, "name": v.get("m_name"), "abbreviation": v.get("m_abbreviation"),
            "demand_factor_id": dfid,
            "demand_factor": (df.get(dfid) or {}).get("name"),
            "param_elem_ids": {k: v.get(k) for k in LOAD_CLASS_PARAM_FIELDS},
            "signature_type": v.get("m_signitureType"),
            "space_load_class": v.get("m_spaceLoadClass"),
        })
    return out


def electrical_settings(doc: Document) -> dict:
    """The whole electrical-settings inventory of a document (READ)."""
    es = None
    esid = _one(doc, CLS_ELEC_SETTING)
    if esid is not None:
        v = doc.value(esid) or {}
        es = {
            "id": esid,
            "circuit_name_phases": [v.get("m_circuitNamePhaseA"), v.get("m_circuitNamePhaseB"),
                                    v.get("m_circuitNamePhaseC")],
            "space_label": v.get("m_spaceLabel"), "spare_label": v.get("m_spareLabel"),
            "circuit_rating": v.get("m_circuitRating"),
            "circuit_path_offset_ft": v.get("m_circuitPathOffset"),
            "include_spares_in_totals": v.get("m_isIncludeSparesInPanelTotals"),
            "circuit_load_calc_method": v.get("m_circuitLoadCalculationMethod"),
            "merge_multipoled_circuits": v.get("m_mergeMultiPoledCircuitsIntoSingleCell"),
        }
    ws = None
    wsid = _one(doc, CLS_WIRE_SETTINGS)
    if wsid is not None:
        v = doc.value(wsid) or {}
        ws = {
            "id": wsid,
            "connector_separator": v.get("m_strElectricalConnectorSeparator"),
            "crossing_gap_ft": v.get("m_dWiringCrossingGap"),
            "home_run_arrow_leader_style": v.get("m_idWireHomeRunArrowLeaderStyle"),
            "show_tick_marks": v.get("m_eShowTickMarks"),
            "tick_mark_style": v.get("m_nWireTickMarkStyle"),
        }
    return {
        "voltage_types": voltage_types(doc),
        "distribution_systems": distribution_systems(doc),
        "wire_types": wire_types(doc),
        "wire_type_domains": wire_type_domains(doc),
        "demand_factors": demand_factors(doc),
        "load_classifications": load_classifications(doc),
        "electrical_setting": es,
        "wire_settings": ws,
    }


# ===========================================================================
# 3 · READ: circuits, panels, wires
# ===========================================================================
def circuit_panel(doc: Document, circuit_id: int) -> Optional[Tuple[int, int]]:
    """(panel_id, panel_slot_connector) feeding a circuit, else None.

    A circuit's LAST connector references its base equipment (the panel) at
    one of the panel's 50000-series slot connectors with connType 4."""
    cc = connectors(doc.value(circuit_id) or {})
    if not cc:
        return None
    last = cc.get(max(cc)) or []
    for (t, ti, ct) in last:
        if ct == CONN_SYSTEM and t != circuit_id:
            return (t, ti)
    return None


def circuit_loads(doc: Document, circuit_id: int) -> List[Tuple[int, int]]:
    """[(load_element, its_connector_index)] for a circuit (every connector
    except the last / panel one)."""
    cc = connectors(doc.value(circuit_id) or {})
    if not cc:
        return []
    hi = max(cc)
    out = []
    for i in sorted(cc):
        if i == hi:
            continue
        for (t, ti, ct) in cc[i]:
            if t != circuit_id:
                out.append((t, ti))
    return out


def circuits_of_panel(doc: Document, panel_id: int) -> List[int]:
    """All ``RbsElectricalSystem`` s whose base equipment is ``panel_id``."""
    out = []
    for cid in doc.ids_of_class(CLS_CIRCUIT):
        p = circuit_panel(doc, cid)
        if p and p[0] == panel_id:
            out.append(cid)
    return out


def panels(doc: Document) -> List[dict]:
    """Every host-document panelboard = electrical equipment that feeds at
    least one circuit or exposes 50000-series slot connectors."""
    fed = set()
    for cid in doc.ids_of_class(CLS_CIRCUIT):
        p = circuit_panel(doc, cid)
        if p:
            fed.add(p[0])
    out = []
    for eid in doc.ids_of_class("FamilyInstance"):
        if doc.category_of(eid) != OST_ElectricalEquipment:
            continue
        v = doc.value(eid) or {}
        idx = [i for i in connectors(v) if isinstance(i, int)]
        slots = [i for i in idx if i >= 50000]
        if eid not in fed and not slots:
            continue
        out.append(panel_info(doc, eid, _v_cache=v))
    return out


def panel_info(doc: Document, panel_id: int, *, _v_cache: Optional[dict] = None) -> dict:
    """A panel's own data: name, mark, family/type, mains rating, its
    distribution system + resolved voltages, slot connectors, circuit count."""
    v = _v_cache or (doc.value(panel_id) or {})
    ii = _v(v.get("m_pInstanceInfo"))
    sym = ii.get("m_symbolId")
    fam, typ = inv.family_and_symbol_names(doc, sym) if sym else (None, None)
    ds_id = _elementid_param(v, BIP_ELEC_PANEL_DIST_SYSTEM)
    ds = next((d for d in distribution_systems(doc) if d["id"] == ds_id), None)
    mains = _instparam(v, BIP_ELEC_PANEL_MAINS)
    poles = _instparam(v, BIP_ELEC_PANEL_MAX_POLES)
    idx = [i for i in connectors(v) if isinstance(i, int)]
    dpm = _v(v.get("m_pDesignPropManager"))
    return {
        "id": panel_id,
        "name": _astring_param(v, BIP_RBS_ELEC_PANEL_NAME),
        "mark": _astring_param(v, BIP_ALL_MODEL_MARK),
        "family": fam, "type": typ, "symbol_id": sym,
        "mains_rating_a": (mains or {}).get("m_value") if mains else None,
        "max_poles": (poles or {}).get("m_int") if poles else None,
        "distribution_system_id": ds_id,
        "distribution_system": (ds or {}).get("name"),
        "voltage_ll": (ds or {}).get("vll"), "voltage_lg": (ds or {}).get("vlg"),
        "slot_connectors": sorted(i for i in idx if i >= 50000),
        "supply_connector": min(idx) if idx else None,
        "circuit_numbering_option": dpm.get("m_eCircuitNumberingOption"),
        "n_circuits": len(circuits_of_panel(doc, panel_id)),
    }


def panel_circuits(doc: Document, panel_id: int) -> List[dict]:
    """The circuits fed by a panel, in schedule order (start slot, id)."""
    rows = []
    for cid in circuits_of_panel(doc, panel_id):
        v = doc.value(cid) or {}
        p = circuit_panel(doc, cid) or (None, None)
        rows.append({
            "id": cid,
            "number": v.get("m_number"),
            "start_slot": v.get("m_nStartSlot"),
            "poles": v.get("m_nPoles"),
            "panel_slot_connector": p[1],
            "rating_a": v.get("m_dRating"),
            "load_name": v.get("m_strDescription"),
            "load_classifications": v.get("m_strLoadClassifications"),
            "apparent_load_va": internal_to_va(v.get("m_dApparentLoad")),
            "circuit_conn_type": v.get("m_circuitConnType"),
            "system_type": v.get("m_systemType"),
        })
    rows.sort(key=lambda r: ((r["start_slot"] if isinstance(r["start_slot"], int) else 0), r["id"]))
    return rows


def _slots_of(number: Any, start: Any, poles: Any) -> List[int]:
    """The slot list a circuit occupies: parse '20,22,24' else start + parity."""
    if isinstance(number, str) and number.strip():
        try:
            got = [int(x) for x in re.split(r"[,\s]+", number.strip()) if x != ""]
            if got:
                return got
        except ValueError:
            pass
    n = max(1, int(poles or 1))
    s = int(start or 0)
    return [s + 2 * k for k in range(n)]


def check_panel_numbering(doc: Document, panel_id: int) -> dict:
    """Panel-schedule integrity report for the circuits' slot layout
    (m_number / m_nStartSlot / m_nPoles).

    HARD errors (``consistent == False``): overlapping slots, a multi-pole
    circuit spanning both columns (mixed parity), or a circuit whose
    ``m_number`` string disagrees with its ``m_nStartSlot`` / pole count.
    Empty slots below the highest used slot are SPACES (legal — a schedule
    need not be full); ``compact`` says whether the layout already equals
    the packed re-layout :func:`renumber_circuits` would produce.
    """
    rows = panel_circuits(doc, panel_id)
    used: Dict[int, List[int]] = {}
    parity_bad = []
    numstr_bad = []
    for r in rows:
        slots = _slots_of(r["number"], r["start_slot"], r["poles"])
        if r["poles"] and len(slots) != int(r["poles"]):
            numstr_bad.append(r["id"])
        if len(slots) > 1 and len({s % 2 for s in slots}) > 1:
            parity_bad.append(r["id"])
        if isinstance(r["start_slot"], int) and slots and slots[0] != r["start_slot"]:
            numstr_bad.append(r["id"])
        for s in slots:
            used.setdefault(s, []).append(r["id"])
    overlaps = {s: ids for s, ids in used.items() if len(ids) > 1}
    hi = max(used) if used else 0
    spaces = [s for s in range(1, hi + 1) if s not in used] if used else []
    laid = layout_circuits(rows) if rows else []
    compact = all((r.get("number") or "") == r["new_number"]
                  and r.get("start_slot") == r["new_start_slot"] for r in laid)
    return {
        "panel": panel_id, "circuits": len(rows),
        "slots_used": sorted(used), "highest_slot": hi,
        "spaces": spaces, "overlaps": overlaps,
        "parity_violations": parity_bad,        # multi-pole spanning both columns
        "number_string_mismatch": sorted(set(numstr_bad)),
        "compact": bool(compact),
        "consistent": (not overlaps and not parity_bad and not numstr_bad),
    }


# --- wires -----------------------------------------------------------------
def wire_info(doc: Document, wid: int, *, _v_cache: Optional[dict] = None) -> dict:
    """One wire: view, type, circuits, its two ends (device + connector or
    free) and its point path.  ``home_run`` = exactly one connected end."""
    v = _v_cache or (doc.value(wid) or {})
    cc = connectors(v)
    ends = []
    for i in (0, 1):
        tgt = None
        for (t, ti, ct) in cc.get(i, []):
            if t != wid:
                tgt = {"device": t, "connector": ti, "conn_type": ct,
                       "class": doc.class_of(t)}
        ends.append(tgt)
    dpm = _v(v.get("m_pDesignPropManager"))
    connected = [e for e in ends if e]
    return {
        "id": wid,
        "view": v.get("m_ownerDBViewId"),
        "level": v.get("m_assocLevelId"),
        "wire_type": v.get("m_idType"),
        "circuits": list(dpm.get("m_setidCircuits") or []),
        "wiring": "arc" if v.get("m_eType") == WIRING_ARC else "chamfer",
        "points_ft": v.get("m_rgPoints"),
        "start": ends[0], "end": ends[1],
        "home_run": len(connected) == 1,
        "unconnected": len(connected) == 0,
        "mark": _astring_param(v, BIP_ALL_MODEL_MARK),
    }


def wires(doc: Document, limit: Optional[int] = None) -> List[dict]:
    out = []
    for wid in doc.ids_of_class(CLS_WIRE):
        out.append(wire_info(doc, wid))
        if limit is not None and len(out) >= limit:
            break
    return out


def wires_of_circuit(doc: Document, circuit_id: int) -> List[int]:
    """Wires whose design-property manager lists ``circuit_id``."""
    out = []
    for wid in doc.ids_of_class(CLS_WIRE):
        dpm = _v((doc.value(wid) or {}).get("m_pDesignPropManager"))
        if circuit_id in (dpm.get("m_setidCircuits") or []):
            out.append(wid)
    return out


def device_supply_connector(doc: Document, device: int) -> int:
    """The connector index other wires attach to on a device (1 on every
    corpus specimen); falls back to the lowest small index."""
    idx = sorted(i for i in connectors(doc.value(device) or {})
                 if isinstance(i, int) and 0 <= i < 1000)
    if 1 in idx:
        return 1
    return idx[0] if idx else 1


def device_connector_position(doc: Document, device: int, conn_index: int = 1,
                              *, exclude_wire: Optional[int] = None) -> Optional[List[float]]:
    """Best world position (ft) of a device connector for wiring endpoints.

    Exact when another wire already ends on that connector (its endpoint IS
    the connector position); otherwise the instance origin (Revit re-snaps
    the wire end onto the connector on regeneration)."""
    for wid in doc.ids_of_class(CLS_WIRE):
        if wid == exclude_wire:
            continue
        v = doc.value(wid) or {}
        pts = v.get("m_rgPoints") or []
        if not pts:
            continue
        cc = connectors(v)
        for i, refs in cc.items():
            for (t, ti, ct) in refs:
                if t == device and ti == conn_index and ct == CONN_LOGICAL:
                    p = pts[0] if i == 0 else pts[-1]
                    return [float(p[0]), float(p[1]), float(p[2])]
    return _instance_origin(doc.value(device) or {})


# ===========================================================================
# 4 · CREATE: cloning helpers
# ===========================================================================
def _clone_records(doc: Document, tpl: int) -> Tuple[dict, dict, Optional[dict]]:
    """Deep copies of a specimen's (object, header, rep-or-None)."""
    obj = copy.deepcopy(doc.value(tpl))
    hdr = copy.deepcopy(doc.value(tpl, 101)) or {}
    rep = None
    trep = doc.decode(tpl, 103)
    if trep is not None and trep.class_id == CLASS_GELEMENT and trep.clean:
        rep = copy.deepcopy(trep.value)
    return obj, hdr, rep


def _reset_identity(obj: dict, eid: int) -> None:
    """Standard identity/state fields of any new host-document element."""
    obj["m_id"] = eid
    obj["m_famId"] = -1
    obj["m_unplacedOwnerId"] = -1
    obj["m_designOptionId"] = -1
    obj["m_locked"] = False
    obj["m_moribund"] = False
    obj["m_dummy"] = False


def _finish_header(header: dict, *, deletion: Iterable[int], regen_only=(),
                   appearance=(), deferred=(), nondeterm: bool = False) -> dict:
    """Rebuild an ElementHeader's ElementParents lists for a NEW element."""
    header["m_regenHistory"] = {"m_historyMap": []}
    parents = _v(header.get("m_parents"))
    parents.update({
        "m_deletion": sorted({int(x) for x in deletion if x is not None}),
        "m_regenOnly": sorted({int(x) for x in regen_only if x is not None and int(x) > 0}),
        "m_regenWildcards": [],
        "m_nonDetermRegenChildren": [],
        "m_dependencyParents": [],
        "m_appearanceParents": sorted({int(x) for x in appearance
                                       if x is not None and int(x) > 0}),
        "m_deferredParents": sorted({int(x) for x in deferred if x is not None and int(x) > 0}),
        "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
        "m_hasNonDetermRegenChildren": bool(nondeterm),
    })
    if isinstance(header.get("m_parents"), dict):
        header["m_parents"]["value"] = parents
    header["m_pBBox"] = None
    return header


def _register(doc: Document, eid: int, kind: str, class_name: str,
              header: dict, obj: dict, rep: Optional[dict], tpl: int,
              notes: List[str]) -> NewElement:
    class_id = doc.dec.schema.by_name[class_name].type_id
    el = NewElement(eid, kind, class_name, class_id, header, obj, rep,
                    doc._new_elemrec(eid), tpl, notes=notes)
    doc.new_elements.append(el)
    return el


# ===========================================================================
# 5 · CREATE: electrical settings
# ===========================================================================
def add_voltage_type(doc: Document, name: str, volts: float,
                     min_volts: Optional[float] = None,
                     max_volts: Optional[float] = None,
                     template_id: Optional[int] = None) -> NewElement:
    """Plan a new voltage definition (``RbsVoltageType``, e.g. '347')."""
    tpl = template_id or _one(doc, CLS_VOLTAGE)
    if tpl is None:
        raise LookupError("no RbsVoltageType specimen to clone")
    eid = doc.next_id()
    obj, hdr, _rep = _clone_records(doc, tpl)
    _reset_identity(obj, eid)
    si = _v(obj.get("m_symbolInfo"))
    si["m_name"] = str(name)
    lo = volts if min_volts is None else min_volts
    hi = volts if max_volts is None else max_volts
    obj["m_dActualVoltage"] = volts_to_internal(volts)
    obj["m_dMinVoltage"] = volts_to_internal(lo)
    obj["m_dMaxVoltage"] = volts_to_internal(hi)
    obj["m_renderStyleId"] = -1
    obj["m_previewElemId"] = -1
    _finish_header(hdr, deletion=[eid])
    return _register(doc, eid, "voltage_type", CLS_VOLTAGE, hdr, obj, None, tpl,
                     [f"cloned from voltage type {tpl}; {volts} V (range {lo}-{hi} V), "
                      f"internal = V / 0.3048^2"])


def add_distribution_system(doc: Document, name: str, *,
                            vll: Union[int, NewElement],
                            vlg: Union[int, NewElement, None] = None,
                            phase: str = "three", config: str = "wye",
                            num_wires: int = 4,
                            template_id: Optional[int] = None) -> NewElement:
    """Plan a new ``RbsDistributionSysType`` (e.g. '600/347 Wye').

    ``vll`` / ``vlg`` are RbsVoltageType elements (existing ids or NewElements
    planned in the same run).  ``phase``: 'single'|'three' (m_kPhase 0/1);
    ``config``: 'single'|'wye' (m_kConfig 0/1 — the two configurations the
    corpus exhibits; a delta/high-leg system would need m_highLegPhase and
    an m_kConfig value the corpus does not show)."""
    tpl = template_id
    if tpl is None:
        want = 1 if phase == "three" else 0
        cands = doc.ids_of_class(CLS_DIST_SYS)
        tpl = next((i for i in cands if (doc.value(i) or {}).get("m_kPhase") == want),
                   cands[0] if cands else None)
    if tpl is None:
        raise LookupError("no RbsDistributionSysType specimen to clone")
    eid = doc.next_id()
    obj, hdr, _rep = _clone_records(doc, tpl)
    _reset_identity(obj, eid)
    _v(obj.get("m_symbolInfo"))["m_name"] = str(name)
    vll_id = _elem_id(vll)
    vlg_id = _elem_id(vlg) if vlg is not None else -1
    obj["m_idVll"] = vll_id if vll_id is not None else -1
    obj["m_idVlg"] = vlg_id if vlg_id is not None else -1
    obj["m_kPhase"] = {"single": 0, "three": 1}.get(phase, 1)
    obj["m_kConfig"] = {"single": 0, "wye": 1}.get(config, 1)
    obj["m_highLegPhase"] = -1
    obj["m_iNumWires"] = int(num_wires)
    obj["m_renderStyleId"] = -1
    obj["m_previewElemId"] = -1
    deletion = {eid}
    for x in (vll_id, vlg_id):
        if x is not None and x > 0:
            deletion.add(x)
    _finish_header(hdr, deletion=deletion)
    return _register(doc, eid, "distribution_system", CLS_DIST_SYS, hdr, obj, None,
                     tpl, [f"cloned from distribution system {tpl}; "
                           f"Vll={vll_id} Vlg={vlg_id} {phase}/{config} "
                           f"{num_wires}-wire"])


def add_demand_factor(doc: Document, name: str, *,
                      factor: Union[float, Sequence[Tuple[float, float, float]]] = 1.0,
                      rule_type: int = 0,
                      additional_load_va: float = 0.0,
                      include_additional_load: bool = False,
                      template_id: Optional[int] = None) -> NewElement:
    """Plan a new ``ElectricalDemandFactorDefinition``.

    ``factor``: a constant (single value) or a table of
    ``(factor, min_va, max_va)`` rows (``max_va=None`` = unbounded).
    ``rule_type``: 0 constant [V], 3 per-object ranking (motors) [V],
    4 apparent-load range table (receptacles, NEC 220.44) [V]."""
    tpl = template_id
    if tpl is None:
        # prefer a constant-rule donor
        for i in doc.ids_of_class(CLS_DEMAND_FACTOR):
            if (doc.value(i) or {}).get("m_ruleType") == 0:
                tpl = i
                break
        tpl = tpl or _one(doc, CLS_DEMAND_FACTOR)
    if tpl is None:
        raise LookupError("no ElectricalDemandFactorDefinition specimen to clone")
    eid = doc.next_id()
    obj, hdr, _rep = _clone_records(doc, tpl)
    _reset_identity(obj, eid)
    obj["m_name"] = str(name)
    if isinstance(factor, (int, float)):
        rows = [(float(factor), 0.0, None)]
    else:
        rows = [tuple(r) for r in factor]
    vals = []
    for f, lo, hi in rows:
        vals.append({"m_factor": float(f),
                     "m_minRange": va_to_internal(lo or 0.0),
                     "m_maxRange": (1e30 if hi in (None, 0) else va_to_internal(hi))})
    obj["m_values"] = vals
    obj["m_ruleType"] = int(rule_type)
    obj["m_additionalLoad"] = va_to_internal(additional_load_va)
    obj["m_includeAdditionalLoad"] = bool(include_additional_load)
    _finish_header(hdr, deletion=[eid])
    return _register(doc, eid, "demand_factor", CLS_DEMAND_FACTOR, hdr, obj, None, tpl,
                     [f"cloned from demand factor {tpl}; rule {rule_type}, "
                      f"{len(vals)} row(s)"])


def _caption_swap(text: Any, old: str, new: str) -> Any:
    if not isinstance(text, str) or not old:
        return text
    return text.replace(old, new)


def add_load_classification(doc: Document, name: str, *,
                            abbreviation: str = "",
                            demand_factor: Union[float, int, NewElement] = 1.0,
                            signature_type: int = 0,
                            space_load_class: int = 0,
                            create_parameters: bool = True,
                            template_id: Optional[int] = None) -> List[NewElement]:
    """Plan a new ``ElectricalLoadClassification`` and everything it owns.

    Returns the list of NewElements created, classification first:
    ``[classification, demand_factor?, param x6?]``.

    A Revit load classification is a small closure of elements
    (verified on all 10 corpus classifications):
      * its own ``ElectricalDemandFactorDefinition`` (``m_demandFactorId``),
      * six ``ParamElemElectricalLoadClassification`` parameter elements
        (connected / demand apparent power, connected / estimated demand
        current, demand factor, actual space load), each pointing back with
        ``m_idLoadClassification`` and named ``'<name> ...'``,
      * ElementHeader deletion parents both ways (the classification lists
        its factor + params; each param lists the classification).
    ``demand_factor``: a constant factor (a new definition named like the
    classification is created), an existing definition id, or a NewElement.
    """
    tpl = template_id or _one(doc, CLS_LOAD_CLASS)
    if tpl is None:
        raise LookupError("no ElectricalLoadClassification specimen to clone")
    created: List[NewElement] = []

    # 1. demand factor
    if isinstance(demand_factor, NewElement):
        df_id = demand_factor.elem_id
    elif isinstance(demand_factor, (int, float)) and not (
            isinstance(demand_factor, int) and doc.exists(int(demand_factor))
            and (doc.class_of(int(demand_factor)) == CLS_DEMAND_FACTOR)):
        df = add_demand_factor(doc, name, factor=float(demand_factor))
        created.append(df)
        df_id = df.elem_id
    else:
        df_id = int(demand_factor)

    # 2. the classification object
    tval = doc.value(tpl) or {}
    old_name = tval.get("m_name") or ""
    eid = doc.next_id()
    obj, hdr, _rep = _clone_records(doc, tpl)
    _reset_identity(obj, eid)
    obj["m_name"] = str(name)
    obj["m_abbreviation"] = str(abbreviation)
    obj["m_demandFactorId"] = df_id
    obj["m_signitureType"] = int(signature_type)
    obj["m_spaceLoadClass"] = int(space_load_class)
    cls_el = NewElement(eid, "load_classification", CLS_LOAD_CLASS,
                        doc.dec.schema.by_name[CLS_LOAD_CLASS].type_id,
                        hdr, obj, None, doc._new_elemrec(eid), tpl, notes=[])
    doc.new_elements.append(cls_el)
    created.insert(0, cls_el)

    # 3. the six parameter elements (cloned from the donor's six)
    param_ids: Dict[str, int] = {}
    session_guid = uuid.uuid4().hex             # shared by params created together
    if create_parameters:
        for fname in LOAD_CLASS_PARAM_FIELDS:
            donor_pid = tval.get(fname)
            if not (isinstance(donor_pid, int) and donor_pid > 0 and doc.exists(donor_pid)):
                obj[fname] = -1
                continue
            pid_new = doc.next_id()
            pobj, phdr, _prep = _clone_records(doc, donor_pid)
            _reset_identity(pobj, pid_new)
            pobj["m_idLoadClassification"] = eid
            pd = _v(pobj.get("m_pParamDef"))
            pd["m_paramElemId"] = pid_new
            pd["m_caption"] = _caption_swap(pd.get("m_caption"), old_name, name)
            tid = pd.get("m_typeId")
            if isinstance(tid, dict):
                # 'revit.local.classification:<32-hex guid><8-hex elem id>-<ver>'
                tid["m_typeId"] = f"revit.local.classification:{session_guid}{pid_new:08x}-1.0.0"
            pobj["m_description"] = _caption_swap(pobj.get("m_description"), old_name, name)
            _finish_header(phdr, deletion=[eid, pid_new])
            pel = _register(doc, pid_new, "load_class_param", CLS_LOAD_CLASS_PARAM,
                            phdr, pobj, None, donor_pid,
                            [f"param '{pd.get('m_caption')}' of new classification {eid}; "
                             f"cloned from {donor_pid}"])
            created.append(pel)
            param_ids[fname] = pid_new
            obj[fname] = pid_new
    else:
        for fname in LOAD_CLASS_PARAM_FIELDS:
            obj[fname] = -1

    # 4. classification header: factor + params + self are deletion parents
    _finish_header(hdr, deletion=[eid, df_id] + list(param_ids.values()))
    cls_el.notes.extend([
        f"cloned from load classification {tpl} ('{old_name}'); demand factor "
        f"{df_id}; {len(param_ids)} new parameter element(s) {sorted(param_ids.values())}",
        "closure = classification + its ElectricalDemandFactorDefinition + six "
        "ParamElemElectricalLoadClassification (mutual deletion parents)",
    ])
    return created


# ===========================================================================
# 6 · CREATE: wires (home runs / branch wires)
# ===========================================================================
@dataclass
class WirePlan:
    """A new wire + the record edits linking its device(s) back to it."""
    wire: NewElement
    device_plans: List[ModifyPlan] = dc_field(default_factory=list)
    home_run: bool = False
    view_id: int = -1
    circuits: List[int] = dc_field(default_factory=list)
    notes: List[str] = dc_field(default_factory=list)

    @property
    def elem_id(self) -> int:
        return self.wire.elem_id

    def to_json(self) -> dict:
        return {"wire": self.wire.to_json(),
                "device_plans": [p.to_json() for p in self.device_plans],
                "home_run": self.home_run, "view_id": self.view_id,
                "circuits": self.circuits, "notes": self.notes}


def _next_wire_mark(doc: Document) -> str:
    """max numeric Mark over the wires + 1 (marks are unique small ints)."""
    hi = 0
    for wid in doc.ids_of_class(CLS_WIRE):
        s = _astring_param(doc.value(wid) or {}, BIP_ALL_MODEL_MARK)
        if isinstance(s, str) and s.strip().isdigit():
            hi = max(hi, int(s.strip()))
    for e in doc.new_elements:
        if e.class_name == CLS_WIRE:
            s = _astring_param(e.obj, BIP_ALL_MODEL_MARK)
            if isinstance(s, str) and s.strip().isdigit():
                hi = max(hi, int(s.strip()))
    return str(hi + 1)


def _wire_template(doc: Document, view_id: Optional[int]) -> int:
    """A real 3-point wire to clone, preferring one owned by ``view_id``."""
    best = None
    for wid in doc.ids_of_class(CLS_WIRE):
        v = doc.value(wid) or {}
        if len(v.get("m_rgPoints") or []) != 3:
            continue
        if _conn_manager(v) is None:
            continue
        if view_id is not None and v.get("m_ownerDBViewId") == view_id:
            return wid
        if best is None:
            best = wid
    if best is None:
        raise LookupError("no RbsWireCurve specimen to clone (a template needs one wire)")
    return best


def _infer_wire_view(doc: Document, devices: Sequence[int],
                     circuits: Sequence[int]) -> Optional[int]:
    """The plan view owning the wires already attached to these devices /
    circuits (wires are view-specific: m_ownerDBViewId)."""
    from collections import Counter
    votes: Counter = Counter()
    cset = set(circuits)
    for wid in doc.ids_of_class(CLS_WIRE):
        v = doc.value(wid) or {}
        view = v.get("m_ownerDBViewId")
        if not isinstance(view, int) or view < 0:
            continue
        dpm = _v(v.get("m_pDesignPropManager"))
        if cset & set(dpm.get("m_setidCircuits") or []):
            votes[view] += 3
        for _i, refs in connectors(v).items():
            for (t, _ti, ct) in refs:
                if t in devices and ct == CONN_LOGICAL:
                    votes[view] += 1
    if not votes:
        return None
    return votes.most_common(1)[0][0]


def _unit(a, b):
    d = [b[i] - a[i] for i in range(3)]
    n = math.sqrt(sum(x * x for x in d)) or 1.0
    return [x / n for x in d], n


def add_wire(doc: Document, circuits: Union[int, NewElement, Sequence[Union[int, NewElement]]],
             from_device: int, to_device: Optional[int] = None, *,
             wiring_type: str = "arc",
             view_id: Optional[int] = None,
             from_conn: Optional[int] = None,
             to_conn: Optional[int] = None,
             free_point_ft: Optional[Sequence[float]] = None,
             mid_point_ft: Optional[Sequence[float]] = None,
             mark: Optional[str] = None,
             template_id: Optional[int] = None) -> WirePlan:
    """Plan a new plan-view WIRE for one or more existing circuits.

    * ``to_device`` given -> a BRANCH wire between two devices (both ends
      connected: the wire's end connectors reference the devices' supply
      connectors, and both devices are edited to reference the wire back).
    * ``to_device=None`` -> a HOME RUN: the wire starts at a FREE end (the
      arrowhead Revit draws pointing to the panel; ``free_point_ft`` or an
      auto point 4 ft from the device towards the circuit's panel) and ends
      on ``from_device``.  Home runs never touch the panel physically
      (verified: 0/1,045 corpus wire connectors reference equipment).
    ``wiring_type``: 'arc' [V, all corpus wires] or 'chamfer' [H, Revit
    WiringType enum].  ``view_id``: the plan view owning the wire (default:
    the view owning the devices'/circuits' existing wires).
    """
    if wiring_type not in ("arc", "chamfer"):
        raise ValueError("wiring_type must be 'arc' or 'chamfer'")
    ckt_ids: List[int] = []
    if isinstance(circuits, (list, tuple, set)):
        ckt_ids = [int(_elem_id(c)) for c in circuits]
    else:
        ckt_ids = [int(_elem_id(circuits))]
    for c in ckt_ids:
        if not doc.exists(c) or doc.class_of(c) != CLS_CIRCUIT:
            raise LookupError(f"circuit {c} is not an existing RbsElectricalSystem")
    for d in [from_device] + ([to_device] if to_device is not None else []):
        if not doc.exists(int(d)) or doc.class_of(int(d)) != "FamilyInstance":
            raise LookupError(f"device {d} is not an existing FamilyInstance")

    home_run = to_device is None
    devices = [from_device] + ([to_device] if to_device is not None else [])
    view = view_id if view_id is not None else _infer_wire_view(doc, devices, ckt_ids)
    if view is None:
        raise M.ManipulationError(
            "cannot infer the plan view to own the wire (its devices/circuits have "
            "no wires yet) -- pass view_id= a plan view; wires are view-specific")

    tpl = template_id or _wire_template(doc, view)
    tval = doc.value(tpl) or {}
    eid = doc.next_id()
    obj, hdr, rep = _clone_records(doc, tpl)

    # ---- endpoints: A = start (conn 0), B = end (conn 1) -------------------------
    fdev, tdev = int(from_device), (int(to_device) if to_device is not None else None)
    if home_run:
        b_dev, b_conn = fdev, (from_conn if from_conn is not None
                               else device_supply_connector(doc, fdev))
        a_dev, a_conn = None, None
        pb = device_connector_position(doc, b_dev, b_conn) or [0.0, 0.0, 0.0]
        if free_point_ft is not None:
            pa = [float(x) for x in free_point_ft]
        else:
            # 4 ft from the device towards its panel, at the view level (z 0)
            pnl = circuit_panel(doc, ckt_ids[0])
            ppos = _instance_origin(doc.value(pnl[0]) or {}) if pnl else None
            if ppos:
                dxy, _n = _unit(pb, [ppos[0], ppos[1], pb[2]])
            else:
                dxy = [1.0, 0.0, 0.0]
            pa = [pb[0] + 4.0 * dxy[0], pb[1] + 4.0 * dxy[1], 0.0]
    else:
        a_dev, a_conn = fdev, (from_conn if from_conn is not None
                               else device_supply_connector(doc, fdev))
        b_dev, b_conn = tdev, (to_conn if to_conn is not None
                               else device_supply_connector(doc, tdev))
        pa = device_connector_position(doc, a_dev, a_conn) or [0.0, 0.0, 0.0]
        pb = device_connector_position(doc, b_dev, b_conn) or [0.0, 0.0, 0.0]
    if len(pa) < 3:
        pa = [pa[0], pa[1], 0.0]
    if len(pb) < 3:
        pb = [pb[0], pb[1], 0.0]

    dvec, chord = _unit(pa, pb)
    if chord < 1e-6:
        raise ValueError("wire endpoints coincide")
    if mid_point_ft is not None:
        pm = [float(x) for x in mid_point_ft]
    else:
        # midpoint with a lateral bulge of 12% of the chord (an arc, like the corpus)
        mx = [(pa[i] + pb[i]) / 2.0 for i in range(3)]
        lat = [-dvec[1], dvec[0], 0.0]
        ln = math.hypot(lat[0], lat[1]) or 1.0
        bul = 0.12 * chord if wiring_type == "arc" else 0.0
        pm = [mx[0] + lat[0] / ln * bul, mx[1] + lat[1] / ln * bul, mx[2]]

    # ---- object patches --------------------------------------------------------
    _reset_identity(obj, eid)
    obj["m_ownerDBViewId"] = view
    if (doc.value(tpl) or {}).get("m_ownerDBViewId") != view:
        # keep the wire on the level of a device rather than the donor's view level
        lvl = (doc.value(b_dev) or {}).get("m_assocLevelId", obj.get("m_assocLevelId"))
        if isinstance(lvl, int) and lvl > 0:
            obj["m_assocLevelId"] = lvl
    obj["m_createdPhaseId"] = tval.get("m_createdPhaseId", -1)
    obj["m_demolishedPhaseId"] = -1
    obj["m_designOptionId"] = -1

    # design properties: the circuits carried by this wire (one-way link;
    # circuits do NOT reference their wires back)
    dpm = _v(obj.get("m_pDesignPropManager"))
    dpm["m_setidCircuits"] = sorted(ckt_ids)
    dpm["m_strCircuits"] = ""
    dpm["m_idCenterLine"] = -1
    dpm["m_idDownstreamCircuit"] = -1
    dpm["m_nHotAdjustment"] = 0
    dpm["m_nNeutralAdjustment"] = 0
    dpm["m_nGroundAdjustment"] = 0
    dpm["m_dElevation"] = 0.0

    # geometry: rgPoints path + the GLine chord driver
    obj["m_rgPoints"] = [[float(x) for x in pa], pm, [float(x) for x in pb]]
    obj["m_vNormal"] = [0.0, 0.0, 1.0]
    drv = _v(obj.get("m_pCurveDriver"))
    crv = _v(drv.get("m_pCrv"))
    crv["m_origin"] = [float(x) for x in pa]
    crv["m_dirVec"] = dvec
    crv["m_endParams"] = [0.0, chord]
    drv["m_sideJoins"] = []
    drv["m_controlJoinsSet"] = []
    drv["m_midParams"] = []
    obj["m_startOffsetVectorXYZ"] = [0.0, 0.0, 0.0]
    obj["m_endOffsetVectorXYZ"] = [0.0, 0.0, 0.0]
    a_conn_flag = a_dev is not None
    obj["m_bStartOffsetInitialized"] = bool(a_conn_flag)
    obj["m_bEndOffsetInitialized"] = True
    obj["m_bDynamicUpdateEnds"] = [bool(a_conn_flag), True]      # end i connected -> updates
    obj["m_bManualModifiedEnds"] = [False, False]
    obj["m_eType"] = WIRING_ARC if wiring_type == "arc" else WIRING_CHAMFER
    obj["m_bDrawCircularArc"] = (wiring_type == "arc")
    obj["m_iEndReference"] = 0
    obj["m_dParamTickMarksPos"] = 0.5
    obj["m_eTickMarkState"] = 0
    obj["m_idSystemCategory"] = -1
    obj["m_idSegment"] = -1

    # connector manager: conn 0 = start end, conn 1 = end end; each references
    # its sibling ({self, other, 1}) plus its connected device connector
    mgr = _conn_manager(obj) or {}
    mgr["m_setDeletedConnectors"] = []
    conns = mgr.get("m_connPtrArray") or []
    if len(conns) < 2:
        raise M.ManipulationError(f"template wire {tpl} has fewer than 2 connectors")
    del conns[2:]
    for c in conns:
        cv = _v(c)
        i = cv.get("m_nIndex")
        other = 1 - i
        refs = [{"m_id": eid, "m_nIndex": other, "m_connType": CONN_LOGICAL}]
        if i == 0 and a_dev is not None:
            refs.append({"m_id": a_dev, "m_nIndex": a_conn, "m_connType": CONN_LOGICAL})
        if i == 1:
            refs.append({"m_id": b_dev, "m_nIndex": b_conn, "m_connType": CONN_LOGICAL})
        cv["m_arrRefs"] = refs
        for m in cv.get("m_modifiers") or []:
            mv = _v(m)
            if not mv:
                continue
            if "m_paramOnCurve" in mv:
                mv["m_paramOnCurve"] = 0.0 if i == 0 else 1.0
            if "m_idSystem" in mv:                       # SegmentConnectorCalculation
                mv["m_idSystem"] = -1
                mv["m_dActualFlow"] = 0.0
                mv["m_dDemand"] = 0.0
                mv["m_dFlow"] = 0.0
                mv["m_eDirection"] = 0
                mv["m_nSection"] = 0
            if "m_delayedWriteParamMap" in mv:
                mv["m_delayedWriteParamMap"] = {"m_paramIdValueMap": []}

    # Mark (unique small integer) — the donor's would collide
    _set_astring_param(obj, BIP_ALL_MODEL_MARK, mark if mark is not None else _next_wire_mark(doc))
    # remap any leftover donor self-ids (geometry tags etc.)
    Document._remap_ids(obj, {tval.get("m_id"): eid})

    # ---- header ---------------------------------------------------------------
    hdr["m_ownerViewId"] = view
    hdr["m_categroryId"] = OST_Wire
    thdr = doc.value(tpl, 101) or {}
    tparents = _v(thdr.get("m_parents"))
    # stable style/settings regen parents from the donor (wire style, wire
    # settings, home-run leader style): keep those, drop the donor's own
    # devices / neighbouring wires
    keep_regen = []
    for x in tparents.get("m_regenOnly") or []:
        cn = doc.class_of(x) if isinstance(x, int) and x > 0 else None
        if cn in ("GStyleElem", CLS_WIRE_SETTINGS, "LeaderStyle"):
            keep_regen.append(x)
    keep_app = [x for x in (tparents.get("m_appearanceParents") or [])
                if isinstance(x, int) and x > 0 and doc.class_of(x) == "GStyleElem"]
    panel_ids = []
    for c in ckt_ids:
        p = circuit_panel(doc, c)
        if p:
            panel_ids.append(p[0])
    # other wires already attached to the same device connectors (run continuity)
    sibling_wires = []
    for (dv, dc) in ([(a_dev, a_conn)] if a_dev is not None else []) + [(b_dev, b_conn)]:
        for (t, _ti, ct) in connectors(doc.value(dv) or {}).get(dc, []):
            if ct == CONN_LOGICAL and doc.class_of(t) == CLS_WIRE:
                sibling_wires.append(t)
    deletion = {eid, obj.get("m_idType"), obj.get("m_assocLevelId"), view, *devices, *ckt_ids}
    trackers = doc.ids_of_class(CLS_SYSTEM_TRACKER)
    _finish_header(hdr,
                   deletion={x for x in deletion if isinstance(x, int) and x > 0},
                   regen_only=set(keep_regen) | set(panel_ids) | set(sibling_wires),
                   appearance=set(keep_app) | {obj.get("m_idType"), obj.get("m_assocLevelId"), b_dev},
                   deferred=trackers[:1],
                   nondeterm=False)
    hdr["m_ownerViewId"] = view

    # ---- rep (seq 103): the small view-graphics GElement, patch its tags -----
    if rep is not None:
        gi = rep.get("m_GInfo") or {}
        gi["m_tag"] = eid
        rep["m_elementId"] = eid
        Document._remap_ids(rep, {tval.get("m_id"): eid})

    el = NewElement(eid, "wire", CLS_WIRE, doc.dec.schema.by_name[CLS_WIRE].type_id,
                    hdr, obj, rep, doc._new_elemrec(eid), tpl,
                    notes=[f"cloned from wire {tpl} (view {view}); "
                           f"{'HOME RUN (free arrow start end)' if home_run else 'branch wire'}; "
                           f"circuits {sorted(ckt_ids)}; {wiring_type}; "
                           f"A={('free' if a_dev is None else f'{a_dev}:{a_conn}')} "
                           f"B={b_dev}:{b_conn}"])
    doc.new_elements.append(el)

    # ---- device back-links (connector arrRefs += {wire, wire_conn, 1}) ------
    plans: List[ModifyPlan] = []
    links = [(b_dev, b_conn, 1)]
    if a_dev is not None:
        links.insert(0, (a_dev, a_conn, 0))
    for (dv, dc, wire_conn) in links:
        plans.append(_link_device_to_wire(doc, dv, dc, eid, wire_conn))

    wp = WirePlan(el, plans, home_run, view, sorted(ckt_ids),
                  notes=[f"device edits: {[p.elem_id for p in plans]} "
                         "(connector back-references, connType 1)"])
    return wp


def add_home_run(doc: Document, circuit: int, device: Optional[int] = None, **kw) -> WirePlan:
    """Home run for ``circuit`` from ``device`` (default: the circuit's first
    member load) with a free arrow end towards the panel."""
    if device is None:
        loads = circuit_loads(doc, int(circuit))
        if not loads:
            raise LookupError(f"circuit {circuit} has no member loads to home-run from")
        device = loads[0][0]
        kw.setdefault("from_conn", loads[0][1])
    return add_wire(doc, circuit, device, None, **kw)


def _link_device_to_wire(doc: Document, device: int, dev_conn: int,
                         wire_id: int, wire_conn: int) -> ModifyPlan:
    """Edit an EXISTING device so its connector references the new wire back
    (Connector.m_arrRefs += {wire, wire_conn, connType 1}).  Uses the
    manipulate edit session, so several wires attaching to one device
    accumulate in one working copy (the last replacement carries all)."""
    sess = M.session(doc)
    val = sess.value(device, 102)
    cv = _connector_dict(val, dev_conn)
    if cv is None:
        raise M.ManipulationError(
            f"device {device}: no connector {dev_conn} (has "
            f"{sorted(connectors(val))}) to attach wire {wire_id}")
    refs = list(cv.get("m_arrRefs") or [])
    if not any(r.get("m_id") == wire_id and r.get("m_nIndex") == wire_conn for r in refs):
        refs.append({"m_id": wire_id, "m_nIndex": wire_conn, "m_connType": CONN_LOGICAL})
    cv["m_arrRefs"] = refs
    plan = ModifyPlan(kind="wire-backlink", elem_id=device,
                      class_name=doc.class_of(device),
                      changes=[FieldChange(102, f"connector[{dev_conn}].m_arrRefs",
                                           len(refs) - 1, len(refs))],
                      notes=[f"connector {dev_conn} += {{wire {wire_id}, conn "
                             f"{wire_conn}, connType 1}} (back-link to new wire)"])
    plan.record_edits.append(sess.replacement(device, 102,
                                              f"wire {wire_id} back-link"))
    sess.plans.append(plan)
    return plan


# ===========================================================================
# 7 · DELETE
# ===========================================================================
def delete_wire(doc: Document, wid: int, *, cascade: bool = True) -> DeletePlan:
    """Remove a wire: its three records + ElemRec, its annotation dependents
    (a wire tag cascades) and the devices' connector back-links (neutralised
    referrers).  Circuits are untouched (they never reference their wires)."""
    if doc.class_of(int(wid)) != CLS_WIRE:
        raise M.ManipulationError(f"element {wid} is a {doc.class_of(int(wid))!r}, "
                                  f"not an {CLS_WIRE}")
    return M.delete_element(doc, int(wid), cascade=cascade)


# ===========================================================================
# 8 · MODIFY: settings (thin, on manipulate.modify_element)
# ===========================================================================
def modify_setting(doc: Document, eid: int, changes: Dict[str, Any], *,
                   reason: str = "") -> ModifyPlan:
    """Generic field edit of an electrical-settings element (byte-exact
    re-encode, fresh stamp).  ``changes``: JSON path -> value."""
    return M.modify_element(doc, int(eid), dict(changes), kind="electrical-setting",
                            reason=reason or f"electrical setting {eid} edit")


def set_demand_factor(doc: Document, def_id: int, factor: float, *, row: int = 0,
                      min_va: Optional[float] = None,
                      max_va: Optional[float] = None) -> ModifyPlan:
    """Change one row of a demand factor definition (factor, optional range)."""
    if doc.class_of(int(def_id)) != CLS_DEMAND_FACTOR:
        raise M.ManipulationError(f"{def_id} is not a {CLS_DEMAND_FACTOR}")
    v = doc.value(def_id) or {}
    n = len(v.get("m_values") or [])
    if not (0 <= row < n):
        raise M.ManipulationError(f"demand factor {def_id} has {n} row(s); row {row} invalid")
    changes: Dict[str, Any] = {f"m_values[{row}].m_factor": float(factor)}
    if min_va is not None:
        changes[f"m_values[{row}].m_minRange"] = va_to_internal(min_va)
    if max_va is not None:
        changes[f"m_values[{row}].m_maxRange"] = va_to_internal(max_va)
    return modify_setting(doc, def_id, changes,
                          reason=f"demand factor {def_id} row {row} -> {factor}")


def set_voltage_type(doc: Document, vt_id: int, *, volts: Optional[float] = None,
                     min_volts: Optional[float] = None,
                     max_volts: Optional[float] = None) -> ModifyPlan:
    """Change a voltage definition's nominal / min / max (SI volts)."""
    if doc.class_of(int(vt_id)) != CLS_VOLTAGE:
        raise M.ManipulationError(f"{vt_id} is not a {CLS_VOLTAGE}")
    changes: Dict[str, Any] = {}
    if volts is not None:
        changes["m_dActualVoltage"] = volts_to_internal(volts)
    if min_volts is not None:
        changes["m_dMinVoltage"] = volts_to_internal(min_volts)
    if max_volts is not None:
        changes["m_dMaxVoltage"] = volts_to_internal(max_volts)
    if not changes:
        raise ValueError("give at least one of volts / min_volts / max_volts")
    return modify_setting(doc, vt_id, changes, reason=f"voltage type {vt_id} edit")


def rename_setting(doc: Document, eid: int, name: str) -> ModifyPlan:
    """Rename a *Type-style settings element (voltage type, distribution
    system, wire type/material/insulation: ``m_symbolInfo.m_name``) or a
    named definition (demand factor / load classification: ``m_name``)."""
    v = doc.value(int(eid)) or {}
    if isinstance(v.get("m_symbolInfo"), dict):
        path = "m_symbolInfo.value.m_name"
    elif "m_name" in v:
        path = "m_name"
    else:
        raise M.ManipulationError(f"element {eid} ({doc.class_of(int(eid))}) has no name field")
    return modify_setting(doc, eid, {path: str(name)}, reason=f"rename {eid} -> {name!r}")


def set_load_classification(doc: Document, cls_id: int, **fields) -> ModifyPlan:
    """Edit a load classification's plain fields (abbreviation, name,
    demand factor id, signature type, space load class)."""
    if doc.class_of(int(cls_id)) != CLS_LOAD_CLASS:
        raise M.ManipulationError(f"{cls_id} is not a {CLS_LOAD_CLASS}")
    keymap = {"abbreviation": "m_abbreviation", "name": "m_name",
              "demand_factor_id": "m_demandFactorId",
              "signature_type": "m_signitureType",
              "space_load_class": "m_spaceLoadClass"}
    changes = {keymap[k]: v for k, v in fields.items() if k in keymap}
    if not changes:
        raise ValueError(f"no known fields in {sorted(fields)}; known: {sorted(keymap)}")
    return modify_setting(doc, cls_id, changes,
                          reason=f"load classification {cls_id}: {sorted(changes)}")


# ===========================================================================
# 9 · MODIFY: panel circuit numbering
# ===========================================================================
def layout_circuits(rows: Sequence[dict]) -> List[dict]:
    """Revit's two-column panelboard layout rule.

    For each circuit (in the given order) with ``poles`` n, occupy the
    LOWEST start slot s such that s, s+2, ..., s+2(n-1) are all free (an
    n-pole breaker takes n slots of one column, i.e. same parity), then
    number it ``str(s)`` (n == 1) or ``"s,s+2,...``.  Verified to reproduce
    Autodesk's own numbering on the sample's untouched panels (PP-2B:
    singles 1..19, the 3-pole 'EP-2' at 20,22,24, then 21, 23; PP-3B:
    1..18 then 'EP-3' at 19,21,23) value-for-value.
    """
    used: set = set()
    out = []
    for r in rows:
        n = max(1, int(r.get("poles") or 1))
        s = 1
        while True:
            slots = [s + 2 * k for k in range(n)]
            if all(x not in used for x in slots):
                break
            s += 1
        used.update(slots)
        number = str(s) if n == 1 else ",".join(str(x) for x in slots)
        out.append({**r, "new_start_slot": s, "new_number": number,
                    "new_slots": slots})
    return out


def renumber_circuits(doc: Document, panel_id: int, *,
                      order: Optional[Sequence[int]] = None) -> List[ModifyPlan]:
    """Re-lay-out a panel's circuits: consistent circuit numbers + start
    slots (closes gaps, resolves overlaps), the data behind a correct panel
    schedule.  ``order``: explicit circuit-id sequence (default = current
    schedule order by start slot).  Returns the ModifyPlans (empty if the
    panel is already consistent — the numbering is idempotent)."""
    rows = panel_circuits(doc, panel_id)
    if not rows:
        raise M.ManipulationError(f"panel {panel_id} feeds no circuits")
    if order:
        byid = {r["id"]: r for r in rows}
        seq = [byid[i] for i in order if i in byid] + \
              [r for r in rows if r["id"] not in set(order)]
    else:
        seq = list(rows)
    laid = layout_circuits(seq)
    plans: List[ModifyPlan] = []
    for r in laid:
        cur_num = r.get("number") or ""
        cur_slot = r.get("start_slot")
        if cur_num == r["new_number"] and cur_slot == r["new_start_slot"]:
            continue
        pl = M.modify_element(doc, r["id"],
                              {"m_number": r["new_number"],
                               "m_nStartSlot": int(r["new_start_slot"])},
                              kind="renumber-circuit",
                              reason=(f"panel {panel_id} renumber: circuit {r['id']} "
                                      f"{cur_num!r}@{cur_slot} -> "
                                      f"{r['new_number']!r}@{r['new_start_slot']}"))
        plans.append(pl)
    return plans


def rename_panel(doc: Document, panel_id: int, name: str) -> ModifyPlan:
    """The panel's 'Panel Name' built-in parameter (BIP_RBS_ELEC_PANEL_NAME)."""
    return M.rename_panel(doc, int(panel_id), name)


# ===========================================================================
# 10 · COMMIT: new elements + record edits in ONE re-emit of save-unit 0
# ===========================================================================
@dataclass
class ElectricalCommitReport:
    partition: str
    new_element_ids: List[int]
    removed_ids: List[int]
    replaced: List[Tuple[int, int]]           # (seq, elem_id)
    elemtable_count_before: int
    elemtable_count_after: int
    watermark_after: int
    blocks_after: Dict[int, int]
    out_path: str

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        d["replaced"] = [list(x) for x in self.replaced]
        return d


def _sentinel_offset(seg: bytes, seq: int) -> int:
    """Offset of the trailing sentinel record in a unit-0 per-seq segment."""
    return _commit._assert_sentinel_tail(seg, seq)


def commit_electrical(src_rvt: str, out_path: str, doc: Document, *,
                      new_elements: Sequence[NewElement] = (),
                      plans: Sequence[Any] = (),
                      block_budget: int = BLOCK_BUDGET,
                      own_identity: bool = False,
                      identity: Optional[dict] = None) -> ElectricalCommitReport:
    """Write ``out_path`` = ``src_rvt`` + new elements + modify/delete plans.

    A single re-emit of save-unit 0 that combines the CREATE path
    (:mod:`rvt.commit`: three new records per element inserted immediately
    before each per-seq sentinel + ElemTable rows) with the EDIT path
    (:mod:`rvt.manipulate`: record replacements / removals + ElemTable row
    removals).  Needed by wiring, where a new wire (create) and its devices'
    connector back-links (in-place edits) must land in the SAME file.
    Every other stream and every embedded-document unit is copied verbatim;
    both re-emitted streams are re-paged with real CRCIO ECC.

    ``own_identity`` (default False): also rewrite ``BasicFileInfo`` with
    the writer's identity (:mod:`rvt.identity`, gate G2).  OFF by default
    because the identity scrub as of 2026-08-03 replaces the Unique Document
    GUID WITHOUT prepending the matching ``Global/History`` episode, which
    breaks the verified cross-stream invariant ``BasicFileInfo GUID ==
    History entry[0] GUID`` and makes ``rvt_validate`` FAIL (L2) — the same
    conflict any post-2026-08-03 ``commit_new_elements`` output hits.  Flip it
    on once the identity path records the episode (see the stream record).
    """
    # ---- gather ---------------------------------------------------------------
    recs_by_element: List[Dict[int, bytes]] = []
    elemrecs: List[ElemRecPlan] = []
    for e in new_elements:
        framed = doc.serialize(e)
        if framed is None:
            raise M.ManipulationError("rvt.encode is required to serialize new elements")
        recs_by_element.append(dict(framed))
        elemrecs.append(e.elemrec)
    removals: set = set()
    replacements: Dict[Tuple[int, int], bytes] = {}
    et_remove: set = set()
    for pl in plans:
        for ed in getattr(pl, "record_edits", []) or []:
            if ed.action == "remove":
                removals.add(ed.elem_id)
            elif ed.action == "replace":
                replacements[(ed.seq, ed.elem_id)] = ed.new_record
        for i in getattr(pl, "elemtable_remove", []) or []:
            et_remove.add(i)
    for key in [k for k in replacements if k[1] in removals]:
        del replacements[key]

    new_streams: Dict[str, bytes] = {}
    with open_rvt(src_rvt) as d:
        pname = M._primary_partition(d)
        bfi = d.raw("BasicFileInfo") if d.has("BasicFileInfo") else None

        # ---- 1. Global/ElemTable ------------------------------------------------
        model = SE.decode_elemtable(d.inflate("Global/ElemTable"))
        count_before = len(model["records"])
        if et_remove:
            model["records"] = [r for r in model["records"] if r[4] not in et_remove]
        creation_ep = max((r[2] for r in model["records"]), default=0)
        for plan in elemrecs:
            elemtable_add_element(model, plan.elem_id, creation_ep=creation_ep,
                                  modified_ep=creation_ep,
                                  user_modified_ep=creation_ep)
        count_after = len(model["records"])
        watermark = int(model["footer"]["last_id"])
        et_payload = SE.encode_elemtable(model)
        et_logical = global_prefix("Global/ElemTable") + gzip_member(et_payload, level=3)
        new_streams["Global/ElemTable"] = ecc.frame_stream(et_logical)

        # ---- 2. Partitions/<N>: rewrite save-unit 0 -----------------------------
        logical = d.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        if w.errors:
            raise M.ManipulationError(f"walker errors on source {pname}: {w.errors[:3]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        u0 = [b for b in blocks if b.unit == 0]
        if not u0:
            raise M.ManipulationError(f"{pname}: no save-unit-0 blocks")
        seq_order: List[int] = []
        for b in u0:
            if b.seq not in seq_order:
                seq_order.append(b.seq)
        segments = {s: b"".join(b.data for b in u0 if b.seq == s) for s in seq_order}

        new_segments: Dict[int, bytes] = {}
        for s in seq_order:
            rep_map = {eid: rec for (sq, eid), rec in replacements.items() if sq == s}
            seg2, st = apply_edits_to_segment(segments[s], s, removals, rep_map)
            if not st["sentinel_last"]:
                raise M.ManipulationError(f"seq {s}: unit-0 segment lost its sentinel")
            extra = b"".join(rr[s] for rr in recs_by_element if s in rr)
            if extra:
                ins = _sentinel_offset(seg2, s)
                seg2 = seg2[:ins] + extra + seg2[ins:]
            new_segments[s] = seg2

        u0_first = u0[0].hdr_offset
        u0_footer = w.units[0].footer_offset
        if u0_footer is None:
            raise M.ManipulationError(f"{pname}: unit-0 footer not found")
        out = bytearray(logical[:u0_first])
        blocks_after: Dict[int, int] = {}
        for s in seq_order:
            nb = chunk_segment(new_segments[s], s, block_budget)
            blocks_after[s] = len(nb)
            for b in nb:
                out += M._emit_block(b, s)
        out += logical[u0_footer:]
        struct.pack_into("<I", out, PART_HDR_COUNT_OFF, count_after)
        w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
        if w2.errors:
            raise M.ManipulationError(f"walker errors after re-emit: {w2.errors[:3]}")
        part_logical = bytes(out[:w2.end_offset + len(w2.end_record)])
        new_streams[pname] = ecc.frame_stream(part_logical)

    # ---- 3. identity (gate G2) — opt-in, see docstring ---------------------------
    if own_identity:
        try:
            from ..identity import own_basic_file_info
            if bfi is not None:
                new_streams["BasicFileInfo"] = own_basic_file_info(
                    bfi, out_path=out_path, **(identity or {}))
        except Exception as exc:                                    # pragma: no cover
            import warnings
            warnings.warn(f"identity scrub skipped: {exc}")

    # ---- 4. write -------------------------------------------------------------
    rewrite_entries(src_rvt, out_path, new_streams)
    return ElectricalCommitReport(
        pname, sorted(e.elem_id for e in new_elements), sorted(removals),
        sorted(replacements.keys()), count_before, count_after, watermark,
        blocks_after, out_path)


def verify_electrical(path: str, *, new_ids: Sequence[int] = (),
                      edited_ids: Sequence[int] = (),
                      deleted_ids: Sequence[int] = ()) -> dict:
    """Structural + semantic proof of a committed file (wraps
    ``manipulate.verify_manipulated`` and treats new elements as edited:
    present, decoding cleanly, in all their seqs)."""
    v = M.verify_manipulated(path, deleted_ids=list(deleted_ids),
                              edited_ids=list(new_ids) + list(edited_ids))
    v["new_ids"] = list(new_ids)
    v["structurally_valid"] = structurally_valid(v)
    return v


def structurally_valid(v: dict) -> bool:
    ok = (v.get("crc_failures") == 0 and v.get("ecc_mismatches") == 0
          and v.get("walker_errors") == 0
          and v.get("isize_identity_mismatches") == 0
          and v.get("stamps_ok") is True
          and all((v.get("sentinel_last") or {}).values())
          and v.get("elemtable_count") == v.get("header_count")
          and v.get("elemtable_ids_sorted") and v.get("unit0_ids_equal_elemtable")
          and not v.get("deleted_still_present") and not v.get("deleted_in_elemtable"))
    for _eid, seqs in (v.get("edited") or {}).items():
        ok = ok and all(x.get("clean") for x in seqs.values())
    return bool(ok)


# ===========================================================================
# 11 · CLI
# ===========================================================================
def _cli(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path, cmd = argv[0], argv[1]
    doc = Document.from_file(path)
    if cmd == "settings":
        print(json.dumps(electrical_settings(doc), indent=1, default=str))
    elif cmd == "wires":
        n = int(argv[2]) if len(argv) > 2 else 10
        print(json.dumps(wires(doc, limit=n), indent=1, default=str))
    elif cmd == "panels":
        print(json.dumps(panels(doc), indent=1, default=str))
    elif cmd == "panel":
        pid = int(argv[2])
        print(json.dumps({"panel": panel_info(doc, pid),
                          "numbering": check_panel_numbering(doc, pid),
                          "circuits": panel_circuits(doc, pid)}, indent=1, default=str))
    else:
        print(f"unknown command {cmd!r}; use settings|wires|panels|panel <id>")
        return 2
    return 0


def main(argv=None) -> int:
    return _cli(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
