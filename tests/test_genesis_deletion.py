"""Tests for tools/genesis_deletion.py -- THE DELETION ENDGAME (genesis-deletion).

The subject is the certified in-place base ZA_deep (VERDICTS #18) and the
four delete-with-content rungs + the cumulative D_all this stream retires by
THE REDUCTION LAW (src/rvt/reduce_law.py): every emitted file must be
EDIT-FREE (assert_edit_free: 0 edited survivors / 0 added ids), validator
VALID (0 errors), structurally proven, four-registry coherent, with every
non-partition stream byte-identical to the base (Global/Latest untouched:
registry parity 100% for survivors, deleted ids' entries LEFT DANGLING).

The base + Group A's curtain_constellation.json live under experiments/;
the tests skip when they are absent.  End-to-end emissions go to a temp
directory (module-scoped, built once).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

BASE = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a", "ZA_deep.rvt")
CURTAIN_JSON = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a",
                            "curtain_constellation.json")
DELETION_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "deletion")

_have_base = os.path.exists(BASE) and os.path.exists(CURTAIN_JSON)
pytestmark = pytest.mark.skipif(not _have_base, reason="ZA_deep base / curtain census absent")

if _have_base:
    import genesis_deletion as GD                                    # noqa: E402
    from rvt import reduce_law as RL                                # noqa: E402
    import rvt_reduce as RR                                        # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def st():
    return GD.state_of(BASE)


@pytest.fixture(scope="module")
def endgame(st):
    return GD.build_endgame(st)


@pytest.fixture(scope="module")
def emitted(st, endgame, tmp_path_factory):
    """Emit D_curtain / D_links / D_content (+ probes.json) into a temp dir."""
    out_dir = str(tmp_path_factory.mktemp("deletion"))
    control = GD.stage_control(BASE, out_dir)
    reports = {}
    for name in ("D_curtain", "D_links", "D_content"):
        reports[name] = GD.emit_rung(name, endgame.sets[name], st, endgame=endgame,
                                     out_dir=out_dir, control=control)
    probes = GD.write_probes_manifest(reports, endgame, control, out_dir=out_dir)
    return {"out_dir": out_dir, "reports": reports, "control": control, "probes": probes}


# ---------------------------------------------------------------------------
# 1. the base + the law policy
# ---------------------------------------------------------------------------

def test_base_is_viewer_certified():
    cert = GD.certification_of(BASE)
    assert cert is not None, "ZA_deep must be in viewer-certified.json 'certified'"
    assert "PASS" in str(cert.get("proves") or "").upper() or "LOADS" in str(cert.get("proves") or "")
    assert GD.assert_certified(BASE) == cert


def test_uncertified_base_is_refused(tmp_path):
    p = tmp_path / "K1_lookalike.rvt"
    p.write_bytes(b"not a certified base")
    with pytest.raises(RuntimeError):
        GD.assert_certified(str(p))


def test_law_policy_sanctions_maxgc_and_refuses_neutralise():
    law = RL.law_policy()
    assert law.permits("maxgc", "reduction-rung").allowed
    assert not law.permits("neutralise-referrers", "reduction-rung").allowed
    assert not law.permits("neutralise-struct-drop", "genesis-base").allowed
    with pytest.raises(RL.BannedGeneratorError):
        RL.guard_generator("neutralise-referrers", "reduction-rung")


# ---------------------------------------------------------------------------
# 2. the constellations (graph proof) and the deletion sets
# ---------------------------------------------------------------------------

def test_curtain_constellation_is_the_json_set_plus_two_previews(endgame):
    with open(CURTAIN_JSON) as fh:
        cj = json.load(fh)
    core = {int(e) for e in cj["removal_set"]}
    assert len(core) == 232 == cj["count"]
    ids = set(endgame.curtain.ids)
    assert core <= ids
    assert ids - core == set(GD.PREVIEW_LEGEND_CURTAIN)             # 907423 / 907424
    assert len(ids) == 234
    bc = endgame.curtain.by_class
    assert bc["Family"] == 8 and bc["FamilySurrogate"] == 8
    assert bc["DBViewType"] == 72 and bc["FontElem"] == 24
    assert bc["CategoryElem"] == 40 and bc["GStyleElem"] == 40
    assert bc["PenWidthTableElem"] == 8 and bc["SectionAttributes"] == 8
    assert bc["LegendComponent"] == 2
    # a coherent delete-with-content constellation has NO outside referrers
    assert endgame.curtain.outside_referrers == []
    # the two previews were added because they were the ONLY outside referrers
    added = {p["legend_component"] for p in endgame.curtain.grew_from["previews_added"]}
    assert added == set(GD.PREVIEW_LEGEND_CURTAIN)


def test_links_constellation_deletes_instance_side_and_blocks_symbol(endgame):
    assert set(endgame.links.ids) == {GD.LINK_INSTANCE, GD.LINK_COPYWATCH}
    assert GD.LINK_SYMBOL not in set(endgame.links.ids)
    assert GD.LINK_APPEARANCE_PARENT not in set(endgame.links.ids)     # ours, kept on purpose
    assert endgame.links.outside_referrers == []
    b = endgame.links_blocked
    assert b["element"] == GD.LINK_SYMBOL
    pinners = {p["referrer"] for p in b["pinned_by"]}
    # our own view constellation (Y9 / Y2 landed) pins the symbol ...
    assert {230, 245443, 1064656, 1454508, 69851} <= pinners
    # ... via inherited seq-101 header parents, plus the drafting view's seq-102 map
    seqs = {(p["referrer"], f["seq"]) for p in b["pinned_by"] for f in p["fields"]}
    assert (245443, 101) in seqs and (1454508, 101) in seqs
    assert (GD.DRAFTING_VIEW, 102) in seqs
    ours = {p["referrer"]: p["ours"] for p in b["pinned_by"]}
    assert ours[230] and ours[245443] and ours[1454508]                 # OUR landed slots


def test_content_constellation_is_the_dimension_group_room_and_previews_blocked(endgame):
    assert set(endgame.content.ids) == {GD.CONSTRAINT_DIM, *GD.CONSTRAINED_REFPLANES}
    assert endgame.content.outside_referrers == []
    b = endgame.content_blocked
    room = set(b["room_constellation"]["ids"])
    assert {GD.ROOM, GD.ROOM_LEVEL_PLAN, GD.ROOM_SKETCH_PLANE, *GD.ROOM_BOUNDARY_CURVES} == room
    # the anchor chain names the containing topology and OUR area scheme + its seq-102 field
    chain = b["room_constellation"]["anchor_chain"]
    els = {c["element"] for c in chain}
    assert els == {GD.ROOM_TOPOLOGY, GD.AREA_SCHEME_OURS}
    ours = [c for c in chain if c["element"] == GD.AREA_SCHEME_OURS][0]
    assert ours["ours"] is True
    assert any(f.get("seq") == 102 for f in ours["names_topology_in"])
    # the two type previews are owned via m_previewElemId (a seq-102 field)
    tp = b["type_preview_legend_components"]
    assert set(tp["ids"]) == {GD.PREVIEW_LEGEND_WALLTYPE, GD.PREVIEW_LEGEND_FLOORTYPE}
    for owner_fields in tp["owners"].values():
        assert any(f.get("seq") == 102 and "m_previewElemId" in str(f.get("field", ""))
                   for f in owner_fields)


def test_queue99_closure_equals_curtain_union_content(endgame):
    acct = endgame.queue_accounting
    assert acct["queue_count"] == 99
    bc = acct["queue_by_class"]
    assert bc == {"DBViewType": 72, "Family": 8, "FamilySurrogate": 8, "CurveElem": 5,
                  "LegendComponent": 4, "LinearDimString": 1, "LevelRoomPlan": 1}
    assert acct["equals_curtain_union_content"] is True
    assert acct["queue_members_unaccounted"] == []
    assert set(acct["queue_members_blocked_room"]) == {*GD.ROOM_BOUNDARY_CURVES, GD.ROOM_LEVEL_PLAN}
    assert set(acct["queue_members_blocked_type_previews"]) == {GD.PREVIEW_LEGEND_WALLTYPE,
                                                               GD.PREVIEW_LEGEND_FLOORTYPE}
    assert set(endgame.sets["D_queue"]) == set(endgame.sets["D_curtain"]) | set(endgame.sets["D_content"])


def test_set_relations_and_bisection_structure(endgame):
    S = {k: set(v) for k, v in endgame.sets.items()}
    assert S["D_all"] == S["D_curtain"] | S["D_links"] | S["D_content"] | S["D_queue"]
    assert S["D_all"] - S["D_queue"] == {GD.LINK_INSTANCE, GD.LINK_COPYWATCH}
    assert not (S["D_curtain"] & S["D_links"])
    assert not (S["D_curtain"] & S["D_content"])
    assert not (S["D_links"] & S["D_content"])
    assert len(S["D_all"]) == 240 and len(S["D_curtain"]) == 234
    rel = endgame.set_relations()
    assert rel["D_all_equals_union_of_singles"] and rel["D_queue_equals_curtain_union_content"]


def test_no_set_touches_history_carrier_or_our_slots_beyond_the_documented_one(st, endgame):
    doc = st["doc"]
    top = max(doc.et_by_id.values(), key=lambda r: r.modified_ep)     # the History-invariant carrier
    landed = GD.landed_slots()
    for name, ids in endgame.sets.items():
        assert int(top.id) not in set(ids), f"{name} deletes the max-episode element"
        ours_deleted = {i for i in ids if i in landed}
        # the ONLY landed (ours) element any set deletes = our CopyWatchProperties
        assert ours_deleted <= {GD.LINK_COPYWATCH}, (name, ours_deleted)


def test_every_set_is_maxgc_closed(st, endgame):
    for name, ids in endgame.sets.items():
        seed = RR._protect_history(st, set(ids))
        assert seed == set(ids), name
        delete, kept, _ev = RR.maxgc(st, seed)
        assert kept == set(), f"{name}: {len(kept)} pinned -> not a closed constellation"
        assert delete == set(ids)


# ---------------------------------------------------------------------------
# 3. end-to-end emission: the law + the gates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected_deleted", [("D_curtain", 234), ("D_links", 2), ("D_content", 4)])
def test_emitted_rung_is_edit_free_valid_and_coherent(emitted, endgame, name, expected_deleted):
    rep = emitted["reports"][name]
    assert rep["verdict"] == "VALID", rep.get("problems")
    assert rep["deletion_set"]["deleted"] == expected_deleted
    assert rep["deletion_set"]["kept_pinned"] == 0
    # THE LAW GUARD
    assert rep["reduce_law"]["assert_edit_free"] == "PASS"
    lj = rep["reduce_law"]["report"]
    assert lj["verdict"] == "EDIT-FREE" and lj["survivors_edited"] == 0 and lj["added"] == 0
    assert lj["removed"] == expected_deleted
    # the arbiter + structure + coherence
    assert rep["validator"]["ok"] and rep["validator"]["errors"] == 0
    assert rep["structural"]["ok"] and rep["structural"]["stamps_bad"] == 0
    assert rep["structural"]["deleted_still_present"] == []
    assert rep["coherence"]["coherent"] is True
    # only the partition + ElemTable may differ; the ADocument is untouched
    si = rep["stream_identity"]
    assert si["only_partition_and_elemtable_differ"] and si["latest_byte_identical"]
    assert si["contentdocs_byte_identical"] and si["partitiontable_byte_identical"]
    assert set(si["differing_streams"]) == {"Global/ElemTable", "Partitions/21"}
    # the dangling census lists deleted ids only (never a present one)
    assert rep["dangling_census"]["deleted_ids_still_present_in_file"] == []
    assert rep["registry_parity"]["nulled_live_registry_ids"] == 0
    # a separate law report is written per file
    with open(os.path.join(emitted["out_dir"], f"{name}_law.json")) as fh:
        law_file = json.load(fh)
    assert law_file["assert_edit_free"] == "PASS"


def test_reduce_law_guard_on_the_emitted_files_directly(emitted):
    """The GUARD itself (not our wrapper): assert_edit_free raises on any
    edited survivor; on our files it must return an EDIT-FREE report."""
    for name in ("D_links", "D_content"):
        path = os.path.join(emitted["out_dir"], f"{name}.rvt")
        rep = RL.assert_edit_free_files(BASE, path)                # raises SurvivorEditedError if not
        assert rep.ok and rep.verdict == "EDIT-FREE"
        assert not rep.added and not rep.survivors_edited


def test_curtain_dangling_census_is_the_registry_surface(emitted):
    d = emitted["reports"]["D_curtain"]["dangling_census"]
    assert d["by_class"] == {"CategoryElem": 40, "GStyleElem": 40, "FamilySurrogate": 8}
    paths = " ".join(d["by_registry_path"])
    assert "CategoryTracking" in paths and "FamilyMgr" in paths


def test_links_dangling_census_names_the_link_registries(emitted):
    d = emitted["reports"]["D_links"]["dangling_census"]
    assert set(d["by_class"]) == {"RvtLinkInstance", "CopyWatchProperties"}
    paths = " ".join(d["by_registry_path"])
    assert "CopyWatchModeMgr" in paths and "RvtLinkInstTracking" in paths


def test_probes_manifest_declares_certified_base_and_control_bisection_first(emitted):
    with open(emitted["probes"]) as fh:
        man = json.load(fh)
    order = man["upload_order_bisection_first"]
    assert order[0] == "D_all"                                     # cumulative first
    assert set(order) == {"D_all", "D_curtain", "D_links", "D_content", "D_queue"}
    assert man["standing_control"]["file"].endswith(GD.CONTROL_NAME)
    for p in man["probes"]:
        assert p["base"]["file"] == "experiments/genesis/subst_k4/residue_a/ZA_deep.rvt"
        assert p["derived_from"] == p["base"]["file"]
        assert p["control_to_upload_with_batch"]["md5"] == emitted["control"]["md5"]
    # the gate's own base resolver reads the declaration (manifest override
    # -> our temp probes.json; the ledger must call the base CERTIFIED)
    import probe_batch as PB
    br = PB.resolve_base(os.path.join(emitted["out_dir"], "D_links.rvt"),
                         manifest_override=emitted["probes"])
    assert br.base == "experiments/genesis/subst_k4/residue_a/ZA_deep.rvt"
    st, _entry = PB.Ledger.load().status(br.base)
    assert st == "certified"


def test_control_is_byte_identical_to_the_base(emitted):
    ctrl = os.path.join(emitted["out_dir"], GD.CONTROL_NAME)
    assert emitted["control"]["md5"] == GD._md5(BASE) == GD._md5(ctrl)


# ---------------------------------------------------------------------------
# 4. the committed batch (skip if the stream has not been run)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["D_all", "D_curtain", "D_links", "D_content", "D_queue"])
def test_committed_batch_files_are_certified_clean(name):
    rvt = os.path.join(DELETION_DIR, f"{name}.rvt")
    rep_p = os.path.join(DELETION_DIR, f"{name}.json")
    if not (os.path.exists(rvt) and os.path.exists(rep_p)):
        pytest.skip("committed deletion batch not built")
    with open(rep_p) as fh:
        rep = json.load(fh)
    assert rep["verdict"] == "VALID", rep.get("problems")
    assert rep["reduce_law"]["assert_edit_free"] == "PASS"
    assert rep["validator"]["errors"] == 0 and rep["validator"]["ok"]
    assert rep["coherence"]["coherent"] is True
    assert rep["stream_identity"]["latest_byte_identical"] is True
