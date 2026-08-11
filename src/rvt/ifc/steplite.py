"""rvt.ifc.steplite -- a stdlib-only IFC4 STEP reader for tekton's IFC READ
paths (perf-deps stream).

WHY.  The plugin's IFC input routes (``rvt.ifc.intent`` -- the placement-true
resolved intent behind ``frontdoor author --ifc`` -- and
``rvt.ifc.product_facts`` -- the product-facts extractor behind the IFC
family pipeline) read IFC through ``ifcopenshell``, a ~40 MB binary wheel
whose cold install on a fresh sandbox VM costs minutes.  Both modules consume
only a NARROW, line-oriented slice of IFC4: ``#id=ENTITY(args)`` records,
attribute access by name, ``is_a`` with inheritance, psets, tessellated
face sets, extruded area solids + their profiles, placements, styles.  No
geometry kernel is ever invoked (the writer bakes world coordinates into
``IfcCartesianPointList3D`` vertices; extrusions are expanded to prism
corners by ``rvt.ifc.intent`` itself).
This module implements exactly that slice in pure stdlib python, so the IFC
read routes run on a BARE interpreter with ZERO pip installs.

WHAT IT MIMICS (the call surface the read paths actually use, verified
against ifcopenshell 0.8.5 on the two reference IFCs):

* ``steplite.open(path)`` -> :class:`File` with ``schema`` (general
  version, ``IFC4X3``) / ``schema_identifier`` (``IFC4X3_ADD2``),
  ``by_type`` (subtype closure, ifcopenshell's declaration-tree DFS
  ordering), ``by_id``, ``by_guid``, ``get_inverse``.
* entities: ``.is_a()`` / ``.is_a(name)`` (case-insensitive, ancestors
  included), ``.id()``, attribute access by attribute NAME (positional
  STEP args mapped through the bundled schema tables), the inverse
  attributes ``ContainedInStructure`` / ``IsDefinedBy`` / ``IsTypedBy``.
* typed values (``IFCLABEL('x')``) -> objects with ``.is_a()`` and
  ``.wrappedValue``; enums -> plain strings; ``.T.``/``.F.`` -> bool.
* util equivalents with ifcopenshell'S OWN semantics: :func:`get_psets`
  (type psets first, occurrence overrides, ``"id"`` key last),
  :func:`get_type`, :func:`calculate_unit_scale`,
  :func:`get_local_placement` (pure-python 4x4 nested lists).

CLASSES OUTSIDE THE ATTRIBUTE SUBSET (issue #155).  The hand-transcribed
``_SCHEMA`` rows below carry attribute names for the classes the read paths
touch.  Every OTHER IFC4 entity is still placed in the hierarchy through
:mod:`rvt.ifc.ifc4_parents` (the full IFC4 class -> supertype table, our
own generated text): such an entity answers ``is_a()`` with its proper
CamelCase name and ``is_a('IfcElement')`` / ``by_type('IfcProduct')`` exactly
as ifcopenshell does, and serves the positional attributes of its nearest
transcribed ancestor (``GlobalId``/``Name``/``ObjectPlacement``/
``Representation``/``Tag`` for anything under IfcElement); only its OWN leaf
attributes raise a clear ``AttributeError``.  A class in neither table (an
IFC2X3-only or misspelt name) parses, carries ``is_a``/``id``, is returned by
``by_type`` of its exact name only, and raises on named-attribute access.

CLASS TREE PER FILE_SCHEMA (issue #337).  The tree is chosen per file from
its ``FILE_SCHEMA``: ``IFC4X3*`` files are read through the IFC4X3_ADD2 tree
(:mod:`rvt.ifc.ifc4x3_add2_parents` + the small ``_SCHEMA_IFC4X3`` row
delta -- IfcBuiltElement, IfcFacility, ``IfcProperty.Specification``,
``IfcObjectPlacement.PlacementRelTo``), so an IFC4X3 wall answers
``is_a('IfcBuiltElement')`` and ``by_type('IfcBuiltElement')`` finds it, as
ifcopenshell does; every other identifier (IFC4, IFC4X1/X2, IFC2X3) keeps
the IFC4 tree -- IFC2X3's own hierarchy and attribute orders are #159's.

WHAT IT DOES NOT DO: write IFC, evaluate derived attributes (``*`` slots
read as None), or run ``ifcopenshell.geom``/``validate``/``api`` (the
authoring and validation surfaces stay on the real library).

SELECTION.  Callers never import this directly for the fallback to work:
``rvt/ifc/_ifcos_shim/ifcopenshell`` is a package with this exact module as
its backend, appended to ``sys.path`` by the ENGINE itself when ``rvt.ifc``
is imported (:mod:`rvt.ifc._fallback`, issue #130; ``tekton_env.ensure_engine``
delegates to it) ONLY when the real ifcopenshell is absent -- try
ifcopenshell, else steplite, selected by ordinary import resolution (no
monkeypatching, no edits to the consumer modules).  ``RVT_STEPLITE_FORCE=1``
forces the shim backend even when the real library is installed (the engine
then puts the shim FIRST; used by the equivalence tests and backend A/B).

TERRITORY (perf-deps stream): this module, ``rvt/ifc/ifc4_parents.py``,
``rvt/ifc/ifc4x3_add2_parents.py``, ``rvt/ifc/_ifcos_shim/**``,
``tests/test_steplite.py``, ``docs/writer/dependency-audit.md``,
``docs/inbox/perf-deps.md`` / ``docs/inbox/steplite-parity.md``.  Imports
nothing beyond the stdlib.
"""
from __future__ import annotations

import importlib
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = [
    "STEPLITE_VERSION", "SteliteError", "StepLiteError", "open", "File",
    "Entity", "TypedValue", "get_psets", "get_type", "calculate_unit_scale",
    "get_local_placement",
]

STEPLITE_VERSION = "1.0"
IS_STEPLITE = True          # lets doctors/preflights tell the shim from the real lib


class StepLiteError(RuntimeError):
    """The STEP file cannot be parsed (not ISO-10303-21 / truncated / bad ref)."""


SteliteError = StepLiteError  # spelling alias


# ===========================================================================
# IFC4 schema subset: parent links + OWN attribute names (positional order).
# Full attribute lists are the concatenation root..leaf, exactly as STEP
# serialises them.  Hand-transcribed from the public IFC4 documentation;
# every row's parent and full attribute list is cross-checked against
# ifcopenshell 0.8.5's IFC4 declarations whenever that library is importable
# (tests/test_steplite.py::test_schema_rows_match_declarations), and
# attribute-by-attribute against get_info() on the reference IFCs.  The
# IFC4X3 tree reuses these rows with the ``_SCHEMA_IFC4X3`` delta below.
# ===========================================================================

#: UPPERCASE -> (CamelCase, parent UPPERCASE or None, own attribute names)
_SCHEMA: Dict[str, Tuple[str, Optional[str], Tuple[str, ...]]] = {
    # -- rooted object tree ------------------------------------------------
    "IFCROOT": ("IfcRoot", None, ("GlobalId", "OwnerHistory", "Name", "Description")),
    "IFCOBJECTDEFINITION": ("IfcObjectDefinition", "IFCROOT", ()),
    "IFCOBJECT": ("IfcObject", "IFCOBJECTDEFINITION", ("ObjectType",)),
    "IFCCONTEXT": ("IfcContext", "IFCOBJECTDEFINITION",
                   ("ObjectType", "LongName", "Phase", "RepresentationContexts",
                    "UnitsInContext")),
    "IFCPROJECT": ("IfcProject", "IFCCONTEXT", ()),
    "IFCPRODUCT": ("IfcProduct", "IFCOBJECT", ("ObjectPlacement", "Representation")),
    # spatial
    "IFCSPATIALELEMENT": ("IfcSpatialElement", "IFCPRODUCT", ("LongName",)),
    "IFCSPATIALSTRUCTUREELEMENT": ("IfcSpatialStructureElement", "IFCSPATIALELEMENT",
                                   ("CompositionType",)),
    "IFCSITE": ("IfcSite", "IFCSPATIALSTRUCTUREELEMENT",
                ("RefLatitude", "RefLongitude", "RefElevation", "LandTitleNumber",
                 "SiteAddress")),
    "IFCBUILDING": ("IfcBuilding", "IFCSPATIALSTRUCTUREELEMENT",
                    ("ElevationOfRefHeight", "ElevationOfTerrain", "BuildingAddress")),
    "IFCBUILDINGSTOREY": ("IfcBuildingStorey", "IFCSPATIALSTRUCTUREELEMENT",
                          ("Elevation",)),
    "IFCSPACE": ("IfcSpace", "IFCSPATIALSTRUCTUREELEMENT",
                 ("PredefinedType", "ElevationWithFlooring")),
    # elements
    "IFCELEMENT": ("IfcElement", "IFCPRODUCT", ("Tag",)),
    "IFCBUILDINGELEMENT": ("IfcBuildingElement", "IFCELEMENT", ()),
    "IFCBUILDINGELEMENTPROXY": ("IfcBuildingElementProxy", "IFCBUILDINGELEMENT",
                                ("PredefinedType",)),
    "IFCWALL": ("IfcWall", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCWALLSTANDARDCASE": ("IfcWallStandardCase", "IFCWALL", ()),
    "IFCSLAB": ("IfcSlab", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCCOVERING": ("IfcCovering", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCDOOR": ("IfcDoor", "IFCBUILDINGELEMENT",
                ("OverallHeight", "OverallWidth", "PredefinedType", "OperationType",
                 "UserDefinedOperationType")),
    "IFCWINDOW": ("IfcWindow", "IFCBUILDINGELEMENT",
                  ("OverallHeight", "OverallWidth", "PredefinedType",
                   "PartitioningType", "UserDefinedPartitioningType")),
    "IFCCOLUMN": ("IfcColumn", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCBEAM": ("IfcBeam", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCMEMBER": ("IfcMember", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCPLATE": ("IfcPlate", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCFOOTING": ("IfcFooting", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCROOF": ("IfcRoof", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCSTAIR": ("IfcStair", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCRAILING": ("IfcRailing", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCCURTAINWALL": ("IfcCurtainWall", "IFCBUILDINGELEMENT", ("PredefinedType",)),
    "IFCFURNISHINGELEMENT": ("IfcFurnishingElement", "IFCELEMENT", ()),
    # distribution (MEP / electrical) elements + ports
    "IFCDISTRIBUTIONELEMENT": ("IfcDistributionElement", "IFCELEMENT", ()),
    "IFCDISTRIBUTIONFLOWELEMENT": ("IfcDistributionFlowElement",
                                   "IFCDISTRIBUTIONELEMENT", ()),
    "IFCENERGYCONVERSIONDEVICE": ("IfcEnergyConversionDevice",
                                  "IFCDISTRIBUTIONFLOWELEMENT", ()),
    "IFCTRANSFORMER": ("IfcTransformer", "IFCENERGYCONVERSIONDEVICE",
                       ("PredefinedType",)),
    "IFCELECTRICMOTOR": ("IfcElectricMotor", "IFCENERGYCONVERSIONDEVICE",
                         ("PredefinedType",)),
    "IFCELECTRICGENERATOR": ("IfcElectricGenerator", "IFCENERGYCONVERSIONDEVICE",
                             ("PredefinedType",)),
    "IFCFLOWCONTROLLER": ("IfcFlowController", "IFCDISTRIBUTIONFLOWELEMENT", ()),
    "IFCELECTRICDISTRIBUTIONBOARD": ("IfcElectricDistributionBoard",
                                     "IFCFLOWCONTROLLER", ("PredefinedType",)),
    "IFCSWITCHINGDEVICE": ("IfcSwitchingDevice", "IFCFLOWCONTROLLER",
                           ("PredefinedType",)),
    "IFCPROTECTIVEDEVICE": ("IfcProtectiveDevice", "IFCFLOWCONTROLLER",
                            ("PredefinedType",)),
    "IFCFLOWFITTING": ("IfcFlowFitting", "IFCDISTRIBUTIONFLOWELEMENT", ()),
    "IFCCABLECARRIERFITTING": ("IfcCableCarrierFitting", "IFCFLOWFITTING",
                               ("PredefinedType",)),
    "IFCJUNCTIONBOX": ("IfcJunctionBox", "IFCFLOWFITTING", ("PredefinedType",)),
    "IFCFLOWSEGMENT": ("IfcFlowSegment", "IFCDISTRIBUTIONFLOWELEMENT", ()),
    "IFCCABLECARRIERSEGMENT": ("IfcCableCarrierSegment", "IFCFLOWSEGMENT",
                               ("PredefinedType",)),
    "IFCCABLESEGMENT": ("IfcCableSegment", "IFCFLOWSEGMENT", ("PredefinedType",)),
    "IFCFLOWSTORAGEDEVICE": ("IfcFlowStorageDevice", "IFCDISTRIBUTIONFLOWELEMENT", ()),
    "IFCELECTRICFLOWSTORAGEDEVICE": ("IfcElectricFlowStorageDevice",
                                     "IFCFLOWSTORAGEDEVICE", ("PredefinedType",)),
    "IFCFLOWTERMINAL": ("IfcFlowTerminal", "IFCDISTRIBUTIONFLOWELEMENT", ()),
    "IFCLIGHTFIXTURE": ("IfcLightFixture", "IFCFLOWTERMINAL", ("PredefinedType",)),
    "IFCOUTLET": ("IfcOutlet", "IFCFLOWTERMINAL", ("PredefinedType",)),
    "IFCELECTRICAPPLIANCE": ("IfcElectricAppliance", "IFCFLOWTERMINAL",
                             ("PredefinedType",)),
    "IFCAUDIOVISUALAPPLIANCE": ("IfcAudioVisualAppliance", "IFCFLOWTERMINAL",
                                ("PredefinedType",)),
    "IFCPORT": ("IfcPort", "IFCPRODUCT", ()),
    "IFCDISTRIBUTIONPORT": ("IfcDistributionPort", "IFCPORT",
                            ("FlowDirection", "PredefinedType", "SystemType")),
    # groups / systems
    "IFCGROUP": ("IfcGroup", "IFCOBJECT", ()),
    "IFCSYSTEM": ("IfcSystem", "IFCGROUP", ()),
    "IFCDISTRIBUTIONSYSTEM": ("IfcDistributionSystem", "IFCSYSTEM",
                              ("LongName", "PredefinedType")),
    "IFCZONE": ("IfcZone", "IFCSYSTEM", ("LongName",)),
    "IFCELEMENTCOMPONENT": ("IfcElementComponent", "IFCELEMENT", ()),
    "IFCDISCRETEACCESSORY": ("IfcDiscreteAccessory", "IFCELEMENTCOMPONENT",
                             ("PredefinedType",)),
    "IFCFEATUREELEMENT": ("IfcFeatureElement", "IFCELEMENT", ()),
    "IFCFEATUREELEMENTSUBTRACTION": ("IfcFeatureElementSubtraction",
                                     "IFCFEATUREELEMENT", ()),
    "IFCOPENINGELEMENT": ("IfcOpeningElement", "IFCFEATUREELEMENTSUBTRACTION",
                          ("PredefinedType",)),
    # type objects
    "IFCTYPEOBJECT": ("IfcTypeObject", "IFCOBJECTDEFINITION",
                      ("ApplicableOccurrence", "HasPropertySets")),
    "IFCTYPEPRODUCT": ("IfcTypeProduct", "IFCTYPEOBJECT",
                       ("RepresentationMaps", "Tag")),
    "IFCELEMENTTYPE": ("IfcElementType", "IFCTYPEPRODUCT", ("ElementType",)),
    "IFCBUILDINGELEMENTTYPE": ("IfcBuildingElementType", "IFCELEMENTTYPE", ()),
    "IFCBUILDINGELEMENTPROXYTYPE": ("IfcBuildingElementProxyType",
                                    "IFCBUILDINGELEMENTTYPE", ("PredefinedType",)),
    "IFCWALLTYPE": ("IfcWallType", "IFCBUILDINGELEMENTTYPE", ("PredefinedType",)),
    "IFCSLABTYPE": ("IfcSlabType", "IFCBUILDINGELEMENTTYPE", ("PredefinedType",)),
    "IFCDOORTYPE": ("IfcDoorType", "IFCBUILDINGELEMENTTYPE",
                    ("PredefinedType", "OperationType", "ParameterTakesPrecedence",
                     "UserDefinedOperationType")),
    "IFCWINDOWTYPE": ("IfcWindowType", "IFCBUILDINGELEMENTTYPE",
                      ("PredefinedType", "PartitioningType",
                       "ParameterTakesPrecedence", "UserDefinedPartitioningType")),
    "IFCELEMENTCOMPONENTTYPE": ("IfcElementComponentType", "IFCELEMENTTYPE", ()),
    "IFCDISCRETEACCESSORYTYPE": ("IfcDiscreteAccessoryType", "IFCELEMENTCOMPONENTTYPE",
                                 ("PredefinedType",)),
    "IFCDISTRIBUTIONELEMENTTYPE": ("IfcDistributionElementType", "IFCELEMENTTYPE", ()),
    "IFCDISTRIBUTIONFLOWELEMENTTYPE": ("IfcDistributionFlowElementType",
                                       "IFCDISTRIBUTIONELEMENTTYPE", ()),
    "IFCFLOWCONTROLLERTYPE": ("IfcFlowControllerType",
                              "IFCDISTRIBUTIONFLOWELEMENTTYPE", ()),
    "IFCELECTRICDISTRIBUTIONBOARDTYPE": ("IfcElectricDistributionBoardType",
                                         "IFCFLOWCONTROLLERTYPE", ("PredefinedType",)),
    "IFCENERGYCONVERSIONDEVICETYPE": ("IfcEnergyConversionDeviceType",
                                      "IFCDISTRIBUTIONFLOWELEMENTTYPE", ()),
    "IFCTRANSFORMERTYPE": ("IfcTransformerType", "IFCENERGYCONVERSIONDEVICETYPE",
                           ("PredefinedType",)),
    "IFCFLOWTERMINALTYPE": ("IfcFlowTerminalType",
                            "IFCDISTRIBUTIONFLOWELEMENTTYPE", ()),
    "IFCLIGHTFIXTURETYPE": ("IfcLightFixtureType", "IFCFLOWTERMINALTYPE",
                            ("PredefinedType",)),
    # relationships
    "IFCRELATIONSHIP": ("IfcRelationship", "IFCROOT", ()),
    "IFCRELDECOMPOSES": ("IfcRelDecomposes", "IFCRELATIONSHIP", ()),
    "IFCRELAGGREGATES": ("IfcRelAggregates", "IFCRELDECOMPOSES",
                         ("RelatingObject", "RelatedObjects")),
    "IFCRELNESTS": ("IfcRelNests", "IFCRELDECOMPOSES",
                    ("RelatingObject", "RelatedObjects")),
    "IFCRELVOIDSELEMENT": ("IfcRelVoidsElement", "IFCRELDECOMPOSES",
                           ("RelatingBuildingElement", "RelatedOpeningElement")),
    "IFCRELCONNECTS": ("IfcRelConnects", "IFCRELATIONSHIP", ()),
    "IFCRELCONTAINEDINSPATIALSTRUCTURE": ("IfcRelContainedInSpatialStructure",
                                          "IFCRELCONNECTS",
                                          ("RelatedElements", "RelatingStructure")),
    "IFCRELFILLSELEMENT": ("IfcRelFillsElement", "IFCRELCONNECTS",
                           ("RelatingOpeningElement", "RelatedBuildingElement")),
    "IFCRELCONNECTSPORTS": ("IfcRelConnectsPorts", "IFCRELCONNECTS",
                            ("RelatingPort", "RelatedPort", "RealizingElement")),
    "IFCRELCONNECTSPORTTOELEMENT": ("IfcRelConnectsPortToElement", "IFCRELCONNECTS",
                                    ("RelatingPort", "RelatedElement")),
    "IFCRELASSIGNS": ("IfcRelAssigns", "IFCRELATIONSHIP",
                      ("RelatedObjects", "RelatedObjectsType")),
    "IFCRELASSIGNSTOGROUP": ("IfcRelAssignsToGroup", "IFCRELASSIGNS",
                             ("RelatingGroup",)),
    # material association: by_type() already finds these (the class names are
    # parsed), but without their attribute rows every read of .RelatingMaterial
    # / .RelatedObjects raised "outside the read-path attribute subset", so an
    # IFC's own material assignment was unreadable under the stdlib reader.
    "IFCRELASSOCIATES": ("IfcRelAssociates", "IFCRELATIONSHIP", ("RelatedObjects",)),
    "IFCRELASSOCIATESMATERIAL": ("IfcRelAssociatesMaterial", "IFCRELASSOCIATES",
                                 ("RelatingMaterial",)),
    "IFCMATERIALDEFINITION": ("IfcMaterialDefinition", None, ()),
    "IFCMATERIAL": ("IfcMaterial", "IFCMATERIALDEFINITION",
                    ("Name", "Description", "Category")),
    "IFCMATERIALLAYER": ("IfcMaterialLayer", "IFCMATERIALDEFINITION",
                         ("Material", "LayerThickness", "IsVentilated", "Name",
                          "Description", "Category", "Priority")),
    "IFCMATERIALLAYERSET": ("IfcMaterialLayerSet", "IFCMATERIALDEFINITION",
                            ("MaterialLayers", "LayerSetName", "Description")),
    "IFCMATERIALCONSTITUENT": ("IfcMaterialConstituent", "IFCMATERIALDEFINITION",
                               ("Name", "Description", "Material", "Fraction",
                                "Category")),
    "IFCMATERIALCONSTITUENTSET": ("IfcMaterialConstituentSet", "IFCMATERIALDEFINITION",
                                  ("Name", "Description", "MaterialConstituents")),
    "IFCMATERIALLIST": ("IfcMaterialList", None, ("Materials",)),
    "IFCRELDEFINES": ("IfcRelDefines", "IFCRELATIONSHIP", ()),
    "IFCRELDEFINESBYPROPERTIES": ("IfcRelDefinesByProperties", "IFCRELDEFINES",
                                  ("RelatedObjects", "RelatingPropertyDefinition")),
    "IFCRELDEFINESBYTYPE": ("IfcRelDefinesByType", "IFCRELDEFINES",
                            ("RelatedObjects", "RelatingType")),
    # property sets / quantities
    "IFCPROPERTYDEFINITION": ("IfcPropertyDefinition", "IFCROOT", ()),
    "IFCPROPERTYSETDEFINITION": ("IfcPropertySetDefinition",
                                 "IFCPROPERTYDEFINITION", ()),
    "IFCPROPERTYSET": ("IfcPropertySet", "IFCPROPERTYSETDEFINITION",
                       ("HasProperties",)),
    "IFCQUANTITYSET": ("IfcQuantitySet", "IFCPROPERTYSETDEFINITION", ()),
    "IFCELEMENTQUANTITY": ("IfcElementQuantity", "IFCQUANTITYSET",
                           ("MethodOfMeasurement", "Quantities")),
    "IFCPROPERTYABSTRACTION": ("IfcPropertyAbstraction", None, ()),
    "IFCPROPERTY": ("IfcProperty", "IFCPROPERTYABSTRACTION", ("Name", "Description")),
    "IFCSIMPLEPROPERTY": ("IfcSimpleProperty", "IFCPROPERTY", ()),
    "IFCPROPERTYSINGLEVALUE": ("IfcPropertySingleValue", "IFCSIMPLEPROPERTY",
                               ("NominalValue", "Unit")),
    "IFCPROPERTYENUMERATEDVALUE": ("IfcPropertyEnumeratedValue", "IFCSIMPLEPROPERTY",
                                   ("EnumerationValues", "EnumerationReference")),
    "IFCPROPERTYLISTVALUE": ("IfcPropertyListValue", "IFCSIMPLEPROPERTY",
                             ("ListValues", "Unit")),
    "IFCPHYSICALQUANTITY": ("IfcPhysicalQuantity", None, ("Name", "Description")),
    "IFCPHYSICALSIMPLEQUANTITY": ("IfcPhysicalSimpleQuantity",
                                  "IFCPHYSICALQUANTITY", ("Unit",)),
    "IFCQUANTITYLENGTH": ("IfcQuantityLength", "IFCPHYSICALSIMPLEQUANTITY",
                          ("LengthValue", "Formula")),
    "IFCQUANTITYAREA": ("IfcQuantityArea", "IFCPHYSICALSIMPLEQUANTITY",
                        ("AreaValue", "Formula")),
    "IFCQUANTITYVOLUME": ("IfcQuantityVolume", "IFCPHYSICALSIMPLEQUANTITY",
                          ("VolumeValue", "Formula")),
    "IFCQUANTITYCOUNT": ("IfcQuantityCount", "IFCPHYSICALSIMPLEQUANTITY",
                         ("CountValue", "Formula")),
    "IFCQUANTITYWEIGHT": ("IfcQuantityWeight", "IFCPHYSICALSIMPLEQUANTITY",
                          ("WeightValue", "Formula")),
    "IFCQUANTITYTIME": ("IfcQuantityTime", "IFCPHYSICALSIMPLEQUANTITY",
                        ("TimeValue", "Formula")),
    # geometry: placements + points
    "IFCREPRESENTATIONITEM": ("IfcRepresentationItem", None, ()),
    "IFCGEOMETRICREPRESENTATIONITEM": ("IfcGeometricRepresentationItem",
                                       "IFCREPRESENTATIONITEM", ()),
    "IFCPLACEMENT": ("IfcPlacement", "IFCGEOMETRICREPRESENTATIONITEM",
                     ("Location",)),
    "IFCAXIS2PLACEMENT2D": ("IfcAxis2Placement2D", "IFCPLACEMENT",
                            ("RefDirection",)),
    "IFCAXIS2PLACEMENT3D": ("IfcAxis2Placement3D", "IFCPLACEMENT",
                            ("Axis", "RefDirection")),
    "IFCOBJECTPLACEMENT": ("IfcObjectPlacement", None, ()),
    "IFCLOCALPLACEMENT": ("IfcLocalPlacement", "IFCOBJECTPLACEMENT",
                          ("PlacementRelTo", "RelativePlacement")),
    "IFCGRIDPLACEMENT": ("IfcGridPlacement", "IFCOBJECTPLACEMENT",
                         ("PlacementLocation", "PlacementRefDirection")),
    "IFCPOINT": ("IfcPoint", "IFCGEOMETRICREPRESENTATIONITEM", ()),
    "IFCCARTESIANPOINT": ("IfcCartesianPoint", "IFCPOINT", ("Coordinates",)),
    "IFCDIRECTION": ("IfcDirection", "IFCGEOMETRICREPRESENTATIONITEM",
                     ("DirectionRatios",)),
    "IFCCARTESIANPOINTLIST": ("IfcCartesianPointList",
                              "IFCGEOMETRICREPRESENTATIONITEM", ()),
    "IFCCARTESIANPOINTLIST3D": ("IfcCartesianPointList3D", "IFCCARTESIANPOINTLIST",
                                ("CoordList", "TagList")),
    "IFCCARTESIANPOINTLIST2D": ("IfcCartesianPointList2D", "IFCCARTESIANPOINTLIST",
                                ("CoordList", "TagList")),
    # geometry: tessellation + brep subset
    "IFCTESSELLATEDITEM": ("IfcTessellatedItem", "IFCGEOMETRICREPRESENTATIONITEM",
                           ()),
    "IFCTESSELLATEDFACESET": ("IfcTessellatedFaceSet", "IFCTESSELLATEDITEM",
                              ("Coordinates",)),
    "IFCTRIANGULATEDFACESET": ("IfcTriangulatedFaceSet", "IFCTESSELLATEDFACESET",
                               ("Normals", "Closed", "CoordIndex", "PnIndex")),
    "IFCTRIANGULATEDIRREGULARNETWORK": ("IfcTriangulatedIrregularNetwork",
                                        "IFCTRIANGULATEDFACESET", ("Flags",)),
    "IFCPOLYGONALFACESET": ("IfcPolygonalFaceSet", "IFCTESSELLATEDFACESET",
                            ("Closed", "Faces", "PnIndex")),
    "IFCINDEXEDPOLYGONALFACE": ("IfcIndexedPolygonalFace", "IFCTESSELLATEDITEM",
                                ("CoordIndex",)),
    "IFCINDEXEDPOLYGONALFACEWITHVOIDS": ("IfcIndexedPolygonalFaceWithVoids",
                                         "IFCINDEXEDPOLYGONALFACE",
                                         ("InnerCoordIndices",)),
    "IFCSOLIDMODEL": ("IfcSolidModel", "IFCGEOMETRICREPRESENTATIONITEM", ()),
    "IFCMANIFOLDSOLIDBREP": ("IfcManifoldSolidBrep", "IFCSOLIDMODEL", ("Outer",)),
    "IFCFACETEDBREP": ("IfcFacetedBrep", "IFCMANIFOLDSOLIDBREP", ()),
    # geometry: swept solids + the profiles / planar curves they sweep (#152)
    "IFCSWEPTAREASOLID": ("IfcSweptAreaSolid", "IFCSOLIDMODEL",
                          ("SweptArea", "Position")),
    "IFCEXTRUDEDAREASOLID": ("IfcExtrudedAreaSolid", "IFCSWEPTAREASOLID",
                             ("ExtrudedDirection", "Depth")),
    "IFCEXTRUDEDAREASOLIDTAPERED": ("IfcExtrudedAreaSolidTapered",
                                    "IFCEXTRUDEDAREASOLID", ("EndSweptArea",)),
    "IFCPROFILEDEF": ("IfcProfileDef", None, ("ProfileType", "ProfileName")),
    "IFCPARAMETERIZEDPROFILEDEF": ("IfcParameterizedProfileDef", "IFCPROFILEDEF",
                                   ("Position",)),
    "IFCRECTANGLEPROFILEDEF": ("IfcRectangleProfileDef", "IFCPARAMETERIZEDPROFILEDEF",
                               ("XDim", "YDim")),
    "IFCROUNDEDRECTANGLEPROFILEDEF": ("IfcRoundedRectangleProfileDef",
                                      "IFCRECTANGLEPROFILEDEF", ("RoundingRadius",)),
    "IFCRECTANGLEHOLLOWPROFILEDEF": ("IfcRectangleHollowProfileDef",
                                     "IFCRECTANGLEPROFILEDEF",
                                     ("WallThickness", "InnerFilletRadius",
                                      "OuterFilletRadius")),
    "IFCCIRCLEPROFILEDEF": ("IfcCircleProfileDef", "IFCPARAMETERIZEDPROFILEDEF",
                            ("Radius",)),
    "IFCCIRCLEHOLLOWPROFILEDEF": ("IfcCircleHollowProfileDef", "IFCCIRCLEPROFILEDEF",
                                  ("WallThickness",)),
    "IFCARBITRARYCLOSEDPROFILEDEF": ("IfcArbitraryClosedProfileDef", "IFCPROFILEDEF",
                                     ("OuterCurve",)),
    "IFCARBITRARYPROFILEDEFWITHVOIDS": ("IfcArbitraryProfileDefWithVoids",
                                        "IFCARBITRARYCLOSEDPROFILEDEF", ("InnerCurves",)),
    "IFCCURVE": ("IfcCurve", "IFCGEOMETRICREPRESENTATIONITEM", ()),
    "IFCBOUNDEDCURVE": ("IfcBoundedCurve", "IFCCURVE", ()),
    "IFCPOLYLINE": ("IfcPolyline", "IFCBOUNDEDCURVE", ("Points",)),
    "IFCINDEXEDPOLYCURVE": ("IfcIndexedPolyCurve", "IFCBOUNDEDCURVE",
                            ("Points", "Segments", "SelfIntersect")),
    "IFCCONNECTEDFACESET": ("IfcConnectedFaceSet", "IFCTOPOLOGICALREPRESENTATIONITEM",
                            ("CfsFaces",)),
    "IFCCLOSEDSHELL": ("IfcClosedShell", "IFCCONNECTEDFACESET", ()),
    "IFCTOPOLOGICALREPRESENTATIONITEM": ("IfcTopologicalRepresentationItem",
                                         "IFCREPRESENTATIONITEM", ()),
    "IFCFACE": ("IfcFace", "IFCTOPOLOGICALREPRESENTATIONITEM", ("Bounds",)),
    "IFCFACEBOUND": ("IfcFaceBound", "IFCTOPOLOGICALREPRESENTATIONITEM",
                     ("Bound", "Orientation")),
    "IFCFACEOUTERBOUND": ("IfcFaceOuterBound", "IFCFACEBOUND", ()),
    "IFCLOOP": ("IfcLoop", "IFCTOPOLOGICALREPRESENTATIONITEM", ()),
    "IFCPOLYLOOP": ("IfcPolyLoop", "IFCLOOP", ("Polygon",)),
    # geometry: mapped items
    "IFCMAPPEDITEM": ("IfcMappedItem", "IFCREPRESENTATIONITEM",
                      ("MappingSource", "MappingTarget")),
    "IFCREPRESENTATIONMAP": ("IfcRepresentationMap", None,
                             ("MappingOrigin", "MappedRepresentation")),
    "IFCCARTESIANTRANSFORMATIONOPERATOR": ("IfcCartesianTransformationOperator",
                                           "IFCGEOMETRICREPRESENTATIONITEM",
                                           ("Axis1", "Axis2", "LocalOrigin", "Scale")),
    "IFCCARTESIANTRANSFORMATIONOPERATOR3D": ("IfcCartesianTransformationOperator3D",
                                             "IFCCARTESIANTRANSFORMATIONOPERATOR",
                                             ("Axis3",)),
    "IFCCARTESIANTRANSFORMATIONOPERATOR3DNONUNIFORM": (
        "IfcCartesianTransformationOperator3DnonUniform",
        "IFCCARTESIANTRANSFORMATIONOPERATOR3D", ("Scale2", "Scale3")),
    # representation containers
    "IFCREPRESENTATION": ("IfcRepresentation", None,
                          ("ContextOfItems", "RepresentationIdentifier",
                           "RepresentationType", "Items")),
    "IFCSHAPEMODEL": ("IfcShapeModel", "IFCREPRESENTATION", ()),
    "IFCSHAPEREPRESENTATION": ("IfcShapeRepresentation", "IFCSHAPEMODEL", ()),
    "IFCPRODUCTREPRESENTATION": ("IfcProductRepresentation", None,
                                 ("Name", "Description", "Representations")),
    "IFCPRODUCTDEFINITIONSHAPE": ("IfcProductDefinitionShape",
                                  "IFCPRODUCTREPRESENTATION", ()),
    "IFCREPRESENTATIONCONTEXT": ("IfcRepresentationContext", None,
                                 ("ContextIdentifier", "ContextType")),
    "IFCGEOMETRICREPRESENTATIONCONTEXT": ("IfcGeometricRepresentationContext",
                                          "IFCREPRESENTATIONCONTEXT",
                                          ("CoordinateSpaceDimension", "Precision",
                                           "WorldCoordinateSystem", "TrueNorth")),
    "IFCGEOMETRICREPRESENTATIONSUBCONTEXT": ("IfcGeometricRepresentationSubContext",
                                             "IFCGEOMETRICREPRESENTATIONCONTEXT",
                                             ("ParentContext", "TargetScale",
                                              "TargetView", "UserDefinedTargetView")),
    # styles
    "IFCSTYLEDITEM": ("IfcStyledItem", "IFCREPRESENTATIONITEM",
                      ("Item", "Styles", "Name")),
    "IFCPRESENTATIONSTYLEASSIGNMENT": ("IfcPresentationStyleAssignment", None,
                                       ("Styles",)),
    "IFCPRESENTATIONSTYLE": ("IfcPresentationStyle", None, ("Name",)),
    "IFCSURFACESTYLE": ("IfcSurfaceStyle", "IFCPRESENTATIONSTYLE",
                        ("Side", "Styles")),
    "IFCPRESENTATIONITEM": ("IfcPresentationItem", None, ()),
    "IFCSURFACESTYLESHADING": ("IfcSurfaceStyleShading", "IFCPRESENTATIONITEM",
                               ("SurfaceColour", "Transparency")),
    "IFCSURFACESTYLERENDERING": ("IfcSurfaceStyleRendering", "IFCSURFACESTYLESHADING",
                                 ("DiffuseColour", "TransmissionColour",
                                  "DiffuseTransmissionColour", "ReflectionColour",
                                  "SpecularColour", "SpecularHighlight",
                                  "ReflectanceMethod")),
    "IFCCOLOURSPECIFICATION": ("IfcColourSpecification", "IFCPRESENTATIONITEM",
                               ("Name",)),
    "IFCCOLOURRGB": ("IfcColourRgb", "IFCCOLOURSPECIFICATION",
                     ("Red", "Green", "Blue")),
    # units + header-ish entities
    "IFCNAMEDUNIT": ("IfcNamedUnit", None, ("Dimensions", "UnitType")),
    "IFCSIUNIT": ("IfcSIUnit", "IFCNAMEDUNIT", ("Prefix", "Name")),
    "IFCCONVERSIONBASEDUNIT": ("IfcConversionBasedUnit", "IFCNAMEDUNIT",
                               ("Name", "ConversionFactor")),
    "IFCMEASUREWITHUNIT": ("IfcMeasureWithUnit", None,
                           ("ValueComponent", "UnitComponent")),
    "IFCUNITASSIGNMENT": ("IfcUnitAssignment", None, ("Units",)),
    "IFCPERSON": ("IfcPerson", None,
                  ("Identification", "FamilyName", "GivenName", "MiddleNames",
                   "PrefixTitles", "SuffixTitles", "Roles", "Addresses")),
    "IFCORGANIZATION": ("IfcOrganization", None,
                        ("Identification", "Name", "Description", "Roles",
                         "Addresses")),
    "IFCPERSONANDORGANIZATION": ("IfcPersonAndOrganization", None,
                                 ("ThePerson", "TheOrganization", "Roles")),
    "IFCAPPLICATION": ("IfcApplication", None,
                       ("ApplicationDeveloper", "Version", "ApplicationFullName",
                        "ApplicationIdentifier")),
    "IFCOWNERHISTORY": ("IfcOwnerHistory", None,
                        ("OwningUser", "OwningApplication", "State", "ChangeAction",
                         "LastModifiedDate", "LastModifyingUser",
                         "LastModifyingApplication", "CreationDate")),
}

#: CamelCase names of the inline typed-value wrappers the reference files +
#: product_facts._MEASURE_* tables use (measure selects), plus the segment
#: index types of IfcIndexedPolyCurve -- interior capitals cannot be
#: recovered from the all-caps STEP token, so no-arg is_a() needs the table.
_TYPED_CAMEL = {n.upper(): n for n in (
    "IfcLabel", "IfcText", "IfcIdentifier", "IfcReal", "IfcInteger", "IfcBoolean",
    "IfcLogical", "IfcCountMeasure", "IfcLengthMeasure", "IfcPositiveLengthMeasure",
    "IfcAreaMeasure", "IfcVolumeMeasure", "IfcPowerMeasure",
    "IfcElectricVoltageMeasure", "IfcElectricCurrentMeasure",
    "IfcLuminousFluxMeasure", "IfcThermodynamicTemperatureMeasure",
    "IfcNumericMeasure", "IfcRatioMeasure", "IfcMassMeasure",
    "IfcPlaneAngleMeasure", "IfcFrequencyMeasure", "IfcNormalisedRatioMeasure",
    "IfcTimeMeasure", "IfcMonetaryMeasure", "IfcTimeStamp",
    "IfcLineIndex", "IfcArcIndex", "IfcPositiveInteger",
)}

#: Rows above that deliberately go BEYOND IFC4 -- IFC4x1 additions the
#: reference writer emits: class -> its trailing attribute names absent from
#: IFC4 (they read None on IFC4 files), or None when the whole class is
#: absent from IFC4.  The declaration cross-check in the tests reads this.
_BEYOND_IFC4: Dict[str, Optional[Tuple[str, ...]]] = {
    "IFCCARTESIANPOINTLIST2D": ("TagList",),
    "IFCCARTESIANPOINTLIST3D": ("TagList",),
    "IFCTRIANGULATEDIRREGULARNETWORK": None,
}

# ---------------------------------------------------------------------------
# Per-schema deltas (issue #337).  The rows above are IFC4's.  A file whose
# FILE_SCHEMA is IFC4X3* is read through the IFC4X3_ADD2 class tree instead:
# the generated ``rvt.ifc.ifc4x3_add2_parents`` table supplies EVERY
# supertype there (IfcWall < IfcBuiltElement < IfcElement, IfcBuilding <
# IfcFacility, ...), so the rows below only replace / add / drop the
# transcribed rows whose EXISTENCE or OWN ATTRIBUTES differ in that schema
# (transcribed from the public IFC4.3 documentation; cross-checked against
# ifcopenshell's IFC4X3_ADD2 declarations by the tests).  Same row shape as
# _SCHEMA; a row's parent slot names its true IFC4X3 supertype (tested) but,
# as for every row of a class the generated table declares, the TABLE is
# what places it.  None = no such class in IFC4X3: the IFC4 row is dropped.
# ---------------------------------------------------------------------------
_SCHEMA_IFC4X3: Dict[str, Optional[Tuple[str, Optional[str], Tuple[str, ...]]]] = {
    # IfcBuildingElement(Type) was RENAMED IfcBuiltElement(Type)
    "IFCBUILDINGELEMENT": None,
    "IFCBUILTELEMENT": ("IfcBuiltElement", "IFCELEMENT", ()),
    "IFCBUILDINGELEMENTTYPE": None,
    "IFCBUILTELEMENTTYPE": ("IfcBuiltElementType", "IFCELEMENTTYPE", ()),
    # new intermediate spatial supertype: IfcBuilding < IfcFacility
    "IFCFACILITY": ("IfcFacility", "IFCSPATIALSTRUCTUREELEMENT", ()),
    # IfcProperty.Description was renamed Specification (same position)
    "IFCPROPERTY": ("IfcProperty", "IFCPROPERTYABSTRACTION", ("Name", "Specification")),
    # PlacementRelTo was hoisted from IfcLocalPlacement to IfcObjectPlacement
    # (IfcLocalPlacement's full list is unchanged; IfcGridPlacement gains it)
    "IFCOBJECTPLACEMENT": ("IfcObjectPlacement", None, ("PlacementRelTo",)),
    "IFCLOCALPLACEMENT": ("IfcLocalPlacement", "IFCOBJECTPLACEMENT",
                          ("RelativePlacement",)),
}

#: Rows kept in the IFC4X3 tree although IFC4X3_ADD2 does not declare the
#: class (same shape as _BEYOND_IFC4): IfcPresentationStyleAssignment was
#: deleted in IFC4.3 (deprecated since IFC4) but writers that merely bump the
#: FILE_SCHEMA string still emit it around their styles.
_BEYOND_IFC4X3: Dict[str, Optional[Tuple[str, ...]]] = {
    "IFCPRESENTATIONSTYLEASSIGNMENT": None,
}

#: General schema version -> (generated parents module, row delta over
#: _SCHEMA, beyond-schema allowances).  A version absent here (IFC2X3 --
#: #159 --, IFC4X1, IFC4X2, anything unrecognised) reads through IFC4's tree;
#: a schema family is added by one row here plus its delta and its table.
_TREE_SPECS: Dict[str, Tuple[str, Dict[str, Any], Dict[str, Optional[Tuple[str, ...]]]]] = {
    "IFC4": ("rvt.ifc.ifc4_parents", {}, _BEYOND_IFC4),
    "IFC4X3": ("rvt.ifc.ifc4x3_add2_parents", _SCHEMA_IFC4X3, _BEYOND_IFC4X3),
}

_SCHEMA_VERSION_RX = re.compile(r"IFC\d+(?:X\d+)?")


def _schema_version(schema_identifier: str) -> str:
    """General schema version as ifcopenshell spells it: ``IFC4X3`` for
    ``IFC4X3_ADD2`` / ``ifc4x3_tc1``, ``IFC4``, ``IFC2X3`` ...; an identifier
    of no recognisable shape is returned upper-cased as is."""
    ident = schema_identifier.upper()
    m = _SCHEMA_VERSION_RX.match(ident)
    return m.group(0) if m else ident


def _camel_guess(uname: str) -> str:
    # best effort for a name in no table: Ifc + Titlecased remainder
    return "Ifc" + uname[3:].title() if uname.startswith("IFC") else uname


# derived lookups -----------------------------------------------------------

class _Tree:
    """One schema's ENTITY class tree: the UNION of a generated class ->
    supertype table and the transcribed attribute rows.  The generated table
    places every class the schema declares (it IS the schema fact); a row's
    own parent slot only places a class the table lacks (the deliberate
    beyond-schema rows).  UPPERCASE keys throughout (STEP tokens).  One
    instance per schema version, shared by every :class:`File` of it."""
    __slots__ = ("rows", "camel", "parent", "children", "_attrs")

    def __init__(self, generated: Dict[str, Optional[str]],
                 rows: Dict[str, Tuple[str, Optional[str], Tuple[str, ...]]]):
        self.rows = rows
        self.camel: Dict[str, str] = {c.upper(): c for c in generated}
        self.camel.update({u: row[0] for u, row in rows.items()})
        self.parent: Dict[str, Optional[str]] = {
            c.upper(): (p.upper() if p else None) for c, p in generated.items()}
        for u, row in rows.items():
            self.parent.setdefault(u, row[1])
        self.children: Dict[str, List[str]] = {}
        for u, p in self.parent.items():
            if p is not None:
                self.children.setdefault(p, []).append(u)
        for kids in self.children.values():   # ifcopenshell walks subtypes() in
            kids.sort(key=self.camel.__getitem__)  # CASE-SENSITIVE CamelCase order
        self._attrs: Dict[str, Tuple[str, ...]] = {}

    def full_attrs(self, uname: str) -> Tuple[str, ...]:
        """Positional attribute names steplite can serve for ``uname``: the
        own attributes of every transcribed class on its root..leaf chain --
        the full list for a transcribed class (every transcribed class's
        supertype is transcribed too -- tested), the list of the nearest
        transcribed ancestor for any other class of the schema (a true prefix
        of its STEP arguments), ``()`` for a class in neither table."""
        got = self._attrs.get(uname)
        if got is None:
            parent = self.parent.get(uname)
            row = self.rows.get(uname)
            got = (self.full_attrs(parent) if parent else ()) + (row[2] if row else ())
            self._attrs[uname] = got
        return got

    def camel_of(self, uname: str) -> str:
        return self.camel.get(uname) or _camel_guess(uname)


_TREES: Dict[str, _Tree] = {}


def _tree_for(schema_identifier: str) -> _Tree:
    """The class tree a file is read through, by its FILE_SCHEMA identifier
    (see ``_TREE_SPECS``).  Built on first use per version, so an IFC4-only
    process never imports the IFC4X3 table."""
    version = _schema_version(schema_identifier)
    tree = _TREES.get(version)
    if tree is None:
        spec = _TREE_SPECS.get(version)
        if spec is None:
            return _tree_for("IFC4")
        module, delta, _beyond = spec
        rows = {u: row for u, row in {**_SCHEMA, **delta}.items() if row is not None}
        tree = _TREES[version] = _Tree(importlib.import_module(module).PARENT, rows)
    return tree


_TREE_IFC4 = _tree_for("IFC4")


# ===========================================================================
# STEP value model
# ===========================================================================

class TypedValue:
    """An inline typed parameter such as ``IFCLABEL('x')`` -- mirrors
    ifcopenshell's wrapped value objects (``.is_a()`` + ``.wrappedValue``)."""
    __slots__ = ("_uname", "wrappedValue")

    def __init__(self, uname: str, value: Any):
        self._uname = uname
        self.wrappedValue = value

    def is_a(self, name: Optional[str] = None):
        if name is None:      # simple types, not entities: no class tree involved
            return _TYPED_CAMEL.get(self._uname) or _camel_guess(self._uname)
        return name.upper() == self._uname

    def __repr__(self):                                        # pragma: no cover
        return f"{self.is_a()}({self.wrappedValue!r})"


class _Ref:
    """A lazy ``#id`` reference inside a parsed argument tree."""
    __slots__ = ("sid",)

    def __init__(self, sid: int):
        self.sid = sid


_ENUM_TRUE = {"T", "TRUE"}
_ENUM_FALSE = {"F", "FALSE"}
_ENUM_UNKNOWN = {"U", "UNKNOWN"}

_NUM_RX = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_NAME_RX = re.compile(r"[A-Z][A-Z0-9_]*")
_WS = " \t\r\n"


def _decode_string(s: str, i: int) -> Tuple[str, int]:
    """Decode a STEP string starting at the opening quote ``s[i] == "'"``.
    Returns (python string, index just past the closing quote).  Handles
    ``''`` (escaped quote), ``\\\\``, ``\\S\\c``, ``\\X\\hh``, ``\\X2\\...\\X0\\``."""
    out: List[str] = []
    i += 1
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "'":
            if i + 1 < n and s[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        if ch == "\\":
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            if nxt in ("S", "s") and i + 3 < n and s[i + 2] == "\\":
                out.append(chr(ord(s[i + 3]) + 128))
                i += 4
                continue
            if nxt in ("X", "x"):
                if i + 2 < n and s[i + 2] == "\\":              # \X\hh
                    out.append(chr(int(s[i + 3:i + 5], 16)))
                    i += 5
                    continue
                if s[i + 2:i + 4] in ("2\\", "4\\"):            # \X2\..\X0\
                    width = 4 if s[i + 2] == "2" else 8
                    j = s.find("\\X0\\", i + 4)
                    if j < 0:
                        raise StepLiteError("unterminated \\X2\\ escape in string")
                    hexes = s[i + 4:j]
                    for k in range(0, len(hexes), width):
                        out.append(chr(int(hexes[k:k + width], 16)))
                    i = j + 4
                    continue
            out.append(ch)                                      # lone backslash
            i += 1
            continue
        out.append(ch)
        i += 1
    raise StepLiteError("unterminated string in STEP record")


def _parse_value(s: str, i: int) -> Tuple[Any, int]:
    n = len(s)
    while i < n and s[i] in _WS:
        i += 1
    if i >= n:
        raise StepLiteError("unexpected end of arguments")
    ch = s[i]
    if ch == "$":
        return None, i + 1
    if ch == "*":
        return None, i + 1          # derived slot: read as None (documented)
    if ch == "#":
        m = re.match(r"#(\d+)", s[i:])
        if not m:
            raise StepLiteError(f"bad reference at ...{s[i:i+16]!r}")
        return _Ref(int(m.group(1))), i + m.end()
    if ch == "'":
        return _decode_string(s, i)
    if ch == ".":
        j = s.find(".", i + 1)
        if j < 0:
            raise StepLiteError(f"unterminated enum at ...{s[i:i+16]!r}")
        token = s[i + 1:j]
        if token in _ENUM_TRUE:
            return True, j + 1
        if token in _ENUM_FALSE:
            return False, j + 1
        if token in _ENUM_UNKNOWN:
            return "UNKNOWN", j + 1
        return token, j + 1
    if ch == "(":
        items: List[Any] = []
        i += 1
        while True:
            while i < n and s[i] in _WS:
                i += 1
            if i < n and s[i] == ")":
                return tuple(items), i + 1
            v, i = _parse_value(s, i)
            items.append(v)
            while i < n and s[i] in _WS:
                i += 1
            if i < n and s[i] == ",":
                i += 1
            elif i < n and s[i] == ")":
                return tuple(items), i + 1
            else:
                raise StepLiteError(f"bad aggregate near ...{s[i:i+16]!r}")
    m = _NAME_RX.match(s, i)
    if m:                                        # typed parameter IFCX(...)
        uname = m.group(0)
        j = m.end()
        while j < n and s[j] in _WS:
            j += 1
        if j < n and s[j] == "(":
            inner, j2 = _parse_value(s, j)      # parses the (...) as aggregate
            value = inner[0] if isinstance(inner, tuple) and len(inner) == 1 else inner
            return TypedValue(uname, value), j2
        raise StepLiteError(f"bare keyword {uname!r} outside typed parameter")
    m = _NUM_RX.match(s, i)
    if m:
        text = m.group(0)
        if any(c in text for c in ".eE"):
            return float(text), m.end()
        return int(text), m.end()
    raise StepLiteError(f"cannot parse value at ...{s[i:i+24]!r}")


def _parse_args(argtext: str) -> Tuple[Any, ...]:
    """``argtext`` includes the outer parentheses."""
    v, j = _parse_value(argtext, 0)
    if not isinstance(v, tuple):
        raise StepLiteError("entity arguments did not parse as an aggregate")
    return v


# ===========================================================================
# entities + file
# ===========================================================================

class Entity:
    """One ``#id=CLASS(...)`` record with ifcopenshell-shaped access."""
    __slots__ = ("_f", "_sid", "_uname", "_args")

    def __init__(self, f: "File", sid: int, uname: str, args: Tuple[Any, ...]):
        self._f = f
        self._sid = sid
        self._uname = uname
        self._args = args

    # -- ifcopenshell surface ----------------------------------------------
    def id(self) -> int:
        return self._sid

    def is_a(self, name: Optional[str] = None):
        tree = self._f._tree
        if name is None:
            return tree.camel_of(self._uname)
        target = name.upper()
        parent = tree.parent
        cur: Optional[str] = self._uname
        while cur is not None:
            if cur == target:
                return True
            cur = parent.get(cur)
        return False

    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(attr)
        tree = self._f._tree
        attrs = tree.full_attrs(self._uname)
        if attr in attrs:
            idx = attrs.index(attr)
            return self._f._resolve(self._args[idx] if idx < len(self._args) else None)
        if attr == "ContainedInStructure":
            return self._f._inverse_rel("IFCRELCONTAINEDINSPATIALSTRUCTURE",
                                        "RelatedElements", self._sid)
        if attr == "IsDefinedBy":
            return self._f._inverse_rel("IFCRELDEFINESBYPROPERTIES",
                                        "RelatedObjects", self._sid)
        if attr == "IsTypedBy":
            return self._f._inverse_rel("IFCRELDEFINESBYTYPE",
                                        "RelatedObjects", self._sid)
        if self._uname not in tree.rows:
            raise AttributeError(
                f"steplite: entity class {tree.camel_of(self._uname)} is outside the "
                f"read-path attribute subset (served: {', '.join(attrs) or 'nothing'}); "
                f"cannot read .{attr} of #{self._sid}")
        raise AttributeError(
            f"steplite: {tree.camel_of(self._uname)} has no attribute {attr!r}")

    def __repr__(self):                                        # pragma: no cover
        return f"#{self._sid}={self._uname}(...)"


class _Header:
    """Parsed ISO-10303-21 HEADER section (steplite's own API; deliberately
    NOT exposed as ``wrapped_data`` -- ifcopenshell 0.8.5 raises on the old
    ``f.wrapped_data.header`` spelling and consumers fall back to
    ``IfcApplication``, which steplite serves identically)."""
    __slots__ = ("file_description", "file_name", "file_schema")

    def __init__(self, records: Dict[str, Tuple[Any, ...]]):
        self.file_description = records.get("FILE_DESCRIPTION", ())
        self.file_name = records.get("FILE_NAME", ())
        self.file_schema = records.get("FILE_SCHEMA", ())

    @property
    def originating_system(self) -> str:
        fn = self.file_name
        return fn[5] if len(fn) > 5 and isinstance(fn[5], str) else ""


_STRING_OR_SEMI = re.compile(r"'(?:[^']|'')*'|;|/\*.*?\*/", re.S)
_RECORD_RX = re.compile(r"\s*#(\d+)\s*=\s*([A-Za-z][A-Za-z0-9_]*)\s*\(", re.S)


class File:
    """A parsed STEP file -- the subset of ifcopenshell's file surface the
    tekton read paths consume."""

    def __init__(self, path: str, text: str):
        self.path = path
        self._by_id: Dict[int, Entity] = {}
        self._by_class: Dict[str, List[int]] = {}
        self._schema = "IFC4"           # FILE_SCHEMA identifier, upper-cased
        self._tree = _TREE_IFC4         # the class tree that identifier selects
        self._guid_index: Optional[Dict[str, int]] = None
        # (rel class, related attr) -> {related id: rels naming it}; see _inverse_rel (#160)
        self._inverse_index: Dict[Tuple[str, str], Dict[int, Tuple[Entity, ...]]] = {}
        self._get_inverse_index: Optional[Dict[int, List[int]]] = None
        self._by_type_cache: Dict[str, List[Entity]] = {}
        self._parse(text)

    # -- parsing ------------------------------------------------------------
    def _statements(self, text: str) -> Iterable[str]:
        """Split on ``;`` outside strings/comments (writer emits one record
        per line, but nothing here assumes that)."""
        start = 0
        for m in _STRING_OR_SEMI.finditer(text):
            if m.group(0) == ";":
                yield text[start:m.start()]
                start = m.end()
        tail = text[start:].strip()
        if tail:
            yield tail

    def _parse(self, text: str) -> None:
        if "ISO-10303-21" not in text[:256]:
            raise StepLiteError(f"{self.path}: not an ISO-10303-21 (STEP) file")
        d0 = text.find("DATA;")
        if d0 < 0:
            raise StepLiteError(f"{self.path}: no DATA section")
        header_text = text[:d0]
        data_text = text[d0 + 5:]
        e0 = data_text.rfind("ENDSEC;")
        if e0 >= 0:
            data_text = data_text[:e0]
        # header records
        hdr: Dict[str, Tuple[Any, ...]] = {}
        for stmt in self._statements(header_text):
            m = re.match(r"\s*([A-Z][A-Z0-9_]*)\s*\(", stmt)
            if not m:
                continue
            name = m.group(1)
            if name in ("HEADER", "ENDSEC"):
                continue
            argtext = stmt[stmt.find("("):stmt.rfind(")") + 1]
            try:
                hdr[name] = _parse_args(argtext)
            except StepLiteError:
                hdr[name] = ()
        self.header = _Header(hdr)
        fs = hdr.get("FILE_SCHEMA") or ((),)
        if fs and isinstance(fs[0], tuple) and fs[0] and isinstance(fs[0][0], str):
            self._schema = fs[0][0].upper()
            self._tree = _tree_for(self._schema)
        # data records
        for stmt in self._statements(data_text):
            m = _RECORD_RX.match(stmt)
            if not m:
                if stmt.strip():
                    raise StepLiteError(
                        f"{self.path}: unparseable record {stmt.strip()[:60]!r}")
                continue
            sid = int(m.group(1))
            uname = m.group(2).upper()
            close = stmt.rfind(")")
            if close < 0:
                raise StepLiteError(f"{self.path}: record #{sid} has no ')'")
            args = _parse_args(stmt[m.end() - 1:close + 1])
            ent = Entity(self, sid, uname, args)
            self._by_id[sid] = ent
            # FILE order per class, as ifcopenshell keeps it (by_type and the
            # inverse attributes follow it; identical to id order on every
            # writer that numbers records as it emits them)
            self._by_class.setdefault(uname, []).append(sid)

    # -- value resolution ----------------------------------------------------
    def _resolve(self, raw: Any) -> Any:
        if isinstance(raw, _Ref):
            ent = self._by_id.get(raw.sid)
            if ent is None:
                raise StepLiteError(f"{self.path}: dangling reference #{raw.sid}")
            return ent
        if isinstance(raw, tuple):
            return tuple(self._resolve(v) for v in raw)
        return raw

    # -- ifcopenshell surface ------------------------------------------------
    @property
    def schema(self) -> str:
        """General schema version as ifcopenshell reports it: ``IFC4X3`` for
        a ``FILE_SCHEMA(('IFC4X3_ADD2'))`` file, ``IFC4`` / ``IFC2X3`` ..."""
        return _schema_version(self._schema)

    @property
    def schema_identifier(self) -> str:
        """The full FILE_SCHEMA identifier (``IFC4X3_ADD2``)."""
        return self._schema

    def by_id(self, sid: int) -> Entity:
        ent = self._by_id.get(int(sid))
        if ent is None:
            raise RuntimeError(f"Instance with id {sid} not found")
        return ent

    def __getitem__(self, sid: int) -> Entity:
        return self.by_id(sid)

    def by_guid(self, guid: str) -> Entity:
        if self._guid_index is None:
            idx: Dict[str, int] = {}
            for sid, ent in self._by_id.items():
                if ent.is_a("IfcRoot") and ent._args and isinstance(ent._args[0], str):
                    idx[ent._args[0]] = sid
            self._guid_index = idx
        sid = self._guid_index.get(guid)
        if sid is None:
            raise RuntimeError(f"Instance with GlobalId '{guid}' not found")
        return self._by_id[sid]

    def by_type(self, name: str) -> List[Entity]:
        """All instances of ``name`` INCLUDING subclasses, in ifcopenshell's
        ordering: depth-first over the declaration tree of the file's schema
        (the class itself first, then subtypes in case-sensitive CamelCase
        order), instances in file order per class.  Every entity of the
        schema takes part in the closure whether or not steplite transcribes
        its attributes; a class outside it is matched by its exact name only
        (``[]`` where ifcopenshell raises)."""
        key = name.upper()
        got = self._by_type_cache.get(key)
        if got is not None:
            return list(got)
        out: List[Entity] = []
        children = self._tree.children

        def visit(uname: str) -> None:
            for sid in self._by_class.get(uname, ()):
                out.append(self._by_id[sid])
            for child in children.get(uname, ()):
                visit(child)

        visit(key)
        self._by_type_cache[key] = out
        return list(out)

    def get_inverse(self, ent: Entity) -> List[Entity]:
        """Entities whose arguments reference ``ent`` (ifcopenshell returns a
        set; steplite returns a deterministic id-ascending list -- the read
        paths only iterate it)."""
        if self._get_inverse_index is None:
            idx: Dict[int, List[int]] = {}

            def walk(raw: Any, owner: int) -> None:
                if isinstance(raw, _Ref):
                    lst = idx.setdefault(raw.sid, [])
                    if not lst or lst[-1] != owner:
                        lst.append(owner)
                elif isinstance(raw, tuple):
                    for v in raw:
                        walk(v, owner)

            for sid, e in self._by_id.items():
                for raw in e._args:
                    walk(raw, sid)
            self._get_inverse_index = idx
        ids = sorted(set(self._get_inverse_index.get(ent._sid, ())))
        return [self._by_id[i] for i in ids]

    # -- inverse attributes ---------------------------------------------------
    def _inverse_rel(self, rel_uname: str, related_attr: str, sid: int
                     ) -> Tuple[Entity, ...]:
        """The ``rel_uname`` relationships (exact class, file order) whose
        ``related_attr`` aggregate names entity ``sid`` -- each rel once,
        ``()`` for an id no rel names.  Served from a per-(class, attr) index
        built by ONE pass over the class on first use: the per-id scan it
        replaces was O(products x rels), 9 s of a 12 s resolve at 2000
        products (#160)."""
        key = (rel_uname, related_attr)
        index = self._inverse_index.get(key)
        if index is None:
            hits: Dict[int, List[Entity]] = {}
            for rid in self._by_class.get(rel_uname, ()):
                rel = self._by_id[rid]
                for e in getattr(rel, related_attr, ()) or ():
                    if isinstance(e, Entity):
                        lst = hits.setdefault(e._sid, [])
                        if not lst or lst[-1] is not rel:     # an id listed twice: rel once
                            lst.append(rel)
            index = self._inverse_index[key] = {i: tuple(v) for i, v in hits.items()}
        return index.get(sid, ())


def open(path: Any) -> File:                       # noqa: A001 (ifcopenshell name)
    """Parse ``path`` into a :class:`File` (the ifcopenshell entry point)."""
    import io
    p = os.fspath(path)
    with io.open(p, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    return File(p, text)


# ===========================================================================
# util equivalents (ifcopenshell.util.{element,unit,placement} semantics)
# ===========================================================================

def _props_of(definition: Entity) -> Dict[str, Any]:
    """Mirror ifcopenshell.util.element.get_property_definition(def):
    property name -> value, plus ``"id"`` (the definition's id) LAST."""
    props: Dict[str, Any] = {}
    cls = definition.is_a()
    if cls == "IfcPropertySet":
        for pr in definition.HasProperties or ():
            pcls = pr.is_a()
            if pcls == "IfcPropertySingleValue":
                v = pr.NominalValue
                props[pr.Name] = v.wrappedValue if v is not None else None
            elif pcls == "IfcPropertyEnumeratedValue":
                vals = pr.EnumerationValues
                props[pr.Name] = [v.wrappedValue for v in vals] if vals else None
            elif pcls == "IfcPropertyListValue":
                vals = pr.ListValues
                props[pr.Name] = [v.wrappedValue for v in vals] if vals else None
    elif cls == "IfcElementQuantity":
        for q in definition.Quantities or ():
            for attr in ("LengthValue", "AreaValue", "VolumeValue", "CountValue",
                         "WeightValue", "TimeValue"):
                try:
                    val = getattr(q, attr)
                except AttributeError:
                    continue
                if val is not None:
                    props[q.Name] = val
                    break
    props["id"] = definition.id()
    return props


def get_type(element: Entity) -> Optional[Entity]:
    """ifcopenshell.util.element.get_type (IFC4 path)."""
    if element.is_a("IfcTypeObject"):
        return element
    typed_by = getattr(element, "IsTypedBy", ()) or ()
    if typed_by:
        return typed_by[0].RelatingType
    return None


def get_psets(element: Entity, psets_only: bool = False, qtos_only: bool = False,
              should_inherit: bool = True, verbose: bool = False
              ) -> Dict[str, Dict[str, Any]]:
    """ifcopenshell.util.element.get_psets, default (non-verbose) semantics:
    the TYPE's psets first, occurrence psets merged over them per name,
    each pset dict carrying its properties then ``"id"``."""
    if verbose:
        raise NotImplementedError("steplite get_psets implements verbose=False only")
    psets: Dict[str, Dict[str, Any]] = {}
    if element.is_a("IfcTypeObject"):
        for definition in getattr(element, "HasPropertySets", ()) or ():
            if psets_only and not definition.is_a("IfcPropertySet"):
                continue
            if qtos_only and not definition.is_a("IfcElementQuantity"):
                continue
            psets.setdefault(definition.Name, {}).update(_props_of(definition))
        return psets
    if getattr(element, "IsDefinedBy", None) is not None:
        if should_inherit:
            element_type = get_type(element)
            if element_type is not None:
                psets = get_psets(element_type, psets_only=psets_only,
                                  qtos_only=qtos_only, should_inherit=False)
        for rel in element.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                definition = rel.RelatingPropertyDefinition
                if psets_only and not definition.is_a("IfcPropertySet"):
                    continue
                if qtos_only and not definition.is_a("IfcElementQuantity"):
                    continue
                psets.setdefault(definition.Name, {}).update(_props_of(definition))
    return psets


_PREFIX_MULTIPLIER = {
    None: 1.0, "EXA": 1e18, "PETA": 1e15, "TERA": 1e12, "GIGA": 1e9, "MEGA": 1e6,
    "KILO": 1e3, "HECTO": 1e2, "DECA": 1e1, "DECI": 1e-1, "CENTI": 1e-2,
    "MILLI": 1e-3, "MICRO": 1e-6, "NANO": 1e-9, "PICO": 1e-12, "FEMTO": 1e-15,
    "ATTO": 1e-18,
}


def calculate_unit_scale(f: File, unit_type: str = "LENGTHUNIT") -> float:
    """ifcopenshell.util.unit.calculate_unit_scale (metres per project unit)."""
    projects = f.by_type("IfcProject")
    if not projects:
        return 1
    units = projects[0].UnitsInContext
    if not units:
        return 1
    unit_scale = 1
    for unit in units.Units or ():
        if getattr(unit, "UnitType", None) != unit_type:
            continue
        while unit.is_a("IfcConversionBasedUnit"):
            factor = unit.ConversionFactor
            unit_scale *= factor.ValueComponent.wrappedValue
            unit = factor.UnitComponent
        if unit.is_a("IfcSIUnit"):
            unit_scale *= _PREFIX_MULTIPLIER.get(unit.Prefix, 1.0)
    return unit_scale


def _a2p_matrix(o, z, x) -> List[List[float]]:
    """ifcopenshell.util.placement.a2p in pure python (4x4 nested lists)."""
    def norm(v):
        n = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
        return [v[0] / n, v[1] / n, v[2] / n] if n else list(v)

    x = norm(list(x))
    z = norm(list(z))
    y = norm([z[1] * x[2] - z[2] * x[1],
              z[2] * x[0] - z[0] * x[2],
              z[0] * x[1] - z[1] * x[0]])
    return [[x[0], y[0], z[0], float(o[0])],
            [x[1], y[1], z[1], float(o[1])],
            [x[2], y[2], z[2], float(o[2])],
            [0.0, 0.0, 0.0, 1.0]]


def _get_axis2placement(plc: Entity) -> List[List[float]]:
    if plc is None:
        return _a2p_matrix((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    if plc.is_a("IfcAxis2Placement3D"):
        o = list(plc.Location.Coordinates)
        z = list(plc.Axis.DirectionRatios) if plc.Axis else [0.0, 0.0, 1.0]
        x = (list(plc.RefDirection.DirectionRatios) if plc.RefDirection
             else [1.0, 0.0, 0.0])
    else:                                          # IfcAxis2Placement2D
        o = list(plc.Location.Coordinates) + [0.0]
        z = [0.0, 0.0, 1.0]
        rd = getattr(plc, "RefDirection", None)
        x = (list(rd.DirectionRatios) + [0.0]) if rd else [1.0, 0.0, 0.0]
    while len(o) < 3:
        o.append(0.0)
    while len(z) < 3:
        z.append(0.0)
    while len(x) < 3:
        x.append(0.0)
    return _a2p_matrix(o[:3], z[:3], x[:3])


def _matmul4(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)]
            for r in range(4)]


def get_local_placement(placement: Optional[Entity]) -> List[List[float]]:
    """ifcopenshell.util.placement.get_local_placement, returning a 4x4
    nested-list matrix (indexable ``m[r][c]`` exactly like the numpy one)."""
    if placement is None:
        return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    rel_to = placement.PlacementRelTo
    parent = get_local_placement(rel_to) if rel_to is not None else \
        [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
         [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    return _matmul4(parent, _get_axis2placement(placement.RelativePlacement))
