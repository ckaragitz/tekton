# tekton — working guide for coding sessions

You are in **tekton**: a pure-Python interoperability engine that reads,
creates, edits, validates, and converts Autodesk Revit `.rvt` / `.rfa`
containers **without a Revit install, an Autodesk seat, or APS**. Revit is
the last-mile *deliverable* format — a licensed engineer opens our output
for QA. Read this file fully before touching anything; then read
`KNOWLEDGE.md` (institutional memory) and `TRACKER.md` (the curated roadmap).

**You are a tech lead here, not a ticket-taker** (§4): the coding sessions own
the task list, requirements and stories and derive them from the program goals;
the humans steer, and every steer is logged before it is acted on. The two files
you plan from are imported right here so they are always in context:

@docs/PROGRAM.md
@docs/STEERING.md

---

## 1. Hard rules (non-negotiable — they exist because breaking each one cost days)

1. **The deliverable rule.** Status gates (`PROOF-ONLY`, honesty stamps,
   open-bug labels) are **labels, never refusal logic**. Every route always
   *delivers* the built `.rvt`/`.rfa`, stamped, with caveats *after*
   delivery. Never withhold output; never silently swap an IFC for a
   requested `.rvt`.
2. **Never read any Autodesk installation directory** — `ProgramData/Autodesk`,
   `Program Files/Autodesk`, `RVT 20xx/Family Templates`, `/Applications/Autodesk`.
   A runtime tripwire enforces this on the front door. The product's whole
   point is *not needing* Revit.
3. **Zero donor bytes in anything shipped.** We *mine* laws from Autodesk
   files (samples, templates) and *author our own* equivalents; we never
   copy their content into product output. Sample-derived material lives
   only in quarantined, git-ignored dirs (`samples/`, `vendor/`,
   `extracted/`) and dev-only probes under `experiments/` (stamped
   `PROOF-ONLY`). `tools/sync_plugin.py`'s deny-audit blocks it from the
   plugin bundle.
4. **Autodesk's reader is the arbiter, not our validator.** "Validator green"
   is *not* acceptance. A file is *certified* only when
   `viewer.autodesk.com` (or desktop Revit) loads it, and the verdict is
   recorded in `docs/coverage/viewer-certified.json`. Every viewer round
   goes through `tools/probe_batch.py`: **a certified base + a
   byte-identical control per batch**; a base must itself be certified
   *before* you build on it; a failed control voids the round.
5. **The reduction law** (`src/rvt/reduce_law.py`): when removing content, a
   referrer of removed content is deleted *with* it or left
   *byte-identical* — never "neutralised". `assert_edit_free` gates every
   reduction.
6. **Keep this repo private.** It carries counsel-review material (see
   `docs/product/COUNSEL-BRIEF.md`: author strings C1, the per-release
   schema/ESSchema corpora C4, footer token C5, trademark). Nothing here
   goes to a public remote. Leave `PRODUCT_AUTHOR_PLACEHOLDER = "rvt-writer"`
   in `src/rvt/identity.py` alone; never echo "Autodesk Revit" or a
   template's identity as *our* author string.
7. **No Autodesk APS / Design Automation.** Decided twice by the owner; do
   not re-propose it. The writer is our own native binary writer.
8. **If an automated task/charter is declined by a policy layer, surface it
   to the owner verbatim — never reword to get around it.**

## 2. Setup and the commands you'll actually use

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e .          # package: rvt (src layout); only declared dep is olefile
uv pip install --python .venv/bin/python pytest numpy                   # test/geometry extras are NOT declared in pyproject
uv pip install --python .venv/bin/python ifcopenshell                   # OPTIONAL: IFC *authoring* only; IFC reading has a stdlib fallback (steplite)
.venv/bin/python -m pytest tests/test_frontdoor.py -q                   # ALWAYS run python from repo root via .venv/bin/python
```
(Plain `python3.11 -m venv .venv && .venv/bin/pip install -e . pytest numpy` also works; the checked-in `.venv` on the owner's machine is uv-built and has no `pip` inside.)

- **Tests:** the full suite is ~1,700 tests / ~25 min (last canonical:
  1697 passed / 7 failed / 2 skipped); **do not run it casually or
  concurrently** (`docs/inbox/SUITE-COORDINATION.md` — one canonical run at
  a time; contributors run their *stream-local* files:
  `.venv/bin/python -m pytest tests/test_<yours>.py -q`). `RVT_SKIP_LARGE=1`
  skips `@slow` large-file cases. Many tests self-skip when `samples/` or
  built ladders are absent — expected in a fresh clone. After any engine or
  tools change also run `tests/test_plugin_sync.py` + `tools/sync_plugin.py --check`.
- **Validate every output you produce:**
  `.venv/bin/python tools/rvt_validate.py out.rvt --json out.validation.json`
  — 0 errors required (necessary, *not* sufficient — rule 4).
- **The front door** (one entrypoint, three inputs — exactly one of
  `--prompt` / `--ifc` / `--rvt --edit`):
  ```bash
  .venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/demo --json
  .venv/bin/python tools/frontdoor.py author --ifc room.ifc --target-version 2025 --out out/r25
  .venv/bin/python tools/frontdoor.py author --rvt project.rvt --edit "move DP-1 to 3,1,4.66" --out out/e
  ```
- **The permutation router** (any of {prompt, ifc, rvt, rfa, spec} in → {rvt, rfa, ifc} out):
  `.venv/bin/python tools/route.py matrix` (the honest capability table) /
  `route explain ...` / `route run ...`. Cells are declared in
  `src/rvt/frontdoor/matrix.py`; `verify_evidence()` fails the suite if a
  "works" claim loses its evidence.
- **Plugin build:** `.venv/bin/python tools/sync_plugin.py` mirrors
  `src/` + skills into `plugin/`, runs validation + the deny-audit, and
  rebuilds `tekton-plugin.zip` at the repo root (git-ignored; regenerate,
  don't commit). `--check` = report drift only, exit 1 on any. **Run it
  after every change under `src/` or `skills/`** — the plugin ships source
  copies.
- **Viewer rounds:** `tools/probe_batch.py {check,stage,resolve,verdicts,retro}`
  gates a batch (certified base + byte-identical control) and stages it
  into `experiments/acceptance/`; **streams STAGE only and stop at READY —
  the orchestrating human/session uploads and records verdicts.**
  `tools/serve_acceptance.py [PORT]` serves that dir on 127.0.0.1:8765 for
  the browser upload loop.
- **Provenance before anything ships:** `.venv/bin/python tools/provenance.py FILE.rvt --baseline all --streams --json out.json`;
  families: `.venv/bin/python tools/make_family.py provenance PATH.rfa`.
- **Target version is a first-class input:** `--target-version {2026,2025,2024}`.
  Revit cannot open a *newer* file — always ask/pass the recipient's
  release; never present a 2026 file as openable in 2025.
- **Env vars:** `TEKTON_ROOT` (repo-root override), `RVT_PLUGIN_ROOT`
  (plugin bundle root for the standalone path), `RVT_GENESIS_BASE`
  (explicit base override), `RVT_STEPLITE_FORCE=1` (force the pure-Python
  IFC reader), `RVT_SEG_CACHE=<dir>` (cache slow segment builds),
  `RVT_SKIP_LARGE=1` (tests).

### Working from a Claude Code cloud session (claude.ai/code)

Cloud sessions clone this repo into a fresh VM, so they behave like a fresh
clone: no `samples/`, no viewer login → pick `ready` issues. Point the cloud
environment's **Setup script** at `bash scripts/cloud-setup.sh` (creates
`.venv`, installs the engine + test extras, sets `pull.rebase`, checks plugin
drift + portable paths). This file, its two `@` imports, and `.claude/`
(a SessionStart banner with live queue counts, and the project commands
`/steer`, `/techlead`, `/board`, `/fanout`) load automatically. Cloud sessions have no
`gh`: use the GitHub MCP tools for the same moves (§4). Work on a branch,
push, and open the PR from the session UI (or `gh pr create --draft`) exactly
as in section 4 — and if the session ends before the PR is finished, the
repo's bots finish or re-queue it; nothing depends on the session staying up.

## 3. Map

- `src/rvt/` — the engine. Container/codec layers (CFB → framed gzip →
  records), `schema*` (every file carries its own class schema in
  `Formats/Latest`; decode against *it*), `validate.py` (layered validator,
  corpus-law rules E1–E3), `versions/` (release detection from
  `BasicFileInfo`, by-name framing ordinals, `records32` for the 2023
  32-bit-id era, `KNOWN_RELEASES`), `genesis/` (base composition +
  per-release port layers), `frontdoor/` (`build`, `standalone`,
  `release_ctx`, `router`, `matrix`, `prompt_intent`, `ifc_out`),
  `famgen/` (family generation: `factory`, `loader`, `famdoc_adoc`,
  `birthright`), `famload.py` (four-registry family loading),
  `mutate`/`manipulate` (create/edit/delete), `ifc/` (`intent` resolver,
  `steplite` — stdlib-only IFC reader, no ifcopenshell needed), `convert/`
  (rvt→ifc, extract/edit family, add_to_project, merge_ifc), `reduce_law.py`.
- `tools/` — CLIs and campaign drivers (`frontdoor.py`, `route.py`,
  `sync_plugin.py`, `probe_batch.py`, `genesis_*.py` per release,
  forensic instruments like `terminal_diff.py`, `fifth_surface.py`).
- `plugin/` — the distributable: `skills/` (`tekton-author`, `tekton-edit`,
  `tekton-inspect`, `tekton-ifc`, `tekton-native`, `_shared/tekton_env.py`
  = zero-pip bootstrap + one-call `go` dispatch), `commands/`, `agents/`,
  `assets/genesis/` (the certified composed bases G_ABPD /_2025 /_2024),
  `assets/schema_cache/`, `lib/` (mirrored source). Edit **sources**
  (`src/`, `skills/`, `tools/`), never `plugin/lib/`, `plugin/skills/*/scripts/`,
  or `plugin/assets/` directly — sync overwrites them. Plugin gotchas that
  each cost a failed upload once: the manifest lives at
  `plugin/.claude-plugin/plugin.json` (+ `marketplace.json`; the root
  `plugin/marketplace.json` is a derived byte-identical copy); `SKILL.md`
  frontmatter is exactly `{name, description}`, `name` == folder name,
  description ≤ 1024 chars with **no `<`/`>`**; every plugin-relative path a
  skill/command references must exist; the zip has plugin contents at the
  archive root. `plugin/scripts/validate_plugin.py` checks all of this.
- `docs/inbox/` — one record per workstream (see §4). `docs/product/` —
  user-facing truth (`PERMUTATION-MATRIX.md`, `HONEST-STATUS`,
  `SURFACE-PLAYBOOK.md`, `MCP-PATH.md`, `COUNSEL-BRIEF.md`).
  `docs/writer/` — format facts per release. `docs/coverage/viewer-certified.json`
  — the certification ledger. `docs/inbox/genesis-audit.md` — the running
  verdict log (`## ORCHESTRATOR VERDICTS #N`).
- Git-ignored on purpose: `samples/ vendor/ extracted/` (third-party),
  `experiments/**/*.rvt|rfa` (5+ GB of probes), caches, zips.

## 3b. The plugin is the product — and this is the primary repo for iterating on it

What is being built (and eventually sold) is the **plugin + skill
architecture** under `plugin/` (shipped as `tekton-plugin.zip`), backed by
the engine in `src/rvt/`. **You are expected to work on the plugin code
here** — skills, commands, agents, the bootstrap, the manifest, plugin
docs — just as much as on the engine. The only thing to know is which
paths are hand-authored (edit freely) and which are generated mirrors
that `tools/sync_plugin.py` overwrites:

| Edit here (source of truth) | Generated — don't hand-edit (regenerate with `tools/sync_plugin.py`) |
|---|---|
| `plugin/skills/{tekton-author,tekton-edit,tekton-inspect,tekton-native}/SKILL.md` + their `references/` | `plugin/skills/*/scripts/*.py` **except** `_bootstrap.py` (copies of `tools/*.py`) |
| `plugin/skills/_shared/tekton_env.py`, each skill's `scripts/_bootstrap.py` shim | `plugin/skills/tekton-ifc/**` (mirror of repo-root `skills/tekton-ifc/`) — edit the root copy |
| `plugin/commands/*.md`, `plugin/agents/*.md` | `plugin/lib/src/rvt/**` (mirror of `src/rvt/`), `plugin/lib/tools/*` |
| `plugin/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` | `plugin/marketplace.json` (byte-identical derived copy) |
| `plugin/README.md`, `plugin/docs/**`, `plugin/scripts/validate_plugin.py` | `plugin/assets/**` (pinned genesis bases, schema caches), `plugin/skills/*/examples/*` (copied from `spec/`, `inputs/`, `usecases/`) |
| engine: `src/rvt/**`, CLIs: `tools/*.py`, IFC skill: `skills/tekton-ifc/**` | `tekton-plugin.zip` (git-ignored build artifact) |

Rule of thumb: if `tools/sync_plugin.py --check` reports drift right after
your edit, you edited a mirror — move the change to its source.
Engine behaviour a skill needs → change `src/rvt/` or `tools/`, then sync;
skill wording/flow/UX → change the `SKILL.md` / `_shared` / commands
directly under `plugin/`.

**Two hygiene notes so a dev session doesn't confuse itself with an
end-user session:** the repo intentionally has **no `.claude/skills/`** (the
product skills aren't auto-loaded into the session that is editing them —
`.claude/` holds only the *process* pieces: the SessionStart banner and the
`/steer` `/techlead` `/board` `/fanout` commands, none of which are product
skills),
and interactive dogfooding of the skills is best done in a *separate*
scratch session with the built plugin loaded (`claude --plugin-dir
/path/to/tekton/plugin` or the installed zip) — so "the skill I'm editing"
and "the skill I'm running" never blur. That's a recommendation for
clarity, not a ban.

- **Testing the product (as a user would), every time you touch `src/`,
  `tools/`, `skills/`, or `plugin/`:**
  ```bash
  .venv/bin/python tools/sync_plugin.py                    # build: mirror sources -> plugin/, deny-audit, validate, re-zip
  .venv/bin/python plugin/scripts/validate_plugin.py       # structural checks (manifest, frontmatter, referenced paths)
  .venv/bin/python -m pytest tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py -q
  # run it exactly like a skill session on a bare surface (unzipped plugin, no repo on the path):
  .venv/bin/python tools/surface_bench.py --zip tekton-plugin.zip --json out/bench.json   # cowork-VM / stateless / local simulations, wall time + call counts
  # or by hand: unzip tekton-plugin.zip to a temp dir, then from that dir:
  python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/j1 --json
  ```
  The `go` verb is the one-call dispatch a real skill session uses
  (preflight + job + one JSON result); if it isn't `READY` from a bare
  unzip with system Python, the product is broken regardless of what the
  repo tests say.
- A PR that changes engine or skill behaviour states in its record which of
  the above ran and their results (the PR template has the checkbox).

## 4. How work is done here (process) — multiple humans, multiple sessions

Several people work here at once, each driving one or more coding
sessions that start fresh at random times on laptops that get switched off.
Coordination is **GitHub Issues + trunk-based git**, with this repo's record
conventions riding on top; the full operating system — roles, board, bots,
labels, what still needs a human and why — is `docs/process/AUTONOMY.md`.
A session never freelances on `main` and never "claims" work by editing a
markdown file.

**The model (steer #54, standing steers S-2026-08-09-a/b): coding sessions
are the tech leads; humans steer.** You — this session, every other session,
and the scheduled `techlead` planner, all following one charter
(`.github/prompts/techlead.md`) — own the backlog: you log what the humans
say, turn it into requirements and task issues, keep the `ready` queue
stocked and ordered from `docs/PROGRAM.md`, retire what is obsolete, and
decide what the unattended `worker` may take — **and you build**: a tech lead
here sets direction *and* writes code in the same session (steer #58,
S-2026-08-09-c), and may delegate — subagents as hands inside the session,
or extra cloud (CCR) engineer sessions it starts and coordinates, one issue
each under this same protocol (`/fanout`). Humans never have to write a
ticket, assign, review, merge or close anything, and you never tell them to.
**Any time your human volunteers a requirement, an opinion, a priority call
or a correction, log it FIRST — `/steer <their words>`** (project command;
= `python3 tools/dev/techlead.py steer "…" --by <login>`, or in a cloud
session an MCP `issue_write` with label `steer`) — then obey it. Standing
guidance ("always/never/prefer") additionally gets a row in
`docs/STEERING.md`; new work it implies becomes task issues with
`Refs #<steer>` + `from-steer`. Everything you decide lives on GitHub, never
only in the conversation: this session may end mid-sentence and a stranger's
session must be able to continue. The always-current picture is the pinned
**📋 board** issue ([#56](https://github.com/ckaragitz/tekton/issues/56),
label `board`, re-rendered hourly and on every event): in progress, in
review with the exact merge blocker per PR, next up, waiting on a human,
untriaged steers.

**The queue is GitHub Issues.** One issue per task/stream, labelled by
priority (`P0`/`P1`/`P2`), area (`area:engine`, `area:frontdoor`,
`area:famgen`, `area:plugin`, `area:genesis`, `area:docs`, `area:process`, …)
and state (`ready`, or a gate: `blocked`, `needs-viewer`,
`needs-revit-desktop`, `owner-machine`, `needs-decision`), plus provenance
(`from-steer`, `planned`, `from-requirement`) and `hot-file` /
`good-first-pick` / `auto` (cleared for the unattended worker) as fitting.
Title = the checkable DONE; body = Why / DONE / Territory / Evidence /
Context (the *Task* issue form has the shape). **Claiming = being the
issue's assignee.** Assign yourself however your surface allows — `gh issue
edit <n> --add-assignee @me`, the GitHub MCP `issue_write` tool (cloud
sessions have no `gh`), the web UI — or comment `/claim` and the `coord` bot
(`.github/workflows/coord.yml`, no secrets needed) assigns you. **One holder
per issue is enforced, not requested:** if the issue already has an
assignee, a second one is removed again within a minute with a ⛔ comment
naming the holder (a holder *can* add a partner themselves — that is
pairing, and it sticks). If you get the ⛔, pick something else; that
comment is the whole point. `/release` (or unassigning yourself) hands an
issue back. Never start work someone else is assigned to: on this repo's
first night three bugs were filed and fixed twice by two people's sessions
minutes apart, because nobody had claimed anything. **Before filing a new
issue, search for it** (`gh issue list --search "<two or three keywords>"
--state all`, or MCP `search_issues`) — the bot comments likely duplicates
on every new issue, but by then you have already written it. If the work you
want isn't an issue yet, open one (title = the checkable DONE, body =
territory + record path) and assign yourself in the same call.

**Picking work needs no human.** Comment **`/next`** on any issue and the
`coord` bot assigns you the head of the queue (`tools/dev/coord.py queue`:
`ready`, unassigned, not gated, not already answered by an open PR, not
held by the worker; `P0` > `P1` > rest, oldest first) and tells you where
to start — if it says the pick is `retry` work, continue the branch/PR it
names instead of starting over. Choosing by hand is fine too (the board's
*Next up*, or the pinned **"START HERE"** [#25](https://github.com/ckaragitz/tekton/issues/25)
label legend): not on the owner's machine → `ready` only; `P0` before `P1`;
`good-first-pick` for your first PR here.

**Where new work comes from: the tech leads write it.** Inputs, in order of
authority: human steers (logged as `steer` issues — from a session's
`/steer`, the *🧭 Steer* issue form, a `/steer <text>` comment on any
issue/PR, or any free-form issue a human files, which `coord` labels
`intake`), then `docs/PROGRAM.md`, `TRACKER.md`, records' open questions,
red tests. The scheduled planner (`.github/workflows/techlead.yml`, every
6 h and immediately when a steer lands) and any session running
**`/techlead`** turn those into task issues per the charter — bounded
(≤ 5 new issues per pass, queue kept between the floor and ceiling in
`.github/autonomy.json`), search-before-file, one planning note per pass on
the board issue. The unattended **worker** (`worker.yml`, every 2 h, WIP ≤ 2,
≤ 4 runs/day) implements `ready` + `auto` issues exactly as a session
would and opens the PR; the legacy `docs/requirements/` drop-box still files
one issue per merged file. Claims self-heal: the hourly sweep unassigns any
issue held 72 h+ with no open PR and no activity (hardware-gated labels
exempt); a PR the bots cannot finish is not a dead end either — its issue
comes back `ready` + `retry` pointing at the branch.

**Session start protocol (every session, every time) — act as the tech lead
first, the engineer second:**
```bash
git switch main && git pull --ff-only          # start from current trunk
python3 tools/dev/techlead.py brief            # or /board: steers, queue vs floor, PR blockers, waiting-on-human
gh pr list --author @me --state open           # 1. service your own PRs first (below) — and squash-merge any PR labelled
                                               #    `session-merge` (bots may not; you can): green CI + verdict, or read the diff
#  2. your human said something directional this session? -> /steer "<their words>"  (before acting on it)
#  3. untriaged steers, or ready&unassigned below the floor? -> /techlead  (≤10 min, charter-bounded)
gh issue list --assignee @me --state open      # 4. resume yours, or take the head of the queue:
gh issue comment <any> -b /next                #    (or claim by hand: gh issue edit <n> --add-assignee @me)
git switch -c <you>/<issue#>-<slug>            # one issue = one branch = one PR, always from main
#  5. more independent ready issues than you can hold? -> /fanout (engineer sessions / subagents), keep building yours
```
Cloud sessions (no `gh` CLI) do the same through the GitHub MCP tools:
`issue_read` on the board issue for the picture, `issue_write` with label
`steer` to log a steer, `add_issue_comment` with body `/next` or `/claim`
to take work, `issue_write` (assignees) to claim by hand. Either way, glance
at the issue a minute later (`gh issue view <n>` / `issue_read`): a ⛔ from
the bot means someone beat you to it — stop and pick another.
**Before picking new work, service your own open PRs** — this is how a
session "gets notified": it looks.
```bash
gh pr list --author @me --state open --json number,title,isDraft,labels,statusCheckRollup \
  --jq '.[]|"#\(.number) \(.title) draft=\(.isDraft) labels=\([.labels[].name]|join(",")) checks=\([.statusCheckRollup[]?|.conclusion//"…"]|join("/"))"'
gh pr view <n> --comments        # read the review summary, inline notes, automerge/needs-human comments
```
If a PR of yours is red, has `🛑 Changes requested`, or carries `bot-stuck` /
`needs-human`: fix that first (address each blocking bullet, run your gates,
push to the same branch — the bots re-run on the new commit and the labels
clear themselves; remove `needs-human` with
`gh pr edit <n> --remove-label needs-human` once you've pushed a real fix).
Cloud sessions (claude.ai/code) can instead turn on **Auto-fix** in the PR's CI
bar (or run `/autofix-pr` in a terminal session) so the session itself watches
CI failures and review comments and pushes fixes — it has the first
`fix_grace_minutes` (15) after each signal to itself; the bots only step in after
that. A PR you simply walk away from is fine: the bots review it, dispatch
bounded fixes after the grace window, mark a green + approved draft ready after
90 quiet minutes, merge it, and close the issue — or, if they cannot, re-queue
the issue `ready` + `retry` with your branch named.

Then read the issue, `KNOWLEDGE.md`, and any `docs/inbox/` records it cites
before writing code.

**Branch → PR → main (standard trunk-based flow):**
- `main` is protected: no direct commits; merge only via PR with review +
  green checks; squash-merge; delete the branch.
- Keep PRs small and short-lived; `git fetch && git rebase origin/main`
  before pushing; resolve conflicts on *your* branch, never by force-pushing
  shared branches.
- **Never stack a PR on another PR's branch.** `main` squash-merges; when the
  parent's branch is then deleted by hand (`gh pr merge --delete-branch`,
  `git push --delete`) GitHub closes the stacked child **unmerged** and
  nobody is told (#39 was lost this way and #40 stranded on a dead base).
  Branch from `main`; if you depend on an unmerged PR, wait for it or say so
  on the issue. Mergers: let the repo's *automatically delete head branches*
  setting do the deleting (GitHub then retargets children instead of closing
  them) rather than `--delete-branch`. The `coord` bot warns on stacked PRs
  and its hourly sweep retargets/reopens stranded ones, but that is a safety
  net, not a workflow.
- The PR **must** include the stream record `docs/inbox/<stream>.md` (with
  its closing `BRANCH STATE`), the stream-local tests you ran (counts), and
  `tools/sync_plugin.py --check` clean if you touched `src/`/`tools/`/`skills/`.
  Link the issue (`Closes #n`). The PR template carries the checklist.
- CI: the `CI` workflow (`.github/workflows/ci.yml`) runs on every PR and on
  pushes to `main` — jobs `py3.11` and `py3.12` on ubuntu-latest, each running
  `tools/dev/check_portable_paths.py`, `tools/sync_plugin.py --check`,
  `plugin/scripts/validate_plugin.py`, then the fast shard listed in
  `tests/ci_shard.txt` (never the full suite — see
  `docs/inbox/SUITE-COORDINATION.md`). Red CI blocks merge — fix, don't
  bypass.

**Git cadence on your laptop (several engineers, sessions that come and go):**
```bash
git config pull.rebase true && git config rebase.autoStash true   # once per clone
```
- **Start of every session:** `git fetch origin --prune`; on your branch
  `git rebase origin/main` (or `git switch main && git pull --ff-only`
  before cutting a new branch). Never build on a stale trunk.
- **While working:** small commits, each one logical change that leaves
  tests for your area green. **Push early** — after the first meaningful
  commit run `git push -u origin HEAD` and open a **draft PR**
  (`gh pr create --draft --fill`, body starting `Closes #<n>`) so the other
  humans/sessions can see the branch and its territory exist. Keep pushing
  as you go; a laptop that sleeps with unpushed commits is invisible work,
  and so is a pushed branch with no PR — the `coord` bot's hourly sweep
  surfaces any branch left that way for 20+ minutes (a bot-opened draft PR
  you then have to adopt or close, or a line on its tracking issue if the
  repo does not let Actions open PRs), so beat it to it.
- **Re-sync often:** `git fetch && git rebase origin/main` at least at the
  start and end of each session and always right before marking the PR
  ready; if `main` moved under a file you touch, rebase *now*, not at the
  end. After a rebase of an already-pushed branch use
  `git push --force-with-lease` (never plain `--force`, never on `main`,
  never on a branch someone else is also committing to).
- **End of every session:** everything committed and pushed; the draft PR
  description says where you stopped (or the record's `BRANCH STATE`
  does); the issue stays assigned to you. If you're abandoning it,
  unassign yourself and say so on the issue.
- **Ready for review:** rebase on `origin/main`, run your gates, fill the PR
  template, `gh pr ready`. Reviewer merges with **squash**; delete the
  branch; `git switch main && git pull --ff-only` before the next task.
- **Conflicts:** resolve them on your branch during rebase; if the conflict
  is in someone else's active territory or a hot file, talk on the issue
  first rather than guessing. Never "resolve" by reverting their change.
- **Portable paths:** collaborators are on Windows and macOS — no filenames
  containing `? : * " < > |` or backslashes, no trailing dots/spaces, no
  `CON`/`NUL`-style names, keep paths < 240 chars, no case-only twins.
  `python tools/dev/check_portable_paths.py` checks the tracked tree (CI
  runs it); scripts that write `<name>.json` must never run with an empty name.
- **Never:** commit directly to `main`; force-push `main`; rewrite history
  others have pulled; leave generated artifacts or ignored-dir content in
  a commit; let a branch live for more than a few days without rebasing.

**What happens after you open a PR — fully automatic (`.github/workflows/`):**
Contributors here are mostly *not* developers; their coding sessions open PRs and
the repo takes it from there. Tell your human plainly: "PR is open; nothing for
you to do unless the bot asks for a human."
0. **`coord`** (token-free, always on) checks the PR the moment it opens or its
   description changes: no `Closes #N`/`Refs #N` → label `needs-issue`; the linked
   issue unclaimed → it assigns the PR author; the linked issue held by someone
   else, or a second open PR closing the same issue → label `overlap` + a comment
   on the spot (settle it then, not at merge time); base branch not `main` →
   `stacked` warning; "does not close #N" in the body → warning, because GitHub's
   linker ignores the *not* and will close #N. Read what it says and act on it.
1. **`CI`** runs on every push (~1–2 min): portable paths, `sync_plugin.py --check`,
   `validate_plugin.py`, the fast no-samples shard (`tests/ci_shard.txt`).
2. **`claude-review`** reviews every push (~5–15 min) against this file's rules and
   the linked issue's DONE, posts inline comments + one summary whose first line is
   the verdict (✅ Approve / 🟡 Nits only / 🛑 Changes requested) and whose last line is
   a machine-readable marker for that exact head SHA (a short rescue pass posts it if
   the review ran out of turns; `automerge` re-requests a review whose verdict is
   still missing). **Fixing is single-owner (steer #67): on red CI or 🛑, your live
   session goes first** — that is what its PR subscription / Auto-fix is for. The
   bots do *not* fix immediately: only when nothing has been pushed for
   `pipeline.fix_grace_minutes` (15) after the last signal does `automerge` dispatch
   ONE bot fix pass for the current head (budget 3 attempts per PR since the last
   budget reset, `.github/autonomy.json`) — which is also how a PR is carried when
   your session or laptop is gone. If you see the bot's `🔧 dispatched the bot fix
   pass` comment for your head, let it push (or push first — it yields to a newer
   head); never race it. Budget exhausted → label `bot-stuck`, which is **not** a
   human dead-end: after a quiet day the `board` sweep re-queues the issue `ready` +
   `retry`, unassigned, naming the branch, and `/next` or the worker continues it
   with a fresh budget.
3. **`automerge`** squash-merges as soon as: CI green on the head SHA **and** the
   review verdict for that SHA is Approve/Nits **and** the PR is ready — or is a
   **draft that has been quiet (no commits) for 90 min**, which it then marks ready
   itself (label `wip` holds a draft). It deletes the branch and **closes the linked
   issues itself** (bot merges do not reliably fire GitHub's `Closes #N` linker —
   #50 stayed open after #51). It refuses (and comments why) on red checks or a
   missing verdict and re-checks on every new commit and every 30 minutes; zero
   checks → it dispatches CI; missing verdict → it re-requests the review;
   conflicts → it dispatches the worker's rebase mode. **Duplicate rule:** if two
   open PRs close the same issue, the older PR wins and the newer gets
   `duplicate-pr` for the planner to settle — so *`/claim` the issue before you
   start*; `coord` will already have flagged the pair with `overlap` when the
   second PR opened.
4. Escape hatches (humans only): `do-not-merge` holds a PR; `wip` keeps a draft
   from being auto-readied; `merge-when-green` applied by someone other than the
   author (or by the owner) substitutes for the AI verdict when the review bot is
   down or wrong; `@claude <instruction>` in any comment makes the bot answer or
   push a change; label `bots-paused` on the board issue idles planner + worker.
   PRs touching `.github/workflows/**` cannot be merged by the Actions token
   (GitHub restriction), and a PR that edits `claude-review.yml` cannot even be
   bot-reviewed → automerge labels them **`session-merge`: the next coding
   session — anyone's, at session start — checks CI + verdict (or reads the diff)
   and squash-merges with its own credentials** (`gh pr merge <n> --squash` or MCP
   `merge_pull_request`); a session runs under a human's GitHub identity, so
   GitHub allows it (steer #61, S-2026-08-09-d). Nothing waits on the owner for
   that; the optional `AUTOMERGE_TOKEN` secret only makes it hands-free
   (docs/process/AUTONOMY.md §10). `needs-decision` questions, viewer uploads,
   desktop-Revit checks, owner-machine work and a merge GitHub itself refused
   (`needs-human`) are the **complete** list of things that wait for a person,
   and the board's *Waiting on a human* section shows them with the reason.
5. So a session's PR checklist is: link the issue (`Closes #N`), include the record,
   run your stream-local gates, push, open the PR **ready** (not draft) when done —
   or draft early and `gh pr ready <n>` when finished (or just leave: a green,
   approved, quiet draft is readied and merged for you). **Then turn on Auto-fix for
   that PR, every time** — cloud session (claude.ai/code or Desktop-in-cloud): the
   PR's CI status bar → **Auto-fix**, or just say "auto-fix this PR: watch CI
   failures and review comments"; terminal session on the PR branch: `/autofix-pr`.
   That makes *your own session* wake on red CI / review comments and push fixes
   while it is alive (needs the Claude GitHub App on the repo; uses your plan, no
   repo secret); the repo's bots cover for it after it is gone. Tell your human you
   did it. Then stop; read the bot's comments if it pings.
6. One-time setup this depends on (repo admin): Claude GitHub App installed on the
   repo, and an Actions secret `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`
   on the owner's *personal* plan — standing steer S-2026-08-08-a) or
   `ANTHROPIC_API_KEY`. Without it `claude-review`, `techlead` and `worker` are red
   or skipped on purpose (the board's Health line shows it), only the
   `merge-when-green` label path can merge, and sessions do the planning at session
   start. **`coord`, `board`, `CI` and `automerge` need no secret** and keep working
   either way. Two token-free repo checkboxes do most of `coord`'s sweep work
   structurally: *Settings → General → Automatically delete head branches* (GitHub
   deletes merged branches itself and retargets stacked children instead of closing
   them) and *Settings → Actions → General → Allow GitHub Actions to create and
   approve pull requests* (the orphan-branch sweep can open the draft PR itself
   instead of listing branches on a tracking issue).

**Hot files — serialize, don't stack.** `tools/frontdoor.py`,
`plugin/skills/*/SKILL.md`, `src/rvt/versions/`, `src/rvt/frontdoor/base.py`,
`TRACKER.md`, `KNOWLEDGE.md`, `docs/coverage/viewer-certified.json`: changes
need an issue labelled `hot-file`, a tiny dedicated PR, and a merge the same
day. Everything else: prefer **new modules in your territory** and deliver
edits to shared files as a patch in your record if someone else holds them.
`experiments/<stream>/**` is namespaced per stream, so probes never collide.

**Roles.** There is no human orchestrator any more: *orchestration is the
tech-lead loop* — the scheduled planner plus every session at session start,
one charter (`.github/prompts/techlead.md`). That loop triages steers, keeps
the queue and its labels healthy, keeps `TRACKER.md` / `docs/PROGRAM.md`
current **via small PRs** (curated roadmap and goals — never the live claim
board; Issues + the 📋 board are), folds `docs/inbox/learned-*.md` notes
into `KNOWLEDGE.md`, and merges `session-merge` PRs. Humans keep exactly the
physical and reserved things (docs/process/AUTONOMY.md §10): answering
`needs-decision` issues, uploading STAGED viewer batches and recording verdicts
(`docs/coverage/viewer-certified.json` + `docs/inbox/genesis-audit.md`,
`hot-file` PR — a session prepares the PR, the human supplies the verdicts),
desktop-Revit checks, owner-machine runs, and keeping the token/billing alive. Contributors'
sessions STAGE viewer batches on their branch (`probe_batch.py stage`) and
stop at READY, as before.

- **Streams.** Substantial work is still chartered as a stream with a
  *territory* (files it may touch), a checkable *DONE*, and a *record* — the
  issue is the charter. Streams file their own follow-ups as task issues
  (task-shaped, `Refs #<parent>`) — that is tech-lead work, not scope creep —
  and never by editing `TRACKER.md` in passing.
- **Every stream writes `docs/inbox/<stream>.md`**: what was built, the
  evidence (numbers, not adjectives), findings, open questions, and a
  closing **`BRANCH STATE`** block (files written, gates, what's staged vs
  shipped). Durable lessons go to `docs/inbox/learned-<slug>.md`; the
  orchestrator merges them into `KNOWLEDGE.md`.
- **No cross-voice writes**: never write into another stream's record in
  its voice; additions elsewhere go under a header naming *your* stream.
- **Territory discipline**: put new code in new modules; deliver edits to
  shared/hot files (`tools/frontdoor.py`, `plugin/skills/*/SKILL.md`,
  `src/rvt/frontdoor/base.py`, `src/rvt/versions/`) as patches in your
  record unless you own them this round. Mutating tools that write shared
  experiment dirs take a pid lockfile.
- **Evidence discipline**: single-variable experiments with matched
  pass/fail pairs; controls in every batch; an instrument bug voids the
  readings taken with it (re-run, don't reinterpret); "faster" needs a
  measured before/after from a bare environment.
- **Commits**: plain descriptive messages about what the change does; one
  logical change per commit; reference the issue. Regenerate rather than
  commit build artifacts. Never commit anything from the ignored third-party
  dirs, and never a presenter cheat sheet (`ANSWER_KEY.md`,
  `DEMO_RUNBOOK.md`, `demo-talk-track.md`). Never force-push `main` or a
  branch someone else has pulled.

## 5. Where things stand (read `KNOWLEDGE.md` for the full arc)

Certified by Autodesk's reader: composed genesis bases for **2026/2025/2024**
(2023 base certified, compose pending); native creation of projects +
walls (render) + edits incl. foreign files; family **generation** (`.rfa`);
loading any Revit-born `.rfa` and extract→place onto our bases; our
generated equipment placed **into existing/pristine projects**
(`add_to_project`). Two format laws found and fixed forever: the mandatory
64-byte `0x0f3f` unit footer blob, and the D1–D5 corpus laws.
**The one open cell:** *our generated* families + placed instances on
*our composed* bases fail Autodesk's audit while byte-equivalent-by-every-
instrument variants pass — 26 single-variable rounds are logged in
`docs/inbox/genesis-audit.md` (#31–#48); the next signal is desktop Revit's
own error dialog (`experiments/terminal/REVIT-CHECK-KIT.md`). Don't
re-suspect an exonerated axis without new evidence — check the ledger first.
