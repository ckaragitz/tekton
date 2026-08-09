"""Regression gate for issue #6: the prompt-only path must not pay the IFC
import tax.

Importing the whole front door (``rvt.frontdoor`` + ``.build``, the
validator, ``rvt.ifc.intent`` and ``rvt.ifc.product_facts``) and running the
prompt route up to a resolved intent must leave ``ifcopenshell`` -- and the
numpy / shapely it drags in when the real library is installed -- OUT of
``sys.modules``.  The IFC read path must still import it on first use.

The check runs in a subprocess whose ``sys.path`` carries the bundled
steplite shim dir (exactly what ``tekton_env.ensure_engine`` appends on a
surface without the real library), so an eager ``import ifcopenshell`` is
caught on EVERY box: with the real 190 MB package installed it resolves to
that, in a fresh clone / CI it resolves to the shim -- either way it would
show up in ``sys.modules``.  A positive control at the end proves the import
WAS resolvable, so the negative assertions are meaningful.  (The plugin-copy,
numpy-only cousin of this gate is test_coldstart.test_frontdoor_import_is_numpy_free.)
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SHIM = os.path.join(SRC, "rvt", "ifc", "_ifcos_shim")

PROMPT = ("an electrical room 20x15 ft rated for 800 A service with one "
          "switchboard and two lighting panels")

HEAVY = ("ifcopenshell", "numpy", "shapely")

PREAMBLE = f"import sys\nsys.path.insert(0, {SRC!r})\n"


def _run(code: str) -> subprocess.CompletedProcess:
    """``code`` in a fresh interpreter with the engine source first on the path."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    return subprocess.run([sys.executable, "-c", PREAMBLE + code], cwd=ROOT,
                          env=env, capture_output=True, text=True, timeout=60)


def test_frontdoor_import_and_prompt_route_are_ifcopenshell_free():
    code = (
        f"sys.path.append({SHIM!r})\n"
        f"HEAVY = {HEAVY!r}\n"
        "def leaked(stage):\n"
        "    bad = [m for m in HEAVY if m in sys.modules]\n"
        "    assert not bad, f'{stage}: eager import of {bad}'\n"
        "import rvt.frontdoor, rvt.frontdoor.build, rvt.validate\n"
        "import rvt.ifc.intent as I, rvt.ifc.product_facts\n"
        "leaked('import')\n"
        "from rvt.frontdoor import prompt_intent as PI\n"
        f"p = PI.parse_prompt({PROMPT!r})\n"
        "assert p.room is not None and p.items\n"
        "leaked('prompt parse')\n"
        "# positive control: the deferred import IS resolvable here (real or shim)\n"
        "assert I._load_ifcos() is True\n"
        "assert 'ifcopenshell' in sys.modules\n"
        "assert I.ifcopenshell is sys.modules['ifcopenshell']   # global rebound\n"
        "print('IFCOS-LAZY-OK', sys.modules['ifcopenshell'].__file__)\n")
    r = _run(code)
    assert r.returncode == 0, r.stderr[-3000:]
    assert "IFCOS-LAZY-OK" in r.stdout


def test_resolve_intent_still_refuses_cleanly_without_any_ifcopenshell():
    """No real library and no shim on the path: importing intent works, and
    resolve_intent raises the same IntentError as before (not an ImportError
    corpse, not a silent empty model)."""
    code = (
        "import importlib.abc\n"
        "class _Block(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'ifcopenshell' or name.startswith('ifcopenshell.'):\n"
        "            raise ModuleNotFoundError(name)\n"
        "sys.meta_path.insert(0, _Block())\n"
        "import rvt.ifc.intent as I\n"
        "assert I._load_ifcos() is False\n"
        "try:\n"
        "    I.resolve_intent('does-not-matter.ifc')\n"
        "except I.IntentError as e:\n"
        "    assert 'ifcopenshell is required' in str(e); print('REFUSED-OK')\n"
        "else:\n"
        "    raise AssertionError('resolve_intent did not refuse')\n")
    r = _run(code)
    assert r.returncode == 0, r.stderr[-3000:]
    assert "REFUSED-OK" in r.stdout
