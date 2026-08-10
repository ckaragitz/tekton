"""Tests for rvt.ifc.intent -- the IFC INTENT resolver (the front door's two
gaps closed) and its family-mapping layer.

Evidence tiers:

1. PLACEMENT-CHAIN RESOLUTION: a synthetic IFC whose products carry REAL
   nested relative placements (site -> building -> storey -> product,
   rotated + translated) resolves to the exact composed world transform,
   and world = composed_chain @ local geometry holds; the identity-chain /
   world-baked writer style (our own three-d-stage exporter) resolves
   through the same formula from the tessellated vertices.
2. GEOMETRY RECOVERY: upright-box decomposition, minimum-area oriented
   footprint, front-normal inference from named features, wall-run
   extraction from a shell proxy's wall solids (with a door opening), the
   synthesized fourth wall of a cut-away room.
3. SEMANTICS: the tagging-contract pset normalisation (the join key),
   equipment classification, the feeder tree from FedFrom corroborated by
   the conduit-run named solids, NEC clearance parsing.
4. MAPPING: panelboards -> catalog facts (PRL1X / PRL2X), the transformer
   -> the 150 kVA member, the 2500 A switchboard -> the honest factory
   REFUSAL + the house switchboard from our IFC-modeled dims.
5. THE REAL FILE (inputs/ifc/electrical-room-2500a.ifc): every position is
   resolved (none at the origin), the walls close a ring, the feeder tree
   is fully corroborated, the intent JSON round-trips.
6. SWEPT SOLIDS (#152): IfcExtrudedAreaSolid bodies (rectangle / circle /
   arbitrary-closed profiles, direct and mapped) resolve to the same world
   boxes, walls and dims -- a hand-authored fixture shared with the
   stdlib-reader tests.

Corpus-dependent tests skip when the input / catalog is absent.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pytest

from conftest import HAVE_IFC_AUTHORING   # the builders AUTHOR IFC (ifcopenshell.file/.guid), #367

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOM_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
HAVE_ROOM = os.path.exists(ROOM_IFC)

if not HAVE_IFC_AUTHORING:
    pytest.skip("real ifcopenshell not installed (steplite shim on the path)",
                allow_module_level=True)
import ifcopenshell.guid  # noqa: E402

from rvt.ifc import intent as I  # noqa: E402


# ===========================================================================
# synthetic IFC builders
# ===========================================================================

def _box_faceset(f, cx, cy, cz, w, d, h, name):
    """Tessellated axis-aligned box in LOCAL coords (24 verts, 12 tris)."""
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
    rend = f.createIfcSurfaceStyleRendering(col, 0.0, None, None, None, None, None, None, "NOTDEFINED")
    sty = f.createIfcSurfaceStyle(name + "_mat", "BOTH", [rend])
    f.createIfcStyledItem(fs, [f.createIfcPresentationStyleAssignment([sty])], name)
    return fs


class Synth:
    """A tiny IFC4 project with a real placement chain."""

    def __init__(self):
        f = self.f = ifcopenshell.file(schema="IFC4")
        new = ifcopenshell.guid.new
        person = f.createIfcPerson(None, None, "", None, None, None, None, None)
        org = f.createIfcOrganization(None, "three-d-stage", None, None, None)
        pao = f.createIfcPersonAndOrganization(person, org, None)
        app = f.createIfcApplication(org, "1.0", "three-d-stage IFC writer", "three_d_stage")
        self.oh = f.createIfcOwnerHistory(pao, app, None, "NOCHANGE", None, None, None, 1785378586)
        z = f.createIfcDirection((0.0, 0.0, 1.0))
        x = f.createIfcDirection((1.0, 0.0, 0.0))
        o = f.createIfcCartesianPoint((0.0, 0.0, 0.0))
        self.identity = f.createIfcAxis2Placement3D(o, z, x)
        ctx = f.createIfcGeometricRepresentationContext(None, "Model", 3, 1.0e-5, self.identity, None)
        self.body = f.createIfcGeometricRepresentationSubContext(
            "Body", "Model", None, None, None, None, ctx, None, "MODEL_VIEW", None)
        lu = f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE")
        ua = f.createIfcUnitAssignment([lu])
        self.project = f.createIfcProject(new(), self.oh, "synthetic", None, None, None, None, [ctx], ua)
        # site at the origin, building translated (100, 50, 0), storey +3.5 z
        # AND rotated 90 deg about Z (X axis -> +Y)
        self.lp_site = f.createIfcLocalPlacement(None, self.identity)
        site = f.createIfcSite(new(), self.oh, "Site", None, None, self.lp_site, None, None,
                                 "ELEMENT", None, None, None, None, None)
        b_pl = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((100.0, 50.0, 0.0)), z, x)
        self.lp_building = f.createIfcLocalPlacement(self.lp_site, b_pl)
        building = f.createIfcBuilding(new(), self.oh, "Building", None, None, self.lp_building,
                                         None, None, "ELEMENT", None, None, None)
        s_pl = f.createIfcAxis2Placement3D(
            f.createIfcCartesianPoint((0.0, 0.0, 3.5)), z, f.createIfcDirection((0.0, 1.0, 0.0)))
        self.lp_storey = f.createIfcLocalPlacement(self.lp_building, s_pl)
        self.storey = f.createIfcBuildingStorey(new(), self.oh, "Level 1", None, None, self.lp_storey,
                                                  None, None, "ELEMENT", 0.0)
        f.createIfcRelAggregates(new(), self.oh, None, None, self.project, [site])
        f.createIfcRelAggregates(new(), self.oh, None, None, site, [building])
        f.createIfcRelAggregates(new(), self.oh, None, None, building, [self.storey])
        self.products = []

    def add_board(self, name, tag, rel_origin, *, w=0.5, d=0.15, h=1.2, psets=None,
                  world_baked=False, predefined="DISTRIBUTIONBOARD", door_side="+x"):
        """A panelboard: an enclosure box + a door feature on ``door_side``,
        placed by a relative placement (or world-baked into the vertices)."""
        f = self.f
        new = ifcopenshell.guid.new
        z = f.createIfcDirection((0.0, 0.0, 1.0))
        x = f.createIfcDirection((1.0, 0.0, 0.0))
        if world_baked:
            lp = f.createIfcLocalPlacement(self.lp_storey, self.identity)
            ox, oy, oz = rel_origin
        else:
            lp = f.createIfcLocalPlacement(
                self.lp_storey,
                f.createIfcAxis2Placement3D(f.createIfcCartesianPoint(rel_origin), z, x))
            ox, oy, oz = 0.0, 0.0, 0.0
        enc = _box_faceset(f, ox, oy, oz + 0.5, w if door_side in ("+y", "-y") else d,
                           d if door_side in ("+y", "-y") else w, h, f"{tag.lower()}_enclosure")
        # door feature: a thin plate on the requested side
        dd = 0.004
        if door_side == "+x":
            door = _box_faceset(f, ox + d / 2 + dd, oy, oz + 0.55, dd, w * 0.9, h * 0.9, f"{tag.lower()}_door")
        elif door_side == "-x":
            door = _box_faceset(f, ox - d / 2 - dd, oy, oz + 0.55, dd, w * 0.9, h * 0.9, f"{tag.lower()}_door")
        elif door_side == "+y":
            door = _box_faceset(f, ox, oy + d / 2 + dd, oz + 0.55, w * 0.9, dd, h * 0.9, f"{tag.lower()}_door")
        else:
            door = _box_faceset(f, ox, oy - d / 2 - dd, oz + 0.55, w * 0.9, dd, h * 0.9, f"{tag.lower()}_door")
        rep = f.createIfcShapeRepresentation(self.body, "Body", "Tessellation", [enc, door])
        pds = f.createIfcProductDefinitionShape(None, None, [rep])
        prod = f.createIfcElectricDistributionBoard(new(), self.oh, name, None, None, lp, pds,
                                                    tag, predefined)
        if psets:
            for pname, props in psets.items():
                vals = []
                for k, v in props.items():
                    if isinstance(v, bool):
                        nv = f.create_entity("IfcBoolean", v)
                    elif isinstance(v, int):
                        nv = f.create_entity("IfcInteger", v)
                    elif isinstance(v, float):
                        nv = f.create_entity("IfcReal", v)
                    else:
                        nv = f.create_entity("IfcLabel", str(v))
                    vals.append(f.createIfcPropertySingleValue(k, None, nv, None))
                pset = f.createIfcPropertySet(new(), self.oh, pname, None, vals)
                f.createIfcRelDefinesByProperties(new(), self.oh, None, None, [prod], pset)
        self.products.append(prod)
        return prod

    def contain(self):
        f = self.f
        f.createIfcRelContainedInSpatialStructure(
            ifcopenshell.guid.new(), self.oh, None, None, list(self.products), self.storey)
        return self


@pytest.fixture
def synth():
    return Synth()


# ===========================================================================
# 1. placement-chain resolution
# ===========================================================================

def test_axis2placement3d_matrix_defaults_and_orthonormal():
    f = ifcopenshell.file(schema="IFC4")
    o = f.createIfcCartesianPoint((1.0, 2.0, 3.0))
    a2p = f.createIfcAxis2Placement3D(o, None, None)
    m = I.axis2placement3d_matrix(a2p)
    assert np.allclose(m[:3, :3], np.eye(3))
    assert np.allclose(m[:3, 3], [1.0, 2.0, 3.0])
    # non-orthogonal RefDirection is projected onto the plane normal to Axis
    zd = f.createIfcDirection((0.0, 0.0, 1.0))
    xd = f.createIfcDirection((1.0, 0.0, 1.0))          # not perpendicular
    m2 = I.axis2placement3d_matrix(f.createIfcAxis2Placement3D(o, zd, xd))
    r = m2[:3, :3]
    assert np.allclose(r.T @ r, np.eye(3), atol=1e-9)   # orthonormal
    assert np.allclose(np.linalg.det(r), 1.0)
    assert np.allclose(r[:, 0], [1.0, 0.0, 0.0])         # projected X


def test_compose_placement_chain_rotated_translated(synth):
    """building (100,50) then storey rotated 90 deg + z 3.5: a product at
    relative (2, 1, 0) lands at world (100 - 1, 50 + 2, 3.5)."""
    prod = synth.add_board("P", "P", (2.0, 1.0, 0.0))
    plc = I.compose_placement(prod.ObjectPlacement)
    assert plc.chain_depth == 4                       # product, storey, building, site
    assert not plc.identity
    # composed origin: building translation + storey rotation applied to (2,1,0)
    assert np.allclose(plc.origin, [100.0 - 1.0, 50.0 + 2.0, 3.5], atol=1e-9)
    # composed X axis is the storey's rotated X (world +Y)
    assert np.allclose(plc.matrix[:3, 0], [0.0, 1.0, 0.0], atol=1e-9)
    # every link recorded
    classes = [l["class"] for l in plc.chain]
    assert classes == ["IfcLocalPlacement"] * 4
    assert plc.chain[-1]["relative_identity"] is True   # the site link
    # cross-check against ifcopenshell's own resolver
    import ifcopenshell.util.placement as upl
    ref = np.array(upl.get_local_placement(prod.ObjectPlacement), float)
    assert np.allclose(plc.matrix, ref, atol=1e-9)


def test_world_geometry_from_relative_placement(synth):
    """world = composed_chain @ local vertices: the enclosure's world bbox
    centre equals the composed origin (+ the local box centre offset)."""
    prod = synth.add_board("P", "P", (2.0, 1.0, 0.0), w=0.5, d=0.2, h=1.0)
    plc, geom = I.analyze_product(synth.f, prod, scale=1.0)
    enc = geom.item("p_enclosure")
    assert enc is not None
    # local box: centre (0,0), z 0.5..1.5 -> world centre = composed origin + z 1.0
    expected = plc.origin + plc.matrix[:3, :3] @ np.array([0.0, 0.0, 1.0])
    assert np.allclose(enc.center, expected, atol=1e-6)
    # dims survive the rotation (0.5 wide along local Y since door is +x)
    ext = enc.extent
    assert math.isclose(sorted(ext)[0], 0.2, abs_tol=1e-6)
    assert math.isclose(sorted(ext)[1], 0.5, abs_tol=1e-6)
    assert math.isclose(ext[2], 1.0, abs_tol=1e-6)


def test_world_baked_identity_chain_resolves_from_geometry(synth):
    """The three-d-stage writer style: identity placements + world-baked
    vertices -> the position comes from the geometry, not the chain."""
    prod = synth.add_board("P", "P", (7.0, -3.0, 0.0), world_baked=True, door_side="+y")
    plc, geom = I.analyze_product(synth.f, prod, scale=1.0)
    # the chain composes through the storey/building offsets even though the
    # PRODUCT's own relative placement is the identity
    eq = _equipment_from(synth, prod, plc, geom, kind="transformer")   # floor gear
    I._resolve_equipment_placement(eq, room_center_xy=np.array([0.0, -10.0]))
    # world-baked (7,-3) in the storey frame -> world = storey chain @ (7,-3);
    # a floor unit's insertion is the footprint centre at the base
    world = (plc.matrix @ np.array([7.0, -3.0, 0.0, 1.0]))[:3]
    assert np.allclose(eq.insertion_m[0], world[0], atol=1e-3)
    assert np.allclose(eq.insertion_m[1], world[1], atol=1e-3)
    assert "geometry-recovered" in eq.position_source or "placement-chain" in eq.position_source


def test_grid_or_unsupported_placement_is_flagged(synth):
    f = synth.f
    gp = f.create_entity("IfcGridPlacement",
                         PlacementLocation=f.create_entity("IfcVirtualGridIntersection",
                                                             IntersectingAxes=[
                                                                 f.create_entity("IfcGridAxis", "A",
                                                                                 f.createIfcPolyline([f.createIfcCartesianPoint((0.0, 0.0)),
                                                                                                      f.createIfcCartesianPoint((1.0, 0.0))]), True),
                                                                 f.create_entity("IfcGridAxis", "1",
                                                                                 f.createIfcPolyline([f.createIfcCartesianPoint((0.0, 0.0)),
                                                                                                      f.createIfcCartesianPoint((0.0, 1.0))]), True)],
                                                             OffsetDistances=[0.0, 0.0]))
    plc = I.compose_placement(gp)
    assert plc.identity
    assert plc.warnings and "unsupported placement" in plc.warnings[0]


# ===========================================================================
# 2. geometry recovery
# ===========================================================================

def test_box_from_points_upright_and_rotated():
    theta = math.radians(30)
    c, s = math.cos(theta), math.sin(theta)
    w, d, h = 2.0, 1.0, 3.0
    corners = []
    for zz in (0.5, 3.5):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            lx, ly = sx * w / 2, sy * d / 2
            corners.append((5.0 + lx * c - ly * s, 7.0 + lx * s + ly * c, zz))
    b = I.box_from_points(np.array(corners))
    assert b is not None
    assert math.isclose(b["origin"][0], 5.0, abs_tol=1e-4)
    assert math.isclose(b["origin"][1], 7.0, abs_tol=1e-4)
    assert math.isclose(b["origin"][2], 0.5, abs_tol=1e-9)
    assert math.isclose(b["height"], 3.0, abs_tol=1e-9)
    assert math.isclose(max(b["xdim"], b["ydim"]), 2.0, abs_tol=1e-4)
    assert math.isclose(min(b["xdim"], b["ydim"]), 1.0, abs_tol=1e-4)


def test_box_from_points_rejects_non_box():
    pts = np.random.RandomState(0).rand(8, 3)
    assert I.box_from_points(pts) is None
    assert I.box_from_points(np.zeros((0, 3))) is None


def test_decompose_boxes_two_components():
    f = ifcopenshell.file(schema="IFC4")
    a = _box_faceset(f, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, "a")
    pts = np.array(a.Coordinates.CoordList, float)
    tris = np.array(a.CoordIndex, int) - 1
    boxes, ncomp = I.decompose_boxes(pts, tris)
    assert ncomp == 1 and len(boxes) == 1
    b = boxes[0]
    assert math.isclose(b["xdim"], 1.0) and math.isclose(b["ydim"], 1.0)
    assert math.isclose(b["height"], 1.0)


def test_oriented_footprint_rectangle_and_yaw():
    theta = math.radians(20)
    c, s = math.cos(theta), math.sin(theta)
    pts = []
    for x in np.linspace(-2, 2, 9):
        for y in np.linspace(-0.5, 0.5, 5):
            pts.append((10 + x * c - y * s, -4 + x * s + y * c))
    fp = I.oriented_footprint(np.array(pts))
    assert math.isclose(fp["xdim"], 4.0, abs_tol=1e-6)
    assert math.isclose(fp["ydim"], 1.0, abs_tol=1e-6)
    assert math.isclose(fp["center"][0], 10.0, abs_tol=1e-6)
    assert math.isclose(fp["center"][1], -4.0, abs_tol=1e-6)
    assert math.isclose(fp["yaw_deg"], 20.0, abs_tol=1e-6)


def _equipment_from(synth, prod, plc, geom, contract=None, kind="distribution_panelboard"):
    psets = I._psets(prod)
    con = contract if contract is not None else I.normalize_contract(
        psets, name=prod.Name or "", object_type=None, description=prod.Description,
        tag=getattr(prod, "Tag", None))
    return I.Equipment(step_id=prod.id(), guid=prod.GlobalId, ifc_class=prod.is_a(),
                       predefined_type=str(getattr(prod, "PredefinedType", "") or "") or None,
                       name=prod.Name or "", tag=str(prod.Tag or prod.Name),
                       description=prod.Description, object_type=None, type_name=None,
                       kind=kind, psets=psets, contract=con, placement=plc, geometry=geom)


def test_front_normal_from_door_feature_and_upright_frame(synth):
    """The door plate on -X => the panel faces -X (west); wall gear gets the
    upright frame (family +Z = front, +Y = up) and the insertion sits on the
    enclosure's BACK face."""
    prod = synth.add_board("LP-9", "LP-9", (0.0, 0.0, 0.0), world_baked=True,
                           w=0.5, d=0.2, h=1.0, door_side="-x")
    plc, geom = I.analyze_product(synth.f, prod, scale=1.0)
    eq = _equipment_from(synth, prod, plc, geom, kind="lighting_panelboard")
    I._resolve_equipment_placement(eq, room_center_xy=np.array([-5.0, 0.0]))
    # world = storey chain applied; the storey is rotated 90 (X -> +Y), so the
    # local -X front becomes world -Y
    assert np.allclose(eq.front_normal[:2], [0.0, -1.0], atol=1e-6)
    assert eq.frame_kind == "upright"
    fx, fy, fz = eq.frame3x3
    assert np.allclose(fz, [0.0, -1.0, 0.0])            # family Z = front
    assert np.allclose(fy, [0.0, 0.0, 1.0])             # family Y = up
    # right-handed frame
    assert np.allclose(np.cross(fx, fy), fz, atol=1e-9)


def test_floor_gear_yaw_frame_faces_negative_y():
    n = [0.0, -1.0]                                     # faces south
    frame, yaw = I._yaw_frame(n)
    assert math.isclose(yaw, 0.0, abs_tol=1e-9)         # family X along +X
    assert np.allclose(frame[1], [0.0, 1.0, 0.0])       # family +Y = -front
    frame2, yaw2 = I._yaw_frame([1.0, 0.0])             # faces east
    assert math.isclose(yaw2, 90.0, abs_tol=1e-9)         # family X = famY x Z = +Y
    # right-handed in every case
    assert np.allclose(np.cross(frame2[0], frame2[1]), frame2[2], atol=1e-9)


def test_upright_frame_west_wall_panel():
    frame = I._upright_frame([1.0, 0.0, 0.0])           # front +X (west-wall panel)
    fx, fy, fz = frame
    assert np.allclose(fx, [0.0, 1.0, 0.0])
    assert np.allclose(fy, [0.0, 0.0, 1.0])
    assert np.allclose(fz, [1.0, 0.0, 0.0])
    m = np.array(frame)
    assert math.isclose(np.linalg.det(m), 1.0)


def _room_shell_file():
    """A cut-away room shell: back wall, left wall (with a door opening +
    header), right wall (solid), floor slab; the front wall is missing."""
    f = ifcopenshell.file(schema="IFC4")
    new = ifcopenshell.guid.new
    person = f.createIfcPerson(None, None, "", None, None, None, None, None)
    org = f.createIfcOrganization(None, "three-d-stage", None, None, None)
    pao = f.createIfcPersonAndOrganization(person, org, None)
    app = f.createIfcApplication(org, "1.0", "three-d-stage IFC writer", "three_d_stage")
    oh = f.createIfcOwnerHistory(pao, app, None, "NOCHANGE", None, None, None, 1785378586)
    z = f.createIfcDirection((0.0, 0.0, 1.0))
    x = f.createIfcDirection((1.0, 0.0, 0.0))
    o = f.createIfcCartesianPoint((0.0, 0.0, 0.0))
    ident = f.createIfcAxis2Placement3D(o, z, x)
    ctx = f.createIfcGeometricRepresentationContext(None, "Model", 3, 1.0e-5, ident, None)
    body = f.createIfcGeometricRepresentationSubContext("Body", "Model", None, None, None, None,
                                                       ctx, None, "MODEL_VIEW", None)
    ua = f.createIfcUnitAssignment([f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE")])
    proj = f.createIfcProject(new(), oh, "shell", None, None, None, None, [ctx], ua)
    lp_site = f.createIfcLocalPlacement(None, ident)
    site = f.createIfcSite(new(), oh, "Site", None, None, lp_site, None, None, "ELEMENT",
                             None, None, None, None, None)
    storey = f.createIfcBuildingStorey(new(), oh, "L1", None, None,
                                       f.createIfcLocalPlacement(lp_site, ident),
                                       None, None, "ELEMENT", 0.0)
    f.createIfcRelAggregates(new(), oh, None, None, proj, [site])
    f.createIfcRelAggregates(new(), oh, None, None, site, [storey])
    # room: x -4..4, y -3..3; walls 0.2 thick, 3.0 tall
    items = [
        _box_faceset(f, 0.0, 3.1, 0.0, 8.0, 0.2, 3.0, "wall_back"),              # north
        _box_faceset(f, -4.1, 1.25, 0.0, 0.2, 3.5, 3.0, "wall_left_a"),          # west, upper piece (y -0.5..3.0)
        _box_faceset(f, -4.1, -2.75, 0.0, 0.2, 0.5, 3.0, "wall_left_b"),         # west, lower piece
        _box_faceset(f, -4.1, -1.5, 2.2, 0.2, 2.0, 0.8, "wall_left_header"),     # header over the opening
        _box_faceset(f, 4.1, 0.0, 0.0, 0.2, 6.0, 3.0, "wall_right_a"),           # east, solid
        _box_faceset(f, 0.0, 0.1, -0.15, 8.0, 6.2, 0.15, "floor_slab"),
        _box_faceset(f, -4.7, -1.5, 0.0, 0.9, 0.3, 2.1, "door_left_leaf"),
    ]
    rep = f.createIfcShapeRepresentation(body, "Body", "Tessellation", items)
    pds = f.createIfcProductDefinitionShape(None, None, [rep])
    room = f.createIfcBuildingElementProxy(new(), oh, "Electrical room shell",
                                            "back and side walls; front wall cut away for viewing",
                                            None, f.createIfcLocalPlacement(storey.ObjectPlacement, ident),
                                            pds, "ROOM", "NOTDEFINED")
    vals = [f.createIfcPropertySingleValue("RoomName", None, f.create_entity("IfcLabel", "Room"), None),
            f.createIfcPropertySingleValue("ClearWidth", None, f.create_entity("IfcReal", 8.0), None)]
    pset = f.createIfcPropertySet(new(), oh, "RoomInformation", None, vals)
    f.createIfcRelDefinesByProperties(new(), oh, None, None, [room], pset)
    f.createIfcRelContainedInSpatialStructure(new(), oh, None, None, [room], storey)
    return f, room


def test_room_shell_walls_openings_and_synthesized_front():
    f, room = _room_shell_file()
    plc, geom = I.analyze_product(f, room, scale=1.0)
    psets = I._psets(room)
    shell = I._extract_room_shell(f, room, geom, psets)
    I._close_room(shell)
    ids = {w.wall_id: w for w in shell.walls}
    # three modeled + one synthesized closing wall
    assert set(ids) == {"W-N", "W-W", "W-E", "W-S"}
    assert ids["W-S"].synthesized is True
    assert not ids["W-N"].synthesized
    # the west wall carries the door opening (1.0 wide gap between the pieces,
    # head at the header's underside 2.2)
    west = ids["W-W"]
    assert len(west.openings) == 1
    op = west.openings[0]
    assert math.isclose(op.width_m, 2.0, abs_tol=1e-6)   # gap between -0.5 and -2.5
    assert math.isclose(op.head_height_m, 2.2, abs_tol=1e-6)
    # the door leaf matched to the west wall, swung out (leaf outside the room)
    assert shell.doors and shell.doors[0].wall_id == "W-W"
    assert shell.doors[0].swing == "out"
    # ring closed at the centerline corners: N/S span x -4.1..4.1
    n = ids["W-N"]
    assert math.isclose(abs(n.p0_m[0] - n.p1_m[0]), 8.2, abs_tol=1e-6)
    assert math.isclose(n.p0_m[1], 3.1, abs_tol=1e-6)
    # opening offset re-derived from the world anchor after closure: the
    # opening centre is y = -1.5; W wall runs north (y 3.1) -> south (-3.1)
    assert math.isclose(op.center_along_m, 3.1 - (-1.5), abs_tol=1e-6)
    # floor recorded
    assert shell.floor and math.isclose(shell.floor["footprint"]["xdim"], 8.0, abs_tol=1e-6)


def test_clearance_parser_clauses():
    d = ("Condition 2: 1.07 m (3.5 ft) at the 2500 A switchboard; 0.914 m (3 ft) x "
         "0.762 m x 1.98 m at panelboards and transformer")
    req = I._required_clearances(d)
    assert math.isclose(req["switchboard"], 1.07)
    assert math.isclose(req["panel"], 0.914)
    assert req["condition"] == 2


# ===========================================================================
# 3. semantics
# ===========================================================================

def test_parse_voltage_forms():
    v = I.parse_voltage("480Y/277 V")
    assert v["ll"] == 480.0 and v["ln"] == 277.0 and v["phases"] == 3 and v["wires"] == 4
    assert v["system"] == "480Y/277"
    v2 = I.parse_voltage("208Y/120 V")
    assert v2["ll"] == 208.0
    v3 = I.parse_voltage("480 V delta")
    assert v3["ll"] == 480.0
    assert I.parse_voltage(None) == {}


def test_normalize_contract_from_pset_and_name(synth):
    psets = {"PanelSchedule": {"PanelName": "DP-1", "Voltage": "480Y/277 V", "Phases": 3,
                               "Wires": 4, "BusRating": 400.0, "MainsType": "Main breaker",
                               "NumberOfCircuits": 42, "FedFrom": "MSB",
                               "Mounting": "Surface, wall, unistrut backing",
                               "FeederEntry": "Top, overhead EMT"}}
    con = I.normalize_contract(psets, name="DP-1 - distribution panelboard, 480Y/277 V",
                               object_type=None, description="Distribution panelboard",
                               tag="DP-1")
    assert con["PanelName"] == "DP-1"
    assert con["BusRating"] == 400.0
    assert con["MainsRating"] == 400.0                        # derived
    assert con["FedFrom"] == "MSB"
    assert con["_voltage"]["ll"] == 480.0
    assert con["_provenance"]["BusRating"] == "pset:PanelSchedule.BusRating"
    # name-text fallbacks when the pset is absent
    con2 = I.normalize_contract({}, name="Lighting panelboard - 100 A MLO - 30 space, 480Y/277 V",
                                object_type=None, description=None, tag="LP-7")
    assert con2["BusRating"] == 100.0
    assert con2["NumberOfCircuits"] == 30
    assert con2["MainsType"] == "Main lugs only"
    assert con2["Voltage"] == "480Y/277 V"
    assert con2["PanelName"] == "LP-7"


def test_classify_equipment_by_predefined_and_pset(synth):
    msb = synth.add_board("MSB - main switchboard 2500 A", "MSB", (0.0, 0.0, 0.0),
                          predefined="SWITCHBOARD",
                          psets={"SwitchboardSchedule": {"BusRating": 2500.0, "Voltage": "480Y/277 V"}})
    lp = synth.add_board("LP-4 - receptacle panelboard, 208Y/120 V", "LP-4", (2.0, 0.0, 0.0),
                         psets={"PanelSchedule": {"BusRating": 225.0, "Voltage": "208Y/120 V",
                                                   "MainsType": "Main breaker"}})
    dp = synth.add_board("DP-1 - distribution panelboard", "DP-1", (4.0, 0.0, 0.0),
                         psets={"PanelSchedule": {"BusRating": 400.0, "Voltage": "480Y/277 V",
                                                   "MainsType": "Main breaker"}})
    for prod, want in ((msb, "switchboard"), (lp, "receptacle_panelboard"),
                       (dp, "distribution_panelboard")):
        ps = I._psets(prod)
        con = I.normalize_contract(ps, name=prod.Name, object_type=None, description=None,
                                   tag=prod.Tag)
        assert I._classify_equipment(prod, ps, con) == want


def test_feeder_tree_from_fedfrom_and_conduit_corroboration():
    """Two boards fed from MSB; one conduit run corroborates one edge; the
    transformer's own kVA sizes its primary feeder."""
    def eqmk(tag, kind, con):
        return I.Equipment(step_id=0, guid=tag, ifc_class="IfcElectricDistributionBoard",
                           predefined_type=None, name=tag, tag=tag, description=None,
                           object_type=None, type_name=None, kind=kind, psets={},
                           contract=con, placement=I.Placement(np.eye(4)),
                           geometry=I.ProductGeometry(items=[]), fed_from=con.get("FedFrom"))
    msb = eqmk("MSB", "switchboard", {"BusRating": 2500.0})
    dp1 = eqmk("DP-1", "distribution_panelboard", {"FedFrom": "MSB", "MainsRating": 400.0,
                                                     "Voltage": "480Y/277 V", "Phases": 3})
    t1 = eqmk("T1", "transformer", {"FedFrom": "MSB", "RatingkVA": 150.0,
                                     "Primary": "480 V delta", "Secondary": "208Y/120 V"})
    lp4 = eqmk("LP-4", "receptacle_panelboard", {"FedFrom": "T1", "MainsRating": 225.0,
                                                   "Voltage": "208Y/120 V"})

    class _P:
        def __init__(self, name, sid):
            self.Name = name
            self._id = sid
        def id(self):
            return self._id
    # one conduit product with two named runs
    pts = np.zeros((8, 3))
    g = I.ProductGeometry(items=[
        I.GeomItem(1, "conduit_msb_dp1", "Body", 0.0, pts, np.zeros((0, 3), int)),
        I.GeomItem(2, "service_entrance_conduits", "Body", 0.0, pts, np.zeros((0, 3), int)),
    ])
    edges, runs = I._build_feeder_tree([msb, dp1, t1, lp4], [(_P("Feeders", 9), g)])
    by = {(e.source, e.target): e for e in edges}
    assert ("MSB", "DP-1") in by and by[("MSB", "DP-1")].from_pset
    assert by[("MSB", "DP-1")].conduit_items == ["conduit_msb_dp1"]     # corroborated
    assert by[("MSB", "DP-1")].as_json()["corroborated"] is True
    assert by[("MSB", "DP-1")].rating_a == 400.0
    # transformer primary sized from kVA: 150 kVA / (sqrt3 x 480 V) = 180.4 A
    assert by[("MSB", "T1")].kind == "primary"
    assert math.isclose(by[("MSB", "T1")].rating_a, 180.4, abs_tol=0.1)
    # LP-4 hangs off the transformer's SECONDARY
    assert by[("T1", "LP-4")].kind == "secondary"
    # the utility service edge from the service-entrance conduit
    assert ("UTILITY", "MSB") in by and by[("UTILITY", "MSB")].kind == "service"
    assert len(runs) == 2


# ===========================================================================
# 4. family mapping
# ===========================================================================

def _catalog_available():
    try:
        from rvt.famgen import catalog as C
        C.load_line("eaton", "pow-r-line-panelboards")
        C.load_line("eaton", "dry-type-transformers")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _catalog_available(), reason="famgen catalog absent")
def test_mapping_panels_transformer_and_switchboard_refusal():
    def eqmk(tag, kind, con, dims):
        e = I.Equipment(step_id=0, guid=tag, ifc_class="IfcElectricDistributionBoard",
                        predefined_type=None, name=tag, tag=tag, description=None,
                        object_type=None, type_name=None, kind=kind, psets={}, contract=con,
                        placement=I.Placement(np.eye(4)),
                        geometry=I.ProductGeometry(items=[]))
        e.dims_m = dims
        return e
    lp = eqmk("LP-1", "lighting_panelboard",
              {"BusRating": 100.0, "MainsType": "Main lugs only", "NumberOfCircuits": 30,
               "_voltage": {"system": "480Y/277"}, "PanelName": "LP-1"},
              {"w": 0.508, "d": 0.15, "h": 0.914})
    p = I.plan_family_for(lp)
    assert p.status == "resolved" and p.variant == "PRL2X"
    assert p.kwargs["mcb"] is False and p.kwargs["spaces"] == 30
    assert math.isclose(p.dims_catalog_m["w"], 20 / I.IN_PER_M, abs_tol=1e-6)   # 20-in box
    lp4 = eqmk("LP-4", "receptacle_panelboard",
               {"BusRating": 225.0, "MainsType": "Main breaker", "NumberOfCircuits": 42,
                "_voltage": {"system": "208Y/120"}, "PanelName": "LP-4"},
               {"w": 0.508, "d": 0.15, "h": 0.914})
    p4 = I.plan_family_for(lp4)
    assert p4.status == "resolved" and p4.variant == "PRL1X"                    # 208 V class
    t1 = eqmk("T1", "transformer", {"RatingkVA": 150.0, "Primary": "480 V delta",
                                    "Secondary": "208Y/120 V"}, {"w": 0.9, "d": 0.75, "h": 1.14})
    pt = I.plan_family_for(t1)
    assert pt.status == "resolved" and pt.variant == "V48M28T4916"              # 150 kVA member
    msb = eqmk("MSB", "switchboard",
               {"BusRating": 2500.0, "MainsRating": 2500.0, "Phases": 3, "Wires": 4,
                "ShortCircuitRatingkA": 65.0, "MainDevice": "insulated-case main breaker",
                "Manufacturer": "Eaton", "ModelLabel": "Pow-R-Line C style switchboard",
                "_voltage": {"system": "480Y/277", "phases": 3, "wires": 4}},
               {"w": 4.27, "d": 0.62, "h": 2.286})
    pm = I.plan_family_for(msb)
    assert pm.status == "house"
    assert pm.constructor.endswith("make_house_switchboard")
    assert pm.refusal and "2500" in pm.refusal                    # the honest refusal is recorded
    assert math.isclose(pm.kwargs["width_m"], 4.27)


@pytest.mark.skipif(not _catalog_available(), reason="famgen catalog absent")
def test_house_switchboard_composes_a_valid_family(tmp_path):
    prod = I.make_house_switchboard(tag="MSB", name="Switchboard MSB", mains_a=2500,
                                    voltage="480Y/277", phases=3, wires=4, sccr_ka=65,
                                    sections=4, width_m=4.27, depth_m=0.62, height_m=2.286,
                                    start_id=1000)
    s = prod.summary()
    assert s["kind"] == "switchboard"
    assert s["part_type"] == 16                                     # switchboard part type
    assert "Voltage" in s["parameters"] and "BusRating" in s["parameters"]
    assert s["connectors"] == 1
    out = tmp_path / "sb.rfa"
    rep = prod.write(str(out))
    assert rep["ok"], rep.get("validate")
    fm = (rep.get("validate") or {}).get("family_mode") or {}
    assert fm.get("verdict") == "VALID" and fm.get("n_errors") == 0
    assert (rep.get("provenance") or {}).get("ok") is True


# ===========================================================================
# 5. the real room file
# ===========================================================================

@pytest.fixture(scope="module")
def room_model():
    if not HAVE_ROOM:
        pytest.skip("inputs/ifc/electrical-room-2500a.ifc absent")
    return I.resolve_intent(ROOM_IFC)


@pytest.mark.skipif(not HAVE_ROOM, reason="room IFC absent")
def test_real_file_positions_are_resolved(room_model):
    m = room_model
    tags = {e.tag: e for e in m.equipment}
    for t in ("MSB", "DP-1", "DP-2", "LP-1", "LP-2", "LP-3", "LP-4", "T1"):
        assert t in tags
        e = tags[t]
        assert e.geometry.has_body
        assert not (abs(e.insertion_m[0]) < 1e-9 and abs(e.insertion_m[1]) < 1e-9), \
            f"{t} position still at the origin"
        # the placement chain composes to the identity in this writer's export
        assert e.placement.identity and e.placement.chain_depth == 4
        assert "geometry-recovered" in e.position_source
    # the mirrored panel banks: west-wall panels face +X, east-wall face -X
    assert np.allclose(tags["DP-1"].front_normal[:2], [1.0, 0.0])
    assert np.allclose(tags["DP-2"].front_normal[:2], [-1.0, 0.0])
    assert tags["DP-1"].frame_kind == "upright"
    assert tags["MSB"].frame_kind == "yaw" and tags["T1"].frame_kind == "yaw"
    assert np.allclose(tags["MSB"].front_normal[:2], [0.0, -1.0])          # faces the room
    # floor gear on the 100 mm housekeeping pad
    assert math.isclose(tags["MSB"].elevation_m, 0.1, abs_tol=1e-6)
    assert math.isclose(tags["T1"].elevation_m, 0.1, abs_tol=1e-6)
    # DP-1 mounting plane = enclosure back face at x = -4.455
    assert math.isclose(tags["DP-1"].insertion_m[0], -4.455, abs_tol=1e-6)
    assert m.audit["positions_all_zero"] is False
    assert m.audit["equipment_inside_room_ring"].split("/")[0] == \
        m.audit["equipment_inside_room_ring"].split("/")[1]


@pytest.mark.skipif(not HAVE_ROOM, reason="room IFC absent")
def test_real_file_room_walls_and_doors(room_model):
    r = room_model.room
    assert r is not None
    ids = {w.wall_id: w for w in r.walls}
    assert set(ids) == {"W-N", "W-S", "W-E", "W-W"}
    assert ids["W-S"].synthesized                                  # cut-away front wall
    assert not ids["W-N"].synthesized
    # a closed 9.2 x 6.2 m centerline ring
    ext = r.clear["centerline_extents_m"]
    assert math.isclose(ext["x"][1] - ext["x"][0], 9.2, abs_tol=1e-6)
    assert math.isclose(ext["y"][1] - ext["y"][0], 6.2, abs_tol=1e-6)
    # two out-swinging egress doors, one per side wall, 1.0 m openings, head 2.13
    assert len(r.doors) == 2
    assert {d.wall_id for d in r.doors} == {"W-E", "W-W"}
    for d in r.doors:
        assert d.swing == "out"
        assert math.isclose(d.width_m, 1.0, abs_tol=1e-6)
        assert math.isclose(d.head_height_m, 2.13, abs_tol=1e-6)
    # NEC 110.26 clearance depths honoured (1.07 m at the switchboard, 0.914 elsewhere)
    z = {c.equipment_tag: c for c in room_model.clearances}
    assert math.isclose(z["MSB"].depth_m, 1.07, abs_tol=1e-3) and z["MSB"].ok
    assert math.isclose(z["DP-1"].depth_m, 0.914, abs_tol=1e-3) and z["DP-1"].ok


@pytest.mark.skipif(not HAVE_ROOM, reason="room IFC absent")
def test_real_file_feeder_tree_fully_corroborated(room_model):
    m = room_model
    by = {(e.source, e.target): e for e in m.feeders}
    for edge in [("MSB", "DP-1"), ("MSB", "DP-2"), ("MSB", "LP-1"), ("MSB", "LP-2"),
                 ("MSB", "LP-3"), ("MSB", "T1"), ("T1", "LP-4")]:
        assert edge in by, edge
        e = by[edge]
        assert e.from_pset and e.conduit_items, f"{edge} not corroborated"
    assert by[("T1", "LP-4")].kind == "secondary"
    assert by[("MSB", "T1")].kind == "primary"
    assert ("UTILITY", "MSB") in by                                # the service entrance
    assert m.audit["feeder_edges_corroborated"] == 7
    assert m.audit["load_equipment_unfed"] == []


@pytest.mark.skipif(not (HAVE_ROOM and _catalog_available()), reason="room IFC / catalog absent")
def test_real_file_family_mapping_table(room_model):
    plans = {p.tag: p for p in room_model.family_plans}
    for t in ("DP-1", "DP-2"):
        assert plans[t].status == "resolved" and plans[t].variant == "PRL2X"
        assert plans[t].kwargs["mcb"] is True and plans[t].kwargs["spaces"] == 42
    for t in ("LP-1", "LP-2", "LP-3"):
        assert plans[t].variant == "PRL2X" and plans[t].kwargs["mcb"] is False
    assert plans["LP-4"].variant == "PRL1X"
    assert plans["T1"].variant == "V48M28T4916"
    assert plans["MSB"].status == "house" and plans["MSB"].refusal
    # unmapped items say why
    assert plans["CONDUIT"].status == "unmapped" and plans["CONDUIT"].refusal
    # the modeled width matches the Eaton box exactly (our writer models the catalog)
    assert math.isclose(plans["DP-1"].dims_modeled_m["w"], plans["DP-1"].dims_catalog_m["w"],
                        abs_tol=1e-3)


@pytest.mark.skipif(not HAVE_ROOM, reason="room IFC absent")
def test_intent_json_shape_and_roundtrip(room_model, tmp_path):
    js = I.intent_to_json(room_model)
    assert js["specVersion"] == I.INTENT_VERSION == "2.0"
    for key in ("levels", "walls", "equipment", "room", "clearances", "feederTree",
                "familyMapping", "audit", "notes"):
        assert key in js
    # every generated-family equipment record carries the resolved placement fields
    for e in js["equipment"]:
        assert "insertion_m" in e and "orientation" in e and "placementChain" in e
        assert e["placementChain"]["chain_depth"] == 4
    out = tmp_path / "room.intent.json"
    I.write_intent(room_model, str(out))
    back = json.loads(out.read_text())
    assert back["specVersion"] == "2.0"
    assert len(back["equipment"]) == len(room_model.equipment)
    assert len(back["feederTree"]["edges"]) == len(room_model.feeders)


# ===========================================================================
# 6. swept solids: IfcExtrudedAreaSolid bodies ride the tessellated path
#    (#152) -- hand-authored fixture + shared checks in
#    tests/fixtures_ifc_extrusion.py (test_steplite.py holds the stdlib
#    reader to the same tables)
# ===========================================================================

import fixtures_ifc_extrusion as FX  # noqa: E402  (tests/ is on sys.path under pytest)


@pytest.fixture(scope="module")
def extrusion_path(tmp_path_factory):
    return FX.write_fixture(str(tmp_path_factory.mktemp("extrusion")))


def test_extruded_profiles_become_world_upright_boxes(extrusion_path):
    """Rectangle (with a 2-D profile Position), IfcPolyline and
    IfcIndexedPolyCurve (with and without Segments) profiles, a solid
    Position rotated about Z, one extruded horizontally (Axis = +X), a
    rotated *placement*, an IfcMappedItem and a circle profile: each lands
    on its expected WORLD extents (storey at z = 3)."""
    FX.check_world_boxes(FX.geom_by_name(I, ifcopenshell.open(extrusion_path)))


def test_arc_index_is_polygonised_on_the_circle():
    pts = I._arc_through((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0))   # CCW semicircle
    assert len(pts) == I._ARC_SEGMENTS // 2 + 1                  # endpoints included
    assert all(math.isclose(math.hypot(x, y), 1.0, abs_tol=1e-9) for x, y in pts)
    assert pts[0] == (1.0, 0.0)
    assert math.isclose(pts[-1][0], -1.0, abs_tol=1e-9) and abs(pts[-1][1]) < 1e-9
    assert all(y > -1e-9 for _, y in pts)                        # the upper half
    cw = I._arc_through((1.0, 0.0), (0.0, -1.0), (-1.0, 0.0))   # CW: the lower half
    assert all(y < 1e-9 for _, y in cw)
    assert I._arc_through((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)) == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]


def test_extrusion_fixture_resolves_walls_equipment_and_world_z(extrusion_path):
    model = I.resolve_intent(extrusion_path, plan_families_flag=False)
    js = I.intent_to_json(model)
    FX.check_intent_json(js)
    # THE Z CONTRACT through the public helper: level-relative = world - datum
    for e in js["equipment"]:
        exp = FX.EXPECTED_EQUIPMENT[e["tag"]]
        assert math.isclose(I.level_relative_z(e["elevation_m"], js["levels"], e["level"]),
                            exp[3] - FX.STOREY_ORIGIN[2], abs_tol=1e-4)
