"""test_instance_rows_859.py -- a value row carries its parameter's OWN instance flag.

The self-Family's m_familyParams and every type row said m_instance False for every
parameter, including instance parameters (#859).  A Revit-born family's rows say True
for an instance parameter, and the loader builds a placed instance's parameter rows
from exactly those -- so an instance parameter got no row on a placed instance.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import needs_schema                         # noqa: E402

from rvt.famgen import skeleton as fs                      # noqa: E402


def _self_family_rows(obj):
    return {q["m_paramId"]: q for q in obj["m_familyParams"]["value"]["m_params"]}


@needs_schema
def test_every_row_says_what_its_definition_says():
    doc = fs.new_family_document("electrical_equipment", "Inst Rows",
                                 part_type=fs.PART_TYPE["panelboard"], work_plane_based=True)
    i = doc.add_family_parameter("Mounting Height", fs.SPEC_LENGTH, is_instance=True)
    t = doc.add_family_parameter("Width", fs.SPEC_LENGTH)
    doc.add_type("A", {"Mounting Height": 4.0, "Width": 2.0})
    doc.add_type("B", {"Mounting Height": 5.0, "Width": 3.0})
    doc.finalize()
    fam = doc.self_family.obj
    cur = _self_family_rows(fam)
    assert cur[i.elem_id]["m_instance"] is True and cur[t.elem_id]["m_instance"] is False
    for row in fam["m_pFamilyTypes"]["value"]["m_pairs"]:
        by = {q["m_paramId"]: q for q in row["params"]["m_params"]}
        assert by[i.elem_id]["m_instance"] is True and by[t.elem_id]["m_instance"] is False
    assert doc.roundtrip()["failed"] == 0


@needs_schema
def test_a_generated_transformer_marks_its_instance_parameter():
    from rvt.famgen import factory as F
    prod = F.make_transformer(kva=45)
    fam = prod.doc.self_family.obj
    defs = {pe.elem_id: bool(pe.obj.get("m_instanceParam")) for pe in prod.doc.params.values()}
    rows = _self_family_rows(fam)
    assert any(defs.values()), "the transformer carries at least one instance parameter"
    assert all(rows[pid]["m_instance"] is inst for pid, inst in defs.items() if pid in rows)


@needs_schema
def test_placing_the_family_gives_the_instance_its_parameter_row(tmp_path):
    from rvt.famgen import factory as F
    from rvt.famgen import loader as L
    from rvt.families import FamilyIndex
    # a host WITH placed electrical equipment (the loader clones one for placement):
    # a project the front door itself builds from a prompt on our certified base
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, os.path.join(root, "tools", "route.py"), "run",
                    "--prompt", "an electrical room with a 45 kVA transformer",
                    "--output", "rvt", "--target-version", "2026",
                    "--out", str(tmp_path / "host"), "--json"],
                   check=True, capture_output=True, cwd=root)
    host = str(tmp_path / "host" / "prompt_room.rvt")
    wm = L.survey_host(host).watermark
    prod = F.make_transformer(kva=45, start_id=int(wm) + 1)
    out = str(tmp_path / "placed.rvt")
    L.load_family_into_project(host, out, prod, place=True)
    assert os.path.exists(out)
    fi = FamilyIndex(out)
    recs = fi.unit_records(0).get(102, {})
    ids = {int(e) for e in recs}
    inst_rows = []
    for e, r in recs.items():
        if fi.class_name(r.class_id) == "FamilyInstance":
            v = fi.value(0, e) or {}
            inst_rows += ((v.get("m_pInstParams") or {}).get("value") or {}).get("m_params") or []
    assert inst_rows, "the placed instance carries its instance-parameter row"
    assert all(q["m_paramId"] in ids for q in inst_rows), "rows point at the project's twins"
    from rvt.validate import Validator
    rep = Validator(out).run()
    errors = rep.errors() if callable(rep.errors) else rep.errors
    assert not errors, [e.message for e in errors][:5]
