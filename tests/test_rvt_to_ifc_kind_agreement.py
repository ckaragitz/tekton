"""rvt -> ifc labels a board by the resolver's OWN panelboard rule (#412,
landed with #331): ``rvt_to_ifc._classify`` calls
``rvt.ifc.intent.panelboard_flavour`` instead of keeping a copy of its
precedence, so the kind extracted from a .rvt and the kind re-resolved from
the emitted IFC cannot drift apart again -- in particular a family named
``Lighting Panelboard LP-1 208Y/120 ...`` is a lighting panelboard on both
sides and the round-trip table stays ``all_survived``.

The unit table is fresh-clone safe (no files); the end-to-end round trip
builds the #331 conformance fixture through the front door on the bundled
genesis base and skips where the schema cache / famgen catalog / base are
absent.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

pytest.importorskip("numpy", reason="rvt.ifc.intent imports numpy (#127)")

from conftest import needs_schema                              # noqa: E402
from rvt.convert import rvt_to_ifc as R2I                       # noqa: E402
from rvt.ifc import intent as I                                # noqa: E402


@pytest.mark.parametrize("name, contract", [
    # our own generated family names + type-table contract, as extract_intent sees them
    ("Lighting Panelboard LP-1 208Y/120 100A MLO 42sp",
     {"PanelName": "LP-1", "Voltage": 208.0, "BusRating": 100.0, "MainsType": "MLO"}),
    ("Receptacle Panelboard RP-1 480Y/277 225A MB 42sp",
     {"PanelName": "RP-1", "Voltage": 480.0, "BusRating": 225.0, "MainsType": "MCB"}),
    ("Distribution Panelboard DP-1 208Y/120 400A MB 42sp",
     {"PanelName": "DP-1", "Voltage": 208.0, "BusRating": 400.0, "MainsType": "MCB"}),
    ("Panelboard PP-1 208Y/120 225A MB 42sp",
     {"PanelName": "PP-1", "Voltage": "208Y/120 V", "BusRating": 225.0, "MainsType": "MCB"}),
    ("Panelboard H-1 480Y/277 400A", {"PanelName": "H-1", "Voltage": 480.0, "BusRating": 400.0}),
    ("Panelboard H-2 480Y/277", {"PanelName": "H-2", "Voltage": "480Y/277 V"}),
    # a foreign family name (Revit's stock board) round-tripping through us
    ("M_Lighting and Appliance Panelboard - 208V MLO",
     {"PanelName": "LP-4", "Voltage": 208.0, "BusRating": 100.0, "MainsType": "MLO"}),
])
def test_extracted_kind_is_the_resolvers_rule(name, contract):
    """``_classify`` == ``panelboard_flavour`` on the same evidence: one rule."""
    hay = f"{name} {contract['PanelName']}".lower()
    ll = I.parse_voltage(contract["Voltage"]).get("ll") if isinstance(contract["Voltage"], str) \
        else float(contract["Voltage"])
    want = I.panelboard_flavour(hay, ll=ll, bus=contract.get("BusRating"),
                                mains=str(contract.get("MainsType") or ""))
    assert R2I._classify(name, contract) == want


def test_lp_at_208_is_lighting_on_the_rvt_side_too():
    """The #331 case seen from the .rvt: explicit LP-/lighting evidence beats 208 V."""
    assert R2I._classify("Lighting Panelboard LP-1 208Y/120 100A MLO 42sp",
                         {"PanelName": "LP-1", "Voltage": 208.0, "BusRating": 100.0,
                          "MainsType": "MLO"}) == "lighting_panelboard"
    assert R2I._classify("Switchboard MSB 2500A 480Y/277", {"PanelName": "MSB"}) == "switchboard"
    assert R2I._classify("Dry Type Transformer T-1 75kVA 480-208Y/120", {}) == "transformer"


# ---------------------------------------------------------------------------
# end to end: the #331 fixture -> .rvt (front door) -> .ifc (rvt_to_ifc) round trip
# ---------------------------------------------------------------------------

H_FIXTURE = os.path.join(ROOT, "tests", "ifc_conformance", "h_mapped_item_reuse.ifc")
PINNED_2026 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import catalog as C
        C.load_line("eaton", "pow-r-line-panelboards")
        return True
    except Exception:                                          # noqa: BLE001
        return False


@needs_schema
@pytest.mark.skipif(not os.path.isfile(PINNED_2026), reason="bundled genesis base missing")
@pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")
def test_h_fixture_round_trip_survives_with_lighting_kinds(tmp_path):
    """Three ``LP-n lighting panel 208Y/120 V`` boards: built as Lighting
    Panelboard families, extracted from the .rvt as ``lighting_panelboard``,
    re-resolved from the emitted IFC as ``lighting_panelboard`` -- kind_ok x3,
    all_survived (before #331/#412 the extractor said receptacle x3)."""
    import rvt.frontdoor as FD
    job = FD.author(ifc=H_FIXTURE, out=str(tmp_path / "job"), no_handoff=True)
    assert job.ok, (job.status, job.errors)
    rvt_path = job.manifest["build"]["files"]["combined"]["path"]
    rec = R2I.convert_rvt_to_ifc(rvt_path, str(tmp_path / "h.ifc"), out_dir=str(tmp_path / "rt"))
    assert os.path.isfile(str(tmp_path / "h.ifc")), rec.get("errors")          # delivered
    assert sorted((e["tag"], e["kind"]) for e in rec["equipment"]) == [
        ("LP-1", "lighting_panelboard"), ("LP-2", "lighting_panelboard"), ("LP-3", "lighting_panelboard")]
    rt = rec["roundtrip"]
    assert rt["ran"] is True, rt
    assert [r["kind_ok"] for r in rt["equipment"]] == [True, True, True], rt["equipment"]
    assert rt["equipment_survived"] == "3/3" and rt["all_survived"] is True, rt
