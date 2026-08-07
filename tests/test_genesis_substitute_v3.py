"""Tests for tools/genesis_substitute_v3.py (THE SUBSTITUTION LADDER v3:
rebased on a CERTIFIED base, pure IN-PLACE substitution).

They exercise: the base-certification gate (a ladder may only derive from a
viewer-CERTIFIED file -- the K1 disaster's lesson), the in-place PLAN
machinery (role correspondents + slot-fill donors, same class only), the
retarget self-checks (dangling reference / lossy record refusal), and two
end-to-end in-place rungs on the certified base K4: Y1/Y_pen (ONE object
swapped -- our pen table at Autodesk's id 2) and Y_cat (the whole present
built-in catalog swapped row for row).  Each asserts the byte-delta law of
an in-place rung: ONLY the landed slots' seq-102 records change,
Global/Latest + Global/ElemTable are byte-identical, nothing is added or
removed, the validator reports 0 errors.  The built ladder on disk (if
present) is checked for report / manifest consistency.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

K4 = os.path.join(ROOT, "experiments", "genesis", "triage", "K4.rvt")
K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
SUBST = os.path.join(ROOT, "experiments", "genesis", "subst_k4")
pytestmark = pytest.mark.skipif(not os.path.exists(K4),
                                reason="K4.rvt (viewer-CERTIFIED family-free base) not present")

import genesis_substitute_v3 as V3   # noqa: E402


# ---------------------------------------------------------------------------
# 1. the base-certification gate (standing-controls discipline)
# ---------------------------------------------------------------------------

def test_k4_is_certified_and_a_ladder_may_derive_from_it():
    cert = V3.certification_of(K4)
    assert cert is not None, "K4 must be listed in viewer-certified.json 'certified'"
    assert "family" in (cert.get("proves") or "").lower() or "document" in (cert.get("proves") or "").lower()
    assert V3.assert_certified(K4) is not None


@pytest.mark.skipif(not os.path.exists(K1), reason="K1.rvt not present")
def test_uncertified_base_is_refused():
    """K1 is the FAILED base of verdict #15 -- the tool must refuse to build a
    ladder on it (or on any file not listed as certified)."""
    assert V3.certification_of(K1) is None
    with pytest.raises(RuntimeError):
        V3.assert_certified(K1)


# ---------------------------------------------------------------------------
# 2. the in-place plan: role primaries + slot-fill, same class only
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ctx_k4():
    return V3.GS.SubstContext(K4, "TEST")


def test_plan_lands_every_palette_record_into_a_same_class_slot(ctx_k4):
    """X7 on K4: our 22-record palette (13 materials / 5 fills / 4 lines) is
    smaller than the sample's palette (23 / 9 / 7), so slot-fill lands ALL of
    it -- role correspondents first (many sample materials share one of our
    roles -> the most-referenced one is the primary), the rest as donors --
    with every slot the SAME class as our record, no additions, and the
    sample's surplus left as residue."""
    sb = V3.GS.build_X7(ctx_k4)
    plan = V3.plan_inplace(ctx_k4, sb, slot_fill=True)
    recs = {int(r.elem_id): r for r in sb.records}
    assert len(sb.records) == 22
    assert len(plan.pairs) == 22 and not plan.dropped
    for p in plan.pairs:
        assert ctx_k4.cls_of.get(p.slot) == recs[p.ours].class_name == p.cls
        assert p.match in {"role", "role-primary", "sibling-donor", "donor"}
    # slots are unique
    assert len({p.slot for p in plan.pairs}) == 22
    # residue = the sample palette elements + companions nobody landed on
    old = {int(o) for o in sb.old_ids}
    assert {r["id"] for r in plan.residue} == old - {p.slot for p in plan.pairs}
    assert not plan.class_mismatch


def test_plan_never_reuses_a_protected_slot(ctx_k4):
    """A slot landed by an EARLIER rung is protected: it can be neither a
    role slot nor a donor here (the Y2 navigator's viewer must not become
    a slot for a Y9 view's viewer)."""
    sb = V3.GS.build_X1(ctx_k4)
    plan_free = V3.plan_inplace(ctx_k4, sb, slot_fill=True)
    assert len(plan_free.pairs) == 1 and plan_free.pairs[0].slot == 2
    plan_prot = V3.plan_inplace(ctx_k4, sb, slot_fill=True, protected={2})
    assert not plan_prot.pairs
    assert len(plan_prot.dropped) == 1
    assert plan_prot.protected_skipped and plan_prot.protected_skipped[0]["id"] == 2


# ---------------------------------------------------------------------------
# 3. retarget self-checks: no dangling references, no lossy records
# ---------------------------------------------------------------------------

def test_retarget_refuses_records_referencing_nonexistent_ids(ctx_k4, tmp_path, monkeypatch):
    """A rung whose new object references an id that will not exist after
    the substitution is REFUSED before any file is written."""
    from rvt.genesis import settings as ST
    from rvt.genesis.types import IdSource

    def bad_build(ctx):
        rec = ST.pen_width_table(ids=IdSource(9_900_000))
        rec.obj["m_famId"] = 7_777_777                    # an element that does not exist
        return V3.GS.SubstBuild(old_ids=[2], records=[rec], corr={2: rec.elem_id})

    monkeypatch.setattr(V3.GS, "build_X1", bad_build)
    rung = V3.rung_by_name("Y1")
    rep = V3.substitute_inplace(rung, K4, K4, out_dir=str(tmp_path))
    assert rep.get("verdict") == "NOT-BUILT"
    assert rep.get("FAILED_SELF_CHECK")
    assert rep["new_object_reference_check"]["dangling"] >= 1
    assert not os.path.exists(os.path.join(str(tmp_path), "Y1.rvt"))


# ---------------------------------------------------------------------------
# 4. end-to-end: Y1 == Y_pen (ONE object swapped at Autodesk's registration)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def y1_report(tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp("subst_v3"))
    rung = V3.rung_by_name("Y1")
    rep = V3.substitute_inplace(rung, K4, K4, out_dir=out_dir)
    return rep, out_dir


def test_y_pen_swaps_exactly_one_object_record(y1_report):
    """K4 with OUR pen-width table at PenWidthTableElem id 2: the byte-delta
    law of an in-place rung must hold to the letter -- only the (102, 2)
    record differs, the partition stream is the only differing stream,
    Global/Latest + Global/ElemTable are byte-identical, nothing is added
    or removed, the registration of slot 2 is untouched, and the arbiter
    reports ZERO errors."""
    rep, out_dir = y1_report
    assert rep["verdict"] == "VALID", rep.get("FAILED_SELF_CHECK")
    plan = rep["plan"]
    assert plan["landed"] == 1 and plan["dropped_ours"] == 0
    slots = [r["slot"] for r in rep["landed_slots"]]
    assert slots == [2]
    bd = rep["byte_delta"]
    assert bd["assertion_holds"] is True, bd["problems"]
    assert bd["only_partition_differs"] is True
    assert bd["records_changed_ids"] == [2]
    assert bd["records_added_ids"] == [] and bd["records_removed_ids"] == []
    assert bd["elemtable_identical"] is True
    assert bd["adocument_identical"] is True
    par = rep["parity"]
    assert par["latest_byte_identical"] is True
    assert par["pairs"] == 1 and par["pairs_ok"] == 1 and par["pairs_failed"] == 0
    # the registry surface of slot 2 = the one PenWidthTableInfo leaf
    ex = par["surface_examples"][0]
    assert ex["slot"] == 2 and ex["n_paths"] == 1
    assert ex["paths"][0].endswith("PenWidthTableInfo.m_penWidthTableElemId")
    # the registration diff: identical (row / positions / surface untouched)
    rd = rep["registration_diff_sample"]
    assert rd and rd[0]["slot"] == 2 and rd[0]["registration_identical"] is True
    # certification
    assert rep["validator"]["ok"] is True and rep["validator"]["errors"] == 0
    assert rep["structural"]["ok"] is True
    assert rep["coherence"]["coherent"] is True
    assert os.path.exists(os.path.join(out_dir, "Y1.rvt"))


def test_y_pen_object_is_ours_and_id_follows_the_slot(y1_report):
    """The object now at id 2 decodes as OUR pen table (m_id == 2, our pen
    series) -- not the sample's."""
    rep, out_dir = y1_report
    from rvt.mutate import Document
    ours = Document.from_file(os.path.join(out_dir, "Y1.rvt")).value(2, 102)
    parent = Document.from_file(K4).value(2, 102)
    assert ours.get("m_id") == 2
    pens_ours = (((ours.get("m_pPenWidthTable") or {}).get("value") or {})
                 .get("m_draftPenInfo") or {}).get("m_pens")
    pens_parent = (((parent.get("m_pPenWidthTable") or {}).get("value") or {})
                   .get("m_draftPenInfo") or {}).get("m_pens")
    assert pens_ours and pens_parent and pens_ours != pens_parent


# ---------------------------------------------------------------------------
# 5. end-to-end: Y_cat (the whole present catalog, row for row, in place)
# ---------------------------------------------------------------------------

def test_y_cat_swaps_every_present_catalog_row_and_nothing_else(tmp_path_factory):
    """K4 carries 1,172 of the 1,407-row built-in style enum (its R9 lineage
    GC'd the rest and still LOADS): every one of them is replaced in place
    by our row of the same (category, style-type); our 235 rows the base
    lacks are NOT added (listed); only those 1,172 object records change."""
    out_dir = str(tmp_path_factory.mktemp("subst_v3_cat"))
    rep = V3.substitute_inplace(V3.rung_by_name("Y_cat"), K4, K4, out_dir=out_dir)
    assert rep["verdict"] == "VALID", rep.get("FAILED_SELF_CHECK")
    plan = rep["plan"]
    assert plan["landed"] == 1172
    assert plan["landed_by_class"] == {"GStyleElem": 1172}
    assert plan["by_match"] == {"role": 1172}          # a perfect 1:1 by (category, type)
    assert rep["ours_not_landed"]["count"] == 235       # ours-only enum keys: not added
    assert rep["residue_olds_left_in_place"]["count"] == 0
    bd = rep["byte_delta"]
    assert bd["assertion_holds"] and bd["only_partition_differs"]
    assert bd["records_changed_count"] == 1172 and len(bd["records_changed_ids"]) == 1172
    assert not bd["records_added_ids"] and not bd["records_removed_ids"]
    assert bd["elemtable_identical"] and bd["adocument_identical"]
    assert rep["validator"]["ok"] is True and rep["validator"]["errors"] == 0
    # a landed row now carries OUR values with the SAME built-in category key
    from rvt.mutate import Document
    d_out = Document.from_file(os.path.join(out_dir, "Y_cat.rvt"))
    d_base = Document.from_file(K4)
    slot = rep["landed_slots"][0]["slot"]
    o_new, o_old = d_out.value(slot, 102), d_base.value(slot, 102)
    assert o_new["m_categoryId"] == o_old["m_categoryId"]         # same category (the key)
    assert o_new.get("m_gstyleType") == o_old.get("m_gstyleType")
    assert o_new.get("m_id") == slot
    assert o_new != o_old                                        # our values, not theirs


# ---------------------------------------------------------------------------
# 6. the built ladder on disk (reports + manifest) -- consistency
# ---------------------------------------------------------------------------

_LADDER = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7", "Y8", "Y9"]


@pytest.mark.skipif(not os.path.exists(os.path.join(SUBST, "Y9.json")),
                    reason="the v3 substitution ladder has not been built on disk")
def test_built_ladder_reports_all_obey_the_inplace_byte_delta_law():
    for name in _LADDER + ["Y_cat"]:
        p = os.path.join(SUBST, f"{name}.json")
        assert os.path.exists(p), f"{name}.json missing"
        with open(p) as fh:
            rep = json.load(fh)
        assert rep.get("verdict") == "VALID", (name, rep.get("FAILED_SELF_CHECK"))
        assert (rep.get("validator") or {}).get("errors") == 0, name
        assert (rep.get("structural") or {}).get("ok") is True, name
        assert (rep.get("coherence") or {}).get("coherent") is True, name
        bd = rep["byte_delta"]
        assert bd["assertion_holds"] is True, (name, bd["problems"])
        assert bd["only_partition_differs"] is True, name
        assert bd["records_added_ids"] == [] and bd["records_removed_ids"] == [], name
        assert bd["elemtable_identical"] is True and bd["adocument_identical"] is True, name
        assert (rep.get("parity") or {}).get("pairs_failed") == 0, name
        for row in rep.get("registration_diff_sample") or []:
            assert row.get("registration_identical") is True, (name, row)
        assert os.path.exists(os.path.join(SUBST, f"{name}.rvt")), name
        # every rung names its CERTIFIED base
        assert (rep.get("base") or {}).get("certification"), name


@pytest.mark.skipif(not os.path.exists(os.path.join(SUBST, "Yn.json")),
                    reason="the residue census has not been built")
def test_residue_census_accounts_for_every_element():
    with open(os.path.join(SUBST, "Yn.json")) as fh:
        yn = json.load(fh)
    landed = yn["landed_ours"]["elements"]
    residue = yn["residue_still_autodesk"]["elements"]
    assert landed + residue == yn["elements_total"]
    # the residue buckets are all named (no silent unknowns)
    for bkt in yn["residue_still_autodesk"]["by_bucket"]:
        assert bkt != "unclassified", "unclassified residue -- add a bucket reason"
    # the two work queues exist
    assert yn["ours_not_landed_across_ladder"]


@pytest.mark.skipif(not os.path.exists(os.path.join(SUBST, "probes.json")),
                    reason="probes.json not present")
def test_probes_manifest_is_bisection_first_and_names_the_base_and_control():
    with open(os.path.join(SUBST, "probes.json")) as fh:
        man = json.load(fh)
    order = man["upload_order_bisection_first"]
    assert order[:4] == ["Y9", "Y6", "Y_pen", "Y_cat"]
    assert set(_LADDER) <= set(order)
    assert man["base"]["file"].endswith("triage/K4.rvt")
    assert man["base"]["certification"], "the base's certification must be quoted"
    for probe in man["probes"]:
        assert (probe.get("base") or {}).get("certification"), probe.get("rung")
        assert probe.get("control_to_upload_with_batch"), probe.get("rung")
    # the Y_pen alias points at Y1's file
    ypen = next(p for p in man["probes"] if p["rung"] == "Y_pen")
    assert ypen.get("alias_of") == "Y1" and ypen["file"].endswith("Y1.rvt")
