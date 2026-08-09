"""inventory.py — name resolution + seed inventory for authoring on ANY .rvt.

Solves "everything comes back nameless": tells a firm what their SEED file
actually contains — named wall types (with thickness), family symbols
(family :: type, category, placed instances, hosting pattern), levels,
titleblocks, view templates and phases — so authoring can target the
firm's own standards instead of Autodesk's sample content.

Where names live (verified on the rme / rst / rac 2026 samples):

* Level                 -> ``m_text`` (elevation via ``m_pSurface.m_origin.z``)
* FamilySymbol / *Type  -> ``m_symbolInfo.value.m_name``.  Symbols whose
  name is empty are per-instance GEOMETRY CLONES: ``m_masterId`` points at
  the named master symbol (445/632 rme symbols are clones).  Resolve the
  name through the master; count instances against the master.
* Family                -> ``m_name`` (the family / .rfa name).
* Wall types            -> ``BasicWallType`` / ``StackedWallType`` /
  ``CurtainWallType`` objects, ``m_symbolInfo.value.m_name``; thickness =
  sum(``m_pCompoundStructure.value.m_layers[*].m_layerWidth``) in feet.
* Views (``DBView*``)   -> ``m_viewName``; templates carry
  ``m_isTemplate == True``.  Panel schedule templates: ``m_name``.
* Materials             -> ``m_pMaterial.value.m_name``.
* Phases (ProjectPhase) -> ``m_name``.
* Rooms / Spaces        -> AString params ROOM_NAME (-1006900) and
  ROOM_NUMBER (-1006901); panel instances carry RBS_ELEC_PANEL_NAME
  (-1140078) and ALL_MODEL_MARK (-1001203).
* Categories            -> the element header (seq-101) ``m_categroryId``.
  Negative ids are Autodesk's fixed public ``BuiltInCategory`` enum
  (``OST_*``) — the file stores NO id->name table for built-ins (verified:
  no ``OST_`` strings anywhere; ``CategoryTable``/``IFCCategoryTemplate``
  carry no built-in names), so a table of the public constants is embedded
  below and every entry that a sample corroborates is marked verified.
  Positive category ids are ``CategoryElem`` objects in the file:
  ``m_pCategory.value.m_name`` (+ ``m_parentCategoryId``).

Public API::

    element_name(doc, eid) -> str | None
    type_name(doc, type_id) -> str | None
    family_and_symbol_names(doc, symbol_id) -> (family, symbol)
    category_name(doc, cat_id) -> str | None      # 'OST_...' or file name
    category_label(doc, cat_id) -> str | None     # human label
    inventory(doc) -> dict

Demo::

    python -m rvt.inventory samples/rmebasicsampleproject.rvt
    python -m rvt.inventory --stats            # name-resolution % on 3 samples

The functions take an already-open ``Document`` (the caller's release
context applies); the CLI opens a path under the file's OWN release
(``rvt.global_framing.enter_own_release``), so a Revit 2025 / 2024 project
is inventoried, not refused.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from typing import Optional

# ---------------------------------------------------------------------------
# BuiltInCategory — Autodesk's fixed public API enum (OST_*), negative ids.
# The .rvt file stores NO name table for built-in categories, so this table is
# the only route from a header ``m_categroryId`` to a name.  VERIFIED means
# the id's element class / example type name in the three 2026 samples
# corroborates the meaning (e.g. -2001040 hosts panelboards/transformers,
# -2008013 hosts 'M_Supply Diffuser').  ASSUMED entries are the public
# constants recalled from the Revit API documentation but not exercised by
# any sample element — treat as strong hints, not gospel.
# ---------------------------------------------------------------------------
BUILTIN_CATEGORIES_VERIFIED = {
    -2000011: ("OST_Walls", "Walls"),                       # SWall
    -2000014: ("OST_Windows", "Windows"),
    -2000023: ("OST_Doors", "Doors"),                       # nested door refs
    -2000032: ("OST_Floors", "Floors"),                     # Floor
    -2000035: ("OST_Roofs", "Roofs"),                       # RoofAttributes
    -2000038: ("OST_Ceilings", "Ceilings"),                 # Ceiling
    -2000051: ("OST_Lines", "Lines"),                       # CurveElem (bulk)
    -2000080: ("OST_Furniture", "Furniture"),               # Seating chairs
    -2000100: ("OST_Columns", "Columns"),
    -2000120: ("OST_Stairs", "Stairs"),
    -2000126: ("OST_StairsRailing", "Railings"),           # BaseRailing
    -2000127: ("OST_StairsRailingBaluster", "Balusters"),   # '8 x 40mm'
    -2000151: ("OST_GenericModel", "Generic Models"),
    -2000150: ("OST_GenericAnnotation", "Generic Annotations"),  # Centerline / Help Button
    -2000160: ("OST_Rooms", "Rooms"),                       # RoomElem
    -2000170: ("OST_CurtainWallPanels", "Curtain Panels"),  # FamilyInstance
    -2000171: ("OST_CurtainWallMullions", "Curtain Wall Mullions"),  # SysMullionFamSym
    -2000180: ("OST_Ramps", "Ramps"),
    -2000181: ("OST_Cornices", "Wall Sweeps"),              # CorniceAttr
    -2000182: ("OST_Reveals", "Reveals"),                   # RevealAttr
    -2000197: ("OST_ReferenceViewer", "View References"),  # M_View Reference
    -2000220: ("OST_Grids", "Grids"),                       # Grid
    -2000240: ("OST_Levels", "Levels"),                     # Level
    -2000260: ("OST_Dimensions", "Dimensions"),             # LinearDimString
    -2000279: ("OST_Views", "Views"),                       # DBViewSection
    -2000280: ("OST_TitleBlocks", "Title Blocks"),          # 'A0 metric'
    -2000300: ("OST_TextNotes", "Text Notes"),              # TextNote
    -2000340: ("OST_CurtaSystem", "Curtain Systems"),       # CurtaSystemAttr
    -2000400: ("OST_SectionHeads", "Section Heads"),        # M_Section Head
    -2000450: ("OST_WindowTags", "Window Tags"),            # M_Window Tag
    -2000460: ("OST_DoorTags", "Door Tags"),                # M_Door Tag
    -2000480: ("OST_RoomTags", "Room Tags"),                # M_Room Tag
    -2000485: ("OST_MEPSpaceTags", "Space Tags"),           # M_Space Tag
    -2000510: ("OST_Viewports", "Viewports"),               # Viewport
    -2000515: ("OST_ViewportLabel", "View Titles"),         # M_View Title
    -2000538: ("OST_CalloutHeads", "Callout Heads"),        # Callout Head
    -2000700: ("OST_Materials", "Materials"),               # MaterialElem
    -2000924: ("OST_PropertySet", "Property Sets"),         # PropertySetElement
    -2000946: ("OST_RailingTopRail", "Top Rails"),          # TopRailType
    -2000947: ("OST_RailingHandRail", "Handrails"),         # HandRailType
    -2000948: ("OST_RailingSupport", "Supports"),           # railing support
    -2001000: ("OST_Casework", "Casework"),                 # Kitchen Island
    -2001040: ("OST_ElectricalEquipment", "Electrical Equipment"),   # panels/xfmr
    -2001060: ("OST_ElectricalFixtures", "Electrical Fixtures"),     # GFCI receptacle
    -2001100: ("OST_FurnitureSystems", "Furniture Systems"),
    -2001120: ("OST_LightingFixtures", "Lighting Fixtures"),         # 600x600 - 277
    -2001140: ("OST_MechanicalEquipment", "Mechanical Equipment"),   # WSHP 7 kW
    -2001160: ("OST_PlumbingFixtures", "Plumbing Fixtures"),         # water closet
    -2001260: ("OST_Site", "Site"),                         # M_Wind Power Generator
    -2001269: ("OST_SitePropertyLineSegmentTags", "Property Line Tags"),
    -2001300: ("OST_StructuralFoundation", "Structural Foundations"),  # FloorAttributes
    -2001320: ("OST_StructuralFraming", "Structural Framing"),         # beams 356mm
    -2001327: ("OST_StructuralFramingSystem", "Structural Beam Systems"),  # JoistSystemAttr
    -2001330: ("OST_StructuralColumns", "Structural Columns"),         # STB d=30
    -2001340: ("OST_Topography", "Topography"),             # SiteSurface
    -2001350: ("OST_SpecialityEquipment", "Specialty Equipment"),      # 'Aufzug' lift
    -2001352: ("OST_RvtLinks", "RVT Links"),                # RvtLinkSymbol
    -2001360: ("OST_Planting", "Planting"),                 # "Red Ash - 25'"
    -2001370: ("OST_Entourage", "Entourage"),               # M_RPC Beetle
    -2002000: ("OST_DetailComponents", "Detail Items"),     # AISC section / Brick coursing
    -2003000: ("OST_ProfileFamilies", "Profiles"),          # mullion / handrail / cable profiles
    -2003101: ("OST_ProjectInformation", "Project Information"),      # ProjectInfo
    -2003200: ("OST_Areas", "Areas"),                       # RoomElem (area)
    -2003400: ("OST_Mass", "Mass"),                         # 'Giebel'
    -2003500: ("OST_StackedWalls", "Stacked Walls"),        # StackedWallType
    -2003600: ("OST_MEPSpaces", "Spaces"),                  # RoomElem (MEP only)
    -2005003: ("OST_ElectricalEquipmentTags", "Electrical Equipment Tags"),
    -2005008: ("OST_LightingFixtureTags", "Lighting Fixture Tags"),
    -2005009: ("OST_MechanicalEquipmentTags", "Mechanical Equipment Tags"),
    -2005015: ("OST_StructuralFramingTags", "Structural Framing Tags"),
    -2005018: ("OST_StructuralColumnTags", "Structural Column Tags"),
    -2005019: ("OST_StructuralFoundationTags", "Structural Foundation Tags"),
    -2005021: ("OST_PlantingTags", "Planting Tags"),
    -2005029: ("OST_KeynoteTags", "Keynote Tags"),         # M_Keynote Tag
    -2005100: ("OST_SpotElevSymbols", "Spot Elevation Symbols"),
    -2005301: ("OST_BoundaryConditions", "Structural Boundary Conditions"),
    -2006020: ("OST_LevelHeads", "Level Heads"),            # M_Level Head
    -2006040: ("OST_GridHeads", "Grid Heads"),              # M_Grid Head
    -2006045: ("OST_ElevationMarks", "Elevation Marks"),
    -2006060: ("OST_RevisionClouds", "Revision Clouds"),    # RevisionCloudAttr
    -2007000: ("OST_ConnectorElem", "Connectors"),          # ConnectorElem
    -2008000: ("OST_DuctCurves", "Ducts"),                  # RbsDuctCurve
    -2008003: ("OST_DuctTags", "Duct Tags"),                # M_Duct Size Tag
    -2008004: ("OST_FlexDuctTags", "Flex Duct Tags"),       # M_Flex Duct Tag
    -2008010: ("OST_DuctFitting", "Duct Fittings"),         # duct cross/tee
    -2008013: ("OST_DuctTerminal", "Air Terminals"),        # supply diffuser
    -2008014: ("OST_DuctTerminalTags", "Air Terminal Tags"),  # Diffuser Tag
    -2008015: ("OST_DuctSystem", "Duct Systems"),           # RbsHvacSystem
    -2008020: ("OST_FlexDuctCurves", "Flex Ducts"),         # RbsFlexDuctCurve
    -2008037: ("OST_ElectricalCircuit", "Electrical Circuits"),  # RbsElectricalSystem
    -2008039: ("OST_Wire", "Wires"),                        # RbsWireCurve
    -2008043: ("OST_PipingSystem", "Piping Systems"),       # RbsPipingSystem
    -2008044: ("OST_PipeCurves", "Pipes"),                  # RbsPipeCurve
    -2008047: ("OST_PipeTags", "Pipe Tags"),                # M_Pipe Size Tag
    -2008049: ("OST_PipeFitting", "Pipe Fittings"),         # M_Pipe Tee
    -2008050: ("OST_FlexPipeCurves", "Flex Pipes"),         # RbsFlexPipeType
    -2008057: ("OST_WireTags", "Wire Tags"),                # M_Wire Tag
    -2008087: ("OST_LightingDevices", "Lighting Devices"),  # 'Single Pole' switch
    -2008099: ("OST_Sprinklers", "Sprinklers"),             # 15 mm Pendent
    -2008107: ("OST_HVAC_Zones", "HVAC Zones"),             # ZoneElement
    -2008115: ("OST_ZoneTags", "HVAC Zone Tags"),           # M_Zone Tag
    -2008126: ("OST_CableTrayFitting", "Cable Tray Fittings"),  # Channel Horizontal Bend
    -2008128: ("OST_ConduitFitting", "Conduit Fittings"),   # Conduit Body - Type L
}

# Public Revit API constants NOT exercised by any element in the three
# samples — recalled from the API documentation, useful hints only.
BUILTIN_CATEGORIES_ASSUMED = {
    -2000095: ("OST_IOSModelGroups", "Model Groups"),
    -2000123: ("OST_StairsStringerCarriage", "Stair Supports"),
    -2000500: ("OST_Cameras", "Cameras"),
    -2000530: ("OST_CLines", "Reference Planes"),
    -2000560: ("OST_RasterImages", "Raster Images"),
    -2000573: ("OST_Schedules", "Schedules"),
    -2000600: ("OST_Sheets", "Sheets"),
    -2000710: ("OST_ReferencePoints", "Reference Points"),
    -2001180: ("OST_Parking", "Parking"),
    -2001220: ("OST_Roads", "Roads"),
    -2001271: ("OST_SharedBasePoint", "Survey Point"),
    -2001272: ("OST_ProjectBasePoint", "Project Base Point"),
    -2008016: ("OST_DuctAccessory", "Duct Accessories"),
    -2008055: ("OST_PipeAccessory", "Pipe Accessories"),
    -2008077: ("OST_CommunicationDevices", "Communication Devices"),
    -2008079: ("OST_SecurityDevices", "Security Devices"),
    -2008081: ("OST_FireAlarmDevices", "Fire Alarm Devices"),
    -2008083: ("OST_DataDevices", "Data Devices"),
    -2008085: ("OST_NurseCallDevices", "Nurse Call Devices"),
    -2008130: ("OST_CableTray", "Cable Trays"),
    -2008132: ("OST_Conduit", "Conduits"),
}

# well-known category ids used by the authoring layer
OST_ELECTRICAL_EQUIPMENT = -2001040
OST_TITLEBLOCKS = -2000280
OST_DOORS = -2000023
OST_WALLS = -2000011

# well-known BuiltInParameter ids (AString param sets)
BIP_ROOM_NAME = -1006900
BIP_ROOM_NUMBER = -1006901
BIP_PANEL_NAME = -1140078          # RBS_ELEC_PANEL_NAME
BIP_MARK = -1001203                # ALL_MODEL_MARK

WALL_TYPE_CLASSES = ("BasicWallType", "StackedWallType", "CurtainWallType")


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------
def _dig(v, *keys):
    """Walk value dicts through owned-pointer wrappers ({'value': {...}})."""
    cur = v
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
        if isinstance(cur, dict) and "value" in cur and (
                "ptr_class" in cur or "pid" in cur):
            cur = cur.get("value")
    return cur


def _clean_str(s) -> Optional[str]:
    if isinstance(s, str):
        s = s.strip()
        return s or None
    return None


def _symbolinfo_name(v: dict) -> Optional[str]:
    return _clean_str(_dig(v, "m_symbolInfo", "m_name"))


def _astring_param(v: dict, param_id: int) -> Optional[str]:
    ps = _dig(v, "m_pParamValueSetAString", "m_paramSet") or []
    for p in ps:
        if isinstance(p, dict) and p.get("m_paramId") == param_id:
            return _clean_str(p.get("m_value"))
    return None


def _class_of(doc, eid: int) -> Optional[str]:
    try:
        return doc.class_of(eid)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# public name resolution
# ---------------------------------------------------------------------------
def family_and_symbol_names(doc, symbol_id: int) -> tuple[Optional[str], Optional[str]]:
    """(family_name, symbol_name) for a FamilySymbol-like element.

    Follows ``m_masterId`` when the symbol is a nameless geometry clone.
    """
    v = doc.value(symbol_id) or {}
    if not isinstance(v, dict):
        return None, None
    name = _symbolinfo_name(v)
    fam_id = v.get("m_familyId")
    master = v.get("m_masterId")
    hops = 0
    while name is None and master not in (None, -1, symbol_id) and hops < 8:
        mv = doc.value(master) or {}
        name = _symbolinfo_name(mv)
        if fam_id in (None, -1):
            fam_id = mv.get("m_familyId")
        master = mv.get("m_masterId")
        hops += 1
    fam = None
    if fam_id not in (None, -1):
        fv = doc.value(fam_id) or {}
        fam = _clean_str(fv.get("m_name")) if isinstance(fv, dict) else None
    return fam, name


def type_name(doc, type_id: int) -> Optional[str]:
    """The type (symbol) name of ANY *Type / FamilySymbol element."""
    v = doc.value(type_id) or {}
    if not isinstance(v, dict):
        return None
    n = _symbolinfo_name(v)
    if n:
        return n
    _, n = family_and_symbol_names(doc, type_id)
    return n


def element_name(doc, eid: int) -> Optional[str]:
    """Best human name for any element id (never invents one; None if none)."""
    cls = _class_of(doc, eid) or ""
    v = doc.value(eid)
    if not isinstance(v, dict):
        return None
    # datums / phases / families / views / materials / categories
    if cls == "Level" or "m_text" in v:
        n = _clean_str(v.get("m_text"))
        if n:
            return n
    if cls == "ProjectPhase" or (cls == "Family"):
        n = _clean_str(v.get("m_name"))
        if n:
            return n
    if cls.startswith("DBView") or "m_viewName" in v:
        n = _clean_str(v.get("m_viewName"))
        if n:
            return n
    if cls == "MaterialElem":
        n = _clean_str(_dig(v, "m_pMaterial", "m_name"))
        if n:
            return n
    if cls == "CategoryElem":
        n = _clean_str(_dig(v, "m_pCategory", "m_name"))
        if n:
            return n
    if cls == "RoomElem":
        num = _astring_param(v, BIP_ROOM_NUMBER)
        nam = _astring_param(v, BIP_ROOM_NAME)
        if num or nam:
            return f"{num} {nam}".strip() if num and nam else (nam or num)
    if cls in ("FamilyInstance",) or v.get("m_pInstanceInfo") is not None:
        panel = _astring_param(v, BIP_PANEL_NAME)
        if panel:
            return panel
        sid = _dig(v, "m_pInstanceInfo", "m_symbolId")
        if sid not in (None, -1):
            fam, sym = family_and_symbol_names(doc, sid)
            if fam or sym:
                return " : ".join(x for x in (fam, sym) if x)
        mark = _astring_param(v, BIP_MARK)
        if mark:
            return mark
    # symbol-like (types): symbol info, following the master for clones
    if "m_symbolInfo" in v:
        n = _symbolinfo_name(v)
        if n is None and v.get("m_masterId") not in (None, -1):
            _, n = family_and_symbol_names(doc, eid)
        if n:
            return n
    # generic fallbacks
    for key in ("m_name", "m_text", "m_viewName", "m_sName"):
        n = _clean_str(v.get(key))
        if n:
            return n
    for pid in (BIP_ROOM_NAME, BIP_PANEL_NAME, BIP_MARK):
        n = _astring_param(v, pid)
        if n:
            return n
    return None


def category_name(doc, cat_id: Optional[int]) -> Optional[str]:
    """OST_* name for built-in ids; the file's own name for CategoryElem ids."""
    if cat_id is None:
        return None
    if cat_id < 0:
        e = BUILTIN_CATEGORIES_VERIFIED.get(cat_id) or BUILTIN_CATEGORIES_ASSUMED.get(cat_id)
        return e[0] if e else f"OST_?({cat_id})"
    if doc is not None:
        v = doc.value(cat_id)
        if isinstance(v, dict):
            n = _clean_str(_dig(v, "m_pCategory", "m_name"))
            if n:
                return n
    return f"Category({cat_id})"


def category_label(doc, cat_id: Optional[int]) -> Optional[str]:
    """Human label ('Electrical Equipment'); file sub-categories return name."""
    if cat_id is None:
        return None
    if cat_id < 0:
        e = BUILTIN_CATEGORIES_VERIFIED.get(cat_id) or BUILTIN_CATEGORIES_ASSUMED.get(cat_id)
        return e[1] if e else None
    return category_name(doc, cat_id)


def category_source(cat_id: Optional[int]) -> str:
    if cat_id is None:
        return "none"
    if cat_id >= 0:
        return "file"
    if cat_id in BUILTIN_CATEGORIES_VERIFIED:
        return "builtin-verified"
    if cat_id in BUILTIN_CATEGORIES_ASSUMED:
        return "builtin-assumed"
    return "unknown"


# ---------------------------------------------------------------------------
# catalog pieces
# ---------------------------------------------------------------------------
def wall_thickness_ft(v: dict) -> Optional[float]:
    """Wall type thickness = sum of compound-structure layer widths (feet)."""
    layers = _dig(v, "m_pCompoundStructure", "m_layers") or []
    tot = 0.0
    n = 0
    for lyr in layers:
        w = lyr.get("m_layerWidth") if isinstance(lyr, dict) else None
        if isinstance(w, (int, float)):
            tot += float(w)
            n += 1
    return round(tot, 6) if n else None


def wall_types(doc) -> list[dict]:
    out = []
    used = _wall_type_usage(doc)
    for cls in WALL_TYPE_CLASSES:
        if not doc.dec.schema.by_name.get(cls):
            continue
        for tid in doc.ids_of_class(cls):
            v = doc.value(tid) or {}
            out.append({
                "id": tid,
                "class": cls,
                "kind": {"BasicWallType": "basic", "StackedWallType": "stacked",
                         "CurtainWallType": "curtain"}.get(cls, cls),
                "name": _symbolinfo_name(v),
                "family": _astring_param(v, -1010105),   # e.g. 'Basic Wall' / 'Mauerwerk'
                "thickness_ft": wall_thickness_ft(v),
                "walls_using": used.get(tid, 0),
            })
    out.sort(key=lambda r: (-(r["walls_using"] or 0), r["id"]))
    return out


def _wall_type_usage(doc) -> dict[int, int]:
    cnt: Counter = Counter()
    for wcls in ("SWall", "VWall", "Wall", "StackedWall", "CurtainWall"):
        if not doc.dec.schema.by_name.get(wcls):
            continue
        for w in doc.ids_of_class(wcls):
            v = doc.value(w) or {}
            t = v.get("m_WallAttributesId")
            if t not in (None, -1):
                cnt[t] += 1
    return cnt


def _instance_census(doc):
    """Per-master-symbol placed instance count + observed hosting patterns."""
    placed: Counter = Counter()
    hosting: dict[int, Counter] = defaultdict(Counter)
    for iid in doc.ids_of_class("FamilyInstance"):
        v = doc.value(iid) or {}
        if not isinstance(v, dict):
            continue
        sid = _dig(v, "m_pInstanceInfo", "m_symbolId")
        master = v.get("m_masterSymbolId")
        if master in (None, -1):
            master = sid
        # a symbol may itself be a clone -> hop to its master
        hops = 0
        while master not in (None, -1) and hops < 8:
            sv = doc.value(master) or {}
            m2 = sv.get("m_masterId") if isinstance(sv, dict) else None
            if m2 in (None, -1) or m2 == master:
                break
            master = m2
            hops += 1
        if master in (None, -1):
            continue
        placed[master] += 1
        host = v.get("m_hostId")
        wpb = bool(v.get("m_workPlaneBased"))
        if wpb:
            hosting[master]["face"] += 1
        elif host not in (None, -1):
            hosting[master]["host-cut"] += 1
        else:
            hosting[master]["free"] += 1
    return placed, hosting


def _family_hosting_hint(fv: dict) -> Optional[str]:
    if not isinstance(fv, dict):
        return None
    if fv.get("m_isWorkPlaneBased"):
        return "face"
    if fv.get("m_bIsHostBased"):
        return "host-cut"
    return "free"


def symbols(doc, category: Optional[int] = None, masters_only: bool = True) -> list[dict]:
    """FamilySymbol catalog with resolved names, categories, usage, hosting."""
    placed, host = _instance_census(doc)
    out = []
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        if not isinstance(v, dict):
            continue
        is_clone = _symbolinfo_name(v) is None and v.get("m_masterId") not in (None, -1)
        if masters_only and is_clone:
            continue
        cat = doc.category_of(sid)
        if category is not None and cat != category:
            continue
        fam, sym = family_and_symbol_names(doc, sid)
        fam_id = v.get("m_familyId")
        fv = doc.value(fam_id) if fam_id not in (None, -1) else None
        obs = host.get(sid)
        if obs:
            pattern = obs.most_common(1)[0][0]
        else:
            pattern = _family_hosting_hint(fv or {}) or "free"
        out.append({
            "id": sid,
            "symbol_id": sid,               # spec_to_rvt compatibility
            "family_id": fam_id,
            "family": fam,
            "family_name": fam,             # spec_to_rvt compatibility
            "symbol": sym,
            "symbol_name": sym,             # spec_to_rvt compatibility
            "category_id": cat,
            "category": category_name(doc, cat),
            "category_label": category_label(doc, cat),
            "placed_instances": placed.get(sid, 0),
            "hosting_pattern": pattern,     # free | face | host-cut
            "is_clone": is_clone,
        })
    out.sort(key=lambda r: ((r["category_id"] or 0), (r["family"] or ""), (r["symbol"] or "")))
    return out


def levels(doc) -> list[dict]:
    out = []
    for lv in doc.levels():
        out.append({"id": lv["id"], "name": lv.get("name"),
                    "elevation_ft": lv.get("elevation_ft"),
                    "is_building_story": lv.get("is_building_story")})
    return out


def phases(doc) -> list[dict]:
    order: list[int] = []
    for pid in doc.ids_of_class("AllProjectPhases"):
        v = doc.value(pid) or {}
        ids = v.get("m_phaseIds") or []
        order = [i for i in ids if isinstance(i, int)]
    seen = doc.ids_of_class("ProjectPhase") if doc.dec.schema.by_name.get("ProjectPhase") else []
    ids = [i for i in order if i in seen] + [i for i in seen if i not in order]
    out = []
    for i, pid in enumerate(ids):
        v = doc.value(pid) or {}
        out.append({"id": pid, "name": _clean_str(v.get("m_name")),
                    "description": _clean_str(v.get("m_description")), "sequence": i})
    return out


def view_templates(doc) -> list[dict]:
    out = []
    for cls in doc.dec.schema.by_name:
        if not cls.startswith("DBView"):
            continue
        for vid in doc.ids_of_class(cls):
            v = doc.value(vid) or {}
            if isinstance(v, dict) and v.get("m_isTemplate"):
                out.append({"id": vid, "class": cls, "name": _clean_str(v.get("m_viewName"))})
    if doc.dec.schema.by_name.get("PanelScheduleTemplate"):
        for tid in doc.ids_of_class("PanelScheduleTemplate"):
            v = doc.value(tid) or {}
            out.append({"id": tid, "class": "PanelScheduleTemplate",
                        "name": _clean_str(v.get("m_name"))})
    out.sort(key=lambda r: (r["class"], (r["name"] or "")))
    return out


def titleblocks(doc, symbol_rows: Optional[list[dict]] = None) -> list[dict]:
    rows = symbol_rows if symbol_rows is not None else symbols(doc, OST_TITLEBLOCKS)
    return [{"id": r["id"], "family": r["family"], "symbol": r["symbol"],
             "placed_instances": r["placed_instances"]}
            for r in rows if r["category_id"] == OST_TITLEBLOCKS]


def inventory(doc) -> dict:
    """Full seed inventory: levels, wall types, symbols, titleblocks,
    view templates, phases + name-resolution statistics."""
    syms = symbols(doc)
    wts = wall_types(doc)
    named_wt = sum(1 for w in wts if w["name"])
    named_sym = sum(1 for s in syms if s["symbol"])
    named_fam = sum(1 for s in syms if s["family"])
    cats = Counter(category_source(s["category_id"]) for s in syms)
    return {
        "project": getattr(doc, "project", None),
        "source": getattr(doc, "source_path", None),
        "levels": levels(doc),
        "wall_types": wts,
        "symbols": syms,
        "titleblocks": titleblocks(doc, syms),
        "view_templates": view_templates(doc),
        "phases": phases(doc),
        "stats": {
            "levels": len(doc.levels()),
            "wall_types": len(wts),
            "wall_types_named": named_wt,
            "wall_types_named_pct": _pct(named_wt, len(wts)),
            "symbols": len(syms),
            "symbols_named": named_sym,
            "symbols_named_pct": _pct(named_sym, len(syms)),
            "families_named_pct": _pct(named_fam, len(syms)),
            "category_sources": dict(cats),
        },
    }


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 100.0


# ---------------------------------------------------------------------------
# name-resolution statistics across the research corpus
# ---------------------------------------------------------------------------
def resolution_stats(project: str) -> dict:
    from .mutate import Document
    doc = Document.load(project)
    wts = wall_types(doc)
    syms_all = symbols(doc, masters_only=False)
    masters = [s for s in syms_all if not s["is_clone"]]
    clones = [s for s in syms_all if s["is_clone"]]
    clone_named = sum(1 for s in clones if s["symbol"])
    inst_named = 0
    inst = doc.ids_of_class("FamilyInstance")
    sample = inst[: 400]
    for i in sample:
        if element_name(doc, i):
            inst_named += 1
    lv = doc.levels()
    return {
        "project": project,
        "levels": len(lv), "levels_named": sum(1 for l in lv if l.get("name")),
        "wall_types": len(wts),
        "wall_types_named": sum(1 for w in wts if w["name"]),
        "wall_types_with_thickness": sum(1 for w in wts if w["thickness_ft"]),
        "symbols_master": len(masters),
        "symbols_master_named": sum(1 for s in masters if s["symbol"]),
        "symbols_master_family_named": sum(1 for s in masters if s["family"]),
        "symbols_master_categorized": sum(1 for s in masters if s["category_id"] is not None),
        "symbol_clones": len(clones),
        "symbol_clones_named_via_master": clone_named,
        "instances_sampled": len(sample), "instances_named": inst_named,
        "category_sources": dict(Counter(category_source(s["category_id"]) for s in masters)),
    }


def _print_stats():
    print(f"{'project':26s} {'levels':>7s} {'walltypes':>10s} {'wt thick':>8s} "
          f"{'symbols':>8s} {'sym named':>9s} {'fam named':>9s} {'categ':>6s} "
          f"{'clones':>7s} {'clone->name':>11s} {'inst named':>10s}")
    for p in ("rmebasicsampleproject", "rstbasicsampleproject", "racbasicsampleproject"):
        s = resolution_stats(p)
        print(f"{p:26s} {s['levels_named']:>3d}/{s['levels']:<3d} "
              f"{s['wall_types_named']:>4d}/{s['wall_types']:<5d} "
              f"{s['wall_types_with_thickness']:>4d}/{s['wall_types']:<3d} "
              f"{s['symbols_master']:>8d} "
              f"{s['symbols_master_named']:>4d}/{s['symbols_master']:<4d} "
              f"{s['symbols_master_family_named']:>4d}/{s['symbols_master']:<4d} "
              f"{s['symbols_master_categorized']:>3d}   "
              f"{s['symbol_clones']:>7d} "
              f"{s['symbol_clones_named_via_master']:>5d}/{s['symbol_clones']:<5d} "
              f"{s['instances_named']:>4d}/{s['instances_sampled']:<4d}")
        print(f"   category sources (masters): {s['category_sources']}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("--stats",):
        _print_stats()
        return 0
    import os
    from contextlib import ExitStack
    from .global_framing import enter_own_release
    from .mutate import Document
    path = argv[0]
    with ExitStack() as stack:                  # the file's own release, once
        note = enter_own_release(stack, path) if os.path.isfile(path) else None
        doc = Document.from_file(path) if path.endswith(".rvt") else Document.load(path)
        inv = inventory(doc)                    # plain data from here on
    if note:
        inv["release_note"] = note
    if "--json" in argv:
        json.dump(inv, sys.stdout, indent=1, default=str)
        print()
        return 0
    st = inv["stats"]
    print(f"== inventory of {path}")
    if note:
        print(f"release: {note}")
    print(f"levels ({st['levels']}): " + ", ".join(
        f"{l['name']}@{l['elevation_ft']:.2f}ft" for l in inv["levels"]))
    print(f"wall types: {st['wall_types_named']}/{st['wall_types']} named "
          f"({st['wall_types_named_pct']}%)")
    for w in inv["wall_types"][:12]:
        print(f"   {w['id']:>9d} {w['kind']:8s} {str(w['name'])[:40]:40s} "
              f"t={w['thickness_ft']} used={w['walls_using']}")
    print(f"symbols: {st['symbols_named']}/{st['symbols']} named "
          f"({st['symbols_named_pct']}%), families {st['families_named_pct']}%, "
          f"category sources {st['category_sources']}")
    for s in inv["symbols"][:15]:
        print(f"   {s['id']:>9d} [{s['category']}] {s['family']} :: {s['symbol']} "
              f"placed={s['placed_instances']} hosting={s['hosting_pattern']}")
    print(f"titleblocks: {len(inv['titleblocks'])}; view templates: "
          f"{len(inv['view_templates'])}; phases: {[p['name'] for p in inv['phases']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
