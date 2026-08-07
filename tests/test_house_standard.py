"""Tests for rvt.genesis.house_standard -- OUR default content + resource-id
dispositions (P0 gate G1 sub-gates G1b / G1c).

Covers: the catalog builds field-by-field from our tables and round-trips
byte-exact through the schema codec; it is SELF-CONTAINED (references only
OUR ids); the Autodesk resource identifiers our constructors used to emit are
GONE from the serialized bytes (only required-format tokens + our own text
remain); our names are ours (no Revit template terminology except the
required '???' project-view token); the electrical FACT tables are internally
consistent; and -- against ALL SIX Autodesk 2026 sample documents -- no
element reads >= 0.85 structurally similar to any sample element outside the
documented NO_FREE_CHOICE classes.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.genesis import house_standard as hs                       # noqa: E402

CORPUS = os.path.join(ROOT, "extracted", "rstbasicsampleproject")
HAVE_CORPUS = os.path.isdir(CORPUS)


@pytest.fixture(scope="module")
def cat():
    return hs.build_catalog(1_500_000)


@pytest.fixture(scope="module")
def cat_none():
    return hs.build_catalog(1_500_000, scrub="none")


# ---------------------------------------------------------------------------
# build / codec / self-containment
# ---------------------------------------------------------------------------

def test_catalog_builds_expected_inventory(cat):
    counts = cat.counts_by_class()
    # our authored inventory: system-family types, electrical catalog, styles,
    # phases, views, site skeleton
    for cls, n in {"BasicWallType": len(hs.WALL_TYPES), "MaterialElem": len(hs.MATERIALS),
                   "RbsVoltageType": len(hs.VOLTAGES),
                   "RbsDistributionSysType": len(hs.DISTRIBUTION_SYSTEMS),
                   "ElectricalDemandFactorDefinition": len(hs.DEMAND_FACTORS),
                   "ElectricalLoadClassification": len(hs.LOAD_CLASSIFICATIONS),
                   "RbsConduitType": len(hs.CONDUIT_TYPES),
                   "ConduitStandardType": len(hs.CONDUIT_STANDARDS),
                   "RbsWireType": len(hs.WIRE_TYPES),
                   "PhaseFilterElem": len(hs.PHASE_FILTERS),
                   "ProjectPhase": len(hs.PHASES),
                   "Level": len(hs.LEVELS),
                   "ElectricalSetting": 1, "UnitsElem": 1, "ProjectInfo": 1}.items():
        assert counts.get(cls) == n, f"{cls}: {counts.get(cls)} != {n}"
    assert len(cat.records) == len(cat.elements) == len(cat.manifest)
    assert cat.last_id - cat.start_id + 1 == len(cat.records)


def test_roundtrip_byte_exact(cat):
    rep = cat.roundtrip()
    assert rep["failed"] == 0, rep["failures"]
    assert rep["ok"] == rep["records"] == len(cat.records)


def test_self_contained_no_dangling_references(cat):
    assert cat.dangling() == []


def test_scrub_none_also_roundtrips(cat_none):
    rep = cat_none.roundtrip()
    assert rep["failed"] == 0


# ---------------------------------------------------------------------------
# G1c: resource identifiers
# ---------------------------------------------------------------------------

FORBIDDEN = ("assetlibrary_base.fbx", "SunAndSky-002", "52939_2004",
             "Actual %1!s! Load", "%1!s! Demand Factor", "%1!s! Connected Current",
             "%1!s! Connected Apparent Power", "%1!s! Estimated Demand Current",
             "%1!s! Demand Apparent Power", "<In-session")


def test_autodesk_identifiers_are_gone(cat):
    scan = cat.identifier_scan()
    strings = set(scan)
    for bad in FORBIDDEN:
        assert not any(bad in s for s in strings), f"identifier still emitted: {bad!r}"
    # nothing carries Autodesk's asset name 'Generic' as a whole string
    assert not any(s.strip().rstrip('"\'!#$%&+*/ ') == "Generic" for s in strings)
    # what MAY remain: our load labels (with the required %1!s! token), the
    # required Forge typeIds, and our own 'rev-revit...' text
    allowed_labels = set(hs.LOAD_LABEL_TEMPLATES.values())
    for s in strings:
        core = s.strip().rstrip('"\'!#$%&()*+/ ')
        assert (core in allowed_labels
                or core.startswith("autodesk.spec.")
                or core.startswith("autodesk.unit.")
                or core.lower().startswith("rev-revit")), f"unexpected identifier: {s!r}"


def test_unscrubbed_build_shows_the_identifiers_the_scrub_removes(cat_none):
    strings = set(cat_none.identifier_scan())
    assert any("assetlibrary_base.fbx" in s for s in strings)
    assert any("SunAndSky-002" in s for s in strings)
    assert any("Actual %1!s! Load" in s for s in strings)


def test_disposition_table_is_complete():
    ids = {d["id"] for d in hs.RESOURCE_ID_DISPOSITIONS}
    for required in ("material-asset-descriptor", "view-render-assets", "load-class-labels",
                     "formatmessage-token", "forge-typeids", "site-location-defaults",
                     "sun-defaults", "phase-terminology", "view-terminology",
                     "project-view-name-token", "system-family-name", "builtin-enum-ids",
                     "font-names", "partatom-namespace", "revit-build-string",
                     "formats-latest-schema", "save-unit-signature-banner"):
        assert required in ids, required
    for d in hs.RESOURCE_ID_DISPOSITIONS:
        for k in ("id", "what", "where", "count", "disposition", "action"):
            assert k in d and d[k], (d.get("id"), k)
        assert d["disposition"].split()[0] in ("drop", "replace", "required", "counsel"), d
    assert len(hs.CONSTRUCTOR_DIFFS) >= 8
    for c in hs.CONSTRUCTOR_DIFFS:
        assert c["file"] and c["change"]


# ---------------------------------------------------------------------------
# G1b: our values are ours
# ---------------------------------------------------------------------------

REVIT_TEMPLATE_NAMES = {
    "{3D}", "Level 1", "Level 2", "Existing", "New Construction",
    "Show All", "Show Previous Phase", "Show Previous + New", "Show Previous + Demo",
    "Show Demo + New", "Show New", "Show Complete", "<In-session, Still>",
    "Basic Wall", "Generic - 200mm", "Interior - Partition", "Exterior - Brick on CMU",
    "Lighting", "Power", "HVAC", "Receptacles", "Motor", "Spare", "Other",
}


def test_names_are_ours(cat):
    for m in cat.manifest:
        name = m.get("name") or ""
        assert name not in REVIT_TEMPLATE_NAMES, (m["class"], name)
    names = " ".join(m.get("name") or "" for m in cat.manifest)
    assert "GEN " in names                       # our house prefix appears
    # the required project-view token stays exactly '???'
    proj = [m for m in cat.manifest if m["class"] == "DBViewProject"]
    assert proj and proj[0]["name"] == "???"


def test_electrical_facts_self_consistent():
    for v in hs.VOLTAGES:            # ANSI C84.1 Range A = +-5 %
        assert abs(v["min"] - round(v["nominal"] * 0.95, 1)) < 1e-9
        assert abs(v["max"] - round(v["nominal"] * 1.05, 1)) < 1e-9
    dem = {d["key"]: d for d in hs.DEMAND_FACTORS}
    # NEC 220.44 receptacle threshold = 10 kVA in internal power units
    assert abs(dem["receptacle"]["rows"][0][1] - 10000.0 * hs.VA_TO_INTERNAL) < 1e-6
    assert dem["receptacle"]["rule"] == hs.RULE_LOAD
    assert dem["motor"]["rule"] == hs.RULE_COUNT and dem["motor"]["rows"][0][2] == 1.25
    # NEC Ch.9 Table 4/2: EMT 1/2" ID 0.622, bend radius 4"
    emt = next(s for s in hs.CONDUIT_STANDARDS if s["key"] == "emt")
    rows = {r[0]: r for r in hs.conduit_size_rows(emt)}
    assert rows[0.5][1] == 0.622 and rows[0.5][3] == 4.0
    # phase-filter presentation vectors are 7-slot with unused slots 0/1/6
    for _n, _d, pres in hs.PHASE_FILTERS:
        assert len(pres) == 7 and pres[0] == pres[1] == pres[6] == 0
        assert set(pres) <= {0, 1, 2}


def test_units_registry_typeid_shape(cat):
    fmts = hs.UNIT_FORMATS_IMPERIAL
    pat_spec = re.compile(r"^autodesk\.spec\.[a-z.]+:[A-Za-z0-9.]+-\d+\.\d+\.\d+$")
    pat_unit = re.compile(r"^autodesk\.unit\.(unit|symbol):[A-Za-z0-9.]+-\d+\.\d+\.\d+$")
    for spec, unit, sym, acc in fmts:
        assert pat_spec.match(spec), spec
        assert pat_unit.match(unit), unit
        assert sym is None or pat_unit.match(sym), sym
        assert acc > 0
    # manifest count label == the emitted format count (audit error B6 class)
    reg = [m for m in cat.manifest if m.get("kind") == "units-registry"]
    assert reg and reg[0]["params"]["entries"] == len(fmts)


@pytest.mark.skipif(not HAVE_CORPUS, reason="extracted sample corpus not present")
def test_unit_typeids_present_in_corpus():
    """Every spec/unit/symbol typeId we key on occurs in the 2026 corpus."""
    from rvt.container import open_rvt
    from rvt.mutate import Document
    vocab = set()
    for f in ("samples/rstbasicsampleproject.rvt", "samples/rmebasicsampleproject.rvt"):
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        with open_rvt(p) as fh:
            b = fh.inflate("Global/Latest", 0)
        for m in re.finditer(rb"(?:[\x20-\x7e]\x00){10,}", b):
            for tok in re.findall(r"autodesk\.[a-z.]+:[A-Za-z0-9_.-]+",
                                  m.group().decode("utf-16-le")):
                vocab.add(tok)
    for proj in ("rstbasicsampleproject", "rmebasicsampleproject"):
        try:
            d = Document.load(proj)
        except Exception:
            continue
        v = d.value(d.ids_of_class("UnitsElem")[0])
        for e in v["m_units"]["m_formatOptionsMap"]:
            vocab.add(e["first"]["m_typeId"])
            vocab.add(e["second"]["m_unitTypeId"]["m_typeId"])
            vocab.add(e["second"]["m_symbolTypeId"]["m_typeId"])
    if not vocab:
        pytest.skip("no corpus vocabulary available")
    for lst in (hs.UNIT_FORMATS_IMPERIAL, hs.UNIT_FORMATS_METRIC):
        for spec, unit, sym, _acc in lst:
            for s in (spec, unit, sym):
                if s is None:
                    continue
                assert s in vocab, f"typeId not in the 2026 corpus: {s}"


# ---------------------------------------------------------------------------
# G1b: the six-sample similarity gate (structural similarity < 0.85 unless
# the class leaves no free choice)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_CORPUS, reason="extracted sample corpus not present")
def test_no_similarity_violation_against_all_six_samples(cat):
    rep = hs.similarity_report(cat)
    assert rep["samples_used"], "no sample document could be loaded"
    assert rep["violations"] == [], rep["violations"]
    for o in rep["over_threshold"]:
        assert o["class"] in hs.NO_FREE_CHOICE
        assert o["status"] == "no-free-choice"
    # the value-bearing classes the audit named must now be well clear
    cm = rep["class_max"]
    for cls, ceiling in {"ElectricalSetting": 0.6, "ElectricalLoadClassification": 0.6,
                         "PhaseFilterElem": 0.6, "ProjectPhase": 0.6,
                         "MaterialElem": 0.6, "SunAndShadowSettings": 0.6}.items():
        assert cm.get(cls, 0.0) < ceiling, (cls, cm.get(cls))
