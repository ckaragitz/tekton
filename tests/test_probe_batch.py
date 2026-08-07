"""tests/test_probe_batch.py -- THE STANDING-CONTROLS GATE (genesis-discipline).

What the gate must make impossible (docs/inbox/genesis-audit.md, ORCHESTRATOR
VERDICTS #15 -- the K1 retraction):
  * a probe whose declared BASE is not itself viewer-certified reaching the
    viewer -- 'derived from a certified file' and the manifest's own
    "(viewer PASS)" prose do NOT count; only docs/coverage/viewer-certified.json;
  * a batch without a certified CONTROL (a byte-identical, renamed copy of a
    certified file);
  * a round read out in the wrong order: control FAILED => the whole round is
    VOID; control passed but a base uncertified => refuse and demand the base;
    only then attribute a probe's FAIL to its own change.
Tiers: (1) the gate refusals, hermetic (tmp ledger + tmp manifests);
(2) staging + the CTRL_ copy; (3) read_batch_verdicts branches; (4) the retro
replay of the recorded history (K1 lineage VOID, KD1/K4 SURVIVE, one round in
fourteen carried a deliberate control); (5) base resolution against the real
corpus manifests (skipped when the corpus is absent).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import probe_batch as PB                                          # noqa: E402


# ---------------------------------------------------------------------------
# hermetic fixtures: a tmp "corpus" of tiny .rvt files, a ledger, manifests
# ---------------------------------------------------------------------------
def _write(path, data=b"RVT!"):
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def _ledger(path, certified=(), failed=()):
    doc = {"description": "test ledger",
           "certified": [{"file": PB.rel(f), "proves": "test-certified"} for f in certified],
           "failed": [{"file": PB.rel(f), "verdict": "PROCESSING FAILED", "when": "~t",
                       "note": "test-failed"} for f in failed]}
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1)
    return PB.Ledger.load(path)


@pytest.fixture
def corpus(tmp_path):
    """Files: BASE_OK (certified), BASE_FAIL (failed), BASE_NEW (unknown);
    probes P_ok (base BASE_OK), P_bad (base BASE_NEW), P_onfail (base
    BASE_FAIL), P_prose (base BASE_NEW but manifest CLAIMS '(viewer PASS)'),
    P_undeclared (no entry), P_nobase (entry declares no base)."""
    d = tmp_path
    files = {}
    for name, content in [("BASE_OK.rvt", b"certified-bytes-0123456789"),
                          ("BASE_FAIL.rvt", b"failed-bytes"),
                          ("BASE_NEW.rvt", b"new-bytes"),
                          ("P_ok.rvt", b"pok"), ("P_bad.rvt", b"pbad"),
                          ("P_onfail.rvt", b"ponfail"), ("P_prose.rvt", b"pprose"),
                          ("P_undeclared.rvt", b"pund"), ("P_nobase.rvt", b"pnob"),
                          ("CAND.rvt", b"cand")]:
        files[name] = _write(str(d / name), content)
    manifest = {
        "stream": "test-stream",
        "base": None,
        "probes": [
            {"file": files["P_ok.rvt"], "derived_from": files["BASE_OK.rvt"]},
            {"file": files["P_bad.rvt"], "base": files["BASE_NEW.rvt"]},
            {"file": files["P_onfail.rvt"], "derived_from": files["BASE_FAIL.rvt"] + " (its parent)"},
            {"file": files["P_prose.rvt"],
             "derived_from": files["BASE_NEW.rvt"] + " (viewer PASS -- the manifest CLAIMS)"},
            {"file": files["P_nobase.rvt"], "tests_one_thing": "declares no base at all"},
        ]}
    man_path = str(d / "probes.json")
    with open(man_path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    ledger = _ledger(str(d / "viewer-certified.json"),
                     certified=[files["BASE_OK.rvt"]], failed=[files["BASE_FAIL.rvt"]])
    return {"dir": d, "files": files, "manifest": man_path, "ledger": ledger}


# ---------------------------------------------------------------------------
# tier 1: the gate refusals
# ---------------------------------------------------------------------------
def test_gate_admits_probe_on_certified_base(corpus):
    ents, viol = PB.check_batch([corpus["files"]["P_ok.rvt"]], corpus["ledger"],
                                manifest_override=corpus["manifest"])
    assert viol == []
    assert ents[0].base.base == PB.rel(corpus["files"]["BASE_OK.rvt"])
    assert ents[0].base_status == "certified"


def test_gate_refuses_uncertified_base(corpus):
    ents, viol = PB.check_batch([corpus["files"]["P_bad.rvt"]], corpus["ledger"],
                                manifest_override=corpus["manifest"])
    assert len(viol) == 1
    assert "NOT in docs/coverage/viewer-certified.json" in viol[0]
    assert PB.rel(corpus["files"]["BASE_NEW.rvt"]) in viol[0]     # the exact violation names the base


def test_gate_refuses_probe_on_a_recorded_failure(corpus):
    ents, viol = PB.check_batch([corpus["files"]["P_onfail.rvt"]], corpus["ledger"],
                                manifest_override=corpus["manifest"])
    assert len(viol) == 1 and "RECORDED VIEWER FAILURE" in viol[0]


def test_gate_ignores_the_manifests_viewer_PASS_prose(corpus):
    """'(viewer PASS)' written inside a probes.json is prose, not evidence:
    only the LEDGER certifies. BASE_NEW is not in the ledger => refused."""
    br = PB.resolve_base(corpus["files"]["P_prose.rvt"], corpus["manifest"])
    assert br.base == PB.rel(corpus["files"]["BASE_NEW.rvt"])
    assert "viewer PASS" in (br.raw or "")
    ents, viol = PB.check_batch([corpus["files"]["P_prose.rvt"]], corpus["ledger"],
                                manifest_override=corpus["manifest"])
    assert len(viol) == 1 and "prose is not evidence" in viol[0]


def test_gate_refuses_undeclared_lineage(corpus):
    # no manifest entry at all
    ents, viol = PB.check_batch([corpus["files"]["P_undeclared.rvt"]], corpus["ledger"],
                                manifest_override=corpus["manifest"])
    assert len(viol) == 1 and "NO DECLARED BASE" in viol[0]
    # an entry that declares no base
    ents2, viol2 = PB.check_batch([corpus["files"]["P_nobase.rvt"]], corpus["ledger"],
                                  manifest_override=corpus["manifest"])
    assert len(viol2) == 1 and "NO DECLARED BASE" in viol2[0]


def test_gate_reports_every_violation_at_once(corpus):
    ents, viol = PB.check_batch([corpus["files"]["P_ok.rvt"], corpus["files"]["P_bad.rvt"],
                                 corpus["files"]["P_onfail.rvt"], corpus["files"]["P_prose.rvt"]],
                                corpus["ledger"], manifest_override=corpus["manifest"])
    assert len(viol) == 3                                          # P_ok is fine; the other three


def test_candidate_base_needs_no_certified_base_but_is_warned(corpus):
    ents, viol = PB.check_batch([], corpus["ledger"],
                                candidate_bases=[corpus["files"]["P_onfail.rvt"]],
                                manifest_override=corpus["manifest"])
    assert viol == []                                              # exempt from the rule ...
    assert ents[0].kind == "candidate-base"
    assert ents[0].advisory and "RECORDED FAILURE" in ents[0].advisory   # ... but warned


def test_missing_file_is_a_violation(corpus):
    ents, viol = PB.check_batch([str(corpus["dir"] / "ghost.rvt")], corpus["ledger"],
                                manifest_override=corpus["manifest"])
    assert viol and "does not exist" in viol[0]


# ---------------------------------------------------------------------------
# tier 2: staging + the certified CONTROL copy
# ---------------------------------------------------------------------------
def test_stage_refuses_and_stages_nothing(corpus, tmp_path):
    out = tmp_path / "acc"
    with pytest.raises(PB.GateRefusal) as ei:
        PB.stage_batch([corpus["files"]["P_bad.rvt"]], out_dir=str(out),
                       ledger=corpus["ledger"], manifest_override=corpus["manifest"])
    assert "NOT in docs/coverage/viewer-certified.json" in str(ei.value)
    assert not out.exists() or not list(out.glob("batch_*.json"))    # no manifest written


def test_stage_generates_the_control_and_the_manifest(corpus, tmp_path):
    out = tmp_path / "acc"
    man = PB.stage_batch([corpus["files"]["P_ok.rvt"]], out_dir=str(out),
                         ledger=corpus["ledger"], manifest_override=corpus["manifest"],
                         note="tier2")
    assert man["batch"] == PB.HISTORICAL_ROUNDS + 1        # continues after rounds 1..14
    assert man["control_count"] == 1
    entries = man["entries"]
    assert entries[0]["kind"] == "control" and entries[0]["order"] == 0   # control FIRST
    assert entries[1]["kind"] == "probe"
    ctrl = entries[0]
    assert os.path.basename(ctrl["file"]).startswith(PB.CONTROL_PREFIX)  # CTRL_ prefix
    assert f"_b{man['batch']}" in os.path.basename(ctrl["file"])         # batch tag defeats dedupe
    assert ctrl["control_source"] == PB.rel(corpus["files"]["BASE_OK.rvt"])
    # BYTE-IDENTICAL: the copy's md5 == the certified source's md5
    assert ctrl["md5"] == PB.md5_of(corpus["files"]["BASE_OK.rvt"])
    with open(os.path.join(str(out), os.path.basename(ctrl["file"])), "rb") as fh:
        assert fh.read() == b"certified-bytes-0123456789"
    # the probe entry records base + certification
    pe = entries[1]
    assert pe["base"] == PB.rel(corpus["files"]["BASE_OK.rvt"])
    assert pe["base_status"] == "certified"
    assert pe["base_certification"] == "test-certified"
    assert pe["md5"] == PB.md5_of(corpus["files"]["P_ok.rvt"])
    # the manifest is on disk and the probe was copied next to it
    assert (out / f"batch_{man['batch']}.json").exists()
    assert (out / "P_ok.rvt").exists()
    assert man["reading_order"][0].startswith(PB.CONTROL_PREFIX)


def test_batch_numbers_increment(corpus, tmp_path):
    out = tmp_path / "acc"
    m1 = PB.stage_batch([corpus["files"]["P_ok.rvt"]], out_dir=str(out), ledger=corpus["ledger"],
                        manifest_override=corpus["manifest"])
    m2 = PB.stage_batch([corpus["files"]["P_ok.rvt"]], out_dir=str(out), ledger=corpus["ledger"],
                        manifest_override=corpus["manifest"])
    n = PB.HISTORICAL_ROUNDS
    assert (m1["batch"], m2["batch"]) == (n + 1, n + 2)
    assert (out / f"batch_{n + 1}.json").exists() and (out / f"batch_{n + 2}.json").exists()


def test_control_source_must_be_certified(corpus, tmp_path):
    with pytest.raises(PB.GateRefusal):
        PB.make_control(corpus["ledger"], 1, str(tmp_path / "acc"),
                        source=corpus["files"]["BASE_NEW.rvt"])
    with pytest.raises(PB.GateRefusal):
        PB.make_control(corpus["ledger"], 1, str(tmp_path / "acc"),
                        source=corpus["files"]["BASE_FAIL.rvt"])


def test_stage_refuses_to_overwrite_a_different_staged_file(corpus, tmp_path):
    out = tmp_path / "acc"
    out.mkdir()
    _write(str(out / "P_ok.rvt"), b"DIFFERENT bytes already staged under this name")
    with pytest.raises(PB.GateRefusal) as ei:
        PB.stage_batch([corpus["files"]["P_ok.rvt"]], out_dir=str(out),
                       ledger=corpus["ledger"], manifest_override=corpus["manifest"])
    assert "DIFFERENT file already sits" in str(ei.value)


# ---------------------------------------------------------------------------
# tier 3: read_batch_verdicts -- the only safe reading order
# ---------------------------------------------------------------------------
@pytest.fixture
def staged(corpus, tmp_path):
    out = tmp_path / "acc"
    man = PB.stage_batch([corpus["files"]["P_ok.rvt"]], out_dir=str(out),
                         candidate_bases=[corpus["files"]["CAND.rvt"]],
                         ledger=corpus["ledger"], manifest_override=corpus["manifest"])
    ctrl_name = os.path.basename(man["entries"][0]["file"])
    return {"man": man, "ctrl": ctrl_name, "corpus": corpus}


def test_control_failed_voids_every_verdict(staged):
    res = PB.read_batch_verdicts(staged["man"], {staged["ctrl"]: "PROCESSING FAILED",
                                                 "P_ok.rvt": "FAIL", "CAND.rvt": "PASS"},
                                 ledger=staged["corpus"]["ledger"])
    assert res["status"] == "VOID_ROUND"
    assert res["control_results"][0]["verdict"] == "FAIL"
    assert res["per_file"] and all("VOID" in p["reading"] for p in res["per_file"])
    assert res["ledger_updates"] == {"certified": [], "failed": []}     # nothing enters the ledger
    assert any("pause" in a for a in res["actions"])


def test_control_pending_makes_the_round_incomplete(staged):
    res = PB.read_batch_verdicts(staged["man"], {"P_ok.rvt": "FAIL"},
                                 ledger=staged["corpus"]["ledger"])
    assert res["status"] == "INCOMPLETE"
    assert all("PENDING" in p["reading"] for p in res["per_file"])


def test_control_pass_then_attribution(staged):
    res = PB.read_batch_verdicts(staged["man"], {staged["ctrl"]: "TRANSLATION SUCCESS",
                                                 "P_ok.rvt": "PROCESSING FAILED",
                                                 "CAND.rvt": "PASS"},
                                 ledger=staged["corpus"]["ledger"])
    assert res["status"] == "INTERPRETED"
    kinds = {os.path.basename(p["file"]): p for p in res["per_file"]}
    assert "ATTRIBUTED FAIL" in kinds["P_ok.rvt"]["reading"]         # real, attributable
    assert kinds["CAND.rvt"]["reading"].startswith("CERTIFIED")     # candidate-base certified
    # ledger suggestions: the candidate joins 'certified', the probe joins 'failed' as SOUND
    assert any(u["file"].endswith("CAND.rvt") for u in res["ledger_updates"]["certified"])
    assert any("SOUND finding" in u["note"] for u in res["ledger_updates"]["failed"])


def test_control_pass_but_uncertified_base_is_refused(corpus, tmp_path):
    """A hand-built manifest whose probe sits on an uncertified base: the
    interpreter refuses and demands the base be uploaded first."""
    man = {"batch": 9, "entries": [
        {"order": 0, "file": "x/CTRL_BASE_OK_b9.rvt", "kind": "control", "control": True,
         "control_source": PB.rel(corpus["files"]["BASE_OK.rvt"])},
        {"order": 1, "file": PB.rel(corpus["files"]["P_bad.rvt"]), "kind": "probe",
         "base": PB.rel(corpus["files"]["BASE_NEW.rvt"])}]}
    res = PB.read_batch_verdicts(man, {"CTRL_BASE_OK_b9.rvt": "PASS", "P_bad.rvt": "FAIL"},
                                 ledger=corpus["ledger"])
    assert res["status"] == "REFUSED_UNCERTIFIED_BASE"
    assert "REFUSED" in res["per_file"][0]["reading"]
    assert any("candidate-base first" in a for a in res["actions"])


def test_round_without_a_control_is_refused_by_the_reader(corpus):
    man = {"batch": 7, "entries": [
        {"order": 0, "file": PB.rel(corpus["files"]["P_ok.rvt"]), "kind": "probe",
         "base": PB.rel(corpus["files"]["BASE_OK.rvt"])}]}
    res = PB.read_batch_verdicts(man, {"P_ok.rvt": "FAIL"}, ledger=corpus["ledger"])
    assert res["status"] == "REFUSED_NO_CONTROL"
    assert "UNGUARDED" in res["per_file"][0]["reading"]


def test_verdict_normalisation():
    assert PB.normalise_verdict("PASS") == "PASS"
    assert PB.normalise_verdict("TRANSLATION SUCCESS") == "PASS"
    assert PB.normalise_verdict("PROCESSING FAILED") == "FAIL"
    assert PB.normalise_verdict("TranslationWorker-InternalFailure exit code -1073741831") == "FAIL"
    assert PB.normalise_verdict("Revit-DocumentCorruption") == "FAIL"
    assert PB.normalise_verdict(None) == "PENDING"
    assert PB.normalise_verdict("") == "PENDING"
    assert PB.normalise_verdict(True) == "PASS" and PB.normalise_verdict(False) == "FAIL"


# ---------------------------------------------------------------------------
# tier 4: the retro replay of the recorded history
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def retro():
    rows = PB.classify_history()
    return {"rows": rows, "summary": PB.history_summary(rows),
            "by_file": {os.path.basename(r["file"]): r for r in rows}}


def test_retro_every_K1_lineage_failure_is_void(retro):
    k1 = PB.rel(PB.K1)
    k1_rows = [r for r in retro["rows"] if r["verdict"] == "FAIL" and r["base"] == k1]
    assert len(k1_rows) >= 12                                       # X0.., X1, K5/K6, XR0, XA2, P_*
    assert all(r["class"] == "VOID" for r in k1_rows)


def test_retro_bug_a_verdicts_are_void(retro):
    """'settings singletons required' (K5) and 'style catalog required' (K6)
    -- verdict #6's Bug A -- rest on the never-certified K1: VOID."""
    for f in ("K5.rvt", "K6.rvt", "K5a.rvt", "K5d.rvt", "S1.rvt", "S3.rvt", "S4.rvt", "S5.rvt",
              "R1.rvt", "R2.rvt", "R3.rvt", "X0.rvt", "C0.rvt", "X1.rvt", "X_pen.rvt", "X_cat.rvt",
              "X0k.rvt", "XR0.rvt", "XA2.rvt", "G1_candidate.rvt", "G1a.rvt", "G1b.rvt"):
        assert retro["by_file"][f]["class"] == "VOID", f


def test_retro_survivors(retro):
    for f in ("KD1.rvt", "K4.rvt", "K3.rvt", "R5.rvt", "R9.rvt", "R5s.rvt",
              "L1a_rstbasic_loaded_levelhead.rvt", "T_conduit_types.rvt",
              "V32_own_dit_usernames.rvt", "CTRL_L1a_recheck.rvt", "CTRL_R9_recheck.rvt"):
        assert retro["by_file"][f]["class"] == "SURVIVES", f


def test_retro_R9b_is_the_one_sound_failure(retro):
    r = retro["by_file"]["R9b.rvt"]
    assert r["class"] == "SOUND"
    assert "CONFIRMED" in (r["later"] or "")
    fails = [x for x in retro["rows"] if x["verdict"] == "FAIL"]
    assert sum(1 for x in fails if x["class"] == "SOUND") == 1


def test_retro_G0_and_R10b_are_void_by_uncertified_ladder(retro):
    assert retro["by_file"]["G0.rvt"]["class"] == "VOID"
    assert retro["by_file"]["R10b.rvt"]["class"] == "VOID"
    assert "REFUTED" in retro["by_file"]["G0.rvt"]["later"]           # the dangling-id suspect


def test_retro_K1_itself_reads_unguarded_with_a_certified_base(retro):
    r = retro["by_file"]["K1.rvt"]
    assert r["class"] == "UNGUARDED"
    assert r["base"].endswith("R5.rvt") and r["base_status_at_verdict"] == "certified"


def test_retro_only_one_round_of_fourteen_carried_a_deliberate_control(retro):
    s = retro["summary"]
    assert s["rounds"] == 14
    assert s["rounds_with_deliberate_certified_control"] == [12]
    assert s["fail_rounds_with_no_pass"] == [4, 7, 8, 9, 10, 11, 13, 14]
    assert s["fails"] == 35 and s["fails_by_class"]["VOID"] == 31
    assert s["fails_by_class"]["SOUND"] == 1 and s["fails_by_class"]["UNGUARDED"] == 3


def test_retro_render_and_json_are_stable(retro):
    md = PB.render_history(retro["rows"])
    assert md.count("\n") >= 46 and "**VOID**" in md and "**SOUND**" in md
    assert json.loads(json.dumps({"rows": retro["rows"], "summary": retro["summary"]}))


# ---------------------------------------------------------------------------
# tier 5: base resolution against the real corpus manifests
# ---------------------------------------------------------------------------
def _need(path):
    if not os.path.exists(os.path.join(ROOT, path)):
        pytest.skip(f"{path} not present")


def test_resolve_derived_from_convention():
    _need("experiments/genesis/controls/probes.json"); _need("experiments/genesis/controls/X0.rvt")
    br = PB.resolve_base("experiments/genesis/controls/X0.rvt")
    assert br.base == "experiments/genesis/triage/K1.rvt"
    assert "derived_from" in br.source


def test_resolve_template_convention_via_reference_files():
    _need("experiments/genesis/addpath/probes.json"); _need("experiments/genesis/addpath/P_ep_only.rvt")
    assert PB.resolve_base("experiments/genesis/addpath/P_ep_only.rvt").base == \
        "experiments/genesis/triage/K1.rvt"
    _need("experiments/genesis/addpath/P_ep.rvt")
    assert PB.resolve_base("experiments/genesis/addpath/P_ep.rvt").base == \
        "experiments/genesis/controls/X0.rvt"                          # template X0, not K1


def test_resolve_certified_base_is_admitted():
    _need("experiments/genesis/triage/probes.json"); _need("experiments/genesis/triage/KD1.rvt")
    br = PB.resolve_base("experiments/genesis/triage/KD1.rvt")
    assert br.base == "experiments/genesis/R9.rvt"
    st, _e = PB.Ledger.load().status(br.base)
    assert st == "certified"
    _e2, viol = PB.check_batch(["experiments/genesis/triage/KD1.rvt"])
    assert viol == []                                              # KD1 sits on a certified base


def test_resolve_sample_base_is_admitted():
    _need("experiments/genesis/loader/probes.json")
    _need("experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt")
    br = PB.resolve_base("experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt")
    assert br.base == "samples/rstbasicsampleproject.rvt"
    st, _e = PB.Ledger.load().status(br.base)
    assert st in ("sample", "certified")


def test_resolve_bare_filename_fallback_and_symbolic_base():
    _need("experiments/genesis/subst_v2/probes.json"); _need("experiments/genesis/subst_v2/X_pen.rvt")
    assert PB.resolve_base("experiments/genesis/subst_v2/X_pen.rvt").base == \
        "experiments/genesis/triage/K1.rvt"                              # 'K1.rvt' bare name resolved
    _need("experiments/genesis/latest/probes/manifest.json")
    _need("experiments/genesis/latest/probes/P4_ids_null.rvt")
    assert PB.resolve_base("experiments/genesis/latest/probes/P4_ids_null.rvt").base == \
        "samples/rstbasicsampleproject.rvt"                              # symbolic base 'rst'


def test_the_real_K1_lineage_is_refused_today():
    """The exact batches of 08-04 could not be staged now: every K1-derived
    probe declares K1, which the ledger records as FAILED."""
    _need("experiments/genesis/addpath/P_ep_only.rvt"); _need("experiments/genesis/controls/X0.rvt")
    _e, viol = PB.check_batch(["experiments/genesis/addpath/P_ep_only.rvt",
                               "experiments/genesis/controls/X0.rvt"])
    assert len(viol) == 2 and all("K1.rvt" in v for v in viol)


def test_real_control_generation_is_byte_identical(tmp_path):
    _need("docs/coverage/viewer-certified.json")
    ledger = PB.Ledger.load()
    src = ledger.newest_certified_on_disk(max_bytes=8 << 20)
    if not src:
        pytest.skip("no certified file <= 8 MB on disk")
    e = PB.make_control(ledger, 42, str(tmp_path), source=src)
    assert os.path.basename(e.file).startswith("CTRL_") and e.file.endswith("_b42.rvt")
    assert e.md5 == PB.md5_of(os.path.join(ROOT, src))                 # byte-identical
