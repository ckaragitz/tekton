"""``Global/Latest`` = the serialized ``ADocument`` object graph -- FULLY DECODED.

RESULT (verified 6/6 sample files, byte-exact decode->encode round trip):

    Global/Latest OLE stream (logical, inflated payload after the 8-byte
    per-stream prefix ``u64 5``) =

        u16   class_id      = 0x1c  ADocument             ) exactly like an
        ...   ADocument OBJECT (schema-directed,           ) element record
              parent-first fields, breadth-first deferred   ) payload
              pointer bodies)                               )
        u32   0                                       trailing constant

    i.e. the SAME serialization the element records in ``Partitions/<N>``
    use ({u16 class_id, object}), decoded by the SAME schema-directed
    :class:`rvt.objects.ObjectDecoder`, with exactly TWO adjustments:

      1. archive-object-index (pid) seed: the DOCUMENT itself is archive
         object #1 (every ``m_pHostDocument`` / ``m_pDoc`` weak reference
         points at index 1), so the first pointed-to object gets pid 2 --
         whereas an element record's ROOT object is pid 2 and the document
         is the implicit pid 1.  ``ObjectDecoder`` pre-seeds ``{1, 2}``
         (element framing); the document decode seeds ``{1}``.  With the
         wrong seed the very first indexed AppInfo object (pid 2) is
         mistaken for a back-reference and the decode derails at once.
      2. container-count sanity cap: ``SteelModelInfo.m_steelModelLatest``
         is a ``char`` container holding a ~2 MB steel-model blob (dach),
         above the element decoder's 2,000,000 runaway guard.  The document
         reader lifts the cap (``BIG_CONTAINER``).

    No new grammar, no container classes the decoder lacked, no
    externalized sub-objects, no compression.  The wave-1 belief that
    30-60 % of the stream was an "LZ-compressed Forge units dictionary"
    was a mis-framing: that region is plain ``ESSchemaStorage`` --
    two containers of ``std::pair<AString, AString>`` (Autodesk Forge
    unit/symbol/quantity JSON + parameter/spec-group JSON), ordinary
    length-prefixed UTF-16LE strings, decoded to the byte.

DECODE COVERAGE (this module, ``python -m rvt.adocument``): every sample
consumes ``len(payload) - 4`` bytes with ZERO errors; the residual 4 bytes
are the trailing ``u32 0`` constant, present in all six; and
``encode(decode(x)) == x`` byte-for-byte on all six (1.5-4.7 MB each).

DOCUMENT SHAPE (the field map -- ``FIELD_MAP`` below is the data form):
the 19 ``ADocument`` fields serialize in schema order; the four members
whose bodies live in their OWN OLE streams are simply null / empty here
(``m_elemTable`` -> null ptr [Global/ElemTable]; ``m_pHistory`` -> null
[Global/History]; ``m_pPartitionTable`` -> null [Global/PartitionTable];
``m_appInfoArr`` -> empty container -- the app-infos hang off
``m_pAppInfoManager`` instead).  ``m_oContentTable`` (the family-content
registry; its documents' BODIES are in Global/ContentDocuments) IS inline
here as the GUID-keyed ``m_ContentRecSet``.  97-99 % of the bytes are
``m_pAppInfoManager -> AppInfoManager.m_appInfoArr``: a FIXED 241-slot
registry of singleton "AppInfo" manager/tracking objects (slot index =
compiled-in registration order = the archive pid sequence 2..; 227/241
slots hold the same class in all six files, 168 populated in every file,
59 never used -- ``APPINFO_SLOTS``).  Inside it live: the ES/Forge schema
corpus (``ESSchemaStorage``, ~84 % of rst/rac files), the per-category
element registries (``CategoryTracking``, ``ElementTrackingData`` ... =
the "dangling" sample-element references), sheet/assembly numbering
memory (``NewItemNumber``), worksharing per-user settings, wire-size /
electrical settings paths (``AbsLayoutAppInfo``), etc.  The room-name
strings live under ``m_oNobleSecondaryData -> ColorFillSecondaryData
.m_colorFillResults`` (colour-fill result caches).

Public API::

    from rvt.adocument import decode_latest, open_document_object, encode_latest
    adoc = decode_latest(payload)            # payload = inflated Global/Latest
    adoc.coverage                            # (consumed, total, fraction)
    adoc.value                               # the ADocument dict tree
    adoc.appinfo_slots()                     # 241 x class-or-None
    adoc.field_holdings()                    # per-top-field byte/count summary
    bytes_ = encode_latest(adoc.value)       # -> byte-identical payload
    python -m rvt.adocument [--all] [--json] # coverage table + JSON dumps

Territory: this module only.  It SUBCLASSES ``rvt.objects.ObjectDecoder``
(no edit to objects.py) and reuses ``rvt.encode.ObjectEncoder`` unchanged.
See ``docs/writer/adocument.md`` for the grammar, the field map and the
authoring implications; ``docs/inbox/adoc-grammar.md`` for the record.
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Optional

from .objects import (DecodeError, DecodedObject, ObjectDecoder, Reader,
                      _State)
from .schema import Schema, load_schema

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides
SAMPLES = (
    "racbasicsampleproject", "rstbasicsampleproject",
    "racadvancedsampleproject", "rstadvancedsampleproject",
    "rmebasicsampleproject", "dach-sample-project",
)

STREAM = "Global/Latest"
ROOT_CLASS = "ADocument"
ROOT_CLASS_ID = 0x1C          # schema anchor (KNOWLEDGE / rvt.schema ANCHORS)
LATEST_PREFIX_VALUE = 5       # u64 stream prefix (rvt.stream_encoders.global_prefix)
DOCUMENT_PID = 1              # the document = archive object index 1
TRAILER = b"\x00\x00\x00\x00"  # constant u32 0 after the object graph
BIG_CONTAINER = 64_000_000    # lifted count cap (steel-model char blob ~2 MB)
APPINFO_SLOT_COUNT = 241      # AppInfoManager.m_appInfoArr fixed length (Revit 2026)

# ---------------------------------------------------------------------------
# Field map (data): what each top-level ADocument member holds.  ``holds``
# is the measured content; ``externalized`` names the OLE stream that
# carries the member's body when it is not inline here.  Order = schema
# order = serialization order.  See docs/writer/adocument.md for evidence.
# ---------------------------------------------------------------------------
FIELD_MAP = [
    {"field": "m_elemTable", "kind": "owned ptr", "serialized_as": "null pointer (i32 0)",
     "externalized": "Global/ElemTable",
     "holds": "the ElementId -> ElemRec table; body lives in its own stream"},
    {"field": "m_appInfoArr", "kind": "container<owned ptr>", "serialized_as": "u32 count 0",
     "externalized": None,
     "holds": "empty in every file; app-infos are reached via m_pAppInfoManager"},
    {"field": "m_oContentTable", "kind": "owned ptr", "serialized_as": "(-1, ContentTable) + deferred body",
     "externalized": "Global/ContentDocuments (document BODIES only)",
     "holds": "ContentTable: m_ContentRecSet = GUID-keyed registry of loaded family/content "
              "documents (ContentKey GUID, author 'Autodesk Revit', creation/mod episode ids, "
              "per-episode load counts); the documents' bytes live in ContentDocuments"},
    {"field": "m_pHostDocument", "kind": "weak ptr", "serialized_as": "u32 1",
     "externalized": None, "holds": "back-reference to the document itself (archive index 1)"},
    {"field": "m_pAppInfoManager", "kind": "owned ptr", "serialized_as": "(-1, AppInfoManager) + deferred body",
     "externalized": None,
     "holds": "AppInfoManager: m_pADoc (weak 1) + m_appInfoArr = the FIXED 241-slot AppInfo "
              "registry (see APPINFO_SLOTS) -- element registries, ES/Forge schema corpus, "
              "numbering memory, worksharing settings, edit-mode managers"},
    {"field": "m_pStyleSettings", "kind": "owned ptr", "serialized_as": "(-1, StyleSettings) + deferred body",
     "externalized": None,
     "holds": "StyleSettings: 9 owned pointers to the style tables (CategoryTable, MaterialTableNew, "
              "PenWidthTableGetter, LinePatternTable, FontTableNew, FillPatternTable, TilePatternTable, "
              "AppearanceAssetTable, StructuralPropertySetTable) whose bodies are ~empty stubs here "
              "(the style ELEMENTS live in Partitions/<N>)"},
    {"field": "m_pHistory", "kind": "owned ptr", "serialized_as": "null pointer (i32 0)",
     "externalized": "Global/History", "holds": "save-episode history; body in its own stream"},
    {"field": "m_pSteelModelInfo", "kind": "owned ptr", "serialized_as": "(-1, SteelModelInfo) + deferred body",
     "externalized": None,
     "holds": "steel (Advance-Steel bridge) model: ext model GUID, hash strings, and the whole "
              "steel model as a char[] blob (2,085,221 bytes in dach; empty elsewhere)"},
    {"field": "m_pPartitionTable", "kind": "owned ptr", "serialized_as": "null pointer (i32 0)",
     "externalized": "Global/PartitionTable", "holds": "workset (partition) table; body in its own stream"},
    {"field": "m_oNobleSecondaryData", "kind": "owned ptr", "serialized_as": "(-1, NOBLE_SecondaryDataStorage) + deferred body",
     "externalized": None,
     "holds": "NOBLE analysis secondary data: appInfoData ('NobleDocWarnings' -> NobleDocWarnings), "
              "m_data = SecondaryDataId -> {ColorFillSecondaryData ...} entries carrying collected primary "
              "ElementIds AND cached colour-fill results (the room-name / area strings), warnings lists"},
    {"field": "m_ownerFamilyId", "kind": "ElementId", "serialized_as": "i64", "externalized": None,
     "holds": "-1 in a project (owning family element id in a family document)"},
    {"field": "m_ownerFamilyContainingGroupId", "kind": "ElementId", "serialized_as": "i64", "externalized": None,
     "holds": "-1 in a project"},
    {"field": "m_devBranchInfo", "kind": "DevBranchInfo (inline value)", "serialized_as": "i32 branchId + i32 syncVersion",
     "externalized": None, "holds": "{1, 2662} = dev branch 1, sync version 2662 (== ADocument schema version)"},
    {"field": "m_groupFile", "kind": "bool", "serialized_as": "u8", "externalized": None, "holds": "false"},
    {"field": "m_corruptDocument", "kind": "bool", "serialized_as": "u8", "externalized": None, "holds": "false"},
    {"field": "m_bIsCoreDocument", "kind": "bool", "serialized_as": "u8", "externalized": None, "holds": "false"},
    {"field": "m_executedUpgrades", "kind": "container<GUIDvalue>", "serialized_as": "u32 count + GUIDs",
     "externalized": None, "holds": "GUIDs of upgrade steps executed on this document (0 in the six samples)"},
    {"field": "m_storedByRevitBuild", "kind": "container<AStringWrapper>", "serialized_as": "u32 count + AStrings",
     "externalized": None,
     "holds": "the Revit builds that have saved the file, oldest first ('Revit 2018 ... : 2017...' -> "
              "'Revit 2026 ... : 20250227_1515(x64)'); 7-12 entries"},
    {"field": "m_oExServicesUsed", "kind": "owned ptr", "serialized_as": "(-1, ExServicesUsed) + deferred body",
     "externalized": None,
     "holds": "ExServicesUsed.m_arrServiceInfo = external-service usage records (empty container in all six)"},
]

# ---------------------------------------------------------------------------
# The 241-slot AppInfo registry (AppInfoManager.m_appInfoArr), Revit 2026.
# Value = the class occupying that slot (majority over the six samples);
# None = slot unused in all six.  227/241 slots carry the identical class
# in every file; 168 are populated in every file; the differing slots are
# lazily-created edit-mode managers / caches (present or None, never a
# different class).  Slot i is serialized as archive pid (2 + index among
# non-null slots) -- i.e. the wave-1 "u32-keyed table, keys 2..181, u32
# 0xf1" was exactly this container (0xf1 = 241 = the slot count).
# ---------------------------------------------------------------------------
APPINFO_SLOTS = [
    "FamilyMgr", "SketchEditMgr", "SymbolIdMgr", "DBViewInfo", None, "SketchPlaneInfo",
    "DBDrawingInfo", "DimSides", None, "AppearanceInfo", None, None, "LightMgr", None,
    "ElementTracking", "PlanTopologyIdInfo", "AlignSides", "NewItemNumber", "LinkedFileInfo",
    None, None, None, "FillPatternTracking", "WallJoinEditMgr", None, None, "ADocWarnings",
    "WallOffsetAppInfo", "CategoryTracking", None, "DetailLevelMgr", "SFCostIdInfo",
    "ElementTrackingData", "MaterialTracking", None, "RefTableInfo", "AllProjectPhasesInfo",
    "PhaseFilterTracking", "PenWidthTableInfo", "JoinTrackerAppInfo", "LinePatternTracking",
    "SiteMgr", "RoomTracking", "SiteSurfaceEditMgr", "ElementGroupAppInfo",
    "AreaMeasureTracking", "LightGroupTracking", "MultiSketchElemEditMgr", "GroupEditModeMgr",
    "Path3dEditMgr", "SubstitutionManager", "ScheduleInstanceTracking",
    "LevelPlanViewTracking", "DatumTracking", "MoribundElemTracking", None,
    "NewElementsVisibilityInfo", "TransientElemSetTracking", "ExternalParamTracking",
    "ConstraintDimTracking", "GroupHelperAppInfo", "UnitsTracking", "SelectionHistory",
    "ViewSheetSetTracking", "PrintSettingsTracking", "RvtLinkTracking", "RvtTargetTracking",
    "ParamBindingTracking", "ProjectParamTracking", "RvtLinkInstTracking",
    "InEditModeInfoMgr", None, "UniqueElementsTracking", "ViewCreationTracking",
    "TempModeInfo", "BrowserOrganizationTracking", "DesignOptionMgr", "TemporaryElements",
    "TemporaryUndoableElements", "DesignOptionSetTracking", "KeepAtLeastOneLevel",
    "BasedOnTracker", "AbsLayoutAppInfo", "AbsSingleCurveTracking", None, "AutoDimOptions",
    None, None, "StructMgr", "CircuitGroupAppInfo", "CircuitGroupEditModeMgr",
    "CopyWatchModeMgr", "APIAppInfo", "RbsMechanicalDisplayAppInfo",
    "RbsSystemNavigatorTracking", "InterferenceReportAppInfo", "OpenLoadedFamsMgr", None,
    None, "AreaReportSettingsTracking", None, "MaterialPhyParamTracking",
    "DBViewTypesForNewLevel", "ImportInstanceTracking", "StructuralElemSetTracking",
    "GCSElemTracking", "PasteEditModeMgr", "AllViewFiltersAppInfo", "KeynoteTableTracking",
    "KeynotingSystemTracking", "RbsSystemInspectorAppInfo", "RbsSystemInspectorEditModeMgr",
    "AllWatchElems", "SFilterEditModeMgr", "ImageInstanceTracking",
    "RbsLayoutPathEditModeMgr", "PreviewTempElementsTracking", None,
    "RebarShapeRecordAppInfo", None, "ZoneAppInfo", "ZoneEditModeMgr", "TilePatternTracking",
    "ZoneSchemeTracking", "ZoneElementTracking", "KickAutoJoinAppInfo",
    "LightGroupEditModeMgr", "StretchableSymMgr", "KickGCSTrackerAppInfo",
    "APIVSTAMacroElemTracking", "LoadCaseElemTracking", "LoadCombinationElemTracking",
    "BeamAnnotationsInfo", None, None, None, None, "RenderRegionTracking",
    "RbsInsulationLiningEditModeMgr", "RbsJustifySlopeRouteEditModeMgr",
    "HalftoneUnderlaySettingsAppInfo", "XRayContext", None, None,
    "StructConnectionTypeTracking", "DynamicUpdateAppInfo", "WorkPlaneViewContextAppInfo",
    "SpatialFieldTracking", None, "PanelScheduleTemplateEditModeMgr",
    "SurfaceConnectorEditModeMgr", "AnalysisDisplayStyleTracking", None,
    "ElemsSetWithCellsTracking", None, None, "PanelScheduleTemplateElementTracking",
    "MEPSystemElemSetTracking", "AssemblyEditModeMgr", "AppearanceAssetTracking",
    "ExportDWGSettingsTracking", "ViewTagTracking", "PointCloudTypeTracking",
    "AnalyticalModelEditModeMgr", "FamilySymbolTracking", "DivisionEditModeMgr", None,
    "WorksharingDisplaySettingsTracking", "PropertySetLibraryTracking",
    "PropertySetElementTracking", "PointCloudInstanceTracking", "ESSchemaStorage",
    "CreateAssemblyViewsInfo", None, "ExportDGNSettingsTracking", "StairsEditModeMgr",
    "AppInfoSystemFamiliesNames", "RailPathEditModeMgr", None, "EStorageTracking",
    "OpenLockControlTracking", "DisplacementEditModeMgr", "GlobalParamTracking",
    "TemporaryViewPropertiesMenu", "ImportedDataEditMgr", "NumberingAppInfo",
    "ExternalResourceErrorAppInfo", None, None, "PropagationFilterData", None,
    "TemporaryViewPropertiesVolatileData", None, "StructConnectivityEditModeMgr", None,
    "NonInteractingTransientElemSetTracking", None, "EnergyAnalysisModelTracker",
    "UserSpecificSettingsTracker", "FabricationConfigurationAppInfo",
    "FabricationPartRoutingEditModeMgr", "MultistoryStairsConnectedLevelsEditModeMgr", None,
    "StructuralConnectionApprovalTypeTracking", "StructuralConnectionHandlerTypeTracking",
    "StructuralConnectionHandlerTracking", None, None,
    "ExternalResourceReferenceUpdateForWorksharingTracker", "SiteLinkTracking",
    "SteelElementsLinksTracker", "TopographyLinkTypeTracking", None,
    "ExportPDFSettingsTracking", None, None, None, "FamSymGlobalComputedSymbolCache",
    "AppInfoExternalLinks", "TemporaryGraphicsManager", "RevisionNumberingSequenceTracking",
    None, "AppInfoElementsAssociations", None, None, None, None, None, None, None,
    "CustomApiGraphicsServerTrackingAppInfo", "FDXExchangeIdAppInfo", None,
    "SmoothToposolidAppInfo", None, "IfcCategoryTemplateTracking", "CustomElementTracking",
    None, "ViewPositionInfo", "ToposolidBooleanSettingAppInfo",
    "AnalyticalAutomationEditModeMgr",
]
assert len(APPINFO_SLOTS) == APPINFO_SLOT_COUNT

# slot indices whose occupancy varies across the six samples (present-or-null);
# the class, when present, is always the one in APPINFO_SLOTS.
APPINFO_OPTIONAL_SLOTS = (23, 66, 83, 106, 110, 111, 141, 165, 177, 181, 183, 191, 201, 217)


# ---------------------------------------------------------------------------
# Reader with a lifted container cap (the ONLY primitive-level difference)
# ---------------------------------------------------------------------------
class ADocReader(Reader):
    """:class:`rvt.objects.Reader` with the runaway-count cap lifted.

    ``SteelModelInfo.m_steelModelLatest`` (a ``char`` container) legitimately
    holds a multi-megabyte steel-model blob; the element-record cap of
    2,000,000 rejects it.  Everything else is inherited unchanged.
    """

    __slots__ = ()

    def count32(self, min_elem: int = 1, what: str = "count") -> int:
        at = self.p
        c = self.u32()
        if c > BIG_CONTAINER or c * max(min_elem, 1) > (self.n - self.p) + 16:
            raise DecodeError(at, f"implausible {what} {c} (remaining {self.n - self.p})")
        return c


# ---------------------------------------------------------------------------
@dataclass
class LedgerEntry:
    """One decoded object body: its byte span + where it hangs in the tree."""
    start: int
    end: int
    class_name: str
    top_field: str            # ADocument.<field> the body descends from
    appinfo: str = ""         # first AppInfo class on the path ('' outside)
    path: str = ""

    @property
    def size(self) -> int:
        return self.end - self.start


class ADocumentDecoder(ObjectDecoder):
    """ObjectDecoder specialised for the document object (Global/Latest).

    Hooks over the base decoder (which stays untouched):

    * pid seed ``{DOCUMENT_PID}`` (= {1}) instead of ``{1, 2}`` -- the
      document is archive object 1, so the FIRST indexed object gets pid 2.
    * :class:`ADocReader` (lifted container cap).
    * a per-body :class:`LedgerEntry` ledger (byte-region attribution).
    """

    def decode_document(self, payload: bytes, class_id: int = ROOT_CLASS_ID,
                        seed_pids: Iterable[int] = (DOCUMENT_PID,)) -> "ADocument":
        """Decode the object bytes (NO leading u16 class id, NO trailer)."""
        name = self.class_name(class_id)
        obj = DecodedObject(class_id, name, {}, 0, len(payload))
        rd = ADocReader(payload)
        state = _State(seen_pids=set(seed_pids))
        queue: deque = deque()
        ledger: list[LedgerEntry] = []
        try:
            if class_id not in self.schema.by_id:
                raise DecodeError(0, f"unknown class id {class_id:#x}")
            obj.value = self._decode_class(rd, class_id, queue, state, name)
            ledger.append(LedgerEntry(0, rd.p, name, "<top-level fields>", "", name))
            while queue:
                pend = queue.popleft()
                obj.n_deferred += 1
                start = rd.p
                cname = self.class_name(pend.class_id)
                sub = self._decode_class(rd, pend.class_id, queue, state,
                                         f"{pend.path}->{cname}")
                ledger.append(_ledger_entry(start, rd.p, cname, pend.path))
                pend.holder[pend.key] = sub
        except DecodeError as e:
            obj.errors.append({"field": state.path, "offset": e.offset, "error": e.msg})
        except (struct.error, IndexError) as e:  # pragma: no cover - safety net
            obj.errors.append({"field": state.path, "offset": rd.p, "error": f"truncated: {e}"})
        obj.consumed = rd.p
        return ADocument(obj, ledger, self)


def _ledger_entry(start: int, end: int, cname: str, path: str) -> LedgerEntry:
    m = re.match(r"ADocument\.(m_[A-Za-z0-9_]+)", path)
    top = m.group(1) if m else "?"
    app = ""
    if "m_appInfoArr[" in path:
        m3 = re.search(r"m_appInfoArr\[\d+\]->([A-Za-z0-9_]+)", path)
        app = m3.group(1) if m3 else cname   # body of the slot object itself
    return LedgerEntry(start, end, cname, top, app, path)


# ---------------------------------------------------------------------------
class ADocument:
    """A decoded document object graph + coverage/introspection helpers."""

    def __init__(self, obj: DecodedObject, ledger: list[LedgerEntry],
                 decoder: ADocumentDecoder):
        self.obj = obj
        self.ledger = ledger
        self.decoder = decoder
        self.trailer: bytes = b""      # set by decode_latest
        self.payload_len: int = obj.total

    # -- basics --------------------------------------------------------------
    @property
    def value(self) -> dict:
        return self.obj.value

    @property
    def errors(self) -> list:
        return self.obj.errors

    @property
    def consumed(self) -> int:
        """Bytes of the object body consumed by the structured decode."""
        return self.obj.consumed

    @property
    def clean(self) -> bool:
        """Full decode: no errors; only the constant trailer left unconsumed."""
        return not self.obj.errors and (
            self.obj.consumed == self.obj.total or self.trailer == TRAILER)

    @property
    def coverage(self) -> dict:
        c, t = self.obj.consumed, self.obj.total
        return {"consumed": c, "total": t,
                "fraction": (c / t) if t else 1.0,
                "errors": len(self.obj.errors),
                "deferred_bodies": self.obj.n_deferred}

    # -- structure -------------------------------------------------------------
    def app_info_manager(self) -> Optional[dict]:
        m = self.value.get("m_pAppInfoManager")
        return m.get("value") if isinstance(m, dict) else None

    def appinfo_array(self) -> list:
        mgr = self.app_info_manager() or {}
        return mgr.get("m_appInfoArr") or []

    def appinfo_slots(self) -> list[Optional[str]]:
        """241 x (class name | None) as serialized in this document."""
        out: list[Optional[str]] = []
        for x in self.appinfo_array():
            if x is None:
                out.append(None)
            elif isinstance(x, dict) and "ptr_class" in x:
                out.append(x["ptr_class"])
            elif isinstance(x, dict) and "backref_pid" in x:
                out.append(f"backref({x['backref_pid']})")
            else:  # pragma: no cover
                out.append("?")
        return out

    def appinfo(self, class_name: str) -> Optional[dict]:
        """Decoded body of the AppInfo of the given class (first match)."""
        for x in self.appinfo_array():
            if isinstance(x, dict) and x.get("ptr_class") == class_name:
                return x.get("value")
        return None

    def slot_deviations(self) -> list[dict]:
        """Slots whose class differs from the canonical APPINFO_SLOTS table."""
        out = []
        for i, cls in enumerate(self.appinfo_slots()):
            canon = APPINFO_SLOTS[i] if i < len(APPINFO_SLOTS) else None
            if cls != canon and not (cls is None and i in APPINFO_OPTIONAL_SLOTS):
                out.append({"slot": i, "class": cls, "canonical": canon,
                            "optional_slot": i in APPINFO_OPTIONAL_SLOTS})
        return out

    # -- byte attribution --------------------------------------------------------
    def bytes_by_top_field(self) -> Counter:
        c: Counter = Counter()
        for e in self.ledger:
            c[e.top_field] += e.size
        return c

    def bytes_by_appinfo(self) -> Counter:
        c: Counter = Counter()
        for e in self.ledger:
            if e.appinfo:
                c[e.appinfo] += e.size
        return c

    # -- content censuses --------------------------------------------------------
    def element_ids(self, node: Any = None) -> list[int]:
        """Positive ElementId-like ints referenced by the graph (id-named keys)."""
        out: list[int] = []
        _collect_ids(self.value if node is None else node, "", out)
        return out

    def element_ids_by_top_field(self) -> dict[str, list[int]]:
        return {k: _ids_of(v) for k, v in self.value.items() if _ids_of(v)}

    def element_ids_by_appinfo(self) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for x in self.appinfo_array():
            if isinstance(x, dict) and "ptr_class" in x:
                ids = _ids_of(x.get("value"))
                if ids:
                    out.setdefault(x["ptr_class"], []).extend(ids)
        return out

    def strings(self, node: Any = None) -> list[str]:
        out: list[str] = []
        _collect_strings(self.value if node is None else node, out)
        return out

    def forge_schema_corpus(self) -> dict:
        """The ESSchemaStorage AppInfo = Autodesk Forge JSON schema corpus."""
        es = self.appinfo("ESSchemaStorage") or {}
        fs = es.get("m_storedForgeSchemas") or []
        ps = es.get("m_storedParameterSchemas") or []
        su = es.get("m_schemaUsageMap") or []
        fb = sum(4 + 2 * len(p.get("first") or "") + 4 + 2 * len(p.get("second") or "")
                 for p in fs)
        pb = sum(4 + 2 * len(p.get("first") or "") + 4 + 2 * len(p.get("second") or "")
                 for p in ps)
        return {"forge_unit_schema_pairs": len(fs), "forge_unit_schema_bytes": fb,
                "parameter_schema_pairs": len(ps), "parameter_schema_bytes": pb,
                "es_schema_usage_entries": len(su),
                "dirty": es.get("m_dirty")}

    def field_holdings(self) -> list[dict]:
        """FIELD_MAP annotated with this document's measured numbers."""
        byfield = self.bytes_by_top_field()
        nobj = Counter(e.top_field for e in self.ledger)
        idsby = self.element_ids_by_top_field()
        out = []
        for fm in FIELD_MAP:
            f = fm["field"]
            row = dict(fm)
            row["deferred_bodies"] = nobj.get(f, 0)
            row["deferred_bytes"] = byfield.get(f, 0)
            v = self.value.get(f)
            row["value_summary"] = _summarize_value(v)
            ids = idsby.get(f) or []
            row["element_id_refs"] = len(ids)
            row["element_id_refs_distinct"] = len(set(ids))
            out.append(row)
        return out

    def summary(self) -> dict:
        """Compact machine-readable summary (the adoc_<sample>.json body)."""
        cov = self.coverage
        slots = self.appinfo_slots()
        ids = self.element_ids()
        byapp = self.element_ids_by_appinfo()
        return {
            "stream": STREAM,
            "framing": "u64 prefix 5 | u16 class 0x1c (ADocument) + object graph "
                       "(parent-first, breadth-first deferred bodies, document = pid 1) | u32 0",
            "coverage": cov,
            "clean": self.clean,
            "trailer_hex": self.trailer.hex(),
            "payload_len": self.payload_len,
            "adocument_version": self.value.get("m_devBranchInfo", {}).get("m_syncVersion"),
            "top_level": {k: _summarize_value(v) for k, v in self.value.items()},
            "bytes_by_top_field": self.bytes_by_top_field().most_common(),
            "top_appinfo_by_bytes": self.bytes_by_appinfo().most_common(30),
            "appinfo_slot_count": len(slots),
            "appinfo_populated": sum(1 for s in slots if s),
            "appinfo_slots": slots,
            "appinfo_slot_deviations": self.slot_deviations(),
            "forge_schema_corpus": self.forge_schema_corpus(),
            "element_id_refs": {"total": len(ids), "distinct": len(set(ids))},
            "top_appinfo_by_element_id_refs": sorted(
                ((k, len(v), len(set(v))) for k, v in byapp.items()),
                key=lambda t: -t[1])[:20],
            "stored_by_revit_build": [x.get("m_str") if isinstance(x, dict) else x
                                      for x in (self.value.get("m_storedByRevitBuild") or [])],
        }


# ---------------------------------------------------------------------------
# tree utilities
# ---------------------------------------------------------------------------
_ID_KEY_DENY = {"m_devBranchId", "m_docNum", "m_appInfoType", "m_dataType"}


def _collect_ids(v: Any, key: str, out: list) -> None:
    if isinstance(v, dict):
        for k, x in v.items():
            _collect_ids(x, k, out)
    elif isinstance(v, list):
        for x in v:
            _collect_ids(x, key, out)
    elif isinstance(v, int) and not isinstance(v, bool):
        if v > 0 and key not in _ID_KEY_DENY and \
                ("Id" in key or key.endswith("id64") or key == "m_id"):
            out.append(v)


def _ids_of(v: Any) -> list[int]:
    out: list[int] = []
    _collect_ids(v, "", out)
    return out


def _collect_strings(v: Any, out: list) -> None:
    if isinstance(v, dict):
        for x in v.values():
            _collect_strings(x, out)
    elif isinstance(v, list):
        for x in v:
            _collect_strings(x, out)
    elif isinstance(v, str) and v:
        out.append(v)


def _summarize_value(v: Any, maxitems: int = 5) -> Any:
    """Value summary: scalars verbatim; lists as {count, first N}; pointers by class."""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v if len(v) <= 80 else v[:77] + "..."
    if isinstance(v, list):
        return {"count": len(v), "first": [_summarize_value(x, 3) for x in v[:maxitems]]}
    if isinstance(v, dict):
        if "ptr_class" in v:
            body = v.get("value")
            keys = list(body.keys()) if isinstance(body, dict) else None
            out = {"->": v["ptr_class"], "pid": v.get("pid")}
            if keys is not None:
                out["fields"] = {k: _summarize_value(body[k], 3) for k in keys[:8]}
                if len(keys) > 8:
                    out["more_fields"] = len(keys) - 8
            return out
        if "weakref" in v:
            return {"weakref": v["weakref"]}
        if "backref_pid" in v:
            return {"backref": v["backref_pid"]}
        if "classref" in v:
            return {"classref": v["classref"]}
        keys = list(v.keys())
        out = {k: _summarize_value(v[k], 3) for k in keys[:6]}
        if len(keys) > 6:
            out["<more>"] = len(keys) - 6
        return out
    return repr(v)


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------
_DECODER: Optional[ADocumentDecoder] = None


def get_decoder(schema: Optional[Schema] = None) -> ADocumentDecoder:
    """A cached ADocumentDecoder (schema parse is the expensive part)."""
    global _DECODER
    if schema is not None:
        return ADocumentDecoder(schema)
    if _DECODER is None:
        _DECODER = ADocumentDecoder(load_schema())
    return _DECODER


def decode_latest(payload: bytes, decoder: Optional[ADocumentDecoder] = None) -> ADocument:
    """Decode an inflated ``Global/Latest`` payload (prefix already stripped).

    ``payload`` = ``u16 class_id (0x1c)`` + ADocument object + ``u32 0``.
    Returns an :class:`ADocument`; ``.trailer`` holds the bytes after the
    structured decode (the 4-byte zero constant on a clean file).
    """
    if len(payload) < 6:
        raise DecodeError(0, "Global/Latest payload too short")
    dec = decoder or get_decoder()
    class_id = struct.unpack_from("<H", payload, 0)[0]
    adoc = dec.decode_document(payload[2:], class_id=class_id)
    adoc.trailer = payload[2 + adoc.consumed:]
    adoc.payload_len = len(payload)
    adoc.root_class_id = class_id
    return adoc


def open_document_object(path: str, decoder: Optional[ADocumentDecoder] = None) -> ADocument:
    """Open a ``.rvt`` and decode its Global/Latest ADocument graph."""
    from .container import open_rvt
    doc = open_rvt(path)
    try:
        payload = doc.inflate(STREAM, 0)
    finally:
        doc.close()
    return decode_latest(payload, decoder)


def encode_latest(value_or_doc: Any, decoder: Optional[ADocumentDecoder] = None,
                  trailer: bytes = TRAILER, class_id: int = ROOT_CLASS_ID) -> bytes:
    """Serialize an ADocument value tree back to a Global/Latest payload.

    Inverse of :func:`decode_latest` (byte-identical on all six samples):
    ``u16 class_id + rvt.encode.ObjectEncoder.encode_object(...) + trailer``.
    Accepts an :class:`ADocument` (uses its own trailer) or a value dict.
    """
    from .encode import ObjectEncoder
    if isinstance(value_or_doc, ADocument):
        value = value_or_doc.value
        trailer = value_or_doc.trailer or trailer
        class_id = getattr(value_or_doc, "root_class_id", class_id)
    else:
        value = value_or_doc
    enc = ObjectEncoder(decoder=decoder or get_decoder())
    return struct.pack("<H", class_id) + enc.encode_object(class_id, value) + trailer


def latest_logical_stream(payload: bytes, level: int = 3) -> bytes:
    """Frame a payload as the complete logical Global/Latest stream
    (8-byte prefix + gzip member) using the proven stream encoder."""
    from .stream_encoders import wrap_global_stream
    return wrap_global_stream(STREAM, payload, level=level)


def dump_json(adoc: ADocument, path: str, sample: str = "?") -> str:
    """Write the summary JSON (values summarized: counts, first 5 items)."""
    body = {"sample": sample, **adoc.summary()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(body, fh, indent=1, default=str)
    return path


# ---------------------------------------------------------------------------
# writing: put an (authored) ADocument back into a .rvt
# ---------------------------------------------------------------------------
def write_with_latest(src_rvt: str, out_rvt: str, payload: bytes) -> dict:
    """Copy ``src_rvt`` to ``out_rvt`` with Global/Latest replaced.

    ``payload`` is the full Latest payload (``encode_latest`` output:
    ``u16 class + object + u32 0``).  Compression + prefix + CRCIO page
    framing use the proven encoders; every other stream is copied verbatim.
    Returns a small report.
    """
    import dataclasses
    from . import ecc
    from .cfb_writer import write_cfb
    from .roundtrip import read_entries
    from .stream_encoders import wrap_global_stream
    logical = wrap_global_stream(STREAM, payload, level=3)
    framed = ecc.frame_stream(logical)
    entries = read_entries(src_rvt)
    n = 0
    out_entries = []
    for e in entries:
        if e.entry_type == "stream" and e.path == STREAM:
            out_entries.append(dataclasses.replace(e, data=framed))
            n += 1
        else:
            out_entries.append(e)
    if n != 1:
        raise RuntimeError(f"expected exactly one {STREAM} in {src_rvt}, replaced {n}")
    write_cfb(out_rvt, out_entries)
    return {"out": out_rvt, "payload": len(payload), "logical": len(logical),
            "framed": len(framed)}


# ---------------------------------------------------------------------------
# authoring transforms over a decoded ADocument value tree (proof ladder).
# Each returns a NEW value dict (deep copy) and touches only the members
# named in FIELD_MAP / APPINFO_SLOTS -- the raw material for the encoder
# stream's "our own document object".
# ---------------------------------------------------------------------------
def _deepcopy(v):
    return json.loads(json.dumps(v))


def _appinfo_body(value: dict, class_name: str) -> Optional[dict]:
    mgr = (value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def transform_build_list(value: dict, builds: list[str]) -> dict:
    """A1: replace m_storedByRevitBuild (the 'saved by' build strings)."""
    v = _deepcopy(value)
    v["m_storedByRevitBuild"] = [{"m_str": s} for s in builds]
    return v


def transform_drop_forge_corpus(value: dict) -> dict:
    """A2: empty ESSchemaStorage's two Forge JSON corpora (unit/spec schemas
    + parameter/spec-group schemas) -- the ~1.3 MB of Autodesk-authored
    schema documents the audit flagged."""
    v = _deepcopy(value)
    es = _appinfo_body(v, "ESSchemaStorage")
    if es is not None:
        es["m_storedForgeSchemas"] = []
        es["m_storedParameterSchemas"] = []
    return v


def transform_scrub_sample_names(value: dict) -> dict:
    """A3: drop the sample project's own naming: NewItemNumber's last-used
    sheet/assembly names, per-user worksharing settings, and the NOBLE
    colour-fill caches (which carry the sample's room names)."""
    v = _deepcopy(value)
    nin = _appinfo_body(v, "NewItemNumber")
    if nin is not None:
        nin["m_items"] = []
    ws = _appinfo_body(v, "WorksharingDisplaySettingsTracking")
    if ws is not None:
        ws["m_userToSettingsMap"] = []
    noble = (v.get("m_oNobleSecondaryData") or {}).get("value")
    if noble is not None:
        noble["m_data"] = []
        noble["m_primary2SecondaryDataIdMap"] = []
    return v


def transform_empty_content_table(value: dict) -> dict:
    """A4: empty ContentTable.m_ContentRecSet -- the loaded-family/content
    registry (52 'Autodesk Revit'-authored records in the rst lineage) --
    to match a document whose Global/ContentDocuments carries no bodies."""
    v = _deepcopy(value)
    ct = (v.get("m_oContentTable") or {}).get("value")
    if ct is not None:
        ct["m_ContentRecSet"] = []
    return v


PROOF_LADDER = [
    # (tag, description, transform-chain) -- built on the genesis G0.rvt
    ("A0", "control: Global/Latest decoded->re-encoded (payload byte-identical, "
           "recompressed by us)", []),
    ("A1", "authored top-level edit: m_storedByRevitBuild = one string of ours "
           "(different bytes and length)", ["builds"]),
    ("A2", "A1 + Autodesk Forge JSON corpora EMPTIED (ESSchemaStorage forge/"
           "parameter schema pairs -> 0; drops ~1.3 MB / ~84 % of the stream)",
     ["builds", "forge"]),
    ("A3", "A2 + sample naming scrubbed (NewItemNumber names, worksharing user "
           "map, NOBLE colour-fill caches = the sample's room names)",
     ["builds", "forge", "names"]),
    ("A4", "A3 + ContentTable.m_ContentRecSet emptied (52 'Autodesk Revit' content "
           "records; G0 has no family documents)",
     ["builds", "forge", "names", "content"]),
]


def build_proof_files(src_rvt: str = os.path.join(ROOT, "experiments", "genesis", "G0.rvt"),
                      out_dir: str = os.path.join(ROOT, "experiments", "genesis", "latest"),
                      builds: Optional[list[str]] = None) -> list[dict]:
    """Emit the A0-A3 acceptance-candidate files (see PROOF_LADDER)."""
    from .container import open_rvt
    builds = builds or ["tekton genesis (Revit 2026 / 2662)"]
    doc = open_rvt(src_rvt)
    payload = doc.inflate(STREAM, 0)
    doc.close()
    adoc = decode_latest(payload)
    if not adoc.clean:
        raise RuntimeError(f"source ADocument does not decode cleanly: {adoc.errors[:1]}")
    os.makedirs(out_dir, exist_ok=True)
    out = []
    stem = os.path.splitext(os.path.basename(src_rvt))[0]
    for tag, desc, chain in PROOF_LADDER:
        value = adoc.value
        if "builds" in chain:
            value = transform_build_list(value, builds)
        if "forge" in chain:
            value = transform_drop_forge_corpus(value)
        if "names" in chain:
            value = transform_scrub_sample_names(value)
        if "content" in chain:
            value = transform_empty_content_table(value)
        new_payload = encode_latest(value) if chain else encode_latest(adoc)
        # self-check: what we wrote must decode cleanly and match the tree
        back = decode_latest(new_payload)
        ok = back.clean and back.value == value
        path = os.path.join(out_dir, f"{stem}_{tag}.rvt")
        rep = write_with_latest(src_rvt, path, new_payload)
        rep.update({"tag": tag, "desc": desc, "self_decode_ok": ok,
                    "identical_to_source": new_payload == payload})
        out.append(rep)
    return out


# ---------------------------------------------------------------------------
# CLI: coverage report across the corpus
# ---------------------------------------------------------------------------
def coverage_report(samples: Iterable[str] = SAMPLES, write_json: bool = False,
                    json_dir: Optional[str] = None) -> list[dict]:
    from .container import open_rvt
    dec = get_decoder()
    rows = []
    for s in samples:
        path = os.path.join(ROOT, "samples", f"{s}.rvt")
        t0 = time.time()
        doc = open_rvt(path)
        payload = doc.inflate(STREAM, 0)
        prefix = doc.prefix(STREAM)
        doc.close()
        adoc = decode_latest(payload, dec)
        # round-trip proof
        re_bytes = encode_latest(adoc, dec)
        rt = re_bytes == payload
        cov = adoc.coverage
        rows.append({"sample": s, "payload": len(payload),
                     "consumed": cov["consumed"] + 2, "trailer": adoc.trailer.hex(),
                     "fraction": (cov["consumed"] + 2 + len(adoc.trailer)) / len(payload)
                                 if not adoc.errors else cov["consumed"] / len(payload),
                     "errors": cov["errors"], "deferred": cov["deferred_bodies"],
                     "prefix": prefix.hex(), "roundtrip_exact": rt,
                     "slots_populated": sum(1 for x in adoc.appinfo_slots() if x),
                     "slot_deviations": len(adoc.slot_deviations()),
                     "secs": round(time.time() - t0, 2)})
        if write_json:
            out = os.path.join(json_dir or os.path.join(ROOT, "experiments", "genesis", "latest"),
                               f"adoc_{s}.json")
            dump_json(adoc, out, s)
    return rows


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    samples = args if args else list(SAMPLES)
    write_json = "--json" in flags
    rows = coverage_report(samples, write_json=write_json)
    print(f"{'sample':28s} {'payload':>9s} {'consumed':>9s} {'cov%':>8s} "
          f"{'err':>4s} {'deferred':>8s} {'trailer':>8s} {'RT-exact':>9s} "
          f"{'slots':>5s} {'dev':>3s} {'sec':>5s}")
    for r in rows:
        print(f"{r['sample']:28s} {r['payload']:9d} {r['consumed']:9d} "
              f"{100 * r['fraction']:8.4f} {r['errors']:4d} {r['deferred']:8d} "
              f"{r['trailer']:>8s} {str(r['roundtrip_exact']):>9s} "
              f"{r['slots_populated']:5d} {r['slot_deviations']:3d} {r['secs']:5.1f}")
    if write_json:
        print(f"\nwrote experiments/genesis/latest/adoc_<sample>.json for {len(rows)} sample(s)")
    if "--proofs" in flags:
        print("\nproof ladder (built on experiments/genesis/G0.rvt):")
        for rep in build_proof_files():
            print(f"  {rep['tag']}: {rep['out']}  payload={rep['payload']:,} "
                  f"self_decode_ok={rep['self_decode_ok']} "
                  f"identical_to_source={rep['identical_to_source']}\n      {rep['desc']}")
    if "--fields" in flags:
        for r in rows:
            adoc = open_document_object(os.path.join(ROOT, "samples", f"{r['sample']}.rvt"))
            print(f"\n=== {r['sample']} field holdings ===")
            for fh in adoc.field_holdings():
                print(f"  {fh['field']:32s} bodies={fh['deferred_bodies']:4d} "
                      f"bytes={fh['deferred_bytes']:9d} idrefs={fh['element_id_refs_distinct']:6d}  "
                      f"{fh['kind']}")
            print("  --- top appinfos by bytes ---")
            for k, n in adoc.bytes_by_appinfo().most_common(12):
                print(f"    {k:40s} {n:9d}")
    return 0 if all(r["roundtrip_exact"] and r["errors"] == 0 for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
