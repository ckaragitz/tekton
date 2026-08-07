#!/usr/bin/env python
"""genesis_controls.py -- THE THREE-WAY SEPARATION {ADD PATH vs OBJECT SHAPE
vs OUR VALUES}, one class at a time, every probe ONE change away from a
KNOWN-PASSING file (genesis-controls stream, 2026-08-03).

THE DIVIDE (docs/inbox/genesis-audit.md, ORCHESTRATOR VERDICTS #9): every file
whose element records are CLONED / VERBATIM / byte-exact reproductions of real
Autodesk objects LOADS in Autodesk's own reader (35+ certified: K1, R2s, L1a,
the V-line); EVERY file carrying our FROM-SCRATCH CONSTRUCTED objects (genesis
settings singletons, our catalog rows, house-standard content -- built
field-by-field over schema blanks with OUR values) FAILS with Autodesk's own
'Revit-DocumentCorruption: The file is corrupt' (+ 'Design is empty' + an
extractor crash), even on the K1 lineage (R2 / X5 / R1 / R3 FAIL) and even
after registry-parity repair.  Our validator calls every one of them VALID:
validator-clean is NOT reader-loadable.

THE INSTRUMENT.  For ONE class first -- the PenWidthTableElem (X1's class:
the smallest, best-understood settings singleton, whose constructor claims a
byte-exact reproduction of Autodesk's own table when fed Autodesk's values) --
build THREE controls, each derived from K1 (Autodesk's viewer-PASSED empty-
project skeleton, experiments/genesis/triage/K1.rvt) by exactly ONE change so
PASS/FAIL attributes cleanly, ALL through the SAME add/commit path the X-rungs
use (the substitution engine: rvt.commit.commit_new_elements + the OLD element
deleted through rvt.manipulate + the ADocument registry leaf re-pointed +
Global/Latest re-encoded byte-exactly + the canonical save-unit re-block):

  X0   K1 with its project pen table (id 2) REMOVED and the SAME Autodesk pen
       table's exact records RE-INSERTED as a NEW element (new id, its
       identity fields rebased, stamps recomputed) THROUGH OUR ADD PATH.
       PASS => the add path is sound for a settings singleton (X1's residual
       is its records' CONTENT); FAIL => the ADD PATH itself corrupts (the
       report already diffs exactly what our path wrote against K1's original
       registration: ElemTable row fields, record position, id band, registry
       leaf, identity scrub) -- and X0k (same-id re-insert, ZERO registry
       motion) bisects the path in two.
  X1v  K1 with the pen table replaced by OUR CONSTRUCTOR's output fed
       AUTODESK'S EXACT parameter values -- ASSERTED byte-identical to the
       specimen in ALL THREE seqs before emission (header + object + rep).
       Since the assertion holds, X1v's element records are byte-identical
       to X0's => X1v is a NO-UPLOAD twin of X0 (its verdict IS X0's) and the
       assertion RETIRES {shape, header, rep} for this class by construction.
       (The reproduction is NOT free: the constructor's mm interface cannot
       express 8 of the specimen's 128 pen doubles -- see FINDING P1.)
  X1u  OUR constructor with OUR width VALUES, everything structural pinned
       to the specimen (6 model scales keyed on AUTODESK's metric
       denominators 10/20/50/100/200/500, 16 pens each, perspective + draft
       vectors, m_famId -1, byte-identical header/rep): differs from X1v ONLY
       in the 128 width doubles, and from the ladder's X1 ONLY in the 6 scale
       KEYS (X1 keys our imperial 24..768 ladder).  PASS => our width VALUES
       are fine and the sole remaining variable in X1 is the scale KEYS;
       FAIL => a width VALUE is audited => the pre-built halving bisectors
       X1ua (model pens Autodesk's, perspective+draft OURS) / X1ub (model
       pens OURS, perspective+draft Autodesk's) localize it.

THEN the same three for ONE object-styles catalog row -- built-in category
-2000014 (OST_Windows) projection style, K1 row 34: ZERO referrers (host or
embedded), ONE registry leaf (CategoryTracking.m_gstyleData[*].m_gstyleId),
our new_gstyle reproduces its OBJECT byte-exactly but NOT its HEADER (flag
word 0x400001e vs the specimen's 0x400201e -- ONE bit, 0x2000):

  C0   row 34 removed + Autodesk's exact records re-inserted at a new id
       through our add path (CategoryTracking leaf re-pointed).  PASS => the
       add path is fine for a catalog row (compare with X0: both FAIL => the
       path generally; only one => the class-specific registration).
  C1v  our new_gstyle fed the row's exact values: object + rep byte-
       identical (ASSERTED), header differing from Autodesk's in EXACTLY the
       flag bit 0x2000.  PASS => our header preset is tolerated (then C1u
       reads); FAIL with C0 PASS => the ElementHeader flag word IS audited
       for object-style rows.
  C1u  our catalog constructor's LITERAL row for this category (our
       discipline pen 1 / colour 0x181818 vs Autodesk's pen 2 / colour 0):
       differs from C1v ONLY in the two values -- exactly the row X6a / R2
       shipped for OST_Windows.  PASS with C1v PASS => the single-row
       substitution is fully exonerated and R2's failure is a WHOLE-CATALOG
       effect => C0all (all 1,348 referrer-free built-in rows re-inserted
       verbatim at new ids through our path) is the pre-built next probe.

Every emitted file: validator 0 errors, structural proof, registry parity
100 %, four-registry coherent, 0 NEW dangling ids (the substitution engine's
certification), with the byte-identity ASSERTIONS recorded in its .json.

FINDINGS this stream established (see docs/inbox/genesis-controls.md):
  P1  The pen table's stored doubles are NOT `mm / 304.8` of the displayed mm
      values: the naive parametric reproduction (feed feet*304.8 back in)
      loses the last mantissa bit on the eight 9.0-mm pens, and NO mm input
      divided by 304.8 can reach the stored double 0.029527559055118106
      (searched +-2000 ulps).  `pen_width_table` therefore CANNOT reproduce
      its specimen byte-exact from mm values (the constellation's byte-exact
      test is a self-round-trip, not identity-with-specimen); fed exact FEET
      it reproduces header, object AND rep byte-exactly.
  P2  For the pen table {header, rep} are Autodesk-identical by
      construction => X1v collapses onto X0; the ONLY variables X1 changes vs
      the accepted specimen are the width VALUES and the scale KEYS.
  G1  Built-in object-style rows do NOT share one ElementHeader flag word:
      SIX distinct m_abFlags4Bytes presets (0x400081e 645 / 0x400200e 492 /
      0x400080e 145 / 0x400201e 79 / 0x400000e 31 / 0x400001e 15 rows on
      K1) and 790 of 1,407 rows carry a CellList{PatternHelper}; our
      new_gstyle emits the single preset 0x400001e + a null cell list, so it
      reproduces only 15 / 1,407 rows completely (object 617, header 15).
  G2  ...but the flag word and the cell-list presence are NOT per-category
      format constants: they DISAGREE across rst / rme / rac for 916 of the
      1,407 (category, style-type) keys -- per-document history artefacts,
      every combination reader-accepted somewhere.  Our combination
      (0x400001e + no cell list) itself occurs in accepted files.  => the
      per-row header/cell divergence is a WEAK candidate for R2's failure,
      which shifts weight onto the catalog-SCALE add path (C0all) and the
      un-uploaded mechanics control R2s.

Territory: tools/genesis_controls.py, experiments/genesis/controls/*,
tests/test_genesis_controls.py, docs/inbox/genesis-controls.md.  Every
dependency (the substitution engine tools/genesis_substitute.py, rvt.commit /
manipulate / reduce / adocument / encode / objects, rvt.genesis.settings /
catalog / types) is IMPORTED, never edited.  No viewer here: the probes are
left on disk with probes.json (the reading tree) for the orchestrator.

Usage:
  .venv/bin/python tools/genesis_controls.py                    # the six controls
  .venv/bin/python tools/genesis_controls.py --with-optional    # + C0all, X0k, X1ua, X1ub
  .venv/bin/python tools/genesis_controls.py --only X0,C1v      # some probes
  .venv/bin/python tools/genesis_controls.py --findings-only    # the census / analysis json
  .venv/bin/python tools/genesis_controls.py --manifest-only    # re-write probes.json
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import genesis_substitute as GS                                     # noqa: E402  (the X-rung engine)
import rvt_reduce as RR                                            # noqa: E402
from rvt import adocument as adoc                                   # noqa: E402
from rvt import stream_encoders as se                               # noqa: E402
from rvt.commit import commit_new_elements, verify_written          # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.encode import record_bytes, first_divergence               # noqa: E402
from rvt.genesis import settings as ST                              # noqa: E402
from rvt.genesis import catalog as CAT                              # noqa: E402
from rvt.genesis import types as GT                                 # noqa: E402
from rvt.genesis.types import (INVALID, IdSource, TypeRecord,       # noqa: E402
                               LINEPATTERN_SOLID, class_id)
from rvt.mutate import Document, ElemRecPlan                        # noqa: E402
from rvt.objects import ObjectDecoder, iter_records                # noqa: E402
from rvt.partitions import StreamWalker                              # noqa: E402
from rvt.reduce import delete_elements, verify_reduced              # noqa: E402

CONTROLS = os.path.join(ROOT, "experiments", "genesis", "controls")
K1 = GS.K1                                            # experiments/genesis/triage/K1.rvt
PEN_OLD_ID = 2                                        # the project pen table in every 2026 file
CAT_OLD_ID = 34                                       # OST_Windows (-2000014) projection style row
CAT_CATEGORY = -2000014
CAT_STYLE_TYPE = 1
os.makedirs(CONTROLS, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


# ===========================================================================
# 1. SPECIMEN ACCESS -- the exact framed records of an element in a file
# ===========================================================================

class SpecRecord:
    """One seq's record of an element: the walker record, its ORIGINAL framed
    bytes (header + payload + trailer), the schema-decoded value."""
    __slots__ = ("seq", "class_id", "class_name", "framed", "value", "payload_len")

    def __init__(self, seq, class_id, class_name, framed, value, payload_len):
        self.seq = seq
        self.class_id = class_id
        self.class_name = class_name
        self.framed = framed
        self.value = value
        self.payload_len = payload_len


def unit0_segments(path: str) -> Dict[int, bytes]:
    """{seq: concatenated save-unit-0 record stream} of the host document."""
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"{path}: walker errors {w.errors[:2]}")
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        return {s: b"".join(b.data for b in u0 if b.seq == s) for s in (101, 102, 103)}


def specimen_records(path: str, eid: int,
                     segments: Optional[Dict[int, bytes]] = None) -> Dict[int, SpecRecord]:
    """{seq: SpecRecord} for element ``eid`` -- all three seqs must exist."""
    segs = segments or unit0_segments(path)
    dec = ObjectDecoder()
    out: Dict[int, SpecRecord] = {}
    for seq in (101, 102, 103):
        for r in iter_records(segs[seq], seq):
            if r.elem_id == eid:
                framed = bytes(record_bytes(segs[seq], r, seq))
                got = dec.decode_record(r.class_id, r.payload) if r.body_size >= 2 else None
                if got is not None and not got.clean:
                    raise RuntimeError(f"{path}: id {eid} seq {seq} decode not clean: "
                                       f"{got.errors[:1]}")
                out[seq] = SpecRecord(seq, r.class_id, dec.class_name(r.class_id),
                                      framed, (got.value if got is not None else {}),
                                      r.body_size)
                break
    if len(out) != 3:
        raise RuntimeError(f"{path}: id {eid} does not have all three seq records "
                           f"(found {sorted(out)})")
    return out


def byte_compare(ours: bytes, spec: bytes, *, limit: int = 24) -> dict:
    """A byte-identity report: identical flag, first divergence, differing
    offsets, and hex context at the first divergence."""
    n = min(len(ours), len(spec))
    diffs = [i for i in range(n) if ours[i] != spec[i]]
    if len(ours) != len(spec):
        diffs.append(n)
    rep: Dict[str, Any] = {
        "identical": ours == spec, "len_ours": len(ours), "len_specimen": len(spec),
        "differing_bytes": len([d for d in diffs if d < n]) + abs(len(ours) - len(spec)),
        "first_divergence": (diffs[0] if diffs else -1),
        "differing_offsets": diffs[:limit],
    }
    if diffs:
        i = diffs[0]
        lo = max(0, i - 8)
        rep["specimen_hex_at_divergence"] = spec[lo:i + 16].hex(" ")
        rep["ours_hex_at_divergence"] = ours[lo:i + 16].hex(" ")
    return rep


def _digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


# ===========================================================================
# 2. VERBATIM records: Autodesk's own bytes as a "new element" (X0 / C0 / C0all)
# ===========================================================================

def verbatim_typerecord(spec: Dict[int, SpecRecord], class_name: str, new_id: int,
                        ted: "GS.TypedEditor", *, kind: str) -> Tuple[TypeRecord, dict]:
    """Autodesk's EXACT element as a TypeRecord ready for our add path.

    PROOF FIRST: build the TypeRecord over the specimen's DECODED dicts at the
    element's ORIGINAL id and require its encoding to equal the ORIGINAL
    framed bytes byte-for-byte in ALL THREE seqs (the record is genuinely
    Autodesk's, re-serialized by our byte-exact codec).  Only then REBASE the
    element's identity to ``new_id`` (the schema-typed remap of exactly the
    ElementId leaves holding the old id: ``Element.m_id`` in the object and
    the element's own entry in ``ElementParents.m_deletion`` in the header --
    nothing else changes; the stamps recompute mechanically because
    stamp = adler32(class || body)).  The seq-103 representation must be an
    empty SerializedDummy (asserted).
    """
    old_id = int(spec[102].value.get("m_id"))
    if spec[103].class_name != "SerializedDummy" or spec[103].payload_len not in (0, 2):
        raise RuntimeError(f"{class_name} id {old_id}: seq-103 rep is {spec[103].class_name} "
                           f"payload {spec[103].payload_len} (expected an empty SerializedDummy)")
    obj = copy.deepcopy(spec[102].value)
    hdr = copy.deepcopy(spec[101].value)
    t_orig = TypeRecord(old_id, kind, class_name, class_id(class_name), INVALID,
                        obj, hdr, None)
    enc = t_orig.encode()
    proof = {"element": old_id, "class": class_name,
             "verbatim_identity_at_original_id": {
                 str(s): byte_compare(enc[s], spec[s].framed) for s in (101, 102, 103)},
             }
    proof["all_three_seqs_identical"] = all(
        v["identical"] for v in proof["verbatim_identity_at_original_id"].values())
    if not proof["all_three_seqs_identical"]:
        raise RuntimeError(f"{class_name} id {old_id}: decode->encode is NOT byte-exact "
                           f"({proof['verbatim_identity_at_original_id']}) -- refusing "
                           f"to call this a verbatim insert")
    # rebase the element's own identity to the new id (typed leaves only)
    mapping = {old_id: int(new_id)}
    e_obj = ted.remap(obj, class_name, mapping)
    e_hdr = ted.remap(hdr, "ElementHeader", mapping)
    if obj.get("m_id") != int(new_id):                 # belt & braces
        obj["m_id"] = int(new_id)
    proof["identity_rebased_leaves"] = {
        "object": [GS.normalize_surface_path(e["path"]) for e in e_obj],
        "header": [GS.normalize_surface_path(e["path"]) for e in e_hdr]}
    proof["new_id"] = int(new_id)
    rec = TypeRecord(int(new_id), kind, class_name, class_id(class_name), INVALID,
                     obj, hdr, None,
                     refs={"specimen_id": old_id, "verbatim": True},
                     notes=[f"Autodesk's exact {class_name} id {old_id} (all 3 seqs "
                            f"byte-identical at the original id), identity rebased "
                            f"{old_id}->{new_id} on typed leaves only"])
    return rec, proof


# ===========================================================================
# 3. PEN TABLE analysis + our-constructor renditions
# ===========================================================================

def pen_specimen_table(spec_value: dict) -> dict:
    """The decoded PenWidthTable of the specimen (feet doubles)."""
    return spec_value["m_pPenWidthTable"]["value"]


def pen_exact_feet(spec_value: dict) -> Tuple[Dict[int, List[float]], List[float], List[float]]:
    """({scale-key: [16 feet]}, perspective[16 feet], draft[16 feet]) exactly
    as stored in the specimen."""
    t = pen_specimen_table(spec_value)
    model = {int(p["m_invertedScale"]): [float(x) for x in p["m_pens"]]
             for p in t["m_modelPenInfo"]}
    persp = [float(x) for x in t["m_perspectiveModelPenInfo"]["m_pens"]]
    draft = [float(x) for x in t["m_draftPenInfo"]["m_pens"]]
    return model, persp, draft


def our_pen_table_from_feet(elem_id: int, model_feet: Dict[int, Sequence[float]],
                            persp_feet: Sequence[float],
                            draft_feet: Sequence[float]) -> TypeRecord:
    """OUR pen_width_table constructor (blank_object + field-by-field build +
    our header machinery + SerializedDummy rep) fed EXACT FEET values.

    The constructor's public interface is millimetres and divides by 304.8;
    since the specimen's doubles are NOT mm/304.8-derived (FINDING P1), the
    only honest exact-value feed is to build the structure through the
    constructor and set the pen doubles to the exact feet -- the constructor's
    own object, exact values.  Counts / keys / flags all come from the
    constructor's arguments (nothing else is patched)."""
    mm = ST.MM_PER_FT
    rec = ST.pen_width_table(
        elem_id=int(elem_id),
        model_pens_mm={int(s): [x * mm for x in v] for s, v in model_feet.items()},
        perspective_pens_mm=[x * mm for x in persp_feet],
        annotation_pens_mm=[x * mm for x in draft_feet])
    t = rec.obj["m_pPenWidthTable"]["value"]
    for mine in t["m_modelPenInfo"]:
        mine["m_pens"] = [float(x) for x in model_feet[int(mine["m_invertedScale"])]]
    t["m_perspectiveModelPenInfo"]["m_pens"] = [float(x) for x in persp_feet]
    t["m_draftPenInfo"]["m_pens"] = [float(x) for x in draft_feet]
    rec.notes.append("pen doubles set to the EXACT specimen feet (the mm interface "
                     "cannot express 8 of them: FINDING P1)")
    return rec


def pen_naive_mm_render(elem_id: int, spec_value: dict) -> TypeRecord:
    """OUR constructor fed the specimen's values THROUGH ITS PUBLIC mm
    INTERFACE (feet * 304.8) -- the naive parametric reproduction the
    settings tests perform.  Used to MEASURE finding P1, never emitted."""
    model, persp, draft = pen_exact_feet(spec_value)
    mm = ST.MM_PER_FT
    return ST.pen_width_table(
        elem_id=int(elem_id),
        model_pens_mm={s: [x * mm for x in v] for s, v in model.items()},
        perspective_pens_mm=[x * mm for x in persp],
        annotation_pens_mm=[x * mm for x in draft])


def pen_value_analysis(spec_value: dict) -> dict:
    """FINDING P1's evidence: which stored doubles the mm interface cannot
    reproduce, whether ANY mm input divided by 304.8 reaches them, and the
    per-vector layout of the table (counts / keys)."""
    import math
    t = pen_specimen_table(spec_value)
    vectors: List[Tuple[str, List[float]]] = (
        [(f"model[1:{p['m_invertedScale']}]", list(p["m_pens"])) for p in t["m_modelPenInfo"]]
        + [("perspective", list(t["m_perspectiveModelPenInfo"]["m_pens"])),
           ("draft(annotation)", list(t["m_draftPenInfo"]["m_pens"]))])
    non_rt = []
    for name, vec in vectors:
        for j, x in enumerate(vec):
            if (x * ST.MM_PER_FT) / ST.MM_PER_FT != x:
                non_rt.append({"vector": name, "pen_index": j, "stored_feet": repr(x),
                               "displayed_mm": round(x * ST.MM_PER_FT, 6)})
    unreachable: Dict[str, bool] = {}
    for f in sorted({d["stored_feet"] for d in non_rt}):
        x = float(f)
        m0 = x * ST.MM_PER_FT
        hit = False
        for k in range(0, 4000):
            for cand in (m0 + k * math.ulp(m0), m0 - k * math.ulp(m0)):
                if cand / ST.MM_PER_FT == x:
                    hit = True
                    break
            if hit:
                break
        unreachable[f] = not hit
    distinct = sorted({round(x * ST.MM_PER_FT, 6) for _n, v in vectors for x in v})
    return {
        "model_scale_keys": [int(p["m_invertedScale"]) for p in t["m_modelPenInfo"]],
        "pens_per_vector": ST.PEN_COUNT,
        "vectors": [n for n, _v in vectors],
        "total_doubles": sum(len(v) for _n, v in vectors),
        "distinct_displayed_mm": distinct,
        "non_roundtripping_doubles": non_rt,
        "non_roundtripping_count": len(non_rt),
        "stored_double_unreachable_from_any_mm_input": unreachable,
        "verdict": ("the pen table's stored doubles are NOT mm/304.8-derived: the "
                    "naive parametric reproduction (feet*304.8 fed back into the mm "
                    "interface) loses the last mantissa bit on the doubles listed, and "
                    "for those no mm double divided by 304.8 lands on the stored value "
                    "-- the constructor cannot express them; the settings stream's "
                    "'byte-exact' reproduction test proves a self-round-trip "
                    "(encode->decode->encode of OUR value), not identity with the specimen"),
    }


# ===========================================================================
# 4. CATALOG (GStyle) census -- FINDINGS G1 / G2
# ===========================================================================

def _builtin_gstyle_rows(path: str):
    """Yield (eid, category, style_type, value(102), header(101)) for every
    HOST built-in object-style row (m_famId -1, built-in category id)."""
    doc = Document.from_file(path)
    segs = unit0_segments(path)
    dec = ObjectDecoder()
    idx: Dict[int, Dict[int, Any]] = collections.defaultdict(dict)
    for s in (101, 102):
        for r in iter_records(segs[s], s):
            idx[r.elem_id][s] = r
    for eid in sorted(doc.ids_of_class("GStyleElem")):
        recs = idx.get(eid) or {}
        if 102 not in recs or 101 not in recs:
            continue
        v = dec.decode_record(recs[102].class_id, recs[102].payload).value
        if int(v.get("m_famId", -1)) != -1:
            continue
        cid = v.get("m_categoryId")
        if not (isinstance(cid, int) and cid < 0):
            continue
        h = dec.decode_record(recs[101].class_id, recs[101].payload).value
        framed = {s: bytes(record_bytes(segs[s], recs[s], s)) for s in (101, 102)}
        yield eid, int(cid), int(v.get("m_gstyleType", 1)), v, h, framed


def catalog_shape_census(path: str = K1) -> dict:
    """FINDING G1: the built-in object-style rows' HEADER flag words and CELL
    LISTS on the passing skeleton, and how many rows our new_gstyle
    reproduces byte-exactly when fed each row's exact values."""
    flags = collections.Counter()
    cell = collections.Counter()
    cell_x_pattern = collections.Counter()
    cell_classes = collections.Counter()
    universal = {"header_categoryId_-1": 0, "header_vis_-32768": 0,
                 "header_appearance_empty": 0}
    obj_ident = hdr_ident = both = 0
    rows = 0
    obj_fail_examples: List[dict] = []
    hdr_fail_words = collections.Counter()
    flags_by_type = collections.Counter()
    for eid, cid, gt, v, h, framed in _builtin_gstyle_rows(path):
        rows += 1
        a = int(h.get("m_abFlags4Bytes"))
        flags[a] += 1
        flags_by_type[(a, gt)] += 1
        cl = v.get("m_cellList")
        cell[cl is not None] += 1
        if cl is not None:
            for c in (cl.get("value", {}).get("m_cells") or []):
                cell_classes[str(c.get("ptr_class"))] += 1
        g = (v.get("m_pGStyle") or {}).get("value") or {}
        cell_x_pattern[(cl is not None, g.get("m_linePatternId") == -1)] += 1
        universal["header_categoryId_-1"] += int(h.get("m_categroryId") == -1)
        universal["header_vis_-32768"] += int(
            (h.get("m_viewRules") or {}).get("m_nVisibleViewFlags") == -32768)
        universal["header_appearance_empty"] += int(
            not (h["m_parents"]["value"].get("m_appearanceParents") or []))
        ours = GT.new_gstyle(cid, style_type=("cut" if gt == 2 else "projection"),
                             pen=int(g.get("m_penNumber", 1)), color=int(g.get("m_color", 0)),
                             line_pattern_id=int(g.get("m_linePatternId", -1)),
                             material_id=int(g.get("m_materialElemId", -1)),
                             owner_id=int(v.get("m_ownerId", -1)),
                             screen_sized=bool(g.get("m_isScreenSized", False)),
                             elem_id=eid)
        enc = ours.encode()
        oi = enc[102] == framed[102]
        hi = enc[101] == framed[101]
        obj_ident += oi
        hdr_ident += hi
        both += (oi and hi)
        if not oi and len(obj_fail_examples) < 6:
            obj_fail_examples.append({"row": eid, "category": cid, "style_type": gt,
                                      "cellList_present": cl is not None})
        if not hi:
            hdr_fail_words[hex(a)] += 1
    return {
        "file": _relp(path),
        "builtin_rows": rows,
        "header_abFlags4Bytes_histogram": {hex(k): n for k, n in flags.most_common()},
        "header_abFlags_x_styletype": {f"{hex(a)}|type{t}": n
                                       for (a, t), n in flags_by_type.most_common()},
        "our_new_gstyle_header_preset": hex(int(_our_gstyle_header_word())),
        "cellList_present_rows": int(cell[True]), "cellList_null_rows": int(cell[False]),
        "cellList_cell_classes": dict(cell_classes),
        "cellList_x_pattern_is_null_crosstab": {
            f"cell={a}|pattern_-1={b}": n for (a, b), n in cell_x_pattern.items()},
        "universal_fields_confirmed_all_rows": universal,
        "our_reproduction_fed_exact_values": {
            "object_byte_identical_rows": obj_ident,
            "header_byte_identical_rows": hdr_ident,
            "fully_identical_rows": both,
            "object_divergence_cause": "our null m_cellList vs the specimen's "
                                       "CellList{PatternHelper} (present on exactly the "
                                       "non-identical rows)",
            "header_divergence_words_where_not_identical": dict(hdr_fail_words),
            "object_non_identical_examples": obj_fail_examples,
        },
    }


def _our_gstyle_header_word() -> int:
    """The single ElementHeader flag word our new_gstyle emits for a
    built-in object-style row (its 'GStyleElem:objectstyle' preset)."""
    rec = GT.new_gstyle(CAT_CATEGORY, style_type="projection", pen=1, elem_id=1)
    return int(rec.header.get("m_abFlags4Bytes"))


def cross_sample_shape_constancy(samples: Sequence[str] = ("rstbasicsampleproject",
                                                            "rmebasicsampleproject",
                                                            "racbasicsampleproject")) -> dict:
    """FINDING G2: is the built-in row's (flag word, cell-list presence) a
    per-(category, style-type) FORMAT CONSTANT across accepted samples?  It
    is NOT: they disagree per document.  Requires the extracted corpus."""
    per: Dict[str, Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], bool]]] = {}
    for s in samples:
        doc = Document.load(s)
        m: Dict[Tuple[int, int], int] = {}
        c: Dict[Tuple[int, int], bool] = {}
        for eid in doc.ids_of_class("GStyleElem"):
            v = doc.value(eid) or {}
            if int(v.get("m_famId", -1)) != -1:
                continue
            cid = v.get("m_categoryId")
            if not (isinstance(cid, int) and cid < 0):
                continue
            gt = int(v.get("m_gstyleType", 1))
            try:
                h = doc.decode(eid, 101).value
            except Exception:                          # pragma: no cover
                continue
            m[(int(cid), gt)] = int(h.get("m_abFlags4Bytes"))
            c[(int(cid), gt)] = (v.get("m_cellList") is not None)
        per[s] = (m, c)
    keys = set.intersection(*[set(m) for m, _c in per.values()])
    flag_agree = [k for k in keys if len({per[s][0][k] for s in per}) == 1]
    cell_agree = [k for k in keys if len({per[s][1][k] for s in per}) == 1]
    disagree_examples = []
    for k in sorted(k for k in keys if len({per[s][0][k] for s in per}) > 1)[:8]:
        disagree_examples.append({"key": list(k), **{s: hex(per[s][0][k]) for s in per}})
    return {
        "samples": list(samples),
        "common_keys": len(keys),
        "flag_word_identical_across_samples": len(flag_agree),
        "cellList_presence_identical_across_samples": len(cell_agree),
        "flag_word_disagreeing": len(keys) - len(flag_agree),
        "cellList_disagreeing": len(keys) - len(cell_agree),
        "flag_disagreement_examples": disagree_examples,
        "verdict": ("the built-in object-style row's ElementHeader flag word (bits "
                    "0x10 / 0x800 / 0x2000) and its CellList{PatternHelper} are NOT "
                    "per-category format constants -- the same (category, type) row "
                    "carries different combinations in different accepted files "
                    "(per-document creation-history artefacts); every combination our "
                    "constructor emits also occurs somewhere in accepted files"),
    }


# ===========================================================================
# 5. PEN-TABLE RUNG BUILDERS (X0 / X1v / X1u [/ X1ua / X1ub])
# ===========================================================================

def _pen_specimen(ctx: "GS.SubstContext") -> Dict[int, SpecRecord]:
    spec = specimen_records(ctx.parent, PEN_OLD_ID)
    v = spec[102].value
    if spec[102].class_name != "PenWidthTableElem" or int(v.get("m_famId", -1)) != -1:
        raise RuntimeError(f"element {PEN_OLD_ID} of {ctx.parent} is not the project pen "
                           f"table (class {spec[102].class_name}, famId {v.get('m_famId')})")
    return spec


def _pen_common_info(ctx, spec, new_id: int) -> dict:
    """The registry / ElemTable facts shared by the pen probes (what our
    add path writes vs K1's original registration)."""
    surf = GS.adoc_surface(ctx.ted_adoc, ctx.tree, [PEN_OLD_ID]).get(PEN_OLD_ID, [])
    et_row = _elemtable_row(ctx.parent, PEN_OLD_ID)
    inb = ctx.inbound(PEN_OLD_ID)
    return {
        "specimen_element": PEN_OLD_ID,
        "specimen_registry_surface": surf,
        "specimen_referrers": {"total": len(inb),
                               "host": len([r for r in inb if r in ctx.host]),
                               "embedded": len([r for r in inb if r not in ctx.host])},
        "specimen_elemtable_row": et_row,
        "our_add_path_writes": {
            "new_id": int(new_id), "id_band": f">= {ctx.id_start:,} (parent watermark + 100k band)",
            "elemtable_row": ("(original_id = new id, creation_ep = modified_ep = "
                              "user_modified_ep = the parent's max modified episode, "
                              "owner -1, partition 0) -- rvt.commit.commit_new_elements"),
            "record_position": ("the three records are APPENDED before each seq's sentinel "
                                "(end of unit 0), whereas the specimen's records sit "
                                "mid-stream (position 2,516 of 6,541 in seq 102)"),
            "registry": "PenWidthTableInfo.m_penWidthTableElemId re-pointed old -> new "
                        "(same slot, same body; Global/Latest re-encoded byte-exactly)",
            "identity_scrub": ("BasicFileInfo author/username -> 'rvt-writer' (document "
                               "GUID kept), DocumentIncrementTable usernames scrubbed -- "
                               "the V30/V31/V32-proven identity path of commit_new_elements"),
            "reblock": "canonical save-unit-0 re-block (rvt.reduce.delete_elements(., ., []))",
        },
    }


def _elemtable_row(path: str, eid: int) -> dict:
    with open_rvt(path) as f:
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
    for row in et["records"]:
        if int(row[4]) == int(eid):
            own = row[5]
            return {"elem_id": int(row[4]), "original_id": int(row[0]),
                    "creation_ep": int(row[1]), "modified_ep": int(row[2]),
                    "user_modified_ep": int(row[3]),
                    "owner_id": (int(own) if isinstance(own, int) and own < (1 << 63) else -1),
                    "partition_id": int(row[6]) if len(row) > 6 else 0}
    return {}


def build_X0(ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """X0 -- the ADD-PATH control: Autodesk's own pen table, verbatim,
    re-inserted as a NEW element through OUR add path."""
    spec = _pen_specimen(ctx)
    new_id = ctx.ids.next_id()
    rec, proof = verbatim_typerecord(spec, "PenWidthTableElem", new_id, ctx.ted,
                                     kind="pen-table-verbatim")
    info = {"probe": "X0", "role": "ADD PATH control (content held byte-identical)",
            "byte_identity_assertion": proof,
            **_pen_common_info(ctx, spec, new_id)}
    return GS.SubstBuild(old_ids=[PEN_OLD_ID], records=[rec], corr={PEN_OLD_ID: new_id},
                         notes=["Autodesk's EXACT pen table (all 3 seqs byte-identical at "
                                f"id {PEN_OLD_ID}) re-inserted as new element {new_id} "
                                "through the X-rung add path"],
                         info=info)


def build_X1v(ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """X1v -- OUR CONSTRUCTOR fed AUTODESK'S EXACT values: byte-identity of
    header + object + rep ASSERTED, so X1v's records equal X0's (a no-upload
    twin).  Also records FINDING P1 (the naive mm feed is NOT byte-exact)."""
    spec = _pen_specimen(ctx)
    model, persp, draft = pen_exact_feet(spec[102].value)
    # (a) the assertion at the ORIGINAL id: our constructor + exact feet
    ours_orig = our_pen_table_from_feet(PEN_OLD_ID, model, persp, draft)
    enc = ours_orig.encode()
    ident = {str(s): byte_compare(enc[s], spec[s].framed) for s in (101, 102, 103)}
    all_ident = all(v["identical"] for v in ident.values())
    # (b) FINDING P1: the naive mm-interface reproduction is NOT byte-exact
    naive = pen_naive_mm_render(PEN_OLD_ID, spec[102].value).encode()
    naive_cmp = {str(s): byte_compare(naive[s], spec[s].framed) for s in (101, 102, 103)}
    if not all_ident:
        raise RuntimeError("X1v: our pen constructor does NOT reproduce the specimen "
                           f"byte-exactly even fed exact feet: {ident} -- HEADLINE "
                           "FINDING (records the divergence, emits nothing)")
    new_id = ctx.ids.next_id()
    ours = our_pen_table_from_feet(new_id, model, persp, draft)
    ours.kind = "pen-table-our-constructor-exact-values"
    # (c) collapse proof: our record at the new id == Autodesk's verbatim
    #     record rebased to the same id (X0's records), byte for byte
    verb, _p = verbatim_typerecord(spec, "PenWidthTableElem", new_id, ctx.ted,
                                   kind="pen-table-verbatim")
    a, b = ours.encode(), verb.encode()
    collapse = {str(s): byte_compare(a[s], b[s]) for s in (101, 102, 103)}
    info = {
        "probe": "X1v", "role": "OBJECT SHAPE / header / rep control (values exact)",
        "byte_identity_assertion": {
            "our_constructor_fed_exact_feet_vs_specimen_at_original_id": ident,
            "all_three_seqs_identical": all_ident,
        },
        "collapse_onto_X0": {
            "our_records_vs_X0_verbatim_records_at_new_id": collapse,
            "records_identical": all(v["identical"] for v in collapse.values()),
            "statement": ("X1v's three element records are byte-identical to X0's => the "
                          "element streams of X1v and X0 are content-identical (verified "
                          "post-build by stream digest); X1v needs NO viewer upload -- its "
                          "verdict IS X0's.  What X1v proves is proven at BUILD time: for "
                          "PenWidthTableElem our constructor's {object shape, header "
                          "(abFlags 8222 / vis -32768 / deletion [self] / no wildcards / "
                          "no regenOnly), rep (empty SerializedDummy)} are Autodesk-"
                          "identical, so the ONLY things the ladder's X1 changes vs the "
                          "accepted specimen are the width VALUES and the scale KEYS."),
        },
        "finding_P1_naive_mm_interface_not_byte_exact": {
            "our_constructor_fed_feet_times_304.8_vs_specimen": naive_cmp,
            "analysis": pen_value_analysis(spec[102].value),
        },
        **_pen_common_info(ctx, spec, new_id),
    }
    return GS.SubstBuild(old_ids=[PEN_OLD_ID], records=[ours], corr={PEN_OLD_ID: new_id},
                         notes=["our pen_width_table fed Autodesk's EXACT values (feet); "
                                "header/object/rep asserted byte-identical to the specimen; "
                                "records byte-identical to X0's (collapse proven)"],
                         info=info)


def _spec_scale_keys(spec_value: dict) -> List[int]:
    return [int(p["m_invertedScale"]) for p in pen_specimen_table(spec_value)["m_modelPenInfo"]]


def _pen_field_diff(ours_obj: dict, spec_obj: dict) -> List[dict]:
    """Field-level diff of two decoded pen-table objects (floats compared as
    exact doubles -- the values ARE the point)."""
    out: List[dict] = []

    def rec(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if k not in a or k not in b:
                    out.append({"path": f"{path}.{k}", "ours": a.get(k, "<absent>"),
                                "specimen": b.get(k, "<absent>")})
                else:
                    rec(a[k], b[k], f"{path}.{k}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                out.append({"path": f"{path}[len]", "ours": len(a), "specimen": len(b)})
            for i, (x, y) in enumerate(zip(a, b)):
                rec(x, y, f"{path}[{i}]")
        else:
            if a != b:
                out.append({"path": path, "ours": a, "specimen": b})
    rec(ours_obj, spec_obj, "")
    return out


def build_X1u(ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """X1u -- OUR width VALUES with everything structural pinned to the
    specimen (Autodesk's 6 metric scale KEYS, 16 pens each, our header/rep
    already Autodesk-identical): differs from X1v ONLY in the 128 doubles,
    from the ladder's X1 ONLY in the 6 scale keys."""
    spec = _pen_specimen(ctx)
    keys = _spec_scale_keys(spec[102].value)
    new_id = ctx.ids.next_id()
    ours = ST.pen_width_table(elem_id=new_id,
                              model_pens_mm=ST.default_model_pens_mm(scales=tuple(keys)),
                              perspective_pens_mm=ST.pen_series_mm(0),
                              annotation_pens_mm=ST.pen_series_mm(0))
    ours.kind = "pen-table-our-values-specimen-keys"
    # structural pins vs the specimen: identical counts / keys / flags,
    # header + rep byte-identical, ONLY the doubles differ
    diffs = _pen_field_diff(ours.obj, spec[102].value)
    hdr_cmp = byte_compare(ours.encode()[101],
                           # compare header shape modulo the id: rebuild spec at our id
                           _reid_header(spec[101], PEN_OLD_ID, new_id, ctx.ted))
    non_double_diffs = [d for d in diffs if not (isinstance(d.get("ours"), float)
                                                 and isinstance(d.get("specimen"), float))
                        and d["path"] != ".m_id"]
    # the ladder's X1 (our default breakpoints) for the X1u -> X1 delta
    x1 = ST.pen_width_table(elem_id=new_id)
    x1_delta = _pen_field_diff(x1.obj, ours.obj)
    info = {
        "probe": "X1u", "role": "OUR VALUES with the specimen's counts / keys / flags pinned",
        "structural_pins": {
            "model_scale_keys": keys, "model_scale_count": len(keys),
            "pens_per_vector": ST.PEN_COUNT, "vectors": ["model x6", "perspective", "draft"],
            "m_famId": -1, "header_byte_identical_to_specimen": hdr_cmp["identical"],
            "rep": "SerializedDummy (empty) -- identical",
        },
        "our_values": {
            "model_pens_mm_per_scale_key": {str(k): [round(x, 4) for x in v]
                                            for k, v in ST.default_model_pens_mm(
                                                scales=tuple(keys)).items()},
            "perspective_pens_mm": [round(x, 4) for x in ST.pen_series_mm(0)],
            "draft_pens_mm": [round(x, 4) for x in ST.pen_series_mm(0)],
            "source": "OUR ISO-128-based line-weight series (rvt.genesis.settings "
                      "PEN_WIDTHS_MM), coarser scale key = one more leading hairline "
                      "(the specimen's own shift direction)",
        },
        "diff_vs_specimen": {
            "total_field_differences": len(diffs),
            "non_double_differences": non_double_diffs,       # must be [] (only doubles differ)
            "only_the_pen_doubles_differ": non_double_diffs == [],
            "double_differences": len([d for d in diffs
                                       if isinstance(d.get("ours"), float)]),
        },
        "diff_vs_ladder_X1": {
            "explanation": ("the ladder's X1 (experiments/genesis/subst/X1.rvt) is OUR "
                            "constructor with OUR values AND OUR imperial scale keys "
                            f"{ST.PEN_SCALE_BREAKPOINTS}; X1u keeps the specimen's metric "
                            f"keys {keys} -- so X1u -> X1 changes ONLY the six "
                            "m_invertedScale keys (both key sets have 6 entries, both use "
                            "our shifted width series per key)"),
            "field_differences": [d for d in x1_delta if "m_invertedScale" in d["path"]],
        },
        **_pen_common_info(ctx, spec, new_id),
    }
    return GS.SubstBuild(old_ids=[PEN_OLD_ID], records=[ours], corr={PEN_OLD_ID: new_id},
                         notes=["OUR width values over the specimen's exact structure "
                                f"(scale keys {keys}, 16 pens x (6+2) vectors)"],
                         info=info)


def _reid_header(spec101: SpecRecord, old_id: int, new_id: int,
                 ted: "GS.TypedEditor") -> bytes:
    """The specimen's seq-101 header re-encoded with its own-id entry rebased
    to ``new_id`` (so a header built by our constructor at ``new_id`` can be
    byte-compared against it)."""
    from rvt.encode import encode_record
    h = copy.deepcopy(spec101.value)
    ted.remap(h, "ElementHeader", {int(old_id): int(new_id)})
    return encode_record(101, int(new_id), None, spec101.class_id, h)


def _pen_bisector(ctx, which: str) -> "GS.SubstBuild":
    """X1ua / X1ub -- the pre-built halving bisectors for an X1u FAIL:
    ua = model-scale vectors AUTODESK's exact feet + perspective/draft OURS;
    ub = model-scale vectors OURS + perspective/draft Autodesk's exact feet.
    Each pins the specimen's structure exactly like X1u (96 vs 32 of the 128
    doubles ours)."""
    spec = _pen_specimen(ctx)
    keys = _spec_scale_keys(spec[102].value)
    model_f, persp_f, draft_f = pen_exact_feet(spec[102].value)
    new_id = ctx.ids.next_id()
    ours_model = ST.default_model_pens_mm(scales=tuple(keys))          # our widths, spec keys
    if which == "ua":                    # Autodesk model pens, OUR perspective/draft
        rec = our_pen_table_from_feet(new_id, model_f, persp_f, draft_f)
        t = rec.obj["m_pPenWidthTable"]["value"]
        t["m_perspectiveModelPenInfo"]["m_pens"] = [x / ST.MM_PER_FT for x in ST.pen_series_mm(0)]
        t["m_draftPenInfo"]["m_pens"] = [x / ST.MM_PER_FT for x in ST.pen_series_mm(0)]
        held = "the 6 model-scale vectors (96 doubles) = Autodesk's exact feet"
        varied = "perspective + draft vectors (32 doubles) = OUR widths"
    else:                                # OUR model pens, Autodesk perspective/draft
        rec = ST.pen_width_table(elem_id=new_id, model_pens_mm=ours_model,
                                 perspective_pens_mm=[x * ST.MM_PER_FT for x in persp_f],
                                 annotation_pens_mm=[x * ST.MM_PER_FT for x in draft_f])
        t = rec.obj["m_pPenWidthTable"]["value"]
        t["m_perspectiveModelPenInfo"]["m_pens"] = [float(x) for x in persp_f]
        t["m_draftPenInfo"]["m_pens"] = [float(x) for x in draft_f]
        held = "perspective + draft vectors (32 doubles) = Autodesk's exact feet"
        varied = "the 6 model-scale vectors (96 doubles) = OUR widths"
    rec.kind = f"pen-table-value-bisector-{which}"
    info = {"probe": f"X1{which}", "role": "value bisector (upload only if X1u FAILS)",
            "held_at_specimen": held, "varied_ours": varied,
            **_pen_common_info(ctx, spec, new_id)}
    return GS.SubstBuild(old_ids=[PEN_OLD_ID], records=[rec], corr={PEN_OLD_ID: new_id},
                         notes=[f"pen-value bisector {which}: {varied}; {held}"], info=info)


def build_X1ua(ctx):
    return _pen_bisector(ctx, "ua")


def build_X1ub(ctx):
    return _pen_bisector(ctx, "ub")


# ===========================================================================
# 6. CATALOG-ROW RUNG BUILDERS (C0 / C1v / C1u [/ C0all])
# ===========================================================================

def _cat_specimen(ctx: "GS.SubstContext") -> Dict[int, SpecRecord]:
    spec = specimen_records(ctx.parent, CAT_OLD_ID)
    v = spec[102].value
    if (spec[102].class_name != "GStyleElem" or int(v.get("m_categoryId")) != CAT_CATEGORY
            or int(v.get("m_gstyleType", 1)) != CAT_STYLE_TYPE
            or int(v.get("m_famId", -1)) != -1):
        raise RuntimeError(f"element {CAT_OLD_ID} of {ctx.parent} is not the built-in "
                           f"category {CAT_CATEGORY} projection style "
                           f"(class {spec[102].class_name}, cat {v.get('m_categoryId')}, "
                           f"type {v.get('m_gstyleType')}, famId {v.get('m_famId')})")
    inb = ctx.inbound(CAT_OLD_ID)
    if inb:
        raise RuntimeError(f"catalog row {CAT_OLD_ID} has {len(inb)} referrer(s) on the "
                           f"parent -- the C probes require a referrer-free row")
    return spec


def _cat_common_info(ctx, spec, new_id: int) -> dict:
    surf = GS.adoc_surface(ctx.ted_adoc, ctx.tree, [CAT_OLD_ID]).get(CAT_OLD_ID, [])
    v = spec[102].value
    g = v["m_pGStyle"]["value"]
    return {
        "specimen_element": CAT_OLD_ID,
        "specimen_row": {"category": CAT_CATEGORY, "category_label": "OST_Windows",
                         "style_type": "projection", "pen": g.get("m_penNumber"),
                         "colour": g.get("m_color"), "line_pattern": g.get("m_linePatternId"),
                         "material": g.get("m_materialElemId"), "owner": v.get("m_ownerId"),
                         "cell_list": v.get("m_cellList") is not None,
                         "header_abFlags4Bytes": hex(int(spec[101].value.get("m_abFlags4Bytes"))),
                         "rep": spec[103].class_name},
        "specimen_registry_surface": surf,
        "specimen_referrers": 0,
        "specimen_elemtable_row": _elemtable_row(ctx.parent, CAT_OLD_ID),
        "our_add_path_writes": {
            "new_id": int(new_id),
            "elemtable_row": ("(original_id = new id, creation_ep = modified_ep = "
                              "user_modified_ep = the parent's max modified episode, "
                              "owner -1, partition 0)"),
            "record_position": "appended before each seq's sentinel (end of unit 0)",
            "registry": ("CategoryTracking.m_gstyleData row (category -2000014, type 1): "
                         "m_gstyleId re-pointed old -> new in place (same map row / key)"),
            "identity_scrub": "BasicFileInfo + DocumentIncrementTable identity (proven path)",
            "reblock": "canonical save-unit-0 re-block",
        },
    }


def build_C0(ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """C0 -- the ADD-PATH control for a catalog row: Autodesk's own OST_
    Windows projection style row, verbatim, re-inserted at a new id."""
    spec = _cat_specimen(ctx)
    new_id = ctx.ids.next_id()
    rec, proof = verbatim_typerecord(spec, "GStyleElem", new_id, ctx.ted,
                                     kind="gstyle-row-verbatim")
    info = {"probe": "C0", "role": "ADD PATH control for a catalog row (content byte-identical)",
            "byte_identity_assertion": proof,
            **_cat_common_info(ctx, spec, new_id)}
    return GS.SubstBuild(old_ids=[CAT_OLD_ID], records=[rec], corr={CAT_OLD_ID: new_id},
                         notes=[f"Autodesk's EXACT object-styles row {CAT_OLD_ID} "
                                f"(OST_Windows projection) re-inserted as new element "
                                f"{new_id} through the X-rung add path"],
                         info=info)


def _cat_our_render_exact(elem_id: int, spec_value: dict) -> TypeRecord:
    """OUR new_gstyle fed the specimen row's EXACT values."""
    g = spec_value["m_pGStyle"]["value"]
    return GT.new_gstyle(int(spec_value["m_categoryId"]),
                         style_type=("cut" if int(spec_value.get("m_gstyleType", 1)) == 2
                                     else "projection"),
                         pen=int(g["m_penNumber"]), color=int(g["m_color"]),
                         line_pattern_id=int(g["m_linePatternId"]),
                         material_id=int(g["m_materialElemId"]),
                         owner_id=int(spec_value.get("m_ownerId", -1)),
                         screen_sized=bool(g.get("m_isScreenSized", False)),
                         elem_id=int(elem_id))


def build_C1v(ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """C1v -- OUR new_gstyle fed the row's EXACT values: object + rep byte-
    identical (asserted), header differing from Autodesk's in exactly the
    ElementHeader flag bit 0x2000 (recorded to the byte)."""
    spec = _cat_specimen(ctx)
    # assertion at the ORIGINAL id
    ours_orig = _cat_our_render_exact(CAT_OLD_ID, spec[102].value)
    enc = ours_orig.encode()
    ident = {str(s): byte_compare(enc[s], spec[s].framed) for s in (101, 102, 103)}
    if not ident["102"]["identical"] or not ident["103"]["identical"]:
        raise RuntimeError("C1v: our new_gstyle does NOT reproduce the specimen row's "
                           f"object/rep byte-exactly: {ident['102']} {ident['103']} -- "
                           "HEADLINE FINDING (records the divergence, emits nothing)")
    ours_word = int(ours_orig.header.get("m_abFlags4Bytes"))
    spec_word = int(spec[101].value.get("m_abFlags4Bytes"))
    header_delta = _pen_field_diff(ours_orig.header, spec[101].value)   # generic dict diff
    new_id = ctx.ids.next_id()
    ours = _cat_our_render_exact(new_id, spec[102].value)
    ours.kind = "gstyle-row-our-constructor-exact-values"
    info = {
        "probe": "C1v", "role": "HEADER control (object + rep byte-identical, values exact)",
        "byte_identity_assertion": {
            "our_constructor_fed_exact_values_vs_specimen_at_original_id": ident,
            "object_identical": ident["102"]["identical"],
            "rep_identical": ident["103"]["identical"],
            "header_identical": ident["101"]["identical"],
        },
        "the_ONE_difference_header": {
            "field_level_delta_ours_vs_specimen": header_delta,
            "our_abFlags4Bytes": hex(ours_word), "specimen_abFlags4Bytes": hex(spec_word),
            "xor": hex(ours_word ^ spec_word),
            "reading": ("our built-in object-style header preset 0x400001e vs this "
                        "row's 0x400201e: exactly ONE flag bit, 0x2000, is CLEARED in ours; "
                        "every other header byte (category -1, vis flags -32768, "
                        "deletion [self], empty appearance/regen lists) is identical"),
        },
        "finding_G1_G2_context": ("the six-preset / cell-list census (findings.json G1) and "
                                  "the cross-sample non-constancy (G2): our preset "
                                  "0x400001e is itself carried by 15 accepted K1 rows and by "
                                  "other categories in rme -- so the bit is EXPECTED to be "
                                  "tolerated; C1v settles it directly"),
        **_cat_common_info(ctx, spec, new_id),
    }
    return GS.SubstBuild(old_ids=[CAT_OLD_ID], records=[ours], corr={CAT_OLD_ID: new_id},
                         notes=["our new_gstyle fed the row's EXACT values: object + rep "
                                "byte-identical (asserted); header differs by flag bit "
                                f"0x2000 only (ours {hex(ours_word)} vs spec {hex(spec_word)})"],
                         info=info)


def our_catalog_row(elem_id: int, category: int = CAT_CATEGORY,
                    style_type: int = CAT_STYLE_TYPE) -> TypeRecord:
    """The row OUR catalog generator emits for (category, style type) --
    exactly what X6a / R2 shipped for it (discipline scheme + INK_BLACK +
    solid pattern, no material)."""
    disc = CAT.classify_category(int(category))
    sch = CAT.catalog_scheme()
    ppen, cpen, colour = sch.get(disc, sch.get("general", (1, 3, 0)))
    return GT.new_gstyle(int(category),
                         style_type=("cut" if int(style_type) == 2 else "projection"),
                         pen=int(cpen if int(style_type) == 2 else ppen), color=int(colour),
                         line_pattern_id=LINEPATTERN_SOLID, material_id=INVALID,
                         elem_id=int(elem_id))


def build_C1u(ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """C1u -- our catalog constructor's LITERAL row for OST_Windows projection
    (our discipline pen 1 / colour 0x181818): differs from C1v ONLY in the
    two values -- the very row X6a / R2 shipped for this category."""
    spec = _cat_specimen(ctx)
    new_id = ctx.ids.next_id()
    ours = our_catalog_row(new_id)
    ours.kind = "gstyle-row-our-catalog-values"
    # what C1u changes vs C1v (values) and vs the specimen (values + the header bit)
    c1v = _cat_our_render_exact(new_id, spec[102].value)
    value_delta = _pen_field_diff(ours.obj, c1v.obj)
    disc = CAT.classify_category(CAT_CATEGORY)
    info = {
        "probe": "C1u", "role": "OUR VALUES for the same row (the literal X6a/R2 row)",
        "our_row": {"discipline": disc,
                    "pen": ours.obj["m_pGStyle"]["value"]["m_penNumber"],
                    "colour": ours.obj["m_pGStyle"]["value"]["m_color"],
                    "line_pattern": ours.obj["m_pGStyle"]["value"]["m_linePatternId"],
                    "material": ours.obj["m_pGStyle"]["value"]["m_materialElemId"],
                    "identical_to_the_X6a_R2_row_for_this_category": True},
        "the_ONE_difference_vs_C1v_values": value_delta,
        "header": ("same OUR preset as C1v (0x400001e) -- the header bit is C1v's variable; "
                   "C1u is read as C1v + the two value changes"),
        **_cat_common_info(ctx, spec, new_id),
    }
    return GS.SubstBuild(old_ids=[CAT_OLD_ID], records=[ours], corr={CAT_OLD_ID: new_id},
                         notes=[f"our catalog row for OST_Windows projection ({disc} scheme): "
                                f"pen {ours.obj['m_pGStyle']['value']['m_penNumber']}, colour "
                                f"{hex(ours.obj['m_pGStyle']['value']['m_color'])} -- vs C1v: "
                                f"{len(value_delta)} value change(s)"],
                         info=info)


def build_C0all(ctx: "GS.SubstContext") -> "GS.SubstBuild":
    """C0all -- the catalog-SCALE add-path control: EVERY referrer-free
    built-in object-style row (the K6/R2/X6a population, ~1,348 on K1)
    removed and Autodesk's OWN rows re-inserted VERBATIM at new ids through
    our add path, with CategoryTracking mass-re-pointed.  The direct sibling
    of R2 (our rows) and R2s (original ids, registry untouched)."""
    olds: List[int] = []
    for e in ctx.ids_of("GStyleElem"):
        v = ctx.value(e)
        if int(v.get("m_famId", -1)) != -1:
            continue
        cid = v.get("m_categoryId")
        if not (isinstance(cid, int) and cid < 0):
            continue
        if ctx.inbound(e):
            continue
        olds.append(int(e))
    segs = unit0_segments(ctx.parent)
    records: List[TypeRecord] = []
    corr: Dict[int, int] = {}
    n_ident = 0
    for e in olds:
        spec = specimen_records(ctx.parent, e, segments=segs)
        nid = ctx.ids.next_id()
        rec, proof = verbatim_typerecord(spec, "GStyleElem", nid, ctx.ted,
                                         kind="gstyle-row-verbatim")
        n_ident += int(proof["all_three_seqs_identical"])
        records.append(rec)
        corr[e] = nid
    info = {"probe": "C0all",
            "role": "ADD PATH control at CATALOG SCALE (all referrer-free built-in rows, "
                    "Autodesk's exact bytes, new ids)",
            "rows_reinserted": len(olds),
            "all_rows_verbatim_byte_identical_at_original_ids": (n_ident == len(olds)),
            "verbatim_identity_count": n_ident,
            "new_id_range": [min(corr.values()), max(corr.values())] if corr else [],
            "siblings": {
                "R2 (viewer FAIL)": "same population, OUR row shapes/values",
                "R2s (addback, un-uploaded)": ("same population restored at ORIGINAL ids "
                                                 "with the document object reinstated "
                                                 "verbatim -- no registry rewrite"),
                "K1 (viewer PASS)": "the rows at their original ids/positions"},
            "what_it_isolates": ("R2's failure with content held byte-identical: our add "
                                 "path at catalog scale (1,348 deletions + 1,348 high-id "
                                 "re-inserts at the unit end + fresh episodes + the "
                                 "CategoryTracking mass re-point) -- everything R2 did "
                                 "except OUR rows' shape/values")}
    return GS.SubstBuild(old_ids=olds, records=records, corr=corr,
                         notes=[f"{len(olds)} referrer-free built-in object-style rows: "
                                f"Autodesk's exact bytes ({n_ident} verified verbatim at their "
                                "original ids) re-inserted at new ids through the add path"],
                         info=info)


# ===========================================================================
# 7. X0k -- same-id re-insert (ZERO registry motion): the add-path bisector
# ===========================================================================

def build_X0k_file(out_dir: str = CONTROLS) -> dict:
    """X0k -- Autodesk's exact pen table DELETED then RE-INSERTED AT ITS OWN
    id 2 through the SAME record-append path (rvt.reduce.delete_elements then
    rvt.commit.commit_new_elements).  The document object is untouched (its
    PenWidthTableInfo leaf still names 2, present again) -- ZERO registry /
    id motion.  What differs from K1: the three records now sit at the END
    of unit 0, and the ElemTable row for id 2 is rewritten by OUR path
    ((ep, ep, ep) episodes / original_id 2) instead of K1's (0, 976, 976).
    The pre-built bisector for an X0 FAIL: X0k PASS + X0 FAIL => the new-id /
    registry-rewrite half; X0k FAIL => the record-append / ElemTable-row half.
    Cannot go through the substitution engine (delete + add of the SAME id in
    one pass would delete both), hence this direct path."""
    t0 = time.time()
    name = "X0k"
    out = os.path.join(out_dir, f"{name}.rvt")
    spec = specimen_records(K1, PEN_OLD_ID)
    ted = GS.TypedEditor(decoder=Document.from_file(K1).dec, maps=GA_load_maps())
    rec, proof = verbatim_typerecord(spec, "PenWidthTableElem", PEN_OLD_ID, ted,
                                     kind="pen-table-verbatim-same-id")
    t_del = os.path.join(out_dir, ".X0k.deleted.rvt")
    t_add = os.path.join(out_dir, ".X0k.added.rvt")
    log(f"\n== X0k :: pen table re-inserted AT ITS OWN id {PEN_OLD_ID} (zero registry motion)")
    delete_elements(K1, t_del, [PEN_OLD_ID])
    with open_rvt(K1) as f:
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
        max_ep = max(int(r[2]) for r in et["records"])
    plan = ElemRecPlan(elem_id=PEN_OLD_ID, original_id=PEN_OLD_ID, creation_ep=0,
                       modified_ep=0, user_modified_ep=0)
    crep = commit_new_elements(t_del, t_add, [rec.encode()], [plan],
                               identity=dict(GS.IDENTITY))
    ver = verify_written(t_add, [PEN_OLD_ID])
    delete_elements(t_add, out, [])                    # canonical re-block
    for p in (t_del, t_add):
        try:
            os.remove(p)
        except OSError:
            pass
    # certification: validator, structural, Latest unchanged (still names 2), no dangling
    val = RR._run_validator(out)
    struct = verify_reduced(out, [])
    with open_rvt(K1) as f:
        latest_k1 = f.inflate(adoc.STREAM, 0)
    with open_rvt(out) as f:
        latest_out = f.inflate(adoc.STREAM, 0)
        et_out = se.decode_elemtable(f.inflate("Global/ElemTable"))
    a = adoc.decode_latest(latest_out)
    ted2 = GS.TypedEditor(decoder=None, maps=ted.maps)
    surf = GS.adoc_surface(ted2, a.value, [PEN_OLD_ID]).get(PEN_OLD_ID, [])
    row_out = next((r for r in et_out["records"] if int(r[4]) == PEN_OLD_ID), None)
    problems = []
    if not (val.get("ok") and val.get("errors") == 0):
        problems.append(f"validator errors={val.get('errors')}")
    if not struct.get("ok"):
        problems.append("structural proof failed")
    if latest_out != latest_k1:
        problems.append("Global/Latest changed (must be byte-identical to K1's)")
    if not surf:
        problems.append("PenWidthTableInfo no longer indexes id 2")
    rep = {
        "rung": name, "label": "PenWidthTableElem re-inserted AT ITS OWN id (zero registry motion)",
        "kind": "same-id-reinsert", "parent": _relp(K1), "out": _relp(out),
        "description": build_X0k_file.__doc__.strip().split("\n")[0],
        "byte_identity_assertion": proof,
        "add_path": {"delete": "rvt.reduce.delete_elements(K1, ., [2])",
                     "add": "rvt.commit.commit_new_elements (records appended at unit end)",
                     "elemtable_row_written": {"creation_ep": max_ep, "modified_ep": max_ep,
                                               "user_modified_ep": max_ep, "original_id": PEN_OLD_ID,
                                               "owner": -1, "partition": 0},
                     "specimen_elemtable_row": _elemtable_row(K1, PEN_OLD_ID),
                     "elemtable_after": crep.elemtable_count_after,
                     "watermark_after": crep.watermark_after,
                     "verify_written": {k: ver[k] for k in ("crc_failures", "ecc_mismatches",
                                                           "walker_errors", "stamps_ok")},
                     "new_records_found": {str(k): {str(i): v for i, v in s.items()}
                                           for k, s in ver["new_ids_found"].items()}},
        "registry": {"global_latest_byte_identical_to_K1": latest_out == latest_k1,
                     "penwidthtableinfo_surface": surf,
                     "elemtable_row_id2_after": row_out and list(row_out)},
        "validator": val,
        "structural": {k: struct.get(k) for k in ("ok", "crc_failures", "ecc_mismatches",
                                                    "counts_match", "seq_id_sets_equal",
                                                    "stamps_bad", "isize_identity_ok")},
        "problems": problems,
        "verdict": "VALID" if not problems else "NOT-CLEAN",
        "bytes": os.path.getsize(out), "seconds": round(time.time() - t0, 1),
        "tests": ("Is the record-append + ElemTable-row-rewrite HALF of the add path "
                  "(no id change, no registry rewrite, Global/Latest byte-identical to "
                  "K1's) reader-clean for the pen table?  The pre-built bisector for an "
                  "X0 FAIL."),
        "if_PASS": ("With X0 FAILING: the new-id band / ElemTable-append-with-new-id / "
                    "registry-leaf-rewrite half of the add path is the corruption.  With X0 "
                    "PASSING: X0k is expected to pass too (subset of X0's change)."),
        "if_FAIL": ("The record-append / ElemTable-row-rewrite half itself corrupts a "
                    "settings singleton (episodes (ep,ep,ep) vs K1's (0,976,976), or the "
                    "record moved to the unit end): the same path every X-rung and the "
                    "S/G lines use."),
    }
    GS._write_report(out_dir, name, rep)
    log(f"   validator: {'VALID' if val.get('ok') else 'INVALID'} errors={val.get('errors')} "
        f"warnings={val.get('warnings')}; structural ok={struct.get('ok')}; "
        f"Latest==K1 {latest_out == latest_k1}; registry {surf}")
    log(f"   -> {_relp(out)} {rep['bytes']:,} B  VERDICT {rep['verdict']} ({rep['seconds']}s)")
    return rep


def GA_load_maps():
    import genesis_assemble as GA
    return GA.load_registry_maps()


# ===========================================================================
# 8. THE RUNG TABLE (descriptions / tests / decision-tree text)
# ===========================================================================

_ADD_PATH_TXT = ("the X-rung add path (rvt.commit.commit_new_elements: records appended before "
                 "the sentinel, ElemTable row appended with the parent's max episode, "
                 "watermark raised, identity scrub) + OLD element deleted (rvt.manipulate) + "
                 "the ADocument registry leaf re-pointed old->new + Global/Latest re-encoded "
                 "byte-exactly + canonical unit-0 re-block")

RUNGS: List["GS.Rung"] = [
    GS.Rung(
        name="X0", label="PenWidthTableElem: Autodesk's OWN pen table re-inserted VERBATIM "
                          "as a new element through OUR add path",
        parent="K1",
        description=("K1 (viewer PASS) with its project pen table (element id 2) REMOVED and "
                     "the SAME Autodesk pen table's exact records RE-INSERTED as a NEW element "
                     f"(id 1,500,000; only its own identity fields rebased) through {_ADD_PATH_TXT}"
                     ". The ONE change vs K1: the pen table travelled through our add path -- "
                     "its content is byte-identical (asserted, all 3 seqs)."),
        tests=("Is OUR ADD PATH sound for a document-settings singleton?  Content is held at "
               "Autodesk's exact bytes, so a FAIL can only be the path (ElemTable row fields, "
               "record position, new-id band, registry-leaf rewrite, identity scrub, re-block)."),
        if_pass=("The add path is sound for a settings singleton.  The whole X-ladder's "
                 "singleton substitutions rest on this path; whatever an X-rung's FAIL is, "
                 "it is that rung's CONTENT (object shape / header / values), not the path.  "
                 "Read X1u next (values), then the ladder's X1 (keys)."),
        if_fail=("THE ADD PATH ITSELF CORRUPTS a settings singleton -- the X-ladder is void "
                 "until fixed.  The diff of what our path wrote vs K1's original registration "
                 "is in X0.json:build_info (ElemTable row (0,976,976)->(ep,ep,ep) with "
                 "original_id = the new id; record moved from mid-stream to the unit end; "
                 "id 2 -> 1,500,000 leaving a hole at the front of the id space; the "
                 "PenWidthTableInfo leaf rewritten to a 1.5M id; the identity scrub).  Upload "
                 "the pre-built X0k (same-id re-insert, ZERO registry motion) to halve it: "
                 "X0k PASS => the new-id / registry-rewrite half; X0k FAIL => the "
                 "record-append / ElemTable-row half."),
        build=build_X0),
    GS.Rung(
        name="X1v", label="PenWidthTableElem: OUR CONSTRUCTOR fed AUTODESK'S EXACT values "
                           "(byte-identical -- ASSERTED; a no-upload twin of X0)",
        parent="K1",
        description=("K1 with its pen table replaced by OUR pen_width_table constructor's output "
                     "fed the specimen's EXACT parameter values (exact feet -- the mm interface "
                     "cannot express 8 of the 128 doubles, FINDING P1), inserted through the "
                     "same add path.  ASSERTED before emission: our constructor's HEADER, "
                     "OBJECT and REP encode byte-identical to Autodesk's (all 3 seqs), so X1v's "
                     "element records ARE X0's records -- X1v is content-identical to X0."),
        tests=("Does OUR constructor's rendition of a byte-identical object load?  Because the "
               "byte-identity assertion holds for header + object + rep, this file needs NO "
               "upload: its verdict IS X0's.  Its purpose is the ASSERTION (recorded in "
               "X1v.json): {shape, header, rep} of the pen-table constructor are retired as "
               "suspects by construction, leaving only VALUES (X1u) and scale KEYS (X1) as X1's "
               "variables."),
        if_pass=("(= X0 PASS) Our constructor CAN emit a reader-clean pen table when fed "
                 "Autodesk's exact values: the constructor's structure/header/rep are fine; "
                 "any X1 failure is OUR VALUES or OUR SCALE KEYS -- X1u separates them."),
        if_fail=("(= X0 FAIL) The add path is broken; content questions are moot until it is "
                 "fixed (X0k halves it)."),
        build=build_X1v),
    GS.Rung(
        name="X1u", label="PenWidthTableElem: OUR width VALUES, the specimen's structure "
                           "(6 metric scale keys / 16 pens / flags) pinned",
        parent="K1",
        description=("K1 with its pen table replaced by OUR constructor carrying OUR ISO-128-based "
                     "width series (16 pens per vector, coarser scale = one more leading hairline "
                     "-- the specimen's own shift direction) but EVERY structural choice pinned "
                     "to the specimen: the 6 model-scale KEYS are Autodesk's metric denominators "
                     "10/20/50/100/200/500 (not our imperial 24..768 ladder), 16 pens each, "
                     "perspective + draft vectors, m_famId -1, byte-identical header + rep.  ONE "
                     "change vs X1v/X0: the 128 width doubles.  ONE change vs the ladder's X1: "
                     "the 6 scale keys."),
        tests=("Are OUR width VALUES themselves acceptable when nothing structural differs from "
               "the accepted specimen (the value-semantics question for the pen table)?"),
        if_pass=("Our width values are fine.  Then the ONLY variable left in the ladder's X1 is "
                 "the six scale KEYS (our imperial breakpoints 24/48/96/192/384/768 in a "
                 "metric-lineage document vs the specimen's 10..500): if X1 FAILS while X1u "
                 "PASSES, the SCALE-KEY VALUES are the audited constraint (a set of valid "
                 "view-scale denominators, or units-consistency) -- a one-line settings fix "
                 "and a KNOWLEDGE entry.  If X1 also PASSES, PenWidthTableElem is fully retired "
                 "as a suspect (path X0, shape X1v, values X1u, keys X1)."),
        if_fail=("(with X0 PASSING) a WIDTH VALUE range/ordering IS audited by the reader (our "
                 "0.13-8.0 mm series vs Autodesk's 0.1-10.0).  Upload the pre-built halving "
                 "bisectors X1ua (model vectors Autodesk's exact, perspective+draft OURS) and "
                 "X1ub (model OURS, perspective+draft Autodesk's) to localize it to 96 vs 32 "
                 "doubles; the width constraint then becomes a documented constant."),
        build=build_X1u),
    GS.Rung(
        name="C0", label="GStyleElem row (OST_Windows projection): Autodesk's OWN row re-inserted "
                          "VERBATIM as a new element through OUR add path",
        parent="K1",
        description=("K1 with its built-in object-styles row 34 (category -2000014 OST_Windows, "
                     "projection style, ZERO referrers, ONE registry leaf) REMOVED and the SAME "
                     "Autodesk row's exact records RE-INSERTED as a NEW element (only its own "
                     f"identity fields rebased) through {_ADD_PATH_TXT} -- here the registry "
                     "leaf is CategoryTracking.m_gstyleData[(cat -2000014, type 1)].m_gstyleId."
                     "  The ONE change vs K1: the row travelled through our add path (content "
                     "byte-identical, asserted all 3 seqs)."),
        tests=("Is OUR ADD PATH sound for a built-in object-styles catalog row (the class R2 / "
               "X6a substitute wholesale)?  The catalog-row analogue of X0."),
        if_pass=("The add path is sound for a catalog row -- R2's / X6a's mechanics per row are "
                 "not the killer; read C1v (header) and C1u (values), and see C0all for the "
                 "catalog-SCALE version of this question (R2 substituted 1,348 rows at once)."),
        if_fail=("The add path corrupts a catalog row.  With X0 ALSO FAILING => the add path in "
                 "general; with X0 PASSING => the catalog-row registration specifically (the "
                 "CategoryTracking m_gstyleId rewrite to a high id, or a built-in style at a "
                 "1.5M id).  C0.json:build_info carries the exact diff (ElemTable row, record "
                 "position, registry leaf)."),
        build=build_C0),
    GS.Rung(
        name="C1v", label="GStyleElem row (OST_Windows projection): OUR new_gstyle fed the row's "
                           "EXACT values -- object+rep byte-identical, header ONE flag bit apart",
        parent="K1",
        description=("K1 with row 34 replaced by OUR new_gstyle constructor fed the row's EXACT "
                     "values (pen 2, colour 0, solid pattern -3000010, no material, owner -1), "
                     "through the same add path.  ASSERTED: the seq-102 object and the seq-103 "
                     "rep encode BYTE-IDENTICAL to Autodesk's; the seq-101 header differs in "
                     "EXACTLY ONE flag bit -- our built-in object-style preset "
                     "m_abFlags4Bytes = 0x400001e vs this row's 0x400201e (bit 0x2000 cleared "
                     "in ours); every other header byte is identical.  ONE change vs C0: that "
                     "flag bit."),
        tests=("Is the ElementHeader flag word audited for object-style rows?  Our catalog "
               "constructor emits ONE preset (0x400001e) for all 1,407 built-in rows while the "
               "accepted catalog carries SIX presets (findings G1); C1v isolates the bit our "
               "preset drops for this row (0x2000).  Findings G2 (the same category carries "
               "different presets in different accepted files; our preset itself occurs on 15 "
               "accepted K1 rows) predicts PASS."),
        if_pass=("The header flag bit 0x2000 is NOT audited for this row (as G2 predicts): our "
                 "single header preset is tolerated => read C1u for the values; the "
                 "per-row header/cell-list divergence of our catalog constructor is NOT R2's "
                 "killer, and the weight shifts to the catalog-scale path (C0all) and to "
                 "actually uploading R2s (the addback stream's un-uploaded mechanics control)."),
        if_fail=("(with C0 PASSING) THE ELEMENTHEADER FLAG WORD IS AUDITED for built-in "
                 "object-style rows: our catalog constructor must emit each row's flag preset "
                 "(and, likely, the CellList{PatternHelper} the census shows on 790 rows -- "
                 "the next probe would be a cell-list twin).  This ALONE can explain R2 / X6a "
                 "(1,392 of their 1,407 rows carry a preset other than ours).  Since G2 shows "
                 "the presets vary per document, the rule is not per-category: mine the "
                 "constraint from the six accepted combinations (findings.json)."),
        build=build_C1v),
    GS.Rung(
        name="C1u", label="GStyleElem row (OST_Windows projection): OUR catalog constructor's "
                           "LITERAL row (our discipline pen / colour) -- the X6a/R2 row",
        parent="K1",
        description=("K1 with row 34 replaced by the LITERAL row our catalog generator emits for "
                     "(OST_Windows, projection) -- our architectural-discipline pen 1 and our ink "
                     "colour 0x181818 (vs Autodesk's pen 2 / colour 0), solid pattern, no material, "
                     "our header preset -- through the same add path.  ONE change vs C1v: the "
                     "two VALUES (pen number, colour).  This is byte-for-byte the row X6a / R2 "
                     "shipped for this category, alone on a passing base."),
        tests=("Are OUR object-style VALUES (pen number / COLORREF colour) acceptable for a "
               "catalog row?  The value-semantics question, one row."),
        if_pass=("(with C0 and C1v PASSING) the single-row substitution is FULLY EXONERATED -- "
                 "path, shape, header preset AND our values are all reader-clean for a catalog "
                 "row.  R2's / X6a's failure is then a WHOLE-CATALOG effect (1,348 rows at "
                 "once): the pre-built C0all (all referrer-free built-in rows re-inserted "
                 "VERBATIM at new ids through our path) separates 'the add path at catalog "
                 "scale' from 'our rows at catalog scale'; upload it, and upload R2s (never "
                 "uploaded) to close the mechanics side."),
        if_fail=("(with C1v PASSING) OUR VALUES for a catalog row are audited -- pen number 1 "
                 "and/or COLORREF 0x181818; a pen/colour twin pair splits them (seconds to "
                 "build with this tool)."),
        build=build_C1u),
]

OPTIONAL_RUNGS: List["GS.Rung"] = [
    GS.Rung(
        name="C0all", label="ALL referrer-free built-in object-style rows: Autodesk's OWN rows "
                             "re-inserted VERBATIM at new ids through OUR add path (catalog "
                             "SCALE control)",
        parent="K1",
        description=("K1 with EVERY referrer-free built-in object-style row (the exact K6 / R2 / "
                     "X6a population, ~1,348 rows) REMOVED and Autodesk's OWN rows -- byte-"
                     "identical, asserted per row -- RE-INSERTED as new elements at ids "
                     ">= 1,500,000 through the add path, with all ~1,348 "
                     "CategoryTracking.m_gstyleData leaves re-pointed.  Content is Autodesk's; "
                     "the only change vs K1 is our add path applied at catalog scale."),
        tests=("R2 FAILED with our catalog (this population, OUR rows) and its mechanics control "
               "R2s (rows restored at their ORIGINAL ids, document object verbatim) was never "
               "uploaded.  C0all is the missing third: OUR PATH at catalog scale with content "
               "held byte-identical.  Together with C0 (one row) it separates {path per row} "
               "/ {path at scale: 1,348 deletions, 1,348 high-id re-inserts at the unit end, "
               "fresh episodes, the CategoryTracking mass re-point} / {our rows}."),
        if_pass=("Our add path is sound at catalog scale => R2's failure IS our rows' content "
                 "(shape/header/values), and C1v / C1u name which aspect per row.  If C1v/C1u "
                 "also PASS, the residual is a MULTI-row content interaction (e.g. our ink "
                 "colour on 1,300 rows, our single header preset across the whole table) -- "
                 "bisect by band/preset."),
        if_fail=("(with C0 PASSING) the add path breaks AT SCALE though not per row: the "
                 "1,348-row mass motion itself (high-id band for the whole object-styles table, "
                 "the CategoryTracking map's values all rewritten, or 1,348 fresh-episode "
                 "ElemTable rows / records at the unit end) -- and R2s would tell whether "
                 "the SAME mass motion at ORIGINAL ids passes.  (with C0 FAILING) => the add "
                 "path generally."),
        build=build_C0all),
    GS.Rung(
        name="X1ua", label="PenWidthTableElem value bisector A: model-scale vectors Autodesk's "
                            "exact, perspective + draft OURS",
        parent="K1", description="Upload ONLY if X1u FAILS.  Halves the 128 doubles: the six "
                                 "model-scale vectors (96 doubles) hold Autodesk's exact feet; "
                                 "the perspective + draft vectors (32) carry OUR widths.",
        tests="Which half of the width doubles the reader audits (with X1ub).",
        if_pass="the audited value lives in the model-scale vectors (X1ub should FAIL)",
        if_fail="the audited value lives in the perspective / draft vectors (or both halves)",
        build=build_X1ua),
    GS.Rung(
        name="X1ub", label="PenWidthTableElem value bisector B: model-scale vectors OURS, "
                            "perspective + draft Autodesk's exact",
        parent="K1", description="Upload ONLY if X1u FAILS.  The complement of X1ua: the six "
                                 "model-scale vectors carry OUR widths; perspective + draft "
                                 "hold Autodesk's exact feet.",
        tests="Which half of the width doubles the reader audits (with X1ua).",
        if_pass="the audited value lives in the perspective / draft vectors (X1ua should FAIL)",
        if_fail="the audited value lives in the model-scale vectors (or both halves)",
        build=build_X1ub),
]


def rung_by_name(name: str) -> "GS.Rung":
    for r in RUNGS + OPTIONAL_RUNGS:
        if r.name == name:
            return r
    raise KeyError(name)


# ===========================================================================
# 9. post-build checks + the manifest
# ===========================================================================

def stream_digests(path: str) -> dict:
    """sha256 (short) of the meaningful streams -- the collapse check between
    X1v and X0 (their element streams must be identical)."""
    out = {}
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        out["partition"] = _digest(f.logical(pname))
        out["Global/Latest"] = _digest(f.inflate(adoc.STREAM, 0))
        out["Global/ElemTable"] = _digest(f.inflate("Global/ElemTable"))
    return out


def collapse_check(out_dir: str = CONTROLS) -> Optional[dict]:
    """Verify X1v's element streams == X0's (the no-upload twin)."""
    x0 = os.path.join(out_dir, "X0.rvt")
    x1v = os.path.join(out_dir, "X1v.rvt")
    if not (os.path.exists(x0) and os.path.exists(x1v)):
        return None
    d0, d1 = stream_digests(x0), stream_digests(x1v)
    same = {k: (d0[k] == d1[k]) for k in d0}
    return {"X0": d0, "X1v": d1, "identical": same,
            "content_identical": all(same.values()),
            "statement": ("X1v's Partitions / Latest / ElemTable streams are byte-identical to "
                          "X0's" if all(same.values()) else
                          "X1v differs from X0 in " + ", ".join(k for k, v in same.items() if not v))}


def write_findings(out_dir: str = CONTROLS, *, with_cross_sample: bool = True) -> dict:
    """findings.json -- the census / analysis evidence behind P1/P2/G1/G2."""
    t0 = time.time()
    spec = specimen_records(K1, PEN_OLD_ID)
    f: Dict[str, Any] = {
        "generated_by": "tools/genesis_controls.py --findings",
        "P1_pen_table_doubles_not_mm_derived": pen_value_analysis(spec[102].value),
        "P2_pen_table_shape_header_rep_reproduced": {
            "statement": ("our pen_width_table constructor fed the specimen's exact feet "
                          "reproduces element 2's HEADER (abFlags 8222, vis -32768, "
                          "deletion [2], no wildcards / regenOnly), OBJECT and REP "
                          "(empty SerializedDummy) BYTE-IDENTICALLY -- X1v.json carries "
                          "the per-seq assertion; therefore X1v == X0 at the record level"),
        },
        "G1_catalog_row_shape_census_K1": catalog_shape_census(K1),
    }
    if with_cross_sample:
        try:
            f["G2_catalog_row_shape_not_a_format_constant"] = cross_sample_shape_constancy()
        except Exception as e:                                     # corpus absent
            f["G2_catalog_row_shape_not_a_format_constant"] = {
                "skipped": f"cross-sample census unavailable: {e!r}"}
    f["seconds"] = round(time.time() - t0, 1)
    p = os.path.join(out_dir, "findings.json")
    with open(p, "w") as fh:
        json.dump(f, fh, indent=1, default=str)
    log(f"[findings] -> {_relp(p)} ({f['seconds']}s)")
    return f


def write_probes_manifest(out_dir: str = CONTROLS) -> str:
    """probes.json -- ORDERED X0, X1v, X1u, C0, C1v, C1u (+ optional), with
    the full decision tree.  Reads whatever reports exist on disk."""
    reports: Dict[str, dict] = {}
    for r in RUNGS + OPTIONAL_RUNGS + []:
        p = os.path.join(out_dir, f"{r.name}.json")
        if os.path.exists(p):
            with open(p) as fh:
                reports[r.name] = json.load(fh)
    x0k = os.path.join(out_dir, "X0k.json")
    if os.path.exists(x0k):
        with open(x0k) as fh:
            reports["X0k"] = json.load(fh)

    def _probe(rung: "GS.Rung", order: Optional[int], *, optional: bool = False,
               extra: Optional[dict] = None) -> dict:
        rep = reports.get(rung.name, {})
        bi = rep.get("build_info") or {}
        assertions = {}
        if "byte_identity_assertion" in bi:
            a = bi["byte_identity_assertion"]
            if "verbatim_identity_at_original_id" in a:
                # X0 / C0 (/C0all): Autodesk's own records, re-encoded byte-exactly
                assertions = {"autodesk_records_reencoded_byte_identical_all_3_seqs":
                              a.get("all_three_seqs_identical")}
            else:
                # X1v / C1v: OUR constructor fed the specimen's exact values
                assertions = {
                    "our_constructor_all_three_seqs_identical": a.get("all_three_seqs_identical"),
                    "object_identical": a.get("object_identical"),
                    "rep_identical": a.get("rep_identical"),
                    "header_identical": a.get("header_identical"),
                }
            assertions = {k: v for k, v in assertions.items() if v is not None}
        elif bi.get("all_rows_verbatim_byte_identical_at_original_ids") is not None:
            assertions = {"all_rows_verbatim_byte_identical_at_original_ids":
                          bi["all_rows_verbatim_byte_identical_at_original_ids"],
                          "rows": bi.get("rows_reinserted")}
        related = ("experiments/genesis/subst/X1.rvt (the ladder's pen-table rung: OUR "
                   "constructor + OUR values + OUR imperial scale keys; verdict pending)"
                   if rung.name.startswith("X") else
                   "experiments/genesis/addback/R2.rvt (OUR whole catalog on K1: viewer FAIL) "
                   "and R2s.rvt (its original-id mechanics control: NEVER uploaded)")
        entry = {
            "order": order,
            "file": f"experiments/genesis/controls/{rung.name}.rvt",
            "report": f"experiments/genesis/controls/{rung.name}.json",
            "class": ("PenWidthTableElem" if rung.name.startswith("X") else "GStyleElem "
                      "(built-in catalog row: OST_Windows -2000014 projection, K1 row 34)"),
            "derived_from": "experiments/genesis/triage/K1.rvt (viewer PASS) by ONE change",
            "passing_sibling": "experiments/genesis/triage/K1.rvt (Autodesk's empty-project "
                               "skeleton, viewer PASS; descendants K3 / K4 / KD1 PASS)",
            "related_files": related,
            "label": rung.label,
            "the_one_thing_it_tests": rung.tests,
            "if_PASS": rung.if_pass,
            "if_FAIL": rung.if_fail,
            "byte_identity_assertions": assertions,
            "validator_verdict": (rep.get("verdict") or "NOT BUILT"),
            "validator_errors": (rep.get("validator") or {}).get("errors"),
            "optional": optional,
        }
        if extra:
            entry.update(extra)
        return entry

    collapse = collapse_check(out_dir)
    probes: List[dict] = []
    probes.append(_probe(RUNGS[0], 1))                                    # X0
    probes.append(_probe(RUNGS[1], 2, extra={                              # X1v
        "NO_UPLOAD_TWIN_OF": "X0",
        "collapse_check": collapse,
        "upload_note": ("Do NOT spend a viewer round on X1v: its element streams are "
                        "byte-identical to X0's (collapse_check).  Its verdict IS X0's.  It is "
                        "emitted for the record: the byte-identity assertion in X1v.json is "
                        "the deliverable (our pen-table constructor's shape/header/rep are "
                        "Autodesk-identical by construction).")}))
    probes.append(_probe(RUNGS[2], 3))                                    # X1u
    probes.append(_probe(RUNGS[3], 4))                                    # C0
    probes.append(_probe(RUNGS[4], 5))                                    # C1v
    probes.append(_probe(RUNGS[5], 6))                                    # C1u
    opt: List[dict] = []
    opt.append(_probe(OPTIONAL_RUNGS[0], 7, optional=True, extra={
        "when": ("Upload WITH the C batch (high value regardless of C0/C1v/C1u): it is the "
                 "catalog-SCALE add-path control that R2's reading has been missing, and it "
                 "pairs with R2s (experiments/genesis/addback/R2s.rvt -- built by the addback "
                 "stream, NEVER uploaded; R2's failure is only attributable to our rows if R2s "
                 "and C0all PASS).")}))
    if "X0k" in reports or True:
        opt.append({
            "order": 8, "file": "experiments/genesis/controls/X0k.rvt",
            "report": "experiments/genesis/controls/X0k.json", "class": "PenWidthTableElem",
            "derived_from": "experiments/genesis/triage/K1.rvt by ONE change",
            "label": ("PenWidthTableElem re-inserted AT ITS OWN id 2 (delete + append, ZERO "
                      "registry / id motion, Global/Latest byte-identical to K1's)"),
            "the_one_thing_it_tests": (reports.get("X0k") or {}).get("tests",
                                                                   "the add-path bisector"),
            "if_PASS": (reports.get("X0k") or {}).get("if_PASS", ""),
            "if_FAIL": (reports.get("X0k") or {}).get("if_FAIL", ""),
            "validator_verdict": (reports.get("X0k") or {}).get("verdict", "NOT BUILT"),
            "optional": True,
            "when": "Upload ONLY if X0 FAILS (it halves the add path).",
        })
    opt.append(_probe(OPTIONAL_RUNGS[1], 9, optional=True,
                      extra={"when": "Upload ONLY if X1u FAILS (with X1ub)."}))
    opt.append(_probe(OPTIONAL_RUNGS[2], 10, optional=True,
                      extra={"when": "Upload ONLY if X1u FAILS (with X1ua)."}))
    manifest = {
        "generator": "tools/genesis_controls.py",
        "stream": "genesis-controls -- the three-way separation {ADD PATH vs OBJECT SHAPE vs "
                  "OUR VALUES}, one class at a time",
        "the_divide_it_attacks": (
            "ORCHESTRATOR VERDICTS #9: every file whose element records are Autodesk's "
            "verbatim bytes LOADS; every file carrying our from-scratch CONSTRUCTED objects "
            "FAILS with 'Revit-DocumentCorruption'.  These controls hold, in turn, the ADD "
            "PATH, the OBJECT SHAPE/header/rep, and OUR VALUES constant against the same "
            "passing base, first for the PenWidthTableElem (X0/X1v/X1u -- the ladder's X1 "
            "class) then for ONE object-styles catalog row (C0/C1v/C1u -- the class R2 / "
            "X6a substitute wholesale)."),
        "base": "experiments/genesis/triage/K1.rvt (Autodesk's empty-project skeleton, viewer "
                "PASS; its descendants K3 / K4 / KD1 PASS)",
        "method": ("Every probe = K1 + ONE change, built by the SUBSTITUTION ENGINE itself "
                   "(tools/genesis_substitute.substitute with a one-class Rung) -- i.e. the "
                   "IDENTICAL add path the X-rungs use: our records appended via "
                   "rvt.commit.commit_new_elements (ElemTable row = fresh max episode, "
                   "original_id = the new id), the OLD element deleted via rvt.manipulate, "
                   "the ADocument registry leaf re-pointed old->new by the schema-typed "
                   "editor, Global/Latest re-encoded byte-exactly, save-unit 0 re-blocked, "
                   "and the engine's certification (validator 0 errors, structural proof, "
                   "registry parity, four-registry coherence, 0 NEW dangling ids).  What "
                   "differs between the three controls of a class is ONLY where the three "
                   "element records come from: X0/C0 = Autodesk's exact bytes (decoded and "
                   "re-encoded byte-identically -- ASSERTED at the original id -- with only "
                   "the element's own identity fields rebased to the new id); X1v/C1v = OUR "
                   "constructor fed the specimen's EXACT values (byte-identity ASSERTED and "
                   "the residual named to the bit); X1u/C1u = OUR constructor with OUR "
                   "values (everything structural pinned to the specimen)."),
        "reading_order": ["X0", "X1v (no upload: verdict = X0's)", "X1u", "C0", "C1v", "C1u"],
        "upload_batch": ("ONE round: X0, X1u, C0, C1v, C1u (5 files) + C0all + the addback "
                         "stream's un-uploaded R2s.  X1v needs no upload (byte-identical twin "
                         "of X0).  X0k / X1ua / X1ub are pre-built follow-ups (see 'when')."),
        "probes": probes,
        "optional_probes": opt,
        "decision_tree": {
            "X0 FAIL": ("THE ADD PATH corrupts a settings singleton: every X-rung is void until "
                        "fixed.  X0.json:build_info diffs our registration against K1's "
                        "(ElemTable row (0,976,976)->(ep,ep,ep) & original_id, record moved "
                        "to the unit end, id 2 -> 1,500,000, PenWidthTableInfo leaf -> 1.5M "
                        "id, identity scrub).  UPLOAD X0k: X0k PASS => the new-id / registry-"
                        "rewrite half; X0k FAIL => the record-append / ElemTable-row half."),
            "X0 PASS + X1u PASS": ("path fine, our width values fine => the ONLY variable "
                                   "left in the ladder's X1 is the six scale KEYS (our "
                                   "imperial 24..768 vs the specimen's metric 10..500).  If "
                                   "X1 FAILS: the scale-key set is audited (fix: emit valid "
                                   "denominators / follow the document's unit lineage).  If "
                                   "X1 PASSES: PenWidthTableElem is retired as a suspect."),
            "X0 PASS + X1u FAIL": ("our width VALUES are audited (0.13-8.0 mm ISO-128 vs "
                                   "Autodesk's 0.1-10.0): upload X1ua + X1ub to localize to "
                                   "the model vectors (96 doubles) vs perspective/draft (32); "
                                   "the constraint becomes a documented constant."),
            "X1v": ("NO upload: byte-identical twin of X0 (collapse_check).  Its value is the "
                    "recorded assertion: our constructor reproduces Autodesk's pen table "
                    "COMPLETELY (header + object + rep) given exact values -- so shape / "
                    "header / rep are exonerated by construction, and FINDING P1 stands: the "
                    "mm interface cannot express 8 of the 128 doubles (all the 9.0-mm pens), "
                    "the settings stream's 'byte-exact reproduction' test is a self-round-"
                    "trip, not identity-with-specimen."),
            "C0 FAIL": ("the add path corrupts a CATALOG row: with X0 also FAILING => the add "
                        "path generally; with X0 PASSING => the catalog-row registration "
                        "specifically (CategoryTracking m_gstyleId at a 1.5M id / a built-in "
                        "style at a high id band).  R2 / X6a inherit it."),
            "C0 PASS + C1v FAIL": ("THE ELEMENTHEADER FLAG WORD IS AUDITED for built-in "
                                   "object-style rows -- our catalog constructor's single "
                                   "preset 0x400001e (vs SIX presets in the accepted catalog, "
                                   "findings G1) can ALONE explain R2 / X6a; because G2 shows "
                                   "the presets are per-document not per-category, mine the "
                                   "valid-combination rule from findings.json and emit "
                                   "per-row presets (+ the CellList{PatternHelper} 790 rows "
                                   "carry -- the next single-variable twin)."),
            "C0 PASS + C1v PASS + C1u FAIL": ("our object-style VALUES are audited (pen "
                                              "number / COLORREF): split pen vs colour with "
                                              "a twin pair (seconds with this tool)."),
            "C0 PASS + C1v PASS + C1u PASS": ("the SINGLE-ROW substitution is FULLY "
                                              "EXONERATED -- path, shape, header preset and "
                                              "values are all reader-clean for one catalog "
                                              "row => R2's / X6a's failure is a WHOLE-"
                                              "CATALOG effect.  UPLOAD C0all (all 1,348 "
                                              "referrer-free built-in rows, Autodesk's exact "
                                              "bytes, re-inserted at new ids through our "
                                              "path) + R2s (the un-uploaded original-id "
                                              "mechanics control): C0all PASS + R2s PASS => "
                                              "R2's killer is a MULTI-row property of OUR "
                                              "rows (our one preset / ink colour across the "
                                              "whole table); C0all FAIL => the add path "
                                              "breaks AT SCALE (mass id motion / mass "
                                              "CategoryTracking rewrite / 1,348 fresh-"
                                              "episode rows), not per row."),
            "ALL SIX PASS": ("path (X0, C0), shape/header (X1v, C1v) and values (X1u, C1u) are "
                             "reader-clean for BOTH classes => the constructed-object divide "
                             "is NOT per-object for these classes; it is a MULTI-object / "
                             "scale / interaction property (X5 = 51 more singleton classes at "
                             "once; R2 = 1,348 rows at once).  The instrument to run next is "
                             "the same three-way separation applied cumulatively (C0all "
                             "first), and per-class trios for the X2..X5 constellation."),
        },
        "findings": ("experiments/genesis/controls/findings.json + "
                     "docs/inbox/genesis-controls.md: P1 (pen doubles not mm-derived; "
                     "constructor cannot reproduce 8 of 128 doubles via mm), P2 (pen "
                     "header/rep/object Autodesk-identical => X1v == X0), G1 (six header "
                     "presets + 790 cell lists in the accepted catalog vs our one preset / "
                     "no cell), G2 (presets & cell lists are NOT per-category constants -- "
                     "per-document artefacts, every combination reader-accepted)."),
        "reproduce": "cd tekton && .venv/bin/python tools/genesis_controls.py --with-optional",
    }
    p = os.path.join(out_dir, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"[manifest] -> {_relp(p)}")
    return p


# ===========================================================================
# 10. main
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--only", default="", help="comma list of probe names (X0,X1v,...)")
    ap.add_argument("--with-optional", action="store_true",
                    help="also build C0all, X0k, X1ua, X1ub")
    ap.add_argument("--out", default=CONTROLS, help="output directory")
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--findings-only", action="store_true")
    ap.add_argument("--no-findings", action="store_true")
    ap.add_argument("--keep-intermediates", action="store_true")
    args = ap.parse_args(argv)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    if args.findings_only:
        write_findings(out_dir)
        return 0
    if args.manifest_only:
        write_probes_manifest(out_dir)
        return 0

    names = [n.strip() for n in args.only.split(",") if n.strip()]
    if names:
        selected = [n for n in names if n != "X0k"]
        want_x0k = "X0k" in names
    else:
        selected = [r.name for r in RUNGS]
        want_x0k = args.with_optional
        if args.with_optional:
            selected += [r.name for r in OPTIONAL_RUNGS]

    t0 = time.time()
    results: Dict[str, str] = {}
    for name in selected:
        rung = rung_by_name(name)
        rep = GS.substitute(rung, K1, out_dir, keep_intermediates=args.keep_intermediates)
        results[name] = rep.get("verdict", "?")
    if want_x0k:
        rep = build_X0k_file(out_dir)
        results["X0k"] = rep.get("verdict", "?")
    if not args.no_findings:
        write_findings(out_dir)
    write_probes_manifest(out_dir)

    log("\n== summary")
    for n, v in results.items():
        log(f"   {n:6s} {v}")
    coll = collapse_check(out_dir)
    if coll:
        log(f"   X1v==X0 collapse: {coll['content_identical']} {coll['identical']}")
    log(f"   ({round(time.time() - t0, 1)}s total)")
    return 0 if all(v == "VALID" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
