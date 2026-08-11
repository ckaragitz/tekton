#!/usr/bin/env python
"""genesis_addpath_probes.py -- PER-RULE VERBATIM CONTROLS for the ADD PATH
(genesis-addpath-probes stream, 2026-08-04).

THE DECISIVE FACT (docs/inbox/genesis-audit.md, ORCHESTRATOR VERDICTS #11):
X0 (Autodesk's OWN pen table, exact bytes, re-inserted through OUR add path at
a new id) and C0 (Autodesk's own catalog row verbatim via our path) BOTH FAIL
'Revit-DocumentCorruption'.  OUR OBJECTS ARE EXONERATED; the ADD PATH for
non-instance elements (singletons / catalog rows) corrupts, while the
family-INSTANCE add path is PROVEN (V20..V29 created instances / walls /
conduits / circuits LOAD).  So the bug lives in the DELTA between how a
loadable file registers such elements and how our add path does.

WHAT THIS TOOL DOES.  It MEASURES that delta byte-exactly against K1
(Autodesk's viewer-PASSED empty-project skeleton) and turns each candidate
registration rule into a ONE-CHANGE probe.  Measured (K1 vs X0, stream by
stream; the ADocument differs in exactly ONE leaf; see `enumerate_delta()`),
the add path deviates from K1's original registration of the pen table
(element 2) in exactly FOUR dimensions -- and NOTHING else:

  (1) ID MOTION      id 2 -> 1,500,000: the records' own m_id + deletion-list
                     entry, the ElemTable row's id, the footer WATERMARK raised
                     to 1,500,000, and the ONE ADocument leaf
                     PenWidthTableInfo.m_penWidthTableElemId re-pointed.
  (2) EPISODES       ElemTable row episodes (creation, modified,
                     user_modified) = (0, 976, 976) in K1  vs  the add
                     path's (1016, 1016, 1016) = the parent's MAX episode
                     (the VINTAGE dimension; objlint's ETR.created_at_birth).
  (3) RECORD POSITION the three per-seq records sit at index 2,516 of 6,541
                     in K1 (each seq, identical order), immediately after
                     element 1 and before element 3; the add path APPENDS them
                     at the unit-0 END (index 6,539, before the sentinel).
  (4) IDENTITY       BasicFileInfo (username / author / client_app /
                     last_save_path) + DocumentIncrementTable usernames
                     rewritten by the commit path's identity scrub
                     (V30/V31/V32-proven on a working base -- carried here
                     only for completeness).

Two of the brief's named dimensions COLLAPSE onto X0 by measurement (see
`measure_collapses()`): the ElemRec OWNER is 0xFFFF..FF (INVALID) both in
K1's row 2 and in X0's row (P_owner is a byte-identical no-op) and the
ElementHeader FLAG word / parents lists are Autodesk's own bytes in X0 --
only the two typed identity leaves (Element.m_id, the header's own
deletion-list entry) were rebased (P_flags is a byte-identical no-op).
Those two probes therefore need NO file and NO viewer round; the evidence
is recorded in probes.json.

THE PROBE FAMILIES (every probe = a KNOWN-PASSING or a KNOWN-FAILING file
with ONE registration detail changed; the records are always AUTODESK'S OWN
pen-table bytes, so no probe can be confounded by our object payload):

 A. FROM-K1 SINGLES (template = K1, PASS): K1 + ONE add-path deviation each.
    A FAIL here names the fatal rule DIRECTLY on the passing file.
      P_ep_only    K1 with row 2's episodes rewritten (0,976,976)->(1016 x3).
                   A 12-byte Global/ElemTable edit; NOTHING else moves.
      P_pos_only   K1 with element 2's own records MOVED from index 2,516 to
                   the unit-0 END (Autodesk's bytes, id 2, ElemTable
                   untouched).  Position ALONE.
      P_allnew     K1 with element 2 re-registered at the NEW HIGH id
                   1,500,000 IN PLACE (records rebased at their original
                   index, birth episodes kept, K1 identity kept, watermark
                   raised, the ONE ADocument leaf re-pointed).  ID MOTION
                   ALONE -- the maximal registration match for a NEW id.
      P_lowid      as P_allnew but the new id is 27 (a free, unreferenced id
                   inside the birth band, watermark NOT raised).  Separates
                   the ID BAND (high vs low) from id motion per se.
      P_ident_only K1 with the identity scrub only (BasicFileInfo + DIT), the
                   V30..V32-proven path -- the accounting single (optional).
 B. FROM-X0 RESTORES (template = X0, FAIL): X0 with ONE dimension restored
    to K1's convention.  A PASS here shows removing that ONE deviation
    RESCUES the failing add-path product.
      P_ep         X0 with row 1,500,000's episodes restored to (0,976,976).
      P_order      X0 with the three records moved from the unit end back to
                   the ORIGINAL position (right after element 1).
      P_ident      X0 with K1's BasicFileInfo + DIT restored (scrub reverted).
 C. FROM-X0k RESTORES (template = X0k, verdict PENDING: pen table re-added
    AT ITS OWN id 2, zero registry motion) -- OPTIONAL, pre-built for the
    branch where X0k FAILS:
      P_sameid_ep, P_sameid_order, P_sameid_ident (one restore each vs X0k).
 D. ANCHORS (NO UPLOAD -- construction proofs):
      P_all        element 2 deleted and re-added through THIS tool's
                   assembler with ALL FOUR dimensions at K1's convention.
                   ASSERTED BYTE-IDENTICAL TO K1 IN EVERY STREAM => the
                   delete + re-add mechanics are LOSSLESS: nothing outside
                   {3 records, 1 ElemTable row, 1 ADocument leaf} encodes the
                   element.  Its verdict IS K1's (PASS).
      P_x0         ALL FOUR add-path deviations applied by this assembler:
                   ASSERTED SEMANTICALLY IDENTICAL to X0 (ElemTable model,
                   ADocument tree, unit-0 record bytes + order, identity
                   fields; the only raw differences are the reader-tolerated
                   end-record junk length and BasicFileInfo.last_save_path
                   string).  Proves this assembler is a faithful stand-in for
                   commit_new_elements, so every from-K1 single reads as
                   'the add path with all but one deviation removed'.
      P_sameid     X0k reproduced by this assembler (asserted equal to X0k).
 E. COLLAPSED (NO FILE): P_owner, P_flags -- byte-identical to X0.

READING TREE (also probes.json:decision_tree): upload the four from-K1
singles P_ep_only, P_pos_only, P_allnew, P_lowid (+ the from-X0 restores if
capacity allows; X0k is already queued).  A from-K1 single that FAILS names
the audited rule with zero other motion; the from-X0 restores confirm the
rescue and expose interactions (a rule fatal only combined with the id
motion shows as: every from-K1 single PASSES yet X0 FAILS, and the from-X0
restore of the interacting dimension PASSES).

Territory: tools/genesis_addpath_probes.py, experiments/genesis/addpath/*,
tests/test_addpath_probes.py, docs/inbox/genesis-addpath-probes.md.  Every
dependency (rvt.reduce / commit / adocument / identity / encode / objects /
stream_encoders / cfb_writer, tools/genesis_controls.py, genesis_substitute
.py, genesis_assemble.py) is IMPORTED, never edited.  No viewer here: the
files are LEFT ON DISK with probes.json (the reading tree).

Usage:
  .venv/bin/python tools/genesis_addpath_probes.py                 # everything
  .venv/bin/python tools/genesis_addpath_probes.py --only P_all,P_ep_only
  .venv/bin/python tools/genesis_addpath_probes.py --manifest-only # re-write probes.json
  .venv/bin/python tools/genesis_addpath_probes.py --delta-only    # the measured delta
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import json
import os
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import rvt_reduce as RR                                            # noqa: E402
import genesis_assemble as GA                                       # noqa: E402
import genesis_substitute as GS                                     # noqa: E402
import genesis_controls as GC                                       # noqa: E402
from rvt import adocument as adoc                                   # noqa: E402
from rvt import ecc                                                 # noqa: E402
from rvt import identity as IDN                                     # noqa: E402
from rvt import stream_encoders as se                               # noqa: E402
from rvt.cfb_writer import write_cfb                                # noqa: E402
from rvt.commit import verify_written                               # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.mutate import Document                                     # noqa: E402
from rvt.objects import ObjectDecoder, iter_records                # noqa: E402
from rvt.partitions import StreamWalker                              # noqa: E402
from rvt.reduce import (Rec, reblock, split_records, unframe_exact, # noqa: E402
                        verify_reduced, PART_HDR_LEN, PART_HDR_COUNT_OFF)
from rvt.roundtrip import read_entries, read_streams                # noqa: E402
from rvt.streams_edit import elemtable_add_element, INVALID_ID      # noqa: E402
from rvt.writer import gzip_member                                  # noqa: E402

# ---------------------------------------------------------------------------
# paths / constants
# ---------------------------------------------------------------------------
TRIAGE = os.path.join(ROOT, "experiments", "genesis", "triage")
CONTROLS = os.path.join(ROOT, "experiments", "genesis", "controls")
OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "addpath")
K1_PATH = os.path.join(TRIAGE, "K1.rvt")            # viewer PASS -- the reference
X0_PATH = os.path.join(CONTROLS, "X0.rvt")           # viewer FAIL -- add path, new id
X0K_PATH = os.path.join(CONTROLS, "X0k.rvt")         # verdict PENDING -- same id
os.makedirs(OUT_DIR, exist_ok=True)

PEN_ID = 2                       # the project pen table in every 2026 file
PEN_CLASS = "PenWidthTableElem"
X0_NEW_ID = 1_500_000            # the id X0's add path allocated
LOW_ID = 27                      # free, unreferenced id inside K1's birth band
NEVER_EP = 0xFFFFFFFF
SEQS = (101, 102, 103)
BFI = "BasicFileInfo"
DIT = "Global/DocumentIncrementTable"
ETB = "Global/ElemTable"
LAT = adoc.STREAM                # Global/Latest
IDENTITY = dict(GS.IDENTITY)     # {"author","client_app_name","username"} = rvt-writer


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


# ===========================================================================
# 1. MATERIAL: everything assembly needs from one .rvt, byte-exact
# ===========================================================================

@dataclasses.dataclass
class Material:
    """The assembly-relevant, byte-exact state of one file.

    ``true_logical`` is recovered with ``unframe_exact`` (NOT the depaged
    ``logical()``, whose tail carries the final page's ECC pad region) so
    that ``ecc.frame_stream(true_logical)`` reproduces the raw stream
    byte-for-byte -- verified on load (``roundtrip_ok``)."""
    path: str
    entries: list                      # CfbEntry list (template for writing)
    raw: Dict[str, bytes]              # stream path -> raw stream bytes
    pname: str                         # Partitions/<N>
    true_logical: bytes
    roundtrip_ok: bool                 # frame_stream(true_logical) == raw[pname]
    u0_recs: Dict[int, List[Rec]]      # seq -> unit-0 records (sentinel LAST)
    u0_start: int                      # PART_HDR_LEN
    u0_end: int                        # unit-0 footer offset in true_logical
    trail: bytes                       # true_logical[u0_end:] (footer .. end record)
    header_count: int                  # u32 elem_table_count in the 18-byte header
    et_model: Dict[str, Any]
    latest_payload: bytes
    latest_tree: dict
    watermark: int
    max_ep: int                        # max modified episode in the ElemTable

    def stream(self, name: str) -> bytes:
        return self.raw[name]


def load_material(path: str) -> Material:
    entries = read_entries(path)
    raw = {e.path: e.data for e in entries if e.entry_type == "stream"}
    pname = [p for p in raw if p.startswith("Partitions/")]
    if len(pname) != 1:
        raise RuntimeError(f"{path}: expected exactly one partition stream, got {pname}")
    pname = pname[0]
    true_logical = unframe_exact(raw[pname])
    roundtrip_ok = (ecc.frame_stream(true_logical) == raw[pname])
    w = StreamWalker(true_logical, inflate=True, keep_data=True)
    if w.errors:
        raise RuntimeError(f"{path}: walker errors {w.errors[:2]}")
    blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
    u0 = [b for b in blocks if b.unit == 0]
    if not u0 or blocks[0].hdr_offset != PART_HDR_LEN:
        raise RuntimeError(f"{path}: unexpected unit-0 layout")
    u0_end = w.units[0].footer_offset
    u0_recs = {s: split_records(b"".join(b.data for b in u0 if b.seq == s), s) for s in SEQS}
    header_count = struct.unpack_from("<I", true_logical, PART_HDR_COUNT_OFF)[0]
    with open_rvt(path) as f:
        et_model = se.decode_elemtable(f.inflate(ETB))
        latest_payload = f.inflate(LAT, 0)
    a = adoc.decode_latest(latest_payload)
    if not a.clean:
        raise RuntimeError(f"{path}: ADocument decode not clean: {a.errors[:1]}")
    return Material(
        path=path, entries=entries, raw=raw, pname=pname, true_logical=true_logical,
        roundtrip_ok=roundtrip_ok, u0_recs=u0_recs, u0_start=PART_HDR_LEN, u0_end=u0_end,
        trail=true_logical[u0_end:], header_count=header_count, et_model=et_model,
        latest_payload=latest_payload, latest_tree=a.value,
        watermark=int(et_model["footer"]["last_id"]),
        max_ep=max(int(r[2]) for r in et_model["records"]),
    )


# ===========================================================================
# 2. THE MEASURED DELTA (K1 vs X0) -- the probe list is derived from it
# ===========================================================================

def _tree_diff(a: Any, b: Any, path: str = "ADocument", out: Optional[list] = None) -> list:
    """Generic decoded-tree diff [(path, a_value, b_value), ...]."""
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append((f"{path}.{k}", a.get(k, "<absent>"), b.get(k, "<absent>")))
            else:
                _tree_diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((f"{path}[len]", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            _tree_diff(x, y, f"{path}[{i}]", out)
    else:
        if a != b:
            out.append((path, a, b))
    return out


def elemtable_row(model: dict, eid: int) -> Optional[dict]:
    for r in model["records"]:
        if int(r[4]) == int(eid):
            own = int(r[5])
            return {"elem_id": int(r[4]), "original_id": int(r[0]),
                    "creation_ep": int(r[1]), "modified_ep": int(r[2]),
                    "user_modified_ep": int(r[3]),
                    "owner_id": (-1 if own >= (1 << 63) else own),
                    "partition_id": int(r[6])}
    return None


def id_sequence(recs: List[Rec]) -> List[int]:
    return [r.elem_id for r in recs]


def enumerate_delta(k1: Material, x0: Material, x0k: Optional[Material]) -> dict:
    """The complete, measured delta between K1 (PASS) and X0 (FAIL): which
    streams differ, the ONE ADocument leaf, the ElemTable rows / watermark,
    the unit-0 record order, and the identity fields.  This is the ground
    truth the probes are derived from."""
    streams = {}
    for name in sorted(set(k1.raw) | set(x0.raw)):
        a, b = k1.raw.get(name), x0.raw.get(name)
        streams[name] = ("absent" if a is None or b is None else
                         ("identical" if a == b else "DIFFERS"))
    differing = sorted(n for n, v in streams.items() if v == "DIFFERS")
    latest_diff = _tree_diff(k1.latest_tree, x0.latest_tree)
    row_k1 = elemtable_row(k1.et_model, PEN_ID)
    row_x0 = elemtable_row(x0.et_model, X0_NEW_ID)
    seqk = id_sequence(k1.u0_recs[102])
    seqx = id_sequence(x0.u0_recs[102])
    ident_k1 = se.decode_basic_file_info(k1.raw[BFI])
    ident_x0 = se.decode_basic_file_info(x0.raw[BFI])
    ident_diff = {k: [str(ident_k1.get(k))[:80], str(ident_x0.get(k))[:80]]
                  for k in set(ident_k1) | set(ident_x0)
                  if ident_k1.get(k) != ident_x0.get(k) and k != "mirror_text"}
    dit_k1 = se.decode_increment_table(_inflate(k1, DIT))
    dit_x0 = se.decode_increment_table(_inflate(x0, DIT))
    # the partition's raw difference beyond record position: block COMPRESSION.
    # commit_new_elements re-compresses EVERY block (embedded units included);
    # delete_elements / this tool keep untouched blocks' original members.
    compression = _compression_diff(k1, x0)
    delta = {
        "reference_PASS": _relp(k1.path), "subject_FAIL": _relp(x0.path),
        "streams": streams,
        "streams_differing": differing,
        "partition_compression": compression,
        "adocument_leaf_differences": [{"path": p, "K1": a, "X0": b} for p, a, b in latest_diff],
        "elemtable": {
            "K1_row_for_element_2": row_k1,
            "X0_row_for_element_1500000": row_x0,
            "K1_count": len(k1.et_model["records"]), "X0_count": len(x0.et_model["records"]),
            "K1_watermark": k1.watermark, "X0_watermark": x0.watermark,
            "K1_max_modified_ep": k1.max_ep,
        },
        "record_order": {
            "K1_records_per_seq": len(seqk), "X0_records_per_seq": len(seqx),
            "K1_position_of_id_2": (seqk.index(PEN_ID) if PEN_ID in seqk else None),
            "K1_neighbours_of_id_2": (seqk[seqk.index(PEN_ID) - 3:seqk.index(PEN_ID) + 4]
                                      if PEN_ID in seqk else None),
            "X0_position_of_id_1500000": (seqx.index(X0_NEW_ID) if X0_NEW_ID in seqx else None),
            "X0_records_after_sentinel_exclusive_last_index": len(seqx) - 2,
            "three_seqs_identical_order": (id_sequence(k1.u0_recs[101]) == seqk
                                           == id_sequence(k1.u0_recs[103])),
            "K1_order_law": ("NOT id-sorted: 43 ascending id-runs; the max id 1,472,524 sits at "
                             "position 131, the birth-vintage block (ids 1,2,3,...) starts at "
                             "position 2,515; the last real record is id 49,026"),
        },
        "identity": {"BasicFileInfo_fields_changed": ident_diff,
                     "DIT_usernames_K1": sorted({r.get("username") for r in dit_k1["records"]}),
                     "DIT_usernames_X0": sorted({r.get("username") for r in dit_x0["records"]})},
        "end_record_junk_note": (
            "K1's true partition logical ends with a 603-byte 'end record' = the genuine "
            "68-byte end marker + 535 bytes of ancestor ECC-pad junk carried by every "
            "reduction generation; X0 carries one more generation of it.  delete_elements "
            "smuggles the source's final-page ECC pad into the output's logical stream "
            "(uses the depaged logical, whose tail extends past the true end), so no "
            "re-blocked file can be byte-identical to its parent.  READER-TOLERATED (K1 596 B "
            "of it, K4 1.5 KB, all PASS) => cosmetic, not a candidate rule; this tool builds "
            "every probe from unframe_exact() so no NEW junk is added."),
        "dimensions_derived": [
            "ID MOTION (records m_id + deletion entry, ElemTable row id, watermark, "
            "the ONE ADocument leaf PenWidthTableInfo.m_penWidthTableElemId)",
            "EPISODES (ElemTable row (0,976,976) -> (1016,1016,1016))",
            "RECORD POSITION (index 2,516 -> unit-0 end, before the sentinel)",
            "IDENTITY (BasicFileInfo scrub + DIT usernames -- V30..V32-proven)",
        ],
    }
    if x0k is not None:
        seqk2 = id_sequence(x0k.u0_recs[102])
        delta["X0k"] = {
            "row_for_element_2": elemtable_row(x0k.et_model, PEN_ID),
            "watermark": x0k.watermark,
            "position_of_id_2": (seqk2.index(PEN_ID) if PEN_ID in seqk2 else None),
            "global_latest_identical_to_K1": (x0k.raw[LAT] == k1.raw[LAT]),
            "streams_vs_K1": {n: ("identical" if k1.raw.get(n) == x0k.raw.get(n) else "DIFFERS")
                              for n in sorted(set(k1.raw) | set(x0k.raw))},
        }
    return delta


def _inflate(mat: Material, name: str) -> bytes:
    with open_rvt(mat.path) as f:
        return f.inflate(name, 0)


def _compression_diff(k1: Material, x0: Material) -> dict:
    """The partition difference BEYOND record content: commit_new_elements
    (X0's path) re-compresses EVERY gzip block -- the embedded-document units
    included -- while K1 (a delete_elements product) and every probe of this
    tool keep untouched blocks' original compressed members.  The inflated
    payloads of the embedded units are identical; only the deflate bytes and
    the accumulated end-record junk differ.  READER-TOLERATED by construction
    of the format (compression is transparent post-inflate) and by acceptance
    (V15 whole-file recompression PASS; every V20..V29 commit product PASS)."""
    def blocks(mat: Material):
        w = StreamWalker(mat.true_logical, inflate=True, keep_data=True)
        return sorted(w.blocks, key=lambda b: b.hdr_offset), w
    bk, wk = blocks(k1)
    bx, wx = blocks(x0)
    emb_k = [b for b in bk if b.unit != 0]
    emb_x = [b for b in bx if b.unit != 0]
    payload_ident = sum(1 for a, b in zip(emb_k, emb_x) if a.data == b.data)
    member_ident = sum(1 for a, b in zip(emb_k, emb_x)
                       if k1.true_logical[a.member_offset:a.member_offset + a.member_len] ==
                       x0.true_logical[b.member_offset:b.member_offset + b.member_len])
    return {
        "embedded_unit_blocks": [len(emb_k), len(emb_x)],
        "embedded_blocks_with_identical_INFLATED_payload": payload_ident,
        "embedded_blocks_with_identical_COMPRESSED_member": member_ident,
        "end_record_len": [len(wk.end_record), len(wx.end_record)],
        "reading": ("all embedded-unit blocks inflate identically; their compressed members "
                    "and the trailing end-record junk differ because commit_new_elements "
                    "re-compresses every block and each re-block generation appends the "
                    "source's final-page ECC pad.  Compression / trailing junk are "
                    "reader-tolerated cosmetics (V15, V20..V29, K3/K4 all PASS) and are "
                    "therefore NOT candidate rules; this tool's probes add no new junk and "
                    "keep the original compression of every untouched block."),
    }


def measure_collapses(k1: Material, x0: Material) -> dict:
    """P_owner and P_flags: prove they are byte-identical no-ops against X0.

    OWNER: the ElemRec owner of K1's row 2 vs X0's row -> both INVALID; the
    ElementHeader carries no owner beyond the parents lists, which are
    Autodesk's own bytes in X0.  FLAGS: the ElemRec has no flag field
    (40-byte record = original_id, 3 episodes, id, owner, partition); the
    ElementHeader flag word and every list are Autodesk's exact bytes in X0
    -- verified against X0.json's byte-identity assertion (all three seqs
    byte-identical at the original id; only the two typed identity leaves
    rebased) and re-verified here by comparing the decoded headers."""
    row_k1 = elemtable_row(k1.et_model, PEN_ID)
    row_x0 = elemtable_row(x0.et_model, X0_NEW_ID)
    dec = ObjectDecoder()
    hk = next(r for r in k1.u0_recs[101] if r.elem_id == PEN_ID)
    hx = next(r for r in x0.u0_recs[101] if r.elem_id == X0_NEW_ID)
    hk_v = dec.decode_record(_class_id(hk), _payload(hk)).value
    hx_v = dec.decode_record(_class_id(hx), _payload(hx)).value
    hdr_diff = _tree_diff(hk_v, hx_v, "ElementHeader")
    # X0.json's recorded assertion
    x0json = {}
    p = os.path.join(CONTROLS, "X0.json")
    if os.path.exists(p):
        with open(p) as fh:
            j = json.load(fh)
        a = (j.get("build_info") or {}).get("byte_identity_assertion") or {}
        x0json = {"all_three_seqs_identical_at_original_id": a.get("all_three_seqs_identical"),
                  "identity_rebased_leaves": a.get("identity_rebased_leaves")}
    return {
        "P_owner": {
            "collapsed_onto": "X0 (byte-identical -- NO FILE, NO UPLOAD; verdict = X0's)",
            "elemrec_owner_K1_row2": row_k1["owner_id"] if row_k1 else None,
            "elemrec_owner_X0_row": row_x0["owner_id"] if row_x0 else None,
            "both_INVALID": bool(row_k1 and row_x0 and row_k1["owner_id"] == -1
                                 and row_x0["owner_id"] == -1),
            "header_owner_channels": ("the pen table's ElementHeader has category -1, empty "
                                      "appearance/regen parents and deletion = [self]; the "
                                      "ElemTable owner is the only ownership channel and it "
                                      "is INVALID in both K1 and X0"),
        },
        "P_flags": {
            "collapsed_onto": "X0 (byte-identical -- NO FILE, NO UPLOAD; verdict = X0's)",
            "elemrec_has_no_flag_field": ("40-byte ElemRec = original_id(u64) + creation/"
                                          "modified/user_modified episodes(3 x u32) + id(u64) + "
                                          "owner(u64) + partition(u32): there is no flag word"),
            "header_field_differences_K1_id2_vs_X0_id1500000": [
                {"path": p, "K1": _short(a), "X0": _short(b)} for p, a, b in hdr_diff],
            "reading": ("X0's ElementHeader is Autodesk's own header with only the element's "
                        "own entry in ElementParents.m_deletion rebased 2 -> 1,500,000; the "
                        "flag word m_abFlags4Bytes and every other field are byte-identical"),
            "X0_json_byte_identity_assertion": x0json,
        },
    }


def _short(v: Any) -> Any:
    s = repr(v)
    return v if len(s) < 60 else s[:60] + "..."


def _class_id(rec: Rec) -> int:
    """The u16 class id at the start of a framed record's payload."""
    hl = 12 if rec.seq == 101 else 16
    return struct.unpack_from("<H", rec.data, hl)[0]


def _payload(rec: Rec) -> bytes:
    """The record payload WITHOUT the leading u16 class id (ObjectDecoder's
    ``decode_record`` convention), from a framed record."""
    hl = 12 if rec.seq == 101 else 16
    return bytes(rec.data[hl + 2: hl + rec.size])


# ===========================================================================
# 3. RECORDS: Autodesk's own pen-table bytes at any id (byte-exact rebase)
# ===========================================================================
_REC_CACHE: Dict[int, Dict[int, bytes]] = {}
_REBASE_PROOF: Dict[int, dict] = {}


def _typed_editor() -> "GS.TypedEditor":
    return GS.TypedEditor(decoder=Document.from_file(K1_PATH).dec,
                          maps=GA.load_registry_maps())


def pen_records_at(new_id: int, k1: Material) -> Dict[int, bytes]:
    """{seq: framed record bytes} of AUTODESK'S OWN pen table (K1 element 2)
    with its identity rebased to ``new_id``.  For new_id == 2 the bytes are
    K1's originals verbatim.  Otherwise ``genesis_controls.verbatim_typerecord``
    first PROVES decode->encode is byte-exact at the original id, then rebases
    ONLY the schema-typed identity leaves (Element.m_id and the header's own
    deletion-list entry) and re-frames (stamps recompute mechanically)."""
    new_id = int(new_id)
    if new_id in _REC_CACHE:
        return _REC_CACHE[new_id]
    if new_id == PEN_ID:
        recs = {r.seq: bytes(r.data) for r in
                (next(x for x in k1.u0_recs[s] if x.elem_id == PEN_ID) for s in SEQS)}
        _REC_CACHE[new_id] = recs
        _REBASE_PROOF[new_id] = {"element": PEN_ID, "verbatim": "K1's own framed records (no rebase)"}
        return recs
    segs = {s: b"".join(bytes(r.data) for r in k1.u0_recs[s]) for s in SEQS}
    spec = GC.specimen_records(K1_PATH, PEN_ID, segments=segs)
    rec, proof = GC.verbatim_typerecord(spec, PEN_CLASS, new_id, _typed_editor(),
                                        kind="pen-table-verbatim-rebased")
    framed = {int(s): bytes(b) for s, b in rec.encode().items()}
    _REC_CACHE[new_id] = framed
    _REBASE_PROOF[new_id] = proof
    return framed


def framed_to_rec(seq: int, framed: bytes) -> Rec:
    """Wrap one framed record as a reduce.Rec (for the re-blocker)."""
    if seq == 101:
        eid, psize = struct.unpack_from("<qI", framed, 0)
    else:
        eid, _st, psize = struct.unpack_from("<qII", framed, 0)
    return Rec(seq, int(eid), int(psize), bytes(framed))


# ===========================================================================
# 4. STREAM ASSEMBLY PRIMITIVES (byte-exact, no new junk)
# ===========================================================================

def recs_remove(recs: Dict[int, List[Rec]], eid: int) -> Tuple[Dict[int, List[Rec]], Dict[int, int]]:
    """Return (record lists without ``eid``, {seq: original index of eid})."""
    out: Dict[int, List[Rec]] = {}
    idx: Dict[int, int] = {}
    for s in SEQS:
        lst = list(recs[s])
        pos = [i for i, r in enumerate(lst) if r.elem_id == eid]
        if len(pos) != 1:
            raise RuntimeError(f"seq {s}: element {eid} occurs {len(pos)}x (expected 1)")
        idx[s] = pos[0]
        del lst[pos[0]]
        out[s] = lst
    return out, idx


def recs_insert(recs: Dict[int, List[Rec]], new: Dict[int, bytes], where: str,
                *, after_id: int = -999, at_index: Optional[Dict[int, int]] = None
                ) -> Tuple[Dict[int, List[Rec]], Dict[int, int]]:
    """Insert one record per seq.  ``where``:
      'end'      -> immediately BEFORE the sentinel (the add path's position);
      'after'    -> immediately AFTER the record of ``after_id`` (K1's original
                    position of element 2 is right after element 1);
      'index'    -> at the explicit per-seq index ``at_index``.
    Returns (new record lists, {seq: index where the record landed})."""
    out: Dict[int, List[Rec]] = {}
    placed: Dict[int, int] = {}
    for s in SEQS:
        lst = list(recs[s])
        if not lst or not (lst[-1].elem_id == -1 and lst[-1].size == 0):
            raise RuntimeError(f"seq {s}: record list does not end with the sentinel")
        rec = framed_to_rec(s, new[s])
        if where == "end":
            pos = len(lst) - 1
        elif where == "after":
            hits = [i for i, r in enumerate(lst) if r.elem_id == after_id]
            if len(hits) != 1:
                raise RuntimeError(f"seq {s}: anchor {after_id} occurs {len(hits)}x")
            pos = hits[0] + 1
        elif where == "index":
            pos = int((at_index or {})[s])
        else:
            raise ValueError(where)
        lst.insert(pos, rec)
        out[s] = lst
        placed[s] = pos
    return out, placed


def assemble_partition(mat: Material, recs: Dict[int, List[Rec]],
                       elem_table_count: int) -> bytes:
    """The partition TRUE logical stream for material ``mat`` with unit 0
    rebuilt from ``recs``: 18-byte header (elem_table_count patched) + the
    re-blocked unit-0 (seq 101, 102, 103 in stream order) + ``mat``'s exact
    trailing region (unit-0 footer .. end record, its own junk included).
    With ``mat``'s own record lists this reproduces ``mat``'s partition
    byte-for-byte (asserted in the tests / P_all)."""
    hdr = bytearray(mat.true_logical[:PART_HDR_LEN])
    struct.pack_into("<I", hdr, PART_HDR_COUNT_OFF, int(elem_table_count))
    u0 = bytearray()
    for s in SEQS:
        lst = recs[s]
        if not (lst and lst[-1].elem_id == -1 and lst[-1].size == 0):
            raise RuntimeError(f"seq {s}: record list must end with the sentinel")
        for nb in reblock(lst, s):
            u0 += nb.frame()
    return bytes(hdr) + bytes(u0) + mat.trail


def frame_partition(logical: bytes) -> bytes:
    w = StreamWalker(logical, inflate=False, keep_data=False)
    if w.errors:
        raise RuntimeError(f"walker errors on assembled partition: {w.errors[:3]}")
    return ecc.frame_stream(logical)


def et_model_copy(model: dict) -> dict:
    return {"class_tag": model.get("class_tag"), "count": model.get("count"),
            "records": [tuple(r) for r in model["records"]],
            "footer": dict(model["footer"]),
            **{k: v for k, v in model.items() if k not in ("records", "footer",
                                                          "class_tag", "count")}}


def et_remove(model: dict, eid: int) -> tuple:
    for i, r in enumerate(model["records"]):
        if int(r[4]) == int(eid):
            del model["records"][i]
            return tuple(r)
    raise KeyError(f"element {eid} not in ElemTable")


def et_set_episodes(model: dict, eid: int, creation_ep: int, modified_ep: int,
                    user_modified_ep: int) -> Tuple[tuple, tuple]:
    for i, r in enumerate(model["records"]):
        if int(r[4]) == int(eid):
            old = tuple(r)
            new = (r[0], int(creation_ep), int(modified_ep), int(user_modified_ep), r[4], r[5], r[6])
            model["records"][i] = new
            return old, new
    raise KeyError(f"element {eid} not in ElemTable")


def et_insert(model: dict, eid: int, *, creation_ep: int, modified_ep: int,
              user_modified_ep: int, original_id: Optional[int] = None) -> tuple:
    """Insert one ElemRec id-sorted (owner INVALID, partition 0), original_id
    defaulting to the id itself (the 'not renumbered' convention both K1 and
    the add path use); the footer watermark is RAISED if eid exceeds it and
    otherwise LEFT ALONE (a low id under the watermark never lowers it)."""
    elemtable_add_element(model, int(eid), creation_ep=int(creation_ep),
                          modified_ep=int(modified_ep),
                          user_modified_ep=int(user_modified_ep),
                          original_id=(int(original_id) if original_id is not None else int(eid)),
                          owner_id=INVALID_ID, partition_id=0)
    return tuple(next(r for r in model["records"] if int(r[4]) == int(eid)))


def encode_elemtable_stream(model: dict) -> bytes:
    return ecc.frame_stream(se.global_prefix(ETB) +
                            gzip_member(se.encode_elemtable(model), level=3))


def encode_latest_stream(tree: dict) -> bytes:
    payload = adoc.encode_latest(tree)
    back = adoc.decode_latest(payload)
    if not (back.clean and back.value == tree):
        raise RuntimeError("re-encoded ADocument does not round-trip byte-exactly")
    return ecc.frame_stream(se.wrap_global_stream(LAT, payload, level=3))


def latest_repoint(mat: Material, old_id: int, new_id: int) -> Tuple[bytes, List[dict]]:
    """Re-encoded Global/Latest with every typed leaf holding ``old_id``
    remapped to ``new_id`` (the pen table has exactly ONE such leaf:
    PenWidthTableInfo.m_penWidthTableElemId).  Returns (framed, edit log)."""
    tree = copy.deepcopy(mat.latest_tree)
    ted = GS.TypedEditor(decoder=None, maps=GA.load_registry_maps())
    edits = ted.remap(tree, "ADocument", {int(old_id): int(new_id)})
    if not edits:
        raise RuntimeError(f"ADocument has no leaf holding {old_id}")
    return encode_latest_stream(tree), [
        {"path": GS.normalize_surface_path(e["path"]), "old": e["old"], "new": e["new"]}
        for e in edits]


def identity_scrub_streams(mat: Material, out_path: str) -> Dict[str, bytes]:
    """The identity scrub EXACTLY as commit_new_elements applies it: our
    BasicFileInfo (document GUID kept -> History[0] coherence) + the DIT
    usernames rewritten.  ``out_path`` becomes last_save_path."""
    cur = se.decode_basic_file_info(mat.raw[BFI])
    ident = dict(IDENTITY)
    ident["document_guid"] = cur.get("unique_document_guid")
    bfi = IDN.own_basic_file_info(mat.raw[BFI], out_path=out_path, **ident)
    with open_rvt(mat.path) as f:
        pref = f.prefix(DIT)
        infl = f.inflate(DIT, 0)
        rawd = f.raw(DIT)
    dit = IDN.own_increment_table_stream(rawd, pref, infl,
                                         username=IDENTITY.get("username", ""))
    return {BFI: bfi, DIT: dit}


# ===========================================================================
# 5. THE PROBE SPECIFICATION
# ===========================================================================

@dataclasses.dataclass
class Probe:
    name: str
    family: str                    # 'from-K1' | 'from-X0' | 'from-X0k' | 'anchor'
    template: str                  # 'K1' | 'X0' | 'X0k'  (the container we start from)
    label: str
    factors: Dict[str, Any]        # {id, episodes, position, identity} target state
    one_change: str                # the ONE registration detail changed vs the sibling
    sibling: str                   # the file it differs from by that one change
    tests: str
    if_pass: str
    if_fail: str
    order: int                     # information value (1 = read first)
    upload: str                    # 'PRIMARY' | 'SECONDARY' | 'OPTIONAL' | 'NO (anchor)'
    expect_streams_changed_vs_template: List[str]
    #: for anchors: the file this probe must be semantically/byte identical to
    identical_to: Optional[str] = None


def probe_specs() -> List[Probe]:
    """The ordered probe set.  Factor state names:
       id:        'orig' (2) | 'high' (1,500,000, X0's) | 'low' (27)
       episodes:  'orig' (0,976,976) | 'addpath' (parent max ep x3 = 1016)
       position:  'orig' (right after element 1, K1's index 2,516) | 'end'
       identity:  'k1' (K1's BasicFileInfo+DIT) | 'scrub' (the add path's own
                  rewrite) | 'template' (whatever the template carries)"""
    P: List[Probe] = []
    # --------------------------- FROM-K1 SINGLES (K1 + ONE deviation) -------
    P.append(Probe(
        name="P_ep_only", family="from-K1", template="K1", order=1, upload="PRIMARY",
        label="K1 with the pen table's ElemTable EPISODES rewritten to the add path's "
              "vintage (0,976,976) -> (1016,1016,1016); NOTHING else changes",
        factors={"id": "orig", "episodes": "addpath", "position": "orig", "identity": "template"},
        one_change="ElemTable row 2: creation/modified/user_modified episodes (0,976,976) -> "
                   "(max,max,max)=(1016,1016,1016) -- a 12-byte edit of one ElemRec",
        sibling="K1.rvt (viewer PASS)",
        expect_streams_changed_vs_template=[ETB],
        tests=("Is the ElemTable VINTAGE of a birth-vintage settings singleton AUDITED?  This "
               "is the linter's ETR.created_at_birth rule (creation episode 0 in 6/6 project "
               "pen tables) tested with ZERO other motion: Autodesk's own file, Autodesk's own "
               "records at their own id and position, only the three episode u32s changed."),
        if_pass=("VINTAGE ALONE is tolerated for the pen table -- the fresh-episode ElemTable "
                 "row the add path writes is NOT the killer by itself (read P_pos_only / "
                 "P_allnew / P_lowid for the other three dimensions)."),
        if_fail=("THE ELEMTABLE VINTAGE IS A HARD RULE: a birth-vintage singleton must keep "
                 "creation episode 0 (and its birth-era modified/user episodes).  Every "
                 "genesis element carries a fresh episode -- FIX: commit_new_elements must "
                 "honour an explicit ElemRecPlan.creation_ep (it currently IGNORES the plan and "
                 "stamps the parent's max episode) and the genesis writer must mint birth-"
                 "vintage classes at episode 0.  Confirm with P_ep (X0 rescued by episodes alone)."),
    ))
    P.append(Probe(
        name="P_pos_only", family="from-K1", template="K1", order=2, upload="PRIMARY",
        label="K1 with element 2's OWN records MOVED from their original position (index "
              "2,516, right after element 1) to the unit-0 END (before the sentinel)",
        factors={"id": "orig", "episodes": "orig", "position": "end", "identity": "template"},
        one_change="record POSITION: index 2,516 -> 6,539 in each of the three seqs (Autodesk's "
                   "own bytes at id 2; ElemTable / Latest / identity untouched)",
        sibling="K1.rvt (viewer PASS)",
        expect_streams_changed_vs_template=["Partitions/*"],
        tests=("Is the RECORD POSITION of a settings singleton in the unit-0 seq streams audited?"
               "  K1's streams are NOT id-sorted (43 ascending runs; the birth block ids "
               "1,2,3,... start at index 2,515); the add path appends every new record at the "
               "end.  Appending at the end is PROVEN for instance/type classes (V20..V29, "
               "T_conduit_types) -- a FAIL here would prove position is ELEMENT-/CLASS-"
               "SPECIFIC (e.g. birth singletons must sit inside the birth block)."),
        if_pass=("POSITION ALONE is tolerated: a settings singleton's records may sit at the "
                 "unit end -- the add path's record placement is NOT the killer (read the "
                 "episode / id-motion singles)."),
        if_fail=("RECORD POSITION IS A HARD RULE for this element: the writer must place "
                 "non-instance elements at their canonical stream position (inside the birth "
                 "block / their original slot), NOT append them at the unit end.  Confirm with "
                 "P_order (X0 rescued by position alone); P_pos_end vs the birth-block-start "
                 "variant is the next positional bisect (buildable in seconds)."),
    ))
    P.append(Probe(
        name="P_allnew", family="from-K1", template="K1", order=3, upload="PRIMARY",
        label="K1 with the pen table re-registered at the NEW HIGH id 1,500,000 IN PLACE "
              "(records rebased at their original position, birth episodes, K1 identity, "
              "watermark raised, the ONE ADocument leaf re-pointed) -- ID MOTION ALONE",
        factors={"id": "high", "episodes": "orig", "position": "orig", "identity": "template"},
        one_change="the element id 2 -> 1,500,000 (records' m_id + own deletion entry, "
                   "ElemTable row id + footer watermark, PenWidthTableInfo leaf) -- the ID "
                   "MOTION dimension, everything else at K1's convention",
        sibling="K1.rvt (viewer PASS)",
        expect_streams_changed_vs_template=["Partitions/*", ETB, LAT],
        tests=("Is REGISTERING THE SETTINGS SINGLETON AT A NEW HIGH ID fatal by itself (the "
               "ADocument leaf now indexing a 1,500,000 id, the watermark jump 1,472,524 -> "
               "1,500,000, the singleton living in the high user-content band -- objlint's "
               "ETR.id_band rule, <5k in 6/6 pen tables)?  This is the maximal registration "
               "match for a genuinely NEW id: from X0's side it is X0 with episodes + "
               "position + identity ALL restored."),
        if_pass=("ID MOTION ALONE is tolerated: a settings singleton CAN be registered at a "
                 "new high id when its episodes / position / identity follow K1's convention "
                 "=> the killer is among the other three dimensions (their singles name it), "
                 "and the genesis writer may keep high ids for singletons."),
        if_fail=("THE ID MOTION IS FATAL: read P_lowid -- P_lowid PASS => it is the HIGH BAND "
                 "(settings singletons must be minted at LOW ids in the birth band); P_lowid "
                 "ALSO FAIL => ANY id/registry motion of this element is fatal (the leaf "
                 "re-point / watermark itself) => genesis must mint each singleton once at its "
                 "canonical low id and never delete+re-add it."),
    ))
    P.append(Probe(
        name="P_lowid", family="from-K1", template="K1", order=4, upload="PRIMARY",
        label=f"K1 with the pen table re-registered at the LOW free id {LOW_ID} (inside the "
              "birth band, watermark NOT raised) IN PLACE -- the ID-BAND control for P_allnew",
        factors={"id": "low", "episodes": "orig", "position": "orig", "identity": "template"},
        one_change=f"the element id 2 -> {LOW_ID} (a free, unreferenced id below the birth-band "
                   "materials; the ADocument leaf re-pointed; watermark unchanged) -- vs P_allnew "
                   "the ONLY difference is the id VALUE (band)",
        sibling="K1.rvt (PASS); direct comparator: P_allnew (same motion, high band)",
        expect_streams_changed_vs_template=["Partitions/*", ETB, LAT],
        tests=(f"Does the id BAND decide?  Id {LOW_ID} is free and unreferenced in K1 (host "
               "graph AND ADocument), sits among the birth-band materials/patterns, and does "
               "NOT raise the watermark.  Reads only against P_allnew."),
        if_pass=("(with P_allnew FAILING) THE HIGH ID BAND is the audited rule for settings "
                 "singletons -- genesis must allocate them low ids from birth (an id allocator "
                 "per class band); (with P_allnew PASSING) id motion in general is fine and the "
                 "band is irrelevant."),
        if_fail=("(with P_allnew FAILING) not the band: ANY re-registration of this element "
                 "(leaf re-point / new id) is fatal even at a low id -- the reader ties the pen "
                 "table's identity to id 2 (a positional/well-known-id singleton); genesis must "
                 "mint the pen table AT ID 2.  (with P_allnew PASSING) a low-band-specific "
                 "constraint -- unexpected; read the card message."),
    ))
    P.append(Probe(
        name="P_ident_only", family="from-K1", template="K1", order=9, upload="OPTIONAL",
        label="K1 with ONLY the add path's identity scrub applied (BasicFileInfo author/"
              "username/last_save_path + DIT usernames -> 'rvt-writer'); document GUID kept",
        factors={"id": "orig", "episodes": "orig", "position": "orig", "identity": "scrub"},
        one_change="the identity scrub (two streams: BasicFileInfo + DocumentIncrementTable) -- "
                   "the V30/V31/V32-PROVEN path, carried by every X0-class file",
        sibling="K1.rvt (viewer PASS)",
        expect_streams_changed_vs_template=[BFI, DIT],
        tests=("The accounting single for the FOURTH dimension.  The scrub is viewer-proven "
               "on the rst working base (V30 own BasicFileInfo, V31 own author, V32 own DIT "
               "usernames PASS); this re-proves it on the K-lineage skeleton so no dimension is "
               "left unmeasured.  Upload only if the primary batch leaves the fourth "
               "dimension in question."),
        if_pass="the identity scrub is tolerated on the K1 lineage too (expected; V30..V32).",
        if_fail=("the identity scrub is NOT tolerated on the reduced K1 lineage (contradicts "
                 "V30..V32 -- would point at a lineage-specific BasicFileInfo dependence)."),
    ))
    # --------------------------- FROM-X0 RESTORES (X0 with ONE thing restored) --
    P.append(Probe(
        name="P_ep", family="from-X0", template="X0", order=5, upload="SECONDARY",
        label="X0 with the new row's ElemTable EPISODES restored to the ORIGINAL element's "
              "vintage: (1016,1016,1016) -> (0,976,976)",
        factors={"id": "high", "episodes": "orig", "position": "end", "identity": "template"},
        one_change="ElemTable row 1,500,000 episodes (1016,1016,1016) -> (0,976,976); every "
                   "other byte of X0 kept (a 12-byte Global/ElemTable edit)",
        sibling="X0.rvt (viewer FAIL)",
        expect_streams_changed_vs_template=[ETB],
        tests=("Does restoring the birth VINTAGE alone RESCUE the failing add-path product?  "
               "The rescue twin of P_ep_only."),
        if_pass=("VINTAGE IS THE (SOLE) KILLER of X0: restoring the birth episodes makes "
                 "Autodesk's own pen table load through our add path.  With P_ep_only FAILING "
                 "this is a closed, single-cause diagnosis: honour birth episodes for "
                 "birth-vintage classes in the commit path."),
        if_fail=("vintage alone does not rescue X0 => another dimension is (also) fatal or the "
                 "rule is an interaction; read the from-K1 singles."),
    ))
    P.append(Probe(
        name="P_order", family="from-X0", template="X0", order=6, upload="SECONDARY",
        label="X0 with the three appended records MOVED from the unit end back to the "
              "ORIGINAL position (right after element 1's records, K1's index 2,516)",
        factors={"id": "high", "episodes": "addpath", "position": "orig", "identity": "template"},
        one_change="record POSITION of the id-1,500,000 records: unit end -> right after element "
                   "1 (X0's own record bytes; ElemTable / Latest / identity are X0's)",
        sibling="X0.rvt (viewer FAIL)",
        expect_streams_changed_vs_template=["Partitions/*"],
        tests=("Does restoring the ORIGINAL record position alone RESCUE X0?  The rescue twin "
               "of P_pos_only.  Also the interaction detector: if every from-K1 single PASSES "
               "while X0 FAILS, a PASS here means position matters ONLY at a NEW id."),
        if_pass=("record POSITION is the killer of X0 (alone, if P_pos_only also FAILS; only in "
                 "combination with the new id, if P_pos_only PASSES): the add path must place "
                 "non-instance element records at their canonical position, not the unit end."),
        if_fail="position alone does not rescue X0.",
    ))
    P.append(Probe(
        name="P_ident", family="from-X0", template="X0", order=10, upload="OPTIONAL",
        label="X0 with K1's ORIGINAL BasicFileInfo + DocumentIncrementTable restored "
              "(the identity scrub reverted)",
        factors={"id": "high", "episodes": "addpath", "position": "end", "identity": "k1"},
        one_change="BasicFileInfo + DIT streams: our scrubbed identity -> K1's originals",
        sibling="X0.rvt (viewer FAIL)",
        expect_streams_changed_vs_template=[BFI, DIT],
        tests=("The rescue twin of P_ident_only (accounting for the fourth, proven dimension)."
               "  Upload only if the primary batch leaves the identity in question."),
        if_pass="identity is X0's killer (would contradict V30..V32) -- lineage-specific.",
        if_fail="identity is not X0's killer (expected).",
    ))
    # --------------------------- FROM-X0k RESTORES (X0k with ONE thing restored)
    P.append(Probe(
        name="P_sameid_ep", family="from-X0k", template="X0k", order=7, upload="OPTIONAL",
        label="X0k with row 2's EPISODES restored (1016,1016,1016) -> (0,976,976) "
              "[X0k = same-id re-add, verdict pending]",
        factors={"id": "orig", "episodes": "orig", "position": "end", "identity": "template"},
        one_change="ElemTable row 2 episodes (1016,1016,1016) -> (0,976,976) -- X0k with only "
                   "the vintage restored (X0k's raw partition / Latest / identity kept)",
        sibling="X0k.rvt (verdict PENDING -- pen table re-added at its own id 2)",
        expect_streams_changed_vs_template=[ETB],
        tests=("Only relevant if X0k FAILS: separates VINTAGE from POSITION at the SAME id "
               "(zero registry motion).  With X0k PASSING these three are moot."),
        if_pass="(X0k FAIL) vintage was X0k's killer at the same id -- consistent with P_ep_only FAIL.",
        if_fail="(X0k FAIL) not vintage alone; read P_sameid_order / P_sameid_ident.",
    ))
    P.append(Probe(
        name="P_sameid_order", family="from-X0k", template="X0k", order=8, upload="OPTIONAL",
        label="X0k with element 2's records MOVED from the unit end back to the ORIGINAL "
              "position (right after element 1) -- the unit-0 record streams become K1's exactly",
        factors={"id": "orig", "episodes": "addpath", "position": "orig", "identity": "template"},
        one_change="record POSITION of the id-2 records: unit end -> right after element 1 "
                   "(the seq record streams then equal K1's byte-for-byte)",
        sibling="X0k.rvt (verdict PENDING)",
        expect_streams_changed_vs_template=["Partitions/*"],
        tests="Only relevant if X0k FAILS: separates POSITION from VINTAGE at the same id.",
        if_pass=("(X0k FAIL) position was X0k's killer at the same id -- consistent with "
                 "P_pos_only FAIL."),
        if_fail="(X0k FAIL) not position alone; read P_sameid_ep / P_sameid_ident.",
    ))
    P.append(Probe(
        name="P_sameid_ident", family="from-X0k", template="X0k", order=11, upload="OPTIONAL",
        label="X0k with K1's ORIGINAL BasicFileInfo + DIT restored",
        factors={"id": "orig", "episodes": "addpath", "position": "end", "identity": "k1"},
        one_change="BasicFileInfo + DIT -> K1's originals (X0k's raw partition / ElemTable kept)",
        sibling="X0k.rvt (verdict PENDING)",
        expect_streams_changed_vs_template=[BFI, DIT],
        tests="Only relevant if X0k FAILS: the identity dimension at the same id (proven category).",
        if_pass="(X0k FAIL) identity was X0k's killer -- would contradict V30..V32.",
        if_fail="(X0k FAIL) not identity; expected.",
    ))
    # --------------------------- ANCHORS (NO UPLOAD, construction proofs) -----
    P.append(Probe(
        name="P_all", family="anchor", template="K1", order=90, upload="NO (anchor)",
        label="element 2 DELETED and RE-ADDED through this tool's assembler with ALL FOUR "
              "dimensions at K1's convention -- ASSERTED BYTE-IDENTICAL TO K1 IN EVERY STREAM",
        factors={"id": "orig", "episodes": "orig", "position": "orig", "identity": "template"},
        one_change="none: delete + re-add with EVERYTHING restored (the lossless-mechanics proof)",
        sibling="K1.rvt (viewer PASS)",
        expect_streams_changed_vs_template=[],
        identical_to="K1",
        tests=("Is delete + re-add LOSSLESS -- does anything outside {the 3 records, the "
               "ElemTable row, the ADocument leaf} encode the element?  Byte-identity with K1 "
               "PROVES no hidden per-element state exists (no ordinal / offset table / checksum "
               "elsewhere), so the whole bug is a REGISTRATION DETAIL among the four "
               "dimensions.  Verdict = K1's (PASS) by identity: NO UPLOAD."),
        if_pass="(by construction) the delete + re-add mechanics are lossless.",
        if_fail=("(only if the byte-identity assertion FAILS) hidden per-element state exists "
                 "outside the three records / ElemTable row / Latest leaf -- named in the "
                 "residual diff; then P_all IS a probe worth uploading."),
    ))
    P.append(Probe(
        name="P_x0", family="anchor", template="K1", order=91, upload="NO (anchor)",
        label="ALL FOUR add-path deviations applied by THIS assembler (id 1,500,000 at the end, "
              "fresh episodes, leaf re-pointed, identity scrubbed) -- ASSERTED SEMANTICALLY "
              "IDENTICAL to X0",
        factors={"id": "high", "episodes": "addpath", "position": "end", "identity": "scrub"},
        one_change="none vs X0 semantically (reproduces the add path's registration exactly)",
        sibling="X0.rvt (viewer FAIL)",
        expect_streams_changed_vs_template=["Partitions/*", ETB, LAT, BFI, DIT],
        identical_to="X0",
        tests=("Is this assembler a faithful stand-in for commit_new_elements?  Asserted: "
               "ElemTable model == X0's, ADocument tree == X0's, unit-0 record bytes + order "
               "== X0's, identity fields == X0's (the only raw differences allowed are the "
               "reader-tolerated end-record junk length and BasicFileInfo.last_save_path).  "
               "Therefore every from-K1 single reads as 'the add path with all but one "
               "deviation removed'.  Verdict = X0's (FAIL) semantically: NO UPLOAD."),
        if_pass="n/a", if_fail="n/a",
    ))
    P.append(Probe(
        name="P_sameid", family="anchor", template="K1", order=92, upload="NO (anchor)",
        label="X0k's registration (pen table re-added AT ITS OWN id 2: records at the unit "
              "end, fresh episodes, identity scrubbed, ZERO registry motion) reproduced by this "
              "assembler -- ASSERTED SEMANTICALLY IDENTICAL to X0k",
        factors={"id": "orig", "episodes": "addpath", "position": "end", "identity": "scrub"},
        one_change="none vs X0k semantically",
        sibling="X0k.rvt (verdict PENDING -- already in the orchestrator's queue)",
        expect_streams_changed_vs_template=["Partitions/*", ETB, BFI, DIT],
        identical_to="X0k",
        tests=("Cross-check of the assembler against the SAME-ID add-path product (X0k).  "
               "Verdict = X0k's: NO UPLOAD (X0k is queued; the three P_sameid_* restores are "
               "pre-built for its FAIL branch)."),
        if_pass="n/a", if_fail="n/a",
    ))
    return P


# ===========================================================================
# 6. BUILD ONE PROBE
# ===========================================================================

def _target_id(kind: str) -> int:
    return {"orig": PEN_ID, "high": X0_NEW_ID, "low": LOW_ID}[kind]


def build_probe(pr: Probe, mats: Dict[str, Material]) -> dict:
    """Assemble ``pr`` from its template material, write the container,
    certify, and return the report (also written as <name>.json)."""
    t0 = time.time()
    tmpl = mats[pr.template]
    k1 = mats["K1"]
    out = os.path.join(OUT_DIR, f"{pr.name}.rvt")
    log(f"\n== {pr.name} :: {pr.label}")
    log(f"   template {pr.template} ({_relp(tmpl.path)}); one change: {pr.one_change}")

    eid = _target_id(pr.factors["id"])
    epi = pr.factors["episodes"]
    pos = pr.factors["position"]
    idn = pr.factors["identity"]
    orig_row = elemtable_row(k1.et_model, PEN_ID)     # (2, 0,976,976, ...)
    ep_orig = (orig_row["creation_ep"], orig_row["modified_ep"], orig_row["user_modified_ep"])
    ep_add = (tmpl.max_ep, tmpl.max_ep, tmpl.max_ep) if pr.template == "K1" else None
    if ep_add is None:                                  # X0 / X0k already carry the max ep
        ep_add = (k1.max_ep, k1.max_ep, k1.max_ep)
    episodes = ep_orig if epi == "orig" else ep_add

    # --- (a) which element id the template currently registers -------------
    tmpl_id = {"K1": PEN_ID, "X0": X0_NEW_ID, "X0k": PEN_ID}[pr.template]
    new_streams: Dict[str, bytes] = {}
    build_info: Dict[str, Any] = {
        "template": pr.template, "template_path": _relp(tmpl.path),
        "template_partition_roundtrip_ok": tmpl.roundtrip_ok,
        "target_id": eid, "episodes": {"creation": episodes[0], "modified": episodes[1],
                                       "user_modified": episodes[2], "source": epi},
        "position": pos, "identity": idn,
    }

    # --- (b) PARTITION: rebuild only if id or position differ from template
    tmpl_pos = _current_position(tmpl, tmpl_id)      # 'end' or 'orig' or 'other'
    need_partition = (eid != tmpl_id) or (pos != tmpl_pos)
    if need_partition:
        recs_wo, old_idx = recs_remove(tmpl.u0_recs, tmpl_id)
        framed = pen_records_at(eid, k1)
        if pos == "end":
            recs_new, placed = recs_insert(recs_wo, framed, "end")
        else:  # 'orig' = right after element 1 (K1's original position)
            recs_new, placed = recs_insert(recs_wo, framed, "after", after_id=1)
        count = len(tmpl.et_model["records"])          # add-1/remove-1: count unchanged
        logical = assemble_partition(tmpl, recs_new, count)
        new_streams[tmpl.pname] = frame_partition(logical)
        build_info["partition"] = {
            "records_source": ("Autodesk's own element-2 bytes" +
                               ("" if eid == PEN_ID else f", identity rebased 2->{eid} "
                                "(byte-exact codec, proof recorded)")),
            "rebase_proof": _REBASE_PROOF.get(eid),
            "removed_from_index": old_idx, "placed_at_index": placed,
            "records_per_seq": {str(s): len(recs_new[s]) for s in SEQS},
            "logical_len": len(logical), "template_logical_len": len(tmpl.true_logical),
        }
    else:
        build_info["partition"] = {"copied_verbatim_from_template": True}

    # --- (c) ELEMTABLE: row episodes / row id ------------------------------
    et = et_model_copy(tmpl.et_model)
    tmpl_row = elemtable_row(tmpl.et_model, tmpl_id)
    et_changes: List[dict] = []
    if eid != tmpl_id:
        removed = et_remove(et, tmpl_id)
        # watermark: removing a row never lowers the footer.  For a non-K1
        # template (X0's watermark was raised to 1,500,000) a target id below
        # that raised watermark restores K1's convention first, so the footer
        # never names an id that no longer exists; et_insert then raises it
        # again iff the new id exceeds it.
        if pr.template != "K1":
            et["footer"]["last_id"] = int(k1.watermark)
        inserted = et_insert(et, eid, creation_ep=episodes[0], modified_ep=episodes[1],
                             user_modified_ep=episodes[2])
        et_changes.append({"removed_row": _row_str(removed), "inserted_row": _row_str(inserted)})
    elif (tmpl_row is not None and
          (tmpl_row["creation_ep"], tmpl_row["modified_ep"],
           tmpl_row["user_modified_ep"]) != tuple(episodes)):
        old, new = et_set_episodes(et, eid, *episodes)
        et_changes.append({"episodes_row_before": _row_str(old), "episodes_row_after": _row_str(new)})
    et_bytes = encode_elemtable_stream(et)
    if et_bytes != tmpl.raw[ETB]:
        new_streams[ETB] = et_bytes
    build_info["elemtable"] = {
        "changes": et_changes,
        "row_after": elemtable_row(et, eid),
        "count": len(et["records"]),
        "watermark_before": tmpl.watermark, "watermark_after": int(et["footer"]["last_id"]),
    }

    # --- (d) GLOBAL/LATEST: only when the id differs from the template's ---
    latest_edits: List[dict] = []
    if eid != tmpl_id:
        # re-point from whatever the template's leaf currently holds
        lat, latest_edits = latest_repoint(tmpl, tmpl_id, eid)
        new_streams[LAT] = lat
        build_info["latest"] = {"leaf_remapped": latest_edits}
    else:
        build_info["latest"] = {"copied_verbatim_from_template": True}

    # --- (e) IDENTITY ---------------------------------------------------------
    if idn == "template":
        build_info["identity"] = {"copied_verbatim_from_template": True}
    elif idn == "k1":
        for nm in (BFI, DIT):
            if k1.raw[nm] != tmpl.raw[nm]:
                new_streams[nm] = k1.raw[nm]
        build_info["identity"] = {"restored_from": "K1's original BasicFileInfo + DIT"}
    elif idn == "scrub":
        scr = identity_scrub_streams(tmpl, out_path=out)
        for nm, b in scr.items():
            if b != tmpl.raw[nm]:
                new_streams[nm] = b
        build_info["identity"] = {"scrubbed_by": "rvt.identity.own_basic_file_info + "
                                                 "own_increment_table_stream (the commit path's "
                                                 "identity treatment, document GUID kept)"}

    # --- (f) write the container ------------------------------------------
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in tmpl.entries]
    write_cfb(out, out_entries)
    build_info["streams_written_new"] = sorted(new_streams)
    build_info["seconds_build"] = round(time.time() - t0, 1)

    # --- (g) certification --------------------------------------------------
    rep = certify(out, pr, mats, build_info)
    _write_report(pr.name, rep)
    v = rep["verdict"]
    log(f"   -> {_relp(out)} {rep['bytes']:,} B  VERDICT {v}"
        f"{('  *** ' + rep.get('FAILED_SELF_CHECK', '')) if v != 'CERTIFIED' else ''}"
        f" ({rep['seconds']}s)")
    return rep


def _row_str(row) -> Any:
    if row is None:
        return None
    r = list(row)
    own = int(r[5])
    return {"original_id": int(r[0]), "creation_ep": int(r[1]), "modified_ep": int(r[2]),
            "user_modified_ep": int(r[3]), "elem_id": int(r[4]),
            "owner": (-1 if own >= (1 << 63) else own), "partition": int(r[6])}


def _current_position(mat: Material, eid: int) -> str:
    """Where element ``eid``'s record sits in ``mat``'s seq-102 stream:
    'end' (last before the sentinel), 'orig' (right after element 1), or a
    description."""
    ids = id_sequence(mat.u0_recs[102])
    if eid not in ids:
        return "absent"
    i = ids.index(eid)
    if i == len(ids) - 2:
        return "end"
    if i > 0 and ids[i - 1] == 1:
        return "orig"
    return f"index-{i}"


# ===========================================================================
# 7. CERTIFICATION -- validator + structural + the diff tables
# ===========================================================================

def _stream_status(a: Optional[bytes], b: Optional[bytes]) -> str:
    if a is None or b is None:
        return "absent"
    return "identical" if a == b else "DIFFERS"


def _match_expected(name: str, expected: Sequence[str]) -> bool:
    for e in expected:
        if e.endswith("/*"):
            if name.startswith(e[:-1]):
                return True
        elif name == e:
            return True
    return False


def certify(out: str, pr: Probe, mats: Dict[str, Material], build_info: dict) -> dict:
    t0 = time.time()
    k1, x0, x0k = mats["K1"], mats["X0"], mats["X0k"]
    tmpl = mats[pr.template]
    eid = _target_id(pr.factors["id"])
    probe_raw = read_streams(out)
    pmat = load_material(out)

    # (1) per-stream byte diff tables
    def diffvs(other: Material) -> Dict[str, str]:
        return {n: _stream_status(probe_raw.get(n), other.raw.get(n))
                for n in sorted(set(probe_raw) | set(other.raw))}
    vs = {"K1": diffvs(k1), "X0": diffvs(x0), "X0k": diffvs(x0k)}
    changed_vs_template = sorted(n for n, s in vs[pr.template].items() if s == "DIFFERS")
    expected_ok = (sorted(changed_vs_template) ==
                   sorted(n for n in changed_vs_template
                          if _match_expected(n, pr.expect_streams_changed_vs_template)))
    # every expected pattern must actually be present (unless the anchor expects none)
    for e in pr.expect_streams_changed_vs_template:
        if not any(_match_expected(n, [e]) for n in changed_vs_template):
            if not (pr.name == "P_x0" and e in (LAT, DIT)):   # cosmetic-only allowed for the twin
                expected_ok = False

    # (2) validator + structural proof + the target records
    val = RR._run_validator(out)
    struct = verify_reduced(out, [])
    vw = verify_written(out, [eid])
    recs_found = {str(s): (vw["new_ids_found"].get(s) or {}).get(eid) for s in SEQS}
    recs_clean = all((r is not None) and (r.get("clean") is not False)
                     for r in recs_found.values())

    # (3) intended-state assertions
    row = elemtable_row(pmat.et_model, eid)
    epi = build_info["episodes"]
    row_ok = (row is not None and row["creation_ep"] == epi["creation"]
              and row["modified_ep"] == epi["modified"]
              and row["user_modified_ep"] == epi["user_modified"]
              and row["owner_id"] == -1 and row["original_id"] == eid)
    pos_now = _current_position(pmat, eid)
    pos_ok = (pos_now == pr.factors["position"])
    surf = GS.adoc_surface(GS.TypedEditor(decoder=None, maps=GA.load_registry_maps()),
                            pmat.latest_tree, [eid, PEN_ID, X0_NEW_ID, LOW_ID])
    latest_ok = (list(surf.keys()) == [eid] and len(surf[eid]) == 1)
    count_ok = (len(pmat.et_model["records"]) == pmat.header_count == 6540)
    seq_orders_equal = (id_sequence(pmat.u0_recs[101]) == id_sequence(pmat.u0_recs[102])
                        == id_sequence(pmat.u0_recs[103]))
    ids_et = {int(r[4]) for r in pmat.et_model["records"]}
    ids_u0 = set(id_sequence(pmat.u0_recs[102])) - {-1}
    idset_ok = (ids_et == ids_u0)
    wm = int(pmat.et_model["footer"]["last_id"])
    wm_ok = (wm >= max(ids_et)) and (wm == max(k1.watermark, eid) if eid > k1.watermark
                                        else wm == k1.watermark)

    # (4) semantic diffs (readable evidence)
    et_diff_k1 = _elemtable_diff(k1.et_model, pmat.et_model)
    et_diff_t = _elemtable_diff(tmpl.et_model, pmat.et_model)
    order_diff_k1 = _order_diff(k1, pmat, eid)
    latest_leafdiff_k1 = _tree_diff(k1.latest_tree, pmat.latest_tree)
    ident_p = se.decode_basic_file_info(probe_raw[BFI])
    ident_k = se.decode_basic_file_info(k1.raw[BFI])
    ident_x = se.decode_basic_file_info(x0.raw[BFI])
    ident_diff_k1 = {k: [_short(ident_k.get(k)), _short(ident_p.get(k))]
                     for k in set(ident_k) | set(ident_p)
                     if ident_k.get(k) != ident_p.get(k) and k not in ("mirror_text", "stream")}
    dit_users = sorted({r.get("username") for r in
                        se.decode_increment_table(_inflate(pmat, DIT))["records"]})

    # (5) anchor identity proofs
    anchor = None
    if pr.identical_to == "K1":
        byte_ident = {n: (probe_raw.get(n) == k1.raw.get(n)) for n in sorted(set(k1.raw) | set(probe_raw))}
        anchor = {"kind": "byte-identity vs K1", "per_stream": byte_ident,
                  "ALL_STREAMS_BYTE_IDENTICAL_TO_K1": all(byte_ident.values())}
    elif pr.identical_to in ("X0", "X0k"):
        ref = x0 if pr.identical_to == "X0" else x0k
        anchor = _semantic_twin_proof(pmat, probe_raw, ref, eid if pr.identical_to == "X0"
                                      else PEN_ID)

    problems = []
    if not (val.get("ok") and val.get("errors") == 0):
        problems.append(f"validator errors={val.get('errors')}: {val.get('error_messages')}")
    if not struct.get("ok"):
        problems.append(f"structural proof failed: { {k: struct.get(k) for k in ('crc_failures','ecc_mismatches','stamps_bad')} }")
    if vw.get("crc_failures") or vw.get("ecc_mismatches") or vw.get("walker_errors"):
        problems.append(f"verify_written: crc {vw.get('crc_failures')} ecc {vw.get('ecc_mismatches')} walker {vw.get('walker_errors')}")
    if not vw.get("stamps_ok"):
        problems.append("record stamps not all valid")
    if not recs_clean:
        problems.append(f"target records at id {eid} not all found/clean: {recs_found}")
    if not row_ok:
        problems.append(f"ElemTable row for {eid} not as intended: {row}")
    if not pos_ok:
        problems.append(f"record position is '{pos_now}', intended '{pr.factors['position']}'")
    if not latest_ok:
        problems.append(f"ADocument does not index exactly the target id {eid}: {surf}")
    if not count_ok:
        problems.append("ElemTable count / partition header count / 6540 mismatch")
    if not seq_orders_equal:
        problems.append("the three seq record orders are not identical")
    if not idset_ok:
        problems.append("ElemTable id set != unit-0 record id set")
    if not wm_ok:
        problems.append(f"watermark {wm} not consistent (k1 {k1.watermark}, target {eid})")
    if not expected_ok:
        problems.append(f"changed-stream set vs template {changed_vs_template} != expected "
                        f"{pr.expect_streams_changed_vs_template}")
    if pr.identical_to == "K1" and anchor and not anchor["ALL_STREAMS_BYTE_IDENTICAL_TO_K1"]:
        problems.append("anchor P_all is NOT byte-identical to K1 (see residual)")
    if pr.identical_to in ("X0", "X0k") and anchor and not anchor.get("SEMANTICALLY_IDENTICAL"):
        problems.append(f"anchor {pr.name} is NOT semantically identical to {pr.identical_to}")

    rep = {
        "probe": pr.name, "family": pr.family, "label": pr.label, "order": pr.order,
        "upload": pr.upload, "file": _relp(out), "template": pr.template,
        "sibling": pr.sibling, "one_change": pr.one_change,
        "factors": pr.factors, "target_id": eid,
        "tests": pr.tests, "if_PASS": pr.if_pass, "if_FAIL": pr.if_fail,
        "build_info": build_info,
        "streams_vs": vs,
        "changed_vs_template": changed_vs_template,
        "expected_changed_vs_template": pr.expect_streams_changed_vs_template,
        "changed_set_as_expected": expected_ok,
        "validator": val,
        "structural": {k: struct.get(k) for k in ("ok", "crc_failures", "ecc_mismatches",
                                                    "counts_match", "seq_id_sets_equal",
                                                    "stamps_bad", "isize_identity_ok")},
        "verify_written": {k: vw.get(k) for k in ("crc_failures", "ecc_mismatches",
                                                    "walker_errors", "stamps_ok",
                                                    "elemtable_count", "header_count")},
        "target_records": {"id": eid, "found_clean": recs_clean, "per_seq": recs_found},
        "intended_state": {
            "elemtable_row": row, "row_ok": row_ok,
            "record_position": pos_now, "position_ok": pos_ok,
            "adocument_surface": surf, "latest_ok": latest_ok,
            "watermark": wm, "watermark_ok": wm_ok,
            "counts_6540_coherent": count_ok, "three_seq_orders_equal": seq_orders_equal,
            "elemtable_ids_equal_record_ids": idset_ok,
        },
        "semantic_diff": {
            "elemtable_vs_K1": et_diff_k1, "elemtable_vs_template": et_diff_t,
            "record_order_vs_K1": order_diff_k1,
            "adocument_leaf_diff_vs_K1": [{"path": p, "K1": a, "probe": b}
                                          for p, a, b in latest_leafdiff_k1],
            "identity_vs_K1": {"BasicFileInfo": ident_diff_k1, "DIT_usernames": dit_users,
                               "note": ("last_save_path/username/author/client_app are the "
                                        "identity scrub; identical == K1's originals")},
        },
        "anchor_proof": anchor,
        "problems": problems,
        "verdict": ("CERTIFIED" if not problems else "NOT-CERTIFIED"),
        "bytes": os.path.getsize(out), "seconds": round(time.time() - t0, 1),
    }
    if problems:
        rep["FAILED_SELF_CHECK"] = "; ".join(problems)[:600]
    return rep


def _elemtable_diff(a: dict, b: dict) -> dict:
    """Row-level ElemTable diff a -> b keyed by element id (+ footer)."""
    ra = {int(r[4]): tuple(r) for r in a["records"]}
    rb = {int(r[4]): tuple(r) for r in b["records"]}
    removed = sorted(set(ra) - set(rb))
    added = sorted(set(rb) - set(ra))
    changed = sorted(i for i in set(ra) & set(rb) if ra[i] != rb[i])
    return {
        "removed_rows": [_row_str(ra[i]) for i in removed],
        "added_rows": [_row_str(rb[i]) for i in added],
        "changed_rows": [{"before": _row_str(ra[i]), "after": _row_str(rb[i])} for i in changed],
        "count": [len(a["records"]), len(b["records"])],
        "watermark": [int(a["footer"]["last_id"]), int(b["footer"]["last_id"])],
    }


def _order_diff(k1: Material, p: Material, eid: int) -> dict:
    """How the probe's unit-0 id ORDER differs from K1's (seq 102; the three
    seqs are asserted identical)."""
    ak = id_sequence(k1.u0_recs[102])
    ap = id_sequence(p.u0_recs[102])
    # remove the two elements' ids to compare the backbone
    bk = [i for i in ak if i not in (PEN_ID, eid)]
    bp = [i for i in ap if i not in (PEN_ID, eid)]
    return {
        "K1_len": len(ak), "probe_len": len(ap),
        "backbone_order_identical_excluding_target": (bk == bp),
        "K1_index_of_2": (ak.index(PEN_ID) if PEN_ID in ak else None),
        "probe_index_of_target": (ap.index(eid) if eid in ap else None),
        "probe_target_neighbours": (ap[max(0, ap.index(eid) - 3): ap.index(eid) + 4]
                                    if eid in ap else None),
        "record_bytes_at_target_equal_K1_element_2": _target_record_bytes_note(k1, p, eid),
    }


def _target_record_bytes_note(k1: Material, p: Material, eid: int) -> Any:
    """Byte comparison of the probe's target records against K1's element-2
    records (identical when eid == 2; differing only in the rebased identity
    leaves otherwise)."""
    out = {}
    for s in SEQS:
        rk = next((r for r in k1.u0_recs[s] if r.elem_id == PEN_ID), None)
        rp = next((r for r in p.u0_recs[s] if r.elem_id == eid), None)
        if rk is None or rp is None:
            out[str(s)] = "missing"
            continue
        cmp = GC.byte_compare(bytes(rp.data), bytes(rk.data), limit=8)
        out[str(s)] = {"identical": cmp["identical"], "differing_bytes": cmp["differing_bytes"],
                       "len": [len(rp.data), len(rk.data)]}
    return out


def _semantic_twin_proof(pmat: Material, probe_raw: Dict[str, bytes], ref: Material,
                         eid: int) -> dict:
    """The twin's models equal the reference's; the only raw differences are
    reader-tolerated cosmetics (end-record junk length in the partition tail,
    BasicFileInfo.last_save_path, gzip block-ending / identical inflated
    payloads for re-encoded streams)."""
    et_equal = ([tuple(r) for r in pmat.et_model["records"]] ==
                [tuple(r) for r in ref.et_model["records"]] and
                int(pmat.et_model["footer"]["last_id"]) == int(ref.et_model["footer"]["last_id"]))
    tree_equal = (pmat.latest_tree == ref.latest_tree)
    order_equal = all(id_sequence(pmat.u0_recs[s]) == id_sequence(ref.u0_recs[s]) for s in SEQS)
    bytes_equal = all([bytes(a.data) for a in pmat.u0_recs[s]] ==
                      [bytes(b.data) for b in ref.u0_recs[s]] for s in SEQS)
    ip = se.decode_basic_file_info(probe_raw[BFI])
    ir = se.decode_basic_file_info(ref.raw[BFI])
    ident_delta = {k: [_short(ir.get(k)), _short(ip.get(k))] for k in set(ip) | set(ir)
                   if ip.get(k) != ir.get(k) and k not in ("mirror_text", "stream")}
    ident_ok = set(ident_delta) <= {"last_save_path"}
    dit_p = sorted({r.get("username") for r in
                    se.decode_increment_table(_inflate(pmat, DIT))["records"]})
    dit_r = sorted({r.get("username") for r in
                    se.decode_increment_table(_inflate(ref, DIT))["records"]})
    # inflated-payload equality for streams that may differ only in compression
    inflated_equal = {}
    for nm in (LAT, ETB, DIT):
        try:
            inflated_equal[nm] = (_inflate(pmat, nm) == _inflate(ref, nm))
        except Exception as e:                       # pragma: no cover
            inflated_equal[nm] = f"error {e!r}"
    raw_diff = {n: _stream_status(probe_raw.get(n), ref.raw.get(n))
                for n in sorted(set(probe_raw) | set(ref.raw))}
    ok = (et_equal and tree_equal and order_equal and bytes_equal and ident_ok
          and dit_p == dit_r and all(v is True for v in inflated_equal.values()))
    return {
        "kind": f"semantic identity vs {_relp(ref.path)}",
        "elemtable_model_equal": et_equal, "adocument_tree_equal": tree_equal,
        "unit0_record_order_equal": order_equal, "unit0_record_bytes_equal": bytes_equal,
        "identity_fields_equal_except_last_save_path": ident_ok,
        "identity_field_delta": ident_delta,
        "dit_usernames_equal": (dit_p == dit_r), "dit_usernames": dit_p,
        "inflated_payload_equal": inflated_equal,
        "raw_stream_status": raw_diff,
        "raw_differences_are_cosmetic": ("Partitions tail = one fewer generation of the "
                                         "reader-tolerated end-record junk (this tool adds "
                                         "none); BasicFileInfo differs only in last_save_path; "
                                         "any Latest/DIT/ElemTable raw difference is gzip "
                                         "block-ending with byte-identical inflated payloads"),
        "SEMANTICALLY_IDENTICAL": ok,
    }


def _write_report(name: str, rep: dict) -> None:
    with open(os.path.join(OUT_DIR, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))


# ===========================================================================
# 8. THE MANIFEST (probes.json): ordered probes + collapses + decision tree
# ===========================================================================

def write_manifest(mats: Dict[str, Material], reports: Dict[str, dict],
                   delta: dict, collapses: dict) -> str:
    specs = {p.name: p for p in probe_specs()}
    probes_out = []
    for name in sorted(reports, key=lambda n: specs[n].order):
        r = reports[name]
        p = specs[name]
        probes_out.append({
            "order": p.order, "name": name, "family": p.family, "upload": p.upload,
            "file": f"experiments/genesis/addpath/{name}.rvt",
            "report": f"experiments/genesis/addpath/{name}.json",
            "template": p.template, "sibling_it_differs_from": p.sibling,
            "the_ONE_change": p.one_change, "label": p.label,
            "the_one_thing_it_tests": p.tests, "if_PASS": p.if_pass, "if_FAIL": p.if_fail,
            "verdict": r.get("verdict"),
            "validator": {"ok": (r.get("validator") or {}).get("ok"),
                          "errors": (r.get("validator") or {}).get("errors")},
            "changed_vs_template": r.get("changed_vs_template"),
            "changed_set_as_expected": r.get("changed_set_as_expected"),
            "anchor_proof": ({k: v for k, v in (r.get("anchor_proof") or {}).items()
                              if k in ("kind", "ALL_STREAMS_BYTE_IDENTICAL_TO_K1",
                                       "SEMANTICALLY_IDENTICAL")} or None),
        })
    manifest = {
        "generator": "tools/genesis_addpath_probes.py",
        "stream": "genesis-addpath-probes -- PER-RULE VERBATIM CONTROLS for the ADD PATH",
        "the_decisive_fact": (
            "X0 (Autodesk's OWN pen table, exact bytes, through OUR add path at a new id) and "
            "C0 (Autodesk's own catalog row via our path) BOTH FAIL Revit-DocumentCorruption "
            "(verdicts #11): our objects are exonerated; the ADD PATH for non-instance elements "
            "corrupts, while the family-INSTANCE add path is proven (V20..V29 load).  The bug is "
            "the delta between how K1 registered the element and how our path does."),
        "measured_delta_K1_vs_X0": delta,
        "collapsed_probes_no_file": collapses,
        "reference_files": {
            "K1": _relp(K1_PATH) + " (viewer PASS -- the registration reference)",
            "X0": _relp(X0_PATH) + " (viewer FAIL -- our add path, new id 1,500,000)",
            "X0k": _relp(X0K_PATH) + " (verdict PENDING -- same id 2, zero registry motion, "
                                     "already in the orchestrator's queue)",
        },
        "reading_order": [p["name"] for p in probes_out],
        "upload_plan": {
            "PRIMARY_batch": ["P_ep_only", "P_pos_only", "P_allnew", "P_lowid"],
            "PRIMARY_note": ("the four FROM-K1 SINGLES: each = K1 + exactly ONE add-path "
                             "deviation, Autodesk's own records throughout; a FAIL names the "
                             "audited rule DIRECTLY on the passing file with zero other motion"),
            "SECONDARY_same_round_if_capacity": ["P_ep", "P_order"],
            "SECONDARY_note": ("the FROM-X0 RESCUES: X0 with ONE dimension restored; a PASS shows "
                               "removing that ONE deviation makes a real add-path product load, "
                               "and they expose interactions the singles cannot"),
            "OPTIONAL": ["P_sameid_ep", "P_sameid_order", "P_sameid_ident", "P_ident_only",
                         "P_ident"],
            "OPTIONAL_note": ("the FROM-X0k restores are only informative if X0k FAILS "
                              "(pre-built for that branch); the two identity probes cover the "
                              "V30..V32-proven fourth dimension for completeness"),
            "NO_UPLOAD_anchors": ["P_all", "P_x0", "P_sameid"],
            "NO_UPLOAD_note": ("construction proofs: P_all is BYTE-IDENTICAL to K1 (its verdict "
                               "IS K1's PASS); P_x0 / P_sameid are the assembler's semantic twins "
                               "of X0 / X0k (their verdicts are those files')"),
            "NO_FILE_collapsed": ["P_owner", "P_flags"],
        },
        "decision_tree": {
            "given": ("K1 PASS; X0 FAIL; the K1->X0 delta = exactly four dimensions {ID MOTION, "
                      "EPISODES, POSITION, IDENTITY} (measured; the ADocument differs in ONE "
                      "leaf; P_owner / P_flags collapse onto X0 byte-identically); P_all == K1 "
                      "byte-for-byte => the delete+re-add mechanics are lossless and the bug IS "
                      "one (or an interaction) of the four."),
            "P_ep_only FAIL": ("ELEMTABLE VINTAGE IS THE HARD RULE (a 12-byte episode edit alone "
                               "corrupts K1): birth-vintage singletons must keep creation episode "
                               "0 / birth-era episodes.  FIX: commit_new_elements honours an "
                               "explicit ElemRecPlan.creation_ep (today it IGNORES the plan and "
                               "stamps the parent's max episode) + the genesis writer mints "
                               "birth-vintage classes at episode 0.  P_ep PASS confirms the "
                               "rescue on a real add-path product."),
            "P_pos_only FAIL": ("RECORD POSITION IS A HARD RULE for this element: our path's "
                                "append-before-sentinel (proven for instances) is NOT valid for "
                                "birth singletons; the writer must place them at their canonical "
                                "stream position.  P_order PASS confirms the rescue; the next "
                                "bisect is 'unit end' vs 'birth-block start' vs 'exact original "
                                "slot' (buildable in seconds with this tool)."),
            "P_allnew FAIL": ("REGISTERING THE SINGLETON AT A NEW HIGH ID is fatal by itself.  Read "
                              "P_lowid: PASS => it is the HIGH ID BAND (allocate settings "
                              "singletons LOW ids from birth); FAIL => ANY re-registration of "
                              "this element is fatal (the leaf re-point / watermark) => genesis "
                              "must mint the pen table AT ITS CANONICAL id 2 and never move it."),
            "several from-K1 singles FAIL": ("MULTIPLE independent rules -- each named by its "
                                             "own FAIL; fix all; the from-X0 restores tell which "
                                             "single restoration is SUFFICIENT (none, if two are "
                                             "each fatal alone)."),
            "ALL four from-K1 singles PASS (while X0 FAILS)": (
                "an INTERACTION: a dimension fatal only combined with another (typically with "
                "the id motion).  Read the from-X0 restores: P_ep PASS => vintage x new-id; "
                "P_order PASS => position x new-id; P_ident PASS => identity x new-id; none "
                "PASS => a 3-way interaction => next round: pairwise probes (each buildable in "
                "seconds via probe_specs()).  Also re-check the identity singles."),
            "consistency_with_X0k": ("X0k PASS predicts P_ep_only, P_pos_only and P_ident_only "
                                     "PASS (episodes/position/identity all tolerated at the same "
                                     "id) and pushes the fault onto the id motion => expect "
                                     "P_allnew FAIL and P_lowid to decide the band.  X0k FAIL "
                                     "predicts one of {P_ep_only, P_pos_only, P_ident_only} "
                                     "FAILS, and the matching P_sameid_* restore PASSES."),
        },
        "cross_stream_observation_X_pen": (
            "docs/coverage/viewer-certified.json lists experiments/genesis/subst_v2/X_pen.rvt "
            "as FAILED in the same batch as X0.  X_pen is the fixer's IN-PLACE probe: K1 with the "
            "pen table's records replaced AT ITS OWN id 2 by OUR pen-table object via the "
            "CERTIFIED modify path -- and, MEASURED here, X_pen differs from K1 in Partitions/21 "
            "ONLY (BasicFileInfo, DIT, ElemTable, Latest are byte-identical to K1's; no add path, "
            "no identity scrub, no registry motion, record IN PLACE at index 2,516).  Therefore "
            "X_pen convicts OUR PEN-TABLE PAYLOAD independently of the add path -- a SECOND, "
            "SEPARATE bug the 'our objects are exonerated' summary of verdicts #11 does not "
            "cover: X0/C0 prove Autodesk's payload fails through our ADD PATH, and X_pen proves "
            "our payload fails WITHOUT the add path.  Both must be fixed for genesis; this stream "
            "attacks only the add path (every probe here carries Autodesk's own payload).  The "
            "fixer's own tree names the follow-up: X_pen_obj (K1's own header, our object body)."),
        "assembler_findings": [
            ("K1's true partition logical (unframe_exact) round-trips byte-exactly through "
             "ecc.frame_stream; rebuilding unit 0 from its own record lists + K1's exact "
             "trailing region reproduces the stream byte-for-byte (P_all)."),
            ("delete_elements appends the source's final-page ECC pad into the output logical "
             "(the depaged tail extends past the true end) => each re-block generation grows "
             "the partition 'end record' (K1 603 B, its re-block 668 B, K4 ~1.6 KB); the reader "
             "TOLERATES it (K1, K3, K4, KD1 PASS) so it is cosmetic, but it makes byte-identity "
             "with a parent impossible for delete_elements outputs; fix = truncate the source at "
             "unframe_exact()'s true end.  (Owner: the reduce stream; not applied here.)"),
            ("The unit-0 record streams are NOT id-sorted: 43 ascending id-runs; the max id "
             "1,472,524 sits at position 131 of 6,540; the birth-vintage block (ids 1..7...) "
             "starts at position 2,515; the last real record is id 49,026; the three seqs carry "
             "IDENTICAL id order.  'Append at the unit end' therefore does NOT match K1's own "
             "placement of its highest ids (which live in the FIRST run)."),
        ],
        "probes": probes_out,
        "reproduce": ("cd tekton && .venv/bin/python tools/genesis_addpath_probes.py "
                      "(~2 min); .venv/bin/python -m pytest tests/test_addpath_probes.py -q"),
    }
    p = os.path.join(OUT_DIR, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"\n[manifest] -> {_relp(p)}")
    return p


# ===========================================================================
# 9. main
# ===========================================================================

def load_all() -> Dict[str, Material]:
    log(f"[load] K1 {_relp(K1_PATH)}")
    k1 = load_material(K1_PATH)
    log(f"       partition round-trip {k1.roundtrip_ok}; count {len(k1.et_model['records'])}; "
        f"watermark {k1.watermark}; max ep {k1.max_ep}")
    log(f"[load] X0 {_relp(X0_PATH)}")
    x0 = load_material(X0_PATH)
    log(f"[load] X0k {_relp(X0K_PATH)}")
    x0k = load_material(X0K_PATH)
    return {"K1": k1, "X0": x0, "X0k": x0k}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--only", default="", help="comma list of probe names")
    ap.add_argument("--manifest-only", action="store_true",
                    help="re-write probes.json from the reports on disk")
    ap.add_argument("--delta-only", action="store_true", help="print the measured delta and exit")
    args = ap.parse_args(argv)

    t0 = time.time()
    mats = load_all()
    delta = enumerate_delta(mats["K1"], mats["X0"], mats["X0k"])
    collapses = measure_collapses(mats["K1"], mats["X0"])
    with open(os.path.join(OUT_DIR, "delta.json"), "w") as fh:
        json.dump({"delta_K1_vs_X0": delta, "collapsed": collapses}, fh, indent=1, default=str)
    log(f"[delta] streams differing K1->X0: {delta['streams_differing']}")
    log(f"[delta] ADocument leaf differences: {len(delta['adocument_leaf_differences'])} "
        f"({[d['path'].split('->')[-1] for d in delta['adocument_leaf_differences']]})")
    if args.delta_only:
        print(json.dumps({"delta": delta, "collapses": collapses}, indent=1, default=str))
        return 0

    specs = {p.name: p for p in probe_specs()}
    if args.manifest_only:
        reports = {}
        for name in specs:
            pj = os.path.join(OUT_DIR, f"{name}.json")
            if os.path.exists(pj):
                with open(pj) as fh:
                    reports[name] = json.load(fh)
        write_manifest(mats, reports, delta, collapses)
        return 0

    want = [n.strip() for n in args.only.split(",") if n.strip()] or list(specs)
    reports: Dict[str, dict] = {}
    for name in sorted(want, key=lambda n: specs[n].order):
        reports[name] = build_probe(specs[name], mats)
    # merge any earlier reports on disk (for a partial --only run)
    for name in specs:
        if name not in reports:
            pj = os.path.join(OUT_DIR, f"{name}.json")
            if os.path.exists(pj):
                with open(pj) as fh:
                    reports[name] = json.load(fh)
    write_manifest(mats, reports, delta, collapses)

    log("\n== summary")
    ok = True
    for n in sorted(reports, key=lambda x: specs[x].order):
        r = reports[n]
        v = r.get("verdict")
        ok = ok and (v == "CERTIFIED")
        extra = ""
        if r.get("anchor_proof"):
            ap_ = r["anchor_proof"]
            if "ALL_STREAMS_BYTE_IDENTICAL_TO_K1" in ap_:
                extra = f"  byte-identical-to-K1={ap_['ALL_STREAMS_BYTE_IDENTICAL_TO_K1']}"
            elif "SEMANTICALLY_IDENTICAL" in ap_:
                extra = f"  semantic-twin={ap_['SEMANTICALLY_IDENTICAL']}"
        log(f"   {n:16s} {v}{extra}")
    log(f"   ({round(time.time() - t0, 1)}s total)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
