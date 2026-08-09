"""Element-creation planner: turn "add a wall / a family instance" into the
exact set of decoded records that a native ``.rvt`` writer must emit.

This is the MUTATION layer described in ``docs/writer/mutation-plan.md``.
It works entirely in DECODED-DICT space (the objects produced by
:mod:`rvt.objects`): it loads a template document, clones real specimen
records, edits them for the new element, allocates ElementIds, and reports
which streams must be re-emitted (:meth:`Document.diff`).  Turning the
edited dicts back into bytes is the job of the parallel serializer
(``rvt.encode.encode_record``); this module calls it if importable and
otherwise stops at the dict/plan stage.

Public API::

    doc = Document.load("racbasicsampleproject")        # template document
    wall = doc.add_wall(level_id=311, wall_type_id=232827,
                        p0=(10, 20), p1=(30, 20), top_level_id=245423)
    inst = doc.add_family_instance(symbol_id=754016, level_id=311,
                                   position=(4, 8, 0), rotation=1.5708)
    doc.check_references(wall)      # -> [] (every referenced id exists)
    for change in doc.diff():        # every stream that must be re-emitted
        print(change.stream, change.action)
    plan = doc.plan()               # JSON-able description of the mutation

Everything here is derived from the corpus decoders — see
``docs/writer/specimens/`` for annotated real specimens and
``docs/writer/template-catalog.md`` for the ids usable per template.

``python -m rvt.mutate [project]`` runs a demonstration: it builds a new
wall and a new family instance against the sample templates and prints the
plan.  Set ``RVT_SEG_CACHE`` to a directory to cache the (slow to build)
concatenated element segments between runs.
"""
from __future__ import annotations

import copy
import json
import math
import os
import struct
import sys
import zlib
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Optional

from .objects import ObjectDecoder, Record, iter_records, load_segment
from .elemtable import ElemTable, load_elemtable

# ---------------------------------------------------------------------------
# constants (all verified in docs/writer/mutation-plan.md)
# ---------------------------------------------------------------------------

CLASS_ELEMENT_HEADER = 0x05E5     # seq-101 record class (ElementHeader)
CLASS_SERIALIZED_DUMMY = 0x0F2C   # seq-103 placeholder rep
CLASS_GELEMENT = 0x089E           # seq-103 cached geometry rep
CLASS_SWALL = 0x0F02
CLASS_FAMILY_INSTANCE = 0x07C5
CLASS_ELECTRICAL_SYSTEM = 0x0D87   # RbsElectricalSystem (circuits)

#: seq-103 SerializedDummy record: psize 2 (bare class id, empty object)
DUMMY_STAMP = zlib.adler32(struct.pack("<H", CLASS_SERIALIZED_DUMMY)) & 0xFFFFFFFF
assert DUMMY_STAMP == 0x0069003C  # corpus constant, see mutation-plan §4.1

#: built-in categories used by the recipes
OST_Walls = -2000011
OST_Doors = -2000023
OST_ElectricalEquipment = -2001040
OST_ElectricalFixtures = -2001060
OST_LightingFixtures = -2001120

#: known BuiltInParameter ids on walls (racbasic SWall specimen 422243)
BIP_WALL_USER_HEIGHT_PARAM = -1001105   # unconnected height (ft)
BIP_WALL_HEIGHT = -1001101              # computed height (ft) [hypothesis]

STREAMS_TOUCHED = (
    "Global/ElemTable", "Partitions/<N>", "Global/DocumentIncrementTable",
    "Global/History", "BasicFileInfo", "Global/Latest",
)


# ---------------------------------------------------------------------------
def record_stamp(class_id: int, obj_bytes: bytes = b"") -> int:
    """The u32 `stamp` in a seq-102/103 record header.

    SOLVED (mutation-planner): stamp == zlib Adler-32 of the record payload
    (``u16 class_id + object bytes``).  Verified on 287,441 records across
    racbasic / rme / racadv with zero exceptions; the id -1 save-unit
    sentinel's stamp 1 == adler32(b"") and the SerializedDummy constant
    0x0069003C == adler32(2c 0f).  Not present in seq-101 headers.
    """
    return zlib.adler32(struct.pack("<H", class_id) + obj_bytes) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
@dataclass
class ElemRecPlan:
    """The 40-byte ``ElemRec`` a new element inserts into ``Global/ElemTable``."""
    elem_id: int
    original_id: int
    creation_ep: int
    modified_ep: int
    user_modified_ep: int
    owner_id: int = -1
    partition_id: int = 0

    def pack(self) -> bytes:
        own = self.owner_id if self.owner_id >= 0 else 0xFFFFFFFFFFFFFFFF
        um = self.user_modified_ep if self.user_modified_ep >= 0 else 0xFFFFFFFF
        return struct.pack("<QIIIQQI", self.original_id, self.creation_ep,
                           self.modified_ep, um, self.elem_id, own,
                           self.partition_id)

    def to_json(self) -> dict:
        return {"elem_id": self.elem_id, "original_id": self.original_id,
                "creation_ep": self.creation_ep, "modified_ep": self.modified_ep,
                "user_modified_ep": self.user_modified_ep, "owner_id": self.owner_id,
                "partition_id": self.partition_id,
                "raw_40_bytes_hex": self.pack().hex(" ")}


@dataclass
class NewElement:
    """One new element = its three partition records + its ElemTable row."""
    elem_id: int
    kind: str                          # 'wall' | 'family_instance' | ...
    class_name: str                    # concrete seq-102 class
    class_id: int
    header: dict                       # seq-101 ElementHeader object (decoded dict)
    obj: dict                          # seq-102 element object (decoded dict)
    rep: Optional[dict]                # seq-103 GElement dict, or None => SerializedDummy
    elemrec: ElemRecPlan
    template_id: int                   # the specimen this was cloned from
    notes: list = dc_field(default_factory=list)

    @property
    def rep_class_id(self) -> int:
        return CLASS_GELEMENT if self.rep is not None else CLASS_SERIALIZED_DUMMY

    def records(self) -> list:
        """The three (seq, class_id, object-dict) records this element needs."""
        return [
            (101, CLASS_ELEMENT_HEADER, self.header),
            (102, self.class_id, self.obj),
            (103, self.rep_class_id, self.rep if self.rep is not None else {}),
        ]

    def to_json(self) -> dict:
        return {
            "elem_id": self.elem_id, "kind": self.kind,
            "class": self.class_name, "class_id": f"{self.class_id:#06x}",
            "template_id": self.template_id,
            "seq101_ElementHeader": self.header,
            "seq102_object": self.obj,
            "seq103": ({"class": "GElement", "value": self.rep} if self.rep is not None
                       else {"class": "SerializedDummy", "psize": 2,
                             "stamp": f"{DUMMY_STAMP:#010x}"}),
            "elemrec": self.elemrec.to_json(),
            "notes": self.notes,
        }


@dataclass
class StreamChange:
    stream: str
    action: str      # 'insert-records' | 'append-row' | 'rewrite' | 'update-field' | 'copy'
    reason: str
    detail: dict = dc_field(default_factory=dict)

    def to_json(self) -> dict:
        return {"stream": self.stream, "action": self.action, "reason": self.reason,
                "detail": self.detail}


# ---------------------------------------------------------------------------
class Document:
    """In-memory view of a template ``.rvt`` for element-creation planning.

    Loads: the three concatenated element segments (all save units) with an
    id -> record index per seq, the ``Global/ElemTable``, and the canonical
    schema decoder.  Provides id allocation, specimen cloning and the diff.
    """

    def __init__(self, project: str, segments: dict, elemtable: ElemTable,
                 decoder: Optional[ObjectDecoder] = None):
        self.project = project
        self.dec = decoder or ObjectDecoder()
        self.seg = segments
        self.idx: dict[int, dict[int, Record]] = {s: {} for s in (101, 102, 103)}
        for s, buf in segments.items():
            for r in iter_records(buf, s):
                if r.elem_id >= 0:
                    self.idx[s][r.elem_id] = r
        self.et = elemtable
        self.et_by_id = {r.id: r for r in elemtable.records}
        self.new_elements: list[NewElement] = []
        self._decoded: dict[tuple[int, int], Any] = {}
        # id allocator: continue from the ElemTable watermark (IdentifierSource.m_last)
        self.last_issued_id = max(elemtable.footer.last_id if elemtable.footer else 0,
                                  max(self.et_by_id) if self.et_by_id else 0)
        # episode allocator: the new save is a new episode
        self.current_episode = max((r.modified_ep for r in elemtable.records), default=-1)
        self.new_episode = self.current_episode + 1

    # -- construction ----------------------------------------------------
    @classmethod
    def load(cls, project: str, cache_dir: Optional[str] = None) -> "Document":
        """Load from the pre-extracted research corpus (extracted/<project>/).
        For an arbitrary .rvt on disk use :meth:`from_file`."""
        cache_dir = cache_dir or os.environ.get("RVT_SEG_CACHE")
        segs = {s: load_segment(project, s, cache_dir) for s in (101, 102, 103)}
        return cls(project, segs, load_elemtable(project))

    @classmethod
    def from_file(cls, rvt_path: str) -> "Document":
        """Load a Document directly from ANY .rvt file on disk (no corpus).

        Builds everything the authoring API needs from the file itself:
        the schema from its own ``Formats/Latest``, the element-data segments
        (seq 101/102/103) by walking every ``Partitions/<N>`` stream, and the
        ``Global/ElemTable``. This is the entry point the plugin / a user's
        own template project must use.
        """
        from .container import open_rvt
        from .elemtable import inflate_global_stream, parse_elemtable
        from .objects import ObjectDecoder
        from .partitions import StreamWalker
        from .schema import parse as parse_schema

        name = os.path.splitext(os.path.basename(rvt_path))[0]
        segs = {101: bytearray(), 102: bytearray(), 103: bytearray()}
        with open_rvt(rvt_path) as f:
            for pn in f.partition_streams():
                walker = StreamWalker(f.logical(pn), inflate=True, keep_data=True)
                if walker.errors:
                    raise RuntimeError(f"{pn}: walker errors {walker.errors[:3]}")
                for b in sorted(walker.blocks, key=lambda x: x.hdr_offset):
                    if b.seq in segs and b.data:
                        segs[b.seq] += b.data
            et_raw = f.raw("Global/ElemTable")
            st = inflate_global_stream(et_raw)
            table = parse_elemtable(st.payload, name)
            table.stream = st
            schema = parse_schema(f.inflate("Formats/Latest"), source=rvt_path)
        doc = cls(name, {k: bytes(v) for k, v in segs.items()}, table,
                  ObjectDecoder(schema))
        doc.source_path = rvt_path
        return doc

    # -- lookup ------------------------------------------------------------
    def exists(self, eid: int) -> bool:
        return eid in self.idx[102] or eid in self.et_by_id

    def in_host_document(self, eid: int) -> bool:
        """True if the element belongs to the host document (unit 0 == ElemTable)."""
        return eid in self.et_by_id

    def record(self, eid: int, seq: int = 102) -> Optional[Record]:
        return self.idx[seq].get(eid)

    def decode(self, eid: int, seq: int = 102):
        key = (eid, seq)
        if key not in self._decoded:
            r = self.idx[seq].get(eid)
            self._decoded[key] = self.dec.decode_record(r.class_id, r.payload) if r else None
        return self._decoded[key]

    def value(self, eid: int, seq: int = 102) -> Optional[dict]:
        o = self.decode(eid, seq)
        return o.value if o and (o.clean or o.stub) else (o.value if o else None)

    def class_of(self, eid: int, seq: int = 102) -> Optional[str]:
        r = self.idx[seq].get(eid)
        return self.dec.class_name(r.class_id) if r else None

    def category_of(self, eid: int) -> Optional[int]:
        h = self.decode(eid, 101)
        return h.value.get("m_categroryId") if h and h.clean else None

    def ids_of_class(self, name: str, host_only: bool = True) -> list[int]:
        cd = self.dec.schema.by_name.get(name)
        if cd is None:
            return []
        out = [i for i, r in self.idx[102].items() if r.class_id == cd.type_id]
        if host_only:
            out = [i for i in out if i in self.et_by_id]
        return out

    # -- catalog ------------------------------------------------------------
    def levels(self) -> list[dict]:
        """Host-document levels: id, name, elevation (ft), attr (type) id."""
        out = []
        for lv in self.ids_of_class("Level"):
            v = self.value(lv) or {}
            # skip levels owned by an unplaced/in-place family (e.g. racbasic
            # 800333 'Level 1' owned by family 800214): only free datums
            if v.get("m_unplacedOwnerId", -1) != -1:
                continue
            out.append({"id": lv, "name": v.get("m_text"),
                        "elevation_ft": self._level_elevation(lv),
                        "attr_id": v.get("m_attrId"),
                        "is_building_story": v.get("m_isBuildingStory")})
        out.sort(key=lambda r: (r["elevation_ft"], r["id"]))
        return out

    def symbols(self, category: Optional[int] = None) -> list[dict]:
        """Host-document FamilySymbols: id, name, family id/name, category."""
        fam_name = {}
        for fid in self.ids_of_class("Family"):
            fam_name[fid] = (self.value(fid) or {}).get("m_name")
        out = []
        for sid in self.ids_of_class("FamilySymbol"):
            cat = self.category_of(sid)
            if category is not None and cat != category:
                continue
            v = self.value(sid) or {}
            si = ((v.get("m_symbolInfo") or {}).get("value") or {})
            fid = v.get("m_familyId")
            out.append({"symbol_id": sid, "symbol_name": si.get("m_name"),
                        "family_id": fid, "family_name": fam_name.get(fid),
                        "category": cat})
        return out

    # -- allocation --------------------------------------------------------
    def next_id(self) -> int:
        """Allocate the next ElementId: continue from the id watermark.

        Revit issues ids monotonically; the ElemTable footer
        ``IdentifierSource.m_last`` records the highest id ever issued (can
        exceed the current max id when elements were deleted, racbasic:
        watermark 1,098,947 vs max id 1,098,851).  New ids continue above it
        and the watermark is bumped on write.
        """
        self.last_issued_id += 1
        return self.last_issued_id

    def _new_elemrec(self, eid: int) -> ElemRecPlan:
        return ElemRecPlan(elem_id=eid, original_id=eid,
                           creation_ep=self.new_episode,
                           modified_ep=self.new_episode,
                           user_modified_ep=self.new_episode)

    # -- specimen selection --------------------------------------------------
    def straight_walls(self) -> list[int]:
        """Host-document straight (GLine-driven, non-curtain) SWall ids."""
        out = []
        for w in self.ids_of_class("SWall"):
            v = self.value(w) or {}
            drv = ((v.get("m_pCurveDriver") or {}).get("value") or {})
            crv = (drv.get("m_pCrv") or {})
            if crv.get("ptr_class") != "GLine":
                continue
            hom = ((v.get("m_hostObjMiscData") or {}).get("value") or {})
            if hom.get("m_oCGDrivers"):      # curtain-grid driven wall
                continue
            out.append(w)
        return out

    def wall_types_with_instances(self) -> dict[int, list[int]]:
        """wall type id -> straight walls of that type (the clonable types)."""
        out: dict[int, list[int]] = {}
        for w in self.straight_walls():
            t = (self.value(w) or {}).get("m_WallAttributesId")
            out.setdefault(t, []).append(w)
        return out

    def _template_wall(self, wall_type_id: int) -> int:
        cand = self.wall_types_with_instances().get(wall_type_id) or []
        if cand:
            # smallest object = simplest wall (fewest joins / no sweeps)
            return min(cand, key=lambda w: self.record(w).body_size)
        raise LookupError(
            f"{self.project}: no straight SWall of wall type {wall_type_id} to clone; "
            f"clonable types: {sorted(self.wall_types_with_instances())} "
            "(pass template_id= to force a different specimen)")

    def _template_instance(self, symbol_id: int, category: Optional[int]) -> int:
        """Pick the best real instance to clone for ``symbol_id``.

        Strict priority (each pass is exhaustive before the next, so an
        unrelated free-standing element can never outrank a true instance of
        the requested symbol):
          1. an instance whose symbol IS ``symbol_id`` — free-standing wins,
             else a hosted one (hosting is stripped by the caller);
          2. any free-standing instance of the same CATEGORY (symbol==master);
          3. any FamilyInstance.
        """
        insts = self.ids_of_class("FamilyInstance")
        info = []
        for i in insts:
            v = self.value(i)
            if not v:
                continue
            ii = (v.get("m_pInstanceInfo") or {}).get("value") or {}
            sid, msid = ii.get("m_symbolId"), v.get("m_masterSymbolId")
            free = (v.get("m_hostId") in (-1, None)) and not v.get("m_workPlaneBased")
            info.append((i, sid, msid, free))
        # pass 1: exact symbol match
        exact = [(i, free) for i, sid, msid, free in info
                 if sid == symbol_id or msid == symbol_id]
        if exact:
            for i, free in exact:
                if free:
                    return i
            return exact[0][0]
        # pass 2: free-standing, same category, symbol == master
        if category is not None:
            for i, sid, msid, free in info:
                if free and sid == msid and self.category_of(i) == category:
                    return i
        # pass 3: any free-standing symbol==master, then anything
        for i, sid, msid, free in info:
            if free and sid == msid:
                return i
        if insts:
            return insts[0]
        raise LookupError(f"{self.project}: template has no FamilyInstance specimen")

    @staticmethod
    def _scrub_connectors(obj: dict) -> int:
        """Reset a cloned element's connectors to the UNCONNECTED state.

        A cloned equipment instance would otherwise keep ``m_arrRefs`` links
        pointing at the template's circuits (one-way dangling references) and
        stale downstream-circuit ids. New gear must start with free connectors,
        ready to be circuited. Returns the number of connectors scrubbed.
        """
        cm = obj.get("m_pConnectorManager")
        holder = cm.get("value") if isinstance(cm, dict) else None
        if not isinstance(holder, dict):
            return 0
        holder["m_setDeletedConnectors"] = []
        n = 0
        for c in holder.get("m_connPtrArray") or []:
            cv = c.get("value") if isinstance(c, dict) else None
            if not isinstance(cv, dict):
                continue
            if "m_arrRefs" in cv:
                cv["m_arrRefs"] = []
            for m in cv.get("m_modifiers") or []:
                mv = m.get("value") if isinstance(m, dict) else None
                if isinstance(mv, dict) and "m_idDownstreamCircuit" in mv:
                    mv["m_idDownstreamCircuit"] = -1
            n += 1
        return n

    def _level_elevation(self, level_id: int) -> float:
        v = self.value(level_id)
        if not v:
            raise LookupError(f"level {level_id} not found in {self.project}")
        surf = v.get("m_pSurface")
        if isinstance(surf, dict) and isinstance(surf.get("value"), dict):
            org = surf["value"].get("m_origin")
            if org:
                return float(org[2])
        return 0.0

    # -- element creation ----------------------------------------------
    def add_wall(self, level_id: int, wall_type_id: int, p0, p1,
                 height: Optional[float] = None,
                 top_level_id: Optional[int] = None,
                 template_id: Optional[int] = None,
                 phase_id: Optional[int] = None) -> NewElement:
        """Plan a new straight wall (``SWall``) on the wall line p0->p1 (ft).

        Every field of the new records is documented, with its source, in
        ``docs/writer/mutation-plan.md`` §5.  The object is a clone of a real
        SWall of ``wall_type_id`` from this template (so its compound-structure
        driven ref-face offsets, param set and geometry steps are correct)
        with identity, level, type and location-line fields rewritten.
        """
        for eid, what in ((level_id, "level_id"), (wall_type_id, "wall_type_id")):
            if not self.exists(eid):
                raise LookupError(f"{what} {eid} does not exist in template {self.project}")
        if top_level_id is not None and not self.exists(top_level_id):
            raise LookupError(f"top_level_id {top_level_id} not in template")
        tpl = template_id or self._template_wall(wall_type_id)
        eid = self.next_id()

        x0, y0 = float(p0[0]), float(p0[1])
        x1, y1 = float(p1[0]), float(p1[1])
        length = math.hypot(x1 - x0, y1 - y0)
        if length <= 1e-6:
            raise ValueError("wall p0 == p1")
        dx, dy = (x1 - x0) / length, (y1 - y0) / length
        base_z = self._level_elevation(level_id)
        if top_level_id is not None:
            wall_h = self._level_elevation(top_level_id) - base_z
        else:
            wall_h = float(height) if height else 8.0
        if wall_h <= 0:
            raise ValueError(f"non-positive wall height {wall_h}")

        # --- seq 102: clone + rewrite ------------------------------------
        tv = copy.deepcopy(self.value(tpl))
        told = self._wall_geometry(tv)
        obj = tv
        obj["m_id"] = eid
        obj["m_assocLevelId"] = level_id                       # base constraint
        obj["m_upToLevelId"] = top_level_id if top_level_id is not None else -1
        obj["m_WallAttributesId"] = wall_type_id
        obj["m_famId"] = -1
        obj["m_designOptionId"] = -1
        if phase_id is not None:
            obj["m_createdPhaseId"] = phase_id
        obj["m_demolishedPhaseId"] = -1
        obj["m_embeddedTo"] = []
        # location line: GLine origin p0, unit direction, params [0, length]
        drv = ((obj.get("m_pCurveDriver") or {}).get("value") or {})
        crv = (drv.get("m_pCrv") or {}).get("value") or {}
        crv["m_origin"] = [x0, y0, base_z]
        crv["m_dirVec"] = [dx, dy, 0.0]
        crv["m_endParams"] = [0.0, length]
        # a brand-new wall is unjoined
        drv["m_sideJoins"] = []
        drv["m_controlJoinsSet"] = []
        drv["m_endJoins"] = drv.get("m_endJoins", [])[:0] if "m_endJoins" in drv else []
        drv["m_noJoinAtEnd"] = [False, False]
        drv["m_noJoinAtMidEnds"] = []
        drv["m_midParams"] = []
        # driven reference faces: rebuild each face plane for the new line,
        # preserving the template's perpendicular layer offset from the
        # location line (the compound-structure offsets are per wall type).
        self._rebuild_wall_faces(obj, told, (x0, y0, base_z), (dx, dy), length, wall_h)
        # height parameter (kept alongside the top constraint by Revit)
        self._set_param(obj, "m_pParamValueSetDouble", BIP_WALL_HEIGHT, wall_h)
        if top_level_id is None:
            self._set_param(obj, "m_pParamValueSetDouble", BIP_WALL_USER_HEIGHT_PARAM, wall_h)

        # --- seq 101: ElementHeader ------------------------------------
        header = copy.deepcopy(self.value(tpl, 101)) or {}
        header["m_regenHistory"] = {"m_historyMap": []}
        parents = ((header.get("m_parents") or {}).get("value")) or {}
        phase = obj.get("m_createdPhaseId", -1)
        deletion = [level_id]
        if top_level_id is not None:
            deletion.append(top_level_id)
        if phase not in (None, -1):
            deletion.append(phase)
        deletion += [wall_type_id, eid]
        parents.update({
            "m_deletion": sorted(set(deletion)),
            "m_regenOnly": parents.get("m_regenOnly", [30]),
            "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
            "m_dependencyParents": [], "m_deferredParents": [],
            "m_deferredPropagationParents": [], "m_computedParametersParents": [],
            "m_appearanceParents": sorted({p for p in (30, level_id, wall_type_id)}),
            "m_hasNonDetermRegenChildren": False,
        })
        if isinstance(header.get("m_parents"), dict):
            header["m_parents"]["value"] = parents
        # bounding box of the wall solid: line +/- half thickness, base..top
        thick = self._wall_thickness(told) or 0.5
        nx, ny = -dy, dx
        xs = [x0 + s * nx * thick / 2 for s in (-1, 1)] + [x1 + s * nx * thick / 2 for s in (-1, 1)]
        ys = [y0 + s * ny * thick / 2 for s in (-1, 1)] + [y1 + s * ny * thick / 2 for s in (-1, 1)]
        header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1,
                             "value": {"m_minmax": [[min(xs), min(ys), base_z],
                                                    [max(xs), max(ys), base_z + wall_h]]}}

        el = NewElement(eid, "wall", "SWall", CLASS_SWALL, header, obj, None,
                        self._new_elemrec(eid), tpl,
                        notes=[
                            "seq103 = SerializedDummy (no cached geometry): Revit must "
                            "regenerate the wall solid from m_geomSteps [acceptance test T1]; "
                            "fallback = clone-and-transform the template wall's GElement.",
                            f"cloned from wall {tpl} (type {self.value(tpl).get('m_WallAttributesId')})",
                        ])
        self.new_elements.append(el)
        return el

    def add_family_instance(self, symbol_id: int, level_id: int, position,
                            rotation: float = 0.0,
                            host_id: Optional[int] = None,
                            template_instance_id: Optional[int] = None,
                            phase_id: Optional[int] = None) -> NewElement:
        """Plan a new placed ``FamilyInstance`` of ``symbol_id`` at
        ``position`` (x, y, z in feet), rotated ``rotation`` radians about +Z,
        on ``level_id``.

        Free-standing pattern (verified in 202/495 racbasic instances):
        ``InstanceInfo.m_symbolId == m_masterSymbolId == symbol_id``,
        ``m_hostId = -1``, ``m_assocLevelId = level_id``.  Face-hosted
        equipment (all rme panelboards) instead needs ``host_id`` = an
        existing ``SketchPlane`` on the target face (see mutation-plan §6.3).
        Host-cutting instances (doors/windows: symbol != master) need a
        per-host geometry-symbol clone and are phase 2.
        """
        if not self.exists(symbol_id):
            raise LookupError(f"symbol {symbol_id} not in template {self.project}")
        if not self.exists(level_id):
            raise LookupError(f"level {level_id} not in template {self.project}")
        sym_cat = self.category_of(symbol_id)
        tpl = template_instance_id or self._template_instance(symbol_id, sym_cat)
        eid = self.next_id()
        c, s = math.cos(rotation), math.sin(rotation)
        px, py = float(position[0]), float(position[1])
        pz = float(position[2]) if len(position) > 2 else self._level_elevation(level_id)

        obj = copy.deepcopy(self.value(tpl))
        obj["m_id"] = eid
        obj["m_assocLevelId"] = level_id
        obj["m_famId"] = -1
        obj["m_designOptionId"] = -1
        obj["m_demolishedPhaseId"] = -1
        if phase_id is not None:
            obj["m_createdPhaseId"] = phase_id
        ii_holder = obj.get("m_pInstanceInfo") or {}
        ii = ii_holder.get("value") if isinstance(ii_holder, dict) else None
        if ii is None:
            ii = {}
            obj["m_pInstanceInfo"] = {"ptr_class": "InstanceInfo", "pid": -1, "value": ii}
        ii["m_symbolId"] = symbol_id
        ii["m_GRepId"] = 0
        ii["m_Trf"] = {"m_3x3": [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]],
                       "m_or": [px, py, pz]}
        obj["m_masterSymbolId"] = symbol_id
        obj["m_hostId"] = host_id if host_id is not None else -1
        obj["m_extraHostIds"] = []
        obj["m_explicitHostIds"] = []
        obj["m_workPlaneBased"] = host_id is not None
        obj["m_assocSketchPlaneId"] = -1
        obj["m_superInstanceId"] = -1
        obj["m_ownerElemId"] = -1
        obj["m_elevation"] = 0.0 if host_id is None else obj.get("m_elevation", 0.0)
        obj["m_pConnectorManager"] = obj.get("m_pConnectorManager")   # cloned; ids fixed below
        self._scrub_connectors(obj)      # new gear starts UNCONNECTED (no dangling circuit refs)
        obj["m_subInstTable"] = []
        obj["m_refs"] = []
        obj["m_offsetPosArr"] = []
        self._remap_ids(obj, {self.value(tpl).get("m_id"): eid})

        header = copy.deepcopy(self.value(tpl, 101)) or {}
        header["m_regenHistory"] = {"m_historyMap": []}
        parents = ((header.get("m_parents") or {}).get("value")) or {}
        phase = obj.get("m_createdPhaseId", -1)
        deletion = {level_id, symbol_id, eid}
        if phase not in (None, -1):
            deletion.add(phase)
        if host_id is not None:
            deletion.add(host_id)
        family = (self.value(symbol_id) or {}).get("m_familyId")
        parents.update({
            "m_deletion": sorted(deletion),
            "m_regenOnly": sorted({p for p in (family,) if p and p > 0}),
            "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
            "m_dependencyParents": [], "m_deferredParents": [],
            "m_deferredPropagationParents": [], "m_computedParametersParents": [],
            "m_appearanceParents": sorted({symbol_id}),
            "m_hasNonDetermRegenChildren": False,
        })
        if isinstance(header.get("m_parents"), dict):
            header["m_parents"]["value"] = parents
        header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1,
                             "value": {"m_minmax": [[px - 1.0, py - 1.0, pz],
                                                    [px + 1.0, py + 1.0, pz + 3.0]]}}

        # seq 103: the instance geometry rep is a small, formulaic GElement
        # (GInstance -> InstanceInfo{Trf, or, symbolId}); clone the template's
        # and rewrite it.  Fall back to a SerializedDummy if the template had
        # none.
        rep = None
        trep = self.decode(tpl, 103)
        if trep is not None and trep.class_id == CLASS_GELEMENT and trep.clean:
            rep = copy.deepcopy(trep.value)
            self._remap_ids(rep, {self.value(tpl).get("m_id"): eid})
            gi = rep.get("m_GInfo") or {}
            gi["m_tag"] = eid
            rep["m_elementId"] = eid
            for node in rep.get("m_subNodes") or []:
                nv = node.get("value") or {}
                info = ((nv.get("m_instanceInfo") or {}).get("value")) or {}
                if info:
                    info["m_symbolId"] = symbol_id
                    info["m_Trf"] = {"m_3x3": [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]],
                                     "m_or": [px, py, pz]}
            rep["m_bBox"] = [[px - 1.0, py - 1.0, pz], [px + 1.0, py + 1.0, pz + 3.0]]
            rep["m_tightbBox"] = rep["m_bBox"]

        el = NewElement(eid, "family_instance", "FamilyInstance",
                        CLASS_FAMILY_INSTANCE, header, obj, rep,
                        self._new_elemrec(eid), tpl,
                        notes=[
                            f"cloned from instance {tpl}; symbol==masterSymbol=={symbol_id} "
                            "(free/face pattern, no host-cut clone)",
                            "bounding boxes are estimates (regenerated by Revit)",
                        ])
        self.new_elements.append(el)
        return el

    # -- circuits ------------------------------------------------------------
    @staticmethod
    def _conn_manager(obj: dict) -> Optional[dict]:
        h = obj.get("m_pConnectorMgr") or obj.get("m_pConnectorManager") or {}
        v = h.get("value") if isinstance(h, dict) else None
        return v if isinstance(v, dict) else None

    @classmethod
    def _link_connector(cls, elem_obj: dict, conn_index: int, target_id: int,
                        target_index: int, conn_type: int = 4) -> bool:
        """Point an element's connector (by nIndex) at (target_id, target_index)."""
        mgr = cls._conn_manager(elem_obj) or {}
        for c in mgr.get("m_connPtrArray") or []:
            cv = c.get("value") if isinstance(c, dict) else None
            if isinstance(cv, dict) and cv.get("m_nIndex") == conn_index:
                cv["m_arrRefs"] = [{"m_id": target_id, "m_nIndex": target_index,
                                    "m_connType": conn_type}]
                return True
        return False

    @staticmethod
    def _connector_indexes(elem_obj: dict) -> list:
        h = elem_obj.get("m_pConnectorManager") or elem_obj.get("m_pConnectorMgr") or {}
        mgr = h.get("value") if isinstance(h, dict) else {}
        return [(c.get("value") or {}).get("m_nIndex")
                for c in (mgr or {}).get("m_connPtrArray") or []]

    def _template_circuit(self) -> int:
        """A real single-load power circuit (2 own connectors) to clone from."""
        for cid in self.ids_of_class("RbsElectricalSystem"):
            v = self.value(cid) or {}
            mgr = self._conn_manager(v) or {}
            if len(mgr.get("m_connPtrArray") or []) == 2:
                return cid
        raise LookupError(f"{self.project}: no 2-connector circuit specimen to clone")

    def add_circuit(self, panel: "NewElement", load: "NewElement", *,
                    number: str = "1", description: Optional[str] = None,
                    rating: Optional[float] = None, poles: Optional[int] = None,
                    load_classification: Optional[str] = None,
                    panel_conn_index: Optional[int] = None,
                    load_conn_index: Optional[int] = None,
                    template_id: Optional[int] = None) -> "NewElement":
        """Create an electrical CIRCUIT (RbsElectricalSystem) with ``panel`` as
        the BASE EQUIPMENT feeding ``load`` — both must be NEW elements created
        in this same commit (their connector objects are edited here to point
        back at the circuit; circuiting existing elements needs in-place record
        edits, phase 2).

        Reference closure — mirrored from real branch circuits, where a system
        owns one connector per member load plus a FINAL connector for the
        base equipment (the panel):
          circuit.conn[0].refs      -> {load,  load_conn (its supply, ~1), connType 1}
          circuit.conn[LAST].refs   -> {panel, panel_slot (50000-series), connType 4}
          baseConnectorIdArray      -> {circuit(self), LAST, connType 4}
          load.conn[load_conn].refs -> {circuit, 0, connType 4}
          panel.conn[panel_slot].refs -> {circuit, LAST, connType 4}
          pathNodes[0].elemId       -> load
        A panel's 50000-series connectors are its per-circuit SLOTS (one circuit
        each, never shared); its low index (1) is its own INCOMING supply.
        """
        tpl = template_id or self._template_circuit()
        sid = self.next_id()
        tval = self.value(tpl)
        obj = copy.deepcopy(tval)
        self._remap_ids(obj, {tval.get("m_id"): sid})
        obj["m_id"] = sid

        # panel side: allocate the next unused 50000-series circuit slot
        pidx = self._connector_indexes(panel.obj)
        lidx = self._connector_indexes(load.obj)
        if not hasattr(self, "_panel_slots_used"):
            self._panel_slots_used = {}
        used = self._panel_slots_used.setdefault(panel.elem_id, set())
        if panel_conn_index is None:
            slots = sorted(i for i in pidx if isinstance(i, int) and i >= 50000
                           and i not in used)
            if slots:
                panel_conn_index = slots[0]
            else:  # no free slot connector on this family: reuse the highest
                hi = [i for i in pidx if isinstance(i, int) and i >= 50000]
                panel_conn_index = (max(hi) if hi else (max(pidx) if pidx else 50000))
        used.add(panel_conn_index)
        # load side: its own incoming supply connector (lowest small index, ~1)
        if load_conn_index is None:
            low = sorted(i for i in lidx if isinstance(i, int) and 0 < i < 1000)
            load_conn_index = low[0] if low else (lidx[0] if lidx else 1)

        # the circuit's own connectors: conn[0] = the load, conn[LAST=1] = the panel
        mgr = self._conn_manager(obj) or {}
        conns = mgr.get("m_connPtrArray") or []
        if len(conns) >= 2:
            del conns[2:]                     # single-load circuit shape
            c0 = conns[0].get("value") or {}
            c1 = conns[1].get("value") or {}
            c0["m_nIndex"] = 0
            c0["m_arrRefs"] = [{"m_id": load.elem_id, "m_nIndex": load_conn_index,
                                "m_connType": 1}]
            c1["m_nIndex"] = 1
            c1["m_arrRefs"] = [{"m_id": panel.elem_id, "m_nIndex": panel_conn_index,
                                "m_connType": 4}]
        mgr["m_setDeletedConnectors"] = []
        obj["m_baseConnectorIdArray"] = [{"m_id": sid, "m_nIndex": 1, "m_connType": 4}]

        # path nodes: node 0 sits at the load; virtual nodes keep the template's
        # relative offsets so the routing shape is preserved
        def _origin(o):
            ii = ((o.get("m_pInstanceInfo") or {}).get("value")) or {}
            t = (ii.get("m_Trf") or {}).get("m_or") or o.get("m_instOrigin")
            return list(t) if t else [0.0, 0.0, 0.0]
        lpos = _origin(load.obj)
        nodes = obj.get("m_pathNodes") or []
        if nodes:
            base = list(nodes[0].get("m_position") or lpos)
            delta = [lpos[i] - base[i] for i in range(3)]
            for k, nd in enumerate(nodes):
                p = nd.get("m_position") or base
                nd["m_position"] = [p[i] + delta[i] for i in range(3)]
                if k == 0:
                    nd["m_elemId"] = load.elem_id
                    nd["m_isVirtualNode"] = False
                else:
                    nd["m_elemId"] = -1
                    nd["m_isVirtualNode"] = True

        obj["m_number"] = str(number)
        obj["m_strDescription"] = description if description is not None else obj.get("m_strDescription", "")
        obj["m_strName"] = obj.get("m_strName", "")
        if rating is not None:
            obj["m_dRating"] = float(rating)
        if poles is not None:
            obj["m_nPoles"] = int(poles)
        if load_classification is not None:
            obj["m_strLoadClassifications"] = load_classification

        # header: parents = the panel, the load, and the model-level cable settings
        header = copy.deepcopy(self.value(tpl, 101)) or {}
        header["m_regenHistory"] = {"m_historyMap": []}
        parents = ((header.get("m_parents") or {}).get("value")) or {}
        deletion = {panel.elem_id, load.elem_id, sid}
        for k in ("m_cableType", "m_cableSizeElementId"):
            v = obj.get(k)
            if isinstance(v, int) and v > 0:
                deletion.add(v)
        parents.update({
            "m_deletion": sorted(deletion),
            "m_regenOnly": [], "m_regenWildcards": [],
            "m_nonDetermRegenChildren": [], "m_dependencyParents": [],
            "m_appearanceParents": sorted({panel.elem_id, load.elem_id}),
            "m_deferredParents": [], "m_deferredPropagationParents": [],
            "m_computedParametersParents": [],
            "m_hasNonDetermRegenChildren": False,
        })
        if isinstance(header.get("m_parents"), dict):
            header["m_parents"]["value"] = parents

        # mutual links: load's supply connector -> circuit conn 0; panel's slot
        # connector -> circuit conn 1 (both back-links use connType 4)
        okl = self._link_connector(load.obj, load_conn_index, sid, 0, conn_type=4)
        okp = self._link_connector(panel.obj, panel_conn_index, sid, 1, conn_type=4)
        notes = [f"cloned from circuit {tpl}; panel {panel.elem_id} slot {panel_conn_index}"
                 f" ({'linked' if okp else 'NO panel connector'}) feeds load {load.elem_id}"
                 f" conn {load_conn_index} ({'linked' if okl else 'NO load connector'})"]

        el = NewElement(sid, "circuit", "RbsElectricalSystem", CLASS_ELECTRICAL_SYSTEM,
                        header, obj, None, self._new_elemrec(sid), tpl, notes=notes)
        self.new_elements.append(el)
        return el

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _wall_geometry(v: dict) -> dict:
        """Extract the template wall's line + ref-face geometry (feet)."""
        drv = ((v.get("m_pCurveDriver") or {}).get("value") or {})
        crv = (drv.get("m_pCrv") or {}).get("value") or {}
        org = crv.get("m_origin") or [0.0, 0.0, 0.0]
        dvec = crv.get("m_dirVec") or [1.0, 0.0, 0.0]
        ep = crv.get("m_endParams") or [0.0, 1.0]
        # location line start point and unit direction (xy)
        n = math.hypot(dvec[0], dvec[1]) or 1.0
        d = (dvec[0] / n, dvec[1] / n)
        start = (org[0] + d[0] * ep[0], org[1] + d[1] * ep[0], org[2])
        length = ep[1] - ep[0]
        nx, ny = -d[1], d[0]                      # left normal
        faces = []
        for f in v.get("m_pRefFaces") or []:
            fv = f.get("value") or {}
            surf = (fv.get("m_pSurf") or {}).get("value") or {}
            fo = surf.get("m_origin")
            if not fo:
                faces.append(None)
                continue
            # signed perpendicular offset of the face plane from the line
            off = (fo[0] - start[0]) * nx + (fo[1] - start[1]) * ny
            env = (surf.get("m_Envelope") or {}).get("m_corners") or [[0, 0], [length, 0]]
            faces.append({"offset": off, "env_h": env[1][1] if len(env) > 1 else None})
        return {"start": start, "dir": d, "length": length, "faces": faces}

    @staticmethod
    def _rebuild_wall_faces(obj: dict, told: dict, start, d, length, height):
        x0, y0, z0 = start
        dx, dy = d
        nx, ny = -dy, dx
        for f, meta in zip(obj.get("m_pRefFaces") or [], told["faces"]):
            fv = f.get("value") or {}
            surf = (fv.get("m_pSurf") or {}).get("value") or {}
            if meta is None or not surf:
                continue
            off = meta["offset"]
            surf["m_origin"] = [x0 + nx * off, y0 + ny * off, z0]
            surf["m_xVec"] = [dx, dy, 0.0]
            surf["m_yVec"] = [0.0, 0.0, 1.0]
            surf["m_Envelope"] = {"m_corners": [[0.0, 0.0], [length, height]]}

    @staticmethod
    def _wall_thickness(told: dict) -> Optional[float]:
        offs = [m["offset"] for m in told["faces"] if m]
        if not offs:
            return None
        return abs(max(offs) - min(offs)) or None

    @staticmethod
    def _set_param(obj: dict, set_name: str, param_id: int, value) -> str:
        """Upsert one Element param row of a template object being built
        (holder authored when null).  The row / holder shape lives in ONE
        place, :func:`rvt.manipulate.upsert_param_row`; imported lazily --
        ``manipulate`` imports this module (lazily) too, and pulling its
        encoder / writer stack into every ``import rvt.mutate`` would cost
        the create path ~45 ms for two wall-height rows."""
        from .manipulate import upsert_param_row
        return upsert_param_row(obj, param_id, value, holder=set_name)

    @staticmethod
    def _remap_ids(v, mapping: dict):
        """Rewrite occurrences of old element ids (m_id / m_elementId / tags)."""
        if isinstance(v, dict):
            for k, x in list(v.items()):
                if isinstance(x, int) and not isinstance(x, bool) and x in mapping \
                        and ("Id" in k or "_id" in k or k in ("m_tag", "m_id")):
                    v[k] = mapping[x]
                else:
                    Document._remap_ids(x, mapping)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, int) and not isinstance(x, bool) and x in mapping:
                    v[i] = mapping[x]
                else:
                    Document._remap_ids(x, mapping)

    # -- validation ------------------------------------------------------------
    def referenced_ids(self, el: NewElement) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        _collect_ids(el.header, out, "seq101")
        _collect_ids(el.obj, out, "seq102")
        if el.rep is not None:
            _collect_ids(el.rep, out, "seq103")
        return out

    def check_references(self, el: NewElement) -> list[dict]:
        """Referential integrity: every referenced ElementId must exist in the
        template (or be the new element itself / another planned element /
        a negative built-in id).  Returns the list of dangling references."""
        planned = {e.elem_id for e in self.new_elements}
        bad = []
        for path, i in self.referenced_ids(el):
            if i < 0 or i == el.elem_id or i in planned:
                continue
            if not self.exists(i):
                bad.append({"path": path, "id": i})
        return bad

    # -- diff / plan --------------------------------------------------------------
    def diff(self) -> list[StreamChange]:
        """Every stream a save containing the new elements must re-emit."""
        n = len(self.new_elements)
        if n == 0:
            return []
        ids = [e.elem_id for e in self.new_elements]
        et_count = self.et.count + n
        rec_count = sum(len(v) for v in [self.idx[102]]) + n
        return [
            StreamChange("Global/ElemTable", "append-row",
                         "one 40-byte ElemRec per new element, table kept sorted by "
                         "m_id; bump m_elemArr count and IdentifierSource.m_last "
                         "(id watermark); re-gzip (+8-byte 0 prefix), re-page (+ECC).",
                         {"new_count": et_count, "new_last_id": max(ids),
                          "rows": [e.elemrec.to_json() for e in self.new_elements]}),
            StreamChange("Partitions/<N>", "insert-records",
                         "insert three records (seq 101 ElementHeader, seq 102 object, "
                         "seq 103 GElement/SerializedDummy) per new element into SAVE "
                         "UNIT 0 (the host-document unit; unit 0's ids == ElemTable ids); "
                         "re-block/re-gzip unit 0's three segments; copy every embedded-"
                         "document unit (1..k) verbatim; keep the stream number N; "
                         "stream header elem_table_count = new ElemTable count.",
                         {"unit": 0, "keep_partition_number": True,
                          "new_record_count_seq102": rec_count,
                          "record_stamp": "adler32(u16 class_id + object bytes)",
                          "sentinel": "each unit's per-seq segment ends with one id -1 "
                                      "record (psize 0)"}),
            StreamChange("Global/DocumentIncrementTable", "append-row",
                         "append one DocumentIncrement (m_majorVersion = last+1, "
                         "m_incrementVersions[0].m_totalElements = new total record "
                         "count, m_greatest = new max EpisodeId, m_totalEpisodes, "
                         "m_atimeStamp = unix save time, each *StreamRevision +1, "
                         "m_userName) to m_increments AND m_localIncrements; the u32 "
                         "container count is what earlier notes read as 'max(N)+1'.",
                         {"new_major_version": "last+1",
                          "total_elements": rec_count}),
            StreamChange("Global/History", "insert-episode",
                         "prepend one 17-byte episode record (fresh v4 GUID + 0x28) as "
                         "entry 0 and bump both counts; the new elements' ElemRec "
                         "creation/modification EpisodeIds == the new episode index "
                         f"({self.new_episode}).",
                         {"new_episode_index": self.new_episode,
                          "new_episode_count": self.new_episode + 1}),
            StreamChange("BasicFileInfo", "update-field",
                         "'Unique Document GUID' / last-reload episode GUID == the new "
                         "History entry 0 GUID (both encodings inside the stream).",
                         {}),
            StreamChange("Global/Latest", "unchanged-or-append",
                         "no per-element data lives here; optionally append the writer's "
                         "build string to ADocument.m_storedByRevitBuild. The 26 KB of "
                         "increment/revision mirrors sit in DocumentIncrementTable, not here.",
                         {}),
            StreamChange("Contents / Formats/Latest / PartitionTable / ContentDocuments /"
                         " embedded-document units", "copy",
                         "unchanged by adding host-document elements: copy verbatim.", {}),
        ]

    def plan(self) -> dict:
        return {
            "template": self.project,
            "id_watermark_before": (self.et.footer.last_id if self.et.footer else None),
            "id_watermark_after": self.last_issued_id,
            "current_episode": self.current_episode,
            "new_episode": self.new_episode,
            "new_elements": [e.to_json() for e in self.new_elements],
            "referential_integrity": {
                str(e.elem_id): self.check_references(e) for e in self.new_elements
            },
            "streams": [c.to_json() for c in self.diff()],
        }

    # -- serialization (parallel agent's rvt.encode) --------------------------
    def serialize(self, el: NewElement) -> Optional[list[tuple[int, bytes]]]:
        """Encode an element's three records via ``rvt.encode`` if present.

        Intended contract (parallel 'serializer' agent)::

            rvt.encode.encode_record(seq, id, stamp, class_id, obj) -> bytes

        returns the full framed record.  ``stamp`` for seq 102/103 is
        :func:`record_stamp` of the encoded payload; because it depends on
        the object bytes, pass ``stamp=None`` and let the encoder fill it
        (or encode the object first).  Returns None when the encoder is not
        installed yet.
        """
        try:
            from . import encode  # type: ignore
        except Exception:
            return None
        out = []
        for seq, class_id, obj in el.records():
            fn = getattr(encode, "encode_record", None)
            if fn is None:
                return None
            out.append((seq, fn(seq, el.elem_id, None, class_id, obj)))
        return out


# ---------------------------------------------------------------------------
#: sub-trees / keys whose small integers are geometry topology tags,
#: parameter ids or table indices - NOT ElementIds
_NOT_ELEMENT_ID = ("HistTable", "m_faceHist", "m_edgeHist", "m_GInfo",
                   "m_keys", "m_geomGeneratorId", "m_tag", "m_paramId",
                   "m_index", "m_GRepId", "m_gElemType", "m_penNumber",
                   "m_faceRegions", "m_nIndex", "m_nextMidParamId",
                   "m_hostPointId", "m_geomTag")


def _collect_ids(v, out, path=""):
    """(path, id) for every plausible ElementId value in a decoded tree."""
    if isinstance(v, dict):
        for k, x in v.items():
            p = f"{path}.{k}" if path else k
            if isinstance(x, int) and not isinstance(x, bool):
                if x > 0 and ("Id" in k or "_id" in k or k in
                              ("m_deletion", "m_regenOnly", "m_appearanceParents")) \
                        and not any(t in p for t in _NOT_ELEMENT_ID):
                    out.append((p, x))
            else:
                if any(t in k for t in ("HistTable", "m_faceHist", "m_edgeHist", "m_GInfo")):
                    continue
                _collect_ids(x, out, p)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            if isinstance(x, int) and not isinstance(x, bool):
                if x > 0 and any(t in path for t in ("Id", "_id", "m_deletion",
                                                    "m_regenOnly", "Parents")) \
                        and not any(t in path for t in _NOT_ELEMENT_ID):
                    out.append((f"{path}[{i}]", x))
            else:
                _collect_ids(x, out, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# demo driver
# ---------------------------------------------------------------------------

def _pick_symbol(doc: Document, categories: Iterable[int]) -> Optional[int]:
    """First host-document FamilySymbol whose master pattern is placeable."""
    cats = set(categories)
    for sid in doc.ids_of_class("FamilySymbol"):
        if doc.category_of(sid) in cats:
            return sid
    return None


def demo(project: str = "racbasicsampleproject") -> dict:
    doc = Document.load(project)
    levels = doc.levels()
    if not levels:
        raise SystemExit(f"{project}: no levels")
    # base = the host document's "Level 1" (lowest id if several)
    named = sorted((l for l in levels if (l["name"] or "") == "Level 1"),
                   key=lambda l: l["id"])
    lvl = named[0]["id"] if named else levels[0]["id"]
    types = doc.wall_types_with_instances()
    wt = max(types, key=lambda t: len(types[t])) if types else None
    out = {"template": project, "level": lvl, "wall_type": wt}
    if wt is not None:
        w = doc.add_wall(level_id=lvl, wall_type_id=wt, p0=(0.0, 0.0), p1=(20.0, 0.0),
                         height=10.0)
        out["wall"] = {"elem_id": w.elem_id, "template": w.template_id,
                       "dangling_refs": doc.check_references(w)}
    sym = _pick_symbol(doc, (OST_ElectricalEquipment, OST_LightingFixtures,
                              OST_ElectricalFixtures, -2001350, -2000080))
    if sym is not None:
        fi = doc.add_family_instance(symbol_id=sym, level_id=lvl,
                                     position=(5.0, 5.0, 0.0), rotation=math.pi / 2)
        out["family_instance"] = {"elem_id": fi.elem_id, "symbol": sym,
                                  "template": fi.template_id,
                                  "dangling_refs": doc.check_references(fi)}
    out["diff"] = [c.to_json() for c in doc.diff()]
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    project = argv[0] if argv else "racbasicsampleproject"
    result = demo(project)
    print(json.dumps(result, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
