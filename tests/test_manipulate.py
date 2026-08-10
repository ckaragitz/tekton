"""manipulation layer: edit / move / retype / delete EXISTING elements.

Unit tests cover the pure helpers; the end-to-end tests run the four
operations against ``samples/rstbasicsampleproject.rvt`` (the smallest
sample) through the real writer and prove each output with
``verify_manipulated`` + a semantic re-read.  The set_param UPSERT tests
(#186) run on a prompt-built room over the pinned plugin base, so they
need no samples/.
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


# ---------------------------------------------------------------------------
# set_param UPSERT on OUR OWN front-door output (issue #186) -- runs on the
# pinned composed base shipped in plugin/assets/genesis (no samples/ needed)
# ---------------------------------------------------------------------------
PINNED_2026 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")


def _rows(doc, eid, holder="m_pParamValueSetAString"):
    from rvt.manipulate import _param_rows
    return _param_rows(doc.value(eid) or {}, holder)


@pytest.fixture(scope="module")
def prompt_room(tmp_path_factory):
    """A prompt-built room: its placed panel carries all four param holders
    NULL -- the shape that made rename / set-mark raise before #186."""
    if not os.path.isfile(PINNED_2026):
        pytest.skip("bundled genesis base missing")
    import rvt.frontdoor as FD
    from rvt.manipulate import PARAM_HOLDERS
    from rvt.mutate import Document
    out = str(tmp_path_factory.mktemp("p186") / "job")
    r = FD.author(prompt="an electrical room with a 400A distribution panel",
                  out=out, no_handoff=True)
    assert r.ok, (r.status, r.errors)
    path = r.manifest["build"]["files"]["combined"]["path"]
    doc = Document.from_file(path)
    (panel,) = doc.ids_of_class("FamilyInstance")
    assert all(doc.value(panel).get(h) is None for h in PARAM_HOLDERS)
    return {"path": path, "panel": panel}


@pytest.fixture(scope="module")
def renamed_room(prompt_room, tmp_path_factory):
    """prompt_room after rename + set-mark in ONE session: the AString holder
    is authored by the first insert, the second row appended to it."""
    from rvt import manipulate as M
    from rvt.mutate import Document
    doc = Document.from_file(prompt_room["path"])
    eid = prompt_room["panel"]
    plans = [M.rename_panel(doc, eid, "DPX"), M.set_mark(doc, eid, "M-7")]
    out = str(tmp_path_factory.mktemp("p186r") / "renamed.rvt")
    M.commit_session(doc, out)
    return {"path": out, "panel": eid, "plans": plans}


def test_set_param_inserts_absent_astring_rows_authoring_the_holder(renamed_room):
    from rvt import inventory as INV
    from rvt import manipulate as M
    from rvt.mutate import Document
    out, eid = renamed_room["path"], renamed_room["panel"]
    p1, p2 = renamed_room["plans"]
    assert p1.changes[0].path == "m_pParamValueSetAString" and p1.changes[0].before is None
    assert p1.changes[0].after["ptr_class"] == "ParamValueSetAString"
    assert len(p1.changes[0].after["value"]["m_paramSet"]) == 1     # no aliasing of p2's row
    assert any("authored ParamValueSetAString holder" in n for n in p1.notes)
    assert p2.changes[0].path == "m_pParamValueSetAString.value.m_paramSet"
    assert any("into existing" in n for n in p2.notes)
    _healthy(M.verify_manipulated(out, edited_ids=[eid]), expect_edited=[eid])
    d2 = Document.from_file(out)
    assert _rows(d2, eid) == [{"m_paramId": M.BIP_RBS_ELEC_PANEL_NAME, "m_value": "DPX"},
                              {"m_paramId": M.BIP_ALL_MODEL_MARK, "m_value": "M-7"}]
    assert INV.element_name(d2, eid) == "DPX"
    o = d2.decode(eid, 102)
    assert o.clean and o.consumed == o.total


def test_set_param_inserts_absent_double_and_elementid_rows(prompt_room, tmp_path):
    from rvt import manipulate as M
    from rvt.mutate import Document
    src, eid = prompt_room["path"], prompt_room["panel"]
    doc = Document.from_file(src)
    dbl, eidp = -1001200, -1002050                   # any absent built-ins
    plan = M.set_param(doc, eid, dbl, 2.5)
    assert plan.changes[0].path == "m_pParamValueSetDouble" and plan.changes[0].before is None
    M.set_param(doc, eid, eidp, -1, holder="m_pParamValueSetElementId")
    out = str(tmp_path / "dbl.rvt")
    M.commit_session(doc, out)
    _healthy(M.verify_manipulated(out, edited_ids=[eid]), expect_edited=[eid])
    d2 = Document.from_file(out)
    h = d2.value(eid)["m_pParamValueSetDouble"]
    assert h["ptr_class"] == "ParamValueSetDouble" and h["pid"] == -1
    assert h["value"]["m_paramSet"] == [{"m_paramId": dbl, "m_value": 2.5}]
    assert _rows(d2, eid, "m_pParamValueSetElementId") == [{"m_paramId": eidp, "m_value": -1}]
    assert _rows(d2, eid, "m_pParamValueSetInt") is None           # untouched holders stay null


def test_set_param_modifies_present_row_without_duplicating(renamed_room, tmp_path):
    """A file whose rows already exist behaves exactly as before: the row is
    changed in place, never appended a second time."""
    from rvt import manipulate as M
    from rvt.mutate import Document
    eid = renamed_room["panel"]
    doc = Document.from_file(renamed_room["path"])
    p = M.rename_panel(doc, eid, "DPY")
    assert p.changes[0].path.endswith("].m_value") and p.changes[0].before == "DPX"
    assert not p.notes                               # plain modify, nothing authored
    M.set_mark(doc, eid, 8)                          # a known text built-in stays text
    twice = str(tmp_path / "twice.rvt")
    M.commit_session(doc, twice)
    _healthy(M.verify_manipulated(twice, edited_ids=[eid]), expect_edited=[eid])
    assert _rows(Document.from_file(twice), eid) == [
        {"m_paramId": M.BIP_RBS_ELEC_PANEL_NAME, "m_value": "DPY"},
        {"m_paramId": M.BIP_ALL_MODEL_MARK, "m_value": "8"}]


def test_param_holder_for():
    from rvt import manipulate as M
    assert M.param_holder_for(M.BIP_ALL_MODEL_MARK, 7) == "m_pParamValueSetAString"
    assert M.param_holder_for(M.BIP_ROOM_NUMBER, 101) == "m_pParamValueSetAString"
    assert M.param_holder_for(-1001200, "x") == "m_pParamValueSetAString"
    assert M.param_holder_for(-1001200, 2.5) == "m_pParamValueSetDouble"
    assert M.param_holder_for(-1001200, True) == "m_pParamValueSetInt"
    assert M.param_holder_for(-1001200, 3) == "m_pParamValueSetInt"
    with pytest.raises(M.ManipulationError):
        M.param_row_edit({"m_pParamValueSetInt": None}, -1001200, 3, holder="m_pBogus")
    with pytest.raises(M.ManipulationError):        # not an Element object
        M.param_row_edit({"m_name": "x"}, M.BIP_ALL_MODEL_MARK, "M")


# ---------------------------------------------------------------------------
# #289: the raw-dict upsert every create-time helper delegates to, and the
# `holder` key of the ops.json set-param op
# ---------------------------------------------------------------------------
def test_upsert_param_row_pure():
    from rvt import manipulate as M
    obj = {"m_pParamValueSetAString": None, "m_pParamValueSetDouble": None,
           "m_pParamValueSetInt": None, "m_pParamValueSetElementId": None}
    note = M.upsert_param_row(obj, M.BIP_ALL_MODEL_MARK, "M-1")
    assert "authored ParamValueSetAString holder" in note
    assert obj["m_pParamValueSetAString"] == {
        "ptr_class": "ParamValueSetAString", "pid": -1,
        "value": {"m_paramSet": [{"m_paramId": M.BIP_ALL_MODEL_MARK, "m_value": "M-1"}]}}
    assert "into existing" in M.upsert_param_row(obj, M.BIP_ROOM_NAME, "Elec")
    assert M.upsert_param_row(obj, M.BIP_ALL_MODEL_MARK, 7).startswith("set parameter")
    rows = obj["m_pParamValueSetAString"]["value"]["m_paramSet"]
    assert rows == [{"m_paramId": M.BIP_ALL_MODEL_MARK, "m_value": "7"},      # in place, coerced
                    {"m_paramId": M.BIP_ROOM_NAME, "m_value": "Elec"}]        # never duplicated
    M.upsert_param_row(obj, -1002050, -1, holder="m_pParamValueSetElementId")
    assert obj["m_pParamValueSetElementId"]["ptr_class"] == "ParamValueSetElementId"
    assert obj["m_pParamValueSetElementId"]["value"]["m_paramSet"] == [
        {"m_paramId": -1002050, "m_value": -1}]
    assert obj["m_pParamValueSetInt"] is None and obj["m_pParamValueSetDouble"] is None
    with pytest.raises(M.ManipulationError):         # not an Element object: loud, not silent
        M.upsert_param_row({"m_name": "x"}, M.BIP_ALL_MODEL_MARK, "M")


@pytest.mark.parametrize("helper", ["conduit._set_astring_param",
                                    "electrical_data._set_astring_param",
                                    "views_spaces._set_astring_param",
                                    "devices._set_param_astring"])
def test_mep_astring_helpers_author_a_null_holder(helper):
    """conduit._set_astring_param used to return silently on a null
    m_pParamValueSetAString (a Mark on a created run was dropped); all four
    mep helpers now author the holder through manipulate.param_row_edit."""
    import importlib
    from rvt import manipulate as M
    mod, fn = helper.split(".")
    setter = getattr(importlib.import_module(f"rvt.mep.{mod}"), fn)
    obj = {"m_pParamValueSetAString": None}
    setter(obj, M.BIP_ALL_MODEL_MARK, "C-1")
    assert obj["m_pParamValueSetAString"] == {
        "ptr_class": "ParamValueSetAString", "pid": -1,
        "value": {"m_paramSet": [{"m_paramId": M.BIP_ALL_MODEL_MARK, "m_value": "C-1"}]}}
    setter(obj, M.BIP_ALL_MODEL_MARK, "C-2")             # present -> modified in place
    assert M._param_rows(obj, "m_pParamValueSetAString") == [
        {"m_paramId": M.BIP_ALL_MODEL_MARK, "m_value": "C-2"}]


def test_mutate_set_param_authors_a_null_double_holder():
    from rvt.mutate import BIP_WALL_HEIGHT, Document
    obj = {"m_pParamValueSetDouble": None}
    Document._set_param(obj, "m_pParamValueSetDouble", BIP_WALL_HEIGHT, 10)
    assert obj["m_pParamValueSetDouble"]["ptr_class"] == "ParamValueSetDouble"
    assert obj["m_pParamValueSetDouble"]["value"]["m_paramSet"] == [
        {"m_paramId": BIP_WALL_HEIGHT, "m_value": 10.0}]


def test_job_set_param_op_lands_an_elementid_row_via_holder(prompt_room, tmp_path, job):
    """`{"op":"set-param",...,"holder":"m_pParamValueSetElementId"}` through
    tools/rvt_job.py edit (the ops.json door the front door and the skills
    use; ``job`` = the conftest fixture) inserts an ElementId row -- a bare -1
    would otherwise type as Int."""
    import json
    from rvt import manipulate as M
    from rvt.mutate import Document
    src, eid = prompt_room["path"], prompt_room["panel"]
    ops = [{"op": "set-param", "id": eid, "param_id": -1002050, "value": -1,
            "holder": "m_pParamValueSetElementId"},
           {"op": "set-param", "id": eid, "param_id": -1001200, "value": 3}]   # no holder -> Int
    ops_p = tmp_path / "ops.json"
    ops_p.write_text(json.dumps({"ops": ops}))
    out = tmp_path / "eid.rvt"
    rc = job.main(["edit", src, "--ops", str(ops_p), "-o", str(out)])
    assert rc == 0
    man = json.loads((tmp_path / "eid.rvt.manifest.json").read_text())
    assert man["hard_gates_passed"] and man["gates"]["validation"]["status"].startswith("PASS")
    assert any("(m_pParamValueSetElementId)" in line for line in man["edit"]["log"])
    _healthy(M.verify_manipulated(str(out), edited_ids=[eid]), expect_edited=[eid])
    d2 = Document.from_file(str(out))
    assert _rows(d2, eid, "m_pParamValueSetElementId") == [{"m_paramId": -1002050, "m_value": -1}]
    assert _rows(d2, eid, "m_pParamValueSetInt") == [{"m_paramId": -1001200, "m_value": 3}]
    assert _rows(d2, eid, "m_pParamValueSetAString") is None      # untouched holders stay null
