"""#1061: a shared-parameter file with a repeated name, a malformed GUID, a row
before its header, or one GUID under two names still delivers the family.

Every row is taken in file order: one that cannot be used is NOT used and a note
names it; the first name of a GUID keeps it, so a family never carries one GUID
twice; a later row of a name with its own GUID is kept as that name's alternative,
and a parameter takes the first row of its name whose DATATYPE fits.  Through the
reader, a constructor and the CLI.  Synthetic rows only.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402

G1 = "0000dddd-1061-4000-8000-000000000001"
G2 = "0000dddd-1061-4000-8000-000000000002"
G3 = "0000dddd-1061-4000-8000-000000000003"
HDR = ("# synthetic\n*META\tVERSION\tMINVERSION\nMETA\t2\t1\n*GROUP\tID\tNAME\nGROUP\t1\tG\n"
       "*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\tUSERMODIFIABLE\n")


def _row(guid, name, dt="TEXT"):
    return f"PARAM\t{guid}\t{name}\t{dt}\t\t1\t1\t\t1\n"


def _file(tmp_path, body, name="sp.txt"):
    p = tmp_path / name
    p.write_text(HDR + body, encoding="utf-8")
    return str(p)


def test_each_unusable_row_costs_that_row_only(tmp_path):
    path = _file(tmp_path, _row(G1, "PanelName") + _row(G2, "PanelName")       # repeated name
                 + _row("not-a-guid", "Phases", "INTEGER")                  # malformed GUID
                 + _row(G1, "Panel Alias")                                   # GUID taken
                 + _row(G3, "MainsRating", "ELECTRICAL_CURRENT"))
    t = SK.read_shared_parameter_file(path)
    assert list(t) == ["PanelName", "MainsRating"]
    assert t["PanelName"].guid == G1                     # the FIRST row of the name
    notes = "\n".join(t.notes)
    assert "row 'PanelName' repeats a name already read: kept as that name's alternative" in notes
    assert [d.guid for d in t.alternates["PanelName"]] == [G2]
    assert "row 'Phases' NOT used -- it has no valid GUID" in notes
    assert "row 'Panel Alias' NOT used -- its GUID is already used by row 'PanelName'" in notes



@pytest.mark.parametrize("body,refusal", [
    (_row(G1, "PanelName") + _row(G2, "PanelName"), "duplicate PARAM name"),
    (_row("not-a-guid", "Phases", "INTEGER"), "no valid GUID"),
    (_row(G1, "PanelName") + _row(G1, "Panel Alias"), "under two rows"),
])
def test_strict_still_refuses_each_problem(tmp_path, body, refusal):
    """``strict=True`` (tools that audit a file) keeps the old refusal -- for each
    problem on its own, with its own reason."""
    path = _file(tmp_path, body)
    with pytest.raises(ValueError, match=refusal):
        SK.read_shared_parameter_file(path, strict=True)
    assert SK.read_shared_parameter_file(path).notes          # and non-strict says it


def test_parsed_rows_with_one_guid_twice_keep_the_first_name():
    rows = {"A": SK.SharedParamDef(guid=G1, name="A", datatype="TEXT"),
            "B": SK.SharedParamDef(guid=G1.upper(), name="B", datatype="TEXT")}
    t = SK.shared_param_table(rows)
    assert list(t) == ["A"] and any("row 'B' NOT used" in n for n in t.notes)


def test_a_later_row_of_a_name_stands_in_for_one_that_cannot_be_used(tmp_path):
    """Every row is checked against the rows already USED, in file order (#1072
    review): a Width row whose GUID is taken is not used, so the next Width row --
    with its own GUID -- is the one used, and no note says otherwise."""
    G6 = "0000dddd-1061-4000-8000-000000000006"
    path = _file(tmp_path, _row(G1, "PanelName") + _row(G1, "Width", "LENGTH")
                 + _row(G6, "Width", "LENGTH"))
    t = SK.read_shared_parameter_file(path)
    assert {k: v.guid for k, v in t.items()} == {"PanelName": G1, "Width": G6}
    notes = "\n".join(t.notes)
    assert "line 8: row 'Width' NOT used -- its GUID is already used by row 'PanelName'" in notes
    assert "repeats" not in notes and "line 9" not in notes
    with pytest.raises(ValueError, match=r":8: GUID .* under two rows"):
        SK.read_shared_parameter_file(path, strict=True)      # the FIRST problem, by line
    prod = F.make_panelboard(shared_params=path)
    assert prod.shared_parameters().get("Width") == G6


def test_parsed_rows_are_canonicalised_and_checked_like_a_file():
    rows = {"PanelName": SK.SharedParamDef(guid="{" + G1.upper() + "}", name="PanelName",
                                           datatype="TEXT"),
            "Voltage": SK.SharedParamDef(guid="not-a-guid", name="Voltage",
                                         datatype="ELECTRICAL_POTENTIAL"),
            "": SK.SharedParamDef(guid=G3, name="", datatype="TEXT")}
    t = SK.shared_param_table(rows)
    assert {k: v.guid for k, v in t.items()} == {"PanelName": G1}
    notes = "\n".join(t.notes)
    assert "row 'Voltage' NOT used (GUID 'not-a-guid') -- it has no valid GUID" in notes
    assert "a row with no NAME is NOT used" in notes
    prod = F.make_panelboard(shared_params=rows)            # never refused (hard rule 1)
    assert prod.shared_parameters() == {"PanelName": G1}


def test_a_table_passed_in_keeps_its_notes():
    t = SK.SharedParamTable({"A": SK.SharedParamDef(guid=G1, name="A", datatype="TEXT")},
                            notes=["shared-parameter file x.txt line 3: row 'Z' NOT used"])
    assert SK.shared_param_table(t).notes[0].endswith("row 'Z' NOT used")
    doc = SK.new_family_document("generic_model", "Zz Notes", shared_params=t)
    assert any(n.endswith("row 'Z' NOT used") for n in doc.notes)


def test_a_file_row_with_no_name_is_not_used(tmp_path):
    t = SK.read_shared_parameter_file(_file(tmp_path, _row(G1, "") + _row(G2, "PanelName")))
    assert list(t) == ["PanelName"]
    assert any("line 7: a row with no NAME is NOT used" in n for n in t.notes)


def test_a_constructor_delivers_and_says_which_rows(tmp_path):
    path = _file(tmp_path, _row(G1, "PanelName") + _row(G2, "PanelName")
                 + _row("xyz", "Phases", "INTEGER") + _row(G1, "Panel Alias")
                 # a name the panelboard DOES author, on a GUID already used: never shared
                 + _row(G1, "Voltage", "ELECTRICAL_POTENTIAL"))
    prod = F.make_panelboard(shared_params=path)
    rep = prod.write(str(tmp_path / "p.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    notes = "\n".join(prod.doc.notes)
    assert "line 8: row 'PanelName' repeats a name already read" in notes
    assert "row 'Phases' NOT used" in notes
    guids = [str(pe.refs.get("guid") or (pe.obj.get("m_guid") or "")).lower()
             for pe in prod.doc.params.values() if pe.class_name == "ParamElemExternal"]
    assert guids.count(G1) == 1                          # never one GUID twice
    assert prod.shared_parameters().get("PanelName") == G1   # the first row is the one used
    assert "Voltage" not in prod.shared_parameters()
    assert "row 'Voltage' NOT used -- its GUID is already used by row 'PanelName'" in notes


def test_the_cli_delivers(tmp_path):
    path = _file(tmp_path, _row(G1, "PanelName") + _row(G2, "PanelName")
                 + _row("xyz", "Phases", "INTEGER"))
    out = str(tmp_path / "cli.rfa")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"),
                        "panelboard", "--shared-params", path, "-o", out],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and "VALID (0 errors" in r.stdout, r.stdout[-1200:] + r.stderr[-1200:]
    assert os.path.isfile(out)


def test_strict_stops_at_the_first_problem_in_file_order(tmp_path):
    """A repeated name on line 8, a row with no header on line 9: strict stops at
    line 8, and the notes come in file order (#1072 review round 2)."""
    path = _file(tmp_path, _row(G1, "PanelName") + _row(G2, "PanelName") + "junk line\n")
    with pytest.raises(ValueError, match=r":8: duplicate PARAM name 'PanelName'"):
        SK.read_shared_parameter_file(path, strict=True)
    notes = SK.read_shared_parameter_file(path).notes
    assert [n.split(":")[0].rsplit(" ", 1)[1] for n in notes] == ["8", "9"]


def test_a_name_takes_the_row_whose_datatype_fits(tmp_path):
    """Two rows of one name (legal in Revit's own files): the parameter takes the
    first whose DATATYPE fits it -- here the second -- and no note says otherwise
    (#1072 review round 2)."""
    from rvt.famgen import panel_can as PC
    path = _file(tmp_path, _row(G1, "Voltage", "TEXT")
                 + _row(G2, "Voltage", "ELECTRICAL_POTENTIAL"))
    t = SK.read_shared_parameter_file(path)
    assert t["Voltage"].guid == G1 and [d.guid for d in t.alternates["Voltage"]] == [G2]
    for prod in (F.make_panelboard(shared_params=path), PC.make_panel_can(shared_params=path)):
        assert prod.shared_parameters().get("Voltage") == G2
        notes = "\n".join(prod.doc.notes)
        assert "row 'Voltage': the row of DATATYPE 'ELECTRICAL_POTENTIAL'" in notes
        assert "row 'Voltage' NOT used" not in notes and "kept LOCAL, not shared: Voltage" \
            not in notes


def test_parsed_rows_are_named_by_their_key():
    from types import SimpleNamespace
    rows = {"PanelName": SK.SharedParamDef(guid=G1, name="Something Else", datatype="TEXT"),
            "Voltage": SimpleNamespace(guid=G2, datatype="ELECTRICAL_POTENTIAL"),
            "   ": SK.SharedParamDef(guid=G3, name="   ", datatype="TEXT")}
    t = SK.shared_param_table(rows)
    assert {k: v.guid for k, v in t.items()} == {"PanelName": G1, "Voltage": G2}
    assert t["PanelName"].name == "PanelName" and t["Voltage"].name == "Voltage"
    assert any("shared-parameter rows given: a row with no NAME is NOT used" in n for n in t.notes)


def test_an_alternatives_guid_is_never_reused_by_another_name(tmp_path):
    path = _file(tmp_path, _row(G1, "Voltage", "TEXT") + _row(G2, "Voltage", "ELECTRICAL_POTENTIAL")
                 + _row(G2, "PanelName"))
    t = SK.read_shared_parameter_file(path)
    assert "PanelName" not in t
    assert any("line 9: row 'PanelName' NOT used -- its GUID is already used by row 'Voltage'"
               in n for n in t.notes)
    sp = F.make_panelboard(shared_params=path).shared_parameters()
    assert list(sp.values()).count(G2) == 1


def test_a_parameter_not_shared_gets_no_swap_note(tmp_path):
    """A per-instance switch with a TEXT row, then a YESNO row: this route never
    shares it, so no note may say another row "is the one shared" (#1072 review
    round 3)."""
    from rvt.famgen import equipment_clearance as EC
    path = _file(tmp_path, _row(G1, EC.P_SHOW, "TEXT") + _row(G2, EC.P_SHOW, "YESNO"))
    prod = F.make_panelboard(shared_params=path)
    assert EC.P_SHOW not in prod.shared_parameters()
    notes = [n for n in prod.doc.notes if f"row {EC.P_SHOW!r}" in n]
    assert not any("is the one shared" in n for n in notes), notes
    assert any("NOT used -- it is authored per instance or by formula" in n for n in notes)
    assert not any("nor could" in n for n in notes), notes   # the other row was never tried


def test_a_refused_row_names_the_rows_also_tried(tmp_path):
    """No row of the name fits: the note says which other DATATYPEs were tried too."""
    path = _file(tmp_path, _row(G1, "Voltage", "TEXT") + _row(G2, "Voltage", "LENGTH"))
    prod = F.make_panelboard(shared_params=path)
    assert "Voltage" not in prod.shared_parameters()
    assert any("row 'Voltage' NOT used -- the file declares DATATYPE 'TEXT'" in n
               and "nor could the name's other row(s) of DATATYPE 'LENGTH'" in n
               for n in prod.doc.notes), prod.doc.notes


def test_a_name_takes_its_first_fitting_row_of_several(tmp_path):
    G4 = "0000dddd-1061-4000-8000-000000000004"
    path = _file(tmp_path, _row(G1, "Voltage", "TEXT") + _row(G2, "Voltage", "ELECTRICAL_POTENTIAL")
                 + _row(G4, "Voltage", "ELECTRICAL_POTENTIAL"))
    prod = F.make_panelboard(shared_params=path)
    assert prod.shared_parameters()["Voltage"] == G2
    assert sum("is the one shared" in n for n in prod.doc.notes) == 1


def test_a_table_passed_in_is_copied_with_its_alternatives(tmp_path):
    t = SK.read_shared_parameter_file(
        _file(tmp_path, _row(G1, "Voltage", "TEXT") + _row(G2, "Voltage", "ELECTRICAL_POTENTIAL")))
    for _ in range(2):                                   # the caller's table is never used up
        assert F.make_panelboard(shared_params=t).shared_parameters()["Voltage"] == G2
    assert t["Voltage"].guid == G1 and [d.guid for d in t.alternates["Voltage"]] == [G2]


def test_a_table_built_by_hand_is_checked_like_any_rows():
    t = SK.SharedParamTable({"PanelName": SK.SharedParamDef(guid="{" + G1.upper() + "}",
                                                           name="PanelName", datatype="TEXT")})
    prod = F.make_panelboard(shared_params=t)                # never refused (hard rule 1)
    assert prod.shared_parameters() == {"PanelName": G1}


def test_two_names_alternatives_never_share_a_guid():
    """An alternative reserves its GUID like any row: a second name's alternative
    at the same GUID is NOT used (#1072 review round 4)."""
    G4 = "0000dddd-1061-4000-8000-000000000004"
    t = SK.SharedParamTable({"A": SK.SharedParamDef(guid=G1, name="A", datatype="TEXT"),
                             "B": SK.SharedParamDef(guid=G2, name="B", datatype="TEXT")})
    t.alternates = {"A": [SK.SharedParamDef(guid=G3, name="A", datatype="LENGTH")],
                    "B": [SK.SharedParamDef(guid=G3, name="B", datatype="LENGTH"),
                          SK.SharedParamDef(guid=G4, name="B", datatype="LENGTH")]}
    c = SK.shared_param_table(t)
    assert [d.guid for d in c.alternates["A"]] == [G3]
    assert [d.guid for d in c.alternates["B"]] == [G4]
    assert any(f"row 'B' NOT used (GUID {G3!r}) -- its GUID is already used by row 'A'" in n
               for n in c.notes)


def test_a_checked_table_is_never_noted_twice(tmp_path):
    """Passing a checked table back in keeps its alternatives without a second
    "repeats a name" note."""
    t = SK.read_shared_parameter_file(
        _file(tmp_path, _row(G1, "Voltage", "TEXT") + _row(G2, "Voltage", "ELECTRICAL_POTENTIAL")))
    c = SK.shared_param_table(SK.shared_param_table(t))
    assert c.notes == t.notes and sum("repeats a name" in n for n in c.notes) == 1
    assert [d.guid for d in c.alternates["Voltage"]] == [G2]


def test_any_row_object_becomes_a_shared_param_def():
    """A row of another dataclass (no ``name`` field) is named by its key and
    kept as a SharedParamDef -- never handed on as the caller's own object."""
    import dataclasses

    @dataclasses.dataclass
    class Row:
        guid: str
        datatype: str

    t = SK.shared_param_table({"Voltage": Row(guid=G2.upper(), datatype="ELECTRICAL_POTENTIAL")})
    assert isinstance(t["Voltage"], SK.SharedParamDef)
    assert (t["Voltage"].name, t["Voltage"].guid) == ("Voltage", G2)
    assert F.make_panelboard(shared_params=t).shared_parameters() == {"Voltage": G2}


def test_a_swap_undone_is_never_reported():
    """``fit`` may swap a name to its alternative and back again: the row shared
    is then the first row, and no note says another one is."""
    t = SK.SharedParamTable({"X": SK.SharedParamDef(guid=G1, name="X", datatype="TEXT")})
    t.alternates = {"X": [SK.SharedParamDef(guid=G2, name="X", datatype="LENGTH")]}
    assert t.fit("X", "autodesk.spec.aec:length").guid == G2
    assert t.fit("X", "autodesk.spec:spec.string").guid == G1
    assert t.take_swap("X") is None and t.take_swap("X") is None
    assert t.fit("X", "autodesk.spec.aec:length").guid == G2
    assert "(GUID " + G2 + ") is the one shared" in t.take_swap("X")
    assert t.take_swap("X") is None                     # said once
