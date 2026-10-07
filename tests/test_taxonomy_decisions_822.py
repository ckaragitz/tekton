"""#822: a recognised, categorised kind that no lane builds carries a RECORDED decision.

Before this, 62 leaf kinds (disconnects, VFDs, ATSs, smoke detectors, pumps ...) refused the way
the lighting control panel once did -- as the side effect of a taxonomy row with no mechanism.
Now every such row names which of the three honest outcomes closes its gap (archetype / catalog /
not generated) and why; ``taxonomy.check()`` fails on a gap without a decision and on a decision
whose row stopped being a gap, so a new taxonomy row cannot silently add a refusal.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import taxonomy as T  # noqa: E402


def test_every_gap_has_a_decision_and_the_table_is_clean():
    gaps = {r.key for r in T.gap_rows()}
    assert gaps == set(T.DECISIONS)
    assert T.check() == []
    assert all(o in T.DECISION_OUTCOMES and why.strip() for o, why in T.DECISIONS.values())


def test_the_gap_count_only_trends_down():
    # #822 DONE 4: 62 leaf gaps when the decisions were recorded; the count trends down only
    # by building kinds (each such PR drops its decision -- check() enforces it), never up
    assert len(T.gap_rows()) <= 62


def test_a_gap_without_a_decision_fails_the_check(monkeypatch):
    monkeypatch.delitem(T.DECISIONS, "pump")
    assert any("taxonomy[pump]" in p and "no recorded decision" in p for p in T.check())


def test_a_stale_or_malformed_decision_fails_the_check(monkeypatch):
    monkeypatch.setitem(T.DECISIONS, "panelboard", ("archetype", "built already"))
    monkeypatch.setitem(T.DECISIONS, "pump", ("maybe later", "?"))
    monkeypatch.setitem(T.DECISIONS, "boiler", ("archetype", "  "))
    probs = T.check()
    assert any("DECISIONS['panelboard']" in p and "no longer a gap" in p for p in probs)
    assert any("DECISIONS['pump']" in p and "outcome" in p for p in probs)
    assert any("DECISIONS['boiler']" in p and "no reason" in p for p in probs)


def test_the_refusal_and_describe_name_the_decision(monkeypatch):
    ok, why = T.builder_available(T.get("smoke_detector"))
    assert not ok and "planned: built at standard nominal sizes" in why
    ok, why = T.builder_available(T.get("split_system"))
    assert not ok and "covers several products" in why and "#" not in why.split("planned:")[1]
    assert T.describe("smoke detector")["decision"]["outcome"] == "archetype"
    monkeypatch.setitem(T.DECISIONS, "busway", ("not generated", "a stated reason"))
    ok, why = T.builder_available(T.get("busway"))
    assert not ok and "by decision it is not built here: a stated reason" in why


def test_busway_is_a_loadable_family_kind():
    # Revit has no busway system family: busway is loadable, so it is generated, not refused
    assert T.decision("busway")[0] == "archetype"
    assert "drawn, not loaded" not in T.get("busway").note


def test_no_near_miss_mapping_for_the_vav_box():
    # a bare "VAV box" resolves to its own row, which no lane builds yet -- never to the
    # fan-powered terminal (#895); the decision says the alias is split off first
    row = T.resolve("vav box")
    assert row.key == "vav_box" and not T.builder_available(row)[0]
    assert "answers only the 'fan powered box' wording" in T.decision("vav_box")[1]


def test_rows_naming_several_products_are_refined_before_any_archetype():
    assert T.REFINE_FIRST and set(T.REFINE_FIRST) <= set(T.DECISIONS)
    for key, products in T.REFINE_FIRST.items():
        assert len(products) >= 2, key
        assert "refined into them first" in T.decision(key)[1], key
    assert "never one packaged box" in T.decision("split_system")[1]
    # the fan coil constructor (#893) is ONE of the row's products, never all of them
    assert "horizontal concealed unit only" in T.decision("fan_coil_unit")[1]


def test_a_multi_product_row_cannot_gain_a_mechanism_before_it_is_refined(monkeypatch):
    import dataclasses
    row = T._BY_KEY["exhaust_fan"]
    monkeypatch.setitem(T._BY_KEY, "exhaust_fan", dataclasses.replace(row, via=("archetype:x",)))
    assert any("taxonomy[exhaust_fan]: names several products" in p for p in T.check())


def test_a_not_generated_refusal_promises_no_later_lane(monkeypatch):
    monkeypatch.setitem(T.DECISIONS, "busway", ("not generated", "a reason"))
    why = T.builder_available(T.get("busway"))[1]
    assert "no lane builds it:" in why and "yet" not in why
