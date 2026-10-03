"""#984 -- every certified file the matrix cites whose content WE generated is
either registered as an earlier FORM of what a generator emits today (and
fingerprinted), or declared MECHANISM-ONLY; every row citing it says which.

#981 built the guard for the IFC downlight only.  This module extends it to
the rest of the inventory (record: ``docs/inbox/perm-matrix.d/
984-evidence-registry.md``):

* ``stage_L8_lp4.rvt`` -- eight catalog / house families our constructors
  still emit, cited by rows that implied today's constructor output is what
  the ledger certifies -> registered (``recipe='family_set'``), and its
  caveat also states verdict #25's retraction (an empty-design translation:
  no walls, no placed instance);
* ``ROOM2025_walls.rvt`` -- the 2025 prompt route's walls-only output, cited
  by plugin/docs/HONEST-STATUS.md -> registered (``recipe='author'``), the
  one entry whose certified fingerprint the ledger itself records;
* L1a, the 2500a walls-only shell, RSOLID, W1, V23, V25, V26 -> mechanism
  only: no row claims their form and most cannot be rebuilt on a fresh clone.

What this can NOT prove (hard rule 4): a fingerprint match says the bytes
are the ones the wording was reviewed against, never that Revit opens them.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

from rvt.frontdoor import matrix as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L8 = "experiments/ifc_room/stage_L8_lp4.rvt"
R25 = "experiments/frontdoor2025/room_walls/ROOM2025_walls.rvt"
DOWNLIGHT = "experiments/families/ifc/L_downlight_loaded.rvt"
DOCS = (os.path.join(ROOT, "docs", "product", "PERMUTATION-MATRIX.md"),
        os.path.join(ROOT, "plugin", "docs", "HONEST-STATUS.md"))
BASES = {2026: os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt"),
         2025: os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt")}

#: the #984 inventory decision for EVERY certified file the machine matrix
#: cites: 'form' (registered, fingerprinted), 'mechanism' (caveated, not
#: fingerprinted) or 'none' (no content we generated is what the row cites:
#: edits of existing elements, Revit-born / embedded-born families).  A new
#: certified citation fails here until someone decides which it is.
INVENTORY = {
    "experiments/families/ifc/L_downlight_loaded.rvt": "form",
    "experiments/ifc_room/stage_L8_lp4.rvt": "form",
    "experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt": "mechanism",
    "experiments/ifc_room/electrical_room_2500a_walls_only.rvt": "mechanism",
    "experiments/render/RSOLID_walls_A_solid.rvt": "mechanism",
    "experiments/acceptance/V23_electrical_room.rvt": "mechanism",
    "experiments/acceptance/V25_room_from_ifc.rvt": "mechanism",
    "experiments/acceptance/V26_room_from_ifc_with_walls.rvt": "mechanism",
    "experiments/manipulate/M2_delete_cascade.rvt": "none",
    "experiments/manipulate/M2_delete_cascade_rac.rvt": "none",
    "experiments/manipulate/M3_modify.rvt": "none",
    "experiments/manipulate/M4_move_retype.rvt": "none",
    "experiments/rftprobe/T2a.rvt": "none",
    "experiments/species/TB0g.rvt": "none",
}


def _ledger():
    with open(os.path.join(ROOT, M.LEDGER_RELPATH), encoding="utf-8") as fh:
        return json.load(fh)


def _rows():
    """Every (where, text, evidence) row of the machine matrix."""
    out = [(f"stage {s.id}", s.does, s.evidence) for s in M.STAGES.values()]
    out += [(f"cell {'+'.join(c.inputs)}->{c.output}", "\n".join(c.caveats), c.evidence)
            for c in M.all_cells()]
    out += [(f"chain {n}", str(ch.get("note") or ""), ch.get("evidence", ()))
            for n, ch in M.CHAINS.items()]
    return out


def _cited():
    return {ref.split(":", 1)[1] for _, _, ev in _rows() for ref in ev
            if ref.startswith("certified:")}


# ---------------------------------------------------------------------------
# static: the inventory, the registries, the wording
# ---------------------------------------------------------------------------

def test_every_certified_citation_has_an_inventory_decision():
    assert _cited() == set(INVENTORY), sorted(_cited() ^ set(INVENTORY))


def test_the_registries_match_the_inventory_and_the_ledger():
    certified = {e.get("file") for e in _ledger().get("certified", [])}
    assert not set(M.EVIDENCE_FORMS) & set(M.EVIDENCE_MECHANISMS)
    for path, kind in INVENTORY.items():
        assert (path in M.EVIDENCE_FORMS) == (kind == "form"), path
        assert (path in M.EVIDENCE_MECHANISMS) == (kind == "mechanism"), path
    for path in list(M.EVIDENCE_FORMS) + list(M.EVIDENCE_MECHANISMS):
        assert path in certified, path
    # registered beyond the matrix's own citations: files only the docs cite
    assert R25 in M.EVIDENCE_FORMS
    assert "experiments/render/g12/W1_gabpd_wall_solid.rvt" in M.EVIDENCE_MECHANISMS


def test_every_registered_form_is_earlier_and_every_entry_needs_its_caveat():
    for path, ent in M.EVIDENCE_FORMS.items():
        assert M.evidence_form_is_earlier(path), path
        assert M.required_caveat(path) == ent["caveat"]
        assert ent["caveat"].startswith("EARLIER FORM ("), path
        assert ent["recipe"] in ("downlight", "family_set", "author"), path
    for path, ent in M.EVIDENCE_MECHANISMS.items():
        assert M.required_caveat(path) == ent["caveat"]
        assert "MECHANISM ONLY (#984)" in ent["caveat"], path
        assert ent["built_by"] and ent["why"] and ent["content"], path
    assert M.required_caveat("experiments/rftprobe/T2a.rvt") is None


def test_every_citing_row_carries_its_caveat():
    seen = set()
    for where, text, ev in _rows():
        for ref in ev:
            if not ref.startswith("certified:"):
                continue
            path = ref.split(":", 1)[1]
            need = M.required_caveat(path)
            if need is not None:
                assert need in text, (where, path)
                seen.add(path)
    assert seen == {p for p, k in INVENTORY.items() if k != "none"}


def test_verify_evidence_is_clean():
    assert [p for p in M.verify_evidence() if M.ABSENT_BINARY_MARK not in p] == []


def test_verify_evidence_fails_a_row_that_drops_a_mechanism_caveat(monkeypatch):
    s = M.STAGES["spec->rvt-legacy"]
    bare = M.Stage(s.id, s.impl, s.does.replace(M.V23_MECHANISM_ONLY, ""), s.evidence)
    monkeypatch.setitem(M.STAGES, s.id, bare)
    probs = [p for p in M.verify_evidence() if "MECHANISM only" in p]
    assert probs and probs[0].startswith("stage spec->rvt-legacy"), probs


def test_verify_evidence_fails_a_row_that_drops_the_stage_l8_caveat(monkeypatch):
    s = M.STAGES["rfa-reload"]
    bare = M.Stage(s.id, s.impl, s.does.replace(M.STAGE_L8_EARLIER_FORM, ""), s.evidence)
    monkeypatch.setitem(M.STAGES, s.id, bare)
    probs = [p for p in M.verify_evidence() if "EARLIER form" in p]
    assert probs and probs[0].startswith("stage rfa-reload"), probs


def test_the_stage_l8_caveat_states_the_retraction_and_the_current_status():
    c = M.STAGE_L8_EARLIER_FORM
    for must in ("EARLIER FORM", "verdict #22", "verdict #25", "RETRACTED",
                 "NO placed instance", "instance_id -1", "design is empty",
                 "not complete", "#892", "#931", "#887", "VALID",
                 "NO viewer or desktop-Revit verdict"):
        assert must in c, must


def test_the_stage_l8_recipe_is_the_tracked_build_record():
    with open(os.path.join(ROOT, "experiments", "ifc_room", "build_record.json"),
              encoding="utf-8") as fh:
        stage_f = json.load(fh)["stages"][0]
    built = {f["tag"]: (f["constructor"], f["kwargs"])
             for f in stage_f["families"] if f.get("built")}
    fams = M.EVIDENCE_FORMS[L8]["families"]
    assert [t for t, _, _ in fams] == ["MSB", "DP-1", "DP-2", "LP-1", "LP-2", "LP-3",
                                       "T1", "LP-4"]          # the stage L1..L8 order
    for tag, ctor, kwargs in fams:
        rec_ctor, rec_kwargs = built[tag]
        assert ctor.replace(":", ".") == rec_ctor, tag
        assert kwargs == rec_kwargs, tag
    # and the load records name exactly these families, none placed
    for i, tag in enumerate(t for t, _, _ in fams):
        name = {"MSB": "msb", "T1": "t1"}.get(tag, tag.replace("-", "").lower())
        p = os.path.join(ROOT, "experiments", "ifc_room",
                         f"stage_L{i + 1}_{name}.rvt.load.json")
        with open(p, encoding="utf-8") as fh:
            assert json.load(fh)["plan"]["instance_id"] == -1, p


def test_room2025_certified_fingerprint_is_the_ledgers_own():
    ent = M.EVIDENCE_FORMS[R25]
    led = {e.get("file"): e for e in _ledger()["certified"]}
    assert ent["certified"] == {2025: led[R25]["sha256"]}
    assert ent["certified"][2025] != ent["reviewed"][2025]


def _doc_rows(path):
    with open(path, encoding="utf-8") as fh:
        return [ln for ln in fh if ln.startswith("|")]


@pytest.mark.parametrize("path", sorted(set(M.EVIDENCE_FORMS) | set(M.EVIDENCE_MECHANISMS)))
def test_every_doc_row_naming_the_file_says_what_it_certifies(path):
    if path == DOWNLIGHT:
        pytest.skip("the downlight's doc rows are #981's (test_matrix_evidence_981)")
    ent = M.EVIDENCE_FORMS.get(path) or M.EVIDENCE_MECHANISMS[path]
    phrase = "earlier form" if path in M.EVIDENCE_FORMS else "mechanism only"
    pats = [re.compile(p) for p in ent["doc_names"]]
    hits = 0
    for doc in DOCS:
        for ln in _doc_rows(doc):
            if any(p.search(ln) for p in pats):
                hits += 1
                assert "#984" in ln and phrase in ln.lower(), (os.path.basename(doc), ln[:90])
    assert hits, path


def test_honest_status_no_longer_claims_placement_for_stage_l8():
    for doc in DOCS:
        for ln in _doc_rows(doc):
            assert "family load + instance placement" not in ln, ln[:90]


def test_no_doc_or_row_calls_l8_or_l1a_the_same_constructors_families():
    gates = M._FAMSPEC_GATES
    assert "same constructors' families LOADED" not in gates
    assert "EARLIER forms" in gates and "#984" in gates
    with open(DOCS[0], encoding="utf-8") as fh:
        assert "the same constructors’ families are certified" not in fh.read()


# ---------------------------------------------------------------------------
# dynamic: rebuild through the cited generator and compare fingerprints
# ---------------------------------------------------------------------------

_DYN = [(p, r) for p, ent in sorted(M.EVIDENCE_FORMS.items()) if p != DOWNLIGHT
        for r in sorted(ent["reviewed"])]


@pytest.mark.parametrize("path,release", _DYN)
def test_generator_output_is_the_reviewed_form(path, release):
    """Fails when the generator's bytes move.  The fix is NOT to paste the new
    hash: re-read every row citing the file, name the change in its caveat
    (and the rendered docs), THEN record the new ``reviewed`` fingerprint --
    or stage a viewer batch and, once a verdict lands, cite that file."""
    if not os.path.isfile(BASES[release]):
        pytest.skip("bundled genesis base not in this clone")
    ent = M.EVIDENCE_FORMS[path]
    got = M.generator_fingerprint(path, release)
    assert got == ent["reviewed"][release], (
        f"{ent['generator']} output at {release} drifted from the fingerprint the matrix "
        f"wording was reviewed against ({ent['reviewed'][release][:8]} -> {got[:8]}): "
        "update the entry's caveat + the docs to name what changed, then record the new "
        "reviewed fingerprint (#984)")


def test_the_stage_l8_families_validate_today():
    if not os.path.isfile(BASES[2026]):
        pytest.skip("bundled genesis base not in this clone")
    rows = M.family_set_fingerprints(L8, 2026)
    assert [t for t, _, _ in rows] == [t for t, _, _ in M.STAGE_L8_FAMILIES]
    assert {v for _, _, v in rows} == {"VALID"}      # what the caveat says


def test_fingerprints_are_deterministic_across_processes_and_env(tmp_path):
    """A fresh interpreter with a hostile environment (a build date and the
    wall-rep opt-out set) rebuilds the same bytes: the recipes pin their env."""
    if not all(os.path.isfile(b) for b in BASES.values()):
        pytest.skip("bundled genesis bases not in this clone")
    code = ("import json, rvt.frontdoor.matrix as M; print(json.dumps(["
            f"M.generator_fingerprint({R25!r}, 2025), M.generator_fingerprint({L8!r}, 2026)]))")
    env = dict(os.environ, SOURCE_DATE_EPOCH="1234567890", RVT_WALL_REP="dummy",
               PYTHONPATH=os.pathsep.join([os.path.join(ROOT, "src"),
                                           os.environ.get("PYTHONPATH", "")]))
    out = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), env=env,
                         capture_output=True, text=True, timeout=600, check=True)
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got == [M.EVIDENCE_FORMS[R25]["reviewed"][2025],
                   M.EVIDENCE_FORMS[L8]["reviewed"][2026]]
    assert os.environ.get("SOURCE_DATE_EPOCH") != "1234567890"   # nothing leaked here


def test_the_author_fingerprint_does_not_depend_on_the_out_dir(tmp_path):
    if not os.path.isfile(BASES[2025]):
        pytest.skip("bundled genesis base not in this clone")
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert (M.generator_fingerprint(R25, 2025, out_dir=str(a))
            == M.generator_fingerprint(R25, 2025, out_dir=str(b)))


def test_the_placing_chain_names_the_open_cell_and_a_test_that_places():
    """#989 review: the chain's only certified citation has no placed instance,
    so its note carries the open-cell stamp and its evidence names the fresh-clone
    test that does place one."""
    from rvt.frontdoor import matrix as M
    ch = M.CHAINS["prompt->rfa->loaded-rvt"]
    assert M._OPEN_BUG in ch["note"] and "NO placed instance" in ch["note"]
    assert "test:tests/test_frontdoor_standalone.py" in ch["evidence"]
