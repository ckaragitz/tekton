# Tech-lead TICK — the standalone prompt every scheduled fire follows (steer #108 / #302, docs/process/AUTONOMY.md §12c)

Two routines run this file (their stored prompts are two-line stubs that fetch `origin/main` and read THIS file from it, so edits ship by PR and a resumed conversation on some branch still runs main's text):
the **hourly wake** into the persistent tech-lead session (anchored at its creation minute) and the
**watchdog** — a ONE-SHOT routine that fires a fresh session (`create_new_session_on_fire`) only if no acting
tick pushed its `run_once_at` forward in time. Every acting tick pushes it to now + `lease.minutes`; so while a
loop is alive the watchdog never fires, and when the loop dies it fires exactly `lease.minutes` after the last
tick and carries on from GitHub state alone (that is why the wave ledger and the same-tick evidence rules exist).
The LEASE (step 0) is the visible register of who is acting and arbitrates the one case the watchdog cannot: a
session that comes back after it was presumed dead. CLAUDE.md auto-loads and its §1 hard rules bind you. There is
NO GitHub-hosted compute: GitHub check runs mean nothing; CI, review and merges are done here with same-tick
evidence. Cloud sessions have no `gh`/token — use the GitHub MCP tools; `tools/dev/techlead.py` has token-less
forms (`--from-file … --dry-run`) for everything below. Prerequisites a fire checks once: the repo is cloned and
`.venv` exists (the environment's setup script runs `scripts/cloud-setup.sh`; run it yourself if `.venv/bin/python` is
missing — `tools/dev/session_ci.sh` needs it), and the GitHub MCP tools answer for ckaragitz/tekton.

## 0. Lease + watchdog — one command decides; EVERY outcome re-arms the watchdog before the turn can end
Your session id is `$CLAUDE_CODE_REMOTE_SESSION_ID` (a `cse_…` value; the tool normalises it to the `session_…` spelling
every other surface uses — never invent a name like "techlead": mutual exclusion depends on real, distinct ids).
1. `issue_read` (get) the lease issue — number `lease.issue` in `.github/autonomy.json` (#410) — and save the tool
   result to a FILE with the Write tool (e.g. `out/lease.json`). Never pass it through `echo`/an unquoted heredoc: the
   body is data, and a shell that swallows part of it would make you misjudge the lease.
2. `python3 tools/dev/techlead.py lease renew --me "$CLAUDE_CODE_REMOTE_SESSION_ID" --from-file out/lease.json --dry-run`
   prints on stderr `HOLD|TAKE|STANDBY|DAMAGED: …` and **`ARM_WATCHDOG_AT=<UTC>`**, and on stdout (hold/take only)
   the new body.
3. **First, whatever the verdict:** `list_triggers` → the routine named **"tekton tech-lead watchdog"** →
   `update_trigger(<id>, run_once_at=<the ARM_WATCHDOG_AT value, verbatim>, enabled=true)` (setting `run_once_at`
   re-arms a fired one-shot; if you ARE the watchdog's fresh session this schedules your successor). If no such
   routine exists (renamed/deleted): `create_trigger(name="tekton tech-lead watchdog", create_new_session_on_fire=true,
   run_once_at=<that value>, prompt=<the two-line stub: "tekton tech-lead watchdog fire — clone/enter ckaragitz/tekton,
   `git fetch origin main`, read `git show origin/main:.github/prompts/tick.md` and follow it exactly">)` and note that on
   the lease issue. If you could not even read the lease (no GitHub access on this surface): still do this step with
   `now + lease.minutes`, then end the turn.
4. Then act on the verdict:
   - **exit 5 `STANDBY`** (another live loop holds it) → nothing else; one line "standby: held by … until …"; end the turn.
   - **exit 6 `DAMAGED`** (the issue mentions a lease but no marker line parses / impossible timestamp) → re-read once
     (step 1); still damaged → do NOT take: post one line on the lease issue asking the holder/human to repair it, end.
   - **`HOLD`** (yours, even if it lapsed) or **`TAKE`** (none / released / another holder's lease expired — that holder
     is gone) → write stdout with MCP `issue_write` (method `update`, that issue, `body`). After a **TAKE**, `issue_read`
     once more and stand down if the marker line now names someone else (two takers in one minute: the later reader
     yields); then post one line on the board issue (#56): "took the loop lease from `<old holder>` (expired `<until>`)".
5. Long ticks: redo steps 1–4 with a FRESH `issue_read` (never the copy saved at tick start) right before every merge
   in §2, every `create_session` in §3 and every issue you file in §4, whenever your last renew is older than
   `lease.minutes` / 2.
6. End of pass: the persistent session just stops (its lease keeps running; the hourly wake renews it). A
   watchdog-fired session hands the lease back — `lease renew --release --from-file <fresh read> --dry-run` →
   `issue_write` — so a persistent session that is alive after all reclaims at its next wake; if none is, the watchdog
   you armed in step 3 fires at `ARM_WATCHDOG_AT` and its session TAKEs the released lease.

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
reviewer said approve/nits for the exact head you re-read (`git ls-remote`) just before merging. Markers from
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
landed — then ≤ 4 lines. A fresh session ends its turn when the pass is done (step 0.6 released the lease and step 0.3
already scheduled its successor).
