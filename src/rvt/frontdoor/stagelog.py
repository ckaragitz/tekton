"""rvt.frontdoor.stagelog -- ONE quiet-stage log for the three front-door routes.

``frontdoor.py author --json`` / ``route.py run --json`` / the plugin's ``go``
promise exactly one JSON document on stdout and nothing on stderr, but the
stage chains they drive print progress (``[ifc_intent] F ...``, ``[rvt_job]
planning ...``).  Every route therefore runs its stages under
:func:`stage_stdout`: the progress streams into ``<out_dir>/<name>``
(``build.log`` for prompt/IFC builds #312, ``route.log`` for the router
#188/#330, ``edit.log`` for ``--rvt --edit`` #373) and the manifest names
that path beside ``json`` / ``md`` -- never a delivered file role.

The contract every caller shares (issue #373):

* the log is opened at CALL time, before the caller's stage ``try``, so a
  failure to open it can never read as "stage crashed" with no stage run;
* line-buffered utf-8 with ``backslashreplace``: a long job can be tailed, a
  killed one keeps its progress, an odd byte never raises mid-stage;
* a log that cannot be opened -- a read-only / vanished ``out_dir``
  (``OSError``) or an ``--out`` under a quarantined name that the standalone
  tripwire's audit hook refuses from inside ``open()`` (``StandaloneError``,
  a ``RuntimeError``) -- degrades to an unlogged run: an in-memory sink plus
  ONE note through ``on_degrade``.  A label, never an error: logging is an
  observer and can never cost a delivery (hard rule 1);
* capture is ``sys.stdout``-level only; a stage that shells out captures its
  child itself.

Stdlib only and import-light on purpose: nothing here pulls the rest of
``rvt.frontdoor`` in.
"""
from __future__ import annotations

import contextlib
import io
import os
from typing import Callable, ContextManager, Optional

__all__ = ["stage_stdout"]


def stage_stdout(out_dir: str, name: str, *, quiet: bool,
                 on_open: Optional[Callable[[str], None]] = None,
                 on_degrade: Optional[Callable[[str], None]] = None) -> ContextManager[None]:
    """``quiet``: redirect ``sys.stdout`` into ``<out_dir>/<name>`` for the
    duration of the ``with`` block and report the path through
    ``on_open(path)``; not ``quiet``: a null context (progress stays live on
    the caller's stdout, no file, nothing to name).  If the log cannot be
    opened the block still runs, its output goes to an in-memory sink, and
    ``on_degrade(note)`` receives the one-line reason."""
    if not quiet:
        return contextlib.nullcontext()
    log_p = os.path.join(out_dir, name)
    try:
        fh = open(log_p, "w", buffering=1, encoding="utf-8", errors="backslashreplace")
    except Exception as e:               # noqa: BLE001 -- OSError, or whatever an audit hook raises
        if on_degrade is not None:
            on_degrade(f"{name} not writable ({type(e).__name__}: {e}); stage output not logged")
        return _redirect_stdout_into(io.StringIO())
    if on_open is not None:
        on_open(log_p)
    return _redirect_stdout_into(fh)


@contextlib.contextmanager
def _redirect_stdout_into(fh):
    with fh, contextlib.redirect_stdout(fh):
        yield
