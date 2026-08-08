"""tests for the CRUD x category coverage harness (tools/coverage.py).

Asserts the matrix definition loads and is well-formed (every category has
exactly one cell per verb), the status resolver behaves, and the runner
executes end to end on a 2-cell subset — validate-only, so the test never
regenerates proof files (that costs minutes and belongs to the harness run).
"""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import coverage  # noqa: E402

MATRIX = os.path.join(ROOT, "docs", "coverage", "matrix.json")
LEDGER = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")
VERBS = ["create", "read", "modify", "move", "retype", "delete"]

REQUIRED_CATEGORIES = {
    "family_instances", "walls", "floors_roofs_ceilings", "doors_windows",
    "columns_beams", "curtain_walls", "stairs_railings", "rooms_spaces",
    "conduit", "cable_tray", "duct", "pipe", "fittings", "wires",
    "electrical_equipment", "electrical_devices", "lighting_fixtures",
    "circuits_systems", "panel_schedules", "views_sheets", "tags_annotation",
    "levels", "phases", "types", "families", "materials", "parameters",
    "worksets_links",
}


@pytest.fixture(scope="module")
def matrix():
    return coverage.load_matrix(MATRIX)


def test_matrix_loads_and_is_complete(matrix):
    assert matrix["verbs"] == VERBS
    cats = {c["key"] for c in matrix["categories"]}
    assert REQUIRED_CATEGORIES <= cats
    # exactly one cell per (category, verb) — load_matrix already enforces it,
    # re-check the arithmetic here so a regression is obvious
    assert len(matrix["cells"]) == len(cats) * len(VERBS)
    keys = {(c["category"], c["verb"]) for c in matrix["cells"]}
    assert len(keys) == len(matrix["cells"])
    for cat in cats:
        for v in VERBS:
            assert (cat, v) in keys


def test_matrix_wiring_is_consistent(matrix):
    gens = matrix["generators"]
    for cell in matrix["cells"]:
        if cell.get("generator"):
            assert cell["generator"] in gens
        for g in cell.get("extra_generators") or []:
            assert g in gens
        if cell.get("na"):
            assert not cell.get("proof_file"), f"NA cell carries a proof: {cell}"
    # every generator declares a command and its outputs
    for key, g in gens.items():
        assert g.get("cmd"), key
        assert g.get("outputs"), key
    # ledger loads; every entry is a repo-relative .rvt path
    ledger = coverage.load_ledger(LEDGER)
    assert ledger, "viewer-certified ledger is empty"
    for path in ledger:
        assert path.endswith(".rvt")


def test_resolve_status_logic(matrix):
    cell = {"category": "x", "verb": "create", "function": "f",
            "proof_file": "a.rvt"}
    good = {"path": "a.rvt", "exists": True, "validates": True, "error_count": 0}
    bad = {"path": "a.rvt", "exists": True, "validates": False, "error_count": 3}
    gone = {"path": "a.rvt", "exists": False, "validates": False, "error_count": None}
    ledger = {"a.rvt": {"file": "a.rvt"}}
    assert coverage.resolve_status(cell, [good], {}, None)[0] == "VALIDATES"
    assert coverage.resolve_status(cell, [good], ledger, None)[0] == "CERTIFIED"
    assert coverage.resolve_status(cell, [bad], {}, None)[0] == "FAILS"
    assert coverage.resolve_status(cell, [bad], ledger, None)[0] == "REGRESSED"
    assert coverage.resolve_status(cell, [gone], {}, None)[0] == "UNPROVEN"
    assert coverage.resolve_status(dict(cell, na="n/a"), [good], {}, None)[0] == "NA"
    assert coverage.resolve_status(dict(cell, blocked="b"), [good], {}, None)[0] == "BLOCKED"
    fnless = {"category": "x", "verb": "create"}
    assert coverage.resolve_status(fnless, [], {}, None)[0] == "MISSING"
    read = {"category": "x", "verb": "read", "function": "f"}
    assert coverage.resolve_status(read, [], {}, {"passed": True})[0] == "VALIDATES"
    assert coverage.resolve_status(read, [], {}, {"passed": False})[0] == "FAILS"
    assert coverage.resolve_status(read, [], {}, None)[0] == "UNPROVEN"
    # a read cell backed by a proof file (e.g. the .rfa round-trip) instead of a probe
    read_proof = dict(read, proof_file="a.rvt")
    assert coverage.resolve_status(read_proof, [good], {}, None)[0] == "VALIDATES"
    assert coverage.resolve_status(read_proof, [good], ledger, None)[0] == "CERTIFIED"
    assert coverage.resolve_status(read_proof, [bad], {}, {"passed": True})[0] == "VALIDATES"


def test_runner_executes_on_two_cells(matrix):
    """End-to-end on a cheap 2-cell subset: one proof-file cell (viewer-
    certified V20/V21, ~3 s each to validate) and one READ probe cell."""
    m = copy.deepcopy(matrix)
    cells = ["family_instances:create", "levels:read"]
    by0 = {(c["category"], c["verb"]): c for c in m["cells"]}
    missing = [p for cell in cells
               for p in coverage.proof_paths(by0[tuple(cell.split(":"))])
               if not os.path.isfile(os.path.join(ROOT, p))]
    if missing:
        pytest.skip("proof files not on this machine (git-ignored "
                    "experiments/): " + ", ".join(missing))
    summary = coverage.run(m, cells=cells, validate_only=True, log=lambda *a: None)
    by = {(c["category"], c["verb"]): c for c in m["cells"]}
    fi = by[("family_instances", "create")]["result"]
    lv = by[("levels", "read")]["result"]
    assert fi is not None and lv is not None
    assert fi["status"] in ("CERTIFIED", "VALIDATES"), fi
    assert fi["validates"] is True
    assert fi["error_count"] == 0
    assert isinstance(fi["viewer_certified"], bool)
    assert "last_run" in fi
    assert lv["status"] == "VALIDATES", lv
    assert lv["detail"]["probe"]["passed"] is True
    # the summary block is coherent
    assert summary["run"]["cells_selected"] == 2
    assert summary["run"]["mode"] == "validate-only"
    assert 0.0 <= summary["overall_pct"] <= 100.0
    for st, n in summary["counts"].items():
        assert n >= 0


def test_markdown_renders(matrix):
    m = copy.deepcopy(matrix)
    coverage.run(m, cells=["conduit:read"], validate_only=True, log=lambda *a: None)
    md = coverage.render_markdown(m)
    assert "# Writer coverage matrix" in md
    assert "Headline" in md
    assert "conduit" in md
    for v in VERBS:
        assert v in md
