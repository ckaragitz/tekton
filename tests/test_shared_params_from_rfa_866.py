"""#866 step 1: ``tools/shared_params_from_rfa.py`` reads a user's shared-parameter
library back out of families.  Synthetic only: the families here are OUR generated
panelboard / device carrying OUR shared-parameter files (``usecases/eaton-panelboard``
and made-up GUIDs below), and fake in-memory indexes -- no third-party library
content is read or committed (rule 6)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import shared_params_from_rfa as SP  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen.skeleton import read_shared_parameter_file  # noqa: E402

OURS = os.path.join(ROOT, "usecases", "eaton-panelboard", "panelboard-shared-parameters.txt")
PY = sys.executable
TOOL = os.path.join(ROOT, "tools", "shared_params_from_rfa.py")

HDR = ("*META\tVERSION\tMINVERSION\nMETA\t2\t1\n*GROUP\tID\tNAME\nGROUP\t1\tT\n"
       "*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\t"
       "USERMODIFIABLE\tHIDEWHENNOVALUE\n")
G_VOLT = "11111111-2222-4333-8444-555555555555"
G_MH = "11111111-2222-4333-8444-666666666666"


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


@pytest.fixture(scope="module")
def instance_device(tmp_path_factory):
    """Our device with two shared parameters: Voltage bound by type with default
    flags, Mounting Height bound per INSTANCE, hidden, not user-modifiable and
    hide-when-empty -- every flag the other way round."""
    d = tmp_path_factory.mktemp("sp866i")
    txt = d / "dev.txt"
    txt.write_text(HDR + f"PARAM\t{G_VOLT}\tVoltage\tELECTRICAL_POTENTIAL\t\t1\t1\tsynthetic\t1\t0\n"
                   f"PARAM\t{G_MH}\tMounting Height\tLENGTH\t\t1\t1\tsynthetic\t1\t0\n", encoding="utf-8")
    prod = F.make_device("duplex-receptacle", standards=False, shared_params=str(txt))
    pe = prod.doc.params["Mounting Height"]
    assert pe.class_name == "ParamElemExternal"
    pe.refs["instance"] = True
    pe.obj["m_hideWhenNoValue"] = True
    pe.obj["m_userModifiable"] = False
    pe.obj["m_pParamDef"]["value"]["m_userVisible"] = False
    prod.doc.finalize()
    out = str(d / "dev.rfa")
    prod.write(out, validate=False, provenance=False)
    return out


def _rows(path):
    return {k: (v.guid, v.name, v.datatype.upper(), v.description, v.visible)
            for k, v in read_shared_parameter_file(path).items()}


# -- datatype: from the class, the spec, a labelled inference -- never a guess ------

def test_datatype_of_maps_class_and_spec():
    assert SP.datatype_of("ParamDefYesNo", None) == ("YESNO", "class")
    assert SP.datatype_of("ParamDefFamType", None) == ("FAMILYTYPE", "class")
    assert SP.datatype_of("ParamDefValue", "autodesk.spec.aec:length-2.0.0") == ("LENGTH", "spec")
    # how OUR writer authors text / integer parameters (a ParamDefValue with that spec)
    assert SP.datatype_of("ParamDefValue", "autodesk.spec:spec.string-1.0.0") == ("TEXT", "spec")
    assert SP.datatype_of("ParamDefValue", "autodesk.spec:spec.int64-1.0.0") == ("INTEGER", "spec")
    assert SP.datatype_of("ParamDefTextBrowseEdit", None) == ("MULTILINETEXT", "inferred")


@pytest.mark.parametrize("cls,spec", [("ParamDefValue", "autodesk.spec.aec:foo-1.0.0"),
                                      ("ParamDefSomethingNew", None),
                                      ("ParamDefValue", None)])
def test_an_unknown_class_or_spec_has_no_token(cls, spec):
    assert SP.datatype_of(cls, spec) == (None, "unknown")


def _param(guid, name, **kw):
    p = dict(name=name, def_class="ParamDefString", spec=None, spec_family=None, datatype="TEXT",
             datatype_basis="class", data_category=None, description="", visible=True,
             user_modifiable=True, hide_when_no_value=False, used_by=1)
    p.update(kw)
    return guid, p


def test_txt_leaves_out_unknown_tokens_and_writes_the_family_type_category():
    profile = {"parameters": dict([
        _param("aaaaaaaa-0000-4000-8000-000000000001", "Known"),
        _param("aaaaaaaa-0000-4000-8000-000000000002", "Mystery", def_class="ParamDefValue",
               spec="autodesk.spec.aec:foo-1.0.0", datatype=None, datatype_basis="unknown"),
        _param("aaaaaaaa-0000-4000-8000-000000000003", "Nested Type", def_class="ParamDefFamType",
               datatype="FAMILYTYPE", data_category=-2001040),
    ]), "families": {}, "conflicts": [], "variants": [], "warnings": []}
    txt = SP.shared_parameter_txt(profile)
    rows = {r.split("\t")[2]: r.split("\t") for r in txt.splitlines() if r.startswith("PARAM\t")}
    assert set(rows) == {"Known", "Nested Type"}                  # never a guessed token
    assert rows["Nested Type"][3:5] == ["FAMILYTYPE", "-2001040"]
    assert rows["Known"][4] == ""
    assert SP.txt_omitted(profile) == ["aaaaaaaa-0000-4000-8000-000000000002 "
                                       "(ParamDefValue, spec autodesk.spec.aec:foo-1.0.0)"]
    s = SP.summary_of(profile, [])
    assert s["txt_omitted"] and s["duplicate_names"] == 0


# -- the family's OWN binding: instance / type / only-defined -----------------------

class _FakeIndex:
    """unit_records / class_name / value over a dict of {eid: (class, value)}."""

    def __init__(self, elems):
        self.elems = elems

    def unit_records(self, unit):
        return {102: {eid: SimpleNamespace(class_id=cls) for eid, (cls, _v) in self.elems.items()}}

    def class_name(self, cid):
        return cid

    def value(self, unit, eid):
        return self.elems[eid][1]


def _fam(surrogate, rows, cat=-2001040):
    return ("Family", {"m_surrogateId": surrogate, "m_categoryId": cat,
                       "m_familyParams": {"value": {"m_params": [
                           {"m_paramId": pid, "m_instance": inst} for pid, inst in rows]}}})


def _ext(guid, name):
    return ("ParamElemExternal", {"m_externalParamKey": {"m_guidValue": guid},
                                  "m_pParamDef": {"ptr_class": "ParamDefString",
                                                  "value": {"m_caption": name}}})


def test_instance_comes_from_the_own_family_never_a_nested_surrogate():
    idx = _FakeIndex({
        10: _fam(-1, [(1, True), (2, False)]),
        20: _fam(77, [(1, False), (2, True), (3, True)]),         # a nested family's surrogate
        1: _ext("G1", "A"), 2: _ext("G2", "B"), 3: _ext("G3", "C"),
    })
    got = SP.read_index(idx)
    assert got["self_families"] == 1 and got["category"] == -2001040
    assert {p["name"]: p["instance"] for p in got["params"]} == {"A": True, "B": False, "C": None}


def test_two_own_families_are_counted_not_merged(monkeypatch):
    idx = _FakeIndex({10: _fam(-1, [(1, True)]), 11: _fam(-1, [(1, False), (2, True)], cat=-1),
                      1: _ext("G1", "A"), 2: _ext("G2", "B")})
    got = SP.read_index(idx)
    assert got["self_families"] == 2 and got["category"] == -2001040
    assert {p["name"]: p["instance"] for p in got["params"]} == {"A": True, "B": None}
    monkeypatch.setattr(SP, "read_family", lambda p: dict(got, release_note=None))
    monkeypatch.setattr(SP, "_files", lambda a: (list(a), []))
    profile, _ = SP.build(["x.rfa"])
    assert any("2 own Family elements" in w for w in profile["warnings"])


def test_instance_and_flags_read_back_from_a_written_family(instance_device):
    got = {p["name"]: p for p in SP.read_family(instance_device)["params"]}
    mh, v = got["Mounting Height"], got["Voltage"]
    assert (mh["guid"], mh["instance"], mh["visible"], mh["user_modifiable"],
            mh["hide_when_no_value"]) == (G_MH, True, False, False, True)
    assert (v["guid"], v["instance"], v["visible"], v["user_modifiable"],
            v["hide_when_no_value"]) == (G_VOLT, False, True, True, False)
    txt = {r.split("\t")[2]: r.split("\t") for r in
           SP.shared_parameter_txt(SP.build([instance_device])[0]).splitlines()
           if r.startswith("PARAM\t")}
    assert txt["Mounting Height"][6] == "0" and txt["Mounting Height"][8:] == ["0", "1"]
    assert txt["Voltage"][6] == "1" and txt["Voltage"][8:] == ["1", "0"]


# -- round trip through OUR own shared-parameter file -------------------------------

def test_round_trip_reproduces_the_source_file(panelboard, tmp_path):
    profile, errors = SP.build([panelboard])
    assert errors == [] and profile["conflicts"] == [] and profile["warnings"] == []
    assert all(p["datatype_basis"] in ("class", "spec") for p in profile["parameters"].values())
    txt = tmp_path / "back.txt"
    txt.write_text(SP.shared_parameter_txt(profile), encoding="utf-8")
    assert _rows(str(txt)) == _rows(OURS)          # GUID, name, datatype, description, visible
    fam = profile["families"]["pb"]["params"]
    assert {p["name"] for p in fam} == set(_rows(OURS))
    assert all(p["instance"] is False for p in fam)   # the panelboard binds them all by type


def test_extracted_file_drives_a_rebuild_at_the_same_guids(panelboard, tmp_path):
    """The extracted TXT is a working --shared-params input (no name on two GUIDs
    here): a rebuild carries the same parameters at the same GUIDs."""
    txt = tmp_path / "back.txt"
    txt.write_text(SP.shared_parameter_txt(SP.build([panelboard])[0]), encoding="utf-8")
    again = _make_panelboard(str(tmp_path / "again.rfa"), str(txt))
    a = {p["name"]: p["guid"] for p in SP.read_family(panelboard)["params"]}
    b = {p["name"]: p["guid"] for p in SP.read_family(again)["params"]}
    assert a == b and len(a) == len(_rows(OURS))


# -- inputs, errors, the summary ----------------------------------------------------

def test_cli_writes_both_outputs_and_names_unreadable_inputs(panelboard, tmp_path):
    bad = tmp_path / "not_a_family.rfa"
    bad.write_bytes(b"not a compound file")
    txt, prof = tmp_path / "o.txt", tmp_path / "o.json"
    r = subprocess.run([PY, TOOL, panelboard, str(bad), "--txt", str(txt), "--profile", str(prof),
                        "--json"], cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 1                        # one input unreadable -> exit 1, named
    summary = json.loads(r.stdout)
    assert summary["families"] == 1 and summary["parameters"] == len(_rows(OURS))
    assert len(summary["errors"]) == 1 and "not_a_family.rfa" in summary["errors"][0]
    assert summary["rows_not_family_parameters"] == 0 and summary["family_rows"] == 11
    assert _rows(str(txt)) == _rows(OURS)
    assert json.loads(prof.read_text())["schema"] == "tekton.param-profile/1"


def test_files_directory_any_case_dedupe_and_empty(tmp_path):
    d = tmp_path / "lib"
    d.mkdir()
    for n in ("a.rfa", "b.RFA", "c.rvt"):
        (d / n).write_bytes(b"")
    files, errors = SP._files([str(d), str(d / "a.rfa")])
    assert [os.path.basename(f) for f in files] == ["a.rfa", "b.RFA"] and errors == []
    empty = tmp_path / "empty"
    empty.mkdir()
    files, errors = SP._files([str(empty)])
    assert files == [] and len(errors) == 1 and "no .rfa" in errors[0]
    r = subprocess.run([PY, TOOL, str(empty), "--json"], cwd=ROOT, capture_output=True,
                       text=True, timeout=600)
    assert r.returncode == 1


def _fake_family(**kw):
    q = dict(guid="g1", name="X", def_class="ParamDefString", spec=None, datatype="TEXT",
             datatype_basis="class", data_category=None, palette_group="", instance=False,
             description="", visible=True, user_modifiable=True, hide_when_no_value=False)
    q.update(kw)
    return {"category": None, "self_families": 1, "release_note": None, "params": [q]}


def test_identity_conflicts_and_cosmetic_variants_are_kept_apart(monkeypatch):
    fams = {"a": _fake_family(spec="autodesk.spec.aec:length-1.0.0", def_class="ParamDefValue",
                              datatype="LENGTH", datatype_basis="spec"),
            "b": _fake_family(spec="autodesk.spec.aec:length-2.0.0", def_class="ParamDefValue",
                              datatype="LENGTH", datatype_basis="spec", description="edited"),
            "c": _fake_family(name="Y", instance=True),
            "d": _fake_family(def_class="ParamDefTextBrowseEdit", datatype="TEXT")}
    monkeypatch.setattr(SP, "read_family", lambda p: fams[os.path.splitext(os.path.basename(p))[0]])
    monkeypatch.setattr(SP, "_files", lambda a: (list(a), []))
    profile, errors = SP.build(["a.rfa", "b.rfa", "c.rfa", "d.rfa"])
    assert errors == [] and profile["parameters"]["g1"]["name"] == "X"
    assert profile["parameters"]["g1"]["used_by"] == 4
    # a newer spec version or an edited description is drift, not a different parameter
    assert [(v["family"], v["fields"]) for v in profile["variants"]] == \
        [("b", ["spec", "description"]), ("c", ["spec"]), ("d", ["spec"])]
    # another name, another definition class: a conflict, the first kept
    assert [(c["family"], c["fields"]) for c in profile["conflicts"]] == \
        [("c", ["name", "def_class", "spec_family", "datatype", "datatype_basis"]),
         ("d", ["def_class", "spec_family", "datatype", "datatype_basis"])]
    assert profile["conflicts"][0]["kept"]["name"] == "X"


def test_two_files_of_one_name_are_both_kept(monkeypatch, tmp_path):
    fams = {os.path.join("x", "a.rfa"): _fake_family(), os.path.join("y", "a.rfa"): _fake_family()}
    monkeypatch.setattr(SP, "read_family", lambda p: fams[p])
    monkeypatch.setattr(SP, "_files", lambda a: (list(a), []))
    profile, _ = SP.build(list(fams))
    assert sorted(profile["families"]) == sorted(fams)


def test_a_name_on_two_guids_is_counted():
    profile = {"parameters": dict([_param("g1", "Same"), _param("g2", "Same")]),
               "families": {}, "conflicts": [], "variants": [], "warnings": []}
    assert SP.summary_of(profile, [])["duplicate_names"] == 1
