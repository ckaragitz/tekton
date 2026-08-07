#!/usr/bin/env python
"""layout_diff -- THE MATCHED-PAIR UNIT DIFF + THE MORPH PROBES (layout-law
stream, post-verdict-#40).

Verdict #40's conviction: SUB_ALL (donor famdoc lawfully REDUCED to
donor-frame + our 35 axis elements, built by deletion) PASSES instanced
while F1 (the same logical content assembled by famgen with the donor frame
swapped in) FAILS -- "content equal, construction different => the audit
rejects our writer's PHYSICAL DOCUMENT LAYOUT".

This tool tests that conviction by MEASURING it.  `enumerate` extracts both
probes' ADDED UNIT (the famdoc partition unit) and compares at every
granularity: record order per seq segment, per-record bytes for
content-corresponding records (id-normalized decoded leaf diff), block
packing, registry row orders inside the frame elements, the inline
ADocument, and the host side (H8B -- same base rst, same famload loader,
FAIL -- is the base+loader-matched comparator).  Every difference is
classified {ORDER, PACKING, FIELD, CONTENT, IDENTITY, BASE-COUPLED} and
ranked by present-in-all-FAIL / absent-in-all-PASS across the whole probe
corpus on disk (PASS: SUB_ALL + SUB singles/halves + B1..B7 + U12/U15/U25 +
U16 + U12345; FAIL: F1..F4 + H8B + B0 + SUB_O1).

MEASURED HEADLINE (2026-08-05, this stream): the matched pair is NOT
field-equal.  After id normalization, 25/41 corresponding records are
byte-model-identical; the complete remaining suspect list is FINITE:

  * ORDER   -- the physical record order differs (frame region only), BUT
               the corpus already exonerates every order predicate as a sole
               law: SUB_O1 (FAIL) carries the donor's class-order convention
               while B7 (PASS) carries the donor's native order -- no
               ordering separates all-PASS from all-FAIL.
  * FIELD   -- the self-Family "kept-ours" residue separates PERFECTLY:
               m_categoryId, m_partType, the type-table shape, the
               familyParams BIP row, the locked-BIP, absorbed/limit
               counters, m_refTypeIds, the order-cell (famgen emits TWO
               identityData groups -- a duplicate group key no native file
               has), and the header m_deletion non-element entries
               (category id + BIP ids) -- every FAIL carries OUR value,
               every PASS carries the donor's.
  * PACKING -- parity (same block/flags/packer shape both sides).

`probes` builds the morph ladder, each probe = F1 (or SUB_ALL) +/- exactly
ONE change, by byte surgery on the emitted unit (re-emission is proven
byte-exact before any edit; every in-record patch is proven
decode->encode roundtrip-stable before the patch):

  M1  F1's unit re-emitted in SUB_ALL's physical record order (pure order
      transplant; record multiset byte-identical -- proven).
  M2  the converse control: SUB_ALL's unit re-emitted in famgen roster
      order (flips to FAIL if order is the law).
  M3  F1 + the order-cell normalized to the PASS convention (the two
      identityData groups merged into one; electrical last; no dup keys).
  M4  F1 + the donor's sparse-registry counters (m_nextAbsorbedIndex 3165,
      m_predefinedLimitIdx 1963).
  M5  F1 + m_partType -1 (famdoc Family AND host Family -- the mirrored
      pair patched together; partType is the panel-schedule trigger).
  M6  F1 + the donor's m_deletion convention (our category id prepended to
      the self-Family header deletion list).
  BX_layout_f1i1  the PORT proof: the B0 recipe rebuilt through
      src/rvt/famgen/layout_law.py (id-assignment normalization to the
      M1 order convention, monotone ids -- opt-in, default OFF).

`verify` re-runs every per-probe gate; `stage` stages via tools/
probe_batch.py with TWO byte-identical controls (rst + G_ABPD).

Territory: tools/layout_diff.py, src/rvt/famgen/layout_law.py,
experiments/layout/**, tests/test_layout_law.py, docs/inbox/layout-law.md.
Probes are PROOF-ONLY sample-derived dev content, quarantined under
experiments/ (never bundled -- the deliverable rule's dev-only lane).
STAGE ONLY: the orchestrator uploads.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import sys
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import ecc                                        # noqa: E402
from rvt.container import open_rvt                         # noqa: E402
from rvt.partitions import StreamWalker, FOOTER_TAG        # noqa: E402
from rvt.objects import ObjectDecoder                      # noqa: E402
from rvt.encode import ObjectEncoder, record_stamp         # noqa: E402
from rvt.writer import gzip_member                         # noqa: E402
from rvt.roundtrip import read_entries                     # noqa: E402
from rvt.cfb_writer import write_cfb                       # noqa: E402
from rvt.famgen.loader import _walk_replace_ids            # noqa: E402
from rvt.famgen import factory as FACT                     # noqa: E402
from rvt import adocument as ADOC                          # noqa: E402

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
PART = "Partitions/21"
BLOCK_TAG = 0x0F28
TRAILER_TAG = 0x0F21
BLOCK_SIZE = 128 * 1024

OUT_DIR = os.path.join(ROOT, "experiments", "layout")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
DIFF_JSON = os.path.join(OUT_DIR, "layout_diff.json")

SUB_ALL = os.path.join(ROOT, "experiments", "subtractive", "SUB_ALL.rvt")
F1 = os.path.join(ROOT, "experiments", "famdoc_final", "F1.rvt")
H8B = os.path.join(ROOT, "experiments", "famdoc_final", "H8B.rvt")

#: the ranking corpus: every on-disk probe with a recorded per-file verdict
#: from batches 44/45/46 (genesis-audit VERDICTS #38/#39/#40).  E1/E1b (H12
#: byte-copy + blob) add nothing beyond B7's donor-shaped features and DEMO
#: v5's verdict does not localize among its 7 units -- both excluded, on
#: purpose.
PASS_FILES = {
    "SUB_ALL": SUB_ALL,
    **{f"SUB_S{i}": os.path.join(ROOT, "experiments", "subtractive", f"SUB_S{i}.rvt")
       for i in range(1, 8)},
    "SUB_S5A": os.path.join(ROOT, "experiments", "subtractive", "SUB_S5A.rvt"),
    "SUB_S5B": os.path.join(ROOT, "experiments", "subtractive", "SUB_S5B.rvt"),
    **{f"B{i}": os.path.join(ROOT, "experiments", "famdoc_blobs", f"B{i}.rvt")
       for i in range(1, 8)},
    "U12": os.path.join(ROOT, "experiments", "famdoc_final", "U12.rvt"),
    "U15": os.path.join(ROOT, "experiments", "famdoc_final", "U15.rvt"),
    "U25": os.path.join(ROOT, "experiments", "famdoc_final", "U25.rvt"),
    "U16": os.path.join(ROOT, "experiments", "famdoc_final", "U16.rvt"),
    "U12345": os.path.join(ROOT, "experiments", "famdoc_final", "U12345.rvt"),
}
FAIL_FILES = {
    "F1": F1,
    "F2": os.path.join(ROOT, "experiments", "famdoc_final", "F2.rvt"),
    "F3": os.path.join(ROOT, "experiments", "famdoc_final", "F3.rvt"),
    "F4": os.path.join(ROOT, "experiments", "famdoc_final", "F4.rvt"),
    "H8B": H8B,
    "B0": os.path.join(ROOT, "experiments", "famdoc_blobs", "B0.rvt"),
    "SUB_O1": os.path.join(ROOT, "experiments", "subtractive", "SUB_O1.rvt"),
}

MORPHS = ["M1", "M2", "M3", "M4", "M5", "M6", "BX_layout_f1i1"]

_DEC: Optional[ObjectDecoder] = None
_ENC: Optional[ObjectEncoder] = None


def _codec() -> Tuple[ObjectDecoder, ObjectEncoder]:
    global _DEC, _ENC
    if _DEC is None:
        _DEC = ObjectDecoder()
        _ENC = ObjectEncoder(decoder=_DEC)
    return _DEC, _ENC


def log(msg: str) -> None:
    print(f"[layout_diff] {msg}", flush=True)


def relp(p: str) -> str:
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:                                     # pragma: no cover
        return p


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=str)
        f.write("\n")


def _pb():
    spec = importlib.util.spec_from_file_location(
        "_layout_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    return pb


# ===========================================================================
# unit extraction (the added famdoc unit = the LAST unit of Partitions/21)
# ===========================================================================

def split_records(seg: bytes, seq: int) -> List[bytes]:
    """Whole record byte strings of one seq segment (framing: seq 101
    {i64 id, u32 psize} + psize + u32 repeat; 102/103 {i64 id, u32 stamp,
    u32 psize} + psize + u32 repeat)."""
    hl = 12 if seq == 101 else 16
    out, p, n = [], 0, len(seg)
    while p + hl <= n:
        if seq == 101:
            size = struct.unpack_from("<qI", seg, p)[1]
        else:
            size = struct.unpack_from("<qII", seg, p)[2]
        end = p + hl + size + 4
        out.append(seg[p:end])
        p = end
    if p != n:
        raise ValueError(f"seq {seq}: trailing {n - p} bytes are not a whole record")
    return out


def rec_fields(rb: bytes, seq: int) -> Dict[str, Any]:
    """Parse one whole-record byte string."""
    if seq == 101:
        eid, psize = struct.unpack_from("<qI", rb, 0)
        stamp, hl = None, 12
    else:
        eid, stamp, psize = struct.unpack_from("<qII", rb, 0)
        hl = 16
    body = rb[hl:hl + psize]
    cid = struct.unpack_from("<H", body, 0)[0] if psize >= 2 else None
    dec, _ = _codec()
    return {"eid": eid, "stamp": stamp, "psize": psize, "cid": cid,
            "cls": dec.class_name(cid) if (cid is not None and eid != -1) else None,
            "body": body, "raw": rb}


class UnitX:
    """The added unit of one probe file, decomposed to records."""

    def __init__(self, path: str, part: str = PART):
        self.path = path
        self.part = part
        with open_rvt(path) as f:
            self.logical = ecc.unframe_stream(f.raw(part))
        self.walker = StreamWalker(self.logical, inflate=True, keep_data=True)
        if self.walker.errors:
            raise RuntimeError(f"{relp(path)}: walker errors "
                               f"{self.walker.errors[:2]}")
        self.unit = self.walker.units[-1]
        self.blocks = self.walker.blocks[
            self.unit.first_block:self.unit.first_block + self.unit.n_blocks]
        self.seq_records: Dict[int, List[Dict[str, Any]]] = {}
        for b in self.blocks:
            recs = [rec_fields(rb, b.seq) for rb in split_records(b.data, b.seq)]
            self.seq_records.setdefault(b.seq, []).extend(recs)
        self.guid = str(uuid.UUID(bytes_le=bytes(self.unit.guid))) \
            if self.unit.guid else None

    def ids(self, seq: int = 102) -> List[int]:
        return [r["eid"] for r in self.seq_records[seq] if r["eid"] != -1]

    def by_id(self, seq: int) -> Dict[int, Dict[str, Any]]:
        return {r["eid"]: r for r in self.seq_records[seq]}

    def order_roles(self, seq: int = 102) -> List[Tuple[str, int]]:
        """Physical order as (class, k) where k = the record's rank among
        its class in ASCENDING-ID order -- the file-independent role key."""
        rank: Dict[int, Tuple[str, int]] = {}
        per_cls: Dict[str, List[int]] = collections.defaultdict(list)
        for r in sorted((r for r in self.seq_records[seq] if r["eid"] != -1),
                        key=lambda r: r["eid"]):
            per_cls[r["cls"]].append(r["eid"])
        for cls, idlist in per_cls.items():
            for k, eid in enumerate(idlist):
                rank[eid] = (cls, k)
        return [rank[r["eid"]] for r in self.seq_records[seq] if r["eid"] != -1]

    def self_family(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """(seq-102 Family record, its decoded value) for the unit's OWN
        self-Family: the Family-class record whose m_familyIds covers the
        most unit element ids (robust against nested mini-famdoc Families)."""
        dec, _ = _codec()
        unit_ids = set(self.ids(102))
        best, best_cover, best_val = None, -1, None
        for r in self.seq_records[102]:
            if r["cls"] != "Family":
                continue
            d = dec.decode_record(r["cid"], r["body"][2:])
            if d.errors:
                continue
            rows = (((d.value.get("m_familyIds") or {}).get("value") or {})
                    .get("m_data") or [])
            cover = sum(1 for row in rows
                        if int(row.get("m_elementId", -1)) in unit_ids)
            if cover > best_cover:
                best, best_cover, best_val = r, cover, d.value
        if best is None:
            raise RuntimeError(f"{relp(self.path)}: no decodable Family record")
        return best, best_val

    def header_of(self, eid: int) -> Dict[str, Any]:
        dec, _ = _codec()
        r = self.by_id(101)[eid]
        d = dec.decode_record(r["cid"], r["body"][2:])
        if d.errors:
            raise RuntimeError(f"{relp(self.path)} header {eid}: {d.errors[:1]}")
        return d.value

    def inline_adoc(self) -> Tuple[bytes, Dict[str, Any]]:
        with open_rvt(self.path) as f:
            cd = b"".join(f.inflate_all("Global/ContentDocuments"))
        entries, _tail = FACT.parse_content_documents(cd)
        for g, blob in entries:
            if g == self.guid:
                d = ADOC.decode_latest(blob)
                if not d.clean:
                    raise RuntimeError(f"{relp(self.path)}: added-unit inline "
                                       f"ADocument does not decode clean")
                return blob, d.value
        raise RuntimeError(f"{relp(self.path)}: no ContentDocuments entry for "
                           f"unit guid {self.guid}")


# ===========================================================================
# the matched-pair diff
# ===========================================================================

def role_alignment(a: UnitX, b: UnitX) -> Tuple[Dict[int, int],
                                                List[Tuple[str, int]],
                                                List[Tuple[str, int]]]:
    """id_a -> id_b by (class, k-th occurrence in ascending-id order).
    Returns (amap, roles only in a, roles only in b)."""
    def keyed(u: UnitX) -> Dict[str, List[int]]:
        out: Dict[str, List[int]] = collections.defaultdict(list)
        for r in sorted((r for r in u.seq_records[102] if r["eid"] != -1),
                        key=lambda r: r["eid"]):
            out[r["cls"]].append(r["eid"])
        return out
    ka, kb = keyed(a), keyed(b)
    amap: Dict[int, int] = {}
    only_a: List[Tuple[str, int]] = []
    only_b: List[Tuple[str, int]] = []
    for cls in sorted(set(ka) | set(kb)):
        la, lb = ka.get(cls, []), kb.get(cls, [])
        for i in range(max(len(la), len(lb))):
            if i < len(la) and i < len(lb):
                amap[la[i]] = lb[i]
            elif i < len(la):
                only_a.append((cls, la[i]))
            else:
                only_b.append((cls, lb[i]))
    return amap, only_a, only_b


_IDENTITY_MARKERS = ("m_guid", "GUID", "m_famDocGUID", "m_surrogateId",
                     "m_typeId")


def _is_identity_path(path: str, a: Any, b: Any) -> bool:
    """Identity-coupled leaves: GUIDs, guid-bearing local type-id strings
    (revit.local.family:<famGUID><elemIdHex>), surrogates.  The elem-id hex
    suffix is verified separately (suffix == own id in BOTH files)."""
    leaf = path.rsplit(".", 1)[-1].split("[")[0]
    if leaf in ("m_guid", "m_famDocGUID", "m_surrogateId", "m_creationGUID"):
        return True
    if isinstance(a, str) and isinstance(b, str) \
            and a.startswith("revit.local.family:") \
            and b.startswith("revit.local.family:"):
        return True
    return False


def _leaf_diff(a: Any, b: Any, path: str, out: List[Dict[str, Any]],
               limit: int = 4000) -> None:
    """Classified leaf diff.  Equal-length lists with the same multiset but
    a different sequence are ONE ORDER item (no descent); everything else
    descends to leaves."""
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _leaf_diff(a.get(k), b.get(k), f"{path}.{k}", out, limit)
        return
    if isinstance(a, list) and isinstance(b, list):
        if a == b:
            return
        if len(a) == len(b):
            ja = sorted(json.dumps(x, sort_keys=True, default=str) for x in a)
            jb = sorted(json.dumps(x, sort_keys=True, default=str) for x in b)
            if ja == jb:
                out.append({"path": path, "kind": "ORDER",
                            "note": f"same {len(a)} entries, different sequence"})
                return
        if len(a) != len(b):
            out.append({"path": f"{path}#len", "kind": "FIELD",
                        "a": len(a), "b": len(b)})
            return
        for j, (x, y) in enumerate(zip(a, b)):
            _leaf_diff(x, y, f"{path}[{j}]", out, limit)
        return
    if a != b:
        kind = "IDENTITY" if _is_identity_path(path, a, b) else "FIELD"
        out.append({"path": path, "kind": kind,
                    "a": str(a)[:160], "b": str(b)[:160]})


def _localfam_suffix_ok(u: UnitX) -> Dict[str, Any]:
    """Verify the revit.local.family:<guid><elemIdHex> law: every such
    type-id inside a record whose element id is known must end in the hex of
    an id -- measured here as: for ParamElemFamily records, suffix ==
    the record's OWN element id."""
    dec, _ = _codec()
    ok, bad = 0, []
    for r in u.seq_records[102]:
        if r["cls"] != "ParamElemFamily":
            continue
        d = dec.decode_record(r["cid"], r["body"][2:])
        tid = ((((d.value.get("m_pParamDef") or {}).get("value") or {})
                .get("m_typeId") or {}).get("m_typeId") or "")
        if not tid.startswith("revit.local.family:"):
            continue
        suffix = tid.split(":", 1)[1].split("-", 1)[0][-8:]
        if int(suffix, 16) == r["eid"]:
            ok += 1
        else:
            bad.append({"eid": r["eid"], "suffix": suffix})
    return {"params_checked": ok + len(bad), "suffix_matches_own_id": ok,
            "mismatches": bad}


def pair_diff(a: UnitX, b: UnitX, name_a: str, name_b: str) -> Dict[str, Any]:
    """The complete classified diff of two added units."""
    dec, _ = _codec()
    amap, only_a, only_b = role_alignment(a, b)
    items: List[Dict[str, Any]] = []

    # ---- CONTENT: roster delta -------------------------------------------
    if only_a or only_b:
        items.append({"surface": "roster", "kind": "CONTENT",
                      "path": "unit.elements",
                      "a_only": [f"{c}#{k}" for c, k in only_a],
                      "b_only": [f"{c}#{k}" for c, k in only_b],
                      "note": "elements with no counterpart (verdict #40's "
                              "'content equal' holds only at this-many-"
                              "elements granularity)"})

    # ---- ORDER: physical record order ------------------------------------
    ord_a = a.order_roles()
    ord_b = b.order_roles()
    common = set(ord_a) & set(ord_b)
    proj_a = [x for x in ord_a if x in common]
    proj_b = [x for x in ord_b if x in common]
    items.append({
        "surface": "record-order", "kind": "ORDER", "path": "unit.seq102.order",
        "equal_on_common_roles": proj_a == proj_b,
        "a": [f"{c}#{k}" for c, k in ord_a],
        "b": [f"{c}#{k}" for c, k in ord_b],
        "first_divergence": next((i for i, (x, y) in
                                  enumerate(zip(proj_a, proj_b)) if x != y),
                                 None),
    })
    for u, nm in ((a, name_a), (b, name_b)):
        ids102 = u.ids(102)
        items.append({"surface": "record-order", "kind": "ORDER",
                      "path": f"{nm}.invariants",
                      "ascending_id": ids102 == sorted(ids102),
                      "seq101_same_order": u.ids(101) == ids102,
                      "seq103_same_order": u.ids(103) == ids102})

    # ---- PACKING: blocks / envelope --------------------------------------
    pk = {}
    for u, nm in ((a, name_a), (b, name_b)):
        pk[nm] = {
            "blocks": [{"seq": blk.seq, "flags": blk.flags,
                        "records": blk.n_records, "payload": len(blk.data)}
                       for blk in u.blocks],
            "footer_blob_len": len(u.unit.footer_blob),
            "counter": u.unit.counter,
            "n_elements": len(u.ids(102)),
        }
    items.append({
        "surface": "packing", "kind": "PACKING", "path": "unit.blocks",
        "a": pk[name_a], "b": pk[name_b],
        "parity": (len(pk[name_a]["blocks"]) == len(pk[name_b]["blocks"])
                   and all(x["seq"] == y["seq"] and x["flags"] == y["flags"]
                           for x, y in zip(pk[name_a]["blocks"],
                                           pk[name_b]["blocks"]))),
        "note": "counter == n_elements in both (roster-coupled); blob 64 B "
                "both (E1b: content-indifferent)"})

    # ---- FIELD: per-record id-normalized decoded diff ---------------------
    rec_items: List[Dict[str, Any]] = []
    n_eq = 0
    for eid_a in sorted(amap):
        eid_b = amap[eid_a]
        rec_all_eq = True
        for seq in (101, 102, 103):
            ra = a.by_id(seq).get(eid_a)
            rb = b.by_id(seq).get(eid_b)
            if ra is None or rb is None or ra["cid"] != rb["cid"]:
                rec_items.append({"surface": "record", "kind": "CONTENT",
                                  "path": f"seq{seq}.{eid_a}->{eid_b}",
                                  "note": "missing or class-mismatched record"})
                rec_all_eq = False
                continue
            da = dec.decode_record(ra["cid"], ra["body"][2:])
            db = dec.decode_record(rb["cid"], rb["body"][2:])
            if da.errors or db.errors:
                rec_items.append({"surface": "record", "kind": "CONTENT",
                                  "path": f"seq{seq}.{eid_a}->{eid_b}",
                                  "note": f"decode errors a={da.errors[:1]} "
                                          f"b={db.errors[:1]}"})
                rec_all_eq = False
                continue
            va = copy.deepcopy(da.value)
            _walk_replace_ids(va, amap)
            diffs: List[Dict[str, Any]] = []
            _leaf_diff(va, db.value, ra["cls"], diffs)
            if diffs:
                rec_all_eq = False
                for d in diffs:
                    d.update({"surface": "record",
                              "record": f"{ra['cls']} {eid_a}->{eid_b} seq{seq}"})
                rec_items.extend(diffs)
        if rec_all_eq:
            n_eq += 1
    items.extend(rec_items)

    # ---- IDENTITY: local-family type-id suffix law ------------------------
    items.append({"surface": "identity", "kind": "IDENTITY",
                  "path": "revit.local.family suffix",
                  "a": _localfam_suffix_ok(a), "b": _localfam_suffix_ok(b),
                  "note": "suffix == own element id in BOTH -> the typeId "
                          "delta is the family GUID only (pure identity)"})

    # ---- inline ADocument -------------------------------------------------
    blob_a, val_a = a.inline_adoc()
    blob_b, val_b = b.inline_adoc()

    def adoc_row_info(u: UnitX, val: Dict[str, Any]) -> Dict[str, Any]:
        et = ((val.get("m_elemTable") or {}).get("value") or {})
        arr = et.get("m_elemArr") or []
        ids = [int(r.get("m_id", -1)) for r in arr]
        src = ((et.get("m_pSource") or {}).get("value") or {})
        return {"rows": len(arr), "ascending": ids == sorted(ids),
                "rows_equal_unit_ids": set(ids) == set(u.ids(102)),
                "m_last": src.get("m_last")}
    top_sizes = {}
    for k in sorted(set(val_a) | set(val_b)):
        sa = len(json.dumps(val_a.get(k), default=str))
        sb = len(json.dumps(val_b.get(k), default=str))
        if abs(sa - sb) > 64:
            top_sizes[k] = {"a_json_bytes": sa, "b_json_bytes": sb}
    items.append({
        "surface": "inline-adoc", "kind": "FIELD", "path": "ContentDocuments",
        "a": dict(adoc_row_info(a, val_a), bytes=len(blob_a)),
        "b": dict(adoc_row_info(b, val_b), bytes=len(blob_b)),
        "top_level_size_deltas": top_sizes,
        "note": "ElemTable rows == unit ids, ascending, m_last == max in "
                "BOTH; the byte delta is the donor's deep registries vs our "
                "authored minimal form -- the our-authored form is "
                "EXONERATED as a sole axis by B6 + U12345 (both PASS)"})

    return {
        "pair": {"a": {"name": name_a, "file": relp(a.path), "md5": md5_of(a.path),
                       "unit_guid": a.guid, "n_elements": len(a.ids(102))},
                 "b": {"name": name_b, "file": relp(b.path), "md5": md5_of(b.path),
                       "unit_guid": b.guid, "n_elements": len(b.ids(102))}},
        "alignment": {"pairs": len(amap),
                      "records_fully_equal_after_id_normalization": n_eq},
        "items": items,
    }


# ===========================================================================
# host-side diff (base-matched: SUB_ALL vs H8B, both rst + famload)
# ===========================================================================

def host_diff(a_path: str, b_path: str) -> Dict[str, Any]:
    """The HOST-side registration delta between two probes (added ElemTable
    rows, ContentDocuments entry census, changed streams).  Run base-matched
    (SUB_ALL vs H8B: same rst base, same famload loader, PASS vs FAIL) the
    delta is suspect; run cross-base (vs F1 on G_ABPD) it is BASE-COUPLED."""
    from rvt.stream_encoders import decode_elemtable
    out: Dict[str, Any] = {}
    A, B = open_rvt(a_path), open_rvt(b_path)
    try:
        na = {s.name for s in A.streams()}
        nb = {s.name for s in B.streams()}
        out["stream_sets_equal"] = na == nb
        out["only_a"], out["only_b"] = sorted(na - nb), sorted(nb - na)
        changed = sorted(n for n in na & nb if A.raw(n) != B.raw(n))
        out["streams_differing"] = changed
        ea = decode_elemtable(A.inflate("Global/ElemTable", 0))
        eb = decode_elemtable(B.inflate("Global/ElemTable", 0))
        out["elemtable_rows"] = {"a": len(ea["records"]), "b": len(eb["records"])}

        def added_row_order(rows: List[Any], base_path: str) -> Dict[str, Any]:
            with open_rvt(base_path) as Bf:
                base_ids = {r[4] for r in
                            decode_elemtable(Bf.inflate("Global/ElemTable", 0))["records"]}
            added = [(i, r[4]) for i, r in enumerate(rows) if r[4] not in base_ids]
            ids = [x for _i, x in added]
            pos = [i for i, _x in added]
            return {"added_rows": len(added),
                    "appended_at_tail": pos == list(range(len(rows) - len(added),
                                                          len(rows))),
                    "ascending": ids == sorted(ids)}

        def base_of_probe(path: str) -> str:
            return G_ABPD if os.path.basename(path) in (
                "F1.rvt", "F2.rvt", "F3.rvt", "F4.rvt", "B0.rvt",
                "SUB_O1.rvt") else RST
        out["elemtable_added_row_order"] = {
            "a": added_row_order(ea["records"], base_of_probe(a_path)),
            "b": added_row_order(eb["records"], base_of_probe(b_path)),
            "note": "the charter's 'ElemTable row order for the unit': the "
                    "host-side ADD rows (the famdoc unit itself contributes "
                    "no host ElemTable rows -- self-contained); measured "
                    "appended-at-tail ascending in SUB_ALL, H8B AND F1 -> "
                    "PARITY"}
        cda = b"".join(A.inflate_all("Global/ContentDocuments"))
        cdb = b"".join(B.inflate_all("Global/ContentDocuments"))
        out["content_documents_entries"] = {
            "a": len(FACT.parse_content_documents(cda)[0]),
            "b": len(FACT.parse_content_documents(cdb)[0])}
    finally:
        A.close()
        B.close()
    return out


# ===========================================================================
# corpus features + ranking
# ===========================================================================

def unit_features(u: UnitX) -> Dict[str, Any]:
    """The measurable feature vector of one added unit (self-Family residue,
    order fingerprints, adoc shape) -- every candidate the matched pair
    surfaced, computed generically so it evaluates on every corpus file."""
    sf_rec, sf = u.self_family()
    hdr = u.header_of(sf_rec["eid"])
    unit_ids = set(u.ids(102))
    par = ((hdr.get("m_parents") or {}).get("value") or {})
    dele = par.get("m_deletion") or []
    fp_rows = (((sf.get("m_familyParams") or {}).get("value") or {})
               .get("m_params") or [])
    fam_rows = (((sf.get("m_familyIds") or {}).get("value") or {})
                .get("m_data") or [])
    ftt = ((sf.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    locked = sf.get("m_lockedParameterIdsForDirectManipulation") or []
    cells = (((sf.get("m_cellList") or {}).get("value") or {})
             .get("m_cells") or [])
    groups: List[str] = []
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        for g in cv.get("m_sortedParams") or []:
            if isinstance(g, dict):
                tid = str((g.get("m_groupTypeId") or {}).get("m_typeId"))
                groups.append(tid.rsplit(":", 1)[-1].split("-")[0])
        break
    ids102 = u.ids(102)
    order = u.order_roles()
    first_pos = {}
    for i, (cls, _k) in enumerate(order):
        first_pos.setdefault(cls, i)
    viewer_pos = first_pos.get("Viewer")
    dbvp_pos = first_pos.get("DBViewProject")
    max_fam_idx = max((int(r.get("m_index", -1)) for r in fam_rows), default=-1)
    blob_, aval = u.inline_adoc()
    return {
        "n_elements": len(ids102),
        "ascending_id": ids102 == sorted(ids102),
        "sf_categoryId": sf.get("m_categoryId"),
        "sf_partType": sf.get("m_partType"),
        "sf_n_type_pairs": len(pairs),
        "sf_type_idx": ftt.get("m_idx"),
        "sf_familyParams_rows": len(fp_rows),
        "sf_familyParams_has_bip_row": any(
            isinstance(r.get("m_paramId"), int) and r["m_paramId"] < 0
            for r in fp_rows),
        "sf_locked_has_bip": any(isinstance(x, int) and x < 0 for x in locked),
        "sf_nextAbsorbedIndex": sf.get("m_nextAbsorbedIndex"),
        "sf_absorbed_sparse": (isinstance(sf.get("m_nextAbsorbedIndex"), int)
                               and sf["m_nextAbsorbedIndex"] > len(fam_rows) + 1),
        "sf_predefinedLimitIdx": sf.get("m_predefinedLimitIdx"),
        "sf_refTypeIds_len": len(sf.get("m_refTypeIds") or []),
        "sf_deletable_len": len(sf.get("m_deletableElements") or []),
        "sf_fsdos_len": len(sf.get("m_fsdos") or []),
        "cell_groups": groups,
        "cell_dup_group_keys": len(groups) != len(set(groups)),
        "cell_has_materials": "materials" in groups,
        "hdr_deletion_nonelement": sorted(x for x in dele
                                          if isinstance(x, int)
                                          and x not in unit_ids),
        "hdr_deletion_has_category": (isinstance(sf.get("m_categoryId"), int)
                                      and sf["m_categoryId"] in dele),
        "order_viewer_before_viewproject": (
            None if viewer_pos is None or dbvp_pos is None
            else viewer_pos < dbvp_pos),
        "order_first8": ",".join(c for c, _k in order[:8]),
        "adoc_bytes": len(blob_),
        # authoring DEPTH, not roster size: donor-derived inline ADocuments
        # carry deep registries (~480 B/row on the matched pair); our
        # authored form is ~72 B/row at any roster size
        "adoc_bytes_per_row": round(len(blob_) / max(len(unit_ids), 1), 1),
        "adoc_deep": (len(blob_) / max(len(unit_ids), 1)) > 150,
        "max_familyIds_index_gap": max_fam_idx + 1 - len(fam_rows),
    }


#: candidate predicates for the ranking: name -> fn(features) -> bool
CANDIDATES: Dict[str, Any] = {
    "sf_category_is_ours_electrical": lambda f: f["sf_categoryId"] == -2001040,
    "sf_partType_set (not -1)": lambda f: f["sf_partType"] != -1,
    "sf_single_type_pair": lambda f: f["sf_n_type_pairs"] == 1,
    "sf_type_idx_zero": lambda f: f["sf_type_idx"] == 0,
    "sf_familyParams_no_bip_row": lambda f: not f["sf_familyParams_has_bip_row"],
    "sf_locked_no_bip": lambda f: not f["sf_locked_has_bip"],
    "sf_absorbed_dense (no history gap)": lambda f: not f["sf_absorbed_sparse"],
    "sf_predefinedLimitIdx_small": lambda f: (
        isinstance(f["sf_predefinedLimitIdx"], int)
        and f["sf_predefinedLimitIdx"] < 100),
    "sf_refTypeIds_empty": lambda f: f["sf_refTypeIds_len"] == 0,
    "sf_deletable_empty": lambda f: f["sf_deletable_len"] == 0,
    "sf_fsdos_empty": lambda f: f["sf_fsdos_len"] == 0,
    "cell_dup_identity_groups": lambda f: f["cell_dup_group_keys"],
    "cell_no_materials_group": lambda f: not f["cell_has_materials"],
    "hdr_deletion_elements_only": lambda f: not f["hdr_deletion_nonelement"],
    "hdr_deletion_lacks_category": lambda f: not f["hdr_deletion_has_category"],
    "order_view_before_viewer": lambda f: f["order_viewer_before_viewproject"] is False,
    "adoc_authored_minimal": lambda f: not f["adoc_deep"],
    "ascending_id": lambda f: f["ascending_id"],
}


def corpus_rank() -> Dict[str, Any]:
    """Evaluate every candidate predicate on every corpus file; a candidate
    is TOP-RANKED when TRUE on every FAIL and FALSE on every PASS."""
    feats: Dict[str, Dict[str, Any]] = {}
    verdicts: Dict[str, str] = {}
    missing: List[str] = []
    for name, path in {**PASS_FILES, **FAIL_FILES}.items():
        if not os.path.isfile(path):
            missing.append(name)
            continue
        log(f"features: {name}")
        feats[name] = unit_features(UnitX(path))
        verdicts[name] = "PASS" if name in PASS_FILES else "FAIL"
    table: List[Dict[str, Any]] = []
    for cname, fn in CANDIDATES.items():
        vals = {n: bool(fn(f)) for n, f in feats.items()}
        in_fail = [n for n, v in vals.items() if v and verdicts[n] == "FAIL"]
        in_pass = [n for n, v in vals.items() if v and verdicts[n] == "PASS"]
        n_fail = sum(1 for n in vals if verdicts[n] == "FAIL")
        n_pass = sum(1 for n in vals if verdicts[n] == "PASS")
        separates = (len(in_fail) == n_fail and not in_pass)
        table.append({"candidate": cname,
                      "true_in_fail": f"{len(in_fail)}/{n_fail}",
                      "true_in_pass": f"{len(in_pass)}/{n_pass}",
                      "pass_offenders": in_pass[:6],
                      "fail_missers": [n for n in vals
                                       if verdicts[n] == "FAIL"
                                       and not vals[n]][:6],
                      "separates_perfectly": separates})
    table.sort(key=lambda r: (not r["separates_perfectly"], r["candidate"]))
    return {"features": feats, "verdicts": verdicts,
            "missing_files": missing, "ranking": table}


# ===========================================================================
# enumerate
# ===========================================================================

def decision_table(top_candidates: Sequence[str]) -> Dict[str, Any]:
    """The verdict->action map for batch 47 (the morph round), written
    BEFORE upload so the reading is mechanical."""
    return {
        "premise_check": {
            "verdict_40_claim": "content equal, construction different => "
                                "physical layout",
            "measured": "REFUTED at field granularity: the pair shares 25/41 "
                        "byte-model-identical records but the self-Family "
                        "record + header carry a kept-ours residue that "
                        "separates the whole corpus perfectly; every pure "
                        "ORDER predicate is already exonerated "
                        "observationally (SUB_O1 FAIL with donor-convention "
                        "order x B7 PASS with donor-native order)",
            "perfectly_separating_candidates": list(top_candidates),
        },
        "verdict_map": {
            "CTRL FAIL": "that base's probes VOID; re-stage.",
            "M1 PASS (order transplant saves F1)": (
                "record order IS audited despite SUB_O1/B7 -- port ships: "
                "layout_law.normalize_doc(order='donor_frame_first') "
                "becomes the emission default; build DEMO_250v_room_v6 "
                "through it (tools/layout_diff.py has the injection point "
                "proven by BX_layout_f1i1) and stage v6 + fresh control."),
            "M1 FAIL + M2 PASS": (
                "order fully exonerated BOTH directions experimentally -- "
                "the law is field residue; read M3..M6."),
            "M2 FAIL (re-ordered SUB_ALL stops passing)": (
                "order matters on donor content too: the lawful shape is "
                "SUB_ALL's exact artifact (frame-first + monotone) -- "
                "port as for M1 PASS but treat M2 as the stronger proof."),
            "M3 PASS": ("the duplicate identityData group key is the "
                        "defect: make normalize_order_cell part of "
                        "finalize (famgen fix, 1 line call), rebuild v6."),
            "M4 PASS": ("dense absorbed/limit counters are the defect: "
                        "famgen fakes an edit-history gap at finalize "
                        "(nextAbsorbedIndex/predefinedLimitIdx floors)."),
            "M5 PASS": ("partType 14 without panel infrastructure is the "
                        "defect: ship partType -1 until the panel-schedule "
                        "infra is authored (deliverable stays a working "
                        "panelboard family; partType is metadata)."),
            "M6 PASS": ("the deletion-parent convention is the defect: "
                        "finalize prepends the category id (+ measured "
                        "non-element parents) to the self-Family header "
                        "m_deletion."),
            "BX_layout_f1i1": ("tracks M1/M2: the port's end-to-end proof; "
                               "PASS with M1 => normalize_doc is the fix "
                               "vehicle as-built."),
            "ALL SEVEN FAIL": (
                "the residue is a conjunction or sits in the five "
                "UNPROBED separating candidates (m_categoryId itself, the "
                "single-type-pair table, m_refTypeIds, the locked/"
                "familyParams BIP row, the missing materials group). Next "
                "round builds them through the famgen chain, not byte "
                "surgery: BX_cat_gm (the B0 recipe with category="
                "generic_model -- flips category+partType coherently "
                "through every surface), BX_types_5 (five-type table), "
                "BX_bip (the -1001205 row). The matched-pair diff proves "
                "these five + the four probed ones are the COMPLETE "
                "remaining suspect list inside the unit."),
        },
        "v6_gate": {
            "commissioned": "DEMO_250v_room_v6 through the layout law, "
                            "speculatively",
            "decision": "HELD, not built: 'confidently authorable' is NOT "
                        "met -- the order axis the port normalizes is "
                        "corpus-exonerated as a sole law before upload "
                        "(SUB_O1 x B7), so v6-through-layout_law would "
                        "re-test a hypothesis two existing verdicts "
                        "already reject. The port + injection point are "
                        "built and BX_layout_f1i1 proves them end-to-end; "
                        "v6 is one command behind whichever morph verdict "
                        "names the law.",
        },
    }


def enumerate_diff() -> Dict[str, Any]:
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    log("matched pair: SUB_ALL (PASS) vs F1 (FAIL) ...")
    a = UnitX(SUB_ALL)
    b = UnitX(F1)
    pd_main = pair_diff(a, b, "SUB_ALL", "F1")
    log("base+loader-matched: SUB_ALL (PASS) vs H8B (FAIL, rst+famload) ...")
    h = UnitX(H8B)
    pd_matched = pair_diff(a, h, "SUB_ALL", "H8B")
    log("host-side diffs ...")
    hd_matched = host_diff(SUB_ALL, H8B)
    hd_cross = host_diff(SUB_ALL, F1)
    hd_cross["classification"] = ("BASE-COUPLED (rst vs G_ABPD): separated "
                                  "from layout deltas by the H8B pairing")
    log("corpus feature ranking ...")
    rank = corpus_rank()
    top = [r["candidate"] for r in rank["ranking"] if r["separates_perfectly"]]
    order_items = [i for i in pd_main["items"] if i["kind"] == "ORDER"]
    field_items = [i for i in pd_main["items"] if i["kind"] == "FIELD"]

    out = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool": "tools/layout_diff.py enumerate",
        "charter": "layout-law: name the physical-layout law behind "
                   "SUB_ALL PASS vs F1 FAIL (verdict #40)",
        "headline": {
            "content_equal_claim": "REFUTED at field granularity: the pair "
                                   "is element-roster-equal (mod 2 "
                                   "BrowserOrganization) and 25/41 records "
                                   "are byte-model-identical after id "
                                   "normalization, but the self-Family "
                                   "record + its header carry a finite "
                                   "kept-ours residue that separates "
                                   "PERFECTLY across the corpus",
            "order_axis": "corpus-exonerated as a sole law: SUB_O1 (FAIL) "
                          "carries the donor class-order convention while "
                          "B7 (PASS) carries the donor's native order -- "
                          "no order predicate is true in all FAIL and "
                          "false in all PASS; M1/M2 remain the direct "
                          "experimental test",
            "top_ranked_candidates": top,
        },
        "matched_pair": pd_main,
        "base_loader_matched_pair": pd_matched,
        "host_side": {"base_matched_SUB_ALL_vs_H8B": hd_matched,
                      "cross_base_SUB_ALL_vs_F1": hd_cross},
        "corpus": rank,
        "decision_table": decision_table(top),
        "elapsed_s": round(time.time() - t0, 1),
    }
    jdump(DIFF_JSON, out)
    n_sep = len(top)
    log(f"layout_diff.json written: {len(order_items)} ORDER items, "
        f"{len(field_items)} FIELD items, {n_sep} perfectly-separating "
        f"candidates, {out['elapsed_s']}s")
    return out


# ===========================================================================
# morph machinery (byte surgery, identity-gated)
# ===========================================================================

def rebuild_last_unit(u: UnitX, seq_records: Dict[int, List[bytes]]) -> bytes:
    """The whole logical stream with the LAST unit's blocks re-emitted from
    ``seq_records`` (whole-record byte strings per seq).  Everything before
    the unit's 28-byte separator and the end record after it are copied
    verbatim; the separator, terminator, footer blob and footer text are
    copied from the source unit."""
    logical, w, unit = u.logical, u.walker, u.unit
    first = w.blocks[unit.first_block]
    sep_start = first.hdr_offset - 28 if unit.index > 0 else first.hdr_offset
    out = bytearray(logical[:sep_start])
    if unit.index > 0:
        out += logical[sep_start:first.hdr_offset]
    hdr_len = {101: 16, 102: 20, 103: 20}
    for seq in (101, 102, 103):
        recs = seq_records[seq]
        blocks_, cur = [], bytearray()
        for rb in recs:
            if cur and len(cur) + len(rb) > BLOCK_SIZE:
                blocks_.append(bytes(cur))
                cur = bytearray()
            cur += rb
        blocks_.append(bytes(cur))
        for pay in blocks_:
            A = len(split_records(pay, seq))
            C = len(pay) - hdr_len[seq] * A
            gz = gzip_member(pay, level=3, sync_flush=True)
            B = 8 + len(gz)
            out += struct.pack("<HIIIIII", BLOCK_TAG, 4, A, B, C, seq, 0)
            out += gz
            out += struct.pack("<HI", TRAILER_TAG, B)
    out += logical[unit.footer_offset:unit.footer_offset + 18]
    blob = unit.footer_blob
    out += struct.pack("<HI", FOOTER_TAG, len(blob)) + blob
    txt = unit.footer_text.encode("utf-16-le")
    out += struct.pack("<I", len(unit.footer_text)) + txt
    out += w.end_record
    return bytes(out)


def identity_gate(u: UnitX) -> None:
    """REFUSE unless a no-edit re-emission reproduces the source logical
    stream byte-exactly (the packer/gzip recipe matches the file's)."""
    src = {seq: [r["raw"] for r in recs] for seq, recs in u.seq_records.items()}
    if rebuild_last_unit(u, src) != u.logical:
        raise RuntimeError(f"{relp(u.path)}: rebuild-identity gate REFUSED "
                           f"(no-edit reassembly is not byte-exact)")


def patch_record(u: UnitX, seq: int, eid: int, mutate) -> Tuple[bytes, Dict[str, Any]]:
    """One record of the last unit re-encoded with ``mutate(value)`` applied
    to its decoded object.  Refuses unless the UNPATCHED decode->encode
    roundtrip is byte-exact (so the re-emitted delta is exactly the patch).
    Returns (new whole-record bytes, report)."""
    dec, enc = _codec()
    r = u.by_id(seq)[eid]
    cid = r["cid"]
    d = dec.decode_record(cid, r["body"][2:])
    if d.errors:
        raise RuntimeError(f"decode errors on {r['cls']} {eid}: {d.errors[:1]}")
    if enc.encode_object(cid, d.value) != r["body"][2:]:
        raise RuntimeError(f"roundtrip gate REFUSED on {r['cls']} {eid}: "
                           f"encode(decode(x)) != x")
    val = copy.deepcopy(d.value)
    note = mutate(val)
    body = enc.encode_object(cid, val)
    payload = struct.pack("<H", cid) + body
    ps = len(payload)
    if seq == 101:
        raw = struct.pack("<qI", eid, ps) + payload + struct.pack("<I", ps)
    else:
        st = record_stamp(cid, body)
        raw = (struct.pack("<qII", eid, st, ps) + payload
               + struct.pack("<I", ps))
    return raw, {"eid": eid, "cls": r["cls"], "seq": seq,
                 "psize": {"was": r["psize"], "now": ps}, "change": note}


def patch_host_record(u: UnitX, eid: int, mutate) -> Tuple[bytes, Dict[str, Any]]:
    """The same single-record patch applied to a HOST-side seq-102 record
    (any unit but the last): the containing block alone is re-emitted, every
    other byte of the logical stream verbatim.  Gates: the block's
    re-gzip must be byte-exact pre-patch AND the record roundtrip must hold."""
    dec, enc = _codec()
    logical, w = u.logical, u.walker
    for blk in w.blocks[:u.unit.first_block]:
        if blk.seq != 102:
            continue
        recs = split_records(blk.data, 102)
        idx = next((i for i, rb in enumerate(recs)
                    if struct.unpack_from("<q", rb, 0)[0] == eid), None)
        if idx is None:
            continue
        member = logical[blk.member_offset:blk.member_offset + blk.member_len]
        if gzip_member(blk.data, level=3, sync_flush=True) != member:
            raise RuntimeError(f"host block (unit {blk.unit} seq102) re-gzip "
                               f"is not byte-exact -- REFUSING host surgery")
        r = rec_fields(recs[idx], 102)
        d = dec.decode_record(r["cid"], r["body"][2:])
        if d.errors:
            raise RuntimeError(f"host record {eid} decode errors: {d.errors[:1]}")
        if enc.encode_object(r["cid"], d.value) != r["body"][2:]:
            raise RuntimeError(f"host record {eid} roundtrip gate REFUSED")
        val = copy.deepcopy(d.value)
        note = mutate(val)
        body = enc.encode_object(r["cid"], val)
        payload = struct.pack("<H", r["cid"]) + body
        ps = len(payload)
        st = record_stamp(r["cid"], body)
        new_rec = (struct.pack("<qII", eid, st, ps) + payload
                   + struct.pack("<I", ps))
        recs[idx] = new_rec
        pay = b"".join(recs)
        A = len(recs)
        C = len(pay) - 20 * A
        gz = gzip_member(pay, level=3, sync_flush=True)
        B = 8 + len(gz)
        out = bytearray(logical[:blk.hdr_offset])
        out += struct.pack("<HIIIIII", BLOCK_TAG, blk.flags, A, B, C, 102, 0)
        out += gz
        out += struct.pack("<HI", TRAILER_TAG, B)
        out += logical[blk.member_offset + blk.member_len + 6:]
        return bytes(out), {"eid": eid, "cls": r["cls"], "host_unit": blk.unit,
                            "psize": {"was": r["psize"], "now": ps},
                            "change": note}
    raise RuntimeError(f"host seq-102 record {eid} not found")


def emit_probe(name: str, src_path: str, new_logical: bytes) -> str:
    """Write the probe file: src's container with Partitions/21 replaced."""
    import dataclasses
    os.makedirs(OUT_DIR, exist_ok=True)
    outp = os.path.join(OUT_DIR, f"{name}.rvt")
    stream = ecc.frame_stream(new_logical)
    entries = read_entries(src_path)
    out_entries = [dataclasses.replace(e, data=stream)
                   if (e.entry_type == "stream" and e.path == PART) else e
                   for e in entries]
    write_cfb(outp, out_entries)
    return outp


def apply_order(u: UnitX, target_roles: Sequence[Tuple[str, int]],
                extra_last: Sequence[Tuple[str, int]] = ()) -> Dict[int, List[bytes]]:
    """Record byte strings of every seq re-sequenced to ``target_roles``
    (+ ``extra_last`` roles appended, sentinel kept last).  Every seq gets
    the SAME id order.  Content untouched: the per-seq record byte multisets
    are asserted permutation-equal by the caller's gates."""
    rank: Dict[Tuple[str, int], int] = {}
    per_cls: Dict[str, List[int]] = collections.defaultdict(list)
    for r in sorted((r for r in u.seq_records[102] if r["eid"] != -1),
                    key=lambda r: r["eid"]):
        per_cls[r["cls"]].append(r["eid"])
    id_of: Dict[Tuple[str, int], int] = {}
    for cls, idlist in per_cls.items():
        for k, eid in enumerate(idlist):
            id_of[(cls, k)] = eid
    want = list(target_roles) + list(extra_last)
    if sorted(id_of) != sorted(want):
        raise RuntimeError(f"role sets differ: unit has {len(id_of)} roles, "
                           f"target names {len(want)}")
    id_order = [id_of[role] for role in want]
    out: Dict[int, List[bytes]] = {}
    for seq, recs in u.seq_records.items():
        by = {r["eid"]: r["raw"] for r in recs}
        sent = [r["raw"] for r in recs if r["eid"] == -1]
        if len(sent) != 1 or recs[-1]["eid"] != -1:
            raise RuntimeError(f"seq {seq}: sentinel not last")
        out[seq] = [by[i] for i in id_order] + sent
    return out


# ---------------------------------------------------------------------------
# the six morphs + the port probe
# ---------------------------------------------------------------------------

def build_m1() -> Dict[str, Any]:
    """M1: F1's unit re-emitted in SUB_ALL's physical record order."""
    a, b = UnitX(SUB_ALL), UnitX(F1)
    identity_gate(b)
    target = a.order_roles()
    extra = [role for role in b.order_roles() if role[0] == "BrowserOrganization"]
    seqs = apply_order(b, target, extra_last=extra)
    for seq in seqs:
        before = sorted(r["raw"] for r in b.seq_records[seq])
        after = sorted(seqs[seq])
        if before != after:
            raise RuntimeError(f"M1 seq {seq}: record multiset changed -- "
                               f"not a pure order transplant")
    outp = emit_probe("M1", F1, rebuild_last_unit(b, seqs))
    return {"probe": "M1", "file": relp(outp), "base": relp(G_ABPD),
            "source": relp(F1), "md5": md5_of(outp),
            "axis": "ORDER: F1's 44 records physically re-sequenced to "
                    "SUB_ALL's record-order convention (self-Family, "
                    "proj viewer/view/drawing/viewport, units, then content "
                    "in famgen order); the 2 BrowserOrganization records "
                    "(no SUB_ALL counterpart) stay last; ids, bytes, "
                    "stamps, blob all untouched",
            "content_untouched_proof": "per-seq record byte multisets "
                                       "asserted permutation-equal",
            "expected": "PASS convicts record order (and contradicts the "
                        "SUB_O1/B7 corpus exoneration -- re-read both); "
                        "FAIL confirms order is not the law"}


def build_m2() -> Dict[str, Any]:
    """M2: SUB_ALL's unit re-emitted in famgen roster order (converse)."""
    a, b = UnitX(SUB_ALL), UnitX(F1)
    identity_gate(a)
    target = [role for role in b.order_roles() if role[0] != "BrowserOrganization"]
    seqs = apply_order(a, target)
    for seq in seqs:
        if sorted(r["raw"] for r in a.seq_records[seq]) != sorted(seqs[seq]):
            raise RuntimeError(f"M2 seq {seq}: record multiset changed")
    outp = emit_probe("M2", SUB_ALL, rebuild_last_unit(a, seqs))
    return {"probe": "M2", "file": relp(outp), "base": relp(RST),
            "source": relp(SUB_ALL), "md5": md5_of(outp),
            "axis": "ORDER converse: SUB_ALL's 42 records re-sequenced to "
                    "the famgen roster convention (self, units, level type, "
                    "level, proj view/viewer/viewport/drawing, ...); "
                    "content untouched",
            "content_untouched_proof": "per-seq record byte multisets "
                                       "asserted permutation-equal",
            "expected": "FAIL convicts order (SUB_ALL's own content stops "
                        "passing when re-ordered); PASS confirms order is "
                        "not the law"}


def _cell_groups(val: Dict[str, Any]) -> List[Dict[str, Any]]:
    cells = (((val.get("m_cellList") or {}).get("value") or {})
             .get("m_cells") or [])
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        sp = cv.get("m_sortedParams")
        if isinstance(sp, list):
            return sp
    raise RuntimeError("no m_sortedParams order cell")


def build_m3() -> Dict[str, Any]:
    """M3: F1 + the order-cell normalized to the PASS convention (merge the
    duplicate identityData groups; electrical last; no dup keys)."""
    b = UnitX(F1)
    identity_gate(b)
    sf_rec, _sf = b.self_family()

    def mutate(val: Dict[str, Any]) -> Dict[str, Any]:
        sp = _cell_groups(val)
        by_key: Dict[str, Dict[str, Any]] = {}
        merged = []
        for g in sp:
            key = str((g.get("m_groupTypeId") or {}).get("m_typeId"))
            if key in by_key:
                by_key[key]["m_paramIds"].extend(g.get("m_paramIds") or [])
            else:
                by_key[key] = g
                merged.append(g)
        def rank(g):
            tid = str((g.get("m_groupTypeId") or {}).get("m_typeId"))
            if "electrical" in tid:
                return 2
            if "identity" in tid.lower():
                return 1
            return 0
        merged.sort(key=rank)
        sp[:] = merged
        return {"groups_now": [str((g.get("m_groupTypeId") or {}).get("m_typeId"))
                               for g in sp],
                "n_groups": len(sp)}

    raw, rep = patch_record(b, 102, sf_rec["eid"], mutate)
    seqs = {seq: [r["raw"] for r in recs] for seq, recs in b.seq_records.items()}
    seqs[102] = [raw if r["eid"] == sf_rec["eid"] else r["raw"]
                 for r in b.seq_records[102]]
    outp = emit_probe("M3", F1, rebuild_last_unit(b, seqs))
    return {"probe": "M3", "file": relp(outp), "base": relp(G_ABPD),
            "source": relp(F1), "md5": md5_of(outp), "patch": rep,
            "axis": "ORDER-COUPLED STRUCTURE: famgen's order cell emits TWO "
                    "identityData groups (user params + built-ins split -- a "
                    "duplicate group key no PASS file carries); merged into "
                    "one and re-ranked dims < identity < electrical, param "
                    "id sets unchanged",
            "expected": "PASS convicts the duplicate-group-key order cell"}


def build_m4() -> Dict[str, Any]:
    """M4: F1 + the donor's sparse-registry counters."""
    b = UnitX(F1)
    identity_gate(b)
    a = UnitX(SUB_ALL)
    _sfa_rec, sfa = a.self_family()
    donor_next = sfa.get("m_nextAbsorbedIndex")
    donor_limit = sfa.get("m_predefinedLimitIdx")
    sf_rec, _sf = b.self_family()

    def mutate(val: Dict[str, Any]) -> Dict[str, Any]:
        was = {"m_nextAbsorbedIndex": val.get("m_nextAbsorbedIndex"),
               "m_predefinedLimitIdx": val.get("m_predefinedLimitIdx")}
        val["m_nextAbsorbedIndex"] = donor_next
        val["m_predefinedLimitIdx"] = donor_limit
        return {"was": was, "now": {"m_nextAbsorbedIndex": donor_next,
                                    "m_predefinedLimitIdx": donor_limit}}

    raw, rep = patch_record(b, 102, sf_rec["eid"], mutate)
    seqs = {seq: [r["raw"] for r in recs] for seq, recs in b.seq_records.items()}
    seqs[102] = [raw if r["eid"] == sf_rec["eid"] else r["raw"]
                 for r in b.seq_records[102]]
    outp = emit_probe("M4", F1, rebuild_last_unit(b, seqs))
    return {"probe": "M4", "file": relp(outp), "base": relp(G_ABPD),
            "source": relp(F1), "md5": md5_of(outp), "patch": rep,
            "axis": "FIELD residue: the self-Family absorbed/limit counters "
                    "set to the donor's sparse-history values (3165/1963 vs "
                    "our dense 42/35) -- every PASS file carries a gap, "
                    "every FAIL is gapless",
            "expected": "PASS convicts the dense-counter shape"}


def build_m5() -> Dict[str, Any]:
    """M5: F1 + m_partType -1 on BOTH mirrored surfaces (famdoc Family
    record in the unit AND the host-side Family record)."""
    b = UnitX(F1)
    identity_gate(b)
    sf_rec, _sf = b.self_family()

    def mutate(val: Dict[str, Any]) -> Dict[str, Any]:
        was = val.get("m_partType")
        val["m_partType"] = -1
        return {"m_partType": {"was": was, "now": -1}}

    raw, rep_doc = patch_record(b, 102, sf_rec["eid"], mutate)
    seqs = {seq: [r["raw"] for r in recs] for seq, recs in b.seq_records.items()}
    seqs[102] = [raw if r["eid"] == sf_rec["eid"] else r["raw"]
                 for r in b.seq_records[102]]
    logical1 = rebuild_last_unit(b, seqs)

    # host Family record: the seq-102 Family in an earlier unit whose
    # m_famDocGUID... simplest robust key: class Family, id > watermark of
    # the last unit start, m_partType == 14
    dec, _ = _codec()
    host_eid = None
    for blk in b.walker.blocks[:b.unit.first_block]:
        if blk.seq != 102:
            continue
        for rb in split_records(blk.data, 102):
            r = rec_fields(rb, 102)
            if r["cls"] == "Family":
                d = dec.decode_record(r["cid"], r["body"][2:])
                if not d.errors and d.value.get("m_partType") == 14:
                    host_eid = r["eid"]
    if host_eid is None:
        raise RuntimeError("M5: no host-side Family record with partType 14")
    # re-open a UnitX over the ALREADY-morphed logical to patch the host side
    u2 = UnitX.__new__(UnitX)
    u2.path = F1
    u2.part = PART
    u2.logical = logical1
    u2.walker = StreamWalker(logical1, inflate=True, keep_data=True)
    u2.unit = u2.walker.units[-1]
    u2.blocks = u2.walker.blocks[u2.unit.first_block:
                                 u2.unit.first_block + u2.unit.n_blocks]
    u2.seq_records = {}
    for blk in u2.blocks:
        recs = [rec_fields(rb, blk.seq) for rb in split_records(blk.data, blk.seq)]
        u2.seq_records.setdefault(blk.seq, []).extend(recs)
    logical2, rep_host = patch_host_record(u2, host_eid, mutate)
    outp = emit_probe("M5", F1, logical2)
    return {"probe": "M5", "file": relp(outp), "base": relp(G_ABPD),
            "source": relp(F1), "md5": md5_of(outp),
            "patch": {"famdoc": rep_doc, "host": rep_host},
            "axis": "FIELD residue: m_partType 14 (panelboard) -> -1 on the "
                    "mirrored pair (famdoc self-Family + host Family) -- "
                    "partType is the panel-schedule/MEP-part trigger; every "
                    "PASS famdoc carries -1, every FAIL carries 14",
            "expected": "PASS convicts partType-14-without-panel-infra"}


def build_m6() -> Dict[str, Any]:
    """M6: F1 + the donor's m_deletion convention (the family's category id
    prepended to the self-Family header deletion list)."""
    b = UnitX(F1)
    identity_gate(b)
    sf_rec, sf = b.self_family()
    cat = sf.get("m_categoryId")

    def mutate(val: Dict[str, Any]) -> Dict[str, Any]:
        par = ((val.get("m_parents") or {}).get("value") or {})
        dele = par.get("m_deletion")
        if not isinstance(dele, list):
            raise RuntimeError("no m_deletion list on the self-Family header")
        was = len(dele)
        if cat not in dele:
            dele.insert(0, cat)
        return {"m_deletion_len": {"was": was, "now": len(dele)},
                "prepended_category": cat}

    raw, rep = patch_record(b, 101, sf_rec["eid"], mutate)
    seqs = {seq: [r["raw"] for r in recs] for seq, recs in b.seq_records.items()}
    seqs[101] = [raw if r["eid"] == sf_rec["eid"] else r["raw"]
                 for r in b.seq_records[101]]
    outp = emit_probe("M6", F1, rebuild_last_unit(b, seqs))
    return {"probe": "M6", "file": relp(outp), "base": relp(G_ABPD),
            "source": relp(F1), "md5": md5_of(outp), "patch": rep,
            "axis": "FIELD residue: the donor's self-Family header "
                    "m_deletion list opens with non-element parents "
                    "(category id, subcategory, BIP); ours lists elements "
                    "only -- our category id (-2001040) prepended",
            "expected": "PASS convicts the deletion-parent convention"}


def build_bx_layout() -> Dict[str, Any]:
    """BX_layout_f1i1: the PORT proof -- the exact B0/BXhf_f1i1 recipe
    (famgen loader on G_ABPD under corpus_symbol_form, demo placement) with
    layout_law.normalize_doc applied between build_product and the load
    (the SUB_O1 injection point, the M1 order convention, monotone ids)."""
    sys.path.insert(0, HERE)
    import bisect_instance_bug as B
    import ifc_intent as T
    from rvt import famload_hostfix as HF
    from rvt.famgen import loader as L
    from rvt.famgen import layout_law as LL

    info: Dict[str, Any] = {
        "probe": "BX_layout_f1i1", "base": relp(G_ABPD),
        "recipe": "BXhf_f1i1/B0 (famgen loader on G_ABPD under "
                  "corpus_symbol_form, demo stage_equipment placement) with "
                  "layout_law.normalize_doc(order='donor_frame_first') "
                  "injected between build_product and the load"}
    chain_dir = os.path.join(BUILD_DIR, "BX_layout_chain")
    if os.path.isdir(chain_dir):
        shutil.rmtree(chain_dir)
    os.makedirs(chain_dir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "BX_layout_f1i1.rvt")
    with HF.corpus_symbol_form():
        model6 = B.demo_model()
        m1 = B.truncate_model(model6, 1)
        current = os.path.join(chain_dir, "stage_L0_base.rvt")
        shutil.copyfile(G_ABPD, current)
        wm = T.host_watermark(current)
        prod = T.build_product(m1.plan_for("PP-1"), start_id=wm + 1, solid=True)
        if not prod.doc.finalized:
            prod.doc.finalize()
        nrep = LL.normalize_doc(prod.doc, order="donor_frame_first")
        jdump(os.path.join(BUILD_DIR, "BX_layout_normalization.json"), nrep)
        info["normalization"] = {k: nrep[k] for k in
                                 ("n_elements", "n_moved", "class_order_before",
                                  "class_order_after")}
        nxt = os.path.join(chain_dir, "stage_L1_pp1.rvt")
        res = L.load_family_into_project(current, nxt, product=prod,
                                         place=False, symbol_solid=True,
                                         report_path=nxt + ".load.json",
                                         validate=False)
        if not res.ok:
            raise RuntimeError(f"BX_layout: famgen load failed: {res.stop_reason}")
        loaded = {"PP-1": {"symbol_id": res.plan.symbol_id,
                           "family_id": res.plan.host_family_id,
                           "content_guid": res.plan.guid,
                           "product": prod}}
        info["load"] = {"symbol_id": res.plan.symbol_id,
                        "family_id": res.plan.host_family_id,
                        "content_guid": res.plan.guid,
                        "host_watermark": wm}
        erec = B.place_instances(m1, nxt, outp, G_ABPD, loaded)
    insts = erec.get("instances") or []
    info["instance_ids"] = [i["elem_id"] for i in insts]
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    info["axis"] = ("PORT: the famgen product rebuilt with the layout-law "
                    "id-assignment normalization (self-Family, proj viewer/"
                    "view/drawing/viewport, units first -- the M1 order with "
                    "monotone ids, the shape SUB_ALL exhibits)")
    info["expected"] = ("tracks M1: PASS => the port authors the convention "
                        "end-to-end; FAIL alongside M1 FAIL closes the "
                        "order hypothesis")
    return info


# ===========================================================================
# gates + verify + stage
# ===========================================================================

def gate_probe_file(name: str, path: str, source: Optional[str]) -> Dict[str, Any]:
    """Per-probe machine gates: validator 0 errors, walker clean, added unit
    blob-carrying (64 B), every unit record decodes clean, refs resolve
    inside the unit, and (morphs) the only stream changed vs the source is
    Partitions/21."""
    from rvt.validate import validate_file
    dec, _ = _codec()
    rep: Dict[str, Any] = {"name": name, "file": relp(path), "md5": md5_of(path)}
    v = validate_file(path)
    rep["validator"] = {"verdict": "VALID" if not v.errors else "INVALID",
                        "n_errors": len(v.errors), "n_warnings": len(v.warnings),
                        "first_errors": [str(e)[:160] for e in v.errors[:3]]}
    u = UnitX(path)
    rep["walker_clean"] = not u.walker.errors
    rep["footer_blob_len"] = len(u.unit.footer_blob)
    rep["blob_carrying"] = len(u.unit.footer_blob) == 64
    ids = set(u.ids(102))
    decode_errs = 0
    unresolved: List[str] = []
    for seq in (101, 102, 103):
        for r in u.seq_records[seq]:
            if r["eid"] == -1 or r["cid"] is None:
                continue
            d = dec.decode_record(r["cid"], r["body"][2:])
            if d.errors:
                decode_errs += 1
    rep["unit_records_decode_clean"] = decode_errs == 0
    # coherence: inline adoc rows == unit ids
    try:
        _blob, aval = u.inline_adoc()
        et = ((aval.get("m_elemTable") or {}).get("value") or {})
        rows = {int(r.get("m_id", -1)) for r in et.get("m_elemArr") or []}
        rep["adoc_rows_equal_unit_ids"] = rows == ids
    except Exception as e:                                  # pragma: no cover
        rep["adoc_rows_equal_unit_ids"] = f"ERROR: {e}"
    if source and os.path.isfile(source):
        A, B = open_rvt(source), open_rvt(path)
        try:
            names = {s.name for s in A.streams()} & {s.name for s in B.streams()}
            changed = sorted(n for n in names if A.raw(n) != B.raw(n))
        finally:
            A.close()
            B.close()
        rep["streams_changed_vs_source"] = changed
        rep["single_stream_delta"] = changed == [PART]
    ok = (rep["validator"]["n_errors"] == 0 and rep["walker_clean"]
          and rep["blob_carrying"] and rep["unit_records_decode_clean"]
          and rep.get("adoc_rows_equal_unit_ids") is True
          and rep.get("single_stream_delta", True))
    rep["gates_ok"] = bool(ok)
    return rep


def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    os.makedirs(BUILD_DIR, exist_ok=True)
    builders = {"M1": build_m1, "M2": build_m2, "M3": build_m3,
                "M4": build_m4, "M5": build_m5, "M6": build_m6,
                "BX_layout_f1i1": build_bx_layout}
    todo = [n for n in MORPHS if not only or n in only]
    acct: Dict[str, Any] = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            "tool": "tools/layout_diff.py probes",
                            "probes": {}, "gates": {}}
    if os.path.isfile(ACCT):
        with open(ACCT) as fh:
            acct = json.load(fh)
        acct["generated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for n in todo:
        log(f"building {n} ...")
        info = builders[n]()
        acct.setdefault("probes", {})[n] = info
        src = os.path.join(ROOT, info.get("source", "")) if info.get("source") else None
        g = gate_probe_file(n, os.path.join(OUT_DIR, f"{n}.rvt"), src)
        acct.setdefault("gates", {})[n] = g
        log(f"  {n}: gates_ok={g['gates_ok']} validator_errors="
            f"{g['validator']['n_errors']} blob={g['footer_blob_len']}")
    jdump(ACCT, acct)
    write_probes_json(acct)
    return acct


def verify() -> Dict[str, Any]:
    with open(ACCT) as fh:
        acct = json.load(fh)
    for n, info in acct.get("probes", {}).items():
        p = os.path.join(OUT_DIR, f"{n}.rvt")
        src = os.path.join(ROOT, info.get("source", "")) if info.get("source") else None
        g = gate_probe_file(n, p, src)
        acct["gates"][n] = g
        got = md5_of(p)
        if got != info["md5"]:
            raise RuntimeError(f"{n}: file drifted since build "
                               f"({got} vs {info['md5']})")
        log(f"verify {n}: gates_ok={g['gates_ok']}")
    jdump(ACCT, acct)
    write_probes_json(acct)
    return acct


def write_probes_json(acct: Dict[str, Any]) -> str:
    out = {
        "stream": "layout-law: THE MORPH ROUND on the SUB_ALL/F1 matched "
                  "pair (verdict #40).  layout_diff.json measured the pair: "
                  "NOT field-equal -- the self-Family kept-ours residue "
                  "separates the corpus perfectly while every order "
                  "predicate is already exonerated by SUB_O1 (donor order, "
                  "FAIL) x B7 (donor order, PASS).  M1/M2 test order "
                  "DIRECTLY by pure byte transplant; M3..M6 split the "
                  "residue one field-axis at a time; BX_layout_f1i1 proves "
                  "the layout_law port end-to-end.",
        "bases": {"rst": relp(RST), "g_abpd": relp(G_ABPD)},
        "note": "M1/M3..M6 = byte surgery on the STAGED F1 (base G_ABPD); "
                "M2 = byte surgery on the STAGED SUB_ALL (base rst); every "
                "surgery is identity-gated (no-edit re-emission byte-exact) "
                "and roundtrip-gated (encode(decode(x)) == x before the "
                "patch).  BX_layout_f1i1 = the B0 recipe through "
                "src/rvt/famgen/layout_law.py.  Every added unit carries "
                "the 64-byte 0x0f3f blob (machine-verified).  PROOF-ONLY "
                "sample-derived content, quarantined, never shipped.",
        "upload_order_max_information_first": [
            "M1", "BX_layout_f1i1", "M2", "M3", "M5", "M4", "M6"],
        "controls": {
            "rst": {"source": relp(RST), "voids": "M2 on CTRL FAIL"},
            "g_abpd": {"source": relp(G_ABPD),
                       "voids": "M1/M3..M6/BX_layout_f1i1 on CTRL FAIL"}},
        "reading_the_matrix": {
            "CTRL FAIL (either)": "that base's probes are VOID.",
            "M1 PASS": "record order IS audited: the pure order transplant "
                       "saves F1.  Contradicts the SUB_O1xB7 corpus "
                       "exoneration -- re-read SUB_O1's permutation before "
                       "porting.  BX_layout_f1i1 should PASS with it; the "
                       "layout_law port ships and DEMO v6 goes through it.",
            "M1 FAIL + M2 PASS": "order fully exonerated both directions "
                                 "(expected per the corpus): the law is in "
                                 "the FIELD residue -- read M3..M6.",
            "M2 FAIL": "SUB_ALL's content stops passing when re-ordered: "
                       "order is (at least part of) the law even though "
                       "SUB_O1's donor-convention order failed -- the "
                       "lawful order would be SUB_ALL's exact artifact "
                       "shape, not the donor's native shape; port M1's "
                       "convention.",
            "M3 PASS": "the duplicate identityData group key in famgen's "
                       "order cell is the defect: fix "
                       "skeleton.finalize to merge built-ins into one "
                       "group; v6 through the fix.",
            "M4 PASS": "the dense absorbed/limit counters are the defect "
                       "(audit expects an edit-history gap).",
            "M5 PASS": "partType 14 without panel-schedule infrastructure "
                       "is the defect: famgen either authors the infra or "
                       "ships partType -1.",
            "M6 PASS": "the deletion-parent convention (category id in "
                       "m_deletion) is the defect.",
            "ALL M FAIL": "the residue is a conjunction or lives in the "
                          "untransplanted fields (m_categoryId itself, the "
                          "type-table shape, the familyParams BIP row) -- "
                          "next round builds the category probe through "
                          "famgen (generic_model category, full-chain "
                          "coherence) rather than byte surgery.",
        },
        "probes": {},
    }
    for n, info in acct.get("probes", {}).items():
        e = dict(info)
        e["gates"] = acct.get("gates", {}).get(n, {})
        out["probes"][n] = e
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, out)
    log(f"probes.json written ({len(out['probes'])} probes)")
    return path


def stage() -> Dict[str, Any]:
    """probe_batch gate + stage with TWO controls (byte-identical rst copy
    for M2 + a G_ABPD copy for the F1 morphs + BX)."""
    pb = _pb()
    import datetime as _dt
    with open(ACCT) as fh:
        acct = json.load(fh)
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in MORPHS]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run build): {[relp(m) for m in missing]}")
    bad = [n for n in MORPHS
           if not (acct.get("gates") or {}).get(n, {}).get("gates_ok")]
    if bad:
        raise SystemExit(f"gates not green for {bad} -- stage refused")
    if not os.path.isfile(DIFF_JSON):
        raise SystemExit("layout_diff.json missing -- run enumerate first")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    # batch number: continue the acceptance folder's sequence
    n = pb.next_batch_number()
    out_dir = pb.ACCEPTANCE
    ctrl_rst = pb.make_control(ledger, n, out_dir, source=RST)
    ctrl_g = pb.make_control(ledger, n, out_dir, source=G_ABPD)
    ordered = [ctrl_rst, ctrl_g] + [e for e in entries if e.kind == "probe"]
    for i, e in enumerate(ordered):
        e.order = i
        if e.kind == "control":
            continue
        src = pb.abspath(e.file)
        dst = os.path.join(out_dir, os.path.basename(e.file))
        if os.path.abspath(src) != os.path.abspath(dst):
            if os.path.exists(dst) and md5_of(dst) != e.md5:
                raise pb.GateRefusal(
                    [f"{e.file}: a DIFFERENT file already sits at "
                     f"{pb.rel(dst)}; rename the probe -- never overwrite a "
                     f"staged file the viewer may already have read"])
            shutil.copyfile(src, dst)
        e.staged_as = pb.rel(dst)
    manifest = {
        "batch": n,
        "created": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": "tools/layout_diff.py (via tools/probe_batch.py primitives)",
        "law": ("every entry's declared base is ITSELF viewer-certified (or "
                "an Autodesk sample source); >= 1 byte-identical CONTROL per "
                "base; control FAIL voids that base's probes"),
        "ledger": pb.rel(ledger.path),
        "control_count": 2,
        "controls": {"rst": ctrl_rst.staged_as, "g_abpd": ctrl_g.staged_as,
                     "note": "the rst control gates M2; the G_ABPD control "
                             "gates M1/M3..M6/BX_layout_f1i1"},
        "note": "layout-law: the MORPH ROUND on the SUB_ALL/F1 matched pair "
                "(verdict #40).  M1/M2 = pure record-order transplants "
                "(content byte-multiset-equal, machine-proven); M3..M6 = "
                "one self-Family residue field-axis each; BX_layout_f1i1 = "
                "the layout_law port through the B0 recipe.  Read "
                "experiments/layout/probes.json reading_the_matrix; the "
                "measured diff + ranking is experiments/layout/"
                "layout_diff.json.",
        "reading_order": [os.path.basename(e.staged_as or e.file)
                          for e in ordered],
        "entries": [e.to_json() for e in ordered],
    }
    path = os.path.join(out_dir, f"batch_{n}.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    manifest["manifest_path"] = pb.rel(path)
    log(f"STAGED batch {n} -> {manifest['manifest_path']}")
    for e in ordered:
        log(f"  [{e.order}] {e.staged_as} ({e.kind})")
    for e in ordered:
        got = md5_of(os.path.join(ROOT, e.staged_as))
        if got != e.md5:
            raise RuntimeError(f"staged copy md5 mismatch: {e.staged_as}")
    log("staged copies md5-verified")
    return manifest


# ===========================================================================
# main
# ===========================================================================

def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    if cmd == "enumerate":
        enumerate_diff()
        return 0
    if cmd == "probes":
        build(rest or None)
        return 0
    if cmd == "verify":
        verify()
        return 0
    if cmd == "stage":
        stage()
        return 0
    print(f"unknown command {cmd!r}; use enumerate | probes [names] | "
          f"verify | stage")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
