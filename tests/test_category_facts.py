"""Issue #516 -- the family category / part-type facts mined from Revit's
default .rft family templates, and the corrections they forced in
``skeleton._resolve_category``.

Runs in a FRESH CLONE: the template set is quarantined and git-ignored, so
everything here is either a fact about the shipped table or a pin on the
resolver.  The one test that reads templates self-skips when they are
absent.
"""
import os

import pytest

from rvt.famgen import category_facts as CF
from rvt.famgen import skeleton as SK

RFT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "samples", "rft")


# ---------------------------------------------------------------------------
# the table itself
# ---------------------------------------------------------------------------

def test_check_facts_clean():
    assert CF.check_facts() == []


def test_every_row_cites_a_template_and_a_builtin_category():
    assert CF.CATEGORY_FACTS, "the mined table is empty"
    for key, f in CF.CATEGORY_FACTS.items():
        assert f.template.endswith(".rft"), key
        assert f.category < 0, f"{key}: {f.category} is not a built-in id"


def test_accessors():
    assert CF.category_of("electrical_equipment") == -2001040
    assert CF.part_type_of("electrical_equipment") == 14
    assert CF.category_of("Electrical Equipment") == -2001040   # normalised
    assert CF.fact("no_such_kind") is None
    assert CF.category_of("no_such_kind") is None
    assert CF.part_type_of("no_such_kind") is None


def test_still_inferred_keys_are_not_claimed_as_verified():
    for key in CF.STILL_INFERRED:
        assert key not in CF.CATEGORY_FACTS, key


def test_browser_placement_is_recorded_as_unproven():
    # hard rule 4: reading a template is not Autodesk's reader accepting our
    # output.  The caveat must survive, not be optimised away.
    assert "does not prove" in CF.BROWSER_PLACEMENT_UNVERIFIED


# ---------------------------------------------------------------------------
# the corrections -- each pins the NEW value AND rejects the OLD one, so a
# revert fails here rather than passing vacuously
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "key,was,now",
    [(str(c["key"]), c["was"], c["now"]) for c in CF.CORRECTIONS],
    ids=[str(c["key"]) for c in CF.CORRECTIONS])
def test_corrected_category_ids(key, was, now):
    got = SK._resolve_category(key)
    assert got == now, f"{key} should resolve to the corrected {now}"
    assert got != was, f"{key} regressed to the pre-#516 value {was}"


def test_every_correction_actually_changes_something():
    # a CORRECTIONS row whose was == now would make the pin above vacuous
    assert CF.CORRECTIONS
    for c in CF.CORRECTIONS:
        assert c["was"] != c["now"], c["key"]
        assert c["evidence"] in ("rft", "inv", "inv?"), c["key"]


def test_template_tier_corrections_are_backed_by_a_mined_row():
    for c in CF.CORRECTIONS:
        if c["evidence"] != "rft":
            continue
        f = CF.fact(str(c["key"]))
        assert f is not None, c["key"]
        assert f.category == c["now"]
        assert f.template == c["source"]


def test_security_device_no_longer_builds_a_fire_alarm():
    # it used to resolve to -2008085, which IS Fire Alarm Devices by that
    # category's own template: asking for a security device silently got a
    # fire-alarm family.  It must still RESOLVE (hard rule 1 -- never turn a
    # working route into no file), just not to the fire-alarm id.
    sec = SK._resolve_category("security_device")
    fire = SK._resolve_category("fire_alarm_device")
    assert sec != fire
    assert sec != -2008085
    assert fire == -2008085
    # ...and it is honest about still being inferred
    assert "security_device" in CF.STILL_INFERRED
    assert "security_device" not in CF.CATEGORY_FACTS


def test_fire_alarm_is_no_longer_an_air_terminal():
    from rvt import inventory as INV
    # -2008013 is OST_DuctTerminal, corroborated by a real sample element;
    # the old fire_alarm_device id pointed straight at it.
    assert INV.BUILTIN_CATEGORIES_VERIFIED[-2008013][0] == "OST_DuctTerminal"
    assert SK._resolve_category("fire_alarm_device") != -2008013


def test_inventory_tier_corrections_match_inventory():
    from rvt import inventory as INV
    for c in CF.CORRECTIONS:
        if c["evidence"] != "inv":
            continue
        assert c["now"] in INV.BUILTIN_CATEGORIES_VERIFIED, c["key"]


def test_the_unresolved_band_conflict_is_recorded():
    # the templates and inventory's ASSUMED block disagree about -2008085;
    # the conflict must stay visible rather than be quietly picked.
    assert "-2008085" in CF.INVENTORY_ASSUMED_BAND_CONFLICT
    assert "nurse_call_device" in CF.STILL_INFERRED


def test_fire_alarm_and_telephone_no_longer_collide():
    fire = SK._resolve_category("fire_alarm_device")
    tel = SK._resolve_category("telephone_device")
    data = SK._resolve_category("data_device")
    assert len({fire, tel, data}) == 3, (fire, tel, data)


def test_integer_ids_still_pass_through():
    assert SK._resolve_category(-2008085) == -2008085
    assert SK._resolve_category(-999999) == -999999


def test_unknown_key_still_raises():
    with pytest.raises(KeyError):
        SK._resolve_category("not_a_category_at_all")


# ---------------------------------------------------------------------------
# the newly reachable kinds + the duct-fitting part-type enumeration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,cat", [
    ("furniture_system", -2001100), ("entourage", -2001370),
    ("planting", -2001360), ("parking", -2001180), ("site", -2001260),
    ("detail_item", -2002000), ("profile", -2003000),
    ("curtain_wall_panel", -2000170), ("baluster", -2000127),
    ("structural_foundation", -2001300), ("structural_stiffener", -2001354),
    ("duct_fitting", -2008010),
])
def test_newly_resolvable_kinds(key, cat):
    assert SK._resolve_category(key) == cat


def test_duct_fitting_part_types_enumerate_the_fitting_kind():
    assert SK.DUCT_FITTING_PART_TYPE == {"elbow": 5, "tee": 6,
                                         "transition": 7, "cross": 8}
    for kind, pt in SK.DUCT_FITTING_PART_TYPE.items():
        f = CF.fact(f"duct_{kind}")
        assert f is not None and f.part_type == pt and f.category == -2008010


def test_previously_verified_ids_did_not_move():
    # the five that were desktop-verified before #516 -- the mining must not
    # have disturbed them
    assert SK._resolve_category("electrical_equipment") == -2001040
    assert SK._resolve_category("electrical_fixture") == -2001060
    assert SK._resolve_category("lighting_fixture") == -2001120
    assert SK._resolve_category("furniture") == -2000080
    assert SK._resolve_category("generic_model") == -2000151


# ---------------------------------------------------------------------------
# against the real templates (skips without them)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.isdir(RFT_DIR),
                    reason="samples/rft/ templates not present")
def test_shipped_table_matches_the_templates_on_disk():
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "_rft_facts", os.path.join(root, "tools", "rft_facts.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rep = mod.check(RFT_DIR)
    assert rep["problems"] == []
    assert rep["self_check"] == []
    assert rep["rows_checked"] > 0
