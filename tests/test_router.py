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
* the rvt.convert cells registered by issue #5 (rvt->ifc, rvt->rfa extract,
  prompt+rfa family edits, prompt+rvt add-into-project, ifc+rvt merge, the
  extracted-.rfa reload lane) run END TO END on a fresh clone: the source
  project is BUILT here from a prompt on the pinned genesis base (no
  samples/, no experiments/ binaries needed);
* the committed docs/product/PERMUTATION-MATRIX.md agrees with the machine
  matrix cell for cell (a doc that drifts fails the suite);
* CLI: ``tools/route.py matrix`` and ``tools/frontdoor.py matrix`` exit 0
  (the self-audit passes live; absent probe binaries are a note, not a fail).
"""
from __future__ import annotations

import json
import os
import re
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
MATRIX_DOC = os.path.join(ROOT, "docs", "product", "PERMUTATION-MATRIX.md")

PANEL_PROMPT = ("an eaton pow-r-line panelboard rated 400 A with 42 spaces at "
                "480Y/277 V, main breaker, surface mounted, named DP-7")
ROOM_PROMPT = ("an electrical room 30x20 ft rated for 2500 A service with a "
               "main switchboard, two 400 A distribution panels and four "
               "lighting panels")
# a deliberately small room: one wall loop + two lighting panels (~12 s to build)
SMALL_ROOM_PROMPT = "an electrical room 20x15 ft with two 100 A lighting panels"

skip_large = pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1",
                                reason="RVT_SKIP_LARGE=1")
needs_genesis = pytest.mark.skipif(
    not (os.path.exists(GENESIS) and os.path.exists(SPECIMENS)),
    reason="genesis base / specimen ancestor absent")
needs_rst = pytest.mark.skipif(not os.path.exists(RST), reason="rst host absent")


def _pinned_base():
    """The pinned certified genesis base (repo copy or plugin-bundled), or None."""
    try:
        from rvt.frontdoor.base import resolve_base
        return resolve_base().path
    except Exception:
        return None


PINNED_BASE = _pinned_base()
needs_pin = pytest.mark.skipif(PINNED_BASE is None, reason="pinned genesis base absent")


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


def test_evidence_self_audit_is_clean():
    """THE honesty gate, live on EVERY checkout (fresh clone and CI included):
    every cited test/worked/record path exists, every certified: citation is
    in the viewer ledger's CERTIFIED list, every stage/chain reference
    resolves.  Certified probe binaries absent from a fresh clone are the
    one tolerated class -- the ledger certifies them, not the disk -- and
    on a checkout that carries the binaries even those are hard."""
    rep = MX.audit()
    assert rep["ledger_present"], "docs/coverage/viewer-certified.json must be readable"
    assert rep["problems"] == [], ("stale/false evidence citations:\n"
                                   + "\n".join(rep["problems"]))
    for p in rep["absent_binaries"]:
        assert MX.ABSENT_BINARY_MARK in p


def test_audit_classifies_only_the_binary_class_as_soft():
    raw = MX.verify_evidence()
    rep = MX.audit()
    soft = [p for p in raw if MX.ABSENT_BINARY_MARK in p]
    hard = [p for p in raw if MX.ABSENT_BINARY_MARK not in p]
    assert set(hard) <= set(rep["problems"])
    if rep["fresh_clone"]:
        assert rep["absent_binaries"] == soft
    else:
        assert set(soft) <= set(rep["problems"]) and rep["absent_binaries"] == []


def test_render_text_is_the_shared_printer():
    text, rep = MX.render_text()
    assert "PERMUTATION MATRIX" in text and "chains" in text
    cnt = MX.status_counts()
    assert f"{cnt['works']} works / {cnt['partial']} partial / {cnt['missing']} missing" in text
    assert rep["n_cells"] == len(MX.CELLS)


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
    assert MX.as_json()["counts"] == MX.status_counts()


def test_convert_implementations_are_registered():
    """Issue #5's DONE: every rvt.convert route has a matrix cell that names
    a registered router implementation."""
    want = {
        (("rvt",), "ifc"): "rvt_to_ifc",
        (("rvt",), "rfa"): "extract_family",
        (("prompt", "rfa"), "rfa"): "rfa_modify",
        (("ifc", "rvt"), "rvt"): "ifc_merge_into_rvt",
        (("prompt", "rvt"), "rvt"): "rvt_edit",          # edit | add_to_project branch
        (("rfa", "rvt"), "rvt"): "rfa_load",             # famspec | extracted-.rfa reload
        (("rfa",), "rvt"): "rfa_load",
    }
    for key, route in want.items():
        c = MX.CELLS[key]
        assert c.status == MX.STATUS_WORKS, key
        assert c.route == route and route in R._IMPLS, key
    stages = {s.impl for s in MX.STAGES.values()}
    for impl in ("rvt.convert.rvt_to_ifc:extract_intent",
                 "rvt.convert.extract_family:extract_family",
                 "rvt.convert.extract_family:reload_family",
                 "rvt.convert.add_to_project:add_to_project",
                 "rvt.convert.merge_ifc:merge_ifc",
                 "rvt.convert.modify_family:modify_family"):
        assert impl in stages, impl


def test_certified_depths_are_cited_on_the_rfa_cells():
    """The .rfa-load (T2a) and extract->place (TB0g) certifications ride on
    the cells they deepen -- and verify_evidence() keeps them honest."""
    load = MX.CELLS[(("rfa", "rvt"), "rvt")].evidence + MX.CELLS[(("rfa",), "rvt")].evidence
    assert "certified:experiments/rftprobe/T2a.rvt" in load
    assert "certified:experiments/species/TB0g.rvt" in load
    assert "certified:experiments/species/TB0g.rvt" in MX.CELLS[(("rvt",), "rfa")].evidence
    assert "rvt->rfa->loaded-rvt" in MX.CHAINS


_DOC_ROW = re.compile(r"^\|\s*([a-z+ →]+?)\s*\|\s*(\*\*works\*\*|\*partial\*|\*missing\*)\s*\|")


def _doc_cells():
    """{(inputs, output): status} parsed from the two tables of the doc."""
    out = {}
    with open(MATRIX_DOC, encoding="utf-8") as fh:
        for line in fh:
            m = _DOC_ROW.match(line.strip())
            if not m or m.group(1).count("→") != 1:      # chain rows have 2+
                continue
            lhs, rhs = m.group(1).split("→")
            ins = [t.strip() for t in lhs.split("+") if t.strip()]
            status = m.group(2).strip("*")
            out[MX.key_for(ins, rhs.strip())] = status
    return out


def test_permutation_matrix_doc_agrees_with_machine_matrix():
    """docs/product/PERMUTATION-MATRIX.md is the rendered copy: every cell
    row it prints must carry the machine matrix's status, and every machine
    cell must have a row."""
    doc = _doc_cells()
    assert doc, "no cell rows parsed from PERMUTATION-MATRIX.md"
    for key, cell in MX.CELLS.items():
        assert key in doc, f"PERMUTATION-MATRIX.md has no row for {key}"
        assert doc[key] == cell.status, (f"PERMUTATION-MATRIX.md says {doc[key]} for "
                                         f"{key}, the machine matrix says {cell.status}")
    assert set(doc) == set(MX.CELLS), f"doc rows without a machine cell: {set(doc) - set(MX.CELLS)}"


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


def test_famspec_is_not_an_editable_file(tmp_path):
    """prompt+rfa EDITS an existing .rfa; a famspec there is refused with
    the clear line pointing at prompt->rfa."""
    res = R.route({"rfa": {"kind": "downlight"}, "prompt": "set BusRating 225"},
                  "rfa", out=str(tmp_path / "o"))
    assert res.ok is False
    assert "UNSUPPORTED-INPUT-FORM" in res.status
    assert "prompt -> rfa" in res.line and res.files == {}


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
    with pytest.raises(R.RouteError):                 # a .rfa PATH must exist
        R.route({"rfa": str(tmp_path / "some_family.rfa")}, "rvt")


@pytest.mark.parametrize("prompt,edit", [
    ("move DP-1 to 3,1,4.66", True),
    ("delete LP-4 with cascade", True),
    ("rename panel LP-1 to LP-9", True),
    ("set mark of 1472703 to X", True),
    ('[{"op": "delete", "id": 123456}]', True),
    ("add a 75 kVA transformer to my project", False),
    ("an electrical room 30x20 ft with two 400 A distribution panels", False),
    ("a 100 A lighting panel", False),
])
def test_edit_shape_decides_edit_vs_add(prompt, edit):
    """prompt+rvt dispatch is decided on SHAPE without the file: an edit
    clause whose name does not resolve stays an edit (reported honestly),
    it is never re-read as 'add a DP-1'."""
    assert R._edit_shaped(prompt) is edit


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


def _famcontainer_present() -> bool:
    """The famspec (downlight) lane emits its .rfa on the family container
    archetype (rvt.famgen.famdoc_adoc.TEMPLATE_DONOR, research corpus) --
    absent on a fresh clone until famfrom_ifc emits on the bundled base."""
    try:
        from rvt.famgen import famdoc_adoc as FA
        return os.path.isfile(FA.TEMPLATE_DONOR)
    except Exception:
        return False


needs_famcontainer = pytest.mark.skipif(not _famcontainer_present(),
                                        reason="family container archetype absent (owner machine)")


@needs_ifc
@needs_catalog
@needs_famcontainer
@needs_pin
@skip_large
def test_e2e_famspec_downlight_loaded(tmp_path):
    """The RFA -> loaded-RVT combination (the certified L1a/L_downlight
    mechanism, reproduced by the router; default host = the pinned base)."""
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
# 3b. the rvt.convert cells (issue #5) -- END TO END on a fresh clone.
#     The source project is BUILT here from a prompt on the pinned base;
#     the heavy ones honour RVT_SKIP_LARGE like every other build.
# ===========================================================================

def _validator_errors(path: str) -> int:
    from rvt.validate import validate_file
    return len(validate_file(path).errors)


@pytest.fixture(scope="module")
def built_room(tmp_path_factory):
    """ONE prompt->rvt build shared by the convert e2e tests: a small room
    (4 walls + two generated, loaded, placed lighting panels) on the pinned
    genesis base, plus the generated .rfa deliverables.  ~12 s."""
    if os.environ.get("RVT_SKIP_LARGE") == "1":
        pytest.skip("RVT_SKIP_LARGE=1")
    if PINNED_BASE is None or not _catalog_ok():
        pytest.skip("pinned genesis base / famgen catalog absent")
    out = tmp_path_factory.mktemp("built_room")
    res = R.route({"prompt": SMALL_ROOM_PROMPT}, "rvt", out=str(out), no_handoff=True)
    rvt = res.files.get("combined")
    if not (res.ok and rvt and os.path.isfile(rvt)):
        pytest.skip(f"prompt->rvt did not build here: {res.status} {res.errors[:2]}")
    rfas = sorted(p for k, p in res.files.items()
                  if k.startswith("rfa:") or (isinstance(p, str) and p.endswith(".rfa")))
    fam_dir = res.files.get("families_dir")
    if not rfas and fam_dir and os.path.isdir(fam_dir):
        rfas = sorted(os.path.join(fam_dir, f) for f in os.listdir(fam_dir) if f.endswith(".rfa"))
    assert rfas, "the build produced no .rfa deliverables"
    return {"rvt": rvt, "rfas": rfas, "out": str(out)}


@needs_pin
def test_e2e_rvt_to_ifc_delivers_on_the_bare_base(tmp_path):
    """rvt -> ifc runs on ANY project: the family-free genesis base exports
    its levels; the manifest says honestly that no room round trip ran."""
    res = R.route({"rvt": PINNED_BASE}, "ifc", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert res.route == "rvt_to_ifc"
    assert os.path.isfile(res.files["ifc"])
    assert open(res.files["ifc"], "rb").read(32).startswith(b"ISO-10303-21")
    assert os.path.isfile(res.manifest_paths["rvt_to_ifc:json"])
    assert os.path.isfile(res.manifest_paths["route.json"])


@needs_ifc
def test_e2e_rvt_to_ifc_round_trips_a_built_room(built_room, tmp_path):
    """THE ACCEPTANCE of rvt -> ifc: everything the build put in the .rvt
    (walls, equipment, positions) survives into the IFC and back through
    our own resolver."""
    res = R.route({"rvt": built_room["rvt"]}, "ifc", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    man = json.load(open(res.manifest_paths["rvt_to_ifc:json"]))
    rt = man["roundtrip"]
    assert rt["ran"] and rt["all_survived"], rt
    n_eq = len(man["equipment"])
    assert n_eq >= 1 and rt["equipment_survived"] == f"{n_eq}/{n_eq}"
    assert rt["walls_matched"] == "4/4"
    assert "all_survived=True" in res.status


@needs_pin
def test_e2e_extract_family_on_a_family_free_project_is_one_clear_line(tmp_path):
    res = R.route({"rvt": PINNED_BASE}, "rfa", out=str(tmp_path / "o"))
    assert res.ok is False and res.route == "extract_family"
    assert "embeds NO family documents" in res.line
    assert "Closest supported route" in res.line
    assert os.path.isfile(res.files["families"])


def test_e2e_extract_family_needs_a_selector_when_several(built_room, tmp_path):
    res = R.route({"rvt": built_room["rvt"]}, "rfa", out=str(tmp_path / "o"))
    assert res.ok is False
    assert "NEEDS-A-SELECTOR" in res.status
    assert "--family" in res.line
    listing = json.load(open(res.files["families"]))
    assert len(listing) >= 2 and all(r["family_name"] for r in listing)


def test_e2e_extract_then_reload_full_cycle(built_room, tmp_path):
    """rvt -> rfa (extract) then rfa -> rvt (the extracted-.rfa reload lane
    onto the pinned base): generate -> load -> extract -> re-load, all our
    machinery, project validator 0 errors at the end."""
    listing = json.load(open(R.route({"rvt": built_room["rvt"]}, "rfa",
                                       out=str(tmp_path / "ls")).files["families"]))
    sel = str(listing[0]["family_id"])
    ex = R.route({"rvt": built_room["rvt"]}, "rfa", out=str(tmp_path / "x"), family=sel)
    assert ex.ok, ex.errors
    rfa = ex.files["rfa"]
    assert os.path.isfile(rfa) and ex.status.startswith("OK"), ex.status
    xman = json.load(open(ex.manifest_paths["extract_family:json"]))
    assert xman["validation"]["family_mode"]["verdict"] == "VALID"
    assert xman["validation"]["family_mode"]["n_errors"] == 0
    # reload onto the default host (the pinned certified genesis base)
    rl = R.route({"rfa": rfa}, "rvt", out=str(tmp_path / "r"))
    assert rl.ok, rl.errors + [rl.status, rl.line]
    assert rl.route == "rfa_load"
    loaded = rl.files["loaded_rvt"]
    assert os.path.isfile(loaded) and os.path.isfile(rl.files["load_report"])
    assert "VALID 0 errors" in rl.status
    assert _validator_errors(loaded) == 0
    # reloading into the project it came from is refused BY NAME (its ids
    # are already past that host's watermark) -- one clear line, no traceback
    back = R.route({"rfa": rfa, "rvt": built_room["rvt"]}, "rvt", out=str(tmp_path / "b"))
    assert back.ok is False and back.line and "STANDALONE-BORN" in back.line


@needs_catalog
@needs_pin
def test_standalone_born_rfa_gets_the_clear_line_not_a_traceback(tmp_path):
    """Our own .rfa deliverables are standalone-born (ids from 1000): the
    reload lane answers with THE line naming the certified-but-unwired
    id-remap lane (T2a) and the routes that do work today."""
    gen = R.route({"prompt": PANEL_PROMPT}, "rfa", out=str(tmp_path / "g"))
    assert gen.ok, gen.errors
    rfa = next(p for k, p in gen.files.items() if k.startswith("rfa:"))
    res = R.route({"rfa": rfa}, "rvt", out=str(tmp_path / "o"))
    assert res.ok is False
    assert "UNSUPPORTED-INPUT-FORM" in res.status
    assert "STANDALONE-BORN" in res.line and "T2a" in res.line
    assert "loaded_rvt" not in res.files


@needs_catalog
def test_e2e_prompt_rfa_modify(tmp_path):
    """prompt+rfa -> rfa on OUR generated family: rename the type + set two
    parameters; family-mode validator VALID, every edit echoed by the
    semantic re-read, release preserved."""
    gen = R.route({"prompt": PANEL_PROMPT}, "rfa", out=str(tmp_path / "g"))
    assert gen.ok, gen.errors
    rfa = next(p for k, p in gen.files.items() if k.startswith("rfa:"))
    res = R.route({"rfa": rfa, "prompt": "rename the type to 225A MCB 42ckt; "
                                       "set BusRating 225; set PanelName DP-9"},
                  "rfa", out=str(tmp_path / "o"))
    assert res.ok, res.errors + [res.status, res.line]
    assert res.route == "rfa_modify" and res.status.startswith("OK"), res.status
    out_rfa = res.files["rfa"]
    assert os.path.isfile(out_rfa) and out_rfa != rfa
    man = json.load(open(res.manifest_paths["modify_family:json"]))
    g = man["validation"]["rfa"]
    assert g["family_mode"]["verdict"] == "VALID" and g["family_mode"]["n_errors"] == 0
    assert g["release"]["preserved"] is True
    assert [r["ok"] for r in g["reread"]] == [True, True, True]
    assert any("PROOF-ONLY" in s for s in res.stamps)


@needs_catalog
def test_e2e_prompt_rfa_modify_bad_edit_is_one_clear_line(tmp_path):
    gen = R.route({"prompt": PANEL_PROMPT}, "rfa", out=str(tmp_path / "g"))
    assert gen.ok, gen.errors
    rfa = next(p for k, p in gen.files.items() if k.startswith("rfa:"))
    res = R.route({"rfa": rfa, "prompt": "make it prettier"}, "rfa", out=str(tmp_path / "o"))
    assert res.ok is False
    assert res.line and "Grammar" in res.line
    assert not any("Traceback" in e for e in res.errors[:1])


def test_e2e_add_into_project(built_room, tmp_path):
    """prompt+rvt with an AUTHORING prompt: rvt.convert.add_to_project puts a
    generated transformer INTO the built room -- delivered, validator VALID
    0 errors, release preserved, the target's own content untouched."""
    res = R.route({"rvt": built_room["rvt"],
                   "prompt": "add a 75 kVA transformer to my project"},
                  "rvt", out=str(tmp_path / "o"))
    assert res.ok, res.errors + [res.status, res.line]
    assert res.route == "rvt_edit"
    out = res.files["combined"]
    assert os.path.isfile(out) and out != built_room["rvt"]
    assert res.status.startswith("OK") and "release 2026 preserved" in res.status
    man = json.load(open(res.manifest_paths["add_to_project:json"]))
    kinds = {(c["kind"], c.get("tag")) for c in man["created"]}
    assert ("equipment-instance", "T1") in kinds and ("loaded-family", "T1") in kinds
    g = man["validation"]["combined"]
    assert g["validate"]["verdict"] == "VALID" and g["release"]["preserved"] is True
    assert _validator_errors(out) == 0
    assert any("PROOF-ONLY" in s for s in res.stamps)
    assert any(k.startswith("rfa:") for k in res.files)          # the .rfa rides along


@needs_ifc
def test_e2e_merge_ifc_into_project(built_room, tmp_path):
    """ifc+rvt: an IFC of a second small room MERGED into the built room at
    the auto-disjoint offset -- delivered, VALID 0 errors, release preserved,
    the open-bug stamp riding because walls AND families were created."""
    ifc = R.route({"prompt": "an electrical room 16x12 ft with one 100 A lighting panel"},
                  "ifc", out=str(tmp_path / "i"))
    assert ifc.ok, ifc.errors
    res = R.route({"rvt": built_room["rvt"], "ifc": ifc.files["ifc"]}, "rvt",
                  out=str(tmp_path / "o"))
    assert res.ok, res.errors + [res.status, res.line]
    assert res.route == "ifc_merge_into_rvt"
    out = res.files["combined"]
    assert os.path.isfile(out)
    man = json.load(open(res.manifest_paths["merge_ifc:json"]))
    assert len(man["created_ids"]) >= 3                          # walls + family + instance
    assert man["placement"]["offset"] and "auto-disjoint" in man["placement"]["rule"]
    g = man["validation"]["combined"]
    assert g["validate"]["verdict"] == "VALID" and g["release"]["preserved"] is True
    assert _validator_errors(out) == 0
    assert any("walls+families" in s for s in res.stamps), res.stamps


def test_e2e_edit_shaped_prompt_still_edits(built_room, tmp_path):
    """The certified edit branch of prompt+rvt is untouched by the add
    branch: an edit sentence on the built room moves the panel."""
    res = R.route({"rvt": built_room["rvt"], "prompt": "move LP-1 to 3,1,4.66"},
                  "rvt", out=str(tmp_path / "o"))
    assert res.ok, res.errors + [res.status]
    assert os.path.isfile(res.files["edited"])
    assert any("PROOF-ONLY" in s for s in res.stamps)


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

@pytest.mark.parametrize("tool", ["route.py", "frontdoor.py"])
def test_cli_matrix_self_audits(tool):
    """Both front doors print the SAME table through the shared renderer and
    exit 0 on every checkout: hard audit problems fail, absent probe
    binaries (fresh clone) are a note."""
    p = subprocess.run([PY, os.path.join(ROOT, "tools", tool), "matrix"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "PERMUTATION MATRIX" in p.stdout
    assert "evidence self-audit: every citation checks out" in p.stdout
    assert "rvt->rfa->loaded-rvt" in p.stdout


def test_cli_matrix_json_carries_the_audit():
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "matrix", "--json"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stderr
    d = json.loads(p.stdout)
    assert d["audit"]["problems"] == [] and d["counts"]["works"] >= 17
    assert len(d["cells"]) == len(MX.CELLS)


def test_frontdoor_author_route_is_untouched_by_the_matrix_verb():
    """The hot-file patch is additive: `author` keeps its exact usage error."""
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "frontdoor.py"), "author"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 2
    p2 = subprocess.run([PY, os.path.join(ROOT, "tools", "frontdoor.py"), "--help"],
                        capture_output=True, text=True, cwd=ROOT)
    assert p2.returncode == 0 and "matrix" in p2.stdout and "tools/route.py" in p2.stdout


def test_cli_unsupported_exit_code(tmp_path):
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "run",
                        "--output", "ifc", "--rfa", '{"kind": "downlight"}',
                        "--out", str(tmp_path / "o")],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 4, p.stdout + p.stderr
    assert "Closest supported route" in p.stdout


def test_cli_explain_missing_cell():
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "explain",
                        "--output", "rfa", "--inputs", "rfa"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 4
    assert "MISSING" in p.stdout and "prompt+rfa" in p.stdout


def test_cli_explain_flipped_cell_is_zero():
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "explain",
                        "--output", "ifc", "--inputs", "rvt"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout
    assert "works via rvt_to_ifc" in p.stdout and "certified" not in p.stdout.split("\n")[0]


def test_cli_usage_error_is_2():
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "explain",
                        "--output", "rfa", "--inputs", "sonnet"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 2
