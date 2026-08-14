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

  reserve / batchjudge   Viewer batch numbers (#285). `probe_batch.py stage` numbers a batch
           "highest local batch_<n>.json + 1", so two sessions that branch from the same main
           and both STAGE take the same numbers (PRs #277 and #283 both added batch_57..59).
           `reserve` is the `/batches k` decision: a range above everything on the default
           branch, every earlier reservation (markers `<!-- batches by lo hi issue token -->`
           coord records on the one `batch-registry` issue) and every batch file any open PR
           adds; idempotent per requesting comment. `batchjudge` is the safety net run when a
           PR opens / is edited and every hour: which open PRs add a number that is reserved
           for another issue or that an OLDER open PR also adds, and the exact renumber command.
             python tools/dev/coord.py reserve --k 3 --by cam --issue 134 --token 501 --url U \
                    --registry-number 287 --tree tree.txt --registry reg.json --prs prs.json  -> JSON
             python tools/dev/coord.py batchjudge --tree tree.txt --registry reg.json --prs prs.json  -> JSON

issues.json / prs.json are `gh issue list --json number,title,state,assignees,labels` and
`gh pr list --json number,author,body[,files]` output; tree.txt holds the default-branch paths
NUL-separated (TREE_RECIPE: `git fetch -q origin main && git ls-tree --full-tree -r -z --name-only origin/main
-- experiments/ > tree.txt` — the freshly fetched DEFAULT branch, whatever is checked out and from whatever
subdirectory: a stale origin/main is the likeliest way to hand out a taken number; the older one-per-line
`--name-only` output is still read, C-quoted names included, #723). A tree.txt that is not empty yet names nothing
under experiments/ — a UTF-16 file from Windows PowerShell `>`, the wrong tree — is refused, never read as "nothing
on main" (#727); reg.json / comments.json are `gh api repos/R/issues/N/comments` output. A missing or unparseable
input file is a one-line error and exit 2, for every subcommand.
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
FENCE_RE = re.compile(r"(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1")      # [ \t]* not \s*: linear on newline runs; ``` and ~~~ fences


def unquoted(body: str) -> str:
    """A comment body minus fenced blocks (``` / ~~~) and `> ` quoted lines — the part its author actually asserted.
    Marker readers that must not honour a marker someone merely quoted call this first (comments are
    unauthenticated: every session writes under one login and anyone can quote or fence a marker). Indented
    code blocks, inline code spans and an unterminated fence still count as asserted — over-counting is the
    safe direction for a hint that is never authorisation."""
    text = FENCE_RE.sub("", body or "")
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith((">", "&gt;")))   # MCP issue_read entity-escapes `>`



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
BATCH_FILE_RE = re.compile(r"^experiments/(?:.*/)?batch_(\d+)\.json\Z", re.S)   # numbers are campaign-global; re.S/\Z: a NUL-fed name may hold a newline (#723)
RESERVE_RE = re.compile(r"<!-- batches by=([A-Za-z0-9_.\[\]-]+) lo=(\d+) hi=(\d+) issue=(\d+) token=([A-Za-z0-9_-]+) -->")
MAX_RESERVE = 9        # per request; a viewer round is one batch per release, so 3 is typical
BATCH_FLOOR = 14       # == tools/probe_batch.py HISTORICAL_ROUNDS: rounds 1..14 predate the manifests (a test pins the pair)


def batch_numbers(paths) -> set:
    """{n} for every experiments/**/batch_<n>.json repo path in `paths`."""
    return {int(m.group(1)) for m in map(BATCH_FILE_RE.match, map(str, paths or [])) if m}


TREE_RECIPE = "git fetch -q origin main && git ls-tree --full-tree -r -z --name-only origin/main -- experiments/ > tree.txt"


class InputError(ValueError):
    """An input file the CLI cannot trust; main() prints it as one line and exits 2 instead of a traceback (#727)."""


def tree_names(text: str) -> list:
    """Names in a `--tree` file: NUL-separated if it holds a NUL (`git ls-tree -z`, the documented recipe), else one per
    line — split on "\\n" exactly (git's own terminator; str.splitlines() would also cut a raw U+2028/U+0085 inside a
    name), a CRLF producer's "\\r" dropped, and git's surrounding C-quotes stripped: only the ASCII batch_<n>.json tail is
    read downstream and `(?:.*/)?` swallows an escaped middle, so no full unquoting is needed. Never per blank:
    `experiments/w x/batch_57.json` is one name, and a name lost here is a number `reserve` hands out twice (#723)."""
    if "\0" in text:
        return [n for n in text.split("\0") if n]
    return [n for n in (ln.rstrip("\r").strip('"') for ln in text.split("\n")) if n]


def on_main_batches(text: str) -> set:
    """The batch numbers on the default branch, from a `--tree` file's text -- failing CLOSED: a text that is not empty
    yet names nothing under experiments/ is never git's answer to TREE_RECIPE (that prints experiments/... names or
    nothing) but exactly what an unreadable producer decodes to -- UTF-16 from Windows PowerShell 5 `>` (one name per
    NUL-separated byte), a listing of the wrong tree -- and reading it as an empty on_main is a floor answer: numbers
    already on main handed out again (#727; before #723's bytes-faithful open() such a file at least crashed). A
    leading UTF-8 BOM (Windows PowerShell's `Out-File -Encoding utf8`, the producer the refusal recommends there) is dropped
    rather than left to hide the first name. An EMPTY text stays legal: a repository with no experiments/ yet."""
    names = tree_names(text.removeprefix("\ufeff"))
    if names and not any(n.startswith("experiments/") for n in names):
        raise InputError(f"{len(names)} name(s), none under experiments/ -- not readable `git ls-tree` output of the default "
                         f"branch (UTF-16 from Windows PowerShell `>`? the wrong tree?); regenerate it with `{TREE_RECIPE}` from "
                         f"bash or cmd (PowerShell: `git ls-tree ... | Out-File -Encoding utf8 tree.txt`, whose BOM is fine); an EMPTY "
                         f"file is how to say 'no experiments/ on main yet'")
    return batch_numbers(names)


def tree_input(path: str) -> set:
    """on_main from a `--tree` file: opened bytes-faithfully (no universal newlines, no decode crash on a non-UTF-8 name,
    #723), read fail-closed (on_main_batches, #727), a refusal naming the file."""
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
        text = fh.read()
    try:
        return on_main_batches(text)
    except InputError as e:
        raise InputError(f"--tree {path}: {e}") from None


def json_input(path: str):
    """json.load() of a CLI input file, an unparseable one (truncated, HTML, UTF-16) being an InputError that names it."""
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except ValueError as e:          # json.JSONDecodeError, or UnicodeDecodeError on a non-UTF-8 file
            raise InputError(f"{path}: not readable JSON ({e})") from None


def reservations(comments: list) -> list:
    """[{by, lo, hi, issue, token}] recorded on the registry issue, in creation order.
    Only coord's own (bot) comments count when the author is known: a human pasting a marker
    reserves nothing."""
    out = []
    for c in comments or []:
        user = (c.get("user") or {}).get("login", "")
        if user and not user.endswith("[bot]"):
            continue
        for by, lo, hi, issue, token in RESERVE_RE.findall(c.get("body") or ""):
            out.append({"by": by, "lo": int(lo), "hi": int(hi), "issue": int(issue), "token": token})
    return out


def pr_batches(prs: list, on_main: set) -> dict:
    """{pr_number: {n}} — the batch numbers each open PR ADDS: touching a batch file that is not on
    the default branch can only mean adding it (`gh pr list --json files` carries no status; a
    file that also exists on main is an edit of that manifest, or a merge conflict automerge
    already routes)."""
    out = {}
    for p in prs or []:
        nums = batch_numbers(f.get("path", "") for f in (p.get("files") or [])) - on_main
        if nums:
            out[int(p["number"])] = nums
    return out


def next_batch(k: int, on_main: set, reserved: list, taken: set) -> tuple:
    """(lo, hi): k fresh numbers above everything on main, everything reserved and everything any
    open PR adds (`taken`) — a reservation never hands out a number somebody already staged."""
    k = max(1, min(int(k), MAX_RESERVE))
    top = max([BATCH_FLOOR, *on_main, *taken, *(r["hi"] for r in reserved)])
    return top + 1, top + k


def _rng(lo: int, hi: int) -> str:
    return str(lo) if lo == hi else f"{lo}..{hi}"


def reserve(k: int, by: str, issue: int, token: str, url: str, registry: int,
            on_main: set, reserved: list, prs: list) -> dict:
    """The `/batches k` decision: {lo, hi, seen, registry_body, reply}. Idempotent per requesting
    comment (`token`): a re-run answers with the range already recorded and posts nothing new."""
    prior = next((r for r in reserved if r["token"] == str(token)), None)
    if prior:
        lo, hi, seen = prior["lo"], prior["hi"], True
    else:
        taken = set().union(*pr_batches(prs, on_main).values())
        (lo, hi), seen = next_batch(k, on_main, reserved, taken), False
    marker = f"<!-- batches by={by} lo={lo} hi={hi} issue={int(issue)} token={token} -->"
    then = f" (then {_rng(lo + 1, hi)}, one per release)" if hi > lo else ""
    return {
        "lo": lo, "hi": hi, "seen": seen,
        "registry_body": f"🔢 batches **{_rng(lo, hi)}** → @{by} for #{int(issue)} (requested in {url}). {marker}",
        "reply": (f"🔢 @{by} — reserved viewer batch number(s) **{_rng(lo, hi)}** for #{int(issue)} (registry: #{registry}). "
                  f"Stage with `tools/probe_batch.py stage … --batch {lo}`{then}; tools that number batches "
                  f"themselves honour `RVT_BATCH_FLOOR={lo}` in the environment. Name the numbers in your record "
                  "and upload instructions. Nobody else can be handed them, and `coord` flags any open PR that "
                  "reuses one (`batch-clash`, held by automerge until renumbered)."),
    }


def batch_judgement(prs: list, reserved: list, on_main: set) -> list:
    """Which open PRs must renumber which batch files, and to what.

    A number belongs to the ISSUE it was reserved for — every engineer session here may run under
    one login, so the login cannot discriminate; a PR speaks for the issues its body closes/refs
    and for itself. Unreserved numbers belong to the OLDEST open PR that adds them (automerge's
    duplicate rule). Every other PR adding the number must move. Returns, oldest PR first,
      [{pr, nums: [n, ...], key, message}]  — `key` dedupes the comment, `message` is its body.
    """
    added = pr_batches(prs, on_main)
    linked = {}
    for p in prs or []:
        r = refs(p.get("body") or "")
        linked[int(p["number"])] = set(r["closing"]) | set(r["refs"]) | {int(p["number"])}
    movers = {}                                                   # pr -> {n: cause}
    for n in sorted(set().union(*added.values())):
        adders = sorted(pr for pr, nums in added.items() if n in nums)
        res = next((r for r in reserved if r["lo"] <= n <= r["hi"]), None)
        if res:
            owners = [pr for pr in adders if res["issue"] in linked[pr]]
            cause = f"reserved for #{res['issue']}"
        else:
            owners = adders[:1]
            cause = f"kept by the older PR #{adders[0]}"
        if len(adders) == 1 and owners == adders:
            continue
        for pr in adders:
            if pr not in owners:
                movers.setdefault(pr, {})[n] = cause
    taken = set().union(*added.values())
    out = []
    for pr in sorted(movers):
        nums = sorted(movers[pr])
        lo, hi = next_batch(len(nums), on_main, reserved, taken)
        taken |= set(range(lo, hi + 1))                            # two movers are never sent to the same range
        by_cause = {}
        for n, cause in sorted(movers[pr].items()):
            by_cause.setdefault(cause, []).append(f"`batch_{n}.json`")
        causes = "; ".join(f"{', '.join(files)} — {cause}" for cause, files in by_cause.items())
        out.append({"pr": pr, "nums": nums, "key": "batch-clash-" + "_".join(map(str, nums)),
                    "message": (f"🔢 **Viewer batch-number clash** — this PR adds batch number(s) another stream owns: {causes}. "
                                f"Renumber {_rng(nums[0], nums[-1]) if nums == list(range(nums[0], nums[-1] + 1)) else ', '.join(map(str, nums))} "
                                f"→ **{_rng(lo, hi)}**: re-stage with `tools/probe_batch.py stage … --batch {lo}` (or "
                                f"`RVT_BATCH_FLOOR={lo}` for tools that number batches themselves), `git rm` the old "
                                "`batch_<n>.json`, commit the new manifests, and fix the record / upload instructions so a "
                                "verdict never names a number that means two files. Reserve first next time: comment "
                                "`/batches <k>` on your issue (CLAUDE.md §2). automerge holds this PR while it carries "
                                "`batch-clash`; coord re-judges when the PR is edited and every hour, and clears the label itself.")})
    return out


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
    k = sub.add_parser("locks", help="print the standing claim locks of an issue as JSON (first = holder)")
    k.add_argument("--comments", required=True, help="JSON file: the issue's comments (gh api .../comments)")
    k.add_argument("--assignees", default="", help="comma-separated current assignee logins")
    for name, h in (("reserve", "print JSON: the /batches decision {lo, hi, seen, registry_body, reply}"),
                    ("batchjudge", "print JSON: open PRs that must renumber viewer batches [{pr, nums, key, message}]")):
        b = sub.add_parser(name, help=h)
        b.add_argument("--tree", required=True, help=f"text file: default-branch paths, NUL-separated ({TREE_RECIPE}); one-per-line output is read too; refused if non-empty with nothing under experiments/")
        b.add_argument("--registry", required=True, help="JSON file: the batch-registry issue's comments ([] when none)")
        b.add_argument("--prs", required=True, help="JSON file: gh pr list --json number,author,body,files")
        if name == "reserve":
            b.add_argument("--k", type=int, default=1)
            b.add_argument("--by", required=True)
            b.add_argument("--issue", type=int, required=True)
            b.add_argument("--token", required=True, help="id of the requesting comment (idempotency key)")
            b.add_argument("--url", default="", help="html url of the requesting comment")
            b.add_argument("--registry-number", type=int, default=0)
    a = ap.parse_args(argv)
    try:
        return run(a)
    except InputError as e:
        print(f"coord.py {a.cmd}: {e}", file=sys.stderr)
    except OSError as e:                 # a missing/unreadable input file: one line, not a traceback (#727)
        if not e.filename:
            raise
        print(f"coord.py {a.cmd}: cannot read {e.filename}: {e.strerror or e}", file=sys.stderr)
    return 2


def run(a) -> int:
    """The parsed subcommand; input trouble surfaces as InputError / OSError for main() to word."""
    if a.cmd == "refs":
        print(json.dumps(refs(sys.stdin.read())))
        return 0
    if a.cmd == "taskshape":
        return 0 if is_task_shaped(sys.stdin.read()) else 1
    if a.cmd == "locks":
        print(json.dumps(standing_locks(json_input(a.comments), [x for x in a.assignees.split(",") if x])))
        return 0
    if a.cmd in ("reserve", "batchjudge"):
        on_main, reserved, prs = tree_input(a.tree), reservations(json_input(a.registry)), json_input(a.prs)
        if a.cmd == "reserve":
            print(json.dumps(reserve(a.k, a.by, a.issue, a.token, a.url, a.registry_number, on_main, reserved, prs)))
        else:
            print(json.dumps(batch_judgement(prs, reserved, on_main)))
        return 0
    if a.cmd == "reqfile":
        with open(a.path, encoding="utf-8") as fh:
            print(json.dumps(reqfile(fh.read(), a.path)))
        return 0
    if a.cmd == "queue":
        for i in queue(json_input(a.issues), json_input(a.prs)):
            print(i["number"])
        return 0
    data = json_input(a.issues if a.cmd == "similar" else a.prs)
    if a.cmd == "similar":
        for hit in similar(a.title, data, a.self):
            print(_fmt_hit(*hit))
    else:
        for number, login in rivals(a.issue, data, a.self):
            print(number, login)
    return 0


if __name__ == "__main__":
    sys.exit(main())
