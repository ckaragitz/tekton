"""tests/test_instbug.py -- the instbug bisection ladder's stream-local gates.

Covers tools/bisect_instance_bug.py + the emitted experiments/instbug/**
artifacts: the intent truncation logic, the recorded per-rung accounting
(validator 0 errors, four-registry coherence, survivor byte-identity law,
expected registry deltas per rung shape), one live recomputation against the
record, the probe_batch admissibility of the ladder, and the staged batch's
control identity (byte-identical G_ABPD copy).

The ladder itself is built by ``tools/bisect_instance_bug.py build`` (255 s);
these tests never rebuild -- artifact-dependent tests SKIP when the ladder is
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

OUT_DIR = os.path.join(ROOT, "experiments", "instbug")
ACCOUNTING = os.path.join(OUT_DIR, "accounting.json")
PROBES = os.path.join(OUT_DIR, "probes.json")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")

LADDER = ("BX_f2", "BX_f1i1", "SX_f6i6", "BX_f6i6", "BX_f2i2",
          "BX_f6", "BX_f1", "BX_w_f1i1")
#: rung -> (n_families, n_instances, n_walls)
SHAPE = {"BX_f1": (1, 0, 0), "BX_f2": (2, 0, 0), "BX_f6": (6, 0, 0),
         "BX_f1i1": (1, 1, 0), "BX_f2i2": (2, 2, 0), "BX_f6i6": (6, 6, 0),
         "BX_w_f1i1": (1, 1, 1), "SX_f6i6": (6, 6, 0)}
#: one famgen panel load adds exactly these host elements
LOAD_ELEMENTS = 18


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _built() -> bool:
    return os.path.isfile(ACCOUNTING) and os.path.isfile(PROBES) and all(
        os.path.isfile(os.path.join(OUT_DIR, f"{r}.rvt")) for r in LADDER)


needs_ladder = pytest.mark.skipif(
    not _built(), reason="instbug ladder not built "
                         "(run: .venv/bin/python tools/bisect_instance_bug.py build)")


@pytest.fixture(scope="module")
def accounting():
    with open(ACCOUNTING) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def probes():
    with open(PROBES) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# 1. the intent truncation (pure logic; no ladder needed)
# ---------------------------------------------------------------------------

def test_truncate_model_is_a_prefix_of_the_demo_chain():
    import bisect_instance_bug as B
    model6 = B.demo_model()
    assert [e.tag for e in model6.equipment] == [f"PP-{i}" for i in range(1, 7)]
    m2 = B.truncate_model(model6, 2)
    assert [e.tag for e in m2.equipment] == ["PP-1", "PP-2"]
    assert [p.tag for p in m2.family_plans] == ["PP-1", "PP-2"]
    assert m2.feeders == [] or all(
        ed.target in ("PP-1", "PP-2") for ed in m2.feeders)
    # the original model is untouched (deep copy)
    assert len(model6.equipment) == 6 and len(model6.family_plans) == 6
    # the load order of the truncation is the demo chain's prefix
    import ifc_intent as T
    assert T._load_order(m2) == ["PP-1", "PP-2"]
    assert T._load_order(model6)[:2] == ["PP-1", "PP-2"]


# ---------------------------------------------------------------------------
# 2. the emitted ladder (recorded accounting is the gate evidence)
# ---------------------------------------------------------------------------

@needs_ladder
def test_every_rung_exists_with_recorded_md5(accounting):
    built = accounting["built"]
    assert set(LADDER) <= set(built), f"missing rungs: {set(LADDER) - set(built)}"
    for name in LADDER:
        f = os.path.join(ROOT, built[name]["file"])
        assert os.path.isfile(f), f
        assert _md5(f) == built[name]["md5"], f"{name}: file changed since build"


@needs_ladder
def test_accounting_gates_hold_for_every_rung(accounting):
    acc = accounting["accounting"]
    for name in LADDER:
        r = acc[name]
        # build-time validator state (before the instbug-fix stream's D1/D2
        # rules landed): recorded as 0 errors
        assert r["validator"]["n_errors"] == 0, (name, r["validator"])
        assert r["census"]["coherent"] is True, (name, r["census"])
        assert r["survivor_law_ok"] is True, name
        assert (r["identity_gate"] or {}).get("status") == "PASS", name
        assert r["element_diff"]["removed"] == 0, name
        assert r["element_diff"]["survivors_modified"] == 0, name
        # the append-path suspects are measured on every rung
        assert "rows_delta" in r["partition_table"], name
        assert "counters_delta" in r["storage_index"], name
    # the wall rung's intermediate hop is accounted too
    assert "BX_w_f1i1.hop_wall" in acc
    assert acc["BX_w_f1i1.hop_wall"]["validator"]["n_errors"] == 0


@needs_ladder
def test_current_validator_findings_are_exactly_the_reproduced_defects(accounting):
    """After the instbug-fix stream's two loaded-content rules (D1 connector-
    manager class, D2 ContentTable GUID order) landed in rvt.validate, the
    UNFIXED ladder must read exactly those findings and NOTHING unexpected:
    D1 on every rung with placed instances, D2 never on single-load rungs.
    (Run `tools/bisect_instance_bug.py verify` to refresh validator_now.)"""
    acc = accounting["accounting"]
    if not any("validator_now" in acc[n] for n in LADDER):
        pytest.skip("no verify run recorded yet (run: bisect_instance_bug.py verify)")
    for name in LADDER:
        vn = acc[name].get("validator_now")
        assert vn is not None, f"{name}: verify has not covered this rung"
        nf, ni, nw = SHAPE[name]
        known = vn["known_instbug_findings"]
        assert vn["unexpected_errors"] == [], (name, vn["unexpected_errors"])
        assert known["D1_connector_manager_class"] == (1 if ni else 0), (name, known)
        if nf < 2:
            assert known["D2_contenttable_guid_order"] == 0, (name, known)
        # every error is one of the two known findings
        assert vn["n_errors"] == sum(known.values()), (name, vn)


@needs_ladder
def test_census_deltas_match_the_rung_shapes(accounting):
    acc = accounting["accounting"]
    for name in LADDER:
        nf, ni, nw = SHAPE[name]
        r = acc[name]
        cd = r["census_delta"]
        et = r["elemtable"]
        if ni == 0 and nw == 0:
            # load rung: ONE load vs its chain parent
            assert cd["save_units"] == 1, name
            assert cd["contentdocs_entries"] == 1, name
            assert cd["contenttable_records"] == 1, name
            assert cd["familymgr_entries"] == 1, name
            assert et["n_added"] == LOAD_ELEMENTS, name
            changed = {s["stream"] for s in r["streams_changed"]}
            assert {"Global/ContentDocuments", "Global/Latest",
                    "Partitions/21", "Global/ElemTable"} <= changed, (name, changed)
        else:
            # instance (and wall) hops: NO registry motion, adds only
            assert cd["save_units"] == 0, name
            assert cd["contentdocs_entries"] == 0, name
            assert cd["contenttable_records"] == 0, name
            assert cd["familymgr_entries"] == 0, name
            assert et["n_added"] == ni, (name, et["n_added"])
            changed = {s["stream"] for s in r["streams_changed"]}
            assert changed == {"BasicFileInfo", "Global/ElemTable",
                               "Partitions/21"}, (name, changed)
            # the placed instances are NOT indexed by the ADocument (measured
            # fact, identical on the genesis AND the sample base)
            assert len(r.get("added_ids_unregistered_in_adocument") or []) == ni, name
        # the cross-base pair BX_f6i6 / SX_f6i6 must be shape-identical
    b, s = acc["BX_f6i6"], acc["SX_f6i6"]
    for k in ("save_units", "contentdocs_entries", "contenttable_records",
              "familymgr_entries"):
        assert b["census_delta"][k] == s["census_delta"][k]
    assert b["elemtable"]["n_added"] == s["elemtable"]["n_added"] == 6


@needs_ladder
def test_demo_shape_reproduced(accounting):
    """BX_f6i6 is the demo rebuilt: same four-registry shape as the failing
    DEMO_250v_room.rvt (units 7 / cd 6 / ct 6 / fm 15) and same row count."""
    r = accounting["accounting"]["BX_f6i6"]
    assert r["census"]["save_units"] == 7
    assert r["census"]["contentdocs_entries"] == 6
    assert r["census"]["contenttable_records"] == 6
    assert r["census"]["familymgr_entries"] == 15
    demo = os.path.join(ROOT, "experiments", "acceptance", "DEMO_250v_room.rvt")
    if os.path.isfile(demo):
        from rvt.famload import four_registry_census
        d = four_registry_census(demo)
        assert d["save_units"] == 7 and d["contentdocs_entries"] == 6
        assert d["contenttable_records"] == 6 and d["familymgr_entries"] == 15


@needs_ladder
def test_live_recomputation_matches_the_record_BX_f2(accounting):
    """One rung recomputed live (census + elemtable delta) == the record."""
    from rvt.famload import four_registry_census
    from rvt.container import open_rvt
    from rvt.stream_encoders import decode_elemtable
    rec = accounting["accounting"]["BX_f2"]
    child = os.path.join(OUT_DIR, "BX_f2.rvt")
    parent = os.path.join(ROOT, rec["immediate_parent"])
    assert os.path.isfile(parent), "chain parent pruned -- rebuild or relax"
    c = four_registry_census(child)
    assert c["save_units"] == rec["census"]["save_units"]
    assert c["contentdocs_entries"] == rec["census"]["contentdocs_entries"]
    assert c["contenttable_records"] == rec["census"]["contenttable_records"]
    assert c["coherent"] is True

    def rows(p):
        with open_rvt(p) as f:
            return {int(r[4]) for r in decode_elemtable(f.inflate("Global/ElemTable"))["records"]}

    added = sorted(rows(child) - rows(parent))
    assert added == rec["elemtable"]["added_ids"]


# ---------------------------------------------------------------------------
# 3. the staging manifest + gate
# ---------------------------------------------------------------------------

@needs_ladder
def test_probes_json_orders_the_ladder_and_declares_certified_bases(probes):
    order = [p["rung"] for p in probes["probes"]]
    assert order == list(LADDER)
    assert order[0] == "BX_f2" and order[1] == "BX_f1i1"
    for p in probes["probes"]:
        base = os.path.join(ROOT, p["base"])
        assert os.path.isfile(base), p["base"]
        if p["rung"].startswith("SX_"):
            assert p["base"] == "samples/rstbasicsampleproject.rvt"
        else:
            assert p["base"] == "experiments/genesis/subst_k4/compose/G_ABPD.rvt"
    assert "empty_design_caveat" in probes
    assert "reading_the_matrix" in probes


@needs_ladder
def test_probe_batch_gate_admits_the_ladder():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_t_instbug_pb", os.path.join(TOOLS, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(OUT_DIR, f"{r}.rvt") for r in LADDER]
    entries, violations = pb.check_batch(files)
    assert violations == [], violations
    for e in entries:
        assert e.base_status in ("certified", "sample"), (e.file, e.base_status)


@needs_ladder
def test_staged_batch_carries_gabpd_control_and_every_rung():
    import glob
    batches = []
    for p in glob.glob(os.path.join(ROOT, "experiments", "acceptance", "batch_*.json")):
        with open(p) as fh:
            m = json.load(fh)
        names = {os.path.splitext(os.path.basename(e.get("staged_as") or ""))[0]
                 for e in m.get("entries") or []}
        if set(LADDER) <= names:
            batches.append(m)
    assert batches, "the instbug ladder has not been staged (run: bisect_instance_bug.py stage)"
    m = max(batches, key=lambda x: x.get("batch") or 0)
    ctrl = [e for e in m["entries"] if e.get("kind") == "control"]
    assert len(ctrl) == 1
    assert ctrl[0]["control_source"] == "experiments/genesis/subst_k4/compose/G_ABPD.rvt"
    staged_ctrl = os.path.join(ROOT, ctrl[0]["staged_as"])
    assert _md5(staged_ctrl) == _md5(G_ABPD), "control must be byte-identical to G_ABPD"
    # reading order: control first, then the ladder in max-information order
    ro = m["reading_order"]
    assert ro[0].startswith("CTRL_")
    assert [os.path.splitext(x)[0] for x in ro[1:1 + len(LADDER)]] == list(LADDER)
