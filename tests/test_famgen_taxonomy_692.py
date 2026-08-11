"""#692 -- the MEP taxonomy + vendor directory and, above all, ITS GATE.

The tables in ``rvt.famgen.taxonomy`` are trade knowledge, and the one thing
that must never happen is a row claiming something the code cannot back up.
So this module is mostly NEGATIVE tests: for every rule ``taxonomy.check()``
advertises, a test breaks a copy of the table in exactly that way and asserts
the gate FAILS.  A gate nobody has watched fail is not evidence.

The headline pair:

* :func:`test_every_facts_held_line_really_resolves_through_catalog` -- for
  every line the directory says we hold facts for, ``catalog`` really loads the
  record, it really has variants, and a real figure really comes back out.
* :func:`test_a_facts_held_line_catalog_cannot_resolve_fails_the_gate` -- and
  when it does not, ``--check`` fails.

Fresh-clone safe: reads only ``src/rvt/famgen/facts/**`` (shipped in-repo),
no ``samples/``, no ifcopenshell, no built ladders.
"""
from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from rvt.famgen import catalog as C
from rvt.famgen import skeleton as SK
from rvt.famgen import standards as ST
from rvt.famgen import taxonomy as T

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# helpers: build a MUTATED copy of the tables and run the gate against it
# ---------------------------------------------------------------------------

def _run_check(monkeypatch, *, taxa=None, vendors=None, allowed_taxon=None):
    """Run ``taxonomy.check()`` against replaced module tables."""
    if taxa is not None:
        monkeypatch.setattr(T, "_TAXA", tuple(taxa))
        monkeypatch.setattr(T, "MEP_TAXONOMY", {t.key: t for t in taxa})
    if vendors is not None:
        monkeypatch.setattr(T, "_VENDORS", tuple(vendors))
        monkeypatch.setattr(T, "VENDORS", {v.key: v for v in vendors})
    if allowed_taxon is not None:
        monkeypatch.setattr(T, "_ALLOWED_TAXON_FIELDS", allowed_taxon)
    return T.check()


def _taxa_with(key, **changes):
    """The shipped taxa, with one entry modified."""
    return [dataclasses.replace(t, **changes) if t.key == key else t
            for t in T._TAXA]


def _vendors_with(vendor_key, line_name, **changes):
    """The shipped vendors, with one line modified."""
    out = []
    for v in T._VENDORS:
        if v.key != vendor_key:
            out.append(v)
            continue
        lines = tuple(dataclasses.replace(l, **changes)
                      if l.line == line_name else l for l in v.lines)
        out.append(dataclasses.replace(v, lines=lines))
    return out


def _problems_matching(probs, rule):
    return [p for p in probs if p.startswith(rule + " ")]


# ---------------------------------------------------------------------------
# the shipped tables are sound
# ---------------------------------------------------------------------------

def test_the_shipped_tables_pass_their_own_gate():
    probs = T.check()
    assert probs == [], "taxonomy.check() on the shipped tables:\n" + "\n".join(probs)


def test_the_check_cli_exits_zero_on_the_shipped_tables():
    r = subprocess.run([sys.executable, "-m", "rvt.famgen.taxonomy", "--check"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 problems" in r.stdout


def test_the_check_cli_exits_nonzero_when_a_claim_cannot_be_backed(monkeypatch,
                                                                   capsys):
    """The gate must FAIL, not merely mention: an unresolvable facts_held
    claim has to come back as exit 1."""
    monkeypatch.setattr(T, "_VENDORS", tuple(
        _vendors_with("eaton", "Pow-R-Line panelboards",
                      facts_ref=("eaton", "no-such-line"))))
    rc = T.main(["--check"])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "T5" in out and "catalog cannot resolve" in out
    assert "0 problems" not in out


def test_the_tables_are_not_trivially_small():
    """A gate over an empty table proves nothing."""
    assert len(T._TAXA) >= 40
    assert len(T._VENDORS) >= 20
    assert len({t.category for t in T._TAXA}) >= 12
    assert len({t.discipline for t in T._TAXA}) == len(T.DISCIPLINES)


# ---------------------------------------------------------------------------
# THE HEADLINE: facts_held is a claim the code can back up
# ---------------------------------------------------------------------------

def test_every_facts_held_line_really_resolves_through_catalog():
    """For every line the directory claims facts for, catalog resolves the
    record, it has variants, and a real figure comes back out of it."""
    sourced = T.sourced_lines()
    assert sourced, "the directory claims no facts at all -- that cannot be right"
    for v, l in sourced:
        fv, fl = l.facts_ref
        doc = C.load_line(fv, fl)                       # raises if unresolvable
        variants = doc.get("variants") or []
        assert variants, f"{v.key}/{l.line}: {fv}/{fl} has no variants"
        assert C.validate_line(doc) == [], f"{fv}/{fl} is not a valid record"
        # a figure really comes back: every variant exposes its dims in feet
        for var in variants:
            got = C.dims_feet(var)
            assert set(got) == {"w", "h", "d"}
            # and the model is selectable by name, not by guessing
            picked = C.get_variant(fv, fl, model=var["model"])
            assert picked["model"] == var["model"]


def test_facts_held_lines_match_the_store_exactly():
    """Every facts_held ref is in the store, and every store record is
    claimed -- the directory neither overstates nor understates."""
    store = set(C.list_lines())
    claimed = {l.facts_ref for _, l in T.sourced_lines()}
    assert claimed <= store, f"claims not in the store: {claimed - store}"
    assert store <= claimed, f"store records no line claims: {store - claimed}"


def test_lines_we_hold_no_facts_for_say_so_and_point_nowhere():
    unheld = [(v, l) for v in T._VENDORS for l in v.lines if not l.facts_held]
    assert unheld, "every line claims facts -- the honest majority is missing"
    for v, l in unheld:
        assert l.facts_ref is None, f"{v.key}/{l.line} points at a record it does not claim"
    # the majority of the directory is honestly empty
    assert len(unheld) > len(T.sourced_lines())


# ---------------------------------------------------------------------------
# NEGATIVE: each rule of the gate really fires
# ---------------------------------------------------------------------------

def test_a_facts_held_line_catalog_cannot_resolve_fails_the_gate(monkeypatch):
    """T5 -- the rule the module exists for."""
    vendors = _vendors_with("eaton", "Pow-R-Line panelboards",
                            facts_ref=("eaton", "no-such-line"))
    probs = _run_check(monkeypatch, vendors=vendors)
    hits = _problems_matching(probs, "T5")
    assert hits, f"T5 did not fire; got {probs}"
    assert "catalog cannot resolve" in hits[0]


def test_a_facts_held_line_naming_a_missing_vendor_dir_fails_the_gate(monkeypatch):
    vendors = _vendors_with("lithonia", "BLT LED troffers",
                            facts_ref=("nosuchvendor", "blt-led-troffer"))
    probs = _run_check(monkeypatch, vendors=vendors)
    assert _problems_matching(probs, "T5"), probs


def test_a_facts_held_line_with_a_malformed_ref_fails_the_gate(monkeypatch):
    vendors = _vendors_with("hps", "Sentinel G dry-type transformers",
                            facts_ref=None)
    probs = _run_check(monkeypatch, vendors=vendors)
    assert _problems_matching(probs, "T5"), probs


def test_a_facts_ref_without_the_claim_fails_the_gate(monkeypatch):
    """T6 -- cannot point at a record while saying we hold nothing."""
    vendors = _vendors_with("siemens", "P1 / P2 panelboards",
                            facts_held=False,
                            facts_ref=("eaton", "pow-r-line-panelboards"))
    probs = _run_check(monkeypatch, vendors=vendors)
    assert _problems_matching(probs, "T6"), probs


def test_an_unclaimed_facts_record_fails_the_gate(monkeypatch):
    """T8 -- the directory may not quietly understate what we hold."""
    vendors = [v for v in T._VENDORS if v.key != "hps"]
    probs = _run_check(monkeypatch, vendors=vendors)
    hits = _problems_matching(probs, "T8")
    assert hits, f"T8 did not fire; got {probs}"
    assert any("hps/sentinel-g-transformers" in h for h in hits)


def test_two_lines_claiming_one_record_fails_the_gate(monkeypatch):
    vendors = _vendors_with("siemens", "Dry-type transformers",
                            facts_held=True,
                            facts_ref=("hps", "sentinel-g-transformers"))
    probs = _run_check(monkeypatch, vendors=vendors)
    assert _problems_matching(probs, "T8"), probs


def test_a_category_skeleton_does_not_know_fails_the_gate(monkeypatch):
    """T2 -- the taxonomy must agree with skeleton's category vocabulary."""
    taxa = _taxa_with("panelboard", category="electrical_panel_thing")
    probs = _run_check(monkeypatch, taxa=taxa)
    hits = _problems_matching(probs, "T2")
    assert hits, f"T2 did not fire; got {probs}"
    assert "unknown to skeleton._resolve_category" in hits[0]


def test_every_skeleton_category_this_table_uses_has_a_standards_table():
    """The precondition behind T2's second branch: today the two vocabularies
    agree, so no shipped row can hit it."""
    for t in T._TAXA:
        SK._resolve_category(t.category)                    # skeleton knows it
        assert ST.CATEGORY_STANDARDS.get(ST.canonical_category(t.category))


def test_a_category_with_no_standards_table_fails_the_gate(monkeypatch):
    """T2 second branch -- a category skeleton knows but standards has no
    table for.  That cannot happen today (the test above pins it), so the
    gap is SIMULATED by removing one category from standards: the point is
    that if the two vocabularies ever drift apart, the gate says so instead
    of emitting a bare family."""
    assert "mechanical_equipment" not in ST.CATEGORY_ALIASES
    shrunk = {k: v for k, v in ST.CATEGORY_STANDARDS.items()
              if k != "mechanical_equipment"}
    monkeypatch.setattr(ST, "CATEGORY_STANDARDS", shrunk)
    assert not ST.CATEGORY_STANDARDS.get(
        ST.canonical_category("mechanical_equipment"))
    probs = T.check()
    hits = _problems_matching(probs, "T2")
    assert hits, f"T2 did not fire; got {probs}"
    assert "no standards table" in hits[0]


def test_an_unknown_category_name_fails_the_gate(monkeypatch):
    """T2 first branch, with skeleton's own refusal pinned alongside."""
    with pytest.raises(KeyError):
        SK._resolve_category("definitely_not_a_category")
    taxa = _taxa_with("cable_tray_fitting", category="definitely_not_a_category")
    probs = _run_check(monkeypatch, taxa=taxa)
    assert _problems_matching(probs, "T2"), probs


def test_an_invented_schedule_parameter_fails_the_gate(monkeypatch):
    """T3 -- 'an engineer schedules it by X' is bound to the standards table."""
    taxa = _taxa_with("dry_type_transformer",
                      schedule_by=("kVA Rating", "Flux Capacity"))
    probs = _run_check(monkeypatch, taxa=taxa)
    hits = _problems_matching(probs, "T3")
    assert hits, f"T3 did not fire; got {probs}"
    assert "Flux Capacity" in hits[0]


def test_a_second_spelling_of_a_standards_parameter_fails_the_gate(monkeypatch):
    """T3 -- #622's one-entry-per-meaning law reaches this table too."""
    # standards spells it 'Luminous Flux'; 'Lumens' is the same quantity
    assert ST.meaning_key("Lumens") == ST.meaning_key("Luminous Flux")
    taxa = _taxa_with("recessed_troffer", schedule_by=("Lumens", "Wattage"))
    probs = _run_check(monkeypatch, taxa=taxa)
    hits = _problems_matching(probs, "T3")
    assert hits, f"T3 did not fire; got {probs}"
    assert "another spelling" in hits[0]


def test_an_empty_schedule_by_fails_the_gate(monkeypatch):
    taxa = _taxa_with("pump", schedule_by=())
    probs = _run_check(monkeypatch, taxa=taxa)
    assert _problems_matching(probs, "T4"), probs


def test_an_unknown_discipline_fails_the_gate(monkeypatch):
    taxa = _taxa_with("pump", discipline="vibes")
    probs = _run_check(monkeypatch, taxa=taxa)
    assert _problems_matching(probs, "T4"), probs


def test_a_line_naming_an_unknown_taxon_fails_the_gate(monkeypatch):
    vendors = _vendors_with("nibco", "Valves and strainers",
                            taxa=("valve", "warp_core"))
    probs = _run_check(monkeypatch, vendors=vendors)
    assert _problems_matching(probs, "T4"), probs


@pytest.mark.parametrize("bad", [
    "a 12 in wide ladder tray",
    "rated 480 V",
    "75 kVA general purpose",
    "delivers 4600 lm",
    "weighs 300 lb",
])
def test_a_dimension_or_rating_in_the_prose_fails_the_gate(monkeypatch, bad):
    """T7 -- the mechanical half of 'this module holds no figures'."""
    taxa = _taxa_with("panelboard", role=bad)
    probs = _run_check(monkeypatch, taxa=taxa)
    hits = _problems_matching(probs, "T7")
    assert hits, f"T7 did not fire for {bad!r}; got {probs}"


def test_a_dimension_in_a_vendor_line_name_fails_the_gate(monkeypatch):
    vendors = _vendors_with("hoffman", "Enclosures and wireway",
                            note="bodies are 12 in deep")
    probs = _run_check(monkeypatch, vendors=vendors)
    assert _problems_matching(probs, "T7"), probs


def test_product_designations_are_not_mistaken_for_figures():
    """T7 must not fire on 'NEMA 5-15R', 'Cat 6', 'Model 6', 'I-Line'."""
    for ok in ("NEMA 5-15R duplex", "Cat 6 outlet", "Model 6 motor control "
               "centres", "I-Line", "Pow-R-Line", "9395 UPS",
               "39 series air handlers", "P1 / P2 panelboards"):
        assert T._NUM_UNIT_RE.search(ok) is None, ok


def test_a_field_that_could_hold_a_dimension_fails_the_gate(monkeypatch):
    """T1 -- the structural guarantee: adding a slot for a figure fails."""
    shrunk = T._ALLOWED_TAXON_FIELDS - {"role"}
    probs = _run_check(monkeypatch, allowed_taxon=shrunk)
    hits = _problems_matching(probs, "T1")
    assert hits, f"T1 did not fire; got {probs}"


def test_a_facts_record_category_disagreeing_with_the_taxon_fails(monkeypatch):
    """T9 -- the two tables and the store must agree on what a line is."""
    vendors = _vendors_with("lithonia", "BLT LED troffers",
                            taxa=("panelboard",))
    probs = _run_check(monkeypatch, vendors=vendors)
    hits = _problems_matching(probs, "T9")
    assert hits, f"T9 did not fire; got {probs}"


# ---------------------------------------------------------------------------
# the tables themselves carry no figure, structurally
# ---------------------------------------------------------------------------

def test_neither_row_type_has_a_field_a_figure_could_live_in():
    assert {f.name for f in dataclasses.fields(T.Taxon)} == \
        T._ALLOWED_TAXON_FIELDS
    assert {f.name for f in dataclasses.fields(T.VendorLine)} == \
        T._ALLOWED_LINE_FIELDS
    banned = {"dims", "dims_in", "ratings", "size", "width", "height",
              "depth", "weight", "voltage", "value", "values"}
    for dc_type in (T.Taxon, T.VendorLine, T.Vendor):
        names = {f.name for f in dataclasses.fields(dc_type)}
        assert not (names & banned), f"{dc_type.__name__} gained {names & banned}"


def test_no_shipped_row_carries_a_number_with_a_unit():
    for t in T._TAXA:
        for where, s in T._text_of(t):
            assert T._NUM_UNIT_RE.search(s) is None, f"{t.key}.{where}: {s!r}"
    for v in T._VENDORS:
        for l in v.lines:
            for where, s in T._text_of(l):
                assert T._NUM_UNIT_RE.search(s) is None, \
                    f"{v.key}/{l.line}.{where}: {s!r}"


def test_fact_is_not_a_claim_tier_this_module_offers():
    assert "fact" not in T.CLAIM_TIERS
    assert set(T.CLAIM_TIERS) == {T.CLAIM_TAXONOMY, T.CLAIM_DIRECTORY}
    for t in T._TAXA:
        assert t.claim == T.CLAIM_TAXONOMY
    for v in T._VENDORS:
        for l in v.lines:
            assert l.claim == T.CLAIM_DIRECTORY


# ---------------------------------------------------------------------------
# agreement with the tables this one leans on
# ---------------------------------------------------------------------------

def test_every_taxon_category_resolves_the_same_way_skeleton_resolves_it():
    for t in T._TAXA:
        ost = SK._resolve_category(t.category)
        assert isinstance(ost, int)
        assert T.describe(t.key)["category_ost"] == ost


def test_every_taxon_category_has_a_standards_table():
    for t in T._TAXA:
        canon = ST.canonical_category(t.category)
        assert ST.CATEGORY_STANDARDS.get(canon), f"{t.key} -> {canon}"


def test_every_schedule_parameter_is_really_in_the_standards_table():
    for t in T._TAXA:
        rows = ST.CATEGORY_STANDARDS[ST.canonical_category(t.category)]
        known = {ST.meaning_key(p.name) for p in rows}
        known |= {ST.meaning_key(p.name) for p in ST.COMMON_BUILTINS}
        for name in t.schedule_by:
            assert ST.meaning_key(name) in known, f"{t.key}: {name}"


def test_standards_own_gate_is_still_clean():
    """This module leans on standards' table; if that gate is red, T3's
    conclusions mean nothing."""
    assert ST.check_specs() == []


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def test_resolve_finds_trade_names_and_never_guesses():
    assert T.resolve("mcc").key == "motor_control_center"
    assert T.resolve("panel").key == "panelboard"
    assert T.resolve("horn strobe").key == "notification_appliance"
    assert T.resolve("xfmr").key == "dry_type_transformer"
    assert T.resolve("toilet").key == "water_closet"
    # not a near match, not a guess
    assert T.resolve("panelboardish") is None
    assert T.resolve("") is None
    assert T.resolve("a thing that does not exist") is None


def test_describe_of_an_unknown_taxon_says_so_plainly():
    d = T.describe("flux inverter")
    assert d["known"] is False
    assert "no taxonomy entry" in d["note"]
    assert d["nominal_tier"] == T.NOMINAL_TIER_NOTE


def test_describe_of_a_sourced_taxon_names_its_facts():
    d = T.describe("panelboard")
    assert d["known"] is True
    assert d["category"] == "panelboard"
    assert d["facts_held_lines"] >= 2          # eaton + square-d
    refs = {tuple(v["facts_ref"]) for v in d["vendors"] if v["facts_held"]}
    assert ("eaton", "pow-r-line-panelboards") in refs
    assert ("square-d", "nq-nf-iline-panelboards") in refs


def test_describe_of_an_unsourced_taxon_is_honest_about_holding_nothing():
    d = T.describe("chiller")
    assert d["known"] is True
    assert d["facts_held_lines"] == 0
    assert d["vendors"], "we still know who makes one"
    assert all(v["facts_held"] is False for v in d["vendors"])


def test_lines_for_taxon_puts_the_sourced_ones_first():
    lines = T.lines_for_taxon("panelboard")
    held = [i for i, (_, l) in enumerate(lines) if l.facts_held]
    assert held == list(range(len(held))), "facts-held lines must sort first"


def test_taxa_for_category_agrees_with_the_rows():
    for t in T._TAXA:
        assert t in T.taxa_for_category(t.category)
    assert T.taxa_for_category("plumbing_fixture")
    assert T.taxa_for_category("no_such_category") == ()


# ---------------------------------------------------------------------------
# the nominal tier stays where it belongs
# ---------------------------------------------------------------------------

def test_the_module_works_without_the_archetype_registry():
    """archetypes.py lives on the unmerged PR #674; nothing here may require
    it, and the status must say which world we are in."""
    st = T.archetype_status()
    assert set(st) >= {"present", "note"}
    assert isinstance(st["present"], bool)
    assert st["note"] == T.NOMINAL_TIER_NOTE
    if not st["present"]:
        assert "reason" in st
    # the gate does not depend on it either way
    assert T.check() == []


def test_taxonomy_does_not_import_archetypes_at_module_scope():
    src = (REPO / "src/rvt/famgen/taxonomy.py").read_text(encoding="utf-8")
    top = [ln for ln in src.splitlines()
           if ln.startswith("from . import") or ln.startswith("import ")]
    assert not any("archetype" in ln for ln in top), \
        "archetypes must be imported softly, inside a function"


def test_the_nominal_tier_is_named_and_disclaimed():
    assert "nominal" in T.NOMINAL_TIER_NOTE
    assert "archetype" in T.NOMINAL_TIER_NOTE
    assert "facts/" in T.NOT_A_FACT_NOTE
    assert "catalog" in T.NOT_A_FACT_NOTE


# ---------------------------------------------------------------------------
# the whole table renders
# ---------------------------------------------------------------------------

def test_table_renders_and_counts_agree():
    tb = T.table()
    assert tb["counts"]["taxa"] == len(T._TAXA)
    assert tb["counts"]["vendors"] == len(T._VENDORS)
    assert tb["counts"]["lines_facts_held"] == len(T.sourced_lines())
    assert tb["counts"]["facts_store_lines"] == len(C.list_lines())
    assert tb["counts"]["lines_facts_held"] == tb["counts"]["facts_store_lines"]
    assert set(tb["taxa"]) == set(T.MEP_TAXONOMY)
    assert set(tb["vendors"]) == set(T.VENDORS)


def test_table_is_json_serialisable():
    import json
    json.loads(json.dumps(T.table()))
