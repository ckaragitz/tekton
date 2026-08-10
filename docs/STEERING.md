# STEERING — standing guidance from the humans, in force until they say otherwise

Auto-loaded into every coding session (imported by `CLAUDE.md`). Every human steer is first
logged verbatim as a `steer` issue (docs/process/AUTONOMY.md §5); the ones that are *standing*
— a rule, a preference, a priority principle that should shape future decisions — get one row
here so no future session has to be told twice. These outrank a tech lead's own judgement and are
outranked only by the hard rules in `CLAUDE.md` §1 (a steer that conflicts with those becomes a
`needs-decision` issue instead of a row). One row per steer; newest last; never rewrite a row —
supersede it with a new one that says so.

| ID | Date | From | Standing steer | Logged in |
|---|---|---|---|---|
| S-2026-08-04-a | 2026-08-04 | owner | tekton must be drivable from ANY AI surface with any of three inputs (prompt, IFC, existing Revit file); everything ships inside the plugin as skills + references; a hosted MCP server is the documented future path, not built now. | `TRACKER.md` Epic P |
| S-2026-08-08-a | 2026-08-08 | owner | This is a personal/home project: do not wire *work* (employer) API keys or OAuth tokens into its automation. Model-backed bots run on the owner's personal Claude token or not at all; everything else must work on the built-in `GITHUB_TOKEN`. | #46 / `docs/inbox/coord-guards.md` |
| S-2026-08-09-a | 2026-08-09 | ck | Coding sessions are the tech leads: they own the task list, requirements and stories and derive them from the program goals; humans steer, and every steer is logged verbatim (as a `steer` issue) before it is acted on, then tracked to the issues it produced. Never answer a steer with "a human needs to write the ticket". | #54 |
| S-2026-08-09-b | 2026-08-09 | ck | Nothing may depend on a live session or a switched-on laptop: all state lives in GitHub, all automation runs server-side, and the path from pushed code to merged PR needs no human click. Whatever genuinely needs a person is listed, with the reason, where humans look (the board). | #54 |
| S-2026-08-09-c | 2026-08-09 | ck | Tech-lead sessions plan **and** build — the same session sets direction and writes code — and may delegate: subagents as hands inside the session, or additional cloud (CCR) sessions started and coordinated as engineers, one issue each under the same claim/branch/PR protocol. Planning must never crowd out building. | #58 |
| S-2026-08-09-d | 2026-08-09 | ck | When bots cannot perform a step but a session's own (human-attributed) credentials can — e.g. merging a PR that touches `.github/workflows/**`, which the Actions token is blocked from doing — the session does it itself and codifies the mechanism, rather than parking it on the owner. Work never waits on a human for a reason a session's own credentials already clear. | #61 |
| S-2026-08-09-e | 2026-08-09 | ck | One owner per pipeline step. Where a live session and a bot could both act (fixing a red / 🛑 PR), the session goes first and the bot acts only after a grace window sized to CI + review latency; nothing may depend on the session staying alive beyond that window. | #67 |
| S-2026-08-09-f | 2026-08-09 | ck | Work is pulled from one shared ordered queue and locked at pull time — per session, not just per login. Nobody assigns work by hand; a session never resumes an issue another live session (even under the same login) is visibly working. | #90 |
| S-2026-08-09-g | 2026-08-09 | ck | Plugin/skill-path latency is a first-class product requirement — cold start, per-call bootstrap, import weight, tool round-trips per skill flow, and SKILL.md/reference token weight are all product performance, not internal cleanup. Latency work is only "done" with a measured before/after from a bare surface (`tools/surface_bench.py`). | #108 / #110 |
| S-2026-08-09-h | 2026-08-09 | ck | When asked to run continuously, the tech-lead loop keeps itself alive server-side (scheduled wake-ups into the session plus the repo's planner/worker), fans work out to engineer sessions at bounded concurrency, and logs everything it decides on GitHub — never something only a live session's log shows. | #108 |
| S-2026-08-09-i | 2026-08-09 | ck | No paid GitHub Actions minutes and no self-hosted runner — the code→review→merge pipeline must not depend on GitHub-hosted compute. GitHub stays the ledger; CI (sandboxed), independent review, merging through the API, claims and the board are done by the sessions themselves; workflow files stay dispatch-only reference designs; anything re-enabled later must fit the free quota (nightly at most, never per-push). | #302 |
| S-2026-08-10-a | 2026-08-10 | owner | Generated families always carry a Revit-born family's view set (Ref. Level plan, ceiling plan, four elevations, the "View 1" 3D view): every family factory goes through the shared view constellation; a family without them is incomplete, not "minimal". | #381 (logged by the clkaragitz session that received it) |

Older standing decisions that predate this ledger live in `CLAUDE.md` §1 (the hard rules — e.g.
no APS, decided twice) and in `KNOWLEDGE.md`; they are not repeated here.
