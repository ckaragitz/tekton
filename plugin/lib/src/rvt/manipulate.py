"""manipulate.py -- edit EXISTING elements of an arbitrary .rvt.

The create path (:mod:`rvt.mutate` + :mod:`rvt.commit`) appends new
elements.  This module is the CHANGE / DELETE path for elements that
already exist in a user's project: it plans record-level edits against a
:class:`rvt.mutate.Document` and applies them with :func:`commit_plans`,
re-emitting save-unit 0 of ``Partitions/<N>`` and ``Global/ElemTable``.

Operations (each returns a JSON-able PLAN carrying framed record bytes)::

    doc  = rvt.mutate.Document.from_file("project.rvt")

    plan = delete_element(doc, eid, cascade=False)      # DeletePlan
    plan = modify_element(doc, eid, {"json.path": v})  # ModifyPlan
    plan = set_level_elevation(doc, level_id, elev_ft) # ModifyPlan
    plan = set_param(doc, eid, param_id, value)        # ModifyPlan (text/mark)
    plan = move_instance(doc, eid, (x, y, z))          # ModifyPlan
    plan = retype_instance(doc, eid, new_symbol_id)    # ModifyPlan

    commit_plans(src, out, [plans...])                 # or commit_deletions()
    verify_manipulated(out, deleted_ids, edited_ids)   # structural proof

Deletion model (evidence: docs/writer/manipulation.md):

* An element's three records (seq 101 ``ElementHeader`` / seq 102 object /
  seq 103 rep) are removed from save-unit 0; its 40-byte ``ElemRec`` is
  removed from ``Global/ElemTable`` (count decremented, id watermark KEPT);
  the partition stream-header count follows the table.
* HARD dependents (cascade set) come from STRUCTURAL relations only:
  elements whose object hosts on the deleted id (``m_hostId`` /
  ``m_extraHostIds`` / ``m_explicitHostIds``), ``SketchPlane``s whose
  geometry reference lies on the deleted element, ElemTable-owned children
  (``m_OwningElementId``) and object-owned elements (``m_ownerElemId`` /
  ``m_famId`` / ``m_superInstanceId``), elements placed on a deleted Level
  (``m_assocLevelId`` / ``m_levelId`` / ``m_genLevelId``), and ANNOTATION /
  leaf classes (tags, dimensions, warnings, a panel's own schedule view)
  whose header ``ElementParents.m_deletion`` names the deleted id.  The
  ``m_deletion`` list is NOT a general dependency signal: it mixes ownership
  with regenerate/constraint peers (joined walls, rooms, sketches, systems,
  a neighbouring host's inserts) -- those are neutralised, never cascaded.
* SOFT referrers: any other host-document element whose records mention a
  deleted id gets an edited copy with the id neutralised (scalar id fields
  -> -1; bare ids inside id lists -> removed; structured reference entries
  inside lists -> the entry is dropped).
* ``cascade=False`` with hard dependents present raises
  :class:`DependentsError` carrying the full report (fail loudly).

Modification model: the element's seq-102 object (and, when placement /
geometry changes, its seq-101 header bbox and seq-103 rep) is edited in
decoded-dict space, re-encoded byte-exactly by :mod:`rvt.encode` with the
record stamp recomputed (``adler32(u16 class + object)``), and spliced back
at the same position (record length may change; unit 0 is re-blocked).

Nothing here touches the save-history streams (History / increments /
BasicFileInfo): like ``commit.commit_new_elements`` this is a minimal
commit -- edited elements keep their existing episodes.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import math
import re
import struct
import zlib
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import ecc
from . import partitions as _P
from .cfb_writer import write_cfb
from .commit import PART_HDR_COUNT_OFF
from .container import open_rvt
from .encode import ObjectEncoder, record_stamp
from .objects import Record, iter_records
from .partitions import StreamWalker, record_header_len
from .roundtrip import read_entries
from .stream_encoders import decode_elemtable, encode_elemtable, global_prefix
from .versions import LATEST_RELEASE, framing_table
from .writer import gzip_member

# ---------------------------------------------------------------------------
# NOT read by this module: block tags come from rvt.partitions at CALL time
# (see _emit_block, #455 -- a by-value copy froze whatever release context the
# first import sat in).  Kept only as the at-rest 2026 handles that
# frontdoor.release_ctx and tools/genesis_* still getattr/setattr (inert).
_T26 = framing_table(LATEST_RELEASE)
BLOCK_TAG, TRAILER_TAG = _T26["BLOCK_TAG"], _T26["TRAILER_TAG"]

INVALID_ID = -1
OWNER_NONE_U64 = 0xFFFFFFFFFFFFFFFF
CLASS_SKETCH_PLANE = "SketchPlane"

#: block re-emission budget (inflated bytes); Revit's own blocks hover
#: around 128-131 KiB.  The reader walks the per-block ``B`` length, so
#: the exact budget is not load-bearing (dach Partitions/85 has 36-byte
#: blocks).
BLOCK_BUDGET = 131_072
_ISIZE_ADJ = {4: 0, 5: 4, 6: -4, 7: 0}

# built-in parameter ids observed in the 2026 corpus (BuiltInParameter)
BIP_ALL_MODEL_MARK = -1001203        # 'Mark' (AString) on instances
BIP_RBS_ELEC_PANEL_NAME = -1140078   # 'Panel Name' (AString) on panelboards
BIP_DOOR_NUMBER = -1005108            # 'Mark'-like door number
BIP_ALL_MODEL_TYPE_NAME = -1002001
BIP_ROOM_NAME = -1006900              # room / space name (AString)
BIP_ROOM_NUMBER = -1006901            # room / space number (AString)

# keys whose small integers are geometry topology tags / indices, never
# ElementIds (mirrors rvt.mutate._NOT_ELEMENT_ID)
_NOT_ELEMENT_ID = ("HistTable", "m_faceHist", "m_edgeHist", "m_GInfo",
                   "m_keys", "m_geomGeneratorId", "m_tag", "m_paramId",
                   "m_index", "m_GRepId", "m_gElemType", "m_penNumber",
                   "m_faceRegions", "m_nIndex", "m_nextMidParamId",
                   "m_hostPointId", "m_geomTag", "m_connType", "m_number",
                   "m_flags", "m_version", "m_id64",
                   # object-pointer bookkeeping (archive object indexes /
                   # weak references), never ElementIds
                   "pid", "weakref", "ptr_class")


# ===========================================================================
# errors
# ===========================================================================
class ManipulationError(Exception):
    """Base error for the manipulation layer."""


class DependentsError(ManipulationError):
    """delete_element(cascade=False) hit elements that depend on the target.

    ``.report`` is the DeletePlan-style dependency report (dependents,
    referrers) so the caller can show the user what a cascade would remove.
    """

    def __init__(self, elem_id: int, report: dict):
        self.elem_id = elem_id
        self.report = report
        deps = report.get("dependents", [])
        head = ", ".join(f"{d['id']}({d.get('class')})" for d in deps[:8])
        more = "" if len(deps) <= 8 else f" ... +{len(deps) - 8} more"
        super().__init__(
            f"element {elem_id} has {len(deps)} hard dependent(s) that a delete "
            f"would orphan: {head}{more}. Re-run with cascade=True to delete "
            f"them too (see report).")


# ===========================================================================
# plan data structures
# ===========================================================================
@dataclass
class RecordEdit:
    """One byte-level change to a save-unit-0 record."""
    seq: int              # 101 / 102 / 103
    elem_id: int
    action: str           # 'remove' | 'replace'
    new_record: Optional[bytes] = None   # framed record bytes for 'replace'
    reason: str = ""

    def to_json(self) -> dict:
        return {"seq": self.seq, "elem_id": self.elem_id, "action": self.action,
                "new_record_len": (len(self.new_record) if self.new_record else 0),
                "reason": self.reason}


@dataclass
class FieldChange:
    seq: int
    path: str
    before: Any
    after: Any

    def to_json(self) -> dict:
        return {"seq": self.seq, "path": self.path,
                "before": _jsonable(self.before), "after": _jsonable(self.after)}


@dataclass
class ModifyPlan:
    kind: str                       # 'modify' | 'move' | 'retype' | 'referrer-edit'
    elem_id: int
    class_name: Optional[str]
    changes: List[FieldChange] = dc_field(default_factory=list)
    record_edits: List[RecordEdit] = dc_field(default_factory=list)
    notes: List[str] = dc_field(default_factory=list)

    @property
    def edited_ids(self) -> List[int]:
        return sorted({e.elem_id for e in self.record_edits})

    def to_json(self) -> dict:
        return {"plan": "modify", "kind": self.kind, "elem_id": self.elem_id,
                "class": self.class_name,
                "changes": [c.to_json() for c in self.changes],
                "record_edits": [r.to_json() for r in self.record_edits],
                "notes": self.notes}


@dataclass
class DeletePlan:
    root_id: int
    cascade: bool
    ids_to_remove: List[int]                    # root + cascaded hard dependents
    dependents: List[dict]                      # hard dependents report
    referrer_edits: List[dict]                  # {id, class, seq, paths[]} neutralised
    record_edits: List[RecordEdit] = dc_field(default_factory=list)
    elemtable_remove: List[int] = dc_field(default_factory=list)
    warnings: List[str] = dc_field(default_factory=list)
    notes: List[str] = dc_field(default_factory=list)

    @property
    def edited_ids(self) -> List[int]:
        return sorted({e.elem_id for e in self.record_edits if e.action == "replace"})

    def to_json(self) -> dict:
        return {"plan": "delete", "root_id": self.root_id, "cascade": self.cascade,
                "ids_to_remove": self.ids_to_remove,
                "dependents": self.dependents,
                "referrer_edits": self.referrer_edits,
                "record_edits": [r.to_json() for r in self.record_edits],
                "elemtable_remove": self.elemtable_remove,
                "warnings": self.warnings, "notes": self.notes}


Plan = Any  # DeletePlan | ModifyPlan


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        return repr(v)


# ===========================================================================
# session: working copies of decoded objects (edits accumulate)
# ===========================================================================
class EditSession:
    """Per-Document edit state: decoded working copies + the encoder.

    Every manipulation edits the SAME working copy of a record, so several
    plans against one element (move + rename + ...) compose; each plan's
    ``RecordEdit`` is re-serialised from the working copy at plan time and
    :func:`commit_plans` keeps the LAST replacement per (seq, elem_id).
    """

    def __init__(self, doc):
        self.doc = doc
        self.enc = ObjectEncoder(decoder=doc.dec)
        self.work: Dict[Tuple[int, int], dict] = {}       # (eid, seq) -> value dict
        self.removed: set = set()
        self.plans: List[Plan] = []

    # -- decoded access ------------------------------------------------------
    def record(self, eid: int, seq: int) -> Record:
        r = self.doc.idx[seq].get(eid)
        if r is None:
            raise ManipulationError(f"element {eid} has no seq-{seq} record")
        return r

    def decoded(self, eid: int, seq: int):
        """The DecodedObject for (eid, seq); raises if it is not re-encodable."""
        r = self.record(eid, seq)
        o = self.doc.dec.decode_record(r.class_id, r.payload)
        if not (o.clean or o.stub):
            raise ManipulationError(
                f"element {eid} seq {seq} ({o.class_name}) does not decode cleanly "
                f"({len(o.errors)} errors, {o.consumed}/{o.total} bytes) -- refusing to "
                f"re-encode a lossy object")
        return o

    def value(self, eid: int, seq: int) -> dict:
        """Mutable working copy of the element's decoded object for ``seq``."""
        key = (eid, seq)
        if key not in self.work:
            o = self.decoded(eid, seq)
            self.work[key] = copy.deepcopy(o.value)
            self._orig_bytes_check(eid, seq, o)
        return self.work[key]

    def _orig_bytes_check(self, eid: int, seq: int, o) -> None:
        """Prove the UNEDITED object re-encodes byte-exact before we edit it."""
        r = self.record(eid, seq)
        got = self.enc.encode_object(r.class_id, o.value)
        if got != r.payload:
            n = _first_divergence(got, r.payload)
            raise ManipulationError(
                f"element {eid} seq {seq} ({o.class_name}) does not round-trip "
                f"byte-exact (diverges at object byte {n}, {len(got)} vs "
                f"{len(r.payload)}) -- refusing to edit it")

    # -- serialisation -------------------------------------------------------
    def frame(self, seq: int, eid: int, class_id: int, value: dict) -> bytes:
        """Framed record bytes: header + u16 class + object + u32 size repeat."""
        body = self.enc.encode_object(class_id, value or {})
        ps = 2 + len(body)
        payload = struct.pack("<H", class_id) + body
        if seq == 101:
            hdr = struct.pack("<qI", eid, ps)
        else:
            stamp = zlib.adler32(payload) & 0xFFFFFFFF
            hdr = struct.pack("<qII", eid, stamp, ps)
        return hdr + payload + struct.pack("<I", ps)

    def replacement(self, eid: int, seq: int, reason: str = "") -> RecordEdit:
        """RecordEdit that replaces (eid, seq) with the current working copy."""
        r = self.record(eid, seq)
        val = self.value(eid, seq)
        return RecordEdit(seq, eid, "replace", self.frame(seq, eid, r.class_id, val),
                          reason)


def _first_divergence(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n if len(a) != len(b) else -1


def session(doc) -> EditSession:
    """The (lazily created) EditSession attached to a Document."""
    s = getattr(doc, "_manip_session", None)
    if s is None:
        s = EditSession(doc)
        doc._manip_session = s
    return s


def source_path(doc) -> str:
    sp = getattr(doc, "source_path", None)
    if not sp:
        raise ManipulationError("Document has no source_path -- load it with "
                                "Document.from_file(path) to commit edits")
    return sp


# ===========================================================================
# json-path get/set over decoded value dicts
# ===========================================================================
_PATH_TOKEN = re.compile(r"\.?([^.\[\]]+)|\[(-?\d+)\]")


def _parse_path(path: str) -> List[Any]:
    toks: List[Any] = []
    pos = 0
    while pos < len(path):
        m = _PATH_TOKEN.match(path, pos)
        if not m:
            raise ManipulationError(f"bad json path {path!r} at {pos}")
        if m.group(1) is not None:
            toks.append(m.group(1))
        else:
            toks.append(int(m.group(2)))
        pos = m.end()
    return toks


def get_path(value: Any, path: str) -> Any:
    cur = value
    for t in _parse_path(path):
        if isinstance(t, int):
            cur = cur[t]
        else:
            cur = cur[t]
    return cur


def set_path(value: Any, path: str, new) -> Any:
    """Set ``value[path] = new``; returns the previous value."""
    toks = _parse_path(path)
    if not toks:
        raise ManipulationError("empty path")
    cur = value
    for t in toks[:-1]:
        cur = cur[t]
    last = toks[-1]
    old = cur[last]
    cur[last] = new
    return old


# ===========================================================================
# reference / dependency analysis
# ===========================================================================
def _norm_owner(v: int) -> int:
    return INVALID_ID if v in (INVALID_ID, OWNER_NONE_U64, None) else int(v)


def _find_id_paths(v, targets: set, path: str = "", out: Optional[list] = None,
                   skip=_NOT_ELEMENT_ID) -> list:
    """Every (path, id) occurrence of an id in ``targets`` inside a decoded tree,
    ignoring keys known to hold non-ElementId integers."""
    if out is None:
        out = []
    if isinstance(v, dict):
        for k, x in v.items():
            if k in skip:
                continue
            p = f"{path}.{k}" if path else k
            if isinstance(x, int) and not isinstance(x, bool):
                if x in targets:
                    out.append((p, x))
            else:
                _find_id_paths(x, targets, p, out, skip)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            p = f"{path}[{i}]"
            if isinstance(x, int) and not isinstance(x, bool):
                if x in targets:
                    out.append((p, x))
            else:
                _find_id_paths(x, targets, p, out, skip)
    return out


def _le_id_patterns(ids: Iterable[int]) -> List[bytes]:
    return [struct.pack("<q", i) for i in ids]


def _ref_index(doc) -> Dict[int, tuple]:
    """Per-seq byte haystack over the HOST-document records only.

    Built once per Document (cached): {seq: (bytes, [(start, end, eid)...])}
    so that ``candidate_referrers`` costs one ``bytes.find`` sweep per target
    id instead of an O(records x targets) python loop (rme host records:
    6.5/46/38 MB per seq -- a find sweep is ~10 ms).  Embedded-family
    records are excluded: they cannot reference host-document elements.
    """
    idx = getattr(doc, "_manip_refindex", None)
    if idx is not None:
        return idx
    idx = {}
    host = doc.et_by_id
    for seq in (101, 102, 103):
        buf = bytearray()
        spans = []
        for eid, rec in doc.idx[seq].items():
            if eid not in host:
                continue
            start = len(buf)
            buf += rec.payload
            buf += b"\x00" * 8              # separator (matches must sit inside a record)
            spans.append((start, start + len(rec.payload), eid))
        idx[seq] = (bytes(buf), spans, [s[0] for s in spans])
    doc._manip_refindex = idx
    return idx


def candidate_referrers(doc, target_ids: Iterable[int],
                        seqs: Sequence[int] = (101, 102, 103)) -> Dict[int, set]:
    """Byte-level prefilter: host-document elements whose record bytes contain
    the little-endian i64 of any target id.  Returns {eid: {seq,...}}.
    False positives (an id's byte pattern inside a double / string) are
    weeded out later by decoding; false negatives are impossible for the
    flattened i64 ElementId encoding."""
    import bisect
    pats = _le_id_patterns(target_ids)
    targets = set(target_ids)
    out: Dict[int, set] = {}
    idx = _ref_index(doc)
    for seq in seqs:
        buf, spans, starts = idx[seq]
        for p in pats:
            pos = buf.find(p)
            while pos != -1:
                i = bisect.bisect_right(starts, pos) - 1
                if i >= 0:
                    s0, s1, eid = spans[i]
                    if pos + 8 <= s1 and eid not in targets:
                        out.setdefault(eid, set()).add(seq)
                    pos = buf.find(p, s1 if pos + 8 <= s1 else pos + 1)
                else:
                    pos = buf.find(p, pos + 1)
    return out


def referrers(doc, target_ids: Iterable[int]) -> Dict[int, dict]:
    """Decoded reference map: {referrer_id: {'class', 'refs': {seq: [(path,id)]}}}."""
    targets = set(target_ids)
    out: Dict[int, dict] = {}
    for eid, seqs in candidate_referrers(doc, targets).items():
        entry = {"class": doc.class_of(eid), "refs": {}}
        for seq in sorted(seqs):
            o = doc.decode(eid, seq)
            if o is None:
                continue
            paths = _find_id_paths(o.value, targets)
            if paths:
                entry["refs"][seq] = paths
        if entry["refs"]:
            out[eid] = entry
    return out


def owned_children(doc, target_ids: Iterable[int]) -> List[int]:
    """ElemTable-owned children: rows whose m_OwningElementId is a target."""
    t = set(target_ids)
    return [r.id for r in doc.et.records if _norm_owner(r.owner_id) in t]


def _obj_get(v: dict, key: str, default=None):
    if not isinstance(v, dict):
        return default
    return v.get(key, default)


def _is_hosted_on(obj: dict, targets: set) -> Optional[str]:
    """Does this element STRUCTURALLY host on a target? Returns the field."""
    if not isinstance(obj, dict):
        return None
    for f in ("m_hostId", "m_hostObjId", "m_pHostId"):
        if _obj_get(obj, f) in targets:
            return f
    for f in ("m_extraHostIds", "m_explicitHostIds"):
        lst = _obj_get(obj, f)
        if isinstance(lst, list) and any(isinstance(x, int) and x in targets for x in lst):
            return f
    # SketchPlane lying on a target's face
    pr = _obj_get(obj, "m_oPlaneRef")
    prv = pr.get("value") if isinstance(pr, dict) else None
    if isinstance(prv, dict):
        gr = prv.get("m_geomRef")
        if isinstance(gr, dict) and gr.get("m_elemId") in targets:
            return "m_oPlaneRef.m_geomRef.m_elemId"
    return None


def _deletion_parents(header_value: dict) -> List[int]:
    par = _obj_get(header_value, "m_parents")
    parv = par.get("value") if isinstance(par, dict) else None
    dele = parv.get("m_deletion") if isinstance(parv, dict) else None
    return [x for x in dele if isinstance(x, int)] if isinstance(dele, list) else []


#: classes whose ``m_deletion`` mention of a peer means "regenerate me"
#: rather than "delete me" (joined walls, bounded rooms/spaces, area/room
#: plan topology, curve elements, MEP systems / networks / connected
#: curves and their fittings): these are NEUTRALISED, never cascaded.
#: Evidence: deleting an air terminal (rme 379463) via a naive
#: deletion-parent cascade reaches the whole duct network (2,300+ elements)
#: through RbsHvacSystem -> its members -> their systems; Revit instead
#: removes the element from the system and leaves the network in place.
_PEER_CLASSES = {
    "SWall", "VWall", "Wall", "RoomElem", "SpaceElem", "AreaElem", "ZoneElem",
    "LevelRoomPlan", "CurveElem", "MEPCurveElem", "Grid", "Level",
    "RbsElectricalSystem", "RbsSystem", "RbsHvacSystem", "RbsPipingSystem",
    "RbsDuctSystem", "MEPSystem", "MEPNetworkDataElem", "MEPAnalyticalNetwork",
    "RbsDuctCurve", "RbsFlexDuctCurve", "RbsPipeCurve", "RbsFlexPipeCurve",
    "RbsWireCurve", "CableTray", "Conduit", "ConduitRun", "CableTrayRun",
}


def _is_peer_class(name: Optional[str]) -> bool:
    """Class-name test for the peer relation (regenerate, don't cascade)."""
    if not name:
        return False
    if name in _PEER_CLASSES:
        return True
    for suffix in ("System", "SystemZone", "Network", "NetworkData",
                   "Sketch"):
        if name.endswith(suffix):
            return True
    return False


#: classes for which a ``m_deletion`` mention of X really means "delete me
#: with X" (annotation / leaf dependents): tags, dimensions, warnings, and
#: an element's own schedule view.  Evidence (racadv wall 144180): windows
#: hosted on the NEIGHBOURING wall 139857 list 144180 in ``m_deletion`` --
#: a join / constraint mention, not ownership -- so ``m_deletion`` is NOT a
#: hard-dependency signal for hosts, instances, sketches or systems; those
#: rely on the structural relations (m_hostId, ownership) instead and any
#: leftover mention is neutralised.
_ANNOTATION_DEP_SUFFIXES = ("Tag", "DimString", "Dimension", "SpotElev",
                            "SpotCoord", "SpotSlope")
_ANNOTATION_DEP_CLASSES = {"PostedWarningElem", "PanelScheduleView",
                           "MultiSegmentGrid", "Opening", "InsertOpening",
                           "RectOpening", "ArcOpening"}


def _honors_deletion_parents(name: Optional[str]) -> bool:
    """True for leaf/annotation classes whose ``m_deletion`` mention of a
    target genuinely makes them a delete-with dependent."""
    if not name:
        return False
    if name in _ANNOTATION_DEP_CLASSES:
        return True
    return name.endswith(_ANNOTATION_DEP_SUFFIXES)


def dependents_of(doc, target_ids: Iterable[int]) -> Dict[int, dict]:
    """HARD dependents of the targets (elements a cascade must delete).

    dependents(X) =
      * elements STRUCTURALLY hosted on X (m_hostId / extra / explicit hosts,
        SketchPlanes on X's faces);
      * ElemTable-owned children (m_OwningElementId == X) and object-owned
        elements (m_ownerElemId / m_famId / m_symbolFamilyId == X);
      * ANNOTATION / leaf classes (tags, dimensions, warnings, an element's
        own schedule view) whose header ``m_deletion`` names X.
    Every other ``m_deletion`` mention (joined walls, rooms, plans, curves,
    sketches, systems, neighbouring hosts' inserts) is a regenerate/constraint
    peer relation and is neutralised, never cascaded -- Revit's
    deletion-parents list mixes both meanings.
    Returns {dependent_id: {class, relation, via}}.
    """
    targets = set(target_ids)
    out: Dict[int, dict] = {}
    # owned children (ElemTable)
    for cid in owned_children(doc, targets):
        if cid not in targets:
            out[cid] = {"class": doc.class_of(cid), "relation": "owned-child",
                        "via": "ElemRec.m_OwningElementId"}
    # structural hosting + deletion-parents, over byte-search candidates
    cands = candidate_referrers(doc, targets, seqs=(101, 102))
    for eid, seqs in cands.items():
        if eid in targets or eid in out:
            continue
        cls = doc.class_of(eid) or ""
        obj = doc.value(eid, 102) if 102 in seqs else doc.value(eid, 102)
        via = _is_hosted_on(obj or {}, targets)
        if via:
            out[eid] = {"class": cls, "relation": "hosted", "via": via}
            continue
        # object ownership fields (family-owned params, sub-elements)
        if isinstance(obj, dict):
            for f in ("m_ownerElemId", "m_famId", "m_symbolFamilyId",
                      "m_superInstanceId"):
                if obj.get(f) in targets:
                    out[eid] = {"class": cls, "relation": "owned", "via": f}
                    break
            if eid in out:
                continue
            # level association: deleting a Level deletes the elements placed
            # on it and its plan views (Revit); constraint-only references
            # (m_upToLevelId top constraints) are neutralised instead.
            for f in ("m_assocLevelId", "m_levelId", "m_genLevelId"):
                if obj.get(f) in targets:
                    out[eid] = {"class": cls, "relation": "associated-level",
                                "via": f}
                    break
            if eid in out:
                continue
        if 101 in seqs and _honors_deletion_parents(cls) and not _is_peer_class(cls):
            h = doc.decode(eid, 101)
            if h is not None and (h.clean or h.stub):
                dele = _deletion_parents(h.value)
                if any(x in targets for x in dele):
                    out[eid] = {"class": cls, "relation": "deletion-parent",
                                "via": "ElementHeader.m_parents.m_deletion"}
    return out


# ===========================================================================
# neutralising a referrer (remove every mention of the deleted ids)
# ===========================================================================
def _neutralise(v, targets: set, path: str = "", edits: Optional[list] = None,
                skip=_NOT_ELEMENT_ID) -> list:
    """Mutate ``v`` in place removing every reference to a target id.

    Rules (applied recursively):
      * a scalar id field inside a dict            -> set to -1;
      * a bare id inside a list of ids            -> removed from the list;
      * a structured entry inside a list (a dict, or a nested list) that
        mentions a target anywhere              -> the whole entry is dropped
        (join records, plan-topology segments, connector ref entries, ...).
    Returns the list of {path, action, before} edits performed.
    """
    if edits is None:
        edits = []
    if isinstance(v, dict):
        for k, x in list(v.items()):
            if k in skip:
                continue
            p = f"{path}.{k}" if path else k
            if isinstance(x, int) and not isinstance(x, bool):
                if x in targets:
                    v[k] = INVALID_ID
                    edits.append({"path": p, "action": "set-invalid", "before": x})
            elif isinstance(x, list):
                _neutralise_list(x, targets, p, edits, skip)
            else:
                _neutralise(x, targets, p, edits, skip)
    elif isinstance(v, list):
        _neutralise_list(v, targets, path, edits, skip)
    return edits


def _mentions(v, targets: set, skip=_NOT_ELEMENT_ID) -> bool:
    return bool(_find_id_paths(v, targets, "", [], skip)) if not (
        isinstance(v, int) and not isinstance(v, bool)) else (v in targets)


def _neutralise_list(lst: list, targets: set, path: str, edits: list, skip):
    keep = []
    changed = False
    for i, x in enumerate(lst):
        p = f"{path}[{i}]"
        if isinstance(x, int) and not isinstance(x, bool):
            if x in targets:
                edits.append({"path": p, "action": "remove-id", "before": x})
                changed = True
                continue
            keep.append(x)
        elif isinstance(x, (dict, list)):
            if _mentions(x, targets, skip):
                if isinstance(x, dict) and ("ptr_class" in x or "pid" in x):
                    # a pointed-to sub-object (Connector, DuctSection, ...):
                    # dropping it would shift positional back-references
                    # (Connector m_nIndex) held by OTHER elements -- keep the
                    # object and neutralise INSIDE it (its ref entries drop).
                    _neutralise(x, targets, p, edits, skip)
                    keep.append(x)
                    continue
                edits.append({"path": p, "action": "drop-entry",
                              "before": _brief(x)})
                changed = True
                continue
            keep.append(x)
        else:
            keep.append(x)
    if changed:
        lst[:] = keep


def _brief(x, n: int = 120) -> str:
    try:
        s = json.dumps(x, default=str)
    except Exception:
        s = repr(x)
    return s if len(s) <= n else s[:n] + "..."


# ===========================================================================
# DELETE
# ===========================================================================
def dependency_report(doc, eid: int, *, max_depth: int = 8,
                      max_cascade: int = 2000) -> dict:
    """The full picture for deleting ``eid``: cascade closure + referrers.

    Does not mutate anything.  ``report['dependents']`` is the ordered list
    of HARD dependents (with the depth at which the cascade reached them);
    ``report['referrers']`` are the soft referrers that would be neutralised.
    The closure expansion stops (loudly, ``truncated``) at ``max_depth``
    levels or ``max_cascade`` elements -- a runaway cascade is a modelling
    signal (a peer relation misread as a dependency), never a delete to run.
    """
    if not doc.in_host_document(eid):
        raise ManipulationError(f"element {eid} is not a host-document element "
                                "(not in Global/ElemTable) -- cannot delete")
    closure: Dict[int, dict] = {eid: {"depth": 0, "class": doc.class_of(eid),
                                      "relation": "target"}}
    frontier = [eid]
    depth = 0
    truncated = False
    capped = False
    while frontier and depth < max_depth:
        depth += 1
        found = dependents_of(doc, frontier)
        frontier = []
        for cid, info in found.items():
            if cid in closure:
                continue
            closure[cid] = {"depth": depth, **info}
            frontier.append(cid)
        if len(closure) > max_cascade:
            capped = True
            break
    if frontier and not capped:
        truncated = True
    ids = set(closure)
    refs = referrers(doc, ids)
    soft = {k: v for k, v in refs.items() if k not in ids}
    return {
        "target": eid,
        "target_class": doc.class_of(eid),
        "dependents": [{"id": k, **v} for k, v in
                       sorted(closure.items(), key=lambda kv: (kv[1]["depth"], kv[0]))
                       if k != eid],
        "cascade_ids": sorted(ids),
        "referrers": [{"id": k, "class": v["class"],
                       "paths": {str(s): [p for p, _ in ps] for s, ps in v["refs"].items()}}
                      for k, v in sorted(soft.items())],
        "truncated_at_depth": max_depth if truncated else None,
        "cascade_capped_at": max_cascade if capped else None,
    }


def delete_element(doc, eid: int, *, cascade: bool = False, max_depth: int = 8,
                   neutralise_referrers: bool = True) -> DeletePlan:
    """Plan the deletion of host-document element ``eid``.

    ``cascade=False`` (default) refuses to orphan anything: if any HARD
    dependent exists it raises :class:`DependentsError` whose ``.report``
    lists them (and the soft referrers).  ``cascade=True`` deletes the
    whole hard-dependency closure (bounded by ``max_depth``) and neutralises
    every remaining referrer.  The returned plan carries the record removals,
    the referrer replacement records and the ElemTable ids to drop.
    """
    rep = dependency_report(doc, eid, max_depth=max_depth)
    if rep["dependents"] and not cascade:
        raise DependentsError(eid, rep)
    if rep.get("cascade_capped_at"):
        raise ManipulationError(
            f"element {eid}: cascade exceeded {rep['cascade_capped_at']} elements "
            f"-- refusing to delete a runaway closure (a peer relation is being "
            f"read as a dependency; see report)")
    ids = rep["cascade_ids"] if cascade else [eid]
    idset = set(ids)
    sess = session(doc)
    plan = DeletePlan(root_id=eid, cascade=cascade, ids_to_remove=sorted(ids),
                      dependents=rep["dependents"], referrer_edits=[],
                      elemtable_remove=sorted(ids))
    if rep.get("truncated_at_depth"):
        plan.warnings.append(f"cascade truncated at depth {max_depth}")
    # 1. remove the three records of every deleted element
    for did in sorted(ids):
        for seq in (101, 102, 103):
            if doc.idx[seq].get(did) is not None:
                plan.record_edits.append(RecordEdit(seq, did, "remove", None,
                                                    "element deleted"))
        sess.removed.add(did)
    # 2. neutralise soft referrers (elements outside the closure)
    if neutralise_referrers:
        refs = referrers(doc, idset)
        for rid in sorted(refs):
            if rid in idset:
                continue
            info = refs[rid]
            entry = {"id": rid, "class": info["class"], "edits": {}}
            for seq in sorted(info["refs"]):
                try:
                    val = sess.value(rid, seq)
                except ManipulationError as e:
                    plan.warnings.append(f"referrer {rid} seq {seq}: {e} (left as-is)")
                    continue
                ed = _neutralise(val, idset)
                if not ed:
                    continue
                entry["edits"][str(seq)] = ed
                plan.record_edits.append(sess.replacement(
                    rid, seq, f"neutralise reference(s) to deleted {sorted(idset)[:4]}"))
            if entry["edits"]:
                plan.referrer_edits.append(entry)
    plan.notes.append(
        f"deleting {len(ids)} element(s): {sorted(ids)}; "
        f"{len(plan.referrer_edits)} referrer element(s) neutralised; "
        f"ElemTable count -= {len(ids)}, id watermark unchanged")
    sess.plans.append(plan)
    return plan


# ===========================================================================
# MODIFY
# ===========================================================================
def modify_element(doc, eid: int, changes: Dict[str, Any], *, seq: int = 102,
                   kind: str = "modify", reason: str = "") -> ModifyPlan:
    """Set fields of an existing element's decoded object by JSON path.

    ``changes`` maps a path into the decoded seq-``seq`` value dict (dotted
    keys, ``[i]`` list indexes, e.g. ``"m_pSurface.value.m_origin[2]"``)
    to its new value.  The record is re-encoded byte-exact with a fresh
    stamp; the containing block is re-emitted at commit time.
    """
    if not doc.in_host_document(eid):
        raise ManipulationError(f"element {eid} is not a host-document element")
    sess = session(doc)
    val = sess.value(eid, seq)
    plan = ModifyPlan(kind=kind, elem_id=eid, class_name=doc.class_of(eid, seq))
    for path, new in changes.items():
        try:
            old = set_path(val, path, new)
        except (KeyError, IndexError, TypeError) as e:
            raise ManipulationError(
                f"element {eid} seq {seq}: cannot set {path!r}: {e!r}") from None
        plan.changes.append(FieldChange(seq, path, old, copy.deepcopy(new)))
    plan.record_edits.append(sess.replacement(eid, seq, reason or f"{kind}: {sorted(changes)}"))
    sess.plans.append(plan)
    return plan


#: Element param-value holders: field -> owned-pointer class (corpus shape:
#: ``{"ptr_class": cls, "pid": -1, "value": {"m_paramSet": [{"m_paramId",
#: "m_value"}, ...]}}`` -- e.g. BasicWallType 600634 / DBViewPlan 245443 /
#: LeaderStyle 1471069 / Viewer 1457029 on the composed 2026 base).
PARAM_HOLDERS = {"m_pParamValueSetDouble": "ParamValueSetDouble",
                 "m_pParamValueSetInt": "ParamValueSetInt",
                 "m_pParamValueSetAString": "ParamValueSetAString",
                 "m_pParamValueSetElementId": "ParamValueSetElementId"}

#: python coercion of ``m_value`` per holder (ElementId / Int rows are ints)
_HOLDER_VALUE_TYPE = {"m_pParamValueSetAString": str, "m_pParamValueSetDouble": float}


def _coerce_value(holder: str, value):
    """``value`` as the holder stores it when MODIFYING a row (text / double
    coerced; Int / ElementId left as given -- a new row's int() happens in
    :func:`param_row_edit`)."""
    coerce = _HOLDER_VALUE_TYPE.get(holder)
    return coerce(value) if coerce else value

#: built-in parameters whose holder is known whatever python type the value
#: arrives as (a Mark or room number of 7 is still text): id -> holder
KNOWN_PARAM_HOLDERS = {pid: "m_pParamValueSetAString" for pid in (
    BIP_ALL_MODEL_MARK, BIP_RBS_ELEC_PANEL_NAME, BIP_DOOR_NUMBER,
    BIP_ALL_MODEL_TYPE_NAME, BIP_ROOM_NAME, BIP_ROOM_NUMBER)}


def param_holder_for(param_id: int, value) -> str:
    """Which ParamValueSet holder a NEW row for ``param_id`` = ``value``
    belongs to: :data:`KNOWN_PARAM_HOLDERS` first, otherwise by value type
    (str -> AString, float -> Double, bool/int -> Int; pass an ElementId
    row explicitly with ``holder=`` -- a bare int is indistinguishable)."""
    known = KNOWN_PARAM_HOLDERS.get(param_id)
    if known:
        return known
    if isinstance(value, str):
        return "m_pParamValueSetAString"
    if isinstance(value, float):
        return "m_pParamValueSetDouble"
    return "m_pParamValueSetInt"


def _param_rows(val: dict, holder: str) -> Optional[list]:
    """The ``m_paramSet`` row list of ``val[holder]``, or None if the holder
    pointer is null / absent."""
    h = val.get(holder)
    rows = ((h.get("value") or {}).get("m_paramSet")) if isinstance(h, dict) else None
    return rows if isinstance(rows, list) else None


def param_row_edit(val: dict, param_id: int, value, *,
                   holder: Optional[str] = None) -> Tuple[str, Any, str]:
    """The ONE edit that inserts an absent ``{m_paramId, m_value}`` row into
    an Element object ``val``: ``(json_path, new_value, note)`` -- either the
    holder's row list with the row appended, or, when the holder pointer is
    null, the whole authored holder object (:data:`PARAM_HOLDERS` shape).
    Pure: apply it with :func:`set_path` (raw dicts at create time) or
    :func:`modify_element` (committed elements)."""
    holder = holder or param_holder_for(param_id, value)
    if holder not in PARAM_HOLDERS:
        raise ManipulationError(f"unknown param holder {holder!r} "
                                f"(expected one of {sorted(PARAM_HOLDERS)})")
    if holder not in val:
        raise ManipulationError(f"parameter {param_id} not present and the object "
                                f"has no {holder} field to insert it into")
    row = {"m_paramId": param_id,
           "m_value": _HOLDER_VALUE_TYPE.get(holder, int)(value)}
    rows = _param_rows(val, holder)
    if rows is not None:
        return (f"{holder}.value.m_paramSet", rows + [row],
                f"inserted parameter {param_id} row into existing {holder}")
    return (holder, {"ptr_class": PARAM_HOLDERS[holder], "pid": -1,
                     "value": {"m_paramSet": [row]}},
            f"authored {PARAM_HOLDERS[holder]} holder for absent parameter {param_id}")


def upsert_param_row(val: dict, param_id: int, value, *,
                     holder: Optional[str] = None) -> str:
    """Set ``param_id`` = ``value`` in ONE holder of a raw Element object
    ``val`` (a dict being built at create time -- :mod:`rvt.mep`,
    :meth:`rvt.mutate.Document._set_param`): the holder's existing row is
    modified in place, an absent one is inserted with :func:`param_row_edit`
    + :func:`set_path` (authoring the holder when its pointer is null --
    never a silent no-op).  Returns what it did.  Committed elements go
    through :func:`set_param` instead (same shape, recorded as a plan)."""
    holder = holder or param_holder_for(param_id, value)
    for row in _param_rows(val, holder) or ():
        if isinstance(row, dict) and row.get("m_paramId") == param_id:
            row["m_value"] = _coerce_value(holder, value)
            return f"set parameter {param_id} row in {holder}"
    path, new, note = param_row_edit(val, param_id, value, holder=holder)
    set_path(val, path, new)
    return note


def find_param(val: dict, param_id: int) -> List[Tuple[str, int]]:
    """Locate a parameter by BuiltInParameter / shared-param id inside an
    element's decoded object.  Returns [(container_path, index), ...] for
    Element param-value sets and FamilyInstance ``m_pInstParams``."""
    hits = []
    for holder in PARAM_HOLDERS:
        for i, p in enumerate(_param_rows(val, holder) or ()):
            if isinstance(p, dict) and p.get("m_paramId") == param_id:
                hits.append((f"{holder}.value.m_paramSet", i))
    h = val.get("m_pInstParams")
    params = ((h or {}).get("value") or {}).get("m_params") if isinstance(h, dict) else None
    if isinstance(params, list):
        for i, p in enumerate(params):
            if isinstance(p, dict) and p.get("m_paramId") == param_id:
                hits.append(("m_pInstParams.value.m_params", i))
    return hits


def set_param(doc, eid: int, param_id: int, value, *, seq: int = 102,
              holder: Optional[str] = None) -> ModifyPlan:
    """Set a parameter (built-in negative id or a project parameter
    ElementId) on an element -- e.g. the panel name
    (``BIP_RBS_ELEC_PANEL_NAME``) or the Mark (``BIP_ALL_MODEL_MARK``).

    UPSERT: an existing row (in any Element param-value set or the
    FamilyInstance ``m_pInstParams``) is modified in place -- never
    duplicated; an ABSENT row is appended to the holder it belongs to
    (:func:`param_holder_for`, or ``holder=`` explicitly), authoring the
    holder object itself when the element's pointer is null (instances we
    place carry all four holders null).  The row / holder shape is the
    corpus-observed one (:data:`PARAM_HOLDERS`); nothing is copied.

    Element param sets store ``m_value``; FamilyParams entries store
    ``m_str`` (text) / ``m_value`` (double) / ``m_int`` / ``m_elemId``.
    """
    sess = session(doc)
    val = sess.value(eid, seq)
    hits = find_param(val, param_id)
    if not hits:
        try:
            path, new, note = param_row_edit(val, param_id, value, holder=holder)
        except ManipulationError as e:
            raise ManipulationError(f"element {eid} ({doc.class_of(eid, seq)}): {e}") from None
        plan = modify_element(doc, eid, {path: new}, seq=seq, kind="set-param",
                              reason=f"insert parameter {param_id} = {value!r}")
        plan.notes.append(note)
        return plan
    changes = {}
    for cont, idx in hits:
        if cont == "m_pInstParams.value.m_params":
            if isinstance(value, str):
                changes[f"{cont}[{idx}].m_str"] = value
            elif isinstance(value, bool) or isinstance(value, int):
                changes[f"{cont}[{idx}].m_int"] = int(value)
            elif isinstance(value, float):
                changes[f"{cont}[{idx}].m_value"] = float(value)
            else:
                changes[f"{cont}[{idx}].m_elemId"] = value
        else:
            changes[f"{cont}[{idx}].m_value"] = _coerce_value(cont.split(".", 1)[0], value)
    return modify_element(doc, eid, changes, seq=seq, kind="set-param",
                          reason=f"set parameter {param_id} = {value!r}")


def rename_panel(doc, eid: int, name: str) -> ModifyPlan:
    """Rename an electrical panelboard: its 'Panel Name' built-in
    parameter (``BIP_RBS_ELEC_PANEL_NAME``)."""
    return set_param(doc, eid, BIP_RBS_ELEC_PANEL_NAME, name)


def set_mark(doc, eid: int, mark: str) -> ModifyPlan:
    """Set an instance's 'Mark' (``BIP_ALL_MODEL_MARK``)."""
    return set_param(doc, eid, BIP_ALL_MODEL_MARK, mark)


def set_level_elevation(doc, level_id: int, elevation_ft: float) -> ModifyPlan:
    """Move a Level datum to ``elevation_ft`` (project feet).

    A Level's elevation is stored twice in its object -- the datum surface
    ``m_pSurface`` (a ``Plane`` origin) and the display face
    ``m_pFace -> Face.m_pSurf`` -- both origin z components are patched.
    Elements associated with the level are moved by Revit on regeneration.
    """
    if (doc.class_of(level_id) or "") != "Level":
        raise ManipulationError(f"element {level_id} is a "
                                f"{doc.class_of(level_id)!r}, not a Level")
    sess = session(doc)
    val = sess.value(level_id, 102)
    changes = {}
    for path in ("m_pSurface.value.m_origin", "m_pFace.value.m_pSurf.value.m_origin"):
        try:
            org = get_path(val, path)
        except Exception:
            continue
        if isinstance(org, list) and len(org) == 3:
            changes[f"{path}[2]"] = float(elevation_ft)
    if not changes:
        raise ManipulationError(f"level {level_id}: no datum plane origin found")
    return modify_element(doc, level_id, changes, kind="level-elevation",
                          reason=f"level elevation -> {elevation_ft} ft")


# ===========================================================================
# MOVE / RETYPE an instance
# ===========================================================================
def _instance_info(val: dict) -> dict:
    ii = (val.get("m_pInstanceInfo") or {})
    ii = ii.get("value") if isinstance(ii, dict) else None
    if not isinstance(ii, dict):
        raise ManipulationError("element has no InstanceInfo (not a placed instance)")
    return ii


def instance_placement(doc, eid: int) -> dict:
    """Current placement of a FamilyInstance: origin (ft) + 3x3 rotation."""
    val = doc.value(eid, 102) or {}
    ii = _instance_info(val)
    trf = ii.get("m_Trf") or {}
    return {"m_or": list(trf.get("m_or") or [0.0, 0.0, 0.0]),
            "m_3x3": [list(r) for r in (trf.get("m_3x3") or [])],
            "m_symbolId": ii.get("m_symbolId"),
            "m_masterSymbolId": val.get("m_masterSymbolId"),
            "m_hostId": val.get("m_hostId")}


def _rot_z(theta: float):
    c, s = math.cos(theta), math.sin(theta)
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


def _matmul3(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def _shift_box(box, delta):
    """Translate a [[min],[max]] (or list-of-points) box by delta."""
    if not (isinstance(box, list) and box and isinstance(box[0], list)):
        return box
    return [[p[i] + delta[i] for i in range(min(len(p), 3))] + p[3:] for p in box]


def move_instance(doc, eid: int, new_xyz_ft, rotation: Optional[float] = None,
                  *, delta: bool = False,
                  include_owned: bool = True) -> ModifyPlan:
    """Move (and optionally rotate) a placed FamilyInstance.

    ``new_xyz_ft`` is the new placement origin ``m_Trf.m_or`` in feet, or a
    translation when ``delta=True``.  ``rotation`` (radians about +Z) is
    COMPOSED with the existing orientation when given.  Every place the
    placement is cached is rewritten consistently: the object's
    ``InstanceInfo.m_Trf``, the seq-103 rep's ``GInstance`` transforms and
    bounding boxes, and the seq-101 header outline (translated by the same
    vector) -- exactly the fields ``add_family_instance`` sets on creation.

    ``include_owned`` (default) also translates the instance's ElemTable-owned
    child instances (nested / sub-instances such as a table's chairs) by the
    same vector so the assembly moves rigidly; each child gets its own plan.
    """
    if not doc.in_host_document(eid):
        raise ManipulationError(f"element {eid} is not a host-document element")
    sess = session(doc)
    val = sess.value(eid, 102)
    ii = _instance_info(val)
    trf = ii.setdefault("m_Trf", {"m_3x3": _rot_z(0.0), "m_or": [0.0, 0.0, 0.0]})
    old_or = list(trf.get("m_or") or [0.0, 0.0, 0.0])
    tgt = [float(x) for x in new_xyz_ft]
    while len(tgt) < 3:
        tgt.append(old_or[len(tgt)])
    if delta:
        new_or = [old_or[i] + tgt[i] for i in range(3)]
    else:
        new_or = tgt
    dv = [new_or[i] - old_or[i] for i in range(3)]
    plan = ModifyPlan(kind="move", elem_id=eid, class_name=doc.class_of(eid))
    trf["m_or"] = new_or
    plan.changes.append(FieldChange(102, "m_pInstanceInfo.value.m_Trf.m_or", old_or, new_or))
    if rotation is not None:
        old3 = [list(r) for r in (trf.get("m_3x3") or _rot_z(0.0))]
        new3 = _matmul3(_rot_z(float(rotation)), old3)
        trf["m_3x3"] = new3
        plan.changes.append(FieldChange(102, "m_pInstanceInfo.value.m_Trf.m_3x3", old3, new3))
    # mirrored origins some instances carry
    if isinstance(val.get("m_instOrigin"), list) and any(val["m_instOrigin"]):
        oo = list(val["m_instOrigin"])
        val["m_instOrigin"] = [oo[i] + dv[i] for i in range(3)]
        plan.changes.append(FieldChange(102, "m_instOrigin", oo, val["m_instOrigin"]))
    plan.record_edits.append(sess.replacement(eid, 102, "move: placement transform"))
    # seq 103: cached GElement -- translate/rotate its instance transforms + boxes
    r103 = doc.idx[103].get(eid)
    if r103 is not None:
        o103 = doc.decode(eid, 103)
        if o103 is not None and o103.clean and o103.value:
            rep = sess.value(eid, 103)
            moved = _move_rep(rep, dv, trf.get("m_3x3") if rotation is not None else None)
            if moved:
                plan.changes.append(FieldChange(103, "GElement transforms/boxes",
                                                f"+{dv}", "translated"))
                plan.record_edits.append(sess.replacement(eid, 103, "move: cached rep"))
    # seq 101: header outline
    o101 = doc.decode(eid, 101)
    if o101 is not None and o101.clean:
        hdr = sess.value(eid, 101)
        bb = hdr.get("m_pBBox")
        bbv = bb.get("value") if isinstance(bb, dict) else None
        mm = bbv.get("m_minmax") if isinstance(bbv, dict) else None
        if isinstance(mm, list):
            bbv["m_minmax"] = _shift_box(mm, dv)
            plan.changes.append(FieldChange(101, "m_pBBox.value.m_minmax", mm,
                                            bbv["m_minmax"]))
            plan.record_edits.append(sess.replacement(eid, 101, "move: header bbox"))
    plan.notes.append(f"translated by {dv} ft" + (
        f", rotated {rotation} rad" if rotation is not None else ""))
    sess.plans.append(plan)
    if include_owned:
        for cid in owned_children(doc, [eid]):
            if cid == eid or (doc.class_of(cid) or "") != "FamilyInstance":
                continue
            cv = doc.value(cid, 102) or {}
            if not (isinstance(cv.get("m_pInstanceInfo"), dict)
                    and cv["m_pInstanceInfo"].get("value")):
                continue
            try:
                sub = move_instance(doc, cid, dv, None, delta=True,
                                    include_owned=True)
                plan.notes.append(f"owned child {cid} translated with it")
                plan.record_edits.extend(sub.record_edits)
                plan.changes.extend(sub.changes)
            except ManipulationError as e:
                plan.notes.append(f"owned child {cid} NOT moved: {e}")
    return plan


def _move_rep(rep: dict, dv, new_3x3=None) -> bool:
    """Translate (and optionally re-orient) a cached GElement rep in place."""
    changed = False
    for key in ("m_bBox", "m_tightbBox", "m_bbox", "m_tightBox"):
        b = rep.get(key)
        if isinstance(b, list) and b and isinstance(b[0], list):
            rep[key] = _shift_box(b, dv)
            changed = True
    for node in rep.get("m_subNodes") or []:
        nv = node.get("value") if isinstance(node, dict) else None
        if not isinstance(nv, dict):
            continue
        info = ((nv.get("m_instanceInfo") or {}).get("value")) or {}
        trf = info.get("m_Trf") if isinstance(info, dict) else None
        if isinstance(trf, dict):
            o = list(trf.get("m_or") or [0.0, 0.0, 0.0])
            trf["m_or"] = [o[i] + dv[i] for i in range(3)]
            if new_3x3 is not None:
                trf["m_3x3"] = [list(r) for r in new_3x3]
            changed = True
        for key in ("m_bBox", "m_tightbBox"):
            b = nv.get(key)
            if isinstance(b, list) and b and isinstance(b[0], list):
                nv[key] = _shift_box(b, dv)
                changed = True
    return changed


def retype_instance(doc, eid: int, new_symbol_id: int, *,
                    allow_family_change: bool = False) -> ModifyPlan:
    """Point a placed FamilyInstance at another loaded symbol (type).

    Only the free / face-hosted pattern (``symbolId == masterSymbolId``) is
    supported; host-cut instances (doors/windows, whose symbol is a per-host
    geometry clone) raise.  The new symbol must be in the same category as
    the old (and, unless ``allow_family_change``, the same family).  Rewrites
    ``InstanceInfo.m_symbolId``, ``m_masterSymbolId``, the seq-103 rep's
    GInstance symbol ids, and the header's appearance / deletion parents
    (old symbol id -> new).
    """
    if not doc.in_host_document(eid):
        raise ManipulationError(f"element {eid} is not a host-document element")
    if (doc.class_of(new_symbol_id) or "") != "FamilySymbol":
        raise ManipulationError(f"{new_symbol_id} is not a FamilySymbol")
    sess = session(doc)
    val = sess.value(eid, 102)
    ii = _instance_info(val)
    old_sym = ii.get("m_symbolId")
    old_master = val.get("m_masterSymbolId")
    if old_sym != old_master:
        raise ManipulationError(
            f"instance {eid}: symbol {old_sym} != master {old_master} -- a host-cut "
            f"instance (door/window) with a per-host symbol clone; retyping needs "
            f"the clone recipe (phase 2)")
    if old_sym == new_symbol_id:
        raise ManipulationError(f"instance {eid} already uses symbol {new_symbol_id}")
    old_cat = doc.category_of(old_sym)
    new_cat = doc.category_of(new_symbol_id)
    if old_cat is not None and new_cat is not None and old_cat != new_cat:
        raise ManipulationError(
            f"symbol {new_symbol_id} is category {new_cat}, instance's type is "
            f"category {old_cat} -- retype only within a category")
    old_fam = (doc.value(old_sym) or {}).get("m_familyId")
    new_fam = (doc.value(new_symbol_id) or {}).get("m_familyId")
    if old_fam is not None and new_fam is not None and old_fam != new_fam \
            and not allow_family_change:
        raise ManipulationError(
            f"symbol {new_symbol_id} belongs to family {new_fam}, instance's type "
            f"to family {old_fam} -- pass allow_family_change=True to swap families")
    plan = ModifyPlan(kind="retype", elem_id=eid, class_name=doc.class_of(eid))
    ii["m_symbolId"] = new_symbol_id
    val["m_masterSymbolId"] = new_symbol_id
    plan.changes.append(FieldChange(102, "m_pInstanceInfo.value.m_symbolId", old_sym, new_symbol_id))
    plan.changes.append(FieldChange(102, "m_masterSymbolId", old_master, new_symbol_id))
    plan.record_edits.append(sess.replacement(eid, 102, "retype: symbol ids"))
    # seq 103 rep GInstance symbol ids
    o103 = doc.decode(eid, 103)
    if o103 is not None and o103.clean and o103.value:
        rep = sess.value(eid, 103)
        n = 0
        for node in rep.get("m_subNodes") or []:
            nv = node.get("value") if isinstance(node, dict) else None
            info = ((nv.get("m_instanceInfo") or {}).get("value")) if isinstance(nv, dict) else None
            if isinstance(info, dict) and info.get("m_symbolId") == old_sym:
                info["m_symbolId"] = new_symbol_id
                n += 1
        if n:
            plan.changes.append(FieldChange(103, "m_subNodes[*].InstanceInfo.m_symbolId",
                                            old_sym, new_symbol_id))
            plan.record_edits.append(sess.replacement(eid, 103, "retype: cached rep symbol"))
    # seq 101 header parents: old symbol -> new symbol (+ family if it changed)
    o101 = doc.decode(eid, 101)
    if o101 is not None and o101.clean:
        hdr = sess.value(eid, 101)
        remap = {old_sym: new_symbol_id}
        if old_fam is not None and new_fam is not None and old_fam != new_fam:
            remap[old_fam] = new_fam
        n = _remap_in_lists(hdr, remap)
        if n:
            plan.changes.append(FieldChange(101, "m_parents lists (symbol/family remap)",
                                            list(remap.keys()), list(remap.values())))
            plan.record_edits.append(sess.replacement(eid, 101, "retype: header parents"))
    plan.notes.append(f"retyped {eid}: symbol {old_sym} -> {new_symbol_id}"
                      + (f" (family {old_fam} -> {new_fam})" if old_fam != new_fam else ""))
    sess.plans.append(plan)
    return plan


def _remap_in_lists(v, mapping: dict) -> int:
    """Replace ids inside every list of a tree (parents lists). Returns count."""
    n = 0
    if isinstance(v, dict):
        for x in v.values():
            n += _remap_in_lists(x, mapping)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            if isinstance(x, int) and not isinstance(x, bool) and x in mapping:
                v[i] = mapping[x]
                n += 1
            else:
                n += _remap_in_lists(x, mapping)
    return n


# ===========================================================================
# COMMIT: re-emit unit 0 of Partitions/<N> + Global/ElemTable
# ===========================================================================
@dataclass
class ManipCommitReport:
    partition: str
    removed_ids: List[int]
    replaced: List[Tuple[int, int]]          # (seq, elem_id)
    elemtable_count_before: int
    elemtable_count_after: int
    watermark: int
    blocks_before: Dict[int, int]
    blocks_after: Dict[int, int]
    out_path: str

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def _record_spans(seg: bytes, seq: int) -> List[Tuple[Record, int, int]]:
    """[(record, start, length)] over a unit-0 per-seq segment."""
    hlen = 12 if seq == 101 else 16
    out = []
    for r in iter_records(seg, seq):
        length = hlen + r.body_size + 4
        out.append((r, r.seg_offset, length))
    return out


def _hdr_len_w1(seq: int) -> int:
    """Wave-1 record header length used by the block C / ISIZE identity."""
    return record_header_len(seq)          # 16 for seq 101, 20 for 102/103


def chunk_segment(seg: bytes, seq: int, budget: int = BLOCK_BUDGET) -> List[dict]:
    """Re-block a whole per-seq record segment for save-unit 0.

    Returns a list of blocks ``{payload, flags, A, C}`` obeying the corpus
    identity ``ISIZE == hdr_len(seq)*A + C + adj(flags)`` (exact on all
    13,535 corpus blocks): whole records only (flags 4) while the next record
    fits the budget; a record larger than the budget spans blocks
    (6 -> 7... -> 5).
    """
    spans = _record_spans(seg, seq)
    hdr = _hdr_len_w1(seq)
    blocks: List[dict] = []
    cur = bytearray()
    cur_a = 0

    def flush_whole():
        nonlocal cur, cur_a
        if cur:
            blocks.append({"payload": bytes(cur), "flags": 4, "A": cur_a,
                           "C": len(cur) - hdr * cur_a})
            cur = bytearray()
            cur_a = 0

    walked = 0
    for _rec, start, length in spans:
        rb = seg[start:start + length]
        walked = start + length
        if length > budget:
            flush_whole()
            # split into budget-sized chunks: first flags 6, middle 7, last 5
            parts = [rb[i:i + budget] for i in range(0, len(rb), budget)]
            if len(parts) == 1:  # (cannot happen; length > budget)
                blocks.append({"payload": parts[0], "flags": 4, "A": 1,
                               "C": len(parts[0]) - hdr})
                continue
            for k, part in enumerate(parts):
                if k == 0:
                    flags, a = 6, 1
                elif k == len(parts) - 1:
                    flags, a = 5, 0
                else:
                    flags, a = 7, 0
                c = len(part) - hdr * a - _ISIZE_ADJ[flags]
                blocks.append({"payload": part, "flags": flags, "A": a, "C": c})
            continue
        if cur and len(cur) + length > budget:
            flush_whole()
        cur += rb
        cur_a += 1
    flush_whole()
    if walked != len(seg):
        raise ManipulationError(
            f"seq {seq}: record walk covered {walked} of {len(seg)} bytes")
    if not blocks:
        raise ManipulationError(f"seq {seq}: empty segment")
    return blocks


def _emit_block(b: dict, seq: int, level: int = 3) -> bytes:
    """Frame one block with the tags in force in :mod:`rvt.partitions` NOW
    (the release ``rvt.versions.reading()`` activated, 2026 at rest) -- the
    same values the post-emit re-walk checks against."""
    gz = gzip_member(b["payload"], level=level, sync_flush=True)
    nb = 8 + len(gz)
    hdr = struct.pack("<HIIIIII", _P.BLOCK_TAG, b["flags"], b["A"], nb, b["C"], seq, 0)
    return hdr + gz + struct.pack("<HI", _P.TRAILER_TAG, nb)


def apply_edits_to_segment(seg: bytes, seq: int, removals: set,
                           replacements: Dict[int, bytes]) -> Tuple[bytes, dict]:
    """Rebuild a unit-0 per-seq segment with records removed / replaced.

    ``removals``: elem_ids to drop; ``replacements``: elem_id -> new framed
    record bytes.  Returns (new_segment, stats).  The trailing sentinel
    (id -1) is always preserved and stays last.
    """
    spans = _record_spans(seg, seq)
    out = bytearray()
    st = {"removed": 0, "replaced": 0, "kept": 0, "sentinel_last": False}
    for i, (rec, start, length) in enumerate(spans):
        last = (i == len(spans) - 1)
        if rec.elem_id < 0:
            out += seg[start:start + length]
            if last:
                st["sentinel_last"] = True
            continue
        if rec.elem_id in removals:
            st["removed"] += 1
            continue
        if rec.elem_id in replacements:
            out += replacements[rec.elem_id]
            st["replaced"] += 1
            continue
        out += seg[start:start + length]
        st["kept"] += 1
    return bytes(out), st


def _header_count(doc, pname: str) -> Optional[int]:
    """The u32 elem_table_count in ``pname``'s stream header -- None when the
    stream is too short to carry one.  ``doc``: an open ``RvtDocument`` or a
    ``rvt.validate.WalkedFile``."""
    logical = doc.logical(pname)
    if len(logical) < PART_HDR_COUNT_OFF + 4:
        return None
    return struct.unpack_from("<I", logical, PART_HDR_COUNT_OFF)[0]


def _primary_partition(doc, entries_by_path) -> str:
    """The partition stream holding the host document (unit 0 == ElemTable).
    ``doc``: an open ``RvtDocument`` or a ``rvt.validate.WalkedFile``."""
    parts = doc.partition_streams()
    if len(parts) == 1:
        return parts[0]
    # dach carries a second, empty partition (0 elements): pick the stream
    # whose header count matches the ElemTable count; when the ElemTable is
    # unreadable (verify must judge such a file, not raise while choosing)
    # nothing matches and the partition declaring the most elements wins.
    counts = {pn: _header_count(doc, pn) for pn in parts}
    try:
        et_count = struct.unpack_from("<HI", doc.inflate("Global/ElemTable"), 0)[1]
    except Exception:                       # noqa: BLE001 -- lost/absent/garbage: no match
        et_count = None
    for pn in parts:
        if et_count is not None and counts[pn] == et_count:
            return pn
    return max(parts, key=lambda pn: -1 if counts[pn] is None else counts[pn])


def commit_plans(src_rvt: str, out_path: str, plans: Sequence[Plan], *,
                 block_budget: int = BLOCK_BUDGET,
                 rechunk: str = "unit0") -> ManipCommitReport:
    """Apply a set of Delete/Modify plans to ``src_rvt`` and write ``out_path``.

    Save-unit 0 of the host document's ``Partitions/<N>`` is re-emitted
    with the record removals / replacements from every plan (later
    replacements of the same record win; a removal beats a replacement);
    ``Global/ElemTable`` drops the deleted rows (count decremented, id
    watermark kept) and the partition stream-header count is set to the
    new ElemTable count.  Every embedded-document unit (1..k), every other
    stream, and the save-history streams are copied unchanged.
    """
    removals: set = set()
    replacements: Dict[Tuple[int, int], bytes] = {}
    et_remove: set = set()
    for pl in plans:
        for e in pl.record_edits:
            if e.action == "remove":
                removals.add(e.elem_id)
            elif e.action == "replace":
                replacements[(e.seq, e.elem_id)] = e.new_record
        for i in getattr(pl, "elemtable_remove", []) or []:
            et_remove.add(i)
    # a removal supersedes any replacement of the same element
    for key in [k for k in replacements if k[1] in removals]:
        del replacements[key]

    entries = read_entries(src_rvt)
    new_streams: Dict[str, bytes] = {}
    with open_rvt(src_rvt) as doc:
        pname = _primary_partition(doc, entries)

        # ---------------- 1. Global/ElemTable -------------------------------
        model = decode_elemtable(doc.inflate("Global/ElemTable"))
        count_before = len(model["records"])
        if et_remove:
            model["records"] = [r for r in model["records"] if r[4] not in et_remove]
        count_after = len(model["records"])
        watermark = int(model["footer"]["last_id"])
        et_payload = encode_elemtable(model)
        et_logical = global_prefix("Global/ElemTable") + gzip_member(et_payload, level=3)
        new_streams["Global/ElemTable"] = ecc.frame_stream(et_logical)

        # ---------------- 2. Partitions/<N> ---------------------------------
        logical = doc.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        if w.errors:
            raise ManipulationError(f"walker errors on source {pname}: {w.errors[:3]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        u0 = [b for b in blocks if b.unit == 0]
        if not u0:
            raise ManipulationError(f"{pname}: no save-unit-0 blocks")
        seq_order: List[int] = []
        for b in u0:
            if b.seq not in seq_order:
                seq_order.append(b.seq)
        blocks_before = {s: sum(1 for b in u0 if b.seq == s) for s in seq_order}
        segments = {s: b"".join(b.data for b in u0 if b.seq == s) for s in seq_order}

        new_segments: Dict[int, bytes] = {}
        for s in seq_order:
            rep_map = {eid: rec for (sq, eid), rec in replacements.items() if sq == s}
            seg2, st = apply_edits_to_segment(segments[s], s, removals, rep_map)
            if not st["sentinel_last"]:
                raise ManipulationError(f"seq {s}: unit-0 segment lost its sentinel")
            new_segments[s] = seg2

        # emit: stream header + unit-0 block runs + verbatim tail (unit-0
        # footer, embedded units 1..k, end record)
        u0_first = u0[0].hdr_offset
        u0_footer = w.units[0].footer_offset
        if u0_footer is None:
            raise ManipulationError(f"{pname}: unit-0 footer not found")
        out = bytearray(logical[:u0_first])
        blocks_after: Dict[int, int] = {}
        for s in seq_order:
            nb = chunk_segment(new_segments[s], s, block_budget)
            blocks_after[s] = len(nb)
            for b in nb:
                out += _emit_block(b, s)
        out += logical[u0_footer:]
        struct.pack_into("<I", out, PART_HDR_COUNT_OFF, count_after)
        # sanity: the re-walk must be clean and end where the original did
        w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
        if w2.errors:
            raise ManipulationError(f"walker errors after re-emit: {w2.errors[:3]}")
        part_logical = bytes(out[:w2.end_offset + len(w2.end_record)])
        new_streams[pname] = ecc.frame_stream(part_logical)

    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out_path, out_entries)
    return ManipCommitReport(pname, sorted(removals),
                             sorted(replacements.keys()),
                             count_before, count_after, watermark,
                             blocks_before, blocks_after, out_path)


def commit_deletions(src_rvt: str, out_path: str, plan: DeletePlan, **kw) -> ManipCommitReport:
    """Apply one DeletePlan (records + referrer edits + ElemTable rows)."""
    return commit_plans(src_rvt, out_path, [plan], **kw)


def commit_modifications(src_rvt: str, out_path: str,
                         plans: Sequence[ModifyPlan], **kw) -> ManipCommitReport:
    return commit_plans(src_rvt, out_path, list(plans), **kw)


def commit_session(doc, out_path: str, **kw) -> ManipCommitReport:
    """Commit every plan accumulated on the Document's edit session."""
    sess = session(doc)
    if not sess.plans:
        raise ManipulationError("no pending plans on this document")
    return commit_plans(source_path(doc), out_path, sess.plans, **kw)


# ===========================================================================
# VERIFY: structural proof + semantic re-read
# ===========================================================================
def verify_manipulated(path: str, *, deleted_ids: Sequence[int] = (),
                       edited_ids: Sequence[int] = (),
                       expect_elemtable_count: Optional[int] = None,
                       walked=None) -> dict:
    """Prove a manipulated file is structurally healthy and the edits landed.

    Checks: gzip CRC of every framed stream, each enumerated by its framing
    (:meth:`rvt.validate.WalkedFile.crc_failures` -- a body that will not
    inflate at all counts as a CRC failure exactly like the validator's L1
    finding, on whichever stream it sits); per-page ECC trailers of the two
    re-emitted streams; framing walker errors of every partition (a
    partition whose stream header does not parse is ONE walker error, its
    reason recorded in ``rep["framing_errors"][<partition>]`` -- present only
    then -- and, on the primary, the block-dependent facts below stay None:
    a FAIL verdict, never a raise); the block ISIZE identity on the primary
    partition; partition header count == ElemTable count (a lost / CRC-bad
    ElemTable is not parsed: its counts stay None and the verdict FAILs);
    per-seq sentinels last; adler32 stamps of every unit-0 seq-102/103
    record; deleted ids absent from unit 0 (all seqs) and from the
    ElemTable; edited ids present, decoding cleanly, in all their seqs.

    The file is judged under its OWN release framing and OWN schema
    (:func:`rvt.validate.enter_own_release` -- nest-safe, restored on exit;
    :func:`rvt.versions.schema_of`), whoever calls this and from whatever
    context.  ``rep["fallbacks"]`` is empty when both came from the file;
    otherwise it names each rung used instead and why (a label, never a
    raise).

    ``walked`` (optional, :func:`rvt.validate.walk_file`) is the file already
    read by a caller that also runs the validator on it: the byte facts come
    from that one read/inflate walk instead of a second one (#266).  The
    verdict is the same with or without it -- the self-check always judges
    OUR bytes as stored, never the validator's CRCIO-auto-repaired view.
    """
    from contextlib import ExitStack

    from .objects import ObjectDecoder
    from .validate import enter_own_release, walk_file
    from .versions import schema_of
    # block-dependent facts start None = not checked (never PASS); the block
    # walk of the primary partition fills them in
    rep: Dict[str, Any] = {"crc_failures": 0, "ecc_mismatches": 0,
                           "walker_errors": 0, "isize_identity_mismatches": None,
                           "elemtable_count": None, "header_count": None,
                           "sentinel_last": None, "stamps_ok": None,
                           "deleted_still_present": {}, "deleted_in_elemtable": [],
                           "edited": {}, "elemtable_ids_sorted": None,
                           "unit0_ids_equal_elemtable": None, "fallbacks": []}
    with ExitStack() as stack:
        framing_fallback = enter_own_release(stack, path)
        if framing_fallback:
            rep["fallbacks"].append(framing_fallback)
        # the self-check judges OUR payload bytes as stored (the shared walk
        # itself unless its ECC pass repaired a payload bit -- never on a file
        # we just framed); walkers are built here, under the file's release
        walked = (walked.view(repair=False) if walked is not None
                  else walk_file(path, repair=False))
        try:
            dec = ObjectDecoder(schema_of(walked))         # the FILE'S schema
        except Exception as e:                             # noqa: BLE001
            dec = ObjectDecoder()
            rep["fallbacks"].append(
                f"own schema unreadable ({type(e).__name__}: {e}); edited "
                "records decoded against the built-in latest-release schema")
        pname = _primary_partition(walked, None)
        parts = walked.partition_streams()
        # framing walker errors of every partition; one whose stream header
        # does not parse enumerates no block: ONE walker error, its reason
        # recorded as the validator words its L1 finding
        framing: Dict[str, str] = {}
        for p in parts:
            why = walked.framing_error(p)
            if why:
                framing[p] = why
                rep["walker_errors"] += 1
            else:
                rep["walker_errors"] += len(walked.walker(p).errors)
        if framing:
            rep["framing_errors"] = framing
        # gzip CRC by each stream's FRAMING (every partition by its block
        # headers): a body that will not inflate counts wherever it sits
        rep["crc_failures"] = sum(walked.crc_failures(n) for n in walked.names)
        for name in (pname, "Global/ElemTable"):
            if name in walked.names:
                rep["ecc_mismatches"] += ecc.framing_mismatches(walked.raw(name))
        # the ElemTable CRC-verified, else None: a lost / CRC-bad body is
        # counted above and never parsed -- its counts stay None (-> FAIL)
        et_payload = walked.payload("Global/ElemTable")
        etset = None
        if et_payload is not None:
            model = decode_elemtable(et_payload)
            et_ids = [r[4] for r in model["records"]]
            rep["elemtable_count"] = len(et_ids)
            rep["elemtable_ids_sorted"] = et_ids == sorted(et_ids)
            etset = set(et_ids)
            rep["deleted_in_elemtable"] = [i for i in deleted_ids if i in etset]
        rep["header_count"] = _header_count(walked, pname)
        if pname not in framing:                           # the primary's blocks, inflated ONCE
            w = walked.walker(pname)
            rep["isize_identity_mismatches"] = sum(
                1 for b in w.blocks if b.data is not None and b.intended_len != len(b.data))
            rep["sentinel_last"] = {}
            rep["stamps_ok"] = True
            segments = walked.segments(pname)
            u0_102_ids = None
            for seq in (101, 102, 103):
                recs = list(iter_records(segments.get((0, seq), b""), seq))
                rep["sentinel_last"][seq] = bool(recs) and recs[-1].elem_id == -1
                ids_here = set()
                for r in recs:
                    if r.elem_id >= 0:
                        ids_here.add(r.elem_id)
                    if r.elem_id in deleted_ids:
                        rep["deleted_still_present"].setdefault(seq, []).append(r.elem_id)
                    if r.elem_id in edited_ids:
                        o = dec.decode_record(r.class_id, r.payload) if r.body_size >= 2 else None
                        rep["edited"].setdefault(str(r.elem_id), {})[str(seq)] = {
                            "class": (o.class_name if o else None),
                            "clean": (bool(o.clean or o.stub) if o else None)}
                    if (seq != 101 and r.elem_id >= 0 and r.body_size >= 2
                            and record_stamp(r.class_id, r.payload) != r.stamp):
                        rep["stamps_ok"] = False
                if seq == 102:
                    u0_102_ids = ids_here
            if etset is not None:
                rep["unit0_ids_equal_elemtable"] = (u0_102_ids == etset)
    if expect_elemtable_count is not None:
        rep["elemtable_count_expected"] = expect_elemtable_count
    return rep


def reopen(path: str):
    """Fresh Document over a written file (semantic re-read)."""
    from .mutate import Document
    return Document.from_file(path)


# ===========================================================================
# convenience: describe an element (for interactive planning)
# ===========================================================================
def describe(doc, eid: int) -> dict:
    """Compact human-readable snapshot of an element for planning edits."""
    out: Dict[str, Any] = {"elem_id": eid, "in_host_document": doc.in_host_document(eid),
                           "class": doc.class_of(eid), "category": doc.category_of(eid)}
    v = doc.value(eid) or {}
    for k in ("m_id", "m_assocLevelId", "m_hostId", "m_masterSymbolId", "m_text",
              "m_name", "m_famId", "m_elevation", "m_workPlaneBased", "m_number"):
        if k in v:
            out[k] = v[k]
    ii = ((v.get("m_pInstanceInfo") or {}).get("value")) if isinstance(v.get("m_pInstanceInfo"), dict) else None
    if isinstance(ii, dict):
        out["placement_or"] = (ii.get("m_Trf") or {}).get("m_or")
        out["symbol_id"] = ii.get("m_symbolId")
    if doc.class_of(eid) == "Level":
        try:
            out["elevation_ft"] = doc._level_elevation(eid)
        except Exception:
            pass
    r = doc.et_by_id.get(eid)
    if r is not None:
        out["elemrec"] = {"owner": _norm_owner(r.owner_id),
                          "creation_ep": r.creation_ep, "modified_ep": r.modified_ep}
    return out


# ===========================================================================
# CLI / demo
# ===========================================================================
def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 0
    path = argv[0]
    from .mutate import Document
    doc = Document.from_file(path)
    if len(argv) >= 3 and argv[1] == "report":
        eid = int(argv[2])
        rep = dependency_report(doc, eid)
        print(json.dumps(rep, indent=1, default=str)[:20000])
        return 0
    if len(argv) >= 3 and argv[1] == "describe":
        print(json.dumps(describe(doc, int(argv[2])), indent=1, default=str))
        return 0
    print(json.dumps({"levels": doc.levels()[:12],
                      "elemtable_count": doc.et.count,
                      "watermark": doc.last_issued_id}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
