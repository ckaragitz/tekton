"""test_edit_own_release.py -- the user-facing EDIT entry points open, edit and
re-emit a Revit 2026 / 2025 / 2024 project under ITS OWN release (issue #70).

Before, ``tools/rvt_edit.py`` (shipped as ``skills/tekton-edit/scripts/
rvt_edit.py``) and ``tools/rvt_job.py edit`` called ``Document.from_file`` /
``commit_plans`` release-blind: on the bundled 2025 / 2024 bases every verb
died with ``unexpected Partitions header: v=9 cls=0x391`` (0x37b) before any
edit ran, and a forced read re-emitted blocks with the 2026 framing tags.
The ``--rvt --edit`` front-door route enters the host release context since
#14; these tests pin all three surfaces on the three tracked, certified
genesis bases (``plugin/assets/genesis/G_ABPD{,_2025,_2024}.rvt``), so they
run in a fresh clone and in CI -- no samples/, no experiments/ ladders:

* the edit completes; the job runner's ``structural`` gate is PASS with the
  edited Level's seq-102 record clean and ``validation`` PASS;
* the output validates 0 errors STANDALONE (``tools/rvt_validate.py``'s
  ``validate_file``, no context around the judge) under its own release;
* the output's ``BasicFileInfo`` still declares the input's release;
* the native framing / module constants are back after every run (no leak
  into a following 2026 job in the same process).

Run: .venv/bin/python -m pytest tests/test_edit_own_release.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import partitions as P                            # noqa: E402
from rvt import versions as V                              # noqa: E402
from rvt.frontdoor import release_ctx as RC                # noqa: E402

GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
LEVEL_ID = 1351691                     # "GEN B1 - Basement", present in all three
EDIT_TEXT = f"set level {LEVEL_ID} elevation to 5 ft"

pytestmark = [
    pytest.mark.skipif(not all(os.path.isfile(p) for p in BASES.values()), reason="bundled genesis bases missing"),
    pytest.mark.usefixtures("no_release_leak"),      # the framing table is back after every test: no leak past a 2025/2024 edit
]


def _rvt_edit():
    """``tools/rvt_edit.py`` imported as a module (the tekton-edit skill's
    script; ``tools/rvt_job.py`` comes through the engine's own cached
    loader, ``rvt.frontdoor.edit.load_job_module``)."""
    key = "_t70_rvt_edit"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, os.path.join(ROOT, "tools", "rvt_edit.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _assert_own_release_output(path: str, year: int) -> None:
    """The output exists, declares the INPUT's release, and the standalone
    release-aware validator (no context around it) reports 0 errors."""
    from rvt.validate import validate_file
    assert os.path.isfile(path), path
    assert V.detect_release(path) == year
    assert RC.active_release() is None                 # judged bare, as a user would
    rep = validate_file(path).to_json()
    assert rep["counts"]["error"] == 0, [f for f in rep["findings"] if f.get("severity") == "error"][:5]


# ---------------------------------------------------------------------------
# 1. the front door: author --rvt <base> --edit "..."  (all three releases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_frontdoor_rvt_edit_route_under_the_inputs_release(year, tmp_path):
    import rvt.frontdoor as FD
    res = FD.author(rvt=BASES[year], edit=EDIT_TEXT, out=str(tmp_path / f"fd{year}"))
    assert res.ok and res.route == "rvt", res.errors
    out = res.files["edited"]
    with open(out + ".manifest.json") as fh:
        job = json.load(fh)
    gates = job["gates"]
    assert gates["structural"]["status"] == "PASS", gates["structural"]
    assert gates["structural"]["edited"][str(LEVEL_ID)]["102"] == {"class": "Level", "clean": True}
    assert gates["validation"]["status"] == "PASS", gates["validation"]
    assert job["base"]["release"] == year
    _assert_own_release_output(out, year)


# ---------------------------------------------------------------------------
# 2. tools/rvt_edit.py (the tekton-edit skill's script), called as its CLI
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_rvt_edit_cli_set_level_under_the_inputs_release(year, tmp_path, capsys):
    E = _rvt_edit()
    out = str(tmp_path / f"re{year}.rvt")
    rc = E.main([BASES[year], "set-level", "--id", str(LEVEL_ID),
                 "--elevation-ft", "5", "-o", out])
    assert rc == 0
    printed = capsys.readouterr().out
    assert '"walker_errors": 0' in printed and '"crc_failures": 0' in printed, printed[-600:]
    _assert_own_release_output(out, year)


@pytest.mark.parametrize("year", [2025, 2024])
def test_rvt_edit_cli_read_verbs_on_a_foreign_release(year, capsys):
    """``info`` / ``deps`` (read-only) on a 2025/2024 project: the inventory
    is the file's own (six levels, the basement among them), not a crash."""
    E = _rvt_edit()
    assert E.main([BASES[year], "info"]) == 0
    inv = json.loads(capsys.readouterr().out)
    assert any(lv.get("id") == LEVEL_ID for lv in inv["levels"]), inv["levels"]
    assert E.main([BASES[year], "deps", "--id", str(LEVEL_ID)]) == 0
    deps = json.loads(capsys.readouterr().out)
    assert deps["target"] == LEVEL_ID and deps["target_class"] == "Level"


# ---------------------------------------------------------------------------
# 3. tools/rvt_job.py edit (the ops.json door), called DIRECTLY as its CLI
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2025, 2024])
def test_rvt_job_edit_cli_under_the_inputs_release(year, tmp_path):
    from rvt.frontdoor.edit import load_job_module
    J = load_job_module()
    ops = tmp_path / "ops.json"
    ops.write_text(json.dumps([{"op": "set-level", "id": LEVEL_ID, "elevation_ft": 5.0}]))
    out = str(tmp_path / f"rj{year}" / "out.rvt")
    rc = J.main(["edit", BASES[year], "--ops", str(ops), "-o", out, "--no-provenance"])
    assert rc == 0
    with open(out + ".manifest.json") as fh:
        job = json.load(fh)
    assert job["gates"]["structural"]["status"] == "PASS"
    assert job["gates"]["validation"]["status"] == "PASS"
    assert job["base"]["release"] == year and "release_note" not in job["base"]
    _assert_own_release_output(out, year)


# ---------------------------------------------------------------------------
# 4. one process, mixed releases: a 2025 edit then a 2026 edit (no leak)
# ---------------------------------------------------------------------------

def test_mixed_release_edits_in_one_process_do_not_leak(tmp_path):
    E = _rvt_edit()
    for year in (2025, 2024, 2026):
        out = str(tmp_path / f"mix{year}.rvt")
        assert E.main([BASES[year], "set-level", "--id", str(LEVEL_ID),
                       "--elevation-ft", "7.5", "-o", out]) == 0
        assert RC.active_release() is None
        assert P.BLOCK_TAG == V.framing_table(V.LATEST_RELEASE)["BLOCK_TAG"]
        assert V.detect_release(out) == year
