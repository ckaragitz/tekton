#!/usr/bin/env python3
"""tekton_schema.py -- LAZY bundled-schema fallback for bare surfaces.

The problem this kills (found by ``tools/surface_bench.py``, 2026-08-04):
``rvt.schema.DEFAULT_PATH`` points at the research corpus
(``<repo>/extracted/racbasicsampleproject/Formats__Latest.gz/000.bin``).
On any machine that has ONLY the plugin -- every sandboxed AI surface --
that file does not exist, so the first no-arg ``ObjectDecoder()`` /
``ObjectEncoder()`` / ``ADocumentDecoder()`` dies with ``FileNotFoundError``.
The AUTHOR path is already immune (``rvt.frontdoor.standalone`` reroutes the
chokepoints during ``activate()``), but the EDIT path is not:
``rvt_edit.py set-level`` -> ``rvt.manipulate.verify_manipulated`` ->
``ObjectDecoder()`` -> boom, on all three benchmarked surfaces including a
warm local repo running the plugin's bundled engine.

The fix: :func:`install` wraps ``rvt.schema.load_schema`` with a
LAZY fallback --

  * an explicit path that exists on disk loads exactly as before;
  * the default (or any missing) path triggers ONE activation of
    ``rvt.frontdoor.standalone.install_schema()`` -- the proven chokepoint
    reroute that parses the schema embedded in the bundled genesis base
    (byte-identical to the corpus stream; sha256-pinned) -- and returns the
    bundled schema.

Cost model (measured): installing the wrapper is attribute assignment
(~0 ms) plus one ``import rvt.schema`` (~16 ms); the schema parse itself
(~60 ms) happens only IF a job actually needs a decoder, never during
preflight.  ``tekton_env.ensure_engine()`` calls :func:`install` so every
skill script launched through ``_bootstrap.py run ...`` is covered.

HARD RULE unchanged: nothing here reads, probes, or lists any Autodesk
installation directory; the fallback schema comes ONLY from the plugin's
own bundled base (or ``$RVT_GENESIS_BASE`` when the user set one).
"""
from __future__ import annotations

import os
import sys

_FLAG = "_tekton_lazy_bundled_schema"     # set on rvt.schema once installed

#: modules that ``from .schema import load_schema`` at import time; any of
#: them already imported when we install must be re-pointed too (the same
#: list rvt.frontdoor.standalone.install_schema patches).
_FROM_IMPORTERS = ("rvt.objects", "rvt.encode", "rvt.adocument")


def install() -> str:
    """Idempotently wrap the default-schema chokepoint.  Returns a one-word
    status: ``installed`` | ``already`` | ``corpus-present`` (research
    machine with the corpus on disk at an unwrapped DEFAULT_PATH -- the
    wrapper is still installed but will simply never fire)."""
    import rvt.schema as _schema

    if getattr(_schema, _FLAG, False):
        return "already"

    orig_load = _schema.load_schema
    orig_default = _schema.DEFAULT_PATH

    def _load_schema_lazy(path: str = orig_default, _orig=orig_load):
        # 1. any path that actually exists loads exactly as before
        if path and os.path.isfile(path):
            return _orig(path)
        # 2. default / missing path on a bare machine: activate the proven
        #    standalone reroute ONCE, then answer from the bundled schema.
        try:
            from rvt.frontdoor import standalone
            standalone.install_schema()
        except Exception as e:                                  # noqa: BLE001
            raise FileNotFoundError(
                f"schema stream not found at {path!r} and the bundled-base "
                f"fallback failed ({type(e).__name__}: {e}) -- the plugin "
                "bundle is incomplete (assets/genesis/G_ABPD.rvt)") from e
        # install_schema replaced rvt.schema.load_schema with the bundled
        # loader; delegate so its default-path semantics answer.
        return _schema.load_schema(path)

    _schema.load_schema = _load_schema_lazy
    # re-point any from-importer that beat us to it
    for name in _FROM_IMPORTERS:
        mod = sys.modules.get(name)
        if mod is not None and getattr(mod, "load_schema", None) is orig_load:
            mod.load_schema = _load_schema_lazy
    setattr(_schema, _FLAG, True)
    return "corpus-present" if os.path.isfile(orig_default) else "installed"


if __name__ == "__main__":                                       # pragma: no cover
    print(install())
