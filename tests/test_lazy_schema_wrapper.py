"""The plugin's lazy schema install (``plugin/skills/_shared/
tekton_schema.py``) keeps the one chokepoint contract of
``standalone.default_schema_loader`` (issue #376): armed over a default
path that already resolves it wraps nothing; armed on a bare machine the
default-path family installs once and answers with the installed schema,
any other path is parsed verbatim and a missing one raises
``FileNotFoundError``.  Before #376, arming it AFTER a completed
``install_schema()`` made ``None`` and every missing explicit path recurse
into the wrapper until ``RecursionError``, reported as the false "the plugin
bundle is incomplete".

Fresh-clone safe and in-process (the only schema bytes are the pinned plugin
base's own); every swapped name is monkeypatch-restored so neighbours in the
shard see the process exactly as they would without this file.
"""
from __future__ import annotations

import os

import pytest

from rvt import adocument, encode, objects, schema
from rvt.container import open_rvt
from rvt.frontdoor import standalone as SA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(ROOT, "plugin", "skills", "_shared")


@pytest.fixture
def lazy(monkeypatch):
    """The real ``tekton_schema`` module, disarmed, over a process whose
    chokepoint state is a clean slate and is fully restored afterwards."""
    for mod in (schema, objects, encode, adocument):
        monkeypatch.setattr(mod, "load_schema", mod.load_schema)
    monkeypatch.setattr(schema, "DEFAULT_PATH", schema.DEFAULT_PATH)
    monkeypatch.delattr(schema, "_tekton_lazy_bundled_schema", raising=False)
    monkeypatch.setattr(SA, "_SCHEMA_STATE", {})          # a full (re)install
    monkeypatch.syspath_prepend(SHARED)
    import tekton_schema
    return tekton_schema


def test_armed_after_a_completed_install(lazy, tmp_path, monkeypatch):
    # a bare machine, deterministically (a corpus machine would answer "corpus-present" first)
    monkeypatch.setattr(schema, "DEFAULT_PATH", str(tmp_path / "absent" / "000.bin"))
    SA.install_schema()
    installed, loader = SA.bundled_schema(), schema.load_schema
    # the host installed already (in memory, DEFAULT_PATH untouched: #208): nothing is wrapped
    assert lazy.install() == "host-installed"
    assert schema.load_schema is loader and objects.load_schema is loader
    # the default-path family answers with the installed object ...
    assert schema.load_schema() is installed
    assert objects.load_schema(None) is installed
    assert adocument.load_schema(schema.DEFAULT_PATH) is installed
    # ... a missing explicit path raises, naming it -- no RecursionError ...
    missing = str(tmp_path / "typo" / "Formats_Latest_2025.bin")
    for load in (schema.load_schema, objects.load_schema, encode.load_schema):
        with pytest.raises(FileNotFoundError) as ei:
            load(missing)
        assert ei.value.filename == missing and ei.value.__cause__ is None
    # ... and an existing explicit path is that file, parsed verbatim
    copy = tmp_path / "Formats_Latest_copy.bin"
    with open_rvt(SA.bundled_base_path()) as f:          # the installed base's own stream, verbatim
        copy.write_bytes(f.inflate("Formats/Latest", 0))
    assert schema.load_schema(str(copy)).sha256 == installed.sha256
    assert lazy.install() == "already"


def test_explicit_path_never_activates_the_fallback(lazy, tmp_path, monkeypatch):
    # a bare machine, deterministically: the default path does not exist
    monkeypatch.setattr(schema, "DEFAULT_PATH", str(tmp_path / "absent" / "000.bin"))
    assert lazy.install() == "installed"
    wrapper = schema.load_schema
    with pytest.raises(FileNotFoundError) as ei:
        wrapper(str(tmp_path / "no" / "such" / "schema.bin"))
    assert ei.value.filename.endswith("schema.bin")
    assert not SA._SCHEMA_STATE.get("installed")         # nothing was activated
    assert schema.load_schema is wrapper
    # the first default-path need activates install_schema() once ...
    s = objects.ObjectDecoder().schema
    assert SA._SCHEMA_STATE.get("installed") and s is SA.bundled_schema()
    # ... which re-points every chokepoint past the wrapper; a held reference
    # still answers with the same object and still raises for a missing path
    assert schema.load_schema is not wrapper and objects.load_schema is not wrapper
    assert wrapper() is s and wrapper(None) is s and wrapper(schema.DEFAULT_PATH) is s
    with pytest.raises(FileNotFoundError):
        wrapper(str(tmp_path / "still" / "missing.bin"))
    assert lazy.install() == "already"
