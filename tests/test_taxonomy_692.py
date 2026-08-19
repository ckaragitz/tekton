"""#692 slice 1 -- the MEP taxonomy and vendor directory are TABLES that stay honest:

* every taxonomy row's category resolves through ``skeleton._resolve_category`` and has a
  standard-parameter table in ``standards.py``;
* every catalog-lane row has an importable builder AND a facts line the catalog really holds;
* archetype rows degrade gracefully while ``rvt.famgen.archetypes`` (#674) is absent and light
  up when it is present -- probed, never imported unconditionally;
* every facts claim in the vendor directory loads, is the vendor's own, matches the famspec
  kind the taxonomy builds through, and every line the catalog holds is claimed exactly once;
* neither table carries a dimension (the #685 line: names yes, member data no);
* the ``make_family.py taxonomy|vendors`` verbs print the tables and their ``--check`` gates.
"""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import types

import pytest

from rvt.famgen import catalog, skeleton, standards, taxonomy as TX, vendors as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE_FAMILY = os.path.join(ROOT, "tools", "make_family.py")


# --------------------------------------------------------------------------- taxonomy

def test_taxonomy_gate_is_clean():
    assert TX.check() == []


def test_every_row_resolves_to_a_negative_builtin_category_id():
    for row in TX.kinds():
        cid = skeleton._resolve_category(row.category)
        assert isinstance(cid, int) and cid < 0, (row.key, row.category, cid)
        assert row.revit_category[0].isupper(), row.key          # a label, not a slug


def test_every_row_has_a_standards_table():
    cats = set(standards.table()["categories"])
    for row in TX.kinds():
        assert standards.canonical_category(row.standards) in cats, (row.key, row.standards)


def test_breadth_covers_the_three_disciplines_of_the_steer():
    by = TX.by_discipline()
    for disc in ("electrical", "mechanical", "plumbing"):
        assert len(by.get(disc, ())) >= 10, (disc, len(by.get(disc, ())))
    assert set(by) <= set(TX.DISCIPLINES)


def test_catalog_rows_are_exactly_what_the_famspec_lane_builds():
    from rvt.frontdoor import famspec as FS
    cat_rows = [r for r in TX.kinds() if r.lane == "catalog"]
    assert {r.famspec[0] for r in cat_rows} == set(FS.CATALOG_KINDS)
    for row in cat_rows:
        ok, why = TX.builder_available(row)
        assert ok, (row.key, why)
        assert V.facts_lines(row.key), row.key


@pytest.mark.parametrize("text, key", [
    ("MSB", "switchboard"), ("xfmr", "transformer_dry"), ("Dry-Type Transformer", "transformer_dry"),
    ("outlet", "receptacle"), ("2x4 troffer", "troffer"), ("RTU", "rooftop_unit"),
    ("ladder tray", "cable_tray"), ("unistrut", "strut_channel"), ("FACP", "fire_alarm_control_panel"),
    ("water closet", "water_closet"), ("rpz", "backflow_preventer"), ("vfd", "variable_frequency_drive"),
])
def test_resolve_aliases(text, key):
    assert TX.resolve(text).key == key


def test_unknown_and_pending_kinds_answer_honestly():
    d = TX.describe("flux capacitor")
    assert d["known"] is False and "not a kind" in d["line"]
    p = TX.describe("diffuser")
    assert p["known"] is False and p["not_yet"] is True and "Air Terminals" in p["line"]


def test_lane_none_row_says_which_lane_is_missing():
    d = TX.describe("chiller")
    assert d["known"] and d["lane"] == "none" and d["available"] is False
    assert "Mechanical Equipment" in d["line"] and "no lane builds it yet" in d["line"]


def _with_registry(monkeypatch, keys):
    fake = types.ModuleType("rvt.famgen.archetypes")
    fake.ARCHETYPES = {k: object() for k in keys}
    monkeypatch.setitem(sys.modules, "rvt.famgen.archetypes", fake)


def test_archetype_rows_degrade_without_the_registry_and_light_up_with_it(monkeypatch):
    arch_rows = [r for r in TX.kinds() if r.archetype and not r.builder]
    assert {r.archetype for r in arch_rows} == {"cable_tray", "conduit", "wireway", "strut_channel"}
    monkeypatch.setitem(sys.modules, "rvt.famgen.archetypes", None)     # import raises ImportError
    assert TX.archetype_registry() is None
    for row in arch_rows:
        ok, why = TX.builder_available(row)
        assert not ok and "#674" in why, (row.key, why)
    assert TX.check() == []                                              # absence is not a problem
    _with_registry(monkeypatch, [r.archetype for r in arch_rows] + ["junction_box"])
    assert set(TX.archetype_registry()) >= {"cable_tray", "conduit"}
    for row in arch_rows:
        ok, why = TX.builder_available(row)
        assert ok, (row.key, why)
    assert "cable_tray" in TX.table()["available"]


def test_switchboard_is_the_one_nominal_builder_on_main():
    d = TX.describe("switchboard")
    assert d["lane"] == "archetype" and d["available"] is True
    assert d["builder"] == "rvt.ifc.intent:make_house_switchboard"


# --------------------------------------------------------------------------- vendors

def test_vendor_gate_is_clean():
    assert V.check() == []


def test_every_catalog_line_is_claimed_exactly_once_and_loads():
    claimed = [(v.key, ln.facts) for v in V.vendors() for ln in v.lines if ln.facts_held]
    assert sorted(claimed) == sorted(catalog.list_lines())
    assert len(claimed) == len(set(claimed))
    for vendor, line in claimed:
        data = catalog.load_line(vendor, line)
        assert (data["vendor"], data["line"]) == (vendor, line)


def test_facts_held_lines_build_through_the_kind_they_claim():
    for v in V.vendors():
        for ln in v.lines:
            for k in ln.kinds:
                row = TX.get(k)
                if ln.facts_held:
                    assert row.lane == "catalog", (v.key, ln.key, k)
                    assert catalog.load_line(v.key, ln.facts)["category"] == row.famspec[0]


def test_lines_for_kind_puts_facts_first_and_names_the_rest():
    pairs = V.lines_for_kind("panelboard")
    assert [ln.facts_held for _, ln in pairs][:2] == [True, True]
    assert {v.key for v, ln in pairs if ln.facts_held} == {"eaton", "square-d"}
    d = V.describe("schneider electric", kind="switchboard")
    assert d["known"] and d["facts_held"] == [] and "no sourced member data" in d["line"]
    assert V.describe("acme corp")["known"] is False


def test_neither_table_carries_a_dimension():
    """The #685 line as a structural fact: no numeric field exists on either row type."""
    for cls in (TX.Kind, V.Vendor, V.Line):
        for f in dataclasses.fields(cls):
            assert f.type not in ("float", "int", float, int), (cls.__name__, f.name)
    blob = json.dumps([TX.table(), V.table()], default=str).lower()
    for unit in (' in"', "_in", "_mm", "_ft", "inches", "kva", "amps"):
        assert unit not in blob, unit


# --------------------------------------------------------------------------- CLI verbs

def _mf(*args):
    return subprocess.run([sys.executable, MAKE_FAMILY, *args], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)


def test_make_family_taxonomy_verbs():
    r = _mf("taxonomy", "--check")
    assert r.returncode == 0 and r.stdout.rstrip().endswith("0 problems"), r.stdout[-400:]
    r = _mf("taxonomy", "--json")
    doc = json.loads(r.stdout)
    assert doc["count"] == len(TX.kinds()) and "panelboard" in doc["available"]
    r = _mf("taxonomy", "MSB")
    assert r.returncode == 0 and r.stdout.startswith("Switchboard: Electrical Equipment")
    assert _mf("taxonomy", "flux capacitor").returncode == 1


def test_make_family_vendors_verbs():
    r = _mf("vendors", "--check")
    assert r.returncode == 0 and r.stdout.rstrip().endswith("0 problems"), r.stdout[-400:]
    doc = json.loads(_mf("vendors", "--json").stdout)
    assert doc["facts_held_count"] == len(catalog.list_lines())
    r = _mf("vendors", "--kind", "transformer_dry")
    assert r.returncode == 0 and "FACTS: sentinel-g-transformers" in r.stdout
    assert _mf("vendors", "nobody-inc").returncode == 1
