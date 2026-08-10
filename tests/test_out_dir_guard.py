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


def test_a_case_variant_of_a_real_quarantine_root_is_the_root(armed):
    """``<repo>/Samples/x`` IS ``<repo>/samples/x`` on NTFS/APFS, and the
    hook's segment law is case-blind everywhere -- so the overlap test is
    too: refused up front, and arming with it exempts nothing (review E1)."""
    out = os.path.join(REPO, "Samples", "x425")
    line = SA.out_dir_refusal(out)
    assert line and f"quarantined samples{os.sep} directory" in line and line.endswith(out)
    armed(outputs=[out])
    assert SA._GUARD["outputs"] == ()
    _must_trip(os.path.join(out, "prompt_room.rvt"))              # main raised here too
    _must_trip(os.path.join(REPO, "samples", "some.rvt"))
    _must_trip(os.path.join(REPO, "EXPERIMENTS", "Genesis", "R5.rvt"))


@pytest.fixture
def treelink(tmp_path):
    """A second SPELLING of this checkout: ``<tmp>/treelink -> <repo>``."""
    link = tmp_path / "treelink"
    try:
        os.symlink(REPO, str(link), target_is_directory=True)
    except (OSError, NotImplementedError) as e:                # pragma: no cover
        pytest.skip(f"cannot create a directory symlink here: {e}")
    return str(link)


def test_engine_imported_through_a_symlink_still_guards_the_real_tree(treelink, armed,
                                                                       monkeypatch):
    """The engine's ``repo_root()`` is the symlink spelling, the job's --out
    the real one (review D5): the out dir is STILL inside the real quarantine
    root -> refused, and arming with it exempts nothing under either spelling."""
    monkeypatch.setattr(SA, "repo_root", lambda: treelink)
    assert SA.quarantine_roots()[1] == os.path.join(treelink, "samples")
    out = os.path.join(REPO, "samples", "Snowdon")             # the REAL spelling
    line = SA.out_dir_refusal(out)
    assert line and f"quarantined samples{os.sep} directory" in line and line.endswith(out)
    armed(outputs=[out])
    assert SA._GUARD["outputs"] == ()
    _must_trip(os.path.join(out, "real.rvt"))
    _must_trip(os.path.join(treelink, "samples", "Snowdon", "real.rvt"))
    _must_trip(os.path.join(treelink, "vendor", "x.rfa"))


def test_a_symlink_spelled_output_is_dropped_entirely(treelink, armed):
    """A direct caller arms with the SYMLINK spelling of ``<repo>/samples/x``
    (review D3): one of its spellings nests the real root, so the output is
    dropped ENTIRELY -- the link spelling does not survive as a prefix."""
    out = os.path.join(treelink, "samples", "Snowdon")
    assert SA.out_dir_refusal(out) is not None
    armed(outputs=[out, os.path.join(treelink, "experiments")])   # + an ancestor, link-spelled
    assert SA._GUARD["outputs"] == ()
    _must_trip(os.path.join(out, "real.rvt"))                   # link spelling
    _must_trip(os.path.join(REPO, "samples", "Snowdon", "real.rvt"))   # real spelling
    _must_trip(os.path.join(treelink, "experiments", "genesis", "R5.rvt"))
    # while a genuinely foreign dir reached through a link stays the job's own
    # output under BOTH spellings (the stranger's macOS /tmp -> /private/tmp)


def test_a_symlinked_stranger_dir_is_exempt_under_both_spellings(tmp_path, armed):
    real = tmp_path / "disk" / "samples" / "jobs" / "x"
    real.mkdir(parents=True)
    link = tmp_path / "home"
    try:
        os.symlink(str(tmp_path / "disk"), str(link), target_is_directory=True)
    except (OSError, NotImplementedError) as e:                # pragma: no cover
        pytest.skip(f"cannot create a directory symlink here: {e}")
    out = os.path.join(str(link), "samples", "jobs", "x")      # the spelling the user typed
    assert SA.out_dir_refusal(out) is None
    armed(outputs=[out])
    assert set(SA._GUARD["outputs"]) == {out + os.sep, str(real) + os.sep}
    for spelling in (out, str(real)):
        with open(os.path.join(spelling, "build.log"), "a") as fh:
            fh.write("ok\n")
    _must_trip(os.path.join(str(link), "samples", "jobs", "other.rvt"))
    _must_trip(os.path.join(Q_SAMPLES, "some.rvt"))


def _symlink(target: str, link: str) -> str:
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as e:                # pragma: no cover
        pytest.skip(f"cannot create a directory symlink here: {e}")
    return link


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A checkout root of its own under tmp (``repo_root()`` pointed at it),
    with a real ``samples/`` dir and an ``elsewhere/`` dir OUTSIDE it -- so
    the link cases never go near this repo's own ``samples/``."""
    root = tmp_path / "tree"
    (root / "samples").mkdir(parents=True)
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.setattr(SA, "repo_root", lambda: str(root))
    return root


def test_an_outward_link_planted_inside_samples_is_still_inside_samples(tree, armed):
    """Issue #474: ``<tree>/samples/escape -> <tmp>/elsewhere`` + ``--out
    <tree>/samples/escape/j``.  Physically the job would land in
    ``elsewhere/j`` -- but every path it reports is SPELLED under
    ``<tree>/samples/``, which ``is_autodesk_sample()`` calls an Autodesk
    sample ever after.  The lexical spelling lies inside the quarantine root,
    so it is refused with the one line, and arming with it exempts nothing."""
    elsewhere = str(tree.parent / "elsewhere")
    escape = _symlink(elsewhere, str(tree / "samples" / "escape"))
    out = os.path.join(escape, "j")
    assert os.path.realpath(out) == os.path.join(os.path.realpath(elsewhere), "j")  # outward
    line = SA.out_dir_refusal(out)
    assert line and f"quarantined samples{os.sep} directory" in line
    assert line.endswith("choose another --out than " + out)
    assert SA.out_dir_refusal(str(tree / "Samples" / "escape" / "j")) is not None   # case-blind
    armed(outputs=[out])
    assert SA._GUARD["outputs"] == ()
    _must_trip(os.path.join(out, "prompt_room.rvt"))              # the spelling the job would use
    _must_trip(os.path.join(str(tree), "samples", "some.rvt"))
    assert os.listdir(elsewhere) == []                              # nothing reached through the link


def test_an_inward_link_outside_the_tree_is_inside_by_its_physical_spelling(tree, armed):
    """The mirror shape, caught before and after #474 alike: ``<tmp>/inward ->
    <tree>/samples`` + ``--out <tmp>/inward/j`` is physically inside the
    quarantine root -> refused, exempts nothing under either spelling."""
    inward = _symlink(str(tree / "samples"), str(tree.parent / "inward"))
    out = os.path.join(inward, "j")
    line = SA.out_dir_refusal(out)
    assert line and f"quarantined samples{os.sep} directory" in line and line.endswith(out)
    armed(outputs=[out])
    assert SA._GUARD["outputs"] == ()
    _must_trip(os.path.join(str(tree), "samples", "j", "prompt_room.rvt"))


@pytest.mark.parametrize("shape", ["named", "tree_out_link", "foreign_link"])
def test_links_and_names_that_lie_outside_under_both_spellings_are_not_refused(tree, armed,
                                                                             shape):
    """The negatives #474 must not swallow: a dir merely NAMED ``samples``
    elsewhere; an outward link from a NON-quarantine dir of the tree
    (``<tree>/out -> elsewhere``); a link placed OUTSIDE the tree pointing
    outside it (``<tmp>/home -> elsewhere``, a ``samples/`` under it).  None
    is inside a quarantine root under either spelling: not refused, and the
    job's own dir is exempt under both spellings."""
    elsewhere = str(tree.parent / "elsewhere")
    if shape == "named":
        out = os.path.join(elsewhere, "samples", "j")
    elif shape == "tree_out_link":
        out = os.path.join(_symlink(elsewhere, str(tree / "out")), "j")
    else:
        out = os.path.join(_symlink(elsewhere, str(tree.parent / "home")), "samples", "j")
    assert SA.out_dir_refusal(out) is None
    os.makedirs(out)
    armed(outputs=[out])
    spellings = {out, os.path.realpath(out)}
    assert set(SA._GUARD["outputs"]) == {sp + os.sep for sp in spellings}
    for spelling in spellings:
        with open(os.path.join(spelling, "build.log"), "a") as fh:
            fh.write("ok\n")
    _must_trip(os.path.join(str(tree), "samples", "some.rvt"))


def test_a_link_into_an_autodesk_install_dir_is_that_dir(tree):
    """Rule 2's bullet is judged on both spellings too: ``<tmp>/adlink ->
    <tmp>/Program Files/Autodesk/Revit 2026`` + ``--out <tmp>/adlink/j``
    would physically write into the install dir -- refused with the
    install-dir line (the target here is a plain tmp dir NAMED like one;
    nothing under it is opened either way)."""
    target = tree.parent / "Program Files" / "Autodesk" / "Revit 2026"
    target.mkdir(parents=True)
    out = os.path.join(_symlink(str(target), str(tree.parent / "adlink")), "j")
    line = SA.out_dir_refusal(out)
    assert line and "Autodesk installation directory" in line and line.endswith(out)
    assert list(target.iterdir()) == []


def test_run_refuses_the_outward_link_before_anything_lands_beyond_it(tree):
    """End to end through the front door's ``run()`` (which owns the up-front
    refusal, #452): the outward-link ``--out`` raises ``FrontDoorError`` whose
    text IS the one line, and NOTHING is created -- not under the link's
    lexical spelling, not in the dir it points at."""
    import rvt.frontdoor as FD
    elsewhere = str(tree.parent / "elsewhere")
    out = os.path.join(_symlink(elsewhere, str(tree / "samples" / "escape")), "j")
    with pytest.raises(FD.FrontDoorError) as ei:
        FD.author(prompt="a room with four walls", out=out)
    assert str(ei.value) == SA.out_dir_refusal(out)
    assert os.listdir(elsewhere) == [] and not os.path.lexists(out)


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
