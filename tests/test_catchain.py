"""catchain tests: the famgen-chain residue overrides (catchain stream,
post-verdict-#41).  catprobe's category override + doc-level residue
recipes are proven on a real famgen panelboard product: donor shapes
reproduced (mined SUB_ALL/B7 laws), coherence surfaces (blank pair rows ==
current values, deletion prefix == authored non-element parents), byte
stability (record roundtrip), restoration of every runtime patch, and the
probe ladder's separator algebra (BX_conj flips all 12; each single flips
exactly its axis)."""
import copy
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import factory as F                     # noqa: E402
from rvt.famgen import catprobe as CP                   # noqa: E402
from rvt.famgen import skeleton as SK                   # noqa: E402
from rvt.famgen import loader as L                      # noqa: E402


def _tool(fname, alias):
    spec = importlib.util.spec_from_file_location(
        alias, os.path.join(ROOT, "tools", fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def base_doc():
    prod = F.make_panelboard(voltage="480Y/277", mains_a=225, spaces=42,
                             mcb=False, solid=True, start_id=5000)
    d = prod.doc
    if not d.finalized:
        d.finalize()
    return d


@pytest.fixture()
def doc(base_doc):
    return copy.deepcopy(base_doc)


# ---------------------------------------------------------------------------
# category_override
# ---------------------------------------------------------------------------

def test_category_override_births_gm_doc_and_restores():
    class Dummy:
        OST = -2001040
    with CP.category_override(SK.OST_GENERIC_MODEL, part_type=-1,
                              also=[(Dummy, "OST")]):
        prod = F.make_panelboard(voltage="480Y/277", mains_a=225, spaces=42,
                                 mcb=False, solid=True, start_id=5000)
        d = prod.doc
        assert d.category_id == SK.OST_GENERIC_MODEL
        assert d.part_type == -1
        assert d.self_family.obj["m_categoryId"] == SK.OST_GENERIC_MODEL
        assert d.self_family.obj["m_partType"] == -1
        assert Dummy.OST == SK.OST_GENERIC_MODEL
    # restored: a fresh product is electrical panelboard again
    assert Dummy.OST == -2001040
    prod2 = F.make_panelboard(voltage="480Y/277", mains_a=225, spaces=42,
                              mcb=False, solid=True, start_id=5000)
    assert prod2.doc.category_id == SK.OST_ELECTRICAL_EQUIPMENT
    assert prod2.doc.part_type == SK.PART_TYPE["panelboard"]
    assert SK.new_family_document.__name__ == "new_family_document"
    assert L.survey_host.__name__ == "survey_host"


def test_category_override_forces_host_survey():
    g_abpd = os.path.join(ROOT, "experiments", "genesis", "subst_k4",
                          "compose", "G_ABPD.rvt")
    if not os.path.isfile(g_abpd):                     # pragma: no cover
        pytest.skip("G_ABPD base not on disk")
    with CP.category_override(SK.OST_GENERIC_MODEL):
        host = L.survey_host(g_abpd)
    assert host.category == SK.OST_GENERIC_MODEL
    # the corpus-verified GM projection GStyle of the host resolves
    assert host.category_gstyle != -1


# ---------------------------------------------------------------------------
# the residue recipes (donor shapes, mined SUB_ALL/B7)
# ---------------------------------------------------------------------------

def test_types5_donor_table_shape(doc):
    CP.apply_residues(doc, types5=True)
    fam = doc.self_family
    ftt = fam.obj["m_pFamilyTypes"]["value"]
    names = [p["name"] for p in ftt["m_pairs"]]
    assert len(names) == 5
    assert names[0] == " "                       # the donor's blank pair
    assert len(set(names)) == 5                  # distinct names
    assert ftt["m_idx"] == 1
    # the blank pair duplicates the CURRENT values (the donor law)
    fp = fam.obj["m_familyParams"]["value"]["m_params"]
    assert ftt["m_pairs"][0]["params"]["m_params"] == fp
    assert ftt["m_pairs"][1]["params"]["m_params"] == fp
    # the variants differ from the base on the rating rows
    bus_id = doc.params["BusRating"].elem_id
    ratings = set()
    for p in ftt["m_pairs"][1:]:
        row = next(r for r in p["params"]["m_params"] if r["m_paramId"] == bus_id)
        ratings.add(row["m_value"])
    assert len(ratings) >= 3


def test_types5_refuses_double_application(doc):
    CP.apply_residues(doc, types5=True)
    with pytest.raises(ValueError, match="blank pair"):
        CP.apply_types5(doc)


def test_bip_locked_and_palette(doc):
    CP.apply_residues(doc, bip=True)
    fam = doc.self_family
    locked = fam.obj["m_lockedParameterIdsForDirectManipulation"]
    assert CP.BIP_COST_LOCKED in locked
    assert locked[0] == CP.BIP_COST_LOCKED       # sorts first, donor shape
    assert locked == sorted(locked)
    sp = CP._order_cell_groups(fam)
    ids = [pid for g in sp for pid in g["m_paramIds"]]
    assert CP.BIP_COST_LOCKED in ids
    # NO value row (the donor carries none)
    fp = fam.obj["m_familyParams"]["value"]["m_params"]
    assert not any(r["m_paramId"] == CP.BIP_COST_LOCKED for r in fp)


def test_materials_machinery(doc):
    CP.apply_residues(doc, materials=True)
    fam = doc.self_family
    fp = fam.obj["m_familyParams"]["value"]["m_params"]
    row = next(r for r in fp if r["m_paramId"] == CP.BIP_MATERIAL)
    assert row["m_instance"] is True and row["m_elemId"] == -1
    assert len(fp) == 18                          # donor row count
    sp = CP._order_cell_groups(fam)
    assert CP._group_key(sp[0]) == SK.PGROUP_MATERIALS   # materials FIRST
    assert sp[0]["m_paramIds"] == [CP.BIP_MATERIAL]
    # moved OUT of the identity palette finalize put it in
    others = [pid for g in sp[1:] for pid in g["m_paramIds"]]
    assert CP.BIP_MATERIAL not in others
    fsdos = fam.obj["m_fsdos"]
    assert len(fsdos) == 1 and fsdos[0]["ptr_class"] == "MaterialFSDO"
    v = fsdos[0]["value"]
    assert v["m_famParamId"] == CP.BIP_MATERIAL
    assert v["m_categoryId"] == fam.obj["m_categoryId"]
    # every type row carries the material value
    for p in fam.obj["m_pFamilyTypes"]["value"]["m_pairs"]:
        assert any(r["m_paramId"] == CP.BIP_MATERIAL
                   for r in p["params"]["m_params"])


def test_materials_group_wants_value_row_first(doc):
    with pytest.raises(ValueError, match="value"):
        CP.apply_materials_group(doc)


def test_counters_deletion_reftypeids(doc):
    CP.apply_residues(doc, bip=True, materials=True, sparse_counters=True,
                      deletion_prefix=True, ref_type_ids=True)
    fam = doc.self_family
    assert fam.obj["m_nextAbsorbedIndex"] == CP.DONOR_NEXT_ABSORBED
    assert fam.obj["m_predefinedLimitIdx"] == CP.DONOR_PREDEFINED_LIMIT
    assert fam.obj["m_refTypeIds"] == [4]
    dele = fam.header["m_parents"]["value"]["m_deletion"]
    # the prefix = the authored non-element parents, donor order
    assert dele[:3] == [fam.obj["m_categoryId"], CP.BIP_MATERIAL,
                        CP.BIP_COST_LOCKED]
    # element ids all still present after the prefix
    eids = {e.elem_id for e in doc.elements}
    assert eids <= set(dele)


def test_deletion_prefix_without_bip_or_materials(doc):
    CP.apply_residues(doc, deletion_prefix=True)
    dele = doc.self_family.header["m_parents"]["value"]["m_deletion"]
    assert dele[0] == doc.self_family.obj["m_categoryId"]
    assert CP.BIP_MATERIAL not in dele            # only what is authored
    assert CP.BIP_COST_LOCKED not in dele


def test_full_conjunction_flips_and_roundtrips(doc):
    CP.apply_residues(doc, types5=True, bip=True, materials=True,
                      dedup_cell=True, sparse_counters=True,
                      deletion_prefix=True, ref_type_ids=True)
    fam = doc.self_family
    sp = CP._order_cell_groups(fam)
    keys = [CP._group_key(g).rsplit(":", 1)[-1].split("-")[0] for g in sp]
    assert keys == ["materials", "dimensions", "identityData", "electrical"]
    assert len(keys) == len(set(keys))            # no dup keys (M3 fix)
    rt = doc.roundtrip()
    assert rt["failed"] == 0
    assert rt["roundtrip_ok"] == rt["records"]


def test_apply_residues_wants_finalized():
    prod = F.make_panelboard(voltage="480Y/277", mains_a=225, spaces=42,
                             mcb=False, solid=True, start_id=5000)
    d = prod.doc
    d.finalized = False
    with pytest.raises(ValueError, match="FINALIZED"):
        CP.apply_residues(d, types5=True)


# ---------------------------------------------------------------------------
# the probe ladder's separator algebra (tools/catchain.py)
# ---------------------------------------------------------------------------

def test_ladder_separator_vectors():
    CT = _tool("catchain.py", "_test_catchain")
    conj = CT.expected_separators("BX_conj")
    assert set(conj) == set(CT.SEP12)
    assert not any(conj.values())                 # all 12 flipped
    cat = CT.expected_separators("BX_cat_gm")
    assert [c for c, keep in cat.items() if not keep] == sorted(
        ["sf_category_is_ours_electrical", "sf_partType_set (not -1)"])
    t5 = CT.expected_separators("BX_types_5")
    assert [c for c, keep in t5.items() if not keep] == sorted(
        ["sf_single_type_pair", "sf_type_idx_zero"])
    bip = CT.expected_separators("BX_bip")
    assert [c for c, keep in bip.items() if not keep] == ["sf_locked_no_bip"]
    m_cat = CT.expected_separators("BX_conj_minus_cat")
    assert [c for c, keep in m_cat.items() if keep] == sorted(
        ["sf_category_is_ours_electrical", "sf_partType_set (not -1)"])
    m_t5 = CT.expected_separators("BX_conj_minus_types")
    assert [c for c, keep in m_t5.items() if keep] == sorted(
        ["sf_single_type_pair", "sf_type_idx_zero"])


# ---------------------------------------------------------------------------
# the emitted probes (when built): feature vectors match the recipes
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.isfile(os.path.join(ROOT, "experiments", "catchain",
                                    "BX_conj.rvt")),
    reason="chain probes not built (tools/catchain.py build)")
def test_emitted_probes_carry_intended_features():
    CT = _tool("catchain.py", "_test_catchain_emitted")
    LD = CT._ld()
    from rvt.frontdoor import standalone as SA
    SA.install_schema(CT.G_ABPD)
    for name in CT.LADDER:
        p = os.path.join(CT.OUT_DIR, f"{name}.rvt")
        if not os.path.isfile(p):
            continue
        u = LD.UnitX(p)
        feats = LD.unit_features(u)
        want = CT.expected_separators(name)
        got = {c: bool(LD.CANDIDATES[c](feats)) for c in CT.SEP12}
        assert got == want, f"{name}: separator vector drifted"
