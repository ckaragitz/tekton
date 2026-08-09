"""Guard: plugin/scripts/validate_plugin.py passes on a clean checkout.

The validator walks plugin/skills/. `_shared` is the zero-pip bootstrap
package and `__pycache__` is a build artifact; neither is a loadable skill and
neither carries a SKILL.md, so treating every subdirectory as a skill made the
validator fail unconditionally. See issue #26.
"""
import importlib.util
import os
import re
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


def _plugin_front_matter(root, agent_body="Route creation through go author.\n"):
    """Smallest agents/commands/README/docs tree the stale-claim guard scans."""
    for d in ("agents", "commands", "docs", "skills"):
        (root / d).mkdir(parents=True)
    (root / "agents" / "x-agent.md").write_text(
        "---\nname: x-agent\ndescription: builds .rvt files\n---\n" + agent_body,
        encoding="utf-8")
    (root / "commands" / "x.md").write_text(
        "---\ndescription: run a job\n---\nAsk the Revit year first.\n", encoding="utf-8")
    (root / "README.md").write_text("# plugin\nNo install on the job path.\n",
                                    encoding="utf-8")
    (root / "docs" / "HONEST-STATUS.md").write_text(
        "| prompt -> .rvt | validated | matrix row prompt_to_rvt |\n", encoding="utf-8")


def test_stale_claim_guard_is_silent_on_current_wording(tmp_path):
    _plugin_front_matter(tmp_path)
    assert _load().stale_claim_hits(str(tmp_path)) == []


def test_stale_claim_guard_catches_each_retired_phrase(tmp_path):
    """Issue #119: the pre-front-door wording (creation 'not yet available',
    'route to IFC', `pip install ./lib` on the hot path ...) must fail the
    plugin build wherever it reappears in the shipped front matter."""
    mod = _load()
    old_agent = ("1. **The deliverable:** an IFC (default) vs. a native `.rvt` "
                 "(creation of new elements in `.rvt` is not yet available; "
                 "say so and route to IFC).\n"
                 "```bash\npip install ./lib   # the rvt engine\n```\n"
                 "States plainly that new-element creation is in-progress "
                 "and not deliverable.\n")
    _plugin_front_matter(tmp_path, agent_body=old_agent)
    (tmp_path / "docs" / "HONEST-STATUS.md").write_text(
        "| IFC / spec -> native .rvt | in-progress | today deliver Tier-1 IFC instead |\n",
        encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "Creating brand-new equipment inside a `.rvt` is still in progress.\n",
        encoding="utf-8")
    hits = mod.stale_claim_hits(str(tmp_path))
    text = "\n".join(hits)
    for _rx, why in mod.STALE_CLAIMS:            # every retired claim fired
        assert why in text, (why, text)
    # every hit names file:line and the reason, so the fix is obvious
    assert all(re.match(r"^(agents/x-agent\.md|README\.md|docs[/\\]HONEST-STATUS\.md):\d+: "
                        r"stale claim '.+' -- .+", h) for h in hits), hits
    assert not any(h.startswith("commands/") for h in hits)   # the clean file stays clean

    # and it is wired into the CLI: the validator goes red on that tree
    r = subprocess.run([sys.executable, VALIDATOR, str(tmp_path)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1
    assert "stale claim 'not yet available'" in r.stdout, r.stdout


def test_shipped_plugin_carries_no_stale_claim():
    assert _load().stale_claim_hits(os.path.join(ROOT, "plugin")) == []


def test_shared_bootstrap_stays_a_plain_package():
    """The fix must not be 'give _shared a stub SKILL.md' -- it must never
    be loadable as a skill."""
    sd = os.path.join(ROOT, "plugin", "skills", "_shared")
    assert os.path.isdir(sd), "_shared bootstrap package missing"
    assert not os.path.isfile(os.path.join(sd, "SKILL.md")), \
        "_shared must not carry a SKILL.md"
    assert os.path.isfile(os.path.join(sd, "tekton_env.py"))
