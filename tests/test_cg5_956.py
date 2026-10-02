"""#956 -- CG5 corrected to the law Revit-born NESTED documents follow.

CG5 demanded that a labelled dimension's parameter be an element of the
dimension's own document unit.  Over the 421-family born library it fired 236
errors, every one in a nested family's document (0 on host documents): a
labelled ``LinearDimString`` whose parameter is a SHARED parameter
(``ParamElemExternal``) stored once, in the host document (unit 0).  No nested
unit of the library carries a ``ParamElemExternal`` of its own, element ids
never repeat across units, and the nested family's own ``Family`` (the one the
dimension's ``m_famId`` names) lists the parameter in ``m_familyParams`` in
236 / 236 cases.  The corrected law accepts exactly that form and nothing
looser (census: ``docs/inbox/param-drive.d/956-cg5.md``).

Synthetic positive / negative cases below; the corpus test skips cleanly when
the git-ignored ``samples/`` library is absent (fresh clone, CI).  Passing is
necessary, never sufficient (hard rule 4).
"""
import glob
import os
from collections import namedtuple

import pytest

from rvt.famgen import constraint_law as CL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(os.environ.get("TEKTON_ROOT") or ROOT, "samples", "evolve", "lib")

FAM, SHARED, LOCAL = 90, 500, 60


def _gref(eid):
    return {"m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "pid": -1,
                              "value": {"m_geomRef": {"m_elemId": eid,
                                                      "m_geomTag": 0,
                                                      "m_subTag": -1}}}}


def _plane_x(x):
    return {"m_freeEnd": [x, -5.0, 0.0], "m_bubbleEnd": [x, 5.0, 0.0],
            "m_cutVec": [0.0, 0.0, 1.0]}


def _dim(param, n_wit=2, n_seg=1, fam=FAM):
    return {"m_famId": fam,
            "m_witnessRefs": [_gref(30 + i) for i in range(n_wit)],
            "m_ArrSegInfo": [{"m_paramId": param}] * n_seg}


def _family(*params):
    return {"m_familyParams": {"ptr_class": "FamilyParams", "pid": -1, "value": {
        "m_params": [{"m_paramId": p} for p in params]}}}


def _nested(param, listed=(SHARED, LOCAL), **kw):
    """A nested unit's graph: two planes, one labelled dimension, the unit's
    own Family listing ``listed``, and a local ParamElemFamily."""
    return ([(10, "LinearDimString", _dim(param, **kw)),
             (FAM, "Family", _family(*listed)),
             (LOCAL, "ParamElemFamily", {})]
            + [(30 + i, "RefPlane", _plane_x(float(i))) for i in range(3)])


def _rules(findings):
    return sorted(f["rule"] for f in findings)


# -- the born form ----------------------------------------------------------

def test_a_host_shared_parameter_the_family_declares_is_in_the_document():
    assert CL.check_graph(_nested(SHARED), host_shared_params=[SHARED]) == []


def test_without_the_host_context_it_is_still_missing():
    # a nested document judged as if it were standalone: the label dangles
    f = CL.check_graph(_nested(SHARED))
    assert _rules(f) == ["CG5"] and "not in the document" in f[0]["message"]


def test_a_host_shared_parameter_the_family_does_not_list_fails():
    f = CL.check_graph(_nested(SHARED, listed=(LOCAL,)), host_shared_params=[SHARED])
    assert _rules(f) == ["CG5"] and f[0]["severity"] == CL.ERROR
    assert "does not list it" in f[0]["message"]


def test_a_host_shared_parameter_with_no_readable_family_fails():
    # m_famId names no decoded Family: the declaration cannot be shown -> error
    g = [t for t in _nested(SHARED) if t[0] != FAM]
    assert _rules(CL.check_graph(g, host_shared_params=[SHARED])) == ["CG5"]
    g = _nested(SHARED, fam=LOCAL)          # m_famId names a non-Family
    assert _rules(CL.check_graph(g, host_shared_params=[SHARED])) == ["CG5"]


def test_a_parameter_neither_local_nor_host_shared_still_fails():
    f = CL.check_graph(_nested(777, listed=(777,)), host_shared_params=[SHARED])
    assert _rules(f) == ["CG5"] and "not in the document" in f[0]["message"]


def test_local_parameters_are_unaffected():
    assert CL.check_graph(_nested(LOCAL), host_shared_params=[SHARED]) == []
    assert CL.check_graph(_nested(LOCAL)) == []


def test_the_shape_half_of_cg5_still_fires_in_a_nested_unit():
    for kw in ({"n_wit": 2, "n_seg": 2}, {"n_wit": 1, "n_seg": 1}):
        f = CL.check_graph(_nested(SHARED, **kw), host_shared_params=[SHARED])
        assert _rules(f) == ["CG5"] and "witness" in f[0]["message"]


def test_an_angular_dimension_gets_the_same_reading():
    g = _nested(SHARED)
    g[0] = (10, "AngularDim", _dim(SHARED))
    assert CL.check_graph(g, host_shared_params=[SHARED]) == []
    g[1] = (FAM, "Family", _family(LOCAL))
    assert _rules(CL.check_graph(g, host_shared_params=[SHARED])) == ["CG5"]


def test_cg5_is_live_and_the_class_is_pinned():
    assert "CG5" not in CL.RETIRED_RULES
    assert CL.HOST_SHARED_PARAM_CLASS == "ParamElemExternal"
    assert "Family" in CL.FILE_CLASSES


# -- check_file wiring: nested units get the HOST's shared parameters only ----

_Rec = namedtuple("_Rec", "class_id payload")
_CLASSES = {1: "LinearDimString", 2: "Family", 3: "RefPlane",
            4: "ParamElemExternal", 5: "ParamElemFamily"}


class _FakeIndex:
    """Two units: the host holds a shared parameter (500) and a family
    parameter (501); the nested unit (1) labels a dimension with each."""

    def __init__(self, path):
        self.schema = None
        nested_fam = _family(SHARED, 501)
        self.units = {
            0: {500: _Rec(4, {}), 501: _Rec(5, {})},
            1: {10: _Rec(1, _dim(SHARED)), 11: _Rec(1, _dim(501)),
                FAM: _Rec(2, nested_fam),
                30: _Rec(3, _plane_x(0.0)), 31: _Rec(3, _plane_x(1.0))},
        }

    def unit_records(self, unit):
        return {102: self.units.get(unit, {})}

    def ids_of_class(self, unit, name):
        return [e for e, r in self.units.get(unit, {}).items()
                if _CLASSES[r.class_id] == name]

    def class_name(self, cid):
        return _CLASSES[cid]


class _FakeDecoder:
    def __init__(self, schema):
        pass

    def decode_record(self, class_id, payload):
        return namedtuple("_O", "value")(payload)


def test_check_file_passes_only_host_shared_parameters_to_nested_units(monkeypatch):
    import rvt.families
    import rvt.objects
    monkeypatch.setattr(rvt.families, "FamilyIndex", _FakeIndex)
    monkeypatch.setattr(rvt.objects, "ObjectDecoder", _FakeDecoder)
    f = CL._check_file("fake.rfa", unit=1)
    # the shared one (500) resolves through the host; the host's FAMILY
    # parameter (501) is not a nested document's parameter -> CG5 on dim 11
    assert [(x["rule"], x["element"]) for x in f] == [("CG5", 11)]
    # the host unit itself gets no borrowed parameters
    assert CL._check_file("fake.rfa", unit=0) == []


# -- the born library (development instrument; absent in a fresh clone) ------

def _corpus():
    files = sorted(glob.glob(os.path.join(CORPUS, "**", "*.rfa"), recursive=True))
    if not files:
        pytest.skip("born reference library (samples/, git-ignored) not present")
    return files


@pytest.mark.slow
def test_the_law_is_silent_on_born_host_and_nested_units():
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("RVT_SKIP_LARGE set")
    files = _corpus()
    bad = []
    for i, p in enumerate(files):
        for u in [0] + sorted(set(CL.nested_units(p).values())):
            f = CL.check_file(p, unit=u)
            if f:
                # index + counts only: the library's names are not cited
                bad.append((i, u, sorted({x["rule"] for x in f}), len(f)))
    assert bad == [], f"{len(bad)} born units with findings: {bad[:10]}"
