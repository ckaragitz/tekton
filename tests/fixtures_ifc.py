"""Test fixtures: build a small IFC that reproduces the Design v1 exporter
defects that the real saved sample lacks (duplicated per-element types with an
identical name, and a transparent 'working_clearance' phantom solid), on top
of the defects it does have (tessellated boxes, identity placements).

Also runnable as a script to write the fixture next to the sample:
    python tests/fixtures_ifc.py [out.ifc]
"""
from __future__ import annotations

import os
import sys

import ifcopenshell
import ifcopenshell.guid

new = ifcopenshell.guid.new


def _box_faceset(f, cx, cy, cz, w, d, h, name, transparency=0.0, style=None):
    """Tessellated axis-aligned box, three.js style (24 verts, 12 tris)."""
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - d / 2, cy + d / 2
    z0, z1 = cz, cz + h
    P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    verts, tris = [], []
    for face in faces:
        base = len(verts)
        for i in face:
            verts.append(P[i])
        tris.append((base + 1, base + 2, base + 3))
        tris.append((base + 1, base + 3, base + 4))
    pl = f.createIfcCartesianPointList3D(verts)
    fs = f.createIfcTriangulatedFaceSet(pl, None, None, tris, None)
    col = f.createIfcColourRgb(None, 0.6, 0.6, 0.65)
    rend = f.createIfcSurfaceStyleRendering(col, transparency, None, None, None, None, None, None, "NOTDEFINED")
    sty = style or f.createIfcSurfaceStyle(name + "_mat", "BOTH", [rend])
    f.createIfcStyledItem(fs, [f.createIfcPresentationStyleAssignment([sty])], name)
    return fs


def build_v1_defect_fixture(path: str) -> str:
    f = ifcopenshell.file(schema="IFC4")
    person = f.createIfcPerson(None, None, "", None, None, None, None, None)
    org = f.createIfcOrganization(None, "three-d-stage", None, None, None)
    pao = f.createIfcPersonAndOrganization(person, org, None)
    app = f.createIfcApplication(org, "1.0", "three-d-stage IFC writer", "three_d_stage")
    oh = f.createIfcOwnerHistory(pao, app, None, "NOCHANGE", None, None, None, 1785383780)
    zdir = f.createIfcDirection((0.0, 0.0, 1.0))
    xdir = f.createIfcDirection((1.0, 0.0, 0.0))
    origin = f.createIfcCartesianPoint((0.0, 0.0, 0.0))
    a2p = f.createIfcAxis2Placement3D(origin, zdir, xdir)
    ctx = f.createIfcGeometricRepresentationContext(None, "Model", 3, 1.0e-5, a2p, None)
    body = f.createIfcGeometricRepresentationSubContext("Body", "Model", None, None, None, None, ctx, None, "MODEL_VIEW", None)
    lu = f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE")
    f.createIfcUnitAssignment([lu])
    project = f.createIfcProject(new(), oh, "v1 defect fixture", None, None, None, None, [ctx], f.by_type("IfcUnitAssignment")[0])
    lp_site = f.createIfcLocalPlacement(None, a2p)
    site = f.createIfcSite(new(), oh, "Site", None, None, lp_site, None, None, "ELEMENT", None, None, None, None, None)
    lp_bldg = f.createIfcLocalPlacement(lp_site, a2p)
    building = f.createIfcBuilding(new(), oh, "Building", None, None, lp_bldg, None, None, "ELEMENT", None, None, None)
    lp_st = f.createIfcLocalPlacement(lp_bldg, a2p)
    storey = f.createIfcBuildingStorey(new(), oh, "Level 1", None, None, lp_st, None, None, "ELEMENT", 0.0)
    f.createIfcRelAggregates(new(), oh, None, None, project, [site])
    f.createIfcRelAggregates(new(), oh, None, None, site, [building])
    f.createIfcRelAggregates(new(), oh, None, None, building, [storey])

    contained = []
    # three identical panels, each with its OWN identically-named type (v1 bug)
    for i, x in enumerate((0.0, 1.0, 2.0)):
        fs = _box_faceset(f, x, 0.0, 1.067, 0.508, 0.15, 0.914, f"panel{i}_enclosure")
        rep = f.createIfcShapeRepresentation(body, "Body", "Tessellation", [fs])
        pds = f.createIfcProductDefinitionShape(None, None, [rep])
        lp = f.createIfcLocalPlacement(lp_st, a2p)   # identity -> baked coordinates
        panel = f.createIfcElectricDistributionBoard(
            new(), oh, f"B-P{i+1}", "Panelboard 480Y/277 V", None, lp, pds, f"B-P{i+1}", "DISTRIBUTIONBOARD")
        # duplicated type per element (identical Name)
        typ = f.createIfcElectricDistributionBoardType(
            new(), oh, "Eaton Pow-R-Line 4 (style) - 400A MB - 42 space", None, None, None, None,
            None, None, "DISTRIBUTIONBOARD")
        f.createIfcRelDefinesByType(new(), oh, None, None, [panel], typ)
        # per-element pset identical across all three -> should move to the shared type
        props = [f.createIfcPropertySingleValue("Manufacturer", None, f.create_entity("IfcLabel", "Eaton"), None),
                 f.createIfcPropertySingleValue("ModelLabel", None, f.create_entity("IfcLabel", "Pow-R-Line 4"), None)]
        pset = f.createIfcPropertySet(new(), oh, "Pset_ManufacturerTypeInformation", None, props)
        f.createIfcRelDefinesByProperties(new(), oh, None, None, [panel], pset)
        # element-specific pset (differs) -> must stay on the element
        p2 = [f.createIfcPropertySingleValue("PanelName", None, f.create_entity("IfcLabel", f"B-P{i+1}"), None),
              f.createIfcPropertySingleValue("Voltage", None, f.create_entity("IfcElectricVoltageMeasure", 480.0), None)]
        ps2 = f.createIfcPropertySet(new(), oh, "PanelSchedule", None, p2)
        f.createIfcRelDefinesByProperties(new(), oh, None, None, [panel], ps2)
        contained.append(panel)

    # phantom: transparent working-clearance box in front of panel 1
    fs = _box_faceset(f, 0.0, -0.6, 0.0, 0.762, 1.067, 1.981, "b_p1_working_clearance", transparency=0.75)
    rep = f.createIfcShapeRepresentation(body, "Body", "Tessellation", [fs])
    pds = f.createIfcProductDefinitionShape(None, None, [rep])
    clr = f.createIfcBuildingElementProxy(new(), oh, "B-P1 working_clearance",
                                          "NEC 110.26 working clearance volume", None,
                                          f.createIfcLocalPlacement(lp_st, a2p), pds, None, "NOTDEFINED")
    contained.append(clr)

    # orphan element (never contained) to exercise containment repair
    fs = _box_faceset(f, 4.0, 0.0, 0.1, 0.61, 0.51, 0.76, "xfmr_orphan")
    rep = f.createIfcShapeRepresentation(body, "Body", "Tessellation", [fs])
    pds = f.createIfcProductDefinitionShape(None, None, [rep])
    f.createIfcTransformer(new(), oh, "XFMR-1", "orphan transformer", None,
                            f.createIfcLocalPlacement(lp_st, a2p), pds, "XFMR-1", "VOLTAGE")

    f.createIfcRelContainedInSpatialStructure(new(), oh, None, None, contained, storey)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    f.write(path)
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "experiments", "out", "v1_defect_fixture.ifc")
    print(build_v1_defect_fixture(out))
