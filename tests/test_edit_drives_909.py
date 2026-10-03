"""#909 -- a family edit MOVES THE GEOMETRY its parameter drives.

Steers #908 / #913: *"the rest of the elements need to be constrained and move
with it"*.  Our generated families carry constraint graphs (in-plane drives
#904 / #913, heights #787 Case B, diameters #916, the #948 hexagon through a
formula parameter).  Before #909 the edit lane wrote the value and nothing
else: ``Strut Length`` = 36 in left its labelled dimension measuring 30 in and
every plane, locked edge and follower where they were.

Now (``rvt.convert.family_regen``): an edit of a generator INPUT rebuilds the
family from its generator, after the generator -- on the spec recovered from
the file -- reproduced the input byte for byte; the result is byte-identical
to building at the new value directly.  Anything not rebuilt says so in an
explicit caveat (never a silent mismatch).  The chain checked on every
rebuilt file: parameter value == labelled dimension (``label_report``), the
dimension == its planes' distance and every locked edge / face on its plane
(``constraint_law.check_file`` CG7 / CG10 == []), ``tools/rvt_validate.py`` 0
errors, family-mode VALID.

All fixtures are OURS, generated here.  Nothing here claims Revit regenerates
an edited family, or that the rebuilt family flexes: no desktop verdict exists
(hard rule 4).

Run: .venv/bin/python -m pytest tests/test_edit_drives_909.py -q
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import HAVE_SCHEMA, context_constants, ladder_constants   # noqa: E402
from rvt.convert import family_regen as FR                              # noqa: E402
from rvt.convert import modify_family as MF                             # noqa: E402

needs_schema = pytest.mark.skipif(not HAVE_SCHEMA, reason="class schema cache absent")

# the nested-hardware rebuild nests through famgen.nest (host_release_context) and
# constraint_law.check_file reads under enter_own_release: conftest's guard
# watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")

IN = 1.0 / 12.0


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the
    native codec singletons (by design); do that once before the guard's
    first snapshot."""
    if not HAVE_SCHEMA:
        return
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t909w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- helpers

def _sha(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _write(prod, path) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prod.write(path, validate=False, provenance=False)
    return path


def _archetype(d, product="strut_trapeze", name="x.rfa", **kw) -> str:
    from rvt.famgen import factory as F
    return _write(F.make_archetype(product=product, **kw), os.path.join(str(d), name))


def _direct(d, stem, **kw) -> str:
    """The family built AT the new value directly, written under the edit's
    output name (the one path-dependent byte is BasicFileInfo's save name)."""
    return _archetype(os.path.join(str(d), "direct"), name=stem + ".rfa", **kw)


def _edit(src, edit, d, stem="E"):
    rec = MF.modify_family(str(src), edit, os.path.join(str(d), "edit-" + stem), stem=stem)
    return rec, rec["files"]["rfa"]


def _validate(path) -> bool:
    js = path + ".validation.json"
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rvt_validate.py"),
                           path, "--json", js], capture_output=True, text=True, timeout=600)
    rep = json.load(open(js))
    return proc.returncode == 0 and rep["ok"] and rep["counts"]["error"] == 0


def _assert_geometry_true(rec, out):
    """The whole chain agrees: parameter == labelled dimension == plane
    distance == locked edges / faces; validator 0 errors; re-read proven."""
    from rvt.famgen import constraint_law as CL
    g = rec["validation"]["rfa"]
    assert g["family_mode"]["verdict"] == "VALID" and g["family_mode"]["n_errors"] == 0
    assert g["self_checks_ok"] and all(r["ok"] for r in g["reread"])
    labels = FR.label_report(out)
    assert labels and all(l["agree"] for l in labels), [l for l in labels if not l["agree"]]
    assert g["labels"] == {"n": len(labels), "disagree": []}
    assert CL.check_file(out) == []
    assert _validate(out)


def _labels(path, caption):
    return [l for l in FR.label_report(path) if l["caption"] == caption]


def _current(path, caption):
    return MF.inventory_family(path).param_by_caption(caption)["current"]


def _planes_of(path, dim_id):
    """The RefPlane points (along their normals) a labelled dimension witnesses."""
    from rvt.famgen import constraint_law as CL
    from rvt.mutate import Document
    doc = Document.from_file(path)
    out = []
    for eid in CL._witness_targets(doc.value(dim_id) or {}):
        if doc.class_of(eid) == "RefPlane":
            p, n = CL.plane_of_any("RefPlane", doc.value(eid) or {})
            out.append(sum(a * b for a, b in zip(p, n)))
    return out


@pytest.fixture(scope="module")
def trapeze():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    d = tempfile.mkdtemp(prefix="t909tr_")
    try:
        yield _archetype(d)
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- the defect, fixed

@needs_schema
def test_strut_length_moves_its_planes_dimension_edges_and_followers(trapeze, tmp_path):
    before = _labels(trapeze, "Strut Length")
    assert [l["stored"] for l in before] == [pytest.approx(30 * IN)]
    assert sorted(abs(x) for x in _planes_of(trapeze, before[0]["dim"])) == pytest.approx([15 * IN] * 2)
    rec, out = _edit(trapeze, "set Strut Length to 36 in", tmp_path, "T36")
    rg = rec["regeneration"]
    assert rg["route"] == "regenerated" and rg["product"] == "strut_trapeze"
    assert rg["candidates"] == [{"generator": "archetype", "product": "strut_trapeze",
                                 "result": "reproduced"}]
    # Rod Spacing is a value, never a driver: the generator re-derives it, so
    # the rods keep their Rod Inset from the moved ends
    assert rg["re_derived_by_generator"] == ["rod_spacing_in"]
    assert rg["name"] == "Strut Trapeze 36 in 2 Tier"
    after = _labels(out, "Strut Length")
    assert [l["stored"] for l in after] == [pytest.approx(3.0)] and after[0]["agree"]
    assert sorted(abs(x) for x in _planes_of(out, after[0]["dim"])) == pytest.approx([1.5, 1.5])
    assert _current(out, "Strut Length") == pytest.approx(3.0)
    assert _current(out, "Rod Spacing") == pytest.approx(30 * IN)           # 36 - 2 x 3
    _assert_geometry_true(rec, out)
    assert _sha(out) == _sha(_direct(tmp_path, "T36", dimensions={"strut_length_in": 36}))
    assert rec["degradations"] == [
        "Strut Length: 36 in -> 3 ft" + MF.REBUILT_NOTE]


@needs_schema
def test_the_old_lane_left_the_mismatch_the_rebuild_removes(trapeze, tmp_path):
    """The control: the value path alone (what #909 found) leaves the label at 30 in."""
    inv = MF.inventory_family(trapeze)
    ops = MF.parse_family_edit("set Strut Length to 36 in", inv)["ops"]
    out = str(tmp_path / "value-only.rfa")
    MF.apply_family_edits(inv, ops, out)
    sl = _labels(out, "Strut Length")
    assert [(l["stored"], l["value"], l["agree"]) for l in sl] == [
        (pytest.approx(2.5), pytest.approx(3.0), False)]


@needs_schema
def test_a_height_drive_rebuilds(trapeze, tmp_path):
    rec, out = _edit(trapeze, "set Tier Spacing to 18 in", tmp_path, "TS18")
    assert rec["regeneration"]["route"] == "regenerated"
    assert [l["stored"] for l in _labels(out, "Tier Spacing")] == [pytest.approx(1.5)]
    _assert_geometry_true(rec, out)
    assert _sha(out) == _sha(_direct(tmp_path, "TS18", dimensions={"tier_spacing_in": 18}))


@needs_schema
def test_a_diameter_drive_rebuilds(trapeze, tmp_path):
    rec, out = _edit(trapeze, '[{"op": "set-param", "param": "Rod Diameter", "value": "0.5 in"}]',
                     tmp_path, "RD")
    assert rec["regeneration"]["route"] == "regenerated"
    rods = _labels(out, "Rod Diameter")
    assert [l["class"] for l in rods] == ["RadialDim", "RadialDim"]
    assert all(l["stored"] == pytest.approx(0.5 * IN) for l in rods)
    _assert_geometry_true(rec, out)
    assert _sha(out) == _sha(_direct(tmp_path, "RD", dimensions={"rod_diameter_in": 0.5}))


@needs_schema
def test_a_follow_offset_rebuilds_and_rod_spacing_is_re_derived(trapeze, tmp_path):
    rec, out = _edit(trapeze, "set Rod Inset to 4 in", tmp_path, "RI4")
    assert rec["regeneration"]["re_derived_by_generator"] == ["rod_spacing_in"]
    assert _current(out, "Strut Length") == pytest.approx(2.5)
    assert _current(out, "Rod Spacing") == pytest.approx(22 * IN)
    _assert_geometry_true(rec, out)
    assert _sha(out) == _sha(_direct(tmp_path, "RI4", dimensions={"rod_inset_in": 4}))


@needs_schema
@pytest.mark.parametrize("product, edit, dims", [
    ("conduit", "set Outside Diameter to 1.5 in", {"diameter_in": 1.5}),
    ("cable_tray", "set Tray Width to 18 in", {"width_in": 18}),
    ("junction_box", "set Box Width to 8 in", {"width_in": 8}),
])
def test_other_archetypes_rebuild_through_their_own_registries(tmp_path, product, edit, dims):
    src = _archetype(tmp_path / "src", product=product)
    rec, out = _edit(src, edit, tmp_path, product)
    assert rec["regeneration"]["route"] == "regenerated"
    assert rec["regeneration"]["product"] == product
    _assert_geometry_true(rec, out)
    # the rebuild holds every OTHER dimension where the file had it (an edit of
    # Box Width leaves Box Height alone -- the archetype's "follows" rule is for
    # a prompt that states one size, never for an edit)
    rg = rec["regeneration"]
    assert rg["spec_built"] == dict(rg["spec_recovered"], **{k: float(v) for k, v in dims.items()})
    assert _sha(out) == _sha(_direct(tmp_path, product, product=product,
                                     dimensions=rg["spec_built"]))


@needs_schema
def test_the_nested_hardware_trapeze_rebuilds_with_its_nested_children(tmp_path):
    """#917: the washers and nuts are nested families; the rebuild re-nests them
    at the new rod size (its nut's hexagon through its own formula child)."""
    from rvt.famgen import constraint_law as CL
    src = _archetype(tmp_path / "src", nested_hardware=True)
    rec, out = _edit(src, "set Rod Diameter to 0.5 in", tmp_path, "NRD")
    assert rec["regeneration"]["route"] == "regenerated"
    assert rec["regeneration"]["options"] == {"nested_hardware": True}
    _assert_geometry_true(rec, out)
    for unit in CL.nested_units(out).values():
        assert CL.check_file(out, unit=unit) == []
    assert _sha(out) == _sha(_direct(tmp_path, "NRD", nested_hardware=True,
                                     dimensions={"rod_diameter_in": 0.5}))


@needs_schema
def test_an_edit_and_a_value_edit_together_and_a_second_edit_of_the_output(trapeze, tmp_path):
    rec, out = _edit(trapeze, "set Material to aluminum; set Strut Length to 42 in", tmp_path, "M42")
    assert rec["regeneration"]["route"] == "regenerated" and rec["apply"]["rebuilt"]
    assert _current(out, "Material") == "aluminum"
    _assert_geometry_true(rec, out)
    # the rebuilt output is itself re-editable by rebuild ... once its text edit is
    # gone it reproduces; with the text edit on it does NOT (see the unsupported rows)
    rec2, out2 = _edit(_direct(tmp_path, "S42", dimensions={"strut_length_in": 42}),
                       "set Strut Length to 24 in", tmp_path, "S24")
    assert rec2["regeneration"]["route"] == "regenerated"
    _assert_geometry_true(rec2, out2)
    assert _sha(out2) == _sha(_direct(tmp_path, "S24", dimensions={"strut_length_in": 24}))


# --------------------------------------------------------------------------- formula inputs

@pytest.fixture(scope="module")
def hex_nut():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    from rvt.famgen import trapeze_nested as TN
    d = tempfile.mkdtemp(prefix="t909nut_")
    try:
        yield _write(TN.make_hex_nut(1000, across_flats_ft=0.5625 * IN, height_ft=0.328125 * IN),
                     os.path.join(d, "Hex Nut.rfa"))
    finally:
        shutil.rmtree(d, True)


@needs_schema
def test_a_formula_input_rebuilds_the_hexagon_and_its_formula_child(hex_nut, tmp_path):
    from rvt.famgen import trapeze_nested as TN
    rec, out = _edit(hex_nut, "set Nut Across Flats to 0.75 in", tmp_path, "NUT")
    assert rec["regeneration"]["route"] == "regenerated"
    assert rec["regeneration"]["generator"] == "rvt.famgen.trapeze_nested:make_hex_nut"
    assert _current(out, "Nut Across Flats") == pytest.approx(0.75 * IN)
    assert _current(out, TN.NUT_HALF_ACROSS_FLATS) == pytest.approx(0.375 * IN)
    half = _labels(out, TN.NUT_HALF_ACROSS_FLATS)
    assert half and all(l["stored"] == pytest.approx(0.375 * IN) for l in half)
    _assert_geometry_true(rec, out)
    direct = _write(TN.make_hex_nut(1000, across_flats_ft=0.75 * IN, height_ft=0.328125 * IN),
                    str(tmp_path / "direct" / "NUT.rfa"))
    assert _sha(out) == _sha(direct)


@needs_schema
def test_a_formula_parameter_itself_is_refused_by_name(hex_nut, tmp_path):
    with pytest.raises(MF.FamilyEditError, match="Nut Half Across Flats is a FORMULA parameter"):
        _edit(hex_nut, "set Nut Half Across Flats to 0.75 in", tmp_path, "HALF")


@needs_schema
def test_on_the_value_path_a_formula_child_still_follows_and_the_caveat_says_why(hex_nut, tmp_path):
    """A hex nut renamed by hand no longer reproduces: the value path updates
    the formula child from the file's own tree and says the hexagon did not move."""
    from rvt.famgen import trapeze_nested as TN
    _rec0, renamed = _edit(hex_nut, "rename the type to Big Nut", tmp_path, "REN")
    rec, out = _edit(renamed, "set Nut Across Flats to 0.75 in", tmp_path, "NUTV")
    assert rec["regeneration"]["route"] == "value-only"
    assert "does not reproduce the input byte for byte" in rec["regeneration"]["reason"]
    assert _current(out, TN.NUT_HALF_ACROSS_FLATS) == pytest.approx(0.375 * IN)
    assert any(n.startswith(f"{TN.NUT_HALF_ACROSS_FLATS}: re-evaluated by its formula")
               for n in rec["degradations"])
    cav = [n for n in rec["degradations"] if n.startswith("Nut Across Flats: VALUE ONLY")]
    assert len(cav) == 1 and f"through the formula parameter(s) {TN.NUT_HALF_ACROSS_FLATS}" in cav[0]
    assert "did NOT move" in cav[0] and "hard rule 4" in cav[0]
    # honest: the label still measures the old half
    assert any(not l["agree"] for l in _labels(out, TN.NUT_HALF_ACROSS_FLATS))


# --------------------------------------------------------------------------- unsupported -> explicit

@needs_schema
def test_a_family_that_does_not_reproduce_gets_the_explicit_caveat(trapeze, tmp_path):
    _rec0, edited = _edit(trapeze, "set Material to aluminum", tmp_path, "MAT")
    rec, out = _edit(edited, "set Strut Length to 36 in", tmp_path, "MAT36")
    assert rec["regeneration"]["route"] == "value-only"
    assert rec["degradations"][0] == "Strut Length: 36 in -> 3 ft" + MF.LENGTH_CAVEAT
    cav = rec["degradations"][1]
    assert cav.startswith("Strut Length: VALUE ONLY -- this parameter labels 1 dimension(s)")
    assert "still measure 2.5 ft" in cav and "did NOT move" in cav
    assert "does not reproduce the input byte for byte" in cav
    assert [l["agree"] for l in _labels(out, "Strut Length")] == [False]


@needs_schema
def test_a_parameter_the_generator_computes_says_so(trapeze, tmp_path):
    rec, _out = _edit(trapeze, "set Rod Length to 50 in", tmp_path, "RL")
    assert rec["regeneration"]["route"] == "value-only"
    cav = [n for n in rec["degradations"] if n.startswith("Rod Length: VALUE ONLY")]
    assert len(cav) == 1 and "strut_trapeze generator computes this parameter" in cav[0]
    assert "Rod Above Top Tier" in cav[0]


@needs_schema
def test_an_edit_the_generator_refuses_is_delivered_by_value_and_says_why(trapeze, tmp_path):
    rec, out = _edit(trapeze, "set Strut Length to 4 in", tmp_path, "S4")       # hard rule 1
    assert os.path.isfile(out) and rec["regeneration"]["route"] == "value-only"
    assert "the generator refused the edited spec" in rec["regeneration"]["reason"]
    assert any(n.startswith("Strut Length: VALUE ONLY") for n in rec["degradations"])


@needs_schema
def test_an_ifc_pset_drive_family_is_not_rebuilt_and_says_so(tmp_path):
    """#714: an IFC-built family's drives come from the IFC, which the family
    does not carry -- the edit is value-only and says the dimension did not move."""
    from rvt.famgen import factory as F
    from rvt.ifc import pset_drive as PD
    parts = [{"name": "pad", "shape": "box", "width_ft": 4.0, "depth_ft": 3.0,
              "height_ft": 0.5, "center": [0.0, 0.0], "base_z_ft": 0.0}]
    coll = {"params": {"PadWidth": ("length", 4.0)}, "skipped": [], "notes": [],
            "sources": {"PadWidth": {"pset": "P", "product": "pad", "products": ["pad"],
                                     "tier": "given"}}}
    plan = PD.plan(parts, coll)
    prod = F.make_generic_model(parts=parts, name="Pad714", numeric_params=dict(coll["params"]),
                                drives=plan["drives"], heights=plan["heights"],
                                settle_drives=True)
    assert prod.drive_settle["wired"] == ["PadWidth"]
    src = _write(prod, str(tmp_path / "src" / "pad.rfa"))
    rec, out = _edit(src, "set PadWidth to 5 ft", tmp_path, "PW")
    assert rec["regeneration"]["route"] == "value-only"
    assert "no generator of ours matches" in rec["regeneration"]["reason"]
    cav = [n for n in rec["degradations"] if n.startswith("PadWidth: VALUE ONLY")]
    assert len(cav) == 1 and "still measure 4 ft" in cav[0]


# --------------------------------------------------------------------------- the derivations (no file)

def test_the_trapeze_parameter_map_is_derived_from_the_generator():
    cm = FR.caption_map("strut_trapeze")
    assert cm["inputs"]["Strut Length"] == "strut_length_in"
    assert cm["inputs"]["Rod Spacing"] == "rod_spacing_in"
    assert cm["inputs"]["Number of Tiers"] == "tiers"
    assert cm["derived"]["Nut Across Flats"] == ["rod_diameter_in"]           # 1.5 x d: computed
    assert "Rod Length" in cm["derived"] and len(cm["derived"]["Rod Length"]) > 1
    assert "Rod Spacing" not in cm["drivers"] and "Strut Length" in cm["drivers"]
    assert "Rod Inset" in cm["drivers"] and "Rod Diameter" in cm["drivers"]


def test_a_multi_word_caption_parses_in_the_text_grammar():
    class _Inv:
        params = [{"caption": c} for c in ("Strut Length", "Strut Height", "Width")]
    for clause, cap, val in (("set Strut Length to 36 in", "Strut Length", "36 in"),
                             ("set the Strut Height = 2 in", "Strut Height", "2 in"),
                             ("set Width 600 mm", "Width", "600 mm"),
                             ('set Width of type "A B" 2 ft', "Width", "2 ft")):
        m = MF._match_set(_Inv, clause)
        assert (m.group("cap"), m.group("val")) == (cap, val), clause
