"""tests for the Y2025 settings + catalog rungs (rvt.genesis.y2025_a).

Layers, each skipping cleanly when its inputs are absent so the suite stays
green on machines without the certified 2025 base / built artifacts:

  1. the rung table + manifest order (pure, no artifacts);
  2. the built rungs' recorded certifications (needs
     experiments/genesis/subst_k4_2025/): verdict VALID, validator 0 errors,
     the byte-delta assertion table (only the landed slots' seq-102 records
     changed; ADocument + ElemTable byte-identical), registry parity,
     four-registry coherence 1/0/0, and the Y1s/Y1 byte-identity;
  3. on-disk content proofs decoded through the 2025 stack (needs the
     artifacts + the port2025 pins): the Y4 corrected 2025 wire shapes, the
     Y2 browser sortParamId map, the Y6 2025 catalog (1,399-key profile, the
     four differing flag words), the Y7 palette laws (no swapped int params,
     ascending param ids -- the 2026 palette lesson), release detection;
  4. the pen-table scale-key preflight + the probes manifest + the
     probe_batch gate check (base certified by verdict #28).
"""
import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

OUT = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025")
BASE = os.path.join(ROOT, "experiments", "genesis2025", "reduce", "B2025_K4.rvt")
PINS = os.path.join(ROOT, "experiments", "genesis2025", "subst",
                    "builtin_style_profile_2025.json")

LADDER = ["Y1_2025", "Y2_2025", "Y3_2025", "Y4_2025", "Y5_2025", "Y6_2025",
          "Y7_2025"]
SINGLES = ["Y1s_2025", "Y6s_2025"]
ALL = LADDER + SINGLES

pytestmark = pytest.mark.usefixtures("no_release_leak")   # the rung rows enter versions.reading in-process
needs_base = pytest.mark.skipif(not os.path.exists(BASE),
                                reason="certified 2025 base not on this machine")
needs_rungs = pytest.mark.skipif(
    not all(os.path.exists(os.path.join(OUT, f"{n}.json")) for n in ALL),
    reason="Y2025 ladder artifacts not built")
needs_files = pytest.mark.skipif(
    not all(os.path.exists(os.path.join(OUT, f"{n}.rvt")) for n in ALL),
    reason="Y2025 rung files not built")
needs_pins = pytest.mark.skipif(not os.path.exists(PINS),
                                reason="2025 catalog pins not present")


def _rep(name):
    with open(os.path.join(OUT, f"{name}.json")) as fh:
        return json.load(fh)


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _doc(path):
    from rvt.mutate import Document
    return Document.from_file(path)


# ---------------------------------------------------------------------------
# 1. the rung table + manifest order (pure)
# ---------------------------------------------------------------------------
def test_rung_table_shape():
    from rvt.genesis import y2025_a as Y
    rungs = Y.rungs_2025()
    names = [r.name for r in rungs]
    assert names == ALL
    by = {r.name: r for r in rungs}
    # the cumulative chain mirrors the 2026 ladder's Y1..Y7
    assert by["Y1_2025"].parent == "BASE" and by["Y1_2025"].build == "X1"
    for a, b in zip(LADDER, LADDER[1:]):
        assert by[b].parent == a
    assert [by[n].build for n in LADDER] == ["X1", "X2", "X3", "X4", "X5", "X6a", "X7P"]
    # the two single-change probes come straight off the base
    assert by["Y1s_2025"].parent == "BASE" and by["Y1s_2025"].build == "X1"
    assert by["Y6s_2025"].parent == "BASE" and by["Y6s_2025"].build == "X6a"
    # every rung replaces the seq-102 object record only
    assert all(tuple(r.seqs) == (102,) for r in rungs)


def test_upload_order_bisection_first():
    from rvt.genesis import y2025_a as Y
    # the charter: Y7_2025 deepest first, then the singles, then intermediates
    assert Y.UPLOAD_ORDER[0] == "Y7_2025"
    assert set(Y.UPLOAD_ORDER[1:3]) == {"Y1s_2025", "Y6s_2025"}
    assert sorted(Y.UPLOAD_ORDER) == sorted(ALL)


def test_tracking_v6_to_v5_hook_present():
    """The BrowserOrganizationTracking v6->5 field map (three ElementId
    fields) is implemented at the adapt() layer; the in-place Y2 rung never
    writes the ADocument (asserted separately on the report)."""
    from rvt.genesis import port2025 as P25
    keys = {k for k in P25.HOOKS if k[0] == "BrowserOrganizationTracking"}
    assert keys == {("BrowserOrganizationTracking", "m_currentBrOrgViews"),
                    ("BrowserOrganizationTracking", "m_currentBrOrgSheets"),
                    ("BrowserOrganizationTracking", "m_currentBrOrgSchedules")}


# ---------------------------------------------------------------------------
# 2. the recorded certifications of every built rung
# ---------------------------------------------------------------------------
@needs_rungs
@pytest.mark.parametrize("name", ALL)
def test_rung_valid_with_all_assertions(name):
    rep = _rep(name)
    assert rep.get("verdict") == "VALID", rep.get("FAILED_SELF_CHECK")
    v = rep["validator"]
    assert v.get("ok") and v.get("errors") == 0
    assert (rep.get("structural") or {}).get("ok")
    bd = rep["byte_delta"]
    # the byte-delta assertion table: ONLY that layer's seq-102 records change
    assert bd["assertion_holds"], bd["problems"]
    assert bd["only_partition_differs"]
    assert bd["records_added_ids"] == [] and bd["records_removed_ids"] == []
    assert bd["unexpected_changed_ids"] == []
    assert set(bd["records_changed_by_seq"]) <= {"102"}
    assert bd["elemtable_identical"] and bd["adocument_identical"]
    # registry parity + four-registry coherence (family-free: 1 unit / 0 / 0)
    assert (rep.get("parity") or {}).get("latest_byte_identical")
    co = rep["coherence"]
    assert co["coherent"] and co["save_units"] == 1
    assert co["contentdocs_entries"] == 0 and co["contenttable_records"] == 0
    # zero retarget self-check failures, zero dangling refs
    assert rep["retarget"]["record_selfcheck_failures"] == []
    assert rep["new_object_reference_check"]["dangling"] == 0
    # base + certification recorded
    assert rep["base"]["file"] == "experiments/genesis2025/reduce/B2025_K4.rvt"
    assert rep["base"]["certification"] is not None


@needs_rungs
def test_rung_shapes_mirror_the_2026_ladder():
    """Landed counts per rung follow the certified 2026 shape (adjusted for
    the 2025 corpus: 1,399-key profile of which the base carries 1,165)."""
    landed = {n: (_rep(n).get("plan") or {}).get("landed") for n in ALL}
    assert landed["Y1_2025"] == 1
    assert landed["Y2_2025"] == 12
    assert landed["Y3_2025"] == 5
    assert landed["Y4_2025"] == 8
    assert landed["Y5_2025"] == 51
    assert landed["Y6_2025"] == 1165 and landed["Y6s_2025"] == 1165
    assert landed["Y7_2025"] == 60          # 22 (X7) + 10 ext materials + 28 property sets
    assert landed["Y1s_2025"] == 1
    y6 = _rep("Y6_2025")
    assert y6["ours_not_landed"]["count"] == 234    # 2025 enum keys the base lacks
    # every record ported through the 2025 field maps; nothing 2026-only built
    for n in ALL:
        p25 = (_rep(n).get("build_info") or {}).get("port2025") or {}
        assert p25.get("dropped_2026_only") == []


@needs_rungs
def test_y7_palette_bucket_traces():
    """The Y7 union carries the corrected palette bucket: counts, zero family
    mismatches, and the 2026 palette lesson enforced (no swapped int params,
    ascending param-id order) as recorded by the constructor's own ledger."""
    pal = (_rep("Y7_2025").get("build_info") or {}).get("palette_bucket_v2") or {}
    assert pal.get("materials_extended") == 10
    assert pal.get("structural_v2") == 17 and pal.get("thermal_v2") == 11
    assert pal.get("family_mismatches") == []
    traces = pal.get("revalue_traces") or []
    assert len(traces) == 28
    assert all(t.get("swapped_ints_in_output") == 0 for t in traces)
    assert all(all((t.get("ascending") or {}).values()) for t in traces)
    assert all(t.get("elementid_set_present") for t in traces)


@needs_files
def test_single_change_probe_identity():
    """Y1s_2025 (base + only the pen table) is byte-identical to Y1_2025 --
    the build is deterministic and the two files carry one verdict."""
    assert _md5(os.path.join(OUT, "Y1s_2025.rvt")) == _md5(os.path.join(OUT, "Y1_2025.rvt"))


@needs_base
@needs_files
def test_control_is_byte_identical_to_certified_base():
    ctrl = os.path.join(OUT, "CTRL_B2025_K4_base.rvt")
    assert os.path.exists(ctrl)
    assert _md5(ctrl) == _md5(BASE)


# ---------------------------------------------------------------------------
# 3. on-disk content proofs (decoded through the 2025 stack)
# ---------------------------------------------------------------------------
@needs_files
def test_every_rung_detects_as_2025():
    from rvt import versions
    for n in ALL:
        assert versions.detect_release(os.path.join(OUT, f"{n}.rvt")) == 2025


@needs_files
def test_y4_carries_the_corrected_2025_wire_shapes():
    from rvt import versions
    p = os.path.join(OUT, "Y4_2025.rvt")
    with versions.reading(p):
        d = _doc(p)
        ws = d.ids_of_class("RbsWireSettingsElem")
        assert len(ws) == 1
        v = d.value(ws[0], 102)
        # the three 2025-only doubles (mined from the 2025 corpus)
        assert v["m_dMaxVoltageBranchSizing"] == 0.02
        assert v["m_dMaxVoltageFeederSizing"] == 0.03
        assert v["m_dAmbientTemperature"] == 303.15000000000003
        sz = d.ids_of_class("RbsWireSizesElem")
        assert len(sz) == 1
        assert "m_bInitialized" not in (d.value(sz[0], 102) or {})


@needs_files
def test_y2_browser_orgs_carry_the_2025_sort_field():
    from rvt import versions
    p = os.path.join(OUT, "Y2_2025.rvt")
    with versions.reading(p):
        d = _doc(p)
        orgs = d.ids_of_class("BrowserOrganization")
        assert len(orgs) == 10
        for e in orgs:
            blob = json.dumps(d.value(e, 102) or {})
            assert "m_sortParamId" in blob
            assert "m_sortParameter\"" not in blob
    # ... and the ADocument (where BrowserOrganizationTracking lives) is
    # byte-identical to the parent: the v6->v5 registry map is never written
    # by an in-place rung (the hook itself is tested above)
    assert _rep("Y2_2025")["byte_delta"]["adocument_identical"]


@needs_files
@needs_pins
def test_y6_rows_follow_the_2025_profile():
    """The four (category, style-type) keys whose header flag word differs
    between releases carry the 2025 value 0x400201e in the emitted file,
    and the catalog was built from the 1,399-key 2025 profile."""
    from rvt import versions
    want = {-2000710, -2000711, -2000712, -2000713}
    for name in ("Y6_2025", "Y6s_2025"):
        p = os.path.join(OUT, f"{name}.rvt")
        with versions.reading(p):
            d = _doc(p)
            got = {}
            for gid in d.ids_of_class("GStyleElem"):
                v = d.value(gid) or {}
                if v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
                    continue
                if v.get("m_categoryId") in want and int(v.get("m_gstyleType", 1)) == 1:
                    h = d.decode(gid, 101)
                    got[v["m_categoryId"]] = int(h.value.get("m_abFlags4Bytes") or 0)
            assert got == {c: 0x400201e for c in want}, got
    # our records were built 1,399-strong (the 2025 profile), not 1,407 (2026)
    assert (_rep("Y6_2025").get("our_records_by_class") or {}).get("GStyleElem") == 1399


@needs_files
def test_y7_property_sets_obey_the_palette_laws_on_disk():
    """Every landed PropertySetElement in the emitted Y7_2025: int params
    correctly keyed (zero swapped (value, id) tuples) and every param array
    in ascending param-id order -- the 2026 palette lesson, re-proven on the
    2025 bytes."""
    from rvt import versions
    from rvt.genesis import residue_b2 as B2
    rep = _rep("Y7_2025")
    ps_slots = [r["slot"] for r in rep.get("landed_slots") or []
                if r["class"] == "PropertySetElement"]
    assert len(ps_slots) == 28
    p = os.path.join(OUT, "Y7_2025.rvt")
    with versions.reading(p):
        d = _doc(p)
        for slot in ps_slots:
            obj = d.value(int(slot), 102) or {}
            assert B2.swapped_int_entries(obj) == [], f"slot {slot}: swapped int params"
            asc = B2.param_ids_ascending(obj)
            assert all(asc.values()), f"slot {slot}: param ids not ascending: {asc}"


@needs_base
def test_pen_scale_keys_verified_against_the_2025_corpus():
    """The charter's 'verify, never assume': the base's own project pen table
    carries exactly our constructor's six model scale breakpoints, 16 pens
    per scale, and the -1 perspective/draft markers."""
    from rvt.genesis import y2025_a as Y
    with Y.y2025_context(BASE, OUT):
        pen = Y.pen_scale_key_check(BASE)
    assert pen["match"], pen
    assert pen["base_model_scales"] == [10, 20, 50, 100, 200, 500]
    assert pen["pens_per_scale"] == [16]


# ---------------------------------------------------------------------------
# 4. the probes manifest + the standing-controls gate
# ---------------------------------------------------------------------------
@needs_rungs
def test_probes_manifest():
    """probes.json is MERGE-WRITTEN (docs/inbox/y2025-views.md section 6):
    this stream's 9 entries plus the y2025-views stream's, foreign entries
    keyed by 'stream' and carrying their documented base shape
    ({file, certification} -- no certified_by).  Every entry, whichever
    stream wrote it, must name the certified base + its certification + the
    standing control and record a VALID verdict; the verdict-#28 citation is
    THIS stream's own field, asserted on all 9 of our entries."""
    with open(os.path.join(OUT, "probes.json")) as fh:
        m = json.load(fh)
    assert m["release"] == 2025
    assert m["upload_order_bisection_first"][0] == "Y7_2025"
    assert set(m["upload_order_bisection_first"][1:3]) == {"Y1s_2025", "Y6s_2025"}
    assert sorted(m["upload_order_bisection_first"]) == sorted(ALL)
    # every entry (either stream) names the certified base + certification +
    # control, with a VALID verdict
    for e in m["probes"]:
        assert e["base"]["file"] == "experiments/genesis2025/reduce/B2025_K4.rvt"
        assert e["base"]["certification"] is not None
        assert e["control_to_upload_with_batch"]["file"].endswith("CTRL_B2025_K4_base.rvt")
        assert e["verdict"] == "VALID"
    # this stream's 9 entries are all present, once each, and every one
    # carries the verdict-#28 citation (the charter's base-certification law)
    ours = [e for e in m["probes"] if not e.get("stream") and e["rung"] in ALL]
    assert sorted(e["rung"] for e in ours) == sorted(ALL)
    for e in ours:
        assert "#28" in e["base"]["certified_by"]
    pen = m.get("pen_scale_key_verification")
    assert pen and pen.get("match") is True
    ident = m.get("single_change_identity")
    assert ident and ident.get("identical") is True


@needs_rungs
@needs_files
@needs_base
def test_probe_batch_gate_accepts_the_ladder():
    """With B2025_K4 certified (verdict #28) the standing-controls gate must
    resolve every rung's declared base and admit the batch -- no
    --allow-uncertified anywhere in this stream."""
    from rvt.genesis import y2025_a as Y
    gate = Y.gate_check(OUT)
    assert gate["ran"]
    assert gate["admissible"], gate["violations"]
    for e in gate["entries"]:
        assert e["base_status"] in ("certified", "sample"), e
