"""Guard: the packaging metadata keeps its promises (issue #3).

* ``olefile`` stays the ONLY declared runtime dependency (CLAUDE.md section 2);
* the ``test`` / ``geometry`` / ``ifc`` / ``dev`` / ``all`` extras exist and
  mean what the docs say they mean;
* ``ifcopenshell`` stays OPTIONAL -- never a runtime dependency and never in
  an extra a contributor installs by default (the zero-install IFC *read*
  path via ``rvt.ifc.steplite`` is a product requirement,
  docs/product/SURFACE-PLAYBOOK.md; docs/writer/dependency-audit.md F2);
* the ``ifc`` extra pins exactly what ``skills/tekton-ifc/scripts/
  requirements.txt`` pins, so the IFC authoring backend has one version;
* the three setup surfaces (README "Reproduce", CLAUDE.md section 2,
  scripts/cloud-setup.sh) all install through the same ``test`` extra.

Fresh-clone safe: reads tracked text files only.
"""
import os
import re
import tomllib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(ROOT, "pyproject.toml")
IFC_REQUIREMENTS = os.path.join(ROOT, "skills", "tekton-ifc", "scripts",
                                "requirements.txt")
EXPECTED_EXTRAS = ("test", "geometry", "ifc", "dev", "all")


def _project() -> dict:
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)["project"]


def _name(requirement: str) -> str:
    """PEP 503-normalised distribution name of a PEP 508 requirement string."""
    head = re.split(r"[<>=!~\[;\s(]", requirement.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", head).lower()


def _names(requirements) -> set[str]:
    return {_name(r) for r in requirements}


def _requirements_txt(path: str) -> set[str]:
    """Non-comment requirement lines, internal whitespace removed."""
    out = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                out.add(re.sub(r"\s+", "", line))
    return out


def test_olefile_is_the_only_runtime_dependency():
    deps = _project()["dependencies"]
    assert _names(deps) == {"olefile"}, (
        "pyproject.toml must declare olefile as the ONLY runtime dependency; "
        f"heavier packages belong in [project.optional-dependencies]: {deps}")


def test_the_extras_are_declared_and_mean_what_the_docs_say():
    extras = _project().get("optional-dependencies", {})
    missing = [e for e in EXPECTED_EXTRAS if e not in extras]
    assert not missing, f"missing extras in pyproject.toml: {missing}"

    assert {"pytest", "numpy"} <= _names(extras["test"]), extras["test"]
    assert _names(extras["geometry"]) == {"numpy"}, extras["geometry"]
    assert "ifcopenshell" in _names(extras["ifc"]), extras["ifc"]
    assert _names(extras["dev"]) == _names(extras["test"]) | _names(
        extras["geometry"]), "dev must be exactly test + geometry"

    everything = set()
    for name, reqs in extras.items():
        if name != "all":
            everything |= _names(reqs)
    assert _names(extras["all"]) == everything, (
        "the `all` extra must cover every other extra, no more, no less: "
        f"all={sorted(_names(extras['all']))} others={sorted(everything)}")


def test_ifcopenshell_stays_optional():
    project = _project()
    assert "ifcopenshell" not in _names(project["dependencies"])
    extras = project["optional-dependencies"]
    for default_extra in ("test", "geometry", "dev"):
        assert "ifcopenshell" not in _names(extras[default_extra]), (
            f"`{default_extra}` must not pull ifcopenshell -- IFC reading is "
            "zero-install (steplite); ifcopenshell is for IFC authoring only")


def test_ifc_extra_pins_match_the_tekton_ifc_skill_requirements():
    assert os.path.isfile(IFC_REQUIREMENTS), IFC_REQUIREMENTS
    pinned = _requirements_txt(IFC_REQUIREMENTS)
    declared = {re.sub(r"\s+", "", r)
                for r in _project()["optional-dependencies"]["ifc"]}
    assert declared == pinned, (
        "pyproject.toml [ifc] extra and skills/tekton-ifc/scripts/"
        f"requirements.txt disagree: extra={sorted(declared)} "
        f"requirements.txt={sorted(pinned)} -- bump both together")


def test_every_requirement_string_is_valid_pep508():
    req_mod = pytest.importorskip("packaging.requirements")
    project = _project()
    strings = list(project["dependencies"])
    for reqs in project["optional-dependencies"].values():
        strings.extend(reqs)
    for s in strings:
        try:
            req_mod.Requirement(s)
        except Exception as exc:  # packaging raises InvalidRequirement
            pytest.fail(f"not a valid PEP 508 requirement: {s!r} ({exc})")


@pytest.mark.parametrize("rel", [
    "README.md",
    "CLAUDE.md",
    os.path.join("scripts", "cloud-setup.sh"),
])
def test_setup_surfaces_install_through_the_test_extra(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        text = f.read()
    assert ".[test]" in text, (
        f"{rel} should set up with `pip install -e \".[test]\"` so the three "
        "setup surfaces stay one source of truth with pyproject.toml")
