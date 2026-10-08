"""#1058: a row of a shared-parameter file never refuses a family job.

A row the writer cannot author as the family's parameter -- a DATATYPE the writer has
no spec for (YESNO, NUMBER_OF_POLES), a datatype that disagrees with the parameter's
spec, or a parameter authored per instance / by formula -- is NOT used: the parameter
is authored LOCAL and a note names the row and why.  Never a second GUID, never a
refused job (hard rule 1).  A row that matches is still authored SHARED at its GUID.

Synthetic rows only (made-up GUIDs).
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_clearance as EC  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402

ROWS = (("Show Front Clearance", "YESNO"),          # no spec for YESNO
        (EC.P_SHOW, "YESNO"),                       # per instance
        (EC.P_FRONT_ON, "YESNO"),                   # by formula
        ("Number of Poles", "NUMBER_OF_POLES"),     # no spec for it
        ("Width", "TEXT"),                          # a disagreeing datatype
        ("Voltage", "ELECTRICAL_POTENTIAL"))        # matches: authored shared


def _file(tmp_path):
    p = tmp_path / "sp.txt"
    p.write_text("# synthetic\n*META\tVERSION\tMINVERSION\nMETA\t2\t1\n*GROUP\tID\tNAME\n"
                 "GROUP\t1\tG\n*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE"
                 "\tDESCRIPTION\tUSERMODIFIABLE\n"
                 + "".join(f"PARAM\t0000bbbb-1058-4000-8000-00000000000{i}\t{n}\t{dt}\t\t1\t1\t\t1\n"
                           for i, (n, dt) in enumerate(ROWS, start=1)),
                 encoding="utf-8")
    return str(p)


@pytest.mark.parametrize("make", [
    lambda sp: F.make_panelboard(shared_params=sp),
    lambda sp: F.make_transformer(kva=45, shared_params=sp),
    lambda sp: F.make_device("duplex-receptacle", shared_params=sp)],
    ids=["panelboard", "transformer", "device"])
def test_every_constructor_delivers_with_the_rows_it_cannot_share(make, tmp_path):
    prod = make(_file(tmp_path))
    rep = prod.write(str(tmp_path / "x.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    P = prod.doc.params
    for name, _dt in ROWS[:5]:
        if name in P:
            assert P[name].class_name == "ParamElemFamily", name
            assert any(f"row {name!r} NOT used" in n for n in prod.doc.notes), name
    if "Voltage" in P:
        assert P["Voltage"].class_name == "ParamElemExternal"
    assert "Width" in P and P["Width"].class_name == "ParamElemFamily"


def test_the_cli_delivers_too(tmp_path):
    out = tmp_path / "cli.rfa"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "panelboard",
                        "--shared-params", _file(tmp_path), "-o", str(out)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and out.exists(), r.stdout[-1500:] + r.stderr[-1500:]
    assert "VALID (0 errors" in r.stdout


def test_a_standard_parameter_with_a_row_it_cannot_use_is_kept_local(tmp_path):
    """#1053's fourth review: a STANDARD parameter (the #601 step) whose shared row has
    another datatype used to vanish from the family, reported only as "skipped".  It is
    authored LOCAL, read back from the written file, and the row is named."""
    p = tmp_path / "std.txt"
    p.write_text("# synthetic\n*META\tVERSION\tMINVERSION\nMETA\t2\t1\n*GROUP\tID\tNAME\n"
                 "GROUP\t1\tG\n*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE"
                 "\tDESCRIPTION\tUSERMODIFIABLE\n"
                 "PARAM\t0000cccc-1058-4000-8000-000000000001\tEnclosure Rating\tLENGTH\t\t1\t1\t\t1\n"
                 "PARAM\t0000cccc-1058-4000-8000-000000000002\tService Clearance\tTEXT\t\t1\t1\t\t1\n",
                 encoding="utf-8")
    prod = F.make_panelboard(shared_params=str(p))
    path = str(tmp_path / "std.rfa")
    rep = prod.write(path)
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    applied = {a["name"] for a in prod.standards["applied"]}
    skipped = {s["name"] for s in prod.standards["skipped"]}
    for name in ("Enclosure Rating", "Service Clearance"):
        assert name in applied and name not in skipped, name
        assert prod.doc.params[name].class_name == "ParamElemFamily", name
        assert any(f"row {name!r} NOT used" in n for n in prod.doc.notes), name
    from rvt.families import FamilyIndex
    fi = FamilyIndex(path)
    caps = set()
    for e, r in fi.unit_records(0).get(102, {}).items():
        if fi.class_name(r.class_id).startswith("ParamElem"):
            v = fi.decode(0, e, 102).value
            caps.add(((v.get("m_pParamDef") or {}).get("value") or {}).get("m_caption"))
    assert {"Enclosure Rating", "Service Clearance"} <= caps
