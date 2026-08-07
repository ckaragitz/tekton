#!/usr/bin/env python3
"""
Validate the canonical tekton-ifc exporter outputs.

Run after `node run-export.mjs` (which writes tests/out/example-auto.ifc
and tests/out/example-tess.ifc):

    ../../../.venv/bin/python validate_export.py

Checks (asserts) — see docs/design-ground-truth.md section 6 (R1-R10):
  * both files parse (IFC4) and pass ifcopenshell.validate (json rules)
  * both storeys exist with the right elevations
  * exactly ONE shared IfcElectricDistributionBoardType for the two ground-
    floor boards, RelDefinesByType lists both (R3); the L2 board differs
  * auto mode: IfcExtrudedAreaSolid present + an IfcArbitraryProfileDefWithVoids
    (the holed dead front) + IfcMappedItem instancing (R2/R4)
  * tessellation mode: geometry is only IfcTriangulatedFaceSet (v1 fallback)
  * exclusions: no product corresponds to working_clearance (R5)
  * an IfcSpace exists, aggregated to Level 1 (R6)
  * real placements: distinct, non-identity insertion points; the second
    panel carries a rotated axis (R1)
  * entity count auto < tessellation (R10)
  * geometry consistency: per-product world bounding boxes match between the
    solid (auto) and tessellated exports (validates y-up->z-up + placements)
  * ISO-10303-21 unicode / apostrophe escaping round-trips (R9)
"""
from __future__ import annotations

import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.validate as V
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
AUTO = OUT / "example-auto.ifc"
TESS = OUT / "example-tess.ifc"

FAILS: list[str] = []


def check(cond, msg):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {msg}")
    if not cond:
        FAILS.append(msg)


def load(path: Path):
    print(f"\n--- {path.relative_to(HERE)} ---")
    m = ifcopenshell.open(str(path))
    print(f"  schema={m.schema}  entities={len(list(m))}  bytes={path.stat().st_size}")
    return m


def validate(m, name):
    log = V.json_logger()
    V.validate(m, log, express_rules=False)
    issues = [s for s in log.statements
              if str(s.get("level", "")).lower() in ("error", "warning")]
    for s in issues[:20]:
        print(f"    validate: {s.get('level')}: {s.get('message')}")
    check(len(issues) == 0, f"{name}: ifcopenshell.validate reports zero errors/warnings ({len(issues)} found)")
    return issues


def storeys(m):
    return {s.Name: float(s.Elevation or 0.0) for s in m.by_type("IfcBuildingStorey")}


def placement_location(product):
    """Absolute (z-up world) location of a product's local placement."""
    m4 = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
    return m4[:3, 3], m4[:3, :3]


def world_bboxes(m):
    """GlobalId -> (min, max) world-space bbox via ifcopenshell.geom."""
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    out = {}
    for p in m.by_type("IfcProduct"):
        if p.is_a("IfcSpatialStructureElement") and not p.is_a("IfcSpace"):
            continue
        if not p.Representation:
            continue
        try:
            shape = ifcopenshell.geom.create_shape(settings, p)
        except Exception as e:  # pragma: no cover
            print(f"    geom failed for {p.is_a()} {p.Name}: {e}")
            continue
        v = np.array(shape.geometry.verts).reshape(-1, 3)
        if len(v):
            out[p.GlobalId] = (v.min(axis=0), v.max(axis=0), p.Name)
    return out


def main() -> int:
    import ifcopenshell.util.placement  # noqa: F401

    ok_files = True
    for p in (AUTO, TESS):
        if not p.exists():
            print(f"missing {p} — run `node run-export.mjs` first")
            ok_files = False
    if not ok_files:
        return 2

    auto = load(AUTO)
    tess = load(TESS)

    print("\n== schema validation (ifcopenshell.validate, json rules)")
    validate(auto, "auto")
    validate(tess, "tess")
    check(auto.schema == "IFC4" and tess.schema == "IFC4", "both files are IFC4")

    # ---------------------------------------------------------------- storeys
    print("\n== spatial structure (R6)")
    for m, name in ((auto, "auto"), (tess, "tess")):
        st = storeys(m)
        check(abs(st.get("Level 1", 999)) < 1e-9, f"{name}: 'Level 1' storey at elevation 0")
        check(abs(st.get("Level 2", 999) - 4.0) < 1e-9, f"{name}: 'Level 2' storey at elevation 4")
        check(len(st) == 2, f"{name}: exactly two storeys")
        # containment / aggregation exist
        rels = m.by_type("IfcRelContainedInSpatialStructure")
        check(len(rels) == 2, f"{name}: one IfcRelContainedInSpatialStructure per storey ({len(rels)})")

    # ---------------------------------------------------------------- types R3
    print("\n== shared types (R3)")
    for m, name in ((auto, "auto"), (tess, "tess")):
        boards = m.by_type("IfcElectricDistributionBoard")
        check(len(boards) == 3, f"{name}: three IfcElectricDistributionBoard occurrences ({len(boards)})")
        gnd = [b for b in boards if b.Name in ("B-HG4", "B-HQ1")]
        check(len(gnd) == 2, f"{name}: two ground-floor boards B-HG4 / B-HQ1")
        types = {}
        for rel in m.by_type("IfcRelDefinesByType"):
            for obj in rel.RelatedObjects:
                types[obj.GlobalId] = rel.RelatingType
        t1, t2 = types[gnd[0].GlobalId], types[gnd[1].GlobalId]
        check(t1 is not None and t1 == t2 and t1.is_a("IfcElectricDistributionBoardType"),
              f"{name}: the two ground-floor boards share ONE IfcElectricDistributionBoardType")
        # exactly one type object of that name, and its rel lists both boards
        same_name = [t for t in m.by_type("IfcElectricDistributionBoardType") if t.Name == t1.Name]
        check(len(same_name) == 1, f"{name}: exactly one type object named '{t1.Name}'")
        rel = [r for r in m.by_type("IfcRelDefinesByType") if r.RelatingType == t1][0]
        related = {o.GlobalId for o in rel.RelatedObjects}
        check(gnd[0].GlobalId in related and gnd[1].GlobalId in related and len(related) == 2,
              f"{name}: IfcRelDefinesByType for the shared type lists BOTH boards (and only them)")
        l2 = [b for b in boards if b.Name == "B-LQ2"][0]
        check(types[l2.GlobalId] != t1, f"{name}: the Level-2 board has its own (different) type")
        # type psets attach ONCE to the shared type
        check(t1.HasPropertySets is not None and len(t1.HasPropertySets) >= 1,
              f"{name}: shared type carries the typePsets (Pset_ManufacturerTypeInformation)")

    # ------------------------------------------------------------ geometry R2/R4
    print("\n== geometry representations (R2, R4)")
    n_solid_auto = len(auto.by_type("IfcExtrudedAreaSolid"))
    n_voids_auto = len(auto.by_type("IfcArbitraryProfileDefWithVoids"))
    n_mapped_auto = len(auto.by_type("IfcMappedItem"))
    n_maps_auto = len(auto.by_type("IfcRepresentationMap"))
    n_face_auto = len(auto.by_type("IfcTriangulatedFaceSet"))
    print(f"    auto: extrudedSolids={n_solid_auto} voidProfiles={n_voids_auto} "
          f"mappedItems={n_mapped_auto} maps={n_maps_auto} faceSets={n_face_auto}")
    check(n_solid_auto > 0, "auto: contains IfcExtrudedAreaSolid entities")
    check(n_voids_auto >= 1, "auto: contains IfcArbitraryProfileDefWithVoids (the holed dead front)")
    check(n_mapped_auto >= 2, "auto: IfcMappedItem instancing present")
    check(n_maps_auto >= 1, "auto: IfcRepresentationMap present")
    check(n_face_auto >= 1, "auto: baked/merged geometry still falls back to a triangulated face set")
    # rectangle + circle + arbitrary profiles all present
    check(len(auto.by_type("IfcRectangleProfileDef")) > 0 and len(auto.by_type("IfcCircleProfileDef")) > 0
          and len(auto.by_type("IfcArbitraryProfileDefWithVoids")) > 0,
          "auto: box (rectangle), cylinder (circle) and holed extrusion (arbitrary-with-voids) profiles all present")
    # solids reference no dangling profiles / positions
    for s in auto.by_type("IfcExtrudedAreaSolid"):
        assert s.SweptArea is not None and s.Position is not None and s.ExtrudedDirection is not None and s.Depth > 0
    check(True, "auto: every IfcExtrudedAreaSolid has profile, position, direction and positive depth")

    n_solid_tess = len(tess.by_type("IfcExtrudedAreaSolid"))
    n_mapped_tess = len(tess.by_type("IfcMappedItem"))
    n_face_tess = len(tess.by_type("IfcTriangulatedFaceSet"))
    body_items_tess = set()
    for rep in tess.by_type("IfcShapeRepresentation"):
        if rep.RepresentationIdentifier == "Body":
            for it in rep.Items:
                body_items_tess.add(it.is_a())
    print(f"    tess: extrudedSolids={n_solid_tess} mappedItems={n_mapped_tess} faceSets={n_face_tess} "
          f"bodyItemTypes={sorted(body_items_tess)}")
    check(n_solid_tess == 0 and n_mapped_tess == 0, "tess: no solids and no mapped items (v1 behaviour)")
    check(body_items_tess == {"IfcTriangulatedFaceSet"}, "tess: Body items are ONLY IfcTriangulatedFaceSet")
    check(len(tess.by_type("IfcExtrudedAreaSolid")) == 0 and len(tess.by_type("IfcArbitraryProfileDefWithVoids")) == 0,
          "tess: no parametric profile entities at all")

    # shared assembly map attached to the shared type (canonical type-geometry pattern)
    shared_type = [t for t in auto.by_type("IfcElectricDistributionBoardType") if "400A" in (t.Name or "")]
    check(len(shared_type) == 1 and shared_type[0].RepresentationMaps and len(shared_type[0].RepresentationMaps) == 1,
          "auto: the shared board type carries ONE RepresentationMap (type-level geometry)")
    if shared_type and shared_type[0].RepresentationMaps:
        tmap = shared_type[0].RepresentationMaps[0]
        boards_using = 0
        for b in auto.by_type("IfcElectricDistributionBoard"):
            for rep in (b.Representation.Representations if b.Representation else []):
                for it in rep.Items:
                    if it.is_a("IfcMappedItem") and it.MappingSource == tmap:
                        boards_using += 1
        check(boards_using == 2, f"auto: both ground-floor boards reference the type's map via IfcMappedItem ({boards_using})")

    # ------------------------------------------------------------ exclusions R5
    print("\n== exclusions (R5)")
    for m, name in ((auto, "auto"), (tess, "tess")):
        prods = m.by_type("IfcProduct")
        bad = [p for p in prods if p.Name and ("clearance" in p.Name.lower())]
        check(len(bad) == 0, f"{name}: NO product corresponds to working_clearance / door_swing_clearance ({len(bad)})")
        # nor any styled item / representation named clearance
        badstyle = [s for s in m.by_type("IfcStyledItem") if s.Name and "clearance" in s.Name.lower()]
        check(len(badstyle) == 0, f"{name}: no clearance geometry leaked into styled items")
        # screws (ifcLOD='skip') absent from geometry names
        screws = [s for s in m.by_type("IfcStyledItem") if s.Name and "screw" in s.Name.lower()]
        check(len(screws) == 0, f"{name}: ifcLOD='skip' meshes (screws) dropped from geometry")

    # -------------------------------------------------------------- spaces R6
    print("\n== spaces (R6)")
    for m, name in ((auto, "auto"), (tess, "tess")):
        spaces = m.by_type("IfcSpace")
        check(len(spaces) >= 1, f"{name}: an IfcSpace exists ({len(spaces)})")
        if spaces:
            sp = spaces[0]
            check(sp.Name == "Electrical Room 101", f"{name}: space named 'Electrical Room 101'")
            agg_parent = None
            for rel in m.by_type("IfcRelAggregates"):
                if sp in rel.RelatedObjects:
                    agg_parent = rel.RelatingObject
            check(agg_parent is not None and agg_parent.is_a("IfcBuildingStorey") and agg_parent.Name == "Level 1",
                  f"{name}: IfcSpace AGGREGATED to storey 'Level 1' (not contained)")
            contained = any(sp in rel.RelatedElements for rel in m.by_type("IfcRelContainedInSpatialStructure"))
            check(not contained, f"{name}: IfcSpace is not in a containment relationship")

    # ---------------------------------------------------------- placements R1
    print("\n== placements (R1)")
    import ifcopenshell.util.placement as _pl  # noqa
    for m, name in ((auto, "auto"), (tess, "tess")):
        elements = [e for e in m.by_type("IfcElement")]
        locs = {}
        for e in elements:
            m4 = _pl.get_local_placement(e.ObjectPlacement)
            locs[e.Name] = m4
        # distinct insertion points
        pts = [tuple(np.round(v[:3, 3], 6)) for v in locs.values()]
        check(len(set(pts)) == len(pts), f"{name}: every IfcElement has a DISTINCT ObjectPlacement location")
        nonidentity = [n for n, v in locs.items() if np.linalg.norm(v[:3, 3]) > 1e-6]
        check(len(nonidentity) == len(elements), f"{name}: every IfcElement placement is non-identity (not world origin)")
        # the second panel: expected world insertion (3.32, -0.6, 1.0) [z-up] and rotated axes
        p2 = locs.get("B-HQ1")
        check(p2 is not None, f"{name}: second panel B-HQ1 present")
        if p2 is not None:
            expect = np.array([3.32, -0.6, 1.0])  # three (3.32, 1.0, 0.6) → ifc (x, -z, y)
            check(np.allclose(p2[:3, 3], expect, atol=1e-6),
                  f"{name}: B-HQ1 insertion point == (3.32,-0.6,1.0) [{np.round(p2[:3,3],4)}]")
            xdir = p2[:3, :3] @ np.array([1, 0, 0])
            check(abs(xdir[0]) < 1e-6 and abs(abs(xdir[1]) - 1) < 1e-6,
                  f"{name}: B-HQ1 placement is ROTATED (local x → world ±y) [{np.round(xdir,4)}]")
        p1 = locs.get("B-HG4")
        if p1 is not None:
            check(np.allclose(p1[:3, 3], np.array([-1.8, 2.32, 1.0]), atol=1e-6),
                  f"{name}: B-HG4 insertion point == (-1.8,2.32,1.0) [{np.round(p1[:3,3],4)}]")

    # ---------------------------------------------------------- size R10
    print("\n== size / entity counts (R10)")
    na, nt = len(list(auto)), len(list(tess))
    ba, bt = AUTO.stat().st_size, TESS.stat().st_size
    print(f"    auto: {na} entities / {ba} bytes;  tess: {nt} entities / {bt} bytes")
    check(na < nt, f"entity count auto ({na}) < tessellation ({nt})")
    check(ba < bt / 4, f"auto file is >4x smaller than tessellation ({ba} vs {bt})")

    # ------------------------------------------------- geometry cross-check
    print("\n== geometry consistency auto vs tess (validates R1 placement math + y-up->z-up)")
    bb_a, bb_t = world_bboxes(auto), world_bboxes(tess)
    common = set(bb_a) & set(bb_t)
    check(len(common) >= 6, f"products comparable across modes via stable GlobalIds ({len(common)})")
    worst = 0.0
    for gid in sorted(common):
        (mina, maxa, nm), (mint, maxt, _) = bb_a[gid], bb_t[gid]
        d = max(np.abs(mina - mint).max(), np.abs(maxa - maxt).max())
        worst = max(worst, d)
        print(f"    {nm[:32]:34s} bbox Δ={d:.4f} m  extent(auto)={np.round(maxa-mina,3)}")
    check(worst < 0.02, f"solid (auto) vs tessellated world bboxes agree within 2 cm (worst {worst:.4f} m)")

    # room space bbox sanity: 7 x 5 footprint, 3.2 m tall in world z
    for gid, (mn, mx, nm) in bb_a.items():
        if nm == "Electrical Room 101":
            ext = mx - mn
            check(abs(ext[0] - 7.0) < 1e-3 and abs(ext[1] - 5.0) < 1e-3 and abs(ext[2] - 3.2) < 1e-3
                  and abs(mn[2]) < 1e-3, f"IfcSpace geometry is 7 x 5 x 3.2 m, base at z=0 (extent {np.round(ext,3)})")

    # ------------------------------------------------------------ escaping R9
    print("\n== string escaping (R9)")
    p1a = [b for b in auto.by_type("IfcElectricDistributionBoard") if b.Name == "B-HG4"][0]
    desc = p1a.Description or ""
    check("—" in desc and "O'Malley" in desc and "Ø" in desc and "″" in desc,
          f"unicode (em dash, Ø, ″) + apostrophe round-trip through \\X2\\ / '' escaping [{desc!r}]")
    raw = AUTO.read_text()
    check("\\X2\\2014\\X0\\" in raw and "O''Malley" in raw, "raw STEP text uses \\X2\\..\\X0\\ and doubled apostrophes")
    check("$;\n" not in raw, "no dangling '$' entity lines")
    # no dangling references: every #id referenced is defined
    import re
    defined = {int(x) for x in re.findall(r"^#(\d+)=", raw, flags=re.M)}
    referenced = {int(x) for x in re.findall(r"#(\d+)(?!\d*=)", raw)}
    dangling = referenced - defined
    check(not dangling, f"no dangling # references ({len(dangling)} dangling)")

    # ---------------------------------------------------------- application R8
    apps = auto.by_type("IfcApplication")
    check(any(a.ApplicationFullName == "tekton-ifc exporter" for a in apps), "IfcApplication = 'tekton-ifc exporter'")
    oh = auto.by_type("IfcOwnerHistory")
    check(len(oh) == 1 and oh[0].OwningUser.TheOrganization.Name == "tekton", "owner history person/org from meta.author")

    # ---------------------------------------- extra scenario outputs (if any)
    scen = sorted(OUT.glob("scenario-*.ifc"))
    if scen:
        print(f"\n== extra scenario outputs ({len(scen)}) — parse + schema validation")
        for sp in scen:
            try:
                sm = ifcopenshell.open(str(sp))
                log = V.json_logger()
                V.validate(sm, log, express_rules=False)
                iss = [s for s in log.statements if str(s.get('level', '')).lower() in ('error', 'warning')]
                check(len(iss) == 0, f"{sp.name}: parses ({len(list(sm))} entities) with zero schema issues")
            except Exception as e:  # pragma: no cover
                check(False, f"{sp.name}: failed to parse/validate ({e})")

    # ------------------------------------------------------------------------
    print("\n" + "=" * 72)
    if FAILS:
        print(f"VALIDATION FAILED: {len(FAILS)} assertion(s)")
        for f in FAILS:
            print("   - " + f)
        return 1
    print("VALIDATION PASSED: all assertions hold for both auto and tessellation exports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
