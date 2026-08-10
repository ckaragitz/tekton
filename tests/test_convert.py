"""tests/test_convert.py -- the EXPORT / EXTRACT converters (convert-a).

Three routes, each proven end-to-end on OUR OWN acceptance-test output
(zero-donor lineage), plus the honest-refusal / stamping behaviour:

* RVT -> IFC   round trip through rvt.ifc.intent (tags / kinds / walls /
               positions survive);
* RVT -> RFA   family-mode validator 0 errors on the extracted panel + the
               FULL CYCLE (re-load onto a fresh certified base);
* RFA -> RFA   structured ops (rename type / set params) re-read back.

Foreign-file behaviour (rme sample) is a SLOW dev test: stamps + honest
partial cells (skip with RVT_SKIP_LARGE=1).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

ACCEPT_RVT = os.path.join(ROOT, "experiments", "frontdoor",
                          "prompt-electrical-room", "electrical_room_prompt.rvt")
EATON_RFA = os.path.join(ROOT, "experiments", "frontdoor",
                         "prompt-electrical-room", "families",
                         "dp1_eaton_prl2x_400a_42sp_480y_277.rfa")
GENESIS_BASE = os.path.join(ROOT, "experiments", "genesis", "subst_k4",
                            "compose", "G_ABPD.rvt")
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

needs_accept = pytest.mark.skipif(not os.path.isfile(ACCEPT_RVT),
                                  reason="acceptance-test output absent "
                                         "(regenerate via the frontdoor)")
needs_eaton = pytest.mark.skipif(not os.path.isfile(EATON_RFA),
                                 reason="generated Eaton .rfa absent")
needs_base = pytest.mark.skipif(not os.path.isfile(GENESIS_BASE),
                                reason="pinned genesis base absent")
needs_rme = pytest.mark.skipif(not os.path.isfile(RME),
                               reason="rme research sample absent")
skip_large = pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1",
                                reason="RVT_SKIP_LARGE=1")
# (no ifcopenshell gate: rvt->ifc is our own writer and its round trip READS via
# the bundled steplite shim when no wheel is installed -- #130 / #367)


# ===========================================================================
# route 1: RVT -> IFC
# ===========================================================================

@needs_accept
def test_rvt_to_ifc_roundtrip_survives_on_own_output(tmp_path):
    """The acceptance-test .rvt is a SHARED, REGENERABLE artifact -- sibling
    streams rebuild it with prompt variants (7-board room, 4-board room with
    a transformer, ...).  The test therefore SELF-CALIBRATES: whatever the
    room currently contains must survive the round trip IN FULL."""
    from rvt.convert.rvt_to_ifc import convert_rvt_to_ifc
    out = str(tmp_path / "room.ifc")
    rec = convert_rvt_to_ifc(ACCEPT_RVT, out, out_dir=str(tmp_path))
    # deliverable rule: the IFC and its manifest exist
    assert os.path.isfile(out)
    assert rec["deliverables"]["ifc"]["bytes"] > 1000
    assert os.path.isfile(str(tmp_path / "room.manifest.json"))
    assert os.path.isfile(str(tmp_path / "room.MANIFEST.md"))
    # our own lineage: no foreign stamp
    assert not rec["input"]["provenance"]["foreign"]
    assert rec["stamps"] == []
    # the room build always carries walls + boards
    cells = rec["extraction"]["cells"]
    n_eq, n_walls = cells["equipment"]["count"], cells["walls"]["count"]
    assert n_walls >= 4 and n_eq >= 1
    tags = [e["tag"] for e in rec["equipment"]]
    assert len(tags) == len(set(tags))                    # unique join keys
    # THE ACCEPTANCE: FULL survival of whatever is there
    rt = rec["roundtrip"]
    assert rt["ran"] is True
    assert rt["all_survived"] is True, rt
    assert rt["equipment_survived"] == f"{n_eq}/{n_eq}"
    assert rt["walls_matched"] == f"{n_walls}/{n_walls}"
    # kind labels agree in-RVT vs re-resolved, and positions survive to mm
    assert all(r["kind_ok"] for r in rt["equipment"])
    assert all(max(r["dpos_m"]) <= 0.005 for r in rt["equipment"])
    kinds = {r["tag"]: r["kind_out"] for r in rt["equipment"]}
    if "MSB" in kinds:
        assert kinds["MSB"] == "switchboard"
    if "DP-1" in kinds:
        assert kinds["DP-1"] == "distribution_panelboard"


@needs_accept
def test_rvt_to_ifc_extraction_reads_contract_values():
    from rvt.convert.rvt_to_ifc import extract_intent
    model = extract_intent(ACCEPT_RVT)
    dp1 = model.by_tag("DP-1")
    if dp1 is None:                       # regenerable artifact: variant w/o DP-1
        pytest.skip("current acceptance build carries no DP-1 board "
                    f"(tags: {[e.tag for e in model.equipment]})")
    assert dp1.kind == "distribution_panelboard"
    con = dp1.contract
    assert con["PanelName"] == "DP-1"
    assert float(con["BusRating"]) == 400.0
    assert con["MainsType"] == "MCB"
    assert int(con["NumberOfCircuits"]) == 42
    assert con["Manufacturer"] == "Eaton"
    # voltage folded back to the Y-system string the resolver parses
    assert str(con["Voltage"]).startswith("480Y/277")
    # dims from the family params, converted ft -> m
    assert abs(dp1.dims_m["w"] - 0.508) < 1e-3
    # frame: wall panel emitted upright, front = family +Z
    assert dp1.frame_kind == "upright"
    # walls carry the type thickness (121 mm) and height (12 ft)
    w = model.room.walls[0]
    assert abs(w.thickness_m - 0.121) < 1e-3
    assert abs(w.height_m - 12 * 0.3048) < 1e-6


@needs_rme
@skip_large
def test_rvt_to_ifc_foreign_is_stamped_and_honest(tmp_path):
    from rvt.convert.rvt_to_ifc import convert_rvt_to_ifc
    out = str(tmp_path / "rme.ifc")
    rec = convert_rvt_to_ifc(RME, out, out_dir=str(tmp_path), roundtrip=False)
    assert os.path.isfile(out)
    assert rec["input"]["provenance"]["foreign"] is True
    joined = " ".join(rec["stamps"])
    assert "FOREIGN DESIGN CONTENT" in joined
    assert "QUARANTINED SOURCE" in joined
    cells = rec["extraction"]["cells"]
    assert cells["equipment"]["count"] >= 20
    # circuits ARE present in the foreign model and become feeder edges
    assert cells["feeders"]["edges_between_equipment"] >= 20
    assert len(rec["feeder_edges"]) >= 20
    # non-equipment circuits are counted, never faked
    assert cells["feeders"]["circuits_total"] > cells["feeders"]["edges_between_equipment"]


# ===========================================================================
# route 2: RVT -> RFA (+ the full cycle)
# ===========================================================================

def _pick_panel_selector(rvt_path: str) -> str:
    """A panelboard family present in the CURRENT (regenerable) acceptance
    build -- prefer DP-1, else any Panelboard, else the first family."""
    from rvt.convert.extract_family import list_families
    rows = list_families(rvt_path)
    assert rows, "acceptance build embeds no family documents"
    for want in ("DP-1", "Panelboard", ""):
        hits = [r for r in rows if want in (r["family_name"] or "")]
        if len(hits) >= 1:
            return hits[0]["family_name"]
    return rows[0]["family_name"]                          # pragma: no cover


@needs_accept
@needs_base
def test_extract_family_panel_validator_zero_errors(tmp_path):
    from rvt.convert.extract_family import extract_family
    sel = _pick_panel_selector(ACCEPT_RVT)
    out = str(tmp_path / "panel.rfa")
    rec = extract_family(ACCEPT_RVT, sel, out, out_dir=str(tmp_path))
    assert os.path.isfile(out)
    g = rec["validation"]
    assert g["family_mode"]["verdict"] == "VALID"
    assert g["family_mode"]["n_errors"] == 0
    assert g["records_decode_clean"] is True
    assert g["self_checks_ok"] is True
    # our own lineage: no foreign stamp
    assert rec["stamps"] == []
    # the unit's records rode verbatim
    assert rec["assembly"]["elements"] > 10
    ver = rec["assembly"]["verify"]
    assert ver["gzip_crc_failures"] == 0 and ver["ecc_mismatch"] == 0
    assert ver["n_units"] == 1


@needs_accept
@needs_base
@skip_large
def test_extract_family_full_cycle_reloads_onto_fresh_base(tmp_path):
    from rvt.convert.extract_family import extract_family, reload_family
    from rvt.famload import four_registry_census
    from rvt.validate import validate_file
    rfa = str(tmp_path / "panel.rfa")
    extract_family(ACCEPT_RVT, _pick_panel_selector(ACCEPT_RVT), rfa,
                   out_dir=str(tmp_path))
    out_rvt = str(tmp_path / "reloaded.rvt")
    rep = reload_family(rfa, GENESIS_BASE, out_rvt)
    assert rep["ok"] is True, rep
    assert os.path.isfile(out_rvt)
    # the loaded project: project validator 0 errors, four registries coherent
    vrep = validate_file(out_rvt)
    assert len(vrep.errors) == 0, [str(e)[:120] for e in vrep.errors[:3]]
    census = four_registry_census(out_rvt)
    assert census["coherent"] is True
    assert census["save_units"] == 2            # base unit 0 + our family unit


@needs_rme
@skip_large
def test_extract_family_refuses_nested_and_labels_foreign(tmp_path):
    from rvt.convert.extract_family import ExtractError, extract_family
    # every rme electrical family embeds nested families: refused BY NAME
    with pytest.raises(ExtractError, match="NESTED"):
        extract_family(RME, "M_Lighting and Appliance Panelboard - 208V MLO",
                       str(tmp_path / "x.rfa"), out_dir=str(tmp_path))
    # a nested-free foreign family extracts, DELIVERS, and carries the
    # foreign stamp + the honest dangling-host-reference label
    rec = extract_family(RME, "M_Level Head - Circle",
                         str(tmp_path / "head.rfa"), out_dir=str(tmp_path))
    assert os.path.isfile(str(tmp_path / "head.rfa"))
    joined = " ".join(rec["stamps"])
    assert "FOREIGN DESIGN CONTENT" in joined
    fm = rec["validation"]["family_mode"]
    if fm["n_errors"]:                          # host-bound references dangle
        assert any("HOST-RESOURCE REPATRIATION" in d
                   for d in rec["degradations"])


# ===========================================================================
# route 3: RFA + ops -> RFA
# ===========================================================================

@needs_eaton
@needs_accept
def test_edit_family_ops_rename_and_set(tmp_path):
    from rvt.convert import modify_family as MF
    from rvt.convert.edit_family import edit_family
    rec = edit_family(EATON_RFA, [
        {"op": "set-param", "param": "BusRating", "value": 225},
        {"op": "set-param", "param": "PanelName", "value": "DP-7"},
        {"op": "rename-type", "name": "225A MCB 42ckt"},
    ], str(tmp_path), stem="edited")
    out = str(tmp_path / "edited.rfa")
    assert os.path.isfile(out)
    g = rec["validation"]["rfa"]
    assert g["family_mode"]["verdict"] == "VALID"
    assert g["family_mode"]["n_errors"] == 0
    assert all(r["ok"] for r in g["reread"])
    assert g["release"]["preserved"] is True
    # independent re-read through the inventory surface
    inv = MF.inventory_family(out)
    vals = {p["caption"]: p["current"] for p in inv.params}
    assert float(vals["BusRating"]) == 225.0
    assert vals["PanelName"] == "DP-7"
    assert inv.type_names == ["225A MCB 42ckt"]


def test_edit_family_ops_schema_is_checked():
    from rvt.convert.edit_family import FamilyOpsError, normalize_ops
    with pytest.raises(FamilyOpsError, match="no ops"):
        normalize_ops([])
    with pytest.raises(FamilyOpsError, match="unknown op"):
        normalize_ops([{"op": "explode"}])
    with pytest.raises(FamilyOpsError, match="'value' is required"):
        normalize_ops([{"op": "set-param", "param": "BusRating"}])
    with pytest.raises(FamilyOpsError, match="'name' is required"):
        normalize_ops([{"op": "rename-type"}])
    norm = normalize_ops([
        {"op": "set_param", "param": "Width", "value": 600, "unit": "mm"},
        {"op": "set-param", "param": "BusRating", "value": 225, "type": "400A"},
        {"op": "rename-type", "old": "A", "name": "B"},
        {"op": "rename-family", "name": "N"},
    ])
    assert norm[0] == {"op": "set-param", "param": "Width", "value": "600 mm"}
    assert norm[1] == {"op": "set-param", "param": "BusRating", "value": "225",
                       "type": "400A"}
    assert norm[2] == {"op": "rename-type", "type": "A", "name": "B"}
    assert norm[3] == {"op": "rename-family", "name": "N"}


def test_edit_family_leaves_nl_vocabulary_to_modify_family():
    """The shared-vocabulary merge point (convert-B's _sibling_vocabulary
    hook) is DELIBERATELY not claimed: landing a parse_family_edit here
    would silently re-route the live prompt+RFA route through an unagreed
    contract.  Recorded in docs/inbox/convert-a.md."""
    from rvt.convert import edit_family as EF
    assert not hasattr(EF, "parse_family_edit")


# ===========================================================================
# shared plumbing
# ===========================================================================

@needs_accept
def test_provenance_detection():
    from rvt.convert.rvt_to_ifc import source_provenance
    own = source_provenance(ACCEPT_RVT)
    assert own["foreign"] is False and own["quarantined"] is False
    if os.path.isfile(RME):
        foreign = source_provenance(RME)
        assert foreign["foreign"] is True and foreign["quarantined"] is True
