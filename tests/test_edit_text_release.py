"""test_edit_text_release.py -- tekton-native's size-preserving text edit
(``tools/rvt_edit_text.py``, shipped as ``skills/tekton-native/scripts/
rvt_edit_text.py``) walks, edits, re-frames and reads back a project under
ITS OWN release on every certified pinned base (issue #116, Refs #70):

* the CLI reaches ``SELF-CHECK PASS`` (CRC / ECC / walker / stamps all clean)
  for a same-length UTF-16 rename of a level;
* the output validates 0 errors STANDALONE and still declares the input's
  release; the renamed level decodes with the new name;
* the native framing constants are back after every run -- the foreign
  releases run first, so a leak would break the following native edit;
* a natively framed file enters nothing and imports no ``rvt.frontdoor``
  module (``rvt.native_framing``, #575); a foreign one still enters the
  AUTHORING context (``release_ctx``), not the read-side ladder.

Run: .venv/bin/python -m pytest tests/test_edit_text_release.py -q
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import FOREIGN, FOREIGN_FIRST, context_constants, load_tool, pinned_base    # noqa: E402
from rvt import versions as V                                  # noqa: E402
from rvt.frontdoor import release_ctx as RC                    # noqa: E402

LEVEL_ID = 1351691                     # "GEN B1 - Basement", present on every pin
OLD_NAME, NEW_NAME = "GEN B1 - Basement", "OUR B1 - Basement"      # same length
pytestmark = pytest.mark.usefixtures("no_release_leak")             # foreign pins run first: a leak breaks the native edit


@pytest.fixture
def release_leak_extra():
    """The names the AUTHORING context swaps, watched on top of the framing table (whose trailer tag the writer's
    ``BLOCK_TRL_TAG`` alias reads): nothing may leak past an edit of a 2025/2024 file."""
    return context_constants


@pytest.fixture(scope="module")
def edit_text():
    return load_tool("rvt_edit_text")


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


def _modules_after_edit(year: int, out: str) -> set[str]:
    """Run the CLI in a fresh interpreter on the pinned base of ``year`` (rc 0,
    ``SELF-CHECK PASS``) and return the ``rvt.*`` modules it had imported."""
    code = ("import sys; sys.path.insert(0, 'tools'); import rvt_edit_text as T; "
            "rc = T.main(sys.argv[1:]); "
            "print('MODULES', *sorted(m for m in sys.modules if m.startswith('rvt'))); sys.exit(rc)")
    r = subprocess.run([sys.executable, "-c", code, pinned_base(year), "--old", OLD_NAME,
                        "--new", NEW_NAME, "--utf16", "-o", out], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and "SELF-CHECK PASS" in r.stdout, (r.returncode, r.stderr[-600:])
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("MODULES ")][-1]
    return set(line.split()[1:])


def test_native_edit_imports_nothing_under_rvt_frontdoor(tmp_path):
    mods = _modules_after_edit(V.LATEST_RELEASE, str(tmp_path / "native.rvt"))
    assert "rvt.native_framing" in mods
    heavy = sorted(m for m in mods if m.startswith(("rvt.frontdoor", "rvt.global_framing", "rvt.versions")))
    assert heavy == [], heavy


@pytest.mark.parametrize("year", FOREIGN)
def test_foreign_edit_enters_the_authoring_context_not_the_read_side_ladder(year, tmp_path):
    mods = _modules_after_edit(year, str(tmp_path / f"f{year}.rvt"))
    assert "rvt.frontdoor.release_ctx" in mods, sorted(mods)
