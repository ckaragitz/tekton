"""#208 -- ``install_schema()`` touches no filesystem, so no filesystem can fail a job through it.

Until #208 the chokepoint install ALSO materialised the installed base's ``Formats/Latest`` bytes under ONE
fixed, shared ``<tmp>/tekton-schema-cache`` (bare ``makedirs`` + ``open(..., "wb")``) and re-pointed
``rvt.schema.DEFAULT_PATH`` at the file.  Nothing on the product path ever read that file back -- every default-path
loader is answered in memory -- but the second OS account on a box (a CI runner, a shared Linux host) inherited the
first one's directory and every one of its jobs died before building anything: ``FAILED (schema install from base
failed: PermissionError ...)``, ``files: {}`` (hard rule 1; measured as user ``nobody``).  The step is retired:
``install_schema`` is now the same in-memory contract ``release_ctx`` installs for the foreign releases.

Fresh-clone safe: one install-only row, and ONE real prompt build on the native pin (clean skip without the bundle).
Run: .venv/bin/python -m pytest tests/test_install_schema_208.py -q
"""
from __future__ import annotations

import builtins
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import rvt.frontdoor as FD                          # noqa: E402
from rvt import adocument, encode, objects, schema  # noqa: E402
from rvt.frontdoor import standalone as SA          # noqa: E402
from rvt.versions import LATEST_RELEASE             # noqa: E402
from conftest import pinned_base                    # noqa: E402


@pytest.fixture
def reinstall(monkeypatch):
    """A full (re)install of the schema chokepoints inside the test, everything put back at teardown -- the shape
    ``test_frontdoor_standalone`` uses: the rebound loaders, ``DEFAULT_PATH``, the codec singletons, the state."""
    for mod in (schema, objects, encode, adocument):
        monkeypatch.setattr(mod, "load_schema", mod.load_schema)
    monkeypatch.setattr(schema, "DEFAULT_PATH", schema.DEFAULT_PATH)
    monkeypatch.setattr(encode, "_DEFAULT_ENCODER", encode._DEFAULT_ENCODER)
    monkeypatch.setattr(adocument, "_DECODER", adocument._DECODER)
    monkeypatch.setattr(SA, "_SCHEMA_STATE", {})


def test_install_writes_nothing_creates_nothing_and_needs_no_temp_dir(reinstall, monkeypatch):
    """Every write primitive is booby-trapped for the duration of the install: a directory made, a temp dir asked
    for, a file opened for writing would raise straight through it.  It completes, ``DEFAULT_PATH`` is untouched,
    and the whole default-path family answers with the installed schema object -- in memory."""
    def denied(*a, **k):
        raise PermissionError(13, "the #208 trap: install_schema must not write", str(a[:1]))
    real_open = builtins.open

    def read_only_open(file, mode="r", *a, **k):
        if set(mode) & set("wax+"):
            denied(file)
        return real_open(file, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", read_only_open)
    monkeypatch.setattr(os, "makedirs", denied)
    monkeypatch.setattr(os, "mkdir", denied)
    monkeypatch.setattr(tempfile, "gettempdir", denied)
    monkeypatch.setattr(tempfile, "mkstemp", denied)
    default_before = schema.DEFAULT_PATH

    rep = SA.install_schema()

    assert schema.DEFAULT_PATH == default_before
    assert rep["installed"][0] == ("rvt.schema.load_schema default path -> installed schema, in memory "
                                   "(DEFAULT_PATH untouched)")
    assert "blob" not in SA._SCHEMA_STATE                    # the 500 KB stream is not retained either
    s = SA.bundled_schema()
    assert rep["schema_sha256"] == s.sha256 and rep["schema_bytes"] > 400_000
    assert objects.load_schema() is s and encode.load_schema() is s and adocument.load_schema() is s
    assert schema.load_schema() is s and schema.load_schema(None) is s and schema.load_schema(default_before) is s
    assert schema.schema_available() is True
    assert SA.install_schema()["installed"] == ["(already installed)"]


def test_a_prompt_build_delivers_on_the_in_memory_install(reinstall, tmp_path):
    """The issue's DONE row, whole: a fresh install and then a real prompt build that writes the combined ``.rvt``
    -- what user ``nobody`` could not get past on a box whose ``/tmp/tekton-schema-cache`` belonged to root."""
    pinned_base(LATEST_RELEASE)
    default_before = schema.DEFAULT_PATH
    SA.install_schema()
    r = FD.author(prompt="an electrical room with 2 panels", out=str(tmp_path / "job"), no_handoff=True)
    assert r.ok is True, (r.status, r.errors)
    assert os.path.isfile(r.files["combined"])
    assert schema.DEFAULT_PATH == default_before
