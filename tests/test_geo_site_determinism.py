"""GeoSite shared-coordinate GUID determinism (issue #9).

``skeleton.new_geo_site`` used to mint a fresh ``uuid4`` for
``m_sharedCoordGUID`` when the caller supplied none, so two builds of the
same intent differed in their two GeoSite records and the delta rippled
through every descendant hash (docs/inbox/y2024-compose.md §6).  The
default is now OUR deterministic uuid5 over the site's identity.

Covers: same inputs -> same GUID; distinct sites -> distinct GUIDs; the
GUID is a version-5 UUID in OUR namespace; an explicit GUID is honoured
verbatim; and two ``house_standard.build_catalog`` runs serialize
byte-identically (the checkable DONE of the issue).
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.genesis import skeleton as sk                              # noqa: E402

NEUTRAL = dict(latitude_rad=0.0, longitude_rad=0.0, timezone_h=0.0)


def test_default_guid_is_deterministic_for_same_inputs():
    a = sk.new_geo_site(21747, "", **NEUTRAL).obj["m_sharedCoordGUID"]
    b = sk.new_geo_site(21747, "", **NEUTRAL).obj["m_sharedCoordGUID"]
    # equal, and exactly the documented derivation (id | name | lat | lon | tz)
    assert a == b == sk.our_guid("geo-site", 21747, "", 0.0, 0.0, 0.0)


def test_distinct_sites_get_distinct_guids():
    sites = [sk.new_geo_site(100, "", **NEUTRAL),                    # internal
             sk.new_geo_site(101, "", **NEUTRAL),                    # other element
             sk.new_geo_site(100, "Site A", **NEUTRAL),              # other name
             sk.new_geo_site(100, "", latitude_rad=0.9, longitude_rad=0.1, timezone_h=1.0)]
    guids = {s.obj["m_sharedCoordGUID"] for s in sites}
    assert len(guids) == 4, guids


def test_default_guid_is_ours_uuid5():
    # version 5 = name-based in our namespace; every corpus GeoSite GUID is a
    # random version-4 one, so ours can never coincide with a donor value
    assert uuid.UUID(sk.new_geo_site(7, "").obj["m_sharedCoordGUID"]).version == 5


def test_explicit_guid_is_honoured():
    want = "00000000-0000-4000-8000-00000000abcd"
    got = sk.new_geo_site(7, "", shared_coord_guid=want).obj["m_sharedCoordGUID"]
    assert got == want


def test_two_house_standard_builds_are_byte_identical():
    """The issue's DONE: two builds of the same intent serialize to the same
    bytes -- every record, GeoSite pair included (before the fix exactly the
    two GeoSite records differed between builds)."""
    from rvt.genesis import house_standard as hs
    try:
        from rvt.genesis import types as ty
        _dec, enc, _schema = ty._S()
    except Exception as exc:                                         # pragma: no cover
        pytest.skip(f"schema codec unavailable: {exc}")

    def encoded(cat):
        return [(r.elem_id, r.class_name, r.header, enc.encode_object(r.class_id, r.obj or {}))
                for r in cat.records]

    c1, c2 = hs.build_catalog(1_500_000), hs.build_catalog(1_500_000)
    assert encoded(c1) == encoded(c2)
    sites = [r.obj["m_sharedCoordGUID"] for r in c1.records if r.class_name == "GeoSite"]
    assert len(sites) == 2 and len(set(sites)) == 2                  # Internal / Project differ
    assert all(uuid.UUID(g).version == 5 for g in sites)
