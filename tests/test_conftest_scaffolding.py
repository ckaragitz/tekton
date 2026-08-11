"""test_conftest_scaffolding.py -- the own-release test scaffolding lives ONCE,
in ``tests/conftest.py`` (issue #579, Refs #566 / #533 / #518 / #451):

* the law, over EVERY ``tests/test_*.py``: no module binds a private
  ``_native_constants`` / ``_no_leak`` / ``_rewrite_stream`` / ``_partition_of``,
  its own ``FOREIGN_FIRST`` / ``FOREIGN`` / ``NATIVE_LAST`` axis, or a shadow of
  the conftest names at top level (an AST law, so a seventh copy cannot creep
  back anywhere) -- minus a short, shrinking ``EXEMPT`` list of files whose
  copy is not yet conftest-shaped; and the ``ADOPTERS`` keep the leak guard on;
* the hoisted helpers behave as the copies did: ``FOREIGN_FIRST`` = the
  certified years with the native release last; ``native_constants`` /
  ``ladder_constants`` snapshot the framing table / the ladder's swaps;
  ``rewrite_stream`` re-emits a pin with ONE stream damaged or dropped and every
  other stream byte-identical (a missing name is a KeyError); the damaged-copy
  recipes produce what their names say.

Fresh-clone safe: the pins are tracked assets; no pin -> the pin-backed rows skip.

Run: .venv/bin/python -m pytest tests/test_conftest_scaffolding.py -q
"""
from __future__ import annotations

import ast
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import conftest as C                                            # noqa: E402
from rvt import versions as V                                   # noqa: E402

#: names no test module may bind at top level any more: the private copies #579 removed, and shadows of their one home
FORBIDDEN = {"_native_constants", "_no_leak", "_rewrite_stream", "_partition_of", "FOREIGN_FIRST", "FOREIGN",
             "NATIVE_LAST", "native_constants", "ladder_constants", "no_release_leak", "rewrite_stream", "partition_of"}
#: files that still carry a copy of their own -- delete the entry when that file adopts conftest's (then: an empty set)
EXEMPT = {"test_gates_shared_walk"}                               # a `_rewrite_stream(…, mutate)` of its own shape (#604)
#: the files #579 / #602 relieved of an autouse leak guard of their own: each keeps conftest's switched on module-wide
ADOPTERS = ["test_selfcheck_release", "test_inspect_release", "test_edit_text_release",
            "test_natively_framed", "test_estorage_cli_release", "test_edit_own_release",
            "test_rvt_edit_refusal", "test_release_ctx_refusal"]
TEST_FILES = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "tests", "test_*.py")))


def _tree(stem: str) -> ast.Module:
    path = os.path.join(ROOT, "tests", f"{stem}.py")
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def _top_level_names(tree: ast.Module) -> set[str]:
    """Every name the module binds at top level by ``def`` / ``class`` / assignment (``tree.body`` only, where every
    copy ever lived: a copy nested inside a class or function slips past this ratchet -- widen it the day one does)."""
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for n in tree.body:
        targets = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, (ast.AnnAssign, ast.AugAssign)) else []
        names |= {t.id for t in targets if isinstance(t, ast.Name)}
    return names


def test_no_module_carries_a_private_copy():
    clashes = {stem: sorted(_top_level_names(_tree(stem)) & FORBIDDEN) for stem in TEST_FILES if stem not in EXEMPT}
    clashes = {stem: names for stem, names in clashes.items() if names}
    assert clashes == {}, f"{clashes} -- import the own-release scaffolding from conftest instead (#579)"


def test_the_exempt_list_only_names_files_that_exist_and_still_need_it():
    for stem in EXEMPT:
        assert stem in TEST_FILES, stem
        assert _top_level_names(_tree(stem)) & FORBIDDEN, f"{stem} carries no copy any more: drop it from EXEMPT"


@pytest.mark.parametrize("stem", ADOPTERS)
def test_adopter_keeps_the_leak_guard_on(stem):
    marks = [n for n in _tree(stem).body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in n.targets)]
    assert any(isinstance(c, ast.Constant) and c.value == "no_release_leak" for m in marks for c in ast.walk(m.value)), \
        f"tests/{stem}.py: pytestmark must request the no_release_leak fixture"


def test_foreign_first_puts_the_native_release_last():
    assert sorted(C.FOREIGN_FIRST) == sorted(C.CERTIFIED_YEARS)
    assert C.FOREIGN == [y for y in C.CERTIFIED_YEARS if y != V.LATEST_RELEASE]   # the order the per-file copies had
    if V.LATEST_RELEASE in C.CERTIFIED_YEARS:
        assert C.FOREIGN_FIRST[-1] == V.LATEST_RELEASE


def test_native_and_ladder_constants_snapshot_what_a_context_rebinds():
    plain, ladder = C.native_constants(), C.ladder_constants()
    table = V.framing_table(V.LATEST_RELEASE)
    assert plain == dict(table, active_release=None)
    assert set(ladder) == {"iter_records", "adoc_decoder", "family_end_record"} and not set(ladder) & set(plain)


def test_damage_recipes_are_what_their_names_say():
    raw = bytes(range(256)) * 16                                  # 4 KiB
    hz = C.zero_partition_header(raw)
    assert len(hz) == len(raw) and hz[:16] == bytes(16) and hz[16:] == raw[16:]
    sz = C.zero_schema_bytes(raw)
    assert len(sz) == len(raw) and sz[2000:2064] == bytes(64) and sz[:2000] + sz[2064:] == raw[:2000] + raw[2064:]


@pytest.fixture(scope="module")
def pin() -> str:
    if not C.CERTIFIED_YEARS:
        pytest.skip("no certified pinned base")
    return C.pinned_base(C.FOREIGN_FIRST[0])


def test_rewrite_stream_damages_one_stream_and_keeps_the_rest_byte_identical(pin, tmp_path):
    from rvt.roundtrip import read_entries
    pname = C.partition_of(pin)
    assert pname.startswith("Partitions/")
    out = C.rewrite_stream(pin, tmp_path / "hz.rvt", pname, C.zero_partition_header)
    assert out == str(tmp_path / "hz.rvt") and os.path.isfile(out)
    before = {e.path: e.data for e in read_entries(pin) if e.entry_type == "stream"}
    after = {e.path: e.data for e in read_entries(out) if e.entry_type == "stream"}
    assert set(after) == set(before)
    assert after[pname] == C.zero_partition_header(before[pname]) != before[pname]
    assert all(after[p] == before[p] for p in before if p != pname)
    dropped = {e.path for e in read_entries(C.rewrite_stream(pin, tmp_path / "nolatest.rvt", "Formats/Latest", None))}
    assert "Formats/Latest" not in dropped and pname in dropped
    with pytest.raises(KeyError):
        C.rewrite_stream(pin, tmp_path / "never.rvt", "No/Such/Stream", C.zero_partition_header)
    assert not os.path.exists(tmp_path / "never.rvt")


def test_truncated_and_header_zeroed_copies(pin, tmp_path):
    t = C.truncated_copy(pin, tmp_path / "t64k.rvt", 65536)
    with open(pin, "rb") as fh:
        head = fh.read(65536)
    with open(t, "rb") as fh:
        assert fh.read() == head
    z = C.cfb_header_zeroed_copy(pin, tmp_path / "cfb_zeroed.rvt")
    assert os.path.getsize(z) == os.path.getsize(pin)
    with open(z, "rb") as fh:
        assert fh.read(512) == bytes(512) and fh.read(65536 - 512) == head[512:]
