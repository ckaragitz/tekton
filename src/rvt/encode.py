"""Schema-directed ENCODER for serialized Revit element objects.

The exact inverse of :mod:`rvt.objects` (the wave-3 decoder).  Given the
nested value dict that :class:`rvt.objects.ObjectDecoder` produces for a
partition record, :class:`ObjectEncoder` re-serializes it back to the very
same bytes -- verified byte-for-byte over every cleanly-decodable seq-102
record of racbasic + rmebasic and over whole seq-101/102/103 segments
(``tests/test_encode.py``, ``docs/streams/12-encode.md``).

Codebook symmetry (decoder ``Reader``  <->  encoder ``Writer``)::

    u8/i16/u16/i32/u32/i64/u64/f32/f64  ->  struct pack, little-endian
    bool                                ->  u8 (True=1, False=0).  The decoder
                                            always yields a Python ``bool``
                                            (any non-zero byte -> True, both
                                            read paths), so a non-0/1 wire byte
                                            would re-encode as 1 -- the round
                                            trips above met none; a raw int in
                                            a hand-built dict writes its low byte
    AString                             ->  u32 UTF-16 code-unit count +
                                            UTF-16LE; ``None`` -> the null
                                            sentinel 0xFFFFFFFF; ``""`` -> 0
                                            (lone surrogates survive via
                                            ``surrogatepass`` on both sides)
    GUID (16 raw)                       ->  parsed back from the decoder's
                                            ``d1-d2-d3-t0t1-t2..7`` string
    ElementId / Identifier              ->  i64 (-1 invalid), flattened
    XYZ / UV                            ->  3 / 2 fixed doubles
    fixed array (flags>>4 == 1)         ->  elements only, count from schema
    container (flags>>4 == 5)           ->  u32 count + elements
    inline array (kind 0x0d)            ->  anonymous element field repeated
    owned/poly pointer (0e 01/02/04)    ->  i32 pid; 0 = null (4 bytes);
                                            {"backref_pid"} -> i32 pid only;
                                            otherwise + u16 class and the
                                            pointed-to body is DEFERRED onto a
                                            per-record FIFO exactly as the
                                            decoder queued it (breadth-first),
                                            reproducing the ORIGINAL pid
                                            numbering because the decoder
                                            preserved every pid it read
    weak pointer (0e 03)                 ->  u32 pid
    class-def ref (kind 0x0a)           ->  u16 class index (by name)

Record framing (:func:`encode_record`) is the uniform framing proven by the
decoder: ``i64 id`` [+ ``u32 stamp`` for seq 102/103] + ``u32 psize`` +
``u16 class_id`` + object bytes + ``u32 psize`` repeat, with psize = 2 +
len(object bytes); save-unit sentinels (id -1) have psize 0 and no class
word.

Public API::

    enc = ObjectEncoder()                      # loads the canonical schema
    body = enc.encode_object(class_id, value)  # object bytes (record payload)
    rec  = enc.encode_record(seq, elem_id, stamp, class_id, value)
    seg  = reencode_segment(seg_bytes, seq)    # decode+re-encode every record

``python -m rvt.encode [project] [seq]`` runs the byte-exact round-trip
report over a whole element segment.
"""
from __future__ import annotations

import os
import struct
import sys
from collections import Counter, deque
from typing import Any, Optional

from .schema import Schema, ClassDef, Field, load_schema
from .objects import (ObjectDecoder, iter_records, load_segment, Record,
                      _PRIM_FMT, field_key)

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides

_PSIZE = struct.Struct("<I")
_U16 = struct.Struct("<H")


class EncodeError(Exception):
    def __init__(self, path: str, msg: str):
        super().__init__(f"{msg} @ {path}")
        self.path = path
        self.msg = msg


# ---------------------------------------------------------------------------
class Writer:
    """Little-endian byte writer -- the mirror of :class:`rvt.objects.Reader`."""

    __slots__ = ("buf",)

    def __init__(self):
        self.buf = bytearray()

    # -- primitives (one method per Reader primitive) -------------------------
    def u8(self, v: int):
        self.buf += struct.pack("<B", v & 0xFF if isinstance(v, int) else int(v))

    def bool(self, v):
        # decoded values are always Python bools -> exactly 0/1 (module
        # docstring: bool); the int branch only serves hand-built value dicts
        if isinstance(v, bool):
            self.buf.append(1 if v else 0)
        else:
            self.buf.append(int(v) & 0xFF)

    def i16(self, v: int):
        self.buf += struct.pack("<h", v)

    def u16(self, v: int):
        self.buf += struct.pack("<H", v)

    def i32(self, v: int):
        self.buf += struct.pack("<i", v)

    def u32(self, v: int):
        self.buf += struct.pack("<I", v)

    def i64(self, v: int):
        self.buf += struct.pack("<q", v)

    def u64(self, v: int):
        self.buf += struct.pack("<Q", v)

    def f32(self, v: float):
        self.buf += struct.pack("<f", v)

    def f64(self, v: float):
        self.buf += struct.pack("<d", v)

    def raw(self, b: bytes):
        self.buf += b

    def astring(self, s: Optional[str]):
        """AString: u32 UTF-16 code-unit count + UTF-16LE; None -> 0xFFFFFFFF."""
        if s is None:
            self.u32(0xFFFFFFFF)
            return
        enc = s.encode("utf-16-le", errors="surrogatepass")
        self.u32(len(enc) // 2)
        self.buf += enc

    def guid(self, g: str):
        """Inverse of Reader.guid(): 'd1-d2-d3-t0t1-t2t3t4t5t6t7' -> 16 raw bytes."""
        self.buf += guid_to_bytes(g)

    def element_id(self, v: int):
        self.i64(v)

    def xyz(self, v):
        self.buf += struct.pack("<3d", *v)

    def uv(self, v):
        self.buf += struct.pack("<2d", *v)

    def bytes(self) -> bytes:
        return bytes(self.buf)

    def __len__(self):
        return len(self.buf)


def guid_to_bytes(g: str) -> bytes:
    """Parse the decoder's GUID string form back into its 16 raw bytes."""
    d1, d2, d3, t4, tail = g.split("-")
    return (struct.pack("<IHH", int(d1, 16), int(d2, 16), int(d3, 16))
            + bytes.fromhex(t4) + bytes.fromhex(tail))


# ---------------------------------------------------------------------------
class _Pend:
    __slots__ = ("class_id", "value", "path")

    def __init__(self, class_id, value, path):
        self.class_id = class_id
        self.value = value
        self.path = path


class ObjectEncoder:
    """Serialises decoded object dicts using the parsed schema.

    Structurally the transpose of :class:`rvt.objects.ObjectDecoder`: same
    class chain (parent-first), same per-field dispatch, same breadth-first
    deferred-body queue -- every ``Reader.x()`` call site has a ``Writer.x()``
    call site here.
    """

    def __init__(self, schema: Optional[Schema] = None,
                 decoder: Optional[ObjectDecoder] = None):
        # share the decoder's schema + chain cache when one is supplied
        self.dec = decoder or ObjectDecoder(schema)
        self.schema = self.dec.schema
        d = self.dec
        self.id_ElementId = d.id_ElementId
        self.id_Identifier = d.id_Identifier
        self.id_XYZ = d.id_XYZ
        self.id_UV = d.id_UV
        self.id_GUIDvalue = d.id_GUIDvalue

    # -- schema helpers ------------------------------------------------------
    def chain(self, class_id: int) -> list[ClassDef]:
        return self.dec.chain(class_id)

    def class_id_of(self, name: str) -> int:
        cd = self.schema.by_name.get(name)
        if cd is not None:
            return cd.type_id
        # decoder renders unknown ids as '<class 0x1234>' (never in clean data)
        if name.startswith("<class ") and name.endswith(">"):
            return int(name[7:-1], 16)
        raise EncodeError(name, f"unknown class name {name!r}")

    # -- entry points --------------------------------------------------------
    def encode_object(self, class_id: int, value: dict) -> bytes:
        """Serialize one object tree (the inverse of decode_record).

        Returns the object bytes only -- the record ``payload`` (no leading
        u16 class id, no size trailer), i.e. exactly the byte string that
        :func:`rvt.objects.iter_records` yields as ``Record.payload``.
        """
        if class_id not in self.schema.by_id:
            raise EncodeError("<root>", f"unknown class id {class_id:#x}")
        w = Writer()
        queue: deque[_Pend] = deque()
        root_name = self.dec.class_name(class_id)
        self._encode_class(w, class_id, value or {}, queue, root_name)
        # breadth-first deferred pointed-to bodies, in the queue order the
        # decoder used (its FIFO is reconstructed 1:1 from the value tree)
        while queue:
            pend = queue.popleft()
            self._encode_class(w, pend.class_id, pend.value or {}, queue,
                               f"{pend.path}->{self.dec.class_name(pend.class_id)}")
        return w.bytes()

    def encode_record(self, seq: int, elem_id: int, stamp: int, class_id: int,
                      value: Optional[dict], psize: Optional[int] = None) -> bytes:
        """Full record framing bytes (header + payload + size-repeat trailer).

        ``psize`` overrides the payload size for the two degenerate record
        kinds that carry no object: save-unit sentinels (id -1, psize 0, no
        class word) and any other explicit size.  For normal records
        psize = 2 + len(object bytes).
        """
        if elem_id < 0 or psize == 0:
            # save-unit sentinel: no class word, no object
            hdr = struct.pack("<qI", elem_id, 0) if seq == 101 \
                else struct.pack("<qII", elem_id, stamp, 0)
            return hdr + _PSIZE.pack(0)
        body = self.encode_object(class_id, value or {})
        ps = 2 + len(body)
        hdr = struct.pack("<qI", elem_id, ps) if seq == 101 \
            else struct.pack("<qII", elem_id, stamp, ps)
        return hdr + _U16.pack(class_id) + body + _PSIZE.pack(ps)

    # -- class body ------------------------------------------------------------
    def _encode_class(self, w: Writer, class_id: int, value: dict,
                      queue: deque, path: str):
        if not isinstance(value, dict):
            raise EncodeError(path, f"class body must be a dict, got {type(value).__name__}")
        seen: dict = {}
        for cd in self.chain(class_id):
            for f in cd.fields:
                fpath = f"{path}.{f.name}"
                # identical shadowed-name keying rule as the decoder
                key = field_key(cd, f, seen)
                seen[key] = True
                if key not in value:
                    raise EncodeError(fpath, f"missing field {key!r}")
                self._encode_field(w, f, value[key], queue, fpath)

    # -- one field -------------------------------------------------------------
    def _encode_field(self, w: Writer, f: Field, v: Any, queue: deque, path: str):
        kind = f.kind
        flags = f.flags
        shape = flags >> 4
        indir = flags & 0x0F

        if kind == 0x08:                                   # AString
            if shape == 0x5 or shape == 0x1:
                if shape == 0x5:
                    w.u32(len(v))
                for s in v:
                    w.astring(s)
                return
            w.astring(v)
            return

        if kind == 0x0D:                                   # inline array wrapper
            elem = f.element
            if elem is None:
                raise EncodeError(path, f"array field {f.name} without element descriptor")
            if shape == 0x5:
                w.u32(len(v))
            for i, x in enumerate(v):
                self._encode_field(w, elem, x, queue, f"{path}[{i}]")
            return

        if shape == 0x5:                                   # growable container
            w.u32(len(v))
            for i, x in enumerate(v):
                self._encode_scalar(w, f, kind, indir, x, queue, f"{path}[{i}]")
            return

        if shape == 0x1:                                   # fixed array
            for i, x in enumerate(v):
                self._encode_scalar(w, f, kind, indir, x, queue, f"{path}[{i}]")
            return

        self._encode_scalar(w, f, kind, indir, v, queue, path)

    def _encode_scalar(self, w: Writer, f: Field, kind: int, indir: int, v: Any,
                       queue: deque, path: str):
        if kind in _PRIM_FMT:
            if kind == 0x01:
                w.bool(v)
                return
            fmt, _sz = _PRIM_FMT[kind]
            try:
                w.buf += struct.pack(fmt, v)
            except struct.error as e:
                raise EncodeError(path, f"{f.name}: {e}")
            return
        if kind == 0x08:
            w.astring(v)
            return
        if kind == 0x09:
            w.guid(v)
            return
        if kind == 0x0A:                                   # class-definition ref
            name = v["classref"] if isinstance(v, dict) else v
            w.u16(self.class_id_of(name))
            return
        if kind == 0x0E:
            if indir == 0:                                 # inline value class
                if f.type_id is None:
                    raise EncodeError(path, f"typed value field {f.name} without type id")
                self._encode_value_class(w, f.type_id, v, queue, path)
                return
            if indir == 3:                                 # weak pointer
                w.u32(v["weakref"] if isinstance(v, dict) else v)
                return
            self._encode_pointer(w, v, queue, path)
            return
        raise EncodeError(path, f"unsupported kind {kind:#x} in {f.name}")

    # -- value classes -----------------------------------------------------
    def _encode_value_class(self, w: Writer, type_id: int, v: Any, queue: deque,
                            path: str):
        if type_id == self.id_ElementId or type_id == self.id_Identifier:
            w.element_id(v)
            return
        if type_id == self.id_XYZ:
            w.xyz(v)
            return
        if type_id == self.id_UV:
            w.uv(v)
            return
        if type_id == self.id_GUIDvalue:
            w.guid(v)
            return
        self._encode_class(w, type_id, v, queue, path)

    # -- pointer token ---------------------------------------------------------
    def _encode_pointer(self, w: Writer, v: Any, queue: deque, path: str):
        if v is None:
            w.i32(0)
            return
        if isinstance(v, dict) and "backref_pid" in v:
            w.i32(v["backref_pid"])
            return
        if not isinstance(v, dict) or "ptr_class" not in v:
            raise EncodeError(path, f"bad pointer token {v!r}")
        cls = self.class_id_of(v["ptr_class"])
        w.i32(v.get("pid", -1))
        w.u16(cls)
        queue.append(_Pend(cls, v.get("value") or {}, path))


# ---------------------------------------------------------------------------
# Round-trip harness (decode -> encode -> compare)
# ---------------------------------------------------------------------------

def record_bytes(seg: bytes, rec: Record, seq: int) -> bytes:
    """The ORIGINAL raw bytes of a record (header + payload + trailer)."""
    hlen = 12 if seq == 101 else 16
    return seg[rec.seg_offset: rec.seg_offset + hlen + rec.body_size + 4]


def first_divergence(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n if len(a) != len(b) else -1


def field_at_offset(dec: ObjectDecoder, class_id: int, payload: bytes,
                    payload_off: int) -> str:
    """Best-effort: which field path is being decoded at payload offset."""
    # re-decode with an instrumented reader is overkill; walk field starts
    # instead by decoding a truncated payload and reporting the error path.
    try:
        obj = dec.decode_record(class_id, payload[:payload_off])
    except Exception as e:                                 # pragma: no cover
        return f"<{e}>"
    if obj.errors:
        return obj.errors[0]["field"]
    return "<end-of-object>"


def roundtrip_segment(seg: bytes, seq: int, enc: Optional[ObjectEncoder] = None,
                      only_clean: bool = True, limit: Optional[int] = None):
    """Decode->encode every record; compare bytes.  Returns a stats dict.

    ``only_clean``: records whose decode is not clean are excluded from the
    tested set (they cannot be re-encoded from a lossy dict); their count is
    reported.  A record is counted a PASS iff the re-encoded record bytes
    are IDENTICAL to the original (header, sizes, class id, object, trailer).
    """
    enc = enc or ObjectEncoder()
    dec = enc.dec
    st = {"records": 0, "tested": 0, "pass": 0, "fail": 0, "skipped_unclean": 0,
          "skipped_bad_trailer": 0, "by_class": Counter(), "fail_by_class": Counter(),
          "failures": []}
    for rec in iter_records(seg, seq):
        st["records"] += 1
        orig = record_bytes(seg, rec, seq)
        if rec.elem_id < 0:                               # save-unit sentinel
            got = enc.encode_record(seq, rec.elem_id, rec.stamp, 0, None, psize=0)
            st["tested"] += 1
            if got == orig:
                st["pass"] += 1
            else:
                st["fail"] += 1
                st["failures"].append({"elem_id": rec.elem_id, "class": "<sentinel>",
                                        "div": first_divergence(orig, got)})
            continue
        obj = dec.decode_record(rec.class_id, rec.payload)
        if not obj.clean:
            st["skipped_unclean"] += 1
            if only_clean:
                continue
        if not rec.trailer_ok:
            st["skipped_bad_trailer"] += 1
            if only_clean:
                continue
        st["tested"] += 1
        st["by_class"][rec.class_id] += 1
        try:
            got = enc.encode_record(seq, rec.elem_id, rec.stamp, rec.class_id, obj.value)
        except EncodeError as e:
            st["fail"] += 1
            st["fail_by_class"][rec.class_id] += 1
            if len(st["failures"]) < 40:
                st["failures"].append({"elem_id": rec.elem_id, "class": obj.class_name,
                                        "error": str(e)})
            continue
        if got == orig:
            st["pass"] += 1
        else:
            st["fail"] += 1
            st["fail_by_class"][rec.class_id] += 1
            if len(st["failures"]) < 40:
                st["failures"].append(describe_mismatch(dec, seq, rec, obj, orig, got))
        if limit and st["tested"] >= limit:
            break
    return st


def describe_mismatch(dec: ObjectDecoder, seq: int, rec: Record, obj, orig: bytes,
                      got: bytes) -> dict:
    """Diagnose the first divergence between original and re-encoded record."""
    div = first_divergence(orig, got)
    hlen = 12 if seq == 101 else 16
    body_off = div - (hlen + 2)          # offset inside the object payload
    lo = max(0, div - 16)
    fld = "?"
    if body_off >= 0:
        fld = field_at_offset(dec, rec.class_id, rec.payload, body_off)
    return {
        "elem_id": rec.elem_id, "class": obj.class_name, "class_id": rec.class_id,
        "orig_len": len(orig), "got_len": len(got), "div": div,
        "payload_off": body_off, "field": fld,
        "orig_hex": orig[lo:div].hex(" ") + " | " + orig[div:div + 24].hex(" "),
        "got_hex": got[lo:div].hex(" ") + " | " + got[div:div + 24].hex(" "),
    }


def reencode_segment(seg: bytes, seq: int, enc: Optional[ObjectEncoder] = None):
    """Re-serialize a WHOLE per-seq segment.

    Every record is decoded and re-encoded; records that do not decode
    cleanly (Extensible-Storage entity blobs -- see 10-objects.md B1) and
    save-unit sentinels are passed through as their original raw bytes.
    Returns (bytes, stats).
    """
    enc = enc or ObjectEncoder()
    dec = enc.dec
    out = bytearray()
    n = clean = passthru = 0
    end = 0
    for rec in iter_records(seg, seq):
        n += 1
        hlen = 12 if seq == 101 else 16
        end = rec.seg_offset + hlen + rec.body_size + 4
        if rec.elem_id < 0:
            out += enc.encode_record(seq, rec.elem_id, rec.stamp, 0, None, psize=0)
            continue
        obj = dec.decode_record(rec.class_id, rec.payload)
        if obj.clean and rec.trailer_ok:
            out += enc.encode_record(seq, rec.elem_id, rec.stamp, rec.class_id, obj.value)
            clean += 1
        else:
            out += record_bytes(seg, rec, seq)               # opaque pass-through
            passthru += 1
    out += seg[end:]                                        # any trailing tail
    return bytes(out), {"records": n, "reencoded": clean, "passthrough": passthru,
                        "tail": len(seg) - end}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    project = argv[0] if argv else "racbasicsampleproject"
    seqs = [int(a) for a in argv[1:]] or [102]
    cache = os.environ.get("RVT_SEG_CACHE")
    enc = ObjectEncoder()
    for seq in seqs:
        seg = load_segment(project, seq, cache)
        st = roundtrip_segment(seg, seq, enc)
        rate = 100.0 * st["pass"] / max(st["tested"], 1)
        print(f"{project} seq {seq}: records {st['records']}, tested {st['tested']}, "
              f"pass {st['pass']} ({rate:.3f}%), fail {st['fail']}, "
              f"skipped unclean {st['skipped_unclean']}")
        for cid, k in st["fail_by_class"].most_common(10):
            print(f"   fail x{k:<5} {enc.dec.class_name(cid)} ({cid:#06x})")
        for fl in st["failures"][:8]:
            print(f"   {fl}")
        # whole-segment reconstruction
        rebuilt, ss = reencode_segment(seg, seq, enc)
        div = first_divergence(seg, rebuilt)
        print(f"   whole-segment: {len(seg):,} -> {len(rebuilt):,} bytes, "
              f"identical={rebuilt == seg} (first divergence {div}), {ss}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# Module-level convenience (the contract rvt.mutate.Document.serialize()
# expects): encode ONE new/edited record, computing the stamp if not given.
# ---------------------------------------------------------------------------
_DEFAULT_ENCODER = None


def record_stamp(class_id: int, obj_bytes: bytes = b"") -> int:
    """seq-102/103 record stamp = adler32(u16 class_id + object bytes).

    Verified rule (mutation-planner, 287,441/287,441 corpus records).
    Sentinel records use adler32(b"") == 1.
    """
    import zlib as _zlib
    if class_id is None:
        return _zlib.adler32(b"") & 0xFFFFFFFF
    return _zlib.adler32(_U16.pack(class_id) + obj_bytes) & 0xFFFFFFFF


def encode_record(seq: int, elem_id: int, stamp, class_id: int, value) -> bytes:
    """Encode one record dict into framed record bytes.

    ``stamp=None`` (the normal case for freshly created / edited objects)
    computes the correct adler32 stamp from the encoded object bytes.
    seq 101 records carry no stamp.
    """
    global _DEFAULT_ENCODER
    if _DEFAULT_ENCODER is None:
        _DEFAULT_ENCODER = ObjectEncoder()
    enc = _DEFAULT_ENCODER
    if elem_id < 0:
        s = 1 if stamp is None else stamp
        return enc.encode_record(seq, elem_id, s, 0, None, psize=0)
    if seq == 101 or stamp is not None:
        return enc.encode_record(seq, elem_id, 0 if stamp is None else stamp,
                                 class_id, value)
    body = enc.encode_object(class_id, value or {})
    ps = 2 + len(body)
    st = record_stamp(class_id, body)
    hdr = struct.pack("<qII", elem_id, st, ps)
    return hdr + _U16.pack(class_id) + body + _PSIZE.pack(ps)
