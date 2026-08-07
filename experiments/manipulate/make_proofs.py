"""make_proofs.py -- prove the manipulation API on two real projects.

Runs the four operations of ``rvt.manipulate`` against
``samples/rmebasicsampleproject.rvt`` (the MEP file the tools grew up on)
AND ``samples/racadvancedsampleproject.rvt`` (an architectural file the
tools were NOT developed against), writes each result through the real
writer, and proves each output with

  * ``verify_manipulated`` -- CRC of every gzip member, per-page ECC of the
    re-emitted streams, framing-walker errors, block ISIZE identity,
    partition-header count == ElemTable count, sentinels last, adler32
    record stamps, deleted ids gone (unit 0 + ElemTable), edited records
    decoding cleanly, unit-0 seq-102 ids == ElemTable ids;
  * a semantic RE-READ: ``Document.from_file(out)`` and an assertion that
    the change took (element gone / value changed / position changed).

Outputs (experiments/manipulate/):
    M1_delete.rvt          M1_delete_rac.rvt
    M2_delete_cascade.rvt  M2_delete_cascade_rac.rvt
    M3_modify.rvt          M3_modify_rac.rvt
    M4_move_retype.rvt     M4_move_retype_rac.rvt
    proofs.json            (machine-readable proof record)
    README.md              (per-file note of what it proves)

Usage:  .venv/bin/python experiments/manipulate/make_proofs.py
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import manipulate as M                      # noqa: E402
from rvt.mutate import Document                       # noqa: E402

RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
RAC = os.path.join(ROOT, "samples", "racadvancedsampleproject.rvt")

PROOFS: dict = {"files": []}


def _healthy(v: dict) -> bool:
    return (v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
            and v["walker_errors"] == 0 and v["isize_identity_mismatches"] == 0
            and v["stamps_ok"] and all(v["sentinel_last"].values())
            and v["elemtable_count"] == v["header_count"]
            and v["elemtable_ids_sorted"] and v["unit0_ids_equal_elemtable"]
            and not v["deleted_still_present"] and not v["deleted_in_elemtable"]
            and all(all(x["clean"] for x in e.values())
                    for e in v["edited"].values()))


def record(name: str, src: str, what: str, extra: dict, verify: dict,
           semantic: dict) -> None:
    entry = {"file": name, "source": os.path.basename(src), "proves": what,
             "plan": extra, "structural": verify,
             "structural_healthy": _healthy(verify), "semantic": semantic}
    PROOFS["files"].append(entry)
    ok = entry["structural_healthy"] and all(
        v for k, v in semantic.items() if k.startswith("ok"))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {what}", flush=True)


# ---------------------------------------------------------------------------
def m1_delete(src: str, out: str, eid: int, label: str) -> None:
    doc = Document.from_file(src)
    plan = M.delete_element(doc, eid)                    # no cascade needed
    rep = M.commit_plans(src, out, [plan])
    v = M.verify_manipulated(out, deleted_ids=plan.ids_to_remove,
                             edited_ids=plan.edited_ids)
    d2 = Document.from_file(out)
    sem = {"deleted_id": eid, "class": doc.class_of(eid),
           "category": doc.category_of(eid),
           "ok_gone_from_unit0": eid not in d2.idx[102],
           "ok_gone_from_elemtable": eid not in d2.et_by_id,
           "elemtable_count": [rep.elemtable_count_before, rep.elemtable_count_after],
           "watermark_kept": rep.watermark == d2.et.footer.last_id if d2.et.footer else None}
    record(os.path.basename(out), src,
           f"DELETE a family instance with no dependents ({label} {eid})",
           plan.to_json(), v, sem)


def m2_cascade(src: str, out: str, eid: int, label: str) -> None:
    doc = Document.from_file(src)
    err_report = None
    try:
        M.delete_element(doc, eid)                      # must fail loudly
    except M.DependentsError as e:
        err_report = {"message": str(e),
                      "dependents": [(x["id"], x["class"], x["relation"], x["depth"])
                                     for x in e.report["dependents"]]}
    plan = M.delete_element(doc, eid, cascade=True)
    rep = M.commit_plans(src, out, [plan])
    v = M.verify_manipulated(out, deleted_ids=plan.ids_to_remove,
                             edited_ids=plan.edited_ids)
    d2 = Document.from_file(out)
    ref_clean = {str(r["id"]): bool((d2.decode(r["id"], 102) or None) and
                                     (d2.decode(r["id"], 102).clean or
                                      d2.decode(r["id"], 102).stub))
                 for r in plan.referrer_edits}
    sem = {"target": eid, "class": doc.class_of(eid),
           "fail_loud_without_cascade": err_report is not None,
           "dependents_report": (err_report or {}).get("dependents"),
           "cascade_ids": plan.ids_to_remove,
           "referrers_neutralised": [(r["id"], r["class"]) for r in plan.referrer_edits],
           "ok_all_removed": all(i not in d2.idx[102] and i not in d2.et_by_id
                                 for i in plan.ids_to_remove),
           "ok_referrers_decode_clean": all(ref_clean.values()),
           "elemtable_count": [rep.elemtable_count_before, rep.elemtable_count_after]}
    record(os.path.basename(out), src,
           f"DELETE an element WITH dependents ({label} {eid}): "
           f"DependentsError report + cascade run", plan.to_json(), v, sem)


def m3_modify(src: str, out: str, level_id: int, delta_ft: float,
              text_edits: list, label: str) -> None:
    doc = Document.from_file(src)
    e0 = doc._level_elevation(level_id)
    M.set_level_elevation(doc, level_id, e0 + delta_ft)
    applied = []
    for kind, teid, param, value in text_edits:
        if kind == "panel":
            M.rename_panel(doc, teid, value)
        else:
            M.set_param(doc, teid, param, value)
        applied.append((kind, teid, param, value))
    rep = M.commit_session(doc, out)
    edited = sorted({level_id} | {t[1] for t in text_edits})
    v = M.verify_manipulated(out, edited_ids=edited)
    d2 = Document.from_file(out)
    checks = {}
    for kind, teid, param, value in applied:
        val = d2.value(teid) or {}
        hits = M.find_param(val, param)
        got = M.get_path(val, f"{hits[0][0]}[{hits[0][1]}].m_value") if hits else None
        checks[f"{teid}:{param}"] = {"expected": value, "reread": got}
    sem = {"level": level_id, "elevation_before": e0,
           "elevation_after_reread": d2._level_elevation(level_id),
           "ok_elevation": abs(d2._level_elevation(level_id) - (e0 + delta_ft)) < 1e-9,
           "text_params": checks,
           "ok_text": all(c["expected"] == c["reread"] for c in checks.values())}
    record(os.path.basename(out), src,
           f"MODIFY parameters: level {level_id} elevation {delta_ft:+} ft + "
           f"{len(text_edits)} text/mark edit(s) ({label})", rep.to_json(), v, sem)


def m4_move_retype(src: str, out: str, eid: int, new_symbol: int,
                   label: str) -> None:
    doc = Document.from_file(src)
    before = M.instance_placement(doc, eid)
    p_move = M.move_instance(doc, eid, (5.0, 0.0, 0.0), delta=True)
    p_ret = M.retype_instance(doc, eid, new_symbol)
    rep = M.commit_session(doc, out)
    v = M.verify_manipulated(out, edited_ids=[eid])
    d2 = Document.from_file(out)
    after = M.instance_placement(d2, eid)
    dv = [after["m_or"][i] - before["m_or"][i] for i in range(3)]
    sem = {"instance": eid, "before": before, "after": after,
           "translation": dv,
           "ok_moved_5ft_x": abs(dv[0] - 5.0) < 1e-9 and abs(dv[1]) < 1e-9 and abs(dv[2]) < 1e-9,
           "ok_retyped": after["m_symbolId"] == new_symbol == after["m_masterSymbolId"],
           "notes": p_move.notes + p_ret.notes}
    record(os.path.basename(out), src,
           f"MOVE a placed instance 5 ft +X and RETYPE it (symbol "
           f"{before['m_symbolId']} -> {new_symbol}) ({label})",
           {"move": p_move.to_json(), "retype": p_ret.to_json(), "commit": rep.to_json()},
           v, sem)


# ---------------------------------------------------------------------------
def main() -> int:
    t0 = time.time()
    os.makedirs(HERE, exist_ok=True)
    P = lambda n: os.path.join(HERE, n)   # noqa: E731

    # ---- rmebasicsampleproject (MEP) --------------------------------------
    m1_delete(RME, P("M1_delete.rvt"), 430715,
              "unconnected air terminal, host document, no dependents/referrers")
    m2_cascade(RME, P("M2_delete_cascade.rvt"), 573703,
               "SWall hosting 2 SketchPlanes + 10 face-hosted fixtures; pipes/systems referrers")
    m3_modify(RME, P("M3_modify.rvt"), 378118, +2.0,
              [("panel", 581483, M.BIP_RBS_ELEC_PANEL_NAME, "PP-1B-RENAMED"),
               ("mark", 581483, M.BIP_ALL_MODEL_MARK, "15-EDITED")],
              "Level 2 +2 ft; panelboard PP-1B renamed + Mark edited")
    m4_move_retype(RME, P("M4_move_retype.rvt"), 624416, 621232,
                   "free-standing 500 kVA transformer -> 75 kVA sibling type")

    # ---- racadvancedsampleproject (architectural, NOT a development file)
    m1_delete(RAC, P("M1_delete_rac.rvt"), 201309,
              "isolated structural framing instance (W-Wide Flange)")
    m2_cascade(RAC, P("M2_delete_cascade_rac.rvt"), 144180,
               "SWall hosting door 145999 (+ its tag, a dimension, the wall's tag)")
    m3_modify(RAC, P("M3_modify_rac.rvt"), 136342, +1.0,
              [("mark", 147834, M.BIP_ALL_MODEL_MARK, "130A-EDITED")],
              "Level '03 - Floor' +1 ft; door 147834 Mark edited")
    m4_move_retype(RAC, P("M4_move_retype_rac.rvt"), 180360, 180237,
                   "dining table (with 4 owned chairs moved rigidly) -> 1525mm type")

    PROOFS["elapsed_s"] = round(time.time() - t0, 1)
    with open(os.path.join(HERE, "proofs.json"), "w") as f:
        json.dump(PROOFS, f, indent=1, default=str)
    fails = [f["file"] for f in PROOFS["files"]
             if not (f["structural_healthy"]
                     and all(v for k, v in f["semantic"].items() if k.startswith("ok")))]
    print(json.dumps({"outputs": [f["file"] for f in PROOFS["files"]],
                      "all_pass": not fails, "failures": fails,
                      "elapsed_s": PROOFS["elapsed_s"]}, indent=1))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
