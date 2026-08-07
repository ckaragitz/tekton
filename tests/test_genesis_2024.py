"""tests for the 2024 reduction ladder (tools/genesis_2024.py).

Mirrors tests/test_genesis_2025.py at the third release.  Three layers, each
skipping cleanly when its inputs are absent so the suite is green on
machines without the quarantined samples / built artifacts:

  1. the release_context / context_2024 patch set (needs samples/2024/):
     every module-LOCAL framing-tag copy is bound to the 2024 ordinal inside
     the context and RESTORED after -- the "baked 0x0f28 literal" regression
     guard at 2024, plus the context_2024 wrong-release refusal;
  2. the ladder artifacts (needs experiments/genesis2024/reduce/): validator
     0 errors + reduce-law verdicts + four-registry coherence + the RELEASE
     gate (detect_release == 2024, block tags == {0x0e7c}) as RECORDED in
     each rung's report, plus a live release/walk check of B2024_K4;
  3. the staged batch + format pins (needs experiments/genesis2024/ +
     format_facts_2024.json): control byte-identity against all three
     releases' samples, resolvable lineage, pins consistent with
     rvt.versions, the three-release corpus + 2662 stability findings, and
     the B2024_K4-vs-B2025_K4 census divergence == schema drift.
"""
import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

SRC = os.path.join(ROOT, "samples", "2024", "rstbasicsampleproject.rvt")
S25 = os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt")
S26 = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "genesis2024")
RUNGS = os.path.join(OUT, "reduce")
FACTS = os.path.join(OUT, "format_facts_2024.json")
BATCH = os.path.join(OUT, "batch_28.json")

needs_sample = pytest.mark.skipif(not os.path.exists(SRC),
                                  reason="quarantined 2024 samples not on this machine")
needs_rungs = pytest.mark.skipif(not os.path.exists(os.path.join(RUNGS, "B2024_K4.json")),
                                 reason="2024 ladder artifacts not built")
needs_facts = pytest.mark.skipif(not os.path.exists(FACTS),
                                 reason="2024 format facts not collected")

R_RUNGS = ["R5_2024", "R6_2024", "R7_2024", "R8_2024", "R9_2024"]
ALL_RUNGS = R_RUNGS + ["K3_2024", "B2024_K4"]


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
def test_context_2024_patches_and_restores_every_local_tag():
    import genesis_2024 as G
    import importlib
    from rvt import versions

    ords24 = dict(versions.KNOWN_RELEASES[2024].framing)
    before = {}
    for mod_name, attr, _spec in G._LOCAL_TAG_PATCHES:
        mod = importlib.import_module(mod_name)
        before[(mod_name, attr)] = getattr(mod, attr)
    from rvt import adocument as adoc
    dec_before = adoc._DECODER

    with G.context_2024(SRC) as ords:
        assert ords == ords24
        import rvt.reduce as RD
        import rvt.manipulate as MP
        import rvt.commit as CM
        import rvt.writer as WR
        import rvt.famgen.factory as FF
        assert RD.BLOCK_TAG == ords24["BLOCK_TAG"] == 0x0E7C
        assert RD.BLOCK_TRL_TAG == ords24["TRAILER_TAG"] == 0x0E75
        assert MP.BLOCK_TAG == 0x0E7C and MP.TRAILER_TAG == 0x0E75
        assert CM.BLOCK_TRL_TAG == 0x0E75 and WR.BLOCK_TRL_TAG == 0x0E75
        assert FF.CD_SEPARATOR[:2] == (0x037B).to_bytes(2, "little")
        assert FF.CD_END_RECORD[:2] == (0x037B).to_bytes(2, "little")
        # the cached ADocument decoder is the FILE's schema, not the 2026 map
        assert adoc._DECODER is not dec_before
        assert adoc._DECODER.schema.by_name["SegmentMarker"].type_id == 0x0E7C

    # everything restored (incl. the 2026 literals)
    for (mod_name, attr), val in before.items():
        mod = importlib.import_module(mod_name)
        assert getattr(mod, attr) == val, f"{mod_name}.{attr} not restored"
    assert adoc._DECODER is dec_before
    import rvt.reduce as RD
    assert RD.BLOCK_TAG == 0x0F28


@needs_sample
def test_context_2024_refuses_a_non_2024_file():
    import genesis_2024 as G
    from rvt import versions
    wrong = S25 if os.path.exists(S25) else S26
    if not os.path.exists(wrong):
        pytest.skip("no other-release sample to refuse")
    with pytest.raises(versions.VersionError):
        with G.context_2024(wrong):
            pass


@needs_sample
def test_release_context_is_release_general():
    """The shared helper binds whatever release the file is -- same patch
    list, no 2024 hardcoding (the generalization the 2025 ladder should
    adopt)."""
    import genesis_2024 as G
    if not os.path.exists(S25):
        pytest.skip("2025 sample absent")
    with G.release_context(S25) as ords:
        import rvt.reduce as RD
        assert ords["BLOCK_TAG"] == 0x0ED9        # the 2025 ordinal
        assert RD.BLOCK_TAG == 0x0ED9
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
@pytest.mark.parametrize("name", ALL_RUNGS)
def test_rung_release_gate_recorded_2024(name):
    rel = _rep(name)["release_gate"]
    assert rel["ok"] is True
    assert rel["detected_release"] == 2024
    assert rel["block_header_tags"] == ["0xe7c"]
    assert rel["walker_errors"] == 0


@needs_rungs
@pytest.mark.parametrize("name", R_RUNGS + ["B2024_K4"])
def test_reduction_rungs_are_edit_free(name):
    law = _rep(name)["reduce_law"]
    assert law["verdict"] == "EDIT-FREE"
    assert law["ok"] is True
    assert law["added"] == 0
    assert law["survivors_edited"] == 0


@needs_rungs
def test_k3_is_the_declared_modify_rung_and_nothing_else():
    law = _rep("K3_2024")["reduce_law"]
    assert law["removed"] == 0 and law["added"] == 0
    assert law["edits_are_exactly_the_neutralised_referrers"] is True
    assert law["edited_not_neutralised"] == []
    # the certified K3 edit signature (2026 round 5, 2025 verdicts #28)
    classes = {c for c, _n in law["edit_classes"]}
    assert classes <= {"SectionAttributes", "LevelAttributes", "GridAttributes",
                       "ViewportAttributes", "InteriorElevAttributes",
                       "CalloutTag", "StructSettingsElem", "CopyWatchProperties",
                       "AreaReportSettingsElem", "LegendComponent"}


@needs_rungs
def test_four_registry_coherence_along_the_ladder():
    for name in R_RUNGS + ["K3_2024"]:
        cen = _rep(name)["census"]
        assert cen["save_units"] - 1 == cen["contentdocs_entries"] \
            == cen["contenttable_records"] == cen["familymgr_doc_guids"] == 52
    k4 = _rep("B2024_K4")["census"]
    assert (k4["save_units"], k4["contentdocs_entries"],
            k4["contenttable_records"], k4["familymgr_doc_guids"]) == (1, 0, 0, 0)
    assert k4["four_registry_coherent"] is True
    assert _rep("B2024_K4")["residual_guid_bytes_in_Latest_and_ContentDocuments"] == 0


@needs_rungs
@needs_sample
def test_b2024_k4_is_a_2024_file_that_walks_clean():
    from rvt import versions
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    p = os.path.join(RUNGS, "B2024_K4.rvt")
    assert versions.detect_release(p) == 2024
    with versions.reading(p):
        with open_rvt(p) as f:
            w = StreamWalker(f.logical(f.partition_streams()[0]),
                             inflate=False, keep_data=False)
            assert w.errors == []
            assert len(w.units) == 1          # zero embedded family documents


@needs_rungs
def test_k4_census_divergence_from_2025_is_exactly_schema_drift():
    """B2024_K4 vs B2025_K4: any class present in one and absent from the
    other must not EXIST in the other release's schema (the transfer proof:
    the K4 shape is release-invariant modulo the schema's own class set)."""
    p25 = os.path.join(ROOT, "experiments", "genesis2025", "reduce", "B2025_K4.json")
    if not (os.path.exists(p25) and os.path.exists(FACTS)):
        pytest.skip("2025 K4 artifacts or 2024 facts absent")
    c24 = set(_rep("B2024_K4")["census"]["classes"])
    with open(p25) as fh:
        c25 = set(json.load(fh)["census"]["classes"])
    with open(FACTS) as fh:
        cd = json.load(fh)["class_diff_2025_to_2024"]
    assert (c24 - c25) <= set(cd["only_in_2024"])
    assert (c25 - c24) <= set(cd["only_in_2025"])


# ---------------------------------------------------------------------------
# 3. staged batch + format pins
# ---------------------------------------------------------------------------
@needs_rungs
@needs_sample
def test_staged_control_is_byte_identical_to_the_2024_sample():
    ctrl = os.path.join(OUT, "CTRL_rstbasicsampleproject_b28.rvt")
    if not os.path.exists(ctrl):
        pytest.skip("batch not staged")
    assert _md5(ctrl) == _md5(SRC)
    for other in (S25, S26):
        if os.path.exists(other):
            assert _md5(ctrl) != _md5(other)  # the control is the 2024 bytes


@needs_rungs
def test_probes_manifest_declares_resolvable_lineage():
    if not os.path.exists(os.path.join(OUT, "probes.json")):
        pytest.skip("probes.json not written")
    import probe_batch as PB
    expect = {
        "R9_2024": "samples/2024/rstbasicsampleproject.rvt",
        "K3_2024": "experiments/genesis2024/reduce/R9_2024.rvt",
        "B2024_K4": "experiments/genesis2024/reduce/K3_2024.rvt",
    }
    for name, base in expect.items():
        r = PB.resolve_base(os.path.join(RUNGS, f"{name}.rvt"))
        assert r.base == base, f"{name}: resolved {r.base!r}"


@needs_rungs
def test_batch_manifest_number_does_not_collide():
    """Batch numbering must be UNIQUE across every round's on-disk evidence
    (manifests AND CTRL_*_b<n> control names -- rounds 18..27 left controls
    but no manifests).  Not "newest": sibling streams legitimately keep
    staging higher numbers after us (29 and 32..35 landed from the 2025
    fleets), and the uploader stages byte-identical COPIES of a round's
    control in the acceptance dir.  So the guard is the INVARIANT, not a
    snapshot: (1) no number is claimed by two manifests; (2) every control
    claiming OUR number carries OUR control's bytes (a copy is the same
    claim -- different bytes on our number is a real collision); (3) the
    campaign-global allocator (genesis_2024.global_next_batch_number) stays
    strictly above every number on disk, so no round can re-issue one."""
    if not os.path.exists(BATCH):
        pytest.skip("batch not staged")
    import glob
    import re
    import genesis_2024 as G
    with open(BATCH) as fh:
        ours = json.load(fh)
    n = ours["batch"]
    our_ctrl_md5s = {e["md5"] for e in ours["entries"] if e.get("control")}
    assert our_ctrl_md5s, "our manifest must declare >= 1 control"

    manifests = {}                            # number -> [manifest paths]
    controls = {}                             # number -> [control paths]
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "batch_*.json"),
                       recursive=True):
        m = re.match(r"batch_(\d+)\.json$", os.path.basename(p))
        if m:
            manifests.setdefault(int(m.group(1)), []).append(p)
    for p in glob.glob(os.path.join(ROOT, "experiments", "**", "CTRL_*_b*.*"),
                       recursive=True):
        m = re.search(r"_b(\d+)\.[A-Za-z]+$", os.path.basename(p))
        if m:
            controls.setdefault(int(m.group(1)), []).append(p)

    # (1) every number has exactly one manifest, and OUR number is OUR manifest
    dupes = {k: v for k, v in manifests.items() if len(v) > 1}
    assert not dupes, f"batch numbers claimed by more than one manifest: {dupes}"
    assert [os.path.abspath(p) for p in manifests.get(n, [])] \
        == [os.path.abspath(BATCH)]

    # (2) every control claiming our number is a byte-identical copy of OURS
    outsiders = [p for p in controls.get(n, [])
                 if OUT not in os.path.abspath(p) and _md5(p) not in our_ctrl_md5s]
    assert not outsiders, f"batch number {n} also claimed by {outsiders}"

    # (3) the next number can never collide with anything already on disk
    every_number = set(manifests) | set(controls)
    assert G.global_next_batch_number() > max(every_number)


@needs_facts
def test_format_facts_match_the_versions_pins():
    from rvt import versions
    with open(FACTS) as fh:
        facts = json.load(fh)
    fl = facts["formats_latest_2024"]
    rel = versions.KNOWN_RELEASES[2024]
    assert fl["pin_matches_rvt_versions"] is True
    assert fl["size"] == rel.schema_size and fl["sha256"] == rel.schema_sha256
    assert fl["classes"] == rel.class_count == 4492
    assert fl["identical_across_six_samples"] is True
    assert facts["framing_matches_rvt_versions_table"] is True
    es = facts["esschema_corpus_2024"]
    assert es["byte_identical_across_six_samples"] is True
    assert es["total_pairs"] > 1000 and es["total_bytes"] > 800_000


@needs_facts
def test_class_diffs_cover_both_newer_releases():
    with open(FACTS) as fh:
        facts = json.load(fh)
    cd25 = facts["class_diff_2025_to_2024"]
    cd26 = facts["class_diff_2026_to_2024"]
    assert cd25["classes_2025"] == 4600 and cd25["classes_2024"] == 4492
    assert cd26["classes_2026"] == 4690 and cd26["classes_2024"] == 4492
    # names are stable, ordinals drift wholesale (the version model's core)
    assert cd25["renumbered_shared"] > 4000
    assert cd26["renumbered_shared"] > 4000
    # the 2026 conductor catalog is missing from 2024 too (never emit it)
    conductor = {"CustomElement", "NamingCell", "RbsConductorMaterial",
                 "RbsConductorTemperatureRating",
                 "RbsConductorInsulationMaterial", "RbsConductorSize"}
    assert conductor <= set(cd26["only_in_2026"])
    # everything 2026-only vs 2025 is also absent from 2024
    p25facts = os.path.join(ROOT, "experiments", "genesis2025",
                            "format_facts_2025.json")
    if os.path.exists(p25facts):
        with open(p25facts) as fh:
            only26_vs25 = set(json.load(fh)["class_diff_2026_to_2025"]["only_in_2026"])
        assert only26_vs25 <= set(cd26["only_in_2026"])


@needs_facts
def test_esschema_corpus_reference_rows_match_the_2025_stream():
    """The 2025/2026 reference corpora measured by THIS stream's instrument
    must equal the pins the 2025 stream recorded -- two independent runs of
    the same measurement (counsel C4 now names three per-release corpora)."""
    with open(FACTS) as fh:
        es = json.load(fh)["esschema_corpus_2024"]
    p25facts = os.path.join(ROOT, "experiments", "genesis2025",
                            "format_facts_2025.json")
    if not os.path.exists(p25facts):
        pytest.skip("2025 facts absent")
    with open(p25facts) as fh:
        es25 = json.load(fh)["esschema_corpus_2025"]
    assert es["corpus_2025_reference"]["corpus_sha256"] == es25["corpus_sha256"]
    assert es["corpus_2025_reference"]["total_pairs"] == es25["total_pairs"]
    assert es["corpus_2026_reference"]["corpus_sha256"] \
        == es25["corpus_2026_reference"]["corpus_sha256"]
    # and the 2024 corpus is its OWN constant, distinct from both
    assert es["corpus_sha256"] not in (es["corpus_2025_reference"]["corpus_sha256"],
                                       es["corpus_2026_reference"]["corpus_sha256"])


@needs_facts
def test_history_terminal_2662_is_release_stable_not_a_release_marker():
    with open(FACTS) as fh:
        facts = json.load(fh)
    idn = facts["identity_2024"]
    hz = idn["history_upgrade_versions"]
    assert hz["2024_last"] == hz["2025_last"] == hz["2026_last"] == 2662
    assert hz["2024_count"] == hz["2025_count"] == hz["2026_count"] == 190
    assert hz["identical_across_releases"] is True
    # ...because 2662 is the ADocument schema version in ALL three releases
    assert idn["adocument_schema_version"] == {"2024": 2662, "2025": 2662,
                                               "2026": 2662}
    # the release-authoritative marker is BasicFileInfo Format:
    assert idn["basicfileinfo_format"] == "2024"
