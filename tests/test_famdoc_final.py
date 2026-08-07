"""famdoc-final stream tests -- COMBINATION vs FRAME, the round that decides.

Pins the verdict-#38 follow-up machinery: the frame roster (the six famdoc
elements outside every batch-44 content axis, in three groups), the U-probe
axis unions (carried multisets, repoint law, U16's extended donor-ADocument
swap), the F-probe frame swap (field-law dispositions, ownership adoption,
BrowserOrganization imports, donor-block residual zero, donor fields
READ BACK from the emitted probe bytes), H8B's loader-split recipe, the
per-probe blob census + nonce (independently re-derived), probes.json's
decision table, frame_diff.json's fix-spec shape, and -- once staged -- the
two-control batch manifest.

Stream-local only (SUITE-COORDINATION: no full-suite runs from this
stream)::

    .venv/bin/python -m pytest tests/test_famdoc_final.py -q
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "famdoc_final")
ACCT = os.path.join(OUT_DIR, "accounting.json")
PROBES = os.path.join(OUT_DIR, "probes.json")
FRAME_DIFF = os.path.join(OUT_DIR, "frame_diff.json")
ACCEPTANCE = os.path.join(ROOT, "experiments", "acceptance")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")

LADDER = ("U16", "F1", "U12345", "H8B", "U12", "U15", "U25", "F2", "F3", "F4")
U_PROBES = ("U16", "U12345", "U12", "U15", "U25")
F_PROBES = ("F1", "F2", "F3", "F4")

#: elements each union CARRIES onto the donor famdoc (axis multisets:
#: geometry 7 + params 14 + datum 4 + views 8 + connector 2 (+1 param when
#: the params axis is absent))
CARRIED = {"U16": 35, "U12345": 35, "U12": 21, "U15": 10, "U25": 16}
DONOR_N = 417

#: the frame roles and their classes (the roster this whole round is about)
FRAME_CLASSES = {"self_family": "Family", "units": "UnitsElem",
                 "proj_view": "DBViewProject", "proj_viewer": "Viewer",
                 "proj_drawing": "DBDrawing", "proj_viewport": "Viewport"}
DONOR_ROLES = {"self_family": 1410872, "units": 1411008,
               "proj_view": 1410913, "proj_viewer": 1410912,
               "proj_drawing": 1410914, "proj_viewport": 1410915}
DONOR_BROWSER_ORGS = [1411145, 1411146]

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(ACCT) and os.path.isfile(PROBES)),
    reason="famdoc_final artifacts not built (run tools/famdoc_final.py build)")


@pytest.fixture(scope="module")
def acct():
    with open(ACCT) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def probes():
    with open(PROBES) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def fdiff():
    assert os.path.isfile(FRAME_DIFF), "frame_diff.json missing (run diff)"
    with open(FRAME_DIFF) as fh:
        return json.load(fh)


def _base_of(name):
    return G_ABPD if name.startswith("F") else RST


def _units(path, with_data=True):
    """INDEPENDENT raw-scan of every save unit's 0x0f3f footer blob (the
    walker, not the tool's blob_proof)."""
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    out = []
    with open_rvt(path) as f:
        for nm in sorted(s.name for s in f.streams()
                         if s.name.startswith("Partitions/")):
            w = StreamWalker(f.logical(nm), inflate=with_data,
                             keep_data=with_data)
            assert not w.errors, (path, nm, w.errors[:3])
            for u in w.units:
                seg102 = bytearray()
                if with_data:
                    for b in sorted((b for b in
                                     w.blocks[u.first_block:u.first_block + u.n_blocks]
                                     if b.seq == 102), key=lambda b: b.hdr_offset):
                        seg102.extend(b.data or b"")
                out.append({
                    "guid": str(uuid.UUID(bytes_le=u.guid)) if u.guid else None,
                    "blob": bytes(u.footer_blob), "seg102": bytes(seg102)})
    return out


_BASE_GUIDS = {}


def _base_guids(base):
    if base not in _BASE_GUIDS:
        _BASE_GUIDS[base] = {u["guid"] for u in _units(base, with_data=False)}
    return _BASE_GUIDS[base]


# ---------------------------------------------------------------------------
# the frame roster (what this round is about)
# ---------------------------------------------------------------------------

def test_frame_roster_is_the_six_outside_axis_elements(fdiff):
    roster = fdiff["frame_roster"]
    assert len(roster) == 6
    by_role = {r["role"]: r for r in roster}
    assert set(by_role) == set(FRAME_CLASSES)
    for role, cls in FRAME_CLASSES.items():
        assert by_role[role]["class"] == cls
    assert fdiff["donor_roles"] == {k: v for k, v in DONOR_ROLES.items()}
    assert fdiff["donor_browser_org_imports"] == DONOR_BROWSER_ORGS


def test_frame_diff_is_ranked_and_carries_dispositions(fdiff):
    cl = fdiff["checklist"]
    assert [e["role"] for e in cl][0] == "self_family", "deep-walk-first rank"
    ranks = [e["rank"] for e in cl]
    assert ranks == sorted(ranks)
    sf = cl[0]
    disp = sf["swap_disposition_obj"]
    allowed = {"donor", "donor_equal", "kept_ours_membership",
               "kept_ours_identity", "kept_ours_registry_coupled"}
    assert set(disp.values()) <= allowed
    # the honest residue is recorded: kept-ours keys that DIFFER from donor
    assert "untested_by_swap" in sf and len(sf["untested_by_swap"]) > 0
    for k in sf["untested_by_swap"]:
        assert disp[k].startswith("kept_ours")
    # the membership surfaces must never be donor-swapped
    for k in ("m_familyIds", "m_familyParams", "m_pFamilyTypes",
              "m_cellList", "m_deletableElements", "m_oFamDimConstrMgr",
              "m_refs"):
        assert disp[k] == "kept_ours_membership", k
    # identity + registry counters stay ours
    assert disp["m_categoryId"] == "kept_ours_identity"
    assert disp["m_partType"] == "kept_ours_identity"
    assert disp["m_nextAbsorbedIndex"] == "kept_ours_registry_coupled"
    # the frame fields the swap DOES test include the measured suspects
    for k in ("m_seekItemId", "m_omniClassCode", "m_appVersionAtLoad",
              "m_bIsSavable", "m_shouldStayParametric", "m_isWorkPlaneBased"):
        assert disp[k] == "donor", k
    # the ownership frame delta (lives in the ElemTable row, not the bytes)
    owner = {e["role"]: e["ownership"] for e in cl}
    assert owner["units"]["differs"] and owner["units"]["A_owner"] == "self_family"
    assert owner["proj_view"]["differs"] and \
        owner["proj_view"]["A_owner"] == "self_family"
    assert not owner["proj_viewport"]["differs"]


# ---------------------------------------------------------------------------
# every emitted probe: blob census + nonce, independently re-derived
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", LADDER)
def test_probe_every_unit_carries_64B_blob_and_added_nonce_matches(name, acct):
    from rvt.famgen.famdoc_adoc import build_footer
    info = acct["built"][name]
    path = os.path.join(ROOT, info["file"])
    assert os.path.isfile(path)
    units = _units(path)
    assert all(len(u["blob"]) == 64 for u in units), \
        f"{name}: a unit without a 64-byte blob (the batch-37 voider)"
    added = [u for u in units if u["guid"] not in _base_guids(_base_of(name))]
    assert len(added) == 1, f"{name}: expected exactly ONE added unit"
    u = added[0]
    assert u["blob"] == build_footer(guid=u["guid"], payload=u["seg102"]), \
        f"{name}: added unit's blob is not OUR deterministic nonce"


@pytest.mark.parametrize("name", LADDER)
def test_gates_green(name, acct):
    g = acct["gates"][name]
    assert g["gates_ok"] is True, g
    assert g["validator_errors"] == 0 and g["validator_unexpected"] == 0
    assert g["four_registry_coherent"] is True
    assert g["load_hop_units_added"] == 1
    assert g["instance_hop_units_added"] == 0
    assert g["survivor_law_ok"] and g["identity"] == "PASS"
    assert g["blob_all_units_64B"] and g["blob_added_nonce_verified"]
    assert g["famdoc_refs_unresolved_anywhere"] == 0


# ---------------------------------------------------------------------------
# U-probes: the union law
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", U_PROBES)
def test_union_carried_counts_and_element_totals(name, acct):
    info = acct["built"][name]
    assert info["union"]["n_carried"] == CARRIED[name]
    assert info["n_elements"] == DONOR_N + CARRIED[name]


def test_union_repoint_law(acct):
    """An anchor is repointed to the donor's ONLY when the axis that carries
    it is not in the union: U16/U12345 carry everything (self-family repoint
    only); U12/U15 lack datum (level repointed); U25 lacks geometry
    (extrusion repointed for the connector's face ref)."""
    n_repoints = {n: len(acct["built"][n]["union"]["repointed"])
                  for n in U_PROBES}
    assert n_repoints == {"U16": 1, "U12345": 1, "U12": 2, "U15": 2, "U25": 2}


def test_u16_adoc_swap_extended_for_the_carried_roster(acct):
    info = acct["built"]["U16"]
    sw = info["adoc_swap"]
    assert sw["appinfo_populated"] == 131, "the donor inline ADocument pin"
    assert len(sw["elem_rows_appended"]) == CARRIED["U16"]
    assert sw["elem_rows_total"] == info["n_elements"]
    assert len(sw["history_guids_rekeyed_from"]) == 4
    last = sw["identifier_source_last"]
    assert last["after"] >= max(sw["elem_rows_appended"])


def test_u12345_carries_our_authored_adocument(acct):
    """U12345 is the B0-minus-frame shape: NO donor-ADocument swap."""
    assert "adoc_swap" not in acct["built"]["U12345"]
    assert "adoc_swap" in acct["built"]["U16"]


def test_union_registration_absorbed_into_the_donor_registry(acct):
    reg = acct["built"]["U16"]["union"]["registration"]
    idx = list(reg["membership"]["absorbed_indices"].values())
    assert len(idx) == CARRIED["U16"]
    assert min(idx) == 3165, "indices continue the donor's absorbed counter"
    assert reg["params"]["rows_appended"] > 14, "H2 convention incl. built-ins"
    assert reg["params_with_negatives"] is True
    assert acct["built"]["U15"]["union"]["registration"][
        "params_with_negatives"] is False, "H5 convention without axis 2"


# ---------------------------------------------------------------------------
# F-probes: the frame swap law
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,roles", [
    ("F1", {"self_family", "units", "proj_view", "proj_viewer",
            "proj_drawing", "proj_viewport"}),
    ("F2", {"self_family"}),
    ("F3", {"units"}),
    ("F4", {"proj_view", "proj_viewer", "proj_drawing", "proj_viewport"}),
])
def test_f_probe_swaps_exactly_its_groups(name, roles, acct):
    sw = acct["built"][name]["frame_swap"]
    assert {s["role"] for s in sw["swapped"]} == roles
    assert sw["donor_block_residual"] == 0
    n_imports = 2 if name in ("F1", "F4") else 0
    assert len(sw["imports"]) == n_imports
    if n_imports:
        assert [i["donor_id"] for i in sw["imports"]] == DONOR_BROWSER_ORGS
        reg = sw["import_registration"]
        assert sorted(reg["absorbed_indices"].values()) == [40, 41]
        assert reg["next_absorbed_index"] == 42


def test_f_swap_adopts_the_donor_ownership_topology(acct):
    """Measured frame delta: the donor's UnitsElem and DBViewProject are
    OWNED by the self-Family; ours were top-level.  The swap adopts it."""
    sw = acct["built"]["F1"]["frame_swap"]
    by_role = {s["role"]: s for s in sw["swapped"]}
    assert by_role["units"]["owner_changed"] is True
    assert by_role["proj_view"]["owner_changed"] is True
    sf_id = next(s["our_id"] for s in sw["swapped"] if s["role"] == "self_family")
    assert by_role["units"]["owner_adopted"] == sf_id
    assert by_role["proj_view"]["owner_adopted"] == sf_id
    for role in ("proj_viewer", "proj_drawing", "proj_viewport"):
        assert by_role[role]["owner_changed"] is False


def test_f1_sf_disposition_matches_the_field_law(acct, fdiff):
    got = acct["built"]["F1"]["frame_swap"]["self_family_disposition"]["obj"]
    want = fdiff["checklist"][0]["swap_disposition_obj"]
    assert got == want, "the build's disposition must equal the fix spec's"


def test_f1_donor_frame_fields_read_back_from_the_emitted_bytes(acct):
    """The binding proof the swap survived the loader: decode F1's embedded
    unit from the probe FILE and find the donor's frame fields on the
    self-Family (seekItemId / appVersion) with identity kept ours, our 40
    members + 2 BrowserOrganization imports registered."""
    from rvt.families import FamilyIndex
    info = acct["built"]["F1"]
    path = os.path.join(ROOT, info["file"])
    guid = info["load"]["content_guid"]
    idx = FamilyIndex(path)
    unit = next(i for i, u in enumerate(idx.units) if str(u.guid) == guid)
    recs = idx.unit_records(unit)
    sf_id, sf = None, None
    n_browser = 0
    for eid in recs.get(102, {}):
        cname = idx.class_name(recs[102][eid].class_id)
        if cname == "BrowserOrganization":
            n_browser += 1
        if cname == "Family":
            v = idx.value(unit, eid, 102)
            if isinstance(v, dict) and v.get("m_famId") in (-1, None):
                sf_id, sf = eid, v
    assert sf is not None, "no self-Family in F1's embedded unit"
    assert n_browser == 2, "the BrowserOrganization imports must be in the unit"
    # donor frame fields landed
    assert sf["m_seekItemId"] == "Concrete-Square-Column-0000-CAN-ENU"
    assert sf["m_appVersionAtLoad"] == 2660
    assert sf["m_bIsSavable"] is False
    # identity stayed ours
    assert sf["m_categoryId"] == -2001040
    assert sf["m_partType"] == 14
    # our membership registry, extended by the two imports
    rows = ((sf.get("m_familyIds") or {}).get("value") or {}).get("m_data") or []
    assert len(rows) == 42
    assert sf["m_nextAbsorbedIndex"] == 42


def test_f_probes_ride_the_exact_b0_recipe(acct):
    for name in F_PROBES:
        info = acct["built"][name]
        assert info["base"].endswith("G_ABPD.rvt")
        assert "corpus_symbol_form" in info["recipe"]
        assert info["instance_connmgr"] == "FamilyInstanceConnectorManager"
        assert all(v["ok"] for v in info["symbol_form"].values())
        assert len(info["instance_ids"]) == 1


def test_h8b_is_the_loader_split_anchor(acct):
    info = acct["built"]["H8B"]
    assert info["base"].endswith("rstbasicsampleproject.rvt")
    assert "corpus_symbol_form" in info["recipe"]
    assert "famload" in info["recipe"]
    assert info["instance_connmgr"] == "FamilyInstanceConnectorManager"
    assert all(v["ok"] for v in info["symbol_form"].values())
    assert info["reference_resolution"]["unresolved_anywhere"] == 0


# ---------------------------------------------------------------------------
# probes.json: order, bases, md5s, the decision table
# ---------------------------------------------------------------------------

def test_probes_json_order_and_bases(probes):
    rungs = [p["rung"] for p in probes["probes"]]
    assert rungs == list(LADDER), \
        "reading order must be U16, F1, U12345, H8B, pairs, F-singles"
    for p in probes["probes"]:
        want = ("experiments/genesis/subst_k4/compose/G_ABPD.rvt"
                if p["rung"].startswith("F")
                else "samples/rstbasicsampleproject.rvt")
        assert p["base"] == want
        f = os.path.join(ROOT, p["file"])
        assert os.path.isfile(f)
        h = hashlib.md5(open(f, "rb").read()).hexdigest()
        assert h == p["md5"], f"{p['rung']}: probes.json md5 is stale"
        assert p["gates"]["gates_ok"] is True
        assert p["blob_proof"]["added_nonce_verified"] is True
        assert p["blob_proof"]["units_added_vs_base"] == 1


def test_decision_table_covers_the_branches(probes):
    r = probes["reading_the_matrix"]
    keys = " ".join(r)
    for needed in ("CTRL", "U16 FAIL", "U16 PASS + U12345 FAIL",
                   "U16 PASS + U12345 PASS", "F1 PASS", "F1 FAIL",
                   "H8B", "pairs", "singles", "honest residue"):
        assert needed in keys, f"decision table lacks the {needed} branch"
    assert "frame_diff.json" in r["F1 PASS (with U16+U12345 PASS)"]
    assert "untested_by_swap" in r["honest residue"]
    assert "H8B" in r["F1 FAIL"], "F1 FAIL must route through the loader split"


# ---------------------------------------------------------------------------
# the staged batch (two controls) -- runs only once stage() has happened
# ---------------------------------------------------------------------------

def _final_batch():
    best = None
    for p in glob.glob(os.path.join(ACCEPTANCE, "batch_*.json")):
        try:
            with open(p) as fh:
                man = json.load(fh)
        except (OSError, ValueError):
            continue
        if "famdoc_final" in str(man.get("tool", "")):
            n = int(re.match(r"batch_(\d+)", os.path.basename(p)).group(1))
            if best is None or n > best[0]:
                best = (n, man)
    return best


staged = pytest.mark.skipif(_final_batch() is None,
                            reason="round not yet staged")


@staged
def test_staged_batch_two_controls_and_md5s():
    n, man = _final_batch()
    assert man["control_count"] == 2
    entries = man["entries"]
    controls = [e for e in entries if e["kind"] == "control"]
    assert len(controls) == 2
    srcs = {e["control_source"] for e in controls}
    assert srcs == {"samples/rstbasicsampleproject.rvt",
                    "experiments/genesis/subst_k4/compose/G_ABPD.rvt"}
    for e in entries:
        staged_path = os.path.join(ROOT, e["staged_as"])
        assert os.path.isfile(staged_path), e["staged_as"]
        h = hashlib.md5(open(staged_path, "rb").read()).hexdigest()
        assert h == e["md5"], f"{e['staged_as']}: staged copy md5 drifted"
    order = [os.path.splitext(os.path.basename(e["staged_as"]))[0]
             for e in entries if e["kind"] == "probe"]
    assert order == list(LADDER)
    for c in controls:
        src_h = hashlib.md5(
            open(os.path.join(ROOT, c["control_source"]), "rb").read()).hexdigest()
        assert src_h == c["md5"], "control is not byte-identical to its source"


@staged
def test_staged_controls_named_with_batch_tag():
    n, man = _final_batch()
    for e in man["entries"]:
        if e["kind"] == "control":
            assert re.search(rf"_b{n}\.rvt$", e["staged_as"])


@staged
def test_staged_probes_match_the_stream_files():
    n, man = _final_batch()
    with open(ACCT) as fh:
        acct = json.load(fh)
    md5s = {name: acct["built"][name]["md5"] for name in LADDER}
    for e in man["entries"]:
        if e["kind"] != "probe":
            continue
        rung = os.path.splitext(os.path.basename(e["staged_as"]))[0]
        assert e["md5"] == md5s[rung], \
            f"{rung}: staged copy is not the gated build"
