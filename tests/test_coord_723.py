"""#723: `coord.py reserve` / `batchjudge` read the default-branch batch files NUL-clean and quote-tolerant.

The `/batches` reservation exists so two sessions never STAGE the same viewer batch numbers (#285). Its picture of
"what is already on main" came from `git ls-tree -r --name-only … experiments/` split on WHITESPACE, and git C-quotes
any name holding a non-ASCII byte: `experiments/w x/batch_57.json` split into two tokens and
`"experiments/m\\303\\251tier/batch_58.json"` gained a leading quote -- both silently fell out of `on_main`, so 57 and
58 could be handed out again. Fail-OPEN in a collision guard. These rows feed the reader REAL `git ls-tree` output in
every shape a producer can hand it (the documented `-z` recipe; the older line recipe under git's default quoting; the
same line recipe from a machine with `core.quotePath=false`) from a throwaway repo, and prove through `reserve` and
`batchjudge` themselves that such numbers count as taken. Fresh-clone runnable: stdlib + git (the git rows skip
without it, through the git_repo fixture).
"""
import json
import os
import subprocess
import sys

import pytest

from conftest import ROOT, git, git_commit, load_tool

COORD = os.path.join(ROOT, "tools", "dev", "coord.py")
coord = load_tool("dev/coord")

ODD = {"experiments/w x/batch_57.json": "{}\n",           # a blank in a stream directory: whitespace-split lost it
       "experiments/métier/batch_54.json": "{}\n",        # non-ASCII: git C-quotes it under the default core.quotePath
       "experiments/ls\u2028sep/batch_58.json": "{}\n",   # U+2028: whitespace to str.split(), a line end to str.splitlines(), neither to git -- and the
                                                          # path gate admits it; it carries the TOP number so every misreading moves `reserve`'s answer
       "experiments/acceptance/batch_56.json": "{}\n"}    # the ordinary shape, for contrast
ON_MAIN = {54, 56, 57, 58}
SHAPES = ["z", "lines", "lines_raw"]


@pytest.fixture
def trees(git_repo):
    """-> {shape: `git ls-tree … -- experiments/` output as conftest.git() returns it (decoded and str.strip()ped: the line
    shapes lose their trailing "\n", the -z shape keeps its NULs, trailing one included, since NUL is not whitespace --
    the unit row below covers trailing "\n"/CRLF explicitly)}: "z" = the documented -z recipe, "lines" = --name-only
    under git's default quoting (really C-quoted here: GIT_CONFIG_GLOBAL is /dev/null in the rig's GIT_ENV),
    "lines_raw" = the same from a machine with core.quotePath=false (non-ASCII arrives raw)."""
    git_commit(git_repo, ODD, "batches under awkward stream directories")
    out = {"z": git(git_repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "experiments/"),
           "lines": git(git_repo, "ls-tree", "-r", "--name-only", "HEAD", "--", "experiments/"),
           "lines_raw": git(git_repo, "-c", "core.quotePath=false", "ls-tree", "-r", "--name-only", "HEAD", "--", "experiments/")}
    assert "\0" in out["z"] and '"experiments/m\\303\\251tier/batch_54.json"' in out["lines"].split("\n") \
        and "experiments/ls\u2028sep/batch_58.json" in out["lines_raw"].split("\n"), out          # the rig reproduces each misread's input
    return out


@pytest.mark.parametrize("shape", SHAPES)
def test_batch_files_under_blank_or_non_ascii_directories_count_as_on_main(trees, shape):
    assert coord.batch_numbers(coord.tree_names(trees[shape])) == ON_MAIN


def test_the_old_whitespace_reading_is_what_lost_them(trees):
    """Pins the bug's mechanism so the fix cannot quietly regress to `.split()`: over the very same line output the
    whitespace reading keeps only the ordinary batch (57 split in two, 54 and 58 C-quoted)."""
    assert coord.batch_numbers(trees["lines"].split()) == {56}


def _cli(tmp_path, tree_text, registry, prs, *argv):
    """Run the coord CLI the way the tech-lead session does: the three inputs as files, JSON out."""
    files = {"--tree": tree_text, "--registry": json.dumps(registry), "--prs": json.dumps(prs)}
    for flag, text in files.items():
        (tmp_path / flag.lstrip("-")).write_text(text, encoding="utf-8")
    argv = [*map(str, argv), *(a for flag in files for a in (flag, str(tmp_path / flag.lstrip("-"))))]
    return json.loads(subprocess.run([sys.executable, COORD, *argv], capture_output=True, text=True, check=True).stdout)


@pytest.mark.parametrize("shape", SHAPES)
def test_reserve_never_reissues_a_number_staged_under_such_a_directory(trees, shape, tmp_path):
    """End to end, with nothing but the tree deciding: 54, 56..58 are on main, no reservation, no open PR -- so
    `/batches 2` must answer 59..60. The misread answered 57..58 from the line output (only 56 survived; from a
    quotePath=false producer 54 survived too, same answer) and 15..16 from the -z output (one unsplittable token,
    nothing survived): re-issued numbers either way."""
    got = _cli(tmp_path, trees[shape], [], [], "reserve", "--k", 2, "--by", "cam", "--issue", 9, "--token", "t1", "--registry-number", 1)
    assert (got["lo"], got["hi"]) == (59, 60), got


@pytest.mark.parametrize("shape", SHAPES)
def test_batchjudge_does_not_call_an_edit_of_such_a_batch_file_a_clash(trees, shape, tmp_path):
    """The other consumer of `on_main`: pr_batches() counts a PR's batch file as ADDED only when its number is not on
    main. 57..58 were once reserved for issue 9; a later PR for issue 12 re-records a verdict in the existing
    `experiments/w x/batch_57.json`. That is an edit, not a new number -- no clash. With 57 misread as absent from
    main it became "PR 6 adds 57, reserved for #9" and the PR would have been told to renumber a file that is on main."""
    registry = [{"user": {"login": "github-actions[bot]"}, "body": "<!-- batches by=cam lo=57 hi=58 issue=9 token=t0 -->"}]
    prs = [{"number": 6, "author": {"login": "x"}, "body": "Closes #12", "files": [{"path": "experiments/w x/batch_57.json"}]}]
    assert _cli(tmp_path, trees[shape], registry, prs, "batchjudge") == []


def test_the_cli_reads_a_z_tree_bytes_faithfully(tmp_path):
    """No git needed: a -z tree whose names hold a raw CR, a raw LF and a non-UTF-8 (Latin-1) byte -- names the path
    gate refuses in THIS repo, but the reader must not turn them into a re-issued number or a crash. Universal
    newlines used to fold the CR into LF, `.` could not cross the LF, and the Latin-1 byte was a UnicodeDecodeError."""
    tree = tmp_path / "tree"
    tree.write_bytes(b"experiments/acceptance/batch_56.json\0experiments/cr\rdir/batch_60.json\0"
                     b"experiments/lf\ndir/batch_61.json\0experiments/lat\xe9/batch_62.json\0")
    for name, text in {"registry": "[]", "prs": "[]"}.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    out = subprocess.run([sys.executable, COORD, "reserve", "--k", "1", "--by", "cam", "--issue", "9", "--token", "t1", "--registry-number", "1",
                          "--tree", str(tree), "--registry", str(tmp_path / "registry"), "--prs", str(tmp_path / "prs")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["lo"] == 63          # 60, 61 and 62 all counted as on main


def test_tree_names_splits_on_nul_when_present_else_on_git_lines_and_strips_the_quotes():
    assert coord.tree_names("a b/batch_1.json\0c\u2028d/batch_2.json\0e\nf/batch_3.json\0") == ["a b/batch_1.json", "c\u2028d/batch_2.json", "e\nf/batch_3.json"]
    assert coord.tree_names('a b/batch_1.json\r\n"m\\303\\251tier/batch_2.json"\r\nc\u2028d/batch_3.json\n') == \
        ["a b/batch_1.json", "m\\303\\251tier/batch_2.json", "c\u2028d/batch_3.json"]      # CRLF dropped, quotes stripped (escapes left as they are), U+2028 is not a line end
    assert coord.tree_names("") == [] and coord.tree_names("\n\n") == []
    assert coord.batch_numbers(coord.tree_names('"experiments/q\\"d/batch_7.json"\n"experiments/u/batch_9.json\n')) == {7, 9}   # an unbalanced quote (git never emits one) errs towards "taken"
