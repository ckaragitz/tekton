"""The donor byte scan must not count OUR OWN element ids (issue #807).

The scan (``genesis_assemble.byte_scan_ids``) reads every offset of the
authored ADocument payload as a little-endian i64 and counts values that are
element ids of the donor document.  ``corroborated_donor_scan`` already
adjudicates one false-positive class -- an id-shaped window straddling two
fields, corroborated by NO leaf of the schema-decoded tree.

This module pins a second, different class that adjudication cannot reach:
an id-shaped window that IS corroborated by a real leaf, where the leaf
legitimately holds **our own** element id, which the donor document happens
to have allocated too.  On the bundled base against a ``start_id=18400``
panelboard that is 7 of our 122 ids, 3 of them referenced -- our Level
(``m_levelIdToPlanViewIds[0].first``), our DBView (``m_DBViewProjectId``)
and a sun-and-shadow settings element -- whose equally-referenced siblings
in the very same lists are clean only because the donor happened not to use
those numbers.

The exclusion is sound because a reference is resolved in the id space of
the document that carries it, and above the scan floor every integer leaf of
our ADocument is one of our own elements (pinned below: if that ever stops
being true, the premise is gone and this module says so).  A reference to an
id that is NOT ours stays fatal -- pinned here on the SAME id, so the two
outcomes are separated by ownership alone and no guard can be removed
without a test dying for it.
"""
from __future__ import annotations

import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED_BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
GA_TOOL = os.path.join(ROOT, "tools", "genesis_assemble.py")

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(BUNDLED_BASE) and os.path.isfile(GA_TOOL)),
    reason="plugin bundle base or the genesis-2 assembler absent")

from rvt.famgen import famdoc_adoc as FA                  # noqa: E402

START_ID = 18400
SCAN_FLOOR = 4700


@pytest.fixture(scope="module")
def emitted(tmp_path_factory):
    """OUR constructive panelboard, emitted as a .rfa the way the failing
    gate does -- ``emit_family_rfa_v2``, not ``famspec.write``."""
    from rvt.frontdoor import standalone as SA
    from rvt.famgen import factory as F
    SA.install_schema(BUNDLED_BASE)
    doc = F.make_panelboard(start_id=START_ID).doc
    if not doc.finalized:
        doc.finalize()
    path = str(tmp_path_factory.mktemp("collision807") / "panel.rfa")
    FA.emit_family_rfa_v2(doc, path, donor=BUNDLED_BASE, timestamp=0,
                          write_reports=False)
    return path


def _our_ids(rfa) -> set:
    from rvt.families import FamilyIndex, unit_segments
    from rvt.objects import iter_records
    segs = unit_segments(FamilyIndex(rfa), 0)
    return {int(r.elem_id) for r in iter_records(segs[102], 102) if r.elem_id >= 0}


def _leaves(rfa) -> set:
    from rvt import adocument as A
    from rvt.container import open_rvt
    with open_rvt(rfa) as f:
        return FA._tree_int_leaves(A.decode_latest(f.inflate("Global/Latest", 0)).value)


# ---------------------------------------------------------------------------
# the premise the exclusion rests on
# ---------------------------------------------------------------------------

def test_every_leaf_above_the_scan_floor_is_one_of_our_elements(emitted):
    """Excluding our ids from the donor scan is only sound while our payload
    references nothing but our own elements above the floor.  This is that
    premise, asserted rather than assumed."""
    ours = _our_ids(emitted)
    big = {v for v in _leaves(emitted) if v >= SCAN_FLOOR}
    assert big, "no id-range leaves at all -- premise cannot be tested"
    assert not (big - ours), (
        "integer leaves >= the scan floor that are NOT our elements: "
        f"{sorted(big - ours)[:20]} -- the #807 exclusion's premise is gone; "
        "the dangling census, not this exclusion, must decide these")


def test_our_family_and_the_bundled_base_really_do_share_ids(emitted):
    """The collision is present, not hypothetical -- otherwise every
    assertion below would pass vacuously."""
    shared = _our_ids(emitted) & set(FA.donor_element_ids(BUNDLED_BASE))
    assert shared, ("our ids and the bundled base's no longer overlap; #807's "
                    "collision class cannot be exercised from this fixture")


# ---------------------------------------------------------------------------
# recorded, not fatal -- and the same id fatal when it is not ours
# ---------------------------------------------------------------------------

def test_a_shared_id_is_recorded_as_a_collision_and_is_not_fatal(emitted):
    rep = FA.provenance_scan_v2(emitted, donor=BUNDLED_BASE)
    ours = _our_ids(emitted)
    donor = set(FA.donor_element_ids(BUNDLED_BASE))
    coll = rep["adocument"]["own_id_space_collisions"]

    assert coll["hits"] >= 1 and coll["distinct"] >= 1, (
        "the shared ids account for no windows -- nothing was being "
        "miscounted, so this fixture no longer reproduces #807")
    assert set(coll["examples"]) <= (ours & donor)
    assert coll["ids"] == sorted(ours & donor)
    assert rep["checks"]["zero_donor_id_byte_hits"] is True
    assert rep["adocument"]["byte_scan_donor_ids"]["hits"] == 0


def test_the_SAME_id_is_fatal_when_it_is_NOT_one_of_ours(emitted):
    """Ownership alone decides.  One id, scanned twice: recorded when the
    document owns it, fatal when it does not."""
    rep = FA.provenance_scan_v2(emitted, donor=BUNDLED_BASE)
    collided = rep["adocument"]["own_id_space_collisions"]["examples"][0]

    narrowed = _our_ids(emitted) - {collided}
    rep2 = FA.provenance_scan_v2(emitted, donor=BUNDLED_BASE, our_ids=narrowed)
    scan = rep2["adocument"]["byte_scan_donor_ids"]
    assert scan["hits"] >= 1 and collided in scan["examples"]
    assert rep2["checks"]["zero_donor_id_byte_hits"] is False


# ---------------------------------------------------------------------------
# nothing is dropped silently
# ---------------------------------------------------------------------------

def test_the_excluded_ids_are_reported_and_account_for_every_lost_window(emitted):
    """The windows the donor scan no longer counts are exactly the ones the
    collision report claims -- so the exclusion cannot be widened into a
    blanket allowance without this failing."""
    from rvt import adocument as A
    from rvt.container import open_rvt
    rep = FA.provenance_scan_v2(emitted, donor=BUNDLED_BASE)
    scan = rep["adocument"]["byte_scan_donor_ids"]
    coll = rep["adocument"]["own_id_space_collisions"]

    # the scanned universe is the full one minus exactly the reported ids
    assert scan["universe"] - scan["universe_scanned"] == len(coll["ids"])

    # and those ids account for exactly the windows an UNFILTERED scan finds
    with open_rvt(emitted) as f:
        payload = f.inflate("Global/Latest", 0)
        value = A.decode_latest(payload).value
    unfiltered = FA.corroborated_donor_scan(
        payload, value, set(FA.donor_element_ids(BUNDLED_BASE)))
    assert unfiltered["hits"] == scan["hits"] + coll["hits"]
    assert sorted(unfiltered["examples"]) == sorted(
        set(scan["examples"]) | set(coll["examples"]))


def test_a_donor_universe_entirely_inside_ours_still_reports_a_whole_scan(emitted,
                                                                          monkeypatch):
    """When every donor id is one of ours, ``foreign_ids`` is empty and the
    donor scan is a hand-built fallback rather than a real scan result.  It
    must still carry the whole shape -- a caller reading ``examples`` on it
    got a KeyError, which the pre-#807 code could only reach with an EMPTY
    donor universe and this change makes easy to reach.
    """
    ours = _our_ids(emitted)
    monkeypatch.setattr(FA, "donor_element_ids",
                        lambda donor=None, min_id=4700: sorted(ours))
    rep = FA.provenance_scan_v2(emitted, donor=BUNDLED_BASE)
    scan = rep["adocument"]["byte_scan_donor_ids"]

    assert scan["hits"] == 0
    assert scan["distinct"] == 0 and scan["examples"] == []   # KeyError before the fix
    assert scan["universe_scanned"] == 0 and scan["universe"] == len(ours)
    assert rep["checks"]["zero_donor_id_byte_hits"] is True
    # and the windows those ids account for are still reported, not lost
    assert rep["adocument"]["own_id_space_collisions"]["hits"] >= 1
