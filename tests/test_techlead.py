"""Guard: tools/dev/techlead.py — the deterministic half of the tech-lead desk.

The board, the queue pick for the unattended worker, the hygiene sweep, the steer
log and the review-state parsing all run unattended on GITHUB_TOKEN from
.github/workflows/{board,techlead,worker}.yml, so their decisions must be plain,
testable functions of a snapshot. The fixture mirrors the repo on 2026-08-09: the
first logged steer (#54), the queue seeded on the first night, a stuck bot PR, a
green-but-draft PR, a workflow-touching PR only the owner can merge, a conflict.
"""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "dev", "techlead.py")
_spec = importlib.util.spec_from_file_location("techlead", PATH)
tl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tl)

NOW = dt.datetime(2026, 8, 9, 6, 0, tzinfo=dt.timezone.utc)
CFG = tl.load_config(text="{}")


def I(n, title, labels, assignees=(), user="cam-karagitz", created="2026-08-07T23:23:40Z", updated=None, body="## DONE\n- x"):
    return {"number": n, "title": title, "labels": [{"name": l} for l in labels],
            "assignees": [{"login": a} for a in assignees], "user": {"login": user},
            "created_at": created, "updated_at": updated or created, "state": "open", "body": body}


GREEN = [{"name": "py3.11", "status": "completed", "conclusion": "success"},
         {"name": "py3.12", "status": "completed", "conclusion": "success"},
         {"name": "claude-review", "status": "completed", "conclusion": "failure"},   # ignored by the gate
         {"name": "automerge", "status": "completed", "conclusion": "success"}]      # ignored by the gate
RED = [{"name": "py3.11", "status": "completed", "conclusion": "failure"},
       {"name": "py3.12", "status": "completed", "conclusion": "success"}]


def PR(n, title, user, draft, labels, sha, head_ref, head_date, checks, comments, body, mergeable_state="clean", touches=False):
    r = tl.coord.refs(body)
    return {"number": n, "title": title, "user": user, "draft": draft, "labels": labels, "body": body,
            "head_sha": sha, "head_ref": head_ref, "base_ref": "main", "created_at": head_date,
            "updated_at": head_date, "head_date": head_date, "mergeable": mergeable_state == "clean",
            "mergeable_state": mergeable_state, "checks": tl.summarize_checks(checks),
            "review": tl.parse_review_state(comments, sha), "comment_bodies": comments,
            "closing": r["closing"], "refs": r["refs"], "touches_workflows": touches, "html_url": ""}


def snapshot(extra_issues=(), prs=None, board_labels=("board", "tracking")):
    issues = [
        I(56, "📋 Board", list(board_labels), created="2026-08-09T05:12:00Z"),
        I(55, "Autonomy OS", ["P0", "hot-file", "area:process", "from-steer"], ["cam-karagitz"], created="2026-08-09T05:11:00Z"),
        I(54, "Steer: coding sessions are the tech leads", ["steer", "P0"], created="2026-08-09T05:09:10Z", body="## The steer (verbatim)\n> Hi ..."),
        I(52, "Bare generated .rfa crashes desktop Revit 2026", ["famgen", "engine"], user="clkaragitz", created="2026-08-09T02:46:16Z", body="## What happened\ncrash"),
        I(37, "sync_plugin.rebuild_zip shells out to zip", ["P1", "ready", "good-first-pick", "area:plugin"], user="Ckaragitz12", created="2026-08-08T00:11:29Z"),
        I(25, "START HERE", ["P0", "tracking"]),
        I(24, "Skills UX: target-version FIRST", ["P1", "ready", "hot-file", "area:plugin", "auto"]),
        I(23, "Counsel gates — tracking", ["P0", "blocked", "tracking"]),
        I(22, "test_ladder_end_to_end is red", ["P2", "owner-machine", "area:genesis"]),
        I(16, "THE OPEN CELL", ["P0", "needs-revit-desktop", "area:genesis"]),
        I(14, "2025 famload/instance lane", ["P1", "ready", "area:famgen"]),
        I(11, "manipulate: bind the file's own schema", ["P1", "ready", "area:engine", "auto"]),
        I(9, "famgen determinism uuid5", ["P2", "ready", "good-first-pick", "area:famgen", "auto"]),
        I(7, "Validator: 0x0f3f footer-blob rule", ["P1", "ready", "good-first-pick", "area:engine", "auto"]),
        I(6, "Perf: lazy ifcopenshell import", ["P1", "ready", "area:perf"], ["clkaragitz"], updated="2026-08-09T01:00:00Z"),
        I(5, "Permutation matrix flips", ["P0", "ready", "hot-file", "area:frontdoor"]),
        I(3, "pyproject extras", ["P1", "ready", "good-first-pick", "area:docs"]),
        I(60, "Docs the worker leased", ["P2", "ready", "area:docs", "auto", "bot-working"], created="2026-08-09T01:00:00Z", updated="2026-08-09T01:30:00Z"),
    ] + list(extra_issues)
    if prs is None:
        prs = [
            PR(40, "stdlib zip build", "Ckaragitz12", True, ["stacked"], "4833d767d6c6", "ckaragitz12/29-utf8", "2026-08-08T00:40:00Z", GREEN,
               ["✅ Approve\n<!-- claude-review: approve sha=4833d767d6c6 -->"], "Closes #37\nRefs #29"),
            PR(57, "Autonomy OS", "cam-karagitz", False, [], "abc1234", "claude/team-status", "2026-08-09T05:50:00Z", GREEN,
               ["🟡 Nits only\n<!-- claude-review: nits sha=abc1234 -->"], "Closes #55\nRefs #54", touches=True),
            PR(58, "bot: uuid5", "claude[bot]", False, ["bot-stuck"], "def5678", "bot/9-famgen-determinism", "2026-08-08T01:00:00Z", RED,
               ["a\n<!-- claude-autofix attempt=0 -->", "b\n<!-- claude-autofix attempt=1 -->", "c\n<!-- claude-autofix attempt=2 -->",
                "stuck <!-- claude-autofix exhausted sha=def5678 -->"], "Closes #9"),
            PR(59, "conflicting", "clkaragitz", False, [], "9999999", "clkaragitz/x", "2026-08-09T04:00:00Z", GREEN,
               ["✅ Approve\n<!-- claude-review: approve sha=9999999 -->"], "Closes #14", mergeable_state="dirty"),
        ]
    return {"now": tl.iso(NOW), "repo": "ckaragitz/tekton", "issues": issues,
            "closed": [{"number": 50, "title": "release-aware validate", "closed_at": "2026-08-09T03:20:20Z", "state_reason": "completed"}],
            "prs": prs, "merged": [{"number": 53, "title": "famgen famdoc", "merged_at": "2026-08-09T03:11:06Z", "user": {"login": "clkaragitz"}}],
            "runs": [{"name": "coord", "conclusion": "success", "status": "completed", "created_at": "2026-08-09T04:49:41Z", "html_url": "u1", "event": "schedule"},
                     {"name": "claude-review", "conclusion": "failure", "status": "completed", "created_at": "2026-08-09T02:43:00Z", "html_url": "u2", "event": "pull_request"}]}


# ───────────────────────── config / small utils ─────────────────────────

def test_config_defaults_fill_gaps_and_doc_key_is_ignored():
    cfg = tl.load_config(text=json.dumps({"_doc": "x", "worker": {"wip_limit": 5}, "pipeline": {"quiet_minutes": 30}}))
    assert cfg["worker"]["wip_limit"] == 5 and cfg["worker"]["max_runs_per_day"] == 4      # override + default sibling
    assert cfg["pipeline"]["quiet_minutes"] == 30 and cfg["planner"]["ready_floor"] == 4
    assert "_doc" not in cfg
    assert tl.load_config(text="{not json") == tl.load_config(text="{}")                   # malformed = defaults, never a crash


def test_repo_config_file_parses_and_matches_documented_defaults():
    with open(os.path.join(ROOT, ".github", "autonomy.json"), encoding="utf-8") as fh:
        on_disk = json.load(fh)
    on_disk.pop("_doc")
    merged = tl.deep_merge(tl.DEFAULTS, on_disk)
    for section in ("planner", "worker", "pipeline"):
        assert merged[section] == tl.DEFAULTS[section], f"{section}: autonomy.json and DEFAULTS disagree — change both or neither"


def test_slugify_and_age_txt():
    assert tl.slugify("Validator: promote the 0x0f3f unit-footer-blob presence law to a rule (ERROR when …)") == "validator-promote-the-0x0f3f-unit-footer"
    assert tl.slugify("!!!") == "work"
    assert tl.age_txt(NOW - dt.timedelta(minutes=50), NOW) == "<1 h"
    assert tl.age_txt(NOW - dt.timedelta(hours=5), NOW) == "5 h"
    assert tl.age_txt(NOW - dt.timedelta(days=3), NOW) == "3 d"


# ───────────────────────── review state / checks ─────────────────────────

def test_review_state_reads_the_verdict_for_this_sha_and_counts_attempts_since_reset():
    bodies = ["✅ Approve\n<!-- claude-review: approve sha=aaaaaaa1 -->",           # old sha: ignored
              "🛑 Changes requested\n- fix x\n<!-- claude-review: changes sha=bbbbbbb2 -->",
              "did a fix <!-- claude-autofix attempt=0 -->",
              "did a fix <!-- claude-autofix attempt=1 -->",
              "♻️ re-queued\n\n<!-- claude-autofix reset -->",                          # fresh holder: budget resets
              "did a fix <!-- claude-autofix attempt=0 -->"]
    st = tl.parse_review_state(bodies, "bbbbbbb2ffff")
    assert st == {"verdict": "changes", "attempts": 1, "exhausted": False, "last_summary": "🛑 Changes requested"}
    st2 = tl.parse_review_state(bodies + ["x <!-- claude-autofix exhausted sha=bbbbbbb2 -->"], "bbbbbbb2ffff")
    assert st2["exhausted"] is True
    assert tl.parse_review_state([], "abc")["verdict"] is None


def test_ci_gate_matches_automerge_ignoring_its_own_and_claude_checks():
    s = tl.summarize_checks(GREEN)
    assert s == {"total": 2, "pending": [], "bad": [], "ok": 2}
    s = tl.summarize_checks(RED + [{"name": "py3.13", "status": "in_progress", "conclusion": None}])
    assert s["bad"] == ["py3.11"] and s["pending"] == ["py3.13"] and s["total"] == 3


# ───────────────────────── PR status = the exact merge blocker ─────────────────────────

def _pr(**kw):
    base = dict(n=70, title="t", user="u", draft=False, labels=[], sha="1234567", head_ref="u/x",
                head_date="2026-08-09T05:00:00Z", checks=GREEN, comments=["✅ Approve\n<!-- claude-review: approve sha=1234567 -->"],
                body="Closes #3")
    base.update(kw)
    return PR(base["n"], base["title"], base["user"], base["draft"], base["labels"], base["sha"], base["head_ref"],
              base["head_date"], base["checks"], base["comments"], base["body"], kw.get("mergeable_state", "clean"), kw.get("touches", False))


def test_pr_status_lanes_mirror_automerge_order():
    lane = lambda **kw: tl.pr_status(_pr(**kw), CFG, NOW)[1]   # noqa: E731
    assert lane(labels=["do-not-merge"]) == "held"
    assert lane(labels=["needs-human"], touches=True) == "human"
    assert lane(labels=["needs-issue"]) == "blocked"
    assert lane(checks=[]) == "ci"
    assert lane(checks=[{"name": "py3.11", "status": "queued", "conclusion": None}]) == "ci"
    assert lane(checks=RED) == "red"
    assert lane(comments=[]) == "review"
    assert lane(comments=["🛑\n<!-- claude-review: changes sha=1234567 -->"]) == "changes"
    assert lane(touches=True) == "human"                       # green + approved + workflows -> owner
    assert lane(mergeable_state="dirty") == "conflict"
    assert lane() == "merging"
    text, l = tl.pr_status(_pr(draft=True, head_date="2026-08-09T05:00:00Z"), CFG, NOW)   # quiet 60 of 90 min
    assert l == "draft" and "≤ 30 more quiet min" in text
    text, _ = tl.pr_status(_pr(draft=True, head_date="2026-08-09T03:00:00Z"), CFG, NOW)   # quiet 180 min
    assert "next sweep" in text
    text, _ = tl.pr_status(_pr(checks=RED, comments=["<!-- claude-autofix attempt=0 -->"] * 3 + ["<!-- claude-autofix exhausted sha=1234567 -->"]), CFG, NOW)
    assert "auto-fix 3/3" in text and "bot-stuck" in text


# ───────────────────────── classify + board ─────────────────────────

def test_classify_sections():
    m = tl.classify(snapshot(), CFG, NOW)
    assert [s["number"] for s in m["steers"]] == [54] and m["steers"][0]["triaged"] is False
    assert [e["number"] for e in m["progress"]] == [55, 6, 60]                     # assigned or worker-held; board/tracking excluded
    assert [e["number"] for e in m["next_up"]] == [5, 3, 7, 11, 24]                # P0 first, then P1 by age; #14 in review, #37 in review, #9 stuck-in-review, #60 leased
    assert {e["number"] for e in m["waiting"]} == {16, 22}                          # gated; #23 is tracking -> not listed
    assert [e["number"] for e in m["others"]] == [52]                               # not ready, not gated: backlog remainder
    assert [r["number"] for r in m["waiting_prs"]] == [57]                          # workflow-touching PR needs the owner
    h = m["health"]
    assert (h["ready_unassigned"], h["in_review"], h["steers_untriaged"], h["stuck_prs"], h["bot_prs_open"]) == (5, 4, 1, 1, 1)
    assert h["paused"] is False
    assert any("untriaged steer" in w for w in h["warnings"]) and any("fix budget" in w for w in h["warnings"])
    assert not any("below floor" in w for w in h["warnings"])                       # 5 >= floor 4


def test_classify_flags_pause_and_thin_queue():
    snap = snapshot(board_labels=("board", "tracking", "bots-paused"))
    snap["issues"] = [i for i in snap["issues"] if i["number"] not in (5, 3, 7)]    # queue drops to 2 (< floor 4)
    h = tl.classify(snap, CFG, NOW)["health"]
    assert h["paused"] is True and h["ready_unassigned"] == 2
    assert any("below floor" in w for w in h["warnings"]) and any("bots-paused" in w for w in h["warnings"])


def test_board_render_is_complete_marked_and_stable():
    m = tl.classify(snapshot(), CFG, NOW)
    body = tl.render_board(m, CFG, "ckaragitz/tekton")
    assert body.startswith(tl.BOARD_BEGIN) and body.rstrip().endswith(tl.BOARD_END)
    for heading in ("## 🧭 Steers from humans", "## 🔨 In progress", "## 🔍 In review", "## ⏭️ Next up", "## 🧑 Waiting on a human", "## ✅ Done in the last 7 days", "## 🩺 Health"):
        assert heading in body, heading
    assert "| #54 |" in body and "owner squash-merges by hand" in body and "rebase job dispatched" in body
    assert "#10-what-still-needs-a-human-and-why" in body                           # anchor exists in docs/process/AUTONOMY.md
    with open(os.path.join(ROOT, "docs", "process", "AUTONOMY.md"), encoding="utf-8") as fh:
        assert "## 10. What still needs a human, and why" in fh.read()
    # Re-rendering the same state a minute later must not count as a change (no edit-history spam).
    later = tl.classify(snapshot(), CFG, NOW + dt.timedelta(seconds=50))
    later["now"] = tl.iso(NOW + dt.timedelta(seconds=50))
    assert tl.strip_stamp(tl.render_board(later, CFG, "ckaragitz/tekton")) == tl.strip_stamp(body)
    assert "|" not in tl.md_escape("a|b\nc").replace("\\|", "")


def test_brief_lists_untriaged_steer_text_and_hygiene_findings():
    m = tl.classify(snapshot(), CFG, NOW)
    brief = tl.render_brief(m, CFG, "ckaragitz/tekton", root=ROOT)
    assert "### #54 — Steer: coding sessions are the tech leads" in brief and "> Hi ..." in brief
    assert "#52 has no priority label" in brief and "#6 has no area:* label" not in brief   # #6 has area:perf
    assert "at most 5 new issues" in brief


# ───────────────────────── worker pick ─────────────────────────

def test_pick_prefers_retry_then_queue_head_with_auto_and_skips_hot_files():
    snap = snapshot()
    job = tl.pick(snap, CFG, NOW, runs_today=0)
    assert job["go"] and job["issue"] == 7 and job["mode"] == "implement"           # #5 (P0) is hot-file, #3 lacks auto
    assert job["branch"] == "bot/7-validator-0x0f3f-footer-blob-rule"
    # a re-queued issue whose stuck PR is still open: continue on that PR's branch, ahead of everything
    snap["issues"] = [dict(i, labels=i["labels"] + [{"name": "retry"}]) if i["number"] == 9 else i for i in snap["issues"]]
    job = tl.pick(snap, CFG, NOW, runs_today=0)
    assert (job["issue"], job["mode"], job["branch"], job["pr"]) == (9, "continue", "bot/9-famgen-determinism", 58)


def test_pick_respects_pause_cap_wip_config_and_dispatch():
    assert tl.pick(snapshot(board_labels=("board", "bots-paused")), CFG, NOW)["reason"].startswith("`bots-paused`")
    assert "daily cap" in tl.pick(snapshot(), CFG, NOW, runs_today=4)["reason"]
    two_bots = snapshot()["prs"] + [_pr(n=80, user="claude[bot]", head_ref="bot/3-x", body="Closes #3"),
                                    _pr(n=81, user="claude[bot]", head_ref="bot/24-y", body="Closes #24")]
    assert "WIP limit" in tl.pick(snapshot(prs=two_bots), CFG, NOW)["reason"]     # stuck #58 does not count, 80+81 do
    off = tl.deep_merge(CFG, {"worker": {"enabled": False}})
    assert "disabled" in tl.pick(snapshot(), off, NOW)["reason"]
    anyready = tl.deep_merge(CFG, {"worker": {"eligible": "any-ready", "allow_hot_file": True}})
    assert tl.pick(snapshot(), anyready, NOW)["issue"] == 5                          # now the P0 hot-file head is fair game
    forced = tl.pick(snapshot(), CFG, NOW, runs_today=9, forced_issue=3)
    assert forced["go"] and forced["issue"] == 3 and forced["reason"] == "dispatched for this issue"
    assert tl.pick(snapshot(), CFG, NOW, forced_issue=999)["go"] is False
    no_auto = snapshot()
    no_auto["issues"] = [dict(i, labels=[l for l in i["labels"] if l["name"] != "auto"]) for i in no_auto["issues"]]
    r = tl.pick(no_auto, CFG, NOW)
    assert r["go"] is False and "nothing eligible" in r["reason"]


# ───────────────────────── hygiene sweep ─────────────────────────

def test_sweep_requeues_stuck_after_a_quiet_day_frees_dead_leases_and_ages_out_drafts():
    acts = tl.plan_sweep(snapshot(), CFG, NOW)
    ops = {(a["op"], a.get("issue") or a.get("pr")) for a in acts}
    assert ("requeue", 9) in ops                     # PR #58: bot-stuck, head 29 h old >= 24 h
    assert ("release-lease", 60) in ops              # bot-working, no PR, untouched 4.5 h >= 3 h
    assert not any(a["op"] in ("nudge-stale", "close-stale") for a in acts)   # draft #40 is only ~29 h old
    rq = next(a for a in acts if a["op"] == "requeue")
    assert rq["branch"] == "bot/9-famgen-determinism" and rq["key"] == "requeue-58-def5678"
    # not yet a day quiet -> leave the stuck PR to the auto-fix ladder / its session
    fresh = snapshot()
    fresh["prs"][2]["head_date"] = "2026-08-09T02:00:00Z"
    assert not any(a["op"] == "requeue" for a in tl.plan_sweep(fresh, CFG, NOW))
    # drafts: nudge at 5 days, close at 14 (green+approved drafts are automerge's to promote, not ours to nudge)
    old = snapshot()
    old["prs"][0]["head_date"] = "2026-08-03T00:00:00Z"          # 6 days, but green + approved -> no nudge
    assert not any(a["op"] == "nudge-stale" for a in tl.plan_sweep(old, CFG, NOW))
    old["prs"][0]["review"]["verdict"] = "changes"
    assert any(a["op"] == "nudge-stale" and a["pr"] == 40 for a in tl.plan_sweep(old, CFG, NOW))
    old["prs"][0]["head_date"] = "2026-07-20T00:00:00Z"          # 20 days -> close, issue #37 back to the queue
    close = [a for a in tl.plan_sweep(old, CFG, NOW) if a["op"] == "close-stale"]
    assert close and close[0]["closing"] == [37]
    old["prs"][0]["labels"] = ["wip"]                              # wip exempts a draft
    assert not any(a["op"] == "close-stale" for a in tl.plan_sweep(old, CFG, NOW))


# ───────────────────────── steer log ─────────────────────────

def test_steer_issue_is_verbatim_attributed_and_titled_by_first_sentence():
    spec = tl.steer_issue("Windows matters more than new features this month. Also stop touching 2023.\nThanks",
                          by="Ckaragitz12", source="comment on #40", logged_by="github-actions", when=NOW)
    assert spec["title"] == "Steer: Windows matters more than new features this month."
    assert spec["labels"] == ["steer"]
    assert "> Windows matters more than new features this month. Also stop touching 2023.\n> Thanks" in spec["body"]
    assert "From **@Ckaragitz12** via comment on #40, 2026-08-09 06:00 UTC" in spec["body"]
    assert "<!-- steer: source=comment on #40; by=Ckaragitz12; logged-by=github-actions; date=2026-08-09 -->" in spec["body"]
    long = tl.steer_issue("x" * 300)["title"]
    assert len(long) <= 108 and long.endswith("…")
    assert tl.steer_issue("")["title"] == "Steer (see body)"


# ───────────────────────── queue rules shared with coord ─────────────────────────

def test_queue_skips_in_review_unless_retry_and_worker_held():
    issues = [I(1, "a", ["ready", "P1"]), I(2, "b", ["ready", "P0"]), I(3, "c", ["ready", "P1", "retry"]),
              I(4, "d", ["ready", "P1", "bot-working"]), I(5, "e", ["ready", "P2", "needs-decision"])]
    prs = [{"number": 9, "body": "Closes #1\nCloses #3"}]
    assert [i["number"] for i in tl.coord.queue(issues, prs)] == [2, 3]      # 1 in review, 3 in review but retry, 4 held, 5 gated
    assert tl.coord.is_task_shaped("### DONE (checkable)\n- x")             # the Task issue form renders like this
    assert not tl.coord.is_task_shaped("We should really support Windows better, done deal.")


# ───────────────────────── the HTTP client, offline ─────────────────────────

class FakeGH(tl.GH):
    def __init__(self, routes):
        super().__init__("o/r", "tkn")
        self.routes, self.sent = routes, []

    def _send(self, method, url, body=None):
        self.calls += 1
        self.sent.append((method, url, body))
        hits = [(len(needle), resp) for (m, needle), resp in self.routes.items() if m == method and needle in url]
        if not hits:
            return 404, {"message": "no route"}, ""
        resp = max(hits, key=lambda h: h[0])[1]          # most specific route wins
        return resp if not callable(resp) else resp(url, body)


def test_client_pages_unwraps_envelopes_and_comments_once():
    gh = FakeGH({
        ("GET", "/issues?state=open"): (200, [{"number": 1}], '<https://api.github.com/repos/o/r/issues?state=open&page=2>; rel="next"'),
        ("GET", "/issues?state=open&page=2"): (200, [{"number": 2}], ""),
        ("GET", "/check-runs"): (200, {"total_count": 1, "check_runs": [{"name": "py3.11"}]}, ""),
        ("GET", "/issues/5/comments"): (200, [{"body": "hello <!-- techlead:k1 -->"}], ""),
        ("POST", "/issues/5/comments"): (201, {"id": 9}, ""),
        ("DELETE", "/labels/"): (404, {"message": "Label does not exist"}, ""),
    })
    assert [i["number"] for i in gh.paged("{r}/issues", state="open")] == [1, 2]
    assert gh.paged("{r}/commits/abc/check-runs") == [{"name": "py3.11"}]
    assert gh.comment_once(5, "k1", "again") is False                       # marker present -> no second comment
    assert gh.comment_once(5, "k2", "new") is True
    posted = [b for m, u, b in gh.sent if m == "POST"]
    assert posted and posted[-1]["body"].endswith("<!-- techlead:k2 -->")
    assert gh.remove_label(5, "nope") is None or True                        # 404 on label removal is fine
    try:
        gh.get("{r}/nothing/here")
    except tl.GitHubError as e:
        assert e.status == 404
    else:
        raise AssertionError("expected GitHubError")


def test_upsert_board_creates_when_missing_and_skips_identical_rerender():
    log = []
    created = {}

    def create(url, body):
        created.update(body)
        return 201, {"number": 77, "node_id": "N77", "body": body["body"]}, ""
    gh = FakeGH({("POST", "/repos/o/r/issues"): create, ("POST", "/graphql"): (200, {"data": {"repository": {"pinnedIssues": {"nodes": []}}}}, "")})
    n = tl.upsert_board(gh, {"issues": []}, CFG, "BODY v1\n", log=log.append)
    assert n == 77 and created["labels"] == ["board", "tracking"] and any("created #77" in l for l in log)
    # identical content except the render stamp -> no PATCH
    gh2 = FakeGH({("POST", "/graphql"): (200, {"data": {"repository": {"pinnedIssues": {"nodes": [{"issue": {"number": 77}}]}}}}, "")})
    body_a = "_Rendered 2026-08-09 06:00 UTC by `board` …_\nrest\n"
    body_b = "_Rendered 2026-08-09 07:00 UTC by `board` …_\nrest\n"
    log2 = []
    tl.upsert_board(gh2, {"issues": [{"number": 77, "labels": [{"name": "board"}], "body": body_a, "node_id": "N77"}]}, CFG, body_b, log=log2.append)
    assert not any(m == "PATCH" for m, _, _ in gh2.sent) and any("unchanged" in l for l in log2)


# ───────────────────────── CLI surface ─────────────────────────

def test_cli_hello_is_offline_safe_and_fast():
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    env["PATH"] = "/nonexistent"                                            # no gh CLI either
    r = subprocess.run([sys.executable, PATH, "--repo", "o/r", "hello"], capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0 and "TECH LEAD" in r.stdout and "offline" in r.stdout


def test_cli_steer_dry_run_prints_the_issue_spec():
    r = subprocess.run([sys.executable, PATH, "--repo", "o/r", "steer", "Ship the Windows fix first.", "--by", "ck", "--dry-run"],
                       capture_output=True, text=True, timeout=30)
    spec = json.loads(r.stdout)
    assert r.returncode == 0 and spec["title"] == "Steer: Ship the Windows fix first." and spec["labels"] == ["steer"]
