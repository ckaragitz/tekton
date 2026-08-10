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
    """A REAL wheel: spec->ifc AUTHORS through ``ifcopenshell.api``; the bundled
    steplite shim (on ``sys.path`` as soon as ``rvt.ifc`` is imported -- the
    router above already did) only reads, so importability alone proves nothing."""
    try:
        import ifcopenshell
        return not getattr(ifcopenshell, "IS_STEPLITE", False)
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


needs_ifc = pytest.mark.skipif(not _has_ifcopenshell(),
                               reason="ifcopenshell wheel absent (steplite shim only reads)")
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


def test_open_cell_caveat_names_the_front_door_stamp():
    """matrix.py stays import-light, so its open-cell caveat carries the stamp
    as prose: pin it to the front door's constant and to the rendered doc so
    the three cannot drift (issue #142)."""
    from rvt.frontdoor import intent as FI
    assert FI.OPEN_CELL_STAMP in MX._OPEN_BUG
    assert "issue #16" in FI.OPEN_CELL_STAMP and "genesis-audit.md #48" in FI.OPEN_CELL_STAMP
    with open(MATRIX_DOC, encoding="utf-8") as fh:
        assert FI.OPEN_CELL_STAMP in fh.read()


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


@pytest.mark.parametrize("output", ["rvt", "rfa"])
def test_unknown_famspec_kind_is_one_clear_line(output, tmp_path):
    res = R.route({"rfa": {"kind": "switchboard"}}, output, out=str(tmp_path / "o"))
    assert res.ok is False
    assert "UNSUPPORTED-FAMSPEC-KIND (switchboard)" in res.status
    assert "spec/famspec.schema.json" in res.line and "panelboard" in res.line
    assert res.files == {} and not any("Traceback" in e for e in res.errors)


# ===========================================================================
# 2b. the famspec INPUT CONTRACT (issue #162): spec/famspec.schema.json +
#     spec/examples/famspec-*.json, validated stdlib-only (no jsonschema),
#     every catalog kind through rfa -> rfa and rfa -> rvt on a FRESH CLONE
# ===========================================================================

from rvt.frontdoor import famspec as FS     # noqa: E402  (stdlib-light: json/os/re)

FAMSPEC_SCHEMA = os.path.join(ROOT, "spec", "famspec.schema.json")
FAMSPEC_EXAMPLES = {k: os.path.join(ROOT, "spec", "examples", f"famspec-{k}.json")
                    for k in FS.CATALOG_KINDS}


def _famspec_schema():
    with open(FAMSPEC_SCHEMA, encoding="utf-8") as fh:
        return json.load(fh)


def test_famspec_schema_is_draft07_and_covers_every_kind():
    sch = _famspec_schema()
    assert sch["$schema"].startswith("http://json-schema.org/draft-07/schema")
    assert sch["properties"]["kind"]["enum"] == list(FS.KINDS)
    assert set(sch["definitions"]) >= set(FS.KINDS)
    # the DONE names router._FAMSPEC_KINDS: it IS the contract's kind list
    assert R._FAMSPEC_KINDS is FS.KINDS == ("panelboard", "transformer", "luminaire", "downlight")
    assert os.path.samefile(FS.schema_path(), FAMSPEC_SCHEMA)


@pytest.mark.parametrize("kind", ["panelboard", "transformer", "luminaire"])
def test_famspec_schema_mirrors_the_constructor_kwargs(kind):
    """Per-kind fields == make_<kind>'s keyword arguments (minus start_id,
    plus the route field target_version; luminaire's own `kind` is `fixture`)."""
    import inspect
    from rvt.famgen import factory as F
    sch = _famspec_schema()
    fields = set(sch["definitions"][kind]["properties"]) - {"kind", "target_version"}
    if kind == "luminaire":
        fields = (fields - {"fixture"}) | {"kind"}
    params = set(inspect.signature(getattr(F, f"make_{kind}")).parameters) - {"start_id"}
    assert fields == params, (fields ^ params)


@pytest.mark.parametrize("kind", sorted(FAMSPEC_EXAMPLES))
def test_famspec_examples_validate_against_the_schema(kind):
    spec = json.load(open(FAMSPEC_EXAMPLES[kind], encoding="utf-8"))
    assert spec["kind"] == kind
    assert FS.validate(spec) == []
    k, kw, ropts = FS.normalise(spec)
    assert k == kind and ropts == {}
    # luminaire's `fixture` becomes make_luminaire's own `kind`; no other kwarg is `kind`
    assert ("kind" in kw) is (kind == "luminaire")


@pytest.mark.parametrize("bad,needle,status", [
    ({"kind": "panelboard", "mains": 225}, "unknown field 'mains'", "INVALID-FAMSPEC"),
    ({"kind": "panelboard", "mains_a": "big"}, "expected number", "INVALID-FAMSPEC"),
    ({"kind": "transformer", "kva": -5}, "must be > 0", "INVALID-FAMSPEC"),
    ({"kind": "panelboard", "mounting": "ceiling"}, "not one of ['surface', 'flush']", "INVALID-FAMSPEC"),
    ({"kind": "panelboard", "target_version": "2025"}, "integer Revit year", "INVALID-FAMSPEC"),
    ({"kind": "luminaire", "types": []}, "fewer than 1 items", "INVALID-FAMSPEC"),
    ({"kind": "downlight", "detail": "sketchy"}, "not one of ['standard', 'envelope']", "INVALID-FAMSPEC"),
    ({"kinds": "panelboard"}, "is not one of", "UNSUPPORTED-FAMSPEC-KIND (unset)"),
])
def test_invalid_famspec_is_named_by_the_stdlib_validator(bad, needle, status, tmp_path):
    """No jsonschema dependency: rvt.frontdoor.famspec.check_schema covers the
    draft-07 subset the contract uses, and the router turns a violation into
    INVALID-FAMSPEC + THE clear line naming the field -- never a TypeError
    out of the constructor."""
    probs = FS.validate(bad)
    assert probs and any(needle in p for p in probs), probs
    res = R.route({"rfa": bad}, "rfa", out=str(tmp_path / "o"))
    assert res.ok is False and res.files == {} and res.status == status
    assert needle in res.line and "spec/famspec.schema.json" in res.line


def test_famspec_validator_accepts_the_rich_shapes():
    rich = {"kind": "panelboard", "vendor": "eaton", "mains_a": 225, "voltage": "208Y/120",
            "types": [225, "400A", {"mains_a": 600, "type_name": "600A"}],
            "target_version": 2025, "shared_params": "default", "solid": True}
    assert FS.validate(rich) == []
    kind, kw, ropts = FS.normalise(rich)
    assert ropts == {"target_version": 2025} and "target_version" not in kw
    assert os.path.isfile(kw["shared_params"])                  # 'default' -> OUR file
    assert FS.validate({"kind": "transformer", "primary_v": 480, "secondary_v": "208Y/120"}) == []


def test_rfa_path_alone_with_rfa_output_is_the_clear_line(tmp_path):
    p = tmp_path / "some.rfa"
    p.write_bytes(b"x")
    res = R.route({"rfa": str(p)}, "rfa", out=str(tmp_path / "o"))
    assert res.ok is False and res.files == {}
    assert "UNSUPPORTED-INPUT-FORM" in res.status
    assert "prompt+rfa -> rfa" in res.line and "rfa -> rvt" in res.line


@needs_catalog
@pytest.mark.parametrize("kind", sorted(FAMSPEC_EXAMPLES))
def test_e2e_famspec_to_rfa_every_catalog_kind(kind, tmp_path):
    """THE DONE of issue #162, cell rfa -> rfa: each worked famspec delivers a
    family-mode-VALID (0 errors), provenance-clean .rfa + report + route
    manifest, stamped PROOF-ONLY (rule 1: a label, delivered regardless)."""
    from rvt.validate import validate_file
    from rvt.famgen import factory as F
    res = R.route({"rfa": FAMSPEC_EXAMPLES[kind]}, "rfa", out=str(tmp_path / "o"))
    assert res.ok, res.errors + [res.status, res.line]
    assert res.route == "rfa_generate" and res.status.startswith("OK"), res.status
    assert [s["stage"] for s in res.steps] == ["famspec->rfa", "rfa-emit"]
    rfa = res.files["rfa"]
    assert os.path.isfile(rfa) and rfa.endswith(".rfa")
    rep = json.load(open(res.files["rfa_report"]))
    assert rep["validate"]["family_mode"]["verdict"] == "VALID"
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    assert rep["provenance"]["ok"] is True
    assert rep["family"]["kind"] == kind and rep["family"]["elements"] >= 30
    # the independent gates the DONE names: rvt_validate --family, make_family provenance
    assert len(validate_file(rfa, family=True).errors) == 0
    assert F.provenance_scan(rfa)["ok"] is True
    assert any(s.startswith("PROOF-ONLY") for s in res.stamps)
    assert "VALID 0 errors" in res.status and "provenance ok=True" in res.status
    man = json.load(open(res.manifest_paths["route.json"]))
    assert man["cell"]["status"] == "works" and man["files"]["rfa"]
    assert res.target_version["status"] == "unspecified" and res.releases["rfa"] == 2026


@needs_catalog
@needs_pin
@pytest.mark.parametrize("kind", sorted(FAMSPEC_EXAMPLES))
def test_e2e_famspec_loaded_onto_the_pinned_base_every_catalog_kind(kind, tmp_path):
    """Cell rfa -> rvt, famspec lane: the family is generated (the .rfa rides
    along) and LOADED four-registry onto the pinned certified base -- project
    validator 0 errors, census coherent, no instance placed, PROOF-ONLY
    stamped and no 'loads in Revit' claim anywhere in the status."""
    res = R.route({"rfa": FAMSPEC_EXAMPLES[kind]}, "rvt", out=str(tmp_path / "o"))
    assert res.ok, res.errors + [res.status, res.line]
    assert res.route == "rfa_load"
    assert [s["stage"] for s in res.steps] == ["famspec->rfa", "rfa-emit", "rfa-load"]
    assert os.path.isfile(res.files["rfa"]) and os.path.isfile(res.files["loaded_rvt"])
    rep = json.load(open(res.files["load_report"]))
    assert rep["ok"] is True
    assert rep["validate_project_mode"]["verdict"] == "VALID"
    assert rep["validate_project_mode"]["n_errors"] == 0
    reg = (rep.get("verify") or {}).get("registries") or {}
    assert reg.get("coherent") is True and reg.get("ours_in_all_four") is True
    assert _validator_errors(res.files["loaded_rvt"]) == 0
    assert "project validates 0 errors" in res.status and "Revit" not in res.status
    assert any(s.startswith("PROOF-ONLY") for s in res.stamps)
    assert any("no instance is placed" in c for c in res.caveats)


@needs_catalog
def test_famspec_catalog_refusal_is_by_name_not_a_traceback(tmp_path):
    res = R.route({"rfa": {"kind": "panelboard", "mains_a": 5000}}, "rfa", out=str(tmp_path / "o"))
    assert res.ok is False and res.files == {}
    assert res.status.startswith("FAILED (famspec->rfa")
    assert "REFUSED BY NAME" in res.line and "5000" in res.line
    assert not any("Traceback" in e for e in res.errors)


@needs_catalog
def test_famspec_target_version_field_and_flag(tmp_path):
    """'target_version' in the famspec == --target-version (the flag wins):
    2025 emits AS 2025; an uncertified year delivers native + THE line, and
    the line does not promise an IFC a family request cannot have."""
    r25 = R.route({"rfa": {"kind": "transformer", "kva": 45, "target_version": 2025}}, "rfa",
                  out=str(tmp_path / "a"))
    assert r25.ok, r25.errors + [r25.status]
    assert r25.releases["rfa"] == 2025 and r25.target_version["status"] == "match"
    assert any("taken from the famspec" in c for c in r25.caveats)
    flag = R.route({"rfa": {"kind": "transformer", "kva": 45, "target_version": 2025}}, "rfa",
                   out=str(tmp_path / "b"), target_version=2026)
    assert flag.ok and flag.releases["rfa"] == 2026
    r23 = R.route({"rfa": FAMSPEC_EXAMPLES["luminaire"]}, "rfa", out=str(tmp_path / "c"),
                  target_version=2023)
    assert r23.ok and os.path.isfile(r23.files["rfa"])            # rule 1: delivered
    assert r23.target_version["status"] == "fallback" and r23.releases["rfa"] == 2026
    line = r23.target_version["line"]
    assert "cannot open it" in line and "IFC alongside" not in line and "no IFC rides" in line


@needs_catalog
def test_cli_run_json_famspec_is_one_document(tmp_path, capsys):
    """#313/#188's contract holds on the new cell: `route.py run --rfa FAMSPEC
    --output rfa --json` prints exactly ONE JSON document."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_route_cli2", os.path.join(ROOT, "tools", "route.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    rc = cli.main(["run", "--output", "rfa", "--rfa", FAMSPEC_EXAMPLES["panelboard"],
                   "--out", str(tmp_path / "o"), "--json"])
    out = capsys.readouterr().out
    doc = json.loads(out)
    assert rc == 0 and doc["ok"] and doc["route"] == "rfa_generate", out[-1500:]
    assert os.path.isfile(doc["files"]["rfa"]) and "route.log" in doc["manifest"]


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


@needs_ifc
@pytest.mark.skipif(not os.path.exists(TINY_SPEC), reason="spec example absent")
def test_e2e_spec_to_ifc(tmp_path):
    res = R.route({"spec": TINY_SPEC}, "ifc", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert os.path.isfile(res.files["ifc"])
    head = open(res.files["ifc"], "rb").read(64)
    assert head.startswith(b"ISO-10303-21")


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
    assert any("generated-family INSTANCES" in s for s in res.stamps), \
        "the open-cell stamp must ride the combined file (instances placed on the composed base)"


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
    # reloading into the project it came from: its ids no longer clear THAT
    # host's watermark, so the id-remap lane re-numbers it above (issue #99)
    # -- a second copy of the family lands as a new content document
    back = R.route({"rfa": rfa, "rvt": built_room["rvt"]}, "rvt", out=str(tmp_path / "b"))
    assert back.ok, back.errors + [back.status, back.line]
    assert [s["stage"] for s in back.steps][-1] == "rfa-born-load"
    assert _validator_errors(back.files["loaded_rvt"]) == 0


@needs_catalog
@needs_pin
def test_standalone_born_rfa_loads_onto_the_pinned_base(tmp_path):
    """Our own .rfa deliverables are standalone-born (ids from 1000): the
    rfa -> rvt cell LOADS them through the schema-typed id remap +
    rvt.famload (the certified T2a mechanism, product-wired in
    rvt.convert.rfa_load -- issue #99): project validator 0 errors, the
    caveat names the mechanism's certification and this artifact's lack of
    it (never 'loads in Revit')."""
    gen = R.route({"prompt": PANEL_PROMPT}, "rfa", out=str(tmp_path / "g"))
    assert gen.ok, gen.errors
    rfa = next(p for k, p in gen.files.items() if k.startswith("rfa:"))
    res = R.route({"rfa": rfa}, "rvt", out=str(tmp_path / "o"))
    assert res.ok is True, res.errors + [res.status, res.line]
    assert [s["stage"] for s in res.steps] == ["rfa-classify", "rfa-born-load"]
    assert "VALID 0 errors" in res.status and _validator_errors(res.files["loaded_rvt"]) == 0
    reg = json.load(open(res.files["load_report"]))["proofs"]["verify_written"]["registries"]
    assert reg["coherent"] is True and reg["ours_in_all_four"] is True
    # the lane-level contract (caveat wording, rebase census, 2025 host, refusals)
    # is pinned by tests/test_rfa_load.py, which runs in the CI shard


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


def test_e2e_merge_ifc_into_project(built_room, tmp_path):
    """ifc+rvt: an IFC of a second small room MERGED into the built room at
    the auto-disjoint offset -- delivered, VALID 0 errors, release preserved,
    the open-cell stamp riding because an INSTANCE of our generated family was
    placed on a composed-base project (walls + loaded families alone would not)."""
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
    assert any("generated-family INSTANCES" in s for s in res.stamps), res.stamps


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

@needs_ifc
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
# 4b. build degradations ride into the route's caveats (issue #347): a
#     `route run ... --json` consumer sees WHY a build degraded (the IFC
#     census line, 'W-1 NOT built', 'validation SKIPPED', ...) without opening
#     MANIFEST.md.  Labels after delivery: ok / status / exit code untouched.
# ===========================================================================

CENSUS_IFC = os.path.join(ROOT, "tests", "ifc_conformance", "j_census_space_unreadable_body.ifc")


def _fake_author(monkeypatch, degradations):
    """Swap rvt.frontdoor.author for a stand-in: no genesis build, just an
    AuthorResult whose manifest carries the given build.degradations."""
    import rvt.frontdoor as FD

    def fake(*, out, **_kw):
        os.makedirs(out, exist_ok=True)
        return FD.AuthorResult(
            route="prompt", ok=True, status="PROOF-ONLY (fake)", out_dir=out,
            manifest={"build": {"degradations": list(degradations)},
                      "target_version": {"requested": None, "status": "default",
                                         "output_release": 2026, "line": ""}},
            manifest_paths={"json": os.path.join(out, "manifest.json"),
                            "md": os.path.join(out, "MANIFEST.md")})
    monkeypatch.setattr(FD, "author", fake)


def test_build_degradations_become_prefixed_caveats(tmp_path, monkeypatch):
    lines = ["W-1 (wall): NOT built -- family plan unmapped",
             "IFC census: 1 of 7 products dropped (IfcSpace×1); delivery unchanged",
             "W-1 (wall): NOT built -- family plan unmapped"]           # a duplicate
    _fake_author(monkeypatch, lines)
    res = R.route({"prompt": SMALL_ROOM_PROMPT}, "rvt", out=str(tmp_path / "o"), quiet=True)
    assert res.ok and res.status == "PROOF-ONLY (fake)"                # labels, not refusals
    build = [c for c in res.caveats if c.startswith(R.BUILD_CAVEAT_PREFIX)]
    assert build == [R.BUILD_CAVEAT_PREFIX + lines[0], R.BUILD_CAVEAT_PREFIX + lines[1]]
    cell_caveats = list(MX.cell_for(["prompt"], "rvt").caveats)
    assert res.caveats[:len(cell_caveats)] == cell_caveats                # order: cell first
    man = json.load(open(res.manifest_paths["route.json"]))
    assert man["caveats"] == res.caveats and man["ok"] is True
    md = open(res.manifest_paths["ROUTE.md"]).read()
    assert all(b in md for b in build)
    assert res.as_json()["caveats"] == res.caveats


def test_many_build_degradations_are_capped_with_a_pointer(tmp_path, monkeypatch):
    lines = [f"LP-{i} (panelboard): NOT built -- reason {i}" for i in range(R.BUILD_CAVEAT_CAP + 4)]
    _fake_author(monkeypatch, lines)
    res = R.route({"prompt": SMALL_ROOM_PROMPT}, "rvt", out=str(tmp_path / "o"), quiet=True)
    build = [c for c in res.caveats if c.startswith(R.BUILD_CAVEAT_PREFIX)]
    assert len(build) == R.BUILD_CAVEAT_CAP + 1
    assert build[:-1] == [R.BUILD_CAVEAT_PREFIX + s for s in lines[:R.BUILD_CAVEAT_CAP]]
    assert "+4 more" in build[-1] and "MANIFEST.md" in build[-1]


def test_no_degradation_means_no_build_caveat(tmp_path, monkeypatch):
    _fake_author(monkeypatch, [])
    res = R.route({"prompt": SMALL_ROOM_PROMPT}, "rvt", out=str(tmp_path / "o"), quiet=True)
    assert res.caveats == list(MX.cell_for(["prompt"], "rvt").caveats)


@needs_pin
@needs_catalog
def test_e2e_build_degradations_ride_the_route_caveats(tmp_path):
    """ONE real build that degrades deterministically on a fresh clone: the
    #153 census fixture (an IfcSpace dropped, one body unreadable) routed with
    --no-validate -> both the 'IFC census:' line and 'validation SKIPPED' sit
    in build.degradations and must reach res.caveats / route.json / ROUTE.md."""
    if not os.path.exists(CENSUS_IFC):
        pytest.skip("census IFC fixture absent")
    res = R.route({"ifc": CENSUS_IFC}, "rvt", out=str(tmp_path / "o"),
                  no_validate=True, no_handoff=True, quiet=True)
    assert res.ok, res.errors
    degr = json.load(open(res.manifest_paths["author:json"]))["build"]["degradations"]
    assert any("validation SKIPPED" in d for d in degr), degr
    for d in degr:
        assert R.BUILD_CAVEAT_PREFIX + d in res.caveats
    census = [c for c in res.caveats if c.startswith(R.BUILD_CAVEAT_PREFIX + "IFC census:")]
    assert len(census) == 1, res.caveats
    assert "IfcSpace" in census[0]
    man = json.load(open(res.manifest_paths["route.json"]))
    assert man["caveats"] == res.caveats
    md = open(res.manifest_paths["ROUTE.md"]).read()
    assert "IFC census:" in md


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


@needs_catalog
def test_cli_run_json_stdout_is_one_document(tmp_path, capsys):
    """``route.py run ... --json`` writes exactly ONE JSON document to stdout;
    the stages' progress (``[ifc_intent] F ...``) lands in <out>/route.log,
    named in the result's manifest block (issue #188)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_route_cli", os.path.join(ROOT, "tools", "route.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)                 # in-process: capsys sees main()'s stdout
    rc = cli.main(["run", "--output", "rfa", "--prompt", PANEL_PROMPT,
                   "--out", str(tmp_path / "o"), "--json"])
    out = capsys.readouterr().out
    doc = json.loads(out)                        # raises on any non-JSON prefix
    assert rc == 0 and isinstance(doc, dict) and doc["ok"], out[-2000:]
    assert "[ifc_intent]" not in out
    log_p = doc["manifest"]["route.log"]
    assert os.path.isfile(log_p) and "[ifc_intent] F" in open(log_p).read()


@needs_catalog
def test_route_without_quiet_still_prints_progress(tmp_path, capsys):
    """The human (non --json) path is untouched: progress stays live on stdout
    and no route.log is written."""
    res = R.route({"prompt": PANEL_PROMPT}, "rfa", out=str(tmp_path / "o"))
    assert res.ok, res.errors
    assert "[ifc_intent] F" in capsys.readouterr().out
    assert "route.log" not in res.manifest_paths


def test_quiet_route_into_readonly_dir_still_runs_its_stage(tmp_path, capsys, monkeypatch):
    """An unwritable out_dir must degrade ``quiet`` to "unlogged" (in-memory
    sink + a note in ``errors``), not to "route crashed" with no stage run --
    the --json path is never worse than the human path (#330, from #313)."""
    ran = []

    def fake_stage(res, inputs, out_dir, opts):
        print("[fake] progress line")
        ran.append(out_dir)
        res.ok, res.status = True, "OK (fake)"

    monkeypatch.setitem(R._IMPLS, "prompt_to_rfa", fake_stage)
    ro = tmp_path / "ro"
    ro.mkdir()
    out = str(ro)
    ro.chmod(0o555)
    try:
        if os.access(out, os.W_OK):
            pytest.skip("chmod 0555 did not make the dir read-only (running as root?)")
        res = R.route({"prompt": PANEL_PROMPT}, "rfa", out=out, quiet=True)
    finally:
        ro.chmod(0o755)
    assert ran == [out], res.errors
    assert res.ok and res.status == "OK (fake)", res.errors
    assert "route.log" not in res.manifest_paths
    assert any("route.log not writable" in e for e in res.errors), res.errors
    assert not any("route crashed" in e for e in res.errors), res.errors
    assert "[fake]" not in capsys.readouterr().out          # still kept off stdout


@needs_pin
@needs_catalog
def test_frontdoor_json_stdout_stays_one_document(tmp_path):
    """Regression guard for the other front door: ``frontdoor.py author --json``
    already keeps stage progress off stdout (build quiet capture) -- keep it so."""
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "frontdoor.py"), "author",
                        "--prompt", SMALL_ROOM_PROMPT, "--out", str(tmp_path / "o"),
                        "--json"], capture_output=True, text=True, cwd=ROOT)
    assert p.returncode in (0, 3), p.stderr[-2000:]
    doc = json.loads(p.stdout)
    assert isinstance(doc, dict) and doc["route"] == "prompt"
    assert "[ifc_intent]" not in p.stdout


def test_cli_unsupported_exit_code(tmp_path):
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "run",
                        "--output", "ifc", "--rfa", '{"kind": "downlight"}',
                        "--out", str(tmp_path / "o")],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 4, p.stdout + p.stderr
    assert "Closest supported route" in p.stdout


def test_cli_explain_missing_cell():
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "explain",
                        "--output", "ifc", "--inputs", "rfa"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 4
    assert "MISSING" in p.stdout and "prompt -> ifc" in p.stdout


def test_cli_explain_famspec_cell_is_zero():
    """rfa -> rfa flipped to WORKS (issue #162): explain names the route and
    the written contract."""
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "explain",
                        "--output", "rfa", "--inputs", "rfa"],
                       capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout
    assert "works via rfa_generate (famspec->rfa)" in p.stdout
    assert "spec/famspec.schema.json" in p.stdout


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
