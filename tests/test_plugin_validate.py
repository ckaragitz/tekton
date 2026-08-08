"""Guard: plugin/scripts/validate_plugin.py passes on a clean checkout.

The validator walks plugin/skills/. `_shared` is the zero-pip bootstrap
package and `__pycache__` is a build artifact; neither is a loadable skill and
neither carries a SKILL.md, so treating every subdirectory as a skill made the
validator fail unconditionally. See issue #26.
"""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATOR = os.path.join(ROOT, "plugin", "scripts", "validate_plugin.py")


def _load():
    spec = importlib.util.spec_from_file_location("validate_plugin", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validator_passes_on_the_shipped_plugin():
    r = subprocess.run([sys.executable, VALIDATOR],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_underscore_dirs_are_not_treated_as_skills(tmp_path):
    d = tmp_path / "skills"
    (d / "tekton-author").mkdir(parents=True)
    (d / "tekton-author" / "SKILL.md").write_text(
        "---\nname: tekton-author\ndescription: x\n---\n", encoding="utf-8")
    (d / "_shared").mkdir()
    (d / "__pycache__").mkdir()
    (d / "loose-file.txt").write_text("not a skill", encoding="utf-8")
    assert _load().skill_dirs(str(d)) == ["tekton-author"]


def test_shared_bootstrap_stays_a_plain_package():
    """The fix must not be 'give _shared a stub SKILL.md' -- it must never
    be loadable as a skill."""
    sd = os.path.join(ROOT, "plugin", "skills", "_shared")
    assert os.path.isdir(sd), "_shared bootstrap package missing"
    assert not os.path.isfile(os.path.join(sd, "SKILL.md")), \
        "_shared must not carry a SKILL.md"
    assert os.path.isfile(os.path.join(sd, "tekton_env.py"))
