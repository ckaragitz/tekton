"""test_target2024.py -- THE 2024 PRODUCT PATH (target-2024 stream).

The pattern of ``tests/test_target2025.py`` extended to the THIRD release:
a real end user may run Revit 2024, Revit cannot open newer files, and the
front door now carries a 2024 registry slot (``G_ABPD_2024``, pending
certification) next to 2025's.  Two eras, one file of tests:

TODAY (2024 base pending certification -- these tests RUN now):
  * the guards refuse honestly: ``require_creation_release(2024)`` raises,
    the base registry's 2024 slot reads ``pending certification`` with NO
    sha256, and the three-source certification rule reports each source;
  * the front door NEVER silently emits a 2026 file for a 2024 target: it
    delivers the 2026 build PLUS the one clear (generalized) fallback line
    PLUS a version-agnostic IFC addition of the SAME intent;
  * a user-supplied base of the wrong release is refused outright.

THE FINISH LINE (skipped until KNOWN_RELEASES[2024].creation_certified
flips at the 2024 campaign's certification tick -- the same recipe as
G25-5, docs/writer/genesis-2025-plan.md; the recipe transfers wholesale
across releases per docs/inbox/genesis-audit.md verdicts #28):
  * ``author --prompt <panel> --target-version 2024`` produces a file whose
    BasicFileInfo says Format 2024 and whose Formats/Latest is the pinned
    2024 schema, with ``target_version.status == 'match'``.

Every TODAY-test is conditioned on the guard flag (not on the calendar), so
certification day flips them to their certified meaning instead of breaking
them -- the finish line is executable, not prose.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import rvt.versions as V                       # noqa: E402
from rvt.frontdoor import base as B            # noqa: E402
import rvt.frontdoor as FD                     # noqa: E402

GENESIS = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
PANEL_PROMPT = "a 400 A distribution panel"

certified_2024 = 2024 in V.SUPPORTED_CREATION_RELEASES
certified_2025 = 2025 in V.SUPPORTED_CREATION_RELEASES
until_2024_certifies = pytest.mark.skipif(
    not certified_2024,
    reason="the Revit-2024 genesis base is pending certification -- the 2024 "
           "campaign (the certified genesis recipe re-run on 2024 format "
           "data, per genesis-audit verdict #28) flips KNOWN_RELEASES[2024]."
           "creation_certified and this test arms itself")
needs_genesis = pytest.mark.skipif(not os.path.exists(GENESIS),
                                   reason="pinned genesis base absent")


# ===========================================================================
# TODAY: the version-model guard + the generalized fallback line
# ===========================================================================

def test_version_model_2024_guard():
    st = V.creation_status(2024)
    if certified_2024:
        assert st["supported"] and st["base"]
        V.require_creation_release(2024)                      # must not raise
    else:
        assert not st["supported"]
        assert "genesis" in st["reason"]
        assert "2024" in st["reason"]
        with pytest.raises(V.UnsupportedTarget) as ei:
            V.require_creation_release(2024)
        assert "Do NOT substitute a newer release" in str(ei.value)


def test_fallback_line_generalizes_to_2024():
    """creation_fallback_line is release-parametric -- the 2024 wording is
    the SAME charter line with 2024 substituted, nothing bespoke."""
    line = V.creation_fallback_line(2024, 2026)
    assert line == ("target 2024 requested: the 2024 base is pending certification; "
                    "this file targets 2026 -- your Revit 2024 cannot open it; "
                    "the IFC alongside is version-agnostic")


def test_known_releases_2024_mirrors_2025_shape():
    """KNOWN_RELEASES[2024] carries the same creation-guard shape as 2025:
    a full read-side record, creation_certified False (until the campaign
    flips it), and no genesis_base pinned while uncertified."""
    r24, r25 = V.KNOWN_RELEASES[2024], V.KNOWN_RELEASES[2025]
    if not certified_2024:
        assert r24.creation_certified is False
        assert not r24.genesis_base                      # nothing falsely pinned
        assert 2024 not in V.SUPPORTED_CREATION_RELEASES
    if not certified_2025:
        assert r24.creation_certified == r25.creation_certified
    # the read side is fully modelled either way (the versions stream's parity)
    assert r24.class_count == 4492 and r24.schema_size == 470_502
    assert set(r24.framing) == set(r25.framing) == set(V.FRAMING_CLASSES)


# ===========================================================================
# TODAY: the base registry's 2024 slot (three agreeing sources, never fewer)
# ===========================================================================

def test_base_registry_has_a_2024_slot():
    assert 2024 in B.PIN.release_years()
    slot = B.PIN.release_slot(2024)
    assert slot is not None and slot.get("id") == "G_ABPD_2024"
    assert slot.get("relpath") == ("experiments/genesis/subst_k4_2024/compose/"
                                   "G_ABPD_2024.rvt")
    st = B.release_status(2024)
    if certified_2024:
        assert st["certified"] and st["status"] == "certified"
    else:
        assert not st["certified"]
        assert st["status"] == "pending certification"
        assert st["sha256"] is None                        # nothing falsely pinned
        assert st["pending_reason"]                        # the honest reason rides along
        # the three-source rule, reported source by source:
        assert st["slot_certified"] is False
        assert st["version_model_certified"] is False
    # 2026 stays certified either way
    st26 = B.release_status(2026)
    assert st26["certified"] and st26["id"] == "G_ABPD"


def test_three_release_story_is_honest():
    """The registry tells one coherent story across all three releases:
    2026 certified; 2025 and 2024 each present, each honestly pending until
    its own campaign certifies (no slot borrows another's status)."""
    assert set(B.PIN.release_years()) >= {2024, 2025, 2026}
    for year, flag in ((2024, certified_2024), (2025, certified_2025)):
        st = B.release_status(year)
        if flag:
            assert st["certified"]
        else:
            assert not st["certified"] and st["status"] == "pending certification"
            assert st["id"] == f"G_ABPD_{year}"
    assert B.release_status(2026)["certified"]
    # and the version model agrees release by release
    for year in (2024, 2025):
        assert (year in V.SUPPORTED_CREATION_RELEASES) == B.release_status(year)["certified"]


def test_resolve_base_2024_refuses_or_resolves_never_silently():
    if certified_2024:
        rb = B.resolve_base(target_release=2024)
        assert rb.certified and rb.pinned
        assert V.detect_release(rb.path) == 2024
    else:
        with pytest.raises(B.BaseNotCertified) as ei:
            B.resolve_base(target_release=2024)
        assert "pending certification" in str(ei.value)
        assert "2024" in str(ei.value)


@needs_genesis
def test_explicit_base_of_wrong_release_is_refused_for_2024_target():
    """--base <a 2026 file> --target-version 2024 must refuse (require_release),
    never author a 2026 file while promising 2024."""
    with pytest.raises(V.VersionError):
        B.resolve_base(GENESIS, target_release=2024)


def test_cli_flag_parses_2024():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_fd_cli_2024", os.path.join(ROOT, "tools", "frontdoor.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    ap = cli.build_parser()
    a = ap.parse_args(["author", "--prompt", "x", "--target-version", "2024"])
    assert a.target_version == 2024
    # a release with no registry slot at all stays rejected at the CLI
    with pytest.raises(SystemExit):
        ap.parse_args(["author", "--prompt", "x", "--target-version", "2023"])


# ===========================================================================
# TODAY: the honest fallback through the whole front door (fast: handoff-only)
# ===========================================================================

@needs_genesis
def test_frontdoor_2024_target_delivers_line_plus_ifc(tmp_path):
    r = FD.author(prompt=PANEL_PROMPT, target_version=2024, handoff_only=True,
                  out=str(tmp_path))
    assert r.ok
    tv = r.manifest.get("target_version") or {}
    if certified_2024:
        assert tv.get("status") == "match"
        return
    assert tv.get("status") == "fallback"
    assert tv.get("requested") == 2024 and tv.get("output_release") == 2026
    assert tv.get("line") == V.creation_fallback_line(2024, 2026)
    # the honesty box carries the SAME line (no second, softer story)
    assert r.manifest["honesty"]["release"] == tv["line"]
    # the registry's honest status rides in the manifest block
    assert (tv.get("base_status") or {}).get("status") == "pending certification"
    # the version-agnostic IFC addition exists and is stated in the manifest
    ifc = r.files.get("ifc")
    assert ifc and os.path.isfile(ifc) and os.path.getsize(ifc) > 500
    assert tv.get("ifc_addition")
    # persisted manifest agrees (the field survives json round-trip)
    with open(os.path.join(str(tmp_path), "manifest.json")) as fh:
        assert (json.load(fh).get("target_version") or {}).get("line") == tv["line"]


@needs_genesis
def test_frontdoor_explicit_pinned_base_still_falls_back_2024(tmp_path):
    """The plugin's author_standalone passes the BUNDLED base as an explicit
    --base; with a 2024 target that must degrade honestly (fallback), not
    refuse -- the file IS our pinned default, not a user override."""
    if certified_2024:
        pytest.skip("2024 certified: the explicit-2026-base path now refuses correctly")
    r = FD.author(prompt=PANEL_PROMPT, target_version=2024, handoff_only=True,
                  base=GENESIS, out=str(tmp_path))
    tv = r.manifest.get("target_version") or {}
    assert tv.get("status") == "fallback"
    assert r.files.get("ifc") and os.path.isfile(r.files["ifc"])


@needs_genesis
@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "experiments", "genesis", "R5.rvt")),
                    reason="R5 ancestor absent")
def test_frontdoor_user_base_of_wrong_release_is_refused_2024(tmp_path):
    """A genuinely user-supplied 2026 base with a 2024 target is REFUSED --
    the front door never authors a wrong-release file while promising the
    target (R5 is certified 2026 lineage but NOT the pinned default)."""
    r = FD.author(prompt=PANEL_PROMPT, target_version=2024,
                  base=os.path.join(ROOT, "experiments", "genesis", "R5.rvt"),
                  out=str(tmp_path))
    tv = r.manifest.get("target_version") or {}
    assert tv.get("status") == "refused"
    assert not r.files.get("combined") and not r.files.get("ifc")


# ===========================================================================
# THE FINISH LINE (arms itself at the 2024 campaign's certification tick)
# ===========================================================================

@until_2024_certifies
@needs_genesis
def test_END_STATE_author_2024_produces_a_2024_file(tmp_path):
    """2024 acceptance: `author --prompt <panel> --target-version 2024` ->
    a file whose BasicFileInfo Format is 2024 and whose Formats/Latest is
    the pinned 2024 schema; the manifest says match, no fallback line."""
    r = FD.author(prompt=PANEL_PROMPT, target_version=2024, no_handoff=True,
                  out=str(tmp_path))
    assert r.ok, r.errors
    out = r.files.get("combined") or r.files.get("equipment") or r.files.get("shell")
    assert out and os.path.isfile(out)
    # BasicFileInfo: Format says 2024 (detect_release reads exactly that)
    assert V.detect_release(out) == 2024
    from rvt.container import open_rvt
    from rvt import stream_encoders as SE
    doc = open_rvt(out)
    try:
        bfi = SE.decode_basic_file_info(doc.raw("BasicFileInfo"))
    finally:
        doc.close()
    assert "2024" in str(bfi.get("format"))
    assert bfi.get("build")                      # our authoring string, present
    # the schema aboard IS the pinned 2024 schema
    s = V.schema_of(out)
    assert s.stats()["sha256"] == V.KNOWN_RELEASES[2024].schema_sha256
    tv = r.manifest.get("target_version") or {}
    assert tv.get("status") == "match" and not tv.get("line")
