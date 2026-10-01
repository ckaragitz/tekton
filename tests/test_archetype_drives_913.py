"""Every sheet-metal / channel archetype is built with its parts constrained
(#913, steer: "structure our code off the reference families").

These families use the in-plane mechanisms the owner's desktop verified (#904):
- symmetric ends;
- parts locked on a drive's planes;
- parts riding a plane at locked offsets (the P2 chain);
- "span" parts stretching between both planes.

A tray's rails ride its Tray Width, a box's walls ride and stretch with its Width
and Height, and every product's run follows its Length.  Read back from the written
file, every lock lies on its plane.  No route claims these families flex until each
has its own desktop verdict (hard rule 4).
"""
from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from rvt.families import FamilyIndex
from rvt.famgen import archetypes as AR
from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F
from conftest import ladder_constants

pytestmark = pytest.mark.usefixtures("no_release_leak")   # the read-back enters a release context


@pytest.fixture
def release_leak_extra():
    """The read-back climbs the read-side ladder: watch what it swaps, too."""
    return ladder_constants


@pytest.fixture(scope="module", autouse=True)
def _warm_default_decoder():
    """The first write in a process installs the bundled schema and seeds the
    native default ADocument decoder (standalone.install_schema, by design);
    do that once before the guard's first snapshot, so only a swap the
    read-back ladder leaves behind can turn the guard red."""
    d = tempfile.mkdtemp(prefix="t913w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)

EXPECT = {
    # product: {caption: (axis, edges locked on the planes, parts riding)}
    "cable_tray": {"Tray Width": ("y", 20, 6), "Length": ("x", 12, 0)},
    "wireway": {"Wireway Width": ("y", 4, 2), "Length": ("x", 8, 0)},
    "junction_box": {"Box Width": ("x", 8, 2), "Box Height": ("y", 4, 4)},
    "strut_channel": {"Length": ("x", 10, 0), "Section Width": ("y", 2, 4)},
    # #914: the side walls and the door latch ride Cabinet Width; its depth
    # is not driven (one-sided from the mounting plane, no verified anchor)
    "lighting_control_panel": {"Cabinet Width": ("x", 8, 3)},
}


@pytest.mark.parametrize("product", sorted(EXPECT))
def test_every_archetype_wires_its_drives(product):
    prod = F.make_archetype(product=product)
    got = {d["caption"]: (d["axis"], len(d["locks"]), (d.get("attach") or {}).get("parts", 0))
           for d in prod.drives}
    assert got == EXPECT[product]
    assert all(d.get("symmetric") for d in prod.drives)
    assert not any("not wired" in n or "not made" in n for n in prod.doc.notes), prod.doc.notes
    assert not any(e.obj.get("m_constrInfo") for e in prod.doc.elements)


def _read_back(prod):
    """Every sketch lock in the WRITTEN file, checked against its plane."""
    from contextlib import ExitStack
    from rvt.global_framing import enter_own_release
    d = tempfile.mkdtemp(prefix="t913_")
    try:
        path = os.path.join(d, "f.rfa")
        res = prod.write(path)
        assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0
        with ExitStack() as st:
            enter_own_release(st, path)
            fi = FamilyIndex(path)
            ids = fi.unit_records(0).get(102, {})
            E = {eid: (fi.class_name(r.class_id), fi.decode(0, eid, 102).value)
                 for eid, r in ids.items()
                 if fi.class_name(r.class_id) in ("RefPlane", "Alignment", "CurveElem")}
    finally:
        shutil.rmtree(d, True)
    planes = {k: v for k, (c, v) in E.items() if c == "RefPlane"}
    n = bad = 0
    for k, (c, v) in E.items():
        if c != "Alignment":
            continue
        g = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in v["m_witnessRefs"]]
        pl = [x for x in g if x["m_elemId"] in planes]
        cu = [x for x in g if x["m_elemId"] not in planes]
        if not pl or not cu or E.get(cu[0]["m_elemId"], ("",))[0] != "CurveElem":
            continue
        f, b = planes[pl[0]["m_elemId"]]["m_freeEnd"], planes[pl[0]["m_elemId"]]["m_bubbleEnd"]
        ax, at = (0, f[0]) if abs(f[0] - b[0]) < 1e-9 else (1, f[1])
        crv = E[cu[0]["m_elemId"]][1]["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
        ends = [crv["m_origin"][ax] + crv["m_dirVec"][ax] * t for t in crv["m_endParams"]]
        n += 1
        bad += any(abs(e - at) > 1e-6 for e in ends)
    return n, bad


@pytest.mark.parametrize("product", sorted(EXPECT))
def test_every_written_lock_lies_on_its_plane(product):
    prod = F.make_archetype(product=product)
    n, bad = _read_back(prod)
    assert n == len(DL._sketch_locks(prod.doc)) and n > 0 and bad == 0


def test_a_slotted_strut_channel_locks_only_its_end_segments():
    prod = F.make_archetype(product="strut_channel",
                            dimensions={"slot_length_in": 1.125, "slot_spacing_in": 2.0})
    length = next(d for d in prod.drives if d["caption"] == "Length")
    assert length["targets"] == 6 and len(length["locks"]) == 10   # 4 full parts + 2 end segments
    assert _read_back(prod)[1] == 0


@pytest.mark.parametrize("spec, ok", [
    ("autodesk.spec.aec:length-1.0.0", True),
    ("autodesk.spec.aec:length-2.0.0", True),
    ("autodesk.spec.aec.electrical:conduitSize-1.0.0", True),
    ("autodesk.spec.aec.electrical:cableTraySize-1.0.0", True),
    ("autodesk.spec.aec.piping:pipeSize-1.0.0", True),
    ("autodesk.spec.aec:number-1.0.0", False),
    ("autodesk.spec.aec:lengthy-1.0.0", False),
    ("", False),
])
def test_only_the_specs_born_families_label_are_drivable(spec, ok):
    class PE:
        obj = {"m_paramDef": {"value": {"m_specTypeId": {"m_typeId": spec}}}}
    assert bool(DL.drivable_spec(PE())) is ok


def test_the_lighting_control_panel_is_no_longer_the_unconstrained_baseline():
    """It was (#913) until its Cabinet Width drive and heights landed (#914);
    the drive pins live in EXPECT and tests/test_panel_drives_914.py."""
    prod = F.make_archetype(product="lighting_control_panel")
    assert [d["caption"] for d in prod.drives] == ["Cabinet Width"]
    assert prod.heights["wired"] == 3 and not prod.heights["refused"]


# ---- #919 review ----------------------------------------------------------

@pytest.mark.parametrize("key", ["cable_tray", "strut_channel", "wireway", "junction_box"])
def test_each_driven_archetype_says_its_constraints_are_unverified(key):
    lim = " ".join(AR.archetype(key).limits)
    assert "CONSTRAINTS AUTHORED (assembled family unverified)" in lim
    assert "values only" in lim


def test_wire_attach_refuses_a_finalized_document():
    prod = F.make_archetype(product="wireway")
    with pytest.raises(RuntimeError):
        DL.wire_attach(prod.doc, items=[], axis="x")       # finalized
