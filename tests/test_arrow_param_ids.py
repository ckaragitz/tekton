"""Pin the LeaderStyle arrow parameter id -> meaning mapping to the corpus (#343).

``residue_a.BIP_ARROW_ANGLE`` / ``BIP_ARROW_SIZE`` name Revit's arrowhead angle
(radians) and size (feet) parameters.  The names were swapped once; these tests
tie them to the tracked, Revit-born evidence so it cannot silently happen again:
the 1024-arrowhead invariant (``invariants/LeaderStyle.json``), the certified
parent's arrowhead 285 in ``Z_annot.json`` and the birth template's seven
arrowheads (``experiments/birthright/template_birth.json``) -- all tracked, so
this runs in a fresh clone.  They also pin the deliberate, documented crossing
``arrowhead_type`` still writes (our angle under the SIZE id, our size under the
ANGLE id, in that order) so that un-crossing it (#362) is a visible, reviewed
value change with its own viewer round rather than a side effect of a refactor.
"""
from __future__ import annotations

import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools", "dev"))

import arrow_param_ids as API                                   # noqa: E402
from rvt.genesis import residue_a as RA                          # noqa: E402
from rvt.genesis.types import mm                                 # noqa: E402

RADIANS = (0.1, math.pi / 2 + 1e-9)          # every corpus arrow angle: 15..90 deg
FEET = (0.0, 0.1)                            # every corpus arrow size: 1/64"..1/4" (< 30 mm)


def _in(rng, v):
    return rng[0] <= v <= rng[1]


def test_constants_name_the_corpus_ids():
    assert RA.BIP_ARROW_ANGLE == -1006426
    assert RA.BIP_ARROW_SIZE == -1006414
    assert RA.BIP_ARROW_WIDTH_PEN == -1006447
    assert {RA.BIP_ARROW_ANGLE, RA.BIP_ARROW_SIZE} == set(API.IDS)


def test_invariant_says_two_ids_two_disjoint_magnitude_clusters():
    inv = API.invariant_reading()
    assert inv["n_specimens"] == 1024 and inv["files"] == 6
    assert inv["set_len"] == {"2": 1024}                                   # exactly 2 doubles each
    assert inv["id_counts"] == {RA.BIP_ARROW_ANGLE: 1024, RA.BIP_ARROW_SIZE: 1024}
    assert inv["value_range"][0] >= 0.0 and inv["value_range"][1] <= RADIANS[1]
    rad, ft = inv["clusters"]["radians"], inv["clusters"]["feet"]
    assert all(_in(RADIANS, v) for v, _ in rad["values"]) and rad["n"] > 900
    assert all(_in(FEET, v) for v, _ in ft["values"]) and ft["n"] > 900
    assert rad["n"] + ft["n"] == inv["histogram_covered"] <= inv["histogram_total"] == 2048
    # paramSet[0] of the first Revit-born arrowhead scanned: the ANGLE id with a 30 deg value
    assert inv["id_first_seen"] == RA.BIP_ARROW_ANGLE
    assert inv["value_first_seen"] == pytest.approx(math.radians(30.0))


def test_certified_parent_arrowhead_285_pairs_angle_id_with_radians():
    z = API.z_annot_reading()
    parent = dict(z["parent"])
    assert set(parent) == {RA.BIP_ARROW_ANGLE, RA.BIP_ARROW_SIZE}
    assert parent[RA.BIP_ARROW_ANGLE] == pytest.approx(math.radians(30.0))
    assert parent[RA.BIP_ARROW_SIZE] == pytest.approx(1.0 / 64 / 12)      # 1/64 inch in feet
    assert list(parent) == [RA.BIP_ARROW_ANGLE, RA.BIP_ARROW_SIZE]           # Revit's order


def test_birth_template_arrowheads_pair_ids_with_the_right_value_ranges():
    rows = API.birth_reading()
    assert len(rows) >= 7
    for r in rows:
        p = dict(r["pairs"])
        assert _in(FEET, p[RA.BIP_ARROW_SIZE]) and p[RA.BIP_ARROW_SIZE] > 0.0, r
        # the one non-radians angle is the 0.0 of the filled DOT (tick type 11), which has no angle
        assert _in(RADIANS, p[RA.BIP_ARROW_ANGLE]) or (p[RA.BIP_ARROW_ANGLE] == 0.0
                                                     and r["tick_type"] == API.DOT_TICK_TYPE), r
        assert list(p) == [RA.BIP_ARROW_ANGLE, RA.BIP_ARROW_SIZE]                # Revit's order
    named = [r for r in rows if r["name"] == 'Diagonal 1/8"']
    assert named and dict(named[0]["pairs"])[RA.BIP_ARROW_SIZE] == pytest.approx(1.0 / 8 / 12)


def test_per_id_verdict_over_all_revit_born_pairs():
    t = API.per_id_table(API.z_annot_reading(), API.birth_reading())
    assert t[RA.BIP_ARROW_SIZE]["feet"] and not t[RA.BIP_ARROW_SIZE]["radians"]
    assert t[RA.BIP_ARROW_ANGLE]["radians"] and set(t[RA.BIP_ARROW_ANGLE]["feet"]) <= {0.0}


def test_arrowhead_type_keeps_the_certified_crossing_byte_for_byte():
    """The rename moved no byte: our angle still lands under the SIZE id and our
    size under the ANGLE id, SIZE id first -- exactly what G_ABPD/_2025/_2024 carry."""
    ah = RA.arrowhead_type(RA.gen("Arrow Filled 20 Degree"), category_id=99, elem_id=5)
    ps = ah.value["m_pParamValueSetDouble"]["value"]["m_paramSet"]
    assert [p["m_paramId"] for p in ps] == [RA.BIP_ARROW_SIZE, RA.BIP_ARROW_ANGLE]
    assert ps[0]["m_value"] == pytest.approx(math.radians(20.0))
    assert ps[1]["m_value"] == pytest.approx(mm(3.0))
    assert list(ps[0]) == ["m_value", "m_paramId"]                         # Double sets: value first
    assert RA.check_object("LeaderStyle", ah.value)["ok"]


def test_fingerprint_covers_every_writer_path_and_all_carry_the_crossing():
    """The byte-identity instrument itself: 15 cases (3 direct + 6 slots x with/without
    the int set), every one SIZE-id-first carrying a radians value.  (The main-vs-branch
    sha256 diff that proved the rename lives in docs/inbox/arrow-param-ids.md, not here:
    a whole-record digest would go red on any unrelated encoder change.)"""
    fp = API.fingerprint()
    assert len(fp) == 15
    for key, case in fp.items():
        assert [pid for pid, _ in case["double_pairs"]] == [RA.BIP_ARROW_SIZE, RA.BIP_ARROW_ANGLE], key
        assert _in(RADIANS, case["double_pairs"][0][1]) and _in(FEET, case["double_pairs"][1][1]), key
        assert len(case["sha256"]) == 64 and case["bytes"] > 0, key
