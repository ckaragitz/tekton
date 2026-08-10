"""test_router_release.py -- ``--target-version`` on the standalone FAMILY
routes of the permutation router (issue #171; src/rvt/frontdoor/router.py).

The rvt build path already emitted Revit-N families for a certified
``--target-version N``; the three family cells (prompt->rfa, ifc->rfa,
spec->rfa) ignored the flag and handed a Revit 2024/2025 recipient silent
Revit-2026 ``.rfa``.  Proven here, on a FRESH CLONE (no samples/, no
ifcopenshell -- the room IFC is then read by the stdlib steplite shim,
appended to sys.path below by the same rule the plugin bootstrap uses; the
spec->rfa cell needs ifcopenshell to author its IFC and is covered by
tests/test_router.py on machines that have it):

* prompt->rfa and ifc->rfa with ``target_version`` in 2024 / 2025 / 2026:
  EVERY delivered ``families/*.rfa`` detects as that release AND carries
  that release's pinned schema (``Formats/Latest`` sha256 ==
  ``KNOWN_RELEASES[N].schema_sha256``); the route JSON's ``target_version``
  block is the front door's own (``status == 'match'``) and the compact
  ``release`` view agrees;
* an uncertified (2023) or unknown (2027) year is never refused and never
  silent: the families are DELIVERED (hard rule 1) at the native release,
  ``target_version.status == 'fallback'`` with THE one clear line, the line
  rides in the caveats, ROUTE.md prints it, and a version-agnostic IFC of
  the same intent sits beside the families;
* no ``--target-version`` is today's native path, only reported
  (``status == 'unspecified'`` + the ask-the-year note);
* the CLI (``tools/route.py run ... --target-version 2024 --json``) agrees.

Run: .venv/bin/python -m pytest tests/test_router_release.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from conftest import HAVE_IFC_AUTHORING   # spec->ifc AUTHORS through ifcopenshell.api, #367

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
# (the IFC read fallback -- real ifcopenshell absent -> the bundled stdlib
# steplite shim -- is selected by the engine itself when rvt.ifc is imported,
# rvt.ifc._fallback / #130; nothing to arrange here)

from rvt import versions as V                     # noqa: E402
from rvt.frontdoor import router as R             # noqa: E402
from rvt.frontdoor import release_ctx as RC       # noqa: E402

PY = sys.executable
ROOM_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
ROOM_SPEC = os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room", "room-spec.json")
BASE_2025 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt")
PROMPT = "an electrical room with 2 panels"
SUPPORTED = sorted(V.SUPPORTED_CREATION_RELEASES)


def _bases_present() -> bool:
    try:
        from rvt.frontdoor.base import resolve_base
        return all(os.path.isfile(resolve_base(target_release=y).path) for y in SUPPORTED)
    except Exception:
        return False


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=225, spaces=42,
                                   voltage="480Y/277", mcb=True, mounting="surface",
                                   panel_name="X")
        return True
    except Exception:
        return False


def _has_numpy() -> bool:
    try:
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(not _bases_present(), reason="pinned per-release genesis bases absent"),
    pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent"),
]
needs_room_ifc = pytest.mark.skipif(
    not (os.path.isfile(ROOM_IFC) and _has_numpy()),
    reason="room IFC input or numpy absent")
needs_spec_authoring = pytest.mark.skipif(
    not (os.path.isfile(ROOM_SPEC) and _has_numpy() and HAVE_IFC_AUTHORING),
    reason="spec->ifc authoring needs the real ifcopenshell (optional `ifc` extra)")


def _rfas(res):
    return [p for k, p in res.files.items() if k.startswith("rfa:")]


def _assert_release(paths, year: int) -> None:
    from rvt.global_framing import schema_of
    assert paths, "no family .rfa delivered"
    want = V.KNOWN_RELEASES[year].schema_sha256
    for p in paths:
        assert os.path.isfile(p), p
        assert V.detect_release(p) == year, (p, V.detect_release(p), year)
        assert schema_of(p).stats()["sha256"] == want, (p, "Formats/Latest is not the "
                                                          f"pinned Revit {year} schema")


def _manifest(res):
    with open(res.manifest_paths["route.json"]) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# certified targets: the families ARE that release
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", SUPPORTED)
def test_prompt_to_rfa_honours_a_certified_target(tmp_path, year):
    res = R.route({"prompt": PROMPT}, "rfa", out=str(tmp_path / "o"), target_version=year)
    assert res.ok, res.errors
    _assert_release(_rfas(res), year)
    tv = res.target_version or {}
    assert tv.get("requested") == year and tv.get("status") == "match", tv
    assert tv.get("output_release") == year
    assert set(res.releases.values()) == {year}, res.releases
    man = _manifest(res)
    assert man["target_version"]["status"] == "match"
    rel = man["release"]
    assert rel["requested"] == year and rel["output"] == year
    assert rel["resolution"] == "match" and rel["target_support"] == "certified-base"
    assert "line" not in rel, "a certified match carries no fallback line"
    with open(res.manifest_paths["ROUTE.md"]) as fh:
        md = fh.read()
    assert f"requested Revit {year} -> output Revit {year}" in md
    if year != RC.native_release():
        assert any(s.get("stage") == "release-context" and s.get("release") == year
                   for s in res.steps), res.steps


@needs_room_ifc
@pytest.mark.parametrize("year", [y for y in SUPPORTED if y != RC.native_release()])
def test_room_ifc_to_rfa_honours_a_certified_target(tmp_path, year):
    res = R.route({"ifc": ROOM_IFC}, "rfa", out=str(tmp_path / "o"), target_version=year)
    assert res.ok, res.errors
    assert res.route == "ifc_to_rfa"
    rfas = _rfas(res)
    assert len(rfas) >= 2, res.files
    _assert_release(rfas, year)
    assert (res.target_version or {}).get("status") == "match"
    assert _manifest(res)["release"]["output"] == year


# ---------------------------------------------------------------------------
# uncertified / unknown targets: delivered + THE line (never silent, never refused)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2023, 2027])
def test_uncertified_target_delivers_native_with_the_line(tmp_path, year):
    assert year not in SUPPORTED
    native = RC.native_release()
    res = R.route({"prompt": PROMPT}, "rfa", out=str(tmp_path / "o"), target_version=year)
    assert res.ok, res.errors                       # rule 1: delivered, not refused
    _assert_release(_rfas(res), native)
    tv = res.target_version or {}
    assert tv.get("requested") == year and tv.get("status") == "fallback", tv
    assert tv.get("output_release") == native
    line = str(tv.get("line") or "")
    assert f"target {year} requested" in line and f"your Revit {year} cannot open it" in line
    assert f"this file targets {native}" in line
    assert line in res.caveats, "the line must ride as a caveat after delivery"
    assert tv.get("supported_targets") == SUPPORTED
    # the version-agnostic IFC of the SAME intent sits beside the families
    ifc = res.files.get("ifc")
    assert ifc and os.path.isfile(ifc), res.files
    with open(ifc, "rb") as fh:
        assert fh.read(9) == b"ISO-10303"
    man = _manifest(res)
    assert man["target_version"]["status"] == "fallback"
    assert man["release"]["resolution"] == "fallback" and man["release"]["line"] == line
    with open(res.manifest_paths["ROUTE.md"]) as fh:
        md = fh.read()
    assert "(**fallback**)" in md and line in md


@needs_room_ifc
def test_room_ifc_fallback_copies_the_input_ifc_beside(tmp_path):
    res = R.route({"ifc": ROOM_IFC}, "rfa", out=str(tmp_path / "o"), target_version=2023)
    assert res.ok, res.errors
    _assert_release(_rfas(res), RC.native_release())
    tv = res.target_version or {}
    assert tv.get("status") == "fallback" and tv.get("line") in res.caveats
    ifc = res.files.get("ifc")
    assert ifc and os.path.dirname(os.path.abspath(ifc)) == os.path.abspath(str(tmp_path / "o"))
    with open(ifc, "rb") as a, open(ROOM_IFC, "rb") as b:
        assert a.read() == b.read(), "the input IFC is copied verbatim (already version-agnostic)"


@needs_spec_authoring
@pytest.mark.parametrize("year", [min(SUPPORTED), 2023])
def test_spec_to_rfa_honours_the_target_too(tmp_path, year):
    """The third family cell shares `_families_from_model`; prove it end to end
    where the spec's IFC can be authored (its generated IFC is the fallback
    addition)."""
    res = R.route({"spec": ROOM_SPEC}, "rfa", out=str(tmp_path / "o"), target_version=year)
    assert res.ok, res.errors
    assert res.route == "spec_to_rfa"
    tv = res.target_version or {}
    if year in SUPPORTED:
        assert tv.get("status") == "match", tv
        _assert_release(_rfas(res), year)
    else:
        assert tv.get("status") == "fallback" and tv.get("line") in res.caveats, tv
        _assert_release(_rfas(res), RC.native_release())
        ifc = res.files.get("ifc")
        assert ifc and os.path.isfile(ifc), "the spec's generated IFC rides beside the families"


def test_wrong_release_base_is_refused_as_base_but_families_still_delivered(tmp_path):
    """An explicit --base of another release is refused AS A BASE (the resolver's
    verdict, relayed) -- the families need no base, so they are delivered at the
    native release and the line says so (rule 1: never withheld)."""
    if not os.path.isfile(BASE_2025) or RC.native_release() == 2025:
        pytest.skip("bundled 2025 base absent (or 2025 is the native release)")
    native = RC.native_release()
    res = R.route({"prompt": PROMPT}, "rfa", out=str(tmp_path / "o"),
                  target_version=min(SUPPORTED), base=BASE_2025)
    assert res.ok, res.errors
    _assert_release(_rfas(res), native)
    tv = res.target_version or {}
    assert tv.get("status") == "refused" and tv.get("output_release") == native, tv
    line = str(tv.get("line") or "")
    assert "--base" in line and f"delivered at Revit {native}" in line
    assert line in res.caveats


# ---------------------------------------------------------------------------
# no --target-version: today's path, only reported
# ---------------------------------------------------------------------------

def test_no_target_version_is_the_native_path_reported(tmp_path):
    native = RC.native_release()
    res = R.route({"prompt": PROMPT}, "rfa", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    _assert_release(_rfas(res), native)
    tv = res.target_version or {}
    assert tv.get("requested") is None and tv.get("status") == "unspecified", tv
    assert tv.get("output_release") == native
    assert "ask" in str(tv.get("note") or "").lower()
    assert not any(s.get("stage") == "release-context" for s in res.steps)
    assert not any("cannot open" in c for c in res.caveats), res.caveats
    rel = _manifest(res)["release"]
    assert rel["resolution"] == "unspecified" and rel.get("ask")


def test_release_context_is_restored_after_a_targeted_route(tmp_path):
    """A 2024 family route must not leave the process re-pointed at 2024:
    the next flag-less route emits native families again."""
    older = min(SUPPORTED)
    if older == RC.native_release():
        pytest.skip("only one certified release")
    r1 = R.route({"prompt": PROMPT}, "rfa", out=str(tmp_path / "a"), target_version=older)
    assert r1.ok, r1.errors
    _assert_release(_rfas(r1), older)
    assert RC.active_release() is None
    r2 = R.route({"prompt": PROMPT}, "rfa", out=str(tmp_path / "b"))
    assert r2.ok, r2.errors
    _assert_release(_rfas(r2), RC.native_release())


# ---------------------------------------------------------------------------
# the CLI agrees
# ---------------------------------------------------------------------------

def test_cli_route_run_rfa_target_version(tmp_path):
    year = min(SUPPORTED)
    out = tmp_path / "cli"
    cp = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "run",
                         "--output", "rfa", "--prompt", PROMPT,
                         "--target-version", str(year), "--out", str(out), "--json"],
                        cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert cp.returncode == 0, cp.stderr[-2000:] + cp.stdout[-2000:]
    with open(out / "route.json") as fh:
        man = json.load(fh)
    assert man["ok"] and man["target_version"]["status"] == "match"
    assert man["release"]["output"] == year
    rfas = [os.path.join(ROOT, p) if not os.path.isabs(p) else p
            for k, p in man["files"].items() if k.startswith("rfa:")]
    _assert_release(rfas, year)
    assert set(man["releases"][k] for k in man["files"] if k.startswith("rfa:")) == {year}
