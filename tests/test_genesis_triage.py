"""Tests for tools/genesis_triage.py (the Bug-A K-ladder bisection tool).

They exercise the tool's own machinery on the smallest certified anchor
(experiments/genesis/R9.rvt): the family-layer linking rules, the coherent
embedded-document removal (all four document registries), the exact-id
ADocument purge, and one end-to-end crux path (K3-style usage-null +
K4-style layer/document removal) — every emitted file must be walker /
CRC / ECC clean and pass the validator with ZERO errors.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

R9 = os.path.join(ROOT, "experiments", "genesis", "R9.rvt")
pytestmark = pytest.mark.skipif(not os.path.exists(R9),
                                reason="R9.rvt (viewer-PASSED reduction anchor) not present")

import genesis_triage as GT   # noqa: E402


@pytest.fixture(scope="module")
def st9():
    return GT.RR.build_state_v2(R9)


def test_census_coherence_of_r9_anchor():
    """The certified anchor is coherent on all four document registries."""
    c = GT.census(R9)
    assert c["elements"] == 3709
    assert c["save_units"] - 1 == c["contentdocs_entries"] == c["contenttable_records"] == 52
    assert c["familymgr_entries"] == 50 and c["familymgr_doc_guids"] == 52
    assert c["contentdocs_clean_tail"] is True
    assert c["adocument_clean"] is True


def test_family_layer_linking_rules(st9):
    """The loadable-family layer = 13 loadable families + their symbols
    (m_familyId) + surrogates (m_elemId) + m_famId-scoped children; the 8
    curtain SYSTEM families (document-less) are excluded."""
    lay = GT.family_layer(st9)
    cls_of = st9["cls_of"]
    fams = [e for e in lay["ids"] if cls_of.get(e) == "Family"]
    assert len(fams) == 13, len(fams)
    names = set(lay["families"].values())
    assert "A1 metric" in names and "M_View Title" in names
    assert not any("Mullion" in (n or "") or "System Panel" in (n or "") for n in names)
    classes = {c for c, _n in lay["children_by_class"]}
    # symbols / surrogates / children captured through the correct fields
    for c in ("FamilySymbol", "FamilySurrogate", "FamSymSurrogate",
              "ParamElemFamily", "CategoryElem", "GStyleElem", "FontElem"):
        assert c in classes, c
    assert len(lay["ids"]) > 300
    assert len(lay["docs"]) >= 13


def test_layer_referrers_are_only_usage_fields(st9):
    """Everything outside the layer that references it is a USAGE field the
    K3 rung nulls -- a small fixed set, not project infrastructure."""
    lay = GT.family_layer(st9)
    F = lay["ids"]
    host = st9["host"]
    outside = set()
    for f in F:
        for r in st9["referrers"].get(f, ()):
            if r in host and r not in F:
                outside.add(st9["cls_of"].get(r))
    allowed = {"LevelAttributes", "GridAttributes", "ViewportAttributes",
               "SectionAttributes", "InteriorElevAttributes", "CalloutTag",
               "StructSettingsElem", "CopyWatchProperties", "DBViewDrafting",
               "AreaReportSettingsElem", "LegendComponent", "BasicWallType",
               "FloorAttributes"}
    assert outside <= allowed, sorted(outside - allowed)


def test_remove_documents_is_coherent_and_valid(tmp_path):
    """Coherent removal of R9's 38 orphan documents (the KD1 recipe): the
    four GUID registries stay in step, no removed GUID byte survives in
    Latest / ContentDocuments, and the file passes the validator."""
    orphans = GT._r9b_removed_guids()
    assert len(orphans) == 38
    out = str(tmp_path / "kd1.rvt")
    rep = GT.remove_documents(R9, out, orphans, reconcile_contenttable=True,
                              reconcile_familymgr=True)
    assert rep["units_before"] == 53 and rep["units_after"] == 15
    assert rep["cd_entries_before"] == 52 and rep["cd_entries_after"] == 14
    assert rep["cd_tail_ok"] is True
    assert rep["contenttable_records_after"] == 14
    assert rep["familymgr_doc_guids_removed"] == 38
    assert sum(GT._residual_guid_hits(out, orphans).values()) == 0
    c = GT.census(out)
    assert c["save_units"] - 1 == c["contentdocs_entries"] == c["contenttable_records"] == 14
    assert c["familymgr_doc_guids"] == 14
    assert GT.verify_reduced(out, [])["ok"] is True
    v = GT.validate(out)
    assert v["ok"] and v["errors"] == 0, v.get("error_messages")


def test_purge_ids_from_latest_removes_exactly_the_deleted_ids(tmp_path):
    """The exact-id ADocument purge (K5x/K6) nulls/drops ONLY the ids handed
    to it; every other reference (incl. inherited dangling ones) is kept."""
    import genesis_assemble as GA
    from rvt import adocument as A
    from rvt.container import open_rvt

    def leaf_ids(path):
        with open_rvt(path) as f:
            a = A.decode_latest(f.inflate("Global/Latest"))
        ed = GA.AdocGraphEditor(maps=GA.load_registry_maps())
        ids = set()
        for cls_name, body in GA._appinfo_bodies(a.value):
            for lf in ed.iter_leaves(body, cls_name, cls_name) or []:
                if isinstance(lf.value, int) and lf.value > 0:
                    ids.add(lf.value)
        return ids

    before = leaf_ids(R9)
    victims = sorted(before)[:3] + [max(before)]
    out = str(tmp_path / "purged.rvt")
    rep = GT.purge_ids_from_latest(R9, out, victims)
    after = leaf_ids(out)
    assert rep["purged_ids"] == len(set(victims))
    assert not (set(victims) & after)
    assert (before - set(victims)) == after
    v = GT.validate(out)
    assert v["ok"] and v["errors"] == 0


def test_end_to_end_crux_path_k3_then_k4(st9, tmp_path, monkeypatch):
    """The K3 -> K4 crux path in miniature, into a temp dir: null the
    family-usage fields (modify), then remove the whole loadable layer and
    ALL embedded documents together.  Result: zero units 1..k, zero
    ContentDocuments entries, zero ContentTable / FamilyMgr documents, no
    loadable Family element, walker+validator clean."""
    monkeypatch.setattr(GT, "TRIAGE", str(tmp_path))
    lay = GT.family_layer(st9)
    k3 = str(tmp_path / "k3.rvt")
    nrep = GT.neutralise_referrers(st9, lay["ids"], k3, name="test-K3")
    assert nrep["verify"]["walker_errors"] == 0 and nrep["verify"]["stamps_ok"]
    v3 = GT.validate(k3)
    assert v3["ok"] and v3["errors"] == 0
    # K4 body
    _r, guid_of_unit = GT._unit_guid_map(k3)
    rep = GT._delete_layer_after_docs(
        "test-K4", k3, set(lay["ids"]), set(guid_of_unit),
        desc="test", tests="test", pass_means="test", fail_means="test")
    assert rep["structural_ok"] and rep["validator"]["errors"] == 0
    c = rep["census"]
    assert c["save_units"] == 1 and c["contentdocs_entries"] == 0
    assert c["contenttable_records"] == 0 and c.get("familymgr_doc_guids") == 0
    assert (c["classes"].get("FamilySymbol") or 0) == 0
    assert (c["classes"].get("Family") or 0) == 8            # the curtain SYSTEM families stay
    assert rep["layer_gc"]["deleted"] > 350


def test_probes_manifest_and_census_records_are_consistent():
    """If the ladder has been built, its manifest is ordered, every probe is
    validator-clean, and the census names the top singleton suspect."""
    import json
    man = os.path.join(GT.TRIAGE, "probes.json")
    if not os.path.exists(man):
        pytest.skip("probes.json not built (run tools/genesis_triage.py)")
    with open(man) as fh:
        m = json.load(fh)
    files = [p["file"] for p in m["probes"]]
    assert files and files[0].endswith("K4.rvt"), "the crux probe leads the order"
    for p in m["probes"]:
        assert p["validator"]["ok"] is True and p["validator"]["errors"] == 0, p["file"]
        assert p["self_check_failed"] is False
        for key in ("the_ONE_thing_it_tests", "what_it_removes", "if_PASS", "if_FAIL",
                    "derived_from", "order_rationale"):
            assert p.get(key), (p["file"], key)
    if os.path.exists(GT.CENSUS_MD):
        txt = open(GT.CENSUS_MD).read()
        assert "PenWidthTableElem" in txt and "SUSPECTS" in txt
