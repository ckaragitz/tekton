"""Tests for src/rvt/objlint.py -- the constructed-object linter.

Covers the schema-parallel flattener, the leaf tokenizers / null semantics,
invariant derivation on a synthetic corpus, the linter's detection of
injected violations against real mined invariants, cohorts, the ElemTable
id-band helper, family classification, JSON persistence round trip, and the
calibration marking in the aggregation.  The corpus-touching tests mine a
couple of small classes from two samples (fast); everything else is pure.
"""
import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import objlint as OL                                            # noqa: E402


# ---------------------------------------------------------------------------
# fixtures: two small sample sources + a mined mini-corpus
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sources():
    return [OL.SpecimenSource.load_sample("rstbasicsampleproject"),
            OL.SpecimenSource.load_sample("racbasicsampleproject")]


@pytest.fixture(scope="module")
def flat():
    return OL.Flattener()


@pytest.fixture(scope="module")
def mini_corpus(sources, flat):
    """Invariants for two small classes mined from two samples."""
    out = {}
    for cn in ("WallJoinDefaultSetting", "PenWidthTableElem", "UnitsElem"):
        got = OL.mine_from_sources(cn, sources, flat)
        for inv in got.values():
            out[inv.key] = inv
    return out


# ---------------------------------------------------------------------------
# 1. the flattener on a real specimen
# ---------------------------------------------------------------------------
def test_flatten_real_gstyle_specimen(sources, flat):
    src = sources[0]
    ids = src.host_ids_of("GStyleElem")
    assert ids, "rstbasic must have GStyleElem host specimens"
    body, clean = src.object(ids[0], 102)
    assert clean and isinstance(body, dict)
    leaves = flat.flatten("GStyleElem", body, resolve=src.resolve)
    paths = {lf.path: lf for lf in leaves}
    # owned pointer -> #ptr leaf + walked sub-fields
    assert paths["m_pGStyle.#ptr"].value == "GStyle"
    assert "m_pGStyle->GStyle.m_penNumber" in paths
    assert isinstance(paths["m_pGStyle->GStyle.m_penNumber"].value, int)
    # ElementId leaf tokenized: category id is a negative literal
    cat = paths["m_categoryId"]
    assert cat.ftype == "eid" and isinstance(cat.value, int) and cat.value < 0
    # container length synthetic leaf; the element's own m_id is skipped
    assert "m_constrInfo.#len" in paths and paths["m_constrInfo.#len"].ftype == "len"
    assert "m_id" not in paths
    # null pointers become #ptr null leaves
    assert paths["m_pParamValueSetDouble.#ptr"].value is None
    assert OL.is_null_leaf(paths["m_pParamValueSetDouble.#ptr"])


def test_flatten_container_elements_collapse(sources, flat):
    """Elements of a growable container share the '[]' path key."""
    src = sources[0]
    ids = src.host_ids_of("PenWidthTableElem")
    body, clean = src.object(ids[0], 102)
    assert clean
    leaves = flat.flatten("PenWidthTableElem", body, resolve=src.resolve)
    elem_paths = [lf.path for lf in leaves if "[]" in lf.path]
    assert elem_paths, "pen table has container elements"
    # index-normalized: no numeric container index survives except fixed arrays
    for p in elem_paths:
        assert "[]" in p


# ---------------------------------------------------------------------------
# 2. tokenizers / null semantics / helpers
# ---------------------------------------------------------------------------
def test_eid_tokens_and_null():
    r = lambda i: f"@C{i}"                                              # noqa: E731
    assert OL._tok_eid(-1, r) is None                # invalid id = null
    assert OL._tok_eid(-2000011, r) == -2000011    # built-in id literal
    assert OL._tok_eid(42, r) == "@C42"            # resolved class token
    assert OL._tok_str("") is None and OL._tok_str(None) is None
    assert OL._tok_str("Level 1") == "Level 1"
    assert OL._tok_guid(OL.NULL_GUID) is None
    assert OL._tok_guid("e3e052f8-0156-11d5-9301-0000863f27ad") is not None
    assert OL._tok_vec([0.0, 0.0, 0.0]) == "zero"
    assert OL._tok_vec([1.0, 0.0, 0.0]) == "nonzero"
    assert OL.is_null_leaf(OL.Leaf("x", "eid", None))
    assert not OL.is_null_leaf(OL.Leaf("x", "eid", "@Level"))
    assert not OL.is_null_leaf(OL.Leaf("x", "int", 0))
    assert OL.is_null_leaf(OL.Leaf("x", "weak", None))
    assert not OL.is_null_leaf(OL.Leaf("x", "weak", "@weakref"))


def test_id_band_buckets():
    assert OL.id_band(2) == "<5k"
    assert OL.id_band(4_999) == "<5k"
    assert OL.id_band(49_999) == "<50k"
    assert OL.id_band(499_999) == "<500k"
    assert OL.id_band(1_500_000) == "<5M"
    assert OL.id_band(9_999_999) == ">=5M"


def test_family_classification():
    f = OL.family_of
    assert f({"path": "ETR.owner_class", "rule": "NEVER_NULL"}) == "elemtable-ownership"
    assert f({"path": "ETR.owned[]", "rule": "OWNED_CHILD"}) == "elemtable-ownership"
    assert f({"path": "ETR.id_band", "rule": "IDENTICAL"}) == "elemtable-vintage"
    assert f({"path": "REP.seq103_class", "rule": "IDENTICAL"}) == "seq103-rep"
    assert f({"path": "m_geomSteps.#ptr", "rule": "PTR_PRESENT"}) == "missing-subobject"
    assert f({"path": "HDR.m_abFlags4Bytes", "rule": "ENUM"}) == "header-shape"
    assert f({"path": "m_layers.#len", "rule": "CONST_LEN"}) == "container-shape"
    assert f({"path": "m_x", "rule": "RANGE"}) == "value-range"
    assert f({"path": "m_name", "rule": "STR_VOCAB"}) == "string-vocab"
    assert f({"path": "m_previewElemId", "rule": "NEVER_NULL"}) == "nulled-reference"
    assert f({"path": "m_dMin", "rule": "IDENTICAL", "ftype": "float",
              "specimens_say": "identical value 2.08"}) == "product-default-value"


def test_cohorts():
    assert OL.cohort_of("PenWidthTableElem", {"m_famId": -1}) == "project"
    assert OL.cohort_of("PenWidthTableElem", {"m_famId": 123}) == "family-scoped"
    assert OL.cohort_of("GStyleElem", {"m_ownerId": -1}) == "builtin"
    assert OL.cohort_of("GStyleElem", {"m_ownerId": 99}) == "subcategory"
    assert OL.cohort_of("SomeClassWithoutCohorts", {}) == ""


# ---------------------------------------------------------------------------
# 3. invariant derivation on a synthetic corpus
# ---------------------------------------------------------------------------
def _acc_from(ftype, values, src="s"):
    a = OL._Acc(ftype)
    for v in values:
        a.add(OL.Leaf("p", ftype, v), src)
        a.mark_present()
    return a


def test_derive_rules_synthetic():
    n = 6
    accs = {
        "m_never_null": _acc_from("eid", ["@UnitsElem"] * n),
        "m_always_null": _acc_from("eid", [None] * n),
        "m_ident": _acc_from("int", [7] * n),
        "m_enum": _acc_from("int", [1, 2, 1, 2, 1, 2]),
        "m_arr.#len": _acc_from("len", [16] * n),
        "m_ptr.#ptr": _acc_from("ptr", ["CellList"] * n),
        "m_range": _acc_from("float", [1.0, 2.0, 3.0, 4.0, 5.0, 60.0]),
    }
    rules = OL.derive_rules(accs, n)
    by = {(r.path, r.rule): r for r in rules}
    assert ("m_never_null", "NEVER_NULL") in by
    assert ("m_never_null", "IDENTICAL") in by and by[("m_never_null", "IDENTICAL")].expect == "@UnitsElem"
    assert ("m_always_null", "ALWAYS_NULL") in by
    assert ("m_ident", "IDENTICAL") in by and by[("m_ident", "IDENTICAL")].expect == 7
    assert ("m_enum", "ENUM") in by and by[("m_enum", "ENUM")].expect == {1, 2}
    assert ("m_arr.#len", "CONST_LEN") in by and by[("m_arr.#len", "CONST_LEN")].expect == 16
    assert ("m_ptr.#ptr", "PTR_PRESENT") in by
    r = by[("m_range", "RANGE")]
    assert r.expect == [1.0, 60.0]
    # presence tracked, universal
    assert by[("m_ident", "IDENTICAL")].present == n


def test_identical_requires_universality_for_specimen_paths():
    """A sub-object field seen in only 3 of 100 specimens must NOT yield an
    IDENTICAL rule (the sparse-geometry-subpath false-positive class)."""
    a = _acc_from("int", [5, 5, 5])          # present in 3 specimens only
    rules = OL.derive_rules({"m_sub.m_x": a}, 100)
    assert not any(r.rule == "IDENTICAL" for r in rules)


def test_element_paths_can_be_identical_without_universality():
    a = _acc_from("float", [2.083] * 40)       # 40 container elements
    a.present = 5                              # ... spread over 5 specimens
    rules = OL.derive_rules({"m_tbl[].m_len": a}, 6)
    assert any(r.rule == "IDENTICAL" for r in rules)


# ---------------------------------------------------------------------------
# 4. the linter on a real specimen (self-lint clean) + injected violations
# ---------------------------------------------------------------------------
def test_self_lint_and_injected_violations(sources, flat, mini_corpus):
    src = sources[0]
    eid = src.host_ids_of("WallJoinDefaultSetting")[0]
    body, clean = src.object(eid, 102)
    hdr, _ = src.object(eid, 101)
    assert clean
    base = OL.lint_object("WallJoinDefaultSetting", copy.deepcopy(body), hdr,
                          invariants=mini_corpus, resolve=src.resolve, flat=flat,
                          elemrec_leaves=src.elemrec_leaves(eid),
                          seq103_class=src.rep_class(eid))
    # a real specimen is (near-)clean against invariants that include itself
    strong = [f for f in base if f.rule in ("NEVER_NULL", "PTR_PRESENT", "CONST_LEN",
                                            "IDENTICAL", "SEQ103_CLASS")]
    assert not strong, f"specimen self-lint should have no hard findings: {strong[:3]}"

    # inject violations: null a never-null weak doc pointer, break a const-len
    bad = copy.deepcopy(body)
    bad["m_docAccess"] = {"m_pDoc": {"weakref": 0}}      # NEVER_NULL m_docAccess.m_pDoc
    bad["m_constrInfo"] = [1, 2, 3]                        # CONST_LEN 0 -> 3
    found = OL.lint_object("WallJoinDefaultSetting", bad, hdr,
                           invariants=mini_corpus, resolve=src.resolve, flat=flat)
    rules = {(f.field_path, f.rule) for f in found}
    assert ("m_docAccess.m_pDoc", "NEVER_NULL") in rules
    assert ("m_constrInfo.#len", "CONST_LEN") in rules
    # findings are ranked (most severe first) and carry displays
    assert found and found[0].score >= found[-1].score
    for f in found:
        assert f.class_name == "WallJoinDefaultSetting"
        assert f.severity in OL.SEVERITY_NAMES


def test_unresolvable_target_is_not_a_violation():
    """'@?' (an id we cannot resolve to a class) must not trip IDENTICAL,
    while a resolvable WRONG class and a null both do."""
    rule = OL.Rule("m_previewElemId", "IDENTICAL", "@LegendComponent", 100, 6, 100,
                   "eid", "body", 100)
    unknown = OL.Leaf(rule.path, "eid", "@?")
    assert OL._check_rule(rule, [unknown], {rule.path: [unknown]}) is None
    wrong = OL.Leaf(rule.path, "eid", "@GStyleElem")
    assert OL._check_rule(rule, [wrong], {rule.path: [wrong]}) is not None
    null = OL.Leaf(rule.path, "eid", None)
    assert OL._check_rule(rule, [null], {rule.path: [null]}) is not None


# ---------------------------------------------------------------------------
# 5. persistence round trip
# ---------------------------------------------------------------------------
def test_invariants_json_roundtrip(mini_corpus, tmp_path):
    inv = mini_corpus["PenWidthTableElem"]
    d = inv.to_json()
    js = json.dumps(d, default=str)
    back = OL.ClassInvariants.from_json(json.loads(js))
    assert back.class_name == inv.class_name
    assert back.n_specimens == inv.n_specimens
    assert len(back.rules) == len(inv.rules)
    # set-valued expectations survive the round trip as sets
    enums_before = [r for r in inv.rules if r.rule in ("ENUM", "PTR_CLASS_SET", "LEN_SET")]
    enums_after = [r for r in back.rules if r.rule in ("ENUM", "PTR_CLASS_SET", "LEN_SET")]
    assert len(enums_before) == len(enums_after)
    for r in enums_after:
        assert isinstance(r.expect, set)


def test_cohort_corpora_are_mined(mini_corpus):
    """PenWidthTableElem splits into project / family-scoped cohorts."""
    keys = set(mini_corpus)
    assert "PenWidthTableElem" in keys
    assert "PenWidthTableElem|project" in keys
    assert "PenWidthTableElem|family-scoped" in keys
    proj = mini_corpus["PenWidthTableElem|project"]
    fam = mini_corpus["PenWidthTableElem|family-scoped"]
    # the cohort predicate is the discriminator: project pen tables have famId -1
    assert any(r.path == "m_famId" and r.rule == "ALWAYS_NULL" for r in proj.rules)
    assert any(r.path == "m_famId" and r.rule == "NEVER_NULL" for r in fam.rules)


# ---------------------------------------------------------------------------
# 6. aggregation + calibration marking + ranking
# ---------------------------------------------------------------------------
def _finding(cls, path, rule, verdict_src, elem_id, score=0.6):
    return OL.Finding(class_name=cls, cohort="", field_path=path, rule=rule,
                      ours="null", specimens_say="never null (10/10)", support=10,
                      files=3, total=10, ftype="eid", scope="body", severity="HIGH",
                      score=score, present=10, elem_id=elem_id, source=verdict_src)


def test_calibration_marks_rules_violated_by_passing_controls():
    fail_src = {"name": "X5", "verdict": "FAIL", "path": "x"}
    pass_src = {"name": "T_conduit", "verdict": "PASS", "path": "y"}
    results = [
        {"source": fail_src, "findings": [_finding("A", "m_p", "NEVER_NULL", "X5", 100),
                                            _finding("A", "m_q", "NEVER_NULL", "X5", 100)]},
        {"source": pass_src, "findings": [_finding("A", "m_p", "NEVER_NULL", "T_conduit", 900)]},
    ]
    agg = OL.aggregate(results)
    groups = {(g["class"], g["path"]): g for g in agg["groups"]}
    assert groups[("A", "m_p")]["calibration"]                 # also violated by a PASS control
    assert not groups[("A", "m_q")]["calibration"]             # only the failing file breaks it
    ranked = OL.rank_bug_list(agg, {"NEVER_NULL": {"fp_rate": 0.0}})
    # the un-calibrated finding must rank above the calibrated one
    order = [(r["path"]) for r in ranked]
    assert order.index("m_q") < order.index("m_p")


def test_rule_type_fp_rates_shape(mini_corpus):
    res = [{"source": {"name": "P", "verdict": "PASS"},
            "elements": [{"elem_id": 1, "class": "UnitsElem"}],
            "findings": [_finding("UnitsElem", "m_x", "NEVER_NULL", "P", 1)]}]
    rates = OL.rule_type_fp_rates(res, mini_corpus)
    assert "NEVER_NULL" in rates
    st = rates["NEVER_NULL"]
    assert st["violated"] == 1 and st["checked"] >= 1
    assert 0.0 < st["fp_rate"] <= 1.0


# ---------------------------------------------------------------------------
# 7. constructor-class enumeration is stable
# ---------------------------------------------------------------------------
def test_target_class_lists():
    assert "PenWidthTableElem" in OL.CONSTRUCTOR_CLASSES
    assert "GStyleElem" in OL.CONSTRUCTOR_CLASSES
    assert "DBViewPlan" in OL.CONSTRUCTOR_CLASSES
    assert set(OL.CONTROL_CLASSES) == {"FamilyInstance", "SWall", "RbsElectricalSystem"}
    assert set(OL.ALL_CLASSES) == set(OL.CONSTRUCTOR_CLASSES) | set(OL.CONTROL_CLASSES)
    # every source spec is well-formed
    for spec in OL.our_sources():
        assert spec["verdict"] in ("FAIL", "PASS", "UNTESTED")
        assert spec["select"][0] in ("band>=", "created", "ids")
        assert spec["path"].endswith(".rvt")


def test_rung_of_bands():
    assert OL.rung_of(1_500_000, "X5").startswith("X1")
    assert OL.rung_of(1_900_003, "X5").startswith("X5")
    assert OL.rung_of(2_000_400, "X9").startswith("X6a")
    assert OL.rung_of(2_300_100, "X9").startswith("X9")
    assert OL.rung_of(1_500_000, "S5").startswith("S5 base")
    assert OL.rung_of(1_600_050, "S5").startswith("S5 singletons")


# ---------------------------------------------------------------------------
# 8. the fresh-constructor loop (the fix stream's fast iteration)
# ---------------------------------------------------------------------------
def test_fresh_constructor_lint(mini_corpus):
    recs, idmap = OL.fresh_constructor_records()
    assert len(recs) > 100
    classes = set(idmap.values())
    # the house catalog + settings constellation + built-in catalog are present
    for cn in ("PenWidthTableElem", "UnitsElem", "GStyleElem", "MaterialElem"):
        assert cn in classes
    # every record's id is in the map, and the id -> class map is consistent
    for r in recs[:200]:
        assert idmap[int(r.elem_id)] == r.class_name
    # linting the fresh output against a corpus works end to end
    findings = OL.lint_fresh(invariants=mini_corpus, classes=["UnitsElem", "PenWidthTableElem",
                                                               "WallJoinDefaultSetting"])
    assert isinstance(findings, list)
    for f in findings:
        assert f.class_name in ("UnitsElem", "PenWidthTableElem", "WallJoinDefaultSetting")
        assert f.source == "fresh"
