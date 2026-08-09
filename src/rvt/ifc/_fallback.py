"""rvt.ifc._fallback -- ENGINE-level selection of the IFC READ backend.

CLAUDE.md §2 declares ifcopenshell OPTIONAL: the IFC *read* paths
(``rvt.ifc.intent`` behind ``frontdoor author --ifc``, ``rvt.ifc.product_facts``
behind the IFC family pipeline, the ``rvt.convert.rvt_to_ifc`` round-trip
check) fall back to the bundled stdlib reader (:mod:`rvt.ifc.steplite`,
served as an ``ifcopenshell`` look-alike package under
``rvt/ifc/_ifcos_shim``).  Until issue #130 that fallback was wired ONLY by
the plugin bootstrap (``tekton_env.ensure_engine``), so a plain checkout, CI,
or a Windows / cloud contributor without the optional wheel got
``IntentError: ifcopenshell is required to read IFC`` from the very routes
the docs call zero-install.

This module makes the selection an ENGINE property: :func:`ensure_ifc_reader`
runs once when :mod:`rvt.ifc` is first imported (every read module is a
submodule, so it always runs before their ``import ifcopenshell``) and

* when NO ``ifcopenshell`` is findable, **appends** the shim dir to
  ``sys.path`` -- never prepends, so a real distribution anywhere on the
  path always wins (the shim additionally stands down by itself if a real
  install shows up ahead of it, see ``_ifcos_shim/ifcopenshell/__init__``);
* when ``RVT_STEPLITE_FORCE=1`` is set, puts the shim FIRST -- the one,
  explicitly requested case where the pure-python backend must beat an
  installed ifcopenshell (equivalence tests, backend A/B timing);
* otherwise (a real ifcopenshell is installed) touches nothing.

It is idempotent, stdlib-only, and costs one ``find_spec`` (a cached
``sys.path`` scan, well under a millisecond) per process.  Repo, CI and
plugin now select the backend by the same code; ``tekton_env.ensure_engine``
keeps its own append for older engines and additionally exports the dir on
``PYTHONPATH`` for child processes -- a harmless duplicate.

Territory: issue #130 (``docs/inbox/ifc-read-fallback-engine.md``).  The
lazy ``ifcopenshell`` import inside ``rvt.ifc.intent`` is issue #6's and is
not touched: it simply resolves to whichever backend this module selected.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from typing import Optional

__all__ = ["SHIM_DIR", "FORCE_ENV", "ifcopenshell_findable", "ensure_ifc_reader",
           "backend"]

#: the bundled look-alike package root: <SHIM_DIR>/ifcopenshell/__init__.py
SHIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ifcos_shim")

#: set to a non-empty value to force the steplite backend over a real install
FORCE_ENV = "RVT_STEPLITE_FORCE"


def ifcopenshell_findable() -> bool:
    """True when ``import ifcopenshell`` would currently succeed (the real
    library, or the shim if its dir is already on ``sys.path``).  A finder
    that raises (an import blocker in a test, a broken install) counts as
    "not findable" -- the read paths then refuse with their usual
    ``IntentError`` instead of dying here."""
    try:
        return importlib.util.find_spec("ifcopenshell") is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _shim_present() -> bool:
    return os.path.isfile(os.path.join(SHIM_DIR, "ifcopenshell", "__init__.py"))


def ensure_ifc_reader() -> Optional[str]:
    """Select the IFC read backend for this process (see module doc).

    Returns the shim dir when this call put it on ``sys.path`` (appended, or
    inserted first under ``RVT_STEPLITE_FORCE``), else ``None`` (real
    ifcopenshell findable, shim already on the path, or shim not bundled)."""
    if not _shim_present():
        return None
    if os.environ.get(FORCE_ENV):
        if sys.path[:1] == [SHIM_DIR]:
            return None
        try:
            sys.path.remove(SHIM_DIR)
        except ValueError:
            pass
        sys.path.insert(0, SHIM_DIR)
        return SHIM_DIR
    if SHIM_DIR in sys.path or ifcopenshell_findable():
        return None
    sys.path.append(SHIM_DIR)
    return SHIM_DIR


def backend() -> str:
    """``"ifcopenshell"``, ``"steplite"`` or ``"none"`` -- which reader an
    ``import ifcopenshell`` resolves to right now (imports it if needed;
    for manifests / doctors, not for the hot path)."""
    try:
        import ifcopenshell  # type: ignore
    except Exception:
        return "none"
    return "steplite" if getattr(ifcopenshell, "IS_STEPLITE", False) else "ifcopenshell"
