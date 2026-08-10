"""#477 -- ONE executed copy of ``tools/rvt_job.py`` per PRODUCT process.

The job runner has two in-process doors: the ``--rvt`` route / router /
``tools/rvt_edit.py`` (``rvt.frontdoor.edit.load_job_module``) and the prompt /
IFC routes' identity + status gates (``tools/ifc_intent.py``).  Before #477 the
second door did ``sys.path.insert(0, tools); import rvt_job`` and a process
that ran both kinds of job ended with TWO executed copies
(``_frontdoor_rvt_job`` + ``rvt_job``).  Now both doors go through the one
cached loader, which registers the module under its one name, ``rvt_job``.

Pinned here, fresh-clone safe (bundled pinned bases + a famgen-free walls
prompt, ``no_handoff=True``):

1. structure -- the loader's object IS ``sys.modules["rvt_job"]`` and IS what
   ``tools/ifc_intent.py`` drives;
2. behaviour, BOTH job orders, each in a FRESH interpreter (the module is
   process-cached, so only a subprocess can say who loaded first): an edit job
   then a prompt job, and the reverse, leave exactly one live module whose
   ``__file__`` ends in ``rvt_job.py``, and it is ``load_job_module()``.
"""
import json
import os
import subprocess
import sys
import textwrap

import pytest

from conftest import ROOT, pinned_base

WALLS_PROMPT = "a storage room 6 by 4 meters with no equipment"   # famgen-free (as in test_status_gate)
EDIT_TEXT = "set level 1351691 elevation to 5 ft"                  # "GEN B1 - Basement", in every pin (as in test_edit_own_release)


def test_loader_registers_one_name_and_ifc_intent_drives_that_object(job):
    from rvt.frontdoor import build as B, edit as E
    assert job is E.load_job_module() is sys.modules["rvt_job"]
    assert job.__name__ == "rvt_job" and job.__file__.endswith("rvt_job.py")
    room = B.load_ifc_room_module()                                # tools/ifc_intent.py as the front door loads it
    assert room._job_runner() is job


_PROBE = textwrap.dedent("""
    import json, os, sys
    sys.path.insert(0, os.path.join({root!r}, "src"))
    import rvt.frontdoor as FD
    order, base, out = sys.argv[1], sys.argv[2], sys.argv[3]
    def edit():
        return FD.author(rvt=base, edit={edit!r}, out=os.path.join(out, "e"), no_handoff=True, quiet=True)
    def prompt():
        return FD.author(prompt={prompt!r}, out=os.path.join(out, "p"), no_handoff=True, quiet=True)
    jobs = [edit, prompt] if order == "edit-first" else [prompt, edit]
    oks = [bool(j().ok) for j in jobs]
    names = sorted(k for k, m in list(sys.modules.items())
                   if (getattr(m, "__file__", None) or "").endswith("rvt_job.py"))
    import rvt.frontdoor.edit as E
    sys.__stdout__.write("PROBE " + json.dumps({{"oks": oks, "names": names,
        "loader_is_rvt_job": E.load_job_module() is sys.modules.get("rvt_job")}}) + "\\n")
""")


@pytest.mark.parametrize("order", ["edit-first", "prompt-first"])
def test_edit_and_prompt_jobs_in_one_process_share_one_rvt_job(order, tmp_path):
    pinned_base(2026)                                              # the walls prompt builds on the 2026 pin
    base = pinned_base(2025)                                       # the edit job's input (its own release)
    code = _PROBE.format(root=ROOT, edit=EDIT_TEXT, prompt=WALLS_PROMPT)
    proc = subprocess.run([sys.executable, "-c", code, order, base, str(tmp_path)],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE ")]
    assert proc.returncode == 0 and len(lines) == 1, (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:])
    got = json.loads(lines[0][len("PROBE "):])
    assert got["oks"] == [True, True], got
    assert got["names"] == ["rvt_job"], got                        # was ['_frontdoor_rvt_job', 'rvt_job']
    assert got["loader_is_rvt_job"] is True, got                   # ... and edit._JOB is that one object
