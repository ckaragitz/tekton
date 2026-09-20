"""test_famload_determinism_794.py -- two identical family LOADS produce
byte-identical projects (#794).

#168 made the family **build** reproducible. The **load** path was left alone
on purpose, because none of it executes for a build -- and it minted `uuid4`,
so two identical loads produced two different `.rvt` files. That is the half a
user meets more often: `add_to_project` and the whole `rfa -> rvt` lane come
through here.

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

def test_the_same_family_into_the_same_host_derives_the_same_guids():
    a = FL.load_doc_guid("h" * 64, "fam-content-guid")
    b = FL.load_doc_guid("h" * 64, "fam-content-guid")
    assert a == b
    assert (FL.load_session_guid_hex("h" * 64, "fam-content-guid")
            == FL.load_session_guid_hex("h" * 64, "fam-content-guid"))


def test_TWO_DIFFERENT_families_in_one_host_get_DIFFERENT_guids():
    """The property a naive 'hash the host' derivation breaks.

    Both families see the same host digest, so if the family half were
    missing from the key they would collide -- two Family elements in one
    project claiming one family-document identity.
    """
    host = "h" * 64
    assert FL.load_doc_guid(host, "fam-A") != FL.load_doc_guid(host, "fam-B")
    assert (FL.load_session_guid_hex(host, "fam-A")
            != FL.load_session_guid_hex(host, "fam-B"))


def test_one_family_into_TWO_DIFFERENT_hosts_gets_different_guids():
    assert FL.load_doc_guid("h" * 64, "fam") != FL.load_doc_guid("k" * 64, "fam")


def test_the_host_half_of_the_key_is_CONTENT_not_a_path(tmp_path):
    """A path-keyed derivation makes the output depend on where the file
    sits, which is exactly the false reading #168's first probe produced."""
    import shutil
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir(), two.mkdir()
    a, b = str(one / "host.rvt"), str(two / "elsewhere.rvt")
    shutil.copyfile(HOST, a)
    shutil.copyfile(HOST, b)
    assert FL.host_digest(a) == FL.host_digest(b)
    assert FL.host_digest(a) == FL.host_digest(HOST)


def test_the_surveyed_host_carries_its_digest():
    ctx = FL.survey_host(HOST)
    assert ctx.digest == FL.host_digest(HOST)
    assert len(ctx.digest) == 64


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
    """
    import inspect
    from rvt.genesis import skeleton as GSK
    src = inspect.getsource(GSK.minimal_globals)
    assert "uuid4()" in src, (
        "minimal_globals no longer mints -- if that was deliberate, update "
        "this test and docs/inbox/famgen-determinism.d/794-load-path.md; the "
        "certified bases are its other caller (hard rule 4)")
