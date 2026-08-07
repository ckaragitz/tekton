"""genesis/types.py -- pure constructors for SYSTEM-FAMILY TYPES + document-
standard elements: the expression that survives even a family-free reduction
and is NOT a loadable family.

Every function here builds a COMPLETE, schema-valid serialized-object dict
from PLAIN PARAMETERS (millimetres, inches, volts, RGB, names).  Nothing is
cloned from an Autodesk file: each object starts from a schema-directed
SKELETON (:func:`blank_object` walks the archive class map ``Formats/Latest``
and emits a type-correct default for every field of the class + all its
bases, parent-first) and the constructor overlays exactly the fields that ARE
the type's DEFINITION.  The field maps (definition vs. machinery vs.
references) are documented in ``docs/writer/genesis-types.md``; every value
below is either a caller parameter, a documented format constant, or a
sentinel (-1 = invalid ElementId, [] = empty container, null pointer).

Each constructor returns a :class:`TypeRecord` -- the (class_id, obj_dict,
header_dict) triple the record machinery needs, shaped exactly like
``rvt.mutate.NewElement`` (seq 101 ElementHeader / seq 102 object / seq 103
rep), so it plugs into ``rvt.encode.encode_record`` and
``rvt.commit.commit_new_elements`` unchanged (see
:meth:`TypeRecord.as_new_element`).  Id allocation is the caller's: pass an
explicit ``elem_id`` or an ``ids`` allocator (a :class:`GenesisCatalog`, an
:class:`IdSource`, an ``rvt.mutate.Document`` with ``next_id()``, or an
int watermark).

Units (verified against the rme/rst/rac 2026 samples):
    lengths          feet            (mm / 304.8, inches / 12)
    electrical volts internal E = V * 10.7639104167  (kg*ft^2/(s^3*A):
                     the metric watt converted m^2 -> ft^2; 240 V is stored
                     as 2583.3385, 208 V as 2238.89 -- KNOWLEDGE.md)
    current          amperes stored raw (wire ampacity 15.0 = 15 A)
    temperature      kelvin (ampacity correction bands 294.15 K = 21 C)
    angles           radians
    colors           u32 Windows COLORREF (r | g<<8 | b<<16); 0 = black

Demo / self-test::

    python -m rvt.genesis.types            # build + round-trip every kind

TERRITORY note: this module deliberately does not touch mutate/encode/commit;
it produces objects that those (proven) layers consume.
"""
from __future__ import annotations

import json
import math
import os
import struct
import sys
import zlib
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Optional, Sequence, Union

# ---------------------------------------------------------------------------
# unit conversions & format constants
# ---------------------------------------------------------------------------

MM_PER_FT = 304.8
IN_PER_FT = 12.0

#: volts -> Revit internal electrical potential (kg*ft^2 / (s^3*A)).
#: Verified: RbsVoltageType "240" stores m_dActualVoltage 2583.33850001
#: (240 * 10.7639104167), "120" stores 1291.66925 (KNOWLEDGE.md: 208 V ->
#: 2238.89).  The factor is m^2 -> ft^2 (voltage = W/A, watt carries m^2).
VOLT_TO_INTERNAL = 10.7639104167097

INVALID = -1                      # invalid ElementId
NO_DESIGN_OPTION = -1
INTERNAL_DESIGN_OPTION = -4       # design-option sentinel carried by document
                                  # standard elements (categories, styles, fonts)
NULL_GUID = "00000000-0000-0000-0000-000000000000"

#: built-in line-pattern ids (negative = Revit built-ins, portable across
#: files; LinePatternElement.GetSolidPatternId() == -3000010 in the API)
LINEPATTERN_SOLID = -3000010

#: BuiltInCategory ids (Autodesk's fixed public enum -- interoperability
#: constants, not content) used by the constructors' element headers.
OST_Walls = -2000011
OST_Floors = -2000032
OST_Roofs = -2000035
OST_Ceilings = -2000038
OST_Materials = -2000700
OST_Conduit = -2008132
OST_ConduitStandards = -2008144            # ConduitStandardType category
OST_CableTray = -2008130
OST_Wire = -2008039
OST_WireMaterial = -2008111
OST_WireInsulation = -2008112
OST_WireTemperatureRating = -2008113
OST_ElectricalVoltage = -2008040            # RbsVoltageType category
OST_ElectricalDistributionSys = -2008041    # RbsDistributionSysType category
OST_ElectricalDemandFactor = -2008142       # ElectricalDemandFactorDefinition
OST_ElectricalLoadClassification = -2008143
OST_TextNotes = -2000300
OST_TextNoteLineStyle = -2000059            # parent of a text type's own
                                            # line-style sub-category
OST_ConduitFitting = -2008128
OST_CableTrayFitting = -2008126

#: CompoundStructure layer functions (the MaterialFunctionAssignment enum).
LAYER_FUNCTION = {
    "structure": 1, "substrate": 2, "insulation": 3, "thermal": 3, "air": 3,
    "finish1": 4, "exterior": 4, "finish2": 5, "interior": 5,
    "membrane": 100,
}
MEMBRANE_PRIORITY = 999

#: nominal-voltage -> (min, max) service ranges (published NEC/ANSI facts)
#: used as defaults when the caller gives only the nominal voltage.
NOMINAL_VOLTAGE_RANGES = {
    120: (110.0, 130.0), 208: (200.0, 220.0), 240: (220.0, 250.0),
    277: (260.0, 280.0), 480: (460.0, 490.0), 600: (580.0, 610.0),
    347: (330.0, 360.0), 4160: (4000.0, 4300.0),
}

# per-class ElementHeader constants observed on the 2026 samples
# (m_abFlags4Bytes, m_viewRules.m_nVisibleViewFlags).  [verified rme]
_HDR = {
    "BasicWallType": (2364, -32640), "FloorAttributes": (30, -32640),
    "RoofAttributes": (30, -32640), "CompoundCeilingType": (30, -32640),
    "RbsConduitType": (14, -32640), "ConduitStandardType": (14, -32768),
    "RbsCableTrayType": (14, -32640), "RbsWireType": (30, -32640),
    "RbsWireMaterialType": (14, -32768), "RbsWireInsulationType": (30, -32768),
    "RbsWireTemperatureRatingType": (30, -32768),
    "RbsVoltageType": (30, -32768), "RbsDistributionSysType": (30, -32768),
    "ElectricalLoadClassification": (67108878, -32768),
    "ElectricalDemandFactorDefinition": (67117070, -32768),
    "MaterialElem": (67108894, -32736), "LinePatternElem": (67117086, -32768),
    "FillPatternElem": (67117086, -32768), "TextNoteAttributes": (14, -32768),
    "FontElem": (8202, -32768), "DimensionStyle": (30, -32768),
    "CategoryElem": (8202, -32768), "GStyleElem": (8202, -32768),
    "GStyleElem:objectstyle": (67108894, -32768),
    "CustomElement": (8206, -4225), "ConduitSizesElem": (8206, -32768),
    "CableTraySizesElem": (8206, -32768), "ElectricalSetting": (8206, -32768),
    "RbsWireSizesElem": (8222, -32768),
}
_HDR_DEFAULT = (30, -32768)


def mm(x_mm: float) -> float:
    """millimetres -> feet."""
    return float(x_mm) / MM_PER_FT


def inches(x_in: float) -> float:
    """inches -> feet."""
    return float(x_in) / IN_PER_FT


def volts(v: float) -> float:
    """volts -> Revit internal electrical potential units."""
    return float(v) * VOLT_TO_INTERNAL


def rgb(r: int, g: int = 0, b: int = 0) -> int:
    """(r, g, b) 0-255 -> Windows COLORREF u32 (r | g<<8 | b<<16)."""
    if isinstance(r, (tuple, list)):
        r, g, b = r
    return (int(r) & 0xFF) | ((int(g) & 0xFF) << 8) | ((int(b) & 0xFF) << 16)


# ---------------------------------------------------------------------------
# schema / codec singleton
# ---------------------------------------------------------------------------

_STATE = {}


def _S():
    """Lazy (decoder, encoder, schema) triple.  Loads the canonical 2026 class
    map once; shared by every constructor + the round-trip verifier."""
    if not _STATE:
        from ..objects import ObjectDecoder
        from ..encode import ObjectEncoder
        dec = ObjectDecoder()
        _STATE["dec"] = dec
        _STATE["enc"] = ObjectEncoder(decoder=dec)
        _STATE["schema"] = dec.schema
    return _STATE["dec"], _STATE["enc"], _STATE["schema"]


def class_id(name: str) -> int:
    """u16 archive class id of ``name`` (the schema type_id, identity map)."""
    _dec, _enc, schema = _S()
    cd = schema.by_name.get(name)
    if cd is None:
        raise KeyError(f"class {name!r} not in the archive class map")
    return cd.type_id


# ---------------------------------------------------------------------------
# schema-directed SKELETON: a type-correct default value for every field
# ---------------------------------------------------------------------------

def blank_object(class_name: str) -> dict:
    """A complete, encoder-ready object dict for ``class_name`` with EVERY
    field of the class and its bases present (parent-first) and defaulted:

    bool False; numerics 0/0.0; AString ""; GUID zero; ElementId/Identifier
    -1; XYZ/UV zeros; containers []; fixed arrays their schema count of
    defaults; owned pointers null; weak pointers 0; inline value classes
    recursively blanked; classref -> the class's own name (fixed by callers
    where it matters, e.g. ElementHeader.m_classDef).

    This is the FOUNDATION of the "no cloned payload" principle: the object
    starts as pure schema structure and each constructor overlays only the
    fields it defines.  Every product of this function round-trips through
    ``rvt.encode`` -> ``rvt.objects`` byte-exact (tests/test_genesis_types).
    """
    dec, _enc, schema = _S()
    cd = schema.by_name.get(class_name)
    if cd is None:
        raise KeyError(f"class {class_name!r} not in the archive class map")
    return _blank_class(dec, cd.type_id, 0)


def _blank_class(dec, type_id: int, depth: int) -> dict:
    from ..objects import field_key
    out: dict = {}
    for cd in dec.chain(type_id):
        for f in cd.fields:
            out[field_key(cd, f, out)] = _blank_field(dec, f, depth)
    return out


def _blank_field(dec, f, depth: int):
    kind, flags = f.kind, f.flags
    shape, indir = flags >> 4, flags & 0x0F
    if kind == 0x08:                                   # AString
        return [] if shape in (1, 5) else ""
    if kind == 0x0D:                                   # inline array wrapper
        if shape == 1:                                 # FIXED array of arrays
            return [_blank_field(dec, f.element, depth) for _ in range(f.count or 0)]
        return []
    if shape == 5:                                     # growable container
        return []
    if shape == 1:                                     # fixed array
        return [_blank_scalar(dec, f, kind, indir, depth) for _ in range(f.count or 0)]
    return _blank_scalar(dec, f, kind, indir, depth)


def _blank_scalar(dec, f, kind: int, indir: int, depth: int):
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
        if indir == 0:                                 # inline value class
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
            return _blank_class(dec, tid, depth + 1)
        if indir == 3:                                 # weak pointer
            return {"weakref": 0}
        return None                                    # owned/poly pointer null
    raise ValueError(f"unsupported field kind {kind:#x} ({f.name})")


def _ptr(class_name: str, value: dict, pid: int = -1) -> dict:
    """An owned-pointer token exactly as the decoder produces one."""
    return {"ptr_class": class_name, "pid": pid, "value": value}


def _owned(class_name: str, **overlay) -> dict:
    """Owned pointer to a blanked ``class_name`` object with overlays."""
    v = blank_object(class_name)
    v.update(overlay)
    return _ptr(class_name, v)


# ---------------------------------------------------------------------------
# Element / Symbol machinery (the non-definitional base fields)
# ---------------------------------------------------------------------------

def _param_set(class_name: str, params: Optional[dict] = None) -> Optional[dict]:
    """ParamValueSetX pointer with an id->value paramSet (None = null)."""
    if params is None:
        return None
    entries = [{"m_paramId": pid, "m_value": val} for pid, val in params.items()]
    # Double / Int / AString sets serialise m_value FIRST for numeric sets
    if class_name in ("ParamValueSetDouble",):
        entries = [{"m_value": e["m_value"], "m_paramId": e["m_paramId"]} for e in entries]
    return _owned(class_name, m_paramSet=entries)


def element_defaults(obj: dict, elem_id: int, *,
                     double_params=None, int_params=None,
                     astring_params=None, elemid_params=None,
                     design_option: int = NO_DESIGN_OPTION) -> dict:
    """Overlay the universal ``Element`` base fields onto a blanked object.

    ``*_params`` = None emits a null param-set pointer; ``{}`` (or a mapping)
    emits a present set (matching what the given kind of type carries in a
    Revit-authored file -- e.g. wall types carry a present empty Double set).
    """
    obj["m_pParamValueSetDouble"] = _param_set("ParamValueSetDouble", double_params)
    obj["m_pParamValueSetInt"] = _param_set("ParamValueSetInt", int_params)
    obj["m_pParamValueSetAString"] = _param_set("ParamValueSetAString", astring_params)
    obj["m_pParamValueSetElementId"] = _param_set("ParamValueSetElementId", elemid_params)
    obj.setdefault("m_geomSteps", None)
    obj.setdefault("m_pGeomTable", None)
    obj["m_constrInfo"] = []
    obj.setdefault("m_cellList", None)
    obj["m_docAccess"] = {"m_pDoc": {"weakref": 1}}      # weak -> the document
    obj["m_id"] = int(elem_id)
    obj["m_assocLevelId"] = INVALID
    obj["m_famId"] = INVALID
    obj["m_unplacedOwnerId"] = INVALID
    obj["m_ownerDBViewId"] = INVALID
    obj["m_createdPhaseId"] = INVALID
    obj["m_demolishedPhaseId"] = INVALID
    obj["m_designOptionId"] = design_option
    obj["m_locked"] = False
    obj["m_moribund"] = False
    obj["m_dummy"] = False
    return obj


def symbol_defaults(obj: dict, name: str, *, preview_id: int = INVALID,
                    render_style_id: int = INVALID) -> dict:
    """Overlay the ``Symbol`` base fields (the TYPE NAME lives here)."""
    obj["m_symbolInfo"] = _owned("SymbolInfo", m_name=str(name))
    obj["m_renderStyleId"] = int(render_style_id)
    obj["m_previewElemId"] = int(preview_id)
    return obj


def _analytical_cell_list(with_pattern_helper: bool = False,
                          taperable: bool = False) -> dict:
    """HostObjAttr cell list: the analysis-property cells every host type
    carries (values are Revit's own defaults: absorptance 0.1, roughness 1)."""
    cells = [_owned("AnalyticalPropertiesCell", m_absorptance=0.1, m_roughness=1)]
    if with_pattern_helper:
        cells.append(_owned("PatternHelper", m_PatternPositionMap=[],
                            m_substituteFaceMap=[]))
    if taperable:
        cells.append(_owned("TaperableWallTypeAngleParametersCell",
                            m_defaultTaperedExteriorAngle=0.0,
                            m_defaultTaperedInteriorAngle=0.0))
        cells.append(_owned("TaperableWallTypeWidthAtParametersCell",
                            m_widthMeasuredAt=0))
    return _ptr("CellList", {"m_cells": cells})


def element_header(class_name: str, category_id: int, elem_id: int, *,
                   deletion_ids: Iterable[int] = (), family_id: int = INVALID,
                   appearance_ids: Iterable[int] = (),
                   design_option: int = NO_DESIGN_OPTION,
                   ab_flags: Optional[int] = None,
                   visible_flags: Optional[int] = None,
                   hdr_key: Optional[str] = None) -> dict:
    """The seq-101 ``ElementHeader`` object for a new element.

    ``deletion_ids`` = the ids that must accompany this element's deletion
    (Revit lists the element itself plus everything it owns/references:
    materials, fittings, its param elements, its preview).  The element's own
    id is always included.  ``hdr_key`` selects an alternate flag preset
    (e.g. 'GStyleElem:objectstyle').
    """
    ab, vis = _HDR.get(hdr_key or class_name, _HDR_DEFAULT)
    ab = ab if ab_flags is None else int(ab_flags)
    vis = vis if visible_flags is None else int(visible_flags)
    h = blank_object("ElementHeader")
    h["m_regenHistory"] = {"m_historyMap": []}
    h["m_categroryId"] = int(category_id)
    h["m_familyId"] = int(family_id)
    h["m_ownerViewId"] = INVALID
    h["m_designOptionId"] = int(design_option)
    h["m_unplacedOwnerId"] = INVALID
    h["m_miscId"] = INVALID
    h["m_viewRules"] = {"m_nVisibleViewFlags": vis}
    h["m_abFlags4Bytes"] = ab
    h["m_classDef"] = {"m_ref": {"classref": class_name}}
    h["m_pBBox"] = None
    dele = sorted({int(elem_id), *[int(i) for i in deletion_ids if i not in (None, INVALID)]})
    h["m_parents"] = _ptr("ElementParents", {
        "m_deletion": dele,
        "m_regenOnly": [],
        "m_regenWildcards": [],
        "m_nonDetermRegenChildren": [],
        "m_dependencyParents": [],
        "m_appearanceParents": sorted({int(i) for i in appearance_ids}),
        "m_deferredParents": [],
        "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
        "m_hasNonDetermRegenChildren": False,
    })
    return h


# ---------------------------------------------------------------------------
# TypeRecord + id allocation
# ---------------------------------------------------------------------------

@dataclass
class TypeRecord:
    """One synthesized document element = (class_id, obj_dict, header_dict).

    ``rep`` None => the seq-103 representation is a ``SerializedDummy``
    (every type except wall types); otherwise the seq-103 GElement dict.
    ``refs`` names the ids this type references (materials, standards, ...)
    so callers can verify closure; ``notes`` carry per-record caveats.
    """
    elem_id: int
    kind: str
    class_name: str
    class_id: int
    category_id: int
    obj: dict
    header: dict
    rep: Optional[dict] = None
    refs: dict = dc_field(default_factory=dict)
    notes: list = dc_field(default_factory=list)

    # (class_id, obj_dict, header_dict) contract -------------------------
    def as_tuple(self):
        return (self.class_id, self.obj, self.header)

    def __iter__(self):
        return iter(self.as_tuple())

    @property
    def rep_class_id(self) -> int:
        return class_id("GElement") if self.rep is not None else class_id("SerializedDummy")

    @property
    def rep_class_name(self) -> str:
        return "GElement" if self.rep is not None else "SerializedDummy"

    def records(self) -> list:
        """[(seq, class_id, object-dict)] exactly like mutate.NewElement.records()."""
        return [(101, class_id("ElementHeader"), self.header),
                (102, self.class_id, self.obj),
                (103, self.rep_class_id, self.rep if self.rep is not None else {})]

    def encode(self) -> dict:
        """{seq: framed record bytes} via rvt.encode (stamps auto-computed)."""
        from ..encode import encode_record
        return {seq: encode_record(seq, self.elem_id, None, cid, o)
                for seq, cid, o in self.records()}

    def as_new_element(self, creation_ep: int = 0):
        """Adapter -> ``rvt.mutate.NewElement`` (+ ``ElemRecPlan``) so a
        TypeRecord flows through mutate/commit without any change there."""
        from ..mutate import NewElement, ElemRecPlan
        er = ElemRecPlan(elem_id=self.elem_id, original_id=self.elem_id,
                         creation_ep=creation_ep, modified_ep=creation_ep,
                         user_modified_ep=creation_ep)
        return NewElement(self.elem_id, self.kind, self.class_name, self.class_id,
                          self.header, self.obj, self.rep, er, template_id=INVALID,
                          notes=list(self.notes))

    def to_json(self) -> dict:
        return {"elem_id": self.elem_id, "kind": self.kind,
                "class": self.class_name, "class_id": f"{self.class_id:#06x}",
                "category_id": self.category_id, "refs": self.refs,
                "seq101_ElementHeader": self.header, "seq102_object": self.obj,
                "seq103": (self.rep if self.rep is not None else
                           {"class": "SerializedDummy", "psize": 2}),
                "notes": self.notes}

    # verification ---------------------------------------------------------
    def roundtrip(self) -> dict:
        """Encode each record then decode it back: proves the object is
        schema-valid and byte-exact reversible.  Returns a per-seq report."""
        dec, enc, _s = _S()
        rep = {}
        for seq, cid, obj in self.records():
            body = enc.encode_object(cid, obj or {})
            got = dec.decode_record(cid, body)
            body2 = enc.encode_object(cid, got.value) if got.clean else b""
            rep[seq] = {"class": dec.class_name(cid), "bytes": len(body),
                        "clean": bool(got.clean), "byte_exact": body == body2,
                        "value_equal": _values_equal(got.value, obj or {}),
                        "errors": got.errors}
        rep["ok"] = all(r["clean"] and r["byte_exact"] for k, r in rep.items()
                        if k != "ok")
        return rep


def _values_equal(a, b) -> bool:
    """Structural equality tolerant of float repr (round-trip via JSON)."""
    def norm(v):
        if isinstance(v, dict):
            return {k: norm(x) for k, x in v.items()}
        if isinstance(v, list):
            return [norm(x) for x in v]
        if isinstance(v, float):
            return struct.unpack("<d", struct.pack("<d", v))[0]
        if isinstance(v, bool):
            return bool(v)
        return v
    return norm(a) == norm(b)


class IdSource:
    """Monotonic ElementId allocator for standalone genesis (no template).

    ``start`` = the first id issued.  A real document continues from its
    ``IdentifierSource.m_last`` watermark -- pass an ``rvt.mutate.Document``
    (its ``next_id()``) instead of this class in that case.
    """

    def __init__(self, start: int = 100_000):
        self._next = int(start)

    def next_id(self) -> int:
        v = self._next
        self._next += 1
        return v

    @property
    def last_issued(self) -> int:
        return self._next - 1


IdArg = Union[int, IdSource, Any, None]


def _alloc(ids: IdArg, elem_id: Optional[int] = None) -> int:
    """Resolve the new element's id from an explicit id or an allocator."""
    if elem_id is not None:
        return int(elem_id)
    if ids is None:
        raise ValueError("pass elem_id= or an ids= allocator "
                         "(GenesisCatalog / IdSource / mutate.Document)")
    if isinstance(ids, int):
        raise ValueError("ids= must be an allocator (IdSource / Document / "
                         "GenesisCatalog); pass elem_id= for a fixed id")
    fn = getattr(ids, "next_id", None)
    if fn is None:
        raise TypeError(f"{type(ids).__name__} has no next_id() allocator")
    return int(fn())


def _record(kind: str, class_name: str, category_id: int, elem_id: int,
            obj: dict, *, deletion_ids: Iterable[int] = (), rep=None,
            refs: Optional[dict] = None, notes: Optional[list] = None,
            family_id: int = INVALID,
            design_option: int = NO_DESIGN_OPTION,
            hdr_key: Optional[str] = None) -> TypeRecord:
    hdr = element_header(class_name, category_id, elem_id,
                         deletion_ids=deletion_ids, family_id=family_id,
                         design_option=design_option, hdr_key=hdr_key)
    return TypeRecord(elem_id, kind, class_name, class_id(class_name),
                      category_id, obj, hdr, rep, refs or {}, notes or [])


# ---------------------------------------------------------------------------
# WALL / FLOOR / ROOF / CEILING TYPES (HostObjAttr + CompoundStructure)
# ---------------------------------------------------------------------------

def _norm_layers(layers) -> list:
    """Normalise the caller's layer list -> [(function_code, width_ft, material_id)].

    Each layer may be (function, thickness_mm, material_id) or a dict
    {function, thickness_mm | thickness_ft, material_id}.  ``function`` is a
    name from :data:`LAYER_FUNCTION` or the raw integer code.  Exterior side
    first (Revit's layer order: exterior finish ... structure ... interior).
    """
    out = []
    for L in layers:
        if isinstance(L, dict):
            fn = L.get("function", "structure")
            th_ft = (mm(L["thickness_mm"]) if "thickness_mm" in L
                     else float(L.get("thickness_ft", 0.0)))
            mat = L.get("material_id", INVALID)
        else:
            fn, th, mat = (list(L) + [INVALID])[:3]
            th_ft = mm(th)
        code = LAYER_FUNCTION[fn] if isinstance(fn, str) else int(fn)
        out.append((code, float(th_ft), int(mat) if mat is not None else INVALID))
    if not out:
        raise ValueError("a compound structure needs at least one layer")
    return out


def _layer_records(norm) -> list:
    recs = []
    for i, (code, width, mat) in enumerate(norm):
        recs.append({
            "m_layerWidth": width,
            "m_materialId": mat,
            "m_profileId": INVALID,
            "m_layerFunction": code,
            "m_layerPriority": MEMBRANE_PRIORITY if code == 100 else code,
            "m_embeddingType": INVALID,
            "m_layerId": i,
            "m_layerCapFlag": True,
        })
    return recs


def _shell_counts(norm) -> tuple:
    """(exterior shell layers, interior shell layers, structural core index).

    Revit's rule (verified 3 wall types): the core = the contiguous run of
    'structure' (function 1) layers; layers before it form the exterior
    shell, layers after it the interior shell; the structural material index
    is the first structure layer.
    """
    funcs = [c for c, _w, _m in norm]
    if 1 not in funcs:
        return (0, 0, 0)
    first = funcs.index(1)
    last = len(funcs) - 1 - funcs[::-1].index(1)
    return (first, len(funcs) - 1 - last, first)


def _vertical_regions(norm, sample_height_ft: float,
                      cut_off_ft: Optional[float] = None) -> dict:
    """The wall type's ``VerticalRegionsStructure`` (the layer LAYOUT).

    Reproduces Revit's construction for a non-vertically-compound wall
    (verified against 'MW 17.5' (1 layer), 'Exterior - Block on Mtl. Stud'
    (7 layers incl. two 0-width membranes) and the racbasic 6-layer timber
    wall):
      * one region per NON-ZERO-width layer (zero-width membrane layers get
        no region);
      * boundary segments (orientation 0) at the cumulative widths, origin
        0.0 at the exterior face, ids 0..B-1 in exterior->interior order;
        outer faces carry regionId [region, -1], internal boundaries carry
        [outer_region, inner_region];
      * per region two face segments (orientation 1) at coordinate 0.0 and
        sample_height, ids B+2r (bottom) / B+2r+1 (top), regionId
        [region, -1];
      * region r spans segments [left_boundary, bottom_face, right_boundary,
        top_face];
      * array order: bottom faces, top faces, then boundaries (as authored).
    """
    widths = [w for _c, w, _m in norm]
    regions = [i for i, w in enumerate(widths) if w > 0]      # layer indices
    if not regions:                                           # degenerate 0-width
        regions = list(range(len(widths)))
    n = len(regions)
    B = n + 1                                                 # boundary count
    # cumulative coordinates of region boundaries
    coords = [0.0]
    acc = 0.0
    for li in regions:
        acc += widths[li]
        coords.append(acc)
    segs = []
    # boundaries (orientation 0), ids 0..B-1
    bounds = []
    for b in range(B):
        left_r = b - 1 if b >= 1 else -1
        right_r = b if b < n else -1
        rid = [b, -1] if b == 0 else ([b - 1, -1] if b == n else [left_r, right_r])
        bounds.append({"m_coordinate": coords[b], "m_id": b,
                       "m_orientation": 0, "m_regionId": rid})
    # faces (orientation 1)
    bottoms, tops = [], []
    for r in range(n):
        bottoms.append({"m_coordinate": 0.0, "m_id": B + 2 * r,
                        "m_orientation": 1, "m_regionId": [r, -1]})
        tops.append({"m_coordinate": float(sample_height_ft), "m_id": B + 2 * r + 1,
                     "m_orientation": 1, "m_regionId": [r, -1]})
    segs = bottoms + tops + bounds
    region_recs = [{"m_id": r, "m_segmentIds": [r, B + 2 * r, r + 1, B + 2 * r + 1]}
                   for r in range(n)]
    r2l = [{"first": r, "second": regions[r]} for r in range(n)]
    return {
        "regions_layers": regions,
        "structure": _owned("VerticalRegionsStructure",
                            m_extendableRegionIdsTop=[],
                            m_extendableRegionIdsBottom=[],
                            m_regionToLayerMap=r2l,
                            m_grid={"m_segments": segs, "m_regions": region_recs,
                                    "m_tol": 1e-09},
                            m_sampleHeight=float(sample_height_ft),
                            m_cutOffHeight=float(sample_height_ft if cut_off_ft is None
                                                 else cut_off_ft),
                            m_bPreviewDimsAreValid=False,
                            m_wallSweeps=[], m_reveals=[]),
    }


def _seg_ref_face_keys(norm) -> list:
    """Reference-face identity keys for the boundary segments (the stable
    'core boundary' / 'shell boundary' references dimensions attach to).

    Rule (verified on 3 wall types): core exterior boundary -> key0 29;
    core interior boundary -> key0 30; internal boundaries INSIDE the exterior
    shell -> key0 31 with a running key1 counter; inside the core -> key0 32
    (counter); inside the interior shell -> key0 33 (counter [hypothesis:
    unexercised by the samples]).  The outermost faces carry no key unless
    they coincide with a core boundary (single-layer wall: 29 and 30 on the
    two faces).  Segment ids follow :func:`_vertical_regions` (boundaries
    0..B-1 over the NON-ZERO-width regions, exterior->interior).
    """
    widths = [w for _c, w, _m in norm]
    funcs = [c for c, _w, _m in norm]
    regions = [i for i, w in enumerate(widths) if w > 0] or list(range(len(widths)))
    if 1 in funcs:
        core_first = funcs.index(1)
        core_last = len(funcs) - 1 - funcs[::-1].index(1)
    else:
        core_first = core_last = regions[0]
    keys = []
    cnt31 = cnt32 = cnt33 = 0
    B = len(regions) + 1
    for b in range(B):
        # layer indices on either side of boundary b
        left_layer = regions[b - 1] if b >= 1 else None
        right_layer = regions[b] if b < len(regions) else None
        if right_layer is not None and right_layer == core_first:
            keys.append({"m_id": b, "m_key0": 29, "m_key1": 0})
        elif left_layer is not None and left_layer == core_last:
            keys.append({"m_id": b, "m_key0": 30, "m_key1": 0})
        elif left_layer is None or right_layer is None:
            continue                                   # outer face, no key
        elif left_layer < core_first:                  # inside exterior shell
            keys.append({"m_id": b, "m_key0": 31, "m_key1": cnt31})
            cnt31 += 1
        elif right_layer > core_last:                  # inside interior shell
            keys.append({"m_id": b, "m_key0": 33, "m_key1": cnt33})
            cnt33 += 1
        else:                                          # inside the core
            keys.append({"m_id": b, "m_key0": 32, "m_key1": cnt32})
            cnt32 += 1
    return keys


def _compound_structure(norm, *, vertical: bool, sample_height_ft: float = 20.0,
                        cut_off_ft: Optional[float] = None,
                        fill_pattern_id: int = INVALID, end_cap: int = 0,
                        opening_wrapping: int = 0) -> tuple:
    """CompoundStructure pointer + the vertical-region layer list (walls)."""
    layers = _layer_records(norm)
    ext, inte, core = _shell_counts(norm)
    if vertical:
        vr = _vertical_regions(norm, sample_height_ft, cut_off_ft)
        vrs = vr["structure"]
        keys = _seg_ref_face_keys(norm)
    else:
        vrs = None
        keys = []
    cs = _owned("CompoundStructure",
                m_oVertRegStructure=vrs,
                m_layers=layers,
                m_coarseScaleFillPatternElemId=int(fill_pattern_id),
                m_coarseScaleFillColor=0,
                m_endCap=int(end_cap),
                m_openingWrapping=int(opening_wrapping),
                m_numShellLayersExt=ext,
                m_numShellLayersInt=inte,
                m_variableLayerIdx=INVALID,
                m_structuralMaterialLayerIndex=core,
                m_segRefFaceKeys=keys,
                m_segRefFaceKeysPre40=[])
    return cs, layers


def _wall_geom_steps() -> dict:
    """The wall type's GeomStepList regen machinery (constant across every
    Revit wall type: one VertCompoundStructureGStep, weak self-refs = 2)."""
    step = blank_object("VertCompoundStructureGStep")
    step.update({
        "m_faceHistTable": [], "m_curveHistTableSet": [], "m_edgeHistTable": [],
        "m_edgeHistTableReverse": [], "m_id": 1, "m_version": 0, "m_flags": 13,
        "m_pElem": {"weakref": 2}, "m_oExtraDatas": None,
        "m_minimumWallHeight": 0.0})
    gsl = blank_object("GeomStepList")
    gsl.update({
        "m_nonBRepGList": [],
        "m_bRepFormGList": [_ptr("VertCompoundStructureGStep", step)],
        "m_bRepAdjustGList": [], "m_bRepCutOutGList": [],
        "m_bRepPostCutOutGList": [], "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": {"weakref": 2},
        "m_latestGStepTypeInPrevRegenCycle": [2, 2, 2, 2, 2],
        "m_idCounter": 2, "m_flags": 9})
    return _ptr("GeomStepList", gsl)


def _empty_type_rep(elem_id: int) -> dict:
    """The seq-103 GElement a wall type carries: an EMPTY cached-geometry
    node (empty face/edge lists, empty (+-1e30) bounding boxes).  Formulaic --
    verified identical shape on all 10 rme wall types."""
    geo = blank_object("Geometry")
    geo.update({
        "m_GInfo": {"m_categoryId": INVALID, "m_tag": INVALID,
                    "m_controlCommand": 0, "m_flags": 557060},
        "m_pFaces": [], "m_flags": 7, "m_geometryTag": INVALID,
        "m_tessEpsCntrl": {"m_type": 0, "m_TessEpsCntrlVersion": 1},
        "m_pEdges": [], "m_sharedSurfInfo": []})
    rep = blank_object("GElement")
    rep.update({
        "m_GInfo": {"m_categoryId": INVALID, "m_tag": int(elem_id),
                    "m_controlCommand": 0, "m_flags": 557060},
        "m_subNodes": [_ptr("Geometry", geo, pid=3)],
        "m_bBox": [[1e+30, 1e+30, 1e+30], [-1e+30, -1e+30, -1e+30]],
        "m_tightbBox": [[1e+30, 1e+30, 1e+30], [-1e+30, -1e+30, -1e+30]],
        "m_elementId": int(elem_id), "m_gElemType": 3, "m_flags": 0})
    return rep


def new_wall_type(name: str, layers, *, ids: IdArg = None, elem_id: int = None,
                  family_name: Optional[str] = "Basic Wall", function: int = 1,
                  sample_height_mm: float = 6096.0,
                  cut_off_height_mm: Optional[float] = None,
                  fill_pattern_id: int = INVALID,
                  wrap_at_inserts: int = 0, wrap_at_ends: int = 0,
                  default_height_constraint: int = 1,
                  preview_id: int = INVALID,
                  with_geometry_rep: bool = True) -> TypeRecord:
    """A ``BasicWallType`` (Basic Wall system-family type) from a layer list.

    ``layers`` = [(function, thickness_mm, material_id), ...] exterior side
    first; ``function`` in {'structure','substrate','thermal','finish1',
    'finish2','membrane'} or the raw code.  ``material_id`` may be -1 (no
    material) or the id of a :func:`new_material` in the same document.
    ``family_name`` is the system-family grouping name shown by the type
    selector (parameter -1010105; None = no such param, as US-template wall
    types).  ``function`` 0 interior / 1 exterior / 2 foundation / 3
    retaining / 4 soffit / 5 core-shaft.  ``cut_off_height_mm`` = the
    preview cut plane (default = the sample height).

    DEFINITION fields written: m_symbolInfo.m_name, m_pCompoundStructure
    (layers, vertical-region grid, shell counts, structural index, ref-face
    keys, coarse fill), m_function, family-name param.  Everything else is
    Revit machinery reproduced at its documented default (geomSteps regen
    node, taper cells, panel/mullion ids -1, height constraint).
    """
    eid = _alloc(ids, elem_id)
    norm = _norm_layers(layers)
    obj = blank_object("BasicWallType")
    element_defaults(obj, eid, double_params={},
                     astring_params=(None if family_name is None
                                     else {-1010105: str(family_name)}))
    symbol_defaults(obj, name, preview_id=preview_id)
    obj["m_geomSteps"] = _wall_geom_steps()
    obj["m_cellList"] = _analytical_cell_list(with_pattern_helper=True, taperable=True)
    cs, _lay = _compound_structure(norm, vertical=True,
                                   sample_height_ft=mm(sample_height_mm),
                                   cut_off_ft=(None if cut_off_height_mm is None
                                               else mm(cut_off_height_mm)),
                                   fill_pattern_id=fill_pattern_id,
                                   end_cap=int(wrap_at_ends),
                                   opening_wrapping=int(wrap_at_inserts))
    obj["m_pCompoundStructure"] = cs
    obj["m_panel"] = INVALID
    obj["m_intMullions"] = [INVALID, INVALID]
    obj["m_bordMullions"] = [[INVALID, INVALID], [INVALID, INVALID]]
    obj["m_autoJoinCond"] = 0
    obj["m_structHiddenViewDisplayType"] = 0
    obj["m_defHeightConstraint"] = int(default_height_constraint)
    obj["m_function"] = int(function)
    obj["m_fixed"] = False
    obj["m_allowAutoEmbed"] = False
    obj["m_oULineSpec"] = None
    obj["m_oVLineSpec"] = None
    mats = [m for _c, _w, m in norm if m not in (None, INVALID)]
    dele = mats + ([fill_pattern_id] if fill_pattern_id not in (None, INVALID) else []) \
        + ([preview_id] if preview_id not in (None, INVALID) else [])
    rep = _empty_type_rep(eid) if with_geometry_rep else None
    thickness = sum(w for _c, w, _m in norm)
    return _record("wall_type", "BasicWallType", OST_Walls, eid, obj,
                   deletion_ids=dele, rep=rep,
                   refs={"materials": mats, "fill_pattern": fill_pattern_id,
                         "preview": preview_id},
                   notes=[f"{len(norm)} layers, total {thickness * MM_PER_FT:.1f} mm; "
                          "seq103 = empty GElement geometry cache (all 10 rme "
                          "wall types carry one; floors/roofs carry SerializedDummy)",
                          "m_previewElemId -1 (no LegendComponent type preview) "
                          "[open: probe whether the reader requires one]"])


def _flat_host_type(class_name: str, kind: str, category: int, name: str,
                    layers, *, ids, elem_id, fill_pattern_id, preview_id,
                    double_params, int_params, extra: dict,
                    end_cap: int = 3) -> TypeRecord:
    """Shared body of the FLAT host types (floor / roof / ceiling): a
    CompoundStructure with NO vertical-region grid (m_oVertRegStructure null)."""
    eid = _alloc(ids, elem_id)
    norm = _norm_layers(layers)
    obj = blank_object(class_name)
    element_defaults(obj, eid, double_params=double_params, int_params=int_params)
    symbol_defaults(obj, name, preview_id=preview_id)
    obj["m_cellList"] = _analytical_cell_list()
    cs, _lay = _compound_structure(norm, vertical=False,
                                   fill_pattern_id=fill_pattern_id, end_cap=end_cap)
    obj["m_pCompoundStructure"] = cs
    obj.update(extra)
    mats = [m for _c, _w, m in norm if m not in (None, INVALID)]
    dele = mats + ([fill_pattern_id] if fill_pattern_id not in (None, INVALID) else []) \
        + ([preview_id] if preview_id not in (None, INVALID) else [])
    return _record(kind, class_name, category, eid, obj, deletion_ids=dele,
                   refs={"materials": mats, "fill_pattern": fill_pattern_id,
                         "preview": preview_id})


def new_floor_type(name: str, layers, *, ids: IdArg = None, elem_id: int = None,
                   fill_pattern_id: int = INVALID, preview_id: int = INVALID,
                   is_foundation_slab: bool = False) -> TypeRecord:
    """A ``FloorAttributes`` (Floor system-family type).

    ``layers`` as for :func:`new_wall_type` (top layer first).  Definition:
    m_symbolInfo.m_name, m_pCompoundStructure (flat layer list, structural
    index, end cap 3), FLOOR_ATTR default (-1001006 = 0 => not structural),
    m_footingType (0 architectural floor / 2 foundation slab).
    """
    return _flat_host_type(
        "FloorAttributes", "floor_type", OST_Floors, name, layers,
        ids=ids, elem_id=elem_id, fill_pattern_id=fill_pattern_id,
        preview_id=preview_id, double_params={},
        int_params={-1001006: 0},
        extra={"m_footingType": 2 if is_foundation_slab else 0,
               "m_structHiddenViewDisplayType": 0})


def new_roof_type(name: str, layers, *, ids: IdArg = None, elem_id: int = None,
                  fill_pattern_id: int = INVALID,
                  preview_id: int = INVALID) -> TypeRecord:
    """A ``RoofAttributes`` (Basic Roof system-family type): flat layer list."""
    return _flat_host_type(
        "RoofAttributes", "roof_type", OST_Roofs, name, layers,
        ids=ids, elem_id=elem_id, fill_pattern_id=fill_pattern_id,
        preview_id=preview_id, double_params={}, int_params={}, extra={})


def new_ceiling_type(name: str, layers, *, ids: IdArg = None, elem_id: int = None,
                     fill_pattern_id: int = INVALID, preview_id: int = INVALID,
                     grid_pattern: int = 0, system_name: str = "") -> TypeRecord:
    """A ``CompoundCeilingType`` (Compound Ceiling type): flat layer list +
    ceiling-grid pattern index (0 = none) and grid scale params
    (-1002203 / -1002202 = 1.0, the ceiling-grid spacing multipliers)."""
    return _flat_host_type(
        "CompoundCeilingType", "ceiling_type", OST_Ceilings, name, layers,
        ids=ids, elem_id=elem_id, fill_pattern_id=fill_pattern_id,
        preview_id=preview_id,
        double_params={-1002203: 1.0, -1002202: 1.0}, int_params=None,
        extra={"m_CeilingGridPattern": int(grid_pattern), "m_isThick": True,
               "m_system": str(system_name)})


# ---------------------------------------------------------------------------
# MATERIAL
# ---------------------------------------------------------------------------

def new_material(name: str, color=(120, 120, 120), *, ids: IdArg = None,
                 elem_id: int = None, material_class: str = "Unassigned",
                 category: str = "Unassigned", transparency: float = 0.0,
                 shininess: int = 64, smoothness: float = 0.5,
                 surface_pattern_id: int = INVALID,
                 cut_pattern_id: int = INVALID,
                 keywords: str = "") -> TypeRecord:
    """A graphics-only ``MaterialElem`` (no appearance/render asset).

    ``color`` = (r, g, b) 0-255 (or a COLORREF int).  Definition = the inline
    ``Material``: name, class/category strings, m_color, shininess,
    smoothness, transparency, surface/cut pattern ids (-1 = none).  No
    appearance asset (m_appearanceAssetId -1, empty asset containers) --
    Revit renders such a material in its shaded color, which is all a
    system-family type needs.
    """
    eid = _alloc(ids, elem_id)
    obj = blank_object("MaterialElem")
    element_defaults(obj, eid)
    col = color if isinstance(color, int) else rgb(color)
    mat = blank_object("Material")
    mat.update({
        "m_name": str(name),
        "m_oStructuralPropertySet": None, "m_oStructuralPropertySetNew": None,
        "m_appearanceAssetId": INVALID, "m_structuralPropertySetId": INVALID,
        "m_cutPatternId": int(cut_pattern_id), "m_cutBackgroundPatternId": INVALID,
        "m_surfacePatternId": int(surface_pattern_id),
        "m_surfaceBackgroundPatternId": INVALID,
        "m_transparency": float(transparency), "m_smoothness": float(smoothness),
        "m_cutPatternColor": 0, "m_cutBackgroundPatternColor": 0,
        "m_surfacePatternColor": 0, "m_surfaceBackgroundPatternColor": 0,
        "m_color": int(col), "m_shininess": int(shininess), "m_glow": False,
        "m_bUseRenderAppearance": False, "m_accuRenderLib": "",
        "m_accuRenderName": "", "m_keywords": str(keywords),
        "m_sMaterialClass": str(material_class), "m_sCategory": str(category),
    })
    # generic appearance-asset binding descriptor (schema identifiers every
    # material carries), but NO owned appearance asset => rendered by m_color
    mat["m_asset"]["m_sName"] = "Generic"
    mat["m_asset"]["m_sLibrary"] = "assetlibrary_base.fbx"
    mat["m_asset"]["m_eAssetType"] = 4
    obj["m_pMaterial"] = _ptr("Material", mat)
    obj["m_pThumbnail"] = None
    obj["m_materialPathMap"] = []
    pats = [p for p in (surface_pattern_id, cut_pattern_id) if p not in (None, INVALID)]
    return _record("material", "MaterialElem", OST_Materials, eid, obj,
                   deletion_ids=pats, refs={"patterns": pats},
                   notes=["graphics-only material: no appearance asset "
                          "(m_appearanceAssetId -1); shaded by m_color"])


# ---------------------------------------------------------------------------
# LINE / FILL PATTERNS
# ---------------------------------------------------------------------------

_SEG_KIND = {"dash": 0, "space": 1, "dot": 2}


def new_line_pattern(name: str, segments_mm, *, ids: IdArg = None,
                     elem_id: int = None) -> TypeRecord:
    """A ``LinePatternElem`` from a dash/space/dot list.

    ``segments_mm`` = [("dash", 3.175), ("space", 3.175), ("dot", 0), ...].
    Definition = LinePattern{m_name, m_segs[{m_data (ft), m_type
    0 dash / 1 space / 2 dot}], m_pixelPattern 0}.
    """
    eid = _alloc(ids, elem_id)
    segs = []
    for s in segments_mm:
        if isinstance(s, dict):
            k, ln = s.get("kind", "dash"), s.get("length_mm", 0.0)
        else:
            k, ln = s[0], (s[1] if len(s) > 1 else 0.0)
        code = _SEG_KIND[k] if isinstance(k, str) else int(k)
        segs.append({"m_data": mm(ln), "m_type": code})
    if not segs:
        raise ValueError("a line pattern needs at least one segment")
    obj = blank_object("LinePatternElem")
    element_defaults(obj, eid)
    obj["m_pLinePattern"] = _owned("LinePattern", m_name=str(name), m_segs=segs,
                                    m_pixelPattern=0)
    obj["m_ownerId"] = INVALID
    return _record("line_pattern", "LinePatternElem", INVALID, eid, obj)


def new_fill_pattern(name: str, grids, *, ids: IdArg = None, elem_id: int = None,
                     target: str = "drafting", orientation: int = 0,
                     scale: float = 1.0, window_size_mm: float = 2.5) -> TypeRecord:
    """A ``FillPatternElem`` from a list of parallel-line grids.

    ``grids`` = [{"angle_deg": 45, "offset_mm": 0, "spacing_mm": 3,
    "origin_mm": (0, 0), "dashes_mm": []}, ...] (an empty ``grids`` list =
    a SOLID fill, as Revit's 'Solid fill' has zero grids).  ``target``
    'drafting' (symbolic, sheet-scaled) or 'model' (real-world size).
    """
    eid = _alloc(ids, elem_id)
    grid_recs = []
    for g in grids:
        grid_recs.append(_owned(
            "FillGrid",
            m_angle=math.radians(float(g.get("angle_deg", 0.0))),
            m_origin=[mm(v) for v in g.get("origin_mm", (0.0, 0.0))],
            m_deltas=[mm(g.get("offset_mm", 0.0)), mm(g.get("spacing_mm", 3.0))],
            m_segs=[mm(v) for v in g.get("dashes_mm", [])],
        ))
    obj = blank_object("FillPatternElem")
    element_defaults(obj, eid)
    gt = blank_object("GeomTable")
    gt.update({"m_refPntMirrored": False, "m_table": [], "m_bigTableOwner": None,
               "m_materialMarkers": [], "m_faceTypeMarkers": []})
    obj["m_pGeomTable"] = _ptr("GeomTable", gt)
    obj["m_pFillPattern"] = _owned(
        "FillPattern", m_gridsArr=grid_recs, m_name=str(name),
        m_scale=float(scale), m_windowSize=mm(window_size_mm),
        m_fpOrientation=int(orientation),
        m_fpTarget=1 if str(target).lower().startswith("model") else 0)
    obj["m_ownerId"] = INVALID
    return _record("fill_pattern", "FillPatternElem", INVALID, eid, obj,
                   notes=([] if grid_recs else ["zero grids = SOLID fill"]))


# ---------------------------------------------------------------------------
# VOLTAGE / DISTRIBUTION SYSTEM  (electrical definitions)
# ---------------------------------------------------------------------------

def new_voltage_type(name: str, volts_nominal: float, *, ids: IdArg = None,
                     elem_id: int = None, min_volts: float = None,
                     max_volts: float = None) -> TypeRecord:
    """An ``RbsVoltageType`` (Electrical Settings > Voltage Definitions row).

    Definition = m_symbolInfo.m_name + m_dActualVoltage / m_dMinVoltage /
    m_dMaxVoltage (internal units, converted from volts).  Min/max default
    to the published service range for the nominal (240 V -> 220..250 V),
    else +-5 %.
    """
    eid = _alloc(ids, elem_id)
    v = float(volts_nominal)
    lo, hi = NOMINAL_VOLTAGE_RANGES.get(int(round(v)), (v * 0.95, v * 1.05))
    lo = float(min_volts) if min_volts is not None else lo
    hi = float(max_volts) if max_volts is not None else hi
    obj = blank_object("RbsVoltageType")
    element_defaults(obj, eid)
    symbol_defaults(obj, name)
    obj["m_dActualVoltage"] = volts(v)
    obj["m_dMaxVoltage"] = volts(hi)
    obj["m_dMinVoltage"] = volts(lo)
    return _record("voltage_type", "RbsVoltageType", OST_ElectricalVoltage, eid, obj,
                   refs={"volts": v, "range": [lo, hi]})


def new_distribution_system(name: str, *, phase: str = "three",
                            config: str = "wye", wires: int = 4,
                            voltage_ll_id: int = INVALID,
                            voltage_lg_id: int = INVALID,
                            ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """An ``RbsDistributionSysType`` (Electrical Settings > Distribution
    Systems row): phase (single/three), configuration (wye/delta), number of
    wires, and the line-to-line / line-to-ground voltage type ids
    (:func:`new_voltage_type`).

    Encodings (verified rme): m_kPhase 0 single / 1 three; m_kConfig 0
    (delta / none) / 1 wye; m_iNumWires; m_idVll / m_idVlg -> voltage
    types; m_highLegPhase -1 (no high leg).
    """
    eid = _alloc(ids, elem_id)
    ph = str(phase).lower()
    kphase = 0 if ph.startswith("single") or ph == "1" else 1
    cf = str(config).lower()
    kconfig = 1 if cf.startswith("wye") or cf in ("y", "star") else 0
    obj = blank_object("RbsDistributionSysType")
    element_defaults(obj, eid, astring_params={})
    symbol_defaults(obj, name)
    obj["m_idVll"] = int(voltage_ll_id)
    obj["m_idVlg"] = int(voltage_lg_id)
    obj["m_kPhase"] = kphase
    obj["m_kConfig"] = kconfig
    obj["m_highLegPhase"] = INVALID
    obj["m_iNumWires"] = int(wires)
    vids = [i for i in (voltage_ll_id, voltage_lg_id) if i not in (None, INVALID)]
    return _record("distribution_system", "RbsDistributionSysType",
                   OST_ElectricalDistributionSys, eid, obj,
                   deletion_ids=vids, refs={"voltage_types": vids},
                   notes=(["voltage type ids not supplied (-1): a real "
                           "distribution system references its L-L / L-G "
                           "voltage definitions"] if not vids else []))


# ---------------------------------------------------------------------------
# CONDUIT: standard + sizes table + type
# ---------------------------------------------------------------------------

def new_conduit_standard(name: str, *, ids: IdArg = None,
                         elem_id: int = None) -> TypeRecord:
    """A ``ConduitStandardType`` -- a named conduit STANDARD (EMT, IMC, RMC,
    'RNC Schedule 40', ...).  The definition is just the name; the sizes live
    in the document's :func:`conduit_sizes_element` keyed by this id."""
    eid = _alloc(ids, elem_id)
    obj = blank_object("ConduitStandardType")
    element_defaults(obj, eid, astring_params={})
    symbol_defaults(obj, name)
    return _record("conduit_standard", "ConduitStandardType", OST_ConduitStandards,
                   eid, obj)


def conduit_sizes_element(sizes_by_standard: dict, *, ids: IdArg = None,
                          elem_id: int = None) -> TypeRecord:
    """The document's single ``ConduitSizesElem``: for each conduit standard
    id, the size table.

    ``sizes_by_standard`` = {standard_id: [ {nominal_in, inner_in, outer_in,
    bend_radius_in} or (nominal, inner, outer, bend), ...]} in INCHES (trade
    size, inner diameter, outer diameter, minimum bend radius) -- e.g. EMT
    1/2": (0.5, 0.622, 0.706, 4.35).  These are published ANSI/NEC dimensions
    (facts), not authored content.
    """
    eid = _alloc(ids, elem_id)
    obj = blank_object("ConduitSizesElem")
    element_defaults(obj, eid)
    pairs = []
    for std_id, rows in sizes_by_standard.items():
        data = []
        for r in rows:
            if isinstance(r, dict):
                nom, idn, od, bend = (r["nominal_in"], r.get("inner_in", 0.0),
                                     r.get("outer_in", 0.0), r.get("bend_radius_in", 0.0))
                in_list = r.get("in_size_list", True)
                sizing = r.get("used_by_sizing", True)
            else:
                nom, idn, od, bend = (list(r) + [0.0, 0.0, 0.0])[:4]
                in_list = sizing = True
            data.append({"m_dSize": inches(nom), "m_dInnerDiameter": inches(idn),
                         "m_dOuterDiameter": inches(od), "m_dBendRadius": inches(bend),
                         "m_bInSizeList": bool(in_list),
                         "m_bUsedBySizing": bool(sizing)})
        pairs.append({"first": int(std_id), "second": {"m_sizeData": data}})
    obj["m_sizes"] = pairs
    stds = [int(k) for k in sizes_by_standard]
    return _record("conduit_sizes", "ConduitSizesElem", INVALID, eid, obj,
                   deletion_ids=stds, refs={"standards": stds},
                   notes=["singleton: one ConduitSizesElem per document"])


def _sweep_profile(shape: str = "circular") -> dict:
    """The routing-profile object a curve type carries (circular conduit /
    U-shape or ladder cable tray)."""
    if shape == "circular":
        return _ptr("AbsSysCircSweepProfile", blank_object("AbsSysCircSweepProfile"))
    cls = {"ladder": "LadderSweepProfile"}.get(shape, "UShapeSweepProfile")
    return _ptr(cls, blank_object(cls))


def new_conduit_type(name: str, *, standard_id: int = INVALID,
                     with_fitting: bool = False,
                     fittings: Optional[dict] = None,
                     roughness_ft: float = 0.0003,
                     max_size_in: float = 96.0,
                     ids: IdArg = None, elem_id: int = None,
                     preview_id: int = INVALID) -> TypeRecord:
    """An ``RbsConduitType`` (a routable conduit type).

    Definition = name, m_idStandardType (-> :func:`new_conduit_standard`),
    m_bWithFitting (with-fitting vs. without-fitting family of types),
    default FITTING symbol ids (elbow/tee/cross/transition/union -- ids of
    loadable fitting-family symbols; -1 until such families are OWNED
    content), roughness, max width/height, circular sweep profile.

    ``fittings`` = {'elbow':id,'tee':id,'cross':id,'transition':id,
    'union':id,...} (keys match the m_idDefault* fields).
    """
    eid = _alloc(ids, elem_id)
    fittings = fittings or {}
    obj = blank_object("RbsConduitType")
    element_defaults(obj, eid)
    symbol_defaults(obj, name, preview_id=preview_id)
    obj["m_pCompoundStructure"] = None
    obj["m_dMaxWidth"] = inches(max_size_in)
    obj["m_dMaxHeight"] = inches(max_size_in)
    obj["m_dRoughness"] = float(roughness_ft)
    obj["m_Profile"] = _sweep_profile("circular")
    obj["m_eRiseDropType"] = 0
    fmap = {"cross": "m_idDefaultCross", "elbow": "m_idDefaultElbow",
            "elbow_down": "m_idDefaultElbowDown", "elbow_up": "m_idDefaultElbowUp",
            "multi_shape": "m_idDefaultMultiShape",
            "oval_to_round": "m_idDefaultMultiShapeOvalToRound",
            "rect_to_oval": "m_idDefaultMultiShapeRectToOval",
            "takeoff": "m_idDefaultTakeoff", "tee": "m_idDefaultTee",
            "tee_down": "m_idDefaultTeeDown", "tee_up": "m_idDefaultTeeUp",
            "transition": "m_idDefaultTransition", "union": "m_idDefaultUnion",
            "mech_joint": "m_idMechJoint"}
    used = []
    for key, fld in fmap.items():
        v = fittings.get(key, INVALID)
        obj[fld] = int(v) if v is not None else INVALID
        if obj[fld] != INVALID:
            used.append(obj[fld])
    obj["m_bWithFitting"] = bool(with_fitting)
    obj["m_bBranchTypeTee"] = True
    obj["m_idStandardType"] = int(standard_id)
    dele = list(used)
    if standard_id not in (None, INVALID):
        dele.append(int(standard_id))
    if preview_id not in (None, INVALID):
        dele.append(int(preview_id))
    return _record("conduit_type", "RbsConduitType", OST_Conduit, eid, obj,
                   deletion_ids=dele,
                   refs={"standard": standard_id, "fittings": used,
                         "preview": preview_id},
                   notes=(["default fitting symbols -1: fitting families are "
                           "loadable content, authored separately"] if not used else []))


# ---------------------------------------------------------------------------
# CABLE TRAY
# ---------------------------------------------------------------------------

def cable_tray_sizes_element(sizes_in: Sequence[float], *, ids: IdArg = None,
                             elem_id: int = None) -> TypeRecord:
    """The document's single ``CableTraySizesElem``: the tray size list
    (nominal widths, inches).  Inner/outer diameters are 0 for trays."""
    eid = _alloc(ids, elem_id)
    obj = blank_object("CableTraySizesElem")
    element_defaults(obj, eid)
    obj["m_sizes"] = {"m_sizeData": [
        {"m_dSize": inches(s), "m_dInnerDiameter": 0.0, "m_dOuterDiameter": 0.0,
         "m_bInSizeList": True, "m_bUsedBySizing": True} for s in sizes_in]}
    return _record("cable_tray_sizes", "CableTraySizesElem", INVALID, eid, obj,
                   notes=["singleton: one CableTraySizesElem per document"])


def new_cable_tray_type(name: str, *, shape: str = "ushape",
                        with_fitting: bool = True,
                        fittings: Optional[dict] = None,
                        min_bend_multiplier: float = 1.0,
                        roughness_ft: float = 0.0003,
                        max_size_in: float = 96.0,
                        ids: IdArg = None, elem_id: int = None,
                        preview_id: int = INVALID) -> TypeRecord:
    """An ``RbsCableTrayType`` (channel/ladder/solid/wire-mesh tray type).

    ``shape`` 'ushape' (channel / solid bottom / trough) or 'ladder' picks
    the sweep profile and m_eCableTrayType (verified: ladder tray = 2, the
    others 1).  Fittings (elbow, elbow_up, elbow_down, tee, cross,
    transition, union) reference loadable fitting-family symbols; -1 until
    those are owned content.
    """
    eid = _alloc(ids, elem_id)
    fittings = fittings or {}
    is_ladder = str(shape).lower().startswith("ladder")
    obj = blank_object("RbsCableTrayType")
    element_defaults(obj, eid)
    symbol_defaults(obj, name, preview_id=preview_id)
    obj["m_pCompoundStructure"] = None
    obj["m_dMaxWidth"] = inches(max_size_in)
    obj["m_dMaxHeight"] = inches(max_size_in)
    obj["m_dRoughness"] = float(roughness_ft)
    obj["m_Profile"] = _sweep_profile("ladder" if is_ladder else "ushape")
    obj["m_eRiseDropType"] = 0
    fmap = {"cross": "m_idDefaultCross", "elbow": "m_idDefaultElbow",
            "elbow_down": "m_idDefaultElbowDown", "elbow_up": "m_idDefaultElbowUp",
            "multi_shape": "m_idDefaultMultiShape",
            "oval_to_round": "m_idDefaultMultiShapeOvalToRound",
            "rect_to_oval": "m_idDefaultMultiShapeRectToOval",
            "takeoff": "m_idDefaultTakeoff", "tee": "m_idDefaultTee",
            "tee_down": "m_idDefaultTeeDown", "tee_up": "m_idDefaultTeeUp",
            "transition": "m_idDefaultTransition", "union": "m_idDefaultUnion",
            "mech_joint": "m_idMechJoint"}
    used = []
    for key, fld in fmap.items():
        v = fittings.get(key, INVALID)
        obj[fld] = int(v) if v is not None else INVALID
        if obj[fld] != INVALID:
            used.append(obj[fld])
    obj["m_bWithFitting"] = bool(with_fitting)
    obj["m_bBranchTypeTee"] = True
    obj["m_eCableTrayType"] = 2 if is_ladder else 1
    obj["m_dMinBendMultiplier"] = float(min_bend_multiplier)
    dele = list(used) + ([preview_id] if preview_id not in (None, INVALID) else [])
    return _record("cable_tray_type", "RbsCableTrayType", OST_CableTray, eid, obj,
                   deletion_ids=dele,
                   refs={"fittings": used, "preview": preview_id, "shape": shape})


# ---------------------------------------------------------------------------
# WIRE: symbol types + conductor definition cells + wire type
# ---------------------------------------------------------------------------

def _named_symbol_type(class_name: str, kind: str, category: int, name: str, *,
                       ids: IdArg, elem_id: Optional[int],
                       astring_params=None) -> TypeRecord:
    """Body of the pure-name symbol types (wire material / insulation /
    temperature rating): definition = the symbol name only."""
    eid = _alloc(ids, elem_id)
    obj = blank_object(class_name)
    element_defaults(obj, eid, astring_params=astring_params)
    symbol_defaults(obj, name)
    return _record(kind, class_name, category, eid, obj)


def new_wire_material_type(name: str, *, ids: IdArg = None,
                           elem_id: int = None) -> TypeRecord:
    """``RbsWireMaterialType`` (Copper / Aluminium ...): the wire-sizes
    table's material key.  Definition = the name."""
    return _named_symbol_type("RbsWireMaterialType", "wire_material_type",
                              OST_WireMaterial, name, ids=ids, elem_id=elem_id,
                              astring_params={})


def new_wire_insulation_type(name: str, *, ids: IdArg = None,
                             elem_id: int = None) -> TypeRecord:
    """``RbsWireInsulationType`` (THWN / XHHW ...).  Definition = the name."""
    return _named_symbol_type("RbsWireInsulationType", "wire_insulation_type",
                              OST_WireInsulation, name, ids=ids, elem_id=elem_id,
                              astring_params={})


def new_wire_temperature_rating_type(name: str, *, ids: IdArg = None,
                                     elem_id: int = None) -> TypeRecord:
    """``RbsWireTemperatureRatingType`` ('60' / '75' / '90' [deg C]).
    Definition = the name (the rating value as text)."""
    return _named_symbol_type("RbsWireTemperatureRatingType",
                              "wire_temperature_rating_type",
                              OST_WireTemperatureRating, name, ids=ids,
                              elem_id=elem_id, astring_params={})


def _custom_cell_element(cell_class: str, cell_overlay: dict, name: str,
                         kind: str, *, ids: IdArg, elem_id: Optional[int]) -> TypeRecord:
    """A ``CustomElement`` = the generic 'named definition cell' element
    Revit uses for the conductor catalog: CellList{ <cell_class>{...},
    NamingCell{name} }.  A wire type points at four of these (material,
    temperature rating, insulation, max conductor size)."""
    eid = _alloc(ids, elem_id)
    obj = blank_object("CustomElement")
    element_defaults(obj, eid)
    cell = blank_object(cell_class)
    cell.update(cell_overlay)
    obj["m_cellList"] = _ptr("CellList", {"m_cells": [
        _ptr(cell_class, cell), _owned("NamingCell", m_name=str(name))]})
    return _record(kind, "CustomElement", INVALID, eid, obj,
                   refs={"cell": cell_class, "name": name})


def new_conductor_material(name: str = "Copper", *, ids: IdArg = None,
                           elem_id: int = None) -> TypeRecord:
    """Conductor MATERIAL definition cell (RbsConductorMaterial 'Copper')."""
    return _custom_cell_element("RbsConductorMaterial", {}, name,
                                "conductor_material", ids=ids, elem_id=elem_id)


def new_conductor_temperature_rating(name: str = "60", *, ids: IdArg = None,
                                     elem_id: int = None) -> TypeRecord:
    """Conductor TEMPERATURE-RATING cell (RbsConductorTemperatureRating '60')."""
    return _custom_cell_element("RbsConductorTemperatureRating", {}, name,
                                "conductor_temperature", ids=ids, elem_id=elem_id)


def new_conductor_insulation(name: str = "THWN", *, ids: IdArg = None,
                             elem_id: int = None) -> TypeRecord:
    """Conductor INSULATION cell (RbsConductorInsulationMaterial 'THWN')."""
    return _custom_cell_element("RbsConductorInsulationMaterial", {}, name,
                                "conductor_insulation", ids=ids, elem_id=elem_id)


def new_conductor_size(name: str, diameter_mm: float, *, ids: IdArg = None,
                       elem_id: int = None) -> TypeRecord:
    """Conductor SIZE cell (RbsConductorSize{m_diameter} + name), e.g.
    name '12' (AWG) with its bare-conductor diameter in mm."""
    return _custom_cell_element("RbsConductorSize", {"m_diameter": mm(diameter_mm)},
                                name, "conductor_size", ids=ids, elem_id=elem_id)


def new_wire_type(name: str, *, material_id: int = INVALID,
                  temperature_rating_id: int = INVALID,
                  insulation_id: int = INVALID,
                  max_size_id: int = INVALID,
                  neutral_multiplier: float = 1.0,
                  neutral_mode: int = 0,
                  neutral_included_in_balanced_load: bool = True,
                  share_neutral: bool = True, share_ground: bool = True,
                  conduit_type: str = "Non-Magnetic",
                  ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """An ``RbsWireType`` (a wire type: material / temperature rating /
    insulation / max size / neutral & ground policy).

    The four reference ids point at conductor definition cells
    (:func:`new_conductor_material`, :func:`new_conductor_temperature_rating`,
    :func:`new_conductor_insulation`, :func:`new_conductor_size`).
    ``conduit_type`` = the raceway magnetism string ('Non-Magnetic' /
    'Magnetic'), part of the definition (it selects impedance behaviour).
    """
    eid = _alloc(ids, elem_id)
    obj = blank_object("RbsWireType")
    element_defaults(obj, eid)
    symbol_defaults(obj, name)
    obj["m_strConduitType"] = str(conduit_type)
    obj["m_dNeutralMultiplier"] = float(neutral_multiplier)
    obj["m_idMaterial"] = int(material_id)
    obj["m_idTempratureRating"] = int(temperature_rating_id)   # (sic: schema spelling)
    obj["m_idInsulation"] = int(insulation_id)
    obj["m_idMaxConductorSize"] = int(max_size_id)
    obj["m_eNeutralMode"] = int(neutral_mode)
    obj["m_bNeutralIncludedInBalancedLoad"] = bool(neutral_included_in_balanced_load)
    obj["m_bShareNeutral"] = bool(share_neutral)
    obj["m_bShareGround"] = bool(share_ground)
    refids = [i for i in (material_id, temperature_rating_id, insulation_id, max_size_id)
              if i not in (None, INVALID)]
    return _record("wire_type", "RbsWireType", OST_Wire, eid, obj,
                   deletion_ids=refids,
                   refs={"material": material_id, "temperature": temperature_rating_id,
                         "insulation": insulation_id, "max_size": max_size_id},
                   notes=(["conductor cell ids not supplied (-1): a complete "
                           "wire type points at its 4 conductor definition cells"]
                          if len(refids) < 4 else []))


# ---------------------------------------------------------------------------
# LOAD CLASSIFICATION + DEMAND FACTOR
# ---------------------------------------------------------------------------

def new_demand_factor(name: str, factor: float = 1.0, *, ids: IdArg = None,
                      elem_id: int = None, rule: str = "constant",
                      rows: Optional[Sequence] = None,
                      additional_load: float = 0.0,
                      include_additional_load: bool = False) -> TypeRecord:
    """An ``ElectricalDemandFactorDefinition``.

    ``rule`` 'constant' => one row {min 0, max 1e30, factor}; or pass
    ``rows`` = [(min, max, factor), ...] for a stepped rule (m_ruleType per
    Revit's DemandFactorRule enum: 0 constant, 1 quantity ranges, 2 load
    ranges, 3 percentage ranges).
    """
    eid = _alloc(ids, elem_id)
    rt = {"constant": 0, "quantity": 1, "load": 2, "percentage": 3}
    rule_code = rt[rule] if isinstance(rule, str) else int(rule)
    if rows is None:
        rows = [(0.0, 1e30, float(factor))]
    vals = [{"m_factor": float(f), "m_maxRange": float(mx), "m_minRange": float(mn)}
            for (mn, mx, f) in rows]
    obj = blank_object("ElectricalDemandFactorDefinition")
    element_defaults(obj, eid)
    obj["m_name"] = str(name)
    obj["m_ruleType"] = rule_code
    obj["m_values"] = vals
    obj["m_additionalLoad"] = float(additional_load)
    obj["m_includeAdditionalLoad"] = bool(include_additional_load)
    return _record("demand_factor", "ElectricalDemandFactorDefinition",
                   OST_ElectricalDemandFactor, eid, obj, refs={"rule": rule_code})


def new_load_class(name: str, demand_factor_id: int = INVALID, *,
                   ids: IdArg = None, elem_id: int = None,
                   space_load_class: int = 0,
                   param_elem_ids: Optional[dict] = None) -> TypeRecord:
    """An ``ElectricalLoadClassification`` (Lighting / Receptacle / Motor /
    ...), referencing its demand-factor definition.

    The label templates are Revit's own format strings (verified constant on
    all 10 rme classifications).  The six companion parameter elements
    (m_*ParamElemId: the schedule columns Revit auto-creates per
    classification) are OUT OF SCOPE here -- pass ``param_elem_ids`` when a
    parameter-elements stream provides them, else they stay -1
    [documented gap; genesis-types.md].
    """
    eid = _alloc(ids, elem_id)
    pe = {"actual_space": INVALID, "demand_factor_param": INVALID,
          "est_current": INVALID, "est_load": INVALID,
          "total_current": INVALID, "total_load": INVALID}
    if param_elem_ids:
        pe.update(param_elem_ids)
    obj = blank_object("ElectricalLoadClassification")
    element_defaults(obj, eid)
    obj["m_name"] = str(name)
    obj["m_abbreviation"] = ""
    obj["m_demandFactorId"] = int(demand_factor_id)
    obj["m_actualElectricalLoadLabel"] = "Actual %1!s! Load"
    obj["m_loadSummaryDemandFactorLabel"] = "%1!s! Demand Factor"
    obj["m_panelConnectedCurrentLabel"] = "%1!s! Connected Current"
    obj["m_panelConnectedLabel"] = "%1!s! Connected Apparent Power"
    obj["m_panelEstimatedCurrentLabel"] = "%1!s! Estimated Demand Current"
    obj["m_panelEstimatedLabel"] = "%1!s! Demand Apparent Power"
    obj["m_actualSpaceLoadParamElemId"] = int(pe["actual_space"])
    obj["m_demandFactorParamElemId"] = int(pe["demand_factor_param"])
    obj["m_estCurrentParamElemId"] = int(pe["est_current"])
    obj["m_estLoadParamElemId"] = int(pe["est_load"])
    obj["m_totalCurrentParamElemId"] = int(pe["total_current"])
    obj["m_totalLoadParamElemId"] = int(pe["total_load"])
    obj["m_signitureType"] = 0
    obj["m_spaceLoadClass"] = int(space_load_class)
    dele = ([demand_factor_id] if demand_factor_id not in (None, INVALID) else []) \
        + [v for v in pe.values() if v not in (None, INVALID)]
    return _record("load_classification", "ElectricalLoadClassification",
                   OST_ElectricalLoadClassification, eid, obj, deletion_ids=dele,
                   refs={"demand_factor": demand_factor_id, "param_elems": pe},
                   notes=(["6 companion ParamElemElectricalLoadClassification "
                           "ids left -1 (parameter-elements stream owns them)"]
                          if all(v == INVALID for v in pe.values()) else []))


# ---------------------------------------------------------------------------
# ELECTRICAL SETTING (document singleton)
# ---------------------------------------------------------------------------

def electrical_setting(*, ids: IdArg = None, elem_id: int = None,
                       phase_labels=("A", "B", "C"), circuit_rating: float = 20.0,
                       circuit_path_offset_mm: float = 2750.0,
                       specific_angles_deg=(11.25, 22.5, 30.0, 45.0, 60.0, 90.0),
                       load_calc_method: int = 0,
                       run_load_calcs_in_spaces: bool = True,
                       include_spares_in_totals: bool = True,
                       merge_multi_pole_circuits: bool = False,
                       space_label: str = "Space",
                       spare_label: str = "Spare") -> TypeRecord:
    """The document's single ``ElectricalSetting`` (Electrical Settings >
    General): phase naming, default circuit rating, wiring angle set, panel-
    schedule spare/space labels, load-calculation policy.  m_pADocument is
    the weak back-pointer to the document (archive index 1)."""
    eid = _alloc(ids, elem_id)
    obj = blank_object("ElectricalSetting")
    element_defaults(obj, eid)
    obj["m_pADocument"] = {"weakref": 1}
    obj["m_circuitNamePhaseA"], obj["m_circuitNamePhaseB"], obj["m_circuitNamePhaseC"] = (
        str(phase_labels[0]), str(phase_labels[1]), str(phase_labels[2]))
    obj["m_oldSpaceLabel"] = obj["m_spaceLabel"] = str(space_label)
    obj["m_oldSpareLabel"] = obj["m_spareLabel"] = str(spare_label)
    obj["m_specificAngles"] = [{"first": float(a), "second": True} for a in specific_angles_deg]
    obj["m_angleIncrement"] = math.radians(1.0)
    obj["m_circuitPathOffset"] = mm(circuit_path_offset_mm)
    obj["m_circuitRating"] = float(circuit_rating)
    obj["m_capitalizationForLoadNames"] = 0
    obj["m_circuitLoadCalculationMethod"] = int(load_calc_method)
    obj["m_circuitSequenceValue"] = 0
    obj["m_fittingAngleUsage"] = 0
    obj["m_isIncludeSparesInPanelTotals"] = bool(include_spares_in_totals)
    obj["m_isRunCalculationsForLoadsInSpaces"] = bool(run_load_calcs_in_spaces)
    obj["m_mergeMultiPoledCircuitsIntoSingleCell"] = bool(merge_multi_pole_circuits)
    return _record("electrical_setting", "ElectricalSetting", INVALID, eid, obj,
                   notes=["singleton: one ElectricalSetting per document"])


# ---------------------------------------------------------------------------
# TEXT TYPE (TextNoteAttributes + its owned FontElem + line sub-category)
# ---------------------------------------------------------------------------

def new_category(name: str, parent_category_id: int, owner_id: int = INVALID, *,
                 category_type: int = 4, flags: int = 7,
                 gstyle_ids: Sequence[int] = (), ids: IdArg = None,
                 elem_id: int = None,
                 design_option: int = NO_DESIGN_OPTION) -> TypeRecord:
    """A ``CategoryElem`` = a sub-category (line style / object sub-category).

    ``parent_category_id`` is a built-in OST id (or another category);
    ``owner_id`` the owning type/family (-1 = document); ``gstyle_ids`` the
    GStyleElem records giving it graphics.  categoryType 4 = internal/line-
    style category (as text types' own categories), 1 = model, 2 =
    annotation.  Owned categories list their owner in the deletion set.
    """
    eid = _alloc(ids, elem_id)
    obj = blank_object("CategoryElem")
    element_defaults(obj, eid, design_option=design_option)
    obj["m_ownerId"] = int(owner_id)
    obj["m_pCategory"] = _owned("Category", m_name=str(name),
                                 m_parentCategoryId=int(parent_category_id),
                                 m_categoryType=int(category_type),
                                 m_flags=int(flags))
    obj["m_gstyleIds"] = [int(g) for g in gstyle_ids]
    dele = list(gstyle_ids) + ([owner_id] if owner_id not in (None, INVALID) else [])
    return _record("category", "CategoryElem", INVALID, eid, obj,
                   deletion_ids=dele, design_option=design_option,
                   refs={"parent": parent_category_id, "owner": owner_id,
                         "gstyles": list(gstyle_ids)})


def new_gstyle(category_id: int, *, style_type: str = "projection",
               pen: int = 1, color: int = 0, line_pattern_id: int = LINEPATTERN_SOLID,
               material_id: int = INVALID, owner_id: int = INVALID,
               screen_sized: bool = False, ids: IdArg = None,
               elem_id: int = None,
               design_option: int = NO_DESIGN_OPTION) -> TypeRecord:
    """A ``GStyleElem`` = one graphics style row of a category.

    ``category_id`` = a built-in OST id (=> a document OBJECT STYLE row) or
    a :func:`new_category` id (=> a sub-category style).  ``style_type``
    'projection' (1) or 'cut' (2).  ``pen`` = line-weight 1-16;
    ``line_pattern_id`` -3000010 = solid, a :func:`new_line_pattern` id, or
    -1 = none.  ``color`` = COLORREF (0 = black).
    """
    eid = _alloc(ids, elem_id)
    gt = 2 if str(style_type).lower().startswith("cut") else (
        int(style_type) if isinstance(style_type, int) else 1)
    obj = blank_object("GStyleElem")
    element_defaults(obj, eid, design_option=design_option)
    obj["m_pGStyle"] = _owned("GStyle", m_linePatternId=int(line_pattern_id),
                                m_materialElemId=int(material_id),
                                m_penNumber=int(pen), m_color=int(color),
                                m_isScreenSized=bool(screen_sized))
    obj["m_categoryId"] = int(category_id)
    obj["m_ownerId"] = int(owner_id)
    obj["m_gstyleType"] = gt
    dele = [i for i in (line_pattern_id if line_pattern_id and line_pattern_id > 0 else None,
                        material_id if material_id and material_id > 0 else None) if i]
    builtin_row = isinstance(category_id, int) and category_id < 0
    if isinstance(category_id, int) and category_id > 0:
        dele.append(category_id)
    return _record("gstyle", "GStyleElem", INVALID, eid, obj, deletion_ids=dele,
                   design_option=design_option,
                   hdr_key=("GStyleElem:objectstyle" if builtin_row else None),
                   refs={"category": category_id, "style_type": gt, "pen": pen})


def new_text_type(name: str, *, font: str = "Arial", size_mm: float = 3.2,
                  bold: bool = False, italic: bool = False, underline: bool = False,
                  color: int = 0, background: int = 0,
                  width_factor: float = 1.0, tab_size_mm: float = 12.7,
                  leader_offset_mm: float = 2.032,
                  leader_arrowhead_id: int = INVALID,
                  show_border: bool = False, line_pen: int = 1,
                  ids: IdArg = None, elem_ids: Optional[Sequence[int]] = None,
                  design_option: int = NO_DESIGN_OPTION) -> list:
    """A TEXT TYPE = four linked elements (returned as a list, wired):

      1. ``TextNoteAttributes`` (the type: name, size params, leader
         offset, arrowhead, text-box visibility, LineAndTextAttr -> font +
         its line sub-category)
      2. ``FontElem`` OWNED by the type (font name, size in feet = paper
         height, color)
      3. ``CategoryElem`` OWNED by the type (its private line style: leader
         and box lines; parent = the text-note line-style built-in category)
      4. ``GStyleElem`` of that category (the line style's pen/color)

    ``size_mm`` = paper text height (3.2 mm ~ 1/8").  Parameters written:
    -1006327 (width factor) and -1006326 (tab size); -1006315 = leader
    arrowhead LeaderStyle id (-1 = none, else an existing arrowhead type).
    """
    eids = list(elem_ids) if elem_ids else [_alloc(ids) for _ in range(4)]
    while len(eids) < 4:
        eids.append(_alloc(ids))
    type_id, font_id, cat_id, gs_id = (int(eids[0]), int(eids[1]),
                                       int(eids[2]), int(eids[3]))
    # 2. font (owned by the type)
    fobj = blank_object("FontElem")
    element_defaults(fobj, font_id, design_option=design_option)
    fobj["m_ownerId"] = type_id
    fobj["m_pFont"] = _owned("Font", m_name=str(font), m_size=mm(size_mm),
                              m_color=int(color) if color else 0xFFFFFF)
    font_rec = _record("font", "FontElem", INVALID, font_id, fobj,
                       deletion_ids=[type_id], design_option=design_option,
                       refs={"owner": type_id})
    # 4. the sub-category's line style (leader / box lines: black solid)
    gs_rec = new_gstyle(cat_id, style_type="projection", pen=int(line_pen),
                        color=0, line_pattern_id=LINEPATTERN_SOLID,
                        owner_id=INVALID, elem_id=gs_id, design_option=design_option)
    # 3. line sub-category (owned by the type, points at its gstyle)
    cat_rec = new_category("", OST_TextNoteLineStyle, owner_id=type_id,
                           category_type=4, flags=7, gstyle_ids=[gs_id],
                           elem_id=cat_id, design_option=design_option)
    # the type's OWNED companions carry the internal design-option sentinel
    # in their objects (headers keep -1) -- verified on rme text types
    for r in (font_rec, cat_rec, gs_rec):
        r.obj["m_designOptionId"] = INTERNAL_DESIGN_OPTION
    # 1. the type
    obj = blank_object("TextNoteAttributes")
    element_defaults(obj, type_id, design_option=design_option,
                     double_params={-1006327: float(width_factor),
                                    -1006326: mm(tab_size_mm)},
                     elemid_params={-1006315: int(leader_arrowhead_id)})
    symbol_defaults(obj, name)
    gt = blank_object("GeomTable")
    gt.update({"m_refPntMirrored": False, "m_table": [], "m_bigTableOwner": None,
               "m_materialMarkers": [], "m_faceTypeMarkers": []})
    obj["m_pGeomTable"] = _ptr("GeomTable", gt)
    obj["m_lineAndTextAttr"] = {"m_fontId": font_id, "m_categoryId": cat_id,
                               "m_background": int(background),
                               "m_bBold": bool(bold), "m_bItalic": bool(italic),
                               "m_bUnderline": bool(underline)}
    obj["m_leaderOffsetSheet"] = mm(leader_offset_mm)
    obj["m_textBoxVisibility"] = bool(show_border)
    dele = [font_id, cat_id, gs_id] + ([leader_arrowhead_id]
                                        if leader_arrowhead_id not in (None, INVALID)
                                        else [])
    type_rec = _record("text_type", "TextNoteAttributes", INVALID, type_id, obj,
                       deletion_ids=dele, design_option=design_option,
                       refs={"font": font_id, "line_category": cat_id,
                             "line_style": gs_id, "arrowhead": leader_arrowhead_id},
                       notes=([] if leader_arrowhead_id not in (None, INVALID) else
                              ["leader arrowhead LeaderStyle id -1: arrowhead "
                               "types are separate document standards"]))
    return [type_rec, font_rec, cat_rec, gs_rec]


# ---------------------------------------------------------------------------
# OBJECT STYLES  (built-in-category GStyleElem records)
# ---------------------------------------------------------------------------

_DATA_DIR = os.environ.get(
    "RVT_REFERENCE_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                 "experiments", "genesis", "reference"))
# QUARANTINE: the Autodesk-extracted style table lives OUTSIDE src/ (never in
# the shipped plugin). default_object_styles() must move to OUR house standard;
# until then it reads the quarantined reference file and marks output as such.
_STYLE_TABLE_FILE = "object_styles.autodesk-extracted.json"


def object_styles_table() -> dict:
    """The bundled built-in object-styles table (data/object_styles.json):
    per BuiltInCategory, the projection/cut pen, color and line pattern
    Revit 2026 assigns by default -- a PRODUCT CONSTANT (1,239 of the 1,407
    entries are byte-identical between two unrelated sample projects; the
    remainder are the MEP template's values, flagged confirmed=false)."""
    with open(os.path.join(_DATA_DIR, _STYLE_TABLE_FILE)) as fh:
        return json.load(fh)


def default_object_styles(ids: IdArg, *, categories: Optional[Iterable[int]] = None,
                          confirmed_only: bool = False,
                          line_pattern_ids: Optional[dict] = None,
                          material_id: int = INVALID) -> list:
    """Generate the document's OBJECT STYLES = one projection GStyleElem
    (+ one cut GStyleElem where the category is cuttable) per built-in
    category, from the bundled product-constant table.

    ``categories`` restricts the set (built-in OST ids); ``confirmed_only``
    keeps only cross-file-confirmed constants; ``line_pattern_ids`` maps a
    pattern NAME -> a :func:`new_line_pattern` id for the (few) built-in
    styles that use a named non-solid pattern (else solid);
    ``material_id`` = the material every style points at (-1 = none; the
    template points a few categories at file-local materials, which are not
    portable).  Returns [TypeRecord (GStyleElem), ...].
    """
    tab = object_styles_table()["styles"]
    lp_by_name = line_pattern_ids or {}
    want = set(int(c) for c in categories) if categories is not None else None
    out = []
    for cat_s, ent in sorted(tab.items(), key=lambda kv: int(kv[0])):
        cat = int(cat_s)
        if want is not None and cat not in want:
            continue
        for role in ("projection", "cut"):
            e = ent.get(role)
            if not e:
                continue
            if confirmed_only and not e.get("confirmed"):
                continue
            pat = e.get("pattern_id")
            if pat is None:
                pn = e.get("pattern_name")
                pat = lp_by_name.get(pn, LINEPATTERN_SOLID if pn else INVALID)
            out.append(new_gstyle(
                cat, style_type=role, pen=int(e.get("pen") or 1),
                color=int(e.get("color") or 0), line_pattern_id=int(pat),
                material_id=int(material_id), screen_sized=bool(e.get("screen_sized")),
                ids=ids))
    return out


# ---------------------------------------------------------------------------
# CATALOG: id allocation + cross-reference wiring + injection/verification
# ---------------------------------------------------------------------------

class GenesisCatalog:
    """Collects TypeRecords, allocates ids, verifies and (optionally) injects.

    ``GenesisCatalog(ids=Document)`` continues an existing document's id
    watermark (injection into a template); ``GenesisCatalog(start=N)``
    numbers a standalone genesis document.  Every ``add_*`` mirrors the
    module-level constructor, appending the record(s).
    """

    def __init__(self, ids=None, start: int = 100_000):
        self.ids = ids if ids is not None else IdSource(start)
        self.records: list = []

    # allocation ------------------------------------------------------------
    def next_id(self) -> int:
        return int(self.ids.next_id())

    def add(self, rec) -> "TypeRecord":
        if isinstance(rec, (list, tuple)):
            for r in rec:
                self.records.append(r)
            return rec
        self.records.append(rec)
        return rec

    # constructor mirrors -------------------------------------------------
    def wall_type(self, name, layers, **kw):
        return self.add(new_wall_type(name, layers, ids=self, **kw))

    def floor_type(self, name, layers, **kw):
        return self.add(new_floor_type(name, layers, ids=self, **kw))

    def roof_type(self, name, layers, **kw):
        return self.add(new_roof_type(name, layers, ids=self, **kw))

    def ceiling_type(self, name, layers, **kw):
        return self.add(new_ceiling_type(name, layers, ids=self, **kw))

    def material(self, name, color=(120, 120, 120), **kw):
        return self.add(new_material(name, color, ids=self, **kw))

    def line_pattern(self, name, segments_mm, **kw):
        return self.add(new_line_pattern(name, segments_mm, ids=self, **kw))

    def fill_pattern(self, name, grids, **kw):
        return self.add(new_fill_pattern(name, grids, ids=self, **kw))

    def voltage_type(self, name, volts_nominal, **kw):
        return self.add(new_voltage_type(name, volts_nominal, ids=self, **kw))

    def distribution_system(self, name, **kw):
        return self.add(new_distribution_system(name, ids=self, **kw))

    def conduit_standard(self, name, **kw):
        return self.add(new_conduit_standard(name, ids=self, **kw))

    def conduit_sizes(self, sizes_by_standard, **kw):
        return self.add(conduit_sizes_element(sizes_by_standard, ids=self, **kw))

    def conduit_type(self, name, **kw):
        return self.add(new_conduit_type(name, ids=self, **kw))

    def cable_tray_sizes(self, sizes_in, **kw):
        return self.add(cable_tray_sizes_element(sizes_in, ids=self, **kw))

    def cable_tray_type(self, name, **kw):
        return self.add(new_cable_tray_type(name, ids=self, **kw))

    def wire_type(self, name, **kw):
        return self.add(new_wire_type(name, ids=self, **kw))

    def demand_factor(self, name, factor=1.0, **kw):
        return self.add(new_demand_factor(name, factor, ids=self, **kw))

    def load_class(self, name, demand_factor_id=INVALID, **kw):
        return self.add(new_load_class(name, demand_factor_id, ids=self, **kw))

    def electrical_setting(self, **kw):
        return self.add(electrical_setting(ids=self, **kw))

    def text_type(self, name, **kw):
        return self.add(new_text_type(name, ids=self, **kw))

    def object_styles(self, **kw):
        recs = default_object_styles(self, **kw)
        for r in recs:
            self.records.append(r)
        return recs

    def wire_type_full(self, name, *, material="Copper", temperature="75",
                       insulation="THWN", max_size=("500", 21.79),
                       **kw):
        """A complete wire definition: the 4 conductor cells + the wire type,
        wired together.  ``max_size`` = (size name, diameter_mm)."""
        mat = self.add(new_conductor_material(material, ids=self))
        tmp = self.add(new_conductor_temperature_rating(temperature, ids=self))
        ins = self.add(new_conductor_insulation(insulation, ids=self))
        siz = self.add(new_conductor_size(max_size[0], max_size[1], ids=self))
        wt = self.add(new_wire_type(name, material_id=mat.elem_id,
                                    temperature_rating_id=tmp.elem_id,
                                    insulation_id=ins.elem_id,
                                    max_size_id=siz.elem_id, ids=self, **kw))
        return [wt, mat, tmp, ins, siz]

    # verification -----------------------------------------------------------
    def roundtrip(self) -> dict:
        """Encode+decode every record; summary + per-record failures."""
        ok = 0
        fails = []
        for r in self.records:
            rep = r.roundtrip()
            if rep["ok"]:
                ok += 1
            else:
                fails.append({"elem_id": r.elem_id, "class": r.class_name,
                              "report": rep})
        return {"records": len(self.records), "ok": ok, "failures": fails}

    def check_references(self, known_ids: Optional[Iterable[int]] = None) -> list:
        """Every positive ElementId a record references must be another
        catalog record or in ``known_ids`` (template ids).  Returns the
        dangling (elem_id, path, target) list.

        The compound-structure grid / geometry-step subtrees are topology
        (segment/region/layer/step indices), not ElementIds, and are skipped.
        """
        from ..mutate import _collect_ids
        mine = {r.elem_id for r in self.records}
        known = set(known_ids or ()) | mine
        bad = []
        for r in self.records:
            for path, i in _element_refs(r):
                if i > 0 and i not in known and i != r.elem_id:
                    bad.append({"elem_id": r.elem_id, "path": path, "target": i})
        return bad

    # emission ---------------------------------------------------------------
    def new_elements(self, creation_ep: int = 0) -> list:
        """All records as ``rvt.mutate.NewElement`` objects (id-sorted)."""
        return [r.as_new_element(creation_ep)
                for r in sorted(self.records, key=lambda x: x.elem_id)]

    def commit_into(self, src_rvt: str, out_path: str, *,
                    identity: Optional[dict] = None):
        """Inject the catalog into a copy of ``src_rvt`` via the proven
        ``rvt.commit.commit_new_elements`` (host-document save unit 0), then
        run ``verify_written``.  Returns (CommitReport, verify_report).

        ``identity`` is passed through to the writer's BasicFileInfo
        identity scrub (see rvt.identity).
        """
        from ..commit import commit_new_elements, verify_written
        els = self.new_elements()
        recs = [{seq: bytes_ for seq, bytes_ in
                 zip((101, 102, 103), _encode_element(el))} for el in els]
        rep = commit_new_elements(src_rvt, out_path, recs, [el.elemrec for el in els],
                                  identity=identity)
        ver = verify_written(out_path, [el.elem_id for el in els])
        return rep, ver

    def to_json(self) -> dict:
        return {"count": len(self.records),
                "records": [r.to_json() for r in self.records]}


#: subtrees / keys whose integers are internal topology or table indices,
#: never ElementIds (grid segment/region/layer/gstep ids, id counters)
_NOT_ELEMENT_ID_SUBTREES = ("m_oVertRegStructure", "m_grid", "m_geomSteps",
                            "m_segRefFaceKeys", "m_regionToLayerMap")
_NOT_ELEMENT_ID_KEYS = {"m_regionId", "m_segmentIds", "m_layerId", "m_idCounter",
                        "m_layerFunction", "m_layerPriority", "m_embeddingType",
                        "m_gstyleType", "m_categoryType", "m_paramId"}


def _element_refs(rec: "TypeRecord") -> list:
    """(path, id) for every plausible ElementId reference of a record,
    excluding the internal-topology subtrees."""
    from ..mutate import _collect_ids
    out: list = []
    trees = [(rec.header, "seq101"), (rec.obj, "seq102")]
    if rec.rep is not None:
        trees.append((rec.rep, "seq103"))
    for tree, tag in trees:
        raw: list = []
        _collect_ids(tree, raw, tag)
        for path, i in raw:
            if any(t in path for t in _NOT_ELEMENT_ID_SUBTREES):
                continue
            leaf = path.rsplit(".", 1)[-1].split("[")[0]
            if leaf in _NOT_ELEMENT_ID_KEYS:
                continue
            out.append((path, i))
    return out


def _encode_element(el) -> tuple:
    from ..encode import encode_record
    out = []
    for seq, cid, obj in el.records():
        out.append(encode_record(seq, el.elem_id, None, cid, obj))
    return tuple(out)


# ---------------------------------------------------------------------------
# DEMO / self-test
# ---------------------------------------------------------------------------

def demo_catalog(start: int = 200_000) -> GenesisCatalog:
    """A representative electrical-project standards catalog built purely
    from our own parameters (no template): materials, patterns, wall/floor/
    roof/ceiling types, voltages, distribution systems, conduit standard +
    sizes + types, cable tray, wire, load classes, electrical setting, a
    text type and a small object-styles set."""
    cat = GenesisCatalog(start=start)
    # patterns + materials
    dash = cat.line_pattern("GEN Dash 3mm", [("dash", 3.0), ("space", 3.0)])
    cross = cat.fill_pattern("GEN Diagonal crosshatch",
                             [{"angle_deg": 45, "spacing_mm": 3.0},
                              {"angle_deg": 135, "spacing_mm": 3.0}])
    conc = cat.material("GEN Concrete, Cast-in-Place", (192, 192, 192),
                        material_class="Concrete", category="Concrete",
                        cut_pattern_id=cross.elem_id)
    gyp = cat.material("GEN Gypsum Wall Board", (250, 250, 245),
                       material_class="Gypsum Board", category="Interior")
    stud = cat.material("GEN Metal Stud Layer", (160, 160, 170),
                        material_class="Metal", category="Metal")
    # system-family types
    cat.wall_type("GEN Interior - 92mm Partition (1-hr)",
                  [("finish2", 16.0, gyp.elem_id), ("structure", 92.0, stud.elem_id),
                   ("finish1", 16.0, gyp.elem_id)])
    cat.wall_type("GEN Exterior - 200mm Concrete",
                  [("structure", 200.0, conc.elem_id)], function=1)
    cat.floor_type("GEN Slab 150mm Concrete", [("structure", 150.0, conc.elem_id)])
    cat.roof_type("GEN Roof - Generic 300mm", [("structure", 300.0, INVALID)])
    cat.ceiling_type("GEN ACT 600x600",
                     [("finish2", 16.0, gyp.elem_id), ("structure", 30.0, INVALID)])
    # electrical definitions
    v120 = cat.voltage_type("120", 120)
    v208 = cat.voltage_type("208", 208)
    v277 = cat.voltage_type("277", 277)
    v480 = cat.voltage_type("480", 480)
    cat.distribution_system("120/208 Wye", phase="three", config="wye", wires=4,
                            voltage_ll_id=v208.elem_id, voltage_lg_id=v120.elem_id)
    cat.distribution_system("480/277 Wye", phase="three", config="wye", wires=4,
                            voltage_ll_id=v480.elem_id, voltage_lg_id=v277.elem_id)
    # conduit
    emt = cat.conduit_standard("EMT")
    cat.conduit_sizes({emt.elem_id: [
        (0.5, 0.622, 0.706, 4.35), (0.75, 0.824, 0.922, 4.96),
        (1.0, 1.049, 1.163, 6.33), (1.25, 1.380, 1.510, 8.0),
        (1.5, 1.610, 1.740, 9.12), (2.0, 2.067, 2.197, 10.6),
        (2.5, 2.731, 2.875, 10.6), (3.0, 3.356, 3.500, 13.0),
        (3.5, 3.834, 4.000, 15.0), (4.0, 4.334, 4.500, 16.0)]})
    cat.conduit_type("GEN Conduit - EMT (no fittings)", standard_id=emt.elem_id,
                     with_fitting=False)
    cat.conduit_type("GEN Conduit - EMT with Fittings", standard_id=emt.elem_id,
                     with_fitting=True)
    # cable tray
    cat.cable_tray_sizes([4, 6, 8, 12, 18, 24, 30, 36])
    cat.cable_tray_type("GEN Ladder Cable Tray", shape="ladder")
    cat.cable_tray_type("GEN Solid Bottom Cable Tray", shape="ushape")
    # wire (full definition: 4 conductor cells + type)
    cat.wire_type_full("GEN THWN Copper", material="Copper", temperature="75",
                       insulation="THWN", max_size=("500", 21.79))
    # load classes
    df_lt = cat.demand_factor("GEN Lighting Demand", 1.0)
    df_rc = cat.demand_factor("GEN Receptacle Demand", 1.0,
                              rows=[(0.0, 10000.0, 1.0), (10000.0, 1e30, 0.5)],
                              rule="load")
    cat.load_class("GEN Lighting", df_lt.elem_id)
    cat.load_class("GEN Receptacle", df_rc.elem_id)
    cat.electrical_setting()
    # annotation standards
    cat.text_type("GEN 3.2mm Arial", font="Arial", size_mm=3.2)
    # a slice of the object-styles table (walls, floors, electrical, MEP)
    cat.object_styles(categories=[OST_Walls, OST_Floors, OST_Roofs, OST_Ceilings,
                                  -2001040, -2001060, -2001120, OST_Conduit,
                                  OST_CableTray, OST_Wire, OST_TextNotes],
                      line_pattern_ids={"Dash": dash.elem_id})
    return cat


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cat = demo_catalog()
    rt = cat.roundtrip()
    dangling = cat.check_references()
    kinds = {}
    for r in cat.records:
        kinds[r.class_name] = kinds.get(r.class_name, 0) + 1
    print(f"genesis demo catalog: {rt['records']} records, "
          f"{len(kinds)} classes; round-trip clean+byte-exact "
          f"{rt['ok']}/{rt['records']}; dangling references {len(dangling)}")
    for k, n in sorted(kinds.items()):
        print(f"   {n:3d} x {k}")
    for f in rt["failures"][:5]:
        print("   FAIL", f["elem_id"], f["class"],
              {k: (v.get("errors") if isinstance(v, dict) else v)
               for k, v in f["report"].items() if k != "ok"})
    if "--json" in argv:
        json.dump(cat.to_json(), sys.stdout, indent=1, default=str)
        print()
    return 0 if (rt["ok"] == rt["records"] and not dangling) else 1


if __name__ == "__main__":
    sys.exit(main())
