#!/usr/bin/env bash
# Setup script for Claude Code cloud sessions (claude.ai/code) and CI-like sandboxes.
# Point the cloud environment's "Setup script" at:   bash scripts/cloud-setup.sh
# Idempotent; safe to re-run. Needs network access to PyPI (the Default/"Trusted" level has it).
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -e ".[test]"               # engine + the `test` extra (pytest, numpy) declared in pyproject.toml
# Optional IFC *authoring* backend (the `ifc` extra = pinned ifcopenshell); IFC reading works
# without it (steplite). Don't fail setup on it.
.venv/bin/python -m pip install -q -e ".[ifc]" 2>/dev/null || echo "note: ifcopenshell not installed (optional; IFC authoring only)"

git config pull.rebase true
git config rebase.autoStash true

# Smoke: engine imports, plugin mirrors in sync, portable paths.
.venv/bin/python - <<'PY'
import rvt, rvt.frontdoor.build  # noqa
print("tekton engine import OK")
PY
.venv/bin/python tools/sync_plugin.py --check || echo "warning: plugin drift — run tools/sync_plugin.py"
.venv/bin/python tools/dev/check_portable_paths.py
echo "cloud-setup: READY  (.venv/bin/python; run tests with .venv/bin/python -m pytest tests/test_<yours>.py -q)"
