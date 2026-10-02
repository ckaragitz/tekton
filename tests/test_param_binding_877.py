"""#877: a family parameter ASSOCIATED to a solid's material and visibility, in the
encoding the owner's library uses (private census, counts only; the module docstring
of ``rvt.famgen.param_binding`` has the numbers):

* a ``FamilyParametrizedElemParamsCell`` entry ``{m_famParamId, m_elemPropId,
  m_geomTag -1, m_bIsSymbol False}`` before the solid's ``PatternHelper``;
* the parameter among the solid's deletion parents;
* MATERIAL (-1002107): the solid's own ``m_materialId`` = the parameter's value;
* VISIBLE (-1006205): a Yes/No parameter.

The family validates at 0 errors and the associations read back from the written
file.  No claim that Revit honours them (hard rule 4).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_clearance as EC  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import param_binding as PB  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402


def _bound_family(bind_material=True, bind_visible=True):
    doc = SK.new_family_document("generic_model", "Zz Bound Box", work_plane_based=False)
    mat = EC.new_family_material(doc, "Zz Body Grey", (128, 128, 128), 0.0)
    mp = PB.add_material_parameter(doc, "Body Material", mat.elem_id)
    vp = doc.add_family_parameter("Show Body", SK.SPEC_YESNO, default=True)
    # a type row starts every parameter at 0.0: the material and the flag go in the row
    doc.add_type("Zz Bound Box", {mp.elem_id: {"m_elemId": mat.elem_id}, vp.elem_id: True})
    fb = F.add_box_form(doc, 1.0, 0.75, 2.0, base_z_ft=0.0, center=(0.0, 0.0), rep="solid")
    if bind_material:
        PB.bind_material(fb, mp, mat.elem_id)
    if bind_visible:
        PB.bind_visibility(fb, vp)
    doc.finalize()
    prod = F.FamilyProduct("generic_model", doc, F.FactSheet(subject="binding probe"),
                           forms=[fb], file_stem="zz_bound_box")
    return prod, fb, mp, vp, mat


def test_the_bindings_are_written_as_the_library_writes_them():
    prod, fb, mp, vp, mat = _bound_family()
    solid = PB.solid_of(fb)
    got = {d["m_elemPropId"]: d for d in PB.bound(solid)}
    assert got[PB.ELEM_PROP_MATERIAL] == {"m_famParamId": mp.elem_id, "m_elemPropId": -1002107,
                                          "m_geomTag": -1, "m_bIsSymbol": False}
    assert got[PB.ELEM_PROP_VISIBLE]["m_famParamId"] == vp.elem_id
    cells = [c["ptr_class"] for c in solid.obj["m_cellList"]["value"]["m_cells"]]
    assert cells.index("FamilyParametrizedElemParamsCell") < next(
        i for i, c in enumerate(cells) if c.endswith("PatternHelper"))
    assert cells.count("FamilyParametrizedElemParamsCell") == 1      # both in ONE cell
    deletion = solid.header["m_parents"]["value"]["m_deletion"]
    assert mp.elem_id in deletion and vp.elem_id in deletion
    assert solid.obj["m_materialId"] == mat.elem_id


def test_binding_twice_replaces_never_duplicates():
    prod, fb, mp, vp, mat = _bound_family()
    PB.bind_visibility(fb, vp)
    entries = list(PB.bound(PB.solid_of(fb)))
    assert sum(d["m_elemPropId"] == PB.ELEM_PROP_VISIBLE for d in entries) == 1


def test_the_wrong_kind_of_parameter_is_refused():
    doc = SK.new_family_document("generic_model", "Zz Wrong", work_plane_based=False)
    w = doc.add_family_parameter("Zz Len", SK.SPEC_LENGTH)
    doc.add_type("T", {})
    fb = F.add_box_form(doc, 1.0, 1.0, 1.0, base_z_ft=0.0, center=(0.0, 0.0), rep="solid")
    with pytest.raises(PB.BindingError, match="Yes/No"):
        PB.bind_visibility(fb, w)
    with pytest.raises(PB.BindingError, match="material parameter"):
        PB.bind_material(fb, w, 1)


@pytest.mark.parametrize("year", [2026, 2025])
def test_the_bound_family_validates_and_reads_back(tmp_path, year):
    out = str(tmp_path / f"bound{year}.rfa")
    if year == 2026:
        prod, fb, mp, vp, mat = _bound_family()
        rep = prod.write(out)
    else:
        from rvt.frontdoor import release_ctx as RC
        base = os.path.join(ROOT, "plugin", "assets", "genesis", f"G_ABPD_{year}.rvt")
        if not os.path.exists(base):
            pytest.skip(f"the pinned {year} base is not in this checkout")
        with RC.release_build_context(base):
            prod, fb, mp, vp, mat = _bound_family()
            rep = prod.write(out)
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True
    from contextlib import ExitStack
    from rvt import global_framing as GF
    from rvt.families import FamilyIndex
    with ExitStack() as st:
        GF.enter_own_release(st, out)
        fi = FamilyIndex(out)
        sid = PB.solid_of(fb).elem_id
        v = fi.value(0, sid)
        entries = [d for c in v["m_cellList"]["value"]["m_cells"]
                   if str(c.get("ptr_class", "")).endswith("FamilyParametrizedElemParamsCell")
                   for d in c["value"]["m_paramDrivenData"]]
        assert {(d["m_famParamId"], d["m_elemPropId"]) for d in entries} == {
            (mp.elem_id, PB.ELEM_PROP_MATERIAL), (vp.elem_id, PB.ELEM_PROP_VISIBLE)}
        assert v["m_materialId"] == mat.elem_id
        fam = next(fi.value(0, e) for e, r in fi.unit_records(0).get(102, {}).items()
                   if fi.class_name(r.class_id) == "Family"
                   and (fi.value(0, e) or {}).get("m_surrogateId") == -1)
        row = {q["m_paramId"]: q for q in fam["m_familyParams"]["value"]["m_params"]}
        assert row[mp.elem_id]["m_elemId"] == mat.elem_id and row[vp.elem_id]["m_int"] == 1
