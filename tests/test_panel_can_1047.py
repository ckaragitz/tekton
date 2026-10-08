"""#1047 (steer #1046): a panelboard as its BACK BOX and COVER.

* five plates make an open-front box of ``Box Thickness`` walls; the cover sits on
  its front, the box's size when ``Surface Cover`` is on and lapping the opening
  1/2 in per side when it is off, shown by ``Show Cover`` (bound to its visibility);
* Width / Height / Depth / Mounting Height (per instance) drive the box; the cover,
  the working space and the dedicated space ride it; the clearance size parameters
  label the zones' own dimensions;
* one power connector whose voltage, poles, power factor, load and load class are
  ASSOCIATED to family parameters (poles as Revit's number-of-poles storage, the
  load class as a load-classification parameter), and two conduit connectors;
* VALID, 0 errors, on 2026, 2025 and 2024.

"Behaves in Revit" (the switches, the resizing) is a desktop claim (hard rule 4);
these pin what the file carries.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_clearance as EC  # noqa: E402
from rvt.famgen import formula as FM  # noqa: E402
from rvt.famgen import panel_can as PC  # noqa: E402
from rvt.famgen import param_binding as PB  # noqa: E402
from conftest import context_constants  # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")   # rows build inside release_build_context


@pytest.fixture
def release_leak_extra():
    return context_constants


IN = 1 / 12.0
PLATES = ("back", "left side", "right side", "bottom", "top")


@pytest.fixture(scope="module")
def can():
    return PC.make_panel_can()


def _forms(prod):
    return {f.params["role"]: f for f in prod.forms}


def _bound(form):
    ext = form.by_class("ExtrusionElem")[0]
    return {(d["m_famParamId"], d["m_elemPropId"]) for d in PB.bound(ext)}


def _extents(form):
    p = form.params
    cx, cy = p["center"][0], p["center"][1]
    return ((cx - p["width_ft"] / 2, cx + p["width_ft"] / 2),
            (cy - p["depth_ft"] / 2, cy + p["depth_ft"] / 2),
            (p["base_z_ft"], p["base_z_ft"] + p["height_ft"]))


def test_five_plates_make_an_open_front_box(can):
    f = _forms(can)
    W, D, H = 20 * IN, 5.75 * IN, (can.facts.get("height_in")) * IN
    t = PC.BOX_THICKNESS_IN * IN
    MH = (PC.MOUNT_TOP_IN - can.facts.get("height_in")) * IN
    box = [_extents(f[f"back box: {n}"]) for n in PLATES]
    xs = [a for e in box for a in e[0]]
    ys = [a for e in box for a in e[1]]
    zs = [a for e in box for a in e[2]]
    assert (min(xs), max(xs)) == pytest.approx((-W / 2, W / 2))
    assert (min(ys), max(ys)) == pytest.approx((0.0, D))          # the back on the wall plane
    assert (min(zs), max(zs)) == pytest.approx((MH, MH + H))      # the top at 78 in
    # every plate is one wall thick; nothing closes the front
    for (x, y, z) in box:
        assert min(x[1] - x[0], y[1] - y[0], z[1] - z[0]) == pytest.approx(t)
    assert all(e[1][1] <= D + 1e-9 for e in box)


def test_the_cover_switch_and_its_formulas():
    names = {n: FM.ParamRef(i, s) for i, (n, s) in enumerate((
        (PC.P_SURFACE, "autodesk.spec:spec.bool-1.0.0"),
        (PC.P_WIDTH, "autodesk.spec.aec:length-1.0.0"),
        (PC.P_HEIGHT, "autodesk.spec.aec:length-1.0.0"),
        (PC.P_MOUNT, "autodesk.spec.aec:length-1.0.0")), start=1)}
    W, H, MH = 20 * IN, 48 * IN, 30 * IN
    for surface, (cw, ch, cz) in ((1, (W, H, MH)), (0, (W + IN, H + IN, MH - IN / 2))):
        vals = {1: surface, 2: W, 3: H, 4: MH}
        got = [FM.evaluate(FM.parse_formula(PC.cover_formulas()[c], names)[0], vals)
               for c in (PC.P_COVER_W, PC.P_COVER_H, PC.P_COVER_Z)]
        assert got == pytest.approx([cw, ch, cz])


@pytest.mark.parametrize("surface", [True, False])
def test_the_cover_is_drawn_at_its_formula_values(surface):
    prod = PC.make_panel_can(surface=surface)
    W, H = 20 * IN, prod.facts.get("height_in") * IN
    MH = (PC.MOUNT_TOP_IN - prod.facts.get("height_in")) * IN
    lap = 0 if surface else PC.FLUSH_LAP_IN * IN
    x, y, z = _extents(_forms(prod)["cover"])
    assert (x[1] - x[0], z[0], z[1] - z[0]) == pytest.approx((W + 2 * lap, MH - lap, H + 2 * lap))
    assert y == pytest.approx((5.75 * IN, 5.75 * IN + PC.BOX_THICKNESS_IN * IN))
    vals = prod.doc.types[0][1]
    assert vals[prod.doc.params[PC.P_SURFACE].elem_id] == int(surface)
    assert vals[prod.doc.params[PC.P_FLUSH].elem_id] == int(not surface)


def test_the_switches_are_bound_to_visibility(can):
    f, P = _forms(can), can.doc.params
    assert (P[PC.P_SHOW_COVER].elem_id, PB.ELEM_PROP_VISIBLE) in _bound(f["cover"])
    assert (P[EC.P_FRONT_ON].elem_id, PB.ELEM_PROP_VISIBLE) in _bound(
        f["clearance: front working space"])
    assert (P[EC.P_TOP_ON].elem_id, PB.ELEM_PROP_VISIBLE) in _bound(f["clearance: top"])
    for n in PLATES:                                       # the box itself always shows
        assert not _bound(f[f"back box: {n}"])


def test_the_parameters_read_in_sections(can):
    P = can.doc.params
    for hdr, _g in PC.HEADERS:
        assert P[hdr].refs["formula"] == f'"{hdr}"'
    for cap in (PC.P_WIDTH, PC.P_HEIGHT, PC.P_DEPTH, PC.P_MOUNT, PC.P_SURFACE, PC.P_SHOW_COVER,
                PC.P_MIN_CLW, PC.P_FRONT_DEPTH, PC.P_TOP_H, PC.P_TO_FLOOR, PC.P_LOAD):
        assert P[cap].obj["m_instanceParam"] is True, cap
    assert P[PC.P_THICK].obj["m_instanceParam"] is False
    assert P[PC.P_CLW].refs["formula"] == (f"if({PC.P_WIDTH} < {PC.P_MIN_CLW}, "
                                           f"{PC.P_MIN_CLW}, {PC.P_WIDTH})")
    assert P[PC.P_FRONT_H].refs["formula"] == (f"if({PC.P_TO_FLOOR}, {PC.P_MOUNT} + "
                                               f"{PC.P_HEIGHT}, {PC.P_HEIGHT})")


def test_every_drive_is_wired(can):
    assert {d["caption"] for d in can.drives} >= {PC.P_WIDTH, PC.P_COVER_W, PC.P_DEPTH, PC.P_CLW}
    assert set(can.heights["captions"]) == {PC.P_MOUNT, PC.P_HEIGHT, PC.P_COVER_Z, PC.P_COVER_H,
                                            PC.P_TOP_H, PC.P_FRONT_H}
    assert can.heights["refused"] == []
    notes = "\n".join(can.doc.notes)
    assert "not wired" not in notes and "drives nothing" not in notes
    # the working space's depth: a labelled drive anchored on the box's front plane
    depth = next(d for d in can.drives if d["caption"] == PC.P_DEPTH)
    front = depth["planes"][1]
    dims = [e for e in can.doc.elements if e.class_name == "LinearDimString"
            and any(s.get("m_paramId") == can.doc.params[PC.P_FRONT_DEPTH].elem_id
                    for s in e.obj.get("m_ArrSegInfo") or [])]
    assert len(dims) == 1
    assert front in {r.get("m_elemId") for r in _refs(dims[0].obj)}


def _refs(o):
    out = []
    if isinstance(o, dict):
        if "m_elemId" in o:
            out.append(o)
        for v in o.values():
            out += _refs(v)
    elif isinstance(o, list):
        for v in o:
            out += _refs(v)
    return out


def test_the_power_connector_reads_the_family_parameters(can):
    P = can.doc.params
    (con,) = can.doc.connectors
    want = {(P[PC.P_VOLTAGE].elem_id, PC.ELEM_PROP_VOLTAGE),
            (P[PC.P_POLES].elem_id, PC.ELEM_PROP_POLES),
            (P[PC.P_PF].elem_id, PC.ELEM_PROP_POWER_FACTOR),
            (P[PC.P_LOAD].elem_id, PC.ELEM_PROP_APPARENT_LOAD),
            (P[PC.P_LOAD_CLASS].elem_id, PC.ELEM_PROP_LOAD_CLASS)}
    assert {(d["m_famParamId"], d["m_elemPropId"]) for d in PB.bound(con)} == want
    poles = P[PC.P_POLES].obj["m_pParamDef"]
    assert poles["ptr_class"] == "ParamDefNoOfPoles"
    assert (poles["value"]["m_lowBound"], poles["value"]["m_upBound"]) == (1, 3)
    assert con.obj["m_pDomain"]["value"]["m_nNumberOfPoles"] == 3
    lc = P[PC.P_LOAD_CLASS]
    assert lc.obj["m_pParamDef"]["ptr_class"] == "ElectricalLoadClassificationParamDef"
    assert can.doc.types[0][1][lc.elem_id]["m_elemId"] == \
        con.obj["m_pDomain"]["value"]["m_idLoadClassification"]


def test_two_conduit_connectors_on_the_box_top_and_bottom(can):
    f = _forms(can)
    mep = can.doc.mep_connectors
    assert len(mep) == 2
    hosts = {c.obj["m_oPlaneRef"]["value"]["m_geomRef"]["m_elemId"] for c in mep}
    assert hosts == {f["back box: top"].by_class("ExtrusionElem")[0].elem_id,
                     f["back box: bottom"].by_class("ExtrusionElem")[0].elem_id}
    assert sum(c.obj["m_pDomain"]["value"]["m_bIsPrimaryConnector"] for c in mep) == 1


def test_a_low_mounted_box_keeps_the_code_height_and_says_so():
    prod = PC.make_panel_can(mounting_height_in=24)
    assert PC.P_TO_FLOOR not in prod.doc.params and PC.P_FRONT_H not in prod.doc.params
    assert any("the code minimum, not switchable" in n for n in prod.doc.notes)
    assert prod.heights["refused"] == []


def test_a_given_size_is_said_and_a_box_with_no_inside_is_refused():
    prod = PC.make_panel_can(width_in=26, height_in=60, depth_in=6)
    assert any(n.startswith("box size GIVEN") for n in prod.notes)
    x, _y, z = _extents(_forms(prod)["back box: back"])
    assert (x[1] - x[0], z[1] - z[0]) == pytest.approx((26 * IN, 60 * IN))
    with pytest.raises(PC.PanelCanError):
        PC.make_panel_can(depth_in=0.4)


@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_the_written_family_validates(can, tmp_path, year):
    out = str(tmp_path / f"can{year}.rfa")
    if year == 2026:
        rep = can.write(out)
    else:
        from rvt.frontdoor import release_ctx as RC
        base = os.path.join(ROOT, "plugin", "assets", "genesis", f"G_ABPD_{year}.rvt")
        if not os.path.exists(base):
            pytest.skip(f"the pinned {year} base is not in this checkout")
        with RC.release_build_context(base):
            rep = PC.make_panel_can(surface=False).write(out)
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True


def test_the_cli_builds_it(tmp_path):
    out = tmp_path / "cli.rfa"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "panel-can",
                        "--cover", "flush", "--mounting-height", "18", "-o", str(out)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert out.exists() and "VALID (0 errors" in r.stdout
