"""Guard: tools/dev/techlead.py — the deterministic half of the tech-lead desk.

The board, the queue pick for the unattended worker, the hygiene sweep, the steer
log and the review-state parsing all run unattended on GITHUB_TOKEN from
.github/workflows/{board,techlead,worker}.yml, so their decisions must be plain,
testable functions of a snapshot. The fixture mirrors the repo on 2026-08-09: the
first logged steer (#54), the queue seeded on the first night, a stuck bot PR, a
green-but-draft PR, a workflow-touching PR only the owner can merge, a conflict.

The second half pins the vocabulary this file SHARES with the bash merge machine
(.github/workflows/automerge.yml, claude-review.yml): labels, comment markers, the
closing-keyword grammar and the config fallbacks. automerge is bash-with-no-checkout
on purpose (a broken techlead.py on main must never halt merging), so the two can
only be kept in step by tests like these.
"""
import datetime as dt
import glob
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "dev", "techlead.py")
WF = os.path.join(ROOT, ".github", "workflows")
_spec = importlib.util.spec_from_file_location("techlead", PATH)
tl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tl)

NOW = dt.datetime(2026, 8, 9, 6, 0, tzinfo=dt.timezone.utc)
CFG = tl.load_config(text="{}")


def _wf(name):
    with open(os.path.join(WF, name), encoding="utf-8") as fh:
        return fh.read()


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


def PR(n, title, user, draft, labels, sha, head_ref, head_date, checks, comments, body,
       mergeable_state="clean", touches=False, touches_reviewer=False):
    r = tl.coord.refs(body)
    return {"number": n, "title": title, "user": user, "draft": draft, "labels": labels, "body": body,
            "head_sha": sha, "head_ref": head_ref, "created_at": head_date, "head_date": head_date,
            "mergeable": mergeable_state == "clean", "mergeable_state": mergeable_state,
            "checks": tl.summarize_checks(checks), "review": tl.parse_review_state(comments, sha),
            "comment_bodies": comments, "closing": r["closing"], "refs": r["refs"],
            "touches_workflows": touches or touches_reviewer, "touches_reviewer": touches_reviewer}


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
               [], "Closes #55\nRefs #54", touches_reviewer=True),
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


def test_autonomy_json_is_complete_and_the_fallbacks_agree_with_it():
    """The JSON is authoritative; DEFAULTS and the workflows' `jq // N` literals are only fallbacks
    for a missing file, so they must carry the same keys and numbers (docs/process/AUTONOMY.md §11)."""
    with open(os.path.join(ROOT, ".github", "autonomy.json"), encoding="utf-8") as fh:
        on_disk = json.load(fh)
    on_disk.pop("_doc")

    def walk(d, prefix=""):
        for k, v in d.items():
            yield from walk(v, f"{prefix}{k}.") if isinstance(v, dict) else [(f"{prefix}{k}", v)]
    defaults, disk = dict(walk(tl.DEFAULTS)), dict(walk(on_disk))
    assert set(defaults) == set(disk), f"keys differ: {set(defaults) ^ set(disk)}"
    assert defaults == disk, {k: (defaults[k], disk[k]) for k in defaults if defaults[k] != disk[k]}
    # every `.section.key // literal` in a workflow reads a real key and falls back to the same value
    seen = 0
    for path in glob.glob(os.path.join(WF, "*.yml")):
        for key, lit in re.findall(r"'\.([a-z_]+\.[a-z_]+) // ([0-9]+)'", _wf(os.path.basename(path))):
            assert key in disk, f"{os.path.basename(path)} reads unknown knob {key}"
            assert int(lit) == disk[key], f"{os.path.basename(path)}: {key} // {lit} but autonomy.json says {disk[key]}"
            seen += 1
    assert seen >= 4      # quiet_minutes, review_wait/stuck (automerge), max_fix_attempts (claude-review)


def test_slugify_age_and_stamps():
    assert tl.slugify("Validator: promote the 0x0f3f unit-footer-blob presence law to a rule (ERROR when …)") == "validator-promote-the-0x0f3f-unit-footer"
    assert tl.slugify("!!!") == "work"
    assert tl.age_txt(NOW - dt.timedelta(minutes=50), NOW) == "50 min"
    assert tl.age_txt(NOW - dt.timedelta(hours=5), NOW) == "5 h"
    assert tl.age_txt(NOW - dt.timedelta(days=3), NOW) == "3 d"
    assert tl.at("2026-08-09T05:11:00Z") == "08-09 05:11" and tl.at(None) == "?"


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
    assert s == {"total": 2, "pending": [], "bad": [], "ok": 2, "green": True}
    s = tl.summarize_checks(RED + [{"name": "py3.13", "status": "in_progress", "conclusion": None}])
    assert s["bad"] == ["py3.11"] and s["pending"] == ["py3.13"] and s["total"] == 3 and s["green"] is False
    assert tl.summarize_checks([])["green"] is False


# ───────────────────────── PR status = the exact merge blocker ─────────────────────────

def _pr(**kw):
    base = dict(n=70, title="t", user="u", draft=False, labels=[], sha="1234567", head_ref="u/x",
                head_date="2026-08-09T05:00:00Z", checks=GREEN, comments=["✅ Approve\n<!-- claude-review: approve sha=1234567 -->"],
                body="Closes #3")
    base.update(kw)
    return PR(base["n"], base["title"], base["user"], base["draft"], base["labels"], base["sha"], base["head_ref"],
              base["head_date"], base["checks"], base["comments"], base["body"], kw.get("mergeable_state", "clean"),
              kw.get("touches", False), kw.get("touches_reviewer", False))


def test_pr_status_lanes_mirror_automerge_order():
    lane = lambda **kw: tl.pr_status(_pr(**kw), CFG)[1]   # noqa: E731
    text = lambda **kw: tl.pr_status(_pr(**kw), CFG)[0]   # noqa: E731
    assert lane(labels=["do-not-merge"]) == "held"
    assert lane(labels=["needs-human"], touches=True) == "human"           # GitHub refused the merge: a person
    assert lane(labels=["session-merge"], touches=True) == "session"       # bots may not merge it: any session does
    assert lane(labels=["duplicate-pr"]) == "human"
    assert lane(labels=["needs-issue"]) == "merging" and "no linked issue" in text(labels=["needs-issue"])   # a note, not a blocker (automerge does not check it)
    assert lane(checks=[]) == "ci"
    assert lane(checks=[{"name": "py3.11", "status": "queued", "conclusion": None}]) == "ci"
    assert lane(checks=RED) == "red"
    assert lane(comments=[]) == "review"
    assert lane(comments=[], touches_reviewer=True) == "review"                       # reviewer edit: independent verdict from main required first (#88)
    assert "independent verdict" in text(comments=[], touches_reviewer=True)
    assert lane(comments=[], labels=["merge-when-green"]) == "merging"                # human approval substitutes for the verdict
    assert lane(comments=["🛑\n<!-- claude-review: changes sha=1234567 -->"]) == "changes"
    assert lane(touches=True) == "session"                     # green + approved + workflows -> the next session merges it
    assert lane(mergeable_state="dirty") == "conflict"
    assert lane() == "merging"
    t, l = tl.pr_status(_pr(draft=True, head_date="2026-08-09T05:00:00Z"), CFG)
    assert l == "draft" and "auto-marked ready ≈ 08-09 06:30 UTC" in t                # last push 05:00 + 90 quiet min, absolute
    assert lane(draft=True, labels=["wip"]) == "held"
    t, _ = tl.pr_status(_pr(checks=RED, comments=["<!-- claude-autofix attempt=0 -->"] * 3 + ["<!-- claude-autofix exhausted sha=1234567 -->"]), CFG)
    assert "attempts 3/3" in t and "bot-stuck" in t and "bot fix pass after 15 quiet min" in t


def test_board_and_automerge_share_one_vocabulary():
    """Every label automerge/claude-review act on is one the board knows how to explain, and the
    comment markers both sides parse are spelled identically."""
    am, cr = _wf("automerge.yml"), _wf("claude-review.yml")
    acted_on = set(re.findall(r"(?:has_label|add_label|drop_label) ([a-z][a-z-]+)", am))
    assert {"do-not-merge", "needs-human", "session-merge", "duplicate-pr", "merge-when-green", "wip", "needs-rebase", "bot-stuck"} <= acted_on
    src = open(PATH, encoding="utf-8").read()
    for label in acted_on:
        assert label in tl.LABELS, f"automerge acts on `{label}` but LABELS does not define it"
        assert f'"{label}"' in src, f"automerge acts on `{label}` but techlead.py never mentions it"
    # markers: written by claude-review.yml / automerge.yml, read by parse_review_state
    marker_grep = "<!-- claude-review: (approve|nits|changes) sha=[0-9a-f]{12,40} -->"     # matched by >=12-hex prefix of the head (#90)
    assert marker_grep in cr and marker_grep in am
    assert "<!-- claude-review: approve sha=${{ steps.ctx.outputs.sha }} -->" in cr   # ...and WRITTEN with the exact, full head SHA
    assert tl.VERDICT_RE.search("<!-- claude-review: nits sha=abcdef1 -->")
    assert "<!-- claude-autofix attempt=" in cr and tl.ATTEMPT_RE.search("<!-- claude-autofix attempt=2 -->")
    assert tl.RESET_MARK in cr and tl.RESET_MARK in src
    assert "<!-- claude-autofix exhausted sha=$2 -->" in cr and tl.EXHAUSTED_RE.search("<!-- claude-autofix exhausted sha=abcdef1 -->")
    assert tl.REVIEWER_WORKFLOW == ".github/workflows/claude-review.yml" and '".github/workflows/claude-review.yml"' in am


def test_automerge_closing_keyword_grammar_is_coords():
    """automerge has no checkout, so it carries coord.py's CLOSING grammar as an inline python
    snippet (CLOSES_PY). Run that snippet and coord.refs() over the same bodies."""
    m = re.search(r"CLOSES_PY: \|\n((?:            .*\n)+)", _wf("automerge.yml"))
    assert m, "CLOSES_PY block not found in automerge.yml"
    snippet = "\n".join(line[12:] for line in m.group(1).splitlines())
    bodies = ["Closes #12\nRefs #3", "closes: #7 and FIXES #8, resolved  #9", "<!-- Closes #99 -->\nRefs #1",
              "does not close #5 (GitHub closes it anyway)", "pre-closes #4 nothing", "Fixed #10.\nfix #11"]
    for body in bodies:
        out = subprocess.run([sys.executable, "-c", snippet], input=body, capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        got = [int(x) for x in out.stdout.split()]
        assert got == tl.coord.refs(body)["closing"], (body, got)


def test_workflows_only_create_labels_the_vocabulary_owns():
    for name in ("automerge.yml", "claude-review.yml", "coord.yml", "worker.yml", "techlead.yml", "board.yml"):
        for label in re.findall(r"gh label create ([a-z][a-z:-]+)", _wf(name)):
            assert label in tl.LABELS, f"{name} creates label `{label}` that tools/dev/techlead.py LABELS does not own"


def test_merge_gate_ignores_exactly_the_bots_own_jobs():
    """A bot job's check run on a PR head (cancelled board render, coord pr-check, …) is not CI (#64).
    Both sides carry the same ignore-list; every job of every non-CI workflow must be on it."""
    for path in glob.glob(os.path.join(WF, "*.yml")):
        name = os.path.basename(path)
        if name == "ci.yml":
            continue
        text = _wf(name)
        jobs_block = text.split("\njobs:\n", 1)[1]
        job_ids = re.findall(r"(?m)^  ([a-z][a-z0-9-]*):\s*$", jobs_block)
        job_names = re.findall(r"(?m)^    name: ([A-Za-z0-9$.{} _-]+)$", jobs_block)
        assert job_ids, f"{name}: no jobs parsed"
        for j in job_ids + job_names:
            assert tl.is_bot_check(j.strip()), f"{name}: job `{j}` is not in techlead.BOT_CHECK_NAMES — the merge gate would treat its check run as CI"
    # CI's own jobs must NOT be ignored
    ci_jobs = re.findall(r"(?m)^    name: (.+)$", _wf("ci.yml").split("\njobs:\n", 1)[1])
    assert ci_jobs and not any(tl.is_bot_check(j.replace("${{ matrix.python-version }}", "3.11")) for j in ci_jobs)
    assert not tl.is_bot_check("py3.11") and not tl.is_bot_check("windows / py3.12")
    # automerge's inline list is the same set
    m = re.search(r"IGNORED_CHECKS='([^']+)'", _wf("automerge.yml"))
    assert m, "IGNORED_CHECKS not found in automerge.yml"
    assert set(json.loads("[" + m.group(1) + "]")) == set(tl.BOT_CHECK_NAMES)
    # and a cancelled render no longer reads as red
    s = tl.summarize_checks(GREEN + [{"name": "render", "status": "completed", "conclusion": "cancelled"},
                                     {"name": "pr-check", "status": "completed", "conclusion": "failure"}])
    assert s["green"] is True and s["bad"] == []


def test_fix_pass_is_dispatched_after_a_grace_window_never_inline():
    """Steer #67 / issue #69: a live session fixes first; bots only after pipeline.fix_grace_minutes,
    dispatched by automerge from the default branch; the review job never fixes inline; no
    workflow_run auto-fix on red CI."""
    am, cr = _wf("automerge.yml"), _wf("claude-review.yml")
    assert "'.pipeline.fix_grace_minutes // 15'" in am and "maybe_dispatch_fix" in am
    assert re.search(r'gh workflow run claude-review\.yml --repo "\$REPO" --ref "\$DEFAULT" -f pr="\$pr" -f mode=fix', am)
    assert "-f mode=review" in am                                    # re-requests also come from the default branch
    on_block = cr.split("\non:\n", 1)[1].split("\nconcurrency:", 1)[0]
    keys = "\n".join(ln for ln in on_block.splitlines() if not ln.lstrip().startswith("#"))
    assert "workflow_run" not in keys and "mode:" in keys
    review_job = cr.split("\n  claude-review:\n", 1)[1].split("\n  fix:\n", 1)[0]
    assert "anthropics/claude-code-action" in review_job and "Auto-fix" not in review_job and "claude-autofix attempt=${{" not in review_job
    fix_job = cr.split("\n  fix:\n", 1)[1]
    assert "inputs.mode == 'fix'" in fix_job and "<!-- claude-autofix attempt=" in fix_job and "park_stuck" in fix_job
    assert tl.is_bot_check("fix")


def test_workflow_file_prs_need_a_verdict_before_session_merge():
    """#88: automerge applies `session-merge` only on the approved path; a reviewer edit gets its
    verdict from a review dispatched on the default branch; no verdict obtainable -> needs-human."""
    am = _wf("automerge.yml")
    no_verdict = am.split("if [ -z \"$approved_by\" ]; then", 1)[1].split("if [ \"$draft\" = \"true\" ]; then", 1)[0]
    assert "add_label session-merge" not in no_verdict, "session-merge must never be offered before a verdict exists"
    assert "-f mode=review" in no_verdict and "add_label needs-human" in no_verdict and "other than the author" in no_verdict
    assert "drop_label needs-human" in am, "the human gate must lift itself once the approval it asked for exists"
    assert 'has_marker "merge-failed-$sha"' in am, "a merge GitHub refused at this head must stay a true stop (no thrashing)"
    # Our own bots dispatch or author these runs (automerge re-requests, coord wake-ups, planner/worker PRs):
    # the action rejects every non-human actor unless allowed_bots names them.
    for wf_name in ("claude-review.yml", "techlead.yml", "worker.yml", "claude.yml"):
        text = _wf(wf_name)
        uses = text.count("uses: anthropics/claude-code-action@v1")
        assert uses and text.count("allowed_bots:") == uses, f"{wf_name}: every claude-code-action step must set allowed_bots"
        assert "github-actions[bot]" in text and "claude[bot]" in text
    approved = am.split("if [ \"$touches_wf\" != \"0\" ]; then", 1)[1].split("if [ \"$mergeable\" = \"CONFLICTING\" ]", 1)[0]
    assert "add_label session-merge" in approved and "--match-head-commit" in approved
    for wf_name in ("worker.yml", "techlead.yml"):
        text = _wf(wf_name)
        top = "\n".join(ln.split("#", 1)[0] for ln in text.split("\njobs:\n", 1)[0].splitlines())   # permission keys, not comments
        assert "actions: read" in top and "actions: write" not in top, f"{wf_name}: the model job must not hold actions: write"
        assert "\n  refresh-board:\n" in text and "actions: write" in text.split("\n  refresh-board:\n", 1)[1]
    assert tl.is_bot_check("refresh-board")


def test_session_locks_and_the_resume_rule():
    """steer #90: locks are per session; standing = holder still assigned and not unlocked since;
    the earliest standing lock wins; `mine` judges this-session / active-elsewhere / idle."""
    coord = tl.coord
    lm, um = coord.lock_marker, coord.unlock_marker
    cs = [{"id": 1, "created_at": "2026-08-09T10:00:00Z", "body": "🔒 " + lm("cam", "laptop", "111")},
          {"id": 2, "created_at": "2026-08-09T10:00:03Z", "body": "🔒 " + lm("cam", "phone", "222")},
          {"id": 3, "created_at": "2026-08-09T10:00:04Z", "body": "🔒 " + lm("chase", "desk", "333")}]
    locks = coord.standing_locks(cs, ["cam", "chase"])
    assert [(l["by"], l["session"]) for l in locks] == [("cam", "laptop"), ("cam", "phone"), ("chase", "desk")]
    assert coord.standing_locks(cs, ["chase"])[0]["session"] == "desk"            # cam unassigned -> cam's locks lapse
    cs2 = cs + [{"id": 4, "created_at": "2026-08-09T11:00:00Z", "body": "released " + um("cam")},
                {"id": 5, "created_at": "2026-08-09T12:00:00Z", "body": "🔒 " + lm("cam", "cloud", "555")}]
    assert [(l["session"]) for l in coord.standing_locks(cs2, ["cam"])] == ["cloud"]  # unlock marker resets cam's epoch
    # coord's re-lock / take-over reply carries the unlock AND the fresh lock in ONE comment: the fresh
    # lock must stand (review finding on #107), and older locks of that holder must not.
    cs3 = cs + [{"id": 6, "created_at": "2026-08-09T12:30:00Z",
                 "body": "🔒 @cam holds #5 (session tablet, taken over). " + um("cam") + "\n" + lm("cam", "tablet", "666")}]
    relocked = coord.standing_locks(cs3, ["cam", "chase"])
    assert [(l["by"], l["session"]) for l in relocked] == [("chase", "desk"), ("cam", "tablet")]
    assert [l["session"] for l in relocked if l["by"] == "cam"] == ["tablet"]                # laptop/phone released, tablet stands
    # first standing assignee = single-holder's replay rule
    ev = [{"event": "assigned", "assignee": {"login": "a"}}, {"event": "assigned", "assignee": {"login": "b"}},
          {"event": "unassigned", "assignee": {"login": "a"}}, {"event": "assigned", "assignee": {"login": "a"}}]
    assert tl.first_standing_assignee(ev, ["a", "b"]) == "b" and tl.first_standing_assignee([], ["z"]) == "z"
    # the resume rule
    now = dt.datetime(2026, 8, 9, 10, 30, tzinfo=dt.timezone.utc)
    issue = {"number": 7, "updated_at": "2026-08-09T10:20:00Z"}
    assert tl.judge_mine(issue, locks, "cam", "laptop", now)[0] == "this-session"
    assert tl.judge_mine(issue, locks, "cam", "tablet", now)[0] == "active-elsewhere"          # another session's fresh lock
    old_issue = {"number": 7, "updated_at": "2026-08-09T06:00:00Z"}
    old_locks = [dict(locks[0], created_at="2026-08-09T06:00:00Z")]
    assert tl.judge_mine(old_issue, old_locks, "cam", "tablet", now)[0] == "idle"              # > 2 h quiet -> resumable
    assert tl.judge_mine(issue, [], "cam", "tablet", now)[0] == "active-elsewhere"             # recent activity, no lock of ours
    # coord.yml wiring: per-login serialization of /next, session-tagged locks, verification, unlock markers
    cy = _wf("coord.yml")
    assert "format('next-{0}', github.event.comment.user.login)" in cy
    for needle in ("lock_line()", "first_holder()", "first_lock()", "tools/dev/coord.py locks", "<!-- unlock by=$WHO -->",
                   "your other session", "take-over", "yields #"):
        assert needle in cy, needle
    # verdict markers match by >=12-hex prefix of the head on both bash sides
    assert "sha=[0-9a-f]{12,40}" in _wf("automerge.yml") and "verdict_of()" in _wf("claude-review.yml")


def test_automerge_grep_captures_survive_no_match():
    """automerge.yml runs under `set -euo pipefail`: a `x=$(grep ... | ...)` capture whose pattern is
    absent exits 1 through pipefail and aborts the entire sweep (2026-08-09 outage). Every such capture
    must end in `|| true` (or the grep must sit in an if/&&/|| condition)."""
    am = _wf("automerge.yml")
    bad = [ln.strip() for ln in am.splitlines()
           if re.search(r"^\s*[A-Za-z_][A-Za-z0-9_]*=\$\(.*\bgrep\b", ln) and "|| true" not in ln and "|| echo" not in ln]
    assert not bad, "grep captures without a no-match guard:\n" + "\n".join(bad)


def test_board_triggers_stay_bounded():
    """#64: no workflow_run fan-out and no label/assignment triggers on the board (30 runs in 3 min on day one)."""
    on_block = _wf("board.yml").split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    keys = "\n".join(ln for ln in on_block.splitlines() if not ln.lstrip().startswith("#"))   # trigger keys, not the prose
    assert "workflow_run" not in keys and "labeled" not in keys and "assigned" not in keys
    assert "*/20" in keys and "workflow_dispatch" in keys
    for wf_name in ("automerge.yml", "techlead.yml", "worker.yml"):
        assert "gh workflow run board.yml" in _wf(wf_name), f"{wf_name} must refresh the board itself after changing state"


# ───────────────────────── classify + board ─────────────────────────

def test_classify_sections():
    m = tl.classify(snapshot(), CFG, NOW)
    assert [s["number"] for s in m["steers"]] == [54] and m["steers"][0]["triaged"] is False
    assert [e["number"] for e in m["progress"]] == [55, 6, 60]                     # assigned or worker-held; board/tracking excluded
    assert [e["number"] for e in m["next_up"]] == [5, 3, 7, 11, 24]                # P0 first, then P1 by age; #14/#37/#9 in review, #60 leased
    assert {e["number"] for e in m["waiting"]} == {16, 22}                          # gated; #23 is tracking -> not listed
    assert [e["number"] for e in m["others"]] == [52]                               # not ready, not gated: backlog remainder
    assert m["waiting_prs"] == [] and m["session_prs"] == []                        # reviewer-touching PR without a verdict: still in review (#88), nobody may merge yet
    h = m["health"]
    assert (h["ready_unassigned"], h["in_review"], h["steers_untriaged"], h["stuck_prs"], h["bot_prs_open"], h["session_merge"]) == (5, 4, 1, 1, 1, 0)
    assert h["paused"] is False and h["board_issue"] == 56
    assert any("untriaged steer" in w for w in h["warnings"]) and any("fix budget" in w for w in h["warnings"])
    labelled = snapshot()
    labelled["prs"][1]["labels"] = ["session-merge"]                                # once automerge offered it (verdict + green), the board flags it for a session
    m2 = tl.classify(labelled, CFG, NOW)
    assert [r["number"] for r in m2["session_prs"]] == [57] and any("waiting for ANY coding session" in w and "#57" in w for w in m2["health"]["warnings"])
    assert not any("below floor" in w for w in h["warnings"])                       # 5 >= floor 4


def test_classify_flags_pause_and_thin_queue():
    snap = snapshot(board_labels=("board", "tracking", "bots-paused"))
    snap["issues"] = [i for i in snap["issues"] if i["number"] not in (5, 3, 7)]    # queue drops to 2 (< floor 4)
    h = tl.classify(snap, CFG, NOW)["health"]
    assert h["paused"] is True and h["ready_unassigned"] == 2
    assert any("below floor" in w for w in h["warnings"]) and any("bots-paused" in w for w in h["warnings"])


def test_board_render_is_complete_marked_and_stable_across_renders():
    m = tl.classify(snapshot(), CFG, NOW)
    body = tl.render_board(m, CFG, "ckaragitz/tekton")
    assert body.startswith(tl.BOARD_BEGIN) and body.rstrip().endswith(tl.BOARD_END)
    for heading in ("## 🧭 Steers from humans", "## 🔨 In progress", "## 🔍 In review", "## ⏭️ Next up", "## 🧑 Waiting on a human", "## ✅ Done in the last 7 days", "## 🩺 Health"):
        assert heading in body, heading
    assert "| #54 |" in body and "independent verdict" in body and "rebase job dispatched" in body
    assert "0 for a session to merge" in body
    assert "#10-what-still-needs-a-human-and-why" in body                           # anchor exists in docs/process/AUTONOMY.md
    with open(os.path.join(ROOT, "docs", "process", "AUTONOMY.md"), encoding="utf-8") as fh:
        assert "## 10. What still needs a human, and why" in fh.read()
    # The board re-renders on every event: an unchanged repo an hour later must produce the same
    # body modulo the stamp line, or every render becomes an issue edit.
    later = tl.classify(snapshot(), CFG, NOW + dt.timedelta(hours=1))
    assert tl.strip_stamp(tl.render_board(later, CFG, "ckaragitz/tekton")) == tl.strip_stamp(body)
    assert "|" not in tl.md_escape("a|b\nc").replace("\\|", "")


def test_brief_lists_untriaged_steer_text_and_hygiene_findings():
    m = tl.classify(snapshot(), CFG, NOW)
    brief = tl.render_brief(m, CFG, "ckaragitz/tekton")
    assert "### #54 — Steer: coding sessions are the tech leads" in brief and "> Hi ..." in brief
    assert "#52 has no priority label" in brief and "#6 has no area:* label" not in brief   # #6 has area:perf
    assert "at most 5 new issues" in brief


# ───────────────────────── worker pick ─────────────────────────

def test_pick_prefers_retry_then_queue_head_with_auto_and_skips_hot_files():
    snap = snapshot()
    job = tl.pick(snap, CFG, runs_today=0)
    assert job["go"] and job["issue"] == 7 and job["mode"] == "implement" and job["max_turns"] == 120   # #5 (P0) is hot-file, #3 lacks auto
    assert job["branch"] == "bot/7-validator-0x0f3f-footer-blob-rule"
    # a re-queued issue whose stuck PR is still open: continue on that PR's branch, ahead of everything
    snap["issues"] = [dict(i, labels=i["labels"] + [{"name": "retry"}]) if i["number"] == 9 else i for i in snap["issues"]]
    job = tl.pick(snap, CFG, runs_today=0)
    assert (job["issue"], job["mode"], job["branch"], job["pr"]) == (9, "continue", "bot/9-famgen-determinism", 58)
    # a re-queued issue whose PR was closed: the sweep recorded the branch in the body
    body = "## DONE\n- x\n\n<!-- retry-branch: Ckaragitz12/61-thing -->\n"
    snap2 = snapshot(extra_issues=[I(61, "re-queued human work", ["P0", "ready", "retry", "area:engine"], body=body)])
    job = tl.pick(snap2, CFG, runs_today=0)
    assert (job["issue"], job["mode"], job["branch"], job["pr"]) == (61, "continue", "Ckaragitz12/61-thing", 0)


def test_pick_respects_pause_cap_wip_config_and_dispatch():
    assert tl.pick(snapshot(board_labels=("board", "bots-paused")), CFG)["reason"].startswith("`bots-paused`")
    assert "daily cap" in tl.pick(snapshot(), CFG, runs_today=4)["reason"]
    two_bots = snapshot()["prs"] + [_pr(n=80, user="claude[bot]", head_ref="bot/3-x", body="Closes #3"),
                                    _pr(n=81, user="claude[bot]", head_ref="bot/24-y", body="Closes #24")]
    assert "WIP limit" in tl.pick(snapshot(prs=two_bots), CFG)["reason"]           # stuck #58 does not count, 80+81 do
    off = tl.deep_merge(CFG, {"worker": {"enabled": False}})
    assert "disabled" in tl.pick(snapshot(), off)["reason"]
    anyready = tl.deep_merge(CFG, {"worker": {"eligible": "any-ready", "allow_hot_file": True}})
    assert tl.pick(snapshot(), anyready)["issue"] == 5                              # now the P0 hot-file head is fair game
    forced = tl.pick(snapshot(), CFG, runs_today=9, forced_issue=3)
    assert forced["go"] and forced["issue"] == 3 and forced["reason"] == "dispatched for this issue"
    assert tl.pick(snapshot(), CFG, forced_issue=999)["go"] is False
    no_auto = snapshot()
    no_auto["issues"] = [dict(i, labels=[l for l in i["labels"] if l["name"] != "auto"]) for i in no_auto["issues"]]
    r = tl.pick(no_auto, CFG)
    assert r["go"] is False and "nothing eligible" in r["reason"]


# ───────────────────────── hygiene sweep ─────────────────────────

def test_sweep_requeues_stuck_after_a_quiet_day_frees_dead_leases_and_ages_out_drafts():
    acts = tl.plan_sweep(snapshot(), CFG, NOW)
    ops = {(a["op"], a.get("issue") or a.get("pr")) for a in acts}
    assert ("requeue", 9) in ops                     # PR #58: bot-stuck, head 29 h old >= 24 h
    assert ("release-lease", 60) in ops              # bot-working, no PR, untouched 4.5 h >= 3 h
    assert not any(a["op"] in ("nudge-stale", "close-stale") for a in acts)   # draft #40 is only ~29 h old
    rq = next(a for a in acts if a["op"] == "requeue")
    assert rq["branch"] == "bot/9-famgen-determinism" and rq["key"] == "requeue-58-def5678" and rq["pr_comments"]
    fresh = snapshot()
    fresh["prs"][2]["head_date"] = "2026-08-09T02:00:00Z"          # not yet a day quiet -> leave it to the ladder
    assert not any(a["op"] == "requeue" for a in tl.plan_sweep(fresh, CFG, NOW))
    old = snapshot()
    old["prs"][0]["head_date"] = "2026-08-03T00:00:00Z"            # 6 days, but green + approved -> automerge's, no nudge
    assert not any(a["op"] == "nudge-stale" for a in tl.plan_sweep(old, CFG, NOW))
    old["prs"][0]["review"]["verdict"] = "changes"
    assert any(a["op"] == "nudge-stale" and a["pr"] == 40 for a in tl.plan_sweep(old, CFG, NOW))
    old["prs"][0]["head_date"] = "2026-07-20T00:00:00Z"            # 20 days -> close, issue #37 back to the queue
    close = [a for a in tl.plan_sweep(old, CFG, NOW) if a["op"] == "close-stale"]
    assert close and close[0]["closing"] == [37]
    old["prs"][0]["labels"] = ["wip"]                                # wip exempts a draft
    assert not any(a["op"] == "close-stale" for a in tl.plan_sweep(old, CFG, NOW))


# ───────────────────────── steer log ─────────────────────────

def test_steer_issue_is_verbatim_attributed_and_titled_by_first_sentence():
    spec = tl.steer_issue("Windows matters more than new features this month. Also stop touching 2023.\nThanks",
                          by="@Ckaragitz12", source="comment on #40", logged_by="github-actions", when=NOW)
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


def test_client_builds_repo_relative_urls_pages_and_comments_once():
    gh = FakeGH({
        ("GET", "/repos/o/r/issues?state=open"): (200, [{"number": 1}], '<https://api.github.com/repos/o/r/issues?state=open&page=2>; rel="next"'),
        ("GET", "/repos/o/r/issues?state=open&page=2"): (200, [{"number": 2}], ""),
        ("GET", "/repos/o/r/issues/5/comments"): (200, [{"body": "hello <!-- techlead:k1 -->"}], ""),
        ("POST", "/repos/o/r/issues/5/comments"): (201, {"id": 9}, ""),
        ("DELETE", "/labels/"): (404, {"message": "Label does not exist"}, ""),
        ("DELETE", "/repos/o/r/issues/5/assignees"): (200, {}, ""),
    })
    assert [i["number"] for i in gh.paged("issues", state="open")] == [1, 2]
    assert gh.comment_once(5, "k1", "again") is False                       # marker present -> no second comment
    assert gh.comment_once(5, "k2", "new") is True
    assert gh.comment_once(5, "k1", "known", existing=["x <!-- techlead:k1 -->"]) is False   # pre-fetched bodies, no GET
    posted = [b for m, u, b in gh.sent if m == "POST"]
    assert posted and posted[-1]["body"].endswith("<!-- techlead:k2 -->")
    gh.remove_label(5, "nope")                                                # 404 on label removal is fine
    gh.unassign(5, ["a", "b"])
    assert gh.sent[-1] == ("DELETE", "https://api.github.com/repos/o/r/issues/5/assignees", {"assignees": ["a", "b"]})
    gh.unassign(5, [])                                                        # nothing to do -> no call
    assert gh.sent[-1][0] == "DELETE" and gh.sent[-1][1].endswith("/assignees")
    try:
        gh.get("nothing/here")
    except tl.GitHubError as e:
        assert e.status == 404
    else:
        raise AssertionError("expected GitHubError")


def test_upsert_board_creates_when_missing_and_skips_identical_rerender():
    log, created = [], {}

    def create(url, body):
        created.update(body)
        return 201, {"number": 77, "node_id": "N77", "body": body["body"]}, ""
    gh = FakeGH({("POST", "/repos/o/r/issues"): create, ("POST", "/graphql"): (200, {"data": {"repository": {"pinnedIssues": {"nodes": []}}}}, "")})
    n = tl.upsert_board(gh, [], CFG, "BODY v1\n", log=log.append)
    assert n == 77 and created["labels"] == ["board", "tracking"] and any("created #77" in l for l in log)
    assert any(u.endswith("/graphql") and b and "pinIssue" in b["query"] for _, u, b in gh.sent)     # pinned after creation
    gh2 = FakeGH({("POST", "/graphql"): (200, {"data": {"repository": {"pinnedIssues": {"nodes": [{"issue": {"number": 77}}]}}}}, "")})
    body_a = "_Rendered 08-09 06:00 UTC by `board` …_\nrest\n"
    body_b = "_Rendered 08-09 07:00 UTC by `board` …_\nrest\n"
    log2 = []
    tl.upsert_board(gh2, [{"number": 77, "labels": [{"name": "board"}], "body": body_a, "node_id": "N77"}], CFG, body_b, log=log2.append)
    assert not any(m == "PATCH" for m, _, _ in gh2.sent) and any("unchanged" in l for l in log2)


# ───────────────────────── CLI surface ─────────────────────────

def test_cli_hello_is_offline_safe_and_fast():
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    env["PATH"] = "/nonexistent"                                            # no gh CLI either
    r = subprocess.run([sys.executable, PATH, "--repo", "o/r", "hello"], capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0 and "TECH LEAD" in r.stdout and "you build" in r.stdout and "offline" in r.stdout


def test_cli_steer_dry_run_and_config():
    r = subprocess.run([sys.executable, PATH, "--repo", "o/r", "steer", "Ship the Windows fix first.", "--by", "ck", "--dry-run"],
                       capture_output=True, text=True, timeout=30)
    spec = json.loads(r.stdout)
    assert r.returncode == 0 and spec["title"] == "Steer: Ship the Windows fix first." and spec["labels"] == ["steer"]
    r = subprocess.run([sys.executable, PATH, "config", "worker.max_turns"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and r.stdout.strip() == "120"
