#!/usr/bin/env python3
"""tools/dev/ci_fresh_drift.py -- the "disjoint drift" judge behind tools/dev/ci_fresh.sh (#539).

ci_fresh.sh calls this only when origin/main moved under a stored sandboxed-CI verdict by MORE than tolerated docs
(code drift, a docs deletion, a docs file the shard reads). Question: may the pass verdict for PR head H, computed by
tools/dev/session_ci.sh against main W, still be merged on now that main is N? The merged tree is N + the PR's own
change; the run tested W + that change; N itself went through the same gate. So a test can only change colour if what
it executes or reads meets BOTH changes at once. FRESH is answered only when every rule below holds -- each a cheap,
static, fail-closed reading; the first one that does not hold is the STALE reason:
  1. shape: H is a commit in this clone, W is an ancestor of N, and H has exactly one merge base with N, itself an
     ancestor of W (the run really tested H merged with something N descends from; a head rebased past W or a
     rewritten trunk is not judged);
  2. every changed path on both sides -- main: W..N; PR: merge-base..H; renames unpaired, so both names count -- is a
     plain portable name (letters, digits, _ . / + -), was ADDED or MODIFIED (a deletion, rename or type change can be
     felt through a name computed at run time -- load_tool("genesis_%d" % year) -- so it is re-run, never argued), and
     there are at most LIMIT of them per side;
  3. neither side touches a GATE: the shard machinery (conftest -- any conftest.py, pytest.ini & co., wherever they
     lie -- the shard list and its reader, session_ci, this judge and its caller, the portable-paths law, pyproject,
     the setup script), a whole-tree checker session_ci.sh runs or its law data (sync_plugin and its identity allowlist,
     validate_plugin, the tests that sweep the tree with them, the pinned assets and manifests), or a docs file the
     shard reads (SHARD_READS, handed in by ci_fresh.sh from its one line); a shard drop-in tests/ci_shard.d/<n>.txt is
     fine only when every test it enrols is itself changed on that side (enrolling an UNCHANGED test is precisely a
     test the other side's change never ran under). tests/test_ci_fresh.py pins that every gate exists and that every
     file session_ci.sh executes is one;
  4. added/modified docs/** outside SHARD_READS are then set aside on both sides (inert: the docs-only rule's ground,
     tests/test_ci_fresh.py + the runtime audit keep it true) -- everything else must be DISJOINT: no path on both sides;
  5. uncoupled, both directions, on text read from git blobs as data (nothing imported, nothing executed): no changed
     .py file of one side imports -- absolutely or relatively, as a module or through its package -- a module the
     other side changed (`from pkg import name` counts as the whole package unless `name` is a module file of either
     tree, so façade re-exports are covered); no changed text file of one side names a path the other side changed
     (repo-relative path, basename, dotted module name; for tools/, tests/ and scripts/ files also the bare stem as a
     word: load_tool("x"), `python tools/x.py`, `-m x`); and no changed .py file BUILDS a name that can reach a path
     the other side changed: a loader call on a non-literal (import_module / __import__ / load_tool /
     spec_from_file_location / runpy) reaches everything, a templated literal (f"rvt.genesis.port{year}",
     "genesis_%d") reaches every changed path, module or stem its literal prefix begins;
  6. clean: `git merge-tree --write-tree N H` (git >= 2.38: the merge happens in the object store -- no checkout, no
     worktree; older git cannot judge) reports no conflict, and the merged tree's full name list still passes
     tools/dev/check_portable_paths.py's own check() (a case-only twin across the two sides merges "cleanly" in git).
Unjudged, stated: coupling THROUGH an unchanged third file (main changes rvt.x; the PR changes a caller of rvt.y;
rvt.y uses rvt.x), and references assembled at run time inside files neither side changed. Both parents were green
with their own change in place; the rule bets that a semantic collision between file-disjoint, import-disjoint,
name-disjoint changes is rarer than a re-run is cheap -- and everything it CAN see wrong is STALE.

argv: WAS NOW HEAD PR SHARD_READS_ERE. stdout: exactly one line -- the payload ci_fresh.sh wraps into its own
STALE/FRESH/cannot-judge envelope: exit 0 "main=<n> pr=<n> …" | 4 the STALE reason | 2 why it cannot judge.
Trusted side only, stdlib only; ci_fresh.sh runs it with `python3 -IB` from the checkout it lives in, and the only code
it executes besides git plumbing is that checkout's check_portable_paths.py and shard_list.py, loaded by path from its
own directory.
"""
import collections
import importlib.util
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 200                                                     # changed paths per side this judge is willing to read
GATES = {"tests/conftest.py", "tests/ci_shard.txt", "tools/dev/shard_list.py", "tools/dev/session_ci.sh",            # the shard machinery
         "tools/dev/ci_fresh.sh", "tools/dev/ci_fresh_drift.py", "tools/dev/check_portable_paths.py", "pyproject.toml", "scripts/cloud-setup.sh",
         "tools/sync_plugin.py", "tools/plugin_identity_allowlist.json", "plugin/scripts/validate_plugin.py",              # whole-tree checkers, their law
         "tests/test_plugin_sync.py", "tests/test_plugin_validate.py", "tests/test_ci_fresh.py", "tests/test_shard_list.py",  # data, and the tests that
         "tests/test_portable_paths.py"}                                                                                     # sweep the tree with them
GATE_DIRS = ("plugin/assets/", "src/rvt/frontdoor/assets/", "plugin/lib/src/rvt/frontdoor/assets/", "plugin/.claude-plugin/")   # pinned bases, manifests
RUNNER_FILES = {"conftest.py", "pytest.ini", "tox.ini", "setup.cfg", "setup.py", "sitecustomize.py", "usercustomize.py"}   # picked up by name, in any directory
PLAIN = re.compile(r"^[A-Za-z0-9_./+-]+$")                       # a name this judge argues about (git quotes most others anyway)
IMPORT = re.compile(r"^[ \t]*(?:from[ \t]+([.\w]+)[ \t]+import[ \t]+([^#\n]*)|import[ \t]+([^#\n]*))", re.M)
ALIAS = re.compile(r"([A-Za-z_][\w.]*)(?:[ \t]+as[ \t]+\w+)?")     # one item of an import list
# A loader call whose first argument is neither a plain string literal nor a plain (dotted) name: the name is being
# BUILT right there ("genesis_%d" % year, f"rvt.mep.{mod}", prefix + name). A plain variable is let through: its
# value is a literal somewhere -- in this file or in the caller's -- and literals are what the needle scan reads.
DYNAMIC = re.compile(r"""\b(?:import_module|__import__|load_tool|spec_from_file_location|run_path|run_module)\((?!\s*(?:['"][\w./-]+['"]|[A-Za-z_][\w.]*)\s*[,)])""")
LITERAL_HEAD = re.compile(r"""\s*[fF]?[rR]?['"]([\w./-]*)[%{]""")            # a template opened right after such a paren: its literal prefix
# ...and the literal such a variable is built from, when it is a template: a string that looks like a repo module or
# path ("rvt.…", "….py", "tools/…", "tests/…", "src/…", "plugin/…", "skills/…", "test_…", "genesis_…") with a
# %-conversion or an f-string field inside it and no blank anywhere (a name has none; a message -- f"tools/x.py not
# found at {p}" -- has). Output paths ("out/%s.rvt") match no prefix and stay unflagged.
TEMPLATED = re.compile(r"""[fF]?[rRbB]?['"](?=[^'"\s]*(?:\brvt\.|\.py\b|\b(?:tools|tests|src|plugin|skills)/|\btest_|\bgenesis_))[^'"\s]*(?:%[-+0-9.]*[sdixr]|\{[\w.\[\]!:]*\})[^'"\s]*['"]""")
PY_ROOTS = ("plugin/lib/src/", "plugin/lib/tools/", "src/", "tests/", "tools/")   # stripped to get a file's importable dotted name
BY_STEM = ("tools/", "tests/", "plugin/lib/tools/")                # .py files there (and under any scripts/) are also loaded by bare name

Side = collections.namedtuple("Side", "label tip files texts")   # one side of the merge: who, at which commit, its non-docs changed paths, their text


class Stale(Exception):
    pass


class CannotJudge(Exception):
    pass


def trusted(name):
    """This checkout's tools/dev/<name>.py, loaded by path from the judge's own directory (never through sys.path)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args, ok=(0,), stdin=None):
    p = subprocess.run(["git", *args], input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode not in ok:
        err = p.stderr.decode("utf-8", "replace").strip()
        hint = " -- `git merge-tree --write-tree` needs git >= 2.38" if args[0] == "merge-tree" and p.returncode == 129 else ""
        raise CannotJudge("git %s failed (%d)%s: %s" % (" ".join(args[:2]), p.returncode, hint, err.splitlines()[0][:160] if err else "-"))
    return p


def few(items, n=1):
    """The first n named, the rest counted."""
    return (", ".join(items[:n]) + (" (+%d more)" % (len(items) - n) if items[n:] else "")) if items else "?"


def changed(a, b, label, reads):
    """The NON-DOCS paths a..b adds or modifies -> sorted list; anything rules 2-3 refuse raises Stale. Added/modified
    docs outside SHARD_READS are counted against LIMIT and then set aside (rule 4)."""
    recs = git("diff", "--name-status", "--no-renames", "-z", a, b, "--").stdout.split(b"\0")[:-1]
    if len(recs) % 2:
        raise CannotJudge("odd name-status record count on the %s side" % label)
    if len(recs) // 2 > LIMIT:
        raise Stale("%s changes more than %d paths, over what this judge reads" % (label, LIMIT))
    out = []
    for st, path in zip(recs[0::2], recs[1::2]):
        st, path = st.decode(), path.decode("utf-8", "replace")
        if not PLAIN.match(path):
            raise Stale("%s changes a path this judge does not argue about: %r" % (label, path[:80]))
        if st not in ("A", "M"):
            raise Stale("%s %s %s; deletions, renames and type changes are re-run, not judged" % (label, {"D": "deletes", "T": "retypes"}.get(st, st + "s"), path))
        why = gate(path) or ("a docs file the shard reads (SHARD_READS)" if reads.match(path) else None)
        if why:
            raise Stale("%s changes %s, %s" % (label, path, why))
        if not path.startswith("docs/"):
            out.append(path)
    return sorted(out)


def gate(path):
    """Why `path` is a gate (rule 3), or None."""
    if path in GATES or path.startswith(GATE_DIRS):
        return "a gate: shard machinery, a whole-tree checker or its law data"
    if os.path.basename(path) in RUNNER_FILES or path.endswith(".pth") or path == "tests/__init__.py":
        return "a file pytest or the interpreter picks up by name, wherever it lies"
    if path.startswith(SHARD.DROPIN_DIR + "/") and not SHARD.DROPIN_NAME.match(path[len(SHARD.DROPIN_DIR) + 1:]):
        return "shard machinery"
    return None


def blobs(tip, paths):
    """{path: text} of `paths` at commit `tip` through one `git cat-file --batch`: blobs read as data, undecodable bytes
    -> U+FFFD; a missing or non-blob entry (a submodule, say) -> CannotJudge."""
    out = {}
    if not paths:
        return out
    buf, i = git("cat-file", "--batch", stdin="".join("%s:%s\n" % (tip, q) for q in paths).encode()).stdout, 0
    for q in paths:
        nl = buf.index(b"\n", i)
        head = buf[i:nl].split()
        if len(head) != 3 or head[1] != b"blob":
            raise CannotJudge("%s:%s is not a blob (%s)" % (tip[:12], q, buf[i:nl].decode("utf-8", "replace")[:60]))
        size = int(head[2])
        out[q] = buf[nl + 1:nl + 1 + size].decode("utf-8", "replace")
        i = nl + 1 + size + 1
    return out


def module_name(path):
    """The dotted name a repo .py file is imported as ('' for a non-.py path): src/rvt/a/b.py -> rvt.a.b,
    src/rvt/a/__init__.py -> rvt.a, tests/x.py -> x, tools/dev/x.py -> dev.x, any/where/else/x.py -> x."""
    if not path.endswith(".py"):
        return ""
    rel = next((path[len(root):] for root in PY_ROOTS if path.startswith(root)), os.path.basename(path))
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def tree_modules(tip):
    """The dotted name of every .py file in the tree of `tip`."""
    names = git("ls-tree", "-r", "--name-only", "-z", tip).stdout.decode("utf-8", "replace").split("\0")
    return {module_name(p) for p in names if p.endswith(".py")} - {""}


def import_items(text):
    """The names of a comma-separated import list, or None when it does not parse as one (prose)."""
    matches = [ALIAS.fullmatch(part.strip()) for part in text.strip().rstrip("\\").strip().strip("()").split(",") if part.strip()]
    return [m.group(1) for m in matches] if matches and all(matches) else None


def imports(path, text, modules):
    """Every module name a .py file's import statements name, absolute (relative ones resolved against the file's own
    dotted name). `from X import a, b`: an item that is a module of either tree (`modules`) names X.a; any other item
    (a re-exported attribute), a `*`, or a `(` list continued on later lines names the package X itself -- which
    related() then couples to EVERY changed module under X. Lines that do not parse as an import statement are prose (a
    docstring line starting with "import" or "from") and name nothing: real code with such a line would not have
    compiled under the run being judged."""
    me = module_name(path).split(".")
    pkg = me if path.endswith("/__init__.py") else me[:-1]
    names = set()
    for frm, what, plain in IMPORT.findall(text):
        if plain:                                                # import a.b as c, d
            names.update(import_items(plain) or ())
            continue
        whole = what.strip() == "*" or what.strip().startswith("(")   # everything, or a list continued on later lines
        items = import_items(what)
        if not (whole or items):
            continue
        if frm.startswith("."):
            rest = frm.lstrip(".")
            up = len(frm) - len(rest)                            # from . = 1, from .. = 2, ...
            if up - 1 > len(pkg):
                raise Stale("%s has a relative import that climbs above its root (%s)" % (path, frm[:40]))
            frm = ".".join(pkg[:len(pkg) - (up - 1)] + ([rest] if rest else []))
            if not frm:
                raise Stale("%s has a relative import this judge cannot resolve" % path)
        if whole:
            names.add(frm)
        for item in items or ():
            sub = frm + "." + item
            names.add(sub if "." not in item and sub in modules else frm)
    return names


def related(a, b):
    """Do dotted names a and b lie on one import chain (equal, or one a package above the other)?"""
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def names_of(path):
    """(dotted module name, every token another file's text can name `path` by): its repo-relative path, its basename
    (a package's is its dotted name, never "__init__.py"), its dotted module name, and for files loaded by bare name
    (tools/, tests/, any scripts/ dir, the repo root) the stem."""
    dotted = module_name(path)
    names = {path, dotted, os.path.basename(path)} - {"", "__init__.py"}
    if path.endswith(".py") and (path.startswith(BY_STEM) or "/scripts/" in path or "/" not in path):
        names.add(os.path.basename(path)[:-3])
    return dotted, names


def templates(text):
    """The literal prefixes of the module/path names a .py text BUILDS at run time: the part of each templated literal
    before its first %-conversion / f-string field; for a loader call on a non-literal, the literal prefix of a
    template written right in the call (import_module(f"rvt.mep.{mod}") -> "rvt.mep."), else '' = anything at all."""
    built = {(m.group(1) if m else "") for m in (LITERAL_HEAD.match(text, call.end()) for call in DYNAMIC.finditer(text))}
    return built | {re.split(r"%|\{", m.group(0).lstrip("fFrRbB")[1:-1], maxsplit=1)[0] for m in TEMPLATED.finditer(text)}


def coupling(x, y, modules):
    """The first way a changed file of side x refers to a changed path of side y, or None; `modules` = every dotted
    module name of both trees (what `from pkg import name` is resolved against)."""
    def token(names):                                            # ONE whole-token regex over a set of names, longest first
        return re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)))
    targets = sorted(((q, *names_of(q)) for q in y.files), key=lambda t: -len(t[1]))   # (path of y, dotted name, name tokens); most specific module first, so the reason names it
    if not targets:
        return None
    any_name = token(set().union(*(names for _, _, names in targets)))   # each text is scanned once; only a file that hits pays for the per-target pass
    for f in x.files:
        text = x.texts[f]
        if f.endswith(".py"):
            for prefix in sorted(templates(text)):               # a name built at run time reaches every changed path its literal prefix allows
                hit = next((q for q, _, names in targets if any(n.startswith(prefix) for n in names)), None)
                if hit:
                    return "%s's %s builds names at run time (\"%s…\") that can reach %s, changed on %s" % (x.label, f, prefix[:40], hit, y.label)
            named = sorted(imports(f, text, modules))
            for q, dotted, _ in targets:
                hit = next((i for i in named if related(i, dotted)), None) if dotted else None
                if hit:
                    return "%s's %s imports %s%s (%s), changed on %s" % (x.label, f, hit, "" if hit == dotted else ", on one import chain with " + dotted, q, y.label)
        if any_name.search(text):
            q = next(q for q, _, names in targets if token(names).search(text))
            return "%s's %s names %s, changed on %s" % (x.label, f, q, y.label)
    return None


def dropins_enrol_only_changed_tests(side):
    for f in side.files:
        if f.startswith(SHARD.DROPIN_DIR + "/"):
            stranger = next((t for t in SHARD.parse(side.texts[f]) if t not in side.files), None)
            if stranger:
                raise Stale("%s's %s enrols %s, a test %s does not change (never run with the other side's change)" % (side.label, f, stranger[:80], side.label))


def judge(was, now, head, pr, shard_reads):
    """-> (non-docs paths changed on main, on the PR) when every rule holds; raises Stale / CannotJudge otherwise."""
    reads, prl = re.compile(shard_reads), "PR %s" % pr
    if git("cat-file", "-e", head + "^{commit}", ok=(0, 1, 128)).returncode:
        raise Stale("the recorded head %s is not a commit in this clone, so %s's own change cannot be read" % (head[:12], prl))
    if git("merge-base", "--is-ancestor", was, now, ok=(0, 1)).returncode:
        raise Stale("the recorded main is not an ancestor of origin/main (trunk rewritten)")
    bases = git("merge-base", "--all", now, head, ok=(0, 1)).stdout.split()
    if len(bases) != 1:
        raise Stale("%s's head has %d merge bases with origin/main" % (prl, len(bases)))
    base = bases[0].decode()
    if git("merge-base", "--is-ancestor", base, was, ok=(0, 1)).returncode:
        raise Stale("%s's merge base %s is not an ancestor of the recorded main (head rebased past the run)" % (prl, base[:12]))
    drift, prs = changed(was, now, "main", reads), changed(base, head, prl, reads)
    both = sorted(set(drift) & set(prs))
    if both:
        raise Stale("%s also changes %s" % (prl, few(both)))
    main_side, pr_side = Side("main", now, drift, blobs(now, drift)), Side(prl, head, prs, blobs(head, prs))
    dropins_enrol_only_changed_tests(main_side)
    dropins_enrol_only_changed_tests(pr_side)
    modules = tree_modules(now) | tree_modules(head)
    why = coupling(pr_side, main_side, modules) or coupling(main_side, pr_side, modules)
    if why:
        raise Stale(why)
    mt = git("merge-tree", "--write-tree", "--name-only", "--no-messages", now, head, ok=(0, 1))
    lines = mt.stdout.decode("utf-8", "replace").splitlines()
    if mt.returncode:
        raise Stale("merging %s into origin/main conflicts on %s" % (prl, few(lines[1:], 3)))
    findings = trusted("check_portable_paths").check(git("ls-tree", "-r", "--name-only", "-z", lines[0]).stdout.decode("utf-8", "replace").split("\0")[:-1])
    if findings:
        raise Stale("tools/dev/check_portable_paths.py rejects the merged tree: %s" % few([problem for problem, _ in findings]))
    return len(drift), len(prs)


def main(argv):
    global SHARD
    was, now, head, pr, shard_reads = argv
    try:
        SHARD = trusted("shard_list")                            # DROPIN_DIR, DROPIN_NAME, parse(): the drop-in law from its one home
        nmain, npr = judge(was, now, head, pr, shard_reads)
    except Stale as e:
        print(e)
        return 4
    except Exception as e:                                       # noqa: BLE001 -- whatever else goes wrong is "cannot judge", said in one line, never FRESH
        print("%s%s" % ("" if isinstance(e, CannotJudge) else type(e).__name__ + ": ", str(e) or "-"))
        return 2
    print("main=%d pr=%d (disjoint from the %d non-docs path%s PR %s changes: not imported or named either way, no gate touched, merge clean)"
          % (nmain, npr, npr, "" if npr == 1 else "s", pr))
    return 0


SHARD = None
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
