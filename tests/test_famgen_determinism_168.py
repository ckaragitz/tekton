"""test_famgen_determinism_168.py -- two identical family builds produce
byte-identical files (#168).

WHY THIS MATTERS MORE THAN IT LOOKS.  Determinism is not tidiness here; it is
the precondition for every claim this repo makes about a family.  Provenance
and certification both lean on sha256-pinned artifacts, so a file that changes
on every run cannot be pinned in a manifest or cached -- but the expensive one
is evidence discipline (CLAUDE.md section 4): *every* experiment here compares
two builds, and "otherwise byte-identical" is not a statement anyone can make
about a `.rfa` that is different every time.  #787 DONE 4 asks for exactly
such a pair.

WHAT WAS ACTUALLY NON-DETERMINISTIC -- measured by instrumenting `uuid.uuid4`
and running the job, not by grepping, because the issue's cited line numbers
were five weeks stale and named the wrong set (it listed seven sites, three of
which are the LOAD path and never execute for a family build):

  * `famgen.skeleton.new_family_document` -- the document GUID
  * `genesis.skeleton.minimal_globals`    -- the episode and workset GUIDs
  * `famgen.skeleton.build_part_atom`     -- a WALL-CLOCK `<updated>` stamp

The third is the half the issue missed, and it is why the fix is not just
"use uuid5".  Pinning every GUID and rebuilding still differed:

    @0x05385  a: ...<updated>2026-09-14T01:19:43Z</updated>...
              b: ...<updated>2026-09-14T01:19:44Z</updated>...

Two builds one second apart.  A test written to the issue's DONE would have
passed inside a single second and certified a lie.

THE PROBE'S OWN BUG, kept in mind by every case below: the first version of
that experiment wrote `pin_a.rfa` and `pin_b.rfa`, and the output filename
legitimately appears in the file (last-save path, PartAtom title).  Two
variables.  So these tests write the SAME filename in DIFFERENT directories.
"""
import json
import os
import subprocess
import sys

import pytest

from rvt.famgen import skeleton as SK

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")

#: the flagship job, as the issue names it
JOB = ["panelboard", "--mains", "400", "--spaces", "42", "--voltage", "480Y/277"]


def _needs_base():
    if not os.path.isfile(BASE):
        pytest.skip("bundled genesis base not in this clone")


def _doc(name="Panelboard 480Y/277 400A MLO 42ckt Surface", **kw):
    kw.setdefault("part_type", SK.PART_TYPE["panelboard"])
    return SK.new_family_document("electrical_equipment", name, **kw)


# ---------------------------------------------------------------------------
# (1) the derivation itself
# ---------------------------------------------------------------------------

def test_the_same_spec_derives_the_same_document_guid():
    assert _doc().document_guid == _doc().document_guid


@pytest.mark.parametrize("kw", [
    {"name": "Panelboard 480Y/277 600A MLO 42ckt Surface"},   # a different spec
    {"host": "wall"},
    {"start_id": 2000},
    {"origin": (1.0, 0.0, 0.0)},
    {"work_plane_based": True},
    {"with_views": False},
])
def test_a_different_spec_derives_a_different_document_guid(kw):
    """Every field of the canonical key must actually be IN the key.

    A derivation that quietly ignores one collapses two real documents onto
    one GUID -- which is worse than the uuid4 it replaced, because it is
    silent and stable.
    """
    assert _doc(**kw).document_guid != _doc().document_guid


def test_two_documents_that_differ_only_AFTER_creation_still_differ():
    """THE case the creation-time key could not see, and the reason the GUID
    is sealed from CONTENT at ``finalize``.

    ``family_document_guid`` runs inside ``new_family_document``, before any
    parameter, type, shared-parameter binding or solid exists. Two documents
    identical at that moment and different afterwards therefore shared a
    GUID -- silently and stably, which the module's own docstring calls
    worse than the uuid4 it replaced.

    Measured by the #168 review on the real CLI: the same panelboard built
    with and without ``--shared-params`` differed in 11 bound shared
    parameters and in sha256, and carried the SAME ``document_guid``,
    ``episode_guid`` and ``unique_document_guid``. The parametrisation above
    never varied anything post-creation, so it could not catch it.
    """
    a, b = _doc(), _doc()
    assert a.document_guid == b.document_guid, "identical at creation"
    b.add_family_parameter("Probe Only On B", SK.PARAM_TYPE_LENGTH
                           if hasattr(SK, "PARAM_TYPE_LENGTH") else 1)
    a.finalize()
    b.finalize()
    assert a.document_guid != b.document_guid, (
        "two documents that differ only in content added after creation "
        "still share a GUID -- the seal at finalize is not working")
    assert SK.family_episode_guid(a.document_guid) != \
        SK.family_episode_guid(b.document_guid)


def test_the_content_seal_is_idempotent_and_respects_a_callers_guid():
    given = "12345678-1234-5678-1234-567812345678"
    d = _doc(document_guid=given).finalize()
    assert d.document_guid == given, "a supplied GUID must never be resealed"
    e = _doc().finalize()
    once = e.document_guid
    e.finalize()
    assert e.document_guid == once, "finalize is idempotent; the GUID must not move"


def test_the_episode_and_workset_guids_are_derived_and_distinct():
    g = _doc().document_guid
    ep, ws = SK.family_episode_guid(g), SK.family_workset_guid(g)
    assert ep == SK.family_episode_guid(g), "must be a function, not a mint"
    assert len({g, ep, ws}) == 3, "a document, its episode and its workset " \
                                  "must not share one GUID"


def test_an_explicit_document_guid_still_wins():
    given = "12345678-1234-5678-1234-567812345678"
    d = _doc(document_guid=given)
    assert d.document_guid == given
    assert d.guid_source == "caller", \
        "the report must not claim a caller's GUID is reproducible"


def test_a_derived_document_says_so():
    assert _doc().guid_source == "derived"


# ---------------------------------------------------------------------------
# (2) the stamp -- the half the issue missed
# ---------------------------------------------------------------------------

def test_the_part_atom_stamp_is_stable_by_default(monkeypatch):
    monkeypatch.delenv(SK.SOURCE_DATE_EPOCH, raising=False)
    assert SK.stable_updated_stamp() == SK.EPOCH_STAMP
    a = SK.build_part_atom("T", "Electrical Equipment")
    b = SK.build_part_atom("T", "Electrical Equipment")
    assert a == b, "two PartAtoms for one family must be byte-identical"
    assert SK.EPOCH_STAMP.encode() in a


@pytest.mark.parametrize("value,stamp_source", [
    ("1700000000", "SOURCE_DATE_EPOCH"),
    ("not-a-number", "fixed"),
    ("", "fixed"),
    ("9" * 40, "fixed"),
])
def test_the_REPORT_names_the_mechanism_that_actually_produced_the_stamp(
        value, stamp_source, monkeypatch):
    """The report used to test whether the variable was SET, not whether it
    PARSED, so ``SOURCE_DATE_EPOCH=not-a-number`` fell back to the fixed
    stamp while the report claimed the environment supplied it (#168
    review). A false provenance line in a report this repo treats as
    evidence is the same class of error as a stale test count.

    Asserted through ``_determinism_report`` -- the CONSUMER that had the
    bug -- not through the helper the fix added. The first version of this
    test called ``stable_updated_stamp_with_source()`` directly and passed
    with the report's own line reverted: it tested the new code instead of
    the old defect, which is no test at all.
    """
    from rvt.famgen import famdoc_adoc as FA
    monkeypatch.setenv(SK.SOURCE_DATE_EPOCH, value)
    doc = _doc()
    assert FA._determinism_report(doc)["updated_stamp"] == stamp_source
    # and the stamp itself agrees with what the report says produced it
    stamp, src = SK.stable_updated_stamp_with_source()
    assert src == stamp_source
    assert (stamp == SK.EPOCH_STAMP) == (stamp_source == "fixed")


def test_source_date_epoch_is_honoured(monkeypatch):
    """The cross-ecosystem convention for exactly this (reproducible-builds
    .org), so a build system that already sets it gets a real date free."""
    monkeypatch.setenv(SK.SOURCE_DATE_EPOCH, "1700000000")
    assert SK.stable_updated_stamp() == "2023-11-14T22:13:20Z"


@pytest.mark.parametrize("bad", ["", "   ", "not-a-number", "9" * 40, "-1e999"])
def test_a_malformed_source_date_epoch_does_not_break_the_build(bad, monkeypatch):
    """Hard rule 1: a junk environment variable is not a reason to withhold
    a file.  It falls back to the fixed stamp, which is still stable."""
    monkeypatch.setenv(SK.SOURCE_DATE_EPOCH, bad)
    assert SK.stable_updated_stamp() == SK.EPOCH_STAMP


def test_an_explicit_updated_stamp_still_wins():
    atom = SK.build_part_atom("T", "Electrical Equipment",
                              updated="2026-01-02T03:04:05Z")
    assert b"2026-01-02T03:04:05Z" in atom


# ---------------------------------------------------------------------------
# (3) genesis is UNTOUCHED -- the guard on the blast radius
# ---------------------------------------------------------------------------

def test_minimal_globals_still_mints_its_own_guids_by_default():
    """The fix derives the episode/workset GUIDs in ``FamilyDoc`` and PASSES
    them down, deliberately NOT by changing ``minimal_globals``' defaults.

    That function is shared with the genesis compose path, whose output is
    the three CERTIFIED bases (hard rule 4).  Making the family path
    reproducible must not move a byte of genesis, and this is the test that
    fails if someone later "tidies" the derivation down into the shared
    function.
    """
    from rvt.genesis import skeleton as GSK
    a = GSK.minimal_globals([])["_ids"]
    b = GSK.minimal_globals([])["_ids"]
    assert a["document_guid"] != b["document_guid"], \
        "genesis' own default changed -- the compose path is no longer what " \
        "produced the certified bases"


# ---------------------------------------------------------------------------
# (4) end to end: the file itself
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_two_cli_runs_produce_byte_identical_files(tmp_path):
    """The claim the issue actually makes, through the CLI a user runs.

    SAME filename, DIFFERENT directories -- the output path is written into
    the file (last-save path, PartAtom title), so two different names would
    put a second variable in the experiment.  That is exactly how the first
    draft of this probe reported a false difference.
    """
    _needs_base()
    outs = []
    for d in ("r1", "r2"):
        (tmp_path / d).mkdir()
        out = tmp_path / d / "panel.rfa"
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        env.pop(SK.SOURCE_DATE_EPOCH, None)
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "make_family.py")]
            + JOB + ["--out", str(out)],
            cwd=ROOT, env=env, capture_output=True, text=True)
        assert out.is_file(), "build failed:\n%s\n%s" % (r.stdout[-2000:],
                                                         r.stderr[-2000:])
        outs.append(out.read_bytes())
    assert outs[0] == outs[1], (
        "two identical CLI runs differ at byte %d"
        % next((i for i, (x, y) in enumerate(zip(*outs)) if x != y), -1))


@pytest.mark.slow
def test_the_report_names_where_the_identity_came_from(tmp_path):
    _needs_base()
    out = tmp_path / "panel.rfa"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    env.pop(SK.SOURCE_DATE_EPOCH, None)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py")]
                   + JOB + ["--out", str(out)],
                   cwd=ROOT, env=env, capture_output=True, text=True)
    rep = json.loads((tmp_path / "panel.json").read_text())
    det = rep["emit"]["determinism"]
    assert det["deterministic"] is True
    assert det["document_guid"] == "derived"
    assert det["updated_stamp"] == "fixed"
    assert rep["provenance"]["checks"]["identity_is_ours"] is True, \
        "determinism must not have cost us our own identity block (G2)"
    # `validate` nests per-mode verdicts; family_mode is the one that judges
    # a .rfa (arbiter_raw deliberately reports the project-schema view too)
    assert rep["validate"]["family_mode"]["n_errors"] == 0, \
        rep["validate"]["family_mode"]["errors"][:3]
