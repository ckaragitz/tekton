"""tests/test_y2025_b.py -- the y2025-views stream's gates, pinned.

Covers rvt.genesis.y2025_b: the 2025 run context (patch + restore), the
emitted Y8_2025 / Y9_2025 / RA_2025 / RB / RC chain's certification reports
(validator 0 errors, byte-delta assertions, registry identity, the reduction
law on the deletion rung), the byte-level 2025-layout proofs on the emitted
files, and the composer handoff (Z aliases + D specs + probes.json).

Every artifact-dependent test SKIPS cleanly when the chain has not been
built on this machine (`.venv/bin/python -m rvt.genesis.y2025_b`).
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

from rvt.genesis import y2025_b as Y                                # noqa: E402

D = Y.OUT_DIR


def _rep(name: str) -> dict:
    p = os.path.join(D, f"{name}.json")
    if not os.path.exists(p):
        pytest.skip(f"{name}.json not built (run -m rvt.genesis.y2025_b)")
    with open(p) as fh:
        return json.load(fh)


def _rvt(name: str) -> str:
    p = os.path.join(D, f"{name}.rvt")
    if not os.path.exists(p):
        pytest.skip(f"{name}.rvt not built (run -m rvt.genesis.y2025_b)")
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
def test_base_is_the_certified_2025_base():
    """The stream builds ONLY on the viewer-certified B2025_K4 path."""
    import genesis_substitute_v3 as V3
    cert = V3.certification_of(Y.BASE_2025)
    assert cert is not None, "B2025_K4 must be in viewer-certified.json 'certified'"
    assert "2025" in json.dumps(cert)


def test_2025_schema_lacks_the_2026_only_view_fields_and_conductor_catalog():
    """The port table's four missed deltas + the missing conductor catalog,
    re-checked against the live 2025 schema pin."""
    from rvt.genesis import port2025 as P25
    _dec, _enc, schema = P25._S25()

    def own_fields(cls):
        cd = schema.by_name[cls]
        return {f.name for f in cd.fields}

    assert "m_viewPositionId" not in own_fields("DBView")
    assert "m_sheetTitleBlockId" not in own_fields("DBViewDrafting")
    assert "m_viewPosition" not in own_fields("Viewport")
    assert "m_viewAnchor" not in own_fields("Viewport")
    for cls in ("CustomElement", "NamingCell", "RbsConductorSize",
                "RbsConductorMaterial", "RbsConductorInsulationMaterial",
                "RbsConductorTemperatureRating"):
        assert not P25.exists_2025(cls), f"{cls} must be 2026-only"


def test_context_patches_and_restores_the_framing_constants():
    from rvt import reduce as RED
    before = RED.BLOCK_TAG
    with Y.context_y2025(Y.BASE_2025):
        assert RED.BLOCK_TAG != 0x0F28, "inside the context the 2025 ordinal is bound"
    assert RED.BLOCK_TAG == before == 0x0F28, "the context must restore the 2026 constant"


def test_source_aware_hooks_carry_already_2025_shaped_values():
    """A hook must not clobber a field the source (a decoded 2025 subtree)
    already carries; on a genuinely 2026-shaped source it still fires."""
    from rvt.genesis import port2025 as P25
    wrapped = Y._source_aware_hooks(P25)
    hook = wrapped[("GeomTable", "m_maxSafeTag")]
    assert hook({"m_maxSafeTag": 7}, None) == 7                  # 2025-shaped: carried
    assert hook({}, None) == P25.GEOMTABLE_2025["m_maxSafeTag"]  # 2026-shaped: mined constant


# ---------------------------------------------------------------------------
# 1. the in-place rungs' certification reports
# ---------------------------------------------------------------------------
INPLACE_RUNGS = ["Y8_2025", "Y9_2025", "RA_2025", "RB1_defs_2025", "RB2_mepcat_2025"]


@pytest.mark.parametrize("name", INPLACE_RUNGS)
def test_inplace_rung_report_gates(name):
    rep = _rep(name)
    assert rep.get("verdict") == "VALID", rep.get("FAILED_SELF_CHECK")
    v = rep.get("validator") or {}
    assert v.get("ok") and v.get("errors") == 0
    bd = rep.get("byte_delta") or {}
    assert bd.get("assertion_holds") is True
    assert bd.get("adocument_identical") is True
    assert bd.get("elemtable_identical") is True
    assert not bd.get("records_added_ids")
    assert not bd.get("records_removed_ids")
    assert (rep.get("base") or {}).get("file") == os.path.relpath(Y.BASE_2025, ROOT)


def test_y8_y9_parent_chain_and_mode_recorded():
    y8, y9 = _rep("Y8_2025"), _rep("Y9_2025")
    assert y8.get("parent_mode"), "each report must record which parent mode built it"
    assert y9.get("parent") == "experiments/genesis/subst_k4_2025/Y8_2025.rvt"
    # settings-chain mode: Y8's parent is the settings stream's Y7_2025
    if "settings-chain" in y8.get("parent_mode", ""):
        assert y8.get("parent") == "experiments/genesis/subst_k4_2025/Y7_2025.rvt"


def test_zrc_and_rc_inplace_reports():
    for name in ("Z_RC_2025", "RC_2025_inplace"):
        rep = _rep(name)
        assert rep.get("verdict") == "VALID", rep.get("FAILED_SELF_CHECK")
        assert (rep.get("validator") or {}).get("errors") == 0
        bd = rep.get("byte_delta") or {}
        assert bd.get("assertion_holds") is True
        assert bd.get("global_latest_identical") is True
        assert bd.get("global_elemtable_identical") is True


# ---------------------------------------------------------------------------
# 2. the deletion rung: the reduction law + stream identity
# ---------------------------------------------------------------------------
def test_rc_2025_deletion_is_law_clean():
    rep = _rep("RC_2025")
    assert rep.get("verdict") == "VALID", rep.get("FAILED_SELF_CHECK")
    law = rep.get("reduce_law") or {}
    assert law.get("ok") and law.get("verdict") == "EDIT-FREE"
    assert law.get("added") == 0 and law.get("survivors_edited") == 0
    assert (rep.get("validator") or {}).get("errors") == 0
    assert (rep.get("structural") or {}).get("ok") in (True, "True")
    assert (rep.get("four_registry") or {}).get("four_registry_coherent") is True
    si = rep.get("stream_identity") or {}
    assert si.get("only_partition_and_elemtable_differ") is True
    assert si.get("latest_byte_identical") is True
    ds = rep.get("deletion_set") or {}
    assert not ds.get("kept_pinned"), "maxgc must pin nothing"
    assert not ds.get("history_protected_removed")
    # the straggler families, nothing else
    assert set(ds.get("deleted_by_class") or {}) <= {
        "RvtLinkSymbol", "RvtLinkInstance", "CopyWatchProperties", "DataStorage",
        "LinearDimString", "RefPlane", "AreaSchemePlanTopologies", "RoomElem",
        "LevelRoomPlan", "CurveElem", "SketchPlane"}


def test_rc_2025_deleted_ids_absent_from_the_emitted_file():
    rep = _rep("RC_2025")
    path = _rvt("RC_2025")
    deleted = set(rep["deletion_set"]["deleted_ids"])
    assert deleted, "the deletion rung must delete something"
    with Y.context_y2025(Y.BASE_2025):
        from rvt.mutate import Document
        doc = Document.from_file(path)
        ids = {int(e) for e in doc.et_by_id}
    assert not (deleted & ids)


# ---------------------------------------------------------------------------
# 3. byte-level 2025-layout proofs on the emitted files
# ---------------------------------------------------------------------------
def test_emitted_files_detect_as_2025_and_carry_2025_block_tags():
    from rvt import versions
    y9 = _rvt("Y9_2025")
    rc = _rvt("RC_2025")
    assert versions.detect_release(y9) == 2025
    assert versions.detect_release(rc) == 2025
    with Y.context_y2025(Y.BASE_2025):
        from rvt.container import open_rvt
        from rvt.partitions import StreamWalker
        for path in (y9, rc):
            tags = set()
            with open_rvt(path) as f:
                for pn in f.partition_streams():
                    raw = f.logical(pn)
                    w = StreamWalker(raw, inflate=True, keep_data=False)
                    assert not w.errors, f"{path}: walker errors {w.errors[:2]}"
                    for b in w.blocks:
                        tags.add(struct.unpack_from("<H", raw, b.hdr_offset)[0])
            assert tags == {0xED9}, f"{path}: 2025 SegmentMarker only, got {tags}"


def test_y9_landed_views_have_the_2025_layout_and_our_names():
    rep = _rep("Y9_2025")
    path = _rvt("Y9_2025")
    landed = rep.get("landed_slots") or []
    with Y.context_y2025(Y.BASE_2025):
        from rvt.mutate import Document
        doc = Document.from_file(path)
        checked = 0
        for r in landed:
            if r["class"] not in ("DBViewPlan", "DBView3d", "DBViewProject",
                                  "DBViewDrafting", "Viewport"):
                continue
            v = doc.value(int(r["slot"])) or {}
            for k in ("m_viewPositionId", "m_sheetTitleBlockId",
                      "m_viewPosition", "m_viewAnchor"):
                assert k not in v, f"slot {r['slot']}: 2026-only field {k} present"
            checked += 1
        assert checked >= 5
        names = {str((doc.value(int(r["slot"])) or {}).get("m_viewName") or "")
                 for r in landed if r["class"] in ("DBViewPlan", "DBView3d")}
    assert any(n.startswith("GEN ") or n.startswith("L1 ") or n.startswith("L2 ")
               for n in names), names


def test_rb1_keeps_the_2025_shared_parameter_guid_registry_keys():
    rb1 = _rvt("RB1_defs_2025")
    ra = _rvt("RA_2025")
    with Y.context_y2025(Y.BASE_2025):
        from rvt.mutate import Document
        new, old = Document.from_file(rb1), Document.from_file(ra)
        n = same = 0
        for e in new.et_by_id:
            if new.class_of(int(e)) != "ParamElemExternal":
                continue
            g_new = ((new.value(int(e)) or {}).get("m_externalParamKey") or {}).get("m_guidValue")
            g_old = ((old.value(int(e)) or {}).get("m_externalParamKey") or {}).get("m_guidValue")
            n += 1
            same += (g_new == g_old and bool(g_new))
        assert n >= 400 and same == n, f"{same}/{n} GUID registry keys preserved"


def test_rb_conductor_catalog_skip_is_recorded_not_silent():
    """The 2026-only conductor catalog: the port layer's drop channel exists
    in both RB reports and recorded ZERO drops (the charter's 'skip it and
    note it' -- nothing constructed it, and the report says so)."""
    for name in ("RB1_defs_2025", "RB2_mepcat_2025"):
        rep = _rep(name)
        port = (rep.get("build_info") or {}).get("port2025") or {}
        assert "dropped_2026_only" in port
        assert port.get("dropped_2026_only") == []
        assert any("2026-only" in n for n in rep.get("build_notes") or [])


def test_z_rc_year_names_previews_and_link_pin():
    path = _rvt("Z_RC_2025")
    with Y.context_y2025(Y.BASE_2025):
        from rvt.mutate import Document
        doc = Document.from_file(path)
        years = [str((doc.value(int(e)) or {}).get("m_scheduleName") or "")
                 for e in doc.et_by_id
                 if doc.class_of(int(e)) == "BuildingOperatingYearSchedule"]
        assert years and all(s.startswith("GEN ") for s in years), years[:4]
        cen = _rep("rc_census_2025")
        for e in cen.get("previews") or []:
            assert (doc.value(int(e)) or {}).get("m_oPreviewImage") is None
        for e in cen.get("link_override_slots") or []:
            lo = ((doc.value(int(e)) or {}).get("m_pRvtLinkOverrides") or {}).get("value") or {}
            assert lo.get("m_displaySettingsMap") == []


def test_rc_census_was_derived_not_assumed():
    """The census carries the graph-derived sets, and the deletion seed came
    from them (no 2026 id list is baked into the module)."""
    cen = _rep("rc_census_2025")
    for k in ("link_symbols", "link_instances", "copywatch", "vendor_datastorage",
              "year_schedules", "header_slots", "link_override_slots",
              "room_constellations", "constraint_sets"):
        assert k in cen
    rep = _rep("RC_2025")
    seed = set(rep["deletion_set"]["seed"])
    assert set(cen["link_symbols"]) <= seed
    assert set(cen["vendor_datastorage"]) <= seed
    for members in (cen["room_constellations"] or {}).values():
        assert set(members) <= seed


# ---------------------------------------------------------------------------
# 4. the composer handoff
# ---------------------------------------------------------------------------
def test_z_aliases_are_byte_identical_and_name_their_parents():
    for alias, src, parent in (("Z_RA_2025", "RA_2025", "Y9_2025.rvt"),
                               ("Z_RB_2025", "RB_2025", "RA_2025.rvt")):
        a, s = _rvt(alias), _rvt(src)
        assert _md5(a) == _md5(s)
        rep = _rep(alias)
        assert rep.get("parent", "").endswith(parent)
    rb = _rep("RB_2025")
    assert rb.get("alias_of") in ("RB2_mepcat_2025", "RB1_defs_2025")
    assert _md5(_rvt("RB_2025")) == _md5(_rvt(rb["alias_of"]))


def test_d_specs_are_pin_free_subsets_of_the_proven_deletion():
    rep = _rep("RC_2025")
    deleted = set(rep["deletion_set"]["deleted_ids"])
    n = 0
    for stem in ("D_2025_links_pair", "D_2025_vendor_datastorage",
                 "D_2025_constraint_dim"):
        p = os.path.join(D, f"{stem}.json")
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            spec = json.load(fh)
        assert spec.get("policy") == "maxgc"
        assert spec.get("ids") and set(spec["ids"]) <= deleted
        # the symbol + room sets need the RC fixes first: never in a D_ spec
        cen = _rep("rc_census_2025")
        assert not (set(spec["ids"]) & set(cen["link_symbols"]))
        for members in (cen["room_constellations"] or {}).values():
            assert not (set(spec["ids"]) & set(members))
        n += 1
    assert n >= 2, "the composer's pin-free deletion specs must exist"


def test_d_union_spec_matches_the_proven_deletion_exactly():
    """D_2025_stragglers_full.json (the union the composer's subset-collapse
    composes) must carry EXACTLY the ids RC_2025 deleted (proven EDIT-FREE),
    and declare its prerequisite fixes."""
    p = os.path.join(D, "D_2025_stragglers_full.json")
    if not os.path.exists(p):
        pytest.skip("union spec not written")
    with open(p) as fh:
        spec = json.load(fh)
    rep = _rep("RC_2025")
    assert set(spec["ids"]) == set(rep["deletion_set"]["deleted_ids"])
    assert spec.get("policy") == "maxgc"
    assert spec.get("requires_first"), "the union must name the enabling fixes"


def test_probes_manifest_carries_this_stream_and_preserves_foreign_entries():
    p = os.path.join(D, "probes.json")
    if not os.path.exists(p):
        pytest.skip("probes.json not written")
    with open(p) as fh:
        man = json.load(fh)
    mine = [e for e in man.get("probes") or [] if e.get("stream") == "y2025-views"]
    if not mine:
        pytest.skip("y2025-views entries not merged yet")
    names = {e["rung"] for e in mine}
    assert {"Y8_2025", "Y9_2025", "RA_2025", "RC_2025"} <= names
    for e in mine:
        assert (e.get("base") or {}).get("file") == os.path.relpath(Y.BASE_2025, ROOT)
    foreign = [e for e in man.get("probes") or [] if e.get("stream") != "y2025-views"]
    settings = {e.get("rung") for e in foreign}
    if os.path.exists(os.path.join(D, "Y1_2025.json")):
        assert "Y1_2025" in settings or "Y7_2025" in settings, \
            "the settings stream's entries must survive the merge"
