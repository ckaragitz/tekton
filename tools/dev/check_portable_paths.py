#!/usr/bin/env python3
"""Fail if any tracked path is not portable to Windows/macOS checkouts (or breaks the docs/inbox record layout).

Checks: characters illegal on Windows (<>:"|?* backslash, control chars incl.
DEL 0x7f -- a class that contains the whole byte set git C-quotes even with
core.quotePath=false, which is what lets tools/dev/ci_fresh.sh read every quoted
docs name as a name this gate refuses, #540), trailing dot/space in any component, reserved device names (CON, NUL, ...),
paths longer than 240 chars, names whose bytes are not valid UTF-8, and the two
cross-file laws of the filesystems collaborators check out onto: case-only
collisions (NTFS, APFS) and normalisation-only collisions -- `café.md` spelled NFC
(precomposed é) and NFD (e + combining acute) are two names to git and ONE file to
APFS/HFS+, exactly like case twins (#724). Run in CI and before pushing:
  python tools/dev/check_portable_paths.py
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
import collections, re, subprocess, sys, unicodedata

BAD = re.compile(r'[<>:"|?*\\\x00-\x1f\x7f]')
SURROGATE = re.compile("[\udc80-\udcff]")                          # what surrogateescape leaves for each byte that was not UTF-8 (#724)
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

def nfd(p: str) -> str:
    """Canonical decomposition: the representative every canonically-equivalent spelling of `p` shares, and the form the
    filesystems that fold names compare in (APFS hashes the case-folded DEcomposed name; HFS+ stores one), #724."""
    return unicodedata.normalize("NFD", p)

def check(paths: list[str]) -> list[tuple[str, list[str]]]:
    """Every problem in a list of repo-relative names -> [(problem line, the names involved)], in the order the CLI
    prints them. Pure: no git, no filesystem, so the same list means the same verdict wherever it is judged. Names
    may repeat (both sides of a merge adding one name): a repeat is a case-only collision group like any other twin.
    Names arrive as str: a gatherer that read bytes git could not vouch for decodes them with surrogateescape (this
    CLI) or replace (tools/dev/ci_fresh.sh) -- the encoding law recognises either residue (#724). Both cross-file laws
    judge whole names, as the case law always has: twins that differ inside a DIRECTORY component only
    (Docs/a.md vs docs/b.md, an NFC vs an NFD spelling of one <stream>.d/) are not paired here."""
    findings = []
    seen = collections.defaultdict(list)          # case law: what a case-insensitive checkout (NTFS, default APFS) folds together -- lower(), not casefold(): volumes fold 1:1, straße/strasse are two files everywhere
    forms = collections.defaultdict(list)         # normalisation law: what ANY APFS/HFS+ checkout folds together
    for p in paths:
        d = nfd(p)
        seen[d.lower()].append(p)                 # decompose THEN lower: J+caron vs precomposed j-caron (no capital form exists) fold too
        forms[d].append(p)
        if BAD.search(p):
            findings.append((f"illegal character for Windows: {p!r}", [p]))
        if not p.isascii():                       # both residues below are non-ASCII, and a repo's names almost never are: skip the scans
            if SURROGATE.search(p):               # the offending bytes, spelled as the bytes they are
                findings.append((f"not valid UTF-8: {p.encode('utf-8', 'surrogateescape')!r}", [p]))
            elif "\ufffd" in p:                    # valid UTF-8 spelling U+FFFD: some tool already replaced a byte it could not decode (a `replace` reader such as ci_fresh.sh's, or the writer itself)
                findings.append((f"replacement character U+FFFD in name (an undecodable byte was replaced somewhere upstream): {ascii(p)}", [p]))
        if len(p) > MAXLEN:
            findings.append((f"path too long ({len(p)} > {MAXLEN}): {p[:100]}...", [p]))
        for comp in p.split("/"):
            if comp.endswith((".", " ")):
                findings.append((f"trailing dot/space in component: {p!r}", [p])); break
            if comp.split(".")[0].lower() in RESERVED:
                findings.append((f"reserved device name on Windows: {p!r}", [p])); break
    for group in seen.values():        # a repeated name, or two-plus spellings that survive decomposition (a real case difference); a group differing ONLY by normalisation form is the next law's alone
        if len(group) > 1 and (len(set(group)) == 1 or len({nfd(p) for p in group}) > 1):
            findings.append((f"case-only collision (breaks case-insensitive filesystems): {group}", group))
    for group in forms.values():       # canonically equivalent yet not byte-equal: one file on a macOS checkout, and phantom `git status` changes on HFS+ (#724)
        if len(set(group)) > 1:
            findings.append((f"normalisation-only collision (breaks macOS checkouts): {ascii(group)}", group))   # ascii(): the twins print identically otherwise
    for line, involved in layout_violations(p[len(INBOX):] for p in paths if p.startswith(INBOX)):
        findings.append((f"record layout ({INBOX}README.md): {line}", [INBOX + n for n in involved]))
    return findings

def main() -> int:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    paths = [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]   # bytes-faithful: a name that is not UTF-8 reaches check() (and its law) instead of arriving pre-mangled
    problems = [line for line, _ in check(paths)]
    if problems:
        sys.stdout.reconfigure(errors="backslashreplace")                          # a problem line may quote such a name raw (the record-layout law does); print it, never die on it
        print("NON-PORTABLE PATHS:\n  " + "\n  ".join(problems))
        return 1
    print(f"ok: {len(paths)} tracked paths are portable")
    return 0

if __name__ == "__main__":
    sys.exit(main())
