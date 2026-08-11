"""test_rvt_to_ifc_param_carrier.py -- the rvt -> ifc family tagging contract
reads Integer / Text parameters of law-built families by STORAGE CLASS (#355).

Under the storage-class law (#333 round 24, landed in #336) our generated
families author a Text parameter as ``ParamDefString`` and an Integer
parameter as ``ParamDefInt`` -- both WITHOUT ``m_specTypeId``.  The tagging
contract ``rvt.convert.rvt_to_ifc`` writes into the IFC property set keyed
its value carrier on the spec alone, so ``NumberOfCircuits`` (``m_int`` 42)
exported as ``0.0`` and an empty text as ``0.0``.  It now decides by the
definition CLASS first, spec second, through the ONE rule shared with the
family-edit inventory (``rvt.convert.param_carrier``, #354).

Self-contained: the family is generated fresh from the bundled catalog +
genesis base (no ``samples/``, no pre-built experiment output), so this file
runs green in a fresh clone and rides in the CI shard
(``tests/ci_shard.d/355-rvt-to-ifc-params.txt``).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import needs_schema                              # noqa: E402
from rvt.convert import rvt_to_ifc as R2I                       # noqa: E402
from rvt.convert import modify_family as MFAM                  # noqa: E402
from rvt.convert.param_carrier import carrier_for_param        # noqa: E402


# ---------------------------------------------------------------------------
# the pure rule on law-shaped rows (no file needed)
# ---------------------------------------------------------------------------

_INT64 = "autodesk.spec:spec.int64-2.0.0"
_STRING = "autodesk.spec:spec.string-2.0.0"
_LENGTH = "autodesk.spec.aec:length-1.0.0"
_POTENTIAL = "autodesk.spec.aec.electrical:potential-1.0.0"
_CURRENT = "autodesk.spec.aec.electrical:current-1.0.0"


@pytest.mark.parametrize("row, def_class, spec, want", [
    # the law: class decides, no spec at all
    ({"m_int": 42, "m_value": 0.0, "m_str": ""}, "ParamDefInt", "", 42),
    ({"m_int": 0, "m_value": 0.0, "m_str": ""}, "ParamDefInt", "", 0),
    ({"m_int": 0, "m_value": 0.0, "m_str": ""}, "ParamDefString", "", None),   # not 0.0
    ({"m_int": 0, "m_value": 0.0, "m_str": "DP-1"}, "ParamDefString", "", "DP-1"),
    # pre-law files: a ParamDefValue typed by spec -- unchanged
    ({"m_int": 42, "m_value": 0.0, "m_str": ""}, "ParamDefValue", _INT64, 42),
    ({"m_int": 0, "m_value": 0.0, "m_str": ""}, "ParamDefValue", _STRING, None),
    ({"m_int": 0, "m_value": 0.0, "m_str": "MLO"}, "ParamDefValue", _STRING, "MLO"),
    # measurable doubles: spec-converted exactly as before
    ({"m_int": 0, "m_value": 2.0, "m_str": ""}, "ParamDefValue", _LENGTH, 0.6096),      # ft -> m
    ({"m_int": 0, "m_value": 480.0 / 0.3048 ** 2, "m_str": ""}, "ParamDefValue", _POTENTIAL, 480.0),
    ({"m_int": 0, "m_value": 225.0, "m_str": ""}, "ParamDefValue", _CURRENT, 225.0),   # amps as-is
    # a class the rule does not name (foreign family) that stores text keeps its text
    ({"m_int": 0, "m_value": 0.0, "m_str": "http://x"}, "ParamDefURL", "", "http://x"),
])
def test_param_value_decides_by_class_first_spec_second(row, def_class, spec, want):
    assert R2I._param_value(row, def_class, spec) == want


def test_one_shared_rule_not_a_copy():
    """modify_family's inventory and rvt_to_ifc's contract call the SAME
    function -- the fork that caused #355 cannot reopen silently."""
    assert MFAM.carrier_for_param is R2I.carrier_for_param is carrier_for_param


# ---------------------------------------------------------------------------
# a family built under the law, read through the contract reader itself
# ---------------------------------------------------------------------------

def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=225, spaces=42,
                                   voltage="208Y/120", mcb=True,
                                   mounting="surface", panel_name="X")
        return True
    except Exception:                                          # noqa: BLE001
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")


@pytest.fixture(scope="module")
def law_rfa(tmp_path_factory):
    """A panelboard .rfa generated NOW (so it carries ParamDefString /
    ParamDefInt definitions per the storage-class law)."""
    from rvt.famgen import factory as F
    prod = F.make_panelboard(mains_a=225, spaces=42, voltage="208Y/120", mcb=True,
                             mounting="surface", panel_name="DP-1")
    path = str(tmp_path_factory.mktemp("law") / "panel_225a.rfa")
    rep = prod.write(path, validate=False, provenance=False)
    assert rep["verify"]["ok"], rep
    return path


@needs_schema
@needs_catalog
def test_family_contract_reads_integers_and_texts_of_a_law_built_family(law_rfa):
    """The exact #355 symptom, on a real file: the family document's tagging
    contract (what an rvt -> ifc export writes into the property set)
    carries NumberOfCircuits / Phases / Wires as integers -- not 0.0 -- and
    the texts as texts; the spec-driven doubles are untouched."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex(law_rfa)
    # the law really is in force on this file: class-typed, no spec
    defs = {cap: (cls, spec) for cap, cls, spec in R2I._family_param_defs(idx, 0).values()}
    assert defs["NumberOfCircuits"] == ("ParamDefInt", "")
    assert defs["PanelName"] == ("ParamDefString", "")
    assert defs["BusRating"][0] == "ParamDefValue" and "electrical:current" in defs["BusRating"][1]
    contract, src = R2I._family_contract(idx, 0, None)
    assert src and "type table" in src[0]
    assert contract["NumberOfCircuits"] == 42 and isinstance(contract["NumberOfCircuits"], int)
    assert contract["Phases"] == 3 and contract["Wires"] == 4
    assert contract["PanelName"] == "DP-1"
    assert contract["MainsType"] == "MCB"
    assert contract["Manufacturer"] == "Eaton"                 # built-in text
    assert contract["BusRating"] == 225.0                      # amps as-is
    assert contract["Voltage"] == 208.0                        # internal -> V
    assert abs(contract["Width"] - 0.508) < 1e-6               # ft -> m
    # nothing the constructor FILLED degraded to the old tell-tale float 0.0.
    # (A blank category-standard parameter, #601, IS 0.0 on purpose: a fact
    # nobody supplied is an honest blank, not a guessed value -- so the check
    # is over the parameters that carry values, not over every key.)
    filled = {k: v for k, v in contract.items()
              if k in ("NumberOfCircuits", "Phases", "Wires", "PanelName",
                       "MainsType", "MainsRating", "BusRating", "Voltage",
                       "ShortCircuitRatingkA", "NeutralRating", "Mounting",
                       "Manufacturer", "Width", "Height", "Depth")}
    assert [k for k, v in filled.items() if isinstance(v, float) and v == 0.0] == []


# ---------------------------------------------------------------------------
# end to end: prompt -> .rvt (a placed generated panel) -> .ifc, read back
# ---------------------------------------------------------------------------

PINNED_2026 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
needs_pinned = pytest.mark.skipif(not os.path.isfile(PINNED_2026),
                                  reason="bundled genesis base missing")


@needs_schema
@needs_catalog
@needs_pinned
def test_rvt_to_ifc_export_writes_integer_and_text_properties(tmp_path):
    """The public path that reaches _param_value: a front-door prompt job
    places OUR generated panelboard on the bundled base, convert_rvt_to_ifc
    exports it, and the IFC property set -- read back by the stdlib IFC
    reader the product ships -- says NumberOfCircuits = 42 as an IfcInteger
    and PanelName as an IfcLabel, never IfcReal(0.)."""
    import rvt.frontdoor as FD
    from rvt.convert.rvt_to_ifc import convert_rvt_to_ifc
    from rvt.ifc import steplite
    job = FD.author(prompt="an electrical room with 1 panel", out=str(tmp_path / "job"),
                    no_handoff=True)
    assert job.ok, (job.status, job.errors)
    rvt_path = job.manifest["build"]["files"]["combined"]["path"]
    out = str(tmp_path / "room.ifc")
    rec = convert_rvt_to_ifc(rvt_path, out, out_dir=str(tmp_path / "x"), roundtrip=False)
    assert rec["deliverables"].get("ifc"), rec.get("errors")
    (eq,) = rec["equipment"]
    assert eq["contract"]["NumberOfCircuits"] == 42 and eq["contract"]["PanelName"] == eq["tag"]
    f = steplite.open(out)
    (board,) = f.by_type("IfcElectricDistributionBoard")
    typed = {pr.Name: (pr.NominalValue.is_a(), pr.NominalValue.wrappedValue)
             for pr in f.by_type("IfcPropertySingleValue")}
    assert typed["NumberOfCircuits"] == ("IfcInteger", 42)
    assert typed["Phases"] == ("IfcInteger", 3)
    assert typed["PanelName"] == ("IfcLabel", eq["tag"])
    assert typed["MainsType"][0] == "IfcLabel"
    # and the pset reader a consumer would use agrees
    props = {k: v for ps in steplite.get_psets(board).values() for k, v in ps.items()}
    assert props["NumberOfCircuits"] == 42 and props["PanelName"] == eq["tag"]
