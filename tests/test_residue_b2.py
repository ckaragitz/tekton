"""Tests for rvt.genesis.residue_b2 -- THE PALETTE-BUCKET FIX
(genesis-palette-fix stream: the one named constructor defect, Group B's
PALETTE bucket).

They pin: (1) the DIAGNOSIS -- residue_b's ORIGINAL structural / thermal
constructors carry the D1 int-param SWAP (m_paramId <-> m_value) and the D2
corpus-invariant violations (descending order, null ElementId set); (2) the
corrected helpers (correct keying, ascending order, present-empty ElementId
set, positive-id refusal); (3) the corrected constructor property_set_v2
over EVERY shape variant on the certified base Y9 -- byte-exact schema
round trip, zero swapped ints, ascending, ElementId set present, our
provenance (source cleared, house library GUID), class-family
correspondence; (4) the class-constrained role selection (zero family
mismatches over Y9's 28 property-set slots; residue_b's picker mis-classes
concrete / plastic slots); (5) the swap-fix detector/repair pair; (6) the
built probe set + probes.json contract when the files are present.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

Y9 = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "Y9.rvt")
ZB5 = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_b", "ZB5_palette.rvt")
OUT = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "palette_fix")

from rvt.genesis import residue_b as RB      # noqa: E402
from rvt.genesis import residue_b2 as B2     # noqa: E402


# ---------------------------------------------------------------------------
# fixtures: the certified base's substitution context (loaded once)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ctx():
    if not os.path.exists(Y9):
        pytest.skip("certified base Y9.rvt not present")
    import genesis_substitute as GS
    return GS.SubstContext(Y9, "test_residue_b2")


@pytest.fixture(scope="module")
def landed():
    return RB.y_ladder_landed()


@pytest.fixture(scope="module")
def pairs_v2(ctx, landed):
    return B2.propertyset_pairs_v2(ctx, landed)


# ---------------------------------------------------------------------------
# 1. THE DIAGNOSIS: the ORIGINAL constructors carry D1 (the int-param swap)
# ---------------------------------------------------------------------------

def _spec(pool, key):
    return next(s for s in pool if s["key"] == key)


def test_residue_b_structural_constructor_carries_the_int_param_swap():
    """D1, at the source: residue_b.structural_asset emits int params whose
    m_paramId is a small POSITIVE int and m_value the built-in id."""
    rec = RB.structural_asset(_spec(RB.STRUCTURAL_ASSETS, "steel_345"), elem_id=1_500_000)
    swapped = B2.swapped_int_entries(rec.obj)
    assert swapped, "residue_b.structural_asset must exhibit the D1 swap"
    for e in swapped:
        assert e["m_paramId"] >= 0 and e["m_value"] < 0
    # the concrete swap: the asset-class enum id lands in m_value
    assert any(e["m_value"] == -1150464 for e in swapped)


def test_residue_b_thermal_constructor_carries_the_int_param_swap():
    rec = RB.thermal_asset(_spec(RB.THERMAL_ASSETS, "steel"), elem_id=1_500_001)
    swapped = B2.swapped_int_entries(rec.obj)
    assert len(swapped) == 4, "the thermal asset carries 4 (swapped) int params"
    assert {e["m_value"] for e in swapped} >= {-1150464, -1140322}


def test_residue_b_originals_violate_the_ascending_order_law():
    """D2(a): the original constructors emit doubles in DESCENDING param-id
    order (the corpus is ascending 300/300)."""
    for rec in (RB.structural_asset(_spec(RB.STRUCTURAL_ASSETS, "steel_345"), elem_id=1_500_002),
                RB.thermal_asset(_spec(RB.THERMAL_ASSETS, "steel"), elem_id=1_500_003)):
        asc = B2.param_ids_ascending(rec.obj)
        assert asc["m_pDoubleParams"] is False


def test_residue_b_originals_emit_a_null_ElementId_set():
    """D2(b): the corpus's PropertySetElement carries a PRESENT-empty
    ParamValueSetElementId (16/16 shapes); the originals emit None."""
    rec = RB.thermal_asset(_spec(RB.THERMAL_ASSETS, "concrete"), elem_id=1_500_004)
    ps = ((rec.obj.get("m_oParamSet") or {}).get("value") or {})
    assert ps.get("m_pElementIdParams") is None


@pytest.mark.skipif(not os.path.exists(ZB5), reason="the failing ZB5_palette.rvt not present")
def test_diagnosis_holds_on_the_failing_file():
    """The on-disk proof: EVERY landed PropertySetElement in the FAILING
    ZB5_palette.rvt carries the swap, a descending container and a null
    ElementId set."""
    d = B2.diagnose_zb5(ZB5)
    n = d["landed_propertysets"]
    assert n == 28
    assert d["objects_with_a_swapped_int"] == 28
    assert d["swapped_int_param_entries_total"] == 78          # 17 x 2 + 11 x 4
    assert d["objects_with_a_descending_container"] == 28
    assert d["objects_with_null_ElementId_set"] == 28


# ---------------------------------------------------------------------------
# 2. the corrected helpers
# ---------------------------------------------------------------------------

def _entries(pset: dict) -> list:
    return (pset.get("value") or {}).get("m_paramSet") or []


def test_int_param_set_is_correctly_keyed_and_ascending():
    ps = B2.int_param_set([(-1140322, 0), (-1150464, 3), (-1152338, 1)])
    ents = _entries(ps)
    assert [e["m_paramId"] for e in ents] == [-1152338, -1150464, -1140322]
    assert {e["m_paramId"]: e["m_value"] for e in ents} == {-1150464: 3, -1140322: 0, -1152338: 1}


def test_int_param_set_refuses_positive_param_ids():
    with pytest.raises(ValueError):
        B2.int_param_set([(3, -1150464)])            # the swapped call -- refused


def test_double_and_astring_sets_are_ascending():
    d = _entries(B2.double_param_set([(-1140300, 6.0), (-1140320, 1.66), (-1140309, 7.0)]))
    assert [e["m_paramId"] for e in d] == [-1140320, -1140309, -1140300]
    a = _entries(B2.astring_param_set([(-1150465, "sub"), (-1152342, "tok"), (-1150466, "n")]))
    assert [e["m_paramId"] for e in a] == [-1152342, -1150466, -1150465]


def test_elementid_param_set_empty_is_present_and_empty():
    ps = B2.elementid_param_set_empty()
    assert ps.get("ptr_class") == "ParamValueSetElementId"
    assert _entries(ps) == []


def test_unswap_repairs_exactly_the_swap_signature():
    obj = {"m_oParamSet": {"value": {"m_pIntParams": {"value": {"m_paramSet": [
        {"m_paramId": 3, "m_value": -1150464},        # swapped
        {"m_paramId": -1140322, "m_value": 0},        # already correct
    ]}}}}}
    assert len(B2.swapped_int_entries(obj)) == 1
    assert B2.unswap_int_params(obj) == 1
    ents = obj["m_oParamSet"]["value"]["m_pIntParams"]["value"]["m_paramSet"]
    assert ents[0] == {"m_paramId": -1150464, "m_value": 3}
    assert ents[1] == {"m_paramId": -1140322, "m_value": 0}
    assert B2.swapped_int_entries(obj) == []
    assert B2.unswap_int_params(obj) == 0                 # idempotent


def test_house_asset_library_guid_is_a_deterministic_valid_uuid5():
    g = uuid.UUID(B2.HOUSE_ASSET_LIBRARY_GUID)
    assert g.version == 5
    # deterministic: recomputing the module's derivation reproduces it
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, "rvt-writer.gen.house-standard")
    assert str(uuid.uuid5(ns, "asset-library/1")).upper() == B2.HOUSE_ASSET_LIBRARY_GUID
    # and it is not one of Autodesk's shipped library GUIDs
    autodesk = {"AD121259-C03E-4A1D-92D8-59A22B4807AD", "05AB8C01-9E15-4D19-8791-5CD982F715F4",
                "51130EE1-53FE-486E-B966-9316623FCB83", "314DE259-5443-4621-BFBD-1730C6CC9AE9"}
    assert B2.HOUSE_ASSET_LIBRARY_GUID not in autodesk


# ---------------------------------------------------------------------------
# 3. property_set_v2 on the certified base (every shape variant)
# ---------------------------------------------------------------------------
#: one representative slot per shape variant in Y9
SHAPE_SLOTS = {
    194585: ("structural", "legacy"),        # legacy 16-dbl steel '345 MPa'
    1177773: ("structural", "legacy"),       # legacy 15-dbl concrete
    1352644: ("structural", "legacy"),       # legacy 26-dbl 'Grade 65'
    174481: ("structural", "modern"),        # modern 43-dbl concrete
    174586: ("structural", "modern"),        # modern 43-dbl steel (5 ints)
    174509: ("structural", "modern"),        # modern 29-dbl soil (basic)
    174580: ("structural", "modern"),        # modern 47-dbl wood
    174516: ("thermal", "thermal"),          # thermal 11-dbl
    600685: ("thermal", "thermal-uw"),       # thermal 12-dbl with -1140309
}


@pytest.mark.parametrize("slot", sorted(SHAPE_SLOTS))
def test_property_set_v2_shape_variants(ctx, pairs_v2, slot):
    kind_exp, shape_exp = SHAPE_SLOTS[slot]
    by_slot = {s: (k, sp, fam) for s, k, sp, fam in pairs_v2}
    assert slot in by_slot, f"slot {slot} not a residue property set"
    kind, spec, fam = by_slot[slot]
    assert kind == kind_exp
    rec, tr = B2.property_set_v2(ctx.value(slot), spec, kind=kind, elem_id=1_900_000 + slot % 997,
                                slot=slot, spec_key=spec["key"])
    assert tr.shape == shape_exp
    # byte-exact schema round trip
    rt = rec.roundtrip()
    assert rt[102]["clean"] and rt[102]["byte_exact"], rt[102]
    # the D1 / D2 laws hold on the OUTPUT
    assert tr.swapped_ints_in_output == 0
    assert all(tr.ascending.values()), tr.ascending
    assert tr.elementid_set_present is True
    # every OUR-overridden id was present in the slot's skeleton (never invented)
    skel = B2.skeleton_ids_of(rec.obj)
    for _key, pid in tr.ours:
        assert pid in skel


def test_property_set_v2_states_our_values_and_our_provenance(ctx, pairs_v2):
    """Concrete slot 174481: our physical constants + provenance land, the
    slot's machinery (schema token, class enum, wood-schema defaults) is
    reproduced."""
    slot = 174481
    kind, spec, fam = next((k, sp, f) for s, k, sp, f in pairs_v2 if s == slot)
    rec, tr = B2.property_set_v2(ctx.value(slot), spec, kind=kind, elem_id=1_900_500,
                                 slot=slot, spec_key=spec["key"])
    vals = {}
    ps = ((rec.obj.get("m_oParamSet") or {}).get("value") or {})
    for key in ("m_pDoubleParams", "m_pIntParams", "m_pAStringParams"):
        for x in (((ps.get(key) or {}).get("value") or {}).get("m_paramSet") or []):
            vals[x["m_paramId"]] = x["m_value"]
    # ours: Young's modulus (both blocks) = E_MPa x 1e6 x 0.3048; asset name; provenance
    E = float(spec["E_MPa"]) * 1e6 * B2.PA_TO_INTERNAL
    assert vals[-1140300] == pytest.approx(E) and vals[-1152301] == pytest.approx(E)
    assert vals[-1150466] == spec["name"]                     # our name
    assert vals[-1152340] == ""                                # no Autodesk source token
    assert vals[-1152337] == B2.HOUSE_ASSET_LIBRARY_GUID       # our library GUID
    # concrete compression stated (concrete family) from our f'c
    assert vals[-1140314] == pytest.approx(float(spec["fc_MPa"]) * 1e6 * B2.PA_TO_INTERNAL)
    # machinery reproduced: the slot's class enum + schema token + wood defaults
    parent = B2._asset_strings(ctx.value(slot))
    assert vals[-1150464] == 4                                 # StructuralAssetClass Concrete kept
    assert vals[-1152342] == parent[-1152342] == "structural:concrete"
    assert vals[-1140416] == "Douglas Fir (West)"              # wood-schema default (machinery)


def test_property_set_v2_states_each_quantity_ONCE_across_duplicate_ids(ctx, pairs_v2):
    """The leak-audit law: the modern shape carries E / nu / G / alpha at
    several ids each (the legacy primaries -1140300.. , the -1140xxx-range
    DUPLICATES -1140401 / -1140412 / -1140413 / -1140415, and the unified
    -1152301..-1152307 block).  Ours must state ONE value per quantity at
    ALL of them -- residue_b (BIP_PHY only) would have left the duplicates
    at the SAMPLE's value: two Young's moduli in one asset, and a leak."""
    for slot in (174481, 174586, 174580):                       # concrete / steel / wood, modern
        kind, spec, fam = next((k, sp, f) for s, k, sp, f in pairs_v2 if s == slot)
        rec, tr = B2.property_set_v2(ctx.value(slot), spec, kind=kind, elem_id=1_900_600 + slot % 991,
                                     slot=slot, spec_key=spec["key"])
        d = {}
        ps = ((rec.obj.get("m_oParamSet") or {}).get("value") or {})
        for x in (((ps.get("m_pDoubleParams") or {}).get("value") or {}).get("m_paramSet") or []):
            d[x["m_paramId"]] = x["m_value"]
        for grp in ((-1140300, -1140301, -1140302, -1140401, -1152301, -1152302),   # E
                    (-1140303, -1140304, -1140305, -1140412, -1152303, -1152304),   # nu
                    (-1140306, -1140307, -1140308, -1140413, -1152305),             # G
                    (-1140310, -1140311, -1140312, -1140415, -1152306, -1152307)):  # alpha
            present = [d[p] for p in grp if p in d]
            assert present, (slot, grp)
            assert max(present) == pytest.approx(min(present), rel=1e-9), (slot, grp, present)


def test_property_set_v2_thermal_states_our_thermophysical_constants(ctx, pairs_v2):
    slot = 174516                                              # thermal 'Concrete'
    kind, spec, fam = next((k, sp, f) for s, k, sp, f in pairs_v2 if s == slot)
    assert kind == "thermal" and fam == "concrete"
    rec, tr = B2.property_set_v2(ctx.value(slot), spec, kind=kind, elem_id=1_900_501,
                                 slot=slot, spec_key=spec["key"])
    vals = {}
    ps = ((rec.obj.get("m_oParamSet") or {}).get("value") or {})
    for key in ("m_pDoubleParams", "m_pIntParams", "m_pAStringParams"):
        for x in (((ps.get(key) or {}).get("value") or {}).get("m_paramSet") or []):
            vals[x["m_paramId"]] = x["m_value"]
    assert vals[-1152311] == pytest.approx(float(spec["k"]) * B2.K_TO_INTERNAL)       # conductivity
    assert vals[-1152312] == pytest.approx(float(spec["cp"]) * B2.CP_TO_INTERNAL)     # specific heat
    assert vals[-1152313] == pytest.approx(float(spec["rho"]) * B2.RHO_TO_INTERNAL)   # density
    assert vals[-1152340] == "" and vals[-1152337] == B2.HOUSE_ASSET_LIBRARY_GUID
    assert vals[-1150464] == 3                                                          # thermal Solid kept


# ---------------------------------------------------------------------------
# 4. the class-constrained role selection (correspondence law)
# ---------------------------------------------------------------------------

def test_v2_pairing_covers_all_28_slots_with_zero_family_mismatches(ctx, pairs_v2):
    assert len(pairs_v2) == 28
    equivalent = {("generic", "wood"), ("basic", "basic"), ("mineral", "mineral")}
    for slot, kind, spec, fam in pairs_v2:
        ours = B2.our_spec_family(spec, kind)
        assert fam == ours or (fam, ours) in equivalent, (slot, kind, fam, ours, spec["key"])


def test_asset_class_family_reads_the_authoritative_signals(ctx):
    """Concrete slots (StructuralAssetClass 4 / 'structural:concrete' token)
    classify as concrete -- the slots residue_b's picker mis-classed as
    metal via the 'cast' -> 'Cast-in-Place' referrer bug."""
    for slot in (174481, 600684, 1177773, 1407838):
        assert B2.asset_class_family(ctx.value(slot), "structural") == "concrete", slot
    assert B2.asset_class_family(ctx.value(174577), "structural") == "plastic"     # 'Plastic:structural'
    assert B2.asset_class_family(ctx.value(174580), "structural") == "wood"
    assert B2.asset_class_family(ctx.value(174509), "structural") == "basic"       # soil
    assert B2.asset_class_family(ctx.value(174586), "structural") == "metal"
    assert B2.asset_class_family(ctx.value(174578), "thermal") == "plastic"        # HDPE
    assert B2.asset_class_family(ctx.value(174516), "thermal") == "concrete"


def test_residue_b_role_picker_misclasses_concrete_as_metal(ctx, landed):
    """Pins the SECOND residue-B defect this stream found: its hint-based
    structural role lands steel on concrete / plastic slots (the referrer
    names are polluted by Y7's material substitution and 'cast' matches
    'Cast-in-Place')."""
    # reproduce residue_b's own selection through residue_b2's original-pairing helper
    orig = {slot: sp["key"] for slot, kind, sp in B2.propertyset_pairs(ctx, landed)}
    steel_on_concrete = [s for s in (174481, 600684, 1177773, 1407838)
                         if orig.get(s, "").startswith("steel")]
    assert steel_on_concrete, "residue_b's picker is expected to land steel on concrete slots"


# ---------------------------------------------------------------------------
# 5. materials: the certified constructor, reproduced pairing
# ---------------------------------------------------------------------------

def test_material_pairs_cover_the_10_surplus_slots(ctx, landed):
    mp = B2.material_pairs(ctx, landed)
    assert len(mp) == 10
    assert len({slot for slot, _ in mp}) == 10                      # distinct slots
    assert len({spec["key"] for _, spec in mp}) == 10               # distinct specs (no reuse)
    for slot, _spec in mp:
        assert ctx.cls_of.get(slot) == "MaterialElem"


def test_material_constructor_is_the_certified_y7_shape():
    """D3: our surplus materials are graphics-only (no appearance / property
    set links) -- exactly the shape Y7 certified on 13 slots."""
    rec = RB.extended_material(RB.EXTENDED_MATERIALS[0], elem_id=1_950_000)
    mat = (rec.obj.get("m_pMaterial") or {}).get("value") or {}
    assert mat.get("m_appearanceAssetId") == -1
    assert mat.get("m_structuralPropertySetId") == -1
    assert rec.obj.get("m_pParamValueSetAString") is None
    assert rec.obj.get("m_pParamValueSetDouble") is None
    rt = rec.roundtrip()
    assert rt["ok"]


# ---------------------------------------------------------------------------
# 6. the probe table + the built artefacts (when present)
# ---------------------------------------------------------------------------

def test_probe_table_and_predictions():
    names = [r.name for r in B2.PAL_PROBES]
    assert names == ["Z_palette_v2", "P_pal_mat", "P_pal_struct", "P_pal_thermal",
                     "P_pal_swapfix", "P_pal_struct_v2", "P_pal_thermal_v2"]
    for n in names:
        assert n in B2.PREDICTED_VERDICTS
    # the diagnostic bisection predicts the two ORIGINAL sub-classes FAIL
    assert B2.PREDICTED_VERDICTS["P_pal_struct"] == "FAIL"
    assert B2.PREDICTED_VERDICTS["P_pal_thermal"] == "FAIL"
    assert B2.PREDICTED_VERDICTS["P_pal_mat"] == "PASS"
    assert B2.PREDICTED_VERDICTS["Z_palette_v2"] == "PASS"


@pytest.mark.skipif(not os.path.exists(os.path.join(OUT, "probes.json")),
                    reason="probes not built (run: python -m rvt.genesis.residue_b2)")
def test_built_probes_are_valid_and_manifested():
    with open(os.path.join(OUT, "probes.json")) as fh:
        man = json.load(fh)
    probes = {p["probe"]: p for p in man["probes"]}
    assert set(probes) == {r.name for r in B2.PAL_PROBES}
    for name, p in probes.items():
        assert p["verdict"] == "VALID", (name, p.get("self_check"))
        assert p["validator"]["ok"] is True and p["validator"]["errors"] == 0
        bd = p["byte_delta"] or {}
        assert bd.get("assertion_holds") is True, name           # only the slots' records changed
        assert bd.get("elemtable_identical") and bd.get("adocument_identical")
        assert p["base"]["file"].endswith("subst_k4/Y9.rvt")
        assert p["control_to_upload_with_batch"]["file"].endswith("CTRL_Y9_base.rvt")
        assert p["predicted_verdict"]
    # the deliverable substitutes the whole bucket; the singles one sub-class each
    assert probes["Z_palette_v2"]["elements_substituted_in_place"]["landed"] == 38
    assert probes["P_pal_mat"]["elements_substituted_in_place"]["landed"] == 10
    assert probes["P_pal_struct"]["elements_substituted_in_place"]["landed"] == 17
    assert probes["P_pal_thermal"]["elements_substituted_in_place"]["landed"] == 11
    assert man["upload_order_bisection_first"][0] == "Z_palette_v2"


@pytest.mark.skipif(not os.path.exists(os.path.join(OUT, "Z_palette_v2.rvt")),
                    reason="Z_palette_v2.rvt not built")
def test_z_palette_v2_carries_no_D1_D2_violation():
    """The deliverable, checked from its BYTES: no swapped int, every param
    set ascending, every ElementId set present, on all 28 landed slots."""
    from rvt.mutate import Document
    doc = Document.from_file(os.path.join(OUT, "Z_palette_v2.rvt"))
    with open(os.path.join(OUT, "Z_palette_v2.json")) as fh:
        rep = json.load(fh)
    slots = [int(r["slot"]) for r in rep["landed_slots"] if r["class"] == "PropertySetElement"]
    assert len(slots) == 28
    for e in slots:
        v = doc.value(e)
        assert B2.swapped_int_entries(v) == [], e
        assert all(B2.param_ids_ascending(v).values()), e
        ps = ((v.get("m_oParamSet") or {}).get("value") or {})
        assert ps.get("m_pElementIdParams") is not None, e


@pytest.mark.skipif(not os.path.exists(os.path.join(OUT, "P_pal_swapfix.rvt")) or
                    not os.path.exists(ZB5), reason="swapfix probe / ZB5 not present")
def test_swapfix_equals_zb5_with_only_the_ints_unswapped():
    """The swap-ALONE isolate: P_pal_swapfix's property sets == ZB5's with
    ONLY the int keying corrected; its materials byte-identical to ZB5's."""
    from rvt.mutate import Document
    zb5 = Document.from_file(ZB5)
    sf = Document.from_file(os.path.join(OUT, "P_pal_swapfix.rvt"))
    with open(os.path.join(ROOT, "experiments/genesis/subst_k4/residue_b/ZB5_palette.json")) as fh:
        rep = json.load(fh)
    n_ps = n_mat = 0
    for row in rep["landed_slots"]:
        s, cls = int(row["slot"]), row["class"]
        if cls == "MaterialElem":
            assert bytes(zb5.record(s).payload) == bytes(sf.record(s).payload), s
            n_mat += 1
        else:
            a = json.loads(json.dumps(zb5.value(s)))
            B2.unswap_int_params(a)
            b = sf.value(s)
            assert json.dumps(a, sort_keys=True, default=str) == \
                json.dumps(b, sort_keys=True, default=str), s
            n_ps += 1
    assert (n_ps, n_mat) == (28, 10)
