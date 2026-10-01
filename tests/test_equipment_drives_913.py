"""Equipment families built with their parts constrained to parameter drives (#913).

Steer #913 ("structure our code off the reference families ... until everything is
complete"): every generated family's parts ride the parameter that sizes them.  The
panelboard got there in #914 (``tests/test_panel_drive_law_914.py``); this module pins
the same law on the next constructors, in product order:

* **transformer** (``make_transformer(drive="law")``): Width / Depth symmetric in-plane
  drives (``drive_law``) with the skids, cheeks, louvers, access panel, bolts and the
  clearance zones riding or spanning them, Height the #787 Case B cap-face chain
  (``height_law``) with the vent slot, drip lid and upper hardware riding the top;
* **troffer** (``make_luminaire(drive="law")``): Length / Width symmetric, Height;
  a downlight's 4-gon can gets Height only;
* **wiring device** (``make_device(drive="law")``): new Width / Height / Depth
  dimension parameters (the record's envelope, 'assumed' as the geometry already is),
  the plate on the Width / Height planes with the box spanning them, Depth the box's
  back face from the wall plane;
* **fan coil** (``make_fan_coil_unit(drive="law")``): Width (airflow depth) / Length
  symmetric with every box part riding, Height with the hangers and top faces riding;
* **house switchboard** (``make_house_switchboard(drive="law")``): Width / Depth / Height
  on the lineup box.

Every one is read back from the WRITTEN file on 2026 and 2025: each sketch lock's line
lies on its plane, the count equals what was authored, ``constraint_law.check_file`` is
empty.  The old behaviour stays behind ``drive=None`` (and ``"372"`` where the #372
first-solid chain existed); a refused spec leaves the file byte-identical to the build
without it, and every spec refused equals ``drive=None``.

Nothing here claims a family flexes in Revit: no assembled family has a desktop verdict
(hard rule 4) -- authored, assembled family unverified.
"""
from __future__ import annotations

import copy
import hashlib
import os
import shutil
import tempfile
from contextlib import ExitStack

import pytest

from rvt.families import FamilyIndex
from rvt.famgen import constraint_law as CL
from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F
from rvt.famgen import fan_coil as FC
from rvt.ifc import intent as I
from conftest import context_constants, ladder_constants

# builds enter the write-side release context (2025 targets) and the read-back
# climbs the read-side ladder: conftest's guard watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the native
    codec singletons (by design); do that once before the guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t913w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


TOL = 1e-6


def _switchboard(**kw):
    return I.make_house_switchboard(width_m=3.2, depth_m=1.2, height_m=2.3, **kw)


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t913sha_")
    try:
        path = os.path.join(d, "f.rfa")
        res = prod.write(path)
        assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _refusals(doc):
    return [n for n in doc.notes if "not wired" in n or "NOT wired" in n or "not made" in n]


# --------------------------------------------------------------------------- the wired chains

#: (in-plane drives: caption -> (edge locks, attach (parts, planes, locks) or None),
#:  heights: (specs wired, face locks, locked unlabelled))
EXPECT = {
    # Width 6 -> 8 (#933 review): the default 75 kVA working space is drawn at the
    # box's width (NEC 110.26(A)(2)), so it is a Width drive part, not a stayer
    "transformer": ({"Width": (8, (36, 14, 72)), "Depth": (8, (37, 10, 74))}, (23, 42, 22)),
    "transformer_dummy": ({"Width": (2, None), "Depth": (2, None)}, (1, 2, 0)),
    "troffer": ({"Length": (2, None), "Width": (2, None)}, (1, 2, 0)),
    "downlight": ({}, (1, 2, 0)),
    "device": ({"Width": (2, (1, 2, 2)), "Height": (2, (1, 2, 2))}, (1, 3, 0)),
    "fan_coil": ({"Width": (2, (12, 13, 24)), "Length": (2, (12, 11, 24))}, (3, 14, 2)),
    "switchboard": ({"Width": (2, None), "Depth": (2, None)}, (1, 2, 0)),
}

WIRED = {
    "transformer": lambda: F.make_transformer(name="E913X"),
    "transformer_dummy": lambda: F.make_transformer(name="E913XD", solid=False),
    "troffer": lambda: F.make_luminaire(name="E913T"),
    "downlight": lambda: F.make_luminaire(name="E913DL", kind="recessed-downlight"),
    "device": lambda: F.make_device(name="E913D"),
    "fan_coil": lambda: FC.make_fan_coil_unit(name="E913FC"),
    "switchboard": lambda: _switchboard(),
}


@pytest.mark.parametrize("key", sorted(WIRED))
def test_the_drives_are_wired_with_every_part_riding(key):
    prod = WIRED[key]()
    drives, (hw, hf, hl) = EXPECT[key]
    got = {d["caption"]: d for d in prod.drives}
    assert set(got) == set(drives)
    for cap, (locks, att) in drives.items():
        d = got[cap]
        assert len(d["locks"]) == locks and d["symmetric"] is True, (cap, d)
        if att is None:
            assert "attach" not in d
        else:
            assert (d["attach"]["parts"], d["attach"]["planes"], d["attach"]["locks"]) == att
    h = prod.heights
    assert (h["wired"], h["refused"], h["face_locks"], h["locked_unlabelled"]) == (hw, [], hf, hl)
    doc = prod.doc
    assert doc.born_drive_law is True
    assert not any(e.obj.get("m_constrInfo") for e in doc.elements)   # the born law: none
    assert all(int(a.obj["m_ownerDBViewId"]) == -1 for a in DL._sketch_locks(doc))
    assert CL.check_doc(doc) == []
    assert _refusals(doc) == [], doc.notes


# --------------------------------------------------------------------------- written-file read-back

def _plane(o):
    """(point, unit normal) of a RefPlane record."""
    f, b, c = o["m_freeEnd"], o["m_bubbleEnd"], o["m_cutVec"]
    u = [b[i] - f[i] for i in range(3)]
    n = (u[1] * c[2] - u[2] * c[1], u[2] * c[0] - u[0] * c[2], u[0] * c[1] - u[1] * c[0])
    m = sum(x * x for x in n) ** 0.5
    return (f, tuple(x / m for x in n)) if m > 1e-12 else None


def _locks_on_planes(path):
    """Every SKETCH lock of the written file: (locks read, locks off their plane) --
    the curve's GLine ends measured against the plane it is locked to."""
    with ExitStack() as st:
        from rvt.global_framing import enter_own_release
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})
        E = {eid: (fi.class_name(r.class_id), fi.decode(0, eid, 102).value)
             for eid, r in recs.items()
             if fi.class_name(r.class_id) in ("RefPlane", "Alignment", "CurveElem")}
    n = off = 0
    for _eid, (cls, v) in E.items():
        if cls != "Alignment":
            continue
        g = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in v["m_witnessRefs"]]
        pl = [x for x in g if E.get(x["m_elemId"], ("",))[0] == "RefPlane"]
        cu = [x for x in g if E.get(x["m_elemId"], ("",))[0] == "CurveElem"]
        if len(pl) != 1 or len(cu) != 1:
            continue                                   # a face lock, not a sketch lock
        crv = E[cu[0]["m_elemId"]][1]["m_pCurveDriver"]["value"]["m_pCrv"]
        assert crv["ptr_class"] == "GLine", crv["ptr_class"]
        c = crv["value"]
        p0, nrm = _plane(E[pl[0]["m_elemId"]][1])
        ends = [[c["m_origin"][i] + c["m_dirVec"][i] * t for i in range(3)]
                for t in c["m_endParams"]]
        n += 1
        off += any(abs(sum((e[i] - p0[i]) * nrm[i] for i in range(3))) > TOL for e in ends)
    return n, off


def _in_release(release, build):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return build()
    with RC.release_build_context(RC._bundled_base_of(release)):
        return build()


READ_BACK = dict(WIRED, **{
    "transformer_types": lambda: F.make_transformer(name="E913XT", types=[45, 75]),
    "troffer_2x2": lambda: F.make_luminaire(name="E913T2", size="2x2"),
    "switch": lambda: F.make_device("switch", name="E913S"),
    "junction_box": lambda: F.make_device("junction-box", name="E913J"),
    "fan_coil_non_fused": lambda: FC.make_fan_coil_unit(name="E913FN", fused=False),
    "fan_coil_cabinet_only": lambda: FC.make_fan_coil_unit(name="E913FS", length_in=20),
})


@pytest.mark.parametrize("release", [2026, 2025])
@pytest.mark.parametrize("key", sorted(READ_BACK))
def test_every_written_sketch_lock_lies_on_its_plane(key, release):
    d = tempfile.mkdtemp(prefix=f"t913_{release}_")
    try:
        def build():
            prod = READ_BACK[key]()
            path = os.path.join(d, "f.rfa")
            res = prod.write(path)
            assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
            return prod, path
        prod, path = _in_release(release, build)
        n, off = _locks_on_planes(path)
        assert n == len(DL._sketch_locks(prod.doc))
        assert off == 0, f"{off} of {n} sketch locks are off their planes"
        assert CL.check_file(path) == []
        assert _refusals(prod.doc) == [], prod.doc.notes
        assert prod.drives or prod.heights.get("wired")
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- who rides what

def _specs_of(monkeypatch, mod, fn, build):
    seen = {}
    real = getattr(mod, fn)

    def spy(*a, **k):
        seen["out"] = real(*a, **k)
        return seen["out"]
    monkeypatch.setattr(mod, fn, spy)
    build()
    return seen["out"]


def test_the_transformer_specs_name_who_rides_what(monkeypatch):
    (width, depth), heights = _specs_of(monkeypatch, F, "_transformer_drive_specs",
                                        lambda: F.make_transformer(name="E913XR"))
    # the default 75 kVA working space is drawn at the box's width, so it tracks
    # Width as a drive part (NEC 110.26(A)(2); #933 review)
    assert set(width["parts"]) == {"transformer enclosure", "clearance: top",
                                   "enclosure upper band (behind the vent slot)",
                                   "clearance: front working space"}
    span = width["attach"]["span"]
    assert "top cover" in span and "front access panel" in span
    assert all(n.startswith("vent slot louver") for n in span
               if n not in ("top cover", "front access panel"))
    # the skids, cheeks, side louver banks and bolts ride their own side; the
    # nameplate keeps its x
    rides = width["attach"]["lo"] + width["attach"]["hi"]
    assert {"base skid 1", "base skid 2", "vent slot cheek 1", "vent slot cheek 2"} <= set(rides)
    assert "nameplate" not in rides and "clearance: front working space" not in rides
    assert set(depth["parts"]) == {"transformer enclosure", "base skid 1", "base skid 2",
                                   "clearance: top"}
    assert {"front access panel", "nameplate",
            "clearance: front working space"} <= set(depth["attach"]["lo"])
    assert "hi" not in depth["attach"]            # nothing hangs off the back
    top = heights[0]
    assert top["caption"] == "Height" and top["parts"]["top cover"] == {"end": "hi"}
    assert top["parts"]["clearance: top"] == {"start": "hi"}
    # the body's top face rides the top with the slot band standing on it
    body = [h for h in heights[1:] if "transformer enclosure" in h["parts"]]
    assert len(body) == 1 and body[0]["parts"]["transformer enclosure"] == {"end": "lo"}
    assert "enclosure upper band (behind the vent slot)" in body[0]["parts"]


def test_the_fan_coil_specs_name_who_rides_what(monkeypatch):
    (width, length), heights = _specs_of(monkeypatch, FC, "fan_coil_drive_specs",
                                         lambda: FC.make_fan_coil_unit(name="E913FR"))
    assert set(width["parts"]) == {"fan coil cabinet"} == set(length["parts"])
    assert width["attach"]["span"] == ["bottom access panel"]
    assert {"supply duct collar", "fused disconnect switch",
            "clearance: front working space"} <= set(width["attach"]["hi"])
    assert {"return filter rack", "unit control box"} <= set(width["attach"]["lo"])
    assert set(length["attach"]["span"]) == {"supply duct collar", "return filter rack",
                                             "bottom access panel"}
    assert {"unit control box", "fused disconnect switch", "disconnect operating handle",
            "disconnect rating label", "clearance: front working space"} <= set(
                length["attach"]["hi"])
    assert heights[0]["parts"]["fan coil cabinet"] == {"start": "lo", "end": "hi"}
    # the disconnect is centred on the cabinet's height: it keeps its place
    assert not any("fused disconnect switch" in h["parts"] for h in heights)


def test_the_fan_coil_says_its_round_parts_do_not_ride():
    prod = FC.make_fan_coil_unit(name="E913FN2")
    assert any("round parts" in n and "NOT tied to the drives" in n for n in prod.doc.notes)


def test_the_device_dimensions_are_the_record_envelope():
    prod = F.make_device(name="E913DV")
    doc = prod.doc
    row = doc.types[doc.current_type][1]
    fx = prod.facts
    for cap, key in (("Width", "plate_width_in"), ("Height", "plate_height_in"),
                     ("Depth", "box_depth_in")):
        assert abs(row[doc.params[cap].elem_id] - F.inches(fx.get(key))) < 1e-9, cap
    # the envelope is the record's ASSUMED geometry, surfaced as before
    assert any("UNVERIFIED (assumed)" in n for n in prod.notes)


def test_multi_type_transformer_notes_say_what_the_rows_label():
    prod = F.make_transformer(name="E913XT2", types=[45, 75])
    assert not any("geometry is not label-driven yet" in n for n in prod.notes)
    assert any("labelled by the rows' Width / Depth / Height" in n and "UNVERIFIED" in n
               for n in prod.notes)


def test_plan_drive_spec_reads_the_parts_off_their_extents():
    spec = F._plan_drive_spec("Width", "x", -1.0, 1.0, [
        ("body", (-1.0, 1.0)), ("lid", (-1.1, 1.1)), ("foot +", (0.8, 1.0)),
        ("foot -", (-1.0, -0.8)), ("badge", (-0.1, 0.1)), ("label", (0.2, 0.4))],
        span=["lid"], stay=["label"])
    assert spec["parts"] == {"body": ("lo", "hi")} and spec["symmetric"] is True
    assert spec["attach"] == {"lo": ["foot -"], "hi": ["foot +"], "span": ["lid"]}


def test_unique_names_number_only_repeated_roles():
    assert F._unique_names(["a", "b", "a", "c", "a"]) == ["a 1", "b", "a 2", "c", "a 3"]


# --------------------------------------------------------------------------- the old behaviour, kept

@pytest.mark.parametrize("build", [
    lambda: F.make_transformer(name="E913N", drive=None),
    lambda: F.make_luminaire(name="E913N", drive=None),
    lambda: F.make_device(name="E913N", drive=None),
    lambda: FC.make_fan_coil_unit(name="E913N", drive=None),
    lambda: _switchboard(drive=None),
])
def test_no_drive_wires_nothing(build):
    prod = build()
    doc = prod.doc
    assert (len(doc.by_class("Alignment")), len(doc.by_class("LinearDimString"))) == (0, 0)
    assert not getattr(doc, "born_drive_law", False)


def test_the_device_without_drives_carries_no_dimension_parameters():
    """``drive=None`` is the device as it was: no Width / Height / Depth at all."""
    assert not {"Width", "Height", "Depth"} & set(F.make_device(name="E913N", drive=None).doc.params)
    assert {"Width", "Height", "Depth"} <= set(F.make_device(name="E913L").doc.params)


@pytest.mark.parametrize("build", [
    lambda: F.make_luminaire(name="E913C", drive="372"),
    lambda: _switchboard(drive="372"),
])
def test_the_old_372_chain_is_kept_behind_the_flag(build):
    prod = build()
    doc = prod.doc
    assert prod.drives == [] and prod.heights == {}
    assert not getattr(doc, "born_drive_law", False)
    assert (len(doc.by_class("Alignment")), len(doc.by_class("LinearDimString"))) == (4, 2)
    assert CL.check_doc(doc) == []


@pytest.mark.parametrize("build", [
    lambda: F.make_transformer(name="E913B", drive="372"),
    lambda: F.make_luminaire(name="E913B", drive="flex"),
    lambda: F.make_device(name="E913B", drive="372"),
    lambda: _switchboard(drive="flex"),
])
def test_an_unknown_drive_mode_is_refused(build):
    with pytest.raises(F.FactoryError):
        build()


def test_an_unknown_fan_coil_drive_mode_is_refused():
    with pytest.raises(F.FactoryError):           # a famspec refusal, like every kind
        FC.make_fan_coil_unit(name="E913B", drive="372")


@pytest.mark.parametrize("kva, tracks", [(15, False), (45, False), (75, True), (225, True)])
def test_the_transformer_working_space_tracks_width_only_where_it_is_the_box_width(kva, tracks):
    """NEC 110.26(A)(2): the greater of the equipment width or 30 in (#933
    review). Drawn at the box's width (75 kVA up) the zone is a Width drive
    part; drawn at the 30 in minimum it stays. The note says which, and that
    the boundary itself is not re-derived."""
    prod = F.make_transformer(kva=kva)
    (width,) = [d for d in prod.drives if d["caption"] == "Width"]
    base = [d for d in F.make_transformer(kva=15).drives if d["caption"] == "Width"][0]
    note = next(n for n in prod.doc.notes if n.startswith("front working space (NEC"))
    if tracks:
        assert "tracks Width" in note and "BELOW 30 in" in note
        assert len(width["locks"]) == len(base["locks"]) + 2
    else:
        assert "stays" in note and "ABOVE 30 in" in note
        assert len(width["locks"]) == len(base["locks"])
    assert "unverified" in note


# --------------------------------------------------------------------------- refusals

def _patched(monkeypatch, mod, fn, edit, build):
    real = getattr(mod, fn)

    def specs(*a, **k):
        d, h = real(*a, **k)
        d, h = copy.deepcopy(d), copy.deepcopy(h)
        edit(d, h)
        return d, h
    monkeypatch.setattr(mod, fn, specs)
    try:
        return build()
    finally:
        monkeypatch.setattr(mod, fn, real)


def _drop(i):
    def edit(d, _h):
        del d[i]
    return edit


XFMR = (F, "_transformer_drive_specs", lambda: F.make_transformer(name="E913XS"))
FANC = (FC, "fan_coil_drive_specs", lambda: FC.make_fan_coil_unit(name="E913FS2"))


@pytest.mark.parametrize("target", [XFMR, FANC], ids=["transformer", "fan_coil"])
@pytest.mark.parametrize("bad, control", [
    # a part name that matches nothing
    (lambda d, h: d[0]["parts"].update({"no such part": ("lo", "hi")}), _drop(0)),
    # planes that disagree with the row
    (lambda d, h: d[1].update(lo=d[1]["lo"] - 0.1), _drop(1)),
], ids=["missing-part", "planes-off-the-row"])
def test_a_refused_drive_leaves_the_file_byte_identical(monkeypatch, target, bad, control):
    mod, fn, build = target
    prod = _patched(monkeypatch, mod, fn, bad, build)
    ref = _patched(monkeypatch, mod, fn, control, build)
    assert len(prod.drives) == 1
    assert any("not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(ref)


@pytest.mark.parametrize("target", [XFMR, FANC], ids=["transformer", "fan_coil"])
def test_a_refused_attach_keeps_its_drive_and_touches_nothing_else(monkeypatch, target):
    mod, fn, build = target

    def bad(d, _h):
        d[0]["attach"]["hi"] = d[0]["attach"]["hi"] + ["no such part"]

    def control(d, _h):
        del d[0]["attach"]
    prod = _patched(monkeypatch, mod, fn, bad, build)
    ref = _patched(monkeypatch, mod, fn, control, build)
    assert len(prod.drives) == 2 and "attach" not in prod.drives[0]
    assert any("parts attached to 'Width' not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(ref)


@pytest.mark.parametrize("target", [XFMR, FANC], ids=["transformer", "fan_coil"])
def test_a_refused_height_leaves_the_file_byte_identical(monkeypatch, target):
    mod, fn, build = target

    def bad(_d, h):
        h[-1]["lo" if h[-1]["hi"] == "top" else "hi"] = 99.0      # off every face

    def control(_d, h):
        del h[-1]
    prod = _patched(monkeypatch, mod, fn, bad, build)
    ref = _patched(monkeypatch, mod, fn, control, build)
    assert prod.heights["refused"] and prod.heights["wired"] == ref.heights["wired"]
    assert _sha(prod) == _sha(ref)


@pytest.mark.parametrize("target, undriven", [
    (XFMR, lambda: F.make_transformer(name="E913XS", drive=None)),
    (FANC, lambda: FC.make_fan_coil_unit(name="E913FS2", drive=None)),
], ids=["transformer", "fan_coil"])
def test_every_spec_refused_is_the_undriven_family(monkeypatch, target, undriven):
    mod, fn, build = target

    def bad(d, h):
        for s in d:
            s["caption"] = "Voltage"                   # not a length: every drive refused
        h[:] = [dict(h[0], hi=h[0]["hi"] + 1.0)]       # off the cap faces
    prod = _patched(monkeypatch, mod, fn, bad, build)
    assert prod.drives == [] and prod.heights["wired"] == 0
    assert any("drives NOT wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(undriven())
