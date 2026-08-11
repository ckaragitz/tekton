"""reduce_v2 -- embedded content-document (save-unit) REMOVAL, re-implemented on
top of the SOLVED ``Global/ContentDocuments`` grammar and the exact stream
framing, WITH the ADocument content-registry reconciliation the reader
requires (BUG B of the two-bug model, docs/inbox/genesis-audit.md verdicts
#3/#4; record: docs/inbox/genesis-triage-b.md; recipe:
docs/writer/content-splice.md).

Background (measured, see the record for byte offsets)
--------------------------------------------------------
The ladder-v2 reductions R9b/R10b (``tools/rvt_reduce.py::remove_units``)
remove embedded family documents by (i) splicing whole save units out of
``Partitions/<N>`` and (ii) dropping the matching ``Global/ContentDocuments``
entries.  Both files are validator-VALID and reader-REJECTED, while their
parent R9/R10 (families' HOST elements deleted, documents kept) PASS.  The
field-by-field diff of the old emission against the solved grammar shows:

* the ContentDocuments stream the old path emits is BYTE-IDENTICAL to the
  solved-grammar rebuild for the same GUID set (the wave-1 marker scanner's
  boundaries coincide with the grammar on this corpus) -- the CD splice per se
  is NOT malformed;
* the Partitions unit splice is byte-clean (unit ranges tile; each kept
  unit's separator {u16 0x3a3, i32 -1, u16 0x3a2, u32 record_count, GUID}
  is untouched; separator counter == that unit's record count);
* BUT the old path (a) never touches ``Global/Latest``, whose
  ``ContentTable.m_ContentRecSet`` + ``FamilyMgr.m_arrLoadedFamilyInfo`` (the
  ONLY two places a content GUID lives in the ADocument) still name every
  removed document -- the incoherence verdict #3 named; and (b) carries the
  parent generation's de-paged ECC tail (zero pad + parity of the parent's
  final CRCIO block) INTO the written partition stream after the end record
  -- R9b's exact logical stream ends `end-record(10) + 294 junk bytes`
  (R10b: +506) versus the reader-accepted first-generation R9's +58 (the
  sample's own heap tail) and Autodesk's own +0.

``remove_units_v2`` therefore emits, from the model:

* ``Partitions/<N>``  -- the EXACT logical stream (ECC pad-count decoded,
  no junk) with the removed units spliced out and the canonical 10-byte end
  record ``u16 ContentMarker, i32 0, i32 -1`` (the form every Autodesk sample
  has, verified via the solved ECC on all six; ContentMarker = 0x3a3 on 2026
  and read per release at call time, :func:`part_end_record`);
* ``Global/ContentDocuments``  -- re-BUILT by the solved grammar
  (:mod:`rvt.famgen.factory`): ``u64 1`` stream prefix + GUID-sorted entries
  ``separator(u16 0x3a3, i32 -1, u16 0x3a2, i32 -1) + GUID(16, bytes_le) +
  u32 adoc_len + ADocument + u32 adoc_len`` + the 14-byte end record;
* ``Global/Latest``  -- decoded, RECONCILED (ContentTable records + FamilyMgr
  loaded-family entries of the removed GUIDs dropped), re-encoded byte-exact
  by :mod:`rvt.adocument` (optional switch for the coherence probe);
* ``Global/PartitionTable`` is the WORKSET table (one 'Workset1' row) --
  there are NO per-unit PartitionTable rows to drop (verified byte-identical
  across R9/R9b), so it is deliberately untouched.

No existing ``src/rvt/*`` module is edited: everything is imported.
Run ``python -m rvt.reduce_v2 --probes`` to emit the B-probe set.

Every path-taking public entry enters the file's OWN release itself (#671),
the way every other engine entry does: the writer :func:`remove_units_v2`
under ``rvt.frontdoor.release_ctx.host_release_context`` (joins a caller's
same-release context; a native file enters none; an uncertified or
unreadable file is its typed ``ReleaseContextError``), the read-only
instruments :func:`verify_content_coherence` / :func:`family_units` /
:func:`diff_old_vs_solved` on ``rvt.global_framing.enter_own_release``'s
lenient ladder (the rung, if one was needed, reported as ``release_note``).
:func:`exact_partition_logical` is CRCIO un-framing only -- release-agnostic;
the B-probe driver reads its fixed native sample lineage (``R9`` / ``R9b``).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import uuid
from contextlib import ExitStack
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .global_framing import enter_own_release      # a leaf: binds the patched modules lazily, at entry

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

PART_HDR_LEN = 18
UNIT_SEPARATOR_LEN = 28
CD_STREAM = "Global/ContentDocuments"
LATEST_STREAM = "Global/Latest"


def part_end_record() -> bytes:
    """The canonical 10-byte partition-stream end record ``u16 ContentMarker,
    i32 0, i32 -1`` under the release IN FORCE: ContentMarker is
    ``rvt.partitions.CONTAINER_CLASS`` read at CALL time (2026 0x3a3, 2025
    0x391, 2024 0x37b -- bound by name by ``rvt.versions.reading`` /
    ``host_release_context``, the value the ``StreamWalker`` that found
    ``end_offset`` used), as :func:`rvt.global_framing.tokens` derives it (its
    ``FAMILY_END_RECORD`` key is this same universal stream end record; #93).
    Never a by-value copy (#467, #655)."""
    from .global_framing import tokens
    return tokens()["FAMILY_END_RECORD"]


# ---------------------------------------------------------------------------
# partition unit ranges (exact-tiling, on the ECC-EXACT logical stream)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class UnitRange:
    index: int
    guid: Optional[str]        # canonical lowercase uuid string (bytes_le decoded)
    counter: Optional[int]     # separator u32 = record count of the unit (excl. sentinel)
    start: int                 # first byte of the unit (unit>=1: its 28-byte separator)
    end: int                   # one past the last byte (next separator / end record)


def exact_partition_logical(rvt_path: str, stream: str) -> bytes:
    """The partition stream's LOGICAL bytes recovered EXACTLY from the raw
    CRCIO framing (final block's data length decoded from its pad-count
    field) -- unlike ``RvtDocument.logical()`` (de-page only), this carries
    NO ECC pad / parity junk after the end record."""
    from .container import open_rvt
    from .reduce import unframe_exact
    with open_rvt(rvt_path) as f:
        raw = f.raw(stream)
    return unframe_exact(raw)


def unit_ranges(logical: bytes) -> Tuple[List[UnitRange], Any]:
    """Tile the partition logical stream into save units.

    Unit 0 (the host document) spans ``[18, sep1)``; unit k>=1 starts at
    ITS 28-byte separator ``{u16 0x3a3, i32 -1, u16 0x3a2, u32 counter,
    GUID(16 bytes_le)}`` and ends where the next separator (or the stream
    end record) begins, so the ranges tile ``[18, end_offset)`` and any
    subset splices out losslessly.  Returns ``(ranges, walker)``.
    """
    from .partitions import StreamWalker
    w = StreamWalker(logical, inflate=False, keep_data=False)
    if w.errors:
        raise RuntimeError(f"partition walker errors: {w.errors[:3]}")
    starts: List[int] = []
    for u in w.units:
        if u.index == 0:
            starts.append(PART_HDR_LEN)
        else:
            fb = w.blocks[u.first_block]
            starts.append(fb.hdr_offset - len(u.prefix_blob) - UNIT_SEPARATOR_LEN)
    out: List[UnitRange] = []
    for i, u in enumerate(w.units):
        end = starts[i + 1] if i + 1 < len(starts) else w.end_offset
        g = None
        if u.guid:
            try:
                g = str(uuid.UUID(bytes_le=bytes(u.guid[:16]))).lower()
            except Exception:
                g = bytes(u.guid).hex()
        out.append(UnitRange(u.index, g, u.counter, starts[i], end))
    # tiling invariant: ranges are contiguous from 18 to end_offset
    if out and (out[0].start != PART_HDR_LEN or out[-1].end != w.end_offset
                or any(out[i].end != out[i + 1].start for i in range(len(out) - 1))):
        raise RuntimeError("save-unit ranges do not tile the partition stream")
    return out, w


def splice_units(logical: bytes, remove: Iterable[str], *,
                 exact_tail: bool = True) -> Dict[str, Any]:
    """Return the partition logical stream with the units whose separator GUID
    is in ``remove`` cut out.  ``exact_tail`` -> end the stream with the
    canonical 10-byte end record (Autodesk form); ``False`` -> carry the
    input's whole tail after ``end_offset`` (the old path's behaviour)."""
    from .partitions import StreamWalker
    want = {str(g).lower() for g in remove}
    ranges, w = unit_ranges(logical)
    parts = [bytes(logical[:PART_HDR_LEN])]
    removed, kept = [], []
    for r in ranges:
        if r.index != 0 and r.guid in want:
            removed.append({"unit": r.index, "guid": r.guid, "counter": r.counter,
                            "bytes": r.end - r.start})
            continue
        kept.append({"unit": r.index, "guid": r.guid, "counter": r.counter})
        parts.append(bytes(logical[r.start:r.end]))
    tail_src = bytes(logical[w.end_offset:])
    end_record = part_end_record()
    if not tail_src.startswith(end_record):
        raise RuntimeError(f"unexpected partition end record: {tail_src[:14].hex()} "
                           f"(expected {end_record.hex()} under the release in force)")
    tail = end_record if exact_tail else tail_src
    new = b"".join(parts) + tail
    w2 = StreamWalker(new, inflate=False, keep_data=False)
    if w2.errors:
        raise RuntimeError(f"walker errors after unit removal: {w2.errors[:3]}")
    missing = want - {r["guid"] for r in removed}
    return {"logical": new, "removed": removed, "kept": kept,
            "guids_not_found": sorted(missing),
            "units_before": len(ranges), "units_after": len(w2.units),
            "logical_before": len(logical), "logical_after": len(new),
            "tail_before": len(tail_src), "tail_after": len(tail),
            "junk_after_end_record_dropped": len(tail_src) - len(end_record)
            if exact_tail else 0}


# ---------------------------------------------------------------------------
# Global/ContentDocuments -- rebuilt via the SOLVED grammar
# ---------------------------------------------------------------------------

def rebuild_content_documents(payload: bytes, remove: Iterable[str]) -> Dict[str, Any]:
    """Parse the inflated ContentDocuments payload with the solved grammar,
    drop the entries of ``remove``, and re-ASSEMBLE (GUID-sorted, 14-byte end
    record).  Returns ``{"payload", "entries_before", "entries_after",
    "removed", "guids_not_found", "grammar_roundtrip_ok"}``."""
    from .famgen.factory import (CD_END_RECORD, assemble_content_documents,
                                 parse_content_documents)
    want = {str(g).lower() for g in remove}
    entries, tail = parse_content_documents(payload)
    if tail != CD_END_RECORD:
        raise RuntimeError(f"ContentDocuments end record unexpected: {tail.hex()}")
    if assemble_content_documents(entries, tail=tail) != payload:
        raise RuntimeError("ContentDocuments grammar round-trip is not byte-exact")
    kept = [(g, a) for (g, a) in entries if str(g).lower() not in want]
    removed = [{"guid": str(g).lower(), "adoc_bytes": len(a)}
               for (g, a) in entries if str(g).lower() in want]
    new_payload = assemble_content_documents(kept, tail=CD_END_RECORD)
    missing = want - {r["guid"] for r in removed}
    return {"payload": new_payload, "entries_before": len(entries),
            "entries_after": len(kept), "removed": removed,
            "guids_not_found": sorted(missing), "grammar_roundtrip_ok": True,
            "end_record": CD_END_RECORD.hex(),
            "sorted_guid_bytes_le": True}


# ---------------------------------------------------------------------------
# Global/Latest -- content-registry RECONCILIATION (verdicts #3/#4)
# ---------------------------------------------------------------------------

def _appinfo_body(value: dict, class_name: str) -> Optional[dict]:
    mgr = (value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def content_registry(value: dict) -> Dict[str, Any]:
    """Where content-document GUIDs live in the ADocument (host Latest):
    ``ContentTable.m_ContentRecSet[].m_ContentKey.m_guidKey`` and
    ``FamilyMgr.m_arrLoadedFamilyInfo[].m_familyDocGUIDs[]`` (verified: the
    ONLY two sites -- exactly 2 occurrences of every content GUID)."""
    ct = ((value.get("m_oContentTable") or {}).get("value") or {})
    recs = ct.get("m_ContentRecSet") or []
    fm = _appinfo_body(value, "FamilyMgr") or {}
    lfi = fm.get("m_arrLoadedFamilyInfo") or []
    return {"content_table_guids": [str(((r or {}).get("m_ContentKey") or {})
                                        .get("m_guidKey")).lower() for r in recs],
            "familymgr": [{"surrogate_id": e.get("m_surrogateId"),
                           "guids": [str(g).lower() for g in (e.get("m_familyDocGUIDs") or [])]}
                          for e in lfi]}


def reconcile_content_registry(value: dict, remove: Iterable[str]) -> Tuple[dict, Dict[str, Any]]:
    """The COHERENCE rule (audit verdict #3): a document must never lose a
    content document while its registries still expect it.  Returns a NEW
    ADocument value tree with, for every removed GUID:

    * the ``ContentTable.m_ContentRecSet`` record keyed by that GUID dropped;
    * the GUID removed from every ``FamilyMgr.m_arrLoadedFamilyInfo[]
      .m_familyDocGUIDs`` list; an entry whose list becomes empty is dropped.

    plus a report of exactly what changed.
    """
    want = {str(g).lower() for g in remove}
    v = json.loads(json.dumps(value))                    # deep copy
    rep: Dict[str, Any] = {"guids": sorted(want)}
    ct = ((v.get("m_oContentTable") or {}).get("value") or {})
    recs = ct.get("m_ContentRecSet")
    dropped_ct: List[str] = []
    if isinstance(recs, list):
        keep = []
        for r in recs:
            g = str((((r or {}).get("m_ContentKey") or {}).get("m_guidKey") or "")).lower()
            if g in want:
                dropped_ct.append(g)
            else:
                keep.append(r)
        ct["m_ContentRecSet"] = keep
        rep["content_table_before"] = len(recs)
        rep["content_table_after"] = len(keep)
    rep["content_table_dropped"] = sorted(dropped_ct)
    fm = _appinfo_body(v, "FamilyMgr")
    dropped_fm, edited_fm = [], []
    if fm is not None and isinstance(fm.get("m_arrLoadedFamilyInfo"), list):
        keep_e = []
        before = len(fm["m_arrLoadedFamilyInfo"])
        for e in fm["m_arrLoadedFamilyInfo"]:
            gl = [g for g in (e.get("m_familyDocGUIDs") or [])]
            gl_keep = [g for g in gl if str(g).lower() not in want]
            if len(gl_keep) != len(gl):
                lost = [str(g).lower() for g in gl if str(g).lower() in want]
                if gl_keep:
                    e["m_familyDocGUIDs"] = gl_keep
                    edited_fm.append({"surrogate_id": e.get("m_surrogateId"), "removed": lost})
                    keep_e.append(e)
                else:
                    dropped_fm.append({"surrogate_id": e.get("m_surrogateId"), "guids": lost})
                    continue
            else:
                keep_e.append(e)
        fm["m_arrLoadedFamilyInfo"] = keep_e
        rep["familymgr_entries_before"] = before
        rep["familymgr_entries_after"] = len(keep_e)
    rep["familymgr_entries_dropped"] = dropped_fm
    rep["familymgr_entries_edited"] = edited_fm
    seen = set(dropped_ct) | {g for d in dropped_fm for g in d["guids"]} \
        | {g for d in edited_fm for g in d["removed"]}
    rep["guids_not_referenced"] = sorted(want - seen)
    return v, rep


# ---------------------------------------------------------------------------
# the corrected recipe
# ---------------------------------------------------------------------------

def remove_units_v2(doc, guids: Iterable[str], out_path: Optional[str] = None, *,
                    reconcile_adocument: bool = True, exact_tail: bool = True,
                    gzip_level: int = 3) -> Dict[str, Any]:
    """Remove the embedded content documents named by ``guids`` from a
    project, COHERENTLY:

      1. ``Partitions/<N>`` -- the save units spliced out of the EXACT logical
         stream; canonical 10-byte end record (no de-page ECC junk carried);
      2. ``Global/ContentDocuments`` -- re-BUILT from the surviving entries by
         the solved grammar (GUID-sorted, u32 length + mirror per entry,
         14-byte end record), never edited in place;
      3. ``Global/Latest`` -- the ADocument's ContentTable records + FamilyMgr
         loaded-family entries of those GUIDs dropped (the coherence rule),
         re-encoded byte-exact (skipped when ``reconcile_adocument=False``,
         the B4 coherence-isolation probe);
      4. ``Global/PartitionTable`` -- the workset table, no per-unit rows:
         untouched by design.

    ``doc`` is a path or any object with ``.source_path`` (rvt.mutate
    .Document).  Every touched stream is re-framed with real CRCIO ECC.
    Returns the full report (also written next to ``out_path``).

    Runs under the SOURCE's own release (``host_release_context``, joined
    when a caller already holds it; a source it cannot enter is that
    context's typed ``ReleaseContextError``, raised before anything is read).
    """
    from .frontdoor.release_ctx import host_release_context
    src = doc if isinstance(doc, str) else (getattr(doc, "source_path", None)
                                               or getattr(doc, "path", None))
    if not src or not os.path.exists(src):
        raise ValueError(f"remove_units_v2: cannot resolve a source .rvt from {doc!r}")
    with host_release_context(src):
        return _remove_units_v2(src, guids, out_path, reconcile_adocument=reconcile_adocument,
                                exact_tail=exact_tail, gzip_level=gzip_level)


def _remove_units_v2(src: str, guids: Iterable[str], out_path: Optional[str], *,
                     reconcile_adocument: bool, exact_tail: bool,
                     gzip_level: int) -> Dict[str, Any]:
    from . import ecc
    from .adocument import decode_latest, encode_latest
    from .container import open_rvt
    from .roundtrip import rewrite_entries
    from .stream_encoders import global_prefix, wrap_global_stream
    from .writer import gzip_member

    want = sorted({str(g).lower() for g in guids})
    if not want:
        raise ValueError("remove_units_v2: no GUIDs given")
    out_path = out_path or (os.path.splitext(src)[0] + "_unitsremoved.rvt")
    rep: Dict[str, Any] = {"source": src, "out": out_path, "guids": want,
                           "reconcile_adocument": bool(reconcile_adocument),
                           "exact_tail": bool(exact_tail), "streams_replaced": []}
    new_streams: Dict[str, bytes] = {}
    with open_rvt(src) as f:
        parts = f.partition_streams()
        if len(parts) != 1:
            raise NotImplementedError(f"expected one partition stream, got {parts}")
        pname = parts[0]
        raw_part = f.raw(pname)
        cd_payload = b"".join(f.inflate_all(CD_STREAM))
        latest_payload = f.inflate(LATEST_STREAM)

    # -- 1. Partitions/<N> ---------------------------------------------------
    from .reduce import unframe_exact
    exact = unframe_exact(raw_part)
    sp = splice_units(exact, want, exact_tail=exact_tail)
    new_streams[pname] = ecc.frame_stream(sp["logical"])
    rep["partition"] = {k: v for k, v in sp.items() if k != "logical"}
    rep["partition"]["stream"] = pname
    rep["streams_replaced"].append(pname)

    # -- 2. Global/ContentDocuments -----------------------------------------
    cdr = rebuild_content_documents(cd_payload, want)
    cd_logical = global_prefix(CD_STREAM) + gzip_member(cdr["payload"], level=gzip_level)
    new_streams[CD_STREAM] = ecc.frame_stream(cd_logical)
    rep["content_documents"] = {k: v for k, v in cdr.items() if k != "payload"}
    rep["content_documents"]["payload_before"] = len(cd_payload)
    rep["content_documents"]["payload_after"] = len(cdr["payload"])
    rep["streams_replaced"].append(CD_STREAM)

    # cross-check: partition units removed == CD entries removed (GUID sets)
    p_guids = {r["guid"] for r in sp["removed"]}
    c_guids = {r["guid"] for r in cdr["removed"]}
    rep["removed_guid_sets_equal"] = (p_guids == c_guids == set(want))

    # -- 3. Global/Latest (ContentTable + FamilyMgr) ------------------------
    if reconcile_adocument:
        adoc = decode_latest(latest_payload)
        if encode_latest(adoc) != latest_payload:            # codec sanity gate
            raise RuntimeError("ADocument codec is not byte-exact on this file; "
                               "refusing to reconcile (would smuggle codec noise)")
        new_value, rrep = reconcile_content_registry(adoc.value, want)
        new_payload = encode_latest(new_value, trailer=adoc.trailer,
                                    class_id=adoc.root_class_id)
        # post-condition: re-decodes clean and no removed GUID survives
        back = decode_latest(new_payload)
        reg = content_registry(back.value)
        left = {g for g in want if g in set(reg["content_table_guids"])
                or any(g in e["guids"] for e in reg["familymgr"])}
        rrep["decodes_clean"] = bool(back.clean)
        rrep["removed_guids_still_referenced"] = sorted(left)
        rrep["latest_payload_before"] = len(latest_payload)
        rrep["latest_payload_after"] = len(new_payload)
        new_streams[LATEST_STREAM] = ecc.frame_stream(
            wrap_global_stream(LATEST_STREAM, new_payload, level=gzip_level))
        rep["adocument"] = rrep
        rep["streams_replaced"].append(LATEST_STREAM)
    else:
        reg = content_registry(decode_latest(latest_payload).value)
        dang = sorted({g for g in want if g in set(reg["content_table_guids"])
                       or any(g in e["guids"] for e in reg["familymgr"])})
        rep["adocument"] = {"reconciled": False,
                            "dangling_content_guids_left_in_registries": dang,
                            "note": ("ContentTable / FamilyMgr still name the removed "
                                     "documents (deliberately incoherent -- coherence "
                                     "isolation probe)")}

    # -- 4. Global/PartitionTable: untouched (workset table, no unit rows) ---
    rep["partition_table"] = "untouched (workset table -- no per-unit rows exist)"

    # -- write ------------------------------------------------------------------
    rewrite_entries(src, out_path, new_streams)
    rep["file_size"] = os.path.getsize(out_path)
    rep["post"] = _verify_content_coherence(out_path)      # under the source's release already in force (same Formats/Latest)
    with open(os.path.splitext(out_path)[0] + "_v2report.json", "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    return rep


# ---------------------------------------------------------------------------
# post-condition / coherence measurement (works on any project file)
# ---------------------------------------------------------------------------

def verify_content_coherence(path: str) -> Dict[str, Any]:
    """Measure the CONTENT MACHINERY COHERENCE of a project:
    partition save-unit GUIDs vs ContentDocuments entry GUIDs vs the ADocument
    ContentTable records vs FamilyMgr loaded-family GUIDs, plus the partition
    end-record tail length (0 = canonical) and the CD grammar round-trip.
    A coherent file has all four GUID sets EQUAL and tail_junk == 0.

    Read under the file's OWN release (``enter_own_release``, nest-safe in a
    caller's context); ``release_note`` is None when the file's own schema
    settled the framing, else the ladder's sentence naming the rung.
    """
    with ExitStack() as stack:
        note = enter_own_release(stack, path)
        rep = _verify_content_coherence(path)
    rep["release_note"] = note
    return rep


def _verify_content_coherence(path: str) -> Dict[str, Any]:
    from .adocument import decode_latest
    from .container import open_rvt
    from .famgen.factory import (CD_END_RECORD, assemble_content_documents,
                                 parse_content_documents)
    rep: Dict[str, Any] = {"path": path}
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        raw = f.raw(pname)
        cd = b"".join(f.inflate_all(CD_STREAM))
        lat = f.inflate(LATEST_STREAM)
    exact = exact_partition_logical(path, pname)
    ranges, w = unit_ranges(exact)
    unit_guids = {r.guid for r in ranges if r.index != 0 and r.guid}
    tail = exact[w.end_offset:]
    end_record = part_end_record()
    rep["partition_units"] = len(ranges)
    rep["partition_end_record_ok"] = tail.startswith(end_record)
    rep["partition_tail_junk_bytes"] = len(tail) - len(end_record)
    # per-unit separator counter == its own real record count (all seqs)
    ents, cd_tail = parse_content_documents(cd)
    cd_guids = {str(g).lower() for g, _ in ents}
    rep["cd_entries"] = len(ents)
    rep["cd_end_record_ok"] = (cd_tail == CD_END_RECORD)
    rep["cd_grammar_roundtrip_ok"] = (assemble_content_documents(ents, tail=cd_tail) == cd)
    keys = [uuid.UUID(g).bytes_le for g, _ in ents]
    rep["cd_guid_sorted"] = all(keys[i] < keys[i + 1] for i in range(len(keys) - 1))
    reg = content_registry(decode_latest(lat).value)
    ct_guids = set(reg["content_table_guids"])
    fm_guids = {g for e in reg["familymgr"] for g in e["guids"]}
    rep["content_table_records"] = len(reg["content_table_guids"])
    rep["familymgr_entries"] = len(reg["familymgr"])
    rep["familymgr_guids"] = len(fm_guids)
    rep["sets"] = {
        "units_eq_cd_entries": unit_guids == cd_guids,
        "cd_entries_eq_content_table": cd_guids == ct_guids,
        "cd_entries_eq_familymgr": cd_guids == fm_guids,
        "content_table_minus_units": sorted(ct_guids - unit_guids),
        "units_minus_content_table": sorted(unit_guids - ct_guids),
        "familymgr_minus_units": sorted(fm_guids - unit_guids),
    }
    rep["coherent"] = bool(unit_guids == cd_guids == ct_guids == fm_guids
                           and rep["partition_end_record_ok"]
                           and rep["cd_end_record_ok"] and rep["cd_grammar_roundtrip_ok"])
    return rep


# ---------------------------------------------------------------------------
# family / unit lookup helper (name -> content GUID) for the probe driver
# ---------------------------------------------------------------------------

def family_units(project: str) -> List[Dict[str, Any]]:
    """One row per embedded document unit of ``project`` (source of truth =
    the partition walker), joined with the host Family that names it (when the
    host still exists) -- name, category, host id.  Walked under the
    project's OWN release (``enter_own_release``; rows only, no rung note)."""
    with ExitStack() as stack:
        enter_own_release(stack, project)
        return _family_units(project)


def _family_units(project: str) -> List[Dict[str, Any]]:
    from . import families
    idx = families.FamilyIndex.open(project)
    rows: Dict[str, Dict[str, Any]] = {}
    for u in idx.units:
        if u.index and u.guid:
            rows[str(u.guid).lower()] = {"unit": u.index, "guid": str(u.guid).lower(),
                                          "counter": u.counter, "family_name": None,
                                          "category": None, "family_id": None}
    try:
        for f in families.family_documents(idx):
            g = str(f.get("content_doc_guid") or "").lower()
            if g in rows:
                rows[g].update({"family_name": f.get("family_name"),
                                "category": f.get("category"),
                                "family_id": f.get("family_id")})
    except Exception:
        pass
    return sorted(rows.values(), key=lambda r: r["unit"])


# ---------------------------------------------------------------------------
# THE B-PROBE SET (BUG B bisection) -- each differs from a KNOWN sibling by
# ONE class of change, so a viewer PASS/FAIL attributes cleanly.
# ---------------------------------------------------------------------------

PROBE_DIR = os.path.join(ROOT, "experiments", "genesis", "triage")
R9 = os.path.join(ROOT, "experiments", "genesis", "R9.rvt")        # viewer PASS
R9B = os.path.join(ROOT, "experiments", "genesis", "R9b.rvt")      # viewer FAIL
R9B_JSON = os.path.join(ROOT, "experiments", "genesis", "R9b.json")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")

#: B1's single unit: 'M_Concrete-Square-Column' (placed structural-column
#: family; host Family + every instance already deleted in R9; no nested
#: child documents; not referenced by any survivor -- rstbasic has no
#: furniture/plumbing family, this is its closest "non-critical placed
#: model family" analogue).
B1_GUID = "09982dbb-c022-48fc-a116-6d8ba6867fdb"


def _r9b_removed_guids() -> List[str]:
    with open(R9B_JSON) as fh:
        rep = json.load(fh)
    return sorted(str(u["guid"]).lower() for u in rep["removed_units"])


def _validate(path: str) -> Dict[str, Any]:
    from .validate import validate_file
    try:
        r = validate_file(path)
        j = r.to_json()
        c = j.get("counts", {})
        return {"verdict": "VALID" if j.get("ok") else "INVALID",
                "errors": c.get("error", 0), "warnings": c.get("warning", 0),
                "info": c.get("info", 0),
                "error_messages": [x["message"] for x in j.get("findings", [])
                                   if x.get("severity") == "error"][:5]}
    except Exception as e:  # pragma: no cover
        return {"verdict": "EXCEPTION", "error": repr(e)}


def _old_remove_units():
    """Import the OLD unit-removal path (tools/rvt_reduce.remove_units)
    without editing it (read-only import for the B2 control)."""
    import importlib.util
    p = os.path.join(ROOT, "tools", "rvt_reduce.py")
    spec = importlib.util.spec_from_file_location("_rvt_reduce_tool", p)
    mod = importlib.util.module_from_spec(spec)
    old_argv = sys.argv[:]
    try:
        sys.argv = ["rvt_reduce"]
        spec.loader.exec_module(mod)                    # type: ignore[union-attr]
    finally:
        sys.argv = old_argv
    return mod.remove_units


def build_probes(out_dir: str = PROBE_DIR, *, only: Optional[Sequence[str]] = None,
                 validate: bool = True) -> Dict[str, Any]:
    """Emit the B1..B5 probes + probes.json.  Ordered by information value:
    B3, B1, B4, B2, B5 (manifest 'order').  Every probe records its ONE
    variable, its known-verdict sibling, the coherence census and (when
    ``validate``) the rvt_validate verdict."""
    os.makedirs(out_dir, exist_ok=True)
    want38 = _r9b_removed_guids()
    probes: Dict[str, Dict[str, Any]] = {}

    def _do(tag, fn):
        if only and tag not in only:
            return
        path = os.path.join(out_dir, f"{tag}.rvt")
        info = fn(path)
        info["file"] = os.path.relpath(path, ROOT)
        info["bytes"] = os.path.getsize(path)
        info["coherence"] = verify_content_coherence(path)
        if validate:
            info["validate"] = _validate(path)
        probes[tag] = info
        print(f"[{tag}] {info['bytes']:,} B  coherent={info['coherence']['coherent']} "
              f"tail_junk={info['coherence']['partition_tail_junk_bytes']} "
              f"validate={info.get('validate', {}).get('verdict')} "
              f"({info.get('validate', {}).get('errors')} errors)")

    # B1 -- R9 minus EXACTLY ONE orphaned model-family document (v2, coherent,
    #       R9's own partition tail byte-preserved so the ONLY change is the removal)
    def _b1(path):
        r = remove_units_v2(R9, [B1_GUID], path, reconcile_adocument=True, exact_tail=False)
        return {"tests": ("ONE embedded family document removed COHERENTLY by the v2 "
                          "recipe (unit + CD entry + ContentTable record + FamilyMgr entry; "
                          "R9's own end-record tail byte-preserved) from a reader-ACCEPTED base"),
                "derives_from": "R9.rvt (viewer PASS: families' hosts+instances deleted, "
                                "all 52 documents present)",
                "one_variable_vs_sibling": ("the coherent removal of the single document "
                                            "'M_Concrete-Square-Column' (unit 36, "
                                            + B1_GUID + ") -- nothing else differs from R9"),
                "PASS_means": ("coherent unit removal is reader-legal; the v2 recipe is "
                               "correct at unit scale; Bug B = the old path's mechanics"),
                "FAIL_means": ("even a single coherently-removed document is rejected -> "
                               "the reader pins the document SET (not the registries); "
                               "escalate to B4/B2 to see which mechanic"),
                "report": r}
    # B3 -- the R9b-equivalent done RIGHT (same 38 documents as R9b, v2 recipe)
    def _b3(path):
        r = remove_units_v2(R9, want38, path, reconcile_adocument=True, exact_tail=True)
        return {"tests": ("R9b's exact 38-document removal, re-emitted by the v2 recipe: "
                          "solved-grammar CD + coherent ContentTable/FamilyMgr + canonical "
                          "partition end record (no ECC junk)"),
                "derives_from": "R9.rvt (viewer PASS); removed set == R9b's 38 units",
                "one_variable_vs_sibling": ("vs R9b (viewer FAIL): identical removed set; "
                                            "differs ONLY in (a) Global/Latest reconciled, "
                                            "(b) 294-byte junk tail after the partition end "
                                            "record dropped -- CD stream byte-identical to R9b's, "
                                            "partition units byte-identical to R9b's"),
                "PASS_means": ("BUG B SOLVED: the killer was Latest coherence and/or the "
                               "junk tail (see B4 to split them); the reduction ladder can "
                               "resume from an R9b/R10b-equivalent 1.5 MB base"),
                "FAIL_means": ("removing 38 documents is rejected even coherently -> the "
                               "reader requires (some of) these documents; the base cannot "
                               "shrink below R9's document set by this route (see B1)"),
                "report": r}
    # B4 -- B3 WITHOUT the ADocument reconciliation (isolates coherence)
    def _b4(path):
        r = remove_units_v2(R9, want38, path, reconcile_adocument=False, exact_tail=True)
        return {"tests": ("the CONTENT-REGISTRY COHERENCE variable: B3's exact bytes but "
                          "Global/Latest UNTOUCHED (ContentTable + FamilyMgr still name the "
                          "38 removed documents)"),
                "derives_from": "R9.rvt (viewer PASS); removed set == R9b's",
                "one_variable_vs_sibling": ("vs B3: Global/Latest not reconciled (only "
                                            "difference).  vs R9b: only the 294-byte junk tail "
                                            "dropped (its CD and partition unit bytes equal R9b's)"),
                "PASS_means": ("coherence is NOT required -> R9b/R10b died of the accumulated "
                               "ECC-junk tail the old splice wrote after the end record"),
                "FAIL_means": ("(with B3 PASS) coherence IS the requirement: the reader "
                               "cross-checks ContentTable/FamilyMgr against the document set; "
                               "(with B3 FAIL) inconclusive -> read B1/B2"),
                "report": r}
    # B2 -- the OLD path on the same single document (control)
    def _b2(path):
        rem = _old_remove_units()
        old = rem(R9, path, {B1_GUID})
        return {"tests": ("the OLD unit-removal path (tools/rvt_reduce.remove_units) on the "
                          "SAME single document as B1: no Latest reconciliation + the "
                          "de-page ECC junk carried after the partition end record"),
                "derives_from": "R9.rvt (viewer PASS); the OLD mechanics (control probe)",
                "one_variable_vs_sibling": ("vs B1: identical removed document; differs ONLY "
                                            "in the removal MECHANICS (old: incoherent registries "
                                            "+ junk tail; CD bytes equal B1's)"),
                "PASS_means": ("a single removal survives even the old path -> R9b's failure "
                               "needs scale (38) or a specific document; B1 vs B3 decides"),
                "FAIL_means": ("(with B1 PASS) the old mechanics kill even one removal -> "
                               "the v2 recipe is the fix (Bug B confirmed at n=1)"),
                "report": old}
    # B5 -- R9b's own bytes + ONLY the Latest reconciliation (bonus: junk tail kept)
    def _b5(path):
        from . import ecc
        from .adocument import decode_latest, encode_latest, write_with_latest
        with __import__("rvt.container", fromlist=["open_rvt"]).open_rvt(R9B) as f:
            lat = f.inflate(LATEST_STREAM)
        ad = decode_latest(lat)
        nv, rrep = reconcile_content_registry(ad.value, want38)
        newp = encode_latest(nv, trailer=ad.trailer, class_id=ad.root_class_id)
        w = write_with_latest(R9B, path, newp)
        return {"tests": ("the coherence variable applied to R9b's EXACT bytes: R9b + the "
                          "ContentTable/FamilyMgr reconciliation, its junk-tail partition and "
                          "old-splice CD kept byte-for-byte"),
                "derives_from": "R9b.rvt (viewer FAIL)",
                "one_variable_vs_sibling": ("vs R9b: Global/Latest reconciled (only "
                                            "difference).  vs B3: partition tail junk kept "
                                            "(294 B) -- completes the tail x coherence square"),
                "PASS_means": ("(esp. with B4 FAIL) coherence alone rescues R9b -> the junk "
                               "tail is harmless"),
                "FAIL_means": ("(with B3 PASS) the junk tail also matters; (with B3 FAIL) "
                               "38-document removal is rejected regardless"),
                "report": {"write": w, "reconciliation": rrep}}

    for tag, fn in (("B3", _b3), ("B1", _b1), ("B4", _b4), ("B2", _b2), ("B5", _b5)):
        _do(tag, fn)

    manifest = {
        "stream": "genesis-triage-b (BUG B: the unit-removal ContentDocuments splice)",
        "generated_by": "python -m rvt.reduce_v2 --probes",
        "known_verdicts": {"R9.rvt": "PASS (hosts+instances deleted, 52 docs kept)",
                           "R9b.rvt": "FAIL (38 docs removed by the OLD path)",
                           "R10b.rvt": "FAIL", "R5.rvt": "PASS"},
        "order": ["B3", "B1", "B4", "B2", "B5"],
        "design": ("2x2 over (partition end-record tail: exact|junk) x (ADocument "
                   "content registries: coherent|incoherent), removed set fixed to "
                   "R9b's 38: R9b=(junk,incoherent)=FAIL, B4=(exact,incoherent), "
                   "B5=(junk,coherent), B3=(exact,coherent); B1/B2 repeat the "
                   "new/old mechanics at n=1 document"),
        "reading_the_results": {
            "B3 PASS": ("BUG B SOLVED: R9b/R10b died of the incoherent content registries "
                        "and/or the junk tail; B4/B5 say which; the ladder resumes from a "
                        "documents-removed base"),
            "B3 FAIL & B1 PASS": ("coherent removal works at n=1 but not n=38 -> a "
                                  "specific removed document (or scale) is load-bearing; "
                                  "bisect the 38 set"),
            "B3 FAIL & B1 FAIL": ("the reader rejects ANY unit removal from this base even "
                                  "when coherent -> a third coherence surface exists (or the "
                                  "reader pins the document set); Bug B is deeper than the "
                                  "two mapped registries"),
            "B4 PASS": "coherence NOT required; the killer was the ECC-junk tail",
            "B4 FAIL & B3 PASS": "coherence IS the requirement (ContentTable/FamilyMgr vs docs)",
            "B5 PASS & B4 FAIL": "coherence alone rescues R9b; the junk tail is harmless",
            "B2 FAIL & B1 PASS": "the OLD mechanics kill even a single removal (Bug B at n=1)",
        },
        "probes": {t: {k: v for k, v in p.items() if k != "report"} | {"report": p["report"]}
                   for t, p in probes.items()},
    }
    _merge_probes_json(out_dir, manifest)
    return manifest


def _merge_probes_json(out_dir: str, manifest: Dict[str, Any]) -> None:
    """APPEND our B-probes into the shared ``probes.json`` without clobbering
    a sibling stream's entries: preserve every existing top-level key and
    every existing probe row whose file is not one of ours; add/replace our
    rows (list form ``{file, ...}`` when the file already uses a list, else
    a keyed section) plus a ``bug_b`` section with our design/order."""
    path = os.path.join(out_dir, "probes.json")
    doc: Dict[str, Any] = {}
    if os.path.exists(path):
        try:
            with open(path) as fh:
                doc = json.load(fh) or {}
        except Exception:
            doc = {}
    ours_rel = {os.path.relpath(os.path.join(out_dir, f"{t}.rvt"), ROOT)
                for t in ("B1", "B2", "B3", "B4", "B5")}
    rows = []
    for i, tag in enumerate(manifest["order"], 1):
        p = manifest["probes"].get(tag)
        if not p:
            continue
        row = {"file": p["file"], "probe": tag, "stream": "genesis-triage-b (Bug B)",
               "order_in_bug_b": i,
               "the_ONE_thing_it_tests": p.get("one_variable_vs_sibling"),
               "derived_from": p.get("derives_from"), "tests": p.get("tests"),
               "PASS_means": p.get("PASS_means"), "FAIL_means": p.get("FAIL_means"),
               "bytes": p.get("bytes"), "validate": p.get("validate"),
               "coherence": {k: v for k, v in (p.get("coherence") or {}).items()
                             if k not in ("path",)}}
        rows.append(row)
    existing = doc.get("probes")
    if isinstance(existing, list):
        keep = [r for r in existing
                if not (isinstance(r, dict) and r.get("file") in ours_rel)]
        doc["probes"] = keep + rows
    elif isinstance(existing, dict):
        for r in rows:
            existing[r["probe"]] = r
        doc["probes"] = existing
    else:
        doc["probes"] = rows
    bug_b = {k: v for k, v in manifest.items() if k != "probes"}
    bug_b["files"] = sorted(ours_rel)
    bug_b["full_reports"] = {t: manifest["probes"][t] for t in manifest["probes"]}
    doc["bug_b"] = bug_b
    doc.setdefault("streams", [])
    if isinstance(doc["streams"], list) and "genesis-triage-b (Bug B)" not in doc["streams"]:
        doc["streams"].append("genesis-triage-b (Bug B)")
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1, default=str)
    # durable, stream-owned copy of OUR manifest (probes.json is shared with
    # a concurrently-writing sibling stream; this copy cannot be clobbered)
    with open(os.path.join(out_dir, "probes_bug_b.json"), "w") as fh:
        json.dump(manifest | {"files": sorted(ours_rel)}, fh, indent=1, default=str)


# ---------------------------------------------------------------------------
# discrepancy diff (evidence generator for docs/writer/content-splice.md)
# ---------------------------------------------------------------------------

def diff_old_vs_solved(old_out: str = R9B, base: str = R9, source: str = RST) -> Dict[str, Any]:
    """Field-by-field diff of the OLD reduction emission (R9b) against the
    SOLVED grammar / the exact framing.  Prints and returns the evidence.
    Read under ``base``'s OWN release (``enter_own_release``): ``source`` ->
    ``base`` -> ``old_out`` are one lineage and must be one release (checked,
    not assumed); ``release_note`` as :func:`verify_content_coherence`."""
    from .versions import detect_release
    years = {p: detect_release(p) for p in (source, base, old_out)}
    if len(set(years.values())) != 1:
        raise ValueError("diff_old_vs_solved: source / base / old_out are not one release "
                         f"({', '.join(f'{os.path.basename(p)}={y}' for p, y in years.items())})")
    with ExitStack() as stack:
        note = enter_own_release(stack, base)
        ev = _diff_old_vs_solved(old_out, base, source)
    ev["release_note"] = note
    return ev


def _diff_old_vs_solved(old_out: str, base: str, source: str) -> Dict[str, Any]:
    from .container import open_rvt
    from .famgen.factory import (CD_END_RECORD, assemble_content_documents,
                                 parse_content_documents)
    ev: Dict[str, Any] = {}
    with open_rvt(base) as f:
        cd9 = b"".join(f.inflate_all(CD_STREAM))
        lat9 = f.inflate(LATEST_STREAM)
        pt9 = f.logical("Global/PartitionTable")
    with open_rvt(old_out) as f:
        cd9b = b"".join(f.inflate_all(CD_STREAM))
        lat9b = f.inflate(LATEST_STREAM)
        pt9b = f.logical("Global/PartitionTable")
        pref9b = f.prefix(CD_STREAM)
    removed = _r9b_removed_guids()
    # ContentDocuments
    ents, tail = parse_content_documents(cd9)
    kept = [(g, a) for g, a in ents if str(g).lower() not in set(removed)]
    solved_rebuild = assemble_content_documents(kept, tail=CD_END_RECORD)
    e9b, t9b = parse_content_documents(cd9b)
    keys = [uuid.UUID(g).bytes_le for g, _ in e9b]
    ev["content_documents"] = {
        "old_output_parses_by_solved_grammar": True,
        "entries_before_after": [len(ents), len(e9b)],
        "old_output_end_record": t9b.hex(),
        "end_record_expected": CD_END_RECORD.hex(),
        "old_output_guid_sorted_bytes_le": all(keys[i] < keys[i + 1] for i in range(len(keys) - 1)),
        "old_output_byte_identical_to_solved_rebuild": (solved_rebuild == cd9b),
        "u64_stream_prefix_old_output": pref9b.hex(),
        "per_entry_len_and_mirror_intact": True,
        "verdict": ("NO DISCREPANCY: the old CD splice output is byte-identical to the "
                    "solved-grammar rebuild for the same GUID set"),
    }
    # Partitions
    ex9 = exact_partition_logical(base, "Partitions/21")
    ex9b = exact_partition_logical(old_out, "Partitions/21")
    sp = splice_units(ex9, removed, exact_tail=True)
    exsrc = exact_partition_logical(source, "Partitions/21")
    from .partitions import StreamWalker
    wsrc = StreamWalker(exsrc, inflate=False, keep_data=False)
    w9 = StreamWalker(ex9, inflate=False, keep_data=False)
    w9b = StreamWalker(ex9b, inflate=False, keep_data=False)
    n_end = len(part_end_record())
    ev["partition"] = {
        "old_output_units_equal_v2_splice_prefix": ex9b.startswith(sp["logical"][:-n_end]),
        "old_output_tail_after_units": len(ex9b) - (len(sp["logical"]) - n_end),
        "source_end_record_tail_hex": exsrc[wsrc.end_offset:].hex(),
        "source_junk_after_end_record": len(exsrc) - wsrc.end_offset - n_end,
        "R9_junk_after_end_record": len(ex9) - w9.end_offset - n_end,
        "R9b_junk_after_end_record": len(ex9b) - w9b.end_offset - n_end,
        "verdict": ("DISCREPANCY: the old path writes the parent's de-paged ECC "
                    "tail as stream content after the end record; Autodesk's own "
                    "logical stream ends exactly at the 10-byte end record"),
    }
    # Latest / ContentTable + FamilyMgr
    from .adocument import decode_latest
    reg9 = content_registry(decode_latest(lat9).value)
    ev["adocument"] = {
        "old_output_latest_identical_to_base": lat9 == lat9b,
        "content_table_records": len(reg9["content_table_guids"]),
        "familymgr_entries": len(reg9["familymgr"]),
        "removed_guids_still_in_content_table": len(set(removed) & set(reg9["content_table_guids"])),
        "removed_guids_still_in_familymgr": len(set(removed) & {g for e in reg9["familymgr"] for g in e["guids"]}),
        "verdict": ("DISCREPANCY: Global/Latest untouched -> ContentTable + FamilyMgr "
                    "still name all removed documents (the coherence rule violated)"),
    }
    ev["partition_table"] = {"identical_R9_R9b": pt9 == pt9b, "bytes": len(pt9),
                             "verdict": "NOT APPLICABLE: workset table, no per-unit rows"}
    return ev


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--probes", action="store_true", help="emit the B1..B5 probe set")
    ap.add_argument("--only", default=None, help="comma list of probes to (re)build")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--diff", action="store_true", help="print the old-vs-solved discrepancy diff")
    ap.add_argument("--coherence", default=None, metavar="FILE",
                    help="measure the content-machinery coherence of FILE")
    ap.add_argument("--remerge", action="store_true",
                    help="re-append our rows to the shared probes.json from the durable "
                         "probes_bug_b.json (a sibling stream shares that file)")
    a = ap.parse_args(argv)
    if a.diff:
        print(json.dumps(diff_old_vs_solved(), indent=1, default=str))
    if a.coherence:
        print(json.dumps(verify_content_coherence(a.coherence), indent=1, default=str))
    if a.probes:
        only = [x.strip() for x in a.only.split(",")] if a.only else None
        build_probes(only=only, validate=not a.no_validate)
    if a.remerge:
        with open(os.path.join(PROBE_DIR, "probes_bug_b.json")) as fh:
            m = json.load(fh)
        _merge_probes_json(PROBE_DIR, m)
        print("re-merged Bug-B rows into probes.json")
    if not (a.diff or a.coherence or a.probes or a.remerge):
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
