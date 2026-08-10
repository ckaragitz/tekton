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
    families on G_ABPD are ours (0 transitive-cloned), file delivered;
  * the census applies TRANSITIVELY (issue #284): an EDIT of our own output
    is classified descends-from-pinned-genesis (byte descent test) and
    ledgered against the pin with the pin's census (same totals in kind as
    the build it edits, the reason names the pin), residue slots edited
    upstream stay derived, and a file with no byte descent keeps user-base.
"""
from __future__ import annotations

import importlib.util
import json
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


def _no_lineage(monkeypatch):
    """Read our own bytes as NEITHER a pin NOR a descendant (both byte tests
    off) -- the only way a fresh clone can stage a 'sample' / 'user' base."""
    monkeypatch.setattr(C, "lookup", lambda p: (None, None))
    monkeypatch.setattr(C, "DESCENT_MIN_IDENTICAL", 1.01)


def test_sample_base_wording_is_unchanged(job, tmp_path, monkeypatch):
    """A base that IS an Autodesk sample keeps the v1 sentence verbatim.  No
    sample bytes exist in a fresh clone, so the fixture is our own base read
    as NOT pinned and NOT descending (both patched off) under a sample's
    name -- the name is what is_autodesk_sample keys on once the bytes say
    nothing."""
    _no_lineage(monkeypatch)
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
    _no_lineage(monkeypatch)
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


def test_census_module_unavailable_is_said_in_the_gate(job, monkeypatch):
    """If the census lookup cannot even import, base_kind falls back to the
    name heuristic -- and the manifest SAYS the lookup was down (review nit
    on #276: never a silent user-base for our own pin)."""
    monkeypatch.setattr(job, "_census_mod", lambda: None)
    monkeypatch.setitem(job.OPT.errors, "rvt.frontdoor.census", "ImportError: simulated")
    path = _pinned(2026)
    g = job.provenance_gate(path, path)
    assert g["base_kind"] == "user-base"                # bytes could not be consulted
    assert g["census"].startswith("UNAVAILABLE (ImportError: simulated)")
    assert "reads as user-base until fixed" in g["census"]
    assert g["status"] == "PROOF-ONLY, NOT-DELIVERABLE"  # fails safe: never over-claims


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

    # --- #284: an EDIT of that output is judged against the pin transitively:
    # our 6 loaded famgen families (host records AND embedded family documents)
    # and their instances stay OURS one lineage step later
    e = FD.author(rvt=combined, edit="move PP-1 to 3,1,4.66", out=str(tmp_path / "e1"))
    assert e.ok, (e.status, e.errors)
    eg = _job_gate(e.manifest)
    assert eg["base_kind"] == "descends-from-pinned-genesis"
    assert eg["provenance_totals"] == tot                     # same reading, one step later
    ecats = {b["category"] for b in eg["g1"]["blocking"] if b.get("layer") is None}
    assert not ecats & {"loadable-families", "placed-model-content", "embedded-family-documents"}
    assert eg["ledgered_against"].endswith("G_ABPD.rvt")


# ---------------------------------------------------------------------------
# 4. the census applies TRANSITIVELY: an edit of our own output (issue #284)
# ---------------------------------------------------------------------------
WALLS_PROMPT = "a storage room 6 by 4 meters with no equipment"   # famgen-free: ~1 s, CI-safe
_CHAINS: dict = {}


def _job_gate(frontdoor_manifest: dict) -> dict:
    """The job runner's FULL base_provenance gate of an --rvt --edit run (the
    front-door manifest links it as edit.job_manifest and echoes a subset)."""
    jm = frontdoor_manifest["edit"]["job_manifest"]
    with open(jm if os.path.isabs(jm) else os.path.join(ROOT, jm)) as fh:
        return json.load(fh)["gates"]["base_provenance"]


def _chain(year: int, tmp_path_factory):
    """prompt (walls only) -> X on the `year` pin, then `--rvt X --edit` -> Y.
    Cached per release for the module: (create result, edit result)."""
    if year not in _CHAINS:
        import rvt.frontdoor as FD
        _pinned(year)                                        # skip cleanly if the bundle is absent
        d = tmp_path_factory.mktemp(f"chain{year}")
        c = FD.author(prompt=WALLS_PROMPT, out=str(d / "p"), no_handoff=True, target_version=year)
        assert c.ok, (year, c.status, c.errors)
        walls = [e["elem_id"] for e in c.manifest["build"]["elements_created"] if e.get("kind") == "wall"]
        assert len(walls) == 4, walls
        x = c.manifest["build"]["files"]["combined"]["path"]
        e = FD.author(rvt=x, edit=f"delete wall {walls[-1]}", out=str(d / "e"))
        assert e.ok, (year, e.status, e.errors)
        _CHAINS[year] = (c, e)
    return _CHAINS[year]


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_edit_of_our_output_descends_from_the_pin(year, tmp_path_factory):
    """`frontdoor author --rvt <our output> --edit …`: the input is not the
    pin's bytes but DESCENDS from it, so the gate reads the pin's census
    transitively -- same totals in kind as the build it edits (residue =
    the pin's residue carried through, composed slots ours, the earlier
    build's walls re-examined for lineage: still transitive-cloned on
    2025/2024 where the wall type is residue (F2), ours on 2026), the reason
    names the pin, the label is unchanged and the file is delivered."""
    c, e = _chain(year, tmp_path_factory)
    sg = c.manifest["build"]["status_gate"]                  # the create route's reading
    assert sg["base_kind"] == "pinned-composed-genesis"
    pin_id = B.PIN.release_slot(year)["id"]
    out = e.manifest["output"]["path"]
    assert os.path.isfile(out if os.path.isabs(out) else os.path.join(ROOT, out))   # delivered
    g = _job_gate(e.manifest)
    assert g["base_kind"] == "descends-from-pinned-genesis"
    assert g["base_is_autodesk_sample"] is False
    assert g["status"] == "PROOF-ONLY, NOT-DELIVERABLE" and g["deliverable"] is False   # a LABEL
    res = g["residue"]                                       # the PIN's census + the descent evidence
    assert res["base_id"] == res["descends_from"] == pin_id and res["revit_release"] == year
    census = C.load()[str(B.PIN.release_slot(year)["sha256"])]
    assert {k: v for k, v in res.items() if k not in ("descends_from", "descent")} == census.summary()
    dsc = res["descent"]
    assert dsc["min_share"] == C.DESCENT_MIN_IDENTICAL == 0.95
    assert dsc["share"] >= 0.99 and dsc["pin_slots_dropped"] == 0 and dsc["pin_slots_edited"] <= 3
    assert dsc["pin_slots_probed"] == census.ours_by_composition and dsc["probed"] == "composed slots"
    assert dsc["history_head_guid_matches_pin"] is True     # corroborating, not the test
    assert os.path.basename(g["ledgered_against"]) == os.path.basename(_pinned(year))
    # the same reading as the create route, one lineage step later (one wall gone)
    ct, et = sg["provenance_totals"], g["provenance_totals"]
    assert et["ours-composed"] == ct["ours-composed"] > 2000
    assert et["autodesk-sample"] == ct["autodesk-sample"]
    assert not et.get("ours-modified") and not et.get("unmatched")
    walls_before = ct.get("ours-created", 0) + ct.get("transitive-cloned", 0)
    walls_after = et.get("ours-created", 0) + et.get("transitive-cloned", 0)
    assert (walls_before, walls_after) == (4, 3)
    assert et.get("transitive-cloned", 0) == max(0, ct.get("transitive-cloned", 0) - 1)   # F2 survives the edit
    if year == 2026:
        assert not et.get("transitive-cloned")
    else:
        assert [w["provenance"] for w in g["created_elements"]] == ["transitive-cloned"] * 3
        assert "600634" in g["created_elements"][0]["reason"]      # the un-ported BasicWallType
    blockers = [b for b in g["g1"]["blocking"] if b.get("layer") is None]
    n_edit = sum(b["count"] for b in blockers)
    n_create = sum(b["count"] for b in sg["g1"]["blocking"] if b.get("layer") is None)
    assert 100 < n_edit <= n_create < 1000, (n_edit, n_create)      # hundreds, never ~3,166
    assert "identity" in g["g1"]["layers"]                          # G2 measured, as on the pin
    reason = g["reason"]
    for cite in ("an edit of our own output", f"descends from the certified composed genesis base {pin_id} (",
                 "ledgered against that pin and its authorship census", "G2 identity (#19)",
                 "G3 counsel (#23", "residue (#21)",
                 f"{et['autodesk-sample']:,} of the pin's {res['identical_to_ancestor']:,} residue slots still aboard",
                 f"{et['ours-composed']:,} of its {res['ours_by_composition']:,} composed slots inherited (ours)",
                 "PROOF-ONLY is a label", "delivered"):
        assert cite in reason, (cite, reason)
    for banned in ("user-supplied", "sample base", "sample project"):
        assert banned not in reason
    # the front-door manifest echoes the label + the sentence naming the pin
    fm = e.manifest
    assert fm["status"].startswith("PROOF-ONLY, NOT-DELIVERABLE")
    assert fm["edit"]["gates"]["base_provenance"]["reason"] == reason


def test_second_generation_edit_still_descends(tmp_path_factory, tmp_path):
    """An edit of an EDIT keeps descending (the chain never decays into
    user-base while the bytes still say so)."""
    import rvt.frontdoor as FD
    c, e = _chain(2026, tmp_path_factory)
    y = e.manifest["output"]["path"]
    e2 = FD.author(rvt=y, edit="set level 311 elevation to 1 ft", out=str(tmp_path / "e2"))
    assert e2.ok, (e2.status, e2.errors)
    g = _job_gate(e2.manifest)
    assert g["base_kind"] == "descends-from-pinned-genesis"
    assert g["residue"]["descent"]["share"] >= 0.99
    lvl = [m for m in g["modified_elements"] if m["id"] == 311]
    assert [(m["provenance"], m.get("edited")) for m in lvl] == [("ours-composed", True)]
    assert g["provenance_totals"] == _job_gate(e.manifest)["provenance_totals"]


def test_lineage_api(tmp_path_factory):
    """rvt.frontdoor.census.lineage / pin_file: exact pin, descendant, nothing."""
    from rvt.mutate import Document
    pin = _pinned(2026)
    lin = C.lineage(pin)
    assert lin.exact and lin.kind == C.KIND_PINNED == "pinned-composed-genesis"
    assert lin.pin_doc is None and lin.pin_path == os.path.abspath(pin)
    assert lin.composed_baseline().residue_ids == C.for_file(pin).residue_ids
    assert lin.composed_baseline().pinned_id == "G_ABPD"
    assert lin.summary() == C.for_file(pin).summary()             # unchanged since #143
    assert C.pin_file(2026) == ("G_ABPD", pin, B.PIN.release_slot(2026)["sha256"])
    assert C.pin_file(2019) == (None, None, None) == C.pin_file(None)
    c, _e = _chain(2026, tmp_path_factory)
    x = c.manifest["build"]["files"]["combined"]["path"]
    d = C.lineage(x)
    assert d is not None and not d.exact and d.kind == C.KIND_DESCENDS == "descends-from-pinned-genesis"
    assert d.pinned_id == "G_ABPD" and d.pin_path == os.path.abspath(pin)
    assert d.pin_doc is not None and set(d.pin_doc.et_by_id) == set(Document.from_file(pin).et_by_id)
    assert d.composed_baseline() == lin.composed_baseline()       # the SAME census either way
    assert d.evidence["share"] >= 0.99 and d.evidence["pin_slots_probed"] == 2680
    assert C.lineage(x, Document.from_file(x)) == d                # an open doc spares the parse
    assert C.lineage(x, exact_only=True) is None                  # bytes-only: not a pin
    assert C.lineage(None) is None and C.lineage(str(tmp_path_factory.mktemp("n") / "nope.rvt")) is None


def test_no_byte_descent_keeps_user_base(job, tmp_path_factory, monkeypatch):
    """A file that shares ids -- even the History episode -- with the pin but
    NOT its bytes does not descend: it stays user-base, worded as such, and
    nothing inherited is presumed ours (the fail-safe direction)."""
    import rvt.provenance as P
    c, e = _chain(2026, tmp_path_factory)
    x = c.manifest["build"]["files"]["combined"]["path"]
    y = e.manifest["output"]["path"]
    monkeypatch.setattr(P, "same_records", lambda a, b, eid: False)     # "every slot differs"
    assert C.lineage(x) is None
    g = job.provenance_gate(y, x)
    assert g["base_kind"] == "user-base" and "residue" not in g
    assert g["status"] == "PROOF-ONLY, NOT-DELIVERABLE"
    assert "user-supplied base with no authorship census" in g["reason"]
    assert g["provenance_totals"].get("autodesk-sample", 0) > 3000       # everything inherited
    monkeypatch.undo()
    monkeypatch.setattr(C, "DESCENT_MIN_IDENTICAL", 1.01)                # the bar decides, nothing else
    assert C.lineage(x) is None and job.classify_base(x) == ("user-base", None)
    monkeypatch.undo()
    g = job.provenance_gate(y, x, skip=True)                             # --no-provenance never parses
    assert g["base_kind"] == "user-base" and g["status"].startswith("SKIPPED")


@pytest.mark.skipif(not os.path.isfile(os.path.join(
    ROOT, "tekton-eval-kit", "TEST-KIT", "02_created_room_shell_with_geometry.rvt")),
    reason="eval-kit specimen absent")
def test_a_relative_that_is_not_a_descendant_stays_user_base(job):
    """Real bytes: an older tekton output that carries every pin id AND the
    pin's History[0] episode, but only ~64 % of the composed slots
    byte-identical (grown on an earlier rung).  Not a descendant of THESE
    certified bytes -> no census can vouch for it -> user-base.  This is why
    the episode GUID is evidence, never the test."""
    p = os.path.join(ROOT, "tekton-eval-kit", "TEST-KIT", "02_created_room_shell_with_geometry.rvt")
    assert C.history_head_guid(p) == C.history_head_guid(_pinned(2026))
    assert C.lineage(p) is None
    assert job.classify_base(p) == ("user-base", None)


def test_residue_slot_edited_upstream_stays_derived(tmp_path_factory, tmp_path):
    """Real bytes: an earlier edit changed a RESIDUE slot (set-mark on an
    Autodesk-identical GStyleElem); a later edit that leaves it alone still
    ledgers it ours-modified (derived) -- never promoted to ours / sample."""
    import rvt.frontdoor as FD
    from rvt.mutate import Document
    from rvt.provenance import _cls
    c, _e = _chain(2026, tmp_path_factory)
    x = c.manifest["build"]["files"]["combined"]["path"]
    pin = Document.from_file(_pinned(2026))
    slot = min(e for e in C.for_file(_pinned(2026)).residue_ids if _cls(pin, e) == "GStyleElem")
    e1 = FD.author(rvt=x, edit=json.dumps({"ops": [{"op": "set-mark", "id": slot, "mark": "ZZ"}]}),
                   out=str(tmp_path / "m1"))
    assert e1.ok, (e1.status, e1.errors)
    g1 = _job_gate(e1.manifest)
    assert g1["base_kind"] == "descends-from-pinned-genesis"
    assert g1["provenance_totals"] == {"autodesk-sample": 421, "ours-modified": 1,
                                       "ours-created": 4, "ours-composed": 2680}
    e2 = FD.author(rvt=e1.manifest["output"]["path"], edit="set level 311 elevation to 1 ft",
                   out=str(tmp_path / "m2"))
    assert e2.ok, (e2.status, e2.errors)
    g2 = _job_gate(e2.manifest)
    assert g2["base_kind"] == "descends-from-pinned-genesis"
    assert g2["provenance_totals"] == g1["provenance_totals"]           # left alone, still derived
    mods = {m["id"]: (m["provenance"], m.get("edited")) for m in g2["modified_elements"]}
    assert mods[slot] == ("ours-modified", None) and mods[311] == ("ours-composed", True)
    assert "421 of the pin's 422 residue slots still aboard" in g2["reason"]
    assert "1 more edited along the way and still derived" in g2["reason"]


def test_provenance_cli_composed_base_auto(tmp_path_factory, tmp_path):
    """tools/provenance.py --composed-base auto ledgers a descendant against
    the pin it descends from with the pin's census (same element reading as
    the gate), skips the stream ledger honestly, and is the fallback when no
    sample baseline resolves (a fresh clone)."""
    prov = _load_tool("provenance")
    c, e = _chain(2026, tmp_path_factory)
    y = e.manifest["output"]["path"]
    js = tmp_path / "prov.json"
    rc = prov.main([y, "--composed-base", "auto", "--no-strings", "-q", "--json", str(js)])
    assert rc == 2                                            # G1 fails honestly, never certifies
    with open(js) as fh:
        rep = json.load(fh)
    assert rep["baseline_kind"] == "pinned-composed-genesis"          # the PIN is the baseline
    assert rep["composed_base"]["kind"] == "descends-from-pinned-genesis"
    assert rep["composed_base"]["pinned_id"] == "G_ABPD"
    assert "streams" not in rep["layers"] and rep["gate_G1"]["certifies_G1"] is False
    assert rep["provenance_totals"] == _job_gate(e.manifest)["provenance_totals"]
    # no samples/ in a fresh clone: --baseline all falls back to the same reading
    if not prov.sample_paths():
        js2 = tmp_path / "prov2.json"
        assert prov.main([y, "--baseline", "all", "--no-strings", "-q", "--json", str(js2)]) == 2
        with open(js2) as fh:
            assert json.load(fh)["provenance_totals"] == rep["provenance_totals"]
    assert prov.main([y, "--composed-base", "auto", "--baseline", "self", "-q"]) == 1
