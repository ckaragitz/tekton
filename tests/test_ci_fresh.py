"""tools/dev/ci_fresh.sh -- a sandboxed-CI verdict is only valid against the `main` it was merged with (#487).

Incident #476: two PRs, each green against the origin/main of its own session_ci.sh run, collided semantically once
both landed. So session_ci.sh records that trunk as "main" in its one-line JSON, and the tick merges only when
ci_fresh.sh says FRESH against the origin/main re-fetched right before the merge. Tolerated drift = added/modified
docs/** that no shard test opens; the ledger/matrix/AUTONOMY docs, a docs deletion, a docs file added on main that
case-twins a path the PR adds (#496) are STALE; CODE drift is STALE -- and, only when the tech lead opted in with
CI_FRESH_JUDGE=1, handed to the disjoint-drift judge (tools/dev/ci_fresh_drift.py, #539), which may show from git objects
alone that main's change and the PR's are disjoint, uncoupled (no import, no name, no run-time-built or directory-walked
name either way), gate-free and merge-clean -> FRESH(disjoint drift).
Pinned here on a throwaway `git init` repo, plus the JSON field itself, the optional <head-sha> refusal, that every
awk on this machine gives the same quiet answer, that helper and judge stay on the trusted side, and (meta) that the
helper's SHARD_READS list still covers every docs/ path the real CI shard reads. Fresh-clone runnable: stdlib + git +
bash only (skips where bash or git is absent).
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import types

import pytest

from conftest import GIT_ENV, HAVE_GIT, ci_shard_files, git, git_commit, git_init, shard_reads_pattern

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, "tools", "dev", "ci_fresh.sh")
JUDGE = os.path.join(ROOT, "tools", "dev", "ci_fresh_drift.py")           # the disjoint-drift judge the helper hands code drift to (#539)...
CHECKER = os.path.join(ROOT, "tools", "dev", "check_portable_paths.py")   # ...the names-only gate both re-run at merge time (#522)...
SHARD_LIST = os.path.join(ROOT, "tools", "dev", "shard_list.py")          # ...and the drop-in law the judge loads by path
SESSION_CI = os.path.join(ROOT, "tools", "dev", "session_ci.sh")

pytestmark = pytest.mark.skipif(not (shutil.which("bash") and HAVE_GIT), reason="needs bash + git")

E40 = "e" * 40                       # a head SHA this clone has never seen
PR_ADDS = {"docs/inbox/foo.md": "f\n", "src/new.py": "n\n"}   # what the rig's PR 7 adds on top of origin/main


def _verdict(ci_dir, pr, **fields):
    with open(os.path.join(ci_dir, "%d.json" % pr), "w", encoding="utf-8") as fh:
        json.dump({"pr": pr, **fields}, fh)


def stale(was, now, changed, pr=7):
    """The standing gate's answer to code drift, byte-identical to before #539: exit 4, no reason, re-run."""
    return (4, "STALE was=%s now=%s changed=%s -> re-run tools/dev/session_ci.sh %d" % (was, now, changed, pr))


def stale_reason(result, was, now, changed, pr=7):
    """Assert `result` (rc, line) is the code-drift STALE line -- exit 4, `changed=` naming exactly `changed`, the re-run
    instruction last -- and return the parenthesised reason the disjoint-drift judge (#539) gave for not tolerating it."""
    rc, line = result
    head, tail = "STALE was=%s now=%s changed=%s (" % (was, now, changed), ") -> re-run tools/dev/session_ci.sh %d" % pr
    assert rc == 4 and line.startswith(head) and line.endswith(tail), result
    return line[len(head):-len(tail)]


@pytest.fixture
def rig(tmp_path):
    """An upstream repo + a clone of it that carries a COPY of the helper, of the disjoint-drift judge and of the checker
    they re-run at tools/dev/ (so the script's own `dirname $0/../..` resolution is what is tested), a real PR head in
    the clone (branch pr7 = origin/main + PR_ADDS, what session_ci.sh would have fetched as refs/pr/7) and a stored
    pass verdict for PR 7 against the clone's origin/main."""
    up, clone = git_init(str(tmp_path / "upstream")), str(tmp_path / "clone")
    git_commit(up, {"src/a.py": "a\n", "docs/x.md": "d\n", "docs/inbox/old.md": "o\n", "docs/coverage/viewer-certified.json": "{}\n"}, "one")
    git(tmp_path, "clone", "-q", up, clone)
    was = git(clone, "rev-parse", "origin/main")
    os.makedirs(os.path.join(clone, "tools", "dev"))
    for tool in (HELPER, JUDGE, CHECKER, SHARD_LIST):
        shutil.copy(tool, os.path.join(clone, "tools", "dev"))
    ci = os.path.join(clone, ".git", "session-ci", "ci")
    os.makedirs(ci)
    ns = types.SimpleNamespace(up=up, clone=clone, ci=ci, was=was, err=None)

    def pr(n, files, delete=(), base=None):
        """A PR head in the clone the way session_ci.sh leaves it (`base` -- default: the clone's ORIGINAL origin/main,
        `was`, whatever the helper has fetched since -- plus `files` minus `delete`; committed, not left checked out)
        and a stored pass verdict for it against `was` -> the head SHA."""
        git(clone, "switch", "-q", "-c", "pr%d" % n, base or was)
        head = git_commit(clone, files, "PR %d" % n, delete=delete)   # those paths only: the untracked helper copies never ride along
        git(clone, "switch", "-q", "--detach", was)
        _verdict(ci, n, head=head, main=was, verdict="pass")
        return head

    def fresh(*argv, path=None, env=None):
        env = dict(GIT_ENV, **(env or {}))
        if path:
            env["PATH"] = path
        out = subprocess.run(["bash", os.path.join(clone, "tools", "dev", "ci_fresh.sh"), *(map(str, argv or (7,)))],
                             cwd=clone, env=env, capture_output=True, text=True, timeout=60)
        ns.err = out.stderr
        return out.returncode, out.stdout.strip()

    def judged(*argv, path=None, env=None):
        """fresh() the way a tech lead who OPTED IN to the disjoint-drift judge runs it (CI_FRESH_JUDGE=1)."""
        return fresh(*argv, path=path, env=dict(env or {}, CI_FRESH_JUDGE="1"))
    ns.pr, ns.fresh, ns.judged = pr, fresh, judged
    ns.head = pr(7, PR_ADDS)
    return ns


def test_unchanged_main_is_fresh(rig):
    assert rig.fresh() == (0, "FRESH main=%s" % rig.was)
    assert rig.fresh(7, rig.head) == (0, "FRESH main=%s" % rig.was)     # with the expected head: same answer when it matches a pass


def test_docs_only_drift_is_fresh_and_says_so(rig):
    now = git_commit(rig.up, {"docs/x.md": "more\n", "docs/inbox/record.md": "new\n", "docs/STEERING.md": "| row |\n"}, "docs only")
    assert rig.fresh() == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))
    assert rig.err == ""


def test_code_drift_is_stale_names_the_first_three_paths_and_exits_4(rig):
    now = git_commit(rig.up, {"docs/x.md": "more\n", "src/a.py": "b\n", "tests/ci_shard.d/9-x.txt": "tests/test_b.py\n",
                           "tools/t.py": "t\n", "src/z.py": "z\n"}, "code moved under the verdict")
    assert rig.fresh() == stale(rig.was, now, "src/a.py,src/z.py,tests/ci_shard.d/9-x.txt,…")       # docs/x.md is not counted; 4 blocking paths -> 3 named + ellipsis
    reason = stale_reason(rig.judged(), rig.was, now, "src/a.py,src/z.py,tests/ci_shard.d/9-x.txt,…")  # opted in, the judge declines it too, saying why
    assert reason == "main's tests/ci_shard.d/9-x.txt enrols tests/test_b.py, a test main does not change (never run with the other side's change)"


READS = "main changes %s, a docs file the shard reads (SHARD_READS)"


@pytest.mark.parametrize("files,delete,blocking,reason", [
    ({"docs/coverage/viewer-certified.json": " \n"}, (), "docs/coverage/viewer-certified.json", READS),         # tests/test_router.py + test_probe_batch.py open the ledger
    ({"docs/product/PERMUTATION-MATRIX.md": "| cell |\n"}, (), "docs/product/PERMUTATION-MATRIX.md", READS),    # test_router.py compares the rendered matrix
    ({"docs/process/AUTONOMY.md": "words\n"}, (), "docs/process/AUTONOMY.md", READS),                           # test_techlead.py pins needles in it
    ({"docs/x.md": "more\n"}, ("docs/inbox/old.md",), "docs/inbox/old.md",
     "main deletes %s; deletions, renames and type changes are re-run, not judged"),                             # matrix.py cites records by existence: a deletion is drift
])
def test_docs_the_shard_reads_and_docs_deletions_are_stale(rig, files, delete, blocking, reason):
    now = git_commit(rig.up, files, "docs the gates can feel", delete=delete)
    assert rig.fresh() == stale(rig.was, now, blocking)
    assert stale_reason(rig.judged(), rig.was, now, blocking) == reason % blocking


# ---- code drift, OPT-IN: the disjoint-drift judge, tools/dev/ci_fresh_drift.py (#539) --------------------------------
# Every row below moves CODE on main under PR 7's verdict (PR 7 = docs/inbox/foo.md + src/new.py) and runs the helper
# the way a tech lead who exported CI_FRESH_JUDGE=1 does (rig.judged). The one shape the judge tolerates is pinned once
# (FRESH(disjoint drift), both counts named); every way the two changes could meet is pinned as STALE with the judge's
# own reason, so a rule quietly dropped from the judge turns a row red here; and without the variable the standing
# gate's byte-identical pre-#539 STALE line is pinned next to it.

def fresh_disjoint(was, now, nmain, npr, pr=7):
    """The one FRESH line the code-drift path can print: both non-docs file counts named."""
    return (0, "FRESH(disjoint drift) was=%s now=%s main=%d pr=%d (disjoint from the %d non-docs path%s PR %d changes: not imported or named "
               "either way, no gate touched, merge clean)" % (was, now, nmain, npr, npr, "" if npr == 1 else "s", pr))


def test_disjoint_uncoupled_clean_code_drift_is_fresh_and_names_both_counts(rig):
    """main gains a modified module, a new tool, a new test WITH the drop-in that enrols it, and docs; PR 7 touches none
    of them, imports none of them, names none of them, and merges clean: the one tolerated shape."""
    now = git_commit(rig.up, {"src/a.py": "A = 2\n", "tools/t.py": "import os\n", "tests/test_m.py": "import a\n",
                              "tests/ci_shard.d/12-m.txt": "# fresh-clone safe\ntests/test_m.py\n", "docs/x.md": "more\n"}, "disjoint code")
    assert rig.judged(7, rig.head) == fresh_disjoint(rig.was, now, 4, 1)
    assert rig.judged() == fresh_disjoint(rig.was, now, 4, 1)             # the head comes from the JSON either way
    assert rig.err == ""
    assert rig.fresh(7, rig.head) == stale(rig.was, now, "src/a.py,tests/ci_shard.d/12-m.txt,tests/test_m.py,…")   # the standing gate: not opted in, not judged


def test_the_judge_is_opt_in_and_a_built_name_reaches_only_what_its_repo_prefix_begins(rig):
    """Two edges of the same rule: only CI_FRESH_JUDGE=1 -- exactly -- hands code drift to the judge (anything else is
    the pre-#539 answer), and a name built at run time inside the rvt. namespace or under a tracked top-level directory
    couples a file only to what that literal prefix can reach (f"rvt.zz.{n}" and tools/*.py reach no src/a.py), so
    precision is pinned from the FRESH side too."""
    head = rig.pr(15, dict(PR_ADDS, **{"tools/dyn.py": 'import glob, importlib, os\nM = importlib.import_module(f"rvt.zz.{N}")\n'
                                                       'G = glob.glob(os.path.join(ROOT, "tools", "*.py"))\n'}))
    now = git_commit(rig.up, {"src/a.py": "A = 2\n"}, "code")
    assert rig.judged(15, head) == fresh_disjoint(rig.was, now, 1, 2, pr=15)
    for value in ("", "0", "yes", "true"):
        assert rig.fresh(15, head, env={"CI_FRESH_JUDGE": value}) == stale(rig.was, now, "src/a.py", pr=15), value


def test_a_path_changed_on_both_sides_is_stale(rig):
    head = rig.pr(8, {"src/a.py": "# PR side\n", "docs/inbox/eight.md": "e\n"})
    now = git_commit(rig.up, {"src/a.py": "# main side\n"}, "main edits the same module")
    assert stale_reason(rig.judged(8, head), rig.was, now, "src/a.py", pr=8) == "PR 8 also changes src/a.py"


@pytest.mark.parametrize("main_files,pr_files,reason", [
    ({"src/a.py": "A = 2\n"}, {"src/uses_a.py": "import os, a as alpha\n"},
     "PR 9's src/uses_a.py imports a (src/a.py), changed on main"),                                   # PR imports what main changed
    ({"tools/t.py": "from new import thing\n"}, {},
     "main's tools/t.py imports new (src/new.py), changed on PR 9"),                                   # ...and the reverse direction
    ({"src/pkg/__init__.py": "", "src/pkg/low.py": "LOW = 1\n"}, {"src/pkg/high.py": "from .low import LOW\n"},
     "PR 9's src/pkg/high.py imports pkg.low (src/pkg/low.py), changed on main"),                      # relative imports are resolved
    ({"src/pkg/__init__.py": "", "src/pkg/low.py": "LOW = 1\n"}, {"src/pkg/high.py": "from . import low\n"},
     "PR 9's src/pkg/high.py imports pkg.low (src/pkg/low.py), changed on main"),                      # `from . import mod` names the module...
    ({"src/pkg/__init__.py": "from .low import LOW\n", "src/pkg/low.py": "LOW = 1\n"}, {"src/user.py": "from pkg import LOW\n"},
     "PR 9's src/user.py imports pkg, on one import chain with pkg.low (src/pkg/low.py), changed on main"),   # ...a façade import names the whole package
    ({"tools/t.py": "T = 1\n"}, {"tests/test_t.py": 'from conftest import load_tool\nT = load_tool("t")\n'},
     "PR 9's tests/test_t.py names tools/t.py, changed on main"),                                      # loaded by bare name, not imported
    ({"src/pkg/__init__.py": "", "src/pkg/low.py": "LOW = 1\n"}, {"src/user.py": "from pkg import high, \\\n    low\n"},
     "PR 9's src/user.py imports pkg.low (src/pkg/low.py), changed on main"),                          # a backslash-continued list is read whole (ast) -- c3
    ({"src/pkg/__init__.py": "", "src/pkg/low.py": "LOW = 1\n"}, {"src/user.py": "import os; from pkg import low\nif os.sep:\n    pass\n"},
     "PR 9's src/user.py imports pkg.low (src/pkg/low.py), changed on main"),                          # a `;` chain on one line -- c4
    ({"src/pkg/__init__.py": "", "src/pkg/low.py": "LOW = 1\n"}, {"src/user.py": "if True: from pkg import low\n\ndef f():\n    import os\n"},
     "PR 9's src/user.py imports pkg.low (src/pkg/low.py), changed on main"),                          # an inline suite -- c4
    ({"src/a.py": "A = 2\n"}, {"tools/dyn.py": 'import importlib\nM = importlib.import_module(PREFIX + "a")\n'},
     "PR 9's tools/dyn.py builds or discovers names at run time (\"…\") that can reach src/a.py, changed on main"),   # a loader fed an expression reaches anything...
    ({"src/a.py": "A = 2\n"}, {"tools/dyn.py": 'import importlib\nM = importlib.import_module(name)\n'},
     "PR 9's tools/dyn.py builds or discovers names at run time (\"…\") that can reach src/a.py, changed on main"),   # ...fed a plain variable too (its literal may live in an unchanged caller)
    ({"tools/genesis_2031.py": "G = 1\n"}, {"tests/test_g.py": 'from conftest import load_tool\nYEAR = 2031\nNAME = "genesis_%d" % YEAR\nG = load_tool(NAME)\n'},
     "PR 9's tests/test_g.py builds or discovers names at run time (\"…\") that can reach tools/genesis_2031.py, changed on main"),   # a template outside the repo prefixes reaches anything
    ({"tools/t.py": "T = 1\n"}, {"tests/test_walk.py": 'import os\nfrom conftest import load_tool\nfor f in os.listdir(TOOLS):\n    n = f[:-3]\n    load_tool(n)\n'},
     "PR 9's tests/test_walk.py builds or discovers names at run time (\"…\") that can reach tools/t.py, changed on main"),   # a directory walk with no literal start reaches anything -- j3
    ({"tools/gen_x.py": "T = 1\n"}, {"tests/test_walk.py": 'import glob, os, subprocess, sys\nfor p in glob.glob(os.path.join(ROOT, "tools", "gen_*.py")):\n    subprocess.run([sys.executable, p])\n'},
     "PR 9's tests/test_walk.py builds or discovers names at run time (\"tools/gen_…\") that can reach tools/gen_x.py, changed on main"),   # ...one with a literal start reaches what it begins -- j4
    ({"tools/t.py": "T = 1\n"}, {"tests/test_spec.py": 'import importlib.util\nS = importlib.util.spec_from_file_location("mod", path)\n'},
     "PR 9's tests/test_spec.py builds or discovers names at run time (\"…\") that can reach tools/t.py, changed on main"),   # spec_from_file_location's PATH argument counts -- j5
    ({"tools/t.py": "T = 1\n"}, {"tests/test_spec.py": 'import importlib.util, os\nS = importlib.util.spec_from_file_location("mod", os.path.join(ROOT, "tools", "t.py"))\n'},
     "PR 9's tests/test_spec.py builds or discovers names at run time (\"tools/t.py…\") that can reach tools/t.py, changed on main"),   # ...narrowed to the path its literal pieces spell
])
def test_disjoint_but_coupled_changes_are_stale(rig, main_files, pr_files, reason):
    head = rig.pr(9, dict(PR_ADDS, **pr_files))
    now = git_commit(rig.up, main_files, "main side")
    assert stale_reason(rig.judged(9, head), rig.was, now, ",".join(sorted(main_files)), pr=9) == reason


@pytest.mark.parametrize("main_files,pr_files,reason", [
    ({"tests/conftest.py": "import os\n"}, {}, "main changes tests/conftest.py, a gate: shard machinery, a whole-tree checker or its law data"),
    ({"src/a.py": "A = 2\n"}, {"tests/ci_shard.txt": "tests/test_x.py\n"}, "PR 10 changes tests/ci_shard.txt, a gate: shard machinery, a whole-tree checker or its law data"),
    ({"tools/dev/session_ci.sh": "#\n"}, {}, "main changes tools/dev/session_ci.sh, a gate: shard machinery, a whole-tree checker or its law data"),
    ({"tools/sync_plugin.py": "#\n"}, {}, "main changes tools/sync_plugin.py, a gate: shard machinery, a whole-tree checker or its law data"),
    ({"src/a.py": "A = 2\n"}, {"tests/ci_shard.d/README": "words\n"}, "PR 10 changes tests/ci_shard.d/README, shard machinery"),
    ({"src/a.py": "A = 2\n"}, {"docs/coverage/viewer-certified.json": '{"x": 1}\n'}, "PR 10 changes docs/coverage/viewer-certified.json, a docs file the shard reads (SHARD_READS)"),
    ({"src/a.py": "A = 2\n"}, {"tests/ci_shard.d/10-x.txt": "tests/test_old.py\n"}, "PR 10's tests/ci_shard.d/10-x.txt enrols tests/test_old.py, a test PR 10 does not change (never run with the other side's change)"),
    ({"src/a.py": "A = 2\n"}, {"tests/pyproject.toml": "[tool.pytest.ini_options]\n"}, "PR 10 changes tests/pyproject.toml, a file pytest or the interpreter picks up by name, wherever it lies"),   # a nested inifile -- e4
    ({"src/a.py": "A = 2\n"}, {"tests/sub/__init__.py": ""}, "PR 10 changes tests/sub/__init__.py, a file pytest or the interpreter picks up by name, wherever it lies"),                     # rootdir/package discovery -- e5
    ({"tools/sitecustomize.py": "import os\n"}, {}, "main changes tools/sitecustomize.py, a file pytest or the interpreter picks up by name, wherever it lies"),
])
def test_gates_shard_reads_and_dropins_enrolling_unchanged_tests_are_stale_on_either_side(rig, main_files, pr_files, reason):
    head = rig.pr(10, dict(PR_ADDS, **pr_files))
    now = git_commit(rig.up, main_files, "main side")
    assert stale_reason(rig.judged(10, head), rig.was, now, ",".join(sorted(main_files)), pr=10) == reason


def test_symlinks_submodule_entries_oversized_files_and_a_non_sha_head_are_not_judged(rig):
    """Rule 2's other refusals: a symlink (mode 120000) or a gitlink (160000) is judged by its target by nobody; a file
    over the 2 MB the judge reads is not scanned; a recorded head that is not a 40-hex id (a ref name in the JSON) is
    not argued about even though git could resolve it -- m12, m2, h2."""
    git(rig.clone, "switch", "-q", "-c", "pr16", rig.was)              # PR 16 by hand: git_commit writes regular files only
    os.makedirs(os.path.join(rig.clone, "tests"))
    os.symlink("test_helper.py", os.path.join(rig.clone, "tests", "test_link.py"))
    git(rig.clone, "add", "--", "tests/test_link.py")
    git(rig.clone, "commit", "-qm", "PR 16: a symlinked test")
    head = git(rig.clone, "rev-parse", "HEAD")
    git(rig.clone, "switch", "-q", "--detach", rig.was)
    _verdict(rig.ci, 16, head=head, main=rig.was, verdict="pass")
    now = git_commit(rig.up, {"tools/t.py": "T = 1\n"}, "code")
    assert stale_reason(rig.judged(16, head), rig.was, now, "tools/t.py", pr=16) == "PR 16 changes tests/test_link.py, a symlink (mode 120000): only regular files are judged"
    git(rig.up, "update-index", "--add", "--cacheinfo", "160000,%s,vendor/sub" % rig.was)
    git(rig.up, "commit", "-qm", "a submodule entry")
    now = git(rig.up, "rev-parse", "HEAD")
    assert stale_reason(rig.judged(7, rig.head), rig.was, now, "tools/t.py,vendor/sub") == "main changes vendor/sub, a submodule entry (mode 160000): only regular files are judged"
    git(rig.up, "rm", "-q", "--cached", "vendor/sub")
    now = git_commit(rig.up, {"tools/big.py": "#" * 2_000_001}, "a dump, not a source file")
    assert stale_reason(rig.judged(7, rig.head), rig.was, now, "tools/big.py,tools/t.py") == "main's tools/big.py is 2000001 bytes, over the 2000000 this judge reads"
    _verdict(rig.ci, 18, head="HEAD", main=rig.was, verdict="pass")     # git resolves "HEAD" happily; the judge must not
    assert stale_reason(rig.judged(18), rig.was, now, "tools/big.py,tools/t.py", pr=18) == "the recorded head 'HEAD' is not a 40-hex commit id"


def test_deletions_and_renames_on_either_side_are_stale_both_names_counted(rig):
    """--no-renames: a rename is a deletion plus an addition, so both its names are in the set -- and the deletion half
    alone makes it STALE (a vanished path can be reached through a name computed at run time)."""
    git(rig.up, "mv", "src/a.py", "src/b.py")
    git(rig.up, "commit", "-qm", "main renames a module")
    now = git(rig.up, "rev-parse", "HEAD")
    assert stale_reason(rig.judged(7, rig.head), rig.was, now, "src/a.py,src/b.py") == "main deletes src/a.py; deletions, renames and type changes are re-run, not judged"
    head = rig.pr(11, {"docs/inbox/renamed.md": "o\n"}, delete=("docs/inbox/old.md",))
    now = git_commit(rig.up, {"tools/t.py": "T = 1\n"}, "and some code")
    assert stale_reason(rig.judged(11, head), rig.was, now, "src/a.py,src/b.py,tools/t.py", pr=11) == "main deletes src/a.py; deletions, renames and type changes are re-run, not judged"
    _verdict(rig.ci, 11, head=head, main=now, verdict="pass")           # re-run against that main: now only the PR's own rename is left to object to
    later = git_commit(rig.up, {"tools/u.py": "U = 1\n"}, "more code")
    assert stale_reason(rig.judged(11, head), now, later, "tools/u.py", pr=11) == "PR 11 deletes docs/inbox/old.md; deletions, renames and type changes are re-run, not judged"


def test_merge_conflicts_are_stale_even_between_disjoint_or_docs_only_sets(rig):
    """Disjoint path SETS can still collide in the merge (a file where the other side needs a directory), and docs set
    aside as inert can still conflict textually (the same record edited on both sides): merge-tree says so, from objects."""
    head = rig.pr(12, {"lib/x.py": "X = 1\n", "docs/x.md": "PR's words\n"})
    now = git_commit(rig.up, {"lib": "a file where the PR has a directory\n"}, "file vs directory")
    assert stale_reason(rig.judged(12, head), rig.was, now, "lib", pr=12).startswith("merging PR 12 into origin/main conflicts on lib~")   # git parks the file as lib~<side>
    head = rig.pr(13, {"docs/x.md": "PR's words\n"})
    now = git_commit(rig.up, {"docs/x.md": "main's words\n", "tools/t.py": "T = 1\n"}, "the same doc, differently", delete=("lib",))
    assert stale_reason(rig.judged(13, head), rig.was, now, "tools/t.py", pr=13) == "merging PR 13 into origin/main conflicts on docs/x.md"


def test_a_case_twin_across_the_two_sides_of_code_drift_is_stale_by_the_checker_itself(rig):
    """git merges src/NEW.py (main) and src/new.py (PR 7) without a word; tools/dev/check_portable_paths.py over the
    MERGED tree's names does not -- the same law the docs-only path applies, felt on the code path."""
    now = git_commit(rig.up, {"src/NEW.py": "TWIN = 1\n", "tools/t.py": "T = 1\n"}, "a twin of the PR's module")
    assert stale_reason(rig.judged(7, rig.head), rig.was, now, "src/NEW.py,tools/t.py") == \
        "tools/dev/check_portable_paths.py rejects the merged tree: case-only collision (breaks case-insensitive filesystems): ['src/NEW.py', 'src/new.py']"


def test_more_than_200_changed_paths_a_side_are_not_judged(rig):
    now = git_commit(rig.up, {"gen/f%03d.txt" % i: "x\n" for i in range(201)}, "a big sweep")
    assert stale_reason(rig.judged(7, rig.head), rig.was, now, "gen/f000.txt,gen/f001.txt,gen/f002.txt,…") == "main changes more than 200 paths, over what this judge reads"


def test_a_head_based_past_the_recorded_main_or_missing_here_is_stale(rig):
    """Shape: the judge only argues about a head whose merge base is at or below the recorded main (what session_ci
    really merged); and code drift with a head this clone never fetched cannot be judged at all -- both STALE."""
    now = git_commit(rig.up, {"tools/t.py": "T = 1\n"}, "code")
    git(rig.clone, "fetch", "-q")
    head = rig.pr(14, {"src/late.py": "L = 1\n"}, base="origin/main")   # branched from the NEW origin/main, verdict recorded against the old one
    reason = stale_reason(rig.judged(14, head), rig.was, now, "tools/t.py", pr=14)
    assert reason.startswith("PR 14's merge base ") and reason.endswith(" is not an ancestor of the recorded main (head rebased past the run)")
    _verdict(rig.ci, 17, head=E40, main=rig.was, verdict="pass")
    assert stale_reason(rig.judged(17), rig.was, now, "tools/t.py", pr=17) == "the recorded head %s is not a commit in this clone, so PR 17's own change cannot be read" % E40[:12]


def shim_path(where, exe, refuse, action):
    """A PATH string that puts a shim of `exe` first: it runs the shell snippet `action` (say something on stderr and
    exit, or sleep) when any argument matches the shell pattern `refuse`, and hands everything else to the real program."""
    where.mkdir(exist_ok=True)
    shim = where / exe
    shim.write_text('#!/bin/sh\nfor a in "$@"; do case "$a" in %s) %s;; esac; done\nexec "%s" "$@"\n' % (refuse, action, shutil.which(exe)))
    shim.chmod(0o755)
    return str(where) + os.pathsep + os.environ.get("PATH", "")


@pytest.mark.parametrize("exe,refuse,action,line", [
    ("python3", "*/ci_fresh_drift.py", 'echo "shim says no" >&2; exit 1',
     "cannot judge PR 7: the disjoint-drift judge failed (rc=1; was=%(was)s now=%(now)s changed=tools/t.py)"),        # the judge's interpreter dies: no payload
    ("python3", "*/ci_fresh_drift.py", 'sleep 5',
     "cannot judge PR 7: the disjoint-drift judge failed (rc=124; was=%(was)s now=%(now)s changed=tools/t.py)"),      # ...or outlives its budget (CI_FRESH_JUDGE_TIMEOUT=1 below): timeout's 124
    ("git", "merge-tree", 'echo "shim says no" >&2; exit 129',
     "cannot judge PR 7: git merge-tree --write-tree failed (129) -- `git merge-tree --write-tree` needs git >= 2.38: "
     "shim says no (was=%(was)s now=%(now)s changed=tools/t.py)"),                                                     # a git too old for --write-tree (usage = 129)
    ("git", "--is-ancestor", 'echo "shim says no" >&2; exit 128',
     "cannot judge PR 7: git merge-base %(was)s failed"),                                                             # git failing under the helper's own ancestry check
    ("git", "--all", 'echo "shim says no" >&2; exit 128',
     "cannot judge PR 7: git merge-base --all failed (128): shim says no (was=%(was)s now=%(now)s changed=tools/t.py)"),   # any other git failure under the judge
])
def test_the_judge_fails_closed_when_git_or_its_interpreter_fails_or_stalls(rig, tmp_path, exe, refuse, action, line):
    """cannot judge (exit 2), never FRESH -- with the reason on the one line the tick posts."""
    now = git_commit(rig.up, {"tools/t.py": "T = 1\n"}, "code")
    assert rig.judged(7, rig.head) == fresh_disjoint(rig.was, now, 1, 1)              # the ground truth for this drift
    got = rig.judged(7, rig.head, path=shim_path(tmp_path / "shim", exe, refuse, action), env={"CI_FRESH_JUDGE_TIMEOUT": "1"})
    assert got == (2, (line % {"was": rig.was, "now": now}).replace("merge-base %s failed" % rig.was, "merge-base %s %s failed" % (rig.was, now)))


def test_a_rewritten_trunk_is_stale_even_when_the_difference_is_docs_only(rig):
    """Drift is was..now only while origin/main still DESCENDS from the recorded main: an amended/rewritten trunk whose
    tree differs by nothing but a record is not "docs-only drift" -- the run merged with a commit that no longer leads
    to main. STALE, on the standing gate, no judge involved."""
    with open(os.path.join(rig.up, "docs", "inbox", "later.md"), "w", encoding="utf-8") as fh:
        fh.write("a record\n")
    git(rig.up, "add", "--", "docs/inbox/later.md")
    git(rig.up, "commit", "-q", "--amend", "--no-edit")
    now = git(rig.up, "rev-parse", "HEAD")
    assert rig.fresh(7, rig.head) == (4, "STALE was=%s now=%s changed=? (%s is not an ancestor of origin/main: main rewritten under the verdict) -> re-run tools/dev/session_ci.sh 7" % (rig.was, now, rig.was))
    assert rig.err == ""


TWIN_LINE = ("STALE was=%s now=%s changed=%s (added on main; PR 7 adds the same name or a case-twin of it: an add/add conflict or a "
             "portable_paths failure after the merge) -> re-run tools/dev/session_ci.sh 7")


@pytest.mark.parametrize("added", ["docs/inbox/Foo.md", "docs/inbox/FOO.MD", "docs/inbox/foo.md"])
def test_a_docs_file_added_on_main_that_case_twins_a_pr_added_path_is_stale(rig, added):
    """#496: case-only twins are the one CROSS-FILE law of tools/dev/check_portable_paths.py, so `main` adding
    docs/inbox/Foo.md while the PR adds docs/inbox/foo.md reddens portable_paths only after the merge -- the verdict
    computed against the older main cannot have seen it. (The very same name is an add/add conflict: not mergeable on
    the old verdict either.) Other docs adds in the same drift stay tolerated and unnamed."""
    now = git_commit(rig.up, {added: "twin\n", "docs/inbox/record.md": "new\n", "docs/x.md": "more\n"}, "main adds a twin of the PR's docs/inbox/foo.md")
    assert rig.fresh(7, rig.head) == (4, TWIN_LINE % (rig.was, now, added))
    assert rig.err == ""


def test_docs_added_on_main_with_a_head_this_clone_lacks_fail_closed_but_modified_docs_need_no_head(rig):
    _verdict(rig.ci, 17, head=E40, main=rig.was, verdict="pass")        # a JSON whose head was never fetched here
    now = git_commit(rig.up, {"docs/x.md": "more\n"}, "docs modified only")
    assert rig.fresh(17) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))   # a MODIFIED docs file existed at `was`: session_ci already saw its name
    now = git_commit(rig.up, {"docs/inbox/record.md": "new\n", "docs/inbox/note.md": "n\n"}, "docs added")
    assert rig.fresh(17) == (4, 'STALE was=%s now=%s changed=docs/inbox/note.md,docs/inbox/record.md (main added docs files and the recorded head "%s" '
                             'is not a commit in this clone, so a collision with a path PR 17 adds cannot be ruled out) -> re-run tools/dev/session_ci.sh 17' % (rig.was, now, E40))
    assert rig.fresh(7) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))    # the same drift with a known head: no twin, tolerated


def test_the_collision_check_fails_closed_when_its_interpreter_fails(rig, tmp_path):
    """A merge gate never reads "the check crashed" as "no collision": if the python3 behind the collision check fails
    (the review forced it with an argv above 128 KiB; the names are now read from git -z plumbing inside the program,
    and any other failure -- a git call, the checker import -- lands here), the answer is "cannot judge", exit 2 --
    not FRESH. A python3 shim that dies only for that one program (the one handed tools/dev/check_portable_paths.py,
    #522) proves it; the JSON read before it goes through the real interpreter."""
    path = shim_path(tmp_path / "py-shim", "python3", "*/check_portable_paths.py", 'echo "shim: refusing the collision check" >&2; exit 1')
    now = git_commit(rig.up, {"docs/inbox/Foo.md": "twin\n"}, "main adds a twin")
    assert rig.fresh(7, rig.head) == (4, TWIN_LINE % (rig.was, now, "docs/inbox/Foo.md"))          # the real interpreter sees it
    assert rig.fresh(7, rig.head, path=path) == (2, "cannot judge PR 7: the collision check against the names PR 7 adds failed")
    assert "shim: refusing" in rig.err
    now = git_commit(rig.up, {"docs/x.md": "more\n"}, "and a modified doc", delete=("docs/inbox/Foo.md",))
    assert rig.fresh(7, rig.head, path=path) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))   # no docs ADD left in was..now: the check is not needed, the shim never fires


@pytest.mark.skipif(sys.platform == "win32", reason="a file named aux.md cannot be created on Windows -- that is the law being felt")
def test_the_merge_time_gate_is_the_checker_itself_not_a_rederived_twin_law(rig):
    """#522: once main added docs files, the helper re-runs tools/dev/check_portable_paths.py's own check() over the
    post-merge name set instead of comparing lower-cased names inline. Fingerprint: a reserved device name has
    nothing to do with case twins, yet a PR adding docs/aux.md is refused with the checker's own problem line the
    moment main adds any docs file (a real pass verdict cannot carry such a name -- session_ci.sh ran the same checker
    over it -- so this row proves which code judges, and fails closed should a JSON ever lie). Modified docs alone
    change no name, so they re-run nothing; a PR whose names are clean stays FRESH under the very same drift."""
    head = rig.pr(8, {"docs/aux.md": "x\n"})
    now = git_commit(rig.up, {"docs/x.md": "more\n"}, "docs modified only")
    assert rig.fresh(8, head) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))
    now = git_commit(rig.up, {"docs/inbox/record.md": "new\n"}, "a record added on main")
    assert rig.fresh(8, head) == (4, "STALE was=%s now=%s changed=docs/aux.md (tools/dev/check_portable_paths.py rejects the post-merge name set: "
                                    "reserved device name on Windows: 'docs/aux.md') -> re-run tools/dev/session_ci.sh 8" % (rig.was, now))
    assert rig.fresh(7, rig.head) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))
    assert rig.err == ""


@pytest.mark.skipif(sys.platform == "win32", reason="a file named ' ' cannot exist on Windows")
def test_a_blocking_path_whose_name_is_all_blanks_is_still_named_and_stale(rig):
    """The join helper counts lines by length, not awk NF: a top-level file literally named " " is untolerated drift
    and must keep main's answer (STALE, the blank name after changed=), never vanish into FRESH(docs-only drift)."""
    now = git_commit(rig.up, {" ": "z\n", "docs/x.md": "more\n"}, "a file named blank")
    assert rig.fresh() == stale(rig.was, now, " ")
    assert stale_reason(rig.judged(), rig.was, now, " ") == "main changes a path this judge does not argue about: ' '"   # and the opt-in judge refuses to reason about such a name


@pytest.mark.parametrize("flavour", [pytest.param(f, marks=pytest.mark.skipif(not shutil.which(f), reason="%s is not installed on this machine" % f))
                                     for f in ("mawk", "gawk", "busybox")])
def test_every_installed_awk_gives_the_same_quiet_answers(rig, tmp_path, flavour):
    """#496: gawk warns on stderr about `\\.` inside a -v string and degrades it to `.`; mawk keeps it literal. The
    helper's regexes must mean the same thing, silently, under whichever awk is /usr/bin/awk on the tech lead's box.
    Runs once per awk flavour installed here (the others are reported as skips, so the CI summary says what was covered)."""
    shim = tmp_path / ("awk-" + flavour)
    shim.mkdir()
    (shim / "awk").symlink_to(shutil.which(flavour))                    # busybox, too: it picks the applet from argv[0]'s basename
    path = str(shim) + os.pathsep + os.environ.get("PATH", "")
    # a near-miss of a SHARD_READS name (any character where the literal dot must be) is plain tolerated docs drift...
    now = git_commit(rig.up, {"docs/product/PERMUTATION-MATRIX-md": "x\n", "docs/process/AUTONOMY_md": "x\n", "docs/x.md": "more\n"}, "near misses")
    assert rig.fresh(path=path) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now)), flavour
    assert rig.err == "", (flavour, rig.err)
    # ...the real name is not, and the blocking list is joined the same way
    now = git_commit(rig.up, {"docs/product/PERMUTATION-MATRIX.md": "| cell |\n", "src/a.py": "b\n", "src/b.py": "b\n", "src/c.py": "c\n"}, "the real thing")
    assert rig.fresh(path=path) == stale(rig.was, now, "docs/product/PERMUTATION-MATRIX.md,src/a.py,src/b.py,…"), flavour
    assert rig.err == "", (flavour, rig.err)


def test_missing_or_pre_487_json_exits_3_and_bad_usage_2(rig):
    rc, line = rig.fresh(8)                                             # no run stored for this PR
    assert rc == 3 and line.startswith("MISSING ") and "8.json" in line
    _verdict(rig.ci, 9, head=E40, verdict="pass")                       # a verdict written before session_ci.sh recorded "main"
    rc, line = rig.fresh(9)
    assert rc == 3 and line.startswith('MISSING "main"'), line
    with open(os.path.join(rig.ci, "5.json"), "w", encoding="utf-8") as fh:
        fh.write("not json\n")                                          # a truncated/garbled result file is MISSING too, never FRESH
    assert rig.fresh(5)[0] == 3
    assert rig.fresh("7x")[0] == 2


def test_expected_head_refuses_a_json_for_another_head_or_a_non_pass(rig):
    rc, line = rig.fresh(7, "f" * 40)
    assert rc == 5 and line.startswith("WRONG-HEAD json=%s now=%s" % (rig.head, "f" * 40)), line
    _verdict(rig.ci, 4, head=E40, main=rig.was, verdict="fail")
    assert rig.fresh(4) == (0, "FRESH main=%s" % rig.was)               # without a head the helper judges main only (the tick read the verdict itself)
    rc, line = rig.fresh(4, E40)
    assert rc == 5 and line.startswith("NOT-PASS verdict=fail"), line


def test_unknown_recorded_main_fails_closed(rig):
    """A `main` this clone has never seen (trunk rewritten, or a JSON copied from another checkout) cannot be diffed:
    that is STALE, never FRESH."""
    _verdict(rig.ci, 6, head=E40, main="1" * 40, verdict="pass")
    rc, line = rig.fresh(6)
    assert rc == 4 and line.startswith("STALE was=%s now=" % ("1" * 40)) and "changed=?" in line


def test_session_ci_records_the_main_it_merged_and_the_helper_stays_trusted_side():
    # session_ci.sh's other needles (sandbox, locks, shard reader, the merge with "$MAIN") are pinned in tests/test_techlead.py
    src = open(SESSION_CI, encoding="utf-8").read()
    assert src.index('HEAD=$(git rev-parse "refs/pr/$PR")') < src.index("MAIN=$(git rev-parse --verify -q origin/main)") < src.index("git worktree add --detach")   # captured with the head, before the merge test
    assert 'rev-list --count "HEAD..$MAIN"' in src and 'merge --no-edit "$MAIN"' in src                                     # merged with the sha it records, not the ref name
    assert '"$HEAD" "$MAIN" "$MERGE"' in src and '"head":head,"main":main,' in src                                          # emitted right after "head"
    header = src.split("\nset -uo pipefail")[0]
    assert src.count('\\"error\\":\\"') == 6, "session_ci.sh gained or lost a setup-failure exit: name it in its header comment and adjust this pin"
    for reason in ("no ref", "no origin/main", "worktree", "tree export", "lock"):   # every setup failure it can emit is named where the tick reads about them (#496)
        assert reason in header, reason
    helper = open(HELPER, encoding="utf-8").read()
    assert os.access(HELPER, os.X_OK) and helper.startswith("#!/usr/bin/env bash")
    assert "SESSION_CI_DIR:-$REPO/.git/session-ci" in helper and "SESSION_CI_DIR:-$REPO/.git/session-ci" in src           # one scratch layout, two readers
    for needle in ("git checkout", "git switch", "worktree add", "pytest", "refs/pr/", "cat-file -p", "cat-file blob", "git show", "git archive"):
        assert needle not in helper, needle          # it never touches PR code: our own JSON + git plumbing (names, never contents) only...
    assert 'python3 -IB "$REPO/tools/dev/ci_fresh_drift.py"' in helper                    # ...and hands code drift to THIS checkout's judge, which
    judge = open(JUDGE, encoding="utf-8").read()                                             # READS blob text as data (cat-file --batch); same deny-list, minus its one loader:
    code = "\n".join(ln.split("  # ")[0] for ln in re.sub(r'"""[\s\S]*?"""', '""', judge).splitlines() if not ln.lstrip().startswith("#")).replace("spec.loader.exec_module(module)", "")
    for needle in ("checkout", "switch", "worktree", "-m pytest", "pytest.main", "git show", "archive", "exec(", "eval(", " compile(", "os.system", "shell=True", "import_module(", "sys.path"):
        assert needle not in code, needle
    assert 'os.path.join(HERE, name + ".py")' in code and sorted(re.findall(r'trusted\("(\w+)"\)', code)) == ["check_portable_paths", "shard_list"]   # the only code it loads: two trusted neighbours, by path
    assert r"\." not in _portable_ere()              # [.] is the portable literal dot inside an awk -v string (gawk degrades \. to . with a warning)


def test_every_gate_the_judge_names_exists_and_everything_session_ci_executes_is_a_gate():
    """GATES/GATE_DIRS in the judge are a hand list, and a stale entry fails OPEN (a renamed checker would silently stop
    being a gate). So: every named gate is a tracked path (or a prefix of one), every file tools/dev/session_ci.sh
    executes -- this checkout's trusted helpers and the whole-tree steps it runs on the PR (`step <name> "$PY" <path>`)
    -- is a gate, and the drop-in law is shard_list.py's own (loaded, not copied)."""
    from conftest import load_tool
    judge_mod, tracked = load_tool("dev/ci_fresh_drift"), set(git(ROOT, "ls-files").splitlines())
    assert not [g for g in judge_mod.GATES if g not in tracked], [g for g in judge_mod.GATES if g not in tracked]
    assert all(any(t.startswith(d) for t in tracked) for d in judge_mod.GATE_DIRS), judge_mod.GATE_DIRS
    src = open(SESSION_CI, encoding="utf-8").read()
    executed = set(re.findall(r'\$REPO/(tools/[\w./-]+\.(?:py|sh))', src)) | set(re.findall(r'step \w+ "\$PY" ([\w./-]+\.py)', src))
    assert {"tools/dev/check_portable_paths.py", "tools/dev/shard_list.py", "tools/sync_plugin.py", "plugin/scripts/validate_plugin.py"} <= executed   # the scrape still sees them
    assert executed <= judge_mod.GATES, executed - judge_mod.GATES
    assert {"tools/dev/session_ci.sh", "tools/dev/ci_fresh.sh", "tools/dev/ci_fresh_drift.py", "tests/conftest.py", "tests/ci_shard.txt"} <= judge_mod.GATES
    assert judge_mod.SHARD is None and "DROPIN_NAME" not in vars(judge_mod)                # no private copy of the drop-in law: it comes from shard_list.py at run time


# ---- meta: SHARD_READS must cover every docs/ path the real CI shard reads (#496) --------------------------------------

def _portable_ere():
    """The helper's SHARD_READS ERE (conftest lifts it out of the script itself: one source of truth). It is run below as
    a Python `re`, so it must stay inside the subset both dialects read the same way (anchors, groups, alternation, [.] classes)."""
    pattern = shard_reads_pattern()
    assert re.fullmatch(r"[\w/^$|()\[\].-]+", pattern), pattern
    return pattern


# Shard files whose code NAMES repo docs/ paths without reading them, and why -- they are still checked for what they
# pass to open()/read_text(), so the excuse covers naming, never opening. Keep it tiny: the point of the meta-test is
# that a new docs/ reader in the shard forces a decision (SHARD_READS in the helper, or a line here). This file is one
# by construction: the scanner's fixtures and the rig's committed file names ARE docs/ paths.
NAMES_NOT_READS = {
    "tests/test_ci_fresh.py": "the instrument itself: scanner fixtures + names committed to throwaway repos in tmp_path",
}
OPENERS = {"open", "read_text", "read_bytes"}


class _DocsRefs(ast.NodeVisitor):
    """Collect every docs/ path a module's CODE names as a path: whole string constants without whitespace that contain
    `docs/` (also inside f-strings), and `docs` as one component of a join-like run of constant call arguments or
    `/`/`+` operands (os.path.join(ROOT, "docs", "x.md"), ROOT / "docs" / name). Prose (docstrings, messages with
    spaces, comments) never counts: a sentence cannot be opened. -> .refs = {(path, dynamic)}, dynamic = a computed
    part follows the literal one, so only a directory prefix of the real path is known.
    opens_only: collect nothing except inside the arguments (and receiver) of open()/read_text()/read_bytes() calls."""

    def __init__(self, opens_only=False):
        self.refs, self.opens_only = set(), opens_only

    def _text(self, s, dynamic=False):
        if "docs/" in s and not any(c.isspace() for c in s):
            tail = s[s.index("docs/"):]
            lit = re.match(r"docs/[A-Za-z0-9_.\-/]*", tail).group(0)
            self.refs.add((lit, dynamic or len(lit) < len(tail) or lit.endswith("/")))   # a %s / {} after the literal part, or a bare "dir/", = computed tail

    def _seq(self, seq):
        """Operands of one join-like run: `docs` starting a stretch of string constants -> one reference; the rest is visited."""
        strs = [n.value.strip("/") if isinstance(n, ast.Constant) and isinstance(n.value, str) else "" for n in seq]
        i = 0
        while i < len(seq):
            if not self.opens_only and (strs[i] == "docs" or strs[i].startswith("docs/")):
                j = i + 1
                while j < len(seq) and strs[j]:
                    j += 1
                self.refs.add(("/".join(strs[i:j]), j < len(seq)))
                i = j
            else:
                self.visit(seq[i])
                i += 1

    def _skip_docstring(self, node):
        doc = node.body[0] if ast.get_docstring(node, clean=False) is not None else None
        for child in ast.iter_child_nodes(node):
            if child is not doc:
                self.visit(child)

    visit_Module = visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = _skip_docstring

    def visit_Constant(self, node):
        if isinstance(node.value, str) and not self.opens_only:
            self._text(node.value)

    def visit_JoinedStr(self, node):
        for i, part in enumerate(node.values):
            if not isinstance(part, ast.Constant):
                self.visit(part)
            elif isinstance(part.value, str) and not self.opens_only:
                self._text(part.value, dynamic=i + 1 < len(node.values))

    def visit_Call(self, node):
        f = node.func
        if self.opens_only and (f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")) in OPENERS:
            inner = _DocsRefs()
            inner._seq([*node.args, *([f.value] if isinstance(f, ast.Attribute) else [])])
            self.refs |= inner.refs
        self.visit(f)
        self._seq(node.args)
        for kw in node.keywords:
            self.visit(kw.value)

    def visit_BinOp(self, node):
        if not isinstance(node.op, (ast.Div, ast.Add)):
            return self.generic_visit(node)
        seq, cur = [], node
        while isinstance(cur, ast.BinOp) and isinstance(cur.op, type(node.op)):   # the whole left-leaning chain at once, so sub-chains are not re-read as shorter paths
            seq.insert(0, cur.right)
            cur = cur.left
        self._seq([cur, *seq])


def _reads(path, dynamic, tracked):
    """The tracked files a reference can read: the file itself, everything under it if it is a directory, or -- for a
    computed reference whose literal part is not a whole name -- everything under its nearest existing directory.
    A fully literal path that does not exist is fiction (fixture names, examples): it reads nothing."""
    p = path.rstrip("/")
    while True:
        if p in tracked:
            return [p]
        under = sorted(t for t in tracked if t.startswith(p + "/"))
        if under or not dynamic or "/" not in p:
            return under
        p = p.rsplit("/", 1)[0]


def test_the_docs_reference_scanner_sees_paths_and_ignores_prose():
    src = '''"""module docstring naming docs/process/AUTONOMY.md is prose"""
import os
LEDGER = os.path.join(ROOT, "docs", "coverage", "viewer-certified.json")
DOC = ROOT / "docs" / "product" / name
def f():
    """docs/inbox/x.md in a docstring"""
    _need("docs/a.json"); g(f"{ROOT}/docs/inbox/{slug}.md"); h("%s/docs/writer/notes.md" % ROOT); k(ROOT + "/docs/z/" + n)
    pytest.skip(reason="pending (docs/writer/plan.md) flips it")   # a sentence: not a path
'''
    v = _DocsRefs()
    v.visit(ast.parse(src))
    assert v.refs == {("docs/coverage/viewer-certified.json", False), ("docs/product", True), ("docs/a.json", False),
                      ("docs/inbox/", True), ("docs/writer/notes.md", False), ("docs/z", True)}
    v = _DocsRefs(opens_only=True)
    v.visit(ast.parse(src + '''    names = ["docs/STEERING.md", os.path.join(ROOT, "docs", "x.md")]      # named, not opened
    text = open(os.path.join(ROOT, "docs", "PROGRAM.md")).read() + (ROOT / "docs" / "product" / n).read_text() + json.load(open(f"{ROOT}/docs/j.json"))
'''))
    assert v.refs == {("docs/PROGRAM.md", False), ("docs/product", True), ("docs/j.json", False)}
    tracked = {"docs/inbox/a.md", "docs/inbox/b.md", "docs/x.md", "docs/coverage/l.json"}
    assert _reads("docs/inbox/", True, tracked) == ["docs/inbox/a.md", "docs/inbox/b.md"]          # a computed name under a real directory reads the directory
    assert _reads("docs/inbox/learned-", True, tracked) == ["docs/inbox/a.md", "docs/inbox/b.md"]  # partial literal name: nearest existing directory
    assert _reads("docs/inbox/zz.md", False, tracked) == [] and _reads("docs/nope/", True, tracked) == sorted(tracked)   # fiction reads nothing; an unknown computed dir escalates to its parent
    assert _reads("docs/x.md", False, tracked) == ["docs/x.md"] and _reads("docs", False, tracked) == sorted(tracked)


def test_SHARD_READS_covers_every_docs_path_the_ci_shard_reads():
    """The helper tolerates added/modified docs/** drift EXCEPT the docs files shard tests open for content
    (SHARD_READS). That list is hand-written; this keeps it true: every docs/ path named as a path by the code of any
    file in the merged CI shard (tests/ci_shard.txt + tests/ci_shard.d/*.txt, exactly what session_ci.sh runs) or by
    the tests/ helpers they import must fall under SHARD_READS -- otherwise a docs-only merge touching that file
    between a PR's CI run and its merge is the #476 shape again and the helper would call it FRESH.
    Ways out when this fails: the test really reads that file -> add it to SHARD_READS in tools/dev/ci_fresh.sh (and a
    STALE row above); the file only names docs paths (fixtures, examples) -> NAMES_NOT_READS, saying why -- it is then
    still held to what it hands to open()/read_text(). Blind spot, stated: a docs read hidden inside src/ or tools/
    code a test merely calls is not seen here (today those are the ledger via matrix.py/census.py -- covered -- and
    matrix.py's existence-only record citations, which is why a docs DELETION is never tolerated drift)."""
    shard = ci_shard_files()
    helpers = sorted("tests/" + n for n in os.listdir(os.path.join(ROOT, "tests")) if n.endswith(".py") and not n.startswith("test_"))
    reads = re.compile(_portable_ere())
    tracked = set(git(ROOT, "ls-files", "--", "docs").splitlines())
    assert len(shard) > 40 and "tests/test_router.py" in shard and len(tracked) > 50          # the instrument is looking at the real thing
    assert set(NAMES_NOT_READS) <= set(shard + helpers), "NAMES_NOT_READS excuses a file that is not in the shard any more"
    offenders, readers = {}, set()
    for rel in shard + helpers:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            text = fh.read()
        if "docs" not in text:                                       # no such substring, no possible reference: skip the parse
            continue
        v = _DocsRefs(opens_only=rel in NAMES_NOT_READS)
        v.visit(ast.parse(text, rel))
        for path, dynamic in sorted(v.refs):
            hit = _reads(path, dynamic, tracked)
            uncovered = [t for t in hit if not reads.match(t)]
            if hit:
                readers.add(rel)
            if uncovered:
                offenders[(rel, path)] = uncovered[:3] + (["… (%d files)" % len(uncovered)] if len(uncovered) > 3 else [])
    assert not offenders, ("shard tests name docs/ paths that tools/dev/ci_fresh.sh SHARD_READS does not cover, so a docs-only merge touching them "
                           "between a PR's CI run and its merge would wrongly stay FRESH: %r -- add them to SHARD_READS (the test reads them), "
                           "or the file to NAMES_NOT_READS here (it only names them), saying why" % offenders)
    assert {"tests/test_router.py", "tests/test_probe_batch.py", "tests/test_techlead.py"} <= readers, readers   # the known readers are still seen: the scanner did not go blind
