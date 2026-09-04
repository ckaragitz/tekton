"""#769 -- an IFC's own property sets reach the family as real parameters."""
import os
import pytest
from rvt.ifc import pset_params as PP

IFC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "out", "xfmr", "padmountedtransformer.ifc")


def test_clean_name_is_palette_safe():
    assert PP._clean("Top_Clearance") == "Top Clearance"
    assert PP._clean("  a   b  ") == "a b"
    assert PP._clean("") == "Property"
    assert len(PP._clean("x" * 200)) <= 60


def test_eid_handles_a_method_not_an_attribute():
    class _E:
        def id(self):
            return 7
    assert PP._eid(_E()) == 7

    class _F:
        id = 9
    assert PP._eid(_F()) == 9
    assert PP._eid(object()) == -1


def test_type_name_handles_both_reader_shapes():
    class _Callable:
        def is_a(self):
            return "IfcLengthMeasure"

    class _Attr:
        is_a = "IfcReal"
    assert PP._type_name(_Callable()) == "IfcLengthMeasure"
    assert PP._type_name(_Attr()) == "IfcReal"
    assert PP._type_name(object()) == ""


def test_an_unreadable_file_yields_no_params_and_says_so():
    # hard rule 1: never block delivery on this
    c = PP.collect("/definitely/not/a/file.ifc")
    assert c["params"] == {}
    assert c["notes"] and "not read" in c["notes"][0]


def test_reserved_names_are_never_substituted_for_geometry_dims():
    assert "Width" in PP.RESERVED_NAMES
    assert "Height" in PP.RESERVED_NAMES
    assert "Depth" in PP.RESERVED_NAMES


def test_summarise_is_quotable_and_names_skips():
    c = {"params": {"TopClearance": ("length", 3.0)},
         "skipped": [{"name": "Width", "pset": "P", "why": "reserved"}],
         "notes": []}
    lines = PP.summarise(c)
    assert any("carried through as 1 family parameter" in t for t in lines)
    assert any("was NOT carried" in t for t in lines)


def test_summarise_of_nothing_is_silent():
    assert PP.summarise({"params": {}, "skipped": [], "notes": []}) == []


FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "pset_mm_unit.ifc")


def test_the_tracked_mm_fixture_proves_the_conversion_in_ci():
    # the #769 review's nit: the only conversion test depended on an
    # untracked file, so CI never proved it.  This fixture is tracked.
    c = PP.collect(FIXTURE)
    p = c["params"]
    assert p["TopClearance"][0] == "length"
    assert abs(p["TopClearance"][1] - 3.0) < 1e-9          # 914.4 mm, not 914.4 or 3000
    assert p["PhaseCount"] == ("number", 3.0)
    # text and booleans are CARRIED, verbatim -- the review's blocker
    assert p["InsulationClass"] == ("text", "ONAN")
    assert p["IsOutdoor"] == ("text", "Yes")
    assert [s["name"] for s in c["skipped"]] == ["Width"]  # reserved
    assert c["notes"] == []                                # unit was READ
    assert all(v["tier"] == "given" for v in c["sources"].values())


def test_text_pset_values_land_on_the_type_row_as_text_not_zero():
    # the #769 review, sandbox-measured: float("ONAN") raised and the TEXT
    # parameter silently kept add_family_parameter's 0.0 while the caveat
    # claimed the value was carried.  Pin the fix at the factory level.
    from conftest import HAVE_SCHEMA
    if not HAVE_SCHEMA:
        pytest.skip("schema cache not present")
    from rvt.famgen import factory as F
    prod = F.make_generic_model(
        parts=[{"shape": "box", "width_ft": 1.0, "depth_ft": 1.0,
                "height_ft": 1.0}],
        name="Pset Carry", category="electrical_equipment",
        numeric_params={"InsulationClass": ("text", "ONAN"),
                        "TopClearance": ("length", 3.0),
                        "PhaseCount": ("number", 3.0)})
    _tname, vals = prod.doc.types[0]
    by_name = {name: vals[pe.elem_id]
               for name, pe in prod.doc.params.items() if pe.elem_id in vals}
    assert by_name["InsulationClass"] == "ONAN"            # not 0.0
    assert by_name["TopClearance"] == 3.0
    assert by_name["PhaseCount"] == 3.0


# ---------------------------------------------------------------------------
# the route wiring (#769 round-2 review): nothing pinned that _assembly_rfa
# actually PASSES the collection into the builder, so a refactor of its kw
# dict could silently reintroduce the drop with no test failing.
# ---------------------------------------------------------------------------

_MESH_IFC = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('psetbox.ifc','2026-01-01T00:00:00',('t'),('t'),'tekton-test','tekton-test','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPERSON($,$,'t',$,$,$,$,$);
#2=IFCORGANIZATION($,'t',$,$,$);
#3=IFCPERSONANDORGANIZATION(#1,#2,$);
#4=IFCAPPLICATION(#2,'1.0','tekton-test','TT');
#5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,$,$,0);
#6=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#10=IFCUNITASSIGNMENT((#6));
#11=IFCDIRECTION((0.,0.,1.));
#12=IFCDIRECTION((1.,0.,0.));
#13=IFCCARTESIANPOINT((0.,0.,0.));
#14=IFCAXIS2PLACEMENT3D(#13,#11,#12);
#15=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#14,$);
#16=IFCPROJECT('0project0000000000000t',#5,'T',$,$,$,$,(#15),#10);
#17=IFCLOCALPLACEMENT($,#14);
#100=IFCCARTESIANPOINTLIST3D(((-500.,-500.,0.),(500.,-500.,0.),(500.,500.,0.),(-500.,500.,0.),(-500.,-500.,1000.),(500.,-500.,1000.),(500.,500.,1000.),(-500.,500.,1000.)));
#101=IFCTRIANGULATEDFACESET(#100,$,.T.,((1,3,2),(1,4,3),(5,6,7),(5,7,8),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,4,8),(3,8,7),(4,1,5),(4,5,8)),$);
#102=IFCSHAPEREPRESENTATION(#15,'Body','Tessellation',(#101));
#103=IFCPRODUCTDEFINITIONSHAPE($,$,(#102));
#104=IFCBUILDINGELEMENTPROXY('0000000000000000000104',#5,'Xfmr',$,$,#17,#103,$,.NOTDEFINED.);
#120=IFCPROPERTYSINGLEVALUE('TopClearance',$,IFCLENGTHMEASURE(914.4),$);
#121=IFCPROPERTYSINGLEVALUE('InsulationClass',$,IFCLABEL('ONAN'),$);
#130=IFCPROPERTYSET('0000000000000000000130',#5,'Pset_TransformerClearances',$,(#120,#121));
#140=IFCRELDEFINESBYPROPERTIES('0000000000000000000140',#5,$,$,(#104),#130);
ENDSEC;
END-ISO-10303-21;
"""


def _write_mesh_ifc(tmp_path):
    p = tmp_path / "psetbox.ifc"
    p.write_text(_MESH_IFC, encoding="utf-8")
    return str(p)


def test_assembly_rfa_passes_the_collection_to_the_constructor(tmp_path,
                                                               monkeypatch):
    # pins the WIRE, not the builder: whatever _famspec_rfa is handed must
    # contain the collected psets, and the caveats must carry summarise().
    pytest.importorskip("numpy")
    from rvt.frontdoor import router as R
    seen = {}

    def fake_famspec_rfa(res, kind, kw, out_dir, sub, **k):
        seen["kind"], seen["kw"] = kind, kw
        res.files["rfa"] = "captured"                # stop the fallback lane
    monkeypatch.setattr(R, "_famspec_rfa", fake_famspec_rfa)
    res = R.RouteResult(ok=True, status="", route="ifc->rfa")
    R._assembly_rfa(res, _write_mesh_ifc(tmp_path), str(tmp_path), {})
    np = seen["kw"]["numeric_params"]
    assert np["InsulationClass"] == ("text", "ONAN")
    assert np["TopClearance"][0] == "length"
    assert abs(np["TopClearance"][1] - 3.0) < 1e-9
    assert any("YOUR PROPERTY SETS carried through" in c for c in res.caveats)


def test_the_route_delivers_the_family_with_the_carry_caveat(tmp_path):
    # end to end: route run --ifc ... --output rfa on a tessellated mm-unit
    # IFC with psets attached -> a delivered .rfa and the carry caveat naming
    # the carried parameters.
    from conftest import HAVE_SCHEMA
    if not HAVE_SCHEMA:
        pytest.skip("schema cache not present")
    pytest.importorskip("numpy")
    from rvt.frontdoor import router as R
    res = R.route({"ifc": _write_mesh_ifc(tmp_path)}, "rfa",
                  out=str(tmp_path / "o"))
    assert res.ok, res.status
    rfa = res.files.get("rfa")
    assert rfa and os.path.isfile(rfa)
    carry = [c for c in res.caveats if "YOUR PROPERTY SETS carried through" in c]
    assert carry and "InsulationClass" in carry[0] and "TopClearance" in carry[0]


@pytest.mark.skipif(not os.path.exists(IFC), reason="sample IFC not present")
def test_the_transformer_psets_are_carried_with_unit_conversion():
    c = PP.collect(IFC)
    p = c["params"]
    assert len(p) == 10, sorted(p)
    # metres -> feet, checked against the file's own _in companions
    assert p["TopClearance"][0] == "length"
    assert abs(p["TopClearance"][1] * 12.0 - 36.0) < 1e-6
    assert abs(p["FrontClearance"][1] * 12.0 - 120.0) < 1e-6
    assert abs(p["BodyWidth"][1] * 12.0 - 62.0) < 1e-6
    assert abs(p["PadDepth"][1] * 12.0 - 72.0) < 1e-6
    # a plain IfcReal stays a number, NOT scaled as a length
    assert p["TopClearance in"] == ("number", 36.0)
    assert c["sources"]["TopClearance"]["tier"] == "given"
