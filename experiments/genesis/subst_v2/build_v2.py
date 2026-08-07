#!/usr/bin/env python
"""build_v2.py -- THE FIXER's re-emit: (A) IN-PLACE PAYLOAD PROBES on K1 for
the two convicted classes (PenWidthTableElem + the built-in GStyleElem
catalog), and (B) the settings + catalog substitution rungs (X1, X2, X3, X4,
X5, X10, X6a) re-derived through ``tools/genesis_substitute.py``'s proven
engine with the FIXED constructors (rvt.genesis.settings / catalog after the
fixer's specimen field-diff, 2026-08-03) -- all into
``experiments/genesis/subst_v2/`` with certification + ``probes.json``.

WHY IN-PLACE PROBES.  Verdict #9's divide (cloned records LOAD, our
from-scratch constructed records FAIL) leaves TWO suspects for our objects:
the object PAYLOAD (shape / values) and the ADD PATH (new ids, ElemTable
rows, registry re-pointing).  Every X/R rung so far substituted our records
at NEW ids -- so R2 (K6 + our catalog) also carried ~1,400 references from
INSIDE the embedded family documents to the deleted OLD catalog ids
(uneditable, left dangling; the parity audit never checks document
internals) plus our commit path's ElemTable rows.  ``X_pen`` / ``X_cat``
remove the add path entirely: the records of the EXISTING element ids (pen
table id 2; the 1,407 built-in style rows) are REPLACED IN PLACE by OUR
objects built AT THOSE IDS -- no id changes, no ElemTable change, no
registry re-pointing, Global/Latest and every embedded document
byte-identical to K1's -- through the certified byte-exact modify path
(rvt.manipulate, viewer-certified M3/M4).  A FAIL there convicts OUR OBJECT
PAYLOAD alone; a PASS retires the constructor and points at the add path
(the controls stream's X0 tests exactly that half).

Run (repo root):
    .venv/bin/python experiments/genesis/subst_v2/build_v2.py            # everything
    .venv/bin/python experiments/genesis/subst_v2/build_v2.py --probes-only
    .venv/bin/python experiments/genesis/subst_v2/build_v2.py --rungs-only
    .venv/bin/python experiments/genesis/subst_v2/build_v2.py --manifest-only
"""
from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

SUBST_V2 = HERE
K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")

from rvt.mutate import Document                                   # noqa: E402
from rvt import manipulate as MP                                  # noqa: E402
from rvt.genesis import settings as ST                            # noqa: E402
from rvt.genesis import catalog as CAT                            # noqa: E402
from rvt.genesis.types import INVALID                             # noqa: E402


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _validate(path: str) -> dict:
    from rvt.validate import validate_file
    rep = validate_file(path)
    errs = rep.errors
    return {"ok": bool(rep.ok), "errors": len(errs), "warnings": len(rep.warnings),
            "error_messages": [f"[{f.layer}] {f.where}: {f.message}"[:400] for f in errs[:6]],
            "stats": {k: v for k, v in rep.stats.items()
                      if k in ("streams", "records", "elements_decoded", "refs_checked",
                               "partition_blocks", "decode_failures")}}


# ===========================================================================
# A. IN-PLACE PAYLOAD PROBES on K1
# ===========================================================================

def _catalog_id_map(doc: Document) -> Tuple[Dict[Tuple[int, int], int],
                                            Dict[Tuple[int, int], dict]]:
    """{(category, type): existing element id} for K1's built-in
    object-style rows + the OLD rows' own pattern / material references
    (the document wiring the strict 'elem' keys keep)."""
    ids: Dict[Tuple[int, int], int] = {}
    wiring: Dict[Tuple[int, int], dict] = {}
    for gid in doc.ids_of_class("GStyleElem", host_only=True):
        v = doc.value(gid) or {}
        if v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
            continue
        cid = v.get("m_categoryId")
        if not (isinstance(cid, int) and cid < 0):
            continue
        key = (int(cid), int(v.get("m_gstyleType", 1)))
        if key in ids:
            continue
        ids[key] = int(gid)
        gs = ((v.get("m_pGStyle") or {}).get("value") or {})
        wiring[key] = {"line_pattern_id": gs.get("m_linePatternId"),
                       "material_id": gs.get("m_materialElemId")}
    return ids, wiring


def _replace_element(sess: MP.EditSession, eid: int, rec, *, with_header: bool,
                     plans: list, report: list) -> None:
    """Replace the seq-102 object (and optionally the seq-101 header) of the
    EXISTING element ``eid`` with OUR record built at that id, through the
    certified modify path (working copy overwrite -> re-encoded replacement).
    seq-103 (SerializedDummy) is left untouched."""
    pl = MP.ModifyPlan(kind="fixer-inplace-substitute", elem_id=int(eid),
                       class_name=rec.class_name)
    # object
    val = sess.value(eid, 102)                    # asserts the ORIGINAL round-trips
    orig_cells = copy.deepcopy(val.get("m_cellList"))
    val.clear()
    val.update(copy.deepcopy(rec.obj))
    kept_cells = False
    if not with_header and orig_cells is not None:
        # the KEPT parent header carries the cell-list era bit (0x800) exactly
        # when its object holds a CellList{PatternHelper}: keep that machinery
        # cell with the kept header so the object-only probe stays internally
        # consistent (the body VALUES are still ours)
        val["m_cellList"] = orig_cells
        kept_cells = True
    pl.record_edits.append(sess.replacement(
        eid, 102, f"in-place substitute {rec.class_name} object with OURS at id {eid}"))
    edited = ["102"]
    if with_header:
        hv = sess.value(eid, 101)
        hv.clear()
        hv.update(copy.deepcopy(rec.header))
        pl.record_edits.append(sess.replacement(
            eid, 101, f"in-place substitute {rec.class_name} header with OURS at id {eid}"))
        edited.append("101")
    plans.append(pl)
    report.append({"id": int(eid), "class": rec.class_name, "seqs_replaced": edited,
                   **({"kept_parent_cell_list": True} if kept_cells else {})})


def build_inplace_probes(only: Optional[List[str]] = None) -> Dict[str, dict]:
    """X_pen / X_pen_obj / X_cat / X_cat_obj on K1.  Returns per-probe reports."""
    want = set(only) if only else None
    log(f"\n=== PART A: in-place payload probes on {_relp(K1)} ===")
    t0 = time.time()
    doc = Document.from_file(K1)
    log(f"   K1 loaded: {len(doc.et_by_id):,} host elements ({round(time.time()-t0,1)}s)")
    results: Dict[str, dict] = {}

    # ---- the project pen table (id 2 in every 2026 file; m_famId -1) ------
    pen_id = None
    for e in doc.ids_of_class("PenWidthTableElem", host_only=True):
        if int((doc.value(e) or {}).get("m_famId", -1)) == INVALID:
            pen_id = int(e)
            break
    if pen_id is None:
        raise RuntimeError("K1: project pen table (m_famId -1) not found")
    our_pen = ST.pen_width_table(elem_id=pen_id)
    pen_lint = ST.lint_pen_width_table(our_pen)
    log(f"   our pen table AT id {pen_id}: lint hard={len(pen_lint['hard'])} ok={pen_lint['ok']}")

    for name, with_header in (("X_pen", True), ("X_pen_obj", False)):
        if want and name not in want:
            continue
        results[name] = _emit_inplace(
            doc, name, [(pen_id, our_pen)], with_header=with_header,
            desc={"class": "PenWidthTableElem",
                  "one_change": (f"K1's project pen table (id {pen_id}) records replaced IN "
                                 f"PLACE by OUR pen table built at id {pen_id} "
                                 f"({'object + header' if with_header else 'object only'}); "
                                 f"scale set {our_pen.refs.get('scales')} (the six-sample "
                                 f"format constant), our ISO-128 widths"),
                  "lint": pen_lint})

    # ---- the built-in object-styles catalog (1,407 rows) -------------------
    if not want or ("X_cat" in want or "X_cat_obj" in want):
        id_map, wiring = _catalog_id_map(doc)
        log(f"   K1 built-in style rows: {len(id_map)} keys")
        recs = CAT.builtin_style_catalog(None, id_map=id_map, wiring=wiring)
        by_key = {(int(r.obj["m_categoryId"]), int(r.obj["m_gstyleType"])): r for r in recs}
        missing = sorted(set(id_map) - set(by_key))
        if missing:
            raise RuntimeError(f"catalog missing {len(missing)} K1 keys, e.g. {missing[:5]}")
        # only the keys K1 carries (the enum is exactly K1's set; assert)
        extra = sorted(set(by_key) - set(id_map))
        cat_lint = CAT.lint_builtin_style_catalog(recs, standalone=False)
        log(f"   our catalog AT the existing ids: {len(recs)} rows (K1 keys not in enum: "
            f"{len(extra)}); lint hard={len(cat_lint['hard'])} soft={len(cat_lint['soft'])} "
            f"ok={cat_lint['ok']}")
        pairs = [(id_map[k], by_key[k]) for k in sorted(id_map, key=lambda kk: id_map[kk])]
        for name, with_header in (("X_cat", True), ("X_cat_obj", False)):
            if want and name not in want:
                continue
            results[name] = _emit_inplace(
                doc, name, pairs, with_header=with_header,
                desc={"class": "GStyleElem (built-in object-styles catalog)",
                      "one_change": (f"K1's {len(pairs)} built-in object-style rows' records "
                                     f"replaced IN PLACE by OUR profiled catalog rows built "
                                     f"at the SAME ids ({'object + header' if with_header else 'object only'}); "
                                     f"pattern/material of the strict 'elem' keys wired to "
                                     f"the SAME elements the old rows referenced"),
                      "lint": {"ok": cat_lint["ok"], "hard": len(cat_lint["hard"]),
                               "soft": len(cat_lint["soft"])},
                      "wiring_keys": sorted([list(k) for k in wiring
                                             if (by_key[k].refs.get("profile") or {})
                                             .get("pattern") == "elem"
                                             or (by_key[k].refs.get("profile") or {})
                                             .get("material") == "elem"])[:200]})
    return results


def _emit_inplace(doc: Document, name: str, pairs: List[Tuple[int, Any]], *,
                   with_header: bool, desc: dict) -> dict:
    """Write ``<name>.rvt`` = K1 with the given (existing id -> our record)
    pairs replaced in place; certify; write ``<name>.json``."""
    out = os.path.join(SUBST_V2, f"{name}.rvt")
    log(f"\n-- {name}: {desc['one_change']}")
    t0 = time.time()
    sess = MP.EditSession(doc)                    # fresh working copies per probe
    plans: list = []
    replaced: list = []
    skipped: list = []
    for eid, rec in pairs:
        try:
            _replace_element(sess, int(eid), rec, with_header=with_header,
                             plans=plans, report=replaced)
        except MP.ManipulationError as e:                  # original not byte-exact editable
            skipped.append({"id": int(eid), "class": rec.class_name, "error": str(e)[:300]})
    crep = MP.commit_plans(K1, out, plans)
    log(f"   committed: {len(replaced)} element(s) replaced in place "
        f"({sum(len(r['seqs_replaced']) for r in replaced)} records), {len(skipped)} skipped; "
        f"elemtable {crep.elemtable_count_before}->{crep.elemtable_count_after}; "
        f"{round(time.time()-t0,1)}s")
    # ---- certification ---------------------------------------------------
    val = _validate(out)
    log(f"   validator: ok={val['ok']} errors={val['errors']} warnings={val['warnings']}")
    check = _reload_check(out, [p[0] for p in pairs], [p[1] for p in pairs],
                          ignore_cell=(not with_header))
    log(f"   re-decode: {check['decoded_clean']}/{check['checked']} target records clean; "
        f"objects equal ours {check['equal_ours']}/{check['checked']}; "
        f"non-target streams identical {check['streams_identical']}")
    report = {
        "probe": name, "kind": "in-place substitution (records of EXISTING ids replaced)",
        "base": _relp(K1), "out": _relp(out), "class": desc["class"],
        "one_change": desc["one_change"], "with_header": with_header,
        "replaced_elements": len(replaced),
        "replaced": (replaced if len(replaced) <= 24 else
                     replaced[:12] + [{"...": f"{len(replaced) - 12} more"}]),
        "skipped_not_editable": skipped,
        "commit": crep.to_json(),
        "constructor_lint": desc.get("lint"),
        "wiring_keys": desc.get("wiring_keys"),
        "validator": val,
        "reload_check": check,
        "verdict": ("VALID" if (val["ok"] and val["errors"] == 0 and not skipped
                                and check["decoded_clean"] == check["checked"]) else "PROBLEM"),
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(SUBST_V2, f"{name}.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    return report


def _reload_check(path: str, ids: List[int], recs: list, *, ignore_cell: bool = False) -> dict:
    """Reload the written file: each target id's records decode clean, its
    object EQUALS our record's object (modulo the parent's kept CellList
    on object-only probes), and Global/Latest + every non-partition
    stream is byte-identical to K1's."""
    from rvt.container import open_rvt
    from rvt.genesis.types import _values_equal
    d2 = Document.from_file(path)
    clean = equal = 0
    bad: list = []
    by_id = {int(r.elem_id): r for r in recs}
    for eid in ids:
        r = d2.record(eid, 102)
        o = d2.dec.decode_record(r.class_id, r.payload) if r else None
        if o is not None and o.clean:
            clean += 1
            got, want = o.value, by_id[eid].obj
            if ignore_cell:
                got = {k: v for k, v in got.items() if k != "m_cellList"}
                want = {k: v for k, v in want.items() if k != "m_cellList"}
            if _values_equal(got, want):
                equal += 1
            elif len(bad) < 5:
                bad.append({"id": eid, "why": "decoded object != our record"})
        elif len(bad) < 5:
            bad.append({"id": eid, "why": "no clean seq-102 record after commit"})
    # stream identity vs K1 (everything except the partition + ElemTable/Contents
    # side-effects the modify path re-frames)
    same = diff = 0
    diffs: list = []
    with open_rvt(K1) as a, open_rvt(path) as b:
        for si in a.streams():
            s = si.name
            if s.startswith("Partitions/") or s == "Global/ElemTable":
                continue
            try:
                if a.raw(s) == b.raw(s):
                    same += 1
                else:
                    diff += 1
                    diffs.append(s)
            except Exception:                              # noqa: BLE001
                pass
    return {"checked": len(ids), "decoded_clean": clean, "equal_ours": equal,
            "problems": bad, "streams_identical": same, "streams_differing": diffs,
            "latest_identical": "Global/Latest" not in diffs}


# ===========================================================================
# B. THE V2 SUBSTITUTION RUNGS (X1, X2, X3, X4, X5, X10, X6a) via the tool
# ===========================================================================

def build_v2_rungs(only: Optional[List[str]] = None, keep_intermediates: bool = False) -> Dict[str, dict]:
    import genesis_substitute as GS
    GS.SUBST = SUBST_V2                             # parent resolution -> our directory
    want = set(only) if only else None

    def build_X6a_v2(ctx):
        """The tool's X6a correspondence + THE FIXER'S WIRING: the strict
        'elem' keys' pattern / material reference the SAME document
        element the parent's OLD row referenced (our object, the
        document's wiring); everything else = our profiled catalog."""
        old_by_key: Dict[Tuple[int, int], int] = {}
        for e in ctx.ids_of("GStyleElem"):
            v = ctx.value(e)
            if int(v.get("m_famId", -1) or -1) != -1:
                continue
            cid = v.get("m_categoryId")
            t = v.get("m_gstyleType")
            if not (isinstance(cid, int) and cid < 0 and isinstance(t, int)):
                continue
            old_by_key.setdefault((int(cid), int(t)), int(e))
        wiring: Dict[Tuple[int, int], dict] = {}
        for key, oid in old_by_key.items():
            gs = (((ctx.value(oid) or {}).get("m_pGStyle") or {}).get("value") or {})
            wiring[key] = {"line_pattern_id": gs.get("m_linePatternId"),
                           "material_id": gs.get("m_materialElemId")}
        ours = CAT.builtin_style_catalog(ctx.ids, wiring=wiring)
        lint = CAT.lint_builtin_style_catalog(ours, standalone=False)
        corr: Dict[int, int] = {}
        new_only: list = []
        covered = set()
        for r in ours:
            key = (int(r.obj.get("m_categoryId")), int(r.obj.get("m_gstyleType")))
            o = old_by_key.get(key)
            if o is None:
                new_only.append(r)
            else:
                corr[o] = r.elem_id
                covered.add(key)
        old_uncovered = sorted(set(old_by_key) - covered)
        notes = [f"FIXER v2: our catalog {len(ours)} rows shaped by the frozen per-key "
                 f"structural profile (lint hard {len(lint['hard'])}, soft {len(lint['soft'])}); "
                 f"strict 'elem' keys wired to the parent's own pattern/material elements",
                 f"1:1 by (category, style-type): mapped {len(corr)}, sample-only (deleted) "
                 f"{len(old_uncovered)}, ours-only (registered) {len(new_only)}"]
        return GS.SubstBuild(old_ids=sorted(old_by_key.values()), records=list(ours),
                             corr=corr, new_only=new_only, notes=notes,
                             residue={"GStyleElem(project-subcategory)":
                                      "the subcategory / line-style layer (X6b gap) kept"},
                             info={"catalog_lint": {"hard": len(lint['hard']),
                                                    "soft": len(lint['soft'])},
                                   "sample_only_keys": [list(k) for k in old_uncovered[:40]]})

    chain_names = ["X1", "X2", "X3", "X4", "X5", "X10", "X6a"]
    rungs = {r.name: r for r in GS.RUNGS}
    results: Dict[str, dict] = {}
    log(f"\n=== PART B: v2 substitution rungs {chain_names} -> {_relp(SUBST_V2)} ===")
    for name in chain_names:
        if want and name not in want:
            continue
        rung = rungs[name]
        if name == "X6a":
            rung = dataclasses.replace(rung, build=build_X6a_v2)
        parent = GS.parent_path_of(rung)
        if not os.path.exists(parent):
            log(f"\n== {name}: parent {_relp(parent)} missing -- SKIPPED (build {rung.parent} first)")
            continue
        try:
            if rung.kind == "removal":
                results[name] = GS.run_family_removal(rung, parent, out_dir=SUBST_V2)
            else:
                results[name] = GS.substitute(rung, parent, out_dir=SUBST_V2,
                                              keep_intermediates=keep_intermediates)
        except Exception as ex:                              # a rung that cannot build is a FINDING
            import traceback
            tb = traceback.format_exc()
            log(f"\n== {name}: BUILD ABORTED -- {ex!r}\n{tb}")
            results[name] = {"rung": name, "verdict": "NOT-BUILT", "abort": repr(ex),
                             "traceback": tb}
            with open(os.path.join(SUBST_V2, f"{name}.json"), "w") as fh:
                json.dump(results[name], fh, indent=1, default=str)
            bad = os.path.join(SUBST_V2, f"{name}.rvt")
            if os.path.exists(bad):
                os.remove(bad)
            break
    return results


# ===========================================================================
# C. probes.json (the upload manifest, ORDERED BY INFORMATION VALUE)
# ===========================================================================

def write_probes_manifest() -> str:
    def rep(name):
        p = os.path.join(SUBST_V2, f"{name}.json")
        if not os.path.exists(p):
            return None
        with open(p) as fh:
            return json.load(fh)

    def rvt_exists(name):
        return os.path.exists(os.path.join(SUBST_V2, f"{name}.rvt"))

    probes = []

    def add(name, sibling, one_thing, passing_means, failing_means, order_note):
        r = rep(name)
        if r is None or not rvt_exists(name):
            return
        val = r.get("validator") or {}
        probes.append({
            "file": f"experiments/genesis/subst_v2/{name}.rvt",
            "rung": name,
            "kind": r.get("kind") or r.get("label") or "",
            "verdict": r.get("verdict", "?"),
            "validator": {"ok": val.get("ok"), "errors": val.get("errors"),
                          "warnings": val.get("warnings")},
            "tests_one_thing": one_thing,
            "passing_sibling": sibling,
            "PASS_means": passing_means,
            "FAIL_means": failing_means,
            "read_order_note": order_note,
            "bytes": (r.get("bytes") or (os.path.getsize(os.path.join(SUBST_V2, f'{name}.rvt'))
                                          if rvt_exists(name) else 0)),
        })

    add("X_cat", "K1.rvt (viewer PASS; byte-identical except the 1,407 style-row records)",
        "OUR built-in object-styles catalog OBJECT PAYLOAD alone (records replaced IN PLACE at "
        "K1's existing ids; no add path, no registry edits, Global/Latest byte-identical to K1's)",
        "our catalog objects (fixed per-key structural profile: per-category header flag byte, "
        "pattern/pen null cells, screen-sized flag, built-in material ids; our pens/colours) are "
        "reader-accepted => X6a/K6/R2's residual defect is the ADD PATH (new ids / re-pointing / "
        "R2's dangling embedded-document refs), not our rows",
        "our catalog OBJECTS themselves are rejected -> diff the FIRST failing key class: read the "
        "card message; bisect X_cat_obj (object only, K1 headers kept) then by profile class "
        "(null-pattern / screen-sized / built-in-material keys)",
        "highest information value: attributes R2/X6a/K6 in one file")
    add("X_pen", "K1.rvt (viewer PASS; byte-identical except element id 2's records)",
        "OUR PenWidthTableElem OBJECT PAYLOAD alone (id 2's header + object replaced in place; "
        "scale set 10/20/50/100/200/500 = the six-sample format constant, our ISO-128 widths)",
        "our pen table constructor is reader-accepted; the pen table is retired from the "
        "constructed-base suspect list (X1's remaining variable is the add path)",
        "our pen table object is rejected -> read the card message; compare X_pen_obj (K1 "
        "header kept) to separate our header from our object body",
        "second: the census's #1 singleton suspect, one 2-record change")
    add("X_cat_obj", "X_cat / K1.rvt",
        "the same catalog substitution with K1's seq-101 ElementHeaders KEPT (object bodies only; "
        "rows whose kept header carries the cell-list era bit 0x800 also keep the parent's own "
        "CellList so the pair stays internally consistent -- the body VALUES are ours)",
        "our catalog object BODIES load with Autodesk's headers => if X_cat FAILED, our profiled "
        "header flag word is the defect; if X_cat PASSED too, both are fine",
        "our object BODIES are rejected regardless of the header",
        "follow-up to X_cat (attributes header vs body)")
    add("X_pen_obj", "X_pen / K1.rvt",
        "the same pen-table substitution with K1's seq-101 ElementHeader KEPT (object body only)",
        "our pen table BODY loads with Autodesk's header (attributes an X_pen FAIL to our header)",
        "our pen table BODY is rejected regardless of the header",
        "follow-up to X_pen")
    for name, parent in (("X1", "K1"), ("X2", "X1"), ("X3", "X2"), ("X4", "X3"), ("X5", "X4"),
                         ("X10", "X5"), ("X6a", "X10")):
        r = rep(name)
        if r is None:
            continue
        add(name, f"{parent} (its passing parent rung)",
            r.get("tests") or r.get("label") or name,
            r.get("if_PASS") or "", r.get("if_FAIL") or "",
            "the cumulative v2 ladder (add-path route) re-emitted with the FIXED constructors; "
            "read in derivation order X1 -> X2 -> X3 -> X4 -> X5 -> X10 -> X6a")
    manifest = {
        "stream": "genesis-fixer (2026-08-03)",
        "record": "docs/inbox/genesis-fixer.md",
        "what_changed": ("rvt.genesis.settings pen table: the model-pen scale set is now the "
                         "six-sample format constant (10, 20, 50, 100, 200, 500) -- our old "
                         "24..768 ladder put a scale (768) NO specimen of 3,494 corpus pen "
                         "tables carries into the table; widths stay our ISO-128 series.  "
                         "rvt.genesis.catalog: the object-styles table is now SHAPED per "
                         "(category, style-type) by the frozen structural profile "
                         "(builtin_style_profile.json): per-category ElementHeader flag word "
                         "(low byte 0x0E vs 0x1E is a per-CATEGORY compiled-in property; ~668 "
                         "of our rows carried a flag byte outside their category's observed "
                         "set), 380 pattern-null cells, 40 pen-null cells, 48 screen-sized "
                         "keys, 32 built-in material ids -- 2,560 fields the linter method "
                         "convicted, now 0."),
        "reading_the_results": {
            "X_cat PASS + X_pen PASS": ("our two convicted CONSTRUCTORS are reader-accepted "
                                        "objects; the constructed-base defect lives in the "
                                        "ADD PATH (the controls' X0 half of the matrix) -- "
                                        "genesis proceeds by fixing the add path / minting "
                                        "rows in place."),
            "X_cat FAIL": ("our catalog objects are still rejected after the shape fix: the "
                           "residual is a VALUE constraint (colour palette? pen assignment?) or "
                           "an unmeasured field -- read the card message, upload X_cat_obj, "
                           "then bisect by profile class."),
            "X_pen FAIL": ("our pen table object is rejected: upload X_pen_obj; if that "
                           "PASSES the defect is our ElementHeader for PenWidthTableElem."),
            "v2 ladder": ("X1..X6a re-emitted through the add-path route with the fixed "
                          "constructors; only informative once X_pen/X_cat read PASS "
                          "(then the FIRST failing v2 rung convicts the add path of that rung's "
                          "class)."),
        },
        "upload_order": [p["rung"] for p in probes],
        "probes": probes,
    }
    p = os.path.join(SUBST_V2, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"\nwrote {_relp(p)} ({len(probes)} probes: {[x['rung'] for x in probes]})")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probes-only", action="store_true", help="only the in-place probes")
    ap.add_argument("--rungs-only", action="store_true", help="only the v2 ladder rungs")
    ap.add_argument("--manifest-only", action="store_true", help="only (re)write probes.json")
    ap.add_argument("--only", default="", help="comma list (X_pen,X_cat,X1,...)")
    args = ap.parse_args(argv)
    only = [s.strip() for s in args.only.split(",") if s.strip()] or None
    t0 = time.time()
    if not args.manifest_only:
        if not args.rungs_only:
            build_inplace_probes(only)
        if not args.probes_only:
            build_v2_rungs(only)
    write_probes_manifest()
    log(f"\ntotal {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
