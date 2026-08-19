"""#692 slice 1 -- the MEP taxonomy and vendor directory are TABLES that stay honest.

Pinned as mechanisms, not as content counts (adding a kind or a maker is adding a row):

* the two gates are clean on the real tables, and FIRE on deliberately broken rows;
* a row's category is cross-checked against the ids Revit-written files show
  (``rvt.inventory``): a conflicting row never claims placeability, and lights up by itself
  when the resolver is corrected (#516);
* catalog rows are exactly the famspec lane's kinds and each has a held record whose worth
  (fact-tier or search-summary ``assumed``) is computed from the catalog's provenance report;
* archetype rows degrade while ``rvt.famgen.archetypes`` (#674) is absent and light up with it;
* neither row type can carry a number (the #685 line: names yes, member data no);
* the ``make_family.py taxonomy|vendors`` verbs and their ``--check`` gates run.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import types
import typing

import pytest

from rvt import inventory
from rvt.famgen import catalog, skeleton, standards, taxonomy as TX, vendors as V
from rvt.frontdoor import famspec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE_FAMILY = os.path.join(ROOT, "tools", "make_family.py")


@pytest.fixture(scope="module")
def make_family():
    spec = importlib.util.spec_from_file_location("make_family", MAKE_FAMILY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_registry(monkeypatch, categories):
    """A #674-shaped registry: key -> object with a ``category``."""
    fake = types.ModuleType("rvt.famgen.archetypes")
    fake.ARCHETYPES = {k: types.SimpleNamespace(key=k, category=c) for k, c in categories.items()}
    monkeypatch.setitem(sys.modules, "rvt.famgen.archetypes", fake)


# --------------------------------------------------------------------------- the gates

def test_both_gates_are_clean_on_the_real_tables():
    assert TX.check() == []
    assert V.check() == []


@pytest.mark.parametrize("row, needle", [
    (TX._k("x", "X", "astrology", "electrical_equipment"), "discipline"),
    (TX._k("x", "X", "electrical", "no_such_category"), "does not resolve"),
    (TX._k("x", "X", "electrical", None), "neither a category key nor a pending"),
    (TX._k("x", "X", "electrical", None, ["famspec:panelboard"], pending="Nowhere"), "pending row"),
    (TX._k("x", "X", "electrical", "electrical_equipment", ["famspec:switchgear"]), "not in"),
    (TX._k("x", "X", "electrical", "electrical_equipment", ["famspec:device"]), "needs sub-kind"),
    (TX._k("x", "X", "electrical", "electrical_equipment", ["famspec:panelboard/extra"]), "takes no"),
    (TX._k("x", "X", "electrical", "electrical_fixture", ["famspec:device/teleporter"]), "sub-kind"),
    (TX._k("x", "X", "lighting", "lighting_fixture", ["famspec:luminaire/no-such-fixture"]), "sub-kind"),
    (TX._k("x", "X", "electrical", "electrical_equipment", ["famspec:transformer"]), "no catalog record"),
    (TX._k("x", "X", "electrical", "electrical_equipment", ["house:rvt.nowhere:fn"]), "not on this build"),
    (TX._k("x", "X", "electrical", "electrical_equipment", ["teleport:now"]), "malformed"),
])
def test_taxonomy_gate_fires_on_a_broken_row(row, needle):
    problems = TX.check_row(row)
    assert any(needle in p for p in problems), problems


def test_taxonomy_gate_checks_archetype_keys_once_the_registry_exists(monkeypatch):
    row = TX._k("x", "X", "electrical", "electrical_equipment", ["archetype:hoverboard"])
    monkeypatch.setitem(sys.modules, "rvt.famgen.archetypes", None)
    assert TX.check_row(row) == []                                   # absent registry: #674, not a lie
    _fake_registry(monkeypatch, {"wireway": "electrical_equipment"})
    assert any("not in the registry" in p for p in TX.check_row(row))
    _fake_registry(monkeypatch, {"hoverboard": "generic_model"})     # key exists, wrong category
    assert any("builds category" in p for p in TX.check_row(row))


def test_vendor_gate_fires_on_a_broken_line():
    v = V.get("eaton")
    assert any("not a taxonomy row" in p
               for p in V.check_line(v, V._L("l", "L", ["no_such_kind"])))
    assert any("does not load" in p
               for p in V.check_line(v, V._L("no-such-record", "L", ["panelboard"], record=True)))
    # a real record claimed for a kind that does not build through its category
    assert any("record category" in p
               for p in V.check_line(v, V._L("pow-r-line-panelboards", "L", ["chiller"], record=True)))
    assert any("filed under" in p                                    # OST_ElectricalEquipment vs a fixture
               for p in V.check_line(v, V._L("pow-r-line-panelboards", "L", ["receptacle"], record=True)))


def test_alias_index_reports_a_clash():
    rows = (TX._k("a", "Alpha", "electrical", "panelboard", aliases=("shared name",)),
            TX._k("b", "Beta", "electrical", "panelboard", aliases=("Shared-Name",)))
    _index, clashes = TX._alias_index(rows, TX._names)
    assert clashes and "'a'" in clashes[0] and "'b'" in clashes[0]


# --------------------------------------------------------------------------- categories

def test_every_keyed_row_resolves_and_has_a_standards_table():
    for row in TX.kinds():
        if row.category is None:
            assert row.pending and not row.via and row.lane == "none", row.key
            continue
        assert skeleton._resolve_category(row.category) < 0, row.key
        assert standards.canonical_category(row.category) in standards.CATEGORY_STANDARDS, row.key
        assert row.revit_category == TX.INTENDED_LABEL[row.category]


def test_category_status_follows_the_verified_evidence(monkeypatch):
    row = TX.get("panelboard")
    assert TX.category_status(row)[0] == "confirmed"
    cid = skeleton._resolve_category(row.category)
    # a Revit-written file that showed this id under another name would make the row a conflict
    monkeypatch.setitem(inventory.BUILTIN_CATEGORIES_VERIFIED, cid, ("OST_X", "Something Else"))
    status, detail = TX.category_status(row)
    assert status == "conflict" and TX.RESOLVER_ISSUE in detail
    ok, why = TX.builder_available(row)
    assert not ok and why == detail                    # a conflicting row never claims to build


def test_an_inferred_id_is_caveated_whether_or_not_the_kind_builds():
    for row in TX.kinds():
        if TX.category_status(row)[0] == "inferred":
            assert "[category id inferred:" in TX.describe(row.key)["line"], row.key


def test_conflict_and_pending_rows_are_never_available():
    t = TX.table()
    blocked = set(t["by_category_status"]["conflict"]) | set(t["by_category_status"]["pending"])
    assert blocked and not (blocked & set(t["available"]))
    for key in t["by_category_status"]["pending"]:
        assert TX.describe(key)["line"].count("NOT buildable here") == 1


# --------------------------------------------------------------------------- lanes

def test_catalog_rows_are_exactly_what_the_famspec_lane_builds():
    cat_rows = [r for r in TX.kinds() if r.lane == "catalog"]
    fams = {TX._mech(m)[1].partition("/")[0] for r in cat_rows for m in r.via if m.startswith("famspec:")}
    assert fams == set(famspec.CATALOG_KINDS)
    for row in cat_rows:
        ok, why = TX.builder_available(row, strict=True)
        assert ok, (row.key, why)
        tier, records, n_fact, model = TX.facts_tier(row.key)
        assert records and tier in ("fact", "assumed") and (tier == "fact") == (n_fact > 0)
        # counted on the MEMBER: the variant a device sub-kind selects, else the whole record
        flags = [f for v, ln in records for x in catalog.load_line(v, ln)["variants"]
                 if model in (None, x["model"]) for f in x["field_provenance"].values()]
        assert flags and n_fact == flags.count("fact"), row.key


def test_a_device_member_with_no_fact_field_is_not_called_fact():
    """The generic device record holds its 4 fact fields on the 4-in box; the receptacle
    variants hold none -- the tier follows the member, not the line."""
    per_model = {x["model"]: list(x["field_provenance"].values()).count("fact")
                 for x in catalog.load_line("generic", "devices-and-mounting")["variants"]}
    for row in (r for r in TX.kinds() if any(m.startswith("famspec:device/") for m in r.via)):
        tier, _recs, n_fact, model = TX.facts_tier(row.key)
        assert model in per_model and n_fact == per_model[model], row.key
        assert (tier == "fact") == (per_model[model] > 0), row.key


def test_lane_none_row_says_which_lane_is_missing():
    row = next(r for r in TX.kinds() if r.lane == "none" and TX.category_status(r)[0] == "confirmed")
    d = TX.describe(row.key)
    assert d["available"] is False and "no lane builds it yet" in d["line"]
    assert row.revit_category in d["line"]


def test_archetype_rows_degrade_without_the_registry_and_light_up_with_it(monkeypatch):
    arch = {TX._mech(m)[1]: r for r in TX.kinds() for m in r.via if m.startswith("archetype:")}
    only = {k: r for k, r in arch.items()
            if r.lane == "archetype" and TX.category_status(r)[0] != "conflict"}
    assert arch and only
    monkeypatch.setitem(sys.modules, "rvt.famgen.archetypes", None)      # import -> ImportError
    assert TX.archetype_registry() is None
    for key, row in only.items():
        ok, why = TX.builder_available(row)
        assert not ok and "#674" in why, (key, why)
    assert TX.check() == []                                               # absence is not a lie
    _fake_registry(monkeypatch, {k: r.category for k, r in arch.items()})
    assert set(TX.archetype_registry()) == set(arch)
    for key, row in only.items():
        ok, why = TX.builder_available(row)
        assert ok and "archetype lane" in why, (key, why)
    for key, row in arch.items():                                         # conflicts stay blocked
        if TX.category_status(row)[0] == "conflict":
            assert TX.builder_available(row)[0] is False


def test_the_house_switchboard_states_its_tier_honestly():
    d = TX.describe("MSB")
    assert d["key"] == "switchboard" and d["lane"] == "archetype" and d["available"]
    assert "no manufacturer member" in d["line"] and "given" in d["line"]


@pytest.mark.parametrize("text, key", [
    ("MSB", "switchboard"), ("xfmr", "transformer_dry"), ("Dry-Type Transformer", "transformer_dry"),
    ("J-Box", "junction_box"), ("2x4 troffer", "troffer"), ("RTU", "rooftop_unit"),
    ("5-20R", "receptacle_20a"), ("diffuser", "air_terminal"), ("FACP", "fire_alarm_control_panel"),
])
def test_resolve_folds_case_space_and_hyphen(text, key):
    assert TX.resolve(text).key == key


def test_unknown_text_says_so():
    d = TX.describe("flux capacitor")
    assert d["known"] is False and "not a kind" in d["line"]


def test_the_prompt_grammar_kinds_resolve():
    """The kinds today's prompt grammar emits must land on a row (slice 2 dispatches by it)."""
    from rvt.frontdoor import prompt_intent as PI
    emitted = {k for k, *_ in PI._KIND_PATTERNS}
    unresolved = {k for k in emitted if TX.resolve(k) is None}
    assert unresolved <= {"luminaire"}, unresolved      # 'luminaire' is a family, not a kind


# --------------------------------------------------------------------------- vendors

def test_every_catalog_line_is_claimed_exactly_once_and_loads():
    claimed = [(v.key, ln.key) for v in V.vendors() for ln in v.lines if ln.record]
    assert sorted(claimed) == sorted(catalog.list_lines()) and len(claimed) == len(set(claimed))
    for vendor, line in claimed:
        data = catalog.load_line(vendor, line)
        assert (data["vendor"], data["line"]) == (vendor, line)
        assert V.record_tier(vendor, line)["tier"] in ("fact", "assumed")


def test_lines_for_kind_puts_records_first_and_names_the_rest():
    for row in TX.kinds():
        flags = [ln.record for _, ln in V.lines_for_kind(row.key)]
        assert flags == sorted(flags, reverse=True), row.key
    held = {v for v, _ in V.records_for_kind("panelboard")}
    assert held == {v for v, ln in catalog.list_lines() if catalog.load_line(v, ln)["category"] == "panelboard"}
    named_only = next(v for v in V.vendors() if not any(ln.record for ln in v.lines))
    d = V.describe(named_only.name)
    assert d["known"] and d["records"] == [] and "no member data is held" in d["line"]
    assert V.describe("acme corp")["known"] is False


def test_a_named_only_line_never_claims_what_the_taxonomy_cannot_build():
    """The vendor line is computed from the kind's availability (review of #735)."""
    for v in V.vendors():
        for ln in v.lines:
            if ln.record:
                continue
            for k in ln.kinds:
                ok, why = TX.builder_available(TX.get(k))
                line = V.describe(v.key, kind=k)["line"]
                assert why in line, (v.key, k)
                if not ok:
                    assert "not buildable here yet" in line and "generated" not in line, (v.key, k)
                elif TX.get(k).lane == "catalog":
                    assert f"never presented as a {v.name} product" in line, (v.key, k)


def test_an_assumed_only_record_is_reported_as_such():
    assumed = [(v, ln) for v, ln in catalog.list_lines()
               if catalog.provenance_report(v, ln)["fields_fact"] == 0]
    for v, ln in assumed:
        assert V.record_tier(v, ln)["tier"] == "assumed"
        assert "NO fact-tier field" in V.describe(v)["line"]


def test_neither_row_type_can_carry_a_number():
    allowed = {str, bool, typing.Optional[str], typing.Tuple[str, ...], typing.Tuple[V.Line, ...]}
    for cls in (TX.Kind, V.Vendor, V.Line):
        for name, hint in typing.get_type_hints(cls).items():
            assert hint in allowed, (cls.__name__, name, hint)


# --------------------------------------------------------------------------- CLI verbs

def test_taxonomy_verb_in_process(make_family, capsys):
    assert make_family.main(["taxonomy", "--check"]) == 0
    assert capsys.readouterr().out.rstrip().endswith("0 problems")
    assert make_family.main(["taxonomy", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["count"] == len(TX.kinds()) and set(doc["available"]) == set(TX.table()["available"])
    assert make_family.main(["taxonomy", "--discipline", "plumbing"]) == 0
    assert "== plumbing" in capsys.readouterr().out
    assert make_family.main(["taxonomy", "flux capacitor"]) == 1
    capsys.readouterr()


def test_vendors_verb_in_process(make_family, capsys):
    assert make_family.main(["vendors", "--check"]) == 0
    assert capsys.readouterr().out.rstrip().endswith("0 problems")
    assert make_family.main(["vendors", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["record_count"] == len(catalog.list_lines())
    assert make_family.main(["vendors", "--kind", "transformer_dry"]) == 0
    assert "RECORD (fact)" in capsys.readouterr().out
    assert make_family.main(["vendors", "nobody-inc"]) == 1
    capsys.readouterr()


def test_one_verb_through_a_real_process():
    r = subprocess.run([sys.executable, MAKE_FAMILY, "taxonomy", "MSB"], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.startswith("Switchboard: Electrical Equipment"), r.stderr[-500:]
