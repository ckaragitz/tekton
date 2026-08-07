#!/usr/bin/env python
"""build_g12_probes.py -- GENESIS-12 probe builder (tasks 2 + 3).

TASK 2 -- THE WALLS+FAMILIES BUG, the two proof probes.

  Mechanism (named from the bytes; docs/inbox/genesis-12.md):
  ``rvt.famgen.loader`` authors the host family layer with TWO owned-pointer
  slots NULLED that Autodesk's serializer NEVER nulls --
  ``Family.m_oFamDimConstrMgr`` (present 831/831 corpus host Families) and
  ``FamilySymbol.m_pMoveRestrictions`` (present 2710/2710 corpus symbols) --
  the only CRITICAL rvt.objlint violations separating every audit-FAILED
  loaded-family file (stage_W, F_lp4, F_msb, R_inst_box/panel,
  electrical_room_2500a: all famgen.loader) from every audit-PASSED one
  (L1a, L_v2, L_downlight: all rvt.famload, which writes the lawful empty
  forms).  Revit's open-time document audit (-1073742517
  Revit-DocumentCorruption -- the K1-autopsy check that already rejected
  null/neutralised owned state no Autodesk file exhibits) walks the family
  layer only when the design is NON-empty: a symbol-only file short-circuits
  at 'Design is empty' (stage_L8_lp4's non-test), walls alone carry no
  family layer (walls_only PASS), walls + a loaded family forces the walk
  and FAILS.

  The probes (both from the CERTIFIED walls-only base, one build pipeline):
    WF_nofix.rvt = walls_only + ONE loaded family (the bare box,
                   rvt.famgen.loader place=False) -- carries the two nulls.
    WF_fix.rvt   = the SAME file with ONLY the two records repaired in
                   place (rvt.genesis.residue_c.fix_family_layer_records ->
                   regadd.substitute_elements seqs=(102,)): the lawful
                   empty FamDimConstrMgrImpl / Matrix forms supplied.
  The pair differs in EXACTLY two seq-102 records (asserted byte-for-byte).
  Viewer reading: WF_nofix FAIL (reproduces the bug on the certified base)
  + WF_fix PASS (the two fields were the mechanism) = proof.  WF_fix FAIL
  too = the mechanism is deeper than the null pair (the next diff dimension
  is pre-staged in the record).

TASK 3 -- WALL RENDER on the composed genesis base:
    W1_gabpd_wall_solid.rvt = certified G_ABPD + ONE created wall
    (rvt.mutate.add_wall, R5 specimen clone, mode 'min') whose seq-103 rep
    is the AUTHORED GElement B-rep solid (rvt.render.brep.wall_rep_from_
    object -- the exact RSOLID_walls_A_solid mechanism, certified PASS +
    RENDERS), applied as a WRAPPER (post-commit in-place substitution;
    rvt/mutate.py untouched -- the create-time diff is in the record).

Reproduce (repo root)::

    .venv/bin/python experiments/render/g12/build_g12_probes.py            # both tasks
    .venv/bin/python experiments/render/g12/build_g12_probes.py --only fix # task 2
    .venv/bin/python experiments/render/g12/build_g12_probes.py --only wall# task 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

WALLS_ONLY = os.path.join(ROOT, "experiments", "ifc_room",
                          "electrical_room_2500a_walls_only.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
R5 = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")
OUT_DIR = HERE

FINISH_MATERIAL = 600660        # 'GEN Concrete, Cast-in-Place' (ours, in the lineage)
WALL_LINE_FT = ((4.0, -12.0), (24.0, -12.0))   # 20 ft, clear of the room ring
WALL_HEIGHT_FT = 12.0


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log(m: str) -> None:
    print(m, flush=True)


def _write(path: str, obj: Any) -> None:
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def ledger_cert(path: str) -> Optional[dict]:
    from rvt.genesis.residue_c import ledger_certification
    return ledger_certification(path)


# ===========================================================================
# task 2 -- the walls+families fix probes
# ===========================================================================

def build_fix_probes() -> dict:
    from rvt.mutate import Document
    from rvt.regadd import substitute_elements, stream_diff_report
    from rvt.famgen import loader as L
    from rvt.genesis.residue_c import (famdim_constr_empty, fix_family_layer_records,
                                       move_restrictions_empty)
    import render_probes as RP

    t0 = time.time()
    rec: Dict[str, Any] = {"task": "walls+families fix probes",
                           "base": {"file": _relp(WALLS_ONLY),
                                    "certification": ledger_cert(WALLS_ONLY)}}
    base_doc = Document.from_file(WALLS_ONLY)
    wm = max(int(e) for e in base_doc.et_by_id)
    log(f"[fix] base {os.path.basename(WALLS_ONLY)} watermark {wm}")

    # ---- WF_nofix: the bug reproduced on the certified base ---------------
    prod = RP.make_bare_box_product(start_id=wm + 1)
    nofix = os.path.join(OUT_DIR, "WF_nofix.rvt")
    res = L.load_family_into_project(WALLS_ONLY, nofix, product=prod, place=False,
                                     symbol_solid=True, validate=False,
                                     report_path=nofix + ".load.json")
    if not res.ok:
        raise RuntimeError(f"WF_nofix load failed: {res.stop_reason}")
    plan = res.plan
    fam_id, sym_ids = int(plan.host_family_id), [int(plan.symbol_id)]
    rec["family"] = {"name": prod.name, "loader":
                     "rvt.famgen.loader.load_family_into_project(place=False, symbol_solid=True)",
                     "host_family_id": fam_id, "symbol_ids": sym_ids,
                     "content_guid": plan.guid}
    d1 = Document.from_file(nofix)
    defect = {
        "family_m_oFamDimConstrMgr_null": d1.value(fam_id).get("m_oFamDimConstrMgr") is None,
        "symbol_m_pMoveRestrictions_null": all(
            d1.value(s).get("m_pMoveRestrictions") is None for s in sym_ids),
    }
    rec["defect_present_in_nofix"] = defect
    if not all(defect.values()):
        raise RuntimeError(f"WF_nofix does not carry the named defect: {defect}")

    # ---- WF_fix: ONLY the two records repaired in place -------------------
    fix = os.path.join(OUT_DIR, "WF_fix.rvt")
    fixes = fix_family_layer_records(d1, family_ids=[fam_id], symbol_ids=sym_ids)
    if sorted(fixes) != sorted([fam_id] + sym_ids):
        raise RuntimeError(f"fix records unexpected: {sorted(fixes)}")
    srep = substitute_elements(nofix, fix, fixes, seqs=(102,), keep_row=True,
                               verify=True, diff=True)
    rec["fix_substitution"] = {"verdict": srep.verdict, "problems": srep.problems,
                               "records": sorted(fixes),
                               "empty_forms": {"m_oFamDimConstrMgr": famdim_constr_empty(),
                                               "m_pMoveRestrictions": move_restrictions_empty()}}

    # ---- the pair's delta is EXACTLY the two records ----------------------
    diff = stream_diff_report(nofix, fix)
    ch = diff["records"]
    delta_ok = (sorted(ch["changed_ids"]) == sorted([fam_id] + sym_ids)
                and not ch["added_ids"] and not ch["removed_ids"]
                and ch["changed_count"] == len(fixes)
                and diff["elemtable"]["identical"]
                and diff["latest"]["identical"]
                and diff["embedded_units_identical"])
    rec["pair_delta"] = {
        "changed_ids": ch["changed_ids"], "changed_count": ch["changed_count"],
        "added": ch["added_ids"], "removed": ch["removed_ids"],
        "elemtable_identical": diff["elemtable"]["identical"],
        "latest_identical": diff["latest"]["identical"],
        "embedded_units_identical": diff["embedded_units_identical"],
        "assertion_exactly_the_two_records": delta_ok,
    }
    if not delta_ok:
        raise RuntimeError(f"WF pair delta is not exactly the fix records: {rec['pair_delta']}")

    # ---- the defect is gone in WF_fix ------------------------------------
    d2 = Document.from_file(fix)
    rec["defect_absent_in_fix"] = {
        "family_m_oFamDimConstrMgr_present": d2.value(fam_id).get("m_oFamDimConstrMgr") is not None,
        "symbol_m_pMoveRestrictions_present": all(
            d2.value(s).get("m_pMoveRestrictions") is not None for s in sym_ids),
    }

    # ---- objlint A/B (the mined-corpus statement of the mechanism) --------
    try:
        from rvt import objlint as OL
        ab = {}
        for label, doc in (("WF_nofix", d1), ("WF_fix", d2)):
            crit = []
            for e in [fam_id] + sym_ids:
                for f in OL.lint_object(doc.class_of(e), doc.value(e), doc.value(e, seq=101)):
                    fd = f.__dict__ if hasattr(f, "__dict__") else dict(f)
                    if str(fd.get("severity")).upper() == "CRITICAL":
                        crit.append({"element": e, "field": fd.get("field_path"),
                                     "rule": fd.get("rule"),
                                     "support": fd.get("support")})
            ab[label] = crit
        rec["objlint_critical_findings"] = ab
        rec["objlint_mechanism_confirmed"] = bool(ab["WF_nofix"]) and not ab["WF_fix"]
    except Exception as ex:                                     # pragma: no cover
        rec["objlint_critical_findings"] = {"error": repr(ex)[:200]}

    # ---- validator on both ------------------------------------------------
    from rvt.validate import validate_file
    for name, path in (("WF_nofix", nofix), ("WF_fix", fix)):
        r = validate_file(path)
        rec[f"validator_{name}"] = {"errors": len(r.errors), "warnings": len(r.warnings)}
        if r.errors:
            raise RuntimeError(f"{name} validator errors: {r.errors[:3]}")
    rec["files"] = {"WF_nofix": {"file": _relp(nofix), "md5": md5_of(nofix)},
                    "WF_fix": {"file": _relp(fix), "md5": md5_of(fix)}}
    rec["seconds"] = round(time.time() - t0, 1)
    log(f"[fix] WF_nofix + WF_fix built; pair delta = exactly {len(fixes)} records; "
        f"validators clean ({rec['seconds']}s)")
    return rec


# ===========================================================================
# task 3 -- G_ABPD + one wall with the baked B-rep solid
# ===========================================================================

def build_wall_probe() -> dict:
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements, verify_written
    from rvt.regadd import substitute_elements
    from rvt.render.brep import CLASS_GELEMENT, wall_rep_from_object
    from rvt.render import inspect as RI
    import ifc_intent as T
    from rvt.validate import validate_file

    t0 = time.time()
    rec: Dict[str, Any] = {"task": "G_ABPD + one created wall with baked solid",
                           "base": {"file": _relp(G_ABPD),
                                    "certification": ledger_cert(G_ABPD)}}
    specimens = T.SpecimenSet(R5)
    doc = Document.from_file(G_ABPD)
    rec["specimens"] = specimens.inject_into(doc)
    wt = T._wall_type_of_base(doc)
    lvl = T._pick_level(doc, 0.0)
    rec["wall_type"] = wt
    rec["level"] = lvl
    if specimens.wall_id is None or wt is None:
        raise RuntimeError("no wall specimen / wall type available")

    p0, p1 = WALL_LINE_FT
    el = doc.add_wall(lvl, wt, p0, p1, height=WALL_HEIGHT_FT,
                      template_id=specimens.wall_id)
    clean = T._clean_wall_clone(el, doc, specimens.wall_id, mode="min")
    dangling = doc.check_references(el)
    rec["wall"] = {"elem_id": el.elem_id, "p0_ft": list(p0), "p1_ft": list(p1),
                   "height_ft": WALL_HEIGHT_FT, "clone_cleanup": clean,
                   "n_dangling": len(dangling),
                   "dangling_refs": dangling[:12]}

    tmp = os.path.join(OUT_DIR, "_gabpd_wall_dummy.tmp.rvt")
    recs = doc.serialize(el)
    if recs is None:
        raise RuntimeError("rvt.encode unavailable")
    crep = commit_new_elements(G_ABPD, tmp, [dict(recs)], [el.elemrec])
    ver = verify_written(tmp, [el.elem_id])
    rec["commit"] = {"elemtable_after": crep.elemtable_count_after,
                     "watermark_after": crep.watermark_after,
                     "verify_ok": bool(getattr(ver, "ok", ver))}

    # ---- the WRAPPER: bake the seq-103 GElement solid in place -----------
    d2 = Document.from_file(tmp)
    obj = d2.value(el.elem_id, 102)
    rep, geom, tags = wall_rep_from_object(
        obj, element_id=el.elem_id,
        root_category_id=-1,               # the RSOLID-certified root-category form
        side_material_id=FINISH_MATERIAL, end_material_id=-1,
        with_ref_planes=False)
    out = os.path.join(OUT_DIR, "W1_gabpd_wall_solid.rvt")
    srep = substitute_elements(tmp, out, {el.elem_id: {103: (CLASS_GELEMENT, rep)}},
                               seqs=(103,), keep_row=True, verify=True, diff=True)
    os.remove(tmp)
    rec["bake"] = {"verdict": srep.verdict, "problems": srep.problems,
                   "record_len_delta": srep.record_len_delta,
                   "mechanism": ("rvt.render.brep.wall_rep_from_object -> "
                                 "regadd.substitute_elements(seqs=(103,)) -- the "
                                 "RSOLID_walls_A_solid mechanism (certified PASS + "
                                 "RENDERS) applied as a post-commit wrapper; "
                                 "rvt/mutate.py untouched"),
                   "geometry": {"length_ft": round(geom.length, 4),
                                "thickness_ft": round(geom.thickness, 4),
                                "height_ft": round(geom.height, 4)}}

    # ---- read-back --------------------------------------------------------
    d3 = Document.from_file(out)
    ins = RI.inspect_element(d3, el.elem_id)
    rec["readback"] = ins.to_json() if hasattr(ins, "to_json") else str(ins)
    r = validate_file(out)
    rec["validator"] = {"errors": len(r.errors), "warnings": len(r.warnings)}
    if r.errors:
        raise RuntimeError(f"W1 validator errors: {r.errors[:3]}")
    if not getattr(ins, "has_baked_geometry", False):
        raise RuntimeError("W1 wall read-back is not baked")
    rec["file"] = {"file": _relp(out), "md5": md5_of(out)}
    rec["seconds"] = round(time.time() - t0, 1)
    log(f"[wall] W1_gabpd_wall_solid: wall {el.elem_id} baked "
        f"({getattr(ins, 'geometry_bytes', '?')} B GElement), validator 0 errors "
        f"({rec['seconds']}s)")
    return rec


# ===========================================================================
# the batch manifest + control
# ===========================================================================

def write_manifest(fix_rec: Optional[dict], wall_rec: Optional[dict]) -> str:
    ctrl = os.path.join(OUT_DIR, "CTRL_walls_only_g12.rvt")
    if not os.path.exists(ctrl):
        shutil.copyfile(WALLS_ONLY, ctrl)
    probes: List[dict] = []
    if fix_rec:
        base = fix_rec["base"]
        probes.append({
            "order": 1, "rung": "WF_nofix",
            "file": fix_rec["files"]["WF_nofix"]["file"],
            "base": base, "derived_from": base["file"], "kind": "probe",
            "the_ONE_thing_it_tests": (
                "the walls+families bug REPRODUCES on the certified walls-only base: "
                "one famgen.loader family (bare box, no connector) + the certified "
                "walls => expect the audit FAIL (-1073742517)"),
            "if_FAIL": "expected -- the bug is reproduced with a one-family minimal delta",
            "if_PASS": ("the bug does NOT reproduce with the box family: the defect is "
                        "family-content- or order-dependent -- diff vs F_lp4's panel next"),
            "md5": fix_rec["files"]["WF_nofix"]["md5"],
        })
        probes.append({
            "order": 2, "rung": "WF_fix",
            "file": fix_rec["files"]["WF_fix"]["file"],
            "base": base, "derived_from": base["file"], "kind": "probe",
            "the_ONE_thing_it_tests": (
                "THE MECHANISM: byte-identical to WF_nofix except the TWO seq-102 "
                "records where the null Family.m_oFamDimConstrMgr / "
                "FamilySymbol.m_pMoveRestrictions are replaced by the corpus-lawful "
                "empty forms (present 831/831 and 2710/2710 specimens; the only "
                "CRITICAL objlint deltas between every audit-failed and every "
                "audit-passed loaded-family file)"),
            "if_PASS": ("with WF_nofix FAIL: the mechanism is PROVEN -- the famgen."
                        "loader null-field pair is the walls+families bug; route the "
                        "two-line fix to the famgen owner"),
            "if_FAIL": ("the null pair is not (all of) the mechanism: the next diff "
                        "dimensions are pre-staged in docs/inbox/genesis-12.md "
                        "(FamilyTypeTable pairs, ConnectorDataCell shape, "
                        "surrogate order)"),
            "md5": fix_rec["files"]["WF_fix"]["md5"],
        })
    if wall_rec:
        probes.append({
            "order": 3, "rung": "W1_gabpd_wall_solid",
            "file": wall_rec["file"]["file"],
            "base": wall_rec["base"], "derived_from": wall_rec["base"]["file"],
            "kind": "probe",
            "the_ONE_thing_it_tests": (
                "CREATION RENDERS ON THE COMPOSED GENESIS BASE: one created wall "
                "carrying the authored seq-103 GElement six-face solid (the "
                "RSOLID-certified grammar, root category -1) on G_ABPD itself"),
            "if_PASS": ("read the model tree: a wall node under 'GEN L1' + a visible "
                        "shaded wall = LOAD+RENDER proven on the genesis base proper"),
            "if_FAIL": ("walls-only lineage renders but G_ABPD does not: the delta is "
                        "the composed base's residue layers -- bisect against "
                        "RSOLID_walls_A_solid (same wall grammar, walls-only base)"),
            "md5": wall_rec["file"]["md5"],
        })
    man = {
        "stream": "genesis-12 (g12): walls+families mechanism proof + wall render on G_ABPD",
        "mechanism_statement": (
            "rvt.famgen.loader nulls Family.m_oFamDimConstrMgr and FamilySymbol."
            "m_pMoveRestrictions -- forms present in 831/831 and 2710/2710 corpus "
            "specimens and in every audit-PASSED loaded-family file (rvt.famload's "
            "output); Revit's open-time corruption audit walks the family layer only "
            "when the design is non-empty, so symbol-only files short-circuit "
            "('Design is empty') while walls+family / instance+family files FAIL "
            "(-1073742517). WF_fix vs WF_nofix isolates exactly those two records."),
        "standing_control": {
            "file": _relp(ctrl), "copied_from": _relp(WALLS_ONLY), "md5": md5_of(ctrl),
            "note": "byte-identical to the certified walls-only base; read FIRST",
            "certification": ledger_cert(WALLS_ONLY)},
        "upload_order_bisection_first": [p["rung"] for p in probes],
        "reading_the_matrix": {
            "CTRL FAIL": "round VOID",
            "WF_nofix FAIL + WF_fix PASS": "mechanism PROVEN (the two null fields)",
            "WF_nofix FAIL + WF_fix FAIL": ("null pair insufficient -- escalate to the "
                                            "pre-staged next diffs in the record"),
            "WF_nofix PASS": ("bug does not reproduce with the box family on walls_only "
                              "-- the defect is content/order-dependent; rebuild the "
                              "pair with the LP-4 panel product"),
            "W1 PASS + renders": "creation visible on the composed genesis base",
        },
        "probes": probes,
    }
    p = os.path.join(OUT_DIR, "probes.json")
    _write(p, man)
    log(f"[manifest] {_relp(p)} ({len(probes)} probes + control)")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", choices=["fix", "wall"], default=None)
    args = ap.parse_args(argv)
    os.makedirs(OUT_DIR, exist_ok=True)
    fix_rec = wall_rec = None
    if args.only in (None, "fix"):
        fix_rec = build_fix_probes()
        _write(os.path.join(OUT_DIR, "WF_report.json"), fix_rec)
    if args.only in (None, "wall"):
        wall_rec = build_wall_probe()
        _write(os.path.join(OUT_DIR, "W1_report.json"), wall_rec)
    write_manifest(fix_rec, wall_rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
