"""#210 -- the bare `go` surface under a forced-ASCII locale: the Linux CI gate for #29.

#29 (open) is the Windows class of crash: text I/O without ``encoding=`` writes in the
locale codepage (cp1252) and dies on the first character it cannot represent -- and the
front door's own MANIFEST.md carries ``—``, ``“…”`` and ``→``.  Nobody can see that on an
ubuntu shard ... unless the locale is made *stricter* than Windows: with locale coercion
(PEP 538) and UTF-8 mode (PEP 540) both switched off under ``LC_ALL=C``, CPython's preferred
encoding is pure ASCII (measured: ``ANSI_X3.4-1968``), so every encoding-less text write of
a non-ASCII character fails exactly the way cp1252 fails on ``→``.  ``-I`` ignores
``PYTHONUTF8``, hence the explicit ``-X utf8=0``; ``PYTHONCOERCECLOCALE`` is honoured even
under ``-I`` (it is read before the environment is ignored) -- both measured, see the record.

Three tests, three different contracts:

* ``test_preflight_is_ready_under_ascii_locale`` -- passes today: preflight answers READY as
  one JSON document on an ASCII stdout.
* ``test_go_author_delivers_cleanly_under_ascii_locale`` -- THE GATE.  An ASCII prompt into
  a spaced ``--out``: the build must complete (exit 0/4, never 3), MANIFEST.md / manifest.json
  must be real UTF-8 files, and no ``Unicode*Error`` may ride in ``result.errors`` (today two
  do: the manifest WRITE of ``—`` and the handoff package's encoding-less READ).  It is
  ``xfail(strict=True)`` until #29's stage 1 lands; that PR deletes the marker -- if it does
  not, this test XPASSes and turns the shard red on purpose, which is the reminder.
* ``test_non_ascii_prompt_keeps_the_one_json_contract`` -- passes today and must keep
  passing: under a TRUE ASCII locale a non-ASCII prompt/``--out`` reaches the child
  surrogate-escaped (undecodable by construction -- unlike Windows, whose argv is UTF-16),
  so this is deliberately NOT part of #29's flip condition; what it pins is hard rule 1 on
  the nastiest surface: exactly one pure-ASCII JSON document, the job's exit code, no
  wrapper exception, and the ``.rvt`` on disk whenever the build got that far (#209).

Bare surface = a copy of ``plugin/`` driven by ``sys.executable -I -S`` (no site-packages,
no repo on the path), the fixtures ``test_coldstart`` already builds; ~2 prompt builds.
Record: docs/inbox/locale-gate.md.
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from test_coldstart import BARE_PY, _bootstrap, plugin_copy, workdir  # noqa: F401 (fixtures)

# locale coercion off + UTF-8 mode off + the C locale = an ASCII preferred encoding
ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
ASCII_PY = BARE_PY + ["-X", "utf8=0"]          # -I ignores PYTHONUTF8; the -X flag does not

ASCII_PROMPT = "an electrical room 5x4 m with 2 panels"
GERMAN_PROMPT = "Elektroraum – Größe 5×4 m with 2 panels"   # – ö ß ×

EX_DELIVERED = (0, 4)      # tools/frontdoor.py: 0 completed (PROOF-ONLY too), 4 self-checks
                           # failed but delivered; 3 = the build/manifest did NOT complete


def _run_ascii(args, cwd, timeout=600):
    """The child gets this process's environment minus RVT_*/PYTHONPATH (as test_coldstart
    does) plus the forced-ASCII locale; stdout/stderr come back as BYTES on purpose."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    env.update(ASCII_LOCALE)
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=timeout)


@pytest.fixture(scope="module")
def ascii_locale(workdir):
    """Skip the module's locale tests unless this interpreter really CAN be forced to an
    ASCII preferred encoding (glibc: yes; a libc that pins UTF-8, or Windows' cp1252: no --
    the reason line says what it measured)."""
    probe = ("import codecs, locale, sys; "
             "print(codecs.lookup(locale.getpreferredencoding(False)).name, "
             "sys.getfilesystemencoding(), sys.flags.utf8_mode)")
    r = _run_ascii(ASCII_PY + ["-c", probe], cwd=workdir, timeout=60)
    got = r.stdout.decode("ascii", "replace").split()
    if r.returncode != 0 or not got or got[0] != "ascii":
        pytest.skip(f"cannot force an ASCII locale on this interpreter (probe said {got!r}, "
                    f"exit {r.returncode})")
    return got


def _one_json(stdout: bytes) -> dict:
    assert stdout, "empty stdout: the one-JSON contract is broken"
    assert max(stdout) < 128, "stdout carries raw non-ASCII bytes -- an ASCII console would " \
                             "have raised instead of printing the document"
    return json.loads(stdout)


def test_preflight_is_ready_under_ascii_locale(plugin_copy, workdir, ascii_locale):
    r = _run_ascii(ASCII_PY + [_bootstrap(plugin_copy), "--json"], cwd=workdir, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    pf = _one_json(r.stdout)
    assert pf["ok"] is True and pf["line"].startswith("tekton: READY"), pf["line"]


@pytest.mark.xfail(strict=True, reason="#29 stage 1 not merged: MANIFEST.md is written and "
                   "the handoff notes are read without encoding= (remove this marker in the "
                   "PR that fixes it -- an XPASS here is that reminder)")
def test_go_author_delivers_cleanly_under_ascii_locale(plugin_copy, workdir, ascii_locale):
    out = os.path.join(workdir, "job 1 (ascii locale)")          # spaces + parens, on purpose
    r = _run_ascii(ASCII_PY + [_bootstrap(plugin_copy), "go", "author", "--prompt",
                               ASCII_PROMPT, "--out", out, "--json"], cwd=workdir)
    doc = _one_json(r.stdout)
    g, res = doc["go"], doc["result"]
    assert "exception" not in g, g.get("exception")
    assert res is not None, g
    status, errors = res.get("status", ""), res.get("errors") or []
    # the gate proper: completed and delivered, not "FAILED (post-build error: UnicodeEncodeError…"
    assert r.returncode in EX_DELIVERED and g["exit_code"] == r.returncode, (status, errors[:2])
    assert not status.startswith("FAILED"), status
    unicode_errors = [e for e in errors if "UnicodeEncodeError" in e or "UnicodeDecodeError" in e]
    assert not unicode_errors, unicode_errors        # the handoff READ counts too
    combined = res["files"]["combined"]
    assert os.path.isfile(combined), combined
    for name in ("MANIFEST.md", "manifest.json"):
        path = os.path.join(out, name)
        with open(path, "rb") as fh:
            raw = fh.read()
        assert raw, f"{name} is empty (a write that died mid-way truncates it)"
        text = raw.decode("utf-8")                   # strict: it IS a UTF-8 file
        if name == "manifest.json":
            json.loads(text)
        else:
            assert os.path.basename(combined) in text, "MANIFEST.md does not name the delivered file"


def test_non_ascii_prompt_keeps_the_one_json_contract(plugin_copy, workdir, ascii_locale):
    out = os.path.join(workdir, "job ä 2")                   # non-ASCII dir name too
    r = _run_ascii(ASCII_PY + [_bootstrap(plugin_copy), "go", "author", "--prompt",
                               GERMAN_PROMPT, "--out", out, "--json"], cwd=workdir)
    doc = _one_json(r.stdout)
    g = doc["go"]
    assert "exception" not in g, g.get("exception")   # the wrapper never fell over
    assert g["exit_code"] == r.returncode and r.returncode in EX_DELIVERED + (3,), \
        (r.returncode, r.stderr[-1500:])
    res = doc["result"]
    assert res is not None and res.get("status"), g  # the job answered with its own document
    combined = (res.get("files") or {}).get("combined")
    if combined:                                     # built => on disk (rule 1), reachable
        assert os.path.isfile(combined), ascii(combined)   # through the surrogate-escaped path
    assert os.path.isdir(out), "the non-ASCII --out directory was not created"
