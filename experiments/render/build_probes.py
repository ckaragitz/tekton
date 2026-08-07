"""Build the RENDER probe files: our created walls WITH authored baked
B-rep solids (rvt.render.brep), on the LOAD-certified walls-only base.

Base = experiments/ifc_room/electrical_room_2500a_walls_only_unjoined.rvt --
the viewer-certified file whose model tree held ONLY the level node (walls
invisible; the LOAD != RENDER finding).  We replace each of our four walls'
seq-103 SerializedDummy with an authored GElement solid, keeping every other
byte (object records, headers, ElemTable, Global/Latest) --
rvt.regadd.substitute_elements(seqs=(103,)).

Variants:
  A  RSOLID_walls_A_solid.rvt             solid only (the primary probe)
  B  RSOLID_walls_B_solid_refplanes.rvt   solid + 4 ref-plane sub-graphics
See docs/writer/baked-geometry.md sec. 6-7 and experiments/render/probes.json.

Run:  .venv/bin/python experiments/render/build_probes.py
"""
import json
import os
import time

from rvt.mutate import Document
from rvt.regadd import substitute_elements
from rvt.render import inspect as RI
from rvt.render.brep import CLASS_GELEMENT, wall_rep_from_object

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "experiments", "ifc_room",
                    "electrical_room_2500a_walls_only_unjoined.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "render")

#: 'Precast aerated concrete' -- the wall type's finish material, present in the base
FINISH_MATERIAL = 600660
#: the wall ref-plane subcategory GStyle -- present in the base (Walls GStyle 30 is NOT)
REFPLANE_GSTYLE = 24925


def build(variant: str) -> dict:
    doc = Document.from_file(BASE)
    walls = [w for w in sorted(doc.ids_of_class("SWall", host_only=True)) if w > 1470000]
    if len(walls) != 4:
        raise RuntimeError(f"expected our 4 created walls, found {walls}")
    records: dict = {}
    manifest = []
    with_rp = variant == "B"
    for w in walls:
        obj = doc.value(w, 102)
        rep, geom, tags = wall_rep_from_object(
            obj, element_id=w,
            root_category_id=-1,          # NO Walls-category GStyle in this base
            side_material_id=FINISH_MATERIAL, end_material_id=-1,
            with_ref_planes=with_rp, refplane_gstyle_id=REFPLANE_GSTYLE)
        records[w] = {103: (CLASS_GELEMENT, rep)}
        manifest.append({
            "id": w,
            "line_ft": [[round(x, 4) for x in geom.p0], [round(x, 4) for x in geom.p1]],
            "length_ft": round(geom.length, 4),
            "thickness_ft": round(geom.thickness, 4),
            "base_z_ft": geom.base_z, "height_ft": round(geom.height, 4),
            "tags": {"faces": {str(k): v for k, v in tags.faces.items()},
                     "edges": tags.edges, "source": tags.source},
            "ref_planes": with_rp,
        })
    name = {"A": "RSOLID_walls_A_solid.rvt",
            "B": "RSOLID_walls_B_solid_refplanes.rvt"}[variant]
    out = os.path.join(OUT_DIR, name)
    t0 = time.time()
    rep = substitute_elements(BASE, out, records, seqs=(103,), keep_row=True,
                              verify=True, diff=True)
    dt = time.time() - t0
    print(f"\n=== variant {variant} -> {out} ({dt:.1f}s)")
    print("  verdict:", rep.verdict, "problems:", rep.problems)
    print("  record_len_delta:", rep.record_len_delta)
    print("  validator:", json.dumps(rep.validator, default=str)[:260])
    print("  structural:", json.dumps(rep.structural, default=str)[:260])
    doc2 = Document.from_file(out)
    rows = []
    for w in walls:
        r = RI.inspect_element(doc2, w)
        print(f"  wall {w}: kind={r.kind} baked={r.has_baked_geometry} "
              f"bytes={r.geometry_bytes} solids={r.n_solids} faces={r.n_faces} "
              f"edges={r.n_edges} styles={r.render_style_ids}")
        rows.append(r.to_json())
    return {"variant": variant, "file": out, "verdict": rep.verdict,
            "problems": rep.problems, "walls": manifest, "rows_after": rows,
            "record_len_delta": rep.record_len_delta,
            "validator": rep.validator, "structural": rep.structural}


def main() -> int:
    results = [build("A"), build("B")]
    rec = os.path.join(OUT_DIR, "build_record.json")
    with open(rec, "w") as fh:
        json.dump({"base": BASE, "finish_material": FINISH_MATERIAL,
                   "refplane_gstyle": REFPLANE_GSTYLE, "results": results},
                  fh, indent=1, default=str)
    print("\nwrote", rec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
