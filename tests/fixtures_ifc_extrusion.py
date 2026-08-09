"""Hand-authored IFC4 STEP fixture (zero third-party bytes, stdlib only):
a one-storey room whose every body is an ``IfcExtrudedAreaSolid`` -- the
body type our tekton-ifc harden step and most Revit/ArchiCAD exports emit
(issue #152).  Shared by ``tests/test_ifc_intent.py`` (real ifcopenshell)
and ``tests/test_steplite.py`` (stdlib reader), so both backends are held
to the SAME expected world numbers below.

Layout (metres; the storey sits at world (10, 20, 3), so every expected z
is WORLD -- the intent's z contract):

* ``Room shell`` proxy, placed AT the storey origin, five named solids:
  ``floor_slab``  rectangle profile 6 x 4 with a 2-D profile Position
                  (3, 2), solid Position z = -0.15, depth 0.15;
  ``wall_south``  arbitrary closed profile over an ``IfcPolyline``
                  (closing point repeated), depth 3;
  ``wall_north``  arbitrary closed profile over an ``IfcIndexedPolyCurve``
                  with NO Segments, depth 3;
  ``wall_west``   the same with explicit ``IfcLineIndex`` Segments;
  ``wall_east``   rectangle 3.6 x 0.2 whose solid Position is ROTATED 90
                  degrees about Z (RefDirection = +Y) at (5.9, 2, 0);
  ``wall_south_header``  rectangle 0.2 x 0.3 extruded HORIZONTALLY (solid
                  Position Axis = +X) from (2, 0.1, 2.35), depth 1.
* ``PANEL-X``     IfcElectricDistributionBoard whose placement is rotated
                  90 degrees about Z at storey-local (2, 1, 1.2); body =
                  rectangle 0.6 x 0.2, depth 1.5 (direct item).
* ``PANEL-M``     typed occurrence whose body is an ``IfcMappedItem`` onto
                  a type RepresentationMap holding rectangle 0.5 x 0.19,
                  depth 1.372; placement storey-local (5, 1, 1).
* ``BOLLARD``     IfcDiscreteAccessory, circle profile r = 0.15, depth 0.9,
                  placement storey-local (1, 3, 0).
* Type objects: the shell, PANEL-M and BOLLARD are typed
  (IfcBuildingElementProxyType / IfcElectricDistributionBoardType /
  IfcDiscreteAccessoryType) and an IfcWallType + IfcSlabType stand
  unassigned, so every steplite type-object row is instantiated once.

The ``check_*`` helpers below are the ONE assertion body both backends'
tests call (numpy imported inside; this module stays stdlib at import).
"""
from __future__ import annotations

import os

STOREY_ORIGIN = (10.0, 20.0, 3.0)

STEP_TEXT = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [ReferenceView]'),'2;1');
FILE_NAME('extrusion-fixture.ifc','2026-08-09T00:00:00',(''),(''),'tekton tests','tekton tests','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPERSON($,$,'',$,$,$,$,$);
#2=IFCORGANIZATION($,'tekton tests',$,$,$);
#3=IFCPERSONANDORGANIZATION(#1,#2,$);
#4=IFCAPPLICATION(#2,'1.0','tekton test fixture','tekton_tests');
#5=IFCOWNERHISTORY(#3,#4,$,.NOCHANGE.,$,$,$,1785378586);
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCDIRECTION((0.,0.,1.));
#8=IFCDIRECTION((1.,0.,0.));
#9=IFCAXIS2PLACEMENT3D(#6,#7,#8);
#10=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#9,$);
#11=IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,#10,$,.MODEL_VIEW.,$);
#12=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
#13=IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.);
#14=IFCUNITASSIGNMENT((#12,#13));
#15=IFCPROJECT('0test000000000000000P1',#5,'extrusion fixture',$,$,$,$,(#10),#14);
#16=IFCLOCALPLACEMENT($,#9);
#17=IFCSITE('0test000000000000000S1',#5,'Site',$,$,#16,$,$,.ELEMENT.,$,$,$,$,$);
#18=IFCLOCALPLACEMENT(#16,#9);
#19=IFCBUILDING('0test000000000000000B1',#5,'Building',$,$,#18,$,$,.ELEMENT.,$,$,$);
#20=IFCCARTESIANPOINT((10.,20.,3.));
#21=IFCAXIS2PLACEMENT3D(#20,#7,#8);
#22=IFCLOCALPLACEMENT(#18,#21);
#23=IFCBUILDINGSTOREY('0test000000000000000L1',#5,'Level 3m',$,$,#22,$,$,.ELEMENT.,3.);
#24=IFCRELAGGREGATES('0test000000000000000R1',#5,$,$,#15,(#17));
#25=IFCRELAGGREGATES('0test000000000000000R2',#5,$,$,#17,(#19));
#26=IFCRELAGGREGATES('0test000000000000000R3',#5,$,$,#19,(#23));
#30=IFCCOLOURRGB($,0.6,0.6,0.65);
#31=IFCSURFACESTYLERENDERING(#30,0.,$,$,$,$,$,$,.NOTDEFINED.);
#32=IFCSURFACESTYLE('mat',.BOTH.,(#31));
#33=IFCPRESENTATIONSTYLEASSIGNMENT((#32));
#40=IFCLOCALPLACEMENT(#22,#9);
#41=IFCCARTESIANPOINT((3.,2.));
#42=IFCAXIS2PLACEMENT2D(#41,$);
#43=IFCRECTANGLEPROFILEDEF(.AREA.,$,#42,6.,4.);
#44=IFCCARTESIANPOINT((0.,0.,-0.15));
#45=IFCAXIS2PLACEMENT3D(#44,#7,#8);
#46=IFCEXTRUDEDAREASOLID(#43,#45,#7,0.15);
#47=IFCSTYLEDITEM(#46,(#33),'floor_slab');
#50=IFCCARTESIANPOINT((0.,0.));
#51=IFCCARTESIANPOINT((6.,0.));
#52=IFCCARTESIANPOINT((6.,0.2));
#53=IFCCARTESIANPOINT((0.,0.2));
#54=IFCPOLYLINE((#50,#51,#52,#53,#50));
#55=IFCARBITRARYCLOSEDPROFILEDEF(.AREA.,$,#54);
#56=IFCEXTRUDEDAREASOLID(#55,#9,#7,3.);
#57=IFCSTYLEDITEM(#56,(#33),'wall_south');
#60=IFCCARTESIANPOINTLIST2D(((0.,3.8),(6.,3.8),(6.,4.),(0.,4.)));
#61=IFCINDEXEDPOLYCURVE(#60,$,.F.);
#62=IFCARBITRARYCLOSEDPROFILEDEF(.AREA.,'north',#61);
#63=IFCEXTRUDEDAREASOLID(#62,$,#7,3.);
#64=IFCSTYLEDITEM(#63,(#33),'wall_north');
#70=IFCCARTESIANPOINTLIST2D(((0.,0.2),(0.2,0.2),(0.2,3.8),(0.,3.8)));
#71=IFCINDEXEDPOLYCURVE(#70,(IFCLINEINDEX((1,2)),IFCLINEINDEX((2,3)),IFCLINEINDEX((3,4)),IFCLINEINDEX((4,1))),.F.);
#72=IFCARBITRARYCLOSEDPROFILEDEF(.AREA.,$,#71);
#73=IFCEXTRUDEDAREASOLID(#72,#9,#7,3.);
#74=IFCSTYLEDITEM(#73,(#33),'wall_west');
#80=IFCRECTANGLEPROFILEDEF(.AREA.,$,$,3.6,0.2);
#81=IFCCARTESIANPOINT((5.9,2.,0.));
#82=IFCDIRECTION((0.,1.,0.));
#83=IFCAXIS2PLACEMENT3D(#81,#7,#82);
#84=IFCEXTRUDEDAREASOLID(#80,#83,#7,3.);
#85=IFCSTYLEDITEM(#84,(#33),'wall_east');
#90=IFCRECTANGLEPROFILEDEF(.AREA.,$,$,0.2,0.3);
#91=IFCCARTESIANPOINT((2.,0.1,2.35));
#92=IFCAXIS2PLACEMENT3D(#91,#8,#82);
#93=IFCEXTRUDEDAREASOLID(#90,#92,#7,1.);
#94=IFCSTYLEDITEM(#93,(#33),'wall_south_header');
#95=IFCSHAPEREPRESENTATION(#11,'Body','SweptSolid',(#46,#56,#63,#73,#84,#93));
#96=IFCPRODUCTDEFINITIONSHAPE($,$,(#95));
#97=IFCBUILDINGELEMENTPROXY('0test000000000000000X1',#5,'Room shell',$,$,#40,#96,'ROOM',.USERDEFINED.);
#98=IFCPROPERTYSINGLEVALUE('RoomName',$,IFCLABEL('Test room'),$);
#99=IFCPROPERTYSET('0test000000000000000Q1',#5,'RoomInformation',$,(#98));
#100=IFCRELDEFINESBYPROPERTIES('0test000000000000000R4',#5,$,$,(#97),#99);
#110=IFCCARTESIANPOINT((2.,1.,1.2));
#111=IFCAXIS2PLACEMENT3D(#110,#7,#82);
#112=IFCLOCALPLACEMENT(#22,#111);
#113=IFCRECTANGLEPROFILEDEF(.AREA.,$,$,0.6,0.2);
#114=IFCEXTRUDEDAREASOLID(#113,#9,#7,1.5);
#115=IFCSTYLEDITEM(#114,(#33),'px_enclosure');
#116=IFCSHAPEREPRESENTATION(#11,'Body','SweptSolid',(#114));
#117=IFCPRODUCTDEFINITIONSHAPE($,$,(#116));
#118=IFCELECTRICDISTRIBUTIONBOARD('0test000000000000000E1',#5,'PANEL-X','Panelboard 480Y/277 V',$,#112,#117,'PANEL-X',.DISTRIBUTIONBOARD.);
#119=IFCPROPERTYSINGLEVALUE('PanelName',$,IFCLABEL('PANEL-X'),$);
#120=IFCPROPERTYSINGLEVALUE('Voltage',$,IFCLABEL('480Y/277 V'),$);
#121=IFCPROPERTYSINGLEVALUE('BusRating',$,IFCREAL(400.),$);
#122=IFCPROPERTYSET('0test000000000000000Q2',#5,'PanelSchedule',$,(#119,#120,#121));
#123=IFCRELDEFINESBYPROPERTIES('0test000000000000000R5',#5,$,$,(#118),#122);
#130=IFCRECTANGLEPROFILEDEF(.AREA.,$,$,0.5,0.19);
#131=IFCEXTRUDEDAREASOLID(#130,#9,#7,1.372);
#132=IFCSTYLEDITEM(#131,(#33),'pm_enclosure');
#133=IFCSHAPEREPRESENTATION(#11,'Body','SweptSolid',(#131));
#134=IFCREPRESENTATIONMAP(#9,#133);
#135=IFCELECTRICDISTRIBUTIONBOARDTYPE('0test000000000000000T1',#5,'Panel type 400A',$,$,$,(#134),$,$,.DISTRIBUTIONBOARD.);
#136=IFCCARTESIANTRANSFORMATIONOPERATOR3D($,$,#6,1.,$);
#137=IFCMAPPEDITEM(#134,#136);
#138=IFCSHAPEREPRESENTATION(#11,'Body','MappedRepresentation',(#137));
#139=IFCPRODUCTDEFINITIONSHAPE($,$,(#138));
#140=IFCCARTESIANPOINT((5.,1.,1.));
#141=IFCAXIS2PLACEMENT3D(#140,#7,#8);
#142=IFCLOCALPLACEMENT(#22,#141);
#143=IFCELECTRICDISTRIBUTIONBOARD('0test000000000000000E2',#5,'PANEL-M','Panelboard 480Y/277 V',$,#142,#139,'PANEL-M',.DISTRIBUTIONBOARD.);
#144=IFCRELDEFINESBYTYPE('0test000000000000000R6',#5,$,$,(#143),#135);
#145=IFCPROPERTYSINGLEVALUE('PanelName',$,IFCLABEL('PANEL-M'),$);
#146=IFCPROPERTYSINGLEVALUE('BusRating',$,IFCREAL(400.),$);
#147=IFCPROPERTYSET('0test000000000000000Q3',#5,'PanelSchedule',$,(#145,#146));
#148=IFCRELDEFINESBYPROPERTIES('0test000000000000000R7',#5,$,$,(#143),#147);
#150=IFCCIRCLEPROFILEDEF(.AREA.,$,$,0.15);
#151=IFCEXTRUDEDAREASOLID(#150,#9,#7,0.9);
#152=IFCSTYLEDITEM(#151,(#33),'bollard_body');
#153=IFCSHAPEREPRESENTATION(#11,'Body','SweptSolid',(#151));
#154=IFCPRODUCTDEFINITIONSHAPE($,$,(#153));
#155=IFCCARTESIANPOINT((1.,3.,0.));
#156=IFCAXIS2PLACEMENT3D(#155,#7,#8);
#157=IFCLOCALPLACEMENT(#22,#156);
#158=IFCDISCRETEACCESSORY('0test000000000000000D1',#5,'BOLLARD',$,$,#157,#154,'BOLLARD',.USERDEFINED.);
#160=IFCRELCONTAINEDINSPATIALSTRUCTURE('0test000000000000000R8',#5,$,$,(#97,#118,#143,#158),#23);
#170=IFCBUILDINGELEMENTPROXYTYPE('0test000000000000000T2',#5,'Room shell type',$,$,$,$,$,$,.USERDEFINED.);
#171=IFCRELDEFINESBYTYPE('0test000000000000000R9',#5,$,$,(#97),#170);
#172=IFCDISCRETEACCESSORYTYPE('0test000000000000000T3',#5,'Bollard 300 dia',$,$,$,$,$,$,.USERDEFINED.);
#173=IFCRELDEFINESBYTYPE('0test00000000000000R10',#5,$,$,(#158),#172);
#174=IFCWALLTYPE('0test000000000000000T4',#5,'Generic 200 wall',$,$,$,$,$,$,.STANDARD.);
#175=IFCSLABTYPE('0test000000000000000T5',#5,'Generic 150 slab',$,$,$,$,$,$,.FLOOR.);
ENDSEC;
END-ISO-10303-21;
"""

#: expected WORLD upright boxes per styled item name: (lo, hi) in metres
_SX, _SY, _SZ = STOREY_ORIGIN
EXPECTED_BOXES = {
    "floor_slab": ((_SX + 0.0, _SY + 0.0, _SZ - 0.15), (_SX + 6.0, _SY + 4.0, _SZ + 0.0)),
    "wall_south": ((_SX + 0.0, _SY + 0.0, _SZ), (_SX + 6.0, _SY + 0.2, _SZ + 3.0)),
    "wall_north": ((_SX + 0.0, _SY + 3.8, _SZ), (_SX + 6.0, _SY + 4.0, _SZ + 3.0)),
    "wall_west": ((_SX + 0.0, _SY + 0.2, _SZ), (_SX + 0.2, _SY + 3.8, _SZ + 3.0)),
    "wall_east": ((_SX + 5.8, _SY + 0.2, _SZ), (_SX + 6.0, _SY + 3.8, _SZ + 3.0)),
    "wall_south_header": ((_SX + 2.0, _SY + 0.0, _SZ + 2.2), (_SX + 3.0, _SY + 0.2, _SZ + 2.5)),
    # PANEL-X: placement rotated 90 deg -> the 0.6 width runs along world Y
    "px_enclosure": ((_SX + 2.0 - 0.1, _SY + 1.0 - 0.3, _SZ + 1.2), (_SX + 2.0 + 0.1, _SY + 1.0 + 0.3, _SZ + 2.7)),
    "pm_enclosure": ((_SX + 5.0 - 0.25, _SY + 1.0 - 0.095, _SZ + 1.0), (_SX + 5.0 + 0.25, _SY + 1.0 + 0.095, _SZ + 2.372)),
}

#: expected equipment records (world insertion z contract: level annotates,
#: z stays world): tag -> (w, d, h, elevation_m, typeName)
EXPECTED_EQUIPMENT = {
    "PANEL-X": (0.6, 0.2, 1.5, _SZ + 1.2, None),
    "PANEL-M": (0.5, 0.19, 1.372, _SZ + 1.0, "Panel type 400A"),
    "BOLLARD": (0.3, 0.3, 0.9, _SZ + 0.0, "Bollard 300 dia"),
}

EXPECTED_WALL_IDS = ("W-E", "W-N", "W-S", "W-W")


def write_fixture(dirpath: str, name: str = "extrusion-fixture.ifc") -> str:
    """Write :data:`STEP_TEXT` to ``dirpath/name``; return the path."""
    path = os.path.join(str(dirpath), name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(STEP_TEXT)
    return path


def geom_by_name(intent_mod, f) -> dict:
    """``{styled item name: GeomItem}`` over every element product of the
    opened file ``f`` (either backend), via ``rvt.ifc.intent``."""
    out = {}
    for prod, plc, geom in intent_mod.resolve_products(f):
        assert not plc.identity and plc.chain_depth == 4, prod.Name   # real chains
        for it in geom.items:
            out[it.name] = it
    return out


def check_world_boxes(items: dict) -> None:
    """Every named extrusion is ONE upright box at its expected WORLD extents;
    the mapped item came through the map; the circle is a 0.3 x 0.3 x 0.9
    prism (not a box) centred on its placement."""
    import numpy as np

    for name, (lo, hi) in EXPECTED_BOXES.items():
        it = items[name]
        assert it.is_all_boxes and it.n_components == 1, name
        assert np.allclose(it.lo, lo, atol=1e-6), (name, it.lo, lo)
        assert np.allclose(it.hi, hi, atol=1e-6), (name, it.hi, hi)
    assert items["pm_enclosure"].rep_identifier == "Body/mapped"
    bol = items["bollard_body"]
    assert not bol.is_all_boxes and bol.n_components == 1
    assert np.allclose(bol.extent, [0.3, 0.3, 0.9], atol=1e-6)
    assert np.allclose(bol.center, [_SX + 1.0, _SY + 3.0, _SZ + 0.45], atol=1e-6)


def check_intent_json(js: dict) -> None:
    """The resolved intent of the fixture: 4 wall runs closing the ring, all
    equipment with geometry + dims, WORLD elevations with the level as an
    annotation, typeName through the type objects."""
    assert sorted(w["id"] for w in js["walls"]) == sorted(EXPECTED_WALL_IDS)
    for w in js["walls"]:
        assert abs(w["thickness"] - 0.2) < 1e-4 and abs(w["height"] - 3.0) < 1e-4, w
    assert js["audit"]["equipment_with_geometry"] == len(EXPECTED_EQUIPMENT)
    assert js["levels"][0]["elevation"] == _SZ
    eq = {e["tag"]: e for e in js["equipment"]}
    for tag, (w, d, h, elev, type_name) in EXPECTED_EQUIPMENT.items():
        e = eq[tag]
        assert abs(e["dims_m"]["w"] - w) < 2e-3 and abs(e["dims_m"]["d"] - d) < 2e-3, tag
        assert abs(e["dims_m"]["h"] - h) < 1e-4, tag
        assert abs(e["elevation_m"] - elev) < 1e-4, tag          # z stays WORLD
        assert e["level"] == "L1", tag                            # level annotates
        assert e["typeName"] == type_name, tag
        assert e["positionSource"] == "placement-chain + local geometry", tag
