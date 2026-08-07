#!/usr/bin/env python3
"""make_type_proofs -- INJECTION PROOF for the genesis type constructors.

Builds three batches of OUR OWN system-family types / standards with
``rvt.genesis.types`` (plain parameters, zero cloned payload), injects each
batch into a copy of the MEP sample through the PROVEN commit path
(``rvt.commit.commit_new_elements``: host-document unit-0 records + ElemTable
rows + ECC re-framing + container rebuild), reads the result back
(``verify_written``) and runs the Autodesk-free arbiter
(``rvt.validate.validate_file`` == tools/rvt_validate.py) which must report
ZERO errors.  The sample project is only the INJECTION HOST for this proof
(the deliverable use of these constructors is the family-free genesis base).

Outputs (experiments/genesis/types/):
    T_walltype.rvt       wall (2) + floor + roof + ceiling types, their
                         materials + a fill pattern + a line pattern
    T_conduit_types.rvt  conduit standard + 2 conduit types, 2 cable-tray
                         types, wire (4 conductor cells + wire type),
                         wire symbol types
    T_settings.rvt       voltage types, distribution systems, demand factors,
                         load classifications, text type (4 elements),
                         sub-category + gstyle
    *.json               commit + read-back + validator reports
    proof_summary.json   the three verdicts

Run:  .venv/bin/python experiments/genesis/types/make_type_proofs.py
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.commit import commit_new_elements, verify_written        # noqa: E402
from rvt.mutate import Document                                     # noqa: E402
from rvt.validate import validate_file                               # noqa: E402
from rvt.genesis import types as G                                  # noqa: E402

PROJECT = "rmebasicsampleproject"
SRC = os.path.join(ROOT, "samples", f"{PROJECT}.rvt")


def build_walltype(doc) -> G.GenesisCatalog:
    cat = G.GenesisCatalog(ids=doc)
    dash = cat.line_pattern("GEN Dash 3mm", [("dash", 3.0), ("space", 3.0)])
    xhatch = cat.fill_pattern("GEN Diagonal crosshatch 3mm",
                              [{"angle_deg": 45, "spacing_mm": 3.0},
                               {"angle_deg": 135, "spacing_mm": 3.0}])
    solid = cat.fill_pattern("GEN Solid fill", [])
    conc = cat.material("GEN Concrete, Cast-in-Place", (192, 192, 192),
                        material_class="Concrete", category="Concrete",
                        cut_pattern_id=xhatch.elem_id)
    del dash  # the line pattern is exercised by T_settings' sub-category style
    gyp = cat.material("GEN Gypsum Wall Board", (250, 250, 245),
                       material_class="Gypsum Board", category="Interior")
    stud = cat.material("GEN Metal Stud Layer", (160, 160, 170),
                        material_class="Metal", category="Metal")
    ins = cat.material("GEN Mineral Wool Insulation", (240, 230, 140),
                       material_class="Insulation", category="Insulation")
    # 5-layer partition (finish / stud+insulation core / finish) and a
    # single-layer concrete wall -- exercises the vertical-region grid
    cat.wall_type("GEN Interior - 124mm Partition (1-hr)",
                  [("finish2", 16.0, gyp.elem_id),
                   ("thermal", 0.0, ins.elem_id),          # zero-width membrane-like
                   ("structure", 92.0, stud.elem_id),
                   ("finish1", 16.0, gyp.elem_id)],
                  function=0, fill_pattern_id=solid.elem_id)
    cat.wall_type("GEN Exterior - 200mm Concrete",
                  [("structure", 200.0, conc.elem_id)], function=1,
                  fill_pattern_id=solid.elem_id)
    cat.floor_type("GEN Slab - 150mm Concrete", [("structure", 150.0, conc.elem_id)],
                   fill_pattern_id=solid.elem_id)
    cat.roof_type("GEN Roof - 300mm Concrete", [("structure", 300.0, conc.elem_id)])
    cat.ceiling_type("GEN ACT - 16mm Gypsum on 30mm Grid",
                     [("finish2", 16.0, gyp.elem_id), ("structure", 30.0, G.INVALID)])
    return cat


def build_conduit(doc) -> G.GenesisCatalog:
    cat = G.GenesisCatalog(ids=doc)
    emt = cat.conduit_standard("GEN EMT")
    rmc = cat.conduit_standard("GEN RMC")
    # published ANSI trade sizes (inches): nominal, ID, OD, min bend radius
    cat.conduit_sizes({
        emt.elem_id: [(0.5, 0.622, 0.706, 4.35), (0.75, 0.824, 0.922, 4.96),
                      (1.0, 1.049, 1.163, 6.33), (1.25, 1.380, 1.510, 8.0),
                      (1.5, 1.610, 1.740, 9.12), (2.0, 2.067, 2.197, 10.6),
                      (2.5, 2.731, 2.875, 10.6), (3.0, 3.356, 3.500, 13.0),
                      (3.5, 3.834, 4.000, 15.0), (4.0, 4.334, 4.500, 16.0)],
        rmc.elem_id: [(0.5, 0.632, 0.840, 4.35), (0.75, 0.836, 1.050, 4.96),
                      (1.0, 1.063, 1.315, 5.75), (2.0, 2.083, 2.375, 9.5),
                      (3.0, 3.090, 3.500, 13.0), (4.0, 4.050, 4.500, 16.0)]})
    cat.conduit_type("GEN Conduit - EMT (no fittings)", standard_id=emt.elem_id,
                     with_fitting=False)
    cat.conduit_type("GEN Conduit - RMC with Fittings", standard_id=rmc.elem_id,
                     with_fitting=True)
    cat.cable_tray_sizes([4, 6, 8, 12, 18, 24, 30, 36])
    cat.cable_tray_type("GEN Ladder Cable Tray", shape="ladder", with_fitting=True)
    cat.cable_tray_type("GEN Solid Bottom Cable Tray", shape="ushape", with_fitting=True)
    # wire: complete definition (4 conductor cells + the type) + symbol types
    cat.wire_type_full("GEN THWN Copper", material="Copper", temperature="75",
                       insulation="THWN", max_size=("500", 21.79))
    cat.add(G.new_wire_material_type("GEN Copper", ids=cat))
    cat.add(G.new_wire_insulation_type("GEN THWN", ids=cat))
    cat.add(G.new_wire_temperature_rating_type("75", ids=cat))
    return cat


def build_settings(doc) -> G.GenesisCatalog:
    cat = G.GenesisCatalog(ids=doc)
    v120 = cat.voltage_type("GEN 120", 120)
    v208 = cat.voltage_type("GEN 208", 208)
    v277 = cat.voltage_type("GEN 277", 277)
    v480 = cat.voltage_type("GEN 480", 480)
    cat.distribution_system("GEN 120/208 Wye", phase="three", config="wye", wires=4,
                            voltage_ll_id=v208.elem_id, voltage_lg_id=v120.elem_id)
    cat.distribution_system("GEN 480/277 Wye", phase="three", config="wye", wires=4,
                            voltage_ll_id=v480.elem_id, voltage_lg_id=v277.elem_id)
    dlt = cat.demand_factor("GEN Lighting DF", 1.0)
    drc = cat.demand_factor("GEN Receptacle DF", 1.0,
                            rows=[(0.0, 10000.0, 1.0), (10000.0, 1e30, 0.5)],
                            rule="load")
    dmt = cat.demand_factor("GEN Motor DF", 1.25)
    cat.load_class("GEN Lighting", dlt.elem_id)
    cat.load_class("GEN Receptacle", drc.elem_id)
    cat.load_class("GEN Motor", dmt.elem_id)
    cat.text_type("GEN 3.2mm Arial", font="Arial", size_mm=3.2)
    cat.text_type("GEN 2.5mm Arial Narrow", font="Arial Narrow", size_mm=2.5)
    # a document sub-category with its own line style (a legal genesis-side
    # analogue of the OBJECT-STYLES table without duplicating built-in rows)
    dash = cat.line_pattern("GEN Hidden 2mm", [("dash", 4.0), ("space", 2.0)])
    gs_id = cat.next_id()
    sub = cat.add(G.new_category("GEN Cable Tray Center Lines", -2008130,
                                 owner_id=-1, category_type=1, flags=7,
                                 gstyle_ids=[gs_id], ids=cat))
    cat.add(G.new_gstyle(sub.elem_id, style_type="projection", pen=1, color=0,
                         line_pattern_id=dash.elem_id, elem_id=gs_id))
    return cat


def template_document_guid(src_rvt: str) -> str:
    """The template's own document GUID (BasicFileInfo == History entry[0]).

    The commit path's G2 identity writer (rvt.identity) stamps a FRESH
    document GUID into BasicFileInfo but does not (yet) prepend a matching
    History episode, which the L2 consistency layer flags ('Unique Document
    GUID != History entry[0] GUID').  That is a writer/identity gap outside
    this stream's territory (recorded in docs/inbox/systemtypes.md); for
    these proofs we keep the template's GUID via the identity parameter so
    the arbiter judges ONLY the injected types.
    """
    from rvt.container import open_rvt
    from rvt import stream_encoders as se
    with open_rvt(src_rvt) as d:
        model = se.decode_basic_file_info(d.raw("BasicFileInfo"))
    return model["unique_document_guid"]


def prove(name: str, cat: G.GenesisCatalog, out_dir: str) -> dict:
    out = os.path.join(out_dir, f"T_{name}.rvt")
    rt = cat.roundtrip()
    dang = cat.check_references()
    t0 = time.time()
    rep, ver = cat.commit_into(SRC, out,
                               identity={"document_guid": template_document_guid(SRC)})
    t_commit = time.time() - t0
    t0 = time.time()
    vrep = validate_file(out)
    t_val = time.time() - t0
    summary = {
        "file": out, "records": len(cat.records),
        "classes": sorted({r.class_name for r in cat.records}),
        "roundtrip_ok": f"{rt['ok']}/{rt['records']}",
        "dangling_refs": len(dang),
        "commit": {"elemtable_before": rep.elemtable_count_before,
                   "elemtable_after": rep.elemtable_count_after,
                   "watermark_after": rep.watermark_after,
                   "bytes_added": rep.per_seq_bytes_added, "seconds": round(t_commit, 1)},
        "readback": {"crc_failures": ver["crc_failures"],
                     "ecc_mismatches": ver["ecc_mismatches"],
                     "walker_errors": ver["walker_errors"],
                     "elemtable_count": ver["elemtable_count"],
                     "header_count": ver["header_count"],
                     "sentinel_last": {str(k): v for k, v in ver["sentinel_last"].items()},
                     "stamps_ok": ver["stamps_ok"],
                     "new_ids_found_seq102": len(ver["new_ids_found"].get(102, {})),
                     "new_ids_clean_seq102": sum(
                         1 for v in ver["new_ids_found"].get(102, {}).values() if v.get("clean"))},
        "validator": {"ok": vrep.ok, "errors": len(vrep.errors),
                      "warnings": len(vrep.warnings), "seconds": round(t_val, 1),
                      "error_list": [str(e) for e in vrep.errors[:10]]},
    }
    with open(os.path.join(out_dir, f"T_{name}.json"), "w") as fh:
        json.dump({"summary": summary, "catalog": cat.to_json()}, fh, indent=1,
                  default=str)
    print(f"== T_{name}: {summary['records']} records "
          f"({len(summary['classes'])} classes), roundtrip {summary['roundtrip_ok']}, "
          f"dangling {summary['dangling_refs']}")
    print(f"   commit: ElemTable {rep.elemtable_count_before} -> {rep.elemtable_count_after}, "
          f"bytes added {rep.per_seq_bytes_added} ({t_commit:.1f}s)")
    print(f"   readback: crc {ver['crc_failures']} ecc {ver['ecc_mismatches']} "
          f"walker {ver['walker_errors']} stamps_ok {ver['stamps_ok']} "
          f"count {ver['elemtable_count']}=={ver['header_count']} "
          f"new102 clean {summary['readback']['new_ids_clean_seq102']}/"
          f"{summary['readback']['new_ids_found_seq102']}")
    print(f"   VALIDATOR: {'OK' if vrep.ok else 'FAIL'} errors={len(vrep.errors)} "
          f"warnings={len(vrep.warnings)} ({t_val:.1f}s)")
    for e in vrep.errors[:8]:
        print("      ERROR:", e)
    return summary


def main() -> int:
    doc = Document.load(PROJECT)
    builders = [("walltype", build_walltype), ("conduit_types", build_conduit),
                ("settings", build_settings)]
    results = {}
    for name, fn in builders:
        cat = fn(doc)
        results[name] = prove(name, cat, HERE)
        # each proof restarts from the untouched template: reset the id
        # allocator so ids stay above the template watermark either way
    with open(os.path.join(HERE, "proof_summary.json"), "w") as fh:
        json.dump(results, fh, indent=1, default=str)
    allok = all(r["validator"]["ok"] and r["validator"]["errors"] == 0
                for r in results.values())
    print("\nALL PROOFS", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
