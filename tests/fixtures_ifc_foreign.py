"""Hand-authored IFC4 STEP fixture (zero third-party bytes, stdlib only):
the building / MEP classes a FOREIGN authoring tool emits and steplite did
not use to place in its ``by_type`` closures (issue #155).  Shared by
``tests/test_steplite.py`` (always, no ifcopenshell needed) and its parity
leg (when the real library is importable), so both backends are held to
the SAME pinned id lists below.

No geometry -- this fixture is about the class tree, attribute access and
relationship rows, not placement.  Record ids are deliberately NOT
ascending in file order (``#40`` before ``#12`` ...) so the per-class FILE
ordering ifcopenshell keeps is exercised too.

Contents (one storey ``L1`` in a building in a site):

* transcribed element rows: IfcWall W1 (+ IfcOpeningElement / IfcRelVoids
  / IfcDoor D1 / IfcRelFills), IfcWindow WN1, IfcColumn C1, IfcBeam B1,
  IfcCurtainWall CW1, IfcFurnishingElement DESK, IfcOutlet RX-1,
  IfcJunctionBox JB-1, IfcProtectiveDevice CB-1, IfcElectricAppliance EA-1,
  IfcElectricDistributionBoard DP-1, IfcCableCarrierFitting CT-L1,
  IfcElectricFlowStorageDevice UPS-1, IfcElectricGenerator GEN-1;
* IFC4 classes WITHOUT a transcribed row (served through ifc4_parents):
  IfcSanitaryTerminal SINK, IfcSensor OCC-1 (an
  IfcDistributionControlElement), IfcChimney CH1, IfcRamp R1;
* ports + systems: two IfcDistributionPorts nested under DP-1 / RX-1
  (IfcRelNests) and connected (IfcRelConnectsPorts); an
  IfcDistributionSystem 'LV' grouping DP-1, RX-1, JB-1
  (IfcRelAssignsToGroup); an IfcZone grouping the one IfcSpace.
"""
from __future__ import annotations

import os

STEP_TEXT = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [ReferenceView]'),'2;1');
FILE_NAME('foreign-classes-fixture.ifc','2026-08-09T00:00:00',(''),(''),'tekton tests','tekton tests','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPERSON($,$,'',$,$,$,$,$);
#2=IFCORGANIZATION($,'tekton tests',$,$,$);
#3=IFCPERSONANDORGANIZATION(#1,#2,$);
#4=IFCAPPLICATION(#2,'1.0','tekton test fixture','tekton_tests');
#5=IFCOWNERHISTORY(#3,#4,$,.NOCHANGE.,$,$,$,1785378586);
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCAXIS2PLACEMENT3D(#6,$,$);
#8=IFCLOCALPLACEMENT($,#7);
#9=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
#10=IFCUNITASSIGNMENT((#9));
#11=IFCPROJECT('0proj00000000000000001',#5,'Foreign classes',$,$,$,$,$,#10);
#90=IFCSITE('0site00000000000000001',#5,'Site',$,$,#8,$,$,.ELEMENT.,$,$,$,$,$);
#91=IFCBUILDING('0bldg00000000000000001',#5,'Building',$,$,#8,$,$,.ELEMENT.,$,$,$);
#92=IFCBUILDINGSTOREY('0stry00000000000000001',#5,'L1',$,$,#8,$,$,.ELEMENT.,0.);
#93=IFCSPACE('0spce00000000000000001',#5,'101',$,$,#8,$,'Electrical room',.ELEMENT.,.SPACE.,$);
#94=IFCRELAGGREGATES('0agg000000000000000001',#5,$,$,#11,(#90));
#95=IFCRELAGGREGATES('0agg000000000000000002',#5,$,$,#90,(#91));
#96=IFCRELAGGREGATES('0agg000000000000000003',#5,$,$,#91,(#92));
#97=IFCRELAGGREGATES('0agg000000000000000004',#5,$,$,#92,(#93));
#40=IFCWALL('0wall00000000000000001',#5,'W1',$,$,#8,$,'W1',.SOLIDWALL.);
#12=IFCOPENINGELEMENT('0open00000000000000001',#5,'W1-O1',$,$,#8,$,'O1',.OPENING.);
#41=IFCRELVOIDSELEMENT('0void00000000000000001',#5,$,$,#40,#12);
#20=IFCDOOR('0door00000000000000001',#5,'D1',$,$,#8,$,'D1',2.134,0.914,.DOOR.,.SINGLE_SWING_LEFT.,$);
#42=IFCRELFILLSELEMENT('0fill00000000000000001',#5,$,$,#12,#20);
#21=IFCWINDOW('0wndw00000000000000001',#5,'WN1',$,$,#8,$,'WN1',1.2,0.9,.WINDOW.,.SINGLE_PANEL.,$);
#30=IFCCOLUMN('0colm00000000000000001',#5,'C1',$,$,#8,$,'C1',.COLUMN.);
#22=IFCBEAM('0beam00000000000000001',#5,'B1',$,$,#8,$,'B1',.BEAM.);
#31=IFCCURTAINWALL('0cwal00000000000000001',#5,'CW1',$,$,#8,$,'CW1',.NOTDEFINED.);
#32=IFCCHIMNEY('0chim00000000000000001',#5,'CH1',$,$,#8,$,'CH1',.NOTDEFINED.);
#23=IFCRAMP('0ramp00000000000000001',#5,'R1',$,$,#8,$,'R1',.STRAIGHT_RUN_RAMP.);
#50=IFCFURNISHINGELEMENT('0furn00000000000000001',#5,'DESK',$,$,#8,$,'DESK');
#51=IFCSANITARYTERMINAL('0sink00000000000000001',#5,'SINK',$,$,#8,$,'SINK',.SINK.);
#60=IFCELECTRICDISTRIBUTIONBOARD('0dp1000000000000000001',#5,'DP-1',$,'DP-1 208Y/120V',#8,$,'DP-1',.DISTRIBUTIONBOARD.);
#52=IFCOUTLET('0rx1000000000000000001',#5,'RX-1',$,$,#8,$,'RX-1',.POWEROUTLET.);
#61=IFCJUNCTIONBOX('0jb1000000000000000001',#5,'JB-1',$,$,#8,$,'JB-1',.POWER.);
#53=IFCPROTECTIVEDEVICE('0cb1000000000000000001',#5,'CB-1',$,$,#8,$,'CB-1',.CIRCUITBREAKER.);
#62=IFCELECTRICAPPLIANCE('0ea1000000000000000001',#5,'EA-1',$,$,#8,$,'EA-1',.HANDDRYER.);
#54=IFCCABLECARRIERFITTING('0ctl100000000000000001',#5,'CT-L1',$,$,#8,$,'CT-L1',.BEND.);
#63=IFCELECTRICFLOWSTORAGEDEVICE('0ups100000000000000001',#5,'UPS-1',$,$,#8,$,'UPS-1',.UPS.);
#55=IFCELECTRICGENERATOR('0gen100000000000000001',#5,'GEN-1',$,$,#8,$,'GEN-1',.STANDALONE.);
#64=IFCSENSOR('0occ100000000000000001',#5,'OCC-1',$,$,#8,$,'OCC-1',.MOVEMENTSENSOR.);
#70=IFCDISTRIBUTIONPORT('0port00000000000000001',#5,'DP-1 load',$,$,#8,$,.SOURCE.,.CABLE.,.ELECTRICAL.);
#71=IFCDISTRIBUTIONPORT('0port00000000000000002',#5,'RX-1 line',$,$,#8,$,.SINK.,.CABLE.,.ELECTRICAL.);
#72=IFCRELNESTS('0nest00000000000000001',#5,$,$,#60,(#70));
#73=IFCRELNESTS('0nest00000000000000002',#5,$,$,#52,(#71));
#74=IFCRELCONNECTSPORTS('0conn00000000000000001',#5,$,$,#70,#71,$);
#80=IFCDISTRIBUTIONSYSTEM('0sys000000000000000001',#5,'LV',$,$,'Low voltage distribution',.ELECTRICAL.);
#81=IFCRELASSIGNSTOGROUP('0grp000000000000000001',#5,$,$,(#60,#52,#61),$,#80);
#82=IFCZONE('0zone00000000000000001',#5,'Electrical zone',$,$,'EZ-1');
#83=IFCRELASSIGNSTOGROUP('0grp000000000000000002',#5,$,$,(#93),$,#82);
#98=IFCRELCONTAINEDINSPATIALSTRUCTURE('0cont00000000000000001',#5,$,$,(#40,#20,#21,#30,#22,#31,#32,#23,#50,#51,#60,#52,#61,#53,#62,#54,#63,#55,#64),#92);
ENDSEC;
END-ISO-10303-21;
"""

#: ``[e.id() for e in f.by_type("IfcProduct")]`` -- pinned.  This is
#: ifcopenshell 0.8.5's own order (declaration-tree DFS: IfcElement's
#: subtypes alphabetically -- IfcBuildingElement {Beam, Chimney, Column,
#: CurtainWall, Door, Ramp, Wall, Window}, IfcDistributionElement {control:
#: Sensor; flow: EnergyConversion{Generator}, Controller{Board, Protective},
#: Fitting{CableCarrier, JunctionBox}, Storage{UPS}, Terminal{Appliance,
#: Outlet, Sanitary}}, IfcFeatureElement {Opening}, IfcFurnishingElement;
#: then IfcPort, then IfcSpatialElement {Building, Storey, Site, Space}).
EXPECTED_PRODUCT_IDS = [
    22, 32, 30, 31, 20, 23, 40, 21,            # building elements
    64,                                        # IfcSensor (control element)
    55, 60, 53, 54, 61, 63, 62, 52, 51,        # flow elements
    12,                                        # opening
    50,                                        # furnishing
    70, 71,                                    # distribution ports
    91, 92, 90, 93,                            # building, storey, site, space
]
EXPECTED_ELEMENT_IDS = EXPECTED_PRODUCT_IDS[:20]

#: classes in this fixture that steplite serves through ifc4_parents only
#: (no transcribed attribute row): leaf attributes raise AttributeError,
#: the IfcElement prefix is served.
UNTRANSCRIBED = {"IfcChimney": 32, "IfcRamp": 23, "IfcSanitaryTerminal": 51,
                 "IfcSensor": 64}


def write_fixture(dirpath: str, name: str = "foreign-classes-fixture.ifc") -> str:
    path = os.path.join(dirpath, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(STEP_TEXT)
    return path
