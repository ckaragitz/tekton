"""#209 -- an exception AFTER the build still yields the ONE ``--json`` result naming the delivered file.

Hard rule 1 from the stranger's side: when anything late in a route throws (an encoding error writing
``MANIFEST.md`` on a non-UTF-8 locale, #29; a full disk; a read-only subdirectory), ``rvt.frontdoor.run()``
used to leave by traceback -- ``tools/frontdoor.py`` returned 1 with no JSON, the plugin's ``go`` reported
``result: null``, and the skill told its user the job failed while ``prompt_room.rvt`` and its families
sat in ``--out``.  ``run()`` now hands the route a result object it owns, so whatever the route recorded
before dying (files as the build named them, intent, handoff, manifest, errors) comes back as an honest
``FAILED (post-build error: ...)`` document; refused requests keep their one line.

Fresh-clone safe: the one real build uses the bundled certified 2026 pin (a clean skip when it is absent);
every other row stubs the route.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import rvt.frontdoor as FD                    # noqa: E402
from rvt.frontdoor import base as B           # noqa: E402
from rvt.frontdoor import manifest as MF      # noqa: E402
from rvt.frontdoor import router as R         # noqa: E402
from conftest import pinned_base              # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")   # a route that dies mid-way must not leave a release entered

PROMPT = "an electrical room with 2 panels"
ASCII_CRASH = ("UnicodeEncodeError: 'ascii' codec can't encode character '\\u2014' in position 0: "
               "ordinal not in range(128)")


def _ascii_locale_crash(*_a, **_k):
    """What ``manifest.write_manifest`` did under a forced-ASCII locale (#29): the .rvt was already on disk."""
    raise UnicodeEncodeError("ascii", "—", 0, 1, "ordinal not in range(128)")


def _dies_after_recording(files, note=None, exc=_ascii_locale_crash):
    """A route stub: record ``files`` (as ``build_intent`` names them) and an optional earlier error note on the
    result it was handed, write the bytes, then die -- the post-build failure shape without paying for a build."""
    def route(req, out_dir, res):
        for role, p in files(out_dir).items():
            if role.endswith("_dir"):
                os.makedirs(p, exist_ok=True)
            else:
                with open(p, "wb") as fh:
                    fh.write(b"built bytes")
            res.files[role] = p
        if note:
            res.errors.append(note)
        exc() if callable(exc) and not isinstance(exc, BaseException) else _raise(exc)
    return route


def _raise(exc):
    raise exc


# --------------------------------------------------------------------------- the real thing, once

def test_a_late_exception_hands_back_the_built_file_with_its_stamps(tmp_path, monkeypatch):
    pinned_base(2026)
    monkeypatch.setattr(MF, "write_manifest", _ascii_locale_crash)
    out = tmp_path / "job"
    r = FD.author(prompt=PROMPT, out=str(out), no_handoff=True)

    assert r.ok is False
    assert r.status == f"FAILED (post-build error: {ASCII_CRASH}; delivered anyway: prompt_room.rvt, families/)"
    assert r.files["combined"] == str(out / "prompt_room.rvt") and os.path.isfile(r.files["combined"])
    assert os.path.isdir(r.files["families_dir"]) and os.listdir(r.files["families_dir"])
    assert set(r.files) == {"combined", "families_dir"}          # exactly what build_intent named -- nothing re-guessed
    assert r.intent_json == str(out / "intent.json") and os.path.isfile(r.intent_json)
    assert r.route == "prompt" and r.out_dir == str(out) and r.seconds >= 0
    assert r.errors[-2] == f"prompt route raised {ASCII_CRASH}"
    assert r.errors[-1].startswith("Traceback (most recent call last):") and "write_manifest" in r.errors[-1]
    doc = r.as_json()
    assert doc["manifest"] == {}                                     # no manifest PATHS: none was written ...
    assert doc["stamps"] and doc["release"]                          # ... but the manifest the route had built still
    json.dumps(doc)                                                  # yields the stamps + release story, and it dumps


# --------------------------------------------------------------------------- the mechanism, without builds

def test_an_exception_before_the_build_says_nothing_was_built_and_never_names_a_stale_file(tmp_path, monkeypatch):
    """Only what THIS route recorded is ever named: a ``prompt_room.rvt`` an earlier job left in a reused ``--out``
    is not this prompt's output."""
    out = tmp_path / "reused"
    out.mkdir()
    stale = out / "prompt_room.rvt"
    stale.write_bytes(b"an earlier job's bytes")
    os.utime(stale, (time.time() - 3600,) * 2)

    def boom(req):
        raise RuntimeError("boom")
    monkeypatch.setattr(FD, "_resolve_base_and_version", boom)   # dies after the parse, before any build
    r = FD.author(prompt=PROMPT, out=str(out), no_handoff=True)

    assert r.ok is False and r.files == {}
    assert r.status == "FAILED (RuntimeError: boom; nothing was built)"
    assert r.intent_json == str(out / "intent.json")              # the parse DID record it before the crash
    assert r.errors[0] == "prompt route raised RuntimeError: boom" and "in boom" in r.errors[1] and len(r.errors) == 2
    assert stale.read_bytes() == b"an earlier job's bytes"


def test_the_verdict_is_overwritten_and_everything_recorded_before_the_crash_survives(tmp_path, monkeypatch):
    note = "target 2023 is not certified yet: built on the 2026 base instead (say so to the recipient)"
    monkeypatch.setattr(FD, "_route_prompt", _dies_after_recording(
        lambda d: {"combined": os.path.join(d, "prompt_room.rvt"), "families_dir": os.path.join(d, "families")},
        note=note, exc=OSError(28, "No space left on device")))
    r = FD.author(prompt=PROMPT, out=str(tmp_path / "full"))

    assert r.status == ("FAILED (post-build error: OSError: [Errno 28] No space left on device; "
                        "delivered anyway: prompt_room.rvt, families/)")
    assert r.files == {"combined": str(tmp_path / "full" / "prompt_room.rvt"),
                       "families_dir": str(tmp_path / "full" / "families")}
    assert r.errors[0] == note and r.errors[1] == "prompt route raised OSError: [Errno 28] No space left on device"
    assert r.errors[2].startswith("Traceback (most recent call last):") and len(r.errors) == 3
    assert r.ok is False and r.intent_json is None and r.as_json()["files"] == r.files


def test_the_rvt_route_names_its_edited_file_as_the_edit_wrote_it(tmp_path, monkeypatch):
    """``edit.run_edit`` names ``<input basename>.edited.rvt`` from the RAW basename (spaces kept); the salvage
    repeats what the route recorded, so no second, sanitised guess (``Office_Tower…``) can miss the file."""
    src = tmp_path / "Office Tower.rvt"
    src.write_bytes(b"the user's project")
    monkeypatch.setattr(FD, "_route_rvt", _dies_after_recording(
        lambda d: {"edited": os.path.join(d, "Office Tower.edited.rvt")}))
    r = FD.author(rvt=str(src), edit="move DP-1 to 3,1,4.66", out=str(tmp_path / "e"))

    assert r.route == "rvt" and r.files == {"edited": str(tmp_path / "e" / "Office Tower.edited.rvt")}
    assert r.status == f"FAILED (post-build error: {ASCII_CRASH}; delivered anyway: Office Tower.edited.rvt)"


@pytest.mark.parametrize("exc", [FD.FrontDoorError("a refused request"), B.BaseError("a refused base")])
def test_refused_requests_keep_their_one_line(tmp_path, monkeypatch, exc):
    """The CLI maps these to its usage-error exit 2 with ONE line and no traceback -- unchanged by the guard
    (``InputReleaseRefused``, #176, is a ``FrontDoorError``)."""
    monkeypatch.setattr(FD, "_route_prompt", lambda req, out_dir, res: _raise(exc))
    with pytest.raises(type(exc)) as ei:
        FD.author(prompt=PROMPT, out=str(tmp_path / "r"))
    assert ei.value is exc


def test_the_router_relays_the_salvaged_result(tmp_path, monkeypatch):
    """``route run --output rvt`` composes ``author()``: the step now RETURNS (recorded ``ok: True`` -- it ran) with
    the FAILED status and the delivered file, instead of raising into a bare ``FAILED (stage failed)``."""
    monkeypatch.setattr(FD, "_route_prompt", _dies_after_recording(
        lambda d: {"combined": os.path.join(d, "prompt_room.rvt")}))
    rr = R.route({"prompt": PROMPT}, "rvt", out=str(tmp_path / "rt"), quiet=True)

    assert rr.ok is False
    assert rr.status == f"FAILED (post-build error: {ASCII_CRASH}; delivered anyway: prompt_room.rvt)"
    assert rr.files["combined"] == str(tmp_path / "rt" / "prompt_room.rvt") and os.path.isfile(rr.files["combined"])
    step = next(s for s in rr.steps if s["impl"] == "rvt.frontdoor:author")
    assert step["ok"] is True
    assert any(e == f"prompt route raised {ASCII_CRASH}" for e in rr.errors)


def test_the_cli_prints_the_json_result_and_exits_incomplete_instead_of_a_traceback(tmp_path):
    """The CLI's half of the contract, in a child interpreter running the real ``tools/frontdoor.py``: a route that
    dies after recording its .rvt yields the ONE ``--json`` document and exit 3 (INCOMPLETE) -- never exit 1, a
    traceback on stderr and no document.  (The real build's half is proven in-process above, once, so the shard does
    not pay for a second build.)"""
    out = tmp_path / "cli"
    shim = (
        "import os, runpy, sys\n"
        "import rvt.frontdoor as FD\n"
        "def build_then_die(req, out_dir, res):\n"
        "    p = os.path.join(out_dir, 'prompt_room.rvt')\n"
        "    open(p, 'wb').write(b'built bytes')\n"
        "    res.files['combined'] = p\n"
        "    raise UnicodeEncodeError('ascii', '\\u2014', 0, 1, 'ordinal not in range(128)')\n"
        "FD._route_prompt = build_then_die\n"
        f"sys.argv = ['frontdoor.py', 'author', '--prompt', {PROMPT!r}, '--out', {str(out)!r}, '--json']\n"
        f"runpy.run_path({os.path.join(ROOT, 'tools', 'frontdoor.py')!r}, run_name='__main__')\n")
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    p = subprocess.run([sys.executable, "-c", shim], capture_output=True, text=True, env=env, cwd=str(tmp_path),
                       timeout=300)
    assert p.returncode == 3, (p.returncode, p.stderr[-2000:])
    doc = json.loads(p.stdout)
    assert doc["ok"] is False and doc["route"] == "prompt"
    assert doc["status"] == f"FAILED (post-build error: {ASCII_CRASH}; delivered anyway: prompt_room.rvt)"
    assert doc["files"] == {"combined": str(out / "prompt_room.rvt")} and os.path.isfile(doc["files"]["combined"])
    assert "Traceback" not in p.stderr                              # the tail rides INSIDE the document instead
    assert doc["errors"][-1].startswith("Traceback (most recent call last):") and "build_then_die" in doc["errors"][-1]
