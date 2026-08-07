#!/usr/bin/env python3
"""rvt_validate — Autodesk-free arbiter of .rvt validity.

Usage:
    .venv/bin/python tools/rvt_validate.py FILE.rvt [FILE2.rvt ...]
        [--json out.json] [--layers structure,consistency,semantic]
        [--decode-limit N] [--quiet]

Exit status 0 = every file validated with ZERO errors (warnings allowed);
1 = at least one file has errors.  See src/rvt/validate.py and
docs/writer/validation.md for the layered checks (L1 structure / L2
consistency / L3 semantic) and the meaning of each finding.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from rvt.validate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
