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

The companion question -- "is the ``ifcopenshell`` this process would import
the REAL wheel (authoring API and all), not the reader-only shim?" -- is
:func:`ifc_authoring_available` (#367), kept here next to the selection so
there is exactly one definition of "real" for the engine and the test suite.
"""
from __future__ import annotations

import functools
import importlib.machinery
import importlib.util
import os
import sys

__all__ = ["SHIM_DIR", "FORCE_ENV", "ifcopenshell_findable", "ifc_authoring_available",
           "ensure_ifc_reader"]

#: path-segment name shared by EVERY copy of the shim (this tree, the plugin
#: mirror under plugin/lib/, an unzipped bundle): "is this the shim" keys on
#: it, not on SHIM_DIR, so a mirrored shim never counts as the real library
_SHIM_MARK = "_ifcos_shim"

#: the bundled look-alike package root: <SHIM_DIR>/ifcopenshell/__init__.py
SHIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), _SHIM_MARK)

#: set to a non-empty value to force the steplite backend over a real install
FORCE_ENV = "RVT_STEPLITE_FORCE"

_FINDER_ERRORS = (ImportError, AttributeError, ValueError)


def _ifcopenshell_spec():
    """``find_spec("ifcopenshell")`` or ``None``.  A finder that raises (an
    import blocker in a test, a broken install, a module whose ``__spec__``
    was cleared) counts as "not findable" -- the read paths then refuse with
    their usual ``IntentError`` instead of dying here."""
    try:
        return importlib.util.find_spec("ifcopenshell")
    except _FINDER_ERRORS:
        return None


def _is_shim(spec) -> bool:
    return bool(spec.origin) and _SHIM_MARK in spec.origin


def ifcopenshell_findable() -> bool:
    """True when ``import ifcopenshell`` would currently succeed (the real
    library, or the shim once its dir is on ``sys.path``)."""
    return _ifcopenshell_spec() is not None


@functools.lru_cache(maxsize=None)
def ifc_authoring_available() -> bool:
    """True iff ``import ifcopenshell`` in THIS process yields a REAL
    ifcopenshell distribution that ships ``ifcopenshell.api`` -- the surface
    IFC *authoring* (spec->ifc, the tekton-ifc generators) and the real-library
    parity tests need.  The bundled steplite shim never counts: it only reads.

    Decided from ``find_spec`` origins alone -- nothing is imported, so it is
    safe to ask before (or without) paying for the wheel's import -- and it
    mirrors what the import would actually do: a real origin answers directly;
    a shim origin (the shim can sit AHEAD of a wheel on a skill child's
    ``PYTHONPATH``) answers the way the shim's own stand-down law does -- the
    real distribution further along ``sys.path`` wins, unless
    ``RVT_STEPLITE_FORCE`` pins the reader-only shim, in which case this
    truthfully says False for the process.  So the answer does not depend on
    whether :func:`ensure_ifc_reader` already appended the shim.  Memoised: a
    wheel does not appear or vanish mid-process (tests that flip the backend
    do it in child interpreters).

    This is THE query; ``tests/conftest.py`` builds its one
    ``needs_ifc_authoring`` gate on it (#367) instead of every test module
    hand-rolling "is the ifcopenshell I can import the real one"."""
    spec = _ifcopenshell_spec()
    if spec is not None and _is_shim(spec):
        spec = None
        if not os.environ.get(FORCE_ENV):            # the shim would stand down to ...
            # non-str entries (a pathlib.Path some tool appended): skipped, as
            # CPython's PathFinder and the shim's own stand-down walk skip them
            behind = [p for p in sys.path if isinstance(p, str) and _SHIM_MARK not in p]
            try:
                spec = importlib.machinery.PathFinder.find_spec("ifcopenshell", behind)
            except _FINDER_ERRORS:
                pass
    if spec is None or not spec.origin or _is_shim(spec):
        return False
    pkg_dirs = spec.submodule_search_locations or [os.path.dirname(spec.origin)]
    return any(os.path.isfile(os.path.join(d, "api", "__init__.py")) for d in pkg_dirs)


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
