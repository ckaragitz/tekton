# tekton — working guide for coding sessions

You are in **tekton**: a pure-Python interoperability engine that reads,
creates, edits, validates, and converts Autodesk Revit `.rvt` / `.rfa`
containers **without a Revit install, an Autodesk seat, or APS**. Revit is
the last-mile *deliverable* format — a licensed engineer opens our output
for QA. Read this file fully before touching anything; then read
`KNOWLEDGE.md` (the ledger: institutional memory), `docs/ORCHESTRATOR.md`
(state: what is live, how to ship, what is running, the P0 shipping gates)
and the open GitHub Issues (the work queue, `now` first — §4). `TRACKER.md`
is retired (2026-10-08) and `docs/archive/` is history: read it only when
an issue, a ledger entry or a cited row key sends you there.

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
drift + portable paths). This file and `.claude/agents/` load automatically.
Work on a branch, push, and open the PR from the session UI (or `gh pr create
--draft`) exactly as in section 4.

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
product skills aren't auto-loaded into the session that is editing them),
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
sessions. Coordination is **GitHub Issues + trunk-based git**, with this
repo's record conventions riding on top. A session never freelances on
`main` and never "claims" work by editing a markdown file. There is no
tracker file: `TRACKER.md` was retired on 2026-10-08 (old body:
`docs/archive/2026-10/TRACKER-2026-10.md`; the row keys that code,
manifests and docs still cite — `G2`, `G4b`, `D4`, `F8`, `P1` … — resolve
there, and the P0 shipping-gate status now lives in `docs/ORCHESTRATOR.md`).

**Who you are decides what you may write — decide first, every session.**
- **Direct session** — a person started you (terminal, desktop, web,
  Slack / Claude Tag, a cloud session they opened) and gave you the task in
  their own words. You own the externalized context for your task and
  update it before you stop: the issue(s) you worked (claim → close with
  evidence), the plan you worked under (`docs/plans/`), `KNOWLEDGE.md` (the
  entries your work produced), `docs/ORCHESTRATOR.md` (if what is live /
  how to ship / what is running / a P0 gate changed), and `README.md` /
  `plugin/docs/**` when what the product does changed. `KNOWLEDGE.md` and
  `docs/ORCHESTRATOR.md` are hot files, so that update is its own tiny
  `hot-file` PR. A session that fans work out to other sessions is still
  the direct session and owns all of this for everything it delegated.
- **Delegated session** — another session started you (a subagent, a cloud
  fan-out, a workflow step, a charter or `AGENT_BRIEF.md` handed to you as
  your first message). You write code on your branch plus ONE record,
  `docs/inbox/<stream>.md`, ending in the literal line
  `READY for review — <branch> @ <sha>`, and you never touch
  `KNOWLEDGE.md`, `docs/ORCHESTRATOR.md`, the viewer ledger, `main` or
  another branch. Your parent folds the record in and archives it.
- Can't tell → default to delegated and say so in your first message.
- One direct session at a time edits the ledger files (that is what the
  `hot-file` label serializes); if a pull shows someone else moved them,
  rebase onto theirs first.

**The queue is this repo's GitHub Issues** — never a file, and never a
session-local task list or plan (nothing outside your session can see
those). One issue per outcome.
- **Kind, one label each:** `fr` (a user story written as the outcome, with
  what done looks like and the files involved by repo path) · `stream` (a
  broad directive — the parent: the direct session that picks it up writes
  the charter `docs/plans/<issue>-<slug>.md` and splits it into child
  issues that say "Part of #N"; the parent closes when its children do) ·
  `bug` · `look` (a viewer / render / UX finding, frame attached) ·
  `proposal` (a `KNOWLEDGE.md` entry to ratify, text verbatim) ·
  `owner-decision` (only the owner can answer: counsel items C1 / C4 / C5,
  trademark, pricing, the target Revit release) · `documentation`.
- **Area and repo-state labels (unchanged):** `engine`, `frontdoor`,
  `famgen`, `plugin`, `genesis`, `docs`, … · `ready` (doable from a fresh
  clone — no `samples/`, no viewer login) · `hot-file` · `needs-viewer` ·
  `good-first-pick` · `P0` / `P1` (shipping-gate severity).
- **Workflow labels:** `claimed`, `blocked`, `ready-for-review`.
- **Priority is the owner's:** `now` · `next` · `later`. Set them only on
  the owner's explicit word, quoting it in a comment. Pick from `now`
  first, then `next` (inside a band, `P0` before `P1`); `later` is parked —
  ask before starting. No priority label = triage: work it only if it is
  small and clearly in scope, otherwise ask.
- **Lifecycle:**
  1. **File** — search open issues first. Title = the checkable DONE,
     body = territory + record path.
  2. **Claim before you start** — assign yourself
     (`gh issue edit <n> --add-assignee @me`; atomic, visible to everyone,
     and automerge's duplicate rule leans on it), add `claimed`, and leave
     one comment: `Claimed by <who> (<session id/name>) · branch <name> ·
     <date>` plus a link to the plan. One claimant: never start work
     someone else holds, except a claim older than 48 h with no commit on
     its branch, which is free to take (say so on the issue). Release =
     unassign + remove the label + one line.
  3. **Work** on a branch named for the issue; anything new you discover
     is a new issue, never a line in a file.
  4. **Blocked** — label `blocked` + a comment naming exactly what you
     need and from whom.
  5. **Ready** — push, with the gate numbers verbatim in the PR. A
     delegated session leaves the PR draft, adds `ready-for-review` to the
     issue and stops. A direct session takes it to the merge gate, which
     here is a machine: mark the PR ready and let CI + `claude-review` +
     `automerge` land it (below).
  6. **Close** — only with evidence, as a comment on the issue: the merge
     sha on `main` AND the ship state (there is no deploy step here: say
     "plugin zip not rebuilt", or what was rebuilt / re-certified and who
     has it), the `KNOWLEDGE.md` entries ratified, records archived.
     `Closes #N` closes the issue at merge; the evidence comment is still
     owed. Never close an issue whose change is not on `main`.
     `owner-decision` issues close quoting the owner.
- **Views replace lists:** open `fr` = backlog · open `stream` = chartered ·
  `claimed` = in flight · `now` = do first · `owner-decision` = waiting on
  the owner · `proposal` = to ratify · `ready-for-review` = waiting on a
  gate · `P0` = the shipping gates.
- Cloud sessions: where `gh issue` porcelain is refused, use REST —
  `gh api "repos/ckaragitz/tekton/issues?state=open&labels=now"`. If a
  label above does not exist on the repo yet, create it.

**Don't know what to work on? That's expected.** Read the pinned issue
**"START HERE"** ([#25](https://github.com/ckaragitz/tekton/issues/25)):
it explains the area labels and how to choose (it predates the kind /
workflow / priority labels above; where they disagree, this file wins).
Rule of thumb: `now` first, then `next`; if you are not on the owner's
machine, pick `ready` issues (doable from a fresh clone — no `samples/`,
no viewer login), `P0` before `P1`, and `good-first-pick` for your first
PR here.

**Session start protocol (every session, every time):**
```bash
git switch main && git pull --ff-only          # start from current trunk
gh issue list --assignee @me --state open      # resume yours, or:
gh issue list --label now --search "no:assignee"     # the owner's do-first band, then `next`
gh issue list --label ready --search "no:assignee"   # pick one, then claim it (assign + `claimed` + comment)
git switch -c <you>/<issue#>-<slug>            # one issue = one branch = one PR
```
**Before picking new work, service your own open PRs** — this is how a
session "gets notified": it looks.
```bash
gh pr list --author @me --state open --json number,title,isDraft,labels,statusCheckRollup \
  --jq '.[]|"#\(.number) \(.title) draft=\(.isDraft) labels=\([.labels[].name]|join(",")) checks=\([.statusCheckRollup[]?|.conclusion//"…"]|join("/"))"'
gh pr view <n> --comments        # read the review summary, inline notes, automerge/needs-human comments
```
If a PR of yours is red, has `🛑 Changes requested`, or carries `needs-human`:
fix that first (address each blocking bullet, run your gates, push to the same
branch — the bots re-run on the new commit; remove `needs-human` with
`gh pr edit <n> --remove-label needs-human` once you've pushed a real fix).
Cloud sessions (claude.ai/code) can instead turn on **Auto-fix** in the PR's CI
bar (or run `/autofix-pr` in a terminal session) so the session itself watches
CI failures and review comments and pushes fixes.

Then read the issue, its plan in `docs/plans/` if it has one,
`KNOWLEDGE.md`, and any `docs/inbox/` records it cites before writing code.

**Branch → PR → main (standard trunk-based flow):**
- `main` is protected: no direct commits; merge only via PR with review +
  green checks; squash-merge; delete the branch.
- Keep PRs small and short-lived; `git fetch && git rebase origin/main`
  before pushing; resolve conflicts on *your* branch, never by force-pushing
  shared branches.
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
  (`gh pr create --draft --fill`) so the other humans/sessions can see the
  branch and its territory exist. Keep pushing as you go; a laptop that
  sleeps with unpushed commits is invisible work.
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
1. **`CI`** runs on every push: portable paths, `sync_plugin.py --check`,
   `validate_plugin.py`, the fast no-samples shard (`tests/ci_shard.txt`).
   If CI finishes **red**, `claude-review`'s `ci-autofix` job reads the failed log,
   makes the smallest in-territory fix, re-runs the CI commands locally, and pushes
   (same 2-attempt budget; exhausted → `needs-human`).
2. **`claude-review`** reviews every push against this file's rules and the linked
   issue's DONE, posts inline comments + one summary whose first line is the
   verdict (✅ Approve / 🟡 Nits only / 🛑 Changes requested) and whose last line is a
   machine-readable marker for that exact head SHA. On 🛑 it runs a **bounded
   auto-fix pass** (max 2 attempts per PR): edits, runs the gates, pushes to your
   branch, which re-triggers CI + review. Still 🛑 after 2 → label `needs-human`.
3. **`automerge`** squash-merges as soon as: not draft **and** CI green on the head
   SHA **and** the review verdict for that SHA is Approve/Nits. It deletes the
   branch; `Closes #N` closes the issue. It refuses (and comments why) on zero/red
   checks, conflicts, or a missing verdict, and re-checks on every new commit and
   every 30 minutes. **Duplicate rule:** if two open PRs close the same issue, the
   older PR wins and the newer gets `needs-human` — so *assign yourself to the
   issue before you start*.
4. Escape hatches (humans only): `do-not-merge` holds a PR; `merge-when-green`
   applied by someone other than the author (or by the owner) substitutes for the
   AI verdict when the review bot is down or wrong; `@claude <instruction>` in any
   comment makes the bot answer or push a change. PRs touching
   `.github/workflows/**` can never be bot-merged (GitHub restriction) → owner
   merges those by hand.
5. So a session's PR checklist is: link the issue (`Closes #N`), include the record,
   run your stream-local gates, push, open the PR **ready** (not draft) when done —
   or draft early and `gh pr ready <n>` when finished. **Then turn on Auto-fix for
   that PR, every time** — cloud session (claude.ai/code or Desktop-in-cloud): the
   PR's CI status bar → **Auto-fix**, or just say "auto-fix this PR: watch CI
   failures and review comments"; terminal session on the PR branch: `/autofix-pr`.
   That makes *your own session* wake on red CI / review comments and push fixes
   (needs the Claude GitHub App on the repo; uses your plan, no repo secret). Tell
   your human you did it. Then stop; read the bot's comments if it pings.
6. One-time setup this depends on (repo admin): Claude GitHub App installed on the
   repo, and an Actions secret `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`)
   or `ANTHROPIC_API_KEY`. Without it `claude-review` fails red on purpose and only
   the `merge-when-green` label path can merge.

**Hot files — serialize, don't stack.** `tools/frontdoor.py`,
`plugin/skills/*/SKILL.md`, `src/rvt/versions/`, `src/rvt/frontdoor/base.py`,
`KNOWLEDGE.md`, `docs/ORCHESTRATOR.md`, `docs/coverage/viewer-certified.json`:
changes need an issue labelled `hot-file`, a tiny dedicated PR, and a merge
the same day. Everything else: prefer **new modules in your territory** and deliver
edits to shared files as a patch in your record if someone else holds them.
`experiments/<stream>/**` is namespaced per stream, so probes never collide.

**Roles.** The *orchestrator* is a rotating human role, not a bot: they
triage issues, set (or relay the owner's) `now · next · later`, and
run/record viewer certification rounds. There is no roadmap file to keep
current — the views over Issues are the roadmap, and standing state is
`docs/ORCHESTRATOR.md`. Ledger entries are ratified by the **direct
session** that lands the work (a `hot-file` PR to `KNOWLEDGE.md`), not
batched for the orchestrator. Contributors STAGE viewer batches on their
branch (`probe_batch.py stage`) and stop at READY; whoever uploads records
verdicts in `docs/coverage/viewer-certified.json` +
`docs/inbox/genesis-audit.md` via a `hot-file` PR.

- **Streams.** Substantial work is still chartered as a stream with a
  *territory* (files it may touch), a checkable *DONE*, and a *record*: a
  `stream` issue plus its charter `docs/plans/<issue>-<slug>.md` (a small
  task's issue is its own charter). Streams propose follow-ups by opening
  issues; a delegated session that cannot reach GitHub lists them in its
  record and its parent files them. Never a line in a file.
- **Every stream writes `docs/inbox/<stream>.md`**: what was built, the
  evidence old → new (numbers, not adjectives), gate numbers verbatim,
  findings, open questions, a `## Proposed KNOWLEDGE entry` section for
  durable lessons, and a closing **`BRANCH STATE`** block (files written,
  gates, what's staged vs shipped, tip sha); a delegated session ends it
  with the literal line `READY for review — <branch> @ <sha>`. Proposed
  ledger entries ride inside that one record (no separate
  `learned-<slug>.md`; the two in `docs/inbox/` predate this). The direct
  session that lands the branch ratifies or declines them in
  `KNOWLEDGE.md` and archives the record (`docs/inbox/README.md`).
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

**Plans are charters — not the queue, not the ledger.**
`.claude/settings.json` sets `"plansDirectory": "docs/plans"`, so plan mode
writes into the repo instead of `~/.claude/plans`. Rename the plan
`docs/plans/<issue>-<slug>.md`, commit it on the branch, link it from the
issue's claim comment, keep it current, and `git mv` it to
`docs/archive/<YYYY-MM>/plans/` in the PR that closes the issue. The issue
says who is doing what; the plan says how; `KNOWLEDGE.md` says what was
decided.

**Keep the externalized context small and true (archive rule).**
- **Live set:** this file, `KNOWLEDGE.md`, `docs/ORCHESTRATOR.md`,
  `README.md`, `AGENT_BRIEF.md`, `RENAME.md`, `docs/product/`,
  `docs/writer/`, `docs/streams/`, `docs/legal/`, `docs/acceptance-log.md`,
  `plugin/docs/**`, open plans in `docs/plans/`, un-ingested records in
  `docs/inbox/` plus its two live files (`genesis-audit.md`,
  `SUITE-COORDINATION.md`).
- **Archive when** a thing stops being true (record ingested, stream
  merged or abandoned, a doc superseded, the state file rewritten) — in
  the SAME PR that supersedes it. **How:** `git mv` to
  `docs/archive/<YYYY-MM>/<same relative path>`; one line in
  `docs/archive/README.md` (what · why · superseded by); grep the repo
  and fix live references (code comments and docs cite records by path).
- **Contracts are never archived:** anything a test, tool or CI step
  reads — `docs/coverage/viewer-certified.json`, `docs/coverage/matrix.json`,
  `tests/ci_shard.txt`, evidence paths `src/rvt/frontdoor/matrix.py`
  verifies, manifests under `experiments/`. Delete outright (don't
  archive): scratch captures, logs, duplicates.
- Never read `docs/archive/` cold — only when an issue, a ledger entry or
  a cited row key points there.
- **Tripwire:** if `docs/ORCHESTRATOR.md`'s "as of" is more than 14 days
  old, or `docs/inbox/` holds a record added after 2026-10-08 whose branch
  is already on `main`, fix that before your own task. (The ~150 August
  records are a known backlog — `docs/ORCHESTRATOR.md`, open fronts.)
- **Shipping honesty:** end your summary with the ship state. Nothing
  here deploys; say whether `tekton-plugin.zip` was rebuilt and, if a
  step is owed (a viewer round, a rebuild on the owner's machine), the
  exact command and the machine it must run from.

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
