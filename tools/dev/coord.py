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

  locks    Session-scoped claim locks (steer #90). Every 🔒 comment coord posts carries
           `<!-- lock by=LOGIN session=TAG token=ID -->`; /release, the reaper and the
           re-queue sweep post `<!-- unlock by=LOGIN -->`. A lock is STANDING when its
           holder is still an assignee and no later unlock names them. The earliest
           standing lock wins ties between sessions — including two sessions of the SAME
           login, which the assignee field alone cannot tell apart.
             python tools/dev/coord.py locks --comments comments.json --assignees a,b  -> JSON

  nextbatch / reservations / batchclash   Viewer batch numbers (#285). `probe_batch.py
           stage` numbers a batch "highest local batch_<n>.json + 1", so two sessions that
           branch from the same main and both STAGE take the same numbers (PRs #277 and
           #283 both added batch_57..59). `/batches k` reserves a range server-side: coord
           records `<!-- batches by=LOGIN lo=N hi=M issue=I token=ID -->` on the one
           registry issue (label `batch-registry`), N = 1 + max(highest batch file on the
           default branch, highest earlier reservation, highest batch file any open PR
           adds). `batchclash` is the PR-time safety net: a PR whose added batch_<n>.json is
           already on main, reserved for another issue, or also added by an OLDER open PR
           is told the exact renumber command; a newer/unreserved rival is flagged instead.
             python tools/dev/coord.py nextbatch --k 3 --tree tree.txt --registry reg.json --prs prs.json  -> "lo hi"
             python tools/dev/coord.py batchclash --self 283 --linked 134 --self-files files.json \
                    --prs prs.json --registry reg.json --tree tree.txt                       -> JSON

issues.json / prs.json are `gh issue list --json number,title,state,assignees,labels` and
`gh pr list --json number,author,body[,files]` output; tree.txt is one repo path per line
(`gh api repos/R/git/trees/main?recursive=1 --jq '.tree[].path'`); reg.json / comments.json
are `gh api repos/R/issues/N/comments` output.
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
# Held without an assignee: the unattended worker's lease (GitHub cannot assign a bot).
HELD = ("bot-working",)
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


LOCK_RE = re.compile(r"<!-- lock by=([A-Za-z0-9_.\[\]-]+) session=([A-Za-z0-9_.:@/-]+) token=([A-Za-z0-9_-]+) -->")
UNLOCK_RE = re.compile(r"<!-- unlock by=([A-Za-z0-9_.\[\]-]+) -->")


def lock_marker(by: str, session: str = "-", token: str = "-") -> str:
    return f"<!-- lock by={by} session={session or '-'} token={token or '-'} -->"


def unlock_marker(by: str) -> str:
    return f"<!-- unlock by={by} -->"


def standing_locks(comments: list, assignees) -> list:
    """Locks whose holder is still assigned and not unlocked since, oldest first.

    `comments` = the issue's comments in creation order ({body, created_at, id});
    returns [{by, session, token, created_at, comment_id}]. The FIRST entry holds the issue.
    A comment carrying BOTH an unlock and a lock for the same holder (coord's re-lock /
    take-over reply) means "release the old, take the new": unlocks in a comment apply
    before the locks in that same comment, so the fresh lock stands.
    """
    held = set(assignees or [])
    last_unlock = {}
    locks = []
    for i, c in enumerate(comments or []):
        body = c.get("body") or ""
        for by in UNLOCK_RE.findall(body):
            last_unlock[by] = i
        for by, session, token in LOCK_RE.findall(body):
            locks.append({"by": by, "session": session, "token": token, "created_at": c.get("created_at", ""),
                          "comment_id": c.get("id"), "_idx": i})
    out = [l for l in locks if l["by"] in held and l["_idx"] >= last_unlock.get(l["by"], -1)]
    for l in out:
        l.pop("_idx", None)
    return out


# ---- viewer batch numbers (#285) -------------------------------------------------------------
BATCH_FILE_RE = re.compile(r"(?:^|/)batch_(\d+)\.json$")
RESERVE_RE = re.compile(r"<!-- batches by=([A-Za-z0-9_.\[\]-]+) lo=(\d+) hi=(\d+) issue=(\d+) token=([A-Za-z0-9_-]+) -->")
MAX_RESERVE = 9        # per request; a viewer round is one batch per release, so 3 is typical


def batch_numbers(paths) -> set:
    """{n} for every experiments/**/batch_<n>.json path in `paths` (numbers are campaign-global)."""
    out = set()
    for p in paths or []:
        p = str(p).replace("\\", "/")
        m = BATCH_FILE_RE.search(p)
        if m and (p.startswith("experiments/") or "/" not in p):
            out.add(int(m.group(1)))
    return out


def reserve_marker(by: str, lo: int, hi: int, issue: int, token: str) -> str:
    return f"<!-- batches by={by} lo={int(lo)} hi={int(hi)} issue={int(issue)} token={token or '-'} -->"


def reservations(comments: list) -> list:
    """Reserved ranges recorded on the registry issue, in creation order.

    Only coord's own comments count when the author is known (a human pasting a marker
    reserves nothing); test fixtures without a `user` field are accepted as-is.
    """
    out = []
    for c in comments or []:
        user = ((c.get("user") or {}).get("login") or "") if isinstance(c, dict) else ""
        if user and not user.endswith("[bot]"):
            continue
        for by, lo, hi, issue, token in RESERVE_RE.findall((c.get("body") or "") if isinstance(c, dict) else str(c)):
            out.append({"by": by, "lo": int(lo), "hi": int(hi), "issue": int(issue), "token": token,
                        "created_at": c.get("created_at", "") if isinstance(c, dict) else ""})
    return out


def pr_batches(prs: list, on_main: set) -> dict:
    """{pr_number: {n}} — batch numbers each open PR ADDS (touching a batch file that is not on
    the default branch can only mean adding it; `gh pr list --json files` carries no status)."""
    out = {}
    for p in prs or []:
        paths = [(f.get("path") if isinstance(f, dict) else str(f)) for f in (p.get("files") or [])]
        nums = batch_numbers(paths) - set(on_main)
        if nums:
            out[int(p["number"])] = nums
    return out


def next_batch(k: int, on_main: set, reserved: list, open_pr_nums: set) -> tuple:
    """(lo, hi): k fresh numbers above everything on main, everything reserved, everything any
    open PR adds — so a reservation can never hand out a number somebody already staged."""
    k = max(1, min(int(k or 1), MAX_RESERVE))
    top = max([0, *[int(n) for n in on_main], *[r["hi"] for r in reserved], *[int(n) for n in open_pr_nums]])
    return top + 1, top + k


def batch_clashes(self_pr: int, self_added: set, linked: set, prs: list, reserved: list, on_main: set) -> dict:
    """PR-time judgement for the batch files `self_pr` adds.

    A number belongs to the ISSUE it was reserved for (all engineer sessions may share one
    login, so the login cannot discriminate); with no reservation the OLDER open PR wins —
    automerge's duplicate rule. Returns
      {"clashes": [{n, kind: main|reserved|older-pr, ...}],   # self must renumber these
       "flag":    {rival_pr: [n, ...]},                       # rivals that must renumber instead
       "suggest": (lo, hi) | None, "key": str, "message": str, "rival_messages": {pr: str}}
    """
    self_pr = int(self_pr)
    mine = {int(p) for p in (linked or [])} | {self_pr}
    others = {pr: nums for pr, nums in pr_batches(prs, on_main).items() if pr != self_pr}
    authors = {int(p["number"]): ((p.get("author") or {}).get("login", "")) for p in prs or []}
    clashes, flag = [], {}
    for n in sorted(int(x) for x in self_added or []):
        if n in on_main:
            clashes.append({"n": n, "kind": "main"})
            continue
        owner = next((r for r in reserved if r["lo"] <= n <= r["hi"]), None)
        rivals = sorted(pr for pr, nums in others.items() if n in nums)
        if owner is not None and owner["issue"] not in mine:
            clashes.append({"n": n, "kind": "reserved", "issue": owner["issue"], "by": owner["by"]})
        elif owner is None and any(pr < self_pr for pr in rivals):
            older = min(pr for pr in rivals if pr < self_pr)
            clashes.append({"n": n, "kind": "older-pr", "pr": older, "author": authors.get(older, "")})
        else:
            for pr in rivals:                       # I own n (reserved for my issue, or I am the older PR)
                flag.setdefault(pr, []).append(n)
    suggest = None
    if clashes:
        taken = set().union(*others.values()) if others else set()
        taken |= {int(x) for x in self_added or []} - {c["n"] for c in clashes}
        suggest = next_batch(len(clashes), on_main, reserved, taken)
    key = ",".join(f"{c['n']}:{c['kind']}" for c in clashes) or "none"
    return {"clashes": clashes, "flag": {str(k): v for k, v in flag.items()}, "suggest": suggest,
            "key": key, "message": _clash_message(self_pr, clashes, suggest),
            "rival_messages": {str(pr): _rival_message(pr, self_pr, nums) for pr, nums in flag.items()}}


def _clash_message(self_pr: int, clashes: list, suggest) -> str:
    if not clashes:
        return ""
    groups = {}                                     # one clause per cause, not per number
    for c in clashes:
        cause = (c["kind"], c.get("pr") or c.get("issue") or 0, c.get("author") or c.get("by") or "")
        groups.setdefault(cause, []).append(c["n"])
    why = []
    for (kind, ref, who), nums in groups.items():
        files = _batch_files(nums)
        if kind == "main":
            why.append(f"{files} already exist(s) on the default branch (merged since this branch was cut)")
        elif kind == "reserved":
            why.append(f"batch {', '.join(map(str, nums))} is reserved for #{ref} (`/batches` by @{who})")
        else:
            why.append(f"{files} is/are also added by the older open PR #{ref}" + (f" (@{who})" if who else "")
                       + " — the older PR keeps its numbers")
    lo, hi = suggest
    rng = f"{lo}" if lo == hi else f"{lo}..{hi}"
    old = ", ".join(str(c["n"]) for c in clashes)
    return ("🔢 **Viewer batch-number clash** — " + "; ".join(why) + ".\n\n"
            f"Renumber this PR's batch(es) {old} → **{rng}**: re-stage with "
            f"`tools/probe_batch.py stage … --batch {lo}`" + (" (and up)" if lo != hi else "") +
            f", `git rm` the old `batch_<n>.json`, commit the new manifests, and update the record / the "
            "upload instructions so the human records verdicts against unambiguous numbers. Next time reserve "
            "first: comment `/batches <k>` on your issue and pass the numbers coord replies with to `--batch` "
            "(CLAUDE.md §2). This check re-runs on every push and clears the label by itself.")


def _batch_files(nums) -> str:
    return ", ".join(f"`batch_{n}.json`" for n in sorted(nums))


def _rival_message(rival_pr: int, self_pr: int, nums: list) -> str:
    return (f"🔢 **Viewer batch-number clash** — {_batch_files(nums)} is/are also added by PR #{self_pr}, which owns the number(s) "
            "(reserved for its issue via `/batches`, or it is the older PR). Renumber here: comment `/batches "
            f"{len(nums)}` for a fresh range, re-stage with `tools/probe_batch.py stage … --batch <N>`, `git rm` the "
            "old manifests, and update your record / upload instructions. This check re-runs on every push.")


def is_task_shaped(body: str) -> bool:
    """True if an issue body carries a checkable DONE (## DONE, **DONE =**, DONE: ...)."""
    return bool(TASK_SHAPE.search(re.sub(r"<!--.*?-->", " ", body or "", flags=re.S)))


def _load_json(path: str, default):
    """JSON from `path`; `default` when the path is empty, missing or blank (optional inputs)."""
    if not path:
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return default
    return json.loads(text) if text.strip() else default


def _load_lines(path: str) -> list:
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            return [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return []


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
    k = sub.add_parser("locks", help="print the standing claim locks of an issue as JSON (first = holder)")
    k.add_argument("--comments", required=True, help="JSON file: the issue's comments (gh api .../comments)")
    k.add_argument("--assignees", default="", help="comma-separated current assignee logins")
    v = sub.add_parser("reservations", help="print the batch-number reservations recorded in a registry issue's comments as JSON")
    v.add_argument("--registry", required=True, help="JSON file: the registry issue's comments ('' or missing = none)")
    nb = sub.add_parser("nextbatch", help="print 'lo hi': the next k free viewer batch numbers")
    nb.add_argument("--k", type=int, default=1)
    nb.add_argument("--tree", default="", help="text file: one default-branch path per line")
    nb.add_argument("--registry", default="", help="JSON file: the registry issue's comments")
    nb.add_argument("--prs", default="", help="JSON file: gh pr list --json number,author,body,files")
    bc = sub.add_parser("batchclash", help="print JSON: batch-number clashes of PR --self and what to renumber to")
    bc.add_argument("--self", type=int, required=True, help="number of the PR being checked")
    bc.add_argument("--linked", default="", help="comma-separated issue numbers the PR closes/refs")
    bc.add_argument("--self-files", default="", help="JSON file: REST pulls/N/files ([{filename,status}]); default: paths from --prs")
    bc.add_argument("--tree", default="")
    bc.add_argument("--registry", default="")
    bc.add_argument("--prs", default="")
    a = ap.parse_args(argv)
    if a.cmd == "refs":
        print(json.dumps(refs(sys.stdin.read())))
        return 0
    if a.cmd == "taskshape":
        return 0 if is_task_shaped(sys.stdin.read()) else 1
    if a.cmd == "locks":
        with open(a.comments, encoding="utf-8") as fh:
            comments = json.load(fh)
        print(json.dumps(standing_locks(comments, [x for x in a.assignees.split(",") if x])))
        return 0
    if a.cmd in ("reservations", "nextbatch", "batchclash"):
        reserved = reservations(_load_json(a.registry, []))
        if a.cmd == "reservations":
            print(json.dumps(reserved))
            return 0
        on_main = batch_numbers(_load_lines(a.tree))
        prs = _load_json(a.prs, [])
        if a.cmd == "nextbatch":
            taken = set().union(*pr_batches(prs, on_main).values()) if prs else set()
            print(*next_batch(a.k, on_main, reserved, taken))
            return 0
        files = _load_json(a.self_files, None)
        if files is None:      # no REST statuses: fall back to "touches a batch file not on main"
            self_added = pr_batches([p for p in prs if int(p["number"]) == a.self], on_main).get(a.self, set())
        else:
            self_added = batch_numbers(f.get("filename") or f.get("path") or "" for f in files
                                       if (f.get("status") or "added") == "added")
        linked = {int(x) for x in a.linked.split(",") if x.strip().isdigit()}
        print(json.dumps(batch_clashes(a.self, self_added, linked, prs, reserved, on_main)))
        return 0
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
