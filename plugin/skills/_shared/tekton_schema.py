#!/usr/bin/env python3
"""tekton_schema.py -- LAZY one-time schema install for bare surfaces.

History: ``rvt.schema.DEFAULT_PATH`` names the research corpus
(``<repo>/extracted/racbasicsampleproject/Formats__Latest.gz/000.bin``),
absent on any machine that has ONLY the plugin, and the bare EDIT path
(``rvt_edit.py`` -> ``verify_manipulated`` -> no-arg ``ObjectDecoder()``)
once died on it (``tools/surface_bench.py``, 2026-08-04).  The engine has
since grown its own default-path fallback (``rvt.schema.load_schema`` ->
the sha-pinned bundled base), so what this module still buys is latency
and completeness: the FIRST default-path need on a bare machine escalates
to ``rvt.frontdoor.standalone.install_schema()`` -- every chokepoint then
answers in memory (~1 us/call instead of the native fallback's per-call
resolve + sha256, measured in ``docs/inbox/install-schema.md``) and the
singleton codecs are seeded -- and it covers an engine that predates the
native fallback.

:func:`install` decides at arm time: if the default path is already a real
file (the research corpus) or the host process has already completed
``install_schema()`` (its loaders answer in memory; since #208 it leaves
``DEFAULT_PATH`` alone, so that is asked of its state, not of the path)
nothing is wrapped -- the loader in place answers.  Otherwise
``rvt.schema.load_schema`` (and its from-imported copies) become a wrapper
with the one contract every chokepoint loader has
(``standalone.default_schema_loader``, #315/#376):

  * the default-path call (no arg, ``None``, or ``DEFAULT_PATH``) activates
    ``install_schema()`` ONCE -- it parses the schema embedded in the bundled
    genesis base (byte-identical to the corpus stream; sha256-pinned) and
    re-points every chokepoint past this wrapper -- and answers with the
    schema it installed;
  * any other path is parsed verbatim by ``rvt.schema.load_schema_file`` --
    it never activates the install, and a missing one raises
    ``FileNotFoundError`` naming it.  Nothing here calls
    ``rvt.schema.load_schema``, so no arm order can re-enter the wrapper.

Cost model (measured): arming is attribute assignment (~0 ms) plus one
``import rvt.schema`` (~16 ms); the schema parse itself (~60 ms) happens
only IF a job actually needs a decoder, never during preflight.
``tekton_env.ensure_engine()`` calls :func:`install` so every skill script
launched through ``_bootstrap.py run ...`` is covered.

HARD RULE unchanged: nothing here reads, probes, or lists any Autodesk
installation directory; the schema comes ONLY from the plugin's own bundled
base (or ``$RVT_GENESIS_BASE`` when the user set one).
"""
from __future__ import annotations

import os
import sys

_FLAG = "_tekton_lazy_bundled_schema"     # set on rvt.schema once armed

#: modules that ``from .schema import load_schema`` at import time; any of
#: them already imported when we install must be re-pointed too (the same
#: list rvt.frontdoor.standalone.install_schema patches).
_FROM_IMPORTERS = ("rvt.objects", "rvt.encode", "rvt.adocument")


def install() -> str:
    """Idempotently arm the lazy install.  Returns ``installed`` |
    ``already`` | ``corpus-present`` (the default path is a real file: the
    research corpus) | ``host-installed`` (``install_schema()`` already ran
    in this process: its in-memory loaders are in place) -- the last two
    wrap nothing."""
    import rvt.schema as _schema

    if getattr(_schema, _FLAG, False):
        return "already"
    setattr(_schema, _FLAG, True)
    orig_default = _schema.DEFAULT_PATH
    if os.path.isfile(orig_default):
        return "corpus-present"
    host = sys.modules.get("rvt.frontdoor.standalone")     # never imported FOR this check (cold start)
    if (getattr(host, "_SCHEMA_STATE", None) or {}).get("installed"):   # engine-skew safe, as below
        return "host-installed"

    orig_load = _schema.load_schema
    # the engine's verbatim leaf loader (#315); an engine older than it only
    # has load_schema, which is verbatim for explicit paths and is not us
    load_file = getattr(_schema, "load_schema_file", orig_load)

    def _load_schema_lazy(path=None):
        # explicit path: verbatim (the default family = no arg, None, the
        # arm-time default and the live DEFAULT_PATH, as default_schema_loader's)
        if path not in (None, orig_default, _schema.DEFAULT_PATH):
            return load_file(path)
        # default path: install once, answer with what it installed
        try:
            from rvt.frontdoor import standalone
            rep = standalone.install_schema()
        except Exception as e:                                  # noqa: BLE001
            raise FileNotFoundError(
                f"schema stream not found at {orig_default!r} and the bundled-"
                f"base fallback failed ({type(e).__name__}: {e}) -- the plugin "
                "bundle is incomplete (assets/genesis/G_ABPD.rvt)") from e
        return standalone.bundled_schema(rep["from"])

    _schema.load_schema = _load_schema_lazy
    # re-point any from-importer that beat us to it
    for name in _FROM_IMPORTERS:
        mod = sys.modules.get(name)
        if mod is not None and getattr(mod, "load_schema", None) is orig_load:
            mod.load_schema = _load_schema_lazy
    return "installed"


if __name__ == "__main__":                                       # pragma: no cover
    print(install())
