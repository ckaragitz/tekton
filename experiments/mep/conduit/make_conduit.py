#!/usr/bin/env python3
"""make_conduit.py — build the CONDUIT / CABLE-TRAY proof files (MEP stream: conduit).

Every file is written from the Revit MEP sample (samples/rmebasicsampleproject.rvt)
by the conduit CRUD module (src/rvt/mep/conduit.py) and then proven three ways:

  * STRUCTURAL — rvt.commit.verify_written / rvt.manipulate.verify_manipulated
    (gzip CRC of every member, per-page CRCIO ECC byte-exact, framing walker,
    block-counter identity, header count == ElemTable count, sentinels last,
    adler32 record stamps, new/edited records re-decode clean, deleted ids gone);
  * SEMANTIC — the written file is re-opened with rvt.mutate.Document.from_file
    and the conduit model is read back (run member order, per-conduit length /
    size / level offsets, mutual connector graph, centre-line ownership, elbow
    corner frame + shared symbol clone);
  * THE VALIDATOR — tools/rvt_validate.py (rvt.validate.validate_file), all
    three layers; every proof file must have ZERO errors.

Outputs (experiments/mep/conduit/):
    conduit_create.rvt          a 3-segment 2" RNC Sch-80 run with TWO real 90° elbow
                                fittings (the flexible-family symbol clone REUSED),
                                every companion centre-line, one ConduitRun
    conduit_create_straight.rvt 3 disjoint straight runs (horizontal / riser / diagonal)
                                — the fitting-free fallback
    conduit_modify.rvt          RESIZE (686270 2"->1"), MOVE (run 679175, 3 conduits +
                                2 elbows + centre-lines, rigid), EXTEND (686514 open
                                end +3 ft), RETYPE (run 688539 -> type 662475)
    conduit_delete.rvt          DELETE run 679090 (3 conduits + 2 elbows + 5 centre-lines
                                + run; transformer connector neutralised) and DELETE
                                fitting 688548 (elbow + its centre-line; conduits'
                                connector refs and the run member list neutralised)
    cable_tray_create.rvt       EXPERIMENTAL: two straight cable-tray runs (Ladder
                                12"x4", Channel 6"x3.5") synthesised by class-morphing
                                a conduit specimen (no cable-tray specimen exists in
                                any 2026 sample) — structurally valid, acceptance unproven
    manifest.json               all plans, structural reports, semantic read-backs,
                                validator verdicts

Run from the repo root:
    .venv/bin/python experiments/mep/conduit/make_conduit.py
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import manipulate as M                       # noqa: E402
from rvt.commit import verify_written                 # noqa: E402
from rvt.mep import conduit as C                      # noqa: E402
from rvt.mutate import Document                       # noqa: E402
from rvt.validate import validate_file                # noqa: E402

SRC = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

# rme template constants
LEVEL1 = 378117                 # 'Level 1', elevation 0.309 ft
LEVEL2 = 378118                 # 'Level 2', elevation 12.467 ft
TYPE_RNC80 = 662478             # 'Rigid Nonmetallic Conduit (RNC Sch 80)' (all 20 conduits)
TYPE_RNC80_WITH_FITTINGS = 662475
TYPE_RMC_NOFIT = 662479         # 'Rigid Metal Conduit (RMC)' without fittings
TRAY_LADDER = 643893            # 'Ladder Cable Tray'
TRAY_CHANNEL = 643892           # 'Channel Cable Tray'

MANIFEST: dict = {"template": os.path.basename(SRC), "files": []}


def _validator(path: str) -> dict:
    t0 = time.time()
    rep = validate_file(path, layers=("structure", "consistency", "semantic"))
    return {"ok": bool(rep.ok), "errors": [str(f) for f in rep.errors],
            "n_warnings": len(rep.warnings),
            "warnings": [str(w)[:200] for w in rep.warnings],
            "seconds": round(time.time() - t0, 1)}


def _struct_ok_created(v: dict, ids) -> bool:
    clean = {s: sum(1 for x in v["new_ids_found"][s].values() if x["clean"])
             for s in (101, 102, 103)}
    return (v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
            and v["walker_errors"] == 0 and v["stamps_ok"]
            and all(n == len(ids) for n in clean.values())
            and v["elemtable_count"] == v["header_count"]
            and all(v["sentinel_last"].values()))


def _struct_ok_manip(v: dict) -> bool:
    return (v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
            and v["walker_errors"] == 0 and v["isize_identity_mismatches"] == 0
            and v["stamps_ok"] and all(v["sentinel_last"].values())
            and v["elemtable_count"] == v["header_count"]
            and v["elemtable_ids_sorted"] and v["unit0_ids_equal_elemtable"]
            and not v["deleted_still_present"] and not v["deleted_in_elemtable"]
            and all(all(x["clean"] for x in e.values()) for e in v["edited"].values()))


def _record(name, kind, proves, plan, structural, structural_ok, semantic, validator):
    entry = {"file": name, "kind": kind, "proves": proves, "plan": plan,
             "structural": structural, "STRUCTURALLY_VALID": bool(structural_ok),
             "semantic": semantic, "validator": validator,
             "VALIDATOR_ZERO_ERRORS": bool(validator["ok"])}
    MANIFEST["files"].append(entry)
    sem_ok = all(v for k, v in semantic.items() if k.startswith("ok"))
    tag = "PASS" if (structural_ok and validator["ok"] and sem_ok) else "FAIL"
    print(f"\n[{tag}] {name}: {proves}")
    print(f"       structural={structural_ok} validator_errors={len(validator['errors'])} "
          f"warnings={validator['n_warnings']} semantic_ok={sem_ok}", flush=True)


# ---------------------------------------------------------------------------
# CREATE: a 3-segment run with two 90-degree elbows
# ---------------------------------------------------------------------------
def build_create() -> None:
    name = "conduit_create.rvt"
    out = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    # An overhead run west of the switchgear (existing overhead conduits sit at
    # z ~9.5 near x -33..-63, y 17..22): three legs meeting at two 90° corners.
    path = [(-30.0, 26.0, 9.5), (-22.0, 26.0, 9.5), (-22.0, 32.0, 9.5), (-14.0, 32.0, 9.5)]
    plan = C.add_conduit_path(doc, path, LEVEL1, TYPE_RNC80, size_ft=2.0 / 12.0)
    graph = C.verify_plan_graph(doc, plan)
    rep = C.commit_created(SRC, out, doc, [plan])
    ids = rep["new_element_ids"]
    v = verify_written(out, ids)
    d2 = Document.from_file(out)
    rb = C.readback_run(d2, plan.run.elem_id)
    elbows = [C.fitting_geometry(d2, f.elem_id) for f in plan.fittings]
    sem = {
        "run_id": plan.run.elem_id,
        "member_order": [(m["id"], m["class"]) for m in rb["members"]],
        "curve_lengths_ft": [round(m["length_ft"], 4) for m in rb["members"] if m.get("length_ft")],
        "elbows": [{"id": e["id"], "corner": e["corner"], "clone": e["symbol_clone_id"],
                    "master": e["master_symbol_id"], "connectors": e["connectors"]}
                   for e in elbows],
        "ok_readback_graph": rb["ok"],
        "ok_two_elbows_reuse_clone": all(e["symbol_clone_id"] == 679082 for e in elbows)
                                     and len(elbows) == 2,
        "ok_run_lists_members_in_path_order": [m["id"] for m in rb["members"]] == [
            plan.curves[0].elem_id, plan.fittings[0].elem_id, plan.curves[1].elem_id,
            plan.fittings[1].elem_id, plan.curves[2].elem_id],
        "readback_issues": rb["issues"],
    }
    _record(name, "create",
            "3-segment 2\" RNC Sch-80 conduit run with TWO 90° elbow fittings "
            "(shared geometry-symbol clone 679082 reused; connector graph mutual; "
            "each curve owns a SegmentCenterLine, each elbow a ConduitFittingCenterLine)",
            {"path_ft": path, "plan": plan.to_json(), "notes": plan.notes,
             "plan_graph_check": graph,
             "elemtable": [rep["elemtable_count_before"], rep["elemtable_count_after"]],
             "bytes_added": rep["per_seq_bytes_added"]},
            {k: v[k] for k in ("crc_failures", "ecc_mismatches", "walker_errors",
                               "stamps_ok", "elemtable_count", "header_count",
                               "sentinel_last")}
            | {"new_records_clean_per_seq": {
                str(s): sum(1 for x in v["new_ids_found"][s].values() if x["clean"])
                for s in (101, 102, 103)}, "expected": len(ids)},
            _struct_ok_created(v, ids), sem, _validator(out))


def build_create_straight() -> None:
    name = "conduit_create_straight.rvt"
    out = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    p1 = C.add_conduit_run(doc, (-30.0, 40.0, 9.5), (-14.0, 40.0, 9.5), LEVEL1,
                           TYPE_RNC80, size_ft=2.0 / 12.0)          # horizontal 2"
    p2 = C.add_conduit_run(doc, (-30.0, 44.0, 0.5), (-30.0, 44.0, 10.5), LEVEL1,
                           TYPE_RNC80, size_ft=1.0 / 12.0)          # 1" vertical riser
    p3 = C.add_conduit_run(doc, (-26.0, 46.0, 8.0), (-16.0, 50.0, 10.0), LEVEL1,
                           TYPE_RMC_NOFIT, size_ft=3.0 / 12.0)      # 3" RMC diagonal (sloped)
    plans = [p1, p2, p3]
    graphs = [C.verify_plan_graph(doc, p) for p in plans]
    rep = C.commit_created(SRC, out, doc, plans)
    ids = rep["new_element_ids"]
    v = verify_written(out, ids)
    d2 = Document.from_file(out)
    rbs = [C.readback_run(d2, p.run.elem_id) for p in plans]
    sem = {"runs": [(r["run"], r["ok"], [(m["id"], round(m["length_ft"] or 0, 4),
                                             m.get("size_ft")) for m in r["members"]])
                    for r in rbs],
           "ok_all_readback": all(r["ok"] for r in rbs)}
    _record(name, "create",
            "three disjoint straight conduit runs (horizontal 2\" RNC, vertical 1\" riser, "
            "sloped 3\" RMC) — the fitting-free fallback; each = curve + SegmentCenterLine + run",
            {"plans": [p.to_json() for p in plans], "notes": sum([p.notes for p in plans], []),
             "plan_graph_checks": graphs,
             "elemtable": [rep["elemtable_count_before"], rep["elemtable_count_after"]]},
            {k: v[k] for k in ("crc_failures", "ecc_mismatches", "walker_errors",
                               "stamps_ok", "elemtable_count", "header_count",
                               "sentinel_last")},
            _struct_ok_created(v, ids), sem, _validator(out))


# ---------------------------------------------------------------------------
# MODIFY: resize + move + extend + retype (disjoint elements, one file)
# ---------------------------------------------------------------------------
def build_modify() -> None:
    name = "conduit_modify.rvt"
    out = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    ops = {}
    # RESIZE conduit 686270 (single-conduit run 686345, panel end + open end) 2" -> 1"
    before = C.curve_geometry(doc, 686270)
    plans = C.resize_run(doc, 686270, 1.0 / 12.0)
    ops["resize"] = {"conduit": 686270, "from_in": round(before["diameter_or_width_ft"] * 12, 3),
                     "to_in": 1.0, "n_plans": len(plans)}
    # MOVE run 679175 (3 conduits + 2 elbows + 5 centre-lines, both ends open) by (+4,+3,0)
    dv = (4.0, 3.0, 0.0)
    mv_before = {m: C.curve_geometry(doc, m)["p0"]
                 for m in (679170, 679171, 679172)}
    fit_before = {f: C.fitting_geometry(doc, f)["corner"] for f in (688129, 679174)}
    plans += C.move_run(doc, 679175, dv)
    ops["move"] = {"run": 679175, "delta_ft": dv}
    # EXTEND the open top end of conduit 686514 (p1 at z 24.57) by +3 ft
    ext_before = C.curve_geometry(doc, 686514)
    plans += C.extend_run(doc, 686514, 3.0, end="p1")
    ops["extend"] = {"conduit": 686514, "end": "p1", "delta_ft": 3.0,
                     "length_before_ft": round(ext_before["length_ft"], 4)}
    # RETYPE run 688539 (2 conduits + 1 elbow): RNC Sch80 662478 -> 662475 (same standard)
    plans += C.retype_run(doc, 688539, TYPE_RNC80_WITH_FITTINGS)
    ops["retype"] = {"run": 688539, "from": TYPE_RNC80, "to": TYPE_RNC80_WITH_FITTINGS}
    rep = M.commit_plans(SRC, out, plans)
    edited = sorted({e for p in plans for e in p.edited_ids})
    v = M.verify_manipulated(out, edited_ids=edited)
    d2 = Document.from_file(out)
    g270 = C.curve_geometry(d2, 686270)
    g514 = C.curve_geometry(d2, 686514)
    mv_after = {m: C.curve_geometry(d2, m)["p0"] for m in (679170, 679171, 679172)}
    fit_after = {f: C.fitting_geometry(d2, f)["corner"] for f in (688129, 679174)}
    rb_moved = C.readback_run(d2, 679175)
    rt = C.curve_geometry(d2, 688538)
    run_type = (d2.value(688539) or {}).get("m_typeId")
    def _close(a, b, t=1e-6):
        return all(abs(a[i] - b[i]) < t for i in range(3))
    sem = {
        "resize_after": {"diameter_ft": g270["diameter_or_width_ft"],
                         "size_label": g270["size_label"]},
        "ok_resized": abs(g270["diameter_or_width_ft"] - 1.0 / 12.0) < 1e-9
                      and g270["size_label"] == "25 mmø",
        "move_delta_ft": dv,
        "moved_conduit_p0": {m: (mv_before[m], mv_after[m]) for m in mv_before},
        "moved_elbow_corners": {f: (fit_before[f], fit_after[f]) for f in fit_before},
        "ok_moved_rigidly": all(_close(mv_after[m], [mv_before[m][i] + dv[i] for i in range(3)])
                                for m in mv_before)
                            and all(_close(fit_after[f], [fit_before[f][i] + dv[i] for i in range(3)])
                                    for f in fit_before),
        "ok_moved_graph_still_mutual": rb_moved["ok"],
        "extend_after": {"length_ft": round(g514["length_ft"], 4), "p1": g514["p1"]},
        "ok_extended": abs(g514["length_ft"] - (ext_before["length_ft"] + 3.0)) < 1e-6,
        "retype_after": {"conduit_688538_type": rt["type_id"], "run_688539_type": run_type},
        "ok_retyped": rt["type_id"] == TYPE_RNC80_WITH_FITTINGS
                      and run_type == TYPE_RNC80_WITH_FITTINGS,
    }
    _record(name, "modify",
            "RESIZE 686270 2\"->1\" (diameter + inner/outer + size label), MOVE run "
            "679175 by (4,3,0) ft rigidly (curves, both elbows, all centre-lines), "
            "EXTEND 686514's open end +3 ft, RETYPE run 688539 -> type 662475",
            {"ops": ops, "n_plans": len(plans), "edited_ids": edited,
             "elemtable": [rep.elemtable_count_before, rep.elemtable_count_after]},
            {k: v[k] for k in ("crc_failures", "ecc_mismatches", "walker_errors",
                               "isize_identity_mismatches", "stamps_ok",
                               "elemtable_count", "header_count", "sentinel_last",
                               "elemtable_ids_sorted", "unit0_ids_equal_elemtable")},
            _struct_ok_manip(v), sem, _validator(out))


# ---------------------------------------------------------------------------
# DELETE: a whole run and, separately, one fitting
# ---------------------------------------------------------------------------
def build_delete() -> None:
    name = "conduit_delete.rvt"
    out = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    # (a) delete run 679090 (conduits 687998, 679071, 678659 + elbows 688027,
    #     688029 + 5 centre-lines + the run); conduit 678659 taps the
    #     transformer 624416 (surface connector 2001) -> that reference is
    #     neutralised on the transformer.
    xfmr_before = json.dumps(doc.value(624416).get("m_pConnectorManager"), default=str)
    plans = C.delete_run(doc, 679090)
    # (b) delete elbow 688548 out of run 688539 (conduits 688538 / 688547 keep
    #     the run; their connector refs and the run's member list are neutralised)
    plans += C.delete_fitting(doc, 688548)
    removed = sorted({i for p in plans for i in p.ids_to_remove})
    edited = sorted({e for p in plans for e in p.edited_ids} - set(removed))
    rep = M.commit_plans(SRC, out, plans)
    v = M.verify_manipulated(out, deleted_ids=removed, edited_ids=edited)
    d2 = Document.from_file(out)
    gone = {i: (i not in d2.idx[102] and i not in d2.et_by_id) for i in removed}
    xfmr_after = json.dumps(d2.value(624416).get("m_pConnectorManager"), default=str)
    run_539 = d2.value(688539) or {}
    c538 = C.curve_geometry(d2, 688538)
    still_mentions = any(str(x) in json.dumps(d2.value(624416), default=str) for x in (678659,))
    sem = {
        "removed_ids": removed,
        "referrers_edited": edited,
        "ok_all_removed": all(gone.values()),
        "ok_transformer_no_longer_refs_678659": ("678659" in xfmr_before) and not still_mentions,
        "ok_run688539_dropped_elbow": 688548 not in (run_539.get("m_elemIdArr") or []),
        "run_688539_members_after": run_539.get("m_elemIdArr"),
        "ok_conduit_688538_conn_no_longer_refs_elbow": all(
            r.get("m_id") != 688548 for c in c538["connectors"] for r in c["refs"]),
        "ok_referrers_decode_clean": all(
            (d2.decode(r, 102) is None) or d2.decode(r, 102).clean or d2.decode(r, 102).stub
            for r in edited if d2.in_host_document(r)),
        "elemtable_count": [rep.elemtable_count_before, rep.elemtable_count_after],
    }
    _record(name, "delete",
            "DELETE run 679090 (3 conduits + 2 elbows + 5 centre-lines + run; the "
            "transformer's surface-connector reference neutralised) and DELETE elbow "
            "688548 (fitting + its centre-line; conduits' connector refs and run member "
            "list neutralised)",
            {"delete_run_679090_closure": C.run_closure(doc, 679090),
             "removed": removed, "n_plans": len(plans),
             "elemtable": [rep.elemtable_count_before, rep.elemtable_count_after]},
            {k: v[k] for k in ("crc_failures", "ecc_mismatches", "walker_errors",
                               "isize_identity_mismatches", "stamps_ok",
                               "elemtable_count", "header_count", "sentinel_last",
                               "deleted_still_present", "deleted_in_elemtable",
                               "elemtable_ids_sorted", "unit0_ids_equal_elemtable")},
            _struct_ok_manip(v), sem, _validator(out))


# ---------------------------------------------------------------------------
# CABLE TRAY (experimental synthesis)
# ---------------------------------------------------------------------------
def build_cable_tray() -> None:
    name = "cable_tray_create.rvt"
    out = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    # two straight trays overhead at Level 1 + 10.5 ft, near the corridor
    p1 = C.add_cable_tray_run(doc, (-30.0, 60.0, 10.5), (-10.0, 60.0, 10.5), LEVEL1,
                              tray_type_id=TRAY_LADDER, width_ft=1.0, height_ft=4.0 / 12.0)
    p2 = C.add_cable_tray_run(doc, (-30.0, 64.0, 10.5), (-16.0, 64.0, 10.5), LEVEL1,
                              tray_type_id=TRAY_CHANNEL, width_ft=0.5, height_ft=3.5 / 12.0)
    plans = [p1, p2]
    graphs = [C.verify_plan_graph(doc, p) for p in plans]
    rep = C.commit_created(SRC, out, doc, plans)
    ids = rep["new_element_ids"]
    v = verify_written(out, ids)
    d2 = Document.from_file(out)
    rbs = [C.readback_run(d2, p.run.elem_id) for p in plans]
    trays = [C.curve_geometry(d2, p.curves[0].elem_id) for p in plans]
    sem = {"runs": [(r["run"], r["class"], r["ok"]) for r in rbs],
           "trays": [{"id": t["id"], "class": t["class"], "width_ft": t["diameter_or_width_ft"],
                      "height_ft": t["height_ft"], "length_ft": round(t["length_ft"], 4),
                      "type_id": t["type_id"], "size_label": t["size_label"]} for t in trays],
           "ok_all_readback": all(r["ok"] for r in rbs),
           "ok_class_is_CableTray": all(t["class"] == "CableTray" for t in trays)}
    _record(name, "create-experimental",
            "EXPERIMENTAL: two straight cable-tray runs (Ladder 12\"x4\", Channel 6\"x3.5\") "
            "class-morphed from a conduit specimen (CableTray/CableTrayRun have NO specimen "
            "in any 2026 sample); category ids of the run/centre-line are INFERRED",
            {"plans": [p.to_json() for p in plans], "notes": sum([p.notes for p in plans], []),
             "plan_graph_checks": graphs,
             "elemtable": [rep["elemtable_count_before"], rep["elemtable_count_after"]]},
            {k: v[k] for k in ("crc_failures", "ecc_mismatches", "walker_errors",
                               "stamps_ok", "elemtable_count", "header_count",
                               "sentinel_last")},
            _struct_ok_created(v, ids), sem, _validator(out))


def main() -> int:
    t0 = time.time()
    print(f"source: {os.path.relpath(SRC, ROOT)}")
    build_create()
    build_create_straight()
    build_modify()
    build_delete()
    build_cable_tray()
    MANIFEST["seconds"] = round(time.time() - t0, 1)
    mpath = os.path.join(HERE, "manifest.json")
    with open(mpath, "w") as fh:
        json.dump(MANIFEST, fh, indent=1, default=str)
    print(f"\nwrote {os.path.relpath(mpath, ROOT)} in {MANIFEST['seconds']} s")
    allok = all(e["STRUCTURALLY_VALID"] and e["VALIDATOR_ZERO_ERRORS"] for e in MANIFEST["files"])
    print("ALL FILES STRUCTURALLY VALID + VALIDATOR CLEAN:", allok)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
