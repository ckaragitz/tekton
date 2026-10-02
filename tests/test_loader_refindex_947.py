"""Loaded and nested families never list a "Not a Reference" plane (#947).

A census of 421 born families: a reference plane whose Is-Reference is "Not a
Reference" (``RefPlane.m_refName`` 12) is in NO loaded/nested family's
reference index (0 / 1,312 ``FamilyReferenceIdxMgr`` entries) and in NO
symbol's strong references (0 / 3,349), while real Is-Reference codes always
are (Center (Elevation), code 7: 61 / 61 and 11 / 11).  The loader used to
copy every origin-defining plane with an int code into both lists, so every
height-driven generated family -- whose #787 Case B origin elevation plane
carries code 12 -- arrived in a project (or nested in a family) with an entry
no born file has.  ``rvt.famgen.loader`` now leaves code 12 out of both lists
(``_is_reference_code``); ``rvt.famload`` leaves it out of a loaded Revit-born
family's index.

Measured (#947 record, ``docs/inbox/param-drive.d/947-refindex.md``): a load
of the transformer / panelboard into each bundled base changes ONE partition
stream (-79 inflated bytes); every other stream is byte-identical.

Nothing here claims Revit behaviour (hard rule 4).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import ExitStack
from types import SimpleNamespace

import pytest

from conftest import context_constants, ladder_constants

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
NOT_A_REFERENCE = 12

pytestmark = [pytest.mark.skipif(not all(os.path.isfile(p) for p in BASES.values()),
                                 reason="bundled certified genesis bases missing"),
              pytest.mark.usefixtures("no_release_leak")]


@pytest.fixture
def release_leak_extra():
    from rvt import partitions as P
    from rvt.famgen import factory as FF, skeleton as FSK
    from rvt.genesis import types as GT
    return lambda: dict(ladder_constants(), **context_constants(),
                        **{"P.TERMINATOR": P.TERMINATOR, "FSK.FOOTER_TAG": FSK.FOOTER_TAG,
                           "GT._STATE": sorted(GT._STATE),
                           "FF.FORMATS_LATEST_SHA256_PREFIX": FF.FORMATS_LATEST_SHA256_PREFIX})


def _origin_codes(product):
    return sorted((e.obj or {}).get("m_refName") for e in product.doc.elements
                  if e.class_name == "RefPlane" and (e.obj or {}).get("m_definesOrigin"))


def _transformer(sid):
    from rvt.famgen import factory as F
    return F.make_transformer(start_id=sid)


@pytest.fixture(scope="module", autouse=True)
def loaded():
    """The transformer (a height-driven family: its origin planes are codes
    1, 4 AND 12) loaded once into each bundled base, plus one native nesting
    (:func:`_nest_trapeze`).  Built here so the lazy codec singletons are
    seeded before the leak guard's first snapshot."""
    from rvt.famgen import loader as L
    from rvt.frontdoor.release_ctx import host_release_context
    d = tempfile.mkdtemp(prefix="t947_")
    out = {}
    try:
        for yr, base in BASES.items():
            with host_release_context(base):
                host = L.survey_host(base)
                product = _transformer(host.watermark + 1)
                codes = _origin_codes(product)
                path = os.path.join(d, f"xfmr_{yr}.rvt")
                res = L.load_family_into_project(base, path, product, place=False,
                                                 validate=True)
            assert res.ok, res.stop_reason
            out[yr] = (path, res, codes)
        out["nested"] = _nest_trapeze(d)
        yield out
    finally:
        shutil.rmtree(d, True)


def _family_lists(path, unit=0):
    """{Family id: [reference-index codes]}, {FamilySymbol id: [strong-ref
    geomTags]} of one unit, read back under the file's own release."""
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    fams, syms = {}, {}
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        for eid in fi.ids_of_class(unit, "Family"):
            v = fi.value(unit, eid) or {}
            rim = ((v.get("m_oFamilyReferenceIdxMgr") or {}).get("value") or {})
            fams[eid] = [e["second"]["first"] for e in rim.get("m_idxToRefMap") or []]
        for eid in fi.ids_of_class(unit, "FamilySymbol"):
            v = fi.value(unit, eid) or {}
            syms[eid] = [r.get("m_geomTag") for r in v.get("m_strongRefs") or []]
    return fams, syms


def test_the_probe_family_really_carries_a_code_12_origin_plane(loaded):
    """Guard against a vacuous pass: the loaded product HAS the plane."""
    for yr in BASES:
        codes = loaded[yr][2]
        assert codes == [1, 4, NOT_A_REFERENCE], (yr, codes)


@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_no_code_12_in_a_loaded_projects_reference_index_or_strong_refs(loaded, year):
    path, res, _codes = loaded[year]
    fams, syms = _family_lists(path)
    plan = res.plan
    # ours: exactly the real centre codes, in both lists
    assert sorted(fams[plan.host_family_id]) == [1, 4]
    assert sorted(syms[plan.symbol_id]) == [1, 4]
    # and nothing anywhere in the project lists "Not a Reference"
    assert all(NOT_A_REFERENCE not in c for c in fams.values()), fams
    assert all(NOT_A_REFERENCE not in c for c in syms.values()), syms


def _nest_trapeze(d):
    """The nesting path authors through the same loader functions: a strut
    trapeze (origin planes 1, 4, 12) nested into a generated host family."""
    from rvt.famgen import factory as F, nest as N
    host = os.path.join(d, "host.rfa")
    F.make_generic_model(width_ft=4.0, depth_ft=1.0, height_ft=0.2, name="Nest Host").write(host)
    codes = _origin_codes(F.make_archetype(product="strut_trapeze"))
    out = os.path.join(d, "nested.rfa")
    res = N.nest_family(host, out,
                        lambda sid: F.make_archetype(product="strut_trapeze", start_id=sid),
                        [(0.0, 0.0, 0.0)])
    return out, res, codes


def test_no_code_12_when_a_height_driven_family_is_nested(loaded):
    from rvt.famgen import constraint_law as CL
    out, res, codes = loaded["nested"]
    assert NOT_A_REFERENCE in codes                     # not a vacuous pass
    fams, syms = _family_lists(out)
    assert sorted(fams[res.nested_family_id]) == [1, 4]
    assert sorted(syms[res.symbol_id]) == [1, 4]
    assert all(NOT_A_REFERENCE not in c for c in fams.values())
    assert all(NOT_A_REFERENCE not in c for c in syms.values())
    assert CL.check_file(out) == []


def test_is_reference_code():
    from rvt.famgen import loader as L
    assert L.NOT_A_REFERENCE == NOT_A_REFERENCE
    from rvt.famgen import skeleton as SK
    assert SK.REF_NAME["not_a_reference"] == L.NOT_A_REFERENCE
    assert [c for c in (0, 1, 4, 7, 8, 12, 13, None, "1") if L._is_reference_code(c)] == \
        [0, 1, 4, 7, 8, 13]


def test_famload_reference_index_skips_not_a_reference():
    """A Revit-born family loaded by ``rvt.famload``: a code-12 origin plane
    (a template's origin elevation plane) is left out of the index."""
    from rvt import famload as FL

    def rp(eid, code, origin=True):
        return SimpleNamespace(class_name="RefPlane", elem_id=eid,
                               obj={"m_definesOrigin": origin, "m_refName": code})
    doc = SimpleNamespace(elements=[rp(10, 1), rp(11, 4), rp(12, NOT_A_REFERENCE),
                                    rp(13, 7, origin=False)])
    plan = SimpleNamespace(abs_index={10: 4, 11: 5, 12: 6, 13: 7})
    rim = FL._reference_idx_mgr(doc, plan)
    assert [e["first"] for e in rim["value"]["m_idxToRefMap"]] == [4, 5]
    only12 = SimpleNamespace(elements=[rp(12, NOT_A_REFERENCE)])
    assert FL._reference_idx_mgr(only12, plan) is None
