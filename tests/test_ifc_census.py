"""The IFC census (issue #153, PG1 honesty): every ``--ifc`` intent enumerates
what the file held against what reached it -- per IfcProduct class read /
mapped / recorded-only / dropped (+ why), the spatial structure, every Body
item by type with the ones no reader exists for, the relationships not read
-- and the deliverable manifest PRINTS the losses ('Not converted from the
IFC') plus ONE build degradation line, without touching delivery (a label,
hard rule 1).

Stdlib / steplite only, in the CI shard: the resolver runs in a child
interpreter with ``RVT_STEPLITE_FORCE=1`` through the conformance generator's
``--resolve`` (tools/dev/make_ifc_fixtures.py), on OUR hand-authored fixture
``j_census_space_unreadable_body`` (an IfcSpace with its own extrusion, a
panel, a wall extrusion, a conduit whose only body is an IfcSweptDiskSolid)
and on ``inputs/ifc/electrical-room-2500a.ifc`` (nothing dropped, nothing
unreadable).  When a REAL ifcopenshell is importable the census it yields
must be identical to steplite's.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "dev", "make_ifc_fixtures.py")
FIXTURE = os.path.join(ROOT, "tests", "ifc_conformance", "j_census_space_unreadable_body.ifc")
ROOM_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")

_spec = importlib.util.spec_from_file_location("make_ifc_fixtures", TOOL)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

needs_numpy = pytest.mark.skipif(importlib.util.find_spec("numpy") is None,
                                 reason="intent placement / geometry maths needs numpy (#127)")
pytestmark = needs_numpy


def _censuses(force_steplite: bool, backend: str) -> dict:
    got = M.resolve_summaries([FIXTURE, ROOM_IFC], force_steplite=force_steplite)
    out = {}
    for path, summary in got.items():
        assert summary["backend"] == backend, f"{path}: expected the {backend} backend"
        assert summary["ok"], summary.get("error")
        out[path] = summary["census"]
    return out


@pytest.fixture(scope="module")
def lite():
    return _censuses(True, "steplite")


# ---------------------------------------------------------------------------
# the census itself (steplite, child interpreter)
# ---------------------------------------------------------------------------

def test_fixture_census_counts_space_dropped_and_swept_disk_unreadable(lite):
    c = lite[FIXTURE]
    assert c["schema"] == "IFC4"
    assert c["products_total"] == 7                     # site, building, storey, space, DP-1, W-1, CT-1
    assert c["totals"] == {"mapped": 2, "recorded": 4, "dropped": 1}
    bc = c["by_class"]
    assert bc["IfcSpace"] == {"read": 1, "mapped": 0, "recorded": 0, "dropped": 1,
                              "reason": bc["IfcSpace"]["reason"]}
    assert "#158" in bc["IfcSpace"]["reason"]
    assert bc["IfcElectricDistributionBoard"]["mapped"] == 1
    assert bc["IfcBuildingStorey"]["mapped"] == 1
    assert bc["IfcWallStandardCase"]["recorded"] == 1 and "kind wall" in bc["IfcWallStandardCase"]["reason"]
    assert bc["IfcCableCarrierSegment"]["recorded"] == 1
    assert {bc[k]["recorded"] for k in ("IfcSite", "IfcBuilding")} == {1}
    assert c["spatial"] == {"sites": 1, "buildings": 1, "storeys": 1, "spaces": 1}
    b = c["body_items"]
    assert b["by_type"] == {"IfcExtrudedAreaSolid": 2, "IfcSweptDiskSolid": 1, "IfcTriangulatedFaceSet": 2}
    assert (b["read"], b["unreadable"], b["on_unread_products"]) == (3, 1, 1)
    assert b["unreadable_by_type"] == {"IfcSweptDiskSolid": 1}
    assert [p["tag"] for p in b["products_left_bodiless"]] == ["CT-1"]
    assert "IfcExtrudedAreaSolid" in b["readable_kinds"] and "IfcSweptDiskSolid" not in b["readable_kinds"]
    assert c["relationships_ignored"] == []
    assert set(c["relationships_consumed"]) == {"IfcRelAggregates", "IfcRelContainedInSpatialStructure",
                                                "IfcRelDefinesByProperties"}


def test_room_ifc_census_drops_nothing_and_reads_every_body_item(lite):
    c = lite[ROOM_IFC]
    assert c["products_total"] == 17
    assert c["totals"]["dropped"] == 0
    assert all(row["dropped"] == 0 for row in c["by_class"].values())
    b = c["body_items"]
    assert b["by_type"] == {"IfcTriangulatedFaceSet": 111}
    assert (b["read"], b["unreadable"], b["on_unread_products"]) == (111, 0, 0)
    assert b["products_left_bodiless"] == [] and c["relationships_ignored"] == []


@pytest.mark.parametrize("path", [FIXTURE, ROOM_IFC])
def test_census_invariants(lite, path):
    """Every product lands in exactly one bucket; every body item is read,
    unreadable, or sat on a product the resolver never reads."""
    c = lite[path]
    rows = c["by_class"].values()
    assert sum(r["read"] for r in rows) == c["products_total"]
    for r in rows:
        assert r["mapped"] + r["recorded"] + r["dropped"] == r["read"]
        assert (r["dropped"] == 0) or r["reason"], "a dropped class always says why"
    assert {k: sum(r[k] for r in rows) for k in ("mapped", "recorded", "dropped")} == c["totals"]
    b = c["body_items"]
    assert b["read"] + b["unreadable"] + b["on_unread_products"] == b["total"] == sum(b["by_type"].values())
    assert sum(b["unreadable_by_type"].values()) == b["unreadable"]


def test_census_identical_under_real_ifcopenshell(lite):
    try:
        import ifcopenshell                                     # noqa: F401
    except ImportError:
        pytest.skip("real ifcopenshell not installed (optional extra .[ifc]); parity runs where it is")
    if getattr(ifcopenshell, "IS_STEPLITE", False):
        pytest.skip("only the bundled steplite shim is importable here")
    real = _censuses(False, "ifcopenshell")
    assert real == lite


# ---------------------------------------------------------------------------
# the manifest: section + ONE degradation line, delivery untouched
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def models():
    """Each IFC resolved ONCE in-process (whichever backend rvt.ifc selected --
    the census is identical under both)."""
    from rvt.frontdoor import intent as FI
    return {p: FI.intent_from_ifc(p) for p in (FIXTURE, ROOM_IFC)}


def _manifest_for(model, tmp_path):
    """summarize() -> build_manifest() -> MANIFEST.md text, with no build (the
    section and the line hang off the intent alone; the 17 s genesis build is
    the /verify run, not a shard test)."""
    from rvt.frontdoor import intent as FI
    from rvt.frontdoor import manifest as MF
    from rvt.frontdoor.base import ResolvedBase
    summary = FI.summarize(model)
    base = ResolvedBase(path=model.source_path, source="explicit", sha256="0" * 64, pinned=False)
    m = MF.build_manifest(route="ifc", inputs={"ifc": model.source_path}, base=base,
                          out_dir=str(tmp_path), intent_summary=summary, intent_json=None, build=None)
    return summary, m, MF._render_md(m)


def test_manifest_prints_not_converted_section_and_one_degradation(models, tmp_path):
    model = models[FIXTURE]
    summary, m, md = _manifest_for(model, tmp_path)
    assert {k: v for k, v in model.census.items() if k != "legend"} == summary["census"]
    assert summary["census"]["totals"]["dropped"] == 1
    assert m["intent"]["census_gaps"]["show"] is True            # manifest.json carries the compact gaps too
    assert summary["other_products_total"] == 0 and summary["other_products"] == []
    degr = [d for d in m["build"]["degradations"] if d.startswith("IFC census:")]
    assert len(degr) == 1, m["build"]["degradations"]
    assert "1 of 7 products dropped (IfcSpace×1)" in degr[0]
    assert "1 of 5 body items unreadable (IfcSweptDiskSolid×1)" in degr[0]
    assert "delivery unchanged" in degr[0]
    assert "## Not converted from the IFC" in md
    section = md.split("## Not converted from the IFC", 1)[1].split("\n## ", 1)[0]
    assert "**dropped** IfcSpace ×1" in section and "#158" in section
    assert "**unreadable body items** (1 of 5): IfcSweptDiskSolid ×1" in section
    assert "**left without any body**: 'CT-1'" in section
    assert "7 products read — 2 mapped, 4 recorded only, 1 dropped; body items 3/5 read, 1 unreadable" in md
    # the census never touches the status roll-up (a label, not refusal logic)
    assert "census" not in m["status"].lower()


def test_manifest_has_no_section_when_nothing_is_lost(models, tmp_path):
    model = models[ROOM_IFC]
    summary, m, md = _manifest_for(model, tmp_path)
    assert summary["census"]["totals"]["dropped"] == 0
    assert summary["census"]["body_items"]["unreadable"] == 0
    assert "## Not converted from the IFC" not in md
    assert not any(d.startswith("IFC census:") for d in m["build"]["degradations"])
    assert "nothing dropped or unreadable" in md
    # summarize() now carries the recorded-only products the manifest used to omit
    assert summary["other_products_total"] == len(model.other_products) == 2
    assert {o["kind"] for o in summary["other_products"]} == {"room_shell", "clearance"}
    assert "recorded, not modelled (2)" in md


def test_a_failing_census_never_costs_the_intent(monkeypatch, tmp_path):
    """The census is a pure observer: if IT raises, resolve_intent still
    returns the full intent (so the file is still built and delivered --
    rule 1), the fault rides in census['error'], the manifest says
    'unavailable' and adds no section / no degradation."""
    from rvt.ifc import intent as I
    from rvt.frontdoor import intent as FI
    from rvt.frontdoor import manifest as MF
    from rvt.frontdoor.base import ResolvedBase

    def boom(*_a, **_k):
        raise RuntimeError("synthetic census fault")
    monkeypatch.setattr(I, "_census", boom)
    model = FI.intent_from_ifc(FIXTURE)
    assert model.equipment and model.census == {"error": "RuntimeError: synthetic census fault"}
    summary = FI.summarize(model)
    base = ResolvedBase(path=FIXTURE, source="explicit", sha256="0" * 64, pinned=False)
    m = MF.build_manifest(route="ifc", inputs={"ifc": FIXTURE}, base=base, out_dir=str(tmp_path),
                          intent_summary=summary, intent_json=None, build=None)
    md = MF._render_md(m)
    assert "IFC census: **unavailable** (RuntimeError: synthetic census fault)" in md
    assert "## Not converted from the IFC" not in md
    assert not any(d.startswith("IFC census:") for d in m["build"]["degradations"])


def test_prompt_route_other_products_render_without_an_ifc_class(tmp_path):
    """The prompt route's recorded-only entries carry kind + name but no
    ifcClass; the manifest line must not print 'None →'."""
    from rvt.frontdoor import manifest as MF
    from rvt.frontdoor.base import ResolvedBase
    summary = {"project": "p", "other_products": [{"kind": "luminaire", "name": "6 downlights",
                                                    "disposition": "not modelled"}]}
    base = ResolvedBase(path=FIXTURE, source="explicit", sha256="0" * 64, pinned=False)
    m = MF.build_manifest(route="prompt", inputs={"prompt": "x"}, base=base, out_dir=str(tmp_path),
                          intent_summary=summary, intent_json=None, build=None)
    md = MF._render_md(m)
    assert "- recorded, not modelled (1): 6 downlights (luminaire)" in md and "None →" not in md


def test_intent_json_carries_the_census(models, tmp_path):
    import json
    from rvt.frontdoor import intent as FI
    p = FI.write_intent_json(models[FIXTURE], str(tmp_path / "intent.json"))
    with open(p) as fh:
        doc = json.load(fh)
    assert doc["census"]["by_class"]["IfcSpace"]["dropped"] == 1
    assert doc["census"]["legend"]["dropped"].startswith("present in the IFC")
