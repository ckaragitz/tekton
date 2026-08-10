"""test_place_fixtures.py -- the front door LOADS + PLACES Electrical Fixtures
(issue #359; generation + the unplaced load lane were #166).

``author --prompt 'a room with 4 duplex receptacles'``: the four devices share
ONE generated ``make_device`` family (``tools/ifc_intent.family_key``), stage L
loads it in the same host pass as any equipment with the family's OWN category
(-2001060) on its surrogates / symbol header / tracking row
(``rvt.famgen.loader.bind_category``), stage E places one ``FamilyInstance``
per device -- header category Electrical Fixtures, upright work-plane frame on
the wall's interior face, z = the AFF height, ``m_assocLevelId`` = the room's
datum -- and the ONE combined file is delivered STAMPED (the open cell, rule
1), project validator 0 errors.  A device family that cannot be authored costs
devices only, never the equipment loaded before it.

Sample-free: the bundled certified genesis base (plugin/assets/genesis) + the
famgen catalog; every written file is read back (the file is the truth).
Validator-green is necessary, NOT certification (rule 4) -- nothing here says
'loads in Revit'.

Run: .venv/bin/python -m pytest tests/test_place_fixtures.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import intent as FI               # noqa: E402
from rvt.frontdoor import prompt_intent as PP        # noqa: E402
import rvt.frontdoor as FD                           # noqa: E402

BASE26 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
OST_ELECTRICAL_EQUIPMENT = -2001040
OST_ELECTRICAL_FIXTURES = -2001060
DONE_PROMPT = "a room with 4 duplex receptacles on a 20A circuit"
MIXED_PROMPT = ("an electrical room 30x20 ft with a 150 kVA transformer, a 225 A 208Y/120 "
                "receptacle panel, two lighting panels and 6 receptacles at 1.1 m above the floor")


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_device_facts("duplex-receptacle")
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=100, spaces=30,
                                    voltage="208Y/120", mcb=True, mounting="surface",
                                    panel_name="X")
        return True
    except Exception:                                    # noqa: BLE001
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")
needs_base = pytest.mark.skipif(not os.path.isfile(BASE26),
                                reason="bundled certified genesis base missing")


def _room():
    from rvt.frontdoor import build as BLD
    return BLD.load_ifc_room_module()


def _readback(path: str):
    """The written project, decoded against its OWN schema."""
    from rvt.frontdoor import standalone as SA
    from rvt.mutate import Document
    SA.install_schema(path)
    return Document.from_file(path)


# ---------------------------------------------------------------------------
# 1. the sharing law: one device family per distinct kwargs, loaded last
# ---------------------------------------------------------------------------

@needs_catalog
def test_devices_share_one_family_and_load_after_the_equipment():
    R = _room()
    model, _ = PP.prompt_to_intent(MIXED_PROMPT)
    groups = R.family_groups(model)
    assert groups == {"LP-1": ["LP-1"], "LP-2": ["LP-2"], "RP-1": ["RP-1"], "T1": ["T1"],
                      "R-1": ["R-1", "R-2", "R-3", "R-4", "R-5", "R-6"]}
    order = R._load_order(model)
    assert order[-1] == "R-1" and sorted(order[:-1]) == ["LP-1", "LP-2", "RP-1", "T1"]
    dev = model.plan_for("R-3")
    assert R._is_device_plan(dev) and not R._is_device_plan(model.plan_for("LP-1"))
    # the device family name carries NO tag (kind / rating / height) -> one key for all six
    assert R._family_name_for(dev) == "Duplex Receptacle 5-15R 120V 180VA 43.31in AFF"
    assert len({R.family_key(model.plan_for(t)) for t in groups["R-1"]}) == 1
    assert "LP-1" in R._family_name_for(model.plan_for("LP-1"))          # boards keep per-tag names
    # two mounting heights = two device families (never one family silently at one height),
    # each written to its OWN .rfa (the file is named by the family, not the constructor stem)
    two, _ = PP.prompt_to_intent("a room with 4 receptacles at 18 in AFF and 2 outlets at 44 in AFF")
    g2 = R.family_groups(two)
    assert sorted(len(v) for v in g2.values()) == [2, 4] and len(g2) == 2
    names = {R._slug(R._family_name_for(two.plan_for(t))) for t in g2}
    assert names == {"duplex_receptacle_5_15r_120v_180va_18in_aff",
                     "duplex_receptacle_5_15r_120v_180va_44in_aff"}


# ---------------------------------------------------------------------------
# 2. the loader binds each family's OWN category on one surveyed host
# ---------------------------------------------------------------------------

class _StubDoc:
    def __init__(self, category_id):
        self.category_id = category_id


class _StubProduct:
    """A product-shaped object: only ``.doc.category_id`` matters here (the
    shape of famgen ``FamilyProduct`` AND of ``convert.extract_family``'s
    extracted products, whose ``RfaFamilyDoc.category_id`` is -1 when the
    family's category could not be read)."""

    def __init__(self, category_id):
        self.doc = _StubDoc(category_id)


def test_product_category_defaults_an_unknown_category_to_the_equipment_binding():
    """The pre-#359 behaviour for anything that is not a real BuiltInCategory:
    an extracted family whose category could not be read (-1), a doc without
    the field, None, junk -> Electrical Equipment (never an UNBOUND load); a
    real non-equipment category (an extracted lighting fixture) -> ITSELF,
    so ``extract_family.reload_family`` now stamps such a family with its own
    category instead of -2001040."""
    from rvt.famgen import loader as L
    assert L.product_category(_StubProduct(-1)) == OST_ELECTRICAL_EQUIPMENT
    assert L.product_category(_StubProduct(None)) == OST_ELECTRICAL_EQUIPMENT
    assert L.product_category(_StubProduct(0)) == OST_ELECTRICAL_EQUIPMENT
    assert L.product_category(_StubProduct(125)) == OST_ELECTRICAL_EQUIPMENT      # a GStyle id, not a category
    assert L.product_category(_StubProduct("-2001060")) == OST_ELECTRICAL_EQUIPMENT
    assert L.product_category(_StubProduct(True)) == OST_ELECTRICAL_EQUIPMENT
    assert L.product_category(object()) == OST_ELECTRICAL_EQUIPMENT              # no doc at all
    assert L.product_category(_StubProduct(-1), default=OST_ELECTRICAL_FIXTURES) == OST_ELECTRICAL_FIXTURES
    assert L.product_category(_StubProduct(OST_ELECTRICAL_FIXTURES)) == OST_ELECTRICAL_FIXTURES
    assert L.product_category(_StubProduct(-2001120)) == -2001120                # OST_LightingFixtures: its own
    assert L.product_category(_StubProduct(-2000011)) == -2000011                # the ceiling's edge (Walls)
    assert L.BUILTIN_CATEGORY_CEILING == -2000000


@needs_base
@needs_catalog
def test_bind_category_rebinds_the_surveyed_host_without_mutating_it():
    from rvt.famgen import factory as F
    from rvt.famgen import loader as L
    from rvt.frontdoor import standalone as SA
    SA.install_schema(BASE26)
    host = L.survey_host(BASE26)
    assert host.category == OST_ELECTRICAL_EQUIPMENT
    fx = L.bind_category(host, OST_ELECTRICAL_FIXTURES)
    assert fx is not host and fx.category == OST_ELECTRICAL_FIXTURES
    assert host.category == OST_ELECTRICAL_EQUIPMENT                    # the survey is untouched
    assert (fx.doc, fx.watermark, fx.levels) == (host.doc, host.watermark, host.levels)
    assert L.bind_category(fx, OST_ELECTRICAL_FIXTURES) is fx           # already bound -> same
    dev = F.make_device("duplex-receptacle", start_id=host.watermark + 1)
    pnl = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=100, spaces=30,
                            voltage="208Y/120", mcb=True, mounting="surface",
                            start_id=host.watermark + 1)
    assert L.product_category(dev) == OST_ELECTRICAL_FIXTURES
    assert L.product_category(pnl) == OST_ELECTRICAL_EQUIPMENT
    assert L.product_category(object()) == OST_ELECTRICAL_EQUIPMENT      # no doc -> the default


@needs_base
@needs_catalog
def test_batched_load_carries_each_familys_own_category(tmp_path):
    """One host pass, an equipment family + a fixtures family: every host
    element of the device (Family object, symbol header, both surrogates,
    the ElementTrackingData symbol row) carries -2001060, the panel's
    -2001040 -- read back off the written file."""
    from rvt.famgen import factory as F
    from rvt.famgen import loader as L
    from rvt.frontdoor import standalone as SA
    from rvt.container import open_rvt
    from rvt.adocument import decode_latest
    SA.install_schema(BASE26)
    out = str(tmp_path / "two_categories.rvt")
    res = L.load_families_into_project(BASE26, out, [
        lambda s: F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=100, spaces=30,
                                   voltage="208Y/120", mcb=True, mounting="surface",
                                   name="Lighting Panelboard LP-1 208Y/120 100A", start_id=s),
        lambda s: F.make_device("duplex-receptacle", mounting_height_in=18, start_id=s),
    ], validate=True, report_path=out + ".load.json")
    assert res.ok and res.n_loaded == 2, res.stop_reason
    cats = [ld.proofs["plan"]["resolved"]["category"] for ld in res.loads]
    assert cats == [OST_ELECTRICAL_EQUIPMENT, OST_ELECTRICAL_FIXTURES]
    ver = res.shared["verify_written"]
    assert ver["file_ok"] and ver["structure_layer"]["n_errors"] == 0
    doc = _readback(out)
    by_family = {}
    for ld, want in zip(res.loads, cats):
        p = ld.plan
        assert doc.value(p.host_family_id).get("m_categoryId") == want
        assert doc.category_of(p.symbol_id) == want
        assert doc.value(p.surrogate_id).get("m_categoryId") == want
        assert doc.value(p.symbol_surrogate_id).get("m_categoryId") == want
        by_family[want] = p.symbol_id
    with open_rvt(out) as f:
        lat = decode_latest(f.inflate("Global/Latest"))
    etd = L._appinfo_slot(lat.value, "ElementTrackingData")
    rows = {r["m_categoryId"]: r["m_elemIdSet"] for r in etd["m_symbols"]}
    assert by_family[OST_ELECTRICAL_FIXTURES] in rows[OST_ELECTRICAL_FIXTURES]
    assert by_family[OST_ELECTRICAL_EQUIPMENT] in rows[OST_ELECTRICAL_EQUIPMENT]
    assert by_family[OST_ELECTRICAL_FIXTURES] not in rows[OST_ELECTRICAL_EQUIPMENT]


# ---------------------------------------------------------------------------
# 3. the DONE prompt end to end, read back off the delivered bytes
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def done_job(tmp_path_factory):
    if not (os.path.isfile(BASE26) and _catalog_ok()):
        pytest.skip("bundled base / famgen catalog missing")
    out = tmp_path_factory.mktemp("fixtures359")
    r = FD.author(prompt=DONE_PROMPT, out=str(out / "job"), no_handoff=True)
    assert r.route == "prompt" and r.ok, (r.status, r.errors)
    return r


def test_done_prompt_delivers_one_stamped_file_with_four_placed_devices(done_job):
    man = done_job.manifest
    build = man["build"]
    assert "PROOF-ONLY" in done_job.status and build["errors"] == [] and build["degradations"] == []
    v = build["combination_verdict"]
    assert (v["mode"], v["n_loaded_families"], v["n_instances"], v["stamp"]) == (
        "stamp-proof-only", 1, 4, FI.OPEN_CELL_STAMP)
    assert list(build["files"]) == ["combined"]
    g = build["validation"]["combined"]
    assert g["validate"]["verdict"] == "VALID" and g["validate"]["n_errors"] == 0
    assert g["census"].get("coherent") is not False and g["self_checks_ok"] is True
    # provenance vs the pinned base: everything this build added is ours-created --
    # 1 Family, 1 FamilySymbol, the surrogates + param twins, 4 walls, 4 instances
    sg = build["status_gate"]
    classes = [c["class"] for c in sg["created_elements"]]
    assert {c["provenance"] for c in sg["created_elements"]} == {"ours-created"}
    assert (classes.count("Family"), classes.count("FamilySymbol"), classes.count("FamilyInstance"),
            classes.count("SWall")) == (1, 1, 4, 4)
    assert sg["provenance_totals"]["ours-created"] == len(classes) == 15
    # one family file, one loaded family shared by the four tags, four device rows
    created = build["elements_created"]
    rfa = [c for c in created if c["kind"] == "family(.rfa)"]
    assert len(rfa) == 1 and rfa[0]["ok"] and os.path.isfile(rfa[0]["path"])
    assert rfa[0]["variant"] == "duplex-receptacle-5-15R" and rfa[0]["tags"] == ["R-1", "R-2", "R-3", "R-4"]
    assert os.path.basename(rfa[0]["path"]) == "duplex_receptacle_5_15r_120v_180va_18in_aff.rfa"
    lf = [c for c in created if c["kind"] == "loaded-family"]
    assert len(lf) == 1 and lf[0]["tags"] == ["R-1", "R-2", "R-3", "R-4"]
    devices = [c for c in created if c["kind"] == "fixture-instance"]
    assert [d["tag"] for d in devices] == ["R-1", "R-2", "R-3", "R-4"]
    assert [d["shared_with"] for d in devices] == [None, "R-1", "R-1", "R-1"]
    assert {d["symbol"] for d in devices} == {lf[0]["symbol_id"]}
    sched = devices[0]["schedule"]
    assert (sched["Voltage"], sched["Load"], sched["MountingHeight"], sched["Phases"], sched["Wires"]) == (
        "120 V", 180.0, 18.0, 1, 2)
    assert "5-15R" in sched["DeviceType"]
    # CRUD: every device is movable / retypable / deletable through the edit route
    crud = {e["tag"]: e for e in man["crud"]["elements"] if e["kind"] == "fixture-instance"}
    assert set(crud) == {"R-1", "R-2", "R-3", "R-4"}
    assert set(crud["R-2"]["modify"]) == {"move", "retype", "delete"}
    with open(done_job.manifest_paths["md"], encoding="utf-8") as fh:
        md = fh.read()
    assert "4 wiring devices" in md and "device schedule" in md and "| R-1 |" in md
    assert FI.OPEN_CELL_STAMP in md


def test_done_prompt_readback_instances_are_fixtures_at_18in_upright_on_L1(done_job):
    build = done_job.manifest["build"]
    path = build["files"]["combined"]["path"]
    doc = _readback(path)
    devices = [c for c in build["elements_created"] if c["kind"] == "fixture-instance"]
    room_level = build["levels"]["room_level_id"]
    assert room_level and {d["level_id"] for d in devices} == {room_level}
    ours = sorted(d["elem_id"] for d in devices)
    assert sorted(i for i in doc.ids_of_class("FamilyInstance")) == ours     # nothing else placed
    symbol = devices[0]["symbol"]
    assert doc.category_of(symbol) == OST_ELECTRICAL_FIXTURES
    for d in devices:
        v = doc.value(d["elem_id"])
        ii = (v.get("m_pInstanceInfo") or {}).get("value") or {}
        assert doc.category_of(d["elem_id"]) == OST_ELECTRICAL_FIXTURES       # header category
        assert v.get("m_assocLevelId") == room_level                          # scheduled to L1
        assert ii.get("m_symbolId") == v.get("m_masterSymbolId") == symbol    # our shared symbol
        trf = ii["m_Trf"]
        x, y, z = trf["m_or"]
        assert abs(z - 1.5) < 1e-6                                            # 18 in AFF (L1 @ 0)
        assert abs(abs(x) - 4.4704 * 3.280839895) < 1e-3                      # on the W / E interior face
        bx, by, bz = trf["m_3x3"]
        assert by == [0.0, 0.0, 1.0]                                          # family +Y = up (upright)
        assert bz == ([1.0, 0.0, 0.0] if x < 0 else [-1.0, 0.0, 0.0])       # family +Z faces INTO the room
        conns = ((v.get("m_pConnectorManager") or {}).get("value") or {}).get("m_connPtrArray") or []
        assert len(conns) == 1                                                # our one 1-pole connector, no panel slots
        assert v.get("m_hostId") in (-1, None)                                # free-standing (face-hosting = follow-up)


BASES = {2025: os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt"),
         2024: os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2024.rvt")}


@needs_catalog
@pytest.mark.parametrize("release", [2025, 2024])
def test_done_prompt_places_the_devices_on_the_older_certified_bases_too(tmp_path, release):
    """``--target-version 2025 / 2024``: the same one shared family + four
    placed Electrical Fixtures on that release's certified base, the output
    IS that release (BasicFileInfo), project validator 0 errors under its own
    release -- the famgen load lane needed nothing device-specific there.
    Validated, NOT viewer-certified (rule 4); the open-cell stamp rides along."""
    if not os.path.isfile(BASES[release]):
        pytest.skip(f"bundled {release} genesis base missing")
    from rvt.versions import detect_release
    r = FD.author(prompt=DONE_PROMPT, out=str(tmp_path / f"v{release}"), no_handoff=True,
                  target_version=release)
    assert r.ok, (r.status, r.errors)
    build = r.manifest["build"]
    assert build["errors"] == []
    kinds = [c["kind"] for c in build["elements_created"]]
    assert (kinds.count("family(.rfa)"), kinds.count("fixture-instance"), kinds.count("loaded-family")) == (1, 4, 1)
    assert {c["category"] for c in build["elements_created"] if c["kind"] == "fixture-instance"} == {OST_ELECTRICAL_FIXTURES}
    assert build["combination_verdict"]["stamp"] == FI.OPEN_CELL_STAMP
    g = build["validation"]["combined"]["validate"]
    assert (g["verdict"], g["n_errors"]) == ("VALID", 0)
    combined = build["files"]["combined"]["path"]
    assert detect_release(combined) == release                             # the file IS that release
    tv = r.manifest["target_version"]
    assert (tv["requested"], tv["output_release"], tv["status"]) == (release, release, "match")


# ---------------------------------------------------------------------------
# 4. mixed prompts: equipment exactly as before, devices added, never shed
# ---------------------------------------------------------------------------

@needs_base
@needs_catalog
def test_mixed_prompt_places_boards_transformer_circuit_and_six_devices(tmp_path):
    r = FD.author(prompt=MIXED_PROMPT, out=str(tmp_path / "mixed"), no_handoff=True)
    assert r.ok, (r.status, r.errors)
    build = r.manifest["build"]
    assert build["errors"] == [] and build["degradations"] == []
    load = build["load"]
    assert load["order"] == ["LP-1", "LP-2", "T1", "RP-1", "R-1"]        # feeder depth, devices LAST
    assert (load["n_loaded"], load["n_planned"], load["host_passes"]) == (5, 5, 1)
    kinds = [(c["kind"], c["tag"]) for c in build["elements_created"]]
    assert [t for k, t in kinds if k == "equipment-instance"] == ["LP-1", "LP-2", "RP-1", "T1"]
    assert [t for k, t in kinds if k == "fixture-instance"] == [f"R-{i}" for i in range(1, 7)]
    assert [t for k, t in kinds if k == "circuit"] == ["T1>RP-1"]          # the feeder still wires
    assert [t for k, t in kinds if k == "loaded-family"] == ["LP-1", "LP-2", "T1", "RP-1", "R-1"]
    v = build["combination_verdict"]
    assert (v["n_loaded_families"], v["n_instances"]) == (5, 10)
    z = {c["tag"]: c["z_above_level_ft"] for c in build["elements_created"]
         if c["kind"] in ("equipment-instance", "fixture-instance")}
    assert {round(z[f"R-{i}"], 3) for i in range(1, 7)} == {round(1.1 * 3.280839895, 3)}
    assert z["LP-1"] == z["RP-1"] > z["R-1"]                               # boards at their own height
    assert build["circuits"]["ok"] is True and build["circuits"]["circuits_built"] == 1
    assert build["validation"]["combined"]["validate"]["n_errors"] == 0


@needs_base
@needs_catalog
def test_a_device_family_that_cannot_be_authored_costs_devices_only(tmp_path, monkeypatch):
    """The no-regression clause: the device family loads LAST, so when
    ``make_device`` cannot build it the batch stops THERE -- the lighting
    panel before it is loaded AND placed exactly as in a device-free job, the
    blocker names R-1, and no device instance is faked."""
    from rvt.famgen import factory as F

    def broken(*_a, **_kw):
        raise F.FactoryError("device facts withdrawn for this test")
    monkeypatch.setattr(F, "make_device", broken)
    r = FD.author(prompt="an electrical room with a 100 A lighting panel and 4 duplex receptacles",
                  out=str(tmp_path / "broken"), no_handoff=True)
    assert r.ok, (r.status, r.errors)                                     # delivered (rule 1)
    build = r.manifest["build"]
    assert build["errors"] == []
    load = build["load"]
    assert load["order"] == ["LP-1", "R-1"] and load["n_loaded"] == 1 and load["host_passes"] == 1
    assert load["blocker"].startswith("R-1:") and "device facts withdrawn" in load["blocker"]
    kinds = [(c["kind"], c["tag"]) for c in build["elements_created"]]
    assert ("equipment-instance", "LP-1") in kinds and ("loaded-family", "LP-1") in kinds
    assert not [k for k, _t in kinds if k == "fixture-instance"]
    assert [d for d in build["degradations"] if d.startswith("family LOAD blocked at R-1")]
    v = build["combination_verdict"]
    assert (v["mode"], v["n_loaded_families"], v["n_instances"]) == ("stamp-proof-only", 1, 1)
    assert build["validation"]["combined"]["validate"]["n_errors"] == 0


@needs_base
@needs_catalog
def test_strict_split_isolates_the_placed_devices_in_the_equipment_file(tmp_path):
    r = FD.author(prompt="a room with 4 duplex receptacles", out=str(tmp_path / "strict"),
                  strict=True, no_handoff=True)
    assert r.ok, (r.status, r.errors)
    build = r.manifest["build"]
    assert build["combination_verdict"]["mode"] == "split-strict"
    assert set(build["files"]) == {"shell", "equipment"}
    devices = [c for c in build["elements_created"] if c["kind"] == "fixture-instance"]
    assert len(devices) == 4 and {c["file_role"] for c in devices} == {"E(equipment)"}
    walls = [c for c in build["elements_created"] if c["kind"] == "wall"]
    assert len(walls) == 4 and {c["file_role"] for c in walls} == {"W(shell)"}
    for role in ("shell", "equipment"):
        assert build["validation"][role]["validate"]["n_errors"] == 0, role
    shell = _readback(build["files"]["shell"]["path"])
    assert shell.ids_of_class("FamilyInstance") == []                    # the certified shape: no placement
    equip = _readback(build["files"]["equipment"]["path"])
    assert len(equip.ids_of_class("FamilyInstance")) == 4
