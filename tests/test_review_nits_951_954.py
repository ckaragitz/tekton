"""Review nits from #951 (refindex) and #954 (hexagon drive).

* ``famload._reference_idx_mgr`` reads "Not a Reference" from its single
  source, ``rvt.famgen.loader.NOT_A_REFERENCE`` (no bare 12).
* The #947 record's correction: a generic model always carries the Case B
  origin elevation plane, so its origin-plane codes are ``[1, 4, 12]``.
* ``angular_law.wire_hexagon_drive`` refuses (``AngularLawError``) instead of
  crashing (plain ``ValueError``) when the document has no origin centre
  plane, so ``trapeze_nested.make_hex_nut`` takes its documented VALUE ONLY
  fallback and still delivers the nut (hard rule 1).
* ``nest.verify_nested`` fails a nest only on constraint-law ERRORs, judges
  every nested unit as well as the host, and keeps the warnings in its report.

Nothing here claims Revit behaviour (hard rule 4).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from types import SimpleNamespace

import pytest

from rvt.famgen import angular_law as AL
from rvt.famgen import constraint_law as CL
from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F
from rvt.famgen import nest as N
from rvt.famgen import trapeze_nested as TN
from conftest import context_constants, ladder_constants

pytestmark = pytest.mark.usefixtures("no_release_leak")

IN = 1.0 / 12.0


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process seeds the native codec singletons; do it
    once before the leak guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t951w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="t951_")
    yield d
    shutil.rmtree(d, True)


def _origin_codes(product):
    return sorted((e.obj or {}).get("m_refName") for e in product.doc.elements
                  if e.class_name == "RefPlane" and (e.obj or {}).get("m_definesOrigin"))


# -- 1. famload: one source for "Not a Reference" -----------------------------

def test_famload_reads_not_a_reference_from_the_loader(monkeypatch):
    from rvt import famload as FL
    from rvt.famgen import loader as L
    from rvt.famgen import skeleton as SK
    assert L.NOT_A_REFERENCE == SK.REF_NAME["not_a_reference"]

    def rp(eid, code):
        return SimpleNamespace(class_name="RefPlane", elem_id=eid,
                               obj={"m_definesOrigin": True, "m_refName": code})
    doc = SimpleNamespace(elements=[rp(10, 1), rp(11, L.NOT_A_REFERENCE)])
    plan = SimpleNamespace(abs_index={10: 4, 11: 5})
    firsts = lambda: [e["first"] for e in FL._reference_idx_mgr(doc, plan)["value"]["m_idxToRefMap"]]
    assert firsts() == [4]
    # the predicate follows the constant: a bare literal would not
    monkeypatch.setattr(L, "NOT_A_REFERENCE", -999)
    assert firsts() == [4, 5]


# -- 2. the #947 record correction ---------------------------------------------

def test_a_generic_model_carries_the_origin_elevation_plane():
    assert _origin_codes(F.make_generic_model(width_ft=2.0, depth_ft=1.0,
                                              height_ft=2.0)) == [1, 4, 12]
    assert _origin_codes(F.make_archetype(product="wireway")) == [1, 4]


# -- 3. no origin centre plane: a refusal, so the nut still delivers ------------

def _no_centre_plane(doc, axis):
    raise ValueError(f"drive_law: no origin centre plane normal to {axis}")


def test_a_missing_origin_centre_plane_is_a_refusal_not_a_crash(monkeypatch):
    monkeypatch.setattr(DL, "origin_centre_plane", _no_centre_plane)
    with pytest.raises(AL.AngularLawError, match="no origin centre plane"):
        prod_doc = TN._child_doc(TN.NUT_FAMILY, 1000)
        fb = F.add_generic_part(prod_doc, {"shape": "polygon", "name": "nut",
                                           "vertices": TN.hex_ring(0.5 * IN),
                                           "height_ft": 0.25 * IN, "center": [0.0, 0.0],
                                           "base_z_ft": 0.0})
        from rvt.famgen import skeleton as SK
        af = prod_doc.add_family_parameter("Nut Across Flats", SK.SPEC_LENGTH,
                                           SK.PGROUP_DIMENSIONS, is_instance=True,
                                           default=0.5 * IN)
        half = prod_doc.add_family_parameter(TN.NUT_HALF_ACROSS_FLATS, SK.SPEC_LENGTH,
                                             SK.PGROUP_DIMENSIONS, is_instance=True,
                                             formula="Nut Across Flats / 2",
                                             default=0.25 * IN)
        prod_doc.add_type("t", {af.elem_id: 0.5 * IN, half.elem_id: 0.25 * IN})
        sk = next(e for e in fb.elements if e.class_name == "VarSketch")
        AL.wire_hexagon_drive(prod_doc, sketch=sk, caption="Nut Across Flats",
                              half_caption=TN.NUT_HALF_ACROSS_FLATS)


def test_the_nut_without_origin_centre_planes_still_delivers(tmp, monkeypatch):
    monkeypatch.setattr(DL, "origin_centre_plane", _no_centre_plane)
    prod = TN.make_hex_nut(1000, across_flats_ft=0.5625 * IN, height_ft=0.328125 * IN)
    assert prod.doc.hexagon_drive is None
    assert any("VALUE ONLY" in n and "no origin centre plane" in n for n in prod.doc.notes)
    assert not [e for e in prod.doc.elements if e.class_name == "AngularDim"]
    p = os.path.join(tmp, "nut.rfa")
    assert prod.write(p)["ok"] and os.path.isfile(p)
    assert [f for f in CL.check_file(p) if f["severity"] == CL.ERROR] == []


# -- 4. the nest gate: errors fail, warnings are recorded, nested units judged --

def _washer(sid):
    return F.make_generic_model(width_ft=1.5 * IN, depth_ft=1.5 * IN, height_ft=0.125 * IN,
                                name="Square Washer", start_id=sid)


def _nest(tmp, name):
    host = os.path.join(tmp, "host.rfa")
    if not os.path.isfile(host):
        F.make_generic_model(width_ft=2.0, depth_ft=0.5, height_ft=0.2,
                             name="Nest Host").write(host)
    out = os.path.join(tmp, name)
    return N.nest_family(host, out, _washer, [(0.0, 0.0, 0.0)]), out


def _injecting(real, *, unit_pred, severity):
    seen = []

    def check_file(path, unit=0):
        seen.append(unit)
        fs = list(real(path, unit=unit))
        if unit_pred(unit):
            fs.append({"severity": severity, "rule": "PROBE", "element": -1,
                       "class": "Probe", "message": f"probe {severity} in unit {unit}"})
        return fs
    return check_file, seen


def test_the_real_nest_judges_every_nested_unit_clean(tmp, monkeypatch):
    check, seen = _injecting(CL.check_file, unit_pred=lambda u: False, severity="none")
    monkeypatch.setattr(CL, "check_file", check)
    res, out = _nest(tmp, "clean.rfa")
    ver = res.proofs["verify"]
    assert res.ok and ver["ok"]
    assert ver["constraint_law"] == [] and ver["constraint_law_errors"] == 0
    assert ver["constraint_law_warnings"] == []
    units = CL.nested_units(out)
    assert len(units) == 1 and sorted(ver["constraint_law_nested"]) == sorted(units)
    assert sorted(set(seen)) == sorted({0} | set(units.values()))


def test_a_warning_is_recorded_and_does_not_fail_the_nest(tmp, monkeypatch):
    check, _ = _injecting(CL.check_file, unit_pred=lambda u: True, severity="warning")
    monkeypatch.setattr(CL, "check_file", check)
    res, out = _nest(tmp, "warned.rfa")
    ver = res.proofs["verify"]
    assert res.ok and os.path.isfile(out)
    assert ver["constraint_law_errors"] == 0
    assert len(ver["constraint_law_warnings"]) == 2           # host + the nested unit
    assert all(f["rule"] == "PROBE" for f in ver["constraint_law_warnings"])


def test_an_error_in_a_nested_unit_fails_the_nest(tmp, monkeypatch):
    check, _ = _injecting(CL.check_file, unit_pred=lambda u: u != 0, severity=CL.ERROR)
    monkeypatch.setattr(CL, "check_file", check)
    with pytest.raises(N.NestError, match=r"constraint law: 1 error\(s\)"):
        _nest(tmp, "bad.rfa")
    assert not os.path.isfile(os.path.join(tmp, "bad.rfa"))
