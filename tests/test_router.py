"""test_router.py -- THE PERMUTATION MATRIX + THE ROUTER contract
(src/rvt/frontdoor/{matrix,router}.py, tools/route.py; perm-matrix stream).

What is enforced here:

* the MATRIX IS HONEST BY CONSTRUCTION: every works/partial cell cites
  evidence and every citation resolves (test files exist, worked examples
  exist, every ``certified:`` ref is really in
  docs/coverage/viewer-certified.json's CERTIFIED list) -- a stale claim
  fails the suite;
* MATRIX <-> ROUTER coherence: every non-missing cell names a registered
  route implementation; every chain resolves;
* every WORKS cell has a smoke test: a fast structural smoke always runs
  (cell -> registered impl), and the runnable end-to-end smokes execute
  when their inputs are present (heavy builds gated the same way
  tests/test_frontdoor.py gates them: file presence + RVT_SKIP_LARGE);
* every MISSING cell answers with ok=False and THE one clear line naming
  the closest supported route -- never a traceback;
* CLI: ``tools/route.py matrix`` exits 0 (the self-audit passes live).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import matrix as MX     # noqa: E402
from rvt.frontdoor import router as R      # noqa: E402

PY = sys.executable
GENESIS = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
SPECIMENS = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
ROOM_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
PRODUCT_IFC = os.path.join(ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")
TINY_SPEC = os.path.join(ROOT, "spec", "examples", "tiny.json")
ROOM_SPEC = os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room", "room-spec.json")
WORKED_RVT = os.path.join(ROOT, "experiments", "frontdoor", "prompt-electrical-room",
                          "electrical_room_prompt.rvt")

PANEL_PROMPT = ("an eaton pow-r-line panelboard rated 400 A with 42 spaces at "
                "480Y/277 V, main breaker, surface mounted, named DP-7")
ROOM_PROMPT = ("an electrical room 30x20 ft rated for 2500 A service with a "
               "main switchboard, two 400 A distribution panels and four "
               "lighting panels")

skip_large = pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1",
                                reason="RVT_SKIP_LARGE=1")
needs_genesis = pytest.mark.skipif(
    not (os.path.exists(GENESIS) and os.path.exists(SPECIMENS)),
    reason="genesis base / specimen ancestor absent")
needs_rst = pytest.mark.skipif(not os.path.exists(RST), reason="rst host absent")


def _has_ifcopenshell() -> bool:
    try:
        import ifcopenshell  # noqa: F401
        return True
    except Exception:
        return False


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=400, spaces=42,
                                   voltage="480Y/277", mcb=True, mounting="surface",
                                   panel_name="X")
        return True
    except Exception:
        return False


needs_ifc = pytest.mark.skipif(not _has_ifcopenshell(), reason="ifcopenshell absent")
needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")


# ===========================================================================
# 1. the matrix is honest by construction
# ===========================================================================

def test_matrix_kinds_and_statuses():
    assert MX.INPUT_KINDS == ("prompt", "ifc", "rvt", "rfa", "spec")
    assert MX.OUTPUT_KINDS == ("rvt", "rfa", "ifc")
    for c in MX.all_cells():
        assert c.status in (MX.STATUS_WORKS, MX.STATUS_PARTIAL, MX.STATUS_MISSING)
        assert c.output in MX.OUTPUT_KINDS
        assert c.inputs == tuple(sorted(set(c.inputs)))
        for k in c.inputs:
            assert k in MX.INPUT_KINDS


def test_every_claimed_cell_carries_evidence_and_stages():
    for c in MX.all_cells():
        if c.status == MX.STATUS_MISSING:
            assert c.route is None
            assert c.missing_reason
        else:
            assert c.route, f"{c.key()} claims {c.status} without a route"
            assert c.evidence, f"{c.key()} claims {c.status} without evidence"
            assert c.stages, f"{c.key()} claims {c.status} without stages"


def _fresh_clone_missing_bins(problems):
    """True when EVERY audit problem is a certified .rvt under the
    git-ignored experiments/ tree AND none of those binaries exist here --
    the fresh-clone signature.  Any other problem class (ledger mismatch,
    missing tests/ citation) is a genuine stale citation everywhere."""
    import glob as _glob
    if not problems:
        return False
    if not all("certified file missing on disk: experiments/" in p
               for p in problems):
        return False
    return not _glob.glob(os.path.join(ROOT, "experiments", "acceptance",
                                       "*.rvt"))


def test_evidence_self_audit_is_clean():
    """THE honesty gate: every cited test/worked path exists on disk and
    every certified: citation is in the viewer ledger's CERTIFIED list."""
    problems = MX.verify_evidence()
    if _fresh_clone_missing_bins(problems):
        pytest.skip("certified evidence binaries live in git-ignored "
                    "experiments/ and are absent on a fresh clone")
    assert problems == [], "stale/false evidence citations:\n" + "\n".join(problems)


def test_matrix_router_coherence():
    for c in MX.all_cells():
        if c.route is not None:
            assert c.route in R._IMPLS, f"cell {c.key()} names unregistered route {c.route}"
    for name, ch in MX.CHAINS.items():
        assert ch["cell"] in MX.CELLS, name
        assert ch["route"] in R._IMPLS, f"chain {name} names unregistered route"
        for sid in ch["stages"]:
            assert sid in MX.STAGES


def test_singles_are_fully_enumerated():
    """Every single-input x output pair has an explicit cell (15 cells)."""
    for i in MX.INPUT_KINDS:
        for o in MX.OUTPUT_KINDS:
            assert MX.cell_for([i], o) is not None, f"({i},) -> {o} unenumerated"


def test_lookup_is_order_insensitive():
    a = MX.cell_for(["rvt", "prompt"], "rvt")
    b = MX.cell_for(["prompt", "rvt"], "rvt")
    assert a is not None and a is b


def test_closest_supported_prefers_same_output():
    c = MX.closest_supported(["rvt"], "ifc")
    assert c is not None and c.output == "ifc" and c.status != MX.STATUS_MISSING
    c2 = MX.closest_supported(["prompt", "spec"], "rvt")
    assert c2 is not None and c2.output == "rvt"


def test_missing_cells_point_to_live_closest():
    for c in MX.all_cells():
        if c.status != MX.STATUS_MISSING:
            continue
        line = MX.unsupported_line(list(c.inputs), c.output)
        assert "Closest supported route" in line
        assert c.missing_reason.split()[0].lower() in line.lower()


def test_matrix_as_json_serializes():
    j = json.dumps(MX.as_json(), default=str)
    assert "cells" in j and "chains" in j


# ===========================================================================
# 2. the router: unsupported cells = ONE clear line, never a traceback
# ===========================================================================

def _dummy_inputs(kinds, tmp_path):
    vals = {}
    for k in kinds:
        if k == "prompt":
            vals[k] = "do the thing"
        elif k == "rfa":
            vals[k] = {"kind": "downlight"}
        else:
            p = tmp_path / f"dummy.{k if k != 'spec' else 'json'}"
            p.write_bytes(b"{}" if k == "spec" else b"x")
            vals[k] = str(p)
    return vals


@pytest.mark.parametrize("cell", [c for c in MX.all_cells()
                                  if c.status == MX.STATUS_MISSING],
                         ids=lambda c: "+".join(c.inputs) + "->" + c.output)
def test_missing_cell_routes_to_clear_line(cell, tmp_path):
    res = R.route(_dummy_inputs(cell.inputs, tmp_path), cell.output)
    assert res.ok is False
    assert res.status == "UNSUPPORTED"
    assert res.line and "Closest supported route" in res.line
    assert res.files == {}


def test_unknown_combination_gets_the_fallback_line(tmp_path):
    spec = tmp_path / "s.json"
    spec.write_text("{}")
    res = R.route({"prompt": "x", "spec": str(spec)}, "rvt")
    assert res.ok is False and res.status == "UNSUPPORTED"
    assert "not a cell of the permutation matrix" in res.line
    assert "Closest supported route" in res.line


def test_bare_rfa_path_is_refused_with_the_row(tmp_path):
    res = R.route({"rfa": str(tmp_path / "some_family.rfa")}, "rvt",
                  out=str(tmp_path / "o"))
    assert res.ok is False
    assert "UNSUPPORTED-INPUT-FORM" in res.status
    assert "famspec" in res.line


def test_unwired_famspec_kind_names_the_room_pipeline(tmp_path):
    res = R.route({"rfa": {"kind": "panelboard"}}, "rvt", out=str(tmp_path / "o"))
    assert res.ok is False
    assert "UNSUPPORTED-FAMSPEC-KIND" in res.status
    assert "room pipeline" in res.line


def test_bad_arguments_raise_route_error(tmp_path):
    with pytest.raises(R.RouteError):
        R.route({"bogus": "x"}, "rvt")
    with pytest.raises(R.RouteError):
        R.route({"prompt": "x"}, "bogus")
    with pytest.raises(R.RouteError):
        R.route({}, "rvt")
    with pytest.raises(R.RouteError):
        R.route({"ifc": str(tmp_path / "missing.ifc")}, "rvt")


# ===========================================================================
# 3. WORKS cells: structural smoke for every one (always), end-to-end
#    smokes where the inputs allow
# ===========================================================================

@pytest.mark.parametrize("cell", [c for c in MX.all_cells()
                                  if c.status in (MX.STATUS_WORKS, MX.STATUS_PARTIAL)],
                         ids=lambda c: "+".join(c.inputs) + "->" + c.output)
def test_works_cell_resolves_to_registered_impl(cell):
    """The always-on smoke: the router resolves the cell and has the
    implementation registered (end-to-end runs below where inputs allow)."""
    assert cell.route in R._IMPLS
    assert callable(R._IMPLS[cell.route])


@needs_catalog
def test_e2e_prompt_to_rfa(tmp_path):
    res = R.route({"prompt": PANEL_PROMPT}, "rfa", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    rfas = [p for k, p in res.files.items() if k.startswith("rfa:")]
    assert rfas and all(os.path.isfile(p) for p in rfas)
    assert os.path.isfile(res.files["intent"])
    assert os.path.isfile(res.manifest_paths["route.json"])
    man = json.load(open(res.manifest_paths["route.json"]))
    assert man["cell"]["status"] == "works"
    assert man["evidence"], "route manifest must cite the matrix evidence"


@needs_ifc
@needs_catalog
def test_e2e_prompt_to_ifc_round_trips(tmp_path):
    res = R.route({"prompt": ROOM_PROMPT}, "ifc", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    ifc = res.files["ifc"]
    assert os.path.isfile(ifc)
    # the acceptance: our own resolver reads the emitted IFC back
    from rvt.frontdoor import intent as FI
    model = FI.intent_from_ifc(ifc)
    tags = {e.tag for e in model.equipment}
    assert "MSB" in tags and len(model.equipment) >= 7
    assert model.room and len(model.room.walls) == 4


@pytest.mark.skipif(not os.path.exists(TINY_SPEC), reason="spec example absent")
def test_e2e_spec_to_ifc(tmp_path):
    res = R.route({"spec": TINY_SPEC}, "ifc", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert os.path.isfile(res.files["ifc"])
    head = open(res.files["ifc"], "rb").read(64)
    assert head.startswith(b"ISO-10303-21")


@needs_ifc
def test_e2e_ifc_normalize(tmp_path):
    if not os.path.exists(ROOM_IFC):
        pytest.skip("worked room IFC absent")
    res = R.route({"ifc": ROOM_IFC}, "ifc", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert os.path.isfile(res.files["ifc"]) and os.path.isfile(res.files["intent"])


@needs_ifc
@needs_catalog
@pytest.mark.skipif(not os.path.exists(ROOM_SPEC), reason="room spec absent")
@skip_large
def test_e2e_spec_to_rfa_chain(tmp_path):
    res = R.route({"spec": ROOM_SPEC}, "rfa", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    rfas = [p for k, p in res.files.items() if k.startswith("rfa:")]
    assert rfas, "the spec's tagged equipment must yield catalog families"
    steps = [s["stage"] for s in res.steps]
    assert steps[:2] == ["spec->ifc", "ifc->intent"]


@pytest.mark.skipif(not os.path.exists(WORKED_RVT), reason="worked .rvt absent")
def test_e2e_prompt_rvt_edit(tmp_path):
    res = R.route({"rvt": WORKED_RVT, "prompt": "move DP-1 to 3,1,4.66"},
                  "rvt", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert os.path.isfile(res.files["edited"])
    assert res.route == "rvt_edit"
    assert any("PROOF-ONLY" in s for s in res.stamps)


@needs_ifc
@needs_catalog
@needs_rst
@skip_large
def test_e2e_famspec_downlight_loaded(tmp_path):
    """The RFA -> loaded-RVT combination (the certified L1a/L_downlight
    mechanism, reproduced by the router)."""
    res = R.route({"rfa": {"kind": "downlight"}}, "rvt", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert os.path.isfile(res.files["rfa"])
    assert os.path.isfile(res.files["loaded_rvt"])
    rep = json.load(open(res.files["load_report"]))
    assert rep["ok"] is True
    assert rep["validate_project_mode"]["verdict"] == "VALID"


@needs_ifc
@needs_catalog
@needs_genesis
@skip_large
def test_e2e_prompt_via_ifc_to_rvt_chain(tmp_path):
    """The mandated chain: prompt -> IFC -> RVT, run in-process."""
    res = R.route({"prompt": ROOM_PROMPT}, "rvt", via="ifc",
                  out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert os.path.isfile(res.files["ifc"])
    assert os.path.isfile(res.files["intent_from_prompt"])
    assert res.files.get("combined") and os.path.isfile(res.files["combined"])
    assert any("walls+families" in s for s in res.stamps), \
        "the open-bug stamp must ride the combined file"


@needs_ifc
@needs_catalog
@needs_genesis
@skip_large
def test_e2e_ifc_to_rvt(tmp_path):
    if not os.path.exists(ROOM_IFC):
        pytest.skip("worked room IFC absent")
    res = R.route({"ifc": ROOM_IFC}, "rvt", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert res.files.get("combined") and os.path.isfile(res.files["combined"])


# ===========================================================================
# 4. the route manifest contract
# ===========================================================================

@pytest.mark.skipif(not os.path.exists(TINY_SPEC), reason="spec example absent")
def test_route_manifest_shape(tmp_path):
    res = R.route({"spec": TINY_SPEC}, "ifc", out=str(tmp_path / "o"))
    man = json.load(open(res.manifest_paths["route.json"]))
    for key in ("cell", "route", "steps", "files", "caveats", "evidence",
                "deliverable_rule", "status"):
        assert key in man
    assert man["cell"]["inputs"] == ["spec"] and man["cell"]["output"] == "ifc"
    assert all("stage" in s and "impl" in s and "seconds" in s for s in man["steps"])
    md = open(res.manifest_paths["ROUTE.md"]).read()
    assert "# route: spec -> ifc" in md and "delivered" in md


# ===========================================================================
# 5. the CLI
# ===========================================================================

def test_cli_matrix_self_audits():
    if _fresh_clone_missing_bins(MX.verify_evidence()):
        pytest.skip("certified evidence binaries live in git-ignored "
                    "experiments/ and are absent on a fresh clone")
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "matrix"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "PERMUTATION MATRIX" in p.stdout
    assert "evidence self-audit: every citation checks out" in p.stdout


def test_cli_unsupported_exit_code(tmp_path):
    rvt = tmp_path / "x.rvt"
    rvt.write_bytes(b"x")
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "run",
                        "--output", "ifc", "--rvt", str(rvt)],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 4, p.stdout + p.stderr
    assert "Closest supported route" in p.stdout


def test_cli_explain_missing_cell():
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "explain",
                        "--output", "rfa", "--inputs", "prompt,rfa"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 4
    assert "MISSING" in p.stdout and "prompt->rfa" in p.stdout.replace(" ", "")


def test_cli_usage_error_is_2():
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "explain",
                        "--output", "rfa", "--inputs", "sonnet"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 2
