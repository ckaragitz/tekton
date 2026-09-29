"""#866 step 1: ``tools/shared_params_from_rfa.py`` reads a user's shared-parameter
library back out of families.  Synthetic only: the families here are OUR generated
panelboard carrying OUR shared-parameter file (``usecases/eaton-panelboard``) -- no
third-party library content is read or committed (rule 6)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import shared_params_from_rfa as SP  # noqa: E402
from rvt.famgen.skeleton import read_shared_parameter_file  # noqa: E402

OURS = os.path.join(ROOT, "usecases", "eaton-panelboard", "panelboard-shared-parameters.txt")
PY = sys.executable


def _make_panelboard(out, shared):
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "make_family.py"), "panelboard",
                        "--mains", "400", "--spaces", "42", "--mcb",
                        "--shared-params", shared, "-o", out],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    return out


@pytest.fixture(scope="module")
def panelboard(tmp_path_factory):
    d = tmp_path_factory.mktemp("sp866")
    return _make_panelboard(str(d / "pb.rfa"), OURS)


def _rows(path):
    return {k: (v.guid, v.name, v.datatype.upper(), v.description, v.visible)
            for k, v in read_shared_parameter_file(path).items()}


def test_datatype_of_maps_class_and_spec():
    assert SP.datatype_of("ParamDefYesNo", None) == ("YESNO", True)
    assert SP.datatype_of("ParamDefValue", "autodesk.spec.aec:length-2.0.0") == ("LENGTH", True)
    # how OUR writer authors text / integer parameters (a ParamDefValue with that spec)
    assert SP.datatype_of("ParamDefValue", "autodesk.spec:spec.string-1.0.0") == ("TEXT", True)
    assert SP.datatype_of("ParamDefValue", "autodesk.spec:spec.int64-1.0.0") == ("INTEGER", True)
    # an unknown spec is written as its own id and flagged, never guessed
    assert SP.datatype_of("ParamDefValue", "autodesk.spec.aec:foo-1.0.0") == \
        ("autodesk.spec.aec:foo-1.0.0", False)


def test_round_trip_reproduces_the_source_file(panelboard, tmp_path):
    profile, errors = SP.build([panelboard])
    assert errors == []
    assert profile["conflicts"] == []
    assert all(p["datatype_known"] for p in profile["parameters"].values())
    txt = tmp_path / "back.txt"
    txt.write_text(SP.shared_parameter_txt(profile), encoding="utf-8")
    assert _rows(str(txt)) == _rows(OURS)          # GUID, name, datatype, description, visible
    fam = profile["families"]["pb"]["params"]
    assert {p["name"] for p in fam} == set(_rows(OURS))
    assert all(p["instance"] is False for p in fam)   # the panelboard binds them all by type


def test_extracted_file_drives_a_rebuild_at_the_same_guids(panelboard, tmp_path):
    """The extracted TXT is a working --shared-params input: a rebuild carries the same
    parameters at the same GUIDs."""
    txt = tmp_path / "back.txt"
    txt.write_text(SP.shared_parameter_txt(SP.build([panelboard])[0]), encoding="utf-8")
    again = _make_panelboard(str(tmp_path / "again.rfa"), str(txt))
    a = {p["name"]: p["guid"] for p in SP.read_family(panelboard)["params"]}
    b = {p["name"]: p["guid"] for p in SP.read_family(again)["params"]}
    assert a == b and len(a) == len(_rows(OURS))


def test_cli_writes_both_outputs_and_names_unreadable_inputs(panelboard, tmp_path):
    bad = tmp_path / "not_a_family.rfa"
    bad.write_bytes(b"not a compound file")
    txt, prof = tmp_path / "o.txt", tmp_path / "o.json"
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "shared_params_from_rfa.py"),
                        panelboard, str(bad), "--txt", str(txt), "--profile", str(prof), "--json"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 1                        # one input unreadable -> exit 1, named
    summary = json.loads(r.stdout)
    assert summary["families"] == 1 and summary["parameters"] == len(_rows(OURS))
    assert len(summary["errors"]) == 1 and "not_a_family.rfa" in summary["errors"][0]
    assert _rows(str(txt)) == _rows(OURS)
    assert json.loads(prof.read_text())["schema"] == "tekton.param-profile/1"


def test_a_guid_seen_with_two_names_is_a_conflict_not_an_overwrite(monkeypatch):
    fams = {"a": {"category": None, "params": [dict(guid="g1", name="X", def_class="ParamDefString",
                                                    spec=None, datatype="TEXT", datatype_known=True,
                                                    palette_group="", instance=False, description="",
                                                    visible=True, user_modifiable=True,
                                                    hide_when_no_value=False)]},
            "b": {"category": None, "params": [dict(guid="g1", name="Y", def_class="ParamDefString",
                                                    spec=None, datatype="TEXT", datatype_known=True,
                                                    palette_group="", instance=True, description="",
                                                    visible=True, user_modifiable=True,
                                                    hide_when_no_value=False)]}}
    monkeypatch.setattr(SP, "read_family", lambda p: fams[os.path.splitext(os.path.basename(p))[0]])
    monkeypatch.setattr(SP, "_files", lambda a: list(a))
    profile, errors = SP.build(["a.rfa", "b.rfa"])
    assert errors == [] and profile["parameters"]["g1"]["name"] == "X"
    assert profile["parameters"]["g1"]["used_by"] == 2
    assert profile["conflicts"] == [{"guid": "g1", "kept": ["X", "TEXT"], "also": ["Y", "TEXT"],
                                     "family": "b"}]
