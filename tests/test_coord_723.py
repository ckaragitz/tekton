"""#723: `coord.py reserve` / `batchjudge` read the default-branch batch files NUL-clean and quote-tolerant.

The `/batches` reservation exists so two sessions never STAGE the same viewer batch numbers (#285). Its picture of
"what is already on main" came from `git ls-tree -r --name-only … experiments/` split on WHITESPACE, and git C-quotes
any name holding a non-ASCII byte: `experiments/w x/batch_57.json` split into two tokens and
`"experiments/m\\303\\251tier/batch_58.json"` gained a leading quote -- both silently fell out of `on_main`, so 57 and
58 could be handed out again. Fail-OPEN in a collision guard. These rows feed the reader REAL `git ls-tree` output in
both shapes (the documented `-z` recipe and the older line-wise one) from a throwaway repo, and prove through
`reserve` and `batchjudge` themselves that such numbers count as taken. Fresh-clone runnable: stdlib + git.
"""
import json
import os
import subprocess
import sys

import pytest

from conftest import HAVE_GIT, ROOT, git, git_commit, load_tool

COORD = os.path.join(ROOT, "tools", "dev", "coord.py")
coord = load_tool("dev/coord")

pytestmark = pytest.mark.skipif(not HAVE_GIT, reason="needs git")

ODD = {"experiments/w x/batch_57.json": "{}\n",          # a blank in a stream directory: whitespace-split lost it
       "experiments/métier/batch_58.json": "{}\n",       # non-ASCII: git C-quotes it under the default core.quotePath
       "experiments/acceptance/batch_56.json": "{}\n",   # the ordinary shape, for contrast
       "docs/batch_99.json": "{}\n"}                     # outside experiments/: never a batch number


@pytest.fixture
def trees(git_repo):
    """-> {"z": <ls-tree -z output>, "lines": <ls-tree --name-only output>} of a repo holding ODD, as text exactly
    as `> tree.txt` would leave it (the line form really is C-quoted here: GIT_CONFIG_GLOBAL is /dev/null in the rig)."""
    git_commit(git_repo, ODD, "batches under awkward stream directories")
    z = git(git_repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "experiments/")
    lines = git(git_repo, "ls-tree", "-r", "--name-only", "HEAD", "--", "experiments/")
    assert "\0" in z and '"experiments/m\\303\\251tier/batch_58.json"' in lines.splitlines(), (z, lines)   # the rig reproduces the misread's input
    return {"z": z, "lines": lines}


@pytest.mark.parametrize("shape", ["z", "lines"])
def test_batch_files_under_blank_or_non_ascii_directories_count_as_on_main(trees, shape):
    assert coord.batch_numbers(coord.tree_names(trees[shape])) == {56, 57, 58}


def test_the_old_whitespace_reading_is_what_lost_them(trees):
    """Pins the bug's mechanism so the fix cannot quietly regress to `.split()`: over the very same line output a
    whitespace reading still loses the batch under the BLANK-carrying directory (57) -- which is why tree_names()
    never splits on blanks -- while the C-quoted one (58) now survives any reading because batch_numbers() un-quotes."""
    assert coord.batch_numbers(trees["lines"].split()) == {56, 58}


def _cli(*argv):
    return json.loads(subprocess.run([sys.executable, COORD, *map(str, argv)], capture_output=True, text=True, check=True).stdout)


@pytest.mark.parametrize("shape", ["z", "lines"])
def test_reserve_never_reissues_a_number_staged_under_such_a_directory(trees, shape, tmp_path):
    """End to end through the CLI the tech-lead session runs, with nothing but the tree deciding: 56..58 are on main,
    no reservation, no open PR -- so `/batches 2` must answer 59..60. The misread answered 57..58 from the line output
    (only 56 survived) and 15..16 from the -z output (one unsplittable token, nothing survived): re-issued numbers."""
    tree, reg, prs = tmp_path / "tree.txt", tmp_path / "reg.json", tmp_path / "prs.json"
    tree.write_text(trees[shape], encoding="utf-8")
    reg.write_text("[]", encoding="utf-8")
    prs.write_text("[]", encoding="utf-8")
    got = _cli("reserve", "--k", 2, "--by", "cam", "--issue", 9, "--token", "t1", "--registry-number", 1,
               "--tree", tree, "--registry", reg, "--prs", prs)
    assert (got["lo"], got["hi"]) == (59, 60), got


@pytest.mark.parametrize("shape", ["z", "lines"])
def test_batchjudge_does_not_call_an_edit_of_such_a_batch_file_a_clash(trees, shape, tmp_path):
    """The other consumer of `on_main`: pr_batches() counts a PR's batch file as ADDED only when its number is not on
    main. 57..58 were once reserved for issue 9; a later PR for issue 12 re-records a verdict in the existing
    `experiments/w x/batch_57.json`. That is an edit, not a new number -- no clash. With 57 misread as absent from
    main it became "PR 6 adds 57, reserved for #9" and the PR would have been told to renumber a file that is on main."""
    tree, reg, prs = tmp_path / "tree.txt", tmp_path / "reg.json", tmp_path / "prs.json"
    tree.write_text(trees[shape], encoding="utf-8")
    reg.write_text(json.dumps([{"user": {"login": "github-actions[bot]"},
                                "body": "<!-- batches by=cam lo=57 hi=58 issue=9 token=t0 -->"}]), encoding="utf-8")
    prs.write_text(json.dumps([{"number": 6, "author": {"login": "x"}, "body": "Closes #12",
                                "files": [{"path": "experiments/w x/batch_57.json"}]}]), encoding="utf-8")
    assert _cli("batchjudge", "--tree", tree, "--registry", reg, "--prs", prs) == []


def test_tree_names_splits_on_nul_when_present_else_on_lines_never_on_blanks():
    assert coord.tree_names("a b/batch_1.json\0c/batch_2.json\0") == ["a b/batch_1.json", "c/batch_2.json"]
    assert coord.tree_names("a b/batch_1.json\nc/batch_2.json\n") == ["a b/batch_1.json", "c/batch_2.json"]
    assert coord.tree_names("") == [] and coord.tree_names("\n\0") == ["\n"]   # a NUL-separated name may itself hold a newline
    assert coord.batch_numbers(['"experiments/q\\"d/batch_7.json"', 'experiments/plain/batch_8.json', '"unbalanced/batch_9.json']) == {7, 8}
