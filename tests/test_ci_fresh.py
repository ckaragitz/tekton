"""tools/dev/ci_fresh.sh -- a sandboxed-CI verdict is only valid against the `main` it was merged with (#487).

Incident #476: two PRs, each green against the origin/main of its own session_ci.sh run, collided semantically once
both landed. So session_ci.sh records that trunk as "main" in its one-line JSON, and the tick merges only when
ci_fresh.sh says FRESH against the origin/main re-fetched right before the merge. Tolerated drift = added/modified
docs/** that no shard test opens; everything else (code, the ledger/matrix/AUTONOMY docs, a docs deletion, a docs
file added on main that case-twins a path the PR adds -- #496) is STALE.
Pinned here on a throwaway `git init` repo, plus the JSON field itself, the optional <head-sha> refusal, that every
awk on this machine gives the same quiet answer, and (meta) that the helper's SHARD_READS list still covers every
docs/ path the real CI shard reads. Fresh-clone runnable: stdlib + git + bash only (skips where bash or git is absent).
"""
import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, "tools", "dev", "ci_fresh.sh")
CHECKER = os.path.join(ROOT, "tools", "dev", "check_portable_paths.py")   # the names-only gate the helper re-runs at merge time (#522)
SESSION_CI = os.path.join(ROOT, "tools", "dev", "session_ci.sh")
SHARD_LIST = os.path.join(ROOT, "tools", "dev", "shard_list.py")

pytestmark = pytest.mark.skipif(not (shutil.which("bash") and shutil.which("git")), reason="needs bash + git")

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
E40 = "e" * 40                       # a head SHA this clone has never seen
PR_ADDS = {"docs/inbox/foo.md": "f\n", "src/new.py": "n\n"}   # what the rig's PR 7 adds on top of origin/main


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True, timeout=60).stdout.strip()


def _commit(repo, files, msg, delete=()):
    for rel, text in files.items():
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    for rel in delete:
        os.remove(os.path.join(repo, rel))
    _git(repo, "add", "-A", "--", *files, *delete)                     # these paths only: untracked helper copies never ride along
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def _verdict(ci_dir, pr, **fields):
    with open(os.path.join(ci_dir, "%d.json" % pr), "w", encoding="utf-8") as fh:
        json.dump({"pr": pr, **fields}, fh)


@pytest.fixture
def rig(tmp_path):
    """An upstream repo + a clone of it that carries a COPY of the helper and of the checker it re-runs at tools/dev/ (so
    the script's own `dirname $0/../..` resolution is what is tested), a real PR head in the clone (branch pr7 =
    origin/main + PR_ADDS, what session_ci.sh would have fetched as refs/pr/7) and a stored pass verdict for PR 7
    against the clone's origin/main."""
    up, clone = str(tmp_path / "upstream"), str(tmp_path / "clone")
    os.makedirs(up)
    _git(up, "init", "-q", "-b", "main")
    _commit(up, {"src/a.py": "a\n", "docs/x.md": "d\n", "docs/inbox/old.md": "o\n", "docs/coverage/viewer-certified.json": "{}\n"}, "one")
    _git(str(tmp_path), "clone", "-q", up, clone)
    was = _git(clone, "rev-parse", "origin/main")
    os.makedirs(os.path.join(clone, "tools", "dev"))
    for tool in (HELPER, CHECKER):
        shutil.copy(tool, os.path.join(clone, "tools", "dev"))
    ci = os.path.join(clone, ".git", "session-ci", "ci")
    os.makedirs(ci)
    ns = types.SimpleNamespace(up=up, ci=ci, was=was, err=None)

    def pr(n, files):
        """A PR head in the clone the way session_ci.sh leaves it (origin/main + `files`, fetched, not checked out)
        and a stored pass verdict for it against the clone's origin/main -> the head SHA."""
        _git(clone, "switch", "-q", "-c", "pr%d" % n, "origin/main")
        head = _commit(clone, files, "PR %d" % n)
        _git(clone, "switch", "-q", "--detach", "origin/main")
        _verdict(ci, n, head=head, main=was, verdict="pass")
        return head

    def fresh(*argv, path=None):
        env = dict(GIT_ENV, PATH=path) if path else GIT_ENV
        out = subprocess.run(["bash", os.path.join(clone, "tools", "dev", "ci_fresh.sh"), *(map(str, argv or (7,)))],
                             cwd=clone, env=env, capture_output=True, text=True, timeout=60)
        ns.err = out.stderr
        return out.returncode, out.stdout.strip()
    ns.pr, ns.fresh = pr, fresh
    ns.head = pr(7, PR_ADDS)
    return ns


def test_unchanged_main_is_fresh(rig):
    assert rig.fresh() == (0, "FRESH main=%s" % rig.was)
    assert rig.fresh(7, rig.head) == (0, "FRESH main=%s" % rig.was)     # with the expected head: same answer when it matches a pass


def test_docs_only_drift_is_fresh_and_says_so(rig):
    now = _commit(rig.up, {"docs/x.md": "more\n", "docs/inbox/record.md": "new\n", "docs/STEERING.md": "| row |\n"}, "docs only")
    assert rig.fresh() == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))
    assert rig.err == ""


def test_code_drift_is_stale_names_the_first_three_paths_and_exits_4(rig):
    now = _commit(rig.up, {"docs/x.md": "more\n", "src/a.py": "b\n", "tests/ci_shard.d/9-x.txt": "tests/test_b.py\n",
                           "tools/t.py": "t\n", "src/z.py": "z\n"}, "code moved under the verdict")
    rc, line = rig.fresh()
    assert rc == 4, line
    assert line == "STALE was=%s now=%s changed=src/a.py,src/z.py,tests/ci_shard.d/9-x.txt,… -> re-run tools/dev/session_ci.sh 7" % (rig.was, now), line   # docs/x.md is not counted; 4 blocking paths -> 3 named + ellipsis


@pytest.mark.parametrize("files,delete,blocking", [
    ({"docs/coverage/viewer-certified.json": " \n"}, (), "docs/coverage/viewer-certified.json"),        # tests/test_router.py + test_probe_batch.py open the ledger
    ({"docs/product/PERMUTATION-MATRIX.md": "| cell |\n"}, (), "docs/product/PERMUTATION-MATRIX.md"),   # test_router.py compares the rendered matrix
    ({"docs/process/AUTONOMY.md": "words\n"}, (), "docs/process/AUTONOMY.md"),                          # test_techlead.py pins needles in it
    ({"docs/x.md": "more\n"}, ("docs/inbox/old.md",), "docs/inbox/old.md"),                              # matrix.py cites records by existence: a deletion is drift
])
def test_docs_the_shard_reads_and_docs_deletions_are_stale(rig, files, delete, blocking):
    now = _commit(rig.up, files, "docs the gates can feel", delete=delete)
    assert rig.fresh() == (4, "STALE was=%s now=%s changed=%s -> re-run tools/dev/session_ci.sh 7" % (rig.was, now, blocking))


TWIN_LINE = ("STALE was=%s now=%s changed=%s (added on main; PR 7 adds the same name or a case-twin of it: an add/add conflict or a "
             "portable_paths failure after the merge) -> re-run tools/dev/session_ci.sh 7")


@pytest.mark.parametrize("added", ["docs/inbox/Foo.md", "docs/inbox/FOO.MD", "docs/inbox/foo.md"])
def test_a_docs_file_added_on_main_that_case_twins_a_pr_added_path_is_stale(rig, added):
    """#496: case-only twins are the one CROSS-FILE law of tools/dev/check_portable_paths.py, so `main` adding
    docs/inbox/Foo.md while the PR adds docs/inbox/foo.md reddens portable_paths only after the merge -- the verdict
    computed against the older main cannot have seen it. (The very same name is an add/add conflict: not mergeable on
    the old verdict either.) Other docs adds in the same drift stay tolerated and unnamed."""
    now = _commit(rig.up, {added: "twin\n", "docs/inbox/record.md": "new\n", "docs/x.md": "more\n"}, "main adds a twin of the PR's docs/inbox/foo.md")
    assert rig.fresh(7, rig.head) == (4, TWIN_LINE % (rig.was, now, added))
    assert rig.err == ""


def test_docs_added_on_main_with_a_head_this_clone_lacks_fail_closed_but_modified_docs_need_no_head(rig):
    _verdict(rig.ci, 17, head=E40, main=rig.was, verdict="pass")        # a JSON whose head was never fetched here
    now = _commit(rig.up, {"docs/x.md": "more\n"}, "docs modified only")
    assert rig.fresh(17) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))   # a MODIFIED docs file existed at `was`: session_ci already saw its name
    now = _commit(rig.up, {"docs/inbox/record.md": "new\n", "docs/inbox/note.md": "n\n"}, "docs added")
    assert rig.fresh(17) == (4, 'STALE was=%s now=%s changed=docs/inbox/note.md,docs/inbox/record.md (main added docs files and the recorded head "%s" '
                             'is not a commit in this clone, so a collision with a path PR 17 adds cannot be ruled out) -> re-run tools/dev/session_ci.sh 17' % (rig.was, now, E40))
    assert rig.fresh(7) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))    # the same drift with a known head: no twin, tolerated


def test_the_collision_check_fails_closed_when_its_interpreter_fails(rig, tmp_path):
    """A merge gate never reads "the check crashed" as "no collision": if the python3 behind the collision check fails
    (the review forced it with an argv above 128 KiB; the names are now read from git -z plumbing inside the program,
    and any other failure -- a git call, the checker import -- lands here), the answer is "cannot judge", exit 2 --
    not FRESH. A python3 shim that dies only for that one program (the one handed tools/dev/check_portable_paths.py,
    #522) proves it; the JSON read before it goes through the real interpreter."""
    shim = tmp_path / "py-shim"
    shim.mkdir()
    (shim / "python3").write_text('#!/bin/sh\nfor a in "$@"; do case "$a" in */check_portable_paths.py) echo "shim: refusing the collision check" >&2; exit 1;; esac; done\n'
                                  'exec "%s" "$@"\n' % shutil.which("python3"))
    (shim / "python3").chmod(0o755)
    path = str(shim) + os.pathsep + os.environ.get("PATH", "")
    now = _commit(rig.up, {"docs/inbox/Foo.md": "twin\n"}, "main adds a twin")
    assert rig.fresh(7, rig.head) == (4, TWIN_LINE % (rig.was, now, "docs/inbox/Foo.md"))          # the real interpreter sees it
    assert rig.fresh(7, rig.head, path=path) == (2, "cannot judge PR 7: the collision check against the names PR 7 adds failed")
    assert "shim: refusing" in rig.err
    now = _commit(rig.up, {"docs/x.md": "more\n"}, "and a modified doc", delete=("docs/inbox/Foo.md",))
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
    now = _commit(rig.up, {"docs/x.md": "more\n"}, "docs modified only")
    assert rig.fresh(8, head) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))
    now = _commit(rig.up, {"docs/inbox/record.md": "new\n"}, "a record added on main")
    assert rig.fresh(8, head) == (4, "STALE was=%s now=%s changed=docs/aux.md (tools/dev/check_portable_paths.py rejects the post-merge name set: "
                                    "reserved device name on Windows: 'docs/aux.md') -> re-run tools/dev/session_ci.sh 8" % (rig.was, now))
    assert rig.fresh(7, rig.head) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now))
    assert rig.err == ""


@pytest.mark.skipif(sys.platform == "win32", reason="a file named ' ' cannot exist on Windows")
def test_a_blocking_path_whose_name_is_all_blanks_is_still_named_and_stale(rig):
    """The join helper counts lines by length, not awk NF: a top-level file literally named " " is untolerated drift
    and must keep main's answer (STALE, the blank name after changed=), never vanish into FRESH(docs-only drift)."""
    now = _commit(rig.up, {" ": "z\n", "docs/x.md": "more\n"}, "a file named blank")
    assert rig.fresh() == (4, "STALE was=%s now=%s changed=  -> re-run tools/dev/session_ci.sh 7" % (rig.was, now))


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
    now = _commit(rig.up, {"docs/product/PERMUTATION-MATRIX-md": "x\n", "docs/process/AUTONOMY_md": "x\n", "docs/x.md": "more\n"}, "near misses")
    assert rig.fresh(path=path) == (0, "FRESH(docs-only drift) was=%s now=%s" % (rig.was, now)), flavour
    assert rig.err == "", (flavour, rig.err)
    # ...the real name is not, and the blocking list is joined the same way
    now = _commit(rig.up, {"docs/product/PERMUTATION-MATRIX.md": "| cell |\n", "src/a.py": "b\n", "src/b.py": "b\n", "src/c.py": "c\n"}, "the real thing")
    assert rig.fresh(path=path) == (4, "STALE was=%s now=%s changed=docs/product/PERMUTATION-MATRIX.md,src/a.py,src/b.py,… -> re-run tools/dev/session_ci.sh 7" % (rig.was, now)), flavour
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
        assert needle not in helper, needle          # it never touches PR code: our own JSON + git plumbing (names, never contents) only
    assert r"\." not in _shard_reads()               # [.] is the portable literal dot inside an awk -v string (gawk degrades \. to . with a warning)


# ---- meta: SHARD_READS must cover every docs/ path the real CI shard reads (#496) --------------------------------------

def _shard_reads():
    """The helper's SHARD_READS ERE, from the script itself (one source of truth). It is run below as a Python `re`, so
    it must stay inside the subset both dialects read the same way (anchors, groups, alternation, [.] classes)."""
    with open(HELPER, encoding="utf-8") as fh:
        pattern = re.search(r"^SHARD_READS='([^']*)'", fh.read(), re.M).group(1)
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
    spec = importlib.util.spec_from_file_location("shard_list", SHARD_LIST)
    sl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sl)
    shard = sl.merge(*sl.from_tree(ROOT))
    helpers = sorted("tests/" + n for n in os.listdir(os.path.join(ROOT, "tests")) if n.endswith(".py") and not n.startswith("test_"))
    reads = re.compile(_shard_reads())
    tracked = set(_git(ROOT, "ls-files", "--", "docs").splitlines())
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
