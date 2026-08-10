"""test_edit_text_release.py -- tekton-native's size-preserving text edit
(``tools/rvt_edit_text.py``, shipped as ``skills/tekton-native/scripts/
rvt_edit_text.py``) walks, edits, re-frames and reads back a project under
ITS OWN release on every certified pinned base (issue #116, Refs #70):

* the CLI reaches ``SELF-CHECK PASS`` (CRC / ECC / walker / stamps all clean)
  for a same-length UTF-16 rename of a level;
* the output validates 0 errors STANDALONE and still declares the input's
  release; the renamed level decodes with the new name;
* the native framing constants are back after every run -- the foreign
  releases run first, so a leak would break the following native edit.

Run: .venv/bin/python -m pytest tests/test_edit_text_release.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import CERTIFIED_YEARS, load_tool, pinned_base    # noqa: E402
from rvt import partitions as P                                # noqa: E402
from rvt import versions as V                                  # noqa: E402
from rvt import writer as W                                    # noqa: E402
from rvt.frontdoor import release_ctx as RC                    # noqa: E402

LEVEL_ID = 1351691                     # "GEN B1 - Basement", present on every pin
OLD_NAME, NEW_NAME = "GEN B1 - Basement", "OUR B1 - Basement"      # same length
FOREIGN_FIRST = sorted(CERTIFIED_YEARS, key=lambda y: y == V.LATEST_RELEASE)


@pytest.fixture(scope="module")
def edit_text():
    return load_tool("rvt_edit_text")


def _native_constants() -> dict:
    """The framing table + the writer's trailer-tag copy a release context
    swaps: snapshot to prove nothing leaks past an edit of a 2025/2024 file."""
    snap = {k: getattr(P, k) for k in V.framing_table(V.LATEST_RELEASE)}
    snap["W.BLOCK_TRL_TAG"] = W.BLOCK_TRL_TAG
    snap["active_release"] = RC.active_release()
    return snap


@pytest.fixture(autouse=True)
def _no_leak():
    before = _native_constants()
    assert before["active_release"] is None
    yield
    assert _native_constants() == before


def _level_name(path: str, level_id: int) -> str | None:
    """The level's decoded name, read under the file's own release."""
    from rvt.mutate import Document
    with RC.host_release_context(path):
        for lv in Document.from_file(path).levels():
            if lv["id"] == level_id:
                return lv.get("name")
    return None


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_text_edit_self_checks_pass_under_the_inputs_release(year, edit_text, tmp_path, capsys):
    out = str(tmp_path / f"t{year}" / "edited.rvt")          # fresh dir: created
    rc = edit_text.main([pinned_base(year), "--old", OLD_NAME, "--new", NEW_NAME,
                         "--utf16", "-o", out])
    printed = capsys.readouterr().out
    assert rc == 0 and "SELF-CHECK PASS" in printed, printed[-800:]
    assert "CRC failures 0; ECC mismatches 0; walker errors 0" in printed
    assert "new text present True; old text present False" in printed

    from rvt.validate import validate_file
    assert V.detect_release(out) == year                     # Revit N in -> Revit N out
    rep = validate_file(out).to_json()                       # judged bare, as a user would
    assert rep["counts"]["error"] == 0, [f for f in rep["findings"] if f.get("severity") == "error"][:5]
    assert _level_name(out, LEVEL_ID) == NEW_NAME


def test_length_change_is_refused_before_any_read(edit_text, tmp_path, capsys):
    out = str(tmp_path / "never.rvt")
    rc = edit_text.main([pinned_base(FOREIGN_FIRST[0]), "--old", OLD_NAME,
                         "--new", OLD_NAME + "X", "--utf16", "-o", out])
    assert rc == 2 and not os.path.exists(out)
    assert "size-preserving edit required" in capsys.readouterr().err
