"""tests/test_regadd.py -- THE FIXED NON-INSTANCE ADD PATH + THE IN-PLACE
SUBSTITUTE PATH (genesis-addfix stream, ``rvt.regadd``).

Tiers:
  1. the corpus REGISTRATION RULES (measured this session over all six
     samples + K1): the three universal document-birth singletons are
     creation-episode 0 / id < 5,000 in 7/7 files; the built-in GStyle
     catalog rows are unconstrained; ``vintage_for`` / ``check_registration``
     encode the two known add-path defects (owner INVALID where the corpus
     has an owner; a late episode where the corpus says birth).
  2. the record-POSITION policies (``choose_position``): the ID-HOLE insert
     that reproduces the corpus's consecutive-id birth run; the after-
     predecessor rule; the append fallback.
  3. K1 end-to-end (skipped without K1): the NULL substitution is
     ZERO-MOTION (every stream RAW-byte-identical to K1 -- the batch
     positive control); an in-place content substitution changes EXACTLY
     the target's records (ElemTable / Latest / block partition / id order
     asserted identical); the add-path NULL (delete + verbatim re-add at
     the same id, row preserved) is byte-identical to K1; the add path at
     a NEW low id honours the corpus rule (episode-0 row, id-hole position,
     schema-typed registry re-point) and is validator-VALID; the stream diff
     report names exactly what changed.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt import regadd as RA                                        # noqa: E402
from rvt.reduce import Rec                                           # noqa: E402

K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
needs_k1 = pytest.mark.skipif(not os.path.exists(K1),
                              reason="K1.rvt (viewer-PASSED base) not present")
PEN_ID = 2


# ===========================================================================
# tier 1 -- the corpus rules
# ===========================================================================

def test_birth_singletons_are_episode_zero_and_low_band():
    for cls in ("AllProjectPhases", "DBViewProject", "PenWidthTableElem"):
        rule = RA.reg_rule(cls)
        assert rule["creation_ep"] == "birth", cls
        assert rule["id_band"] == "<5k", cls
        assert rule["owner"] is None
        assert rule["support"], cls


def test_builtin_gstyle_rows_are_unconstrained():
    rule = RA.reg_rule("GStyleElem")
    assert rule["creation_ep"] == "any"
    assert rule["id_band"] is None
    assert rule["owner"] is None
    # the finding: every property the old add path wrote for a catalog row
    # is IN-CORPUS => a fresh late-episode high-id row violates nothing
    assert RA.check_registration("GStyleElem", elem_id=1_500_000, creation_ep=1016,
                                 owner_class=None) == []


def test_vintage_for_birth_class_is_zero_and_usermod_is_an_episode():
    ce, me, ue = RA.vintage_for("PenWidthTableElem", parent_max_ep=1016)
    assert ce == 0
    assert me == ce
    assert ue != RA.NO_EPISODE          # 'never' is NEVER seen on a project singleton (7/7)


def test_vintage_for_late_class_uses_parent_episode():
    ce, me, ue = RA.vintage_for("StructSettingsElem", parent_max_ep=1016)
    assert (ce, me, ue) == (1016, 1016, 1016)


def test_vintage_explicit_arguments_win():
    ce, me, ue = RA.vintage_for("PenWidthTableElem", parent_max_ep=99,
                                creation_ep=5, modified_ep=7, user_modified_ep=6)
    assert (ce, me, ue) == (5, 7, 6)


def test_check_registration_catches_the_two_known_defects():
    # X0's registration of the pen table: high id + late episode
    v = RA.check_registration("PenWidthTableElem", elem_id=1_500_000,
                              creation_ep=1016, owner_class=None)
    assert any("creation episode 0" in x for x in v)
    assert any("<5k" in x for x in v)
    # the corpus-conformant registration is clean
    assert RA.check_registration("PenWidthTableElem", elem_id=27, creation_ep=0,
                                 owner_class=None) == []


def test_check_registration_owner_rule():
    # a FontElem must be OWNED (5,982/5,982)
    v = RA.check_registration("FontElem", elem_id=123456, creation_ep=1000, owner_class=None)
    assert v and "OWNED" in v[0]
    assert RA.check_registration("FontElem", elem_id=123456, creation_ep=1000,
                                 owner_class="TextNoteAttributes") == []
    # a class the corpus says is un-owned must not get an owner
    v2 = RA.check_registration("PenWidthTableElem", elem_id=2, creation_ep=0,
                               owner_class="Family")
    assert v2 and "un-owned" in v2[0]


def test_scoped_pen_table_rule_differs_from_project():
    proj = RA.reg_rule("PenWidthTableElem", cohort="project")
    scoped = RA.reg_rule("PenWidthTableElem", cohort="scoped")
    assert proj["creation_ep"] == "birth" and proj["owner"] is None
    assert scoped["owner"] == "Family" and scoped["creation_ep"] == "any"


def test_id_band_buckets():
    assert RA.id_band(2) == "<5k"
    assert RA.id_band(4999) == "<5k"
    assert RA.id_band(5000) == "<50k"
    assert RA.id_band(1_472_524) == "<5M"
    assert RA.id_band(-2000014) == "<5M"                 # abs()
    assert RA.id_band(50_000_000) == ">=5M"


def test_unknown_class_has_no_rule():
    assert RA.reg_rule("SomeClassWeNeverMeasured") == {}
    assert RA.check_registration("SomeClassWeNeverMeasured", elem_id=99,
                                 creation_ep=5, owner_class=None) == []


# ===========================================================================
# tier 2 -- placement policies (synthetic runs, no file needed)
# ===========================================================================

def _rec(seq: int, eid: int) -> Rec:
    # a minimal well-formed framed record: id + [stamp] + psize(2) + class(2) + repeat
    import struct
    body = struct.pack("<H", 0x25)                     # bare class, empty object
    ps = len(body)
    if seq == 101:
        hdr = struct.pack("<qI", eid, ps)
    else:
        hdr = struct.pack("<qII", eid, 1, ps)
    return Rec(seq, eid, ps, hdr + body + struct.pack("<I", ps))


def _sentinel(seq: int) -> Rec:
    import struct
    if seq == 101:
        data = struct.pack("<qI", -1, 0) + struct.pack("<I", 0)
    else:
        data = struct.pack("<qII", -1, 1, 0) + struct.pack("<I", 0)
    return Rec(seq, -1, 0, data)


def _run(ids):
    return RA.SeqRun(102, [_rec(102, i) for i in ids] + [_sentinel(102)])


def test_position_id_hole_between_adjacent_neighbours():
    # the corpus birth run: ..., 1000, 1, 3, 4, 5 -- inserting 2 goes between 1 and 3
    run = _run([1000, 1, 3, 4, 5])
    idx, info = RA.choose_position(run, 2, "auto")
    assert idx == 2, info                                # after id 1 (pos 1), before 3 (pos 2)
    assert "ID-HOLE" in info["reason"]
    assert info["id_predecessor"]["id"] == 1 and info["id_successor"]["id"] == 3


def test_position_after_predecessor_in_ascending_stretch():
    # neighbours 40 and 60 are NOT adjacent (500 between), but 40 sits in an
    # ascending stretch (next is 500 > 40) -> insert after 40
    run = _run([10, 40, 500, 60, 70])
    idx, info = RA.choose_position(run, 50, "auto")
    assert idx == 2, info
    assert "AFTER-PREDECESSOR" in info["reason"]


def test_position_append_fallback():
    # 999 has no id below it in an ascending stretch and no bracketing
    # neighbours -> the predecessor 5 is followed by a lower id -> append
    run = _run([9, 5, 3, 1])
    idx, info = RA.choose_position(run, 999, "auto")
    assert idx == len(run.recs) - 1                    # before the sentinel
    assert "APPEND" in info["reason"]


def test_position_explicit_policies():
    run = _run([10, 20, 30])
    idx, _ = RA.choose_position(run, 25, "append")
    assert idx == len(run.recs) - 1
    idx, info = RA.choose_position(run, 25, "after:10")
    assert idx == 1 and info["anchor"] == 10
    idx, _ = RA.choose_position(run, 25, "index:0")
    assert idx == 0
    with pytest.raises(ValueError):
        RA.choose_position(run, 25, "nonsense")


def test_position_never_lands_after_the_sentinel():
    run = _run([10])
    idx, _ = RA.choose_position(run, 5, "index:999")
    assert idx <= len(run.recs) - 1


# ===========================================================================
# tier 3 -- K1 end-to-end
# ===========================================================================

@pytest.fixture(scope="module")
def out_dir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("regadd"))


@pytest.fixture(scope="module")
def k1_image():
    return RA.EditImage(K1)


@needs_k1
def test_edit_image_loads_k1(k1_image):
    img = k1_image
    assert img.pname.startswith("Partitions/")
    assert set(img.runs) == {101, 102, 103}
    # the three seqs carry the same id set, in the same order
    o101 = img.runs[101].ids
    assert o101 == img.runs[102].ids == img.runs[103].ids
    # every run ends with the sentinel
    for seq in (101, 102, 103):
        assert img.runs[seq].recs[-1].is_sentinel
    # the project pen table is element 2 and its row is birth-vintage
    assert img.class_of(PEN_ID) == "PenWidthTableElem"
    row = img.elemtable_row(PEN_ID)
    assert row["creation_ep"] == 0 and RA.id_band(PEN_ID) == "<5k"
    # the exact logical is shorter than / equal to the depaged one
    assert len(img.logical) <= 3_900_000


@needs_k1
def test_null_substitution_is_zero_motion(out_dir):
    """The batch positive control: every stream RAW-byte-identical to K1."""
    out = os.path.join(out_dir, "null.rvt")
    rep = RA.substitute_element(K1, out, PEN_ID, null=True, verify=False)
    assert rep.verdict == "VALID", rep.problems
    assert rep.identity_at_original["all_identical"] is True
    d = rep.diff
    assert d["streams"]["differing"] == []          # EVERY stream raw-identical
    assert d["partition_logical_identical"] is True
    assert d["records"]["added"] == [] and d["records"]["removed"] == []
    assert d["records"]["changed_count"] == 0
    assert d["elemtable"]["identical"] and d["latest"]["identical"]


@needs_k1
def test_inplace_substitution_changes_only_the_target(out_dir):
    """Our pen table at id 2: ONE record changes; everything else identical."""
    from rvt.genesis import settings as ST
    ours = ST.pen_width_table(elem_id=PEN_ID)
    out = os.path.join(out_dir, "xr0.rvt")
    rep = RA.substitute_element(K1, out, PEN_ID, ours, verify=False)
    assert rep.verdict == "VALID", rep.problems
    d = rep.diff
    assert d["records"]["changed_ids"] == [PEN_ID]
    assert d["records"]["added"] == [] and d["records"]["removed"] == []
    assert d["records"]["id_order_identical"] is True
    assert d["elemtable"]["identical"] is True
    assert d["latest"]["identical"] is True
    assert d["embedded_units_identical"] is True
    # our object encodes to the SAME length -> the block partition is preserved
    assert all(v["identical"] for v in d["blocks"].values()), d["blocks"]
    # only the partition stream differs
    assert d["streams"]["differing"] == ["Partitions/21"] or \
        (len(d["streams"]["differing"]) == 1
         and d["streams"]["differing"][0].startswith("Partitions/"))
    # and the only field differences are the pen doubles
    ch = [c for c in d["records"]["changed"] if c["id"] == PEN_ID]
    assert ch and ch[0]["len_ours"] == ch[0]["len_parent"]
    paths = [f["path"] for f in ch[0].get("field_diff", []) if "path" in f]
    assert paths and all("m_pens" in p for p in paths), paths


@needs_k1
def test_constructor_fed_exact_feet_reproduces_k1(out_dir):
    """XR0v: our pen constructor fed K1's EXACT feet == K1's own records."""
    from rvt.mutate import Document
    from rvt.genesis import settings as ST
    doc = Document.from_file(K1)
    spec = doc.value(PEN_ID)
    t = spec["m_pPenWidthTable"]["value"]
    model = {int(p["m_invertedScale"]): [float(x) for x in p["m_pens"]]
             for p in t["m_modelPenInfo"]}
    persp = [float(x) for x in t["m_perspectiveModelPenInfo"]["m_pens"]]
    draft = [float(x) for x in t["m_draftPenInfo"]["m_pens"]]
    ours = ST.pen_width_table(elem_id=PEN_ID, model_pens_ft=model,
                              perspective_pens_ft=persp, annotation_pens_ft=draft)
    img = RA.EditImage(K1)
    old = img.records_of(PEN_ID)
    enc = ours.encode()
    for seq in (101, 102, 103):
        assert enc[seq] == old[seq].data, f"seq {seq} not byte-identical"


@needs_k1
def test_add_path_null_same_id_reinsert_is_identical_to_k1(out_dir):
    """XA0: delete id 2 + re-add Autodesk's exact records at id 2 (row
    preserved, in-place position, Latest untouched) == K1 byte-for-byte."""
    img = RA.EditImage(K1)
    old = img.records_of(PEN_ID)
    verbatim = {s: r.data for s, r in old.items()}
    out = os.path.join(out_dir, "xa0.rvt")
    rep = RA.add_element_like_original(K1, out, verbatim, class_name="PenWidthTableElem",
                                       new_id=PEN_ID, replace_old_id=PEN_ID,
                                       place="auto", preserve_row_of=PEN_ID, verify=False)
    assert rep.verdict == "VALID", rep.problems
    assert rep.rule_violations == []
    assert rep.registry.get("latest_touched") is False
    d = rep.diff
    assert d["streams"]["differing"] == [], d["streams"]["differing"]
    assert d["elemtable"]["identical"] and d["latest"]["identical"]
    assert d["partition_logical_identical"] is True
    # placement chose the same-id in-place policy
    assert rep.placement["per_seq"][102]["policy"] == "same-id-in-place"


@needs_k1
def test_add_path_new_low_id_registration_conforms(out_dir):
    """XA2-style: Autodesk's exact pen table added at a NEW low id with the
    corpus row copied, the id-hole position, and a typed registry re-point."""
    import copy as _copy
    import struct as _st
    from rvt.encode import encode_record
    img = RA.EditImage(K1)
    old = img.records_of(PEN_ID)
    # a free low id (27 in K1)
    present = set(img.runs[102].ids)
    new_id = next(i for i in range(7, 5000) if i not in present)
    obj = _copy.deepcopy(img.decode(old[102]).value)
    hdr = _copy.deepcopy(img.decode(old[101]).value)
    obj["m_id"] = new_id
    dele = [new_id if int(x) == PEN_ID else int(x)
            for x in (hdr["m_parents"]["value"].get("m_deletion") or [])]
    hdr["m_parents"]["value"]["m_deletion"] = dele
    cls102 = _st.unpack_from("<H", old[102].data, 16)[0]
    cls101 = _st.unpack_from("<H", old[101].data, 12)[0]
    cls103 = _st.unpack_from("<H", old[103].data, 16)[0]
    framed = {101: encode_record(101, new_id, None, cls101, hdr),
              102: encode_record(102, new_id, None, cls102, obj),
              103: encode_record(103, new_id, None, cls103, {})}
    out = os.path.join(out_dir, "xa2.rvt")
    rep = RA.add_element_like_original(K1, out, framed, class_name="PenWidthTableElem",
                                       new_id=new_id, replace_old_id=PEN_ID, place="auto",
                                       preserve_row_of=PEN_ID,
                                       latest_remap={PEN_ID: new_id}, verify=True)
    assert rep.verdict == "VALID", rep.problems
    assert rep.rule_violations == [], rep.rule_violations
    # the corpus row: creation episode 0 (7/7), low band
    row = rep.elemtable_row
    assert row["creation_ep"] == 0 and RA.id_band(new_id) == "<5k"
    assert row["elem_id"] == new_id
    # the typed registry re-point touched exactly the PenWidthTableInfo leaf
    reg = rep.registry
    assert reg["latest_touched"] is True and reg["remap_edits"] == 1
    assert "PenWidthTableInfo" in reg["remap_examples"][0]["path"]
    assert reg["remap_examples"][0]["old"] == PEN_ID
    assert reg["remap_examples"][0]["new"] == new_id
    # the ADocument codec round-tripped; validator clean
    assert rep.validator["ok"] and rep.validator["errors"] == 0
    # placement went into an id-hole (K1's low ids 26 / 29 bracket 27)
    p102 = rep.placement["per_seq"][102]
    assert p102["policy"] == "auto"
    assert "ID-HOLE" in p102["reason"] or "AFTER-PREDECESSOR" in p102["reason"], p102
    # diff: exactly one added + one removed id
    d = rep.diff
    assert d["records"]["added_ids"] == [new_id]
    assert d["records"]["removed_ids"] == [PEN_ID]
    assert d["records"]["changed_ids"] == []
    assert d["records"]["common_order_preserved"] == {101: True, 102: True, 103: True} \
        or all(d["records"]["common_order_preserved"].values())
    assert d["embedded_units_identical"] is True


@needs_k1
def test_strict_rules_refuse_a_violating_registration(out_dir):
    """strict_rules=True refuses X0's registration (high id + late episode)."""
    import struct as _st
    from rvt.encode import encode_record
    img = RA.EditImage(K1)
    old = img.records_of(PEN_ID)
    high = img.watermark + 1000
    obj = img.decode(old[102]).value
    obj["m_id"] = high
    hdr = img.decode(old[101]).value
    hdr["m_parents"]["value"]["m_deletion"] = [high]
    framed = {101: encode_record(101, high, None, _st.unpack_from("<H", old[101].data, 12)[0], hdr),
              102: encode_record(102, high, None, _st.unpack_from("<H", old[102].data, 16)[0], obj),
              103: encode_record(103, high, None, _st.unpack_from("<H", old[103].data, 16)[0], {})}
    with pytest.raises(ValueError, match="corpus rule"):
        RA.add_element_like_original(K1, os.path.join(out_dir, "bad.rvt"), framed,
                                     class_name="PenWidthTableElem", new_id=high,
                                     replace_old_id=PEN_ID, place="append",
                                     creation_ep=1016, strict_rules=True,
                                     verify=False, diff=False)


@needs_k1
def test_stream_diff_report_structure(out_dir):
    """The diff report the assertions rest on: identical files -> nothing differs."""
    d = RA.stream_diff_report(K1, K1)
    assert d["streams"]["differing"] == []
    assert d["partition_logical_identical"] is True
    assert d["records"]["changed_count"] == 0
    assert d["records"]["id_order_identical"] is True
    assert d["elemtable"]["identical"] is True
    assert d["latest"]["identical"] is True
    assert d["embedded_units_identical"] is True


@needs_k1
def test_batch_substitution_null(out_dir):
    """substitute_elements over several ids in one image (the XR3 primitive)
    in NULL mode is still zero-motion."""
    ids = {PEN_ID: None, 1: None, 3: None}
    out = os.path.join(out_dir, "batch_null.rvt")
    rep = RA.substitute_elements(K1, out, ids, null=True, verify=False)
    assert rep.verdict == "VALID", rep.problems
    assert rep.diff["streams"]["differing"] == []
    assert rep.identity_at_original["all_identical"] is True
