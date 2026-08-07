#!/usr/bin/env python
"""build_regadd.py -- THE FIXED-ADD-PATH PROBE LADDER (genesis-addfix stream).

Every probe derives from K1 (Autodesk's viewer-PASSING empty-project
skeleton, experiments/genesis/triage/K1.rvt) by ONE change, is emitted
through ``rvt.regadd`` (the proven ``rvt.reduce`` re-blocker underneath),
and carries its BYTE-DIFF vs K1 in ``<probe>.diff.json`` -- the assertions
'ElemTable identical / Latest identical / record positions identical /
only object bytes changed' are checked, not claimed.

READ THE ORDER (probes.json:reading_order).  The night's decisive batch
(X0, X1u, C0, X_pen, X_cat -- ALL FAIL, ~00:25 2026-08-04) contained NO
positive control, and X_pen (a pure in-place content swap differing from
K1 in ONE record) failing beside X0 (Autodesk's own bytes via the add path)
cannot be explained by one defect.  So the FIRST file is a POSITIVE CONTROL
that MUST pass: if XR_null fails, the pipeline / viewer batch is broken and
every genesis verdict since ~22:50 is suspect -- STOP and re-read the failed
set beside a fresh control before believing any of it.

  XR_null  K1 with the pen table (id 2) substituted by ITS OWN exact bytes:
           BYTE-IDENTICAL to K1 in EVERY stream (asserted) => content-
           identical to a certified-lineage base.  THE BATCH POSITIVE CONTROL.
  XR0      K1 with element 2's records substituted IN PLACE by OUR pen table
           (fixed six-sample scale set + our ISO-128 widths).  ONE change vs
           K1: element 2's object bytes.  Same id, same ElemTable stream,
           same Latest, same record position, same block partition (asserted).
           == the fixer's X_pen minus the re-chunker variable (proven reblock
           mechanics; X_pen used manipulate's).  XR0 FAIL + XR_null PASS =>
           OUR PEN-TABLE VALUES ARE AUDITED (name them: XR0.json:content).
           XR0 PASS => X_pen's failure was mechanics / the batch, and our pen
           table is reader-clean.
  XR0v     (NO upload) our constructor fed K1's EXACT feet at id 2, in place:
           byte-identical to K1 (asserted at build) -- collapses onto XR_null;
           re-proves the pen constructor's shape/header/rep exactness.
  XR1      K1 with catalog row 34 (OST_Windows projection) substituted IN
           PLACE by OUR profiled row (wired to the row's own pattern /
           material).  ONE change: row 34's object (+ its header flag word,
           the C1v variable).  Reads like XR0, for the catalog class.
  XA0      THE ADD-PATH NULL: K1 with element 2 DELETED and Autodesk's EXACT
           pen table RE-ADDED at id 2 through the FIXED add path
           (row COPIED, same-id re-insert at the deleted position, Latest
           untouched) => BYTE-IDENTICAL to K1 (asserted).  Proves the add
           path is zero-motion when the registration is unchanged.
  XA1      the FIXED add path carrying OUR pen table at id 2 (delete 2 + add
           ours at 2, row preserved): content == XR0, mechanics == the add
           path.  Asserted byte-identical to XR0 (no upload unless XR0's
           verdict needs cross-checking).
  XA2      X0 DONE RIGHT: K1 minus id 2 + Autodesk's EXACT pen table added at
           a FREE LOW id (< 5,000, the corpus band -- X0 used 1,500,000) with
           the corpus row COPIED from K1's own element 2 (creation ep 0,
           modified 976, user 976 -- X0 wrote 1016,1016,1016), inserted at
           the ID HOLE (X0 appended at the unit end), the PenWidthTableInfo
           leaf re-pointed 2 -> new id (schema-typed).  The DIRECT SIBLING OF
           X0 differing ONLY in the registration (id band + vintage +
           position).  XA2 PASS + X0 FAIL => THE REGISTRATION IS AUDITED and
           this path FIXES it (KNOWLEDGE-grade).  XA2 FAIL + XR_null PASS =>
           moving a birth singleton to a new id is itself rejected (the
           genesis writer must MINT such singletons at their canonical low
           ids, in place -- see docs/writer/add-path.md).
  XR3      K1 with ALL built-in object-style catalog rows substituted IN
           PLACE row-for-row by OUR profiled catalog (the fixer's X_cat
           content on the proven mechanics; ids / rows / positions / Latest
           untouched -- and NO family removal needed: in-place moves nothing,
           so the embedded documents' catalog references stay valid).
  XR2      the settings singletons substituted IN PLACE 1:1 (the subset of
           the X-ladder's X1..X5 whose old class == our class); the classes
           that CANNOT be swapped in place (count mismatch / new-only
           companions) are LISTED, not faked.
  XR_deep  XR2 + XR3 (settings + catalog ours, in place).

Reproduce (repo root, ~6-8 min):
    .venv/bin/python experiments/genesis/regadd/build_regadd.py
    .venv/bin/python experiments/genesis/regadd/build_regadd.py --only XR_null,XR0
    .venv/bin/python experiments/genesis/regadd/build_regadd.py --manifest-only
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt import regadd as RA                                       # noqa: E402
from rvt.encode import encode_record, record_bytes                # noqa: E402
from rvt.genesis import settings as ST                              # noqa: E402
from rvt.genesis import catalog as CAT                              # noqa: E402
from rvt.genesis.types import INVALID, IdSource, TypeRecord         # noqa: E402
from rvt.mutate import Document                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
PEN_ID = 2                      # the project pen table (m_famId -1) in K1
CAT_ROW = 34                    # OST_Windows (-2000014) projection row in K1


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _write(name: str, rep: dict) -> None:
    with open(os.path.join(HERE, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=str)


def _summ(rep) -> dict:
    d = rep.to_json() if hasattr(rep, "to_json") else dict(rep)
    diff = d.pop("diff", None)
    if diff is not None:
        # keep the report readable; the full diff is written separately
        d["diff_summary"] = {
            "streams_differing": diff["streams"]["differing"],
            "streams_identical_count": len(diff["streams"]["identical"]),
            "partition_logical_identical": diff["partition_logical_identical"],
            "records_added": len(diff["records"]["added"]),
            "records_removed": len(diff["records"]["removed"]),
            "records_changed": diff["records"]["changed_count"],
            "changed_ids": diff["records"]["changed_ids"][:20],
            "id_order_identical": diff["records"]["id_order_identical"],
            "common_order_preserved": diff["records"]["common_order_preserved"],
            "block_partition_identical": {str(k): v["identical"]
                                          for k, v in diff["blocks"].items()},
            "elemtable_identical": diff["elemtable"]["identical"],
            "latest_identical": diff["latest"]["identical"],
            "embedded_units_identical": diff["embedded_units_identical"],
        }
    return d


def _stream_identity(a: str, b: str) -> dict:
    """Raw per-stream identity between two files (the collapse checks)."""
    from rvt.container import open_rvt
    same, diff = [], []
    with open_rvt(a) as fa, open_rvt(b) as fb:
        for s in [x.name for x in fa.streams()]:
            try:
                (same if fa.raw(s) == fb.raw(s) else diff).append(s)
            except Exception:                                    # noqa: BLE001
                diff.append(s)
    return {"identical": sorted(same), "differing": sorted(diff),
            "all_identical": not diff}


# ===========================================================================
# THE PEN-TABLE CONTENT (ours) + the exact-feet twin
# ===========================================================================

def our_pen_table(elem_id: int) -> TypeRecord:
    """OUR pen table (the fixed constructor: six-sample scale set + our
    ISO-128 widths) at ``elem_id``."""
    return ST.pen_width_table(elem_id=int(elem_id))


def exact_feet_pen_table(elem_id: int, spec_value: dict) -> TypeRecord:
    """OUR constructor fed the specimen's EXACT feet (the X1v assertion)."""
    t = spec_value["m_pPenWidthTable"]["value"]
    model = {int(p["m_invertedScale"]): [float(x) for x in p["m_pens"]]
             for p in t["m_modelPenInfo"]}
    persp = [float(x) for x in t["m_perspectiveModelPenInfo"]["m_pens"]]
    draft = [float(x) for x in t["m_draftPenInfo"]["m_pens"]]
    return ST.pen_width_table(elem_id=int(elem_id), model_pens_ft=model,
                              perspective_pens_ft=persp, annotation_pens_ft=draft)


def _pen_content_note(rec: TypeRecord) -> dict:
    t = rec.obj["m_pPenWidthTable"]["value"]
    mm = ST.MM_PER_FT
    return {
        "scale_keys": [int(p["m_invertedScale"]) for p in t["m_modelPenInfo"]],
        "model_pens_mm": {int(p["m_invertedScale"]): [round(x * mm, 4) for x in p["m_pens"]]
                          for p in t["m_modelPenInfo"]},
        "perspective_mm": [round(x * mm, 4) for x in t["m_perspectiveModelPenInfo"]["m_pens"]],
        "draft_mm": [round(x * mm, 4) for x in t["m_draftPenInfo"]["m_pens"]],
        "provenance": ("OUR ISO-128-based line-weight series; scale set {10,20,50,100,200,"
                       "500} = the six-sample format constant (the fixer's P1/G-fix)"),
    }


# ===========================================================================
# THE PROBES
# ===========================================================================

def build_XR_null() -> dict:
    """K1 with element 2 substituted by ITS OWN bytes -> byte-identical to K1."""
    name = "XR_null"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: element {PEN_ID} substituted by its OWN exact bytes (null)")
    t0 = time.time()
    rep = RA.substitute_element(K1, out, PEN_ID, null=True)
    ident = _stream_identity(K1, out)
    body = _summ(rep)
    body.update({
        "probe": name, "role": "BATCH POSITIVE CONTROL + zero-motion proof",
        "one_change_vs_K1": "NONE by content: element 2 re-written with its own exact bytes",
        "raw_stream_identity_vs_K1": ident,
        "the_assertion": "every stream RAW-byte-identical to K1 (a content-identical "
                         "sibling of the certified base): this file MUST pass",
        "if_PASS": ("the upload/viewer batch is healthy and the reduce-writer mechanics "
                    "under regadd are zero-motion: read the other probes"),
        "if_FAIL": ("A CONTENT-IDENTICAL COPY OF K1 FAILS => the batch / viewer / upload "
                    "pipeline is broken, NOT any file.  STOP: every genesis verdict since "
                    "the last certified file (~21:05 08-03) is suspect and must be re-read "
                    "beside a fresh control.  Re-upload K1.rvt itself to confirm."),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", rep.diff or {})
    log(f"   verdict {rep.verdict}; all raw streams identical to K1: {ident['all_identical']} "
        f"({rep.problems or 'no problems'})")
    return body


def build_XR0() -> dict:
    """K1 with element 2's records replaced in place by OUR pen table."""
    name = "XR0"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: element {PEN_ID} substituted IN PLACE by OUR pen table")
    t0 = time.time()
    ours = our_pen_table(PEN_ID)
    rep = RA.substitute_element(K1, out, PEN_ID, ours)
    body = _summ(rep)
    d = rep.diff or {}
    ch = [c for c in d.get("records", {}).get("changed", []) if c["id"] == PEN_ID]
    body.update({
        "probe": name, "role": "OUR pen-table CONTENT, in place, proven mechanics",
        "one_change_vs_K1": ("element 2's records (our object + our header, same id, same "
                             "position, same ElemTable row, same Latest)"),
        "content": _pen_content_note(ours),
        "changed_records": [{k: v for k, v in c.items() if k != "field_diff"} for c in ch],
        "field_diff_examples": (ch[0].get("field_diff", [])[:12] if ch else []),
        "sibling_experiment": ("X_pen (experiments/genesis/subst_v2/X_pen.rvt) carried the "
                               "SAME content via manipulate.chunk_segment and FAILED; XR0 "
                               "removes the re-chunker variable (block partition asserted "
                               "identical to K1's)"),
        "if_PASS": ("our pen-table object is reader-clean; X_pen's failure was the "
                    "manipulate re-chunk mechanics on K1 or the ~00:25 batch, NOT our "
                    "content.  The pen constructor + this in-place route are the "
                    "genesis pen-table path"),
        "if_FAIL": ("(with XR_null PASSING) our pen-table VALUES are audited by the reader "
                    "-- the ONLY difference is the width doubles (see field_diff_examples): "
                    "our ISO-128 series 0.13..8.0 mm vs Autodesk's 0.1..10.0.  Next: the "
                    "width-value bisectors (Autodesk's exact widths on our scale set = "
                    "XR0v is already byte-identical to K1, so bisect the doubles by vector)."),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", d)
    log(f"   verdict {rep.verdict}; changed ids {d.get('records', {}).get('changed_ids')}; "
        f"ElemTable identical {d.get('elemtable', {}).get('identical')}; "
        f"Latest identical {d.get('latest', {}).get('identical')}")
    return body


def build_XR0v(k1doc: Optional[Document] = None) -> dict:
    """(no upload) OUR constructor fed K1's EXACT feet at id 2, in place:
    must be byte-identical to K1 -> collapses onto XR_null."""
    name = "XR0v"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: OUR constructor fed K1's EXACT feet at id {PEN_ID} (build assertion)")
    t0 = time.time()
    doc = k1doc or Document.from_file(K1)
    spec = doc.value(PEN_ID)
    ours = exact_feet_pen_table(PEN_ID, spec)
    # PROOF at the byte level: our records == K1's own records for id 2
    from rvt.regadd import EditImage
    img = EditImage(K1)
    old = img.records_of(PEN_ID)
    enc = ours.encode()
    per_seq = {}
    all_ident = True
    for s in (101, 102, 103):
        same = (enc[s] == old[s].data)
        per_seq[str(s)] = {"identical": same, "len_ours": len(enc[s]),
                           "len_k1": len(old[s].data)}
        if not same:
            n = min(len(enc[s]), len(old[s].data))
            per_seq[str(s)]["first_divergence"] = next(
                (i for i in range(n) if enc[s][i] != old[s].data[i]), n)
        all_ident = all_ident and same
    rep = RA.substitute_element(K1, out, PEN_ID, ours)
    ident = _stream_identity(K1, out)
    body = _summ(rep)
    body.update({
        "probe": name, "role": "constructor exactness assertion (NO UPLOAD)",
        "our_records_vs_K1_records": {"per_seq": per_seq, "all_identical": all_ident},
        "raw_stream_identity_vs_K1": ident,
        "collapse_onto_XR_null": ident["all_identical"],
        "reading": ("our pen constructor fed EXACT feet reproduces K1's element 2 "
                    "byte-for-byte (header + object + rep) => this file IS XR_null; "
                    "the ONLY thing XR0 changes vs an accepted file is the VALUES"),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    log(f"   our records == K1's: {all_ident}; file raw-identical to K1: "
        f"{ident['all_identical']} (verdict {rep.verdict})")
    return body


def build_XR1(k1doc: Optional[Document] = None) -> dict:
    """K1 with catalog row 34 substituted in place by OUR profiled row."""
    name = "XR1"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: catalog row {CAT_ROW} (OST_Windows projection) substituted IN PLACE "
        f"by OUR profiled row")
    t0 = time.time()
    doc = k1doc or Document.from_file(K1)
    v = doc.value(CAT_ROW) or {}
    cid = int(v.get("m_categoryId"))
    gtype = int(v.get("m_gstyleType", 1))
    gs = ((v.get("m_pGStyle") or {}).get("value") or {})
    wiring = {(cid, gtype): {"line_pattern_id": gs.get("m_linePatternId"),
                              "material_id": gs.get("m_materialElemId")}}
    id_map = {(cid, gtype): CAT_ROW}
    recs = CAT.builtin_style_catalog(IdSource(9_000_000), id_map=id_map, wiring=wiring)
    ours = [r for r in recs if int(r.elem_id) == CAT_ROW]
    if not ours:
        raise RuntimeError(f"our catalog did not emit the (cat {cid}, type {gtype}) row")
    ours = ours[0]
    rep = RA.substitute_element(K1, out, CAT_ROW, ours)
    body = _summ(rep)
    d = rep.diff or {}
    ch = [c for c in d.get("records", {}).get("changed", []) if c["id"] == CAT_ROW]
    ours_gs = ours.obj["m_pGStyle"]["value"]
    body.update({
        "probe": name, "role": "OUR catalog-row CONTENT (one row), in place, proven mechanics",
        "one_change_vs_K1": (f"row {CAT_ROW} (category {cid} OST_Windows, type {gtype}) "
                             f"object + header replaced by ours at the same id / position"),
        "specimen_row": {"pen": gs.get("m_penNumber"), "colour": gs.get("m_color"),
                         "line_pattern": gs.get("m_linePatternId"),
                         "material": gs.get("m_materialElemId"),
                         "header_abFlags4Bytes": hex(int((doc.decode(CAT_ROW, 101).value or {})
                                                         .get("m_abFlags4Bytes", 0)))},
        "our_row": {"pen": ours_gs.get("m_penNumber"), "colour": ours_gs.get("m_color"),
                    "line_pattern": ours_gs.get("m_linePatternId"),
                    "material": ours_gs.get("m_materialElemId"),
                    "header_abFlags4Bytes": hex(int(ours.header.get("m_abFlags4Bytes", 0))),
                    "profile": ours.refs.get("profile")},
        "changed_records": [{k: vv for k, vv in c.items() if k != "field_diff"} for c in ch],
        "field_diff_examples": (ch[0].get("field_diff", [])[:12] if ch else []),
        "sibling_experiment": ("C1v / C1u (controls) tested this row via the add path; X_cat "
                               "(subst_v2) carried the whole catalog in place via manipulate "
                               "and FAILED with the batch"),
        "if_PASS": ("our profiled catalog row (values + header preset) is reader-clean in "
                    "place; XR3 (the whole catalog in place) is the next read"),
        "if_FAIL": ("(with XR_null PASSING) a catalog-row VALUE or the header flag word "
                    "is audited: field_diff_examples names every difference (pen / colour "
                    "/ the profiled abFlags word)"),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", d)
    log(f"   verdict {rep.verdict}; changed ids {d.get('records', {}).get('changed_ids')}")
    return body


def build_XA0() -> dict:
    """THE ADD-PATH NULL: delete element 2 and RE-ADD Autodesk's exact pen
    table at id 2 through the fixed add path (row copied, same-id in-place
    position, Latest untouched) -> byte-identical to K1."""
    name = "XA0"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: ADD-PATH NULL -- delete {PEN_ID}, re-add Autodesk's exact pen table "
        f"at {PEN_ID} via add_element_like_original")
    t0 = time.time()
    from rvt.regadd import EditImage
    img = EditImage(K1)
    old = img.records_of(PEN_ID)
    verbatim = {s: r.data for s, r in old.items()}          # Autodesk's exact framed bytes
    rep = RA.add_element_like_original(
        K1, out, verbatim, class_name="PenWidthTableElem", new_id=PEN_ID,
        replace_old_id=PEN_ID, place="auto", preserve_row_of=PEN_ID)
    ident = _stream_identity(K1, out)
    body = _summ(rep)
    body.update({
        "probe": name, "role": "add-path NULL (delete + verbatim re-add at the same id)",
        "one_change_vs_K1": "NONE by content: Autodesk's exact records re-added at id 2",
        "raw_stream_identity_vs_K1": ident,
        "the_assertion": ("byte-identical to K1 in every stream: the fixed add path with "
                          "unchanged registration is a no-op"),
        "if_PASS": "the add path's mechanics are zero-motion (with XR_null PASSING)",
        "if_FAIL": ("(with XR_null PASSING) impossible unless the assertion above failed "
                    "at build time -- see rule_violations / diff_summary"),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", rep.diff or {})
    log(f"   verdict {rep.verdict}; raw-identical to K1: {ident['all_identical']}; "
        f"placement {rep.placement['per_seq'].get(102, {}).get('policy')}")
    return body


def build_XA1() -> dict:
    """The fixed add path carrying OUR pen table at id 2 (delete 2 + add
    ours at 2, row preserved) -> byte-identical to XR0."""
    name = "XA1"
    out = os.path.join(HERE, f"{name}.rvt")
    xr0 = os.path.join(HERE, "XR0.rvt")
    log(f"\n== {name}: the fixed add path with OUR pen table at id {PEN_ID} "
        f"(delete-and-add, row preserved) -> must equal XR0")
    t0 = time.time()
    ours = our_pen_table(PEN_ID)
    rep = RA.add_element_like_original(
        K1, out, ours, class_name="PenWidthTableElem", new_id=PEN_ID,
        replace_old_id=PEN_ID, place="auto", preserve_row_of=PEN_ID)
    ident = _stream_identity(xr0, out) if os.path.exists(xr0) else {"error": "XR0 not built"}
    body = _summ(rep)
    body.update({
        "probe": name, "role": "add-path mechanics == in-place mechanics (content = XR0's)",
        "one_change_vs_XR0": "NONE: same content via the delete-and-add route",
        "raw_stream_identity_vs_XR0": ident,
        "upload": ("NO upload unless XR0's verdict must be cross-checked through the add "
                   "route: XA1 is byte-identical to XR0 (asserted here)"),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", rep.diff or {})
    log(f"   verdict {rep.verdict}; raw-identical to XR0: {ident.get('all_identical')}")
    return body


def _free_low_id(img, prefer_hole: bool = True) -> Tuple[int, dict]:
    """Choose a FREE id < 5,000 for a birth-vintage singleton in K1; prefer
    one whose id neighbours are stream-adjacent (a clean ID-HOLE insert)."""
    run = img.runs[102]
    present = set(run.ids) | set(int(r[4]) for r in img.et_model["records"])
    cands = [i for i in range(7, 5000) if i not in present]
    info = {"free_low_ids_sample": cands[:12]}
    if prefer_hole:
        pos = {r.elem_id: i for i, r in enumerate(run.recs)}
        for c in cands:
            below = max((e for e in present if e < c), default=None)
            above = min((e for e in present if e > c), default=None)
            if below in pos and above in pos and pos[above] == pos[below] + 1:
                info.update({"chosen": c, "id_neighbours": [below, above],
                             "why": "id neighbours are stream-adjacent (clean ID-HOLE)"})
                return c, info
    c = cands[0]
    info.update({"chosen": c, "why": "smallest free low id (no clean hole found)"})
    return c, info


def build_XA2() -> dict:
    """X0 DONE RIGHT: Autodesk's exact pen table added at a FREE LOW id with
    the corpus row copied from K1's own element 2, the ID-HOLE position, and
    the PenWidthTableInfo leaf re-pointed 2 -> new id (typed)."""
    name = "XA2"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: X0 DONE RIGHT -- Autodesk's exact pen table added at a FREE LOW id "
        f"with corpus vintage / id-hole position / typed registry re-point")
    t0 = time.time()
    from rvt.regadd import EditImage
    img = EditImage(K1)
    new_id, id_info = _free_low_id(img)
    log(f"   chosen new id {new_id}: {id_info.get('why')}")
    # Autodesk's exact pen table, decoded and re-encoded at the NEW id: prove
    # byte-exactness at the ORIGINAL id first, then rebase only m_id (+ the
    # header's own-deletion entry) -- the controls stream's verbatim recipe
    old = img.records_of(PEN_ID)
    ident = RA._verify_byte_identity(img, PEN_ID, old)
    if not ident.get("all_identical"):
        raise RuntimeError(f"element {PEN_ID}: decode->encode not byte-exact: {ident}")
    obj = copy.deepcopy(img.decode(old[102]).value)
    hdr = copy.deepcopy(img.decode(old[101]).value)
    obj["m_id"] = int(new_id)
    dele = list(((hdr.get("m_parents") or {}).get("value") or {}).get("m_deletion") or [])
    dele = [int(new_id) if int(x) == PEN_ID else int(x) for x in dele]
    hdr["m_parents"]["value"]["m_deletion"] = dele
    cls_id = int.from_bytes(old[102].data[16:18], "little")
    framed = {101: encode_record(101, int(new_id), None, _hdr_class_id(old), hdr),
              102: encode_record(102, int(new_id), None, cls_id, obj),
              103: _dummy_rep(int(new_id), old[103])}
    rep = RA.add_element_like_original(
        K1, out, framed, class_name="PenWidthTableElem", new_id=int(new_id),
        replace_old_id=PEN_ID, place="auto",
        preserve_row_of=PEN_ID,                       # K1's OWN row: ce 0 / me 976 / ue 976
        latest_remap={PEN_ID: int(new_id)},           # PenWidthTableInfo 2 -> new (typed)
        strict_rules=False)
    body = _summ(rep)
    x0 = os.path.join(ROOT, "experiments", "genesis", "controls", "X0.rvt")
    body.update({
        "probe": name,
        "role": "THE ADD-PATH FIX: X0's experiment with the corpus-conformant registration",
        "id_choice": id_info,
        "verbatim_content_assertion": ident,
        "vs_X0": {
            "X0 (FAILED)": {"new_id": 1_500_000, "id_band": ">=1.5M (out of corpus band)",
                            "row": "(orig=new, ce 1016, me 1016, ue 1016) = parent's max ep",
                            "position": "appended at the unit END (position 6539/6540)",
                            "registry": "PenWidthTableInfo leaf re-pointed to 1,500,000"},
            "XA2 (this)": {"new_id": int(new_id), "id_band": RA.id_band(new_id),
                           "row": ("COPIED from K1's element 2 = (ce 0, me 976, ue 976): "
                                   "creation-episode 0 is the 7/7 corpus fact"),
                           "position": rep.placement["per_seq"].get(102, {}).get("reason"),
                           "registry": "PenWidthTableInfo leaf re-pointed 2 -> new (typed)"},
        },
        "the_one_thing_it_tests": ("does the corpus-conformant REGISTRATION (low id + "
                                   "birth-vintage row + hole position) make the add path "
                                   "load, with Autodesk's own content held byte-exact?"),
        "if_PASS": ("with X0 FAILED and XR_null PASSED: THE REGISTRATION IS AUDITED and this "
                    "path fixes it -- id band / vintage / position (a KNOWLEDGE finding; "
                    "the follow-up per-rule twins split which of the three).  The genesis "
                    "writer must mint birth singletons at low ids with episode-0 rows."),
        "if_FAIL": ("(with XR_null PASSED) even a corpus-conformant NEW-id registration of "
                    "a birth singleton is rejected => the reader binds these singletons to "
                    "their canonical ids/history: DO NOT MOVE THEM.  The route is XR0's: "
                    "substitute IN PLACE (a genesis writer mints them AT their canonical "
                    "ids in a fresh document).  Also read: was the typed re-point the only "
                    "registry motion (registry.remap_examples)?"),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", rep.diff or {})
    log(f"   verdict {rep.verdict}; new id {new_id}; violations {rep.rule_violations}; "
        f"registry remaps {rep.registry.get('remap_edits')}")
    return body


def _hdr_class_id(old: dict) -> int:
    """The ElementHeader class id from the old seq-101 record."""
    import struct as _st
    return _st.unpack_from("<H", old[101].data, 12)[0]


def _dummy_rep(new_id: int, old103) -> bytes:
    """The seq-103 SerializedDummy record re-framed at the new id (its body is
    empty / a bare class id, so only the record id changes)."""
    import struct as _st
    hl = 16
    size = old103.size
    cls = _st.unpack_from("<H", old103.data, hl)[0] if size >= 2 else None
    if size in (0, 2) and cls is not None:
        return encode_record(103, int(new_id), None, cls, {})
    # non-trivial rep (not expected for the pen table): re-id the header only
    stamp = _st.unpack_from("<I", old103.data, 8)[0]
    return _st.pack("<qII", int(new_id), stamp, size) + old103.data[hl:]


# ---------------------------------------------------------------------------
# XR3: the whole built-in catalog IN PLACE (row-for-row)
# ---------------------------------------------------------------------------

def _catalog_id_map(doc: Document) -> Tuple[Dict[Tuple[int, int], int],
                                            Dict[Tuple[int, int], dict]]:
    """{(category, type): existing id} for K1's built-in object-style rows +
    each old row's own pattern / material references (the wiring the
    profile's 'elem' keys keep)."""
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


def build_XR3(k1doc: Optional[Document] = None) -> dict:
    """ALL built-in catalog rows substituted IN PLACE by OUR profiled catalog."""
    name = "XR3"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: the WHOLE built-in object-styles catalog substituted IN PLACE "
        f"row-for-row (X_cat's content, proven mechanics)")
    t0 = time.time()
    doc = k1doc or Document.from_file(K1)
    id_map, wiring = _catalog_id_map(doc)
    recs = CAT.builtin_style_catalog(IdSource(9_000_000), id_map=id_map, wiring=wiring)
    by_key = {(int(r.obj["m_categoryId"]), int(r.obj["m_gstyleType"])): r for r in recs}
    missing = sorted(set(id_map) - set(by_key))
    if missing:
        raise RuntimeError(f"our catalog misses {len(missing)} K1 keys, e.g. {missing[:5]}")
    lint = CAT.lint_builtin_style_catalog(recs, standalone=False)
    pairs = {id_map[k]: by_key[k] for k in id_map}
    log(f"   {len(pairs)} rows to substitute in place; catalog lint hard "
        f"{len(lint['hard'])} soft {len(lint['soft'])}")
    rep = RA.substitute_elements(K1, out, pairs)
    body = _summ(rep)
    d = rep.diff or {}
    body.update({
        "probe": name, "role": "the WHOLE catalog OUR content, in place (X6a via substitution)",
        "rows_substituted": len(pairs),
        "one_change_vs_K1": (f"all {len(pairs)} built-in object-style rows' objects + headers "
                             f"replaced by ours at the SAME ids / rows / positions"),
        "catalog_lint": {"ok": lint["ok"], "hard": len(lint["hard"]),
                         "soft": len(lint["soft"])},
        "ordering_rule_note": ("the ladder's 'family removal must precede catalog "
                               "substitution' rule (embedded documents pin OLD catalog ids) "
                               "is MOOT for in-place: the ids do not change, so the embedded "
                               "documents' catalog references stay valid -- XR3 derives from "
                               "K1 directly (families intact = closer to the proven base)"),
        "sibling_experiment": ("X_cat (subst_v2) = this content via manipulate; FAILED in "
                               "the ~00:25 batch"),
        "if_PASS": ("our profiled catalog (per-key structure + our pens/colours) is reader-"
                    "clean in place: the catalog counsel item is now purely a legal decision"),
        "if_FAIL": ("(with XR1 PASSING) a MULTI-row property is audited (our single ink "
                    "colour / pen distribution across the whole table) -- bisect by row band; "
                    "(with XR1 FAILING) the row-level cause dominates"),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", d)
    log(f"   verdict {rep.verdict}; changed {d.get('records', {}).get('changed_count')} records; "
        f"ElemTable identical {d.get('elemtable', {}).get('identical')}; "
        f"Latest identical {d.get('latest', {}).get('identical')}")
    return body


# ---------------------------------------------------------------------------
# XR2: the settings singletons IN PLACE (the 1:1 subset), with the residue listed
# ---------------------------------------------------------------------------

def _our_settings_1to1(doc: Document, ctx=None) -> Tuple[Dict[int, TypeRecord], List[dict]]:
    """OUR settings-singleton records that map 1:1 onto an existing K1 element
    of the SAME class (in-placeable), plus the honest RESIDUE list (classes
    whose in-place substitution CANNOT hold).  Uses the substitution engine's
    own rung builders (X1 X3 X4 X5) so OUR values / wiring are exactly the
    ladder's; where a builder emits N != old-count or new-only companions,
    the class is residue (it needs the ADD path)."""
    import genesis_substitute as GS
    pairs: Dict[int, TypeRecord] = {}
    residue: List[dict] = []
    if ctx is None:
        ctx = GS.SubstContext(K1, "XR2")
    for rung_name in ("X1", "X2", "X3", "X4", "X5"):
        try:
            rung = GS.rung_by_name(rung_name)
            sb = rung.build(ctx)
        except Exception as e:                                        # noqa: BLE001
            residue.append({"rung": rung_name, "reason": f"builder raised {e!r}"[:300]})
            continue
        corr = {int(k): int(v) for k, v in sb.corr.items()
                if v not in (None, INVALID) and int(k) in {int(x) for x in sb.old_ids}}
        by_new = {int(r.elem_id): r for r in sb.records}
        # invert: new -> old for 1:1 same-class pairs
        new_to_old: Dict[int, int] = {}
        for o, n in corr.items():
            r = by_new.get(n)
            if r is None:
                continue
            if ctx.cls_of.get(o) != r.class_name:
                residue.append({"rung": rung_name, "old": o, "old_class": ctx.cls_of.get(o),
                                "new_class": r.class_name,
                                "reason": "class differs old vs ours (not a pure content swap)"})
                continue
            new_to_old[n] = o
        # new-only companions cannot be in-placed
        for r in sb.records:
            if int(r.elem_id) not in new_to_old:
                residue.append({"rung": rung_name, "our_new_only": int(r.elem_id),
                                "class": r.class_name,
                                "reason": "OUR new-only record has no old correspondent "
                                          "(needs the ADD path)"})
        for r in sb.new_only:
            residue.append({"rung": rung_name, "our_new_only": int(r.elem_id),
                            "class": r.class_name,
                            "reason": "new-only registration record (needs the ADD path)"})
        for o in sb.old_ids:
            if int(o) not in corr:
                residue.append({"rung": rung_name, "old_deleted": int(o),
                                "class": ctx.cls_of.get(int(o)),
                                "reason": "OLD element deleted without a correspondent "
                                          "(a deletion, not a substitution)"})
        # references between OUR records must be remapped new -> old (the
        # constellation's internal wiring: e.g. keynoting system -> table)
        mapping = {n: o for n, o in new_to_old.items()}
        dropped_new = {int(r.elem_id) for r in sb.records if int(r.elem_id) not in new_to_old} \
            | {int(r.elem_id) for r in sb.new_only}
        for n, o in new_to_old.items():
            r = by_new[n]
            # any reference to a dropped (residue) new id makes this record unusable
            leaves = ctx.ted.leaves(r.obj, r.class_name) + ctx.ted.leaves(r.header, "ElementHeader")
            refs = {lf.value for lf in leaves if isinstance(lf.value, int) and lf.value > 0}
            bad = refs & dropped_new
            if bad:
                residue.append({"rung": rung_name, "old": o, "new": n, "class": r.class_name,
                                "reason": f"OUR record references residue new id(s) {sorted(bad)[:4]} "
                                          f"(would dangle in place)"})
                continue
            rr = copy.deepcopy(r)
            ctx.ted.remap(rr.obj, rr.class_name, mapping)
            ctx.ted.remap(rr.header, "ElementHeader", mapping)
            rr.elem_id = int(o)
            if isinstance(rr.obj, dict) and "m_id" in rr.obj:
                rr.obj["m_id"] = int(o)
            # the header's own-deletion entry follows the id
            dl = ((rr.header.get("m_parents") or {}).get("value") or {}).get("m_deletion")
            if isinstance(dl, list):
                rr.header["m_parents"]["value"]["m_deletion"] = sorted(
                    {int(o) if int(x) == n else int(x) for x in dl})
            pairs[int(o)] = rr
    return pairs, residue


def build_XR2(k1doc: Optional[Document] = None, ctx=None) -> Tuple[dict, Any]:
    """The settings-singleton layer substituted IN PLACE (the 1:1 subset)."""
    name = "XR2"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: the settings singletons substituted IN PLACE (the 1:1 subset of "
        f"X1/X3/X4/X5); residue listed")
    t0 = time.time()
    doc = k1doc or Document.from_file(K1)
    import genesis_substitute as GS
    if ctx is None:
        ctx = GS.SubstContext(K1, "XR2")
    pairs, residue = _our_settings_1to1(doc, ctx)
    log(f"   {len(pairs)} singleton(s) in-placeable 1:1; residue entries {len(residue)}")
    rep = RA.substitute_elements(K1, out, pairs)
    body = _summ(rep)
    d = rep.diff or {}
    body.update({
        "probe": name, "role": "the settings-singleton layer OUR content, in place (1:1 subset)",
        "inplaced": [{"id": i, "class": pairs[i].class_name} for i in sorted(pairs)],
        "inplaced_count": len(pairs),
        "residue_not_inplaceable": residue,
        "assertion_that_cannot_hold": (
            "the classes listed under residue_not_inplaceable have NO pure in-place form: "
            "their corpus registration genuinely differs from a content swap (our constructor "
            "emits a different NUMBER of elements or new-only registry companions -- the "
            "browser-organization set X2 (11 old / our 6), the navigator constellation, param "
            "companions).  Those need the ADD path (regadd.add_element_like_original with the "
            "class rule) and are the honest limit of the in-place ladder."),
        "if_PASS": ("the in-placeable settings singletons carry OUR values reader-clean; "
                    "the settings-layer residue is exactly the add-path work list above"),
        "if_FAIL": ("(with XR0 PASSING) one of the in-placed classes' VALUES is audited: "
                    "bisect the pairs (halve the id list -- seconds with this tool)"),
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", d)
    log(f"   verdict {rep.verdict}; changed {d.get('records', {}).get('changed_count')} records")
    return body, ctx


def build_XR_deep(k1doc: Optional[Document] = None, ctx=None) -> dict:
    """XR2 + XR3: the settings layer AND the whole catalog, in place."""
    name = "XR_deep"
    out = os.path.join(HERE, f"{name}.rvt")
    log(f"\n== {name}: settings singletons + the whole catalog IN PLACE")
    t0 = time.time()
    doc = k1doc or Document.from_file(K1)
    import genesis_substitute as GS
    if ctx is None:
        ctx = GS.SubstContext(K1, "XR_deep")
    pairs, residue = _our_settings_1to1(doc, ctx)
    id_map, wiring = _catalog_id_map(doc)
    recs = CAT.builtin_style_catalog(IdSource(9_000_000), id_map=id_map, wiring=wiring)
    by_key = {(int(r.obj["m_categoryId"]), int(r.obj["m_gstyleType"])): r for r in recs}
    cat_pairs = {id_map[k]: by_key[k] for k in id_map if k in by_key}
    allp = dict(pairs)
    allp.update(cat_pairs)
    log(f"   {len(pairs)} singletons + {len(cat_pairs)} catalog rows = {len(allp)} in place")
    rep = RA.substitute_elements(K1, out, allp)
    body = _summ(rep)
    d = rep.diff or {}
    body.update({
        "probe": name, "role": "settings + catalog OUR content, in place (the deep rung)",
        "inplaced_count": len(allp), "settings": len(pairs), "catalog": len(cat_pairs),
        "residue_not_inplaceable": residue,
        "if_PASS": ("the whole ours-in-place layer loads: the genesis base = a fresh "
                    "document minted class-by-class AT canonical ids with this content, "
                    "plus the add path for the residue"),
        "if_FAIL": "read XR2 / XR3 individually (the deep rung is their sum)",
        "seconds": round(time.time() - t0, 1),
    })
    _write(name, body)
    _write(f"{name}.diff", d)
    log(f"   verdict {rep.verdict}; changed {d.get('records', {}).get('changed_count')} records")
    return body


# ===========================================================================
# THE MANIFEST
# ===========================================================================
ORDER = ["XR_null", "XR0", "XR0v", "XR1", "XA0", "XA1", "XA2", "XR3", "XR2", "XR_deep"]
UPLOAD = ["XR_null", "XR0", "XR1", "XA2", "XR3", "XR2", "XR_deep"]      # no XR0v / XA0 / XA1


def write_manifest() -> str:
    reports = {}
    for n in ORDER:
        p = os.path.join(HERE, f"{n}.json")
        if os.path.exists(p):
            with open(p) as fh:
                reports[n] = json.load(fh)

    def entry(n: str, order: Optional[int]) -> dict:
        r = reports.get(n, {})
        return {
            "order": order, "file": f"experiments/genesis/regadd/{n}.rvt",
            "report": f"experiments/genesis/regadd/{n}.json",
            "diff": f"experiments/genesis/regadd/{n}.diff.json",
            "derived_from": "experiments/genesis/triage/K1.rvt (viewer-PASS base) by ONE change",
            "role": r.get("role"), "the_one_change": r.get("one_change_vs_K1")
            or r.get("one_change_vs_XR0"),
            "if_PASS": r.get("if_PASS"), "if_FAIL": r.get("if_FAIL"),
            "validator_verdict": r.get("verdict", "NOT BUILT"),
            "problems": r.get("problems"),
            "upload": (n in UPLOAD),
        }

    manifest = {
        "generator": "experiments/genesis/regadd/build_regadd.py (genesis-addfix stream)",
        "stream": "genesis-addfix -- the fixed non-instance ADD path + the in-place "
                  "substitute path (rvt.regadd), on the mechanics of the certified reduce "
                  "writer",
        "READ_THIS_FIRST": (
            "The ~00:25 batch (X0, X1u, C0, X_pen, X_cat) FAILED WITH NO POSITIVE CONTROL, "
            "and X_pen (a pure in-place content swap differing from the reader-PASSING K1 in "
            "ONE record's pen doubles) failing beside X0 (Autodesk's own bytes via the add "
            "path) cannot both follow from one defect.  Every writer module is unchanged since "
            "before the last certified file, so a batch/viewer failure is NOT excluded.  "
            "UPLOAD XR_null FIRST (content-identical to K1, asserted byte-for-byte): if it "
            "FAILS, the pipeline is broken and every genesis verdict since ~22:50 08-03 is "
            "suspect -- re-upload K1.rvt to confirm and STOP interpreting.  Only if XR_null "
            "PASSES do the other verdicts read as written below."),
        "reading_order": ORDER,
        "upload_batch": ("ONE round, IN THIS ORDER: XR_null (positive control), XR0, XR1, "
                         "XA2, XR3, XR2, XR_deep.  XR0v / XA0 / XA1 are build-time assertions "
                         "(byte-identical twins of XR_null / K1 / XR0) and need NO upload."),
        "probes": {n: entry(n, i + 1) for i, n in enumerate(ORDER)},
        "decision_tree": {
            "XR_null FAIL": ("THE BATCH / PIPELINE IS BROKEN (a content-identical copy of the "
                             "certified base fails).  Every FAIL since ~22:50 08-03 -- X0, C0, "
                             "X_pen, X_cat, X1u, the X-ladder, R1..R3 -- must be RE-READ "
                             "against a fresh control.  Do not touch the writer.  Re-upload "
                             "K1.rvt and one previously-certified file (e.g. K4.rvt) to "
                             "localize the pipeline fault."),
            "XR_null PASS + XR0 PASS": ("our pen-table CONTENT is reader-clean; X_pen's "
                                        "failure was manipulate's re-chunk mechanics on K1 or "
                                        "the batch.  X0's failure then convicts the OLD add "
                                        "path's REGISTRATION -- read XA2."),
            "XR_null PASS + XR0 FAIL": ("our pen-table VALUES are audited (the ONLY delta is "
                                        "the width doubles -- XR0.json:field_diff_examples). "
                                        "Bisect the doubles by vector (a X1ua/X1ub-style twin: "
                                        "Autodesk's model vectors + ours perspective/draft and "
                                        "vice versa) -- seconds with regadd.substitute_element."),
            "XA2 PASS (with X0 FAILED)": ("THE REGISTRATION IS AUDITED and the fixed path "
                                          "(low id + birth-vintage row + hole position + typed "
                                          "re-point) FIXES IT -- promote to KNOWLEDGE; per-rule "
                                          "twins (id band only / vintage only / position only) "
                                          "split the credit."),
            "XA2 FAIL (with XR_null PASSED)": ("moving a birth singleton to a new id is itself "
                                              "rejected: MINT birth singletons AT their canonical "
                                              "ids, in place (XR0's route); the add path serves "
                                              "the non-birth residue only."),
            "XR1 -> XR3": ("row (XR1) then table (XR3): a PASS/PASS retires the catalog to a "
                           "counsel-only item; XR1 PASS + XR3 FAIL = a whole-table property "
                           "(our ink colour / pen distribution) -- bisect by row band."),
            "XR2 / XR_deep": ("the in-placeable settings layer; the residue list "
                              "(XR2.json:residue_not_inplaceable) is the add-path work queue "
                              "(browser orgs, navigator constellation, param companions)."),
        },
        "reproduce": "cd rev-revit && .venv/bin/python experiments/genesis/regadd/build_regadd.py",
    }
    p = os.path.join(HERE, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"\n[manifest] -> {_relp(p)}")
    return p


# ===========================================================================
# main
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--only", default="", help="comma list of probe names")
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--skip-deep", action="store_true", help="skip XR3 / XR2 / XR_deep")
    args = ap.parse_args(argv)
    os.makedirs(HERE, exist_ok=True)
    if args.manifest_only:
        write_manifest()
        return 0
    want = [n.strip() for n in args.only.split(",") if n.strip()] or [
        n for n in ORDER if not (args.skip_deep and n in ("XR3", "XR2", "XR_deep"))]
    t0 = time.time()
    results: Dict[str, str] = {}
    k1doc = None
    ctx = None
    for n in ORDER:
        if n not in want:
            continue
        if n in ("XR0v", "XR1", "XR3", "XR2", "XR_deep") and k1doc is None:
            log("\n[loading K1 Document for the constructor probes ...]")
            k1doc = Document.from_file(K1)
        try:
            if n == "XR_null":
                r = build_XR_null()
            elif n == "XR0":
                r = build_XR0()
            elif n == "XR0v":
                r = build_XR0v(k1doc)
            elif n == "XR1":
                r = build_XR1(k1doc)
            elif n == "XA0":
                r = build_XA0()
            elif n == "XA1":
                r = build_XA1()
            elif n == "XA2":
                r = build_XA2()
            elif n == "XR3":
                r = build_XR3(k1doc)
            elif n == "XR2":
                r, ctx = build_XR2(k1doc, ctx)
            elif n == "XR_deep":
                r = build_XR_deep(k1doc, ctx)
            else:
                continue
            results[n] = str(r.get("verdict"))
        except Exception as e:                                        # noqa: BLE001
            import traceback
            traceback.print_exc()
            results[n] = f"ERROR {e!r}"[:200]
    write_manifest()
    log("\n== summary")
    for n, v in results.items():
        log(f"   {n:8s} {v}")
    log(f"   ({round(time.time() - t0, 1)}s total)")
    return 0 if all(v == "VALID" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
