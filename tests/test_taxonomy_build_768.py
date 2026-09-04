"""#768 -- the three findings the #767 merge review left as nits, pinned.

1. taxonomy_build's ``builder_available()`` gate actually gates (the tuple
   truthiness made it dead code);
2. the prompt battery's honest set no longer counts the generic
   "no family plan" refusal as holding the line;
3. the router's taxonomy lane labels a failed sibling plan's errors as its
   own and keeps every built kind's file under a label key.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rvt.frontdoor import taxonomy_build as TB                 # noqa: E402


# ---------------------------------------------------------------------------
# 1. the gate
# ---------------------------------------------------------------------------

def test_an_unbuildable_hint_carrying_row_yields_no_plan(monkeypatch):
    # before #768 `if not TX.builder_available(row)` tested the (bool, why)
    # TUPLE -- always truthy, gate never fired.  test_unbuildable_kinds_
    # yield_no_plan passed only because VAV carries no hint; this pins the
    # gate itself with a hint-carrying row forced unbuildable.
    from rvt.famgen import taxonomy as TX
    assert TB.plans("a 2x4 recessed troffer light fixture"), \
        "precondition: the troffer prompt plans when buildable"
    monkeypatch.setattr(TX, "builder_available",
                        lambda row: (False, "forced unbuildable for #768"))
    assert TB.plans("a 2x4 recessed troffer light fixture") == []


def test_a_buildable_row_still_plans():
    plans = TB.plans("a 2x4 recessed troffer light fixture")
    assert len(plans) == 1
    assert plans[0]["kind"] == "luminaire"


# ---------------------------------------------------------------------------
# 2. the battery's honest set
# ---------------------------------------------------------------------------

def _battery():
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "prompt_battery", os.path.join(root, "tools", "prompt_battery.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeRes:
    def __init__(self, ok, status):
        self.ok = ok
        self.status = status
        self.files = {}


def _run_with_status(monkeypatch, battery, ok, status):
    from rvt.frontdoor import router as R
    monkeypatch.setattr(R, "route",
                        lambda *a, **k: _FakeRes(ok, status))
    return battery.run_prompt("any prompt")


def test_the_generic_refusal_no_longer_holds_the_line(monkeypatch):
    # the pre-#767 troffer failure status: the battery must FAIL it now,
    # not bless it -- it would have PASSed the very bug #766 fixed.
    b = _battery()
    row = _run_with_status(monkeypatch, b, False,
                           "FAILED (no family plan in this prompt could be "
                           "built -- see caveats for every refusal)")
    assert row["held_the_line"] is False


def test_the_taxonomys_own_line_still_holds(monkeypatch):
    b = _battery()
    row = _run_with_status(monkeypatch, b, False,
                           "FAILED (recognised, NOT built by this route: "
                           "'VAV box' -> VAV terminal unit; NOT buildable "
                           "here -- ...)")
    assert row["held_the_line"] is True


def test_a_delivery_holds_the_line(monkeypatch):
    b = _battery()
    row = _run_with_status(monkeypatch, b, True, "OK (1 family .rfa ...)")
    assert row["held_the_line"] is True


def test_a_crash_is_a_fail_but_keyboard_interrupt_propagates(monkeypatch):
    b = _battery()
    from rvt.frontdoor import router as R

    def _boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(R, "route", _boom)
    row = b.run_prompt("any prompt")
    assert row["held_the_line"] is False and "CRASH" in row["status"]

    def _interrupt(*a, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(R, "route", _interrupt)
    with pytest.raises(KeyboardInterrupt):        # was swallowed as CRASH
        b.run_prompt("any prompt")


# ---------------------------------------------------------------------------
# 3. the router lane: sibling labels + per-label file keys
# ---------------------------------------------------------------------------

def test_two_built_kinds_keep_both_files_and_own_their_failures(monkeypatch,
                                                                tmp_path):
    from rvt.frontdoor import router as R
    plans = [
        {"kind": "luminaire", "kw": {"a": 1}, "mention": "m1",
         "label": "kind-one", "route_opts": {}, "notes": []},
        {"kind": "luminaire", "kw": {"a": 2}, "mention": "m2",
         "label": "kind-two", "route_opts": {}, "notes": []},
    ]
    monkeypatch.setattr(TB, "plans", lambda prompt: plans)
    calls = {"n": 0}

    def fake_famspec_rfa(res, kind, kw, out_dir, sub, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            res.errors.append("famspec: kind-two exploded")   # a SIBLING fail
            return None
        res.files["rfa"] = f"file-{calls['n']}.rfa"
        return (object(), f"stem{calls['n']}")
    monkeypatch.setattr(R, "_famspec_rfa", fake_famspec_rfa)
    res = R.RouteResult(ok=True, status="", route="prompt->rfa")
    R._r_prompt_to_rfa(res, {"prompt": "zzz unparseable zzz"},
                       str(tmp_path), {})
    assert res.ok
    # the built kind's file survives under its label key
    assert res.files.get("rfa:kind-one") == "file-1.rfa"
    # the sibling's failure is labelled as the famspec lane's own,
    # never blamed on the scene grammar
    tax = [c for c in res.caveats if c.startswith("taxonomy plan:")]
    assert any("kind-two exploded" in c for c in tax)
    assert not any("kind-two exploded" in c for c in res.caveats
                   if c.startswith("scene grammar:"))
