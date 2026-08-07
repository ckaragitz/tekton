"""birthright stream tests -- the v2 AUTHOR lanes + the miner's adoption
line (tools/birthright_mine.py + rvt.famgen.birthright v2).

Three layers, no viewer and no heavy builds:

1. the author-lane pure contracts (materialize / roles / block / types /
   topology / fields / indices / verify) on toy documents;
2. the miner's adoption-line helpers (stem extraction, classref rule);
3. spec-level invariants of the REAL mined ``experiments/birthright/
   template_birth.json`` (skipped when the spec has not been mined):
   ZERO donor identity leakage, closure soundness, roster arithmetic.
"""
import json
import os
import re
import sys
import importlib.util

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

SPEC_PATH = os.path.join(ROOT, "experiments", "birthright",
                         "template_birth.json")


def _bm():
    spec = importlib.util.spec_from_file_location(
        "_test_birthright_mine", os.path.join(ROOT, "tools",
                                              "birthright_mine.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# toy documents (the same duck shape test_rft_probe uses)
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
    def __init__(self, els, sf):
        self.elements = els
        self.self_family = sf
        self.family_guid = "11111111-2222-3333-4444-555555555555"
        self.types = [("225A", {})]
        self.current_type = 0
        self.finalized = True


def _toy_doc():
    sf = _El(100, "Family",
             obj={"m_partType": 14,
                  "m_bIsSavable": True,
                  "m_familyIds": {"ptr_class": "ElementIdIndexPairSet",
                                  "value": {"m_data": [
                                      {"m_elementId": 101, "m_index": 0},
                                      {"m_elementId": 102, "m_index": 1}]}},
                  "m_nextAbsorbedIndex": 2},
             header={"m_abFlags4Bytes": 26,
                     "m_parents": {"ptr_class": "ElementParents",
                                   "value": {"m_deletion": [101, 102,
                                                            100]}}})
    units = _El(101, "UnitsElem", obj={"m_formats": []})
    lvl = _El(102, "Level", obj={"m_name": "Ref. Level"})
    return _Doc([sf, units, lvl], sf)


def _v2_spec(tmp_path, **over):
    data = {
        "version": 2,
        "source": {"rfa": "x.rfa", "sha256": "0" * 64},
        "famdoc": {"n_records": 5, "self_family_id": 17,
                   "category_id": -2000080, "part_type": 0,
                   "class_histogram": {"Family": 1, "UnitsElem": 1,
                                       "GStyleElem": 2, "CategoryElem": 1},
                   "self_family_fields": {"m_bIsSavable": False},
                   "self_family_header": {"m_abFlags4Bytes": 26}},
        "type_table": {"n_pairs": 4, "m_idx": 2,
                       "names": [" ", "a", "b", "c"],
                       "blank_pair_first": True},
        "separators_born": {"sf_partType": 0},
        "topology": {"self_family_owned_ours_top": ["UnitsElem", "Level"]},
        "field_policy": {"deletion_prefix": [-1154647, -1001205]},
        "birth_elements": [
            {"born_id": 40, "class": "CategoryElem", "owner": "self_family",
             "absorbed_index": 7,
             "header": {"m_abFlags4Bytes": 3},
             "obj": {"m_id": {"__eid__": 40},
                     "m_famId": {"__role__": "self_family"},
                     "m_gstyleIds": [{"__eid__": 41}],
                     "m_name": "Hidden Lines"},
             "rep": None},
            {"born_id": 41, "class": "GStyleElem",
             "owner": {"__eid__": 40}, "absorbed_index": 9,
             "header": {"m_abFlags4Bytes": 3},
             "obj": {"m_id": {"__eid__": 41},
                     "m_categoryId": {"__eid__": 40},
                     "m_guid": {"__author__": {"kind": "guid"}},
                     "m_label": {"__author__": {
                         "kind": "string", "shape_len": 30,
                         "shape_stem": "SecretInternalStyle"}},
                     "m_pen": 3},
             "rep": None},
        ],
    }
    data.update(over)
    p = tmp_path / "template_birth.json"
    p.write_text(json.dumps(data))
    return str(p)


# ===========================================================================
# 1. author-lane contracts
# ===========================================================================

class TestAuthorLanes:
    def test_v2_spec_parses(self, tmp_path):
        from rvt.famgen import birthright as BR
        s = BR.read_birth_spec(_v2_spec(tmp_path))
        assert s.version == 2
        assert len(s.birth_elements) == 2
        assert s.type_table["blank_pair_first"] is True
        assert s.topology["self_family_owned_ours_top"] == ["UnitsElem",
                                                            "Level"]

    def test_apply_v2_full_pipeline(self, tmp_path):
        from rvt.famgen import birthright as BR
        s = BR.read_birth_spec(_v2_spec(tmp_path))
        doc = _toy_doc()
        rep = BR.apply_birthright(doc, s)
        idmap = rep.pop("_idmap")
        # roster: both elements appended, ids above our block, refs remapped
        assert rep["roster"]["n_added"] == 2
        cat = next(e for e in doc.elements
                   if e.class_name == "CategoryElem")
        gs = next(e for e in doc.elements if e.class_name == "GStyleElem")
        assert cat.elem_id == idmap[40] and gs.elem_id == idmap[41]
        assert cat.obj["m_id"] == cat.elem_id            # self-ref remapped
        assert cat.obj["m_famId"] == 100                 # role -> our sf
        assert cat.obj["m_gstyleIds"] == [gs.elem_id]
        assert gs.obj["m_categoryId"] == cat.elem_id
        assert gs.owner_id == cat.elem_id                # eid owner
        assert cat.owner_id == 100                       # role owner
        # identity authored, never the specimen's
        assert re.match(r"^[0-9a-f-]{36}$", gs.obj["m_guid"])
        assert gs.obj["m_label"].startswith("SecretInternalStyle")
        # topology: our top-level UnitsElem/Level now self-Family-owned
        assert all(e.owner_id == 100 for e in doc.elements
                   if e.class_name in ("UnitsElem", "Level"))
        # types: blank pair first, current -> the real type
        assert doc.types[0][0] == " " and doc.current_type == 1
        # fields: born residue adopted
        assert doc.self_family.obj["m_bIsSavable"] is False
        # deletion prefix prepended in born order
        dele = doc.self_family.header["m_parents"]["value"]["m_deletion"]
        assert dele[:2] == [-1154647, -1001205]
        # absorbed indices: the toy doc has no finalize(), so the index
        # lane rewrites the EXISTING pairs (membership completion is
        # FamilyDoc.finalize's job, proven on the real chain): our
        # elements continue ABOVE the born maximum (9), next = max + 1
        pairs = {p["m_elementId"]: p["m_index"] for p in
                 doc.self_family.obj["m_familyIds"]["value"]["m_data"]}
        assert sorted(pairs.values()) == [10, 11]
        assert doc.self_family.obj["m_nextAbsorbedIndex"] == 12

    def test_verify_clean_and_catches_drift(self, tmp_path):
        from rvt.famgen import birthright as BR
        s = BR.read_birth_spec(_v2_spec(tmp_path))
        doc = _toy_doc()
        rep = BR.apply_birthright(doc, s)
        idmap = rep.pop("_idmap")
        ver = BR.birth_verify(doc, s, idmap, rep["roles"])
        assert ver["ok"], ver["mismatches"][:3]
        assert ver["counts"]["authored"] == 2
        assert ver["counts"]["refs_remapped"] >= 4
        # now corrupt one adopted law -> the diff must catch it
        gs = next(e for e in doc.elements if e.class_name == "GStyleElem")
        gs.obj["m_pen"] = 999
        ver2 = BR.birth_verify(doc, s, idmap, rep["roles"])
        assert not ver2["ok"]
        assert any(m["path"].endswith(".m_pen") for m in ver2["mismatches"])

    def test_materialize_refuses_outside_ref(self, tmp_path):
        from rvt.famgen import birthright as BR
        with pytest.raises(ValueError, match="outside the authored birth"):
            BR.materialize({"__eid__": 999}, {40: 1}, {}, BR._Author("s"))

    def test_author_deterministic_within_seed(self):
        from rvt.famgen.birthright import _Author
        a1, a2 = _Author("seed"), _Author("seed")
        g1 = a1.value({"kind": "guid"}, context="x")
        g2 = a2.value({"kind": "guid"}, context="x")
        assert g1 == g2
        assert _Author("other").value({"kind": "guid"}, context="x") != g1

    def test_v1_spec_still_routes_to_v1(self, tmp_path):
        from rvt.famgen import birthright as BR
        p = tmp_path / "v1.json"
        p.write_text(json.dumps({
            "version": 1,
            "famdoc": {"class_histogram": {"Family": 1},
                       "self_family_fields": {"m_partType": 14}}}))
        s = BR.read_birth_spec(str(p))
        doc = _toy_doc()
        rep = BR.apply_birthright(doc, s, lanes=("fields",))
        assert rep.get("version") != 2          # the v1 report shape
        assert "fields_set" in rep

    def test_types_lane_idempotent(self, tmp_path):
        from rvt.famgen import birthright as BR
        s = BR.read_birth_spec(_v2_spec(tmp_path))
        doc = _toy_doc()
        r1 = BR.apply_birth_types(doc, s)
        r2 = BR.apply_birth_types(doc, s)
        assert r1["applied"] and not r2["applied"]
        assert [n for n, _ in doc.types].count(" ") == 1


# ===========================================================================
# 2. the miner's adoption line
# ===========================================================================

class TestAdoptionLine:
    def test_name_stem(self):
        bm = _bm()
        assert bm._name_stem("SecretInternalLinAngDimStyle5p47") == \
            "SecretInternalLinAngDimStyle"
        assert bm._name_stem("Site Preparation Costs Etc") is None
        assert bm._name_stem(r"C:\Users\someone\file") is None
        assert bm._name_stem("short1") is None

    def test_classref_strings_always_adopt(self):
        bm = _bm()
        census = {}
        out = bm._adopt_filter(
            {"ptr_class": "RvtLinkInstanceAppearanceParentElem",
             "classref": "CoordinateSystemDisplayElem"}, census)
        assert out["ptr_class"] == "RvtLinkInstanceAppearanceParentElem"
        assert out["classref"] == "CoordinateSystemDisplayElem"

    def test_schema_class_names_adopt(self):
        bm = _bm()
        census = {}
        out = bm._adopt_filter({"m_name": "ALongClassNameOverTwentyFour"},
                               census,
                               class_names={"ALongClassNameOverTwentyFour"})
        assert out["m_name"] == "ALongClassNameOverTwentyFour"

    def test_identity_never_carried(self):
        bm = _bm()
        census = {}
        out = bm._adopt_filter(
            {"m_guid": "e2fe4920-1111-2222-3333-444455556666",
             "m_path": "C:\\Users\\someone\\OneDrive - Autodesk\\f.txt",
             "m_pen": 3}, census)
        assert out["m_guid"] == {"__author__": {"kind": "guid"}}
        assert out["m_path"]["__author__"]["kind"] == "string"
        assert "shape_stem" not in out["m_path"]["__author__"]
        assert out["m_pen"] == 3

    def test_forge_vocabulary_adopts(self):
        bm = _bm()
        out = bm._adopt_filter(
            {"t": "autodesk.parameter.group:identityData-1.0.0"}, {})
        assert out["t"].startswith("autodesk.")


# ===========================================================================
# 3. invariants of the REAL mined spec (skipped until `mine` has run)
# ===========================================================================

needs_spec = pytest.mark.skipif(not os.path.isfile(SPEC_PATH),
                                reason="template_birth.json not mined")


@needs_spec
class TestMinedSpec:
    @pytest.fixture(scope="class")
    def spec(self):
        with open(SPEC_PATH) as fh:
            return json.load(fh)

    def test_zero_donor_identity_leakage(self, spec):
        blob = json.dumps(spec["birth_elements"]) + json.dumps(
            spec["famdoc"]["self_family_fields"])
        # no user paths, no employee names, no OneDrive
        for needle in ("hansonje", "OneDrive", "C:\\\\Users", "Autodesk\\\\"):
            assert needle not in blob, needle
        # the specimen's secret-style TOKENS never ride; only the naming
        # STEM (product vocabulary) may appear, and only inside an
        # __author__ shape_stem slot
        stems = []

        def walk(node):
            if isinstance(node, dict):
                a = node.get("__author__")
                if isinstance(a, dict) and len(node) == 1:
                    if a.get("shape_stem"):
                        stems.append(a["shape_stem"])
                    return
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        for e in spec["birth_elements"]:
            walk(e)
        n_secret_total = blob.count("SecretInternal")
        n_secret_stem = sum(1 for s in stems if "SecretInternal" in s)
        assert n_secret_total == n_secret_stem
        assert all(not any(c.isdigit() for c in s) for s in stems)

    def test_no_guid_values_carried(self, spec):
        # every GUID-shaped string in the spec must be an AUTHOR slot,
        # never a carried value (source.sha256 lives outside famdoc)
        blob = json.dumps(spec["birth_elements"])
        assert not re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", blob)

    def test_closure_sound(self, spec):
        ids = {e["born_id"] for e in spec["birth_elements"]}

        def refs(node, out):
            if isinstance(node, dict):
                if set(node) == {"__eid__"}:
                    out.append(node["__eid__"])
                    return
                for v in node.values():
                    refs(v, out)
            elif isinstance(node, list):
                for v in node:
                    refs(v, out)

        for e in spec["birth_elements"]:
            out = []
            refs(e["header"], out)
            refs(e["obj"], out)
            refs(e["rep"], out)
            assert all(r in ids for r in out), (e["class"], e["born_id"])

    def test_partition_arithmetic(self, spec):
        part = spec["birth_partition"]
        assert part["n_birth"] == len(spec["birth_elements"])
        assert part["n_candidates"] == part["n_birth"] + part["n_dropped"]
        # birth classes are disjoint from the classes famgen authors
        ours = set(part["our_classes"])
        assert not ours & {e["class"] for e in spec["birth_elements"]}

    def test_blank_pair_table_and_separators(self, spec):
        tt = spec["type_table"]
        assert tt["blank_pair_first"] and tt["names"][0] == " "
        sep = spec["separators_born"]
        assert sep["sf_partType"] == 0                  # furniture specimen
        assert sep["sf_familyIds"]["next_equals_max_plus_1"]

    def test_topology_names_units_and_view_chain(self, spec):
        flips = spec["topology"]["self_family_owned_ours_top"]
        assert "UnitsElem" in flips and "DBViewProject" in flips

    def test_absorbed_indices_present_and_unique(self, spec):
        idxs = [e["absorbed_index"] for e in spec["birth_elements"]]
        assert all(isinstance(i, int) for i in idxs)
        assert len(set(idxs)) == len(idxs)
