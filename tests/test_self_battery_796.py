"""#796: the exhaustive self-battery, and the conformance instrument it reads.

Fresh-clone safe: every family here is built from the tracked genesis bases;
the born corpus (samples/, quarantined) is never needed -- the conformance
instrument is exercised on a corpus of OUR OWN files, which is enough to prove
it reads each file in its own release, never mines a silent zero, and that the
battery's conformance path passes, fails and refuses to be inert as it says.

Every instrument is also shown FAILING here (a corrupted file, a doctored
invariant, a failing scan): an instrument that could only ever say "pass"
would make the whole battery a rubber stamp.
"""
import argparse
import dataclasses
import json
import os
import shutil
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import self_battery as SB                                      # noqa: E402
sys.path.pop(0)

from rvt.famgen import archetypes as AR                        # noqa: E402
from rvt.famgen import conformance as CO                       # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.frontdoor import release_ctx as RC                    # noqa: E402
from conftest import context_constants, ladder_constants       # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")
NATIVE = RC.native_release()


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs(tmp_path_factory):
    """The first write in a process seeds the native codec singletons
    (standalone.install_schema, by design): do it once before the guard's
    first snapshot, so only a swap a release context leaves behind is red."""
    F.make_archetype(product="wireway").write(
        str(tmp_path_factory.mktemp("warm") / "w.rfa"))


def _build(path, year=None, product="junction_box", **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if year is None or year == NATIVE:
        F.make_archetype(product=product, **kw).write(path, validate=False, provenance=False)
    else:
        base = RC._bundled_base_of(year)
        if not base:
            pytest.skip(f"no bundled Revit {year} base")
        with RC.release_build_context(base):
            F.make_archetype(product=product, **kw).write(path, validate=False,
                                                          provenance=False)
    return path


@pytest.fixture(scope="module")
def own_corpus(tmp_path_factory):
    """Five born-alike documents of OUR OWN (min_specimens = 5) + their oracle."""
    d = tmp_path_factory.mktemp("own_corpus")
    for i, w in enumerate((4, 6, 8, 12, 6)):
        _build(str(d / f"w{i}.rfa"), product="wireway", dimensions={"width_in": w})
    return str(d), CO.mine(str(d)).invariants()


@pytest.fixture(scope="module")
def ours(tmp_path_factory):
    """One native wireway at its nominal -- the file the instruments read."""
    return _build(str(tmp_path_factory.mktemp("ours") / "w.rfa"), product="wireway")


# -- the conformance instrument (the one src/ change) -------------------------

def test_mine_reads_rfa_and_rft_each_in_its_own_release_and_counts_failures(tmp_path):
    corpus = tmp_path / "corpus"
    a = _build(str(corpus / "a.rfa"))
    b = _build(str(corpus / "b.rfa"), 2025)
    shutil.copy(a, corpus / "c.rft")                      # a template is mined too
    (corpus / "d.rfa").write_bytes(b"not a compound file")
    (corpus / "e.txt").write_text("ignored")
    # control: read under the session's framing, the 2025 file does not open --
    # the defect that made the old miner report 0 files on the 2025 corpus
    from rvt.families import FamilyIndex
    with pytest.raises(Exception):
        FamilyIndex(b).unit_records(0)
    o = CO.mine(str(corpus))
    assert (o.attempted, o.files, o.failed) == (4, 3, 1)
    assert dict(o.releases) == {str(NATIVE): 2, "2025": 1}
    assert o.fallbacks == 0 and o.undecoded_records == 0 and o.partial_records == 0
    assert sum(o.failure_types.values()) == 1 and len(o.failures) == 1
    s = o.summary()
    assert "3/4" in s and "1 failed" in s and "partly decoded" in s and "undecoded" in s, s
    assert o.invariants(), "nothing derived from three real family documents"


def test_a_corpus_that_decodes_nothing_says_so(tmp_path):
    (tmp_path / "x.rfa").write_bytes(b"\0" * 512)
    o = CO.mine(str(tmp_path))
    assert (o.attempted, o.files, o.failed) == (1, 0, 1)
    assert o.summary().startswith("NOTHING MINED") and "0/1" in o.summary()


def test_partly_decoded_records_are_counted_and_left_out(tmp_path, monkeypatch, ours):
    """A record the decoder returns NOT clean is never observed as complete
    (corpus side) and makes the battery's conformance FAIL (our side)."""
    from rvt.objects import ObjectDecoder
    orig = ObjectDecoder.decode_record

    def dirty(self, class_id, payload):
        o = orig(self, class_id, payload)
        return dataclasses.replace(o, errors=["forced by the test"]) if o is not None else o
    clean = CO.mine(os.path.dirname(ours))
    monkeypatch.setattr(ObjectDecoder, "decode_record", dirty)
    o = CO.mine(os.path.dirname(ours))
    assert o.partial_records > 0 and not o.specimens, (o.partial_records, o.specimens)
    assert clean.specimens and clean.partial_records == 0
    assert "partly" in o.summary()
    st = {}
    CO.check_file(ours, clean.invariants(), stats=st)
    assert st["partial_records"] > 0
    st_, detail, extra = SB.Battery(str(tmp_path), invariants=clean.invariants()
                                    )._i_conformance(ours, NATIVE)
    assert st_ == "fail" and "partly" in detail and extra["partial_records"] > 0


def test_records_the_decoder_cannot_read_are_counted_and_fail_conformance(tmp_path, monkeypatch,
                                                                          ours):
    """The twin of the partial case: a record whose decode RAISES is counted
    (corpus side and check side), never silently dropped, and the battery's
    conformance FAILS on it (#1088 review)."""
    from rvt.objects import ObjectDecoder
    clean = CO.mine(os.path.dirname(ours))

    def boom(self, class_id, payload):
        raise ValueError("forced by the test")
    monkeypatch.setattr(ObjectDecoder, "decode_record", boom)
    o = CO.mine(os.path.dirname(ours))
    assert o.undecoded_records > 0 and not o.specimens
    assert "undecoded" in o.summary()
    st = {}
    CO.check_file(ours, clean.invariants(), stats=st)
    assert st["undecoded_records"] > 0
    st_, detail, extra = SB.Battery(str(tmp_path), invariants=clean.invariants()
                                    )._i_conformance(ours, NATIVE)
    assert st_ == "fail" and extra["undecoded_records"] > 0, detail


def test_a_file_of_ours_read_on_a_fallback_rung_fails_verify_and_conformance(tmp_path,
                                                                              monkeypatch, ours,
                                                                              own_corpus):
    """Our own output must name its release through its own schema: a fallback
    rung reading it is a FAIL, not a footnote (#1088 review)."""
    import rvt.global_framing as GF
    real = GF.enter_own_release

    def fallback(stack, path):
        real(stack, path)
        return "forced by the test: read on the pinned fallback table"
    monkeypatch.setattr(GF, "enter_own_release", fallback)
    bat = SB.Battery(str(tmp_path), invariants=own_corpus[1])
    st_v, d_v, _ = bat._i_verify(ours, NATIVE)
    st_c, d_c, _ = bat._i_conformance(ours, NATIVE)
    assert (st_v, st_c) == ("fail", "fail"), (d_v, d_c)
    assert "did not resolve its release" in d_v and "did not resolve its release" in d_c


def test_a_requested_class_with_no_specimens_is_named(own_corpus):
    o = CO.mine(own_corpus[0], classes=("ExtrusionElem", "NoSuchClassAnywhere"))
    assert o.classes_without_specimens() == ["NoSuchClassAnywhere"]
    assert "0 specimens of NoSuchClassAnywhere" in o.summary()
    back = CO.Oracle.from_json(json.loads(json.dumps(o.to_json())))
    assert back.classes_without_specimens() == ["NoSuchClassAnywhere"]


def test_the_oracle_cache_form_round_trips_and_carries_no_path(tmp_path):
    corpus = tmp_path / "corpus"
    _build(str(corpus / "a.rfa"))
    (corpus / "bad.rfa").write_bytes(b"junk")
    o = CO.mine(str(corpus))
    blob = json.dumps(o.to_json())
    assert str(tmp_path) not in blob and "bad.rfa" not in blob
    back = CO.Oracle.from_json(json.loads(blob))
    assert back.invariants() == o.invariants()
    assert (back.files, back.attempted, back.failed) == (o.files, o.attempted, o.failed)
    # a cache HIT must report exactly what a miss reports (#1088 review)
    assert back.summary() == o.summary()
    assert dict(back.releases) == dict(o.releases) and dict(back.releases)
    assert dict(back.failure_types) == dict(o.failure_types)
    assert sum(o.failure_types.values()) == o.failed == 1
    # the cache form is a snapshot: observing more afterwards does not change it
    d = o.to_json()
    before = json.dumps(d, sort_keys=True)
    o.observe("ExtrusionElem", {"m_new_field_after_snapshot": 1})
    assert json.dumps(d, sort_keys=True) == before


def test_check_file_reads_the_written_file_and_is_not_inert(tmp_path, own_corpus):
    _corpus, inv = own_corpus
    ours25 = _build(str(tmp_path / "ours" / "w.rfa"), 2025, product="wireway")
    st = {}
    found = CO.check_file(ours25, inv, stats=st)
    assert st["rules_evaluated"] > 100 and st["elements"] > 0, st
    assert st["release_note"] is None and st["partial_records"] == 0
    assert not [f for f in found if f["severity"] == "question"], found[:3]


# -- the battery's corpus path: load_oracle + the conformance instrument ------

def test_load_oracle_caches_by_corpus_bytes_and_decoder_source(tmp_path, monkeypatch,
                                                               own_corpus):
    corpus = str(tmp_path / "c")
    shutil.copytree(own_corpus[0], corpus)
    cache = str(tmp_path / "cache")
    inv1, b1 = SB.load_oracle(corpus, cache, explicit=True)
    inv2, b2 = SB.load_oracle(corpus, cache, explicit=True)
    assert (b1["state"], b1["cache"], b2["cache"]) == ("ok", "miss", "hit")
    assert inv1 == inv2 and b1["decoded"] == 5 and b1["failed"] == 0
    assert b1["partial_records"] == 0 and "classes_without_specimens" in b1
    assert corpus not in json.dumps(b1)                   # counts only, no path
    # same names, different bytes -> a different key -> mined again
    shutil.copy(os.path.join(corpus, "w3.rfa"), os.path.join(corpus, "w4.rfa"))
    _inv3, b3 = SB.load_oracle(corpus, cache, explicit=True)
    assert b3["cache"] == "miss" and b3["corpus_sha256"] != b1["corpus_sha256"]
    # a decoder change (any module of the rvt package) moves the key too
    paths = CO.corpus_paths(corpus)
    k = SB.corpus_sha(paths)
    assert len(SB.instrument_sha()) == 64
    monkeypatch.setattr(SB, "instrument_sha", lambda: "0" * 64)
    assert SB.corpus_sha(paths) != k


def test_a_corpus_that_mines_nothing_or_is_missing_fails_when_asked_for(tmp_path):
    junk = tmp_path / "junk"
    junk.mkdir()
    for i in range(3):
        (junk / f"j{i}.rfa").write_bytes(b"\0" * 1024)
    inv, blk = SB.load_oracle(str(junk), None, explicit=True)
    assert inv is None and blk["state"] == "fail" and blk["failed"] == 3
    # missing / empty: a FAIL when the caller named it, a skip at the default spot
    assert SB.load_oracle(str(tmp_path / "nope"), None, explicit=True)[1]["state"] == "fail"
    assert SB.load_oracle(str(tmp_path / "nope"), None)[1]["state"] == "skip"
    (tmp_path / "empty").mkdir()
    assert SB.load_oracle(str(tmp_path / "empty"), None, explicit=True)[1]["state"] == "fail"
    rc = SB.main(["--quick", "--only", "archetype:wireway@", "--no-twin",
                  "--corpus", str(junk), "--out", str(tmp_path / "o")])
    rep = json.loads((tmp_path / "o.json").read_text())
    assert rc == 1 and rep["corpus"]["state"] == "fail"


def test_the_conformance_instrument_passes_fails_and_refuses_to_be_inert(tmp_path, own_corpus,
                                                                         ours):
    _corpus, inv = own_corpus
    bat = SB.Battery(str(tmp_path), invariants=inv)
    st, detail, extra = bat._i_conformance(ours, NATIVE)
    assert st == "pass" and extra["rules_evaluated"] > 100, detail
    # a doctored CONSTANT the file carries -> a question -> FAIL
    _n, objs, _c = CO.iter_objects(ours, tuple(inv))
    have = {(c, f) for _e, c, o in objs for f in o}
    cls, fld = next((c, f) for c, rules in sorted(inv.items()) for f, r in sorted(rules.items())
                    if r["invariant"] == "CONSTANT" and r["specimens"] >= 5
                    and r["value"].startswith("int:") and (c, f) in have)
    bad = json.loads(json.dumps(inv))
    bad[cls][fld]["value"] = f"int:{int(inv[cls][fld]['value'][4:]) + 7919}"
    st, detail, extra = SB.Battery(str(tmp_path), invariants=bad)._i_conformance(ours, NATIVE)
    assert st == "fail" and f"{cls}.{fld}" in extra["question_fields"], detail
    # invariants that only name a class the file lacks -> 0 rules -> inert -> FAIL
    lone = {"NoSuchClassAnywhere": {"m_x": {"invariant": "CONSTANT", "value": 1,
                                           "specimens": 99}}}
    st, detail, _x = SB.Battery(str(tmp_path), invariants=lone)._i_conformance(ours, NATIVE)
    assert st == "fail" and detail.startswith("inert"), detail


# -- the read-back instruments can FAIL ----------------------------------------

def _corrupt(path, out, n=16):
    """XOR ``n`` bytes in the middle of Partitions/0 -- past the CRCIO ECC's
    repair envelope (a single flipped byte is repairable, and the validator
    rightly calls that a warning)."""
    import olefile
    data = open(path, "rb").read()
    ole = olefile.OleFileIO(path)
    try:
        s = ole.openstream("Partitions/0").read()
    finally:
        ole.close()
    win = s[len(s) // 2: len(s) // 2 + 48]
    off = data.find(win)
    assert off > 0 and data.count(win) == 1
    b = bytearray(data)
    b[off:off + n] = bytes(x ^ 0x5A for x in b[off:off + n])
    with open(out, "wb") as fh:
        fh.write(b)
    return out


def test_a_corrupted_file_fails_verify_and_validate(tmp_path, ours):
    bad = _corrupt(ours, str(tmp_path / "bad.rfa"))
    bat = SB.Battery(str(tmp_path))
    row = SB._new_row(SB.Case("pinned", "bad", {}), "pinned:bad@0")
    bat.instruments(row, bad, NATIVE)
    ins = row["instruments"]
    assert ins["verify"]["state"] == "fail", ins["verify"]
    assert ins["validate"]["state"] == "fail" and ins["validate"]["errors"] > 0, ins["validate"]
    good = SB._new_row(SB.Case("pinned", "good", {}), "pinned:good@0")
    bat.instruments(good, ours, NATIVE)
    assert {k: v["state"] for k, v in good["instruments"].items()} == {
        "release": "pass", "verify": "pass", "validate": "pass", "provenance": "pass",
        "law": "pass", "conformance": "skip"}


def test_a_failing_provenance_check_fails_the_instrument(tmp_path, monkeypatch, ours):
    from rvt.famgen import famdoc_adoc as FA
    bat = SB.Battery(str(tmp_path))
    assert bat._i_provenance(ours, NATIVE)[0] == "pass"
    real = FA.provenance_scan_v2

    def not_ours(path, donor=None):
        r = real(path, donor=donor)
        return dict(r, ok=False, checks=dict(r["checks"], identity_is_ours=False))
    monkeypatch.setattr(FA, "provenance_scan_v2", not_ours)
    st, detail, extra = bat._i_provenance(ours, NATIVE)
    assert st == "fail" and "v2.identity_is_ours" in extra["failing_checks"], detail
    monkeypatch.setattr(FA, "provenance_scan_v2", real)
    monkeypatch.setattr(F, "provenance_scan", lambda p: {"checks": {"ledger_present": False}})
    st, detail, extra = bat._i_provenance(ours, NATIVE)
    assert st == "fail" and extra["failing_checks"] == ["ledger.ledger_present"], detail


def test_the_law_reads_every_nested_document(tmp_path, monkeypatch, ours):
    from rvt.famgen import constraint_law as CL
    real = CL.check_file
    monkeypatch.setattr(CL, "nested_units", lambda p: {"0123456789abcdef": 7})

    def law(path, unit=0):
        if unit == 7:
            return [{"severity": "error", "message": "a broken nested chain"}]
        return real(path) if unit == 0 else []
    monkeypatch.setattr(CL, "check_file", law)
    st, detail, _x = SB.Battery(str(tmp_path))._i_law(ours, NATIVE)
    assert st == "fail" and "[nested 01234567]" in detail and "2 document(s)" in detail


# -- the matrix comes from the declarations (DONE 1) ---------------------------

def test_every_declared_source_contributes_cases():
    cases, decl = SB.enumerate_matrix()
    by = {}
    for c in cases:
        by.setdefault(c.source, []).append(c)
    assert set(by) >= {"make_family", "famspec", "archetype", "part_shape", "prism",
                       "ifc_route", "evidence"}
    assert {c.product for c in by["archetype"]} == set(AR.keys())
    shapes = set(F.GENERIC_PART_SHAPES) | set(__import__(
        "rvt.famgen.revolve", fromlist=["x"]).COMPOSITE_SHAPES)
    assert {c.product for c in by["part_shape"]} == shapes
    assert not [c for c in cases if c.error], [c.error for c in cases if c.error]
    assert all(c.rebuildable for c in cases)              # the twin can rebuild every one
    gens = decl["make_family"]["generators"]
    assert {"panelboard", "transformer", "luminaire", "device"} <= set(gens)
    assert "load" in decl["make_family"]["excluded"]       # an .rvt lane, not a family
    # every device kind the engine declares is a case
    kinds = {c.variant.get("kind", "duplex-receptacle") for c in by["make_family"]
             if c.product == "device"}
    assert kinds == set(F.DEVICE_KINDS)
    # every archetype with an NEC working space has its clearance case
    ws = {k for k in AR.keys() if AR.archetype(k).working_space}
    assert "lighting_control_panel" in ws
    assert {c.product for c in by["archetype"] if c.variant == {"prompt": "clearance"}} == ws
    # every taxonomy builder is driven -- the switchboard by its declared kwargs
    assert decl["taxonomy"]["uncovered"] == []
    assert decl["taxonomy"]["mechanisms"][
        "house:rvt.ifc.intent:make_house_switchboard"] == "evidence"
    assert any(c.product.endswith("/MSB") for c in by["evidence"])


def test_an_uncovered_taxonomy_builder_is_a_failing_row(monkeypatch):
    from rvt.famgen import taxonomy as TX
    row = dataclasses.replace(TX.get("switchboard"), key="battery_probe",
                              via=("house:rvt.ifc.intent:make_battery_probe",))
    monkeypatch.setattr(TX, "kinds", lambda: TX._ROWS + (row,))
    cases = SB.enumerate_matrix(sources=["taxonomy"])[0]
    assert [c.product for c in cases] == ["house:rvt.ifc.intent:make_battery_probe"]
    assert "driven by no battery source" in cases[0].error


def test_a_non_generator_with_output_must_say_why(monkeypatch):
    monkeypatch.setattr(SB, "NON_FAMILY_SUBCOMMANDS", {})
    cases = SB.enumerate_matrix(sources=["make_family"])[0]
    gaps = sorted(c.product for c in cases if c.error)
    # proofs takes no --output but WRITES (--no-validate): a writer is a gap too (#1088 review)
    assert gaps == ["load", "load-device", "loader", "proofs"], gaps


def test_adding_an_archetype_adds_its_cases_with_no_edit_here(monkeypatch):
    before = len(SB.enumerate_matrix(sources=["archetype"])[0])
    a = AR.archetype("wireway")
    monkeypatch.setitem(AR.ARCHETYPES, "battery_probe", dataclasses.replace(a, key="battery_probe"))
    cases = SB.enumerate_matrix(sources=["archetype"])[0]
    mine = [c for c in cases if c.product == "battery_probe"]
    assert mine and len(cases) - before == len(mine)
    assert {} in [c.variant for c in mine]                  # its nominal
    assert {"width_in": 12.0} in [c.variant for c in mine]  # a standard size


def test_adding_a_device_kind_adds_its_cases(monkeypatch):
    monkeypatch.setitem(F.DEVICE_KINDS, "battery-probe", F.DEVICE_KINDS["switch"])
    cases = SB.enumerate_matrix(sources=["make_family"])[0]
    assert [c for c in cases if c.product == "device"
            and c.variant.get("kind") == "battery-probe"]


def test_a_shape_the_schema_does_not_declare_is_a_failing_row(monkeypatch):
    monkeypatch.setattr(F, "GENERIC_PART_SHAPES", F.GENERIC_PART_SHAPES + ("battery_probe",))
    cases = SB.enumerate_matrix(sources=["part_shape"])[0]
    drift = [c for c in cases if c.error]
    assert drift and "declaration drift" in drift[0].error


def test_capturing_the_make_family_parser_leaves_argparse_alone():
    orig = argparse.ArgumentParser.parse_args
    p = SB.make_family_parser()
    assert argparse.ArgumentParser.parse_args is orig
    assert "panelboard" in SB._subparsers(p)


def test_releases_follow_known_releases():
    from rvt import versions as V
    run, bases, skipped, broken = SB.releases()
    assert NATIVE in run and not broken
    for y in V.KNOWN_RELEASES:
        assert (y in run) != (str(y) in skipped)
        if not V.KNOWN_RELEASES[y].creation_certified:
            assert y not in run


def test_a_broken_base_or_an_empty_run_fails(tmp_path, monkeypatch):
    from rvt.frontdoor import base as FB
    real = FB.resolve_base

    def broken(*a, **k):
        if k.get("target_release") == 2024:
            raise FB.BaseError("simulated: the tracked 2024 base does not resolve")
        return real(*a, **k)
    monkeypatch.setattr(FB, "resolve_base", broken)
    run, _b, _s, bad = SB.releases([2024])
    assert run == [] and 2024 in bad and "simulated" in bad[2024]
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1234")
    rc = SB.main(["--release", "2024", "--no-corpus", "--no-twin", "--out", str(tmp_path / "r")])
    rep = json.loads((tmp_path / "r.json").read_text())
    assert rc == 1 and rep["summary"]["failures"][0]["case"] == "release:base@2024"
    assert os.environ.get("SOURCE_DATE_EPOCH") == "1234"     # put back, not leaked
    monkeypatch.setattr(FB, "resolve_base", real)
    # an --only that matches nothing ran nothing: never a pass
    assert SB.main(["--only", "no-such-case-anywhere", "--no-corpus",
                    "--out", str(tmp_path / "e")]) == 1
    assert os.environ.get("SOURCE_DATE_EPOCH") == "1234"


def test_an_unpinned_or_uncertified_base_is_broken_not_skipped(monkeypatch):
    from rvt.frontdoor import base as FB
    real = FB.resolve_base

    def unpinned(*a, **k):
        rb = real(*a, **k)
        return dataclasses.replace(rb, pinned=False) if k.get("target_release") == 2024 else rb
    monkeypatch.setattr(FB, "resolve_base", unpinned)
    run, _b, _s, bad = SB.releases([2024])
    assert run == [] and "not pinned + certified" in bad[2024]


def test_the_exit_code_fails_on_every_failure_kind():
    ok_row = {"state": "pass", "ok": True}
    good = {"summary": {"totals": {"fail": 0}}}
    assert SB.exit_code(good, [], {"state": "ok"}, [ok_row]) == 0
    assert SB.exit_code({"summary": {"totals": {"fail": 1}}}, [], {"state": "ok"}, [ok_row]) == 1
    assert SB.exit_code(good, [{"ok": False}], {"state": "ok"}, [ok_row]) == 1   # a pinned probe
    assert SB.exit_code(good, [], {"state": "fail"}, [ok_row]) == 1
    assert SB.exit_code(good, [], {"state": "partial"}, [ok_row]) == 1
    assert SB.exit_code(good, [], {"state": "skip"}, [ok_row]) == 0
    assert SB.exit_code(good, [], {"state": "ok"}, []) == 1                      # ran nothing


# -- states: pass / fail / refused / alias; a crash is a fail ------------------

def _case(build, product="probe", **kw):
    return SB.Case("pinned", product, {}, release=NATIVE, build=build,
                   write=SB._default_write, **kw)


def test_a_named_port_refusal_is_refused_not_failed(tmp_path):
    from rvt.genesis.port2024 import Missing2024

    def refuse():
        raise Missing2024("class 'ArcElemCell' has no 2024 twin")
    row = SB.Battery(str(tmp_path)).run(_case(refuse))[0]
    assert row["state"] == "refused" and not row["ok"]
    assert row["instruments"]["build"]["state"] == "refused"
    assert row["instruments"]["verify"]["state"] == "not_run"
    s = SB.summarize([row])
    assert s["totals"]["refused"] == 1 and s["totals"]["fail"] == 0 and s["refusals"]


@pytest.mark.parametrize("exc", ["ReleaseContextError", "BaseNotCertified",
                                 "UnsupportedTarget", "KeyError", "PortabilityError"])
def test_anything_but_a_port_refusal_is_a_failure(tmp_path, exc):
    """The bare ``PortabilityError`` is raised for OUR encoder gaps ("unsupported
    field kind", a drifted 2023 pin): a defect, never a known-good refusal
    (#1088 review) -- only the named Missing20xx refuse."""
    from rvt import versions as V
    from rvt.frontdoor import base as FB
    from rvt.genesis.port2025 import PortabilityError
    cls = {"ReleaseContextError": RC.ReleaseContextError, "BaseNotCertified": FB.BaseNotCertified,
           "UnsupportedTarget": V.UnsupportedTarget, "KeyError": KeyError,
           "PortabilityError": PortabilityError}[exc]

    def crash():
        raise cls("a release context entered inside another one")
    row = SB.Battery(str(tmp_path)).run(_case(crash))[0]
    assert row["state"] == "fail" and row["instruments"]["build"]["state"] == "fail", exc
    assert SB.classify(cls("x")) == "fail"


@pytest.mark.parametrize("missing", ["port2025.Missing2025", "port2024.Missing2024",
                                     "port2023.Missing2023"])
def test_every_named_missing_class_refuses(missing):
    import importlib
    mod, name = missing.split(".")
    cls = getattr(importlib.import_module(f"rvt.genesis.{mod}"), name)
    assert SB.classify(cls("class 'X' has no twin")) == "refused"


def test_a_stale_file_from_an_earlier_run_is_never_graded(tmp_path):
    """A writer that returns but writes nothing must FAIL write even when an
    earlier run left a family at that very path -- the stale bytes are never
    handed to the read-back instruments or to determinism (#1088 review)."""
    good = _case(lambda: F.make_archetype(product="wireway"))
    first = SB.Battery(str(tmp_path), keep=True).run(good)[0]
    assert first["state"] == "pass" and os.path.isfile(first["path"])

    def no_write(prod, path):
        return {"ok": True}
    lazy = SB.Case("pinned", "probe", {}, release=NATIVE,
                   build=lambda: F.make_archetype(product="wireway"), write=no_write)
    assert lazy.cid == good.cid                     # the same case dir as the first run
    row = SB.Battery(str(tmp_path), keep=True).run(lazy)[0]
    assert row["instruments"]["write"]["state"] == "fail", row["instruments"]["write"]
    assert "wrote no file" in row["instruments"]["write"]["detail"]
    assert row["state"] == "fail"
    for inst in ("verify", "validate", "law", "determinism"):
        assert row["instruments"][inst]["state"] == "not_run", inst


def test_a_hung_twin_fails_determinism_instead_of_hanging(tmp_path):
    tw = SB.Twin(str(tmp_path), {})
    tw.proc = None
    import queue as Q
    import subprocess as SP
    tw.proc = SP.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                       stdin=SP.PIPE, stdout=SP.PIPE, text=True)
    tw._lines = Q.Queue()
    t0 = time.time()
    with pytest.raises(RuntimeError, match="no answer in 0.5 s"):
        tw.collect(timeout=0.5)
    assert time.time() - t0 < 30 and tw.proc is None


def test_a_corpus_that_mines_only_partly_fails_the_run(tmp_path, own_corpus):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for p in sorted(os.listdir(own_corpus[0])):
        shutil.copy(os.path.join(own_corpus[0], p), corpus / p)
    (corpus / "zz_junk.rfa").write_bytes(b"\0" * 1024)
    inv, blk = SB.load_oracle(str(corpus), str(tmp_path / "cache"), explicit=True)
    assert inv and blk["state"] == "partial" and "1 of" in blk["reason"]
    rc = SB.main(["--quick", "--only", "archetype:wireway@", "--no-twin",
                  "--corpus", str(corpus), "--out", str(tmp_path / "o")])
    assert rc == 1


def test_the_release_and_write_instruments_can_fail(tmp_path, ours):
    bat = SB.Battery(str(tmp_path))
    st, detail, _ = bat._i_release(ours, 2025)          # a native file is not a 2025 file
    assert st == "fail" and str(NATIVE) in detail

    def explode(prod, path):
        raise OSError("disk full (forced by the test)")
    case = SB.Case("pinned", "probe", {}, release=NATIVE,
                   build=lambda: F.make_archetype(product="wireway"), write=explode)
    row = bat.run(case)[0]
    assert row["instruments"]["build"]["state"] == "pass"
    assert row["instruments"]["write"]["state"] == "fail" and "disk full" in \
        row["instruments"]["write"]["detail"]
    assert row["state"] == "fail"


@pytest.mark.parametrize("second", ["different bytes", "nothing"])
def test_route_determinism_fails_when_the_second_run_differs(tmp_path, ours, second):
    calls = []

    def route(out_dir, year):
        calls.append(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        if len(calls) == 1:
            shutil.copy(ours, os.path.join(out_dir, "f.rfa"))
        elif second == "different bytes":
            data = bytearray(open(ours, "rb").read())
            data[-1] ^= 0xFF
            open(os.path.join(out_dir, "f.rfa"), "wb").write(bytes(data))
        return {"ok": True}
    case = SB.Case("ifc_route", "flaky", {}, release=NATIVE, route=route)
    rows = SB.Battery(str(tmp_path)).run(case)
    det = [r["instruments"]["determinism"] for r in rows if r["case"] != case.cid]
    assert len(calls) == 2 and det and det[0]["state"] == "fail", det
    assert ("sha256 differs" if second == "different bytes" else "did not write it") \
        in det[0]["detail"]


def test_an_instrument_that_crashes_is_a_fail_never_a_skip(tmp_path, monkeypatch):
    def boom(self, path, year):
        raise RuntimeError("instrument down")
    monkeypatch.setattr(SB.Battery, "_i_law", boom)
    row = SB.Battery(str(tmp_path)).run(_case(lambda: F.make_archetype(product="conduit")))[0]
    assert row["instruments"]["law"]["state"] == "fail"
    assert "instrument crashed" in row["instruments"]["law"]["detail"]
    assert row["state"] == "fail"


def test_determinism_catches_a_build_that_changes_between_runs(tmp_path):
    n = []

    def drifting():
        n.append(1)
        return F.make_archetype(product="conduit", name=f"Conduit {len(n)}")
    row = SB.Battery(str(tmp_path)).run(_case(drifting))[0]
    assert row["instruments"]["determinism"]["state"] == "fail", row["steps"]
    assert row["state"] == "fail"


def test_determinism_catches_a_build_that_reads_the_wall_clock(tmp_path):
    """Two builds seconds apart agree on the minute; the rebuild's clock does not."""
    def by_the_minute():
        return F.make_archetype(product="conduit", name=f"Conduit {int(time.time() // 60)}")
    row = SB.Battery(str(tmp_path)).run(_case(by_the_minute))[0]
    det = row["instruments"]["determinism"]
    assert det["state"] == "fail" and "clock +400 d" in det["detail"], det


def test_the_twin_runs_on_another_hash_seed_and_a_shifted_clock(tmp_path):
    twin = SB.Twin(str(tmp_path), {})
    try:
        p = twin.probe("self-battery")
    finally:
        twin.close()
    now = time.time()
    assert abs(p["time"] - now - SB.TIME_SHIFT_S) < 120, p
    assert abs(p["now"] - now - SB.TIME_SHIFT_S) < 120, p
    assert p["hash_seed"] == SB.twin_hash_seed() and p["hash"] != hash("self-battery")
    # a FIXED seed that is not ours: the twin's ordering is reproducible, and differs
    assert p["hash_seed"].isdigit() and p["hash_seed"] != SB.parent_hash_seed()
    assert SB.twin_hash_seed("41") == "42" and SB.twin_hash_seed("random") == "796"


def test_byte_identical_cases_are_aliases_only_when_pinned(tmp_path):
    mk = lambda: F.make_archetype(product="conduit")          # noqa: E731
    bat = SB.Battery(str(tmp_path / "p"), alias_groups={"pinned:one": 0, "pinned:two": 0})
    first = bat.run(_case(mk, product="one"))[0]
    second = bat.run(_case(mk, product="two"))[0]
    assert first["state"] == "pass", first["steps"]
    assert second["state"] == "alias" and second["alias_of"] == first["case"]
    s = SB.summarize([first, second])
    assert s["totals"] == {"pass": 1, "fail": 0, "refused": 0, "alias": 1}
    assert s["aliases"] == [{"case": second["case"], "alias_of": first["case"],
                             "state": "alias"}]
    # the same pair, NOT pinned: the variant had no effect -> FAIL
    bat = SB.Battery(str(tmp_path / "u"), alias_groups={})
    bat.run(_case(mk, product="one"))
    second = bat.run(_case(mk, product="two"))[0]
    assert second["state"] == "fail"
    assert "had no effect" in second["instruments"]["build"]["detail"]
    # a pinned group whose members now differ is reported as drift (a note)
    rows = [{"case": "a:x@2026", "sha256": "1"}, {"case": "a:x y=1@2026", "sha256": "2"}]
    assert SB.alias_drift(rows, {"a:x": 0, "a:x y=1": 0})[0]["distinct"] == 2


def test_the_alias_pin_names_enumerated_cases_only():
    pin = SB.load_alias_pin()
    assert not pin.get("missing")
    keys = {c.key for c in SB.enumerate_matrix()[0]}
    flat = [k for g in pin["groups"] for k in g]
    assert flat and set(flat) <= keys, sorted(set(flat) - keys)
    assert len(flat) == len(set(flat))                    # no key in two groups
    # 25 relations: 2026 and 2025 show all 25, 2024 the 20 whose members build there
    assert sum(len(g) - 1 for g in pin["groups"]) == pin["relations"] == 25


def test_the_route_lane_fails_a_route_that_is_not_ok_or_raises(tmp_path, ours):
    def written_but_not_ok(out_dir, year):
        os.makedirs(out_dir, exist_ok=True)
        shutil.copy(ours, os.path.join(out_dir, "f.rfa"))
        return {"ok": False, "line": "partial", "errors": ["one family refused"]}
    case = SB.Case("ifc_route", "fake", {}, release=NATIVE, route=written_but_not_ok)
    rows = SB.Battery(str(tmp_path)).run(case)
    top = [r for r in rows if r["case"] == case.cid]
    assert top and top[0]["state"] == "fail", [r["case"] for r in rows]
    assert "route not ok" in top[0]["instruments"]["build"]["detail"]
    files = [r for r in rows if r["case"] != case.cid]
    assert files and files[0]["instruments"]["verify"]["state"] == "pass"
    assert files[0]["instruments"]["determinism"]["state"] == "pass"

    def raises(out_dir, year):
        raise RC.ReleaseContextError("nested release context")
    rows = SB.Battery(str(tmp_path / "x")).run(
        SB.Case("ifc_route", "raises", {}, release=NATIVE, route=raises))
    assert [r["state"] for r in rows] == ["fail"]


def test_the_report_names_every_failing_tuple(tmp_path):
    def crash():
        raise KeyError("boom")
    bat = SB.Battery(str(tmp_path))
    rows = bat.run(_case(crash, product="broken"))
    s = SB.summarize(rows)
    assert s["failures"] and s["failures"][0]["tuple"]["product"] == "broken"
    report = {"mode": "test", "seconds": 0.0, "summary": s,
              "matrix": {"cases": 1, "distinct": 1},
              "releases": {"run": [NATIVE], "skipped": {}},
              "corpus": {"reason": "none"}, "pinned": []}
    assert "FAIL pinned:broken@" in SB.text_summary(report)


# -- the CI shard's battery (DONE 5) ------------------------------------------

def test_quick_mode_builds_every_archetype_and_every_instrument_passes(tmp_path):
    out = tmp_path / "q"
    rc = SB.main(["--quick", "--no-corpus", "--out", str(out)])
    rep = json.loads((tmp_path / "q.json").read_text())
    assert (tmp_path / "q.txt").is_file()
    assert {r["tuple"]["product"] for r in rep["rows"]} == set(AR.keys())
    assert rep["releases"]["run"] == [NATIVE]
    bad = rep["summary"]["failures"]
    assert rc == 0 and not bad, bad
    per = rep["summary"]["per_instrument"]
    for inst in SB.INSTRUMENTS:
        if inst == "conformance":
            assert per[inst]["skip"] == len(rep["rows"])
        else:
            assert per[inst]["pass"] == len(rep["rows"]), (inst, per[inst])
    # determinism was judged by the twin: another process, hash seed and clock
    assert rep["determinism"]["mode"] == "twin process"
    assert all("twin process" in r["instruments"]["determinism"]["detail"]
               for r in rep["rows"])
    # the determinism copies are cleaned unless --keep
    assert not [d for d, _s, _f in os.walk(out) if d.endswith(os.sep + "b")]
