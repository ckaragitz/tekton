"""tests/test_go_report_185.py -- the ONE front-door ``--json`` result carries a
compact ``report`` block (issue #185, epic #110 / steer #108: tool round-trips
and tokens per skill flow are product latency).

Before: ``AuthorResult.as_json()`` (what ``tools/frontdoor.py --json`` prints
and the plugin's ``go author`` relays under ``result``) named the files, the
status, the release story and the stamps, but tekton-author's "how to report"
steps also need the degradations, the validator summary and the counts -- which
lived only in ``manifest.json`` (45 KB for one panel, 150 KB for the 6-panel
room, 225 KB for the IFC example) or ``MANIFEST.md`` (9-14 KB): a second tool
call and thousands of tokens on every job.  Now each manifest builder stores
``manifest["report"]`` = {degradations, validation{verdict, errors, warnings,
self_checks_ok, files}, counts{...}} from the data it natively holds, and
``as_json()`` relays it as ``result.report`` -- same keys on the prompt / IFC /
edit routes and (empty but present, like ``stamps``) on a result with no
manifest; the whole result, in the indented form the CLI prints, stays under
4 KB for the flagship prompt.  Stamps and the target-version line keep their
#24 homes (``result.stamps``, ``result.release.line``) and are not said twice.

Pinned here: the block's assembly rules (zero-filled counts, budgeted
degradations: order kept, duplicates dropped, capped with a '+N more' tail),
both validation roll-ups (any non-VALID verdict wins, errors / warnings summed;
the edit gate's PASS / FAIL / SKIPPED said in the same words), MANIFEST.md's
"created:" line counting through the shared tally, ``as_json`` without a
manifest -- and, end to end on the bundled genesis base: the 6-panel prompt
(keys, numbers equal to the manifest's, manifest.json carries the same block,
the 4 KB budget in the CLI's ``indent=1`` form), an edit of that output, and a
FAILED IFC intake.

Fresh-clone safe (bundled base + in-repo catalog only; no samples/, no viewer).
Run: .venv/bin/python -m pytest tests/test_go_report_185.py -q
"""
from __future__ import annotations

import json
import os

import pytest

from conftest import ROOT, pinned_base
import rvt.frontdoor as FD
from rvt import _jsonsafe
from rvt import versions as V
from rvt.frontdoor import manifest as MF

FLAGSHIP = "an electrical room with 6 panels"
REPORT_KEYS = ["counts", "degradations", "validation"]
NO_VALIDATION = {"verdict": "NOT-RUN", "errors": 0, "warnings": 0, "self_checks_ok": False, "files": 0}
ZERO_COUNTS = dict.fromkeys(("families", "walls", "equipment_instances", "wiring_devices",
                             "loaded_families", "elements_created", "circuits", "edited", "deleted"), 0)
BUDGET = 4096                     # bytes of the whole --json result as the CLI prints it (#185 DONE 2)


def _rows(*kinds):
    return [{"kind": k, "tag": f"T{i}"} for i, k in enumerate(kinds)]


def _shipped_bytes(doc) -> int:
    """tools/frontdoor.py prints ``_jsonsafe.dumps(as_json(), indent=1)``; measure THAT."""
    return len(_jsonsafe.dumps(doc, indent=1).encode("utf-8"))


# ---------------------------------------------------------------------------
# assembly + roll-up rules (pure)
# ---------------------------------------------------------------------------

def test_empty_block_has_every_key_empty_but_present():
    r = MF.report_block()
    assert sorted(r) == REPORT_KEYS
    assert r == {"degradations": [], "validation": NO_VALIDATION, "counts": ZERO_COUNTS}
    json.dumps(r)                                                  # plain JSON types only


def test_counts_are_zero_filled_and_degradations_budgeted():
    many = [f"D-{i} NOT built" for i in range(MF.REPORT_DEGRADATIONS_CAP + 3)]
    r = MF.report_block(degradations=["walls NOT built: x", "walls NOT built: x", "y" * 900] + many,
                        counts={"walls": 4, "edited": 2})
    assert r["counts"] == {**ZERO_COUNTS, "walls": 4, "edited": 2}
    d = r["degradations"]
    assert d[0] == "walls NOT built: x" and d.count("walls NOT built: x") == 1      # order kept, dup dropped
    assert len(d[1]) <= MF._REPORT_DEGRADATION_MAX and d[1].endswith("...")        # one long line: clip's rule
    assert len(d) == MF.REPORT_DEGRADATIONS_CAP + 1 and d[-1].startswith("... +5 more degradation(s)")   # 15 unique, 10 kept


def test_build_validation_rolls_up_over_every_emitted_file():
    val = {"shell": {"validate": {"verdict": "VALID", "n_errors": 0, "n_warnings": 1}, "self_checks_ok": True},
           "equipment": {"validate": {"verdict": "INVALID", "n_errors": 2, "n_warnings": 0},
                         "self_checks_ok": False}}
    assert MF._build_validation_summary(val) == {"verdict": "INVALID", "errors": 2, "warnings": 1,
                                                 "self_checks_ok": False, "files": 2}
    val["equipment"] = {"validate": {"verdict": "VALID", "n_errors": 0, "n_warnings": 2}, "self_checks_ok": True}
    assert MF._build_validation_summary(val) == {"verdict": "VALID", "errors": 0, "warnings": 3,
                                                 "self_checks_ok": True, "files": 2}
    assert MF._build_validation_summary({}) == NO_VALIDATION == MF._build_validation_summary(None)


@pytest.mark.parametrize("status, verdict", [("PASS", "VALID"), ("FAIL", "INVALID"),
                                             ("SKIPPED", "SKIPPED"), (None, "NOT-RUN")])
def test_edit_validation_speaks_the_same_words(status, verdict):
    gate = {"status": status, "errors": 4, "warnings": 1} if status else {}
    # hard gates "pass" on SKIPPED too (`--no-validate`); self-checked means the validator PASSED;
    # a skipped validator found nothing, so its counts are zero whatever the gate carries (#751)
    got = MF._edit_validation_summary(gate, hard_gates_passed=status in ("PASS", "SKIPPED"),
                                      has_output=bool(status))
    ran = status in ("PASS", "FAIL")
    assert got == {"verdict": verdict, "errors": 4 if ran else 0, "warnings": 1 if ran else 0,
                   "self_checks_ok": status == "PASS", "files": 1 if status else 0}


def test_manifest_md_created_line_counts_through_the_shared_tally():
    rows = _rows("family(.rfa)", "family(.rfa)", "wall", "wall", "wall", "wall", "equipment-instance",
                 "equipment-instance", "loaded-family", "loaded-family", "fixture-instance")
    assert MF.created_counts(rows) == {"families": 2, "walls": 4, "equipment_instances": 2,
                                       "wiring_devices": 1, "loaded_families": 2}
    md = MF._render_md({"route": "prompt", "build": {"elements_created": rows}, "status": "BUILT"})
    assert "- created: 4 walls, 2 equipment instances, 1 wiring devices, 2 loaded families" in md


def test_as_json_carries_report_and_stamps_even_without_a_manifest():
    res = FD.AuthorResult(route="ifc", ok=False, status="FAILED (x)", out_dir="/nowhere", errors=["x"])
    j = res.as_json()
    assert j["report"] == MF.report_block() and j["stamps"] == []
    assert "release" not in j                                       # unchanged: the release view needs a manifest


# ---------------------------------------------------------------------------
# end to end on the bundled base: create, edit, FAILED -- ONE result each
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def flagship(tmp_path_factory):
    pinned_base(V.LATEST_RELEASE)                 # clean skip if the bundle is absent / overridden
    out = tmp_path_factory.mktemp("go_report_185") / "p6"
    return FD.author(prompt=FLAGSHIP, out=str(out))          # default handoff ON: the shipped shape


def test_flagship_result_carries_the_report_and_fits_the_budget(flagship):
    r = flagship
    assert r.ok, (r.status, r.errors)
    j = r.as_json()
    rep = j["report"]
    assert sorted(rep) == REPORT_KEYS
    assert _shipped_bytes(j) <= BUDGET, _shipped_bytes(j)
    # the numbers agree with the manifest the block summarises -- and the manifest carries the block itself
    build = r.manifest["build"]
    g = build["validation"]["combined"]["validate"]
    assert rep["validation"] == {"verdict": g["verdict"], "errors": g["n_errors"],
                                 "warnings": g["n_warnings"], "self_checks_ok": True, "files": 1}
    assert rep["validation"]["verdict"] == "VALID" and rep["validation"]["errors"] == 0
    assert rep["counts"] == {**ZERO_COUNTS, "families": 6, "equipment_instances": 6, "walls": 4,
                             "loaded_families": 6, "elements_created": len(build["elements_created"])}
    assert rep["degradations"] == MF._budgeted(build["degradations"])
    assert r.manifest["report"] == rep and r.manifest["report"] is not rep    # equal, never aliased
    with open(j["manifest"]["json"], encoding="utf-8") as fh:
        assert json.load(fh)["report"] == rep
    assert j["stamps"] and all("PROOF-ONLY" in s for s in j["stamps"])      # #24's homes, said once
    assert "proof_only_stamps" not in rep and "target_version_line" not in rep


def test_edit_route_fills_the_same_block(flagship, tmp_path):
    r = FD.author(rvt=flagship.files["combined"], edit="move PP-1 to 3,1,0", out=str(tmp_path / "e"))
    assert r.ok, (r.status, r.errors)
    j = r.as_json()
    rep = j["report"]
    assert sorted(rep) == REPORT_KEYS and r.manifest["report"] == rep
    gate = r.manifest["edit"]["gates"]["validation"]
    assert rep["validation"] == {"verdict": "VALID", "errors": gate["errors"], "warnings": gate["warnings"],
                                 "self_checks_ok": True, "files": 1}
    assert rep["counts"] == {**ZERO_COUNTS, "edited": 1}
    assert rep["degradations"] == MF._budgeted(r.manifest["edit"]["degradations"])
    assert _shipped_bytes(j) <= BUDGET


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")   # a real ifcopenshell's
def test_failed_intake_still_answers_with_the_block(tmp_path):                     # __del__ on a file it refused
    r = FD.author(ifc=os.path.join(ROOT, "tests", "conftest.py"), out=str(tmp_path / "f"))   # not an IFC
    assert r.ok is False and r.status.startswith("FAILED (")
    j = r.as_json()
    assert j["report"] == {"degradations": [], "validation": NO_VALIDATION, "counts": ZERO_COUNTS}
    assert j["stamps"] == [] and j["errors"]
