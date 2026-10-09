"""#1047 (steer #1046): a panelboard as its BACK BOX and TRIM.

* five plates make an open-front box; the trim sits on its front, the box's size when
  ``Surface Trim`` is on and lapping the opening on every side when it is off, shown by
  ``Show Trim`` (bound to its visibility);
* Width / Height / Depth / Mounting Height (per instance) drive the box; the trim, the
  working space and the dedicated space ride it; the clearance size parameters label
  the zones' own dimensions, the working space's width as a chain that stays positive
  at any shift;
* one power connector whose voltage, poles, power factor, load and load class are
  ASSOCIATED to family parameters, and two conduit connectors;
* VALID, 0 errors, on 2026, 2025 and 2024 -- and the values / formulas READ BACK from
  the written file, not only the in-memory rows.

"Behaves in Revit" (the switches, the resizing) is a desktop claim (hard rule 4);
these pin what the file carries.
"""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import ExitStack

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_clearance as EC  # noqa: E402
from rvt.famgen import formula as FM  # noqa: E402
from rvt.famgen import panel_can as PC  # noqa: E402
from rvt.famgen import param_binding as PB  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402
from conftest import context_constants  # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")   # rows build inside release_build_context


@pytest.fixture
def release_leak_extra():
    return context_constants


IN = 1 / 12.0
PLATES = ("back", "left side", "right side", "bottom", "top")
LENGTH = "autodesk.spec.aec:length-1.0.0"
BOOL = "autodesk.spec:spec.bool-1.0.0"


def readback(path):
    """``{caption: {value, int, str, elem, formula}}`` of the WRITTEN family's own
    parameters (its self Family's current values), read under the file's own release."""
    from rvt import global_framing as GF
    from rvt.families import FamilyIndex
    with ExitStack() as st:
        GF.enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})
        caps, fam = {}, None
        for e, r in recs.items():
            cls = fi.class_name(r.class_id)
            if cls.startswith("ParamElem"):
                v = fi.decode(0, e, 102).value
                caps[int(e)] = ((v.get("m_pParamDef") or {}).get("value") or {}).get("m_caption")
            elif cls == "Family":
                v = fi.decode(0, e, 102).value
                if v.get("m_surrogateId") == -1:
                    fam = v
    out = {}
    for q in fam["m_familyParams"]["value"]["m_params"]:
        if q["m_paramId"] in caps:
            out[caps[q["m_paramId"]]] = {"value": q["m_value"], "int": q["m_int"],
                                         "str": q["m_str"], "elem": q["m_elemId"],
                                         "formula": q.get("m_oExpression"),
                                         "id": q["m_paramId"], "instance": q["m_instance"]}
    return out


@pytest.fixture(scope="module")
def can(tmp_path_factory):
    prod = PC.make_panel_can()
    path = str(tmp_path_factory.mktemp("can") / "can.rfa")
    rep = prod.write(path)
    return prod, path, rep


@pytest.fixture(scope="module")
def flush(tmp_path_factory):
    prod = PC.make_panel_can(surface=False)
    path = str(tmp_path_factory.mktemp("flush") / "flush.rfa")
    rep = prod.write(path)
    return prod, path, rep


def _forms(prod):
    return {f.params["role"]: f for f in prod.forms}


def _bound(element):
    return {(d["m_famParamId"], d["m_elemPropId"]) for d in PB.bound(element)}


def _extents(form):
    p = form.params
    cx, cy = p["center"][0], p["center"][1]
    return ((cx - p["width_ft"] / 2, cx + p["width_ft"] / 2),
            (cy - p["depth_ft"] / 2, cy + p["depth_ft"] / 2),
            (p["base_z_ft"], p["base_z_ft"] + p["height_ft"]))


def test_five_plates_make_an_open_front_box(can):
    prod = can[0]
    f = _forms(prod)
    W, D, H = 20 * IN, 5.75 * IN, prod.facts.get("height_in") * IN
    t = PC.BOX_THICKNESS_IN * IN
    MH = (PC.MOUNT_TOP_IN - prod.facts.get("height_in")) * IN
    box = [_extents(f[f"back box: {n}"]) for n in PLATES]
    assert (min(a for e in box for a in e[0]), max(a for e in box for a in e[0])) == \
        pytest.approx((-W / 2, W / 2))
    assert (min(a for e in box for a in e[1]), max(a for e in box for a in e[1])) == \
        pytest.approx((0.0, D))                                   # the back on the wall plane
    assert (min(a for e in box for a in e[2]), max(a for e in box for a in e[2])) == \
        pytest.approx((MH, MH + H))                               # the top at 78 in
    for (x, y, z) in box:                                         # every plate one wall thick
        assert min(x[1] - x[0], y[1] - y[0], z[1] - z[0]) == pytest.approx(t)


def test_the_written_values_are_the_built_ones(can, flush):
    W, D = 20 * IN, 5.75 * IN
    lap = PC.FLUSH_LAP_IN * IN
    for (prod, path, _rep), surface in ((can, True), (flush, False)):
        H = prod.facts.get("height_in") * IN
        MH = (PC.MOUNT_TOP_IN - prod.facts.get("height_in")) * IN
        rb = readback(path)
        assert [rb[c]["value"] for c in (PC.P_WIDTH, PC.P_HEIGHT, PC.P_DEPTH, PC.P_MOUNT)] == \
            pytest.approx([W, H, D, MH])
        assert (rb[PC.P_SURFACE]["int"], rb[PC.P_FLUSH]["int"]) == (int(surface), int(not surface))
        want = (W, H, MH) if surface else (W + 2 * lap, H + 2 * lap, MH - lap)
        assert [rb[c]["value"] for c in (PC.P_TRIM_W, PC.P_TRIM_H, PC.P_TRIM_Z)] == \
            pytest.approx(want)
        x, _y, z = _extents(_forms(prod)["trim"])                 # ... and the trim drawn so
        assert (x[1] - x[0], z[0], z[1] - z[0]) == pytest.approx((want[0], want[2], want[1]))
        assert rb[PC.P_VOLTAGE]["value"] == pytest.approx(SK.volts(208))
        assert rb[PC.P_POLES]["int"] == 3
        # the tagging contract carries the catalog facts, as make_panelboard writes them
        assert rb["PanelName"]["str"] == "PANEL"
        assert (rb["Phases"]["int"], rb["Wires"]["int"], rb["NumberOfCircuits"]["int"]) == (3, 4, 42)
        assert rb["MainsRating"]["value"] == pytest.approx(225.0)         # amperes are internal units


def test_every_formula_is_written_and_agrees_with_its_inputs(can, flush):
    for prod, path, _rep in (can, flush):
        assert not any("NOT written" in n for n in prod.doc.notes)
        rb = readback(path)
        table = {n: FM.ParamRef(pe.elem_id, SK._formula_spec(pe))
                 for n, pe in prod.doc.params.items()}
        vals = {}
        for n, pe in prod.doc.params.items():
            r = rb[n]
            spec = SK._formula_spec(pe)
            vals[pe.elem_id] = (r["str"] if FM.is_text(spec) else r["int"]
                                if spec in (BOOL, SK.SPEC_INTEGER) else r["value"])
        n_formulas = 0
        for n, pe in prod.doc.params.items():
            text = pe.refs.get("formula")
            if not text:
                continue
            n_formulas += 1
            assert rb[n]["formula"], f"{n}: formula not written"
            got = FM.evaluate(FM.parse_formula(text, table)[0], vals)
            assert got == pytest.approx(vals[pe.elem_id]), n
        assert n_formulas >= 16


def test_the_trim_formulas_follow_the_switch():
    names = {n: FM.ParamRef(i, s) for i, (n, s) in enumerate((
        (PC.P_SURFACE, BOOL), (PC.P_WIDTH, LENGTH), (PC.P_HEIGHT, LENGTH),
        (PC.P_MOUNT, LENGTH)), start=1)}
    W, H, MH = 20 * IN, 48 * IN, 30 * IN
    for lap_in in (PC.FLUSH_LAP_IN, 0.5):
        lap = lap_in * IN
        for surface, want in ((1, (W, H, MH)), (0, (W + 2 * lap, H + 2 * lap, MH - lap))):
            got = [FM.evaluate(FM.parse_formula(PC.trim_formulas(lap_in)[c], names)[0],
                               {1: surface, 2: W, 3: H, 4: MH})
                   for c in (PC.P_TRIM_W, PC.P_TRIM_H, PC.P_TRIM_Z)]
            assert got == pytest.approx(want)


def test_each_shift_is_applied_from_its_own_side_and_clamped():
    names = {n: FM.ParamRef(i, s) for i, (n, s) in enumerate((
        (PC.P_CENTERED, BOOL), (PC.P_SHIFT_L, LENGTH), (PC.P_SHIFT_R, LENGTH),
        (PC.P_WS_W, LENGTH), (PC.P_WIDTH, LENGTH)), start=1)}
    left = FM.parse_formula(PC.shift_formula(PC.P_SHIFT_L), names)[0]
    right = FM.parse_formula(PC.shift_formula(PC.P_SHIFT_R), names)[0]
    W, CLW = 20 * IN, 30 * IN                                     # 5 in of room each side
    for centred, sl, sr, want_l, want_r in (
            (1, 3 * IN, 2 * IN, 0.0, 0.0), (0, 3 * IN, 2 * IN, 3 * IN, 2 * IN),
            (0, 8 * IN, 0.0, 5 * IN, 0.0), (0, -4 * IN, 9 * IN, 0.0, 5 * IN)):
        vals = {1: centred, 2: sl, 3: sr, 4: CLW, 5: W}
        assert FM.evaluate(left, vals) == pytest.approx(want_l)
        assert FM.evaluate(right, vals) == pytest.approx(want_r)
    # a box at least the minimum wide leaves no room: no shift either way
    assert FM.evaluate(right, {1: 0, 2: 0.0, 3: 3 * IN, 4: 32 * IN, 5: 32 * IN}) == 0.0


def test_the_left_edge_keeps_the_working_space_over_the_box(can):
    prod = can[0]
    P = prod.doc.params
    # each applied shift reads ITS OWN side's shift
    assert P[PC.P_SHIFT_L_ON].refs["formula"] == PC.shift_formula(PC.P_SHIFT_L)
    assert P[PC.P_SHIFT_R_ON].refs["formula"] == PC.shift_formula(PC.P_SHIFT_R)
    names = {n: FM.ParamRef(P[n].elem_id, LENGTH)
             for n in (PC.P_WS_W, PC.P_SHIFT_L_ON, PC.P_SHIFT_R_ON)}
    edge = FM.parse_formula(P[PC.P_WS_LEFT].refs["formula"], names)[0]
    W, CLW = 20 * IN, 30 * IN
    for l, r in ((0.0, 0.0), (0.0, 5 * IN), (5 * IN, 0.0)):        # applied shifts, clamped
        got = FM.evaluate(edge, {P[PC.P_WS_W].elem_id: CLW, P[PC.P_SHIFT_L_ON].elem_id: l,
                                 P[PC.P_SHIFT_R_ON].elem_id: r})
        assert got >= W / 2 - 1e-9 and CLW - got >= W / 2 - 1e-9   # spans the box, never 0
        assert got == pytest.approx(CLW / 2 - r + l)              # right = +x, left = -x


def test_the_switches_are_bound_to_visibility(can):
    prod = can[0]
    f, P = _forms(prod), prod.doc.params
    ext = lambda n: f[n].by_class("ExtrusionElem")[0]               # noqa: E731
    assert (P[PC.P_SHOW_TRIM].elem_id, PB.ELEM_PROP_VISIBLE) in _bound(ext("trim"))
    assert (P[EC.P_FRONT_ON].elem_id, PB.ELEM_PROP_VISIBLE) in _bound(ext(PC.ZONE_FRONT))
    assert (P[EC.P_TOP_ON].elem_id, PB.ELEM_PROP_VISIBLE) in _bound(ext(PC.ZONE_TOP))
    for n in PLATES:                                                # the box always shows
        assert not _bound(ext(f"back box: {n}"))


def test_the_parameters_read_in_sections_and_bind_per_instance(can):
    prod, path, _rep = can
    P, rb = prod.doc.params, readback(path)
    for hdr, _g in PC.HEADERS:
        assert P[hdr].refs["formula"] == f'"{hdr}"' and rb[hdr]["str"] == hdr
    for cap in (PC.P_WIDTH, PC.P_HEIGHT, PC.P_DEPTH, PC.P_MOUNT, PC.P_SURFACE, PC.P_SHOW_TRIM,
                PC.P_MIN_WS_W, PC.P_WS_W, PC.P_WS_DEPTH, PC.P_DED_H, PC.P_FROM_FLOOR, PC.P_WS_H,
                PC.P_LOAD, PC.P_CENTERED, PC.P_SHIFT_L, PC.P_SHIFT_R, PC.P_WS_LEFT, PC.P_MOTOR):
        assert rb[cap]["instance"] is True, cap
    for cap in (PC.P_THICK, PC.P_VOLTAGE, PC.P_POLES, PC.P_PF):
        assert rb[cap]["instance"] is False, cap


def test_every_drive_is_wired(can):
    prod = can[0]
    by = {d["caption"]: d for d in prod.drives}
    assert set(by) == {PC.P_WIDTH, PC.P_TRIM_W, PC.P_DEPTH, PC.P_WS_DEPTH, PC.P_WS_LEFT,
                       PC.P_WS_W}
    assert by[PC.P_WIDTH]["attach"]["parts"] == 2                  # the two sides ride the width
    assert by[PC.P_DEPTH]["attach"]["parts"] == 1                  # the trim rides the front
    assert set(prod.heights["captions"]) == {PC.P_MOUNT, PC.P_HEIGHT, PC.P_TRIM_Z, PC.P_TRIM_H,
                                             PC.P_DED_H, PC.P_WS_H}
    assert prod.heights["refused"] == [] and prod.heights["locked_unlabelled"] == 2
    assert not any("not wired" in n for n in prod.doc.notes)


def test_the_working_space_starts_at_the_trim_face(can):
    prod = can[0]
    D, t = 5.75 * IN, PC.BOX_THICKNESS_IN * IN
    _x, y, _z = _extents(_forms(prod)[PC.ZONE_FRONT])
    assert y[0] == pytest.approx(D + t)                            # not behind the trim
    planes = {p.elem_id: p for p in prod.doc.refplanes}
    from rvt.famgen import drive_law as DL
    lo = planes[next(d for d in prod.drives if d["caption"] == PC.P_WS_DEPTH)["planes"][0]]
    assert DL.plane_at(lo, "y") == pytest.approx(D + t)


def test_the_power_connector_reads_the_family_parameters(can):
    prod = can[0]
    P = prod.doc.params
    (con,) = prod.doc.connectors
    # the census's property ids, as literals: poles, voltage, apparent load (-1140004,
    # NOT the -1140005 skeleton.ELEM_PROP_APPARENT_LOAD holds), power factor, load class
    assert _bound(con) == {(P[PC.P_POLES].elem_id, -1140001), (P[PC.P_VOLTAGE].elem_id, -1140002),
                           (P[PC.P_LOAD].elem_id, -1140004), (P[PC.P_PF].elem_id, -1140008),
                           (P[PC.P_LOAD_CLASS].elem_id, -1140014)}
    poles = P[PC.P_POLES].obj["m_pParamDef"]
    assert poles["ptr_class"] == "ParamDefNoOfPoles"
    assert (poles["value"]["m_lowBound"], poles["value"]["m_upBound"]) == (1, 3)
    lc = P[PC.P_LOAD_CLASS]
    assert lc.obj["m_pParamDef"]["ptr_class"] == "ElectricalLoadClassificationParamDef"
    assert readback(can[1])[PC.P_LOAD_CLASS]["elem"] == \
        con.obj["m_pDomain"]["value"]["m_idLoadClassification"]


def test_two_conduit_connectors_on_the_box_top_and_bottom(can):
    prod = can[0]
    f = _forms(prod)
    mep = prod.doc.mep_connectors
    assert len(mep) == 2
    hosts = {c.obj["m_oPlaneRef"]["value"]["m_geomRef"]["m_elemId"] for c in mep}
    assert hosts == {f["back box: top"].by_class("ExtrusionElem")[0].elem_id,
                     f["back box: bottom"].by_class("ExtrusionElem")[0].elem_id}
    assert sum(c.obj["m_pDomain"]["value"]["m_bIsPrimaryConnector"] for c in mep) == 1


@pytest.mark.parametrize("kw", [{"height_in": 80}, {"mounting_height_in": 0}])
def test_a_box_on_the_floor_keeps_its_height_chain(kw):
    prod = PC.make_panel_can(**kw)
    assert prod.heights["refused"] == [] and PC.P_HEIGHT in prod.heights["captions"]
    assert PC.P_MOUNT not in prod.heights["captions"]
    assert any("stands on the floor" in n for n in prod.doc.notes)
    assert PC.P_FROM_FLOOR not in prod.doc.params                  # it always starts there
    flush = PC.make_panel_can(surface=False, **kw)
    assert flush.heights["refused"] == []
    assert any("laps" in n and "below the floor" in n for n in flush.doc.notes)


def test_a_low_mounted_box_keeps_the_code_height_and_says_so():
    prod = PC.make_panel_can(mounting_height_in=24)
    assert PC.P_FROM_FLOOR not in prod.doc.params and PC.P_WS_H not in prod.doc.params
    assert any("the code minimum, not switchable" in n for n in prod.doc.notes)
    assert prod.heights["refused"] == []


def test_given_sizes_are_said_and_impossible_ones_refused():
    prod = PC.make_panel_can(width_in=26, height_in=60, depth_in=6, box_thickness_in=0.125,
                             flush_lap_in=0.5, surface=False)
    assert any(n.startswith("GIVEN") and "box thickness 0.125 in" in n for n in prod.notes)
    x, _y, z = _extents(_forms(prod)["back box: back"])
    assert (x[1] - x[0], z[1] - z[0]) == pytest.approx((26 * IN, 60 * IN))
    tx, ty, _tz = _extents(_forms(prod)["trim"])
    assert (tx[1] - tx[0], ty[1] - ty[0]) == pytest.approx((27 * IN, 0.125 * IN))
    assert prod.doc.params[PC.P_THICK].refs["formula"] == "0.0104166666666667'"
    for bad in ({"depth_in": 0.2}, {"box_thickness_in": 0}, {"mounting_height_in": -3}):
        with pytest.raises(PC.PanelCanError):
            PC.make_panel_can(**bad)


@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_the_written_family_validates(can, tmp_path, year):
    if year == 2026:
        rep = can[2]
    else:
        from rvt.frontdoor import release_ctx as RC
        base = os.path.join(ROOT, "plugin", "assets", "genesis", f"G_ABPD_{year}.rvt")
        if not os.path.exists(base):
            pytest.skip(f"the pinned {year} base is not in this checkout")
        out = str(tmp_path / f"can{year}.rfa")
        with RC.release_build_context(base):
            rep = PC.make_panel_can(surface=False).write(out)
        assert readback(out)[PC.P_FLUSH]["int"] == 1
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True


def test_the_cli_builds_it(tmp_path):
    out = tmp_path / "cli.rfa"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "panel-can",
                        "--cover", "flush", "--mounting-height", "18", "-o", str(out)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert out.exists() and "VALID (0 errors" in r.stdout
    assert readback(str(out))[PC.P_MOUNT]["value"] == pytest.approx(18 * IN)


# --- #1053 review round 2 ------------------------------------------------------------

def _labelled(prod):
    """[(param id, the value the labelled dimension holds)] of every labelled segment."""
    out = []
    for e in prod.doc.elements:
        if e.class_name != "LinearDimString":
            continue
        for seg in e.obj.get("m_ArrSegInfo") or []:
            pid = seg.get("m_paramId")
            if isinstance(pid, int) and pid > 0:
                out.append((pid, seg["m_values"][0]["m_value"]))
    return out


@pytest.mark.parametrize("kw,n", [({}, 12), ({"surface": False}, 12), ({"height_in": 80}, 9),
                                  ({"height_in": 80, "surface": False}, 8),
                                  ({"mounting_height_in": 24}, 11)])
def test_every_labelled_dimension_holds_its_parameters_written_value(kw, n, tmp_path):
    prod = PC.make_panel_can(**kw)
    path = str(tmp_path / "x.rfa")
    prod.write(path)
    by_id = {r["id"]: r["value"] for r in readback(path).values()}
    labelled = _labelled(prod)
    assert len(labelled) == n
    for pid, held in labelled:
        assert held > 0 and by_id[pid] == pytest.approx(held), pid


def test_the_chains_are_anchored_where_they_belong(can):
    from rvt.famgen import drive_law as DL
    prod = can[0]
    by = {d["caption"]: d for d in prod.drives}
    ox, oy = (DL.origin_centre_plane(prod.doc, a).elem_id for a in ("x", "y"))
    assert by[PC.P_DEPTH]["anchored"] == ["lo"] and by[PC.P_DEPTH]["planes"][0] == oy
    assert by[PC.P_WS_DEPTH]["anchored"] == ["lo"]
    assert by[PC.P_WS_LEFT]["anchored"] == ["hi"] and by[PC.P_WS_LEFT]["planes"][1] == ox
    assert by[PC.P_WS_W]["anchored"] == ["lo"]
    assert by[PC.P_WS_W]["planes"][0] == by[PC.P_WS_LEFT]["planes"][0]
    assert by[PC.P_WIDTH].get("symmetric") and by[PC.P_TRIM_W].get("symmetric")


@pytest.mark.parametrize("kw,locks", [({}, (16, 8)), ({"height_in": 80}, (14, 7)),
                                      ({"height_in": 80, "surface": False}, (12, 6))])
def test_the_height_chain_locks_every_face_it_should(kw, locks):
    h = PC.make_panel_can(**kw).heights
    assert (h["face_locks"], h["extrusions_locked"]) == locks and h["refused"] == []


def test_the_connectors_point_out_of_their_faces_apart_from_each_other(can):
    prod = can[0]
    W, D, H = 20 * IN, 5.75 * IN, prod.facts.get("height_in") * IN
    MH = (PC.MOUNT_TOP_IN - prod.facts.get("height_in")) * IN

    def frame(c):                                      # (origin, direction) on its face
        surf = c.obj["m_pFaceU"]["value"]["m_pSurf"]["value"]
        return tuple(surf["m_origin"]), tuple(surf["m_xVec"])
    (power,) = prod.doc.connectors
    assert frame(power) == (pytest.approx((0.0, D / 2, MH + H)), (0.0, 0.0, 1.0))
    got = sorted(frame(c) for c in prod.doc.mep_connectors)
    assert got[0][0] == pytest.approx((W / 4, D / 2, MH)) and got[0][1] == (0.0, 0.0, -1.0)
    assert got[1][0] == pytest.approx((W / 4, D / 2, MH + H)) and got[1][1] == (0.0, 0.0, 1.0)


def test_each_header_heads_its_section(can):
    prod = can[0]
    names = {pe.elem_id: n for n, pe in prod.doc.params.items()}
    cells = prod.doc.self_family.obj["m_cellList"]["value"]["m_cells"]
    order = next(c for c in cells if "FamilyParamsOrderCell" in c["ptr_class"])["value"]
    seq = [names.get(i, i) for g in order["m_sortedParams"] for i in g["m_paramIds"]]
    for hdr, first in ((PC.H_DIMS, PC.P_WIDTH), (PC.H_TRIM, PC.P_SURFACE),
                       (PC.H_CLEAR, PC.P_MIN_WS_W), (PC.H_IDENTITY, "PanelName")):
        assert seq[seq.index(hdr) + 1] == first, hdr


def test_a_flush_trim_on_the_floor_says_its_bottom_is_not_driven():
    prod = PC.make_panel_can(surface=False, mounting_height_in=PC.FLUSH_LAP_IN)
    assert prod.heights["refused"] == [] and PC.P_TRIM_Z not in prod.heights["captions"]
    assert any("trim's bottom is on the floor" in n for n in prod.doc.notes)


def test_a_shared_parameter_file_never_refuses_the_job(tmp_path):
    rows = (("Width", "LENGTH"), ("Show Clearances", "YESNO"), ("Number of Poles", "NUMBER_OF_POLES"),
            ("Show Front Clearance", "YESNO"), ("Voltage", "ELECTRICAL_POTENTIAL"))
    sp = tmp_path / "sp.txt"
    sp.write_text("# synthetic\n*META\tVERSION\tMINVERSION\nMETA\t2\t1\n*GROUP\tID\tNAME\n"
                  "GROUP\t1\tDims\n*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE"
                  "\tDESCRIPTION\tUSERMODIFIABLE\n"
                  + "".join(f"PARAM\t0000aaaa-1047-4000-8000-00000000000{i}\t{n}\t{dt}\t\t1\t1\t\t1\n"
                            for i, (n, dt) in enumerate(rows, start=1)),
                  encoding="utf-8")
    prod = PC.make_panel_can(shared_params=str(sp))
    rep = prod.write(str(tmp_path / "sp.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    P = prod.doc.params
    for local in (PC.P_WIDTH, PC.P_POLES, "Show Front Clearance"):
        assert P[local].class_name == "ParamElemFamily", local
    assert P[PC.P_POLES].obj["m_pParamDef"]["ptr_class"] == "ParamDefNoOfPoles"
    assert P[PC.P_VOLTAGE].class_name == "ParamElemExternal"        # it matches: authored shared
    notes = "\n".join(prod.doc.notes)
    assert "kept LOCAL, not shared: Width, Number of Poles, Show Clearances" in notes
    assert "kept LOCAL, not shared: Show Front Clearance -- the shared-parameter file's " \
           "datatype" in notes
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "panel-can",
                        "--shared-params", str(sp), "-o", str(tmp_path / "cli_sp.rfa")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and "VALID (0 errors" in r.stdout, r.stdout[-1500:] + r.stderr[-1500:]


def test_zone_notes_are_kept_without_drives():
    prod = PC.make_panel_can(mounting_height_in=24, drive=False)
    assert prod.drives == [] and any("the code minimum, not switchable" in n
                                     for n in prod.doc.notes)


@pytest.mark.parametrize("kw,said", [({"mounting_height_in": 0.01}, "the box bottom 0.01 in"),
                                     ({"mounting_height_in": -1e-9}, "the box bottom -1e-09 in"),
                                     ({"mounting_height_in": PC.FLUSH_LAP_IN + 0.0001,
                                       "surface": False}, "flush trim's bottom on the floor"),
                                     ({"mounting_height_in": PC.FLUSH_LAP_IN - 0.0001,
                                       "surface": False}, "flush trim's bottom on the floor"),
                                     # #1053 round 4: a lap under 1/32 in never LIFTS a box
                                     # off the floor into a dimension Revit cannot draw
                                     ({"mounting_height_in": 0, "surface": False,
                                       "flush_lap_in": 0.02}, "0.02 in flush lap is built as none"),
                                     ({"mounting_height_in": 0.01, "surface": False,
                                       "flush_lap_in": 0.02}, "the box bottom 0.01 in"),
                                     ({"box_thickness_in": 0.01}, "0.01 in wall is built 0.03125")])
def test_a_length_too_short_for_revit_is_built_on_the_floor(kw, said, tmp_path):
    prod = PC.make_panel_can(**kw)
    assert any(said in n and "which Revit cannot dimension" in n for n in prod.doc.notes)
    assert prod.heights["refused"] == []
    path = str(tmp_path / "f.rfa")
    prod.write(path)
    by_id = {r["id"]: r["value"] for r in readback(path).values()}
    assert all(held >= PC.FLOOR_SNAP_IN / 12 for _pid, held in _labelled(prod))
    assert all(by_id[pid] == pytest.approx(held) for pid, held in _labelled(prod))


@pytest.mark.parametrize("kw,mh", [({"mounting_height_in": 0, "surface": False,
                                     "flush_lap_in": 0.02}, 0.0),
                                   ({"mounting_height_in": 0.01, "surface": False,
                                     "flush_lap_in": 0.02}, 0.0),
                                   ({"mounting_height_in": PC.FLUSH_LAP_IN - 0.0001,
                                     "surface": False}, PC.FLUSH_LAP_IN)])
def test_a_snap_lands_on_the_floor_never_off_it(kw, mh, tmp_path):
    prod = PC.make_panel_can(**kw)
    path = str(tmp_path / "f.rfa")
    prod.write(path)
    got = readback(path)
    assert got[PC.P_MOUNT]["value"] == pytest.approx(mh / 12.0)
    assert got[PC.P_THICK]["value"] >= PC.FLOOR_SNAP_IN / 12 - 1e-12
    # the zone note says the given height was changed, never "(given)" for a changed one
    given = float(kw["mounting_height_in"])
    if mh != given:
        assert any(f"(given {given:g} in, snapped" in n for n in prod.doc.notes), prod.doc.notes


def test_a_wall_too_thin_for_revit_is_built_at_the_shortest_length(tmp_path):
    prod = PC.make_panel_can(box_thickness_in=0.01, mounting_height_in=24)
    path = str(tmp_path / "f.rfa")
    prod.write(path)
    assert readback(path)[PC.P_THICK]["value"] == pytest.approx(PC.FLOOR_SNAP_IN / 12)
    assert all(held >= PC.FLOOR_SNAP_IN / 12 - 1e-12 for _pid, held in _labelled(prod))


@pytest.mark.parametrize("kw", [{"width_in": float("nan")}, {"width_in": float("inf")},
                                {"depth_in": float("-inf")}, {"mounting_height_in": float("nan")},
                                {"flush_lap_in": float("nan"), "surface": False},
                                {"box_thickness_in": float("inf")}])
def test_a_size_that_is_not_a_length_is_refused_by_name(kw):
    with pytest.raises(PC.PanelCanError, match="is not a length"):
        PC.make_panel_can(**kw)


def test_every_caption_the_constructor_authors_is_in_a_shared_row_table(tmp_path):
    """A shared-parameter row can never reach a caption this constructor authors
    unless the tables say what it may be: per instance, by formula or as a local-only
    storage -> :func:`_local_only`; otherwise its spec -> :func:`_authored_specs`.
    Read from the WRITTEN family (#1053 round 4: dropping a caption from the local
    table survived every other test)."""
    prod = PC.make_panel_can(standards=False, mounting_height_in=24)
    path = str(tmp_path / "f.rfa")
    prod.write(path)
    got = readback(path)
    local, specs = set(PC._local_only()), set(PC._authored_specs())
    assert len(got) >= 30 and set(got) <= local | specs, sorted(set(got) - local - specs)
    for cap, row in got.items():
        if row["instance"] or row["formula"]:
            assert cap in local, cap
    assert not local & specs
