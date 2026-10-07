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
    # #822 DONE 4: 62 leaf gaps when the decisions were recorded; each later PR that builds a
    # kind removes its decision (check() enforces it), so this number may only fall
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


def test_the_refusal_names_the_decision():
    ok, why = T.builder_available(T.get("smoke_detector"))
    assert not ok and "planned lane (catalog, #822)" in why
    ok, why = T.builder_available(T.get("busway"))
    assert not ok and "not generated here, by decision" in why


def test_no_near_miss_mapping_for_the_vav_box():
    # the fan-powered terminal (#895) must never answer a bare "VAV box": the decision says so
    assert "never" in T.decision("vav_box")[1]
