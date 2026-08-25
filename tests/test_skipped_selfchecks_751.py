"""tests/test_skipped_selfchecks_751.py -- a skipped validator is SAID, never
reported as a pass (issue #751, follow-up of #185 / #748).

Before: a create-route job run with ``--no-validate`` (or a ``--stages`` subset
without V) emitted its files, gated nothing, and ``_rollup_status`` still printed
``PROOF-ONLY (self-checks PASS; ...)`` -- its self-check clause was only tested
when ``build.validation`` was non-empty.  Meanwhile ``report.validation`` said
``NOT-RUN`` on the create routes but ``SKIPPED`` on the edit route for the same
situation, and the job runner's status read ``(hard gates PASSED)`` with the
validator counted as passed.  A status line is relayed verbatim by the skills
(hard rule 1's honesty stamps); "PASS" for a check that never ran is the one
thing it must not say.

Now the build stage records WHY it gated nothing (``BuildResult.validation_skipped``
= the reason, in ``manifest["build"]``), the status reads ``... (self-checks
SKIPPED: <reason>; ...)``, MANIFEST.md carries the same line, ``release.this_file``
says ``self-checks-skipped``, the job runner says ``(hard gates PASSED; validation
SKIPPED: --no-validate)``, and ``report.validation.verdict`` is ONE word on every
route: ``SKIPPED`` over the emitted files the validator would have judged,
``NOT-RUN`` only when nothing was emitted.  A validated run keeps today's exact
strings byte for byte.

Fresh-clone safe (bundled base + in-repo catalog; no samples/, no viewer).
Run: .venv/bin/python -m pytest tests/test_skipped_selfchecks_751.py -q
"""
from __future__ import annotations

import pytest

from conftest import pinned_base
import rvt.frontdoor as FD
from rvt import versions as V
from rvt.frontdoor import manifest as MF

NO_VALIDATION = {"verdict": "NOT-RUN", "errors": 0, "warnings": 0, "self_checks_ok": False, "files": 0}
PASS_STATUS = "PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)"
EDIT_STATUS = "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)"           # rvt_job's, verbatim
PROMPT = "create an eaton panel for me with 6 switches"                   # one panel: ~1 s a build


def _skipped(n_files):
    return {**NO_VALIDATION, "verdict": "SKIPPED", "files": n_files}


def _gated(verdict="VALID", n_err=0, n_warn=1, ok=True):
    return {"validate": {"verdict": verdict, "n_errors": n_err, "n_warnings": n_warn}, "self_checks_ok": ok}


def _manifest(*, validation, skipped=None, files=("combined",), stamps=("PROOF-ONLY, NOT-DELIVERABLE",)):
    return {"build": {"files": {r: {} for r in files}, "validation": validation,
                      "validation_skipped": skipped, "status_gate": {}, "errors": []},
            "honesty": {"proof_only_stamps": list(stamps)}}


# ---------------------------------------------------------------------------
# the status line (pure)
# ---------------------------------------------------------------------------

def test_skipped_validator_is_named_in_the_status_never_pass():
    assert MF._rollup_status(_manifest(validation={}, skipped="--no-validate")) == (
        "PROOF-ONLY (self-checks SKIPPED: --no-validate; see honesty.proof_only_stamps + status_gate)")
    assert MF._rollup_status(_manifest(validation={}, skipped="stage V not in --stages FLWEC", stamps=())) == \
        "BUILT (self-checks SKIPPED: stage V not in --stages FLWEC)"
    # no reason recorded at all: still SKIPPED, with the honest default
    assert MF._rollup_status(_manifest(validation={}, stamps=())) == \
        "BUILT (self-checks SKIPPED: validator did not run)"


def test_a_gated_run_keeps_todays_exact_strings():
    assert MF._rollup_status(_manifest(validation={"combined": _gated()})) == PASS_STATUS
    assert MF._rollup_status(_manifest(validation={"combined": _gated()}, stamps=())) == "BUILT (self-checks PASS)"
    assert MF._rollup_status(_manifest(validation={"combined": _gated("INVALID", 2, 0, ok=False)})) == \
        "SELF-CHECKS FAILED (combined)"
    assert MF._rollup_status({"build": {"files": {}, "validation": {}, "errors": []}}) == \
        "NO-OUTPUT (see build.degradations / errors)"


# ---------------------------------------------------------------------------
# report.validation: ONE word on every route
# ---------------------------------------------------------------------------

def test_create_summary_is_skipped_over_the_emitted_files_and_not_run_when_none():
    assert MF._build_validation_summary({}, emitted={"combined": {}}) == _skipped(1)
    assert MF._build_validation_summary({}, emitted={"shell": {}, "equipment": {}}) == _skipped(2)
    assert MF._build_validation_summary({}, emitted={}) == NO_VALIDATION
    assert MF._build_validation_summary({"combined": _gated()}, emitted={"combined": {}}) == {
        "verdict": "VALID", "errors": 0, "warnings": 1, "self_checks_ok": True, "files": 1}


@pytest.mark.parametrize("gate, has_output, expect", [
    ({"status": "SKIPPED", "reason": "--no-validate"}, True, _skipped(1)),   # rvt_job's --no-validate gate
    ({}, True, _skipped(1)),                                                 # output but no gate record
    ({"status": "SKIPPED", "reason": "--no-validate"}, False, NO_VALIDATION),
])
def test_edit_summary_uses_the_same_words(gate, has_output, expect):
    assert MF._edit_validation_summary(gate, hard_gates_passed=True, has_output=has_output) == expect


# ---------------------------------------------------------------------------
# end to end on the bundled base
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    pinned_base(V.LATEST_RELEASE)
    root = tmp_path_factory.mktemp("skipped_751")
    nov = FD.author(prompt=PROMPT, out=str(root / "nov"), no_validate=True, no_handoff=True)
    val = FD.author(prompt=PROMPT, out=str(root / "val"), no_handoff=True)
    return nov, val


def test_no_validate_build_says_skipped_everywhere(built):
    nov, val = built
    assert nov.ok and val.ok, (nov.status, val.status, nov.errors, val.errors)
    assert nov.status == "PROOF-ONLY (self-checks SKIPPED: --no-validate; see honesty.proof_only_stamps + status_gate)"
    assert val.status == PASS_STATUS
    b = nov.manifest["build"]
    assert b["validation"] == {} and b["validation_skipped"] == "--no-validate"
    assert list(b["files"]) == ["combined"]
    assert nov.manifest["report"]["validation"] == _skipped(1) == nov.as_json()["report"]["validation"]
    assert "validation SKIPPED (--no-validate): this is NOT a shippable run" in b["degradations"]
    assert nov.as_json()["release"]["this_file"].startswith("self-checks-skipped")
    md = open(nov.manifest_paths["md"], encoding="utf-8").read()
    assert "self-checks SKIPPED** (--no-validate)" in md and "self-checks PASS" not in md
    # the gated twin: unchanged shape, verdict from the validator
    assert val.manifest["build"]["validation_skipped"] is None
    assert val.manifest["report"]["validation"]["verdict"] == "VALID"
    assert val.as_json()["release"]["this_file"].startswith("validated-not-certified")
    assert "self-checks PASS" in open(val.manifest_paths["md"], encoding="utf-8").read()


def test_stages_without_v_is_skipped_with_its_own_reason(built, tmp_path):
    r = FD.author(prompt=PROMPT, out=str(tmp_path / "s"), stages="FLWEC", no_handoff=True)
    assert r.ok, (r.status, r.errors)
    assert r.status == ("PROOF-ONLY (self-checks SKIPPED: stage V not in --stages FLWEC; "
                        "see honesty.proof_only_stamps + status_gate)")
    assert r.manifest["build"]["validation_skipped"] == "stage V not in --stages FLWEC"
    assert r.manifest["report"]["validation"] == _skipped(1)
    assert any(d.startswith("validation SKIPPED (stage V not in --stages FLWEC)")
               for d in r.manifest["build"]["degradations"])


def test_no_validate_edit_names_the_skip_in_its_status(built, tmp_path):
    _nov, val = built
    e = FD.author(rvt=val.files["combined"], edit="move PP-1 to 3,1,0", out=str(tmp_path / "e"),
                  no_validate=True)
    assert e.ok, (e.status, e.errors)
    assert e.status == EDIT_STATUS[:-1] + "; validation SKIPPED: --no-validate)"
    assert e.manifest["report"]["validation"] == _skipped(1)
    assert e.as_json()["release"]["this_file"].startswith("self-checks-skipped")
