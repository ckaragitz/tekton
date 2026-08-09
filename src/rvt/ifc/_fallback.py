"""rvt.ifc._fallback -- ENGINE-level selection of the IFC READ backend (#130).

CLAUDE.md §2 declares ifcopenshell OPTIONAL: the IFC *read* paths
(``rvt.ifc.intent``, ``rvt.ifc.product_facts``, the ``rvt_to_ifc`` round
trip) fall back to the bundled stdlib reader (:mod:`rvt.ifc.steplite`,
served as an ``ifcopenshell`` look-alike package under
``rvt/ifc/_ifcos_shim``).  :func:`ensure_ifc_reader` is THE place that
fallback is selected; :mod:`rvt.ifc` calls it once on import, and every read
module is a submodule, so it always runs before their ``import ifcopenshell``
-- repo checkout, CI and plugin alike:

* NO ``ifcopenshell`` findable -> **append** the shim dir to ``sys.path``
  (never prepend: a real distribution anywhere on the path always wins, and
  the shim additionally stands down by itself if one shows up ahead of it);
* ``RVT_STEPLITE_FORCE=1`` -> shim FIRST, the one explicitly requested case
  where steplite must beat an installed wheel (equivalence tests, A/B) --
  the shim's own FORCE check then keeps it from standing down;
* a real ifcopenshell installed -> nothing is touched.

Idempotent, stdlib-only, one cached ``find_spec`` per process (~0.1 ms).
The plugin bootstrap (``tekton_env.ensure_engine``) adds exactly one thing on
top: exporting the dir on ``PYTHONPATH`` for a skill session's children.
The lazy ``ifcopenshell`` import inside ``rvt.ifc.intent`` (#6) is untouched;
it resolves to whichever backend was selected here.
"""
from __future__ import annotations

import importlib.util
import os
import sys

__all__ = ["SHIM_DIR", "FORCE_ENV", "ifcopenshell_findable", "ensure_ifc_reader"]

#: the bundled look-alike package root: <SHIM_DIR>/ifcopenshell/__init__.py
SHIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ifcos_shim")

#: set to a non-empty value to force the steplite backend over a real install
FORCE_ENV = "RVT_STEPLITE_FORCE"


def ifcopenshell_findable() -> bool:
    """True when ``import ifcopenshell`` would currently succeed (the real
    library, or the shim once its dir is on ``sys.path``).  A finder that
    raises (an import blocker in a test, a broken install) counts as "not
    findable" -- the read paths then refuse with their usual ``IntentError``
    instead of dying here."""
    try:
        return importlib.util.find_spec("ifcopenshell") is not None
    except (ImportError, AttributeError, ValueError):
        return False


def ensure_ifc_reader() -> str | None:
    """Select the IFC read backend for this process (see module doc).
    Returns the shim dir when this call placed it on ``sys.path``, else
    ``None`` (already placed, real library findable, or shim not bundled)."""
    force = bool(os.environ.get(FORCE_ENV))
    if force and sys.path[:1] == [SHIM_DIR]:
        return None
    if not force and (SHIM_DIR in sys.path or ifcopenshell_findable()):
        return None
    if not os.path.isfile(os.path.join(SHIM_DIR, "ifcopenshell", "__init__.py")):
        return None
    if force:
        if SHIM_DIR in sys.path:
            sys.path.remove(SHIM_DIR)
        sys.path.insert(0, SHIM_DIR)
    else:
        sys.path.append(SHIM_DIR)
    return SHIM_DIR
