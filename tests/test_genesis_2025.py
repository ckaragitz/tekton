"""tests for the 2025 reduction ladder (tools/genesis_2025.py).

Three layers, each skipping cleanly when its inputs are absent so the suite
is green on machines without the quarantined samples / built artifacts:

  1. the context_2025 patch set (needs samples/2025/): every module-LOCAL
     framing-tag copy is bound to the 2025 ordinal inside the context and
     RESTORED after -- the plan-SS7 "baked 0x0f28 literal" regression guard;
  2. the ladder artifacts (needs experiments/genesis2025/reduce/): validator
     0 errors + reduce-law verdicts + four-registry coherence as RECORDED in
     each rung's report, plus a live release/walk check of B2025_K4;
  3. the staged batch + format pins (needs experiments/genesis2025/ +
     docs/writer/format-2025.md facts): control byte-identity, resolvable
     lineage, pins consistent with rvt.versions.
"""
import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

SRC = os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "genesis2025")
RUNGS = os.path.join(OUT, "reduce")
FACTS = os.path.join(OUT, "format_facts_2025.json")

needs_sample = pytest.mark.skipif(not os.path.exists(SRC),
                                  reason="quarantined 2025 samples not on this machine")
needs_rungs = pytest.mark.skipif(not os.path.exists(os.path.join(RUNGS, "B2025_K4.rvt")),
                                 reason="2025 ladder artifacts not built")
needs_facts = pytest.mark.skipif(not os.path.exists(FACTS),
                                 reason="2025 format facts not collected")

R_RUNGS = ["R5_2025", "R6_2025", "R7_2025", "R8_2025", "R9_2025"]
ALL_RUNGS = R_RUNGS + ["K3_2025", "B2025_K4"]


def _rep(name):
    with open(os.path.join(RUNGS, f"{name}.json")) as fh:
        return json.load(fh)


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. the context patch set
# ---------------------------------------------------------------------------
@needs_sample
def test_context_2025_patches_and_restores_every_local_tag():
    import genesis_2025 as G
    import importlib
    from rvt import versions

    ords25 = dict(versions.KNOWN_RELEASES[2025].framing)
    before = {}
    for mod_name, attr, _spec in G._LOCAL_TAG_PATCHES:
        mod = importlib.import_module(mod_name)
        before[(mod_name, attr)] = getattr(mod, attr)
    from rvt import adocument as adoc
    dec_before = adoc._DECODER

    with G.context_2025(SRC) as ords:
        assert ords == ords25
        import rvt.reduce as RD
        import rvt.manipulate as MP
        import rvt.commit as CM
        import rvt.writer as WR
        import rvt.famgen.factory as FF
        assert RD.BLOCK_TAG == ords25["BLOCK_TAG"] == 0x0ED9
        assert RD.BLOCK_TRL_TAG == ords25["TRAILER_TAG"] == 0x0ED2
        assert MP.BLOCK_TAG == 0x0ED9 and MP.TRAILER_TAG == 0x0ED2
        assert CM.BLOCK_TRL_TAG == 0x0ED2 and WR.BLOCK_TRL_TAG == 0x0ED2
        assert FF.CD_SEPARATOR[:2] == (0x0391).to_bytes(2, "little")
        assert FF.CD_END_RECORD[:2] == (0x0391).to_bytes(2, "little")
        # the cached ADocument decoder is the FILE's schema, not the 2026 map
        assert adoc._DECODER is not dec_before
        assert adoc._DECODER.schema.by_name["SegmentMarker"].type_id == 0x0ED9

    # everything restored (incl. the 2026 literals)
    for (mod_name, attr), val in before.items():
        mod = importlib.import_module(mod_name)
        assert getattr(mod, attr) == val, f"{mod_name}.{attr} not restored"
    assert adoc._DECODER is dec_before
    import rvt.reduce as RD
    assert RD.BLOCK_TAG == 0x0F28


# ---------------------------------------------------------------------------
# 2. the ladder artifacts
# ---------------------------------------------------------------------------
@needs_rungs
@pytest.mark.parametrize("name", ALL_RUNGS)
def test_rung_validator_and_structure_recorded_clean(name):
    rep = _rep(name)
    assert rep["structural_ok"] is True
    assert rep["validator"]["ok"] is True
    assert rep["validator"]["errors"] == 0
    assert not rep.get("FAILED_SELF_CHECK")
    assert os.path.exists(os.path.join(RUNGS, f"{name}.rvt"))


@needs_rungs
@pytest.mark.parametrize("name", R_RUNGS + ["B2025_K4"])
def test_reduction_rungs_are_edit_free(name):
    law = _rep(name)["reduce_law"]
    assert law["verdict"] == "EDIT-FREE"
    assert law["ok"] is True
    assert law["added"] == 0
    assert law["survivors_edited"] == 0


@needs_rungs
def test_k3_is_the_declared_modify_rung_and_nothing_else():
    law = _rep("K3_2025")["reduce_law"]
    assert law["removed"] == 0 and law["added"] == 0
    assert law["edits_are_exactly_the_neutralised_referrers"] is True
    assert law["edited_not_neutralised"] == []
    # the 2026 K3 edit signature: view-type/attribute + settings referrers only
    classes = {c for c, _n in law["edit_classes"]}
    assert classes <= {"SectionAttributes", "LevelAttributes", "GridAttributes",
                       "ViewportAttributes", "InteriorElevAttributes",
                       "CalloutTag", "StructSettingsElem", "CopyWatchProperties",
                       "AreaReportSettingsElem", "LegendComponent"}


@needs_rungs
def test_four_registry_coherence_along_the_ladder():
    for name in R_RUNGS + ["K3_2025"]:
        cen = _rep(name)["census"]
        assert cen["save_units"] - 1 == cen["contentdocs_entries"] \
            == cen["contenttable_records"] == cen["familymgr_doc_guids"] == 52
    k4 = _rep("B2025_K4")["census"]
    assert (k4["save_units"], k4["contentdocs_entries"],
            k4["contenttable_records"], k4["familymgr_doc_guids"]) == (1, 0, 0, 0)
    assert k4["four_registry_coherent"] is True
    assert _rep("B2025_K4")["residual_guid_bytes_in_Latest_and_ContentDocuments"] == 0


@needs_rungs
@needs_sample
def test_b2025_k4_is_a_2025_file_that_walks_clean():
    from rvt import versions
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    p = os.path.join(RUNGS, "B2025_K4.rvt")
    assert versions.detect_release(p) == 2025
    with versions.reading(p):
        with open_rvt(p) as f:
            w = StreamWalker(f.logical(f.partition_streams()[0]),
                             inflate=False, keep_data=False)
            assert w.errors == []
            assert len(w.units) == 1          # zero embedded family documents


# ---------------------------------------------------------------------------
# 3. staged batch + format pins
# ---------------------------------------------------------------------------
@needs_rungs
@needs_sample
def test_staged_control_is_byte_identical_to_the_2025_sample():
    ctrl = os.path.join(OUT, "CTRL_rstbasicsampleproject_b17.rvt")
    if not os.path.exists(ctrl):
        pytest.skip("batch not staged")
    assert _md5(ctrl) == _md5(SRC)
    s26 = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
    if os.path.exists(s26):
        assert _md5(ctrl) != _md5(s26)      # the control is the 2025 bytes


@needs_rungs
def test_probes_manifest_declares_resolvable_lineage():
    if not os.path.exists(os.path.join(OUT, "probes.json")):
        pytest.skip("probes.json not written")
    import probe_batch as PB
    expect = {
        "R5_2025": "samples/2025/rstbasicsampleproject.rvt",
        "R9_2025": "samples/2025/rstbasicsampleproject.rvt",
        "K3_2025": "experiments/genesis2025/reduce/R9_2025.rvt",
        "B2025_K4": "experiments/genesis2025/reduce/K3_2025.rvt",
    }
    for name, base in expect.items():
        r = PB.resolve_base(os.path.join(RUNGS, f"{name}.rvt"))
        assert r.base == base, f"{name}: resolved {r.base!r}"


@needs_facts
def test_format_facts_match_the_versions_pins():
    from rvt import versions
    with open(FACTS) as fh:
        facts = json.load(fh)
    fl = facts["formats_latest_2025"]
    rel = versions.KNOWN_RELEASES[2025]
    assert fl["pin_matches_rvt_versions"] is True
    assert fl["size"] == rel.schema_size and fl["sha256"] == rel.schema_sha256
    assert fl["classes"] == rel.class_count == 4600
    assert fl["identical_across_six_samples"] is True
    assert facts["framing_matches_rvt_versions_table"] is True
    es = facts["esschema_corpus_2025"]
    assert es["byte_identical_across_six_samples"] is True
    assert es["total_pairs"] > 1000 and es["total_bytes"] > 1_000_000


@needs_facts
def test_class_diff_confirms_the_plan_portability_table():
    with open(FACTS) as fh:
        facts = json.load(fh)
    cd = facts["class_diff_2026_to_2025"]
    assert cd["classes_2026"] == 4690 and cd["classes_2025"] == 4600
    assert len(cd["only_in_2026"]) == 106 and len(cd["only_in_2025"]) == 16
    # plan SS5a.1: the conductor catalog is a 2026 invention
    conductor = {"CustomElement", "NamingCell", "RbsConductorMaterial",
                 "RbsConductorTemperatureRating",
                 "RbsConductorInsulationMaterial", "RbsConductorSize"}
    assert conductor <= set(cd["only_in_2026"])
    # names are stable, ordinals drift wholesale
    assert cd["renumbered_shared"] > 4000


@needs_facts
def test_history_terminal_2662_is_release_stable_not_a_2026_marker():
    with open(FACTS) as fh:
        facts = json.load(fh)
    hz = facts["identity_2025"]["history_upgrade_versions"]
    assert hz["2025_last"] == hz["2026_last"] == 2662
    assert hz["2025_count"] == hz["2026_count"] == 190
