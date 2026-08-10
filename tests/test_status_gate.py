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
    upstream stay derived, and a file with no byte descent keeps user-base;
    and the front door's OWN edit manifest echoes that gate like the create
    routes' build.status_gate (kind / residue / ledgered_against / totals,
    the base-authorship line, the label as a stamp -- issue #406);
  * the hardening of issue #303: the census tool's laws ("changed => landed"
    per rung, the phase-2 deletion reconciliation, chain == byte truth) void
    the census when broken (exit 1, nothing written); the DELIVERABLE label
    needs a CERTIFIED G1 and G3 cleared, never `g1.passes` alone; and a
    STALE / UNAVAILABLE census is SAID in the front door's manifest.json +
    MANIFEST.md instead of reading as a plain user-supplied base.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
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
    """The certified PINNED base of ``year`` -- or a clean skip: the bundle may
    be absent, and ``$RVT_GENESIS_BASE`` may point the resolver at a firm's
    own (non-pinned) base, whose authorship these tests cannot speak to."""
    try:
        rb = B.resolve_base(target_release=year)
    except B.BaseError as e:                          # pragma: no cover - bundle absent
        pytest.skip(f"pinned base for {year} unavailable: {e}")
    if not (rb.pinned and rb.certified):              # pragma: no cover - override in force
        pytest.skip(f"Revit {year}: the resolved base is not the certified pin "
                    f"({rb.path}; $RVT_GENESIS_BASE / --base override) -- census tests are of the pin only")
    return rb.path


@pytest.fixture(scope="module")
def built(census_tool):
    """(census, audit) from ONE deterministic un-patched ``build_census`` --
    skipping, not erroring, when a base override is in force (the tool
    refuses anything but the pins, by design)."""
    audit: dict = {}
    try:
        return census_tool.build_census(audit), audit
    except B.BaseError as e:                          # pragma: no cover - override in force
        pytest.skip(str(e))


CERTIFIED_YEARS = [y for y in B.PIN.release_years() if B.release_status(y)["certified"]]


# ---------------------------------------------------------------------------
# 1. the census asset
# ---------------------------------------------------------------------------
def test_census_asset_is_current(census_tool, built):
    """tools/genesis_census.py check: the shipped JSON rebuilds byte-identically
    from the tracked evidence (re-pin without rebuilding => red here)."""
    with open(C.CENSUS_PATH) as fh:
        assert fh.read() == census_tool.dumps(built[0]), \
            "genesis_census.json is STALE — run tools/genesis_census.py build"


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


def test_2026_chain_method_agrees_with_byte_ground_truth(built):
    """The rung-chain derivation reproduces residue_c/census.json (seq-102
    compare vs the K4 ancestor) id for id: 422 identical, 11 never authored."""
    c = C.for_file(_pinned(2026))
    assert c is not None and c.base_id == "G_ABPD"
    raw = built[0]["bases"][c.sha256]
    cc = raw["cross_check"]
    assert cc["agree"] is True
    assert cc["truth_identical"] == cc["chain_identical"] == len(c.residue_ids) == 422
    assert len(c.never_authored_ids) == 11 and c.landed_but_identical == 411
    assert c.by_disposition["MACHINERY"] == 349 and sum(c.by_disposition.values()) == 422


# ---------------------------------------------------------------------------
# 1b. the census tool's LAWS (issue #303): broken evidence voids the census
# ---------------------------------------------------------------------------
def test_census_laws_hold_and_reconcile_on_every_pin(census_tool, built):
    """`check` exits 0 today: "changed => landed" holds on all rung reports of
    the three chains, and every id a rung changed that is no longer aboard the
    pin is a recorded phase-2 deletion (2026: 2,700 = 2,680 + 20; 2025:
    2,392 = 2,391 + 1; 2024: 2,356 = 2,355 + 1) -- the count-level truth for
    the two bases that have no byte-ground-truth census."""
    census, audit = built
    assert sorted(audit) == sorted(b["id"] for b in census["bases"].values()) == ["G_ABPD", "G_ABPD_2024", "G_ABPD_2025"]
    for base_id, rec in audit.items():
        assert rec["changed_in_chain"] == rec["changed_aboard"] + len(rec["changed_then_deleted"]), (base_id, rec)
        assert rec["landed_in_chain"] >= rec["changed_in_chain"] > 2000 and rec["phase_2_deleted"] >= 17
        b = next(v for v in census["bases"].values() if v["id"] == base_id)
        assert b["ours_by_composition"] == rec["changed_aboard"]           # "ours" == changed-and-aboard
    assert [len(audit[k]["changed_then_deleted"]) for k in ("G_ABPD", "G_ABPD_2025", "G_ABPD_2024")] == [20, 1, 1]
    assert census_tool.main(["check"]) == 0


@pytest.fixture(scope="module")
def real_index(census_tool):
    """The tracked evidence, globbed + parsed ONCE for every doctored variant."""
    return census_tool.ReportIndex()


def _doctored_index(real, mutate):
    """A ReportIndex class whose parsed docs `mutate(index)` tampers with -- a
    deep copy of the once-parsed real index; the tracked files are never touched."""

    class Doctored(type(real)):                            # type: ignore[misc]
        def __init__(self, *a, **kw):                      # no re-glob: copy, then tamper
            self.docs = copy.deepcopy(real.docs)
            self.by_out, self.truth = dict(real.by_out), dict(real.truth)
            mutate(self)
    return Doctored


def _inplace_docs(index):
    return [d for d in index.docs.values() if d.get("kind") == "inplace" and d.get("byte_delta")]


def _stray_change(index):          # a rung "changed" a record its constructor never landed
    for d in _inplace_docs(index):
        landed = {int(r["slot"]) for r in d.get("landed_slots") or [] if "slot" in r}
        bd = d["byte_delta"]
        key = "records_changed_ids" if "records_changed_ids" in bd else "changed_ids"
        if isinstance(bd.get(key), list) and landed:
            bd[key] = list(bd[key]) + [max(landed) + 999_999]


def _unexpected_flag(index):        # the rung's own certification recorded a stray change
    for d in _inplace_docs(index):
        d["byte_delta"]["unexpected_changed_ids"] = [424242]


def _assertion_fails(index):        # the rung's byte_delta assertion did not hold
    for d in _inplace_docs(index):
        d["byte_delta"]["assertion_holds"] = False
        d["byte_delta"]["problems"] = ["synthetic"]


def _truth_loses_one(index):         # the byte-ground-truth census and the chain now differ by one id
    for rp in index.truth.values():
        index.docs[rp]["elements"] = index.docs[rp]["elements"][1:]


@pytest.mark.parametrize("mutate,needle", [
    (_stray_change, "did not land"),                                  # the id sets themselves
    (_unexpected_flag, "unexpected_changed_ids = [424242]"),          # the rung report's own record
    (_assertion_fails, "assertion_holds is False"),
    (_truth_loses_one, "G_ABPD (2026): CHAIN vs BYTE TRUTH DISAGREE -- the chain says 422 identical"),
])
def test_census_tool_refuses_evidence_that_breaks_the_law(census_tool, real_index, monkeypatch, tmp_path,
                                                          capsys, mutate, needle):
    """'changed => landed by our constructor' (checked on the id sets AND on
    each rung report's own unexpected_changed_ids / assertion_holds) and
    'chain == byte ground truth where one exists' are LAWS of the tool: a
    violation derives no census, `build` writes NOTHING and `check` exits 1 --
    so the shipped asset stays the last census the evidence supported (a
    changed pin then reads STALE in the gate = the conservative ledger)."""
    _pinned(2026)
    monkeypatch.setattr(census_tool, "ReportIndex", _doctored_index(real_index, mutate))
    with pytest.raises(census_tool.LawViolation) as ei:
        census_tool.build_census()
    assert needle in str(ei.value)
    out = tmp_path / "census.json"
    assert census_tool.main(["build", "--out", str(out)]) == 1
    assert not out.exists()                                          # nothing written
    assert "LAW VIOLATED, no census derived (nothing written)" in capsys.readouterr().err
    assert census_tool.main(["check"]) == 1


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
# 2b. the DELIVERABLE flip (issue #303): certified G1 AND G3 cleared, only
# ---------------------------------------------------------------------------
def _passing_g1(certifies: bool):
    """A gate_G1 stub that PASSES with zero blockers -- certified or not."""
    layers = ["elements", "identity"] + (["streams", "strings"] if certifies else [])
    verdict = ("PASS — G1 CERTIFIED: …" if certifies else
               "PASS (elements+identity layer(s) ONLY) — NOT a G1 certification: streams, strings not ledgered")
    return lambda report, strict=False: {"passes": True, "certifies_G1": certifies,
                                         "layers": layers, "verdict": verdict, "blocking": []}


def test_deliverable_flip_needs_certified_g1_and_g3_cleared(job, monkeypatch):
    """The day #21/#19 zero the residue and re-mint the GUIDs, the element +
    identity ledger will PASS with 0 blockers -- and the label must STILL read
    PROOF-ONLY: an element-only pass is not a G1 certification, and G3
    counsel (#23) is a human gate the flag `G3_CLEARED` records.  Only a
    certified G1 with G3 cleared flips the LABEL; the file is delivered in
    every case (hard rule 1 -- the gate never touches it)."""
    assert job.G3_CLEARED is False                                    # owned by #23, open today
    for certifies, g3, flips in ((False, False, False), (True, False, False),
                                 (False, True, False), (True, True, True)):
        monkeypatch.setattr(job, "G3_CLEARED", g3)
        assert job.deliverable_now({"passes": True, "certifies_G1": certifies}) is flips, (certifies, g3)
    monkeypatch.setattr(job, "G3_CLEARED", False)

    path = _pinned(2026)
    P = job._provenance_mod()
    monkeypatch.setattr(P, "gate_G1", _passing_g1(certifies=False))
    with V.reading(path):
        g = job.provenance_gate(path, path)                           # a zero-blocker census, G3 open
    assert g["g1"]["passes"] is True and g["g1"]["blocking"] == []
    assert g["status"] == "PROOF-ONLY, NOT-DELIVERABLE" and g["deliverable"] is False
    assert "NOT a G1 certification" in g["reason"] and "G3 counsel (#23" in g["reason"]
    assert "is a human gate, open" in g["reason"] and "PROOF-ONLY is a label: the file is delivered" in g["reason"]
    assert os.path.isfile(path)                                       # nothing withheld, ever

    monkeypatch.setattr(P, "gate_G1", _passing_g1(certifies=True))
    monkeypatch.setattr(job, "G3_CLEARED", True)                      # the flag IS the switch (#23's PR)
    with V.reading(path):
        g = job.provenance_gate(path, path)
    assert g["status"] == "DELIVERABLE" and g["deliverable"] is True


# ---------------------------------------------------------------------------
# 2c. a STALE / UNAVAILABLE census REACHES the front door's manifests (#303)
# ---------------------------------------------------------------------------
def _walls_job(tmp_path, sub: str):
    import rvt.frontdoor as FD
    r = FD.author(prompt=WALLS_PROMPT, out=str(tmp_path / sub), no_handoff=True)
    assert r.ok, (r.status, r.errors)
    with open(os.path.join(str(tmp_path / sub), "MANIFEST.md")) as fh:
        return r.manifest, fh.read()


def test_census_unavailable_reaches_the_front_door_manifest(job, monkeypatch, tmp_path):
    """The product path (frontdoor author --prompt): if the census lookup
    cannot import, base_kind falls back to the name heuristic (user-base for
    our own pin) -- and manifest.json / MANIFEST.md SAY the census was
    UNAVAILABLE (status_gate.census, a build degradation, the base-authorship
    line) instead of presenting our pin as a plain user-supplied base.  The
    label stays PROOF-ONLY and the file is delivered."""
    _pinned(2026)
    monkeypatch.setitem(sys.modules, "rvt_job", job)                  # the module ifc_intent.status_gate imports
    monkeypatch.setattr(job, "_census_mod", lambda: None)
    monkeypatch.setitem(job.OPT.errors, "rvt.frontdoor.census", "ImportError: simulated")
    man, md = _walls_job(tmp_path, "u")
    assert os.path.isfile(man["build"]["files"]["combined"]["path"])   # delivered
    sg = man["build"]["status_gate"]
    assert sg["status"] == "PROOF-ONLY, NOT-DELIVERABLE" and sg["deliverable"] is False
    assert sg["base_kind"] == "user-base" and "residue" not in sg   # the fail-safe fallback ...
    assert sg["census"].startswith("UNAVAILABLE (ImportError: simulated)")   # ... SAID, not silent
    deg = [d for d in man["build"]["degradations"] if "authorship census UNAVAILABLE" in d]
    assert len(deg) == 1 and "conservative reading" in deg[0] and "hard rule 1" in deg[0]
    assert "census **UNAVAILABLE (ImportError: simulated)" in md
    assert "**degradation**: status-gate authorship census UNAVAILABLE" in md
    assert "base authorship: **user-base** (no census" not in md       # never the plain user-base line
    assert man["status"].startswith("PROOF-ONLY")
    assert sg["provenance_totals"].get("autodesk-sample", 0) > 3000    # over-states, never under-states


def test_stale_census_reaches_the_front_door_manifest(monkeypatch, tmp_path):
    """A re-pin without `tools/genesis_census.py build`: the gate says STALE
    and so do manifest.json (status_gate.census + a degradation) and
    MANIFEST.md; base_kind stays pinned-composed-genesis."""
    _pinned(2026)
    monkeypatch.setattr(C, "lookup", lambda p: ("G_ABPD", None) if p and os.path.isfile(p) else (None, None))
    man, md = _walls_job(tmp_path, "s")
    sg = man["build"]["status_gate"]
    assert sg["base_kind"] == "pinned-composed-genesis" and "residue" not in sg
    assert sg["census"].startswith("STALE") and "genesis_census.py build" in sg["census"]
    assert any("authorship census STALE" in d for d in man["build"]["degradations"])
    assert "census **STALE" in md and "census asset STALE" in sg["reason"]
    assert sg["status"] == "PROOF-ONLY, NOT-DELIVERABLE"


def test_applied_census_adds_no_note(tmp_path_factory):
    """The normal case (census applied, `residue` present): no census note,
    no degradation about it -- manifest.json carries the residue block."""
    from rvt.frontdoor.manifest import authorship_census_note
    c, _e = _chain(2026, tmp_path_factory)
    sg = c.manifest["build"]["status_gate"]
    assert sg["base_kind"] == "pinned-composed-genesis" and sg["residue"]["base_id"] == "G_ABPD"
    assert "census" not in sg and authorship_census_note(sg) is None
    assert not any("authorship census" in d for d in c.manifest["build"]["degradations"])
    assert authorship_census_note({"census": "STALE: x"}).startswith("status-gate authorship census STALE: x")
    assert authorship_census_note(None) is None and authorship_census_note({}) is None


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
    pin = C.for_file(_pinned(2026))                     # expected numbers come from the census itself
    assert sg["residue"]["base_id"] == pin.base_id == "G_ABPD" and "census" not in sg
    tot = sg["provenance_totals"]
    assert tot["ours-composed"] == pin.ours_by_composition and tot["autodesk-sample"] == len(pin.residue_ids)
    assert tot.get("ours-created", 0) >= 100            # walls + instances + loaded families
    assert not tot.get("transitive-cloned"), sg["created_elements"][:3]
    elements = [b for b in sg["g1"]["blocking"] if b.get("layer") is None]
    cats = {b["category"] for b in elements}
    assert not cats & {"loadable-families", "placed-model-content", "embedded-family-documents"}
    assert 100 < sum(b["count"] for b in elements) < 1000
    assert "sample base" not in sg["reason"] and "residue (#21)" in sg["reason"]
    # G2 is MEASURED: the count the sentence gives == the identity fields it names,
    # and every identity blocker the gate lists is among them
    g2 = re.search(r"G2 identity \(#19\): (\d+) inherited lineage identifier\(s\) still aboard \(([^)]*)\)",
                   sg["reason"])
    assert g2, sg["reason"]
    named = g2.group(2).split(", ")
    assert int(g2.group(1)) == len(named) >= 1
    ident = [b["category"].split(":", 1)[-1] for b in sg["g1"]["blocking"] if b.get("layer") == "identity"]
    assert ident and set(ident) <= set(named), (ident, named)
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


#: the base_provenance keys the front-door EDIT manifest echoes (#406),
#: pinned here independently of manifest._EDIT_GATE_KEYS on purpose (the
#: contract a skill session reads); the per-element lists (g1.blocking,
#: created/modified_elements) stay one hop away in edit.job_manifest
ECHOED = ("status", "deliverable", "base_is_autodesk_sample", "base_kind", "residue",
          "ledgered_against", "provenance_totals", "reason")
EDIT_LEDGER_OF = "this file's ledger (everything the chain created)"


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_edit_manifest_surfaces_the_gate_like_the_create_routes(year, tmp_path_factory):
    """#406: the front door's OWN manifest.json / MANIFEST.md of an edit say
    what the create routes' build.status_gate says -- base_kind, the pin's
    census + descent evidence, the pin it was ledgered against, the ledger
    totals -- and the P0 label is a STAMP (honesty.proof_only_stamps, the
    --json `stamps`), not only the status line.  Nothing about the label or
    the delivery changes (rule 1)."""
    from rvt.frontdoor.manifest import status_gate_lines
    c, e = _chain(year, tmp_path_factory)
    pin_name = os.path.basename(_pinned(year))
    g = _job_gate(e.manifest)                                  # the job runner's full gate
    fg = e.manifest["edit"]["gates"]["base_provenance"]       # the front door's echo of it
    assert {k: fg[k] for k in ECHOED} == {k: g[k] for k in ECHOED}
    assert set(fg) <= set(ECHOED) | {"census"}                # summaries only, no element lists
    assert fg["base_kind"] == "descends-from-pinned-genesis" and fg["base_is_autodesk_sample"] is False
    assert fg["residue"]["descends_from"] == B.PIN.release_slot(year)["id"]
    assert os.path.basename(fg["ledgered_against"]) == pin_name
    ct = c.manifest["build"]["status_gate"]["provenance_totals"]      # the create route's reading
    tot = fg["provenance_totals"]
    assert (tot["ours-composed"], tot["autodesk-sample"]) == (ct["ours-composed"], ct["autodesk-sample"])
    assert tot.get("ours-created", 0) + tot.get("transitive-cloned", 0) == 3      # 4 walls built, 1 deleted
    # the label is a stamp wherever a reader looks -- and the file is delivered
    assert "PROOF-ONLY, NOT-DELIVERABLE" in e.manifest["honesty"]["proof_only_stamps"]
    assert "PROOF-ONLY, NOT-DELIVERABLE" in e.as_json()["stamps"]
    assert e.manifest["status"].startswith("PROOF-ONLY, NOT-DELIVERABLE") and e.ok
    out = e.manifest["output"]["path"]
    assert os.path.isfile(out if os.path.isabs(out) else os.path.join(ROOT, out))
    assert not any("authorship census" in d for d in e.manifest["edit"]["degradations"])   # census applied
    # MANIFEST.md: the same lines the create routes print, worded for a descendant
    with open(e.manifest_paths["md"], encoding="utf-8") as fh:
        md = fh.read()
    lines = status_gate_lines(fg, ledger_of=EDIT_LEDGER_OF)
    assert len(lines) == 3 and all(ln in md for ln in lines), (lines, md)
    assert lines[0] == f"- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — {fg['reason']}"
    dsc = fg["residue"]["descent"]
    for cite in ("- base authorship (issue #143 census): **descends-from-pinned-genesis** — descends from "
                 f"{fg['residue']['descends_from']} (Revit {year}; ",
                 f"{dsc['probed_identical']:,} of {dsc['pin_slots_probed']:,} composed slots byte-identical, "
                 f"share {dsc['share']} ≥ 0.95), ledgered against the pin `{pin_name}` and its census — ",
                 f"{tot['ours-composed']:,} of {fg['residue']['host_elements']:,} base elements ours by composition"):
        assert cite in lines[1], (cite, lines[1])
    assert lines[2].startswith(f"- {EDIT_LEDGER_OF}: {tot.get('ours-created', 0)} created elements ours, ")
    assert "## Honesty\n- **PROOF-ONLY, NOT-DELIVERABLE** (a label: the file is delivered)" in md


def test_edit_manifest_words_a_foreign_base_and_a_downed_census_honestly(tmp_path):
    """The same echo for the other base kinds, on synthetic job manifests (no
    bytes needed): a user's own file reads user-base with the no-census line;
    our pin with a STALE census is SAID (one degradation + the census line,
    as on the create routes, #303); a gate that never classified prints no
    authorship line; a refused input (no job at all) stamps nothing."""
    from rvt.frontdoor import manifest as MF
    out = tmp_path / "y.rvt"
    out.write_bytes(b"x")

    def _man(gate):
        run = {"rc": 0, "out_rvt": str(out), "degradations": [],
               "job_manifest": {"status": "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)",
                                "hard_gates_passed": True,
                                "gates": {"validation": {"status": "PASS", "errors": 0, "warnings": 1,
                                                         "report": {"big": 1}, "extra": "dropped"},
                                          "base_provenance": dict(gate)}}}
        m = MF.edit_manifest(inputs={"rvt": "in.rvt", "edit": "x"}, base_note="n", out_dir=str(tmp_path),
                             edit_spec={"understood": []}, run=run)
        return m, MF._render_md(m)

    user = {"status": "PROOF-ONLY, NOT-DELIVERABLE", "deliverable": False, "base": "/abs/in.rvt",
            "base_is_autodesk_sample": False, "base_kind": "user-base",
            "g1": {"blocking": [{"count": 3283}]}, "created_elements": [], "modified_elements": [],
            "provenance_totals": {"autodesk-sample": 3345, "ours-modified": 1},
            "reason": "P0 genesis gate G1 fails (a user-supplied base with no authorship census; …)"}
    m, md = _man(user)
    fg = m["edit"]["gates"]["base_provenance"]
    assert fg["base_kind"] == "user-base" and fg["provenance_totals"] == user["provenance_totals"]
    assert not {"g1", "created_elements", "modified_elements", "base"} & set(fg)
    assert m["edit"]["gates"]["validation"] == {"status": "PASS", "errors": 0, "warnings": 1, "report": {"big": 1}}
    assert m["honesty"]["proof_only_stamps"] == ["PROOF-ONLY, NOT-DELIVERABLE"]
    assert "- base authorship: **user-base** (no census: everything inherited from the base is ledgered as the base's)" in md
    assert f"- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — {user['reason']}" in md
    assert m["edit"]["degradations"] == []

    stale = dict(user, base_kind="pinned-composed-genesis",
                 census="STALE: no census entry for the pinned G_ABPD bytes -- run tools/genesis_census.py build")
    m, md = _man(stale)
    assert m["edit"]["gates"]["base_provenance"]["census"].startswith("STALE")
    deg = [d for d in m["edit"]["degradations"] if "authorship census STALE" in d]
    assert len(deg) == 1 and "hard rule 1" in deg[0]
    assert "- base authorship: **pinned-composed-genesis** (census **STALE" in md
    assert "**degradation**: status-gate authorship census STALE" in md

    skipped = {"status": "SKIPPED (--no-provenance) => treated as NOT-DELIVERABLE", "deliverable": False,
               "reason": "provenance ledger not run; deliverability unproven"}
    m, md = _man(skipped)
    assert "base authorship" not in md and m["honesty"]["proof_only_stamps"] == []
    assert "- deliverability (P0 gate): SKIPPED (--no-provenance)" in md
    assert MF.status_gate_lines({}) == [] and MF.status_gate_lines(None) == []

    m = MF.edit_manifest(inputs={"rvt": "in.rvt", "edit": "x"}, base_note="n", out_dir=str(tmp_path),
                         edit_spec={}, run={}, errors=["refused"])
    assert m["edit"]["gates"] == {} and m["honesty"]["proof_only_stamps"] == []
    assert m["status"].startswith("FAILED") and "base authorship" not in MF._render_md(m)


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
