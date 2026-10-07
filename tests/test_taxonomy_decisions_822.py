"""#822: a recognised, categorised kind that no lane builds carries a RECORDED decision.

Before this, 62 leaf kinds (disconnects, VFDs, ATSs, smoke detectors, pumps ...) refused the way
the lighting control panel once did -- as the side effect of a taxonomy row with no mechanism.
Now every such row names which of the three honest outcomes closes its gap (archetype / catalog /
not generated) and why.  One-shape rows carry an explicit ``DECISIONS`` entry; rows that name
SEVERAL products (``REFINE_FIRST``, #1043 review) get a derived one -- one archetype per product,
after the row is split into one row per product and its key retired -- and ``check()`` fails if
such a row ever gains a mechanism or becomes a generic word, so "one box for all" cannot ship.
"""
from __future__ import annotations

import dataclasses
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import taxonomy as T  # noqa: E402


def _replace_rows(monkeypatch, drop=(), add=()):
    """Patch the table the way a real edit to ``_ROWS`` would: rows, key index and alias index
    together (the alias index is what ``resolve`` / ``scan`` read)."""
    rows = tuple(r for r in T._ROWS if r.key not in drop) + tuple(add)
    alias, clashes = T._alias_index(rows, T._names)
    monkeypatch.setattr(T, "_ROWS", rows)
    monkeypatch.setattr(T, "_BY_KEY", {r.key: r for r in rows})
    monkeypatch.setattr(T, "_ALIAS", alias)
    monkeypatch.setattr(T, "_ALIAS_CLASHES", clashes)


def test_every_gap_has_a_decision_and_the_table_is_clean():
    gaps = T.gap_rows()
    assert all(T.decision(r) is not None for r in gaps)
    assert {r.key for r in gaps} == set(T.DECISIONS) | (set(T.REFINE_FIRST) & {r.key for r in gaps})
    assert not set(T.DECISIONS) & set(T.REFINE_FIRST)
    assert T.check() == []
    assert all(T.decision(r)[0] in T.DECISION_OUTCOMES and T.decision(r)[1].strip() for r in gaps)


def test_the_gap_count_only_trends_down():
    # #822 DONE 4: 62 leaf gaps when the decisions were recorded; the count falls only by
    # building kinds (each such PR drops or retires its decision -- check() enforces it)
    assert len(T.gap_rows()) <= 62


def test_a_gap_without_a_decision_fails_the_check(monkeypatch):
    monkeypatch.delitem(T.DECISIONS, "generator")
    assert any("taxonomy[generator]" in p and "no recorded decision" in p for p in T.check())


def test_a_stale_overlapping_or_malformed_decision_fails_the_check(monkeypatch):
    monkeypatch.setitem(T.DECISIONS, "panelboard", ("archetype", "built already"))
    monkeypatch.setitem(T.DECISIONS, "pump", ("archetype", "one pump for all"))
    monkeypatch.setitem(T.DECISIONS, "ups", ("maybe later", "?"))
    monkeypatch.setitem(T.DECISIONS, "generator", ("archetype", "  "))
    probs = T.check()
    assert any("DECISIONS['panelboard']" in p and "no longer a gap" in p for p in probs)
    assert any("'pump' is in both DECISIONS and REFINE_FIRST" in p for p in probs)
    assert any("DECISIONS['ups']" in p and "outcome" in p for p in probs)
    assert any("DECISIONS['generator']" in p and "no reason" in p for p in probs)


def test_the_refusal_and_describe_name_the_decision(monkeypatch):
    ok, why = T.builder_available(T.get("smoke_detector"))
    assert not ok and "planned: built at standard nominal sizes" in why
    ok, why = T.builder_available(T.get("split_system"))
    assert not ok and "covers several products" in why and "#" not in why.split("planned:")[1]
    assert T.describe("smoke detector")["decision"]["outcome"] == "archetype"
    monkeypatch.setitem(T.DECISIONS, "generator", ("not generated", "a stated reason"))
    ok, why = T.builder_available(T.get("generator"))
    assert not ok and "by decision it is not built here: a stated reason" in why
    assert "no lane builds it:" in why and "yet" not in why     # no later lane is promised


def test_busway_is_a_loadable_family_kind():
    # Revit has no busway system family: busway is loadable, so it is generated, not refused
    assert T.decision("busway")[0] == "archetype"
    assert "drawn, not loaded" not in T.get("busway").note


def test_no_near_miss_mapping_for_the_vav_box():
    # a bare "VAV box" resolves to its own row, which no lane builds yet -- never to the
    # fan-powered terminal (#895)
    row = T.resolve("vav box")
    assert row.key == "vav_box" and not T.builder_available(row)[0]
    assert "answers only the 'fan powered box' wording" in T.decision("vav_box")[1]


def test_rows_naming_several_products_get_a_derived_split_first_decision():
    for key, products in T.REFINE_FIRST.items():
        assert len(products) >= 2, key
        assert "one row per product is added beside this one" in T.decision(key)[1], key
    assert "never one packaged box" in T.decision("split_system")[1]
    # the fan coil constructor (#893) is ONE of the row's products, never all of them
    assert "horizontal concealed unit only" in T.decision("fan_coil_unit")[1]


def test_a_multi_product_row_given_a_mechanism_fails_even_with_its_decision_gone(monkeypatch):
    # the bypass: give the row a builder in _ROWS itself.  Its derived decision vanishes (it is
    # no longer a gap) -- and the REFINE_FIRST law still fails the check
    row = T._BY_KEY["fan_coil_unit"]
    _replace_rows(monkeypatch, drop=("fan_coil_unit",),
                  add=(dataclasses.replace(row, via=("house:rvt.famgen.fan_coil:make_fan_coil_unit",)),))
    probs = T.check()
    assert any("taxonomy[fan_coil_unit]: names several products" in p for p in probs), probs
    assert not any("DECISIONS['fan_coil_unit']" in p for p in probs)


def test_a_multi_product_row_cannot_be_renamed_away(monkeypatch):
    # the rename bypass: the same label and words under a new key, with a builder.  The
    # REFINE_FIRST key must stay a row, so the check fails
    row = T._BY_KEY["fan_coil_unit"]
    _replace_rows(monkeypatch, drop=("fan_coil_unit",),
                  add=(dataclasses.replace(row, key="fan_coil",
                                           via=("house:rvt.famgen.fan_coil:make_fan_coil_unit",)),))
    assert any("REFINE_FIRST['fan_coil_unit'] is no row" in p for p in T.check())


def test_the_prescribed_split_passes_and_the_shared_words_stay_unbuilt(monkeypatch):
    # the path every REFINE_FIRST decision prescribes, done for the fan coil: the multi-product
    # row STAYS (unbuilt, its shared words "fan coil unit" / "fcu" / "fan coil"); one row per
    # product is added beside it with only the words that name that product, the horizontal
    # one carrying the existing constructor (#893)
    row = T._BY_KEY["fan_coil_unit"]
    mk = lambda key, label, via=(), aliases=(): T._k(key, label, row.discipline, row.category,
                                                    via, aliases=aliases)
    products = (mk("fan_coil_horizontal", "Fan coil unit (horizontal concealed)",
                   via=("house:rvt.famgen.fan_coil:make_fan_coil_unit",),
                   aliases=("horizontal fan coil", "concealed fan coil")),
                mk("fan_coil_vertical", "Fan coil unit (vertical cabinet)",
                   aliases=("vertical fan coil",)),
                mk("fan_coil_cassette", "Fan coil unit (ceiling cassette)",
                   aliases=("cassette fan coil",)))
    _replace_rows(monkeypatch, add=products)
    monkeypatch.setitem(T.DECISIONS, "fan_coil_vertical", ("archetype", "a vertical cabinet unit"))
    monkeypatch.setitem(T.DECISIONS, "fan_coil_cassette", ("archetype", "a ceiling cassette"))
    assert T.check() == []
    for shared in ("fan coil unit", "fan coil", "fcu"):          # never one box for all
        r = T.resolve(shared)
        assert r.key == "fan_coil_unit" and not T.builder_available(r)[0], shared
    assert T.resolve("horizontal fan coil").key == "fan_coil_horizontal"
    assert T.resolve("cassette fan coil").key == "fan_coil_cassette"


def test_a_not_generated_reason_is_user_safe(monkeypatch):
    monkeypatch.setitem(T.DECISIONS, "generator", ("not generated", "see #123 in rvt.x"))
    assert any("DECISIONS['generator'] is 'not generated'" in p for p in T.check())
