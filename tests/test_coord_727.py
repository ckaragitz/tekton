"""#727: `coord.py reserve` / `batchjudge` fail CLOSED on a `--tree` file they cannot read, and every input file that is
missing or unparseable is a one-line error (exit 2), never a traceback and never an empty picture of main.

#723 made the `--tree` reader bytes-faithful so no producer can crash it; the flip side, outside the documented bash
recipe, was that a `tree.txt` written by Windows PowerShell 5 redirection (`git ls-tree … > tree.txt` is UTF-16LE with
a BOM there) decoded to text naming nothing under `experiments/`, so `on_main` came out EMPTY and `reserve` answered
from the floor -- numbers already on main handed out again, silently, where the same file used to raise. These rows
run the CLI exactly as the tech-lead session does (three input files, JSON on stdout) over such files. Stdlib only:
no git needed, fresh-clone runnable.
"""
import json
import os
import subprocess
import sys

import pytest

from conftest import ROOT, load_tool

COORD = os.path.join(ROOT, "tools", "dev", "coord.py")
coord = load_tool("dev/coord")

TREE = "experiments/acceptance/batch_60.json\nexperiments/acceptance/batch2_manifest.json\nexperiments/w x/batch_57.json\n"   # the TOP number first: a reader that loses the first line answers 58, not 61
RESERVE = ["reserve", "--k", "1", "--by", "cam", "--issue", "9", "--token", "t1", "--registry-number", "1"]


def run(tmp_path, cmd, tree: bytes = None, registry: bytes = b"[]", prs: bytes = b"[]"):
    """coord.py <cmd…> --tree/--registry/--prs as files holding exactly these bytes (None = do not create the file)."""
    paths = {}
    for flag, data in (("tree", tree), ("registry", registry), ("prs", prs)):
        paths[flag] = tmp_path / flag
        if data is not None:
            paths[flag].write_bytes(data)
    r = subprocess.run([sys.executable, COORD, *cmd, *(x for f, p in paths.items() for x in (f"--{f}", str(p)))],
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def refused(rc, out, err, *needles):
    """Exit 2, nothing on stdout (a caller doing out=$(…) gets no half-answer), ONE stderr line naming what to fix."""
    assert rc == 2 and out == "" and len(err.strip().splitlines()) == 1 and "Traceback" not in err, (rc, out, err)
    for n in needles:
        assert n in err, (n, err)


@pytest.mark.parametrize("codec", ["utf-16", "utf-16-le", "utf-16-be"])          # PowerShell 5 `>` = utf-16 (LE + BOM); the BOM-less pair for any other such producer
@pytest.mark.parametrize("cmd", [RESERVE, ["batchjudge"]], ids=["reserve", "batchjudge"])
def test_a_utf16_tree_is_refused_not_read_as_an_empty_main(tmp_path, codec, cmd):
    rc, out, err = run(tmp_path, cmd, tree=TREE.encode(codec))
    refused(rc, out, err, f"--tree {tmp_path / 'tree'}", "none under experiments/", coord.TREE_RECIPE, "Out-File -Encoding utf8")


def test_before_the_law_such_a_tree_was_a_floor_answer(tmp_path):
    """Pins the mechanism the refusal replaces: decoded bytes-faithfully, UTF-16 text splits into one 'name' per byte,
    none under experiments/, so the pre-#727 arithmetic saw nothing on main and `/batches 1` got BATCH_FLOOR + 1."""
    text = TREE.encode("utf-16").decode("utf-8", errors="surrogateescape")
    names = coord.tree_names(text)
    assert names and not any(n.startswith("experiments/") for n in names)
    assert coord.batch_numbers(names) == set()
    assert coord.next_batch(1, coord.batch_numbers(names), [], set()) == (coord.BATCH_FLOOR + 1,) * 2


@pytest.mark.parametrize("shape", ["lines", "crlf", "z"])
def test_a_utf8_bom_does_not_hide_the_first_name(tmp_path, shape):
    """`Out-File -Encoding utf8` (the producer the refusal recommends on Windows PowerShell) writes a BOM; glued to the
    first name it made `experiments/…/batch_60.json` unrecognisable and the answer 58. The BOM is dropped instead."""
    body = {"lines": TREE, "crlf": TREE.replace("\n", "\r\n"), "z": TREE.replace("\n", "\0")}[shape]
    rc, out, err = run(tmp_path, RESERVE, tree=b"\xef\xbb\xbf" + body.encode("utf-8"))
    assert rc == 0 and err == "", err
    assert json.loads(out)["lo"] == 61


@pytest.mark.parametrize("tree", [b"", b"\n", b"\r\n"], ids=["empty", "lf", "crlf"])
def test_an_empty_tree_stays_legal(tmp_path, tree):
    """A repository with no experiments/ yet: the recipe prints nothing (cmd/PowerShell may still write a line end)."""
    rc, out, err = run(tmp_path, RESERVE, tree=tree)
    assert rc == 0 and err == "", err
    assert json.loads(out)["lo"] == coord.BATCH_FLOOR + 1


def test_a_listing_of_the_wrong_tree_is_refused(tmp_path):
    """Names, none under experiments/: `git ls-tree` of another directory or without the pathspec in a repo that has no
    experiments/ -- an operator error the same law catches; the message says an EMPTY file is the honest 'nothing yet'."""
    refused(*run(tmp_path, ["batchjudge"], tree=b"src/rvt/validate.py\0tools/dev/coord.py\0"), "2 name(s), none under experiments/", "EMPTY file")


@pytest.mark.parametrize("missing", ["tree", "registry", "prs"])
def test_a_missing_input_file_is_one_line_not_a_traceback(tmp_path, missing):
    files = {"tree": TREE.encode(), "registry": b"[]", "prs": b"[]", missing: None}
    refused(*run(tmp_path, RESERVE, **files), f"cannot read {tmp_path / missing}", "No such file or directory")


@pytest.mark.parametrize("bad", [b"not json", "[]".encode("utf-16"), b""], ids=["garbage", "utf16", "empty"])
@pytest.mark.parametrize("which", ["registry", "prs"])
def test_an_unparseable_json_input_is_one_line_naming_the_file(tmp_path, which, bad):
    """The same PowerShell `>` writes reg.json / prs.json as UTF-16 too; that always failed closed, but as a traceback
    naming no file. Now: one line, the file, the parser's reason."""
    files = {"tree": TREE.encode(), "registry": b"[]", "prs": b"[]", which: bad}
    refused(*run(tmp_path, ["batchjudge"], **files), f"{tmp_path / which}: not readable JSON")


def test_the_other_subcommands_word_a_missing_file_the_same_way(tmp_path):
    """One mechanism in main(), not a reserve/batchjudge special case: `queue` and `locks` read JSON files too."""
    for argv in (["queue", "--issues", str(tmp_path / "nope.json"), "--prs", str(tmp_path / "nope.json")],
                 ["locks", "--comments", str(tmp_path / "nope.json")],
                 ["reqfile", "--path", str(tmp_path / "nope.md")]):
        r = subprocess.run([sys.executable, COORD, *argv], capture_output=True, text=True, timeout=60)
        refused(r.returncode, r.stdout, r.stderr, "cannot read", "nope.")


def test_on_main_batches_unit():
    assert coord.on_main_batches("") == set() and coord.on_main_batches("\r\n") == set()
    assert coord.on_main_batches("﻿" + TREE) == {57, 60} == coord.on_main_batches(TREE.replace("\n", "\0"))
    with pytest.raises(coord.InputError, match="none under experiments/"):
        coord.on_main_batches("e\0x\0p\0")
    with pytest.raises(ValueError):                       # InputError is a ValueError: a caller catching the broad class still fails closed
        coord.on_main_batches('"docs/inbox/x.md"\n')
    assert coord.on_main_batches("README.md\0experiments/acceptance/batch_56.json\0") == {56}   # a whole-repo listing is read, not refused: something IS under experiments/
