"""Tests for the authorship PROVENANCE LEDGER (src/rvt/provenance.py).

Covers: the legal-category taxonomy (every class of every host element gets
a category), the four provenance verdicts on real files (autodesk-sample,
ours-created / transitive-cloned, ours-modified), embedded family-document
units, the G1 gate, the wrong-baseline safety net, and the CLI end to end.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import provenance as prv                                   # noqa: E402
from rvt.mutate import Document                                    # noqa: E402
from rvt.provenance import (P_CLONED, P_CREATED, P_MODIFIED, P_SAMPLE,
                            P_UNMATCHED, category_for_class, gate_G1,
                            provenance)                            # noqa: E402

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
V29 = os.path.join(ROOT, "experiments", "acceptance", "V29_room_with_circuits.rvt")
M3 = os.path.join(ROOT, "experiments", "acceptance", "M3_modify.rvt")
R2S = os.path.join(ROOT, "experiments", "genesis", "R2s.rvt")
PY = os.path.join(ROOT, ".venv", "bin", "python")
CLI = os.path.join(ROOT, "tools", "provenance.py")

pytestmark = pytest.mark.skipif(not os.path.exists(RST), reason="samples missing")


@pytest.fixture(scope="module")
def rst_doc():
    return Document.from_file(RST)


@pytest.fixture(scope="module")
def rme_doc():
    return Document.from_file(RME)


# ---------------------------------------------------------------------------
# taxonomy
# ---------------------------------------------------------------------------
def test_explicit_class_categories(rst_doc):
    s = rst_doc.dec.schema
    expect = {
        "Family": "loadable-families",
        "FamilySymbol": "family-types-symbols",
        "BasicWallType": "system-family-types",
        "FloorAttributes": "system-family-types",
        "RbsConduitType": "system-family-types",
        "DBViewPlan": "views-and-templates",
        "DBViewType": "views-and-templates",
        "CategoryElem": "object-styles",
        "GStyleElem": "object-styles",
        "FillPatternElem": "patterns-materials",
        "LinePatternElem": "patterns-materials",
        "MaterialElem": "patterns-materials",
        "TextNoteAttributes": "text-dimension-types",
        "DimensionStyle": "text-dimension-types",
        "LeaderStyle": "text-dimension-types",
        "ParamElemExternal": "parameter-definitions",
        "ParamBinding": "parameter-definitions",
        "ProjectPhase": "phases-design-options",
        "DesignOptionSet": "phases-design-options",
        "ProjectInfo": "project-info-settings",
        "UnitsElem": "project-info-settings",
        "ElectricalSetting": "project-info-settings",
        "RbsVoltageType": "mep-electrical-definitions",
        "ElectricalLoadClassification": "mep-electrical-definitions",
        "Level": "datums",
        "Grid": "datums",
        "SWall": "placed-model-content",
        "FamilyInstance": "placed-model-content",
        "RbsElectricalSystem": "placed-model-content",
        "CurveElem": "view-annotation-2d-content",
        "TextNote": "view-annotation-2d-content",
        "RegenSplitterElem": "internal-bookkeeping",
        "PostedWarningElem": "internal-bookkeeping",
    }
    for cls, cat in expect.items():
        assert category_for_class(s, cls) == cat, cls


def test_every_host_class_is_mapped(rst_doc, rme_doc):
    """The gate instrument must classify EVERY element: no 'unmapped' left in
    the reference samples (the taxonomy covers the whole class census)."""
    for doc in (rst_doc, rme_doc):
        unmapped = set()
        for eid in doc.et_by_id:
            cls = doc.class_of(eid) or "?"
            if category_for_class(doc.dec.schema, cls) == "unmapped":
                unmapped.add(cls)
        assert not unmapped, f"unmapped classes: {sorted(unmapped)}"


def test_annotation_symbol_override(rst_doc):
    """Title-block / tag family symbols land in annotation-symbols-titleblocks."""
    verdicts = prv.classify_elements(rst_doc, rst_doc)
    cats = {v.category for v in verdicts.values()}
    assert "annotation-symbols-titleblocks" in cats


# ---------------------------------------------------------------------------
# provenance verdicts on real files
# ---------------------------------------------------------------------------
def test_self_baseline_all_autodesk_sample(rst_doc):
    rep = provenance(rst_doc, rst_doc)
    assert rep["provenance_totals"] == {P_SAMPLE: len(rst_doc.et_by_id)}
    assert rep["baseline_id_overlap"] == 1.0
    assert rep["embedded_family_documents"]["count"] == 52
    assert rep["embedded_family_documents"]["by_provenance"] == {P_SAMPLE: 52}
    g = rep["gate_G1"]
    assert g["passes"] is False
    assert any(b["category"] == "object-styles" for b in g["blocking"])
    # nothing created / modified / unmatched in an untouched sample
    for p in (P_CREATED, P_CLONED, P_MODIFIED, P_UNMATCHED):
        assert p not in rep["provenance_totals"]
    json.dumps(rep)   # serialisable


def test_created_elements_are_transitive_clones(rme_doc):
    """V29 = rme sample + 16 created elements (walls, panels, transformer,
    circuits) — all cloned from Autodesk specimens: the honest current state."""
    if not os.path.exists(V29):
        pytest.skip("V29 acceptance file missing")
    cand = Document.from_file(V29)
    rep = provenance(cand, rme_doc)
    tot = rep["provenance_totals"]
    assert tot[P_SAMPLE] == 28132
    assert tot[P_CLONED] == 16
    assert P_CREATED not in tot and P_MODIFIED not in tot and P_UNMATCHED not in tot
    classes = sorted(c["class"] for c in rep["created_elements"])
    assert classes == ["FamilyInstance"] * 9 + ["RbsElectricalSystem"] * 3 + ["SWall"] * 4
    # every clone names its Autodesk lineage
    for c in rep["created_elements"]:
        assert c["provenance"] == P_CLONED
        assert c.get("lineage") or c.get("clone_of") is not None
    wall = next(c for c in rep["created_elements"] if c["class"] == "SWall")
    assert any(l["class"] == "BasicWallType" for l in wall["lineage"])
    inst = next(c for c in rep["created_elements"] if c["class"] == "FamilyInstance")
    assert any(l["class"] == "FamilySymbol" for l in inst["lineage"])
    circ = next(c for c in rep["created_elements"] if c["class"] == "RbsElectricalSystem")
    assert any(l["class"] == "RbsCableType" for l in circ["lineage"])
    # gate fails and names the 16 clones in placed-model-content
    g = rep["gate_G1"]
    assert g["passes"] is False
    assert {"category": "placed-model-content", "provenance": P_CLONED,
            "count": 16, "why": "Autodesk-derived expression in an expression-bearing category"} \
        in g["blocking"]


def test_ours_modified_detected(rme_doc):
    """M3_modify edited two sample elements in place (a Level + an instance)."""
    if not os.path.exists(M3):
        pytest.skip("M3 acceptance file missing")
    cand = Document.from_file(M3)
    rep = provenance(cand, rme_doc, with_units=False)
    assert rep["provenance_totals"].get(P_MODIFIED) == 2
    kinds = {(m["class"], m["provenance"]) for m in rep["modified_elements"]}
    assert kinds == {("Level", P_MODIFIED), ("FamilyInstance", P_MODIFIED)}
    for m in rep["modified_elements"]:
        assert "differs in" in m["reason"]


def test_reduction_survivors_are_pure_sample(rst_doc):
    """A staged reduction (R2s) only DELETES: every survivor is byte-identical
    Autodesk content, so the gap list is the whole surviving inventory."""
    if not os.path.exists(R2S):
        pytest.skip("R2s genesis file missing")
    cand = Document.from_file(R2S)
    rep = provenance(cand, rst_doc)
    tot = rep["provenance_totals"]
    assert set(tot) == {P_SAMPLE}
    assert tot[P_SAMPLE] == len(cand.et_by_id) < len(rst_doc.et_by_id)
    assert rep["embedded_family_documents"]["by_provenance"] == {P_SAMPLE: 52}
    assert rep["gate_G1"]["passes"] is False
    assert rep["gate_G1"]["gap_list"]


def test_wrong_baseline_is_flagged(rst_doc, rme_doc):
    """rme against the rst baseline: near-zero overlap -> unmatched + warning,
    and the gate refuses to pass on unattributable provenance."""
    rep = provenance(rme_doc, rst_doc, with_units=False)
    assert rep["provenance_totals"].get(P_UNMATCHED, 0) > 20000
    assert rep["baseline_id_overlap"] < 0.1
    assert rep["warnings"], "expected a baseline-mismatch warning"
    assert rep["gate_G1"]["passes"] is False
    assert any(b["provenance"] == P_UNMATCHED for b in rep["gate_G1"]["blocking"])


def test_gate_passes_on_empty_ledger():
    """A synthetic report with zero derived elements passes G1; adding one
    autodesk-sample loadable family fails it; datums are report-only unless strict."""
    base = {"baseline": "x", "categories": {
        "datums": {"expression_bearing": False, "counts": {P_SAMPLE: 3}},
        "loadable-families": {"expression_bearing": True, "counts": {P_CREATED: 5}},
    }}
    assert gate_G1(base)["passes"] is True
    assert gate_G1(base, strict=True)["passes"] is False       # datums gated when strict
    bad = json.loads(json.dumps(base))
    bad["categories"]["loadable-families"]["counts"][P_SAMPLE] = 1
    g = gate_G1(bad)
    assert g["passes"] is False and g["gap_list"][0]["count"] == 1
    unb = json.loads(json.dumps(base))
    unb["baseline"] = None
    assert gate_G1(unb)["passes"] is False


def test_no_baseline_is_unbaselined(rst_doc):
    rep = provenance(rst_doc, None, with_units=False)
    assert set(rep["provenance_totals"]) == {"unbaselined"}
    assert rep["gate_G1"]["passes"] is False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_cli_writes_json_and_exit_code(tmp_path):
    out = tmp_path / "led.json"
    r = subprocess.run([PY, CLI, RST, "--baseline", "self", "--json", str(out),
                        "--no-examples", "--max-classes", "2"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2, r.stdout + r.stderr        # gate fails => 2
    assert "G1 GATE: FAIL" in r.stdout
    d = json.loads(out.read_text())
    assert d["host_elements"] == 13936
    assert d["gate_G1"]["passes"] is False
    assert "object-styles" in d["categories"]
    assert d["categories"]["object-styles"]["counts"][P_SAMPLE] > 2000
    # v2: all four layers ledgered by default in the CLI
    assert d["layers"] == ["elements", "streams", "strings", "identity"]
    assert d["stream_ledger"]["totals"]["identical_pct"] == 100.0   # self vs self


# ---------------------------------------------------------------------------
# v2: stream ledger / multi-baseline / strings / identity / honest gate
# ---------------------------------------------------------------------------
G0 = os.path.join(ROOT, "experiments", "genesis", "G0.rvt")


@pytest.fixture(scope="module")
def rst_corpus():
    return prv.build_baseline_corpus([RST])


def test_content_units_cover_streams_and_save_units():
    units = prv.content_units(RST)
    names = {u.name for u in units}
    # every OLE stream + the host unit + the 52 embedded family save units
    for want in ("Formats/Latest", "Global/Latest", "Global/ElemTable",
                 "Global/History", "Global/DocumentIncrementTable",
                 "Global/PartitionTable", "Global/ContentDocuments",
                 "BasicFileInfo", "ProjectInformation", "TransmissionData",
                 "Partitions/21#host"):
        assert want in names, want
    saves = [u for u in units if u.kind == "save-unit"]
    assert len(saves) == 52 and all(u.guid for u in saves)
    lat = next(u for u in units if u.name == "Global/Latest")
    assert len(lat.data) == 8 + 1_586_246       # 8-byte global prefix + inflated ADocument


def test_stream_ledger_self_is_all_identical(rst_corpus):
    """A file against itself: every unit byte-identical, 100 % byte-weighted."""
    led = prv.stream_ledger(RST, rst_corpus)
    assert led["totals"]["identical_pct"] == 100.0
    assert led["totals"]["identical"] == led["totals"]["inflated"]
    assert all(r["class"] == prv.S_IDENTICAL for r in led["units"])
    assert led["schema_stream"]["identical_pct"] == 100.0


def test_stream_ledger_buckets_partition_bytes(rst_corpus):
    """identical + modified-lineage remainder + ours == inflated, per unit
    and in total (the byte-weighted percentages sum to 100)."""
    if not os.path.exists(G0):
        pytest.skip("G0 genesis file missing")
    led = prv.stream_ledger(G0, rst_corpus)
    for r in led["units"]:
        assert r["identical_bytes"] + r["lineage_remainder_bytes"] + r["ours_bytes"] == r["inflated"], r["name"]
    t = led["totals"]
    assert t["identical"] + t["lineage_remainder"] + t["ours"] == t["inflated"]
    assert abs(t["identical_pct"] + t["lineage_remainder_pct"] + t["ours_pct"] - 100.0) < 0.05


def test_G0_stream_layer_finds_the_sample_document(rst_corpus):
    """THE audit finding, made permanent: G0's Global/Latest (the ADocument)
    is byte-identical to the rst sample's and it is expression-bearing —
    the v1 headline '0 autodesk-sample' hid ~94 % Autodesk bytes."""
    if not os.path.exists(G0):
        pytest.skip("G0 genesis file missing")
    led = prv.stream_ledger(G0, rst_corpus)
    by = {r["name"]: r for r in led["units"]}
    lat = by["Global/Latest"]
    assert lat["class"] == prv.S_IDENTICAL and lat["expression_bearing"] is True
    assert lat["identical_bytes"] == lat["inflated"] == 1_586_254
    assert lat["identical_to"] == ["rstbasicsampleproject:Global/Latest"]
    fmt = by["Formats/Latest"]
    assert fmt["class"] == prv.S_IDENTICAL and fmt["role"] == "schema"
    assert fmt["expression_bearing"] is False            # counsel C4, separate
    # our own streams read as ours
    assert by["Global/ElemTable"]["class"] == prv.S_OURS
    assert by["Partitions/21#host"]["class"] == prv.S_OURS
    # byte-weighted headline: ~94 % Autodesk without the schema stream
    tex = led["totals_excluding_schema"]
    assert 92.0 < tex["identical_pct"] < 96.0
    assert led["expression_streams_identical_bytes"]["Global/Latest"] == 1_586_254


def test_resource_ref_scan_ascii_and_utf16():
    ascii_buf = b"see http://www.autodesk.com and assetlibrary_base.fbx x autodesk.spec.aec:length-2.0.0"
    wide = "SunAndSky-002 by Autodesk".encode("utf-16le")
    hits = prv.scan_resource_refs(ascii_buf + wide, samples=2)
    assert hits["autodesk-url"]["count"] == 1
    assert hits["asset-library-fbx"]["count"] == 1
    assert hits["forge-typeid"]["count"] == 1
    assert hits["sunandsky-asset"]["count"] == 1
    assert hits["autodesk-name"]["count"] == 1        # 'Autodesk' (not the URL / typeid)
    assert prv.scan_resource_refs(b"nothing to see here") == {}


def test_G0_resource_refs_are_counted():
    if not os.path.exists(G0):
        pytest.skip("G0 genesis file missing")
    rr = prv.resource_ref_report(G0, Document.from_file(G0))
    assert rr["total_refs"] > 5000                     # thousands of Forge typeIds
    assert rr["by_pattern"]["forge-typeid"] > 5000
    # G0 was regenerated 2026-08-03 through the identity-scrub pipeline: the
    # asset-library fbx references it once inherited from the sample are gone.
    assert rr["by_pattern"].get("asset-library-fbx", 0) == 0
    assert rr["elements_with_refs"] >= 1               # OUR records carry some too


def test_identity_flags_autodesk_usernames_and_sample_identity(rst_corpus):
    """The rst sample asserts Autodesk's own identity: template author,
    an employee path in last_save_path, employee usernames in the DIT."""
    idr = prv.identity_report(RST, rst_corpus)
    assert idr["ok"] is False
    fields = {v["field"] for v in idr["violations"]}
    assert "author" in fields                          # 'Autodesk Revit'
    assert "last_save_path" in fields                  # C:\Users\hansonje\...
    dit = [v for v in idr["violations"] if v["field"] == "DocumentIncrementTable.username"]
    assert dit and "loboarch" in dit[0]["value"]


def test_G0_identity_fully_owned():
    """G0 (regenerated 2026-08-03 through the V32 identity scrub) owns its
    whole identity: BasicFileInfo ours, bare save path, and the
    DocumentIncrementTable carries OUR username on every save episode —
    no sample employee usernames remain, and the ledger must agree."""
    if not os.path.exists(G0):
        pytest.skip("G0 genesis file missing")
    idr = prv.identity_report(G0)
    assert idr["basic_file_info"]["last_save_path"] == "G0.rvt"
    fields = [v["field"] for v in idr["violations"]]
    assert "author" not in fields and "last_save_path" not in fields
    assert "DocumentIncrementTable.username" not in fields


def test_multi_baseline_union_and_attribution(rst_doc, rme_doc):
    """G0 vs [rst, rme]: the union counts an element cloned if EITHER sample
    holds a specimen; every derived verdict names WHICH baseline (attribution)."""
    if not os.path.exists(G0):
        pytest.skip("G0 genesis file missing")
    cand = Document.from_file(G0)
    single = provenance(cand, rst_doc)
    multi = provenance(cand, baselines=[rst_doc, rme_doc])
    assert multi["multi_baseline"] is True
    assert len(multi["baselines"]) == 2
    s_cl = single["provenance_totals"].get(P_CLONED, 0)
    m_cl = multi["provenance_totals"].get(P_CLONED, 0)
    assert m_cl >= s_cl                               # union can only add clones
    assert m_cl > s_cl                                # ...and rme adds some (product defaults)
    for c in multi["created_elements"]:
        if c["provenance"] == P_CLONED:
            assert c["attribution"] in {"rstbasicsampleproject", "rmebasicsampleproject"}
            assert set(c["baselines"]) == {"rstbasicsampleproject", "rmebasicsampleproject"}
    mt = multi["multi_baseline_table"]
    assert set(mt["per_baseline"]) == {"rstbasicsampleproject", "rmebasicsampleproject"}
    assert mt["union"] == multi["provenance_totals"]
    b = mt["created_max_similarity_buckets"]
    assert b["max_sim_lt_0.25"] <= b["max_sim_lt_0.40"] <= b["created_total"]


def test_gate_v2_blocks_on_stream_bytes_and_strings_and_identity():
    """The honest gate: an element-clean ledger still FAILS on identical
    expression-stream bytes / resource refs / identity; the schema stream is
    a counsel item, never a blocker; a partial-layer PASS does not certify."""
    clean = {"baseline": "x", "layers": ["elements"], "categories": {
        "loadable-families": {"expression_bearing": True, "counts": {P_CREATED: 5}}}}
    g = gate_G1(clean)
    assert g["passes"] is True and g["certifies_G1"] is False    # element layer only
    assert "NOT a G1 certification" in g["verdict"]
    full = json.loads(json.dumps(clean))
    full["layers"] = ["elements", "streams", "strings", "identity"]
    full["stream_ledger"] = {"units": [], "schema_stream": None, "fingerprints": []}
    full["resource_refs"] = {"total_refs": 0, "by_pattern": {}, "total_refs_schema_stream": 0}
    full["identity"] = {"violations": [], "advisories": []}
    g = gate_G1(full)
    assert g["passes"] is True and g["certifies_G1"] is True
    assert "G1 CERTIFIED" in g["verdict"]
    # a byte-identical expression stream blocks; the schema stream does not
    bad = json.loads(json.dumps(full))
    bad["stream_ledger"] = {
        "units": [
            {"name": "Global/Latest", "class": "identical", "expression_bearing": True,
             "identical_bytes": 1586254, "inflated": 1586254, "best_baseline": "rst"},
            {"name": "Formats/Latest", "class": "identical", "expression_bearing": False,
             "identical_bytes": 496597, "inflated": 496597, "best_baseline": "rst"},
        ],
        "schema_stream": {"name": "Formats/Latest", "identical_pct": 100.0,
                          "identical_to": ["rst:Formats/Latest"]},
        "fingerprints": [],
    }
    g = gate_G1(bad)
    assert g["passes"] is False and g["stream_gap_bytes"] == 1586254
    assert any(b.get("layer") == "streams" and b["category"] == "Global/Latest"
               for b in g["blocking"])
    assert not any(b.get("category") == "Formats/Latest" for b in g["blocking"])
    assert any(c["item"] == "C4 schema-stream" for c in g["counsel"])
    # resource refs and identity violations block too
    bad2 = json.loads(json.dumps(full))
    bad2["resource_refs"]["total_refs"] = 3
    bad2["identity"]["violations"] = [{"field": "username", "value": "hansonje",
                                        "why": "Autodesk employee username"}]
    g = gate_G1(bad2)
    assert g["passes"] is False
    assert g["resource_ref_count"] == 3 and g["identity_violations"] == 1


def test_cli_multi_baseline_end_to_end(tmp_path):
    """--baseline given twice (multi) with all layers; exit 2, JSON complete."""
    if not os.path.exists(G0):
        pytest.skip("G0 genesis file missing")
    out = tmp_path / "g0.json"
    r = subprocess.run([PY, CLI, G0, "--baseline", RST, "--baseline", RME,
                        "--json", str(out), "--no-examples", "--max-classes", "1",
                        "--cache-dir", str(tmp_path / "cache")],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "STREAM LEDGER (byte-weighted)" in r.stdout
    assert "MULTI-BASELINE ELEMENT TABLE" in r.stdout
    d = json.loads(out.read_text())
    assert d["multi_baseline"] is True
    assert d["gate_G1"]["certifies_G1"] is False
    assert d["gate_G1"]["stream_gap_bytes"] == 1_586_254   # the ADocument
    assert d["gate_G1"]["resource_ref_count"] > 0
    assert (tmp_path / "cache").is_dir()                    # baseline index cached
