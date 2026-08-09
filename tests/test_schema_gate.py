"""The ONE schema-availability gate (issue #298).

``rvt.schema.schema_available()`` is the engine-owned answer to "can a class
schema be loaded here?" (research corpus blob, else the sha-pinned bundled
genesis base ``load_schema`` falls back to) and ``tests/conftest.py`` builds
the suite's single ``HAVE_SCHEMA`` / ``needs_schema`` on it.  The ungated
SENTINEL is the point: whenever ``plugin/assets/genesis/G_ABPD.rvt`` is in the
tree the gate is open AND the schema really parses, so a regression in the
fallback fails CI loudly instead of turning every ``needs_schema`` test back
into a skip (the failure mode #161 existed to kill).  All fresh-clone.
"""
from __future__ import annotations

import os

import pytest

from conftest import HAVE_SCHEMA, ROOT, needs_schema
from rvt import schema as S
from rvt.frontdoor import standalone as ST

BUNDLED_BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")

#: the engine's own ``load_schema``, bound at collection time -- i.e. before
#: any test in the run can call ``standalone.install_schema()``, which swaps
#: ``rvt.schema.load_schema`` (and re-points ``DEFAULT_PATH``) for the rest
#: of the process.  The fallback rule under test lives in the real function,
#: called with the live ``S.DEFAULT_PATH``.
LOAD_SCHEMA = S.load_schema


def test_sentinel_bundled_base_in_tree_means_schema_loads():
    if not os.path.isfile(BUNDLED_BASE):
        pytest.skip("plugin/assets/genesis/G_ABPD.rvt not in this tree")
    assert S.schema_available() is True
    assert HAVE_SCHEMA is True
    try:
        schema = LOAD_SCHEMA(S.DEFAULT_PATH)
    except FileNotFoundError as exc:   # a hard FAIL, never conftest's research-input skip
        pytest.fail(f"bundled base present but load_schema() found no source: {exc}")
    assert len(schema.classes) > 4000 and schema.by_name["ADocument"]
    assert schema.sha256 == S.EXPECTED_SHA256


def test_gate_has_no_side_effects(monkeypatch):
    monkeypatch.setattr(S, "_MEMO", {})
    assert S.schema_available() is HAVE_SCHEMA
    assert S._MEMO == {}


def test_no_corpus_no_bundle_closes_the_gate_and_names_the_path(monkeypatch, tmp_path):
    missing = str(tmp_path / "extracted" / "Formats__Latest.gz" / "000.bin")
    monkeypatch.setattr(S, "DEFAULT_PATH", missing)

    def _absent(*_a, **_k):
        raise ST.StandaloneError("no bundled base anywhere")

    monkeypatch.setattr(ST, "bundled_base_path", _absent)
    assert S.schema_available() is False
    with pytest.raises(FileNotFoundError) as ei:
        LOAD_SCHEMA(S.DEFAULT_PATH)
    assert ei.value.filename == missing


@needs_schema
def test_a_broken_bundled_fallback_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "DEFAULT_PATH", str(tmp_path / "nope.bin"))
    monkeypatch.setattr(ST, "bundled_base_path", lambda *a, **k: BUNDLED_BASE)

    def _corrupt(*_a, **_k):
        raise S.ParseError(0, "simulated corrupt Formats/Latest")

    monkeypatch.setattr(ST, "bundled_schema", _corrupt)
    assert S.schema_available() is True          # the file exists ...
    with pytest.raises(S.ParseError):            # ... so its failure surfaces
        LOAD_SCHEMA(S.DEFAULT_PATH)
