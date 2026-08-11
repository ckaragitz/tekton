"""The object decoder's compiled-plan read path is invisible (issue #427).

``rvt.objects.ObjectDecoder.decode_record`` decodes a record through a
per-class compiled plan (fused ``struct`` runs, precomputed keys, no path
strings) and hands anything that path raises to the field-by-field reference
walk, which is also the only path a hook-overriding subclass takes.  The
contract pinned here, on every seq-102 record of the three bundled genesis
bases: the plan path returns exactly what the reference walk returns --
values (and their Python types), ``consumed``/``total``, ``clean``/``stub``,
``n_deferred``, errors -- and its ``ref_sink`` (field name, ElementId) stream
is the reference walk's, which in turn is the leaf of the full field path a
``_decode_value_class`` override sees.  Truncated / corrupt payloads report
the very same error dicts either way, and the validator's semantic layer says
the same thing (findings, stats) whichever path read the records, dangling-
reference message with its exact field path included.

Fresh-clone runnable (tracked bundled bases; the damaged copy is written to
``tmp_path``); in the CI shard via tests/ci_shard.d/427-objects-plans.txt.

Run: .venv/bin/python -m pytest tests/test_objects_plans.py -q
"""
from __future__ import annotations

import os
import struct
from contextlib import ExitStack

import pytest

from conftest import context_constants
from rvt import objects as O
from rvt.objects import ObjectDecoder, Reader, _fmt_guid, leaf_name
from rvt.schema import Field
from rvt.validate import (Validator, _iter_seg_records, _RefDecoder, enter_own_release,
                          validate_file)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}

pytestmark = [pytest.mark.skipif(not all(os.path.isfile(p) for p in BASES.values()),
                                 reason="bundled genesis bases missing"),
              pytest.mark.usefixtures("no_release_leak")]   # the corpus climbs the ladder; one row authors damage

@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches the names the authoring context swaps too, not the framing table alone."""
    return context_constants

# the plan path's only legitimate exits: it declines (_Bail) or runs out of
# bytes (struct.error); any other exception type there is a plan bug
LEGIT_BAILS = {"_Bail", struct.error.__name__}


def _records(path: str, stack: ExitStack):
    """(schema, [(elem_id, class_id, payload), ...]) of every seq-102 record
    of ``path``, read under the file's own release (kept in force on ``stack``)."""
    enter_own_release(stack, path)
    v = Validator(path)
    v._open()
    stack.callback(v.ole.close)
    v._walkers()
    schema = v._load_schema()
    recs = []
    for _pname, segs in v.unit_segments.items():
        for (unit, seq), buf in segs.items():
            if seq != 102:
                continue
            for r in _iter_seg_records(buf, seq, unit):
                if r.elem_id >= 0 and r.body_size >= 2:
                    recs.append((r.elem_id, r.class_id,
                                 buf[r.payload_off + 2:r.payload_off + r.body_size]))
    assert schema is not None and len(recs) > 3000
    return schema, recs


def _same(a: O.DecodedObject, b: O.DecodedObject) -> bool:
    fa = (a.class_id, a.class_name, a.consumed, a.total, a.errors, a.n_deferred, a.stub, a.clean)
    fb = (b.class_id, b.class_name, b.consumed, b.total, b.errors, b.n_deferred, b.stub, b.clean)
    # repr pins structure, key order AND value types (bool vs int, list vs
    # tuple), and unlike == it calls two identical NaN doubles equal
    return fa == fb and repr(a.value) == repr(b.value)


@pytest.fixture(scope="module")
def corpus():
    """{year: (schema, records)} -- read once per module."""
    out = {}
    with ExitStack() as stack:
        for year, path in BASES.items():
            out[year] = _records(path, stack)
        yield out


# ---------------------------------------------------------------------------
# 1. every record of every bundled base: plan path == reference walk
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("year", sorted(BASES))
def test_plan_path_equals_reference_walk_on_every_record(corpus, year):
    schema, recs = corpus[year]
    fast = ObjectDecoder(schema)
    slow = ObjectDecoder(schema)
    slow.use_plans = False
    hooked = _RefDecoder(schema)                # ids by full path via a hook override
    assert fast._hooks_native and slow._hooks_native and not hooked._hooks_native
    for eid, cls, payload in recs:
        fast.ref_sink, slow.ref_sink, hooked.refs = [], [], []
        a = fast.decode_record(cls, payload)
        b = slow.decode_record(cls, payload)
        c = hooked.decode_record(cls, payload)
        assert _same(a, b) and _same(b, c), (year, eid, a.class_name)
        assert fast.ref_sink == slow.ref_sink == [(leaf_name(p), v) for p, v in hooked.refs], \
            (year, eid, a.class_name)
        if not a.clean:                         # a record the walk faults: the plan path bailed
            assert sum(fast.plan_bails.values()) >= 1
    # the plan path is the one doing the work: it declines at most the decode-
    # gap record or two the walk also faults, and only ever by its two exits
    bailed = sum(fast.plan_bails.values())
    assert bailed <= 2 and bailed == sum(1 for _e, c, p in recs
                                         if not slow.decode_record(c, p).clean), fast.plan_bails
    assert set(fast.plan_bails) <= LEGIT_BAILS, fast.plan_bails
    assert not slow.plan_bails and not hooked.plan_bails      # they never tried


def test_hook_override_never_takes_the_plan_path(corpus, monkeypatch):
    schema, recs = corpus[2025]
    hooked = _RefDecoder(schema)
    monkeypatch.setattr(ObjectDecoder, "_decode_record_planned",
                        lambda self, c, p: pytest.fail("plan path taken under a hook override"))
    for _eid, cls, payload in recs[:200]:
        hooked.decode_record(cls, payload)
    assert hooked.refs, "the override saw no ElementId -- it was bypassed"

    class NamesOnly(ObjectDecoder):             # even a class_name override counts
        def class_name(self, class_id):
            return super().class_name(class_id).upper()
    assert not NamesOnly._hooks_native and ObjectDecoder._hooks_native
    assert NamesOnly(schema).decode_record(recs[0][1], recs[0][2]).class_name.isupper()


def test_instance_patched_hook_takes_the_walk_and_sees_every_field(corpus, monkeypatch):
    """Hooks are meant to be overridden by subclassing, but a hook assigned on
    an *instance* must not be silently bypassed by the plans either (#449):
    that instance drops to the reference walk -- whether patched before or
    after its first decode -- and the patch sees exactly the fields a subclass
    override sees.  Other instances and the class keep the plan path."""
    schema, recs = corpus[2025]
    sample = recs[:300]

    def patch(dec):
        seen = []
        inner = dec._decode_value_class         # the bound original
        def spy(rd, type_id, queue, state, path):
            v = inner(rd, type_id, queue, state, path)
            if type_id == dec.id_ElementId:
                seen.append((path, v))
            return v
        dec._decode_value_class = spy
        return seen

    fresh = ObjectDecoder(schema)               # patched before any decode
    seen_fresh = patch(fresh)
    late = ObjectDecoder(schema)                # patched after plans were compiled and used
    for _eid, cls, payload in sample[:50]:
        assert late.decode_record(cls, payload).clean
    assert late._plans and late._hooks_native
    seen_late = patch(late)
    assert not fresh._hooks_native and not late._hooks_native
    assert ObjectDecoder._hooks_native and ObjectDecoder(schema)._hooks_native   # per instance only

    monkeypatch.setattr(ObjectDecoder, "_decode_record_planned",
                        lambda self, c, p: pytest.fail("plan path taken under an instance patch"))
    hooked = _RefDecoder(schema)                # the subclass way (== the walk, pinned by test 1)
    n_ids = 0
    for eid, cls, payload in sample:
        del seen_fresh[:], seen_late[:]
        hooked.refs = []
        ref = hooked.decode_record(cls, payload)
        assert _same(fresh.decode_record(cls, payload), ref), eid
        assert _same(late.decode_record(cls, payload), ref), eid
        assert seen_fresh == seen_late == hooked.refs, (eid, ref.class_name)
        n_ids += len(hooked.refs)
    assert n_ids > 500                                        # the sample does exercise the hook
    assert not fresh.plan_bails and not late.plan_bails       # they never tried (after the patch)


def test_ids32_era_takes_the_walk(corpus, monkeypatch):
    """rvt.versions.records32 swaps Reader.element_id for a 32-bit read
    (Revit <= 2023).  Plans assume the 64-bit read, so while that patch is
    in force every record goes through the walk -- and thereby through the
    patched method, exactly as before plans existed."""
    from rvt.versions import records32
    schema, recs = corpus[2025]
    fast = ObjectDecoder(schema)
    slow = ObjectDecoder(schema)
    slow.use_plans = False
    monkeypatch.setattr(ObjectDecoder, "_decode_record_planned",
                        lambda self, c, p: pytest.fail("plan path taken in the 32-bit era"))
    with records32.ids32():
        assert Reader.element_id is not O._ELEMENT_ID64
        for _eid, cls, payload in recs[:150]:
            fast.ref_sink, slow.ref_sink = [], []
            assert _same(fast.decode_record(cls, payload), slow.decode_record(cls, payload))
            assert fast.ref_sink == slow.ref_sink
    assert Reader.element_id is O._ELEMENT_ID64            # restored: plans are back
    monkeypatch.undo()
    fast.decode_record(recs[0][1], recs[0][2])
    assert not fast.plan_bails


def test_flattened_value_classes_compile_flat(corpus):
    """The walk flattens ElementId/Identifier/XYZ/UV/GUIDvalue in
    _decode_value_class; the compiler must never plan them as a nested class
    (E_CLASS) and must give the fixed-size ones a run slot -- one ladder."""
    schema, _recs = corpus[2025]
    dec = ObjectDecoder(schema)
    flat = {"id_ElementId": O.E_ID, "id_Identifier": O.E_ID, "id_XYZ": O.E_XYZ,
            "id_UV": O.E_UV, "id_GUIDvalue": O.E_GUID}
    for attr, code in flat.items():
        t = getattr(dec, attr)
        assert t is not None, attr
        f = Field(name="m_x", kind=0x0E, flags=0x00, offset=0, type_id=t)
        assert dec._compile_elem(f, "m_x")[0] == code, attr
        assert dec._fixed_slot(f) is not None, attr
        arr = Field(name="m_xs", kind=0x0E, flags=0x10, offset=0, type_id=t, count=3)
        assert (dec._fixed_slot(arr) is not None) == (code == O.E_ID), attr   # id arrays fuse
    other = next(c for c in schema.classes if c.fields and c.type_id not in
                 {getattr(dec, a) for a in flat})
    f = Field(name="m_o", kind=0x0E, flags=0x00, offset=0, type_id=other.type_id)
    assert dec._compile_elem(f, "m_o")[0] == O.E_CLASS and dec._fixed_slot(f) is None


# ---------------------------------------------------------------------------
# 2. damaged payloads: identical error reports (the walk is the reporter)
# ---------------------------------------------------------------------------
def test_truncated_and_corrupt_payloads_report_identically(corpus):
    schema, recs = corpus[2025]
    fast = ObjectDecoder(schema)
    slow = ObjectDecoder(schema)
    slow.use_plans = False
    # a spread of classes: the 40 largest distinct-class records + 40 small ones
    by_cls = {}
    for eid, cls, payload in recs:
        if cls not in by_cls or len(payload) > len(by_cls[cls][2]):
            by_cls[cls] = (eid, cls, payload)
    sample = sorted(by_cls.values(), key=lambda r: -len(r[2]))[:40] + recs[:40]
    checked = 0
    for eid, cls, payload in sample:
        step = max(1, len(payload) // 60)
        for cut in range(0, len(payload), step):            # every truncation depth
            a = fast.decode_record(cls, payload[:cut])
            b = slow.decode_record(cls, payload[:cut])
            assert _same(a, b), (eid, cut)
            checked += 1
        smashed = payload[:8] + b"\xff" * (len(payload) - 8)  # implausible counts / lengths
        zeroed = bytes(len(payload))
        for bad in (smashed, zeroed, payload + b"\x00\x00\x00", payload[3:]):
            assert _same(fast.decode_record(cls, bad), slow.decode_record(cls, bad)), eid
        assert _same(fast.decode_record(0xFFFE, payload), slow.decode_record(0xFFFE, payload))
    assert checked > 2000


def test_ref_sink_is_reset_when_the_plan_path_bails(corpus):
    """A record the plan path gives up on half-way leaves no half-read ids
    behind: the sink holds exactly what the reference walk read."""
    schema, recs = corpus[2025]
    eid, cls, payload = max(recs, key=lambda r: len(r[2]))
    fast = ObjectDecoder(schema)
    slow = ObjectDecoder(schema)
    slow.use_plans = False
    for cut in (len(payload) // 3, len(payload) // 2, len(payload) - 1):
        fast.ref_sink, slow.ref_sink = [("keep", 7)], [("keep", 7)]
        a = fast.decode_record(cls, payload[:cut])
        b = slow.decode_record(cls, payload[:cut])
        assert not a.clean and _same(a, b)
        assert fast.ref_sink == slow.ref_sink and fast.ref_sink[0] == ("keep", 7)


def test_reader_primitives_and_plan_primitives_agree():
    raw = bytes(range(16))
    assert Reader(raw).guid() == _fmt_guid(0x03020100, 0x0504, 0x0706, raw[8:]) \
        == "03020100-0504-0706-0809-0a0b0c0d0e0f"
    # AString: the plan path's codec shortcut == Reader.astring, lone
    # surrogates (surrogatepass), BOM-looking prefixes, empty and null included
    for units in ([0xD800], [0x41, 0xDC00], [0xFEFF, 0x42], [0xFFFE], [], [0xD83D, 0xDE00]):
        body = struct.pack("<I", len(units)) + b"".join(struct.pack("<H", u) for u in units)
        cx = O._Cx(body, None)
        assert O._astring(cx) == Reader(body).astring() and cx.p == len(body)
    null = struct.pack("<I", 0xFFFFFFFF)
    assert O._astring(O._Cx(null, None)) is None is Reader(null).astring()
    assert leaf_name("HostObj.m_a->Sub.m_ids[3]") == "m_ids"
    assert leaf_name("Level.m_levelTypeId") == "m_levelTypeId"
    assert leaf_name("A.m_arr[1][2]") == "m_arr"


# ---------------------------------------------------------------------------
# 3. the validator says the same thing whichever path read the records
# ---------------------------------------------------------------------------
def _report(path: str, use_plans: bool, monkeypatch) -> dict:
    monkeypatch.setattr(ObjectDecoder, "use_plans", use_plans)
    d = validate_file(path).to_json()
    d.pop("timings")
    return d


@pytest.mark.parametrize("year", sorted(BASES))
def test_validator_report_identical_either_path(year, monkeypatch):
    walked = _report(BASES[year], False, monkeypatch)
    planned = _report(BASES[year], True, monkeypatch)
    assert planned == walked
    assert planned["stats"]["refs_checked"] > 40000 and planned["counts"]["error"] == 0


def test_dangling_reference_message_keeps_its_exact_path(tmp_path, monkeypatch):
    """A view whose associated-level id points at nothing: the semantic ERROR
    names the id by its full field path -- read back through the path-recording
    walk for that one owner -- identically under either decode path."""
    from rvt import manipulate as M
    from rvt.frontdoor.release_ctx import release_build_context
    from rvt.mutate import Document
    base = BASES[2025]
    bad = str(tmp_path / "dangling.rvt")
    with release_build_context(base):
        doc = Document.from_file(base)
        view = doc.ids_of_class("DBViewPlan")[0]
        plan = M.modify_element(doc, view, {"m_assocLevelId": 987654321},
                                kind="test-damage", reason="dangling level id")
        M.commit_plans(base, bad, [plan])
    walked = _report(bad, False, monkeypatch)
    planned = _report(bad, True, monkeypatch)
    assert planned == walked
    errors = [f for f in planned["findings"] if f["severity"] == "error"]
    assert len(errors) == 1 and errors[0]["where"] == "references", errors
    msg = errors[0]["message"]
    assert msg.startswith("1 dangling ElementId reference(s)") and "m_assocLevelId x1" in msg
    assert f"element {view} DBViewPlan.m_assocLevelId=987654321" in msg, msg
