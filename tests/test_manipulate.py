"""manipulation layer: edit / move / retype / delete EXISTING elements.

Unit tests cover the pure helpers; the end-to-end tests run the four
operations against ``samples/rstbasicsampleproject.rvt`` (the smallest
sample) through the real writer and prove each output with
``verify_manipulated`` + a semantic re-read.
"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")


def _need(path):
    if not os.path.exists(path):
        pytest.skip(f"sample not present: {path}")


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------
def test_get_set_path():
    from rvt.manipulate import get_path, set_path
    v = {"a": {"value": {"b": [1, 2, {"c": 3}]}}}
    assert get_path(v, "a.value.b[2].c") == 3
    old = set_path(v, "a.value.b[2].c", 9)
    assert old == 3 and get_path(v, "a.value.b[2].c") == 9
    set_path(v, "a.value.b[0]", -1)
    assert get_path(v, "a.value.b[0]") == -1


def test_neutralise_rules():
    from rvt.manipulate import _neutralise
    v = {
        "m_hostId": 500,                                   # scalar -> -1
        "m_deletion": [1, 500, 2],                         # bare id removed
        "m_joins": [{"m_id": 500, "x": 1}, {"m_id": 7}],   # struct entry dropped
        "m_conn": [{"ptr_class": "Connector", "pid": 4,   # ptr entry KEPT,
                    "value": {"m_arrRefs": [{"m_id": 500, "m_nIndex": 0}],
                              "m_x": 1}}],                 # refs neutralised inside
        "m_tag": 500,                                      # topology tag: NOT an id
    }
    edits = _neutralise(v, {500})
    assert v["m_hostId"] == -1
    assert v["m_deletion"] == [1, 2]
    assert v["m_joins"] == [{"m_id": 7}]
    assert len(v["m_conn"]) == 1                          # connector kept
    assert v["m_conn"][0]["value"]["m_arrRefs"] == []
    assert v["m_tag"] == 500                               # skip-key untouched
    kinds = {e["action"] for e in edits}
    assert kinds == {"set-invalid", "remove-id", "drop-entry"}


def test_peer_and_annotation_classification():
    from rvt.manipulate import _honors_deletion_parents, _is_peer_class
    for cls in ("SWall", "RoomElem", "RbsHvacSystem", "RbsPipingSystem",
                "RbsDuctCurve", "VarSketch", "MEPNetworkDataElem"):
        assert _is_peer_class(cls), cls
    for cls in ("IndependentTag", "RoomTag", "LinearDimString",
                "PostedWarningElem", "PanelScheduleView"):
        assert _honors_deletion_parents(cls), cls
    # a family instance / host is neither a peer nor an annotation dependent:
    assert not _honors_deletion_parents("FamilyInstance")
    assert not _honors_deletion_parents("SWall")


def test_chunk_and_edit_segment_roundtrip():
    _need(RST)
    from rvt.container import open_rvt
    from rvt.manipulate import (_ISIZE_ADJ, apply_edits_to_segment,
                                chunk_segment)
    from rvt.objects import iter_records
    from rvt.partitions import StreamWalker
    with open_rvt(RST) as d:
        pn = d.partition_streams()[0]
        w = StreamWalker(d.logical(pn), inflate=True, keep_data=True)
    seg = b"".join(b.data for b in sorted(w.blocks, key=lambda b: b.hdr_offset)
                   if b.unit == 0 and b.seq == 102)
    blocks = chunk_segment(seg, 102, budget=131072)
    # concatenation reproduces the segment; per-block A counts the records
    assert b"".join(b["payload"] for b in blocks) == seg
    a_total = sum(b["A"] for b in blocks)
    recs = list(iter_records(seg, 102))
    assert a_total == len(recs)                      # incl. the sentinel
    for b in blocks:
        # the corpus block identity: ISIZE == hdr*A + C + adj(flags)
        assert len(b["payload"]) == 20 * b["A"] + b["C"] + _ISIZE_ADJ[b["flags"]]
    # remove one element, keep the sentinel last
    victim = recs[3].elem_id
    seg2, st = apply_edits_to_segment(seg, 102, {victim}, {})
    assert st["removed"] == 1 and st["sentinel_last"]
    ids2 = {r.elem_id for r in iter_records(seg2, 102)}
    assert victim not in ids2 and -1 in ids2


# ---------------------------------------------------------------------------
# end-to-end (rstbasicsampleproject, ~6 s per commit)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def rst_doc():
    _need(RST)
    from rvt.mutate import Document
    return Document.from_file(RST)


def _healthy(v, expect_deleted=(), expect_edited=()):
    assert v["crc_failures"] == 0
    assert v["ecc_mismatches"] == 0
    assert v["walker_errors"] == 0
    assert v["isize_identity_mismatches"] == 0
    assert v["stamps_ok"]
    assert all(v["sentinel_last"].values())
    assert v["elemtable_count"] == v["header_count"]
    assert v["elemtable_ids_sorted"] and v["unit0_ids_equal_elemtable"]
    assert not v["deleted_still_present"] and not v["deleted_in_elemtable"]
    for eid in expect_edited:
        e = v["edited"][str(eid)]
        assert all(x["clean"] for x in e.values()), (eid, e)


def test_modify_level_elevation_roundtrip(rst_doc, tmp_path):
    from rvt import manipulate as M
    from rvt.mutate import Document
    lvl = 245423                                   # 'Level 2'
    before = rst_doc._level_elevation(lvl)
    plan = M.set_level_elevation(rst_doc, lvl, before + 1.25)
    assert plan.record_edits and plan.changes
    out = str(tmp_path / "level.rvt")
    rep = M.commit_plans(RST, out, [plan])
    assert rep.elemtable_count_before == rep.elemtable_count_after
    v = M.verify_manipulated(out, edited_ids=[lvl])
    _healthy(v, expect_edited=[lvl])
    assert abs(Document.from_file(out)._level_elevation(lvl) - (before + 1.25)) < 1e-9


def test_delete_isolated_instance(tmp_path):
    from rvt import manipulate as M
    from rvt.mutate import Document
    doc = Document.from_file(RST)                  # fresh session
    victim = None
    for eid in doc.ids_of_class("FamilyInstance"):
        if M.candidate_referrers(doc, {eid}):
            continue
        rep = M.dependency_report(doc, eid)
        if not rep["dependents"] and not rep["referrers"]:
            victim = eid
            break
    if victim is None:
        pytest.skip("no isolated instance found in rstbasic")
    plan = M.delete_element(doc, victim)
    assert plan.ids_to_remove == [victim] and not plan.referrer_edits
    out = str(tmp_path / "del.rvt")
    rep = M.commit_plans(RST, out, [plan])
    assert rep.elemtable_count_after == rep.elemtable_count_before - 1
    v = M.verify_manipulated(out, deleted_ids=[victim])
    _healthy(v)
    d2 = Document.from_file(out)
    assert victim not in d2.et_by_id and victim not in d2.idx[102]
    assert d2.et.footer.last_id == doc.et.footer.last_id      # watermark kept


def test_delete_with_dependents_fails_loudly_then_cascades(tmp_path):
    from rvt import manipulate as M
    from rvt.mutate import Document
    doc = Document.from_file(RST)
    lvl = 245423                                   # 'Level 2' carries elements
    with pytest.raises(M.DependentsError) as ei:
        M.delete_element(doc, lvl)
    rep = ei.value.report
    assert rep["dependents"], "a level with elements must report dependents"
    assert any(d["relation"] == "associated-level" for d in rep["dependents"])
    # a small cascade: pick an element with exactly a few dependents
    for eid in doc.ids_of_class("FamilyInstance"):
        r = M.dependency_report(doc, eid)
        if 1 <= len(r["dependents"]) <= 6 and not r["truncated_at_depth"] \
                and not r["cascade_capped_at"]:
            break
    else:
        pytest.skip("no small-cascade element found in rstbasic")
    plan = M.delete_element(doc, eid, cascade=True)
    assert len(plan.ids_to_remove) == 1 + len(r["dependents"])
    out = str(tmp_path / "cascade.rvt")
    M.commit_plans(RST, out, [plan])
    v = M.verify_manipulated(out, deleted_ids=plan.ids_to_remove,
                             edited_ids=plan.edited_ids)
    _healthy(v, expect_edited=plan.edited_ids)
    d2 = Document.from_file(out)
    assert all(i not in d2.et_by_id for i in plan.ids_to_remove)


def test_move_and_retype_instance(tmp_path):
    from rvt import manipulate as M
    from rvt.mutate import Document
    doc = Document.from_file(RST)
    # a free instance whose family has a sibling symbol
    syms = doc.symbols()
    byfam = {}
    for s in syms:
        byfam.setdefault(s["family_id"], []).append(s["symbol_id"])
    fam_of = {s["symbol_id"]: s["family_id"] for s in syms}
    target = new_sym = None
    for eid in doc.ids_of_class("FamilyInstance"):
        v = doc.value(eid) or {}
        ii = ((v.get("m_pInstanceInfo") or {}).get("value") or {})
        sym = ii.get("m_symbolId")
        if sym is None or sym != v.get("m_masterSymbolId"):
            continue
        sib = [s for s in byfam.get(fam_of.get(sym), []) if s != sym]
        if not sib:
            continue
        o = doc.decode(eid, 102)
        if not (o and o.clean):
            continue
        target, new_sym = eid, sib[0]
        break
    if target is None:
        pytest.skip("no retypeable instance in rstbasic")
    before = M.instance_placement(doc, target)
    M.move_instance(doc, target, (5.0, 0.0, 0.0), delta=True)
    M.retype_instance(doc, target, new_sym)
    out = str(tmp_path / "movert.rvt")
    M.commit_session(doc, out)
    v = M.verify_manipulated(out, edited_ids=[target])
    _healthy(v, expect_edited=[target])
    after = M.instance_placement(Document.from_file(out), target)
    assert abs((after["m_or"][0] - before["m_or"][0]) - 5.0) < 1e-9
    assert abs(after["m_or"][1] - before["m_or"][1]) < 1e-9
    assert after["m_symbolId"] == new_sym == after["m_masterSymbolId"]
