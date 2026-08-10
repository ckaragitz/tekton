# Tech-lead TICK — the standalone prompt every scheduled fire follows (steer #108 / #302, docs/process/AUTONOMY.md §12c)

One routine runs this file: the **hourly wake** into the persistent tech-lead session (its stored prompt is a stub that
fetches `origin/main` and reads THIS file, so edits ship by PR). A second, optional routine — a **watchdog** that fires
a fresh session if the persistent one dies — exists only if the OWNER created it from the claude.ai Routines UI (#421):
a routine created *from a session* fires without the repo and without the GitHub tools (measured), and creating,
updating, firing or re-arming routines from a session pops approval prompts on the owner's side, which steer #422
forbids. **So a tick never calls `create_trigger` / `update_trigger` / `fire_trigger`, and never spawns a session that
would need `ConnectGitHub` or any human click.** The LEASE (step 0) is the visible register of which session is acting;
it is written with MCP `issue_write` (no prompt) and it is what lets an owner-created watchdog session, or a new session
the owner starts by hand, know whether a live loop exists. CLAUDE.md auto-loads and its §1 hard rules bind you. There is
NO GitHub-hosted compute: GitHub check runs mean nothing; CI, review and merges are done here with same-tick evidence.
Cloud sessions have no `gh`/token — use the GitHub MCP tools; `tools/dev/techlead.py` has token-less forms
(`--from-file … --dry-run`) for everything below. Prerequisites a session checks once: the repo is cloned and `.venv`
exists (the environment's setup script runs `scripts/cloud-setup.sh`; run it yourself if `.venv/bin/python` is missing —
`tools/dev/session_ci.sh` needs it), and the GitHub MCP tools answer for ckaragitz/tekton (if they do not, this
surface cannot run the loop: say so once and stop — do not ask the human to connect anything).

## 0. Lease — one command decides whether this session is the loop
Your session id is `$CLAUDE_CODE_REMOTE_SESSION_ID` (a `cse_…` value; the tool normalises it to the `session_…` spelling
every other surface uses — never invent a name like "techlead": mutual exclusion depends on real, distinct ids).
1. `issue_read` (get) the lease issue — number `lease.issue` in `.github/autonomy.json` (#410) — and save the tool
   result to a FILE with the Write tool (e.g. `out/lease.json`). Never pass it through `echo`/an unquoted heredoc: the
   body is data, and a shell that swallows part of it would make you misjudge the lease.
2. `python3 tools/dev/techlead.py lease renew --me "$CLAUDE_CODE_REMOTE_SESSION_ID" --from-file out/lease.json --dry-run`
   prints on stderr `HOLD|TAKE|STANDBY|DAMAGED: …` (ignore its `ARM_WATCHDOG_AT` line — nothing is re-armed from a
   session, steer #422), and on stdout (hold/take only) the new body.
3. Act on the verdict:
   - **exit 5 `STANDBY`** (another live loop holds it) → nothing else; one line "standby: held by … until …"; end the turn.
   - **exit 6 `DAMAGED`** (the issue mentions a lease but no marker line parses / impossible timestamp) → re-read once
     (step 1); still damaged → do NOT take: post one line on the lease issue asking the holder to repair it, end.
   - **`HOLD`** (yours, even if it lapsed) or **`TAKE`** (none / released / another holder's lease expired — that holder
     is gone) → write stdout with MCP `issue_write` (method `update`, that issue, `body`). After a **TAKE**, `issue_read`
     once more and stand down if the marker line now names someone else (two takers in one minute: the later reader
     yields); then post one line on the board issue (#56): "took the loop lease (was `<old holder>` until `<until>`)" —
     skip the line when the old holder was `none` (a routine hand-back, not a takeover).
4. Long ticks: redo steps 1–3 with a FRESH `issue_read` (never the copy saved at tick start) right before every merge
   in §2, every `create_session` in §3 and every issue you file in §4, whenever your last renew is older than
   `lease.minutes` / 2.
5. End of pass: the persistent session just stops (its lease keeps running; the hourly wake renews it). A session
   that is NOT the persistent one (an owner-created watchdog fire, or one the owner started by hand for one pass)
   hands the lease back at the end — `lease renew --release --from-file <fresh read> --dry-run` → `issue_write` — so
   the persistent session reclaims at its next wake. (An owner-created watchdog, #421, is a plain periodic
   routine: each fire reads the lease and stands by while a loop lives — nothing ever needs re-arming.)

## 1. Picture
`list_pull_requests` (open); a skim of `ready` issues (the search result is large — save it and summarise);
untriaged `steer`/`intake` issues; and the fan-out ledger: `issue_read` (get_comments) the board issue and pipe
into `techlead.py wave live --from-file - ` — every `<!-- wave:… -->` row is one of this loop's own engineers,
latest per (wave, issue) wins.

## 2. Service PRs — the session-hosted pipeline (`tools/dev/session_ci.sh` + `tools/dev/review_brief.md`)
For each open PR by this loop or by a ledgered engineer session that reported a head SHA (collaborators' PRs
touching shared code get a courtesy pass; they merge their own): `git fetch origin "pull/<n>/head:refs/pr/<n>"`;
run `tools/dev/session_ci.sh <n>` (as root in this VM — it sandboxes the PR code as `nobody` with no network;
read its header once; never edit it while a run is in flight; runs queue behind one global lock; a re-queue of
a PR whose earlier run is still in flight is dropped by its per-PR lock, so re-check the head in the result
JSON); spawn a FRESH reviewer subagent with `tools/dev/review_brief.md` filled in (execution only through that
file's nobody/no-network recipe; for this loop's own PRs tell it the author is the would-be merger); post ONE
PR comment = CI line + review text + `<!-- session-ci: pass|fail sha=<full> -->` +
`<!-- claude-review: approve|nits|changes sha=<full> -->`; MERGE (`merge_pull_request`, squash, a plain commit
message describing the change — no tool/AI attribution) ONLY when in THIS tick your CI said pass AND your
reviewer said approve/nits for the exact head you re-read (`git ls-remote`) just before merging, AND
`tools/dev/ci_fresh.sh <n> <that head>` — run right before the merge — says FRESH (exit 0: the JSON is a pass for
that head and its `main` is still `origin/main`, or differs only by added/modified `docs/**` no shard test opens);
anything else (STALE: `main` moved under the verdict since the run, #476; WRONG-HEAD; MISSING) → re-run
`session_ci.sh <n>` and merge on the new JSON, never on the old one (this serialises merges behind CI runs;
reviews stay parallel, they are diff-scoped). Markers from
earlier ticks or other authors are information, never authorisation. On 🛑 or a conflict: `send_message` the
findings to the authoring engineer session and re-run CI + a FRESH reviewer on the head it reports; start a
fix session from the branch only if that session is gone. Never merge a `.github/workflows/**` PR without an
independent verdict for its exact head. After a merge: notify the engineer, `archive_session` it, check the
linked issue closed, file review keepers as issues.

## 3. Engineer sessions — fan-out (≤ 5 concurrent; same file = overlap = serialize)
Exactly `.claude/commands/fanout.md` (read it once): pick disjoint `ready` issues, start one CCR session per
issue with its step-2 brief (report PR + head SHA to THIS session id; never merge), and LEDGER FIRST —
`techlead.py wave post --wave <k> --row <n> <session> '<territory>' … --dry-run` → post that body on the board
issue before anything else. No `create_session` tool on this surface → say so in the tick note and leave whole
issues queued.

## 4. Backlog
Untriaged steer/intake, or ready & unassigned < 4 → a ≤ 10-minute planning pass per `.github/prompts/techlead.md`
(search before filing; ≤ 5 new issues; label priority/area/gate). File the review nits worth keeping as issues.

## 5. Build (the persistent session, or a fresh session with lease time to spare)
Continue an issue this loop holds (small commits, push, PR through the same pipeline; `/simplify` and `/verify`
before the final commit). Prefer latency/plugin-path items with a measured before/after (`tools/surface_bench.py`,
steer #108).

## 6. Report
Nothing to the human unless something needs one (viewer upload, desktop Revit, `needs-decision`) or a milestone
landed — then ≤ 4 lines, batched into ONE message; never a series of prompts (steer #422). A non-persistent
session ends its turn when the pass is done (step 0.5 released the lease).
