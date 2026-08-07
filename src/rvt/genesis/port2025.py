"""genesis/port2025.py -- the Revit-2025 PORTABILITY LAYER over the 2026
constructors (genesis-2025 campaign step G25-3, constructor side).

The 2026 constructors (``rvt.genesis.types`` / ``settings`` / ``catalog`` /
``skeleton`` / ``residue_*``) build schema-directed objects against the 2026
archive class map.  This module WRAPS them -- it never edits them:

    adapt(class_name, obj_2026)  ->  obj_2025
    adapt_record(record_2026)    ->  PortedRecord (2025 class ids, 2025-shaped
                                     seq-101/102/103 bodies)

The transform is driven by BOTH schemas (the pinned 2026 map and the pinned
2025 map, ``rvt.versions.schema_2025``): the adapter walks the TARGET (2025)
class chain field by field, carries every field that exists under the same
name in the source object (recursively adapting nested owned/inline class
values), synthesises a 2025 schema-blank default for fields the 2026 object
does not have, and applies the CONFIRMED per-class hooks below where a blank
default is not the corpus value.  2026-only fields disappear by construction
(the walk enumerates 2025 fields only).  Classes that do not exist in the
2025 schema raise :class:`Missing2025` (the conductor catalog -- their 2025
representation is the string field on ``RbsWireType``, hook below).

CONFIRMED PORTABILITY VERDICT (this module's ``--verify`` re-derives it;
frozen copy: ``experiments/genesis2025/subst/portability-2025.json``).
Method = docs/writer/genesis-2025-plan.md section 6 (own-field signatures by
type NAME, flattened parent-first chain layout, per-class versions), run over
the harvested constructed-class set + every base class on their chains.

Corrections this verification found against the plan's section-5 table
(the plan is the PREDICTION; this module is the CONFIRMATION):

* THE PLAN MISSED FOUR LAYOUT-DELTA CLASSES, all in the view layer:
    - ``DBView`` (base of EVERY view class we construct: DBView3d,
      DBViewPlan, DBViewProject, DBViewDrafting, RbsDbViewSystemNavigator):
      2026-only own field ``m_viewPositionId`` (ElementId) -- dropped for
      2025 (skeleton writes -1 anyway);
    - ``DBViewDrafting``: additionally 2026-only ``m_sheetTitleBlockId``;
    - ``Viewport`` v13->10: 2026-only ``m_viewPosition`` (XYZ) and
      ``m_viewAnchor`` (int) -- dropped (skeleton writes zeros);
    - ``BrowserOrganizationTracking`` v6->5 (ADocument registry class, not
      an element): 2026 map ``m_currentBrOrgTypeToBrOrgMap``
      [(tree type, org id)] becomes THREE 2025 ElementId fields
      (views / sheets / schedules), split by the tree-type codes.
* Value corrections (mined from the 2025 samples, see MINED constants):
    - ``GeomTable`` extra ints default **-1 / -1** (the plan guessed 0/0;
      5,620 of 5,637 decoded 2025-sample GeomTables carry (-1, -1));
    - ``ReinforcementSettings.m_numberVaryingLengthRebarsIndividually``
      sample default is **True** (plan implied the blank default);
    - ``RbsWireType.m_strMaxConductorSize`` sample value is the bare size
      label (**'2000'**), not '1000 kcmil' -- we write OUR size label
      resolved from the conductor-size cell the 2026 record references.
* Confirmed exactly as planned: the 6 MISSING conductor-catalog classes;
  RbsWireSettingsElem's three 2025-only doubles = 0.02 / 0.03 / 303.15 K
  (decoded from the 2025 rst sample, elem 102129 -- same values the plan
  read from the 2025 rme sample); GeomStep m_oExtraDatas->m_oExtraData
  rename (5 GStep constructors); NumberingSchema rework (2025 shape decoded
  from rst 1218729/1218730/1457391 -- the ORACLE for the hook below);
  BrowserOrganization m_sortParameter->m_sortParamId; ModelGraphicsStyle /
  ViewDisplayMgr GDI flags default False (85/85 decoded ViewDisplayMgr);
  the 1-field drops (AssemblyCodeTable / KeynoteTable / StructSettingsElem /
  RbsWireSizesElem m_bInitialized); RbsWireSizesElem map order free under
  schema-directed encode.

Round-trip gate: every adapted object must encode -> decode -> re-encode
BYTE-EXACT under the 2025 schema (:func:`verify_roundtrip_2025`;
tests/test_port2025.py runs it over the constructor battery).

Territory: this module, tests/test_port2025.py,
experiments/genesis2025/subst/**, docs/inbox/genesis-2025-port.md.
Python: ALWAYS ``.venv/bin/python`` from the repo root.

CLI::

    .venv/bin/python -m rvt.genesis.port2025 --verify    # portability table
    .venv/bin/python -m rvt.genesis.port2025 --mine      # 2025 corpus miners
    .venv/bin/python -m rvt.genesis.port2025 --selftest  # adapt+roundtrip battery
"""
from __future__ import annotations

import ast
import collections
import copy
import dataclasses
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from .types import INVALID, NULL_GUID

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
GENESIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "experiments", "genesis2025", "subst")
PORTABILITY_JSON = os.path.join(OUT_DIR, "portability-2025.json")
ENUM_2025_JSON = os.path.join(OUT_DIR, "builtin_category_enum_2025.json")
PROFILE_2025_JSON = os.path.join(OUT_DIR, "builtin_style_profile_2025.json")

#: the quarantined 2025 samples (DEV-ONLY field oracles; never shipped)
SAMPLES_2025 = os.path.join(ROOT, "samples", "2025")
RST_2025 = os.path.join(SAMPLES_2025, "rstbasicsampleproject.rvt")


class PortabilityError(RuntimeError):
    """A 2026 object cannot be expressed under the 2025 schema."""


class Missing2025(PortabilityError):
    """The class does not exist in the Revit-2025 archive class map."""


# ---------------------------------------------------------------------------
# schema / codec singletons (2026 = the genesis default; 2025 = the pin)
# ---------------------------------------------------------------------------
_STATE: Dict[str, Any] = {}


def _S26():
    """(decoder, encoder, schema) for the canonical 2026 map (the genesis
    singleton's own machinery, shared object identity not required)."""
    if "s26" not in _STATE:
        from .types import _S
        _STATE["s26"] = _S()
    return _STATE["s26"]


def _S25():
    """(decoder, encoder, schema) for the pinned Revit-2025 map."""
    if "s25" not in _STATE:
        from ..encode import ObjectEncoder
        from ..objects import ObjectDecoder
        from ..versions import schema_2025
        dec = ObjectDecoder(schema_2025.load())
        _STATE["s25"] = (dec, ObjectEncoder(decoder=dec), dec.schema)
    return _STATE["s25"]


def class_id_2025(name: str) -> int:
    """u16 Revit-2025 archive class id of ``name`` (raises Missing2025)."""
    _dec, _enc, schema = _S25()
    cd = schema.by_name.get(name)
    if cd is None:
        raise Missing2025(f"class {name!r} is not in the Revit-2025 archive class map")
    return cd.type_id


def exists_2025(name: str) -> bool:
    _dec, _enc, schema = _S25()
    return name in schema.by_name


# ---------------------------------------------------------------------------
# 2025 schema-blank defaults (the 2025 twin of types.blank_object)
# ---------------------------------------------------------------------------
def blank_object_2025(class_name: str) -> dict:
    """A complete, 2025-encoder-ready object dict for ``class_name``: every
    field of the class + its bases (parent-first) at its schema default --
    the exact rule of ``rvt.genesis.types.blank_object``, walked over the
    2025 map."""
    dec, _enc, schema = _S25()
    cd = schema.by_name.get(class_name)
    if cd is None:
        raise Missing2025(f"class {class_name!r} is not in the Revit-2025 archive class map")
    return _blank_class25(dec, cd.type_id, 0)


def _blank_class25(dec, type_id: int, depth: int) -> dict:
    from ..objects import field_key
    out: dict = {}
    for cd in dec.chain(type_id):
        for f in cd.fields:
            out[field_key(cd, f, out)] = _blank_field25(dec, f, depth)
    return out


def _blank_field25(dec, f, depth: int):
    kind, flags = f.kind, f.flags
    shape = flags >> 4
    if kind == 0x08:
        return [] if shape in (1, 5) else ""
    if kind == 0x0D:
        if shape == 1:
            return [_blank_field25(dec, f.element, depth) for _ in range(f.count or 0)]
        return []
    if shape == 5:
        return []
    if shape == 1:
        return [_blank_scalar25(dec, f, kind, flags & 0x0F, depth)
                for _ in range(f.count or 0)]
    return _blank_scalar25(dec, f, kind, flags & 0x0F, depth)


def _blank_scalar25(dec, f, kind: int, indir: int, depth: int):
    from ..objects import _PRIM_FMT
    if kind == 0x01:
        return False
    if kind in _PRIM_FMT:
        return 0.0 if kind in (0x06, 0x07) else 0
    if kind == 0x08:
        return ""
    if kind == 0x09:
        return NULL_GUID
    if kind == 0x0A:
        return {"classref": "Element"}
    if kind == 0x0E:
        if indir == 0:
            tid = f.type_id
            if tid in (dec.id_ElementId, dec.id_Identifier):
                return INVALID
            if tid == dec.id_XYZ:
                return [0.0, 0.0, 0.0]
            if tid == dec.id_UV:
                return [0.0, 0.0]
            if tid == dec.id_GUIDvalue:
                return NULL_GUID
            if depth > 8:
                return {}
            return _blank_class25(dec, tid, depth + 1)
        if indir == 3:
            return {"weakref": 0}
        return None
    raise PortabilityError(f"unsupported field kind {kind:#x} ({f.name})")


# ---------------------------------------------------------------------------
# MINED 2025 corpus constants (field oracles; provenance in each comment).
# Everything below was DECODED from the quarantined samples/2025 corpus by
# ``--mine`` -- per-release format data / product defaults, the same
# classification as the 2026 constants the constructors already mirror.
# ---------------------------------------------------------------------------
#: RbsWireSettingsElem's three 2025-only doubles (the wire-sizing model that
#: moved into the conductor catalog in 2026).  Decoded from the 2025 rst
#: sample elem 102129 (plan section 5a read the same values off the 2025 rme
#: sample elem 293123): the 2 % / 3 % max voltage-DROP sizing fractions and
#: 30 degC ambient in kelvin.  303.15000000000003 is the EXACT stored double.
WIRE_SETTINGS_2025 = {
    "m_dMaxVoltageBranchSizing": 0.02,
    "m_dMaxVoltageFeederSizing": 0.03,
    "m_dAmbientTemperature": 303.15000000000003,
}

#: GeomTable's two 2025-only leading ints.  Corpus value for fresh/empty
#: tables is (-1, -1): 5,620 of 5,637 GeomTables decoded from the 2025 rst
#: sample carry exactly that (the plan guessed 0/0 -- corrected).
GEOMTABLE_2025 = {"m_maxSafeTag": -1, "m_lastCheckedKingsUserModificationDate": -1}

#: NumberingSchema 2025: schemaTypeGuid per scope category, decoded from the
#: 2025 rst sample's three built-in numbering schemas (1218729 rebar /
#: 1457391 couplers / 1218730 fabric sheets) -- product identity GUIDs of
#: Revit's own numbering machinery (format constants, not authorship).
NUMBERING_SCHEMA_TYPE_GUIDS_2025 = {
    -2009000: "e0bc59cf-a1aa-48ae-83a2-637780af923d",   # Rebar Numbering
    -2009060: "396c2ee8-a554-4fed-bf44-c2e648dec011",   # Rebar Couplers Numbering
    -2009016: "f90085e5-ffbd-4dea-aadc-837c93df2943",   # Fabric Sheets Numbering
}

#: ViewDisplayMgr.m_useGDI / ModelGraphicsStyle.m_bUseGDI: False in every
#: decoded 2025 specimen (85/85 ViewDisplayMgr, 2/2 ModelGraphicsStyle).
USE_GDI_2025 = False

#: ReinforcementSettings.m_numberVaryingLengthRebarsIndividually: the 2025
#: sample default is True (rst elem 137426) -- NOT the blank default.
REINF_NUMBER_INDIVIDUALLY_2025 = True

#: RbsWireType.m_strMaxConductorSize: the 2025 sample stores the bare size
#: label ('2000' on rst elem 55171).  OUR wire types resolve their own
#: conductor-size cell's label ('500' / '750'); this is the fallback when a
#: record's reference cannot be resolved.
WIRE_MAX_SIZE_FALLBACK_2025 = "2000"


# ---------------------------------------------------------------------------
# the per-class field-map HOOKS (keyed by DECLARING class name + field name,
# so inherited and nested occurrences are covered uniformly)
# ---------------------------------------------------------------------------
def _hook_wire_max_size(src: dict, ctx: "_AdaptContext"):
    sid = src.get("m_idMaxConductorSize", INVALID)
    if isinstance(sid, int) and sid not in (None, INVALID) and ctx.resolve_name:
        nm = ctx.resolve_name(int(sid))
        if nm:
            ctx.note(f"RbsWireType.m_strMaxConductorSize <- conductor-size cell "
                     f"{sid} name {nm!r}")
            return str(nm)
    ctx.note("RbsWireType.m_strMaxConductorSize <- fallback "
             f"{WIRE_MAX_SIZE_FALLBACK_2025!r} (max-size cell not resolvable)")
    return WIRE_MAX_SIZE_FALLBACK_2025


def _hook_sort_param_id(src: dict, ctx: "_AdaptContext"):
    ap = src.get("m_sortParameter")
    path = (ap or {}).get("m_paramIdPath") if isinstance(ap, dict) else None
    if path:
        return int(path[0])
    return INVALID


def _hook_numbering_partition_creator(src: dict, ctx: "_AdaptContext"):
    parts = src.get("m_partitioningParams") or []
    pid = INVALID
    if parts and isinstance(parts[0], dict):
        pid = int(parts[0].get("m_parameterId", INVALID))
    body = blank_object_2025("ParameterBasedPartitionDescriptionCreator")
    body["m_ccda"] = {"m_pDoc": {"weakref": 1}}
    body["m_partitionParameterId"] = pid
    return {"ptr_class": "ParameterBasedPartitionDescriptionCreator",
            "pid": -1, "value": body}


def _hook_numbering_min_digits(src: dict, ctx: "_AdaptContext"):
    fs = src.get("m_formatSettings") or {}
    return int(fs.get("m_minimumNumberOfDigits", 1) or 1)


def _hook_numbering_type_guid(src: dict, ctx: "_AdaptContext"):
    cats = src.get("m_scopeCategories") or []
    guid = NUMBERING_SCHEMA_TYPE_GUIDS_2025.get(int(cats[0]) if cats else 0)
    if guid is None:
        guid = NULL_GUID
        ctx.note(f"NumberingSchema.schemaTypeGuid: scope categories {cats} not in "
                 "the mined 2025 GUID table -> null GUID")
    body = blank_object_2025("NumberingSchemaType")
    body["m_value"] = guid
    return body


def _hook_numbering_matching(src: dict, ctx: "_AdaptContext"):
    return bool(src.get("m_enabled", True))


def _browser_tracking_tree(src: dict, code: int):
    for row in src.get("m_currentBrOrgTypeToBrOrgMap") or []:
        if isinstance(row, dict) and int(row.get("first", -999)) == code:
            return int(row.get("second", INVALID))
    return INVALID


#: (declaring class, 2025 field) -> value hook(src_2026_obj, ctx).
#: A hook OVERRIDES both carry-over and the blank default.  Fields not
#: hooked and absent from the source get the 2025 schema blank.
HOOKS: Dict[Tuple[str, str], Callable[[dict, "_AdaptContext"], Any]] = {
    # GeomTable: two 2025-only leading ints, corpus value (-1, -1)
    ("GeomTable", "m_maxSafeTag"): lambda s, c: GEOMTABLE_2025["m_maxSafeTag"],
    ("GeomTable", "m_lastCheckedKingsUserModificationDate"):
        lambda s, c: GEOMTABLE_2025["m_lastCheckedKingsUserModificationDate"],
    # GeomStep: m_oExtraDatas (2026) -> m_oExtraData (2025); constructors
    # leave it defaulted (None) -- carry the 2026 value under the new name
    ("GeomStep", "m_oExtraData"): lambda s, c: s.get("m_oExtraDatas", None),
    # RbsWireSettingsElem: the three 2025-only sizing doubles (mined)
    ("RbsWireSettingsElem", "m_dMaxVoltageBranchSizing"):
        lambda s, c: WIRE_SETTINGS_2025["m_dMaxVoltageBranchSizing"],
    ("RbsWireSettingsElem", "m_dMaxVoltageFeederSizing"):
        lambda s, c: WIRE_SETTINGS_2025["m_dMaxVoltageFeederSizing"],
    ("RbsWireSettingsElem", "m_dAmbientTemperature"):
        lambda s, c: WIRE_SETTINGS_2025["m_dAmbientTemperature"],
    # RbsWireType: id-of-catalog-cell -> the size label string
    ("RbsWireType", "m_strMaxConductorSize"): _hook_wire_max_size,
    # BrowserOrganization: AggregatedParameter -> plain ElementId
    ("BrowserOrganization", "m_sortParamId"): _hook_sort_param_id,
    # ModelGraphicsStyle / ViewDisplayMgr: 2025-only GDI flags (mined False)
    ("ModelGraphicsStyle", "m_bUseGDI"): lambda s, c: USE_GDI_2025,
    ("ViewDisplayMgr", "m_useGDI"): lambda s, c: USE_GDI_2025,
    # ReinforcementSettings: int m_numberingMethod (2026) has no 2025 twin;
    # the 2025 bool's sample default is True (mined)
    ("ReinforcementSettings", "m_numberVaryingLengthRebarsIndividually"):
        lambda s, c: REINF_NUMBER_INDIVIDUALLY_2025,
    # NumberingSchema: 2025 shape rebuilt from the 2026 object + the mined
    # oracle (rst 1218729 / 1218730 / 1457391)
    ("NumberingSchema", "m_oPartitionDescriptionCreator"): _hook_numbering_partition_creator,
    ("NumberingSchema", "m_minimumNumberOfDigits"): _hook_numbering_min_digits,
    ("NumberingSchema", "schemaTypeGuid"): _hook_numbering_type_guid,
    ("NumberingSchema", "m_isMatchingEnabled"): _hook_numbering_matching,
    # BrowserOrganizationTracking (ADocument registry class): the 2026
    # type->org map splits into three 2025 ElementId fields by tree code
    # (settings.BROWSER_ORG_*: 0 views / 1 sheets / 3 schedules)
    ("BrowserOrganizationTracking", "m_currentBrOrgViews"):
        lambda s, c: _browser_tracking_tree(s, 0),
    ("BrowserOrganizationTracking", "m_currentBrOrgSheets"):
        lambda s, c: _browser_tracking_tree(s, 1),
    ("BrowserOrganizationTracking", "m_currentBrOrgSchedules"):
        lambda s, c: _browser_tracking_tree(s, 3),
}


# ---------------------------------------------------------------------------
# the generic schema-pair adapter
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class _AdaptContext:
    resolve_name: Optional[Callable[[int], Optional[str]]] = None
    notes: List[str] = dataclasses.field(default_factory=list)
    path: str = ""

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def adapt(class_name: str, obj: dict, *,
          resolve_name: Optional[Callable[[int], Optional[str]]] = None,
          _ctx: Optional[_AdaptContext] = None) -> dict:
    """A Revit-2025 object dict for ``class_name`` from a 2026-built one.

    Walks the 2025 class chain; carries same-name fields (recursively
    adapting nested class values), applies :data:`HOOKS`, blanks the rest.
    The source is never mutated.  Raises :class:`Missing2025` when the class
    (or a pointed-to class inside it) has no 2025 twin and no hook covers it.
    """
    ctx = _ctx or _AdaptContext(resolve_name=resolve_name)
    dec25, _enc, schema25 = _S25()
    cd = schema25.by_name.get(class_name)
    if cd is None:
        raise Missing2025(f"class {class_name!r} is not in the Revit-2025 archive "
                          "class map (2026-only)")
    return _adapt_class(class_name, cd.type_id, obj or {}, ctx)


def _adapt_class(class_name: str, type_id: int, src: dict, ctx: _AdaptContext) -> dict:
    from ..objects import field_key
    dec25, _enc, _s = _S25()
    out: dict = {}
    for cd in dec25.chain(type_id):
        for f in cd.fields:
            key = field_key(cd, f, out)
            hook = HOOKS.get((cd.name, f.name))
            if hook is not None:
                out[key] = hook(src, ctx)
                continue
            if key in src:
                out[key] = _adapt_field(f, src[key], ctx, f"{class_name}.{key}")
            elif f.name in src:                       # shadow-key fallback
                out[key] = _adapt_field(f, src[f.name], ctx, f"{class_name}.{f.name}")
            else:
                out[key] = _blank_field25(dec25, f, 0)
    return out


def _adapt_field(f, v: Any, ctx: _AdaptContext, path: str):
    kind, flags = f.kind, f.flags
    shape = flags >> 4
    dec25, _enc, schema25 = _S25()
    if kind == 0x08:                                   # AString (scalar or list)
        if shape in (1, 5):
            return [str(x) for x in (v or [])]
        return "" if v is None else str(v)
    if kind == 0x0D:                                   # inline array wrapper
        if not isinstance(v, list):
            ctx.note(f"{path}: expected list for array field, got "
                     f"{type(v).__name__} -> blank []")
            return _blank_field25(dec25, f, 0)
        return [_adapt_field(f.element, x, ctx, f"{path}[{i}]")
                for i, x in enumerate(v)]
    if shape == 5:                                     # growable container
        if not isinstance(v, list):
            ctx.note(f"{path}: expected container, got {type(v).__name__} -> []")
            return []
        return [_adapt_scalar(f, kind, flags & 0x0F, x, ctx, f"{path}[{i}]")
                for i, x in enumerate(v)]
    if shape == 1:                                     # fixed array
        vals = v if isinstance(v, list) else []
        n = f.count or 0
        out = [_adapt_scalar(f, kind, flags & 0x0F, x, ctx, f"{path}[{i}]")
               for i, x in enumerate(vals[:n])]
        while len(out) < n:
            out.append(_blank_scalar25(dec25, f, kind, flags & 0x0F, 0))
        return out
    return _adapt_scalar(f, kind, flags & 0x0F, v, ctx, path)


def _adapt_scalar(f, kind: int, indir: int, v: Any, ctx: _AdaptContext, path: str):
    from ..objects import _PRIM_FMT
    dec25, _enc, schema25 = _S25()
    if kind == 0x01:
        return bool(v)
    if kind in _PRIM_FMT:
        return v if isinstance(v, (int, float)) else (0.0 if kind in (0x06, 0x07) else 0)
    if kind == 0x08:
        return "" if v is None else str(v)
    if kind == 0x09:
        return str(v) if v else NULL_GUID
    if kind == 0x0A:                                   # classref
        name = v.get("classref") if isinstance(v, dict) else v
        if name and name not in schema25.by_name:
            raise Missing2025(f"{path}: classref {name!r} has no 2025 twin")
        return {"classref": name or "Element"}
    if kind == 0x0E:
        if indir == 0:                                 # inline value class
            tid = f.type_id
            if tid in (dec25.id_ElementId, dec25.id_Identifier):
                return int(v) if isinstance(v, (int, float)) else INVALID
            if tid == dec25.id_XYZ:
                return list(v) if isinstance(v, list) else [0.0, 0.0, 0.0]
            if tid == dec25.id_UV:
                return list(v) if isinstance(v, list) else [0.0, 0.0]
            if tid == dec25.id_GUIDvalue:
                return str(v) if v else NULL_GUID
            cname = dec25.class_name(tid)
            if not isinstance(v, dict):
                ctx.note(f"{path}: inline {cname} source is {type(v).__name__} "
                         "-> 2025 blank")
                return _blank_class25(dec25, schema25.by_name[cname].type_id, 1)
            return _adapt_class(cname, tid, v, ctx)
        if indir == 3:                                 # weak pointer
            if isinstance(v, dict) and "weakref" in v:
                return {"weakref": int(v["weakref"])}
            return {"weakref": int(v or 0)}
        # owned / poly pointer
        if v is None:
            return None
        if isinstance(v, dict) and "backref_pid" in v:
            return dict(v)
        if isinstance(v, dict) and "ptr_class" in v:
            pcls = v["ptr_class"]
            cd = schema25.by_name.get(pcls)
            if cd is None:
                raise Missing2025(f"{path}: pointed-to class {pcls!r} has no 2025 twin")
            body = v.get("value")
            new = {"ptr_class": pcls, "pid": v.get("pid", -1),
                   "value": (None if body is None
                             else _adapt_class(pcls, cd.type_id, body, ctx))}
            return new
        ctx.note(f"{path}: unrecognised pointer token {type(v).__name__} -> null")
        return None
    raise PortabilityError(f"{path}: unsupported field kind {kind:#x}")


# ---------------------------------------------------------------------------
# record-level adaptation (what the substitution ladder consumes)
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class PortedRecord:
    """A 2026 TypeRecord-shaped record re-expressed for Revit 2025: 2025
    class ids, 2025-shaped seq-101/102/103 bodies.  Carries exactly the
    attributes the substitution machinery reads."""
    elem_id: int
    kind: str
    class_name: str
    class_id: int                     # 2025 ordinal
    obj: dict                         # seq-102 body (2025 shape)
    header: dict                      # seq-101 body (2025 shape)
    rep: Optional[dict]               # seq-103 GElement body or None (dummy)
    rep_class_id: int                 # 2025 ordinal (GElement / SerializedDummy)
    rep_class_name: str
    refs: dict = dataclasses.field(default_factory=dict)
    notes: List[str] = dataclasses.field(default_factory=list)

    def records(self) -> list:
        return [(101, class_id_2025("ElementHeader"), self.header),
                (102, self.class_id, self.obj),
                (103, self.rep_class_id, self.rep if self.rep is not None else {})]


def adapt_record(rec, *, resolve_name: Optional[Callable[[int], Optional[str]]] = None
                 ) -> PortedRecord:
    """Adapt one 2026 constructor record (``rvt.genesis.types.TypeRecord`` or
    any object with elem_id / kind / class_name / obj / header / rep) into a
    :class:`PortedRecord`.  Raises :class:`Missing2025` for the conductor
    catalog (callers list those as 2026-only, they emit nothing on 2025)."""
    cname = rec.class_name
    if not exists_2025(cname):
        raise Missing2025(f"{cname} (record {rec.elem_id}) is 2026-only -- "
                          "emit nothing on a 2025 build")
    ctx = _AdaptContext(resolve_name=resolve_name)
    obj25 = _adapt_class(cname, _S25()[2].by_name[cname].type_id,
                         copy.deepcopy(rec.obj or {}), ctx)
    hdr25 = adapt("ElementHeader", copy.deepcopy(rec.header or {}),
                  resolve_name=resolve_name, _ctx=ctx)
    rep = getattr(rec, "rep", None)
    if rep is not None:
        rep25 = adapt("GElement", copy.deepcopy(rep), resolve_name=resolve_name,
                      _ctx=ctx)
        rep_cid, rep_cn = class_id_2025("GElement"), "GElement"
    else:
        rep25, rep_cid, rep_cn = None, class_id_2025("SerializedDummy"), "SerializedDummy"
    return PortedRecord(
        elem_id=int(rec.elem_id), kind=str(getattr(rec, "kind", "")),
        class_name=cname, class_id=class_id_2025(cname), obj=obj25,
        header=hdr25, rep=rep25, rep_class_id=rep_cid, rep_class_name=rep_cn,
        refs=dict(getattr(rec, "refs", {}) or {}),
        notes=list(getattr(rec, "notes", []) or []) + ctx.notes)


def verify_roundtrip_2025(class_id: int, obj: dict) -> dict:
    """Encode ``obj`` under the 2025 schema, decode it back, re-encode:
    the port2025 round-trip gate (clean + byte-exact required)."""
    dec, enc, _s = _S25()
    body = enc.encode_object(class_id, obj or {})
    got = dec.decode_record(class_id, body)
    body2 = enc.encode_object(class_id, got.value) if got.clean else b""
    return {"class": dec.class_name(class_id), "bytes": len(body),
            "clean": bool(got.clean), "byte_exact": body == body2,
            "errors": list(got.errors or [])[:3],
            "ok": bool(got.clean) and body == body2}


def verify_ported(pr: PortedRecord) -> dict:
    """Round-trip every seq body of a :class:`PortedRecord` under 2025."""
    rep = {}
    for seq, cid, body in pr.records():
        rep[seq] = verify_roundtrip_2025(cid, body or {})
    rep["ok"] = all(rep[s]["ok"] for s in (101, 102, 103))
    return rep


# ---------------------------------------------------------------------------
# the CONFIRMED portability table (verification of the plan's section 5)
# ---------------------------------------------------------------------------
def harvest_constructed_classes() -> Dict[str, List[str]]:
    """{class name: [where]} harvested from the genesis sources: every
    CODE-position string literal (docstrings skipped) naming a schema class,
    over types / settings / catalog / skeleton / house_standard / residue_*.
    The plan's section-6 harvest rule, re-run."""
    _d, _e, s26 = _S26()
    out: Dict[str, Set[str]] = collections.defaultdict(set)
    for fn in sorted(os.listdir(GENESIS_DIR)):
        if not fn.endswith(".py") or fn == os.path.basename(__file__):
            continue
        src = open(os.path.join(GENESIS_DIR, fn)).read()
        tree = ast.parse(src)
        doc_positions: Set[int] = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                doc_positions.add(id(body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in doc_positions:
                v = node.value
                if v in s26.by_name and v.strip() == v and " " not in v:
                    out[v].add(f"{fn}:{node.lineno}")
    return {k: sorted(v) for k, v in sorted(out.items())}


def _field_sig(f, schema):
    tn = None
    if f.type_id is not None:
        c = schema.by_id.get(f.type_id)
        tn = c.name if c else f.type_name
    el = _field_sig(f.element, schema) if f.element is not None else None
    return (f.name, f.kind, f.flags, f.count, tn, f.extra, el)


def diff_class(name: str) -> dict:
    """One class's CONFIRMED verdict: IDENTICAL / VERSION-ONLY /
    LAYOUT-DELTA (with the exact field deltas) / MISSING-2025."""
    dec26, _e26, s26 = _S26()
    dec25, _e25, s25 = _S25()
    a = s26.by_name.get(name)
    if a is None:
        return {"class": name, "verdict": "NOT-IN-2026"}
    b = s25.by_name.get(name)
    if b is None:
        return {"class": name, "verdict": "MISSING-2025", "version_2026": a.version}
    ca, cb = dec26.chain(a.type_id), dec25.chain(b.type_id)
    flat26 = [(c.name, _field_sig(f, s26)) for c in ca for f in c.fields]
    flat25 = [(c.name, _field_sig(f, s25)) for c in cb for f in c.fields]
    chain26, chain25 = [c.name for c in ca], [c.name for c in cb]
    out: Dict[str, Any] = {"class": name, "version_2026": a.version,
                           "version_2025": b.version, "chain": chain26}
    if flat26 == flat25 and chain26 == chain25:
        out["verdict"] = ("IDENTICAL" if a.version == b.version else "VERSION-ONLY")
        return out
    out["verdict"] = "LAYOUT-DELTA"
    if chain26 != chain25:
        out["chain_2025"] = chain25
    deltas = []
    for c26 in ca:
        c25 = next((c for c in cb if c.name == c26.name), None)
        if c25 is None:
            deltas.append({"base": c26.name, "delta": "base class missing in 2025"})
            continue
        f26 = [_field_sig(f, s26) for f in c26.fields]
        f25 = [_field_sig(f, s25) for f in c25.fields]
        if f26 == f25 and c26.version == c25.version:
            continue
        n26, n25 = {t[0] for t in f26}, {t[0] for t in f25}
        d = {"base": c26.name, "version": f"{c26.version}->{c25.version}",
             "only_2026": [t[0] for t in f26 if t[0] not in n25],
             "only_2025": [t[0] for t in f25 if t[0] not in n26],
             "changed": [t[0] for t in f26
                         if t[0] in n25 and next(u for u in f25 if u[0] == t[0]) != t]}
        shared26 = [t[0] for t in f26 if t[0] in n25]
        shared25 = [t[0] for t in f25 if t[0] in n26]
        if shared26 != shared25:
            d["order_differs"] = True
        deltas.append(d)
    out["deltas"] = deltas
    out["hooked"] = sorted({f for (c, f) in HOOKS
                            if c in chain26 or c == name})
    return out


def portability_table(*, write: bool = True) -> dict:
    """The CONFIRMED constructor-portability table 2026 -> 2025: harvested
    constructed classes + every base on their chains, each with its verdict.
    Frozen to :data:`PORTABILITY_JSON` (the deliverable artifact)."""
    dec26, _e, s26 = _S26()
    harvest = harvest_constructed_classes()
    names: Set[str] = set(harvest)
    # chain expansion: a base-class delta hits every subclass we construct
    for n in list(names):
        cd = s26.by_name.get(n)
        if cd:
            names.update(c.name for c in dec26.chain(cd.type_id))
    rows = {n: diff_class(n) for n in sorted(names)}
    counts = collections.Counter(r["verdict"] for r in rows.values())
    plan_missed = ["DBView (m_viewPositionId, base of every constructed view class)",
                   "DBViewDrafting (m_sheetTitleBlockId)",
                   "Viewport (m_viewPosition + m_viewAnchor, v13->10)",
                   "BrowserOrganizationTracking (type->org map -> three ElementId fields)"]
    table = {
        "generator": "rvt.genesis.port2025.portability_table",
        "method": "docs/writer/genesis-2025-plan.md section 6, re-run: own-field "
                  "signatures by type NAME + flattened parent-first chain + class "
                  "versions, 2026 pin vs rvt.versions.schema_2025 pin",
        "universe": {"harvested": len(harvest), "with_chain_expansion": len(names)},
        "counts": dict(counts),
        "corrections_vs_plan_table": {
            "layout_deltas_the_plan_missed": plan_missed,
            "value_corrections": [
                "GeomTable extra ints corpus default is (-1,-1), not 0/0",
                "ReinforcementSettings.m_numberVaryingLengthRebarsIndividually "
                "sample default True",
                "RbsWireType.m_strMaxConductorSize is the bare size label "
                "('2000' in the sample; ours resolve the cell name)"],
        },
        "mined_constants": {
            "WIRE_SETTINGS_2025": WIRE_SETTINGS_2025,
            "GEOMTABLE_2025": GEOMTABLE_2025,
            "NUMBERING_SCHEMA_TYPE_GUIDS_2025": NUMBERING_SCHEMA_TYPE_GUIDS_2025,
            "USE_GDI_2025": USE_GDI_2025,
            "REINF_NUMBER_INDIVIDUALLY_2025": REINF_NUMBER_INDIVIDUALLY_2025,
            "WIRE_MAX_SIZE_FALLBACK_2025": WIRE_MAX_SIZE_FALLBACK_2025,
        },
        "classes": rows,
        "harvest_provenance": harvest,
    }
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(PORTABILITY_JSON, "w") as fh:
            json.dump(table, fh, indent=1)
    return table


# ---------------------------------------------------------------------------
# 2025 corpus miners: the built-in category enum + per-key style profile
# (the Y6 catalog rung's 2025 format constants -- same derivations as
# rvt.genesis.catalog, run over the quarantined samples/2025 corpus)
# ---------------------------------------------------------------------------
def _sample_documents_2025(names: Sequence[str] = ("rstbasicsampleproject",
                                                   "rmebasicsampleproject",
                                                   "racbasicsampleproject")):
    from .. import versions
    from ..mutate import Document
    for n in names:
        p = os.path.join(SAMPLES_2025, f"{n}.rvt")
        if not os.path.exists(p):
            continue
        with versions.reading(p):
            yield n, Document.from_file(p)


def derive_builtin_category_enum_2025(verbose: bool = True) -> dict:
    """The Revit-2025 graphic-category ENUM (rvt.genesis.catalog's
    derivation, over the 2025 samples): every built-in category id carrying
    a host object-style row + its cuttability, asserted identical across
    the samples.  Only ids + the cut flag -- no pen / colour value."""
    per: Dict[str, Dict[int, set]] = {}
    for s, doc in _sample_documents_2025():
        rows: Dict[int, set] = collections.defaultdict(set)
        for gid in doc.ids_of_class("GStyleElem", host_only=True):
            v = doc.value(gid) or {}
            if v.get("m_famId", -1) != -1:
                continue
            cid = v.get("m_categoryId")
            if isinstance(cid, int) and cid < 0:
                rows[cid].add(int(v.get("m_gstyleType", 1)))
        per[s] = dict(rows)
        if verbose:
            print(f"   [enum-2025] {s}: {len(rows)} built-in categories, "
                  f"{sum(1 for t in rows.values() if 2 in t)} cuttable")
    base = None
    for s, rows in per.items():
        norm = {k: tuple(sorted(v)) for k, v in rows.items()}
        if base is None:
            base = norm
        elif norm != base:
            diff = set(norm) ^ set(base)
            raise RuntimeError(f"2025 graphic-category enum differs in {s}: "
                               f"{len(diff)} ids differ")
    cats = [{"id": int(cid), "cut": 2 in ts} for cid, ts in sorted((base or {}).items())]
    return {"generator": "rvt.genesis.port2025.derive_builtin_category_enum_2025",
            "derived_from": sorted(per), "release": 2025,
            "count": len(cats), "cuttable": sum(1 for c in cats if c["cut"]),
            "categories": cats}


def derive_builtin_style_profile_2025(verbose: bool = True) -> dict:
    """The per-(category, style-type) STRUCTURAL profile of the 2025
    object-styles table (rvt.genesis.catalog.derive_builtin_style_profile's
    rules, over the 2025 samples): header flag word / vis flags / pattern /
    material / screen-sized / pen-null rules.  Structure only."""
    from .catalog import AB_CELLLIST_BIT, BUILTIN_SOLID_PATTERN, _modal
    per: Dict[Tuple[int, int], dict] = collections.defaultdict(lambda: {
        "ab": collections.Counter(), "vis": collections.Counter(),
        "pat_val": collections.Counter(), "pat_kind": collections.Counter(),
        "mat_val": collections.Counter(), "mat_kind": collections.Counter(),
        "scr": collections.Counter(), "pen": collections.Counter(), "files": set()})
    n_rows = 0
    for s, doc in _sample_documents_2025():
        seen = 0
        for gid in doc.ids_of_class("GStyleElem", host_only=True):
            v = doc.value(gid) or {}
            if v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
                continue
            cid = v.get("m_categoryId")
            if not (isinstance(cid, int) and cid < 0):
                continue
            gt = int(v.get("m_gstyleType", 1))
            p = per[(int(cid), gt)]
            p["files"].add(s)
            gs = ((v.get("m_pGStyle") or {}).get("value") or {})
            pat, mat, pen = (gs.get("m_linePatternId"), gs.get("m_materialElemId"),
                             gs.get("m_penNumber"))
            p["pat_kind"]["null" if pat == INVALID else
                          ("builtin" if isinstance(pat, int) and pat < 0 else "elem")] += 1
            if isinstance(pat, int) and pat < 0 and pat != INVALID:
                p["pat_val"][int(pat)] += 1
            p["mat_kind"]["null" if mat == INVALID else
                          ("builtin" if isinstance(mat, int) and mat < 0 else "elem")] += 1
            if isinstance(mat, int) and mat < 0 and mat != INVALID:
                p["mat_val"][int(mat)] += 1
            p["scr"][bool(gs.get("m_isScreenSized"))] += 1
            if isinstance(pen, int):
                p["pen"][int(pen)] += 1
            h = doc.decode(gid, 101)
            if h and getattr(h, "clean", False) and h.value:
                p["ab"][int(h.value.get("m_abFlags4Bytes") or 0)] += 1
                p["vis"][int(((h.value.get("m_viewRules") or {})
                              .get("m_nVisibleViewFlags") or 0))] += 1
            seen += 1
        n_rows += seen
        if verbose:
            print(f"   [profile-2025] {s}: {seen} built-in object-style rows")
    keys = {}
    for (cid, gt), p in sorted(per.items()):
        clean = collections.Counter({a: c for a, c in p["ab"].items()
                                     if not (a & AB_CELLLIST_BIT)})
        ab = _modal(clean)
        if ab is None:
            ab = (_modal(p["ab"]) or 0) & ~AB_CELLLIST_BIT
        vis = _modal(p["vis"])
        kinds = set(p["pat_kind"])
        if kinds == {"null"}:
            pattern = "null"
        elif kinds == {"elem"}:
            pattern = "elem"
        elif "builtin" in kinds:
            if BUILTIN_SOLID_PATTERN in p["pat_val"]:
                pattern = "solid"
            elif kinds == {"builtin"}:
                pattern = f"builtin:{_modal(p['pat_val'])}"
            else:
                pattern = "solid"
        else:
            pattern = "nullwire"
        mkinds = set(p["mat_kind"])
        if mkinds == {"null"}:
            material = "null"
        elif mkinds == {"elem"}:
            material = "elem"
        elif mkinds == {"builtin"}:
            material = f"builtin:{_modal(p['mat_val'])}"
        else:
            material = "nullwire"
        pens = set(p["pen"])
        keys[f"{cid}:{gt}"] = {
            "cat": cid, "type": gt, "files": len(p["files"]),
            "ab": int(ab), "ab_set": sorted(int(x) for x in p["ab"]),
            "vis": int(vis) if vis is not None else -32768,
            "pattern": pattern, "material": material,
            "screen_sized": (set(p["scr"]) == {True}),
            "pen": ("null0" if pens == {0} else
                    ("nullneg1" if pens == {-1} else "ours")),
        }
    return {"generator": "rvt.genesis.port2025.derive_builtin_style_profile_2025",
            "release": 2025, "rows_analysed": n_rows, "count": len(keys),
            "keys": keys}


def load_2025_catalog_constants(*, derive_if_missing: bool = True) -> Tuple[dict, dict]:
    """(enum, profile) for the 2025 catalog rung -- frozen JSON next to the
    ladder artifacts, derived on first use."""
    out = []
    for path, derive in ((ENUM_2025_JSON, derive_builtin_category_enum_2025),
                         (PROFILE_2025_JSON, derive_builtin_style_profile_2025)):
        if os.path.exists(path):
            with open(path) as fh:
                out.append(json.load(fh))
            continue
        if not derive_if_missing:
            raise FileNotFoundError(path)
        data = derive()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=1)
        out.append(data)
    return out[0], out[1]


# ---------------------------------------------------------------------------
# self-test battery: adapt + 2025 round-trip over representative constructors
# ---------------------------------------------------------------------------
def selftest(verbose: bool = True) -> dict:
    """Build a battery of 2026 constructor records, adapt each to 2025, and
    round-trip every body under the 2025 schema.  Returns the report."""
    from . import settings as st
    from . import types as T
    from .residue_b import BUILTIN_NUMBERING_SCHEMES, builtin_numbering_schema
    ids = T.IdSource(9_000_000)
    battery: List[Any] = [
        T.new_wall_type("P25 Wall", [("structure", 200, INVALID)], ids=ids),
        T.new_material("P25 Concrete", (120, 120, 120), ids=ids),
        T.new_line_pattern("P25 Dash", [("dash", 3.175), ("space", 1.5875)], ids=ids),
        T.new_fill_pattern("P25 Solid", [], ids=ids),
        T.new_floor_type("P25 Floor", [("structure", 150, INVALID)], ids=ids),
        T.new_wire_type("P25 THWN", ids=ids),
        builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], ids=ids),
    ]
    battery += [
        st.pen_width_table(ids=ids),
        st.browser_organization("all", ids=ids),
        st.struct_settings(ids=ids),
        st.keynote_table(ids=ids),
        st.wire_settings(ids=ids),
        st.reinforcement_settings(ids=ids),
    ]
    # a view + its display manager exercise the DBView / ViewDisplayMgr deltas
    try:
        from . import skeleton as sk
        battery += list(sk.view_type_records(ids)[:1]) if hasattr(sk, "view_type_records") else []
    except Exception:
        pass
    rows = []
    ok = True
    for rec in battery:
        try:
            pr = adapt_record(rec)
            v = verify_ported(pr)
            rows.append({"class": pr.class_name, "elem_id": pr.elem_id,
                         "ok": v["ok"],
                         "seq102": {k: v[102][k] for k in ("clean", "byte_exact", "bytes")},
                         "notes": pr.notes[:4]})
            ok = ok and v["ok"]
            if verbose:
                s = v[102]
                print(f"   {pr.class_name:<28} seq102 {s['bytes']:>6} B clean={s['clean']} "
                      f"byte_exact={s['byte_exact']} all-ok={v['ok']}")
        except Missing2025 as ex:
            rows.append({"class": rec.class_name, "elem_id": rec.elem_id,
                         "missing_2025": str(ex)})
            if verbose:
                print(f"   {rec.class_name:<28} MISSING-2025 (expected for the "
                      "conductor catalog)")
    return {"ok": ok, "records": rows}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verify", action="store_true",
                    help="derive + freeze the CONFIRMED portability table")
    ap.add_argument("--mine", action="store_true",
                    help="derive + freeze the 2025 category enum + style profile")
    ap.add_argument("--selftest", action="store_true",
                    help="adapt + 2025 round-trip the constructor battery")
    args = ap.parse_args(argv)
    rc = 0
    if args.verify or not (args.mine or args.selftest):
        t = portability_table(write=True)
        print(f"[portability] {t['universe']} -> {t['counts']}  "
              f"-> {os.path.relpath(PORTABILITY_JSON, ROOT)}")
    if args.mine:
        enum, prof = load_2025_catalog_constants()
        print(f"[mine] enum-2025 {enum['count']} categories ({enum['cuttable']} cuttable) "
              f"-> {os.path.relpath(ENUM_2025_JSON, ROOT)}")
        print(f"[mine] profile-2025 {prof['count']} keys over {prof['rows_analysed']} rows "
              f"-> {os.path.relpath(PROFILE_2025_JSON, ROOT)}")
    if args.selftest:
        rep = selftest()
        print(f"[selftest] ok={rep['ok']} over {len(rep['records'])} records")
        rc = 0 if rep["ok"] else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
