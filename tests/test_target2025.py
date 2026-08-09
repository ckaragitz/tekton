"""test_target2025.py -- THE 2025 PRODUCT PATH (target-2025 stream).

The real end user runs Revit 2025 and Revit cannot open newer files, so the
front door carries a version target (``--target-version``) wired into the
version model (``rvt.versions``) and the genesis base registry
(``rvt.frontdoor.base``).  Two eras, one file of tests:

TODAY (2025 base pending certification -- these tests RUN now):
  * the guards refuse honestly: ``require_creation_release(2025)`` raises,
    the base registry's 2025 slot reads ``pending certification``, a --base
    of the wrong release is refused;
  * the front door NEVER silently emits a 2026 file for a 2025 target: it
    delivers the 2026 build PLUS the one clear fallback line PLUS a
    version-agnostic IFC addition of the SAME intent;
  * the IFC addition round-trips through our own ``--ifc`` resolver
    (same tags, kinds, walls, feeder edges).

THE FINISH LINE (skipped until KNOWN_RELEASES[2025].creation_certified
flips at G25-5 -- docs/writer/genesis-2025-plan.md):
  * ``author --prompt <panel> --target-version 2025`` produces a file whose
    BasicFileInfo says Format 2025 and whose Formats/Latest is the pinned
    2025 schema, with ``target_version.status == 'match'``.

When the 2025 campaign certifies, the skipped tests arm THEMSELVES (the
skip condition is the guard flag) -- the finish line is executable, not
prose.
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
ROOM_PROMPT = ("an electrical room 30x20 ft rated for 2500 A service with a main "
               "switchboard, two 400 A distribution panels and four lighting panels")

certified_2025 = 2025 in V.SUPPORTED_CREATION_RELEASES
until_2025_certifies = pytest.mark.skipif(
    not certified_2025,
    reason="the Revit-2025 genesis base is pending certification -- G25-5 "
           "(docs/writer/genesis-2025-plan.md) flips KNOWN_RELEASES[2025]."
           "creation_certified and this test arms itself")
needs_genesis = pytest.mark.skipif(not os.path.exists(GENESIS),
                                   reason="pinned genesis base absent")


def _have_ifcopenshell() -> bool:
    try:
        import ifcopenshell  # noqa: F401
        return True
    except Exception:
        return False


# ===========================================================================
# TODAY: the guards (these flip meaning when 2025 certifies, so every one is
# conditioned on the flag rather than hard-coding the present)
# ===========================================================================

def test_version_model_2025_guard():
    st = V.creation_status(2025)
    if certified_2025:
        assert st["supported"] and st["base"]
        V.require_creation_release(2025)                      # must not raise
    else:
        assert not st["supported"]
        assert "genesis" in st["reason"]
        with pytest.raises(V.UnsupportedTarget) as ei:
            V.require_creation_release(2025)
        assert "Do NOT substitute a newer release" in str(ei.value)


def test_fallback_line_wording_is_the_charter_line():
    line = V.creation_fallback_line(2025, 2026)
    assert line == ("target 2025 requested: the 2025 base is pending certification; "
                    "this file targets 2026 -- your Revit 2025 cannot open it; "
                    "the IFC alongside is version-agnostic")


def test_base_registry_has_a_2025_slot():
    assert 2025 in B.PIN.release_years()
    slot = B.PIN.release_slot(2025)
    assert slot is not None and slot.get("id") == "G_ABPD_2025"
    st = B.release_status(2025)
    if certified_2025:
        assert st["certified"] and st["status"] == "certified"
    else:
        assert not st["certified"]
        assert st["status"] == "pending certification"
        assert st["sha256"] is None                        # nothing falsely pinned
    # 2026 stays certified either way
    st26 = B.release_status(2026)
    assert st26["certified"] and st26["id"] == "G_ABPD"


def test_resolve_base_2025_refuses_or_resolves_never_silently():
    if certified_2025:
        rb = B.resolve_base(target_release=2025)
        assert rb.certified and rb.pinned
        assert V.detect_release(rb.path) == 2025
    else:
        with pytest.raises(B.BaseNotCertified) as ei:
            B.resolve_base(target_release=2025)
        assert "pending certification" in str(ei.value)


@needs_genesis
def test_explicit_base_of_wrong_release_is_refused_for_2025_target():
    """--base <a 2026 file> --target-version 2025 must refuse (require_release),
    never author a 2026 file while promising 2025."""
    with pytest.raises(V.VersionError):
        B.resolve_base(GENESIS, target_release=2025)


def test_cli_flag_parses():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_fd_cli", os.path.join(ROOT, "tools", "frontdoor.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    ap = cli.build_parser()
    a = ap.parse_args(["author", "--prompt", "x", "--target-version", "2025"])
    assert a.target_version == 2025
    # Any year parses (issue #24, hard rule 1): a year with no certified slot
    # is not argparse-refused but reaches the engine's guard, which DELIVERS
    # the default build + the honest line + the IFC addition
    # (tests/test_target_version_first.py pins that); non-integers still exit 2.
    assert ap.parse_args(["author", "--prompt", "x", "--target-version",
                          "2023"]).target_version == 2023
    with pytest.raises(SystemExit):
        ap.parse_args(["author", "--prompt", "x", "--target-version", "R25"])


# ===========================================================================
# TODAY: the honest fallback through the whole front door (fast: handoff-only)
# ===========================================================================

@needs_genesis
def test_frontdoor_2025_target_delivers_line_plus_ifc(tmp_path):
    r = FD.author(prompt=PANEL_PROMPT, target_version=2025, handoff_only=True,
                  out=str(tmp_path))
    assert r.ok
    tv = r.manifest.get("target_version") or {}
    if certified_2025:
        assert tv.get("status") == "match"
        return
    assert tv.get("status") == "fallback"
    assert tv.get("requested") == 2025 and tv.get("output_release") == 2026
    assert tv.get("line") == V.creation_fallback_line(2025, 2026)
    # the honesty box carries the SAME line (no second, softer story)
    assert r.manifest["honesty"]["release"] == tv["line"]
    # the version-agnostic IFC addition exists and is stated in the manifest
    ifc = r.files.get("ifc")
    assert ifc and os.path.isfile(ifc) and os.path.getsize(ifc) > 500
    assert tv.get("ifc_addition")
    # persisted manifest agrees (the field survives json round-trip)
    with open(os.path.join(str(tmp_path), "manifest.json")) as fh:
        assert (json.load(fh).get("target_version") or {}).get("line") == tv["line"]


@needs_genesis
def test_frontdoor_explicit_pinned_base_still_falls_back(tmp_path):
    """The plugin's author_standalone passes the BUNDLED base as an explicit
    --base; with a 2025 target that must degrade honestly (fallback), not
    refuse -- the file IS our pinned default, not a user override."""
    if certified_2025:
        pytest.skip("2025 certified: the explicit-2026-base path now refuses correctly")
    r = FD.author(prompt=PANEL_PROMPT, target_version=2025, handoff_only=True,
                  base=GENESIS, out=str(tmp_path))
    tv = r.manifest.get("target_version") or {}
    assert tv.get("status") == "fallback"
    assert r.files.get("ifc") and os.path.isfile(r.files["ifc"])


@needs_genesis
@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "experiments", "genesis", "R5.rvt")),
                    reason="R5 ancestor absent")
def test_frontdoor_user_base_of_wrong_release_is_refused(tmp_path):
    """A genuinely user-supplied 2026 base with a 2025 target is REFUSED --
    the front door never authors a wrong-release file while promising the
    target (R5 is certified 2026 lineage but NOT the pinned default)."""
    r = FD.author(prompt=PANEL_PROMPT, target_version=2025,
                  base=os.path.join(ROOT, "experiments", "genesis", "R5.rvt"),
                  out=str(tmp_path))
    tv = r.manifest.get("target_version") or {}
    assert tv.get("status") == "refused"
    assert not r.files.get("combined") and not r.files.get("ifc")


@needs_genesis
def test_frontdoor_2026_target_matches_no_addition(tmp_path):
    r = FD.author(prompt=PANEL_PROMPT, target_version=2026, handoff_only=True,
                  out=str(tmp_path))
    tv = r.manifest.get("target_version") or {}
    assert tv.get("status") == "match" and tv.get("output_release") == 2026
    assert "ifc" not in r.files


# ===========================================================================
# TODAY: the IFC addition is REAL -- it round-trips through our own resolver
# ===========================================================================

@pytest.mark.skipif(not _have_ifcopenshell(), reason="ifcopenshell absent")
def test_ifc_addition_roundtrips_the_intent(tmp_path):
    from rvt.frontdoor import prompt_intent as PP, ifc_out
    from rvt.frontdoor.intent import intent_from_ifc
    model, _parsed = PP.prompt_to_intent(ROOM_PROMPT)
    p = ifc_out.write_intent_ifc(model, str(tmp_path / "room.ifc"))
    m2 = intent_from_ifc(p)
    assert {e.tag for e in m2.equipment} == {e.tag for e in model.equipment}
    assert {(e.tag, e.kind) for e in m2.equipment} == \
           {(e.tag, e.kind) for e in model.equipment}
    assert m2.room is not None and len(m2.room.walls) == len(model.room.walls) == 4
    orig_edges = {(f.source, f.target) for f in model.feeders}
    rt_edges = {(f.source, f.target) for f in m2.feeders}
    assert orig_edges == rt_edges
    # deterministic: same intent + same filename -> same bytes
    p2 = ifc_out.write_intent_ifc(model, str(tmp_path / "b" / "room.ifc"))
    assert open(p, "rb").read() == open(p2, "rb").read()


# ===========================================================================
# THE FINISH LINE (arms itself at G25-5)
# ===========================================================================

@until_2025_certifies
@needs_genesis
def test_END_STATE_author_2025_produces_a_2025_file(tmp_path):
    """G25-5 acceptance: `author --prompt <panel> --target-version 2025` ->
    a file whose BasicFileInfo Format is 2025 and whose Formats/Latest is
    the pinned 2025 schema; the manifest says match, no fallback line.
    PLUS the framing proof (build-2025): the partitions walk CLEAN under
    2025 ordinals and are REFUSED under the native (2026) ordinals -- the
    file carries only 2025 framing on disk."""
    r = FD.author(prompt=PANEL_PROMPT, target_version=2025, no_handoff=True,
                  out=str(tmp_path))
    assert r.ok, r.errors
    out = r.files.get("combined") or r.files.get("equipment") or r.files.get("shell")
    assert out and os.path.isfile(out)
    # BasicFileInfo: Format says 2025 (detect_release reads exactly that)
    assert V.detect_release(out) == 2025
    from rvt.container import open_rvt
    from rvt import stream_encoders as SE
    doc = open_rvt(out)
    try:
        bfi = SE.decode_basic_file_info(doc.raw("BasicFileInfo"))
    finally:
        doc.close()
    assert "2025" in str(bfi.get("format"))
    assert bfi.get("build")                      # our authoring string, present
    # the schema aboard IS the pinned 2025 schema
    s = V.schema_of(out)
    assert s.stats()["sha256"] == V.KNOWN_RELEASES[2025].schema_sha256
    tv = r.manifest.get("target_version") or {}
    assert tv.get("status") == "match" and not tv.get("line")
    # FRAMING: clean under 2025 ordinals, refused under the native ordinals
    from rvt.partitions import StreamWalker
    with open_rvt(out) as f:
        pns = f.partition_streams()
        with V.reading(out):
            for pn in pns:
                w = StreamWalker(f.logical(pn), inflate=True, keep_data=False)
                assert not w.errors, (pn, w.errors[:3])
        with pytest.raises(Exception):
            for pn in pns:                       # native (2026) framing: must refuse
                StreamWalker(f.logical(pn), inflate=True, keep_data=False)


def _bundled_2025_base():
    """The certified 2025 base from BUNDLED locations (plugin/assets in git),
    so the family/instance finish line runs in a fresh clone and in CI."""
    from rvt.frontdoor import release_ctx as RC
    return RC._bundled_base_of(2025) if certified_2025 else None


@pytest.mark.skipif(_bundled_2025_base() is None,
                    reason="no bundled certified 2025 base resolves (or 2025 "
                           "is not a certified creation release)")
def test_END_STATE_2025_family_and_instance_lane(tmp_path):
    """Issue #14 finish line: ``author --prompt <panel> --target-version 2025``
    emits a Revit-2025 file with ONE generated family LOADED four-registry and
    ONE instance PLACED, and that file -- judged standalone under its own
    release, no context around the judge -- validates with 0 errors, carries
    only 2025 framing on disk, and reads four-registry coherent.  Then the
    manifest's advertised CRUD entrypoint (``--rvt <that file> --edit``)
    moves the placed instance and the result is still a clean 2025 file."""
    from rvt.famload import four_registry_census
    from rvt.partitions import StreamWalker
    from rvt.container import open_rvt
    from rvt.validate import validate_file
    from rvt.frontdoor import release_ctx as RC

    r = FD.author(prompt=PANEL_PROMPT, target_version=2025, no_handoff=True,
                  out=str(tmp_path / "a"))
    assert r.ok, r.errors
    assert (r.manifest.get("target_version") or {}).get("status") == "match"
    build = r.manifest.get("build") or {}
    kinds = [c.get("kind") for c in (build.get("elements_created") or [])]
    assert kinds.count("loaded-family") == 1, kinds
    assert kinds.count("equipment-instance") == 1, kinds
    out = r.files.get("combined") or r.files.get("equipment")
    assert out and os.path.isfile(out)

    def clean_2025(path):
        assert V.detect_release(path) == 2025
        rep = validate_file(path)                       # release-aware judge, bare
        assert rep.ok, [f"{x.where}: {x.message}" for x in rep.errors]
        census = four_registry_census(path)             # bare: the file's release
        assert census["coherent"] and census["contentdocs_entries"] == 1, census
        with open_rvt(path) as f:
            pns = f.partition_streams()
            with V.reading(path):
                for pn in pns:
                    assert not StreamWalker(f.logical(pn), inflate=True,
                                            keep_data=False).errors
            with pytest.raises(Exception):              # native framing refuses
                for pn in pns:
                    StreamWalker(f.logical(pn), inflate=True, keep_data=False)

    clean_2025(out)
    assert RC.active_release() is None
    # the CRUD entrypoint the manifest prints, on the 2025 output (gap B)
    e = FD.author(rvt=out, edit="move DP-1 to 3,1,0", out=str(tmp_path / "e"))
    assert e.ok, e.errors
    clean_2025(e.files["edited"])
    assert RC.active_release() is None


# ===========================================================================
# THE RELEASE BUILD CONTEXT (rvt.frontdoor.release_ctx -- build-2025 stream)
# ===========================================================================

G25 = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025", "compose",
                   "G_ABPD_2025.rvt")
needs_2025_base = pytest.mark.skipif(not os.path.exists(G25),
                                     reason="composed 2025 base absent")


@until_2025_certifies
@needs_2025_base
def test_release_ctx_swaps_and_restores_everything():
    """Entering the context re-points framing tags, codec singletons and the
    mutate class ids at the 2025 release; exiting restores EVERY one."""
    from rvt.frontdoor import release_ctx as RC
    from rvt import partitions as P, mutate as MU, encode as ENC
    from rvt.genesis import types as GT
    from rvt.famgen import skeleton as FSK

    before = (P.BLOCK_TAG, P.CONTAINER_CLASS, FSK.BLOCK_TAG, FSK._PART_TAG,
              MU.CLASS_FAMILY_INSTANCE, ENC._DEFAULT_ENCODER, dict(GT._STATE))
    assert RC.native_release() == 2026
    assert RC.active_release() is None
    with RC.release_build_context(G25) as info:
        assert info and info["release"] == 2025 and RC.active_release() == 2025
        ords = info["ordinals"]
        assert P.BLOCK_TAG == ords["BLOCK_TAG"] != before[0]
        assert P.CONTAINER_CLASS == ords["CONTAINER_CLASS"] != before[1]
        assert FSK.BLOCK_TAG == ords["BLOCK_TAG"]
        assert FSK._PART_TAG == ords["CONTAINER_CLASS"]
        assert MU.CLASS_FAMILY_INSTANCE != before[4]      # 2025 ordinal
        assert ENC._DEFAULT_ENCODER is not before[5]
    assert RC.active_release() is None
    after = (P.BLOCK_TAG, P.CONTAINER_CLASS, FSK.BLOCK_TAG, FSK._PART_TAG,
             MU.CLASS_FAMILY_INSTANCE, ENC._DEFAULT_ENCODER, dict(GT._STATE))
    assert after[:6] == before[:6]
    assert set(after[6]) == set(before[6])


@needs_genesis
def test_release_ctx_native_base_is_a_noop():
    """The default-release base enters no context at all (yields None)."""
    from rvt.frontdoor import release_ctx as RC
    from rvt import partitions as P
    tag = P.BLOCK_TAG
    with RC.release_build_context(GENESIS) as info:
        assert info is None
        assert P.BLOCK_TAG == tag
    assert not RC.needs_release_context(GENESIS)
