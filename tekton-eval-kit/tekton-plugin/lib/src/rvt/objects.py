"""Schema-directed decoder for serialized Revit element objects.

This is the first "read the model" layer: it walks a class's field list
from the canonical archive class map (``Formats/Latest`` via
:mod:`rvt.schema`) and decodes a serialized object body (a
``Partitions/<N>`` record) into a nested dict of real values.

Serialization rules established in this module (all verified byte-exact
against many records; see ``docs/streams/10-objects.md``):

Record framing (refines wave-1 ``partitions.py``; uniform across seqs)
    record = ``i64 id`` + [``u32 stamp`` in seq 102/103 only]
             + ``u32 psize`` + payload(psize bytes) + ``u32 psize`` (repeat)
    payload = ``u16 class_id`` + object bytes (psize - 2).  Total record
    length = 16/20 + psize.  The wave-1 ``u32 class_word`` is really
    ``u16 class_id`` + the first u16 of the object.  ``class_id`` is the
    schema type_id DIRECTLY (identity mapping, no offset/drift).  Save-unit
    sentinel records have id = -1 and psize = 0.  ``SerializedDummy``
    records (seq 103 placeholder) have psize = 2 = a bare class id with an
    empty object.  The trailing ``u32 psize`` repeat holds for 100% of
    records in all files (racbasic seq 102: 85,814/85,814).

Field order
    Base classes serialize FIRST (parent-first), root base down to the
    concrete class, each contributing its schema fields in schema order.

Primitives
    bool/char = u8; short = i16; int = i32; uint = u32; float = f32;
    double = f64; int64 = i64; AString = u32 char_count + UTF-16LE;
    GUID = 16 raw bytes; ElementId (a value class wrapping Identifier
    wrapping int64) reads structurally as i64 (-1 = invalid).

Pointers (kind 0x0e, flags low nibble 1/2/4 = owned/polymorphic)
    ``i32 pid``: 0 = null (4 bytes total); otherwise a ``u16 class``
    follows (6 bytes total) and the pointed-to object body is DEFERRED —
    appended to a per-record FIFO queue and serialized only after the
    current object's field list completes (breadth-first).  pid = -1 means
    an anonymous (unshared) object; pid > 0 assigns an archive object index
    (1 = the document, 2 = the record's root object, 3.. = new indexed
    objects) so weak pointers can refer to it.  A pid > 0 already seen is a
    back-reference (no class word, no body).

Weak pointers (flags low nibble 3)
    ``u32 pid`` referencing an archive object index (1 = document, 2 = the
    root element, 0 = null).

Containers (flags high nibble 5) = ``u32 count`` + count elements
    (element = primitive / inline value class / pointer token / weak ref /
    inline array per the field's kind & low nibble).  Fixed arrays (flags
    high nibble 1) take their count from the schema.  Kind 0x0d "inline
    array" fields repeat their anonymous element descriptor.

Public API::

    dec = ObjectDecoder()                    # loads the canonical schema
    obj = dec.decode_record(class_id, body)  # body = record payload
    obj.value      -> nested dict {field: value}
    obj.consumed   -> bytes consumed (target: len(body))
    obj.errors     -> [{field, offset, error}] (empty on a clean decode)

``python -m rvt.objects [project]`` runs the driver (per-class decode-rate
table, samples) — see :func:`main`.
"""
from __future__ import annotations

import json
import os
import struct
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional

from .schema import Schema, ClassDef, Field, load_schema

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides
EXTRACTED = os.path.join(ROOT, "extracted")

# hard caps to keep a misparse from running away
MAX_CONTAINER = 2_000_000
MAX_DEPTH = 64

INVALID_ELEMENT_ID = -1

# primitive kinds -> (struct fmt, size)
_PRIM_FMT = {
    0x01: ("<B", 1),   # bool
    0x02: ("<B", 1),   # char
    0x03: ("<h", 2),   # short
    0x04: ("<i", 4),   # int
    0x05: ("<I", 4),   # uint
    0x06: ("<f", 4),   # float
    0x07: ("<d", 8),   # double
    0x0b: ("<q", 8),   # int64
}


class DecodeError(Exception):
    def __init__(self, offset: int, msg: str):
        super().__init__(f"{msg} @+{offset:#x}")
        self.offset = offset
        self.msg = msg


def field_key(cd, f, out: dict) -> str:
    """Dict key for a field: its plain name, unless SHADOWED.

    18 of 4,690 classes re-declare an ancestor's field name (e.g.
    ``PropertySetLibrary.m_locked`` shadows ``Element.m_locked``;
    ``RbsFlexPipeType.m_dRoughness``; ``m_pConnectorManager`` on the
    RbsInsulation family).  Keying a flat dict by name silently dropped
    the earlier value (a decode information loss that broke byte-exact
    re-encoding).  The FIRST occurrence keeps its plain name (all existing
    consumers unaffected); a shadowing re-declaration is stored under
    ``"<DeclaringClass>::<name>"``.  ``rvt.encode`` applies the identical
    rule so decode->encode stays symmetric.
    """
    if f.name not in out:
        return f.name
    key = f"{cd.name}::{f.name}"
    i = 2
    while key in out:                     # pathological triple-shadow guard
        key = f"{cd.name}::{f.name}#{i}"
        i += 1
    return key


# ---------------------------------------------------------------------------
class Reader:
    """Bounded little-endian byte reader over one object payload."""

    __slots__ = ("d", "p", "n")

    def __init__(self, data: bytes, pos: int = 0):
        self.d = data
        self.p = pos
        self.n = len(data)

    # -- helpers ---------------------------------------------------------
    def remaining(self) -> int:
        return self.n - self.p

    def need(self, k: int, what: str = "bytes"):
        if self.p + k > self.n:
            raise DecodeError(self.p, f"truncated: need {k} {what}, have {self.n - self.p}")

    def _unpack(self, fmt: str, size: int):
        self.need(size, fmt)
        v = struct.unpack_from(fmt, self.d, self.p)[0]
        self.p += size
        return v

    # -- primitives --------------------------------------------------------
    def u8(self) -> int:
        return self._unpack("<B", 1)

    def bool(self) -> bool:
        return bool(self._unpack("<B", 1))

    def i16(self) -> int:
        return self._unpack("<h", 2)

    def u16(self) -> int:
        return self._unpack("<H", 2)

    def i32(self) -> int:
        return self._unpack("<i", 4)

    def u32(self) -> int:
        return self._unpack("<I", 4)

    def i64(self) -> int:
        return self._unpack("<q", 8)

    def u64(self) -> int:
        return self._unpack("<Q", 8)

    def f32(self) -> float:
        return self._unpack("<f", 4)

    def f64(self) -> float:
        return self._unpack("<d", 8)

    def take(self, k: int) -> bytes:
        self.need(k)
        v = self.d[self.p:self.p + k]
        self.p += k
        return v

    def astring(self) -> str:
        """AString: u32 UTF-16 code-unit count + UTF-16LE, no terminator."""
        start = self.p
        n = self.u32()
        if n == 0xFFFFFFFF:          # null AString sentinel (strings-map §6.2)
            return None
        if n > (self.n - self.p) // 2:
            raise DecodeError(start, f"AString length {n} exceeds remaining")
        raw = self.take(2 * n)
        # surrogatepass keeps lone surrogates byte-exact reversible
        # (encoder inverse); 'replace' silently mapped them to U+FFFD.
        return raw.decode("utf-16-le", errors="surrogatepass")

    def guid(self) -> str:
        b = self.take(16)
        d1, d2, d3 = struct.unpack_from("<IHH", b, 0)
        t = b[8:16]
        return (f"{d1:08x}-{d2:04x}-{d3:04x}-{t[0]:02x}{t[1]:02x}-"
                f"{t[2:].hex()}")

    def element_id(self) -> int:
        """ElementId = Identifier = int64 LE, -1 invalid."""
        return self.i64()

    def xyz(self):
        self.need(24)
        v = struct.unpack_from("<3d", self.d, self.p)
        self.p += 24
        return list(v)

    def uv(self):
        self.need(16)
        v = struct.unpack_from("<2d", self.d, self.p)
        self.p += 16
        return list(v)

    def count32(self, min_elem: int = 1, what: str = "count") -> int:
        """u32 container count with a sanity cap against runaway parses."""
        at = self.p
        c = self.u32()
        if c > MAX_CONTAINER or c * max(min_elem, 1) > (self.n - self.p) + 16:
            raise DecodeError(at, f"implausible {what} {c} (remaining {self.n - self.p})")
        return c


# ---------------------------------------------------------------------------
@dataclass
class DecodedObject:
    class_id: int
    class_name: str
    value: dict
    consumed: int = 0
    total: int = 0
    errors: list = dc_field(default_factory=list)
    n_deferred: int = 0
    stub: bool = False        # empty placeholder object (e.g. SerializedDummy)

    @property
    def clean(self) -> bool:
        return not self.errors and (self.consumed == self.total or self.stub)

    def to_json(self):
        return {
            "class_id": self.class_id,
            "class": self.class_name,
            "consumed": self.consumed,
            "total": self.total,
            "clean": self.clean,
            "errors": self.errors,
            "value": self.value,
        }


class _Pending:
    """A deferred (queued) pointed-to object awaiting body decode."""

    __slots__ = ("class_id", "holder", "key", "pid", "path")

    def __init__(self, class_id, holder, key, pid, path):
        self.class_id = class_id
        self.holder = holder     # dict/list receiving the decoded value
        self.key = key           # key/index in holder
        self.pid = pid
        self.path = path


# ---------------------------------------------------------------------------
class ObjectDecoder:
    """Decodes serialized objects using a parsed :class:`rvt.schema.Schema`."""

    def __init__(self, schema: Optional[Schema] = None):
        self.schema = schema or load_schema()
        self._chain_cache: dict[int, list[ClassDef]] = {}
        # field order: base classes first (verified).  Set True to test the
        # rejected alternative (concrete class's own fields first).
        self.self_first = False
        # ids of tiny wrapper classes we flatten for readability
        s = self.schema
        self.id_ElementId = s.by_name["ElementId"].type_id if "ElementId" in s.by_name else None
        self.id_Identifier = s.by_name["Identifier"].type_id if "Identifier" in s.by_name else None
        self.id_XYZ = s.by_name["XYZ"].type_id if "XYZ" in s.by_name else None
        self.id_UV = s.by_name["UV"].type_id if "UV" in s.by_name else None
        self.id_GUIDvalue = s.by_name["GUIDvalue"].type_id if "GUIDvalue" in s.by_name else None
        self.id_AStringWrapper = s.by_name["AStringWrapper"].type_id if "AStringWrapper" in s.by_name else None

    # -- schema helpers ------------------------------------------------------
    def chain(self, class_id: int) -> list[ClassDef]:
        """Class + ancestors, ROOT BASE FIRST (parent-first serialization)."""
        c = self._chain_cache.get(class_id)
        if c is not None:
            return c
        out: list[ClassDef] = []
        cur = self.schema.by_id.get(class_id)
        seen = set()
        while cur is not None and cur.type_id not in seen:
            seen.add(cur.type_id)
            out.append(cur)
            cur = self.schema.by_id.get(cur.parent_id) if cur.parent_id is not None else None
        if not self.self_first:
            out.reverse()          # root base first == parent-first
        self._chain_cache[class_id] = out
        return out

    def class_name(self, class_id: int) -> str:
        c = self.schema.by_id.get(class_id)
        return c.name if c else f"<class {class_id:#x}>"

    # -- entry point ---------------------------------------------------------
    def decode_record(self, class_id: int, payload: bytes) -> DecodedObject:
        """Decode one serialized object (a partition record payload).

        ``payload`` is the object bytes only (record payload minus the
        leading ``u16 class_id``; the record's trailing ``u32 psize``
        repeat is not part of the object) — exactly what
        :func:`iter_records` yields in ``Record.payload``.  Returns a
        :class:`DecodedObject`.
        """
        name = self.class_name(class_id)
        obj = DecodedObject(class_id, name, {}, 0, len(payload))
        rd = Reader(payload)
        state = _State(seen_pids={1, 2})
        queue: deque[_Pending] = deque()
        try:
            if class_id not in self.schema.by_id:
                raise DecodeError(0, f"unknown class id {class_id:#x}")
            obj.value = self._decode_class(rd, class_id, queue, state, name)
            # breadth-first: deferred pointed-to object bodies, in queue order
            while queue:
                pend = queue.popleft()
                obj.n_deferred += 1
                cname = self.class_name(pend.class_id)
                sub = self._decode_class(rd, pend.class_id, queue, state,
                                         f"{pend.path}->{cname}")
                pend.holder[pend.key] = sub
        except DecodeError as e:
            obj.errors.append({"field": state.path, "offset": e.offset, "error": e.msg})
        except (struct.error, IndexError) as e:
            obj.errors.append({"field": state.path, "offset": rd.p, "error": f"truncated: {e}"})
        obj.consumed = rd.p
        # a zero-field class over an all-zero payload is an empty stub object
        # (e.g. SerializedDummy in seq 103: tiny record, no size trailer)
        if not obj.errors and obj.consumed < obj.total and obj.total <= 4 \
                and not any(payload[obj.consumed:]):
            obj.stub = True
        return obj

    # -- class body ------------------------------------------------------------
    def _decode_class(self, rd: Reader, class_id: int, queue: deque, state: "_State",
                      path: str) -> dict:
        state.depth += 1
        if state.depth > MAX_DEPTH:
            raise DecodeError(rd.p, "max nesting depth")
        out: dict = {}
        try:
            for cd in self.chain(class_id):
                for f in cd.fields:
                    fpath = f"{path}.{f.name}"
                    state.path = fpath
                    out[field_key(cd, f, out)] = self._decode_field(rd, f, queue, state, fpath)
        finally:
            state.depth -= 1
        return out

    # -- one field -------------------------------------------------------------
    def _decode_field(self, rd: Reader, f: Field, queue: deque, state: "_State",
                      path: str) -> Any:
        kind = f.kind
        flags = f.flags
        shape = flags >> 4          # 0 scalar, 1 fixed array, 5 container, 6 string
        indir = flags & 0x0F        # 0 value, 1/2/4 pointer, 3 weak

        # AString (kind 8, flags 0x60)
        if kind == 0x08:
            if shape == 0x5 or shape == 0x1:      # container/array of strings
                n = f.count if shape == 0x1 else rd.count32(4, "string count")
                return [rd.astring() for _ in range(n)]
            return rd.astring()

        # inline array wrapper (kind 0x0d): repeat the anonymous element field
        if kind == 0x0D:
            elem = f.element
            if elem is None:
                raise DecodeError(rd.p, f"array field {f.name} without element descriptor")
            if shape == 0x1:
                n = f.count or 0
            elif shape == 0x5:
                n = rd.count32(1, f"array count {f.name}")
            else:
                n = 1
            return [self._decode_field(rd, elem, queue, state, f"{path}[{i}]") for i in range(n)]

        # containers (growable): u32 count + elements
        if shape == 0x5:
            n = rd.count32(self._min_size(f), f"container count {f.name}")
            return [self._decode_scalar(rd, f, kind, indir, queue, state, f"{path}[{i}]")
                    for i in range(n)]

        # fixed arrays: schema count
        if shape == 0x1:
            n = f.count or 0
            return [self._decode_scalar(rd, f, kind, indir, queue, state, f"{path}[{i}]")
                    for i in range(n)]

        return self._decode_scalar(rd, f, kind, indir, queue, state, path)

    def _min_size(self, f: Field) -> int:
        if f.kind in _PRIM_FMT:
            return _PRIM_FMT[f.kind][1]
        if f.kind == 0x08:
            return 4
        if f.kind == 0x0E and (f.flags & 0x0F) in (1, 2, 4):
            return 4
        return 1

    def _decode_scalar(self, rd: Reader, f: Field, kind: int, indir: int, queue: deque,
                       state: "_State", path: str) -> Any:
        if kind in _PRIM_FMT:
            fmt, sz = _PRIM_FMT[kind]
            v = rd._unpack(fmt, sz)
            if kind == 0x01:
                return bool(v)
            return v
        if kind == 0x08:
            return rd.astring()
        if kind == 0x09:
            return rd.guid()
        if kind == 0x0A:              # class-definition ref: u16 class index
            return {"classref": self.class_name(rd.u16())}
        if kind == 0x0E:
            if indir == 0:            # inline value class
                if f.type_id is None:
                    raise DecodeError(rd.p, f"typed value field {f.name} without type id")
                return self._decode_value_class(rd, f.type_id, queue, state, path)
            if indir == 3:            # weak pointer: u32 archive object index
                return {"weakref": rd.u32()}
            return self._decode_pointer(rd, queue, state, path)
        raise DecodeError(rd.p, f"unsupported kind {kind:#x} in {f.name}")

    # -- value classes with friendly flattening -----------------------------------
    def _decode_value_class(self, rd: Reader, type_id: int, queue: deque,
                            state: "_State", path: str) -> Any:
        if type_id == self.id_ElementId or type_id == self.id_Identifier:
            return rd.element_id()
        if type_id == self.id_XYZ:
            return rd.xyz()
        if type_id == self.id_UV:
            return rd.uv()
        if type_id == self.id_GUIDvalue:
            return rd.guid()
        return self._decode_class(rd, type_id, queue, state, path)

    # -- pointer token ----------------------------------------------------------
    def _decode_pointer(self, rd: Reader, queue: deque, state: "_State", path: str) -> Any:
        at = rd.p
        pid = rd.i32()
        if pid == 0:
            return None
        if pid > 0 and pid in state.seen_pids:
            return {"backref_pid": pid}
        cls = rd.u16()
        if cls not in self.schema.by_id:
            raise DecodeError(at, f"pointer token pid={pid} to unknown class {cls:#x}")
        if pid > 0:
            state.seen_pids.add(pid)
        holder = {"ptr_class": self.class_name(cls), "pid": pid, "value": None}
        queue.append(_Pending(cls, holder, "value", pid, path))
        return holder


class _State:
    __slots__ = ("seen_pids", "path", "depth")

    def __init__(self, seen_pids):
        self.seen_pids = seen_pids
        self.path = "<root>"
        self.depth = 0


# ---------------------------------------------------------------------------
# Record source: partition seq-102 records with the corrected framing
# ---------------------------------------------------------------------------

@dataclass
class Record:
    elem_id: int
    stamp: int
    class_id: int
    body_size: int            # psize (u16 class + object bytes)
    payload: bytes            # object bytes (psize - 2), size-repeat trailer excluded
    seg_offset: int
    trailer_ok: bool = True   # trailing u32 psize repeat matched


def iter_records(seg: bytes, seq: int = 102):
    """Iterate seq-101/102/103 records with the corrected (uniform) framing.

    record = i64 id [+ u32 stamp for seq 102/103] + u32 psize
             + payload (psize bytes = u16 class_id + object bytes)
             + u32 psize (trailer repeat)
    Save-unit sentinels have id == -1 and psize == 0.  The wave-1 walker
    read {..., u32 psize, u32 class_word} with the object starting at the
    class word's high u16 -- an equivalent view of the same bytes.
    """
    hlen = 12 if seq == 101 else 16
    p = 0
    n = len(seg)
    while p + hlen + 4 <= n:
        if seq == 101:
            eid, size = struct.unpack_from("<qI", seg, p)
            stamp = 0
        else:
            eid, stamp, size = struct.unpack_from("<qII", seg, p)
        if not (-1 <= eid < (1 << 40)) or size > (1 << 30):
            return
        pay = seg[p + hlen: p + hlen + size]
        if len(pay) < size:
            return
        tail_off = p + hlen + size
        trailer_ok = True
        if tail_off + 4 <= n:
            trailer_ok = struct.unpack_from("<I", seg, tail_off)[0] == size
        if size >= 2:
            cls = struct.unpack_from("<H", pay, 0)[0]
            payload = pay[2:]
        else:
            cls = 0
            payload = b""
        yield Record(eid, stamp, cls, size, payload, p, trailer_ok)
        p = tail_off + 4


def load_segment(project: str, seq: int = 102, cache_dir: Optional[str] = None) -> bytes:
    """Concatenated element-data segment of a project (all partition streams)."""
    from .partitions import partition_stream_paths, load_stream
    if cache_dir:
        cp = os.path.join(cache_dir, f"{project}_seg{seq}.bin")
        if os.path.exists(cp):
            with open(cp, "rb") as fh:
                return fh.read()
    parts = []
    for path in partition_stream_paths(project):
        # partition_stream_paths() globs 'Partitions__*.bin', which ALSO
        # matches the de-paged 'Partitions__N.logical.bin' extraction
        # artefact.  load_stream() expects the RAW (page-framed) stream and
        # de-pages it itself; feeding it the .logical.bin duplicate appends
        # a garbled second copy of the head of the segment (this produced
        # phantom duplicate records / bogus "AString length" failures).
        # Only walk the raw streams here.  See docs/inbox/object-decoder.md.
        if path.endswith(".logical.bin"):
            continue
        parts.append(load_stream(path).concat_segment(seq))
    seg = b"".join(parts)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, f"{project}_seg{seq}.bin"), "wb") as fh:
            fh.write(seg)
    return seg


# ---------------------------------------------------------------------------
# Driver / reporting
# ---------------------------------------------------------------------------

def _fmt_value(v, depth=0, maxlist=6):
    pad = "  " * depth
    if isinstance(v, dict):
        if "ptr_class" in v:
            inner = _fmt_value(v.get("value"), depth + 1)
            tag = f"-> {v['ptr_class']}" + (f" (pid {v['pid']})" if v.get("pid", -1) > 0 else "")
            return f"{tag} " + inner.strip() if isinstance(v.get("value"), dict) and len(str(inner)) < 80 else f"{tag}\n{inner}"
        if "weakref" in v:
            return f"weakref({v['weakref']})"
        if "backref_pid" in v:
            return f"backref(pid {v['backref_pid']})"
        if "classref" in v:
            return f"classref({v['classref']})"
        if not v:
            return "{}"
        lines = []
        for k, x in v.items():
            r = _fmt_value(x, depth + 1)
            if "\n" in r:
                lines.append(f"{pad}{k}:{r if r.startswith(' ->') else chr(10) + r}")
            else:
                lines.append(f"{pad}{k}: {r.strip()}")
        return "\n" + "\n".join(lines) if depth else "\n".join(lines)
    if isinstance(v, list):
        if not v:
            return "[]"
        if all(not isinstance(x, (dict, list)) for x in v):
            body = ", ".join(_short(x) for x in v[:maxlist])
            more = f", ... x{len(v)}" if len(v) > maxlist else ""
            return f"[{body}{more}]"
        parts = []
        for x in v[:maxlist]:
            r = _fmt_value(x, depth + 1)
            parts.append(("  " * (depth + 1)) + "- " + r.strip())
        more = f"\n{'  ' * (depth + 1)}... {len(v)} items" if len(v) > maxlist else ""
        return "\n" + "\n".join(parts) + more
    return _short(v)


def _short(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, str):
        return repr(v)
    return str(v)


def analyse(project: str = "racbasicsampleproject", seq: int = 102,
            cache_dir: Optional[str] = None, limit: Optional[int] = None,
            decoder: Optional[ObjectDecoder] = None, keep_samples: int = 3,
            collect_ids: bool = False):
    """Decode every record of a project's element segment; collect stats."""
    dec = decoder or ObjectDecoder()
    seg = load_segment(project, seq, cache_dir)
    per_class = defaultdict(lambda: {"n": 0, "clean": 0, "consumed": 0, "total": 0,
                                     "err": Counter(), "samples": [], "fail": None})
    ref_ids: set = set() if collect_ids else None  # every ElementId seen in values
    n = 0
    for rec in iter_records(seg, seq):
        if rec.elem_id < 0:      # save-unit sentinel record
            continue
        n += 1
        obj = dec.decode_record(rec.class_id, rec.payload)
        st = per_class[rec.class_id]
        st["n"] += 1
        st["consumed"] += obj.consumed
        st["total"] += obj.total
        if obj.clean:
            st["clean"] += 1
            if collect_ids:
                _collect_element_ids(obj.value, ref_ids)
        else:
            key = obj.errors[0]["error"] if obj.errors else f"trailing {obj.total - obj.consumed} bytes"
            fld = obj.errors[0]["field"] if obj.errors else "<end>"
            st["err"][(fld, key)] += 1
            if st["fail"] is None:
                off = obj.errors[0]["offset"] if obj.errors else obj.consumed
                lo = max(0, off - 24)
                st["fail"] = {
                    "elem_id": rec.elem_id, "field": fld, "error": key, "offset": off,
                    "consumed": obj.consumed, "total": obj.total,
                    "hex": rec.payload[lo:off].hex(" ") + " | " + rec.payload[off:off + 40].hex(" "),
                }
        if keep_samples and len(st["samples"]) < keep_samples and obj.clean:
            st["samples"].append((rec.elem_id, obj))
        if limit and n >= limit:
            break
    return dec, per_class, n, ref_ids


def _collect_element_ids(v, out: set):
    """Gather plausible ElementId values (positive int64s) from a decoded tree."""
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(x, int) and not isinstance(x, bool):
                if x > 0 and ("Id" in k or "_id" in k):
                    out.add(x)
            else:
                _collect_element_ids(x, out)
    elif isinstance(v, list):
        for x in v:
            _collect_element_ids(x, out)


def rate_table(dec, per_class, top=None):
    rows = []
    for cls, st in sorted(per_class.items(), key=lambda kv: -kv[1]["n"]):
        rate = 100.0 * st["clean"] / max(st["n"], 1)
        cov = 100.0 * st["consumed"] / max(st["total"], 1)
        mean_cons = st["consumed"] / max(st["n"], 1)
        mean_tot = st["total"] / max(st["n"], 1)
        rows.append((cls, dec.class_name(cls), st["n"], st["clean"], rate, cov,
                     mean_cons, mean_tot))
    return rows[:top] if top else rows


def offset_experiment(project: str, seq: int = 102, cache_dir=None,
                      offsets=(-2, -1, 0, 1, 2), limit: int = 4000):
    """Prove the class_word -> schema type_id mapping.

    Decode the same records with the header class id shifted by ``k`` and
    measure the fraction that decode CLEANLY (100% of body bytes consumed,
    no error).  The true mapping maximises clean decodes.
    """
    dec = ObjectDecoder()
    seg = load_segment(project, seq, cache_dir)
    recs = [r for _, r in zip(range(limit), (x for x in iter_records(seg, seq) if x.elem_id >= 0))]
    out = {}
    for k in offsets:
        clean = 0
        cov = 0.0
        for r in recs:
            cid = r.class_id + k
            if cid not in dec.schema.by_id:
                continue
            obj = dec.decode_record(cid, r.payload)
            clean += obj.clean
            cov += obj.consumed / max(obj.total, 1)
        out[k] = {"records": len(recs), "clean": clean,
                  "clean_rate": clean / max(len(recs), 1),
                  "mean_byte_cov": cov / max(len(recs), 1)}
    return out


def order_experiment(project: str, seq: int = 102, cache_dir=None, limit: int = 4000):
    """Parent-first vs self-first field order over the same records."""
    seg = load_segment(project, seq, cache_dir)
    recs = [r for _, r in zip(range(limit), (x for x in iter_records(seg, seq) if x.elem_id >= 0))]
    out = {}
    for order in ("parent_first", "self_first"):
        dec = ObjectDecoder()
        dec.self_first = order == "self_first"
        clean = 0
        for r in recs:
            obj = dec.decode_record(r.class_id, r.payload)
            clean += obj.clean
        out[order] = {"records": len(recs), "clean": clean,
                      "clean_rate": clean / max(len(recs), 1)}
    return out


def collect_strings(v, out: list, path=""):
    """All AString values in a decoded tree, with field name."""
    if isinstance(v, dict):
        for k, x in v.items():
            collect_strings(x, out, k)
    elif isinstance(v, list):
        for x in v:
            collect_strings(x, out, path)
    elif isinstance(v, str) and v:
        out.append((path, v))


def sample_instances(project: str, seq: int = 102, cache_dir=None,
                     per_class: int = 3, top: int = 15, decoder=None):
    """Top classes by count -> first N cleanly decoded instances each."""
    dec = decoder or ObjectDecoder()
    seg = load_segment(project, seq, cache_dir)
    counts = Counter()
    for r in iter_records(seg, seq):
        if r.elem_id >= 0:
            counts[r.class_id] += 1
    want = {c for c, _ in counts.most_common(top)}
    got = defaultdict(list)
    for r in iter_records(seg, seq):
        if r.elem_id < 0 or r.class_id not in want or len(got[r.class_id]) >= per_class:
            continue
        obj = dec.decode_record(r.class_id, r.payload)
        if obj.clean:
            got[r.class_id].append((r.elem_id, obj))
        if len(got) == len(want) and all(len(v) >= per_class for v in got.values()):
            break
    return counts, got


# classes we always want represented in the sample dump (readable proof of
# real values: names, elevations, ids, MEP data)
DEFAULT_EXTRA_CLASSES = (
    "Level", "SWall", "Grid", "CategoryElem", "DBViewPlan", "DBView3d",
    "BasicWallType", "FamilySymbol", "FamilyInstance", "ElectricalSetting",
    "ElectricalLoadClassification", "RbsElectricalSystem", "ConnectorElem",
    "RbsWireCurve", "RbsConduitCurve", "PanelScheduleView", "RbsVoltageType",
    "RbsDistributionSysType", "ProjectInfo",
)


def _prune(v, max_list: int = 40, depth: int = 0):
    """JSON-friendly copy with long lists capped (records can be huge)."""
    if isinstance(v, dict):
        return {k: _prune(x, max_list, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        out = [_prune(x, max_list, depth + 1) for x in v[:max_list]]
        if len(v) > max_list:
            out.append(f"... {len(v) - max_list} more (total {len(v)})")
        return out
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            return str(v)
        return round(v, 9)
    return v


def collect_samples(project: str = "racbasicsampleproject", seq: int = 102,
                    cache_dir: Optional[str] = None, per_class: int = 3, top: int = 15,
                    extra_classes=DEFAULT_EXTRA_CLASSES, limit: int = 100,
                    decoder: Optional[ObjectDecoder] = None) -> list:
    """Top classes by count x per_class, plus targeted classes, capped at limit."""
    dec = decoder or ObjectDecoder()
    seg = load_segment(project, seq, cache_dir)
    counts: Counter = Counter()
    for r in iter_records(seg, seq):
        if r.elem_id >= 0:
            counts[r.class_id] += 1
    want: dict = {c: per_class for c, _ in counts.most_common(top)}
    for name in extra_classes:
        cd = dec.schema.by_name.get(name)
        if cd is not None and cd.type_id in counts:
            want.setdefault(cd.type_id, per_class)
    # fill the remaining budget with one instance each of further classes
    for c, _ in counts.most_common():
        if sum(min(w, counts[cc]) for cc, w in want.items()) >= limit:
            break
        want.setdefault(c, 1)
    got: dict = defaultdict(list)
    for r in iter_records(seg, seq):
        if r.elem_id < 0 or r.class_id not in want:
            continue
        if len(got[r.class_id]) >= want[r.class_id]:
            continue
        obj = dec.decode_record(r.class_id, r.payload)
        rec = {
            "project": project, "seq": seq, "element_id": r.elem_id,
            "class_id": f"{r.class_id:#06x}", "class": obj.class_name,
            "clean": obj.clean, "consumed": obj.consumed, "total": obj.total,
            "value": _prune(obj.value),
        }
        if obj.errors:
            rec["errors"] = obj.errors
        got[r.class_id].append(rec)
    out: list = []
    order = [c for c, _ in counts.most_common(top)]
    order += [c for c in want if c not in order]
    for c in order:
        out.extend(got.get(c, []))
        if len(out) >= limit:
            break
    return out[:limit]


def write_samples_json(path: str, project: str = "racbasicsampleproject", **kw) -> int:
    samples = collect_samples(project, **kw)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump({"project": project,
                   "framing": "record = i64 id, u32 stamp, u32 psize, "
                              "u16 class_id, object[psize-2], u32 psize",
                   "count": len(samples), "instances": samples}, fh, indent=1, default=str)
    return len(samples)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    project = args[0] if args else "racbasicsampleproject"
    seq = int(args[1]) if len(args) > 1 else 102
    cache = os.environ.get("RVT_SEG_CACHE")
    dec, per_class, n, _ = analyse(project, seq=seq, cache_dir=cache)
    tot_clean = sum(st["clean"] for st in per_class.values())
    cons = sum(st["consumed"] for st in per_class.values())
    tot = sum(st["total"] for st in per_class.values())
    print(f"{project} seq {seq}: {n} records, {len(per_class)} classes; clean "
          f"full-record decodes {tot_clean} ({100.0 * tot_clean / max(n, 1):.2f}%); "
          f"byte coverage {100.0 * cons / max(tot, 1):.2f}%")
    print(f"{'class':>7} {'name':32s} {'records':>8} {'clean':>7} {'rate':>6} "
          f"{'byte-cov':>8} {'mean cons/total':>18}")
    for cls, name, cnt, clean, rate, cov, mc, mt in rate_table(dec, per_class, 40):
        print(f"{cls:#06x} {name:32s} {cnt:8d} {clean:7d} {rate:6.1f} {cov:8.1f} "
              f"{mc:9.1f}/{mt:.1f}")
    fails = [(st["n"] - st["clean"], cls, st["fail"]) for cls, st in per_class.items()
             if st["fail"] is not None]
    print("\nfirst failures:" if fails else "\nno failures.")
    for nf, cls, fl in sorted(fails, reverse=True)[:10]:
        print(f"  x{nf:<5} {dec.class_name(cls)} id={fl['elem_id']} {fl['error']} "
              f"@{fl['offset']:#x} in {fl['field'][-70:]}")
        print(f"         {fl['hex']}")
    if "--samples" in flags:
        counts, got = sample_instances(project, seq, cache, per_class=3, top=15, decoder=dec)
        for cls in [c for c, _ in counts.most_common(15)]:
            for eid, obj in got.get(cls, [])[:1]:
                print(f"\n--- {dec.class_name(cls)} ({cls:#06x}) element {eid} "
                      f"[{obj.consumed}/{obj.total}] ---")
                print(_fmt_value(obj.value)[:1600])
    if "--json" in flags:
        path = os.path.join(EXTRACTED, "_objects", "racbasic_sample.json")
        k = write_samples_json(path, project, seq=seq, cache_dir=cache)
        print(f"\nwrote {k} decoded instances -> {path}")
    if "--experiments" in flags:
        print("\nclass_word mapping (identity vs offsets), 4000 records:")
        for k, v in offset_experiment(project, seq, cache).items():
            print(f"  type_id = class_id{k:+d}: clean {v['clean']}/{v['records']} "
                  f"({100 * v['clean_rate']:.2f}%), mean byte cov {100 * v['mean_byte_cov']:.1f}%")
        print("field order:")
        for k, v in order_experiment(project, seq, cache).items():
            print(f"  {k}: clean {v['clean']}/{v['records']} ({100 * v['clean_rate']:.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
