"""#932: the family build got faster without moving a byte.

Every speed-up in #932 replaces a computation with a cheaper one that must
give the SAME answer; these tests pin each equivalence against the slow form
it replaced, on real documents:

* ``build_unit_segments(cache=...)`` == the uncached encode, also after a
  record changes between calls and after the encoder (schema) changes;
* the encoder's precompiled class plans and lazy field paths == the general
  path -- the same bytes for every record of a built family, and the same
  exception type and message for a bad value or a missing field;
* ``geometry._assert_pid_stable`` (read-only) == the copy-and-renumber
  reference, on real breps and on tampered ones;
* decoder plans shared per schema == a decoder's own plans == the reference
  walk;
* the loader's ``_dc`` == ``copy.deepcopy``, shared sub-objects included;
* a ``decode_memo`` scope returns what decoding afresh returns and replays
  the ``ref_sink`` / ``plan_bails`` effects of the first decode;
* ``RvtDocument.inflate`` / ``inflate_all`` (payloads kept from the member
  scan) == inflating each member afresh; ``iter_records`` == its reference
  form, truncated segments included;
* the donor caches of the provenance scan == reading the donor afresh, and
  re-read when the donor file changes;
* ``gcpolicy.build_gc`` restores the collector's thresholds, nested or not.
"""
from __future__ import annotations

import copy
import gc
import hashlib
import os
import shutil
import struct
import tempfile
import zlib

import pytest

from rvt import encode as E
from rvt.famgen import factory as F
from rvt.famgen import geometry as G
from rvt.famgen import loader as L
from rvt.famgen import skeleton as SK
from rvt.genesis import skeleton as GSK
from rvt import objects as O
from rvt.objects import ObjectDecoder


@pytest.fixture(scope="module")
def doc():
    d = F.make_transformer(name="L932").doc     # the largest equipment document on main
    d.finalize()
    return d


def _enc():
    return GSK._SCHEMA_CACHE["enc"]


class _GeneralOnly(E.ObjectEncoder):
    """The encoder with every precompiled op switched off: each field takes
    the general _encode_field path, exactly as before #932."""

    def _class_plan(self, class_id, native_ids=True):
        return tuple((k, f, 0, None)
                     for k, f, _op, _p in super()._class_plan(class_id, native_ids))


def _records(doc):
    enc = _enc()
    return [(e.elem_id, seq, cid, obj) for e in doc.elements
            for seq, cid, obj in e.records(class_ids=enc.class_id_of)]


# -- build_unit_segments cache ----------------------------------------------------

def test_the_cached_segments_are_the_uncached_segments(doc):
    plain = SK.build_unit_segments(doc.elements)
    cache: dict = {}
    assert SK.build_unit_segments(doc.elements, cache=cache) == plain
    assert len(cache["records"]) == len(_records(doc))
    assert SK.build_unit_segments(doc.elements, cache=cache) == plain    # all hits
    assert doc.partition_payloads() == plain


def test_a_changed_record_is_re_encoded_not_served_from_the_cache(doc):
    cache: dict = {}
    SK.build_unit_segments(doc.elements, cache=cache)
    rp = next(e for e in doc.elements if e.class_name == "RefPlane")
    old = copy.deepcopy(rp.obj)
    try:
        rp.obj["m_freeEnd"] = [v + 0.25 for v in rp.obj["m_freeEnd"]]
        got = SK.build_unit_segments(doc.elements, cache=cache)
        assert got == SK.build_unit_segments(doc.elements)
        # a value that is == but not the same type/sign is a different key
        assert SK._record_key(102, 1, 2, {"a": -0.0}) != SK._record_key(102, 1, 2, {"a": 0.0})
        assert SK._record_key(102, 1, 2, {"a": True}) != SK._record_key(102, 1, 2, {"a": 1})
        assert SK._record_key(102, 1, 2, {"a": 1}) != SK._record_key(102, 1, 2, {"a": 1.0})
        assert SK._record_key(102, 1, 2, {"a": [1]}) != SK._record_key(102, 1, 2, {"a": (1,)})
    finally:
        rp.obj.clear()
        rp.obj.update(old)
    assert SK.build_unit_segments(doc.elements, cache=cache) == SK.build_unit_segments(doc.elements)


def test_the_id_width_era_starts_the_segment_cache_afresh(doc):
    """#933 review: a document encoded natively, then under ids32, must not be
    served its cached i64 bytes."""
    from rvt.versions import records32 as R32
    cache: dict = {}
    native = SK.build_unit_segments(doc.elements, cache=cache)
    with R32.ids32():
        cached = SK.build_unit_segments(doc.elements, cache=cache)
        fresh = SK.build_unit_segments(doc.elements)
    assert cached == fresh and cached != native
    assert SK.build_unit_segments(doc.elements, cache=cache) == native


def test_a_new_encoder_starts_the_cache_afresh(doc):
    cache: dict = {}
    SK.build_unit_segments(doc.elements, cache=cache)
    first = cache["enc"]
    saved = dict(GSK._SCHEMA_CACHE)
    try:
        GSK._SCHEMA_CACHE["enc"] = E.ObjectEncoder(decoder=saved["dec"])
        got = SK.build_unit_segments(doc.elements, cache=cache)
        assert cache["enc"] is GSK._SCHEMA_CACHE["enc"] is not first
        assert got == SK.build_unit_segments(doc.elements)
    finally:
        GSK._SCHEMA_CACHE.clear()
        GSK._SCHEMA_CACHE.update(saved)


# -- encoder plans + lazy paths -----------------------------------------------------

def test_the_precompiled_encoder_writes_what_the_general_path_writes(doc):
    fast = _enc()
    slow = _GeneralOnly(decoder=fast.dec)
    n = 0
    for eid, seq, cid, obj in _records(doc):
        assert fast.encode_record(seq, eid, 0, cid, obj) == \
            slow.encode_record(seq, eid, 0, cid, obj), (eid, seq)
        n += 1
    assert n > 1000


def test_under_ids32_the_precompiled_encoder_writes_32_bit_ids(doc):
    """#933 review: the 2023 era patches Writer.element_id to i32; the
    precompiled ElementId op must not pack i64 underneath it."""
    from rvt.versions import records32 as R32
    fast = _enc()
    slow = _GeneralOnly(decoder=fast.dec)
    native = {(eid, seq): fast.encode_record(seq, eid, 0, cid, obj)
              for eid, seq, cid, obj in _records(doc)}
    with R32.ids32():
        n = changed = 0
        for eid, seq, cid, obj in _records(doc):
            got = fast.encode_record(seq, eid, 0, cid, obj)
            assert got == slow.encode_record(seq, eid, 0, cid, obj), (eid, seq)
            changed += got != native[(eid, seq)]
            n += 1
    assert n > 1000 and changed > 100               # ids really were re-sized
    # and the native plans are untouched once the era is restored
    eid, seq, cid, obj = next(iter(_records(doc)))
    assert fast.encode_record(seq, eid, 0, cid, obj) == native[(eid, seq)]


def _raised(enc, cid, obj):
    """The outcome of one encode: its bytes, or (exception type, message, path)."""
    try:
        return ("bytes", enc.encode_object(cid, obj))
    except Exception as e:                                         # noqa: BLE001
        return type(e), str(e), getattr(e, "path", None)


@pytest.mark.parametrize("field, bad", [
    ("m_freeEnd", "not a point"),          # XYZ op
    ("m_freeEnd", [1.0, 2.0]),             # short
    ("m_cutVec", None),
])
def test_a_bad_value_raises_exactly_what_the_general_path_raises(doc, field, bad):
    fast = _enc()
    slow = _GeneralOnly(decoder=fast.dec)
    rp = next(e for e in doc.elements if e.class_name == "RefPlane")
    cid = fast.class_id_of("RefPlane")
    obj = copy.deepcopy(rp.obj)
    obj[field] = bad
    assert _raised(fast, cid, obj) == _raised(slow, cid, obj)


def test_bad_primitives_and_ids_raise_like_the_general_path(doc):
    fast = _enc()
    slow = _GeneralOnly(decoder=fast.dec)
    hits = 0
    for e in doc.elements[:400]:
        cid = fast.class_id_of(e.class_name)
        for key, f, op, _p in fast._class_plan(cid):
            if not op or op in (E._OP_PTR, E._OP_VCLASS):
                continue
            obj = copy.deepcopy(e.obj)
            obj[key] = "x" if op != E._OP_BOOL else None
            got = _raised(fast, cid, obj)
            assert got == _raised(slow, cid, obj), (e.class_name, key)
            hits += got[0] != "bytes"
            break
    assert hits > 20


def test_a_missing_nested_field_names_its_full_path(doc):
    enc = _enc()
    ext = next(e for e in doc.elements if e.class_name == "ExtrusionElem")
    obj = copy.deepcopy(ext.obj)
    del obj["m_pParamValueSetDouble"]["value"]["m_paramSet"]
    t, msg, path = _raised(enc, enc.class_id_of("ExtrusionElem"), obj)
    assert t is E.EncodeError
    assert msg == ("missing field 'm_paramSet' @ "
                   "ExtrusionElem.m_pParamValueSetDouble->ParamValueSetDouble.m_paramSet")
    assert path == "ExtrusionElem.m_pParamValueSetDouble->ParamValueSetDouble.m_paramSet"
    assert E.path_str((("A", ".", "b"), "[", 3)) == "A.b[3]"


# -- pid self-check ---------------------------------------------------------------------

def _breps(doc):
    return [e.rep for e in doc.elements
            if isinstance(getattr(e, "rep", None), dict) and "ptr_class" in str(e.rep)[:20000]]


def _verdict(fn, obj):
    try:
        fn(obj)
        return "ok"
    except AssertionError:
        return "bad"


def test_the_read_only_pid_check_agrees_with_the_copy_check(doc):
    objs = [e.obj for e in doc.elements] + [e.rep for e in doc.elements if isinstance(e.rep, dict)]
    n_bad = 0
    for o in objs:
        assert _verdict(G._assert_pid_stable, o) == _verdict(G._assert_pid_stable_by_copy, o)
        n_bad += _verdict(G._assert_pid_stable, o) == "bad"
    # tampered: a moved pid and a missing pid are both caught by both
    toks = []

    def find(v):
        if isinstance(v, dict):
            if "ptr_class" in v and v["ptr_class"] in G.REGISTERED_CLASSES:
                toks.append(v)
            for x in v.values():
                find(x)
        elif isinstance(v, list):
            for x in v:
                find(x)
    host = next(o for o in objs if (toks.clear() or find(o) or toks)
                and _verdict(G._assert_pid_stable, o) == "ok")
    for tamper in ("move", "drop"):
        o = copy.deepcopy(host)
        toks.clear()
        find(o)
        if tamper == "move":
            toks[0]["pid"] += 7
        else:
            del toks[0]["pid"]
        assert _verdict(G._assert_pid_stable, o) == "bad" == _verdict(G._assert_pid_stable_by_copy, o)


# -- shared decoder plans ---------------------------------------------------------------

def test_decoders_of_one_schema_share_plans_and_decode_like_the_walk(doc):
    dec0 = _enc().dec
    a, b = ObjectDecoder(dec0.schema), ObjectDecoder(dec0.schema)
    walk = ObjectDecoder(dec0.schema)
    walk.use_plans = False
    enc = _enc()
    n = 0
    for eid, seq, cid, obj in _records(doc):
        if seq != 102:
            continue
        payload = enc.encode_object(cid, obj)
        va, vb, vw = (d.decode_record(cid, payload) for d in (a, b, walk))
        assert va.value == vb.value == vw.value
        n += 1
    assert n > 300
    shared = [k for k in a._plans if a._plans[k] is b._plans.get(k)]
    assert shared and len(shared) == len(a._plans)


# -- loader deep copy -------------------------------------------------------------------

def test_the_loader_copy_is_a_deep_copy_with_sharing_kept(doc):
    leaf = {"x": [1, 2.5, None, True, "s"]}
    tree = {"a": leaf, "b": [leaf, leaf], "c": doc.elements[5].obj}
    got = L._dc(tree)
    assert got == copy.deepcopy(tree)
    assert got["a"] is got["b"][0] is got["b"][1] and got["a"] is not leaf
    assert L._dc(object) is copy.deepcopy(object)      # pickle-by-reference types too


# -- the decode memo ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def written(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("l932") / "p.rfa")
    F.make_panelboard(name="M932").write(path)
    return path


def _file_records(path):
    from rvt.families import FamilyIndex, unit_segments
    idx = FamilyIndex(path)
    segs = unit_segments(idx, 0)
    return idx.schema, [(r.class_id, r.payload) for r in O.iter_records(segs[102], 102)
                        if r.elem_id >= 0]


def test_a_memo_scope_decodes_what_a_fresh_decoder_decodes(written):
    schema, recs = _file_records(written)
    fresh = ObjectDecoder(schema)
    want = [(o.value, o.clean, o.stub, o.consumed, o.errors)
            for o in (fresh.decode_record(c, p) for c, p in recs)]
    with O.decode_memo():
        for _ in range(2):                         # the second pass is all hits
            dec = ObjectDecoder(schema)
            sink: list = []
            dec.ref_sink = sink
            got, sinks = [], []
            for c, p in recs:
                sink.clear()
                o = dec.decode_record(c, p)
                got.append((o.value, o.clean, o.stub, o.consumed, o.errors))
                sinks.append(list(sink))
            assert got == want
            ref = ObjectDecoder(schema)
            ref_sinks = []
            for c, p in recs:
                rs: list = []
                ref.ref_sink = rs
                O.ObjectDecoder._decode_record_once(ref, c, p)
                ref_sinks.append(rs)
            assert sinks == ref_sinks
        assert len(O._MEMO.rows) == len({(c, bytes(p)) for c, p in recs})
    assert O._MEMO.rows is None                    # dropped with the scope


def test_a_sink_less_first_read_never_hides_refs_from_a_later_sink_ful_read(written):
    """#933 review: FamilyIndex / provenance decode with no ref_sink BEFORE the
    validator's semantic layer decodes with one; the memo must still hand the
    validator every ElementId the record carries."""
    schema, recs = _file_records(written)
    ref = ObjectDecoder(schema)
    want = []
    for c, p in recs:
        rs: list = []
        ref.ref_sink = rs
        O.ObjectDecoder._decode_record_once(ref, c, p)
        want.append(rs)
    assert sum(map(len, want)) > 100
    with O.decode_memo():
        blind = ObjectDecoder(schema)               # no sink: the first reader
        for c, p in recs:
            blind.decode_record(c, p)
        assert blind.ref_sink is None               # the temporary sink is gone
        dec = ObjectDecoder(schema)
        got = []
        for c, p in recs:
            sink: list = []
            dec.ref_sink = sink
            dec.decode_record(c, p)
            got.append(sink)
    assert got == want


def test_a_memo_hit_replays_the_plan_bails_and_nested_scopes_share(written):
    schema, recs = _file_records(written)
    c, p = recs[0]
    with O.decode_memo():
        a = ObjectDecoder(schema)
        a.use_plans = False                        # the walk: a different key, no bail
        oa = a.decode_record(c, p)
        with O.decode_memo():                      # nested: the outer scope stays
            b = ObjectDecoder(schema)
            ob = b.decode_record(c, p)
            assert O._MEMO.rows is not None
        assert O._MEMO.rows is not None
        assert oa.value == ob.value and oa is not ob
        rows = O._MEMO.rows
        key = next(k for k in rows if k[-1] == bytes(p) and k[1])
        obj, refs, _bails = rows[key]
        rows[key] = (obj, refs, ("_Bail",))        # as if the first decode had bailed
        d = ObjectDecoder(schema)
        assert d.decode_record(c, p) is obj
        assert d.plan_bails == {"_Bail": 1}


def test_a_decoder_subclass_is_never_memoized(written):
    schema, recs = _file_records(written)

    class Sub(ObjectDecoder):
        pass

    with O.decode_memo():
        Sub(schema).decode_record(*recs[0])
        assert O._MEMO.rows == {}


# -- container + record framing ------------------------------------------------------------

def test_inflate_serves_the_member_scan_payloads(written):
    from rvt.container import open_rvt, _inflate_at
    with open_rvt(written) as f:
        names = [s.name for s in f.streams()]
        n = 0
        for name in names:
            ms = f.members(name)
            if not ms:
                continue
            data = f.logical(name)
            fresh = [_inflate_at(bytes(data), m.offset)[0] for m in ms]
            assert list(f.inflate_all(name)) == fresh
            assert [f.inflate(name, i) for i in range(len(ms))] == fresh
            n += len(ms)
    assert n > 5


def _iter_records_reference(seg, seq=102):
    """``objects.iter_records`` as it read before #932 (format strings, the
    payload sliced then re-sliced)."""
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
        yield O.Record(eid, stamp, cls, size, payload, p, trailer_ok)
        p = tail_off + 4


def test_iter_records_reads_what_the_reference_framing_reads(written):
    from rvt.families import FamilyIndex, unit_segments
    segs = unit_segments(FamilyIndex(written), 0)
    for seq, seg in segs.items():
        cuts = {len(seg), len(seg) - 1, len(seg) - 7, len(seg) // 2, 37, 3}
        for cut in sorted(c for c in cuts if c >= 0):
            for buf in (seg[:cut], bytearray(seg[:cut])):
                got = list(O.iter_records(buf, seq))
                assert got == list(_iter_records_reference(buf, seq)), (seq, cut)
        assert len(list(O.iter_records(seg, seq))) > 100
    bad = bytearray(segs[102])
    bad[12:16] = struct.pack("<I", 1 << 31)        # an implausible size stops both
    assert list(O.iter_records(bytes(bad))) == list(_iter_records_reference(bytes(bad)))


# -- donor caches ------------------------------------------------------------------------------

def test_the_donor_caches_read_what_the_donor_holds_and_follow_its_file(tmp_path):
    from rvt.famgen import famdoc_adoc as FA
    from rvt.frontdoor.standalone import bundled_base_path
    src = bundled_base_path()
    donor = str(tmp_path / "donor.rvt")
    shutil.copyfile(src, donor)
    FA._DONOR_IDS_CACHE.clear()
    FA._DONOR_LATEST_CACHE.clear()
    first = FA.donor_element_ids(donor)
    assert first and FA.donor_element_ids(donor) == first
    first.append(-5)                                # callers get their own list
    assert FA.donor_element_ids(donor)[-1] != -5
    payload = b"\x00" * 50 + open(src, "rb").read()[:4000]
    lcr = FA._longest_common_run(payload, donor)
    FA._DONOR_LATEST_CACHE.clear()
    assert FA._longest_common_run(payload, donor) == lcr
    # another file at the same path is read afresh (mtime/size key)
    other = F.make_panelboard(name="D932")
    other.write(donor)
    st = os.stat(donor)
    os.utime(donor, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    from rvt.families import FamilyIndex
    want = sorted({int(i) for i in FamilyIndex(donor).unit_records(0)[102] if int(i) >= 4700})
    assert FA.donor_element_ids(donor) == want != first[:-1]


# -- gc pacing -----------------------------------------------------------------------------------

def test_build_gc_restores_the_thresholds_nested_or_not():
    from rvt import gcpolicy
    before = gc.get_threshold()
    with gcpolicy.build_gc():
        assert gc.get_threshold() == gcpolicy.BUILD_THRESHOLDS
        gc.set_threshold(1234, 5, 6)               # an inner scope never touches it
        with gcpolicy.build_gc():
            assert gc.get_threshold() == (1234, 5, 6)
        assert gc.get_threshold() == (1234, 5, 6)
    assert gc.get_threshold() == before
    with pytest.raises(RuntimeError):
        with gcpolicy.build_gc():
            raise RuntimeError("x")
    assert gc.get_threshold() == before


def test_overlapping_build_jobs_restore_the_host_thresholds_when_the_last_leaves():
    """#933 review: the outer job leaving first must not strand the inner
    one's pacing or the host's own thresholds."""
    from rvt import gcpolicy
    host = gc.get_threshold()
    outer, inner = gcpolicy.build_gc(), gcpolicy.build_gc()
    outer.__enter__()
    inner.__enter__()
    outer.__exit__(None, None, None)               # out of order, as two threads can
    assert gc.get_threshold() == gcpolicy.BUILD_THRESHOLDS
    inner.__exit__(None, None, None)
    assert gc.get_threshold() == host
    with gcpolicy.build_gc():                       # and the next job paces again
        assert gc.get_threshold() == gcpolicy.BUILD_THRESHOLDS
    assert gc.get_threshold() == host


def test_past_the_payload_budget_members_are_re_inflated_identically(written, monkeypatch):
    from rvt import container as C
    from rvt.container import open_rvt
    with open_rvt(written) as d:
        names = [s.name for s in d.streams() if d.members(s.name)]
        want = {n: list(d.inflate_all(n)) for n in names}
    monkeypatch.setattr(C, "PAYLOAD_CACHE_BUDGET", 0)
    with open_rvt(written) as d:
        for n in names:
            assert list(d.inflate_all(n)) == want[n]
            assert d.inflate(n, 0) == want[n][0]
        assert d._payload_cache == {} and d._payload_bytes == 0
