"""#692 slice 2 -- the MEP taxonomy and the vendor directory are what the prompt grammar and
the plan resolver READ (DONE 3 relay + DONE 5): a phrase scanner over both tables, generic
words that name a category rather than a type, makers carried as declared identity with the
directory's one honest sentence, and the review nits carried from #735."""
from __future__ import annotations

import types

import pytest

from rvt.famgen import taxonomy as TX
from rvt.famgen import vendors as V
from rvt.frontdoor import prompt_intent as PP


# --------------------------------------------------------------------------- the scanner

def _keys(text):
    return [(m.key, m.text) for m in TX.scan(text)]


def test_scan_is_plural_spacing_and_case_tolerant_longest_first():
    got = _keys("A fire alarm control panel, two exhaust fans, cable trays, three VAVs, "
                "down lights, J-boxes and an UPS")
    assert got == [("fire_alarm_control_panel", "fire alarm control panel"),
                   ("exhaust_fan", "exhaust fans"), ("cable_tray", "cable trays"),
                   ("vav_box", "VAVs"), ("downlight", "down lights"),
                   ("junction_box", "J-boxes"), ("ups", "UPS")]


def test_scan_mentions_are_ordered_disjoint_spans_of_the_text():
    text = "smoke detectors, a duct smoke detector and horn strobes"
    ms = TX.scan(text)
    assert [m.key for m in ms] == ["smoke_detector", "duct_smoke_detector", "horn_strobe"]
    assert all(text[m.start:m.end] == m.text for m in ms)
    assert all(a.end <= b.start for a, b in zip(ms, ms[1:]))


@pytest.mark.parametrize("text", ["a room 10 meters by 8 meters", "keep the drive aisle clear",
                                  "a box of parts", "switch the layout", "cut the pipe and duct"])
def test_scan_skips_ambiguous_words_standing_alone(text):
    assert TX.scan(text) == []


@pytest.mark.parametrize("text,key", [("a pull box", "junction_box"),
                                      ("an automatic transfer switch", "automatic_transfer_switch"),
                                      ("a meter socket", "meter_center"),
                                      ("one duct detector", "duct_smoke_detector")])
def test_scan_still_reads_ambiguous_words_inside_a_longer_name(text, key):
    assert [m.key for m in TX.scan(text)] == [key]


def test_resolve_keeps_answering_the_ambiguous_word_as_a_whole_answer():
    # the interview answer 'switch' IS a light switch; only the sentence scanner skips it
    assert TX.resolve("switch").key == "light_switch" and TX.resolve("box").key == "junction_box"


def test_gates_stay_clean_with_the_scanner_tables():
    assert TX.check() == []
    assert V.check() == []
    assert all(w in TX._ALIAS for w in TX.AMBIGUOUS_ALONE)
    assert all(w in V._ALIAS for w in V.AMBIGUOUS_ALONE)


# --------------------------------------------------------------------------- generic words

def test_a_generic_word_names_the_types_it_narrows_to_and_is_never_buildable():
    row = TX.resolve("light fixtures")
    assert row.key == "luminaire" and row.refine and not row.via
    ok, why = TX.builder_available(row)
    assert not ok and why.startswith("a generic word -- name the type:")
    assert "Recessed LED troffer" in why and "(buildable here)" in why
    d = TX.describe("lighting fixture")
    assert d["generic"] is True and d["available"] is False and d["lane"] == "none"
    assert TX.describe("troffer")["generic"] is False


def _row(**kw):
    base = dict(key="zz_test", label="Test kind", discipline="lighting", category="lighting_fixture")
    base.update(kw)
    return TX.Kind(**base)


@pytest.mark.parametrize("kw,needle", [
    (dict(refine=("no_such_kind",)), "refines to unknown kind"),
    (dict(refine=("luminaire",)), "itself generic"),
    (dict(refine=("pump",)), "never changes category"),
    (dict(refine=("troffer",), via=("famspec:luminaire/recessed-troffer",)), "cannot declare build"),
    (dict(category=None, pending="Sprinklers", refine=("troffer",)), "pending row cannot"),
    (dict(category=None, pending="Lighting Fixtures"), "already carries"),
    (dict(category=None, pending="Doors"), "resolves through skeleton._resolve_category"),
])
def test_check_row_rejects_dishonest_generic_and_pending_rows(kw, needle):
    problems = TX.check_row(_row(**kw))
    assert any(needle in p for p in problems), problems


# --------------------------------------------------------------------------- nits from #735

@pytest.mark.parametrize("mech,needle", [
    ("house:json:dumps", "not one of ours"),                       # importable, but not rvt.
    ("house:rvt.ifc.intent:NO_SUCH_BUILDER", "no such callable"),
    ("house:rvt.ifc.intent:DEVICE_PSET", "no such callable"),      # an rvt attribute, not callable
])
def test_house_mechanism_must_be_a_callable_in_an_rvt_module(mech, needle):
    row = _row(key="zz_house", category="switchboard", discipline="electrical", via=(mech,))
    problems = TX.check_row(row)
    assert any(needle in p for p in problems), problems
    assert TX.builder_available(row, strict=True) == (False, problems[-1].split(": ", 1)[1])


def test_a_record_that_fails_to_load_is_a_finding_not_a_traceback(monkeypatch):
    from rvt.famgen import catalog as C
    real = C.load_line

    def broken(vendor, line, *a, **k):
        if (vendor, line) == ("lithonia", "blt-led-troffer"):
            raise C.CatalogError("simulated corrupt record")
        return real(vendor, line, *a, **k)

    monkeypatch.setattr(C, "load_line", broken)
    row = TX.get("troffer")
    ok, why = TX.builder_available(row, strict=True)
    assert not ok and "does not load" in why and "simulated corrupt record" in why
    assert "does not load" in TX.describe("troffer")["line"]
    assert any("does not load" in p for p in TX.check_row(row))
    assert any("does not load" in p for p in V.check())


def test_record_problems_compare_the_member_and_the_ost_label(monkeypatch):
    from rvt.famgen import catalog as C
    real = C.load_line

    def relabelled(vendor, line, *a, **k):
        rec = dict(real(vendor, line, *a, **k))
        if (vendor, line) == ("generic", "devices-and-mounting"):
            rec["revit_category"] = "OST_LightingFixtures"
            rec["variants"] = [x for x in rec["variants"] if x.get("model") != "box-4in-square"]
        return rec

    monkeypatch.setattr(C, "load_line", relabelled)
    problems = TX.check_row(TX.get("junction_box"))
    assert any("holds no variant 'box-4in-square'" in p for p in problems), problems
    assert any("files under 'Lighting Fixtures'" in p for p in problems), problems


def test_vendor_describe_counts_the_tier_on_the_member_a_kind_selects():
    # ONE shared device record: the 4in box variant carries the fact-tier fields, the
    # receptacle variant none -- a kind must be judged on ITS member (nit 1 of #735)
    jb = V.describe("generic", kind="junction_box")
    rc = V.describe("generic", kind="receptacle")
    assert jb["lines"][0]["model"] == "box-4in-square" and jb["lines"][0]["fields_fact"] > 0
    assert rc["lines"][0]["model"] == "duplex-receptacle-5-15R" and rc["lines"][0]["fields_fact"] == 0
    assert "variant box-4in-square: sourced facts" in jb["line"]
    assert "variant duplex-receptacle-5-15R: a catalog record with NO fact-tier field" in rc["line"]
    whole = V.describe("generic")                    # no kind: the whole line, as before
    assert whole["lines"][0]["model"] is None


# --------------------------------------------------------------------------- vendors: scan / declared

def test_vendor_scan_reads_names_aliases_and_capitalised_common_words_only():
    got = [(m.key, m.text) for m in V.scan(
        "Six Eaton panels, a square d NQ board, a Hammond transformer, GE breakers rated "
        "1200 watts, Watts regulators, a cable carrier by york, York chillers, NEMA 3R")]
    assert got == [("eaton", "Eaton"), ("square-d", "square d"), ("hps", "Hammond"),
                   ("abb", "GE"), ("watts", "Watts"), ("york", "York")]


def test_record_for_is_the_makers_own_held_record_or_none():
    assert V.record_for("square-d", "panelboard") == ("square-d", "nq-nf-iline-panelboards")
    assert V.record_for("Schneider Electric", "panelboard") == ("square-d", "nq-nf-iline-panelboards")
    assert V.record_for("hps", "transformer_dry") == ("hps", "sentinel-g-transformers")
    assert V.record_for("siemens", "panelboard") is None          # named only
    assert V.record_for("trane", "panelboard") is None            # not a maker of the kind
    assert V.record_for("nobody-gmbh", "panelboard") is None      # unknown


@pytest.mark.parametrize("maker,kind,record,needles", [
    ("Square D", "panelboard", ("square-d", "nq-nf-iline-panelboards"),
     ["declared -> its own catalog record", "fact-tier fields"]),
    ("Siemens", "panelboard", None, ["known by name only", V.NOT_THAT_MAKER]),
    ("Trane", "panelboard", None, ["not as a maker of Panelboard", V.NOT_THAT_MAKER]),
    ("Nobody GmbH", "panelboard", None, ["not a maker the vendor directory knows", V.NOT_THAT_MAKER]),
    ("Eaton", "switchboard", None, ["house model", V.NOT_THAT_MAKER]),
])
def test_declared_says_one_honest_sentence_per_case(maker, kind, record, needles):
    d = V.declared(maker, kind)
    assert d["record"] == record and d["known"] == (maker != "Nobody GmbH")
    for n in needles:
        assert n in d["line"], d["line"]


def test_no_table_stores_a_number():
    # taxonomy and directory are words: no dimension, rating or price fields (steer #685)
    import typing
    for cls in (TX.Kind, V.Vendor, V.Line):
        hints = typing.get_type_hints(cls)
        assert not any(t in (int, float) for t in hints.values()), (cls, hints)


# --------------------------------------------------------------------------- the prompt grammar

def _nb(parsed):
    return {n["kind"]: n for n in parsed.coverage.not_built}


def test_a_control_panel_is_no_longer_read_as_a_panelboard():
    p = PP.parse_prompt("an electrical room with a fire alarm control panel, a lighting relay "
                        "panel and two lighting panels")
    assert [(it.kind, it.tag) for it in p.items] == [("lighting_panelboard", "LP-1"),
                                                     ("lighting_panelboard", "LP-2")]
    nb = _nb(p)
    assert set(nb) == {"fire_alarm_control_panel", "lighting_control_panel"}
    assert nb["fire_alarm_control_panel"]["revit_category"] == "Fire Alarm Devices"
    assert nb["lighting_control_panel"]["revit_category"] == "Electrical Equipment"
    assert p.coverage.ignored_words == []


def test_switchgear_still_builds_the_service_board():
    p = PP.parse_prompt("an electrical room with 2000 A switchgear and two panels")
    assert [it.kind for it in p.items].count("switchboard") == 1
    assert "switchgear" not in _nb(p)


def test_every_recognised_kind_carries_the_taxonomy_line_and_what_this_route_does():
    p = PP.parse_prompt("an electrical room 30 by 20 ft with a switchboard, twelve LED troffers, "
                        "a VAV box, two J-boxes, four light fixtures, a load center and two doors")
    nb = _nb(p)
    assert set(nb) == {"troffer", "vav_box", "junction_box", "luminaire", "panelboard", "door"}
    t = nb["troffer"]
    assert (t["label"], t["revit_category"], t["lane"], t["family_buildable_here"]) == \
        ("Recessed LED troffer", "Lighting Fixtures", "catalog", True)
    assert t["reason"].startswith(TX.describe("troffer")["line"]) and "prompt -> rfa" in t["reason"]
    v = nb["vav_box"]
    assert v["family_buildable_here"] is False and "no lane builds it yet" in v["reason"]
    assert v["revit_category"] == "Mechanical Equipment" and "NOT modelled" in v["reason"]
    g = nb["luminaire"]
    assert g["generic"] is True and "name the type" in g["reason"]
    lc = nb["panelboard"]                                    # a modelled kind, unparsed phrasing
    assert lc["text"] == "load center" and "DOES model it, as 'panelboard'" in lc["reason"]
    assert nb["door"]["reason"].startswith("recognised, NOT modelled")
    assert "label" not in nb["door"]                        # context word, not a taxonomy row
    assert p.coverage.ignored_words == []


def test_nothing_buildable_relays_the_taxonomy_line_in_the_error():
    with pytest.raises(PP.PromptError) as ei:
        PP.parse_prompt("create a cable tray family by Eaton")
    msg = str(ei.value)
    assert "Recognised, NOT built by this route: 'cable tray' -> " in msg
    assert TX.describe("cable tray")["line"] in msg and "Makers named: Eaton." in msg
    with pytest.raises(PP.PromptError) as ei:
        PP.parse_prompt("please make me something nice")
    assert "No other equipment kind was recognised either" in str(ei.value)


def test_grammar_kinds_are_taxonomy_rows_and_scene_kinds_invert_them():
    for kind, _prefix, _pat in PP._KIND_PATTERNS:
        assert TX.for_intent_kind(kind) is not None, kind
    assert TX.for_intent_kind("lighting_panelboard").key == "panelboard"
    assert TX.for_intent_kind("wall") is None
    assert PP._SCENE_KIND["switchgear"] == "switchboard" and PP._SCENE_KIND["panelboard"] == "panelboard"
    assert set(PP._SCENE_KIND.values()) <= {k for k, _p, _r in PP._KIND_PATTERNS}


def _makers(parsed):
    return [(u["clause"], tuple(u["tags"]), u["record"]) for u in parsed.coverage.understood
            if u["as"] == "manufacturer"]


def test_a_maker_named_in_a_clause_rides_that_item_as_declared_identity():
    p = PP.parse_prompt("an electrical room with two Square D lighting panels, an Eaton 75 kVA "
                        "transformer and 4 receptacles")
    assert [(it.tag, it.manufacturer) for it in p.items] == [
        ("LP-1", "Square D"), ("LP-2", "Square D"), ("T1", "Eaton"),
        ("R-1", None), ("R-2", None), ("R-3", None), ("R-4", None)]
    assert _makers(p) == [("Square D", ("LP-1", "LP-2"), "square-d/nq-nf-iline-panelboards"),
                          ("Eaton", ("T1",), "eaton/dry-type-transformers")]
    assert p.coverage.warnings == [] and p.coverage.ignored_words == []
    assert PP._contract_for(p.items[0])["Manufacturer"] == "Square D"
    assert PP._contract_for(p.items[2])["Manufacturer"] == "Eaton"
    model, _parsed = PP.prompt_to_intent("an electrical room with two Square D lighting panels "
                                         "and 4 receptacles")
    decl = {e.tag: e.contract.get("Manufacturer") for e in model.equipment}
    assert decl == {"LP-1": "Square D", "LP-2": "Square D", "R-1": None, "R-2": None,
                    "R-3": None, "R-4": None}


def test_one_maker_outside_every_clause_applies_to_all_two_apply_to_none():
    p = PP.parse_prompt("an electrical room with 4 panels and a 75 kVA transformer, all gear by Eaton")
    assert {it.manufacturer for it in p.items} == {"Eaton"}
    assert all("scope" in u for u in p.coverage.understood if u["as"] == "manufacturer")
    q = PP.parse_prompt("an electrical room with 4 panels; Eaton or Siemens")
    assert {it.manufacturer for it in q.items} == {None}
    assert any("named outside any equipment clause" in w for w in q.coverage.warnings)
    assert q.coverage.ignored_words == []                 # the names are consumed, not 'ignored'


def test_a_named_maker_with_no_record_is_said_not_substituted_silently():
    p = PP.parse_prompt("an electrical room with 3 Siemens panels and two Leviton receptacles")
    assert _makers(p) == [("Siemens", ("PP-1", "PP-2", "PP-3"), None),
                          ("Leviton", ("R-1", "R-2"), None)]
    w = " ".join(p.coverage.warnings)
    assert "PP-1, PP-2, PP-3: Siemens for panelboard: known by name only" in w
    assert "R-1, R-2: Leviton for receptacle: known by name only" in w
    assert w.count(V.NOT_THAT_MAKER) == 2


# --------------------------------------------------------------------------- the plan resolver

def _plans(prompt):
    model, parsed = PP.prompt_to_intent(prompt)
    return {fp.tag: fp for fp in model.family_plans}, model, parsed


def test_the_plan_reads_the_declared_makers_own_record_when_held():
    plans, _m, _p = _plans("an electrical room with a Square D 225 A lighting panel 42 spaces "
                           "208Y/120 V and a Hammond 75 kVA transformer")
    lp, t1 = plans["LP-1"], plans["T1"]
    assert (lp.status, lp.catalog, lp.variant) == ("resolved", "square-d/nq-nf-iline-panelboards", "NQ")
    assert lp.kwargs["vendor"] == "square-d" and lp.facts_summary["manufacturer"] == "Schneider Electric"
    assert (t1.status, t1.catalog) == ("resolved", "hps/sentinel-g-transformers")
    assert any("declared -> its own catalog record" in n for n in lp.notes + t1.notes)


def test_a_member_the_makers_record_refuses_falls_back_loudly_and_is_delivered():
    # HPS holds no 45 kVA member; NF has no sizing table at 480Y/277: both fall back to the
    # default record, keep the refusal verbatim, and carry the substitution phrase
    plans, model, _p = _plans("an electrical room with a Hammond 45 kVA transformer and a "
                              "Square D 400 A distribution panel 480Y/277 V")
    for tag, cat in (("T1", "eaton/dry-type-transformers"), ("DP-1", "eaton/pow-r-line-panelboards")):
        fp = plans[tag]
        assert fp.status == "resolved" and fp.catalog == cat and fp.refusal is None
        note = next(n for n in fp.notes if "REFUSED this member" in n)
        assert V.NOT_THAT_MAKER in note and "FactoryError" in note
    from rvt.frontdoor import intent as FI, manifest as MF
    degr = MF.plan_note_degradations(FI.summarize(model))
    assert {d.split(":")[0] for d in degr} == {"T1", "DP-1"}


def test_named_only_and_unknown_makers_build_from_the_default_and_say_so():
    plans, model, _p = _plans("an electrical room with a Siemens panel, a Trane panel and an "
                              "Eaton 2000 A switchboard")
    assert plans["PP-1"].catalog == plans["PP-2"].catalog == "eaton/pow-r-line-panelboards"
    assert any("known by name only" in n and V.NOT_THAT_MAKER in n for n in plans["PP-1"].notes)
    assert any("not as a maker of Panelboard" in n for n in plans["PP-2"].notes)
    msb = plans["MSB"]
    assert msb.status == "house" and msb.kwargs["manufacturer"] == "Eaton"
    assert any("house model" in n and V.NOT_THAT_MAKER in n for n in msb.notes)


def test_declared_maker_on_a_hand_built_contract_never_raises():
    from rvt.ifc import intent as I
    assert I.declared_maker({}, "panelboard") == (None, None)
    assert I.declared_maker({"Manufacturer": "unspecified"}, "panelboard") == (None, None)
    rec, note = I.declared_maker({"Manufacturer": "Cutler-Hammer"}, "panelboard")
    assert rec == ("eaton", "pow-r-line-panelboards") and "Eaton declared" in note
    rec, note = I.declared_maker({"Manufacturer": object()}, "panelboard")
    assert rec is None and note                       # junk in the cell: a sentence, not a raise


def test_route_run_relays_the_line_for_a_kind_it_cannot_build(tmp_path):
    from rvt.frontdoor import router as R
    res = R.route({"prompt": "create a VAV box family"}, "rfa", out=str(tmp_path / "o"), quiet=True)
    assert res.ok is False
    assert "VAV terminal unit: Mechanical Equipment; NOT buildable here" in res.status
    assert "no lane builds it yet" in res.status
