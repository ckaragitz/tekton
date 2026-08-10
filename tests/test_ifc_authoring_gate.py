"""The ONE real-ifcopenshell gate (issue #367).

``rvt.ifc._fallback.ifc_authoring_available()`` is the engine-owned answer to
"is the ``ifcopenshell`` this process would import a REAL wheel that ships
``ifcopenshell.api`` (IFC authoring), not the bundled reader-only steplite
shim?", and ``tests/conftest.py`` builds the suite's single
``HAVE_IFC_AUTHORING`` / ``needs_ifc_authoring`` on it -- replacing the
hand-rolled predicates whose permissive form ("does ``import ifcopenshell``
succeed") had been a no-op since the shim (#130, found by #366).

All fresh-clone: the wheel's presence / absence is SIMULATED through the
``find_spec`` the query consults and a fake package on disk, so the same
assertions hold on a box that has the wheel and on one that does not; the
last test cross-checks the live answer against the process's actual
``import ifcopenshell``.
"""
from __future__ import annotations

import importlib.machinery
import os
import sys

import pytest

from conftest import HAVE_IFC_AUTHORING
from rvt.ifc import _fallback as F

MIRRORED_SHIM = os.path.join("elsewhere", "plugin", "lib", "src", "rvt", "ifc", "_ifcos_shim")


@pytest.fixture(autouse=True)
def _fresh_memo():
    """The query is memoised per process; every simulation starts (and leaves)
    the cache empty so the live conftest answer is never poisoned."""
    F.ifc_authoring_available.cache_clear()
    yield
    F.ifc_authoring_available.cache_clear()


def _pkg_spec(pkg_dir: str) -> importlib.machinery.ModuleSpec:
    spec = importlib.machinery.ModuleSpec("ifcopenshell", loader=None,
                                          origin=os.path.join(pkg_dir, "__init__.py"))
    spec.submodule_search_locations = [pkg_dir]
    return spec


def _fake_site(root, *, with_api: bool) -> str:
    """A site dir holding a fake ``ifcopenshell`` package (optionally with ``.api``)."""
    pkg = root / "site-packages" / "ifcopenshell"
    (pkg / "api").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    if with_api:
        (pkg / "api" / "__init__.py").write_text("")
    return str(pkg.parent)


def _finds(monkeypatch, spec) -> None:
    monkeypatch.setattr(F.importlib.util, "find_spec", lambda name, *a, **k: spec)


def test_nothing_findable_means_no_authoring(monkeypatch):
    _finds(monkeypatch, None)
    assert F.ifc_authoring_available() is False


@pytest.mark.parametrize("shim_root", [F.SHIM_DIR, MIRRORED_SHIM])
def test_the_shim_never_counts(monkeypatch, shim_root):
    """The shim IS findable (that is the whole point of the fallback) -- and is
    exactly what must not open the authoring gate, wherever it was mirrored."""
    _finds(monkeypatch, _pkg_spec(os.path.join(shim_root, "ifcopenshell")))
    monkeypatch.setattr(sys, "path", [shim_root])
    assert F.ifcopenshell_findable() is True
    assert F.ifc_authoring_available() is False


@pytest.mark.parametrize("with_api", [True, False])
def test_a_real_distribution_counts_iff_it_ships_api(monkeypatch, tmp_path, with_api):
    _finds(monkeypatch, _pkg_spec(os.path.join(_fake_site(tmp_path, with_api=with_api), "ifcopenshell")))
    assert F.ifc_authoring_available() is with_api


def test_shim_ahead_of_a_wheel_answers_like_the_shim_stands_down(monkeypatch, tmp_path):
    """A skill child inherits the shim on PYTHONPATH, i.e. AHEAD of site-packages:
    ``import ifcopenshell`` still yields the wheel (the shim stands down to it)
    unless RVT_STEPLITE_FORCE pins the shim -- and the query says the same."""
    _finds(monkeypatch, _pkg_spec(os.path.join(MIRRORED_SHIM, "ifcopenshell")))
    monkeypatch.setattr(sys, "path", [MIRRORED_SHIM, _fake_site(tmp_path, with_api=True)])
    monkeypatch.setattr(sys, "path_importer_cache", {})
    monkeypatch.delenv(F.FORCE_ENV, raising=False)
    assert F.ifc_authoring_available() is True
    F.ifc_authoring_available.cache_clear()
    monkeypatch.setenv(F.FORCE_ENV, "1")
    assert F.ifc_authoring_available() is False


def test_a_raising_finder_counts_as_absent(monkeypatch):
    def boom(name, *a, **k):
        raise ValueError("ifcopenshell.__spec__ is None")
    monkeypatch.setattr(F.importlib.util, "find_spec", boom)
    assert F.ifc_authoring_available() is False


def test_query_imports_nothing_and_is_memoised(monkeypatch):
    calls = []
    real_find_spec = F.importlib.util.find_spec

    def counting(name, *a, **k):
        calls.append(name)
        return real_find_spec(name, *a, **k)

    had = "ifcopenshell" in sys.modules
    monkeypatch.setattr(F.importlib.util, "find_spec", counting)
    first = F.ifc_authoring_available()
    assert F.ifc_authoring_available() is first and F.ifc_authoring_available() is first
    assert calls == ["ifcopenshell"]                      # one find_spec, then the memo answers
    assert ("ifcopenshell" in sys.modules) is had         # asking never imports the wheel


def test_live_answer_agrees_with_what_import_yields():
    """The cross-check that retires ``not IS_STEPLITE``: in THIS process the
    gate is open exactly when ``import ifcopenshell`` is the real library."""
    import ifcopenshell                                   # real wheel, or the shim rvt.ifc appended
    is_shim = bool(getattr(ifcopenshell, "IS_STEPLITE", False))
    assert HAVE_IFC_AUTHORING is (not is_shim)
    assert F.ifc_authoring_available() is HAVE_IFC_AUTHORING
    if HAVE_IFC_AUTHORING:
        import ifcopenshell.api                           # noqa: F401  -- the surface the gate promises
