#!/usr/bin/env python3
"""tools/dev/ci_fresh_drift.py -- the OPT-IN "disjoint drift" judge behind tools/dev/ci_fresh.sh (#539).

ci_fresh.sh calls this only when CI_FRESH_JUDGE=1 is exported AND origin/main moved under a stored sandboxed-CI verdict
by MORE than tolerated docs (code drift, a docs deletion, a docs file the shard reads); without the variable code drift
is STALE, full stop -- the standing gate keeps its pre-#539 guarantee, and the tech lead takes this bet deliberately on
queue-heavy ticks. Question: may the pass verdict for PR head H, computed by tools/dev/session_ci.sh against main W,
still be merged on now that main is N? The merged tree is N + the PR's own change; the run tested W + that change; N
itself went through the same gate. So a test can only change colour if what it executes or reads meets BOTH changes at
once. FRESH is answered only when every rule below holds -- each a cheap, static, fail-closed reading; the first one
that does not hold is the STALE reason:
  1. shape: W, N and H are 40-hex ids, H is a commit in this clone, W is an ancestor of N, and H has exactly one merge
     base with N, itself an ancestor of W (the run really tested H merged with something N descends from; a head
     rebased past W or a rewritten trunk is not judged);
  2. every changed path on both sides -- main: W..N; PR: merge-base..H; renames unpaired, so both names count -- is a
     plain portable name (letters, digits, _ . / + -), a REGULAR file (a symlink or a submodule entry is judged by
     nobody: STALE), was ADDED or MODIFIED (a deletion, rename or type change can be felt through a name computed at
     run time -- load_tool("genesis_%d" % year) -- so it is re-run, never argued), is at most BLOB_LIMIT bytes, and
     there are at most LIMIT of them per side;
  3. neither side touches a GATE: the shard machinery (conftest -- any conftest.py, pytest.ini, pyproject.toml & co.
     wherever they lie, any __init__.py under tests/ -- the shard list and its reader, session_ci, this judge and its
     caller, the portable-paths law, the setup script), a whole-tree checker session_ci.sh runs or its law data
     (sync_plugin and its identity allowlist, validate_plugin, the tests that sweep the tree with them, the pinned assets
     and manifests), or a docs file the shard reads (SHARD_READS, handed in by ci_fresh.sh from its one line); a shard
     drop-in tests/ci_shard.d/<n>.txt is fine only when every test it enrols is itself changed on that side (enrolling an
     UNCHANGED test is precisely a test the other side's change never ran under). tests/test_ci_fresh.py pins that every
     gate exists and that every file session_ci.sh executes is one;
  4. added/modified docs/** outside SHARD_READS are then set aside on both sides (inert: the docs-only rule's ground,
     tests/test_ci_fresh.py + the runtime audit keep it true) -- everything else must be DISJOINT: no path on both sides;
  5. uncoupled, both directions, on text read from git blobs as data (parsed, never imported, never executed):
     (a) no changed .py file of one side imports a module the other side changed -- every `import` / `from … import`
     statement anywhere in the file, found with ast (a file that does not parse is STALE), absolute or relative, as a
     module or through its package (`from pkg import name` names the whole package unless `name` is a module file of
     either tree, so façade re-exports are covered), plus a line-regex reading of the same statements as a backstop;
     (b) no changed text file of one side NAMES a path the other side changed (repo-relative path, basename, dotted
     module name; for tools/, tests/ and scripts/ files also the bare stem as a word: load_tool("x"), `python
     tools/x.py`, `-m x`); (c) no changed .py file of one side BUILDS or DISCOVERS names that can reach a path the other
     side changed: a loader call (import_module / __import__ / load_tool / spec_from_file_location -- name AND path --
     / run_path / run_module) whose deciding arguments are not plain string literals, and any directory walk (glob /
     iglob / rglob / listdir / scandir / walk / iterdir), reaches EVERYTHING the other side changed -- narrowed only
     when the call itself spells a literal repo prefix (a tracked top-level directory: os.path.join(ROOT, "tools",
     "x.py") -> tools/x.py; or the rvt. namespace: import_module(f"rvt.mep.{mod}") -> rvt.mep.) to the changed paths
     that prefix begins; a templated literal anywhere in the file that looks like a module or repo path
     (f"rvt.genesis.port{year}", "tools/%s.py") reaches what its literal prefix begins, or everything when that prefix
     is not such a repo prefix ("genesis_%d", f"{tool}.py");
  6. clean: `git merge-tree --write-tree N H` (git >= 2.38: the merge happens in the object store -- no checkout, no
     worktree; older git cannot judge) reports no conflict, and the merged tree's full name list still passes
     tools/dev/check_portable_paths.py's own check() (a case-only twin across the two sides merges "cleanly" in git).
Unjudged, stated: coupling THROUGH an unchanged third file (main changes rvt.x; the PR changes a caller of rvt.y;
rvt.y uses rvt.x); names assembled at run time by plain concatenation or os.path.join pieces with no loader or walk
call in the changed file itself; references living in files neither side changed. Both parents were green with their
own change in place; the rule bets that a semantic collision between file-disjoint, import-disjoint, name-disjoint
changes is rarer than a re-run is cheap -- and everything it CAN see wrong is STALE. (An exact alternative -- refuse
whenever the two changes share one test's import cone -- was measured and rejected for now: tests/conftest.py imports
rvt.frontdoor at start-up, so every shard cone is ~170 files and the rule degenerates to "always STALE"; it becomes
viable the day a runtime import/read audit supplies real per-test cones.)

argv: WAS NOW HEAD PR SHARD_READS_ERE. stdout: exactly one line -- the payload ci_fresh.sh wraps into its own
STALE/FRESH/cannot-judge envelope: exit 0 "main=<n> pr=<n> …" | 4 the STALE reason | 2 why it cannot judge.
Trusted side only, stdlib only; ci_fresh.sh runs it under `timeout` with `python3 -IB` from the checkout it lives in,
and the only code it executes besides git plumbing is that checkout's check_portable_paths.py and shard_list.py, loaded
by path from its own directory.
"""
import ast
import collections
import importlib.util
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 200                                                     # changed paths per side this judge is willing to read
BLOB_LIMIT = 2_000_000                                          # bytes of one changed file it is willing to scan (a source file is far below; a dump is not judged)
GATES = {"tests/conftest.py", "tests/ci_shard.txt", "tools/dev/shard_list.py", "tools/dev/session_ci.sh",            # the shard machinery
         "tools/dev/ci_fresh.sh", "tools/dev/ci_fresh_drift.py", "tools/dev/check_portable_paths.py", "pyproject.toml", "scripts/cloud-setup.sh",
         "tools/sync_plugin.py", "tools/plugin_identity_allowlist.json", "plugin/scripts/validate_plugin.py",              # whole-tree checkers, their law
         "tests/test_plugin_sync.py", "tests/test_plugin_validate.py", "tests/test_ci_fresh.py", "tests/test_shard_list.py",  # data, and the tests that
         "tests/test_portable_paths.py"}                                                                                     # sweep the tree with them
GATE_DIRS = ("plugin/assets/", "src/rvt/frontdoor/assets/", "plugin/lib/src/rvt/frontdoor/assets/", "plugin/.claude-plugin/")   # pinned bases, manifests
RUNNER_FILES = {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", "setup.py", "sitecustomize.py", "usercustomize.py"}   # picked up by name, in ANY directory
REGULAR = (b"100644", b"100755")                                # git modes of a regular file; 120000 (symlink) and 160000 (gitlink) are not argued about
SHA = re.compile(r"[0-9a-f]{40}")
PLAIN = re.compile(r"^[A-Za-z0-9_./+-]+$")                       # a name this judge argues about (git quotes most others anyway)
IMPORT = re.compile(r"^[ \t]*(?:from[ \t]+([.\w]+)[ \t]+import[ \t]+([^#\n]*)|import[ \t]+([^#\n]*))", re.M)   # the line-regex backstop to the ast reading
ALIAS = re.compile(r"([A-Za-z_][\w.]*)(?:[ \t]+as[ \t]+\w+)?")     # one item of an import list
# Calls that load code by name/path or discover files: unless their deciding arguments are plain string literals, the
# names they produce are BUILT at run time (rule 5c). Group 1 = the callee, so spec_from_file_location can demand two literals.
BUILDER = re.compile(r"\b(import_module|__import__|load_tool|spec_from_file_location|run_path|run_module|i?glob|rglob|listdir|scandir|walk|iterdir)\s*\(")
LOADERS = {"import_module", "__import__", "load_tool", "spec_from_file_location", "run_path", "run_module"}   # the BUILDER callees that load (the rest discover)
LITERAL_ARG = re.compile(r"""\s*['"]([\w./-]+)['"]\s*([,)])""")   # one plain string-literal argument and what follows it
PIECE = re.compile(r"""[fF]?[rRbB]{0,2}['"]([\w./*?-]*)['"%{]""")   # the literal head of a string (up to its end, a %-conversion or an f-field)
# A templated literal that looks like a module or repo path: quote to quote with no blank inside (a name has none; a
# message -- f"tools/x.py not found at {p}" -- has), bounded so a quote-poor megabyte line costs O(n), holding a
# %-conversion or an f-string field. Output paths ("out/%s.rvt") do not look like one and stay unflagged.
QUOTED = re.compile(r"""[fF]?[rRbB]{0,2}['"]([^'"\s]{2,240})['"]""")
LOOKS_LIKE_NAME = re.compile(r"\brvt\.|\.py$|\.py\b|^(?:tools|tests|src|plugin|skills)/|\btest_|\bgenesis_")
FIELD = re.compile(r"%[-+0-9.]*[sdixr]|\{[\w.\[\]!:]*\}")
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
    docs outside SHARD_READS are counted against LIMIT and then set aside (rule 4). Read from `git diff --raw -z` so the
    file MODE is judged too: only regular files on both ends of an entry are argued about."""
    recs = git("diff", "--raw", "--no-renames", "--no-abbrev", "-z", a, b, "--").stdout.split(b"\0")[:-1]
    if len(recs) % 2:
        raise CannotJudge("odd raw-diff record count on the %s side" % label)
    if len(recs) // 2 > LIMIT:
        raise Stale("%s changes more than %d paths, over what this judge reads" % (label, LIMIT))
    out = []
    for meta, path in zip(recs[0::2], recs[1::2]):
        fields, path = meta.split(), path.decode("utf-8", "replace")   # :oldmode newmode oldsha newsha status
        if len(fields) != 5 or not fields[0].startswith(b":"):
            raise CannotJudge("unreadable raw-diff record on the %s side: %r" % (label, meta[:60]))
        old_mode, new_mode, st = fields[0][1:], fields[1], fields[4].decode()
        if not PLAIN.match(path):
            raise Stale("%s changes a path this judge does not argue about: %r" % (label, path[:80]))
        if st not in ("A", "M"):
            raise Stale("%s %s %s; deletions, renames and type changes are re-run, not judged" % (label, {"D": "deletes", "T": "retypes"}.get(st, st + "s"), path))
        if new_mode not in REGULAR or (st == "M" and old_mode not in REGULAR):
            raise Stale("%s changes %s, %s (mode %s): only regular files are judged" % (label, path, {b"120000": "a symlink", b"160000": "a submodule entry"}.get(new_mode, "not a regular file"), new_mode.decode()))
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
    if os.path.basename(path) in RUNNER_FILES or path.endswith(".pth") or (path.startswith("tests/") and os.path.basename(path) == "__init__.py"):
        return "a file pytest or the interpreter picks up by name, wherever it lies"
    if path.startswith(SHARD.DROPIN_DIR + "/") and not SHARD.DROPIN_NAME.match(path[len(SHARD.DROPIN_DIR) + 1:]):
        return "shard machinery"
    return None


def blobs(side_label, tip, paths):
    """{path: text} of `paths` at commit `tip` through one `git cat-file --batch`: blobs read as data, undecodable bytes
    -> U+FFFD; a missing or non-blob entry -> CannotJudge; a blob over BLOB_LIMIT -> Stale (not scanned, not judged)."""
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
        if size > BLOB_LIMIT:
            raise Stale("%s's %s is %d bytes, over the %d this judge reads" % (side_label, q, size, BLOB_LIMIT))
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


def tree_names(tip):
    """(the dotted name of every .py file in the tree of `tip`, its top-level directory names)."""
    names = git("ls-tree", "-r", "--name-only", "-z", tip).stdout.decode("utf-8", "replace").split("\0")[:-1]
    return {module_name(p) for p in names if p.endswith(".py")} - {""}, {p.split("/", 1)[0] for p in names if "/" in p}


def resolve(path, frm, level):
    """The absolute dotted name of `from <'.' * level><frm> import …` inside repo file `path` (raises Stale when the
    dots climb above the file's own root)."""
    if not level:
        return frm
    me = module_name(path).split(".")
    pkg = me if path.endswith("/__init__.py") else me[:-1]
    if level - 1 > len(pkg) or not (pkg[:len(pkg) - (level - 1)] or frm):
        raise Stale("%s has a relative import this judge cannot resolve (%s%s)" % (path, "." * level, frm))
    return ".".join(pkg[:len(pkg) - (level - 1)] + ([frm] if frm else []))


def import_items(text):
    """The names of a comma-separated import list, or None when it does not parse as one (prose)."""
    matches = [ALIAS.fullmatch(part.strip()) for part in text.strip().rstrip("\\").strip().strip("()").split(",") if part.strip()]
    return [m.group(1) for m in matches] if matches and all(matches) else None


def imports(path, text, modules):
    """Every module name a .py file's import statements name, absolute (relative ones resolved against the file's own
    dotted name). Read twice and united: with ast over the whole file (every statement wherever it sits -- inline
    suites, `;` chains, backslash or parenthesised continuations, function bodies; a file that does not parse cannot be
    read, so it is STALE), and with a line regex as a backstop. `from X import a, b`: an item that is a module of either
    tree (`modules`) names X.a; any other item (a re-exported attribute) or a `*` names the package X itself -- which
    related() then couples to EVERY changed module under X."""
    try:
        tree = ast.parse(text, path)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
        raise Stale("%s does not parse, so its imports cannot be read (%s: %s)" % (path, type(e).__name__, str(e).splitlines()[0][:80] if str(e) else "-"))
    found = []                                                   # (absolute package/module, [item names] or None for a plain `import`)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((resolve(path, node.module or "", node.level), [alias.name for alias in node.names]))
    for frm, what, plain in IMPORT.findall(text):                # the backstop: same statements, line by line (prose that does not parse as one names nothing)
        if plain:
            found.extend((name, None) for name in import_items(plain) or ())
        elif import_items(what) or what.strip().startswith(("*", "(")):   # a bare `(` opens a list continued on later lines: the package itself
            found.append((resolve(path, frm.lstrip("."), len(frm) - len(frm.lstrip("."))), import_items(what) or ["*"]))
    names = set()
    for frm, items in found:
        if items is None:
            names.add(frm)
            continue
        for item in items:
            sub = frm + "." + item
            names.add(sub if item != "*" and "." not in item and sub in modules else frm)
    return names - {""}


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


def call_args(text, start, limit=400):
    """The argument text of the call whose `(` ends just before `start`, up to its matching `)` (or `limit` chars)."""
    depth, i = 1, start
    while i < len(text) and i - start < limit:
        c = text[i]
        depth += (c == "(") - (c == ")")
        i += 1
        if not depth:
            break
    return text[start:i]                                         # the closing `)` included when it was found


def repo_prefix(pieces, tops):
    """The literal path/module prefix a call or template spells, or '' (= reaches everything): the leading plain pieces
    joined with '/', kept only when they start at a tracked top-level directory or in the rvt. namespace -- a piece
    from the middle of an os.path.join (base, "gen", name) proves nothing about where the walk starts."""
    lead = []
    for piece in pieces:
        literal = re.split(r"[*?\[]", piece, maxsplit=1)[0]      # a glob pattern counts up to its first wildcard
        if not literal or literal.startswith((".", "/")):
            break
        lead.append(literal.strip("/"))
        if literal != piece:
            break
    prefix = "/".join(lead)
    return prefix if prefix and (prefix.split("/", 1)[0] in tops or prefix.startswith("rvt.")) else ""


def builds(text, tops):
    """The literal prefixes of the names a .py text BUILDS or DISCOVERS at run time (rule 5c); '' among them = anything."""
    prefixes = set()
    for call in BUILDER.finditer(text):
        args = call_args(text, call.end())
        loader, first = call.group(1) in LOADERS, LITERAL_ARG.match(args)
        if loader and first and (first.group(2) == ")" or call.group(1) != "spec_from_file_location" or LITERAL_ARG.match(args, first.end())):
            continue                                             # plain literals: the needle scan reads them
        skip = first.end() if first and call.group(1) == "spec_from_file_location" else 0   # its NAME argument says nothing about the PATH being built
        prefixes.add(repo_prefix(PIECE.findall(args, skip), tops))
    for m in QUOTED.finditer(text):
        body = m.group(1)
        if FIELD.search(body) and LOOKS_LIKE_NAME.search(body):
            prefixes.add(repo_prefix([re.split(r"%|\{", body, maxsplit=1)[0]], tops))
    return prefixes


def coupling(x, y, modules, tops):
    """The first way a changed file of side x refers to a changed path of side y, or None; `modules` = every dotted
    module name of both trees (what `from pkg import name` is resolved against), `tops` = their top-level directories."""
    def token(names):                                            # ONE whole-token regex over a set of names, longest first
        return re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)))
    targets = sorted(((q, *names_of(q)) for q in y.files), key=lambda t: -len(t[1]))   # (path of y, dotted name, name tokens); most specific module first, so the reason names it
    if not targets:
        return None
    any_name = token(set().union(*(names for _, _, names in targets)))   # each text is scanned once; only a file that hits pays for the per-target pass
    for f in x.files:
        text = x.texts[f]
        if f.endswith(".py"):
            for prefix in sorted(builds(text, tops)):            # a name built or discovered at run time reaches every changed path its literal prefix allows
                hit = next((q for q, _, names in targets if any(n.startswith(prefix) for n in names)), None)
                if hit:
                    return "%s's %s builds or discovers names at run time (\"%s…\") that can reach %s, changed on %s" % (x.label, f, prefix[:40], hit, y.label)
            named = sorted(imports(f, text, modules))
            for q, dotted, _ in targets:
                hit = (dotted if dotted in named else next((i for i in named if related(i, dotted)), None)) if dotted else None
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
    for what, sha in (("main", was), ("origin/main", now), ("head", head)):
        if not SHA.fullmatch(sha):
            raise Stale("the recorded %s %r is not a 40-hex commit id" % (what, sha[:44]))
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
    main_side, pr_side = Side("main", now, drift, blobs("main", now, drift)), Side(prl, head, prs, blobs(prl, head, prs))
    dropins_enrol_only_changed_tests(main_side)
    dropins_enrol_only_changed_tests(pr_side)
    (mods_now, tops_now), (mods_head, tops_head) = tree_names(now), tree_names(head)
    modules, tops = mods_now | mods_head, tops_now | tops_head
    why = coupling(pr_side, main_side, modules, tops) or coupling(main_side, pr_side, modules, tops)
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
        print(str(e).splitlines()[0])
        return 4
    except Exception as e:                                       # noqa: BLE001 -- whatever else goes wrong is "cannot judge", said in one line, never FRESH
        print(("%s%s" % ("" if isinstance(e, CannotJudge) else type(e).__name__ + ": ", str(e) or "-")).splitlines()[0])
        return 2
    print("main=%d pr=%d (disjoint from the %d non-docs path%s PR %s changes: not imported or named either way, no gate touched, merge clean)"
          % (nmain, npr, npr, "" if npr == 1 else "s", pr))
    return 0


SHARD = None
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
