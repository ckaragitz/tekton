"""test_edit_status.py -- when ``author --rvt FILE --edit ...`` never gets to
run the edit (the file cannot be opened / planned, the edit sentence is not
understood, the run raised) the manifest's STATUS sentence names the reason
-- ``FAILED (<errors[0]>)`` like the create routes -- instead of the opaque
``FAILED (edit did not complete: rc None)`` a skill session used to relay
verbatim (issue #559).  Everything else about the envelope stays put: exit 3
at the CLI, one JSON document on stdout, nothing on stderr, ``errors[0]``
whole, ``edit.rc`` unchanged; a job that DID run and returned rc != 0 keeps
``FAILED (edit did not complete: rc N)``; the refused / UNVERIFIED-RELEASE
composition and every successful (PROOF-ONLY) status are byte-identical.

Sample-free: the "cannot open" inputs are a 64 KB truncation of the tracked
native-release genesis pin, the same truncation of the certified 2025 pin,
and a schema-damaged copy of the 2025 pin, written under a deliberately long
(>= 120 character) tmp directory: the sentence names the input by basename
so the reason survives the status cut, while the absolute path stays in the
manifest's ``inputs.rvt`` (issue #573); the reason itself rides as short
clauses -- a host whose own class schema cannot be read says THAT inside the
cut (the open failure once when it is the same error, as a second finding
after it when it is not, #587), and the layers' whole errors follow in
``errors[1]`` (issue #574).  The grammar miss and the good edit run on the
2025 pin itself.  Fresh-clone runnable (CI shard drop-in
tests/ci_shard.d/559-edit-status.txt).

Run: .venv/bin/python -m pytest tests/test_edit_status.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import pinned_base, rewrite_stream, truncated_copy, zero_schema_bytes   # noqa: E402
import rvt.frontdoor as FD                                   # noqa: E402
from rvt import versions as V                                # noqa: E402
from rvt.frontdoor import input_release as IR                # noqa: E402
from rvt.frontdoor import manifest as MF                     # noqa: E402

GRAMMAR_MISS = "set level L1 elevation 3.5"          # no `to`, no unit: not in the grammar
GOOD_EDIT = "set level 311 elevation to 1 ft"        # "L1 - Ground Floor", on every pin
GOOD_STATUS = "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)"   # main's, verbatim
LONG_DIR_MIN = 120                                   # a cloud / tmp upload path is about this long


@pytest.fixture(scope="module")
def long_dir(tmp_path_factory):
    """A directory whose absolute path is >= LONG_DIR_MIN characters."""
    d = str(tmp_path_factory.mktemp("edit_status"))
    while len(d) < LONG_DIR_MIN:
        d = os.path.join(d, "a-deliberately-long-directory-name-573")
    os.makedirs(d, exist_ok=True)
    assert len(d) >= LONG_DIR_MIN
    return d


@pytest.fixture(scope="module")
def trunc64k(long_dir):
    """The NATIVE pin cut at 64 KB (a valid CFB header, its release still
    detected, broken streams) -- no release context is involved for a
    native host, so the walker's finding is the whole reason on its own."""
    return truncated_copy(pinned_base(V.LATEST_RELEASE), os.path.join(long_dir, "trunc64k.rvt"), 65536)


@pytest.fixture(scope="module")
def trunc64k_2025(long_dir):
    """The 2025 pin cut at 64 KB: the open fails on the walker AND the host
    cannot be probed (its ``Formats/Latest`` inflates to nothing) -- two
    findings, both owed inside the cut (#587)."""
    return truncated_copy(pinned_base(2025), os.path.join(long_dir, "trunc64k_2025.rvt"), 65536)


@pytest.fixture(scope="module")
def schema_dmg(long_dir):
    """The 2025 pin re-emitted with 64 bytes of its ``Formats/Latest`` zeroed
    -- every other entry byte-identical."""
    return rewrite_stream(pinned_base(2025), os.path.join(long_dir, "schema_dmg.rvt"), "Formats/Latest", zero_schema_bytes)


def _assert_named_not_pathed(man: dict, src: str, *reason_words: str):
    """The #573/#574 contract for a host that cannot be opened / planned, read
    off its ``manifest.json``: every sentence names the input by basename,
    the reason words sit inside the status cut, and the absolute path lives
    on in ``inputs.rvt`` -- and only there."""
    named = f"cannot open/plan {os.path.basename(src)}: "
    status, errors = man["status"], man["errors"]
    for e in errors:
        assert e.startswith(named), e[:200]
    assert status.startswith(f"FAILED ({named}"), status
    assert len(status) <= len("FAILED ()") + MF._STATUS_REASON_MAX
    assert os.path.dirname(src) not in " ".join([status, *errors])   # the path no longer eats the budget ...
    for w in reason_words:                                     # ... so the reason rides inside the cut
        assert w in status, (w, status)
    assert man["inputs"]["rvt"] == src == man["base"]["input_file"]   # nothing lost: the full path, where it lived
    assert man["edit"]["rc"] is None and man["edit"]["spec"] == {"error": errors[:1]}


def _edit_manifest(**kw):
    args = dict(inputs={"rvt": "x.rvt", "edit": "e"}, base_note="n", out_dir="o",
                edit_spec={}, run={}, errors=None)
    args.update(kw)
    return MF.edit_manifest(**args)


# ---------------------------------------------------------------------------
# the roll-up itself (pure: no file opened)
# ---------------------------------------------------------------------------

def test_job_never_started_status_is_the_reason():
    reason = "cannot open/plan x.rvt: RuntimeError: Partitions/20: walker errors ['no trailer']"
    m = _edit_manifest(errors=[reason, "second"])
    assert m["status"] == f"FAILED ({reason})"
    assert m["errors"] == [reason, "second"]
    assert m["edit"]["rc"] is None
    # a partial `run` with no rc is still "never started", not "rc None"
    assert _edit_manifest(errors=[reason], run={"degradations": []})["status"] == f"FAILED ({reason})"


def test_long_reason_is_cut_at_a_word_boundary_within_the_limit():
    words = "edit not understood: " + " ".join(f"clause{i:02d}," for i in range(40))
    status = _edit_manifest(errors=[words])["status"]
    assert status.startswith("FAILED (edit not understood: ")
    assert status.endswith("...)")
    reason = status[len("FAILED ("):-1]
    assert len(reason) <= MF._STATUS_REASON_MAX
    kept = reason[:-3]                                     # what precedes the "..."
    assert words.startswith(kept)
    assert words[len(kept)] in " ,"                        # cut on a boundary, never mid-word
    # a reason with no boundary to cut on is still bounded (the one hard cut)
    reason = _edit_manifest(errors=["x" * 400])["status"][len("FAILED ("):-1]
    assert len(reason) == MF._STATUS_REASON_MAX
    # multi-line reasons ride as one line
    assert _edit_manifest(errors=["a\nb  c"])["status"] == "FAILED (a b c)"
    # and the cut is THE clip rule (rvt._clause), not a copy that can drift again (#587)
    from rvt._clause import clip
    assert MF._status_reason(words) == clip(words, MF._STATUS_REASON_MAX)


def test_job_that_ran_and_failed_keeps_its_rc_sentence():
    assert _edit_manifest(run={"rc": 5})["status"] == "FAILED (edit did not complete: rc 5)"
    assert _edit_manifest(run={"rc": 5}, errors=["late"])["status"] == \
        "FAILED (edit did not complete: rc 5)"
    assert _edit_manifest(run={"rc": 0, "job_manifest": {"status": GOOD_STATUS}})["status"] == \
        GOOD_STATUS


def test_refused_and_unverified_composition_unchanged():
    line = IR.REFUSED_PREFIX + " their.rvt is not a Revit file"
    m = _edit_manifest(errors=[line], input_release={"status": "refused", "line": line})
    assert m["status"] == line
    assert m["honesty"]["release"] == line
    m = _edit_manifest(errors=["cannot open/plan y.rvt: boom"],
                       input_release={"status": "unverified", "year": 2031,
                                      "stamp": IR.UNVERIFIED_STAMP})
    assert m["status"] == f"FAILED (cannot open/plan y.rvt: boom); {IR.UNVERIFIED_TAG} (input Revit 2031)"


# ---------------------------------------------------------------------------
# the route, in process: an edit sentence the grammar does not parse
# ---------------------------------------------------------------------------

def test_grammar_miss_status_names_the_reason(tmp_path):
    r = FD.author(rvt=pinned_base(2025), edit=GRAMMAR_MISS, out=str(tmp_path / "job"))
    assert r.ok is False
    assert not r.files
    assert r.status.startswith("FAILED (edit not understood: "), r.status
    assert "rc None" not in r.status
    assert r.errors[0].startswith("edit not understood: ")
    assert GRAMMAR_MISS in r.errors[0]                     # errors[0] stays whole
    man = json.loads((tmp_path / "job" / "manifest.json").read_text())
    assert man["status"] == r.status and man["errors"] == r.errors
    assert man["edit"]["rc"] is None and man["edit"]["spec"] == {"error": r.errors[:1]}
    md = (tmp_path / "job" / "MANIFEST.md").read_text()
    assert f"**Status:** {r.status}" in md


# ---------------------------------------------------------------------------
# the CLI, as a skill session runs it: a host that cannot be opened
# ---------------------------------------------------------------------------

def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "frontdoor.py"),
                           "author", *args, "--json"], capture_output=True, text=True)


def test_cli_unopenable_host_exit_3_one_json_reason_in_status(trunc64k, tmp_path):
    p = _cli("--rvt", trunc64k, "--edit", "move DP-1 to 3,1,4.66", "--out", str(tmp_path / "j"))
    assert p.returncode == 3, (p.returncode, p.stderr[-600:])
    assert p.stderr == ""
    doc = json.loads(p.stdout)                             # ONE strict JSON document
    assert doc["ok"] is False and doc["route"] == "rvt"
    man = json.loads((tmp_path / "j" / "manifest.json").read_text())
    assert (doc["status"], doc["errors"]) == (man["status"], man["errors"])
    _assert_named_not_pathed(man, trunc64k, "RuntimeError", "walker errors")
    assert len(man["errors"]) == 1                         # nothing was cut: no second, whole entry needed


# ---------------------------------------------------------------------------
# the route, in process: a 2025 host whose own class schema does not parse
# ---------------------------------------------------------------------------

def test_schema_damaged_host_status_says_its_schema_cannot_be_read(schema_dmg, tmp_path):
    r = FD.author(rvt=schema_dmg, edit=GOOD_EDIT, out=str(tmp_path / "s"))
    assert r.ok is False and not r.files
    man = json.loads((tmp_path / "s" / "manifest.json").read_text())
    assert (r.status, r.errors) == (man["status"], man["errors"])
    # the host could not even be probed: THAT is the sentence, whole, in words (no byte dump) ...
    _assert_named_not_pathed(man, schema_dmg, "its Formats/Latest class schema cannot be read",
                             "(ParseError: parse error at 0x")
    assert man["status"] == f"FAILED ({r.errors[0]})" and "@0x" not in r.errors[0]
    whole, = r.errors[1:]                       # ... and every layer's words ride whole, once, behind it
    assert whole.startswith("cannot open/plan schema_dmg.rvt: ParseError: parse error at 0x") and " | " in whole
    assert "(no release context for schema_dmg.rvt: its Formats/Latest class schema cannot be read " \
        "(ParseError: " in whole and "; read side: own schema unreadable (ParseError: " in whole
    assert f"**Status:** {r.status}" in (tmp_path / "s" / "MANIFEST.md").read_text()


def test_truncated_foreign_host_status_carries_both_findings(trunc64k_2025, tmp_path):
    """The open fails on the walker; the release probe fails on the (empty)
    schema stream: the status leads with what could not be read and names
    the error that stopped the open after it -- both inside the cut -- and
    every layer's whole words (the empty/truncated-schema sentence included)
    ride once behind it in ``errors[1]`` (#587)."""
    r = FD.author(rvt=trunc64k_2025, edit=GOOD_EDIT, out=str(tmp_path / "t"))
    assert r.ok is False and not r.files
    man = json.loads((tmp_path / "t" / "manifest.json").read_text())
    assert (r.status, r.errors) == (man["status"], man["errors"])
    _assert_named_not_pathed(man, trunc64k_2025, "its Formats/Latest class schema cannot be read; ",
                             "RuntimeError: ", "walker errors")
    whole, = r.errors[1:]
    assert whole.startswith("cannot open/plan trunc64k_2025.rvt: RuntimeError: Partitions/")
    assert "(no release context for trunc64k_2025.rvt: its Formats/Latest class schema cannot be read " \
        "(ParseError: " in whole and "; read side: own schema unreadable (ParseError: " in whole
    assert "truncated schema stream)" in whole and "..." not in whole   # the parser's one sentence, whole (#569)


def test_good_edit_status_unchanged(tmp_path):
    r = FD.author(rvt=pinned_base(2025), edit=GOOD_EDIT, out=str(tmp_path / "g"))
    assert r.ok is True, (r.status, r.errors)              # rc 0 at the CLI
    assert r.status == GOOD_STATUS
    assert os.path.isfile(r.files["edited"])
