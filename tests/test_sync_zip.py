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
# this tree (measured against Info-ZIP 3.0), minus its one quirk: a
# `__pycache__`/`node_modules` at the plugin ROOT slipped past `*/x/*`; the
# stdlib build prunes them at any depth.
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
}
EMPTY_DIRS = ("emptydir",)
EXPECTED = [
    ".claude-plugin/", ".claude-plugin/plugin.json", "README.md",
    "assets/", "assets/genesis/", "assets/genesis/G.compose.json", "assets/genesis/G.rvt",
    "assets/genesis/deep/", "assets/genesis/deep/H.RVT",
    "emptydir/",
    "examples/", "examples/job/", "examples/job/spec.json", "examples/onlyproofs/",
    "lib/", "lib/src/", "lib/src/rvt/", "lib/src/rvt/mod.py",
    "skills/", "skills/a/", "skills/a/scripts/", "skills/a/scripts/t.py",
]


def _make_tree(root):
    for rel, text in TREE.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for d in EMPTY_DIRS:
        (root / d).mkdir()
    (root / "skills" / "a" / "scripts" / "t.py").chmod(0o755)   # modes are normalised away


def test_zip_entries_keep_the_cli_rules(tmp_path):
    sp = _sync_plugin()
    root = tmp_path / "plugin"
    _make_tree(root)
    entries = sp.zip_entries(str(root))
    assert [arc for arc, _ in entries] == EXPECTED
    for arc, path in entries:
        assert (path is None) == arc.endswith("/"), arc
        assert not arc.startswith(("./", "/")) and "\\" not in arc, arc


def test_write_zip_is_deterministic_and_rooted(tmp_path):
    sp = _sync_plugin()
    root = tmp_path / "plugin"
    _make_tree(root)
    z1, z2 = tmp_path / "one.zip", tmp_path / "two.zip"
    size = sp.write_zip(str(z1), str(root))
    os.utime(root / "README.md", (0, 0))                # mtimes never reach the archive
    sp.write_zip(str(z2), str(root))
    assert size == z1.stat().st_size and z1.read_bytes() == z2.read_bytes()
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
    for base in ("G_ABPD.rvt", "G_ABPD_2025.rvt", "G_ABPD_2024.rvt"):
        assert f"assets/genesis/{base}" in names, base
    for arc in names:
        parts = arc.rstrip("/").split("/")
        assert not set(parts) & (sp.ZIP_SKIP_DIRS | {".DS_Store"}), arc
        assert not (arc.lower().endswith(".rvt") and not arc.startswith("assets/")), arc
