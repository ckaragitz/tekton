"""#1061: a shared-parameter file with a repeated name, a malformed GUID, a row
before its header, or one GUID under two names still delivers the family.

The row is NOT used and a note names it; the first row of a name -- and the first
name of a GUID -- is the one used, so a family never carries one GUID twice.
Through the reader, a constructor and the CLI.  Synthetic rows only.
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
    assert "row 'PanelName' NOT used -- the name repeats" in notes
    assert "row 'Phases' NOT used -- it has no valid GUID" in notes
    assert "row 'Panel Alias' NOT used -- its GUID is already row 'PanelName'" in notes



@pytest.mark.parametrize("body,refusal", [
    (_row(G1, "PanelName") + _row(G2, "PanelName"), "duplicate PARAM name"),
    (_row("not-a-guid", "Phases", "INTEGER"), "no valid GUID"),
    (_row(G1, "PanelName") + _row(G1, "Panel Alias"), "under two names"),
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


def test_a_constructor_delivers_and_says_which_rows(tmp_path):
    path = _file(tmp_path, _row(G1, "PanelName") + _row(G2, "PanelName")
                 + _row("xyz", "Phases", "INTEGER") + _row(G1, "Panel Alias"))
    prod = F.make_panelboard(shared_params=path)
    rep = prod.write(str(tmp_path / "p.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    notes = "\n".join(prod.doc.notes)
    assert "line 8: row 'PanelName' NOT used" in notes and "row 'Phases' NOT used" in notes
    guids = [str(pe.refs.get("guid") or (pe.obj.get("m_guid") or "")).lower()
             for pe in prod.doc.params.values() if pe.class_name == "ParamElemExternal"]
    assert guids.count(G1) <= 1                          # never one GUID twice
    assert prod.shared_parameters().get("PanelName") == G1   # the first row is the one used


def test_the_cli_delivers(tmp_path):
    path = _file(tmp_path, _row(G1, "PanelName") + _row(G2, "PanelName")
                 + _row("xyz", "Phases", "INTEGER"))
    out = str(tmp_path / "cli.rfa")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"),
                        "panelboard", "--shared-params", path, "-o", out],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and "VALID (0 errors" in r.stdout, r.stdout[-1200:] + r.stderr[-1200:]
    assert os.path.isfile(out)
