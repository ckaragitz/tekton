"""reduce.py — DELETE elements from a .rvt and re-emit it (genesis research).

The inverse of ``commit.commit_new_elements``: instead of splicing records IN,
this cuts records OUT.  Deleting element ``E`` from the host document means:

  1. remove E's records from all three parallel record streams (seq 101 /
     102 / 103) of save-unit 0 of ``Partitions/<N>``;
  2. remove E's 40-byte ElemRec from ``Global/ElemTable`` (count drops; the
     id watermark ``IdentifierSource.m_last`` in the footer is NOT lowered —
     Revit never re-issues ids);
  3. patch the partition stream header's ``elem_table_count`` to match;
  4. re-frame both streams with real CRCIO ECC and rebuild the container.

Because deleted records can sit anywhere (and may span blocks), unit 0 is
RE-BLOCKED from scratch: for each seq the surviving records are concatenated
in their original order and re-chunked into ~128 KiB gzip blocks using the
same rules Autodesk's writer uses (whole records packed <= 131,072 payload
bytes; a record too large for one block is body-chunked at 131,072 with the
6/7/5 continuation flags; the per-seq sentinel record stays LAST).  Blocks
group by seq (all 101, then 102, then 103) exactly as in the samples.
Embedded family/content documents (save units 1..k) and every byte from
unit 0's terminator/footer onward are copied VERBATIM.

Save-history streams (History / DocumentIncrementTable / BasicFileInfo /
Contents) and Global/Latest are deliberately NOT modified — this is the same
"minimal commit" convention proven acceptable by commit.py (the History
invariant count == max(modified_ep)+1 is preserved as long as the element
carrying the maximum modified episode survives; ``analyze_deletion`` warns).

References are the real danger: nothing here rewrites survivors, so any
survivor (or Global/Latest / ContentDocuments, which we do not edit) that
holds a deleted ElementId is left DANGLING.  ``reference_graph`` +
``analyze_deletion`` measure that; ``closure_delete`` grows a seed set until
no partition-record survivor references a deleted id.  Whether Autodesk's
reader tolerates the dangling references that remain in Global/Latest is the
open empirical question this module exists to answer.

Territory: this module is READ-only over the rest of the writer stack; it
does not modify mutate.py / commit.py / partitions.py behaviour.
"""
from __future__ import annotations

import dataclasses
import struct
import zlib
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import ecc
from . import partitions as _P
from .cfb_writer import write_cfb
from .container import open_rvt
from .objects import iter_records
from .partitions import StreamWalker
from .roundtrip import read_entries
from .stream_encoders import decode_elemtable, encode_elemtable, global_prefix
from .writer import gzip_member

# --- framing constants ------------------------------------------------------
# (block header/trailer tags: read from rvt.partitions at CALL time -- #467)
SEQS = (101, 102, 103)
#: uncompressed payload target per block; Autodesk's writer packs whole
#: records up to 131,072 (0x20000) and body-chunks bigger records at 131,072
BLOCK_TARGET = 131072
PART_HDR_LEN = 18                 # Partitions/<N> stream header
PART_HDR_COUNT_OFF = 14           # u32 elem_table_count inside it
#: ISIZE identity  ISIZE == rec_hdr_len(seq)*A + C + adj(flags)
_ISIZE_ADJ = {4: 0, 5: 4, 6: -4, 7: 0}


def _raw_hdr_len(seq: int) -> int:
    """Bytes of a record header BEFORE the body: id(8)[+stamp(4)]+psize(4)."""
    return 12 if seq == 101 else 16


def _rec_hdr_len(seq: int) -> int:
    """Header length used by the A/C/ISIZE identity (raw header + u32 repeat)."""
    return _raw_hdr_len(seq) + 4


# ---------------------------------------------------------------------------
# record extraction
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Rec:
    seq: int
    elem_id: int
    size: int          # body size (psize)
    data: bytes        # the full framed record: header + body + u32 repeat

    @property
    def is_sentinel(self) -> bool:
        return self.elem_id == -1 and self.size == 0


def split_records(segment: bytes, seq: int) -> List[Rec]:
    """Split a concatenated per-seq segment into framed records (lossless).

    Every record occupies exactly ``rawhdr + size + 4`` bytes and the next
    record starts immediately after; the walk must consume the whole segment
    up to (and including) the sentinel or we refuse (we never silently drop
    bytes we don't understand).
    """
    out: List[Rec] = []
    hl = _raw_hdr_len(seq)
    p = 0
    n = len(segment)
    for r in iter_records(segment, seq):
        span = hl + r.body_size + 4
        if r.seg_offset != p:
            raise ValueError(f"seq {seq}: record walk gap at {r.seg_offset} (expected {p})")
        out.append(Rec(seq, r.elem_id, r.body_size, segment[p:p + span]))
        p += span
    if p != n:
        # trailing bytes after the last parsed record -> not understood
        raise ValueError(f"seq {seq}: record walk covered {p} of {n} segment bytes")
    if not out or not out[-1].is_sentinel:
        raise ValueError(f"seq {seq}: segment does not end with the sentinel record")
    return out


# ---------------------------------------------------------------------------
# re-blocking (the writer side)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class NewBlock:
    seq: int
    flags: int
    A: int             # record headers that START in this block
    C: int             # record body bytes stored in this block
    payload: bytes     # uncompressed block payload

    def frame(self, level: int = 3) -> bytes:
        gz = gzip_member(self.payload, level=level, sync_flush=True)
        B = 8 + len(gz)
        hdr = struct.pack("<HIIIIII", _P.BLOCK_TAG, self.flags, self.A, B, self.C,
                          self.seq, 0)
        return hdr + gz + struct.pack("<HI", _P.TRAILER_TAG, B)

    @property
    def isize_ok(self) -> bool:
        return len(self.payload) == _rec_hdr_len(self.seq) * self.A + self.C + _ISIZE_ADJ[self.flags]


def reblock(records: Sequence[Rec], seq: int,
            target: int = BLOCK_TARGET) -> List[NewBlock]:
    """Pack records into blocks the way Autodesk's writer does.

    * whole records greedily while the block payload stays <= ``target``
      (flags 4);
    * a record whose framed length exceeds ``target`` starts a FRESH block and
      is body-chunked: first block = header + first ``target`` body bytes
      (flags 6, A=1), continuation blocks of ``target`` body bytes (flags 7,
      A=0), final block = remaining body + the u32 size-repeat (flags 5, A=0).
      (Byte-exact match to the three spanning chains in rstbasic.)
    """
    blocks: List[NewBlock] = []
    hl = _raw_hdr_len(seq)
    cur_payload = bytearray()
    cur_A = 0
    cur_C = 0

    def flush() -> None:
        nonlocal cur_payload, cur_A, cur_C
        if cur_payload:
            blocks.append(NewBlock(seq, 4, cur_A, cur_C, bytes(cur_payload)))
        cur_payload = bytearray()
        cur_A = 0
        cur_C = 0

    for rec in records:
        n = len(rec.data)
        if n <= target:
            if len(cur_payload) + n > target:
                flush()
            cur_payload += rec.data
            cur_A += 1
            cur_C += rec.size
            continue
        # -- spanning record ---------------------------------------------------
        flush()
        body = rec.data[hl:hl + rec.size]      # excludes header and the u32 repeat
        # first block: header + first `target` body bytes
        take = min(target, len(body) - 4)       # leave >=4 body bytes for the tail
        first = rec.data[:hl] + body[:take]
        blocks.append(NewBlock(seq, 6, 1, take, first))
        pos = take
        while len(body) - pos > target:
            chunk = body[pos:pos + target]
            blocks.append(NewBlock(seq, 7, 0, len(chunk), chunk))
            pos += target
        tail = body[pos:] + rec.data[hl + rec.size:]   # remaining body + u32 repeat
        blocks.append(NewBlock(seq, 5, 0, len(body) - pos, tail))
    flush()
    for b in blocks:
        if not b.isize_ok:
            raise AssertionError(f"seq {seq}: ISIZE identity violated by rebuilt block "
                                 f"(flags={b.flags} A={b.A} C={b.C} len={len(b.payload)})")
    return blocks


# ---------------------------------------------------------------------------
# the delete operation
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ReduceReport:
    partition: str
    deleted: int
    elemtable_count_before: int
    elemtable_count_after: int
    watermark: int
    records_removed: Dict[int, int]
    blocks_before: int
    blocks_after: int
    logical_before: int
    logical_after: int
    out_path: str

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def delete_elements(src_rvt: str, out_path: str, delete_ids: Iterable[int], *,
                    target: int = BLOCK_TARGET) -> ReduceReport:
    """Remove ``delete_ids`` from the host document of ``src_rvt`` -> ``out_path``.

    Ids that are not in the host ElemTable are ignored (they may still hit
    unit-0 records; both filters key on the id set).  Embedded documents
    (save units 1..k) are copied byte-for-byte and never inspected.
    """
    delete = {int(i) for i in delete_ids}
    entries = read_entries(src_rvt)
    new_streams: Dict[str, bytes] = {}
    with open_rvt(src_rvt) as doc:
        parts = doc.partition_streams()
        if len(parts) != 1:
            raise NotImplementedError(f"expected one partition stream, got {parts}")
        pname = parts[0]

        # ---------------- 1. ElemTable ------------------------------------
        model = decode_elemtable(doc.inflate("Global/ElemTable"))
        count_before = len(model["records"])
        model["records"] = [r for r in model["records"] if r[4] not in delete]
        count_after = len(model["records"])
        watermark = model["footer"]["last_id"]
        et_logical = global_prefix("Global/ElemTable") + gzip_member(
            encode_elemtable(model), level=3)
        new_streams["Global/ElemTable"] = ecc.frame_stream(et_logical)

        # ---------------- 2. Partitions/<N> --------------------------------
        logical = doc.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"walker errors on source: {w.errors[:3]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        u0 = [b for b in blocks if b.unit == 0]
        if not u0 or blocks[0].hdr_offset != PART_HDR_LEN:
            raise RuntimeError("unexpected unit-0 layout (first block not at offset 18)")
        u0_end = w.units[0].footer_offset      # unit-0 terminator/footer starts here
        if u0_end is None:
            raise RuntimeError("unit 0 has no footer")

        removed: Dict[int, int] = {}
        new_u0 = bytearray()
        for seq in SEQS:
            seg = b"".join(b.data for b in u0 if b.seq == seq)
            if not seg:
                raise RuntimeError(f"unit 0 has no seq-{seq} data")
            recs = split_records(seg, seq)
            keep = [r for r in recs if r.is_sentinel or r.elem_id not in delete]
            removed[seq] = len(recs) - len(keep)
            for nb in reblock(keep, seq, target=target):
                new_u0 += nb.frame()

        out = bytearray(logical[:PART_HDR_LEN]) + new_u0 + logical[u0_end:]
        struct.pack_into("<I", out, PART_HDR_COUNT_OFF, count_after)
        w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
        if w2.errors:
            raise RuntimeError(f"walker errors after re-block: {w2.errors[:3]}")
        part_logical = bytes(out[:w2.end_offset + len(w2.end_record)])
        new_streams[pname] = ecc.frame_stream(part_logical)

    # ---------------- 3. write ------------------------------------------------
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out_path, out_entries)
    return ReduceReport(pname, len(delete), count_before, count_after, watermark,
                        removed, len(u0), sum(1 for b in w2.blocks if b.unit == 0),
                        len(logical), len(part_logical), out_path)


# ---------------------------------------------------------------------------
# structural verification (the self-check gate for every staged reduction)
# ---------------------------------------------------------------------------

# The last-block law this stream found first (R1s: a 64,875-byte final block)
# now lives in the codec (``ecc.iter_blocks``, #236); the name stays for callers.
unframe_exact = ecc.unframe_stream

def verify_reduced(path: str, deleted_ids: Iterable[int] = ()) -> dict:
    """Prove a reduced file is structurally healthy.

    Checks: every gzip member CRC-verifies; every full-page ECC trailer of
    the partition + ElemTable streams matches ``ecc.page_trailer``; the
    partition walker reports zero errors; ElemTable count == partition header
    count; each unit-0 seq segment walks losslessly and ENDS with the
    sentinel; the three unit-0 seqs carry IDENTICAL id sets; every seq-102/103
    record stamp == adler32(class+body); no deleted id survives anywhere in
    unit 0 or the ElemTable; every ElemTable id has a seq-102 record.
    """
    deleted = {int(i) for i in deleted_ids}
    rep: dict = {"path": path, "crc_failures": 0, "ecc_mismatches": 0,
                 "walker_errors": [], "elemtable_count": None,
                 "header_count": None, "counts_match": None,
                 "sentinel_last": {}, "segment_walks": {},
                 "seq_id_sets_equal": None, "stamps_bad": 0,
                 "deleted_still_present": [], "elemtable_ids_without_record": 0,
                 "units": None, "blocks_unit0": None, "ok": False}
    with open_rvt(path) as d:
        pname = d.partition_streams()[0]
        rep["crc_failures"] = sum(0 if m.crc_ok else 1
                                   for s in d.streams() for m in d.members(s.name))
        for name in (pname, "Global/ElemTable"):
            # full round-trip proof: every full page's trailer AND the final
            # block (decoded by its pad-count field) must re-encode exactly
            rep["ecc_mismatches"] += ecc.framing_mismatches(d.raw(name))
        model = decode_elemtable(d.inflate("Global/ElemTable"))
        et_ids = {r[4] for r in model["records"]}
        rep["elemtable_count"] = len(model["records"])
        logical = d.logical(pname)
        rep["header_count"] = struct.unpack_from("<I", logical, PART_HDR_COUNT_OFF)[0]
        rep["counts_match"] = (rep["header_count"] == rep["elemtable_count"])
        w = StreamWalker(logical, inflate=True, keep_data=True)
        rep["walker_errors"] = w.errors
        rep["units"] = len(w.units)
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        rep["blocks_unit0"] = len(u0)
        rep["isize_identity_ok"] = all(len(b.data) == b.intended_len for b in u0)
        ids_by_seq: Dict[int, Set[int]] = {}
        for seq in SEQS:
            seg = b"".join(b.data for b in u0 if b.seq == seq)
            ids: Set[int] = set()
            walk_ok = True
            last_sentinel = False
            try:
                recs = split_records(seg, seq)
                last_sentinel = recs[-1].is_sentinel
                for r in recs:
                    if r.is_sentinel:
                        continue
                    ids.add(r.elem_id)
                    if seq != 101 and r.size >= 2:
                        stamp = struct.unpack_from("<I", r.data, 8)[0]
                        body = r.data[16:16 + r.size]
                        if (zlib.adler32(body) & 0xFFFFFFFF) != stamp:
                            rep["stamps_bad"] += 1
            except ValueError as e:
                walk_ok = False
                rep["walker_errors"].append(f"seq{seq}: {e}")
            rep["segment_walks"][seq] = walk_ok
            rep["sentinel_last"][seq] = last_sentinel
            ids_by_seq[seq] = ids
        rep["seq_id_sets_equal"] = (ids_by_seq[101] == ids_by_seq[102] == ids_by_seq[103])
        alive = ids_by_seq[102]
        rep["deleted_still_present"] = sorted((deleted & alive) | (deleted & et_ids))[:20]
        rep["elemtable_ids_without_record"] = len(et_ids - alive)
        rep["unit0_element_records"] = len(alive)
    rep["ok"] = (rep["crc_failures"] == 0 and rep["ecc_mismatches"] == 0
                 and not rep["walker_errors"] and rep["counts_match"]
                 and all(rep["sentinel_last"].values())
                 and all(rep["segment_walks"].values())
                 and rep["seq_id_sets_equal"] and rep["stamps_bad"] == 0
                 and not rep["deleted_still_present"]
                 and rep["elemtable_ids_without_record"] == 0
                 and rep["isize_identity_ok"])
    return rep


# ---------------------------------------------------------------------------
# reference analysis (what a deletion breaks)
# ---------------------------------------------------------------------------

def reference_graph(doc, host_ids: Optional[Set[int]] = None) -> Dict[int, Set[int]]:
    """Forward reference graph over host-document elements.

    ``graph[e]`` = set of host element ids referenced by e's decoded records
    (seq 101 header + seq 102 object + seq 103 rep), via the same
    ``mutate._collect_ids`` heuristic the creation path validates with.
    ``doc`` is a ``rvt.mutate.Document``.
    """
    from .mutate import _collect_ids
    host = set(doc.et_by_id) if host_ids is None else set(host_ids)
    graph: Dict[int, Set[int]] = {}
    for eid in host:
        refs: List[Tuple[str, int]] = []
        for seq in SEQS:
            o = doc.decode(eid, seq)
            if o is not None:
                _collect_ids(o.value, refs)
        graph[eid] = {i for _p, i in refs if i in host and i != eid}
    return graph


def scan_stream_ids(payload: bytes, valid: Set[int]) -> Set[int]:
    """Every host ElementId that appears as a little-endian i64 anywhere in
    ``payload`` (heuristic scan of an un-decoded stream such as
    Global/Latest / ContentDocuments).  Small ids (< 4096) are ignored to
    keep the false-positive rate negligible.
    """
    found: Set[int] = set()
    lo, hi = 4096, max(valid) if valid else 0
    n = len(payload)
    for off in range(0, n - 7):
        v = struct.unpack_from("<q", payload, off)[0]
        if lo <= v <= hi and v in valid:
            found.add(v)
    return found


def closure_delete(graph: Dict[int, Set[int]], seed: Iterable[int],
                   protected: Set[int] = frozenset()) -> Set[int]:
    """Grow ``seed`` until no SURVIVOR references a deleted element.

    Any survivor that references a to-be-deleted id is itself deleted, unless
    it is ``protected`` (then it keeps a dangling reference — reported by
    ``analyze_deletion``).  Terminates because the set only grows.
    """
    delete = set(seed) - set(protected)
    # invert: who references x?
    referrers: Dict[int, Set[int]] = defaultdict(set)
    for e, refs in graph.items():
        for r in refs:
            referrers[r].add(e)
    frontier = set(delete)
    while frontier:
        nxt: Set[int] = set()
        for x in frontier:
            for src in referrers.get(x, ()):
                if src in delete or src in protected:
                    continue
                delete.add(src)
                nxt.add(src)
        frontier = nxt
    return delete


def analyze_deletion(doc, graph: Dict[int, Set[int]], delete: Set[int],
                     external_refs: Optional[Dict[str, Set[int]]] = None) -> dict:
    """Report what a deletion leaves dangling.

    ``external_refs``: {stream_name: set(host ids referenced by that stream)}
    for streams we do not rewrite (Global/Latest, ContentDocuments).
    """
    delete = set(delete)
    survivors_dangling: Dict[int, Set[int]] = {}
    for e, refs in graph.items():
        if e in delete:
            continue
        bad = refs & delete
        if bad:
            survivors_dangling[e] = bad
    by_class = Counter(doc.class_of(e) or "?" for e in survivors_dangling)
    del_by_class = Counter(doc.class_of(e) or "?" for e in delete)
    ext = {}
    for name, ids in (external_refs or {}).items():
        hit = ids & delete
        ext[name] = {"dangling": len(hit),
                     "by_class": Counter(doc.class_of(i) or "?" for i in hit).most_common(12)}
    max_ep_id = max(doc.et_by_id.values(), key=lambda r: r.modified_ep).id \
        if doc.et_by_id else None
    return {
        "deleted": len(delete),
        "deleted_by_class": del_by_class.most_common(40),
        "surviving_elements": len(graph) - sum(1 for e in graph if e in delete),
        "survivors_with_dangling_refs": len(survivors_dangling),
        "dangling_by_survivor_class": by_class.most_common(30),
        "external": ext,
        "history_invariant_at_risk": (max_ep_id in delete) if max_ep_id is not None else False,
    }


__all__ = ["delete_elements", "verify_reduced", "reference_graph",
           "scan_stream_ids", "closure_delete", "analyze_deletion",
           "split_records", "reblock", "ReduceReport"]
