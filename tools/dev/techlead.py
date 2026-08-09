#!/usr/bin/env python3
"""The tech-lead desk: board, brief, queue pick, hygiene sweep, steer log (stdlib only).

tekton's coding sessions are the project's tech leads (docs/process/AUTONOMY.md):
they own the backlog, humans steer. This file is the deterministic half of that
job — everything that needs no judgement — so it can run unattended on the
built-in GITHUB_TOKEN from .github/workflows/{board,techlead,worker}.yml AND from
any coding session (`GH_TOKEN`/`GITHUB_TOKEN` env, or a logged-in `gh`). The
judgement half is the charter in .github/prompts/techlead.md, which the scheduled
planner and human-started sessions both follow, starting from `brief`.

  board   re-render the pinned board issue (label `board`; created + pinned if missing):
          in progress / in review with the exact merge blocker / next up / waiting on a
          human / untriaged steers / done this week / health.      needs: issues:write
  brief   the state digest a tech-lead pass starts from (markdown, or --json)
  pick    the issue the unattended worker should take next -> JSON on stdout, or exit 3
          with the reason on stderr (paused, daily cap, WIP limit, nothing eligible)
  sweep   hygiene the merge bots do not do: re-queue issues whose PR is `bot-stuck`,
          free issues whose worker died (`bot-working` with nothing to show), nudge and
          eventually close drafts nobody has touched for days
  steer   log a human steer verbatim as a `steer` issue BEFORE acting on it:
            python3 tools/dev/techlead.py steer "what they said" --by <login>
  labels  create/update the label vocabulary this system relies on
  hello   the SessionStart banner (never fails; offline-safe; < 2 s without a token)

Config: .github/autonomy.json on the default branch (DEFAULTS below fill any gap).
Repo:   --repo owner/name, else $GITHUB_REPOSITORY, else the `origin` remote.
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

DEFAULTS = {
    "board": {"label": "board", "recent_days": 7, "next_up": 10,
              "title": "📋 Board — what the tech leads are doing, reviewing, planning, and waiting on (auto-updated)"},
    "planner": {"enabled": True, "ready_floor": 4, "ready_ceiling": 12, "max_new_issues_per_run": 5, "max_turns": 60},
    "worker": {"enabled": True, "eligible": "auto", "wip_limit": 2, "max_runs_per_day": 4,
               "allow_hot_file": False, "max_turns": 120, "branch_prefix": "bot/"},
    "pipeline": {"quiet_minutes": 90, "max_fix_attempts": 3, "stale_draft_days": 5,
                 "close_stale_days": 14, "requeue_stuck_after_hours": 24, "worker_lease_hours": 3},
    "pause_label": "bots-paused",
}

# name -> (color, description). `ensure_labels` creates what is missing; nothing is renamed.
LABELS = {
    "steer": ("0e8a16", "A human steer, logged verbatim; the tech leads triage it into work"),
    "intake": ("0e8a16", "Free-form issue filed by a human; triaged by the tech leads like a steer"),
    "triaged": ("bfdadc", "Steer/intake processed: derived issues filed and linked"),
    "planned": ("c5def5", "Filed by the tech-lead planner from the program goals"),
    "from-steer": ("c5def5", "Derived from a logged steer (see Refs in the body)"),
    "auto": ("1d76db", "Cleared for the unattended worker (fresh-clone doable, clear DONE, no hardware)"),
    "bot-working": ("5319e7", "Held by the unattended worker right now"),
    "bot-stuck": ("b60205", "Bots exhausted their fix budget on this PR; its issue is re-queued with context"),
    "retry": ("fbca04", "Re-queued after a stuck/abandoned attempt: continue the existing branch"),
    "needs-decision": ("b60205", "A human must answer the question in this issue before work continues"),
    "needs-rebase": ("d93f0b", "Conflicts with main; the rebase job (or the author) must merge main in"),
    "duplicate-pr": ("d93f0b", "A second open PR for an issue another PR already closes; the older one wins"),
    "stale": ("cfd3d7", "No commits for days; will be closed and its issue re-queued unless it moves"),
    "board": ("5319e7", "The auto-rendered task board issue"),
    "bots-paused": ("000000", "Put on the board issue to pause the planner and the worker (merging continues)"),
    "epic": ("3e4b9e", "Multi-issue objective; children are linked task issues"),
    "area:process": ("cfd3d7", "How work flows: automation, coordination, docs of the process"),
    "ready": ("0e8a16", "Doable now from a fresh clone; unassigned = free to claim (/next hands out the top one)"),
}

BOT_SUFFIX = "[bot]"
VERDICT_RE = re.compile(r"<!-- claude-review: (approve|nits|changes) sha=([0-9a-f]{7,40}) -->")
ATTEMPT_RE = re.compile(r"<!-- claude-autofix attempt=\d+ -->")
RESET_MARK = "<!-- claude-autofix reset -->"
EXHAUSTED_RE = re.compile(r"<!-- claude-autofix exhausted sha=([0-9a-f]{7,40}) -->")
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


def age_txt(then, now) -> str:
    """Coarse on purpose (hour buckets): the board re-renders on every event, and minute-exact
    ages would turn every no-op render into an issue edit."""
    if then is None:
        return "?"
    s = max(0, int((now - then).total_seconds()))
    if s < 3600:
        return "<1 h"
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


def load_config(root=ROOT, text=None) -> dict:
    if text is None:
        p = os.path.join(root, ".github", "autonomy.json")
        try:
            with open(p, encoding="utf-8") as fh:
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
    s = s[:limit].rstrip("-")
    return s or "work"


def is_bot(login: str) -> bool:
    return (login or "").endswith(BOT_SUFFIX) or login in ("github-actions", "claude")


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def labels_of(x: dict) -> list:
    return coord.label_names(x)


# ─────────────────────────────── GitHub client ──────────────────────────────

class GitHubError(RuntimeError):
    def __init__(self, status, msg):
        super().__init__(f"GitHub API {status}: {msg}")
        self.status = status


class GH:
    """Minimal REST/GraphQL client on urllib. Honours HTTPS_PROXY like urllib does."""

    def __init__(self, repo: str, token: str, api: str = "", timeout: float = 20.0):
        self.repo = repo
        self.token = token
        self.api = (api or os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
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
        if path.startswith("http"):
            url = path
        else:
            url = self.api + path.replace("{r}", f"/repos/{self.repo}")
        if params:
            q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url += ("&" if "?" in url else "?") + q
        return url

    def request(self, method, path, body=None, params=None, ok=(200, 201, 202, 204)):
        status, data, link = self._send(method, self._url(path, params), body)
        if status not in ok:
            msg = (data or {}).get("message", "") if isinstance(data, dict) else str(data)[:300]
            raise GitHubError(status, f"{method} {path}: {msg}")
        return data, link

    def get(self, path, **params):
        return self.request("GET", path, params=params)[0]

    def paged(self, path, max_pages=10, **params):
        params.setdefault("per_page", 100)
        out, url, pages = [], self._url(path, params), 0
        while url and pages < max_pages:
            status, data, link = self._send("GET", url)
            if status != 200:
                msg = (data or {}).get("message", "") if isinstance(data, dict) else ""
                raise GitHubError(status, f"GET {path}: {msg}")
            if isinstance(data, dict):          # e.g. check-runs / workflow runs envelopes
                key = next((k for k in ("check_runs", "workflow_runs", "jobs", "items") if k in data), None)
                data = data.get(key, []) if key else [data]
            out.extend(data)
            m = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
            url = m.group(1) if m else None
            pages += 1
        return out

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body=body, **kw)[0]

    def patch(self, path, body=None):
        return self.request("PATCH", path, body=body)[0]

    def put(self, path, body=None):
        return self.request("PUT", path, body=body)[0]

    def delete(self, path):
        return self.request("DELETE", path, ok=(200, 204, 404))[0]

    def graphql(self, query, variables=None):
        endpoint = self.api[:-3] + "/graphql" if self.api.endswith("/api/v3") else self.api + "/graphql"
        data, _ = self.request("POST", endpoint, body={"query": query, "variables": variables or {}})
        if isinstance(data, dict) and data.get("errors"):
            raise GitHubError(200, "; ".join(e.get("message", "?") for e in data["errors"]))
        return (data or {}).get("data")

    # -- conveniences --
    def comment(self, number, body):
        return self.post(f"{{r}}/issues/{number}/comments", {"body": body})

    def comments(self, number):
        return self.paged(f"{{r}}/issues/{number}/comments")

    def comment_once(self, number, key, body, existing=None):
        marker = f"<!-- techlead:{key} -->"
        bodies = existing if existing is not None else [c.get("body") or "" for c in self.comments(number)]
        if any(marker in b for b in bodies):
            return False
        self.comment(number, body.rstrip() + "\n\n" + marker)
        return True

    def add_labels(self, number, *names):
        return self.post(f"{{r}}/issues/{number}/labels", {"labels": list(names)})

    def remove_label(self, number, name):
        return self.delete(f"{{r}}/issues/{number}/labels/{urllib.parse.quote(name)}")

    def edit_issue(self, number, **fields):
        return self.patch(f"{{r}}/issues/{number}", fields)


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


def resolve_token(allow_gh_cli=True, timeout=5) -> str:
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    if allow_gh_cli:
        try:
            r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


# ─────────────────────────────── snapshot ───────────────────────────────────

def parse_review_state(comment_bodies: list, head_sha: str) -> dict:
    """Verdict for THIS head sha, fix attempts since the last reset marker, exhaustion."""
    verdict, attempts, exhausted, last_summary = None, 0, False, ""
    for b in comment_bodies:
        b = b or ""
        for v, sha in VERDICT_RE.findall(b):
            if head_sha.startswith(sha) or sha.startswith(head_sha[:len(sha)]):
                verdict = v
                first = b.strip().splitlines()[0] if b.strip() else ""
                last_summary = first[:160]
        if RESET_MARK in b:
            attempts, exhausted = 0, False
        if ATTEMPT_RE.search(b):
            attempts += 1
        for sha in EXHAUSTED_RE.findall(b):
            if head_sha.startswith(sha) or sha.startswith(head_sha[:len(sha)]):
                exhausted = True
    return {"verdict": verdict, "attempts": attempts, "exhausted": exhausted, "last_summary": last_summary}


def summarize_checks(check_runs: list) -> dict:
    """CI gate exactly as automerge sees it: ignore automerge itself and the claude* checks."""
    runs = [c for c in check_runs or [] if c.get("name") != "automerge" and not str(c.get("name", "")).startswith("claude")]
    pending = [c["name"] for c in runs if c.get("status") != "completed"]
    bad = [c["name"] for c in runs if c.get("status") == "completed" and c.get("conclusion") not in ("success", "neutral", "skipped")]
    ok = [c["name"] for c in runs if c.get("conclusion") == "success"]
    return {"total": len(runs), "pending": pending, "bad": bad, "ok": len(ok)}


def enrich_pr(gh: GH, p: dict) -> dict:
    """One open PR with everything the board / sweep need (4-5 API calls)."""
    n = p["number"]
    detail = gh.get(f"{{r}}/pulls/{n}")
    sha = detail["head"]["sha"]
    try:
        checks = gh.get(f"{{r}}/commits/{sha}/check-runs", per_page=100).get("check_runs", [])
    except GitHubError:
        checks = []
    try:
        head_date = gh.get(f"{{r}}/commits/{sha}")["commit"]["committer"]["date"]
    except GitHubError:
        head_date = detail.get("updated_at")
    bodies = [c.get("body") or "" for c in gh.comments(n)]
    try:
        files = gh.paged(f"{{r}}/pulls/{n}/files", max_pages=3)
    except GitHubError:
        files = []
    r = coord.refs(detail.get("body") or "")
    return {
        "number": n, "title": detail.get("title", ""), "user": (detail.get("user") or {}).get("login", ""),
        "draft": bool(detail.get("draft")), "labels": labels_of(detail), "body": detail.get("body") or "",
        "head_sha": sha, "head_ref": detail["head"]["ref"], "base_ref": detail["base"]["ref"],
        "created_at": detail.get("created_at"), "updated_at": detail.get("updated_at"), "head_date": head_date,
        "mergeable": detail.get("mergeable"), "mergeable_state": detail.get("mergeable_state", "unknown"),
        "checks": summarize_checks(checks), "review": parse_review_state(bodies, sha),
        "comment_bodies": bodies, "closing": r["closing"], "refs": r["refs"],
        "touches_workflows": any(str(f.get("filename", "")).startswith(".github/workflows/") for f in files),
        "html_url": detail.get("html_url", ""),
    }


def snapshot(gh: GH, cfg: dict, now=None, with_runs=True) -> dict:
    now = now or utcnow()
    days = int(cfg["board"]["recent_days"])
    cutoff = now - _dt.timedelta(days=days)
    raw_open = gh.paged("{r}/issues", state="open")
    issues = [i for i in raw_open if not i.get("pull_request")]
    closed = [i for i in gh.paged("{r}/issues", state="closed", since=iso(cutoff), max_pages=3)
              if not i.get("pull_request") and parse_ts(i.get("closed_at") or "") and parse_ts(i["closed_at"]) >= cutoff]
    prs = [enrich_pr(gh, p) for p in sorted(gh.paged("{r}/pulls", state="open"), key=lambda p: p["number"])[:30]]
    merged = [p for p in gh.get("{r}/pulls", state="closed", sort="updated", direction="desc", per_page=50)
              if p.get("merged_at") and parse_ts(p["merged_at"]) >= cutoff]
    runs = []
    if with_runs:
        try:
            runs = gh.get("{r}/actions/runs", per_page=60).get("workflow_runs", [])
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
}


def pr_status(pr: dict, cfg: dict, now) -> tuple:
    """(emoji+text of the exact thing standing between this PR and merge, lane) — mirrors automerge."""
    L = set(pr["labels"])
    ch, rv = pr["checks"], pr["review"]
    mx = int(cfg["pipeline"]["max_fix_attempts"])
    quiet_need = int(cfg["pipeline"]["quiet_minutes"])
    quiet = int((now - (parse_ts(pr.get("head_date")) or now)).total_seconds() // 60)
    fix = f"auto-fix {min(rv['attempts'], mx)}/{mx}" + (" → **bot-stuck**, issue re-queued" if rv["exhausted"] or "bot-stuck" in L else "")
    if "do-not-merge" in L:
        return "⏸ held by `do-not-merge`", "held"
    if "needs-human" in L:
        why = "changes `.github/workflows/**` → owner squash-merges by hand" if pr["touches_workflows"] else "see the bot's last comment"
        return f"🧑 needs a human: {why}", "human"
    if "duplicate-pr" in L:
        return "👯 a second PR for an issue another open PR already closes (older wins) — the planner closes one", "human"
    if "needs-issue" in L:
        return "🏷️ no linked issue (`Closes #N`) — cannot merge until it has one", "blocked"
    if ch["total"] == 0:
        return "⏳ no CI checks on this commit yet (automerge dispatches CI itself)", "ci"
    if ch["pending"]:
        return f"⏳ CI running ({len(ch['pending'])})", "ci"
    if ch["bad"]:
        return f"🟥 CI red ({', '.join(ch['bad'][:3])}) · {fix}", "red"
    v = rv["verdict"]
    if pr["draft"]:
        if v in ("approve", "nits"):
            left = -(-max(0, quiet_need - quiet) // 10) * 10          # 10-min buckets keep no-op renders identical
            when = "auto-marked ready on the next sweep" if left == 0 else f"auto-marked ready after ≤ {left} more quiet min"
            return f"🟢 CI · ✅ {v} · **draft** — {when} (label `wip` to hold)", "draft"
        if v == "changes":
            return f"🟢 CI · 🛑 changes requested · {fix} · draft", "changes"
        return "🟢 CI · review verdict pending · draft", "review"
    if v is None:
        return "🟢 CI · ⏳ no review verdict for this commit yet (re-requested automatically if it goes missing)", "review"
    if v == "changes":
        return f"🟢 CI · 🛑 changes requested · {fix}", "changes"
    if pr["touches_workflows"]:
        return f"🟢 CI · ✅ {v} · changes `.github/workflows/**` → **owner squash-merges by hand** (GitHub forbids the bot)", "human"
    if pr["mergeable_state"] == "dirty" or pr.get("mergeable") is False:
        return f"🟢 CI · ✅ {v} · ⚠️ conflicts with main → rebase job dispatched", "conflict"
    return f"🟢 CI · ✅ {v} → merges on the next automerge sweep (≤ 30 min)", "merging"


def classify(snap: dict, cfg: dict, now=None) -> dict:
    now = now or parse_ts(snap["now"])
    issues, prs = snap["issues"], snap["prs"]
    closing_prs = {}
    for p in prs:
        for n in p["closing"]:
            closing_prs.setdefault(n, []).append(p["number"])
    q = coord.queue(issues, [{"number": p["number"], "body": p["body"]} for p in prs])
    steers, waiting, progress, others = [], [], [], []
    for i in sorted(issues, key=lambda i: (coord.priority(i), i["number"])):
        L = set(labels_of(i))
        entry = {"number": i["number"], "title": i.get("title", ""), "labels": sorted(L),
                 "assignees": [a["login"] for a in i.get("assignees") or []],
                 "user": (i.get("user") or {}).get("login", ""), "priority": coord.priority(i),
                 "created_at": i.get("created_at"), "updated_at": i.get("updated_at"),
                 "prs": closing_prs.get(i["number"], []), "body": i.get("body") or ""}
        if L & {"steer", "intake"}:
            entry["triaged"] = "triaged" in L
            steers.append(entry)
            continue
        if L & {"board"}:
            continue
        gated = [g for g in coord.GATED if g in L]
        if gated and "tracking" not in L:
            entry["why"] = [HUMAN_REASONS.get(g, g) for g in gated]
            waiting.append(entry)
        if entry["assignees"] or "bot-working" in L:
            if "tracking" not in L:
                progress.append(entry)
        elif not gated and "ready" not in L and not (L & set(coord.NOT_WORK)):
            others.append(entry)
    review = []
    for p in prs:
        status, lane = pr_status(p, cfg, now)
        review.append({**{k: p[k] for k in ("number", "title", "user", "draft", "labels", "head_ref", "closing",
                                              "refs", "created_at", "head_date", "touches_workflows")},
                       "status": status, "lane": lane, "verdict": p["review"]["verdict"],
                       "attempts": p["review"]["attempts"], "exhausted": p["review"]["exhausted"]})
    human_prs = [r for r in review if r["lane"] == "human"]
    done_issues = [{"number": i["number"], "title": i.get("title", ""), "closed_at": i.get("closed_at"),
                    "reason": i.get("state_reason") or "completed"} for i in snap["closed"]]
    done_prs = [{"number": p["number"], "title": p.get("title", ""), "merged_at": p.get("merged_at"),
                 "user": (p.get("user") or {}).get("login", "")} for p in snap["merged"]]
    ready_unassigned = [i for i in q]
    health = {
        "open_issues": len(issues), "ready_unassigned": len(ready_unassigned),
        "in_progress": len(progress), "in_review": len(review), "waiting_human": len(waiting) + len(human_prs),
        "steers_untriaged": len([s for s in steers if not s["triaged"]]),
        "bot_prs_open": len([r for r in review if r["head_ref"].startswith(cfg["worker"]["branch_prefix"]) or is_bot(r["user"])]),
        "stuck_prs": len([r for r in review if r["exhausted"] or "bot-stuck" in r["labels"]]),
        "ready_floor": int(cfg["planner"]["ready_floor"]), "ready_ceiling": int(cfg["planner"]["ready_ceiling"]),
        "bots": bot_health(snap.get("runs") or [], now),
        "paused": any(cfg["pause_label"] in labels_of(i) for i in issues if cfg["board"]["label"] in labels_of(i)),
    }
    warnings = []
    if health["ready_unassigned"] < health["ready_floor"]:
        warnings.append(f"ready queue below floor ({health['ready_unassigned']} < {health['ready_floor']}) — the planner replenishes it on its next run; any session may run a tech-lead pass now")
    if health["steers_untriaged"]:
        oldest = min((parse_ts(s["created_at"]) for s in steers if not s["triaged"]), default=None)
        warnings.append(f"{health['steers_untriaged']} untriaged steer(s), oldest {age_txt(oldest, now)} old")
    if health["stuck_prs"]:
        warnings.append(f"{health['stuck_prs']} PR(s) exhausted the bots' fix budget — their issues are re-queued for a fresh attempt")
    if health["paused"]:
        warnings.append("`bots-paused` is set on this board: planner and worker are idle (reviews and merges continue)")
    health["warnings"] = warnings
    return {"now": iso(now), "repo": snap["repo"], "steers": steers, "waiting": waiting, "waiting_prs": human_prs,
            "progress": progress, "review": review, "next_up": [
                {"number": i["number"], "title": i.get("title", ""), "priority": coord.priority(i),
                 "labels": sorted(labels_of(i)), "created_at": i.get("created_at")} for i in ready_unassigned],
            "others": others, "done_issues": done_issues, "done_prs": done_prs, "health": health, "by_num": {}}


def bot_health(runs: list, now) -> dict:
    """Latest run per workflow name: conclusion + age (for the Health line)."""
    latest = {}
    for r in runs:
        name = r.get("name") or ""
        if name not in latest:
            latest[name] = r
    out = {}
    for name, r in latest.items():
        out[name] = {"conclusion": r.get("conclusion") or r.get("status"), "age": age_txt(parse_ts(r.get("created_at")), now),
                     "url": r.get("html_url", ""), "event": r.get("event", "")}
    return out


# ─────────────────────────────── render ─────────────────────────────────────

def _p(pr): return f"P{pr}" if pr < 3 else "P–"


def _lbl(labels, keep=("area:", "hot-file", "auto", "retry", "good-first-pick", "from-steer", "planned")):
    shown = [l for l in labels if any(l.startswith(k) for k in keep)]
    return " ".join(f"`{l}`" for l in shown)


def render_board(model: dict, cfg: dict, repo: str) -> str:
    now = parse_ts(model["now"])
    h = model["health"]
    L = []
    L.append(BOARD_BEGIN)
    L.append(f"_Rendered {model['now'][:16].replace('T', ' ')} UTC by `board` (token-free; hourly + on every issue/PR event). "
             f"Do not edit this body — it is overwritten. Talk in comments; steer with `/steer <text>`._")
    L.append("")
    L.append(f"**{h['in_progress']} in progress · {h['in_review']} in review · {h['ready_unassigned']} ready & free · "
             f"{h['waiting_human']} waiting on a human · {h['steers_untriaged']} untriaged steer(s)** — "
             f"[START HERE](https://github.com/{repo}/issues/25) · [how this works](https://github.com/{repo}/blob/main/docs/process/AUTONOMY.md) · "
             f"[goals](https://github.com/{repo}/blob/main/docs/PROGRAM.md) · [standing steers](https://github.com/{repo}/blob/main/docs/STEERING.md)")
    if h["warnings"]:
        L.append("")
        for w in h["warnings"]:
            L.append(f"> ⚠️ {w}")
    # steers
    L.append("")
    L.append("## 🧭 Steers from humans")
    if model["steers"]:
        L.append("| # | steer | from | logged | state |")
        L.append("|---|---|---|---|---|")
        for s in model["steers"]:
            state = "✅ triaged" if s["triaged"] else "🆕 **untriaged** — planner picks it up ≤ 6 h (or any session: `/techlead`)"
            L.append(f"| #{s['number']} | {md_escape(s['title'])[:110]} | @{s['user']} | {age_txt(parse_ts(s['created_at']), now)} ago | {state} |")
    else:
        L.append("_None open. Steer any time: New issue → **Steer**, or comment `/steer <what you want>` on any issue/PR, or just tell your session._")
    # in progress
    L.append("")
    L.append("## 🔨 In progress")
    if model["progress"]:
        L.append("| # | task | holder | since | PR |")
        L.append("|---|---|---|---|---|")
        for e in model["progress"]:
            holder = ", ".join("@" + a for a in e["assignees"]) or ("🤖 worker" if "bot-working" in e["labels"] else "—")
            prs = " ".join(f"#{n}" for n in e["prs"]) or "—"
            L.append(f"| #{e['number']} | {_p(e['priority'])} {md_escape(e['title'])[:100]} {_lbl(e['labels'])} | {holder} | {age_txt(parse_ts(e['updated_at']), now)} | {prs} |")
    else:
        L.append("_Nothing claimed right now._")
    # in review
    L.append("")
    L.append("## 🔍 In review — and exactly what stands between each PR and `main`")
    if model["review"]:
        L.append("| PR | title | by | closes | state |")
        L.append("|---|---|---|---|---|")
        for r in model["review"]:
            closes = " ".join(f"#{n}" for n in r["closing"]) or ("refs " + " ".join(f"#{n}" for n in r["refs"]) if r["refs"] else "—")
            who = "🤖" if is_bot(r["user"]) else "@" + r["user"]
            L.append(f"| #{r['number']} | {md_escape(r['title'])[:90]} | {who} | {closes} | {r['status']} |")
    else:
        L.append("_No open pull requests._")
    # next up
    L.append("")
    nx = model["next_up"]
    cap = int(cfg["board"]["next_up"])
    L.append(f"## ⏭️ Next up — `ready`, unassigned, workable now ({len(nx)}) — `/next` on any issue hands you the top one")
    if nx:
        L.append("| # | P | task | labels | age |")
        L.append("|---|---|---|---|---|")
        for e in nx[:cap]:
            L.append(f"| #{e['number']} | {_p(e['priority'])} | {md_escape(e['title'])[:110]} | {_lbl(e['labels'])} | {age_txt(parse_ts(e['created_at']), now)} |")
        if len(nx) > cap:
            L.append(f"| … | | +{len(nx) - cap} more: [full queue](https://github.com/{repo}/issues?q=is%3Aopen+label%3Aready+no%3Aassignee) | | |")
    else:
        L.append("_Queue empty — the planner files new work from docs/PROGRAM.md on its next run._")
    # waiting on humans
    L.append("")
    L.append("## 🧑 Waiting on a human — the only things the bots cannot do")
    if model["waiting"] or model["waiting_prs"]:
        L.append("| item | what is needed |")
        L.append("|---|---|")
        for r in model["waiting_prs"]:
            L.append(f"| PR #{r['number']} {md_escape(r['title'])[:80]} | {r['status']} |")
        for e in model["waiting"]:
            L.append(f"| #{e['number']} {_p(e['priority'])} {md_escape(e['title'])[:80]} | {'; '.join(e['why'])} |")
    else:
        L.append("_Nothing. 🎉_")
    # backlog remainder
    if model["others"]:
        L.append("")
        L.append(f"<details><summary>📚 Backlog not yet <code>ready</code> ({len(model['others'])}) — the planner promotes these when they become workable</summary>\n")
        for e in model["others"][:40]:
            L.append(f"- #{e['number']} {_p(e['priority'])} {md_escape(e['title'])[:120]} {_lbl(e['labels'])}")
        L.append("\n</details>")
    # done
    L.append("")
    days = cfg["board"]["recent_days"]
    L.append(f"## ✅ Done in the last {days} days")
    if model["done_prs"] or model["done_issues"]:
        for p in model["done_prs"][:25]:
            who = "🤖" if is_bot(p["user"]) else "@" + p["user"]
            L.append(f"- merged #{p['number']} {md_escape(p['title'])[:110]} ({who}, {age_txt(parse_ts(p['merged_at']), now)} ago)")
        for i in model["done_issues"][:25]:
            mark = "closed" if i["reason"] == "completed" else i["reason"]
            L.append(f"- {mark} #{i['number']} {md_escape(i['title'])[:110]} ({age_txt(parse_ts(i['closed_at']), now)} ago)")
    else:
        L.append("_Nothing yet this week._")
    # health
    L.append("")
    L.append("## 🩺 Health")
    bots = h["bots"]
    names = [("board", "board"), ("techlead", "planner"), ("worker", "worker"), ("claude-review", "review+auto-fix"),
             ("automerge", "automerge"), ("coord", "coord"), ("CI", "CI")]
    cells = []
    for wf, nice in names:
        b = bots.get(wf)
        if not b:
            cells.append(f"{nice}: –")
            continue
        icon = {"success": "✅", "failure": "❌", "skipped": "⏭️", "cancelled": "⛔", "in_progress": "⏳", "queued": "⏳"}.get(b["conclusion"], "·")
        cells.append(f"[{nice} {icon} {b['age']} ago]({b['url']})" if b.get("url") else f"{nice} {icon} {b['age']} ago")
    L.append(" · ".join(cells))
    L.append("")
    L.append(f"queue floor/ceiling {h['ready_floor']}/{h['ready_ceiling']} · worker WIP {h['bot_prs_open']}/{cfg['worker']['wip_limit']} "
             f"(≤ {cfg['worker']['max_runs_per_day']} runs/day, eligible: `{cfg['worker']['eligible']}`) · "
             f"auto-fix budget {cfg['pipeline']['max_fix_attempts']} · drafts auto-ready after {cfg['pipeline']['quiet_minutes']} quiet min · "
             f"knobs: [`.github/autonomy.json`](https://github.com/{repo}/blob/main/.github/autonomy.json) · pause planner+worker: add label `{cfg['pause_label']}` to this issue")
    L.append("")
    L.append("---")
    L.append("**Humans:** you never need to write tickets, assign, review, merge or close anything here. Steer instead — "
             "tell your session, use *New issue → Steer*, or comment `/steer <text>` anywhere — and it is logged verbatim, "
             "turned into requirements by the tech leads, and tracked on this board. The short list of things that genuinely "
             f"need a person is the *Waiting on a human* section above ([why](https://github.com/{repo}/blob/main/docs/process/AUTONOMY.md#10-what-still-needs-a-human-and-why)).")
    L.append(BOARD_END)
    return "\n".join(L) + "\n"


def render_brief(model: dict, cfg: dict, repo: str, root=ROOT) -> str:
    now = parse_ts(model["now"])
    h = model["health"]
    L = [f"# Tech-lead brief — {repo} @ {model['now']}", ""]
    L.append(f"- ready & unassigned: **{h['ready_unassigned']}** (floor {h['ready_floor']}, ceiling {h['ready_ceiling']}); "
             f"in progress {h['in_progress']}; in review {h['in_review']}; waiting on humans {h['waiting_human']}; "
             f"untriaged steers **{h['steers_untriaged']}**; stuck PRs {h['stuck_prs']}; paused={h['paused']}")
    L.append(f"- limits this pass: at most {cfg['planner']['max_new_issues_per_run']} new issues; stop filing at the ceiling; "
             f"worker eligibility = `{cfg['worker']['eligible']}` (label `auto`), hot-file allowed for worker: {cfg['worker']['allow_hot_file']}")
    for w in h["warnings"]:
        L.append(f"- ⚠️ {w}")
    L.append("")
    L.append("## Steers / intake awaiting triage (obey; log derived issues with `Refs #<steer>` + label `from-steer`; then label the steer `triaged`)")
    unt = [s for s in model["steers"] if not s["triaged"]]
    if not unt:
        L.append("_none_")
    for s in unt:
        L.append(f"### #{s['number']} — {s['title']}  (by @{s['user']}, {age_txt(parse_ts(s['created_at']), now)} ago, labels: {', '.join(s['labels'])})")
        body = s["body"].strip()
        L.append("")
        L.append(body[:2500] + (" …(truncated; `gh issue view` for the rest)" if len(body) > 2500 else ""))
        L.append("")
    L.append("## Queue in pick order (ready, unassigned, workable now)")
    for e in model["next_up"]:
        L.append(f"- #{e['number']} {_p(e['priority'])} {e['title']}  [{', '.join(e['labels'])}] ({age_txt(parse_ts(e['created_at']), now)} old)")
    if not model["next_up"]:
        L.append("_empty_")
    L.append("")
    L.append("## In progress")
    for e in model["progress"]:
        holder = ", ".join(e["assignees"]) or "worker"
        L.append(f"- #{e['number']} {e['title']} — {holder}, updated {age_txt(parse_ts(e['updated_at']), now)} ago, PRs {e['prs'] or '-'}")
    L.append("")
    L.append("## Open PRs and their exact merge blocker")
    for r in model["review"]:
        L.append(f"- #{r['number']} {r['title']} (@{r['user']}, closes {r['closing'] or '-'}, refs {r['refs'] or '-'}) — {r['status']}"
                 + (f"  labels: {', '.join(r['labels'])}" if r["labels"] else ""))
    if not model["review"]:
        L.append("_none_")
    L.append("")
    L.append("## Waiting on humans (do NOT relabel these ready; you may sharpen the question)")
    for e in model["waiting"]:
        L.append(f"- #{e['number']} {e['title']} — {'; '.join(e['why'])}")
    for r in model["waiting_prs"]:
        L.append(f"- PR #{r['number']} {r['title']} — {r['status']}")
    L.append("")
    L.append("## Backlog not ready (candidates to promote / retire / split)")
    for e in model["others"][:60]:
        L.append(f"- #{e['number']} {_p(e['priority'])} {e['title']} [{', '.join(e['labels'])}]")
    L.append("")
    L.append(f"## Done in the last {cfg['board']['recent_days']} days")
    for p in model["done_prs"]:
        L.append(f"- merged PR #{p['number']} {p['title']}")
    for i in model["done_issues"]:
        L.append(f"- closed #{i['number']} {i['title']} ({i['reason']})")
    L.append("")
    L.append("## Label hygiene findings (fix in passing)")
    findings = hygiene_findings(model)
    L.extend(f"- {f}" for f in findings) if findings else L.append("_clean_")
    L.append("")
    L.append("## Read before planning")
    L.append("- docs/PROGRAM.md (goals, current objectives) · docs/STEERING.md (standing steers) · TRACKER.md (curated roadmap) · "
             "KNOWLEDGE.md (skim §-headers) · docs/product/PERMUTATION-MATRIX.md · docs/coverage/viewer-certified.json")
    recent = recent_records(root)
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


def recent_records(root, days=14) -> list:
    try:
        r = subprocess.run(["git", "-C", root, "log", f"--since={days} days ago", "--name-only", "--pretty=format:", "--", "docs/inbox"],
                           capture_output=True, text=True, timeout=10)
        names = sorted({ln.strip() for ln in r.stdout.splitlines() if ln.strip()})
        return names[:30]
    except (OSError, subprocess.SubprocessError):
        return []


# ─────────────────────────────── board upsert ───────────────────────────────

def find_board_issue(issues: list, cfg: dict):
    cands = [i for i in issues if cfg["board"]["label"] in labels_of(i)]
    return min(cands, key=lambda i: i["number"]) if cands else None


def strip_stamp(body: str) -> str:
    return re.sub(r"_Rendered [^\n]*\n", "", body or "")


def upsert_board(gh: GH, snap: dict, cfg: dict, body: str, log=print) -> int:
    issue = find_board_issue(snap["issues"], cfg)
    if issue is None:
        issue = gh.post("{r}/issues", {"title": cfg["board"]["title"], "body": body, "labels": [cfg["board"]["label"], "tracking"]})
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
    node_id = issue.get("node_id") or gh.get(f"{{r}}/issues/{issue['number']}")["node_id"]
    gh.graphql("mutation($id:ID!){pinIssue(input:{issueId:$id}){issue{number}}}", {"id": node_id})


def ensure_labels(gh: GH, log=print) -> int:
    have = {l["name"] for l in gh.paged("{r}/labels")}
    made = 0
    for name, (color, desc) in LABELS.items():
        if name in have:
            continue
        try:
            gh.post("{r}/labels", {"name": name, "color": color, "description": desc[:100]})
            made += 1
        except GitHubError as e:
            log(f"labels: could not create {name}: {e}")
    log(f"labels: {made} created, {len(LABELS) - made} present")
    return made


# ─────────────────────────────── worker pick ────────────────────────────────

def worker_runs_today(gh: GH, workflow_file: str, now, exclude_run_id="") -> int:
    """Runs of the worker workflow since 00:00 UTC whose `implement` job actually started."""
    day = now.strftime("%Y-%m-%d")
    try:
        runs = gh.get(f"{{r}}/actions/workflows/{workflow_file}/runs", created=f">={day}", per_page=50).get("workflow_runs", [])
    except GitHubError:
        return 0
    n = 0
    for r in runs:
        if str(r.get("id")) == str(exclude_run_id):
            continue
        try:
            jobs = gh.get(f"{{r}}/actions/runs/{r['id']}/jobs", per_page=30).get("jobs", [])
        except GitHubError:
            continue
        if any(str(j.get("name", "")).startswith("implement") and j.get("conclusion") not in ("skipped",) for j in jobs):
            n += 1
    return n


def pick(snap: dict, cfg: dict, now=None, runs_today=0, forced_issue=0) -> dict:
    """Decide the worker's next job. Returns {'go': bool, 'reason': str, ...job fields}."""
    now = now or parse_ts(snap["now"])
    w = cfg["worker"]
    issues, prs = snap["issues"], snap["prs"]
    board = find_board_issue(issues, cfg)
    if not w.get("enabled", True):
        return {"go": False, "reason": "worker disabled in .github/autonomy.json"}
    if board and cfg["pause_label"] in labels_of(board):
        return {"go": False, "reason": f"`{cfg['pause_label']}` is set on the board issue #{board['number']}"}
    if runs_today >= int(w["max_runs_per_day"]) and not forced_issue:
        return {"go": False, "reason": f"daily cap reached ({runs_today}/{w['max_runs_per_day']} worker runs today)"}
    bot_prs = [p for p in prs if p["head_ref"].startswith(w["branch_prefix"]) or is_bot(p["user"])]
    live_bot_prs = [p for p in bot_prs if "bot-stuck" not in p["labels"] and not p["review"]["exhausted"]]
    # 1) explicit dispatch for one issue
    if forced_issue:
        i = {i["number"]: i for i in issues}.get(int(forced_issue))
        if not i:
            return {"go": False, "reason": f"#{forced_issue} is not an open issue"}
        return _job(i, prs, w, mode_hint="implement", reason="dispatched for this issue")
    queue = coord.queue(issues, [{"number": p["number"], "body": p["body"]} for p in prs])
    # 2) retry issues (continue an existing branch) come first — finishing beats starting
    for i in queue:
        if "retry" in labels_of(i) and _eligible(i, w):
            return _job(i, prs, w, mode_hint="continue", reason="re-queued work (retry) has priority")
    if len(live_bot_prs) >= int(w["wip_limit"]):
        return {"go": False, "reason": f"WIP limit: {len(live_bot_prs)} unattended PR(s) still open (limit {w['wip_limit']}) — finish before starting"}
    # 3) head of the queue that the planner cleared for unattended work
    for i in queue:
        if _eligible(i, w):
            return _job(i, prs, w, mode_hint="implement", reason="top eligible issue in the ready queue")
    return {"go": False, "reason": "nothing eligible: no `ready` + `auto` unassigned issue that is workable unattended (planner marks `auto`; humans may set worker.eligible=any-ready)"}


def _eligible(i: dict, w: dict) -> bool:
    L = set(labels_of(i))
    if w.get("eligible", "auto") != "any-ready" and "auto" not in L and "retry" not in L:
        return False
    if "hot-file" in L and not w.get("allow_hot_file", False):
        return False
    return True


def _job(i: dict, prs: list, w: dict, mode_hint: str, reason: str) -> dict:
    n = i["number"]
    branch = f"{w['branch_prefix']}{n}-{slugify(i.get('title', ''))}"
    existing = [p for p in prs if n in p["closing"]]
    body = i.get("body") or ""
    m = re.search(r"(?im)^\s*(?:continue on|branch)\s*[:=]?\s*`([^`\s]+)`", body)
    mode, pr_num = mode_hint, 0
    if existing:
        mode, branch, pr_num = "continue", existing[0]["head_ref"], existing[0]["number"]
    elif mode_hint == "continue" and m:
        branch = m.group(1)
    elif mode_hint == "continue":
        mode = "implement"       # nothing to continue from: start clean
    return {"go": True, "reason": reason, "issue": n, "title": i.get("title", ""), "branch": branch, "mode": mode,
            "pr": pr_num, "labels": labels_of(i)}


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
        stuck = "bot-stuck" in L or p["review"]["exhausted"]
        # (a) stuck PR, quiet for long enough -> re-queue its issue(s) for a fresh holder
        if stuck and head_age_h >= float(P["requeue_stuck_after_hours"]):
            for n in p["closing"]:
                i = issues_by.get(n)
                if not i:
                    continue
                acts.append({"op": "requeue", "issue": n, "pr": p["number"], "branch": p["head_ref"],
                             "assignees": [a["login"] for a in i.get("assignees") or []],
                             "summary": p["review"]["last_summary"], "key": f"requeue-{p['number']}-{p['head_sha'][:12]}"})
        # (b) drafts nobody touches
        if p["draft"] and "wip" not in L and "do-not-merge" not in L:
            days = head_age_h / 24
            if days >= float(P["close_stale_days"]):
                acts.append({"op": "close-stale", "pr": p["number"], "branch": p["head_ref"], "closing": p["closing"],
                             "days": int(days), "key": f"close-stale-{p['number']}"})
            elif days >= float(P["stale_draft_days"]) and not (p["review"]["verdict"] in ("approve", "nits") and not p["checks"]["bad"]):
                acts.append({"op": "nudge-stale", "pr": p["number"], "days": int(days),
                             "left": int(float(P["close_stale_days"]) - days), "key": f"stale-{p['number']}-{p['head_sha'][:12]}"})
    # (c) worker leases that produced nothing
    closing_any = set()
    for p in snap["prs"]:
        closing_any.update(p["closing"])
    for i in snap["issues"]:
        if "bot-working" in labels_of(i) and i["number"] not in closing_any:
            upd = parse_ts(i.get("updated_at"))
            if upd and (now - upd).total_seconds() / 3600 >= float(P["worker_lease_hours"]):
                acts.append({"op": "release-lease", "issue": i["number"], "key": f"lease-{i['number']}-{i.get('updated_at','')[:13]}"})
    return acts


def apply_sweep(gh: GH, acts: list, log=print) -> int:
    done = 0
    for a in acts:
        try:
            if a["op"] == "requeue":
                n = a["issue"]
                existing = [c.get("body") or "" for c in gh.comments(n)]
                body = (f"♻️ **Re-queued.** PR #{a['pr']} exhausted the bots' automatic fix budget and has not moved since "
                        f"(last review: {a['summary'] or 'see the PR'}). This issue is `ready` + `retry` again and unassigned so a "
                        f"fresh session — or the unattended worker — can finish it. **Continue on `{a['branch']}`** (push to it; the "
                        f"PR, review and merge machinery re-arm on the new commit, with a fresh fix budget). Previous holder: "
                        f"{', '.join('@' + x for x in a['assignees']) or 'the worker'} — `/claim` to take it back.")
                if gh.comment_once(n, a["key"], body, existing):
                    for u in a["assignees"]:
                        try:
                            gh.request("DELETE", f"{{r}}/issues/{n}/assignees", body={"assignees": [u]})
                        except GitHubError:
                            pass
                    gh.add_labels(n, "ready", "retry")
                    gh.remove_label(n, "bot-working")
                    # The reset marker gives whoever continues on the branch a fresh auto-fix budget.
                    gh.comment_once(a["pr"], a["key"], f"♻️ Issue #{n} re-queued for a fresh holder to continue on this branch.\n\n{RESET_MARK}")
                    done += 1
                    log(f"sweep: re-queued #{n} (stuck PR #{a['pr']})")
            elif a["op"] == "nudge-stale":
                if gh.comment_once(a["pr"], a["key"],
                                   f"🕰️ No commits for {a['days']} days on this draft. If it is alive, push or comment; otherwise it is "
                                   f"closed in ~{a['left']} day(s) (branch kept) and its issue goes back to the queue. Label `wip` to exempt it."):
                    gh.add_labels(a["pr"], "stale")
                    done += 1
                    log(f"sweep: nudged stale draft #{a['pr']}")
            elif a["op"] == "close-stale":
                existing = [c.get("body") or "" for c in gh.comments(a["pr"])]
                if gh.comment_once(a["pr"], a["key"],
                                   f"🧹 Closing: draft with no commits for {a['days']} days. The branch `{a['branch']}` is kept; reopen "
                                   f"and push if you come back to it. Linked issue(s) {' '.join('#%d' % n for n in a['closing']) or '—'} return to the queue.", existing):
                    gh.patch(f"{{r}}/pulls/{a['pr']}", {"state": "closed"})
                    for n in a["closing"]:
                        try:
                            cur = gh.get(f"{{r}}/issues/{n}")
                            if cur.get("state") == "open":
                                for u in [x["login"] for x in cur.get("assignees") or []]:
                                    gh.request("DELETE", f"{{r}}/issues/{n}/assignees", body={"assignees": [u]})
                                gh.add_labels(n, "ready", "retry")
                                gh.comment_once(n, a["key"], f"♻️ PR #{a['pr']} went stale and was closed; this issue is unassigned and "
                                                             f"`ready` + `retry` again. Continue on `{a['branch']}`.")
                        except GitHubError:
                            pass
                    done += 1
                    log(f"sweep: closed stale draft #{a['pr']}")
            elif a["op"] == "release-lease":
                n = a["issue"]
                gh.remove_label(n, "bot-working")
                gh.comment_once(n, a["key"], "🤖 The unattended worker's lease on this issue expired without a PR (run ended or "
                                             "timed out). Released back to the queue; the next worker run or any session may take it.")
                done += 1
                log(f"sweep: released worker lease on #{n}")
        except GitHubError as e:
            log(f"sweep: {a['op']} failed: {e}")
    return done


# ─────────────────────────────── steer ──────────────────────────────────────

def steer_issue(text: str, by: str = "", source: str = "session", logged_by: str = "", when=None) -> dict:
    when = when or utcnow()
    text = (text or "").strip()
    first = re.split(r"(?<=[.!?])\s+|\n", text, maxsplit=1)[0].strip()
    title = "Steer: " + (first[:100] + ("…" if len(first) > 100 else "")) if first else "Steer (see body)"
    who = f"@{by}" if by and not by.startswith("@") else (by or "a human")
    quoted = "\n".join("> " + ln if ln.strip() else ">" for ln in text.splitlines()) or "> (empty)"
    body = (f"## The steer (verbatim)\n\nFrom **{who}** via {source}, {when.strftime('%Y-%m-%d %H:%M UTC')}:\n\n{quoted}\n\n"
            "## What happens next\n\n"
            "The tech leads (the scheduled planner within ~6 h, or any coding session sooner via `/techlead`) triage this: "
            "restate it, file the requirement/task issues it implies (`Refs #<this>` + `from-steer`), record it in "
            "`docs/STEERING.md` if it is standing guidance, then label this issue `triaged`. Disagree with the interpretation? "
            "Comment here — comments from humans on a steer are themselves steers.\n\n"
            f"<!-- steer: source={source}; by={by or '?'}; logged-by={logged_by or '?'}; date={when.strftime('%Y-%m-%d')} -->\n")
    return {"title": title, "body": body, "labels": ["steer"]}


# ─────────────────────────────── hello (SessionStart) ───────────────────────

HELLO = """\
tekton · you are a TECH LEAD here, not a ticket-taker (docs/process/AUTONOMY.md, CLAUDE.md §4).
  1. If your human says anything that changes direction — a want, an opinion, a correction — LOG IT FIRST:
     /steer <their words>   (or: python3 tools/dev/techlead.py steer "..." --by <login>; cloud: MCP issue_write, label `steer`)
  2. Session start: service your open PRs → triage untriaged steers → if the ready queue is thin, plan (/techlead) → then /next.
  3. Never keep state in your head: issue comments, the PR, the record. Bots finish PRs you leave behind (review, fix, ready, merge).
  Board: {board}   Brief: python3 tools/dev/techlead.py brief   Full protocol: CLAUDE.md §4"""


def hello(repo: str, timeout=6.0) -> str:
    board_url = f"https://github.com/{repo}/issues?q=label%3Aboard" if repo else "(no repo detected)"
    lines = [HELLO.format(board=board_url)]
    token = resolve_token(allow_gh_cli=True, timeout=3)
    if not (token and repo):
        lines.append("  (offline: no GH_TOKEN / gh login here — read the board issue in the browser or via MCP issue_read)")
        return "\n".join(lines)
    try:
        gh = GH(repo, token, timeout=timeout)
        issues = [i for i in gh.paged("{r}/issues", state="open", max_pages=2) if not i.get("pull_request")]
        cfg = load_config()
        board = find_board_issue(issues, cfg)
        steers = [i for i in issues if set(labels_of(i)) & {"steer", "intake"} and "triaged" not in labels_of(i)]
        q = coord.queue(issues, [])
        stuck = [i for i in issues if "retry" in labels_of(i)]
        lines.append(f"  Live: {len(steers)} untriaged steer(s) · {len(q)} ready & unassigned (floor {cfg['planner']['ready_floor']}) · "
                     f"{len(stuck)} re-queued (retry) · board: " + (f"https://github.com/{repo}/issues/{board['number']}" if board else board_url))
        if steers:
            lines.append("  Untriaged: " + "; ".join(f"#{i['number']} {i['title'][:60]}" for i in steers[:3]))
        if q:
            lines.append("  Top of queue: " + "; ".join(f"#{i['number']} {i['title'][:50]}" for i in q[:3]))
    except Exception as e:      # noqa: BLE001 — a banner must never break a session
        lines.append(f"  (live status unavailable: {str(e)[:120]})")
    return "\n".join(lines)


# ─────────────────────────────── CLI ────────────────────────────────────────

def _client(args, need_token=True) -> GH:
    repo = resolve_repo(args.repo)
    token = resolve_token()
    if not repo:
        sys.exit("techlead: cannot tell which repo (pass --repo owner/name or set GITHUB_REPOSITORY)")
    if need_token and not token:
        sys.exit("techlead: no GH_TOKEN / GITHUB_TOKEN and no logged-in gh CLI")
    return GH(repo, token)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default="", help="owner/name (default: $GITHUB_REPOSITORY or the origin remote)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("board", help="render + upsert + pin the board issue")
    b.add_argument("--dry-run", action="store_true", help="print the body, change nothing")
    b.add_argument("--no-sweep", action="store_true", help="skip the hygiene sweep that normally runs first")
    r = sub.add_parser("brief", help="print the tech-lead state brief")
    r.add_argument("--json", action="store_true")
    r.add_argument("--out", default="", help="also write it to this file")
    k = sub.add_parser("pick", help="print the worker's next job as JSON (exit 3 = nothing to do)")
    k.add_argument("--issue", type=int, default=0, help="force this issue (workflow_dispatch)")
    k.add_argument("--workflow-file", default="worker.yml")
    k.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT", ""), help="also append key=value lines here")
    s = sub.add_parser("sweep", help="run the hygiene sweep only")
    s.add_argument("--dry-run", action="store_true")
    t = sub.add_parser("steer", help="log a steer issue")
    t.add_argument("text")
    t.add_argument("--by", default="", help="GitHub login (or name) of the human who said it")
    t.add_argument("--source", default="session", help="session | comment | form | requirement-file")
    t.add_argument("--dry-run", action="store_true")
    sub.add_parser("labels", help="create the label vocabulary")
    sub.add_parser("hello", help="SessionStart banner")
    a = ap.parse_args(argv)

    if a.cmd == "hello":
        try:
            print(hello(resolve_repo(a.repo)))
        except Exception as e:  # noqa: BLE001
            print(HELLO.format(board="(see the issue labelled `board`)") + f"\n  ({e})")
        return 0

    cfg = load_config()
    if a.cmd == "steer":
        spec = steer_issue(a.text, by=a.by, source=a.source, logged_by=os.environ.get("GITHUB_ACTOR", ""))
        if a.dry_run:
            print(json.dumps(spec, indent=2, ensure_ascii=False))
            return 0
        gh = _client(a)
        issue = gh.post("{r}/issues", spec)
        print(issue.get("html_url", ""))
        return 0

    gh = _client(a)
    if a.cmd == "labels":
        ensure_labels(gh)
        return 0
    snap = snapshot(gh, cfg, with_runs=(a.cmd in ("board", "brief")))
    now = parse_ts(snap["now"])
    if a.cmd == "sweep" or (a.cmd == "board" and not a.no_sweep):
        acts = plan_sweep(snap, cfg, now)
        if getattr(a, "dry_run", False):
            print(json.dumps(acts, indent=2))
        else:
            if apply_sweep(gh, acts):
                snap = snapshot(gh, cfg)          # re-read: the sweep changed labels/assignees
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
            upsert_board(gh, snap, cfg, body)
        print(f"api calls: {gh.calls}", file=sys.stderr)
        return 0
    if a.cmd == "brief":
        out = json.dumps(model, indent=2, default=str) if a.json else render_brief(model, cfg, gh.repo)
        print(out)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(out)
        return 0
    if a.cmd == "pick":
        runs_today = worker_runs_today(gh, a.workflow_file, now, exclude_run_id=os.environ.get("GITHUB_RUN_ID", ""))
        job = pick(snap, cfg, now, runs_today=runs_today, forced_issue=a.issue)
        job["runs_today"] = runs_today
        print(json.dumps(job, ensure_ascii=False))
        if a.github_output:
            with open(a.github_output, "a", encoding="utf-8") as fh:
                fh.write(f"go={'yes' if job['go'] else 'no'}\n")
                for key in ("issue", "branch", "mode", "pr", "title", "reason"):
                    if key in job:
                        val = str(job[key]).replace("\n", " ")
                        fh.write(f"{key}={val}\n")
        if not job["go"]:
            print(f"pick: {job['reason']}", file=sys.stderr)
            return 3
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
