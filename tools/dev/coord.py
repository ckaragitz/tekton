#!/usr/bin/env python3
"""Coordination helpers for .github/workflows/coord.yml (stdlib only, GITHUB_TOKEN only).

The parts of the workflow that bash + jq do badly:

  similar  Rank existing issues whose TITLE looks like a new issue's title, so a
           freshly filed issue gets a "possible duplicates" hint before two
           sessions fix the same bug twice. IDF-weighted token overlap over the
           issue list passed in; identifiers such as validate_plugin,
           schema_cache/index.json or cp1252 carry most of the weight.
             python tools/dev/coord.py similar --title "T" --self 45 --issues issues.json

  refs     Parse a PR body (stdin) the way GitHub's linker does: which issues it
           CLOSES on merge (close/closes/closed/fix/fixes/fixed/resolve/resolves/
           resolved #N) vs merely mentions, plus the "does not close #N" trap -
           GitHub ignores the negation and closes #N anyway.
             python tools/dev/coord.py refs < body.txt                 -> JSON

  rivals   Other PRs whose body closes a given issue, through the same parser.
             python tools/dev/coord.py rivals --issue 37 --prs prs.json  -> "number login" lines

  reqfile  Parse a docs/requirements/*.md drop-box file for requirements.yml: optional
           front matter (--- delimited, simple `key: value` lines only — no YAML dep)
           with `title:`, `labels:` (comma-separated) and `auto:`; title falls back to
           the first `# ` heading, then to the prettified filename.
             python tools/dev/coord.py reqfile --path docs/requirements/foo.md  -> JSON

  queue    The work queue in pick order — `ready`, unassigned, not gated (blocked /
           needs-viewer / needs-revit-desktop / owner-machine / needs-decision), not a
           steer / tracking / board / epic issue, not held by the unattended worker
           (`bot-working`), and not already answered by an open PR that closes it
           (unless re-queued with `retry` because that PR got stuck) —
           sorted P0 > P1 > rest, oldest first. `/next` takes the head of this list;
           the worker (tools/dev/techlead.py) filters it further.
             python tools/dev/coord.py queue --issues issues.json --prs prs.json  -> numbers

  taskshape  Exit 0 if the issue body on stdin is shaped like a task (has a DONE
           section), 1 if it reads like free-form human input — coord labels the latter
           `intake` so the tech-lead planner triages it instead of it sitting unread.
             python tools/dev/coord.py taskshape < body.txt

issues.json / prs.json are `gh issue list --json number,title,state,assignees,labels` and
`gh pr list --json number,author,body` output.
"""
import argparse, json, math, re, sys
from collections import Counter

STOP = frozenset("""
the a an and or of on in to for with without from by at as is are be it its this that these those
when then than not no into via per all any every each own one two make add fix run use new vs do
does did which what who how here there after before under over out up so if
""".split())

_KEYWORD = r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)"
CLOSING = re.compile(r"(?<![\w-])" + _KEYWORD, re.I)
NEGATED = re.compile(r"\bnot\b[\s*_`~]{0,8}" + _KEYWORD, re.I)
MENTION = re.compile(r"(?<![\w/&])#(\d+)\b")


def _stem(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("es") and (t[-3] in "sxz" or t[-4:-2] in ("ch", "sh")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokens(title: str) -> set:
    """Lower-cased content tokens of a title: whole identifiers plus their parts."""
    out = set()
    for piece in re.findall(r"[a-z0-9_][a-z0-9_.\-]*", title.lower()):
        piece = piece.strip("._-")
        subs = [s for s in re.split(r"[._\-]", piece) if len(s) >= 3]
        for t in [piece] + subs:
            if t and t not in STOP and re.search(r"[a-z]", t):
                out.add(_stem(t))
    return out


def similar(title: str, issues: list, self_number: int = 0,
            threshold: float = 0.22, limit: int = 3) -> list:
    """Return [(score, issue, shared_tokens)] for issues whose title resembles `title`.

    score = IDF-weighted overlap coefficient in [0, 1]; document frequencies come
    from the candidate list itself plus the new title, so words every issue uses
    ("windows", "plugin") count little and rare identifiers count a lot.
    """
    mine = tokens(title)
    cands = [(i, tokens(i.get("title", ""))) for i in issues
             if int(i.get("number", 0)) != int(self_number or 0)]
    if not mine or not cands:
        return []
    df = Counter(t for toks in [mine, *(toks for _, toks in cands)] for t in toks)
    w = {t: math.log((len(cands) + 2) / (c + 0.5)) for t, c in df.items()}
    mine_w = sum(w[t] for t in mine)
    hits = []
    for issue, other in cands:
        shared = mine & other
        if not shared:
            continue
        score = sum(w[t] for t in shared) / min(mine_w, sum(w[t] for t in other))
        if score >= threshold:
            hits.append((round(score, 3), issue, sorted(shared, key=lambda t: (-w[t], t))))
    hits.sort(key=lambda h: (-h[0], int(h[1]["number"])))
    return hits[:limit]


def refs(body: str) -> dict:
    """{'closing': [...], 'refs': [...], 'negated': [...]} issue numbers found in a PR body."""
    body = re.sub(r"<!--.*?-->", " ", body or "", flags=re.S)   # template comments don't count
    closing = sorted({int(n) for n in CLOSING.findall(body)})
    return {"closing": closing,
            "refs": sorted({int(n) for n in MENTION.findall(body)} - set(closing)),
            "negated": sorted({int(n) for n in NEGATED.findall(body)})}


def rivals(issue: int, prs: list, self_number: int = 0) -> list:
    """[(number, author_login)] of PRs (other than self) whose body closes `issue`."""
    return [(int(p["number"]), (p.get("author") or {}).get("login", ""))
            for p in prs
            if int(p["number"]) != int(self_number or 0) and issue in refs(p.get("body") or "")["closing"]]


def reqfile(text: str, path: str = "") -> dict:
    """Parse a requirements drop-box markdown file.

    Returns {'title', 'labels', 'auto', 'body'}. Front matter is the strict
    subset every generator gets right: a leading `---` line, `key: value`
    lines, a closing `---`. Unknown keys are ignored; a malformed block is
    treated as body so a requirement never fails to file over formatting.
    """
    title, labels, auto = "", [], ""
    body = text or ""
    lines = body.split("\n")
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                fm = {}
                for ln in lines[1:end]:
                    m = re.match(r"^\s*([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$", ln)
                    if not m:
                        fm = None
                        break
                    fm[m.group(1).lower()] = m.group(2)
                if fm is not None:
                    title = fm.get("title", "")
                    labels = [t.strip() for t in fm.get("labels", "").split(",") if t.strip()]
                    auto = fm.get("auto", "").strip().lower()
                    body = "\n".join(lines[end + 1:])
                break
            if re.match(r"^\s*[A-Za-z_][\w-]*\s*:", lines[end]) is None:
                break   # not front matter (e.g. a --- rule further down a plain document)
    if not title:
        m = re.search(r"^#\s+(.+?)\s*$", body, re.M)
        title = m.group(1) if m else ""
    if not title and path:
        stem = re.sub(r"\.md$", "", path.replace("\\", "/").rsplit("/", 1)[-1])
        title = re.sub(r"[-_]+", " ", stem).strip().capitalize()
    return {"title": title.strip(), "labels": labels, "auto": auto, "body": body.strip()}


# Labels that mean "a person / a machine / a login is required": the queue skips these.
GATED = ("blocked", "needs-viewer", "needs-revit-desktop", "owner-machine", "needs-decision", "needs-human")
# Labels that mean "not a unit of work at all".
NOT_WORK = ("tracking", "board", "steer", "intake", "epic", "duplicate")
PRIORITY = {"P0": 0, "P1": 1, "P2": 2}
TASK_SHAPE = re.compile(r"(?im)^[\s>*_#-]*(?:\*\*|__)?\s*done\b(?:\*\*|__)?\s*(?:[=:(—-]|$)|^#{1,4}\s+.*\bdone\b")


def label_names(issue: dict) -> list:
    return [(l.get("name") if isinstance(l, dict) else str(l)) for l in (issue.get("labels") or [])]


def priority(issue: dict) -> int:
    return min([PRIORITY[n] for n in label_names(issue) if n in PRIORITY] or [3])


def queue(issues: list, prs: list, *, held_labels=("bot-working",)) -> list:
    """Open issues in pick order: ready, unassigned, workable now, nobody on it, no PR yet."""
    in_review = set()
    for p in prs or []:
        in_review.update(refs(p.get("body") or "")["closing"])
    out = []
    for i in issues or []:
        if str(i.get("state", "open")).lower() != "open" or i.get("pull_request"):
            continue
        names = set(label_names(i))
        if "ready" not in names or i.get("assignees"):
            continue
        if names & (set(GATED) | set(NOT_WORK) | set(held_labels)):
            continue
        if int(i["number"]) in in_review and "retry" not in names:
            continue          # answered by an open PR — unless that PR got stuck and the issue was re-queued
        out.append(i)
    return sorted(out, key=lambda i: (priority(i), int(i["number"])))


def is_task_shaped(body: str) -> bool:
    """True if an issue body carries a checkable DONE (## DONE, **DONE =**, DONE: ...)."""
    return bool(TASK_SHAPE.search(re.sub(r"<!--.*?-->", " ", body or "", flags=re.S)))


def _fmt_hit(score, issue, shared) -> str:
    who = ", ".join("@" + a["login"] for a in (issue.get("assignees") or []) if a.get("login"))
    state = str(issue.get("state", "")).lower() or "?"
    held = f", held by {who}" if who else (", unassigned" if state == "open" else "")
    return (f"- #{issue['number']} ({state}{held}) {issue.get('title', '').strip()} "
            f"— {int(round(score * 100))}% title overlap on `{'`, `'.join(shared[:5])}`")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("similar", help="print markdown bullets for likely-duplicate issues (empty = none)")
    s.add_argument("--title", required=True)
    s.add_argument("--self", type=int, default=0, help="number of the issue being checked (excluded)")
    s.add_argument("--issues", required=True, help="JSON file: gh issue list --json number,title,state,assignees")
    sub.add_parser("refs", help="read a PR body on stdin, print JSON {closing, refs, negated}")
    r = sub.add_parser("rivals", help="print 'number login' per other PR that closes --issue")
    r.add_argument("--issue", type=int, required=True)
    r.add_argument("--self", type=int, default=0, help="number of the PR being checked (excluded)")
    r.add_argument("--prs", required=True, help="JSON file: gh pr list --json number,author,body")
    q = sub.add_parser("reqfile", help="parse a docs/requirements/*.md file, print JSON {title, labels, auto, body}")
    q.add_argument("--path", required=True)
    u = sub.add_parser("queue", help="print the ready queue in pick order (issue numbers, one per line)")
    u.add_argument("--issues", required=True, help="JSON file: gh issue list --json number,title,state,assignees,labels")
    u.add_argument("--prs", required=True, help="JSON file: gh pr list --json number,author,body")
    sub.add_parser("taskshape", help="exit 0 if the issue body on stdin has a DONE section, else 1")
    a = ap.parse_args(argv)
    if a.cmd == "refs":
        print(json.dumps(refs(sys.stdin.read())))
        return 0
    if a.cmd == "taskshape":
        return 0 if is_task_shaped(sys.stdin.read()) else 1
    if a.cmd == "reqfile":
        with open(a.path, encoding="utf-8") as fh:
            print(json.dumps(reqfile(fh.read(), a.path)))
        return 0
    if a.cmd == "queue":
        with open(a.issues, encoding="utf-8") as fh:
            issues = json.load(fh)
        with open(a.prs, encoding="utf-8") as fh:
            prs = json.load(fh)
        for i in queue(issues, prs):
            print(i["number"])
        return 0
    with open(a.issues if a.cmd == "similar" else a.prs, encoding="utf-8") as fh:
        data = json.load(fh)
    if a.cmd == "similar":
        for hit in similar(a.title, data, a.self):
            print(_fmt_hit(*hit))
    else:
        for number, login in rivals(a.issue, data, a.self):
            print(number, login)
    return 0


if __name__ == "__main__":
    sys.exit(main())
