"""selfcontained stream (THE CLOSE): pins for the census instrument, the
render-bind law, the SC1/base-ladder/DEMO v8 build evidence, and batch 53.

Everything here reads artifacts the stream already built (fast), except
one live rebind test that authors a fresh product through the lane.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = os.path.join(ROOT, "experiments", "selfcontained")
ACCT = os.path.join(OUT, "accounting.json")
PROBES = os.path.join(OUT, "probes.json")
HR1 = os.path.join(OUT, "hr1_report.json")
BINDS = os.path.join(OUT, "render_binds.json")
BATCH = os.path.join(ROOT, "experiments", "acceptance", "batch_53.json")
BIRTH_SPEC = os.path.join(ROOT, "experiments", "birthright",
                          "template_birth.json")

G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
K4 = os.path.join(ROOT, "experiments", "genesis", "triage", "K4.rvt")
G_ABP = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                     "G_ABP.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(ACCT), reason="selfcontained artifacts not built")


def _j(path):
    with open(path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# the render-bind sidecar
# ---------------------------------------------------------------------------

class TestBindSpec:
    def test_shape_and_roles(self):
        from rvt.famgen import birthright as BR
        spec = BR.read_bind_spec(BINDS)
        assert set(spec["binds"]) == set(BR.BIND_ROLES)
        for node in spec["binds"].values():
            assert set(node) == {"__eid__"}

    def test_measured_values(self):
        """[V specimen] solid 4087 / face-fill 5564 / sketch 4123 /
        material 5265 -- the born render-bind law."""
        b = _j(BINDS)["binds"]
        assert b["solid_style"]["__eid__"] == 4087
        assert b["face_fill_style"]["__eid__"] == 5564
        assert b["sketch_style"]["__eid__"] == 4123
        assert b["render_material"]["__eid__"] == 5265

    def test_zero_donor_identity(self):
        raw = json.dumps(_j(BINDS))
        for needle in ("Autodesk\\u00ae", "OneDrive", "Users\\\\",
                       "rstbasic", "acme"):
            assert needle not in raw
        # only integer ids ride in the binds
        for node in _j(BINDS)["binds"].values():
            assert isinstance(node["__eid__"], int)

    def test_targets_in_birth_set(self):
        have = {e["born_id"] for e in _j(BIRTH_SPEC)["birth_elements"]}
        for node in _j(BINDS)["binds"].values():
            assert node["__eid__"] in have


# ---------------------------------------------------------------------------
# the census instrument, pinned on the known cells
# ---------------------------------------------------------------------------

class TestCensusInstrument:
    def test_hr1_report_exists_with_all_censuses(self):
        r = _j(HR1)
        for name in ("U16g", "T1v", "T2a", "T1r", "B0", "BX_birth", "U16"):
            assert name in r["censuses"], name

    def test_t2a_is_the_only_walked_self_contained_g_abpd_famdoc(self):
        """The HR1 separator: T2a (PASS) walked-self-contained; every
        failing ours-content famdoc is not."""
        c = _j(HR1)["censuses"]
        assert c["T2a"]["units"][0]["walked_binds"]["self_contained"] is True
        for name in ("T1v", "B0", "BX_birth", "U16g"):
            assert c[name]["units"][0]["walked_binds"]["self_contained"] \
                is False, name

    def test_u16g_host_resident_enumeration(self):
        """The charter's 29 (seq-102) + the header/rep surfaces."""
        u = _j(HR1)["censuses"]["U16g"]["units"][0]
        assert u["totals"]["seq102_host"] == 29
        assert u["totals"]["seq101_host"] == 23
        assert u["totals"]["seq103_host"] == 51
        assert u["host_resident_total"] == 103

    def test_ours_famdocs_zero_host_refs_but_unbound(self):
        """B0/BX_birth: zero host-resident refs on all four surfaces --
        the failure is the UNBOUND walk, not literal host ids."""
        c = _j(HR1)["censuses"]
        for name in ("B0", "BX_birth"):
            u = c[name]["units"][0]
            assert u["host_resident_total"] == 0, name
            assert u["walked_binds"]["unbound_form"] > 0, name

    def test_target_diffs_all_substituted_or_missing(self):
        rows = _j(HR1)["target_diffs_rst_vs_G_ABPD"]
        by_t = {r["target"]: r for r in rows}
        assert by_t[3644]["verdict"].startswith("MISSING")
        for t in (7845, 12632, 429, 1177727, 311, 86961):
            assert by_t[t]["verdict"] == "SUBSTITUTED (ours)", t
            assert by_t[t]["bytes_same_101"] is True, t  # headers identical

    def test_ranked_objections_present(self):
        r = _j(HR1)
        ranks = [o["rank"] for o in r["ranked_objections"]]
        assert ranks == [1, 2, 3, 4, 5]
        assert "compose_side_alternative" in r


# ---------------------------------------------------------------------------
# the live rebind lane (one fresh product through birthright + binds)
# ---------------------------------------------------------------------------

class TestRebindLane:
    def test_apply_render_binds_makes_walk_self_contained(self):
        import famdoc_bisect as FB
        from rvt.famgen import birthright as BR
        FB.OUT_DIR = os.path.join(OUT, "_build", "_test_fb")
        FB.BUILD_DIR = os.path.join(FB.OUT_DIR, "_build")
        spec = BR.read_birth_spec(BIRTH_SPEC)
        binds = BR.read_bind_spec(BINDS)
        with BR.enabled(spec, binds=binds) as ctx:
            from rvt.famgen import factory as F
            prod = FB.our_product(9000000)
        assert ctx["reports"], "birthright hook did not fire"
        ent = ctx["reports"][0]
        assert (ent.get("verify") or {}).get("ok") is True
        census = ent["walked_bind_census"]
        assert census["self_contained"] is True
        assert census["foreign"] == 0 and census["unbound_form"] == 0
        b = ent["binds"]["bound"]
        assert b["solid_nodes"] == 1
        assert b["faces_render"] == 6
        assert b["sketch_curves"] == 4
        assert b["material_field"] == 1
        # bound targets are authored in-unit rows of the right class
        by_id = {e.elem_id: e for e in prod.doc.elements}
        t = ent["binds"]["targets"]
        assert by_id[t["solid_style"]].class_name == "GStyleElem"
        assert by_id[t["sketch_style"]].class_name == "GStyleElem"
        assert by_id[t["render_material"]].class_name == "MaterialElem"

    def test_bind_spec_missing_role_refused(self, tmp_path):
        from rvt.famgen import birthright as BR
        bad = tmp_path / "binds.json"
        bad.write_text(json.dumps(
            {"binds": {"solid_style": {"__eid__": 4087}}}))
        with pytest.raises(ValueError, match="missing roles"):
            BR.read_bind_spec(str(bad))

    def test_bind_spec_identity_shape_refused(self, tmp_path):
        from rvt.famgen import birthright as BR
        bad = tmp_path / "binds.json"
        binds = {r: {"__eid__": 1} for r in BR.BIND_ROLES[:-1]}
        binds[BR.BIND_ROLES[-1]] = {"name": "vendor material"}
        bad.write_text(json.dumps({"binds": binds}))
        with pytest.raises(ValueError, match="symbolic"):
            BR.read_bind_spec(str(bad))

    def test_apply_refuses_target_outside_idmap(self):
        from rvt.famgen import birthright as BR

        class _El:
            def __init__(self):
                self.elem_id, self.class_name = 1, "GStyleElem"
                self.rep, self.obj, self.notes = None, {}, []

        class _Doc:
            elements = [_El()]

        with pytest.raises(ValueError):
            BR.apply_render_binds(
                _Doc(), {"binds": {r: {"__eid__": 999999}
                                   for r in BR.BIND_ROLES}}, {})


# ---------------------------------------------------------------------------
# the built probes' evidence
# ---------------------------------------------------------------------------

class TestBuiltProbes:
    def test_all_four_built_gates_green(self):
        a = _j(ACCT)
        for n in ("SC1", "U16gK4", "U16gABP", "DEMO_250v_room_v8"):
            assert a["gates"][n]["gates_ok"] is True, n
        assert not a["errors"]

    def test_sc1_machine_verified_self_contained(self):
        a = _j(ACCT)
        sc = a["built"]["SC1"]["self_containment"]
        assert sc["host_resident_total"] == 0
        assert sc["walked_self_contained"] is True
        assert sc["self_contained"] is True
        wb = sc["units"][0]["walked_binds"]
        assert wb["unbound_form"] == 0 and wb["foreign"] == 0
        assert len(wb["faces_render"]) == 6
        assert len(set(wb["faces_render"])) == 1     # one material, 6 faces

    def test_sc1_lane_is_t2a_exact(self):
        """SC1 rode the T-lane: famload + place_one on G_ABPD, +1 unit on
        the load hop, +0 on the instance hop, dangling-free."""
        g = _j(ACCT)["gates"]["SC1"]
        assert g["load_hop_units_added"] == 1
        assert g["instance_hop_units_added"] == 0
        assert g["instance_zero_dangling"] is True

    def test_ladder_byte_identity_to_u16(self):
        a = _j(ACCT)
        for n in ("U16gK4", "U16gABP"):
            bi = a["built"][n]["byte_identity"]
            assert all(bi["segments_byte_identical"].values()), n
            rr = a["built"][n]["reference_resolution"]
            assert rr["standalone_dangling_host_resident"] == 29, n
            assert rr["unresolved_anywhere"] == 0, n

    def test_ladder_same_host_allocation_as_u16g(self):
        """wm(K4) == wm(G_ABP) == wm(G_ABPD) == 1472524 => the three base
        cells share famdoc bytes AND host ids (pure base split)."""
        a = _j(ACCT)
        for n in ("U16gK4", "U16gABP"):
            i = a["built"][n]
            assert i["symbol_id"] == 1474584, n
            assert i["family_id"] == 1474565, n
            assert i["instance_ids"] == [1474585], n

    def test_ladder_premise_targets(self):
        """K4's referenced targets are BORN (byte == rst); G_ABP's are
        SUBSTITUTED (byte == G_ABPD, != rst)."""
        from rvt.families import FamilyIndex
        hosts = {n: FamilyIndex.open(p) for n, p in
                 (("rst", RST), ("K4", K4), ("ABP", G_ABP),
                  ("ABPD", G_ABPD))}

        def rec(h, t):
            return hosts[h].unit_records(0).get(102, {}).get(t)

        for t in (7845, 1177727, 201):
            assert rec("K4", t).payload == rec("rst", t).payload, t
            assert rec("ABP", t).payload == rec("ABPD", t).payload, t
            assert rec("ABP", t).payload != rec("rst", t).payload, t

    def test_demo_v8_six_self_contained_units(self):
        a = _j(ACCT)
        i = a["built"]["DEMO_250v_room_v8"]
        assert i["n_families"] == 6
        sc = i["self_containment"]
        assert len(sc["units"]) == 6
        assert sc["host_resident_total"] == 0
        assert sc["walked_self_contained"] is True
        for u in sc["units"]:
            assert u["n_records_102"] == 1724
            assert u["walked_binds"]["self_contained"] is True


# ---------------------------------------------------------------------------
# probes.json + the staged batch
# ---------------------------------------------------------------------------

class TestStagedRound:
    def test_probes_json_shape(self):
        m = _j(PROBES)
        rungs = [p["rung"] for p in m["probes"]]
        assert rungs == ["SC1", "U16gK4", "U16gABP", "DEMO_250v_room_v8"]
        assert "reading_the_matrix" in m
        for key in ("SC1 PASS", "SC1 FAIL", "U16gK4 PASS + U16gABP FAIL",
                    "U16gK4 PASS + U16gABP PASS", "U16gK4 FAIL",
                    "SC1 PASS + DEMO v8 PASS", "SC1 PASS + DEMO v8 FAIL"):
            assert key in m["reading_the_matrix"], key
        assert "u16g25_blocker" in m
        assert "v=9 cls=0x391" in m["u16g25_blocker"]

    def test_batch_53_staged_and_md5_verified(self):
        import hashlib
        m = _j(BATCH)
        assert m["control_count"] == 3
        names = m["reading_order"]
        assert names[:3] == ["CTRL_G_ABPD_b53.rvt", "CTRL_K4_b53.rvt",
                             "CTRL_G_ABP_b53.rvt"]
        assert names[3:] == ["SC1.rvt", "U16gK4.rvt", "U16gABP.rvt",
                             "DEMO_250v_room_v8.rvt"]
        for e in m["entries"]:
            p = os.path.join(ROOT, e.get("staged_as") or e["file"])
            with open(p, "rb") as fh:
                assert hashlib.md5(fh.read()).hexdigest() == e["md5"], p

    def test_controls_are_byte_identical_certified_copies(self):
        import hashlib

        def md5(p):
            with open(p, "rb") as fh:
                return hashlib.md5(fh.read()).hexdigest()

        acc = os.path.join(ROOT, "experiments", "acceptance")
        assert md5(os.path.join(acc, "CTRL_G_ABPD_b53.rvt")) == md5(G_ABPD)
        assert md5(os.path.join(acc, "CTRL_K4_b53.rvt")) == md5(K4)
        assert md5(os.path.join(acc, "CTRL_G_ABP_b53.rvt")) == md5(G_ABP)
