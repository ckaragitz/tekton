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
    assert len(rungs) == 11                   # 10 ft at 12 in centres, both ends
    assert len(parts) == len(rails) + len(rungs)
    # the rungs span the usable width, and sit on the bottom flange
    assert all(p["depth_ft"] == pytest.approx(1.0) for p in rungs)
    assert all(p["base_z_ft"] > 0 for p in rungs)


def test_the_rung_count_follows_the_rung_spacing():
    def rungs(spacing):
        r = AR.resolve("cable_tray", {"rung_spacing_in": spacing, "length_ft": 10})
        return len([p for p in r.parts() if p["name"].startswith("rung")])
    assert rungs(18) == 7 and rungs(12) == 11 and rungs(9) == 14 and rungs(6) == 21


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
