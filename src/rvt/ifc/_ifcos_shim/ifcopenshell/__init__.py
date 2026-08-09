"""ifcopenshell -- tekton's stdlib-only FALLBACK package (steplite backend).

This package directory is appended to ``sys.path`` by the engine when
``rvt.ifc`` is imported (``rvt.ifc._fallback``, issue #130 -- and by
``tekton_env.ensure_engine``, which delegates to it) ONLY when the real
ifcopenshell distribution is absent, so ``import ifcopenshell`` inside the
read paths (``rvt.ifc.intent``, ``rvt.ifc.product_facts``) resolves here as
an ordinary import fallback -- try ifcopenshell, else steplite -- with no
monkeypatching and no edits to the consumer modules.

STAND-DOWN GUARANTEE: even if this directory ends up on ``sys.path`` (or a
child's ``PYTHONPATH``) while a REAL ifcopenshell is also installed, this
``__init__`` finds the real distribution on the rest of ``sys.path``, loads
it, and replaces itself in ``sys.modules`` -- the real library always wins.
Set ``RVT_STEPLITE_FORCE=1`` to skip that check and force the pure-python
backend (the equivalence tests use this).

Served surface (the read-path subset; see ``rvt.ifc.steplite``):
``open``, file ``schema``/``by_type``/``by_id``/``by_guid``/``get_inverse``,
entity ``is_a``/``id``/named attributes/inverse attributes, and
``ifcopenshell.util.{element,unit,placement}``.  The authoring / validation
surfaces (``ifcopenshell.api``, ``.geom``, ``.validate``, ``.guid``) are NOT
served -- importing them raises ModuleNotFoundError exactly as when
ifcopenshell is absent, which is the honest signal those routes still need
the real library.
"""
from __future__ import annotations

import importlib.machinery as _ilm
import importlib.util as _ilu
import os as _os
import sys as _sys

_PKG_DIR = _os.path.dirname(_os.path.abspath(__file__))
_SHIM_ROOT = _os.path.dirname(_PKG_DIR)          # .../rvt/ifc/_ifcos_shim


def _find_real_spec():
    """A spec for a REAL ifcopenshell elsewhere on sys.path (never us)."""
    paths = []
    for p in _sys.path:
        try:
            ap = _os.path.abspath(p or _os.getcwd())
        except (TypeError, ValueError):
            continue
        if ap != _SHIM_ROOT:
            paths.append(p)
    try:
        spec = _ilm.PathFinder.find_spec("ifcopenshell", paths)
    except (ImportError, AttributeError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    if _os.path.abspath(_os.path.dirname(spec.origin)) == _PKG_DIR:
        return None                               # found ourselves again
    return spec


_real_spec = None if _os.environ.get("RVT_STEPLITE_FORCE") else _find_real_spec()

if _real_spec is not None:
    # ---- stand down: hand the import over to the real distribution --------
    _real = _ilu.module_from_spec(_real_spec)
    _sys.modules[__name__] = _real               # import machinery returns this
    _real_spec.loader.exec_module(_real)
    # mirror into our namespace too, for any caller holding this module object
    globals().update({k: v for k, v in vars(_real).items()
                      if not k.startswith("__")})
    __path__ = list(getattr(_real, "__path__", []))  # noqa: F811 -- submodules
else:
    # ---- steplite backend --------------------------------------------------
    from rvt.ifc.steplite import (                     # noqa: F401
        STEPLITE_VERSION as _STEPLITE_VERSION,
        Entity as entity_instance,                     # nearest-name alias
        File as file,                                  # noqa: A001
        StepLiteError as Error,
        open,                                          # noqa: A001
    )

    IS_STEPLITE = True
    version = f"steplite-{_STEPLITE_VERSION} (pure-python IFC read subset)"

    from . import util as util                         # noqa: F401,E402
