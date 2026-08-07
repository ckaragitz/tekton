"""Tests for tools/genesis_substitute.py (THE SUBSTITUTION LADDER, X-rungs).

They exercise the tool's core machinery on the passing base
(experiments/genesis/triage/K1.rvt = Autodesk's empty-project skeleton,
viewer PASS): the schema-TYPED reference walk (no false positives on the
pen table's id 2, which byte-scans hit ~40 times in geometry-step
counters), the registry-surface capture + path normalization, and one
end-to-end substitution (X1: the project pen table -> ours) whose registry
PARITY, validator-cleanliness (0 errors), structural proof and four-
registry document coherence must all hold.  The already-built ladder on
disk (if present) is checked for report / manifest consistency.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
SUBST = os.path.join(ROOT, "experiments", "genesis", "subst")
pytestmark = pytest.mark.skipif(not os.path.exists(K1),
                                reason="K1.rvt (viewer-PASSED empty-project base) not present")

import genesis_substitute as GS   # noqa: E402


@pytest.fixture(scope="module")
def ctx():
    return GS.SubstContext(K1, "TX")


# ---------------------------------------------------------------------------
# 1. the typed reference machinery
# ---------------------------------------------------------------------------

def test_typed_walk_ignores_the_pen_tables_false_positives(ctx):
    """The project pen table is element id 2.  A byte scan finds dozens of
    'referrers' (geometry-step type codes / counters equal to 2); the
    schema-TYPED walk must find ZERO ElementId leaves holding 2 in those
    records -- the whole reason the substitution uses typed decoding."""
    doc = ctx.doc
    pens = [e for e in ctx.ids_of("PenWidthTableElem")
            if int(ctx.value(e).get("m_famId", -1)) == -1]
    assert pens == [2], pens
    # a curtain-mullion FamilySymbol byte-mentions '2' many times
    victims = [e for e in ctx.host if ctx.cls_of.get(e) == "FamilySymbol"][:6]
    assert victims
    for e in victims:
        v = doc.value(e) or {}
        leaves = ctx.ted.leaves(v, "FamilySymbol")
        assert not [lf for lf in leaves if lf.value == 2], \
            f"typed walk falsely typed a '2' as an ElementId in {e}"
    # and the arbiter-typed graph has NO referrer for the pen table
    assert not ctx.inbound(2)


def test_typed_walk_finds_dbviewproject_regen_edges_to_default_orgs(ctx):
    """DBViewProject's seq-101 header m_regenOnly names the four DEFAULT
    browser organizations -- the typed walk must find exactly those (the
    edges X2 re-points)."""
    orgs = set(ctx.ids_of("BrowserOrganization"))
    defaults = {o for o in orgs if bool(ctx.value(o).get("m_bDefault"))}
    assert len(defaults) == 4
    proj = ctx.ids_of("DBViewProject")
    assert len(proj) == 1
    hdr = ctx.doc.value(proj[0], 101)
    hits = {lf.value for lf in ctx.ted.leaves(hdr, "ElementHeader") if lf.value in orgs}
    assert hits == defaults, (hits, defaults)


def test_registry_surface_of_the_pen_table_is_one_leaf(ctx):
    """id 2's whole ADocument registry surface = PenWidthTableInfo.
    m_penWidthTableElemId (1 leaf) -- the surface X1 re-points."""
    surf = GS.adoc_surface(ctx.ted_adoc, ctx.tree, {2})
    assert set(surf) == {2}
    assert len(surf[2]) == 1
    assert surf[2][0].endswith("PenWidthTableInfo.m_penWidthTableElemId")


def test_uet_slot_index_survives_path_normalization():
    """Path normalization wildcards ordinary container indices but KEEPS
    the positional UniqueElementsTracking slot index (the slot IS the
    identity there)."""
    n = GS.normalize_surface_path
    p_uet = ("ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[72]"
             "->UniqueElementsTracking.m_elemIds[43]")
    assert n(p_uet).endswith("UniqueElementsTracking.m_elemIds[43]")
    assert "m_appInfoArr[*]" in n(p_uet)
    p_set = ("ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[75]"
             "->BrowserOrganizationTracking.m_elemIdSet[9]")
    assert n(p_set).endswith("BrowserOrganizationTracking.m_elemIdSet[*]")


def test_own_fixpoint_does_not_swallow_view_trackers(ctx):
    """The substitution's ownership growth must NOT pull in trackers /
    settings singletons that merely REFERENCE seeded content (the
    reduction ladder's child set does -- X9's parity assertion caught our
    InitialViewSettings being swept away by its start-view reference)."""
    for cls_name in ("InitialViewSettings", "AllPlanTopologies", "GCSTracker"):
        assert cls_name not in GS.SUBST_CHILD_CLASSES
    for cls_name in ("Viewer", "Viewport", "DBDrawing", "SunAndShadowSettings"):
        assert cls_name in GS.SUBST_CHILD_CLASSES
    ivs = ctx.ids_of("InitialViewSettings")
    assert len(ivs) == 1
    views = set(ctx.ids_of("DBViewDrafting"))       # its start view is a drafting view
    grown = ctx.own_fixpoint(views)
    assert ivs[0] not in grown


# ---------------------------------------------------------------------------
# 2. one end-to-end substitution: X1 (the project pen table -> ours)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def x1_report(tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp("subst"))
    rung = GS.rung_by_name("X1")
    rep = GS.substitute(rung, K1, out_dir=out_dir)
    return rep, out_dir


def test_x1_pen_table_substitution_is_valid_and_parity_holds(x1_report):
    """K1 with its pen table (id 2) replaced by ours: exactly one old /
    one new element, a 1:1 correspondence, the PenWidthTableInfo leaf now
    names OUR id, zero old ids left in the ADocument, zero NEW dangling
    ids, structural proof clean, four-registry coherence intact, and the
    validator reports ZERO errors."""
    rep, out_dir = x1_report
    assert rep["verdict"] == "VALID", rep.get("FAILED_SELF_CHECK")
    assert rep["old"]["count"] == 1 and rep["new"]["count"] == 1
    assert len(rep["correspondence"]) == 1
    pair = rep["correspondence"][0]
    assert pair["old"] == 2 and pair["old_class"] == "PenWidthTableElem"
    assert pair["new_class"] == "PenWidthTableElem"
    par = rep["parity"]
    assert par["pairs"] == 1 and par["pairs_ok"] == 1 and par["pairs_failed"] == 0
    assert not par["old_ids_still_in_adocument"]
    assert par["adocument_dangling_created"] == []
    row = par["table"][0]
    assert row["parity"] is True
    assert any(p.endswith("PenWidthTableInfo.m_penWidthTableElemId")
               for p in row["surface_after"])
    # certification
    assert rep["validator"]["ok"] is True and rep["validator"]["errors"] == 0
    assert rep["structural"]["ok"] is True
    assert rep["coherence"]["coherent"] is True
    # the emitted file exists and re-decodes with our id in the registry
    out = os.path.join(out_dir, "X1.rvt")
    assert os.path.exists(out)
    from rvt.container import open_rvt
    from rvt import adocument as adoc
    with open_rvt(out) as f:
        a = adoc.decode_latest(f.inflate("Global/Latest"))
    assert a.clean
    body = GS.GA._appinfo_body(a.value, "PenWidthTableInfo")
    assert body["m_penWidthTableElemId"] == pair["new"]


def test_new_records_reference_check_refuses_dangling(ctx, monkeypatch, tmp_path):
    """A rung whose new records reference an id that will not exist after
    the substitution is REFUSED before any file is written (the X5-defect
    guard: our records must be wired to the CURRENT file, not to dropped
    catalog siblings)."""
    from rvt.genesis import settings as ST
    from rvt.genesis.types import IdSource

    def bad_build(c):
        rec = ST.pen_width_table(ids=IdSource(9_900_000))
        rec.obj["m_famId"] = 7_777_777          # a family that does not exist
        return GS.SubstBuild(old_ids=[2], records=[rec], corr={2: rec.elem_id})
    rung = GS.Rung(name="TBAD", label="bad", parent="K1", description="", tests="",
                   if_pass="", if_fail="", build=bad_build)
    rep = GS.substitute(rung, K1, out_dir=str(tmp_path))
    assert rep.get("FAILED_SELF_CHECK")
    assert rep["new_records_reference_check"]["dangling"] >= 1
    assert not os.path.exists(os.path.join(str(tmp_path), "TBAD.rvt"))


# ---------------------------------------------------------------------------
# 3. the built ladder on disk (reports + manifest) -- consistency
# ---------------------------------------------------------------------------

_LADDER = ["X1", "X2", "X3", "X4", "X5", "X10", "X6a", "X7", "X8", "X9"]


@pytest.mark.skipif(not os.path.exists(os.path.join(SUBST, "X9.json")),
                    reason="the substitution ladder has not been built on disk")
def test_built_ladder_reports_are_all_valid_and_parity_clean():
    for name in _LADDER:
        p = os.path.join(SUBST, f"{name}.json")
        assert os.path.exists(p), f"{name}.json missing"
        with open(p) as fh:
            rep = json.load(fh)
        assert rep.get("verdict") == "VALID", (name, rep.get("FAILED_SELF_CHECK"))
        v = rep.get("validator") or {}
        assert v.get("ok") is True and v.get("errors") == 0, name
        assert (rep.get("structural") or {}).get("ok") is True, name
        assert (rep.get("coherence") or {}).get("coherent") is True, name
        if rep.get("kind") == "substitute":
            par = rep["parity"]
            assert par["pairs_failed"] == 0, name
            assert par["uet_failed"] == 0, name
            assert not par["old_ids_still_in_adocument"], name
            assert par["adocument_dangling_created"] == [], name
        assert os.path.exists(os.path.join(SUBST, f"{name}.rvt")), name


@pytest.mark.skipif(not os.path.exists(os.path.join(SUBST, "probes.json")),
                    reason="probes.json not present")
def test_probes_manifest_is_ordered_and_derivation_is_a_chain():
    with open(os.path.join(SUBST, "probes.json")) as fh:
        man = json.load(fh)
    names = [p["rung"] for p in man["probes"]]
    assert names[:len(_LADDER)] == _LADDER
    # every uploaded rung derives from the previous one (a chain from K1)
    by_name = {r.name: r for r in GS.RUNGS}
    prev = "K1"
    for n in _LADDER:
        assert by_name[n].parent == prev, (n, by_name[n].parent, prev)
        prev = n
    assert "Xn" not in man["upload_order"]          # the report rung has no file
    assert man["upload_order"] == _LADDER
