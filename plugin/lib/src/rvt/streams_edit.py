"""Mutation helpers for the small table streams (the writer's save-side edits).

Operates on the plain-dict models produced by ``rvt.stream_encoders``:

* ``elemtable_add_element`` / ``elemtable_next_element_id`` — insert an
  ``ElemRec`` in ElementId order, keep the count and the last-id watermark.
* ``history_append_episode`` — record a new save episode (GUID prepended,
  newest first) and return the EpisodeId that new/edited ElemRecs must carry.
* ``increment_table_record_save`` — append one document-increment record
  (and normalise the previous newest one) the way consecutive saves in the
  corpus differ.
* ``contents_update_from_increment`` — refresh the ``Contents`` counter
  mirror from the newest increment record.
* ``basic_file_info_record_save`` — bump the increment count / version and
  episode GUIDs in ``BasicFileInfo``.
* ``save_impact`` — which of these tables MUST change when N new elements
  are added, and what stays constant (evidence in
  ``docs/streams/13-stream-encoders.md``).

Every rule here is derived from the six corpus files; the ones that are
inferred rather than directly observed are marked ``[hypothesis]`` in the
docstrings.  Nothing here touches the container/paging layers.
"""
from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

INVALID_ID = 0xFFFFFFFFFFFFFFFF     # ElementId::InvalidElementId (no owner)
NO_EPISODE = 0xFFFFFFFF             # ElementHistory "never user-modified"


# ---------------------------------------------------------------------------
# Global/ElemTable
# ---------------------------------------------------------------------------

def elemtable_watermark(model: Dict[str, Any]) -> int:
    """The footer's last-id watermark (highest ElementId ever issued)."""
    return int(model["footer"]["last_id"])


def elemtable_max_id(model: Dict[str, Any]) -> int:
    recs = model["records"]
    return max(r[4] for r in recs) if recs else 0


def elemtable_next_element_id(model: Dict[str, Any]) -> int:
    """Next ElementId to allocate = watermark + 1.

    Evidence (all six samples): the footer u64 watermark is >= every record
    id; it equals the max id in 5 files and exceeds it in racbasic (watermark
    1,098,947 vs max id 1,098,851 — 96 ids issued to since-deleted elements),
    i.e. it is a monotonic "highest ever issued" counter, so allocation is
    watermark+1 ``[hypothesis: allocation direction verified, off-by-one
    convention (next = wm+1 vs wm = next) not observable from static files]``.
    """
    return elemtable_watermark(model) + 1


def elemtable_add_element(model: Dict[str, Any], element_id: int, *,
                          creation_ep: int,
                          modified_ep: Optional[int] = None,
                          user_modified_ep: Optional[int] = NO_EPISODE,
                          original_id: Optional[int] = None,
                          owner_id: int = INVALID_ID,
                          partition_id: int = 0) -> int:
    """Insert one 40-byte ``ElemRec`` keeping the array id-sorted.

    Returns the insertion index.  ``original_id`` defaults to ``element_id``
    (no worksharing renumbering); ``modified_ep`` defaults to ``creation_ep``;
    ``user_modified_ep`` defaults to 0xFFFFFFFF ("never").  The footer
    watermark is raised to ``element_id`` if lower.  ``partition_id`` is 0 in
    all 128,331 corpus records.
    """
    if modified_ep is None:
        modified_ep = creation_ep
    if user_modified_ep is None:
        user_modified_ep = NO_EPISODE
    if original_id is None:
        original_id = element_id
    rec = (original_id, creation_ep, modified_ep, user_modified_ep,
           element_id, owner_id, partition_id)
    recs: List = model["records"]
    # binary search by id (records sorted ascending by index 4)
    lo, hi = 0, len(recs)
    while lo < hi:
        mid = (lo + hi) // 2
        if recs[mid][4] < element_id:
            lo = mid + 1
        else:
            hi = mid
    if lo < len(recs) and recs[lo][4] == element_id:
        raise ValueError(f"ElementId {element_id} already present in ElemTable")
    recs.insert(lo, rec)
    if element_id > model["footer"]["last_id"]:
        model["footer"]["last_id"] = element_id
    return lo


def elemtable_add_elements(model: Dict[str, Any], count: int, *,
                           creation_ep: int, **kw) -> List[int]:
    """Allocate ``count`` fresh ids (watermark+1 ...) and add records."""
    ids = []
    for _ in range(count):
        eid = elemtable_next_element_id(model)
        elemtable_add_element(model, eid, creation_ep=creation_ep, **kw)
        ids.append(eid)
    return ids


# ---------------------------------------------------------------------------
# Global/History
# ---------------------------------------------------------------------------

def history_episode_count(model: Dict[str, Any]) -> int:
    return len(model["entries"])


def history_append_episode(model: Dict[str, Any], guid: Optional[str] = None,
                           tag: int = 0x28) -> Tuple[int, str]:
    """Record a new save episode. Returns ``(episode_id, guid)``.

    Entries are stored NEWEST-FIRST, so the new episode is PREPENDED (index
    0) and the header count incremented; EpisodeIds used by ElemRecs count
    from the OLDEST entry, so the new episode's id = old entry count and
    existing records' ids are unchanged (invariant: history count ==
    max(m_lastModificationDate)+1, verified in all six samples).  The tag byte
    is 0x28 in all 6,597 corpus entries.  Entry 0 == BasicFileInfo's Unique
    Document GUID, so the caller must also update BasicFileInfo.
    """
    if guid is None:
        guid = str(uuid.uuid4())
    ep_id = len(model["entries"])
    model["entries"].insert(0, (guid, tag))
    model["hdr_count"] = len(model["entries"])
    return ep_id, guid


def history_upgrade_format(model: Dict[str, Any], version: int = 2662) -> None:
    """Ensure the ascending upgrade list ends at ``version`` (2662 = 2026)."""
    fv = model["format_versions"]
    if version not in fv:
        fv.append(version)
        fv.sort()


# ---------------------------------------------------------------------------
# Global/DocumentIncrementTable
# ---------------------------------------------------------------------------

def increment_table_record_save(model: Dict[str, Any], *, episode_id: int,
                                element_record_count: int, username: str,
                                timestamp: Optional[int] = None,
                                flag: int = 1) -> Dict[str, Any]:
    """Append one increment record for a save; returns the new record.

    Rules derived from consecutive corpus records (see doc §"what changes on
    save"):

    * ``sequence`` = previous + 1;  ``id_pair`` = (episode_id, episode_id+1)
      (= (last EpisodeId, History count) — 6/6 files);
    * ``pairs`` = [(-1, element_record_count)] and ``elem_id_repeat`` = the
      same value on the NEWEST record; every older record has
      ``elem_id_repeat`` = 0 (6/6) and gains a ``(sequence, 0)`` pair
      ``[hypothesis: (own sequence, 0) is the majority pattern; a minority of
      older records point at a later sequence]``;
    * ``counters`` = previous counters +1 element-wise (index 7 only on
      flag=1 saves), ``counter_g`` = previous + 1;
    * ``flag`` = 1 for an ordinary modifying save (0 for a no-change save);
    * copy 2 of the table is byte-identical to copy 1 (6/6).
    """
    recs: List[Dict[str, Any]] = model["records"]
    if not recs:
        raise ValueError("empty increment table: no template record to extend")
    prev = recs[-1]
    ts = int(timestamp if timestamp is not None else time.time())
    counters = list(prev["counters"])
    for i in range(len(counters)):
        if i == 7 and not flag:
            continue
        counters[i] += 1
    new = {
        "pairs": [(-1, element_record_count)],
        "username": username,
        "unknown_zero_1": 0,
        "id_pair": (episode_id, episode_id + 1),
        "unknown_zero_2": 0,
        "timestamp": ts,
        "sequence": prev["sequence"] + 1,
        "elem_id_repeat": element_record_count,
        "counters": counters,
        "counter_g": prev["counter_g"] + 1,
        "flag": flag,
    }
    # normalise the previous newest record
    prev["elem_id_repeat"] = 0
    prev_pairs = list(prev["pairs"])
    if not prev_pairs or prev_pairs[-1][1] != 0 or prev_pairs[-1][0] < 0:
        prev_pairs.append((prev["sequence"], 0))
    prev["pairs"] = prev_pairs
    recs.append(new)
    model["records2"] = copy.deepcopy(recs)
    return new


# ---------------------------------------------------------------------------
# Contents  /  BasicFileInfo
# ---------------------------------------------------------------------------

def contents_update_from_increment(contents: Dict[str, Any],
                                   newest_record: Dict[str, Any]) -> None:
    """Mirror the newest increment record into ``Contents``.

    ``Contents.counters`` == the newest DIT record's 10 counters with index
    7 removed, and ``Contents.counter_g`` == its ``counter_g`` (6/6 files).
    """
    ctr = list(newest_record["counters"])
    contents["counters"] = ctr[:7] + ctr[8:] if len(ctr) == 10 else ctr
    contents["counter_g"] = newest_record["counter_g"]


def basic_file_info_record_save(bfi: Dict[str, Any], *, increments: int,
                                episode_guid: str,
                                last_save_path: Optional[str] = None) -> None:
    """Bump BasicFileInfo for a save: increment count / version + GUIDs.

    ``unique_document_increments`` (a string!) == DIT record count and
    ``central_version_number`` == the same number; ``unique_document_guid``
    and ``central_episode_guid`` == History entry 0 (6/6 files).  The
    UTF-16 mirror block is regenerated by the encoder.
    """
    bfi["unique_document_increments"] = str(increments)
    bfi["central_version_number"] = int(increments)
    bfi["unique_document_guid"] = episode_guid
    bfi["central_episode_guid"] = episode_guid
    if last_save_path is not None:
        bfi["last_save_path"] = last_save_path


# ---------------------------------------------------------------------------
# Coordinated save
# ---------------------------------------------------------------------------

def record_save(models: Dict[str, Dict[str, Any]], *, new_element_ids: Sequence[int] = (),
                username: str = "user", element_record_count: Optional[int] = None,
                timestamp: Optional[int] = None,
                last_save_path: Optional[str] = None) -> Dict[str, Any]:
    """Apply ONE save across the coordinated tables (mutates ``models``).

    ``models`` keys: ``ElemTable``, ``History``, ``DocumentIncrementTable``,
    ``Contents``, ``BasicFileInfo`` (missing ones are skipped).  New elements
    (already inserted or listed in ``new_element_ids``) get the new EpisodeId.
    Returns a summary (episode id/guid, increment count, element count).
    """
    hist = models["History"]
    ep_id, ep_guid = history_append_episode(hist)
    et = models.get("ElemTable")
    if et is not None:
        for eid in new_element_ids:
            elemtable_add_element(et, eid, creation_ep=ep_id)
    dit = models.get("DocumentIncrementTable")
    newest = None
    if dit is not None:
        n_elem = element_record_count
        if n_elem is None:
            # best available proxy for the "-1 pair" value = element count
            n_elem = len(et["records"]) if et is not None else 0
        newest = increment_table_record_save(dit, episode_id=ep_id,
                                             element_record_count=n_elem,
                                             username=username, timestamp=timestamp)
    con = models.get("Contents")
    if con is not None and newest is not None:
        contents_update_from_increment(con, newest)
    bfi = models.get("BasicFileInfo")
    increments = len(dit["records"]) if dit is not None else None
    if bfi is not None and increments is not None:
        basic_file_info_record_save(bfi, increments=increments,
                                    episode_guid=ep_guid,
                                    last_save_path=last_save_path)
    return {
        "episode_id": ep_id,
        "episode_guid": ep_guid,
        "history_count": history_episode_count(hist),
        "increments": increments,
        "elem_count": len(et["records"]) if et is not None else None,
        "watermark": et["footer"]["last_id"] if et is not None else None,
    }


# ---------------------------------------------------------------------------
# "what MUST change when N elements are added" — the writer's checklist
# ---------------------------------------------------------------------------

def save_impact(n_new_elements: int) -> Dict[str, Any]:
    """Structured report: which streams change when a save adds N elements.

    Derived from the six-file corpus (relationships that hold 6/6 unless a
    tag says otherwise).  See docs/streams/13-stream-encoders.md §5.
    """
    n = int(n_new_elements)
    return {
        "n_new_elements": n,
        "must_change": {
            "Global/ElemTable": [
                f"+{n} ElemRec records (40 B each, inserted in ElementId order)",
                "u32 count += N; footer last-id watermark = max(new ids)",
                "new records: creation_ep = modified_ep = new EpisodeId, "
                "user_modified_ep = 0xFFFFFFFF (or the new episode), partition 0",
            ],
            "Global/History": [
                "+1 episode entry prepended (16-byte GUID + 0x28 tag), "
                "header count u32 += 1 (== max(m_lastModificationDate)+1 invariant)",
            ],
            "Global/DocumentIncrementTable": [
                "+1 increment record in BOTH serialized copies, u32 counts += 1",
                "new record: sequence+1, id_pair=(E,E+1), 10 counters each +1 "
                "(idx 7 only if flag=1), counter_g+1, flag=1, pairs=[(-1, elem_count)], "
                "elem_id_repeat = elem_count",
                "previous newest record: elem_id_repeat -> 0, gains a (sequence, 0) pair "
                "[hypothesis on the exact pair key]",
            ],
            "Contents": [
                "counters[] = newest DIT counters minus index 7; counter_g = newest DIT G",
                "(24-byte prologue and identity/GUID/build fields constant)",
            ],
            "BasicFileInfo": [
                "unique_document_increments (string) & central_version_number = DIT count",
                "unique_document_guid & central_episode_guid = new episode GUID (History entry 0)",
                "mirror text regenerated (byte-exact from fields)",
            ],
            "Partitions/<N> [not encoded here]": [
                "the new element object records themselves (object stream, another slice)",
                "18-byte stream header u32 @+14 elem_table_count = ElemTable count",
            ],
            "Global/Latest [not encoded here]": [
                "ADocument object graph (element-count / episode mirrors) — separate slice",
            ],
        },
        "constant": {
            "Formats/Latest": "per-release schema constant (496,597 B, identical corpus-wide)",
            "Global/PartitionTable": "workset table — unchanged unless a workset is added",
            "Global/ContentDocuments": "loaded content documents — unchanged unless content loaded",
            "ProjectInformation / TransmissionData": "project info / external refs — unchanged",
            "RevitPreview4.0": "thumbnail — unchanged (Revit regenerates on its own saves)",
            "8-byte Global/* prefixes": "Latest=5, CD/DIT/History=1, ElemTable/PartitionTable=0",
            "Contents class_ref / creation_guid / partition 'GLOBAL'": "constant per document",
        },
        "cross_check_invariants": [
            "History count == max(ElemRec.m_lastModificationDate) + 1        (6/6)",
            "DIT newest id_pair == (History count - 1, History count)      (6/6)",
            "BasicFileInfo increments == central_version_number == DIT count (6/6)",
            "BasicFileInfo Unique Document GUID == History entry[0].guid   (6/6)",
            "ElemTable ids strictly ascending; watermark >= max id       (6/6)",
            "Partitions/<N> header elem_table_count == ElemTable count    (6/6)",
            "Contents.counters == DIT newest counters minus index 7; G == DIT newest G (6/6)",
        ],
    }


if __name__ == "__main__":
    import json
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(json.dumps(save_impact(n), indent=2))
