"""#876 part B: a profile map PROPOSED from the user's own families.

``tools/profile_map_from_rfa.py`` reads which axis each shared LENGTH parameter's
labelled dimensions run along (``LinearDimString.m_pDimLine.m_dirVec``) and proposes
library parameter -> the generated family's parameter of that role (Width x, Depth y,
Height z).  One parameter per axis -- the one labelling it in the most families; a
part's size, a disagreement, a non-length, an oblique dimension or a tie is listed
with its reason, never guessed.

Synthetic only: our own generated families as the "library", made-up GUIDs (rule 6).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import profile_map_from_rfa as PM  # noqa: E402

L = "autodesk.spec.aec:length-2.0.0"


@pytest.mark.parametrize("vec,axis", [([1.0, 0.0, 0.0], "x"), ([-1.0, 0.0, 0.0], "x"),
                                      ([0.0, 1.0, 0.0], "y"), ([0.0, 0.0, -1.0], "z"),
                                      ([0.7071, 0.7071, 0.0], None), (None, None), ([1.0], None)])
def test_a_dimension_line_has_an_axis_only_when_aligned(vec, axis):
    assert PM.axis_of(vec) == axis


def _fam(cat=-1, **params):
    return {"category": cat, "params": {g: {"name": n, "spec": s, "axes": a}
                                        for g, (n, s, a) in params.items()}}


def test_one_parameter_per_axis_the_one_most_families_size_by():
    fams = [_fam(g1=("Zz W", L, {"x": 2}), g2=("Zz D", L, {"y": 1}), g3=("Zz H", L, {"z": 4}))
            for _ in range(3)]
    fams.append(_fam(g4=("Zz Part W", L, {"x": 1})))
    fams.append(_fam(g4=("Zz Part W", L, {"x": 3})))
    mapping, report = PM.propose(fams)
    assert mapping == {"g1": "Width", "g2": "Depth", "g3": "Height"}
    part = next(r for r in report if r["guid"] == "g4")
    assert "'Zz W' labels the x axis in more families (3 vs 2)" in part["why"]


@pytest.mark.parametrize("fams,why", [
    ([_fam(g=("Zz N", "autodesk.spec.aec:number-1.0.0", {"x": 1}))] * 2, "not a length (number-1.0.0)"),
    ([_fam(g=("Zz O", L, {"oblique": 2}))] * 2, "its dimensions are not along an axis"),
    ([_fam(g=("Zz One", L, {"x": 1}))], "labels a dimension in 1 family(ies), fewer than 2"),
    ([_fam(g=("Zz Mix", L, {"x": 1}))] * 2 + [_fam(g=("Zz Mix", L, {"y": 1}))],
     "its families disagree on the axis"),
])
def test_what_cannot_be_proposed_is_said(fams, why):
    mapping, report = PM.propose(fams)
    assert mapping == {} and report[0]["why"].startswith(why)


def test_a_tie_on_an_axis_is_not_guessed():
    fams = [_fam(a=("Zz A", L, {"x": 1}), b=("Zz B", L, {"x": 1}))] * 2
    mapping, report = PM.propose(fams)
    assert mapping == {}
    assert all("2 parameters label the x axis in 2 families each" in r["why"] for r in report)


def test_the_category_filter_and_custom_targets():
    fams = [_fam(1, g=("Zz W", L, {"x": 1}))] * 2 + [_fam(2, h=("Zz Run", L, {"y": 1}))] * 2
    assert PM.propose(fams, category=1)[0] == {"g": "Width"}
    assert PM.propose(fams, category=2, targets={"y": "Length"})[0] == {"h": "Length"}
    assert "no target parameter named for the y axis" in \
        PM.propose(fams, category=2, targets={"x": "Width"})[1][0]["why"]


SP_TXT = ("# synthetic\n*META\tVERSION\tMINVERSION\nMETA\t2\t1\n*GROUP\tID\tNAME\nGROUP\t1\tDims\n"
          "*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\tUSERMODIFIABLE\n"
          + "".join(f"PARAM\t0000eeee-0000-4000-8000-00000000000{i}\t{n}\tLENGTH\t\t1\t1\t\t1\n"
                    for i, n in ((1, "Width"), (2, "Depth"), (3, "Height"))))


def test_the_cli_reads_the_axes_from_real_families(tmp_path):
    """A 'library' of our own generated equipment, its sizes SHARED parameters: the
    labelled dimensions are read from the written files and proposed by role."""
    from rvt.famgen import factory as F
    sp = tmp_path / "sp.txt"
    sp.write_text(SP_TXT, encoding="utf-8")
    lib = tmp_path / "lib"
    lib.mkdir()
    F.make_transformer(kva=45, shared_params=str(sp)).write(str(lib / "a.rfa"), validate=False,
                                                            provenance=False)
    F.make_panelboard(shared_params=str(sp)).write(str(lib / "b.rfa"), validate=False,
                                                   provenance=False)
    out = tmp_path / "map.json"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "profile_map_from_rfa.py"),
                        str(lib), "--category", "-2001040", "-o", str(out), "--json"],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "0000eeee-0000-4000-8000-000000000001": "Width",
        "0000eeee-0000-4000-8000-000000000002": "Depth",
        "0000eeee-0000-4000-8000-000000000003": "Height"}
    summary = json.loads(r.stdout)
    assert (summary["read"], summary["proposed"], summary["errors"]) == (2, 3, [])


# --- #971 review ----------------------------------------------------------------------

def test_the_axis_is_ranked_by_its_own_votes():
    a = [_fam(a=("Zz A", L, {"x": 1}))] * 8 + [_fam(a=("Zz A", L, {"y": 1}))] * 2
    b = [_fam(b=("Zz B", L, {"x": 1}))] * 9
    mapping, report = PM.propose(a + b)
    assert mapping == {"b": "Width"}
    row = next(r for r in report if r["guid"] == "a")
    assert "'Zz B' labels the x axis in more families (9 vs 8)" in row["why"]


def test_a_family_labelling_two_axes_equally_votes_for_neither():
    fams = [_fam(g=("Zz Both", L, {"x": 1, "y": 1}))] * 2
    mapping, report = PM.propose(fams)
    assert mapping == {} and report[0]["axis"] == "mixed"
    assert report[0]["why"] == "its families label it along two axes equally"


def test_families_split_evenly_between_two_axes_are_not_guessed():
    fams = [_fam(g=("Zz Even", L, {"x": 1}))] * 2 + [_fam(g=("Zz Even", L, {"y": 1}))] * 2
    mapping, report = PM.propose(fams, min_share=0.5)
    assert mapping == {} and report[0]["axis"] == "mixed"
    assert report[0]["why"].startswith("its families label it along two axes equally")
