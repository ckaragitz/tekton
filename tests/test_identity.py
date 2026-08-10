"""identity stream tests -- the BORN IDENTITY lane (birthright v4), the
identity forensics record, and the staged identity cells.

Three layers, no viewer and no heavy builds:

1. the v4 lane pure contracts (suffix re-mint / flags law / census /
   pipeline dispatch / refusals) on toy documents, plus the lane over the
   three real famgen products (bundled spec; #388);
2. pins on the MEASURED forensic record
   (``experiments/identity/identity_diff.json``);
3. pins on the built probes + staged batch
   (``experiments/identity/accounting.json``) -- surgical single-variable
   claims, identity census, zero-donor.

Layers 2-3 skip when the evidence has not been generated (fresh clone).
"""
import hashlib
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from rvt.famgen import birthright as BR                          # noqa: E402

DIFF = os.path.join(ROOT, "experiments", "identity", "identity_diff.json")
ACCT = os.path.join(ROOT, "experiments", "identity", "accounting.json")
PROBES = os.path.join(ROOT, "experiments", "identity", "probes.json")


def _j(path):
    with open(path) as fh:
        return json.load(fh)


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ===========================================================================
# toy documents (test_species' duck shape)
# ===========================================================================

class _El:
    def __init__(self, eid, cls, obj=None, header=None, rep=None, owner=-1):
        self.elem_id = eid
        self.class_name = cls
        self.obj = obj if obj is not None else {}
        self.header = header if header is not None else {}
        self.rep = rep
        self.owner_id = owner
        self.kind = ""


class _Doc:
    def __init__(self, els, finalized=True):
        self.elements = els
        self.finalized = finalized


def _param(eid, session="ab" * 16, embedded=None, tail="1.0.0",
           flags=8218):
    emb = eid if embedded is None else embedded
    tid = f"revit.local.family:{session}{emb & 0xFFFFFFFF:08x}-{tail}"
    return _El(eid, "ParamElemFamily",
               obj={"m_pParamDef": {"ptr_class": "ParamDefValue", "pid": -1,
                                    "value": {"m_typeId": {"m_typeId": tid},
                                              "m_caption": f"P{eid}"}}},
               header={"m_abFlags4Bytes": flags})


def _tid_of(el):
    return el.obj["m_pParamDef"]["value"]["m_typeId"]["m_typeId"]


# ===========================================================================
# 1. the IDENTITY lane -- pure contracts
# ===========================================================================

class TestBornIdentityLane:
    def test_suffix_remint_and_flags(self):
        els = [
            _param(1474542),
            _param(1474543),
            _El(1474527, "Level", header={"m_abFlags4Bytes": 2058}),
            _El(1474540, "RefPlane", header={"m_abFlags4Bytes": 2058}),
            _El(1474536, "SunAndShadowSettings",
                header={"m_abFlags4Bytes": 10}),
            _El(999, "ExtrusionElem", header={"m_abFlags4Bytes": 3896}),
        ]
        d = _Doc(els)
        rep = BR.apply_born_identity(d)
        assert rep["applied"] is True
        assert rep["n_suffixes_reminted"] == 2
        # suffixes now frozen-birth: base + k, in id order
        assert _tid_of(els[0]).endswith(
            f"{BR.BIRTH_SUFFIX_BASE:08x}-1.0.0")
        assert _tid_of(els[1]).endswith(
            f"{BR.BIRTH_SUFFIX_BASE + 1:08x}-1.0.0")
        # session hex untouched
        assert ("ab" * 16) in _tid_of(els[0])
        # covered flags set to the born table
        assert els[2].header["m_abFlags4Bytes"] == 2074
        assert els[3].header["m_abFlags4Bytes"] == 2074
        assert els[4].header["m_abFlags4Bytes"] == 8222
        # uncovered class untouched
        assert els[5].header["m_abFlags4Bytes"] == 3896
        assert rep["flags_changed"] == 3

    def test_census_green_after_lane(self):
        els = [_param(1474542), _El(1474527, "Level",
                                    header={"m_abFlags4Bytes": 2058})]
        d = _Doc(els)
        BR.apply_born_identity(d)
        c = BR.identity_census(d)
        assert c["identity_ok"] is True
        assert c["n_params"] == 1
        assert not c["self_minted"]

    def test_census_flags_self_mint(self):
        d = _Doc([_param(1474542)])          # SELF, un-normalized
        c = BR.identity_census(d)
        assert c["identity_ok"] is False
        assert c["checks"]["no_self_minted_suffix"] is False

    def test_census_flags_off_table(self):
        els = [_param(10, embedded=4096),
               _El(20, "Level", header={"m_abFlags4Bytes": 2058})]
        c = BR.identity_census(_Doc(els))
        assert c["identity_ok"] is False
        assert c["checks"]["born_header_flags"] is False
        assert c["flags_off"][0]["class"] == "Level"

    def test_census_flags_big_suffix(self):
        d = _Doc([_param(10, embedded=1474542)])   # frozen but host-scale
        c = BR.identity_census(d)
        assert c["identity_ok"] is False
        assert c["checks"]["suffixes_in_small_birth_space"] is False

    def test_refuses_unfinalized(self):
        d = _Doc([_param(1)], finalized=False)
        with pytest.raises(ValueError, match="not finalized"):
            BR.apply_born_identity(d)

    def test_refuses_non_self_mint(self):
        d = _Doc([_param(1474542, embedded=4208)])
        with pytest.raises(ValueError, match="not the famgen SELF mint"):
            BR.apply_born_identity(d)

    def test_refuses_missing_session_identity(self):
        el = _El(5, "ParamElemFamily",
                 obj={"m_pParamDef": {"value": {"m_typeId":
                                                {"m_typeId": "autodesk."
                                                             "spec"}}}})
        with pytest.raises(ValueError, match="no 'revit.local.family:'"):
            BR.apply_born_identity(_Doc([el]))

    def test_accepts_dbview3d_and_splits_extent_role(self):
        # since #381/#383 every generated family carries the "View 1"
        # DBView3d: its ExtentElem satellite gets the born role value 10,
        # plan/section satellites keep the table's 26 (specimen 26x6/10x1)
        els = [_param(1),
               _El(2, "DBViewPlan", header={"m_abFlags4Bytes": 10}),
               _El(3, "DBView3d", header={"m_abFlags4Bytes": 10}),
               _El(4, "ExtentElem", obj={"m_dbViewId": 2},
                   header={"m_abFlags4Bytes": 10}),
               _El(5, "ExtentElem", obj={"m_dbViewId": 3},
                   header={"m_abFlags4Bytes": 26})]
        d = _Doc(els)
        rep = BR.apply_born_identity(d)
        assert els[3].header["m_abFlags4Bytes"] == 26
        assert els[4].header["m_abFlags4Bytes"] == BR.BORN_EXTENT_FLAGS_3D \
            == 10
        assert els[2].header["m_abFlags4Bytes"] == 10      # DBView3d untouched
        assert rep["extent_roles"] == {"plan_section": 1, "view3d": 1}
        assert rep["flags_classes"]["ExtentElem"] == 2
        c = BR.identity_census(d)
        assert c["identity_ok"] is True, c["flags_off"]
        # the census applies the same split: a 3D satellite left at 26 is off
        els[4].header["m_abFlags4Bytes"] = 26
        c = BR.identity_census(d)
        assert c["checks"]["born_header_flags"] is False
        assert c["flags_off"] == [{"id": 5, "class": "ExtentElem",
                                   "got": 26, "want": 10}]

    def test_refuses_extent_naming_absent_view(self):
        d = _Doc([_El(4, "ExtentElem", obj={"m_dbViewId": 99},
                      header={"m_abFlags4Bytes": 26})])
        with pytest.raises(ValueError, match="names view 99"):
            BR.apply_born_identity(d)

    def test_refuses_missing_flags_key(self):
        d = _Doc([_El(3, "Level", header={})])
        with pytest.raises(ValueError, match="no m_abFlags4Bytes"):
            BR.apply_born_identity(d)

    def test_deterministic(self):
        def build():
            d = _Doc([_param(1474542), _param(1474543)])
            BR.apply_born_identity(d)
            return [_tid_of(e) for e in d.elements]
        assert build() == build()


class TestPipelineDispatch:
    def test_v4_lanes(self):
        assert BR._V4_LANES == BR._V3_LANES + ("identity",)
        assert "hostsym" in BR._V4_LANES

    def test_enabled_rejects_unknown_version(self):
        with pytest.raises(ValueError, match="unknown version"):
            with BR.enabled(os.path.join(ROOT, "experiments", "birthright",
                                         "template_birth.json"), version=5):
                pass

    def test_apply_v4_routes_through_v3(self, monkeypatch):
        calls = {}

        def fake_v3(doc, spec, lanes=None):
            calls["v3_lanes"] = lanes
            return {"version": 3, "lanes": list(lanes or ())}

        monkeypatch.setattr(BR, "apply_birthright_v3", fake_v3)
        d = _Doc([_param(1474542)])
        rep = BR.apply_birthright_v4(d, spec=None)
        assert rep["version"] == 4
        assert "identity" in rep["lanes"]
        assert "identity" not in (calls["v3_lanes"] or ())
        assert rep["identity"]["applied"] is True
        assert rep["identity_census"]["identity_ok"] is True

    def test_loader_half_states_native_verdict(self):
        # tools/identity_probe.py DEMO v10 keys on 'native' (the loader
        # authors the shape itself since #10, so 'applied' is False there)
        def fam(names):
            return _El(9, "Family", obj={"m_pFamilyTypes": {"value": {
                "m_pairs": [{"name": n} for n in names], "m_idx": 0}}})
        lawful = BR.apply_host_family_table_law(fam([" ", "225A"]))
        assert (lawful["applied"], lawful["native"]) == (False, True)
        stripped = BR.apply_host_family_table_law(fam([" ", " ", "225A"]))
        assert (stripped["applied"], stripped["native"]) == (True, True)
        off = BR.apply_host_family_table_law(fam(["225A"]))
        assert (off["applied"], off["native"]) == (False, False)
        assert off["why"]
        assert BR.apply_host_family_table_law(fam([]))["native"] is False

    def test_apply_v4_refuses_red_census(self, monkeypatch):
        monkeypatch.setattr(BR, "apply_birthright_v3",
                            lambda doc, spec, lanes=None: {"version": 3})
        monkeypatch.setattr(BR, "identity_census",
                            lambda doc: {"identity_ok": False,
                                         "checks": {"x": False},
                                         "n_params": 0})
        with pytest.raises(ValueError, match="census not green"):
            BR.apply_birthright_v4(_Doc([_param(7)]), spec=None)


SPEC = os.path.join(ROOT, "experiments", "birthright", "template_birth.json")


@pytest.mark.skipif(not os.path.isfile(SPEC), reason="mined spec absent")
class TestV4LaneOnRealProducts:
    """The v4 lane over the REAL famgen products (fresh-clone safe: bundled
    spec, no samples).  #388: every generated family carries the "View 1"
    DBView3d since #381/#383, and the lane raised on all three products
    while the toy-document tests stayed green -- so the products themselves
    are pinned here, and the next view-constellation change trips a test."""

    @pytest.fixture(scope="class")
    def built(self):
        from rvt.famgen import factory as F
        out = {}
        with BR.enabled(SPEC, version=4) as ctx:
            for name in ("make_panelboard", "make_luminaire",
                         "make_transformer"):
                prod = getattr(F, name)(start_id=3000)
                out[name] = (prod, ctx["reports"][-1])
        return out

    @pytest.mark.parametrize("name", ["make_panelboard", "make_luminaire",
                                      "make_transformer"])
    def test_builds_green_through_v4(self, built, name):
        prod, entry = built[name]
        rep = entry["report"]
        assert rep["version"] == 4
        assert rep["identity"]["applied"] is True
        assert rep["identity_census"]["identity_ok"] is True
        assert entry["verify"]["ok"] is True
        assert BR.identity_census(prod.doc)["identity_ok"] is True

    def test_extent_role_split_on_panelboard(self, built):
        prod, entry = built["make_panelboard"]
        els = prod.doc.elements
        cls_of = {int(e.elem_id): e.class_name for e in els}
        roles = {}
        for e in els:
            if e.class_name == "ExtentElem":
                view_cls = cls_of[e.obj["m_dbViewId"]]
                roles.setdefault(view_cls, set()).add(
                    e.header["m_abFlags4Bytes"])
        # the family view set: Ref. Level plan + ceiling plan (DBViewPlan)
        # and "View 1" (DBView3d) -- satellites 26 / 26 / 10
        assert roles == {"DBViewPlan": {26}, "DBView3d": {10}}, roles
        assert entry["report"]["identity"]["extent_roles"] == \
            {"plan_section": 2, "view3d": 1}
        # every other covered class carries the table value uniformly
        for e in els:
            want = BR.BORN_HEADER_FLAGS.get(e.class_name)
            if want is not None and e.class_name != "ExtentElem":
                assert e.header["m_abFlags4Bytes"] == want, e.class_name


class TestBornFlagsTable:
    #: measured on vendor/phi-ag-rvt racbasicsamplefamily-2026.rfa (the
    #: T2a source); a drift here means the authority file changed
    EXPECT = {"Level": 2074, "LevelAttributes": 30, "DBViewType": 26,
              "DBViewPlan": 26, "Viewer": 26, "Viewport": 26,
              "DBDrawing": 8218, "ExtentElem": 26, "SketchPlane": 26,
              "RefPlane": 2074, "SunAndShadowSettings": 8222}

    def test_table_values(self):
        assert BR.BORN_HEADER_FLAGS == self.EXPECT

    def test_birth_space_disjoint_from_specimen_params(self):
        # the .rfa's own params sit at 4208..5812; our mint must not
        # collide inside its span
        assert BR.BIRTH_SUFFIX_BASE + BR._BIRTH_SUFFIX_SPAN <= 4208

    @pytest.mark.skipif(not os.path.isfile(os.path.join(
        ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
        "racbasicsamplefamily-2026.rfa")), reason="vendor .rfa absent")
    def test_table_matches_rfa_authority(self):
        from rvt.families import FamilyIndex
        import collections
        idx = FamilyIndex(os.path.join(
            ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
            "racbasicsamplefamily-2026.rfa"))
        recs = idx.unit_records(0)
        seen = collections.defaultdict(collections.Counter)
        for e in recs.get(101, {}):
            if e not in recs.get(102, {}):
                continue
            cn = idx.class_name(recs[102][e].class_id)
            h = idx.value(0, e, 101) or {}
            seen[cn][h.get("m_abFlags4Bytes")] += 1
        for cls, want in BR.BORN_HEADER_FLAGS.items():
            vals = seen.get(cls)
            if not vals:
                continue                      # class absent from specimen
            if cls == "ExtentElem":
                # role-split in the specimen: plan/section 26, DBView3d 10
                assert vals.most_common(1)[0][0] == want
                assert set(vals) <= {26, 10}
                continue
            assert set(vals) == {want}, f"{cls}: {dict(vals)}"


# ===========================================================================
# 2. pins on the forensic record
# ===========================================================================

needs_diff = pytest.mark.skipif(not os.path.isfile(DIFF),
                                reason="identity_diff.json not generated")


@needs_diff
class TestForensicRecord:
    @pytest.fixture(scope="class")
    def diff(self):
        return _j(DIFF)

    def test_host_writes_identical(self, diff):
        hw = diff["host_side_writes"]
        assert hw["document_increment_table"]["t1ug_equals_tb0g_bytes"] \
            is True
        assert hw["history"]["touched_by_either"] is False
        assert hw["host_latest_adocument"]["n_leaf_diffs"] == 6

    def test_reduced_base_premise_falsified(self, diff):
        pr = diff["host_side_writes"]["reduced_base_identity_premise"]
        assert pr["history_entry_guids_equal_rst"] is True
        assert pr["dit_rows_equal_rst"] is True
        assert pr["surviving_elemtable_rows_changed_vs_rst"] == 0

    def test_native_identity_law(self, diff):
        law = diff["element_identity"]["param_identity_strings"][
            "native_law"]
        assert law["rst_host"]["OTHER"] == 0
        assert law["rst_host"]["SELF"] > 0
        assert law["rst_units"]["OTHER"] == 0
        assert law["rst_units"]["SELF"] > 0

    def test_self_other_split_separates_cells(self, diff):
        cells = diff["element_identity"]["param_identity_strings"][
            "cells_on_g_abpd"]
        assert cells["T2a (PASS)"] == {"all:OTHER": 6}
        assert cells["TB0g (PASS)"] == {"all:OTHER": 3}
        assert cells["T1uG (FAIL)"]["ours:SELF"] == 14
        assert cells["SC1 (FAIL)"] == {"all:SELF": 14}

    def test_ranked_fix_list(self, diff):
        ranks = [r["rank"] for r in diff["ranked_fix_list"]]
        assert ranks[:2] == [1, 2]
        assert "identity suffix" in diff["ranked_fix_list"][0]["field"] \
            or "m_typeId" in diff["ranked_fix_list"][0]["field"]
        assert "m_abFlags4Bytes" in diff["ranked_fix_list"][1]["field"]

    def test_flags_deviations_cover_born_table_only(self, diff):
        devs = diff["element_identity"]["header_flags"][
            "ours_deviations_vs_born_table"]
        assert devs, "expected measured deviations"
        for d in devs:
            assert d["class"] in BR.BORN_HEADER_FLAGS


# ===========================================================================
# 3. pins on the built probes + staged batch
# ===========================================================================

needs_acct = pytest.mark.skipif(not os.path.isfile(ACCT),
                                reason="probes not built")


@needs_acct
class TestBuiltProbes:
    @pytest.fixture(scope="class")
    def acct(self):
        return _j(ACCT)

    def test_no_build_errors(self, acct):
        assert not acct.get("errors"), acct.get("errors")

    def test_gates_green(self, acct):
        for name in ("I1", "BX_v4", "DEMO_250v_room_v10"):
            g = acct["gates"].get(name) or {}
            assert g.get("gates_ok") is True, f"{name}: {g}"

    def test_i1_base_byte_identity_then_surgical(self, acct):
        info = acct["built"]["I1"]
        bi = info["base_byte_identity"]
        assert all(bi["segments_byte_identical"].values())
        sp = info["surgical_proof"]
        assert sp["surgical"] is True
        assert sp["seq103_byte_identical"] is True
        # 14 identity suffixes in seq-102, 12 flag words in seq-101
        assert len(sp["seq102_differing_records"]) == 14
        assert len(sp["seq101_differing_records"]) == 12

    def test_i1_birth_ids_continue_shell_space(self, acct):
        info = acct["built"]["I1"]
        assert info["normalization"]["birth_ids"] == \
            list(range(7675, 7675 + 14))
        assert info["file_identity_census"]["all_other_form"] is True

    def test_bx_v4_identity_and_species(self, acct):
        info = acct["built"]["BX_v4"]
        assert info["birthright"]["version"] == 4
        assert info["birthright"]["identity_census"]["identity_ok"] is True
        assert info["file_identity_census"]["all_other_form"] is True
        assert info["species"]["species_ok"] is True

    def test_bx_v4_same_spec_and_binds_as_sc1(self, acct):
        # single-variable claim vs BX_v3/SC1: same birth spec + binds
        info = acct["built"]["BX_v4"]
        sp_acct = os.path.join(ROOT, "experiments", "species",
                               "accounting.json")
        if not os.path.isfile(sp_acct):
            pytest.skip("species accounting absent")
        v3 = _j(sp_acct)["built"].get("BX_v3")
        if not v3:
            pytest.skip("BX_v3 not built")
        assert info["birth_spec_sha256"] == v3["birth_spec_sha256"]
        assert info["binds"] == v3["binds"]

    def test_demo_v10_all_families_green(self, acct):
        info = acct["built"]["DEMO_250v_room_v10"]
        assert info["n_families"] >= 6
        assert all(x["census_ok"] for x in info["identity_per_family"])
        assert info["file_identity_census"]["all_other_form"] is True
        assert info["species"]["species_ok"] is True

    def test_zero_donor_in_shipped_lanes(self, acct):
        """BX_v4 + DEMO v10 carry OUR minted identity only: every unit
        param suffix is in the private birth space, never a donor id."""
        import identity_probe as IP
        for name in ("BX_v4", "DEMO_250v_room_v10"):
            info = acct["built"].get(name)
            if not info:
                continue
            path = os.path.join(ROOT, info["file"])
            if not os.path.isfile(path) or _md5(path) != info["md5"]:
                pytest.skip(f"{name} file drifted/absent")
            from rvt.families import FamilyIndex
            n_units = len(FamilyIndex(path).units)
            for u in range(1, n_units):
                for row in IP._param_identities(path, u):
                    emb = row.get("embedded_id")
                    assert emb is not None
                    assert BR.BIRTH_SUFFIX_BASE <= emb < \
                        BR.BIRTH_SUFFIX_BASE + BR._BIRTH_SUFFIX_SPAN

    def test_md5_pins(self, acct):
        for name, info in acct["built"].items():
            path = os.path.join(ROOT, info["file"])
            if os.path.isfile(path):
                assert _md5(path) == info["md5"], f"{name} drifted"


@needs_acct
class TestStagedBatch:
    def test_batch_manifest(self):
        probes = _j(PROBES) if os.path.isfile(PROBES) else {}
        if not probes:
            pytest.skip("probes.json absent")
        import glob
        batches = sorted(glob.glob(os.path.join(
            ROOT, "experiments", "acceptance", "batch_*.json")))
        ours = None
        for b in reversed(batches):
            m = _j(b)
            if "identity_probe" in str(m.get("tool", "")):
                ours = m
                break
        if ours is None:
            pytest.skip("identity batch not staged yet")
        assert ours["control_count"] >= 1
        names = [os.path.basename(e["file"]) for e in ours["entries"]]
        for want in ("I1.rvt", "BX_v4.rvt", "DEMO_250v_room_v10.rvt"):
            assert want in names
        assert ours["reading_order"][0].startswith("CTRL_")
        # staged copies byte-match their manifests (the staged .rvt binaries
        # are git-ignored: absent on a fresh clone -> skip, never fail)
        if not any(os.path.isfile(os.path.join(ROOT, e.get("staged_as") or e["file"]))
                   for e in ours["entries"]):
            pytest.skip("staged binaries are git-ignored and absent (fresh clone)")
        for e in ours["entries"]:
            staged = e.get("staged_as") or e["file"]
            path = os.path.join(ROOT, staged)
            assert os.path.isfile(path), staged
            assert _md5(path) == e["md5"], staged
