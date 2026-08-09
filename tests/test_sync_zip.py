"""tools/sync_plugin.py builds tekton-plugin.zip with the stdlib (issue #37):
plugin contents at the archive root, the CLI-era exclusions kept, the certified
genesis bases under assets/ kept, and a byte-identical artifact on every run.

Hermetic: zips a small temp tree, never the whole plugin build. The one
real-tree case only lists plugin/ (tracked in git), it writes nothing.
"""
import importlib
import os
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")


def _sync_plugin():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        return importlib.reload(importlib.import_module("sync_plugin"))
    finally:
        sys.path.pop(0)


# what `zip -qr Z . -x '*/node_modules/*' -x '*/__pycache__/*' -x '*.rvt'
# -x '*.DS_Store' -x .DS_Store && zip -qr Z assets -x '*.DS_Store'` kept from
# this tree (measured against Info-ZIP 3.0), minus two deliberate tightenings:
# junk dirs are pruned at ANY depth (a `__pycache__` at the plugin root slipped
# past `*/x/*`) and `.pytest_cache` is junk too (SKIP_DIR_NAMES, the set the
# deny/identity audits prune with -- the zip never carries an unaudited file).
TREE = {
    ".claude-plugin/plugin.json": "{}",
    "README.md": "x",
    ".DS_Store": "junk",
    "__pycache__/top.pyc": "junk",
    "assets/.DS_Store": "junk",
    "assets/genesis/G.rvt": "base",
    "assets/genesis/G.compose.json": "{}",
    "assets/genesis/deep/H.RVT": "base",
    "examples/job/proof.rvt": "proof",
    "examples/job/spec.json": "{}",
    "examples/onlyproofs/big.rvt": "proof",
    "lib/src/rvt/mod.py": "x",
    "lib/src/rvt/__pycache__/mod.cpython-311.pyc": "junk",
    "lib/node_modules/pkg/index.js": "junk",
    "skills/a/scripts/t.py": "x",
    "skills/a/.DS_Store": "junk",
    "skills/a/tests/.pytest_cache/README.md": "junk",
}
EXPECTED = [
    ".claude-plugin/", ".claude-plugin/plugin.json", "README.md",
    "assets/", "assets/genesis/", "assets/genesis/G.compose.json", "assets/genesis/G.rvt",
    "assets/genesis/deep/", "assets/genesis/deep/H.RVT",
    "emptydir/",
    "examples/", "examples/job/", "examples/job/spec.json", "examples/onlyproofs/",
    "lib/", "lib/src/", "lib/src/rvt/", "lib/src/rvt/mod.py",
    "skills/", "skills/a/", "skills/a/scripts/", "skills/a/scripts/t.py", "skills/a/tests/",
]


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "plugin"
    for rel, text in TREE.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    (root / "emptydir").mkdir()
    (root / "skills" / "a" / "scripts" / "t.py").chmod(0o755)   # modes are normalised away
    return root


def test_zip_entries_keep_the_cli_rules(tree):
    entries = _sync_plugin().zip_entries(str(tree))
    assert [arc for arc, _ in entries] == EXPECTED
    for arc, path in entries:
        assert (path is None) == arc.endswith("/"), arc


def test_write_zip_is_deterministic_and_rooted(tree, tmp_path):
    sp = _sync_plugin()
    z1, z2 = tmp_path / "one.zip", tmp_path / "two.zip"
    sp.write_zip(str(z1), str(tree))
    os.utime(tree / "README.md", (0, 0))                # mtimes never reach the archive
    sp.write_zip(str(z2), str(tree))
    assert z1.read_bytes() == z2.read_bytes()
    with zipfile.ZipFile(z1) as zf:
        assert zf.testzip() is None
        assert zf.namelist() == EXPECTED                # sorted, at the archive root
        for info in zf.infolist():
            assert info.date_time == sp.ZIP_DATE_TIME, info.filename
            assert info.create_system == 3, info.filename
            if info.is_dir():
                assert info.external_attr == sp.ZIP_DIR_ATTR, info.filename
            else:
                assert info.external_attr == sp.ZIP_FILE_ATTR, info.filename
                assert info.compress_type == zipfile.ZIP_DEFLATED, info.filename
                assert zf.read(info).decode() == TREE[info.filename], info.filename


def test_real_plugin_tree_ships_the_genesis_bases_and_no_junk():
    sp = _sync_plugin()
    names = [arc for arc, _ in sp.zip_entries(PLUGIN)]
    assert ".claude-plugin/plugin.json" in names and "skills/tekton-author/SKILL.md" in names
    bases = [dst for _, dst, required in sp.asset_mappings() if required]
    assert bases and all(b.startswith(sp.ZIP_RVT_PREFIX) and b.endswith(".rvt") for b in bases)
    for b in bases:
        assert b in names, b
    for arc in names:
        assert not set(arc.rstrip("/").split("/")) & sp.SKIP_DIR_NAMES, arc
        assert not (arc.lower().endswith(".rvt") and not arc.startswith(sp.ZIP_RVT_PREFIX)), arc
