#!/usr/bin/env python3
"""tekton skill bootstrap -- a thin shim over ``skills/_shared/tekton_env.py``
(the ONE shared environment module).  Identical in every tekton skill.

    python scripts/_bootstrap.py                        # ONE readiness line (<2 s), exit 0/3
    python scripts/_bootstrap.py --json                 # the full preflight dict
    python scripts/_bootstrap.py run frontdoor.py author --prompt "..." --json
                                                        # run a sibling script, engine ready:
                                                        #   no pip, no eval, no env prefix
    python scripts/_bootstrap.py doctor [--install]     # one-time environment check/setup

The plugin root is resolved strictly by walking UP from this file to the
directory containing ``.claude-plugin/`` -- never by searching the
filesystem.  The engine is made importable by inserting the bundled
``<plugin-root>/lib/src`` into ``sys.path`` (vendored olefile fallback
included); nothing is installed on the hot path.

From another script in this directory:
    from _bootstrap import ensure_rvt; ensure_rvt()
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_tekton_env():
    """Locate skills/_shared/tekton_env.py by walking up from THIS file
    (the same no-search rule as the module itself), import it by path."""
    if "tekton_env" in sys.modules:
        return sys.modules["tekton_env"]
    d = _HERE
    while True:
        cand = os.path.join(d, "skills", "_shared", "tekton_env.py")
        if os.path.isfile(cand):
            break
        parent = os.path.dirname(d)
        if parent == d:
            sys.stderr.write(
                "tekton: skills/_shared/tekton_env.py not found on the path above "
                f"{_HERE} -- the plugin folder is incomplete (keep skills/ together).\n")
            raise SystemExit(3)
        d = parent
    spec = importlib.util.spec_from_file_location("tekton_env", cand)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tekton_env"] = mod
    spec.loader.exec_module(mod)
    return mod


_env = _load_tekton_env()

# re-exports (legacy names kept: older scripts do `from _bootstrap import ensure_rvt`)
plugin_root = _env.plugin_root
ensure_engine = _env.ensure_engine
ensure_rvt = _env.ensure_engine
preflight = _env.preflight
family_donor_status = _env.family_donor_status


def main(argv=None) -> int:
    return _env.cli(list(sys.argv[1:] if argv is None else argv), base_dir=_HERE)


if __name__ == "__main__":
    raise SystemExit(main())
