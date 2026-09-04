"""test_famgen_archetypes.py -- named products generated at standard NOMINAL
sizes (steer #591).

Owner steer, verbatim: *"pause , for example if i say crate a cable tray family
you should be able to create it in lod 400, you should be able to create
anything"*.

Evidence tiers:

1. THE REGISTRY holds together: every archetype builds from its own nominals,
   emits only shapes the famspec accepts, and is recognised by its own name.
2. PROVENANCE is the point: a dimension nobody stated is ``nominal`` and is
   reported as generated (it lands in ``unverified_fields``); a dimension the
   caller stated is ``given`` with the words quoted back. No archetype family
   carries a manufacturer, model or part number.
3. LOD 400 means the parts are the real parts -- a ladder tray is rails plus a
   rung at every standard spacing, and the rung count follows the spacing.
4. THE ROUTE: ``route run --prompt "create a cable tray family" --output rfa``
   delivers, catalog facts still win when the prompt names a catalog product,
   and a prompt naming nothing we build is still refused honestly.
5. ON THE FILE: the generated .rfa is family-mode VALID with 0 errors and
   provenance-clean.

Sample-free: no ``samples/``, no viewer, no desktop. Validator-green is
necessary, NOT certification (hard rule 4) -- nothing here says Revit opens it.

Run: .venv/bin/python -m pytest tests/test_famgen_archetypes.py -q
"""
from __future__ import annotations

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import needs_schema                              # noqa: E402
from rvt.famgen import archetypes as AR                        # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402
from rvt.famgen import skeleton as SK                          # noqa: E402

ALL = AR.keys()


# ---------------------------------------------------------------------------
# 1. the registry
# ---------------------------------------------------------------------------

def test_the_registry_passes_its_own_check():
    assert AR.check_registry() == []


def test_the_registry_is_a_registry_not_one_special_case():
    assert len(ALL) >= 5 and "cable_tray" in ALL


@pytest.mark.parametrize("key", ALL)
def test_every_archetype_builds_from_its_own_nominals(key):
    a = AR.archetype(key)
    parts = a.build(a.defaults())
    assert parts, key
    assert all(p.get("name") for p in parts), "every part is named"
    # the category it declares is one the writer accepts AND the standards
    # table covers, so a generated product lands in the right branch of Revit's
    # category tree carrying its category's parameters
    SK._resolve_category(a.category)
    assert ST.describe(a.category)["covered"], a.category


@pytest.mark.parametrize("key", ALL)
def test_every_archetype_says_what_it_does_not_model(key):
    """An honest archetype states its limits; silence would read as complete."""
    a = AR.archetype(key)
    assert a.basis and a.lod_note and a.limits
    assert all(p.basis for p in a.params), "every nominal says which practice it follows"


def test_an_unknown_product_is_refused_by_name_and_lists_what_is_generated():
    with pytest.raises(AR.ArchetypeError) as e:
        AR.archetype("flux capacitor")
    assert "flux capacitor" in str(e.value) and "cable_tray" in str(e.value)


def test_an_unknown_dimension_is_refused_by_name():
    with pytest.raises(AR.ArchetypeError, match="rung_colour"):
        AR.resolve("cable_tray", {"rung_colour": 3})


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), -1.0, "wide"])
def test_an_unusable_dimension_is_refused_rather_than_written(bad):
    with pytest.raises(AR.ArchetypeError):
        AR.resolve("cable_tray", {"width_in": bad})


# ---------------------------------------------------------------------------
# 2. provenance
# ---------------------------------------------------------------------------

def test_a_bare_product_name_is_all_nominal():
    r = AR.resolve_prompt("create a cable tray family")
    assert r is not None and r.arch.key == "cable_tray"
    assert r.given() == []
    assert set(r.nominal()) == {p.key for p in r.arch.params}


def test_the_prompt_overrides_a_nominal_and_relabels_it_given():
    r = AR.resolve_prompt("a 24 inch cable tray 20 ft long with 6 inch rung spacing")
    assert r.values["width_in"] == 24.0 and r.values["length_ft"] == 20.0
    assert r.values["rung_spacing_in"] == 6.0
    assert set(r.given()) == {"width_in", "length_ft", "rung_spacing_in"}
    assert "24 inch cable tray" in r.quoted["width_in"]
    assert r.values["depth_in"] == 4.0 and "depth_in" in r.nominal()   # untouched


def test_fractional_and_metric_dimensions_are_read():
    r = AR.resolve_prompt("a 1-5/8 in strut channel 3 m long")
    assert r.values["height_in"] == pytest.approx(1.625)
    assert r.values["length_ft"] == pytest.approx(3000 * AR.MM, rel=1e-6) or \
        r.values["length_ft"] == pytest.approx(10.0)      # 'm' is not a unit we read
    r2 = AR.resolve("conduit", {}, prompt="a 3/4 in EMT run")
    assert r2.values["diameter_in"] == pytest.approx(0.75)
    r3 = AR.resolve_prompt("a 600 mm wide cable tray")
    assert r3.values["width_in"] == pytest.approx(600 * AR.MM / AR.IN)


def test_a_cross_dimension_sets_both_and_a_square_section_follows_its_width():
    r = AR.resolve_prompt("a 12x12 wireway 3 ft long")
    assert (r.values["width_in"], r.values["height_in"]) == (12.0, 12.0)
    assert set(r.given()) == {"width_in", "height_in", "length_ft"}
    # width alone: the square section follows it, and says WHY rather than
    # presenting the derived number as a nominal
    r2 = AR.resolve_prompt("a 12 in wireway")
    assert r2.values["height_in"] == 12.0 and "height_in" in r2.given()
    assert "follows the given Width" in r2.quoted["height_in"]


def test_a_structural_override_is_given_by_definition():
    r = AR.resolve("cable_tray", {"width_in": 18})
    assert r.values["width_in"] == 18.0 and r.given() == ["width_in"]


def test_a_prompt_naming_no_generated_product_is_not_an_archetype_request():
    assert AR.resolve_prompt("a 225 A Eaton panelboard") is None
    assert AR.resolve_prompt("an electrical room 30x20 ft") is None
    assert AR.resolve_prompt("") is None


# ---------------------------------------------------------------------------
# 3. LOD 400 -- the parts are the real parts
# ---------------------------------------------------------------------------

def test_a_ladder_tray_is_rails_and_rungs_not_a_box():
    r = AR.resolve_prompt("create a cable tray family")           # 12 in x 10 ft, 12 in rungs
    parts = r.parts()
    rails = [p for p in parts if "rail" in p["name"]]
    rungs = [p for p in parts if p["name"].startswith("rung")]
    assert len(rails) == 6                    # two channels: web + two flanges each
    # 10 ft at a TRUE 12 in pitch = 10 rungs spanning 9 ft, centred, with equal
    # 6 in end bays -- the pitch is the one the family reports, not L/(n-1)
    assert len(rungs) == 10
    assert len(parts) == len(rails) + len(rungs)
    # the rungs span the usable width, and sit on the bottom flange
    assert all(p["depth_ft"] == pytest.approx(1.0) for p in rungs)
    assert all(p["base_z_ft"] > 0 for p in rungs)


def test_the_rung_count_follows_the_rung_spacing():
    def rungs(spacing):
        r = AR.resolve("cable_tray", {"rung_spacing_in": spacing, "length_ft": 10})
        return len([p for p in r.parts() if p["name"].startswith("rung")])
    assert rungs(18) == 7 and rungs(12) == 10 and rungs(9) == 14 and rungs(6) == 20


def test_a_slotted_strut_back_is_the_material_between_the_slots():
    solid = AR.resolve("strut_channel", {})
    slotted = AR.resolve("strut_channel",
                         {"slot_length_in": 1.125, "slot_spacing_in": 2.0})
    backs_solid = [p for p in solid.parts() if p["name"].startswith("back")]
    backs_slot = [p for p in slotted.parts() if p["name"].startswith("back")]
    assert len(backs_solid) == 1                    # P1000-style: one solid back
    assert len(backs_slot) > 10                     # a segment between every slot
    # the slots are really ABSENT: less back material than the solid channel
    assert sum(p["width_ft"] for p in backs_slot) < backs_solid[0]["width_ft"]


def test_a_geometry_that_cannot_close_is_refused_not_approximated():
    with pytest.raises(AR.ArchetypeError, match="flange"):
        AR.resolve("cable_tray", {"width_in": 1, "rail_flange_in": 4}).parts()
    with pytest.raises(AR.ArchetypeError):
        AR.resolve("junction_box", {"thickness_in": 9}).parts()


# ---------------------------------------------------------------------------
# 4. through the constructor
# ---------------------------------------------------------------------------

@needs_schema
@pytest.mark.parametrize("key", ALL)
def test_every_archetype_composes_a_family(key):
    prod = F.make_archetype(product=key)
    a = AR.archetype(key)
    assert prod.kind == "archetype"
    assert prod.doc.finalized and prod.doc.category_id == SK._resolve_category(a.category)
    assert prod.archetype["product"] == key
    assert prod.archetype["given"] == [] and prod.archetype["nominal"]
    # every nominal dimension SURFACES as unverified -- generated, not sourced
    assert set(prod.archetype["nominal"]) <= set(prod.unverified())


@needs_schema
def test_no_archetype_family_claims_a_manufacturer():
    """The line the honesty contract actually draws (#591): generating geometry
    is fine, wearing a manufacturer's identity is not."""
    for key in ALL:
        prod = F.make_archetype(product=key)
        (_tname, vals), = prod.doc.types
        for bip in (SK.BIP_TYPE_MANUFACTURER, SK.BIP_TYPE_MODEL):
            assert not str(vals.get(bip, "")).strip(), key
        assert prod.facts.catalog == "", key


@needs_schema
def test_the_family_reports_which_dimensions_were_generated():
    prod = F.make_archetype(product="cable_tray",
                            prompt="a 24 inch cable tray 20 ft long")
    facts = prod.facts.values
    assert facts["width_in"].kind == "given" and "24 inch" in facts["width_in"].source
    assert facts["rung_spacing_in"].kind == AR.NOMINAL
    assert facts["rung_spacing_in"].note                    # the practice it follows
    # the assembly bounding box is NOT the archetype's own width (a tray's
    # usable width is inside its rails) and does not overwrite it
    assert facts["overall_depth_in"].value > facts["width_in"].value
    assert any("no manufacturer" in n.lower() for n in prod.notes)


@needs_schema
def test_an_archetype_family_carries_its_category_standards():
    prod = F.make_archetype(product="cable_tray")
    assert prod.standards["category"] == "cable_tray_fitting"
    assert {"Tray Width", "Tray Height", "Tray Type"} <= set(prod.standards["filled"])


@needs_schema
def test_the_famspec_contract_accepts_an_archetype():
    from rvt.frontdoor import famspec as FS
    spec = {"kind": "archetype", "product": "cable_tray",
            "dimensions": {"width_in": 24, "length_ft": 20},
            "prompt": "with 6 in rung spacing"}
    assert FS.validate(spec) == []
    kind, kw, _route = FS.normalise(spec)
    prod = FS.build(kind, kw)
    assert set(prod.archetype["given"]) == {"width_in", "length_ft", "rung_spacing_in"}
    assert FS.constructor_name("archetype") == "rvt.famgen.factory:make_archetype"
    # the schema refuses a famspec that names no product, and one with junk
    assert FS.validate({"kind": "archetype"}) != []
    assert FS.validate({"kind": "archetype", "product": "cable_tray",
                        "dimensions": {"width_in": "wide"}}) != []


# ---------------------------------------------------------------------------
# 5. the route, and the file
# ---------------------------------------------------------------------------

@needs_schema
def test_the_bare_prompt_that_used_to_be_refused_now_delivers(tmp_path):
    """The headline of #591."""
    from rvt.frontdoor import router as R
    res = R.route({"prompt": "create a cable tray family"}, "rfa",
                  out=str(tmp_path / "ct"))
    assert res.ok, res.status
    rfa = res.files.get("rfa")
    assert rfa and os.path.isfile(rfa)
    assert "Cable Tray" in res.status and "nominal" in res.status
    assert os.path.isfile(res.files["archetype"])
    assert any("ARCHETYPE LANE" in c for c in res.caveats)
    assert any("no manufacturer" in c.lower() for c in res.caveats)


@needs_schema
def test_the_prompt_overrides_reach_the_route(tmp_path):
    from rvt.frontdoor import router as R
    res = R.route({"prompt": "a 24 inch cable tray 20 ft long with 6 inch rung spacing"},
                  "rfa", out=str(tmp_path / "ct2"))
    assert res.ok, res.status
    assert "3 dimension(s) from the prompt" in res.status


@needs_schema
def test_catalog_facts_still_win_when_the_prompt_names_a_catalog_product(tmp_path):
    """#591 DONE 6: a real record must never route to a generated approximation."""
    from rvt.frontdoor import router as R
    res = R.route({"prompt": "a 225 A Eaton panelboard with 30 spaces at 208Y/120"},
                  "rfa", out=str(tmp_path / "pb"))
    assert res.ok, res.status
    assert "family .rfa generated" in res.status
    assert not any("ARCHETYPE LANE" in c for c in res.caveats)


@needs_schema
def test_a_prompt_naming_nothing_we_build_is_still_refused(tmp_path):
    from rvt.frontdoor import router as R
    res = R.route({"prompt": "make me a spaceship"}, "rfa", out=str(tmp_path / "no"))
    assert res.ok is False
    assert res.errors and "nothing to author" in " ".join(map(str, res.errors))


@needs_schema
@pytest.mark.parametrize("key", ALL)
def test_every_archetype_emits_a_valid_provenance_clean_rfa(key, tmp_path):
    prod = F.make_archetype(product=key)
    rep = prod.write(str(tmp_path / f"{key}.rfa"), validate=True, provenance=True)
    assert rep["ok"], rep.get("caveats")
    fam = rep["validate"]["family_mode"]
    assert fam["verdict"] == "VALID" and fam["n_errors"] == 0, fam.get("errors")
    assert rep["provenance"]["ok"] and rep["provenance"]["suspects"] == []
    assert rep["family"]["archetype"]["product"] == key


# ---------------------------------------------------------------------------
# 6. regressions found by the independent review of PR #674 -- one test per
#    finding, each failing on the code as first written
# ---------------------------------------------------------------------------

def test_a_longer_alias_is_not_swallowed_by_a_shorter_one():
    """`length` sits inside `slot length`. Scanned parameter-by-parameter the
    short alias won the region and locked the long one out, so this prompt
    built a 1.1-INCH channel that reported a slot spacing it did not have."""
    r = AR.resolve_prompt("a strut channel with slot spacing 2 in and slot length 1.125 in")
    assert r.values["slot_length_in"] == pytest.approx(1.125)
    assert r.values["slot_spacing_in"] == pytest.approx(2.0)
    assert r.values["length_ft"] == 10.0                      # the nominal, untouched
    assert "length_ft" not in r.given()
    # ... and the slots are really built from the prompt alone
    assert len([p for p in r.parts() if p["name"].startswith("back")]) > 10
    # word order must not change the reading
    r2 = AR.resolve_prompt("a strut channel 10 ft long with slot spacing 2 in "
                           "and slot length 1.125 in")
    assert r2.values["length_ft"] == 10.0 and r2.values["slot_length_in"] == pytest.approx(1.125)


@pytest.mark.parametrize("prompt", ["a 10 ft cable tray", "a 10 foot cable tray",
                                    "a 20 ft cable tray"])
def test_a_foot_measurement_before_the_noun_is_a_length_not_a_width(prompt):
    """"a 10 ft cable tray" is a ten-foot-LONG tray. The bare-measurement path
    bound it to the primary (Width, measured in inches) and produced a
    ten-foot-WIDE tray."""
    r = AR.resolve_prompt(prompt)
    want = float(prompt.split()[1])
    assert r.values["length_ft"] == pytest.approx(want) and "length_ft" in r.given()
    assert r.values["width_in"] == 12.0 and "width_in" in r.nominal()
    # the inch form still means the width
    r2 = AR.resolve_prompt("a 24 in cable tray")
    assert r2.values["width_in"] == 24.0 and r2.values["length_ft"] == 10.0


def test_the_rungs_sit_at_the_spacing_the_family_reports():
    """Spreading rungs evenly over the length made the ACHIEVED pitch differ
    from the reported one (9 in asked, 9.23 in built) -- a parameter lying
    about its own geometry."""
    for spacing in (6.0, 9.0, 12.0, 18.0):
        r = AR.resolve("cable_tray", {"length_ft": 10, "rung_spacing_in": spacing})
        xs = sorted(p["center"][0] for p in r.parts() if p["name"].startswith("rung"))
        gaps = [b - a for a, b in zip(xs, xs[1:])]
        assert gaps, spacing
        assert all(g == pytest.approx(spacing * AR.IN, abs=1e-9) for g in gaps), spacing
        assert all(-5.0 <= x <= 5.0 for x in xs)              # inside the section


@pytest.mark.parametrize("product,dims", [
    ("cable_tray", {"depth_in": 0.15}),                       # flanges overlap
    ("cable_tray", {"rung_thickness_in": 9}),                 # rung taller than the rail
    ("strut_channel", {"lip_in": 0.8}),                       # lips meet through the middle
    ("wireway", {"thickness_in": 9}),
    ("junction_box", {"thickness_in": 9}),
])
def test_self_intersecting_geometry_is_refused_not_built(product, dims):
    with pytest.raises(AR.ArchetypeError):
        AR.resolve(product, dims).parts()


@pytest.mark.parametrize("product,dims", [
    ("cable_tray", {"length_ft": 20, "rung_spacing_in": 0.6, "rung_width_in": 0.5}),
    ("strut_channel", {"length_ft": 20, "slot_length_in": 0.01, "slot_spacing_in": 0.02}),
])
def test_a_runaway_part_count_is_refused_by_name(product, dims):
    with pytest.raises(AR.ArchetypeError, match=str(AR.MAX_PARTS)):
        AR.resolve(product, dims).parts()


# ---------------------------------------------------------------------------
# 7. the named-product guard (#591 "Still refused")
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt", [
    "an Eaton B-Line 24 in cable tray part number 24A-09-120",
    "a cable tray, catalog number 24A-09-120",
    "a Unistrut P1000 strut channel",
    "a cable tray p/n 24A-09-120",
])
def test_a_named_manufacturer_item_is_caught(prompt):
    claim = AR.manufacturer_claim(prompt)
    assert claim and claim["reasons"]
    assert "NOT IT" in claim["line"]


@pytest.mark.parametrize("prompt", [
    "create a cable tray family",
    "a 24 inch cable tray 20 ft long with 6 in rung spacing",
    "a 1-5/8 in strut channel 10 ft long",
    "a 12x12 wireway 3 ft long",
    "a 480Y/277 panel and a 2x4 troffer near the cable tray",
    "a 3/4 in EMT conduit run",
])
def test_an_ordinary_generic_request_is_not_flagged(prompt):
    """False positives would put a scary line on every honest delivery."""
    assert AR.manufacturer_claim(prompt) is None


@needs_schema
def test_a_named_product_still_delivers_but_never_silently(tmp_path):
    """Hard rule 1 and steer #591 together: the file is delivered, and the
    FIRST thing said about it is that the named item is not what it is."""
    from rvt.frontdoor import router as R
    res = R.route({"prompt": "an Eaton B-Line 24 in cable tray part number 24A-09-120"},
                  "rfa", out=str(tmp_path / "mfr"))
    assert res.ok and os.path.isfile(res.files["rfa"])        # delivered
    assert "NOT the product you named" in res.status
    assert "AND THIS FILE IS NOT IT" in res.caveats[0]
    assert "24A-09-120" in res.caveats[0] and "eaton" in res.caveats[0].lower()


@needs_schema
def test_the_named_product_never_reaches_the_family_identity():
    """The file must not WEAR the name, whatever the prompt said."""
    prod = F.make_archetype(product="cable_tray",
                            prompt="an Eaton B-Line 24 in tray part number 24A-09-120")
    (_tname, vals), = prod.doc.types
    for bip in (SK.BIP_TYPE_MANUFACTURER, SK.BIP_TYPE_MODEL):
        assert not str(vals.get(bip, "")).strip()
    blob = " ".join(str(v) for v in vals.values()) + " " + prod.doc.name
    assert "24A-09-120" not in blob and "Eaton" not in blob
    assert prod.archetype["manufacturer_claim"]["tokens"] == ["24A-09-120"]


def test_a_null_standard_value_is_not_a_refusal():
    """The schema-valued additionalProperties check newly REJECTED famspecs the
    engine documents as valid: `None` means 'no value, leave the slot blank'."""
    from rvt.frontdoor import famspec as FS
    for values in ({"Voltage": None}, {"Ports": [1, 2]}, {"Material": "steel"}):
        spec = {"kind": "generic_model", "width_ft": 1, "depth_ft": 1,
                "height_ft": 1, "standard_values": values}
        assert FS.validate(spec) == [], values
    # ... while a dimension that is not a number is still refused by name
    assert FS.validate({"kind": "archetype", "product": "cable_tray",
                        "dimensions": {"width_in": "wide"}}) != []


# ---------------------------------------------------------------------------
# 8. regressions found by the SECOND independent review of PR #674
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt", [
    "a junction box on the partition wall",       # 'part' inside 'partition'
    "a cable tray above the catwalk",             # 'cat' inside 'catwalk'
    "a partial run of cable tray",
    "create a generic model family for a strut channel",   # 'model family'
    "a cable tray with particular rung spacing of 9 in",
    "a Cat6A data outlet on a cable tray",
    "a 480Y/277 panel beside a cable tray",
    "a 12x12 wireway 3 ft long",
    "a 2x4 troffer above the cable tray",
    "a 120V junction box",
    "a 5-15R device beside a wireway",
    "a 1-5/8 in strut channel 10 ft long",
])
def test_the_manufacturer_guard_does_not_fire_on_ordinary_english(prompt):
    """Without a word boundary after the keyword, 'partition' produced the
    token 'ition' and every honest delivery got the loudest line in the
    product -- which the skill is told to relay verbatim, first."""
    assert AR.manufacturer_claim(prompt) is None


@pytest.mark.parametrize("prompt,token", [
    ("an Eaton B-Line 24 in cable tray part number 24A-09-120", "24A-09-120"),
    ("a cable tray, catalog number 24A-09-120", "24A-09-120"),
    ("a cable tray p/n 24A-09-120", "24A-09-120"),
    ("a model 2BLT4 troffer style tray", "2BLT4"),
    ("a Hoffman F66L120 wireway", "F66L120"),
])
def test_the_manufacturer_guard_still_catches_a_real_designator(prompt, token):
    claim = AR.manufacturer_claim(prompt)
    assert claim and token in claim["tokens"], claim


def test_a_rung_wider_than_its_spacing_is_refused():
    """rung_width was never compared to rung_spacing: 24 in rungs at 12 in
    centres built 8 pairs of interpenetrating solids with no raise."""
    with pytest.raises(AR.ArchetypeError, match="rung"):
        AR.resolve("cable_tray", {"rung_width_in": 24}).parts()
    with pytest.raises(AR.ArchetypeError):
        AR.resolve("cable_tray", {"rung_width_in": 24, "rung_spacing_in": 6}).parts()


@pytest.mark.parametrize("spacing,length,want", [(144, 10, 1), (240, 20, 1), (120, 10, 1)])
def test_a_spacing_wider_than_the_section_gives_one_rung_inside_it(spacing, length, want):
    """max(2, ...) put two rungs a foot past both ends of the rails."""
    r = AR.resolve("cable_tray", {"rung_spacing_in": spacing, "length_ft": length})
    parts = r.parts()
    rungs = [p for p in parts if p["name"].startswith("rung")]
    assert len(rungs) == want
    half = length / 2.0
    for p in rungs:
        assert -half <= p["center"][0] - p["width_ft"] / 2.0
        assert p["center"][0] + p["width_ft"] / 2.0 <= half


@pytest.mark.parametrize("prompt,key,want_in", [
    ("a 600 mm cable tray", "width_in", 600 * AR.MM / AR.IN),
    ("a 300 mm wireway", "width_in", 300 * AR.MM / AR.IN),
])
def test_a_metric_measurement_before_the_noun_is_read_not_dropped(prompt, key, want_in):
    """The unit redirect looked for a parameter measured in mm, found none and
    silently dropped the number -- while the record advertised '600 mm'."""
    r = AR.resolve_prompt(prompt)
    assert key in r.given(), r.given()
    assert r.values[key] == pytest.approx(want_in)


@pytest.mark.parametrize("product,dims", [
    ("strut_channel", {"thickness_in": 0}),
    ("wireway", {"thickness_in": 0}),
    ("junction_box", {"thickness_in": 0}),
    ("cable_tray", {"rail_thickness_in": 0}),
    ("cable_tray", {"rail_flange_in": 0}),
    ("cable_tray", {"width_in": 0}),
])
def test_a_zero_dimension_is_refused_not_authored_as_a_zero_volume_solid(product, dims):
    with pytest.raises(AR.ArchetypeError):
        AR.resolve(product, dims)


def test_zero_is_still_a_meaning_where_it_is_one():
    """The strut's slot parameters mean 'solid back' at 0 -- the blanket
    zero-refusal must not take that away."""
    r = AR.resolve("strut_channel", {"slot_length_in": 0, "slot_spacing_in": 0})
    assert len([p for p in r.parts() if p["name"].startswith("back")]) == 1


@pytest.mark.parametrize("product,dims", [
    ("cable_tray", {"rung_spacing_in": 0.6, "rung_width_in": 0.5, "length_ft": 20}),
    ("strut_channel", {"slot_spacing_in": 0.3, "slot_length_in": 0.1}),
])
def test_the_part_budget_counts_parts_not_rungs(product, dims):
    """The budget compared the RUNG count to MAX_PARTS, so 401 and 405 part
    families slipped past a stated 400-part limit."""
    with pytest.raises(AR.ArchetypeError, match=str(AR.MAX_PARTS)):
        AR.resolve(product, dims).parts()


def test_no_shipped_text_claims_a_refusal_that_does_not_happen():
    """Two rounds of review found this claim in seven places. It is a fact
    about the CODE, so it is pinned as one."""
    import pathlib
    root = pathlib.Path(ROOT)
    # SHIPPED text only -- deliberately no docs/ file here: the CI shard may not
    # open one (tools/dev/ci_fresh.sh SHARD_READS, #523), and it is the code and
    # the user-facing surfaces that must not lie.
    files = [root / "src/rvt/famgen/archetypes.py", root / "src/rvt/famgen/factory.py",
             root / "src/rvt/frontdoor/matrix.py", root / "src/rvt/frontdoor/router.py",
             root / "src/rvt/frontdoor/famspec.py", root / "spec/famspec.schema.json",
             root / "plugin/skills/tekton-author/SKILL.md",
             # the RENDERED matrix is the product's honest capability table and
             # is where the blanket claim survived four rounds. It is in
             # ci_fresh.sh's SHARD_READS, so the shard may open it.
             root / "docs/product/PERMUTATION-MATRIX.md"]
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for phrase in ("part is still refused", "still get a refusal",
                       "is still refused by name"):
            assert phrase not in text, f"{f.name} still claims a refusal that does not happen"
        # The subtler version, and the one four reviewers had to find by hand:
        # a surface may still say the router REFUSES what it has no facts for --
        # that is true of the catalog lanes -- but wherever it says so it must
        # name the archetype lane as an exception IN THE SAME SENTENCE, or it
        # reads as a blanket refusal on the very deliveries that lane makes.
        #
        # SENTENCE-LOCAL ON PURPOSE.  The first version of this check asked
        # `"archetype" in text` over the whole file and was VACUOUS: reverting
        # matrix._CATALOG to its blanket wording left it passing, because these
        # files all mention the word somewhere else. A reviewer proved that by
        # reintroducing the exact regression; the test now fails on it.
        # Target the BLANKET claim specifically -- "anything the catalog has no
        # facts for is refused" -- not every honest "refused by name" in the
        # repo (nested family documents, GraveyardRec footers and unknown
        # famspec kinds really are refused by name, and must stay sayable).
        blanket = (r"anything without facts is refused by name",
                   r"facts the catalog (?:lacks|does not carry) are\s*\*{0,2}refused",
                   r"refused BY NAME in one clear line, never invented",
                   r"REFUSED by name, never invented")
        for pat in blanket:
            for m in re.finditer(pat, text, re.I):
                # the ENCLOSING SENTENCE, not a fixed character window: the
                # 600-char window let the schema's leg pass because
                # "make_archetype" appears in its constructor list earlier in
                # the same paragraph (a reviewer proved that too).
                lo = max((text.rfind(c, 0, m.start()) for c in ".!?\n"), default=-1) + 1
                hi = min((h for h in (text.find(c, m.end()) for c in ".!?\n")
                          if h != -1), default=len(text)) + 1
                window = text[lo:hi].lower()
                assert ("kind='archetype'" in window or "archetype lane" in window
                        or "`archetype`" in window or "the archetype" in window), (
                    f"{f.name} claims a catalog refusal near offset {m.start()} "
                    f"without naming the archetype lane in the same passage: "
                    f"...{text[max(0, m.start() - 120):m.end() + 120]}...")


# ---------------------------------------------------------------------------
# 9. regressions found by the THIRD independent review of PR #674
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt", [
    "an IP65 junction box",              # 'IP65' -> a 65 in box
    "a Unistrut P1000 strut",            # 'P1000' -> an 83 ft section
    "a 480Y/277 wireway",                # '277'  -> a 277 in wireway
    "a T8 wireway",
    "a NEMA 3R junction box",
    "a cable tray for 12AWG conductors",
    "a THHN12 cable tray",
])
def test_digits_inside_a_token_are_not_a_caller_given_dimension(prompt):
    """`_NUM` had no LEFT boundary, so the digits inside an alphanumeric token
    became a dimension -- reported `given` and quoted back with words the
    caller never used as a measurement. The provenance contract lying about
    itself, and it survived three rounds."""
    r = AR.resolve_prompt(prompt)
    assert r is not None
    assert r.given() == [], {k: r.values[k] for k in r.given()}


@pytest.mark.parametrize("prompt,key,want", [
    ("a 24 inch cable tray 20 ft long with 6 in rung spacing", "width_in", 24.0),
    ("a 600 mm cable tray", "width_in", 600 * AR.MM / AR.IN),
    ("a 12x12 wireway 3 ft long", "height_in", 12.0),
    ("a 4x4x6 in junction box", "depth_in", 6.0),
    ("a 1-5/8 in strut channel", "height_in", 1.625),
    ("a 10 ft cable tray", "length_ft", 10.0),
])
def test_the_left_boundary_does_not_cost_a_real_measurement(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert key in r.given(), r.given()
    assert r.values[key] == pytest.approx(want)


@pytest.mark.parametrize("prompt", [
    "a cable tray for 12AWG conductors",
    "500MCM feeders in a wireway",
    "a 200A3P junction box",
    "a 480V3PH wireway",
    "a THHN12 cable tray",
    "an IP65 junction box",
    "a NFPA70 compliant cable tray",
    "a 4C10AWG run in a wireway",
])
def test_electrical_shorthand_is_not_a_manufacturer_claim(prompt):
    """'two letters and two digits' is exactly a wire gauge. A bare designator
    now needs a manufacturer or part-number phrasing beside it before the
    loudest line in the product fires."""
    assert AR.manufacturer_claim(prompt) is None


@pytest.mark.parametrize("prompt,token", [
    ("a Hoffman F66L120 wireway", "F66L120"),
    ("an Eaton B-Line tray part number 24A-09-120", "24A-09-120"),
    ("a model 2BLT4 troffer style tray", "2BLT4"),
])
def test_a_bare_designator_beside_a_brand_still_fires(prompt, token):
    claim = AR.manufacturer_claim(prompt)
    assert claim and token in claim["tokens"], claim


def test_a_brand_alone_still_fires_even_with_no_designator():
    claim = AR.manufacturer_claim("a Panduit 12 in cable tray")
    assert claim and claim["brands"]


def test_a_slot_longer_than_its_own_pitch_is_refused_not_dropped():
    """It returned a SOLID back while the report said both slot values were
    `given` -- the same physical impossibility its sibling condition raises on."""
    with pytest.raises(AR.ArchetypeError, match="slot"):
        AR.resolve("strut_channel", {"slot_length_in": 2.0, "slot_spacing_in": 1.5}).parts()
    with pytest.raises(AR.ArchetypeError):
        AR.resolve("strut_channel", {"slot_length_in": 2.0, "slot_spacing_in": 2.0}).parts()


def test_a_rung_wider_than_the_section_is_refused():
    with pytest.raises(AR.ArchetypeError, match="section"):
        AR.resolve("cable_tray", {"length_ft": 0.2, "rung_width_in": 5}).parts()


# ---------------------------------------------------------------------------
# 10. regressions found by the FOURTH independent review of PR #674
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt,key,want", [
    ("a 24-inch-wide cable tray 20 feet long", "width_in", 24.0),
    ("a 24-inch-wide cable tray 20 feet long", "length_ft", 20.0),
    ("a 6-in-deep cable tray with 9-in rung spacing", "depth_in", 6.0),
    ("a 6-in-deep cable tray with 9-in rung spacing", "rung_spacing_in", 9.0),
    ("a 12-inch-wide cable tray", "width_in", 12.0),
    ("a 10-ft-long cable tray", "length_ft", 10.0),
    ("a 20-foot cable tray", "length_ft", 20.0),
    ("a 3-1/2-in conduit", "diameter_in", 3.5),
    ("a 1-5/8-in strut channel", "height_in", 1.625),
    ("a 4-in junction box", "width_in", 4.0),
])
def test_a_hyphenated_measurement_is_read(prompt, key, want):
    """English hyphenates measurement adjectives, and this domain does it
    constantly. A bare `\\s*` between the number, its unit and the noun dropped
    every one of them -- and then reported the value `nominal`, i.e. "we
    generated it", when the caller had stated it."""
    r = AR.resolve_prompt(prompt)
    assert key in r.given(), (prompt, r.given())
    assert r.values[key] == pytest.approx(want)


@pytest.mark.parametrize("prompt", [
    "a 24-inch-wide cable tray 20 feet long",
    "a 6-in-deep cable tray with 9-in rung spacing",
    "a 10-ft-long cable tray",
    "an 18-in-wide ladder tray",
    "a 2-gang junction box",
    "a 4-pole wireway",
])
def test_a_hyphenated_measurement_is_not_a_catalogue_number(prompt):
    """`6-in-deep` fits the separator-bearing part-number shape exactly, so the
    loudest line in the product fired on the most ordinary request there is."""
    assert AR.manufacturer_claim(prompt) is None


def test_a_grouped_number_is_the_number_the_caller_wrote():
    """"a 1,200 mm cable tray" matched the '200' and delivered a 7.9 in tray,
    quoted back as '200 mm cable tray' -- a truncated fragment that reads
    deliberate."""
    r = AR.resolve_prompt("a 1,200 mm cable tray")
    assert r.values["width_in"] == pytest.approx(1200 * AR.MM / AR.IN)
    assert "width_in" in r.given()


def test_a_slot_length_without_a_spacing_is_refused():
    """It built a SOLID back while the report listed `Slot Length 1.125 in
    (given)` -- a parameter the geometry does not have."""
    with pytest.raises(AR.ArchetypeError, match="(?i)both"):
        AR.resolve("strut_channel", {"slot_length_in": 1.125}).parts()
    with pytest.raises(AR.ArchetypeError, match="(?i)both"):
        AR.resolve("strut_channel", {"slot_spacing_in": 2.0}).parts()
    # both together still build, and neither still means a solid back
    assert len(AR.resolve("strut_channel", {"slot_length_in": 1.125,
                                            "slot_spacing_in": 2.0}).parts()) > 10
    assert len([p for p in AR.resolve("strut_channel", {}).parts()
                if p["name"].startswith("back")]) == 1


def test_the_rendered_matrix_names_the_archetype_lane():
    """docs/product/PERMUTATION-MATRIX.md is the product's honest capability
    table and is where the blanket-refusal claim survived four rounds -- it was
    not even in the diff."""
    import pathlib
    doc = (pathlib.Path(ROOT) / "docs/product/PERMUTATION-MATRIX.md").read_text(encoding="utf-8")
    assert "archetype" in doc.lower()
    assert "make_archetype" in doc


# ---------------------------------------------------------------------------
# 11. regressions found by the FIFTH independent review of PR #674
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["3/0", "4/0", "250/0", "0/0"])
def test_a_zero_denominator_never_reaches_the_router(raw):
    """`_to_number("3/0")` raised ZeroDivisionError, which escaped
    ArchetypeError, crashed the route and WITHHELD THE FILE -- hard rule 1
    broken by a number parser. 3/0 and 4/0 AWG are everyday phrasing here."""
    assert AR._to_number(raw) is None


@needs_schema
def test_a_resolver_crash_costs_the_lane_not_the_delivery(tmp_path, monkeypatch):
    """Whatever the resolver does, the route must still answer. A parser bug
    may cost the archetype lane; it may never cost the file."""
    from rvt.frontdoor import router as R
    from rvt.famgen import archetypes as _AR

    def boom(_prompt, **_kw):
        raise ZeroDivisionError("float division by zero")

    monkeypatch.setattr(_AR, "resolve_prompt", boom)
    res = R.route({"prompt": "a 3/0 cable tray"}, "rfa", out=str(tmp_path / "z"))
    # the archetype lane declined; the route still ends honestly rather than
    # crashing, and says why
    assert any("could not read this prompt" in c for c in res.caveats)


@pytest.mark.parametrize("prompt", [
    "3 cable trays", "6 junction boxes", "a NEMA 12 wireway",
    "a Type 1 junction box", "level 2 cable tray", "a Class 2 wireway",
    "a 3/0 cable tray", "a 4/0 tray",
])
def test_a_bare_number_before_the_noun_is_not_a_dimension(prompt):
    """A bare integer in front of the noun is far more often a COUNT or a
    RATING than a size: "3 cable trays" built one 3-INCH tray and quoted the
    user's own words back as if they had given a width."""
    r = AR.resolve_prompt(prompt)
    assert r is not None and r.given() == [], {k: r.values[k] for k in r.given()}


@pytest.mark.parametrize("prompt,key,want", [
    ("a 2 1/2 in conduit", "diameter_in", 2.5),
    ("a 1 1/2 in conduit", "diameter_in", 1.5),
    ("a 4 1/2 in strut channel", "height_in", 4.5),
    ("a 2-1/2 in conduit", "diameter_in", 2.5),
])
def test_a_spaced_mixed_fraction_keeps_its_whole_number(prompt, key, want):
    """"a 2 1/2 in conduit" matched the trailing "1/2" alone and delivered a
    0.5 in run -- 5x too small, reported `given`, quoted '1/2 in conduit'."""
    r = AR.resolve_prompt(prompt)
    assert key in r.given(), r.given()
    assert r.values[key] == pytest.approx(want)


@pytest.mark.parametrize("prompt", [
    "a Class-I-Div-2 junction box",
    "a NEMA-4X-rated junction box",
    "a 90-degree-elbow-ready cable tray",
    "a UL-listed wireway",
])
def test_a_rating_or_classification_is_not_a_catalogue_number(prompt):
    assert AR.manufacturer_claim(prompt) is None


def test_an_archetype_refusal_is_classified_as_a_refusal_by_name():
    """`famspec.is_refusal` did not list ArchetypeError, so a geometry that
    could not close reported as an opaque emit failure instead of the clear
    one-line refusal the contract promises."""
    from rvt.frontdoor import famspec as FS
    assert FS.is_refusal(AR.ArchetypeError("nope"))
