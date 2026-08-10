"""tests/test_frontdoor_manifest_pin.py -- manifest.json ``base.pin`` names the
release slot the run actually resolved (issue #264).

Before: ``build_manifest`` always embedded the DEFAULT (2026) pin, so a
``--target-version 2025`` manifest recorded ``base.sha256 = 6242c3aa…`` (the
2025 base) next to ``base.pin.sha256 = 84173b89…`` / ``base.pin.relpath =
…/G_ABPD.rvt`` -- the pin block contradicted the base it sat under and
``tools/probe_batch.py`` had to match the digest against every slot to learn
the lineage.  Now the pin block is the slot the base answers to: same relpath,
same sha256, same certification entry; 2026 unchanged.

Fresh-clone safe: the three pinned bases ship in-repo under
``plugin/assets/genesis`` (sha-verified against the registry by
``resolve_base``); nothing here builds a model or needs ``samples/``.
"""
from __future__ import annotations

import os
import sys

import pytest

from rvt.frontdoor import base as B
from rvt.frontdoor import manifest as MF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import probe_batch as PB                                          # noqa: E402

DEFAULT_YEAR = int(B.PIN.revit_release)                            # 2026
OTHER_YEARS = [y for y in B.PIN.release_years() if y != DEFAULT_YEAR]   # [2024, 2025]


def _resolved(year):
    try:
        return B.resolve_base(None, target_release=year)
    except B.BaseError as e:                                      # bundle absent on this machine
        pytest.skip(f"pinned Revit {year} genesis base not resolvable here: {e}")


def _manifest(tmp_path, year):
    """A real build_manifest over the really-resolved base of ``year``; the
    'built' file is a stand-in (the pin block does not depend on it)."""
    out = tmp_path / f"pb{year}"
    out.mkdir()
    built = out / "prompt_room.rvt"
    built.write_bytes(b"stand-in for the built project")
    rb = _resolved(year)
    version = {"requested": year, "status": "match", "output_release": year}
    man = MF.build_manifest(route="prompt", inputs={"prompt": "a room with four walls"},
                            base=rb, out_dir=str(out), intent_summary=None,
                            intent_json=None, build={"files": {"combined": str(built)}},
                            version=version)
    return man, rb


@pytest.mark.parametrize("year", OTHER_YEARS)
def test_target_release_manifest_pins_its_own_slot(tmp_path, year):
    man, rb = _manifest(tmp_path, year)
    base, pin = man["base"], man["base"]["pin"]
    slot = B.PIN.release_slot(year)
    assert os.path.basename(base["path"]) == os.path.basename(slot["relpath"])
    assert pin["relpath"] == slot["relpath"]                     # …/subst_k4_2025/compose/G_ABPD_2025.rvt
    assert pin["sha256"] == base["sha256"] == rb.sha256 == slot["sha256"]
    assert pin["id"] == slot["id"] and pin["revit_release"] == str(year)
    assert pin["bytes"] == slot["bytes"] == os.path.getsize(rb.path)
    assert pin["lineage"] == slot["lineage"]
    # the pin block carries the slot's certification entry, so base.certification
    # (the ResolvedBase's) and base.pin agree -- and the entry IS the pinned relpath
    assert pin["certification"] == base["certification"] == slot["certification"]
    assert pin["certification"]["entry"] == pin["relpath"]
    assert pin["certification"]["ledger"] == "docs/coverage/viewer-certified.json"
    # registry-wide facts ride along unchanged
    assert pin["specimen_ancestor"] == B.PIN.as_json()["specimen_ancestor"]


def test_default_release_manifest_pin_is_unchanged(tmp_path):
    man, rb = _manifest(tmp_path, DEFAULT_YEAR)
    assert man["base"]["pin"] == B.PIN.as_json()                # byte-for-byte the old block
    assert man["base"]["pin"]["sha256"] == man["base"]["sha256"] == rb.sha256
    # and no --target-version at all is the same default
    man2 = MF.build_manifest(route="prompt", inputs={}, base=rb, out_dir=str(tmp_path),
                             intent_summary=None, intent_json=None, build=None, version=None)
    assert man2["base"]["pin"] == B.PIN.as_json()


def test_resolved_pin_prefers_the_digest_then_the_release_then_the_default():
    default = B.PIN.as_json()
    y1 = OTHER_YEARS[0]
    slot1 = B.PIN.release_slot(y1)
    # 1. the digest decides even when the release says otherwise (a --base copy
    #    that IS the certified 2025 bytes, run without --target-version)
    rb = B.ResolvedBase(path="/x/copy.rvt", source="explicit", sha256=slot1["sha256"].upper(),
                        pinned=False)
    assert MF.resolved_pin(rb, DEFAULT_YEAR)["relpath"] == slot1["relpath"]
    # 2. an unpinned user base: the run's release names the slot
    firm = B.ResolvedBase(path="/x/firm.rvt", source="explicit", sha256="ab" * 32, pinned=False)
    p = MF.resolved_pin(firm, y1)
    assert (p["relpath"], p["sha256"], p["revit_release"]) == (slot1["relpath"], slot1["sha256"], str(y1))
    assert p["sha256"] != firm.sha256                            # honest: base.pinned stays False
    # 3. the default release, an unknown year, or no release at all: the default pin
    assert MF.resolved_pin(firm, DEFAULT_YEAR) == default
    assert MF.resolved_pin(firm, 2019) == default
    assert MF.resolved_pin(firm) == default


def test_the_version_block_names_the_release():
    """build_manifest reads the release off the front door's version block:
    what was produced, else what was requested (a refused run), else None."""
    y1 = OTHER_YEARS[0]
    assert MF._version_release({"requested": y1, "status": "match", "output_release": y1}) == y1
    assert MF._version_release({"requested": 2019, "status": "fallback",
                                "output_release": DEFAULT_YEAR}) == DEFAULT_YEAR
    assert MF._version_release({"requested": y1, "status": "refused", "output_release": None}) == y1
    assert MF._version_release({"requested": None, "status": "unspecified",
                                "output_release": DEFAULT_YEAR}) == DEFAULT_YEAR
    assert MF._version_release(None) is None and MF._version_release({}) is None


def test_manifest_md_cites_the_slots_ledger_entry(tmp_path):
    """The per-release slots carry ledger/entry/required (no prose 'proves'):
    MANIFEST.md cites the entry instead of printing an empty certification."""
    year = OTHER_YEARS[0]
    man, _ = _manifest(tmp_path, year)
    paths = MF.write_manifest(man, str(tmp_path / "w"))
    with open(paths["md"], encoding="utf-8") as fh:
        md = fh.read()
    entry = B.PIN.release_slot(year)["certification"]["entry"]
    assert f"entry `{entry}`" in md
    assert "- certification: \n" not in md and "  - verdict: \n" not in md


@pytest.mark.parametrize("year", OTHER_YEARS)
def test_probe_batch_resolves_a_target_release_output_via_base_pin_alone(tmp_path, year):
    """DONE #3: with the all-slots digest match disabled (no pins handed in),
    tools/probe_batch.py still declares the 2025 output's base correctly --
    straight from base.pin, because base.sha256 == base.pin.sha256 now."""
    man, _ = _manifest(tmp_path, year)
    ents = PB.frontdoor_entries(man, pins=())
    assert len(ents) == 1
    name, decl = ents[0]
    assert name == "prompt_room"
    assert decl["base"] == PB.rel(B.PIN.release_slot(year)["relpath"])
    assert decl["release"] == year and decl["digest_matched"] is True
    assert decl["declared_by"].endswith("== base.pin")


def test_an_unresolved_target_run_names_the_targets_slot():
    """The stand-in base a refused run's manifest gets names the target's own
    slot path, so base.path and base.pin agree even when nothing was built."""
    import rvt.frontdoor as FD
    y1 = OTHER_YEARS[0]
    rb = FD._explicit_or_pin(FD.AuthorRequest(prompt="x", target_version=y1))
    assert os.path.basename(rb.path) == os.path.basename(B.PIN.release_slot(y1)["relpath"])
    assert rb.sha256 == "(unresolved)" and rb.pinned is False and rb.certified is False
    pin = MF.resolved_pin(rb, MF._version_release({"requested": y1, "status": "refused",
                                                   "output_release": None}))
    assert os.path.basename(pin["relpath"]) == os.path.basename(rb.path)
    # no target, or a year the registry has no slot for: the default relpath, as before
    for req in (FD.AuthorRequest(prompt="x"), FD.AuthorRequest(prompt="x", target_version=2019)):
        assert FD._explicit_or_pin(req).path == os.path.join(B.repo_root(), B.PIN.base_relpath)
