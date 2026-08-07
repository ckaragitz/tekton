"""Tests for src/rvt/inventory.py (name resolution + seed inventory) and
tools/seed_audit.py (seed coverage report)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from rvt import inventory as inv  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples")
CORPUS = os.path.join(ROOT, "extracted")


def _have_corpus(name: str) -> bool:
    return os.path.isdir(os.path.join(CORPUS, name, "_index")) or os.path.isdir(
        os.path.join(CORPUS, name))


pytestmark = pytest.mark.skipif(
    not (_have_corpus("rstbasicsampleproject") and _have_corpus("rmebasicsampleproject")),
    reason="research corpus (extracted/) absent")


@pytest.fixture(scope="module")
def rst():
    from rvt.mutate import Document
    return Document.load("rstbasicsampleproject")


@pytest.fixture(scope="module")
def rme():
    from rvt.mutate import Document
    return Document.load("rmebasicsampleproject")


# --------------------------------------------------------------------------
# built-in category table
# --------------------------------------------------------------------------
def test_builtin_table_anchors():
    assert inv.category_name(None, -2001040) == "OST_ElectricalEquipment"
    assert inv.category_label(None, -2001040) == "Electrical Equipment"
    assert inv.category_name(None, -2000011) == "OST_Walls"
    assert inv.category_name(None, -2000280) == "OST_TitleBlocks"
    assert inv.category_name(None, -2008010) == "OST_DuctFitting"
    assert inv.category_source(-2001040) == "builtin-verified"
    # an id we never claimed comes back tagged, never invented
    assert inv.category_name(None, -2999999).startswith("OST_?(")
    assert inv.category_source(-2999999) == "unknown"
    # no id appears in both tables
    assert not (set(inv.BUILTIN_CATEGORIES_VERIFIED)
                & set(inv.BUILTIN_CATEGORIES_ASSUMED))


# --------------------------------------------------------------------------
# name resolution
# --------------------------------------------------------------------------
def test_levels_named(rst):
    lv = inv.levels(rst)
    assert lv and all(l["name"] for l in lv)
    names = {l["name"] for l in lv}
    assert "Level 1" in names or any("Level" in n for n in names)


def test_element_name_level_and_type(rst):
    lv = inv.levels(rst)[0]
    assert inv.element_name(rst, lv["id"]) == lv["name"]
    wts = inv.wall_types(rst)
    assert wts
    named = [w for w in wts if w["name"]]
    assert len(named) == len(wts)                    # 100% named
    w = named[0]
    assert inv.type_name(rst, w["id"]) == w["name"]
    assert inv.element_name(rst, w["id"]) == w["name"]


def test_wall_type_thickness(rme):
    wts = {w["name"]: w for w in inv.wall_types(rme)}
    # rme German standard types: 'STB 20.0' = 20 cm concrete
    assert "STB 20.0" in wts
    t = wts["STB 20.0"]["thickness_ft"]
    assert abs(t * 304.8 - 200.0) < 1.0                # 200 mm
    assert wts["STB 20.0"]["walls_using"] > 0        # a placed specimen exists


def test_symbols_all_named_and_clones_resolved(rme):
    masters = inv.symbols(rme)
    assert masters and all(s["symbol"] for s in masters)
    assert all(s["family"] for s in masters)
    everything = inv.symbols(rme, masters_only=False)
    clones = [s for s in everything if s["is_clone"]]
    assert clones                                      # rme is clone-heavy
    assert all(s["symbol"] for s in clones)            # named via m_masterId


def test_electrical_equipment_inventory(rme):
    rows = inv.symbols(rme, inv.OST_ELECTRICAL_EQUIPMENT)
    assert rows
    byname = {(r["family"], r["symbol"]): r for r in rows}
    key = ("M_Lighting and Appliance Panelboard - 480V MCB - Surface", "400 A")
    assert key in byname, sorted(byname)[:5]
    pnl = byname[key]
    assert pnl["category"] == "OST_ElectricalEquipment"
    assert pnl["category_label"] == "Electrical Equipment"
    assert pnl["hosting_pattern"] == "face"             # rme panels are face-hosted
    assert pnl["placed_instances"] >= 1
    xfmr = [r for r in rows if (r["family"] or "").startswith("M_Dry Type Transformer")]
    assert xfmr and any(r["hosting_pattern"] == "free" for r in xfmr)


def test_instance_name_uses_panel_name_param(rme):
    inst = rme.ids_of_class("FamilyInstance")
    # a panel instance carries RBS_ELEC_PANEL_NAME (-1140078)
    found = [inv.element_name(rme, i) for i in inst[:300]]
    assert any(n for n in found)
    assert all(isinstance(n, str) or n is None for n in found)


def test_inventory_shape(rme):
    d = inv.inventory(rme)
    for k in ("levels", "wall_types", "symbols", "titleblocks", "view_templates",
              "phases", "stats"):
        assert k in d
    st = d["stats"]
    assert st["wall_types_named_pct"] == 100.0
    assert st["symbols_named_pct"] == 100.0
    assert d["titleblocks"] and d["titleblocks"][0]["family"] == "A0 metric"
    assert {"Existing", "New Construction"} <= {p["name"] for p in d["phases"]}
    assert d["view_templates"]
    json.dumps(d, default=str)                         # JSON-serialisable


@pytest.mark.parametrize("proj", ["rmebasicsampleproject", "rstbasicsampleproject",
                                  "racbasicsampleproject"])
def test_resolution_stats_all_samples(proj):
    if not _have_corpus(proj):
        pytest.skip("corpus absent")
    s = inv.resolution_stats(proj)
    assert s["levels_named"] == s["levels"]
    assert s["wall_types_named"] == s["wall_types"]
    assert s["symbols_master_named"] == s["symbols_master"]
    assert s["symbols_master_family_named"] == s["symbols_master"]
    assert s["symbol_clones_named_via_master"] == s["symbol_clones"]


# --------------------------------------------------------------------------
# seed_audit tool
# --------------------------------------------------------------------------
def _load_seed_audit():
    p = os.path.join(ROOT, "tools", "seed_audit.py")
    spec = importlib.util.spec_from_file_location("seed_audit", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SPEC = os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room", "room-spec.json")


@pytest.mark.skipif(not os.path.exists(SPEC), reason="job spec absent")
def test_seed_audit_rme_against_electrical_room():
    sa = _load_seed_audit()
    spec = json.load(open(SPEC))
    rep = sa.audit("rmebasicsampleproject", spec)
    cov = rep["coverage"]
    assert cov["verdict"] in ("SEED READY", "SEED USABLE WITH GAPS", "SEED NOT READY")
    # panelboards resolve to the panelboard families, MCB vs MLO respected
    eq = {r["want"]: r for r in cov["equipment"] if r.get("seed")}
    hg = eq["Eaton Pow-R-Line 4 (style) - 400A MB - 42 space"]
    assert "480V MCB" in hg["seed"]
    lq = eq["Eaton Pow-R-Line 1 (style) - 225A MLO - 42 space"]
    assert "MLO" in lq["seed"]
    xf = eq["45 kVA dry-type 480D-208Y/120"]
    assert xf["seed"].startswith("M_Dry Type Transformer") and "45 kVA" in xf["seed"]
    # the proxy trapeze hangers are flagged, not silently dropped
    assert any(r["status"] == "NEEDS-FAMILY" for r in cov["equipment"])
    # wall type: no CMU name in rme, but the 200 mm STB type matches by thickness
    wt = cov["wall_types"][0]
    assert wt["item"] == "Painted CMU 8in"
    assert wt["seed"] == "STB 20.0"
    assert wt["status"].startswith("THICKNESS-ONLY")
    # every non-OK row carries an actionable fix
    for section in ("levels", "wall_types", "doors", "equipment", "other"):
        for r in cov[section]:
            if r["status"] not in ("OK", "INFO"):
                assert r.get("fix"), r


def test_seed_audit_missing_kind_gives_fix():
    sa = _load_seed_audit()
    syms = []      # an empty seed: nothing loaded
    rows = sa.audit_equipment({"equipment": [
        {"kind": "panelboard", "name": "P1", "typeName": "480V 400A MB"},
        {"kind": "proxy", "name": "H1", "typeName": "trapeze"}]}, syms)
    st = {r["kind"]: r for r in rows}
    assert st["panelboard"]["status"] == "MISSING"
    assert "load a panelboard family" in st["panelboard"]["fix"]
    assert st["proxy"]["status"] == "NEEDS-FAMILY"


def test_seed_audit_wall_missing_when_no_types():
    sa = _load_seed_audit()
    rows = sa.audit_walls({"walls": [{"id": "w", "type": "Painted CMU 8in",
                                       "thickness": 0.2}]}, [])
    assert rows[0]["status"] == "MISSING"
    assert "PLACE one wall" in rows[0]["fix"]
