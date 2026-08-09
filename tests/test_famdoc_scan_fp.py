"""Tests for the donor-id byte-scan CORROBORATION at famdoc_adoc's raise
sites (issue #12, record docs/inbox/famdoc-scan-fp.md).

The zero-donor gate byte-scans the authored family ADocument payload for the
archetype's element ids (every offset read as a little-endian i64).  That
scan has a documented false-positive class: an id-shaped window straddling
two fields -- e.g. a monotone position-index / slot table read one byte off
yields ``k<<8``, and the 2025 base really carries element 18432 == 72<<8
(docs/inbox/build-2025.md §3).  The fix adjudicates every window hit against
the schema-DECODED tree of the same, byte-exact payload: a donor id some
integer leaf actually holds stays a hit (fatal); a window no leaf holds is
recorded as ``false_positive_windows`` and is not fatal.

Everything here runs in a fresh clone: the family document is OUR
constructive panelboard (schema from the bundled genesis base), the donor id
universe is synthetic and chosen FROM the payload so both the false-positive
and the genuine case are proven present before they are asserted on.
"""
from __future__ import annotations

import os
import struct

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED_BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
BUNDLED_2025 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt")
GA_TOOL = os.path.join(ROOT, "tools", "genesis_assemble.py")

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(BUNDLED_BASE) and os.path.isfile(GA_TOOL)),
    reason="plugin bundle base or the genesis-2 assembler absent")

from rvt.famgen import famdoc_adoc as FA                    # noqa: E402

#: our family's element ids start here, so the self-Family id (== START_ID)
#: is >= the scan's 4700 floor and is serialized as an i64 ElementId leaf
START_ID = 18400


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def authored():
    """OUR constructive panelboard family document, authored once:
    ``{"doc", "tree" (the source archetype), "ad" (author result)}``."""
    from rvt.frontdoor import standalone as SA
    from rvt.famgen import factory as F
    SA.install_schema(BUNDLED_BASE)
    doc = F.make_panelboard(start_id=START_ID).doc
    if not doc.finalized:
        doc.finalize()
    tree = FA.constructive_family_host_tree(doc)
    return {"doc": doc, "tree": tree, "ad": FA.author_family_adocument(doc, source_tree=tree)}


def _int_leaves(node, out=None) -> set:
    """Every integer leaf of a decoded value tree (test-local, recursive --
    the fixture premise must not lean on the walker under test)."""
    out = set() if out is None else out
    if isinstance(node, dict):
        for v in node.values():
            _int_leaves(v, out)
    elif isinstance(node, list):
        for v in node:
            _int_leaves(v, out)
    elif isinstance(node, int) and not isinstance(node, bool):
        out.add(node)
    return out


def _id_shaped_windows(payload: bytes, floor: int = 4700) -> set:
    """Every little-endian i64 window value >= ``floor`` with a zero high
    dword -- exactly the values ``byte_scan_ids`` can ever report."""
    out = set()
    for off in range(len(payload) - 7):
        if payload[off + 4] or payload[off + 5] or payload[off + 6] or payload[off + 7]:
            continue
        v = struct.unpack_from("<q", payload, off)[0]
        if v >= floor:
            out.add(v)
    return out


@pytest.fixture(scope="module")
def misaligned_window(authored):
    """A ``k<<8`` window value present in OUR payload that NO integer leaf of
    the decoded tree holds -- the build-2025 false-positive class, found (not
    assumed) in the authored payload."""
    payload, value = authored["ad"]["payload"], authored["ad"]["value"]
    cands = sorted(v for v in _id_shaped_windows(payload) - _int_leaves(value)
                   if v % 256 == 0 and v < (1 << 24))
    assert cands, "no misaligned k<<8 window in the authored payload -- fixture premise"
    return cands[0]


@pytest.fixture(scope="module")
def self_family_id(authored):
    """An id the decoded tree REALLY carries as an i64 ElementId leaf (our
    self-Family) -- the stand-in for a genuine donor reference."""
    ad = authored["ad"]
    fam = int(ad["inventory"].self_family_id)
    assert fam >= 4700 and ad["value"]["m_ownerFamilyId"] == fam
    return fam


def _raw_scan(authored, ids):
    return FA._ga().byte_scan_ids(authored["ad"]["payload"], set(ids))


def _corroborated(authored, ids, tree=None):
    ad = authored["ad"]
    return FA.corroborated_donor_scan(ad["payload"], ad["value"] if tree is None else tree,
                                      set(ids))


def _with_donor_universe(monkeypatch, tree: dict, donor_ids):
    """Route ``author_family_adocument``'s archetype to ``tree`` with a
    SYNTHETIC donor element-id universe (the vendor .rfa is never read)."""
    meta = {"donor": "(synthetic archetype)", "donor_element_ids": sorted(donor_ids)}
    monkeypatch.setattr(FA, "family_template_tree", lambda donor=None: (tree, meta))


# ---------------------------------------------------------------------------
# 1. the corroboration itself
# ---------------------------------------------------------------------------

def test_misaligned_window_is_recorded_not_counted(authored, misaligned_window):
    """The raw scan hits the cross-field window; corroboration moves it to
    ``false_positive_windows`` and counts zero genuine hits."""
    raw = _raw_scan(authored, {misaligned_window})
    assert raw["hits"] >= 1 and raw["examples"] == [misaligned_window]
    r = _corroborated(authored, {misaligned_window})
    assert r["hits"] == 0 and r["distinct"] == 0 and r["examples"] == []
    assert r["false_positive_windows"] == [misaligned_window]
    assert r["raw_window_hits"] == raw["hits"] and r["raw_window_distinct"] == raw["distinct"]
    assert r["false_positive_windows_complete"] is True
    assert "cross-field" in r["false_positive_note"]


def test_tree_corroborated_id_stays_a_hit(authored, self_family_id):
    """An id the decoded tree really carries, declared as a donor id: the hit
    survives corroboration."""
    assert _raw_scan(authored, {self_family_id})["hits"] >= 1
    r = _corroborated(authored, {self_family_id})
    assert r["hits"] >= 1 and r["examples"] == [self_family_id]
    assert r["false_positive_windows"] == []


def test_mixed_universe_splits_genuine_from_window(authored, self_family_id,
                                                   misaligned_window):
    """Both at once: the genuine id is counted, the window is recorded."""
    universe = {self_family_id, misaligned_window}
    assert _raw_scan(authored, universe)["distinct"] == 2
    r = _corroborated(authored, universe)
    assert r["examples"] == [self_family_id] and r["hits"] >= 1
    assert r["false_positive_windows"] == [misaligned_window]


def test_unverifiable_premise_keeps_raw_hits(authored, misaligned_window):
    """If the payload is NOT the exact encoding of the tree handed in, nothing
    is reclassified -- the raw hits stand (strictness is the default)."""
    raw = _raw_scan(authored, {misaligned_window})
    value = authored["ad"]["value"]
    other_tree = dict(value, m_ownerFamilyId=int(value["m_ownerFamilyId"]) + 1)
    r = _corroborated(authored, {misaligned_window}, tree=other_tree)
    assert r["hits"] == raw["hits"] and r["examples"] == raw["examples"]
    assert r["corroboration"].startswith("skipped")
    assert "false_positive_windows" not in r


def test_no_hits_is_the_plain_scan(authored):
    assert _corroborated(authored, {987654321}) == {"hits": 0, "distinct": 0, "examples": []}


def test_tree_int_leaves_counts_every_integer_under_any_key(authored):
    """The corroboration walker is a strict SUPERSET of the id-named census
    (it errs towards 'genuine'): every int leaf, whatever its key."""
    value = authored["ad"]["value"]
    assert FA._tree_int_leaves(value) == _int_leaves(value)
    assert FA._tree_int_leaves({"m_count": 5, "xs": [7, {"m_ownerFamilyId": 9}],
                                "flag": True, "s": "12"}) == {5, 7, 9}


# ---------------------------------------------------------------------------
# 2. the author raise site
# ---------------------------------------------------------------------------

def test_author_site_does_not_raise_on_the_misaligned_window(authored, misaligned_window,
                                                             monkeypatch):
    """Reproduces build-2025 §3 at the raise site: a donor universe that
    intersects our payload only through a cross-field window.  Before the
    fix: ``RuntimeError: donor element ids survive``.  Now: authored, with
    the window named in the gate report."""
    _with_donor_universe(monkeypatch, authored["tree"], {misaligned_window})
    ad = FA.author_family_adocument(authored["doc"])
    gate = ad["report"]["gates"]["byte_scan_donor_ids"]
    assert gate["hits"] == 0 and gate["universe"] == 1
    assert gate["false_positive_windows"] == [misaligned_window]
    assert "byte-scan donor ids = 0" in ad["report"]["conclusion"]


def test_author_site_still_raises_on_a_genuine_donor_id(authored, self_family_id,
                                                        monkeypatch):
    """A donor id the authored tree genuinely carries stays FATAL (rule 3)."""
    _with_donor_universe(monkeypatch, authored["tree"], {self_family_id})
    with pytest.raises(RuntimeError, match="donor element ids survive"):
        FA.author_family_adocument(authored["doc"])


def test_author_site_raises_on_genuine_even_beside_a_window(authored, self_family_id,
                                                            misaligned_window, monkeypatch):
    """A false-positive window in the same scan never masks a genuine hit."""
    _with_donor_universe(monkeypatch, authored["tree"], {self_family_id, misaligned_window})
    with pytest.raises(RuntimeError, match="donor element ids survive"):
        FA.author_family_adocument(authored["doc"])


# ---------------------------------------------------------------------------
# 3. the provenance ledger site (provenance_scan_v2 on an emitted .rfa)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def emitted_rfa(authored, tmp_path_factory):
    path = str(tmp_path_factory.mktemp("scanfp") / "panel.rfa")
    FA.emit_family_rfa_v2(authored["doc"], path, donor=BUNDLED_BASE, timestamp=0,
                          write_reports=False)
    return path


def _scan_with_universe(monkeypatch, rfa, donor_ids):
    monkeypatch.setattr(FA, "donor_element_ids",
                        lambda donor=None, min_id=4700: sorted(donor_ids))
    return FA.provenance_scan_v2(rfa, donor=BUNDLED_BASE)


def test_provenance_scan_records_the_window_and_stays_clean(emitted_rfa, misaligned_window,
                                                            monkeypatch):
    rep = _scan_with_universe(monkeypatch, emitted_rfa, {misaligned_window})
    scan = rep["adocument"]["byte_scan_donor_ids"]
    assert scan["universe"] == 1 and scan["hits"] == 0
    assert scan["false_positive_windows"] == [misaligned_window]
    assert rep["checks"]["zero_donor_id_byte_hits"] is True


def test_provenance_scan_flags_a_genuine_donor_id(emitted_rfa, self_family_id, monkeypatch):
    rep = _scan_with_universe(monkeypatch, emitted_rfa, {self_family_id})
    scan = rep["adocument"]["byte_scan_donor_ids"]
    assert scan["hits"] >= 1 and scan["examples"] == [self_family_id]
    assert rep["checks"]["zero_donor_id_byte_hits"] is False
    assert rep["ok"] is False


def test_provenance_scan_on_the_real_bundled_universe_is_clean(emitted_rfa):
    """Unpatched: the bundled base's own id universe against our emitted
    family -- clean, and any window collision is named, not fatal."""
    rep = FA.provenance_scan_v2(emitted_rfa, donor=BUNDLED_BASE)
    scan = rep["adocument"]["byte_scan_donor_ids"]
    assert scan["universe"] > 0
    assert rep["checks"]["zero_donor_id_byte_hits"] is True, scan


# ---------------------------------------------------------------------------
# 4. the release_ctx mitigation is gone (the fix lives at the raise sites)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.isfile(BUNDLED_2025), reason="bundled 2025 base absent")
def test_release_ctx_no_longer_wraps_the_byte_scan():
    from rvt import versions as V
    if 2025 not in V.SUPPORTED_CREATION_RELEASES:
        pytest.skip("2025 not creation-certified: the context would refuse the base")
    from rvt.frontdoor import release_ctx as RC
    GA = FA._ga()
    scan = GA.byte_scan_ids
    with RC.release_build_context(BUNDLED_2025) as info:
        assert info and info["release"] == 2025
        assert GA.byte_scan_ids is scan
    assert GA.byte_scan_ids is scan
