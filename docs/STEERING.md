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

Older standing decisions that predate this ledger live in `CLAUDE.md` §1 (the hard rules — e.g.
no APS, decided twice) and in `KNOWLEDGE.md`; they are not repeated here.
