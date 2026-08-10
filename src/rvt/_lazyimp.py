"""rvt._lazyimp -- import-on-first-use proxies for HEAVY optional modules.

WHY (perf-coldstart stream, 2026-08-04): a module-level ``import numpy``
inside the author path meant two things on a bare sandboxed surface:

  * ~47 ms of import work on EVERY process that touches the front door,
    even for routes that never do numeric math (measured: the -X importtime
    profile of ``author --prompt`` in the bare env -- numpy is the single
    biggest import on the path); and, far worse,
  * a hard ``ModuleNotFoundError`` at IMPORT time when numpy is absent --
    the whole author route (even ``--handoff-only``) died before doing any
    work, forcing a minutes-long ``pip install`` onto the hot path.

The proxy defers the real import to the FIRST ATTRIBUTE ACCESS.  Modules
whose annotations are lazy (``from __future__ import annotations``) and
that evaluate no module-level ``np.…`` expression import instantly and
numpy-free; the numeric code paths behave exactly as before once touched.
On first use the proxy also REBINDS the owner module's global to the real
module, so steady-state access has zero indirection.

If the module is genuinely missing, the first USE raises ``ImportError``
naming the module and the operation that needed it -- one clear error at
the exact point of need, never a corpse at import time.

Usage (the whole patch a module needs)::

    from .._lazyimp import lazy_import
    np = lazy_import("numpy", globals(), "np", hint="geometry resolution")

Territory: perf-coldstart stream (``docs/inbox/perf-coldstart.md``).
"""
from __future__ import annotations

import importlib
from typing import Any, MutableMapping, Optional

__all__ = ["ExtraNotInstalled", "LazyModule", "lazy_import"]


class ExtraNotInstalled(ImportError):
    """The first USE of a lazy optional extra that is not installed.  An
    ``ImportError`` (every existing handler still catches it) whose ``name``
    is the missing top-level module and ``hint`` the operation that needed
    it -- so a route boundary can word its own one-line prerequisite (#127)
    without parsing the message or digging in ``__cause__``."""

    def __init__(self, msg: str, *, name: str, hint: str = ""):
        super().__init__(msg, name=name)
        self.hint = hint


class LazyModule:
    """A stand-in that becomes the real module on first attribute access."""

    __slots__ = ("_name", "_owner", "_binding", "_hint", "_mod")

    def __init__(self, name: str, owner: Optional[MutableMapping[str, Any]] = None,
                 binding: Optional[str] = None, hint: str = ""):
        self._name = name
        self._owner = owner
        self._binding = binding
        self._hint = hint
        self._mod = None

    def _load(self):
        mod = self._mod
        if mod is None:
            try:
                mod = importlib.import_module(self._name)
            except ImportError as e:
                raise ExtraNotInstalled(
                    f"{self._name} is required here"
                    + (f" ({self._hint})" if self._hint else "")
                    + f" but is not installed: {e}. One-time fix: "
                    f"python -m pip install {self._name} "
                    "(or run the skill's doctor --install)",
                    name=self._name, hint=self._hint) from e
            self._mod = mod
            # steady state: the owner's global now IS the real module
            if self._owner is not None and self._binding:
                if self._owner.get(self._binding) is self:
                    self._owner[self._binding] = mod
        return mod

    def __getattr__(self, item: str) -> Any:
        return getattr(self._load(), item)

    def __repr__(self) -> str:                            # pragma: no cover
        state = "loaded" if self._mod is not None else "lazy"
        return f"<LazyModule {self._name} ({state})>"


def lazy_import(name: str, owner: Optional[MutableMapping[str, Any]] = None,
                binding: Optional[str] = None, hint: str = "") -> LazyModule:
    """A :class:`LazyModule` for ``name``; pass ``globals()`` + the binding
    name so the first use rebinds the owner's global to the real module."""
    return LazyModule(name, owner, binding, hint)
