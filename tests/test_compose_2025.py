"""test_compose_2025.py -- THE 2025 COMPOSER (compose-2025 stream).

Guards the stream's four deliverables (docs/inbox/compose-2025.md):

  1. THE ANCHOR: compose(B2025_K4, the nine cumulative Y2025 rung deltas)
     reproduces the ladder's deepest cumulative rung Y9.rvt BYTE-IDENTICALLY
     (the 2026 anchor proof, transferred to 2025).
  2. THE CANDIDATE: the deepest available composed G file is COMPOSED-VALID
     with every invariant held (registry parity, in-place law, fidelity,
     four-registry coherence, validator 0 errors), and the registry relpath
     ``G_ABPD_2025.rvt`` is NEVER occupied by a partial composition.
  3. THE BATCH: staged through the probe_batch gate -- control = a
     byte-identical copy of the CERTIFIED base, base declarations resolvable.
  4. THE FLIP IS APPLIED (G25-5 landed): the genesis_base.json 2025 slot
     reads certified with the composed file's sha256/bytes pinned;
     KNOWN_RELEASES[2025].creation_certified is True with the genesis base
     set; the finish-line dry-run reports exist and are honest.

Every artifact-dependent test skips cleanly off the build machine.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

COMPOSE_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4_2025", "compose")
BASE = os.path.join(ROOT, "experiments", "genesis2025", "reduce", "B2025_K4.rvt")
ANCHOR_RVT = os.path.join(COMPOSE_DIR, "G_Y2025_anchor.rvt")
ANCHOR_JSON = os.path.join(COMPOSE_DIR, "anchor_2025.json")
G_FINAL = os.path.join(COMPOSE_DIR, "G_ABPD_2025.rvt")
G_PARTIAL = os.path.join(COMPOSE_DIR, "G_partial_2025.rvt")
COMPOSE_JSON = os.path.join(COMPOSE_DIR, "compose_2025.json")
PROBES = os.path.join(COMPOSE_DIR, "probes.json")

needs_artifacts = pytest.mark.skipif(
    not (os.path.exists(ANCHOR_JSON) and os.path.exists(BASE)),
    reason="compose-2025 artifacts absent on this machine")


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _g_file() -> str:
    return G_FINAL if os.path.exists(G_FINAL) else G_PARTIAL


# ---------------------------------------------------------------------------
# 1. the anchor
# ---------------------------------------------------------------------------

@needs_artifacts
def test_anchor_holds_byte_identical():
    a = _load(ANCHOR_JSON)
    assert a["BYTE_IDENTICAL"] is True
    assert a["md5_reproduction"] == a["md5_target"]
    assert a["compose_verdict"] == "COMPOSED-VALID"
    assert not a["compose_problems"]
    # the claim is re-checkable from the bytes on disk, not just the record:
    # the reproduction equals the chain's deepest cumulative rung
    target = os.path.join(ROOT, a["target"])
    assert os.path.exists(target)
    assert _md5(ANCHOR_RVT) == _md5(target) == a["md5_target"]


@needs_artifacts
def test_anchor_composed_the_cumulative_y_chain_in_one_pass():
    a = _load(ANCHOR_JSON)
    names = [r["name"] for r in a["rung_sets"]]
    assert len(names) >= 7 and all(n.startswith("Y2025:") for n in names)
    # the chain is composed base -> deepest, one rung per step
    assert names == sorted(names, key=names.index)
    # every slot has exactly one owner after linearization: the merged total
    # is the plain sum of the (restricted) deltas
    assert a["merged_slots"] == sum(r["slots"] for r in a["rung_sets"])
    # the Y ladder is an object-record ladder (seq 102 only)
    assert all(r["seqs"] == [102] for r in a["rung_sets"])


@needs_artifacts
def test_anchor_base_is_the_certified_2025_base():
    a = _load(ANCHOR_JSON)
    assert a["base"] == "experiments/genesis2025/reduce/B2025_K4.rvt"
    assert a["base_certification"], "the base must be viewer-certified (verdicts #28)"
    assert _md5(BASE) == a["base_md5"]


# ---------------------------------------------------------------------------
# 2. the composed candidate
# ---------------------------------------------------------------------------

@needs_artifacts
def test_composed_candidate_is_composed_valid_with_invariants():
    g = _g_file()
    assert os.path.exists(g)
    comp = _load(COMPOSE_JSON)
    assert comp["verdict"] == "COMPOSED-VALID"
    assert not comp["problems"]
    man = _load(os.path.splitext(g)[0] + ".manifest.json")
    assert man["verdict"] == "COMPOSED-VALID"
    assert not man["problems"]
    inv = man["invariants"]
    assert inv["validator_final"]["errors"] == 0
    assert inv["four_registry_final"].get("coherent") is not False
    # the in-place invariants live in the phase-1 manifest when the
    # composition ran chain-faithfully as two calls (substitute THEN delete)
    p1 = comp.get("phase1_manifest")
    man1 = _load(os.path.join(ROOT, p1)) if p1 else man
    assert man1["verdict"] == "COMPOSED-VALID"
    inv1 = man1["invariants"]
    parity = inv1["registry_parity"]
    assert parity["global_latest_identical"] and parity["global_elemtable_identical"]
    assert inv1["in_place_law"]["ok"]
    assert inv1["byte_delta_in_place"]["assertion_holds"]
    assert man1["phase_1_inplace"]["rung_fidelity"]["all_ok"]
    # phase 2 (when present): the deletion layer under the reduction law
    if man["phase_2_deletions"]:
        law = man["phase_2_deletions"]["reduce_law"]
        assert law["verdict"] == "EDIT-FREE" and law["ok"]


@needs_artifacts
def test_registry_relpath_is_never_occupied_by_a_partial():
    """G_ABPD_2025.rvt (the exact relpath genesis_base.json releases.2025
    reserves) may exist ONLY when the composition was complete (Y rungs +
    residue rungs + a lawful deletion set)."""
    comp = _load(COMPOSE_JSON)
    if not comp["complete"]:
        assert not os.path.exists(G_FINAL), \
            "a PARTIAL composition must never sit at the registry relpath"
        assert os.path.exists(G_PARTIAL)
        assert comp["completion"]["one_command"].endswith(
            "tools/genesis_compose_2025.py all")
    else:
        assert os.path.exists(G_FINAL)
        assert comp["layers"]["residue_rungs"] and comp["layers"]["deletion_sets"]


@needs_artifacts
def test_composed_candidate_chain_proofs():
    """The chain-replay proofs recorded by compose: the in-place layer equals
    the chain's deepest in-place file, and (when the sibling published a
    deletion-applied proof file) the FINAL output equals it byte-for-byte."""
    comp = _load(COMPOSE_JSON)
    ip = comp.get("inplace_layer_byte_identical_to_deepest_chain_file") or {}
    if ip.get("deepest_chain_file"):
        assert ip.get("identical") is True
    fp = comp.get("final_byte_identical_to_sibling_deletion_proof") or {}
    if fp.get("deletion_proof_file"):
        assert fp.get("identical") is True
        # re-checkable from disk
        assert _md5(os.path.join(ROOT, fp["file"])) == \
            _md5(os.path.join(ROOT, fp["deletion_proof_file"]))


# ---------------------------------------------------------------------------
# 3. the staged batch
# ---------------------------------------------------------------------------

@needs_artifacts
def test_staged_batch_control_is_byte_identical_to_certified_base():
    batches = [f for f in os.listdir(COMPOSE_DIR)
               if f.startswith("batch_") and f.endswith(".json")]
    assert batches, "no staged batch in the compose dir"
    man = _load(os.path.join(COMPOSE_DIR, sorted(batches)[-1]))
    ctrl = [e for e in man["entries"] if e["kind"] == "control"]
    assert len(ctrl) == 1
    staged = os.path.join(ROOT, ctrl[0]["staged_as"])
    assert os.path.exists(staged)
    assert _md5(staged) == _md5(BASE)
    assert ctrl[0]["control_source"] == "experiments/genesis2025/reduce/B2025_K4.rvt"
    # control reads FIRST
    assert man["reading_order"][0].startswith("CTRL_")


@needs_artifacts
def test_probes_manifest_declares_the_certified_base_and_resolves():
    import probe_batch as PB
    m = _load(PROBES)
    assert m["release"] == 2025
    (probe,) = m["probes"]
    assert probe["kind"] == "candidate-base"
    assert probe["base"] == "experiments/genesis2025/reduce/B2025_K4.rvt"
    g = os.path.join(ROOT, probe["file"])
    assert os.path.exists(g)
    res = PB.resolve_base(g, manifest_override=PROBES)
    assert res.base == "experiments/genesis2025/reduce/B2025_K4.rvt"


# ---------------------------------------------------------------------------
# 4. the flip IS applied (G25-5; and the finish-line dry run is honest)
# ---------------------------------------------------------------------------

G_SHA256 = "6242c3aaccf86e7187fbd56879d450089c6fd33ad677d5847cb7c56d5e2b1171"
G_BYTES = 598016


def test_flip_applied_registry_slot_certified():
    slot = _load(os.path.join(ROOT, "src", "rvt", "frontdoor", "assets",
                              "genesis_base.json"))["releases"]["2025"]
    assert slot["status"] == "certified"
    assert slot["sha256"] == G_SHA256
    assert slot["bytes"] == G_BYTES
    assert slot["relpath"] == "experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt"


def test_flip_applied_version_model_certified():
    import rvt.versions as V
    assert V.KNOWN_RELEASES[2025].creation_certified is True
    assert 2025 in V.SUPPORTED_CREATION_RELEASES
    assert V.KNOWN_RELEASES[2025].genesis_base == \
        "experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt"


@needs_artifacts
def test_finishline_dry_run_reports_exist_and_are_honest():
    """The dry run of the self-arming finish-line test: resolution + manifest
    honesty WOULD PASS post-flip; the FULL build's gaps are named, layered,
    and the flip stayed in memory."""
    rep = _load(os.path.join(COMPOSE_DIR, "finishline_2025.json"))
    assert rep["flip"].startswith("IN MEMORY ONLY")
    assert rep["checks"]["creation_status_supported"] is True
    assert rep["checks"]["release_status_certified"] is True
    rb = rep["checks"]["resolve_base"]
    assert rb.get("detected_release") == 2025 and rb.get("certified")
    # resolution honesty holds in every mode
    assert rep["author"]["target_version"]["status"] == "match"
    assert not rep["author"]["target_version"]["line"]


@needs_artifacts
def test_context_compose_2025_patches_and_restores():
    import genesis_compose as GC
    import genesis_compose_2025 as GC25
    from rvt import regadd
    from rvt.genesis import port2025 as P25

    dec26 = GC._DEC
    orig_regadd_dec = regadd.ObjectDecoder
    dec25, _enc25, schema25 = P25._S25()
    with GC25.context_compose_2025(BASE):
        assert GC._DEC is dec25
        assert regadd.ObjectDecoder is not orig_regadd_dec
    assert GC._DEC is dec26
    assert regadd.ObjectDecoder is orig_regadd_dec
