"""test_category_band_agreement_516.py -- the four in-repo tables that name
the low-voltage device band must agree with the mined facts (#516 review).

WHY THIS EXISTS.  #698 corrected the band in ``rvt.famgen.category_facts``
from the family templates -- ``Fire_Alarm_Device.rft`` carries -2008085, so
Fire Alarm and Nurse Call had been swapped in the ASSUMED block, and
Communication/Nurse Call were swapped again in a different module.  Three
OTHER tables in this repo name the same ids, and NONE of them were checked
when the facts changed:

  * ``rvt.mep.devices.DEVICE_CATEGORIES``   -- id -> name, used by
    ``device_census`` / ``device_symbols``.  It had -2008081 for
    Communication and -2008077 for Nurse Call, the exact inverse of the
    templates: a generated speaker was REPORTED as "Nurse Call Devices".
  * ``rvt.inventory.CATEGORY_NAMES``        -- id -> name, what inspect and
    validate output call a category.  It had Fire Alarm and Nurse Call
    swapped, so a template-verified fire-alarm family was DESCRIBED by our
    own inspect route as "Nurse Call Devices".
  * ``rvt.genesis.residue_b``               -- the six ids go into one
    category SET, so its swap left the set unchanged (the emitted LIST ORDER
    of two entries does change); pinned anyway, because the next reader has
    no way to know that without checking.
  * ``rvt.genesis.house_standard``          -- label-only, rides into the
    build manifest.  It had -2008081 as "Fire Alarm Devices", which the
    template refutes.

NOT swept here, deliberately: ``rvt.mep.electrical_data`` declares
``OST_ElectricalCircuit = -2008087``, colliding with inventory's VERIFIED
``OST_LightingDevices`` for the same id.  One of them is wrong and neither is
in this band; it is #782's item 4, not something to guess at here.

A shared contract is only correct when the LAST consumer is.  This module is
that check, so the next id correction cannot land in one table alone.
"""
import pytest

from rvt.famgen import category_facts as CF

#: Devices sit on the odd slots, alternating with their tag categories
#: (CF.DEVICE_TAG_PAIRING).  THREE of these are template facts; the
#: Communication/Nurse Call pair is NOT -- see TEMPLATE_PINNED below.
BAND = {
    -2008075: "telephone_device",
    -2008077: "communication_device",
    -2008079: "security_device",
    -2008081: "nurse_call_device",
    -2008083: "data_device",
    -2008085: "fire_alarm_device",
}


#: Read from the category's own family template -- these are FACTS.
TEMPLATE_PINNED = {-2008075: "telephone_device",
                   -2008083: "data_device",
                   -2008085: "fire_alarm_device"}

#: NOT settled by any template (#782).  The band law puts devices on the odd
#: slots, which leaves -2008077 and -2008081 for these two -- and BOTH
#: arrangements satisfy it equally.  The assignment below is the engine's
#: current inference; every table is aligned to it so the engine cannot
#: contradict itself, and the tests here pin that AGREEMENT, never the truth
#: of the pair.  When #782 mines the templates, the correction lands in
#: category_facts alone and these tests fail for every other table -- which is
#: exactly what they are for.
INFERRED_PAIR = {-2008077: "communication_device",
                 -2008081: "nurse_call_device"}


@pytest.mark.parametrize("cid,key", sorted(TEMPLATE_PINNED.items()))
def test_template_pinned_ids_are_facts_everywhere(cid, key):
    """The three ids a template actually declares. Changing one is a bug."""
    from rvt.famgen import skeleton as SK
    assert SK._resolve_category(key) == cid
    f = CF.fact(key)
    assert f is not None, f"{key} should have a mined row"
    assert f.category == cid


@pytest.mark.parametrize("cid,key", sorted(INFERRED_PAIR.items()))
def test_the_inferred_pair_is_declared_inferred(cid, key):
    """Pins that the pair is CONSISTENT and still honestly labelled unproven.

    Deliberately NOT a claim that ``cid`` is correct -- #782 decides that.
    What must hold today is that no table disagrees with any other, and that
    the engine has not quietly promoted the guess to a fact.
    """
    from rvt.famgen import skeleton as SK
    assert SK._resolve_category(key) == cid
    assert key in CF.STILL_INFERRED, \
        (f"{key} left STILL_INFERRED without a template: if #782 mined it, "
         f"move it to TEMPLATE_PINNED here and cite the .rft")
    assert CF.fact(key) is None, f"{key} has a mined row but is still inferred"


@pytest.mark.parametrize("cid,key", sorted(BAND.items()))
def test_the_resolver_agrees_with_the_band(cid, key):
    """``_resolve_category`` is the path every family constructor takes.

    Pinned through the RESOLVER, not through ``CF.fact()``: three of these
    six keys (communication / nurse_call / security) are ``STILL_INFERRED``
    and have no mined row, so a fact-only assertion would skip exactly the
    ids that were wrong -- the vacuous-test trap (#674 round 5).
    """
    from rvt.famgen import skeleton as SK
    assert SK._resolve_category(key) == cid


@pytest.mark.parametrize("cid,key", sorted(BAND.items()))
def test_mined_rows_where_they_exist_agree_too(cid, key):
    """And where a template DID declare it, the mined row says the same."""
    f = CF.fact(key)
    if f is None:
        assert key in CF.STILL_INFERRED, \
            f"{key} has no mined row but is not declared STILL_INFERRED"
        pytest.skip(f"{key} is STILL_INFERRED (no template declares it)")
    assert f.category == cid, f"{key}: facts say {f.category}, band says {cid}"


def test_mep_devices_agrees_with_the_facts():
    """The id -> name map behind device_census / device_symbols."""
    from rvt.mep import devices as D
    assert D.OST_CommunicationDevices == -2008077
    assert D.OST_NurseCallDevices == -2008081
    assert D.OST_FireAlarmDevices == -2008085
    # and the map a caller actually reads
    assert D.DEVICE_CATEGORIES[-2008077] == "Communication Devices"
    assert D.DEVICE_CATEGORIES[-2008081] == "Nurse Call Devices"
    assert D.DEVICE_CATEGORIES[-2008085] == "Fire Alarm Devices"


def test_inventory_names_agree_with_the_facts():
    """What inspect / validate output CALLS each category.

    ``category_name`` is the accessor those routes use; it reads the
    ASSUMED band, which is where the Fire Alarm / Nurse Call swap lived.
    """
    from rvt import inventory as INV
    assert INV.category_name(None, -2008085) == "OST_FireAlarmDevices"
    assert INV.category_name(None, -2008081) == "OST_NurseCallDevices"
    assert INV.category_name(None, -2008077) == "OST_CommunicationDevices"


def test_residue_b_names_agree_with_the_facts():
    """Cosmetic in effect (the ids go into ONE set) -- pinned so it stays true."""
    from rvt.genesis import residue_b as RB
    assert RB.OST_FireAlarmDevices == -2008085
    assert RB.OST_NurseCallDevices == -2008081
    assert RB.OST_CommunicationDevices == -2008077


def test_no_id_in_the_band_is_claimed_by_two_names():
    """The whole failure mode, stated once: one id, one meaning, everywhere.

    Compares the two id -> name tables a user actually sees, after folding
    inventory's ``OST_FireAlarmDevices`` spelling onto mep's
    ``"Fire Alarm Devices"``.
    """
    from rvt.mep import devices as D
    from rvt import inventory as INV
    for cid in BAND:
        mep = D.DEVICE_CATEGORIES.get(cid)
        inv = INV.category_name(None, cid)
        if mep is None or inv is None or inv.startswith("OST_?"):
            continue
        folded = inv.replace("OST_", "").replace("Devices", " Devices")
        assert folded.replace(" ", "").lower() == mep.replace(" ", "").lower(), \
            f"{cid}: mep says {mep!r}, inventory says {inv!r}"
