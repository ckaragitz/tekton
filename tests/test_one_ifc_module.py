"""#507 -- ONE executed copy of ``tools/ifc_intent.py`` per process.

``tools/ifc_intent.py`` (the ifc-room stream's staged builder that the front
door reuses) has two in-process doors: ``rvt.frontdoor.build.load_ifc_room_module``
(the prompt / IFC routes, the router, ``add_to_project``) and the by-name
``import ifc_intent`` of the dev tools and tests that put ``tools/`` on
``sys.path``.  Before #507 the loader registered the private name
``_frontdoor_ifc_room``, so a process through both doors executed the module
twice and ``rvt.famload_fix`` scanned every alias to patch "it".  Now the
loader registers -- or, when the by-name import came first, adopts --
``sys.modules["ifc_intent"]``: one name, one object, whichever door was first.

Every check runs in a FRESH interpreter: the loader is process-cached and
``conftest.load_tool("ifc_intent")`` hands a requesting test file its own fresh
copy on purpose, so only a subprocess can say who loaded first and what a
product process holds.  Fresh-clone safe (bundled 2026 pin, famgen-free walls
prompt, ``no_handoff=True``).

1. structure, both door orders: one module object, it IS
   ``sys.modules["ifc_intent"]`` and IS ``load_ifc_room_module()``, and
   ``famload_fix.fixed_product_path()`` patches (then reverts) that object's
   ``_connector_manager_for`` -- also when the by-name import was first;
2. behaviour, both orders: a prompt job (``FD.author``) and a by-name import in
   one process -> exactly one live module whose ``__file__`` ends in
   ``ifc_intent.py``, named ``ifc_intent``, and it is the loader's object.
"""
import json
import subprocess
import sys
import textwrap

import pytest

from conftest import ROOT, pinned_base

WALLS_PROMPT = "a storage room 6 by 4 meters with no equipment"   # famgen-free (as in test_one_job_module)

_HEAD = textwrap.dedent("""
    import json, os, sys
    root = {root!r}
    sys.path.insert(0, os.path.join(root, "src"))
    sys.path.insert(0, os.path.join(root, "tools"))                # the dev tools' / tests' by-name door
    def by_name():
        import ifc_intent
        return ifc_intent
    def live_names():
        return sorted(k for k, m in list(sys.modules.items())
                      if (getattr(m, "__file__", None) or "").endswith("ifc_intent.py"))
    def emit(d):
        sys.__stdout__.write("PROBE " + json.dumps(d) + "\\n")
""").format(root=ROOT)

_STRUCTURE = _HEAD + textwrap.dedent("""
    from rvt.frontdoor import build as B
    from rvt import famload_fix as FX
    order = sys.argv[1]
    doors = [B.load_ifc_room_module, by_name] if order == "loader-first" else [by_name, B.load_ifc_room_module]
    got = [door() for door in doors]
    orig = got[0]._connector_manager_for
    with FX.fixed_product_path(fix_specimen_phase=False):
        patched = got[0]._connector_manager_for is not orig
    emit({"same": got[0] is got[1], "names": live_names(), "name": got[0].__name__,
          "loader_is_entry": B.load_ifc_room_module() is sys.modules.get("ifc_intent"),
          "patched": patched, "reverted": got[0]._connector_manager_for is orig})
""")

_JOBS = _HEAD + textwrap.dedent("""
    import rvt.frontdoor as FD
    order, out, text = sys.argv[1:4]
    def prompt():
        return FD.author(prompt=text, out=os.path.join(out, "p"), no_handoff=True, quiet=True)
    steps = [prompt, by_name] if order == "prompt-first" else [by_name, prompt]
    res = {step.__name__: step() for step in steps}
    from rvt.frontdoor import build as B
    emit({"ok": bool(res["prompt"].ok), "names": live_names(),
          "loader_is_entry": B.load_ifc_room_module() is sys.modules.get("ifc_intent")})
""")


def _probe(code, *argv):
    proc = subprocess.run([sys.executable, "-c", code, *argv], cwd=ROOT,
                          capture_output=True, text=True, timeout=600)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE ")]
    assert proc.returncode == 0 and len(lines) == 1, (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:])
    return json.loads(lines[0][len("PROBE "):])


@pytest.mark.parametrize("order", ["loader-first", "import-first"])
def test_loader_and_by_name_import_share_one_ifc_intent(order):
    got = _probe(_STRUCTURE, order)
    assert got["same"] is True and got["names"] == ["ifc_intent"], got   # was ['_frontdoor_ifc_room', 'ifc_intent']
    assert got["name"] == "ifc_intent" and got["loader_is_entry"] is True, got
    assert got["patched"] is True and got["reverted"] is True, got       # famload_fix reaches the one copy by its one name


@pytest.mark.parametrize("order", ["prompt-first", "import-first"])
def test_prompt_job_and_by_name_import_in_one_process_share_one_ifc_intent(order, tmp_path):
    pinned_base(2026)                                              # the walls prompt builds on the 2026 pin
    got = _probe(_JOBS, order, str(tmp_path), WALLS_PROMPT)
    assert got["ok"] is True, got
    assert got["names"] == ["ifc_intent"], got
    assert got["loader_is_entry"] is True, got                     # ... and build._ROOM is that one object
