"""test_famload_determinism_794.py -- two identical family LOADS produce
byte-identical projects (#794).

#168 made the family **build** reproducible. The **load** path was left alone
on purpose, because none of it executes for a build -- and it minted `uuid4`,
so two identical loads produced two different `.rvt` files. That is the half a
user meets more often: `add_to_project` and the whole `rfa -> rvt` lane come
through here.

THE KEY IS THE FAMILY AND NOT THE HOST, which is a correction to what the
issue asked for. #794 DONE 1 specified a key over the host too; the sandbox
CI failed `test_famload_batch.py::test_chain_and_batch_are_logically_identical`,
an invariant older than the issue -- loading two families one at a time must
produce the same plans as loading both in one batch, and in the chain the
second family's host is the intermediate file. Any host term must differ
between the two, so the host term had to go. It is also the better semantics:
`m_famDocGUID` identifies the family DOCUMENT, and the same family in two
projects genuinely is the same family document.

WHAT WAS ACTUALLY NON-DETERMINISTIC, measured by instrumenting `uuid.uuid4`
and running each lane rather than by grepping -- the issue's own table named
three sites and was wrong about two of them:

  | site                                    | reached by                      |
  |-----------------------------------------|---------------------------------|
  | `famload._plan_family`                  | famspec -> rvt                  |
  | `convert.rfa_load.BornRfaDoc.__init__`  | ANY `.rfa` path -> rvt          |
  | `famgen.loader.plan_load`               | extract's own re-load check     |
  | `genesis.skeleton.minimal_globals`      | the EXTRACT lane (rvt -> rfa)   |

`convert.rfa_load` was not in the issue's table at all and is the one a user
hits by handing us a `.rfa`. `factory.py`'s host-document GUID fallback *was*
in the table and is not reached by any product lane -- famload passes
`document_guid=plan.guid` explicitly, and since #793 a finalized document
always carries a sealed GUID, so the `or str(uuid.uuid4())` arm is dead there.
`minimal_globals` is out of this issue's territory BY NAME: it is shared with
the genesis compose path, whose output is the certified bases (hard rule 4).
The extract lane is therefore still non-deterministic and that is recorded,
not quietly fixed.

THE PROBE'S OWN BUG, inherited from #168 and kept in mind by every case here:
the output filename legitimately appears inside the file (last-save path,
PartAtom title), so a probe that writes `a.rvt` and `b.rvt` is measuring two
variables. Every case below writes the SAME filename in DIFFERENT directories.

WHAT THIS IS NOT. Reproducibility is a fact about our bytes. It is never
evidence that Revit opens them (hard rule 4), and nothing here claims a viewer
or desktop verdict.
"""
import dataclasses
import hashlib
import os

import pytest

from rvt import famload as FL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
FAMSPEC = os.path.join(ROOT, "spec", "examples", "famspec-panelboard.json")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(HOST) and os.path.exists(FAMSPEC)),
    reason="needs the bundled genesis base and the worked famspec examples")

#: the one output name every probe writes, in its own directory
OUT = "loaded.rvt"


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _route(tmp_path, sub, inputs, output="rvt", **opts):
    from rvt.frontdoor import router as R
    return R.route(inputs, output, out=str(tmp_path / sub), quiet=True, **opts)


def _the_rvt(res):
    hits = sorted(v for k, v in res.files.items() if str(v).endswith(".rvt"))
    assert hits, res.files
    return hits[0]


# ===========================================================================
# 1. the derivations themselves (DONE 1 and 2)
# ===========================================================================

def test_the_same_family_derives_the_same_guids():
    assert FL.load_doc_guid("fam-content-guid") == FL.load_doc_guid("fam-content-guid")
    assert (FL.load_session_guid_hex("fam-content-guid")
            == FL.load_session_guid_hex("fam-content-guid"))


def test_TWO_DIFFERENT_families_get_DIFFERENT_guids():
    """DONE 2's first half, and the reason the key cannot be the host alone.

    Two Family elements in one project must never claim one family-document
    identity, and the content GUID -- content-derived since #793 -- is what
    keeps them apart.
    """
    assert FL.load_doc_guid("fam-A") != FL.load_doc_guid("fam-B")
    assert FL.load_session_guid_hex("fam-A") != FL.load_session_guid_hex("fam-B")


def test_the_HOST_is_NOT_in_the_key_and_that_is_load_bearing():
    """The correction CI forced, pinned so it cannot be quietly undone.

    #794 DONE 1 asked for a key over the host as well, and the first version
    of this change did exactly that -- until
    `test_famload_batch.py::test_chain_and_batch_are_logically_identical`
    failed in the sandbox. That test encodes an invariant older than the
    issue: loading two families ONE AT A TIME (each into the previous
    output) must produce the same plans as loading both in ONE batch. In the
    chain, the second family's host is the intermediate file; in the batch it
    is the original base. Any key over host bytes MUST differ between them.

    Re-introducing a host term would break that test, but it would break it
    600 lines away in another module, so this asserts the API shape here
    where the decision lives.
    """
    import inspect
    sig = inspect.signature(FL.load_doc_guid)
    assert list(sig.parameters) == ["family_guid"], (
        "load_doc_guid grew a parameter -- if a host term came back, read "
        "test_chain_and_batch_are_logically_identical first")
    assert list(inspect.signature(FL.load_session_guid_hex).parameters) == ["family_guid"]


def test_the_SAME_family_into_TWO_DIFFERENT_HOSTS_derives_one_guid(tmp_path):
    """The behavioural half of the no-host-in-the-key rule.

    `test_the_HOST_is_NOT_in_the_key_and_that_is_load_bearing` above is a
    signature-shape proxy, and #801's round-3 reviewer showed exactly how far
    that gets you: a host-sha256 term inlined at `_plan_family`'s CALL SITE,
    without touching `load_doc_guid`'s signature, left all 29 tests passing.
    A future session re-introducing the host that way would sail through.

    So this drives the real `_plan_family` against THREE HostContexts and
    pins the derived GUIDs identical across all of them:

    * host B differs in `path` and in the bytes of the file behind it --
      what a host-*bytes* term would hash;
    * host C differs in EVERY OTHER FIELD of `HostContext` that a term could
      reach for -- not just `watermark` and `episode`. An earlier version of
      this test varied only those two, calling them "the host's other two
      identities"; `HostContext` has nine more, and #801's round-5 reviewer
      duly found `partition_name` and `category_gstyles` mutants still
      surviving. Closing fields one per review round is a losing game, so
      host C is built by replacing everything except `doc` (which cannot be
      synthesised) and the id-allocation inputs the plan legitimately needs.
      An earlier version of this test held `watermark`/`episode` equal and
      claimed varying them "would prove nothing about the GUID key". That
      was an over-claim, caught by #801's round-4 reviewer with a working
      repro: `our_guid("famload-doc", guid, int(host.watermark))` and its
      `episode` twin BOTH survived all 30 tests. The assertion here is on
      `fam_doc_guid` / `session_guid_hex` alone, so varying those fields
      proves exactly what it needs to -- that they are not in the key.

    Host C LOWERS the watermark rather than raising it, so the document's own
    ids stay above it and `_plan_family`'s `lo <= host.watermark` guard is
    still satisfied; what matters is that the value moved, not which way.
    """
    import shutil
    from rvt.famgen import factory as F

    host_a = FL.survey_host(HOST)
    # a second host that is a DIFFERENT FILE with different bytes -- which is
    # what any host-derived term would hash -- while leaving every field
    # `_plan_family` legitimately reads untouched
    other = str(tmp_path / "other-host.rvt")
    shutil.copyfile(HOST, other)
    with open(other, "ab") as fh:
        fh.write(b"\0" * 64)
    assert open(HOST, "rb").read() != open(other, "rb").read()
    host_b = dataclasses.replace(host_a, path=other)

    wm = int(host_a.watermark)
    # EVERY other field of HostContext, moved at once. Enumerated from the
    # dataclass rather than hand-listed, so a field added later is varied
    # here automatically instead of quietly becoming the next surviving
    # mutant. `doc` is excluded (it cannot be synthesised); `watermark` and
    # `episode` get values the plan can still work with.
    varied = {"watermark": wm - 10, "episode": int(host_a.episode) + 7,
              "path": other, "partition_name": str(host_a.partition_name) + "-x",
              # NON-EMPTY on purpose: host_a's is already {}, so replacing it
              # with {} varied nothing and a `len(host.category_gstyles)`
              # mutant survived this very check until it was measured
              "category_gstyles": {-2001040: 999999},
              "fill_pattern_solid": 123456,
              "line_pattern_solid": 123457, "census_before": {"probe": 1},
              "usage_referrers": {"Probe": [1, 2]}, "notes": ["probe"]}
    # NOTE on what this guard does and does not catch: it asserts the VALUES
    # differ, so a mutant that collapses a field (`len()`, `bool()`) could in
    # principle still survive if host C's value collapsed onto host A's.
    # Measured today there is no such collision (census 19 vs 1, referrers
    # 7 vs 1, notes 0 vs 1, gstyles {} vs 1 entry), but a future field whose
    # varied value collapses the same way would need a different value here,
    # not a different assertion.
    for name, value in varied.items():
        assert value != getattr(host_a, name), (
            "host C's %r is equal to host A's, so this axis is not actually "
            "varied and a term keyed on it would survive" % name)
    fields = {f.name for f in dataclasses.fields(FL.HostContext)} - {"doc"}
    assert set(varied) == fields, (
        "HostContext gained or lost a field -- vary it here too, or say in "
        "this test why it cannot be varied: %s" % (fields ^ set(varied)))
    host_c = dataclasses.replace(host_a, **varied)

    guids = []
    for host in (host_a, host_b, host_c):
        prod = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=225,
                                 spaces=42, voltage="208Y/120", start_id=wm + 1)
        prod.doc.finalize()
        plan, _cursor = FL._plan_family(
            FL.FamilyLoad(key="probe", doc=prod.doc), prod.doc, host, wm + 50000)
        guids.append((plan.fam_doc_guid, plan.session_guid_hex))
    assert guids[0] == guids[1] == guids[2], (
        "the derived GUIDs moved with the host -- something host-derived is "
        "back in the key (path/bytes, watermark or episode); read "
        "test_famload_batch.py::test_chain_and_batch_are_logically_identical "
        "before 'fixing' this")


def test_chaining_and_batching_agree_on_the_derived_guids(tmp_path):
    """The invariant itself, exercised through the derivation directly.

    `test_famload_batch.py` owns the end-to-end version; this is the unit
    statement of why the key had to lose the host: the SAME family gets the
    SAME guid no matter which project it is going into.
    """
    fam = "76e2f89b-1ee0-57f1-ab95-3fd07efb19d0"
    assert FL.load_doc_guid(fam) == FL.load_doc_guid(fam)


# ===========================================================================
# 2. the lanes, end to end (DONE 3)
# ===========================================================================

def test_two_identical_FAMSPEC_loads_are_byte_identical(tmp_path):
    a = _the_rvt(_route(tmp_path, "a", {"rfa": FAMSPEC}, stem="loaded"))
    b = _the_rvt(_route(tmp_path, "b", {"rfa": FAMSPEC}, stem="loaded"))
    assert os.path.basename(a) == os.path.basename(b)       # the #168 trap
    assert os.path.dirname(a) != os.path.dirname(b)
    assert _sha(a) == _sha(b)


def test_two_identical_RFA_PATH_reloads_are_byte_identical(tmp_path):
    """The lane `convert.rfa_load` serves -- the one a user reaches by
    handing us a `.rfa`, and the one the issue's table did not list."""
    built = _route(tmp_path, "build", {"rfa": FAMSPEC}, output="rfa")
    rfa = built.files["rfa"]
    a = _the_rvt(_route(tmp_path, "a", {"rfa": rfa}, stem="loaded"))
    b = _the_rvt(_route(tmp_path, "b", {"rfa": rfa}, stem="loaded"))
    assert os.path.basename(a) == os.path.basename(b)
    assert _sha(a) == _sha(b)


def test_the_loaded_project_still_validates_and_keeps_our_identity(tmp_path):
    """DONE 4: determinism must not have been bought with a broken file."""
    from rvt import validate as V
    out = _the_rvt(_route(tmp_path, "a", {"rfa": FAMSPEC}, stem="loaded"))
    rep = V.validate_file(out)
    errors = [f for f in rep.findings if f.severity == "error"]
    assert errors == [], errors


def test_a_DIFFERENT_famspec_loads_to_a_different_project(tmp_path):
    """The control the determinism cases need: identical output for identical
    input is only meaningful if different input still differs."""
    tr = os.path.join(ROOT, "spec", "examples", "famspec-transformer.json")
    if not os.path.exists(tr):
        pytest.skip("no transformer example on this checkout")
    a = _the_rvt(_route(tmp_path, "a", {"rfa": FAMSPEC}, stem="loaded"))
    b = _the_rvt(_route(tmp_path, "b", {"rfa": tr}, stem="loaded"))
    assert _sha(a) != _sha(b)


# ===========================================================================
# 3. the mint census -- the claim that no product lane mints any more
# ===========================================================================

def _mint_sites(fn):
    """Run ``fn`` with ``uuid.uuid4`` instrumented; return {site: count}.

    Instrumented rather than grepped, because that is how #168's own issue
    came to name the wrong lines: a grep finds text, a stack finds what
    actually ran.
    """
    import collections
    import traceback
    import uuid
    seen = collections.Counter()
    real = uuid.uuid4

    def spy():
        stack = traceback.extract_stack()[:-1]
        for fr in reversed(stack):
            if os.sep + "rvt" + os.sep in fr.filename:
                seen["%s:%s" % (os.path.basename(fr.filename), fr.name)] += 1
                break
        return real()

    uuid.uuid4 = spy
    try:
        fn()
    finally:
        uuid.uuid4 = real
    return dict(seen)


@pytest.mark.parametrize("name,inputs,output", [
    ("famspec->rvt", {"rfa": FAMSPEC}, "rvt"),
    ("famspec->rfa", {"rfa": FAMSPEC}, "rfa"),
])
def test_no_product_lane_MINTS_a_guid_any_more(tmp_path, name, inputs, output):
    seen = _mint_sites(lambda: _route(tmp_path, "out", inputs, output=output))
    assert seen == {}, seen


def test_the_rfa_path_reload_lane_mints_nothing(tmp_path):
    built = _route(tmp_path, "build", {"rfa": FAMSPEC}, output="rfa")
    rfa = built.files["rfa"]
    seen = _mint_sites(lambda: _route(tmp_path, "out", {"rfa": rfa}))
    assert seen == {}, seen


def test_the_standalone_born_guid_separates_two_copies_in_one_host(tmp_path):
    """The reason the old code gave for minting, kept rather than discarded.

    Two loads of ONE `.rfa` into one project must not claim one document
    identity. They cannot share an id block -- each is allocated above the
    other -- so `start_id` is what separates them, and using it means the
    distinctness survives without costing reproducibility.
    """
    from rvt.convert.rfa_load import RfaSource
    built = _route(tmp_path, "build", {"rfa": FAMSPEC}, output="rfa")
    ldr = RfaSource(built.files["rfa"])
    assert ldr.document_guid_at(100000) == ldr.document_guid_at(100000)
    assert ldr.document_guid_at(100000) != ldr.document_guid_at(200000)


def test_the_standalone_born_guid_is_keyed_on_the_rfas_CONTENT(tmp_path):
    import shutil
    from rvt.convert.rfa_load import RfaSource
    built = _route(tmp_path, "build", {"rfa": FAMSPEC}, output="rfa")
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir(), two.mkdir()
    a, b = str(one / "f.rfa"), str(two / "renamed.rfa")
    shutil.copyfile(built.files["rfa"], a)
    shutil.copyfile(built.files["rfa"], b)
    assert (RfaSource(a).document_guid_at(100000)
            == RfaSource(b).document_guid_at(100000))


# ===========================================================================
# 4. what is NOT fixed, pinned so it cannot be forgotten
# ===========================================================================

def test_the_EXTRACT_lane_is_still_nondeterministic_and_that_is_on_purpose():
    """`genesis.skeleton.minimal_globals` is out of #794's territory BY NAME.

    It is shared with the genesis compose path, whose output is the three
    certified bases (hard rule 4), and #168 has a test pinning its defaults.
    So this asserts the CURRENT boundary rather than a wish: if someone later
    makes it derived, this test fails and the decision gets re-made on
    purpose instead of drifting.

    Asserted BEHAVIOURALLY -- two calls, different results -- and not by
    grepping the function's source for "uuid4()", which #801's reviewer
    rightly called a weak form: a source grep passes if someone makes the
    lane deterministic while leaving a dead mint behind, and fails on a
    cosmetic refactor that changes nothing.
    """
    import json
    from rvt.genesis import skeleton as GSK
    a = json.dumps(GSK.minimal_globals([]), sort_keys=True, default=str)
    b = json.dumps(GSK.minimal_globals([]), sort_keys=True, default=str)
    assert a != b, (
        "minimal_globals is now deterministic -- if that was deliberate, "
        "update this test and "
        "docs/inbox/famgen-determinism.d/794-load-path.md; the three "
        "certified bases are its other caller (hard rule 4), so the change "
        "needs a viewer round, not just a green suite")
    # and name WHICH fields move, so a future reader does not have to
    # re-derive it (they are nested under BasicFileInfo, not top level)
    ga, gb = json.loads(a)["BasicFileInfo"], json.loads(b)["BasicFileInfo"]
    moved = {k for k in ga if ga[k] != gb.get(k)}
    assert moved == {"unique_document_guid", "central_episode_guid"}, moved
