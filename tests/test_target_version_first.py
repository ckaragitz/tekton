"""Target-version FIRST (issue #24): the ONE `go` JSON carries the honest
per-release story, so a skill asks the recipient's Revit year once and
needs no follow-up call.

Proven here, from a BARE plugin copy on an isolated interpreter (no
site-packages, no repo on the path -- exactly a stranger's unzip):

* ``go author ... --target-version Y`` for Y in 2026/2025/2024 resolves THAT
  release's certified bundled base (``result.release``: requested == output
  == Y, ``certified-base``) -- the regression: the bootstrap used to pin
  ``$RVT_GENESIS_BASE`` to the 2026 file, so 2025/2024 recipients got a
  2026 file plus a false "pending certification" line;
* a full 2025 build really IS a Revit 2025 file (BasicFileInfo), validated
  by our gate, stamps present in the same JSON;
* an unsupported year (2019) is accepted, never argparse-refused: the run
  DELIVERS (hard rule 1) with ``resolution=fallback``, THE line to relay
  verbatim ("your Revit 2019 cannot open it"), the nearest supported year
  and a version-agnostic IFC beside the build;
* ``.rvt`` inputs are auto-detected: ``go.inputs[].revit_release`` for any
  script, ``result.release.input_release`` on the front door's edit route;
* the creation skills ask the year BEFORE the job and name the flag.

Run: .venv/bin/python -m pytest tests/test_target_version_first.py -q
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
sys.path.insert(0, os.path.join(ROOT, "src"))

PROMPT = "an electrical room 12x10 ft with one lighting panel"
BARE_PY = [sys.executable, "-I", "-S"]          # isolated: no site-packages at all

pytestmark = pytest.mark.skipif(
    not os.path.isfile(os.path.join(PLUGIN, "assets", "genesis", "G_ABPD_2025.rvt")),
    reason="bundled genesis bases missing")


@pytest.fixture(scope="module")
def plugin_copy(tmp_path_factory):
    dst = os.path.join(str(tmp_path_factory.mktemp("tvfirst")), "plugin copy (bare)")
    ign = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".DS_Store")
    for part in (".claude-plugin", "skills", "lib", "assets"):
        shutil.copytree(os.path.join(PLUGIN, part), os.path.join(dst, part), ignore=ign)
    return dst


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("tvwork"))


def _go(plugin_copy, workdir, *args, skill="tekton-author", timeout=900):
    boot = os.path.join(plugin_copy, "skills", skill, "scripts", "_bootstrap.py")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    r = subprocess.run(BARE_PY + [boot, "go", *args], cwd=workdir, env=env,
                       capture_output=True, text=True, timeout=timeout)
    try:
        doc = json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f"stdout is not ONE json (rc={r.returncode}):\n"
                             f"{r.stdout[-1500:]}\n--stderr--\n{r.stderr[-1500:]}")
    return r.returncode, doc, r.stderr


# ---------------------------------------------------------------------------
# the honest per-release block, one call, every supported year
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_supported_year_resolves_its_own_certified_base(plugin_copy, workdir, year):
    out = os.path.join(workdir, f"h{year}")
    rc, doc, err = _go(plugin_copy, workdir, "author", "--handoff-only", "--prompt", PROMPT,
                       "--target-version", str(year), "--out", out)
    assert rc == 0, err[-1500:]
    assert doc["go"]["ready"] is True
    rel = doc["result"]["release"]
    assert rel["requested"] == year and rel["output"] == year, rel
    assert rel["resolution"] == "match", rel          # NOT the false 2026 fallback
    assert rel["target_support"] == "certified-base"
    assert rel["supported_targets"] == [2024, 2025, 2026]
    assert rel["opens_in"].startswith(f"Revit {year} and newer")
    assert "line" not in rel                          # nothing the recipient cannot open
    assert doc["result"]["stamps"] == []              # handoff-only: nothing built, no stamps


def test_full_2025_build_is_a_revit_2025_file(plugin_copy, workdir):
    """THE regression, end to end: the delivered .rvt IS Revit 2025 (read
    back from its own BasicFileInfo), our gate validated it, and the stamps
    ride in the same JSON -- no manifest re-read needed."""
    from rvt import versions as V
    out = os.path.join(workdir, "b2025")
    rc, doc, err = _go(plugin_copy, workdir, "author", "--prompt", PROMPT,
                       "--target-version", "2025", "--out", out)
    assert rc in (0, 4), err[-2000:]                  # 4 = ECC tier states its numpy need
    res = doc["result"]
    combined = (res.get("files") or {}).get("combined")
    assert combined and os.path.isfile(combined), res.get("errors")
    assert V.detect_release(combined) == 2025
    rel = res["release"]
    assert (rel["requested"], rel["output"], rel["resolution"]) == (2025, 2025, "match")
    assert rel["this_file"].startswith(("validated-not-certified", "self-checks-failed"))
    assert "ifc_addition" not in rel                  # no fallback -> no IFC substitute story
    assert isinstance(res["stamps"], list) and res["stamps"], "PROOF-ONLY stamps must ride along"
    assert all("PROOF-ONLY" in s for s in res["stamps"])


def test_unsupported_year_delivers_with_the_line_and_nearest(plugin_copy, workdir):
    """Hard rule 1 semantics: 2019 is not refused and nothing is withheld --
    the default build route runs, THE line says the recipient cannot open
    it, the nearest supported year is named, and the version-agnostic IFC
    is written beside it (handoff-only here keeps it fast; the IFC addition
    is emitted from the resolved intent either way)."""
    out = os.path.join(workdir, "h2019")
    rc, doc, err = _go(plugin_copy, workdir, "author", "--handoff-only", "--prompt", PROMPT,
                       "--target-version", "2019", "--out", out)
    assert rc == 0, err[-1500:]                       # accepted, not an argparse exit 2
    res = doc["result"]
    assert res["ok"] is True
    rel = res["release"]
    assert rel["requested"] == 2019 and rel["resolution"] == "fallback", rel
    assert rel["target_support"] == "not-supported"
    assert rel["nearest_supported"] == 2024
    assert rel["output"] == 2026                      # the default-release build route
    line = rel["line"]
    assert "your Revit 2019 cannot open it" in line
    assert "2024, 2025, 2026" in line and "IFC" in line
    assert "pending certification" not in line        # honest wording for an unknown year
    ifc = rel.get("ifc_addition")
    assert ifc and os.path.isfile(ifc) and res["files"].get("ifc") == ifc


# ---------------------------------------------------------------------------
# .rvt inputs: the release is DETECTED and stated, never asked
# ---------------------------------------------------------------------------

def test_rvt_inputs_are_auto_detected_in_go_inputs(plugin_copy, workdir):
    base25 = os.path.join(plugin_copy, "assets", "genesis", "G_ABPD_2025.rvt")
    rc, doc, err = _go(plugin_copy, workdir, "rvt_validate.py", base25,
                       skill="tekton-inspect", timeout=300)
    assert rc == 0, err[-1500:]
    ins = doc["go"]["inputs"]
    assert len(ins) == 1 and ins[0]["revit_release"] == 2025
    assert ins[0]["opens_in"].startswith("Revit 2025 and newer")


def test_edit_route_states_detected_release_without_target(plugin_copy, workdir):
    base26 = os.path.join(plugin_copy, "assets", "genesis", "G_ABPD.rvt")
    out = os.path.join(workdir, "e26")
    rc, doc, err = _go(plugin_copy, workdir, "author", "--rvt", base26,
                       "--edit", "move NOPE-9 to 1,1", "--out", out, skill="tekton-edit")
    assert rc == 3, err[-1500:]                       # honest one-line refusal by name ...
    res = doc["result"]
    assert any("NOPE-9" in e for e in res["errors"])
    rel = res["release"]                              # ... and the release story anyway
    assert rel["requested"] is None and rel["resolution"] == "detected"
    assert rel["input_release"] == 2026 and rel["output"] == 2026
    assert doc["go"]["inputs"][0]["revit_release"] == 2026


# ---------------------------------------------------------------------------
# the vocabulary + the skills' text
# ---------------------------------------------------------------------------

def test_target_status_vocabulary():
    from rvt.frontdoor import target_status as TS
    assert TS.supported_targets() == [2024, 2025, 2026]
    assert TS.support_status(2025) == "certified-base"
    assert TS.support_status(2023) == "known-not-certified"
    assert TS.support_status(2019) == "not-supported"
    assert TS.nearest_supported(2019) == 2024         # nothing older exists: oldest we have
    assert TS.nearest_supported(2025) == 2025
    assert TS.nearest_supported(2031) == 2026         # newer Revit opens our newest
    assert TS.opens_in(2025).startswith("Revit 2025 and newer") and TS.opens_in(None) is None


SKILLS = {
    "tekton-author": os.path.join(PLUGIN, "skills", "tekton-author", "SKILL.md"),
    "tekton-native": os.path.join(PLUGIN, "skills", "tekton-native", "SKILL.md"),
    "tekton-ifc": os.path.join(ROOT, "skills", "tekton-ifc", "SKILL.md"),
}


@pytest.mark.parametrize("skill", sorted(SKILLS))
def test_creation_skills_ask_the_year_first_and_pass_it_through(skill):
    text = open(SKILLS[skill], encoding="utf-8").read()
    assert "--target-version" in text, f"{skill}: must pass the year through"
    assert re.search(r"2026.{0,6}2025.{0,6}2024", text), f"{skill}: must name the supported years"
    if skill == "tekton-author":
        step0 = text.index("Step 0")
        step1 = text.index("Step 1")
        assert step0 < step1 and "year" in text[step0:step1].lower()
        assert "go author" in text[step1:]
        assert "references/REVIT-VERSIONS.md" in text
        assert os.path.isfile(os.path.join(PLUGIN, "skills", "tekton-author",
                                           "references", "REVIT-VERSIONS.md"))


def test_edit_skill_states_detected_release():
    text = open(os.path.join(PLUGIN, "skills", "tekton-edit", "SKILL.md"),
                encoding="utf-8").read()
    assert "go.inputs" in text and "DETECTED" in text
