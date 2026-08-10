"""test_out_dir_guard.py -- the job's OWN out dir vs the research-input
tripwire (issue #425; ``rvt.frontdoor.standalone`` section 7).

The law under test, in one breath: the armed build may never READ anything
under this checkout's quarantine roots (``samples/ vendor/ extracted/
experiments/genesis/``) or any Autodesk installation directory -- exactly as
strict as before -- while a job whose ``--out`` merely lives under a
directory NAMED ``samples/`` somewhere else on the user's disk writes and
re-reads its own outputs freely; an ``--out`` INSIDE a real quarantine root
(or an Autodesk install dir) is refused up front with ONE line.

Stdlib + the package only (no build, no samples/): fresh-clone safe, in the
CI shard via tests/ci_shard.d/425-out-dir-guard.txt.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from rvt.frontdoor import standalone as SA      # noqa: E402

REPO = SA.repo_root()
Q_SAMPLES = os.path.join(REPO, "samples")
Q_R5 = os.path.join(REPO, "experiments", "genesis")


@pytest.fixture
def armed():
    """``armed(**kw)`` (re-)arms the tripwire; always disarmed afterwards so
    a failure never poisons later tests (the audit hook is process-wide)."""
    try:
        yield SA.forbid_research_inputs
    finally:
        SA.allow_research_inputs()


def _must_trip(path: str, mode: str = "rb", match: str = "research-machine input"):
    with pytest.raises(SA.StandaloneError, match=match):
        open(path, mode)


def test_quarantine_roots_are_this_checkouts_four_dirs():
    roots = SA.quarantine_roots()
    assert roots == [os.path.join(REPO, "extracted"), Q_SAMPLES,
                     os.path.join(REPO, "vendor"), Q_R5]
    assert all(os.path.isabs(r) for r in roots)


def test_out_dir_named_samples_elsewhere_is_the_jobs_own_output(tmp_path, armed):
    """The stranger's case: ``~/samples/jobs/x`` -- writes AND re-reads of the
    job's own files pass; everything else stays exactly as guarded."""
    out = tmp_path / "samples" / "jobs" / "x"
    (out / "_stages").mkdir(parents=True)
    armed(outputs=[str(out)])
    with open(out / "build.log", "w") as fh:                 # its own log: written
        fh.write("ok\n")
    with open(out / "_stages" / "stage_P_identity.rvt", "wb") as fh:
        fh.write(b"\0")
    with open(out / "_stages" / "stage_P_identity.rvt", "rb") as fh:   # ...and re-read
        assert fh.read() == b"\0"
    # a sibling under the same "samples" name is NOT the job's output
    _must_trip(str(tmp_path / "samples" / "jobs" / "other.rvt"))
    _must_trip(str(tmp_path / "samples" / "jobs" / "xy" / "a.rvt"))   # prefix, not path, sibling
    # this checkout's real quarantine roots: as forbidden as ever
    _must_trip(os.path.join(Q_SAMPLES, "rstbasicsampleproject.rvt"))
    _must_trip(os.path.join(REPO, "vendor", "phi-ag-rvt", "x.rfa"))
    _must_trip(os.path.join(REPO, "extracted", "racbasicsampleproject", "Formats__Latest.gz",
                            "000.bin"))
    _must_trip(os.path.join(Q_R5, "R5.rvt"))
    # and the Autodesk-install ban is absolute: an output dir never bypasses it
    _must_trip(str(out / "ProgramData" / "Autodesk" / "RVT 2026" / "x.rft"),
               match="Autodesk installation")
    _must_trip(str(out / "Family Templates" / "x.rft"), match="Autodesk installation")


@pytest.mark.parametrize("out_rel", [
    ("samples", "x"),                  # inside the real quarantine root
    ("samples",),                      # the root itself
    ("experiments", "genesis", "job"),
    (),                                # the checkout root: CONTAINS every quarantine root
    ("experiments",),                  # contains experiments/genesis
])
def test_an_output_dir_overlapping_a_real_quarantine_root_exempts_nothing(armed, out_rel):
    """``--out <repo>/samples/x`` (or the root itself, or an ancestor of one)
    can never be used to read a sample: such an ``outputs`` entry is dropped,
    so ``open(<repo>/samples/some.rvt)`` STILL raises -- even for a file
    under the very out dir that was passed."""
    out = os.path.join(REPO, *out_rel)
    armed(outputs=[out])
    _must_trip(os.path.join(Q_SAMPLES, "some.rvt"))
    _must_trip(os.path.join(Q_SAMPLES, "x", "prompt_room.rvt"))
    _must_trip(os.path.join(Q_R5, "job", "_stages", "stage_P_identity.rvt"))
    _must_trip(os.path.join(Q_R5, "R5.rvt"))


def test_disarmed_guard_polices_nothing(tmp_path, armed):
    armed(outputs=[str(tmp_path)])
    SA.allow_research_inputs()
    p = tmp_path / "samples" / "free.txt"
    p.parent.mkdir()
    p.write_text("x")                                        # no raise once disarmed


@pytest.mark.parametrize("out_rel, word", [
    (("samples", "x425"), "samples"),
    (("samples",), "samples"),
    (("vendor", "jobs", "a"), "vendor"),
    (("extracted", "y"), "extracted"),
    (("experiments", "genesis", "probe"), os.path.join("experiments", "genesis")),
])
def test_out_inside_this_checkouts_quarantine_is_refused_with_one_line(out_rel, word):
    out = os.path.join(REPO, *out_rel)
    line = SA.out_dir_refusal(out)
    assert line and "\n" not in line
    assert line.startswith("--out refused (nothing built): ")
    assert f"quarantined {word}{os.sep} directory" in line
    assert line.endswith("choose another --out than " + out)      # the path last: survives truncation


@pytest.mark.parametrize("segments", [
    ("ProgramData", "Autodesk", "RVT 2026", "jobs"),
    ("Program Files", "Autodesk", "Revit 2026", "out"),
    ("Applications", "Autodesk", "out"),
    ("x", "Family Templates", "English"),
])
def test_out_inside_an_autodesk_install_dir_is_refused_with_one_line(tmp_path, segments):
    # rooted at "/" for the /Applications marker, under tmp for the rest -- never created
    out = os.path.join(os.sep, *segments) if segments[0] == "Applications" \
        else str(tmp_path.joinpath(*segments))
    line = SA.out_dir_refusal(out)
    assert line and line.startswith("--out refused (nothing built): ")
    assert "Autodesk installation directory" in line and line.endswith(out)


@pytest.mark.parametrize("out", [
    lambda tmp: str(tmp / "samples" / "x"),                  # named like one, elsewhere: builds
    lambda tmp: str(tmp / "vendor"),
    lambda tmp: str(tmp / "experiments" / "genesis" / "y"),
    lambda tmp: os.path.join(REPO, "out", "demo"),           # the README's own example
    lambda tmp: os.path.join(REPO, "experiments", "frontdoor", "job-1"),   # the default out dir
    lambda tmp: os.path.join(REPO, "samplesheet"),           # a prefix is not a path segment
    lambda tmp: REPO,                                        # ancestors are not refused (nothing
    lambda tmp: os.path.join(REPO, "experiments"),           # exempted either -- see above)
])
def test_every_other_out_dir_is_not_refused(tmp_path, out):
    assert SA.out_dir_refusal(out(tmp_path)) is None
