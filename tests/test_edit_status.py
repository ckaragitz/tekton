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

Sample-free: the "cannot open" input is a 64 KB truncation of the tracked,
certified 2025 genesis pin written into ``tmp_path``; the grammar miss and
the good edit run on the pin itself.  Fresh-clone runnable (CI shard drop-in
tests/ci_shard.d/559-edit-status.txt).

Run: .venv/bin/python -m pytest tests/test_edit_status.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import pinned_base                             # noqa: E402
import rvt.frontdoor as FD                                   # noqa: E402
from rvt.frontdoor import input_release as IR                # noqa: E402
from rvt.frontdoor import manifest as MF                     # noqa: E402

GRAMMAR_MISS = "set level L1 elevation 3.5"          # no `to`, no unit: not in the grammar
GOOD_EDIT = "set level 311 elevation to 1 ft"        # "L1 - Ground Floor", on every pin
GOOD_STATUS = "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)"   # main's, verbatim


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


def test_cli_unopenable_host_exit_3_one_json_reason_in_status(tmp_path):
    src = tmp_path / "trunc64k.rvt"
    with open(pinned_base(2025), "rb") as fh:
        src.write_bytes(fh.read(64 * 1024))                 # a valid CFB header, broken streams
    p = _cli("--rvt", str(src), "--edit", "move DP-1 to 3,1,4.66", "--out", str(tmp_path / "j"))
    assert p.returncode == 3, (p.returncode, p.stderr[-600:])
    assert p.stderr == ""
    doc = json.loads(p.stdout)                             # ONE strict JSON document
    assert doc["ok"] is False and doc["route"] == "rvt"
    assert doc["status"].startswith("FAILED (cannot open/plan "), doc["status"]
    assert "rc None" not in doc["status"]
    assert len(doc["status"]) <= len("FAILED ()") + MF._STATUS_REASON_MAX
    assert doc["errors"][0].startswith("cannot open/plan ") and str(src) in doc["errors"][0]
    man = json.loads((tmp_path / "j" / "manifest.json").read_text())
    assert man["status"] == doc["status"] and man["edit"]["rc"] is None


def test_good_edit_status_unchanged(tmp_path):
    r = FD.author(rvt=pinned_base(2025), edit=GOOD_EDIT, out=str(tmp_path / "g"))
    assert r.ok is True, (r.status, r.errors)              # rc 0 at the CLI
    assert r.status == GOOD_STATUS
    assert os.path.isfile(r.files["edited"])
