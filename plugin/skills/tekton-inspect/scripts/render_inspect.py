#!/usr/bin/env python3
"""render_inspect.py -- the LOAD-vs-RENDER lens for any .rvt (skill entry).

A file that LOADS (the viewer opens it) may still RENDER nothing: an
element only DRAWS when its Partitions/<N> seq-103 record carries baked
geometry (a GElement B-rep / mesh / curves, or an instance reference to a
symbol whose own rep carries a solid).  A `SerializedDummy` rep = nothing to
draw ("Design is empty").  This entry runs the engine's geometry-carriage
inspector, `rvt.render.inspect`, so a passing LOAD verdict is never mistaken
for a passing RENDER verdict.

Usage (same flags as `python -m rvt.render.inspect`):
    python scripts/render_inspect.py file.rvt                    # every host element
    python scripts/render_inspect.py file.rvt --class SWall      # by seq-102 class name
    python scripts/render_inspect.py file.rvt --id 493612        # one element
    python scripts/render_inspect.py file.rvt --json geom.json   # machine-readable
    python scripts/render_inspect.py file.rvt --faces            # per-face plane/material dump

Read the `kind` column:  brep / mesh / instance-ref = draws; dummy /
empty-grep = LOADS BUT DOES NOT DRAW.  The final line summarises how many
elements carry baked or referenced geometry.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bootstrap import ensure_rvt  # noqa: E402

ensure_rvt()

import runpy  # noqa: E402

if __name__ == "__main__":
    # delegate to the engine module's CLI (single source of truth)
    sys.argv[0] = "rvt.render.inspect"
    runpy.run_module("rvt.render.inspect", run_name="__main__", alter_sys=True)
