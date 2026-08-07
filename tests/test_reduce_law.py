"""Tests for src/rvt/reduce_law.py -- THE REDUCTION LAW folded into code.

The centrepiece is the K1 REGRESSION: the recipe that produced K1
("R5 minus the placed model" via rvt.manipulate's NEUTRALISE pre-pass --
the never-uploaded base whose CRASH cost the campaign a night, ORCHESTRATOR
VERDICTS #15) MUST be rejected by the guard, while K1a_editfree (the same
deletion with ZERO survivor edits, viewer-PASSED in batch 15, VERDICTS #17)
MUST be accepted.  Both files live under experiments/genesis/ (K1a in
autopsy/, K1 in triage/); the tests skip when they are absent.

Also covered: the law's data tables, the generator policy (the neutralise
mechanism is refused for any base purpose and allowed only for research
probes / genuine user modification), the byte-strict element_diff
instrument, the clause classifier on K1's real edit groups, the K3/K4
byte-vindication technique, the in-place substitution law on the certified
Y1 rung, and the sanctioned deletion-with-content seed.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import reduce_law as RL                                   # noqa: E402

GEN = os.path.join(ROOT, "experiments", "genesis")
R5 = os.path.join(GEN, "R5.rvt")
K1 = os.path.join(GEN, "triage", "K1.rvt")
K1A = os.path.join(GEN, "autopsy", "K1a_editfree.rvt")
K3 = os.path.join(GEN, "triage", "K3.rvt")
K4 = os.path.join(GEN, "triage", "K4.rvt")
Y1 = os.path.join(GEN, "subst_k4", "Y1.rvt")

_have_regression_files = all(os.path.exists(p) for p in (R5, K1, K1A))


@pytest.fixture(scope="module")
def docs():
    """Load the three regression documents once (fast: ~0.5 s)."""
    from rvt.mutate import Document
    r5 = Document.from_file(R5)
    k1 = Document.from_file(K1)
    k1a = Document.from_file(K1A)
    r5.name, k1.name, k1a.name = "R5", "K1", "K1a_editfree"
    return {"R5": r5, "K1": k1, "K1a": k1a}


# ---------------------------------------------------------------------------
# 1. the LAW as data
# ---------------------------------------------------------------------------

def test_law_statement_and_five_clauses():
    assert "BYTE-IDENTICAL" in RL.THE_LAW and "DELETED WITH" in RL.THE_LAW
    assert set(RL.CLAUSES) == {1, 2, 3, 4, 5}
    # clause 1 owns the family/type layer; clause 3 the model views
    assert "FamilySymbol" in RL.CLAUSES[1].classes
    assert "FamSymSurrogate" in RL.CLAUSES[1].classes
    assert "DBViewGraphSchedColumn" in RL.CLAUSES[2].classes
    assert "DBView3d" in RL.CLAUSES[3].classes
    assert RL.CLAUSES[4].classes == frozenset()          # the catch-all clause
    assert RL.CLASS_CLAUSE["StairsTriserSymbol"] == 1
    assert RL.CLASS_CLAUSE["LevelRoomPlan"] == 2
    assert RL.CLASS_CLAUSE["DBViewSection"] == 3


def test_sanctioned_and_banned_tables():
    assert "maxgc" in RL.SANCTIONED_GENERATORS
    assert "in-place-substitution" in RL.SANCTIONED_GENERATORS
    assert "registry-reconciliation" in RL.SANCTIONED_GENERATORS
    assert "neutralise-referrers" in RL.BANNED_MECHANISMS
    assert {"neutralise-scalar-null", "neutralise-list-remove",
            "neutralise-struct-drop"} <= set(RL.BANNED_MECHANISMS)
    # no mechanism is both sanctioned and banned
    assert not (set(RL.SANCTIONED_GENERATORS) & set(RL.BANNED_MECHANISMS))
    js = RL.law_policy().to_json()
    assert js["law"] == RL.THE_LAW and set(js["clauses"]) == {1, 2, 3, 4, 5}


# ---------------------------------------------------------------------------
# 2. the policy: which mechanism may emit for which purpose
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("purpose", ["genesis-base", "reduction-rung",
                                     "substitution-base", "candidate-base"])
@pytest.mark.parametrize("mech", ["neutralise-referrers", "neutralise-scalar-null",
                                  "neutralise-list-remove", "neutralise-struct-drop"])
def test_neutralise_is_refused_for_every_base_purpose(mech, purpose):
    dec = RL.law_policy().permits(mech, purpose)
    assert not dec.allowed and not bool(dec)
    assert "BANNED" in dec.reason
    with pytest.raises(RL.BannedGeneratorError) as ei:
        RL.guard_generator(mech, purpose)
    assert ei.value.report is dec or ei.value.report == dec


@pytest.mark.parametrize("mech", ["maxgc", "registry-reconciliation",
                                  "unit-removal-reconciled", "in-place-substitution",
                                  "control-copy"])
def test_sanctioned_generators_allowed_for_genesis_base(mech):
    dec = RL.guard_generator(mech, "genesis-base")
    assert dec.allowed and bool(dec)
    assert "sanctioned" in dec.reason


def test_neutralise_allowed_only_for_research_probes_and_user_edits():
    d = RL.law_policy().permits("neutralise-referrers", "research-probe")
    assert d.allowed and "may NEVER be certified" in d.reason
    assert RL.law_policy().permits("neutralise-scalar-null", "user-modify").allowed
    assert RL.law_policy().permits("neutralise-struct-drop", "diagnostic").allowed


def test_unknown_purpose_and_unknown_base_mechanism_refused():
    assert not RL.law_policy().permits("maxgc", "no-such-purpose").allowed
    d = RL.law_policy().permits("some-new-machinery", "genesis-base")
    assert not d.allowed and "unknown mechanism" in d.reason
    # ...but an unknown mechanism for a non-base purpose is merely noted
    assert RL.law_policy().permits("some-new-machinery", "diagnostic").allowed


def test_purpose_and_mechanism_are_case_insensitive():
    assert not RL.law_policy().permits("Neutralise-Referrers", "GENESIS-BASE").allowed
    assert RL.law_policy().permits("MAXGC", "Genesis-Base").allowed


# ---------------------------------------------------------------------------
# 3. the byte-strict instrument on a document vs itself
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _have_regression_files, reason="genesis corpus (R5) not present")
def test_element_diff_of_identical_documents_is_empty(docs):
    d = RL.element_diff(docs["R5"], docs["R5"])
    assert d.removed == set() and d.added == set() and d.modified == {}
    assert d.common == len(RL._all_ids(docs["R5"]))
    rep = RL.check_reduction(docs["R5"], docs["R5"])
    assert rep.ok and rep.verdict == "EDIT-FREE" and rep.removed == 0
    assert RL.assert_edit_free(docs["R5"], docs["R5"]).ok


def test_record_signature_covers_stamp_class_and_payload():
    class R:                       # a minimal Record stand-in
        def __init__(self, cid, st, sz, pay, ok=True):
            self.class_id, self.stamp, self.body_size, self.payload, self.trailer_ok = cid, st, sz, pay, ok
    a = R(0x1c, 5, 6, b"abcd")
    assert RL.record_signature(a, 102) == RL.record_signature(R(0x1c, 5, 6, b"abcd"), 102)
    assert RL.record_signature(a, 102) != RL.record_signature(R(0x1c, 6, 6, b"abcd"), 102)   # stamp
    assert RL.record_signature(a, 102) != RL.record_signature(R(0x1d, 5, 6, b"abcd"), 102)   # class
    assert RL.record_signature(a, 102) != RL.record_signature(R(0x1c, 5, 6, b"abcX"), 102)   # bytes
    assert RL.record_signature(a, 102) != RL.record_signature(a, 103)                          # seq
    assert RL.record_signature(None, 102) is None


# ---------------------------------------------------------------------------
# 4. THE K1 REGRESSION -- the recipe is REJECTED, its edit-free twin ACCEPTED
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _have_regression_files, reason="genesis corpus (R5/K1/K1a) not present")
def test_editfree_recipe_K1a_is_ACCEPTED(docs):
    """K1a_editfree = R5 minus maxgc(placed model), ZERO survivor edits: the
    corrected recipe.  Viewer-PASSED (VERDICTS #17).  The guard must accept."""
    rep = RL.assert_edit_free(docs["R5"], docs["K1a"],
                              before_label="R5", after_label="K1a_editfree")
    assert rep.ok and rep.verdict == "EDIT-FREE"
    assert rep.removed == 599                      # K1a's certified deletion set size
    assert rep.added == [] and rep.survivors_edited == []
    assert rep.clause_counts == {}
    # non-raising form agrees
    assert RL.check_reduction(docs["R5"], docs["K1a"]).ok


@pytest.mark.skipif(not _have_regression_files, reason="genesis corpus (R5/K1/K1a) not present")
def test_neutralise_recipe_K1_is_REJECTED(docs):
    """K1 = R5 minus the placed model VIA THE NEUTRALISE PRE-PASS
    (genesis_triage.build_K1: neutralise_referrers then maxgc).  It CRASHED
    the reader.  The guard must REJECT it, naming every edited survivor."""
    with pytest.raises(RL.SurvivorEditedError) as ei:
        RL.assert_edit_free(docs["R5"], docs["K1"], before_label="R5", after_label="K1")
    rep = ei.value.report
    assert isinstance(rep, RL.EditFreeReport)
    assert not rep.ok and rep.verdict == "SURVIVORS-EDITED"
    # the autopsy's accounting, byte-record-exact: 2,117 deleted, 23 survivors EDITED
    assert rep.removed == 2117
    assert len(rep.survivors_edited) == 23
    assert rep.added == []
    # no vindication sources given => the vindicated sheet still counts
    assert rep.vindicated == 0
    edited = {e.id: e for e in rep.survivors_edited}
    # every K1 edit group is present and lands in the right clause
    assert edited[876569].clause == 1 and edited[876569].class_name == "FamilySymbol"
    assert edited[876494].clause == 1 and edited[876494].class_name == "FamilySurrogate"
    assert edited[513310].clause == 1                      # StairsTriserSymbol un-hosted
    assert edited[1250040].clause == 2                     # graphical column schedule
    assert edited[1004909].clause == 2                     # LevelRoomPlan topology pruned
    assert edited[1141621].clause == 3                     # DBView3d hidden list pruned
    assert edited[1199134].clause == 3                     # DBViewSection
    assert edited[1457028].clause == 4                     # a sheet (title block -> -1)
    assert set(rep.clause_counts) == {1, 2, 3, 4}
    assert sum(rep.clause_counts.values()) == 23
    # the message names the law
    assert "REDUCTION LAW VIOLATED" in str(ei.value)


@pytest.mark.skipif(not _have_regression_files, reason="genesis corpus (R5/K1) not present")
def test_K1_edit_signatures_are_diagnosed(docs):
    """The classifier's evidence matches the autopsy field-by-field."""
    rep = RL.check_reduction(docs["R5"], docs["K1"])
    edited = {e.id: e for e in rep.survivors_edited}
    # clause 1: the orphaned default FamilySymbol -- m_familyId AND
    # m_ownerInstanceId nulled to -1 in the seq-102 object
    sym = edited[876569]
    assert any("m_familyId" in p for p in sym.nulled_id_leafs)
    assert any("m_ownerInstanceId" in p for p in sym.nulled_id_leafs)
    assert 102 in sym.seqs
    # clause 2: the graphical column schedule -- ALL 27 grid-intersection
    # struct entries DROPPED (27 -> 0) from the seq-102 object
    sched = edited[1250040]
    key = "seq102:m_visGridIntPntArr"
    assert key in sched.dropped_entries and sched.dropped_entries[key] == [27, 0]
    # clause 3: a 3D view's hidden-element list pruned
    v3d = edited[1250103]
    assert any("m_oHiddenElementsViewSettings" in p for p in v3d.dropped_entries)
    # every edit report names the certified alternative (deletion-with-content)
    assert all(e.instead for e in rep.survivors_edited)
    # the report is JSON-serializable and one_line renders
    js = rep.to_json()
    assert js["survivors_edited"] == 23 and len(js["edits"]) == 23
    assert "CLAUSE 1" in sym.one_line()


@pytest.mark.skipif(not (_have_regression_files and os.path.exists(K3) and os.path.exists(K4)),
                    reason="K3/K4 (byte-vindication sources) not present")
def test_byte_vindication_by_the_passing_K3(docs):
    """K1's sheet 1457028 carries its edited record BYTE-IDENTICALLY in the
    viewer-PASSED K3/K4 -- the edit is reader-legal (byte-vindicated), and
    the guard says so when handed the certified sources; the other 22
    edits stay unvindicated so the file is still REJECTED."""
    from rvt.mutate import Document
    k3 = Document.from_file(K3)
    k3.name = "K3"
    k4 = Document.from_file(K4)
    k4.name = "K4"
    rep = RL.check_reduction(docs["R5"], docs["K1"], vindication_sources=[k3, k4])
    edited = {e.id: e for e in rep.survivors_edited}
    sheet = edited[1457028]
    assert sheet.vindicated and set(sheet.vindicated_by) <= {"K3", "K4"}
    assert "K3" in sheet.vindicated_by
    assert rep.vindicated == 1
    assert not rep.ok and rep.verdict == "SURVIVORS-EDITED"
    assert sum(rep.clause_counts.values()) == 22          # 23 - 1 vindicated
    # a direct vindicated_by call agrees
    assert "K3" in RL.vindicated_by(docs["K1"], 1457028, [k3])
    # the orphaned symbol is in NO passing file
    assert RL.vindicated_by(docs["K1"], 876569, [k3, k4]) == []


# ---------------------------------------------------------------------------
# 5. the in-place substitution law (the engine's policy)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not (os.path.exists(K4) and os.path.exists(Y1)),
                    reason="K4 / Y1 (certified in-place rung) not present")
def test_in_place_law_on_the_certified_Y1_rung():
    """Y1 = certified K4 with ONLY the pen-table object (element id 2)
    substituted in place: exactly one seq-102 record differs, nothing is
    added or removed, and the law's assertions read it correctly."""
    from rvt.mutate import Document
    k4 = Document.from_file(K4)
    y1 = Document.from_file(Y1)
    rep = RL.assert_substitution(k4, y1, landed_ids={2})
    assert rep.ok and rep.changed == [2] and rep.stray_changed == []
    assert rep.added == [] and rep.removed == [] and rep.seq_violations == {}
    # the same file with NO declared landed slot => id 2 is a STRAY change
    bad = RL.check_substitution(k4, y1, landed_ids=set())
    assert not bad.ok and bad.stray_changed == [2]
    assert any("beyond the landed slots" in p for p in bad.problems)
    with pytest.raises(RL.InPlaceLawError):
        RL.assert_substitution(k4, y1, landed_ids=set())
    # object-only mode: the change is in seq 102; restricting to (101,) flags it
    seqbad = RL.check_substitution(k4, y1, landed_ids={2}, allow_seqs=(101,))
    assert not seqbad.ok and seqbad.seq_violations == {2: [102]}
    # a landed slot may be byte-identical (Y5's empty-tracker finding):
    # declaring a slot that did not change is NOT a violation
    quiet = RL.check_substitution(k4, y1, landed_ids={2, 1})
    assert quiet.ok and 1 in quiet.unchanged_landed


# ---------------------------------------------------------------------------
# 6. the sanctioned alternative to the neutralise pre-pass
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(R5), reason="R5 not present")
def test_deletion_with_content_seed_returns_the_referrers(docs):
    """Instead of NEUTRALISING the in-place family 'building option'
    (876493)'s referrers, the sanctioned move is to delete them WITH the
    family: the seed must contain its FamilySymbol / surrogates / instance /
    family-scoped sketch content -- and never the target itself."""
    seed = RL.deletion_with_content_seed(docs["R5"], {876493})
    assert 876493 not in seed
    # K1's G4 orphaning group members are referrers of the family
    assert {876494, 876569, 876570} <= seed          # surrogate, symbol, symbol-surrogate
    assert 876571 in seed                             # the placed instance
    r5 = docs["R5"]
    assert r5.class_of(876569) == "FamilySymbol"
    assert r5.class_of(876494) == "FamilySurrogate"
    assert r5.class_of(876570) == "FamSymSurrogate"
    # every returned id is a host-document element
    assert seed <= set(r5.et_by_id)
    # excluding an id removes it from the seed
    seed2 = RL.deletion_with_content_seed(r5, {876493}, exclude={876571})
    assert 876571 not in seed2 and 876569 in seed2


# ---------------------------------------------------------------------------
# 7. the classifier's fallback for classes outside the K1 groups
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _have_regression_files, reason="genesis corpus not present")
def test_ungrouped_class_defaults_to_clause_4(docs):
    """A synthetic edit on a class the K1 groups do not name (a wall) is
    the generic survivor-byte-identity clause 4."""
    r5, k1a = docs["R5"], docs["K1a"]
    # find a surviving SWall (or any wall class) present in both
    walls = [e for e in r5.et_by_id
             if e in k1a.idx[102] and (r5.class_of(e) or "").endswith("Wall")]
    if not walls:
        pytest.skip("no surviving wall in K1a")
    eid = walls[0]
    e = RL.classify_survivor_edit(r5, k1a, eid, [102])
    assert e.clause == 4 and e.clause_slug == "survivors-byte-identical"
