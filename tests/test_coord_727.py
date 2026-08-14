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


def cli(*argv):
    return subprocess.run([sys.executable, COORD, *argv], capture_output=True, text=True, timeout=60)


def run(tmp_path, cmd, tree: bytes = TREE.encode(), registry: bytes = b"[]", prs: bytes = b"[]"):
    """coord.py <cmd…> --tree/--registry/--prs as files holding exactly these bytes (None = do not create that file)."""
    argv = list(cmd)
    for flag, data in (("tree", tree), ("registry", registry), ("prs", prs)):
        if data is not None:
            (tmp_path / flag).write_bytes(data)
        argv += [f"--{flag}", str(tmp_path / flag)]
    return cli(*argv)


def refused(r, *needles):
    """Exit 2, nothing on stdout (a caller doing out=$(…) gets no half-answer), ONE stderr line naming what to fix."""
    assert r.returncode == 2 and r.stdout == "" and len(r.stderr.strip().splitlines()) == 1 and "Traceback" not in r.stderr, (r.returncode, r.stdout, r.stderr)
    for n in needles:
        assert n in r.stderr, (n, r.stderr)


@pytest.mark.parametrize("codec", ["utf-16", "utf-16-le", "utf-16-be"])          # PowerShell 5 `>` = utf-16 (LE + BOM); the BOM-less pair for any other such producer
@pytest.mark.parametrize("cmd", [RESERVE, ["batchjudge"]], ids=["reserve", "batchjudge"])
def test_a_utf16_tree_is_refused_not_read_as_an_empty_main(tmp_path, codec, cmd):
    refused(run(tmp_path, cmd, tree=TREE.encode(codec)),
            f"--tree {tmp_path / 'tree'}: ", "none under experiments/", coord.TREE_RECIPE, "Out-File -Encoding utf8")


def test_before_the_law_such_a_tree_was_a_floor_answer():
    """Pins the mechanism the refusal replaces: decoded bytes-faithfully, UTF-16 text splits into one 'name' per byte,
    none under experiments/, so the pre-#727 arithmetic saw nothing on main and `/batches 1` got BATCH_FLOOR + 1."""
    names = coord.tree_names(TREE.encode("utf-16").decode("utf-8", errors="surrogateescape"))
    assert names and not any(n.startswith("experiments/") for n in names)
    assert coord.next_batch(1, coord.batch_numbers(names), [], set()) == (coord.BATCH_FLOOR + 1,) * 2


@pytest.mark.parametrize("shape", ["lines", "crlf", "z"])
def test_a_utf8_bom_does_not_hide_the_first_name(tmp_path, shape):
    """`Out-File -Encoding utf8` (the producer the refusal recommends on Windows PowerShell) writes a BOM; glued to the
    first name it made `experiments/…/batch_60.json` unrecognisable and the answer 58. The BOM is dropped instead, and
    the reply says what it saw on main."""
    body = {"lines": TREE, "crlf": TREE.replace("\n", "\r\n"), "z": TREE.replace("\n", "\0")}[shape]
    r = run(tmp_path, RESERVE, tree=b"\xef\xbb\xbf" + body.encode("utf-8"))
    assert r.returncode == 0 and r.stderr == "", r.stderr
    out = json.loads(r.stdout)
    assert out["lo"] == 61 and "highest batch on main: 60)" in out["reply"]


@pytest.mark.parametrize("tree", [b"", b"\n", b"\r\n", b"\xef\xbb\xbf\r\n"], ids=["empty", "lf", "crlf", "bom-crlf"])
def test_an_empty_tree_stays_legal_and_the_reply_says_main_holds_none(tmp_path, tree):
    """A repository with no experiments/ yet: the recipe prints nothing (cmd/PowerShell may still write a line end).
    Legal -- and the one residue the law cannot see (a 0-byte file left by a `>` whose git failed) is at least made
    VISIBLE: the reply states 'highest batch on main: none', which a reader who knows main holds batches will question."""
    r = run(tmp_path, RESERVE, tree=tree)
    assert r.returncode == 0 and r.stderr == "", r.stderr
    out = json.loads(r.stdout)
    assert out["lo"] == coord.BATCH_FLOOR + 1 and "highest batch on main: none)" in out["reply"]


def test_a_listing_of_the_wrong_tree_is_refused(tmp_path):
    """Names, none under experiments/: `git ls-tree` of another directory or without the pathspec in a repo that has no
    experiments/ -- an operator error the same law catches; the message says an EMPTY file is the honest 'nothing yet'."""
    refused(run(tmp_path, ["batchjudge"], tree=b"src/rvt/validate.py\0tools/dev/coord.py\0"), "2 name(s), none under experiments/", "EMPTY file")


@pytest.mark.parametrize("missing", ["tree", "registry", "prs"])
def test_a_missing_input_file_is_one_line_not_a_traceback(tmp_path, missing):
    refused(run(tmp_path, RESERVE, **{missing: None}), f"cannot read {tmp_path / missing}: No such file or directory")


@pytest.mark.parametrize("bad", [b"not json", "[]".encode("utf-16"), b""], ids=["garbage", "utf16", "empty"])
@pytest.mark.parametrize("which", ["registry", "prs"])
def test_an_unparseable_json_input_is_one_line_naming_the_file(tmp_path, which, bad):
    """The same PowerShell `>` writes reg.json / prs.json as UTF-16 too; that always failed closed, but as a traceback
    naming no file. Now: one line, the file, the parser's reason."""
    refused(run(tmp_path, ["batchjudge"], **{which: bad}), f"{tmp_path / which}: not readable JSON (")


def test_bom_led_json_inputs_read_like_plain_utf8(tmp_path):
    """`Out-File -Encoding utf8` -- the producer the tree refusal recommends on Windows PowerShell -- BOMs reg.json and
    prs.json too when applied to all three files; utf-8-sig reads them instead of refusing 'Unexpected UTF-8 BOM'."""
    bom = b"\xef\xbb\xbf"
    registry = bom + json.dumps([{"user": {"login": "github-actions[bot]"}, "body": "<!-- batches by=cam lo=63 hi=65 issue=700 token=t0 -->"}]).encode()
    r = run(tmp_path, RESERVE, tree=bom + TREE.encode(), registry=registry, prs=bom + b"[]")
    assert r.returncode == 0 and r.stderr == "", r.stderr
    assert json.loads(r.stdout)["lo"] == 66                      # 63..65 reserved (read through the BOM) lifts it past main's 60


@pytest.mark.parametrize("argv", [["queue", "--issues", "nope.json", "--prs", "nope.json"], ["locks", "--comments", "nope.json"],
                                  ["reqfile", "--path", "nope.md"]], ids=["queue", "locks", "reqfile"])
def test_the_other_subcommands_word_a_missing_file_the_same_way(tmp_path, argv):
    """One mechanism in main(), not a reserve/batchjudge special case: the other file-reading subcommands too."""
    refused(cli(argv[0], *(str(tmp_path / a) if a.startswith("nope.") else a for a in argv[1:])), f"cannot read {tmp_path / 'nope.'}")


def test_the_law_and_the_tokenizer_unit():
    assert coord.on_main_batches("") == set() == coord.on_main_batches("\r\n")
    assert coord.tree_names("\ufeff" + TREE)[0] == "experiments/acceptance/batch_60.json" == coord.tree_names("\ufeff" + TREE.replace("\n", "\0"))[0]   # the tokenizer drops the BOM, in both shapes
    assert coord.on_main_batches("\ufeff" + TREE) == {57, 60} == coord.on_main_batches(TREE.replace("\n", "\0"))
    with pytest.raises(coord.InputError, match=r"^tree16\.txt: 3 name\(s\), none under experiments/"):
        coord.on_main_batches("e\0x\0p\0", "tree16.txt")
    with pytest.raises(ValueError):                       # InputError is a ValueError: a caller catching the broad class still fails closed
        coord.on_main_batches('"docs/inbox/x.md"\n')
    assert coord.on_main_batches("README.md\0experiments/acceptance/batch_56.json\0") == {56}   # a whole-repo listing is read, not refused: something IS under experiments/
