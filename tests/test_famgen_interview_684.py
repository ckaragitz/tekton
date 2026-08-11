"""``rvt.famgen.interview`` -- the question engine (#684, steer S-2026-08-11-b,
with #685 / #687's correction that the PROMPT is the interface and questions are
only the residue it leaves).

The suite is organised around the three ways this kind of feature is known to go
wrong, because a sibling PR (#674) spent six review rounds on exactly them:

* **the file is withheld.** Hard rule 1 says the deliverable always ships. So
  every prefix of every question set -- zero answers included -- must resolve to
  a famspec the contract accepts, an answer set that contradicts itself must
  still deliver, and one real ``.rfa`` is written from a plan nobody answered.
* **a choice is offered that the engine cannot build.** Eaton's 500 kVA row is
  in the catalog and publishes no dimensions; HPS publishes 30 and 75 kVA and
  nothing else. Neither may appear on a list a user picks from, and what was
  held back is named rather than hidden.
* **the text claims behaviour the code does not have.** Absent sources are
  reported absent, an unbuildable kind says so plainly instead of interviewing,
  every default that gets used carries a basis, and no question's sentence lists
  a choice the question does not offer.

Registry-derived throughout: the vendor list, the rating rows and the schedule
parameters are recomputed here from ``catalog`` / ``factory`` / ``standards``
and compared, so a test fails if the engine ever starts carrying its own copy.
Pure Python + the shipped facts store: no samples, no bases, fresh-clone safe.
"""
from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from rvt.famgen import catalog as C
from rvt.famgen import factory as F
from rvt.famgen import interview as IV
from rvt.famgen import standards as S
from rvt.frontdoor import famspec as FS

REPO = Path(__file__).resolve().parents[1]
KINDS = IV.kinds()


# ---------------------------------------------------------------------------
# the engine has something to interview for at all
# ---------------------------------------------------------------------------

def test_the_engine_has_a_question_set_for_every_catalog_kind_it_can_build():
    # derived, not asserted against a literal list: every famspec catalog kind
    # whose facts resolver accepts the constructor's own defaults
    expect = {b.kind for b in IV.BINDINGS
              if IV._deliverable(b.kind, {}) is None}
    assert set(KINDS) >= expect and expect, KINDS


def test_check_registry_is_clean():
    """The engine's own audit: zero-answer famspecs valid, no undeliverable
    choice offered, no duplicate keys, every default carries a basis."""
    assert IV.check_registry() == []


def test_ordering_is_most_decisive_first():
    for kind in KINDS:
        ranks = [q.rank for q in IV.plan(kind=kind).questions]
        assert ranks == sorted(ranks), (kind, ranks)


def test_rank_bands_all_have_a_meaning():
    for kind in KINDS:
        for q in IV.plan(kind=kind).questions:
            assert IV.RANKS.get(q.rank), (kind, q.key, q.rank)


# ---------------------------------------------------------------------------
# (b) HARD RULE 1 -- the question loop never withholds the file
# ---------------------------------------------------------------------------

def test_zero_answers_resolve_to_a_valid_famspec():
    for kind in KINDS:
        r = IV.resolve(IV.plan(kind=kind))
        assert FS.validate(r.famspec) == [], (kind, r.famspec)


def test_stopping_after_every_prefix_still_resolves():
    """Answer the first k questions, for every k, and stop. Each stop must
    produce a buildable famspec and name exactly what it assumed."""
    for kind in KINDS:
        base = IV.plan(kind=kind)
        for k in range(len(base.questions) + 1):
            answers = {}
            p = IV.plan(kind=kind)
            for q in p.questions[:k]:
                if str(q.key).startswith("std:"):
                    continue
                answers[q.key] = q.choices[0].value if q.choices else q.default
            answers = {a: v for a, v in answers.items() if v is not None}
            p = IV.plan(kind=kind, answers=answers)
            r = IV.resolve(p)
            assert FS.validate(r.famspec) == [], (kind, k, r.famspec)
            # every remaining question either was assumed or is honestly blank
            for q in p.questions:
                if q.key in r.assumed:
                    continue
                assert q.default is None, (kind, k, q.key)


def test_an_unanswered_plan_names_every_assumption():
    p = IV.plan(kind="transformer")
    r = IV.resolve(p)
    assert r.assumed, "a plan with no answers assumed nothing?"
    for key in r.assumed:
        a = r.values[key]
        assert a.tier in IV.TIERS and a.basis, (key, a)
    assert "ASSUMED" in r.say()


def test_resolve_never_raises_for_an_unanswered_question():
    for kind in KINDS:
        p = IV.plan(kind=kind)
        assert p.questions, kind
        IV.resolve(p)                       # must not raise


def test_a_plan_nobody_answered_writes_a_real_rfa(tmp_path):
    """The end of the loop is a FILE, not a prompt for more answers."""
    p = IV.plan(prompt="a transformer")
    r = IV.resolve(p)
    kind, kw, _ropts = FS.normalise(r.famspec)
    prod = FS.build(kind, kw)
    out = tmp_path / "unanswered.rfa"
    FS.write(prod, str(out))
    assert out.is_file() and out.stat().st_size > 0
    assert r.assumed and "vendor" in r.assumed and "kva" in r.assumed


def test_contradictory_answers_still_deliver_and_say_so():
    """HPS publishes 30 and 75 kVA. ``vendor=hps`` and ``kva=225`` are each
    deliverable and jointly impossible -- which is a caveat, not a refusal."""
    p = IV.plan(kind="transformer", answers={"vendor": "hps", "kva": 225})
    assert p.conflicts, "a jointly impossible answer set produced no conflict"
    c = p.conflicts[0]
    assert c["key"] == "kva" and c["asked"] == 225
    assert c["used"] in (30.0, 75.0)
    assert "225" in p.conflict_line() and str(c["used"]) in p.conflict_line()
    r = IV.resolve(p)
    assert FS.validate(r.famspec) == []
    assert r.famspec["vendor"] == "hps"          # the DECISIVE answer is kept
    FS.build(*FS.normalise(r.famspec)[:2])        # and it really builds


def test_the_least_decisive_answer_is_the_one_that_yields():
    p = IV.plan(kind="transformer", answers={"vendor": "hps", "kva": 225})
    assert p.answers["vendor"].value == "hps"
    assert p.answers["vendor"].tier == IV.GIVEN
    assert p.answers["kva"].tier == IV.NOMINAL   # it was not given, it was chosen for you
    assert "225" in p.answers["kva"].basis


def test_no_conflict_means_no_conflict_line():
    p = IV.plan(kind="transformer", answers={"vendor": "hps", "kva": 30})
    assert p.conflicts == () and p.conflict_line() == ""


# ---------------------------------------------------------------------------
# (c) ONLY CHOICES THE ENGINE CAN ACTUALLY DELIVER
# ---------------------------------------------------------------------------

def test_every_offered_choice_is_deliverable():
    for kind in KINDS:
        p = IV.plan(kind=kind)
        for q in p.questions:
            if q.slot or not q.choices:
                continue
            for c in q.choices:
                if c.source != "catalog":
                    continue
                why = IV._deliverable(kind, {q.key: c.value})
                assert why is None, (kind, q.key, c.value, why)


def test_eaton_500_kva_is_never_offered_and_is_named():
    """The catalog HAS the row; it publishes no dimensions ('Contact Eaton
    representative'), so the factory refuses it -- and so must the question."""
    variant = C.get_variant("eaton", "dry-type-transformers", kva=500)
    assert variant["dims_in"]["w"] is None       # the fixture is still the fixture
    q = IV.plan(kind="transformer", answers={"vendor": "eaton"}).question("kva")
    assert q is not None
    assert 500.0 not in [c.value for c in q.choices]
    held = {w["value"]: w["why"] for w in q.withheld}
    assert 500.0 in held and "NOT SOURCED" in held[500.0]


def test_kva_choices_are_exactly_the_deliverable_published_rows():
    for vendor, line in F._XFMR_LINES.items():
        expect = sorted(
            float(v["ratings"]["kva"])
            for v in C.load_line(*line)["variants"]
            if F is not None
            and IV._deliverable("transformer",
                                {"vendor": vendor,
                                 "kva": float(v["ratings"]["kva"])}) is None)
        q = IV.plan(kind="transformer", answers={"vendor": vendor}).question("kva")
        assert sorted(c.value for c in q.choices) == expect, vendor
        assert expect, vendor


def test_hps_offers_only_what_hps_publishes():
    q = IV.plan(kind="transformer", answers={"vendor": "hps"}).question("kva")
    assert sorted(c.value for c in q.choices) == [30.0, 75.0]


def test_answering_a_vendor_reshapes_the_next_questions():
    eaton = IV.plan(kind="transformer", answers={"vendor": "eaton"}).question("kva")
    hps = IV.plan(kind="transformer", answers={"vendor": "hps"}).question("kva")
    assert [c.value for c in eaton.choices] != [c.value for c in hps.choices]


def test_a_later_answer_can_bring_a_withheld_vendor_back():
    """Square D's panelboards are refused at the default 480Y/277 (the record
    carries no circuits->height table for NF) and accepted at 240 -- so the
    vendor question must be recomputed from the answers, not fixed."""
    default = IV.plan(kind="panelboard")
    vq = default.question("vendor")
    if vq is None:                               # auto-filled: one deliverable
        assert "square-d" in default.answers["vendor"].basis
    else:
        assert "square-d" in {w["value"] for w in vq.withheld}
    at240 = IV.plan(kind="panelboard", answers={"voltage": "240"})
    q = at240.question("vendor")
    assert q is not None and {c.value for c in q.choices} >= {"eaton", "square-d"}


def test_choices_collapse_to_one_per_deliverable_record():
    """``_PANEL_LINES`` spells one Eaton record three ways. Asking a user to
    choose between three names for the same file is not a question."""
    aliases = {ln for vn, ln in F._PANEL_LINES if vn == "eaton"}
    assert len(aliases) >= 3
    p = IV.plan(kind="panelboard", answers={"vendor": "eaton"})
    q = p.question("line")
    offered = [c.value for c in q.choices] if q else [p.answers["line"].value]
    assert len(offered) == 1, offered
    assert offered[0] in aliases


def test_a_choice_the_engine_refuses_is_withheld_not_hidden():
    """Nothing is dropped silently: whatever a source names and the engine
    cannot build is on ``withheld`` with the constructor's own words."""
    q = IV.plan(kind="transformer", answers={"vendor": "eaton"}).question("kva")
    published = {float(v["ratings"]["kva"])
                 for v in C.load_line("eaton", "dry-type-transformers")["variants"]}
    accounted = {c.value for c in q.choices} | {w["value"] for w in q.withheld}
    assert published <= accounted
    for w in q.withheld:
        assert w["why"], w


# ---------------------------------------------------------------------------
# (a) THE TEXT MATCHES THE CODE
# ---------------------------------------------------------------------------

def test_absent_sources_are_reported_absent_and_never_claimed():
    st = IV.source_status()
    names = {r["source"] for r in st["sources"]}
    assert names == {s.name for s in IV.SOURCES}
    for row in st["sources"]:
        assert row["available"] is (IV.load_source(row["source"]) is not None)
    for absent in st["absent"]:
        assert absent in st["note"]
        # nothing derived claims to have come from a source that is not there
        for kind in KINDS:
            for q in IV.plan(kind=kind).questions:
                assert q.source != absent, (kind, q.key, absent)


def test_a_plan_carries_the_source_status_it_was_built_with():
    p = IV.plan(kind="transformer")
    assert p.sources["available"] and "note" in p.sources
    assert p.note == p.sources["note"]
    assert IV.resolve(p).sources == p.sources


def test_a_restricted_source_list_really_restricts():
    p = IV.plan(kind="transformer", sources=["catalog"])
    assert [q for q in p.questions if q.source == "standards"] == []
    assert not any(str(q.key).startswith("std:") for q in p.questions)
    assert FS.validate(IV.resolve(p).famspec) == []


def test_load_source_refuses_an_unknown_name_by_name():
    with pytest.raises(IV.InterviewError) as e:
        IV.load_source("no-such-registry")
    assert "no-such-registry" in str(e.value)


def test_a_kind_with_no_question_set_says_so_plainly():
    """DONE (6). ``generic_model`` is a real famspec kind whose geometry the
    caller supplies -- no series of questions ends in a file, and the engine
    says that instead of interviewing."""
    p = IV.plan(kind="generic_model")
    assert p.covered is False
    assert p.questions == ()
    assert "generic_model" in p.note and "no question set" in p.note.lower()
    for k in KINDS:
        assert k in p.note                       # it names what it CAN do
    assert p.say() == p.note
    with pytest.raises(IV.InterviewError):
        IV.resolve(p)                            # no famspec is invented


def test_an_unknown_word_gets_the_same_plain_answer():
    p = IV.plan(kind="ductwork")
    assert p.covered is False and p.questions == ()
    assert "ductwork" in p.note


def test_a_prompt_naming_nothing_asks_which_product():
    p = IV.plan(prompt="build me something nice")
    assert p.kind is None
    assert [q.key for q in p.questions] == ["kind"]
    assert {c.value for c in p.questions[0].choices} == set(KINDS)


def test_every_default_that_is_used_carries_a_basis_and_a_tier():
    for kind in KINDS:
        r = IV.resolve(IV.plan(kind=kind))
        for key, a in r.values.items():
            assert a.tier in IV.TIERS, (kind, key, a.tier)
            assert IV.TIER_MEANING[a.tier]
            if a.tier != IV.BLANK:
                assert a.basis, (kind, key)


def test_a_question_sentence_lists_exactly_the_choices_it_offers():
    for kind in KINDS:
        for q in IV.plan(kind=kind).questions:
            for c in q.choices:
                assert str(c.label) in q.ask, (kind, q.key, c.label)
            for w in q.withheld:                 # never advertised as pickable
                assert f" {w['value']}," not in q.ask and not q.ask.endswith(
                    f" {w['value']}."), (kind, q.key, w)


def test_the_unbuildable_categories_report_names_only_unbuildable_ones():
    for row in IV.unbuildable_categories():
        assert row["category"] not in KINDS
        assert _constructorless(row["category"])
        assert row["records"] and row["why"]


def _constructorless(category: str) -> bool:
    return getattr(F, f"make_{category}", None) is None


# ---------------------------------------------------------------------------
# the questions are DERIVED, not written per product
# ---------------------------------------------------------------------------

def test_every_question_binds_to_a_real_constructor_argument():
    for kind in KINDS:
        ctor = IV._constructor(kind)
        if ctor is None:                         # an archetype product
            continue
        accepted = set(inspect.signature(ctor).parameters)
        for q in IV.plan(kind=kind).questions:
            if q.slot:                           # standard_values / dimensions
                continue
            assert q.kwarg in accepted, (kind, q.key, q.kwarg)


def test_no_plumbing_argument_is_ever_asked():
    for kind in KINDS:
        keys = {q.key for q in IV.plan(kind=kind).questions} | set(
            IV.plan(kind=kind).answers)
        assert keys.isdisjoint(set(IV._NOT_A_QUESTION)), kind


def test_the_vendor_list_is_the_catalogs_own_vendors():
    """Adding a vendor record adds its choice with no edit to this module: the
    offer is exactly (the factory's vendor map) intersect (deliverable)."""
    expect = sorted(v for v in F._XFMR_LINES
                    if IV._deliverable("transformer", {"vendor": v}) is None)
    q = IV.plan(kind="transformer").question("vendor")
    assert [c.value for c in q.choices] == expect
    assert len(expect) > 1                       # DONE (2): more than one -> a question


def test_vendor_and_line_are_first_class_where_the_catalog_holds_several():
    q = IV.plan(kind="transformer").question("vendor")
    assert q is not None and q.rank == IV.RANK_VENDOR and q.decisive
    lq = IV.plan(kind="luminaire").question("fixture")
    assert lq is not None and lq.rank == IV.RANK_LINE and len(lq.choices) > 1


def test_one_deliverable_choice_is_filled_not_asked():
    """A question with a single answer is not a decision -- but the engine says
    where the value came from and what it held back."""
    p = IV.plan(kind="panelboard")
    a = p.answers.get("vendor")
    assert a is not None and p.question("vendor") is None
    assert a.tier == IV.FACT and a.source == "catalog"
    assert "the only value this engine can deliver" in a.basis


def test_the_line_question_uses_the_famspec_spelling_not_the_constructors():
    """``make_luminaire``'s selector is ``kind``; the famspec spells it
    ``fixture`` because ``kind`` selects the constructor. An answer must never
    have to be renamed by the caller."""
    q = IV.plan(kind="luminaire").question("fixture")
    assert q.key == FS.OWN_KIND_FIELD["luminaire"] == "fixture"
    assert q.kwarg == "kind"
    spec = IV.resolve(IV.plan(kind="luminaire", answers={"fixture": "downlight"})).famspec
    assert spec["fixture"] == "downlight" and FS.validate(spec) == []


def test_schedule_questions_come_from_the_standards_table():
    for b in IV.BINDINGS:
        if b.kind not in KINDS or not b.std_category:
            continue
        named = {p.name for p in S.authored_params(b.std_category)}
        plan = IV.plan(kind=b.kind)
        asked = [q for q in plan.questions if str(q.key).startswith("std:")]
        assert asked, b.kind
        for q in asked:
            assert q.param in named, (b.kind, q.param)
            assert q.rank == IV.RANK_SCHEDULE and not q.decisive
            assert q.default is None and q.default_tier == IV.BLANK
            assert q.slot == "standard_values"


def test_a_schedule_question_is_not_asked_twice_under_two_spellings():
    """#622's law: one meaning, one entry. A constructor argument that already
    fills a standard parameter must not reappear as a schedule question."""
    for b in IV.BINDINGS:
        if b.kind not in KINDS or not b.std_category:
            continue
        p = IV.plan(kind=b.kind)
        ctor_keys = {S.meaning_key(q.key.replace("_", " "))
                     for q in p.questions if not q.slot}
        for q in p.questions:
            if q.slot == "standard_values":
                assert S.meaning_key(q.param) not in ctor_keys, (b.kind, q.param)


def test_an_answered_schedule_question_reaches_the_famspec():
    p = IV.plan(kind="transformer", answers={"std:Enclosure Rating": "NEMA 3R"})
    r = IV.resolve(p)
    assert r.famspec["standard_values"]["Enclosure Rating"] == "NEMA 3R"
    assert FS.validate(r.famspec) == []
    assert r.values["std:Enclosure Rating"].tier == IV.GIVEN


def test_affects_names_the_standard_parameter_when_the_two_line_up():
    """The link back to source 3: where a constructor argument and a standard
    parameter are the same quantity by MEANING, ``affects`` says which
    parameter and which group the answer lands in."""
    q = IV.plan(kind="panelboard").question("voltage")
    assert "'Voltage' family parameter" in q.affects and "electrical" in q.affects
    q2 = IV.plan(kind="luminaire").question("cct")
    assert "Initial Color Temperature" in q2.affects, q2.affects


def test_affects_does_not_invent_a_parameter_that_is_not_in_the_table():
    """``kVA Rating`` is a parameter ``make_transformer`` authors itself, not a
    row of the Electrical Equipment standards table -- so ``affects`` must name
    the constructor argument rather than a table entry that does not exist."""
    assert "kVA Rating" not in {p.name for p in S.authored_params("electrical_equipment")}
    q = IV.plan(kind="transformer").question("kva")
    assert q.affects == "the constructor's kva argument"


# ---------------------------------------------------------------------------
# the PROMPT is the interface (#685 / #687)
# ---------------------------------------------------------------------------

def test_a_descriptive_prompt_leaves_no_decisive_residue():
    p = IV.plan(prompt="a 75 kVA eaton transformer")
    assert p.kind == "transformer"
    assert p.enough is True
    assert [q.key for q in p.questions if q.decisive] == []
    assert p.answers["kva"].value == 75.0 and p.answers["kva"].tier == IV.GIVEN
    assert p.answers["vendor"].value == "eaton"


def test_a_broad_prompt_asks_the_decisive_things_first():
    p = IV.plan(prompt="a transformer")
    assert p.enough is False
    decisive = [q.key for q in p.questions if q.decisive]
    assert decisive[:2] == ["vendor", "kva"]


def test_the_prompt_answer_is_quoted_back():
    p = IV.plan(prompt="a 30 kVA hps transformer")
    assert p.answers["kva"].quoted.lower().replace(" ", "") == "30kva"
    assert p.answers["kva"].source == "prompt"
    assert p.answers["vendor"].quoted.lower() == "hps"


@pytest.mark.parametrize("prompt,key", [
    ("an IP65 transformer", "kva"),           # digits inside a token
    ("a V48M28T7516 transformer", "kva"),     # a catalog model number
    ("a 480Y/277 panelboard", "mains_a"),     # a voltage is not an ampacity
])
def test_a_number_inside_a_token_is_never_read_as_a_dimension(prompt, key):
    p = IV.plan(prompt=prompt)
    a = p.answers.get(key)
    assert a is None or a.source != "prompt", (prompt, key, a)


def test_a_number_with_its_unit_is_read():
    assert IV.plan(prompt="a 400 amp panelboard").answers["mains_a"].value == 400.0
    assert IV.plan(prompt="a 42 circuit panelboard").answers["spaces"].value == 42.0


def test_one_measurement_answers_one_question():
    """The bug this rule exists for: a single "24 inch" was bound to every
    question whose key ends in ``_in``, so eight dimensions were reported as
    'you said so' off three words the caller wrote once."""
    p = IV.plan(prompt="a duplex receptacle at 18 in")
    from_prompt = [k for k, a in p.answers.items() if a.source == "prompt"
                   and a.quoted.replace(" ", "").lower() == "18in"]
    assert from_prompt == ["mounting_height_in"], from_prompt


def test_the_generic_reader_binds_a_bare_measurement_to_one_key_only():
    """Directly on the reader, so the law holds for any registry that grows a
    second question sharing a unit."""
    qs = [IV.Question(key="width_in", ask="", rank=IV.RANK_SELECTOR,
                      source="t", default=12.0, words=("width", "wide")),
          IV.Question(key="depth_in", ask="", rank=IV.RANK_SIZED,
                      source="t", default=4.0, words=("depth", "deep")),
          IV.Question(key="rung_thickness_in", ask="", rank=IV.RANK_OPEN,
                      source="t", default=0.1, words=("rung thickness",))]
    read = IV._read_prompt("a 24 inch tray", qs)
    assert list(read) == ["width_in"] and read["width_in"][0] == 24.0
    both = IV._read_prompt("a 24 in wide tray 6 in deep", qs)
    assert both["width_in"][0] == 24.0 and both["depth_in"][0] == 6.0
    assert "rung_thickness_in" not in both


def test_the_kind_is_read_from_the_registries_vocabulary():
    assert IV.plan(prompt="make me a duplex receptacle").kind == "device"
    assert IV.plan(prompt="a recessed troffer for the office").kind == "luminaire"
    assert IV.plan(prompt="a panelboard").kind == "panelboard"


def test_an_explicit_kind_beats_the_prompt():
    p = IV.plan(prompt="a transformer", kind="panelboard")
    assert p.kind == "panelboard"


# ---------------------------------------------------------------------------
# the conversational flow (DONE 5)
# ---------------------------------------------------------------------------

def test_next_hands_back_a_few_at_a_time_from_the_head():
    p = IV.plan(prompt="a transformer")
    assert list(p.next(3)) == list(p.questions[:3])
    assert len(p.next(2)) == 2
    assert p.next(0) == ()


def test_answering_the_decisive_questions_flips_enough():
    p = IV.plan(prompt="a transformer")
    assert not p.enough
    p = IV.answer(p, vendor="eaton")
    p = IV.answer(p, kva=300)
    assert p.enough is True
    assert IV.resolve(p).famspec["kva"] == 300


def test_answer_keeps_what_was_already_given():
    p = IV.answer(IV.plan(prompt="a transformer"), vendor="hps")
    p = IV.answer(p, kva=30)
    assert p.answers["vendor"].value == "hps" and p.answers["kva"].value == 30


def test_answer_refuses_an_unknown_key_by_name():
    p = IV.plan(prompt="a transformer")
    with pytest.raises(IV.InterviewError) as e:
        IV.answer(p, nonsense=1)
    assert "nonsense" in str(e.value)


def test_say_tells_the_user_they_can_stop():
    p = IV.plan(prompt="a transformer")
    assert "stop any time" in p.say()


def test_plan_and_resolution_are_json_serialisable():
    p = IV.plan(prompt="a transformer", answers={"vendor": "hps", "kva": 225})
    json.dumps(p.to_json(), default=str)
    json.dumps(IV.resolve(p).to_json(), default=str)
    assert IV.resolve(p).by_tier()[IV.GIVEN]


# ---------------------------------------------------------------------------
# the archetype source, only when it is present (PR #674 is unmerged)
# ---------------------------------------------------------------------------

def test_the_archetype_source_degrades_without_being_imported():
    """The whole engine must work on a checkout where #674 has not landed --
    which is this one until it merges."""
    st = IV.source_status(["archetypes"])
    row = st["sources"][0]
    assert row["module"] == "rvt.famgen.archetypes"
    if not row["available"]:
        assert "archetypes" in st["absent"]
        assert KINDS and IV.check_registry() == []


def test_archetype_kinds_get_their_questions_from_the_archetype_registry():
    arch = IV.load_source("archetypes")
    if arch is None:
        pytest.skip("rvt.famgen.archetypes is not on this checkout (PR #674)")
    for key in arch.keys():
        p = IV.plan(kind=key)
        assert p.covered, key
        params = {x.key for x in arch.archetype(key).params}
        asked = {q.key for q in p.questions if not str(q.key).startswith("std:")}
        assert asked <= params, (key, asked - params)
        for q in p.questions:
            if q.key in params:
                assert q.default_tier == IV.NOMINAL and q.source == "archetypes"
        r = IV.resolve(p)
        assert r.famspec["kind"] == "archetype" and r.famspec["product"] == key
        assert FS.validate(r.famspec) == []


def test_an_archetype_reads_its_own_prompt():
    """The registry's own resolver is the reader for its own products: one
    "24 inch" is the tray's WIDTH and nothing else's."""
    arch = IV.load_source("archetypes")
    if arch is None:
        pytest.skip("rvt.famgen.archetypes is not on this checkout (PR #674)")
    p = IV.plan(prompt="a 24 inch cable tray 20 ft long")
    assert p.kind == "cable_tray"
    given = {k: a.value for k, a in p.answers.items() if a.source == "prompt"}
    assert given == {"width_in": 24.0, "length_ft": 20.0}, given
    r = IV.resolve(p)
    assert r.famspec["dimensions"]["width_in"] == 24.0
    assert r.values["depth_in"].tier == IV.NOMINAL      # NOT "you said 24"
    assert FS.validate(r.famspec) == []


# ---------------------------------------------------------------------------
# the CLI a skill session drives
# ---------------------------------------------------------------------------

def _cli(*args, expect=None):
    proc = subprocess.run([sys.executable, str(REPO / "tools" / "interview.py"), *args],
                          capture_output=True, text=True, cwd=str(REPO))
    if expect is not None:
        assert proc.returncode == expect, (args, proc.returncode, proc.stderr[-800:])
    return proc


def test_cli_ask_exit_codes_distinguish_enough_from_open():
    _cli("ask", "a 75 kVA eaton transformer", expect=0)
    _cli("ask", "a transformer", expect=2)
    _cli("ask", "--kind", "generic_model", expect=3)


def test_cli_ask_json_is_the_plan():
    out = _cli("ask", "a transformer", "--json", expect=2).stdout
    d = json.loads(out)
    assert d["kind"] == "transformer" and d["enough_to_build"] is False
    assert d["questions"][0]["key"] == "vendor"
    assert d["sources"]["available"]


def test_cli_build_writes_a_file_with_no_answers(tmp_path):
    out = tmp_path / "cli.rfa"
    proc = _cli("build", "a transformer", "-o", str(out), "--json", expect=0)
    d = json.loads(proc.stdout)
    assert Path(d["file"]).is_file()
    assert d["interview"]["assumed_answers"]


def test_cli_build_says_no_when_there_is_no_question_set(tmp_path):
    proc = _cli("build", "--kind", "generic_model", "-o", str(tmp_path / "x.rfa"),
                expect=3)
    assert "no question set" in proc.stderr.lower()
    assert not (tmp_path / "x.rfa").exists()


def test_cli_sources_lists_every_source():
    out = _cli("sources", "--json", expect=0).stdout
    assert {r["source"] for r in json.loads(out)["sources"]} == {
        s.name for s in IV.SOURCES}


def test_cli_kinds_matches_the_engine():
    out = _cli("kinds", "--json", expect=0).stdout
    assert json.loads(out)["kinds"] == list(KINDS)
