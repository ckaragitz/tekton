"""verify_manipulated judges an edited file under its OWN release (issue #11).

Before, ``rvt.manipulate.verify_manipulated`` decoded the edited records
against the built-in latest-release schema and read the partition stream
with whatever framing ordinals happened to be active: called bare on an
edited Revit 2025 / 2024 file it raised ``unexpected Partitions header``;
called inside ``rvt.versions.reading`` it mis-named the edited Level as an
unrelated class and reported ``clean: False`` for a perfectly good edit.

Fresh-clone runnable: the sources are the tracked bundled genesis bases;
the edits are written into ``tmp_path`` through the product's own release
context (``rvt.frontdoor.release_ctx.release_build_context``).

Run: .venv/bin/python -m pytest tests/test_verify_manipulated_release.py -q
"""
from __future__ import annotations

import os
import struct

import pytest

from conftest import context_constants
from rvt import manipulate as M
from rvt import partitions as P
from rvt import versions as V
from rvt.encode import record_stamp
from rvt.objects import iter_records

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}

pytestmark = [pytest.mark.skipif(not all(os.path.isfile(p) for p in BASES.values()),
                                 reason="bundled genesis bases missing"),
              pytest.mark.usefixtures("no_release_leak")]   # after every test the native framing is back


@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches the names the authoring context swaps too -- minus its two lazy schema caches: this
    file's NATIVE builds fill / re-point ``SA._SCHEMA_STATE`` and ``GSK._SCHEMA_CACHE`` by design (a first
    ``bundled_schema()`` on a corpus-less machine, an ``install_schema(target)``), which is no release leak (#707's
    finding; #706 re-aims those two watches at the release-relevant bit, and this trim goes)."""
    return lambda: {k: v for k, v in context_constants().items() if k not in ("SA._SCHEMA_STATE", "GSK._SCHEMA_CACHE")}


def _tamper_102(*, extra: bytes = b"", stamp_delta: int = 0):
    """A plan tamper: re-frame the plan's seq-102 replacement with ``extra``
    stray bytes after the object and/or the stamp off by ``stamp_delta``.
    The framing itself stays valid (64-bit-id era: 2024+ bases only)."""
    def tamper(plan):
        for e in plan.record_edits:
            if e.seq == 102:
                r = next(iter_records(e.new_record, 102))
                payload = r.payload + extra
                stamp = (record_stamp(r.class_id, payload) + stamp_delta) & 0xFFFFFFFF
                ps = 2 + len(payload)
                e.new_record = (struct.pack("<qIIH", r.elem_id, stamp, ps, r.class_id)
                                + payload + struct.pack("<I", ps))
    return tamper


def _edit(year: int, out_dir, *, tamper=None) -> tuple:
    """Raise the first level of BASES[year] by 1.25 ft and commit it to
    ``out_dir`` the way the front door does (inside the base's own release
    context).  ``tamper(plan)`` may rewrite the plan's record edits first.
    Returns (out_path, level_id)."""
    from rvt.frontdoor.release_ctx import release_build_context
    from rvt.mutate import Document
    base = BASES[year]
    out = str(out_dir / f"level_{year}.rvt")
    with release_build_context(base):
        doc = Document.from_file(base)
        lvl = doc.levels()[0]["id"]
        plan = M.set_level_elevation(doc, lvl, doc._level_elevation(lvl) + 1.25)
        if tamper:
            tamper(plan)
        M.commit_plans(base, out, [plan])
    return out, lvl


@pytest.fixture(scope="module")
def edited(tmp_path_factory):
    d = tmp_path_factory.mktemp("verify_release")
    return {year: _edit(year, d) for year in BASES}


def _healthy(v):
    assert v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
    assert v["walker_errors"] == 0 and v["isize_identity_mismatches"] == 0
    assert v["stamps_ok"] and all(v["sentinel_last"].values())
    assert v["elemtable_count"] == v["header_count"]
    assert v["elemtable_ids_sorted"] and v["unit0_ids_equal_elemtable"]
    assert not v["deleted_still_present"] and not v["deleted_in_elemtable"]


@pytest.mark.parametrize("year", sorted(BASES))
def test_edit_verifies_clean_bare_under_its_own_release(edited, year):
    """No context armed by the caller: the verifier binds the file's own
    framing + schema itself, and says it took no fallback."""
    out, lvl = edited[year]
    v = M.verify_manipulated(out, edited_ids=[lvl])
    _healthy(v)
    assert v["fallbacks"] == []
    assert v["edited"][str(lvl)] == {
        "101": {"class": "ElementHeader", "clean": True},
        "102": {"class": "Level", "clean": True},
        "103": {"class": "SerializedDummy", "clean": True}}


def test_nested_inside_an_outer_reading_context(edited):
    """Inside a caller's own ``reading`` (front door, parity) the verdict is
    the same and the caller's ordinals survive the call."""
    out, lvl = edited[2024]
    with V.reading(year=2025) as outer:
        v = M.verify_manipulated(out, edited_ids=[lvl])
        assert {k: getattr(P, k) for k in outer} == dict(outer)
    _healthy(v)
    assert v["edited"][str(lvl)]["102"] == {"class": "Level", "clean": True}


def test_corrupted_edit_is_caught_by_the_own_schema_decode(tmp_path):
    """A structurally impeccable but semantically corrupted seq-102 record
    (8 stray bytes after the object, stamp recomputed) passes every framing
    check and is caught ONLY by the decode against the file's own schema --
    the probe that used to read ``clean: False`` for the honest edit too."""
    out, lvl = _edit(2025, tmp_path, tamper=_tamper_102(extra=b"\0" * 8))
    v = M.verify_manipulated(out, edited_ids=[lvl])
    _healthy(v)                                     # framing, stamps: all fine
    assert v["fallbacks"] == []
    assert v["edited"][str(lvl)]["102"] == {"class": "Level", "clean": False}
    assert v["edited"][str(lvl)]["101"]["clean"] is True


def test_bad_stamp_is_caught(tmp_path):
    """The width-independent stamp check still fires on a wrong stamp."""
    out, lvl = _edit(2025, tmp_path, tamper=_tamper_102(stamp_delta=1))
    v = M.verify_manipulated(out, edited_ids=[lvl])
    assert v["stamps_ok"] is False
    assert v["walker_errors"] == 0 and v["crc_failures"] == 0
    assert v["edited"][str(lvl)]["102"] == {"class": "Level", "clean": True}


def test_unreadable_schema_degrades_with_a_stated_fallback(edited, monkeypatch):
    """If the file's own schema cannot be parsed the verifier still runs:
    framing from the release BasicFileInfo declares, decode against the
    built-in schema, and BOTH substitutions are named in ``fallbacks``."""
    def broken(*a, **kw):
        raise ValueError("synthetic schema damage")

    monkeypatch.setattr(V, "schema_of", broken)     # THIS file's Formats/Latest only
    out, lvl = edited[2025]
    v = M.verify_manipulated(out, edited_ids=[lvl])
    assert v["walker_errors"] == 0 and v["stamps_ok"]          # framing rung 2 held
    assert len(v["fallbacks"]) == 2, v["fallbacks"]
    assert "Revit 2025 framing table" in v["fallbacks"][0]
    assert "synthetic schema damage" in v["fallbacks"][1]
    assert "latest-release schema" in v["fallbacks"][1]
    # the honest consequence of the decode fallback on a 2025 file:
    assert v["edited"][str(lvl)]["102"]["clean"] is False
