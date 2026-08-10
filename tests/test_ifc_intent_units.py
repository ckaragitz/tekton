"""Pset measures honour the IFC project's unit assignment (issue #348).

``rvt.ifc.intent._psets`` used to hand back the raw wrapped number of every
property, so a millimetre file's ``RoomInformation.ClearWidth`` read 5800
"metres" next to wall coordinates that WERE converted.  The law pinned here:

* ``IfcLengthMeasure`` / ``IfcPositiveLengthMeasure`` /
  ``IfcNonNegativeLengthMeasure`` (and ``IfcQuantityLength``) x the length
  scale -- the very number applied to vertices;
* ``IfcAreaMeasure`` / ``IfcVolumeMeasure`` (and their quantities) x the
  project's OWN area / volume unit (an SI prefix counts squared / cubed;
  a mm file that keeps SQUARE_METRE is left alone);
* a property's own ``Unit`` beats the project's (INCH on one property of a
  mm file);
* an occurrence pset overrides the same-named type pset property, unit and
  measure type and all (a unitless override must not inherit the type's factor);
* ``IfcReal`` / ``IfcInteger`` / ``IfcCountMeasure`` / labels: untouched.

Both reader backends must agree: the read runs in-process on whatever
``rvt.ifc`` selected (steplite in the wheel-less CI shard) and, when that
was a real ifcopenshell, once more in a child pinned to steplite.  The
fixture is hand-authored STEP text (ours, no third-party bytes) and needs
neither ifcopenshell nor numpy.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IFC_TEXT = """ISO-10303-21;
/* hand-authored by tekton (tests/test_ifc_intent_units.py) -- no third-party bytes */
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('units_psets.ifc','2026-08-10T00:00:00',('tekton'),('tekton'),'tekton tests','tekton tests','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPERSON($,'tekton','tests',$,$,$,$,$);
#2=IFCORGANIZATION($,'tekton',$,$,$);
#3=IFCPERSONANDORGANIZATION(#1,#2,$);
#4=IFCAPPLICATION(#2,'1.0','tekton tests','tekton_tests');
#5=IFCOWNERHISTORY(#3,#4,$,.NOCHANGE.,$,$,$,1786147200);
#6=IFCDIRECTION((1.,0.,0.));
#8=IFCDIRECTION((0.,0.,1.));
#9=IFCCARTESIANPOINT((0.,0.,0.));
#10=IFCAXIS2PLACEMENT3D(#9,#8,#6);
#11=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#10,$);
#13=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#14=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);
#15=IFCSIUNIT(*,.VOLUMEUNIT.,.MILLI.,.CUBIC_METRE.);
#16=IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.);
#17=IFCUNITASSIGNMENT((#13,#14,#15,#16));
#18=IFCPROJECT('1Do5cudwndK1xWynSYFT64',#5,'units psets',$,$,$,$,(#11),#17);
#19=IFCDIMENSIONALEXPONENTS(1,0,0,0,0,0,0);
#20=IFCMEASUREWITHUNIT(IFCLENGTHMEASURE(25.4),#13);
#21=IFCCONVERSIONBASEDUNIT(#19,.LENGTHUNIT.,'INCH',#20);
#23=IFCLOCALPLACEMENT($,#10);
#24=IFCSITE('2ZlkTrpKqT6no0HnekIRKA',#5,'Site',$,$,#23,$,$,.ELEMENT.,$,$,$,$,$);
#25=IFCLOCALPLACEMENT(#23,#10);
#26=IFCBUILDING('3mQ$xwDXYx5BzANNFhkJiF',#5,'Building',$,$,#25,$,$,.ELEMENT.,$,$,$);
#27=IFCLOCALPLACEMENT(#25,#10);
#28=IFCBUILDINGSTOREY('2zgEzgv5ICkrJcFEmq105k',#5,'Level 1',$,$,#27,$,$,.ELEMENT.,0.);
#29=IFCRELAGGREGATES('0Aq7yTVi5B0uOFx1oq7XbA',#5,$,$,#18,(#24));
#30=IFCRELAGGREGATES('1Bq7yTVi5B0uOFx1oq7XbB',#5,$,$,#24,(#26));
#31=IFCRELAGGREGATES('2Cq7yTVi5B0uOFx1oq7XbC',#5,$,$,#26,(#28));
#38=IFCLOCALPLACEMENT(#27,#10);
#41=IFCELECTRICDISTRIBUTIONBOARD('2opDp$QjHt4MreXGtbuEKm',#5,'DP-1 distribution panel',$,$,#38,$,'DP-1',.DISTRIBUTIONBOARD.);
#42=IFCRELCONTAINEDINSPATIALSTRUCTURE('3Dq7yTVi5B0uOFx1oq7XbD',#5,$,$,(#41),#28);
#50=IFCPROPERTYSINGLEVALUE('ClearWidth',$,IFCLENGTHMEASURE(5800.),$);
#51=IFCPROPERTYSINGLEVALUE('MountingHeight',$,IFCPOSITIVELENGTHMEASURE(1800.),$);
#52=IFCPROPERTYSINGLEVALUE('Setback',$,IFCNONNEGATIVELENGTHMEASURE(0.),$);
#53=IFCPROPERTYSINGLEVALUE('TrimDepth',$,IFCLENGTHMEASURE(4.),#21);
#54=IFCPROPERTYSINGLEVALUE('FloorArea',$,IFCAREAMEASURE(24.94),$);
#55=IFCPROPERTYSINGLEVALUE('RoomVolume',$,IFCVOLUMEMEASURE(74820000000.),$);
#56=IFCPROPERTYSINGLEVALUE('BusRating',$,IFCREAL(400.),$);
#57=IFCPROPERTYSINGLEVALUE('NumberOfCircuits',$,IFCINTEGER(42),$);
#58=IFCPROPERTYSINGLEVALUE('Poles',$,IFCCOUNTMEASURE(3.),$);
#59=IFCPROPERTYSINGLEVALUE('RoomName',$,IFCLABEL('Electrical Room'),$);
#60=IFCPROPERTYSINGLEVALUE('Depth',$,IFCLENGTHMEASURE(250.),$);
#63=IFCPROPERTYSINGLEVALUE('Clearance',$,IFCREAL(3.),$);
#61=IFCPROPERTYSET('2WlPi3cMjdFj2QxD8LTZVX',#5,'RoomInformation',$,(#50,#51,#52,#53,#54,#55,#56,#57,#58,#59,#60,#63));
#62=IFCRELDEFINESBYPROPERTIES('0vpFR5nqIXSvbhw1DOgOb_',#5,$,$,(#41),#61);
#70=IFCQUANTITYLENGTH('Perimeter',$,$,20200.,$);
#71=IFCQUANTITYLENGTH('TrimLength',$,#21,10.,$);
#72=IFCQUANTITYAREA('GrossFloorArea',$,$,26.1,$);
#73=IFCQUANTITYVOLUME('GrossVolume',$,$,78300000000.,$);
#74=IFCQUANTITYCOUNT('Doors',$,$,2.,$);
#75=IFCELEMENTQUANTITY('1XmPi3cMjdFj2QxD8LTZVY',#5,'BaseQuantities',$,$,(#70,#71,#72,#73,#74));
#76=IFCRELDEFINESBYPROPERTIES('1wpFR5nqIXSvbhw1DOgOc_',#5,$,$,(#41),#75);
#80=IFCPROPERTYSINGLEVALUE('Width',$,IFCPOSITIVELENGTHMEASURE(900.),$);
#81=IFCPROPERTYSINGLEVALUE('Depth',$,IFCLENGTHMEASURE(10.),#21);
#82=IFCPROPERTYSINGLEVALUE('Weight',$,IFCMASSMEASURE(85.),$);
#86=IFCPROPERTYSINGLEVALUE('Clearance',$,IFCLENGTHMEASURE(915.),$);
#83=IFCPROPERTYSET('3YnPi3cMjdFj2QxD8LTZVZ',#5,'RoomInformation',$,(#80,#81,#82,#86));
#84=IFCELECTRICDISTRIBUTIONBOARDTYPE('1SjXz5KmJDvpDo5xNnSmuA',#5,'DP 400 A',$,$,(#83),$,'DP-400','distribution panelboard',.DISTRIBUTIONBOARD.);
#85=IFCRELDEFINESBYTYPE('2GWk8j$FiUjnocAsdzE3Rf',#5,$,$,(#41),#84);
ENDSEC;
END-ISO-10303-21;
"""

#: property -> SI value the resolver must hand back (see the module docstring
#: for which law each row pins)
EXPECTED = {
    "RoomInformation": {
        "ClearWidth": 5.8,               # IfcLengthMeasure, mm -> m
        "MountingHeight": 1.8,           # IfcPositiveLengthMeasure
        "Setback": 0.0,                  # IfcNonNegativeLengthMeasure (steplite has no camel row for it)
        "TrimDepth": 0.1016,             # own Unit INCH = 25.4 x MILLI METRE beats the project's mm
        "FloorArea": 24.94,              # AREAUNIT is plain SQUARE_METRE in this mm file: untouched
        "RoomVolume": 74.82,             # VOLUMEUNIT MILLI CUBIC_METRE = mm3: prefix cubed, 1e-9
        "BusRating": 400.0,              # IfcReal: unitless, untouched
        "NumberOfCircuits": 42,          # IfcInteger: untouched (and stays an int)
        "Poles": 3.0,                    # IfcCountMeasure: untouched
        "RoomName": "Electrical Room",   # label
        "Depth": 0.25,                   # occurrence (mm, 250) overrides the TYPE's inch-united Depth
        "Width": 0.9,                    # inherited from the type pset, mm -> m
        "Weight": 85.0,                  # IfcMassMeasure: not a dimension we convert
        "Clearance": 3.0,                # occurrence IfcReal overrides the type's IfcLengthMeasure: no factor leaks
    },
    "BaseQuantities": {
        "Perimeter": 20.2,               # IfcQuantityLength, mm -> m
        "TrimLength": 0.254,             # IfcQuantityLength with its own INCH unit
        "GrossFloorArea": 26.1,          # IfcQuantityArea, SQUARE_METRE
        "GrossVolume": 78.3,             # IfcQuantityVolume, mm3 -> m3
        "Doors": 2.0,                    # IfcQuantityCount: untouched
    },
}


def read_psets(path: str) -> dict:
    """{'backend', 'unit_scales', 'psets'} for the one board in ``path`` --
    importable by the steplite child below."""
    from rvt.ifc import intent as I
    assert I._load_ifcos()
    import ifcopenshell                                    # type: ignore  (real or shim, now bound)
    f = ifcopenshell.open(path)
    board = f.by_type("IfcElectricDistributionBoard")[0]
    unit_scales = I._unit_scales(f)
    return {"backend": "steplite" if getattr(ifcopenshell, "IS_STEPLITE", False) else "ifcopenshell",
            "unit_scales": unit_scales, "psets": I._psets(board, unit_scales)}


@pytest.fixture(scope="module")
def ifc_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("units348") / "units_psets.ifc"
    p.write_text(IFC_TEXT, encoding="utf-8", newline="\n")
    return str(p)


@pytest.fixture(scope="module")
def here(ifc_path):
    return read_psets(ifc_path)


def _assert_expected(got: dict) -> None:
    assert got["unit_scales"] == pytest.approx({"LENGTHUNIT": 0.001, "AREAUNIT": 1.0, "VOLUMEUNIT": 1e-9})
    for pset, want in EXPECTED.items():
        have = got["psets"][pset]
        assert have.keys() == want.keys(), pset
        for prop, value in want.items():
            if isinstance(value, str):
                assert have[prop] == value, (got["backend"], pset, prop)
            else:
                assert have[prop] == pytest.approx(value, rel=1e-9, abs=1e-12), (got["backend"], pset, prop, have[prop])
    assert isinstance(got["psets"]["RoomInformation"]["NumberOfCircuits"], int), \
        "an untouched IfcInteger stays an int"


def test_dimensioned_measures_come_back_in_si(here):
    _assert_expected(here)


def test_steplite_child_agrees(here, ifc_path):
    """On a machine WITH the real wheel, run the same read once more in a
    child pinned to steplite: both backends must land on EXPECTED."""
    if here["backend"] == "steplite":
        pytest.skip("the selected backend already IS steplite (asserted above)")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.join(ROOT, "src"), os.path.join(ROOT, "tests")]
        + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
    env["RVT_STEPLITE_FORCE"] = "1"
    code = ("import json, sys; from test_ifc_intent_units import read_psets; "
            "print(json.dumps(read_psets(sys.argv[1])))")
    proc = subprocess.run([sys.executable, "-c", code, ifc_path], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-3000:]
    child = json.loads(proc.stdout)
    assert child["backend"] == "steplite", "the child must really run the stdlib reader"
    _assert_expected(child)


def test_metre_file_reads_verbatim():
    """On the shipped metre-unit input every factor is 1.0: ``_psets`` is
    the backend's ``get_psets`` verbatim (minus its ``id`` keys)."""
    path = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
    if not os.path.exists(path):
        pytest.skip("inputs/ifc/electrical-room-2500a.ifc absent")
    from rvt.ifc import intent as I
    assert I._load_ifcos()
    import ifcopenshell                                    # type: ignore
    import ifcopenshell.util.element as ue                 # type: ignore
    f = ifcopenshell.open(path)
    unit_scales = I._unit_scales(f)
    assert unit_scales == {"LENGTHUNIT": 1.0, "AREAUNIT": 1.0, "VOLUMEUNIT": 1.0}
    for prod in f.by_type("IfcBuildingElementProxy") + f.by_type("IfcElectricDistributionBoard"):
        verbatim = {n: {k: v for k, v in ps.items() if k != "id"} for n, ps in ue.get_psets(prod).items()}
        assert I._psets(prod, unit_scales) == verbatim
