#!/usr/bin/env python3
"""Fail if any tracked path is not portable to Windows/macOS checkouts (or breaks the docs/inbox record layout).

Checks: characters illegal on Windows (<>:"|?* backslash, control chars),
trailing dot/space in any component, reserved device names (CON, NUL, ...),
paths longer than 240 chars, and case-only collisions. Run in CI and before
pushing:  python tools/dev/check_portable_paths.py
`check(paths)` is the whole gate as a pure function; callers run it over name sets
other than the work tree (tools/dev/ci_fresh.sh: the post-merge names, at merge
time, #522), so keep every law inside check() and main() a gatherer of names only.
One such law is not about portability at all but rides the same seam on purpose:
the stream-record layout under docs/inbox/ (docs/inbox/README.md, #636/#638) --
`layout_violations()` below, called by check(), so a record index deleted by a PR
while main adds a fragment beside it is refused at merge time, not found on main.
Stdlib only and self-contained: session_ci.sh runs this file with `python3 -I` and
ci_fresh.sh loads it by path, so it must never import a sibling module.
"""
import collections, re, subprocess, sys

BAD = re.compile(r'[<>:"|?*\\\x00-\x1f]')
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
MAXLEN = 240
INBOX = "docs/inbox/"                                                # stream records: <stream>.md, or that index + <stream>.d/<issue>-<slug>.md fragments
FRAGMENT = re.compile(r"^[0-9]+-[A-Za-z0-9][A-Za-z0-9_.-]*\.md$")   # <issue>-<slug>.md; slug class = tools/dev/shard_list.py DROPIN_NAME's

def layout_violations(names) -> list[tuple[str, list[str]]]:
    """The record-layout law (docs/inbox/README.md) over INBOX-relative posix file names -> [(breach line, the names
    involved)], sorted, empty = lawful: every <stream>.d/*.md is named <issue>-<slug>.md, and every <stream>.d/ that
    holds files has its index <stream>.md beside it. Only direct <stream>.d/<file> children are judged; single-file
    records, attachments (<issue>-evidence.json) and deeper paths are not. Pure, like check()."""
    names = set(names)
    out = collections.defaultdict(set)
    for n in names:
        parts = n.split("/")
        if len(parts) != 2 or not parts[0].endswith(".d"):
            continue
        d, leaf = parts
        if d[:-2] + ".md" not in names:
            out[f"{d}/ has no index {d[:-2]}.md beside it"].add(n)
        if leaf.endswith(".md") and not FRAGMENT.match(leaf):
            out[f"{n} is not named <issue>-<slug>.md"].add(n)
    return sorted((line, sorted(involved)) for line, involved in out.items())

def check(paths: list[str]) -> list[tuple[str, list[str]]]:
    """Every problem in a list of repo-relative names -> [(problem line, the names involved)], in the order the CLI
    prints them. Pure: no git, no filesystem, so the same list means the same verdict wherever it is judged. Names
    may repeat (both sides of a merge adding one name): a repeat is a case-only collision group like any other twin."""
    findings = []
    seen = collections.defaultdict(list)
    for p in paths:
        seen[p.lower()].append(p)
        if BAD.search(p):
            findings.append((f"illegal character for Windows: {p!r}", [p]))
        if len(p) > MAXLEN:
            findings.append((f"path too long ({len(p)} > {MAXLEN}): {p[:100]}...", [p]))
        for comp in p.split("/"):
            if comp.endswith((".", " ")):
                findings.append((f"trailing dot/space in component: {p!r}", [p])); break
            if comp.split(".")[0].lower() in RESERVED:
                findings.append((f"reserved device name on Windows: {p!r}", [p])); break
    for group in seen.values():
        if len(group) > 1:
            findings.append((f"case-only collision (breaks case-insensitive filesystems): {group}", group))
    for line, involved in layout_violations(p[len(INBOX):] for p in paths if p.startswith(INBOX)):
        findings.append((f"record layout ({INBOX}README.md): {line}", [INBOX + n for n in involved]))
    return findings

def main() -> int:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    paths = [p.decode("utf-8", "replace") for p in out.split(b"\0") if p]
    problems = [line for line, _ in check(paths)]
    if problems:
        print("NON-PORTABLE PATHS:\n  " + "\n  ".join(problems))
        return 1
    print(f"ok: {len(paths)} tracked paths are portable")
    return 0

if __name__ == "__main__":
    sys.exit(main())
