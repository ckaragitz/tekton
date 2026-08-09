#!/usr/bin/env python3
"""The tech-lead desk: board, brief, queue pick, hygiene sweep, steer log (stdlib only).

tekton's coding sessions are the project's tech leads (docs/process/AUTONOMY.md):
they own the backlog and also build; humans steer. This file is the deterministic
half of the desk — everything that needs no judgement — so it can run unattended on
the built-in GITHUB_TOKEN from .github/workflows/{board,techlead,worker}.yml AND from
any coding session (`GH_TOKEN`/`GITHUB_TOKEN` env, or a logged-in `gh`). The
judgement half is the charter in .github/prompts/techlead.md, which the scheduled
planner and human-started sessions both follow, starting from `brief`.

  board   re-render the pinned board issue (label `board`; created + pinned if missing):
          in progress / in review with the exact merge blocker / next up / waiting on a
          human / untriaged steers / done this week / health. Runs the sweep first.
  brief   the state digest a tech-lead pass starts from (markdown, or --json)
  pick    the issue the unattended worker should take next -> JSON on stdout (+ GITHUB_OUTPUT),
          or exit 3 with the reason (paused, daily cap, WIP limit, nothing eligible)
  sweep   hygiene the merge bots do not do: re-queue issues whose PR is `bot-stuck`,
          free issues whose worker died (`bot-working` with nothing to show), nudge and
          eventually close drafts nobody has touched for days
  steer   log a human steer verbatim as a `steer` issue BEFORE acting on it:
            python3 tools/dev/techlead.py steer "what they said" --by <login>
  claim   claim-and-VERIFY one issue for this session (steer #90): assign me, wait, confirm I am the
          earliest standing assignee and lock, post the session-tagged 🔒 — exit 4 (holder printed)
          if someone, or another session of mine, was first:  techlead.py claim 24 --session laptop
  mine    my assigned issues, each judged `this-session` / `active-elsewhere (hands off)` / `idle,
          resumable` from lock session tags and recent activity — the resume rule for a fresh session
  config  print one knob (dotted key) from the merged config, for workflows with a checkout
  labels  create the label vocabulary this system relies on
  hello   the SessionStart banner (never fails; offline-safe; a few small calls at most)

Config: .github/autonomy.json (authoritative; DEFAULTS below only fill missing keys).
Repo:   --repo owner/name, else $GITHUB_REPOSITORY, else the `origin` remote.

The merge machine itself is bash in .github/workflows/automerge.yml on purpose: a broken
copy of this file on `main` must never be able to halt merging. `pr_status()` below only
DESCRIBES what automerge will do; tests/test_techlead.py pins the two vocabularies together.
"""
import argparse
import datetime as _dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location("coord", os.path.join(HERE, "coord.py"))
coord = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(coord)
labels_of = coord.label_names

DEFAULTS = {
    "board": {"label": "board", "recent_days": 7, "next_up": 10,
              "title": "📋 Board — what the tech leads are doing, reviewing, planning, and waiting on (auto-updated)"},
    "planner": {"enabled": True, "ready_floor": 4, "ready_ceiling": 12, "max_new_issues_per_run": 5, "max_turns": 60},
    "worker": {"enabled": True, "eligible": "auto", "wip_limit": 2, "max_runs_per_day": 4,
               "allow_hot_file": False, "max_turns": 120, "branch_prefix": "bot/"},
    "pipeline": {"quiet_minutes": 90, "max_fix_attempts": 3, "fix_grace_minutes": 15, "review_wait_minutes": 20, "review_stuck_minutes": 240,
                 "stale_draft_days": 5, "close_stale_days": 14, "requeue_stuck_after_hours": 24, "worker_lease_hours": 3},
    "pause_label": "bots-paused",
}

# The label vocabulary (name -> color, description). `ensure_labels` (every board run) creates
# what is missing; workflows only ever `gh label create NAME` bare, so this table owns the words.
LABELS = {
    "steer": ("0e8a16", "A human steer, logged verbatim; the tech leads triage it into work"),
    "intake": ("0e8a16", "Free-form issue filed by a human; triaged by the tech leads like a steer"),
    "triaged": ("bfdadc", "Steer/intake processed: derived issues filed and linked"),
    "planned": ("c5def5", "Filed by the tech-lead planner from the program goals"),
    "from-steer": ("c5def5", "Derived from a logged steer (see Refs in the body)"),
    "ready": ("0e8a16", "Doable now from a fresh clone; unassigned = free to claim (/next hands out the top one)"),
    "auto": ("1d76db", "Cleared for the unattended worker (fresh-clone doable, clear DONE, no hardware)"),
    "bot-working": ("5319e7", "Held by the unattended worker right now"),
    "bot-stuck": ("b60205", "Bots exhausted their fix budget on this PR; its issue is re-queued with context"),
    "retry": ("fbca04", "Re-queued after a stuck/abandoned attempt: continue the existing branch"),
    "needs-decision": ("b60205", "A human must answer the question in this issue before work continues"),
    "needs-human": ("b60205", "GitHub itself refused the merge; a person must look (rare)"),
    "session-merge": ("1d76db", "Bots may not merge this (workflow files / reviewer edit); the next coding session squash-merges it"),
    "needs-rebase": ("d93f0b", "Conflicts with main; the rebase job (or the author) must merge main in"),
    "needs-issue": ("b60205", "PR has no linked issue (Closes #N / Refs #N)"),
    "overlap": ("d93f0b", "Another open PR or another assignee targets the same issue"),
    "stacked": ("fbca04", "Base is another PR's branch, not the default branch"),
    "duplicate-pr": ("d93f0b", "A second open PR for an issue another PR already closes; the older one wins"),
    "stale": ("cfd3d7", "No commits for days; will be closed and its issue re-queued unless it moves"),
    "wip": ("cfd3d7", "Holds a draft: automerge will not auto-mark it ready"),
    "do-not-merge": ("000000", "Holds a PR from automerge entirely"),
    "merge-when-green": ("0e8a16", "Human approval substituting for the AI verdict (must be applied by a non-author)"),
    "board": ("5319e7", "The auto-rendered task board issue"),
    "tracking": ("5319e7", "Context-only issue: never in the queue"),
    "bots-paused": ("000000", "Put on the board issue to pause the planner and the worker (merging continues)"),
    "epic": ("3e4b9e", "Multi-issue objective; children are linked task issues"),
    "area:process": ("cfd3d7", "How work flows: automation, coordination, docs of the process"),
}

REVIEWER_WORKFLOW = ".github/workflows/claude-review.yml"
# Job names of the repo's own bot workflows. Their check runs can land on a PR head (pull_request /
# pull_request_target jobs, or a cancelled run from a concurrency group) and must never be mistaken
# for CI by the merge gate or the board. automerge.yml carries the same list (IGNORED_CHECKS there);
# tests/test_techlead.py fails when a bot workflow gains a job that neither list knows.
BOT_CHECK_NAMES = frozenset({
    "automerge", "claude-review", "fix", "ci-autofix", "claude",   # merge machine, reviewer + dispatched fix pass, mention bot
    "render", "refresh-board",                                     # board.yml, and the planner/worker's board-refresh job
    "claim", "single-holder", "issue-intake", "pr-check", "sweep",  # coord.yml
    "gate", "plan",                                                # techlead.yml
    "pick", "implement",                                           # worker.yml
    "file-issues",                                                 # requirements.yml
})


def is_bot_check(name: str) -> bool:
    return name in BOT_CHECK_NAMES or str(name).startswith("claude")
BOT_SUFFIX = "[bot]"
VERDICT_RE = re.compile(r"<!-- claude-review: (approve|nits|changes) sha=([0-9a-f]{7,40}) -->")
ATTEMPT_RE = re.compile(r"<!-- claude-autofix attempt=\d+ -->")
RESET_MARK = "<!-- claude-autofix reset -->"
EXHAUSTED_RE = re.compile(r"<!-- claude-autofix exhausted sha=([0-9a-f]{7,40}) -->")
RETRY_BRANCH_RE = re.compile(r"<!-- retry-branch: ([A-Za-z0-9._/-]+) -->")
BOARD_BEGIN, BOARD_END = "<!-- board:begin -->", "<!-- board:end -->"


# ─────────────────────────────── small utils ────────────────────────────────

def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def parse_ts(s: str):
    if not s:
        return None
    return _dt.datetime.strptime(s.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")


def iso(t: _dt.datetime) -> str:
    return t.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def at(ts) -> str:
    """Absolute short UTC stamp for the board ('08-09 05:11'). Absolute on purpose: the board is
    re-rendered on every event and only rewritten when its content changes; relative ages would
    make every render an edit."""
    t = parse_ts(ts) if isinstance(ts, str) else ts
    return t.astimezone(_dt.timezone.utc).strftime("%m-%d %H:%M") if t else "?"


def age_txt(then, now) -> str:
    """Relative age for the brief and the banner (never for the board body)."""
    if then is None:
        return "?"
    s = max(0, int((now - then).total_seconds()))
    if s < 5400:
        return f"{s // 60} min"
    if s < 172800:
        return f"{s // 3600} h"
    return f"{s // 86400} d"


def deep_merge(base: dict, over: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(text=None) -> dict:
    if text is None:
        try:
            with open(os.path.join(ROOT, ".github", "autonomy.json"), encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            text = "{}"
    try:
        over = json.loads(text or "{}")
    except ValueError:
        over = {}
    over.pop("_doc", None)
    return deep_merge(DEFAULTS, over)


def slugify(title: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s[:limit].rstrip("-") or "work"


def is_bot(login: str) -> bool:
    return (login or "").endswith(BOT_SUFFIX)


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def is_stuck(pr: dict) -> bool:
    return "bot-stuck" in pr["labels"] or pr["review"]["exhausted"]


def is_bot_pr(pr: dict, cfg: dict) -> bool:
    return pr["head_ref"].startswith(cfg["worker"]["branch_prefix"]) or is_bot(pr["user"])


def closing_map(prs: list) -> dict:
    """issue number -> [numbers of open PRs whose body closes it]."""
    out = {}
    for p in prs:
        for n in p["closing"]:
            out.setdefault(n, []).append(p["number"])
    return out


# ─────────────────────────────── GitHub client ──────────────────────────────

class GitHubError(RuntimeError):
    def __init__(self, status, msg):
        super().__init__(f"GitHub API {status}: {msg}")
        self.status = status


class GH:
    """Minimal REST/GraphQL client on urllib (honours HTTPS_PROXY). Paths are repo-relative."""

    def __init__(self, repo: str, token: str, timeout: float = 20.0):
        self.repo = repo
        self.token = token
        self.api = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
        self.timeout = timeout
        self.calls = 0

    # -- transport (overridden by the test fake) --
    def _send(self, method, url, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "tekton-techlead")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None), r.headers.get("Link", "")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                payload = json.loads(raw) if raw else None
            except ValueError:
                payload = {"message": raw.decode("utf-8", "replace")[:300]}
            return e.code, payload, ""

    def _url(self, path, params=None):
        url = path if path.startswith("http") else f"{self.api}/repos/{self.repo}/{path.lstrip('/')}"
        if params:
            q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url += ("&" if "?" in url else "?") + q
        return url

    @staticmethod
    def _check(status, data, method, path, ok):
        if status not in ok:
            msg = (data or {}).get("message", "") if isinstance(data, dict) else str(data)[:300]
            raise GitHubError(status, f"{method} {path}: {msg}")

    def request(self, method, path, body=None, params=None, ok=(200, 201, 202, 204)):
        status, data, _ = self._send(method, self._url(path, params), body)
        self._check(status, data, method, path, ok)
        return data

    def get(self, path, **params):
        return self.request("GET", path, params=params)

    def paged(self, path, max_pages=10, **params):
        params.setdefault("per_page", 100)
        out, url, pages = [], self._url(path, params), 0
        while url and pages < max_pages:
            status, data, link = self._send("GET", url)
            self._check(status, data, "GET", path, (200,))
            out.extend(data or [])
            m = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
            url = m.group(1) if m else None
            pages += 1
        return out

    def post(self, path, body=None):
        return self.request("POST", path, body=body)

    def patch(self, path, body=None):
        return self.request("PATCH", path, body=body)

    def delete(self, path, body=None):
        return self.request("DELETE", path, body=body, ok=(200, 204, 404))

    def graphql(self, query, variables=None):
        endpoint = os.environ.get("GITHUB_GRAPHQL_URL") or self.api + "/graphql"
        data = self.request("POST", endpoint, body={"query": query, "variables": variables or {}})
        if isinstance(data, dict) and data.get("errors"):
            raise GitHubError(200, "; ".join(e.get("message", "?") for e in data["errors"]))
        return (data or {}).get("data")

    # -- conveniences --
    def comment(self, number, body):
        return self.post(f"issues/{number}/comments", {"body": body})

    def comments(self, number):
        return self.paged(f"issues/{number}/comments")

    def comment_once(self, number, key, body, existing=None):
        """One comment per (number, key). Pass `existing` bodies when already fetched."""
        marker = f"<!-- techlead:{key} -->"
        bodies = existing if existing is not None else [c.get("body") or "" for c in self.comments(number)]
        if any(marker in b for b in bodies):
            return False
        self.comment(number, body.rstrip() + "\n\n" + marker)
        return True

    def add_labels(self, number, *names):
        return self.post(f"issues/{number}/labels", {"labels": list(names)})

    def remove_label(self, number, name):
        return self.delete(f"issues/{number}/labels/{urllib.parse.quote(name)}")

    def edit_issue(self, number, **fields):
        return self.patch(f"issues/{number}", fields)

    def unassign(self, number, logins):
        if logins:
            self.delete(f"issues/{number}/assignees", body={"assignees": list(logins)})


def resolve_repo(explicit="") -> str:
    if explicit:
        return explicit
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    try:
        url = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"], capture_output=True,
                             text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.\s]+?)(?:\.git)?/?$", url) or re.search(r"/git/([^/]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def resolve_token(gh_cli_timeout=5) -> str:
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=gh_cli_timeout)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


# ─────────────────────────────── snapshot ───────────────────────────────────

def _same_sha(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def parse_review_state(comment_bodies: list, head_sha: str) -> dict:
    """Verdict for THIS head sha, fix attempts since the last reset marker, exhaustion —
    the same reading automerge.yml / claude-review.yml take of the same markers."""
    verdict, attempts, exhausted, last_summary = None, 0, False, ""
    for b in comment_bodies:
        b = b or ""
        for v, sha in VERDICT_RE.findall(b):
            if _same_sha(head_sha, sha):
                verdict = v
                last_summary = (b.strip().splitlines() or [""])[0][:160]
        if RESET_MARK in b:
            attempts, exhausted = 0, False
        if ATTEMPT_RE.search(b):
            attempts += 1
        if any(_same_sha(head_sha, sha) for sha in EXHAUSTED_RE.findall(b)):
            exhausted = True
    return {"verdict": verdict, "attempts": attempts, "exhausted": exhausted, "last_summary": last_summary}


def summarize_checks(check_runs: list) -> dict:
    """CI gate exactly as automerge sees it: the repo's own bot jobs are not CI (BOT_CHECK_NAMES)."""
    runs = [c for c in check_runs or [] if not is_bot_check(c.get("name", ""))]
    pending = [c["name"] for c in runs if c.get("status") != "completed"]
    bad = [c["name"] for c in runs if c.get("status") == "completed" and c.get("conclusion") not in ("success", "neutral", "skipped")]
    ok = [c["name"] for c in runs if c.get("conclusion") == "success"]
    return {"total": len(runs), "pending": pending, "bad": bad, "ok": len(ok),
            "green": bool(runs) and not pending and not bad and bool(ok)}


def enrich_pr(gh: GH, p: dict) -> dict:
    """One open PR (an item of GET /pulls) plus what the board / sweep / pick need.
    3 calls always (check-runs, comments, files); mergeability and the head-commit date only for
    the lanes that read them (approved+green / draft or stuck)."""
    n, sha = p["number"], p["head"]["sha"]
    labels = labels_of(p)
    try:
        checks = summarize_checks(gh.get(f"commits/{sha}/check-runs", per_page=100).get("check_runs", []))
    except GitHubError:
        checks = summarize_checks([])
    bodies = [c.get("body") or "" for c in gh.comments(n)]
    review = parse_review_state(bodies, sha)
    try:
        files = [f.get("filename", "") for f in gh.paged(f"pulls/{n}/files", max_pages=3)]
    except GitHubError:
        files = []
    mergeable, mergeable_state = None, "unknown"
    if checks["green"] and review["verdict"] in ("approve", "nits"):
        d = gh.get(f"pulls/{n}")
        mergeable, mergeable_state = d.get("mergeable"), d.get("mergeable_state", "unknown")
    head_date = None
    if p.get("draft") or "bot-stuck" in labels or review["exhausted"]:
        try:
            head_date = gh.get(f"commits/{sha}")["commit"]["committer"]["date"]
        except GitHubError:
            head_date = p.get("updated_at")
    r = coord.refs(p.get("body") or "")
    return {
        "number": n, "title": p.get("title", ""), "user": (p.get("user") or {}).get("login", ""),
        "draft": bool(p.get("draft")), "labels": labels, "body": p.get("body") or "",
        "head_sha": sha, "head_ref": p["head"]["ref"], "created_at": p.get("created_at"),
        "head_date": head_date or p.get("updated_at"), "mergeable": mergeable, "mergeable_state": mergeable_state,
        "checks": checks, "review": review, "comment_bodies": bodies, "closing": r["closing"], "refs": r["refs"],
        "touches_workflows": any(f.startswith(".github/workflows/") for f in files),
        "touches_reviewer": REVIEWER_WORKFLOW in files,
    }


def fetch_issues(gh: GH) -> list:
    return [i for i in gh.paged("issues", state="open") if not i.get("pull_request")]


def snapshot(gh: GH, cfg: dict, now=None, with_runs=True) -> dict:
    now = now or utcnow()
    cutoff = now - _dt.timedelta(days=int(cfg["board"]["recent_days"]))
    issues = fetch_issues(gh)
    closed = [i for i in gh.paged("issues", state="closed", since=iso(cutoff), max_pages=3)
              if not i.get("pull_request") and parse_ts(i.get("closed_at") or "") and parse_ts(i["closed_at"]) >= cutoff]
    prs = [enrich_pr(gh, p) for p in sorted(gh.paged("pulls", state="open"), key=lambda p: p["number"])[:30]]
    merged = [p for p in gh.get("pulls", state="closed", sort="updated", direction="desc", per_page=50)
              if p.get("merged_at") and parse_ts(p["merged_at"]) >= cutoff]
    runs = []
    if with_runs:
        try:
            runs = gh.get("actions/runs", per_page=60).get("workflow_runs", [])
        except GitHubError:
            runs = []
    return {"now": iso(now), "repo": gh.repo, "issues": issues, "closed": closed, "prs": prs,
            "merged": merged, "runs": runs}


# ─────────────────────────────── model ──────────────────────────────────────

HUMAN_REASONS = {
    "needs-decision": "a person must answer the question in the issue",
    "needs-revit-desktop": "needs someone with desktop Revit",
    "needs-viewer": "needs an Autodesk-viewer upload (login) — stage with probe_batch, a human uploads",
    "owner-machine": "needs the quarantined samples/ corpus on the owner's machine",
    "blocked": "blocked on something external (see issue)",
    "needs-human": "flagged by a bot as needing a person (see its last comment)",
}


def pr_status(pr: dict, cfg: dict) -> tuple:
    """(text of the exact thing standing between this PR and merge, lane).
    Mirrors the decision order of .github/workflows/automerge.yml — keep the two in step;
    tests/test_techlead.py::test_board_and_automerge_share_one_vocabulary is the tripwire."""
    L = set(pr["labels"])
    ch, rv = pr["checks"], pr["review"]
    mx = int(cfg["pipeline"]["max_fix_attempts"])
    quiet_min = int(cfg["pipeline"]["quiet_minutes"])
    note = " · ⚠️ no linked issue (`Closes #N`)" if "needs-issue" in L else ""
    grace = int(cfg["pipeline"]["fix_grace_minutes"])
    fix = (f"your session first, bot fix pass after {grace} quiet min · attempts {min(rv['attempts'], mx)}/{mx}"
           + (" → **bot-stuck**, issue re-queued after a quiet day" if is_stuck(pr) else ""))
    if "do-not-merge" in L:
        return "⏸ held by `do-not-merge`" + note, "held"
    if "session-merge" in L:
        return ("🧑‍💻 waiting for **a coding session** (preferably not the author's) to squash-merge it: it changes "
                "`.github/workflows/**`, which the Actions token may not merge; prerequisites already met and to be re-checked "
                "at merge time — ✅/🟡 verdict for this exact head + green CI; read the workflow diff once more") + note, "session"
    if "needs-human" in L:
        why = ("no independent review verdict could be produced for a workflow-file PR — a collaborator other than the author "
               "applies `merge-when-green` (or the owner merges)" if pr["touches_workflows"] and rv["verdict"] not in ("approve", "nits")
               else "GitHub refused the merge — see the bot's last comment")
        return f"🧑 needs a human: {why}" + note, "human"
    if "duplicate-pr" in L:
        return "👯 a second PR for an issue another open PR already closes (older wins) — the planner closes one" + note, "human"
    if ch["total"] == 0:
        return "⏳ no CI checks on this commit yet (automerge dispatches CI itself)" + note, "ci"
    if ch["pending"]:
        return f"⏳ CI running ({len(ch['pending'])})" + note, "ci"
    if ch["bad"]:
        return f"🟥 CI red ({', '.join(ch['bad'][:3])}) · {fix}" + note, "red"
    v = rv["verdict"]
    approved = f"✅ {v}" if v in ("approve", "nits") else ("🏷️ `merge-when-green` (human approval; counts if applied by a non-author)" if "merge-when-green" in L else "")
    if not approved:
        if v == "changes":
            return f"🟢 CI · 🛑 changes requested · {fix}" + (" · draft" if pr["draft"] else "") + note, "changes"
        if pr["touches_reviewer"]:
            return ("🟢 CI · ⏳ changes the reviewer workflow itself: its own review run refuses a modified copy, so automerge "
                    "re-requests the review from `main`'s reviewer — an independent verdict for this head is **required** "
                    "before any session may merge it (`needs-human` = `merge-when-green` from a non-author if none can be produced)") + note, "review"
        return ("🟢 CI · ⏳ no review verdict for this commit yet (automerge re-requests it after "
                f"{cfg['pipeline']['review_wait_minutes']} min; `bot-stuck` after {cfg['pipeline']['review_stuck_minutes']})") + note, "review"
    if pr["draft"]:
        if "wip" in L:
            return f"🟢 CI · {approved} · draft held by `wip` (remove the label or mark ready to merge)" + note, "held"
        eta = (parse_ts(pr["head_date"]) or utcnow()) + _dt.timedelta(minutes=quiet_min)
        return f"🟢 CI · {approved} · **draft** — auto-marked ready ≈ {at(eta)} UTC ({quiet_min} quiet min after the last push), then merged" + note, "draft"
    if pr["touches_workflows"]:
        return f"🟢 CI · {approved} · changes `.github/workflows/**` → `session-merge`: **the next coding session squash-merges it** (or `AUTOMERGE_TOKEN` makes it automatic)" + note, "session"
    if pr["mergeable_state"] == "dirty" or pr.get("mergeable") is False:
        return f"🟢 CI · {approved} · ⚠️ conflicts with main → rebase job dispatched (`needs-rebase`)" + note, "conflict"
    return f"🟢 CI · {approved} → merges on the next automerge sweep (≤ 30 min)" + note, "merging"


def classify(snap: dict, cfg: dict, now=None) -> dict:
    now = now or parse_ts(snap["now"])
    issues, prs = snap["issues"], snap["prs"]
    pr_for = closing_map(prs)
    queue = coord.queue(issues, prs)
    steers, waiting, progress, others = [], [], [], []
    for i in sorted(issues, key=lambda i: (coord.priority(i), i["number"])):
        L = set(labels_of(i))
        entry = {"number": i["number"], "title": i.get("title", ""), "labels": sorted(L),
                 "assignees": [a["login"] for a in i.get("assignees") or []],
                 "user": (i.get("user") or {}).get("login", ""), "priority": coord.priority(i),
                 "created_at": i.get("created_at"), "updated_at": i.get("updated_at"),
                 "prs": pr_for.get(i["number"], []), "body": i.get("body") or ""}
        if L & {"steer", "intake"}:
            entry["triaged"] = "triaged" in L
            steers.append(entry)
            continue
        if cfg["board"]["label"] in L:
            continue
        gated = [g for g in coord.GATED if g in L]
        if gated and "tracking" not in L:
            entry["why"] = [HUMAN_REASONS.get(g, g) for g in gated]
            waiting.append(entry)
        if (entry["assignees"] or L & set(coord.HELD)) and "tracking" not in L:
            progress.append(entry)
        elif not gated and "ready" not in L and not (L & set(coord.NOT_WORK)):
            others.append(entry)
    review = []
    for p in prs:
        status, lane = pr_status(p, cfg)
        review.append({"number": p["number"], "title": p["title"], "user": p["user"], "labels": p["labels"],
                       "head_ref": p["head_ref"], "closing": p["closing"], "refs": p["refs"],
                       "status": status, "lane": lane, "stuck": is_stuck(p), "bot": is_bot_pr(p, cfg)})
    human_prs = [r for r in review if r["lane"] == "human"]
    session_prs = [r for r in review if r["lane"] == "session"]
    board = find_board_issue(issues, cfg)
    health = {
        "open_issues": len(issues), "ready_unassigned": len(queue), "in_progress": len(progress),
        "in_review": len(review), "waiting_human": len(waiting) + len(human_prs), "session_merge": len(session_prs),
        "steers_untriaged": len([s for s in steers if not s["triaged"]]),
        "bot_prs_open": len([r for r in review if r["bot"]]), "stuck_prs": len([r for r in review if r["stuck"]]),
        "ready_floor": int(cfg["planner"]["ready_floor"]), "ready_ceiling": int(cfg["planner"]["ready_ceiling"]),
        "bots": bot_health(snap.get("runs") or []),
        "paused": bool(board and cfg["pause_label"] in labels_of(board)),
        "board_issue": board["number"] if board else None,
    }
    warnings = []
    if health["ready_unassigned"] < health["ready_floor"]:
        warnings.append(f"ready queue below floor ({health['ready_unassigned']} < {health['ready_floor']}) — the planner replenishes it on its next run; any session may run a tech-lead pass now")
    if health["steers_untriaged"]:
        oldest = min((s["created_at"] for s in steers if not s["triaged"]), default="")
        warnings.append(f"{health['steers_untriaged']} untriaged steer(s), oldest logged {at(oldest)} UTC")
    if health["stuck_prs"]:
        warnings.append(f"{health['stuck_prs']} PR(s) exhausted the bots' fix budget — their issues are re-queued for a fresh attempt")
    if health["paused"]:
        warnings.append("`bots-paused` is set on this board: planner and worker are idle (reviews and merges continue)")
    if session_prs:
        warnings.append("PR(s) waiting for ANY coding session to squash-merge (bots may not: workflow files / reviewer edit): "
                        + " ".join(f"#{r['number']}" for r in session_prs) + " — the first session to start does it (CLAUDE.md §4 step 1)")
    health["warnings"] = warnings
    return {"now": iso(now), "repo": snap["repo"], "steers": steers, "waiting": waiting, "waiting_prs": human_prs, "session_prs": session_prs,
            "progress": progress, "review": review, "next_up": [
                {"number": i["number"], "title": i.get("title", ""), "priority": coord.priority(i),
                 "labels": sorted(labels_of(i)), "created_at": i.get("created_at")} for i in queue],
            "others": others,
            "done_issues": [{"number": i["number"], "title": i.get("title", ""), "closed_at": i.get("closed_at"),
                             "reason": i.get("state_reason") or "completed"} for i in snap["closed"]],
            "done_prs": [{"number": p["number"], "title": p.get("title", ""), "merged_at": p.get("merged_at"),
                          "user": (p.get("user") or {}).get("login", "")} for p in snap["merged"]],
            "health": health}


def bot_health(runs: list) -> dict:
    """Latest run per workflow name: conclusion + when (for the Health line)."""
    out = {}
    for r in runs:
        name = r.get("name") or ""
        if name not in out:
            out[name] = {"conclusion": r.get("conclusion") or r.get("status"), "at": r.get("created_at"),
                         "url": r.get("html_url", ""), "event": r.get("event", "")}
    return out


# ─────────────────────────────── render ─────────────────────────────────────

def _p(pr): return f"P{pr}" if pr < 3 else "P–"


def _lbl(labels, keep=("area:", "hot-file", "auto", "retry", "good-first-pick", "from-steer", "planned")):
    return " ".join(f"`{l}`" for l in labels if any(l.startswith(k) for k in keep))


def render_board(model: dict, cfg: dict, repo: str) -> str:
    h = model["health"]
    L = [BOARD_BEGIN,
         f"_Rendered {at(model['now'])} UTC by `board` (token-free; every 20 min and when issues/PRs open, close or become ready). "
         "Do not edit this body — it is overwritten. Talk in comments; steer with `/steer <text>`. All times UTC._",
         "",
         f"**{h['in_progress']} in progress · {h['in_review']} in review · {h['ready_unassigned']} ready & free · "
         f"{h['session_merge']} for a session to merge · {h['waiting_human']} waiting on a human · {h['steers_untriaged']} untriaged steer(s)** — "
         f"[START HERE](https://github.com/{repo}/issues/25) · [how this works](https://github.com/{repo}/blob/main/docs/process/AUTONOMY.md) · "
         f"[goals](https://github.com/{repo}/blob/main/docs/PROGRAM.md) · [standing steers](https://github.com/{repo}/blob/main/docs/STEERING.md)"]
    if h["warnings"]:
        L.append("")
        L.extend(f"> ⚠️ {w}" for w in h["warnings"])
    L += ["", "## 🧭 Steers from humans"]
    if model["steers"]:
        L += ["| # | steer | from | logged | state |", "|---|---|---|---|---|"]
        for s in model["steers"]:
            state = "✅ triaged" if s["triaged"] else "🆕 **untriaged** — planner picks it up ≤ 6 h (or any session: `/techlead`)"
            L.append(f"| #{s['number']} | {md_escape(s['title'])[:110]} | @{s['user']} | {at(s['created_at'])} | {state} |")
    else:
        L.append("_None open. Steer any time: New issue → **Steer**, or comment `/steer <what you want>` on any issue/PR, or just tell your session._")
    L += ["", "## 🔨 In progress"]
    if model["progress"]:
        L += ["| # | task | holder | last activity | PR |", "|---|---|---|---|---|"]
        for e in model["progress"]:
            holder = ", ".join("@" + a for a in e["assignees"]) or ("🤖 worker" if "bot-working" in e["labels"] else "—")
            prs = " ".join(f"#{n}" for n in e["prs"]) or "—"
            L.append(f"| #{e['number']} | {_p(e['priority'])} {md_escape(e['title'])[:100]} {_lbl(e['labels'])} | {holder} | {at(e['updated_at'])} | {prs} |")
    else:
        L.append("_Nothing claimed right now._")
    L += ["", "## 🔍 In review — and exactly what stands between each PR and `main`"]
    if model["review"]:
        L += ["| PR | title | by | closes | state |", "|---|---|---|---|---|"]
        for r in model["review"]:
            closes = " ".join(f"#{n}" for n in r["closing"]) or ("refs " + " ".join(f"#{n}" for n in r["refs"]) if r["refs"] else "—")
            who = "🤖" if is_bot(r["user"]) else "@" + r["user"]
            L.append(f"| #{r['number']} | {md_escape(r['title'])[:90]} | {who} | {closes} | {r['status']} |")
    else:
        L.append("_No open pull requests._")
    nx, cap = model["next_up"], int(cfg["board"]["next_up"])
    L += ["", f"## ⏭️ Next up — `ready`, unassigned, workable now ({len(nx)}) — `/next` on any issue hands you the top one"]
    if nx:
        L += ["| # | P | task | labels | filed |", "|---|---|---|---|---|"]
        for e in nx[:cap]:
            L.append(f"| #{e['number']} | {_p(e['priority'])} | {md_escape(e['title'])[:110]} | {_lbl(e['labels'])} | {at(e['created_at'])[:5]} |")
        if len(nx) > cap:
            L.append(f"| … | | +{len(nx) - cap} more: [full queue](https://github.com/{repo}/issues?q=is%3Aopen+label%3Aready+no%3Aassignee) | | |")
    else:
        L.append("_Queue empty — the planner files new work from docs/PROGRAM.md on its next run._")
    L += ["", "## 🧑 Waiting on a human — the only things the bots cannot do"]
    if model["waiting"] or model["waiting_prs"]:
        L += ["| item | what is needed |", "|---|---|"]
        for r in model["waiting_prs"]:
            L.append(f"| PR #{r['number']} {md_escape(r['title'])[:80]} | {r['status']} |")
        for e in model["waiting"]:
            L.append(f"| #{e['number']} {_p(e['priority'])} {md_escape(e['title'])[:80]} | {'; '.join(e['why'])} |")
    else:
        L.append("_Nothing. 🎉_")
    if model["others"]:
        L += ["", f"<details><summary>📚 Backlog not yet <code>ready</code> ({len(model['others'])}) — the planner promotes these when they become workable</summary>\n"]
        L += [f"- #{e['number']} {_p(e['priority'])} {md_escape(e['title'])[:120]} {_lbl(e['labels'])}" for e in model["others"][:40]]
        L.append("\n</details>")
    L += ["", f"## ✅ Done in the last {cfg['board']['recent_days']} days"]
    if model["done_prs"] or model["done_issues"]:
        for p in model["done_prs"][:25]:
            who = "🤖" if is_bot(p["user"]) else "@" + p["user"]
            L.append(f"- merged #{p['number']} {md_escape(p['title'])[:110]} ({who}, {at(p['merged_at'])})")
        for i in model["done_issues"][:25]:
            mark = "closed" if i["reason"] == "completed" else i["reason"]
            L.append(f"- {mark} #{i['number']} {md_escape(i['title'])[:110]} ({at(i['closed_at'])})")
    else:
        L.append("_Nothing yet this week._")
    L += ["", "## 🩺 Health"]
    icons = {"success": "✅", "failure": "❌", "skipped": "⏭️", "cancelled": "⛔", "in_progress": "⏳", "queued": "⏳"}
    cells = []
    for wf, nice in (("board", "board"), ("techlead", "planner"), ("worker", "worker"), ("claude-review", "review+auto-fix"),
                     ("automerge", "automerge"), ("coord", "coord"), ("CI", "CI")):
        b = h["bots"].get(wf)
        if not b:
            cells.append(f"{nice}: –")
        else:
            txt = f"{nice} {icons.get(b['conclusion'], '·')} {at(b['at'])}"
            cells.append(f"[{txt}]({b['url']})" if b.get("url") else txt)
    L.append(" · ".join(cells))
    L += ["", (f"queue floor/ceiling {h['ready_floor']}/{h['ready_ceiling']} · worker WIP {h['bot_prs_open']}/{cfg['worker']['wip_limit']} "
               f"(≤ {cfg['worker']['max_runs_per_day']} runs/day, eligible: `{cfg['worker']['eligible']}`) · "
               f"auto-fix budget {cfg['pipeline']['max_fix_attempts']} · drafts auto-ready after {cfg['pipeline']['quiet_minutes']} quiet min · "
               f"knobs: [`.github/autonomy.json`](https://github.com/{repo}/blob/main/.github/autonomy.json) · pause planner+worker: add label `{cfg['pause_label']}` to this issue"),
          "", "---",
          ("**Humans:** you never need to write tickets, assign, review, merge or close anything here. Steer instead — "
           "tell your session, use *New issue → Steer*, or comment `/steer <text>` anywhere — and it is logged verbatim, "
           "turned into requirements by the tech leads, and tracked on this board. The short list of things that genuinely "
           f"need a person is the *Waiting on a human* section above ([why](https://github.com/{repo}/blob/main/docs/process/AUTONOMY.md#10-what-still-needs-a-human-and-why))."),
          BOARD_END]
    return "\n".join(L) + "\n"


def render_brief(model: dict, cfg: dict, repo: str) -> str:
    now = parse_ts(model["now"])
    h = model["health"]
    ago = lambda ts: age_txt(parse_ts(ts), now)   # noqa: E731
    L = [f"# Tech-lead brief — {repo} @ {model['now']}", "",
         f"- ready & unassigned: **{h['ready_unassigned']}** (floor {h['ready_floor']}, ceiling {h['ready_ceiling']}); "
         f"in progress {h['in_progress']}; in review {h['in_review']}; waiting on humans {h['waiting_human']}; "
         f"untriaged steers **{h['steers_untriaged']}**; stuck PRs {h['stuck_prs']}; paused={h['paused']}",
         f"- limits this pass: at most {cfg['planner']['max_new_issues_per_run']} new issues; stop filing at the ceiling; "
         f"worker eligibility = `{cfg['worker']['eligible']}` (label `auto`), hot-file allowed for worker: {cfg['worker']['allow_hot_file']}"]
    L.extend(f"- ⚠️ {w}" for w in h["warnings"])
    L += ["", "## Steers / intake awaiting triage (obey; log derived issues with `Refs #<steer>` + label `from-steer`; then label the steer `triaged`)"]
    unt = [s for s in model["steers"] if not s["triaged"]]
    if not unt:
        L.append("_none_")
    for s in unt:
        body = s["body"].strip()
        L += [f"### #{s['number']} — {s['title']}  (by @{s['user']}, {ago(s['created_at'])} ago, labels: {', '.join(s['labels'])})", "",
              body[:2500] + (" …(truncated; `gh issue view` for the rest)" if len(body) > 2500 else ""), ""]
    L.append("## Queue in pick order (ready, unassigned, workable now)")
    L.extend(f"- #{e['number']} {_p(e['priority'])} {e['title']}  [{', '.join(e['labels'])}] ({ago(e['created_at'])} old)" for e in model["next_up"])
    if not model["next_up"]:
        L.append("_empty_")
    L += ["", "## In progress"]
    L.extend(f"- #{e['number']} {e['title']} — {', '.join(e['assignees']) or 'worker'}, updated {ago(e['updated_at'])} ago, PRs {e['prs'] or '-'}"
             for e in model["progress"])
    L += ["", "## Open PRs and their exact merge blocker"]
    L.extend(f"- #{r['number']} {r['title']} (@{r['user']}, closes {r['closing'] or '-'}, refs {r['refs'] or '-'}) — {r['status']}"
             + (f"  labels: {', '.join(r['labels'])}" if r["labels"] else "") for r in model["review"])
    if not model["review"]:
        L.append("_none_")
    L += ["", "## Waiting on humans (do NOT relabel these ready; you may sharpen the question)"]
    L.extend(f"- #{e['number']} {e['title']} — {'; '.join(e['why'])}" for e in model["waiting"])
    L.extend(f"- PR #{r['number']} {r['title']} — {r['status']}" for r in model["waiting_prs"])
    L += ["", "## Backlog not ready (candidates to promote / retire / split)"]
    L.extend(f"- #{e['number']} {_p(e['priority'])} {e['title']} [{', '.join(e['labels'])}]" for e in model["others"][:60])
    L += ["", f"## Done in the last {cfg['board']['recent_days']} days"]
    L.extend(f"- merged PR #{p['number']} {p['title']}" for p in model["done_prs"])
    L.extend(f"- closed #{i['number']} {i['title']} ({i['reason']})" for i in model["done_issues"])
    L += ["", "## Label hygiene findings (fix in passing)"]
    L.extend([f"- {f}" for f in hygiene_findings(model)] or ["_clean_"])
    L += ["", "## Read before planning",
          "- docs/PROGRAM.md (goals, current objectives) · docs/STEERING.md (standing steers) · TRACKER.md (curated roadmap) · "
          "KNOWLEDGE.md (skim §-headers) · docs/product/PERMUTATION-MATRIX.md · docs/coverage/viewer-certified.json"]
    recent = recent_records()
    if recent:
        L.append("- records touched in the last 14 days: " + ", ".join(recent))
    return "\n".join(L) + "\n"


def hygiene_findings(model: dict) -> list:
    out = []
    for e in model["next_up"] + model["others"] + model["progress"]:
        L = set(e["labels"])
        if not (L & set(coord.PRIORITY)):
            out.append(f"#{e['number']} has no priority label (P0/P1/P2)")
        if not any(l.startswith("area:") for l in L):
            out.append(f"#{e['number']} has no area:* label")
    for e in model["waiting"]:
        if "ready" in e["labels"]:
            out.append(f"#{e['number']} is labelled ready AND gated ({'/'.join(l for l in e['labels'] if l in coord.GATED)}) — drop `ready`")
    return out[:40]


def recent_records(days=14) -> list:
    try:
        r = subprocess.run(["git", "-C", ROOT, "log", f"--since={days} days ago", "--name-only", "--pretty=format:", "--", "docs/inbox"],
                           capture_output=True, text=True, timeout=10)
        return sorted({ln.strip() for ln in r.stdout.splitlines() if ln.strip()})[:30]
    except (OSError, subprocess.SubprocessError):
        return []


# ─────────────────────────────── board upsert ───────────────────────────────

def find_board_issue(issues: list, cfg: dict):
    cands = [i for i in issues if cfg["board"]["label"] in labels_of(i)]
    return min(cands, key=lambda i: i["number"]) if cands else None


def strip_stamp(body: str) -> str:
    return re.sub(r"_Rendered [^\n]*\n", "", body or "")


def upsert_board(gh: GH, issues: list, cfg: dict, body: str, log=print) -> int:
    issue = find_board_issue(issues, cfg)
    if issue is None:
        issue = gh.post("issues", {"title": cfg["board"]["title"], "body": body, "labels": [cfg["board"]["label"], "tracking"]})
        log(f"board: created #{issue['number']}")
    elif strip_stamp(issue.get("body") or "") != strip_stamp(body):
        gh.edit_issue(issue["number"], body=body)
        log(f"board: updated #{issue['number']}")
    else:
        log(f"board: #{issue['number']} unchanged")
    try:
        pin_issue(gh, issue)
    except GitHubError as e:
        log(f"board: pin skipped ({e})")
    return issue["number"]


def pin_issue(gh: GH, issue: dict):
    owner, name = gh.repo.split("/", 1)
    data = gh.graphql("query($o:String!,$n:String!){repository(owner:$o,name:$n){pinnedIssues(first:3){nodes{issue{number}}}}}",
                      {"o": owner, "n": name})
    nodes = (((data or {}).get("repository") or {}).get("pinnedIssues") or {}).get("nodes") or []
    pinned = [n["issue"]["number"] for n in nodes]
    if issue["number"] in pinned or len(pinned) >= 3:
        return
    node_id = issue.get("node_id") or gh.get(f"issues/{issue['number']}")["node_id"]
    gh.graphql("mutation($id:ID!){pinIssue(input:{issueId:$id}){issue{number}}}", {"id": node_id})


def ensure_labels(gh: GH, log=print) -> int:
    have = {l["name"] for l in gh.paged("labels")}
    made = 0
    for name, (color, desc) in LABELS.items():
        if name in have:
            continue
        try:
            gh.post("labels", {"name": name, "color": color, "description": desc[:100]})
            made += 1
        except GitHubError as e:
            log(f"labels: could not create {name}: {e}")
    log(f"labels: {made} created, {len(LABELS) - made} present")
    return made


# ─────────────────────────────── worker pick ────────────────────────────────

def worker_runs_today(gh: GH, now, cap: int, exclude_run_id="") -> int:
    """Runs of worker.yml since 00:00 UTC whose `implement` job actually started (stops counting at cap).
    A run that finished within three minutes never reached the model, so it costs no jobs call."""
    day = now.strftime("%Y-%m-%d")
    try:
        runs = gh.get("actions/workflows/worker.yml/runs", created=f">={day}", per_page=50).get("workflow_runs", [])
    except GitHubError:
        return 0
    n = 0
    for r in runs:
        if n >= cap:
            break
        if str(r.get("id")) == str(exclude_run_id):
            continue
        started, ended = parse_ts(r.get("run_started_at") or r.get("created_at")), parse_ts(r.get("updated_at"))
        if r.get("status") == "completed" and started and ended and (ended - started).total_seconds() < 180:
            continue
        try:
            jobs = gh.get(f"actions/runs/{r['id']}/jobs", per_page=30).get("jobs", [])
        except GitHubError:
            continue
        if any(str(j.get("name", "")).startswith("implement") and j.get("conclusion") != "skipped" for j in jobs):
            n += 1
    return n


def pick(snap: dict, cfg: dict, runs_today=0, forced_issue=0) -> dict:
    """Decide the worker's next job. Returns {'go': bool, 'reason': str, ...job fields}."""
    w = cfg["worker"]
    issues, prs = snap["issues"], snap["prs"]
    board = find_board_issue(issues, cfg)
    if not w.get("enabled", True):
        return {"go": False, "reason": "worker disabled in .github/autonomy.json"}
    if board and cfg["pause_label"] in labels_of(board):
        return {"go": False, "reason": f"`{cfg['pause_label']}` is set on the board issue #{board['number']}"}
    if forced_issue:
        i = {i["number"]: i for i in issues}.get(int(forced_issue))
        if not i:
            return {"go": False, "reason": f"#{forced_issue} is not an open issue"}
        return _job(i, prs, w, "dispatched for this issue")
    if runs_today >= int(w["max_runs_per_day"]):
        return {"go": False, "reason": f"daily cap reached ({runs_today}/{w['max_runs_per_day']} worker runs today)"}
    queue = coord.queue(issues, prs)
    # Re-queued work first — finishing beats starting, and it does not count against the WIP limit.
    for i in queue:
        if "retry" in labels_of(i) and _eligible(i, w):
            return _job(i, prs, w, "re-queued work (retry) has priority")
    live_bot_prs = [p for p in prs if is_bot_pr(p, cfg) and not is_stuck(p)]
    if len(live_bot_prs) >= int(w["wip_limit"]):
        return {"go": False, "reason": f"WIP limit: {len(live_bot_prs)} unattended PR(s) still open (limit {w['wip_limit']}) — finish before starting"}
    for i in queue:
        if _eligible(i, w):
            return _job(i, prs, w, "top eligible issue in the ready queue")
    return {"go": False, "reason": "nothing eligible: no `ready` + `auto` unassigned issue that is workable unattended (planner marks `auto`; humans may set worker.eligible=any-ready)"}


def _eligible(i: dict, w: dict) -> bool:
    L = set(labels_of(i))
    if w.get("eligible", "auto") != "any-ready" and not (L & {"auto", "retry"}):
        return False
    return "hot-file" not in L or bool(w.get("allow_hot_file", False))


def _job(i: dict, prs: list, w: dict, reason: str) -> dict:
    """Which branch to work on: the open PR that already closes the issue, else the branch a
    re-queue note recorded in the issue body, else a fresh bot/<n>-<slug>. worker.yml derives
    implement/continue from whether the branch exists; `pr` is 0 when there is none."""
    n = i["number"]
    existing = [p for p in prs if n in p["closing"]]
    m = RETRY_BRANCH_RE.search(i.get("body") or "")
    if existing:
        branch, pr_num, mode = existing[0]["head_ref"], existing[0]["number"], "continue"
    elif m:
        branch, pr_num, mode = m.group(1), 0, "continue"
    else:
        branch, pr_num, mode = f"{w['branch_prefix']}{n}-{slugify(i.get('title', ''))}", 0, "implement"
    return {"go": True, "reason": reason, "issue": n, "title": i.get("title", ""), "branch": branch, "mode": mode,
            "pr": pr_num, "labels": labels_of(i), "max_turns": int(w["max_turns"])}


# ─────────────────────────────── hygiene sweep ──────────────────────────────

def plan_sweep(snap: dict, cfg: dict, now=None) -> list:
    """Pure: the list of actions the sweep should take. Each is a dict with an 'op'."""
    now = now or parse_ts(snap["now"])
    P = cfg["pipeline"]
    acts = []
    issues_by = {i["number"]: i for i in snap["issues"]}
    for p in snap["prs"]:
        L = set(p["labels"])
        head_age_h = (now - (parse_ts(p.get("head_date")) or now)).total_seconds() / 3600
        # (a) stuck PR, quiet for long enough -> re-queue its issue(s) for a fresh holder
        if is_stuck(p) and head_age_h >= float(P["requeue_stuck_after_hours"]):
            for n in p["closing"]:
                i = issues_by.get(n)
                if i:
                    acts.append({"op": "requeue", "issue": n, "pr": p["number"], "branch": p["head_ref"],
                                 "assignees": [a["login"] for a in i.get("assignees") or []], "pr_comments": p["comment_bodies"],
                                 "summary": p["review"]["last_summary"], "key": f"requeue-{p['number']}-{p['head_sha'][:12]}"})
        # (b) drafts nobody touches (a green + approved one is automerge's to promote, not ours to nag)
        if p["draft"] and not (L & {"wip", "do-not-merge"}):
            days = head_age_h / 24
            if days >= float(P["close_stale_days"]):
                acts.append({"op": "close-stale", "pr": p["number"], "branch": p["head_ref"], "closing": p["closing"],
                             "pr_comments": p["comment_bodies"], "days": int(days), "key": f"close-stale-{p['number']}"})
            elif days >= float(P["stale_draft_days"]) and not (p["review"]["verdict"] in ("approve", "nits") and p["checks"]["green"]):
                acts.append({"op": "nudge-stale", "pr": p["number"], "pr_comments": p["comment_bodies"], "days": int(days),
                             "left": int(float(P["close_stale_days"]) - days), "key": f"stale-{p['number']}-{p['head_sha'][:12]}"})
    # (c) worker leases that produced nothing
    closing_any = set(closing_map(snap["prs"]))
    for i in snap["issues"]:
        if set(labels_of(i)) & set(coord.HELD) and i["number"] not in closing_any:
            upd = parse_ts(i.get("updated_at"))
            if upd and (now - upd).total_seconds() / 3600 >= float(P["worker_lease_hours"]):
                acts.append({"op": "release-lease", "issue": i["number"], "key": f"lease-{i['number']}-{i.get('updated_at', '')[:13]}"})
    return acts


def _requeue_issue(gh: GH, n: int, key: str, note: str, branch: str, unassign=()) -> bool:
    """Unassign, `ready` + `retry`, record the branch to continue in the body, say why. Idempotent per key."""
    note = note.rstrip() + "".join(f" {coord.unlock_marker(u)}" for u in unassign)     # their session locks lapse too
    if not gh.comment_once(n, key, note):
        return False
    gh.unassign(n, unassign)
    gh.add_labels(n, "ready", "retry")
    gh.remove_label(n, "bot-working")
    body = gh.get(f"issues/{n}").get("body") or ""
    if branch and not RETRY_BRANCH_RE.search(body):
        gh.edit_issue(n, body=body.rstrip() + f"\n\n<!-- retry-branch: {branch} -->\n")
    return True


def apply_sweep(gh: GH, acts: list, log=print) -> int:
    done = 0
    for a in acts:
        try:
            if a["op"] == "requeue":
                note = (f"♻️ **Re-queued.** PR #{a['pr']} exhausted the bots' automatic fix budget and has not moved since "
                        f"(last review: {a['summary'] or 'see the PR'}). This issue is `ready` + `retry` again and unassigned so a "
                        f"fresh session — or the unattended worker — can finish it. **Continue on `{a['branch']}`** (push to it; the "
                        f"PR, review and merge machinery re-arm on the new commit, with a fresh fix budget). Previous holder: "
                        f"{', '.join('@' + x for x in a['assignees']) or 'the worker'} — `/claim` to take it back.")
                if _requeue_issue(gh, a["issue"], a["key"], note, a["branch"], a["assignees"]):
                    # The reset marker gives whoever continues on the branch a fresh auto-fix budget.
                    gh.comment_once(a["pr"], a["key"], f"♻️ Issue #{a['issue']} re-queued for a fresh holder to continue on this branch.\n\n{RESET_MARK}",
                                    existing=a["pr_comments"])
                    done += 1
                    log(f"sweep: re-queued #{a['issue']} (stuck PR #{a['pr']})")
            elif a["op"] == "nudge-stale":
                if gh.comment_once(a["pr"], a["key"],
                                   f"🕰️ No commits for {a['days']} days on this draft. If it is alive, push or comment; otherwise it is "
                                   f"closed in ~{a['left']} day(s) (branch kept) and its issue goes back to the queue. Label `wip` to exempt it.",
                                   existing=a["pr_comments"]):
                    gh.add_labels(a["pr"], "stale")
                    done += 1
                    log(f"sweep: nudged stale draft #{a['pr']}")
            elif a["op"] == "close-stale":
                closes = " ".join(f"#{n}" for n in a["closing"]) or "—"
                if gh.comment_once(a["pr"], a["key"],
                                   f"🧹 Closing: draft with no commits for {a['days']} days. The branch `{a['branch']}` is kept; reopen "
                                   f"and push if you come back to it. Linked issue(s) {closes} return to the queue.", existing=a["pr_comments"]):
                    gh.patch(f"pulls/{a['pr']}", {"state": "closed"})
                    for n in a["closing"]:
                        cur = gh.get(f"issues/{n}")
                        if cur.get("state") == "open" and not cur.get("pull_request"):
                            _requeue_issue(gh, n, a["key"], f"♻️ PR #{a['pr']} went stale and was closed; this issue is unassigned and "
                                                             f"`ready` + `retry` again. Continue on `{a['branch']}`.",
                                           a["branch"], [x["login"] for x in cur.get("assignees") or []])
                    done += 1
                    log(f"sweep: closed stale draft #{a['pr']}")
            elif a["op"] == "release-lease":
                gh.remove_label(a["issue"], "bot-working")
                gh.comment_once(a["issue"], a["key"], "🤖 The unattended worker's lease on this issue expired without a PR (run ended or "
                                                      "timed out). Released back to the queue; the next worker run or any session may take it.")
                done += 1
                log(f"sweep: released worker lease on #{a['issue']}")
        except GitHubError as e:
            log(f"sweep: {a['op']} failed: {e}")
    return done


# ─────────────────────────────── steer ──────────────────────────────────────

def steer_issue(text: str, by: str = "", source: str = "session", logged_by: str = "", when=None) -> dict:
    when = when or utcnow()
    text = (text or "").strip()
    first = re.split(r"(?<=[.!?])\s+|\n", text, maxsplit=1)[0].strip()
    if len(first) > 100:
        first = first[:100] + "…"
    title = f"Steer: {first}" if first else "Steer (see body)"
    who = "@" + by.lstrip("@") if by else "a human"
    quoted = "\n".join("> " + ln if ln.strip() else ">" for ln in text.splitlines()) or "> (empty)"
    body = (f"## The steer (verbatim)\n\nFrom **{who}** via {source}, {when.strftime('%Y-%m-%d %H:%M UTC')}:\n\n{quoted}\n\n"
            "## What happens next\n\n"
            "The tech leads (the scheduled planner within ~6 h, or any coding session sooner via `/techlead`) triage this: "
            "restate it, file the requirement/task issues it implies (`Refs #<this>` + `from-steer`), record it in "
            "`docs/STEERING.md` if it is standing guidance, then label this issue `triaged`. Disagree with the interpretation? "
            "Comment here — comments from humans on a steer are themselves steers.\n\n"
            f"<!-- steer: source={source}; by={by.lstrip('@') or '?'}; logged-by={logged_by or '?'}; date={when.strftime('%Y-%m-%d')} -->\n")
    return {"title": title, "body": body, "labels": ["steer"]}


# ─────────────────────────────── claim / mine (steer #90) ──────────────────

def first_standing_assignee(events: list, assignees) -> str:
    """Earliest assignee still standing, replaying assigned/unassigned events (single-holder's rule)."""
    cur = list(assignees or [])
    pos, order = {}, []
    for e in events or []:
        ev, who = e.get("event"), ((e.get("assignee") or {}).get("login") or "")
        if ev == "assigned" and who not in pos:
            order.append(who); pos[who] = len(order)
        elif ev == "unassigned":
            pos.pop(who, None)
    for i, who in enumerate(order, start=1):
        if who in pos and pos[who] == i and who in cur:
            return who
    return cur[0] if cur else ""


def judge_mine(issue: dict, locks: list, me: str, session: str, now, idle_hours: float = 2.0, pr_head_date=None) -> tuple:
    """('this-session' | 'active-elsewhere' | 'idle', reason) for one of MY assigned issues.
    locks = coord.standing_locks(comments, assignees); pr_head_date = newest push on a PR closing it."""
    mine = [l for l in locks if l["by"] == me]
    lock = mine[0] if mine else None
    last = max([t for t in (parse_ts(issue.get("updated_at")), parse_ts(pr_head_date) if pr_head_date else None) if t] or [now])
    idle_h = (now - last).total_seconds() / 3600
    if lock and lock["session"] == session and session not in ("", "-"):
        return "this-session", f"locked by this session ({lock['session']})"
    if lock and lock["session"] not in ("", "-") and lock["session"] != session:
        lock_age_h = (now - (parse_ts(lock["created_at"]) or now)).total_seconds() / 3600
        if min(lock_age_h, idle_h) < idle_hours:
            return "active-elsewhere", f"held by your other session `{lock['session']}` (lock {lock_age_h:.1f} h old, activity {idle_h:.1f} h ago) — hands off"
    if idle_h < idle_hours:
        return "active-elsewhere", f"activity {idle_h:.1f} h ago and no lock naming this session — assume another live session; hands off (or `/claim s=<tag> take-over`)"
    return "idle", f"idle {idle_h:.1f} h — resumable: re-lock it for this session (`techlead.py claim {issue['number']} --session <tag>` or `/claim s=<tag>`)"


def claim(gh: GH, number: int, me: str, session: str, settle: float = 6.0, log=print) -> dict:
    """Assign me, wait, verify first standing assignee + first standing lock, post the session lock.
    Returns {'ok': bool, 'holder': str, 'holder_session': str, 'reason': str}."""
    import time
    issue = gh.get(f"issues/{number}")
    assignees = [a["login"] for a in issue.get("assignees") or []]
    if assignees and me not in assignees:
        return {"ok": False, "holder": assignees[0], "holder_session": "-", "reason": f"held by @{', @'.join(assignees)}"}
    comments = gh.comments(number)
    locks = coord.standing_locks(comments, assignees)
    if me in assignees and locks and locks[0]["by"] == me and locks[0]["session"] not in ("-", session):
        age_h = (utcnow() - (parse_ts(locks[0]["created_at"]) or utcnow())).total_seconds() / 3600
        if age_h < 2:
            return {"ok": False, "holder": me, "holder_session": locks[0]["session"],
                    "reason": f"held by your other session `{locks[0]['session']}` ({age_h:.1f} h) — /next instead, or claim with --take-over"}
    if me not in assignees:
        gh.post(f"issues/{number}/assignees", {"assignees": [me]})
    token = f"cli-{int(utcnow().timestamp())}"
    gh.comment(number, f"🔒 @{me} holds #{number} (session `{session or '-'}`, claimed from a coding session).\n{coord.lock_marker(me, session or '-', token)}")
    time.sleep(settle)
    events = gh.paged(f"issues/{number}/events", max_pages=3)
    issue = gh.get(f"issues/{number}")
    assignees = [a["login"] for a in issue.get("assignees") or []]
    first = first_standing_assignee([e for e in events if e.get("event") in ("assigned", "unassigned")], assignees)
    # ONE authority per question (#90): across logins the earliest standing ASSIGNEE wins (single-holder's
    # rule); between sessions of one login the earliest standing LOCK *of that login* picks the session.
    mine_locks = [l for l in coord.standing_locks(gh.comments(number), assignees) if l["by"] == me]
    lock0 = mine_locks[0] if mine_locks else {"by": me, "session": "-", "token": ""}
    if first == me and lock0.get("token") == token:
        return {"ok": True, "holder": me, "holder_session": session, "reason": "verified: first assignee and my login's first lock"}
    if first != me:
        gh.unassign(number, [me])                     # another login was first: undo mine and yield
        gh.comment(number, f"↩️ @{me} (session `{session or '-'}`) yields #{number} to @{first}, whose claim landed first. {coord.unlock_marker(me)}")
        return {"ok": False, "holder": first, "holder_session": "-", "reason": "lost the race to another login"}
    # my login holds it through ANOTHER of my sessions: keep the assignment, drop only this request's lock
    gh.comment(number, f"↩️ session `{session or '-'}` of @{me} steps back from #{number}: session `{lock0.get('session', '-')}` "
                       f"locked it first. {coord.unlock_marker(me)}\n{coord.lock_marker(me, lock0.get('session', '-'), lock0.get('token') or 'relock')}")
    return {"ok": False, "holder": me, "holder_session": lock0.get("session", "-"), "reason": "held by another session of mine"}


def mine(gh: GH, me: str, session: str, idle_hours: float, now=None) -> list:
    now = now or utcnow()
    out = []
    issues = [i for i in gh.get("issues", state="open", assignee=me, per_page=100) if not i.get("pull_request")]
    prs = gh.get("pulls", state="open", per_page=100)
    closing = {}
    for p in prs:
        for n in coord.refs(p.get("body") or "")["closing"]:
            closing.setdefault(n, []).append(p)
    for i in issues:
        comments = gh.comments(i["number"])
        locks = coord.standing_locks(comments, [a["login"] for a in i.get("assignees") or []])
        head_date = None
        for p in closing.get(i["number"], []):
            try:
                d = gh.get(f"commits/{p['head']['sha']}")["commit"]["committer"]["date"]
                head_date = max(head_date or d, d)
            except GitHubError:
                pass
        verdict, why = judge_mine(i, locks, me, session, now, idle_hours, head_date)
        out.append({"number": i["number"], "title": i.get("title", ""), "verdict": verdict, "why": why,
                    "prs": [p["number"] for p in closing.get(i["number"], [])]})
    return out


def whoami(gh: GH) -> str:
    return (gh.request("GET", gh.api + "/user") or {}).get("login", "")


# ─────────────────────────────── hello (SessionStart) ───────────────────────

HELLO = ("tekton · you are a TECH LEAD here: you own the backlog AND you build (CLAUDE.md §4, docs/process/AUTONOMY.md).\n"
         "  Log any human steer FIRST (/steer <their words>) · session start: your PRs → untriaged steers → thin queue? /techlead → /next\n"
         "  Several independent ready issues? /fanout to engineer sessions or subagents. State lives on GitHub, never only here.")


def hello(repo: str, timeout=4.0) -> str:
    lines = [HELLO]
    token = resolve_token(gh_cli_timeout=2)
    board_q = f"https://github.com/{repo}/issues?q=label%3Aboard" if repo else "(no repo detected)"
    if not (token and repo):
        lines.append(f"  Board: {board_q}  (offline here: no GH_TOKEN / gh login — read the board issue in the browser or via MCP issue_read)")
        return "\n".join(lines)
    try:
        gh = GH(repo, token, timeout=timeout)
        cfg = load_config()
        ready = [i for i in gh.get("issues", state="open", labels="ready", assignee="none", per_page=100)
                 if not i.get("pull_request") and not (set(labels_of(i)) & (set(coord.GATED) | set(coord.NOT_WORK) | set(coord.HELD)))]
        ready.sort(key=lambda i: (coord.priority(i), i["number"]))
        inbox = [i for lab in ("steer", "intake") for i in gh.get("issues", state="open", labels=lab, per_page=50)
                 if "triaged" not in labels_of(i)]
        board = gh.get("issues", state="open", labels=cfg["board"]["label"], per_page=5)
        board_url = board[0]["html_url"] if board else board_q
        merge_me = gh.get("issues", state="open", labels="session-merge", per_page=20)
        lines.append(f"  Live: {len(inbox)} untriaged steer(s) · {len(ready)} ready & unassigned (floor {cfg['planner']['ready_floor']}) · board: {board_url}")
        if merge_me:
            lines.append("  MERGE FIRST (bots may not; a session can): " + "; ".join(f"PR #{i['number']} {i['title'][:50]}" for i in merge_me[:4])
                         + " — ONLY with a ✅/🟡 verdict for the exact head + green CI (re-check both, read the workflow diff; prefer a PR"
                           " you did not author), then `gh pr merge <n> --squash --match-head-commit <sha>` / MCP merge_pull_request."
                           " No verdict → do not merge; a non-author collaborator applies `merge-when-green`.")
        if inbox:
            lines.append("  Untriaged: " + "; ".join(f"#{i['number']} {i['title'][:60]}" for i in inbox[:3]))
        if ready:
            lines.append("  Top of queue: " + "; ".join(f"#{i['number']} {i['title'][:50]}" for i in ready[:3]))
    except Exception as e:      # noqa: BLE001 — a banner must never break a session
        lines.append(f"  Board: {board_q}  (live status unavailable: {str(e)[:120]})")
    return "\n".join(lines)


# ─────────────────────────────── CLI ────────────────────────────────────────

def _client(repo_arg) -> GH:
    repo, token = resolve_repo(repo_arg), resolve_token()
    if not repo:
        sys.exit("techlead: cannot tell which repo (pass --repo owner/name or set GITHUB_REPOSITORY)")
    if not token:
        sys.exit("techlead: no GH_TOKEN / GITHUB_TOKEN and no logged-in gh CLI")
    return GH(repo, token)


def _write_outputs(path: str, pairs: dict):
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for k, v in pairs.items():
                fh.write(f"{k}={str(v).replace(chr(10), ' ')}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default="", help="owner/name (default: $GITHUB_REPOSITORY or the origin remote)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("board", help="sweep, then render + upsert + pin the board issue")
    b.add_argument("--dry-run", action="store_true", help="print the sweep plan and the body, change nothing")
    r = sub.add_parser("brief", help="print the tech-lead state brief")
    r.add_argument("--json", action="store_true")
    r.add_argument("--out", default="", help="also write it to this file")
    k = sub.add_parser("pick", help="print the worker's next job as JSON (exit 3 = nothing to do); also writes $GITHUB_OUTPUT")
    k.add_argument("--issue", type=int, default=0, help="force this issue (workflow_dispatch)")
    s = sub.add_parser("sweep", help="run the hygiene sweep only")
    s.add_argument("--dry-run", action="store_true")
    t = sub.add_parser("steer", help="log a steer issue")
    t.add_argument("text")
    t.add_argument("--by", default="", help="GitHub login (or name) of the human who said it")
    t.add_argument("--source", default="session", help="session | comment | form | requirement-file")
    t.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("config", help="print one merged config value, e.g. `config planner.max_turns`")
    c.add_argument("key")
    cl = sub.add_parser("claim", help="claim-and-verify one issue for this session (exit 4 = someone else holds it)")
    cl.add_argument("number", type=int)
    cl.add_argument("--session", default=os.environ.get("TEKTON_SESSION", "-"), help="tag for THIS session (also $TEKTON_SESSION)")
    cl.add_argument("--me", default="", help="my login (default: whoever the token belongs to)")
    cl.add_argument("--take-over", action="store_true", help="take it from another session of mine (that session is gone)")
    mi = sub.add_parser("mine", help="my assigned issues judged this-session / active-elsewhere / idle (the resume rule)")
    mi.add_argument("--session", default=os.environ.get("TEKTON_SESSION", "-"))
    mi.add_argument("--me", default="")
    mi.add_argument("--idle-hours", type=float, default=2.0)
    mi.add_argument("--json", action="store_true")
    sub.add_parser("labels", help="create the label vocabulary")
    sub.add_parser("hello", help="SessionStart banner")
    a = ap.parse_args(argv)

    if a.cmd == "hello":
        print(hello(resolve_repo(a.repo)))
        return 0
    cfg = load_config()
    if a.cmd == "config":
        node = cfg
        for part in a.key.split("."):
            if not isinstance(node, dict) or part not in node:
                sys.exit(f"techlead: no such knob '{a.key}' (see .github/autonomy.json)")
            node = node[part]
        print(json.dumps(node) if isinstance(node, (dict, list)) else node)
        return 0
    try:
        return _run(a, cfg)
    except GitHubError as e:
        sys.exit(f"techlead: {e}")


def _run(a, cfg: dict) -> int:
    if a.cmd == "steer":
        spec = steer_issue(a.text, by=a.by, source=a.source, logged_by=os.environ.get("GITHUB_ACTOR", ""))
        if a.dry_run:
            print(json.dumps(spec, indent=2, ensure_ascii=False))
        else:
            print(_client(a.repo).post("issues", spec).get("html_url", ""))
        return 0

    gh = _client(a.repo)
    if a.cmd == "labels":
        ensure_labels(gh)
        return 0
    if a.cmd == "claim":
        me = a.me or whoami(gh)
        if a.take_over:
            gh.comment(a.number, f"🔓 @{me} takes #{a.number} over from another session of theirs. {coord.unlock_marker(me)}")
        r = claim(gh, a.number, me, a.session)
        print(json.dumps(r, ensure_ascii=False))
        if not r["ok"]:
            print(f"claim: NOT yours — {r['reason']} (holder @{r['holder']}, session {r['holder_session']})", file=sys.stderr)
            return 4
        return 0
    if a.cmd == "mine":
        me = a.me or whoami(gh)
        rows = mine(gh, me, a.session, a.idle_hours)
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            icons = {"this-session": "🟢 yours (this session)", "active-elsewhere": "⛔ active elsewhere", "idle": "🟡 idle, resumable"}
            for r in rows:
                print(f"#{r['number']:<5} {icons[r['verdict']]:<26} {r['title'][:70]}\n        {r['why']}" + (f"  PRs: {r['prs']}" if r["prs"] else ""))
            if not rows:
                print(f"@{me} holds nothing open — `/next s={a.session}` for the head of the queue.")
        return 0
    snap = snapshot(gh, cfg, with_runs=(a.cmd in ("board", "brief")))
    now = parse_ts(snap["now"])
    if a.cmd in ("sweep", "board"):
        acts = plan_sweep(snap, cfg, now)
        if a.dry_run:
            print(json.dumps([{k: v for k, v in x.items() if k != "pr_comments"} for x in acts], indent=2))
        elif apply_sweep(gh, acts):
            # Reflect what the sweep just changed without paying for a second full snapshot.
            snap["issues"] = fetch_issues(gh)
            closed_prs = {x["pr"] for x in acts if x["op"] == "close-stale"}
            snap["prs"] = [p for p in snap["prs"] if p["number"] not in closed_prs]
        if a.cmd == "sweep":
            return 0
    model = classify(snap, cfg, now)
    if a.cmd == "board":
        body = render_board(model, cfg, gh.repo)
        if a.dry_run:
            print(body)
        else:
            try:
                ensure_labels(gh)
            except GitHubError as e:
                print(f"labels: skipped ({e})")
            upsert_board(gh, snap["issues"], cfg, body)
        print(f"api calls: {gh.calls}", file=sys.stderr)
    elif a.cmd == "brief":
        out = json.dumps(model, indent=2, default=str) if a.json else render_brief(model, cfg, gh.repo)
        print(out)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(out)
    elif a.cmd == "pick":
        runs_today = 0 if a.issue else worker_runs_today(gh, now, int(cfg["worker"]["max_runs_per_day"]), os.environ.get("GITHUB_RUN_ID", ""))
        job = pick(snap, cfg, runs_today=runs_today, forced_issue=a.issue)
        job["runs_today"] = runs_today
        print(json.dumps(job, ensure_ascii=False))
        _write_outputs(os.environ.get("GITHUB_OUTPUT", ""), {"go": "yes" if job["go"] else "no",
                       **{key: job[key] for key in ("issue", "branch", "mode", "pr", "reason", "max_turns") if key in job}})
        if not job["go"]:
            print(f"pick: {job['reason']}", file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
