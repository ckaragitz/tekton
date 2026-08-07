"""hostpair stream tests: the H9/H10 host-pair byte-copy binary (batch 38)
+ the corpus-lawful symbol form fix (src/rvt/famload_hostfix, batch 39).

Stream-local file only (SUITE-COORDINATION rule).  Everything here reads
the already-emitted artifacts under experiments/hostpair/ +
experiments/acceptance/ -- no probe is rebuilt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = os.path.join(ROOT, "experiments", "hostpair")
ACC = os.path.join(ROOT, "experiments", "acceptance")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(os.path.join(OUT, "H9.rvt")),
    reason="hostpair probes not built (tools/hostpair_probe.py build)")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jload(path):
    with open(path) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def schema():
    import famdoc_bisect as FDB
    FDB._install_schema()                                  # noqa: SLF001
    return True


@pytest.fixture(scope="module")
def h9_doc(schema):
    from rvt.mutate import Document
    return Document.from_file(os.path.join(OUT, "H9.rvt"))


@pytest.fixture(scope="module")
def acct():
    return jload(os.path.join(OUT, "accounting.json"))


@pytest.fixture(scope="module")
def copyrep():
    return jload(os.path.join(OUT, "copy_report.json"))


@pytest.fixture(scope="module")
def probes():
    return jload(os.path.join(OUT, "probes.json"))


# ---------------------------------------------------------------------------
# the native-cluster survey pins
# ---------------------------------------------------------------------------

def test_native_cluster_survey_pins():
    rep = jload(os.path.join(OUT, "native_cluster_survey.json"))
    assert all(rep["pins"].values()), \
        [k for k, v in rep["pins"].items() if not v]
    rt = rep["reencode_roundtrip"]
    assert rt["records"] == rt["byte_exact"] == 66 and not rt["diffs"]
    assert rep["typed_ref_census"]["unresolved"] == 0
    assert rep["typed_ref_census"]["embedded_typed"] == 0
    assert rep["embedded_id_hits"] == 50          # the big2small m_id64s only
    assert len(rep["cluster"]) == 22


# ---------------------------------------------------------------------------
# the byte-copy delta ledger (the "byte-identical except" proof)
# ---------------------------------------------------------------------------

def test_copy_ledger_exactly_five_content_moves(copyrep):
    led = copyrep["ledger"]
    moves = led["content_moves"]
    assert len(moves) == 5
    got = {(m["element"], m["path"]) for m in moves}
    assert got == {
        (1410863, "m_name"),
        (1410863, "m_famDocGUID"),
        (1410863, "m_oFamDoc.value.m_contentDocGUID"),
        (1411267, "m_name"),
        (1411280, "m_pParamDef.value.m_typeId.m_typeId"),
    }
    # every element's leaf deltas = id remaps + its declared moves
    for e in led["elements"]:
        assert e["leaf_deltas_total"] == e["id_remapped_leaves"] + \
            len(e["content_moves"])


def test_copy_ledger_covers_the_full_constellation(copyrep):
    led = copyrep["ledger"]
    assert len(led["elements"]) == 22
    classes = [e["class"] for e in led["elements"]]
    assert classes.count("FamilySymbol") == 2       # the type symbol + slave
    assert "LegendComponent" in classes             # the preview
    assert classes.count("ParamElemFamily") == 1    # the native twin roster
    reps = {e["class"]: e["rep"] for e in led["elements"]}
    assert reps["FamilySymbol"] == "GElement"
    assert reps["LegendComponent"] == "GElement"


# ---------------------------------------------------------------------------
# the emitted probes
# ---------------------------------------------------------------------------

def test_h10_is_h9s_immediate_parent(acct):
    h10 = os.path.join(OUT, "H10.rvt")
    parent = os.path.join(OUT, "_build", "H9_load.rvt")
    assert md5(h10) == md5(parent)
    assert acct["built"]["H9"]["immediate_parent"].endswith("H9_load.rvt")


def test_h9_copies_and_renames_read_back(h9_doc, copyrep):
    idmap = {int(k): v for k, v in copyrep["host_idmap"].items()}
    plan = copyrep["plan"]
    fam = h9_doc.value(idmap[1410863]) or {}
    assert fam.get("m_name") == "M Concrete-Square-Column H9"
    fd = ((fam.get("m_oFamDoc") or {}).get("value") or {})
    assert str(fd.get("m_contentDocGUID")) == plan["guid"]
    assert len(fd.get("m_big2SmallMap2") or []) == 50
    # class parity with the native original, all 22
    from rvt.mutate import Document
    nat = Document.from_file(RST)
    for old, new in idmap.items():
        assert h9_doc.class_of(new) == nat.class_of(old)
    # slave master link + surrogate preview link remapped
    slave = h9_doc.value(idmap[1411406]) or {}
    assert slave.get("m_masterId") == idmap[1411287]
    sur = h9_doc.value(idmap[1411267]) or {}
    assert sur.get("m_previewElemId") == idmap[1411268]
    assert sur.get("m_name") == "M Concrete-Square-Column H9"
    # the copied symbol keeps its geometry history + GElement rep
    sym = h9_doc.value(idmap[1411287]) or {}
    assert isinstance(sym.get("m_geomSteps"), dict)
    assert isinstance(sym.get("m_pGeomTable"), dict)
    assert h9_doc.class_of(idmap[1411287], 103) == "GElement"
    assert len(sym.get("m_refFaces") or []) == 14
    # twin typeId law: trailing 8 hex == the twin's own new id
    tw = h9_doc.value(idmap[1411280]) or {}
    pd = ((tw.get("m_pParamDef") or {}).get("value") or {})
    tid = pd.get("m_typeId")
    tid = tid.get("m_typeId") if isinstance(tid, dict) else tid
    m = re.match(r"revit\.local\.family:([0-9a-f]{32})([0-9a-f]{8})-1\.0\.0$",
                 str(tid))
    assert m and int(m.group(2), 16) == idmap[1411280]


def test_h9_instance_carries_the_v20_shape(h9_doc, acct):
    iid = acct["built"]["H9"]["instance_ids"][0]
    idmap = {int(k): v for k, v in
             jload(os.path.join(OUT, "copy_report.json"))["host_idmap"].items()}
    v = h9_doc.value(iid) or {}
    assert h9_doc.class_of(iid) == "FamilyInstance"
    assert v.get("m_createdPhaseId") == 86961
    assert v.get("m_masterSymbolId") == idmap[1411287]
    assert v.get("m_pConnectorManager") is None
    hdr = h9_doc.value(iid, 101) or {}
    dele = (((hdr.get("m_parents") or {}).get("value") or {})
            .get("m_deletion") or [])
    assert dele == sorted({311, 86961, idmap[1411287], iid})


def test_gates_all_green(acct):
    for name in ("H9", "H10"):
        a = acct["accounting"][name]
        assert a["validator"]["n_errors"] == 0
        assert not a["validator"]["unexpected_errors"]
        assert a["census"]["coherent"] is True
        assert a["survivor_law_ok"] is True
        assert a["identity_gate"]["status"] == "PASS"
    assert acct["accounting"]["H10"]["census_delta"]["save_units"] == 1
    assert acct["accounting"]["H9"]["census_delta"]["save_units"] == 0


# ---------------------------------------------------------------------------
# probes.json + the staged batches
# ---------------------------------------------------------------------------

def test_probes_json_decision_table(probes):
    rungs = {p["rung"]: p for p in probes["probes"]}
    assert list(probes["upload_order_max_information_first"]) == ["H9", "H10"]
    assert set(probes["reading_the_matrix"]) == {
        "CTRL FAIL", "H9 PASS", "H9 FAIL + H10 PASS", "H9 FAIL + H10 FAIL",
        "H9 PASS + H10 FAIL"}
    for n in ("H9", "H10"):
        assert rungs[n]["base"].endswith("rstbasicsampleproject.rvt")
        assert rungs[n]["gates"]["validator_errors"] == 0
        assert rungs[n]["gates"]["four_registry_coherent"] is True
    for n in ("BXhf_f1i1", "DEMO_250v_room_v3"):
        assert rungs[n]["base"].endswith("G_ABPD.rvt")
        assert rungs[n]["gates"]["validator_errors"] == 0
        assert rungs[n]["gates"]["symbol_form_ok"] is True
    assert "fix_reading" in probes


def test_batch_38_staged_with_byte_identical_control(probes):
    man = jload(os.path.join(ACC, "batch_38.json"))
    entries = {e.get("staged_as") or e.get("file"): e for e in man["entries"]}
    ctrl = next(e for e in man["entries"] if e["kind"] == "control")
    assert md5(os.path.join(ROOT, ctrl["staged_as"])) == md5(RST)
    for name in ("H9", "H10"):
        e = next(x for x in man["entries"]
                 if x.get("staged_as", "").endswith(f"{name}.rvt"))
        staged = os.path.join(ROOT, e["staged_as"])
        assert md5(staged) == e["md5"] == md5(os.path.join(OUT, f"{name}.rvt"))


def test_batch_39_staged_with_byte_identical_control():
    man = jload(os.path.join(ACC, "batch_39.json"))
    ctrl = next(e for e in man["entries"] if e["kind"] == "control")
    assert md5(os.path.join(ROOT, ctrl["staged_as"])) == md5(G_ABPD)
    names = [os.path.basename(e.get("staged_as") or "") for e in man["entries"]]
    assert "BXhf_f1i1.rvt" in names and "DEMO_250v_room_v3.rvt" in names


# ---------------------------------------------------------------------------
# famload_hostfix: the corpus law + the applied form
# ---------------------------------------------------------------------------

def test_mined_corpus_law_aggregate():
    rep = jload(os.path.join(OUT, "corpus_geometry_grammar.json"))
    agg = rep["aggregate"]
    assert agg["instanced_symbols"] == 201
    assert agg["rep_GElement"] == 201
    assert agg["single_subnode"] == 0
    assert agg["ref_faces_empty"] == 0
    assert agg["ref_faces_min"] == 9
    assert agg["one_step"] == 201
    assert agg["idCounter_2"] == 201
    assert agg["hasParamDef_0"] == 200
    assert agg["root_tag_is_self"] == 201


def test_reference_specs_pure():
    from rvt.famload_hostfix import reference_specs

    class E:
        def __init__(self, cls, obj):
            self.class_name = cls
            self.obj = obj
    els = [E("RefPlane", {"m_definesOrigin": True, "m_refName": 1}),
           E("RefPlane", {"m_definesOrigin": True, "m_refName": 4}),
           E("Level", {})]
    specs = reference_specs(els, [-1.0, -2.0, 0.0], [1.0, 2.0, 3.0])
    assert [s["kind"] for s in specs] == ["origin_plane_x", "origin_plane_y",
                                          "ref_level"]
    x, y, z = specs
    assert x["x_vec"] == [0.0, 1.0, 0.0] and x["y_vec"] == [0.0, 0.0, 1.0]
    assert x["envelope"] == [[-2.0, 0.0], [2.0, 3.0]]
    assert y["x_vec"] == [0.0, 0.0, 1.0] and y["y_vec"] == [1.0, 0.0, 0.0]
    assert z["x_vec"] == [1.0, 0.0, 0.0] and z["y_vec"] == [0.0, 1.0, 0.0]
    assert z["envelope"] == [[-1.0, -2.0], [1.0, 2.0]]
    # origin planes carry the origin flag; the level the datum flag
    assert x["flags"] == 2622116 and z["flags"] == 2622180


def test_build_corpus_symbol_geometry_id_space():
    from rvt.famload_hostfix import build_corpus_symbol_geometry
    solid = {
        "m_GInfo": {"m_categoryId": -1, "m_tag": -1, "m_controlCommand": 0,
                    "m_flags": 557060},
        "m_subNodes": [{"ptr_class": "Geometry", "pid": -1, "value": {
            "m_GInfo": {"m_categoryId": -1, "m_tag": -1},
            "m_pFaces": [{"ptr_class": "Face", "pid": -1,
                          "value": {"m_GInfo": {"m_tag": 10}}}
                         for _ in range(6)],
            "m_pEdges": [{"ptr_class": "Edge", "pid": -1,
                          "value": {"m_GInfo": {"m_tag": 20}}}
                         for _ in range(12)],
        }}],
        "m_bBox": [[-1.0, -1.0, 0.0], [1.0, 1.0, 2.0]],
        "m_gElemType": 3, "m_flags": 2,
    }
    specs = [{"kind": "origin_plane_x", "flags": 2622116,
              "origin": [0.0, 0.0, 0.0], "x_vec": [0, 1, 0], "y_vec": [0, 0, 1],
              "envelope": [[-1, 0], [1, 2]]}] * 3
    b = build_corpus_symbol_geometry(solid, absorbed_form_index=7,
                                     symbol_id=999, category_gstyle=124,
                                     ref_specs=specs)
    # id space: 3 ref nodes + 6 faces + 12 edges + 1 geometry tag = 22
    assert b["n_symbol_ids"] == 22
    assert len((b["geom_table"]["value"] or {}).get("m_table")) == 22
    assert b["history"] == {"ref_nodes": 3, "faces": 6, "edges": 12,
                            "curves": 1, "geom_table_rows": 22}
    assert len(b["ref_faces"]) == 3
    subs = b["rep"]["m_subNodes"]
    assert [s["ptr_class"] for s in subs] == ["GFilter", "GFilter", "Geometry"]
    assert (subs[-1]["value"]["m_pFaces"] == []
            and subs[-1]["value"]["m_pEdges"] == [])
    assert b["rep"]["m_GInfo"]["m_tag"] == 999
    assert b["rep"]["m_GInfo"]["m_categoryId"] == 124
    assert b["geometry_tag"] == 21
    # refuses an empty ref set (the 0/201 corpus law)
    with pytest.raises(ValueError):
        build_corpus_symbol_geometry(solid, absorbed_form_index=7,
                                     symbol_id=999, category_gstyle=124,
                                     ref_specs=[])


def test_corpus_symbol_form_patches_and_reverts(schema):
    from rvt import famload_hostfix as HF
    from rvt import famload as FL
    from rvt.famgen import loader as L
    orig_fl = FL.author_family_symbols
    orig_fg = L.author_family_symbol
    with HF.corpus_symbol_form():
        assert FL.author_family_symbols is not orig_fl
        assert L.author_family_symbol is not orig_fg
    assert FL.author_family_symbols is orig_fl
    assert L.author_family_symbol is orig_fg


def test_emitted_fix_probe_symbol_form(schema):
    from rvt import famload_hostfix as HF
    path = os.path.join(OUT, "BXhf_f1i1.rvt")
    if not os.path.isfile(path):
        pytest.skip("fixdemo not built")
    fixacct = jload(os.path.join(OUT, "fix_accounting.json"))
    sym = sorted(fixacct["built"]["BXhf_f1i1"]["symbol_form"])[0]
    rep = HF.assert_symbol_form(path, int(sym))
    assert rep["ok"], rep["checks"]
    assert rep["counts"]["refFaces"] == 3
    assert rep["counts"]["table"] == rep["counts"]["faceHist"] + \
        rep["counts"]["edgeHist"] + rep["counts"]["curveHist"]


def test_fix_probes_gates(acct):
    fixacct = jload(os.path.join(OUT, "fix_accounting.json"))
    for name in ("BXhf_f1i1", "DEMO_250v_room_v3"):
        a = fixacct["accounting"][name]
        assert a["validator"]["n_errors"] == 0
        assert not a["validator"]["unexpected_errors"]
        assert a["census"]["coherent"] is True
        assert a["survivor_law_ok"] is True
    assert fixacct["accounting"]["DEMO_250v_room_v3"]["census_delta"][
        "save_units"] == 6


def test_hostfix_spec_ranked(probes):
    spec = jload(os.path.join(OUT, "hostfix_spec.json"))
    ranks = [(e["rank"], e["element"]) for e in spec["checklist"]]
    assert ranks[0] == (1, "FamilySymbol")
    sym = spec["checklist"][0]
    assert sym["rep"] == {"A": "GElement", "B": "SerializedDummy"}
    assert "m_geomSteps" in sym["content_deltas"]
    assert "m_pGeomTable" in sym["content_deltas"]
    assert "m_refFaces" in sym["content_deltas"]
    ng = sym["native_geometry_history"]
    assert ng["geomTable_rows"] == 34 and ng["refFaces"] == 14
