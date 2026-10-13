"""#1058: a row of a shared-parameter file never refuses a family job.

A YESNO row is authored SHARED with the Yes/No storage.  Any other row the writer
cannot author as the family's parameter is NOT used: the parameter is authored LOCAL
and a note gives the true reason, checked in order -- a per-instance / formula
parameter (never shared on this route, whatever the row); a DATATYPE known but not
shared yet (NUMBER_OF_POLES on an integer parameter: the row suits it); a DATATYPE
this writer does not know (not checked); a DATATYPE that disagrees (fix the row).
Never a second GUID, never a refused job (hard rule 1).  A row that matches is still
authored SHARED at its GUID.

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
from rvt.famgen import skeleton as SK  # noqa: E402
from conftest import ladder_constants  # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")   # the read-back climbs the ladder


@pytest.fixture
def release_leak_extra():
    return ladder_constants


@pytest.fixture(scope="module", autouse=True)
def _warm_default_decoder(tmp_path_factory):
    """The first write in a process installs the bundled schema and seeds the
    native default ADocument decoder (by design); do that once before the
    guard's first snapshot, so only a swap the read-back leaves can turn it red."""
    F.make_device().write(str(tmp_path_factory.mktemp("w1058") / "w.rfa"))


ROWS = (("Show Front Clearance", "YESNO"),          # a type Yes/No: authored SHARED (#1058)
        (EC.P_SHOW, "YESNO"),                       # per instance: local
        (EC.P_FRONT_ON, "YESNO"),                   # by formula: local
        ("Number of Poles", "NUMBER_OF_POLES"),     # not authored shared yet: local
        ("Width", "TEXT"),                          # a disagreeing datatype: local
        ("Voltage", "ELECTRICAL_POTENTIAL"))        # matches: authored shared
GUID = {n: f"0000bbbb-1058-4000-8000-00000000000{i}" for i, (n, _dt) in enumerate(ROWS, start=1)}
LOCAL_WHY = {EC.P_SHOW: "per instance or by formula", EC.P_FRONT_ON: "per instance or by formula",
             "Number of Poles": "does not author a shared 'NUMBER_OF_POLES' parameter yet "
                                "(the row itself suits the parameter)",
             "Width": f"the file declares DATATYPE 'TEXT' but the family authors it as "
                      f"{SK.SPEC_LENGTH!r} (fix the file row to share it)"}
#: what each constructor authors of ROWS -- exercised, never skipped silently
EXERCISED = {"panelboard": ({EC.P_SHOW, EC.P_FRONT_ON, "Width"}, {"Show Front Clearance", "Voltage"}),
             "transformer": ({EC.P_SHOW, EC.P_FRONT_ON, "Width"}, {"Show Front Clearance", "Voltage"}),
             "device": ({"Number of Poles", "Width"}, {"Voltage"})}


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
def test_every_constructor_delivers_with_the_rows_it_cannot_share(make, tmp_path, request):
    prod = make(_file(tmp_path))
    rep = prod.write(str(tmp_path / "x.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    P = prod.doc.params
    local, shared = EXERCISED[request.node.callspec.id]
    for name in local:
        assert P[name].class_name == "ParamElemFamily", name
        assert any(f"row {name!r} NOT used" in n and LOCAL_WHY[name] in n
                   for n in prod.doc.notes), name
    for name in shared:
        assert P[name].class_name == "ParamElemExternal", name
        assert not any(f"row {name!r} NOT used" in n for n in prod.doc.notes), name


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



def _params_read_back(path):
    """{caption: (class, def class, guid or None, current value row)} of the WRITTEN family."""
    from contextlib import ExitStack
    from rvt import global_framing as GF
    from rvt.families import FamilyIndex
    with ExitStack() as st:
        GF.enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})
        out, fam = {}, None
        for e, r in recs.items():
            cls = fi.class_name(r.class_id)
            if cls.startswith("ParamElem"):
                v = fi.decode(0, e, 102).value
                pd = v.get("m_pParamDef") or {}
                key = (v.get("m_externalParamKey") or {}).get("m_guidValue")
                out[int(e)] = [cls, pd.get("ptr_class"), key,
                               (pd.get("value") or {}).get("m_caption")]
            elif cls == "Family":
                v = fi.decode(0, e, 102).value
                if v.get("m_surrogateId") == -1:
                    fam = v
    rows = {q["m_paramId"]: q for q in fam["m_familyParams"]["value"]["m_params"]}
    return {c: (cls, dc, g, rows.get(i)) for i, (cls, dc, g, c) in out.items()}


def test_a_yes_no_row_is_authored_shared_with_yes_no_storage(tmp_path):
    """#1058 DONE (1): YESNO maps to spec.bool -- read back from the written file: the
    parameter is a ParamElemExternal with the Yes/No storage at the row's GUID and
    holds the value the family would have given it locally."""
    sp = _file(tmp_path)
    shared, local = str(tmp_path / "shared.rfa"), str(tmp_path / "local.rfa")
    F.make_panelboard(shared_params=sp).write(shared)
    F.make_panelboard().write(local)
    got, base = _params_read_back(shared), _params_read_back(local)
    cls, dc, guid, row = got["Show Front Clearance"]
    assert (cls, dc) == ("ParamElemExternal", "ParamDefYesNo")
    assert str(guid).lower() == GUID["Show Front Clearance"]
    assert row["m_int"] == base["Show Front Clearance"][3]["m_int"]
    guids = [g for _c, _d, g, _r in got.values() if g]
    assert len(guids) == len(set(guids))                      # never one GUID twice


def test_a_per_instance_or_formula_parameter_keeps_its_binding_local():
    """The two branches a matching row cannot share on this route, pinned directly: the
    parameter is LOCAL, keeps its instance binding / formula, and the note says why."""
    from rvt.famgen import skeleton as SK
    rows = {n: SK.SharedParamDef(guid=f"0000eeee-1058-4000-8000-00000000000{i}", name=n,
                                 datatype="LENGTH")
            for i, n in enumerate(("Inst Len", "Form Len", "Plain Len"), start=1)}
    doc = SK.new_family_document("generic_model", "Zz Branches", shared_params=rows)
    inst = doc.add_family_parameter("Inst Len", SK.SPEC_LENGTH, is_instance=True, default=1.0)
    form = doc.add_family_parameter("Form Len", SK.SPEC_LENGTH, formula="Inst Len * 2")
    plain = doc.add_family_parameter("Plain Len", SK.SPEC_LENGTH, default=0.5)
    assert inst.class_name == "ParamElemFamily" and inst.obj["m_instanceParam"] is True
    assert form.class_name == "ParamElemFamily" and form.refs["formula"] == "Inst Len * 2"
    assert plain.class_name == "ParamElemExternal"
    for name in ("Inst Len", "Form Len"):
        assert any(f"row {name!r} NOT used" in n and "per instance or by formula" in n
                   and "the parameter-profile path shares its own parameters so" in n
                   for n in doc.notes), name
    assert not any("row 'Plain Len' NOT used" in n for n in doc.notes)



@pytest.mark.parametrize("dt,spec,kw,why", [
    # the order of the reasons (#1068 review round 2): a per-instance parameter is
    # never shared here, so a mismatched row is not told "fix the row"
    ("TEXT", "SPEC_YESNO", {"is_instance": True}, "per instance or by formula"),
    ("LENGTH", "SPEC_LENGTH", {"formula": "1'"}, "per instance or by formula"),
    # a known-but-unshared datatype on a parameter it does not suit: fix the row
    ("NUMBER_OF_POLES", "SPEC_LENGTH", {}, "(fix the file row to share it)"),
    # a datatype the writer does not know: not checked, never "the row is fine"
    ("LENGHT", "SPEC_LENGTH", {}, "is not one this writer knows"),
    # a spec no shared datatype fits yet: fixing the row would not share it, so the
    # note never says to (#1068 review round 4)
    ("TEXT", "electrical:frequency", {}, "no DATATYPE this writer shares fits that spec"),
    ("NUMBER", "electrical:frequency", {}, "no DATATYPE this writer shares fits that spec"),
    ("FOO_BAR", "SPEC_VOLTAGE", {}, "is not one this writer knows"),
])
def test_each_reason_is_the_true_one(dt, spec, kw, why):
    from rvt.famgen import skeleton as SK
    rows = {"P": SK.SharedParamDef(guid="0000eeee-1068-4000-8000-000000000001", name="P",
                                   datatype=dt)}
    doc = SK.new_family_document("generic_model", "Zz Reasons", shared_params=rows)
    spec_id = (getattr(SK, spec) if spec.startswith("SPEC_") else
               f"autodesk.spec.aec.{spec}-1.0.0")
    pe = doc.add_family_parameter("P", spec_id, **kw)
    assert pe.class_name == "ParamElemFamily"
    note = [n for n in doc.notes if "row 'P' NOT used" in n]
    assert len(note) == 1 and why in note[0], note
    assert "suits the parameter" not in note[0] and "row itself is fine" not in note[0]
    if spec_id.rsplit("-", 1)[0] not in SK.SHAREABLE_SPECS:
        assert "fix the file row" not in note[0]


def test_a_datatype_is_read_without_regard_to_case():
    from rvt.famgen import skeleton as SK
    rows = {n: SK.SharedParamDef(guid=f"0000eeee-1068-4000-8000-00000000001{i}", name=n,
                                 datatype=dt)
            for i, (n, dt) in enumerate((("Flag", "yesno"), ("Len", " length ")))}
    doc = SK.new_family_document("generic_model", "Zz Case", shared_params=rows)
    flag = doc.add_family_parameter("Flag", SK.SPEC_YESNO, default=1)
    ln = doc.add_family_parameter("Len", SK.SPEC_LENGTH, default=1.0)
    assert flag.class_name == ln.class_name == "ParamElemExternal"
    assert flag.obj["m_pParamDef"]["ptr_class"] == "ParamDefYesNo"
    # the matcher panel_can's own check calls with the file's raw DATATYPE (#1068 round 2)
    assert SK.shared_datatype_matches(" yesno ", SK.SPEC_YESNO)
    assert SK.shared_datatype_matches("Length\t", SK.SPEC_LENGTH)
    assert not SK.shared_datatype_matches(" text ", SK.SPEC_LENGTH)
