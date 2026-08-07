"""tests/test_genesis_controls.py -- THE THREE-WAY SEPARATION controls
(genesis-controls stream: {ADD PATH vs OBJECT SHAPE vs OUR VALUES} for the
PenWidthTableElem and one built-in object-styles catalog row).

Tiers:
  1. the byte-identity ASSERTIONS the probes rest on -- Autodesk's own
     records re-encode byte-exactly (X0/C0's "verbatim"), our pen-table
     constructor fed exact FEET reproduces header + object + rep
     byte-identically (X1v == X0, finding P2), and the naive mm-interface feed
     does NOT (finding P1: 8 unreachable doubles); our GStyle constructor
     reproduces some rows completely and others only in the object (finding
     G1: the header flag word / cell-list variation).
  2. the identity REBASE touches only the element's own id leaves.
  3. the emitted deliverables (when built): probes.json ORDER = X0, X1v, X1u,
     C0, C1v, C1u; every listed file certified VALID with 0 validator
     errors, parity clean, 0 NEW dangling ids; X1v recorded as a NO-UPLOAD
     byte-identical twin of X0.
  4. one END-TO-END probe (C1v) built through the substitution engine into a
     temp dir: VALID, parity 1/1, header-bit assertion recorded.
Skips when K1.rvt (the viewer-PASSED base) is not present.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
CONTROLS = os.path.join(ROOT, "experiments", "genesis", "controls")
pytestmark = pytest.mark.skipif(not os.path.exists(K1),
                                reason="K1.rvt (viewer-PASSED empty-project base) not present")

import genesis_controls as GC                                     # noqa: E402
import genesis_substitute as GS                                   # noqa: E402
from rvt.genesis import settings as ST                            # noqa: E402
from rvt.genesis import types as GT                               # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def segs():
    return GC.unit0_segments(K1)


@pytest.fixture(scope="module")
def pen_spec(segs):
    return GC.specimen_records(K1, GC.PEN_OLD_ID, segments=segs)


@pytest.fixture(scope="module")
def cat_spec(segs):
    return GC.specimen_records(K1, GC.CAT_OLD_ID, segments=segs)


@pytest.fixture(scope="module")
def ted():
    from rvt.mutate import Document
    return GS.TypedEditor(decoder=Document.from_file(K1).dec,
                          maps=GC.GA_load_maps())


# ---------------------------------------------------------------------------
# tier 1: the byte-identity assertions
# ---------------------------------------------------------------------------

def test_specimen_pen_table_is_the_documented_element(pen_spec):
    v = pen_spec[102].value
    assert pen_spec[102].class_name == "PenWidthTableElem"
    assert v["m_famId"] == -1                                     # the PROJECT pen table
    keys = [p["m_invertedScale"] for p in v["m_pPenWidthTable"]["value"]["m_modelPenInfo"]]
    assert keys == [10, 20, 50, 100, 200, 500]                     # Autodesk's metric keys
    for p in v["m_pPenWidthTable"]["value"]["m_modelPenInfo"]:
        assert len(p["m_pens"]) == ST.PEN_COUNT
    assert pen_spec[103].class_name == "SerializedDummy" and pen_spec[103].payload_len == 2


def test_specimen_catalog_row_is_the_documented_element(cat_spec):
    v = cat_spec[102].value
    assert cat_spec[102].class_name == "GStyleElem"
    assert v["m_categoryId"] == GC.CAT_CATEGORY == -2000014        # OST_Windows
    assert v["m_gstyleType"] == GC.CAT_STYLE_TYPE == 1              # projection
    assert v["m_famId"] == -1 and v["m_cellList"] is None
    assert int(cat_spec[101].value["m_abFlags4Bytes"]) == 0x400201e


def test_autodesk_records_reencode_byte_exactly_pen_and_gstyle(pen_spec, cat_spec, ted):
    """X0 / C0's premise: decode -> re-encode of Autodesk's own three
    records is byte-identical (so 'verbatim through our path' is honest)."""
    for spec, cls in ((pen_spec, "PenWidthTableElem"), (cat_spec, "GStyleElem")):
        rec, proof = GC.verbatim_typerecord(spec, cls, 7_000_001, ted, kind="test")
        assert proof["all_three_seqs_identical"] is True, proof
        for s in ("101", "102", "103"):
            assert proof["verbatim_identity_at_original_id"][s]["identical"] is True
        assert rec.elem_id == 7_000_001


def test_verbatim_rebase_touches_only_the_elements_own_id_leaves(pen_spec, cat_spec, ted):
    for spec, cls, old in ((pen_spec, "PenWidthTableElem", GC.PEN_OLD_ID),
                           (cat_spec, "GStyleElem", GC.CAT_OLD_ID)):
        rec, proof = GC.verbatim_typerecord(spec, cls, 7_000_002, ted, kind="test")
        leaves = proof["identity_rebased_leaves"]
        assert leaves["object"] == [f"{cls}.m_id"], leaves
        assert leaves["header"] == ["ElementHeader.m_parents->ElementParents.m_deletion[*]"]
        assert rec.obj["m_id"] == 7_000_002
        dele = rec.header["m_parents"]["value"]["m_deletion"]
        assert 7_000_002 in dele and old not in dele


def test_our_pen_constructor_fed_exact_feet_reproduces_all_three_seqs(pen_spec):
    """FINDING P2 / the X1v assertion: header + object + rep byte-identical
    => X1v's records ARE X0's records."""
    model, persp, draft = GC.pen_exact_feet(pen_spec[102].value)
    ours = GC.our_pen_table_from_feet(GC.PEN_OLD_ID, model, persp, draft)
    enc = ours.encode()
    for s in (101, 102, 103):
        cmp = GC.byte_compare(enc[s], pen_spec[s].framed)
        assert cmp["identical"] is True, (s, cmp)


def test_our_pen_constructor_naive_mm_interface_is_NOT_byte_exact(pen_spec):
    """FINDING P1 pinned: feeding feet*304.8 back into the mm interface does
    NOT reproduce the specimen -- 8 doubles (every 9.0-mm pen) lose the
    last mantissa bit, and the stored double is unreachable from ANY mm."""
    naive = GC.pen_naive_mm_render(GC.PEN_OLD_ID, pen_spec[102].value).encode()
    cmp = GC.byte_compare(naive[102], pen_spec[102].framed)
    assert cmp["identical"] is False
    assert cmp["differing_bytes"] == 11 and cmp["first_divergence"] == 8   # stamp + 7 payload
    ana = GC.pen_value_analysis(pen_spec[102].value)
    assert ana["non_roundtripping_count"] == 8
    assert {round(d["displayed_mm"], 6) for d in ana["non_roundtripping_doubles"]} == {9.0}
    assert ana["stored_double_unreachable_from_any_mm_input"] == {"0.029527559055118106": True}
    # header + rep are still byte-identical (only the doubles differ)
    assert GC.byte_compare(naive[101], pen_spec[101].framed)["identical"]
    assert GC.byte_compare(naive[103], pen_spec[103].framed)["identical"]


def test_our_gstyle_constructor_reproduction_row30_full_row34_object_only(segs):
    """FINDING G1's two anchor rows: OST_Walls projection (id 30) reproduces
    COMPLETELY; OST_Windows projection (id 34, the C-trio row) reproduces
    object + rep but the header differs in EXACTLY the flag bit 0x2000."""
    for eid in (30, 34):
        spec = GC.specimen_records(K1, eid, segments=segs)
        ours = GC._cat_our_render_exact(eid, spec[102].value)
        enc = ours.encode()
        assert GC.byte_compare(enc[102], spec[102].framed)["identical"], eid
        assert GC.byte_compare(enc[103], spec[103].framed)["identical"], eid
        hcmp = GC.byte_compare(enc[101], spec[101].framed)
        if eid == 30:
            assert hcmp["identical"]                      # walls: our preset 0x400001e IS theirs
        else:
            assert not hcmp["identical"]
            ours_w = int(ours.header["m_abFlags4Bytes"])
            spec_w = int(spec[101].value["m_abFlags4Bytes"])
            assert (ours_w, spec_w) == (0x400001e, 0x400201e)
            assert ours_w ^ spec_w == 0x2000                # ONE bit apart
            delta = GC._pen_field_diff(ours.header, spec[101].value)
            assert [d["path"] for d in delta] == [".m_abFlags4Bytes"]


def test_our_catalog_row_differs_from_C1v_only_in_pen_and_colour(cat_spec):
    """C1u vs C1v = exactly the two VALUES (the literal X6a / R2 row)."""
    c1v = GC._cat_our_render_exact(4242, cat_spec[102].value)
    c1u = GC.our_catalog_row(4242)
    delta = GC._pen_field_diff(c1u.obj, c1v.obj)
    assert sorted(d["path"] for d in delta) == [".m_pGStyle.value.m_color",
                                                ".m_pGStyle.value.m_penNumber"]
    g = c1u.obj["m_pGStyle"]["value"]
    assert (g["m_penNumber"], g["m_color"]) == (1, 0x181818)          # ours
    assert (g["m_linePatternId"], g["m_materialElemId"]) == (-3000010, -1)
    assert c1u.header == c1v.header                                      # same OUR preset


def test_our_pen_table_with_specimen_keys_differs_only_in_the_doubles(pen_spec):
    """X1u's design: OUR widths, everything structural pinned to the
    specimen -- only pen doubles (and the id) differ."""
    keys = GC._spec_scale_keys(pen_spec[102].value)
    ours = ST.pen_width_table(elem_id=GC.PEN_OLD_ID,
                              model_pens_mm=ST.default_model_pens_mm(scales=tuple(keys)),
                              perspective_pens_mm=ST.pen_series_mm(0),
                              annotation_pens_mm=ST.pen_series_mm(0))
    diffs = GC._pen_field_diff(ours.obj, pen_spec[102].value)
    non_double = [d for d in diffs
                  if not (isinstance(d.get("ours"), float) and isinstance(d.get("specimen"), float))]
    assert non_double == [], non_double
    assert GC.byte_compare(ours.encode()[101], pen_spec[101].framed)["identical"]  # header


def test_catalog_row_has_zero_referrers_and_one_registry_leaf():
    ctx = GS.SubstContext(K1, "TC")
    assert ctx.inbound(GC.CAT_OLD_ID) == set()
    assert ctx.inbound(GC.PEN_OLD_ID) == set()
    surf = GS.adoc_surface(ctx.ted_adoc, ctx.tree, [GC.CAT_OLD_ID, GC.PEN_OLD_ID])
    assert surf[GC.CAT_OLD_ID] == [
        "ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[*]->"
        "CategoryTracking.m_gstyleData[*].m_gstyleId"]
    assert surf[GC.PEN_OLD_ID] == [
        "ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[*]->"
        "PenWidthTableInfo.m_penWidthTableElemId"]


# ---------------------------------------------------------------------------
# tier 3: the emitted deliverables (when the ladder has been built)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(os.path.join(CONTROLS, "probes.json")),
                    reason="controls not built (run tools/genesis_controls.py)")
def test_probes_manifest_order_and_decision_tree():
    with open(os.path.join(CONTROLS, "probes.json")) as fh:
        m = json.load(fh)
    names = [p["file"].split("/")[-1].replace(".rvt", "") for p in m["probes"]]
    assert names == ["X0", "X1v", "X1u", "C0", "C1v", "C1u"]
    assert [p["order"] for p in m["probes"]] == [1, 2, 3, 4, 5, 6]
    tree = m["decision_tree"]
    for k in ("X0 FAIL", "X0 PASS + X1u PASS", "C0 PASS + C1v FAIL",
              "C0 PASS + C1v PASS + C1u PASS", "ALL SIX PASS", "X1v"):
        assert k in tree, k
    x1v = [p for p in m["probes"] if p["order"] == 2][0]
    assert x1v["NO_UPLOAD_TWIN_OF"] == "X0"


@pytest.mark.skipif(not os.path.exists(os.path.join(CONTROLS, "C1u.json")),
                    reason="controls not built (run tools/genesis_controls.py)")
def test_every_built_control_is_certified_valid_and_parity_clean():
    for name in ("X0", "X1v", "X1u", "C0", "C1v", "C1u"):
        p = os.path.join(CONTROLS, f"{name}.json")
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            rep = json.load(fh)
        assert rep["verdict"] == "VALID", (name, rep.get("problems"))
        assert rep["validator"]["ok"] is True and rep["validator"]["errors"] == 0, name
        assert rep["parity"]["pairs_failed"] == 0 and rep["parity"]["pairs"] == 1, name
        assert rep["parity"]["adocument_dangling_created"] == [], name
        assert rep["parity"]["old_ids_still_in_adocument"] == {}, name
        assert rep["structural"]["ok"] is True, name
        assert rep["coherence"]["coherent"] is True, name
        assert rep["referrer_repoint"]["referrer_elements"] == 0, name
        assert rep["build_info"]["probe"] == name


@pytest.mark.skipif(not (os.path.exists(os.path.join(CONTROLS, "X1v.rvt"))
                         and os.path.exists(os.path.join(CONTROLS, "X0.rvt"))),
                    reason="X0/X1v not built")
def test_X1v_collapses_onto_X0_at_the_stream_level():
    c = GC.collapse_check(CONTROLS)
    assert c is not None and c["content_identical"] is True, c
    with open(os.path.join(CONTROLS, "X1v.json")) as fh:
        rep = json.load(fh)
    coll = rep["build_info"]["collapse_onto_X0"]
    assert coll["records_identical"] is True


# ---------------------------------------------------------------------------
# tier 4: one end-to-end control through the substitution engine
# ---------------------------------------------------------------------------

def test_end_to_end_C1v_is_valid_with_the_header_bit_recorded(tmp_path):
    out_dir = str(tmp_path)
    rung = GC.rung_by_name("C1v")
    rep = GS.substitute(rung, K1, out_dir=out_dir)
    assert rep["verdict"] == "VALID", rep.get("problems")
    assert rep["validator"]["errors"] == 0
    assert rep["old"]["ids"] == [GC.CAT_OLD_ID]
    assert rep["parity"]["pairs_ok"] == 1 and rep["parity"]["pairs_failed"] == 0
    assert rep["parity"]["adocument_dangling_created"] == []
    bi = rep["build_info"]
    assert bi["probe"] == "C1v"
    a = bi["byte_identity_assertion"]
    assert a["object_identical"] and a["rep_identical"] and not a["header_identical"]
    assert bi["the_ONE_difference_header"]["xor"] == "0x2000"
    # the registry leaf now names OUR row (registry parity by construction)
    tbl = rep["parity"]["table"][0]
    assert tbl["old"] == GC.CAT_OLD_ID and tbl["parity"] is True
    assert any("CategoryTracking.m_gstyleData" in s for s in tbl["surface_after"])
    assert os.path.exists(os.path.join(out_dir, "C1v.rvt"))
