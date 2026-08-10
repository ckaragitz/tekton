"""provenance.py — the AUTHORSHIP PROVENANCE LEDGER (the P0 cutover-gate instrument).

For EVERY element of a document, classify who authored it, then roll the
verdicts up into the CATEGORIES OF THING THAT MATTER LEGALLY (families,
system-family types, view templates, object styles, patterns, text/dimension
types, annotation symbols, parameter definitions, phases, settings ...).

Why this exists: ``docs/product/content-strategy.md`` sets the P0 shipping
gate — nothing ships until the base document contains NO Autodesk-authored
expression (not just "no families": also wall/duct/pipe/conduit types, view
templates, object styles, patterns, text styles, annotation symbols, shared
parameter definitions, keynote / load-classification settings).  Until now
that gate was a slogan.  This module makes it CHECKABLE: run it on a
candidate genesis file and G1 passes iff it reports ZERO ``autodesk-sample``
and ZERO ``transitive-cloned`` in the expression-bearing categories.

Provenance classes
------------------
For a candidate document C and a reference Autodesk sample B (the "baseline"
C descends from):

* ``autodesk-sample``   element id present in B with the same class AND the
                        same seq-102 payload (and seq-101/103) -> byte-for-byte
                        Autodesk's original object.
* ``ours-modified``     id present in B with the same class but a payload that
                        no longer matches -> a sample element WE edited (still
                        derived expression; the geometry lineage is Autodesk's).
* ``ours-created``      id NOT in B and above B's original id watermark
                        (``IdentifierSource.m_last``), with no clone lineage
                        into sample expression -> genuinely ours.
* ``transitive-cloned`` created (as above) but derived from a sample element:
                        either it REFERENCES a sample-authored definition
                        (its family symbol / wall type / cable type ...) or its
                        serialized body is a STRUCTURAL CLONE of a sample
                        specimen (shingle similarity >= threshold).  Cloned
                        geometry / parameters of an Autodesk family instance is
                        still derived expression until the FAMILY is ours —
                        this is the honest state of everything our machinery
                        creates today.
* ``unmatched``         id not in B and NOT above the watermark, or a class
                        mismatch at the same id -> wrong baseline / renumbered;
                        never passes a gate.
* ``unbaselined``       no baseline supplied — nothing can be attributed.
* ``ours-composed``     (only when B is OUR pinned composed genesis base and
                        the caller passes its authorship census as a
                        :class:`ComposedBaseline` — issue #143; a candidate
                        that merely DESCENDS from the pin is ledgered against
                        the pin itself, #284) id present in B OUTSIDE the
                        census's residue set: ours by composition, identical
                        or edited.  What is TRUSTED here, exactly: the residue
                        set of ``rvt/frontdoor/assets/genesis_census.json``,
                        which ``tools/genesis_census.py`` derives from the
                        certified rung reports by one law -- a slot of B is
                        ours iff some certified rung's ``byte_delta`` changed
                        its record AND that rung's ``landed_slots`` emitted an
                        object there ("changed => landed", asserted per rung;
                        on 2026 also reproduced id for id by a byte compare
                        against the ancestor).  This module does not re-verify
                        that against the ancestor's bytes (they are not
                        shipped); it applies the set.  B's RESIDUE ids (no rung
                        changed them: still the ancestor's serialization) keep
                        the ``autodesk-sample`` / ``ours-modified`` verdicts BY
                        THIS MODULE'S OWN BYTE LAW against B, and only THEY
                        seed clone lineage for created elements.  No census
                        (stale asset, foreign base) => no ``ours-composed``:
                        everything inherited is ledgered as the sample's.

Embedded family DOCUMENTS (partition save units 1..k) are ledgered as units:
a unit whose separator GUID exists in the baseline is an ``autodesk-sample``
family document; a unit GUID unknown to the baseline is ``ours-created``.

Public API (v1, unchanged)::

    provenance(doc, baseline=None, *, examples=3) -> dict     # the report
    classify_elements(doc, baseline) -> dict[eid] -> ElementVerdict
    legal_category(doc, eid) -> category key
    gate_G1(report) -> {"passes": bool, "blocking": [...]}

v2 (2026-08-03, after the genesis audit — see the "PROVENANCE LEDGER v2"
section at the bottom of this module): the v1 ledger walked the ElemTable
only, against ONE baseline, and reported "0 autodesk-sample" on a file whose
BYTES were ~94 % Autodesk.  v2 adds, without changing v1:

    provenance(doc, baselines=[...], streams=True, strings=True, identity=True)
    content_units(path) / stream_ledger(path, corpus)   # byte-weighted streams
    classify_elements_multi(doc, [b1, b2, ...])        # union + attribution
    resource_ref_report(path, doc)                     # Autodesk resource ids
    identity_report(path, corpus)                      # rvt.identity policy
    gate_G1(report)  # now: elements AND expression-stream bytes AND refs AND
                     # identity; Formats/Latest = counsel C4; certifies_G1 only
                     # when all four layers ran

CLI: ``tools/provenance.py FILE.rvt --baseline all --streams --json out.json``.
"""
from __future__ import annotations

import contextlib
import os
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import AbstractSet, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from . import inventory as inv

# ---------------------------------------------------------------------------
# provenance classes
# ---------------------------------------------------------------------------
P_SAMPLE = "autodesk-sample"
P_MODIFIED = "ours-modified"
P_CREATED = "ours-created"
P_CLONED = "transitive-cloned"
P_UNMATCHED = "unmatched"
P_UNBASELINED = "unbaselined"
#: inherited (identical or edited) from OUR pinned composed genesis base at a
#: slot our constructors re-authored in place (a certified rung changed its
#: record AND landed an object there -- tools/genesis_census.py's law) --
#: ours by composition, NOT Autodesk-derived.  Only ever assigned when the
#: caller supplies the base's authorship census (a :class:`ComposedBaseline`,
#: rvt.frontdoor.census, #143), which is trusted as given; the residue ids of
#: that census keep the sample verdicts below.
P_COMPOSED = "ours-composed"

PROVENANCES = (P_SAMPLE, P_MODIFIED, P_CREATED, P_CLONED, P_COMPOSED,
               P_UNMATCHED, P_UNBASELINED)

#: verdicts that carry Autodesk-derived expression (block the G1 gate when
#: they occur in an expression-bearing category)
DERIVED = frozenset({P_SAMPLE, P_MODIFIED, P_CLONED})


@dataclass(frozen=True)
class ComposedBaseline:
    """The baseline is OUR pinned composed genesis base ``pinned_id``
    (rvt.frontdoor.census, #143 / #284): ``residue_ids`` are ITS slots no
    certified rung changed (still the Autodesk ancestor's serialization) --
    ledgered exactly as sample elements, and alone seeding clone lineage;
    every other baseline slot is ours by composition (a certified rung
    changed its record and landed an object there).  The set is the census
    asset's, derived by tools/genesis_census.py and applied here as given."""
    residue_ids: FrozenSet[int]
    pinned_id: Optional[str] = None

# ---------------------------------------------------------------------------
# the legal category taxonomy
# ---------------------------------------------------------------------------
# key -> (label, expression_bearing, description)
# expression_bearing == the category is named by the P0 gate (content-strategy):
# a candidate genesis file must report ZERO autodesk-sample / transitive-cloned
# elements in every expression-bearing category to pass G1.
CATEGORIES: Dict[str, Tuple[str, bool, str]] = {
    "embedded-family-documents": (
        "Embedded family documents (save units)", True,
        "each embedded save unit 1..k is a complete family DOCUMENT (an .rfa) stored inside the project"),
    "loadable-families": (
        "Loadable families (host side)", True,
        "Family / FamilySurrogate / FamSymSurrogate — the host records for loaded .rfa content"),
    "family-types-symbols": (
        "Family types (symbols)", True,
        "FamilySymbol and Symbol descendants of model categories — the placeable types"),
    "system-family-types": (
        "System-family types", True,
        "wall / floor / roof / ceiling / duct / pipe / conduit / cable-tray types, curtain systems, stairs / railing types (HostObjAttr + *Type)"),
    "views-and-templates": (
        "Views & view templates", True,
        "views, view templates, sheets, viewports, schedules, browser organization"),
    "object-styles": (
        "Object styles (categories / graphics styles)", True,
        "CategoryElem, GStyleElem, ModelGraphicsStyle — subcategories and their graphics"),
    "patterns-materials": (
        "Fill / line patterns, materials, appearance assets", True,
        "FillPatternElem, LinePatternElem, MaterialElem, AppearanceAssetElem, tile / conceptual types, fonts, pen tables"),
    "text-dimension-types": (
        "Text / dimension / arrowhead / annotation types", True,
        "TextNoteAttributes, DimensionStyle, LeaderStyle (arrowheads), FilledRegionAttributes, spot / section / callout styles"),
    "annotation-symbols-titleblocks": (
        "Annotation symbols & title blocks", True,
        "family symbols / families in annotation categories: tags, title blocks, generic annotation, heads, view titles"),
    "parameter-definitions": (
        "Shared / project parameter definitions", True,
        "ParamElemExternal (shared), ParamElemProject, ParamElemFamily, ParamBinding, PropertySetElement"),
    "phases-design-options": (
        "Phases / design options / revisions", True,
        "ProjectPhase, PhaseFilterElem, DesignOption(Set), revision sequences"),
    "project-info-settings": (
        "Project info & settings elements", True,
        "ProjectInfo, UnitsElem, keynote table, ElectricalSetting, all *Settings singletons"),
    "mep-electrical-definitions": (
        "MEP / electrical definition tables", True,
        "voltage & distribution-system types, demand factors, load classifications, wire / pipe / duct material tables, panel schedule templates"),
    "datums": (
        "Datums (levels / grids / reference planes)", False,
        "Level, Grid, RefPlane, extents — near-trivial numeric definitions (reported, not gated)"),
    "placed-model-content": (
        "Placed model content (sample geometry)", True,
        "instances, walls, floors, ceilings, MEP curves, rooms/spaces/zones, circuits, rebar, loads — the sample's model"),
    "view-annotation-2d-content": (
        "View-owned 2D / annotation content", True,
        "detail lines, text notes, dimensions, tags, filled regions, sketches, legend components"),
    "internal-bookkeeping": (
        "Internal bookkeeping (regenerated by Revit)", False,
        "trackers, hubs, regen splitters, warnings, caches — machine state, not expression"),
    "unmapped": (
        "UNMAPPED classes (extend the taxonomy)", True,
        "classes the taxonomy does not yet name — treated as expression-bearing until reviewed"),
}

CATEGORY_ORDER = list(CATEGORIES)

#: categories a CREATED element may derive its expression from — a reference
#: into an autodesk-sample element of one of these categories, or a structural
#: clone of one, makes the created element ``transitive-cloned``.
CLONE_LINEAGE_CATEGORIES = frozenset({
    "loadable-families", "family-types-symbols", "system-family-types",
    "views-and-templates", "object-styles", "patterns-materials",
    "text-dimension-types", "annotation-symbols-titleblocks",
    "parameter-definitions", "mep-electrical-definitions", "unmapped",
})

# --- explicit class -> category ------------------------------------------
_EXPLICIT: Dict[str, str] = {}


def _reg(cat: str, names: Iterable[str]) -> None:
    for n in names:
        _EXPLICIT[n] = cat


_reg("loadable-families", ["Family", "FamilySurrogate", "FamSymSurrogate",
                           "NestedFamSymRefElem", "FamilyDocument"])
_reg("family-types-symbols", ["FamilySymbol", "SysMullionFamSym", "SysPanelFamSym",
                              "BaseRailingSym", "StairsSym", "StairsTriserSymbol",
                              "RvtLinkSymbol", "MasterImportSymbol", "ImageSymbol",
                              "ColorFillSymbol", "ComponentRepeaterSlotSpecialType",
                              "SlaveSymbolTrackerElem"])
_reg("system-family-types", [
    "BasicWallType", "StackedWallType", "NewCurtainWallType", "CurtainRoofAttributes",
    "FloorAttributes", "RoofAttributes", "RoofSoffitType", "FasciaAttr", "GutterAttr",
    "EdgeSlabAttr", "CompoundCeilingType", "ContFootingType", "BuildingPadType",
    "ToposolidType", "CurtaSystemAttr", "CorniceAttr", "RevealAttr",
    "StairsType", "StairsRunType", "StairsLandingType", "StairsPathType",
    "StairsSupportType", "StairsAttributes", "StairsRailingAttr", "HandRailType",
    "TopRailType", "RampAttributes", "JoistSystemAttr", "ElementGroupType",
    "RbsConduitType", "RbsCableTrayType", "RbsPipeType", "RbsFlexPipeType",
    "AbsDuctType", "AbsFlexDuctType", "RbsDuctInsulationType", "RbsDuctLiningType",
    "RbsPipeInsulationType", "RbsWireType", "RbsCableType", "RbsPipingSystemType",
    "RbsHvacSystemType", "MEPSystemZoneType", "MEPSystemZoneElementType",
    "MechanicalEquipmentSetType", "MEPAnalyticalConnectionElementType",
    "AnalyticalLinkType", "LineLoadType", "AreaLoadType", "PointLoadType",
    "AreaReinforcementType", "PathReinforcementType", "RebarBarType", "RebarShape",
    "RebarHookType", "RebarBendingDetailType", "RebarCoverType", "CoverType",
    "FabricSheetType", "FabricAreaType", "FabricWireType", "CustomElementType",
    "AssemblyType", "DivisionProfile", "GraphSchedColumnType",
])
_reg("views-and-templates", [
    "DBViewType", "DBDrawing", "Viewer", "Viewer3d", "Section", "InteriorElev",
    "InteriorElevArrow", "Viewport", "GCSViewport", "ScheduleInstance",
    "PanelScheduleView", "PanelScheduleTemplate", "LevelRoomPlan", "ViewSheetSet",
    "BrowserOrganization", "RbsDbViewSystemNavigator", "SunAndShadowSettings",
    "GraphSchedColumnTable", "ViewReferencing", "InitialViewSettings",
    "ParameterFilterElement", "ReferenceViewerAttributes", "ImageHolder",
    "AreaSchemePlanTopologies", "AllPlanTopologies", "ColorFillSchema",
    "ColorFillLegend", "PrintSettings", "Matchline",
])
_reg("object-styles", ["CategoryElem", "GStyleElem", "ModelGraphicsStyle",
                        "SketchGridAppearanceParentElem",
                        "RvtLinkInstanceAppearanceParentElem"])
_reg("patterns-materials", [
    "FillPatternElem", "LinePatternElem", "MaterialElem", "AppearanceAssetElem",
    "TilePatternType", "ConceptualConstructionType", "ConceptualSurfaceType",
    "ListConceptualSurfaceTypes", "LightSchemeElement", "PenWidthTableElem",
    "FontElem", "AssemblyCodeTable", "DivisionRule",
])
_reg("text-dimension-types", [
    "TextNoteAttributes", "TagNoteAttributes", "LeaderStyle", "DimensionStyle",
    "SpotElevationStyle", "SectionAttributes", "InteriorElevAttributes",
    "FilledRegionAttributes", "LevelAttributes", "GridAttributes",
    "ViewportAttributes", "ContourLabelingAttributes", "Text3dAttrSymbol",
    "MultiReferenceAnnotationType", "RevisionCloudAttr", "RepeatingDetailAttributes",
    "CutMarkType", "CalloutTag", "ConstructionSetProject", "PropertyAttr",
])
_reg("parameter-definitions", [
    "ParamElemExternal", "ParamElemProject", "ParamElemFamily",
    "ParamElemElectricalLoadClassification", "ParamBinding", "PropertySetElement",
    "PropertySetLibrary", "ExternalParamLock", "KeynoteTable", "KeynotingSystem",
])
_reg("phases-design-options", [
    "ProjectPhase", "AllProjectPhases", "PhaseFilterElem", "DesignOption",
    "DesignOptionSet", "ProjectRevision", "AllProjectRevisions",
    "RevisionNumberingSequence", "NumberingSchema",
])
_reg("project-info-settings", [
    "ProjectInfo", "UnitsElem", "TrueNorth", "BasePoint", "GeoSite", "GeoLocation",
    "ActiveGeoLocationTrackingElement", "CoordinateSystemDisplayElem",
    "WorksharingViewModeSettings", "StructSettingsElem", "ElectricalSetting",
    "WallJoinDefaultSetting", "AreaSettingsElem", "AreaReportSettingsElem",
    "EnergyDataSettings", "HalftoneUnderlaySettings", "DaylightSourceIdSet",
    "MultipleValuesIndicationSettings", "RouteAnalysisSettings",
    "ReinforcementSettings", "StructuralConnectionSettings",
    "CircuitNamingTypeSetting", "DefaultDivideSettings", "STEPExportSettings",
    "SSEPointVisibilitySettings", "MEPHiddenLineSettingsElem", "AreaMeasureElem",
    "ZoneScheme", "CopyWatchProperties", "DataStorage",
])
_reg("mep-electrical-definitions", [
    "RbsVoltageType", "RbsDistributionSysType", "ElectricalDemandFactorDefinition",
    "ElectricalLoadClassification", "RbsWireMaterialType", "RbsWireInsulationType",
    "RbsWireTemperatureRatingType", "RbsFluidType", "RbsPipeMaterialType",
    "RbsPipeConnectionType", "RbsPipeScheduleType", "RbsPipeSizesElem", "PipeSegment",
    "ConduitStandardType", "LoadNatureElem", "LoadCaseElem",
    "HVACLoadSpaceTypeElem", "HVACLoadBuildingTypeElem", "HVACLoadScheduleElem",
    "BuildingOperatingYearSchedule", "StructConnectionType",
    "RbsDuctSizesElem", "RbsWireSizesElem", "ConduitSizesElem", "CableTraySizesElem",
    "FabricationSettings", "FabricationSettingsElement", "FabricationServiceSettings",
])
_reg("datums", ["Level", "Grid", "MultiSegmentGrid", "GridChain", "RefPlane",
                "ExtentElem", "GridType", "LevelType"])
_reg("placed-model-content", [
    "FamilyInstance", "ImportInstance", "RvtLinkInstance", "SWall", "VWall",
    "FaceWall", "Floor", "Ceiling", "Toposolid", "RoofBase", "RoomElem",
    "ZoneElement", "RbsElectricalSystem", "RbsHvacSystem", "RbsPipingSystem",
    "MEPSystemZoneElement", "Rebar", "RebarInSystem", "RebarSystem",
    "AnalyticalMember", "AnalyticalPanel", "LineLoad", "AreaLoad", "PointLoad",
    "BoundaryConditions", "StairsElement", "StairsRun", "StairsSupport",
    "StairsPathElement", "Stairs", "BaseRailing", "DPart", "PartMaker",
    "JoistSystem", "FormElem", "MassLevelData", "CustomElement", "ElementGroup",
    "ContFooting", "Toposurface", "BuildingPad", "PathRein", "AreaRein",
    "FabricArea", "FabricSheet", "Truss", "CurtainGridLine", "CurtaSystem",
    "TopographySurface", "PointLoad", "InternalPointLoad", "InternalLineLoad",
    "InternalAreaLoad", "AssemblyInstance", "Cornice", "Reveal", "Fascia",
    "Gutter", "SlabEdge", "RoofSoffit", "SiteSurface", "SWallRectOpening",
    "ShaftOpening", "ComplexOpening", "Opening", "TopRail", "HandRail",
    "StairsLanding", "MultistoryStairs", "WallSweep", "SweepHost", "Ramp",
    "TrussElement", "StructuralConnectionHandler", "RebarContainer",
    "FaceSplitter", "Property", "PropertyLineSegment", "Path3d", "PathRein",
    "FabricRein", "LightGroup", "DisplacementElement",
    "ConduitRun", "PipeFittingCenterLine", "DuctFittingCenterLine",
    "ConduitFittingCenterLine", "SegmentCenterLine", "FlexCenterLine",
    "ReferencePoint", "ExtrusionElem", "BlendElem", "SweepElem", "RevolveElem",
    "FamilyGeomCombination", "ImageInstance", "Text3dElem", "AreaMeasureElem",
    "SpotElevation", "Hub",
])
_reg("view-annotation-2d-content", [
    "CurveElem", "TextNote", "LinearDimString", "RadialDim", "AngularDim",
    "ArcLengthDim", "Alignment", "IndependentTag", "RoomTag", "FilledRegion",
    "LegendComponent", "LegendComponentGRepHolder", "SketchGrid", "VarSketch",
    "NonPlanarSketch", "SketchPlane", "SunAnnotationElem", "ModelClipBox",
    "ContourSpacingElem", "RepeatingDetail", "RevisionCloud", "InsulationElem",
    "AreaTag", "SpaceTag", "SunPath", "ContourLabelingElem", "KeynoteTag",
    "BeamSystemTag", "SpanDirectionSymbol", "PathReinSpanSymbol",
    "FabricReinSpanSymbol", "MultiReferenceAnnotation", "PlanRegion",
    "GuideGrid", "DisplacementElementLocationLine", "PathOfTravel",
    "ProfileRefPlane", "Matchline",
])
_reg("internal-bookkeeping", [
    "RegenSplitterElem", "PostedWarningElem", "GraphicsCache",
    "ReactionsUpToDateElem", "AnalyticalToPhysicalRelationManager",
    "MEPNetworkDataElem", "CurtaSystemFaceManager", "LayoutNodesTracker",
    "SlaveSymbolTracker", "AutoJoinTracker", "HubsTracker", "GCSTracker",
    "AssemblyTracker", "MEPSystemTracker", "MEPComponentTracker", "MEPNetworkTracker",
    "KeynoteTagsOnSheetsTracker", "RevisionCloudsOnSheetsTracker",
    "ScheduleInstanceBaseOnSheetsTracker", "SheetsInSheetCollectionTracker",
    "AreaTypeElem", "ProjectCopySettingsElem", "ReconcileBrowserSettingsElem",
    "WorksetVisibilitySettingsElem", "AutoCamSettingsElem", "Dwg2dExportUserSettingsData",
    "WatchElem", "EnergyAnalysisDetailModel", "EnergyAnalysisSurface",
    "EnergyAnalysisOpening", "EnergyAnalysisSpace", "EnergyAnalysisZone",
    "EnergyAnalysisConstruction", "EnergyAnalysisMaterial",
])
_reg("patterns-materials", ["Pattern"])
_reg("parameter-definitions", ["ParamElemGlobal", "ParamElemRefTableEntry",
                                "RefTableElem"])
_reg("views-and-templates", ["VolumeOfInterest", "SelectionFilterElement"])
_reg("system-family-types", ["ContinuousRailSymbol", "MultiReferenceAnnotationType"])
_reg("family-types-symbols", ["SharedSymbol"])

#: annotation built-in category ids (OST_*): family symbols / families in
#: these categories are annotation symbols, not model families.
_ANNOTATION_OST_NAMES = {
    "OST_TitleBlocks", "OST_GenericAnnotation", "OST_SectionHeads",
    "OST_CalloutHeads", "OST_ViewportLabel", "OST_ReferenceViewer",
    "OST_ElevationMarks", "OST_LevelHeads", "OST_GridHeads",
    "OST_SpotElevSymbols", "OST_DetailComponents", "OST_RevisionClouds",
    "OST_KeynoteTags", "OST_MultiCategoryTags", "OST_StairsUpText",
    "OST_ProfileFamilies", "OST_MatchLine",
}
ANNOTATION_CAT_IDS: Set[int] = set()
for _tbl in (getattr(inv, "BUILTIN_CATEGORIES_VERIFIED", {}),
             getattr(inv, "BUILTIN_CATEGORIES_ASSUMED", {})):
    for _cid, (_ost, _label) in _tbl.items():
        if _ost in _ANNOTATION_OST_NAMES or _label.endswith("Tags") or _ost.endswith("Tags"):
            ANNOTATION_CAT_IDS.add(_cid)


def category_for_class(schema, cls: str) -> str:
    """Legal category for a schema class name (no per-element info).

    Ordered rules: explicit map -> DBView prefix -> ancestry (HostObjAttr /
    LineAndTextAttrSymbol / Symbol / Instance / HostObj / Dimension) -> name
    heuristics (Settings / Tracker / Type / Attributes) -> ``unmapped``.
    """
    if cls in _EXPLICIT:
        return _EXPLICIT[cls]
    if cls.startswith("DBView"):
        return "views-and-templates"
    chain: List[str] = []
    try:
        cd = schema.by_name.get(cls) if schema is not None else None
        if cd is not None:
            chain = schema.parent_chain(cls)[1:]
    except Exception:
        chain = []
    if "HostObjAttr" in chain:
        return "system-family-types"
    if "LineAndTextAttrSymbol" in chain:
        return "text-dimension-types"
    if "Instance" in chain or "HostObj" in chain or "RbsCurve" in chain or \
            "CenterLine" in chain or "LoadBCBase" in chain or "AnalyticalElement" in chain:
        return "placed-model-content"
    if "Dimension" in chain or "DimWithSegRefs" in chain or "ISketch" in chain or \
            "SketchBase" in chain:
        return "view-annotation-2d-content"
    if "DBView" in chain or "Viewer" in chain:
        return "views-and-templates"
    if "Symbol" in chain or "InsertableObj" in chain:
        if re.search(r"(Attributes|Attr|Style)$", cls):
            return "text-dimension-types"
        if cls.endswith("Type"):
            return "system-family-types"
        return "family-types-symbols"
    if re.search(r"Settings(Elem|Element)?$|SettingsElem$|Setting$", cls):
        return "project-info-settings"
    if "Tracker" in cls:
        return "internal-bookkeeping"
    if cls.endswith("Type"):
        return "system-family-types"
    if re.search(r"(Attributes|Attr|AttrSymbol|Style)$", cls):
        return "text-dimension-types"
    return "unmapped"


def legal_category(doc, eid: int) -> str:
    """Legal category of one element, with the annotation-symbol override."""
    cls = _cls(doc, eid)
    cat = category_for_class(doc.dec.schema, cls) if cls else "unmapped"
    if cat in ("loadable-families", "family-types-symbols"):
        cat_id = _category_of(doc, eid)
        if cat_id is not None and cat_id in ANNOTATION_CAT_IDS:
            return "annotation-symbols-titleblocks"
    return cat


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _cls(doc, eid: int) -> str:
    try:
        return doc.class_of(eid) or "<no-record>"
    except Exception:
        return "<no-record>"


def _category_of(doc, eid: int) -> Optional[int]:
    try:
        return doc.category_of(eid)
    except Exception:
        return None


def _payload(doc, eid: int, seq: int) -> Optional[bytes]:
    r = doc.record(eid, seq)
    return None if r is None else r.payload


_NAME_PATHS = {
    "FillPatternElem": ("m_pFillPattern", "m_name"),
    "LinePatternElem": ("m_pLinePattern", "m_name"),
    "FontElem": ("m_pFont", "m_name"),
    "AppearanceAssetElem": ("m_pAppearanceAsset", "m_Name"),
    "TilePatternType": ("m_symbolInfo", "m_name"),
}


def _name(doc, eid: int) -> Optional[str]:
    """Best human name — inventory.element_name plus a few class extras."""
    try:
        n = inv.element_name(doc, eid)
    except Exception:
        n = None
    if n:
        return n
    try:
        cls = doc.class_of(eid) or ""
        v = doc.value(eid)
        if not isinstance(v, dict):
            return None
        if cls in _NAME_PATHS:
            n = inv._clean_str(inv._dig(v, *_NAME_PATHS[cls]))
            if n:
                return n
        if cls.startswith("ParamElem"):
            n = inv._clean_str(inv._dig(v, "m_pParamDef", "m_caption"))
            if n:
                return n
        if cls == "GStyleElem":
            cid = v.get("m_categoryId")
            lab = inv.category_label(doc, cid) if cid is not None else None
            if lab:
                return f"style:{lab}"
        if cls == "ParamBinding":
            pid = v.get("m_paramId")
            pn = _name(doc, pid) if pid not in (None, -1) else None
            cid = v.get("m_categoryId")
            lab = inv.category_label(doc, cid) if cid is not None else None
            if pn or lab:
                return f"{pn or pid} -> {lab or cid}"
    except Exception:
        return None
    return None


def watermark(doc) -> int:
    """The document's original id watermark (``IdentifierSource.m_last``)."""
    et = doc.et
    wm = et.footer.last_id if getattr(et, "footer", None) else 0
    return max(wm, max(doc.et_by_id) if doc.et_by_id else 0)


# ---------------------------------------------------------------------------
# clone-lineage detection for created elements
# ---------------------------------------------------------------------------
#: decoded-tree paths that yield false-positive "element ids" (geometry face /
#: edge / topology indices, history tables) — excluded from lineage refs.
_GEOM_PATH_TOKENS = ("m_geomSteps", "m_faces", "m_edges", "m_geomTops",
                     "Snapshot", "HistTable", "m_faceHist", "m_edgeHist",
                     "m_GInfo", "m_pBBox")

CLONE_SIMILARITY_THRESHOLD = 0.50   # shingle overlap => structural clone
_SHINGLE = 16
_STRIDE = 8

#: element-header parent lists — real references but the least specific
#: attribution; ranked after direct fields (symbolId, WallAttributesId ...)
_HEADER_PARENT_KEYS = ("m_deletion", "m_regenOnly", "m_appearanceParents",
                       "m_parents", "m_regenChildren")
#: preference order when naming the ONE thing a created element derives from
_LINEAGE_CAT_RANK = {
    "family-types-symbols": 0, "system-family-types": 1, "loadable-families": 2,
    "mep-electrical-definitions": 3, "annotation-symbols-titleblocks": 4,
    "text-dimension-types": 5, "patterns-materials": 6, "parameter-definitions": 7,
    "views-and-templates": 8, "object-styles": 9, "unmapped": 10,
}


def _shingles(b: bytes) -> Set[bytes]:
    if not b or len(b) < _SHINGLE:
        return {b or b""}
    return {b[i:i + _SHINGLE] for i in range(0, len(b) - _SHINGLE + 1, _STRIDE)}


def _reference_ids(doc, eid: int) -> List[Tuple[str, int]]:
    """(path, id) references from an element's three record streams, minus
    geometry-index false positives."""
    from .mutate import _collect_ids
    refs: List[Tuple[str, int]] = []
    for seq in (101, 102, 103):
        try:
            o = doc.decode(eid, seq)
        except Exception:
            o = None
        if o is not None and getattr(o, "value", None) is not None:
            try:
                _collect_ids(o.value, refs)
            except Exception:
                pass
    return [(p, i) for p, i in refs
            if i != eid and not any(t in p for t in _GEOM_PATH_TOKENS)]


class _CloneIndex:
    """Per-class shingle index over BASELINE payloads, built lazily.
    ``only_ids`` restricts the specimens to the baseline's sample-authored
    ids (a composed base's residue) so OUR composed objects never make a
    created element ``transitive-cloned``."""

    def __init__(self, baseline, only_ids: Optional[AbstractSet[int]] = None):
        self.base = baseline
        self.only_ids = only_ids
        self._by_class: Dict[str, Dict[bytes, Set[int]]] = {}

    def _index(self, cls: str) -> Dict[bytes, Set[int]]:
        if cls not in self._by_class:
            idx: Dict[bytes, Set[int]] = defaultdict(set)
            cd = self.base.dec.schema.by_name.get(cls)
            if cd is not None:
                for eid, rec in self.base.idx[102].items():
                    if rec.class_id != cd.type_id or eid not in self.base.et_by_id:
                        continue
                    if self.only_ids is not None and eid not in self.only_ids:
                        continue
                    for sh in _shingles(rec.payload):
                        idx[sh].add(eid)
            self._by_class[cls] = idx
        return self._by_class[cls]

    def best_match(self, cls: str, payload: bytes) -> Tuple[Optional[int], float]:
        """(baseline eid, similarity) of the closest same-class specimen."""
        idx = self._index(cls)
        if not idx or not payload:
            return None, 0.0
        sh = _shingles(payload)
        if not sh:
            return None, 0.0
        hits: Counter = Counter()
        for s in sh:
            for e in idx.get(s, ()):
                hits[e] += 1
        if not hits:
            return None, 0.0
        e, n = hits.most_common(1)[0]
        return e, n / len(sh)


# ---------------------------------------------------------------------------
# per-element classification
# ---------------------------------------------------------------------------
@dataclass
class ElementVerdict:
    eid: int
    cls: str
    category: str
    provenance: str
    reason: str = ""
    lineage: List[dict] = field(default_factory=list)   # created only
    clone_of: Optional[int] = None
    clone_similarity: float = 0.0
    attribution: Optional[str] = None                  # multi-baseline: which sample explains it
    baselines: Dict[str, str] = field(default_factory=dict)  # label -> verdict brief
    edited: bool = False                               # ours-composed only: this build changed it

    def to_json(self) -> dict:
        d = {"id": self.eid, "class": self.cls, "category": self.category,
             "provenance": self.provenance}
        if self.edited:
            d["edited"] = True
        if self.reason:
            d["reason"] = self.reason
        if self.lineage:
            d["lineage"] = self.lineage[:6]
        if self.clone_of is not None:
            d["clone_of"] = self.clone_of
            d["clone_similarity"] = round(self.clone_similarity, 3)
        if self.attribution:
            d["attribution"] = self.attribution
        if self.baselines:
            d["baselines"] = self.baselines
        return d


def _same_records(cand, base, eid: int) -> Tuple[bool, str]:
    """True if the element's seq-102 object (and 101 header / 103 rep) are
    byte-identical in candidate and baseline."""
    diffs = []
    for seq in (102, 101, 103):
        a = _payload(cand, eid, seq)
        b = _payload(base, eid, seq)
        if a is None and b is None:
            continue
        if a != b:
            diffs.append({101: "header", 102: "object", 103: "geometry"}[seq])
    return (not diffs), ("differs in " + "+".join(diffs)) if diffs else "byte-identical to sample"


def same_records(a, b, eid: int) -> bool:
    """True iff element ``eid``'s records (seq 101/102/103) are byte-identical
    in documents ``a`` and ``b`` -- the ledger's one byte law, reused by the
    census descent test (rvt.frontdoor.census.lineage, #284)."""
    return _same_records(a, b, eid)[0]


def classify_elements(doc, baseline=None, *, clone_index: Optional[_CloneIndex] = None,
                      composed: Optional[ComposedBaseline] = None) -> Dict[int, ElementVerdict]:
    """Classify EVERY host-document element of ``doc`` (candidate).

    ``baseline`` is the reference Autodesk sample ``Document`` the candidate
    descends from (or None -> everything is ``unbaselined``).

    ``composed`` (issue #143): pass it iff ``baseline`` is OUR pinned
    composed genesis base -- its ``residue_ids`` are the baseline ids no
    certified rung changed (still the Autodesk ancestor's serialization;
    rvt.frontdoor.census, derived by tools/genesis_census.py under the law
    "ours iff a certified rung changed the record AND landed an object
    there").  That set is applied as given, not re-derived here: every other
    baseline id is ours by composition (``ours-composed``, inherited or
    edited) and seeds no clone lineage; the residue ids are ledgered exactly
    as sample elements are (this module's byte law against ``baseline``).
    ``None`` = the baseline is a sample: v1 behaviour.
    """
    verdicts: Dict[int, ElementVerdict] = {}
    host_ids = sorted(doc.et_by_id)
    base_ids: Set[int] = set(baseline.et_by_id) if baseline is not None else set()
    wm = watermark(baseline) if baseline is not None else -1
    residue = composed.residue_ids if composed is not None else None
    cindex = clone_index or (_CloneIndex(baseline, only_ids=residue)
                             if baseline is not None else None)

    created: List[int] = []
    for eid in host_ids:
        cls = _cls(doc, eid)
        cat = legal_category(doc, eid)
        if baseline is None:
            verdicts[eid] = ElementVerdict(eid, cls, cat, P_UNBASELINED,
                                           "no baseline supplied")
            continue
        if eid in base_ids:
            bcls = _cls(baseline, eid)
            if bcls != cls:
                verdicts[eid] = ElementVerdict(
                    eid, cls, cat, P_UNMATCHED,
                    f"id exists in baseline as a different class ({bcls}) — renumbered / wrong baseline")
                continue
            same, why = _same_records(doc, baseline, eid)
            if residue is not None and eid not in residue:
                verdicts[eid] = ElementVerdict(
                    eid, cls, cat, P_COMPOSED,
                    "our composed base's own object (slot re-authored in place), "
                    + ("inherited unchanged" if same else "edited by this build: " + why),
                    edited=not same)
                continue
            verdicts[eid] = ElementVerdict(eid, cls, cat,
                                           P_SAMPLE if same else P_MODIFIED, why)
        elif eid > wm:
            created.append(eid)
            verdicts[eid] = ElementVerdict(eid, cls, cat, P_CREATED,
                                           f"id {eid} > baseline watermark {wm}")
        else:
            verdicts[eid] = ElementVerdict(
                eid, cls, cat, P_UNMATCHED,
                f"id {eid} <= watermark {wm} but absent from baseline — wrong baseline?")

    # --- refine created elements: transitive clone or genuinely ours -------
    for eid in created:
        v = verdicts[eid]
        seen: Dict[int, dict] = {}
        for path, tgt in _reference_ids(doc, eid):
            tv = verdicts.get(tgt)
            if tv is None or tv.provenance not in (P_SAMPLE, P_MODIFIED):
                continue
            if tv.category not in CLONE_LINEAGE_CATEGORIES:
                continue
            via = path.split(".")[-1]
            rank = (1 if any(via.startswith(h) for h in _HEADER_PARENT_KEYS) else 0,
                    _LINEAGE_CAT_RANK.get(tv.category, 9))
            prev = seen.get(tgt)
            if prev is None or rank < prev["rank"]:
                seen[tgt] = {"id": tgt, "class": tv.cls, "category": tv.category,
                             "via": via, "name": _name(doc, tgt), "rank": rank}
        lineage = sorted(seen.values(), key=lambda d: d["rank"])
        for d in lineage:
            d.pop("rank", None)
        lineage = lineage[:12]
        clone_of, sim = (None, 0.0)
        if cindex is not None:
            try:
                clone_of, sim = cindex.best_match(v.cls, _payload(doc, eid, 102) or b"")
            except Exception:
                clone_of, sim = (None, 0.0)
        v.lineage = lineage
        v.clone_of, v.clone_similarity = (clone_of, sim) if sim >= 0.25 else (None, sim)
        cloned = bool(lineage) or (clone_of is not None and sim >= CLONE_SIMILARITY_THRESHOLD)
        if cloned:
            v.provenance = P_CLONED
            bits = []
            if lineage:
                l0 = lineage[0]
                bits.append(f"references sample {l0['category']} "
                            f"{l0['class']} {l0['id']} via {l0['via']}")
            if clone_of is not None and sim >= CLONE_SIMILARITY_THRESHOLD:
                bits.append(f"structural clone of sample {v.cls} {clone_of} "
                            f"({sim:.0%} shingle overlap)")
            v.reason = "; ".join(bits)
        else:
            v.provenance = P_CREATED
            v.reason = (f"id {eid} > watermark {wm}; no lineage into sample "
                        f"expression (max clone overlap {sim:.0%})")
    return verdicts


# ---------------------------------------------------------------------------
# embedded family documents (save units)
# ---------------------------------------------------------------------------
def _unit_guid_str(g: Optional[bytes]) -> Optional[str]:
    if not g or len(g) != 16:
        return None
    try:
        return str(uuid.UUID(bytes_le=bytes(g)))
    except Exception:
        return None


@contextlib.contextmanager
def reading_own_release(rvt_path: str):
    """Walk ``rvt_path`` under its OWN release (rvt.global_framing's lenient
    ladder: own schema -> pinned table -> native; partition framing +
    Global-stream tokens + ADocument decoder follow the file) -- a Revit
    2025/2024 candidate or baseline is walked, not skipped as one opaque
    unit (issue #14).  Yields the fallback note (None = own schema)."""
    from .global_framing import enter_own_release
    with contextlib.ExitStack() as stack:
        yield enter_own_release(stack, rvt_path)


def embedded_units(rvt_path: Optional[str]) -> List[dict]:
    """Enumerate the embedded save units (family DOCUMENTS) of a file.

    Unit 0 is the host document and is excluded.  Each entry:
    {partition, index, guid, blocks, counter}.
    """
    if not rvt_path or not os.path.exists(rvt_path):
        return []
    from .container import open_rvt
    from .partitions import StreamWalker
    out: List[dict] = []
    with reading_own_release(rvt_path), open_rvt(rvt_path) as f:
        for pn in f.partition_streams():
            try:
                w = StreamWalker(f.logical(pn), inflate=False, keep_data=False)
            except Exception:
                continue
            for u in w.units:
                if u.index == 0:
                    continue
                out.append({"partition": pn, "index": u.index,
                            "guid": _unit_guid_str(u.guid),
                            "blocks": u.n_blocks, "counter": u.counter})
    return out


def _family_docguid_map(doc) -> Dict[str, dict]:
    """content-document GUID -> {family_id, name} from host Family elements."""
    out: Dict[str, dict] = {}
    for fid in doc.ids_of_class("Family"):
        try:
            v = doc.value(fid) or {}
        except Exception:
            continue
        if not isinstance(v, dict):
            continue
        name = inv._clean_str(v.get("m_name"))
        keys = set()
        fd = v.get("m_oFamDoc")
        if isinstance(fd, dict):
            g = (fd.get("value") or {}).get("m_contentDocGUID")
            if isinstance(g, str):
                keys.add(g.lower())
        g2 = v.get("m_famDocGUID")
        if isinstance(g2, str):
            keys.add(g2.lower())
        for k in keys:
            out.setdefault(k, {"family_id": fid, "name": name})
    return out


def classify_units(doc, baseline=None, *, baselines: Optional[List] = None) -> List[dict]:
    """Provenance for every embedded family document (save unit).

    With ``baselines`` (multi-baseline) a unit GUID known to ANY baseline
    is ``autodesk-sample``, attributed to that baseline."""
    cpath = getattr(doc, "source_path", None)
    units = embedded_units(cpath)
    bases = list(baselines) if baselines else ([baseline] if baseline is not None else [])
    base_guids: Dict[str, str] = {}
    for b in bases:
        lab = baseline_label(b)
        for u in embedded_units(getattr(b, "source_path", None)):
            if u["guid"]:
                base_guids.setdefault(u["guid"], lab)
    fmap = _family_docguid_map(doc)
    for u in units:
        g = u["guid"]
        fam = fmap.get(g) if g else None
        u["family_id"] = fam["family_id"] if fam else None
        u["family_name"] = fam["name"] if fam else None
        if not bases:
            u["provenance"] = P_UNBASELINED
        elif g and g in base_guids:
            u["provenance"] = P_SAMPLE
            u["attribution"] = base_guids[g]
        else:
            u["provenance"] = P_CREATED
    return units


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------
def provenance(doc, baseline=None, *, examples: int = 3,
               with_units: bool = True, strict: bool = False,
               baselines: Optional[List] = None,
               streams: bool = False, strings: bool = False,
               identity: bool = False, corpus: Optional["BaselineCorpus"] = None,
               cache_dir: Optional[str] = None, verbose: bool = False,
               composed: Optional[ComposedBaseline] = None) -> dict:
    """Build the provenance ledger for ``doc`` against ``baseline``(s).

    ``doc`` / ``baseline`` are ``rvt.mutate.Document`` objects (use
    ``Document.from_file``).  Returns a JSON-serialisable dict:
    per-category counts by provenance, per-class breakdown with example
    ids+names, embedded family-document units, totals, and the G1 gate verdict.

    ``composed`` (single baseline only, issues #143 / #284): the baseline is
    OUR pinned composed genesis base and this :class:`ComposedBaseline`
    carries its residue ids (see :func:`classify_elements`); the report then
    says ``baseline_kind = 'pinned-composed-genesis'``, names the pin, and
    counts the inherited ``ours-composed`` elements apart from the
    Autodesk-derived residue.  A candidate that DESCENDS from the pin (an
    edit of our own output) is ledgered against the pin the same way.

    v2 layers (opt-in, all ON in the CLI):
      ``baselines=[Document,...]`` — MULTI-BASELINE union: an element is
          sample-derived if derived against ANY baseline, attributed to which.
      ``streams=True`` — the STREAM LEDGER: every stream + save unit is
          classified by bytes (identical / prefix-shared / % identical /
          ours) and rolled up byte-weighted.
      ``strings=True`` — Autodesk resource-identifier census (G1c items).
      ``identity=True`` — BasicFileInfo / DIT identity policy check (G2).
    The report records which ``layers`` ran; the G1 gate CERTIFIES only
    when all four ran and none blocks (element-only PASS is labelled as such).
    """
    if baselines:
        baselines = [b for b in baselines if b is not None]
        baseline = baseline or baselines[0]
        # the primary baseline (compat fields) = best id overlap
        try:
            baseline = max(baselines,
                           key=lambda b: len(set(doc.et_by_id) & set(b.et_by_id)))
        except Exception:
            pass
    else:
        baselines = [baseline] if baseline is not None else []
    if len(baselines) > 1:
        verdicts = classify_elements_multi(doc, baselines)
        composed = None                      # multi-baseline = the samples themselves
    else:
        verdicts = classify_elements(doc, baseline, composed=composed)
        if baseline is not None:
            lab = baseline_label(baseline)
            for v in verdicts.values():
                v.attribution = lab
    residue = composed.residue_ids if composed is not None else None
    units = classify_units(doc, baseline, baselines=baselines) if with_units else []

    # roll up
    cat_prov: Dict[str, Counter] = {c: Counter() for c in CATEGORY_ORDER}
    cat_class_prov: Dict[str, Dict[str, Counter]] = {c: defaultdict(Counter) for c in CATEGORY_ORDER}
    examples_ix: Dict[Tuple[str, str, str], List[int]] = defaultdict(list)
    prov_tot: Counter = Counter()
    for eid, v in verdicts.items():
        cat = v.category if v.category in cat_prov else "unmapped"
        cat_prov[cat][v.provenance] += 1
        cat_class_prov[cat][v.cls][v.provenance] += 1
        prov_tot[v.provenance] += 1
        key = (cat, v.cls, v.provenance)
        if len(examples_ix[key]) < examples:
            examples_ix[key].append(eid)

    # units roll-up (a legal category of its own)
    unit_prov: Counter = Counter(u["provenance"] for u in units)
    if units:
        for p, n in unit_prov.items():
            cat_prov["embedded-family-documents"][p] += n
            cat_class_prov["embedded-family-documents"]["<family document (save unit)>"][p] += n

    categories_out: Dict[str, dict] = {}
    for cat in CATEGORY_ORDER:
        counts = cat_prov[cat]
        if not counts:
            continue
        label, expression, desc = CATEGORIES[cat]
        classes_out: Dict[str, dict] = {}
        for cls in sorted(cat_class_prov[cat], key=lambda c: -sum(cat_class_prov[cat][c].values())):
            cc = cat_class_prov[cat][cls]
            entry = {"counts": {p: cc[p] for p in PROVENANCES if cc[p]}}
            ex: Dict[str, list] = {}
            for p in PROVENANCES:
                ids = examples_ix.get((cat, cls, p))
                if ids:
                    ex[p] = [_example(doc, e, verdicts) for e in ids]
            if ex:
                entry["examples"] = ex
            classes_out[cls] = entry
        categories_out[cat] = {
            "label": label, "expression_bearing": expression, "description": desc,
            "counts": {p: counts[p] for p in PROVENANCES if counts[p]},
            "classes": classes_out,
        }

    if units and "embedded-family-documents" in categories_out:
        categories_out["embedded-family-documents"]["units"] = units[:400]
        if len(units) > 400:
            categories_out["embedded-family-documents"]["units_truncated"] = len(units) - 400

    overlap = None
    if baseline is not None and doc.et_by_id:
        both = len(set(doc.et_by_id) & set(baseline.et_by_id))
        overlap = round(both / max(1, len(doc.et_by_id)), 4)

    layers = ["elements"]
    report = {
        "candidate": os.path.abspath(getattr(doc, "source_path", "") or doc.project),
        "baseline": (os.path.abspath(getattr(baseline, "source_path", "") or baseline.project)
                     if baseline is not None else None),
        "baselines": [os.path.abspath(getattr(b, "source_path", "") or b.project)
                      for b in baselines] if baselines else [],
        "multi_baseline": len(baselines) > 1,
        "baseline_kind": (None if baseline is None else
                          "pinned-composed-genesis" if residue is not None
                          else "autodesk-sample"),
        "composed": ({
            "pinned_id": composed.pinned_id,
            "baseline_residue_ids": len(residue),
            "inherited_ours_composed": prov_tot.get(P_COMPOSED, 0),
            "note": ("baseline = OUR pinned composed genesis base: ids outside its residue "
                     "are ours by composition (not Autodesk-derived); the residue ids are "
                     "ledgered as sample elements and alone seed clone lineage"),
        } if residue is not None else None),
        "baseline_watermark": watermark(baseline) if baseline is not None else None,
        "candidate_watermark": watermark(doc),
        "host_elements": len(doc.et_by_id),
        "baseline_host_elements": len(baseline.et_by_id) if baseline is not None else None,
        "baseline_id_overlap": overlap,
        "provenance_totals": {p: prov_tot[p] for p in PROVENANCES if prov_tot[p]},
        "embedded_family_documents": {
            "count": len(units),
            "by_provenance": dict(unit_prov),
        },
        "categories": categories_out,
        "created_elements": [verdicts[e].to_json() for e in sorted(verdicts)
                             if verdicts[e].provenance in (P_CREATED, P_CLONED)],
        "modified_elements": [verdicts[e].to_json() for e in sorted(verdicts)
                              if verdicts[e].provenance == P_MODIFIED or verdicts[e].edited][:200],
    }
    if len(baselines) > 1:
        # per-baseline table + union attribution (audit §B3)
        attrib: Counter = Counter()
        for v in verdicts.values():
            if v.provenance in DERIVED and v.attribution:
                attrib[v.attribution] += 1
        per_base: Dict[str, dict] = {}
        for b in baselines:
            lab = baseline_label(b)
            c: Counter = Counter()
            for v in verdicts.values():
                r = v.baselines.get(lab)
                if r:
                    c[r.split(" ", 1)[0]] += 1
            per_base[lab] = {p: c[p] for p in PROVENANCES if c[p]}
        # how "ours" are the union-created elements really?  bucket by the
        # MAX structural similarity to ANY sample specimen (audit §B3: only
        # elements below ~0.40 everywhere carry genuinely authored payload).
        sims = [(v.clone_similarity or 0.0) for v in verdicts.values()
                if v.provenance == P_CREATED]
        report["multi_baseline_table"] = {
            "union": {p: prov_tot[p] for p in PROVENANCES if prov_tot[p]},
            "per_baseline": per_base,
            "derived_attribution": dict(attrib.most_common()),
            "created_max_similarity_buckets": {
                "created_total": len(sims),
                "max_sim_lt_0.25": sum(1 for s in sims if s < 0.25),
                "max_sim_lt_0.40": sum(1 for s in sims if s < 0.40),
                "max_sim_ge_0.40": sum(1 for s in sims if s >= 0.40),
                "note": "created (below the 0.50 clone bar against EVERY sample) "
                        "but with high residual similarity = Autodesk product-default "
                        "values reproduced; only the low-similarity elements carry "
                        "genuinely authored payload",
            },
        }
    warnings: List[str] = []
    if baseline is not None and overlap is not None and overlap < 0.9 and len(baselines) <= 1:
        warnings.append(
            f"baseline mismatch: only {overlap:.0%} of candidate ids exist in the baseline "
            f"— {prov_tot.get(P_UNMATCHED, 0):,} elements are unattributable; "
            f"pick the sample this file actually descends from (tools/provenance.py --baseline auto)")
    if baseline is None:
        warnings.append("no baseline supplied: every element is unbaselined; the gate cannot pass")

    # --- v2 layers ------------------------------------------------------------
    cpath = getattr(doc, "source_path", None)
    if (streams or strings or identity) and cpath and os.path.exists(cpath):
        cunits: Optional[List[ContentUnit]] = None
        base_paths = [getattr(b, "source_path", None) for b in baselines]
        base_paths = [p for p in base_paths if p and os.path.exists(p)]
        if streams and not base_paths and corpus is None:
            warnings.append("stream ledger skipped: no baseline file to compare bytes against")
            streams = False
        if streams:
            if corpus is None:
                corpus = build_baseline_corpus(base_paths, cache_dir=cache_dir, verbose=verbose)
            cunits = content_units(cpath)
            report["stream_ledger"] = stream_ledger(cpath, corpus, units=cunits)
            layers.append("streams")
        if strings:
            if cunits is None:
                cunits = content_units(cpath)
            report["resource_refs"] = resource_ref_report(cpath, doc, units=cunits)
            layers.append("strings")
        if identity:
            if cunits is None:
                cunits = content_units(cpath, with_partitions=False)
            icorpus = corpus
            if icorpus is None and base_paths:
                # identity only needs the baselines' declared identities —
                # read their BasicFileInfo directly (no block index needed).
                icorpus = BaselineCorpus()
                from .container import open_rvt
                from . import stream_encoders as _se
                for bp in base_paths:
                    lab = os.path.splitext(os.path.basename(bp))[0]
                    try:
                        with open_rvt(bp) as f:
                            icorpus.bfi[lab] = _bfi_identity(
                                _se.decode_basic_file_info(f.raw("BasicFileInfo")))
                        icorpus.labels.append(lab)
                        icorpus.paths[lab] = os.path.abspath(bp)
                    except Exception:
                        continue
            report["identity"] = identity_report(cpath, icorpus, units=cunits)
            layers.append("identity")
    report["layers"] = layers
    report["warnings"] = warnings
    report["gate_G1"] = gate_G1(report, strict=strict)
    return report


def _example(doc, eid: int, verdicts: Dict[int, ElementVerdict]) -> dict:
    v = verdicts[eid]
    d = {"id": eid, "class": v.cls, "name": _name(doc, eid)}
    if v.provenance == P_MODIFIED and v.reason:
        d["change"] = v.reason
    if v.clone_of is not None:
        d["clone_of"] = v.clone_of
        d["clone_similarity"] = round(v.clone_similarity, 2)
    if v.lineage:
        l0 = v.lineage[0]
        d["derived_from"] = {"id": l0["id"], "class": l0["class"], "name": l0["name"]}
    return d


# ---------------------------------------------------------------------------
# the G1 gate
# ---------------------------------------------------------------------------
GATE_LAYERS = ("elements", "streams", "strings", "identity")


def gate_G1(report: dict, strict: bool = False) -> dict:
    """G1 GENESIS gate — the HONEST (v2) reading.

    PASS iff, with no unattributable provenance:
      * ELEMENTS  — zero autodesk-sample / ours-modified / transitive-cloned
                     in every expression-bearing category (union over all
                     baselines when multi-baseline) and zero Autodesk-sample
                     embedded family documents;
      * STREAMS   — zero bytes byte-identical to any baseline in the
                     expression-bearing streams (Global/Latest,
                     Global/ContentDocuments, the family save units);
                     Formats/Latest is the counsel-C4 schema stream, listed
                     under ``counsel`` and NOT counted as a byte blocker;
      * STRINGS   — zero autodesk-resource-refs in the document content;
      * IDENTITY  — BasicFileInfo / DocumentIncrementTable assert OUR
                     identity (rvt.identity policy).
    A report that ledgered only some layers can only PASS *those* layers:
    ``certifies_G1`` is True iff all four layers ran and none blocks — an
    element-only "PASS" is labelled as NOT a G1 certification (this is the
    lie the genesis audit caught the v1 instrument telling).

    ``strict=True`` additionally gates the report-only element categories.
    Returns {passes, certifies_G1, layers, blocking, counsel, advisories, ...}.
    """
    blocking: List[dict] = []
    counsel: List[dict] = []
    advisories: List[dict] = []
    layers = list(report.get("layers") or ["elements"])

    # --- element layer --------------------------------------------------
    cats = report.get("categories", {})
    for cat in CATEGORY_ORDER:
        info = cats.get(cat)
        if not info:
            continue
        expression = strict or CATEGORIES.get(cat, ("", True, ""))[1]
        for prov, n in info.get("counts", {}).items():
            if n <= 0:
                continue
            # NOTE: element-layer entries keep the v1 shape (no "layer" key)
            # so v1 consumers / tests match them exactly; every OTHER layer
            # carries an explicit "layer" key.
            if prov in (P_UNMATCHED, P_UNBASELINED):
                blocking.append({"category": cat, "provenance": prov, "count": n,
                                 "why": "unattributable — the gate cannot pass on unknown provenance"})
            elif prov in DERIVED and expression:
                blocking.append({"category": cat, "provenance": prov, "count": n,
                                 "why": "Autodesk-derived expression in an expression-bearing category"})

    # --- stream layer -----------------------------------------------------
    sl = report.get("stream_ledger")
    if sl:
        for row in sl.get("units", []):
            if row.get("expression_bearing") and row.get("identical_bytes", 0) > 0:
                blocking.append({
                    "layer": "streams", "category": row["name"],
                    "provenance": f"stream-{row['class']}",
                    "count": row["identical_bytes"],
                    "why": (f"{row['identical_bytes']:,} of {row['inflated']:,} bytes byte-identical "
                            f"to baseline {row.get('best_baseline')} — sample-authored expression "
                            f"shipping verbatim in an expression-bearing stream")})
        ss = sl.get("schema_stream")
        if ss and ss.get("identical_pct", 0) > 0:
            counsel.append({"item": "C4 schema-stream", "stream": ss["name"],
                            "identical_pct": ss["identical_pct"],
                            "identical_to": ss.get("identical_to"),
                            "why": "Formats/Latest is Autodesk's serialized class model shipped "
                                   "byte-identical — counsel decides ship-verbatim vs clean-room "
                                   "re-serialization (interoperability defence to raise, not a settled fact)"})
        for fp in sl.get("fingerprints", []):
            advisories.append({"layer": "streams", "stream": fp["name"],
                               "class": fp["class"], "identical_pct": fp["identical_pct"],
                               "why": "lineage fingerprint (identity / save history / GUIDs) — "
                                      "not expression, but chain-of-custody in the sample's bytes"})
    # --- string layer -----------------------------------------------------
    rr = report.get("resource_refs")
    if rr is not None:
        n = rr.get("total_refs", 0)
        if n > 0:
            blocking.append({"layer": "strings", "category": "autodesk-resource-refs",
                             "provenance": "autodesk-resource-refs", "count": n,
                             "why": (f"{n:,} Autodesk resource identifier(s) in document content "
                                     f"({', '.join(f'{k}={v}' for k, v in sorted(rr.get('by_pattern', {}).items(), key=lambda kv: -kv[1])[:5])}) "
                                     f"— references-to / identifiers-of Autodesk artefacts (G1c)")})
        ns = rr.get("total_refs_schema_stream", 0)
        if ns:
            counsel.append({"item": "C4 schema-stream", "stream": "Formats/Latest",
                            "refs": ns,
                            "why": f"{ns:,} Autodesk identifiers inside the schema stream (counted separately)"})
    # --- identity layer ---------------------------------------------------
    idr = report.get("identity")
    if idr is not None:
        for v in idr.get("violations", []):
            blocking.append({"layer": "identity", "category": f"identity:{v.get('field')}",
                             "provenance": "identity-not-ours",
                             "count": 1 if not isinstance(v.get("value"), dict)
                                      else sum(v["value"].values()),
                             "value": v.get("value"),
                             "why": v.get("why")})
        for a in idr.get("advisories", []):
            advisories.append({"layer": "identity", **a})

    baseline_ok = report.get("baseline") is not None
    passes = not blocking and baseline_ok
    if not baseline_ok:
        blocking.append({"category": "*", "provenance": P_UNBASELINED, "count": 0,
                         "why": "no baseline supplied — provenance unattributable"})
    missing_layers = [l for l in GATE_LAYERS if l not in layers]
    certifies = passes and not missing_layers
    derived_total = sum(b["count"] for b in blocking
                        if b.get("layer") is None and b["provenance"] in DERIVED)
    stream_bytes = sum(b["count"] for b in blocking if b.get("layer") == "streams")
    string_hits = sum(b["count"] for b in blocking if b.get("layer") == "strings")
    ident_hits = sum(1 for b in blocking if b.get("layer") == "identity")

    if passes and certifies:
        verdict = ("PASS — G1 CERTIFIED: no Autodesk-derived expression, no identical "
                   "expression-stream bytes, no Autodesk resource identifiers, identity ours")
    elif passes and not certifies:
        verdict = (f"PASS ({'+'.join(layers)} layer(s) ONLY) — NOT a G1 certification: "
                   f"{', '.join(missing_layers)} not ledgered; rerun with "
                   f"--baseline all --streams --strings --identity")
    else:
        bits = []
        if not baseline_ok:
            bits.append("no baseline supplied (provenance unattributable)")
        if derived_total:
            bits.append(f"{derived_total:,} Autodesk-derived element(s) in expression-bearing categories")
        if stream_bytes:
            bits.append(f"{stream_bytes:,} byte(s) byte-identical to baseline in expression-bearing streams")
        if string_hits:
            bits.append(f"{string_hits:,} Autodesk resource identifier(s)")
        if ident_hits:
            bits.append(f"{ident_hits} identity violation(s)")
        if not bits:
            bits.append("unattributable provenance")
        verdict = "FAIL — " + "; ".join(bits)
    return {
        "passes": passes,
        "certifies_G1": certifies,
        "layers": layers,
        "missing_layers": missing_layers,
        "strict": bool(strict),
        "verdict": verdict,
        "blocking": blocking,
        "counsel": counsel,
        "advisories": advisories[:60],
        "gap_list": [b for b in blocking
                     if b.get("layer") is None and b["provenance"] in DERIVED],
        "stream_gap_bytes": stream_bytes,
        "resource_ref_count": string_hits,
        "identity_violations": ident_hits,
    }


# ---------------------------------------------------------------------------
# text rendering
# ---------------------------------------------------------------------------
_PROV_SHORT = {P_SAMPLE: "sample", P_MODIFIED: "modified", P_CREATED: "created",
               P_CLONED: "cloned", P_COMPOSED: "composed",
               P_UNMATCHED: "unmatched", P_UNBASELINED: "unbaselined"}


def format_report(report: dict, *, show_examples: bool = True, max_classes: int = 8) -> str:
    """Human table: category x provenance counts + per-class examples."""
    lines: List[str] = []
    lines.append(f"PROVENANCE LEDGER v2 — {os.path.basename(report['candidate'])}")
    b = report.get("baseline")
    bl = report.get("baselines") or ([b] if b else [])
    if len(bl) > 1:
        lines.append("baselines (multi, union): " + ", ".join(os.path.basename(x) for x in bl))
        lines.append(f"primary baseline: {os.path.basename(b) if b else '(none)'}"
                     f"   watermark: {report.get('baseline_watermark')}"
                     f"   overlap: {report.get('baseline_id_overlap')}")
    else:
        lines.append(f"baseline: {os.path.basename(b) if b else '(none)'}"
                     f"   watermark: {report.get('baseline_watermark')}"
                     f"   overlap: {report.get('baseline_id_overlap')}")
    comp = report.get("composed")
    if comp:
        lines.append(f"baseline kind: {report.get('baseline_kind')}"
                     + (f" ({comp['pinned_id']})" if comp.get("pinned_id") else "") + " — "
                     f"{comp['inherited_ours_composed']:,} inherited elements ours by composition; "
                     f"residue of the base = {comp['baseline_residue_ids']:,} ids")
    lines.append(f"layers ledgered: {' + '.join(report.get('layers') or ['elements'])}")
    lines.append(f"host elements: {report['host_elements']:,}   "
                 f"embedded family documents: {report['embedded_family_documents']['count']:,}"
                 f" {report['embedded_family_documents']['by_provenance'] or ''}")
    tot = report.get("provenance_totals", {})
    lines.append("element totals: " + "  ".join(f"{_PROV_SHORT.get(p, p)}={tot[p]:,}"
                                               for p in PROVENANCES if tot.get(p)))
    for w in report.get("warnings", []):
        lines.append(f"WARNING: {w}")
    lines.append("")
    # --- stream ledger --------------------------------------------------------
    sl = report.get("stream_ledger")
    if sl:
        lines.append("STREAM LEDGER (byte-weighted):")
        lines.append("  " + sl["headline"])
        lines.append("  " + sl["headline_excluding_schema"])
        hdr = f"  {'stream / unit':40s} R {'inflated':>11s} {'identical':>11s} {'%ident':>7s}  class            best-baseline"
        lines.append(hdr)
        lines.append("  " + "-" * (len(hdr) - 2))
        role_flag = {"expression": "E", "schema": "S", "fingerprint": "F",
                     "host-records": "H", "other": " "}
        for r in sl["units"]:
            lines.append(f"  {r['name'][:40]:40s} {role_flag.get(r['role'],' ')} "
                         f"{r['inflated']:>11,} {r['identical_bytes']:>11,} "
                         f"{r['identical_pct']:>6.1f}%  {r['class']:16s} "
                         f"{(r.get('best_baseline') or '-')}")
        lines.append("  R: E=expression-bearing (gated)  S=schema (counsel C4)  "
                     "F=fingerprint (identity/lineage)  H=host element records")
        lines.append("")
    # --- resource refs --------------------------------------------------------
    rr = report.get("resource_refs")
    if rr is not None:
        lines.append(f"AUTODESK RESOURCE REFS (G1c): {rr['total_refs']:,} in document content"
                     f" ({rr.get('elements_with_refs', 0)} host elements carry them)"
                     f"; {rr['total_refs_schema_stream']:,} more inside the schema stream")
        for k, v in sorted(rr.get("by_pattern", {}).items(), key=lambda kv: -kv[1]):
            lines.append(f"    {k:26s} {v:>7,}")
        lines.append("")
    # --- identity -------------------------------------------------------------
    idr = report.get("identity")
    if idr is not None:
        bfi = idr.get("basic_file_info") or {}
        lines.append(f"IDENTITY (G2 policy): author={bfi.get('author')!r} "
                     f"username={bfi.get('username')!r} last_save_path={bfi.get('last_save_path')!r}")
        for v in idr.get("violations", []):
            lines.append(f"    x {v.get('field')}: {v.get('value')} — {v.get('why')}")
        for a in idr.get("advisories", []):
            lines.append(f"    ~ {a.get('field')}: {a.get('value')} — {a.get('why')}")
        if idr.get("ok"):
            lines.append("    (no identity violations)")
        lines.append("")
    # --- multi-baseline element table ------------------------------------------
    mt = report.get("multi_baseline_table")
    if mt:
        lines.append("MULTI-BASELINE ELEMENT TABLE (per baseline, then union over all):")
        for lab, counts in mt["per_baseline"].items():
            lines.append(f"    {lab:32s} " + "  ".join(f"{_PROV_SHORT.get(p,p)}={n:,}"
                                                        for p, n in counts.items()))
        lines.append(f"    {'UNION (any baseline)':32s} " + "  ".join(
            f"{_PROV_SHORT.get(p,p)}={n:,}" for p, n in mt['union'].items()))
        if mt.get("derived_attribution"):
            lines.append("    derived elements attributed to: " + ", ".join(
                f"{k}={v}" for k, v in mt["derived_attribution"].items()))
        lines.append("")
    provs = [p for p in PROVENANCES if any(
        c["counts"].get(p) for c in report["categories"].values())]
    hdr = f"{'category':44s} E " + " ".join(f"{_PROV_SHORT[p]:>10s}" for p in provs)
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for cat in CATEGORY_ORDER:
        info = report["categories"].get(cat)
        if not info:
            continue
        flag = "E" if info["expression_bearing"] else " "
        row = f"{info['label'][:44]:44s} {flag} " + " ".join(
            f"{info['counts'].get(p, 0):>10,}" for p in provs)
        lines.append(row)
    lines.append("")
    lines.append("E = expression-bearing (gated).  Per-class detail (top classes, "
                 "example ids : name):")
    for cat in CATEGORY_ORDER:
        info = report["categories"].get(cat)
        if not info:
            continue
        lines.append(f"\n[{cat}]  {info['label']}")
        shown = 0
        for cls, cinfo in info["classes"].items():
            if shown >= max_classes:
                rest = len(info["classes"]) - shown
                lines.append(f"    ... {rest} more class(es)")
                break
            counts = " ".join(f"{_PROV_SHORT[p]}={n:,}" for p, n in cinfo["counts"].items())
            lines.append(f"  {cls:40s} {counts}")
            if show_examples:
                for p, exs in (cinfo.get("examples") or {}).items():
                    bits = []
                    for e in exs:
                        nm = e.get("name") or "-"
                        s = f"{e['id']}:{nm[:38]}"
                        if e.get("derived_from"):
                            s += f" <-clone-of {e['derived_from']['class']} {e['derived_from']['id']}"
                        elif e.get("clone_of") is not None:
                            s += f" ~{e['clone_of']}({e.get('clone_similarity')})"
                        bits.append(s)
                    lines.append(f"      {_PROV_SHORT[p]:>10s}: " + ", ".join(bits))
            shown += 1
    g = report.get("gate_G1", {})
    lines.append("")
    lines.append(f"G1 GATE: {g.get('verdict')}")
    if g.get("missing_layers"):
        lines.append(f"   (layers NOT ledgered: {', '.join(g['missing_layers'])})")
    for blk in g.get("blocking", [])[:40]:
        lay = blk.get("layer", "elements")
        lines.append(f"   x [{lay[:8]:8s}] {str(blk['category'])[:34]:34s} "
                     f"{str(blk['provenance'])[:22]:22s} {blk['count']:>12,}")
    if len(g.get("blocking", [])) > 40:
        lines.append(f"   ... {len(g['blocking']) - 40} more")
    for c in g.get("counsel", []):
        lines.append(f"   ? [counsel ] {c.get('item')} {c.get('stream','')} — {c.get('why')[:120]}")
    if g.get("advisories"):
        lines.append(f"   ~ {len(g['advisories'])} advisory item(s) (lineage fingerprints / identity notes) in JSON")
    return "\n".join(lines)


# ===========================================================================
# PROVENANCE LEDGER v2 — STREAM-AWARE, MULTI-BASELINE, BYTE-WEIGHTED
# ===========================================================================
# The v1 ledger (above) walks the ElemTable only, against ONE baseline.  The
# genesis audit (docs/inbox/genesis-audit.md) showed that reports "0
# autodesk-sample" on a file whose BYTES are ~94 % Autodesk (Global/Latest =
# the sample's ADocument, Formats/Latest = Autodesk's class model, History /
# DocumentIncrementTable = sample lineage with Autodesk employee usernames)
# and that a single baseline hides product-default reproduction sourced from
# OTHER samples (DBViewProject = 0.91 clone of racbasic's; ElectricalSetting
# 46/49 fields identical to rme's).  v2 adds, without touching v1:
#
#   * stream ledger      — every stream + every partition save unit is
#                          classified by BYTES vs the baseline(s): identical /
#                          prefix-shared / % byte-identical (block matching) /
#                          ours, and reported BYTE-WEIGHTED.
#   * multi-baseline     — `provenance(doc, baselines=[...])`: an element or
#                          stream is sample-derived if it matches ANY
#                          baseline (union), attributed to WHICH baseline.
#   * embedded strings   — records / streams carrying Autodesk resource
#                          identifiers (Forge typeIds, assetlibrary_base.fbx,
#                          SunAndSky, ADSK, autodesk.com ...) are counted as
#                          `autodesk-resource-refs` (the G1c items).
#   * identity policy    — BasicFileInfo / DocumentIncrementTable must carry
#                          OUR identity (rvt.identity), never a template's.
#   * an honest gate     — G1 v2 = element layer AND zero identical bytes in
#                          the expression-bearing streams AND zero resource
#                          refs AND identity ours; Formats/Latest is reported
#                          separately as the counsel-C4 schema stream.
# ===========================================================================
import hashlib
import pickle

#: stream-level provenance classes
S_IDENTICAL = "identical"          # byte-identical to a baseline's stream/unit
S_PREFIX = "prefix-shared"         # same-named stream sharing a long common prefix
S_LINEAGE = "modified-lineage"     # >= LINEAGE_MATCH_THRESHOLD of its bytes exist in a baseline
S_OURS = "ours"                    # no meaningful baseline byte overlap
STREAM_PROVENANCES = (S_IDENTICAL, S_PREFIX, S_LINEAGE, S_OURS)

#: streams whose bytes ARE the document's authored expression: any byte
#: identical to a baseline blocks G1 (the family SAVE UNITS, Partitions/N#uK
#: for K>=1, are added dynamically — each is an embedded family document).
EXPRESSION_STREAMS = frozenset({"Global/Latest", "Global/ContentDocuments"})
#: Autodesk's serialized class model — reported SEPARATELY (counsel C4), not
#: counted in the byte-weighted headline and not a mechanical G1 blocker.
SCHEMA_STREAMS = frozenset({"Formats/Latest"})
#: identity / lineage-FINGERPRINT streams: not expression, but they carry the
#: sample's GUIDs, save history and usernames (advisory + identity policy).
FINGERPRINT_STREAMS = frozenset({"BasicFileInfo", "Global/History",
                                 "Global/DocumentIncrementTable", "Contents",
                                 "Global/PartitionTable", "TransmissionData",
                                 "PartAtom", "ProjectInformation",
                                 "RevitPreview4.0"})

LINEAGE_MATCH_THRESHOLD = 0.10     # >= 10 % byte overlap => modified-lineage
PREFIX_SHARED_FRACTION = 0.50      # common prefix >= 50 % of the shorter => prefix-shared
BIG_BLOCK = 4096                   # fixed block grid (rsync-style) for all units
SMALL_BLOCK = 256                  # finer grid for units below SMALL_UNIT_MAX
SMALL_UNIT_MAX = 4 * 1024 * 1024
CHUNK_INDEX_VERSION = 4

#: Autodesk employee usernames observed in the sample corpus' save histories
#: (genesis audit 2026-08-03).  A generated file must never carry them.
AUTODESK_EMPLOYEE_USERNAMES = frozenset({
    "campbes", "hansonje", "loboarch", "okapaw", "youyi", "zhangg",
    "gbs_subsuser6", "xuew"})

#: Autodesk resource-identifier patterns (the G1c items).  Scanned in both
#: ASCII and UTF-16LE (the scan de-widens the buffer).  'autodesk-name' is
#: 'Autodesk' NOT followed by '.', so Forge typeIds / URLs are counted once,
#: by their own more specific pattern.
RESOURCE_PATTERNS: Dict[str, str] = {
    "forge-typeid": r"autodesk\.(?:spec|unit|parameter|revit|symbol|category|generic)[.:][A-Za-z0-9_.:\-]+",
    "forge-schema-corpus": r"forge-data-schema",
    "autodesk-url": r"autodesk\.com",
    "asset-library-fbx": r"assetlibrary_base\.fbx",
    "sunandsky-asset": r"SunAndSky",
    "adsk-token": r"(?<![A-Za-z])ADSK(?![A-Za-z])",
    "revit-resource-string": r"%1!s!",
    "revit-server-string": r"Revit Default DB Server|AREXContentGenerator",
    "autodesk-name": r"[Aa]utodesk(?![.\w])",
}
_RESOURCE_RES = {k: re.compile(v.encode("latin-1")) for k, v in RESOURCE_PATTERNS.items()}


# ---------------------------------------------------------------------------
# content units — every stream, and every partition save unit, as BYTES
# ---------------------------------------------------------------------------
@dataclass
class ContentUnit:
    """One ledgerable byte-run: a whole stream, the host-document unit
    (Partitions/N unit 0) or one embedded family save unit (unit >= 1)."""
    name: str                      # 'Global/Latest', 'Partitions/21#u3', ...
    kind: str                      # 'stream' | 'host-unit' | 'save-unit'
    data: bytes                    # INFLATED (member-bearing) or logical raw bytes
    stored: int                    # bytes as stored in the container (compressed)
    guid: Optional[str] = None     # save-unit separator GUID
    stream: str = ""               # owning OLE stream name

    @property
    def base_stream(self) -> str:
        return self.stream or self.name

    def to_json(self) -> dict:
        return {"name": self.name, "kind": self.kind, "stream": self.base_stream,
                "inflated": len(self.data), "stored": self.stored,
                **({"guid": self.guid} if self.guid else {})}


def _stream_content(f, name: str) -> bytes:
    """Ledger bytes of a non-partition stream: prefix + all inflated members
    when the stream carries gzip members, else the logical (de-paged) bytes."""
    try:
        m = f.members(name)
    except Exception:
        m = []
    if m:
        try:
            return f.prefix(name) + b"".join(f.inflate_all(name))
        except Exception:
            return f.logical(name)
    return f.logical(name)


def content_units(rvt_path: str, *, with_partitions: bool = True) -> List[ContentUnit]:
    """Enumerate every ledgerable byte-run of a file, INFLATED.

    Non-partition streams become one unit each (Formats/Latest, Global/*,
    BasicFileInfo, PartAtom, RevitPreview4.0, ...).  Each ``Partitions/N``
    contributes unit 0 (``#host`` — the host document's element records) plus
    one ``save-unit`` per embedded family document (``#uK`` + its GUID).
    """
    from .container import open_rvt
    from .partitions import StreamWalker, _inflate_member
    units: List[ContentUnit] = []
    with reading_own_release(rvt_path), open_rvt(rvt_path) as f:
        for s in sorted(f.streams(), key=lambda x: x.name):
            n = s.name
            if n.startswith("Partitions/"):
                if not with_partitions:
                    continue
                try:
                    raw = f.logical(n)
                    w = StreamWalker(raw, inflate=False, keep_data=False)
                except Exception:
                    units.append(ContentUnit(n, "stream", f.logical(n), s.size, stream=n))
                    continue
                for u in w.units:
                    parts: List[bytes] = []
                    stored = 0
                    for b in w.blocks[u.first_block:u.first_block + u.n_blocks]:
                        try:
                            data, _ok, _isz = _inflate_member(
                                raw, b.member_offset, b.member_offset + b.member_len)
                        except Exception:
                            data = b""
                        parts.append(data)
                        stored += b.member_len + 26
                    kind = "host-unit" if u.index == 0 else "save-unit"
                    tag = "host" if u.index == 0 else f"u{u.index}"
                    units.append(ContentUnit(f"{n}#{tag}", kind, b"".join(parts), stored,
                                             _unit_guid_str(u.guid), stream=n))
            else:
                units.append(ContentUnit(n, "stream", _stream_content(f, n), s.size, stream=n))
    return units


# ---------------------------------------------------------------------------
# block hashing (rsync-style: fixed grid on baselines, rolling on candidate)
# ---------------------------------------------------------------------------
def _weak_hashes_grid(data: bytes, w: int):
    """Weak (a,b)-checksums of every ALIGNED w-byte block, as one uint64 array."""
    import numpy as np
    n = len(data) // w
    if n == 0:
        return None
    arr = np.frombuffer(data[:n * w], dtype=np.uint8).reshape(n, w).astype(np.uint64)
    a = arr.sum(axis=1) & np.uint64(0xFFFF)
    wts = np.arange(w, 0, -1, dtype=np.uint64)
    b = (arr @ wts) & np.uint64(0xFFFF)
    return (a << np.uint64(16)) | b


def _weak_hashes_rolling(data: bytes, w: int):
    """Weak checksums at EVERY offset (rolling window), vectorised via prefix
    sums (identical (a,b) definition as the aligned grid, mod 2^16 each)."""
    import numpy as np
    n = len(data)
    if n < w:
        return None
    x = np.frombuffer(data, dtype=np.uint8).astype(np.uint64)
    zero = np.zeros(1, dtype=np.uint64)
    s1 = np.concatenate((zero, np.cumsum(x)))
    s2 = np.concatenate((zero, np.cumsum(x * np.arange(n, dtype=np.uint64))))
    m = n - w + 1
    i = np.arange(m, dtype=np.uint64)
    A = s1[w:w + m] - s1[:m]
    B = (i + np.uint64(w)) * A - (s2[w:w + m] - s2[:m])
    return ((A & np.uint64(0xFFFF)) << np.uint64(16)) | (B & np.uint64(0xFFFF))


def _strong(b: bytes) -> bytes:
    return hashlib.blake2b(b, digest_size=8).digest()


def _is_trivial(block: bytes) -> bool:
    """A block with <= 2 distinct byte values (zero-runs, padding) is not
    evidence of copying — excluded from the identical-byte count."""
    return len(set(block[:512] + block[-512:])) <= 2 and len(set(block)) <= 2


class BaselineCorpus:
    """Block-hash index over ALL content units of one or more baseline files.

    Per unit: whole-content sha1 (identity), length, GUID, and (for units
    small enough) the raw bytes for exact common-prefix comparison.  Two
    fixed-grid block indexes (4096 B for everything, 256 B for units under
    ``SMALL_UNIT_MAX``) map block hashes to (baseline label, unit, block#).
    """

    def __init__(self):
        self.labels: List[str] = []                       # baseline labels (basename stems)
        self.paths: Dict[str, str] = {}
        self.units: Dict[Tuple[str, str], dict] = {}      # (label, unit) -> meta
        self.sha_index: Dict[bytes, List[Tuple[str, str]]] = defaultdict(list)
        self.guid_index: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.weak: Dict[int, set] = {BIG_BLOCK: set(), SMALL_BLOCK: set()}
        self.strong: Dict[int, Dict[bytes, list]] = {BIG_BLOCK: defaultdict(list),
                                                     SMALL_BLOCK: defaultdict(list)}
        self.small_bytes: Dict[Tuple[str, str], bytes] = {}
        self.bfi: Dict[str, dict] = {}                    # label -> BasicFileInfo model
        self.total_bytes = 0

    # -- build ---------------------------------------------------------------
    def add_baseline(self, path: str, *, cache_dir: Optional[str] = None,
                     verbose: bool = False) -> str:
        label = os.path.splitext(os.path.basename(path))[0]
        if label in self.paths:
            return label
        entry = _load_or_build_baseline_index(path, cache_dir=cache_dir, verbose=verbose)
        self.labels.append(label)
        self.paths[label] = os.path.abspath(path)
        self.bfi[label] = entry.get("bfi") or {}
        for name, meta in entry["units"].items():
            key = (label, name)
            self.units[key] = meta
            self.total_bytes += meta["len"]
            self.sha_index[meta["sha1"]].append(key)
            if meta.get("guid"):
                self.guid_index[meta["guid"]].append(key)
            if meta.get("bytes") is not None:
                self.small_bytes[key] = meta["bytes"]
            for w in (BIG_BLOCK, SMALL_BLOCK):
                blk = meta.get(f"blocks{w}")
                if not blk:
                    continue
                weaks, strongs = blk
                self.weak[w].update(weaks)
                for j, sh in enumerate(strongs):
                    self.strong[w][sh].append((label, name, j))
        return label

    def same_named(self, unit_name: str) -> List[Tuple[str, str]]:
        return [(lab, unit_name) for lab in self.labels if (lab, unit_name) in self.units]


def _index_content_units(units: Iterable[ContentUnit], verbose: bool = False) -> dict:
    """Per-unit meta + block hashes for a baseline (the cacheable payload)."""
    out: Dict[str, dict] = {}
    for cu in units:
        data = cu.data
        meta = {"len": len(data), "sha1": hashlib.sha1(data).digest(),
                "kind": cu.kind, "stream": cu.base_stream, "stored": cu.stored,
                "guid": cu.guid}
        # raw bytes (exact common-prefix comparison) and the fine 256-byte
        # grid are kept for OLE STREAMS only (globals / identity streams);
        # partition units use the 4 KB grid + whole-sha identity, so a
        # 700 MB partition corpus indexes to a few MB, not 700 MB.
        is_stream = cu.kind == "stream"
        if is_stream and len(data) <= SMALL_UNIT_MAX:
            meta["bytes"] = data
        for w, limit in ((BIG_BLOCK, None), (SMALL_BLOCK, SMALL_UNIT_MAX)):
            if limit is not None and (len(data) > limit or not is_stream):
                continue
            wk = _weak_hashes_grid(data, w)
            if wk is None:
                continue
            weaks = wk.tolist()
            strongs = [_strong(data[j * w:(j + 1) * w]) for j in range(len(weaks))]
            # drop trivial (low-entropy) blocks from the index entirely
            for j in range(len(weaks)):
                if _is_trivial(data[j * w:(j + 1) * w]):
                    weaks[j] = None
                    strongs[j] = b""
            meta[f"blocks{w}"] = ([x for x in weaks if x is not None], strongs)
        out[cu.name] = meta
    return out


def _load_or_build_baseline_index(path: str, *, cache_dir: Optional[str] = None,
                                  verbose: bool = False) -> dict:
    """The per-baseline index (unit meta + block hashes), disk-cached by
    (basename, size, mtime, version) so repeated `--baseline all` runs are cheap."""
    st = os.stat(path)
    key = f"{os.path.basename(path)}.{st.st_size}.{int(st.st_mtime)}.v{CHUNK_INDEX_VERSION}.pkl"
    cache_path = os.path.join(cache_dir, key) if cache_dir else None
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as fh:
                return pickle.load(fh)
        except Exception:
            pass
    t0 = None
    if verbose:
        import time as _t
        t0 = _t.time()
        print(f"[stream-ledger] indexing baseline {os.path.basename(path)} ...",
              file=__import__("sys").stderr)
    units = content_units(path)
    entry = {"units": _index_content_units(units, verbose=verbose),
             "path": os.path.abspath(path), "size": st.st_size,
             "version": CHUNK_INDEX_VERSION}
    # the baseline's declared identity (for the identity-policy check)
    try:
        from . import stream_encoders as _se
        bfi_unit = next((u for u in units if u.name == "BasicFileInfo"), None)
        entry["bfi"] = _bfi_identity(_se.decode_basic_file_info(bfi_unit.data)) if bfi_unit else {}
    except Exception:
        entry["bfi"] = {}
    if verbose and t0 is not None:
        import time as _t
        print(f"[stream-ledger]   {sum(len(u.data) for u in units):,} inflated bytes, "
              f"{len(units)} units, {(_t.time() - t0):.1f}s", file=__import__("sys").stderr)
    if cache_path:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_path, "wb") as fh:
                pickle.dump(entry, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass
    return entry


def build_baseline_corpus(paths: Iterable[str], *, cache_dir: Optional[str] = None,
                          verbose: bool = False) -> BaselineCorpus:
    corpus = BaselineCorpus()
    for p in paths:
        if p and os.path.exists(p):
            corpus.add_baseline(p, cache_dir=cache_dir, verbose=verbose)
    return corpus


def _common_prefix_len(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    if n == 0:
        return 0
    if a[:n] == b[:n]:
        return n
    try:
        import numpy as np
        av = np.frombuffer(a, dtype=np.uint8, count=n)
        bv = np.frombuffer(b, dtype=np.uint8, count=n)
        neq = np.flatnonzero(av != bv)
        return int(neq[0]) if neq.size else n
    except Exception:
        i = 0
        while i < n and a[i] == b[i]:
            i += 1
        return i


def _match_unit_bytes(data: bytes, corpus: BaselineCorpus, w: int
                      ) -> Tuple[List[Tuple[int, int]], Counter, Counter]:
    """Rolling match of ``data`` against the corpus block index of size w.

    Returns (matched byte ranges [start,end), matched bytes attributed per
    baseline label, matched bytes per (label, unit)).  Greedy non-overlapping:
    a verified match at offset p claims [p, p+w) and matching resumes at p+w.
    Trivial (low-entropy) blocks were never indexed, so they never match.
    """
    ranges: List[Tuple[int, int]] = []
    per_label: Counter = Counter()
    per_unit: Counter = Counter()
    weakset = corpus.weak.get(w)
    strong = corpus.strong.get(w)
    if not weakset or len(data) < w or not strong:
        return ranges, per_label, per_unit
    weak = _weak_hashes_rolling(data, w)
    if weak is None:
        return ranges, per_label, per_unit
    import numpy as np
    keys = np.fromiter(weakset, dtype=np.uint64, count=len(weakset))
    hits = np.flatnonzero(np.isin(weak, keys))
    last = 0
    for p in hits.tolist():
        if p < last:
            continue
        blk = data[p:p + w]
        who = strong.get(_strong(blk))
        if not who:
            continue
        ranges.append((p, p + w))
        last = p + w
        # attribute the block once per baseline label that has it
        seen_labels: Set[str] = set()
        for lab, uname, _j in who:
            if lab in seen_labels:
                continue
            seen_labels.add(lab)
            per_label[lab] += w
            per_unit[(lab, uname)] += w
    return ranges, per_label, per_unit


def _merged_len(ranges: List[Tuple[int, int]]) -> int:
    if not ranges:
        return 0
    ranges = sorted(ranges)
    total = 0
    cs, ce = ranges[0]
    for s, e in ranges[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            total += ce - cs
            cs, ce = s, e
    total += ce - cs
    return total


# ---------------------------------------------------------------------------
# the stream ledger
# ---------------------------------------------------------------------------
def _unit_role(cu: ContentUnit) -> Tuple[bool, str]:
    """(expression_bearing, role) for a content unit.

    role: 'expression' (gated), 'schema' (counsel C4, reported separately),
    'fingerprint' (identity / lineage advisory), 'host-records' (the
    element records — provenance is the ELEMENT ledger's job), 'other'.
    """
    name = cu.base_stream
    if cu.kind == "save-unit":
        return True, "expression"          # an embedded family DOCUMENT
    if cu.kind == "host-unit":
        return False, "host-records"
    if name in EXPRESSION_STREAMS:
        return True, "expression"
    if name in SCHEMA_STREAMS:
        return False, "schema"
    if name in FINGERPRINT_STREAMS or name == "Global/ElemTable":
        return False, "fingerprint"
    return False, "other"


def stream_ledger(rvt_path: str, corpus: BaselineCorpus, *,
                  units: Optional[List[ContentUnit]] = None) -> dict:
    """Classify every stream / save unit of ``rvt_path`` against the corpus.

    Per unit: bytes byte-identical to some baseline (block cover, plus exact
    whole-unit sha1 identity and exact same-named common prefix), the class
    (identical / prefix-shared / modified-lineage / ours), the best-matching
    baseline (WHICH sample the bytes come from) and per-baseline byte counts.
    Rolled up BYTE-WEIGHTED: of N inflated bytes, X% identical-to-baseline,
    Y% modified-lineage (the non-identical remainder of streams that descend
    from a baseline), Z% ours — with the schema stream (Formats/Latest)
    accounted separately.
    """
    units = units if units is not None else content_units(rvt_path)
    rows: List[dict] = []
    tot = {"inflated": 0, "identical": 0, "lineage_remainder": 0, "ours": 0}
    tot_ex = {"inflated": 0, "identical": 0, "lineage_remainder": 0, "ours": 0}
    for cu in units:
        expression, role = _unit_role(cu)
        n = len(cu.data)
        sha = hashlib.sha1(cu.data).digest()
        row: dict = {**cu.to_json(), "role": role,
                     "expression_bearing": expression}
        # (1) exact whole-unit identity (any baseline unit, any name)
        ident_keys = corpus.sha_index.get(sha) or []
        # (2) same-named counterpart per baseline: exact common prefix
        counterparts = corpus.same_named(cu.name)
        if cu.guid:                                   # save units also pair by GUID
            counterparts = list({*counterparts, *(tuple(k) for k in corpus.guid_index.get(cu.guid, []))})
        common: Dict[str, int] = {}
        for lab, uname in counterparts:
            other = corpus.small_bytes.get((lab, uname))
            if other is not None:
                common[f"{lab}:{uname}"] = _common_prefix_len(cu.data, other)
        # (3) rolling block cover (4096 always; 256 too for small units)
        ranges: List[Tuple[int, int]] = []
        per_label: Counter = Counter()
        per_unit: Counter = Counter()
        r1, pl1, pu1 = _match_unit_bytes(cu.data, corpus, BIG_BLOCK)
        ranges += r1
        per_label += pl1
        per_unit += pu1
        if n <= SMALL_UNIT_MAX:
            r2, pl2, pu2 = _match_unit_bytes(cu.data, corpus, SMALL_BLOCK)
            covered = _merged_len(r1)
            covered_both = _merged_len(r1 + r2)
            if covered_both > covered:
                ranges += r2
                for lab, v in pl2.items():
                    per_label[lab] = max(per_label[lab], v)
                for k, v in pu2.items():
                    per_unit[k] = max(per_unit[k], v)
        matched = _merged_len(ranges)
        # identical bytes = whole identity, else the block cover, else a
        # same-named common prefix long enough to be copying evidence (a
        # <256-byte shared FORMAT HEADER on an empty stream is not).
        best_prefix = max(common.values(), default=0)
        prefix_evidence = best_prefix if best_prefix >= SMALL_BLOCK else 0
        identical_bytes = n if ident_keys else max(matched, prefix_evidence)
        identical_bytes = min(identical_bytes, n)
        ratio = identical_bytes / n if n else 0.0
        # class
        if ident_keys or (n and identical_bytes == n):
            cls = S_IDENTICAL
        elif counterparts and best_prefix >= PREFIX_SHARED_FRACTION * n and n:
            cls = S_PREFIX
        elif ratio >= LINEAGE_MATCH_THRESHOLD:
            cls = S_LINEAGE
        else:
            cls = S_OURS
        # attribution: which baseline(s) own the bytes
        attrib: Counter = Counter(per_label)
        for lab, uname in ident_keys:
            attrib[lab] = max(attrib[lab], n)
        for key, cp in common.items():
            lab = key.split(":", 1)[0]
            attrib[lab] = max(attrib[lab], cp)
        best_label = attrib.most_common(1)[0][0] if attrib else None
        row.update({
            "class": cls,
            "identical_bytes": identical_bytes,
            "identical_pct": round(100.0 * ratio, 2),
            # the three buckets PARTITION the unit's bytes (sum == inflated):
            # the non-identical remainder of a stream that descends from a
            # baseline is 'modified-lineage'; of an 'ours' stream it is ours.
            "lineage_remainder_bytes": (n - identical_bytes) if cls != S_OURS else 0,
            "ours_bytes": (n - identical_bytes) if cls == S_OURS else 0,
            "best_baseline": best_label,
            "attribution": {lab: min(v, n) for lab, v in attrib.most_common(6)},
            "identical_to": sorted({f"{lab}:{u}" for lab, u in ident_keys}),
            "common_prefix": common,
            "top_matched_units": [f"{lab}:{u}" for (lab, u), _v in per_unit.most_common(3)],
        })
        rows.append(row)
        # totals: everything counts in `tot`; `tot_ex` excludes the schema stream
        tot["inflated"] += n
        tot["identical"] += identical_bytes
        tot["lineage_remainder"] += row["lineage_remainder_bytes"]
        tot["ours"] += row["ours_bytes"]
        if role != "schema":
            tot_ex["inflated"] += n
            tot_ex["identical"] += identical_bytes
            tot_ex["lineage_remainder"] += row["lineage_remainder_bytes"]
            tot_ex["ours"] += row["ours_bytes"]

    def _pct(d: dict, k: str) -> float:
        return round(100.0 * d[k] / d["inflated"], 2) if d["inflated"] else 0.0

    def _headline(d: dict, label: str) -> str:
        return (f"{label}: of {d['inflated']:,} total inflated bytes, "
                f"{_pct(d, 'identical')}% identical-to-baseline, "
                f"{_pct(d, 'lineage_remainder')}% modified-lineage, "
                f"{_pct(d, 'ours')}% ours")

    ledger = {
        "candidate": os.path.abspath(rvt_path),
        "baselines": [{"label": lab, "path": corpus.paths[lab]} for lab in corpus.labels],
        "block_sizes": [BIG_BLOCK, SMALL_BLOCK],
        "units": rows,
        "totals": {**tot, "identical_pct": _pct(tot, "identical"),
                   "lineage_remainder_pct": _pct(tot, "lineage_remainder"),
                   "ours_pct": _pct(tot, "ours")},
        "totals_excluding_schema": {
            **tot_ex, "identical_pct": _pct(tot_ex, "identical"),
            "lineage_remainder_pct": _pct(tot_ex, "lineage_remainder"),
            "ours_pct": _pct(tot_ex, "ours")},
        "headline": _headline(tot, "ALL STREAMS"),
        "headline_excluding_schema": _headline(tot_ex, "EXCLUDING Formats/Latest (schema, counsel C4)"),
        "by_class": dict(Counter(r["class"] for r in rows)),
        "schema_stream": next(({"name": r["name"], "class": r["class"],
                                "identical_pct": r["identical_pct"],
                                "identical_to": r["identical_to"],
                                "note": "Autodesk's serialized class model — counsel question C4 "
                                        "(ship verbatim vs clean-room re-serialization); "
                                        "reported separately, not counted in the "
                                        "excluding-schema headline"}
                               for r in rows if r["role"] == "schema"), None),
        "expression_streams_identical_bytes": {
            r["name"]: r["identical_bytes"] for r in rows
            if r["expression_bearing"] and r["identical_bytes"] > 0},
        "fingerprints": [
            {"name": r["name"], "class": r["class"], "identical_pct": r["identical_pct"],
             "best_baseline": r["best_baseline"]}
            for r in rows if r["role"] == "fingerprint" and r["class"] != S_OURS],
    }
    return ledger


# ---------------------------------------------------------------------------
# embedded Autodesk resource identifiers (the G1c items)
# ---------------------------------------------------------------------------
def _dewidened(buf: bytes) -> bytes:
    """Collapse UTF-16LE ASCII-range text so one latin-1 regex pass sees
    both encodings (dropping NULs never removes an ASCII match)."""
    return buf.replace(b"\x00", b"") if b"\x00" in buf else buf


def scan_resource_refs(buf: bytes, *, samples: int = 0) -> Dict[str, dict]:
    """Count Autodesk resource identifiers in a byte buffer.

    Returns {pattern: {"count": n, "examples": [...]}} for patterns that hit."""
    text = _dewidened(buf)
    out: Dict[str, dict] = {}
    for key, rx in _RESOURCE_RES.items():
        found = rx.findall(text)
        if not found:
            continue
        entry = {"count": len(found)}
        if samples:
            uniq: List[str] = []
            for m in found:
                s = (m if isinstance(m, (bytes, bytearray)) else m[0]).decode("latin-1", "replace")
                if s not in uniq:
                    uniq.append(s)
                    if len(uniq) >= samples:
                        break
            entry["examples"] = uniq
        out[key] = entry
    return out


def resource_ref_report(rvt_path: str, doc=None, *,
                        units: Optional[List[ContentUnit]] = None) -> dict:
    """Autodesk resource-identifier census: per stream/unit and (if ``doc`` is
    given) per host ELEMENT (which of OUR records carry Autodesk resource ids).

    Every hit is an `autodesk-resource-refs` item: a reference-to /
    identifier-of an Autodesk artefact inside the file (G1c).  The schema
    stream is scanned but tallied separately (its typeIds are the class
    model, counsel C4)."""
    units = units if units is not None else content_units(rvt_path)
    per_unit: List[dict] = []
    totals: Counter = Counter()
    totals_schema: Counter = Counter()
    for cu in units:
        hits = scan_resource_refs(cu.data, samples=3)
        if not hits:
            continue
        _exp, role = _unit_role(cu)
        n = sum(v["count"] for v in hits.values())
        per_unit.append({"unit": cu.name, "role": role, "hits": hits, "total": n})
        (totals_schema if role == "schema" else totals).update(
            {k: v["count"] for k, v in hits.items()})
    elements: List[dict] = []
    elem_by_pattern: Counter = Counter()
    if doc is not None:
        for eid in sorted(getattr(doc, "et_by_id", {}) or {}):
            bufs = [(_payload(doc, eid, s) or b"") for s in (101, 102, 103)]
            hits = scan_resource_refs(b"".join(bufs), samples=2)
            if not hits:
                continue
            elements.append({"id": eid, "class": _cls(doc, eid),
                             "patterns": {k: v["count"] for k, v in hits.items()},
                             "examples": {k: v.get("examples", []) for k, v in hits.items()}})
            for k in hits:
                elem_by_pattern[k] += 1
    total_refs = sum(totals.values())
    return {
        "total_refs": total_refs,                     # document content (schema excluded)
        "total_refs_schema_stream": sum(totals_schema.values()),
        "by_pattern": dict(totals),
        "by_pattern_schema_stream": dict(totals_schema),
        "units": per_unit,
        "elements_with_refs": len(elements),
        "elements_by_pattern": dict(elem_by_pattern),
        "elements": elements[:200],
        "elements_truncated": max(0, len(elements) - 200),
        "patterns": RESOURCE_PATTERNS,
    }


# ---------------------------------------------------------------------------
# identity policy (rvt.identity): the file must assert OUR identity
# ---------------------------------------------------------------------------
def _bfi_identity(model: dict) -> dict:
    keys = ("author", "client_app_name", "format", "build", "username",
            "last_save_path", "unique_document_guid", "central_episode_guid",
            "central_model_identity", "model_identity", "locale")
    return {k: model.get(k) for k in keys}


def identity_report(rvt_path: str, corpus: Optional[BaselineCorpus] = None, *,
                    units: Optional[List[ContentUnit]] = None) -> dict:
    """Check the identity block against the rvt.identity policy.

    BLOCKING violations: an Autodesk employee username (BasicFileInfo or any
    DocumentIncrementTable save episode), a document / episode GUID inherited
    from a baseline sample, a template file path in last_save_path, or an
    author string asserting 'Autodesk Revit' authorship (we never claim an
    origin we don't have).  ADVISORY: author != our product placeholder is the
    open counsel-C1 wording question, recorded, not blocking."""
    from . import stream_encoders as _se
    try:
        from . import identity as _ident
        our_author = getattr(_ident, "DEFAULT_AUTHOR", None)
        our_client = getattr(_ident, "DEFAULT_CLIENT_APP", None)
    except Exception:
        our_author = our_client = None
    units = units if units is not None else content_units(rvt_path, with_partitions=False)
    by_name = {u.name: u for u in units}
    violations: List[dict] = []
    advisories: List[dict] = []
    bfi: dict = {}
    u = by_name.get("BasicFileInfo")
    if u is not None:
        try:
            bfi = _bfi_identity(_se.decode_basic_file_info(u.data))
        except Exception as e:  # pragma: no cover
            advisories.append({"field": "BasicFileInfo", "why": f"decode failed: {e}"})
    if bfi:
        author = (bfi.get("author") or "")
        if author.strip().lower() == "autodesk revit":
            violations.append({"field": "author", "value": author,
                               "why": "asserts Autodesk authorship — a template identity, never claim an origin we don't have"})
        elif our_author and author != our_author:
            advisories.append({"field": "author", "value": author,
                               "why": f"not our product identity ({our_author!r}) — counsel C1 wording question"})
        client = (bfi.get("client_app_name") or "")
        if client.strip().lower() == "revitapplication":
            violations.append({"field": "client_app_name", "value": client,
                               "why": "template client identity inherited"})
        uname = (bfi.get("username") or "")
        if uname.lower() in AUTODESK_EMPLOYEE_USERNAMES:
            violations.append({"field": "username", "value": uname,
                               "why": "Autodesk employee username"})
        lsp = (bfi.get("last_save_path") or "")
        if "\\" in lsp or "/" in lsp or "autodesk" in lsp.lower():
            violations.append({"field": "last_save_path", "value": lsp,
                               "why": "template file path leaked (must be a bare filename or empty)"})
        if corpus is not None:
            for lab, bmodel in corpus.bfi.items():
                if not bmodel:
                    continue
                for gk in ("unique_document_guid", "central_episode_guid"):
                    v = (bfi.get(gk) or "").lower()
                    bv = (bmodel.get(gk) or "").lower()
                    if v and bv and v == bv and v != "00000000-0000-0000-0000-000000000000":
                        violations.append({"field": gk, "value": v, "baseline": lab,
                                           "why": "document GUID inherited from a sample (identity is theirs)"})
                if bmodel.get("last_save_path") and bfi.get("last_save_path") == bmodel.get("last_save_path"):
                    violations.append({"field": "last_save_path", "value": bfi.get("last_save_path"),
                                       "baseline": lab, "why": "sample save path inherited"})
    # DocumentIncrementTable usernames (one per save episode)
    dit_users: Counter = Counter()
    u = by_name.get("Global/DocumentIncrementTable")
    if u is not None:
        try:
            data = u.data
            if data[:8] == _prefix_bytes_or(data, "Global/DocumentIncrementTable"):
                data = data[8:]
            m = _se.decode_increment_table(data)
            for r in (m.get("records") or []):
                dit_users[r.get("username", "")] += 1
        except Exception as e:
            advisories.append({"field": "DocumentIncrementTable", "why": f"decode failed: {e}"})
    employees = {n: c for n, c in dit_users.items() if n.lower() in AUTODESK_EMPLOYEE_USERNAMES}
    if employees:
        violations.append({
            "field": "DocumentIncrementTable.username",
            "value": dict(sorted(employees.items(), key=lambda kv: -kv[1])),
            "why": (f"{sum(employees.values())} of {sum(dit_users.values())} save episodes are signed by "
                    f"Autodesk employee usernames — the sample's chain of custody, in our bytes")})
    return {
        "basic_file_info": bfi,
        "our_identity": {"author": our_author, "client_app_name": our_client},
        "dit_usernames": dict(dit_users),
        "violations": violations,
        "advisories": advisories,
        "ok": not violations,
    }


def _prefix_bytes_or(data: bytes, name: str) -> bytes:
    try:
        from .stream_encoders import global_prefix
        return global_prefix(name)
    except Exception:
        return data[:0]


# ---------------------------------------------------------------------------
# multi-baseline ELEMENT classification (union with attribution)
# ---------------------------------------------------------------------------
_PROV_RANK = {P_SAMPLE: 0, P_MODIFIED: 1, P_CLONED: 2, P_CREATED: 3,
              P_UNMATCHED: 4, P_UNBASELINED: 5}


def baseline_label(doc) -> str:
    p = getattr(doc, "source_path", None) or getattr(doc, "project", "") or "baseline"
    return os.path.splitext(os.path.basename(str(p)))[0]


def classify_elements_multi(doc, baselines: List) -> Dict[int, ElementVerdict]:
    """Union classification against SEVERAL baseline Documents.

    An element is sample-derived if it is derived against ANY baseline
    (precedence sample > modified > cloned > created > unmatched); the
    winning verdict carries ``attribution`` = the baseline that explained it
    and ``baselines`` = the per-baseline reading.  This is what surfaces
    product-default reproduction sourced from a DIFFERENT sample than the
    one the candidate descends from (audit §B3)."""
    if not baselines:
        return classify_elements(doc, None)
    if len(baselines) == 1:
        vs = classify_elements(doc, baselines[0])
        lab = baseline_label(baselines[0])
        for v in vs.values():
            v.attribution = lab
            v.baselines = {lab: _brief_verdict(v)}
        return vs
    per: List[Tuple[str, Dict[int, ElementVerdict]]] = []
    for b in baselines:
        per.append((baseline_label(b), classify_elements(doc, b)))
    out: Dict[int, ElementVerdict] = {}
    for eid in sorted(doc.et_by_id):
        best: Optional[Tuple[Tuple[int, float], str, ElementVerdict]] = None
        readings: Dict[str, str] = {}
        for lab, vs in per:
            v = vs.get(eid)
            if v is None:
                continue
            readings[lab] = _brief_verdict(v)
            key = (_PROV_RANK.get(v.provenance, 9), -(v.clone_similarity or 0.0))
            if best is None or key < best[0]:
                best = (key, lab, v)
        assert best is not None
        _k, lab, v = best
        w = ElementVerdict(v.eid, v.cls, v.category, v.provenance, v.reason,
                           list(v.lineage), v.clone_of, v.clone_similarity)
        w.attribution = lab
        w.baselines = readings
        if v.provenance in (P_SAMPLE, P_MODIFIED, P_CLONED) and lab:
            w.reason = f"[vs {lab}] " + (w.reason or "")
        out[eid] = w
    return out


def _brief_verdict(v: ElementVerdict) -> str:
    if v.provenance == P_CLONED and v.clone_of is not None:
        return f"{v.provenance} (~{v.clone_of} {v.clone_similarity:.2f})"
    if v.provenance == P_CLONED and v.lineage:
        return f"{v.provenance} (via {v.lineage[0].get('class')})"
    if v.clone_similarity and v.provenance == P_CREATED:
        return f"{v.provenance} (max sim {v.clone_similarity:.2f})"
    return v.provenance


__all__ = [
    "provenance", "classify_elements", "classify_units", "legal_category",
    "category_for_class", "gate_G1", "format_report", "watermark",
    "embedded_units", "CATEGORIES", "CATEGORY_ORDER", "PROVENANCES",
    "P_SAMPLE", "P_MODIFIED", "P_CREATED", "P_CLONED", "P_COMPOSED", "P_UNMATCHED",
    "P_UNBASELINED", "ElementVerdict", "ComposedBaseline", "same_records",
    # v2 stream-aware / multi-baseline / string / identity ledger
    "ContentUnit", "content_units", "BaselineCorpus", "build_baseline_corpus",
    "stream_ledger", "scan_resource_refs", "resource_ref_report",
    "identity_report", "classify_elements_multi", "baseline_label",
    "STREAM_PROVENANCES", "S_IDENTICAL", "S_PREFIX", "S_LINEAGE", "S_OURS",
    "EXPRESSION_STREAMS", "SCHEMA_STREAMS", "FINGERPRINT_STREAMS",
    "AUTODESK_EMPLOYEE_USERNAMES", "RESOURCE_PATTERNS",
]
