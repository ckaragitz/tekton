"""tests/test_frontdoor_manifest_pin.py -- manifest.json ``base.pin`` names the
release slot the run actually resolved (issue #264).

Before: ``build_manifest`` always embedded the DEFAULT (2026) pin, so a
``--target-version 2025`` manifest recorded ``base.sha256 = 6242c3aa…`` (the
2025 base) next to ``base.pin.sha256 = 84173b89…`` / ``base.pin.relpath =
…/G_ABPD.rvt`` -- the pin block contradicted the base it sat under and
``tools/probe_batch.py`` had to match the digest against every slot to learn
the lineage.  Now the pin block is the slot the base answers to: same relpath,
same sha256, same certification entry; 2026 unchanged.  Issue #439 (section
below) makes ``resolve_base``'s explicit / env branches agree: a ``--base`` copy
of a certified slot's bytes reads ``pinned`` / certified for that slot; issue
#472 (last section) makes the front door's VERSION block agree too: with no
``--target-version`` it reports the resolved base's own release, and a slot
copy offered for another target resolves that target's slot for every slot.

Fresh-clone safe: the three pinned bases ship in-repo under
``plugin/assets/genesis`` (sha-verified against the registry by
``resolve_base``); nothing here builds a model or needs ``samples/``.
"""
from __future__ import annotations

import copy
import os
import shutil
import sys

import pytest

import rvt.frontdoor as FD
from rvt.frontdoor import base as B
from rvt.frontdoor import manifest as MF
from rvt.frontdoor import target_status as TS

from conftest import CERTIFIED_YEARS, pinned_base

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


# ---------------------------------------------------------------------------
# eng #439 -- 2026-08-10: an explicit --base / $RVT_GENESIS_BASE that IS a
# certified slot's bytes reads pinned + certified for THAT slot (before: only
# the default 2026 sha was compared, so a copy of G_ABPD_2025.rvt passed by
# path read pinned=False + "not the pinned genesis base" next to a base.pin
# block naming the very slot it is).  Labels only -- the bytes never change.
# ---------------------------------------------------------------------------

OTHER_CERTIFIED_YEARS = [y for y in CERTIFIED_YEARS if y != DEFAULT_YEAR]
NOT_PINNED = "not the pinned genesis base"


def _slot_copy(tmp_path, year):
    """A byte-identical copy of the certified pinned base of ``year`` under a
    foreign name/dir -- what a packager or a firm pointing at the bundled base
    hands in (a clean skip when the pin is not resolvable / overridden here)."""
    dst = tmp_path / f"copy_of_{year}.rvt"
    shutil.copyfile(pinned_base(year), dst)
    return str(dst)


def _assert_pinned_as(rb, year, source):
    slot = B.PIN.release_slot(year)
    assert rb.source == source
    assert rb.pinned is True and rb.certified is True
    assert rb.sha256 == slot["sha256"]
    assert rb.certification == dict(slot.get("certification") or {}) != {}
    assert not any(NOT_PINNED in w for w in rb.warnings)
    js = rb.as_json()
    assert js["pinned"] is True and js["certified_genesis_base"] is True
    assert js["certification"] == rb.certification


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_explicit_copy_of_a_certified_slot_is_pinned_for_that_slot(tmp_path, year):
    slot_copy = _slot_copy(tmp_path, year)
    # with the matching --target-version ...
    _assert_pinned_as(B.resolve_base(slot_copy, target_release=year), year, "explicit")
    # ... and with none at all (DONE 2: the digest is matched against every certified slot)
    _assert_pinned_as(B.resolve_base(slot_copy), year, "explicit")


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_env_copy_of_a_certified_slot_is_pinned_for_that_slot(tmp_path, monkeypatch, year):
    monkeypatch.setenv("RVT_GENESIS_BASE", _slot_copy(tmp_path, year))
    _assert_pinned_as(B.resolve_base(None, target_release=year), year, "env")
    _assert_pinned_as(B.resolve_base(None), year, "env")


@pytest.mark.parametrize("year", OTHER_CERTIFIED_YEARS)
def test_manifest_of_an_explicit_slot_copy_is_self_consistent(tmp_path, year):
    """DONE 3: base.pinned true AND base.pin.sha256 == base.sha256 (after #264
    the pin block already named the slot by digest; now the flag agrees)."""
    rb = B.resolve_base(_slot_copy(tmp_path, year), target_release=year)
    man = MF.build_manifest(route="prompt", inputs={}, base=rb, out_dir=str(tmp_path),
                            intent_summary=None, intent_json=None, build=None,
                            version={"requested": year, "status": "match", "output_release": year})
    base, slot = man["base"], B.PIN.release_slot(year)
    assert base["source"] == "explicit" and base["pinned"] is True
    assert base["certified_genesis_base"] is True and base["warnings"] == []
    assert base["pin"]["sha256"] == base["sha256"] == slot["sha256"]
    assert base["pin"]["id"] == slot["id"]
    assert base["pin"]["certification"] == base["certification"]


def test_a_foreign_base_stays_unpinned_with_the_warning(tmp_path, monkeypatch):
    firm = tmp_path / "firm_standard.rvt"
    firm.write_bytes(b"a firm's own base -- not any registry slot's bytes")
    rb = B.resolve_base(str(firm))
    assert rb.source == "explicit" and rb.pinned is False and rb.certified is False
    assert rb.certification == {} and rb.as_json()["certification"] is None
    assert any(NOT_PINNED in w for w in rb.warnings)
    monkeypatch.setenv("RVT_GENESIS_BASE", str(firm))
    rb = B.resolve_base(None)
    assert rb.source == "env" and rb.pinned is False and rb.certified is False
    assert any(NOT_PINNED in w for w in rb.warnings)


def test_a_pending_slots_bytes_are_not_called_certified(tmp_path):
    """pinned/certified needs the slot to be CERTIFIED (release_status: slot
    status + sha pin + version model), not merely to carry a matching sha --
    the same bytes the shipped registry calls certified (tests above)."""
    year = OTHER_CERTIFIED_YEARS[0]
    raw = copy.deepcopy(B.PIN.raw)
    raw["releases"][str(year)]["status"] = "pending certification"
    pending_pin = B.GenesisPin(raw)
    assert B.release_status(year, pin=pending_pin)["certified"] is False
    rb = B.resolve_base(_slot_copy(tmp_path, year), pin=pending_pin)
    assert rb.pinned is False and rb.certified is False and rb.certification == {}
    assert any(NOT_PINNED in w for w in rb.warnings)


# ---------------------------------------------------------------------------
# eng #472 -- 2026-08-10: the VERSION block follows the base.  With no
# --target-version, ``_resolve_base_and_version`` reported the registry
# default (2026) whatever base it resolved, so ``--base <copy of
# G_ABPD_2025.rvt>`` delivered a 2025 file (build_intent runs in the base's
# own release context) under ``output_release: 2026``.  Now the block names
# the release the resolved base produces; and a copy of ANY certified slot
# combined with a different --target-version is "our base arriving by path"
# (the target's own slot decides), not only a copy of the default -- one rule
# for 2026, 2025 and 2024 copies alike.  A firm's own base keeps its release
# with no target and stays REFUSED against a different one.
# ---------------------------------------------------------------------------

CROSS = [(c, t) for c in CERTIFIED_YEARS for t in CERTIFIED_YEARS if c != t]   # (copy of, target)
OTHER_TO_OTHER = [c for c in CROSS if DEFAULT_YEAR not in c][:1]   # e.g. (2024, 2025): refused before
DEFAULT_TO_OTHER = [c for c in CROSS if c[0] == DEFAULT_YEAR][:1]  # e.g. (2026, 2024): #24's path
UNSUPPORTED = min(B.PIN.release_years()) - 1                       # a year with no slot at all


def _firm_bases(monkeypatch):
    """Switch the registry match off: a slot's bytes then read as a firm's own
    base -- same detectable release, no pin (nothing built, fresh-clone safe)."""
    monkeypatch.setattr(B, "_certified_slot_for_digest", lambda digest, pin=B.PIN: None)


def _no_target(req):
    base, vb, errors = FD._resolve_base_and_version(req)
    assert errors == [] and vb["requested"] is None
    return base, vb


def _assert_reports(vb, year, *, named_by):
    assert vb["requested"] is None and vb["status"] == "unspecified"
    assert vb["output_release"] == year
    assert f"Revit {year}" in vb["note"] and named_by in vb["note"]
    assert "ask the user" in vb["note"]                            # release_view relays it as `ask`
    view = TS.release_view({"target_version": vb})
    assert view["output"] == year and f"Revit {year}" in view["opens_in"]
    assert view["resolution"] == "unspecified" and view.get("ask") == vb["note"]
    assert f"Revit {year} target" in MF._release_line(vb)


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_no_target_explicit_slot_copy_reports_its_own_release(tmp_path, year):
    """#472's tripwire (was xfail strict): a copy of G_ABPD_2025.rvt handed in by
    --base with NO --target-version reports 2025 -- the release of the file the
    build delivers -- and the base block still names that slot."""
    base, vb = _no_target(FD.AuthorRequest(prompt="x", base=_slot_copy(tmp_path, year)))
    assert base.source == "explicit" and base.pinned is True and base.certified is True
    _assert_reports(vb, year, named_by="--base")
    assert "our certified" in vb["note"]
    assert MF.resolved_pin(base, MF._version_release(vb))["id"] == B.PIN.release_slot(year)["id"]


@pytest.mark.parametrize("year", OTHER_CERTIFIED_YEARS)
def test_no_target_env_slot_copy_reports_its_own_release(tmp_path, monkeypatch, year):
    monkeypatch.setenv("RVT_GENESIS_BASE", _slot_copy(tmp_path, year))
    base, vb = _no_target(FD.AuthorRequest(prompt="x"))
    assert base.source == "env" and base.pinned is True
    _assert_reports(vb, year, named_by="$RVT_GENESIS_BASE")


def test_no_target_no_base_is_still_the_certified_default(monkeypatch):
    monkeypatch.delenv("RVT_GENESIS_BASE", raising=False)
    base, vb, errors = FD._resolve_base_and_version(FD.AuthorRequest(prompt="x"))
    if base is None:                                              # pragma: no cover - bundle absent
        pytest.skip(f"default pin not resolvable here: {errors}")
    assert base.source.startswith("pinned") and errors == []
    assert vb["output_release"] == DEFAULT_YEAR and vb["status"] == "unspecified"
    assert "the certified default release" in vb["note"] and "--base" not in vb["note"]


@pytest.mark.parametrize("year", OTHER_CERTIFIED_YEARS)
def test_no_target_firm_base_reports_the_release_it_is(tmp_path, monkeypatch, year):
    """A firm's own (unpinned) 2025 base with no target: the file built on it is
    2025, so the block says 2025 -- on the supplier's authority, not certified.
    (The firm base here = the slot's bytes with the registry match switched off:
    same detectable release, no pin.)"""
    _firm_bases(monkeypatch)
    base, vb = _no_target(FD.AuthorRequest(prompt="x", base=_slot_copy(tmp_path, year)))
    assert base.pinned is False and base.certified is False
    assert any(NOT_PINNED in w for w in base.warnings)
    _assert_reports(vb, year, named_by="--base")
    assert "supplier's authority" in vb["note"] and "our certified" not in vb["note"]


@pytest.mark.parametrize("copy_year,target", CROSS)
def test_a_slot_copy_with_another_target_resolves_the_targets_own_slot(tmp_path, copy_year, target):
    """The uniform rule (#472 sibling): --base <copy of ANY certified slot>
    + --target-version <a different certified year> is our base arriving by
    path, so the target's own pinned slot is resolved -- before, only a copy of
    the DEFAULT degraded this way and a 2025/2024 copy was refused outright."""
    base, vb, errors = FD._resolve_base_and_version(
        FD.AuthorRequest(prompt="x", base=_slot_copy(tmp_path, copy_year), target_version=target))
    slot = B.PIN.release_slot(target)
    assert errors == [] and vb["status"] == "match"
    assert vb["requested"] == target and vb["output_release"] == target
    assert base.source.startswith("pinned") and base.pinned is True and base.certified is True
    assert base.sha256 == slot["sha256"]
    assert f"--base is our certified Revit {copy_year} genesis base" in vb["note"]   # names what it recognised


@pytest.mark.parametrize("copy_year,target", OTHER_TO_OTHER + DEFAULT_TO_OTHER)
def test_an_env_slot_copy_with_another_target_resolves_the_targets_own_slot(
        tmp_path, monkeypatch, copy_year, target):
    env_copy = _slot_copy(tmp_path, copy_year)
    monkeypatch.setenv("RVT_GENESIS_BASE", env_copy)
    base, vb, errors = FD._resolve_base_and_version(
        FD.AuthorRequest(prompt="x", target_version=target))
    assert errors == [] and vb["status"] == "match" and vb["output_release"] == target
    assert base.pinned is True and base.sha256 == B.PIN.release_slot(target)["sha256"]
    assert "$RVT_GENESIS_BASE is our certified" in vb["note"]
    assert os.environ["RVT_GENESIS_BASE"] == env_copy               # popped for the slot resolution, restored


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_a_slot_copy_with_an_unsupported_target_falls_back_to_its_own_release(tmp_path, year):
    """Same rule, no slot to resolve: the honest FALLBACK delivers the supplied
    copy (its own release) + THE line -- for a 2025 copy exactly as for a 2026
    one (before: 2026 copy fell back, 2025 copy was refused)."""
    slot_copy = _slot_copy(tmp_path, year)
    base, vb, errors = FD._resolve_base_and_version(
        FD.AuthorRequest(prompt="x", base=slot_copy, target_version=UNSUPPORTED))
    assert errors == [] and vb["status"] == "fallback"
    assert vb["requested"] == UNSUPPORTED and vb["output_release"] == year
    assert base.source == "explicit" and os.path.samefile(base.path, slot_copy)
    assert f"target {UNSUPPORTED}" in vb["line"] and f"targets {year}" in vb["line"]


@pytest.mark.parametrize("copy_year,target", OTHER_TO_OTHER + DEFAULT_TO_OTHER)
def test_a_firm_base_of_another_release_stays_refused(tmp_path, monkeypatch, copy_year, target):
    """The other side of the rule: bytes that are NOT a certified slot's (a
    firm's 2025 project) offered for a 2024 build are a genuine wrong-release
    override -- refused, nothing built, one clear error."""
    _firm_bases(monkeypatch)
    base, vb, errors = FD._resolve_base_and_version(
        FD.AuthorRequest(prompt="x", base=_slot_copy(tmp_path, copy_year), target_version=target))
    assert base is None and vb["status"] == "refused" and vb["output_release"] is None
    assert len(errors) == 1 and str(copy_year) in errors[0] and str(target) in errors[0]
