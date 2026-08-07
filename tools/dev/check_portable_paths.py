#!/usr/bin/env python3
"""Fail if any tracked path is not portable to Windows/macOS checkouts.

Checks: characters illegal on Windows (<>:"|?* backslash, control chars),
trailing dot/space in any component, reserved device names (CON, NUL, ...),
paths longer than 240 chars, and case-only collisions. Run in CI and before
pushing:  python tools/dev/check_portable_paths.py
"""
import collections, re, subprocess, sys

BAD = re.compile(r'[<>:"|?*\\\x00-\x1f]')
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
MAXLEN = 240

def main() -> int:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    paths = [p.decode("utf-8", "replace") for p in out.split(b"\0") if p]
    problems = []
    seen = collections.defaultdict(list)
    for p in paths:
        seen[p.lower()].append(p)
        if BAD.search(p):
            problems.append(f"illegal character for Windows: {p!r}")
        if len(p) > MAXLEN:
            problems.append(f"path too long ({len(p)} > {MAXLEN}): {p[:100]}...")
        for comp in p.split("/"):
            if comp.endswith((".", " ")):
                problems.append(f"trailing dot/space in component: {p!r}"); break
            if comp.split(".")[0].lower() in RESERVED:
                problems.append(f"reserved device name on Windows: {p!r}"); break
    for group in seen.values():
        if len(group) > 1:
            problems.append(f"case-only collision (breaks case-insensitive filesystems): {group}")
    if problems:
        print("NON-PORTABLE PATHS:\n  " + "\n  ".join(problems))
        return 1
    print(f"ok: {len(paths)} tracked paths are portable")
    return 0

if __name__ == "__main__":
    sys.exit(main())
