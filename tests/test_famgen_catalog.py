"""Tests for the manufacturer FACTS STORE (src/rvt/famgen/facts) and its
loader (rvt.famgen.catalog).

The store is DATA that drives family generation: published dimensional /
rating facts, each with a source and a per-field provenance flag. These
tests guard the schema, the honesty rules (every field flagged; nulls never
silently zero-filled; 'assumed' distinguishable from 'fact') and the
selector API. They do not touch any other rvt module.

Run: .venv/bin/python -m pytest tests/test_famgen_catalog.py -q
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rvt.famgen import catalog as cat

# ---------------------------------------------------------------------------
# the DONE set: the four product families named by the stream + generics
# ---------------------------------------------------------------------------

REQUIRED_LINES = {
    ("eaton", "pow-r-line-panelboards"),      # (1) Eaton Pow-R-Line panelboards
    ("square-d", "nq-nf-iline-panelboards"),  # (2) Square D NQ / NF / I-Line
    ("eaton", "dry-type-transformers"),        # (3) dry-type transformers (Eaton)
    ("hps", "sentinel-g-transformers"),        # (3) ... and one other vendor
    ("lithonia", "blt-led-troffer"),           # (4) recessed LED troffer
    ("lithonia", "ldn6-led-downlight"),        # (4) plenum-rated recessed downlight
    ("generic", "devices-and-mounting"),       # (5) generic device facts
}

URL_RE = re.compile(r"^https?://", re.I)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def docs():
    return cat.all_lines()


# ---------------------------------------------------------------------------
# presence / license notes
# ---------------------------------------------------------------------------

def test_facts_dir_and_required_lines_present():
    assert cat.facts_dir().is_dir()
    present = set(cat.list_lines())
    missing = REQUIRED_LINES - present
    assert not missing, f"missing facts records: {sorted(missing)}"


def test_license_notes_present_and_states_the_basis():
    notes = cat.facts_dir() / "LICENSE_NOTES.md"
    assert notes.is_file()
    text = notes.read_text(encoding="utf-8")
    # facts-not-expression basis and the no-files rule must both be stated
    assert "Feist" in text
    assert "fact" in text and "assumed" in text
    assert re.search(r"never stores or redistributes.*\.rfa", text, re.I | re.S)
    assert re.search(r"photometr", text, re.I)


# ---------------------------------------------------------------------------
# schema validity (every record, via the loader's own validator)
# ---------------------------------------------------------------------------

def test_every_record_passes_schema_validation(docs):
    for (v, l), doc in docs.items():
        probs = cat.validate_line(doc)
        assert probs == [], f"{v}/{l}: {probs}"


def test_top_level_shape(docs):
    for (v, l), doc in docs.items():
        assert doc["schema_version"] == 1
        assert doc["vendor"] == v and doc["line"] == l
        assert doc["category"] in {"panelboard", "transformer", "luminaire", "device"}
        assert isinstance(doc["collection_posture"], dict)
        assert doc["collection_posture"].get("summary")
        assert "license_note" in doc


# ---------------------------------------------------------------------------
# sources: every source cites url / doc / accessed and a verification level
# ---------------------------------------------------------------------------

def test_sources_carry_url_doc_accessed(docs):
    for (v, l), doc in docs.items():
        assert doc["sources"], f"{v}/{l}: no sources"
        for sid, s in doc["sources"].items():
            assert URL_RE.match(s["url"]), f"{v}/{l} {sid}: bad url {s['url']!r}"
            assert s["doc"], f"{v}/{l} {sid}: empty doc"
            assert s["verification"] in cat.VERIFICATION_LEVELS
            # deliberately-not-fetched primaries may have accessed=None,
            # anything we actually READ (VERIFIED) must carry a real date
            if s["verification"] == "VERIFIED":
                assert DATE_RE.match(str(s["accessed"])), \
                    f"{v}/{l} {sid}: VERIFIED source needs accessed date"


def test_at_least_one_verified_source_per_manufacturer_line(docs):
    """The panelboard / transformer / troffer lines must each rest on at
    least one document we actually read (VERIFIED)."""
    must_have_verified = {
        ("eaton", "pow-r-line-panelboards"), ("square-d", "nq-nf-iline-panelboards"),
        ("eaton", "dry-type-transformers"), ("hps", "sentinel-g-transformers"),
        ("lithonia", "blt-led-troffer"),
    }
    for key in must_have_verified:
        levels = {s["verification"] for s in docs[key]["sources"].values()}
        assert "VERIFIED" in levels, f"{key}: no VERIFIED source"


# ---------------------------------------------------------------------------
# variants: per-variant source + provenance flag on EVERY tracked field
# ---------------------------------------------------------------------------

def test_variant_sources_have_url_doc_accessed(docs):
    for (v, l), doc in docs.items():
        for var in doc["variants"]:
            s = var["source"]
            assert URL_RE.match(s["url"]), f"{v}/{l} {var['model']}: url"
            assert s["doc"], f"{v}/{l} {var['model']}: doc"
            assert "accessed" in s


def test_every_leaf_field_has_a_provenance_flag(docs):
    for (v, l), doc in docs.items():
        for var in doc["variants"]:
            fp = var["field_provenance"]
            for path in cat.leaf_paths(var):
                assert fp.get(path) in cat.PROVENANCE_FLAGS, \
                    f"{v}/{l} {var['model']}: no fact/assumed flag on {path}"


def test_provenance_flags_are_only_fact_or_assumed(docs):
    for (v, l), doc in docs.items():
        for var in doc["variants"]:
            for path, flag in var["field_provenance"].items():
                assert flag in ("fact", "assumed"), f"{v}/{l} {var['model']} {path}={flag}"


def test_dims_in_has_w_h_d_keys(docs):
    for (v, l), doc in docs.items():
        for var in doc["variants"]:
            for axis in ("w", "h", "d"):
                assert axis in var["dims_in"], f"{v}/{l} {var['model']}: dims_in.{axis}"


def test_store_contains_both_facts_and_assumed_values(docs):
    """Sanity: the store is not all one flag -- it distinguishes verified
    figures from inferred/unsourced ones."""
    seen = set()
    for doc in docs.values():
        for var in doc["variants"]:
            seen.update(var["field_provenance"].values())
    assert seen == {"fact", "assumed"}


def test_null_values_are_never_flagged_as_fact(docs):
    """A NOT-SOURCED (null) figure must be 'assumed' or otherwise not a
    'fact' -- we never claim a fact we do not have."""
    for (v, l), doc in docs.items():
        for var in doc["variants"]:
            for path in cat.leaf_paths(var):
                if cat._get_path(var, path) is None:
                    assert var["field_provenance"].get(path) != "fact", \
                        f"{v}/{l} {var['model']}: null {path} flagged fact"


# ---------------------------------------------------------------------------
# selectors
# ---------------------------------------------------------------------------

def test_get_variant_by_model_and_alias():
    v = cat.get_variant("eaton", "pow-r-line-panelboards", model="PRL1a")
    assert v["model"] == "PRL1a"
    # alias resolution
    v = cat.get_variant("eaton", "pow-r-line-panelboards", model="Pow-R-Line Xpert 3X")
    assert v["model"] == "PRL3X"
    v = cat.get_variant("lithonia", "blt-led-troffer", model="2BLT4")
    assert v["model"] == "2BLT4-38W"


def test_get_variant_by_rating():
    v = cat.get_variant("eaton", "dry-type-transformers", kva=75)
    assert v["ratings"]["kva"] == 75 and v["ratings"]["frame"] == "FR942"
    v = cat.get_variant("eaton", "dry-type-transformers", kva=112.5)
    assert v["dims_in"]["h"] == 51.00


def test_range_selector_matches_inside_a_two_number_range():
    # PRL1a bus_current_range_a = [100, 600]
    hits = cat.find_variants("eaton", "pow-r-line-panelboards", bus_current_range_a=225)
    assert [h["model"] for h in hits] == ["PRL1a"]
    assert cat.find_variants("eaton", "pow-r-line-panelboards", bus_current_range_a=800) == []


def test_find_variants_multi_and_dotted_selector():
    hits = cat.find_variants("square-d", "nq-nf-iline-panelboards", voltage_max_ac_v=600)
    assert {h["model"] for h in hits} == {"NF", "I-Line"}
    hits = cat.find_variants("eaton", "dry-type-transformers",
                             **{"ratings.temp_rise_c": 150, "kva": 150})
    assert [h["model"] for h in hits] == ["V48M28T4916"]


def test_get_variant_raises_on_zero_or_ambiguous():
    with pytest.raises(cat.CatalogError):
        cat.get_variant("eaton", "dry-type-transformers")            # 9 candidates
    with pytest.raises(cat.CatalogError):
        cat.get_variant("eaton", "dry-type-transformers", kva=99)    # none
    with pytest.raises(cat.CatalogError):
        cat.load_line("nobody", "nothing")


def test_list_lines_and_load_are_consistent():
    for v, l in cat.list_lines():
        assert cat.load_line(v, l)["line"] == l


# ---------------------------------------------------------------------------
# require(): the never-invent-a-dimension guard
# ---------------------------------------------------------------------------

def test_require_returns_sourced_value():
    v = cat.get_variant("eaton", "dry-type-transformers", kva=75)
    assert cat.require(v, "dims_in.w") == 30.50
    assert cat.require(v, "dims_in.w", fact_only=True) == 30.50


def test_require_refuses_null():
    v = cat.get_variant("lithonia", "ldn6-led-downlight", model="LDN6-35/15-CP")
    with pytest.raises(cat.CatalogError):
        cat.require(v, "dims_in.w")            # housing dims NOT SOURCED
    v500 = cat.get_variant("eaton", "dry-type-transformers", kva=500)
    with pytest.raises(cat.CatalogError):
        cat.require(v500, "dims_in.h")         # 'Contact Eaton' row - null


def test_require_fact_only_rejects_assumed():
    v = cat.get_variant("hps", "sentinel-g-transformers", kva=30)
    assert cat.field_provenance(v, "dims_in.w") == "assumed"
    with pytest.raises(cat.CatalogError):
        cat.require(v, "dims_in.w", fact_only=True)
    assert cat.require(v, "dims_in.w") == 25.8   # allowed when facts not demanded


def test_assumed_and_unsourced_helpers():
    v = cat.get_variant("lithonia", "blt-led-troffer", model="2BLT4-38W")
    assumed = cat.assumed_fields(v)
    assert "ratings.efficacy_lm_per_w" in assumed      # derived by us
    assert "dims_in.w" not in assumed                   # read directly
    assert cat.unsourced_fields(v) == []
    ldn = cat.get_variant("lithonia", "ldn6-led-downlight", model="LDN6-35/15-CP")
    assert set(cat.unsourced_fields(ldn)) >= {"dims_in.w", "dims_in.h", "dims_in.d"}


# ---------------------------------------------------------------------------
# units + reports
# ---------------------------------------------------------------------------

def test_dims_feet_converts_and_preserves_null():
    v = cat.get_variant("eaton", "dry-type-transformers", kva=15)
    ft = cat.dims_feet(v)
    assert ft["w"] == pytest.approx(21.88 / 12.0)
    assert ft["h"] == pytest.approx(28.00 / 12.0)
    ldn = cat.get_variant("lithonia", "ldn6-led-downlight", model="LDN6-35/15-CP")
    assert cat.dims_feet(ldn) == {"w": None, "h": None, "d": None}   # never zero-filled


def test_provenance_report_counts():
    rep = cat.provenance_report("eaton", "dry-type-transformers")
    assert rep["variants"] == 9
    assert rep["fields_fact"] > rep["fields_assumed"] >= 0
    assert rep["fields_missing_flag"] == 0
    ldn = cat.provenance_report("lithonia", "ldn6-led-downlight")
    assert ldn["fields_fact"] == 0 and ldn["fields_assumed"] > 0   # honest all-assumed record


def test_validate_all_clean_and_validator_catches_bad_records():
    for key, probs in cat.validate_all().items():
        assert probs == [], f"{key}: {probs}"
    # a synthetic broken record must be flagged
    bad = {
        "vendor": "x", "line": "y",
        "sources": {"S1": {"url": "http://a", "doc": "d", "accessed": "2026-08-03",
                           "verification": "MAYBE"}},           # invalid level
        "variants": [{"model": "M", "ratings": {"r": 1}, "dims_in": {"w": 1},
                      "source": {"url": "u"},                    # missing doc/accessed
                      "field_provenance": {}}],                  # no flags
    }
    probs = cat.validate_line(bad)
    joined = " | ".join(probs)
    assert "missing top-level" in joined
    assert "verification" in joined
    assert "no provenance flag" in joined
    assert "dims_in missing" in joined


# ---------------------------------------------------------------------------
# domain sanity on the flagship facts (guards against silent data drift)
# ---------------------------------------------------------------------------

def test_eaton_panelboard_box_family_facts():
    doc = cat.load_line("eaton", "pow-r-line-panelboards")
    lf = doc["line_facts"]
    assert lf["box_width_standard_in"]["value"] == 20.00
    assert lf["box_depth_standard_in"]["value"] == 5.75
    assert lf["box_width_standard_in"]["provenance"] == "fact"
    p1x = cat.get_variant("eaton", "pow-r-line-panelboards", model="PRL1X")
    heights = {row[1] for cfg in p1x["options"]["box_height_by_circuits"] for row in cfg["rows"]}
    assert heights <= {36.00, 48.00, 60.00, 72.00, 90.00}


def test_eaton_transformer_frames_and_weights():
    doc = cat.load_line("eaton", "dry-type-transformers")
    fr = doc["frames"]["table"]
    assert fr["FR942"] == {"h_in": 43.00, "w_in": 30.50, "d_in": 24.00,
                           "h_mm": 1092, "w_mm": 775, "d_mm": 610, "drawing": 5}
    v = cat.get_variant("eaton", "dry-type-transformers", kva=75)
    assert v["ratings"]["weight_lb"] == 570
    # frame dims and variant dims agree
    assert (v["dims_in"]["h"], v["dims_in"]["w"], v["dims_in"]["d"]) == (
        fr["FR942"]["h_in"], fr["FR942"]["w_in"], fr["FR942"]["d_in"])


def test_photometry_is_referenced_never_stored():
    """No .ies payload anywhere in the store; luminaires reference IES by URL."""
    root = cat.facts_dir()
    assert not list(root.rglob("*.ies"))
    assert not list(root.rglob("*.IES"))
    blt = cat.load_line("lithonia", "blt-led-troffer")
    ref = blt["line_facts"]["photometry_reference"]
    assert ref["provenance"] == "fact"
    assert re.search(r"URL", str(ref["value"]))
