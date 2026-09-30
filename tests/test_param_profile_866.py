"""#866 step 3: a user's PARAMETER PROFILE applied to a family we generate
(``rvt.famgen.param_profile``, ``make_family --param-profile``).

Synthetic only: the profile below is made up here (made-up GUIDs and names), in
the ``tekton.param-profile/1`` shape ``tools/shared_params_from_rfa.py`` writes --
no third-party library content is read or committed (rule 6).  What is pinned:

* selection by category (share threshold, majority binding, a tie said and
  written by type, a label's / nested family's definition never selected) and by
  one named profile family;
* application: blank SHARED parameters at the profile's GUIDs, with its storage
  class, spec, palette group, flags and instance binding; what the family already
  authors (same name / GUID) and what this writer cannot author are left out and
  SAID; once per document however often it is finalized;
* the written family: family-mode VALID 0 errors, every added value row blank,
  and the extractor reads the same definitions + bindings back;
* a profile that selects nothing leaves the file byte-identical;
* a placed instance carries the profile's instance rows, resolving in the
  project, validator 0 errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import shared_params_from_rfa as SP  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import param_profile as PP  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402

EQ, LF = SK.OST_ELECTRICAL_EQUIPMENT, SK.OST_LIGHTING_FIXTURES
GRP_ID = "autodesk.parameter.group:identityData-1.0.0"
GRP_EL = "autodesk.parameter.group:electrical-1.0.0"


def _g(n: int) -> str:
    return f"0000aaaa-bbbb-4ccc-8ddd-{n:012d}"


def _defn(name, def_class="ParamDefString", spec=None, **kw):
    d = dict(name=name, def_class=def_class, spec=spec, datatype="TEXT", datatype_basis="class",
             data_category=None, description="made up", visible=True, user_modifiable=True,
             hide_when_no_value=False, used_by=1)
    d.update(kw)
    return d


PARAMS = {
    _g(1): _defn("Zz Tag Text"),
    _g(2): _defn("Zz Rated Amps", "ParamDefValue", "autodesk.spec.aec.electrical:current-1.0.0",
                 datatype="ELECTRICAL_CURRENT", datatype_basis="spec"),
    _g(3): _defn("Zz Spare Flag", "ParamDefYesNo", datatype="YESNO", visible=False,
                 user_modifiable=False, hide_when_no_value=True),
    _g(4): _defn("Zz Rare"),
    _g(5): _defn("Zz Notes", "ParamDefTextBrowseEdit", datatype="MULTILINETEXT",
                 datatype_basis="inferred"),
    _g(6): _defn("Width", "ParamDefValue", "autodesk.spec.aec:length-2.0.0",
                 datatype="LENGTH", datatype_basis="spec"),
    _g(7): _defn("Zz Label Only"),
    _g(8): _defn("Zz Tie"),
    _g(9): _defn("Zz Finish", "ParamDefMaterialBrowse", datatype="MATERIAL"),
}


def _row(n, inst, group=GRP_ID):
    return {"guid": _g(n), "name": PARAMS[_g(n)]["name"], "instance": inst, "palette_group": group}


PROFILE = {
    "schema": PP.PROFILE_SCHEMA, "conflicts": [], "variants": [], "warnings": [],
    "parameters": PARAMS,
    "families": {
        "Fam A": {"category": EQ, "params": [_row(1, False), _row(2, True, GRP_EL), _row(3, True),
                                             _row(5, False), _row(6, False), _row(7, None),
                                             _row(8, True), _row(9, False), _row(4, False)]},
        "Fam B": {"category": EQ, "params": [_row(1, False), _row(2, True, GRP_EL), _row(3, True),
                                             _row(5, False), _row(6, False), _row(7, None),
                                             _row(8, False), _row(9, False)]},
        "Fam C": {"category": EQ, "params": [_row(1, True), _row(2, True, GRP_EL), _row(7, None)]},
        "Fam D": {"category": EQ, "params": [_row(1, False), _row(3, True), _row(7, None)]},
        "Lamp": {"category": LF, "params": [_row(4, True)]},
    },
}


# -- selection ------------------------------------------------------------------------

def test_select_by_category_share_majority_and_tie():
    sel, notes = PP.select(PROFILE, category=EQ)
    got = {p.name: (p.instance, p.palette_group) for p in sel}
    # carried by >= 2 of the 4 equipment families, as each family's OWN parameter
    assert set(got) == {"Zz Tag Text", "Zz Rated Amps", "Zz Spare Flag", "Zz Notes", "Width",
                        "Zz Tie", "Zz Finish"}
    assert "Zz Rare" not in got and "Zz Label Only" not in got   # 1 of 4 / defined only
    assert got["Zz Tag Text"] == (False, GRP_ID)                  # 3 by type, 1 by instance
    assert got["Zz Rated Amps"] == (True, GRP_EL)
    assert got["Zz Tie"][0] is False and any("equally often" in n for n in notes)
    assert [p.name for p in sel] == sorted(p.name for p in sel)   # deterministic order
    assert [p.name for p in PP.select(PROFILE, category=EQ, share=1.0)[0]] == ["Zz Tag Text"]
    assert {p.name for p in PP.select(PROFILE, category=EQ, share=0.75)[0]} == \
        {"Zz Tag Text", "Zz Rated Amps", "Zz Spare Flag"}


def test_select_one_family_and_the_empty_cases():
    sel, _ = PP.select(PROFILE, family="Fam C")
    assert {(p.name, p.instance) for p in sel} == {("Zz Tag Text", True), ("Zz Rated Amps", True)}
    with pytest.raises(PP.ProfileError):
        PP.select(PROFILE, family="Nope")
    sel, notes = PP.select(PROFILE, category=SK.OST_ELECTRICAL_FIXTURES)
    assert sel == [] and "no family of category" in notes[0]


def test_load_profile_refuses_other_json(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"schema": "something-else"}), encoding="utf-8")
    with pytest.raises(PP.ProfileError):
        PP.load_profile(str(bad))
    good = tmp_path / "p.json"
    good.write_text(json.dumps(PROFILE), encoding="utf-8")
    assert PP.load_profile(str(good))["families"]["Lamp"]["category"] == LF


# -- application ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def profiled(tmp_path_factory):
    d = tmp_path_factory.mktemp("pp866")
    path = d / "profile.json"
    path.write_text(json.dumps(PROFILE), encoding="utf-8")
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(str(path)))
    out = str(d / "tx.rfa")
    rep = prod.write(out, validate=True, provenance=True)
    return prod, out, rep


def test_profile_parameters_are_added_shared_blank_and_bound(profiled):
    prod, _out, _rep = profiled
    doc = prod.doc
    added = {n: pe for n, pe in doc.params.items() if n.startswith("Zz ")}
    assert set(added) == {"Zz Tag Text", "Zz Rated Amps", "Zz Spare Flag", "Zz Tie", "Zz Finish"}
    for name, pe in added.items():
        assert pe.class_name == "ParamElemExternal"
        assert pe.obj["m_externalParamKey"]["m_guidValue"] == \
            next(g for g, p in PARAMS.items() if p["name"] == name)
        assert pe.obj["m_pParamDef"]["ptr_class"] == PARAMS[pe.refs["guid"]]["def_class"]
    amps = added["Zz Rated Amps"].obj["m_pParamDef"]["value"]
    assert amps["m_specTypeId"]["m_typeId"] == PARAMS[_g(2)]["spec"]
    assert amps["m_groupTypeId"]["m_typeId"] == GRP_EL
    flag = added["Zz Spare Flag"]
    assert (flag.obj["m_pParamDef"]["value"]["m_userVisible"], flag.obj["m_userModifiable"],
            flag.obj["m_hideWhenNoValue"]) == (False, False, True)
    # Width is the family's own (local) parameter: kept as authored, and said
    assert doc.params["Width"].class_name == "ParamElemFamily"
    notes = "\n".join(doc.notes)
    assert "'Width': the family already authors a parameter of this name" in notes
    assert "'Zz Notes': storage class ParamDefTextBrowseEdit is not written" in notes
    assert "parameter profile: 5 shared parameters added, 0 of them given" in notes


def test_written_family_is_valid_blank_and_reads_back(profiled):
    prod, out, rep = profiled
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0)
    assert rep["provenance"]["ok"] is True
    ids = {pe.elem_id for n, pe in prod.doc.params.items() if n.startswith("Zz ")}
    fam = prod.doc.self_family.obj
    rows = list(fam["m_familyParams"]["value"]["m_params"])
    for pair in fam["m_pFamilyTypes"]["value"]["m_pairs"]:
        rows += pair["params"]["m_params"]
    mine = [q for q in rows if q["m_paramId"] in ids]
    assert mine and all((q["m_str"], q["m_int"], q["m_value"], q["m_elemId"], q["m_oExpression"])
                        == ("", 0, 0.0, -1, None) for q in mine)          # nothing invented
    got = {p["name"]: p for p in SP.read_family(out)["params"]}
    want = {"Zz Tag Text": False, "Zz Rated Amps": True, "Zz Spare Flag": True, "Zz Tie": False,
            "Zz Finish": False}
    assert {n: got[n]["instance"] for n in want} == want
    assert (got["Zz Spare Flag"]["visible"], got["Zz Spare Flag"]["user_modifiable"],
            got["Zz Spare Flag"]["hide_when_no_value"]) == (False, False, True)


def test_applied_once_however_often_finalized(profiled):
    prod, _out, _rep = profiled
    n = len(prod.doc.params)
    prod.doc.finalize()
    prod.doc.finalize()
    assert len(prod.doc.params) == n
    assert sum("parameter profile:" in x for x in prod.doc.notes) == 1


def test_a_profile_selecting_nothing_leaves_the_file_byte_identical(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE), encoding="utf-8")

    def sha(shared, sub):
        (tmp_path / sub).mkdir()
        out = str(tmp_path / sub / "device.rfa")      # same name: the file records its own name
        F.make_device("duplex-receptacle", standards=False, shared_params=shared).write(
            out, validate=False, provenance=False)
        with open(out, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    # electrical fixtures: the profile holds no family of that category
    assert sha(None, "plain") == sha(PP.ProfileRequest(str(path)), "profiled")


def test_make_family_cli_takes_a_profile(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE), encoding="utf-8")
    out = tmp_path / "tx.rfa"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "transformer",
                        "--kva", "45", "--param-profile", str(path), "--profile-family", "Fam C",
                        "-o", str(out), "--json"],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    shared = json.loads(r.stdout)["family"]["shared_parameters"]
    assert shared == {"Zz Tag Text": _g(1), "Zz Rated Amps": _g(2)}


def test_a_placed_instance_carries_the_profile_instance_rows(tmp_path):
    from rvt.famgen import loader as L
    from rvt.families import FamilyIndex
    from rvt.validate import Validator
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "route.py"), "run",
                    "--prompt", "an electrical room with a 45 kVA transformer",
                    "--output", "rvt", "--target-version", "2026",
                    "--out", str(tmp_path / "host"), "--json"],
                   check=True, capture_output=True, cwd=ROOT)
    host = str(tmp_path / "host" / "prompt_room.rvt")
    wm = L.survey_host(host).watermark
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE), encoding="utf-8")

    def placed_rows(shared, name):
        prod = F.make_transformer(kva=45, start_id=int(wm) + 1, shared_params=shared)
        out = str(tmp_path / name)
        L.load_family_into_project(host, out, prod, place=True)
        fi = FamilyIndex(out)
        recs = fi.unit_records(0).get(102, {})
        rows = []
        for e, r in recs.items():
            if fi.class_name(r.class_id) == "FamilyInstance":
                rows += (((fi.value(0, e) or {}).get("m_pInstParams") or {}).get("value")
                         or {}).get("m_params") or []
        rep = Validator(out).run()
        errors = rep.errors() if callable(rep.errors) else rep.errors
        assert not errors, [e.message for e in errors][:5]
        assert all(q["m_paramId"] in {int(e) for e in recs} for q in rows)
        return rows

    plain = placed_rows(None, "plain.rvt")
    prof = placed_rows(PP.ProfileRequest(str(path)), "profiled.rvt")
    assert len(prof) == len(plain) + 2              # Zz Rated Amps + Zz Spare Flag, per instance


# -- values: a constant or a formula per parameter, the rest blank ---------------------

def test_values_fill_constants_and_formulas_and_refuse_mismatches(tmp_path):
    import copy
    prof = copy.deepcopy(PROFILE)
    prof["parameters"][_g(10)] = _defn("Zz Box Width", "ParamDefValue",
                                       "autodesk.spec.aec:length-2.0.0", datatype="LENGTH",
                                       datatype_basis="spec")
    for fam in ("Fam A", "Fam B"):
        prof["families"][fam]["params"].append({"guid": _g(10), "name": "Zz Box Width",
                                                "instance": True, "palette_group": GRP_ID})
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(prof), encoding="utf-8")
    values = {"Zz Tag Text": "TX-1",                         # text constant, by name
              _g(3): True,                                    # Yes/No, by GUID
              "Zz Box Width": {"formula": "Width"},           # a length driven by ours
              "Zz Rated Amps": {"formula": "Width"},          # length into a current: refused at build
              "Zz Tie": 12.5,                                 # a number for text: refused
              "Not Selected": "x"}
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(str(path), values=values))
    doc = prod.doc
    notes = "\n".join(doc.notes)
    assert "6 shared parameters added, 4 of them given a value or formula" in notes
    assert "'Zz Tie': the given value is not text for a ParamDefString -- left blank" in notes
    assert "values given for parameters the profile did not select: Not Selected" in notes
    assert "formula of 'Zz Rated Amps' NOT written" in notes      # never a wrong-spec formula
    fam = doc.self_family.obj
    rows = {q["m_paramId"]: q for q in fam["m_familyParams"]["value"]["m_params"]}
    pid = {n: pe.elem_id for n, pe in doc.params.items()}
    assert rows[pid["Zz Tag Text"]]["m_str"] == "TX-1"
    assert rows[pid["Zz Spare Flag"]]["m_int"] == 1
    assert rows[pid["Zz Tie"]]["m_str"] == ""
    assert rows[pid["Zz Rated Amps"]]["m_oExpression"] is None
    box = rows[pid["Zz Box Width"]]
    assert box["m_oExpression"] is not None                 # written as its formula
    assert box["m_value"] == pytest.approx(rows[pid["Width"]]["m_value"])   # evaluated per type


def test_values_file_through_the_cli(tmp_path):
    prof, vals, out = tmp_path / "profile.json", tmp_path / "values.json", tmp_path / "tx.rfa"
    prof.write_text(json.dumps(PROFILE), encoding="utf-8")
    vals.write_text(json.dumps({"Zz Tag Text": "TX-9"}), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "transformer",
                        "--kva", "45", "--param-profile", str(prof), "--profile-values", str(vals),
                        "-o", str(out), "--json"], cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    got = {p["name"]: p for p in SP.read_family(str(out))["params"]}
    assert "Zz Tag Text" in got
    from rvt.families import FamilyIndex
    fi = FamilyIndex(str(out))
    for e, rec in fi.unit_records(0).get(102, {}).items():
        v = fi.value(0, e) or {}
        if fi.class_name(rec.class_id) == "Family" and v.get("m_surrogateId") == -1:
            strs = [q["m_str"] for q in v["m_familyParams"]["value"]["m_params"]]
            assert "TX-9" in strs


# -- review of 96008fd (#881): typed formulas, finite values, exact share, GUID case,
#    type-reads-instance, and a bad profile never blocks delivery ----------------------

def _profile_plus(tmp_path, extra_params, extra_rows):
    import copy
    prof = copy.deepcopy(PROFILE)
    prof["parameters"].update(extra_params)
    for fam in ("Fam A", "Fam B"):
        prof["families"][fam]["params"] += copy.deepcopy(extra_rows)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(prof), encoding="utf-8")
    return str(path)


def _rows_by_name(doc):
    fam = doc.self_family.obj
    rows = {q["m_paramId"]: q for q in fam["m_familyParams"]["value"]["m_params"]}
    return {n: rows[pe.elem_id] for n, pe in doc.params.items() if pe.elem_id in rows}


def test_a_formula_is_typed_by_the_parameters_own_class(tmp_path):
    path = _profile_plus(tmp_path, {
        _g(11): _defn("Zz Count", "ParamDefInt", datatype="INTEGER"),
    }, [{"guid": _g(11), "name": "Zz Count", "instance": False, "palette_group": GRP_ID}])
    values = {"Zz Tag Text": {"formula": "Width"},          # text is not a length
              "Zz Count": {"formula": "Width"},             # nor is an integer
              "Zz Spare Flag": {"formula": "Width > 1'"},   # a Yes/No formula IS a Yes/No
              "Zz Finish": {"formula": "Width"}}            # no formula for a material
    doc = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, values=values)).doc
    notes = "\n".join(doc.notes)
    rows = _rows_by_name(doc)
    for name in ("Zz Tag Text", "Zz Count"):
        assert f"formula of '{name}' NOT written" in notes
        assert rows[name]["m_oExpression"] is None
        assert (rows[name]["m_value"], rows[name]["m_str"]) == (0.0, "")
    assert rows["Zz Spare Flag"]["m_oExpression"] is not None
    assert rows["Zz Spare Flag"]["m_int"] == 1                 # 2.07 ft > 1 ft
    assert "'Zz Finish': the given value is a formula (a material is not written" in notes


def test_non_finite_values_and_uppercase_guids(tmp_path):
    path = _profile_plus(tmp_path, {
        _g(10): _defn("Zz Box Width", "ParamDefValue", "autodesk.spec.aec:length-2.0.0",
                      datatype="LENGTH", datatype_basis="spec")},
        [{"guid": _g(10), "name": "Zz Box Width", "instance": True, "palette_group": GRP_ID}])
    values = {"Zz Box Width": float("nan"), _g(3).upper(): True}
    doc = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, values=values)).doc
    notes = "\n".join(doc.notes)
    assert "'Zz Box Width': the given value is not a finite number" in notes
    assert _rows_by_name(doc)["Zz Box Width"]["m_value"] == 0.0
    assert _rows_by_name(doc)["Zz Spare Flag"]["m_int"] == 1     # the GUID matched, any case
    assert "did not select" not in notes
    assert "1 of them given a value or formula" in notes         # NaN counted as nothing


def test_the_share_is_an_exact_ceiling_and_must_be_in_range():
    # 25 x 0.28 is 7.000000000000001 in floating point: a naive ceiling asks for 8
    fams = {f"F{i}": {"category": EQ, "params": ([_row(1, False)] if i < 7 else [])}
            for i in range(25)}
    prof = dict(PROFILE, families=fams)
    assert [p.name for p in PP.select(prof, category=EQ, share=0.28)[0]] == ["Zz Tag Text"]
    assert PP.select(prof, category=EQ, share=0.29)[0] == []
    for bad in (0, 1.5, -0.1, True, "half"):
        with pytest.raises(PP.ProfileError):
            PP.select(prof, category=EQ, share=bad)


def test_a_type_formula_reading_an_instance_shared_parameter_is_refused(tmp_path):
    path = _profile_plus(tmp_path, {
        _g(10): _defn("Zz Box Width", "ParamDefValue", "autodesk.spec.aec:length-2.0.0",
                      datatype="LENGTH", datatype_basis="spec"),
        _g(12): _defn("Zz Type Len", "ParamDefValue", "autodesk.spec.aec:length-1.0.0",
                      datatype="LENGTH", datatype_basis="spec")},
        [{"guid": _g(10), "name": "Zz Box Width", "instance": True, "palette_group": GRP_ID},
         {"guid": _g(12), "name": "Zz Type Len", "instance": False, "palette_group": GRP_ID}])
    values = {"Zz Box Width": {"formula": "Width"}, "Zz Type Len": {"formula": "Zz Box Width"}}
    doc = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, values=values)).doc
    notes = "\n".join(doc.notes)
    assert ("formula of 'Zz Type Len' NOT written: a type parameter's formula cannot read an "
            "instance parameter") in notes
    rows = _rows_by_name(doc)
    assert rows["Zz Box Width"]["m_oExpression"] is not None     # length-2.0.0 = Width's kind
    assert rows["Zz Type Len"]["m_oExpression"] is None


@pytest.mark.parametrize("req", [
    dict(family="No Such Family"),
    dict(profile="missing-profile.json"),
    dict(values="missing-values.json"),
    dict(values=["not", "a", "map"]),
    dict(share=2.0),
])
def test_a_bad_profile_request_still_delivers_the_family(tmp_path, req):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE), encoding="utf-8")
    kw = {"profile": str(path)}
    kw.update({k: (str(tmp_path / v) if k in ("profile", "values") and isinstance(v, str) else v)
               for k, v in req.items()})
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(**kw))
    assert any("parameter profile NOT applied" in n for n in prod.doc.notes)
    assert not any(n.startswith("Zz ") for n in prod.doc.params)
    rep = prod.write(str(tmp_path / "tx.rfa"), validate=True, provenance=False)
    assert rep["validate"]["family_mode"]["n_errors"] == 0
