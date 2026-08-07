"""Tests for rvt.regdiff -- the registration diff.

Pinned facts (docs/writer/registration-diff.md), all measured against the
files the reader has actually judged: K1 (Autodesk's registration of the pen
table, viewer PASS), X0 (the same pen table re-registered through OUR add
path, viewer FAIL), V20 (the proven family-INSTANCE add path, viewer PASS).
"""
from __future__ import annotations

import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import adocument as adoc                                   # noqa: E402
from rvt import regdiff as RD                                       # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402

K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
X0 = os.path.join(ROOT, "experiments", "genesis", "controls", "X0.rvt")
X0K = os.path.join(ROOT, "experiments", "genesis", "controls", "X0k.rvt")
C0 = os.path.join(ROOT, "experiments", "genesis", "controls", "C0.rvt")
V20 = os.path.join(ROOT, "experiments", "acceptance", "V20_first_created_element.rvt")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(K1) and os.path.exists(X0) and os.path.exists(V20)),
    reason="regdiff fixtures (K1 / X0 / V20) not present")


@pytest.fixture(scope="module")
def k1():
    return RD.RegDoc(K1)


@pytest.fixture(scope="module")
def x0():
    return RD.RegDoc(X0)


@pytest.fixture(scope="module")
def v20():
    return RD.RegDoc(V20)


# ---------------------------------------------------------------------------
# registration_of on Autodesk's own registration (K1 id 2, viewer PASS)
# ---------------------------------------------------------------------------

def test_k1_pen_table_registration(k1):
    r = RD.registration_of(k1, 2)
    assert r.class_name == "PenWidthTableElem"
    row = r.row
    # Autodesk's ElemTable row for the project pen table: birth-vintage
    assert (row["elem_id"], row["original_id"]) == (2, 2)
    assert (row["creation_ep"], row["modified_ep"], row["user_modified_ep"]) == (0, 976, 976)
    assert row["created_at_birth"] is True
    assert row["id_band"] == "<5k"
    assert row["owner_id"] is None and row["partition_id"] == 0
    assert row["renumbered"] is False
    # header: empty regen-history map (no episode mirror in the header),
    # self-only deletion list
    assert r.header["regen_history_map_len"] == 0
    assert r.header["deletion"] == [2]
    assert r.header["appearance_parents"] == [] and r.header["regen_only"] == []
    # the registry surface: exactly ONE typed leaf, the PenWidthTableInfo slot
    assert len(r.registry) == 1
    assert r.registry[0].endswith("PenWidthTableInfo.m_penWidthTableElemId")
    # nothing owns rows on behalf of the pen table
    assert r.owned_rows == []


def test_k1_pen_table_position_in_its_own_episode_run(k1):
    r = RD.registration_of(k1, 2)
    p = r.positions[102]
    assert p["index"] == 2516 and p["total"] == 6540
    assert p["is_last_record"] is False
    assert (p["prev_id"], p["next_id"]) == (1, 3)          # inside the birth id run
    # the run law: an element's records sit in the run of ITS OWN modified_ep
    assert p["run_modal_modified_ep"] == 976 == r.row["modified_ep"]


def test_k1_seq_orders_identical(k1):
    orders = {s: [int(x.elem_id) for x in k1.host_records(s)] for s in (101, 102, 103)}
    assert orders[101] == orders[102] == orders[103]


# ---------------------------------------------------------------------------
# the unit-0 record-order LAW: id-ascending runs grouped by modified episode,
# newest-modified run FIRST
# ---------------------------------------------------------------------------

def test_unit0_runs_are_grouped_by_modified_episode_descending(k1):
    rep = RD.run_law_report(k1)
    assert rep["runs"] > 20
    assert rep["runs_modal_episode_descending"] is True
    assert rep["first_run_modal_episode"] > rep["last_run_modal_episode"]
    assert rep["adjacent_id_ascending_fraction"] > 0.98


# ---------------------------------------------------------------------------
# X0: the same element through OUR add path (viewer FAIL) -- the diff
# ---------------------------------------------------------------------------

def test_x0_registration_and_diff_against_k1(k1, x0):
    a = RD.registration_of(k1, 2)
    b = RD.registration_of(x0, 1_500_000)
    assert b.class_name == "PenWidthTableElem"
    # our add path writes a FRESH-episode row at the new id, in a high band
    assert (b.row["creation_ep"], b.row["modified_ep"], b.row["user_modified_ep"]) == (1016, 1016, 1016)
    assert b.row["created_at_birth"] is False and b.row["id_band"] == "<5M"
    assert b.row["original_id"] == 1_500_000              # our path: original_id = new id
    # the records went to the END of unit 0 (last record) -- into the OLDEST run
    p = b.positions[102]
    assert p["is_last_record"] is True and p["index"] == p["total"] - 1
    assert p["run_modal_modified_ep"] == 277
    # the registry surface: same single leaf, now naming the new id
    assert len(b.registry) == 1 and b.registry[0].endswith("PenWidthTableInfo.m_penWidthTableElemId")
    # the diff names exactly the registration deltas (header identical, ids ignored)
    dims = {d["dimension"] for d in RD.diff_registrations(a, b)}
    assert {"ETR.creation_ep", "ETR.created_at_birth", "ETR.id_band",
            "POS.seq102.is_last_record", "POS.seq102.run_modal_modified_ep"} <= dims
    assert not any(d.startswith("HDR.abFlags") for d in dims)      # header preserved


def test_x0_verbatim_records_and_single_leaf_latest_change(k1, x0):
    """Content is held at Autodesk's bytes: the seq-101 header differs only in
    the self-entry of m_deletion + the record id; Global/Latest differs in
    exactly the 3 bytes of the single re-pointed i64 leaf."""
    hk = k1.decode_record(101, 2).value
    hx = x0.decode_record(101, 1_500_000).value
    hk2 = dict(hk)
    hx2 = dict(hx)
    hk2.pop("m_parents"); hx2.pop("m_parents")
    assert hk2 == hx2
    assert hx["m_parents"]["value"]["m_deletion"] == [1_500_000]
    ok = x0.decode_record(102, 1_500_000).value
    assert ok["m_id"] == 1_500_000
    # Global/Latest: exactly 3 differing payload bytes (2 -> 1,500,000)
    pk, px = k1.latest_payload, x0.latest_payload
    assert len(pk) == len(px)
    diffs = [i for i in range(len(pk)) if pk[i] != px[i]]
    assert len(diffs) == 3
    off = diffs[0]
    assert px[off:off + 8] == struct.pack("<q", 1_500_000)
    assert pk[off:off + 8] == struct.pack("<q", 2)


def test_adocument_codec_byte_exact_on_k1(k1):
    a = adoc.decode_latest(k1.latest_payload)
    assert a.clean
    assert adoc.encode_latest(a.value) == k1.latest_payload


def test_typed_surface_of_id_2_is_a_single_leaf(k1):
    surf = k1.adoc_surface([2])
    assert surf[2] == [
        "ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[38]->"
        "PenWidthTableInfo.m_penWidthTableElemId"]


# ---------------------------------------------------------------------------
# the calibration control: V20's PROVEN created FamilyInstance shares X0's
# record position (last) and fresh (ep,ep,ep) row -- so those are NOT the fault
# ---------------------------------------------------------------------------

def test_v20_proven_instance_shares_x0_position_and_episode_shape(v20, x0):
    v = RD.registration_of(v20, 1_472_525)
    x = RD.registration_of(x0, 1_500_000)
    assert v.class_name == "FamilyInstance"
    # both sit LAST, both inside the OLDEST-episode run, both (max_ep x3) rows
    assert v.positions[102]["is_last_record"] is True and x.positions[102]["is_last_record"] is True
    assert v.positions[102]["run_modal_modified_ep"] == x.positions[102]["run_modal_modified_ep"] == 277
    assert (v.row["creation_ep"], v.row["modified_ep"], v.row["user_modified_ep"]) == (1016, 1016, 1016)
    assert v.row["episodes_all_equal"] is True and x.row["episodes_all_equal"] is True
    # what V20 does NOT share with X0: no registry surface, no birth-vintage claim
    assert v.registry == []
    assert v.row["created_at_birth"] is False


def test_deletion_collateral_zero_referrers_for_the_pen_table(k1):
    """The deletion half of X0: element 2 has no typed inbound referrers and
    owns no ElemTable rows (independently re-derived, host + embedded units)."""
    refs = RD.inbound_referrers(k1, {2}, include_embedded=True)
    assert refs[2] == set()
    assert [int(r[4]) for r in k1.elemtable["records"] if int(r[5]) == 2] == []


@pytest.mark.skipif(not os.path.exists(X0K), reason="X0k not present")
def test_x0k_holds_latest_and_moves_only_position_and_row(k1):
    """X0k (same-id re-insert): Global/Latest byte-identical to K1's, records
    byte-identical but moved LAST, ElemTable row rewritten (ep,ep,ep)."""
    xk = RD.RegDoc(X0K)
    assert xk.latest_payload == k1.latest_payload
    r = RD.registration_of(xk, 2)
    assert (r.row["creation_ep"], r.row["modified_ep"], r.row["user_modified_ep"]) == (1016, 1016, 1016)
    assert r.positions[102]["is_last_record"] is True
    for s in (101, 102, 103):
        assert k1.record(s, 2).payload == xk.record(s, 2).payload
        assert k1.record(s, 2).stamp == xk.record(s, 2).stamp


@pytest.mark.skipif(not os.path.exists(C0), reason="C0 not present")
def test_c0_catalog_row_single_leaf_repoint():
    c0 = RD.RegDoc(C0)
    r = RD.registration_of(c0, 1_500_000)
    assert r.class_name == "GStyleElem"
    assert len(r.registry) == 1
    assert "CategoryTracking.m_gstyleData[" in r.registry[0]
    assert r.registry[0].endswith(".m_gstyleId")
    assert r.positions[102]["is_last_record"] is True
    with open_rvt(K1) as f:
        pk = f.inflate(adoc.STREAM, 0)
    diffs = [i for i in range(len(pk)) if pk[i] != c0.latest_payload[i]]
    assert len(diffs) == 3                                   # only the leaf value 34 -> 1.5M
