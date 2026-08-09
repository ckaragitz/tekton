"""Issue #130: the steplite IFC-read fallback is selected by the ENGINE
(``rvt.ifc`` package init -> :mod:`rvt.ifc._fallback`), not only by the
plugin bootstrap -- so ``frontdoor author --ifc`` and the ``rvt_to_ifc``
round trip work from a plain checkout / CI with NO ifcopenshell installed.

Everything here runs on a fresh clone (no samples/, no ifcopenshell): the
absence of the real library is SIMULATED in-process (the way test_coldstart
hides numpy, but with monkeypatch instead of ``-S``) so the same assertions
hold on a box that does have the 190 MB wheel installed:

* selection law: absent -> the shim dir is APPENDED (never first); present ->
  ``sys.path`` untouched and the import is the REAL library (its ``__file__``
  is not under ``_ifcos_shim``); ``RVT_STEPLITE_FORCE=1`` -> shim FIRST;
  a finder that raises counts as absent; idempotent;
* the front door's ``intent_from_ifc`` resolves the tracked example IFC
  through steplite (``ifcopenshell.IS_STEPLITE``) with the expected census
  (4 walls, 12 equipment, 8 buildable family plans);
* the ``rvt_to_ifc`` round-trip check RUNS (``ran: True``) on steplite;
* ``tekton_env.ensure_engine`` keeps working on top (harmless duplicate).
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
ROOM_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")

from rvt.ifc import _fallback as F  # noqa: E402

SHIM = F.SHIM_DIR

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:                                    # pragma: no cover
    HAVE_NUMPY = False

needs_room = pytest.mark.skipif(not os.path.isfile(ROOM_IFC),
                                reason="tracked example IFC absent")
# the intent's placement / geometry maths is numpy (issue #127 tracks the
# numpy-free bare surface); the READER selection itself needs nothing
needs_numpy = pytest.mark.skipif(not HAVE_NUMPY,
                                 reason="intent geometry needs numpy (#127)")


def _real_ifcopenshell_dir() -> str | None:
    """site dir holding a REAL ifcopenshell, if one is installed here."""
    paths = [p for p in sys.path if os.path.abspath(p or ".") != SHIM]
    spec = importlib.machinery.PathFinder.find_spec("ifcopenshell", paths)
    if spec is None or not spec.origin:
        return None
    return os.path.dirname(os.path.dirname(os.path.abspath(spec.origin)))


REAL_SITE = _real_ifcopenshell_dir()


class _HideReal(importlib.abc.MetaPathFinder):
    """Make the REAL ifcopenshell unfindable while leaving the shim (and
    everything else on sys.path) alone: top-level ``ifcopenshell`` is looked
    up on sys.path minus the real install's site dir.  With no real install
    on this box a miss is an ordinary ``None`` (exactly what an absent wheel
    yields); with one installed the miss must be FINAL (raise), or the
    default path finder behind us would serve the real library after all --
    the engine helper treats a raising finder as 'absent' too."""

    def find_spec(self, name, path=None, target=None):
        if name != "ifcopenshell":
            return None                     # submodules resolve via parent __path__
        if REAL_SITE is None:
            return None                     # nothing to hide: normal resolution
        paths = [p for p in sys.path if os.path.abspath(p or ".") != REAL_SITE]
        spec = importlib.machinery.PathFinder.find_spec(name, paths)
        if spec is None:
            raise ModuleNotFoundError("No module named 'ifcopenshell' (hidden by test)")
        return spec


def _is_ifcos(name: str) -> bool:
    return name == "ifcopenshell" or name.startswith("ifcopenshell.")


@pytest.fixture
def no_real_ifcopenshell(monkeypatch):
    """In-process simulation of 'ifcopenshell is not installed': the real
    distribution is hidden from the import system and every cached
    ``ifcopenshell*`` module plus the shim path entry are dropped.  On exit
    ``sys.path`` / ``sys.modules`` / ``sys.meta_path`` are restored exactly,
    so later tests see the session's normal backend again (no module is
    ever reloaded -- class identities elsewhere in the suite stay intact)."""
    saved_mods = {k: m for k, m in sys.modules.items() if _is_ifcos(k)}
    saved_path = list(sys.path)
    for k in saved_mods:
        monkeypatch.delitem(sys.modules, k)
    while SHIM in sys.path:
        sys.path.remove(SHIM)
    monkeypatch.delenv(F.FORCE_ENV, raising=False)
    hider = _HideReal()
    sys.meta_path.insert(0, hider)
    try:
        yield
    finally:
        if hider in sys.meta_path:
            sys.meta_path.remove(hider)
        for k in [k for k in sys.modules if _is_ifcos(k)]:
            del sys.modules[k]
        sys.path[:] = saved_path
        sys.modules.update(saved_mods)


def _fresh_intent_reader(monkeypatch):
    """``rvt.ifc.intent`` with its lazy ``ifcopenshell`` proxies re-armed, so
    the NEXT read resolves against the backend selected right now (an
    earlier test may already have bound them to the real library).  With
    the real wheel merely HIDDEN (still on disk) the shim's own stand-down
    probe would find it, so ``RVT_STEPLITE_FORCE`` pins the steplite
    backend -- what a genuinely absent wheel yields (proved for real in the
    record's no-ifcopenshell venv transcript).  monkeypatch restores the
    original bindings on teardown."""
    from rvt._lazyimp import lazy_import
    if REAL_SITE is not None:
        monkeypatch.setenv(F.FORCE_ENV, "1")
    I = importlib.import_module("rvt.ifc.intent")
    g = vars(I)
    monkeypatch.setattr(I, "ifcopenshell", lazy_import("ifcopenshell", g, "ifcopenshell"))
    monkeypatch.setattr(I, "_ue", lazy_import("ifcopenshell.util.element", g, "_ue"))
    return I


# ===========================================================================
# 1. the selection law
# ===========================================================================

def test_absent_appends_shim_last_and_is_idempotent(no_real_ifcopenshell):
    assert not F.ifcopenshell_findable()
    n = len(sys.path)
    assert F.ensure_ifc_reader() == SHIM
    assert sys.path[-1] == SHIM and sys.path.index(SHIM) == n   # appended, never first
    assert F.ensure_ifc_reader() is None                        # idempotent
    assert sys.path.count(SHIM) == 1
    assert F.ifcopenshell_findable()                            # the shim now answers


def test_raising_finder_counts_as_absent(no_real_ifcopenshell, monkeypatch):
    class _Boom(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name == "ifcopenshell":
                raise ModuleNotFoundError(name)
            return None
    boom = _Boom()
    sys.meta_path.insert(0, boom)
    try:
        assert F.ifcopenshell_findable() is False
        assert F.ensure_ifc_reader() == SHIM          # still appends; import then refuses
    finally:
        sys.meta_path.remove(boom)


def test_force_puts_shim_first(no_real_ifcopenshell, monkeypatch):
    monkeypatch.setenv(F.FORCE_ENV, "1")
    assert F.ensure_ifc_reader() == SHIM
    assert sys.path[0] == SHIM
    assert F.ensure_ifc_reader() is None and sys.path.count(SHIM) == 1
    import ifcopenshell
    assert getattr(ifcopenshell, "IS_STEPLITE", False)


@pytest.mark.skipif(REAL_SITE is None, reason="real ifcopenshell not installed here")
def test_real_install_wins_and_path_is_untouched(monkeypatch):
    monkeypatch.delenv(F.FORCE_ENV, raising=False)
    while SHIM in sys.path:
        sys.path.remove(SHIM)
    before = list(sys.path)
    assert F.ensure_ifc_reader() is None
    assert sys.path == before and SHIM not in sys.path
    import ifcopenshell
    assert "_ifcos_shim" not in os.path.abspath(ifcopenshell.__file__)
    assert not getattr(ifcopenshell, "IS_STEPLITE", False)
    assert F.backend() == "ifcopenshell"


def test_package_import_selects_backend_in_a_fresh_interpreter():
    """The law end to end, out of process: importing ``rvt.ifc`` alone makes
    ``import ifcopenshell`` resolvable on ANY box (real if installed, else the
    appended shim) -- no tekton_env, no PYTHONPATH tricks."""
    import subprocess
    code = (
        "import sys\n"
        f"sys.path.insert(0, {SRC!r})\n"
        "import importlib.util as u\n"
        "had_real = u.find_spec('ifcopenshell') is not None\n"
        "import rvt.ifc\n"
        "from rvt.ifc import _fallback as F\n"
        "import ifcopenshell\n"
        "shim = getattr(ifcopenshell, 'IS_STEPLITE', False)\n"
        "assert shim != had_real, (shim, had_real)\n"
        "assert (F.SHIM_DIR in sys.path) == (not had_real)\n"
        "assert had_real or sys.path[-1] == F.SHIM_DIR\n"
        "print('SELECT-OK', F.backend())\n")
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", F.FORCE_ENV)}
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "SELECT-OK" in r.stdout


# ===========================================================================
# 2. the read routes on steplite, in-process
# ===========================================================================

@needs_room
@needs_numpy
def test_intent_from_ifc_resolves_example_via_steplite(no_real_ifcopenshell, monkeypatch):
    I = _fresh_intent_reader(monkeypatch)
    assert F.ensure_ifc_reader() == SHIM
    import ifcopenshell
    assert getattr(ifcopenshell, "IS_STEPLITE", False), ifcopenshell.__file__
    assert I._load_ifcos() is True and I.ifcopenshell is ifcopenshell   # proxy rebound
    from rvt.frontdoor import intent as FI
    model = FI.intent_from_ifc(ROOM_IFC)
    assert isinstance(model, FI.IntentModel)
    assert model.room is not None and len(model.room.walls) == 4
    assert len(model.equipment) == 12
    assert len(FI.buildable_family_plans(model)) == 8      # -> the 8 placed instances
    assert F.backend() == "steplite"


@needs_room
@needs_numpy
def test_rvt_to_ifc_roundtrip_runs_on_steplite(no_real_ifcopenshell, monkeypatch, tmp_path):
    """The round-trip acceptance re-resolves the emitted IFC through the same
    reader: on steplite it must RUN (formerly 'did not run: ifcopenshell is
    required to read IFC')."""
    I = _fresh_intent_reader(monkeypatch)
    F.ensure_ifc_reader()
    from rvt.frontdoor import ifc_out
    from rvt.convert import rvt_to_ifc as R
    src_model = I.resolve_intent(ROOM_IFC)
    assert getattr(I.ifcopenshell, "IS_STEPLITE", False)
    # the intent doubles as the ExtractedModel: the round trip only reads
    # .equipment[*].{tag,kind,insertion_m,front_normal},
    # .room.walls[*].{p0_m,p1_m,thickness_m} and .feeders
    out_ifc = ifc_out.write_intent_ifc(src_model, str(tmp_path / "room.ifc"))
    table = R.roundtrip_table(src_model, out_ifc)
    assert table["ran"] is True, table.get("why")
    assert table["walls_in"] == 4 and table["walls_matched"] == "4/4"
    assert table["equipment_survived"].endswith(f"/{len(src_model.equipment)}")


# ===========================================================================
# 3. the plugin bootstrap still composes with the engine helper
# ===========================================================================

def test_tekton_env_ensure_engine_composes_with_engine_helper():
    """Bare interpreter (``-S``: no site-packages, so no ifcopenshell at all)
    on the synced plugin tree: ``ensure_engine`` (twice) + the engine's own
    selection leave exactly ONE shim entry, appended, exported for children,
    and ``import ifcopenshell`` is steplite.  Out of process, so the
    bootstrap's env exports never leak into this session."""
    import subprocess
    plugin = os.path.join(ROOT, "plugin")
    shared = os.path.join(plugin, "skills", "_shared")
    mirror = os.path.join(plugin, "lib", "src", "rvt", "ifc", "_fallback.py")
    if not (os.path.isfile(os.path.join(shared, "tekton_env.py"))
            and os.path.isfile(mirror)):
        pytest.skip("plugin tree not synced with the engine helper")
    code = (
        "import os, sys\n"
        f"sys.path.insert(0, {shared!r})\n"
        "import tekton_env\n"
        f"tekton_env.ensure_engine({plugin!r}); tekton_env.ensure_engine({plugin!r})\n"
        "from rvt.ifc import _fallback as F\n"
        "import rvt.ifc.intent, ifcopenshell\n"
        "assert getattr(ifcopenshell, 'IS_STEPLITE', False), ifcopenshell.__file__\n"
        "hits = [p for p in sys.path if p == F.SHIM_DIR]\n"
        "assert hits == [F.SHIM_DIR] and sys.path[0] != F.SHIM_DIR, sys.path\n"
        "assert F.SHIM_DIR in os.environ['PYTHONPATH'].split(os.pathsep)\n"
        "assert F.ensure_ifc_reader() is None\n"
        "print('COMPOSE-OK', F.backend())\n")
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "RVT_PLUGIN_ROOT", F.FORCE_ENV)}
    r = subprocess.run([sys.executable, "-S", "-c", code], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "COMPOSE-OK steplite" in r.stdout
