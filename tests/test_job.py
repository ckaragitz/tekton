"""test_job.py — the FRONT DOOR (tools/rvt_job.py) contract.

Smoke tests against ``samples/rstbasicsampleproject.rvt`` (the smallest
sample, ~6 s per commit): the EDIT mode plans ops via rvt.manipulate,
commits them in ONE commit, adds elements via rvt.mutate in a second stage,
asserts OUR identity, and runs every gate (structural / rvt.validate 0
errors / identity / P0 base-provenance) into the deliverable manifest.
Pure-python helpers (op planning failures, hosting detection) run without
any commit.
"""
from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
# the `job` fixture (tools/rvt_job.py as module ``rvt_job``) comes from tests/conftest.py


needs_rst = pytest.mark.skipif(not os.path.exists(RST),
                               reason="samples/rstbasicsampleproject.rvt missing")


# ---------------------------------------------------------------------------
# pure helpers (no commit)
# ---------------------------------------------------------------------------
def test_needs_hosting_detection(job):
    assert job._needs_hosting({"equipment": [{"kind": "panelboard", "hostWall": "W-1"}]})
    assert job._needs_hosting({"equipment": [{"kind": "panelboard", "mounting": "Wall"}]})
    assert not job._needs_hosting({"equipment": [{"kind": "transformer"}]})
    assert not job._needs_hosting({})


def test_is_autodesk_sample(job):
    assert job.is_autodesk_sample(RST)
    assert job.is_autodesk_sample("/anything/rmebasicsampleproject.rvt")
    assert not job.is_autodesk_sample("/firm/seeds/karagitz-electric-seed.rvt")


@needs_rst
def test_plan_rejects_unknown_op(job):
    from rvt.mutate import Document
    doc = Document.from_file(RST)
    with pytest.raises(ValueError):
        job.plan_edit_ops(doc, [{"op": "explode", "id": 1}])


# ---------------------------------------------------------------------------
# EDIT mode end-to-end smoke: manipulate ops (ONE commit) + add-instance stage
# ---------------------------------------------------------------------------
@needs_rst
def test_edit_mode_manipulate_smoke(job, tmp_path):
    from rvt.mutate import Document
    doc = Document.from_file(RST)
    lvl = 245423                                       # 'Level 2' (manipulate test specimen)
    before = doc._level_elevation(lvl)
    ops = [{"op": "set-level", "id": lvl, "elevation_ft": before + 1.5}]
    ops_p = tmp_path / "ops.json"
    ops_p.write_text(json.dumps({"ops": ops}))
    out = tmp_path / "edit.rvt"
    rc = job.main(["edit", RST, "--ops", str(ops_p), "-o", str(out)])
    assert rc == 0, "hard gates should pass (status may be PROOF-ONLY)"
    man = json.loads((tmp_path / "edit.rvt.manifest.json").read_text())
    assert man["mode"] == "edit"
    assert man["hard_gates_passed"] is True
    g = man["gates"]
    assert g["structural"]["status"] == "PASS"
    assert g["validation"]["status"] == "PASS" and g["validation"]["errors"] == 0
    assert g["identity"]["status"] == "PASS"
    ident = g["identity"]["identity"]
    assert ident["last_save_path"] == "edit.rvt"          # path scrubbed to basename
    assert ident["username"] == "" and ident["central_model_path"] == ""
    assert ident["author"] == "rvt-writer"
    # the sample base can never be deliverable
    assert man["deliverable"] is False
    assert man["status"].startswith("PROOF-ONLY")
    assert g["base_provenance"]["base_is_autodesk_sample"] is True
    # the edit landed
    assert abs(Document.from_file(str(out))._level_elevation(lvl) - (before + 1.5)) < 1e-9


@needs_rst
def test_edit_mode_add_instance_stage(job, tmp_path):
    """add-instance ops route through rvt.mutate as the create stage of an edit."""
    from rvt.mutate import Document
    doc = Document.from_file(RST)
    # a free-standing instance's symbol we can place again
    sym = level = None
    for eid in doc.ids_of_class("FamilyInstance"):
        v = doc.value(eid) or {}
        ii = ((v.get("m_pInstanceInfo") or {}).get("value") or {})
        if v.get("m_hostId") in (-1, None) and ii.get("m_symbolId") == v.get("m_masterSymbolId"):
            sym = ii.get("m_symbolId")
            break
    if sym is None:
        pytest.skip("no free-standing instance symbol in rstbasic")
    ops = [{"op": "add-instance", "name": "JOB-NEW", "symbol": sym,
            "position_ft": [10.0, 10.0, 0.0], "rotation_deg": 0}]
    ops_p = tmp_path / "ops.json"
    ops_p.write_text(json.dumps(ops))
    out = tmp_path / "add.rvt"
    rc = job.main(["edit", RST, "--ops", str(ops_p), "-o", str(out),
                   "--no-provenance"])                 # provenance already covered above
    assert rc == 0
    man = json.loads((tmp_path / "add.rvt.manifest.json").read_text())
    assert man["hard_gates_passed"] is True
    new_ids = man["edit"]["created_ids"]
    assert len(new_ids) == 1
    d2 = Document.from_file(str(out))
    assert new_ids[0] in d2.et_by_id and d2.class_of(new_ids[0]) == "FamilyInstance"
    # not-deliverable is honest even when the ledger is skipped
    assert man["deliverable"] is False


@needs_rst
def test_edit_mode_fails_loudly_on_bad_target(job, tmp_path):
    ops_p = tmp_path / "ops.json"
    ops_p.write_text(json.dumps([{"op": "set-level", "id": 245423 * 1000,   # nonexistent
                                   "elevation_ft": 1.0}]))
    out = tmp_path / "bad.rvt"
    rc = job.main(["edit", RST, "--ops", str(ops_p), "-o", str(out)])
    assert rc == 2                                    # planning failure, nothing written
    assert not out.exists()
    man = json.loads((tmp_path / "bad.rvt.manifest.json").read_text())
    assert man["status"].startswith("FAILED")
