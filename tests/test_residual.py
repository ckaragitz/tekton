"""tests/test_residual.py -- the instbug-residual stream's local gates.

Covers tools/residual_probe.py + the emitted experiments/instbug/residual/**
artifacts: the rung shapes (dummy-symbol-under-instance really is what was
built), the recorded accounting gates (validator 0 unexpected errors,
four-registry coherence, survivor law, per-hop registry deltas), the P3
one-change law (BXns vs BXfix symbol differs in EXACTLY the three baked-
geometry fields + the rep class), the delta matrix's separating features,
the probes.json base declarations, the staged batch-34 control identity,
and the corpus symbol law (zero instanced SerializedDummy symbols in every
Autodesk sample).

The rungs are built by ``tools/residual_probe.py build`` (~120 s); these
tests never rebuild -- artifact-dependent tests SKIP when the rungs are
absent so a fresh tree still collects clean.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
TOOLS = os.path.join(ROOT, "tools")
for p in (SRC, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "instbug", "residual")
ACCOUNTING = os.path.join(OUT_DIR, "accounting.json")
PROBES = os.path.join(OUT_DIR, "probes.json")
MATCHED = os.path.join(OUT_DIR, "matched_pair_delta.json")
MATRIX = os.path.join(OUT_DIR, "delta_matrix.json")
CORPUS = os.path.join(OUT_DIR, "corpus_symbols.json")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")

LADDER = ("BXns_f1i1", "SL_f6i6", "BXns_f6i6", "SL_f1i1")
#: rung -> (path kind, n_families, n_instances)
SHAPE = {"BXns_f1i1": ("famgen_nosolid", 1, 1), "BXns_f6i6": ("famgen_nosolid", 6, 6),
         "SL_f1i1": ("famload", 1, 1), "SL_f6i6": ("famload", 6, 6)}

needs = pytest.mark.skipif(not os.path.isfile(ACCOUNTING),
                           reason="residual rungs not built (tools/residual_probe.py build)")


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def acct():
    with open(ACCOUNTING) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def probes():
    with open(PROBES) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# the tool's pure invariants
# ---------------------------------------------------------------------------

def test_ladder_covers_the_charter_shapes():
    import residual_probe as R
    assert set(R.LADDER) == set(SHAPE)
    assert R.LADDER[0] == "BXns_f1i1"          # the hypothesis-killing rung reads first
    assert R.LADDER[1] == "SL_f6i6"            # then the path attribution at N=6
    for name, (kind, nf, ni) in SHAPE.items():
        base, k, f, i = R.RUNG_SPEC[name]
        assert (k, f, i) == (kind, nf, ni)
        assert os.path.isfile(base)


def test_no_loader_edit_was_needed():
    """The charter pre-authorized src/rvt/famgen/nosolid_variant.py ONLY if
    famgen could not emit solid=False + instance; it can (loader's F4b mode +
    the exposed symbol_solid flag), so the wrapper must NOT exist."""
    assert not os.path.exists(os.path.join(SRC, "rvt", "famgen", "nosolid_variant.py"))


# ---------------------------------------------------------------------------
# the recorded accounting gates
# ---------------------------------------------------------------------------

@needs
def test_every_rung_built_with_clean_gates(acct):
    assert not {k: v for k, v in acct["errors"].items()
                if not k.endswith((".traceback", ".tb"))}
    for name in LADDER:
        assert name in acct["built"], f"{name} missing from build record"
        rep = acct["accounting"][name]
        assert rep["gates_ok"], f"{name}: gates not ok"
        assert rep["validator"]["unexpected_errors"] == [], f"{name}: unexpected validator errors"
        assert rep["validator"]["n_errors"] == 0, f"{name}: validator errors at build"
        assert rep["survivor_law_ok"], f"{name}: survivor law violated"
        assert rep["census"]["coherent"], f"{name}: four registries incoherent"


@needs
def test_load_hop_registry_deltas_match_family_count(acct):
    for name in LADDER:
        _, nf, ni = SHAPE[name]
        hop = acct["accounting"][name + ".hop_load"]
        for k in ("save_units", "contentdocs_entries", "contenttable_records",
                  "familymgr_entries"):
            assert hop["census_delta"][k] == nf, f"{name}.hop_load {k}: " \
                f"{hop['census_delta'][k]} != {nf}"
        inst = acct["accounting"][name]
        assert inst["elemtable"]["n_added"] == ni, f"{name}: instance rows"
        for k in ("save_units", "contentdocs_entries", "contenttable_records",
                  "familymgr_entries"):
            assert inst["census_delta"][k] == 0, f"{name}: instance hop touched registries"


@needs
def test_rung_md5s_match_disk(acct):
    for name in LADDER:
        info = acct["built"][name]
        path = os.path.join(ROOT, info["file"])
        assert os.path.isfile(path), f"{name} file missing"
        assert _md5(path) == info["md5"], f"{name}: file changed since build"


# ---------------------------------------------------------------------------
# the rung SHAPES read back from the emitted bytes
# ---------------------------------------------------------------------------

@needs
def test_bxns_is_dummy_symbol_under_instance(acct):
    """The BXns rungs really are the hypothesis's shape: every placed
    instance references OUR symbol and that symbol carries NO baked geometry
    (SerializedDummy rep, m_geomSteps/m_pGeomTable None)."""
    from rvt.mutate import Document
    info = acct["built"]["BXns_f1i1"]
    d = Document.from_file(os.path.join(ROOT, info["file"]))
    for inst in info["equipment"]["instances"]:
        iv = d.value(inst["elem_id"]) or {}
        assert iv.get("m_masterSymbolId") == inst["symbol"]
        sv = d.value(inst["symbol"]) or {}
        assert d.class_of(inst["symbol"], 103) == "SerializedDummy"
        assert sv.get("m_geomSteps") is None
        assert sv.get("m_pGeomTable") is None
        assert sv.get("m_geomTag2MaterialId") in ([], None)
        # the D-fix era placement shape (D1/D5 live in the tree)
        assert (iv.get("m_pConnectorManager") or {}).get("ptr_class") == \
            "FamilyInstanceConnectorManager"


@needs
def test_sl_f6i6_is_famload_symbols_under_six_instances(acct):
    from rvt.mutate import Document
    info = acct["built"]["SL_f6i6"]
    assert len(info["equipment"]["instances"]) == 6
    d = Document.from_file(os.path.join(ROOT, info["file"]))
    for inst in info["equipment"]["instances"]:
        iv = d.value(inst["elem_id"]) or {}
        assert iv.get("m_masterSymbolId") == inst["symbol"]
        assert d.class_of(inst["symbol"], 103) == "SerializedDummy"
        sv = d.value(inst["symbol"]) or {}
        assert sv.get("m_geomSteps") is None
        assert sv.get("m_hasParamDefValue") == 1        # famload's symbol shape


# ---------------------------------------------------------------------------
# the matched-pair law + the delta matrix
# ---------------------------------------------------------------------------

@needs
def test_p3_one_change_law():
    """BXns_f1i1 vs the FAILED BXfix_f1i1: the symbol objects differ in
    EXACTLY the three baked-geometry fields (+ the seq-103 rep class) --
    the single-variable rung really is single-variable."""
    if not os.path.isfile(MATCHED):
        pytest.skip("run tools/residual_probe.py forensics")
    with open(MATCHED) as fh:
        m = json.load(fh)
    p3 = m.get("P3") or {}
    if p3.get("skipped"):
        pytest.skip(p3["skipped"])
    assert p3["rep_class"] == {"A": "SerializedDummy", "B": "GElement"}
    od = p3["obj_diff"]
    assert od["only_in_A"] == {} and od["only_in_B"] == {}
    assert sorted(od["differing"]) == ["m_geomSteps", "m_geomTag2MaterialId",
                                       "m_pGeomTable"]


def test_delta_matrix_separators_hold():
    if not os.path.isfile(MATRIX):
        pytest.skip("run tools/residual_probe.py forensics")
    with open(MATRIX) as fh:
        m = json.load(fh)
    f = m["features"]
    for feat in ("our_instance_reaches_our_baked_geometry",
                 "our_instance_of_our_family"):
        assert f[feat]["separates"], f"{feat} no longer separates"
        assert f[feat]["pass_files"] == [], f"{feat} appeared in a PASS file"
    # the instance MECHANISM is exonerated: sample-symbol instances only pass
    assert f["sample_symbol_instanced_by_us"]["fail_files"] == []


def test_corpus_law_no_instanced_dummy_symbols():
    if not os.path.isfile(CORPUS):
        pytest.skip("run tools/residual_probe.py mine")
    with open(CORPUS) as fh:
        c = json.load(fh)
    seen = 0
    for s, d in c["samples"].items():
        cells = d.get("cells_with_instances")
        if not cells:
            continue
        seen += 1
        assert cells["SerializedDummy+steps"] == 0, s
        assert cells["SerializedDummy+nosteps"] == 0, s
        assert cells["GElement+nosteps"] == 0, s
        assert cells["GElement+steps"] > 0, s
    assert seen >= 3
    assert c["examples_dummy_instanced"] == []
    # the corpus's own no-cache form keeps the history tables
    for e in c["examples_dummy_uninstanced"]:
        assert e["geom_steps"] and e["geom_table"]


# ---------------------------------------------------------------------------
# staging law
# ---------------------------------------------------------------------------

@needs
def test_probes_declare_certified_or_sample_bases(probes):
    with open(os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")) as fh:
        ledger = json.load(fh)
    certified = {e.get("file") for e in ledger.get("certified", [])}
    assert [p["rung"] for p in probes["probes"]] == list(LADDER)
    for p in probes["probes"]:
        base = p["base"]
        ok = base in certified or base.startswith("samples/")
        assert ok, f"{p['rung']}: base {base} neither certified nor a sample"
        assert p["gates"]["validator_errors_at_build"] == 0
        assert p["gates"]["four_registry_coherent"] is True
        assert p["gates"]["survivor_law_ok"] is True


@needs
def test_staged_batch_carries_byte_identical_control(acct):
    import glob
    batches = sorted(glob.glob(os.path.join(ROOT, "experiments", "acceptance",
                                            "batch_*.json")))
    ours = None
    for b in reversed(batches):
        with open(b) as fh:
            man = json.load(fh)
        names = {os.path.basename(e.get("file", "")) for e in man.get("entries", [])}
        if {"BXns_f1i1.rvt", "SL_f6i6.rvt"} <= names:
            ours = man
            break
    if ours is None:
        pytest.skip("residual batch not staged yet (tools/residual_probe.py stage)")
    controls = [e for e in ours["entries"] if e.get("kind") == "control"]
    assert len(controls) == 1
    ctrl = os.path.join(ROOT, controls[0]["staged_as"])
    assert _md5(ctrl) == _md5(G_ABPD), "control is not byte-identical to certified G_ABPD"
    # staged copies match the built rungs byte-for-byte
    for e in ours["entries"]:
        if e.get("kind") != "probe":
            continue
        name = os.path.splitext(os.path.basename(e["file"]))[0]
        built = acct["built"][name]
        assert e["md5"] == built["md5"], f"{name}: staged md5 differs from build record"
        staged = os.path.join(ROOT, e["staged_as"])
        assert _md5(staged) == built["md5"], f"{name}: staged copy drifted"
