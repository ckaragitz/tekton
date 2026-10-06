"""#876: a PROFILE MAP links a library's size parameters to the generated family's
own (``{"<library Width>": "Width"}``), written as a formula naming our parameter,
so a schedule of the library's parameters shows our family's sizes in every type.

* a link is a formula, tagged ``given`` from the map, evaluated on every type row;
* a link that cannot hold is refused and said: no such parameter, a name a formula
  cannot spell, another kind of value (a length is never linked to a number, a text
  to a length), a material;
* a caller's value for the same parameter wins over the map, said;
* the family validates, and a placed instance validates.

Synthetic only: made-up names / GUIDs (rule 6).  No claim that the link *drives*
anything in Revit (hard rule 4).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import param_profile as PP  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tests"))
from conftest import context_constants  # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")   # the 2025 build enters release_build_context


@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches the names the authoring context swaps too (#707)."""
    return context_constants

EQ = SK.OST_ELECTRICAL_EQUIPMENT
GRP = "autodesk.parameter.group:geometry-1.0.0"


def _g(n: int) -> str:
    return f"0000cccc-dddd-4eee-8fff-{n:012d}"


def _defn(name, def_class="ParamDefValue", spec="autodesk.spec.aec:length-2.0.0"):
    return dict(name=name, def_class=def_class, spec=spec, datatype="LENGTH",
                datatype_basis="spec", data_category=None, description="", visible=True,
                user_modifiable=True, hide_when_no_value=False, used_by=2)


PARAMS = {
    _g(1): _defn("Zz Box Width"),
    _g(2): _defn("Zz Box Height"),
    _g(3): _defn("Zz Count", spec="autodesk.spec.aec:number-1.0.0"),
    _g(4): _defn("Zz Text", "ParamDefString", None),
    _g(5): _defn("Zz Finish", "ParamDefMaterialBrowse", None),
    _g(6): _defn("Zz Box Depth"),
}


def _profile():
    rows = [{"guid": g, "name": d["name"], "instance": False, "palette_group": GRP,
             "value": None, "formula": None, "formula_unread": False} for g, d in PARAMS.items()]
    return {"schema": PP.PROFILE_SCHEMA, "conflicts": [], "variants": [], "warnings": [],
            "parameters": dict(PARAMS),                    # a copy: tests may extend it
            "families": {"Unit A": {"category": EQ, "params": rows},
                         "Unit B": {"category": EQ, "params": [dict(r) for r in rows]}}}


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(_profile()), encoding="utf-8")
    return str(p)


def _rows(doc):
    fam = doc.self_family.obj
    out = {}
    for r in fam["m_pFamilyTypes"]["value"]["m_pairs"]:
        by_id = {e["m_paramId"]: e for e in r["params"]["m_params"]}
        out[r["name"]] = {n: by_id[pe.elem_id] for n, pe in doc.params.items() if pe.elem_id in by_id}
    return out


def _linked(path, links, values=None, second_type=True):
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, links=links,
                                                                      values=values))
    if second_type:
        first = dict(prod.doc.types[0][1])
        first[prod.doc.params["Width"].elem_id] = 3.25
        prod.doc.add_type("Wide", first)
    prod.doc.finalize()
    return prod


def test_a_link_is_a_formula_that_follows_every_type(path):
    prod = _linked(path, {_g(1): "Width", "Zz Box Height": "Height"})
    rows = _rows(prod.doc)
    assert len(rows) == 2
    for tname, r in rows.items():
        assert r["Zz Box Width"]["m_oExpression"]["ptr_class"] == "ParameterExpression"
        assert r["Zz Box Width"]["m_value"] == pytest.approx(r["Width"]["m_value"])
        assert r["Zz Box Height"]["m_value"] == pytest.approx(r["Height"]["m_value"])
    assert rows["Wide"]["Zz Box Width"]["m_value"] == pytest.approx(3.25)
    assert prod.doc.params["Zz Box Width"].refs["provenance"] == {
        "tier": "given", "source": "the given profile map", "by": "formula", "link": "Width"}
    note = next(n for n in prod.doc.notes if n.startswith("linked by the given profile map"))
    assert "'Zz Box Width' = 'Width'" in note and "'Zz Box Height' = 'Height'" in note
    assert "Zz Box Depth" not in note                         # not mapped: blank
    assert rows["Wide"]["Zz Box Depth"]["m_oExpression"] is None


@pytest.mark.parametrize("key,target,why", [
    ("Zz Count", "Width", "'Width' is a length, the library parameter a number"),
    ("Zz Text", "Width", "'Width' is a length, the library parameter a spec.string"),
    ("Zz Box Width", "Temperature Rise", "'Temperature Rise' is a number, the library parameter a length"),
    ("Zz Box Width", "No Such", "the family has no parameter 'No Such'"),
    ("Zz Box Width", 5, "the map entry is 5, not a parameter name"),
    ("Zz Finish", "Width", "a material is not written by formula"),
])
def test_a_link_that_cannot_hold_is_refused_and_said(path, key, target, why):
    prod = _linked(path, {key: target}, second_type=False)
    name = key
    assert "provenance" not in prod.doc.params[name].refs
    assert any(n == f"{name!r}: the map's link is refused -- {why} -- left blank"
               for n in prod.doc.notes), [n for n in prod.doc.notes if name in n]
    assert all(r[name]["m_oExpression"] is None for r in _rows(prod.doc).values())


def test_a_given_value_wins_over_the_map(path):
    prod = _linked(path, {"Zz Box Width": "Width"}, values={"Zz Box Width": 1.5},
                   second_type=False)
    r = next(iter(_rows(prod.doc).values()))["Zz Box Width"]
    assert r["m_oExpression"] is None and r["m_value"] == pytest.approx(1.5)
    assert any("the map links it to 'Width', but a value was given" in n for n in prod.doc.notes)


def test_a_map_entry_the_profile_did_not_select_is_said(path):
    prod = _linked(path, {"Zz Elsewhere": "Width"}, second_type=False)
    assert any(n == "map entries for parameters the profile did not select: Zz Elsewhere"
               for n in prod.doc.notes)


@pytest.mark.parametrize("year", [2026, 2025])
def test_the_linked_family_validates(tmp_path, path, year):
    out = str(tmp_path / f"linked{year}.rfa")
    links = {"Zz Box Width": "Width", "Zz Box Height": "Height", "Zz Box Depth": "Depth"}
    if year == 2026:
        rep = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, links=links)).write(out)
    else:
        from rvt.frontdoor import release_ctx as RC
        base = os.path.join(ROOT, "plugin", "assets", "genesis", f"G_ABPD_{year}.rvt")
        if not os.path.exists(base):
            pytest.skip(f"the pinned {year} base is not in this checkout")
        with RC.release_build_context(base):
            rep = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, links=links)).write(out)
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True


def test_a_placed_linked_instance_validates(tmp_path, path):
    from rvt.famgen import loader as L
    from rvt.validate import Validator
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "route.py"), "run",
                    "--prompt", "an electrical room with a 45 kVA transformer",
                    "--output", "rvt", "--target-version", "2026",
                    "--out", str(tmp_path / "host"), "--json"],
                   check=True, capture_output=True, cwd=ROOT)
    host = str(tmp_path / "host" / "prompt_room.rvt")
    wm = L.survey_host(host).watermark
    prod = F.make_transformer(kva=45, start_id=int(wm) + 1, shared_params=PP.ProfileRequest(
        path, links={"Zz Box Width": "Width", "Zz Box Depth": "Depth"}))
    out = str(tmp_path / "placed.rvt")
    L.load_family_into_project(host, out, prod, place=True)
    rep = Validator(out).run()
    errors = rep.errors() if callable(rep.errors) else rep.errors
    assert not errors, [e.message for e in errors][:5]


def test_the_cli_takes_a_profile_map(tmp_path, path):
    m, out = tmp_path / "map.json", tmp_path / "tx.rfa"
    m.write_text(json.dumps({"Zz Box Width": "Width"}), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "transformer",
                        "--kva", "45", "--param-profile", path, "--profile-map", str(m),
                        "-o", str(out), "--json"], cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    from rvt.families import FamilyIndex
    fi = FamilyIndex(str(out))
    found = False
    for e, rec in fi.unit_records(0).get(102, {}).items():
        v = fi.value(0, e) or {}
        if fi.class_name(rec.class_id) == "Family" and v.get("m_surrogateId") == -1:
            exprs = [q["m_oExpression"] for q in v["m_familyParams"]["value"]["m_params"]
                     if q.get("m_oExpression")]
            found = any(x.get("ptr_class") == "ParameterExpression" for x in exprs)
    assert found
    assert "the profile map 'map.json'" in r.stdout


# --- #971 review: every link announced is one the family carries ----------------------

def _profile_plus(tmp_path, extra):
    prof = _profile()
    for i, (name, def_class, spec, conv) in enumerate(extra, start=50):
        g = _g(i)
        prof["parameters"][g] = _defn(name, def_class, spec)
        for fam in prof["families"].values():
            fam["params"].append({"guid": g, "name": name, "instance": False, "palette_group": GRP,
                                  "value": conv, "formula": None, "formula_unread": False})
    p = tmp_path / "profile_plus.json"
    p.write_text(json.dumps(prof), encoding="utf-8")
    return str(p)


def test_a_type_link_to_an_instance_parameter_or_an_integer_is_refused_up_front(tmp_path):
    path = _profile_plus(tmp_path, [
        ("Zz Load", "ParamDefValue", "autodesk.spec.aec.electrical:apparentPower-1.0.0", None),
        ("Zz Poles", "ParamDefInt", None, None)])
    prod = _linked(path, {"Zz Load": "Apparent Load", "Zz Poles": "Phases"}, second_type=False)
    notes = prod.doc.notes
    assert any(n.startswith("'Zz Load': the map's link is refused -- 'Apparent Load' is bound per "
                            "instance") for n in notes)
    assert any(n.startswith("'Zz Poles': the map's link is refused -- an integer") for n in notes)
    assert not any(n.startswith("linked by") for n in notes)
    assert not any("formula of 'Zz Load' NOT written" in n or "formula of 'Zz Poles' NOT written" in n
                   for n in notes)


def test_the_linked_line_lists_only_links_still_carried(path):
    prod = _linked(path, {"Zz Box Width": "Width", "Zz Box Height": "Height"}, second_type=False)
    doc = prod.doc
    keep = {doc.params["Zz Box Height"].elem_id}
    PP.settle_formula_provenance(doc, keep)               # the width's formula not written
    (line,) = [n for n in doc.notes if n.startswith("linked by")]
    assert "'Zz Box Height' = 'Height'" in line and "Zz Box Width" not in line
    PP.settle_formula_provenance(doc, set())
    (line,) = [n for n in doc.notes if n.startswith("linked by")]
    assert line.endswith("): none written")


def test_a_refused_link_keeps_the_librarys_convention(tmp_path):
    path = _profile_plus(tmp_path, [("Zz Plain W", "ParamDefValue",
                                     "autodesk.spec.aec:length-2.0.0", 2.0)])
    prod = _linked(path, {"Zz Plain W": "No Such"}, second_type=False)
    assert prod.doc.params["Zz Plain W"].refs["provenance"]["tier"] == "library"
    assert any(n == "'Zz Plain W': the map's link is refused -- the family has no parameter "
                    "'No Such' -- the library's convention is used instead (a formula is checked "
                    "when the family is finalized)" for n in prod.doc.notes)


# --- #971 round-2 nits -------------------------------------------------------------------

def test_a_map_name_holding_the_heads_separator_still_rebuilds(tmp_path, path):
    m = tmp_path / "odd): name.json"
    m.write_text(json.dumps({"Zz Box Width": "Width"}), encoding="utf-8")
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, links=str(m)))
    prod.doc.finalize()
    (line,) = [n for n in prod.doc.notes if n.startswith("linked by")]
    assert line.endswith("'Zz Box Width' = 'Width'")
    PP.settle_formula_provenance(prod.doc, set())
    (line,) = [n for n in prod.doc.notes if n.startswith("linked by")]
    assert line.endswith(": none written") and "odd): name.json" in line


def test_map_flags_without_a_profile_are_said(tmp_path):
    m = tmp_path / "map.json"
    m.write_text("{}", encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "transformer",
                        "--kva", "45", "--profile-map", str(m), "-o", str(tmp_path / "t.rfa"),
                        "--no-validate"], cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-1500:]
    assert "--profile-map given without --param-profile -- ignored" in r.stderr


def test_a_link_whose_formula_was_replaced_leaves_the_linked_line(tmp_path, path):
    """#1029 review: a link's claim dropped because its formula was replaced must not
    leave the map's line announcing it."""
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"Zz Box Width": "Width"}), encoding="utf-8")
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, links=str(m)))
    doc = prod.doc
    doc.finalize()
    pe = doc.params["Zz Box Width"]
    pe.refs["formula"] = "Width / 2"                      # someone else's formula now
    PP.settle_formula_provenance(doc, {pe.elem_id})
    (line,) = [n for n in doc.notes if n.startswith("linked by")]
    assert line.endswith(": none written") and "provenance" not in pe.refs


def test_a_profile_name_holding_the_separator_keeps_its_library_line(tmp_path):
    p = tmp_path / "odd): profile.json"
    import shutil
    prof = _profile()
    for fam in prof["families"].values():
        for r in fam["params"]:
            if r["name"] == "Zz Box Depth":
                r["value"] = 0.5                           # a convention: both families agree
    p.write_text(json.dumps(prof), encoding="utf-8")
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(str(p)))
    prod.doc.finalize()
    PP.settle_formula_provenance(prod.doc, set())
    (line,) = [n for n in prod.doc.notes if n.startswith("provenance library (")]
    assert line == "provenance library (the profile 'odd): profile.json'): 'Zz Box Depth' by value"
