"""#210 -- the bare `go` surface under a forced-ASCII locale: the Linux CI gate for #29.

#29 (open) is the Windows class of crash: text I/O without ``encoding=`` writes in the locale
codepage and dies on the first character it cannot represent (cp1252 dies on the ``→`` the front
door's own MANIFEST.md carries).  An ubuntu shard can be made *stricter* than that: with
``LC_ALL=C`` set, PEP 538 locale coercion never runs, and ``-X utf8=0`` keeps PEP 540 UTF-8
mode off (``-I`` ignores the ``PYTHONUTF8``/``PYTHONCOERCECLOCALE`` spellings), so CPython's
preferred encoding is pure ASCII (glibc: ``ANSI_X3.4-1968``) and EVERY encoding-less write of a
non-ASCII character fails -- ``—``, ``“…”``, ``→`` alike.  The autouse probe below measures that
in the child before anything is asserted.

Bare surface = a copy of ``plugin/`` driven by ``sys.executable -I -S`` (no site-packages, no repo
on the path) -- the fixtures ``test_coldstart`` already builds; cost ~2 prompt builds.
Record (before/after numbers, the five live sites, proof the gate flips): docs/inbox/locale-gate.md.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess

import pytest

from test_coldstart import BARE_PY, _bootstrap, plugin_copy, workdir  # noqa: F401 (fixtures)

ASCII_PY = BARE_PY + ["-X", "utf8=0"]
EX_DELIVERED = (0, 4)      # tools/frontdoor.py: 0 completed (PROOF-ONLY too), 4 self-checks failed
                           # but delivered; 3 = the build/manifest did NOT complete; 1 = crashed


def _run_ascii(args, cwd):
    """This process's environment minus RVT_*/PYTHONPATH (as test_coldstart does) plus the one
    load-bearing knob, LC_ALL=C; stdout/stderr come back as BYTES on purpose."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("RVT_") and k != "PYTHONPATH"}
    env["LC_ALL"] = "C"
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=180)


@pytest.fixture(scope="module", autouse=True)
def ascii_locale(workdir):
    """Every test here needs a child that REALLY has an ASCII preferred encoding.  On glibc (the
    CI reference platform, where this is measured to work) anything else is news and fails loudly;
    elsewhere (a libc that pins UTF-8, Windows' cp1252 -- #122 covers Windows for real) it skips."""
    probe = "import codecs, locale; print(codecs.lookup(locale.getpreferredencoding(False)).name)"
    r = _run_ascii(ASCII_PY + ["-c", probe], cwd=workdir)
    if r.stdout.strip() != b"ascii":
        verdict = pytest.fail if platform.libc_ver()[0] == "glibc" else pytest.skip
        verdict(f"cannot force an ASCII locale on this interpreter (probe said {r.stdout!r}, "
                f"exit {r.returncode})")


def _one_json(stdout: bytes) -> dict:
    assert stdout.isascii(), "stdout carries raw non-ASCII bytes -- an ASCII console would have " \
                             "raised instead of printing the document"
    return json.loads(stdout)


def _go_author(plugin_copy, workdir, prompt, out):
    r = _run_ascii(ASCII_PY + [_bootstrap(plugin_copy), "go", "author",
                               "--prompt", prompt, "--out", out, "--json"], cwd=workdir)
    doc = _one_json(r.stdout)
    assert doc["go"]["exit_code"] == r.returncode, (doc["go"], r.stderr[-1500:])
    assert doc["result"] is not None, doc["go"]          # the job answered with its own document
    return r.returncode, doc["result"]


def test_preflight_is_ready_under_ascii_locale(plugin_copy, workdir):
    r = _run_ascii(ASCII_PY + [_bootstrap(plugin_copy), "--json"], cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    pf = _one_json(r.stdout)
    assert pf["ok"] is True and pf["line"].startswith("tekton: READY"), pf["line"]


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="#29 open: the MANIFEST.md write and the handoff-notes read lack "
                          "encoding= -- delete this marker in the PR that fixes #29")
def test_go_author_delivers_cleanly_under_ascii_locale(plugin_copy, workdir):
    out = os.path.join(workdir, "job 1 (ascii locale)")             # spaces + parens, on purpose
    code, res = _go_author(plugin_copy, workdir, "an electrical room 5x4 m with 2 panels", out)
    assert code in EX_DELIVERED, (res.get("status"), (res.get("errors") or [])[:2])
    unicode_errors = [e for e in res.get("errors") or [] if "Unicode" in e]
    assert not unicode_errors, unicode_errors            # the handoff READ counts too
    combined = res["files"]["combined"]
    assert os.path.isfile(combined), combined
    with open(os.path.join(out, "MANIFEST.md"), encoding="utf-8") as fh:  # strict: it IS UTF-8
        assert os.path.basename(combined) in fh.read(), "MANIFEST.md does not name the delivered file"
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as fh:
        json.load(fh)


def test_non_ascii_prompt_keeps_the_one_json_contract(plugin_copy, workdir):
    """Deliberately NOT #29's flip condition: under a true ASCII locale a non-ASCII prompt or
    --out reaches the child surrogate-escaped (undecodable by construction -- Windows argv is
    UTF-16 and never sees this), so no strict codec can ever write it back.  What must hold
    anyway: one pure-ASCII JSON document, the job's own exit code, and the .rvt on disk (rule 1,
    #209) -- reachable through the surrogate-escaped path the document reports."""
    out = os.path.join(workdir, "job ä 2")
    code, res = _go_author(plugin_copy, workdir, "Elektroraum – Größe 5×4 m with 2 panels", out)
    assert code in EX_DELIVERED + (3,), (code, res.get("status"))
    assert os.path.isfile(res["files"]["combined"]), ascii(res.get("files"))
