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
LAZY fallback that follows the one contract every chokepoint wrapper has
(``rvt.frontdoor.standalone.default_schema_loader``, #315/#376) --

  * the default-path call (no arg, ``None``, or ``DEFAULT_PATH``) triggers
    ONE activation of ``rvt.frontdoor.standalone.install_schema()`` -- the
    proven chokepoint reroute that parses the schema embedded in the bundled
    genesis base (byte-identical to the corpus stream; sha256-pinned) -- and
    answers with the schema it installed;
  * any other path is parsed verbatim by ``rvt.schema.load_schema_file`` --
    it never activates the fallback, and a missing one raises
    ``FileNotFoundError`` naming it.  Nothing here re-enters
    ``rvt.schema.load_schema`` (which may be this wrapper itself when it was
    armed after a completed ``install_schema()``).

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
    status: ``installed`` | ``already`` | ``corpus-present`` (the default
    path is already a real file -- the research corpus, or the cache file a
    completed ``install_schema()`` left as DEFAULT_PATH -- so the wrapper is
    still installed but its fallback will simply never fire)."""
    import rvt.schema as _schema

    if getattr(_schema, _FLAG, False):
        return "already"

    orig_load = _schema.load_schema
    orig_default = _schema.DEFAULT_PATH
    # the engine's verbatim leaf loader (#315); an engine older than it only
    # has load_schema, which is verbatim for explicit paths and is not us
    load_file = getattr(_schema, "load_schema_file", orig_load)

    def _load_schema_lazy(path=None):
        # any other path: parsed verbatim, never the fallback; a missing one
        # raises FileNotFoundError naming it
        if path is not None and path != orig_default and path != _schema.DEFAULT_PATH:
            return load_file(path)
        # the default path the wrapped loader can already answer (research
        # corpus on disk, or armed over a completed install_schema())
        if os.path.isfile(orig_default):
            return orig_load(orig_default)
        # the default path on a bare machine: activate the proven standalone
        # reroute ONCE (it re-points every chokepoint past this wrapper) and
        # answer with the schema it installed
        try:
            from rvt.frontdoor import standalone
            standalone.install_schema()
        except Exception as e:                                  # noqa: BLE001
            raise FileNotFoundError(
                f"schema stream not found at {orig_default!r} and the bundled-"
                f"base fallback failed ({type(e).__name__}: {e}) -- the plugin "
                "bundle is incomplete (assets/genesis/G_ABPD.rvt)") from e
        return standalone.bundled_schema()

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
