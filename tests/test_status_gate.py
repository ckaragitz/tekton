"""test_status_gate.py — the front door's deliverability gate on OUR pinned
composed genesis bases (issue #143), fresh-clone runnable (no samples/).

Before #143 the gate ledgered a build against its own composed base as if the
base were an Autodesk sample: every inherited element read 'autodesk-sample'
(3,058 blockers on a prompt job) and the reason said "Nothing built on a
sample base is a product" with base_is_autodesk_sample=false beside it.
Now the base's authorship census (rvt.frontdoor.census, written by
tools/genesis_census.py from tracked rung evidence) tells the ledger which
base slots are ours by composition and which are the true residue.

Asserted here:
  * the shipped census asset is CURRENT (rebuilds byte-identically from the
    tracked evidence) and covers every certified pin, and the 2026 chain
    method agrees id-for-id with the byte-ground-truth census;
  * provenance_gate on each pinned base: base_kind, the label, the wording
    (G2/G3 + #19/#21/#23, no 'sample base'), blockers in the hundreds;
  * the sample wording is UNCHANGED when the base IS a sample, and a
    user base without a census is worded as such;
  * end to end through the front door: our walls / instances / loaded famgen
    families on G_ABPD are ours (0 transitive-cloned), file delivered.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import base as B          # noqa: E402
from rvt.frontdoor import census as C        # noqa: E402
from rvt import versions as V                 # noqa: E402


def _load_tool(name: str):
    p = os.path.join(ROOT, "tools", f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def job():
    return _load_tool("rvt_job")


@pytest.fixture(scope="module")
def census_tool():
    return _load_tool("genesis_census")


def _pinned(year: int) -> str:
    try:
        rb = B.resolve_base(target_release=year)
    except B.BaseError as e:                          # pragma: no cover - bundle absent
        pytest.skip(f"pinned base for {year} unavailable: {e}")
    assert rb.pinned and rb.certified, year
    return rb.path


CERTIFIED_YEARS = [y for y in B.PIN.release_years() if B.release_status(y)["certified"]]


# ---------------------------------------------------------------------------
# 1. the census asset
# ---------------------------------------------------------------------------
def test_census_asset_is_current(census_tool):
    """tools/genesis_census.py check: the shipped JSON rebuilds byte-identically
    from the tracked evidence (re-pin without rebuilding => red here)."""
    built = census_tool.dumps(census_tool.build_census())
    with open(C.CENSUS_PATH) as fh:
        assert fh.read() == built, "genesis_census.json is STALE — run tools/genesis_census.py build"


def test_census_covers_every_certified_pin():
    table = C.load()
    assert CERTIFIED_YEARS == [2024, 2025, 2026]
    for year in CERTIFIED_YEARS:
        slot = B.PIN.release_slot(year)
        c = table.get(str(slot["sha256"]))
        assert c is not None, f"no census for the {year} pin"
        assert c.revit_release == year and c.base_id == slot["id"]
        # the residue is hundreds, our composed slots thousands -- never the reverse
        assert 100 < len(c.residue_ids) < 1000, (year, len(c.residue_ids))
        assert c.ours_by_composition > 2000, (year, c.ours_by_composition)
        assert c.never_authored_ids <= c.residue_ids


def test_2026_chain_method_agrees_with_byte_ground_truth(census_tool):
    """The rung-chain derivation reproduces residue_c/census.json (seq-102
    compare vs the K4 ancestor) id for id: 422 identical, 11 never authored."""
    c = C.for_file(_pinned(2026))
    assert c is not None and c.base_id == "G_ABPD"
    raw = census_tool.build_census()["bases"][c.sha256]
    cc = raw["cross_check"]
    assert cc["agree"] is True
    assert cc["truth_identical"] == cc["chain_identical"] == len(c.residue_ids) == 422
    assert len(c.never_authored_ids) == 11 and c.landed_but_identical == 411
    assert c.by_disposition["MACHINERY"] == 349 and sum(c.by_disposition.values()) == 422


def test_census_applies_only_to_exact_pinned_bytes(tmp_path):
    src = _pinned(2026)
    twin = tmp_path / "OfficeSampleProject.rvt"          # a sample's NAME, our bytes
    shutil.copyfile(src, twin)
    assert C.lookup(str(twin)) == ("G_ABPD", C.for_file(src))   # bytes decide, not names
    with open(twin, "r+b") as fh:                       # one byte off => not a pin, no census
        fh.seek(0x400)
        b = fh.read(1)
        fh.seek(0x400)
        fh.write(bytes([b[0] ^ 0xFF]))
    assert C.lookup(str(twin)) == (None, None)
    assert C.for_file(None) is None and C.for_file(str(tmp_path / "nope.rvt")) is None
    # the registry is the authority: every certified pin, nothing else
    assert sorted(C.pinned_sha256s().values()) == ["G_ABPD", "G_ABPD_2024", "G_ABPD_2025"]


# ---------------------------------------------------------------------------
# 2. the gate on each pinned base (candidate == base: nothing created)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_gate_on_pinned_base_reads_the_census(job, year):
    path = _pinned(year)
    with V.reading(path):
        g = job.provenance_gate(path, path)
    assert g["base_kind"] == "pinned-composed-genesis"
    assert g["base_is_autodesk_sample"] is False
    # a LABEL, never a refusal (hard rule 1) -- and still honestly PROOF-ONLY
    assert g["status"] == "PROOF-ONLY, NOT-DELIVERABLE" and g["deliverable"] is False
    res = g["residue"]
    assert res["revit_release"] == year and res["identical_to_ancestor"] == len(C.for_file(path).residue_ids)
    tot = g["provenance_totals"]
    assert tot.get("ours-composed") == res["ours_by_composition"] > 2000
    assert tot.get("autodesk-sample") == res["identical_to_ancestor"]
    assert not tot.get("ours-modified") and not tot.get("transitive-cloned")
    elements = [b for b in g["g1"]["blocking"] if b.get("layer") is None]
    n = sum(b["count"] for b in elements)
    assert 100 < n < 1000, (year, n)                    # hundreds, not 3,058
    assert all(b["provenance"] == "autodesk-sample" for b in elements)
    # G2 is MEASURED on our base (identity layer ran), never narrated
    assert "identity" in g["g1"]["layers"]
    reason = g["reason"]
    for cite in ("G2 identity (#19)", "G3 counsel (#23", "residue (#21)", res["base_id"],
                 f"{res['identical_to_ancestor']:,} of the base's", "PROOF-ONLY is a label",
                 "delivered"):
        assert cite in reason, (cite, reason)
    assert "sample base" not in reason and "sample project" not in reason


def test_sample_base_wording_is_unchanged(job, tmp_path, monkeypatch):
    """A base that IS an Autodesk sample keeps the v1 sentence verbatim.  No
    sample bytes exist in a fresh clone, so the fixture is our own base read
    as NOT pinned (lookup patched) under a sample's name -- the name is what
    is_autodesk_sample keys on once the bytes are not a pin."""
    monkeypatch.setattr(C, "lookup", lambda p: (None, None))
    fake = tmp_path / "rstbasicsampleproject.rvt"
    shutil.copyfile(_pinned(2026), fake)
    g = job.provenance_gate(str(fake), str(fake))
    assert g["base_is_autodesk_sample"] is True and g["base_kind"] == "autodesk-sample"
    assert "residue" not in g
    assert g["status"] == "PROOF-ONLY, NOT-DELIVERABLE"
    assert "the base is an Autodesk sample project" in g["reason"]
    assert "Nothing built on a sample base is a product" in g["reason"]
    assert g["provenance_totals"].get("autodesk-sample") == 3102      # everything inherited
    assert g["g1"]["layers"] == ["elements"]                       # v1 ledger, unchanged


def test_user_base_is_worded_as_such(job, monkeypatch):
    monkeypatch.setattr(C, "lookup", lambda p: (None, None))
    path = _pinned(2026)
    g = job.provenance_gate(path, path)
    assert g["base_kind"] == "user-base" and "residue" not in g
    assert g["status"] == "PROOF-ONLY, NOT-DELIVERABLE"
    assert "user-supplied base with no authorship census" in g["reason"]
    assert "sample base" not in g["reason"]


def test_stale_census_on_a_pinned_base_is_said_not_mistaken_for_a_user_base(job, monkeypatch):
    """A re-pin without `tools/genesis_census.py build`: the bytes ARE a pin,
    the census has no entry -> still our base (never 'user-supplied'), the
    ledger falls back to the conservative v1 reading and the manifest says
    STALE with the fix."""
    monkeypatch.setattr(C, "lookup", lambda p: ("G_ABPD", None))
    path = _pinned(2026)
    g = job.provenance_gate(path, path)
    assert g["base_kind"] == "pinned-composed-genesis" and "residue" not in g
    assert g["census"].startswith("STALE") and "genesis_census.py build" in g["census"]
    assert g["provenance_totals"].get("autodesk-sample") == 3102      # conservative fallback
    assert "census asset STALE" in g["reason"] and "user-supplied" not in g["reason"]


# ---------------------------------------------------------------------------
# 3. end to end: our created content on our base is OURS
# ---------------------------------------------------------------------------
def _catalog_ok() -> bool:
    if os.environ.get("RVT_SKIP_LARGE") == "1":         # skipped anyway: spare the import
        return False
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=400, spaces=42,
                                   voltage="480Y/277", mcb=True, mounting="surface",
                                   panel_name="X")
        return True
    except Exception:
        return False


@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1", reason="RVT_SKIP_LARGE=1")
@pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")
def test_frontdoor_prompt_job_gate_counts_only_the_residue(tmp_path):
    import rvt.frontdoor as FD
    r = FD.author(prompt="an electrical room with 6 panels", out=str(tmp_path / "g1"),
                  no_handoff=True)
    assert r.ok, (r.status, r.errors)
    man = r.manifest
    combined = man["build"]["files"]["combined"]["path"]
    assert os.path.isfile(combined)                     # delivered, whatever the label
    sg = man["build"]["status_gate"]
    assert sg["base_kind"] == "pinned-composed-genesis"
    assert sg["base_is_autodesk_sample"] is False
    assert sg["status"] == "PROOF-ONLY, NOT-DELIVERABLE"
    assert sg["residue"]["base_id"] == "G_ABPD"
    tot = sg["provenance_totals"]
    assert tot["ours-composed"] == 2680 and tot["autodesk-sample"] == 422
    assert tot.get("ours-created", 0) >= 100            # walls + instances + loaded families
    assert not tot.get("transitive-cloned"), sg["created_elements"][:3]
    elements = [b for b in sg["g1"]["blocking"] if b.get("layer") is None]
    cats = {b["category"] for b in elements}
    assert not cats & {"loadable-families", "placed-model-content", "embedded-family-documents"}
    assert 100 < sum(b["count"] for b in elements) < 1000
    assert "sample base" not in sg["reason"] and "residue (#21)" in sg["reason"]
    assert "G2 identity (#19): 2 inherited lineage identifier(s)" in sg["reason"]   # measured
    # the label reaches the honesty box and the human manifest
    assert "PROOF-ONLY, NOT-DELIVERABLE" in man["honesty"]["proof_only_stamps"]
    with open(man_path := os.path.join(str(tmp_path / "g1"), "MANIFEST.md")) as fh:
        md = fh.read()
    assert "base authorship (issue #143 census): **pinned-composed-genesis** G_ABPD" in md, man_path
