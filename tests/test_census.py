"""Tests for rvt.census -- the required-set census (positive-evidence
model of the mandatory element / stream / save-unit set) and its diffs."""
import os

import pytest

from rvt.census import (census, class_presence, count_shortfall, mandatory_set,
                        missing_from, rank_suspects, stream_unit_matrix,
                        load_certified, ROOT)

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G1 = os.path.join(ROOT, "experiments", "genesis", "G1_candidate.rvt")
R9 = os.path.join(ROOT, "experiments", "genesis", "R9.rvt")
R9B = os.path.join(ROOT, "experiments", "genesis", "R9b.rvt")


# ---------------------------------------------------------------------------
# real-file census (the smallest sample)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rst():
    return census(RST)


def test_rst_host_census_matches_elemtable(rst):
    # the host document is unit 0 of Partitions/<N>, ids == Global/ElemTable
    assert rst["elemtable_rows"] == 13936
    assert rst["host_records"] == 13936 == rst["unit0_records"]
    assert rst["n_classes"] > 250
    assert rst["classes"]["DBViewType"] == 91
    assert rst["classes"]["GStyleElem"] == 2183


def test_rst_units_and_coherence(rst):
    u, cd, coh = rst["units"], rst["content_documents"], rst["coherence"]
    assert u["total"] == 53 and u["guidless_units"] == 1
    assert u["family_documents"] == 52                    # 41 host + 11 nested docs
    assert cd["present"] and cd["entries"] == 52 and cd["clean_tail"]
    assert rst["adocument"]["content_table_records"] == 52
    assert coh["coherent"] is True
    assert coh["content_records_without_document"] == 0


def test_rst_streams_and_families(rst):
    for s in ("Global/Latest", "Formats/Latest", "Global/ElemTable",
              "Global/ContentDocuments", "Global/History", "BasicFileInfo"):
        assert s in rst["streams"]
    assert rst["partition_streams"] == ["Partitions/21"]
    fam = rst["families"]
    assert fam["host_families"] == 50
    assert fam["with_document"] == 41 and fam["without_document"] == 9
    # the 8 curtain-wall SYSTEM families carry no embedded document
    assert "System Panel" in fam["names_without_document"]


def test_rst_dbviewtype_reference_finding(rst):
    dv = rst["dbviewtype"]
    assert dv["n_viewtypes"] == 91
    assert dv["n_with_famId"] == 72                      # 9 view types x 8 curtain families
    assert dv["dangling_ref_fields"] == {}
    assert dv["field_target_classes"]["m_famId->Family"] == 72
    assert dv["field_target_classes"]["m_calloutAttrId->CalloutTag"] == 54
    # every famId target is a document-less curtain-wall system family
    assert all(k.endswith("(doc=no)") for k in dv["famId_families"])


# ---------------------------------------------------------------------------
# diff functions on synthetic censuses
# ---------------------------------------------------------------------------

def _c(name, classes, **kw):
    d = {"file": name, "classes": dict(classes), "host_records": sum(classes.values()),
         "n_classes": len(classes)}
    d.update(kw)
    return d


def test_mandatory_set_is_intersection_with_min_counts():
    a = _c("a", {"X": 5, "Y": 3, "Z": 1})
    b = _c("b", {"X": 2, "Y": 3, "W": 9})
    m = mandatory_set([a, b])
    assert list(m) == ["Y", "X"]                          # sorted by min desc
    assert m["X"] == {"n_files": 2, "min": 2, "max": 5}
    assert m["Y"] == {"n_files": 2, "min": 3, "max": 3}
    assert "Z" not in m and "W" not in m
    assert mandatory_set([]) == {}


def test_missing_from_and_shortfall():
    m = mandatory_set([_c("a", {"X": 5, "Y": 3}), _c("b", {"X": 4, "Y": 3})])
    f = _c("f", {"X": 1})                                # Y absent, X short
    assert missing_from(f, m) == ["Y"]
    sf = count_shortfall(f, m)
    assert sf == [{"class": "X", "have": 1, "min_in_passing": 4,
                   "max_in_passing": 5, "ratio": 0.25}]


def test_rank_suspects_orders_by_universality_then_min_count():
    p1 = _c("p1", {"CAT": 100, "SET": 1, "OPT": 4})
    p2 = _c("p2", {"CAT": 300, "SET": 1})               # OPT optional (absent here)
    f = _c("f", {"OTHER": 2})
    rep = rank_suspects([p1, p2], [f])
    miss = rep["failing"]["f"]["missing_core_classes"]
    assert [r["class"] for r in miss] == ["CAT", "SET"]  # OPT excluded (not in every file)
    assert miss[0]["min_count_in_passing"] == 100
    assert rep["failing"]["f"]["n_missing"] == 2


def test_class_presence_union_counts():
    pres = class_presence([_c("a", {"X": 1}), _c("b", {"X": 2, "Y": 1})])
    assert pres["X"]["n_files"] == 2 and pres["X"]["of"] == 2
    assert pres["Y"]["n_files"] == 1


def test_stream_unit_matrix_flags_missing_streams():
    a = {"file": "a", "streams": {"Global/Latest": 1, "Partitions/21": 2},
         "partition_streams": ["Partitions/21"],
         "units": {"total": 2, "family_documents": 1},
         "content_documents": {"entries": 1}, "adocument": {}, "coherence": {"coherent": True},
         "families": {"host_families": 1, "with_document": 1}}
    b = dict(a, file="b", streams={"Global/Latest": 1})
    m = stream_unit_matrix([a, b])
    assert m["streams_in_every_file"] == ["Global/Latest"]
    assert m["per_file"]["b"]["missing_streams"] == ["Partitions/21"]


def test_load_certified_lists():
    lists = load_certified()
    assert "experiments/genesis/R9.rvt" in lists["certified"]
    assert "experiments/genesis/R10b.rvt" in lists["failed"]


# ---------------------------------------------------------------------------
# the two-bug attribution, on the real probe files (skip if absent)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not (os.path.exists(R9) and os.path.exists(R9B)),
                    reason="reduction probes not on disk")
def test_bug_b_is_below_the_element_layer():
    """R9 (PASS) and R9b (FAIL) have IDENTICAL host element inventories; the
    only difference is the content-document machinery, and R9b's ContentTable
    still names the 38 spliced-out documents (= dangling content records)."""
    a, b = census(R9), census(R9B)
    assert a["classes"] == b["classes"]
    assert a["coherence"]["coherent"] is True
    assert b["units"]["family_documents"] == 14
    assert b["content_documents"]["entries"] == 14
    assert b["adocument"]["content_table_records"] == 52
    assert b["coherence"]["content_records_without_document"] == 38
    assert b["coherence"]["coherent"] is False


@pytest.mark.skipif(not (os.path.exists(G1) and os.path.exists(R9)),
                    reason="genesis files not on disk")
def test_bug_a_constructed_base_lacks_the_core_set():
    """The constructed genesis candidate misses the classes present in every
    accepted file (settings singletons / catalogs / families) -- Bug A."""
    g1, r9, rst_ = census(G1), census(R9), census(RST)
    mand = mandatory_set([r9, rst_])
    missing = missing_from(g1, mand)
    for cls in ("HVACLoadSpaceTypeElem", "Family", "FamilySymbol",
                "PenWidthTableElem", "BrowserOrganization", "KeynoteTable"):
        assert cls in missing
    assert g1["units"]["family_documents"] == 0
    assert g1["coherence"]["coherent"] is True           # coherent-but-empty
    short = {r["class"] for r in count_shortfall(g1, mand)}
    assert {"GStyleElem", "CategoryElem"} <= short


if __name__ == "__main__":                             # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
