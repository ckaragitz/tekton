"""tests/test_y2024.py -- the y2024-compose stream's gates, pinned.

Covers the whole 2024 substitution campaign: the settings ladder
(rvt.genesis.y2024_a: Y1..Y7_2024 + singles), the views/residue chain
(rvt.genesis.y2024_b: Y8/Y9 + RA/RB/RC), and the composer
(tools/genesis_2024_compose.py: anchor + G_ABPD_2024 + the staged batch +
the gated flip).  Every artifact-dependent test SKIPS cleanly when the
chain has not been built on this machine
(`.venv/bin/python -m rvt.genesis.y2024_a` then `-m rvt.genesis.y2024_b`
then `tools/genesis_2024_compose.py all`).
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rvt.genesis import y2024_a as YA                               # noqa: E402
from rvt.genesis import y2024_b as YB                               # noqa: E402

D = YB.OUT_DIR                       # experiments/genesis/subst_k4_2024
CD = os.path.join(D, "compose")


def _read(p: str) -> dict:
    if not os.path.exists(p):
        pytest.skip(f"{os.path.relpath(p, ROOT)} not built")
    with open(p) as fh:
        return json.load(fh)


def _rep(name: str) -> dict:
    return _read(os.path.join(D, f"{name}.json"))


def _rvt(name: str, base=D) -> str:
    p = os.path.join(base, f"{name}.rvt")
    if not os.path.exists(p):
        pytest.skip(f"{name}.rvt not built")
    return p


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 0. schema-level facts (no artifacts needed)
# ---------------------------------------------------------------------------
def test_base_is_the_certified_2024_base():
    """The stream builds ONLY on the viewer-certified B2024_K4 path
    (verdicts #32)."""
    import genesis_substitute_v3 as V3
    cert = V3.certification_of(YB.BASE_2024)
    assert cert is not None, "B2024_K4 must be in viewer-certified.json 'certified'"
    assert "2024" in json.dumps(cert)


def test_2024_schema_lacks_the_missing_constructed_classes():
    """The five 2025-era classes + the conductor catalog have NO 2024 twin
    (port2024 MISSING_2024_CONSTRUCTED) -- re-checked against the live pin."""
    from rvt.genesis import port2024 as P24
    for cls in P24.MISSING_2024_CONSTRUCTED:
        assert not P24.exists_2024(cls), f"{cls} must be missing from the 2024 map"


def test_2024_schema_view_layout_deltas():
    """The 2024 view-layer layout deltas, re-checked against the live pin:
    DBView drops m_viewPositionId; DBViewDrafting lacks m_sheetCollectionId
    and carries the 2024-only m_scheduleInstanceIds; Viewport v10 drops the
    two head-position fields."""
    from rvt.genesis import port2024 as P24
    _dec, _enc, schema = P24._S24()

    def own_fields(cls):
        return {f.name for f in schema.by_name[cls].fields}

    assert "m_viewPositionId" not in own_fields("DBView")
    assert "m_sheetCollectionId" not in own_fields("DBViewDrafting")
    assert "m_scheduleInstanceIds" in own_fields("DBViewDrafting")
    assert "m_viewPosition" not in own_fields("Viewport")
    assert "m_viewAnchor" not in own_fields("Viewport")


def test_context_patches_and_restores_the_framing_constants():
    from rvt import partitions as P      # the one binding every emitter reads (#467)
    from rvt import versions
    before = P.BLOCK_TAG
    want = versions.KNOWN_RELEASES[2024].framing["BLOCK_TAG"]
    with YB.context_y2024(YB.BASE_2024):
        assert P.BLOCK_TAG == want == 0x0E7C
    assert P.BLOCK_TAG == before, "the context must restore on exit"


def test_geo_site_guids_are_pinned_deterministic():
    """The chain's ONE nondeterminism (skeleton.new_geo_site minting uuid4)
    is pinned by the context: the two GeoSite records in Y8_2024.rvt carry
    the uuid5-derived GUIDs, so every full rebuild is byte-identical."""
    import uuid
    from rvt.genesis import skeleton as SK
    want = [str(uuid.uuid5(uuid.UUID(YB._GEO_GUID_NS),
                           f"tekton-y2024-geo-site-{n}")) for n in (1, 2)]
    orig = SK.new_geo_site
    p = os.path.join(D, "Y8_2024.rvt")
    with YB.context_y2024(YB.BASE_2024):
        assert SK.new_geo_site is not orig, "context must swap the constructor"
        if os.path.exists(p):
            from rvt.mutate import Document
            doc = Document.from_file(p)
            got = sorted(str((doc.value(int(e)) or {}).get("m_sharedCoordGUID"))
                         for e in doc.et_by_id
                         if doc.class_of(int(e)) == "GeoSite")
            assert got == sorted(want), got
    assert SK.new_geo_site is orig, "context must restore the constructor"


def test_source_aware_hooks_carry_existing_2024_fields():
    """A hook never clobbers a field the source already carries in its 2024
    form (parent-copied subtrees)."""
    from rvt.genesis import port2024 as P24
    wrapped = YB._source_aware_hooks(P24)
    hook = wrapped[("GeomTable", "m_maxSafeTag")]
    assert hook({"m_maxSafeTag": 42}, None) == 42          # carried
    assert hook({}, None) == -1                            # synthesized


# ---------------------------------------------------------------------------
# 1. the settings ladder (y2024_a)
# ---------------------------------------------------------------------------
SETTINGS = YA.LADDER + YA.SINGLES


@pytest.mark.parametrize("name", SETTINGS)
def test_settings_rung_valid_with_all_assertions(name):
    rep = _rep(name)
    assert rep.get("verdict") == "VALID", rep.get("FAILED_SELF_CHECK")
    v = rep.get("validator") or {}
    assert v.get("ok") and v.get("errors") == 0
    bd = rep.get("byte_delta") or {}
    assert bd.get("assertion_holds") is True
    assert bd.get("elemtable_identical") is True
    assert bd.get("adocument_identical") is True
    assert not bd.get("records_added_ids")
    assert not bd.get("records_removed_ids")


def test_single_change_probe_is_byte_identical_to_rung_one():
    a, b = _rvt("Y1_2024"), _rvt("Y1s_2024")
    assert _md5(a) == _md5(b)


def test_y5_missing_2024_classes_have_no_slots_and_none_landed():
    """The 2024 base carries no slots of the five missing classes (they are
    not in the schema), so the builders construct nothing for them -- the
    not-landed honesty channel."""
    rep = _rep("Y5_2024")
    landed = set((rep.get("plan") or {}).get("landed_by_class") or {})
    olds = set(rep.get("candidates_old_by_class") or {})
    for cls in ("SheetsInSheetCollectionTracker", "MEPNetworkDataElem",
                "STEPExportSettings", "SheetCollection",
                "BuildingOperatingYearSchedule"):
        assert cls not in landed
        assert cls not in olds


def test_probes_manifest_settings_half():
    man = _read(os.path.join(D, "probes.json"))
    mine = [e for e in man["probes"] if e.get("stream") == "y2024-settings"]
    assert [e["rung"] for e in mine] == YA.UPLOAD_ORDER
    for e in mine:
        assert e["base"]["certified_by"].startswith("ORCHESTRATOR VERDICTS #32")
        assert e["release"] == 2024
    pen = man.get("pen_scale_key_verification") or {}
    assert pen.get("match") is True
    gate = man.get("probe_batch_gate_check") or {}
    if gate.get("ran"):
        assert gate.get("admissible") is True


# ---------------------------------------------------------------------------
# 2. the views/residue chain (y2024_b)
# ---------------------------------------------------------------------------
INPLACE_CHAIN = ["Y8_2024", "Y9_2024", "RA_2024", "RB1_defs_2024",
                 "RB2_mepcat_2024", "Z_RC_2024", "RC_2024_inplace"]


@pytest.mark.parametrize("name", INPLACE_CHAIN)
def test_views_chain_rung_valid(name):
    rep = _rep(name)
    assert rep.get("verdict") == "VALID", rep.get("FAILED_SELF_CHECK")
    v = rep.get("validator") or {}
    assert v.get("ok") and v.get("errors") == 0


def test_rb_alias_is_byte_identical():
    rep = _rep("RB_2024")
    src = os.path.join(D, f"{rep['alias_of']}.rvt")
    assert _md5(src) == rep["md5"] == _md5(_rvt("RB_2024"))


def test_rc_census_year_schedules_empty_by_schema():
    cen = _read(os.path.join(D, "rc_census_2024.json"))
    assert cen.get("year_schedules") == []


def test_rc_deletion_rung_lawful():
    rep = _rep("RC_2024")
    assert rep.get("verdict") == "VALID", rep.get("FAILED_SELF_CHECK")
    assert rep["reduce_law"]["verdict"] == "EDIT-FREE"
    ds = rep["deletion_set"]
    assert ds["kept_pinned"] == [] and ds["history_protected_removed"] == []
    assert rep["four_registry"]["four_registry_coherent"] is True
    rg = rep.get("release_gate") or {}
    assert rg.get("ok") and rg.get("detected_release") == 2024
    assert rg.get("block_header_tags") == ["0xe7c"]


def test_deletion_specs_union_supersets_singles():
    full = _read(os.path.join(D, "D_2024_stragglers_full.json"))
    union = set(full["ids"])
    for name in ("D_2024_links_pair", "D_2024_vendor_datastorage",
                 "D_2024_constraint_dim"):
        sub = set(_read(os.path.join(D, f"{name}.json"))["ids"])
        assert sub < union, f"{name} must be a strict subset of the union"
    assert full["policy"] == "maxgc" and full["purpose"] == "genesis-base"


def test_z_aliases_byte_identical():
    for alias, src in (("Z_RA_2024", "RA_2024"), ("Z_RB_2024", "RB_2024")):
        assert _md5(_rvt(alias)) == _md5(_rvt(src))


# ---------------------------------------------------------------------------
# 3. the emitted bytes: release identity + the 2024 layout
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,base", [("Y7_2024", D), ("Y9_2024", D),
                                       ("RC_2024", D), ("G_ABPD_2024", CD)])
def test_emitted_file_is_2024_with_2024_framing(name, base):
    import genesis_2024 as G24
    from rvt import versions
    p = _rvt(name, base)
    assert versions.detect_release(p) == 2024
    rg = G24.release_gate(p)
    assert rg["ok"], rg
    assert rg["block_header_tags"] == ["0xe7c"]


def test_landed_view_records_have_the_2024_layout():
    """Decode a landed DBView-family record back from Y9_2024.rvt: no
    m_viewPositionId anywhere; a DBViewDrafting slot carries
    m_scheduleInstanceIds (blank)."""
    p = _rvt("Y9_2024")
    with YB.context_y2024(YB.BASE_2024):
        from rvt.mutate import Document
        doc = Document.from_file(p)
        checked_view = checked_drafting = 0
        for e in doc.et_by_id:
            e = int(e)
            cls = doc.class_of(e)
            if cls in ("DBViewPlan", "DBView3d", "DBViewDrafting", "DBViewSheet"):
                v = doc.value(e) or {}
                assert "m_viewPositionId" not in v, (e, cls)
                checked_view += 1
                if cls == "DBViewDrafting":
                    assert "m_scheduleInstanceIds" in v, (e, cls)
                    assert "m_sheetCollectionId" not in v, (e, cls)
                    checked_drafting += 1
        assert checked_view > 0 and checked_drafting > 0


# ---------------------------------------------------------------------------
# 4. the composer (anchor + G + batch + gated flip)
# ---------------------------------------------------------------------------
def test_anchor_holds_byte_identically():
    a = _read(os.path.join(CD, "anchor_2024.json"))
    assert a["BYTE_IDENTICAL"] is True
    assert a["compose_verdict"] == "COMPOSED-VALID"
    # recompute from the files, not the report
    repro = os.path.join(ROOT, a["reproduction"])
    target = os.path.join(ROOT, a["target"])
    if os.path.exists(repro) and os.path.exists(target):
        assert _md5(repro) == _md5(target) == a["md5_reproduction"]


def test_composed_g_is_full_valid_and_equals_the_deletion_proof():
    c = _read(os.path.join(CD, "compose_2024.json"))
    assert c["complete"] is True
    assert c["verdict"] == "COMPOSED-VALID" and not c["problems"]
    proof = c["final_byte_identical_to_chain_deletion_proof"]
    assert proof["identical"] is True
    g = _rvt("G_ABPD_2024", CD)
    assert _md5(g) == c["md5"]
    assert _md5(g) == _md5(_rvt("RC_2024"))
    assert (c.get("release_gate") or {}).get("ok") is True


def test_g_registry_relpath_matches_the_reserved_slot():
    """The composed file sits at the EXACT relpath genesis_base.json
    releases.2024 reserves."""
    pin = _read(os.path.join(ROOT, "src", "rvt", "frontdoor", "assets",
                             "genesis_base.json"))
    slot = pin["releases"]["2024"]
    assert slot["relpath"] == "experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt"
    c = _read(os.path.join(CD, "compose_2024.json"))
    assert c["out"] == slot["relpath"]


def test_staged_batch_is_the_charter_four_file_round():
    batches = sorted(f for f in os.listdir(CD) if f.startswith("batch_")
                     and f.endswith(".json")) if os.path.isdir(CD) else []
    if not batches:
        pytest.skip("no batch staged")
    man = _read(os.path.join(CD, batches[-1]))
    kinds = [e["kind"] for e in man["entries"]]
    names = [os.path.basename(e["file"]) for e in man["entries"]]
    assert kinds[0] == "control"
    assert names[1:] == ["G_ABPD_2024.rvt", "Y9_2024.rvt", "Y7_2024.rvt"]
    ctrl = man["entries"][0]
    assert ctrl["md5"] == _md5(YB.BASE_2024), \
        "the control must be byte-identical to the certified base"
    for e in man["entries"][1:]:
        assert str(e["base_status"]).startswith("certified"), e


def test_flip_applied_registry_slot_certified():
    """The 2024 flip IS applied (G_ABPD_2024 viewer-certified): the registry
    slot reads certified with the composed file's sha256/bytes pinned, and
    the version model agrees -- three agreeing sources."""
    from rvt import versions
    assert versions.KNOWN_RELEASES[2024].creation_certified is True
    assert versions.KNOWN_RELEASES[2024].genesis_base == \
        "experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt"
    pin = _read(os.path.join(ROOT, "src", "rvt", "frontdoor", "assets",
                             "genesis_base.json"))
    slot = pin["releases"]["2024"]
    assert slot["status"] == "certified"
    assert slot["sha256"] == \
        "e4a40671d8b6c649f4c8ba2ee45c1843f6d61e722a738cc2c88bd6cdb3dd925a"
    assert slot["bytes"] == 577536
    assert slot["relpath"] == \
        "experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt"


def test_flipdiff_carries_the_live_pins_and_is_blocked():
    import genesis_2024_compose as C24
    if not os.path.exists(C24.G_FINAL):
        pytest.skip("G_ABPD_2024 not composed")
    txt = C24.flipdiff()
    import genesis_compose as GC
    assert GC.sha256_of(C24.G_FINAL) in txt
    assert "NOT applied" in txt
    if GC.certification_of(C24.G_FINAL) is None:
        assert "BLOCKED" in txt


def test_compose_discovery_collapses_subset_deletion_specs():
    import genesis_2024_compose as C24
    if not os.path.exists(os.path.join(D, "D_2024_stragglers_full.json")):
        pytest.skip("deletion specs not written")
    specs = C24.discover_deletion_specs()
    names = {s.name for s in specs}
    assert "D_2024_stragglers_full" in names
    assert not names & {"D_2024_links_pair", "D_2024_vendor_datastorage",
                        "D_2024_constraint_dim"}, \
        "singles must collapse onto the union"
