"""regdiff.py -- THE REGISTRATION DIFF: exactly how an element is registered in
a .rvt (ElemTable row + ElementHeader envelope + record positions in the
unit-0 seq streams + ADocument registry surface + referrer / ownership web),
so the registration OUR add path produces can be compared field by field
against Autodesk's own registration of the same element, against the proven
family-INSTANCE add path, and against corpus-mined invariants.

Background (docs/writer/registration-diff.md, ORCHESTRATOR VERDICTS #11):
X0 (Autodesk's OWN pen table, exact bytes, re-inserted through OUR add path at
a new id 1,500,000) and C0 (Autodesk's own object-styles catalog row verbatim
through our path) both FAIL 'Revit-DocumentCorruption' while the constructed
content is byte-identical to the accepted specimen -- so the corruption lives
in the REGISTRATION delta (this module measures it), whereas the family-INSTANCE
add path (V20..V29 created FamilyInstances / walls / circuits) is viewer-PROVEN.

Public surface
--------------
* :func:`registration_of` -- the full registration record of one element in
  a file: :class:`Registration` (ElemTable row + derived flags, decoded
  ElementHeader summary, the per-seq record POSITIONS and the id-ascending RUN
  each record sits in, the ADocument registry surface, ElemTable-owned rows,
  and -- with ``deep=True`` -- the typed inbound-referrer set).
* :func:`diff_registrations` -- field-by-field diff of two Registrations.
* :func:`unit0_runs` -- the id-ascending RUN structure of a file's unit-0
  record stream (the corpus law: records are grouped by MODIFIED episode,
  newest-modified group FIRST, id-ascending inside each group).
* :func:`mine_elemtable_invariants` / :func:`mine_record_order` -- the six-
  sample census behind the invariants (registration semantics per class).

CLI::

    .venv/bin/python -m rvt.regdiff                       # demo: K1 id 2 / X0 / V20 + corpus laws
    .venv/bin/python -m rvt.regdiff FILE ID [ID ...]      # dump registrations
    .venv/bin/python -m rvt.regdiff --mine                # the six-sample census (JSON)
    .venv/bin/python -m rvt.regdiff --runs FILE           # the run structure of a file

Territory note: read-only over every stream; never writes a .rvt.
"""
from __future__ import annotations

import collections
import dataclasses
import json
import os
import struct
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import adocument as adoc
from .container import open_rvt
from .elemtable import INVALID_ID, NO_EPISODE, load_elemtable
from .objects import ObjectDecoder, Record, field_key, iter_records, load_segment
from .partitions import StreamWalker
from .stream_encoders import decode_elemtable

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLES = ["rstbasicsampleproject", "rstadvancedsampleproject", "racbasicsampleproject",
           "racadvancedsampleproject", "rmebasicsampleproject", "dach-sample-project"]
SEQS = (101, 102, 103)

#: classes whose add path is viewer-PROVEN (created / clone-created elements
#: that the Autodesk reader accepted: V20..V29, T_conduit_types, L1a) --
#: the calibration side of every comparison.
PROVEN_INSTANCE_CLASSES = ("FamilyInstance", "SWall", "RbsElectricalSystem",
                           "FamilySymbol", "Family", "RbsConduitType",
                           "RbsCableTrayType", "RbsWireType", "CustomElement")

#: the settings-singleton / catalog classes the genesis writer emits and the
#: substitution ladder re-registers (the FAILING side).  A superset is fine:
#: classes with zero host specimens are simply reported as unobserved.
GENESIS_SINGLETON_CLASSES = (
    "PenWidthTableElem", "GStyleElem", "CategoryElem", "FillPatternElem",
    "LinePatternElem", "AllProjectPhases", "PhaseElem", "PhaseFilterElem",
    "BrowserOrganization", "RbsDbViewSystemNavigator", "KeynoteTable",
    "KeynotingSystem", "InitialViewSettings", "StructSettingsElem",
    "WallJoinDefaultSetting", "AutoJoinTracker", "ReconcileBrowserSettingsElem",
    "ConstructionSetProject", "RbsWireSettingsElem", "RbsWireSizesElem",
    "RbsPipeSettingsElem", "RbsPipeSizesElem", "RbsDuctSettingsElem",
    "RbsDuctSizesElem", "ConduitSettingsElem", "CableTraySettingsElem",
    "AutoCamSettingsElem", "HalftoneUnderlaySettings", "DaylightSourceIdSet",
    "ExternalParamLock", "AllProjectRevisions", "ProjectRevision",
    "RevisionNumberingSequence", "WorksharingViewModeSettings",
    "CoordinateSystemDisplayElem", "UnitsElem", "TrueNorth", "ProjectInfo",
    "BasePoint", "GeoSite", "GeoLocation", "DBViewProject", "ElectricalSetting",
    "MaterialElem", "SunAndShadowSettings", "Viewer", "Viewport", "DBDrawing",
    "MEPNetworkDataElem", "GraphicsCache", "EnergyDataSettings",
    "AreaSettingsElem", "ReinforcementSettings", "TextNoteAttributes", "FontElem",
    "DBViewType", "DBViewPlan", "DBView3d")


def _band(eid: int) -> str:
    """Coarse id band of a positive ElementId (the objlint id_band buckets)."""
    if eid < 5_000:
        return "<5k"
    if eid < 50_000:
        return "<50k"
    if eid < 500_000:
        return "<500k"
    if eid < 5_000_000:
        return "<5M"
    return ">=5M"


# ===========================================================================
# 1. the minimal schema-typed ElementId leaf walker (surface / referrers)
# ===========================================================================

@dataclasses.dataclass
class IdLeaf:
    path: str
    value: int


class TypedIdWalker:
    """Yield every ElementId-typed leaf of a decoded class body.

    A compact re-implementation of the schema-parallel walk (the same rules
    the genesis ADocument editor certifies with): integers are leaves only
    when the archive field type IS ``ElementId`` / ``Identifier`` (kind 0x0E
    inline value class) -- so counters / enum indexes / the geometry-step '2'
    that byte scans hit are never mistaken for the pen table's id 2.  Kept
    inside ``src/`` so no tool has to be imported.
    """

    def __init__(self, decoder: Optional[ObjectDecoder] = None):
        self.dec = decoder or adoc.get_decoder()
        self.schema = self.dec.schema
        self.eid_types = {t for t in (getattr(self.dec, "id_ElementId", None),
                                      getattr(self.dec, "id_Identifier", None)) if t}
        if not self.eid_types:                              # ordinary ObjectDecoder
            for nm, attr in (("ElementId", "id_ElementId"), ("Identifier", "id_Identifier")):
                cd = self.schema.by_name.get(nm)
                if cd is not None:
                    self.eid_types.add(cd.type_id)

    def class_id(self, name: str) -> Optional[int]:
        cd = self.schema.by_name.get(name)
        return cd.type_id if cd else None

    def leaves(self, value: dict, class_name: str) -> List[IdLeaf]:
        cid = self.class_id(class_name)
        out: List[IdLeaf] = []
        if cid is None or not isinstance(value, dict):
            return out
        self._walk(value, cid, class_name, out)
        return out

    def _walk(self, value: dict, class_id: int, path: str, out: List[IdLeaf]) -> None:
        if not isinstance(value, dict):
            return
        seen: dict = {}
        for cd in self.dec.chain(class_id):
            for f in cd.fields:
                key = field_key(cd, f, seen)
                seen[key] = True
                if key in value:
                    self._walk_field(value[key], f, f"{path}.{key}", out)

    def _walk_field(self, v, f, fpath: str, out: List[IdLeaf]) -> None:
        kind, flags = f.kind, f.flags
        if kind in (0x08, 0x09):                               # string / guid
            return
        if kind == 0x0D:                                       # inline array wrapper
            elem = f.element
            if isinstance(v, list) and elem is not None:
                for i, x in enumerate(v):
                    self._walk_scalar(x, elem, f"{fpath}[{i}]", out)
            return
        if (flags >> 4) in (0x5, 0x1):                         # container / fixed array
            if isinstance(v, list):
                for i, x in enumerate(v):
                    self._walk_scalar(x, f, f"{fpath}[{i}]", out)
            return
        self._walk_scalar(v, f, fpath, out)

    def _walk_scalar(self, x, f, xpath: str, out: List[IdLeaf]) -> None:
        kind, indir = f.kind, f.flags & 0x0F
        if kind == 0x0B:                                       # i64 id-by-name convention
            if any(t in f.name for t in ("ElemId", "ElementId", "Id64")):
                if isinstance(x, int) and not isinstance(x, bool):
                    out.append(IdLeaf(xpath, x))
            return
        if kind != 0x0E:
            return
        if indir == 0:
            if f.type_id in self.eid_types:
                if isinstance(x, int) and not isinstance(x, bool):
                    out.append(IdLeaf(xpath, x))
                return
            if isinstance(x, dict):
                self._walk(x, f.type_id, xpath, out)
            return
        if indir == 3:                                         # weak reference
            return
        if isinstance(x, dict) and "ptr_class" in x:            # owned pointer holder
            cid = self.class_id(x["ptr_class"])
            if cid is not None and isinstance(x.get("value"), dict):
                self._walk(x["value"], cid, f"{xpath}->{x['ptr_class']}", out)


# ===========================================================================
# 2. the loaded-document view
# ===========================================================================

@dataclasses.dataclass
class SeqRec:
    """Where one seq's record of an element sits in the unit-0 stream."""
    seq: int
    index: int              # host-record index within the unit-0 seq segment (sentinel excluded)
    total: int              # host records in this seq segment (sentinel excluded)
    seg_offset: int
    framed_len: int
    class_id: int
    class_name: str
    stamp: int
    body_size: int
    block_pos: Tuple[int, int]      # (block index within the seq run, blocks in the run)
    is_last: bool                    # last record before the sentinel


class RegDoc:
    """Everything the registration diff reads out of one .rvt file.

    Loads (lazily where it costs): the ElemTable, unit-0 of the primary
    partition stream (blocks + the three per-seq record indexes), the decoded
    ADocument tree, and a schema decoder for element records.
    """

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self._et: Optional[dict] = None
        self._rows: Optional[Dict[int, tuple]] = None
        self._u0: Optional[List[Any]] = None
        self._segments: Optional[Dict[int, bytes]] = None
        self._recidx: Optional[Dict[int, List[Record]]] = None
        self._recpos: Optional[Dict[int, Dict[int, int]]] = None
        self._adoc = None
        self._latest_payload: Optional[bytes] = None
        self._dec: Optional[ObjectDecoder] = None
        self._walker: Optional[TypedIdWalker] = None
        self._pname: Optional[str] = None

    # -- ElemTable ---------------------------------------------------------
    @property
    def elemtable(self) -> dict:
        if self._et is None:
            with open_rvt(self.path) as f:
                self._et = decode_elemtable(f.inflate("Global/ElemTable"))
            self._rows = {int(r[4]): r for r in self._et["records"]}
        return self._et

    @property
    def rows(self) -> Dict[int, tuple]:
        self.elemtable
        assert self._rows is not None
        return self._rows

    def row(self, eid: int) -> Optional[tuple]:
        return self.rows.get(int(eid))

    @property
    def watermark(self) -> int:
        return int(self.elemtable["footer"]["last_id"])

    def max_episode(self) -> int:
        return max((int(r[2]) for r in self.elemtable["records"]), default=-1)

    # -- unit-0 record streams -------------------------------------------------
    def _load_unit0(self) -> None:
        with open_rvt(self.path) as f:
            parts = f.partition_streams()
            # host document = the partition whose header count matches the
            # ElemTable count (dach carries an empty second partition)
            pname = parts[0]
            if len(parts) > 1:
                et_count = len(self.elemtable["records"])
                for pn in parts:
                    if struct.unpack_from("<I", f.logical(pn), 14)[0] == et_count:
                        pname = pn
                        break
            self._pname = pname
            w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"{self.path}: partition walker errors {w.errors[:2]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        self._u0 = [b for b in blocks if b.unit == 0]
        self._segments = {s: b"".join(b.data for b in self._u0 if b.seq == s) for s in SEQS}
        self._recidx = {}
        self._recpos = {}
        for s in SEQS:
            recs = [r for r in iter_records(self._segments[s], s) if r.elem_id >= 0]
            self._recidx[s] = recs
            self._recpos[s] = {int(r.elem_id): i for i, r in enumerate(recs)}

    @property
    def unit0_blocks(self):
        if self._u0 is None:
            self._load_unit0()
        return self._u0

    def segment(self, seq: int) -> bytes:
        if self._segments is None:
            self._load_unit0()
        assert self._segments is not None
        return self._segments[seq]

    def host_records(self, seq: int) -> List[Record]:
        """Unit-0 records of one seq in STREAM ORDER (sentinel excluded)."""
        if self._recidx is None:
            self._load_unit0()
        assert self._recidx is not None
        return self._recidx[seq]

    def record_index(self, seq: int, eid: int) -> Optional[int]:
        if self._recpos is None:
            self._load_unit0()
        assert self._recpos is not None
        return self._recpos[seq].get(int(eid))

    # -- decoding ---------------------------------------------------------------
    @property
    def dec(self) -> ObjectDecoder:
        if self._dec is None:
            self._dec = ObjectDecoder()
        return self._dec

    @property
    def walker(self) -> TypedIdWalker:
        if self._walker is None:
            self._walker = TypedIdWalker(self.dec)
        return self._walker

    def record(self, seq: int, eid: int) -> Optional[Record]:
        i = self.record_index(seq, eid)
        return self.host_records(seq)[i] if i is not None else None

    def decode_record(self, seq: int, eid: int):
        r = self.record(seq, eid)
        if r is None or r.body_size < 2:
            return None
        return self.dec.decode_record(r.class_id, r.payload)

    def class_of(self, eid: int) -> Optional[str]:
        r = self.record(102, eid)
        return self.dec.class_name(r.class_id) if r else None

    # -- ADocument --------------------------------------------------------------
    @property
    def latest_payload(self) -> bytes:
        if self._latest_payload is None:
            with open_rvt(self.path) as f:
                self._latest_payload = f.inflate(adoc.STREAM, 0)
        return self._latest_payload

    @property
    def adoc_tree(self) -> dict:
        if self._adoc is None:
            a = adoc.decode_latest(self.latest_payload)
            if not a.clean:
                raise RuntimeError(f"{self.path}: ADocument decode not clean {a.errors[:1]}")
            self._adoc = a
        return self._adoc.value

    def adoc_surface(self, ids: Iterable[int]) -> Dict[int, List[str]]:
        """{id: [typed ADocument leaf paths holding it]} -- the REGISTRY
        SURFACE of each id (schema-typed, whole tree)."""
        want = {int(i) for i in ids}
        out: Dict[int, List[str]] = {i: [] for i in want}
        aw = TypedIdWalker(adoc.get_decoder())
        for lf in aw.leaves(self.adoc_tree, "ADocument"):
            if isinstance(lf.value, int) and lf.value in out:
                out[lf.value].append(lf.path)
        return {k: sorted(v) for k, v in out.items()}


# ===========================================================================
# 3. the RUN structure of unit 0 (the record-position law)
# ===========================================================================

@dataclasses.dataclass
class Run:
    index: int
    start: int                  # host-record index of the first record
    end: int                    # exclusive
    id_min: int
    id_max: int
    modal_modified_ep: int
    modal_share: float          # fraction of the run's rows carrying the modal modified_ep
    distinct_modified_ep: int
    creation_ep_min: int
    creation_ep_max: int
    top_classes: List[Tuple[str, int]]

    @property
    def size(self) -> int:
        return self.end - self.start


def unit0_runs(doc: RegDoc, seq: int = 102, *, class_names: bool = True) -> List[Run]:
    """Split unit 0's ``seq`` record stream into maximal ID-ASCENDING runs
    and characterize each by the ElemTable episodes of its rows.

    CORPUS LAW (all six 2026 samples, docs/writer/registration-diff.md §3):
    the unit-0 record stream is NOT id-sorted; it is a sequence of
    id-ascending RUNS grouped by the rows' MODIFIED episode, the MOST
    RECENTLY modified group FIRST and the oldest-modified group LAST -- the
    save history written newest-first.  A record's position therefore encodes
    'which save last wrote this element'.
    """
    recs = doc.host_records(seq)
    rows = doc.rows
    ids = [int(r.elem_id) for r in recs]
    bounds = [0] + [i + 1 for i in range(len(ids) - 1) if ids[i + 1] < ids[i]] + [len(ids)]
    out: List[Run] = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        if b <= a:
            continue
        me = collections.Counter()
        ce_lo = ce_hi = None
        cls = collections.Counter()
        for j in range(a, b):
            eid = ids[j]
            row = rows.get(eid)
            if row is not None:
                m = int(row[2])
                me[m] += 1
                c = int(row[1])
                ce_lo = c if ce_lo is None or c < ce_lo else ce_lo
                ce_hi = c if ce_hi is None or c > ce_hi else ce_hi
            if class_names:
                cls[doc.dec.class_name(recs[j].class_id)] += 1
        if me:
            modal, n = me.most_common(1)[0]
        else:
            modal, n = -1, 0
        out.append(Run(k, a, b, ids[a], ids[b - 1], int(modal), n / max(1, b - a),
                       len(me), int(ce_lo if ce_lo is not None else -1),
                       int(ce_hi if ce_hi is not None else -1), cls.most_common(4)))
    return out


def run_law_report(doc: RegDoc, seq: int = 102) -> dict:
    """How well a file's unit 0 obeys the (modified_ep DESC, id ASC) law."""
    runs = unit0_runs(doc, seq)
    modals = [r.modal_modified_ep for r in runs]
    nondesc = sum(1 for a, b in zip(modals, modals[1:]) if b > a)
    recs = doc.host_records(seq)
    ids = [int(r.elem_id) for r in recs]
    asc = sum(1 for a, b in zip(ids, ids[1:]) if b > a)
    return {
        "file": doc.name, "seq": seq, "host_records": len(ids), "runs": len(runs),
        "adjacent_id_ascending_fraction": round(asc / max(1, len(ids) - 1), 5),
        "runs_modal_episode_descending_violations": nondesc,
        "runs_modal_episode_descending": nondesc == 0,
        "first_run_modal_episode": modals[0] if modals else None,
        "last_run_modal_episode": modals[-1] if modals else None,
        "max_history_episode": doc.max_episode(),
        "run_summary": [{"pos": [r.start, r.end - 1], "recs": r.size,
                         "ids": [r.id_min, r.id_max],
                         "modal_modified_ep": r.modal_modified_ep,
                         "modal_share": round(r.modal_share, 3),
                         "top_classes": r.top_classes[:2]} for r in runs],
    }


# ===========================================================================
# 4. the registration record
# ===========================================================================

@dataclasses.dataclass
class Registration:
    file: str
    elem_id: int
    class_name: Optional[str]
    # ElemTable row (None if absent)
    row: Optional[dict]
    # decoded ElementHeader summary
    header: Optional[dict]
    # object identity
    object: Optional[dict]
    # per-seq positions
    positions: Dict[int, Optional[dict]]
    # ADocument registry surface (typed leaf paths)
    registry: List[str]
    # ElemTable rows OWNED by this element (owner_id == eid)
    owned_rows: List[int]
    # inbound referrers (only with deep=True; None = not computed)
    referrers: Optional[dict] = None

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def _row_dict(row: tuple, index: Optional[int]) -> dict:
    orig, ce, me, ue, eid, own, part = (int(x) for x in row[:7])
    return {
        "index_in_table": index,
        "elem_id": eid, "original_id": orig,
        "creation_ep": ce, "modified_ep": me,
        "user_modified_ep": (None if ue == NO_EPISODE else ue),
        "owner_id": (None if own == INVALID_ID else own),
        "partition_id": part,
        # derived (the objlint ETR vocabulary)
        "renumbered": orig != eid,
        "created_at_birth": ce == 0,
        "usermod_never": ue == NO_EPISODE,
        "has_owner": own != INVALID_ID,
        "id_band": _band(eid),
        "episodes_all_equal": (ce == me == (ue if ue != NO_EPISODE else me)),
    }


def _header_summary(doc: RegDoc, eid: int) -> Optional[dict]:
    h = doc.decode_record(101, eid)
    if h is None:
        return None
    v = h.value or {}
    parents = (v.get("m_parents") or {}).get("value") or {}
    id_leaves = [{"path": lf.path, "value": lf.value}
                 for lf in doc.walker.leaves(v, "ElementHeader")
                 if isinstance(lf.value, int) and lf.value > 0]
    return {
        "clean": bool(h.clean),
        "abFlags4Bytes": v.get("m_abFlags4Bytes"),
        "visible_view_flags": (v.get("m_viewRules") or {}).get("m_nVisibleViewFlags"),
        "category_id": v.get("m_categroryId"),
        "family_id": v.get("m_familyId"),
        "owner_view_id": v.get("m_ownerViewId"),
        "bbox_present": v.get("m_pBBox") is not None,
        "regen_history_map_len": len(((v.get("m_regenHistory") or {}).get("m_historyMap") or [])),
        "deletion": list(parents.get("m_deletion") or []),
        "regen_only": list(parents.get("m_regenOnly") or []),
        "appearance_parents": list(parents.get("m_appearanceParents") or []),
        "regen_wildcards_len": len(parents.get("m_regenWildcards") or []),
        "non_determ_regen_children_len": len(parents.get("m_nonDetermRegenChildren") or []),
        "dependency": list(parents.get("m_dependency") or [])[:8]
        if isinstance(parents.get("m_dependency"), list) else parents.get("m_dependency"),
        "self_in_deletion": eid in (parents.get("m_deletion") or []),
        "positive_id_leaves": id_leaves,
    }


def _object_summary(doc: RegDoc, eid: int) -> Optional[dict]:
    o = doc.decode_record(102, eid)
    if o is None:
        return None
    v = o.value or {}
    return {
        "clean": bool(o.clean),
        "class": doc.class_of(eid),
        "m_id": v.get("m_id"),
        "m_id_equals_record_id": v.get("m_id") == eid,
        "m_famId": v.get("m_famId"),
        "seq103_class": (doc.dec.class_name(doc.record(103, eid).class_id)
                         if doc.record(103, eid) is not None else None),
        "seq103_payload_len": (doc.record(103, eid).body_size
                               if doc.record(103, eid) is not None else None),
    }


def _positions(doc: RegDoc, eid: int) -> Dict[int, Optional[dict]]:
    runs102 = unit0_runs(doc, 102, class_names=False)
    out: Dict[int, Optional[dict]] = {}
    for s in SEQS:
        i = doc.record_index(s, eid)
        recs = doc.host_records(s)
        if i is None:
            out[s] = None
            continue
        r = recs[i]
        # block within the seq run
        acc = 0
        blk = (-1, 0)
        seq_blocks = [b for b in doc.unit0_blocks if b.seq == s]
        for j, b in enumerate(seq_blocks):
            if acc <= r.seg_offset < acc + len(b.data):
                blk = (j, len(seq_blocks))
                break
            acc += len(b.data)
        entry = {
            "index": i, "total": len(recs), "seg_offset": r.seg_offset,
            "block": [blk[0] + 1, blk[1]],
            "is_last_record": i == len(recs) - 1,
            "prev_id": int(recs[i - 1].elem_id) if i > 0 else None,
            "next_id": int(recs[i + 1].elem_id) if i + 1 < len(recs) else None,
            "class": doc.dec.class_name(r.class_id), "framed_len": None,
            "stamp": (r.stamp if s != 101 else None), "body_size": r.body_size,
        }
        if s == 102:
            run = next((k for k in runs102 if k.start <= i < k.end), None)
            if run is not None:
                entry["run_index"] = run.index
                entry["run_of"] = len(runs102)
                entry["run_span"] = [run.start, run.end - 1]
                entry["run_modal_modified_ep"] = run.modal_modified_ep
                entry["run_id_range"] = [run.id_min, run.id_max]
        out[s] = entry
    return out


def registration_of(doc_or_path, eid: int, *, deep: bool = False,
                    referrer_state: Optional[dict] = None) -> Registration:
    """The complete registration record of element ``eid`` in a file.

    ``deep=True`` also computes the typed inbound-referrer set over EVERY
    host + embedded element record (minutes on a large file); pass a
    precomputed ``referrer_state`` ({eid: set(referrers)}) to reuse one.
    """
    doc = doc_or_path if isinstance(doc_or_path, RegDoc) else RegDoc(str(doc_or_path))
    eid = int(eid)
    row = doc.row(eid)
    row_index = None
    if row is not None:
        for i, r in enumerate(doc.elemtable["records"]):
            if int(r[4]) == eid:
                row_index = i
                break
    rowd = _row_dict(row, row_index) if row is not None else None
    owned = [int(r[4]) for r in doc.elemtable["records"] if int(r[5]) == eid]
    reg = Registration(
        file=os.path.relpath(doc.path, ROOT),
        elem_id=eid,
        class_name=doc.class_of(eid),
        row=rowd,
        header=_header_summary(doc, eid),
        object=_object_summary(doc, eid),
        positions=_positions(doc, eid),
        registry=(doc.adoc_surface([eid]).get(eid) or []),
        owned_rows=owned,
    )
    if referrer_state is not None:
        reg.referrers = {"typed_inbound": sorted(int(x) for x in referrer_state.get(eid, ()))}
    elif deep:
        reg.referrers = {"typed_inbound": sorted(inbound_referrers(doc, {eid}).get(eid, set()))}
    return reg


def inbound_referrers(doc: RegDoc, targets: Iterable[int], *,
                      include_embedded: bool = True) -> Dict[int, Set[int]]:
    """{target: set(referrer element ids)} -- every element whose decoded
    seq-101/102/103 records hold a schema-TYPED ElementId leaf equal to a
    target (its own self-references excluded).  Walks unit 0 and, when
    ``include_embedded``, every embedded-document unit too (typed, so the
    small ids of settings singletons produce no false positives)."""
    want = {int(t) for t in targets}
    out: Dict[int, Set[int]] = {t: set() for t in want}
    dec = doc.dec
    walker = doc.walker
    with open_rvt(doc.path) as f:
        blocks = sorted(StreamWalker(f.logical(doc._pname or f.partition_streams()[0]),
                                     inflate=True, keep_data=True).blocks,
                        key=lambda b: b.hdr_offset)
    for s in SEQS:
        seg = b"".join(b.data for b in blocks
                       if b.seq == s and (include_embedded or b.unit == 0))
        for r in iter_records(seg, s):
            if r.elem_id < 0 or r.body_size < 2:
                continue
            src = int(r.elem_id)
            cname = "ElementHeader" if s == 101 else dec.class_name(r.class_id)
            try:
                got = dec.decode_record(r.class_id, r.payload)
            except Exception:
                continue
            for lf in walker.leaves(got.value or {}, cname):
                v = lf.value
                if v in want and v != src:
                    out[v].add(src)
    return out


# ===========================================================================
# 5. diffing two registrations
# ===========================================================================

def diff_registrations(a: Registration, b: Registration, *,
                       ignore_ids: bool = True) -> List[dict]:
    """Field-level diff of two registrations (dimension, a_value, b_value).

    ``ignore_ids`` skips the leaves that are DEFINED to differ when the
    element sits at a different id (its own row/record/self-entry ids)."""
    out: List[dict] = []

    def cmp(dim: str, x, y):
        if x != y:
            out.append({"dimension": dim, a.file: x, b.file: y})

    ra, rb = a.row or {}, b.row or {}
    for k in ("creation_ep", "modified_ep", "user_modified_ep", "owner_id", "partition_id",
              "renumbered", "created_at_birth", "usermod_never", "has_owner", "id_band",
              "episodes_all_equal", "original_id"):
        if ignore_ids and k == "original_id":
            cmp("ETR.original_id_equals_id", ra.get("original_id") == a.elem_id,
                rb.get("original_id") == b.elem_id)
            continue
        cmp(f"ETR.{k}", ra.get(k), rb.get(k))
    ha, hb = a.header or {}, b.header or {}
    for k in ("abFlags4Bytes", "visible_view_flags", "category_id", "family_id",
              "bbox_present", "regen_history_map_len", "regen_wildcards_len",
              "non_determ_regen_children_len"):
        cmp(f"HDR.{k}", ha.get(k), hb.get(k))
    for k in ("regen_only", "appearance_parents"):
        cmp(f"HDR.m_parents.{k}#len", len(ha.get(k) or []), len(hb.get(k) or []))
    cmp("HDR.m_parents.m_deletion#len", len(ha.get("deletion") or []), len(hb.get("deletion") or []))
    cmp("HDR.self_in_deletion", ha.get("self_in_deletion"), hb.get("self_in_deletion"))
    oa, ob = a.object or {}, b.object or {}
    for k in ("class", "m_id_equals_record_id", "m_famId", "seq103_class", "seq103_payload_len"):
        cmp(f"OBJ.{k}", oa.get(k), ob.get(k))
    pa, pb = a.positions.get(102) or {}, b.positions.get(102) or {}
    cmp("POS.seq102.is_last_record", pa.get("is_last_record"), pb.get("is_last_record"))
    cmp("POS.seq102.run_index_of", (pa.get("run_index"), pa.get("run_of")),
        (pb.get("run_index"), pb.get("run_of")))
    cmp("POS.seq102.run_modal_modified_ep", pa.get("run_modal_modified_ep"),
        pb.get("run_modal_modified_ep"))
    cmp("REG.surface_paths", [_norm_path(p) for p in a.registry],
        [_norm_path(p) for p in b.registry])
    cmp("ETR.owned_rows#len", len(a.owned_rows), len(b.owned_rows))
    return out


import re as _re
_IDX = _re.compile(r"\[(\d+)\]")


def _norm_path(p: str) -> str:
    """Wildcard container indices in a surface path (row order is not
    semantic) but keep positional UniqueElementsTracking slots."""
    if "UniqueElementsTracking.m_elemIds[" in p:
        return p
    return _IDX.sub("[*]", p)


# ===========================================================================
# 6. corpus mining (the six-sample census)
# ===========================================================================

def _corpus_docs(samples: Sequence[str]):
    """Yield (project, elemtable_rows_by_id, host_records_102) from the
    pre-extracted research corpus (fast path, no full-file re-read)."""
    for proj in samples:
        et = load_elemtable(proj)
        rows = {r.id: r for r in et.records}
        seg = load_segment(proj, 102)
        recs = [r for r in iter_records(seg, 102) if r.elem_id in rows]
        yield proj, et, rows, recs


def mine_record_order(samples: Sequence[str] = SAMPLES) -> dict:
    """The unit-0 record-order law across the samples: id-ascending runs
    grouped by MODIFIED episode, newest-modified group first."""
    dec = ObjectDecoder()
    rep = {}
    for proj, et, rows, recs in _corpus_docs(samples):
        ids = [int(r.elem_id) for r in recs]
        asc = sum(1 for a, b in zip(ids, ids[1:]) if b > a)
        bounds = [0] + [i + 1 for i in range(len(ids) - 1) if ids[i + 1] < ids[i]] + [len(ids)]
        modals = []
        pure = 0
        for k in range(len(bounds) - 1):
            a, b = bounds[k], bounds[k + 1]
            me = collections.Counter(rows[e].modified_ep for e in ids[a:b])
            modal, n = me.most_common(1)[0]
            modals.append(modal)
            if len(me) == 1:
                pure += 1
        nondesc = sum(1 for a, b in zip(modals, modals[1:]) if b > a)
        # where do the classes of interest sit (which run / episode group)?
        cls_pos = collections.defaultdict(list)
        for i, r in enumerate(recs):
            nm = dec.class_name(r.class_id)
            if nm in ("PenWidthTableElem", "AllProjectPhases", "UnitsElem"):
                cls_pos[nm].append({"index": i, "id": int(r.elem_id),
                                    "row_modified_ep": rows[r.elem_id].modified_ep,
                                    "row_creation_ep": rows[r.elem_id].creation_ep})
        rep[proj] = {
            "host_records": len(ids),
            "adjacent_id_ascending_fraction": round(asc / max(1, len(ids) - 1), 5),
            "exactly_id_sorted": ids == sorted(ids),
            "id_ascending_runs": len(modals),
            "single_episode_runs": pure,
            "run_modal_episodes_head": modals[:10],
            "run_modal_episodes_tail": modals[-5:],
            "runs_modal_episode_non_descending_pairs": nondesc,
            "runs_modal_episode_descending": nondesc == 0,
            "max_modified_ep": et.max_episode(),
            "sample_singleton_positions": {k: v[:4] for k, v in cls_pos.items()},
        }
    return rep


def _row_facts(row) -> dict:
    return {
        "created_at_birth": row.creation_ep == 0,
        "id_band": _band(row.id),
        "renumbered": row.original_id != row.id,
        "has_owner": row.owner_id != INVALID_ID,
        "usermod_never": row.user_modified_ep == NO_EPISODE,
        "partition": row.partition_id,
        "ce_le_me": row.creation_ep <= row.modified_ep,
    }


def mine_elemtable_invariants(samples: Sequence[str] = SAMPLES,
                              classes: Sequence[str] = (), *,
                              project_pen_only: bool = True) -> dict:
    """Per class, the ElemTable-row facts across every host specimen in the
    samples: creation-episode-0 rate, id bands, renumbering, ownership,
    user-modified-never rate, partition, plus the RUN-position law (fraction
    of specimens sitting in the newest-modified run / in a run whose modal
    episode equals their own modified_ep).  ``project_pen_only`` restricts
    PenWidthTableElem to the m_famId == -1 project table (the family-scoped
    tables are a different cohort)."""
    dec = ObjectDecoder()
    want = set(classes) if classes else None
    acc: Dict[str, dict] = collections.defaultdict(lambda: {
        "specimens": 0, "files": collections.Counter(),
        "created_at_birth": 0, "id_band": collections.Counter(),
        "renumbered": 0, "has_owner": 0, "usermod_never": 0,
        "partition": collections.Counter(), "ce_le_me": 0,
        "owner_classes": collections.Counter(),
        "creation_ep_hist": collections.Counter(),
        "in_run_matching_own_modified_ep": 0,
        "creation_lt_modified": 0,
        "example_rows": [],
    })
    for proj, et, rows, recs in _corpus_docs(samples):
        ids = [int(r.elem_id) for r in recs]
        # run map: record index -> modal modified_ep of its run
        bounds = [0] + [i + 1 for i in range(len(ids) - 1) if ids[i + 1] < ids[i]] + [len(ids)]
        run_modal_at: Dict[int, int] = {}
        for k in range(len(bounds) - 1):
            a, b = bounds[k], bounds[k + 1]
            modal = collections.Counter(rows[e].modified_ep for e in ids[a:b]).most_common(1)[0][0]
            for j in range(a, b):
                run_modal_at[j] = modal
        cls_at = {}
        for i, r in enumerate(recs):
            cls_at[int(r.elem_id)] = (i, dec.class_name(r.class_id))
        # class of every host element for owner-class resolution
        for i, r in enumerate(recs):
            eid = int(r.elem_id)
            nm = cls_at[eid][1]
            if want is not None and nm not in want:
                continue
            row = rows[eid]
            if project_pen_only and nm == "PenWidthTableElem":
                v = dec.decode_record(r.class_id, r.payload).value or {}
                if int(v.get("m_famId", -1)) != -1:
                    continue
            f = _row_facts(row)
            a = acc[nm]
            a["specimens"] += 1
            a["files"][proj] += 1
            a["created_at_birth"] += int(f["created_at_birth"])
            a["id_band"][f["id_band"]] += 1
            a["renumbered"] += int(f["renumbered"])
            a["has_owner"] += int(f["has_owner"])
            a["usermod_never"] += int(f["usermod_never"])
            a["partition"][f["partition"]] += 1
            a["ce_le_me"] += int(f["ce_le_me"])
            a["creation_lt_modified"] += int(row.creation_ep < row.modified_ep)
            a["creation_ep_hist"][min(row.creation_ep, 3)] += 1   # 0,1,2,3+
            if f["has_owner"] and row.owner_id in cls_at:
                a["owner_classes"][cls_at[row.owner_id][1]] += 1
            if run_modal_at.get(i) == row.modified_ep:
                a["in_run_matching_own_modified_ep"] += 1
            if len(a["example_rows"]) < 3:
                a["example_rows"].append({"file": proj, "id": eid,
                                          "row": [int(row.original_id), int(row.creation_ep),
                                                  int(row.modified_ep),
                                                  (None if row.user_modified_ep == NO_EPISODE
                                                   else int(row.user_modified_ep)),
                                                  int(row.id),
                                                  (None if row.owner_id == INVALID_ID else int(row.owner_id)),
                                                  int(row.partition_id)]})
    # finalize
    out = {}
    for nm, a in acc.items():
        n = a["specimens"]
        out[nm] = {
            "specimens": n, "files": dict(a["files"]),
            "created_at_birth_rate": round(a["created_at_birth"] / n, 4),
            "creation_ep_hist_0_1_2_3plus": {str(k): v for k, v in sorted(a["creation_ep_hist"].items())},
            "id_bands": dict(a["id_band"].most_common()),
            "renumbered_rate": round(a["renumbered"] / n, 4),
            "has_owner_rate": round(a["has_owner"] / n, 4),
            "owner_classes": dict(a["owner_classes"].most_common(4)),
            "usermod_never_rate": round(a["usermod_never"] / n, 4),
            "partitions": dict(a["partition"]),
            "creation_le_modified_rate": round(a["ce_le_me"] / n, 4),
            "creation_lt_modified_rate": round(a["creation_lt_modified"] / n, 4),
            "in_run_matching_own_modified_ep_rate": round(a["in_run_matching_own_modified_ep"] / n, 4),
            "examples": a["example_rows"],
        }
    return out


# ===========================================================================
# 7. reporting helpers
# ===========================================================================

def registration_table(regs: Sequence[Registration]) -> List[List[str]]:
    """Rows of a compact comparison table (dimension x file)."""
    def rowfield(r: Registration, k: str):
        return (r.row or {}).get(k)

    def pos102(r: Registration, k: str):
        return (r.positions.get(102) or {}).get(k)

    def hdr(r: Registration, k: str):
        return (r.header or {}).get(k)

    dims: List[Tuple[str, Any]] = [
        ("elem_id", lambda r: r.elem_id),
        ("class", lambda r: r.class_name),
        ("ETR.original_id", lambda r: rowfield(r, "original_id")),
        ("ETR.creation_ep", lambda r: rowfield(r, "creation_ep")),
        ("ETR.modified_ep", lambda r: rowfield(r, "modified_ep")),
        ("ETR.user_modified_ep", lambda r: rowfield(r, "user_modified_ep")),
        ("ETR.owner_id", lambda r: rowfield(r, "owner_id")),
        ("ETR.partition_id", lambda r: rowfield(r, "partition_id")),
        ("ETR.renumbered(orig!=id)", lambda r: rowfield(r, "renumbered")),
        ("ETR.created_at_birth", lambda r: rowfield(r, "created_at_birth")),
        ("ETR.usermod_never", lambda r: rowfield(r, "usermod_never")),
        ("ETR.id_band", lambda r: rowfield(r, "id_band")),
        ("ETR.index_in_table/of", lambda r: (rowfield(r, "index_in_table"))),
        ("HDR.abFlags4Bytes", lambda r: hdr(r, "abFlags4Bytes")),
        ("HDR.regen_history_map_len", lambda r: hdr(r, "regen_history_map_len")),
        ("HDR.deletion", lambda r: hdr(r, "deletion")),
        ("HDR.regen_only", lambda r: hdr(r, "regen_only")),
        ("HDR.appearance_parents", lambda r: hdr(r, "appearance_parents")),
        ("OBJ.m_id==record_id", lambda r: (r.object or {}).get("m_id_equals_record_id")),
        ("OBJ.seq103_class", lambda r: (r.object or {}).get("seq103_class")),
        ("POS.seq102.index/total", lambda r: (pos102(r, "index"), pos102(r, "total"))),
        ("POS.seq102.is_last_record", lambda r: pos102(r, "is_last_record")),
        ("POS.seq102.run(index/of)", lambda r: (pos102(r, "run_index"), pos102(r, "run_of"))),
        ("POS.seq102.run_modal_modified_ep", lambda r: pos102(r, "run_modal_modified_ep")),
        ("POS.seq102.prev_id/next_id", lambda r: (pos102(r, "prev_id"), pos102(r, "next_id"))),
        ("REG.surface", lambda r: [_norm_path(p) for p in r.registry]),
        ("ETR.owned_rows", lambda r: r.owned_rows),
    ]
    table = [["dimension"] + [r.file.split("/")[-1] for r in regs]]
    for name, fn in dims:
        table.append([name] + [_short(fn(r)) for r in regs])
    return table


def _short(v) -> str:
    if isinstance(v, list) and v and isinstance(v[0], str) and len(str(v)) > 90:
        return json.dumps([s.split("->")[-1][-60:] for s in v])
    s = json.dumps(v, default=str) if not isinstance(v, str) else v
    return s if len(s) <= 110 else s[:107] + "..."


def print_table(table: List[List[str]]) -> None:
    widths = [max(len(str(row[i])) for row in table) for i in range(len(table[0]))]
    for row in table:
        print("  " + "  ".join(str(c).ljust(min(w, 60)) for c, w in zip(row, widths)))


# ===========================================================================
# 8. demo / CLI
# ===========================================================================

DEMO_FILES = {
    "K1 (viewer PASS, Autodesk registration of pen table id 2)":
        (os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt"), 2),
    "X0 (FAIL: same pen table via OUR add path at 1,500,000)":
        (os.path.join(ROOT, "experiments", "genesis", "controls", "X0.rvt"), 1_500_000),
    "V20 (viewer PASS: the proven FamilyInstance add path, id 1,472,525)":
        (os.path.join(ROOT, "experiments", "acceptance", "V20_first_created_element.rvt"), 1_472_525),
}


def demo() -> int:
    regs = []
    for label, (path, eid) in DEMO_FILES.items():
        if not os.path.exists(path):
            print(f"missing: {path}")
            continue
        print(f"[registration_of] {os.path.relpath(path, ROOT)} id {eid} -- {label}")
        regs.append(registration_of(path, eid))
    if regs:
        print()
        print_table(registration_table(regs))
    if len(regs) >= 2:
        print("\n== diff K1 vs X0 (registration deltas, id-implied leaves ignored) ==")
        for d in diff_registrations(regs[0], regs[1]):
            print("   ", json.dumps(d, default=str))
    if len(regs) >= 3:
        print("\n== diff X0 vs V20 (what X0's registration does that the PROVEN path does not) ==")
        for d in diff_registrations(regs[1], regs[2]):
            print("   ", json.dumps(d, default=str))
    print("\n== record-order law of the demo files (unit-0 = runs by modified_ep, DESC) ==")
    for label, (path, _e) in DEMO_FILES.items():
        if os.path.exists(path):
            rl = run_law_report(RegDoc(path))
            print(f"   {os.path.basename(path)}: runs={rl['runs']} "
                  f"id-adjacent-ascending={rl['adjacent_id_ascending_fraction']} "
                  f"modal-episode-descending={rl['runs_modal_episode_descending']} "
                  f"first-run-ep={rl['first_run_modal_episode']} last-run-ep={rl['last_run_modal_episode']}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return demo()
    if argv[0] == "--mine":
        classes = list(GENESIS_SINGLETON_CLASSES) + list(PROVEN_INSTANCE_CLASSES)
        rep = {"record_order": mine_record_order(),
               "elemtable_invariants": mine_elemtable_invariants(classes=classes)}
        json.dump(rep, sys.stdout, indent=1)
        print()
        return 0
    if argv[0] == "--runs":
        json.dump(run_law_report(RegDoc(argv[1])), sys.stdout, indent=1)
        print()
        return 0
    path = argv[0]
    ids = [int(x) for x in argv[1:]] or [2]
    doc = RegDoc(path)
    regs = [registration_of(doc, i) for i in ids]
    print_table(registration_table(regs))
    print(json.dumps([r.to_json() for r in regs], indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
