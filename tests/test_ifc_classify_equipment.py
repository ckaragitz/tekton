"""rvt.ifc.intent._classify_equipment / panelboard_flavour -- panelboard
flavours (#331).

Explicit role evidence in the product's own text (name / description /
object type / tag: ``receptacle|appliance|RP-``, ``lighting|LP-``, ``DP-``)
outranks the voltage and mains heuristics, so an ``LP-2 lighting panel
208Y/120 V`` is a lighting panelboard and not a receptacle one by its 208 V.
The heuristics still decide when the text says nothing; the bare word
'distribution' (IEC's generic name for any board) stays below them.

Backend-free and fresh-clone safe: the classifier only reads attributes off
the product, so a stub stands in for an IfcElectricDistributionBoard; the
same cases through both IFC readers are pinned by the conformance fixtures
``c_storeys_relative_placement`` / ``h_mapped_item_reuse`` / ``e_space_in_storey``.
"""
from __future__ import annotations

import pytest

pytest.importorskip("numpy", reason="rvt.ifc.intent imports numpy (#127)")

from rvt.ifc import intent as I  # noqa: E402


class _Board:
    """The attribute surface ``_classify_equipment`` reads off a product."""

    def __init__(self, name, tag, *, object_type=None, description=None, predefined="DISTRIBUTIONBOARD"):
        self.Name, self.Tag, self.ObjectType, self.Description = name, tag, object_type, description
        self.PredefinedType = predefined

    def is_a(self):
        return "IfcElectricDistributionBoard"


def _kind(name, tag, schedule, **kw):
    prod = _Board(name, tag, **kw)
    psets = {"PanelSchedule": schedule}
    contract = I.normalize_contract(psets, name=prod.Name, object_type=prod.ObjectType,
                                    description=prod.Description, tag=prod.Tag)
    return I._classify_equipment(prod, psets, contract)


@pytest.mark.parametrize("name, tag, schedule, want", [
    # #331: the name and the tag prefix say lighting; 208Y/120 V no longer overrides them
    ("LP-2 lighting panel 208Y/120 V", "LP-2",
     {"Voltage": "208Y/120 V", "BusRating": 100.0, "MainsType": "Main lugs only"}, "lighting_panelboard"),
    # one of our three tag prefixes alone is evidence enough, whatever the voltage
    ("Panelboard 100 A", "LP-1", {"Voltage": "208Y/120 V", "BusRating": 100.0}, "lighting_panelboard"),
    ("Panelboard 225 A", "RP-1", {"Voltage": "480Y/277 V", "BusRating": 225.0}, "receptacle_panelboard"),
    ("Panelboard 400 A", "DP-1", {"Voltage": "208Y/120 V", "BusRating": 400.0}, "distribution_panelboard"),
    ("RP-2 receptacle panel 208Y/120 V", "RP-2", {"Voltage": "208Y/120 V", "BusRating": 225.0},
     "receptacle_panelboard"),
    # a receptacle / appliance WORD still beats an LP- prefix (inputs/ifc/electrical-room-2500a LP-4)
    ("LP-4 - receptacle / appliance panelboard, 208Y/120 V", "LP-4",
     {"Voltage": "208Y/120 V", "BusRating": 225.0, "MainsType": "Main breaker"}, "receptacle_panelboard"),
    # today's reading of Revit's stock 'Lighting and Appliance Panelboard' family name (the NEC
    # generic class): 'appliance' wins -- pinned as-is, its handling vs the prompt route is #414's call
    ("M_Lighting and Appliance Panelboard - 480V MLO - Surface", "LP-1",
     {"Voltage": "480Y/277 V", "BusRating": 100.0, "MainsType": "Main lugs only"}, "receptacle_panelboard"),
    # no role evidence in the text: the heuristics decide, in their old order
    ("PP-1A panelboard", "PP-1A", {"Voltage": "208Y/120 V", "BusRating": 225.0}, "receptacle_panelboard"),
    ("Panel P-7", "P-7", {"Voltage": "480Y/277 V", "BusRating": 100.0, "MainsType": "Main lugs only"},
     "lighting_panelboard"),
    ("Panel H-1", "H-1", {"Voltage": "480Y/277 V", "BusRating": 400.0}, "distribution_panelboard"),
    ("Panel H-2", "H-2", {"Voltage": "480Y/277 V"}, "panelboard"),
    # 'distribution' as a bare word is weak: IEC's 230 V 'Distribution Board' is a branch panel
    ("Distribution Board DB-1", "DB-1", {"Voltage": "230 V", "BusRating": 100.0}, "receptacle_panelboard"),
    ("Distribution Board DB-2", "DB-2", {"Voltage": "480Y/277 V", "BusRating": 100.0}, "distribution_panelboard"),
])
def test_panelboard_flavour(name, tag, schedule, want):
    assert _kind(name, tag, schedule) == want


def test_role_word_in_object_type_or_description_counts():
    sched = {"Voltage": "208Y/120 V", "BusRating": 100.0}
    assert _kind("Panel A", "A", sched, object_type="Lighting panelboard") == "lighting_panelboard"
    assert _kind("Panel B", "B", sched, description="appliance branch panel") == "receptacle_panelboard"


def test_switchboard_evidence_precedes_panel_flavours():
    sched = {"Voltage": "208Y/120 V", "BusRating": 1200.0}
    assert _kind("LP-MSB lighting switchboard", "LP-MSB", sched) == "switchboard"
    assert _kind("Board", "SB-1", sched, predefined="SWITCHBOARD") == "switchboard"


def test_shared_flavour_rule_is_callable_without_a_product():
    """The precedence is ONE plain function of (text, volts, amps, mains) so a
    caller that has no IFC product -- the rvt -> ifc extractor, #412 -- labels
    boards by the very same rule instead of a copy of it."""
    assert I.panelboard_flavour("lighting panelboard lp-1 208y/120 100a mlo 42sp",
                                ll=208.0, bus=100.0, mains="MLO") == "lighting_panelboard"
    assert I.panelboard_flavour("panel x", ll=None, bus=None, mains="") == "panelboard"
    assert I.panelboard_flavour("panel x", ll=208.0, bus=400.0, mains="") == "receptacle_panelboard"
