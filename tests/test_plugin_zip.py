"""Guard: tekton-plugin.zip is built with the stdlib, and built the same way twice.

`rebuild_zip()` used to shell out to the Unix `zip` binary, which does not exist
on Windows — and it ran AFTER plugin/ had been rewritten, so the failure left a
half-synced tree. See issue #37.

These tests build into tmp_path rather than the repo-root artifact, so they never
race another session's `tools/sync_plugin.py`.
"""
import hashlib
import importlib
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sync_plugin():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        mod = importlib.import_module("sync_plugin")
        return importlib.reload(mod)
    finally:
        sys.path.pop(0)


def _sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def test_zip_members_are_sorted_unique_and_posix():
    members = _sync_plugin().zip_members()
    arcs = [a for _p, a in members]
    assert arcs, "no members selected"
    assert arcs == sorted(arcs), "archive entries must be sorted"
    assert len(arcs) == len(set(arcs)), "duplicate archive entries"
    assert not any("\\" in a for a in arcs), "archive names must use / separators"


def test_zip_members_exclusions():
    arcs = [a for _p, a in _sync_plugin().zip_members()]
    assert not [a for a in arcs if "__pycache__" in a]
    assert not [a for a in arcs if "node_modules" in a]
    assert not [a for a in arcs if a.endswith(".DS_Store")]
    # proof .rvt outputs stay out; the certified genesis bases under assets/ ship
    stray = [a for a in arcs if a.lower().endswith(".rvt") and not a.startswith("assets/")]
    assert not stray, f"non-asset .rvt bundled: {stray}"
    assert "assets/genesis/G_ABPD.rvt" in arcs
    # plugin contents sit at the archive ROOT, not under a plugin/ prefix
    assert ".claude-plugin/plugin.json" in arcs


def test_rebuild_zip_is_deterministic(tmp_path, monkeypatch):
    sp = _sync_plugin()
    out = []
    for name in ("one.zip", "two.zip"):
        target = str(tmp_path / name)
        monkeypatch.setattr(sp, "ZIP", target)
        size = sp.rebuild_zip()
        assert size == os.path.getsize(target) > 0
        out.append(_sha256(target))
    assert out[0] == out[1], "two consecutive builds differ"


def test_rebuilt_zip_opens_and_matches_members(tmp_path, monkeypatch):
    sp = _sync_plugin()
    target = str(tmp_path / "p.zip")
    monkeypatch.setattr(sp, "ZIP", target)
    sp.rebuild_zip()
    with zipfile.ZipFile(target) as zf:
        assert zf.testzip() is None, "corrupt archive"
        assert zf.namelist() == [a for _p, a in sp.zip_members()]
