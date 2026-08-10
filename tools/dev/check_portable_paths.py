#!/usr/bin/env python3
"""Fail if any tracked path is not portable to Windows/macOS checkouts.

Checks: characters illegal on Windows (<>:"|?* backslash, control chars),
trailing dot/space in any component, reserved device names (CON, NUL, ...),
paths longer than 240 chars, and case-only collisions. Run in CI and before
pushing:  python tools/dev/check_portable_paths.py
`check(paths)` is the whole gate as a pure function; callers run it over name sets
other than the work tree (tools/dev/ci_fresh.sh: the post-merge names, at merge
time, #522), so keep every law inside check() and main() a gatherer of names only.
"""
import collections, re, subprocess, sys

BAD = re.compile(r'[<>:"|?*\\\x00-\x1f]')
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
MAXLEN = 240

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
