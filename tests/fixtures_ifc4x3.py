"""Hand-authored IFC4X3_ADD2 STEP fixture (zero third-party bytes, stdlib
only): the smallest file that makes steplite's per-FILE_SCHEMA class tree
observable (issue #337).  Shared by ``tests/test_steplite.py`` (always, no
ifcopenshell needed) and its parity leg (when the real library is
importable), so both backends are held to the SAME pinned id lists below.

What IFC4X3 changed that this file exercises:

* ``IfcBuildingElement`` was renamed ``IfcBuiltElement`` -- W1 / S1 / D1 /
  C1 / PX-1 and the IFC4X3-only ``IfcKerb`` K1 (no transcribed row: served
  through ifc4x3_add2_parents, its own ``PredefinedType`` raises);
  ``IfcWallType`` is an ``IfcBuiltElementType``;
* ``IfcBuilding`` sits under the new ``IfcFacility``;
* ``IfcDistributionBoard`` DB-1 is an IFC4X3-only ``IfcFlowController``
  (no row) next to the IFC4-era ``IfcElectricDistributionBoard`` DP-1;
* ``IfcProperty.Description`` is called ``Specification``;
* ``IfcObjectPlacement.PlacementRelTo`` was hoisted from IfcLocalPlacement
  (placement #13 is relative to #8, so the chain is walked).

No geometry.  Record ids are deliberately NOT ascending in file order so
the per-class FILE ordering ifcopenshell keeps is exercised too.
"""
from __future__ import annotations

import os

STEP_TEXT = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [ReferenceView]'),'2;1');
FILE_NAME('ifc4x3-classes-fixture.ifc','2026-08-10T00:00:00',(''),(''),'tekton tests','tekton tests','');
FILE_SCHEMA(('IFC4X3_ADD2'));
ENDSEC;
DATA;
#1=IFCPERSON($,$,'',$,$,$,$,$);
#2=IFCORGANIZATION($,'tekton tests',$,$,$);
#3=IFCPERSONANDORGANIZATION(#1,#2,$);
#4=IFCAPPLICATION(#2,'1.0','tekton test fixture','tekton_tests');
#5=IFCOWNERHISTORY(#3,#4,$,.NOCHANGE.,$,$,$,1785456000);
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCAXIS2PLACEMENT3D(#6,$,$);
#8=IFCLOCALPLACEMENT($,#7);
#14=IFCCARTESIANPOINT((2.,1.,0.));
#15=IFCAXIS2PLACEMENT3D(#14,$,$);
#13=IFCLOCALPLACEMENT(#8,#15);
#9=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
#10=IFCUNITASSIGNMENT((#9));
#11=IFCPROJECT('0proj00000000000000001',#5,'IFC4X3 classes',$,$,$,$,$,#10);
#90=IFCSITE('0site00000000000000001',#5,'Site',$,$,#8,$,$,.ELEMENT.,$,$,$,$,$);
#91=IFCBUILDING('0bldg00000000000000001',#5,'Building',$,$,#8,$,$,.ELEMENT.,$,$,$);
#92=IFCBUILDINGSTOREY('0stry00000000000000001',#5,'L1',$,$,#8,$,$,.ELEMENT.,0.);
#94=IFCRELAGGREGATES('0agg000000000000000001',#5,$,$,#11,(#90));
#95=IFCRELAGGREGATES('0agg000000000000000002',#5,$,$,#90,(#91));
#96=IFCRELAGGREGATES('0agg000000000000000003',#5,$,$,#91,(#92));
#40=IFCWALL('0wall00000000000000001',#5,'W1',$,$,#8,$,'W1',.SOLIDWALL.);
#20=IFCSLAB('0slab00000000000000001',#5,'S1',$,$,#8,$,'S1',.FLOOR.);
#21=IFCDOOR('0door00000000000000001',#5,'D1',$,$,#13,$,'D1',2.1,0.9,.DOOR.,.SINGLE_SWING_LEFT.,$);
#22=IFCCOLUMN('0colm00000000000000001',#5,'C1',$,$,#8,$,'C1',.COLUMN.);
#23=IFCBUILDINGELEMENTPROXY('0prxy00000000000000001',#5,'PX-1',$,'Transformer pad',#13,$,'PX-1',.USERDEFINED.);
#24=IFCKERB('0kerb00000000000000001',#5,'K1',$,$,#8,$,'K1',.NOTDEFINED.);
#52=IFCELECTRICDISTRIBUTIONBOARD('0elec00000000000000001',#5,'DP-1',$,$,#13,$,'DP-1',.DISTRIBUTIONBOARD.);
#51=IFCDISTRIBUTIONBOARD('0dbrd00000000000000001',#5,'DB-1',$,$,#8,$,'DB-1',.SWITCHBOARD.);
#53=IFCOUTLET('0outl00000000000000001',#5,'RX-1',$,$,#8,$,'RX-1',.POWEROUTLET.);
#45=IFCWALLTYPE('0wtyp00000000000000001',#5,'Generic 200 wall',$,$,(#62),$,$,$,.SOLIDWALL.);
#46=IFCRELDEFINESBYTYPE('0rdt000000000000000001',#5,$,$,(#40),#45);
#60=IFCPROPERTYSINGLEVALUE('FireRating','2 h per the door schedule',IFCLABEL('120'),$);
#61=IFCPROPERTYENUMERATEDVALUE('Finish',$,(IFCLABEL('PAINT')),$);
#62=IFCPROPERTYSET('0pset00000000000000001',#5,'Pset_WallCommon',$,(#60,#61));
#63=IFCPROPERTYSINGLEVALUE('Rating','nameplate',IFCELECTRICCURRENTMEASURE(400.),$);
#64=IFCPROPERTYSET('0pset00000000000000002',#5,'TektonElectrical',$,(#63));
#65=IFCRELDEFINESBYPROPERTIES('0rdp000000000000000001',#5,$,$,(#52,#51),#64);
#66=IFCPROPERTYSINGLEVALUE('FireRating','occurrence override',IFCLABEL('90'),$);
#67=IFCPROPERTYSET('0pset00000000000000003',#5,'Pset_WallCommon',$,(#66));
#68=IFCRELDEFINESBYPROPERTIES('0rdp000000000000000002',#5,$,$,(#40),#67);
#98=IFCRELCONTAINEDINSPATIALSTRUCTURE('0rcs000000000000000001',#5,$,$,(#40,#20,#21,#22,#23,#24,#52,#51,#53),#92);
ENDSEC;
END-ISO-10303-21;
"""

#: ``by_type("IfcProduct")`` in ifcopenshell 0.8.5's own order for an
#: IFC4X3_ADD2 file: DFS over the IFC4X3 declaration tree (IfcElement ->
#: IfcBuiltElement subtypes alphabetically -> distribution elements ...
#: -> IfcSpatialElement -> ... IfcFacility -> IfcBuilding), FILE order per
#: class.  Pinned here; the parity test re-derives it from the real library.
EXPECTED_PRODUCT_IDS = [
    23, 22, 21, 24, 20, 40,                    # IfcBuiltElement: proxy, column, door, kerb, slab, wall
    51, 52,                                    # IfcFlowController: IfcDistributionBoard < IfcElectricDistributionBoard
    53,                                        # IfcFlowTerminal: outlet
    92, 91, 90,                                # storey, IfcFacility -> building, site
]
EXPECTED_BUILT_ELEMENT_IDS = EXPECTED_PRODUCT_IDS[:6]
EXPECTED_ELEMENT_IDS = EXPECTED_PRODUCT_IDS[:9]

#: IFC4X3-only classes in this fixture with no transcribed row (served
#: through ifc4x3_add2_parents): class -> step id; the IfcElement prefix is
#: served, their own leaf attribute (``PredefinedType``) raises.
UNTRANSCRIBED = {"IfcKerb": 24, "IfcDistributionBoard": 51}


def write_fixture(dirpath: str, name: str = "ifc4x3-classes-fixture.ifc") -> str:
    path = os.path.join(dirpath, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(STEP_TEXT)
    return path
